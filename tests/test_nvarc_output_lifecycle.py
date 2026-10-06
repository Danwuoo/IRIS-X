"""E01 bounded CPU publication faults; no provider/GPU/neural benchmark."""
import copy
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import nvarc_output_lifecycle as lifecycle
from tools import nvarc_public_eval as public
from tools import nvarc_public_eval_parent as parent
from tools import nvarc_native_export as native_export
from tools import nvarc_official_parent as official
from tools import nvarc_official_adapter as adapter
from tools import arc_kaggle_submission as submission
from tools.nvarc_native_multitask import canonical, digest
from tests.test_nvarc_public_eval import fixture, record
from tests.test_nvarc_phase_telemetry import Clock, SolveFixture
from tests import test_nvarc_phase_telemetry as phase_tests

ROOT = Path(__file__).resolve().parents[1]


def retain(name, value):
    directory = os.environ.get('IRIS_E01_EVIDENCE_DIR')
    if directory:
        destination = Path(directory); destination.mkdir(parents=True, exist_ok=True)
        with (destination/name).open('ab') as stream:
            stream.write(canonical(value)+b'\n')


class OutputLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='iris-e01-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan, self.data = fixture()
        self.store = public.ResultStore(self.root, self.plan, self.data, allow_fixture=True)
        self.first = record(self.plan, self.data, 'a', [[2]])
        self.store.commit(self.first)
        self.previous, self.previous_bodies = self.store.generation.read()

    def update(self):
        self.store.commit(record(self.plan, self.data, 'b', [[3]]))

    def assert_previous(self):
        manifest, bodies = self.store.generation.read()
        self.assertEqual(manifest, self.previous)
        self.assertEqual(bodies, self.previous_bodies)
        self.store.recover(); self.store.generation.verify_projection()
        self.assertEqual(self.store.records, {'a': self.first})

    def test_precommit_faults_preserve_previous_all_members_and_orphans(self):
        for stage in ('before-member', 'after-member', 'before-manifest', 'before-commit'):
            with self.subTest(stage=stage):
                def fault(current, path):
                    if current == stage: raise InterruptedError(stage)
                self.store.generation.observe = fault
                with self.assertRaises(InterruptedError): self.update()
                self.store.generation.observe = lambda *_: None
                self.assert_previous()
        self.assertGreater(len(list((self.root/'.output-generations').iterdir())), 2)

    def test_postcommit_fault_and_mixed_projection_recover_new_candidates(self):
        def fault(stage, path):
            if stage == 'after-projection' and path.name == 'candidate-pools.json':
                raise PermissionError(errno.EACCES, 'projection denied')
        self.store.generation.observe = fault
        with self.assertRaises(PermissionError): self.update()
        current, bodies = self.store.generation.read()
        self.assertNotEqual(current['generation'], self.previous['generation'])
        self.assertEqual(json.loads(bodies['candidate-pools.json'])['records']['b']['tests'][0]['ranked_grids'], [[[3]]])
        with self.assertRaisesRegex(RuntimeError, 'marker differs|mixed'): self.store.generation.verify_projection()
        self.store.generation.observe = lambda *_: None
        self.store.recover(); self.store.generation.verify_projection()
        self.assertEqual(len(self.store.records), 2)

    def test_disk_full_and_permission_before_commit_and_initial_no_storage(self):
        actual = lifecycle.write_exclusive
        for error in (OSError(errno.ENOSPC, 'disk full'), PermissionError(errno.EACCES, 'denied')):
            def fail(path, body):
                if Path(path).name == 'submission.json': raise error
                return actual(path, body)
            with self.subTest(error=error.errno), patch.object(lifecycle, 'write_exclusive', fail):
                with self.assertRaises(OSError): self.update()
            self.assert_previous()
            initial = self.root/('initial-'+str(error.errno))
            with patch.object(lifecycle, 'write_exclusive', side_effect=error):
                with self.assertRaises(OSError): public.ResultStore(initial, self.plan, self.data, allow_fixture=True)
            self.assertFalse((initial/'submission.json').exists())
            self.assertFalse((initial/'output-commit.json').exists())

    def test_read_once_marker_keeps_snapshot_during_new_publication(self):
        actual = Path.read_bytes; switched = False
        def racing(path):
            nonlocal switched
            body = actual(path)
            if path == self.root/'output-commit.json' and not switched:
                switched = True; self.update()
            return body
        with patch.object(Path, 'read_bytes', racing):
            manifest, bodies = self.store.generation.read()
        self.assertEqual(manifest, self.previous); self.assertEqual(bodies, self.previous_bodies)
        self.assertNotEqual(self.store.generation.read()[0], self.previous)

    def test_corrupt_committed_file_no_older_fallback_or_republish(self):
        directory = self.root/'.output-generations'/self.previous['generation']
        (directory/'submission-audit.json').write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError, 'hash differs'): self.store.recover()
        with self.assertRaisesRegex(RuntimeError, 'hash differs'): self.update()
        self.assertEqual(submission.load_json(self.root/'output-commit.json')['generation'], self.previous['generation'])

    def test_stale_run_source_code_reset_transcript_and_denominator_rejected(self):
        for key in self.store.generation.bindings:
            bindings = copy.deepcopy(self.store.generation.bindings); bindings[key] = 'foreign'
            with self.subTest(binding=key), self.assertRaisesRegex(RuntimeError, 'stale/foreign'):
                lifecycle.GenerationStore(self.root, 'public', bindings).read()
        for field in ('run_id', 'plan_digest', 'task_digest', 'model_material_digest'):
            bad = copy.deepcopy(self.first); bad['binding'][field] = 'stale'
            with self.subTest(record_binding=field), self.assertRaisesRegex(RuntimeError, 'foreign'):
                self.store.commit(bad)
        # Even consistently rehashed files cannot bypass semantic qualification.
        for mutation in ('views', 'truth', 'baseline', 'ordering'):
            bad = copy.deepcopy(self.first)
            if mutation == 'views': bad['tests'][0]['candidate_evidence'][digest([[2]])]['rows'].pop()
            if mutation == 'truth': bad['tests'][0]['telemetry'] = {'oracle': True}
            if mutation == 'baseline': bad['baseline_verified'] = False
            if mutation == 'ordering': bad['tests'].reverse()
            values = self.store._values(); values['candidate-pools.json']['records'] = {'a': bad}
            self.store.generation.publish(values)
            with self.subTest(mutation=mutation), self.assertRaises((RuntimeError, ValueError)): self.store.recover()
            # Restore through test-only byte publication, without weakening gates.
            self.store.generation.publish({n: json.loads(b) for n, b in self.previous_bodies.items()})
            self.store.recover()

    def test_timeout_boundaries_use_fake_clock_and_leave_committed_candidates(self):
        clock = Clock(); self.store.generation.now = clock; self.store.generation.deadline = 1
        for target in ('before-commit', 'before-projection'):
            def expire(stage, path):
                if stage == target: clock.advance(2)
            self.store.generation.observe = expire
            clock.value = 0
            with self.assertRaises(TimeoutError): self.update()
            self.store.generation.deadline = None; self.store.generation.observe = lambda *_: None
            manifest, bodies = self.store.generation.read()
            self.assertTrue(manifest['outcomes']['output_valid'])
            self.store.recover(); self.store.generation.verify_projection()
            self.store.generation.deadline = 1

    def test_exclusive_writer_and_old_generic_write_new_contract(self):
        with self.store.generation.writer():
            with self.assertRaises(FileExistsError): self.update()
        destination = self.root/'generic.json'
        submission.write_new(destination, b'old')
        with self.assertRaises(FileExistsError): submission.write_new(destination, b'new')
        self.assertEqual(destination.read_bytes(), b'old')

    def test_logger_double_failure_keeps_primary_exception_and_each_diagnostic(self):
        primary = RuntimeError('primary export exception')
        value = {'primary_error': lifecycle.diagnostic(primary, 'export'), **lifecycle.outcomes(True, 'failure', True)}
        class Broken:
            def write(self, *_): raise OSError('stderr also failed')
        def bad(): raise PermissionError('terminal disk logger failed')
        self.assertFalse(lifecycle.terminal_attempt(value, bad, stderr=Broken()))
        self.assertEqual(value['primary_error']['message'], str(primary))
        self.assertEqual([r['message'] for r in value['secondary_errors']],
                         ['terminal disk logger failed', 'stderr also failed'])
        self.assertTrue(value['output_valid']); self.assertTrue(value['evidence_qualified'])
        self.assertEqual(value['notebook_exit'], 'failure'); self.assertFalse(value['promotion'])

    def test_official_primary_exception_survives_terminal_and_root_logger_errors(self):
        primary = RuntimeError('primary source gate')
        candidate = {'run_id': 'stage4-e01-inert-001'}
        with patch.object(official, 'require', side_effect=primary), \
             patch.object(official, 'write', side_effect=OSError('logger disk full')), \
             patch.object(official, 'atomic_bytes', side_effect=PermissionError('root logger denied')), \
             patch.object(lifecycle.sys, 'stderr', io.StringIO()):
            with self.assertRaises(RuntimeError) as raised:
                official.execute(self.root, candidate, {}, time.monotonic())
        self.assertIs(raised.exception, primary)
        notes = '\n'.join(primary.__notes__)
        self.assertIn('primary source gate', notes); self.assertIn('logger disk full', notes)
        self.assertIn('root logger denied', notes)

    def test_public_primary_error_retained_when_export_and_terminal_logger_fail(self):
        self.plan['challenges_sha256'] = hashlib.sha256(canonical(self.data)).hexdigest()
        (self.root/'challenges.json').write_bytes(canonical(self.data))
        # The independent result fixture already binds its old plan; a fresh
        # execution directory is required for this changed fixture plan.
        execution = self.root/'execution'; execution.mkdir()
        (execution/'challenges.json').write_bytes(canonical(self.data))
        terminal = []
        def capture(value, action, **kw):
            result = lifecycle.terminal_attempt(value, action, stderr=io.StringIO(), **kw)
            terminal.append(copy.deepcopy(value)); return result
        with patch.object(parent, 'validate_plan', return_value={'a': 2, 'b': 1}), \
             patch.object(parent, 'ResultStore', side_effect=lambda r, p, d: public.ResultStore(r, p, d, allow_fixture=True)), \
             patch.object(parent, 'prepare', side_effect=RuntimeError('primary hardware failure')), \
             patch.object(parent, 'write', side_effect=OSError('terminal disk full')), \
             patch.object(parent, 'write_archive', side_effect=TimeoutError('archive timeout')), \
             patch.object(parent, 'print', create=True), \
             patch.object(parent, 'terminal_attempt', capture):
            result = parent.execute(execution, self.plan, self.root, time.monotonic())
        self.assertEqual(result, 1)
        self.assertEqual(terminal[-1]['errors'][0]['message'], 'primary hardware failure')
        self.assertTrue(terminal[-1]['output_valid']); self.assertFalse(terminal[-1]['evidence_qualified'])
        self.assertGreaterEqual(len(terminal[-1]['secondary_errors']), 2)

    def test_strict_gate_failure_preserves_existing_output_without_publishing(self):
        context = {'cpu_only': True}
        primary = RuntimeError('strict source/reset/transcript/hash rejected')
        (self.root/'plan.json').write_bytes(canonical(self.plan))
        (self.root/'challenges.json').write_bytes(canonical(self.data))
        with patch.object(native_export, 'build_native_submission', side_effect=primary), \
             patch.object(native_export, 'native_bindings', return_value={'run_id': self.plan['run_id']}):
            with self.assertRaises(RuntimeError) as raised:
                native_export.qualified_values(self.root, self.plan, self.data, [], None, context)
        self.assertIs(raised.exception, primary); self.assert_previous()

    def test_working_root_qualification_and_projection_are_separate(self):
        native_root = self.root/'native'; bindings = {'run_id': 'stage4-e01-native-inert-001', 'plan_digest': digest({})}
        values = {'submission.json': submission.build_submission(self.data, [])[0],
                  'submission-audit.json': submission.build_submission(self.data, [])[1],
                  'native-evidence.json': [], 'export-process.json': {'new_model_calls': 0}}
        native = lifecycle.GenerationStore(native_root, 'native', bindings)
        native.publish(values, evidence_qualified=False)
        summary = {'run_id': bindings['run_id'], 'runtime_plan_digest': bindings['plan_digest'],
                   'strict_same_runtime_export_completed': True,
                   'submission_sha256': lifecycle.sha(canonical(values['submission.json'])),
                   'audit_sha256': lifecycle.sha(canonical(values['submission-audit.json']))}
        working = self.root/'working'
        with self.assertRaisesRegex(RuntimeError, 'strict working'): official.publish_working_output(native, working, self.data, summary)
        self.assertFalse((working/'submission.json').exists())
        native.publish(values, evidence_qualified=True)  # explicit synthetic gate stub only
        committed = official.publish_working_output(native, working, self.data, summary)
        committed.verify_projection()
        (working/'official-summary.json').write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError, 'mixed'): committed.verify_projection()
        committed=official.recover_working_output(native,working,self.data,summary)
        status = committed.verify_projection()['outcomes']
        self.assertEqual(status, lifecycle.outcomes(True, 'unknown', True))

    def test_flush_revalidates_mutable_records_before_publication(self):
        self.store.records['a']['tests'][0]['telemetry'] = {'oracle': True}
        with self.assertRaisesRegex(RuntimeError, 'evaluator'): self.store.flush()
        self.assert_previous()

    def test_foreign_marker_path_rejected_before_referenced_file_is_opened(self):
        original = (self.root/'output-commit.json').read_bytes()
        marker = json.loads(original); marker['generation'] = '../outside'
        (self.root/'output-commit.json').write_bytes(canonical(marker))
        actual = Path.read_bytes; reads = []
        def tracked(path): reads.append(path); return actual(path)
        with patch.object(Path, 'read_bytes', tracked):
            with self.assertRaisesRegex(RuntimeError, 'invalid generation marker'):
                public.write_archive(self.root,self.root/'unused.zip',self.plan)
        self.assertEqual(reads, [self.root/'output-commit.json'])
        (self.root/'output-commit.json').write_bytes(original)
        self.assert_previous()

    def test_symlink_generation_base_rejected_before_any_member_write(self):
        actual = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda p: p == self.root/'.output-generations' or actual(p)):
            with self.assertRaisesRegex(RuntimeError, 'regular confined generation'):
                self.update()
        self.assert_previous()

    def test_archive_retains_committed_generation_and_rejects_mixed_projection(self):
        destination = self.root.parent/(self.plan['run_id']+'.zip')
        self.addCleanup(lambda: destination.unlink(missing_ok=True))
        public.write_archive(self.root, destination, self.plan)
        _, payloads = public.read_archive(destination)
        prefix = '.output-generations/'+self.previous['generation']+'/'
        self.assertTrue(all(prefix+n in payloads for n in self.previous_bodies))
        self.assertIn(prefix+'manifest.json', payloads)
        (self.root/'submission-audit.json').write_bytes(b'{}')
        destination.unlink()
        with self.assertRaisesRegex(RuntimeError, 'mixed'): public.write_archive(self.root, destination, self.plan)

    def test_directory_durability_observation_and_no_power_loss_claim(self):
        manifest, _ = self.store.generation.read()
        self.assertFalse(manifest['durability']['power_loss_verified'])
        self.assertEqual(manifest['durability']['member_directory_fsync_before_manifest'],
                         lifecycle.directory_sync(self.root))
        retain('durability.jsonl', {'platform': sys.platform, 'durability': manifest['durability'],
                                  'linux_os_kill_run_here': False})

    def test_actual_cpu_writer_kill_at_transaction_and_projection_boundaries(self):
        script = r'''
import json,os,sys,time
from pathlib import Path
from tools import nvarc_output_lifecycle as life,nvarc_public_eval as public
from tests.test_nvarc_public_eval import record
root=Path(sys.argv[1]);mode=sys.argv[2]
plan=json.loads((root/'fixture-plan.json').read_bytes());data=json.loads((root/'fixture-input.json').read_bytes())
store=public.ResultStore(root,plan,data,allow_fixture=True)
def barrier(stage,path):
 hit=(stage==mode or mode=='after-commit-replace' and stage=='after-replace' and path.name=='output-commit.json'
      or mode=='root-submission-replace' and stage=='after-replace' and path==root/'submission.json')
 if hit:
  (root/'kill-ready.json').write_text(json.dumps({'stage':stage,'path':str(path),'pid':os.getpid()}))
  time.sleep(20)
store.generation.observe=barrier
actual=life.write_exclusive
def partial(path,body):
 if mode=='temp-write' and Path(path).name=='submission.json':
  with Path(path).open('xb') as stream:
   stream.write(body[:max(1,len(body)//2)]);stream.flush();os.fsync(stream.fileno())
   barrier('temp-write',Path(path))
 else:actual(path,body)
life.write_exclusive=partial
store.commit(record(plan,data,'b',[[3]]))
raise AssertionError('barrier should be killed')
'''
        for mode in ('temp-write', 'after-member', 'before-commit', 'after-commit-replace',
                     'after-commit', 'root-submission-replace', 'before-projection-marker'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='iris-e01-kill-') as folder:
                root = Path(folder); store = public.ResultStore(root, self.plan, self.data, allow_fixture=True)
                store.commit(self.first); old, bodies = store.generation.read()
                (root/'fixture-plan.json').write_bytes(canonical(self.plan))
                (root/'fixture-input.json').write_bytes(canonical(self.data))
                process = subprocess.Popen([sys.executable, '-c', script, str(root), mode], cwd=ROOT,
                    env=dict(os.environ, PYTHONHASHSEED='0', PYTHONUTF8='1', PYTHONPATH=str(ROOT)),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=os.name != 'nt')
                reached = False; started = time.monotonic()
                try:
                    end = started+10
                    while time.monotonic() < end and process.poll() is None:
                        if (root/'kill-ready.json').exists():
                            reached = True; break
                        time.sleep(.02)
                    worker_pid = json.loads((root/'kill-ready.json').read_bytes())['pid'] if reached else None
                    handle = None
                    if os.name == 'nt' and worker_pid is not None:
                        import ctypes
                        from ctypes import wintypes
                        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                        kernel.OpenProcess.restype = wintypes.HANDLE
                        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
                        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                        handle = kernel.OpenProcess(0x100000 | 0x1000, False, worker_pid)
                        self.assertTrue(handle)
                        self.assertEqual(kernel.WaitForSingleObject(handle, 0), 258)
                    parent.stop_process(process); out, err = process.communicate(timeout=5)
                    worker_stopped = process.poll() is not None; worker_exit = process.returncode
                    if handle:
                        try:
                            worker_stopped = kernel.WaitForSingleObject(handle, 1000) == 0
                            code = wintypes.DWORD(); self.assertTrue(kernel.GetExitCodeProcess(handle, code))
                            worker_exit = code.value
                        finally: kernel.CloseHandle(handle)
                    receipt = {'mode': mode, 'pid': process.pid, 'returncode': process.returncode,
                        'worker_pid': worker_pid, 'worker_exit_code': worker_exit,
                        'worker_stopped_handle_verified': worker_stopped,
                        'barrier_reached': reached, 'alive_after_wait': process.poll() is None,
                        'elapsed_seconds': time.monotonic()-started, 'stdout': out.decode('utf-8', 'replace'),
                        'stderr': err.decode('utf-8', 'replace'), 'platform': sys.platform}
                    retain('process-receipts.jsonl', receipt)
                    self.assertTrue(reached, receipt); self.assertNotEqual(process.returncode, 0)
                    self.assertFalse(receipt['alive_after_wait']); self.assertTrue(worker_stopped)
                    self.assertTrue((root/'.output-writer.lock').exists())
                    # Explicit cleanup only after our exact child has been killed/waited.
                    lock = submission.load_json(root/'.output-writer.lock')
                    self.assertEqual(lock['pid'], worker_pid); (root/'.output-writer.lock').unlink()
                    manifest, current = store.generation.read()
                    after = mode in {'after-commit-replace', 'after-commit', 'root-submission-replace', 'before-projection-marker'}
                    self.assertEqual(manifest['generation'] != old['generation'], after)
                    old_directory = root/'.output-generations'/old['generation']
                    self.assertEqual({n: (old_directory/n).read_bytes() for n in bodies}, bodies)
                    if after:
                        with self.assertRaises((RuntimeError, FileNotFoundError)): store.generation.verify_projection()
                    recovered = public.ResultStore(root, self.plan, self.data, allow_fixture=True)
                    recovered.generation.verify_projection()
                    self.assertEqual(set(recovered.records), {'a', 'b'} if after else {'a'})
                finally:
                    if process.poll() is None: parent.stop_process(process); process.communicate(timeout=5)


class FiniteFaultReplayTests(unittest.TestCase):
    def replay(self, case):
        clock = Clock(); clock.advance(.1)
        plan, data = fixture()
        with tempfile.TemporaryDirectory(prefix='iris-e01-replay-') as folder:
            root = Path(folder); store = public.ResultStore(root, plan, data, allow_fixture=True)
            store.generation.now = clock
            store.commit(record(plan, data, 'a', [[2]])); before, bodies = store.generation.read()
            if case == 1:
                single = {'actual-id': data['b']}
                output, audit = submission.build_submission(single, [])
                self.assertEqual(submission.validate_submission(single, output)['test_output_count'], 1)
            elif case == 2:
                unequal = copy.deepcopy(data); unequal['a']['test'] *= 2
                output, audit = submission.build_submission(unequal, [])
                self.assertEqual([len(output[k]) for k in data], [4, 1])
                from tests import test_arc_offline_evaluation as offline_tests
                from tools import arc_offline_evaluation as evaluator
                source, truth, pools = offline_tests.fixture()
                pools['records'][0]['tests'][1]['ranked_grids'] = [[[2]]]
                metrics = evaluator.evaluate(source, truth, pools)['development_metrics']['metrics']
                self.assertEqual(metrics['pass_at_2']['value'], .6)
                self.assertEqual(metrics['task_average_pass_at_2']['value'], .75)
                self.assertEqual(metrics['tasks_all_tests_pass_at_2']['value'], .5)
            elif case == 3:
                changed = copy.deepcopy(data); changed['a']['test'].reverse()
                with self.assertRaises(RuntimeError): public.validate_record(plan, changed, record(plan, data, 'a', [[2]]))
            elif case == 4:
                first = submission.build_submission(data, [{'task_id': k, 'tests': []} for k in data])
                second = submission.build_submission(dict(reversed(list(data.items()))), [{'task_id': k, 'tests': []} for k in reversed(data)])
                self.assertEqual(first[0], second[0])
            elif case == 5:
                for records in ([{'task_id': 'foreign', 'tests': []}], [{'task_id': 'a', 'tests': [
                    {'test_index': 0, 'attempts': []}, {'test_index': 0, 'attempts': []}]}]):
                    with self.assertRaises(ValueError): submission.build_submission(data, records)
            elif case == 6:
                for body in ('{"a":1,"a":2}', '{"x":NaN}'):
                    with self.assertRaises(ValueError): submission.parse_json(body)
                with self.assertRaises(ValueError): submission.grid([[True]])
            elif case == 7:
                for value in ([], [[]], [[1], [1, 2]], [[-1]], [[10]], [[0]*31], [[0]]*31):
                    with self.assertRaises(ValueError): submission.grid(value)
            elif case == 8:
                bad = record(plan, data, 'a', [[2]]); bad['tests'][0]['telemetry'] = {'oracle': True}
                with self.assertRaises(RuntimeError): store.commit(bad)
                bad_data = copy.deepcopy(data); bad_data['a']['test'][0]['output'] = [[2]]
                with self.assertRaises(ValueError): submission.challenge_counts(bad_data)
            elif case == 9:
                _, values = store.generation.read(); audit = json.loads(values['submission-audit.json'])
                self.assertEqual([r['fill_policy'] for r in audit['rows']],
                                 ['duplicate_first', 'constant_zero_1x1', 'constant_zero_1x1'])
                self.assertEqual(audit['model_supplied_attempts'], 1)
            elif case == 10:
                for field in ('model_material_digest', 'store_code_sha256', 'source_inventory_digest'):
                    binding = dict(store.generation.bindings); binding[field] = 'foreign'
                    with self.assertRaises(RuntimeError): lifecycle.GenerationStore(root, 'public', binding).read()
            elif case == 11:
                try: raise ModuleNotFoundError('offline fixture dependency absent')
                except ModuleNotFoundError as error:
                    self.assertIn('ModuleNotFoundError', lifecycle.diagnostic(error, 'dependency')['traceback'])
            elif case == 12:
                with self.assertRaises(RuntimeError): adapter.allocate({'a': {'child_seconds': 500}}, 100)
            elif case == 13:
                state = SimpleNamespace(generation_deadline=0); saves = []
                def solve(index):
                    clock.advance(1)
                    if index == 0: raise TimeoutError('ordinary timeout')
                    return {'test_index': index, 'attempts': [[[2]]], 'missing_attempts': 1}
                tests, failures = adapter.run_all_tests(data, 'a', solve, saves.append, state, 100, 30, now=clock)
                self.assertEqual(len(tests), 2); self.assertEqual(tests[1]['attempts'], [[[2]]])
            elif case in (14, 15):
                phase_tests.PhaseTelemetryTests('test_deadline_before_reservation_and_inflight_overrun_do_not_add_calls').test_deadline_before_reservation_and_inflight_overrun_do_not_add_calls()
            elif case == 16:
                solved = SolveFixture(partial=True).run(True)
                self.assertEqual(solved['ranked_grids'], [[[1]]])
                self.assertEqual(solved['telemetry']['verifications'][-1]['completed_views'], 4)
            elif case == 17:
                failed = copy.deepcopy(store.records['a']); failed['outcome'] = 'failed'
                failed['tests'][1]['termination_reason'] = 'worker_crash'; store.commit(failed)
                self.assertEqual(store.records['a']['tests'][0]['ranked_grids'], [[[2]]])
            elif case == 18:
                bad = record(plan, data, 'b', [[2]]); bad['baseline_verified'] = False
                with self.assertRaises(RuntimeError): store.commit(bad)
                self.assertNotIn('b', store.records)
            elif case == 19:
                coverage = json.loads(bodies['coverage.json'])
                self.assertEqual((coverage['tasks'], coverage['tests'], coverage['tests_not_executed']), (2, 3, 2))
            elif case in (20, 21, 23):
                target = {20: 'after-member', 21: 'before-manifest', 23: 'after-commit'}[case]
                def fault(stage, path):
                    clock.advance(.01)
                    if stage == target: raise TimeoutError(target)
                store.generation.observe = fault
                with self.assertRaises(TimeoutError): store.commit(record(plan, data, 'b', [[3]]))
                store.generation.observe = lambda *_: None; store.recover()
                self.assertEqual(set(store.records), {'a', 'b'} if case == 23 else {'a'})
                store.generation.verify_projection()
            elif case == 22:
                with patch.object(lifecycle, 'write_exclusive', side_effect=OSError(errno.ENOSPC, 'full')):
                    with self.assertRaises(OSError): store.commit(record(plan, data, 'b', [[3]]))
                store.recover(); self.assertEqual(set(store.records), {'a'})
            elif case == 24:
                primary = RuntimeError('primary'); value = {'primary_error': lifecycle.diagnostic(primary, 'export')}
                def fail(): raise PermissionError('logger')
                lifecycle.terminal_attempt(value, fail, stderr=io.StringIO())
                self.assertEqual(value['primary_error']['message'], 'primary')
                foreign = dict(store.generation.bindings, run_id='old-run')
                with self.assertRaises(RuntimeError): lifecycle.GenerationStore(root, 'public', foreign).read()
            self.assertEqual(submission.validate_submission(data, submission.load_json(root/'submission.json')),
                             {'task_count': 2, 'test_output_count': 3})
            return {'case': 'F'+str(case).zfill(2), 'result': 'PASS', 'fake_wall_seconds': clock(),
                    'neural_model_calls': 0, 'promotion': False}

    def test_F01_through_F24_each_replay_twice(self):
        observations = []
        for case in range(1, 25):
            for replay in (1, 2):
                with self.subTest(case=case, replay=replay):
                    observations.append(dict(self.replay(case), replay=replay))
        self.assertEqual(len(observations), 48)
        for case in range(24):
            a, b = observations[case*2:case*2+2]
            self.assertEqual({k: v for k, v in a.items() if k != 'replay'}, {k: v for k, v in b.items() if k != 'replay'})
        retain('fake-clock-replays.jsonl', {'cases': observations})


class StrictExportRecoveryTests(unittest.TestCase):
    def test_real_tiny_source_replay_recovers_projection_but_changed_code_blocks_recovery(self):
        # Reuse the existing authorized tiny CPU fixture, not published weights.
        # Only the fixture provenance reader is injected. Native DFS/token/rank
        # and source byte checks still run; this cannot qualify a real GPU run.
        from tests import test_nvarc_native_multitask as native_tests
        from tools import stage_nvarc_native_multitask as stage
        from tools import nvarc_native_submission as bridge
        import shutil
        Fixture = native_tests.MultiTaskTests
        Fixture.setUpClass()
        try:
            Fixture.plan['approved'] = True
            evidence, _ = Fixture.produce()
            with tempfile.TemporaryDirectory(prefix='iris-e01-strict-') as folder:
                root = Path(folder)
                for name in stage.files_for(Fixture.raw):
                    target = root/name; target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(Fixture.directory/name, target)
                for name, value in {'plan.json': Fixture.plan, 'challenges.json': Fixture.challenges,
                    'worker-receipts.json': [r['receipt'] for r in evidence]}.items():
                    (root/name).write_bytes(canonical(value))
                original_builder = bridge.build_native_submission
                def build(*args): return original_builder(*args, allow_fixture=True)
                tokenizer = stage.MODEL/'model/tokenizer.json'
                with patch.object(native_export, 'read_task_evidence', return_value=evidence), \
                     patch.object(native_export, 'build_native_submission', build):
                    native_export.export(root, tokenizer)
                    binding = native_export.native_bindings(root, Fixture.plan, Fixture.challenges, evidence)
                    committed = lifecycle.GenerationStore(root, 'native', binding)
                    before, bodies = committed.read()
                    (root/'submission.json').write_bytes(b'{')
                    native_export.export(root, tokenizer)
                    self.assertEqual(committed.verify_projection(), before)
                    self.assertEqual(committed.read()[1], bodies)
                    reset = root/'tasks/a/native/reset-inventory.json'
                    reset.parent.mkdir(parents=True, exist_ok=True)
                    reset.write_bytes(b'[]')
                    with self.assertRaisesRegex(RuntimeError, 'stale/foreign'):
                        native_export.export(root, tokenizer)
                    reset.unlink()  # test-created observation, never an owner artifact
                    self.assertEqual(committed.read()[1], bodies)
                    def changing_builder(*args):
                        value=build(*args); reset.write_bytes(b'[]'); return value
                    with patch.object(native_export,'build_native_submission',changing_builder):
                        with self.assertRaisesRegex(RuntimeError,'inputs changed during strict replay'):
                            native_export.export(root,tokenizer)
                    reset.unlink()
                    self.assertEqual(committed.read()[1], bodies)
                    (root/'tools/nvarc_native_submission.py').write_bytes(b'# foreign source\n')
                    with self.assertRaisesRegex(RuntimeError, 'producer program bytes'):
                        native_export.export(root, tokenizer)
                    self.assertEqual(committed.read()[1], bodies)
                    self.assertFalse(before['outcomes']['promotion'])
        finally: Fixture.tearDownClass()


if __name__ == '__main__': unittest.main()

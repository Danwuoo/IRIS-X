"""CPU-only transport counterexamples; no model/runtime modules are imported."""
import ast
import copy
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from tools import nvarc_e11_delivery_envelope as delivery


class DeliveryEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = 'future-e11-fixture'
        self.plan = dict(run_id=self.run, screen_id=self.run, maximum_notebook_wall_seconds=2700,
                         task_order=['task0'], model_material_digest='sha256:fixture')
        self.plan_raw = delivery.canonical(self.plan)
        self.sha = hashlib.sha256(self.plan_raw).hexdigest()
        self.observation = dict(confirmed_stopped=True, launched=True, returncode=0,
            hard_deadline_monotonic=2800., output_capture={'written': True}, e11_supervision=dict(
                format='irisx/e11-supervision-v1', started_monotonic=100., term_deadline_monotonic=2490.,
                kill_deadline_monotonic=2499.8, stop_deadline_monotonic=2500., finalizer_deadline_monotonic=2800.,
                coordinator_stopped_monotonic=1400., capture_finished_monotonic=1450., finished_monotonic=1500.,
                coordinator_group_absent=True, errors=[]))
        self.launch = dict(format='irisx/e11-owned-worker-launch-v1', pid=234, process_group_id=234,
            started_monotonic=200., start_new_session=True, binding=dict(probe_id=self.run,
            plan_digest='sha256:' + self.sha, rank=0, task_id='task0', model_material_digest='sha256:fixture'))
        self.terminal = dict(plan_digest='sha256:' + self.sha, outcome='complete', cleanup=dict(
            format='irisx/e11-collective-cleanup-v1', deadline_monotonic=2499.8, all_producers_stopped=True,
            complete_before_deadline=True, timed_out=False, secondary_errors=[], started_monotonic=1300.,
            finished_monotonic=1350., workers=[dict(identity='0', pid=234, stop_attempted=True,
            group_absent=True, stop_confirmed=True, returncode=0, kill_requested_monotonic=1301.,
            stop_confirmed_monotonic=1302.)]))
        self.proof = dict(format=delivery.STOP_FORMAT, run_id=self.run, plan_sha256=self.sha,
            observation=self.observation, terminal=self.terminal, launches={'0': self.launch})
        self.files = {'screen.json': self.plan_raw, 'plan.json': self.plan_raw,
            'outer-supervision.json': delivery.canonical(self.observation),
            'terminal.json': delivery.canonical(self.terminal),
            'workers/0/process-launch.json': delivery.canonical(self.launch),
            'tools/returned-code.py': b'raise AssertionError("returned code must never execute")\n'}
        self.write_runtime()
        self.clock = patch.object(delivery.time, 'monotonic', return_value=1700.)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.tmp.cleanup()

    def write_runtime(self):
        self.archive_path = self.root / (self.run + '.zip')
        with zipfile.ZipFile(self.archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in self.files.items():
                archive.writestr(name, raw)
        self.original = self.archive_path.read_bytes()
        self.receipt = dict(format='irisx/e11-finalization-timing-v1', plan_sha256=self.sha,
            stages={name: dict(monotonic=1510. + index, remaining_seconds=1290. - index)
                    for index, name in enumerate(delivery.STAGES)}, hard_deadline_monotonic=2800.,
            finalization_qualified=True, receipt_written=True, receipt_write_finished_monotonic=1520.,
            correctness_scored=False, promotion=False, archive_exists=True, archive_size=len(self.original),
            archive_sha256=hashlib.sha256(self.original).hexdigest())
        self.sidecar = dict(self.receipt, finalization_qualified=False, receipt_written=False)
        self.sidecar.pop('receipt_write_finished_monotonic')
        self.result = dict(final_archive_created=True, diagnostic_only_archive_created=False,
            existing_archive_preserved=False, finalization_qualified=True, diagnostic_errors=[],
            coordinator_diagnostic_excerpt='', supervision_observation_retained=True, finalization_timing=self.receipt)

    def build(self, *, sidecar=False, result=False, **changes):
        args = dict(run_id=self.run, plan_sha256=self.sha, stop_evidence=delivery.canonical(self.proof))
        if sidecar:
            args['sidecar'] = delivery.canonical(self.sidecar) if sidecar is True else sidecar
        if result:
            args['finalizer_result'] = delivery.canonical(self.result) if result is True else result
        args.update(changes)
        return delivery.create_envelope(self.root, **args)

    def verify(self):
        return delivery.verify_envelope(self.root, run_id=self.run, plan_sha256=self.sha)

    def test_full_post_write_result_is_bound_and_original_bytes_unchanged(self):
        result = self.build(sidecar=True, result=True)
        manifest = self.verify()
        self.assertEqual(manifest, result['manifest'])
        self.assertEqual(manifest['completion']['evidence_kind'], 'post_write_result')
        self.assertTrue(manifest['completion']['observed_finalization_qualified'])
        self.assertEqual(manifest['completion']['runtime_qualification'], 'not_assessed')
        self.assertFalse(manifest['completion']['promotion'])
        path = Path(result['path'])
        with zipfile.ZipFile(path) as envelope:
            self.assertEqual(envelope.read('runtime.zip'), self.original)
            self.assertEqual(envelope.read('sidecar.json'), delivery.canonical(self.sidecar))
            self.assertEqual(envelope.read('finalizer-result.json'), delivery.canonical(self.result))
            self.assertIsNone(envelope.testzip())
        self.assertEqual(self.archive_path.read_bytes(), self.original)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), result['sha256'])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o400)

    def test_sidecar_only_never_reconstructed_as_after_write_success(self):
        result = self.build(sidecar=True)
        observed = result['manifest']['completion']
        self.assertEqual(observed['evidence_kind'], 'sidecar_only')
        self.assertEqual(observed['archive_binding'], 'verified')
        self.assertIsNone(observed['observed_finalization_qualified'])
        self.assertEqual(self.verify()['completion'], observed)

    def test_missing_evidence_remains_unknown(self):
        observed = self.build()['manifest']['completion']
        self.assertEqual(observed['evidence_kind'], 'unknown')
        self.assertIsNone(observed['observed_finalization_qualified'])

    def test_failed_and_incomplete_results_retained_without_promotion(self):
        self.receipt.update(finalization_qualified=False, receipt_written=False, archive_sha256=None, stages={})
        self.receipt.pop('receipt_write_finished_monotonic')
        self.result.update(finalization_qualified=False, final_archive_created=False,
                           diagnostic_errors=['literal hash deadline failure'])
        result = self.build(result=True)
        self.assertEqual(result['manifest']['completion']['evidence_kind'], 'incomplete_result')
        self.assertEqual(result['manifest']['completion']['archive_binding'], 'unknown')
        self.assertFalse(result['manifest']['completion']['observed_finalization_qualified'])

    def test_diagnostic_fallback_keeps_stopped_workers_without_full_runtime_files(self):
        self.files.pop('workers/0/process-launch.json')
        self.files['diagnostic-only.json'] = delivery.canonical(dict(format='irisx/ttt-probe-diagnostic-only-v1',
            complete_runtime_evidence=False, promotion=False, errors=['literal export failure']))
        self.write_runtime()
        self.result.update(final_archive_created=False, diagnostic_only_archive_created=True, finalization_qualified=False,
                           diagnostic_errors=['literal export failure'])
        self.receipt['finalization_qualified'] = False
        self.assertFalse(self.build(result=True)['manifest']['completion']['observed_finalization_qualified'])

    def test_diagnostic_archive_cannot_claim_success_even_with_rehashed_receipt(self):
        self.files['diagnostic-only.json'] = delivery.canonical(dict(format='irisx/ttt-probe-diagnostic-only-v1',
            complete_runtime_evidence=False, promotion=False))
        self.write_runtime()
        with self.assertRaisesRegex(ValueError, 'full finalizer'):
            self.build(result=True)

    def test_diagnostic_omitted_launch_still_requires_exact_task_model_binding(self):
        self.files.pop('workers/0/process-launch.json')
        self.files['diagnostic-only.json'] = delivery.canonical(dict(format='irisx/ttt-probe-diagnostic-only-v1',
            complete_runtime_evidence=False, promotion=False))
        self.write_runtime()
        for key in ('task_id', 'model_material_digest'):
            proof = copy.deepcopy(self.proof)
            proof['launches']['0']['binding'][key] = 'different'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'launch plan binding'):
                self.build(stop_evidence=delivery.canonical(proof))

    def test_proven_prelaunch_failure_is_retained_as_diagnostic(self):
        self.observation.update(launched=False, launch_failed=True, returncode=None)
        self.observation['e11_supervision'].update(coordinator_stopped_monotonic=None,
                                                   errors=[{'phase': 'launch', 'message': 'literal failure'}])
        self.proof.update(terminal=None, launches={})
        self.files = {'screen.json': self.plan_raw, 'outer-supervision.json': delivery.canonical(self.observation),
            'bootstrap-failure.json': b'{"message":"literal launch failure"}',
            'diagnostic-only.json': delivery.canonical(dict(format='irisx/ttt-probe-diagnostic-only-v1',
                                                           complete_runtime_evidence=False, promotion=False))}
        self.write_runtime()
        self.result.update(final_archive_created=False, diagnostic_only_archive_created=True, finalization_qualified=False)
        self.receipt['finalization_qualified'] = False
        self.assertEqual(self.build(result=True)['manifest']['completion']['runtime_qualification'], 'diagnostic_only')

    def test_no_source_or_directory_open_before_producer_stop_validation(self):
        for mutate in ('outer', 'worker', 'cleanup', 'missing', 'run', 'plan', 'terminal_plan', 'launch_run'):
            proof = copy.deepcopy(self.proof)
            if mutate == 'outer': proof['observation']['confirmed_stopped'] = False
            if mutate == 'worker': proof['terminal']['cleanup']['workers'][0]['group_absent'] = False
            if mutate == 'cleanup': proof['terminal']['cleanup']['timed_out'] = True
            if mutate == 'missing': proof['launches'] = {}
            if mutate == 'run': proof['run_id'] = 'different'
            if mutate == 'plan': proof['plan_sha256'] = '0' * 64
            if mutate == 'terminal_plan': proof['terminal']['plan_digest'] = 'sha256:' + '0' * 64
            if mutate == 'launch_run': proof['launches']['0']['binding']['probe_id'] = 'different'
            with self.subTest(mutate=mutate), patch.object(delivery.os, 'open', side_effect=AssertionError('no I/O')):
                with self.assertRaises(ValueError):
                    self.build(stop_evidence=delivery.canonical(proof))

    def test_wrong_archive_run_or_plan_rejected(self):
        self.files['screen.json'] = delivery.canonical(dict(self.plan, run_id='different'))
        self.write_runtime()
        with self.assertRaisesRegex(ValueError, 'exact run/plan'):
            self.build()
        self.assertFalse((self.root / (self.run + '-delivery.zip')).exists())

    def test_receipt_wrong_plan_archive_size_and_hash_rejected(self):
        for key, value in (('plan_sha256', '0' * 64), ('archive_sha256', '0' * 64), ('archive_size', 1)):
            sidecar = dict(self.sidecar); sidecar[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'binding'):
                self.build(sidecar=delivery.canonical(sidecar))

    def test_duplicate_json_keys_rejected_before_open(self):
        raw = delivery.canonical(self.proof).replace(b'"run_id":', b'"run_id":"duplicate","run_id":', 1)
        with patch.object(delivery.os, 'open', side_effect=AssertionError('no I/O')):
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                self.build(stop_evidence=raw)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            delivery.parse(b'{"nested":{"a":1,"a":2}}')

    def test_nonfinite_and_wrong_boolean_types_rejected(self):
        for raw in (b'{"x":NaN}', b'{"x":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                delivery.parse(raw)
        self.proof['observation']['confirmed_stopped'] = 1
        with self.assertRaises(ValueError): self.build()

    def test_after_close_stage_order_and_hard_deadline_cannot_be_fabricated(self):
        for mutate in ('missing', 'reverse', 'late', 'written', 'sidecar'):
            saved = copy.deepcopy(self.result)
            if mutate == 'missing': self.receipt['stages'].pop('archive_closed')
            if mutate == 'reverse': self.receipt['receipt_write_finished_monotonic'] = 1510.
            if mutate == 'late': self.receipt['receipt_write_finished_monotonic'] = 2800.
            if mutate == 'written': self.receipt['receipt_written'] = False
            if mutate == 'sidecar': self.sidecar['finalization_qualified'] = True
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.build(sidecar=mutate == 'sidecar', result=True)
            self.result = saved; self.receipt = self.result['finalization_timing']

    def test_conflicting_sidecar_rejected(self):
        self.sidecar['stages'] = {}
        with self.assertRaisesRegex(ValueError, 'disagree'):
            self.build(sidecar=True, result=True)

    def test_creation_rejects_future_receipt_observations_but_offline_verification_does_not_replay_clock(self):
        self.receipt['receipt_write_finished_monotonic'] = 1750.
        with self.assertRaisesRegex(ValueError, 'future'):
            self.build(result=True)
        self.receipt['receipt_write_finished_monotonic'] = 1520.
        self.sidecar['stages'] = copy.deepcopy(self.sidecar['stages'])
        self.sidecar['stages']['finalizer_returned'] = dict(monotonic=1750., remaining_seconds=1050.)
        with self.assertRaisesRegex(ValueError, 'stage timing'):
            self.build(sidecar=True)
        self.build(result=True)
        with patch.object(delivery.time, 'monotonic', return_value=10.):
            self.assertTrue(self.verify()['completion']['observed_finalization_qualified'])

    def test_input_symlink_parent_symlink_and_fifo_rejected(self):
        moved = self.root / 'real.zip'; self.archive_path.rename(moved)
        self.archive_path.symlink_to(moved)
        with self.assertRaises(OSError): self.build()
        self.archive_path.unlink(); self.archive_path.write_bytes(self.original)
        alias = self.root / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            delivery.create_envelope(alias, run_id=self.run, plan_sha256=self.sha,
                                     stop_evidence=delivery.canonical(self.proof))
        self.archive_path.unlink(); os.mkfifo(self.archive_path)
        with self.assertRaisesRegex(ValueError, 'regular'): self.build()

    def test_existing_delivery_and_symlink_destination_are_preserved(self):
        result = self.build(); path = Path(result['path']); original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'): self.build()
        self.assertEqual(path.read_bytes(), original)
        path.unlink(); path.symlink_to(self.archive_path)
        with self.assertRaisesRegex(ValueError, 'already exists'): self.build()
        self.assertEqual(self.archive_path.read_bytes(), self.original)

    def test_duplicate_traversal_and_symlink_archive_members_rejected(self):
        for invalid in ('../escape', '/absolute', 'a\\b', 'screen.json', 'SCREEN.JSON', 'symlink'):
            self.write_runtime()
            with warnings.catch_warnings(), zipfile.ZipFile(self.archive_path, 'a') as archive:
                warnings.simplefilter('ignore', UserWarning)
                if invalid == 'symlink':
                    info = zipfile.ZipInfo(invalid); info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, 'outside')
                else:
                    archive.writestr(invalid, b'bad')
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'unsafe'):
                self.build()

    def test_archive_file_directory_prefix_collisions_rejected(self):
        for name in ('workers', 'WORKERS/0', 'screen.json/nested'):
            self.write_runtime()
            with zipfile.ZipFile(self.archive_path, 'a') as archive:
                archive.writestr(name, b'collision')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'prefix collision'):
                self.build()

    def test_archived_receipts_cannot_replace_boolean_with_equal_integer(self):
        for name, value, field in (
                ('outer-supervision.json', self.observation, 'confirmed_stopped'),
                ('terminal.json', self.terminal, None),
                ('workers/0/process-launch.json', self.launch, 'start_new_session')):
            original = self.files[name]
            mutated = copy.deepcopy(value)
            if field is None:
                mutated['cleanup']['all_producers_stopped'] = 1
            else:
                mutated[field] = 1
            self.files[name] = delivery.canonical(mutated)
            self.write_runtime()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'differs'):
                self.build(result=True)
            self.files[name] = original

    def test_corrupted_runtime_crc_rejected(self):
        # ZIP_STORED makes the corruption independent of deflate behavior.
        with zipfile.ZipFile(self.archive_path, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, raw in self.files.items(): archive.writestr(name, raw)
        raw = self.archive_path.read_bytes()
        self.archive_path.write_bytes(raw.replace(b'returned code must never execute', b'Returned code must never execute'))
        with self.assertRaises(zipfile.BadZipFile): self.build()

    def test_size_member_metadata_and_time_bounds_fail_closed(self):
        with patch.object(delivery, 'MAX_ARCHIVE_BYTES', 10):
            with self.assertRaisesRegex(ValueError, 'bounded regular'): self.build()
        with patch.object(delivery, 'MAX_MEMBERS', 2):
            with self.assertRaisesRegex(ValueError, 'directory'): self.build()
        with patch.object(delivery, 'MAX_EXPANDED_BYTES', 100):
            with self.assertRaisesRegex(ValueError, 'expanded'): self.build()
        with patch.object(delivery.time, 'monotonic', return_value=2800.), \
             patch.object(delivery.os, 'open', side_effect=AssertionError('no I/O')):
            with self.assertRaisesRegex(ValueError, 'time budget'): self.build()
        with patch.object(delivery.time, 'monotonic', return_value=1400.), \
             patch.object(delivery.os, 'open', side_effect=AssertionError('no I/O')):
            with self.assertRaisesRegex(ValueError, 'already have been observed'): self.build()

    def test_deadline_expires_mid_copy_leaves_no_partial_delivery(self):
        actual = delivery.stream_digest
        def consume(stream, deadline, limit, target=None):
            if target is not None:
                with patch.object(delivery.time, 'monotonic', return_value=2800.):
                    return actual(stream, deadline, limit, target)
            return actual(stream, deadline, limit, target)
        with patch.object(delivery, 'stream_digest', side_effect=consume):
            with self.assertRaisesRegex(ValueError, 'time budget'): self.build()
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [self.run + '.zip'])

    def test_destination_race_cannot_overwrite_existing_bytes(self):
        original_link = delivery.os.link
        path = self.root / (self.run + '-delivery.zip')
        def racing_link(*args, **kwargs):
            path.write_bytes(b'existing competitor delivery')
            return original_link(*args, **kwargs)
        with patch.object(delivery.os, 'link', side_effect=racing_link):
            with self.assertRaises(FileExistsError): self.build()
        self.assertEqual(path.read_bytes(), b'existing competitor delivery')
        self.assertFalse(list(self.root.glob('.*.tmp')))

    def test_publication_uses_verified_anonymous_inode_without_substitutable_temp_path(self):
        original_link = delivery.os.link
        def checked_link(source, destination, **kwargs):
            self.assertTrue(source.startswith('/proc/self/fd/'))
            self.assertEqual(os.stat(source).st_nlink, 0)
            self.assertEqual(sorted(path.name for path in self.root.iterdir()), [self.run + '.zip'])
            with zipfile.ZipFile(source) as checked:
                self.assertEqual(checked.read('runtime.zip'), self.original)
            return original_link(source, destination, **kwargs)
        with patch.object(delivery.os, 'link', side_effect=checked_link):
            self.build(result=True)
        self.assertTrue(self.verify()['completion']['observed_finalization_qualified'])

    def test_slow_publication_cannot_return_in_budget_success_or_overwrite(self):
        original_fsync = delivery.os.fsync
        def slow_directory_sync(fd):
            original_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                delivery.time.monotonic.return_value = 2800.
        with patch.object(delivery.os, 'fsync', side_effect=slow_directory_sync):
            with self.assertRaisesRegex(ValueError, 'time budget'): self.build()
        path = self.root / (self.run + '-delivery.zip')
        self.assertTrue(path.is_file())
        self.assertEqual(self.verify()['completion']['evidence_kind'], 'unknown')
        self.assertFalse(list(self.root.glob('.*.tmp')))

    def test_source_mutation_during_copy_rejected(self):
        actual = delivery.stream_digest
        def mutate(stream, deadline, limit, target=None):
            if target is not None:
                with self.archive_path.open('ab') as handle: handle.write(b'changed')
            return actual(stream, deadline, limit, target)
        with patch.object(delivery, 'stream_digest', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed'): self.build()
        self.assertFalse((self.root / (self.run + '-delivery.zip')).exists())

    def rewrite_envelope(self, changes):
        path = self.root / (self.run + '-delivery.zip')
        with zipfile.ZipFile(path) as archive:
            bodies = {name: archive.read(name) for name in archive.namelist()}
        changes(bodies)
        path.chmod(0o600)
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, body in bodies.items(): archive.writestr(name, body)

    def test_envelope_payload_tampering_and_rehashed_status_promotion_rejected(self):
        self.build(sidecar=True)
        self.rewrite_envelope(lambda data: data.update({'runtime.zip': data['runtime.zip'] + b'tamper'}))
        with self.assertRaisesRegex(ValueError, 'hash/size'): self.verify()
        (self.root / (self.run + '-delivery.zip')).unlink()
        self.build(sidecar=True)
        def promote(data):
            manifest = delivery.parse(data['manifest.json'])
            manifest['completion']['observed_finalization_qualified'] = True
            data['manifest.json'] = delivery.canonical(manifest)
        self.rewrite_envelope(promote)
        with self.assertRaisesRegex(ValueError, 'cannot promote'): self.verify()

    def test_cli_is_inert_before_imports_and_source_only_imports_stdlib(self):
        tree = ast.parse(Path(delivery.__file__).read_text())
        with patch('builtins.__import__', side_effect=AssertionError('no imports')):
            with self.assertRaisesRegex(RuntimeError, 'INERT'):
                exec(compile(tree, 'delivery-cold', 'exec'), {'__name__': '__main__'})
        modules = [node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
                   for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertTrue(all(name.split('.')[0] in {'hashlib', 'json', 'math', 'os', 'pathlib', 're',
            'stat', 'struct', 'time', 'zipfile'} for name in modules))


if __name__ == '__main__':
    unittest.main()

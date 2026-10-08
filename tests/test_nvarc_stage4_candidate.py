from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import stage_nvarc_stage4_candidate as builder
from tools import nvarc_stage4_parent as parent
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical
from tools.nvarc_output_lifecycle import GenerationStore
from tools.rehearse_stage4_output_resources import run as resource_run


def challenges():
    return {'changed-a': {'train': [{'input': [[1]], 'output': [[2]]}],
        'test': [{'input': [[3]]}, {'input': [[4]]}]},
        'new-b': {'train': [{'input': [[2]], 'output': [[1]]}], 'test': [{'input': [[5]]}]}}


def materials(data):
    return {key: {'rows': [{'input_tokens': 128, 'supervised_tokens': 32} for _ in range(128)],
                  'texts': [{'text': 'public demonstration'} for _ in range(128)]} for key in data}


def candidate():
    return {'run_id': 'stage4-full-input-test', 'model_material_digest': 'fake-model', 'producer_sha256': 'fake-producer', 'native_source_learning_rates': [0.0]*129,
        **builder.POLICY, 'maximum_notebook_wall_seconds': 1000, 'initial_preparation_seconds': 500,
        'packaging_reserve_seconds': 200, 'scheduler_reserve_seconds': 100, 'minimum_free_working_bytes': 1024**2}


class FakeClock:
    def __init__(self): self.value = 0
    def __call__(self): return self.value
    def advance(self, value): self.value += value


class PostPreparationAdmissionTests(unittest.TestCase):
    def test_clock_after_materials_and_dependency_preparation(self):
        clock = FakeClock(); calls = []
        def material(): calls.append('material'); clock.advance(100); return materials(challenges())
        def dependency(): calls.append('dependency'); clock.advance(100); return 'prepared'
        plan, _, prepared = parent.prepare_plan(candidate(), challenges(), material, dependency, 0, now=clock)
        self.assertEqual(calls, ['dependency', 'material']); self.assertEqual(prepared, 'prepared')
        self.assertEqual(plan['allocation']['available_seconds'], 500)
        self.assertEqual(plan['allocation']['observation']['elapsed_seconds'], 200)
        self.assertEqual(plan['runtime_input']['tests'], 3); self.assertEqual(plan['runtime_input']['tasks'], 2)
        self.assertEqual(plan['maximum_optimizer_steps'], 256)
        self.assertEqual(set(sum(plan['allocation']['queues'], [])), set(challenges()))
        self.assertEqual(plan['task_specs']['changed-a']['per_test_seconds'], 30)

    def test_stale_preparation_budget_would_fit_but_fresh_budget_rejects(self):
        clock = FakeClock()
        def material(): clock.advance(250); return materials(challenges())
        def dependency(): clock.advance(150)
        with self.assertRaisesRegex(RuntimeError, 'do not fit'):
            parent.prepare_plan(candidate(), challenges(), material, dependency, 0, now=clock)

    def test_preparation_cap_rejects_after_dependency_not_before(self):
        clock = FakeClock(); c = candidate(); c['initial_preparation_seconds'] = 150
        def material(): clock.advance(100); return materials(challenges())
        def dependency(): clock.advance(100)
        with self.assertRaisesRegex(RuntimeError, 'preparation exceeds'):
            parent.prepare_plan(c, challenges(), material, dependency, 0, now=clock)

    def test_truth_rejected_before_either_preparation_callback(self):
        data = challenges(); data['changed-a']['test'][0]['output'] = [[9]]
        with patch('builtins.print') as unused, patch.object(parent, 'full_input_plan') as plan:
            with self.assertRaises(ValueError): parent.prepare_plan(candidate(), data, unused, unused, 0)
            unused.assert_not_called(); plan.assert_not_called()

    def test_changed_count_order_and_ids_preserve_every_test(self):
        data = challenges(); data = {'new-z': data['new-b'], 'new-y': data['changed-a'], 'new-x': data['new-b']}
        plan = parent.full_input_plan(candidate(), data, materials(data), 0, now=lambda: 0)
        self.assertEqual(plan['task_order'], sorted(data)); self.assertEqual(plan['runtime_input']['tests'], 4)
        self.assertEqual(plan['maximum_training_forwards'], 384)
        self.assertEqual(set(sum(plan['allocation']['queues'], [])), set(data))

    def test_dispatch_rechecks_clock_before_any_worker_or_caller_identity(self):
        c = candidate(); plan = parent.full_input_plan(c, challenges(), materials(challenges()), 0, now=lambda: 0)
        with tempfile.TemporaryDirectory() as directory, patch('tools.nvarc_allocation_transport.CallerAdmissions') as caller:
            launch = unittest.mock.Mock()
            with self.assertRaisesRegex(RuntimeError, 'do not fit'):
                parent.run_full_input(Path(directory), plan, challenges(), materials(challenges()), None, None, [], 0,
                    now=lambda: 400, launch=launch)
            launch.assert_not_called(); caller.assert_not_called()
            self.assertFalse((Path(directory)/'plan.json').exists())


class FullInputProcessBoundaryTests(unittest.TestCase):
    def test_complete_fake_processes_keep_actual_denominator_and_frozen_receipt(self):
        class Done:
            pid = 12345
            returncode = 0
            def poll(self): return 0
        with tempfile.TemporaryDirectory() as directory:
            c = candidate(); data = challenges(); m = materials(data)
            plan = parent.full_input_plan(c, data, m, 0, now=lambda: 0)
            def launch(*_, **kwargs):
                self.assertEqual(len(kwargs['pass_fds']), 1)
                self.assertEqual(kwargs['env']['IRIS_NATIVE_PARENT_PID'], str(__import__('os').getpid()))
                return Done()
            receipts, receipt_sha, cleanup = parent.run_full_input(Path(directory), plan, data, m, 'model', 'deps',
                [{'uuid': 'gpu-'+str(i)} for i in range(4)], 0, now=lambda: 0, epoch=lambda: 100, launch=launch, pause=lambda _: None)
            self.assertEqual(len(receipts), 2); self.assertTrue(all(row['launched'] for row in receipts))
            self.assertTrue(all(row['status'] == 'complete' for row in receipts))
            self.assertTrue(cleanup['all_producers_stopped'])
            binding = parse_json((Path(directory)/'caller-receipt-binding.json').read_bytes())
            self.assertEqual(binding['caller_admissions_sha256'], receipt_sha)
            receipt = parse_json((Path(directory)/'caller-admissions.json').read_bytes())
            self.assertEqual(set(receipt['allocations']), set(data))
            self.assertFalse(receipt['gpu_timing_attestation'])

    def test_popen_failure_preserves_primary_and_attempts_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            c = candidate(); data = challenges(); m = materials(data)
            plan = parent.full_input_plan(c, data, m, 0, now=lambda: 0)
            failure = OSError('fake launch refused')
            with patch.object(parent, 'cleanup_workers', wraps=parent.cleanup_workers) as cleanup:
                with self.assertRaises(OSError) as raised:
                    parent.run_full_input(Path(directory), plan, data, m, 'model', 'deps',
                        [{'uuid': 'gpu-'+str(i)} for i in range(4)], 0, now=lambda: 0, epoch=lambda: 100,
                        launch=unittest.mock.Mock(side_effect=failure))
                self.assertIs(raised.exception, failure); cleanup.assert_called_once()
            self.assertTrue((Path(directory)/'caller-receipt-binding.json').is_file())
            receipts = parse_json((Path(directory)/'worker-receipts.json').read_bytes())
            self.assertEqual(sum(row['launched'] for row in receipts), 1)
            self.assertEqual(len(receipts), 2)

    def test_secondary_receipt_write_failure_does_not_replace_launch_error(self):
        with tempfile.TemporaryDirectory() as directory:
            c = candidate(); data = challenges(); m = materials(data)
            plan = parent.full_input_plan(c, data, m, 0, now=lambda: 0)
            failure = OSError('primary launch failure'); launched = False
            original_write = parent.write
            def launch(*_, **__):
                nonlocal launched
                launched = True; raise failure
            def write(path, value):
                if launched and Path(path).name == 'worker-receipts.json': raise OSError('secondary disk failure')
                return original_write(path, value)
            with patch.object(parent, 'write', write):
                with self.assertRaises(OSError) as raised:
                    parent.run_full_input(Path(directory), plan, data, m, 'model', 'deps',
                        [{'uuid': 'gpu-'+str(i)} for i in range(4)], 0, now=lambda: 0, epoch=lambda: 100, launch=launch)
            self.assertIs(raised.exception, failure)
            self.assertTrue(any('secondary disk failure' in note for note in failure.__notes__))


class ActualPreparationSourceProofTests(unittest.TestCase):
    def test_actual_prepare_receipt_is_completed_without_relaxing_native_gate(self):
        import hashlib
        import sys
        from types import SimpleNamespace
        from tools import nvarc_public_eval_parent as legacy
        from tools.nvarc_source_verification import prepare_verified
        from tools.nvarc_native_multitask import digest, write
        from tools.nvarc_native_submission import verify_native_training_gate
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); root = base/'run'; dependency = base/'dependency'; model = base/'model'
            root.mkdir(); dependency.mkdir(); model.mkdir()
            (dependency/'qwen3.patch').write_bytes(b'synthetic exact dependency file')
            (dependency/'torch.py').write_bytes(b'# synthetic Torch path only')
            (model/'config.json').write_bytes(b'{}')
            inventory = {'qwen3.patch': {'bytes': (dependency/'qwen3.patch').stat().st_size,
                'sha256': hashlib.sha256((dependency/'qwen3.patch').read_bytes()).hexdigest()}}
            write(root/'source-inventory.json', inventory)
            write(root/'model-inventory.json', {'config.json': {'bytes': 2,
                'sha256': hashlib.sha256(b'{}').hexdigest()}})
            plan = {'source_inventory_digest': digest(inventory), 'model_material_digest': 'synthetic-model',
                    'task_specs': {'a': {'selected_gpu_index': 0}}}
            fake_torch = SimpleNamespace(__version__='2.8.0+cu128', __file__=str(dependency/'torch.py'),
                version=SimpleNamespace(cuda='12.8'))
            hardware = [{'uuid': 'synthetic-gpu-'+str(i), 'name': 'NVIDIA L4', 'bf16': True} for i in range(4)]
            helper = SimpleNamespace(collect_hardware_inventory=lambda *_: hardware)
            def path(value):
                if str(value).startswith('/kaggle/input/models/'): return model
                if str(value).startswith('/kaggle/input/qwen3_'): return base/'absent-model'
                return Path(value)
            with patch.object(legacy, 'Path', side_effect=path), \
                 patch.object(legacy.shutil, 'disk_usage', return_value=SimpleNamespace(free=30*1024**3)), \
                 patch.object(sys, 'version_info', (3, 11, 13)), patch.object(sys, 'path', list(sys.path)), \
                 patch.dict(sys.modules, {'torch': fake_torch, 'hardware_helpers': helper}), \
                 patch.object(legacy.subprocess, 'run', return_value=SimpleNamespace(stdout='synthetic inventory')):
                prepared = prepare_verified(root, plan, dependency, prepare=legacy.prepare)
            self.assertEqual(prepared, (model, hardware))
            original = parse_json((root/'source-verification-prepare.json').read_bytes())
            self.assertEqual(set(original), {'inventory_digest', 'dependency_root'})
            observed = parse_json((root/'source-verification.json').read_bytes())
            self.assertEqual(observed['inventory'], inventory)
            self.assertEqual(observed['inventory_digest'], plan['source_inventory_digest'])
            self.assertEqual(observed['prepare_receipt_sha256'], hashlib.sha256(
                (root/'source-verification-prepare.json').read_bytes()).hexdigest())
            write(root/'parent-verification.json', {'plan_digest': digest(plan), 'source_inventory_verified': True,
                'four_distinct_bf16_l4s': True, 'model_material_digest': plan['model_material_digest']})
            # Actual production gate consumes the completed preparation schema.
            # This tiny fixture has no task/model evidence; it must stop at that
            # next missing-artifact gate, never pass native qualification.
            with self.assertRaisesRegex(RuntimeError, 'tasks/a/native/hardware.json'):
                verify_native_training_gate(root, plan, {'a': challenges()['new-b']}, 'a', None, None)

    def test_changed_inventory_or_self_reported_digest_is_rejected(self):
        from tools.nvarc_source_verification import prepare_verified
        from tools.nvarc_native_multitask import digest, write
        for mode in ('changed-inventory', 'wrong-digest', 'wrong-root'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); inventory = {'synthetic': {'bytes': 1, 'sha256': 'a'*64}}
                write(root/'source-inventory.json', inventory)
                def preparer(root, plan, dependency):
                    write(root/'source-verification.json', {'inventory_digest': 'foreign' if mode == 'wrong-digest' else digest(inventory),
                        'dependency_root': 'foreign' if mode == 'wrong-root' else str(dependency)})
                    if mode == 'changed-inventory': write(root/'source-inventory.json', {'changed': True})
                    return None
                with self.assertRaises(RuntimeError):
                    prepare_verified(root, {'source_inventory_digest': digest(inventory)}, Path('/synthetic-dependency'), prepare=preparer)
                self.assertFalse((root/'source-verification-prepare.json').exists())


class ProductionResourceObservationTests(unittest.TestCase):
    def test_owned_cpu_export_observer_measures_child_rss_and_phase_disk(self):
        import os
        import sys
        from tools.nvarc_resource_observer import ResourceObserver, run_observed
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); observer = ResourceObserver(root, sample_seconds=.1).start()
            with (root/'stdout.log').open('w') as out, (root/'stderr.log').open('w') as err, observer.phase('fresh_export_fixture'):
                result = run_observed([sys.executable, '-c', "from pathlib import Path; x=bytearray(8*1024**2); Path('evidence.bin').write_bytes(x)"],
                    cwd=root, env=os.environ.copy(), stdout=out, stderr=err, timeout=10)
            report = observer.close()
            self.assertEqual(result['returncode'], 0); self.assertTrue(result['confirmed_stopped']); self.assertFalse(result['timed_out'])
            self.assertGreater(result['child_peak_rss_bytes'], 0)
            self.assertEqual(result['child_peak_rss_method'], 'owned-child wait4 RUSAGE')
            self.assertGreaterEqual(report['sampled_file_logical_peak_bytes'], 8*1024**2)
            self.assertGreater(report['phases']['fresh_export_fixture']['wall_seconds'], 0)
            self.assertTrue(report['disk_peak_is_sampled']); self.assertFalse(report['resource_qualification'])
            self.assertIn('not run', report['recovery_measurement'])

    def test_cpu_export_clock_kills_silent_child_and_missing_wait4_is_explicit(self):
        import os
        import sys
        from tools.nvarc_resource_observer import run_observed
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root/'stdout.log').open('w') as out, (root/'stderr.log').open('w') as err:
                failed = run_observed([sys.executable, '-c', 'import time;time.sleep(10)'], cwd=root,
                    env=os.environ.copy(), stdout=out, stderr=err, timeout=.7, cleanup_seconds=.3)
                plain = run_observed([sys.executable, '-c', 'pass'], cwd=root, env=os.environ.copy(),
                    stdout=out, stderr=err, timeout=10, wait4=None)
            self.assertTrue(failed['timed_out']); self.assertTrue(failed['confirmed_stopped'])
            self.assertLess(failed['wall_seconds'], 1)
            self.assertIsNone(plain['child_peak_rss_bytes']); self.assertEqual(plain['child_peak_rss_method'], 'unavailable')
            self.assertEqual(plain['gpu_calls_added'], 0); self.assertEqual(plain['device_synchronizations_added'], 0)

    def test_export_launch_nonzero_and_wait_errors_retain_honest_receipts(self):
        import os
        import sys
        from tools.nvarc_resource_observer import run_observed
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root/'stdout.log').open('w') as out, (root/'stderr.log').open('w') as err:
                base = dict(cwd=root, env=os.environ.copy(), stdout=out, stderr=err, timeout=10)
                nonzero = run_observed([sys.executable, '-c', 'raise SystemExit(7)'], **base)
                launch = run_observed([], launch=unittest.mock.Mock(side_effect=OSError('launch denied')), **base)
                unavailable = run_observed([sys.executable, '-c', 'pass'],
                    wait4=unittest.mock.Mock(side_effect=OSError('wait4 unsupported')), **base)
                fake = unittest.mock.Mock(pid=1234, returncode=None)
                lost = run_observed([], launch=unittest.mock.Mock(return_value=fake),
                    wait4=unittest.mock.Mock(side_effect=ChildProcessError('lost receipt')), **base)
            self.assertEqual(nonzero['returncode'], 7); self.assertGreater(nonzero['child_peak_rss_bytes'], 0)
            self.assertFalse(launch['launched']); self.assertIsNone(launch['returncode'])
            self.assertEqual(launch['errors'][0]['phase'], 'child-launch')
            self.assertEqual(unavailable['returncode'], 0); self.assertIsNone(unavailable['child_peak_rss_bytes'])
            self.assertEqual(unavailable['errors'][0]['phase'], 'owned-child-wait4')
            self.assertIsNone(lost['returncode']); self.assertFalse(lost['confirmed_stopped']); fake.poll.assert_not_called()

    def test_live_child_wait4_receipt_loss_still_stops_and_reaps_owned_child(self):
        import os
        import sys
        from tools.nvarc_resource_observer import run_observed
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root/'stdout.log').open('w') as out, (root/'stderr.log').open('w') as err:
                observed = run_observed([sys.executable, '-c', 'import time;time.sleep(30)'], cwd=root,
                    env=os.environ.copy(), stdout=out, stderr=err, timeout=2, cleanup_seconds=.3,
                    wait4=unittest.mock.Mock(side_effect=ChildProcessError('injected live-child wait4 fault')))
            self.assertTrue(observed['stop_attempted']); self.assertTrue(observed['confirmed_stopped'])
            self.assertEqual(observed['returncode'], -9); self.assertFalse(observed['timed_out'])
            self.assertTrue(observed['exit_observation_lost'])
            self.assertIsNone(observed['child_peak_rss_bytes']); self.assertLess(observed['wall_seconds'], 2.1)

    def test_guarded_cpu_replay_stops_after_abrupt_owner_death(self):
        import json
        import os
        import signal
        import subprocess
        import sys
        import time
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fixture = root/'sleep.py'; ready = root/'ready.json'
            fixture.write_text("import json,os,time\nfrom pathlib import Path\nPath("+repr(str(ready))+").write_text(json.dumps({'pid':os.getpid(),'owner':os.getppid()}))\ntime.sleep(30)\n")
            guard = builder.ROOT/'tools/nvarc_guarded_cpu.py'
            code = "import os,subprocess,sys,time\nsubprocess.Popen([sys.executable,"+repr(str(guard))+",'--owner-pid',str(os.getpid()),'--script',"+repr(str(fixture))+",'--'])\ntime.sleep(30)\n"
            environment = dict(os.environ, PYTHONHASHSEED='0', CUDA_VISIBLE_DEVICES='', PYTHONPATH=str(builder.ROOT))
            owner = subprocess.Popen([sys.executable, '-c', code], env=environment, cwd=root, start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            child = None; stopped = False
            try:
                deadline = time.monotonic()+3
                while not ready.exists() and time.monotonic() < deadline: time.sleep(.01)
                self.assertTrue(ready.exists(), 'guarded CPU fixture did not start')
                value = json.loads(ready.read_text()); child = value['pid']; self.assertEqual(value['owner'], owner.pid)
                os.kill(owner.pid, signal.SIGKILL); owner.wait(timeout=2)
                deadline = time.monotonic()+2; stopped = False
                while time.monotonic() < deadline:
                    try: state = Path('/proc/'+str(child)+'/stat').read_text().split(') ', 1)[1].split()[0]
                    # A process reaped between procfs open and read raises ESRCH.
                    except (FileNotFoundError, ProcessLookupError): stopped = True; break
                    if state == 'Z': stopped = True; break
                    time.sleep(.01)
                self.assertTrue(stopped, 'CPU replay survived abrupt owner-only kill')
            finally:
                if owner.poll() is None: os.killpg(owner.pid, signal.SIGKILL); owner.wait(timeout=2)
                if child is not None and not stopped:
                    try: os.kill(child, signal.SIGKILL)
                    except ProcessLookupError: pass

    def test_missing_wait4_does_not_turn_alternate_reaped_exit7_into_zero(self):
        import os
        import subprocess
        import sys
        from tools.nvarc_resource_observer import run_observed
        def alternate_reaper(command, **kwargs):
            child = subprocess.Popen(command, **kwargs)
            pid, status = os.waitpid(child.pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 7)
            return child  # leave Popen.returncode unset, reproducing poll ECHILD
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root/'stdout.log').open('w') as out, (root/'stderr.log').open('w') as err:
                result = run_observed([sys.executable, '-c', 'raise SystemExit(7)'], cwd=root,
                    env=os.environ.copy(), stdout=out, stderr=err, timeout=2, cleanup_seconds=.3,
                    launch=alternate_reaper, wait4=None)
            self.assertIsNone(result['returncode']); self.assertTrue(result['exit_observation_lost'])
            self.assertEqual(result['errors'][-2]['phase'], 'owned-child-waitpid')
            self.assertIsNone(result['child_peak_rss_bytes'])

    def test_resource_close_and_cuda_faults_preserve_primary_and_attempt_receipt(self):
        original = OSError('primary preparation failure')
        observer = unittest.mock.Mock(); observer.close.side_effect = RuntimeError('secondary sampler failure')
        save = unittest.mock.Mock(side_effect=OSError('secondary resource storage failure'))
        with patch.object(parent, 'worker_cuda_observations', side_effect=RuntimeError('secondary CUDA reader failure')):
            _, found = parent.finalize_resource_observations(observer, Path('/unused'), {'task_order': ['a']},
                None, None, {}, 0, original, save=save)
        self.assertIs(found, original); save.assert_called_once(); observer.close.assert_called_once()
        self.assertEqual(len(original.resource_observation_secondary_errors), 3)
        with tempfile.TemporaryDirectory() as directory:
            terminal, returned = parent.finalize_terminal(Path(directory), 'stage4-fixture', None, False, original)
        self.assertIs(returned, original); self.assertEqual(len(terminal['secondary_errors']), 3)
        self.assertEqual(terminal['notebook_exit'], 'failure')

    def test_execute_attempts_terminal_after_primary_disk_and_secondary_observer_failure(self):
        import os
        from types import SimpleNamespace
        original = OSError('primary disk admission failure')
        observer = unittest.mock.Mock(); observer.start.return_value = observer
        observer.close.side_effect = RuntimeError('secondary sampler failure')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'run'; root.mkdir()
            with patch('tools.stage_nvarc_stage4_candidate.verify_runtime_tree', return_value=candidate()), \
                 patch.object(parent, 'ResourceObserver', return_value=observer), \
                 patch.object(parent, 'require_working_disk', side_effect=original), \
                 patch.dict(os.environ, {'PYTHONHASHSEED': '0'}), \
                 patch.object(parent.sys, 'flags', SimpleNamespace(**{name: (0 if name == 'hash_randomization' else getattr(parent.sys.flags, name))
                     for name in dir(parent.sys.flags) if not name.startswith('_') and not callable(getattr(parent.sys.flags, name))})):
                with self.assertRaises(OSError) as raised: parent.execute(root, Path('/unused'), 0)
            self.assertIs(raised.exception, original)
            terminal = parse_json((root/'terminal.json').read_bytes())
            self.assertEqual(terminal['primary_error']['type'], 'OSError')
            self.assertEqual(terminal['secondary_errors'][0]['type'], 'RuntimeError')
            self.assertTrue((root/'resource-observations.json').exists())

    def test_current_disk_reserve_refuses_dispatch_without_workers(self):
        from types import SimpleNamespace
        c = candidate(); data = challenges(); m = materials(data)
        plan = parent.full_input_plan(c, data, m, 0, now=lambda: 0)
        with tempfile.TemporaryDirectory() as directory, patch.object(parent.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)):
            launch = unittest.mock.Mock()
            with self.assertRaisesRegex(RuntimeError, 'disk reserve unavailable'):
                parent.run_full_input(Path(directory), plan, data, m, None, None, [], 0, now=lambda: 0, launch=launch)
            launch.assert_not_called()
            self.assertFalse((Path(directory)/'plan.json').exists())

    def test_worker_cuda_highwaters_are_retained_without_inferred_concurrent_peak(self):
        from tools.nvarc_native_multitask import write
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); task = root/'tasks/a/native'; task.mkdir(parents=True)
            values = {'peak_allocated_bytes': 1234, 'peak_reserved_bytes': 5678, 'added_device_synchronizations': 0}
            write(task/'result.json', {'cuda_memory_observation': values})
            found = parent.worker_cuda_observations(root, ['a', 'missing'])
            self.assertEqual(found['per_task_process']['a']['observation'], values)
            self.assertIsNone(found['per_task_process']['missing']['observation'])
            self.assertIsNone(found['concurrent_gpu_peak_bytes']); self.assertEqual(found['gpu_calls_added'], 0)


class ExactPackageTests(unittest.TestCase):
    def contract(self):
        from tests.test_nvarc_native_notices import contract_v1
        return contract_v1()

    def fake_construct(self):
        sources = {name: (builder.ROOT/name).read_bytes() for name in builder.LOCAL_FILES}
        external = {name: b'{}' for name in builder.EXTERNAL_FILES+('verified-tokenizer.json',)}
        config = {'native_source_learning_rates': [0.0]*129, 'docker_image': 'pinned-test', 'model_sources': ['test/model']}
        return builder.construct('stage4-full-input-fixture-001', 'a'*40, external, config, self.contract(), sources), sources

    def test_new_package_deterministic_notebook_and_inert_transport_plan(self):
        with patch.object(builder, 'validate_baseline'), patch.object(builder, 'render_from_snapshot', return_value=b'# fixture worker\n'):
            (c, payload), sources = self.fake_construct()
            self.assertFalse(c['approved']); self.assertFalse(c['official_submission_authorized'])
            self.assertEqual(c['maximum_formal_submissions'], 0); self.assertFalse(c['promotion'])
            for name in ('tools/nvarc_output_lifecycle.py', 'tools/nvarc_allocation_transport.py', 'tools/nvarc_native_export.py'):
                self.assertIn(name, payload)
            self.assertNotIn('challenges.json', payload)
            notebook = builder.render(c, payload)
            self.assertEqual(builder.decoded_notebook(notebook), payload)
            source = ''.join(notebook['cells'][1]['source'])
            self.assertIn("PYTHONPATH=str(work),", source)
            self.assertNotIn("PYTHONPATH=str(work)+os.pathsep+str(matches[0])", source)
            with tempfile.TemporaryDirectory() as directory:
                package = Path(directory)/'package'; result = builder.stage(package, c, payload, sources)
                self.assertTrue(result['offline_package_verified']); self.assertFalse(result['official_scoring_ready'])
                self.assertEqual(result, builder.preflight(package, expected_manifest_sha256=result['package_manifest_sha256']))
                handoff = parse_json((package/'cli-handoff.json').read_bytes())
                self.assertFalse(handoff['execute_commands']); self.assertFalse(handoff['official_submission_authorized'])
                self.assertEqual(handoff['kernel_push_argv'][0], 'kaggle')
                self.assertNotIn('C:\\', str(handoff)); self.assertIn('--version', handoff['official_submission_argv_template'])
                (package/'unexpected.txt').write_text('extra')
                with self.assertRaisesRegex(RuntimeError, 'inventory differs'): builder.preflight(package)
                manifest = parse_json((package/'package-manifest.json').read_bytes())
                manifest['files_sha256']['unexpected.txt'] = builder.sha(package/'unexpected.txt')
                (package/'package-manifest.json').write_bytes(canonical(manifest))
                with self.assertRaisesRegex(RuntimeError, 'membership differs'): builder.preflight(package)

    def test_official_cli_template_uses_documented_positional_competition(self):
        candidate = {'run_id': 'stage4-full-input-offline-argv', 'kernel_id': 'owner/stage4-full-input-offline-argv',
            'maximum_notebook_wall_seconds': 42600}
        command = builder.cli_handoff(candidate)['official_submission_argv_template']
        self.assertEqual(command[:4], ['kaggle', 'competitions', 'submit', 'arc-prize-2026-arc-agi-2'])
        self.assertNotIn('-c', command); self.assertNotIn('--competition', command)
        self.assertIn('--version', command); self.assertIn('EXACT-REVIEWED-VERSION', command)
        self.assertFalse(builder.cli_handoff(candidate)['execute_commands'])

    def test_tampered_notebook_hash_rejects_without_execution(self):
        with patch.object(builder, 'validate_baseline'), patch.object(builder, 'render_from_snapshot', return_value=b'# fixture worker\n'):
            (c, payload), _ = self.fake_construct()
            notebook = builder.render(c, payload)
            source = ''.join(notebook['cells'][1]['source']).replace("HASHES=", "HASHES={'wrong': 'wrong'}\nOLD_HASHES=", 1)
            notebook['cells'][1]['source'] = source.splitlines(keepends=True)
            with self.assertRaisesRegex(RuntimeError, 'closed notebook'): builder.decoded_notebook(notebook)

    def test_only_new_stage4_run_identity_is_accepted(self):
        with self.assertRaisesRegex(RuntimeError, 'new Stage4 identity'):
            builder.construct('nvarc-stage3-official-001', 'a'*40, {}, {}, {}, {})

    def test_resource_policy_cannot_underreserve_or_use_nonfinite_numbers(self):
        for key, value in [('scheduler_reserve_seconds', 0), ('maximum_notebook_wall_seconds', float('inf')),
                           ('maximum_export_process_seconds', 1801)]:
            policy = dict(builder.POLICY); policy[key] = value
            with self.assertRaises(RuntimeError): builder.validate_policy(policy)

    def test_controller_receipts_never_imply_scientific_promotion(self):
        with patch.object(builder, 'validate_baseline'), patch.object(builder, 'render_from_snapshot', return_value=b'# fixture worker\n'):
            (_, _), sources = self.fake_construct()
            admission = {'decision': '0061', 'run_id': 'stage4-full-input-fixture-002', 'execution_plan_digest': 'sha256:'+'a'*64,
                'current_free_resource_check_sha256': 'b'*64, 'material_rules_check_sha256': 'c'*64, 'paid_usd': 0, 'private': True}
            external = {name: b'{}' for name in builder.EXTERNAL_FILES+('verified-tokenizer.json',)}
            from tools.stage_nvarc_e10_screen import NOTICE_FILES_SHA256
            contract = {**self.contract(), 'format': 'irisx/native-code-material-contract-v2',
                'notices_sha256': dict(NOTICE_FILES_SHA256)}
            external.update({'notices/'+name: (builder.ROOT/'research/stage4-e10/native-notices'/name).read_bytes()
                for name in NOTICE_FILES_SHA256})
            c, _ = builder.construct('stage4-full-input-fixture-002', 'a'*40, external,
                {'native_source_learning_rates': [0.0]*129, 'docker_image': 'test', 'model_sources': []}, contract, sources, admission=admission)
            self.assertTrue(c['approved']); self.assertFalse(c['promotion'])
            self.assertIn('pending', c['scientific_selection_status']); self.assertFalse(c['actual_gpu_timing_measured'])

    def test_historical_material_contract_cannot_admit_private_candidate(self):
        with patch.object(builder, 'validate_baseline'):
            sources = {name: (builder.ROOT/name).read_bytes() for name in builder.LOCAL_FILES}
            with self.assertRaisesRegex(RuntimeError, 'license/notice closure'):
                builder.construct('stage4-full-input-denied-license', 'a'*40, {}, {},
                    self.contract(), sources, admission={})

    def test_v2_notices_survive_exact_candidate_reconstruction(self):
        from tools.stage_nvarc_e10_screen import NOTICE_FILES_SHA256
        with patch.object(builder, 'validate_baseline'), patch.object(builder, 'render_from_snapshot', return_value=b'# fixture worker\n'):
            (_, _), sources = self.fake_construct()
            contract = {**self.contract(), 'format': 'irisx/native-code-material-contract-v2',
                'notices_sha256': dict(NOTICE_FILES_SHA256)}
            external = {name: b'{}' for name in builder.EXTERNAL_FILES+('verified-tokenizer.json',)}
            external.update({'notices/'+name: (builder.ROOT/'research/stage4-e10/native-notices'/name).read_bytes()
                for name in NOTICE_FILES_SHA256})
            c, payload = builder.construct('stage4-full-input-notices-fixture', 'a'*40, external,
                {'native_source_learning_rates': [0.0]*129, 'docker_image': 'test', 'model_sources': []}, contract, sources)
            self.assertTrue(c['native_notebook_notice_closure']); self.assertFalse(c['approved'])
            self.assertIn('tools/nvarc_resource_attachment.py', payload)
            with tempfile.TemporaryDirectory() as temp:
                result = builder.stage(Path(temp)/'package', c, payload, sources)
                self.assertTrue(result['offline_package_verified'])


class IndependentTerminalAndResourceTests(unittest.TestCase):
    def test_output_valid_does_not_imply_success_qualification_or_promotion(self):
        store = unittest.mock.Mock(); store.verify_projection.return_value = {}
        with tempfile.TemporaryDirectory() as directory:
            error = RuntimeError('cleanup failed after committed output')
            terminal, found = parent.finalize_terminal(Path(directory), 'stage4-test', store, True, error)
            self.assertIs(found, error); self.assertTrue(terminal['output_valid'])
            self.assertEqual(terminal['notebook_exit'], 'failure'); self.assertTrue(terminal['evidence_qualified'])
            self.assertFalse(terminal['promotion'])

    def test_strict_export_requires_every_actual_task_without_pool_selection(self):
        command = parent.strict_export_command(Path('/root-fixture'), Path('/model-fixture'), 'a'*64, ['new-b', 'changed-a'])
        values = [value.split('=', 1)[1] for value in command if value.startswith('--require-task-gates=')]
        self.assertEqual(values, ['new-b', 'changed-a'])
        self.assertIn('--', command)
        odd = parent.strict_export_command(Path('.'), Path('.'), 'a'*64, ['--owner-pid'])
        self.assertIn('--require-task-gates=--owner-pid', odd)
        self.assertIn('--caller-admissions-sha256', command)
        self.assertIn('nvarc_guarded_cpu.py', command[1]); self.assertIn('--owner-pid', command)
        self.assertEqual(command[command.index('--owner-pid')+1], str(__import__('os').getpid()))
        with self.assertRaises(RuntimeError): parent.strict_export_command(Path('.'), Path('.'), 'a'*64, [])

    def test_missing_partial_or_bad_mandatory_gates_cannot_qualify_empty_pools(self):
        from copy import deepcopy
        proof = {'training': {'full_task_epoch_verified': True, 'model_material_digest': 'model-pin',
            'preparation_digest': 'sha256:'+'a'*64, 'training_ledger_digest': 'sha256:'+'b'*64,
            'trained_inventory_digest': 'sha256:'+'c'*64, 'reset_verified_by_this_gate': False},
            'reset_inventory_digest': 'sha256:'+'d'*64, 'host_telemetry_digest': 'sha256:'+'e'*64}
        context = {'mandatory_task_gates': {'a': proof, 'b': deepcopy(proof)}}
        parent.require_mandatory_gate_context(context, ['a', 'b'], 'model-pin')
        for mode in ('missing', 'partial', 'epoch', 'reset-digest', 'model', 'extra'):
            bad = deepcopy(context)
            if mode == 'missing': bad = {}
            elif mode == 'partial': del bad['mandatory_task_gates']['b']
            elif mode == 'epoch': bad['mandatory_task_gates']['b']['training']['full_task_epoch_verified'] = False
            elif mode == 'reset-digest': bad['mandatory_task_gates']['b']['reset_inventory_digest'] = None
            elif mode == 'model': bad['mandatory_task_gates']['b']['training']['model_material_digest'] = 'foreign-model'
            elif mode == 'extra': bad['mandatory_task_gates']['b']['evaluator_truth'] = True
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                parent.require_mandatory_gate_context(bad, ['a', 'b'], 'model-pin')

    def test_reused_gate_still_checks_native_epoch_for_a_zero_candidate_pool(self):
        from tools import nvarc_calibration_gate as calibration
        from types import SimpleNamespace
        data = {'a': challenges()['new-b']}
        evidence = [{'task_id': 'a', 'provenance': 'native-model',
            'receipt': {'status': 'complete', 'launched': True, 'returncode': 0},
            'checkpoint': {'tests': [{'attempts': []}]}}]
        with patch.object(calibration, 'load_sources', return_value=(SimpleNamespace(), None, None)), \
             patch.object(calibration, 'verify_native_training_gate', side_effect=RuntimeError('mandatory epoch proof')) as gate:
            with self.assertRaisesRegex(RuntimeError, 'mandatory epoch proof'):
                calibration.require_task_gates('.', {}, data, evidence, None, ['a'])
            gate.assert_called_once()

    def test_final_projection_failure_cannot_return_success_exit(self):
        store = unittest.mock.Mock(); store.verify_projection.side_effect = ValueError('mixed projections')
        with tempfile.TemporaryDirectory() as directory:
            terminal, error = parent.finalize_terminal(Path(directory), 'stage4-test', store, True, None)
            self.assertFalse(terminal['output_valid']); self.assertEqual(terminal['notebook_exit'], 'failure')
            self.assertIsInstance(error, RuntimeError); self.assertTrue(terminal['evidence_qualified'])
            self.assertFalse(terminal['promotion'])
            self.assertEqual(terminal['rss_observation_boundary'], 'after working publication and final projection verification')

    def test_terminal_storage_failure_retains_valid_generation_and_fails_exit(self):
        store = unittest.mock.Mock()
        def fail(*_): raise OSError('disk full')
        terminal, error = parent.finalize_terminal(Path('/unused'), 'stage4-test', store, False, None, save=fail)
        self.assertTrue(terminal['output_valid']); self.assertEqual(terminal['notebook_exit'], 'failure')
        self.assertFalse(terminal['evidence_qualified']); self.assertFalse(terminal['promotion']); self.assertIsInstance(error, OSError)

    def test_empty_pools_or_legal_output_cannot_bypass_epoch_reset_completion(self):
        coverage = {'tasks_launched': 2, 'task_count': 2, 'full_epochs': 2,
                    'tests_started': 3, 'test_count': 3, 'all_resets_verified': True}
        receipts = [{'launched': True, 'status': 'complete', 'returncode': 0} for _ in range(2)]
        parent.require_complete_rehearsal(coverage, receipts)
        for key, value in [('full_epochs', 1), ('tests_started', 2), ('all_resets_verified', False)]:
            changed = dict(coverage); changed[key] = value
            with self.assertRaisesRegex(RuntimeError, 'rehearsal incomplete'):
                parent.require_complete_rehearsal(changed, receipts)
        receipts[0]['status'] = 'worker_crash'
        with self.assertRaisesRegex(RuntimeError, 'rehearsal incomplete'):
            parent.require_complete_rehearsal(coverage, receipts)

    def test_atomic_root_projection_recovery_reuses_same_commit(self):
        from tools.nvarc_output_lifecycle import sha
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); data = challenges()
            submission = {key: [{'attempt_1': [[0]], 'attempt_2': [[0]]} for _ in task['test']] for key, task in data.items()}
            values = {'native-evidence.json': [], 'submission.json': submission, 'submission-audit.json': {}, 'export-process.json': {}}
            native = GenerationStore(root/'native', 'native', {'run_id': 'fake-native', 'plan_digest': 'fake-plan'})
            native.publish(values, evidence_qualified=True)  # only a unit-fixture gate
            _, bodies = native.read()
            summary = {'run_id': 'fake-native', 'runtime_plan_digest': 'fake-plan',
                'strict_same_runtime_export_completed': True, 'submission_sha256': sha(bodies['submission.json']),
                'audit_sha256': sha(bodies['submission-audit.json'])}
            working = parent.publish_working_output(native, root/'working', data, summary)
            before = working.verify_projection()
            (root/'working/submission.json').write_bytes(b'{')
            self.assertFalse(parent.working_valid(working))
            repaired = parent.recover_working_output(native, root/'working', data, summary)
            after = repaired.verify_projection()
            self.assertEqual(before['generation'], after['generation'])
            self.assertFalse(after['outcomes']['promotion']); self.assertEqual(after['outcomes']['notebook_exit'], 'unknown')

    def test_small_resource_fixture_runs_actual_lifecycle_and_stays_unqualified(self):
        with tempfile.TemporaryDirectory() as directory:
            result = resource_run(Path(directory)/'resource', evidence_bytes=1024*1024, maximum_seconds=30)
            self.assertTrue(result['same_committed_generation_recovered']); self.assertEqual(result['counts']['test_output_count'], 3)
            self.assertGreater(result['observed_process_peak_rss_bytes'], 0); self.assertGreater(result['observed_disk_peak_sampled_bytes'], 0)
            self.assertFalse(result['historical_reference_scale_attested']); self.assertEqual(result['gpu_runs'], 0)
            self.assertFalse(result['evidence_qualified']); self.assertFalse(result['promotion'])


if __name__ == '__main__': unittest.main()

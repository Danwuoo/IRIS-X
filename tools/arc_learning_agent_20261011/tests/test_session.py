"""Actual tiny-neural lifecycle; synthetic120/167 only, never benchmark claims."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tools.arc_next_offline_environment import _LAUNCHER
from tools.arc_learning_agent_20261011 import session
from tools.arc_public_research_20261010.tests.test_public_data import make_assets
from tools.arc_learning_agent_20261011.tests.test_data import fixture_tasks
from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_learning_agent_20261011.session import run_session, _path_guard


class SessionBoundaryTests(unittest.TestCase):
    def test_source_output_overlap_rejected_before_work(self):
        from tools.arc_learning_agent_20261011.session import ROOT
        with self.assertRaises(ValueError): _path_guard(ROOT / 'new-output', ['/not-accessed'])

    def test_input_output_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): _path_guard(Path(d) / 'input/output', [Path(d) / 'input'])


class BootstrapBudgetTests(unittest.TestCase):
    def attempt(self, *, age, preflight_seconds=40, bootstrap_seconds=120, blocked=False):
        temp = tempfile.TemporaryDirectory(prefix='learning-budget-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name); output = root / 'output'
        wall = [2_000_000_000.0]; monotonic = [1000.0]
        started_epoch = wall[0] - age
        create_clock = session.SessionClock.create

        def clock(*args, **kwargs):
            return create_clock(*args, **kwargs, wall=lambda: wall[0], monotonic=lambda: monotonic[0])

        def advance(seconds):
            wall[0] += seconds; monotonic[0] += seconds

        def controls(*args):
            advance(preflight_seconds)
            return {'passed': True, 'gas': 0}

        def prepare(*args, **kwargs):
            advance(bootstrap_seconds)
            return {'python_command': [sys.executable, '-I', '-B'],
                    'model_path': str(root / 'unused-model'),
                    'manifest_path': str(root / 'unused-model-manifest'),
                    'environment_lock_path': str(root / 'unused-environment-lock')}

        fake_time = mock.Mock(wraps=time)
        fake_time.monotonic.side_effect = lambda: monotonic[0]
        fake_time.time.side_effect = lambda: wall[0]
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(session, 'time', fake_time))
            stack.enter_context(mock.patch.object(session.SessionClock, 'create', side_effect=clock))
            stack.enter_context(mock.patch.object(session, '_controls', side_effect=controls))
            stack.enter_context(mock.patch.object(session, 'source_identity', return_value={}))
            stack.enter_context(mock.patch.object(session.public_data, 'load_solver_tasks', return_value={
                'manifest': {'evidence_mode': 'synthetic-test-only'}, 'challenges': {}}))
            stack.enter_context(mock.patch('tools.arc_learning_agent_20261011.data.load_official_training',
                                          return_value=({}, {'synthetic_test_only': True})))
            prepare_mock = stack.enter_context(mock.patch(
                'tools.arc_public_research_20261010.offline_bootstrap.prepare_model_environment', side_effect=prepare))
            spawn = stack.enter_context(mock.patch.object(session.OwnedProcessGuard, 'spawn',
                                                          side_effect=RuntimeError('stop before worker')))
            expected = self.assertRaisesRegex(session.BudgetExceeded, 'bootstrap budget exhausted') if blocked else \
                       self.assertRaisesRegex(RuntimeError, 'stop before worker')
            with expected:
                run_session(output, solver_root=root / 'unused-solver', evaluator_root=root / 'unused-evaluator',
                    solver_manifest_sha256='1' * 64, evaluator_manifest_sha256='2' * 64,
                    training_root=root / 'unused-training', enable_model=True,
                    config={'predispatch_clock': True}, started_epoch=started_epoch)
        record = json.loads((output / 'session-clock.json').read_text())
        self.assertEqual(record['started_epoch'], started_epoch)
        self.assertEqual(record['deadline_epoch'], started_epoch + 43200)
        self.assertEqual(record['maximum_seconds'], 43200)
        self.assertEqual(record['origin'], 'pre-dispatch')
        if blocked:
            prepare_mock.assert_not_called(); spawn.assert_not_called()
            self.assertFalse((output / 'worker/request.json').exists())
            return
        prepare_mock.assert_called_once(); spawn.assert_called_once()
        request = json.loads((output / 'worker/request.json').read_text())
        self.assertEqual(request['clock'], record)
        self.assertEqual(request['parent_bootstrap_seconds'], preflight_seconds + bootstrap_seconds)
        return prepare_mock.call_args.kwargs['deadline_seconds']

    def test_old_global_start_keeps_deadline_and_current_attempt_stage_cap(self):
        # A prior failed attempt consumed wall time, not this attempt's setup.
        self.assertEqual(self.attempt(age=3600), 1760)

    def test_global_expiry_or_closure_reserve_blocks_bootstrap(self):
        for remaining in (0, 3599):
            with self.subTest(remaining=remaining):
                self.attempt(age=43200 - remaining, preflight_seconds=0, blocked=True)

    def test_current_attempt_stage_exhaustion_blocks_bootstrap(self):
        for elapsed in (1800, 1801):
            with self.subTest(elapsed=elapsed):
                self.attempt(age=3600, preflight_seconds=elapsed, blocked=True)

    def test_shrinking_global_remaining_further_limits_bootstrap(self):
        self.assertEqual(self.attempt(age=43200 - 3600 - 90, bootstrap_seconds=5), 50)


_LAUNCH_PROBE = '''
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys

request_path = Path(sys.argv[1])
assert len(sys.argv) == 3
assert hashlib.sha256(request_path.read_bytes()).hexdigest() == sys.argv[2]
receipt = {'argv': sys.argv, 'isolated': sys.flags.isolated,
           'ignore_environment': sys.flags.ignore_environment,
           'no_user_site': sys.flags.no_user_site, 'no_site': sys.flags.no_site,
           'dont_write_bytecode': sys.dont_write_bytecode,
           'initial_path': sys.path[:], 'offline_guard': False}
module_path = Path(__file__).with_name('bytecode_probe.py')
spec = importlib.util.spec_from_file_location('bytecode_probe', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.VALUE == 7
if getattr(socket, '_irisx_offline_guard', False):
    blocked = []
    for operation in (lambda: socket.socket(socket.AF_INET),
                      lambda: socket.socket(socket.AF_INET6),
                      lambda: socket.getaddrinfo('localhost', 80)):
        try:
            operation()
        except RuntimeError as exc:
            blocked.append('IRISX offline guard' in str(exc))
        else:
            blocked.append(False)
    receipt['offline_guard'] = all(blocked)
receipt['offline_env'] = {key: os.environ.get(key) for key in
    ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_DATASETS_OFFLINE', 'PIP_NO_INDEX')}
Path('launch-probe.json').write_text(json.dumps(receipt))
'''


@unittest.skipUnless(sys.platform.startswith('linux'), 'real Linux owned-process launch')
class LauncherContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='learning-launch-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'paths with spaces'; self.root.mkdir()
        self.launcher = self.root / 'offline-run.py'
        self.launcher.write_bytes(_LAUNCHER.encode('utf-8'))
        self.prefix = [sys.executable, '-I', '-B', '-S', str(self.launcher)]
        self.probe = self.root / 'worker.py'; self.probe.write_text(_LAUNCH_PROBE)
        (self.root / 'bytecode_probe.py').write_text('VALUE = 7\n')
        self.injection = self.root / 'untrusted-pythonpath'; self.injection.mkdir()
        self.site_marker = self.root / 'sitecustomize-ran'
        (self.injection / 'sitecustomize.py').write_text(
            'from pathlib import Path\nPath(%r).write_text("unexpected")\n' % str(self.site_marker))

    def launch_session(self, name, *, tiny=False, executable=None, real_worker=False):
        output = self.root / name
        prepared = {'python_command': self.prefix, 'model_path': str(self.root / 'unused-model'),
                    'manifest_path': str(self.root / 'unused-model-manifest'),
                    'environment_lock_path': str(self.root / 'unused-environment-lock')}
        config = ({'tiny_cpu': True, 'validation_mode': True, 'session_seconds': 7200,
                   'python_executable': executable} if tiny else {})
        # This isolates command transport, not scientific acceptance. Preflight
        # and bootstrap are stubs; the exact launcher, process guard and child
        # execute for real. No result is fabricated, so scoring must stay closed.
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(session, '_controls', return_value={'passed': True, 'gas': 0}))
            stack.enter_context(mock.patch.object(session, 'source_identity', return_value={}))
            stack.enter_context(mock.patch.object(session.public_data, 'load_solver_tasks', return_value={
                'manifest': {'evidence_mode': 'synthetic-test-only'}, 'challenges': {}}))
            stack.enter_context(mock.patch('tools.arc_learning_agent_20261011.data.load_official_training',
                                          return_value=({}, {'synthetic_test_only': True})))
            stack.enter_context(mock.patch(
                'tools.arc_public_research_20261010.offline_bootstrap.prepare_model_environment',
                return_value=prepared))
            stack.enter_context(mock.patch.dict(os.environ, {'PYTHONPATH': str(self.injection),
                                                             'PYTHONDONTWRITEBYTECODE': '0'}))
            if not real_worker:
                stack.enter_context(mock.patch.object(session, '__file__', str(self.root / 'session.py')))
            result = run_session(output, solver_root=self.root / 'unused-solver',
                evaluator_root=self.root / 'unused-evaluator', solver_manifest_sha256='1' * 64,
                evaluator_manifest_sha256='2' * 64, training_root=self.root / 'unused-training',
                enable_model=True, config=config)
        self.assertEqual(result['status'], 'OWNER_FAILED')
        self.assertIsNone(result['score'])
        self.assertTrue(result['closure']['process_tree_proof']['closed'])
        self.assertTrue(result['closure']['process_tree_proof']['ownership_complete'])
        self.assertFalse((output / 'predictions').exists())
        self.assertFalse((output / 'evaluation').exists())
        return output, result

    def check_probe(self, output, prefix):
        worker = output / 'worker'
        stderr = (worker / 'stderr.txt').read_text()
        self.assertEqual(stderr, '')
        receipt = json.loads((worker / 'launch-probe.json').read_text())
        request = worker / 'request.json'
        expected = [str(self.probe), str(request), hashlib.sha256(request.read_bytes()).hexdigest()]
        self.assertEqual(receipt['argv'], expected)
        launch = json.loads((worker / 'process-guard/launch.json').read_text())
        self.assertEqual(launch['worker_argv'], [*prefix, *expected])
        for flag in ('isolated', 'ignore_environment', 'no_user_site', 'dont_write_bytecode'):
            self.assertEqual(receipt[flag], 1, flag)
        self.assertNotIn(str(self.injection), receipt['initial_path'])
        self.assertFalse(self.site_marker.exists())
        self.assertEqual(list(self.root.rglob('*.pyc')), [])
        return receipt

    def test_original_appended_flags_fail_before_worker_negative_control(self):
        request = self.root / 'negative-request.json'; request.write_text('{}')
        command = [*self.prefix, '-I', '-B', str(self.probe), str(request),
                   hashlib.sha256(request.read_bytes()).hexdigest()]
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FileNotFoundError', result.stderr)
        self.assertIn("'-I'", result.stderr)
        self.assertFalse((self.root / 'launch-probe.json').exists())

    def test_verified_offline_prefix_executes_unchanged_with_guard(self):
        before = list(self.prefix)
        output, result = self.launch_session('wrapped')
        self.assertEqual(result['closure']['returncode'], 0)
        receipt = self.check_probe(output, self.prefix)
        self.assertEqual(self.prefix, before)
        self.assertEqual(self.launcher.read_bytes(), _LAUNCHER.encode('utf-8'))
        self.assertEqual(receipt['no_site'], 1)
        self.assertTrue(receipt['offline_guard'])
        self.assertEqual(set(receipt['offline_env'].values()), {'1'})

    def test_direct_python_string_and_flag_lists_keep_isolation(self):
        for index, executable in enumerate((sys.executable, [sys.executable], [sys.executable, '-u'])):
            with self.subTest(executable=executable):
                output, result = self.launch_session('direct-%d' % index, tiny=True, executable=executable)
                self.assertEqual(result['closure']['returncode'], 0)
                flags = executable[1:] if isinstance(executable, list) else []
                receipt = self.check_probe(output, [sys.executable, '-I', '-B', *flags])
                self.assertEqual(receipt['no_site'], 0)

    def test_real_worker_imports_and_reaches_bound_request_source_gate(self):
        output, result = self.launch_session('real-worker', real_worker=True)
        self.assertEqual(result['closure']['returncode'], 2)
        worker = output / 'worker'
        self.assertEqual((worker / 'stderr.txt').read_text(), 'ValueError: sealed executable source differs\n')
        launch = json.loads((worker / 'process-guard/launch.json').read_text())
        self.assertEqual(launch['worker_argv'][:len(self.prefix)], self.prefix)
        # The real CLI must still validate its request digest before run().
        rejected = subprocess.run([*launch['worker_argv'][:-1], '0' * 64], cwd=worker,
                                  capture_output=True, text=True, timeout=15)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('bound file digest differs: request.json', rejected.stderr)
        self.assertNotIn('ModuleNotFoundError', rejected.stderr)
        self.assertNotIn('FileNotFoundError', rejected.stderr)


@unittest.skipUnless(os.environ.get('ARC_LEARNING_NEURAL_TESTS') == '1', 'explicit actual tiny-neural CPU validation')
class NeuralSessionTests(unittest.TestCase):
    def test_two_tasks_complete_owner_seal_score_archive(self):
        self.run_two_task_session(wrapped=False)

    def test_two_tasks_complete_through_trusted_offline_launcher(self):
        self.run_two_task_session(wrapped=True)

    def run_two_task_session(self, *, wrapped):
        root_parent = Path(os.environ.get('ARC_LEARNING_TEST_OUTPUT', tempfile.gettempdir()))
        root_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='learning-session-', dir=root_parent) as tmp:
            root = Path(tmp); assets = make_assets(root)
            training = root / 'training-fixture.json'
            tasks = fixture_tasks()
            atomic_json(training, {'synthetic_test_only': True, 'tasks': tasks}, exclusive=True)
            output = root / 'output'
            config = {'tiny_cpu': True, 'validation_mode': True,
                      'session_seconds': 7200, 'fixture_tasks': 2, 'max_new_tokens': 32, 'dev_tasks': 0,
                      'model': {'tiny_cpu': True, 'output_cap': 32}}
            started_epoch = time.time() - 2400 if wrapped else None
            if wrapped:
                launcher = root / 'offline-run.py'; launcher.write_bytes(_LAUNCHER.encode('utf-8'))
                config['python_executable'] = [sys.executable, '-I', '-B', '-S', str(launcher)]
                config['predispatch_clock'] = True
            result = run_session(output, solver_root=assets['solver_root'], evaluator_root=assets['evaluator_root'],
                solver_manifest_sha256=assets['solver_manifest_sha256'],
                evaluator_manifest_sha256=assets['evaluator_manifest_sha256'], training_root=training,
                enable_model=True, config=config, started_epoch=started_epoch)
            if result['status'] != 'COMPLETE':
                detail = (output / 'worker/stderr.txt').read_text() if (output / 'worker/stderr.txt').exists() else ''
                self.fail(str(result) + '\n' + detail)
            self.assertEqual(result['score_status'], 'SCORED')
            self.assertGreaterEqual(result['training_steps'], 2)
            if wrapped:
                clock = json.loads((output / 'session-clock.json').read_text())
                self.assertEqual(clock['started_epoch'], started_epoch)
                self.assertEqual(clock['deadline_epoch'], started_epoch + 7200)
                self.assertEqual(clock['maximum_seconds'], 7200)
                self.assertEqual(clock['origin'], 'pre-dispatch')
                self.assertEqual(result['clock'], clock)
                request = json.loads((output / 'worker/request.json').read_text())
                self.assertEqual(request['clock'], clock)
                self.assertLess(request['parent_bootstrap_seconds'], 1800)
            owner = json.loads((output / 'worker/result.json').read_bytes())
            self.assertEqual(len(owner['results']), 2)
            self.assertFalse(owner['production_model'])
            self.assertEqual(owner['prediction_origin'], 'synthetic_cpu')
            self.assertEqual(owner['pending_work'], {})
            self.assertNotEqual(owner['stages']['global_sft']['adapter_before_sha256'],
                                owner['stages']['global_sft']['adapter_after_sha256'])
            scored = json.loads((output / 'evaluation/public-summary.json').read_bytes())
            self.assertEqual((scored['tasks'], scored['tests']), (120, 167))
            self.assertEqual(scored['prediction_origin'], 'synthetic_cpu')
            self.assertFalse(scored['competition_gpu_equivalent'])
            closure = json.loads((output / 'owner-closure.json').read_bytes())
            self.assertTrue(closure['graceful'])
            self.assertTrue(closure['process_tree_proof']['closed'])
            self.assertTrue(closure['process_tree_proof']['ownership_complete'])
            archive = Path(result['export']['archive']['path'])
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), result['export']['archive']['sha256'])
            # Preserve compact evidence only if an explicit receipt destination was configured.
            if os.environ.get('ARC_LEARNING_RECEIPT_DIR'):
                target = Path(os.environ['ARC_LEARNING_RECEIPT_DIR']); target.mkdir(parents=True, exist_ok=True)
                name = 'ACTUAL-TINY-WRAPPED-SESSION.json' if wrapped else 'ACTUAL-TINY-SESSION.json'
                atomic_json(target / name, {'result': result,
                    'stages': owner['stages'], 'closure': closure, 'tasks_observed': len(owner['results']),
                    'synthetic_only': True, 'actual_neural_training': True}, exclusive=True)


if __name__ == '__main__': unittest.main()

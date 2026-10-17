"""Literal CPU subprocess fixtures for probe diagnostics, never native imports."""
from tests.platform_requirements import requires_linux
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from tools.nvarc_probe_bootstrap import finalize
from tools.nvarc_process_supervisor import supervise

ROOT = Path(__file__).resolve().parents[1]


@requires_linux('Real bootstrap children require Linux process groups, procfs ownership and killpg cleanup')
class ProbeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / 'stage4-e10-probe-literal-diagnostics'
        (self.root / 'tools').mkdir(parents=True)
        shutil.copyfile(ROOT / 'tools/nvarc_probe_bootstrap.py', self.root / 'tools/nvarc_probe_bootstrap.py')
        self.screen = b'{"payload_sha256":{},"screen_id":"stage4-e10-probe-literal-diagnostics"}'
        (self.root / 'screen.json').write_bytes(self.screen)
        self.plan_sha256 = hashlib.sha256(self.screen).hexdigest()
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0',
                        PYTHONPATH=str(ROOT), CUDA_VISIBLE_DEVICES='')

    def tearDown(self):
        self.temporary.cleanup()

    def run_entry(self, literal, *, total_seconds=3, limit=65536):
        (self.root / 'tools/nvarc_e10_probe.py').write_text(literal)
        return supervise([sys.executable, '-B', '-S', str(self.root / 'tools/nvarc_probe_bootstrap.py'),
            '--root', str(self.root)], env=self.env, cwd=self.root, started=time.monotonic(),
            total_seconds=total_seconds, cleanup_seconds=.3, capture_path=self.root / 'coordinator-output.log',
            maximum_capture_bytes=limit)

    def finish(self, observation):
        return finalize(self.root, observation, self.plan_sha256)

    def test_uncaught_missing_import_is_visible_and_retained_without_success(self):
        observation = self.run_entry('import irisx_literal_missing_module\n')
        self.assertEqual(observation['returncode'], 1)
        self.assertFalse(observation['timed_out'])
        self.assertTrue(observation['confirmed_stopped'])
        receipt = json.loads((self.root / 'bootstrap-failure.json').read_bytes())
        self.assertEqual(receipt['type'], 'ModuleNotFoundError')
        self.assertIn('irisx_literal_missing_module', receipt['traceback'])
        result = self.finish(observation)
        self.assertIn('ModuleNotFoundError', result['coordinator_diagnostic_excerpt'])
        self.assertTrue(result['diagnostic_only_archive_created'])
        with zipfile.ZipFile(self.root.with_suffix('.zip')) as archive:
            self.assertEqual(archive.read('screen.json'), self.screen)
            marker = json.loads(archive.read('diagnostic-only.json'))
            self.assertFalse(marker['complete_runtime_evidence'])
            self.assertFalse(marker['promotion'])
            self.assertEqual(marker['outcome'], 'failed')

    def test_actual_bad_owner_guard_failure_is_retained(self):
        observation = self.run_entry('import signal\nfrom tools.nvarc_public_eval import install_owner_guard\n'
            'install_owner_guard(2147483647, signal.SIGTERM)\n')
        self.assertEqual(observation['returncode'], 1)
        self.assertIn('live expected Linux owner required', self.finish(observation)['coordinator_diagnostic_excerpt'])

    def test_actual_stale_admission_failure_is_retained(self):
        # Literal independent source-gate fixture. There is no provider snapshot,
        # dependency directory, native import, model or real admission here.
        admission = {'format': 'irisx/stage4-native-probe-resource-admission-v2',
            'probe_id': 'stage4-e10-probe-literal-diagnostics', 'paid_usd_ceiling': 0,
            'quota_hours_available': 3, 'allocated_gpu_hours_per_quota_hour': 1,
            'quota_observed_at': '2000-01-01T00:00:00+00:00', 'provider_session_seconds': 1800,
            'private': True, 'internet': False, 'rules_materials_review_ref': 'literal CPU test only',
            'current_resource_reconciliation': {'quota_snapshot_sha256': 'a'*64,
                'provider_reserved_seconds': 0, 'campaign_pending_actions': 0,
                'historical_sessions_terminal_verified': False,
                'scope': 'current-provider-quota-and-local-campaign-only'}}
        source = 'from tools.stage_nvarc_e10_probe import validate_resource\n'
        source += 'validate_resource(' + repr(admission) + ', {"screen_id":"stage4-e10-probe-literal-diagnostics"})\n'
        observation = self.run_entry(source)
        self.assertEqual(observation['returncode'], 1)
        self.assertIn('quota observation must be current', self.finish(observation)['coordinator_diagnostic_excerpt'])

    def test_capture_is_bounded_for_unterminated_output_and_preserves_last_traceback(self):
        observation = self.run_entry('import os\nfor _ in range(32): os.write(1, b"x"*8192)\n'
            'raise RuntimeError("literal final marker")\n', limit=4096)
        capture = observation['output_capture']
        self.assertTrue(capture['truncated'])
        self.assertEqual(capture['bytes_retained'], 4096)
        self.assertGreater(capture['bytes_received'], 4096)
        self.assertIn('literal final marker', (self.root / 'coordinator-output.log').read_text())

    def test_silent_and_continuous_output_children_still_hit_deadline(self):
        for literal in ('import time\ntime.sleep(30)\n',
                'import os\nwhile True: os.write(1,b"x"*8192)\n'):
            with self.subTest(literal=literal):
                output = self.root / 'coordinator-output.log'
                if output.exists(): output.unlink()
                failure = self.root / 'bootstrap-failure.json'
                if failure.exists(): failure.unlink()
                started = time.monotonic()
                observation = self.run_entry(literal, total_seconds=.8, limit=4096)
                self.assertTrue(observation['timed_out'])
                self.assertTrue(observation['confirmed_stopped'])
                self.assertLess(time.monotonic() - started, 1.5)
                self.assertLessEqual(output.stat().st_size, 4096)

    def test_success_and_failed_worker_uncertainty_never_create_fallback(self):
        observation = self.run_entry('raise SystemExit(0)\n')
        self.assertEqual(observation['returncode'], 0)
        self.assertFalse((self.root / 'bootstrap-failure.json').exists())
        result = self.finish(observation)
        self.assertFalse(result['diagnostic_only_archive_created'])
        (self.root / 'workers').mkdir()
        # New finalization calls are not allowed to rewrite their first receipt.
        result = self.finish({**observation, 'returncode': 1})
        self.assertFalse(result['diagnostic_only_archive_created'])
        self.assertIn('fallback_refused', result)
        self.assertFalse(self.root.with_suffix('.zip').exists())

    def test_existing_zip_and_capture_are_never_overwritten(self):
        archive = self.root.with_suffix('.zip'); archive.write_bytes(b'literal immutable prior ZIP')
        output = self.root / 'coordinator-output.log'; output.write_bytes(b'literal prior log')
        observation = self.run_entry('raise RuntimeError("new failure")\n')
        self.assertEqual(observation['returncode'], 1)
        self.assertFalse(observation['output_capture']['written'])
        self.assertEqual(output.read_bytes(), b'literal prior log')
        result = self.finish(observation)
        self.assertTrue(result['existing_archive_preserved'])
        self.assertEqual(archive.read_bytes(), b'literal immutable prior ZIP')

    def test_unconfirmed_stop_and_wrong_plan_refuse_fallback(self):
        observation = self.run_entry('raise RuntimeError("literal")\n')
        result = self.finish({**observation, 'confirmed_stopped': False})
        self.assertFalse(result['diagnostic_only_archive_created'])
        result = finalize(self.root, observation, '0'*64)
        self.assertFalse(result['diagnostic_only_archive_created'])
        self.assertTrue(any('exact immutable' in item for item in result['diagnostic_errors']))

    def test_post_admission_failure_requires_explicit_cleanup_even_without_worker_directory(self):
        observation = self.run_entry('from pathlib import Path\n'
            'Path("coordinator-admitted.json").write_text("{}")\n'
            'raise RuntimeError("literal admitted failure")\n')
        result = self.finish(observation)
        self.assertFalse(result['diagnostic_only_archive_created'])
        self.assertIn('fallback_refused', result)

    def test_live_cpu_worker_without_terminal_prevents_fallback(self):
        observation = self.run_entry('raise RuntimeError("literal parent failure")\n')
        (self.root / 'workers').mkdir()
        child = subprocess.Popen([sys.executable, '-B', '-S', '-c', 'import time;time.sleep(30)'],
            env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.assertIsNone(child.poll())
            result = self.finish(observation)
            self.assertFalse(result['diagnostic_only_archive_created'])
            self.assertIn('fallback_refused', result)
        finally:
            child.kill(); child.wait(timeout=3)

    def test_fallback_retains_bounded_terminal_and_selected_byte_failure(self):
        observation = self.run_entry('raise RuntimeError("literal")\n')
        (self.root / 'coordinator-admitted.json').write_text('{}')
        (self.root / 'workers').mkdir()
        terminal = {'outcome': 'failed', 'errors': [{'message': 'literal selected byte failure'}],
            'cleanup': {'all_producers_stopped': True}, 'correctness_scored': False}
        receipt = {'outcome': 'failed', 'error': {'message': 'literal digest mismatch'}}
        (self.root / 'terminal.json').write_text(json.dumps(terminal))
        (self.root / 'dependency-readproof-receipt.json').write_text(json.dumps(receipt))
        result = self.finish(observation)
        self.assertTrue(result['diagnostic_only_archive_created'])
        with zipfile.ZipFile(self.root.with_suffix('.zip')) as archive:
            self.assertEqual(json.loads(archive.read('terminal.json')), terminal)
            self.assertEqual(json.loads(archive.read('dependency-readproof-receipt.json')), receipt)


if __name__ == '__main__':
    unittest.main()

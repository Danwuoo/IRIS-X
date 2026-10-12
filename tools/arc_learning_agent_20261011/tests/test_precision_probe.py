import builtins
import copy
import os
from pathlib import Path
import tempfile
from dataclasses import replace
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from tools.arc_learning_agent_20261011.precision_probe import (
    ProbeConfig, ProbeUnavailable, _bounded_subprocess, _execute_probe,
    quantize_e4m3_reference, run_probe, _validate_child_receipt, _result,
)


class FakeBackend:
    def __init__(self, config):
        self.config = config or ProbeConfig(True)
        self.cleanup_count = 0
        self.measured = []
        self.runtime = {'test_only': True}

    def discover(self):
        return {'available': True, 'test_only': True, 'cuda_observed': True,
                'recipe': 'per_tensor_delayed', 'fp8_runtime_check': {'supported': True},
                'distributions': {'torch': 'test-only'}, 'torch': 'test-only'}

    def measure(self, precision):
        self.measured.append(precision)
        return {'measurement_label': 'TE_PER_TENSOR_FP8_FWD_BWD' if precision == 'fp8' else 'TE_BF16_FWD_BWD',
                'fp8_executed': precision == 'fp8', 'fallback_used': False,
                'finite': True, 'loss': 1.0, 'elapsed_seconds': 0.001, 'steps': self.config.steps,
                'memory_scope': 'CPU TEST DOUBLE ONLY',
                'calibration': {'measurement_label': ('BF16_DELAYED_SCALING_CALIBRATION_NOT_FP8_EXECUTION'
                                                     if precision == 'fp8' else 'NOT_APPLICABLE_BF16_REFERENCE'),
                                'steps': self.config.calibration_steps if precision == 'fp8' else 0,
                                'elapsed_seconds': 0.001 if precision == 'fp8' else 0.,
                                'statistics_collected': precision == 'fp8'},
                'peak_allocated_bytes': 42, 'peak_reserved_bytes': 64,
                'snapshots': {key: [1.0, 2.0] for key in ('output', 'weight_grad', 'input_grad')}}

    def cleanup(self):
        self.cleanup_count += 1


class PrecisionProbeTests(unittest.TestCase):
    def test_default_inert_does_not_import_torch_or_start_process(self):
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.startswith(('torch', 'transformer_engine')):
                self.fail('inert probe imported a CUDA framework')
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', guarded), patch('subprocess.Popen') as process:
            result = run_probe()
        process.assert_not_called()
        self.assertEqual(result['status'], 'NOT_RUN')
        self.assertFalse(result['fp8_executed'])

    def test_real_default_cli_stays_inert(self):
        p = subprocess.run([sys.executable, '-m', 'tools.arc_learning_agent_20261011.precision_probe'],
                           text=True, capture_output=True, check=True, timeout=10)
        result = json.loads(p.stdout)
        self.assertEqual(result['status'], 'NOT_RUN')
        self.assertNotIn('runtime', result)

    def test_scope_and_recipe_refused_before_backend(self):
        for config, expected in ((ProbeConfig(True, scope='whole_model_training'), 'REFUSED'),
                                 (ProbeConfig(True, recipe='mxfp8'), 'UNSUPPORTED')):
            with patch('subprocess.Popen') as process:
                self.assertEqual(run_probe(config)['status'], expected)
            process.assert_not_called()

    def test_no_cuda_explicit_not_run(self):
        backend = FakeBackend(None)
        backend.discover = lambda: {'available': False, 'reason': 'No CUDA device available'}
        result = _execute_probe(ProbeConfig(True), lambda c: backend)
        self.assertEqual(result['status'], 'NOT_RUN')
        self.assertFalse(result['fp8_executed'])
        self.assertEqual(backend.measured, [])
        self.assertEqual(backend.cleanup_count, 1)

    def test_success_comparison_is_microprobe_only(self):
        backend = FakeBackend(None)
        result = _execute_probe(ProbeConfig(True), lambda c: backend)
        self.assertEqual(result['status'], 'MEASURED_MICROPROBE_PASS')
        self.assertTrue(result['fp8_executed'])
        self.assertFalse(result['whole_model_admitted'])
        self.assertFalse(result['deployment_admitted'])
        self.assertEqual(backend.measured, ['bf16', 'fp8'])
        self.assertEqual(backend.cleanup_count, 3)
        self.assertEqual(result['comparison']['errors']['weight_grad']['relative_l2'], 0)
        self.assertNotIn('snapshots', result['measurements']['fp8'])
        json.dumps(result, allow_nan=False)

    def test_unsupported_kernel_never_falls_back(self):
        backend = FakeBackend(None)
        def unavailable():
            raise ProbeUnavailable('cuBLASLt/kernel unavailable')
        backend.discover = unavailable
        result = _execute_probe(ProbeConfig(True), lambda c: backend)
        self.assertEqual(result['status'], 'UNSUPPORTED')
        self.assertFalse(result['fp8_executed'])
        self.assertEqual(backend.measured, [])
        self.assertEqual(backend.cleanup_count, 1)

    def test_oom_cleans_up_and_preserves_baseline(self):
        backend = FakeBackend(None)
        measure = backend.measure
        def failing(precision):
            if precision == 'fp8':
                raise RuntimeError('CUDA out of memory')
            return measure(precision)
        backend.measure = failing
        result = _execute_probe(ProbeConfig(True), lambda c: backend)
        self.assertEqual(result['status'], 'OOM')
        self.assertIn('bf16', result['measurements'])
        self.assertFalse(result['fp8_executed'])
        self.assertEqual(backend.cleanup_count, 3)

    def test_bf16_fallback_is_explicit_failure(self):
        backend = FakeBackend(None)
        measure = backend.measure
        def fallback(precision):
            result = measure(precision)
            if precision == 'fp8':
                result.update(fp8_executed=False, fallback_used=True, measurement_label='BF16_FALLBACK')
            return result
        backend.measure = fallback
        result = _execute_probe(ProbeConfig(True), lambda c: backend)
        self.assertEqual(result['status'], 'UNSUPPORTED')
        self.assertTrue(result['fallback_used'])
        self.assertFalse(result['fp8_executed'])
        self.assertIn('fallback', result['reason'])

    def test_explicit_fallback_failure_survives_ipc_without_fp8_credit(self):
        config = ProbeConfig(True)
        backend = FakeBackend(config)
        measure = backend.measure
        def fallback(precision):
            result = measure(precision)
            if precision == 'fp8':
                result.update(fp8_executed=False, fallback_used=True, measurement_label='BF16_FALLBACK')
            return result
        backend.measure = fallback
        fixture = _execute_probe(config, lambda c: backend)
        _validate_child_receipt(fixture, config)
        worker = 'print("PRECISION_PROBE_RESULT=" + ' + repr(json.dumps(fixture)) + ')'
        result = _bounded_subprocess(config, [sys.executable, '-I', '-c', worker])
        self.assertEqual(result['status'], 'UNSUPPORTED', result)
        self.assertTrue(result['fallback_used'])
        self.assertFalse(result['fp8_executed'])
        self.assertIn('fallback', result['reason'])
        self.assertTrue(result['cleanup']['owned_tree_closed'])
        fixture['status'] = 'MEASURED_MICROPROBE_PASS'
        with self.assertRaises(ValueError):
            _validate_child_receipt(fixture, config)

    def test_nonfinite_and_error_tolerances_fail(self):
        for nonfinite in (False, True):
            backend = FakeBackend(None)
            measure = backend.measure
            def bad(precision):
                result = measure(precision)
                if precision == 'fp8':
                    result['snapshots']['weight_grad'] = [float('nan'), 2.] if nonfinite else [5., 6.]
                    result['finite'] = not nonfinite
                return result
            backend.measure = bad
            result = _execute_probe(ProbeConfig(True), lambda c: backend)
            self.assertEqual(result['status'], 'NUMERICAL_FAILURE')
            json.dumps(result, allow_nan=False)

    def test_hard_subprocess_timeout_kills_and_reaps_cpu_child(self):
        result = _bounded_subprocess(ProbeConfig(True, timeout_seconds=.1),
                                     [sys.executable, '-c', 'import time; time.sleep(10)'])
        self.assertEqual(result['status'], 'TIMEOUT')
        self.assertTrue(result['cleanup']['process_reaped'])
        self.assertLess(result['elapsed_wall_seconds'], 3)

    def test_bad_child_receipt_and_nonzero_exit(self):
        for script in ('print("not a receipt")', 'raise SystemExit(3)'):
            result = _bounded_subprocess(ProbeConfig(True), [sys.executable, '-c', script])
            self.assertEqual(result['status'], 'ERROR')

    def test_shape_steps_and_wall_bounds(self):
        for kwargs in ({'rows': 17}, {'steps': 0}, {'steps': 5}, {'in_features': 1024},
                       {'calibration_steps': 0}, {'enable_gpu_probe': 1},
                       {'timeout_seconds': float('nan')}, {'timeout_seconds': 121}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_probe(replace(ProbeConfig(), **kwargs))

    def test_actual_cpu_quantization_reference_and_calibration(self):
        values = [0., 1., 1.1, -1.1, 448., -448., 0.001953125]
        result = quantize_e4m3_reference(values, calibration_amax=448.)
        self.assertEqual(result['scale'], 1.)
        self.assertEqual(result['quantized_dequantized'], [0., 1., 1.125, -1.125, 448., -448., 0.001953125])
        self.assertFalse(result['fp8_executed'])
        self.assertIn('CPU_E4M3_REFERENCE', result['measurement_label'])
        clipped = quantize_e4m3_reference([448., 900.], calibration_amax=448.)
        self.assertEqual(clipped['clipped_values'], 1)
        self.assertEqual(clipped['quantized_dequantized'], [448., 448.])
        self.assertEqual(quantize_e4m3_reference([0., 0.])['error']['relative_l2'], 0.)
        for values in ([], [float('nan')]):
            with self.assertRaises(ValueError):
                quantize_e4m3_reference(values)


    @unittest.skipUnless(sys.platform == 'linux', 'Linux owned-tree lifecycle')
    def test_every_exit_closes_same_session_and_detached_descendants(self):
        from tools.arc_learning_agent_20261011 import process_guard as pg
        for detached in (False, True):
            for exit_kind in ('normal', 'error', 'timeout'):
                with self.subTest(detached=detached, exit_kind=exit_kind), tempfile.TemporaryDirectory() as tmp:
                    marker = Path(tmp) / 'leaf.json'
                    leaf = ('import os,time,json; from pathlib import Path; '
                            f'Path({str(marker)!r}).write_text(json.dumps({{"pid":os.getpid()}})); '
                            'time.sleep(30)')
                    # Leave CPU launch headroom under concurrently running validation.
                    # The worker explicitly waits for leaf readiness before its exit.
                    config = ProbeConfig(True, timeout_seconds=5.)
                    receipt = _result(config, 'NOT_RUN', 'CPU lifecycle fixture only')
                    ending = ('time.sleep(30)' if exit_kind == 'timeout' else
                              'raise SystemExit(7)' if exit_kind == 'error' else
                              f'print("PRECISION_PROBE_RESULT=" + {json.dumps(receipt)!r})')
                    worker = ('import subprocess,sys,time; from pathlib import Path; '
                              f'subprocess.Popen([sys.executable,"-I","-c",{leaf!r}],start_new_session={detached!r}); '
                              f'path=Path({str(marker)!r})\n'
                              'while not path.exists(): time.sleep(.001)\n' + ending)
                    result = _bounded_subprocess(config, [sys.executable, '-I', '-c', worker])
                    self.assertEqual(result['status'], 'TIMEOUT' if exit_kind == 'timeout' else 'ERROR', result)
                    proof = result['cleanup']['closure_proof']
                    self.assertTrue(result['cleanup']['owned_tree_closed'], result)
                    self.assertTrue(pg.verify_closed_proof(proof))
                    self.assertTrue(marker.is_file(), 'bounded fixture did not reach descendant readiness')
                    leaf_pid = json.loads(marker.read_text())['pid']
                    identity = next(row for row in proof['owned_identities'] if row['pid'] == leaf_pid)
                    self.assertFalse(pg._same(pg._read_process(leaf_pid), identity))
                    self.assertTrue(proof['forced'])

    @unittest.skipUnless(sys.platform == 'linux', 'Linux owned-tree lifecycle')
    def test_detached_double_fork_closed_and_unrelated_child_preserved(self):
        from tools.arc_learning_agent_20261011 import process_guard as pg
        unrelated = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(30)'])
        try:
            with tempfile.TemporaryDirectory() as tmp:
                marker = Path(tmp) / 'orphan'
                worker = ("import os,time; from pathlib import Path\n"
                          "if os.fork() == 0:\n"
                          " os.setsid()\n"
                          " if os.fork() != 0: os._exit(0)\n"
                          f" Path({str(marker)!r}).write_text(str(os.getpid()))\n"
                          " time.sleep(30)\n"
                          " os._exit(0)\n"
                          f"while not Path({str(marker)!r}).exists(): time.sleep(.001)\n")
                result = _bounded_subprocess(ProbeConfig(True, timeout_seconds=5),
                                             [sys.executable, '-I', '-c', worker])
                self.assertEqual(result['status'], 'ERROR', result)
                proof = result['cleanup']['closure_proof']
                self.assertTrue(pg.verify_closed_proof(proof))
                self.assertIn(int(marker.read_text()), [row['pid'] for row in proof['owned_identities']])
                self.assertNotIn(unrelated.pid, [row['pid'] for row in proof['owned_identities']])
                self.assertIsNone(unrelated.poll())
        finally:
            unrelated.kill()
            unrelated.wait(timeout=5)

    def test_unsupported_lifecycle_platform_fails_before_spawn(self):
        with patch('tools.arc_learning_agent_20261011.process_guard._require_linux',
                   side_effect=RuntimeError('pidfd unavailable')), patch('subprocess.Popen') as spawn:
            result = _bounded_subprocess(ProbeConfig(True), [sys.executable, '-c', 'pass'])
        self.assertEqual(result['status'], 'UNSUPPORTED')
        self.assertFalse(result['cleanup']['process_started'])
        spawn.assert_not_called()

    def test_valid_receipt_has_fresh_owned_closure(self):
        config = ProbeConfig(True)
        fixture = _result(config, 'NOT_RUN', 'CPU-only fixture')
        worker = 'print("PRECISION_PROBE_RESULT=" + ' + repr(json.dumps(fixture)) + ')'
        result = _bounded_subprocess(config, [sys.executable, '-I', '-c', worker])
        self.assertEqual(result['status'], 'NOT_RUN', result)
        self.assertTrue(result['cleanup']['owned_tree_closed'])
        self.assertFalse(result['cleanup']['closure_proof']['forced'])

    def test_strict_receipt_rejects_impossible_or_nonfinite_claims(self):
        config = ProbeConfig(True)
        good = _execute_probe(config, FakeBackend)
        _validate_child_receipt(good, config)
        mutations = [
            lambda r: r.update(fp8_executed=False),
            lambda r: r.update(whole_model_admitted=True),
            lambda r: r.update(deployment_admitted=True),
            lambda r: r.update(fallback_used=True),
            lambda r: r.pop('config'),
            lambda r: r['config'].update(seed=1),
            lambda r: r['measurements'].pop('fp8'),
            lambda r: r['measurements']['fp8'].update(elapsed_seconds=float('nan')),
            lambda r: r['measurements']['fp8'].update(peak_allocated_bytes=-1),
            lambda r: r['measurements']['fp8'].update(steps=1),
            lambda r: r['comparison']['errors'].pop('weight_grad'),
            lambda r: r['comparison']['errors']['input_grad'].update(relative_l2=.9),
            lambda r: r['runtime'].update(cuda_observed=False),
            lambda r: r['runtime'].update(recipe='per_tensor_current'),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(good)
            mutate(bad)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                _validate_child_receipt(bad, config)
        bad = copy.deepcopy(good)
        bad['fp8_executed'] = False
        worker = 'print("PRECISION_PROBE_RESULT=" + ' + repr(json.dumps(bad)) + ')'
        result = _bounded_subprocess(config, [sys.executable, '-I', '-c', worker])
        self.assertEqual(result['status'], 'ERROR')
        self.assertTrue(result['cleanup']['owned_tree_closed'])

    def test_huge_integer_receipts_and_reference_inputs_are_rejected(self):
        config = ProbeConfig(True)
        bad = _execute_probe(config, FakeBackend)
        bad['measurements']['fp8'].update(peak_allocated_bytes=10**400, peak_reserved_bytes=10**401)
        with self.assertRaises(ValueError):
            _validate_child_receipt(bad, config)
        worker = 'print("PRECISION_PROBE_RESULT=" + ' + repr(json.dumps(bad)) + ')'
        result = _bounded_subprocess(config, [sys.executable, '-I', '-c', worker])
        self.assertEqual(result['status'], 'ERROR', result)
        self.assertTrue(result['cleanup']['owned_tree_closed'])
        with self.assertRaises(ValueError):
            quantize_e4m3_reference([10**400])
        with self.assertRaises(ValueError):
            quantize_e4m3_reference([1.], calibration_amax=10**400)
        with self.assertRaises(ValueError):
            run_probe(ProbeConfig(timeout_seconds=10**400))

    def test_current_scaling_warmup_is_not_persistent_calibration(self):
        config = ProbeConfig(True)
        good = _execute_probe(config, FakeBackend)
        good['runtime']['recipe'] = 'per_tensor_current'
        calibration = good['measurements']['fp8']['calibration']
        calibration.update(measurement_label='BF16_WARMUP_CURRENT_SCALING_NO_PERSISTENT_CALIBRATION',
                           statistics_collected=False)
        _validate_child_receipt(good, config)
        calibration['statistics_collected'] = True
        with self.assertRaises(ValueError):
            _validate_child_receipt(good, config)

    def test_reference_extremes_fail_explicitly_with_bounded_domain(self):
        for values in ([5e-324], [1e308, 1e307]):
            with self.assertRaisesRegex(ValueError, 'magnitude'):
                quantize_e4m3_reference(values)
        for amax in (5e-324, 1e308):
            with self.assertRaisesRegex(ValueError, 'calibration_amax'):
                quantize_e4m3_reference([1.], calibration_amax=amax)
        for values in ([1e-30, 1e30], [-1e30, 0., 1e30]):
            json.dumps(quantize_e4m3_reference(values), allow_nan=False)


if __name__ == '__main__':
    unittest.main()

"""CPU-only fake-Popen tests; no native Windows, auth, or provider proof."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client = load('recovery_observer_launch_client', 'bridge_client.py')
observer = load('recovery_observer_launch_validator', 'recovery_boot_probe.py')
CHALLENGE = 'a' * 64
SOURCES = {'recovery_boot_probe.py': 'b' * 64, 'win_runtime.py': 'c' * 64}
RUNTIME = {'python': 'd' * 64, 'base_python': 'e' * 64}


def fixture_observation(**changes):
    result = {'format': observer.FORMAT, 'ok': True, 'challenge': CHALLENGE,
        'host_install_sha256': 'f' * 64, 'last_boot_utc': '2026-10-15T08:00:00.000000Z',
        'observed_utc': '2026-10-15T09:00:00.000000Z', 'tick_count64_ms': 3600000,
        'windows_version': '10.0.26100', 'windows_build': '26100',
        'source_sha256': dict(SOURCES), 'runtime_sha256': dict(RUNTIME),
        'native_process_closure_verified': True, 'closure': dict(observer.CLOSURE),
        **observer.SAFE_FACTS}
    result.update(changes)
    return observer.canonical_bytes(result)


class FakePipe(io.BytesIO):
    def __init__(self, raw, *, broken=False):
        super().__init__(raw)
        self.broken = broken

    def read(self, count=-1):
        if self.broken:
            raise OSError('SYNTHETIC-SECRET-PATH')
        return super().read(count)


class FakePopen:
    def __init__(self, raw=None, *, stderr=b'', code=0, broken=False):
        self.stdout = FakePipe(fixture_observation() if raw is None else raw, broken=broken)
        self.stderr = FakePipe(stderr)
        self.returncode = code
        self.calls = []

    def poll(self):
        return self.returncode

    def kill(self):
        self.calls.append(('kill_proxy_only',))
        self.returncode = -9

    def wait(self, *, timeout):
        self.calls.append(('wait', timeout))
        return self.returncode


class Harness:
    def __init__(self):
        self.events = []
        self.native = {'source_root': r'C:\Synthetic\bridge', 'runtime': {
            'executable': {'sha256': RUNTIME['python']},
            'base_executable': {'sha256': RUNTIME['base_python']}}}
        self.review = {'boot_source_sha256': dict(SOURCES), 'boot_runtime_sha256': dict(RUNTIME)}
        self.binding = {'configuration': {'wsl_path': '/mnt/c/Synthetic/native-config.json', 'sha256': '1' * 64},
            'executable': {'wsl_path': '/mnt/c/Synthetic/python.exe',
                           'native_path': r'C:\Synthetic\python.exe', 'sha256': RUNTIME['python']}}
        self.configured = types.SimpleNamespace(windows_bridge=self.binding,
                                                evidence_root=Path('/synthetic/ignored-evidence'))
        self.validator = mock.Mock(side_effect=observer.validate_observation)
        self.write = mock.Mock(side_effect=self.write_new)
        self.module_loads = []
        self.verified_reads = []
        self.c = {'configured': lambda: self.configured, 'verified': self.verified,
                  'load_source_module': self.module, 'wall_bound': self.wall_bound,
                  'write_new': self.write}

    def verified(self, path, digest, *, cap):
        self.verified_reads.append((path, digest, cap))
        if path == self.binding['configuration']['wsl_path']:
            return observer.canonical_bytes(self.native)
        return b'synthetic verified public source/runtime'

    def module(self, name, path, digest):
        self.module_loads.append((name, Path(path).name, digest))
        if Path(path).name == 'protocol.py':
            return types.SimpleNamespace(strict_json=json.loads)
        if Path(path).name != 'recovery_boot_probe.py':
            raise AssertionError('unexpected module')
        return types.SimpleNamespace(validate_observation=self.validate)

    def validate(self, raw, **kwargs):
        self.events.append('validate')
        return self.validator(raw, **kwargs)

    def write_new(self, path, raw):
        self.events.append('write')
        self.written = (path, raw)
        return {'path': str(path), 'bytes': len(raw), 'sha256': '2' * 64}

    @contextlib.contextmanager
    def wall_bound(self, seconds):
        self.events.append(('wall_bound', seconds))
        yield


class ObserverLaunchTests(unittest.TestCase):
    def invoke(self, harness, process, *, clock=None):
        with contextlib.ExitStack() as stack:
            popen = stack.enter_context(mock.patch.object(client.subprocess, 'Popen', return_value=process))
            stack.enter_context(mock.patch.object(client.os, 'urandom', return_value=b'\x19' * 32))
            if clock is not None:
                stack.enter_context(mock.patch.object(client, 'time', clock))
            try:
                result = client.observe_recovery_boot(harness.c, harness.review, CHALLENGE)
            finally:
                if popen.called:
                    self.assertTrue(process.stdout.closed)
                    self.assertTrue(process.stderr.closed)
        return result, popen

    def test_success_fixed_argv_pins_validator_and_write_order(self):
        harness, process = Harness(), FakePopen()
        result, popen = self.invoke(harness, process)
        popen.assert_called_once_with([
            '/mnt/c/Synthetic/python.exe', '-I', '-B', r'C:\Synthetic\bridge\recovery_boot_probe.py',
            '--challenge', CHALLENGE, '--probe-sha256', SOURCES['recovery_boot_probe.py'],
            '--runtime-sha256', SOURCES['win_runtime.py'], '--python-sha256', RUNTIME['python'],
            '--base-python-sha256', RUNTIME['base_python'], '--timeout-seconds', '15'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False, close_fds=True, bufsize=0)
        harness.validator.assert_called_once_with(fixture_observation(), challenge=CHALLENGE,
            expected_source_sha256=SOURCES, expected_runtime_sha256=RUNTIME)
        self.assertEqual(harness.events, [('wall_bound', 20), 'validate', 'write'])
        self.assertEqual(harness.written, (Path('/synthetic/ignored-evidence') /
            ('recovery-boot-' + '19' * 32 + '.json'), fixture_observation()))
        self.assertEqual(result['bytes'], len(fixture_observation()))
        self.assertEqual(harness.verified_reads, [
            ('/mnt/c/Synthetic/native-config.json', '1' * 64, 1024**2),
            ('/mnt/c/Synthetic/bridge/recovery_boot_probe.py', SOURCES['recovery_boot_probe.py'], 1024**2),
            ('/mnt/c/Synthetic/python.exe', RUNTIME['python'], 128*1024**2)])
        self.assertEqual([(row[1], row[2]) for row in harness.module_loads],
            [('protocol.py', client.PROTOCOL_SOURCE_SHA256), ('recovery_boot_probe.py', SOURCES['recovery_boot_probe.py'])])
        self.assertEqual(process.calls, [])

    def test_nonzero_exit_never_validates_or_writes(self):
        for code in (1, 124, -9):
            harness, process = Harness(), FakePopen(code=code)
            with self.subTest(code=code), self.assertRaises(ValueError):
                self.invoke(harness, process)
            harness.validator.assert_not_called()
            harness.write.assert_not_called()

    def test_stderr_even_with_valid_stdout_never_writes(self):
        for stderr in (b'SYNTHETIC-SECRET', b'x' * 1025):
            harness, process = Harness(), FakePopen(stderr=stderr)
            with self.subTest(size=len(stderr)), self.assertRaises(ValueError) as caught:
                self.invoke(harness, process)
            self.assertNotIn('SYNTHETIC-SECRET', str(caught.exception))
            harness.validator.assert_not_called()
            harness.write.assert_not_called()

    def test_output_oversize_never_validates_or_writes(self):
        harness, process = Harness(), FakePopen(raw=b'x' * 8193)
        with self.assertRaises(ValueError):
            self.invoke(harness, process)
        harness.validator.assert_not_called()
        harness.write.assert_not_called()

    def test_pipe_read_error_never_leaks_or_writes(self):
        harness, process = Harness(), FakePopen(broken=True)
        with self.assertRaises(ValueError) as caught:
            self.invoke(harness, process)
        self.assertNotIn('SYNTHETIC-SECRET', str(caught.exception))
        harness.validator.assert_not_called()
        harness.write.assert_not_called()

    def test_validator_rejects_wrong_challenge_missing_closure_and_malformed_output(self):
        for raw in (fixture_observation(challenge='0' * 64), fixture_observation(closure=None),
                    fixture_observation(native_process_closure_verified=False),
                    fixture_observation(source_sha256={**SOURCES, 'win_runtime.py': '0' * 64}),
                    b'SYNTHETIC-SECRET\n'):
            harness, process = Harness(), FakePopen(raw=raw)
            with self.subTest(raw=raw[:20]), self.assertRaises(observer.ProbeError):
                self.invoke(harness, process)
            harness.validator.assert_called_once()
            harness.write.assert_not_called()

    def test_timeout_reaps_only_proxy_and_never_invents_evidence(self):
        harness, process = Harness(), FakePopen(code=None)
        calls = iter([0.0])
        clock = types.SimpleNamespace(monotonic=lambda: next(calls, 19.0), sleep=lambda _: None)
        with self.assertRaisesRegex(ValueError, 'observation_timeout'):
            self.invoke(harness, process, clock=clock)
        self.assertEqual(process.calls[0], ('kill_proxy_only',))
        self.assertEqual(process.calls[1][0], 'wait')
        self.assertLessEqual(process.calls[1][1], 1)
        harness.validator.assert_not_called()
        harness.write.assert_not_called()

    def test_proxy_wait_timeout_still_closes_streams_without_evidence(self):
        harness, process = Harness(), FakePopen(code=None)
        process.wait = mock.Mock(side_effect=subprocess.TimeoutExpired('fixed synthetic proxy', 1))
        calls = iter([0.0])
        clock = types.SimpleNamespace(monotonic=lambda: next(calls, 19.0), sleep=lambda _: None)
        with self.assertRaisesRegex(ValueError, 'observation_timeout'):
            self.invoke(harness, process, clock=clock)
        self.assertEqual(process.calls, [('kill_proxy_only',)])
        harness.write.assert_not_called()

    def test_proxy_kill_race_error_still_closes_streams_without_evidence(self):
        harness, process = Harness(), FakePopen(code=None)
        process.kill = mock.Mock(side_effect=OSError('synthetic proxy exit race'))
        calls = iter([0.0])
        clock = types.SimpleNamespace(monotonic=lambda: next(calls, 19.0), sleep=lambda _: None)
        with self.assertRaises(OSError):
            self.invoke(harness, process, clock=clock)
        process.kill.assert_called_once()
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stderr.closed)
        harness.validator.assert_not_called()
        harness.write.assert_not_called()

    def test_binding_failure_prevents_proxy_launch(self):
        cases = [('sources', 'win_runtime.py'), ('runtime', 'base_python'), ('mismatch', 'python')]
        for mode, key in cases:
            harness = Harness()
            if mode == 'sources':
                del harness.review['boot_source_sha256'][key]
            elif mode == 'runtime':
                del harness.review['boot_runtime_sha256'][key]
            else:
                harness.native['runtime']['executable']['sha256'] = '0' * 64
            with self.subTest(mode=mode), mock.patch.object(client.subprocess, 'Popen') as popen:
                with self.assertRaises(ValueError):
                    client.observe_recovery_boot(harness.c, harness.review, CHALLENGE)
                popen.assert_not_called()
                harness.write.assert_not_called()

    def test_source_verification_failure_prevents_proxy_launch(self):
        harness = Harness()
        harness.c['verified'] = mock.Mock(side_effect=ValueError('synthetic_source_hash_mismatch'))
        with mock.patch.object(client.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'source_hash_mismatch'):
                client.observe_recovery_boot(harness.c, harness.review, CHALLENGE)
            popen.assert_not_called()
        harness.write.assert_not_called()

    def test_invalid_challenge_precedes_any_configuration_or_launch(self):
        harness = Harness()
        harness.c['configured'] = mock.Mock(side_effect=AssertionError('must not run'))
        with self.assertRaisesRegex(ValueError, 'recovery_challenge'):
            client.observe_recovery_boot(harness.c, harness.review, 'arbitrary-command')
        harness.c['configured'].assert_not_called()
        harness.write.assert_not_called()


if __name__ == '__main__':
    unittest.main()

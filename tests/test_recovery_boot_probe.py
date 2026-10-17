"""Synthetic/mocked Linux tests only; these do NOT prove native Windows behavior."""
from tests.platform_requirements import requires_linux
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/recovery_boot_probe.py'
SPEC = importlib.util.spec_from_file_location('recovery_boot_probe_tested', SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
CHALLENGE = 'a' * 64
SOURCES = {'recovery_boot_probe.py': 'b' * 64, 'win_runtime.py': 'c' * 64}
RUNTIME = {'python': 'd' * 64, 'base_python': 'e' * 64}


def query(**changes):
    value = {'challenge': CHALLENGE, 'host_install_sha256': 'f' * 64,
             'last_boot_utc': '2026-10-15T08:00:00.000000Z',
             'windows_build': '26100', 'windows_version': '10.0.26100'}
    value.update(changes)
    return value


def observation(**changes):
    value = {'format': probe.FORMAT, 'ok': True, **query(),
             'observed_utc': '2026-10-15T09:00:00.000000Z', 'tick_count64_ms': 3600000,
             'source_sha256': dict(SOURCES), 'runtime_sha256': dict(RUNTIME),
             'native_process_closure_verified': True, 'closure': dict(probe.CLOSURE),
             **probe.SAFE_FACTS}
    value.update(changes)
    return value


def validate(value=None, *, raw=None, **kwargs):
    return probe.validate_observation(raw if raw is not None else probe.canonical_bytes(value or observation()),
        challenge=kwargs.get('challenge', CHALLENGE),
        expected_source_sha256=kwargs.get('sources', SOURCES),
        expected_runtime_sha256=kwargs.get('runtime', RUNTIME))


class PureContractTests(unittest.TestCase):
    def test_synthetic_valid_observation_roundtrip(self):
        self.assertEqual(validate(), observation())
        self.assertEqual(probe.canonical_bytes(validate()), probe.canonical_bytes(observation()))

    def test_exact_closed_schema(self):
        for value in (observation(raw_hostname='NEVER-EMIT'), observation(restart_verified=True),
                      observation(historical_status='CLOSED')):
            with self.subTest(value=value), self.assertRaisesRegex(probe.ProbeError, 'fields'):
                validate(value)
        for key in observation():
            value = observation()
            del value[key]
            with self.subTest(key=key), self.assertRaises(probe.ProbeError):
                validate(value)

    def test_wrong_challenge_and_host_digest(self):
        for value in (observation(challenge='0' * 64), observation(host_install_sha256='raw-machine-guid'),
                      observation(host_install_sha256='F' * 64), observation(host_install_sha256=True)):
            with self.subTest(value=value), self.assertRaises(probe.ProbeError):
                validate(value)

    def test_invalid_challenge_never_bootstraps(self):
        with mock.patch.object(probe, '_load_runtime') as load:
            for challenge in ('', 'A' * 64, 'a' * 63, True, ';arbitrary command', 'a' * 64 + '\n'):
                with self.subTest(challenge=challenge), self.assertRaises(probe.ProbeError):
                    probe.observe_boot(challenge, expected_source_sha256=SOURCES,
                                       expected_runtime_sha256=RUNTIME)
            load.assert_not_called()

    def test_strict_source_and_runtime_bindings(self):
        for kwargs in ({'sources': {}}, {'runtime': {}}, {'sources': {**SOURCES, 'extra.py': 'f' * 64}},
                       {'sources': {**SOURCES, 'win_runtime.py': 'f' * 64}},
                       {'runtime': {**RUNTIME, 'python': 'f' * 64}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(probe.ProbeError):
                validate(**kwargs)

    def test_output_framing_size_duplicate_and_encoding(self):
        raw = probe.canonical_bytes(observation())
        samples = [b'', raw[:-1], raw + b'\n', raw + raw, b' ' + raw,
                   b'{"x":1,"x":2}\n', b'{"x":NaN}\n', b'[]\n',
                   b'\xff\n', b'x' * (probe.OUTPUT_CAP + 1) + b'\n',
                   json.dumps(observation(), indent=2).encode() + b'\n']
        for raw in samples:
            with self.subTest(raw=raw[:30]), self.assertRaises(probe.ProbeError):
                validate(raw=raw)

    def test_timestamp_is_exact_utc_and_real_calendar(self):
        for stamp in ('2026-10-15T09:00:00Z', '2026-10-15T09:00:00.000000+00:00',
                      '2026-02-30T09:00:00.000000Z', '2026-10-15T09:00:60.000000Z',
                      '1999-10-15T09:00:00.000000Z', 'x' * 1000, None):
            with self.subTest(stamp=stamp), self.assertRaises(probe.ProbeError):
                validate(observation(observed_utc=stamp))

    def test_negative_boolean_huge_and_inconsistent_uptime(self):
        for ticks in (True, -1, 2**64, 3600000.0, '3600000', 0, 9000000):
            with self.subTest(ticks=ticks), self.assertRaises(probe.ProbeError):
                validate(observation(tick_count64_ms=ticks))
        with self.assertRaises(probe.ProbeError):
            validate(observation(observed_utc='2026-10-15T07:59:59.000000Z'))

    def test_version_build_bounded_matching_strings(self):
        for version, build in (('10.0.26100', '26101'), ('10.0.26100\n', '26100'),
                               ('10.0.26100', 26100), ('x' * 200, '1'), ('10.0.1.2', '2')):
            with self.subTest(version=version), self.assertRaises(probe.ProbeError):
                validate(observation(windows_version=version, windows_build=build))

    def test_closure_requires_exact_typed_genuine_schema(self):
        for closure in (None, {}, {**probe.CLOSURE, 'active_processes': False},
                        {**probe.CLOSURE, 'active_processes': 1},
                        {**probe.CLOSURE, 'kill_on_close': 1},
                        {**probe.CLOSURE, 'extra': 'untrusted'}):
            with self.subTest(closure=closure), self.assertRaisesRegex(probe.ProbeError, 'closure'):
                validate(observation(closure=closure))
        with self.assertRaises(probe.ProbeError):
            validate(observation(native_process_closure_verified=False))

    def test_scope_flags_are_exact_not_truthy(self):
        for key, value in (('auth_started', True), ('credential_contents_accessed', True),
                           ('network_used', 0), ('provider_calls', False), ('provider_calls', 1)):
            with self.subTest(key=key), self.assertRaisesRegex(probe.ProbeError, 'scope'):
                validate(observation(**{key: value}))

    def test_timeout_validation_before_native_access(self):
        for timeout in (True, 0, .99, 30.01, float('nan'), float('inf'), '15'):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(probe.ProbeError, 'timeout'):
                probe.observe_boot(CHALLENGE, expected_source_sha256=SOURCES,
                    expected_runtime_sha256=RUNTIME, timeout_seconds=timeout)

    def test_linux_is_never_native_acceptance(self):
        with mock.patch.object(probe.os, 'name', 'posix'), mock.patch.object(probe, '_load_runtime') as load:
            with self.assertRaisesRegex(probe.ProbeError, 'native_isolated_windows_required'):
                probe.observe_boot(CHALLENGE, expected_source_sha256=SOURCES,
                                   expected_runtime_sha256=RUNTIME)
            load.assert_not_called()


class SourceBoundaryTests(unittest.TestCase):
    def test_pinned_module_executes_exact_verified_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'runtime.py'
            raw = b'value = 123\n'
            path.write_bytes(raw)
            module = probe._load_runtime(path, hashlib.sha256(raw).hexdigest())
            self.assertEqual(module.value, 123)
            self.assertNotIn('_irisx_recovery_boot_verified_runtime', sys.modules)

    def test_wrong_source_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'runtime.py'
            path.write_text("raise AssertionError('UNTRUSTED CONTENT')\n")
            with self.assertRaisesRegex(probe.ProbeError, 'source_hash_mismatch'):
                probe._load_runtime(path, '0' * 64)

    def test_source_symlink_hardlink_empty_and_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / 'original.py'
            original.write_bytes(b'x=1\n')
            linked = root / 'link.py'
            linked.symlink_to(original)
            with self.assertRaisesRegex(probe.ProbeError, 'reparse'):
                probe._bootstrap_read(linked, 10)
            os.link(original, root / 'hardlink.py')
            with self.assertRaisesRegex(probe.ProbeError, 'file_invalid'):
                probe._bootstrap_read(original, 10)
            empty = root / 'empty.py'
            empty.write_bytes(b'')
            with self.assertRaises(probe.ProbeError):
                probe._bootstrap_read(empty, 10)
            large = root / 'large.py'
            large.write_bytes(b'x' * 11)
            with self.assertRaises(probe.ProbeError):
                probe._bootstrap_read(large, 10)

    def test_fixed_powershell_has_narrow_local_read_surface(self):
        script = probe.POWERSHELL_SCRIPT
        self.assertEqual(script.count('Get-CimInstance'), 2)
        self.assertIn('-Property LastBootUpTime,Version,BuildNumber,InstallDate', script)
        self.assertIn('-Property UUID', script)
        self.assertIn("OpenSubKey('SOFTWARE\\Microsoft\\Cryptography', $false)", script)
        self.assertIn("GetValue('MachineGuid'", script)
        self.assertIn('RegistryView]::Registry64', script)
        for forbidden in ('-ComputerName', '-CimSession', 'Invoke-CimMethod', 'Restart-Computer',
                          'Stop-Computer', 'Get-Content', 'Get-ChildItem', 'Get-WinEvent',
                          'kaggle', '$env:', 'Invoke-Expression', 'Invoke-WebRequest'):
            self.assertNotIn(forbidden, script)
        emitted = script[script.index("$result = '"):]
        for forbidden in ('$machine', '$uuid', '$material', '$installed'):
            self.assertNotIn(forbidden, emitted)
        self.assertIn('irisx/windows-host-install-v1`n$challenge`n$machine`n$uuid`n$installed`n', script)

    def test_error_messages_never_copy_untrusted_details(self):
        error = probe.ProbeError('SECRET raw hostname C:\\private\\token')
        self.assertEqual(str(error), 'boot_observation_failed')
        error = probe.ProbeError('boot_query_failed', closure={'raw': 'SECRET'})
        self.assertIsNone(error.closure)


class FakePipe:
    def __init__(self, data=b'', *, failure=False, blocking=None):
        self.data = io.BytesIO(data)
        self.written = bytearray()
        self.failure = failure
        self.blocking = blocking
        self.closed = False

    def read(self, size):
        if self.blocking is not None:
            self.blocking.wait(2)
        if self.failure:
            raise OSError('SECRET path and identity')
        return self.data.read(size)

    def write(self, data):
        if self.failure:
            raise OSError('SECRET path and identity')
        self.written.extend(data)

    def close(self):
        self.closed = True


class FakeJob:
    def __init__(self, *, output=None, stderr=b'', code=0, closure=None,
                 closure_error=False, pipe_failure=False, delayed_child=False):
        self.release = threading.Event()
        self.stdin = FakePipe()
        self.stdout = FakePipe(output if output is not None else probe.canonical_bytes(query()),
                               failure=pipe_failure, blocking=self.release if delayed_child else None)
        self.stderr = FakePipe(stderr)
        self.code = code
        self.proof = dict(probe.CLOSURE) if closure is None else closure
        self.closure_error = closure_error
        self.events = []

    def poll(self):
        return self.code

    def terminate_and_prove_empty(self, *, timeout, close_pipes):
        self.events.append(('terminate_entire_job', timeout, close_pipes))
        self.release.set()
        if self.closure_error:
            raise RuntimeError('SECRET closure OS path')
        return self.proof

    def _close_handles(self):
        self.events.append(('close_handles',))
        self.release.set()
        for pipe in (self.stdin, self.stdout, self.stderr):
            pipe.close()


class FakeParent:
    def __init__(self, dies=False):
        self.calls = 0
        self.dies = dies
        self.closed = False

    def dead(self):
        self.calls += 1
        return self.dies and self.calls > 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class OwnedQueryTests(unittest.TestCase):
    def run_query(self, job, *, dies=False, timeout=.5):
        parent = FakeParent(dies)
        factory = mock.Mock(return_value=job)
        runtime = types.SimpleNamespace(ParentWatch=lambda: parent, JobProcess=factory)
        with mock.patch.object(probe, '_system_command', return_value=(['fixed.exe'], 'fixed', {'fixed': 'only'})):
            try:
                result = probe._run_query(runtime, CHALLENGE, deadline=time.monotonic() + timeout,
                                          cleanup_reserve=.1)
            finally:
                self.assertTrue(parent.closed)
                self.assertEqual(job.events[0][0], 'terminate_entire_job')
                self.assertEqual(job.events[-1][0], 'close_handles')
                self.assertTrue(all(pipe.closed for pipe in (job.stdin, job.stdout, job.stderr)))
                factory.assert_called_once_with(['fixed.exe'], cwd='fixed', env={'fixed': 'only'})
        return result

    def test_success_proves_whole_job_closure_and_only_writes_challenge(self):
        job = FakeJob()
        raw, closure = self.run_query(job)
        self.assertEqual(raw, probe.canonical_bytes(query()))
        self.assertEqual(closure, probe.CLOSURE)
        self.assertEqual(job.stdin.written, (CHALLENGE + '\n').encode())

    def test_lingering_descendant_pipe_closed_before_success(self):
        job = FakeJob(delayed_child=True)
        raw, closure = self.run_query(job)
        self.assertEqual(closure, probe.CLOSURE)
        self.assertEqual(raw, probe.canonical_bytes(query()))
        self.assertTrue(job.release.is_set())

    def test_query_failure_retains_real_child_closure(self):
        with self.assertRaisesRegex(probe.ProbeError, 'query_failed') as caught:
            self.run_query(FakeJob(code=1))
        self.assertEqual(caught.exception.closure, probe.CLOSURE)

    def test_timeout_closes_whole_owned_job(self):
        with self.assertRaisesRegex(probe.ProbeError, 'deadline') as caught:
            self.run_query(FakeJob(code=None), timeout=.15)
        self.assertEqual(caught.exception.closure, probe.CLOSURE)

    def test_parent_death_closes_whole_owned_job(self):
        with self.assertRaisesRegex(probe.ProbeError, 'parent_dead') as caught:
            self.run_query(FakeJob(code=None), dies=True)
        self.assertEqual(caught.exception.closure, probe.CLOSURE)

    def test_oversized_output_discards_untrusted_data(self):
        with self.assertRaisesRegex(probe.ProbeError, 'output_limit') as caught:
            self.run_query(FakeJob(output=b'SECRET' * 1000))
        self.assertNotIn('SECRET', str(caught.exception))
        self.assertEqual(caught.exception.closure, probe.CLOSURE)

    def test_stderr_failure_or_any_stderr_is_not_success(self):
        for stderr in (b'SECRET', b'SECRET' * 1000):
            with self.subTest(size=len(stderr)), self.assertRaises(probe.ProbeError) as caught:
                self.run_query(FakeJob(stderr=stderr))
            self.assertNotIn('SECRET', str(caught.exception))
            self.assertEqual(caught.exception.closure, probe.CLOSURE)

    def test_pipe_failure_still_closes_job(self):
        with self.assertRaisesRegex(probe.ProbeError, 'pipe_failed') as caught:
            self.run_query(FakeJob(pipe_failure=True))
        self.assertEqual(caught.exception.closure, probe.CLOSURE)

    def test_closure_failure_or_malformed_closure_never_accepted(self):
        for job in (FakeJob(closure_error=True), FakeJob(closure={}),
                    FakeJob(closure={**probe.CLOSURE, 'active_processes': 1})):
            with self.subTest(job=job), self.assertRaisesRegex(probe.ProbeError, 'closure_unverified') as caught:
                self.run_query(job)
            self.assertIsNone(caught.exception.closure)

    def test_spawn_failure_is_sanitized_without_invented_closure(self):
        parent = FakeParent()
        win = types.SimpleNamespace(ParentWatch=lambda: parent,
            JobProcess=mock.Mock(side_effect=RuntimeError('SECRET raw host ID')))
        with mock.patch.object(probe, '_system_command', return_value=(['fixed.exe'], 'fixed', {})):
            with self.assertRaisesRegex(probe.ProbeError, '^boot_query_failed$') as caught:
                probe._run_query(win, CHALLENGE, deadline=time.monotonic() + 1, cleanup_reserve=.1)
        self.assertIsNone(caught.exception.closure)
        self.assertTrue(parent.closed)


class CliTests(unittest.TestCase):
    @requires_linux('Specifically tests the Linux CLI failure branch, not the Windows recovery implementation')
    def test_linux_cli_is_fixed_failure_with_no_traceback(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), '--challenge', CHALLENGE,
            '--probe-sha256', SOURCES['recovery_boot_probe.py'], '--runtime-sha256', SOURCES['win_runtime.py'],
            '--python-sha256', RUNTIME['python'], '--base-python-sha256', RUNTIME['base_python']],
            capture_output=True, timeout=5, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, b'')
        value = json.loads(result.stdout)
        self.assertEqual(value['reason'], 'boot_native_isolated_windows_required')
        self.assertFalse(value['native_process_closure_verified'])
        self.assertIsNone(value['closure'])
        self.assertEqual(result.stdout, probe.canonical_bytes(value))

    def test_bad_arguments_do_not_echo_paths_or_values(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), '--arbitrary-command',
                                 'SECRET-hostname-token-path'], capture_output=True, timeout=5, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, b'')
        self.assertNotIn(b'SECRET', result.stdout)
        self.assertEqual(json.loads(result.stdout)['reason'], 'boot_arguments_invalid')


class ObserveFlowTests(unittest.TestCase):
    """The full production path is mocked; no native calls occur on Linux."""
    def setup_flow(self, stack, *, raw=None, query_error=None, verify_effect=None):
        stack.enter_context(mock.patch.object(probe, 'os', types.SimpleNamespace(name='nt')))
        stack.enter_context(mock.patch.object(probe, 'sys', types.SimpleNamespace(flags=types.SimpleNamespace(
            isolated=1, dont_write_bytecode=1, ignore_environment=1))))
        stack.enter_context(mock.patch.object(probe, '_bootstrap_read', return_value=b'probe bytes'))
        source = {**SOURCES, 'recovery_boot_probe.py': hashlib.sha256(b'probe bytes').hexdigest()}
        win = object()
        load = stack.enter_context(mock.patch.object(probe, '_load_runtime', return_value=win))
        verify = stack.enter_context(mock.patch.object(probe, '_verify_bytes', side_effect=verify_effect))
        collect = stack.enter_context(mock.patch.object(probe, '_run_query',
            return_value=(raw if raw is not None else probe.canonical_bytes(query()), dict(probe.CLOSURE)),
            side_effect=query_error))
        stack.enter_context(mock.patch.object(probe, '_ticks', return_value=3600000))
        fake_datetime = mock.Mock()
        fake_datetime.now.return_value = datetime(2026, 10, 15, 9, tzinfo=timezone.utc)
        fake_datetime.strptime = datetime.strptime
        stack.enter_context(mock.patch.object(probe, 'datetime', fake_datetime))
        return source, load, verify, collect

    def observe(self, sources):
        return probe.observe_boot(CHALLENGE, expected_source_sha256=sources,
                                  expected_runtime_sha256=RUNTIME, timeout_seconds=15)

    def test_mocked_fresh_query_and_both_source_checks_on_each_call(self):
        with ExitStack() as stack:
            sources, load, verify, collect = self.setup_flow(stack)
            first, second = self.observe(sources), self.observe(sources)
            self.assertEqual(first, second)
            self.assertEqual(collect.call_count, 2)
            self.assertEqual(load.call_count, 2)
            self.assertEqual(verify.call_count, 4)
            self.assertEqual(first['source_sha256'], sources)
            self.assertEqual(first['closure'], probe.CLOSURE)

    def test_own_source_failure_precedes_runtime_execution(self):
        with ExitStack() as stack:
            sources, load, verify, collect = self.setup_flow(stack)
            sources['recovery_boot_probe.py'] = '0' * 64
            with self.assertRaisesRegex(probe.ProbeError, 'source_hash_mismatch') as caught:
                self.observe(sources)
            self.assertIsNone(caught.exception.closure)
            load.assert_not_called()
            verify.assert_not_called()
            collect.assert_not_called()

    def test_pre_source_failure_prevents_child(self):
        with ExitStack() as stack:
            sources, load, verify, collect = self.setup_flow(stack,
                verify_effect=probe.ProbeError('boot_source_hash_mismatch'))
            with self.assertRaisesRegex(probe.ProbeError, 'source_hash_mismatch') as caught:
                self.observe(sources)
            collect.assert_not_called()
            self.assertIsNone(caught.exception.closure)

    def test_post_source_failure_retains_closure(self):
        with ExitStack() as stack:
            sources, load, verify, collect = self.setup_flow(stack,
                verify_effect=[None, probe.ProbeError('boot_source_hash_mismatch')])
            with self.assertRaisesRegex(probe.ProbeError, 'source_hash_mismatch') as caught:
                self.observe(sources)
            self.assertEqual(caught.exception.closure, probe.CLOSURE)
            self.assertEqual(verify.call_count, 2)

    def test_wrong_query_challenge_and_unexpected_output_retain_closure(self):
        for raw in (probe.canonical_bytes(query(challenge='0' * 64)),
                    probe.canonical_bytes(query(raw_id='SECRET-IDENTIFIER')),
                    b'UNTRUSTED SECRET OUTPUT\n', b'x' * (probe.QUERY_CAP + 1) + b'\n'):
            with self.subTest(raw=raw[:20]), ExitStack() as stack:
                sources, load, verify, collect = self.setup_flow(stack, raw=raw)
                with self.assertRaises(probe.ProbeError) as caught:
                    self.observe(sources)
                self.assertEqual(caught.exception.closure, probe.CLOSURE)
                self.assertNotIn('SECRET', str(caught.exception))

    def test_query_timeout_preserves_native_closure_but_not_success(self):
        with ExitStack() as stack:
            sources, load, verify, collect = self.setup_flow(stack,
                query_error=probe.ProbeError('boot_deadline', closure=dict(probe.CLOSURE)))
            with self.assertRaisesRegex(probe.ProbeError, 'deadline') as caught:
                self.observe(sources)
            self.assertEqual(caught.exception.closure, probe.CLOSURE)

    def test_unexpected_error_message_is_not_returned(self):
        with ExitStack() as stack:
            sources, load, verify, collect = self.setup_flow(stack,
                query_error=OSError('SECRET original Windows username and file path'))
            with self.assertRaisesRegex(probe.ProbeError, '^boot_observation_failed$') as caught:
                self.observe(sources)
            self.assertIsNone(caught.exception.closure)

    def test_main_failure_retains_only_closure_and_fixed_facts(self):
        chunks = []
        def write(_fd, raw):
            chunks.append(raw)
            return len(raw)
        args = ['--challenge', CHALLENGE, '--probe-sha256', SOURCES['recovery_boot_probe.py'],
                '--runtime-sha256', SOURCES['win_runtime.py'], '--python-sha256', RUNTIME['python'],
                '--base-python-sha256', RUNTIME['base_python']]
        with mock.patch.object(probe, 'observe_boot', side_effect=probe.ProbeError(
                'boot_source_hash_mismatch', closure=dict(probe.CLOSURE))), \
                mock.patch.object(probe.os, 'write', side_effect=write):
            self.assertEqual(probe.main(args), 1)
        value = json.loads(b''.join(chunks))
        self.assertFalse(value['ok'])
        self.assertEqual(value['reason'], 'boot_source_hash_mismatch')
        self.assertTrue(value['native_process_closure_verified'])
        self.assertEqual(value['closure'], probe.CLOSURE)
        self.assertNotIn('host_install_sha256', value)
        self.assertNotIn('challenge', value)


if __name__ == '__main__':
    unittest.main()

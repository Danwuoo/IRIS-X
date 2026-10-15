"""Policy/ABI/mocked ordering tests. Passing on Linux is NOT native proof."""
import ctypes as C
import importlib.util
import math
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import win_runtime as wr
import win_supervisor as ws


class PolicyTests(unittest.TestCase):
    def test_non_windows_fails_without_dll_load(self):
        with mock.patch.object(wr.os, 'name', 'posix'):
            with self.assertRaisesRegex(wr.WindowsGuardError, 'native_windows_required'):
                wr.API()

    def test_accept_local_canonical_path(self):
        self.assertEqual(wr.strict_local_path('c:/Users/owner/file'), r'C:\Users\owner\file')

    def test_reject_ambiguous_or_remote_paths(self):
        for value in (r'\\host\share\file', r'\\?\C:\file', 'C:relative', '/tmp/file',
                      'C:\\a\\..\\b', 'C:\\a\\.\\b', 'C:\\a\\',
                      'C:\\a.\\b', 'C:\\a \\b', 'C:\\a:b', 'C:\\a\0b'):
            with self.subTest(value=value), self.assertRaises(wr.WindowsGuardError):
                wr.strict_local_path(value)

    def test_native_profile_only(self):
        identity = wr.Identity('S-1-5-21-1', r'C:\Users\owner')
        expected = r'C:\Users\owner\.kaggle\credentials.json'
        self.assertEqual(wr.profile_relative(expected, identity, r'.kaggle\credentials.json'), expected)
        for path in (r'D:\Users\owner\a', r'C:\Users\owner2\a', r'C:\Users\owner', r'C:\Windows\a'):
            with self.subTest(path=path), self.assertRaisesRegex(wr.WindowsGuardError, 'original_profile'):
                wr.profile_relative(path, identity)

    def test_exact_store_name(self):
        identity = wr.Identity('sid', r'C:\Users\owner')
        with self.assertRaisesRegex(wr.WindowsGuardError, 'store_path_mismatch'):
            wr.profile_relative(r'C:\Users\owner\.kaggle\other.json', identity, r'.kaggle\credentials.json')

    def test_acl_owner_and_allowlist(self):
        owner = 'S-1-5-21-1'
        entries = [(0, 0, 0x1f01ff, owner), (0, 0x10, 0x1f01ff, 'S-1-5-18'),
                   (0, 0, 0x1f01ff, 'S-1-5-32-544')]
        self.assertEqual(set(wr.validate_acl(owner, owner, entries)), {owner, 'S-1-5-18', 'S-1-5-32-544'})
        with self.assertRaisesRegex(wr.WindowsGuardError, 'owner_sid'):
            wr.validate_acl('other', owner, entries)
        with self.assertRaisesRegex(wr.WindowsGuardError, 'unapproved_allow'):
            wr.validate_acl(owner, owner, entries + [(0, 0, 1, 'S-1-1-0')])

    def test_acl_deny_not_a_grant(self):
        owner = 'owner'
        with self.assertRaisesRegex(wr.WindowsGuardError, 'owner_access_missing'):
            wr.validate_acl(owner, owner, [(1, 0, 1, owner)])
        self.assertEqual(wr.validate_acl(owner, owner, [(0, 0, 1, owner), (1, 0, 1, 'everyone')]), (owner,))

    def test_acl_inherit_only_not_current_grant(self):
        with self.assertRaisesRegex(wr.WindowsGuardError, 'owner_access_missing'):
            wr.validate_acl('owner', 'owner', [(0, 8, 1, 'owner')])

    def test_unsupported_acl_type_rejected(self):
        with self.assertRaisesRegex(wr.WindowsGuardError, 'unsupported_ace'):
            wr.validate_acl('owner', 'owner', [(5, 0, 1, 'owner')])

    def test_source_reader_rejects_credentials_before_any_native_open(self):
        with mock.patch.object(wr, 'api', side_effect=AssertionError('must not open any file')):
            for path in (r'C:\Users\owner\.kaggle\credentials.json',
                         r'C:\Users\owner\.KAGGLE\other.json', r'C:\anywhere\oauth.json',
                         r'C:\elsewhere\credentials.json'):
                with self.subTest(path=path), self.assertRaisesRegex(wr.WindowsGuardError, 'credential_source_read_forbidden'):
                    wr.read_source(path, 65536)

    def test_timeout_finite_strict_bound(self):
        for value in (True, False, 0, -1, math.nan, math.inf, -math.inf, 43200.01, '3'):
            with self.subTest(value=value), self.assertRaises(wr.WindowsGuardError):
                wr.bounded_seconds(value)
        self.assertEqual(wr.bounded_seconds(1), 1.0)

    def test_deadline_never_restarts(self):
        self.assertEqual(ws.remaining_timeout(30, 120, now=100), 20)
        self.assertEqual(ws.remaining_timeout(5, 120, now=100), 5)
        for deadline in (99, 100, 43301, math.nan, math.inf):
            with self.subTest(deadline=deadline), self.assertRaises(wr.WindowsGuardError):
                ws.remaining_timeout(30, deadline, now=100)

    def test_abi_uses_windows_fixed_width_on_linux(self):
        self.assertEqual(C.sizeof(wr.DWORD), 4)
        self.assertEqual(C.sizeof(wr.BOOL), 4)
        self.assertEqual(C.sizeof(wr.FILETIME), 8)
        self.assertEqual(C.sizeof(wr.BY_HANDLE_FILE_INFORMATION), 52)
        self.assertEqual(C.sizeof(wr.JOBOBJECT_BASIC_ACCOUNTING_INFORMATION), 48)
        self.assertEqual(C.sizeof(wr.IO_COUNTERS), 48)
        if C.sizeof(C.c_void_p) == 8:
            self.assertEqual(C.sizeof(wr.STARTUPINFOW), 104)
            self.assertEqual(C.sizeof(wr.STARTUPINFOEXW), 112)
            self.assertEqual(C.sizeof(wr.JOBOBJECT_EXTENDED_LIMIT_INFORMATION), 144)


class FakeAPI:
    def __init__(self, *, reject_job_attribute=False, member=True, resume=1):
        self.calls = []; self.next_handle = 100
        self.reject_job_attribute = reject_job_attribute
        self.member = member; self.resume = resume
        self.k = self

    def check(self, value, code):
        wr.need(value, code); return value

    def handle(self, value, code):
        wr.need(value, code); return value

    def CreateJobObjectW(self, *args):
        self.calls.append(('job',)); return 50

    def SetInformationJobObject(self, h, category, info, size):
        flags = C.cast(info, C.POINTER(wr.JOBOBJECT_EXTENDED_LIMIT_INFORMATION)).contents.BasicLimitInformation.LimitFlags
        self.calls.append(('limits', flags)); return 1

    def QueryInformationJobObject(self, h, category, info, size, written):
        if category == 9:
            C.cast(info, C.POINTER(wr.JOBOBJECT_EXTENDED_LIMIT_INFORMATION)).contents.BasicLimitInformation.LimitFlags = wr.KILL_ON_JOB_CLOSE
        elif category == 1:
            C.cast(info, C.POINTER(wr.JOBOBJECT_BASIC_ACCOUNTING_INFORMATION)).contents.ActiveProcesses = 0
        self.calls.append(('query', category)); return 1

    def CreatePipe(self, read, write, attrs, size):
        self.next_handle += 2
        C.cast(read, C.POINTER(wr.HANDLE)).contents.value = self.next_handle
        C.cast(write, C.POINTER(wr.HANDLE)).contents.value = self.next_handle + 1
        return 1

    def SetHandleInformation(self, h, mask, flags):
        self.calls.append(('inherit', h, mask, flags)); return 1

    def InitializeProcThreadAttributeList(self, attrs, count, reserved, size):
        C.cast(size, C.POINTER(wr.SIZE_T)).contents.value = 256
        return int(attrs is not None)

    def UpdateProcThreadAttribute(self, attrs, flags, key, value, size, old, out):
        self.calls.append(('attribute', key, tuple(value)))
        return not (key == wr.JOB_LIST and self.reject_job_attribute)

    def CreateProcessW(self, executable, command, psa, tsa, inherit, flags, env, cwd, startup, pi):
        self.calls.append(('create', inherit, flags))
        process = C.cast(pi, C.POINTER(wr.PROCESS_INFORMATION)).contents
        process.hProcess = 90; process.hThread = 91; process.dwProcessId = 92
        return 1

    def IsProcessInJob(self, process, job, member):
        self.calls.append(('member',))
        C.cast(member, C.POINTER(wr.BOOL)).contents.value = self.member
        return 1

    def ResumeThread(self, thread):
        self.calls.append(('resume',)); return self.resume

    def DeleteProcThreadAttributeList(self, attrs):
        self.calls.append(('delete_attributes',))

    def TerminateJobObject(self, job, code):
        self.calls.append(('terminate_job',)); return 1

    def CloseHandle(self, handle):
        self.calls.append(('close', handle)); return 1


class MockedProcessTests(unittest.TestCase):
    def test_atomic_membership_before_resume_and_zero_before_close(self):
        fake = FakeAPI()
        with mock.patch.object(wr, 'api', return_value=fake):
            job = wr.JobProcess([r'C:\Python\python.exe', '-I', 'worker.py'])
            proof = job.terminate_and_prove_empty()
        self.assertEqual(proof['active_processes'], 0)
        calls = fake.calls
        names = [c[0] for c in calls]
        create = names.index('create')
        self.assertLess(next(i for i, c in enumerate(calls) if c[:2] == ('attribute', wr.JOB_LIST)), create)
        self.assertLess(names.index('member'), names.index('resume'))
        creation = calls[create]
        self.assertTrue(creation[2] & wr.CREATE_SUSPENDED)
        self.assertFalse(creation[2] & 0x01000000)  # CREATE_BREAKAWAY_FROM_JOB
        handles = next(c[2] for c in calls if c[:2] == ('attribute', wr.HANDLE_LIST))
        self.assertNotIn(50, handles)
        self.assertEqual(calls[names.index('limits')][1], wr.KILL_ON_JOB_CLOSE)
        self.assertLess(next(i for i, c in enumerate(calls) if c == ('query', 1)),
                        next(i for i, c in enumerate(calls) if c == ('close', 50)))

    def test_no_fallback_when_atomic_job_attribute_unavailable(self):
        fake = FakeAPI(reject_job_attribute=True)
        with mock.patch.object(wr, 'api', return_value=fake):
            with self.assertRaisesRegex(wr.WindowsGuardError, 'atomic_job_unavailable'):
                wr.JobProcess([r'C:\Python\python.exe'])
        self.assertNotIn('create', [c[0] for c in fake.calls])
        self.assertIn(('close', 50), fake.calls)

    def test_resume_refused_until_verified_member(self):
        fake = FakeAPI(member=False)
        with mock.patch.object(wr, 'api', return_value=fake):
            with self.assertRaisesRegex(wr.WindowsGuardError, 'child_not_in_job'):
                wr.JobProcess([r'C:\Python\python.exe'])
        self.assertNotIn('resume', [c[0] for c in fake.calls])
        self.assertIn(('terminate_job',), fake.calls)

    def test_resume_failure_kills_job(self):
        fake = FakeAPI(resume=0xffffffff)
        with mock.patch.object(wr, 'api', return_value=fake):
            with self.assertRaisesRegex(wr.WindowsGuardError, 'child_resume_failed'):
                wr.JobProcess([r'C:\Python\python.exe'])
        self.assertIn(('terminate_job',), fake.calls)
        self.assertIn(('close', 50), fake.calls)


class NamedJobTests(unittest.TestCase):
    def test_nonce_name_binds_user_and_exact_nonce(self):
        one = wr.Identity('S-1-5-21-1', r'C:\Users\one')
        two = wr.Identity('S-1-5-21-2', r'C:\Users\two')
        self.assertNotEqual(wr._job_name('a' * 64, one), wr._job_name('a' * 64, two))
        self.assertNotEqual(wr._job_name('a' * 64, one), wr._job_name('b' * 64, one))
        with self.assertRaisesRegex(wr.WindowsGuardError, 'nonce_invalid'):
            wr._job_name('not-a-nonce', one)

    def test_worker_rejects_no_job_without_opening_handle(self):
        fake = FakeAPI(member=False)
        fake.OpenJobObjectW = mock.Mock(side_effect=AssertionError('must never open Job'))
        fake.GetCurrentProcess = lambda: 89
        with mock.patch.object(wr, 'api', return_value=fake):
            with self.assertRaisesRegex(wr.WindowsGuardError, 'job_missing'):
                wr.require_worker_job('a' * 64)
        fake.OpenJobObjectW.assert_not_called()
        self.assertFalse(any(c[0] == 'close' for c in fake.calls))

    def test_worker_uses_null_job_without_opening_or_inheriting_handle(self):
        fake = FakeAPI()
        fake.OpenJobObjectW = mock.Mock(side_effect=AssertionError('must never open Job'))
        fake.GetCurrentProcess = lambda: 89
        query = fake.QueryInformationJobObject
        def null_query(handle, *args):
            self.assertIsNone(handle)
            return query(handle, *args)
        fake.QueryInformationJobObject = null_query
        with mock.patch.object(wr, 'api', return_value=fake):
            proof = wr.require_worker_job('a' * 64)
            self.assertTrue(proof['current_job_kill_on_close'])
            self.assertEqual(proof['exact_membership_authority'], 'supervisor_before_resume')
        fake.OpenJobObjectW.assert_not_called()
        self.assertFalse(any(c[0] == 'close' for c in fake.calls))

    def test_worker_rejects_breakaway_permitted_job(self):
        fake = FakeAPI(); fake.GetCurrentProcess = lambda: 89
        for flags in (0, 0x1000, 0x0800, 0x2800, 0x3800, 0x2001, 0x3001, 0xffffffff):
            def query(handle, category, info, size, written):
                self.assertIsNone(handle)
                C.cast(info, C.POINTER(wr.JOBOBJECT_EXTENDED_LIMIT_INFORMATION)).contents.BasicLimitInformation.LimitFlags = flags
                return 1
            fake.QueryInformationJobObject = query
            with self.subTest(flags=flags), mock.patch.object(wr, 'api', return_value=fake):
                with self.assertRaisesRegex(wr.WindowsGuardError, 'limits_invalid'):
                    wr.require_worker_job('a' * 64)

    def test_immediate_launcher_job_reports_silent_breakaway_truthfully(self):
        fake = FakeAPI(); fake.GetCurrentProcess = lambda: 89
        fake.OpenJobObjectW = mock.Mock(side_effect=AssertionError('must never open Job'))
        for flags in (0x2000, 0x3000):
            def query(handle, category, info, size, written):
                self.assertIsNone(handle)
                C.cast(info, C.POINTER(wr.JOBOBJECT_EXTENDED_LIMIT_INFORMATION)).contents.BasicLimitInformation.LimitFlags = flags
                return 1
            fake.QueryInformationJobObject = query
            with self.subTest(flags=flags), mock.patch.object(wr, 'api', return_value=fake):
                proof = wr.require_worker_job('a' * 64)
            self.assertEqual(proof['current_job_limit_flags'], flags)
            self.assertEqual(proof['current_job_silent_breakaway'], flags == 0x3000)
            self.assertFalse(proof['current_job_explicit_breakaway'])
            self.assertNotIn('breakaway_permitted', proof)
        fake.OpenJobObjectW.assert_not_called()
        self.assertFalse(any(c[0] == 'close' for c in fake.calls))

    def test_duplicate_named_job_is_not_terminated(self):
        fake = FakeAPI()
        class Descriptor:
            def __init__(self, *args):
                self.attributes = wr.SECURITY_ATTRIBUTES()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        with mock.patch.object(wr, 'api', return_value=fake), mock.patch.object(wr, 'SecurityDescriptor', Descriptor), \
             mock.patch.object(wr, 'current_identity', return_value=wr.Identity('sid', r'C:\Users\one')), \
             mock.patch.object(C, 'set_last_error', create=True), \
             mock.patch.object(C, 'get_last_error', return_value=183, create=True):
            with self.assertRaisesRegex(wr.WindowsGuardError, 'nonce_reused'):
                wr.JobProcess([r'C:\Python\python.exe'], job_nonce='a' * 64)
        self.assertIn(('close', 50), fake.calls)
        self.assertNotIn(('terminate_job',), fake.calls)


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        import protocol
        self.protocol = protocol
        self.clock = [100.0, 1000.0]
        self.nonce = 'a' * 64
        self.watch = ws.CommandWatch(protocol, self.nonce, lease_epoch=2000,
            lease_monotonic=1100, monotonic=lambda: self.clock[0], wall=lambda: self.clock[1])
        self.bindings = {}

    def frame(self, kind, payload, sequence=1, digest=None):
        protocol = self.protocol
        if kind == 'request':
            digest = protocol.request_hash(payload['operation'], payload['arguments'],
                deadline_epoch=payload['deadline_epoch'], max_seconds=payload['max_seconds'])
            self.bindings[sequence] = digest
        digest = digest or self.bindings[sequence]
        raw = protocol.canonical({'protocol': protocol.PROTOCOL, 'kind': kind,
            'nonce': self.nonce, 'sequence': sequence, 'request_sha256': digest, 'payload': payload})
        return protocol.HEADER.pack(protocol.MAGIC, protocol.CONTROL, len(raw)) + raw

    def open(self):
        arguments = {'account': 'danielwuu', 'versions': {'code_predecessor': 20,
            'code': 21, 'inactive_predecessor': 39, 'inactive': 40, 'active': 41},
            'configuration_sha256': 'b' * 64, 'bridge_configuration_sha256': 'c' * 64,
            'publication_manifest_sha256': 'd' * 64, 'deadline_epoch': 2000, 'max_seconds': 1000}
        self.watch.observe('request', self.frame('request', {'operation': 'open',
            'arguments': arguments, 'deadline_epoch': 1120, 'max_seconds': 120}))

    def output(self):
        self.open()
        self.watch.observe('response', self.frame('response', {'operation': 'open', 'result': {'authenticated': True}}))
        self.watch.observe('request', self.frame('request', {'operation': 'output',
            'arguments': {'name': 'synthetic.zip', 'version': 1, 'cap': 1024,
                          'expected_bytes': None, 'expected_sha256': None},
            'deadline_epoch': 1900, 'max_seconds': 900}, sequence=2))

    def test_operation_deadline_independent_of_worker(self):
        self.open()
        self.clock[:] = [220, 1120]
        self.assertEqual(self.watch.expired(), 'operation_deadline')

    def test_request_duration_ignores_cross_os_wall_skew(self):
        for wall in (-1000000, 1000000):
            with self.subTest(wall=wall):
                self.setUp()
                self.clock[1] = wall
                self.open()
                self.assertEqual(self.watch.command_deadline, 220)
                self.clock[0] = 220
                self.assertEqual(self.watch.expired(), 'operation_deadline')

    def test_request_duration_cannot_extend_original_lease(self):
        self.clock[:] = [1090, -1000000]
        self.open()
        self.assertEqual(self.watch.command_deadline, 1100)
        self.clock[0] = 1100
        self.assertEqual(self.watch.expired(), 'deadline')

    def test_native_phase_backward_wall_jump_is_duration_and_lease_capped(self):
        for now, expected in ((100, 220), (990, 1000)):
            with self.subTest(now=now):
                self.setUp()
                self.output()
                self.clock[:] = [now, -1000000]
                self.watch.observe('response', self.frame('phase_start', {
                    'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 120,
                    'deadline_epoch': 1120}, sequence=2))
                self.assertEqual(self.watch.phase_deadline, expected)
                self.assertLessEqual(expected, self.watch.lease_deadline)

    def test_native_phase_forward_wall_jump_fails_closed(self):
        self.output()
        original = self.watch.command_deadline
        self.clock[1] = 1000000
        with self.assertRaisesRegex(wr.WindowsGuardError, 'rpc_phase_expired'):
            self.watch.observe('response', self.frame('phase_start', {
                'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 120,
                'deadline_epoch': 1120}, sequence=2))
        self.assertEqual(self.watch.command_deadline, original)
        self.assertEqual(self.watch.lease_deadline, 1100)

    def test_nested_rpc_120_inside_download_900(self):
        self.output()
        self.watch.observe('response', self.frame('phase_start', {
            'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 120,
            'deadline_epoch': 1120}, sequence=2))
        self.clock[:] = [220, 1120]
        self.assertEqual(self.watch.expired(), 'official_rpc_deadline')
        self.assertGreater(self.watch.command_deadline, self.clock[0])

    def test_phase_end_does_not_reset_command(self):
        self.output(); original = self.watch.command_deadline
        self.watch.observe('response', self.frame('phase_start', {
            'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 120,
            'deadline_epoch': 1120}, sequence=2))
        self.clock[:] = [150, 1050]
        self.watch.observe('response', self.frame('phase_end', {'phase_id': 1}, sequence=2))
        self.assertIsNone(self.watch.phase_deadline)
        self.assertEqual(self.watch.command_deadline, original)

    def test_expired_phase_cannot_be_cleared_by_late_end(self):
        self.output()
        self.watch.observe('response', self.frame('phase_start', {
            'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 120,
            'deadline_epoch': 1120}, sequence=2))
        self.clock[:] = [221, 1121]
        with self.assertRaisesRegex(wr.WindowsGuardError, 'deadline_expired'):
            self.watch.observe('response', self.frame('phase_end', {'phase_id': 1}, sequence=2))
        self.assertIsNotNone(self.watch.phase_deadline)

    def test_refresh_cannot_extend_operation(self):
        self.open(); deadline = self.watch.command_deadline
        self.clock[:] = [110, 1010]
        self.watch.observe('response', self.frame('refresh_request', {'refresh_id': 'e' * 64,
            'account': 'danielwuu', 'old_expiration_epoch': 900}))
        self.assertEqual(self.watch.command_deadline, deadline)

    def test_unfinished_phase_cannot_be_hidden_by_response(self):
        self.open()
        self.watch.observe('response', self.frame('phase_start', {'phase_id': 1,
            'kind': 'official_rpc', 'max_seconds': 120, 'deadline_epoch': 1120}))
        with self.assertRaisesRegex(wr.WindowsGuardError, 'phase_unfinished'):
            self.watch.observe('response', self.frame('response',
                {'operation': 'open', 'result': {'authenticated': True}}))

    def test_response_wrong_binding_rejected(self):
        self.open()
        with self.assertRaisesRegex(wr.WindowsGuardError, 'control_binding'):
            self.watch.observe('response', self.frame('response',
                {'operation': 'open', 'result': {'authenticated': True}}, digest='f' * 64))

    def test_partial_frame_never_marks_complete(self):
        self.open()
        self.watch.observe('response', b'IX')
        with self.assertRaises(self.protocol.ProtocolError):
            self.watch.finish('response')

    def test_duplicate_active_phase_rejected(self):
        self.output()
        frame = self.frame('phase_start', {'phase_id': 1, 'kind': 'official_rpc',
            'max_seconds': 120, 'deadline_epoch': 1120}, sequence=2)
        self.watch.observe('response', frame)
        with self.assertRaisesRegex(wr.WindowsGuardError, 'phase_replay'):
            self.watch.observe('response', frame)


class BootstrapTests(unittest.TestCase):
    def test_unbound_pin_fails_before_file_access(self):
        with self.assertRaisesRegex(RuntimeError, 'bootstrap_unbound'):
            ws._pinned_module('never_load', '/nonexistent', 'UNBOUND')

    def test_source_hash_mismatch_prevents_code_execution(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'fixture.py'
            path.write_text("raise AssertionError('must never execute')\n", encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'bootstrap_hash'):
                ws._pinned_module('never_load', path, '0' * 64)
        self.assertNotIn('never_load', sys.modules)

    def test_cli_has_no_arbitrary_worker_argv(self):
        import inspect
        source = inspect.getsource(ws.main)
        self.assertNotIn("add_argument('worker'", source)
        self.assertIn('runtime.worker_path', source)
        self.assertIn("'--config-sha'", source)


class SupervisionFailureReceiptTests(unittest.TestCase):
    """Synthetic ordering only: no native API, authentication or provider call."""
    CLOSURE = {'format': 'irisx/windows-job-closure-v1', 'active_processes': 0,
               'kill_on_close': True, 'breakaway_permitted': False,
               'atomic_job_assignment': True}

    def supervise_fixture(self, completion_error=None, closure_error=None, worker_code=0):
        events = []
        watch = mock.Mock()
        watch.expired.return_value = None
        watch.complete.side_effect = completion_error
        job = SimpleNamespace(job=1, stdout=SimpleNamespace(read=lambda: b''),
            stderr=SimpleNamespace(read=lambda: b''), poll=lambda: worker_code,
            _close_handles=lambda: events.append('handles_closed'))
        def close(**kwargs):
            events.append('closure_query')
            job.job = None
            if closure_error is not None:
                raise closure_error
            return self.CLOSURE
        job.terminate_and_prove_empty = close
        def thread(*, target, daemon):
            # Both drain relays complete synchronously. The input relay is kept
            # open; these tests never touch an actual file descriptor.
            return SimpleNamespace(start=lambda: target() if target.__name__ != 'input_relay' else None)
        parent = mock.MagicMock()
        parent.__enter__.return_value.dead.return_value = False
        with mock.patch.object(ws, 'ExclusiveMutex', return_value=mock.MagicMock()), \
             mock.patch.object(ws, 'ParentWatch', return_value=parent), \
             mock.patch.object(ws, 'JobProcess', return_value=job), \
             mock.patch.object(ws, 'CommandWatch', return_value=watch), \
             mock.patch.object(ws.threading, 'Thread', side_effect=thread):
            result = ws.supervise(['synthetic'], timeout_seconds=5,
                deadline_unix=ws.time.time() + 5, protocol=object(), nonce='a' * 64)
        return result, events, watch

    def test_completion_failure_preserves_queried_zero_and_stays_failed(self):
        for error in (wr.WindowsGuardError('windows_worker_incomplete_command'),
                      RuntimeError('secret-canary/private/path'), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                result, events, watch = self.supervise_fixture(completion_error=error)
            self.assertEqual(result.code, 124)
            self.assertEqual(result.reason, 'worker_completion_check_failed')
            self.assertIs(result.closure, self.CLOSURE)
            self.assertEqual(events, ['closure_query', 'handles_closed'])
            watch.complete.assert_called_once_with()

    def test_completed_success_and_nonzero_worker_are_unchanged(self):
        for worker_code, expected in ((0, 0), (2, 124)):
            with self.subTest(worker_code=worker_code):
                result, events, _ = self.supervise_fixture(worker_code=worker_code)
            self.assertEqual(result.code, expected)
            self.assertEqual(result.reason, 'worker_exit')
            self.assertIs(result.closure, self.CLOSURE)
            self.assertEqual(events, ['closure_query', 'handles_closed'])

    def test_failed_closure_query_cannot_be_promoted_to_receipt(self):
        with self.assertRaisesRegex(wr.WindowsGuardError, 'synthetic_closure_failed'):
            self.supervise_fixture(closure_error=wr.WindowsGuardError('synthetic_closure_failed'))

    def run_main(self, fail_stage=None, result=None, *, epoch=None, max_seconds=5, clock=None):
        import json
        from contextlib import ExitStack
        writes = []
        runtime = SimpleNamespace(source_root=str(ROOT), executable='synthetic-python',
            worker_path=str(ROOT / 'sdk_worker.py'), document={'sources': {
                'protocol.py': {'sha256': 'b' * 64}}})
        config = SimpleNamespace(load_runtime=mock.Mock(return_value=runtime),
                                 same_path=mock.Mock(return_value=True))
        canary = RuntimeError('secret-canary/private/path?access_token=hidden')
        def pinned(name, path, digest):
            if name == fail_stage:
                raise canary
            return {'win_runtime': wr, 'native_config': config, 'protocol': object()}[name]
        if fail_stage == 'runtime_verification':
            config.load_runtime.side_effect = canary
        if fail_stage == 'source_identity':
            config.same_path.return_value = False
        args = ['--config', 'synthetic.json', '--config-sha', 'c' * 64,
                '--nonce', 'a' * 64, '--deadline-epoch', str(ws.time.time() + 5 if epoch is None else epoch),
                '--max-seconds', str(max_seconds)]
        with ExitStack() as stack:
            if clock is not None:
                stack.enter_context(mock.patch.object(ws, 'time', SimpleNamespace(
                    monotonic=clock, time=mock.Mock(side_effect=AssertionError('foreign wall clock')))))
            stack.enter_context(mock.patch.object(ws, 'os', SimpleNamespace(
                name='nt', O_BINARY=0, write=lambda fd, data: writes.append((fd, data)))))
            stack.enter_context(mock.patch.object(ws.sys, 'flags', SimpleNamespace(
                isolated=1, dont_write_bytecode=1, ignore_environment=1, optimize=0)))
            stack.enter_context(mock.patch.dict(sys.modules, {'msvcrt': SimpleNamespace(setmode=lambda *a: None)}))
            stack.enter_context(mock.patch.object(ws, '_pinned_module', side_effect=pinned))
            supervision = stack.enter_context(mock.patch.object(ws, 'supervise',
                side_effect=canary if fail_stage == 'supervision' else None,
                return_value=result or ws.SupervisionResult(0, 'worker_exit', self.CLOSURE)))
            code = ws.main(args)
            self.main_supervision_call = supervision.call_args
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], 2)
        raw = writes[0][1]
        self.assertTrue(raw.endswith(b'\n'))
        self.assertEqual(raw.count(b'\n'), 1)
        self.assertNotIn(b'canary', raw)
        self.assertNotIn(b'private', raw)
        self.assertNotIn(b'access_token', raw)
        receipt = json.loads(raw)
        self.assertEqual(set(receipt), {'format', 'nonce', 'ok', 'reason', 'closure'})
        self.assertEqual(receipt['nonce'], 'a' * 64)
        return code, receipt

    def test_production_lease_uses_duration_and_same_native_worker_deadline(self):
        for epoch in (1000, 100000000000):
            with self.subTest(epoch=epoch):
                code, receipt = self.run_main(epoch=epoch, clock=mock.Mock(side_effect=[100, 103]))
                self.assertEqual(code, 0)
                self.assertTrue(receipt['ok'])
                args, kwargs = self.main_supervision_call
                command = args[0]
                self.assertEqual(float(command[command.index('--lease-monotonic') + 1]), 105)
                self.assertEqual(kwargs['lease_monotonic'], 105)
                self.assertEqual(kwargs['timeout_seconds'], 2)
                self.assertEqual(kwargs['deadline_unix'], epoch)

    def test_bootstrap_consumes_lease_without_job_or_worker_start(self):
        code, receipt = self.run_main(epoch=1000, clock=mock.Mock(side_effect=[100, 106]))
        self.assertEqual(code, 125)
        self.assertEqual(receipt['reason'], 'supervisor_worker_lease_failed')
        self.assertIsNone(self.main_supervision_call)
        self.assertIsNone(receipt['closure'])

    def test_invalid_lease_fails_before_supervision(self):
        for seconds, epoch in ((0, 1000), (43200.1, 1000), (math.inf, 1000), (5, math.nan)):
            with self.subTest(seconds=seconds, epoch=epoch):
                code, receipt = self.run_main(epoch=epoch, max_seconds=seconds,
                                              clock=lambda: 100)
                self.assertEqual(code, 125)
                self.assertEqual(receipt['reason'], 'supervisor_lease_failed')
                self.assertIsNone(self.main_supervision_call)
                self.assertIsNone(receipt['closure'])

    def test_expired_native_lease_cannot_start_job(self):
        with mock.patch.object(ws, 'JobProcess') as job, \
             mock.patch.object(ws.time, 'monotonic', return_value=100):
            with self.assertRaisesRegex(wr.WindowsGuardError, 'bootstrap_deadline'):
                ws.supervise(['synthetic'], timeout_seconds=5, deadline_unix=1000000,
                             lease_monotonic=99)
            job.assert_not_called()

    def test_main_emits_fixed_failure_stage_without_exception_data(self):
        for stage, reason in (('win_runtime', 'supervisor_runtime_bootstrap_failed'),
                ('native_config', 'supervisor_config_bootstrap_failed'),
                ('runtime_verification', 'supervisor_runtime_verification_failed'),
                ('source_identity', 'supervisor_source_identity_failed'),
                ('protocol', 'supervisor_protocol_bootstrap_failed'),
                ('supervision', 'supervisor_supervision_failed')):
            with self.subTest(stage=stage):
                code, receipt = self.run_main(fail_stage=stage)
            self.assertEqual(code, 125)
            self.assertEqual(receipt['reason'], reason)
            self.assertFalse(receipt['ok'])
            self.assertIsNone(receipt['closure'])

    def test_main_preserves_failed_completion_result_and_closure(self):
        code, receipt = self.run_main(result=ws.SupervisionResult(
            124, 'worker_completion_check_failed', self.CLOSURE))
        self.assertEqual(code, 124)
        self.assertFalse(receipt['ok'])
        self.assertEqual(receipt['reason'], 'worker_completion_check_failed')
        self.assertEqual(receipt['closure'], self.CLOSURE)

    def test_main_success_receipt_is_unchanged(self):
        code, receipt = self.run_main()
        self.assertEqual(code, 0)
        self.assertTrue(receipt['ok'])
        self.assertEqual(receipt['reason'], 'worker_exit')
        self.assertEqual(receipt['closure'], self.CLOSURE)

class ProbeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        import native_probe
        self.probe = native_probe
        self.probe.DIAGNOSTICS.clear()

    def tearDown(self):
        self.probe.DIAGNOSTICS.clear()

    def test_exception_does_not_export_message_or_private_path(self):
        import json
        result = self.probe.exception_facts(FileNotFoundError(2, 'private secret', '/private/credential-path'))
        self.assertEqual(result, {'exception_type': 'FileNotFoundError', 'errno': 2})
        self.assertNotIn('private', json.dumps(result))
        self.assertEqual(self.probe.exception_facts(RuntimeError('token-value')),
                         {'exception_type': 'RuntimeError'})

    def test_fixed_code_preserved_but_arbitrary_message_rejected(self):
        result = self.probe.exception_facts(wr.WindowsGuardError('windows_worker_job_limits_invalid'))
        self.assertEqual(result['code'], 'windows_worker_job_limits_invalid')
        self.assertNotIn('code', self.probe.exception_facts(wr.WindowsGuardError('C:\\private\\secret')))
        import protocol
        self.assertEqual(self.probe.exception_facts(protocol.ProtocolError('bridge_eof_or_invalid_read'))['code'],
                         'bridge_eof_or_invalid_read')

    def test_output_structure_distinguishes_eof_partial_nonjson_and_cap(self):
        eof = self.probe.output_facts(b'', 'frame_1')
        self.assertTrue(eof['eof']); self.assertEqual(eof['bytes'], 0)
        partial = self.probe.output_facts(b'{"child":123}', 'frame_2')
        self.assertFalse(partial['newline']); self.assertEqual(partial['json'], 'object')
        bad = self.probe.output_facts(b'private path or token\n', 'frame_3')
        self.assertEqual(bad['json'], 'invalid')
        large = self.probe.output_facts(b'x' * 4097, 'frame_4')
        self.assertTrue(large['over_cap']); self.assertNotIn('json', large)

    def test_unknown_output_and_unhashable_fields_cannot_escape(self):
        import json
        raw = b'{"private":"token-value","reason":[],"exception":{"exception_type":[]}}\n'
        facts = self.probe.output_facts(raw, 'synthetic_test')
        self.assertEqual(facts['unknown_field_count'], 1)
        self.assertNotIn('token-value', json.dumps(facts)); self.assertNotIn('private', json.dumps(facts))

    def test_safe_child_failure_record_preserves_only_allowed_fields(self):
        import json
        raw = json.dumps({'format': 'irisx/native-probe-child-error-v1',
            'exception': {'exception_type': 'WindowsGuardError', 'code': 'windows_worker_job_limits_invalid',
                          'message': '/private/secret'},
            'current_job': {'member_query_ok': True, 'member_query_error': 0, 'is_member': True,
                           'limits_query_ok': True, 'limits_query_error': 0, 'limit_flags': 0,
                           'private': 'secret'}}).encode() + b'\n'
        facts = self.probe.output_facts(raw, 'cleanup_stderr')
        self.assertEqual(facts['current_job']['limit_flags'], 0)
        self.assertEqual(facts['exception']['code'], 'windows_worker_job_limits_invalid')
        self.assertNotIn('private', json.dumps(facts)); self.assertNotIn('secret', json.dumps(facts))

    def test_null_job_diagnostic_never_opens_handle_or_weakens_guard(self):
        fake = FakeAPI(); fake.GetCurrentProcess = lambda: 89
        fake.OpenJobObjectW = mock.Mock(side_effect=AssertionError('must never open Job'))
        def query(handle, category, info, size, written):
            self.assertIsNone(handle)
            C.cast(info, C.POINTER(wr.JOBOBJECT_EXTENDED_LIMIT_INFORMATION)).contents.BasicLimitInformation.LimitFlags = 0
            return 1
        fake.QueryInformationJobObject = query
        with mock.patch.object(self.probe, 'api', return_value=fake), mock.patch.object(wr, 'api', return_value=fake), \
             mock.patch.object(C, 'set_last_error', create=True), mock.patch.object(C, 'get_last_error', return_value=0, create=True):
            with self.assertRaisesRegex(wr.WindowsGuardError, 'job_limits_invalid'):
                self.probe.checked_worker_job('a' * 64)
        self.assertEqual(self.probe.DIAGNOSTICS[0]['limit_flags'], 0)
        self.assertTrue(self.probe.DIAGNOSTICS[0]['is_member'])
        fake.OpenJobObjectW.assert_not_called()

    def test_cleanup_proves_zero_before_reading_synthetic_stderr(self):
        events = []
        chunks = iter((b'{"reason":"caller_pipe_or_protocol_error","closure":{"active_processes":0}}\n', b''))
        def read(count):
            events.append('read'); return next(chunks)
        pipe = SimpleNamespace(handle=1, read=read)
        job = SimpleNamespace(stderr=pipe,
            terminate_and_prove_empty=lambda **kw: events.append(('zero', kw)),
            _close_handles=lambda: events.append('close'))
        self.probe.cleanup_with_diagnostics(job)
        self.assertEqual(events[0], ('zero', {'close_pipes': False}))
        self.assertEqual(events[-1], 'close')
        self.assertEqual(self.probe.DIAGNOSTICS[0]['supervisor_reason'], 'caller_pipe_or_protocol_error')
        self.assertEqual(self.probe.DIAGNOSTICS[0]['active_processes'], 0)

    def test_read_exception_is_not_reported_as_eof(self):
        stream = SimpleNamespace(readline=mock.Mock(side_effect=OSError(5, '/private/path')))
        with self.assertRaisesRegex(wr.WindowsGuardError, 'probe_output_read_failed'):
            self.probe.line_with_timeout(stream, stage='parent_death_handshake_2')
        facts = self.probe.DIAGNOSTICS[0]
        self.assertEqual(facts['event'], 'line_read_error')
        self.assertEqual(facts['stage'], 'parent_death_handshake_2')
        self.assertNotIn('eof', facts)

    def test_diagnostic_record_count_is_bounded(self):
        for _ in range(30):
            self.probe.record_diagnostic({'event': 'test'})
        self.assertEqual(len(self.probe.DIAGNOSTICS), 12)

    def test_short_operation_timer_starts_after_bounded_open_response(self):
        import protocol
        events = []; clock = [100.0]
        def send(kind, payload, **binding):
            events.append((kind, payload, binding))
        def receive(**binding):
            events.append(('receive', binding)); clock[0] = 103.0
        channel = SimpleNamespace(send=send, receive=receive)
        with mock.patch.object(self.probe.time, 'time', side_effect=lambda: clock[0]), \
             mock.patch.object(self.probe.time, 'monotonic', return_value=17):
            began = self.probe.begin_framed_watch(protocol, channel, 'operation', 110)
        self.assertEqual(began, 17)
        self.assertEqual(events[0][1]['operation'], 'open')
        self.assertEqual(events[0][1]['deadline_epoch'], 108)
        self.assertEqual(events[1][0], 'receive')
        self.assertEqual(events[2][1]['operation'], 'output')
        self.assertEqual(events[2][2]['sequence'], 2)
        self.assertEqual(events[2][1]['max_seconds'], 0.6)
        self.assertEqual(events[2][1]['deadline_epoch'], 103.6)

    def test_phase_request_cannot_extend_original_lease_after_handshake(self):
        import protocol
        sent = []; clock = [100.0]
        channel = SimpleNamespace(send=lambda kind, payload, **binding: sent.append(payload),
            receive=lambda **binding: clock.__setitem__(0, 104.0))
        with mock.patch.object(self.probe.time, 'time', side_effect=lambda: clock[0]):
            self.probe.begin_framed_watch(protocol, channel, 'phase', 110)
        self.assertEqual(sent[-1]['deadline_epoch'], 110)
        self.assertEqual(sent[-1]['max_seconds'], 8)

    def test_framed_descendant_exists_before_open_response(self):
        events = []
        requests = iter(({'sequence': 1, 'request_sha256': 'a' * 64},
                         {'sequence': 2, 'request_sha256': 'b' * 64}))
        channel = SimpleNamespace(receive=lambda **kw: next(requests),
            send=lambda kind, payload, **kw: events.append(kind))
        protocol = SimpleNamespace(FramedIO=lambda *args, **kw: channel)
        with mock.patch.object(self.probe, 'framed_module', return_value=protocol), \
             mock.patch.object(self.probe, 'checked_worker_job'), \
             mock.patch.object(self.probe.subprocess, 'Popen', side_effect=lambda *a, **kw: events.append('spawn')), \
             mock.patch.object(self.probe.time, 'sleep', side_effect=lambda seconds: events.append('hang')):
            self.assertEqual(self.probe.framed_worker('phase', 'a' * 64), 0)
        self.assertEqual(events, ['spawn', 'response', 'phase_start', 'hang'])

    def test_controller_python_rejects_unsafe_path_before_read(self):
        with mock.patch.object(self.probe, 'read_source', side_effect=AssertionError('must not read')):
            for path in (r'\\host\share\python.exe', r'C:\a\..\python.exe',
                         r'C:\a\other.exe', r'C:\a\credentials.json'):
                with self.subTest(path=path), self.assertRaises(wr.WindowsGuardError):
                    self.probe.verified_python(path, 'a' * 64)

    def test_controller_python_reads_bound_public_bytes_and_rejects_stale_hash(self):
        import hashlib
        raw = b'public synthetic executable'; digest = hashlib.sha256(raw).hexdigest()
        with mock.patch.object(self.probe, 'read_source', return_value=raw) as source:
            self.assertEqual(self.probe.verified_python(r'C:\base\python.exe', digest), r'C:\base\python.exe')
            source.assert_called_once_with(r'C:\base\python.exe', 128 * 1024 * 1024)
            with self.assertRaisesRegex(wr.WindowsGuardError, 'python_hash_mismatch'):
                self.probe.verified_python(r'C:\base\python.exe', 'f' * 64)

    def test_controller_launch_uses_base_and_carries_original_venv_binding(self):
        with mock.patch.object(self.probe.sys, 'executable', r'C:\venv\Scripts\python.exe'), \
             mock.patch.object(self.probe.sys, '_base_executable', r'C:\base\python.exe'), \
             mock.patch.object(self.probe, 'verified_python', side_effect=lambda path, digest: path) as verify:
            argv = self.probe.controller_command()
        self.assertEqual(argv[0], r'C:\base\python.exe')
        self.assertEqual(argv[4:], ['--parent-owner', r'C:\venv\Scripts\python.exe',
            self.probe.PYTHON_SHA256, r'C:\base\python.exe', self.probe.PYTHON_BASE_EXECUTABLE_SHA256])
        self.assertEqual(verify.call_count, 2)

    def test_controller_supervisor_stays_on_original_venv(self):
        with mock.patch.object(self.probe.sys, 'executable', r'C:\base\python.exe'), \
             mock.patch.object(self.probe.sys, 'prefix', 'base'), mock.patch.object(self.probe.sys, 'base_prefix', 'base'), \
             mock.patch.object(self.probe.os, 'getpid', return_value=77), \
             mock.patch.object(self.probe, 'verified_python', side_effect=lambda path, digest: path) as verify:
            argv = self.probe.controller_supervisor_command(r'C:\venv\Scripts\python.exe', 'a' * 64,
                                                            r'C:\base\python.exe', 'b' * 64)
        self.assertEqual(argv[0], r'C:\venv\Scripts\python.exe')
        self.assertEqual(argv[4:], ['--probe-supervisor', '15', '--watched-controller', '77',
                                    r'C:\venv\Scripts\python.exe', 'a' * 64])
        self.assertEqual(verify.call_count, 3)

    def test_controller_rejects_wrong_actual_path_or_venv_identity(self):
        for actual, prefix in ((r'C:\wrong\python.exe', 'base'), (r'C:\base\python.exe', 'venv')):
            with self.subTest(actual=actual, prefix=prefix), \
                 mock.patch.object(self.probe.sys, 'executable', actual), mock.patch.object(self.probe.sys, 'prefix', prefix), \
                 mock.patch.object(self.probe.sys, 'base_prefix', 'base'), \
                 mock.patch.object(self.probe, 'verified_python', side_effect=lambda path, digest: path):
                with self.assertRaisesRegex(wr.WindowsGuardError, 'controller_python_identity'):
                    self.probe.controller_supervisor_command(r'C:\venv\Scripts\python.exe', 'a' * 64,
                                                            r'C:\base\python.exe', 'b' * 64)

    def test_watched_controller_requires_echo_membership_and_runtime_binding(self):
        identity = {'watched_controller_pid': 77, 'supervisor_python_sha256': self.probe.PYTHON_SHA256}
        controller = {'parent_owner': 77, 'controller_is_base_python': True,
            'controller_python_sha256': self.probe.PYTHON_BASE_EXECUTABLE_SHA256,
            'supervisor_python_sha256': self.probe.PYTHON_SHA256}
        self.assertEqual(self.probe.watched_controller(identity, controller, (77, 88)), 77)
        for change in ({'watched_controller_pid': 88}, {'watched_controller_pid': True},
                       {'supervisor_python_sha256': '0' * 64}):
            with self.subTest(change=change), self.assertRaises(wr.WindowsGuardError):
                self.probe.watched_controller({**identity, **change}, controller, (77, 88))
        with self.assertRaises(wr.WindowsGuardError):
            self.probe.watched_controller(identity, controller, (88,))
        with self.assertRaises(wr.WindowsGuardError):
            self.probe.watched_controller(identity, {**controller, 'controller_is_base_python': False}, (77, 88))


class WSLHarnessTests(unittest.TestCase):
    def setUp(self):
        import wsl_native_probe
        self.harness = wsl_native_probe
        self.expected = {'source_sha256': {name: 'a' * 64 for name in wsl_native_probe.SOURCE_NAMES},
            'python_executable_sha256': 'b' * 64, 'python_base_executable_sha256': 'c' * 64,
            'pyvenv_cfg_sha256': 'd' * 64}
        self.receipt = {'format': 'irisx/wsl-native-observer-result-v1', 'ok': True,
            'scope': 'synthetic_wsl_caller_death_pipe_eof_job_closure',
            'native_windows': True, 'python_version': '3.12.10', **self.expected,
            'network_used': False, 'real_auth_accessed': False, 'caller_pipe_eof_observed': True,
            'observer_job_active_processes': 0, 'original_member_handles_stopped': True,
            'all_members_tracked': 5, 'source_unchanged': True,
            'supervisor': {'reason': 'caller_pipe_eof', 'closure': {
                'format': 'irisx/windows-job-closure-v1', 'active_processes': 0,
                'kill_on_close': True, 'breakaway_permitted': False, 'atomic_job_assignment': True}}}

    def test_native_observer_accepts_base_python_parent_outside_child_job(self):
        import native_probe
        native_probe.require_observed_tree({'job_owner': 10, 'native_parent_pid': 99},
                                          {'child': 20, 'grandchild': 30}, (10, 20, 30))
        native_probe.require_observed_tree({'job_owner': 10, 'native_parent_pid': 9},
                                          {'child': 20, 'grandchild': 30}, (9, 10, 20, 30))
        with self.assertRaises(wr.WindowsGuardError):
            native_probe.require_observed_tree({'job_owner': 10, 'native_parent_pid': 99},
                                              {'child': 20, 'grandchild': 30}, (10, 20))

    def test_accepts_complete_exact_bound_closure(self):
        self.assertIs(self.harness.verify_closure(self.receipt, self.expected), self.receipt)

    def test_rejects_missing_or_stale_base_runtime(self):
        for field in ('python_executable_sha256', 'python_base_executable_sha256', 'pyvenv_cfg_sha256'):
            damaged = dict(self.receipt); damaged[field] = 'e' * 64
            with self.subTest(field=field), self.assertRaises(self.harness.ProbeError):
                self.harness.verify_closure(damaged, self.expected)

    def test_native_process_exit_alone_is_not_closure(self):
        for field, value in (('caller_pipe_eof_observed', False),
                             ('observer_job_active_processes', 1),
                             ('observer_job_active_processes', False),
                             ('original_member_handles_stopped', False),
                             ('all_members_tracked', 2), ('source_unchanged', False)):
            damaged = dict(self.receipt); damaged[field] = value
            with self.subTest(field=field), self.assertRaises(self.harness.ProbeError):
                self.harness.verify_closure(damaged, self.expected)

    def test_wrong_native_stop_reason_rejected(self):
        import copy
        damaged = copy.deepcopy(self.receipt)
        damaged['supervisor']['reason'] = 'deadline'
        with self.assertRaises(self.harness.ProbeError):
            self.harness.verify_closure(damaged, self.expected)

    def test_bool_is_not_process_count(self):
        import copy
        damaged = copy.deepcopy(self.receipt)
        damaged['supervisor']['closure']['active_processes'] = False
        with self.assertRaises(self.harness.ProbeError):
            self.harness.verify_closure(damaged, self.expected)

    def test_source_map_binds_all_four_members(self):
        damaged = dict(self.receipt)
        damaged['source_sha256'] = dict(self.receipt['source_sha256'])
        damaged['source_sha256'].pop('protocol.py')
        with self.assertRaises(self.harness.ProbeError):
            self.harness.verify_closure(damaged, self.expected)

    def test_json_rejects_duplicates_and_nonfinite_values(self):
        for raw in (b'{"ok":true,"ok":false}', b'{"x":NaN}', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(self.harness.ProbeError):
                self.harness.strict_json(raw)

    def test_native_mapping_is_exact_and_rejects_ambiguous_paths(self):
        self.assertEqual(str(self.harness.native_probe_path(r'C:\Users\owner\native_probe.py')),
                         '/mnt/c/Users/owner/native_probe.py')
        for path in (r'\\host\share\native_probe.py', r'\\?\C:\native_probe.py',
                     r'C:\owner\..\native_probe.py', r'C:\owner.\native_probe.py',
                     r'C:\owner\different.py', r'C:relative\native_probe.py'):
            with self.subTest(path=path), self.assertRaises(self.harness.ProbeError):
                self.harness.native_probe_path(path)

    def test_all_native_sources_prehashed_before_execution(self):
        seen = []
        def digest(path, cap):
            seen.append(path)
            return self.expected['source_sha256'][path.name]
        with mock.patch.object(self.harness, 'file_hash', side_effect=digest):
            self.harness.verify_native_sources(r'C:\reviewed\native_probe.py', self.expected['source_sha256'])
        self.assertEqual({path.name for path in seen}, set(self.harness.SOURCE_NAMES))
        self.assertTrue(all(str(path.parent) == '/mnt/c/reviewed' for path in seen))
        with mock.patch.object(self.harness, 'file_hash', return_value='f' * 64):
            with self.assertRaisesRegex(self.harness.ProbeError, 'prelaunch_source_mismatch'):
                self.harness.verify_native_sources(r'C:\wrong\native_probe.py', self.expected['source_sha256'])

    def test_public_source_hash_rejects_symlink_ancestor(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory); real = root / 'real'; real.mkdir()
            (real / 'source.py').write_text('pass', encoding='utf-8')
            alias = root / 'alias'; alias.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(self.harness.ProbeError, 'path_alias'):
                self.harness.file_hash(alias / 'source.py', 65536)

    def test_non_wsl_refused_before_any_execution(self):
        args = SimpleNamespace(native_python='/not/read/python.exe')
        fake_uname = SimpleNamespace(release='ordinary-linux')
        with mock.patch.object(self.harness.os, 'uname', return_value=fake_uname), \
             mock.patch.object(self.harness.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
            with self.assertRaisesRegex(self.harness.ProbeError, 'requires_wsl'):
                self.harness.run(args)


if __name__ == '__main__':
    unittest.main()

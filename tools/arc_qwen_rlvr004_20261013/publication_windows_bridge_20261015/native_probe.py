r"""Offline native acceptance. Never locates, opens, reads, or changes real auth.

Run with the intended existing Windows interpreter:
  python.exe -I -B C:\...\native_probe.py
Outputs one sanitized JSON result. Synthetic private files live in a unique
fresh token-profile directory and are removed after handles close. No network,
package installation, login, environment/security changes, or provider calls.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import struct
import sys
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent


def public_hash(path, cap):
    with open(path, 'rb') as stream:
        raw = stream.read(cap + 1)
    if len(raw) > cap:
        raise RuntimeError('probe_source_size_invalid')
    return hashlib.sha256(raw).hexdigest()


SOURCE_HASHES = {name: public_hash(HERE / name, 1024 * 1024) for name in
                 ('win_runtime.py', 'win_supervisor.py', 'native_probe.py', 'protocol.py')}
PYTHON_SHA256 = public_hash(sys.executable, 128 * 1024 * 1024)
PYTHON_VERSION = '.'.join(str(v) for v in sys.version_info[:3])
PYTHON_BASE_EXECUTABLE_SHA256 = public_hash(getattr(sys, '_base_executable', None) or sys.executable, 128 * 1024 * 1024)
PYVENV_CFG_SHA256 = (public_hash(Path(sys.prefix) / 'pyvenv.cfg', 65536)
                    if sys.prefix != sys.base_prefix else None)
sys.path.insert(0, str(HERE))
from win_runtime import (ExclusiveMutex, JobProcess, PrivateFileGuard, SecurityDescriptor,
                         WindowsGuardError, api, current_identity, need, profile_relative,
                         HANDLE, DWORD, LPVOID, BOOL, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
                         require_worker_job)
from win_supervisor import supervise


# Diagnostic-only observations. Never contain raw output, exception messages,
# traceback paths, environment values, or credential data. Each case remains a
# failure until its original assertions pass; observations are not new checks.
DIAGNOSTICS = []
SUPERVISOR_REASONS = frozenset(('worker_exit', 'deadline', 'operation_deadline',
    'official_rpc_deadline', 'parent_death', 'caller_pipe_eof',
    'caller_pipe_or_protocol_error', 'output_pipe_or_protocol_error',
    'input_limit', 'output_limit', 'output_pipe_error', 'worker_stderr_limit',
    'worker_stderr_pipe_error', 'relay_drain_timeout', 'supervisor_error'))
EXCEPTION_TYPES = frozenset(('WindowsGuardError', 'ProtocolError', 'OSError',
    'ValueError', 'TypeError', 'KeyError', 'IndexError', 'StopIteration',
    'JSONDecodeError', 'UnicodeDecodeError', 'TimeoutExpired', 'TimeoutError',
    'BrokenPipeError', 'PermissionError', 'FileNotFoundError', 'RuntimeError'))
QUERY_FIELDS = frozenset(('member_query_ok', 'member_query_error', 'is_member',
    'limits_query_ok', 'limits_query_error', 'limit_flags'))


def record_diagnostic(value):
    if len(DIAGNOSTICS) < 12:
        DIAGNOSTICS.append(value)


def exception_facts(exc):
    name = type(exc).__name__
    result = {'exception_type': name if name in EXCEPTION_TYPES else 'other'}
    # Only the two reviewed fixed-code exception classes supply a code. All
    # other messages (including OS errors containing paths) are discarded.
    if type(exc) is WindowsGuardError or (name == 'ProtocolError' and type(exc).__module__ == 'protocol'):
        code = str(exc)
        if re.fullmatch(r'(?:windows|probe|bridge)_[a-z0-9_]{1,96}', code):
            result['code'] = code
    for key in ('errno', 'winerror'):
        value = getattr(exc, key, None)
        if type(value) is int and 0 <= value <= 0xffffffff:
            result[key] = value
    return result


def current_job_facts():
    """Read numeric NULL-Job facts, without opening or duplicating a Job."""
    a = api(); member = BOOL(); limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    C.set_last_error(0)
    member_ok = bool(a.k.IsProcessInJob(a.k.GetCurrentProcess(), None, C.byref(member)))
    member_error = C.get_last_error()
    C.set_last_error(0)
    limits_ok = bool(a.k.QueryInformationJobObject(None, 9, C.byref(limits), C.sizeof(limits), None))
    limits_error = C.get_last_error()
    return {'member_query_ok': member_ok, 'member_query_error': member_error,
            'is_member': bool(member.value) if member_ok else None,
            'limits_query_ok': limits_ok, 'limits_query_error': limits_error,
            'limit_flags': int(limits.BasicLimitInformation.LimitFlags) if limits_ok else None}


def checked_worker_job(nonce):
    # Observe the exact API used by the unchanged guard. Its requirement is
    # deliberately not relaxed when a venv creates additional nested Jobs.
    record_diagnostic({'event': 'current_job', **current_job_facts()})
    return require_worker_job(nonce)


def output_facts(data, label):
    result = {'event': 'synthetic_line', 'stage': label, 'bytes': len(data),
              'eof': not data, 'newline': data.endswith(b'\n'), 'over_cap': len(data) > 4096}
    if not data or len(data) > 4096:
        return result
    try:
        value = json.loads(data.decode('ascii'))
    except (ValueError, UnicodeError, RecursionError):
        result['json'] = 'invalid'; return result
    result['json'] = 'object' if type(value) is dict else 'other'
    if type(value) is not dict:
        return result
    known = ('child', 'grandchild', 'job_owner', 'native_parent_pid', 'parent_owner',
             'reason', 'closure', 'format', 'exception', 'current_job', 'mode')
    result['known_fields'] = [key for key in known if key in value]
    result['unknown_field_count'] = sum(key not in known for key in value)
    if type(value.get('reason')) is str and value['reason'] in SUPERVISOR_REASONS:
        result['supervisor_reason'] = value['reason']
    closure = value.get('closure')
    if type(closure) is dict and type(closure.get('active_processes')) is int:
        result['active_processes'] = max(-1, min(0xffffffff, closure['active_processes']))
    if value.get('format') == 'irisx/native-probe-child-error-v1':
        error = value.get('exception')
        if type(error) is dict:
            result['exception'] = {key: val for key, val in error.items() if
                (key == 'exception_type' and type(val) is str and val in EXCEPTION_TYPES | {'other'}) or
                (key == 'code' and type(val) is str and re.fullmatch(r'(?:windows|probe|bridge)_[a-z0-9_]{1,96}', val)) or
                (key in ('errno', 'winerror') and type(val) is int and 0 <= val <= 0xffffffff)}
        facts = value.get('current_job')
        if type(facts) is dict:
            result['current_job'] = {key: val for key, val in facts.items()
                if key in QUERY_FIELDS and (val is None or type(val) is bool or
                    type(val) is int and 0 <= val <= 0xffffffff)}
    return result


def cleanup_with_diagnostics(job):
    """Prove zero first, then drain at most 8 KiB of synthetic stderr."""
    try:
        job.terminate_and_prove_empty(close_pipes=False)
        if not job.stderr or not job.stderr.handle:
            return
        result = queue.Queue(maxsize=1)
        def reader():
            try:
                raw = b''
                while len(raw) <= 8192:
                    chunk = job.stderr.read(min(4096, 8193 - len(raw)))
                    if not chunk:
                        break
                    raw += chunk
                result.put(raw)
            except BaseException as exc:
                result.put(exc)
        threading.Thread(target=reader, daemon=True).start()
        try:
            raw = result.get(timeout=2)
        except queue.Empty:
            record_diagnostic({'event': 'stderr_drain_timeout'}); return
        if isinstance(raw, BaseException):
            record_diagnostic({'event': 'stderr_drain_error', **exception_facts(raw)}); return
        if len(raw) > 8192:
            record_diagnostic({'event': 'stderr_over_cap', 'bytes': len(raw)}); return
        for line in raw.splitlines(keepends=True)[:8]:
            record_diagnostic(output_facts(line, 'cleanup_stderr'))
    finally:
        job._close_handles()


def command(*args):
    return [sys.executable, '-I', '-B', str(Path(__file__).resolve()), *args]


def line_with_timeout(stream, seconds=10, *, stage='unspecified'):
    result = queue.Queue(maxsize=1)
    def reader():
        try:
            result.put(stream.readline(4097))
        except BaseException as exc:
            result.put(exc)
    threading.Thread(target=reader, daemon=True).start()
    try:
        data = result.get(timeout=seconds)
    except queue.Empty:
        record_diagnostic({'event': 'line_timeout', 'stage': stage})
        raise WindowsGuardError('probe_output_timeout') from None
    if isinstance(data, BaseException):
        record_diagnostic({'event': 'line_read_error', 'stage': stage, **exception_facts(data)})
        raise WindowsGuardError('probe_output_read_failed') from None
    record_diagnostic(output_facts(data, stage))
    need(0 < len(data) <= 4096 and data.endswith(b'\n'), 'probe_output_invalid')
    return json.loads(data.decode('ascii'))


class PipeLines:
    def __init__(self, pipe):
        self.pipe = pipe; self.pending = b''

    def readline(self, cap):
        while b'\n' not in self.pending:
            data = self.pipe.read()
            if not data:
                return self.pending
            self.pending += data
            need(len(self.pending) <= cap, 'probe_child_output_limit')
        first, self.pending = self.pending.split(b'\n', 1)
        return first + b'\n'


class ProcessRefs:
    def __init__(self, pids):
        self.handles = []
        try:
            for pid in pids:
                h = api().handle(api().k.OpenProcess(0x00100000 | 0x001000, False, pid), 'probe_process_open_failed')
                self.handles.append(h)
        except BaseException:
            self.close(); raise

    def assert_stopped(self, seconds=8):
        end = time.monotonic() + seconds
        for h in self.handles:
            ms = max(0, int((end - time.monotonic()) * 1000))
            need(api().k.WaitForSingleObject(h, ms) == 0, 'probe_descendant_survived')

    def close(self):
        for h in self.handles:
            api().k.CloseHandle(h)
        self.handles = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def synthetic_file(path, sddl):
    a = api()
    with SecurityDescriptor(sddl) as sd:
        h = a.handle(a.k.CreateFileW(str(path), 0x40000000, 0, C.byref(sd.attributes), 1, 0x80, None), 'probe_create_file_failed')
    try:
        data = b'synthetic-only\n'; count = DWORD(); buf = C.create_string_buffer(data)
        a.check(a.k.WriteFile(h, buf, len(data), C.byref(count), None), 'probe_write_file_failed')
        need(count.value == len(data), 'probe_short_write')
    finally:
        a.k.CloseHandle(h)


def synthetic_junction(path, target, sddl):
    # A new private test directory junction needs no symlink privilege. No
    # existing path, permission or reparse target is changed.
    a = api()
    with SecurityDescriptor(sddl) as sd:
        a.check(a.k.CreateDirectoryW(str(path), C.byref(sd.attributes)), 'probe_junction_directory_failed')
    h = a.handle(a.k.CreateFileW(str(path), 0x40000000, 0, None, 3,
                                0x00200000 | 0x02000000, None), 'probe_junction_open_failed')
    try:
        substitute = ('\\??\\' + str(target)).encode('utf-16le')
        display = str(target).encode('utf-16le')
        paths = substitute + b'\0\0' + display + b'\0\0'
        raw = struct.pack('<IHHHHHH', 0xA0000003, 8 + len(paths), 0,
                          0, len(substitute), len(substitute) + 2, len(display)) + paths
        buf = C.create_string_buffer(raw); count = DWORD()
        a.check(a.k.DeviceIoControl(h, 0x000900A4, buf, len(raw), None, 0,
                                   C.byref(count), None), 'probe_junction_create_failed')
    finally:
        a.k.CloseHandle(h)


def metadata_checks():
    ident = current_identity()
    root = Path(ident.profile) / ('irisx-offline-probe-' + uuid.uuid4().hex)
    sddl = 'O:' + ident.sid + 'D:P(A;;FA;;;' + ident.sid + ')(A;;FA;;;SY)(A;;FA;;;BA)'
    with SecurityDescriptor(sddl) as sd:
        api().check(api().k.CreateDirectoryW(str(root), C.byref(sd.attributes)), 'probe_create_directory_failed')
    try:
        good = root / 'synthetic-private.dat'
        synthetic_file(good, sddl)
        with PrivateFileGuard(str(good)) as guard:
            need(guard.proof['native_profile'] and guard.revalidate()['allow_sids_approved'], 'probe_private_metadata_failed')
        # Explicit refresh-mode write changes only our synthetic file, no ACL.
        with PrivateFileGuard(str(good), allow_write=True) as guard:
            with open(good, 'wb') as stream:
                stream.write(b'synthetic-updated\n')
            guard.revalidate()
        bad = root / 'synthetic-public.dat'
        synthetic_file(bad, sddl + '(A;;FR;;;WD)')
        try:
            with PrivateFileGuard(str(bad)):
                pass
        except WindowsGuardError as exc:
            need(str(exc) == 'windows_acl_unapproved_allow_sid', 'probe_wrong_acl_rejection')
        else:
            raise WindowsGuardError('probe_public_acl_accepted')
        wrong = str(Path(ident.profile).parent / ('outside-' + uuid.uuid4().hex) / 'synthetic.dat')
        try:
            profile_relative(wrong, ident)
        except WindowsGuardError as exc:
            need(str(exc) == 'windows_original_profile_required', 'probe_wrong_profile_rejection')
        else:
            raise WindowsGuardError('probe_other_profile_accepted')
        # A hard link needs no symlink privilege and must be rejected separately.
        alias = root / 'synthetic-hardlink.dat'
        os.link(good, alias)
        try:
            with PrivateFileGuard(str(good)):
                pass
        except WindowsGuardError as exc:
            need(str(exc) == 'windows_regular_single_link_required', 'probe_wrong_hardlink_rejection')
        else:
            raise WindowsGuardError('probe_hardlink_accepted')
        alias.unlink()
        junction = root / 'synthetic-junction'
        synthetic_junction(junction, root, sddl)
        try:
            try:
                with PrivateFileGuard(str(junction / good.name)):
                    pass
            except WindowsGuardError as exc:
                need(str(exc) == 'windows_reparse_path_forbidden', 'probe_wrong_reparse_rejection')
            else:
                raise WindowsGuardError('probe_reparse_accepted')
        finally:
            os.rmdir(junction)
        return {'private_metadata': True, 'in_place_write_revalidated': True,
                'unapproved_allow_rejected': True, 'wrong_profile_rejected': True,
                'hardlink_rejected': True, 'reparse_ancestor_rejected': True, 'real_auth_accessed': False}
    finally:
        shutil.rmtree(root)


def lock_check():
    scope = 'offline-probe-' + uuid.uuid4().hex
    with ExclusiveMutex(scope):
        child = subprocess.run(command('--lock-probe', scope), stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=False)
        need(child.returncode == 0 and child.stdout == b'locked\n', 'probe_duplicate_lock_failed')
    with ExclusiveMutex(scope):
        pass
    return {'duplicate_rejected': True, 'released_lock_reacquired': True}


def job_check():
    nonce = uuid.uuid4().hex + uuid.uuid4().hex
    job = JobProcess(command('--tree', nonce), job_nonce=nonce)
    try:
        data = line_with_timeout(PipeLines(job.stdout), stage='job_tree_handshake')
        with ProcessRefs([data['child'], data['grandchild']]) as refs:
            need(job.active_processes() >= 2, 'probe_job_missing_grandchild')
            proof = job.terminate_and_prove_empty()
            refs.assert_stopped()
            return {**proof, 'exact_membership_checked_before_resume': True, 'worker_null_job_check': True}
    finally:
        cleanup_with_diagnostics(job)


def kill_actual_process(pid):
    # Capture a handle to the announced native role, not a venv launcher PID.
    h = api().handle(api().k.OpenProcess(0x00100000 | 0x1000 | 0x0001, False, pid), 'probe_kill_handle_failed')
    try:
        api().check(api().k.TerminateProcess(h, 137), 'probe_owner_kill_failed')
        need(api().k.WaitForSingleObject(h, 8000) == 0, 'probe_killed_owner_survived')
    finally:
        api().k.CloseHandle(h)


def stable_members(job, seconds=5):
    end = time.monotonic() + seconds
    previous = None
    while time.monotonic() < end:
        current = job.process_ids()
        if current == previous and len(current) >= 3:
            return current
        previous = current
        time.sleep(0.1)
    raise WindowsGuardError('probe_membership_unstable')


def assert_job_empty(job, seconds=8):
    end = time.monotonic() + seconds
    while job.active_processes():
        need(time.monotonic() < end, 'probe_job_members_survived')
        time.sleep(0.01)


def supervisor_check(mode):
    # An outer observer Job neither holds the supervisor's inner Job handle nor
    # triggers its kill-on-close. It permits independent all-descendant counting
    # after the inner Job's sole owner has been forcibly terminated.
    owner = JobProcess(command('--probe-supervisor', '3'))
    refs = None
    try:
        lines = PipeLines(owner.stdout)
        values = [line_with_timeout(lines, stage='supervisor_handshake_1'),
                  line_with_timeout(lines, stage='supervisor_handshake_2')]
        data = next(v for v in values if 'child' in v)
        owner_identity = next(v for v in values if 'job_owner' in v)
        members = stable_members(owner)
        need(owner_identity['job_owner'] in members, 'probe_owner_missing')
        need(data['child'] in members and data['grandchild'] in members, 'probe_membership_missing_tree')
        refs = ProcessRefs(members)
        if mode == 'supervisor_kill':
            kill_actual_process(owner_identity['job_owner'])
        elif mode == 'pipe_eof':
            owner.stdin.close()
        assert_job_empty(owner, 12)
        refs.assert_stopped()
        if mode == 'supervisor_kill':
            return {'descendants_stopped': True, 'kill_on_close_observed': True,
                    'all_members_tracked': len(members), 'observer_job_active_processes': 0,
                    'actual_job_owner_killed': True}
        receipt = line_with_timeout(PipeLines(owner.stderr), stage='supervisor_receipt')
        expected = 'deadline' if mode == 'timeout' else 'caller_pipe_eof'
        need(receipt['reason'] == expected and receipt['closure']['active_processes'] == 0,
             'probe_supervisor_reason_or_closure_failed')
        return {'reason': receipt['reason'], 'active_processes': 0, 'descendants_stopped': True,
                'all_members_tracked': len(members), 'observer_job_active_processes': 0}
    finally:
        # This runs even on handshake failure and proves all created processes
        # stopped before the probe reports failure. It does not explain PASS:
        # assertions above observe an empty outer Job before cleanup terminates.
        cleanup_with_diagnostics(owner)
        if refs:
            refs.close()


def parent_death_check():
    # Outer probe retains stdin's write side after killing the intermediary
    # owner: EOF cannot explain the supervisor's parent_death observation.
    owner = JobProcess(command('--parent-owner'))
    refs = None
    try:
        lines = PipeLines(owner.stdout)
        values = [line_with_timeout(lines, stage='parent_death_handshake_1'),
                  line_with_timeout(lines, stage='parent_death_handshake_2'),
                  line_with_timeout(lines, stage='parent_death_handshake_3')]
        tree = next(v for v in values if 'child' in v)
        identity = next(v for v in values if 'job_owner' in v)
        supervisor_pid = identity['job_owner']
        members = stable_members(owner)
        need(all(pid in members for pid in (tree['child'], tree['grandchild'], supervisor_pid, identity['native_parent_pid'])), 'probe_membership_missing_tree')
        refs = ProcessRefs(members)
        kill_actual_process(identity['native_parent_pid'])
        assert_job_empty(owner)
        refs.assert_stopped()
        receipt = line_with_timeout(PipeLines(owner.stderr), stage='parent_death_receipt')
        need(receipt['reason'] == 'parent_death' and receipt['closure']['active_processes'] == 0,
             'probe_parent_death_not_observed')
        return {'reason': 'parent_death', 'active_processes': 0, 'descendants_stopped': True,
                'caller_pipe_kept_open': True, 'actual_native_parent_killed': True,
                'all_members_tracked': len(members),
                'observer_job_active_processes': 0}
    finally:
        cleanup_with_diagnostics(owner)
        if refs:
            refs.close()



def framed_module():
    # Public reviewed protocol only; no SDK/config/auth modules are imported.
    import protocol
    return protocol


class FramedPipeAdapter:
    def __init__(self, pipe):
        self.pipe = pipe
    def read(self, count):
        return self.pipe.read(min(count, 65536))
    def write(self, data):
        for offset in range(0, len(data), 65536):
            self.pipe.write(bytes(data[offset:offset + 65536]))
        return len(data)
    def flush(self):
        pass


def probe_request(protocol, channel, sequence, operation, arguments, seconds, *, lease_epoch=None):
    now = time.time()
    deadline = now + seconds
    if lease_epoch is not None:
        deadline = min(deadline, lease_epoch)
    need(deadline > now, 'probe_request_lease_expired')
    payload = {'operation': operation, 'arguments': arguments,
               'deadline_epoch': deadline, 'max_seconds': seconds}
    digest = protocol.request_hash(operation, arguments, deadline_epoch=deadline, max_seconds=seconds)
    channel.send('request', payload, sequence=sequence, request_sha256=digest)
    return digest


def begin_framed_watch(protocol, channel, mode, lease_epoch):
    arguments = {'account': 'danielwuu', 'versions': {'code_predecessor': 20, 'code': 21,
        'inactive_predecessor': 39, 'inactive': 40, 'active': 41},
        'configuration_sha256': 'a' * 64, 'bridge_configuration_sha256': 'b' * 64,
        'publication_manifest_sha256': 'c' * 64, 'deadline_epoch': lease_epoch,
        'max_seconds': 10}
    digest = probe_request(protocol, channel, 1, 'open', arguments, 8, lease_epoch=lease_epoch)
    channel.receive(kinds={'response'}, sequence=1, request_sha256=digest)
    # The short watchdog test starts only once the real supervisor has relayed
    # a valid worker response. Slow venv startup cannot consume its 0.6 seconds.
    # The original overall lease is never restarted by this handshake.
    need(lease_epoch - time.time() > 1, 'probe_startup_left_insufficient_lease')
    began = time.monotonic()
    seconds = 0.6 if mode == 'operation' else 8
    probe_request(protocol, channel, 2, 'output', {'name': 'synthetic.zip', 'version': 1,
        'cap': 1024, 'expected_bytes': None, 'expected_sha256': None}, seconds,
        lease_epoch=lease_epoch)
    return began


def framed_watch_check(mode):
    protocol = framed_module(); nonce = uuid.uuid4().hex + uuid.uuid4().hex
    lease_epoch = time.time() + 10
    owner = JobProcess(command('--framed-supervisor', mode, nonce))
    try:
        channel = protocol.FramedIO(FramedPipeAdapter(owner.stdout), FramedPipeAdapter(owner.stdin), nonce=nonce,
                                   deadline=time.monotonic() + 12)
        began = begin_framed_watch(protocol, channel, mode, lease_epoch)
        assert_job_empty(owner, 12)
        receipt = line_with_timeout(PipeLines(owner.stderr), stage='framed_supervisor_receipt')
        expected = 'operation_deadline' if mode == 'operation' else 'official_rpc_deadline'
        need(receipt['reason'] == expected and receipt['closure']['active_processes'] == 0,
             'probe_native_watchdog_failed')
        need(time.monotonic() - began < 6, 'probe_native_watchdog_too_late')
        return {'reason': expected, 'active_processes': 0, 'observer_job_active_processes': 0,
                'real_protocol_observed': True, 'hung_worker_stopped': True}
    finally:
        cleanup_with_diagnostics(owner)


def framed_worker(mode, nonce):
    protocol = framed_module(); checked_worker_job(nonce)
    channel = protocol.FramedIO(sys.stdin.buffer, sys.stdout.buffer, nonce=nonce)
    request = channel.receive(kinds={'request'})
    sequence = request['sequence']; digest = request['request_sha256']
    # Establish the descendant before the open response permits the parent to
    # start its short timer. No startup work consumes the timed-hang interval.
    subprocess.Popen(command('--grandchild'), stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    channel.send('response', {'operation': 'open', 'result': {'authenticated': True}},
                 sequence=sequence, request_sha256=digest)
    request = channel.receive(kinds={'request'})
    sequence = request['sequence']; digest = request['request_sha256']
    if mode == 'phase':
        channel.send('phase_start', {'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 120,
            'deadline_epoch': time.time() + 0.6}, sequence=sequence, request_sha256=digest)
    # Process tree intentionally does no work and does not cooperate with the
    # deadline. Only the independent real native supervisor can enforce it.
    time.sleep(30)
    return 0



def public_bindings():
    return {'source_sha256': dict(SOURCE_HASHES), 'python_version': PYTHON_VERSION,
            'python_executable_sha256': PYTHON_SHA256,
            'python_base_executable_sha256': PYTHON_BASE_EXECUTABLE_SHA256,
            'pyvenv_cfg_sha256': PYVENV_CFG_SHA256}


def public_bindings_unchanged():
    return (all(public_hash(HERE / name, 1024 * 1024) == digest for name, digest in SOURCE_HASHES.items())
            and public_hash(sys.executable, 128 * 1024 * 1024) == PYTHON_SHA256
            and public_hash(getattr(sys, '_base_executable', None) or sys.executable,
                            128 * 1024 * 1024) == PYTHON_BASE_EXECUTABLE_SHA256
            and (public_hash(Path(sys.prefix) / 'pyvenv.cfg', 65536)
                 if sys.prefix != sys.base_prefix else None) == PYVENV_CFG_SHA256)



def require_observed_tree(identity, tree, members):
    # With base python.exe the supervisor's direct parent is this independent
    # observer, deliberately outside its child Job. Only an intermediate venv
    # launcher belongs to the child Job; EOF evidence does not require one.
    need(all(pid in members for pid in (identity['job_owner'], tree['child'], tree['grandchild'])),
         'probe_wsl_observer_membership')

def wsl_observer():
    """Synthetic WSL caller death -> native pipe EOF -> full Job closure.

    The native observer outlives the killed WSL caller. It holds an outer Job,
    never the inner supervisor Job handle. Its tiny EOF relay is diagnostic-only;
    this does not claim to exercise the production config/SDK entry point.
    """
    owner = None; refs = None
    receipt = {'format': 'irisx/wsl-native-observer-result-v1', 'ok': False,
        'scope': 'synthetic_wsl_caller_death_pipe_eof_job_closure',
        'native_windows': True, 'network_used': False, 'real_auth_accessed': False,
        **public_bindings()}
    try:
        owner = JobProcess(command('--probe-supervisor', '15'))
        lines = PipeLines(owner.stdout)
        values = [line_with_timeout(lines), line_with_timeout(lines)]
        identity = next(value for value in values if 'job_owner' in value)
        tree = next(value for value in values if 'child' in value)
        members = stable_members(owner)
        require_observed_tree(identity, tree, members)
        refs = ProcessRefs(members)
        pipe_closed = threading.Event(); pipe_state = {'eof': False}
        def watch_caller_pipe():
            try:
                pipe_state['eof'] = os.read(0, 1) == b''
            except OSError:
                pipe_state['eof'] = False
            finally:
                owner.stdin.close()
                pipe_closed.set()
        threading.Thread(target=watch_caller_pipe, daemon=True).start()
        ready = {'format': 'irisx/wsl-native-observer-ready-v1', 'native_windows': True,
                 'member_count': len(members), 'roles': {**identity, **tree}, **public_bindings()}
        os.write(1, (json.dumps(ready, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
        need(pipe_closed.wait(12), 'probe_wsl_caller_eof_missing')
        need(pipe_state['eof'], 'probe_wsl_caller_pipe_not_eof')
        assert_job_empty(owner, 8)
        refs.assert_stopped()
        supervisor = line_with_timeout(PipeLines(owner.stderr))
        need(supervisor['reason'] == 'caller_pipe_eof' and supervisor['closure']['active_processes'] == 0,
             'probe_wsl_supervisor_closure_failed')
        need(public_bindings_unchanged(), 'probe_wsl_public_sources_changed')
        receipt.update(ok=True, caller_pipe_eof_observed=True,
            observer_job_active_processes=0, original_member_handles_stopped=True,
            all_members_tracked=len(members), supervisor=supervisor,
            source_unchanged=True)
    except WindowsGuardError as exc:
        receipt['reason'] = str(exc)
    except BaseException:
        receipt['reason'] = 'probe_wsl_observer_internal_error'
    finally:
        if owner is not None:
            try:
                owner.terminate_and_prove_empty()
            except BaseException:
                receipt.update(ok=False, reason='probe_wsl_cleanup_unproven')
        if refs is not None:
            refs.close()
    os.write(1, (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
    return 0 if receipt['ok'] else 1


def child_mode(args):
    if args == ['--wsl-observer']:
        return wsl_observer()
    if args[0] == '--framed-worker':
        return framed_worker(args[1], args[2])
    if args[0] == '--framed-supervisor':
        protocol = framed_module(); nonce = args[2]
        result = supervise(command('--framed-worker', args[1], nonce), timeout_seconds=10,
            deadline_unix=time.time() + 10, scope='offline-probe-' + uuid.uuid4().hex,
            protocol=protocol, nonce=nonce)
        os.write(2, (json.dumps({'reason': result.reason, 'closure': result.closure}) + '\n').encode('ascii'))
        return result.code
    if args[0] == '--grandchild':
        time.sleep(60); return 0
    if args[0] == '--tree':
        if len(args) > 1:
            checked_worker_job(args[1])
        child = subprocess.Popen(command('--grandchild'), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.write(1, (json.dumps({'child': os.getpid(), 'grandchild': child.pid}) + '\n').encode('ascii'))
        time.sleep(60); return 0
    if args[0] == '--lock-probe':
        try:
            with ExclusiveMutex(args[1]):
                return 2
        except WindowsGuardError as exc:
            if str(exc) == 'windows_duplicate_worker':
                os.write(1, b'locked\n'); return 0
            return 3
    if args[0] == '--probe-supervisor':
        os.write(1, (json.dumps({'job_owner': os.getpid(), 'native_parent_pid': os.getppid()}) + '\n').encode('ascii'))
        duration = float(args[1])
        result = supervise(command('--tree'), timeout_seconds=duration,
            deadline_unix=time.time() + duration, scope='offline-probe-' + uuid.uuid4().hex)
        os.write(2, (json.dumps({'reason': result.reason, 'closure': result.closure}) + '\n').encode('ascii'))
        return result.code
    if args[0] == '--parent-owner':
        child = subprocess.Popen(command('--probe-supervisor', '15'), stdin=sys.stdin.buffer,
                                 stdout=sys.stdout.buffer, stderr=sys.stderr.buffer)
        os.write(1, (json.dumps({'parent_owner': os.getpid()}) + '\n').encode('ascii'))
        child.wait(timeout=25); return 0
    return 2


def main():
    if os.name != 'nt':
        os.write(1, (json.dumps({'format': 'irisx/windows-native-probe-v1', 'ok': False,
            'native_windows': False, 'reason': 'native_windows_required',
            'source_sha256': SOURCE_HASHES, 'python_version': PYTHON_VERSION,
            'python_executable_sha256': PYTHON_SHA256,
            'python_base_executable_sha256': PYTHON_BASE_EXECUTABLE_SHA256,
            'pyvenv_cfg_sha256': PYVENV_CFG_SHA256}, sort_keys=True) + '\n').encode('ascii'))
        return 2
    import msvcrt
    for fd in (0, 1, 2):
        msvcrt.setmode(fd, os.O_BINARY)
    if len(sys.argv) > 1:
        try:
            return child_mode(sys.argv[1:])
        except BaseException as exc:
            # Every dispatched mode is fixed synthetic code. Do not print the
            # default traceback, which could expose local file paths.
            facts = next((value for value in DIAGNOSTICS if value.get('event') == 'current_job'), None)
            record = {'format': 'irisx/native-probe-child-error-v1',
                      'exception': exception_facts(exc)}
            if facts is not None:
                record['current_job'] = {key: facts[key] for key in QUERY_FIELDS if key in facts}
            os.write(2, (json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
            return 125
    checks = {}; all_ok = True
    cases = [('metadata', metadata_checks), ('mutex', lock_check), ('job_tree', job_check),
             ('deadline', lambda: supervisor_check('timeout')),
             ('pipe_eof', lambda: supervisor_check('pipe_eof')),
             ('supervisor_kill', lambda: supervisor_check('supervisor_kill')),
             ('parent_death', parent_death_check),
             ('framed_operation_deadline', lambda: framed_watch_check('operation')),
             ('framed_official_rpc_deadline', lambda: framed_watch_check('phase'))]
    for name, check in cases:
        DIAGNOSTICS.clear()
        try:
            checks[name] = {'ok': True, 'result': check()}
        except WindowsGuardError as exc:
            all_ok = False
            checks[name] = {'ok': False, 'reason': str(exc), 'win32_error': C.get_last_error(),
                            'exception': exception_facts(exc), 'diagnostics': list(DIAGNOSTICS)}
        except BaseException as exc:
            all_ok = False
            checks[name] = {'ok': False, 'reason': 'probe_internal_error',
                            'exception': exception_facts(exc), 'diagnostics': list(DIAGNOSTICS)}
    unchanged = public_bindings_unchanged()
    checks['source_unchanged'] = {'ok': unchanged}
    all_ok = all_ok and unchanged
    result = {'format': 'irisx/windows-native-probe-v1', 'ok': all_ok,
        'native_windows': True, 'network_used': False, 'real_auth_accessed': False, 'checks': checks,
        'source_sha256': SOURCE_HASHES, 'python_version': PYTHON_VERSION,
        'python_executable_sha256': PYTHON_SHA256,
            'python_base_executable_sha256': PYTHON_BASE_EXECUTABLE_SHA256,
            'pyvenv_cfg_sha256': PYVENV_CFG_SHA256}
    code = 0 if all_ok else 1
    os.write(1, (json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
    return code


if __name__ == '__main__':
    os._exit(main())

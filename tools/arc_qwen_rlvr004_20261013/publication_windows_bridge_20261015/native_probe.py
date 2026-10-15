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
import shutil
import subprocess
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
                 ('win_runtime.py', 'win_supervisor.py', 'native_probe.py')}
PYTHON_SHA256 = public_hash(sys.executable, 128 * 1024 * 1024)
PYTHON_VERSION = '.'.join(str(v) for v in sys.version_info[:3])
sys.path.insert(0, str(HERE))
from win_runtime import (ExclusiveMutex, JobProcess, PrivateFileGuard, SecurityDescriptor,
                         WindowsGuardError, api, current_identity, need, profile_relative,
                         HANDLE, DWORD, LPVOID)
from win_supervisor import supervise


def command(*args):
    return [sys.executable, '-I', '-B', str(Path(__file__).resolve()), *args]


def line_with_timeout(stream, seconds=10):
    result = queue.Queue(maxsize=1)
    def reader():
        try:
            result.put(stream.readline(4097))
        except BaseException:
            result.put(b'')
    threading.Thread(target=reader, daemon=True).start()
    try:
        data = result.get(timeout=seconds)
    except queue.Empty:
        raise WindowsGuardError('probe_output_timeout') from None
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
        return {'private_metadata': True, 'in_place_write_revalidated': True,
                'unapproved_allow_rejected': True, 'wrong_profile_rejected': True,
                'hardlink_rejected': True, 'real_auth_accessed': False}
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
    job = JobProcess(command('--tree'))
    try:
        data = line_with_timeout(PipeLines(job.stdout))
        with ProcessRefs([data['child'], data['grandchild']]) as refs:
            need(job.active_processes() >= 2, 'probe_job_missing_grandchild')
            proof = job.terminate_and_prove_empty()
            refs.assert_stopped()
            return proof
    finally:
        if job.job:
            job.terminate_and_prove_empty()


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
        values = [line_with_timeout(lines), line_with_timeout(lines)]
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
        receipt = line_with_timeout(PipeLines(owner.stderr))
        expected = 'deadline' if mode == 'timeout' else 'caller_pipe_eof'
        need(receipt['reason'] == expected and receipt['closure']['active_processes'] == 0,
             'probe_supervisor_reason_or_closure_failed')
        return {'reason': receipt['reason'], 'active_processes': 0, 'descendants_stopped': True,
                'all_members_tracked': len(members), 'observer_job_active_processes': 0}
    finally:
        # This runs even on handshake failure and proves all created processes
        # stopped before the probe reports failure. It does not explain PASS:
        # assertions above observe an empty outer Job before cleanup terminates.
        owner.terminate_and_prove_empty()
        if refs:
            refs.close()


def parent_death_check():
    # Outer probe retains stdin's write side after killing the intermediary
    # owner: EOF cannot explain the supervisor's parent_death observation.
    owner = JobProcess(command('--parent-owner'))
    refs = None
    try:
        lines = PipeLines(owner.stdout)
        values = [line_with_timeout(lines), line_with_timeout(lines), line_with_timeout(lines)]
        tree = next(v for v in values if 'child' in v)
        identity = next(v for v in values if 'job_owner' in v)
        supervisor_pid = identity['job_owner']
        members = stable_members(owner)
        need(all(pid in members for pid in (tree['child'], tree['grandchild'], supervisor_pid)), 'probe_membership_missing_tree')
        refs = ProcessRefs(members)
        kill_actual_process(identity['native_parent_pid'])
        assert_job_empty(owner)
        refs.assert_stopped()
        receipt = line_with_timeout(PipeLines(owner.stderr))
        need(receipt['reason'] == 'parent_death' and receipt['closure']['active_processes'] == 0,
             'probe_parent_death_not_observed')
        return {'reason': 'parent_death', 'active_processes': 0, 'descendants_stopped': True,
                'caller_pipe_kept_open': True, 'actual_native_parent_killed': True,
                'all_members_tracked': len(members),
                'observer_job_active_processes': 0}
    finally:
        owner.terminate_and_prove_empty()
        if refs:
            refs.close()


def child_mode(args):
    if args[0] == '--grandchild':
        time.sleep(60); return 0
    if args[0] == '--tree':
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
            'python_executable_sha256': PYTHON_SHA256}, sort_keys=True) + '\n').encode('ascii'))
        return 2
    import msvcrt
    for fd in (0, 1, 2):
        msvcrt.setmode(fd, os.O_BINARY)
    if len(sys.argv) > 1:
        return child_mode(sys.argv[1:])
    checks = {}; all_ok = True
    cases = [('metadata', metadata_checks), ('mutex', lock_check), ('job_tree', job_check),
             ('deadline', lambda: supervisor_check('timeout')),
             ('pipe_eof', lambda: supervisor_check('pipe_eof')),
             ('supervisor_kill', lambda: supervisor_check('supervisor_kill')),
             ('parent_death', parent_death_check)]
    for name, check in cases:
        try:
            checks[name] = {'ok': True, 'result': check()}
        except WindowsGuardError as exc:
            all_ok = False
            checks[name] = {'ok': False, 'reason': str(exc), 'win32_error': C.get_last_error()}
        except BaseException:
            all_ok = False
            checks[name] = {'ok': False, 'reason': 'probe_internal_error'}
    unchanged = all(public_hash(HERE / name, 1024 * 1024) == digest for name, digest in SOURCE_HASHES.items())
    checks['source_unchanged'] = {'ok': unchanged}
    all_ok = all_ok and unchanged
    result = {'format': 'irisx/windows-native-probe-v1', 'ok': all_ok,
        'native_windows': True, 'network_used': False, 'real_auth_accessed': False, 'checks': checks,
        'source_sha256': SOURCE_HASHES, 'python_version': PYTHON_VERSION,
        'python_executable_sha256': PYTHON_SHA256}
    code = 0 if all_ok else 1
    os.write(1, (json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
    return code


if __name__ == '__main__':
    os._exit(main())

"""Bounded synthetic WSL caller-death acceptance; no SDK, auth, or network.

Run under WSL Python, alongside the exact reviewed four native source files:
  python3 -I -B wsl_native_probe.py --native-python /mnt/c/.../python.exe \
    --native-probe 'C:\\...\\native_probe.py' --python-sha256 HEX \
    --base-python-sha256 HEX --pyvenv-cfg-sha256 HEX

Use --pyvenv-cfg-sha256 none only for an explicitly non-venv diagnostic. The
receipt identifies that fact and cannot substitute for final venv acceptance.
An independent Windows observer proves every captured process handle stopped
and its outer Job is empty before cleanup. Killing a WSL process alone is never
accepted as Windows closure proof. This is synthetic pipe/interop evidence,
not production bootstrap, authentication, provider, or execution readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
from pathlib import Path
import queue
import re
import signal
import stat
import subprocess
import sys
import threading
import time

SOURCE_NAMES = ('win_runtime.py', 'win_supervisor.py', 'native_probe.py', 'protocol.py')
HEX = re.compile(r'[0-9a-f]{64}\Z')
MAX_LINE = 65536


class ProbeError(RuntimeError):
    pass


def need(value, code):
    if not value:
        raise ProbeError(code)


def file_hash(path, cap):
    path = Path(path).absolute()
    for component in reversed((path, *path.parents)):
        row = component.lstat()
        need(not stat.S_ISLNK(row.st_mode) and not getattr(row, 'st_file_attributes', 0) & 0x400,
             'wsl_probe_public_path_alias')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode)
         and 0 < info.st_size <= cap, 'wsl_probe_public_file_invalid')
    with path.open('rb') as stream:
        data = stream.read(cap + 1)
    need(len(data) == info.st_size, 'wsl_probe_public_file_changed')
    return hashlib.sha256(data).hexdigest()



def native_probe_path(value):
    """Only the explicit standard WSL drive mapping; no guessed translations."""
    need(type(value) is str and 3 <= len(value) <= 4096, 'wsl_probe_native_script_path')
    drive, tail = ntpath.splitdrive(value)
    parts = tail[1:].split('\\') if tail.startswith('\\') else []
    need(re.fullmatch('[A-Za-z]:', drive) and parts
         and ntpath.normpath(value) == value and parts[-1] == 'native_probe.py'
         and not any(c in tail for c in ':*?<>|"\x00/')
         and all(part and part not in ('.', '..') and not part.endswith((' ', '.')) for part in parts),
         'wsl_probe_native_script_path')
    return Path('/mnt') / drive[0].lower() / Path(*parts)


def verify_native_sources(value, expected):
    mapped = native_probe_path(value)
    for name in SOURCE_NAMES:
        need(file_hash(mapped.with_name(name), 1024 * 1024) == expected[name],
             'wsl_probe_native_prelaunch_source_mismatch')
    return mapped

def strict_json(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_LINE, 'wsl_probe_line_bounds')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'wsl_probe_duplicate_json')
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode('ascii'), object_pairs_hook=pairs,
            parse_constant=lambda _: need(False, 'wsl_probe_nonfinite_json'))
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeError('wsl_probe_json_invalid') from None
    need(type(value) is dict, 'wsl_probe_json_object')
    return value


def bounded_line(stream, deadline):
    result = queue.Queue(maxsize=1)
    def reader():
        try:
            result.put(stream.readline(MAX_LINE + 1))
        except BaseException:
            result.put(b'')
    threading.Thread(target=reader, daemon=True).start()
    try:
        data = result.get(timeout=max(0, deadline - time.monotonic()))
    except queue.Empty:
        raise ProbeError('wsl_probe_native_response_timeout') from None
    need(data.endswith(b'\n'), 'wsl_probe_native_response_truncated')
    return strict_json(data)


def verify_bindings(value, expected):
    need(value.get('native_windows') is True and value.get('source_sha256') == expected['source_sha256'],
         'wsl_probe_native_source_mismatch')
    for name in ('python_executable_sha256', 'python_base_executable_sha256', 'pyvenv_cfg_sha256'):
        need(value.get(name) == expected[name], 'wsl_probe_native_runtime_mismatch')
    need(type(value.get('python_version')) is str and re.fullmatch(r'3\.12\.[0-9]{1,2}', value['python_version']),
         'wsl_probe_native_version')


def verify_closure(value, expected):
    verify_bindings(value, expected)
    need(value.get('format') == 'irisx/wsl-native-observer-result-v1' and value.get('ok') is True
         and value.get('scope') == 'synthetic_wsl_caller_death_pipe_eof_job_closure'
         and value.get('network_used') is False and value.get('real_auth_accessed') is False
         and value.get('caller_pipe_eof_observed') is True
         and type(value.get('observer_job_active_processes')) is int
         and value['observer_job_active_processes'] == 0
         and value.get('original_member_handles_stopped') is True
         and type(value.get('all_members_tracked')) is int and value['all_members_tracked'] >= 3
         and value.get('source_unchanged') is True, 'wsl_probe_closure_unproven')
    supervisor = value.get('supervisor')
    need(type(supervisor) is dict and supervisor.get('reason') == 'caller_pipe_eof',
         'wsl_probe_wrong_native_stop_reason')
    closure = supervisor.get('closure')
    need(type(closure) is dict and type(closure.get('active_processes')) is int
         and closure == {'format': 'irisx/windows-job-closure-v1', 'active_processes': 0,
         'kill_on_close': True, 'breakaway_permitted': False, 'atomic_job_assignment': True},
         'wsl_probe_supervisor_job_unproven')
    return value


def hold_writer(fd):
    # The only process holding the write end lives no longer than 30 seconds,
    # including if the harness itself disappears before its explicit SIGKILL.
    try:
        os.fstat(fd)
        os.write(1, b'{"caller_ready":true}\n')
        time.sleep(30)
    finally:
        os.close(fd)
    return 0


def run(args):
    need(os.name == 'posix' and 'microsoft' in os.uname().release.lower(), 'wsl_native_probe_requires_wsl')
    native = Path(args.native_python)
    need(native.is_absolute() and native.name.lower() == 'python.exe'
         and '.kaggle' not in (part.casefold() for part in native.parts), 'wsl_probe_native_executable_path')
    native_probe_path(args.native_probe)
    for value in (args.python_sha256, args.base_python_sha256):
        need(HEX.fullmatch(value), 'wsl_probe_hash_invalid')
    cfg_sha = None if args.pyvenv_cfg_sha256 == 'none' else args.pyvenv_cfg_sha256
    need(cfg_sha is None or HEX.fullmatch(cfg_sha), 'wsl_probe_cfg_hash_invalid')
    need(file_hash(native, 128 * 1024 * 1024) == args.python_sha256, 'wsl_probe_executable_hash')
    here = Path(__file__).absolute().parent
    expected = {'source_sha256': {name: file_hash(here / name, 1024 * 1024) for name in SOURCE_NAMES},
        'python_executable_sha256': args.python_sha256,
        'python_base_executable_sha256': args.base_python_sha256, 'pyvenv_cfg_sha256': cfg_sha}
    # Verify the bytes at the exact Windows execution path BEFORE starting any
    # native script. A post-execution self-reported hash is not admission.
    mapped_probe = verify_native_sources(args.native_probe, expected['source_sha256'])
    own_hash = file_hash(__file__, 1024 * 1024)
    deadline = time.monotonic() + 35
    caller = observer = None
    read_fd = write_fd = None
    try:
        read_fd, write_fd = os.pipe()
        caller = subprocess.Popen([sys.executable, '-I', '-B', str(Path(__file__).absolute()),
            '--hold-writer', str(write_fd)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, pass_fds=(write_fd,), close_fds=True)
        os.close(write_fd); write_fd = None
        need(bounded_line(caller.stdout, deadline) == {'caller_ready': True}, 'wsl_probe_caller_start_failed')
        observer = subprocess.Popen([str(native), '-I', '-B', args.native_probe, '--wsl-observer'],
            stdin=read_fd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            close_fds=True, start_new_session=True)
        os.close(read_fd); read_fd = None
        ready = bounded_line(observer.stdout, deadline)
        verify_bindings(ready, expected)
        need(ready.get('format') == 'irisx/wsl-native-observer-ready-v1'
             and type(ready.get('member_count')) is int and ready['member_count'] >= 3,
             'wsl_probe_native_observer_not_ready')
        roles = ready.get('roles')
        need(type(roles) is dict and set(roles) == {'job_owner', 'native_parent_pid', 'child', 'grandchild'}
             and all(type(pid) is int and pid > 0 for pid in roles.values()), 'wsl_probe_native_roles_invalid')
        # Do not close the writer gracefully: prove its owning WSL process dies.
        caller.kill()
        need(caller.wait(timeout=5) == -signal.SIGKILL, 'wsl_probe_caller_not_killed')
        result = verify_closure(bounded_line(observer.stdout, deadline), expected)
        need(observer.wait(timeout=max(0.1, deadline - time.monotonic())) == 0, 'wsl_probe_native_observer_failed')
        need(file_hash(__file__, 1024 * 1024) == own_hash
             and all(file_hash(here / name, 1024 * 1024) == digest for name, digest in expected['source_sha256'].items()),
             'wsl_probe_local_source_changed')
        verify_native_sources(args.native_probe, expected['source_sha256'])
        return {'format': 'irisx/wsl-native-caller-death-probe-v1', 'ok': True,
            'scope': 'synthetic_wsl_caller_death_pipe_eof_job_closure',
            'wsl_caller_sigkill_observed': True, 'observer_survived_caller': True,
            'harness_sha256': own_hash, 'native_observer': result,
            'network_used': False, 'real_auth_accessed': False,
            'production_bootstrap_tested': False}
    finally:
        for fd in (read_fd, write_fd):
            if fd is not None:
                os.close(fd)
        if caller is not None and caller.poll() is None:
            caller.kill(); caller.wait(timeout=5)
        if observer is not None and observer.poll() is None:
            # A missing native receipt remains UNKNOWN. The native observer's
            # own finite synthetic lease/Job cleanup is not inferred from this.
            observer.terminate()
            try:
                observer.wait(timeout=5)
            except subprocess.TimeoutExpired:
                observer.kill(); observer.wait(timeout=5)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[0] == '--hold-writer':
        return hold_writer(int(argv[1]))
    parser = argparse.ArgumentParser(description='Synthetic WSL caller-death native Job probe')
    parser.add_argument('--native-python', required=True)
    parser.add_argument('--native-probe', required=True)
    parser.add_argument('--python-sha256', required=True)
    parser.add_argument('--base-python-sha256', required=True)
    parser.add_argument('--pyvenv-cfg-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except ProbeError as exc:
        result = {'format': 'irisx/wsl-native-caller-death-probe-v1', 'ok': False,
            'reason': str(exc), 'native_closure': 'UNVERIFIED',
            'network_used': False, 'real_auth_accessed': False}
    except BaseException:
        result = {'format': 'irisx/wsl-native-caller-death-probe-v1', 'ok': False,
            'reason': 'wsl_probe_internal_error', 'native_closure': 'UNVERIFIED',
            'network_used': False, 'real_auth_accessed': False}
    os.write(1, (json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    os._exit(main())

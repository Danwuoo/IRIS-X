"""Bounded, no-auth Windows boot observations, never restart attestation.

Invoke the source-verified script with native Python -I -B, or call observe_boot
from a source-verified native worker BEFORE authentication. The caller owns any
publication mutex and its outer process/deadline boundary. This module owns only
its fixed local PowerShell child Job. No event logs, auth files, SDK, provider,
network, restart command, or historical state are accessed.

MachineGuid, firmware UUID, and OS install date are read only inside the fixed
child, challenge-salted together, and discarded. Only the digest leaves it.
These are trusted-OS observations, not hardware attestation: cloned metadata,
VM snapshots, clock changes, and controlled-Restart provenance require separate
epoch checks. An observation cannot close or upgrade an old UNKNOWN session.
Linux tests are synthetic policy tests and provide no native Windows proof.
"""
from __future__ import annotations

import argparse
import base64
import ctypes as C
import hashlib
import json
import math
import ntpath
import os
import re
import stat
import sys
import threading
import time
import types
from datetime import datetime, timezone
from pathlib import Path

FORMAT = 'irisx/windows-recovery-boot-observation-v1'
OUTPUT_CAP = 8192
QUERY_CAP = 2048
STDERR_CAP = 1024
SOURCE_CAP = 1024 * 1024
RUNTIME_CAP = 128 * 1024 * 1024
SOURCE_NAMES = frozenset(('recovery_boot_probe.py', 'win_runtime.py'))
RUNTIME_NAMES = frozenset(('python', 'base_python'))
SAFE_FACTS = {'auth_started': False, 'credential_contents_accessed': False,
              'provider_calls': 0, 'network_used': False}
CLOSURE = {'format': 'irisx/windows-job-closure-v1', 'active_processes': 0,
           'kill_on_close': True, 'breakaway_permitted': False,
           'atomic_job_assignment': True}
OBSERVATION_KEYS = frozenset(('format', 'ok', 'challenge', 'host_install_sha256',
    'observed_utc', 'last_boot_utc', 'tick_count64_ms', 'windows_version',
    'windows_build', 'source_sha256', 'runtime_sha256',
    'native_process_closure_verified', 'closure', *SAFE_FACTS))

# Fixed program, not a command template. The only stdin is 64 hex characters
# plus LF and EOF. No user-provided path, script, class, property, or CIM server
# is accepted. Explicit module path and a minimal child environment preclude
# user profile/module search. Registry access is exactly one read-only value.
POWERSHELL_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$WarningPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'
try {
    $chars = [Array]::CreateInstance([char], 65)
    for ($i = 0; $i -lt 65; $i++) {
        $v = [Console]::In.Read()
        if ($v -lt 0) { throw 'input' }
        $chars[$i] = [char]$v
    }
    if ($chars[64] -ne [char]10 -or [Console]::In.Read() -ne -1) { throw 'input' }
    $challenge = -join $chars[0..63]
    if ($challenge -cnotmatch '^[0-9a-f]{64}$') { throw 'input' }
    $module = [IO.Path]::Combine([Environment]::SystemDirectory,
        'WindowsPowerShell\v1.0\Modules\CimCmdlets\CimCmdlets.psd1')
    Microsoft.PowerShell.Core\Import-Module -Name $module -ErrorAction Stop
    $osItems = @(CimCmdlets\Get-CimInstance -ClassName Win32_OperatingSystem `
        -Property LastBootUpTime,Version,BuildNumber,InstallDate -OperationTimeoutSec 5)
    $sysItems = @(CimCmdlets\Get-CimInstance -ClassName Win32_ComputerSystemProduct `
        -Property UUID -OperationTimeoutSec 5)
    if ($osItems.Count -ne 1 -or $sysItems.Count -ne 1) { throw 'count' }
    $osInfo = $osItems[0]
    $uuid = ([Guid]([string]$sysItems[0].UUID)).ToString('D').ToLowerInvariant()
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
    try {
        $key = $base.OpenSubKey('SOFTWARE\Microsoft\Cryptography', $false)
        if ($null -eq $key) { throw 'key' }
        try {
            $machine = ([Guid]([string]$key.GetValue('MachineGuid', $null,
                [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames))).ToString('D').ToLowerInvariant()
        } finally { $key.Dispose() }
    } finally { $base.Dispose() }
    foreach ($id in @($machine, $uuid)) {
        if ($id -eq '00000000-0000-0000-0000-000000000000' -or
            $id -eq 'ffffffff-ffff-ffff-ffff-ffffffffffff') { throw 'identity' }
    }
    $culture = [Globalization.CultureInfo]::InvariantCulture
    $dateFormat = "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'"
    if ($osInfo.LastBootUpTime -isnot [DateTime] -or $osInfo.InstallDate -isnot [DateTime]) { throw 'time' }
    $boot = $osInfo.LastBootUpTime.ToUniversalTime().ToString($dateFormat, $culture)
    $installed = $osInfo.InstallDate.ToUniversalTime().ToString($dateFormat, $culture)
    $version = [string]$osInfo.Version
    $build = [string]$osInfo.BuildNumber
    if ($version -cnotmatch '^[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,10}$' -or
        $build -cnotmatch '^[0-9]{1,10}$' -or $version.Split('.')[2] -cne $build) { throw 'version' }
    $material = "irisx/windows-host-install-v1`n$challenge`n$machine`n$uuid`n$installed`n"
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $digest = [BitConverter]::ToString($hasher.ComputeHash(
        [Text.Encoding]::ASCII.GetBytes($material))).Replace('-', '').ToLowerInvariant() }
    finally { $hasher.Dispose() }
    $machine = $uuid = $material = $installed = $null
    $result = '{"challenge":"' + $challenge + '","host_install_sha256":"' + $digest +
        '","last_boot_utc":"' + $boot + '","windows_build":"' + $build +
        '","windows_version":"' + $version + '"}'
    [Console]::Out.Write($result + [char]10)
    exit 0
} catch { exit 1 }
'''


class ProbeError(RuntimeError):
    """Only a fixed local diagnostic and an independently checked closure."""
    def __init__(self, code, *, closure=None):
        if type(code) is not str or not re.fullmatch('boot_[a-z0-9_]{1,80}', code):
            code = 'boot_observation_failed'
        super().__init__(code)
        self.code = code
        self.closure = closure if _closure_valid(closure) else None


def need(condition, code):
    if not condition:
        raise ProbeError(code)


def _closure_valid(value):
    return (type(value) is dict and set(value) == set(CLOSURE)
            and all(type(value[k]) is type(v) and value[k] == v for k, v in CLOSURE.items()))


def canonical_bytes(value):
    try:
        raw = (json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    except (TypeError, ValueError, RecursionError):
        raise ProbeError('boot_output_invalid') from None
    need(0 < len(raw) <= OUTPUT_CAP, 'boot_output_limit')
    return raw


def _hex(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _bindings(challenge, sources, runtime):
    need(_hex(challenge), 'boot_challenge_invalid')
    for value, keys in ((sources, SOURCE_NAMES), (runtime, RUNTIME_NAMES)):
        need(type(value) is dict and set(value) == keys
             and all(_hex(digest) for digest in value.values()), 'boot_bindings_invalid')


def _strict_json(raw, cap):
    need(type(raw) is bytes and 0 < len(raw) <= cap and raw.endswith(b'\n')
         and raw.count(b'\n') == 1, 'boot_output_framing')
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'boot_output_duplicate_key')
            value[key] = item
        return value
    def constant(_):
        raise ProbeError('boot_output_invalid')
    try:
        value = json.loads(raw.decode('ascii'), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeError('boot_output_invalid') from None
    need(type(value) is dict, 'boot_output_object_required')
    need(raw == canonical_bytes(value), 'boot_output_noncanonical')
    return value


def _timestamp(value):
    need(type(value) is str and re.fullmatch(
        r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z', value),
        'boot_timestamp_invalid')
    try:
        result = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
    except ValueError:
        raise ProbeError('boot_timestamp_invalid') from None
    need(result.year >= 2000, 'boot_timestamp_invalid')
    return result


def _validate_query(value, challenge):
    need(set(value) == {'challenge', 'host_install_sha256', 'last_boot_utc',
                        'windows_version', 'windows_build'}, 'boot_query_fields')
    need(value['challenge'] == challenge and _hex(value['challenge']), 'boot_challenge_mismatch')
    need(_hex(value['host_install_sha256']), 'boot_host_digest_invalid')
    _timestamp(value['last_boot_utc'])
    version, build = value['windows_version'], value['windows_build']
    need(type(version) is str and re.fullmatch(r'[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,10}', version)
         and type(build) is str and re.fullmatch('[0-9]{1,10}', build)
         and version.split('.')[2] == build, 'boot_windows_version_invalid')


def validate_observation(raw, *, challenge, expected_source_sha256, expected_runtime_sha256):
    """Pure closed-schema validator. Validation alone is not native provenance."""
    _bindings(challenge, expected_source_sha256, expected_runtime_sha256)
    value = _strict_json(raw, OUTPUT_CAP)
    need(set(value) == OBSERVATION_KEYS, 'boot_observation_fields')
    need(value['format'] == FORMAT and value['ok'] is True, 'boot_observation_failed')
    _validate_query({key: value[key] for key in ('challenge', 'host_install_sha256',
        'last_boot_utc', 'windows_version', 'windows_build')}, challenge)
    need(value['source_sha256'] == expected_source_sha256
         and value['runtime_sha256'] == expected_runtime_sha256, 'boot_bindings_mismatch')
    need(value['native_process_closure_verified'] is True and _closure_valid(value['closure']),
         'boot_native_closure_unverified')
    need(all(type(value[key]) is type(wanted) and value[key] == wanted
             for key, wanted in SAFE_FACTS.items()), 'boot_scope_mismatch')
    ticks = value['tick_count64_ms']
    need(type(ticks) is int and 0 <= ticks <= 0xffffffffffffffff, 'boot_tick_count_invalid')
    observed, boot = _timestamp(value['observed_utc']), _timestamp(value['last_boot_utc'])
    elapsed = (observed - boot).total_seconds()
    need(elapsed >= 0 and abs(elapsed - ticks / 1000) <= 120, 'boot_time_inconsistent')
    return value


def _bootstrap_read(path, cap):
    """No-reparse bootstrap read; execute the exact hashed bytes, never reload."""
    path = Path(path).absolute()
    for part in reversed((path, *path.parents)):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'boot_source_reparse')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= cap,
         'boot_source_file_invalid')
    with path.open('rb') as source:
        raw = source.read(cap + 1)
    need(len(raw) == info.st_size and len(raw) <= cap, 'boot_source_size_invalid')
    return raw


def _load_runtime(path, expected_sha256):
    need(_hex(expected_sha256), 'boot_bindings_invalid')
    raw = _bootstrap_read(path, SOURCE_CAP)
    need(hashlib.sha256(raw).hexdigest() == expected_sha256, 'boot_source_hash_mismatch')
    name = '_irisx_recovery_boot_verified_runtime'
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(Path(path).absolute()), ''
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(raw, module.__file__, 'exec', dont_inherit=True,
                     optimize=sys.flags.optimize), vars(module))
        return module
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


def _verify_bytes(win, sources, runtime):
    directory = Path(__file__).absolute().parent
    for name, digest in sources.items():
        need(hashlib.sha256(win.read_source(str(directory / name), SOURCE_CAP)).hexdigest() == digest,
             'boot_source_hash_mismatch')
    paths = {'python': sys.executable,
             'base_python': getattr(sys, '_base_executable', None) or sys.executable}
    for name, path in paths.items():
        need(ntpath.basename(path).casefold() == 'python.exe', 'boot_python_path_invalid')
        need(hashlib.sha256(win.read_source(path, RUNTIME_CAP)).hexdigest() == runtime[name],
             'boot_runtime_hash_mismatch')


def _system_command(win):
    a = win.api()
    fn = a.k.GetSystemDirectoryW
    fn.argtypes, fn.restype = [C.c_wchar_p, C.c_uint32], C.c_uint32
    buffer = C.create_unicode_buffer(32768)
    size = fn(buffer, len(buffer))
    need(0 < size < len(buffer), 'boot_system_directory_invalid')
    system = win.strict_local_path(buffer.value)
    need(ntpath.basename(system).casefold() == 'system32', 'boot_system_directory_invalid')
    root = ntpath.dirname(system)
    powershell = ntpath.join(system, 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    # Trust the existing OS component; reject path redirection, no PATH lookup.
    # This is metadata-only, unlike the independently pinned Python/source reads.
    for part in reversed((Path(powershell), *Path(powershell).parents)):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'boot_system_component_reparse')
    need(stat.S_ISREG(Path(powershell).stat().st_mode), 'boot_system_component_invalid')
    command = [powershell, '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand',
               base64.b64encode(POWERSHELL_SCRIPT.encode('utf-16-le')).decode('ascii')]
    environment = {'SystemRoot': root, 'WINDIR': root, 'PATH': system,
                   'PSModulePath': ntpath.join(system, 'WindowsPowerShell', 'v1.0', 'Modules')}
    return command, system, environment


def _ticks(win):
    fn = win.api().k.GetTickCount64
    fn.argtypes, fn.restype = [], C.c_uint64
    return int(fn())


def _run_query(win, challenge, *, deadline, cleanup_reserve):
    """Drain bounded pipes; always terminate/query the entire child Job."""
    job = None
    closure = None
    failure = None
    output = bytearray()
    threads = []
    faults = []
    stderr_seen = threading.Event()
    fault_lock = threading.Lock()
    def fault(code):
        with fault_lock:
            if not faults:
                faults.append(code)
    def drain(pipe, cap, collect):
        count = 0
        try:
            while True:
                block = pipe.read(min(1024, cap + 1 - count))
                if not block:
                    return
                count += len(block)
                if count > cap:
                    fault('boot_output_limit' if collect else 'boot_stderr_limit')
                    return
                if collect:
                    output.extend(block)
                else:
                    stderr_seen.set()
        except BaseException:
            fault('boot_pipe_failed')
    def write_challenge():
        try:
            job.stdin.write((challenge + '\n').encode('ascii'))
            job.stdin.close()
        except BaseException:
            fault('boot_pipe_failed')
    try:
        command, cwd, environment = _system_command(win)
        with win.ParentWatch() as parent:
            need(not parent.dead(), 'boot_parent_dead')
            need(time.monotonic() < deadline - cleanup_reserve, 'boot_deadline')
            job = win.JobProcess(command, cwd=cwd, env=environment)
            for target, args in ((drain, (job.stdout, QUERY_CAP, True)),
                                 (drain, (job.stderr, STDERR_CAP, False)),
                                 (write_challenge, ())):
                thread = threading.Thread(target=target, args=args, daemon=True,
                                          name='recovery-boot-bounded-pipe')
                thread.start()
                threads.append(thread)
            while True:
                need(time.monotonic() < deadline - cleanup_reserve, 'boot_deadline')
                need(not parent.dead(), 'boot_parent_dead')
                if faults:
                    raise ProbeError(faults[0])
                code = job.poll()
                if code is not None:
                    need(type(code) is int and code == 0, 'boot_query_failed')
                    break
                time.sleep(0.01)
    except BaseException as error:
        failure = error if type(error) is ProbeError else ProbeError('boot_query_failed')
    finally:
        if job is not None:
            try:
                # KILL_ON_JOB_CLOSE remains enforced even if the query fails.
                proof = job.terminate_and_prove_empty(
                    timeout=max(0.01, min(cleanup_reserve / 2, deadline - time.monotonic())),
                    close_pipes=False)
                need(_closure_valid(proof), 'boot_native_closure_unverified')
                closure = dict(proof)
            except BaseException:
                failure = ProbeError('boot_native_closure_unverified')
            finally:
                try:
                    for thread in threads:
                        thread.join(max(0.0, deadline - time.monotonic()))
                    if any(thread.is_alive() for thread in threads):
                        failure = failure or ProbeError('boot_pipe_drain_timeout')
                finally:
                    job._close_handles()
    if failure is None and faults:
        failure = ProbeError(faults[0])
    if failure is None and stderr_seen.is_set():
        failure = ProbeError('boot_query_stderr')
    if failure is not None:
        raise ProbeError(failure.code, closure=closure) from None
    need(_closure_valid(closure), 'boot_native_closure_unverified')
    return bytes(output), closure


def observe_boot(challenge, *, expected_source_sha256, expected_runtime_sha256, timeout_seconds=15):
    """Collect freshly, before auth; return a strict success or fixed ProbeError.

    timeout_seconds includes reserved child cleanup. The caller's outer native
    supervisor is still required to bound blocking OS/bootstrap file syscalls.
    No cached observation, production mutex, or caller command is accepted.
    """
    started = time.monotonic()
    closure = None
    try:
        _bindings(challenge, expected_source_sha256, expected_runtime_sha256)
        need(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds)
             and 1 <= timeout_seconds <= 30, 'boot_timeout_invalid')
        need(os.name == 'nt' and sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1
             and sys.flags.ignore_environment == 1 and C.sizeof(C.c_void_p) == 8,
             'boot_native_isolated_windows_required')
        deadline = started + timeout_seconds
        need(hashlib.sha256(_bootstrap_read(__file__, SOURCE_CAP)).hexdigest()
             == expected_source_sha256['recovery_boot_probe.py'], 'boot_source_hash_mismatch')
        win = _load_runtime(Path(__file__).absolute().with_name('win_runtime.py'),
                            expected_source_sha256['win_runtime.py'])
        _verify_bytes(win, expected_source_sha256, expected_runtime_sha256)
        raw, closure = _run_query(win, challenge, deadline=deadline,
                                 cleanup_reserve=min(2.0, timeout_seconds / 3))
        query = _strict_json(raw, QUERY_CAP)
        _validate_query(query, challenge)
        tick_count = _ticks(win)
        observed = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        _verify_bytes(win, expected_source_sha256, expected_runtime_sha256)
        need(time.monotonic() < deadline, 'boot_deadline')
        result = {'format': FORMAT, 'ok': True, **query, 'observed_utc': observed,
                  'tick_count64_ms': tick_count, 'source_sha256': dict(expected_source_sha256),
                  'runtime_sha256': dict(expected_runtime_sha256),
                  'native_process_closure_verified': True, 'closure': closure, **SAFE_FACTS}
        return validate_observation(canonical_bytes(result), challenge=challenge,
            expected_source_sha256=expected_source_sha256, expected_runtime_sha256=expected_runtime_sha256)
    except BaseException as error:
        if type(error) is ProbeError:
            raise ProbeError(error.code, closure=closure or error.closure) from None
        raise ProbeError('boot_observation_failed', closure=closure) from None


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ProbeError('boot_arguments_invalid')


def main(argv=None):
    try:
        parser = _Parser(add_help=False, allow_abbrev=False)
        parser.add_argument('--challenge', required=True)
        parser.add_argument('--probe-sha256', required=True)
        parser.add_argument('--runtime-sha256', required=True)
        parser.add_argument('--python-sha256', required=True)
        parser.add_argument('--base-python-sha256', required=True)
        parser.add_argument('--timeout-seconds', type=float, default=15)
        args = parser.parse_args(argv)
        result = observe_boot(args.challenge,
            expected_source_sha256={'recovery_boot_probe.py': args.probe_sha256,
                                    'win_runtime.py': args.runtime_sha256},
            expected_runtime_sha256={'python': args.python_sha256, 'base_python': args.base_python_sha256},
            timeout_seconds=args.timeout_seconds)
    except BaseException as error:
        failure = error if type(error) is ProbeError else ProbeError('boot_observation_failed')
        result = {'format': FORMAT, 'ok': False, 'reason': failure.code,
                  'native_process_closure_verified': failure.closure is not None,
                  'closure': failure.closure, **SAFE_FACTS}
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(1, os.O_BINARY)
    raw = canonical_bytes(result)
    offset = 0
    while offset < len(raw):
        written = os.write(1, raw[offset:])
        if written <= 0:
            return 1
        offset += written
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    # A broken/closed destination must not produce a traceback containing local
    # paths. It cannot be reported on that same destination; exit unsuccessfully.
    try:
        exit_code = main()
    except BaseException:
        exit_code = 1
    os._exit(exit_code)

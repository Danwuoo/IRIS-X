"""WSL diagnostic of the unchanged native production CLI, ending BEFORE auth.

The only transmitted frame is open. After the source/credential-METADATA ready
frame, input is closed without ready_ack. The worker cannot enter SDK import or
authentication. A matching native Job-zero receipt is mandatory; a WSL proxy
exit/kill is never closure evidence. This probe cannot admit production actions.

All seven native sources are hard-pinned independently of the supplied config.
The local and mapped native copies, config, native/base executable and pyvenv.cfg
are checked before launch. No credentials, SDK package or network client is read
or imported by this probe. Actual SDK source verification is the worker's ready
barrier; authentication remains unreachable because no acknowledgement is sent.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import json
import math
import ntpath
import os
from pathlib import Path, PureWindowsPath
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import types

FORMAT = 'irisx/windows-production-cli-preauth-probe-v1'
BOOT_OBSERVER_SHA256 = '46bc3f0b8c47dd53e7da0db58de01f39fc078811e9372fcc803a52db8b496b31'
SOURCE_SHA256 = {
    'win_runtime.py': '7280b755d3155fb3d5d4f9989c0ea592d7a0d8be8750d635360f06fe766db69d',
    'win_supervisor.py': 'f2c8ff86424a993ff7e6a22e056cdf11ffb5d0969b64947d138c08f7c00a7001',
    'protocol.py': '5f67b8655497565cb149dbd7bd4aa675be8cec058089295f0d2a75873787cf24',
    'native_config.py': '5008d989004f2c99948a157f9fda09f6ce751ee93c07ce39f1659f3789fb9fe8',
    'native_auth.py': '785e696dc702e5042f415e3da1bd3fbf43ff34f3f8a579a702ec2f262aefdcd4',
    'sdk_worker.py': 'bd75a7a221b58d7c3723cb98a3f3485135da2a69b2f518683cd9e30eefe29dcd',
    'sdk-lock.json': '3d447ab7fad280fcc378fd18b57c3792c5b39798127f583679646027ab73288d',
}
HEX = re.compile(r'[0-9a-f]{64}\Z')
RECEIPT_CAP = 4096
CLOSURE_WAIT = 5.0
FORBIDDEN_BASENAMES = frozenset(('credentials.json', 'kaggle.json', 'oauth.json',
                               'access_token', 'access_token.txt'))


class ProbeError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(value, code):
    if not value:
        raise ProbeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def public_path(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and not str(path).startswith('//'),
         'preauth_public_path')
    need('.kaggle' not in (part.casefold() for part in path.parts)
         and path.name.casefold() not in FORBIDDEN_BASENAMES, 'preauth_credential_path_forbidden')
    for component in (path, *path.parents):
        need(not component.is_symlink(), 'preauth_source_symlink')
    return path


def bounded_read(path, cap):
    path = public_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and 0 < before.st_size <= cap, 'preauth_public_file')
    def identity(value):
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        need(identity(before) == identity(opened), 'preauth_file_changed')
        raw = stream.read(cap + 1)
        need(len(raw) == before.st_size and identity(before) == identity(os.fstat(stream.fileno()))
             == identity(path.lstat()), 'preauth_file_changed')
    return raw


def native_to_wsl(value):
    need(type(value) is str and 0 < len(value) <= 4096
         and not any(ord(c) < 32 for c in value), 'preauth_native_path')
    path = PureWindowsPath(value)
    need(re.fullmatch('[A-Za-z]:', path.drive) is not None and path.is_absolute()
         and str(path) == value and ntpath.normpath(value) == value,
         'preauth_native_path')
    need(all(part not in ('', '.', '..') and not any(c in part for c in ':*?<>|"')
             and not part.endswith((' ', '.')) for part in path.parts[1:]), 'preauth_native_path')
    mapped = Path('/mnt/' + path.drive[0].lower() + '/' + '/'.join(path.parts[1:]))
    need('.kaggle' not in (part.casefold() for part in mapped.parts)
         and mapped.name.casefold() not in FORBIDDEN_BASENAMES, 'preauth_credential_path_forbidden')
    return mapped


def source_module(name, raw, path):
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def bootstrap_pins(raw):
    tree = ast.parse(raw)
    pins = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name) and target.id in ('WIN_RUNTIME_SHA256', 'NATIVE_CONFIG_SHA256'):
                need(target.id not in pins and isinstance(statement.value, ast.Constant)
                     and type(statement.value.value) is str, 'preauth_bootstrap_pin_schema')
                pins[target.id] = statement.value.value
    need(pins == {'WIN_RUNTIME_SHA256': SOURCE_SHA256['win_runtime.py'],
                  'NATIVE_CONFIG_SHA256': SOURCE_SHA256['native_config.py']},
         'preauth_bootstrap_pin_mismatch')


def prepare(args, *, source_root=None):
    """Public-file verification only. This does not launch any process."""
    here = public_path(Path(__file__).absolute().parent if source_root is None else source_root)
    source = {}
    for name, expected in SOURCE_SHA256.items():
        raw = bounded_read(here / name, 1024 * 1024)
        need(sha(raw) == expected, 'preauth_local_source_hash')
        source[name] = raw
    for name in ('sdk_worker.py', 'win_supervisor.py'):
        bootstrap_pins(source[name])
    config_module = source_module('preauth_reviewed_native_config', source['native_config.py'], here / 'native_config.py')
    protocol = source_module('preauth_reviewed_protocol', source['protocol.py'], here / 'protocol.py')
    need(type(args.native_config_sha256) is str and HEX.fullmatch(args.native_config_sha256), 'preauth_config_hash')
    config_path = native_to_wsl(args.native_config)
    raw_config = bounded_read(config_path, 1024 * 1024)
    need(sha(raw_config) == args.native_config_sha256, 'preauth_config_hash')
    document = config_module.validate_document(config_module.strict_json(raw_config))
    expected_sources = dict(SOURCE_SHA256)
    if document.get('format') == 'irisx/run008-windows-sdk-recovery-runtime-v1':
        expected_sources['recovery_boot_probe.py'] = BOOT_OBSERVER_SHA256
        source['recovery_boot_probe.py'] = bounded_read(here / 'recovery_boot_probe.py', 1024 * 1024)
        need(sha(source['recovery_boot_probe.py']) == BOOT_OBSERVER_SHA256, 'preauth_local_source_hash')
    need(set(document['sources']) == set(expected_sources), 'preauth_source_closure')
    native_root = native_to_wsl(document['source_root'])
    snapshots = {str(config_path): {'sha256': sha(raw_config), 'cap': 1024 * 1024}}
    for name, expected in expected_sources.items():
        descriptor = document['sources'][name]
        need(descriptor == {'bytes': len(source[name]), 'sha256': expected}, 'preauth_config_source_binding')
        native_path = native_root / name
        raw = bounded_read(native_path, 1024 * 1024)
        need(raw == source[name], 'preauth_native_source_hash')
        snapshots[str(native_path)] = {'sha256': expected, 'cap': 1024 * 1024}
        snapshots[str(here / name)] = {'sha256': expected, 'cap': 1024 * 1024}
    spec = document['runtime']
    native_python = native_to_wsl(spec['executable']['path'])
    need(str(native_python) == args.native_python and native_python.name.lower() == 'python.exe',
         'preauth_executable_mapping')
    need(args.native_supervisor == ntpath.join(document['source_root'], 'win_supervisor.py'),
         'preauth_supervisor_mapping')
    for descriptor in (spec['executable'], spec['base_executable']):
        path = native_to_wsl(descriptor['path'])
        need(sha(bounded_read(path, 128 * 1024 * 1024)) == descriptor['sha256'], 'preauth_executable_hash')
        snapshots[str(path)] = {'sha256': descriptor['sha256'], 'cap': 128 * 1024 * 1024}
    cfg = native_to_wsl(ntpath.join(spec['venv_prefix'], 'pyvenv.cfg'))
    need(sha(bounded_read(cfg, 65536)) == spec['pyvenv_cfg_sha256'], 'preauth_pyvenv_hash')
    snapshots[str(cfg)] = {'sha256': spec['pyvenv_cfg_sha256'], 'cap': 65536}
    ca = document['requests_ca_bundle']
    if ca is not None:
        path = native_to_wsl(ca['path'])
        need(sha(bounded_read(path, 16 * 1024 * 1024)) == ca['sha256'], 'preauth_ca_hash')
        snapshots[str(path)] = {'sha256': ca['sha256'], 'cap': 16 * 1024 * 1024}
    return {'protocol': protocol, 'document': document, 'snapshots': snapshots,
        'expected_sources': expected_sources,
        'config_sha256': args.native_config_sha256, 'source_root': here,
        'executable': args.native_python, 'supervisor': args.native_supervisor,
        'native_config': args.native_config}


@contextmanager
def wall_bound(seconds):
    need(threading.current_thread() is threading.main_thread() and 0 < seconds <= 125,
         'preauth_wall_bound')
    old_handler, old_timer = signal.getsignal(signal.SIGALRM), signal.getitimer(signal.ITIMER_REAL)
    start = time.monotonic()
    def timeout(*unused):
        raise ProbeError('preauth_timeout')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, min(seconds, old_timer[0]) if old_timer[0] else seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, max(0.000001, old_timer[0] - (time.monotonic() - start)), old_timer[1])


class Pipes:
    """Fixed production argv, bounded receipt drain; no raw stderr is exposed."""
    def __init__(self, argv):
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False, close_fds=True, bufsize=0)
        self.reader, self.writer = self.process.stdout, self.process.stdin
        self.receipt, self.receipt_failed = bytearray(), False
        def drain():
            try:
                while True:
                    block = self.process.stderr.read(4096)
                    if not block:
                        break
                    if len(self.receipt) + len(block) > RECEIPT_CAP:
                        self.receipt_failed = True
                    elif not self.receipt_failed:
                        self.receipt.extend(block)
            except BaseException:
                self.receipt_failed = True
        self.thread = threading.Thread(target=drain, daemon=True, name='preauth-safe-receipt')
        self.thread.start()

    def finish(self, timeout):
        start = time.monotonic()
        code = self.process.wait(timeout=timeout)
        self.thread.join(max(0, timeout - (time.monotonic() - start)))
        need(not self.thread.is_alive() and not self.receipt_failed, 'preauth_receipt_unavailable')
        # The supervisor has exited and closed its writer. Any byte following
        # ready is unexpected and cannot be treated as pre-auth success.
        need(self.reader.read(1) == b'', 'preauth_unexpected_trailing_frame')
        return code, bytes(self.receipt)

    def release(self):
        for stream in (self.writer, self.reader, self.process.stderr):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
        if self.process.poll() is None:
            # Reaping an interop proxy is cleanup, never native closure proof.
            try:
                self.process.kill()
                self.process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.thread.join(0.1)


def closure_receipt(protocol, nonce, code, raw):
    need(type(raw) is bytes and 0 < len(raw) <= RECEIPT_CAP and raw.endswith(b'\n')
         and raw.count(b'\n') == 1, 'preauth_receipt_bytes')
    value = protocol.strict_json(raw)
    need(set(value) == {'format', 'nonce', 'ok', 'reason', 'closure'}
         and value['format'] == 'irisx/windows-supervisor-result-v1' and value['nonce'] == nonce,
         'preauth_receipt_identity')
    need(type(code) is int and code == 124 and value['ok'] is False
         and value['reason'] in {'caller_pipe_eof', 'worker_exit'}, 'preauth_expected_stop_reason')
    closure = value['closure']
    need(type(closure) is dict and set(closure) == {'format', 'active_processes', 'kill_on_close',
         'breakaway_permitted', 'atomic_job_assignment'}
         and closure['format'] == 'irisx/windows-job-closure-v1'
         and type(closure['active_processes']) is int and closure['active_processes'] == 0
         and closure['kill_on_close'] is True and closure['breakaway_permitted'] is False
         and closure['atomic_job_assignment'] is True, 'preauth_native_closure_unverified')
    return {'reason': value['reason'], 'exit_code': code, 'closure': closure}


def exercise(prepared, *, timeout_seconds=120, transport_factory=None):
    """No branch or callback can send ready_ack; synthetic transport is test-only."""
    need(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds)
         and 1 <= timeout_seconds <= 120, 'preauth_timeout_bounds')
    protocol = prepared['protocol']
    nonce = protocol.new_nonce()
    recovery = prepared['document'].get('recovery')
    if recovery is not None:
        timeout_seconds = min(timeout_seconds, recovery['expires_epoch'] - time.time())
        need(timeout_seconds >= 1, 'preauth_recovery_expired')
    deadline_epoch = time.time() + timeout_seconds
    if recovery is not None:
        deadline_epoch = min(deadline_epoch, recovery['expires_epoch'])
    deadline = time.monotonic() + timeout_seconds
    config_sha = prepared['config_sha256']
    diagnostic_config = sha(b'irisx/preauth-no-operator-contract-v1\n' + config_sha.encode('ascii'))
    diagnostic_manifest = sha(b'irisx/preauth-no-publication-contract-v1\n' + config_sha.encode('ascii'))
    arguments = {'account': 'danielwuu', 'versions': dict(prepared['document']['versions']),
        'configuration_sha256': diagnostic_config, 'bridge_configuration_sha256': config_sha,
        'publication_manifest_sha256': diagnostic_manifest,
        'deadline_epoch': deadline_epoch, 'max_seconds': timeout_seconds}
    if recovery is not None:
        arguments['recovery'] = {key: recovery[key] for key in ('capability_sha256', 'reservation_sha256')}
    digest = protocol.request_hash('open', arguments, deadline_epoch=deadline_epoch,
                                   max_seconds=timeout_seconds)
    argv = [prepared['executable'], '-I', '-B', prepared['supervisor'], '--config',
        prepared['native_config'], '--config-sha', config_sha, '--nonce', nonce,
        '--deadline-epoch', repr(deadline_epoch), '--max-seconds', repr(timeout_seconds)]
    transport = None
    ready = closure = None
    failure = None
    try:
        with wall_bound(timeout_seconds):
            transport = Pipes(argv) if transport_factory is None else transport_factory(protocol, nonce, argv)
            channel = protocol.FramedIO(transport.reader, transport.writer, nonce=nonce, deadline=deadline)
            # This is deliberately the ONLY send in the diagnostic.
            channel.send('request', {'operation': 'open', 'arguments': arguments,
                'deadline_epoch': deadline_epoch, 'max_seconds': timeout_seconds},
                sequence=1, request_sha256=digest)
            message = channel.receive(kinds={'ready'}, sequence=1, request_sha256=digest)
            ready = message['payload']
            need(ready == {'sdk_lock_sha256': SOURCE_SHA256['sdk-lock.json'], 'sdk_source_count': 170,
                'account': 'danielwuu', 'existing_official_store': True}, 'preauth_ready_binding')
    except BaseException as error:
        failure = error.code if isinstance(error, ProbeError) else 'preauth_protocol_or_bootstrap_failure'
    finally:
        if transport is not None:
            try:
                # No acknowledgement is sent, even on timeout or unexpected data.
                transport.writer.close()
                with wall_bound(CLOSURE_WAIT):
                    code, raw = transport.finish(CLOSURE_WAIT)
                    closure = closure_receipt(protocol, nonce, code, raw)
            except BaseException:
                if failure is None:
                    failure = 'preauth_native_closure_unverified'
            finally:
                transport.release()
    result = {'format': FORMAT, 'nonce': nonce,
        'ok': failure is None and ready is not None and closure is not None,
        'scope': 'production_cli_source_and_credential_metadata_before_auth_only',
        'synthetic_contract_bindings': True, 'synthetic_transport': transport_factory is not None,
        'real_operator_contract_tested': False, 'production_execution_admitted': False,
        'ready_ack_sent': False, 'auth_started': False, 'sdk_imported': False,
        'credential_contents_accessed': False, 'provider_calls': 0, 'network_used': False,
        'native_configuration_sha256': config_sha,
        'source_sha256': dict(prepared.get('expected_sources', SOURCE_SHA256)),
        'recovery_boot_mode': recovery is not None,
        'python_executable_sha256': prepared['document']['runtime']['executable']['sha256'],
        'python_base_executable_sha256': prepared['document']['runtime']['base_executable']['sha256'],
        'pyvenv_cfg_sha256': prepared['document']['runtime']['pyvenv_cfg_sha256'],
        'diagnostic_configuration_sha256': diagnostic_config,
        'diagnostic_manifest_sha256': diagnostic_manifest,
        'ready_verified': ready is not None, 'native_process_closure_verified': closure is not None,
        'native_closure': closure}
    if failure is not None:
        result['reason'] = failure
    return result


def run(args):
    need(os.name == 'posix' and 'microsoft' in os.uname().release.lower(), 'preauth_requires_wsl')
    prepared = prepare(args)
    own_sha = sha(bounded_read(Path(__file__).absolute(), 1024 * 1024))
    result = exercise(prepared, timeout_seconds=args.timeout_seconds)
    # Public source/runtime bytes must still match after native Job closure.
    try:
        for path, descriptor in prepared['snapshots'].items():
            need(sha(bounded_read(path, descriptor['cap'])) == descriptor['sha256'], 'preauth_source_changed_after')
        need(sha(bounded_read(Path(__file__).absolute(), 1024 * 1024)) == own_sha, 'preauth_source_changed_after')
        result['sources_unchanged'] = True
    except BaseException:
        result.update(ok=False, sources_unchanged=False, reason='preauth_source_changed_after')
    result['harness_sha256'] = own_sha
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='No-auth production Windows bridge CLI probe')
    parser.add_argument('--native-python', required=True)
    parser.add_argument('--native-supervisor', required=True)
    parser.add_argument('--native-config', required=True)
    parser.add_argument('--native-config-sha256', required=True)
    parser.add_argument('--timeout-seconds', type=float, default=120)
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except BaseException as error:
        result = {'format': FORMAT, 'ok': False,
            'reason': error.code if isinstance(error, ProbeError) else 'preauth_validation_failure',
            'native_process_closure_verified': False, 'ready_ack_sent': False, 'auth_started': False,
            'credential_contents_accessed': False, 'provider_calls': 0, 'network_used': False,
            'real_operator_contract_tested': False, 'production_execution_admitted': False}
    os.write(1, (json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    os._exit(main())

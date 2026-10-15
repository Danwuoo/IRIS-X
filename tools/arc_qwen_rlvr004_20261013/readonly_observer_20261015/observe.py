"""One bounded native read-only bracket for the already accepted v43.

This separate capability never admits publication or resolves an older session.
Run only after independent review of helper/config/accepted-metadata SHA256s.
Credentials stay in the unchanged official Windows store. Refresh is forbidden.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time
import types

PINS = {
    'win_runtime.py': '7280b755d3155fb3d5d4f9989c0ea592d7a0d8be8750d635360f06fe766db69d',
    'native_config.py': '5008d989004f2c99948a157f9fda09f6ce751ee93c07ce39f1659f3789fb9fe8',
    'win_supervisor.py': '5a58f0434499a1b1d0bfb176588a99d31e3da224e1c91486ff306288cd7e9bf2',
    'sdk_worker.py': 'f37a219ed51ec5f2e54816d6e45479ce7cbeeb09eb608184b31a0727da46ea11',
    'native_auth.py': '785e696dc702e5042f415e3da1bd3fbf43ff34f3f8a579a702ec2f262aefdcd4',
    'protocol.py': '5f67b8655497565cb149dbd7bd4aa675be8cec058089295f0d2a75873787cf24',
    'sdk-lock.json': '3d447ab7fad280fcc378fd18b57c3792c5b39798127f583679646027ab73288d',
}
REFERENCE = 'danielwuu/iris-x-learning-agent-20261011'
KERNEL_ID, VERSION, CODE_VERSION = 138123872, 43, 22
SOURCE_SHA256 = 'e834dd924eef286e830f3d3d2a73dc0e0547f4ee756b8ebd60f793d97f8f644d'
CONFIG_SHA256 = 'ec32867044bd6de4f8cead0cc6d9f73a45419c1a091dbe3cdbdfadaf669fe0f9'
METADATA_SHA256 = '0a22a9193407c049cbbceeb01f8ea9c5385d2a1855d0f97a6371adfa8a364106'
CLOCK = {'original_epoch': 1792092816, 'execution_deadline': 1792134816,
         'outer_deadline': 1792134996, 'global_deadline': 1792136016}
TERMINAL = frozenset(('COMPLETE', 'ERROR', 'CANCEL_ACKNOWLEDGED', 'CANCELLED', 'CANCELED'))
STATUS = TERMINAL | {'UNKNOWN', 'QUEUED', 'RUNNING', 'CANCEL_REQUESTED', 'NEW_SCRIPT'}
# First release deliberately has no output/download or storage capability.
RPC_PATHS = frozenset('/v1/kernels.KernelsApiService/' + name
                      for name in ('GetKernel', 'GetKernelSessionStatus'))
RPC_URLS = frozenset(host + path for host in ('https://api.kaggle.com',
                    'https://api.kaggle.com:443') for path in RPC_PATHS)
MAX_SECONDS, MAX_RESULT = 300, 65536


class ObserverError(ValueError):
    pass


def need(value, code):
    if not value:
        raise ObserverError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda unused: need(False, 'nonfinite_json'))


def no_links(path):
    path = Path(path).absolute()
    need('..' not in path.parts, 'parent_path_segment')
    for item in reversed((path, *path.parents)):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'linked_path_forbidden')
    return path


def read_pinned(path, digest, cap=1024 * 1024):
    need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'sha256_required')
    path = no_links(path)
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= cap,
         'bounded_ordinary_file_required')
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    need(len(raw) == info.st_size and sha(raw) == digest, 'source_hash_mismatch')
    no_links(path)
    return raw


def pinned_module(name, path, digest):
    raw = read_pinned(path, digest)
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(Path(path).absolute()), ''
    sys.modules[name] = module
    try:
        exec(compile(raw, module.__file__, 'exec', dont_inherit=True,
                     optimize=sys.flags.optimize), vars(module))
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


class ReadonlyRuntime:
    def __init__(self, runtime):
        self.runtime = runtime
        self.refresh_denied_before_write_guard = False

    def __getattr__(self, name):
        return getattr(self.runtime, name)

    @contextmanager
    def credential_guard(self, *, allow_write=False):
        need(type(allow_write) is bool, 'credential_guard_mode')
        if allow_write:
            self.refresh_denied_before_write_guard = True
            raise ObserverError('existing_credential_requires_refresh')
        with self.runtime.credential_guard(allow_write=False) as guard:
            yield guard


class NoRefresh:
    def check_ready(self):
        return None

    def intent(self, unused):
        raise ObserverError('refresh_forbidden')

    def accepted(self, unused):
        raise ObserverError('refresh_forbidden')


def readonly_request(request):
    need(request.method == 'POST' and request.url in RPC_URLS, 'readonly_rpc_required')


def bind_readonly(boundary, client, auth, deadline):
    boundary.bind(client, auth)
    session = client.http_client()._session
    bounded = session.send
    def send(request, **kwargs):
        need(time.monotonic() < deadline, 'observer_deadline')
        readonly_request(request)
        return bounded(request, **kwargs)
    session.send = send


def accepted_metadata(raw):
    value = strict_json(raw)
    need(type(value) is dict, 'accepted_metadata_object')
    meta = value
    need(type(meta) is dict and meta.get('id') == KERNEL_ID and type(meta.get('id')) is int
         and meta.get('ref') == REFERENCE and meta.get('currentVersionNumber') == VERSION
         and type(meta.get('currentVersionNumber')) is int and meta.get('isPrivate') is True
         and meta.get('enableGpu') is True and meta.get('enableTpu') is False
         and meta.get('enableInternet') is False and meta.get('machineShape') == 'NvidiaRtxPro6000',
         'accepted_v43_metadata_required')
    return meta


def validate_kernel(value, expected):
    need(type(value) is dict and set(value) == {'metadata', 'blob'}
         and value['metadata'] == expected, 'v43_metadata_changed')
    blob = value['blob']
    need(type(blob) is dict and set(blob) == {'source'} and type(blob['source']) is str
         and sha(blob['source'].encode('utf-8')) == SOURCE_SHA256, 'v43_source_changed')


def observe(provider, expected, *, wall=time.time):
    started = wall()
    before = provider.kernel()
    validate_kernel(before, expected)
    status = provider.status()
    need(type(status) is dict and set(status) == {'status', 'failureMessage'}
         and status['status'] in STATUS and status['failureMessage'] in ('', 'Provider error', 'GPU unavailable'),
         'bounded_status_required')
    after = provider.kernel()
    validate_kernel(after, expected)
    finished = wall()
    need(CLOCK['original_epoch'] <= started <= finished < CLOCK['global_deadline'], 'original_clock_bound')
    return {'reference': REFERENCE, 'kernel_id': KERNEL_ID, 'numeric_version': VERSION,
            'code_version': CODE_VERSION, 'saved_source_sha256': SOURCE_SHA256,
            'metadata_sha256': sha(canonical(expected)), 'status': status['status'],
            'failure_message': status['failureMessage'], 'terminal': status['status'] in TERMINAL,
            'started_epoch': started, 'observed_epoch': finished, 'clock': CLOCK,
            'source_and_metadata_bracket_verified': True,
            'remote_process_closure_verified': False, 'billing_verified': False,
            'scientific_success_verified': False, 'old_native_session_closure_verified': False}


def bootstrap(args):
    need(os.name == 'nt' and sys.platform == 'win32' and sys.flags.isolated == 1
         and sys.flags.dont_write_bytecode == 1 and sys.flags.ignore_environment == 1,
         'isolated_native_windows_required')
    read_pinned(__file__, args.helper_sha)
    need(args.config_sha == CONFIG_SHA256 and args.accepted_metadata_sha == METADATA_SHA256,
         'fixed_accepted_input_hashes_required')
    root = Path(args.bridge_root).absolute()
    for name, digest in PINS.items():
        read_pinned(root / name, digest)
    win = pinned_module('win_runtime', root / 'win_runtime.py', PINS['win_runtime.py'])
    need(sha(win.read_source(str(Path(__file__).absolute()), 1024 * 1024)) == args.helper_sha,
         'native_helper_bytes')
    config = pinned_module('native_config', root / 'native_config.py', PINS['native_config.py'])
    runtime = config.load_runtime(args.config, args.config_sha)
    need(runtime.recovery is None and Path(runtime.source_root) == root, 'original_native_config_required')
    need(runtime.versions == {'code_predecessor': 21, 'code': 22, 'inactive_predecessor': 41,
                              'inactive': 42, 'active': 43}, 'accepted_versions_required')
    raw = win.read_source(args.accepted_metadata, 1024 * 1024)
    need(len(raw) == 923 and sha(raw) == args.accepted_metadata_sha, 'accepted_metadata_hash')
    expected = accepted_metadata(raw)
    return root, win, runtime, expected


def worker(args):
    root, win, runtime, expected = bootstrap(args)
    win.require_worker_job(args.nonce)
    need(0 < args.deadline_epoch - time.time() <= MAX_SECONDS
         and args.deadline_epoch <= CLOCK['global_deadline'], 'worker_lease')
    deadline = time.monotonic() + args.deadline_epoch - time.time()
    sdk = pinned_module('observer_sdk_worker', root / 'sdk_worker.py', PINS['sdk_worker.py'])
    auth_module = pinned_module('observer_native_auth', root / 'native_auth.py', PINS['native_auth.py'])
    facade = ReadonlyRuntime(runtime)
    boundary = sdk.HttpBoundary()
    auth = auth_module.OfficialSession(facade, NoRefresh(),
        lambda client, session: bind_readonly(boundary, client, session, deadline),
        lock_path=root / 'sdk-lock.json')
    result = {'format': 'irisx/v43-readonly-worker-v1', 'nonce': args.nonce,
              'request_sha256': args.request_sha, 'ok': False, 'observation': None,
              'old_native_session_closure_verified': False}
    with auth_module.isolate_sdk_output() as (_, writer):
        try:
            auth.prepare()
            auth.protocol_ready()
            auth.open()
            provider = sdk.WorkerProvider(auth, runtime.versions)
            result['observation'] = observe(provider, expected)
            result['ok'] = True
        except auth_module.AuthRefreshUnknown:
            result.update(error='AUTH_REFRESH_UNKNOWN', mutation_uncertain=True,
                          refresh_denied_before_write_guard=facade.refresh_denied_before_write_guard)
        except BaseException:
            result.update(error='readonly_observation_failed', mutation_uncertain=False)
        finally:
            auth.close()
        raw = canonical(result)
        need(len(raw) <= MAX_RESULT, 'result_bound')
        writer.write(raw)
        writer.flush()
    return 0 if result['ok'] else 2


def write_new(path, value):
    raw = canonical(value)
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def observation_output(path, native_root):
    output = Path(path).absolute()
    no_links(output.parent)
    need(not any(part.casefold().startswith('state') for part in output.parts)
         and not output.is_relative_to(Path(native_root).absolute()), 'state_or_source_output_forbidden')
    output.mkdir()  # Exclusive new directory; no original state or receipt writes.
    no_links(output)
    return output


def supervise(args, argv):
    started = time.monotonic()
    root, win, runtime, unused = bootstrap(args)
    supervisor = pinned_module('observer_win_supervisor', root / 'win_supervisor.py', PINS['win_supervisor.py'])
    supervisor._install_runtime(win)
    supervisor.MAX_STREAM_BYTES = MAX_RESULT
    now = time.time()
    need(CLOCK['original_epoch'] <= now < CLOCK['global_deadline'], 'original_global_deadline')
    deadline_epoch = min(now + MAX_SECONDS, CLOCK['global_deadline'])
    lease = min(started + MAX_SECONDS, time.monotonic() + deadline_epoch - now)
    output = observation_output(args.output, root)
    nonce = secrets.token_hex(32)
    request = {'format': 'irisx/v43-readonly-launch-v1', 'nonce': nonce,
               'helper_sha256': args.helper_sha, 'native_config_sha256': args.config_sha,
               'accepted_metadata_sha256': args.accepted_metadata_sha, 'clock': CLOCK,
               'deadline_epoch': deadline_epoch, 'max_seconds': MAX_SECONDS,
               'scope': 'v43-source-bound-status-only-no-refresh',
               'old_native_session_closure_verified': False}
    request_sha = write_new(output / 'launch.json', request)
    receipt = {'format': 'irisx/v43-readonly-supervisor-v1', 'nonce': nonce,
               'request_sha256': request_sha, 'ok': False, 'closure': None,
               'reason': 'observer_supervision_failed', 'old_native_session_closure_verified': False}
    # This new private pipe is only a relay hold-open, not caller-EOF evidence.
    # The real native parent handle and total Job lease enforce lifetime.
    input_fd, hold_open = os.pipe()
    code = 2
    try:
        child = [runtime.executable, '-I', '-B', str(Path(__file__).absolute()), *argv,
                 '--worker', '--nonce', nonce, '--request-sha', request_sha,
                 '--deadline-epoch', str(deadline_epoch)]
        with (output / 'worker-result.json').open('xb', buffering=0) as stream:
            result = supervisor.supervise(child, timeout_seconds=MAX_SECONDS,
                deadline_unix=deadline_epoch, lease_monotonic=lease,
                input_fd=input_fd, output_fd=stream.fileno(),
                scope='publication-worker-v1', protocol=None, nonce=nonce)
            os.fsync(stream.fileno())
        receipt.update(reason=result.reason, closure=result.closure)
        raw = (output / 'worker-result.json').read_bytes()
        need(0 < len(raw) <= MAX_RESULT, 'worker_result_bound')
        value = strict_json(raw)
        need(value.get('nonce') == nonce and value.get('request_sha256') == request_sha
             and value.get('format') == 'irisx/v43-readonly-worker-v1', 'worker_result_binding')
        receipt['worker_result_sha256'] = sha(raw)
        receipt['ok'] = result.code == 0 and value.get('ok') is True
        code = 0 if receipt['ok'] else 2
    except BaseException as error:
        if str(error) == 'windows_duplicate_worker':
            receipt['reason'] = 'original_mutex_exists_no_takeover'
    finally:
        os.close(hold_open)
        os.close(input_fd)
        write_new(output / 'supervisor-result.json', receipt)
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return code


def arguments(argv):
    flags = [arg.split('=', 1)[0] for arg in argv if arg.startswith('--')]
    need(len(argv) <= 40 and len(set(flags)) == len(flags), 'unambiguous_arguments')
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ('helper-sha', 'bridge-root', 'config', 'config-sha', 'accepted-metadata',
                 'accepted-metadata-sha', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--nonce')
    parser.add_argument('--request-sha')
    parser.add_argument('--deadline-epoch', type=float)
    args = parser.parse_args(argv)
    for key in ('helper_sha', 'config_sha', 'accepted_metadata_sha'):
        need(re.fullmatch('[0-9a-f]{64}', getattr(args, key)) is not None, 'argument_sha256')
    if args.worker:
        need(all(type(getattr(args, key)) is str and re.fullmatch('[0-9a-f]{64}', getattr(args, key))
                 for key in ('nonce', 'request_sha')) and type(args.deadline_epoch) is float
             and math.isfinite(args.deadline_epoch), 'worker_binding_arguments')
    else:
        need(args.nonce is args.request_sha is args.deadline_epoch is None, 'supervisor_only_arguments')
    return args


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = arguments(argv)
        return worker(args) if args.worker else supervise(args, argv)
    except BaseException:
        print('{"ok":false,"reason":"observer_bootstrap_failed"}', flush=True)
        return 2


if __name__ == '__main__':
    # Avoid waiting for the supervisor's bounded, disposable relay threads.
    os._exit(main())

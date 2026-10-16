"""Selected numeric-v43 retrieval; separate from collector/scientific admission.

One explicitly selected file per bounded native Job. Use only the reviewed
supervisor entry. The published status observer and accepted run stay unchanged.
--checkpoint-header observes only the fixed checkpoint response headers; it
accepts Location redirects and refuses JSON-body URL redirects without reading.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import sys
import time
import types

OBSERVER_SHA256 = '696cbfc6336fa208526352c4479bf3a32eb5a835d8fa75aca01a87ffa7346655'
MANIFEST_SHA256 = '619dc66bb9b4c1697c0753475ab3e68123d77edbc1d9b0737ba3cbd238db7442'
PREFIX = 'irisx-qwen14b-rlvr-20261013-run008'
TERMINAL_PATH = PREFIX + '.evidence.zip.terminal.json'
EVIDENCE_PATH = PREFIX + '.evidence.zip'
CHECKPOINT_PATH = PREFIX + '/checkpoints.zip'
# Only this reviewed predecessor and its actual completed terminal chain may
# supply the new header capability. This is not general old-helper admission.
HEADER_PREDECESSORS = frozenset({'1bdadfd56c68f53528babf64390295bb53965884bb9eacaff5f20a207e53d615'})
HEADER_TERMINAL_RECEIPT_SHA256 = 'c7aed6c2ea053b4dde32fdb280b36e6694f9da282b9db872abde53185082c697'
HEADER_TERMINAL_FILE = {'bytes': 119652, 'sha256': 'a95c964a8e29d5b27e067ac1a6ee66af7efe345cd55684f88ab11a0cf32092a7'}
CHECKPOINT_SOURCE = {'bytes': 1546535710, 'source_sha256': 'b0dee6ae07d742afb4b8b242bb9e82f7be862a3de6c015fbca96d801c1bfabd4'}
RESERVE = 4 * 1024**3
MAX_SECONDS = 300
SUPERVISOR_ERROR_CODES = frozenset({
    'worker_result_bound', 'worker_result_binding', 'new_job_closure_required',
    'terminal_source_bracket_required', 'terminal_bracket_clock', 'terminal_bracket_changed',
    'download_cap_type', 'bounded_download_file', 'download_file_changed', 'download_cap',
    'original_retrieval_deadline', 'closed_download_hash_changed', 'final_output_exists',
    'linked_path_forbidden',
    'checkpoint_header_result', 'checkpoint_body_forbidden', 'checkpoint_launch_binding',
    'checkpoint_header_worker_result',
})
HEADER_WORKER_STAGES = frozenset({
    'auth_prepare', 'auth_protocol_ready', 'auth_open', 'provider_setup',
    'checkpoint_before', 'checkpoint_output', 'checkpoint_rpc_headers',
    'checkpoint_storage_headers', 'checkpoint_validate_headers', 'checkpoint_after',
    'checkpoint_terminal_brackets', 'unexpected_stage',
})
HEADER_WORKER_ERRORS = frozenset({
    'AUTH_REFRESH_UNKNOWN', 'SELECTED_OUTPUT_PENDING_OR_MISSING',
    'PROVIDER_NOT_TERMINAL', 'selected_retrieval_failed',
})
# Deliberately fixed diagnostic vocabulary. Never serialize exception text,
# response objects, headers, signed URLs, credential/config values or paths.
HEADER_WORKER_ERROR_CODES = frozenset({
    'unexpected_error', 'auth_refresh_unknown', 'http_error',
    'checkpoint_json_body_forbidden', 'checkpoint_header_status',
    'checkpoint_header_length', 'checkpoint_header_encoding', 'provider_not_terminal',
    'original_retrieval_deadline', 'retrieval_deadline', 'readonly_retrieval_rpc_required',
    'terminal_source_bracket_required', 'terminal_bracket_clock', 'terminal_bracket_changed',
    'v43_metadata_changed', 'v43_source_changed', 'bounded_status_required', 'original_clock_bound',
    'existing_credential_requires_refresh', 'refresh_forbidden', 'alternate_auth_environment',
    'auth_already_prepared', 'source_verification_before_protocol_ready', 'protocol_ready_before_sdk_auth',
    'official_sdk_sysconfig_root', 'original_sdk_lock_changed', 'sdk_lock_duplicate_key',
    'sdk_lock_nonfinite', 'sdk_lock_schema', 'sdk_lock_distributions', 'sdk_source_count',
    'official_api_must_not_be_preimported', 'official_sdk_source_closure', 'sdk_distribution_version',
    'sdk_distribution_outside_bound_root',
    'official_sdk_import_missing', 'official_sdk_import_outside_bound_root',
    'official_sdk_unpinned_import', 'official_sdk_import_hash', 'native_auth_account',
    'native_api_account', 'native_official_oauth_required', 'new_oauth_login_not_authorized',
    'native_oauth_renew_failed', 'reviewed_version_schema', 'reviewed_version_sequence',
    'reviewed_numeric_output_version_required', 'worker_latched',
    'dto_string', 'dto_integer', 'dto_boolean', 'dto_list', 'dto_status',
    'official_rpc_route_required', 'unreviewed_rpc_operation', 'tls_verification_required',
    'storage_url_type', 'unsafe_storage_url', 'storage_host_not_allowed',
    'credential_forwarding', 'redirect_location_missing', 'redirect_limit',
    'download_status', 'download_declared_cap',
})


def header_stage(progress, stage):
    if progress is not None:
        progress['stage'] = stage


def header_failure(error, progress, status=None):
    code = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
    if code not in HEADER_WORKER_ERROR_CODES:
        code = 'http_error' if type(status) is int and 400 <= status <= 599 else 'unexpected_error'
    stage = progress.get('stage')
    return {'failure_stage': stage if type(stage) is str and stage in HEADER_WORKER_STAGES
            else 'unexpected_stage', 'error_code': code}


def need(value, code):
    if not value:
        raise ValueError(code)


def load_observer():
    path = Path(__file__).absolute().with_name('observe.py')
    for item in (path, *path.parents):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'observer_linked_source')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= 1024**2,
         'observer_source_file')
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == OBSERVER_SHA256, 'observer_source_hash')
    module = types.ModuleType('retrieval_status_observer')
    module.__file__, module.__package__ = str(path), ''
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


def selected_caps(manifest):
    terminal = manifest['terminal_contract']
    need(terminal['terminal_path'] == TERMINAL_PATH and terminal['evidence_path'] == EVIDENCE_PATH
         and terminal['checkpoint_path'] == PREFIX + '/checkpoints.zip', 'fixed_output_contract')
    archive_cap = terminal['archive_caps']['evidence_archive_bytes']
    need(type(archive_cap) is int and archive_cap == 5 * 1024**3 + 16 * 1024**2,
         'reviewed_archive_cap')
    caps = {TERMINAL_PATH: 16 * 1024**2, EVIDENCE_PATH: archive_cap}
    for name, cap in {'owner-request.json': 4*1024**2, 'owner-clock.json': 1024**2,
                      'artifact-inventory.json': 16*1024**2, 'outer-closure.json': 4*1024**2,
                      'owned-result.json': 4*1024**2}.items():
        caps[PREFIX + '/' + name] = cap
    outer = PREFIX + '-launcher'
    for name in ('outer.ipynb', 'original-request.json', 'operator.json', 'parent-private-scorer.json',
                 'preparation-request.json', 'preparation-receipt.json', 'installed-parent-request.json',
                 'interpreter-manifest.json', 'result.json'):
        caps[outer + '/' + name] = 4 * 1024**2
    caps[outer + '/startup-failure.json'] = 64 * 1024
    for name, cap in {'preparation-failure.json': 64*1024,
                      'preparation-stages.jsonl': 16*1024,
                      'installation-log-excerpt.bin': 128*1024}.items():
        caps[outer + '/preparation/' + name] = cap
    for stage in ('preparation', 'installed-parent'):
        caps[outer + '/' + stage + '/startup-failure.json'] = 64 * 1024
        for name in ('closure.json', 'owned-tree/launch.json', 'owned-tree/worker-launch.json',
                     'owned-tree/supervisor-result.json', 'owned-tree/closure.json'):
            caps[outer + '/' + stage + '/' + name] = 4 * 1024**2
        for name in ('stdout.txt', 'stderr.txt'):
            caps[outer + '/' + stage + '/' + name] = 8 * 1024**2
    return caps


def checkpoint_cap(manifest):
    need(manifest['terminal_contract']['checkpoint_path'] == CHECKPOINT_PATH,
         'fixed_checkpoint_path')
    cap = manifest['terminal_contract']['archive_caps']['checkpoint_archive_bytes']
    need(type(cap) is int and cap == 4 * 1024**3, 'reviewed_checkpoint_cap')
    return cap


def bootstrap(args):
    base = load_observer()
    base.read_pinned(__file__, args.helper_sha)
    original_args = types.SimpleNamespace(**vars(args))
    original_args.helper_sha = OBSERVER_SHA256
    root, win, runtime, expected = base.bootstrap(original_args)
    need(base.sha(win.read_source(str(Path(__file__).absolute()), 1024**2)) == args.helper_sha,
         'native_retrieval_helper_bytes')
    need(args.manifest_sha == MANIFEST_SHA256, 'fixed_manifest_hash_required')
    raw = win.read_source(args.manifest, 1024**2)
    need(len(raw) == 134508 and base.sha(raw) == MANIFEST_SHA256, 'original_manifest_bytes')
    manifest = base.strict_json(raw)
    caps = selected_caps(manifest)
    if args.checkpoint_header:
        need(args.name == CHECKPOINT_PATH, 'fixed_checkpoint_path')
        checkpoint_cap(manifest)
    else:
        need(args.name in caps, 'unreviewed_output_path')
    return base, root, win, runtime, expected, manifest, caps


def digest_file(base, path, cap, deadline):
    need(type(cap) is int and cap >= 0, 'download_cap_type')
    path = base.no_links(path)
    before = path.stat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    # Native Windows path and descriptor APIs can expose different ctime values.
    # Compare that field only within the same API, never drop its change check.
    cross_identity = (lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)) \
        if os.name == 'nt' else identity
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= cap,
         'bounded_download_file')
    hashed = hashlib.sha256()
    total = 0
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        need(cross_identity(opened) == cross_identity(before), 'download_file_changed')
        while True:
            need(time.monotonic() < deadline and time.time() < base.CLOCK['global_deadline'],
                 'original_retrieval_deadline')
            block = stream.read(1024**2)
            if not block:
                break
            total += len(block)
            need(total <= cap, 'download_cap')
            hashed.update(block)
        need(identity(os.fstat(stream.fileno())) == identity(opened), 'download_file_changed')
    need(identity(base.no_links(path).stat()) == identity(before) and total == before.st_size,
         'download_file_changed')
    return {'bytes': total, 'sha256': hashed.hexdigest()}


def new_job_closure(value):
    need(type(value) is dict and set(value) == {'format', 'active_processes', 'kill_on_close',
         'breakaway_permitted', 'atomic_job_assignment'}
         and value['format'] == 'irisx/windows-job-closure-v1'
         and type(value['active_processes']) is int and value['active_processes'] == 0
         and value['kill_on_close'] is True and value['breakaway_permitted'] is False
         and value['atomic_job_assignment'] is True, 'new_job_closure_required')


def terminal_brackets(base, before, after):
    for item in (before, after):
        need(type(item) is dict and item.get('reference') == base.REFERENCE
             and type(item.get('kernel_id')) is int and item['kernel_id'] == base.KERNEL_ID
             and type(item.get('numeric_version')) is int and item['numeric_version'] == 43
             and type(item.get('code_version')) is int and item['code_version'] == 22
             and item.get('saved_source_sha256') == base.SOURCE_SHA256
             and item.get('metadata_sha256') == base.METADATA_SHA256
             and item.get('status') in base.TERMINAL and item.get('terminal') is True
             and item.get('source_and_metadata_bracket_verified') is True
             and item.get('old_native_session_closure_verified') is False
             and item.get('clock') == base.CLOCK, 'terminal_source_bracket_required')
        need(all(type(item.get(key)) in (int, float) and math.isfinite(item[key])
                 for key in ('started_epoch', 'observed_epoch'))
             and base.CLOCK['original_epoch'] <= item['started_epoch'] <= item['observed_epoch']
             < base.CLOCK['global_deadline'], 'terminal_bracket_clock')
    need(before['status'] == after['status'] and before['observed_epoch'] <= after['started_epoch'],
         'terminal_bracket_changed')


def prior_terminal(base, args, cap, deadline, *, checkpoint_cap=None):
    """Bind archive expectations to an actual completed separate retrieval receipt."""
    need(args.terminal_receipt is not None and args.terminal_receipt_sha is not None,
         'prior_terminal_retrieval_required')
    raw = base.read_pinned(args.terminal_receipt, args.terminal_receipt_sha)
    receipt = base.strict_json(raw)
    prior_helper = receipt.get('helper_sha256')
    if checkpoint_cap is not None:
        need(args.terminal_receipt_sha == HEADER_TERMINAL_RECEIPT_SHA256
             and prior_helper in HEADER_PREDECESSORS, 'reviewed_header_predecessor_required')
    else:
        need(prior_helper == args.helper_sha, 'prior_terminal_receipt_binding')
    need(receipt.get('format') == 'irisx/v43-selected-retrieval-v1' and receipt.get('ok') is True
         and type(receipt.get('numeric_version')) is int and receipt['numeric_version'] == 43
         and receipt.get('reason') == 'worker_exit' and receipt.get('provider_path') == TERMINAL_PATH
         and receipt.get('manifest_sha256') == MANIFEST_SHA256
         and receipt.get('observer_sha256') == OBSERVER_SHA256
         and receipt.get('saved_source_sha256') == base.SOURCE_SHA256
         and receipt.get('native_config_sha256') == base.CONFIG_SHA256
         and receipt.get('clock') == base.CLOCK and receipt.get('download_finalized') is True,
         'prior_terminal_receipt_binding')
    new_job_closure(receipt.get('closure'))
    directory = Path(args.terminal_receipt).absolute().parent
    launch_raw = base.read_pinned(directory / 'launch.json', receipt.get('request_sha256'))
    launch = base.strict_json(launch_raw)
    need(launch.get('format') == 'irisx/v43-selected-launch-v1'
         and launch.get('nonce') == receipt.get('nonce')
         and type(launch.get('nonce')) is str and re.fullmatch('[0-9a-f]{64}', launch['nonce'])
         and launch.get('helper_sha256') == prior_helper
         and launch.get('observer_sha256') == OBSERVER_SHA256
         and launch.get('native_config_sha256') == base.CONFIG_SHA256
         and launch.get('accepted_metadata_sha256') == base.METADATA_SHA256
         and launch.get('manifest_sha256') == MANIFEST_SHA256
         and launch.get('provider_path') == TERMINAL_PATH
         and type(launch.get('numeric_version')) is int and launch['numeric_version'] == 43
         and launch.get('clock') == base.CLOCK
         and type(launch.get('cap')) is int and launch['cap'] == 16 * 1024**2
         and launch.get('expected_file') is None and launch.get('terminal_receipt_sha256') is None,
         'prior_terminal_launch_binding')
    need(type(launch.get('max_seconds')) is int and launch['max_seconds'] == MAX_SECONDS
         and launch.get('scope') == 'single-selected-output-no-refresh-no-admission'
         and type(launch.get('deadline_epoch')) in (int, float) and math.isfinite(launch['deadline_epoch'])
         and base.CLOCK['original_epoch'] < launch['deadline_epoch'] <= base.CLOCK['global_deadline'],
         'prior_terminal_launch_lease')
    worker_raw = base.read_pinned(directory / 'worker-result.json', receipt.get('worker_result_sha256'))
    worker_result = base.strict_json(worker_raw)
    need(type(worker_result) is dict and set(worker_result) == {'format', 'nonce', 'request_sha256', 'ok', 'download'}
         and worker_result['format'] == 'irisx/v43-selected-worker-v1' and worker_result['ok'] is True
         and worker_result['nonce'] == receipt['nonce']
         and worker_result['request_sha256'] == receipt['request_sha256'], 'prior_terminal_worker_binding')
    download = worker_result['download']
    need(type(download) is dict and set(download) == {'before', 'after', 'file'}
         and all(download[key] == receipt.get(key) for key in download), 'prior_terminal_result_binding')
    terminal_brackets(base, download['before'], download['after'])
    need(launch['deadline_epoch'] - MAX_SECONDS <= download['before']['started_epoch']
         <= download['after']['observed_epoch'] <= launch['deadline_epoch'], 'prior_terminal_observation_lease')
    row = receipt['file']
    need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int
         and 0 < row['bytes'] <= 16 * 1024**2, 'prior_terminal_file_descriptor')
    raw = base.read_pinned(directory / 'payload.bin', row['sha256'], 16 * 1024**2)
    need(len(raw) == row['bytes'] and time.monotonic() < deadline, 'prior_terminal_download_changed')
    if checkpoint_cap is not None:
        need(row == HEADER_TERMINAL_FILE, 'reviewed_header_terminal_required')
    terminal = base.strict_json(raw)
    need(terminal.get('format') == 'owned-rl-evidence-terminal-v1'
         and terminal.get('status') in ('complete', 'diagnostic')
         and terminal.get('mode') == 'runtime-reload-bound'
         and terminal.get('output_root') == '/kaggle/working/' + PREFIX
         and terminal.get('archive_complete') is True, 'terminal_archive_not_complete')
    archive = terminal.get('archive')
    need(type(archive) is dict and archive.get('path') == '/kaggle/working/' + EVIDENCE_PATH
         and type(archive.get('bytes')) is int and 0 < archive['bytes'] <= cap
         and type(archive.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', archive['sha256']),
         'terminal_archive_descriptor')
    if checkpoint_cap is None:
        return {'bytes': archive['bytes'], 'sha256': archive['sha256']}
    local = terminal.get('checkpoint_archive_observation')
    external = terminal.get('external_bodies', {}).get('checkpoints.zip')
    need(type(local) is dict and local.get('filename') == 'checkpoints.zip'
         and local.get('present') is True and type(local.get('byte_length')) is int
         and 0 < local['byte_length'] <= checkpoint_cap
         and local.get('transport_observation') == 'DECLARED_LOCAL_ARCHIVE_PRESENT'
         and local.get('body_materialized') is False
         and local.get('independently_sha256_verified') is False
         and local.get('observed_sha256') is None, 'checkpoint_source_declaration')
    need(type(external) is dict and external.get('reason') == 'separate-checkpoint-archive-body'
         and external.get('descriptor') == 'checkpoint-zip-descriptor.json'
         and type(external.get('original_bytes')) is int
         and type(external.get('local_observed_bytes')) is int
         and external['original_bytes'] == external['local_observed_bytes'] == local['byte_length']
         and external.get('local_presence_observed') is True
         and external.get('local_sha256_verified') is True
         and external.get('original_sha256') == external.get('local_observed_sha256')
         and external.get('archive_body_included') is False
         and external.get('external_body_materialized') is False
         and external.get('external_sha256_independently_verified') is False
         and external.get('external_observed_sha256') is None, 'checkpoint_source_descriptor')
    source = {'bytes': local['byte_length'], 'source_sha256': external['original_sha256']}
    need(source == CHECKPOINT_SOURCE, 'fixed_checkpoint_source_descriptor')
    return source


class DownloadOnly:
    def __init__(self, storage):
        self.storage = storage

    def download(self, response, cap):
        return self.storage.download(response, cap)

    def chunks(self, response, cap):
        return self.storage.chunks(response, cap)

    def header(self, response, cap):
        return self.storage.download(response, cap, metadata=True)

    def put(self, *unused, **unused_kwargs):
        raise ValueError('upload_forbidden')


def checkpoint_rpc_headers(response):
    # The pinned SDK eagerly consumes JSON RPC bodies. Header-only observation
    # accepts Location redirects, but intentionally declines JSON-body URLs.
    need('json' not in response.headers.get('Content-Type', '').lower()
         or 300 <= response.status_code < 400 and response.headers.get('Location'),
         'checkpoint_json_body_forbidden')


def bind_readonly(base, sdk, client, auth, deadline, *, checkpoint_header=False):
    session = client.http_client()._session
    output_urls = frozenset(host + '/v1/kernels.KernelsApiService/DownloadKernelOutput'
                           for host in ('https://api.kaggle.com', 'https://api.kaggle.com:443'))
    if checkpoint_header:
        raw_send = session.send
        def header_send(request, **kwargs):
            response = raw_send(request, **kwargs)
            if request.url in output_urls:
                try:
                    checkpoint_rpc_headers(response)
                except BaseException:
                    response.close()
                    raise
            return response
        session.send = header_send
    boundary = sdk.HttpBoundary()
    boundary.bind(client, auth)
    bounded = session.send
    urls = base.RPC_URLS | output_urls
    def send(request, **kwargs):
        need(time.monotonic() < deadline, 'retrieval_deadline')
        need(request.method == 'POST' and request.url in urls, 'readonly_retrieval_rpc_required')
        if checkpoint_header and request.url in output_urls:
            kwargs['stream'] = True
        return bounded(request, **kwargs)
    session.send = send


def retrieve_one(base, provider, storage, expected, name, cap, directory, deadline, expected_file=None):
    before = base.observe(provider, expected)
    need(before['terminal'] is True, 'provider_not_terminal')
    budget = expected_file['bytes'] if expected_file is not None else cap
    need(shutil.disk_usage(directory).free >= budget + RESERVE, 'download_disk_reserve')
    partial = Path(directory) / 'payload.part'
    need(not partial.exists() and not (Path(directory) / 'payload.bin').exists(), 'download_already_exists')
    response = provider.output(name, 43)
    hashed, size = hashlib.sha256(), 0
    with storage.download(response, budget) as response:
        need(response.headers.get('Content-Encoding', 'identity') in ('', 'identity'),
             'download_content_encoding')
        declared = response.headers.get('Content-Length')
        need(declared is None or type(declared) is str and re.fullmatch('[0-9]+', declared)
             and 0 <= int(declared) <= budget, 'download_declared_length')
        if expected_file is not None:
            need(declared is None or int(declared) == expected_file['bytes'], 'download_declared_expected_length')
        with partial.open('xb') as stream:
            for block in storage.chunks(response, budget):
                need(time.monotonic() < deadline and time.time() < base.CLOCK['global_deadline'],
                     'original_retrieval_deadline')
                size += len(block)
                need(size <= budget, 'download_cap')
                need(shutil.disk_usage(directory).free >= len(block) + RESERVE, 'download_disk_reserve')
                stream.write(block)
                hashed.update(block)
            stream.flush()
            os.fsync(stream.fileno())
        need(declared is None or size == int(declared), 'download_truncated')
        need(shutil.disk_usage(directory).free >= RESERVE, 'download_disk_reserve')
    row = {'bytes': size, 'sha256': hashed.hexdigest()}
    need(expected_file is None or row == expected_file, 'download_expected_bytes_or_sha')
    after = base.observe(provider, expected)
    terminal_brackets(base, before, after)
    return {'before': before, 'after': after, 'file': row}


def header_observation(size):
    return {'filename': 'checkpoints.zip', 'present': True, 'byte_length': size,
            'transport_observation': 'HTTP200_CONTENT_LENGTH_VERIFIED', 'http_status': 200,
            'body_consumed_bytes': 0, 'body_materialized': False,
            'independently_sha256_verified': False, 'observed_sha256': None}


def require_deadline(base, deadline):
    need(time.monotonic() < deadline and time.time() < base.CLOCK['global_deadline'],
         'original_retrieval_deadline')


def observe_checkpoint_header(base, provider, storage, expected, cap, source, deadline, *, progress=None):
    header_stage(progress, 'checkpoint_before')
    require_deadline(base, deadline)
    before = base.observe(provider, expected)
    need(before['terminal'] is True, 'provider_not_terminal')
    require_deadline(base, deadline)
    header_stage(progress, 'checkpoint_output')
    response = provider.output(CHECKPOINT_PATH, 43)
    try:
        header_stage(progress, 'checkpoint_rpc_headers')
        checkpoint_rpc_headers(response)
        header_stage(progress, 'checkpoint_storage_headers')
        with storage.header(response, cap) as response:
            header_stage(progress, 'checkpoint_validate_headers')
            require_deadline(base, deadline)
            need(response.status_code == 200, 'checkpoint_header_status')
            length = response.headers.get('Content-Length')
            need(type(length) is str and re.fullmatch('[0-9]+', length)
                 and 0 < int(length) == source['bytes'] <= cap, 'checkpoint_header_length')
            need(response.headers.get('Content-Encoding', 'identity') in ('', 'identity'),
                 'checkpoint_header_encoding')
            observation = header_observation(int(length))
    finally:
        response.close()
    header_stage(progress, 'checkpoint_after')
    require_deadline(base, deadline)
    after = base.observe(provider, expected)
    header_stage(progress, 'checkpoint_terminal_brackets')
    terminal_brackets(base, before, after)
    require_deadline(base, deadline)
    return {'before': before, 'after': after, 'checkpoint': observation}


def worker(args):
    base, root, win, runtime, expected, manifest, caps = bootstrap(args)
    win.require_worker_job(args.nonce)
    need(0 < args.deadline_epoch - time.time() <= MAX_SECONDS
         and args.deadline_epoch <= base.CLOCK['global_deadline'], 'worker_lease')
    deadline = time.monotonic() + args.deadline_epoch - time.time()
    directory = base.no_links(args.output)
    launch_raw = base.read_pinned(directory / 'launch.json', args.request_sha)
    launch = base.strict_json(launch_raw)
    need(launch.get('nonce') == args.nonce and launch.get('provider_path') == args.name,
         'worker_launch_binding')
    expected_file = prior_terminal(base, args, caps[args.name], deadline) if args.name == EVIDENCE_PATH else None
    source = None
    if args.checkpoint_header:
        cap = checkpoint_cap(manifest)
        source = prior_terminal(base, args, caps[EVIDENCE_PATH], deadline, checkpoint_cap=cap)
        need(launch.get('format') == 'irisx/v43-checkpoint-header-launch-v1'
             and launch.get('helper_sha256') == args.helper_sha
             and launch.get('observer_sha256') == OBSERVER_SHA256
             and launch.get('manifest_sha256') == MANIFEST_SHA256
             and launch.get('native_config_sha256') == base.CONFIG_SHA256
             and launch.get('accepted_metadata_sha256') == base.METADATA_SHA256
             and type(launch.get('numeric_version')) is int and launch['numeric_version'] == 43
             and launch.get('clock') == base.CLOCK
             and launch.get('terminal_receipt_sha256') == args.terminal_receipt_sha
             and launch.get('expected_checkpoint_source') == source
             and type(launch.get('cap')) is int and launch['cap'] == cap
             and launch.get('deadline_epoch') == args.deadline_epoch
             and type(launch.get('max_seconds')) is int and launch['max_seconds'] == MAX_SECONDS
             and launch.get('scope') == 'checkpoint-header-only-no-refresh-no-admission',
             'checkpoint_launch_binding')
        require_deadline(base, deadline)
    sdk = base.pinned_module('retrieval_sdk_worker', root / 'sdk_worker.py', base.PINS['sdk_worker.py'])
    auth_module = base.pinned_module('retrieval_native_auth', root / 'native_auth.py', base.PINS['native_auth.py'])
    facade = base.ReadonlyRuntime(runtime)
    auth = auth_module.OfficialSession(facade, base.NoRefresh(),
        lambda client, session: bind_readonly(base, sdk, client, session, deadline,
                                            checkpoint_header=args.checkpoint_header),
        lock_path=root / 'sdk-lock.json')
    result = {'format': 'irisx/v43-selected-worker-v1', 'nonce': args.nonce,
              'request_sha256': args.request_sha, 'ok': False, 'download': None}
    if args.checkpoint_header:
        result['format'] = 'irisx/v43-checkpoint-header-worker-v1'
        del result['download']
        result['header'] = None
    progress = {}
    with auth_module.isolate_sdk_output() as (_, writer):
        try:
            header_stage(progress, 'auth_prepare')
            auth.prepare()
            header_stage(progress, 'auth_protocol_ready')
            auth.protocol_ready()
            header_stage(progress, 'auth_open')
            auth.open()
            header_stage(progress, 'provider_setup')
            storage = DownloadOnly(sdk.StorageHttp())
            provider = sdk.WorkerProvider(auth, runtime.versions, storage=storage)
            if args.checkpoint_header:
                result['header'] = observe_checkpoint_header(base, provider, storage,
                    expected, cap, source, deadline, progress=progress)
            else:
                result['download'] = retrieve_one(base, provider, storage, expected, args.name,
                    caps[args.name], directory, deadline, expected_file)
            result['ok'] = True
        except auth_module.AuthRefreshUnknown:
            result.update(error='AUTH_REFRESH_UNKNOWN', mutation_uncertain=True,
                          refresh_denied_before_write_guard=facade.refresh_denied_before_write_guard)
            if args.checkpoint_header:
                result.update(header_failure(ValueError('auth_refresh_unknown'), progress))
        except BaseException as error:
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            reason = 'SELECTED_OUTPUT_PENDING_OR_MISSING' if status == 404 else 'selected_retrieval_failed'
            if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] == 'provider_not_terminal':
                reason = 'PROVIDER_NOT_TERMINAL'
            result.update(error=reason, mutation_uncertain=False)
            if args.checkpoint_header:
                result.update(header_failure(error, progress, status))
        finally:
            auth.close()
        raw = base.canonical(result)
        need(len(raw) <= base.MAX_RESULT, 'result_bound')
        writer.write(raw)
        writer.flush()
    return 0 if result['ok'] else 2


def supervise(args, argv):
    started = time.monotonic()
    base, root, win, runtime, expected, manifest, caps = bootstrap(args)
    supervisor = base.pinned_module('retrieval_win_supervisor', root / 'win_supervisor.py',
                                    base.PINS['win_supervisor.py'])
    supervisor._install_runtime(win)
    supervisor.MAX_STREAM_BYTES = base.MAX_RESULT
    now = time.time()
    need(base.CLOCK['original_epoch'] <= now < base.CLOCK['global_deadline'], 'original_global_deadline')
    deadline_epoch = min(now + MAX_SECONDS, base.CLOCK['global_deadline'])
    deadline = min(started + MAX_SECONDS, time.monotonic() + deadline_epoch - now)
    # Archive admission validates a completed prior numeric-terminal receipt.
    expected_file = prior_terminal(base, args, caps[args.name], deadline) if args.name == EVIDENCE_PATH else None
    source = None
    if args.checkpoint_header:
        cap = checkpoint_cap(manifest)
        source = prior_terminal(base, args, caps[EVIDENCE_PATH], deadline, checkpoint_cap=cap)
        require_deadline(base, deadline)
    else:
        cap = caps[args.name]
    output = base.observation_output(args.output, root)
    nonce = secrets.token_hex(32)
    request = {'format': 'irisx/v43-selected-launch-v1', 'nonce': nonce,
               'helper_sha256': args.helper_sha, 'observer_sha256': OBSERVER_SHA256,
               'native_config_sha256': args.config_sha, 'accepted_metadata_sha256': args.accepted_metadata_sha,
               'manifest_sha256': MANIFEST_SHA256, 'provider_path': args.name, 'numeric_version': 43,
               'clock': base.CLOCK, 'deadline_epoch': deadline_epoch, 'max_seconds': MAX_SECONDS,
               'terminal_receipt_sha256': args.terminal_receipt_sha, 'expected_file': expected_file,
               'cap': cap, 'scope': 'single-selected-output-no-refresh-no-admission'}
    if args.checkpoint_header:
        request.update(format='irisx/v43-checkpoint-header-launch-v1',
                       expected_checkpoint_source=source,
                       scope='checkpoint-header-only-no-refresh-no-admission')
        del request['expected_file']
    request_sha = base.write_new(output / 'launch.json', request)
    receipt = {'format': 'irisx/v43-selected-retrieval-v1', 'nonce': nonce,
               'request_sha256': request_sha, 'ok': False, 'closure': None,
               'reason': 'retrieval_supervision_failed', 'numeric_version': 43,
               'provider_path': args.name, 'manifest_sha256': MANIFEST_SHA256,
               'native_config_sha256': args.config_sha, 'observer_sha256': OBSERVER_SHA256,
               'helper_sha256': args.helper_sha, 'saved_source_sha256': base.SOURCE_SHA256,
               'clock': base.CLOCK, 'download_finalized': False,
               'inventory_scope': 'selected_outputs_only', 'whole_provider_inventory_verified': False,
               'collection_aggregate_verified': False, 'consumer_admitted': False,
               'scientific_success_verified': False, 'old_native_session_closure_verified': False}
    if args.checkpoint_header:
        receipt.update(format='irisx/v43-checkpoint-header-v1', header_observation_finalized=False,
                       terminal_receipt_sha256=args.terminal_receipt_sha,
                       source_checkpoint_descriptor=source, body_materialized=False,
                       independently_sha256_verified=False, observed_sha256=None,
                       body_consumed_bytes=0,
                       redirect_policy='location-only-json-body-redirects-refused',
                       scope='independent-header-observation-no-collector-admission')
        del receipt['download_finalized']
    input_fd, hold_open = os.pipe()
    code = 2
    stage, closed = 'supervise', False
    try:
        child = [runtime.executable, '-I', '-B', str(Path(__file__).absolute()), *argv,
                 '--worker', '--nonce', nonce, '--request-sha', request_sha,
                 '--deadline-epoch', str(deadline_epoch)]
        with (output / 'worker-result.json').open('xb', buffering=0) as stream:
            result = supervisor.supervise(child, timeout_seconds=MAX_SECONDS,
                deadline_unix=deadline_epoch, lease_monotonic=deadline,
                input_fd=input_fd, output_fd=stream.fileno(), scope='publication-worker-v1',
                protocol=None, nonce=nonce)
            os.fsync(stream.fileno())
        receipt.update(reason=result.reason, supervisor_reason=result.reason, closure=result.closure)
        stage = 'worker_result'
        raw = (output / 'worker-result.json').read_bytes()
        need(0 < len(raw) <= base.MAX_RESULT, 'worker_result_bound')
        value = base.strict_json(raw)
        need(value.get('nonce') == nonce and value.get('request_sha256') == request_sha
             and value.get('format') == ('irisx/v43-checkpoint-header-worker-v1' if args.checkpoint_header
                                        else 'irisx/v43-selected-worker-v1'), 'worker_result_binding')
        receipt['worker_result_sha256'] = base.sha(raw)
        if result.code == 0 and value.get('ok') is True:
            stage = 'new_job_closure'
            new_job_closure(result.closure)
            closed = True
            if args.checkpoint_header:
                stage = 'checkpoint_header'
                need(set(value) == {'format', 'nonce', 'request_sha256', 'ok', 'header'}
                     and result.reason == 'worker_exit', 'checkpoint_header_result')
                header = value['header']
                need(type(header) is dict and set(header) == {'before', 'after', 'checkpoint'}
                     and base.canonical(header['checkpoint']) == base.canonical(header_observation(source['bytes'])),
                     'checkpoint_header_result')
                terminal_brackets(base, header['before'], header['after'])
                need(deadline_epoch - MAX_SECONDS <= header['before']['started_epoch']
                     <= header['after']['observed_epoch'] <= deadline_epoch, 'terminal_bracket_clock')
                need(not any(os.path.lexists(output / name) for name in ('payload.part', 'payload.bin')),
                     'checkpoint_body_forbidden')
                require_deadline(base, deadline)
                receipt.update(ok=True, header_observation_finalized=True, **header)
                code = 0
                return code
            stage = 'terminal_brackets'
            terminal_brackets(base, value['download']['before'], value['download']['after'])
            stage = 'digest_file'
            row = digest_file(base, output / 'payload.part', caps[args.name], deadline)
            stage = 'download_descriptor'
            need(row == value['download']['file'] and (expected_file is None or row == expected_file),
                 'closed_download_hash_changed')
            need(time.monotonic() < deadline and time.time() < base.CLOCK['global_deadline'],
                 'original_retrieval_deadline')
            stage = 'finalize'
            need(not (output / 'payload.bin').exists(), 'final_output_exists')
            # Production is native Windows: rename fails if destination exists.
            os.rename(output / 'payload.part', output / 'payload.bin')
            receipt.update(ok=True, download_finalized=True, file=row,
                           before=value['download']['before'], after=value['download']['after'])
            code = 0
        elif args.checkpoint_header:
            stage = 'checkpoint_header_worker'
            need(value.get('ok') is False and value.get('header') is None
                 and all(type(value.get(key)) is str and value[key] in allowed
                         for key, allowed in (('error', HEADER_WORKER_ERRORS),
                             ('failure_stage', HEADER_WORKER_STAGES),
                             ('error_code', HEADER_WORKER_ERROR_CODES))),
                 'checkpoint_header_worker_result')
            receipt.update(worker_error=value['error'], worker_failure_stage=value['failure_stage'],
                           worker_error_code=value['error_code'])
    except BaseException as error:
        # Only fixed local codes may leave this process; exception text can
        # contain private paths, provider bodies or credentials.
        error_code = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
        receipt.update(reason='post_close_validation_failed' if closed else 'retrieval_validation_failed',
                       failure_stage=stage,
                       error_code=error_code if error_code in SUPERVISOR_ERROR_CODES else 'unexpected_error')
        if stage == 'supervise':
            receipt['reason'] = 'retrieval_supervision_failed'
        if error_code == 'windows_duplicate_worker':
            receipt['reason'] = 'original_mutex_exists_no_takeover'
    finally:
        os.close(hold_open)
        os.close(input_fd)
        base.write_new(output / ('checkpoint-header-result.json' if args.checkpoint_header
                                 else 'retrieval-result.json'), receipt)
        if args.checkpoint_header:
            print(json.dumps(receipt, sort_keys=True), flush=True)
    if args.checkpoint_header:
        return code
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return code


def arguments(argv):
    flags = [arg.split('=', 1)[0] for arg in argv if arg.startswith('--')]
    need(len(argv) <= 48 and len(set(flags)) == len(flags), 'unambiguous_arguments')
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ('helper-sha', 'bridge-root', 'config', 'config-sha', 'accepted-metadata',
                 'accepted-metadata-sha', 'manifest', 'manifest-sha', 'name', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--terminal-receipt')
    parser.add_argument('--terminal-receipt-sha')
    parser.add_argument('--checkpoint-header', action='store_true',
                        help='Fixed checkpoint headers only; JSON-body URL redirects are refused.')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--nonce')
    parser.add_argument('--request-sha')
    parser.add_argument('--deadline-epoch', type=float)
    args = parser.parse_args(argv)
    for name in ('helper_sha', 'config_sha', 'accepted_metadata_sha', 'manifest_sha'):
        need(re.fullmatch('[0-9a-f]{64}', getattr(args, name)) is not None, 'argument_sha256')
    need((args.terminal_receipt is None) == (args.terminal_receipt_sha is None), 'terminal_receipt_pair')
    if args.checkpoint_header:
        need(args.name == CHECKPOINT_PATH, 'fixed_checkpoint_path')
    if args.name == EVIDENCE_PATH or args.checkpoint_header:
        need(args.terminal_receipt is not None and re.fullmatch('[0-9a-f]{64}', args.terminal_receipt_sha),
             'terminal_receipt_required')
    else:
        need(args.terminal_receipt is None, 'unused_terminal_receipt_forbidden')
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
        print('{"ok":false,"reason":"retrieval_bootstrap_failed"}', flush=True)
        return 2


if __name__ == '__main__':
    os._exit(main())

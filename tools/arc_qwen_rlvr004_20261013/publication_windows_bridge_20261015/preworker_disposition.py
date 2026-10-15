"""Pure interpretation of an exact, persisted f5 pre-worker lease failure.

The caller authenticates the historical normal native-configuration descriptor,
provides a complete bounded STATE root/event byte snapshot, and rechecks that
snapshot and all descriptors around observation. No candidate code is executed;
only the fixed reviewed f5 source bytes authenticate diagnostic semantics.

Under the existing trusted-host/no-rollback assumption, the fixed supervisor's
lease-failure reason precedes native configuration loading, JobProcess creation,
and worker launch. This is a process-not-started disposition, NEVER a native
Job-zero/closure receipt. process_started=False refers only to the SDK worker
and JobProcess; the native supervisor and interoperability proxy did run.
Original UNKNOWN bytes remain unchanged. The original receipt is neither
required nor reconstructed from its retained digest.
"""
from __future__ import annotations

import hashlib
import json
import math
import ntpath
from pathlib import Path
import re
from types import MappingProxyType

HISTORICAL_COMMIT = 'f5f780cb5823579288385158ce6da70a1ca33899'
SOURCE_PINS_SHA256 = '09e51f695d1dfd216f162b8451cd34331f35f9d137da749bc35e4fde8f6882a7'
FILE_CAP = 4 * 1024**2
# Caller permits 256 MiB of events plus the fixed 32 MiB historical roots.
TREE_CAP = 288 * 1024**2
COUNT_CAP = 100512
NATIVE_SOURCES = frozenset(('win_runtime.py', 'win_supervisor.py', 'protocol.py',
    'native_config.py', 'native_auth.py', 'sdk_worker.py', 'sdk-lock.json'))
DIAGNOSTIC_SOURCES = NATIVE_SOURCES | {'bridge_client.py'}
VERSION_KEYS = frozenset(('code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'))
OPEN_KEYS = frozenset(('account', 'versions', 'configuration_sha256',
    'bridge_configuration_sha256', 'publication_manifest_sha256', 'deadline_epoch', 'max_seconds'))
JOURNAL_KEYS = frozenset(('format', 'nonce', 'claim_sha256', 'stage', 'synthetic_test_only',
    'native_process_closure_verified', 'mutation_attempted'))
OPERATION_KEYS = frozenset(('operation', 'sequence', 'request_sha256', 'deadline_epoch'))
DIAGNOSTIC_KEYS = frozenset(('format', 'ready_observed', 'authenticated_observed',
    'rpc_phase_observed', 'cleanup', 'writer_close', 'finish', 'release',
    'proxy_exit_status', 'receipt_validation', 'receipt_bytes_capped', 'receipt_sha256',
    'supervisor_reason'))
_SESSION = re.compile(r'native-bridge-([0-9a-f]{64})')
_EVENT = re.compile(r'([1-9][0-9]{0,19})-(.+)-([0-9a-f]{8})\.json')


class DispositionError(ValueError):
    """A fixed, non-secret fail-closed diagnostic."""


def _need(value, code):
    if not value:
        raise DispositionError('preworker_' + code)


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 < value <= 1e11


def _keys(value, keys, code):
    _need(type(value) is dict and set(value) == set(keys), code)


def _path(value):
    _need(type(value) is str or isinstance(value, Path), 'absolute_path')
    text = str(value)
    path = Path(text)
    _need(path.is_absolute() and str(path) == text and '..' not in path.parts
          and not text.startswith('//') and len(text) <= 4096
          and not any(ord(ch) < 32 for ch in text), 'absolute_path')
    return path


def _json(raw):
    _need(type(raw) is bytes and 0 < len(raw) <= FILE_CAP, 'json_bound')
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def integer(value):
        _need(len(value) <= 24, 'integer_bound')
        return int(value)
    def number(value):
        result = float(value)
        _need(math.isfinite(result), 'nonfinite_json')
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
            parse_float=number, parse_constant=lambda _: _need(False, 'nonfinite_json'))
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, DispositionError):
            raise
        raise DispositionError('preworker_invalid_json') from None
    stack, count = [(result, 0)], 0
    while stack:
        value, depth = stack.pop()
        count += 1
        _need(count <= 100000 and depth <= 32, 'json_complexity')
        if type(value) is dict:
            _need(all(type(key) is str and len(key) <= 4096 for key in value), 'json_key')
            stack.extend((item, depth + 1) for item in value.values())
        elif type(value) is list:
            stack.extend((item, depth + 1) for item in value)
        elif type(value) is str:
            _need(len(value) <= 65536, 'string_bound')
    _need(type(result) is dict, 'json_object')
    return result


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _verified(row, verified):
    _keys(row, ('path', 'bytes', 'sha256'), 'descriptor_schema')
    _path(row['path'])
    _need(type(row['bytes']) is int and 0 < row['bytes'] <= FILE_CAP
          and _sha(row['sha256']), 'descriptor_bound')
    raw = verified(row)
    _need(type(raw) is bytes and len(raw) == row['bytes'] and _digest(raw) == row['sha256'],
          'descriptor_changed')
    return raw


def _native_path(value):
    _need(type(value) is str and 3 <= len(value) <= 4096
          and not any(ord(ch) < 32 for ch in value), 'native_path')
    drive, tail = ntpath.splitdrive(value)
    _need(re.fullmatch('[A-Za-z]:', drive) is not None and tail.startswith('\\')
          and '/' not in value and not any(ch in tail for ch in ':*?<>|"')
          and ntpath.normpath(value) == value
          and all(part not in ('', '.', '..') and not part.endswith(('.', ' '))
                  for part in tail[1:].split('\\')), 'native_path')
    return value


def _native_document(document, pins):
    _keys(document, ('format', 'account', 'identity', 'runtime', 'source_root', 'sources',
        'versions', 'network_environment_sha256', 'requests_ca_bundle'), 'native_schema')
    _need(document['format'] == 'irisx/run008-windows-sdk-runtime-v1'
          and document['account'] == 'danielwuu', 'native_normal_identity')
    _keys(document['identity'], ('sid', 'profile'), 'native_identity_schema')
    sid = document['identity']['sid']
    _need(type(sid) is str and re.fullmatch(r'S-1-5-21-(?:[0-9]{1,10}-){3}[0-9]{1,10}', sid),
          'native_identity_sid')
    _native_path(document['identity']['profile'])
    _native_path(document['source_root'])
    runtime = document['runtime']
    _keys(runtime, ('executable', 'base_executable', 'pyvenv_cfg_sha256', 'venv_prefix',
        'sdk_root', 'python_version'), 'native_runtime_schema')
    for name in ('executable', 'base_executable'):
        _keys(runtime[name], ('path', 'sha256'), 'native_executable_schema')
        _native_path(runtime[name]['path'])
        _need(_sha(runtime[name]['sha256']), 'native_executable_sha')
    for name in ('venv_prefix', 'sdk_root'):
        _native_path(runtime[name])
    _need(_sha(runtime['pyvenv_cfg_sha256'])
          and ntpath.normcase(runtime['executable']['path']) == ntpath.normcase(
              ntpath.join(runtime['venv_prefix'], 'Scripts', 'python.exe'))
          and ntpath.normcase(runtime['sdk_root']) == ntpath.normcase(
              ntpath.join(runtime['venv_prefix'], 'Lib', 'site-packages')), 'native_runtime_binding')
    version = runtime['python_version']
    _need(type(version) is list and len(version) == 3 and all(type(item) is int for item in version)
          and version[:2] == [3, 12] and 0 <= version[2] <= 99, 'native_python_version')
    _keys(document['sources'], NATIVE_SOURCES, 'native_source_closure')
    _need(all(document['sources'][name] == pins[name] for name in NATIVE_SOURCES),
          'native_source_not_pinned_f5')
    versions = document['versions']
    _keys(versions, VERSION_KEYS, 'native_versions')
    _need(all(type(value) is int and 1 <= value <= 1000000 for value in versions.values())
          and versions['code'] == versions['code_predecessor'] + 1
          and versions['inactive'] == versions['inactive_predecessor'] + 1
          and versions['active'] == versions['inactive'] + 1, 'native_versions')
    network = document['network_environment_sha256']
    _need(type(network) is dict and set(network) <= {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
          'NO_PROXY', 'REQUESTS_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}
          and all(_sha(value) for value in network.values()), 'native_network_schema')
    ca = document['requests_ca_bundle']
    if ca is not None:
        _keys(ca, ('path', 'sha256'), 'native_ca_schema')
        _native_path(ca['path'])
        _need(_sha(ca['sha256']), 'native_ca_sha')
    return document


def _source_context(native_configuration, diagnostic_sources, source_manifest, verified):
    _need(type(source_manifest) is bytes and 0 < len(source_manifest) <= FILE_CAP
          and _digest(source_manifest) == SOURCE_PINS_SHA256,
          'source_manifest_changed')
    manifest = _json(source_manifest)
    _keys(manifest, ('format', 'commit', 'sources'), 'source_manifest_schema')
    _need(manifest['format'] == 'irisx/context-source-pins-v1'
          and manifest['commit'] == HISTORICAL_COMMIT, 'source_manifest_identity')
    pins = manifest['sources']
    _need(type(diagnostic_sources) is dict and DIAGNOSTIC_SOURCES <= set(diagnostic_sources)
          and set(diagnostic_sources) <= set(pins), 'diagnostic_source_closure')
    for name in sorted(DIAGNOSTIC_SOURCES):
        raw = _verified(diagnostic_sources[name], verified)
        _need({'bytes': len(raw), 'sha256': _digest(raw)} == pins[name],
              'diagnostic_source_not_pinned_f5')
    raw = _verified(native_configuration, verified)
    return _native_document(_json(raw), pins)


def _files(files):
    _need(type(files) is dict and len(files) <= COUNT_CAP, 'snapshot_count')
    parsed, events, total = {}, [], 0
    for name, raw in files.items():
        _need(type(name) is str and re.fullmatch(r'(?:events/)?[A-Za-z0-9][A-Za-z0-9_.-]{0,239}\.json', name)
              and '..' not in name, 'snapshot_name')
        parsed[name] = _json(raw)
        total += len(raw)
        _need(total <= TREE_CAP, 'snapshot_bytes')
        if name.startswith('events/'):
            match = _EVENT.fullmatch(name[7:])
            _need(match is not None, 'event_filename')
            events.append((int(match[1]), match[2], name))
    return parsed, sorted(events)


def _mentions(value, nonce, session):
    if type(value) is str:
        return value in (nonce, session)
    if type(value) is dict:
        return any(key in (nonce, session) or _mentions(item, nonce, session)
                   for key, item in value.items())
    if type(value) is list:
        return any(_mentions(item, nonce, session) for item in value)
    return False


def _diagnostics(value, *, complete):
    _keys(value, DIAGNOSTIC_KEYS, 'diagnostic_schema')
    _need(value['format'] == 'irisx/windows-bridge-failure-diagnostics-v1'
          and value['ready_observed'] is False and value['authenticated_observed'] is False
          and value['rpc_phase_observed'] == 'not_started', 'diagnostic_preworker_state')
    if complete:
        _need(value['cleanup'] == 'complete' and value['writer_close'] == 'closed'
              and value['finish'] == 'complete' and value['release'] == 'complete'
              and type(value['proxy_exit_status']) is int and value['proxy_exit_status'] == 125
              and value['receipt_validation'] == 'rejected'
              and type(value['receipt_bytes_capped']) is int and 0 < value['receipt_bytes_capped'] <= 4096
              and _sha(value['receipt_sha256'])
              and value['supervisor_reason'] == 'supervisor_lease_failed', 'diagnostic_lease_failure')
    else:
        _need(value['cleanup'] == 'not_started' and value['writer_close'] == 'not_attempted'
              and value['finish'] == 'not_attempted' and value['release'] == 'not_attempted'
              and value['proxy_exit_status'] is None and value['receipt_validation'] == 'not_attempted'
              and value['receipt_bytes_capped'] is None and value['receipt_sha256'] is None
              and value['supervisor_reason'] == 'unavailable', 'diagnostic_initial_failure')


def _record(root, name, raw):
    return MappingProxyType({'path': str(root / name), 'bytes': len(raw), 'sha256': _digest(raw)})


def _classify_one(files, parsed, events, root, session, native_configuration, native):
    claim_name, journal_name = session + '.claim.json', session + '-journal.json'
    _need(claim_name in files and journal_name in files, 'session_missing_record')
    claim, journal = parsed[claim_name], parsed[journal_name]
    _keys(claim, OPEN_KEYS | {'format', 'nonce', 'synthetic_test_only'}, 'claim_schema')
    nonce = claim['nonce']
    _need(_sha(nonce) and session == 'native-bridge-' + nonce
          and claim['format'] == 'irisx/windows-bridge-session-claim-v1'
          and claim['account'] == 'danielwuu' and claim['synthetic_test_only'] is False
          and claim['versions'] == native['versions']
          and claim['bridge_configuration_sha256'] == native_configuration['sha256']
          and all(_sha(claim[key]) for key in ('configuration_sha256',
              'bridge_configuration_sha256', 'publication_manifest_sha256'))
          and _number(claim['deadline_epoch']) and type(claim['max_seconds']) is float
          and claim['max_seconds'] == 43200.0, 'claim_binding')
    # bool/int dictionary equality must not authorize malformed version fields.
    _keys(claim['versions'], VERSION_KEYS, 'claim_versions')
    _need(all(type(value) is int for value in claim['versions'].values()), 'claim_versions')
    rows = [(stamp, name) for stamp, stem, name in events if stem == session]
    _need(len(rows) == 4 and len({stamp for stamp, _ in rows}) == 4,
          'session_event_sequence')
    _need(files[rows[-1][1]] == files[journal_name], 'journal_event_frontier')
    expected_stages = ('launch_intent', 'operation_intent', 'UNKNOWN', 'UNKNOWN')
    operation = None
    for index, ((_, name), stage) in enumerate(zip(rows, expected_stages)):
        proof = parsed[name]
        extra = set() if index == 0 else set(OPERATION_KEYS)
        if index >= 2:
            extra |= {'unknown_reason', 'failure_diagnostics'}
        _keys(proof, JOURNAL_KEYS | extra, 'journal_schema')
        _need(proof['format'] == 'irisx/windows-bridge-session-journal-v1'
              and proof['stage'] == stage and proof['nonce'] == nonce
              and proof['claim_sha256'] == _digest(files[claim_name])
              and proof['synthetic_test_only'] is False
              and proof['native_process_closure_verified'] is False
              and proof['mutation_attempted'] is False, 'journal_binding')
        if index:
            current = {key: proof[key] for key in OPERATION_KEYS}
            _need(current['operation'] == 'open' and type(current['sequence']) is int
                  and current['sequence'] == 1 and _sha(current['request_sha256'])
                  and _number(current['deadline_epoch'])
                  and current['deadline_epoch'] <= claim['deadline_epoch'], 'open_binding')
            if operation is None:
                operation = current
                # The fixed ordinary open uses integer 120 when the fresh
                # 43,200-second lease has that budget. A shorter/ambiguous open
                # cannot be reconstructed from this journal and stays blocked.
                arguments = {key: claim[key] for key in OPEN_KEYS}
                request = {'operation': 'open', 'arguments': arguments,
                           'deadline_epoch': current['deadline_epoch'], 'max_seconds': 120}
                _need(current['request_sha256'] == _digest(_canonical(request)), 'open_request_hash')
            else:
                _need(_canonical(current) == _canonical(operation), 'operation_changed')
        if index >= 2:
            _need(proof['unknown_reason'] == 'BRIDGE_OPERATION_UNKNOWN', 'unknown_reason')
            _diagnostics(proof['failure_diagnostics'], complete=index == 3)
    allowed = {claim_name, journal_name, *(name for _, name in rows)}
    for name, document in parsed.items():
        if name not in allowed:
            _need(not _mentions(document, nonce, session), 'contradictory_nonce_evidence')
    claim_row = _record(root, claim_name, files[claim_name])
    journal_row = _record(root, journal_name, files[journal_name])
    return MappingProxyType({'disposition': 'process_not_started', 'process_started': False,
        'native_process_closure_verified': False, 'session': session, 'nonce': nonce,
        'claim': claim_row, 'journal': journal_row,
        'claim_sha256': claim_row['sha256'], 'journal_sha256': journal_row['sha256'],
        'events': tuple(_record(root, name, files[name]) for _, name in rows),
        'excluded_root_names': (claim_name, journal_name)})


def classify(files, *, state_root, native_configuration, diagnostic_sources,
             source_manifest, verified):
    """Return immutable exact pre-worker dispositions, without modifying inputs.

    files is the COMPLETE bounded root-JSON plus events/JSON byte map captured
    by the caller's safe read layer. verified(descriptor) must safely reread a
    bounded no-link file. The caller binds native_configuration to the already
    authenticated historical NORMAL template, and diagnostic_sources to that
    original f5 closure, not to candidate/current modules. This function also
    checks their raw bytes against the immutable source manifest.

    Only the exact lease-failure shape is classified. Other UNKNOWNs are left
    unclassified and must continue to the existing historical fail-closed gate.
    A purported lease failure with contradictory/incomplete evidence raises.
    Returned names are solely for a read-only historical root projection;
    callers retain all actual files/events in snapshot and race checks.
    """
    try:
        _need(callable(verified), 'verified_reader_required')
        root = _path(state_root)
        parsed, events = _files(files)
        candidates = []
        for name, document in parsed.items():
            if name.startswith('events/') or not name.endswith('-journal.json'):
                continue
            session = name[:-len('-journal.json')]
            if _SESSION.fullmatch(session) is None:
                continue
            diagnostics = document.get('failure_diagnostics')
            if type(diagnostics) is dict and diagnostics.get('supervisor_reason') == 'supervisor_lease_failed':
                candidates.append(session)
        if not candidates:
            return ()
        native = _source_context(native_configuration, diagnostic_sources, source_manifest, verified)
        return tuple(_classify_one(files, parsed, events, root, session, native_configuration, native)
                     for session in sorted(candidates))
    except (KeyError, TypeError, AttributeError, RecursionError):
        raise DispositionError('preworker_invalid_schema') from None

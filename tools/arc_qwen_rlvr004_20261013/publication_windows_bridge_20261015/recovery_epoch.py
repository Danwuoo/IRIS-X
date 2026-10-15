"""Offline evidence gate for one bounded, read-only failed-open reconciliation.

This module neither restarts Windows nor launches, authenticates, or contacts a
provider. Original UNKNOWN records are immutable. An independently reviewed,
complete original inventory and exact original source/configuration bytes are
required inputs, not conclusions inferred from a file count. A hash descriptor
is an integrity binding, not a signature: the caller must obtain its expected
hash through the existing independent local review, especially for inventory
completeness and the trusted-host controlled-Restart receipt.

All writes use operator_common callbacks while RecoveryOwner owns the existing
external publisher lock. An exclusive capability claim consumes the epoch even
if the next write or process launch fails. No recovery record authorizes a
publication, credential refresh, or replay. A separate successful eligibility
record can cover only its exact historical failed-open claim; normal admission
must still apply every original source/configuration/remote-state gate.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import ntpath
import os
from pathlib import Path
import re
import stat
import types
import time

FILE_CAP = 4 * 1024**2
TREE_CAP = 32 * 1024**2
FILE_COUNT_CAP = 512
MAX_EPOCH_SECONDS = 3600
# Same trusted-OS clock/tick tolerance as the reviewed boot observer. This is
# not an elapsed-time substitute for a full restart or a live observation.
BOOT_SKEW_SECONDS = 120
READ_OPERATIONS = ('dataset', 'kernel', 'status')
ALLOWED_OPERATIONS = ['open', *READ_OPERATIONS, 'close']
ORIGINAL_COMMIT = '01ca4f14d23edaba64111f9ff0bab6d6deb20a91'
# Exact public bytes at ORIGINAL_COMMIT; no mutable HEAD or caller-selected pins.
ORIGINAL_SOURCES = {
    'operator_common.py': (22154, 'c1bddaa8b13598a8546de6e77f8bf29403e2507743adccb1654bdc5be79fedd5'),
    'bridge_client.py': (30257, 'dc5006c8e1bf89aff38cbbf359093cef14fb216e708949d7c54b05816150910d'),
    'protocol.py': (36653, '086c70bc50d942c753ac19b8b6f994a54bef1e6a3b0819cacd496d4d09c57b3d'),
    'native_auth.py': (15321, '785e696dc702e5042f415e3da1bd3fbf43ff34f3f8a579a702ec2f262aefdcd4'),
    'sdk_worker.py': (44153, 'c62059254723542a46d5d76bbe7d817410fee41742b53972ef771640b67a43fe'),
    'win_supervisor.py': (15807, 'b1c7021beeed51a00f7f752669733cb77312d4a7a3055aaf37b6a1043fbeaba2'),
    'win_runtime.py': (35240, '7280b755d3155fb3d5d4f9989c0ea592d7a0d8be8750d635360f06fe766db69d'),
    'native_config.py': (11518, 'fe2ec44a37e8895077162a3369d859967001e5a50f4294d2d8e0fb954fa35282'),
    'config.py': (23625, '11cbdaa9f08a14ba9efcf15207991d5179682413899853becf562f6b4af7169f'),
    'sdk-lock.json': (19816, '3d447ab7fad280fcc378fd18b57c3792c5b39798127f583679646027ab73288d'),
    'launch.py': (5172, 'e70baa1213b6143197b17de0c7b944ce13a0c0a60cad71fbafe8a62e778ef1dc'),
    'rl_transport.py': (59395, 'cc05fc8b6878aa7648a5a526d93fa5b1262e7f2e72a725c986bbe6bd83b18c82'),
    'rl_collect.py': (58716, '117baa170c24768a83cd8c97c45b39385aec162646be329ed62a68a3f74be182'),
    'native_probe.py': (39716, 'd38630677f70dac21d0369623c1d7f7e6650d9085b0d3b9e38a7c2918072f73f'),
    'verify_active_wire.py': (19347, '8a5b7844d1c5cfee3f5c026967d1dab2ed8465aa11e563aec276ba909c086438'),
}
RECOVERY_SOURCES = frozenset(ORIGINAL_SOURCES) | {'recovery_epoch.py', 'recovery_boot_probe.py', 'recovery_entry.py'}
NATIVE_SOURCES = {'win_runtime.py', 'win_supervisor.py', 'protocol.py',
                  'native_config.py', 'native_auth.py', 'sdk_worker.py', 'sdk-lock.json'}
_SESSION = re.compile(r'native-bridge-([0-9a-f]{64})')
_EVENT = re.compile(r'([1-9][0-9]{0,19})-(.+)-([0-9a-f]{8})\.json')


class RecoveryError(ValueError):
    """Fixed, non-secret fail-closed diagnostic."""


def _need(value, code):
    if not value:
        raise RecoveryError(code)


def _keys(value, fields, code='recovery_schema'):
    _need(type(value) is dict and set(value) == set(fields), code)


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def canonical(value):
    try:
        return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    except (ValueError, TypeError, RecursionError):
        raise RecoveryError('recovery_json_encoding') from None


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    _need(type(raw) is bytes and 0 < len(raw) <= FILE_CAP, 'recovery_json_bound')
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, 'recovery_duplicate_json_key')
            result[key] = value
        return result
    def integer(value):
        _need(len(value) <= 24, 'recovery_integer_bound')
        return int(value)
    def number(value):
        result = float(value)
        _need(math.isfinite(result), 'recovery_nonfinite_json')
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
            parse_float=number, parse_constant=lambda _: _need(False, 'recovery_nonfinite_json'))
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, RecoveryError):
            raise
        raise RecoveryError('recovery_invalid_json') from None
    pending, count = [(result, 0)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        _need(count <= 100000 and depth <= 32, 'recovery_json_complexity')
        if type(node) is dict:
            pending.extend((v, depth + 1) for v in node.values())
        elif type(node) is list:
            pending.extend((v, depth + 1) for v in node)
        elif type(node) is str:
            _need(len(node) <= 65536, 'recovery_string_bound')
    _need(type(result) is dict, 'recovery_json_object')
    return result


def _path(value):
    _need(type(value) is str or isinstance(value, Path), 'recovery_path_type')
    text = str(value)
    path = Path(text)
    _need(path.is_absolute() and str(path) == text and '..' not in path.parts
          and not text.startswith('//') and len(text) <= 4096
          and not any(ord(ch) < 32 for ch in text), 'recovery_absolute_path')
    return path


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def _directory(path):
    """Walk with directory handles, never follow an intermediate symlink."""
    path = _path(path)
    descriptors, identities = [], []
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        descriptors.append(fd)
        for component in path.parts[1:]:
            info = os.stat(component, dir_fd=fd, follow_symlinks=False)
            _need(stat.S_ISDIR(info.st_mode), 'recovery_directory_type')
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                            | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=fd)
            descriptors.append(child)
            opened = os.fstat(child)
            # Ancestor contents may change independently (for example /tmp).
            # Object identity must remain stable; STATE scans check contents.
            _need(stat.S_ISDIR(opened.st_mode) and (info.st_dev, info.st_ino)
                  == (opened.st_dev, opened.st_ino), 'recovery_directory_race')
            identities.append((fd, component, info.st_dev, info.st_ino))
            fd = child
        yield fd
        for parent, component, device, inode in identities:
            current = os.stat(component, dir_fd=parent, follow_symlinks=False)
            _need(stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino)
                  == (device, inode), 'recovery_directory_replaced')
    except OSError:
        raise RecoveryError('recovery_file_unavailable') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _read_at(directory, name, cap):
    before = os.stat(name, dir_fd=directory, follow_symlinks=False)
    _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
          and 0 <= before.st_size <= cap, 'recovery_bounded_single_link_file')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                 dir_fd=directory)
    with os.fdopen(fd, 'rb') as stream:
        _need(_identity(os.fstat(fd)) == _identity(before), 'recovery_file_open_race')
        raw = stream.read(cap + 1)
        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        _need(len(raw) == before.st_size and len(raw) <= cap
              and _identity(os.fstat(fd)) == _identity(before) == _identity(current),
              'recovery_file_read_race')
    return raw


def bounded_read(path, cap=FILE_CAP):
    path = _path(path)
    with _directory(path.parent) as fd:
        return _read_at(fd, path.name, cap)


def descriptor(path):
    raw = bounded_read(path)
    return {'path': str(_path(path)), 'bytes': len(raw), 'sha256': sha(raw)}


def _descriptor(value):
    _keys(value, ('path', 'bytes', 'sha256'), 'recovery_descriptor_schema')
    _path(value['path'])
    _need(type(value['bytes']) is int and 0 < value['bytes'] <= FILE_CAP
          and _sha(value['sha256']), 'recovery_descriptor_bounds')
    return value


def verified(value):
    _descriptor(value)
    raw = bounded_read(value['path'])
    _need(len(raw) == value['bytes'] and sha(raw) == value['sha256'], 'recovery_descriptor_changed')
    return raw


def _document(value):
    return strict_json(verified(value))


def _relative(value):
    _need(type(value) is str and re.fullmatch(r'(?:events/)?[A-Za-z0-9][A-Za-z0-9_.-]{0,239}\.json', value)
          and '..' not in value and not value.endswith('.tmp.json'), 'recovery_state_path')
    return value


def _scan(root):
    root = _path(root)
    result, total = {}, 0
    with _directory(root) as fd:
        def visit(directory, prefix):
            nonlocal total
            before = os.fstat(directory)
            names = sorted(os.listdir(directory))
            _need(len(names) <= FILE_COUNT_CAP, 'recovery_inventory_file_count')
            for name in names:
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if not prefix and name == 'events' and stat.S_ISDIR(info.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                                    | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
                    try:
                        _need(_identity(info) == _identity(os.fstat(child)), 'recovery_inventory_directory_race')
                        visit(child, 'events/')
                        _need(_identity(info) == _identity(os.stat(name, dir_fd=directory,
                            follow_symlinks=False)), 'recovery_inventory_directory_race')
                    finally:
                        os.close(child)
                    continue
                relative = _relative(prefix + name)
                raw = _read_at(directory, name, FILE_CAP)
                strict_json(raw)
                result[relative] = raw
                total += len(raw)
                _need(len(result) <= FILE_COUNT_CAP and total <= TREE_CAP,
                      'recovery_inventory_bound')
            _need(names == sorted(os.listdir(directory))
                  and _identity(before) == _identity(os.fstat(directory)), 'recovery_inventory_race')
        visit(fd, '')
    return result


def _manifest(root, files):
    return {'format': 'irisx/recovery-inventory-v1', 'state_root': str(_path(root)),
            'files': [{'path': name, 'bytes': len(raw), 'sha256': sha(raw)}
                      for name, raw in sorted(files.items())]}


def inventory_state(root):
    """Read a bounded snapshot. Completeness still requires independent review."""
    return _manifest(root, _scan(root))


def _inventory(value, root):
    _keys(value, ('format', 'state_root', 'files'), 'recovery_inventory_schema')
    _need(value['format'] == 'irisx/recovery-inventory-v1' and value['state_root'] == str(_path(root)),
          'recovery_inventory_namespace')
    rows = value['files']
    _need(type(rows) is list and 0 < len(rows) <= FILE_COUNT_CAP, 'recovery_inventory_rows')
    result = {}
    for row in rows:
        _keys(row, ('path', 'bytes', 'sha256'))
        name = _relative(row['path'])
        _need(name not in result and type(row['bytes']) is int and 0 < row['bytes'] <= FILE_CAP
              and _sha(row['sha256']), 'recovery_inventory_descriptor')
        result[name] = row
    _need(list(result) == sorted(result) and sum(r['bytes'] for r in rows) <= TREE_CAP,
          'recovery_inventory_order_bound')
    return result


def _review(value, root, inventory_sha256):
    fields = ('format', 'original_commit', 'state_root', 'inventory_sha256', 'unknown_session',
              'original_configuration', 'original_native_configuration', 'original_sources',
              'recovery_sources', 'request_preimages', 'auxiliary_records', 'closed_sessions',
              'boot_source_sha256', 'boot_runtime_sha256', 'restart_authority')
    _keys(value, fields, 'recovery_review_schema')
    _need(value['format'] == 'irisx/recovery-source-review-v1'
          and value['original_commit'] == ORIGINAL_COMMIT
          and value['state_root'] == str(_path(root))
          and value['inventory_sha256'] == inventory_sha256
          and type(value['unknown_session']) is str and _SESSION.fullmatch(value['unknown_session']),
          'recovery_review_identity')
    _need(type(value['original_sources']) is dict and set(value['original_sources']) == set(ORIGINAL_SOURCES),
          'recovery_original_source_closure')
    for name, (size, digest) in ORIGINAL_SOURCES.items():
        row = value['original_sources'][name]
        _descriptor(row)
        _need((row['bytes'], row['sha256']) == (size, digest), 'recovery_original_source_not_known01ca')
        verified(row)
    _need(type(value['recovery_sources']) is dict and set(value['recovery_sources']) == RECOVERY_SOURCES,
          'recovery_execution_source_closure')
    for name, row in value['recovery_sources'].items():
        reviewed = verified(row)
        running = bounded_read(Path(__file__).absolute().with_name(name))
        _need(reviewed == running, 'recovery_executing_source_closure_changed')
    authority = value['restart_authority']
    _keys(authority, ('kind', 'authorization_sha256', 'witness_review_sha256'))
    _need(authority['kind'] == 'reviewed-manual-start-menu-restart'
          and _sha(authority['authorization_sha256']) and _sha(authority['witness_review_sha256']),
          'recovery_restart_authority')
    _keys(value['boot_source_sha256'], ('recovery_boot_probe.py', 'win_runtime.py'))
    _keys(value['boot_runtime_sha256'], ('python', 'base_python'))
    _need(all(_sha(digest) for digest in value['boot_runtime_sha256'].values()), 'recovery_boot_runtime_hash')
    for name, digest in value['boot_source_sha256'].items():
        _need(digest == value['recovery_sources'][name]['sha256'], 'recovery_boot_source_binding')
    configuration = _document(value['original_configuration'])
    native = _document(value['original_native_configuration'])
    _need(configuration.get('format') == 'irisx/run008-windows-bridge-operator-config-v1'
          and configuration.get('state_root') == str(root) and configuration.get('username') == 'danielwuu',
          'recovery_original_configuration_namespace')
    bridge = configuration.get('windows_bridge')
    _need(type(bridge) is dict and type(bridge.get('configuration')) is dict
          and bridge['configuration'].get('sha256') == value['original_native_configuration']['sha256'],
          'recovery_original_native_configuration_binding')
    _need(native.get('format') == 'irisx/run008-windows-sdk-runtime-v1'
          and native.get('account') == 'danielwuu' and native.get('versions') == configuration.get('versions')
          and type(native.get('sources')) is dict and set(native['sources']) == NATIVE_SOURCES,
          'recovery_original_native_source_closure')
    for name in NATIVE_SOURCES:
        _need(native['sources'][name] == {'bytes': ORIGINAL_SOURCES[name][0], 'sha256': ORIGINAL_SOURCES[name][1]},
              'recovery_original_native_source_binding')
    _need(type(value['request_preimages']) is list and len(value['request_preimages']) <= 256
          and type(value['closed_sessions']) is list and len(value['closed_sessions']) <= 64
          and type(value['auxiliary_records']) is list and len(value['auxiliary_records']) <= FILE_COUNT_CAP,
          'recovery_review_lists')
    _need(len(set(value['auxiliary_records'])) == len(value['auxiliary_records']), 'recovery_auxiliary_duplicate')
    for name in value['auxiliary_records']:
        _relative(name)
        _need(not name.endswith(('.claim.json', '-journal.json')) and 'native-bridge-' not in name
              and 'refresh' not in name.lower(), 'recovery_auxiliary_scope')
    return configuration


def validate_closure(raw, *, nonce, exit_status, clean=True):
    """Recompute the unchanged original BridgeClient._receipt predicate."""
    _need(type(raw) is bytes and 0 < len(raw) <= 4096 and raw.endswith(b'\n') and raw.count(b'\n') == 1,
          'recovery_closure_bytes')
    value = strict_json(raw)
    _keys(value, ('format', 'nonce', 'ok', 'reason', 'closure'))
    _need(value['format'] == 'irisx/windows-supervisor-result-v1' and value['nonce'] == nonce
          and type(value['ok']) is bool and type(value['reason']) is str, 'recovery_closure_identity')
    closure = value['closure']
    _keys(closure, ('format', 'active_processes', 'kill_on_close', 'breakaway_permitted', 'atomic_job_assignment'))
    _need(closure['format'] == 'irisx/windows-job-closure-v1'
          and type(closure['active_processes']) is int and closure['active_processes'] == 0
          and closure['kill_on_close'] is True and closure['breakaway_permitted'] is False
          and closure['atomic_job_assignment'] is True, 'recovery_job_zero_required')
    if clean:
        _need(type(exit_status) is int and exit_status == 0 and value['ok'] is True
              and value['reason'] == 'worker_exit', 'recovery_clean_closure_required')
    return value


def _no_refresh_or_mutation(name, document):
    _need('refresh' not in name.lower(), 'recovery_refresh_record_present')
    stack = [document]
    while stack:
        value = stack.pop()
        if type(value) is dict:
            _need(not any('refresh' in key.lower() for key in value), 'recovery_refresh_evidence_present')
            _need(value.get('operation') not in ('start_upload', 'upload_once', 'version', 'save', 'GenerateAccessToken')
                  and value.get('mutation_attempted', False) is False, 'recovery_publication_dispatch_present')
            _need(not str(value.get('stage', '')).lower().startswith('refresh'), 'recovery_refresh_evidence_present')
            stack.extend(value.values())
        elif type(value) is list:
            stack.extend(value)


def _event_rows(files, name):
    found = []
    for path, raw in files.items():
        if not path.startswith('events/'):
            continue
        match = _EVENT.fullmatch(path[7:])
        _need(match is not None, 'recovery_event_filename')
        if match[2] == name:
            found.append((int(match[1]), path, raw))
    found.sort()
    _need(len({row[0] for row in found}) == len(found), 'recovery_event_clock_collision')
    return found


def _session(files, name, review, configuration, *, failed=False):
    claim_name, journal_name = name + '.claim.json', name + '-journal.json'
    _need(claim_name in files and journal_name in files, 'recovery_session_missing_record')
    claim = strict_json(files[claim_name])
    _keys(claim, ('format', 'nonce', 'account', 'versions', 'configuration_sha256',
          'bridge_configuration_sha256', 'publication_manifest_sha256', 'deadline_epoch',
          'max_seconds', 'synthetic_test_only'), 'recovery_original_claim_schema')
    _need(claim['format'] == 'irisx/windows-bridge-session-claim-v1' and name == 'native-bridge-' + claim['nonce']
          and _sha(claim['nonce']) and claim['account'] == 'danielwuu'
          and claim['synthetic_test_only'] is False and claim['versions'] == configuration['versions']
          and claim['configuration_sha256'] == review['original_configuration']['sha256']
          and claim['bridge_configuration_sha256'] == review['original_native_configuration']['sha256']
          and claim['publication_manifest_sha256'] == configuration['publication_manifest_sha256']
          and _number(claim['deadline_epoch']) and _number(claim['max_seconds'])
          and claim['max_seconds'] == 43200, 'recovery_original_claim_binding')
    rows = _event_rows(files, name)
    _need(rows and rows[-1][2] == files[journal_name], 'recovery_journal_event_frontier')
    preimages = {}
    for preimage in review['request_preimages']:
        _keys(preimage, ('session', 'sequence', 'arguments', 'max_seconds'))
        key = (preimage['session'], preimage['sequence'])
        _need(type(preimage['session']) is str and _SESSION.fullmatch(preimage['session'])
              and type(preimage['sequence']) is int and 1 <= preimage['sequence'] <= 256
              and key not in preimages, 'recovery_request_preimage_identity')
        preimages[key] = preimage
    base = {'format', 'nonce', 'claim_sha256', 'stage', 'synthetic_test_only',
            'native_process_closure_verified', 'mutation_attempted'}
    operation_fields = {'operation', 'sequence', 'request_sha256', 'deadline_epoch'}
    previous, active, sequence, used, previous_proof = None, None, 0, set(), None
    for _, _, raw in rows:
        proof = strict_json(raw)
        stage = proof.get('stage')
        extras = operation_fields if 'operation' in proof else set()
        if stage == 'UNKNOWN':
            extras = extras | {'unknown_reason'}
        _keys(proof, base | extras, 'recovery_original_journal_schema')
        _need(proof['format'] == 'irisx/windows-bridge-session-journal-v1'
              and proof['nonce'] == claim['nonce'] and proof['claim_sha256'] == sha(files[claim_name])
              and proof['synthetic_test_only'] is False and proof['mutation_attempted'] is False
              and type(proof['native_process_closure_verified']) is bool,
              'recovery_original_journal_binding')
        _need(proof['native_process_closure_verified'] is (stage == 'closed'),
              'recovery_original_closure_event_order')
        _need(previous not in ('closed',) and (previous != 'UNKNOWN' or stage == 'UNKNOWN'),
              'recovery_terminal_event_replay')
        if previous is None:
            _need(stage == 'launch_intent' and not extras and proof['native_process_closure_verified'] is False,
                  'recovery_initial_event')
        elif stage == 'operation_intent':
            _need(previous in ('launch_intent', 'authenticated', 'operation_accepted')
                  and not (previous == 'operation_accepted' and sequence == 1)
                  and type(proof['sequence']) is int and proof['sequence'] == sequence + 1,
                  'recovery_monotone_sequence')
            sequence += 1
            operation = proof['operation']
            _need(operation in ('open', 'dataset', 'kernel', 'status', 'list_files', 'output',
                  'dataset_download', 'binary_metadata', 'close') and (sequence != 1 or operation == 'open')
                  and (sequence == 1 or operation != 'open'), 'recovery_original_operation_scope')
            key = (name, sequence)
            _need(key in preimages, 'recovery_request_preimage_missing')
            preimage = preimages[key]
            used.add(key)
            seconds = preimage['max_seconds']
            _need(_number(seconds) and 0 < seconds <= (900 if operation in ('output', 'dataset_download') else 120)
                  and _number(proof['deadline_epoch']) and proof['deadline_epoch'] <= claim['deadline_epoch'],
                  'recovery_request_deadline')
            arguments = preimage['arguments']
            if operation == 'open':
                _need(arguments == {key: claim[key] for key in ('account', 'versions', 'configuration_sha256',
                      'bridge_configuration_sha256', 'publication_manifest_sha256', 'deadline_epoch', 'max_seconds')},
                      'recovery_open_request_binding')
            elif operation in ('dataset', 'kernel', 'status', 'close'):
                _need(arguments == {}, 'recovery_read_request_arguments')
            _need(proof['request_sha256'] == sha(json.dumps({'operation': operation, 'arguments': arguments,
                  'deadline_epoch': proof['deadline_epoch'], 'max_seconds': seconds},
                  sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')),
                  'recovery_request_hash')
            active = {key: proof[key] for key in operation_fields}
        elif stage == 'operation_accepted':
            _need(previous == 'operation_intent' and active is not None, 'recovery_accept_without_intent')
        elif stage == 'authenticated':
            _need(previous == 'operation_accepted' and proof.get('operation') == 'open', 'recovery_auth_event_order')
        elif stage == 'closed':
            _need(previous == 'operation_accepted' and proof.get('operation') == 'close'
                  and proof['native_process_closure_verified'] is True, 'recovery_close_event_order')
        elif stage == 'UNKNOWN':
            _need(previous in ('operation_intent', 'UNKNOWN')
                  and proof.get('unknown_reason') in ('BRIDGE_OPEN_UNKNOWN', 'BRIDGE_OPERATION_UNKNOWN')
                  and proof.get('operation') == 'open' and sequence == 1, 'recovery_unknown_not_failed_open1')
            _need(previous != 'UNKNOWN' or proof == previous_proof, 'recovery_failure_latch_changed')
        else:
            _need(False, 'recovery_unreviewed_session_stage')
        if extras and stage != 'operation_intent':
            _need(active is not None and {key: proof[key] for key in operation_fields} == active,
                  'recovery_event_request_binding')
        previous = stage
        previous_proof = proof
        if stage == 'UNKNOWN':
            _need(proof['native_process_closure_verified'] is False, 'recovery_original_unknown_must_remain_unclosed')
    _need(previous == ('UNKNOWN' if failed else 'closed'), 'recovery_uncovered_unknown_session')
    if failed:
        _need(sequence == 1 and len(used) == 1, 'recovery_failed_open1_scope')
    else:
        receipts = [item for item in review['closed_sessions'] if item.get('session') == name]
        _need(len(receipts) == 1, 'recovery_closed_session_review_missing')
        receipt = receipts[0]
        _keys(receipt, ('session', 'claim_sha256', 'journal_sha256'))
        # Original close() checked the unchanged native receipt predicate but
        # did not retain raw receipt bytes. Preserve that original contract;
        # the complete source-bound journal/event history is its durable proof.
        _need(receipt['claim_sha256'] == sha(files[claim_name])
              and receipt['journal_sha256'] == sha(files[journal_name]), 'recovery_closed_session_review_binding')
    return {'name': name, 'claim_sha256': sha(files[claim_name]), 'journal_sha256': sha(files[journal_name]),
            'sequence': sequence, 'stage': previous}, used, {claim_name, journal_name, *(row[1] for row in rows)}


def _frontier_from_files(root, inventory_descriptor, review_descriptor, current, additions):
    inventory = _document(inventory_descriptor)
    expected = _inventory(inventory, root)
    review = _document(review_descriptor)
    configuration = _review(review, _path(root), inventory_descriptor['sha256'])
    extra = {}
    for row in additions:
        _keys(row, ('path', 'bytes', 'sha256'))
        name = _relative(row['path'])
        _need(name not in expected and name not in extra, 'recovery_addition_overlap')
        extra[name] = row
    _need(set(current) == set(expected) | set(extra), 'recovery_inventory_frontier_changed')
    for name, row in {**expected, **extra}.items():
        _need(len(current[name]) == row['bytes'] and sha(current[name]) == row['sha256'],
              'recovery_original_or_added_bytes_changed')
    original = {name: current[name] for name in expected}
    for name, raw in original.items():
        _no_refresh_or_mutation(name, strict_json(raw))
    claims = sorted(name[:-len('.claim.json')] for name in original if name.endswith('.claim.json'))
    _need(claims and review['unknown_session'] in claims and all(_SESSION.fullmatch(name) for name in claims),
          'recovery_non_session_claim_or_missing_unknown')
    covered, used, sessions = set(review['auxiliary_records']), set(), []
    _need(covered <= set(original), 'recovery_auxiliary_missing')
    for name in claims:
        summary, requests, paths = _session(original, name, review, configuration, failed=name == review['unknown_session'])
        sessions.append(summary)
        used |= requests
        covered |= paths
    _need(covered == set(original), 'recovery_orphan_or_unreviewed_state_record')
    _need(used == {(item['session'], item['sequence']) for item in review['request_preimages']},
          'recovery_unused_request_preimage')
    return {'format': 'irisx/recovery-frontier-v1', 'state_root': str(_path(root)),
            'inventory_sha256': inventory_descriptor['sha256'], 'review_sha256': review_descriptor['sha256'],
            'sessions': sessions, 'covered_unknown_session': review['unknown_session'],
            'controlled_refresh_dispatch': 'excluded_by_complete_inventory_and_exact_original_source_ordering',
            'original_authentication_outcome': 'UNKNOWN', 'original_native_process_closure': 'UNKNOWN'}


def validate_frontier(root, inventory_descriptor, review_descriptor, *, additions=()):
    """Re-read complete STATE and recompute original bindings; no count shortcut."""
    return _frontier_from_files(root, inventory_descriptor, review_descriptor, _scan(root), additions)


def _utc(value):
    _need(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z', value),
          'recovery_utc_format')
    try:
        parsed = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        result = parsed.timestamp()
    except (ValueError, OverflowError, OSError):
        raise RecoveryError('recovery_utc_value') from None
    _need(0 < result < 4102444800, 'recovery_utc_bounds')
    return result


def _observation(value, challenge, review):
    # Reuse the exact reviewed observer's pure validator; no observer collection
    # function is called here. This prevents drift in boot schema/uptime rules.
    observer = _reviewed_module(review['recovery_sources']['recovery_boot_probe.py'], 'boot')
    try:
        observer.validate_observation(observer.canonical_bytes(value), challenge=challenge,
            expected_source_sha256=review['boot_source_sha256'],
            expected_runtime_sha256=review['boot_runtime_sha256'])
    except (observer.ProbeError, ValueError, TypeError, KeyError):
        raise RecoveryError('recovery_boot_observer_rejected') from None
    fields = ('format', 'ok', 'challenge', 'host_install_sha256', 'observed_utc', 'last_boot_utc',
              'tick_count64_ms', 'windows_version', 'windows_build', 'source_sha256', 'runtime_sha256',
              'native_process_closure_verified', 'closure', 'auth_started', 'credential_contents_accessed',
              'provider_calls', 'network_used')
    _keys(value, fields, 'recovery_boot_schema')
    _need(value['format'] == 'irisx/windows-recovery-boot-observation-v1'
          and value['ok'] is True and value['challenge'] == challenge and _sha(challenge)
          and _sha(value['host_install_sha256'])
          and value['source_sha256'] == review['boot_source_sha256']
          and value['runtime_sha256'] == review['boot_runtime_sha256']
          and value['native_process_closure_verified'] is True and value['auth_started'] is False
          and value['credential_contents_accessed'] is False and type(value['provider_calls']) is int
          and value['provider_calls'] == 0 and value['network_used'] is False, 'recovery_boot_identity_or_scope')
    validate_closure(canonical({'format': 'irisx/windows-supervisor-result-v1', 'nonce': challenge,
        'ok': True, 'reason': 'worker_exit', 'closure': value['closure']}), nonce=challenge, exit_status=0)
    observed, boot = _utc(value['observed_utc']), _utc(value['last_boot_utc'])
    version, build = value['windows_version'], value['windows_build']
    _need(type(version) is str and re.fullmatch(r'[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,10}', version)
          and type(build) is str and re.fullmatch(r'[0-9]{1,10}', build)
          and version.split('.')[2] == build, 'recovery_windows_version')
    ticks = value['tick_count64_ms']
    _need(type(ticks) is int and 0 <= ticks < 2**64 and observed >= boot
          and abs((observed - boot) - ticks / 1000) <= BOOT_SKEW_SECONDS,
          'recovery_boot_native_uptime_inconsistent')
    return observed, boot


def _preparation(value):
    _keys(value, ('format', 'stage', 'state_root', 'challenge', 'prepared_epoch', 'expires_epoch',
                 'inventory', 'review', 'before_boot', 'frontier'), 'recovery_preparation_schema')
    _need(value['format'] == 'irisx/recovery-preparation-v1' and value['stage'] == 'prepared'
          and _sha(value['challenge']) and _number(value['prepared_epoch']) and _number(value['expires_epoch'])
          and 0 < value['expires_epoch'] - value['prepared_epoch'] <= MAX_EPOCH_SECONDS,
          'recovery_preparation_bounds')
    _path(value['state_root'])
    for key in ('inventory', 'review', 'before_boot'):
        _descriptor(value[key])
    return value


def validate_restart(preparation_descriptor, after_boot_descriptor, restart_descriptor, *, now_epoch):
    """Compare independent observations plus a reviewed trusted-host Restart receipt.

    Receipt fields bind the independently reviewed manual Start-menu Restart
    action to the preparation and an owner-authorization/witness-review digest.
    No script is invented to stand in for the actual witnessed manual action.
    Missing Windows event-log rows are acceptable; a changed boot timestamp
    alone, manual/sleep/hibernation/clock declarations and snapshots are not.
    """
    preparation = _preparation(_document(preparation_descriptor))
    review = _document(preparation['review'])
    before, after = _document(preparation['before_boot']), _document(after_boot_descriptor)
    before_time, before_boot = _observation(before, preparation['challenge'], review)
    after_time, after_boot = _observation(after, preparation['challenge'], review)
    _need(_number(now_epoch) and preparation['prepared_epoch'] <= now_epoch < preparation['expires_epoch']
          and abs(after_time - now_epoch) <= BOOT_SKEW_SECONDS, 'recovery_expired_or_stale_boot')
    _need(before['host_install_sha256'] == after['host_install_sha256']
          and before['windows_version'] == after['windows_version']
          and before['windows_build'] == after['windows_build'], 'recovery_host_install_changed')
    _need(before_boot < preparation['prepared_epoch'] < after_boot <= after_time
          and after_time > before_time and before_boot != after_boot,
          'recovery_full_restart_epoch_required')
    restart = _document(restart_descriptor)
    _keys(restart, ('format', 'preparation_sha256', 'challenge', 'host_install_sha256',
                   'before_observation_sha256', 'action', 'requested_utc', 'authority_sha256'),
          'recovery_controlled_restart_schema')
    requested = _utc(restart['requested_utc'])
    _need(restart['format'] == 'irisx/trusted-host-controlled-restart-v1'
          and restart['preparation_sha256'] == preparation_descriptor['sha256']
          and restart['challenge'] == preparation['challenge']
          and restart['host_install_sha256'] == before['host_install_sha256']
          and restart['before_observation_sha256'] == preparation['before_boot']['sha256']
          and restart['action'] == 'Restart'
          and restart['authority_sha256'] == sha(canonical(review['restart_authority']))
          and preparation['prepared_epoch'] <= requested <= after_boot,
          'recovery_controlled_restart_binding')
    return {'challenge': preparation['challenge'], 'host_install_sha256': after['host_install_sha256'],
            'last_boot_utc': after['last_boot_utc'], 'expires_epoch': preparation['expires_epoch']}


def _same_boot(preparation, baseline_descriptor, current_descriptor, now_epoch):
    review = _document(preparation['review'])
    baseline, current = _document(baseline_descriptor), _document(current_descriptor)
    baseline_time, _ = _observation(baseline, preparation['challenge'], review)
    current_time, _ = _observation(current, preparation['challenge'], review)
    _need(_number(now_epoch) and now_epoch < preparation['expires_epoch']
          and abs(current_time - now_epoch) <= BOOT_SKEW_SECONDS
          and current_time >= baseline_time and current['tick_count64_ms'] >= baseline['tick_count64_ms']
          and all(current[key] == baseline[key] for key in ('host_install_sha256', 'last_boot_utc',
                    'windows_version', 'windows_build', 'source_sha256', 'runtime_sha256')),
          'recovery_boot_changed_replayed_or_expired')


def _binding_review(value, preparation_descriptor, preparation):
    _keys(value, ('format', 'state_root', 'preparation_sha256', 'local_configuration_template',
                 'native_configuration_template', 'output_local_configuration_path',
                 'output_native_configuration_path', 'expected_remote_metadata'), 'recovery_binding_review_schema')
    _need(value['format'] == 'irisx/recovery-binding-review-v1'
          and value['state_root'] == preparation['state_root']
          and value['preparation_sha256'] == preparation_descriptor['sha256'], 'recovery_binding_review_identity')
    local = _document(value['local_configuration_template'])
    native = _document(value['native_configuration_template'])
    _need(local.get('format') == 'irisx/run008-windows-bridge-operator-config-v1'
          and local.get('state_root') == preparation['state_root']
          and native.get('format') == 'irisx/run008-windows-sdk-runtime-v1'
          and native.get('versions') == local.get('versions')
          and local.get('windows_bridge', {}).get('configuration', {}).get('sha256')
              == value['native_configuration_template']['sha256'], 'recovery_configuration_templates')
    _path(value['output_local_configuration_path'])
    _path(value['output_native_configuration_path'])
    _document(value['expected_remote_metadata'])
    return local, native


def _prefix(preparation):
    return 'recovery-epoch-' + preparation['challenge']


def _record_files(files, name, expected):
    claim, journal = name + '.claim.json', name + '-journal.json'
    _need(claim in files and journal in files, 'recovery_record_torn_or_missing')
    _need(strict_json(files[claim]) == expected and files[claim] == files[journal], 'recovery_record_bytes')
    rows = _event_rows(files, name)
    _need(len(rows) == 1 and rows[0][2] == files[claim], 'recovery_record_event_binding')
    return {claim, journal, rows[0][1]}


def _additions(root, files, paths):
    return [{'path': path, 'bytes': len(files[path]), 'sha256': sha(files[path])} for path in sorted(paths)]


def _load_chain(reservation_descriptor):
    reservation = _document(reservation_descriptor)
    _keys(reservation, ('format', 'stage', 'capability', 'capability_sha256', 'session_nonce', 'reserved_epoch'),
          'recovery_reservation_schema')
    capability = reservation['capability']
    _keys(capability, ('format', 'preparation', 'after_boot', 'restart', 'binding_review', 'challenge',
          'host_install_sha256', 'last_boot_utc', 'expires_epoch', 'allowed_operations', 'calls',
          'covered_unknown_session', 'created_epoch'), 'recovery_capability_schema')
    _need(reservation['format'] == 'irisx/recovery-reservation-v1' and reservation['stage'] == 'consumed'
          and _sha(reservation['session_nonce']) and reservation['capability_sha256'] == sha(canonical(capability))
          and _number(reservation['reserved_epoch']) and capability['format'] == 'irisx/recovery-read-only-capability-v1'
          and capability['allowed_operations'] == ALLOWED_OPERATIONS
          and type(capability['calls']) is list and 1 <= len(capability['calls']) <= 16,
          'recovery_reservation_capability_binding')
    for call in capability['calls']:
        _keys(call, ('operation', 'arguments'))
        _need(call['operation'] in READ_OPERATIONS and call['arguments'] == {}, 'recovery_capability_read_only')
    preparation = _preparation(_document(capability['preparation']))
    restarted = validate_restart(capability['preparation'], capability['after_boot'], capability['restart'],
                                 now_epoch=capability['created_epoch'])
    _need(all(capability[key] == value for key, value in restarted.items())
          and capability['covered_unknown_session'] == preparation['frontier']['covered_unknown_session']
          and preparation['prepared_epoch'] <= capability['created_epoch'] <= reservation['reserved_epoch']
              < capability['expires_epoch'], 'recovery_capability_epoch_binding')
    binding = _document(capability['binding_review'])
    _binding_review(binding, capability['preparation'], preparation)
    return reservation, capability, preparation, binding


def recovery_stanza(reservation_descriptor):
    reservation, capability, _, _ = _load_chain(reservation_descriptor)
    return {'capability_sha256': reservation['capability_sha256'],
            'reservation_sha256': reservation_descriptor['sha256'],
            **{key: capability[key] for key in ('challenge', 'host_install_sha256', 'last_boot_utc',
                                                'expires_epoch', 'allowed_operations')}}


def verify_generated_binding(reservation_descriptor, native_document, local_document):
    """Acyclic exact template overlay; no recovery/configuration self-hash cycle."""
    _, capability, preparation, binding = _load_chain(reservation_descriptor)
    local, native = _binding_review(binding, capability['preparation'], preparation)
    review = _document(preparation['review'])
    expected_native = strict_json(canonical(native))
    expected_native['format'] = 'irisx/run008-windows-sdk-recovery-runtime-v1'
    expected_native['recovery'] = recovery_stanza(reservation_descriptor)
    source = review['recovery_sources']['recovery_boot_probe.py']
    expected_native['sources']['recovery_boot_probe.py'] = {'bytes': source['bytes'], 'sha256': source['sha256']}
    _need(native_document == expected_native, 'recovery_native_template_overlay')
    expected_local = strict_json(canonical(local))
    row = expected_local['windows_bridge']['configuration']
    output = binding['output_native_configuration_path']
    _need(Path(output).parent == Path(row['wsl_path']).parent, 'recovery_native_output_directory_changed')
    row['wsl_path'] = output
    row['native_path'] = ntpath.join(ntpath.dirname(row['native_path']), Path(output).name)
    row['sha256'] = sha(canonical(native_document))
    _need(local_document == expected_local, 'recovery_local_template_overlay')


class RecoveryOwner:
    """One publisher-lock owner. Keep this context alive through native closure.

    `c` is the existing reviewed operator_common callback mapping. No file is
    created by the constructor or pure validators. A failed callback permanently
    latches this instance; restarting it cannot reissue an existing epoch claim.
    """
    def __init__(self, c):
        self.c = c
        self.root = _path(c['STATE'])
        self._lock = None
        self._active = self._failed = False
        self._reservations = set()
        self._admitted = set()

    def __enter__(self):
        _need(not self._active and self._lock is None, 'recovery_owner_reentry')
        self._lock = self.c['lock']('recovery-epoch')
        self._lock.__enter__()
        self._active = True
        return self

    def __exit__(self, *args):
        self._active = False
        return self._lock.__exit__(*args)

    def _guard(self):
        _need(self._active and not self._failed and _path(self.c['STATE']) == self.root,
              'recovery_external_publisher_lock_required')

    def _write(self, name, record):
        self._guard()
        try:
            before = _scan(self.root)
            claim = self.c['claim'](name, record)
            expected = self.root / (name + '.claim.json')
            _need(claim == descriptor(expected) and _document(claim) == record,
                  'recovery_claim_callback_binding')
            path = self.c['journal'](name, record)
            _need(_path(path) == self.root / (name + '-journal.json'), 'recovery_journal_callback_binding')
            after = _scan(self.root)
            added = _record_files(after, name, record)
            _need(not (added & set(before)) and set(after) == set(before) | added
                  and all(after[key] == raw for key, raw in before.items()), 'recovery_append_only_write')
            return claim
        except BaseException:
            self._failed = True
            raise

    def prepare(self, inventory_descriptor, review_descriptor, before_boot_descriptor, *,
                challenge, now_epoch, expires_epoch):
        self._guard()
        _need(_sha(challenge) and _number(now_epoch) and _number(expires_epoch)
              and 0 < expires_epoch - now_epoch <= MAX_EPOCH_SECONDS, 'recovery_epoch_bounds')
        frontier = validate_frontier(self.root, inventory_descriptor, review_descriptor)
        review = _document(review_descriptor)
        before = _document(before_boot_descriptor)
        observed, boot = _observation(before, challenge, review)
        _need(boot < now_epoch and 0 <= now_epoch - observed <= BOOT_SKEW_SECONDS,
              'recovery_preparation_boot_freshness')
        preparation = {'format': 'irisx/recovery-preparation-v1', 'stage': 'prepared',
            'state_root': str(self.root), 'challenge': challenge, 'prepared_epoch': now_epoch,
            'expires_epoch': expires_epoch, 'inventory': inventory_descriptor, 'review': review_descriptor,
            'before_boot': before_boot_descriptor, 'frontier': frontier}
        return self._write(_prefix(preparation), preparation)

    def _frontier(self, preparation, records=(), *, session_paths=()):
        files = _scan(self.root)
        paths = _record_files(files, _prefix(preparation), preparation)
        for suffix, record in records:
            paths |= _record_files(files, _prefix(preparation) + suffix, record)
        paths |= set(session_paths)
        result = validate_frontier(self.root, preparation['inventory'], preparation['review'],
                                   additions=_additions(self.root, files, paths))
        _need(result == preparation['frontier'], 'recovery_original_frontier_changed')
        return result

    def capability(self, preparation_descriptor, after_boot_descriptor, restart_descriptor, *,
                   binding_review_descriptor, calls, now_epoch):
        self._guard()
        preparation = _preparation(_document(preparation_descriptor))
        _need(preparation['state_root'] == str(self.root), 'recovery_preparation_wrong_namespace')
        self._frontier(preparation)
        restarted = validate_restart(preparation_descriptor, after_boot_descriptor, restart_descriptor,
                                     now_epoch=now_epoch)
        _binding_review(_document(binding_review_descriptor), preparation_descriptor, preparation)
        _need(type(calls) is list and 1 <= len(calls) <= 16, 'recovery_calls_bound')
        for call in calls:
            _keys(call, ('operation', 'arguments'))
            _need(call['operation'] in READ_OPERATIONS and call['arguments'] == {}, 'recovery_read_only_calls')
        return {'format': 'irisx/recovery-read-only-capability-v1', 'preparation': preparation_descriptor,
            'after_boot': after_boot_descriptor, 'restart': restart_descriptor,
            'binding_review': binding_review_descriptor, **restarted, 'allowed_operations': list(ALLOWED_OPERATIONS),
            'calls': strict_json(canonical({'calls': calls}))['calls'],
            'covered_unknown_session': preparation['frontier']['covered_unknown_session'], 'created_epoch': now_epoch}

    def reserve(self, capability, *, session_nonce, current_boot_descriptor, now_epoch):
        self._guard()
        _need(_sha(session_nonce), 'recovery_session_nonce')
        preparation = _preparation(_document(capability['preparation']))
        _need('native-bridge-' + session_nonce != capability['covered_unknown_session'], 'recovery_original_session_reuse')
        self._frontier(preparation)
        # Recompute the complete proposed capability, never trust its flags.
        expected = self.capability(capability['preparation'], capability['after_boot'], capability['restart'],
            binding_review_descriptor=capability['binding_review'], calls=capability['calls'],
            now_epoch=capability['created_epoch'])
        _need(capability == expected and capability['created_epoch'] <= now_epoch, 'recovery_capability_changed')
        _same_boot(preparation, capability['after_boot'], current_boot_descriptor, now_epoch)
        reservation = {'format': 'irisx/recovery-reservation-v1', 'stage': 'consumed', 'capability': capability,
            'capability_sha256': sha(canonical(capability)), 'session_nonce': session_nonce, 'reserved_epoch': now_epoch}
        # This exclusive claim is the irreversible consume point. A crash after
        # it cannot be repaired into a second capability or launch ticket.
        result = self._write(_prefix(preparation) + '-capability', reservation)
        self._reservations.add(result['sha256'])
        return result

    def verify_reservation(self, reservation_descriptor, *, current_boot_descriptor, now_epoch):
        self._guard()
        reservation, capability, preparation, _ = _load_chain(reservation_descriptor)
        _need(preparation['state_root'] == str(self.root), 'recovery_reservation_wrong_namespace')
        self._frontier(preparation, [('-capability', reservation)])
        _same_boot(preparation, capability['after_boot'], current_boot_descriptor, now_epoch)
        return recovery_stanza(reservation_descriptor)

    def admit_session(self, reservation_descriptor, *, current_boot_descriptor, now_epoch):
        self._guard()
        key = reservation_descriptor['sha256']
        _need(key in self._reservations and key not in self._admitted, 'recovery_launch_ticket_not_live_or_reused')
        stanza = self.verify_reservation(reservation_descriptor, current_boot_descriptor=current_boot_descriptor,
                                         now_epoch=now_epoch)
        reservation, capability, preparation, _ = _load_chain(reservation_descriptor)
        self._admitted.add(key)  # Never un-set, including callback/launch failure.
        launch = {'format': 'irisx/recovery-launch-v1', 'stage': 'launch_consumed',
                  'reservation': reservation_descriptor, 'session_nonce': reservation['session_nonce'],
                  'current_boot': current_boot_descriptor, 'admitted_epoch': now_epoch}
        launch_descriptor = self._write(_prefix(preparation) + '-launch', launch)
        unknown = preparation['frontier']['covered_unknown_session']
        original = next(row for row in preparation['frontier']['sessions'] if row['name'] == unknown)
        return {**stanza, 'native_recovery': stanza, 'session_nonce': reservation['session_nonce'], 'covered_unknown_session': unknown,
                'covered_claim_sha256': original['claim_sha256'], 'covered_journal_sha256': original['journal_sha256'],
                'covered_pending_claims': [{'claim': descriptor(self.root / (unknown + '.claim.json')),
                    'journal': descriptor(self.root / (unknown + '-journal.json'))}],
                'calls': [call['operation'] for call in capability['calls']], 'launch': launch_descriptor}

    def validate_frontier_reserved(self, reservation_descriptor):
        """For the one recovery-client initialization, before its session claim."""
        self._guard()
        _need(reservation_descriptor['sha256'] in self._admitted, 'recovery_launch_not_admitted')
        reservation, capability, preparation, _ = _load_chain(reservation_descriptor)
        launch = _document(descriptor(self.root / (_prefix(preparation) + '-launch.claim.json')))
        _need(launch['reservation'] == reservation_descriptor and launch['session_nonce'] == reservation['session_nonce'],
              'recovery_launch_reservation_binding')
        self._frontier(preparation, [('-capability', reservation), ('-launch', launch)])
        return {row['name']: row['claim_sha256'] for row in preparation['frontier']['sessions']
                if row['name'] == capability['covered_unknown_session']}

    def finalize(self, reservation_descriptor, *, session_name, receipt_bytes,
                 proxy_exit_status, observations, now_epoch):
        self._guard()
        _need(reservation_descriptor['sha256'] in self._admitted, 'recovery_finalize_not_admitted')
        reservation, capability, preparation, binding = _load_chain(reservation_descriptor)
        _need(session_name == 'native-bridge-' + reservation['session_nonce'] and _number(now_epoch)
              and reservation['reserved_epoch'] <= now_epoch < capability['expires_epoch'],
              'recovery_finalize_identity_or_expiry')
        launch_descriptor = descriptor(self.root / (_prefix(preparation) + '-launch.claim.json'))
        launch = _document(launch_descriptor)
        _need(launch['reservation'] == reservation_descriptor, 'recovery_finalize_launch_binding')
        local_descriptor = descriptor(binding['output_local_configuration_path'])
        native_descriptor = descriptor(binding['output_native_configuration_path'])
        local, native = _document(local_descriptor), _document(native_descriptor)
        verify_generated_binding(reservation_descriptor, native, local)
        _need(self.c['configured']().document_sha256 == local_descriptor['sha256'],
              'recovery_final_configuration_not_active')
        files = _scan(self.root)
        session_paths = _new_session(files, session_name, reservation_descriptor, reservation,
                                     capability, local_descriptor, native_descriptor)
        self._frontier(preparation, [('-capability', reservation), ('-launch', launch)], session_paths=session_paths)
        closure = validate_closure(receipt_bytes, nonce=reservation['session_nonce'], exit_status=proxy_exit_status)
        remote = validate_reconciliation(observations, binding, preparation)
        result = {'format': 'irisx/recovery-eligibility-v1', 'stage': 'eligible',
            'state_root': str(self.root), 'reservation': reservation_descriptor, 'launch': launch_descriptor,
            'session_name': session_name, 'session_files': _additions(self.root, files, session_paths),
            'local_configuration': local_descriptor, 'native_configuration': native_descriptor,
            'receipt': closure, 'receipt_sha256': sha(receipt_bytes),
            'receipt_text': receipt_bytes.decode('utf-8'), 'proxy_exit_status': proxy_exit_status,
            'remote': remote, 'completed_epoch': now_epoch,
            'original_authentication_outcome': 'UNKNOWN', 'original_native_process_closure': 'UNKNOWN'}
        eligible = self._write(_prefix(preparation) + '-eligibility', result)
        # One final exclusive index avoids rescanning an ever-growing ordinary
        # event history on later admission. No new token is issued. A crash
        # before this seal leaves the epoch unusable rather than replayable.
        before = _scan(self.root)
        original = _inventory(_document(preparation['inventory']), self.root)
        seal = {'format': 'irisx/recovery-completion-seal-v1', 'eligibility': eligible,
                'files': _additions(self.root, before, set(before) - set(original))}
        try:
            name = _prefix(preparation) + '-sealed'
            sealed = self.c['claim'](name, seal)
            _need(sealed == descriptor(self.root / (name + '.claim.json'))
                  and _document(sealed) == seal, 'recovery_completion_seal_callback')
            after = _scan(self.root)
            _need(set(after) == set(before) | {name + '.claim.json'}
                  and all(after[path] == raw for path, raw in before.items()), 'recovery_completion_seal_append_only')
        except BaseException:
            self._failed = True
            raise
        return eligible


def _reviewed_module(row, role):
    names = {'boot': 'recovery_boot_probe.py', 'protocol': 'protocol.py'}
    _need(role in names, 'recovery_pure_module_role')
    raw = verified(row)
    _need(raw == bounded_read(Path(__file__).absolute().with_name(names[role])),
          'recovery_pure_module_executing_source_changed')
    module = types.ModuleType('reviewed_recovery_' + role + '_' + row['sha256'])
    module.__file__ = row['path']
    exec(compile(raw, row['path'], 'exec', dont_inherit=True), module.__dict__)
    return module


def _protocol(review):
    return _reviewed_module(review['recovery_sources']['protocol.py'], 'protocol')


def validate_reconciliation(observations, binding_review, preparation):
    """Validate live, typed bracket results against independently reviewed bytes.

    The reviewed entrypoint obtains these five DTOs on the one admitted session.
    Hash strings supplied by a caller cannot stand in for the actual DTOs.
    Only computed hashes and fixed identity/status metadata are returned/saved.
    """
    _keys(observations, ('dataset_before', 'kernel_before', 'status', 'kernel_after', 'dataset_after'),
          'recovery_observation_bracket_schema')
    expected = _document(binding_review['expected_remote_metadata'])
    _keys(expected, ('format', 'dataset', 'kernel_metadata', 'notebook_source_sha256', 'provider_status'),
          'recovery_remote_expectation_schema')
    _need(expected['format'] == 'irisx/recovery-expected-remote-v1'
          and _sha(expected['notebook_source_sha256']) and expected['provider_status'] in
              ('COMPLETE', 'ERROR', 'CANCEL_ACKNOWLEDGED'), 'recovery_remote_expectation_identity')
    local = _document(binding_review['local_configuration_template'])
    predecessor = local['remote_predecessor']
    _need(expected['notebook_source_sha256'] == predecessor['notebook_source_sha256']
          and expected['provider_status'] == predecessor['provider_status'], 'recovery_remote_predecessor_binding')
    protocol = _protocol(_document(preparation['review']))
    try:
        for name, value in observations.items():
            protocol.validate_result(name.split('_')[0], value)
        protocol.validate_result('dataset', expected['dataset'])
    except (ValueError, TypeError, KeyError):
        raise RecoveryError('recovery_remote_dto_invalid') from None
    _need(observations['dataset_before'] == observations['dataset_after'] == expected['dataset'],
          'recovery_remote_dataset_changed')
    dataset = observations['dataset_before']
    _need(dataset['id'] == 12504696 and dataset['ref'] == 'danielwuu/iris-x-learning-agent-code-20261011'
          and dataset['isPrivate'] is True and dataset['currentVersionNumber'] == predecessor['code_version'],
          'recovery_remote_dataset_identity')
    before, after = observations['kernel_before'], observations['kernel_after']
    _need(before == after and before['metadata'] == expected['kernel_metadata'], 'recovery_remote_kernel_changed')
    metadata = before['metadata']
    _need(metadata['id'] == 138123872 and metadata['ref'] == 'danielwuu/iris-x-learning-agent-20261011'
          and metadata['isPrivate'] is True and metadata['currentVersionNumber'] == predecessor['notebook_version'],
          'recovery_remote_kernel_identity')
    source_hash = sha(before['blob']['source'].encode('utf-8'))
    _need(source_hash == expected['notebook_source_sha256'], 'recovery_remote_source_changed')
    status = observations['status']
    _need(status['status'] == expected['provider_status'] and status['failureMessage'] != 'GPU unavailable',
          'recovery_remote_status_or_gpu_stop')
    return {'format': 'irisx/recovery-remote-hashes-v1',
            'observation_sha256': {name: sha(canonical(value)) for name, value in observations.items()},
            'dataset_sha256': sha(canonical(dataset)), 'kernel_metadata_sha256': sha(canonical(metadata)),
            'notebook_source_sha256': source_hash, 'provider_status': status['status'],
            'expected_remote_sha256': binding_review['expected_remote_metadata']['sha256']}


def _new_session(files, name, reservation_descriptor, reservation, capability, local_descriptor, native_descriptor):
    claim_path, journal_path = name + '.claim.json', name + '-journal.json'
    _need(claim_path in files and journal_path in files, 'recovery_new_session_missing')
    claim, journal = strict_json(files[claim_path]), strict_json(files[journal_path])
    _need(claim.get('format') == 'irisx/windows-bridge-session-claim-v1'
          and claim.get('nonce') == reservation['session_nonce'] and claim.get('synthetic_test_only') is False
          and claim.get('configuration_sha256') == local_descriptor['sha256']
          and claim.get('bridge_configuration_sha256') == native_descriptor['sha256']
          and claim.get('recovery') == {'capability_sha256': reservation['capability_sha256'],
                                      'reservation_sha256': reservation_descriptor['sha256']}
          and _number(claim.get('deadline_epoch')) and claim['deadline_epoch'] <= capability['expires_epoch'],
          'recovery_new_session_claim_binding')
    _need(journal.get('stage') == 'closed' and journal.get('native_process_closure_verified') is True
          and journal.get('claim_sha256') == sha(files[claim_path])
          and journal.get('mutation_attempted') is False and journal.get('nonce') == reservation['session_nonce'],
          'recovery_new_session_not_closed')
    rows = _event_rows(files, name)
    _need(rows and rows[-1][2] == files[journal_path], 'recovery_new_session_event_frontier')
    operations = ['open', *(call['operation'] for call in capability['calls']), 'close']
    _need(operations == ['open', 'dataset', 'kernel', 'status', 'kernel', 'dataset', 'close'],
          'recovery_required_remote_bracket_order')
    sequence, previous, active = 0, None, None
    for _, _, raw in rows:
        proof = strict_json(raw)
        _no_refresh_or_mutation(name, proof)
        _need(proof.get('nonce') == reservation['session_nonce']
              and proof.get('claim_sha256') == sha(files[claim_path])
              and proof.get('synthetic_test_only') is False, 'recovery_new_event_binding')
        stage = proof.get('stage')
        if previous is None:
            _need(stage == 'launch_intent', 'recovery_new_event_initial')
        elif stage == 'operation_intent':
            _need(previous in ('launch_intent', 'authenticated', 'operation_accepted')
                  and not (previous == 'operation_accepted' and sequence == 1)
                  and type(proof.get('sequence')) is int and proof['sequence'] == sequence + 1
                  and sequence < len(operations) and proof.get('operation') == operations[sequence]
                  and _sha(proof.get('request_sha256')) and _number(proof.get('deadline_epoch'))
                  and proof['deadline_epoch'] <= claim['deadline_epoch'], 'recovery_new_event_operation_order')
            sequence += 1
            active = {key: proof[key] for key in ('operation', 'sequence', 'request_sha256', 'deadline_epoch')}
        elif stage == 'operation_accepted':
            _need(previous == 'operation_intent', 'recovery_new_event_acceptance')
        elif stage == 'authenticated':
            _need(previous == 'operation_accepted' and sequence == 1, 'recovery_new_event_authentication')
        elif stage == 'closed':
            _need(previous == 'operation_accepted' and sequence == len(operations), 'recovery_new_event_close')
        else:
            _need(False, 'recovery_new_session_uncertain')
        if stage not in ('launch_intent', 'operation_intent'):
            _need(active is not None and {key: proof.get(key) for key in active} == active,
                  'recovery_new_event_request_binding')
        _need(previous != 'closed', 'recovery_new_event_after_closure')
        previous = stage
    _need(previous == 'closed' and sequence == len(operations), 'recovery_new_sequence_incomplete')
    paths = {claim_path, journal_path, *(row[1] for row in rows)}
    paths |= _accepted_refresh(files, reservation['session_nonce'], rows, capability)
    return paths


def _accepted_refresh(files, nonce, session_events, capability):
    """One accepted existing-grant refresh, fully bound to this closed worker.

    The original failed epoch still requires no refresh records whatsoever.
    The new reviewed source orders the durable intent ACK before send and the
    accepted ACK before an operation response. A final closed worker and its
    accepted response are required in addition to these matching durable bytes.
    """
    names = [name[:-len('.claim.json')] for name in files
             if name.startswith('native-auth-refresh-') and name.endswith('.claim.json')
             and strict_json(files[name]).get('bridge_nonce') == nonce]
    _need(len(names) <= 1, 'recovery_refresh_count')
    if not names:
        return set()
    name = names[0]
    claim_path, journal_path = name + '.claim.json', name + '-journal.json'
    _need(journal_path in files, 'recovery_refresh_missing_journal')
    claim, journal = strict_json(files[claim_path]), strict_json(files[journal_path])
    _keys(claim, ('account', 'old_expiration_epoch', 'existing_grant_only', 'time_epoch',
                  'bridge_nonce', 'refresh_id', 'synthetic_test_only'), 'recovery_refresh_claim_schema')
    refresh_id = sha(canonical({'account': 'danielwuu', 'old_expiration_epoch': claim['old_expiration_epoch']}))
    _need(claim['account'] == 'danielwuu' and claim['bridge_nonce'] == nonce
          and claim['existing_grant_only'] is True and claim['synthetic_test_only'] is False
          and _number(claim['old_expiration_epoch']) and claim['old_expiration_epoch'] >= 0
          and _number(claim['time_epoch']) and claim['refresh_id'] == refresh_id
          and name == 'native-auth-refresh-' + refresh_id[:24], 'recovery_refresh_claim_binding')
    base = {'stage', 'claim_sha256', 'old_expiration_epoch', 'attempts', 'refresh_id',
            'bridge_nonce', 'sequence', 'request_sha256'}
    accepted_fields = {'new_expiration_epoch', 'official_save_completed', 'credential_acl_verified',
                       'new_grant_created', 'time_epoch'}
    rows = _event_rows(files, name)
    _need(len(rows) == 2 and rows[-1][2] == files[journal_path], 'recovery_refresh_event_frontier')
    intent, accepted = strict_json(rows[0][2]), strict_json(rows[1][2])
    _keys(intent, base, 'recovery_refresh_intent_schema')
    _keys(accepted, base | accepted_fields, 'recovery_refresh_accepted_schema')
    _need(intent['stage'] == 'refresh_intent' and accepted['stage'] == 'refresh_accepted'
          and all(accepted[key] == intent[key] for key in base - {'stage'})
          and intent['claim_sha256'] == sha(files[claim_path])
          and intent['old_expiration_epoch'] == claim['old_expiration_epoch']
          and type(intent['attempts']) is int and intent['attempts'] == 1
          and intent['refresh_id'] == refresh_id and intent['bridge_nonce'] == nonce
          and type(intent['sequence']) is int and 1 <= intent['sequence'] <= len(capability['calls']) + 1
          and _sha(intent['request_sha256']) and accepted['official_save_completed'] is True
          and accepted['credential_acl_verified'] is True and accepted['new_grant_created'] is False
          and _number(accepted['time_epoch']) and claim['time_epoch'] <= accepted['time_epoch'] < capability['expires_epoch']
          and _number(accepted['new_expiration_epoch'])
          and accepted['new_expiration_epoch'] > accepted['time_epoch'] + 300,
          'recovery_refresh_not_fully_accepted')
    relevant = [(stamp, strict_json(raw)) for stamp, _, raw in session_events]
    sent = [(stamp, proof) for stamp, proof in relevant if proof.get('stage') == 'operation_intent'
            and proof.get('sequence') == intent['sequence']]
    done = [(stamp, proof) for stamp, proof in relevant if proof.get('stage') == 'operation_accepted'
            and proof.get('sequence') == intent['sequence']]
    _need(len(sent) == len(done) == 1 and sent[0][1]['request_sha256'] == done[0][1]['request_sha256']
          == intent['request_sha256'] and sent[0][0] < rows[0][0] < rows[1][0] < done[0][0],
          'recovery_refresh_ack_operation_order')
    return {claim_path, journal_path, *(row[1] for row in rows)}


def _root_records(root):
    """Enumerate bounded root claims/journals, never future event bodies."""
    files, total = {}, 0
    with _directory(root) as fd:
        before = os.fstat(fd)
        names = sorted(os.listdir(fd))
        _need(len(names) <= FILE_COUNT_CAP, 'recovery_root_record_count')
        for name in names:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if name == 'events':
                _need(stat.S_ISDIR(info.st_mode), 'recovery_events_directory_type')
                continue
            _relative(name)
            files[name] = _read_at(fd, name, FILE_CAP)
            strict_json(files[name])
            total += len(files[name])
            _need(total <= TREE_CAP, 'recovery_root_record_bytes')
        _need(names == sorted(os.listdir(fd)) and _identity(before) == _identity(os.fstat(fd)),
              'recovery_root_record_race')
    return files


def validate_eligibility(c, current_config, pending_claims, *, current_boot_descriptor=None, now_epoch=None):
    """Validate a durable historical disposition, never a new execution token.

    Subsequent ordinary sessions and publication records are allowed to extend
    STATE. The original inventory and all recovery records stay byte-identical;
    every additional bridge session must satisfy the unchanged closed predicate,
    and no second/prepared/unfinished recovery epoch is ignored. Callers must
    still run original pending-refresh, mutation, source and fresh remote gates.
    """
    root = _path(c['STATE'])
    roots = _root_records(root)
    files = dict(roots)
    candidates = [name for name in files if re.fullmatch(r'recovery-epoch-[0-9a-f]{64}-eligibility\.claim\.json', name)]
    _need(len(candidates) == 1, 'recovery_successful_eligibility_required')
    eligibility_descriptor = descriptor(root / candidates[0])
    eligibility = _document(eligibility_descriptor)
    fields = ('format', 'stage', 'state_root', 'reservation', 'launch', 'session_name', 'session_files',
              'local_configuration', 'native_configuration', 'receipt', 'receipt_sha256', 'receipt_text',
              'proxy_exit_status', 'remote', 'completed_epoch', 'original_authentication_outcome',
              'original_native_process_closure')
    _keys(eligibility, fields, 'recovery_eligibility_schema')
    _need(eligibility['format'] == 'irisx/recovery-eligibility-v1' and eligibility['stage'] == 'eligible'
          and eligibility['state_root'] == str(root)
          and eligibility['original_authentication_outcome'] == eligibility['original_native_process_closure'] == 'UNKNOWN',
          'recovery_eligibility_identity')
    reservation, capability, preparation, binding = _load_chain(eligibility['reservation'])
    _need(preparation['state_root'] == str(root)
          and current_config.document_sha256 == binding['local_configuration_template']['sha256']
          and str(current_config.state_root) == str(root), 'recovery_eligibility_current_configuration')
    prefix = _prefix(preparation)
    seal_name = prefix + '-sealed.claim.json'
    _need(seal_name in roots, 'recovery_completion_seal_required')
    seal = strict_json(roots[seal_name])
    _keys(seal, ('format', 'eligibility', 'files'), 'recovery_completion_seal_schema')
    _need(seal['format'] == 'irisx/recovery-completion-seal-v1' and seal['eligibility'] == eligibility_descriptor,
          'recovery_completion_seal_identity')
    original_rows = _inventory(_document(preparation['inventory']), root)
    indexed_rows = _inventory({'format': 'irisx/recovery-inventory-v1', 'state_root': str(root),
                              'files': seal['files']}, root)
    _need(not (set(original_rows) & set(indexed_rows)) and seal_name not in indexed_rows,
          'recovery_completion_seal_overlap')
    for name, row in {**original_rows, **indexed_rows}.items():
        raw = bounded_read(root / name)
        _need(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'recovery_sealed_bytes_changed')
        files[name] = raw
    launch = _document(eligibility['launch'])
    _need(launch.get('reservation') == eligibility['reservation']
          and launch.get('session_nonce') == reservation['session_nonce'], 'recovery_eligibility_launch_binding')
    recovery_paths = _record_files(files, prefix, preparation)
    recovery_paths |= _record_files(files, prefix + '-capability', reservation)
    recovery_paths |= _record_files(files, prefix + '-launch', launch)
    recovery_paths |= _record_files(files, prefix + '-eligibility', eligibility)
    recovery_paths.add(seal_name)
    _need(not any('recovery-epoch-' in name and name not in recovery_paths for name in files),
          'recovery_other_epoch_or_outstanding_token')
    _need(eligibility['session_name'] == 'native-bridge-' + reservation['session_nonce'],
          'recovery_eligibility_session_identity')
    session_paths = _new_session(files, eligibility['session_name'], eligibility['reservation'], reservation,
        capability, eligibility['local_configuration'], eligibility['native_configuration'])
    _need(set(indexed_rows) == (recovery_paths - {seal_name}) | session_paths,
          'recovery_completion_seal_scope')
    _need(eligibility['session_files'] == _additions(root, files, session_paths), 'recovery_completed_session_changed')
    verify_generated_binding(eligibility['reservation'], _document(eligibility['native_configuration']),
                             _document(eligibility['local_configuration']))
    receipt_raw = eligibility['receipt_text'].encode('utf-8')
    _need(sha(receipt_raw) == eligibility['receipt_sha256'], 'recovery_eligibility_receipt_hash')
    _need(validate_closure(receipt_raw, nonce=reservation['session_nonce'],
          exit_status=eligibility['proxy_exit_status']) == eligibility['receipt'], 'recovery_eligibility_receipt_binding')
    _need(_number(eligibility['completed_epoch'])
          and reservation['reserved_epoch'] <= eligibility['completed_epoch'] < capability['expires_epoch'],
          'recovery_eligibility_completion_time')
    expected_remote = _document(binding['expected_remote_metadata'])
    remote = eligibility['remote']
    _keys(remote, ('format', 'observation_sha256', 'dataset_sha256', 'kernel_metadata_sha256',
                  'notebook_source_sha256', 'provider_status', 'expected_remote_sha256'))
    _need(remote['format'] == 'irisx/recovery-remote-hashes-v1'
          and remote['expected_remote_sha256'] == binding['expected_remote_metadata']['sha256']
          and remote['dataset_sha256'] == sha(canonical(expected_remote['dataset']))
          and remote['kernel_metadata_sha256'] == sha(canonical(expected_remote['kernel_metadata']))
          and remote['notebook_source_sha256'] == expected_remote['notebook_source_sha256']
          and remote['provider_status'] == expected_remote['provider_status'], 'recovery_eligibility_remote_binding')
    _keys(remote['observation_sha256'], ('dataset_before', 'kernel_before', 'status', 'kernel_after', 'dataset_after'))
    _need(all(_sha(value) for value in remote['observation_sha256'].values())
          and remote['observation_sha256']['dataset_before'] == remote['observation_sha256']['dataset_after']
              == remote['dataset_sha256']
          and remote['observation_sha256']['kernel_before'] == remote['observation_sha256']['kernel_after'],
          'recovery_eligibility_remote_bracket_hashes')
    original = _inventory(_document(preparation['inventory']), root)
    additions = set(files) - set(original)
    result = _frontier_from_files(root, preparation['inventory'], preparation['review'], files,
                                  _additions(root, files, additions))
    _need(result == preparation['frontier'], 'recovery_eligibility_original_frontier')
    # Ordinary later bridge sessions are never covered by the old disposition.
    for name in files:
        if not name.endswith('.claim.json') or name in original or name in recovery_paths or name in session_paths:
            continue
        stem = name[:-len('.claim.json')]
        if stem.startswith('native-bridge-'):
            journal_name = stem + '-journal.json'
            _need(journal_name in files, 'recovery_later_session_missing_journal')
            journal = strict_json(files[journal_name])
            _need(journal.get('stage') == 'closed' and journal.get('native_process_closure_verified') is True
                  and journal.get('claim_sha256') == sha(files[name]), 'recovery_later_session_unknown')
        elif stem.startswith('native-auth-refresh-'):
            journal_name = stem + '-journal.json'
            _need(journal_name in files, 'recovery_later_refresh_missing_journal')
            journal = strict_json(files[journal_name])
            _need(journal.get('stage') == 'refresh_accepted' and journal.get('claim_sha256') == sha(files[name]),
                  'recovery_later_refresh_unknown')
    unknown = result['covered_unknown_session']
    expected_pending = [{'claim': descriptor(root / (unknown + '.claim.json')),
                         'journal': descriptor(root / (unknown + '-journal.json'))}]
    _need(pending_claims == expected_pending, 'recovery_pending_claims_not_exactly_covered')
    review = _document(preparation['review'])
    if current_boot_descriptor is None:
        callback = c.get('recovery_boot_observation')
        _need(callable(callback), 'recovery_fresh_boot_observer_required')
        current_boot_descriptor = callback(review, preparation['challenge'])
    if now_epoch is None:
        now_epoch = time.time()
    # Historical disposition outlives its consumed capability's short lease,
    # but only on the exact same fresh native boot and reviewed source lineage.
    current = _document(current_boot_descriptor)
    observed, _ = _observation(current, preparation['challenge'], review)
    after = _document(capability['after_boot'])
    _need(_number(now_epoch) and now_epoch >= eligibility['completed_epoch']
          and abs(observed - now_epoch) <= BOOT_SKEW_SECONDS
          and current['tick_count64_ms'] >= after['tick_count64_ms']
          and all(current[key] == after[key] for key in ('host_install_sha256', 'last_boot_utc',
              'windows_version', 'windows_build', 'source_sha256', 'runtime_sha256')),
          'recovery_eligibility_boot_changed_or_stale')
    _need(_root_records(root) == roots, 'recovery_eligibility_root_frontier_race')
    return {unknown: next(row['claim_sha256'] for row in result['sessions'] if row['name'] == unknown)}

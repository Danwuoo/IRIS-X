"""Offline interpretation of one completed f5 recovery disposition.

Historical recovery and current-release admission are separate. The current
configuration is bound to its actual descriptor and this adapter's checkout;
STATE and scratch stay in the recovered namespace. Current source, candidate,
native configuration and runtime admission belong to the caller's existing
contract/configuration/source gates, not equality with a historical release.
A bounded current publication view preserves native/recovery records. Only
source-proven pre-worker rejections are separately interpreted without inventing
closure; their unchanged on-disk evidence is excluded from the old validator's
view. The original source checkout and recovery evidence stay
intact, without requiring a material-lineage receipt for each current release.
It does not load the historical configuration as a runtime, reopen a capability,
create records, authenticate,
contact a provider, or launch recovery. The caller retains its unchanged current
runtime/socket, source-review, pending-refresh and remote-state gates.

Every historical source descriptor AND the core's complete sibling source tree
must match the fixed f5 manifest before any historical Python is compiled. The
unchanged historical validator decides which original UNKNOWN was covered at
the sealed completion time. Fresh live admission is checked separately: a
later clock adjustment or boot cannot undo that historical termination boundary.
This does not establish current same-boot identity or global process absence.
A pre-worker disposition never borrows the historical recovery's coverage.
One separately pinned accepted read-only frontier can also remain unclosed after
its real, source-bound native-absence cut. This is independent noninterference,
not recovery coverage or Job-zero proof. Its original records remain immutable;
a kernel-backed publisher owner and per-command/auth-ACK rechecks gate each new
session, while the original native mutex and all current admission gates remain.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import types

HISTORICAL_COMMIT = 'f5f780cb5823579288385158ce6da70a1ca33899'
SOURCE_PINS_SHA256 = '09e51f695d1dfd216f162b8451cd34331f35f9d137da749bc35e4fde8f6882a7'
PUBLICATION_STATE_SHA256 = '85101ee677e9c768cc8a5583cbf8df222a9198338040e0f0260bd87a96e9ea77'
PREWORKER_SOURCE_SHA256 = '8624ebfbaf3c620a995723cb5dde23cb52b07b2f03afef406879f1fc0829e9b9'
SOURCE_NAMES = frozenset(('bridge_client.py', 'config.py', 'launch.py', 'native_auth.py',
    'native_config.py', 'native_probe.py', 'operator_common.py', 'protocol.py',
    'recovery_boot_probe.py', 'recovery_entry.py', 'recovery_epoch.py', 'rl_collect.py',
    'rl_transport.py', 'sdk-lock.json', 'sdk_worker.py', 'verify_active_wire.py',
    'win_runtime.py', 'win_supervisor.py'))
FILE_CAP = 4 * 1024**2
FILE_COUNT_CAP = 512
PACKAGE_SUFFIX = ('tools', 'arc_qwen_rlvr004_20261013',
                  'publication_windows_bridge_20261015', 'context_continuation.py')


class ContextError(ValueError):
    """Fixed non-secret fail-closed diagnostic."""


def _need(value, code):
    if not value:
        raise ContextError(code)


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _path(value):
    _need(type(value) is str or isinstance(value, Path), 'context_path_type')
    text = str(value)
    path = Path(text)
    _need(path.is_absolute() and str(path) == text and '..' not in path.parts
          and not text.startswith('//') and len(text) <= 4096
          and not any(ord(ch) < 32 for ch in text), 'context_absolute_path')
    return path


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def _directory(path):
    path = _path(path)
    descriptors, identities = [], []
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        descriptors.append(fd)
        for component in path.parts[1:]:
            before = os.stat(component, dir_fd=fd, follow_symlinks=False)
            _need(stat.S_ISDIR(before.st_mode), 'context_directory_type')
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                            | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=fd)
            descriptors.append(child)
            opened = os.fstat(child)
            _need(stat.S_ISDIR(opened.st_mode) and (before.st_dev, before.st_ino)
                  == (opened.st_dev, opened.st_ino), 'context_directory_race')
            identities.append((fd, component, before.st_dev, before.st_ino))
            fd = child
        yield fd
        for parent, name, device, inode in identities:
            after = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _need(stat.S_ISDIR(after.st_mode) and (after.st_dev, after.st_ino)
                  == (device, inode), 'context_directory_replaced')
    except OSError:
        raise ContextError('context_file_unavailable') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _read_at(directory, name):
    before = os.stat(name, dir_fd=directory, follow_symlinks=False)
    _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
          and 0 < before.st_size <= FILE_CAP, 'context_bounded_single_link_file')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                 dir_fd=directory)
    with os.fdopen(fd, 'rb') as stream:
        _need(_identity(os.fstat(fd)) == _identity(before), 'context_file_open_race')
        raw = stream.read(FILE_CAP + 1)
        after = os.stat(name, dir_fd=directory, follow_symlinks=False)
        _need(len(raw) == before.st_size and len(raw) <= FILE_CAP
              and _identity(os.fstat(fd)) == _identity(before) == _identity(after),
              'context_file_read_race')
    return raw


def _read(path):
    path = _path(path)
    with _directory(path.parent) as fd:
        return _read_at(fd, path.name)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    _need(type(raw) is bytes and 0 < len(raw) <= FILE_CAP, 'context_json_bound')
    def pairs(items):
        value = {}
        for key, item in items:
            _need(key not in value, 'context_duplicate_json_key')
            value[key] = item
        return value
    def integer(value):
        _need(len(value) <= 24, 'context_integer_bound')
        return int(value)
    def number(value):
        result = float(value)
        _need(math.isfinite(result), 'context_nonfinite_json')
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
            parse_float=number, parse_constant=lambda _: _need(False, 'context_nonfinite_json'))
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, ContextError):
            raise
        raise ContextError('context_invalid_json') from None
    pending, count = [(result, 0)], 0
    while pending:
        value, depth = pending.pop()
        count += 1
        _need(count <= 100000 and depth <= 32, 'context_json_complexity')
        if type(value) is dict:
            pending.extend((item, depth + 1) for item in value.values())
        elif type(value) is list:
            pending.extend((item, depth + 1) for item in value)
        elif type(value) is str:
            _need(len(value) <= 65536, 'context_string_bound')
    _need(type(result) is dict, 'context_json_object')
    return result


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _verified(row):
    _need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'context_descriptor_schema')
    _need(type(row['bytes']) is int and 0 < row['bytes'] <= FILE_CAP
          and _sha(row['sha256']), 'context_descriptor_bounds')
    raw = _read(row['path'])
    _need(len(raw) == row['bytes'] and _digest(raw) == row['sha256'], 'context_descriptor_changed')
    return raw


def _pins():
    raw = _read(_path(Path(__file__).absolute()).with_name('context-source-pins.json'))
    _need(_digest(raw) == SOURCE_PINS_SHA256, 'context_source_manifest_changed')
    value = _json(raw)
    _need(set(value) == {'format', 'commit', 'sources'}
          and value['format'] == 'irisx/context-source-pins-v1'
          and value['commit'] == HISTORICAL_COMMIT
          and type(value['sources']) is dict and set(value['sources']) == SOURCE_NAMES,
          'context_source_manifest_schema')
    for row in value['sources'].values():
        _need(type(row) is dict and set(row) == {'bytes', 'sha256'}
              and type(row['bytes']) is int and 0 < row['bytes'] <= FILE_CAP
              and _sha(row['sha256']), 'context_source_manifest_row')
    return value['sources']


def _source(raw, name, pins):
    _need({'bytes': len(raw), 'sha256': _digest(raw)} == pins[name], 'context_source_not_pinned_f5')


def _sources(review, pins):
    rows = review.get('recovery_sources')
    _need(type(rows) is dict and set(rows) == SOURCE_NAMES, 'context_historical_source_closure')
    for name, row in rows.items():
        _source(_verified(row), name, pins)
    # Reviewed copies may live elsewhere; the core's own complete sibling tree
    # must independently be exact f5. Historical helpers compare these bytes.
    parent = _path(rows['recovery_epoch.py']['path']).parent
    core_path, core_raw = parent / 'recovery_epoch.py', None
    for name in sorted(SOURCE_NAMES):
        raw = _read(parent / name)
        _source(raw, name, pins)
        if name == 'recovery_epoch.py':
            core_raw = raw
    return core_path, core_raw


def _eligibility(root):
    with _directory(root) as fd:
        before = os.fstat(fd)
        names = sorted(os.listdir(fd))
        _need(len(names) <= FILE_COUNT_CAP, 'context_root_record_count')
        matches = [name for name in names if re.fullmatch(
            r'recovery-epoch-[0-9a-f]{64}-eligibility\.claim\.json', name)]
        _need(len(matches) == 1, 'context_successful_eligibility_required')
        raw = _read_at(fd, matches[0])
        _need(names == sorted(os.listdir(fd)) and _identity(before) == _identity(os.fstat(fd)),
              'context_root_record_race')
    row = {'path': str(root / matches[0]), 'bytes': len(raw), 'sha256': _digest(raw)}
    return row, raw


def _repository_context(current, original, configured):
    source = _path(Path(__file__).absolute())
    _need(source.parts[-len(PACKAGE_SUFFIX):] == PACKAGE_SUFFIX,
          'context_adapter_repository_location')
    actual_root = source.parents[len(PACKAGE_SUFFIX) - 1]
    current_root = _path(current.get('repository_root'))
    original_root = _path(original.get('repository_root'))
    configured_root = _path(configured.repository_root)
    _need(current_root == configured_root == actual_root, 'context_actual_repository_binding')
    with _directory(original_root) as old_fd, _directory(current_root) as new_fd:
        old, new = os.fstat(old_fd), os.fstat(new_fd)
        if current_root != original_root:
            _need((old.st_dev, old.st_ino) != (new.st_dev, new.st_ino),
                  'context_repository_inode_alias')
            _need(not current_root.is_relative_to(original_root)
                  and not original_root.is_relative_to(current_root), 'context_repository_roots_overlap')
            for key in ('candidate_root', 'scratch_root', 'state_root', 'evidence_root'):
                operational = _path(original.get(key))
                _need(not current_root.is_relative_to(operational)
                      and not operational.is_relative_to(current_root), 'context_repository_operational_overlap')


def _shared_context(current, original, configured):
    # Recovery covers this existing owner namespace, never a fresh STATE or
    # scratch root. Other current-release fields are admitted independently.
    for key in ('state_root', 'scratch_root'):
        _need(_path(current.get(key)) == _path(original.get(key))
              == _path(getattr(configured, key)), 'context_shared_' + key)
    for document in (current, original):
        runtime = document.get('runtime')
        _need(type(runtime) is dict, 'context_runtime_schema')
        selectors = runtime.get('interop_environment_sha256')
        _need(type(selectors) is dict and set(selectors) == {'WSL_INTEROP'}
              and _sha(selectors['WSL_INTEROP']), 'context_interop_selector_schema')


def _current_helper(name, digest):
    path = _path(Path(__file__).absolute()).with_name(name)
    raw = _read(path)
    _need(_digest(raw) == digest, 'context_current_helper_source_pin')
    module = types.ModuleType('reviewed_context_helper_' + digest)
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), module.__dict__)
    return module


def _events(root):
    """Read existing journal evidence; this creates no disposition or receipt."""
    result, total = {}, 0
    with _directory(root / 'events') as fd:
        before = os.fstat(fd)
        names = sorted(os.listdir(fd))
        _need(len(names) <= 100000, 'context_event_count')
        for name in names:
            _need(re.fullmatch(r'[0-9]+-[a-zA-Z0-9-]+-[0-9a-f]{8}\.json', name)
                  is not None, 'context_event_name')
            raw = _read_at(fd, name)
            total += len(raw)
            _need(total <= 256 * 1024**2, 'context_event_bytes')
            result['events/' + name] = raw
        _need(names == sorted(os.listdir(fd)) and _identity(before) == _identity(os.fstat(fd)),
              'context_event_directory_race')
    return result


# One reviewed, real temporal cut. These are original private artifact hashes,
# never hashes of projections or a generic authorization for future UNKNOWNs.
READONLY_NONCE = 'edd2178a2018c21c9e8d5a9b64231a15930efa555bebe874644131401303e253'
READONLY_RESULT = (2759, '419b60845f9e6778b0c9495c65b19f98e2def2ff84162b169856a326554e1e23')
READONLY_ARTIFACTS = {
    'query': ('../query_processes_v2.ps1', 15232, 'd07f3cce2e3e4338e5ae3f676088ae48d3082f36b2706fc015d1005b8a8bba7b'),
    'controller': ('../hold_lock_and_query_v2.py', 12625, '5cd894522400adf3edc2afc76dc2103a3fd3e887e1d2328f730b531a11170b54'),
    'raw_stdout': ('QUERY-STDOUT.raw', 2666, 'c0d821305f8892353267eb0b39796a3400e53c61cb6d2d36e02011db83698bdf'),
    'raw_stderr': ('QUERY-STDERR.raw', 0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'before_snapshot': ('before/SNAPSHOT.json', 812823, '3113534d25c89375bd0b3bdacee225d1dd5b17d6679768001bd7099dd6ce9e6b'),
    'after_snapshot': ('after/SNAPSHOT.json', 812823, 'e223409f602a431d24c84a6d59b7913024aa8c2ac3cc6c52ceaa9b5eeb170e9b'),
}
READONLY_CLAIM = (615, '7ea1cfe05ed126e7c5c9cb2eeaf48231f2d62a475ec27fc4889e3f56e42172d1')
READONLY_JOURNAL = (489, '396cb624c8c2cac02f9a0ab594253071055f55fe3c6160639c012ac1a5b4af11')
READONLY_CALLER = {
    'jit': (4677, '5720fab593246b99084f549286949e1943d86614a434636c42c2cb11eefb7b66'),
    'owner': (6271, 'b110b0a4d33a848411fd94c169464bc90e422e3da06f2407002d5f0a76fc393a'),
    'seq14': (378, '426ef13f3cbc2018ce905b22907ef0f6513330cf7b682d9bbb4abdc540d459fb'),
    'owner_start': (7766, 'b74ef1a7015c27440fa0fcf496fc8361207f274f4e138aa6f2334c302f670ebf'),
}
READONLY_SID_SHA256 = 'cfeb24bac7fb88809b0621ff922c8baacb022600a890ce1ba25f42ddd6e67da6'
READONLY_STATE_SHA256 = 'f82758d953e63e77722e286f6fa777910c89653d7eb63929c365b1810246aa33'
NATIVE_PREFIXES = ('native-bridge-', 'native-auth-refresh-', 'recovery-epoch-')


def _metadata(raw):
    return {'bytes': len(raw), 'sha256': _digest(raw)}


def _readonly_verified(row):
    if row.get('bytes') != 0:
        return _verified(row)
    _need(set(row) == {'path', 'bytes', 'sha256'} and row['sha256'] == _digest(b''),
          'context_presence_empty_descriptor')
    path = _path(row['path'])
    with _directory(path.parent) as directory:
        before = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == 0,
              'context_presence_stderr_not_empty')
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=directory)
        with os.fdopen(fd, 'rb') as stream:
            _need(_identity(os.fstat(fd)) == _identity(before) and stream.read(1) == b''
                  and _identity(os.fstat(fd)) == _identity(before)
                  == _identity(os.stat(path.name, dir_fd=directory, follow_symlinks=False)),
                  'context_presence_stderr_changed')
    return b''


def _native_roots(root):
    result, total = {}, 0
    with _directory(root) as fd:
        before = os.fstat(fd)
        names = sorted(os.listdir(fd))
        _need(len(names) <= FILE_COUNT_CAP, 'context_root_record_count')
        for name in names:
            if name.startswith(NATIVE_PREFIXES):
                raw = _read_at(fd, name)
                total += len(raw)
                _need(total <= 64 * 1024**2, 'context_native_root_bytes')
                result[name] = raw
        _need(names == sorted(os.listdir(fd)) and _identity(before) == _identity(os.fstat(fd)),
              'context_native_root_race')
    return result


def _readonly_events(root):
    result = {}
    with _directory(root / 'events') as fd:
        names = sorted(os.listdir(fd))
        _need(len(names) <= 100000, 'context_event_count')
        selected = [name for name in names if '-native-bridge-' + READONLY_NONCE + '-' in name]
        _need(len(selected) == 196, 'context_readonly_event_frontier')
        for name in selected:
            _need(re.fullmatch(r'[0-9]+-native-bridge-' + READONLY_NONCE + r'-[0-9a-f]{8}\.json', name),
                  'context_readonly_event_name')
            result['events/' + name] = _read_at(fd, name)
        # Other sessions may append events; this exact old nonce may not.
        _need(selected == [name for name in sorted(os.listdir(fd))
              if '-native-bridge-' + READONLY_NONCE + '-' in name], 'context_readonly_event_race')
    return result


def _readonly_history(claim_raw, journal_raw, events):
    _need((len(claim_raw), _digest(claim_raw)) == READONLY_CLAIM
          and (len(journal_raw), _digest(journal_raw)) == READONLY_JOURNAL,
          'context_readonly_exact_frontier')
    claim, journal = _json(claim_raw), _json(journal_raw)
    base = {'format': 'irisx/windows-bridge-session-journal-v1', 'nonce': READONLY_NONCE,
        'claim_sha256': _digest(claim_raw), 'synthetic_test_only': False,
        'native_process_closure_verified': False, 'mutation_attempted': False}
    _need(claim['nonce'] == READONLY_NONCE and claim['synthetic_test_only'] is False,
          'context_readonly_claim')
    rows = [_json(raw) for _, raw in sorted(events.items())]
    _need(len(rows) == 196 and rows[0] == {**base, 'stage': 'launch_intent'},
          'context_readonly_launch_history')
    index = 1
    for sequence in range(1, 98):
        intent, accepted = rows[index:index + 2]
        _need(set(intent) == set(base) | {'stage', 'sequence', 'operation', 'request_sha256', 'deadline_epoch'}
              and all(intent.get(key) == value for key, value in base.items())
              and intent['stage'] == 'operation_intent' and type(intent['sequence']) is int
              and intent['sequence'] == sequence and _sha(intent['request_sha256'])
              and type(intent['deadline_epoch']) in (float, int)
              and 0 < intent['deadline_epoch'] <= claim['deadline_epoch']
              and intent['operation'] in (('open',) if sequence == 1 else
                  ('dataset', 'kernel', 'status', 'list_files', 'output', 'dataset_download', 'binary_metadata'))
              and accepted == {**intent, 'stage': 'operation_accepted'},
              'context_readonly_operation_history')
        index += 2
        if sequence == 1:
            _need(rows[index] == {**accepted, 'stage': 'authenticated'},
                  'context_readonly_authenticated_history')
            index += 1
    _need(rows[-1] == journal and journal['operation'] == 'kernel', 'context_readonly_final_history')
    # Per-command max_seconds/raw frames were not persisted. We verify the
    # durable source-bound intent/accepted pairs, not an invented preimage.


def _presence_documents(result, stdout, before, after):
    _need(result['format'] == 'irisx/readonly-native-process-presence-summary-v1'
          and result['status'] == 'QUERY_COMPLETED' and result['query_exit_code'] == 0
          and result['query_parse_error'] is None, 'context_presence_query_failed')
    for key in ('STATE_bytes_unchanged', 'lock_held_through_both_snapshots',
                'original_accepted97_frontier_unchanged', 'refresh_metadata_unchanged',
                'publisher_lock_bytes_unchanged', 'source_and_config_bytes_unchanged',
                'native_source_7_after_equal_config', 'no_new_STATE_intent_UNKNOWN_or_refresh'):
        _need(result[key] is True, 'context_presence_cut_incomplete')
    _need(all(type(result[key]) is int and result[key] == 0 for key in
              ('Job', 'STATE_writes', 'auth', 'old_pipe', 'process_control', 'provider'))
          and all(result[key] is False for key in
              ('admission_created', 'historical_Job_zero_proven', 'old_closure_modified')),
          'context_presence_readonly_required')
    _need(stdout['format'] == 'irisx/readonly-cim-native-process-presence-v1'
          and stdout['classification'] == 'ABSENT' and stdout['candidates'] == []
          and stdout['issues'] == [] and stdout['queried_basenames'] == ['python.exe']
          and stdout['original_job_zero_proven'] is False and stdout['historical_closure_changed'] is False
          and _digest(stdout['executor_sid'].encode()) == READONLY_SID_SHA256,
          'context_presence_absence_required')
    for key in ('enumeration_complete', 'executor_sid_equal_config', 'configuration_sha256_equal',
                'query_source_sha256_equal', 'native_sources_equal_config', 'native_executables_equal_config'):
        _need(stdout[key] is True, 'context_presence_incomplete')
    for key in ('candidate_count', 'enumerated_candidate_count', 'same_sid_count', 'other_sid_count',
                'unknown_sid_count', 'same_or_unknown_sid_incomplete_count', 'missing_field_count'):
        _need(type(stdout[key]) is int and stdout[key] == 0, 'context_presence_ambiguity')
    _need(type(stdout['enumeration_query_count']) is int and stdout['enumeration_query_count'] == 1
          and stdout['role_counts'] == {'other_edd_nonce_python': 0, 'sdk_worker': 0, 'win_supervisor': 0}
          and all(stdout.get(key) == value for key, value in result['observation'].items()),
          'context_presence_summary_binding')
    for value in (before, after):
        _need(set(value) == {'format', 'observed_epoch', 'files', 'file_count', 'edd_event_count',
              'edd_event_inventory', 'refresh_inventory', 'original_accepted97_frontier_unchanged', 'snapshot_scope'}
              and value['format'] == 'irisx/readonly-presence-state-snapshot-v1'
              and value['original_accepted97_frontier_unchanged'] is True
              and value['file_count'] == len(value['files']) == 3511
              and value['edd_event_count'] == len(value['edd_event_inventory']) == 196
              and len(value['refresh_inventory']) == 4, 'context_presence_inventory_schema')
        for name, row in value['files'].items():
            _need(type(name) is str and len(name) <= 4096 and not name.startswith('/')
                  and all(part not in ('', '.', '..') for part in name.split('/'))
                  and not any(ord(ch) < 32 for ch in name) and type(row) is dict
                  and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int
                  and 0 <= row['bytes'] <= 2**63 - 1 and _sha(row['sha256']),
                  'context_presence_inventory_row')
        for key in ('edd_event_inventory', 'refresh_inventory'):
            _need(all(value['files'].get(name) == row for name, row in value[key].items()),
                  'context_presence_inventory_subset')
    _need(all(before[key] == after[key] for key in ('files', 'edd_event_inventory', 'refresh_inventory'))
          and result['started_epoch'] <= before['observed_epoch'] <= after['observed_epoch'] <= result['finished_epoch'],
          'context_presence_postcut_inventory')
    # Native and WSL clocks are distinct. The fixed controller source proves
    # before -> synchronous query completion -> after, under the same flock.


def _readonly_guard(c, root, baseline, events, refresh_events, evidence):
    def guard(own_nonce=None, in_flight_refresh=None):
        c['publisher_lock_owner']()
        _need(own_nonce is None or (_sha(own_nonce) and own_nonce != READONLY_NONCE),
              'context_readonly_successor_nonce')
        for row, raw in evidence:
            _need(_readonly_verified(row) == raw, 'context_readonly_evidence_changed')
        current = _native_roots(root)
        _need(all(current.get(name) == raw for name, raw in baseline.items()),
              'context_readonly_old_root_changed')
        additions = set(current) - set(baseline)
        own_prefix = 'native-bridge-' + own_nonce if own_nonce else ''
        own_names = {own_prefix + '.claim.json', own_prefix + '-journal.json'} if own_nonce else set()
        if additions & own_names:
            _need(own_names <= additions, 'context_readonly_successor_pair')
            claim = _json(current[own_prefix + '.claim.json'])
            journal = _json(current[own_prefix + '-journal.json'])
            _need(claim.get('nonce') == journal.get('nonce') == own_nonce
                  and journal.get('claim_sha256') == _digest(current[own_prefix + '.claim.json'])
                  and claim.get('synthetic_test_only') is False
                  and journal.get('synthetic_test_only') is False
                  and journal.get('native_process_closure_verified') is False
                  and journal.get('stage') in ('launch_intent', 'operation_intent', 'operation_accepted', 'authenticated'),
                  'context_readonly_successor_binding')
            additions -= own_names
        for name in sorted(additions):
            if name.endswith('-journal.json'):
                continue
            _need(re.fullmatch(r'native-auth-refresh-[0-9a-f]{24}\.claim\.json', name),
                  'context_readonly_new_root')
            journal_name = name[:-len('.claim.json')] + '-journal.json'
            _need(journal_name in additions, 'context_readonly_refresh_pair')
            claim, journal = _json(current[name]), _json(current[journal_name])
            _need(own_nonce is not None and claim.get('bridge_nonce') == journal.get('bridge_nonce') == own_nonce
                  and journal.get('claim_sha256') == _digest(current[name])
                  and claim.get('synthetic_test_only') is False
                  and (in_flight_refresh is None or in_flight_refresh.get('name') != name[:-len('.claim.json')]
                       or in_flight_refresh.get('proof') == journal)
                  and ((journal.get('stage') == 'refresh_accepted' and journal.get('new_grant_created') is False)
                       or (type(in_flight_refresh) is dict and in_flight_refresh.get('name') == name[:-len('.claim.json')]
                           and in_flight_refresh.get('proof') == journal
                           and journal.get('stage') == 'refresh_intent' and claim.get('existing_grant_only') is True)),
                  'context_readonly_new_refresh_unknown')
        _need(all(name.endswith('.claim.json') or name[:-len('-journal.json')] + '.claim.json' in additions
                  for name in additions), 'context_readonly_orphan_journal')
        _need(_readonly_events(root) == events, 'context_readonly_event_changed')
        for name, raw in refresh_events.items():
            _need(_read(root / name) == raw, 'context_readonly_refresh_event_changed')
        _need(_native_roots(root) == current, 'context_readonly_roots_changed_during_check')
        c['publisher_lock_owner']()
    return guard


def _classify_readonly(c, root, roots, pending_claims, actual):
    prefix = 'native-bridge-' + READONLY_NONCE
    names = {prefix + '.claim.json', prefix + '-journal.json'}
    if not names & roots.keys():
        return None
    _need(names <= roots.keys(), 'context_readonly_pair_required')
    callback = c.get('readonly_frontier_descriptor')
    _need(callable(callback) and callable(c.get('publisher_lock_owner')),
          'context_readonly_review_and_owner_required')
    c['publisher_lock_owner']()
    _need(_digest(str(root).encode()) == READONLY_STATE_SHA256, 'context_readonly_original_namespace')
    row = callback()
    _need(type(row) is dict and (row.get('bytes'), row.get('sha256')) == READONLY_RESULT,
          'context_readonly_fixed_cut_required')
    result_raw = _verified(row)
    result, evidence = _json(result_raw), [(row, result_raw)]
    caller_callback = c.get('readonly_caller_descriptors')
    _need(callable(caller_callback), 'context_readonly_caller_required')
    caller = caller_callback()
    _need(type(caller) is dict and set(caller) == set(READONLY_CALLER), 'context_readonly_caller_schema')
    for key, expected in READONLY_CALLER.items():
        item = caller[key]
        _need(type(item) is dict and (item.get('bytes'), item.get('sha256')) == expected,
              'context_readonly_caller_pin')
        evidence.append((item, _verified(item)))
    work = _path(caller['seq14']['path']).parent
    _need(_path(caller['seq14']['path']).name == '0014.json'
          and _path(caller['jit']['path']) == work.parent / 'jit_original_sequence.py'
          and _path(caller['owner']['path']) == work.parent / 'owner.py'
          and _path(caller['owner_start']['path']).name == 'OWNER-START.json',
          'context_readonly_caller_relationship')
    parent = _path(row['path']).parent
    documents = {}
    for key, (relative, size, digest) in READONLY_ARTIFACTS.items():
        _need(result[key] == {'bytes': size, 'sha256': digest}, 'context_readonly_cut_artifact')
        parts = relative.split('/')
        path = parent.parent / parts[1] if parts[0] == '..' else parent.joinpath(*parts)
        descriptor = {'path': str(path), 'bytes': size, 'sha256': digest}
        raw = _readonly_verified(descriptor)
        evidence.append((descriptor, raw))
        if key in ('raw_stdout', 'before_snapshot', 'after_snapshot'):
            documents[key] = _json(raw)
    _presence_documents(result, documents['raw_stdout'], documents['before_snapshot'], documents['after_snapshot'])
    _need(result['original_WSL_config_sha256'] ==
          '0801edb1af103298efac50380c84ab2e248def1bf5bcf6c6769263f5a6aa97ed'
          and result['original_native_config_sha256'] ==
          'ec32867044bd6de4f8cead0cc6d9f73a45419c1a091dbe3cdbdfadaf669fe0f9',
          'context_readonly_original_configuration')
    native_row = actual['windows_bridge']['configuration']
    native_raw = _read(native_row['wsl_path'])
    _need(_digest(native_raw) == native_row['sha256']
          and _json(native_raw)['identity']['sid'] == documents['raw_stdout']['executor_sid'],
          'context_readonly_current_native_sid')
    evidence.append(({'path': native_row['wsl_path'], **_metadata(native_raw)}, native_raw))
    snapshot = documents['after_snapshot']
    baseline = _native_roots(root)
    for name in set(baseline) - set(snapshot['files']):
        if name.startswith(('native-bridge-', 'native-auth-refresh-')):
            match = re.fullmatch(r'(native-bridge-[0-9a-f]{64}|native-auth-refresh-[0-9a-f]{24})(\.claim\.json|-journal\.json)', name)
            _need(match is not None and match[1] + '.claim.json' in baseline
                  and match[1] + '-journal.json' in baseline, 'context_readonly_new_root_pair')
    _need(all(_metadata(baseline.get(name, b'')) == value for name, value in snapshot['files'].items()
              if '/' not in name and name.startswith(NATIVE_PREFIXES)), 'context_readonly_snapshot_roots_changed')
    events = _readonly_events(root)
    _need({name: _metadata(raw) for name, raw in events.items()} == snapshot['edd_event_inventory'],
          'context_readonly_snapshot_events_changed')
    _readonly_history(baseline[prefix + '.claim.json'], baseline[prefix + '-journal.json'], events)
    refresh_events = {}
    for name, value in snapshot['refresh_inventory'].items():
        raw = _read(root / name)
        _need(_metadata(raw) == value, 'context_readonly_snapshot_refresh_changed')
        if '/' in name:
            refresh_events[name] = raw
    pair = {key: {'path': str(root / name), **_metadata(baseline[name])}
            for key, name in (('claim', prefix + '.claim.json'), ('journal', prefix + '-journal.json'))}
    _need(pending_claims.count(pair) == 1, 'context_readonly_pending_pair')
    guard = _readonly_guard(c, root, baseline, events, refresh_events, evidence)
    guard()
    return pair, names, guard


def validate_context(c, current_config, pending_claims, *, current_boot_descriptor=None, now_epoch=None):
    """Return exact historical coverage; never admit a runtime or execute work.

    The production caller first admits the current release through its existing
    contract/configuration/source gates and supplies its actual path/hash descriptor.
    A two-field historical identity is used only by the pure f5 validator; it is
    never provided to configured(), any runtime loader, or the live observer.
    """
    try:
        root = _path(c['STATE'])
        callback = c.get('configuration_descriptor')
        _need(callable(callback), 'context_actual_configuration_descriptor_required')
        actual_row = callback()
        actual_raw = _verified(actual_row)
        _need(actual_row['sha256'] == current_config.document_sha256
              and str(current_config.state_root) == str(root), 'context_actual_configuration_binding')
        actual = _json(actual_raw)
        _need(actual.get('state_root') == str(root), 'context_actual_state_root')
        pins = _pins()
        eligibility_row, eligibility_raw = _eligibility(root)
        chain = [(actual_row, actual_raw), (eligibility_row, eligibility_raw)]
        def document(row):
            raw = _verified(row)
            chain.append((row, raw))
            return _json(raw)
        eligibility = _json(eligibility_raw)
        reservation = document(eligibility['reservation'])
        capability = reservation['capability']
        _need(type(capability) is dict, 'context_capability_schema')
        preparation = document(capability['preparation'])
        review = document(preparation['review'])
        core_path, core_raw = _sources(review, pins)
        binding = document(capability['binding_review'])
        original_row = binding['local_configuration_template']
        original = document(original_row)
        _repository_context(actual, original, current_config)
        _shared_context(actual, original, current_config)
        # This is the first execution of historical code, after all fixed pins.
        historical = types.ModuleType('reviewed_f5_context_' + pins['recovery_epoch.py']['sha256'])
        historical.__file__ = str(core_path)
        exec(compile(core_raw, str(core_path), 'exec', dont_inherit=True), historical.__dict__)
        original_helper = historical._reviewed_module
        def pinned_helper(row, role):
            # The unchanged core rereads helper descriptors. Guard each actual
            # helper load as well, so a concurrent, self-consistent replacement
            # of review/sibling files cannot execute new code before rechecks.
            name = {'boot': 'recovery_boot_probe.py', 'protocol': 'protocol.py'}.get(role)
            _need(name is not None, 'context_historical_helper_role')
            _need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'},
                  'context_descriptor_schema')
            _need({'bytes': row['bytes'], 'sha256': row['sha256']} == pins[name],
                  'context_source_not_pinned_f5')
            return original_helper(row, role)
        historical._reviewed_module = pinned_helper
        publication_view = None
        manifest_callback = c.get('publication_manifest_descriptor')
        if callable(manifest_callback):
            manifest_row = manifest_callback()
            _need(manifest_row['sha256'] == actual['publication_manifest_sha256'],
                  'context_actual_publication_manifest')
            state_module = _current_helper('publication_state.py', PUBLICATION_STATE_SHA256)
            publication_view = state_module.capture(root, manifest_row, actual['versions'], historical,
                publication_root=getattr(current_config, 'publication_state_root', None),
                publication_history=actual.get('publication', {}).get('history', ()))
            historical._root_records = publication_view.root_records
        # A strictly source-proven rejection before worker creation is not a
        # native Job-zero receipt. Keep its UNKNOWN journal byte-identical and
        # interpret it separately from the old reboot disposition. The complete
        # live roots/events remain checked; only the frozen validator's view
        # omits these independently classified pairs.
        root_reader = historical._root_records
        roots = root_reader(root)
        preworker = ()
        event_files = None
        if any(name.endswith('-journal.json') and
               _json(raw).get('failure_diagnostics', {}).get('supervisor_reason')
               == 'supervisor_lease_failed' for name, raw in roots.items()):
            event_files = _events(root)
            classifier = _current_helper('preworker_disposition.py', PREWORKER_SOURCE_SHA256)
            def verified_evidence(row):
                raw = _verified(row)
                chain.append((row, raw))
                return raw
            preworker = classifier.classify({**roots, **event_files}, state_root=str(root),
                native_configuration=binding['native_configuration_template'],
                diagnostic_sources=review['recovery_sources'],
                source_manifest=_read(_path(Path(__file__).absolute()).with_name('context-source-pins.json')),
                verified=verified_evidence)
            excluded = {name for item in preworker for name in item['excluded_root_names']}
            _need(type(pending_claims) is list, 'context_pending_claims_schema')
            classified = []
            for item in preworker:
                pair = {'claim': dict(item['claim']), 'journal': dict(item['journal'])}
                _need(pending_claims.count(pair) == 1, 'context_preworker_pending_pair')
                classified.append(pair)
            def historical_roots(path):
                complete = root_reader(path)
                _need(complete == roots and _events(root) == event_files,
                      'context_preworker_evidence_changed')
                return {name: raw for name, raw in complete.items() if name not in excluded}
            historical._root_records = historical_roots
            pending_claims = [row for row in pending_claims if row not in classified]
        readonly = _classify_readonly(c, root, roots, pending_claims, actual)
        if readonly is not None:
            pair, readonly_names, readonly_guard = readonly
            prior_reader = historical._root_records
            def without_readonly(path):
                readonly_guard()
                return {name: raw for name, raw in prior_reader(path).items() if name not in readonly_names}
            historical._root_records = without_readonly
            pending_claims = [item for item in pending_claims if item != pair]
        identity = types.SimpleNamespace(state_root=root, document_sha256=original_row['sha256'])
        # Recompute the sealed historical disposition at its actual completion,
        # using its authentic after-Restart observation. These are historical
        # inputs, not substitutes for the live observer below. The unchanged f5
        # code still validates the full Restart/request/source/receipt chain,
        # seal and exact original UNKNOWN, and rejects every later unresolved
        # native session/refresh in the current STATE projection.
        # This narrow adapter supports the existing sealed f5 history, whose
        # authentic after-observation precedes completion by 12.629 seconds.
        # The unchanged historical freshness check remains: a different history
        # taking longer than its 120-second limit is rejected, not normalized.
        historical_snapshot = historical._root_records(root)
        result = historical.validate_eligibility({'STATE': root}, identity, pending_claims,
            current_boot_descriptor=capability['after_boot'],
            now_epoch=eligibility['completed_epoch'])
        # Root snapshots alone cannot detect in-place edits of sealed event
        # bodies. Recheck just the two already-validated bounded inventories
        # around the live observer, without scanning unrelated later events.
        original_rows = historical._inventory(document(preparation['inventory']), root)
        seal = _json(historical_snapshot[historical._prefix(preparation) + '-sealed.claim.json'])
        completed_rows = historical._inventory({'format': 'irisx/recovery-inventory-v1',
            'state_root': str(root), 'files': seal['files']}, root)
        for rows in (original_rows, completed_rows):
            for name, row in rows.items():
                descriptor = {**row, 'path': str(root / name)}
                chain.append((descriptor, _verified(descriptor)))
        after = document(capability['after_boot'])
        if current_boot_descriptor is None:
            observer = c.get('recovery_boot_observation')
            _need(callable(observer), 'context_fresh_boot_observer_required')
            current_boot_descriptor = observer(review, preparation['challenge'])
        current = document(current_boot_descriptor)
        observed, _ = historical._observation(current, preparation['challenge'], review)
        if now_epoch is None:
            now_epoch = time.time()
        # A sealed, successful full Restart is an irreversible historical
        # process-termination boundary under the existing trusted-host/no-
        # rollback model. It does not need a permanent same-boot assertion.
        # Keep fresh native identity, reviewed source/runtime, observer closure
        # and current-state checks; no tolerance is added to boot timestamps.
        _need(historical._number(now_epoch) and now_epoch >= eligibility['completed_epoch']
              and abs(observed - now_epoch) <= historical.BOOT_SKEW_SECONDS
              and all(current[key] == after[key] for key in (
                  'host_install_sha256', 'windows_version', 'windows_build',
                  'source_sha256', 'runtime_sha256')),
              'context_live_observation_changed_or_stale')
        _need(historical._root_records(root) == historical_snapshot,
              'context_live_state_changed')
        # An observer cannot replace source/configuration/chain files unnoticed.
        for row, raw in chain:
            _need(_verified(row) == raw, 'context_chain_changed')
        _need(_pins() == pins, 'context_source_manifest_changed')
        _sources(review, pins)
        _need(actual_row['sha256'] == current_config.document_sha256
              and str(current_config.state_root) == str(root), 'context_actual_configuration_binding')
        _repository_context(actual, original, current_config)
        _shared_context(actual, original, current_config)
        if publication_view is not None:
            publication_view.verify_unchanged()
            _need(_digest(_read(Path(__file__).absolute().with_name('publication_state.py')))
                  == PUBLICATION_STATE_SHA256, 'context_current_helper_source_pin')
        if event_files is not None:
            _need(_events(root) == event_files and root_reader(root) == roots,
                  'context_preworker_evidence_changed')
            _need(_digest(_read(Path(__file__).absolute().with_name('preworker_disposition.py')))
                  == PREWORKER_SOURCE_SHA256, 'context_current_helper_source_pin')
            result.update({item['session']: item['claim_sha256'] for item in preworker})
        if readonly is not None:
            readonly_guard()
            receiver = c.get('receive_readonly_frontier_guard')
            _need(callable(receiver), 'context_readonly_guard_receiver_required')
            receiver(readonly_guard)
        return result
    except (KeyError, TypeError, AttributeError, RecursionError):
        raise ContextError('context_invalid_chain_or_configuration') from None

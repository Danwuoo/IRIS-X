"""Offline, same-boot interpretation of one completed f5 recovery disposition.

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
unchanged historical validator alone decides which original UNKNOWN is covered
by the completed recovery. A pre-worker disposition never borrows that coverage.
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
        identity = types.SimpleNamespace(state_root=root, document_sha256=original_row['sha256'])
        callbacks = {'STATE': root}
        observer = c.get('recovery_boot_observation')
        if callable(observer):
            callbacks['recovery_boot_observation'] = observer
        result = historical.validate_eligibility(callbacks, identity, pending_claims,
            current_boot_descriptor=current_boot_descriptor, now_epoch=now_epoch)
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
        return result
    except (KeyError, TypeError, AttributeError, RecursionError):
        raise ContextError('context_invalid_chain_or_configuration') from None

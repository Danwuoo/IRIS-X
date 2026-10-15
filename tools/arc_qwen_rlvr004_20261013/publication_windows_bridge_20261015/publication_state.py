"""Read-only projection of current publication additions around frozen f5 history.

Only names written by rl_transport (and read by rl_collect) are projected out.
This is a namespace/integrity boundary, never publication, runtime, or scientific
admission. Existing publication/collection gates still inspect the real files.
The caller must source-pin this module and independently admit the manifest.
No source, STATE byte, process, credential, or external state is changed here.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
import zipfile

DOC_CAP = 4 * 1024**2
WIRE_CAP = 8 * 1024**2
ARCHIVE_CAP = 64 * 1024**2
PAYLOAD_CAP = 128 * 1024**2
TREE_CAP = 256 * 1024**2
COUNT_CAP = 4096
ROOT_CAP = 512
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
REF = 'danielwuu/iris-x-learning-agent-20261011'
JIT_NAMES = frozenset(('active-finalized.ipynb', 'original-request.json',
                       'operator.json', 'parent-private-scorer.json'))
HISTORY_PREFIXES = ('native-bridge-', 'native-auth-refresh-', 'recovery-epoch-')


class PublicationStateError(ValueError):
    """Fixed, non-secret fail-closed diagnostic."""


def _need(value, code):
    if not value:
        raise PublicationStateError(code)


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def _path(value):
    _need(type(value) is str or isinstance(value, Path), 'publication_state_path_type')
    text = str(value)
    path = Path(text)
    _need(path.is_absolute() and str(path) == text and '..' not in path.parts
          and not text.startswith('//') and len(text) <= 4096
          and not any(ord(ch) < 32 for ch in text), 'publication_state_absolute_path')
    return path


def _relative(value):
    _need(type(value) is str and 0 < len(value) <= 4096
          and not value.startswith('/') and '\\' not in value and ':' not in value,
          'publication_state_relative_path')
    parts = value.split('/')
    _need(len(parts) <= 32 and all(re.fullmatch('[A-Za-z0-9_][A-Za-z0-9_.-]{0,239}', part)
          and '..' not in part and part not in ('.', '..') for part in parts),
          'publication_state_relative_path')
    return value


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def _directory(path):
    descriptors, ancestors = [], []
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        descriptors.append(fd)
        for component in _path(path).parts[1:]:
            before = os.stat(component, dir_fd=fd, follow_symlinks=False)
            _need(stat.S_ISDIR(before.st_mode), 'publication_state_directory_type')
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                            | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=fd)
            descriptors.append(child)
            opened = os.fstat(child)
            _need((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                  'publication_state_directory_race')
            ancestors.append((fd, component, before.st_dev, before.st_ino))
            fd = child
        yield fd
        for parent, name, device, inode in ancestors:
            after = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _need(stat.S_ISDIR(after.st_mode) and (after.st_dev, after.st_ino) == (device, inode),
                  'publication_state_directory_replaced')
    except OSError:
        raise PublicationStateError('publication_state_file_unavailable') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _read_at(directory, name, cap, *, keep=True, empty=False):
    before = os.stat(name, dir_fd=directory, follow_symlinks=False)
    _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
          and (0 if empty else 1) <= before.st_size <= cap,
          'publication_state_bounded_single_link_file')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                 dir_fd=directory)
    chunks, digest, total = [], hashlib.sha256(), 0
    with os.fdopen(fd, 'rb') as stream:
        _need(_identity(os.fstat(fd)) == _identity(before), 'publication_state_file_open_race')
        while True:
            block = stream.read(min(65536, cap + 1 - total))
            if not block:
                break
            total += len(block)
            _need(total <= cap, 'publication_state_file_cap')
            digest.update(block)
            if keep:
                chunks.append(block)
        after = os.stat(name, dir_fd=directory, follow_symlinks=False)
        _need(total == before.st_size and _identity(os.fstat(fd)) == _identity(before) == _identity(after),
              'publication_state_file_read_race')
    return (b''.join(chunks) if keep else None,
            (total, digest.hexdigest(), _identity(before)))


def _read(path, cap=DOC_CAP):
    path = _path(path)
    with _directory(path.parent) as fd:
        return _read_at(fd, path.name, cap)


def _json(raw, cap=DOC_CAP):
    _need(type(raw) is bytes and 0 < len(raw) <= cap, 'publication_state_json_cap')
    def pairs(items):
        value = {}
        for key, item in items:
            _need(key not in value, 'publication_state_duplicate_json_key')
            value[key] = item
        return value
    def integer(value):
        _need(len(value) <= 24, 'publication_state_integer_bound')
        return int(value)
    def number(value):
        result = float(value)
        _need(math.isfinite(result), 'publication_state_nonfinite_json')
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
                           parse_float=number, parse_constant=lambda _: _need(False, 'publication_state_nonfinite_json'))
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, PublicationStateError):
            raise
        raise PublicationStateError('publication_state_invalid_json') from None
    stack, count = [(value, 0)], 0
    while stack:
        node, depth = stack.pop()
        count += 1
        _need(count <= 100000 and depth <= 32, 'publication_state_json_complexity')
        if type(node) is dict:
            _need(all(type(key) is str and len(key) <= 4096 for key in node), 'publication_state_json_key')
            stack.extend((item, depth + 1) for item in node.values())
        elif type(node) is list:
            stack.extend((item, depth + 1) for item in node)
        elif type(node) is str:
            _need(len(node) <= DOC_CAP, 'publication_state_string_bound')
    _need(type(value) is dict, 'publication_state_json_object')
    return value


def _descriptor(row, cap=DOC_CAP):
    _need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}
          and type(row['bytes']) is int and 0 < row['bytes'] <= cap and _sha(row['sha256']),
          'publication_state_descriptor_schema')
    raw, identity = _read(row['path'], cap)
    _need(identity[:2] == (row['bytes'], row['sha256']), 'publication_state_descriptor_changed')
    return raw, identity


def _manifest(descriptor, versions):
    raw, identity = _descriptor(descriptor)
    document = _json(raw)
    versions = dict(versions)
    _need(set(versions) == {'code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'}
          and all(type(value) is int and 0 < value <= 2**31 - 1 for value in versions.values()),
          'publication_state_versions')
    _need(versions['code'] == versions['code_predecessor'] + 1
          and versions['inactive'] == versions['inactive_predecessor'] + 1
          and versions['active'] == versions['inactive'] + 1, 'publication_state_successor_versions')
    _need(document.get('format') == 'irisx/qwen14b-rlvr-run008-publication-contract-v1',
          'publication_state_manifest_format')
    dataset = document['datasets']
    _need(type(dataset) is list and len(dataset) == 1 and type(dataset[0]) is dict,
          'publication_state_manifest_dataset')
    dataset = dataset[0]
    _need(dataset['reference'] == DREF and type(dataset['id']) is int and dataset['id'] == 12504696,
          'publication_state_manifest_dataset')
    for field, key in (('expected_version', 'code'), ('expected_predecessor_version', 'code_predecessor')):
        _need(type(dataset[field]) is int and dataset[field] == versions[key], 'publication_state_manifest_versions')
    notebooks = document['notebooks']
    _need(type(notebooks) is list and len(notebooks) == 2 and all(type(row) is dict for row in notebooks),
          'publication_state_manifest_notebooks')
    notebooks = {row['role']: row for row in notebooks}
    _need(set(notebooks) == {'inactive', 'rlvr004'}, 'publication_state_manifest_notebooks')
    for role, previous, current in (('inactive', 'inactive_predecessor', 'inactive'), ('rlvr004', 'inactive', 'active')):
        row = notebooks[role]
        _need(type(row['existing_notebook_id']) is int and row['existing_notebook_id'] == 138123872
              and row['existing_notebook_reference'] == REF, 'publication_state_manifest_notebooks')
        for field, key in (('expected_version', current), ('expected_predecessor_version', previous)):
            _need(type(row[field]) is int and row[field] == versions[key], 'publication_state_manifest_versions')
    _need(type(document['jit']['output_documents']) is list
          and len(document['jit']['output_documents']) == len(JIT_NAMES)
          and set(document['jit']['output_documents']) == JIT_NAMES, 'publication_state_jit_names')
    layouts = dataset['expected_readback_layouts']
    _need(type(layouts) is dict and 0 < len(layouts) <= 4, 'publication_state_layouts')
    parsed = {}
    for name, rows in layouts.items():
        _need(type(name) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}', name)
              and type(rows) is list and 0 < len(rows) <= 3000, 'publication_state_layouts')
        inventory, aliases = {}, set()
        for row in rows:
            _need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'publication_state_layout_row')
            path = _relative(row['path'])
            _need(path not in inventory and path.casefold() not in aliases and _sha(row['sha256'])
                  and type(row['bytes']) is int and 0 <= row['bytes'] <= (ARCHIVE_CAP if path == 'source.zip' else 16 * 1024**2),
                  'publication_state_layout_row')
            inventory[path] = (row['bytes'], row['sha256'])
            aliases.add(path.casefold())
        _need(sum(value[0] for value in inventory.values()) <= PAYLOAD_CAP,
              'publication_state_layout_bytes')
        _need(not any('/'.join(path.split('/')[:i]) in inventory for path in inventory
                      for i in range(1, len(path.split('/')))), 'publication_state_layout_file_directory_alias')
        parsed[name] = inventory
    return document, versions, parsed, identity


def _zip_inventory(raw):
    result, names, directories, total = {}, set(), set(), 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            _need(len(archive.infolist()) <= 3000, 'publication_state_archive_count')
            for info in archive.infolist():
                name = info.filename[:-1] if info.is_dir() else info.filename
                _relative(name)
                _need(name.casefold() not in names, 'publication_state_archive_duplicate')
                names.add(name.casefold())
                mode = info.external_attr >> 16
                _need(not info.flag_bits & 1 and not stat.S_ISLNK(mode)
                      and (not stat.S_IFMT(mode) or stat.S_ISREG(mode)
                           or info.is_dir() and stat.S_ISDIR(mode)), 'publication_state_archive_special')
                if info.is_dir():
                    directories.add(name)
                    continue
                cap = ARCHIVE_CAP if name == 'source.zip' else 16 * 1024**2
                _need(0 <= info.file_size <= cap, 'publication_state_archive_member_cap')
                total += info.file_size
                _need(total <= PAYLOAD_CAP, 'publication_state_archive_bytes')
                digest, size = hashlib.sha256(), 0
                with archive.open(info) as stream:
                    for block in iter(lambda: stream.read(65536), b''):
                        size += len(block)
                        _need(size <= info.file_size, 'publication_state_archive_stream_cap')
                        digest.update(block)
                _need(size == info.file_size, 'publication_state_archive_size')
                result[name] = (size, digest.hexdigest())
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError):
        raise PublicationStateError('publication_state_invalid_archive') from None
    _need(all(any(path.startswith(name + '/') for path in result) for name in directories),
          'publication_state_archive_extra_directory')
    _need(not any('/'.join(path.split('/')[:i]) in result for path in result
                  for i in range(1, len(path.split('/')))), 'publication_state_archive_path_alias')
    return result


def _publication_names(versions):
    code = 'dataset-code-v' + str(versions['code'])
    names = {code + suffix for suffix in ('.claim.json', '-journal.json', '-receipt.json')}
    for role in ('inactive', 'rlvr004'):
        names.update('notebook-' + role + suffix for suffix in
                     ('.claim.json', '-journal.json', '-receipt.json', '-wire.json', '-saved.ipynb'))
    names.update(JIT_NAMES | {'finalization.json', 'active-readback.claim.json'})
    names.update('historical-code-v' + str(number) + '-inventory.json'
                 for number in range(8, max(7, versions['code_predecessor'] - 9) + 1))
    return names


def _publication_records(files, root, descriptor, versions, manifest):
    """Bind additions to this candidate; leave all action decisions to transport."""
    digest = descriptor['sha256']
    parsed = {name: _json(raw, WIRE_CAP if name.endswith('-wire.json') else DOC_CAP)
              for name, raw in files.items()}
    def manifest_bound(value):
        _need(value.get('manifest_sha256') == digest, 'publication_state_foreign_manifest')
    def number(value, key, expected):
        _need(type(value.get(key)) is int and value[key] == expected, 'publication_state_record_version')
    for name, value in parsed.items():
        if name.startswith('historical-code-v'):
            version = int(name.split('-v')[1].split('-')[0])
            _need(set(value) == {'dataset_id', 'numeric_version', 'captured_while_current_version',
                               'inventory_sha256', 'files_inventory', 'payload_bytes_rehashed'},
                  'publication_state_historical_inventory_schema')
            number(value, 'dataset_id', 12504696)
            number(value, 'numeric_version', version)
            number(value, 'captured_while_current_version', versions['code_predecessor'])
            inventory = value['files_inventory']
            _need(type(inventory) is dict and 0 < len(inventory) <= 12000
                  and value['payload_bytes_rehashed'] is False, 'publication_state_historical_inventory')
            for path, size in inventory.items():
                _relative(path)
                _need(type(size) is int and 0 <= size <= 2**63 - 1, 'publication_state_historical_inventory')
            _need(value['inventory_sha256'] == _digest(_canonical(inventory)), 'publication_state_historical_inventory_hash')
        elif name.startswith('dataset-code-'):
            manifest_bound(value)
            if name.endswith('-receipt.json'):
                number(value, 'version', versions['code'])
                number(value, 'dataset_id', 12504696)
                _need(value.get('publication_manifest_sha256') == digest, 'publication_state_foreign_manifest')
            else:
                number(value, 'expected_version', versions['code'])
                number(value, 'expected_predecessor_version', versions['code_predecessor'])
        elif name.startswith('notebook-') and not name.endswith(('-wire.json', '-saved.ipynb')):
            manifest_bound(value)
            role = 'inactive' if name.startswith('notebook-inactive-') or name.startswith('notebook-inactive.') else 'rlvr004'
            number(value, 'version' if name.endswith('-receipt.json') else 'expected_version',
                   versions['inactive' if role == 'inactive' else 'active'])
            number(value, 'kernel_id', 138123872)
            _need(value.get('reference') == REF and value.get('role') == role, 'publication_state_notebook_identity')
        elif name == 'active-readback.claim.json':
            manifest_bound(value)
            number(value, 'numeric_notebook_version', versions['active'])
            _need(set(value) == {'manifest_sha256', 'numeric_notebook_version', 'launch_claim_sha256', 'action'}
                  and value['action'] == 'initial_post_submit_readback', 'publication_state_active_readback')
            claim = files.get('notebook-rlvr004.claim.json')
            _need(claim is not None and value['launch_claim_sha256'] == _digest(claim), 'publication_state_claim_binding')
        elif name == 'finalization.json':
            manifest_bound(value)
            _need(value.get('format') == 'irisx/rlvr-finalization-v1'
                  and type(value.get('documents')) is dict and set(value['documents']) == JIT_NAMES,
                  'publication_state_finalization_schema')
            for item, row in value['documents'].items():
                _need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}
                      and row['path'] == str(root / item) and type(row['bytes']) is int
                      and item in files and (row['bytes'], row['sha256']) == (len(files[item]), _digest(files[item])),
                      'publication_state_finalization_documents')
        elif name == 'parent-private-scorer.json':
            # Exact descriptor-only schema. Never inspect or include evaluator bodies.
            _need(set(value) == {'format', 'scope', 'role', 'owner_id', 'original_request_id',
                  'original_request_sha256', 'raw_source_sha256', 'evaluator_root',
                  'evaluator_manifest_sha256', 'scorer_pins_sha256'}
                  and value['format'] == 'owned-rl-parent-scorer-material-v1'
                  and all(_sha(value[key]) for key in ('original_request_sha256', 'raw_source_sha256',
                      'evaluator_manifest_sha256', 'scorer_pins_sha256')),
                  'publication_state_parent_metadata_only')
    # Partial claims and readbacks remain possible. If a linked record exists,
    # however, it cannot claim a different reservation or future numeric version.
    for name, value in parsed.items():
        if name.endswith('-journal.json') or name.endswith('-receipt.json'):
            stem = name.rsplit('-', 1)[0]
            claim = files.get(stem + '.claim.json')
            if name.endswith('-journal.json') or stem.startswith('dataset-code-'):
                _need(claim is not None and value.get('claim_sha256') == _digest(claim), 'publication_state_claim_binding')
            if name.endswith('-receipt.json'):
                journal = files.get(stem + '-journal.json')
                key = 'journal_sha256' if stem.startswith('dataset-code-') else 'launch_journal_sha256'
                _need(journal is not None and value.get(key) == _digest(journal), 'publication_state_journal_binding')
        if name.endswith('-wire.json'):
            stem = name[:-len('-wire.json')]
            _need(stem + '.claim.json' in parsed and value.get('id') == 138123872
                  and type(value.get('id')) is int and value.get('slug') == REF
                  and type(value.get('text')) is str and 0 < len(value['text'].encode()) <= 1024**2,
                  'publication_state_wire_binding')
            expected_sources = next(row['dataset_sources'] for row in manifest['notebooks']
                                    if row['role'] == ('inactive' if stem.endswith('inactive') else 'rlvr004'))
            _need(value.get('dataset_data_sources') == expected_sources, 'publication_state_wire_code_pin')
        if name.endswith('-saved.ipynb'):
            stem = name[:-len('-saved.ipynb')]
            _need(stem + '.claim.json' in parsed, 'publication_state_saved_claim')
        if name in JIT_NAMES:
            _need('notebook-rlvr004.claim.json' in parsed, 'publication_state_jit_claim')
    return parsed


def _snapshot(root, descriptor, versions, historical, frontier):
    manifest, versions, layouts, manifest_identity = _manifest(descriptor, versions)
    root = _path(root)
    _need(not _path(descriptor['path']).is_relative_to(root), 'publication_state_manifest_inside_state')
    allowed = _publication_names(versions)
    readback = 'code-v' + str(versions['code']) + '-readback'
    fingerprint, roots, publication, seen, total = {}, {}, {}, set(), 0
    baseline = {} if frontier is None else frontier['files']
    if frontier is not None:
        _need(type(frontier) is dict and set(frontier) == {'root', 'files'}
              and frontier['root'] == str(root) and type(baseline) is dict
              and 0 < len(baseline) <= historical.FILE_COUNT_CAP, 'publication_state_frontier_schema')
    def add(name, record):
        nonlocal total
        device_inode = record[2][:2]
        _need(device_inode not in seen, 'publication_state_inode_alias')
        seen.add(device_inode)
        fingerprint[name] = record
        total += record[0]
        _need(len(fingerprint) <= COUNT_CAP and total <= TREE_CAP, 'publication_state_tree_bound')
    def payload_tree(directory, prefix, possible):
        before = os.fstat(directory)
        names = sorted(os.listdir(directory))
        _need(len(names) <= COUNT_CAP, 'publication_state_tree_count')
        actual = {}
        for name in names:
            path = _relative(prefix + name)
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                _need(any(item.startswith(path + '/') for item in possible), 'publication_state_extra_payload_directory')
                add(readback + '/payload/' + path + '/', (0, None, _identity(info)))
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
                try:
                    _need(_identity(os.fstat(fd)) == _identity(info), 'publication_state_directory_race')
                    actual.update(payload_tree(fd, path + '/', possible))
                    _need(_identity(os.stat(name, dir_fd=directory, follow_symlinks=False)) == _identity(info),
                          'publication_state_directory_replaced')
                finally:
                    os.close(fd)
            else:
                _need(path in possible, 'publication_state_extra_payload_file')
                _, record = _read_at(directory, name, max(value[0] for value in possible[path]), keep=False, empty=True)
                _need(record[:2] in possible[path], 'publication_state_payload_changed')
                add(readback + '/payload/' + path, record)
                actual[path] = record[:2]
        _need(names == sorted(os.listdir(directory)) and _identity(before) == _identity(os.fstat(directory)),
              'publication_state_directory_race')
        return actual
    with _directory(root) as directory:
        before = os.fstat(directory)
        add('/', (0, None, _identity(before)))
        names = sorted(os.listdir(directory))
        _need(len(names) <= ROOT_CAP, 'publication_state_root_count')
        _need(len({name.casefold() for name in names}) == len(names), 'publication_state_name_alias')
        for name in names:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if name == 'events':
                _need(stat.S_ISDIR(info.st_mode), 'publication_state_events_directory_type')
                add('events/', (0, None, _identity(info)))
                continue
            if name == readback:
                _need(stat.S_ISDIR(info.st_mode), 'publication_state_readback_directory_type')
                add(name + '/', (0, None, _identity(info)))
                with _directory(root / name) as rd:
                    children = sorted(os.listdir(rd))
                    _need(set(children) <= {'payload', 'provider.zip', 'archive-download.json'},
                          'publication_state_unexpected_readback_entry')
                    possible = {}
                    for inventory in layouts.values():
                        for path, value in inventory.items():
                            possible.setdefault(path, set()).add(value)
                    actual = {}
                    if 'payload' in children:
                        with _directory(root / name / 'payload') as pd:
                            add(name + '/payload/', (0, None, _identity(os.fstat(pd))))
                            actual = payload_tree(pd, '', possible)
                    matching = [inventory for inventory in layouts.values()
                                if all(inventory.get(path) == value for path, value in actual.items())]
                    _need(bool(matching), 'publication_state_mixed_payload_layout')
                    archive_record = None
                    if 'provider.zip' in children:
                        archive_raw, archive_record = _read_at(rd, 'provider.zip', ARCHIVE_CAP)
                        add(name + '/provider.zip', archive_record)
                        inventory = _zip_inventory(archive_raw)
                        _need(inventory in matching, 'publication_state_archive_layout')
                    if 'archive-download.json' in children:
                        raw, record = _read_at(rd, 'archive-download.json', DOC_CAP)
                        add(name + '/archive-download.json', record)
                        row = _json(raw)
                        _need(archive_record is not None and set(row) == {'path', 'bytes', 'sha256'}
                              and row['path'] == str(root / name / 'provider.zip')
                              and type(row['bytes']) is int and (row['bytes'], row['sha256']) == archive_record[:2],
                              'publication_state_archive_descriptor')
                    _need(children == sorted(os.listdir(rd)) and _identity(info) == _identity(os.fstat(rd)),
                          'publication_state_readback_race')
                continue
            _relative(name)
            raw, record = _read_at(directory, name, WIRE_CAP if name.endswith('-wire.json') else DOC_CAP)
            add(name, record)
            if name in allowed:
                publication[name] = raw
            else:
                # Do not classify native/refresh/recovery records by their contents.
                # Even malformed or new names must reach the unchanged f5 parser.
                historical._relative(name)
                historical.strict_json(raw)
                _need(name in baseline or name.startswith(HISTORY_PREFIXES), 'publication_state_unexpected_root')
                roots[name] = raw
        _need(sum(len(raw) for raw in roots.values()) <= historical.TREE_CAP,
              'publication_state_historical_root_bytes')
        parsed = _publication_records(publication, root, descriptor, versions, manifest)
        code_stem = 'dataset-code-v' + str(versions['code'])
        if readback in names:
            _need(code_stem + '.claim.json' in parsed and code_stem + '-journal.json' in parsed,
                  'publication_state_readback_claim_required')
        for name, row in baseline.items():
            historical._relative(name)
            _need(type(row) is dict and set(row) == {'bytes', 'sha256'}
                  and type(row['bytes']) is int and 0 < row['bytes'] <= historical.FILE_CAP
                  and _sha(row['sha256']), 'publication_state_frontier_row')
            _need(name not in publication, 'publication_state_frontier_publication_overlap')
            if name.startswith('events/'):
                raw, record = _read(root / name, historical.FILE_CAP)
                add(name, record)
            else:
                _need(name in roots, 'publication_state_frontier_missing')
                record = fingerprint[name]
            _need(record[:2] == (row['bytes'], row['sha256']), 'publication_state_frontier_changed')
        _need(names == sorted(os.listdir(directory)) and _identity(before) == _identity(os.fstat(directory)),
              'publication_state_root_race')
    return roots, fingerprint, manifest_identity


class Snapshot:
    """Immutable recorded bytes, with full live rechecks on every f5 callback."""
    __slots__ = ('_root', '_descriptor', '_versions', '_historical', '_frontier', '_records', '_fingerprint', '_manifest_identity')

    def __init__(self, root, descriptor, versions, historical, frontier):
        object.__setattr__(self, '_root', _path(root))
        object.__setattr__(self, '_descriptor', _json(_canonical(descriptor)))
        object.__setattr__(self, '_versions', dict(versions))
        object.__setattr__(self, '_historical', historical)
        object.__setattr__(self, '_frontier', None if frontier is None else _json(_canonical(frontier)))
        roots, fingerprint, manifest_identity = _snapshot(self._root, self._descriptor, self._versions, historical, self._frontier)
        object.__setattr__(self, '_records', MappingProxyType(roots))
        object.__setattr__(self, '_fingerprint', MappingProxyType(fingerprint))
        object.__setattr__(self, '_manifest_identity', manifest_identity)

    def __setattr__(self, name, value):
        raise AttributeError('immutable publication state snapshot')

    def verify_unchanged(self):
        roots, fingerprint, manifest_identity = _snapshot(self._root, self._descriptor, self._versions, self._historical, self._frontier)
        _need(roots == self._records and fingerprint == self._fingerprint
              and manifest_identity == self._manifest_identity, 'publication_state_changed_during_observation')

    def root_records(self, root):
        _need(_path(root) == self._root, 'publication_state_wrong_root')
        self.verify_unchanged()
        return dict(self._records)


def capture(root, manifest_descriptor, versions, historical, *, frontier=None):
    """Capture real STATE without writes; install snapshot.root_records per module.

    frontier, when supplied, is the independently reviewed immutable baseline
    {root, files:{relative_path:{bytes,sha256}}}; new records never replace it.
    Empty or exact-hash subset readback payloads allow read-only reconciliation.
    Temporary/partial download debris is deliberately a fail-closed blocker.
    """
    try:
        return Snapshot(root, manifest_descriptor, versions, historical, frontier)
    except (KeyError, TypeError, AttributeError, RecursionError):
        raise PublicationStateError('publication_state_invalid_schema') from None

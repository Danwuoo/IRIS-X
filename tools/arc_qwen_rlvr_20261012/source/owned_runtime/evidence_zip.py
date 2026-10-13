"""Bounded local evidence ZIP64 and byte-bound terminal receipts.

This is an archive transport, not a model/evaluator authority. It never imports
archived code, opens tensor payloads as objects, or upgrades local hashes into
independent download verification. The original artifact inventory is unchanged.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import hashlib
import json
import math
import os
import shutil
import stat
import struct
import time
import zipfile
import zlib

from .evidence import (EVIDENCE_CAP_BYTES, CHECKPOINT_CAP_BYTES, MAX_MEMBERS,
                       MAX_JSON_MEMBER_BYTES, MAX_JOURNAL_BYTES, DISK_RESERVE_BYTES)
from .release import need, file_sha

OVERHEAD_BYTES = 16 * 1024**2
CHUNK_BYTES = 1024**2
METADATA_BYTES = 16 * 1024**2
TENSOR_NAMES = ('state.pt', 'adapter/adapter_model.safetensors')


def _regular(path):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'regular artifact ancestry required')
    need(stat.S_ISREG(path.stat().st_mode), 'regular artifact required')
    return path


def _name(value):
    need(type(value) is str and value and len(value.encode('utf-8')) <= 4096,
         'bounded member name required')
    need('\\' not in value and '\x00' not in value and
         not PurePosixPath(value).is_absolute() and
         all(p not in ('', '.', '..') for p in value.split('/')), 'unsafe ZIP member name')
    return value


def _sha_value(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _json(path):
    path = _regular(path)
    need(path.stat().st_size <= METADATA_BYTES, 'bounded export metadata required')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate export JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite export JSON constant')
    def number(value):
        parsed = float(value); need(math.isfinite(parsed), 'nonfinite export JSON number'); return parsed
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=nonfinite, parse_float=number)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('invalid bounded export JSON') from exc


def _deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('original absolute export deadline')


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _file_hash(path, deadline=None):
    path = _regular(path); before = _identity(path.stat()); hashed = hashlib.sha256()
    with path.open('rb') as stream:
        need(_identity(os.fstat(stream.fileno())) == before, 'artifact changed before hash')
        while True:
            _deadline(deadline)
            block = stream.read(CHUNK_BYTES)
            if not block: break
            hashed.update(block)
        need(_identity(os.fstat(stream.fileno())) == before == _identity(path.stat()),
             'artifact changed during hash')
    _deadline(deadline)
    return hashed.hexdigest()


def _read(stream, size):
    body = stream.read(size)
    need(len(body) == size, 'truncated ZIP structure')
    return body


def _extra(data):
    result = {}; offset = 0
    while offset < len(data):
        need(offset + 4 <= len(data), 'truncated ZIP extra header')
        tag, size = struct.unpack_from('<HH', data, offset); offset += 4
        need(offset + size <= len(data) and tag not in result, 'truncated/duplicate ZIP extra field')
        result[tag] = data[offset:offset + size]; offset += size
    # The exporter emits no platform/path override or encryption extra records.
    need(set(result) <= {1}, 'unsupported evidence ZIP extra field')
    return result.get(1, b'')


def _sizes(extra, fields):
    """Resolve ZIP64 sentinel fields in specification order, without guessing."""
    cursor = 0; result = []
    for value, width, sentinel in fields:
        if value == sentinel:
            need(cursor + width <= len(extra), 'missing ZIP64 sentinel value')
            value = int.from_bytes(extra[cursor:cursor + width], 'little'); cursor += width
        result.append(value)
    need(cursor == len(extra), 'unexpected ZIP64 extra values')
    return result


def _member_limit(name, checkpoint_archive_body=None):
    if name == 'checkpoints.zip' and checkpoint_archive_body is not None:
        return CHECKPOINT_CAP_BYTES
    if name == 'physical-journal.jsonl':
        return MAX_JOURNAL_BYTES
    return MAX_JSON_MEMBER_BYTES


def preflight_evidence_zip(path, *, checkpoint_archive_body=None, _deadline_at=None):
    """Validate bounded ZIP64 structures without allocating a ZipFile parser.

    Evidence archives are single-disk ZIP_STORED, seekable, regular members with
    no data descriptors. ZIP comments up to the actual uint16 ceiling are valid.
    Central and local records must agree and exactly partition the archive; no
    prepended stub, hidden record, overlapping body, or trailing bytes is allowed.
    """
    _deadline(_deadline_at)
    if checkpoint_archive_body is not None:
        need(type(checkpoint_archive_body) is dict and set(checkpoint_archive_body) == {'bytes', 'sha256'} and
             type(checkpoint_archive_body['bytes']) is int and 0 <= checkpoint_archive_body['bytes'] <= CHECKPOINT_CAP_BYTES and
             _sha_value(checkpoint_archive_body['sha256']), 'bounded original checkpoint archive row required')
    path = _regular(path); before = _identity(path.stat()); size = before[2]
    need(22 <= size <= EVIDENCE_CAP_BYTES + OVERHEAD_BYTES, 'evidence ZIP physical byte cap')
    with path.open('rb') as stream:
        need(_identity(os.fstat(stream.fileno())) == before, 'ZIP changed before preflight')
        tail_start = max(0, size - 65557)
        stream.seek(tail_start); tail = _read(stream, size - tail_start)
        candidates = []
        offset = 0
        while True:
            at = tail.find(b'PK\x05\x06', offset)
            if at < 0: break
            if at + 22 <= len(tail):
                comment = struct.unpack_from('<H', tail, at + 20)[0]
                if at + 22 + comment == len(tail): candidates.append(at)
            offset = at + 1
        need(len(candidates) == 1, 'one unambiguous bounded ZIP EOCD required')
        at = candidates[0]; end = tail_start + at
        _, disk, cd_disk, count_disk, count, cd_bytes, cd_offset, comment = struct.unpack(
            '<4s4H2LH', tail[at:at + 22])
        need(disk == cd_disk == 0, 'single-disk evidence ZIP required')
        central_end = end; has_zip64 = False
        if end >= 20:
            stream.seek(end - 20); locator = _read(stream, 20)
            if locator[:4] == b'PK\x06\x07':
                has_zip64 = True
                _, z_disk, z_offset, z_disks = struct.unpack('<4sLQL', locator)
                need(z_disk == 0 and z_disks == 1 and z_offset == end - 76,
                     'strict bounded ZIP64 locator offset')
                stream.seek(z_offset)
                row = struct.unpack('<4sQ2H2L4Q', _read(stream, 56))
                sig, length, made, version, disk64, cd_disk64, nd64, nt64, cb64, co64 = row
                need(sig == b'PK\x06\x06' and length == 44 and disk64 == cd_disk64 == 0 and
                     version == 45 and made >= 45, 'strict fixed ZIP64 end record')
                for old, actual, sentinel in ((count_disk, nd64, 65535), (count, nt64, 65535),
                                              (cd_bytes, cb64, 0xffffffff), (cd_offset, co64, 0xffffffff)):
                    need(old == sentinel or old == actual, 'ZIP64/classic directory values disagree')
                count_disk, count, cd_bytes, cd_offset = nd64, nt64, cb64, co64
                central_end = z_offset
        need(has_zip64 or (count_disk != 65535 and count != 65535 and
                          cd_bytes != 0xffffffff and cd_offset != 0xffffffff), 'ZIP64 sentinel without end record')
        need(count_disk == count and 0 < count <= MAX_MEMBERS, 'ZIP member cap before allocation')
        need(46 * count <= cd_bytes <= OVERHEAD_BYTES and cd_offset + cd_bytes == central_end,
             'ZIP central table bounds/offset before allocation')
        need(0 <= cd_offset < central_end, 'ZIP central table outside body')
        stream.seek(cd_offset); records = []; names = set(); total = 0
        for _ in range(count):
            _deadline(_deadline_at)
            need(stream.tell() + 46 <= central_end, 'central entry outside table')
            row = struct.unpack('<4s6H3L5H2L', _read(stream, 46))
            (sig, made, version, flags, method, tm, dt, crc, compressed, expanded,
             name_bytes, extra_bytes, comment_bytes, member_disk, internal, external, local_offset) = row
            need(sig == b'PK\x01\x02' and flags in (0, 0x800) and method == 0,
                 'stored unencrypted evidence central member required')
            need(version <= 45 and name_bytes > 0 and name_bytes <= 4096 and
                 stream.tell() + name_bytes + extra_bytes + comment_bytes <= central_end,
                 'bounded central member header')
            raw_name = _read(stream, name_bytes)
            try: name = _name(raw_name.decode('utf-8' if flags & 0x800 else 'cp437'))
            except UnicodeError as exc: raise ValueError('invalid ZIP name encoding') from exc
            need(name not in names, 'duplicate ZIP member name'); names.add(name)
            expanded, compressed, local_offset, member_disk = _sizes(_extra(_read(stream, extra_bytes)),
                ((expanded, 8, 0xffffffff), (compressed, 8, 0xffffffff),
                 (local_offset, 8, 0xffffffff), (member_disk, 4, 65535)))
            _read(stream, comment_bytes)
            mode = external >> 16
            need(member_disk == 0 and stat.S_IFMT(mode) in (0, stat.S_IFREG) and not external & 0x10,
                 'regular single-disk ZIP member required')
            need(compressed == expanded and expanded <= _member_limit(name, checkpoint_archive_body), 'ZIP member expansion cap')
            if name == 'checkpoints.zip' and checkpoint_archive_body is not None:
                need(expanded == checkpoint_archive_body['bytes'], 'diagnostic checkpoint ZIP original length differs')
            total += expanded
            need(total <= EVIDENCE_CAP_BYTES and local_offset < cd_offset, 'ZIP aggregate/member offset cap')
            records.append({'name': name, 'bytes': expanded, 'crc32': crc, 'header_offset': local_offset,
                            '_raw_name': raw_name, '_flags': flags, '_version': version})
        need(stream.tell() == central_end, 'central count/table length disagree')
        need(checkpoint_archive_body is None or 'checkpoints.zip' in names, 'declared diagnostic checkpoint body absent')
        next_offset = 0
        for record in sorted(records, key=lambda r: r['header_offset']):
            _deadline(_deadline_at)
            need(record['header_offset'] == next_offset, 'overlapping/gapped local ZIP records')
            stream.seek(next_offset)
            (sig, version, flags, method, tm, dt, crc, compressed, expanded,
             name_bytes, extra_bytes) = struct.unpack('<4s5H3L2H', _read(stream, 30))
            need(sig == b'PK\x03\x04' and flags == record['_flags'] and method == 0 and version == record['_version'],
                 'local/central ZIP header differs')
            need(name_bytes == len(record['_raw_name']) and stream.tell() + name_bytes + extra_bytes <= cd_offset,
                 'bounded local ZIP name/extra')
            need(_read(stream, name_bytes) == record['_raw_name'], 'local/central ZIP name differs')
            expanded, compressed = _sizes(_extra(_read(stream, extra_bytes)),
                ((expanded, 8, 0xffffffff), (compressed, 8, 0xffffffff)))
            need(expanded == compressed == record['bytes'] and crc == record['crc32'],
                 'local/central ZIP size/CRC differs')
            record['data_offset'] = stream.tell(); next_offset = stream.tell() + expanded
            need(next_offset <= cd_offset, 'local ZIP body overlaps central directory')
            for key in ('_raw_name', '_flags', '_version'): record.pop(key)
        need(next_offset == cd_offset, 'hidden/gapped bytes before ZIP central table')
        need(size - total <= OVERHEAD_BYTES, 'ZIP total overhead cap')
        need(_identity(os.fstat(stream.fileno())) == before == _identity(path.stat()), 'ZIP changed during preflight')
    return {'path': str(path), 'bytes': size, 'uncompressed_bytes': total, 'members': records,
            'zip64': has_zip64, 'central_offset': cd_offset, 'central_bytes': cd_bytes,
            'comment_bytes': comment, 'file_identity': before}


def verify_evidence_zip(path, *, expected_members=None, checkpoint_archive_body=None, _deadline_at=None):
    """Preflight then CRC+SHA each bounded stored body, without ZipFile parsing.

    Direct offset reads avoid stdlib EOCD comment ambiguity and any second
    central-table allocation. Identity checks bind preflight and streaming to
    the same unchanged regular file. Reads never deserialize member content.
    """
    result = preflight_evidence_zip(path, checkpoint_archive_body=checkpoint_archive_body, _deadline_at=_deadline_at)
    records = result['members']; before = result['file_identity']
    if expected_members is not None:
        need(set(expected_members) == {r['name'] for r in records}, 'ZIP member inventory differs')
    members = {}; path = _regular(path)
    with path.open('rb') as archive:
        need(_identity(os.fstat(archive.fileno())) == before, 'ZIP changed after preflight')
        for record in records:
            archive.seek(record['data_offset']); hashed = hashlib.sha256(); crc = 0; remaining = record['bytes']
            while remaining:
                _deadline(_deadline_at)
                block = _read(archive, min(CHUNK_BYTES, remaining)); remaining -= len(block)
                hashed.update(block); crc = zlib.crc32(block, crc)
            need(crc == record['crc32'], 'streamed ZIP CRC differs')
            row = {'bytes': record['bytes'], 'sha256': hashed.hexdigest()}
            if expected_members is not None:
                need(row == expected_members[record['name']], 'ZIP streamed member hash differs: ' + record['name'])
            if record['name'] == 'checkpoints.zip' and checkpoint_archive_body is not None:
                need(row == checkpoint_archive_body, 'retained diagnostic checkpoint archive inventory differs')
            members[record['name']] = row
        archive.seek(0); archive_hash = hashlib.sha256(); remaining = result['bytes']
        while remaining:
            _deadline(_deadline_at)
            block = _read(archive, min(CHUNK_BYTES, remaining)); remaining -= len(block); archive_hash.update(block)
        need(_identity(os.fstat(archive.fileno())) == before == _identity(path.stat()), 'ZIP changed while streaming')
    _deadline(_deadline_at)
    return {'path': str(path), 'bytes': result['bytes'], 'sha256': archive_hash.hexdigest(),
            'members': members, 'member_count': len(members), 'uncompressed_bytes': result['uncompressed_bytes'],
            'zip64': result['zip64'], 'crc_verified': True, 'member_sha256_verified': True}


def _snapshot(root, deadline=None):
    inventory_path = root / 'artifact-inventory.json'; inventory = _json(inventory_path)
    need(inventory.get('format') == 'owned-rl-artifact-inventory-v1' and
         inventory.get('exclusions') == ['artifact-inventory.json'] and inventory.get('truncated') is False,
         'complete unchanged original artifact inventory required')
    files = inventory.get('files')
    need(type(files) is dict and 0 < len(files) <= MAX_MEMBERS, 'bounded original artifact inventory')
    actual = {}; checkpoint_bytes = evidence_bytes = 0
    for path in root.rglob('*'):
        _deadline(deadline)
        need(not path.is_symlink(), 'artifact symlink forbidden')
        if path.is_dir(): continue
        _regular(path); name = _name(path.relative_to(root).as_posix())
        size = path.stat().st_size
        if name == 'artifact-inventory.json': continue
        need(len(actual) < MAX_MEMBERS, 'artifact inventory member cap')
        row = files.get(name)
        need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int and
             row['bytes'] >= 0 and _sha_value(row['sha256']), 'strict artifact inventory row')
        if name.startswith('experiment/checkpoints/'):
            checkpoint_bytes += size; limit = 768 * 1024**2
        elif name == 'checkpoints.zip': limit = CHECKPOINT_CAP_BYTES
        else: evidence_bytes += size; limit = _member_limit(name)
        need(size <= limit and size == row['bytes'], 'artifact member length/cap differs: ' + name)
        need(_file_hash(path, deadline) == row['sha256'], 'original artifact bytes differ: ' + name)
        actual[name] = row
    need(set(actual) == set(files), 'missing/extra original inventory member')
    need(checkpoint_bytes <= CHECKPOINT_CAP_BYTES and evidence_bytes <= EVIDENCE_CAP_BYTES,
         'original artifact aggregate cap')
    need(inventory.get('checkpoint_bytes') == checkpoint_bytes and inventory.get('evidence_bytes') == evidence_bytes,
         'original artifact inventory totals differ')
    actual['artifact-inventory.json'] = {'bytes': inventory_path.stat().st_size, 'sha256': _file_hash(inventory_path, deadline)}
    return actual


def _omissions(root, files, *, diagnostic=False):
    omitted = {}; retained = {}
    def keep(member, reason):
        retained[member] = {'reason': reason, 'original_bytes': files[member]['bytes'],
                            'original_sha256': files[member]['sha256']}
    for label in ('base', 'A', 'B', 'C', 'B-batch-0', 'B-batch-1', 'B-batch-2', 'B-batch-3'):
        prefix = 'experiment/checkpoints/' + label + '/'; manifest_name = prefix + 'manifest.json'
        candidates = [prefix + tail for tail in TENSOR_NAMES if prefix + tail in files]
        if not candidates: continue
        if manifest_name not in files:
            for member in candidates: keep(member, 'checkpoint-manifest-absent-no-omission-authority')
            continue
        try:
            manifest = _json(root / manifest_name)
            need(type(manifest) is dict and manifest.get('format') == 'rl-owned-same-source-state-v1' and
                 type(manifest.get('files')) is dict, 'declared checkpoint manifest required')
        except (OSError, ValueError, TypeError) as exc:
            if not diagnostic: raise
            for member in candidates: keep(member, 'undecidable-checkpoint-manifest:' + type(exc).__name__)
            continue
        for member in candidates:
            tail = member[len(prefix):]
            if tail not in manifest['files']:
                keep(member, 'tensor-not-declared-in-checkpoint-manifest'); continue
            if manifest['files'][tail] != files[member]['sha256']:
                if not diagnostic: raise ValueError('tensor omission requires exact manifest and original inventory hash')
                keep(member, 'checkpoint-manifest-and-original-inventory-disagree'); continue
            omitted[member] = {'reason': 'manifest-declared-checkpoint-tensor-body',
                               'checkpoint_manifest': manifest_name, **_external(root / member, files[member])}
    if 'checkpoints.zip' in files:
        try:
            need('checkpoint-zip-descriptor.json' in files, 'checkpoint archive body requires retained descriptor')
            descriptor = _json(root / 'checkpoint-zip-descriptor.json')
            need(type(descriptor) is dict and descriptor.get('format') == 'owned-checkpoint-zip-descriptor-v1' and
                 descriptor.get('bytes') == files['checkpoints.zip']['bytes'] and
                 descriptor.get('sha256') == files['checkpoints.zip']['sha256'] and
                 descriptor.get('runtime_export_verified') is True,
                 'original checkpoint ZIP descriptor differs')
        except (OSError, ValueError, TypeError) as exc:
            if not diagnostic: raise
            keep('checkpoints.zip', 'undecidable-checkpoint-archive-descriptor:' + type(exc).__name__)
        else:
            omitted['checkpoints.zip'] = {'reason': 'separate-checkpoint-archive-body',
                                        'descriptor': 'checkpoint-zip-descriptor.json',
                                        **_external(root / 'checkpoints.zip', files['checkpoints.zip'])}
    return omitted, retained


def _external(path, row):
    return {'original_bytes': row['bytes'], 'original_sha256': row['sha256'],
            'local_presence_observed': path.is_file(), 'local_observed_bytes': path.stat().st_size,
            'local_sha256_verified': True, 'local_observed_sha256': row['sha256'],
            'archive_body_included': False, 'external_body_materialized': False,
            'external_sha256_independently_verified': False, 'external_observed_sha256': None}


def _checkpoint_observation(omitted):
    body = omitted.get('checkpoints.zip')
    if body is None: return None
    return {'filename': 'checkpoints.zip', 'present': True, 'byte_length': body['local_observed_bytes'],
            'transport_observation': 'DECLARED_LOCAL_ARCHIVE_PRESENT', 'body_materialized': False,
            'independently_sha256_verified': False, 'observed_sha256': None}


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _write_terminal(path, receipt):
    data = (json.dumps(receipt, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    need(len(data) <= METADATA_BYTES, 'terminal receipt metadata cap')
    need(shutil.disk_usage(path.parent).free >= len(data) + DISK_RESERVE_BYTES,
         'terminal receipt preserves 4GiB disk reserve')
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    _fsync_directory(path.parent)
    return {'path': str(path), 'sha256': file_sha(path), 'bytes': path.stat().st_size}


def _destinations(root, destination, terminal_path):
    root = Path(root).absolute(); destination = Path(destination).absolute()
    terminal = Path(terminal_path).absolute() if terminal_path else Path(str(destination) + '.terminal.json')
    partial = Path(str(destination) + '.partial')
    for path in (root, destination, terminal, partial):
        need(all(not p.is_symlink() for p in (path, *path.parents)), 'regular export ancestry required')
    root = root.resolve(); destination = destination.resolve(); terminal = terminal.resolve(); partial = partial.resolve()
    need(root.is_dir() and destination.parent.is_dir() and terminal.parent.is_dir(), 'existing export parent required')
    need(len({root, destination, terminal, partial}) == 4 and all(not p.exists() and not p.is_relative_to(root)
         for p in (destination, terminal, partial)), 'fresh external ZIP/terminal/partial destinations required')
    return root, destination, terminal, partial


def _authorize(capability, kind):
    from .supervisor import verify_closed_capability, verify_terminated_capability
    need(kind in ('closed', 'terminated'), 'known live export authority required')
    verified = (verify_closed_capability(capability) if kind == 'closed'
                else verify_terminated_capability(capability))
    root = Path(verified['output_root'])
    outer = root / 'outer-closure.json'; request = root / 'owner-request.json'
    need(_json(outer) == verified, 'persisted outer closure differs from live export authority')
    request_data = _json(request); request_sha = _file_hash(request)
    need(request_sha == verified['launch_request_sha256'] and
         request_data.get('output_root') == str(root) and request_data.get('clock') == verified['original_clock'],
         'actual owner request/clock differs from live launch')
    source = _json(root / 'release-source-inventory.json')
    need(source.get('source_sha256') == verified['launch_source_sha256'] and
         source.get('files') == request_data.get('sources'), 'owner source inventory differs from live launch')
    return {'kind': 'live-owned-model-closure' if kind == 'closed' else 'live-owned-process-termination',
            'output_root': verified['output_root'], 'original_deadlines': verified['original_deadlines'],
            'original_clock': verified['original_clock'], 'source_sha256': verified['launch_source_sha256'],
            'owner_request_ref': {'path': str(request), 'file_sha256': request_sha},
            'outer_closure_ref': {'path': str(outer), 'file_sha256': _file_hash(outer)},
            'worker_pid': verified['worker_pid'], 'worker_exited': True, 'worker_session_empty': True}


def _export(capability, root, destination, terminal_path, *, kind):
    authority = _authorize(capability, kind)
    model_closed = kind == 'closed'
    root, destination, terminal, partial = _destinations(root, destination, terminal_path)
    need(root == Path(authority['output_root']).resolve(), 'export authority output root differs')
    deadline = authority['original_deadlines']['absolute']
    started = time.monotonic(); inventory = None; omitted = {}; retained_bodies = {}; completed = None
    receipt = {'format': 'owned-rl-evidence-terminal-v1', 'status': 'interrupted',
               'output_root': str(root), 'mode': 'runtime-reload-bound', 'model_closed': False,
               'model_success_claim': False, 'scientific_goal_met': False, 'production_admitted': False,
               'archive_complete': False, 'archive': None, 'external_bodies': {},
               'independent_checkpoint_tensor_verification': False,
               'external_archive_sha256_independently_verified': False,
               'authorization': authority, 'started_monotonic': started,
               'caps': {'evidence_bytes': EVIDENCE_CAP_BYTES, 'checkpoint_bytes': CHECKPOINT_CAP_BYTES,
                        'members': MAX_MEMBERS, 'json_member_bytes': MAX_JSON_MEMBER_BYTES,
                        'journal_bytes': MAX_JOURNAL_BYTES, 'free_disk_reserve_bytes': DISK_RESERVE_BYTES,
                        'archive_overhead_bytes': OVERHEAD_BYTES, 'stream_chunk_bytes': CHUNK_BYTES},
               'terminal_metadata_may_finish_after_absolute_deadline': True}
    try:
        need(_authorize(capability, kind) == authority, 'live export authority changed')
        files = _snapshot(root, deadline); inventory = files['artifact-inventory.json']
        omitted, retained_bodies = _omissions(root, files, diagnostic=kind == 'terminated')
        retained = {name: row for name, row in files.items() if name not in omitted}
        total = sum(row['bytes'] for row in retained.values())
        need(total <= EVIDENCE_CAP_BYTES and len(retained) <= MAX_MEMBERS, 'evidence-only expansion cap')
        need(shutil.disk_usage(destination.parent).free >= total + OVERHEAD_BYTES + DISK_RESERVE_BYTES,
             'evidence ZIP requires actual bytes plus 16MiB overhead and 4GiB reserve')
        with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for name, row in sorted(retained.items()):
                need(time.monotonic() < authority['original_deadlines']['absolute'], 'original absolute export deadline')
                source = _regular(root / name); hashed = hashlib.sha256(); length = 0
                info = zipfile.ZipInfo(name); info.compress_type = zipfile.ZIP_STORED
                info.external_attr = (stat.S_IFREG | 0o600) << 16; info.file_size = row['bytes']
                with source.open('rb') as incoming, archive.open(info, 'w', force_zip64=True) as outgoing:
                    while True:
                        block = incoming.read(CHUNK_BYTES)
                        if not block: break
                        need(time.monotonic() < authority['original_deadlines']['absolute'], 'original absolute export deadline')
                        length += len(block); need(length <= row['bytes'], 'source grew during export')
                        outgoing.write(block); hashed.update(block)
                need(length == row['bytes'] and hashed.hexdigest() == row['sha256'], 'source changed during export')
        with partial.open('rb') as stream: os.fsync(stream.fileno())
        completed = verify_evidence_zip(partial, expected_members=retained, _deadline_at=deadline,
            checkpoint_archive_body=files['checkpoints.zip'] if kind == 'terminated' and 'checkpoints.zip' in retained else None)
        need(_snapshot(root, deadline) == files, 'original output changed during export')
        need(_authorize(capability, kind) == authority, 'live export authority changed')
        need(time.monotonic() < authority['original_deadlines']['absolute'], 'original absolute export deadline')
        # Link is exclusive: a competing path is never overwritten.
        os.link(partial, destination); partial.unlink(); _fsync_directory(destination.parent)
        completed['path'] = str(destination)
        receipt.update(status='complete' if model_closed else 'diagnostic', model_closed=model_closed,
                       archive_complete=True, archive=completed)
    except BaseException as exc:
        observed = destination if destination.exists() else partial
        if observed.exists():
            _regular(observed)
            partial_sha = None
            try: partial_sha = _file_hash(observed, deadline)
            except (OSError, ValueError, TimeoutError): pass
            receipt['partial_archive'] = {'path': str(observed), 'bytes': observed.stat().st_size,
                                          'sha256': partial_sha, 'sha256_completed': partial_sha is not None,
                                          'contents_verified': False}
        receipt.update(error={'type': type(exc).__name__, 'message': str(exc)[:4096]},
                       original_artifact_inventory=inventory, external_bodies=omitted, retained_body_exceptions=retained_bodies,
                       checkpoint_archive_observation=_checkpoint_observation(omitted),
                       finished_monotonic=time.monotonic())
        _write_terminal(terminal, receipt)
        raise
    receipt.update(original_artifact_inventory=inventory, external_bodies=omitted, retained_body_exceptions=retained_bodies,
                   checkpoint_archive_observation=_checkpoint_observation(omitted),
                   finished_monotonic=time.monotonic())
    terminal_ref = _write_terminal(terminal, receipt)
    return {**receipt, 'terminal_receipt': terminal_ref}


def export_evidence_only(capability, root, destination, *, terminal_path=None):
    """Successful local export requires the original live closed capability."""
    return _export(capability, root, destination, terminal_path, kind='closed')


def export_diagnostic_evidence(authorization, root, destination, *, terminal_path=None):
    """Stopped-run export needs actual live supervised process termination.

    A serialized receipt, orphan directory, caller boolean, or forged token is
    insufficient. Empty process session does not establish model/device closure.
    """
    return _export(authorization, root, destination, terminal_path, kind='terminated')

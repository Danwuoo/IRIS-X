"""Hash-verify and safely restore one IRIS-X transfer ZIP; stdlib only.

Nested archives are opaque file payloads. No authentication or runtime entry is
available. All outer payload members pass hashes/CRC before output is created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile


INVENTORY_NAME = 'PAYLOAD-INVENTORY.json'
MAX_TOTAL_BYTES = 1024**3
MAX_MEMBER_BYTES = 200 * 1024**2
MAX_INVENTORY_BYTES = 16 * 1024**2
MAX_MEMBERS = 100_000
CHUNK_BYTES = 1024**2
SHA = re.compile(r'[0-9a-f]{64}')
RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)),
            *(f'lpt{i}' for i in range(1, 10))}


class TransferError(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise TransferError(message)


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'explicit absolute path required')
    for ancestor in reversed((path, *path.parents)):
        try:
            info = ancestor.lstat()
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'link/reparse ancestor denied')
    return path


def portable_name(name):
    need(type(name) is str and bool(name) and len(name.encode('utf-8')) <= 4096,
         'bounded member name required')
    path = PurePosixPath(name)
    need(bool(path.parts) and not path.is_absolute() and path.as_posix() == name and '\\' not in name
         and not any(ord(char) < 32 or ord(char) == 127 or char in '<>"|?*' for char in name),
         'unsafe member name')
    for part in path.parts:
        need(part not in ('.', '..') and ':' not in part and not part.endswith((' ', '.'))
             and part.split('.', 1)[0].casefold() not in RESERVED, 'nonportable member name')
    return name


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate inventory JSON key')
        result[key] = value
    return result


def central_inventory(archive):
    rows = archive.infolist()
    need(0 < len(rows) <= MAX_MEMBERS, 'bounded nonempty central inventory required')
    files, folded = {}, set()
    total = 0
    for info in rows:
        need(info.orig_filename == info.filename, 'unsafe truncated member name')
        name = portable_name(info.filename)
        need(name not in files and name.casefold() not in folded,
             'duplicate/casefold member collision')
        need(not info.is_dir() and info.create_system == 3
             and stat.S_ISREG(info.external_attr >> 16) and not info.external_attr & 0x10,
             'only explicit regular payload members allowed')
        need(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
             'encrypted/unsupported compression denied')
        need(0 <= info.file_size <= MAX_MEMBER_BYTES and 0 <= info.compress_size <= MAX_TOTAL_BYTES,
             'member byte cap exceeded')
        total += info.file_size
        need(total <= MAX_TOTAL_BYTES, 'aggregate uncompressed byte cap exceeded')
        files[name] = info
        folded.add(name.casefold())
    for name in files:
        for parent in PurePosixPath(name).parents:
            if str(parent) != '.':
                need(str(parent).casefold() not in folded, 'file/directory prefix collision')
    need(INVENTORY_NAME in files and files[INVENTORY_NAME].file_size <= MAX_INVENTORY_BYTES,
         'bounded payload inventory missing')
    return files, total


def stream_member(archive, info, *, expected=None, destination=None, collect=False):
    measured = hashlib.sha256()
    count, parts = 0, []
    with archive.open(info, 'r') as source:
        while chunk := source.read(CHUNK_BYTES):
            count += len(chunk)
            need(count <= info.file_size and count <= MAX_MEMBER_BYTES, 'streamed member cap exceeded')
            measured.update(chunk)
            if destination is not None:
                destination.write(chunk)
            if collect:
                need(count <= MAX_INVENTORY_BYTES, 'inventory stream cap exceeded')
                parts.append(chunk)
    row = {'bytes': count, 'sha256': measured.hexdigest()}
    need(count == info.file_size, 'central/member size differs')
    if expected is not None:
        need(row == expected, 'payload bytes/hash differs: ' + info.filename)
    return row, b''.join(parts) if collect else None


def payload_inventory(archive, files):
    row, raw = stream_member(archive, files[INVENTORY_NAME], collect=True)
    inventory = json.loads(raw, object_pairs_hook=unique_pairs)
    need(type(inventory) is dict and raw == canonical(inventory), 'canonical payload inventory required')
    need(set(files) == set(inventory) | {INVENTORY_NAME} and INVENTORY_NAME not in inventory,
         'closed payload inventory differs')
    for name, descriptor in inventory.items():
        portable_name(name)
        need(type(descriptor) is dict and set(descriptor) == {'bytes', 'sha256'}
             and type(descriptor['bytes']) is int and 0 <= descriptor['bytes'] <= MAX_MEMBER_BYTES
             and type(descriptor['sha256']) is str and SHA.fullmatch(descriptor['sha256']) is not None,
             'invalid payload descriptor')
        need(descriptor['bytes'] == files[name].file_size, 'inventory/central size differs')
    return inventory, row


def file_hash(stream):
    stream.seek(0)
    result, count = hashlib.sha256(), 0
    while chunk := stream.read(CHUNK_BYTES):
        count += len(chunk)
        need(count <= MAX_TOTAL_BYTES, 'outer archive byte cap exceeded')
        result.update(chunk)
    return result.hexdigest(), count


def unchanged(before, after):
    return all(getattr(before, key) == getattr(after, key)
               for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def process(*, archive_path, expected_sha256, output_root=None):
    archive_path = ordinary(archive_path)
    need(type(expected_sha256) is str and SHA.fullmatch(expected_sha256) is not None,
         'expected lowercase SHA256 required')
    output = ordinary(output_root) if output_root is not None else None
    if output is not None:
        need(not output.exists(), 'existing output denied; preserve earlier results')
        need(not archive_path.is_relative_to(output), 'archive/output overlap denied')
    before = archive_path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= MAX_TOTAL_BYTES,
         'bounded single-link regular archive required')
    descriptor = os.open(archive_path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        need(unchanged(before, os.fstat(stream.fileno())), 'archive changed before open')
        sha, archive_bytes = file_hash(stream)
        need(sha == expected_sha256, 'outer archive SHA256 differs')
        stream.seek(0)
        with zipfile.ZipFile(stream, 'r') as archive:
            files, total = central_inventory(archive)
            inventory, manifest_row = payload_inventory(archive, files)
            for name in sorted(inventory):
                stream_member(archive, files[name], expected=inventory[name])
            need(unchanged(before, os.fstat(stream.fileno())), 'archive changed during verification')
            need(file_hash(stream)[0] == expected_sha256, 'archive changed after full verification')
            if output is not None:
                # No output is created until the entire archive has passed above.
                ordinary(output)
                output.mkdir(parents=True, mode=0o700)
                for name in sorted(files):
                    target = output.joinpath(*PurePosixPath(name).parts)
                    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                    ordinary(target)
                    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                    with os.fdopen(fd, 'wb') as destination:
                        stream_member(archive, files[name], destination=destination,
                                      expected=manifest_row if name == INVENTORY_NAME else inventory[name])
                need(unchanged(before, os.fstat(stream.fileno())), 'archive changed during restore')
    return {'format': 'irisx/verified-transfer-restore-v1', 'status': 'PASS',
            'archive_sha256': sha, 'archive_bytes': archive_bytes,
            'payload_files': len(inventory), 'uncompressed_bytes_including_inventory': total,
            'inventory_sha256': manifest_row['sha256'], 'all_member_hashes_and_CRC_verified': True,
            'extracted': output is not None, 'output_root': str(output) if output else None,
            'nested_archive_members_opened': False, 'provider_calls': 0,
            'partial_output_on_error': 'preserved; no overwrite or deletion'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--verify-only', action='store_true')
    mode.add_argument('--output-root', type=Path)
    args = parser.parse_args(argv)
    try:
        result = process(archive_path=args.archive, expected_sha256=args.sha256, output_root=args.output_root)
    except (TransferError, OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error),
                          'partial_output_preserved': True, 'provider_calls': 0}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

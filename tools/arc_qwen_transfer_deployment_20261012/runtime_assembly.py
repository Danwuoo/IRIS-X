"""Offline closed-source runtime assembly; no provider, Git, network or model calls.

This is new owner-handoff support, outside the frozen 197 runtime members.
The prior portfolio assembler and all frozen source bytes are preserved.

Only assemble_runtime() and the CLI perform pinned production-source admission.
Internal helpers support source-only synthetic tests and make no execution claim.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat

SOURCE_FREEZE_SHA256 = 'c6f64e966a2ee719d71ff8d6f2777fb275ffb1728ed5c1db9178f63a33a78dd5'
PUBLICATION_MANIFEST_SHA256 = '689e587ce8d7c0c7c606176dac5c010e7a9a1fb817d65ace1c59773f55f96d9a'
PATH_MAP_SHA256 = '370b278549fdfe0438155d85d8c8a32b9edaa3145dc088e1d1455e3f2d57896e'
FULL_IDENTITY_SHA256 = '964475ab2b97a8c45407c771aad233c8833569e5e2aba30d7378735c109af400'
INNER_IDENTITY_SHA256 = '1500df54b593a72441a0237f6697951eb390945988d637cf0e5bf359ea208da7'
FULL_COUNT = 197
INNER_COUNT = 192
MATERIAL_COUNT = 28
MATERIAL_LOGICAL = 'materials/qwen14b/'
MATERIAL_REPOSITORY = 'research/qwen14b-materials/'
INNER_EXCLUSIONS = frozenset({
    'materials/qwen14b/README.md', 'materials/qwen14b/SOURCES.md',
    'tools/arc_qwen_transfer_20261012/README.md',
    'materials/qwen14b/hf-overlay/LICENSE', 'materials/qwen14b/provenance/requirements.lock',
})
FILE_CAP = 12582912
TOTAL_CAP = 16777216
DOCUMENT_CAP = 2 * 1024**2
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class AssemblyError(ValueError):
    """Fixed error codes without untrusted source contents."""


def need(condition, code):
    if not condition:
        raise AssemblyError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha((json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                           allow_nan=False)+'\n').encode())


def safe_name(name):
    need(type(name) is str and 0 < len(name) < 4096 and '\\' not in name and ':' not in name
         and not any(ord(c) < 32 for c in name) and not name.startswith('/')
         and all(part not in ('', '.', '..') for part in name.split('/')), 'unsafe_relative_path')
    return name


def explicit_path(value):
    need(isinstance(value, (str, Path)) and bool(str(value).strip()), 'explicit_local_path_required')
    path = Path(value)
    need('..' not in path.parts, 'unsafe_local_path')
    return path.absolute()


@contextmanager
def directory(path):
    """Open every ancestor without following symlinks; hold its descriptor."""
    path = explicit_path(path)
    fd = os.open(path.anchor, DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            child = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    except OSError as exc:
        raise AssemblyError('directory_unavailable_or_link') from exc
    finally:
        os.close(fd)


@contextmanager
def relative_parent(root_fd, name):
    parts = safe_name(name).split('/')
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd, parts[-1]
    except OSError as exc:
        raise AssemblyError('source_unavailable_or_link') from exc
    finally:
        os.close(fd)


def read_regular(root_fd, name, cap, *, require_mode=False):
    with relative_parent(root_fd, name) as (parent_fd, leaf):
        fd = None
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'regular_unlinked_file_required')
            need(before.st_size <= cap, 'file_size_cap')
            if require_mode:
                need(stat.S_IMODE(before.st_mode) == 0o644, 'source_mode_must_be_100644')
            chunks = []
            count = 0
            while True:
                block = os.read(fd, min(1024**2, cap+1-count))
                if not block:
                    break
                chunks.append(block)
                count += len(block)
                need(count <= cap, 'file_size_cap')
            after = os.fstat(fd)
            need(count == before.st_size == after.st_size and
                 (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns) ==
                 (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns), 'source_changed_during_read')
            return b''.join(chunks)
        except OSError as exc:
            raise AssemblyError('source_unavailable_or_link') from exc
        finally:
            if fd is not None:
                os.close(fd)


def read_document(path, expected_sha):
    path = explicit_path(path)
    with directory(path.parent) as parent_fd:
        raw = read_regular(parent_fd, path.name, DOCUMENT_CAP)
    need(sha(raw) == expected_sha, 'frozen_document_hash_mismatch')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(AssemblyError('nonfinite_json')))
        need(type(result) is dict, 'document_object_required')
        digest(result)
        return result
    except (ValueError, TypeError) as exc:
        if isinstance(exc, AssemblyError):
            raise
        raise AssemblyError('invalid_json') from exc


def repository_name(logical):
    safe_name(logical)
    if logical == 'panel-freeze/public120-exclusions.json':
        return 'research/qwen-transfer-20261012/panel-freeze/public120-exclusions.json'
    return MATERIAL_REPOSITORY+logical[len(MATERIAL_LOGICAL):] if logical.startswith(MATERIAL_LOGICAL) else logical


def _validate_structure(freeze, publication, mapping):
    """Pure structural checks; caller must separately pin all three documents."""
    need(freeze['format'] == 'irisx/qwen14b-transfer-source-freeze-v1' and
         publication['format'] == 'irisx/qwen14b-transfer-publication-contract-v1' and
         mapping['format'] == 'qwen-transfer-runtime-path-map-v1', 'document_formats')
    files = freeze['files']
    identity = freeze['source_identity']
    entries = mapping['files']
    inner_record = publication['terminal_contract']['inner_request_source_identity']
    inner = inner_record['mapping']
    need(type(files) is dict and type(identity) is dict and type(entries) is dict and type(inner) is dict,
         'mapping_objects_required')
    need(len(files) == FULL_COUNT and set(entries) == set(files) == set(identity)
         and freeze['runtime_member_count'] == FULL_COUNT, 'closed_full_mapping')
    need(len(inner) == INNER_COUNT and set(inner) == set(identity)-INNER_EXCLUSIONS
         and all(inner[name] == identity[name] for name in inner), 'complete_inner_subset')
    total = 0
    repository_paths = set()
    for name, row in entries.items():
        safe_name(name)
        need(type(row) is dict and set(row) == {'repository_path', 'mode', 'bytes', 'sha256'}, 'mapping_entry_schema')
        need(type(files[name]) is dict and set(files[name]) == {'bytes', 'sha256'}, 'freeze_entry_schema')
        need(type(row['bytes']) is int and 0 <= row['bytes'] <= (12*1024**2 if name == 'materials/qwen14b/hf-overlay/tokenizer.json' else 2*1024**2) and type(row['sha256']) is str
             and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None, 'mapping_entry_values')
        need({key: row[key] for key in ('bytes', 'sha256')} == files[name]
             and row['sha256'] == identity[name] and row['mode'] == '100644', 'frozen_entry_binding')
        need(safe_name(row['repository_path']) == repository_name(name), 'closed_logical_path_mapping')
        need(row['repository_path'] not in repository_paths, 'duplicate_repository_path')
        repository_paths.add(row['repository_path'])
        total += row['bytes']
    need(total == freeze['total_expanded_bytes'] and total <= TOTAL_CAP, 'expanded_size_binding')
    need(sum(name.startswith(MATERIAL_LOGICAL) for name in entries) == MATERIAL_COUNT, 'closed_material_count')
    need(digest(identity) == freeze['source_identity_sha256'] == publication['source_identity_sha256']
         == mapping['source_identity_sha256'], 'full_identity_binding')
    need(digest(inner) == inner_record['identity_sha256'] == mapping['inner_source_identity_sha256'],
         'inner_identity_binding')
    need(mapping['source_freeze_sha256'] == publication['source_freeze_sha256'], 'source_freeze_binding')
    return entries, inner


def load_contract(*, source_freeze, publication_manifest, path_map):
    freeze = read_document(source_freeze, SOURCE_FREEZE_SHA256)
    publication = read_document(publication_manifest, PUBLICATION_MANIFEST_SHA256)
    mapping = read_document(path_map, PATH_MAP_SHA256)
    entries, inner = _validate_structure(freeze, publication, mapping)
    need(mapping['source_freeze_sha256'] == SOURCE_FREEZE_SHA256 and
         mapping['publication_manifest_sha256'] == PUBLICATION_MANIFEST_SHA256 and
         mapping['source_identity_sha256'] == FULL_IDENTITY_SHA256 and
         mapping['inner_source_identity_sha256'] == INNER_IDENTITY_SHA256, 'frozen_anchor_binding')
    return entries, inner


def _inventory(root_fd):
    """List a closed tree without following symbolic links or special files."""
    files = set()
    directories = set()
    def walk(fd, prefix):
        for leaf in os.listdir(fd):
            safe_name(leaf)
            name = prefix+leaf
            info = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                directories.add(name)
                child = os.open(leaf, DIR_FLAGS, dir_fd=fd)
                try:
                    walk(child, name+'/')
                finally:
                    os.close(child)
            else:
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'inventory_link_or_special_file')
                files.add(name)
    walk(root_fd, '')
    return files, directories


def _expected_directories(names):
    return {'/'.join(name.split('/')[:index]) for name in names for index in range(1, len(name.split('/')))}


def _read_sources(repository_fd, entries):
    material_names = {row['repository_path'][len(MATERIAL_REPOSITORY):]
                      for name, row in entries.items() if name.startswith(MATERIAL_LOGICAL)}
    with relative_parent(repository_fd, MATERIAL_REPOSITORY.rstrip('/')) as (parent_fd, leaf):
        fd = os.open(leaf, DIR_FLAGS, dir_fd=parent_fd)
        try:
            material_files, material_dirs = _inventory(fd)
        finally:
            os.close(fd)
    need(material_files == material_names and material_dirs == _expected_directories(material_names),
         'dedicated_materials_tree_not_closed')
    result = {}
    for name, row in entries.items():
        raw = read_regular(repository_fd, row['repository_path'], FILE_CAP, require_mode=True)
        need(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'source_bytes_mismatch')
        result[name] = raw
    return result


def _check_locations(repository_root, output_root):
    repository_root = explicit_path(repository_root)
    output_root = explicit_path(output_root)
    need(repository_root != output_root and repository_root not in output_root.parents
         and output_root not in repository_root.parents, 'source_output_overlap')
    need(output_root.name not in ('', '.', '..'), 'invalid_output_root')
    return repository_root, output_root


def _require_absent(parent_fd, leaf):
    try:
        os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise AssemblyError('output_must_be_new')


def _verify_tree(root_fd, entries, inner):
    files, directories = _inventory(root_fd)
    need(files == set(entries) and directories == _expected_directories(entries), 'output_tree_not_closed')
    observed = {}
    for name, row in entries.items():
        raw = read_regular(root_fd, name, FILE_CAP, require_mode=True)
        need(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'output_bytes_mismatch')
        observed[name] = sha(raw)
    need(digest(observed) == digest({name: row['sha256'] for name, row in entries.items()})
         and digest({name: observed[name] for name in inner}) == digest(inner), 'output_identity_mismatch')


def _write_new_tree(parent_fd, leaf, sources, entries, inner):
    """Create exactly one new output; never modify or replace an existing path."""
    _require_absent(parent_fd, leaf)
    os.mkdir(leaf, 0o700, dir_fd=parent_fd)
    root_fd = os.open(leaf, DIR_FLAGS, dir_fd=parent_fd)
    try:
        root_stat = os.fstat(root_fd)
        for name in sorted(_expected_directories(sources), key=lambda x: (x.count('/'), x)):
            with relative_parent(root_fd, name) as (fd, child):
                os.mkdir(child, 0o755, dir_fd=fd)
        for name, raw in sources.items():
            with relative_parent(root_fd, name) as (fd, child):
                target = os.open(child, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
                try:
                    view = memoryview(raw)
                    while view:
                        written = os.write(target, view)
                        need(written > 0, 'output_write_failed')
                        view = view[written:]
                    os.fchmod(target, 0o644)
                finally:
                    os.close(target)
        _verify_tree(root_fd, entries, inner)
        linked = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        need(stat.S_ISDIR(linked.st_mode) and (linked.st_dev, linked.st_ino) ==
             (root_stat.st_dev, root_stat.st_ino), 'output_root_replaced')
        os.fchmod(root_fd, 0o755)
    finally:
        os.close(root_fd)


def assemble_runtime(*, repository_root, output_root, source_freeze, publication_manifest, path_map):
    repository_root, output_root = _check_locations(repository_root, output_root)
    entries, inner = load_contract(source_freeze=source_freeze, publication_manifest=publication_manifest, path_map=path_map)
    with directory(repository_root) as repository_fd, directory(output_root.parent) as parent_fd:
        _require_absent(parent_fd, output_root.name)
        sources = _read_sources(repository_fd, entries)
        # Every input has now been checked and captured. No output writes occur earlier.
        _write_new_tree(parent_fd, output_root.name, sources, entries, inner)
    return {'format': 'qwen-transfer-runtime-assembly-receipt-v1', 'runtime_assembled': True,
            'runtime_member_count': FULL_COUNT, 'inner_member_count': INNER_COUNT,
            'material_member_count': MATERIAL_COUNT, 'source_identity_sha256': FULL_IDENTITY_SHA256,
            'inner_source_identity_sha256': INNER_IDENTITY_SHA256,
            'source_freeze_sha256': SOURCE_FREEZE_SHA256, 'publication_manifest_sha256': PUBLICATION_MANIFEST_SHA256,
            'path_map_sha256': PATH_MAP_SHA256, 'output_root': str(output_root),
            'provider_execution_claim': False, 'production_evidence_validated': False,
            'repository_files_modified': False, 'public_score': None}


def verify_runtime(runtime_root, repository_root):
    """Read-only verification for CPU wrappers, before any runtime/model imports.

    Metadata and mapping have fixed repository locations and exact pinned bytes.
    No source or runtime files are written, repaired, imported, or executed.
    """
    repository_root, runtime_root = _check_locations(repository_root, runtime_root)
    deployment = repository_root/'tools/arc_qwen_transfer_deployment_20261012'
    release = deployment/'release/transfer-v1'
    entries, inner = load_contract(source_freeze=release/'SOURCE-FREEZE.json',
                                   publication_manifest=release/'publication-manifest.json',
                                   path_map=deployment/'runtime-path-map.json')
    with directory(repository_root) as repository_fd, directory(runtime_root) as runtime_fd:
        _read_sources(repository_fd, entries)
        _verify_tree(runtime_fd, entries, inner)
    return {'format': 'qwen-transfer-runtime-verification-receipt-v1', 'runtime_verified': True,
            'runtime_member_count': FULL_COUNT, 'inner_member_count': INNER_COUNT,
            'source_identity_sha256': FULL_IDENTITY_SHA256, 'inner_source_identity_sha256': INNER_IDENTITY_SHA256,
            'source_freeze_sha256': SOURCE_FREEZE_SHA256, 'publication_manifest_sha256': PUBLICATION_MANIFEST_SHA256,
            'path_map_sha256': PATH_MAP_SHA256, 'runtime_root': str(runtime_root),
            'provider_execution_claim': False, 'production_evidence_validated': False,
            'repository_files_modified': False, 'runtime_files_modified': False, 'public_score': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'output-root', 'source-freeze', 'publication-manifest', 'path-map'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = vars(parser.parse_args())
    try:
        result = assemble_runtime(**args)
    except Exception as exc:
        print(json.dumps({'runtime_assembled': False, 'provider_execution_claim': False,
                          'error': str(exc) if isinstance(exc, AssemblyError) else 'assembly_failed',
                          'error_type': type(exc).__name__, 'partial_output_may_exist': True}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

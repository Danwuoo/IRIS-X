"""Bounded evidence archive plus separately retained adapter/checkpoint artifacts."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import time
import zipfile

from tools.arc_kaggle_submission import parse_json
from tools.arc_learning_agent_20261011.budget import atomic_json, canonical

ENVIRONMENT_LOCK = 'environment/environment-cp312-cu128/evidence/environment-lock.json'
INSTALLATION_RECEIPT = 'environment/environment-cp312-cu128/installation-receipt.json'
PROOF_LIMIT = 1024 * 1024


@contextmanager
def _open_path(path, *, directory=False):
    """Open each component without following links, including ancestor races."""
    path = Path(path).absolute()
    if '..' in path.parts: raise ValueError('output path traversal forbidden')
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(path.parts[1:]):
            is_directory = directory or index < len(path.parts) - 2
            flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if is_directory else os.O_NONBLOCK)
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except OSError as exc:
                raise ValueError('missing, symlink or nonregular output path') from exc
            os.close(descriptor); descriptor = child
        mode = os.fstat(descriptor).st_mode
        if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
            raise ValueError('nonregular output forbidden')
        yield descriptor
    finally:
        os.close(descriptor)


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_file(path, deadline, *, destination=None, limit=None):
    """Hash the exact bytes copied to ZIP; reject replacement or in-place races."""
    digest = hashlib.sha256(); size = 0; chunks = []
    with _open_path(path) as descriptor:
        before = os.fstat(descriptor)
        if limit is not None and before.st_size > limit:
            raise ValueError('export proof byte bound')
        while True:
            if time.monotonic() >= deadline: raise TimeoutError('export deadline')
            block = os.read(descriptor, 1024 * 1024)
            if not block: break
            size += len(block)
            if limit is not None and size > limit: raise ValueError('export proof byte bound')
            digest.update(block)
            if destination is not None: destination.write(block)
            if limit is not None: chunks.append(block)
        if _signature(before) != _signature(os.fstat(descriptor)) or size != before.st_size:
            raise ValueError('output changed during archive seal')
        with _open_path(path) as current:
            if _signature(before) != _signature(os.fstat(current)):
                raise ValueError('output changed during archive seal')
    return {'bytes': size, 'sha256': digest.hexdigest()}, b''.join(chunks)


def file_hash(path, deadline):
    return _read_file(path, deadline)[0]['sha256']


def _included_files(directory, deadline, prefix=''):
    # Never enumerate the excluded tree. Only its root and fixed proof paths
    # are opened. CPython and venv installation legitimately contain links.
    with os.scandir(directory) as entries:
        entries = sorted(entries, key=lambda entry: entry.name)
    for entry in entries:
        if time.monotonic() >= deadline: raise TimeoutError('export inventory deadline')
        name = prefix + entry.name
        if '\\' in name or ':' in name or any(ord(c) < 32 for c in name):
            raise ValueError('unsafe output archive name')
        info = entry.stat(follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode): raise ValueError('output symlink forbidden')
        if not prefix and entry.name == 'environment':
            if not stat.S_ISDIR(info.st_mode): raise ValueError('environment directory required')
            continue
        if stat.S_ISDIR(info.st_mode):
            try:
                child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            except OSError as exc:
                raise ValueError('output directory changed or symlink') from exc
            try:
                if (info.st_dev, info.st_ino) != (os.fstat(child).st_dev, os.fstat(child).st_ino):
                    raise ValueError('output directory changed during inventory')
                yield from _included_files(child, deadline, name + '/')
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode):
            yield name
        else:
            raise ValueError('nonregular output forbidden')


def _environment_proofs(root, deadline):
    if not os.path.lexists(root / 'environment'):
        if os.path.lexists(root / 'bootstrap-receipt.json'):
            raise ValueError('bootstrap proof requires its environment directory')
        return {}
    with _open_path(root / 'environment', directory=True): pass
    bootstrap_row, raw = _read_file(root / 'bootstrap-receipt.json', deadline, limit=PROOF_LIMIT)
    bootstrap = parse_json(raw)
    if (type(bootstrap) is not dict or bootstrap.get('status') != 'prepared'
            or bootstrap.get('installed_offline') is not True
            or bootstrap.get('environment_lock_path') != str(root / ENVIRONMENT_LOCK)
            or not re.fullmatch('[0-9a-f]{64}', str(bootstrap.get('actual_environment_lock_sha256', '')))):
        raise ValueError('bound bootstrap environment proof required')
    lock_row, lock_raw = _read_file(root / ENVIRONMENT_LOCK, deadline, limit=PROOF_LIMIT)
    receipt_row, receipt_raw = _read_file(root / INSTALLATION_RECEIPT, deadline, limit=PROOF_LIMIT)
    lock = parse_json(lock_raw)
    environment = root / 'environment/environment-cp312-cu128'
    command = [str(environment / 'bin/python'), '-I', '-B', '-S', str(environment / 'offline-run.py')]
    if (lock_row['sha256'] != bootstrap['actual_environment_lock_sha256'] or receipt_raw != lock_raw
            or type(lock) is not dict or lock.get('format') != 'irisx/arc-next-environment-lock-v1'
            or lock.get('status') != 'installed-offline'
            or lock.get('environment_lock') != str(root / ENVIRONMENT_LOCK)
            or lock.get('python_command') != command or bootstrap.get('python_command') != command
            or lock.get('python_executable') != command[0]
            or lock.get('python_launcher_path') != command[-1]):
        raise ValueError('bootstrap environment lock/installation receipt binding differs')
    return {'bootstrap-receipt.json': bootstrap_row, ENVIRONMENT_LOCK: lock_row,
            INSTALLATION_RECEIPT: receipt_row}


def export_evidence(root, *, run_id, deadline):
    root = Path(root).absolute()
    if type(run_id) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', run_id):
        raise ValueError('safe export run identity required')
    with _open_path(root, directory=True) as directory:
        root_identity = os.fstat(directory)
        archive_root = root / 'archives'
        if os.path.lexists(archive_root): raise ValueError('archive identity consumed')
        proofs = _environment_proofs(root, deadline)
        names = list(_included_files(directory, deadline))
    inventory, separate = {}, {}
    for name in sorted(set(names) | set(proofs)):
        row, _ = _read_file(root / name, deadline)
        if name in proofs and row != proofs[name]: raise ValueError('environment proof changed during inventory')
        if name.startswith(('worker/checkpoints/', 'worker/trained-global-adapter/')):
            separate[name] = row
        else: inventory[name] = row
    total = sum(r['bytes'] for r in inventory.values())
    if total > 512 * 1024**2: raise ValueError('evidence archive uncompressed512MiB cap')
    if shutil.disk_usage(root).free < total + 256 * 1024**2:
        raise ValueError('insufficient archive reserve; raw evidence retained')
    with _open_path(root, directory=True) as directory:
        current = os.fstat(directory)
        if (root_identity.st_dev, root_identity.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('output root changed during archive seal')
    archive_root.mkdir()
    manifest = {'format': 'irisx/learning-evidence-inventory-v1', 'run_id': run_id,
                'files': inventory, 'separate_artifacts': separate,
                'separate_reason': 'training checkpoints and inference adapter are retained as individual files, not duplicated in evidence ZIP',
                'evaluator_answer_payloads_included': False,
                'installed_environment_included': False}
    if proofs:
        manifest['environment_proof_files'] = {name: proofs[name] for name in (ENVIRONMENT_LOCK, INSTALLATION_RECEIPT)}
        manifest['excluded_payloads'] = ['environment/** except the two explicitly bound environment_proof_files']
    atomic_json(archive_root / 'evidence-inventory.json', manifest, exclusive=True)
    target = archive_root / ('evidence-' + run_id + '.zip')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, row in inventory.items():
            if time.monotonic() >= deadline: raise TimeoutError('archive deadline')
            if _read_file(root / name, deadline)[0] != row:
                raise ValueError('output changed during archive seal')
            with archive.open(name, 'w') as member:
                copied, _ = _read_file(root / name, deadline, destination=member)
            if copied != row: raise ValueError('output changed during archive seal')
        archive.writestr('evidence-inventory.json', canonical(manifest))
    # Recheck exclusion proof linkage as well as bytes before publishing closure.
    if _environment_proofs(root, deadline) != proofs:
        raise ValueError('environment proof changed during archive seal')
    for name, row in separate.items():
        if _read_file(root / name, deadline)[0] != row:
            raise ValueError('separate artifact changed during archive seal')
    with target.open('rb') as stream: os.fsync(stream.fileno())
    receipt = {'format': 'irisx/learning-export-closure-v1', 'run_id': run_id,
                'archive': {'path': str(target), 'bytes': target.stat().st_size,
                            'sha256': file_hash(target, deadline)},
                'inventory_sha256': hashlib.sha256(canonical(manifest)).hexdigest(),
                'separate_artifacts': separate, 'generation_may_resume': False}
    atomic_json(root / 'post-seal-closure.json', receipt, exclusive=True)
    return receipt

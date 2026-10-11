"""Bounded evidence archive plus separately retained adapter/checkpoint artifacts."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import stat
import time
import zipfile

from tools.arc_learning_agent_20261011.budget import atomic_json, canonical


def file_hash(path, deadline):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            if time.monotonic() >= deadline: raise TimeoutError('export deadline')
            block = stream.read(1024 * 1024)
            if not block: break
            digest.update(block)
    return digest.hexdigest()


def export_evidence(root, *, run_id, deadline):
    root = Path(root)
    archive_root = root / 'archives'
    if archive_root.exists(): raise ValueError('archive identity consumed')
    inventory, separate = {}, {}
    for path in sorted(root.rglob('*')):
        if time.monotonic() >= deadline: raise TimeoutError('export inventory deadline')
        if path.is_symlink(): raise ValueError('output symlink forbidden')
        if path.is_dir(): continue
        if not stat.S_ISREG(path.stat().st_mode): raise ValueError('nonregular output forbidden')
        name = path.relative_to(root).as_posix()
        if name.startswith('environment/'):
            continue  # Installed environment has its separately bound lock and bootstrap receipts.
        row = {'bytes': path.stat().st_size, 'sha256': file_hash(path, deadline)}
        if name.startswith(('worker/checkpoints/', 'worker/trained-global-adapter/')):
            separate[name] = row
        else: inventory[name] = row
    total = sum(r['bytes'] for r in inventory.values())
    if total > 512 * 1024**2: raise ValueError('evidence archive uncompressed512MiB cap')
    if shutil.disk_usage(root).free < total + 256 * 1024**2:
        raise ValueError('insufficient archive reserve; raw evidence retained')
    archive_root.mkdir()
    manifest = {'format': 'irisx/learning-evidence-inventory-v1', 'run_id': run_id,
                'files': inventory, 'separate_artifacts': separate,
                'separate_reason': 'training checkpoints and inference adapter are retained as individual files, not duplicated in evidence ZIP',
                'evaluator_answer_payloads_included': False,
                'installed_environment_included': False}
    atomic_json(archive_root / 'evidence-inventory.json', manifest, exclusive=True)
    target = archive_root / ('evidence-' + run_id + '.zip')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, row in inventory.items():
            if time.monotonic() >= deadline: raise TimeoutError('archive deadline')
            path = root / name
            if path.stat().st_size != row['bytes'] or file_hash(path, deadline) != row['sha256']:
                raise ValueError('output changed during archive seal')
            archive.write(path, name)
        archive.writestr('evidence-inventory.json', canonical(manifest))
    with target.open('rb') as stream: os.fsync(stream.fileno())
    receipt = {'format': 'irisx/learning-export-closure-v1', 'run_id': run_id,
                'archive': {'path': str(target), 'bytes': target.stat().st_size,
                            'sha256': file_hash(target, deadline)},
                'inventory_sha256': hashlib.sha256(canonical(manifest)).hexdigest(),
                'separate_artifacts': separate, 'generation_may_resume': False}
    atomic_json(root / 'post-seal-closure.json', receipt, exclusive=True)
    return receipt

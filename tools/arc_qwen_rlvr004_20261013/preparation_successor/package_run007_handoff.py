"""Local reconstruction: package a committed source and reviewed deployment.

No provider calls. Historical evaluator proof is copied opaquely into the local
deployment backup, separated from the source and the sole Kaggle upload payload.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import zipfile


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, cap=128 * 1024**2):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'no linked package input')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap, 'bounded ordinary package input')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    identity = lambda r: (r.st_dev, r.st_ino, r.st_size, r.st_mtime_ns, r.st_ctime_ns, r.st_nlink)
    need(identity(before) == identity(opened) == identity(after) == identity(path.lstat()) and len(raw) == before.st_size, 'package input changed')
    return raw


def desc(raw):
    return {'bytes': len(raw), 'sha256': sha(raw)}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def zip_roundtrip(path, files):
    need(not path.exists(), 'fresh archive required')
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, raw in sorted(files.items()):
            pure = PurePosixPath(name)
            need(str(pure) == name and not pure.is_absolute() and all(v not in ('.', '..') for v in pure.parts)
                 and '\\' not in name and ':' not in name, 'safe package member')
            info = zipfile.ZipInfo(name, (2026, 10, 13, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    with zipfile.ZipFile(path) as archive:
        need(archive.namelist() == sorted(files), 'archive closed path set')
        for name, raw in files.items():
            need(archive.read(name) == raw, 'archive byte roundtrip: ' + name)


def package(*, repository_root, candidate_root, commit, output_root, validation_summary):
    repository, candidate, output = map(lambda p: Path(p).absolute(), (repository_root, candidate_root, output_root))
    need(len(commit) == 40 and all(c in '0123456789abcdef' for c in commit), 'exact committed source required')
    need(not output.exists() and not output.is_relative_to(candidate), 'fresh separate package root required')
    actual = subprocess.check_output(['git', 'rev-parse', commit + '^{commit}'], cwd=repository).decode().strip()
    need(actual == commit, 'commit identity')
    manifest_raw = read(candidate / 'publication-manifest.json')
    manifest = json.loads(manifest_raw)
    need(manifest['format'] == 'irisx/qwen14b-rlvr-run007-publication-contract-v1', 'reviewed run007 deployment required')
    need(manifest.get('source_review_only') is False and manifest.get('run_authorized') is True
         and manifest.get('release_runtime_finalized') is True, 'final independently reviewed candidate required')
    summary_raw = read(validation_summary, 4 * 1024**2)
    summary = json.loads(summary_raw)
    need(summary.get('format') == 'irisx/run007-local-validation-summary-v1', 'validation summary schema')
    output.mkdir(parents=True)
    source = subprocess.check_output(['git', 'archive', '--format=zip', commit], cwd=repository)
    need(len(source) <= 128 * 1024**2, 'compact committed source archive')
    write_new(output / 'IRIS-X-run007-local-source.zip', source)
    inventory_raw = read(candidate / 'ASSEMBLY-INVENTORY.json')
    inventory = json.loads(inventory_raw)
    actual = {p.relative_to(candidate).as_posix() for p in candidate.rglob('*') if p.is_file()}
    need(actual == set(inventory) | {'ASSEMBLY-INVENTORY.json'}, 'complete closed candidate file set')
    need(sum(r['bytes'] for r in inventory.values()) <= 512 * 1024**2, 'compact local candidate bound')
    files = {'TEST-RESULTS.json': summary_raw, 'candidate/ASSEMBLY-INVENTORY.json': inventory_raw}
    for name, row in inventory.items():
        pure = PurePosixPath(name)
        need(str(pure) == name and not pure.is_absolute() and '..' not in pure.parts and '\\' not in name
             and ':' not in name, 'closed candidate relative path')
        raw = read(candidate / name)
        need(desc(raw) == row, 'closed candidate body changed: ' + name)
        files['candidate/' + name] = raw
    selected = [manifest['datasets'][0]['transport_archive'], *manifest['notebooks'], manifest['jit']['entry'],
                *manifest['jit']['dependencies']]
    for row in selected:
        name = row['path']
        pure = PurePosixPath(name)
        need(str(pure) == name and not pure.is_absolute() and '..' not in pure.parts and '\\' not in name, 'declared relative input')
        raw = read(candidate / name)
        need(desc(raw) == {k: row[k] for k in ('bytes', 'sha256')}, 'declared package input digest')
        need(files['candidate/' + name] == raw, 'selected executable candidate binding')
    evaluator_archives = sorted(n for n in inventory if n.endswith('.evidence.zip'))
    isolation = {'format': 'irisx/local-deployment-evaluator-isolation-v1',
                 'evaluator_only_archives': ['candidate/' + n for n in evaluator_archives],
                 'kaggle_upload_member': 'candidate/' + manifest['datasets'][0]['transport_archive']['path'],
                 'full_local_backup_must_not_be_uploaded_as_code_dataset': True,
                 'evaluator_archive_members_opened': False, 'solver_or_training_use_authorized': False}
    files['EVALUATOR-ONLY-ISOLATION.json'] = encoded(isolation)
    instructions = ('Run007 local repair, source commit ' + commit + '\n\n'
        'Read Decision 0073 and the run007 local handoff. Use a clean Git clone/checkout of the exact source commit, with the frozen snapshot tag and its history fetched.\n'
        'The accompanying git-archive source ZIP has no .git or history and cannot alone authenticate the frozen snapshot.\n'
        'The deployment ZIP contains the complete closed reviewed candidate, JIT finalizer/dependencies, exact code upload, inactive/active templates and test summary.\n'
        'Extract candidate/ as the reviewed candidate root. Only candidate/code-upload.zip is the Kaggle code upload payload.\n'
        'The full local deployment ZIP contains opaque historical evaluator-only proof archives; never upload this full ZIP as code or expose those archives to solver/training/prompt inputs.\n'
        'Runtime epoch is absent from the template; the reviewed transport binds a fresh immutable pre-dispatch epoch exactly once.\n'
        'Authentic predecessor candidate/state/target-free solver and independently reviewed local operator configuration/reviews are separate local inputs.\n'
        'Historical evaluator-only proof remains under candidate/historical-v31 and candidate/predecessor-v33, outside candidate/code-payload and the Kaggle upload. No credentials or model weights are included.\n'
        'Do not dispatch again after an accepted RUN. Preserve claims/journals and reconcile any unknown outcome before writes.\n'
        'This package does not assert GPU installation, model inference, valid scoring or scientific success.\n').encode()
    files['DEPLOYMENT-README.txt'] = instructions
    zip_roundtrip(output / 'IRIS-X-run007-local-deployment.zip', files)
    record = {'format': 'irisx/run007-local-handoff-package-v1', 'source_commit': commit,
              'publication_manifest_sha256': sha(manifest_raw), 'source_archive': desc(source),
              'deployment_archive': desc(read(output / 'IRIS-X-run007-local-deployment.zip')),
              'deployment_members': {n: desc(b) for n, b in sorted(files.items())},
              'local_reconstruction': True, 'full_original_release_recovered': False,
              'credentials_or_weights_included': False, 'historical_evaluator_escrow_included': bool(evaluator_archives),
              'historical_evaluator_escrow_scope': 'LOCAL_OPAQUE_PROOF_ONLY_NEVER_KAGGLE_CODE_UPLOAD',
              'provider_calls': 0, 'GPU_or_scientific_success': False}
    write_new(output / 'PACKAGE-MANIFEST.json', encoded(record))
    write_new(output / 'TEST-RESULTS.json', summary_raw)
    write_new(output / 'DEPLOYMENT-README.txt', instructions)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'candidate-root', 'commit', 'output-root', 'validation-summary'):
        parser.add_argument('--' + name, required=True)
    print(encoded(package(**vars(parser.parse_args()))).decode(), end='')


if __name__ == '__main__':
    main()

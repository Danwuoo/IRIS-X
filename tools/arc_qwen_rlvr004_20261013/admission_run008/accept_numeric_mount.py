"""Native run008 owned no-model acceptance for a reviewed numeric readback.

No provider or credential access. A caller-supplied authentic numeric receipt
and closed downloaded tree are both required; local fixtures cannot stand in
for that provenance. This wrapper never modifies the admitted candidate.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import time
import types

HERE = Path(__file__).absolute().parent
VERIFY_SHA = 'f3cc35d60fd5f5aaa173feeb824120ff6ed18fea6a8aaba0f3368a973215e2b8'
_path = HERE.parent / 'preparation_successor/v35_lineage.py'
if any(p.is_symlink() for p in (_path, *_path.parents)):
    raise ValueError('unsafe pinned verifier source')
_before = _path.lstat()
if not stat.S_ISREG(_before.st_mode) or _before.st_nlink != 1 or _before.st_size > 1024**2:
    raise ValueError('bounded ordinary verifier source required')
with os.fdopen(os.open(_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as _stream:
    _opened = os.fstat(_stream.fileno())
    if (_before.st_dev, _before.st_ino, _before.st_size, _before.st_nlink) != (_opened.st_dev, _opened.st_ino, _opened.st_size, _opened.st_nlink):
        raise ValueError('verifier source changed')
    _raw = _stream.read(1024**2 + 1)
if hashlib.sha256(_raw).hexdigest() != VERIFY_SHA:
    raise ValueError('unreviewed verifier source')
v = types.ModuleType('numeric_mount_pinned_stdlib_verifier')
v.__file__, v.__package__ = str(_path), ''
exec(compile(_raw, str(_path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(v))

MANIFEST_SHA = None
INVENTORY_SHA = None
HELPER = 'assembly/accept_downloaded_mount.py'
GUARD = 'producer-source/baseline/tools/arc_learning_agent_20261011/process_guard.py'
HELPER_SHA = '646b547a3efc848d5ecb0fd0140792fde0de6dbaf69c4407ab9582d4f7433621'
GUARD_SHA = '8bc66ac80499203bca9f583f0d5ea5ecc5d8a131a2aa267f661060fc69e0580c'
SOURCE_SHA = None
ARCHIVE_SHA = None
CODE_MANIFEST_SHA = None
REFERENCE = 'danielwuu/iris-x-learning-agent-code-20261011'
need, read, sha, obj, encoded = v.need, v.read, v.sha, v.obj, v.encoded


def ordinary(path):
    path = Path(os.path.abspath(path))
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary path required')
    return path


def pinned(path, digest):
    need(type(digest) is str and len(digest) == 64 and all(x in '0123456789abcdef' for x in digest), 'SHA256 required')
    raw = read(path)
    need(sha(raw) == digest, 'exact input digest: ' + Path(path).name)
    return raw


def closed(root, rows, *, extra=()):
    root = ordinary(root)
    need(root.is_dir(), 'closed root required')
    v.check_rows(rows)
    need(sum(row['bytes'] for row in rows.values()) <= 128 * 1024**2, 'closed total bound')
    actual = set()
    for path in root.rglob('*'):
        ordinary(path)
        info = path.lstat()
        need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'ordinary closed member')
        if stat.S_ISREG(info.st_mode):
            actual.add(v.relative(path.relative_to(root).as_posix()))
    need(actual == set(rows) | set(extra), 'closed member set differs')
    result = {name: pinned(root / name, row['sha256']) for name, row in rows.items()}
    need(all(len(result[name]) == row['bytes'] for name, row in rows.items()), 'closed member byte count')
    return result


def candidate_inputs(root):
    global SOURCE_SHA, ARCHIVE_SHA
    inventory = obj(pinned(Path(root) / 'ASSEMBLY-INVENTORY.json', INVENTORY_SHA))
    files = closed(root, inventory, extra=('ASSEMBLY-INVENTORY.json',))
    need(sha(files['publication-manifest.json']) == MANIFEST_SHA, 'exact admitted manifest')
    need(sha(files[HELPER]) == HELPER_SHA and sha(files[GUARD]) == GUARD_SHA, 'unchanged frozen helper and guard')
    manifest = obj(files['publication-manifest.json'])
    SOURCE_SHA = manifest['runtime_source_sha256']
    ARCHIVE_SHA = manifest['consumer_contract']['source_archive']['sha256']
    need(all(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
             for value in (SOURCE_SHA, ARCHIVE_SHA)), 'reviewed source/archive digests')
    need(manifest['format'] == 'irisx/qwen14b-rlvr-run008-publication-contract-v1'
         and manifest['runtime_source_sha256'] == SOURCE_SHA and manifest['run_authorized'] is True,
         'exact reviewed candidate identity')
    return manifest, files


def receipt_inputs(manifest, raw, code_root):
    receipt = obj(raw)
    need(receipt.get('status') == 'VERIFIED_CODE_V' + str(manifest['datasets'][0]['expected_version']) and receipt.get('dataset_id') == 12504696
         and type(receipt.get('version')) is int and receipt['version'] == manifest['datasets'][0]['expected_version']
         and receipt.get('is_private') is True and receipt.get('exact_byte_roundtrip') is True,
         'authentic numeric-successor exact private readback receipt required')
    need(receipt.get('manifest_sha256') == receipt.get('publication_manifest_sha256') == MANIFEST_SHA,
         'numeric receipt exact publication binding')
    method, archive = receipt.get('readback_method'), receipt.get('archive_sha256')
    need(method in ('numeric_per_file', 'numeric_whole_archive'), 'official numeric readback method')
    if method == 'numeric_whole_archive':
        need(receipt.get('provider_archive_verified') is True and type(archive) is str
             and len(archive) == 64 and all(x in '0123456789abcdef' for x in archive),
             'whole archive transport provenance')
    else:
        need(receipt.get('provider_archive_verified') is False and archive is None,
             'per-file transport provenance')
    need(receipt.get('payload_root') == str(ordinary(code_root)), 'explicit actual downloaded root binding')
    before = receipt.get('before')
    need(type(before) is dict and before == receipt.get('after') and before.get('id') == 12504696
         and before.get('version') == manifest['datasets'][0]['expected_version'] and before.get('private') is True
         and before.get('owner_ref') == 'danielwuu' and before.get('ref') == REFERENCE,
         'numeric provider metadata bracket')
    layouts = manifest['datasets'][0]['expected_readback_layouts']
    need(receipt.get('layout') in layouts, 'reviewed readback layout')
    listed = layouts[receipt['layout']]
    rows = {row['path']: {k: row[k] for k in ('bytes', 'sha256')} for row in listed}
    need(len(rows) == len(listed), 'no duplicate layout paths')
    need(type(receipt.get('files')) is int and receipt['files'] == len(rows)
         and type(receipt.get('bytes')) is int and receipt['bytes'] == sum(row['bytes'] for row in rows.values())
         and receipt.get('inventory_sha256') == sha(v.canonical(rows)), 'actual numeric inventory binding')
    closed(code_root, rows)
    return receipt


def load_module(raw, path, name):
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


def put(path, value):
    raw = value if isinstance(value, bytes) else encoded(value)
    path = ordinary(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw)
    need(read(path) == raw, 'persisted roundtrip')
    return {'path': str(path), **v.desc(raw)}


def check_closure(guard, proof):
    guard.verify_closed_proof(proof)
    need(proof.get('returncode') == 0 and type(proof.get('returncode')) is int
         and proof.get('worker_returncode') == 0 and type(proof.get('worker_returncode')) is int
         and proof.get('forced') is False, 'successful unforced complete owned closure required')


def check_helper(result):
    need(result.get('format') == 'irisx/rlvr-actual-local-code-mount-acceptance-v1'
         and result.get('status') == 'PASS'
         and all(type(result.get(k)) is int and result[k] == 0
                 for k in ('model_or_GPU_calls', 'public_evaluator_body_reads', 'provider_calls'))
         and result.get('production_execution_claim') is False
         and result.get('provider_provenance_verified_by_this_helper') is False
         and result.get('external_numeric_download_receipt_required') is True,
         'frozen no-model helper result')
    source, isolated = result['source_acceptance'], result['isolated_import']
    need(source['format'] == 'irisx/rlvr-no-model-source-acceptance-v1'
         and source['source_sha256'] == SOURCE_SHA and source['source_archive_sha256'] == ARCHIVE_SHA
         and source['manifest_sha256'] == CODE_MANIFEST_SHA
         and type(source['source_members']) is int and source['source_members'] == 259
         and source['exact_archive_bytes_available'] is True, 'exact complete source259 acceptance')
    need(all(source[k] is False for k in ('model_imported', 'weights_read', 'evaluator_body_read', 'provider_mount_verified'))
         and isolated['source_sha256'] == SOURCE_SHA and isolated['source_only'] is True
         and isolated['model_libraries_imported'] is False, 'no model or evaluator execution')


def accept(*, candidate_root, code_root, code_receipt_path, code_receipt_sha, output_root, manifest_sha, inventory_sha):
    global MANIFEST_SHA, INVENTORY_SHA, CODE_MANIFEST_SHA
    need(all(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
             for digest in (manifest_sha, inventory_sha)), 'independently pinned reviewed candidate digests required')
    MANIFEST_SHA, INVENTORY_SHA = manifest_sha, inventory_sha
    candidate, code, output = map(ordinary, (candidate_root, code_root, output_root))
    receipt_path = ordinary(code_receipt_path)
    need(output.is_relative_to(HERE.parents[2] / '.irisx') and not output.exists(), 'fresh ignored owned output required')
    for root in (candidate, code, receipt_path):
        need(not output.is_relative_to(root) and not root.is_relative_to(output), 'input/output overlap')
    manifest, files = candidate_inputs(candidate)
    CODE_MANIFEST_SHA = manifest['datasets'][0]['root_manifest']['sha256']
    code_version = manifest['datasets'][0]['expected_version']
    receipt_raw = pinned(receipt_path, code_receipt_sha)
    receipt = receipt_inputs(manifest, receipt_raw, code)
    guard_module = load_module(files[GUARD], candidate / GUARD, 'numeric-successor_frozen_owned_guard')
    output.mkdir(parents=True, mode=0o700)
    stdout, stderr = output / 'stdout.txt', output / 'stderr.txt'
    owned = None
    try:
        with stdout.open('xb') as out, stderr.open('xb') as err:
            owned = guard_module.OwnedProcessGuard.spawn(
                [sys.executable, '-I', '-B', '-S', str(candidate / HELPER), '--candidate-root', str(candidate),
                 '--code-root', str(code), '--output-root', str(output / 'acceptance')],
                evidence_dir=output / 'owned-process', cwd=output,
                env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
                     'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1'},
                stdout=out, stderr=err)
            deadline = time.monotonic() + 70
            while owned.poll() is None:
                need(time.monotonic() < deadline, 'no-model acceptance deadline')
                need(stdout.stat().st_size <= 64 * 1024 and stderr.stat().st_size <= 64 * 1024, 'bounded acceptance logs')
                time.sleep(0.02)
        proof = owned.closed_proof()
        check_closure(guard_module, proof)
    except BaseException:
        if owned is not None:
            owned.stop(timeout=5)
        raise
    need(len(read(stdout, 64 * 1024)) <= 64 * 1024 and len(read(stderr, 64 * 1024)) <= 64 * 1024, 'bounded final logs')
    helper_raw = read(output / 'acceptance/receipt.json')
    helper = obj(helper_raw)
    check_helper(helper)
    need(obj(read(stdout)) == helper, 'helper stdout/receipt equality')
    need(helper['actual_code_root'] == str(code) and helper['expected_code_reference'] == REFERENCE + '/' + str(code_version), 'accepted actual numeric-successor root')
    need(pinned(receipt_path, code_receipt_sha) == receipt_raw, 'numeric receipt changed during acceptance')
    receipt_inputs(manifest, receipt_raw, code)
    candidate_inputs(candidate)
    check_closure(guard_module, proof)
    closure = put(output / 'OWNED-CLOSURE.json', proof)
    result = {'format': 'irisx/run008-owned-numeric-mount-acceptance-v1', 'status': 'PASS',
        'publication_manifest_sha256': MANIFEST_SHA, 'assembly_inventory_sha256': INVENTORY_SHA,
        'code_dataset_version': code_version, 'code_receipt_sha256': code_receipt_sha, 'model_calls': 0,
        'owned_tree_closed': True, 'owned_closure': closure, 'numeric_readback_layout': receipt['layout'],
        'helper_receipt': {'path': str(output / 'acceptance/receipt.json'), **v.desc(helper_raw)},
        'helper_source_sha256': HELPER_SHA, 'guard_source_sha256': GUARD_SHA,
        'runner_source_sha256': sha(read(Path(__file__))), 'source_sha256': SOURCE_SHA,
        'provider_calls': 0, 'public_evaluator_body_reads': 0, 'production_execution_claim': False,
        'local_reconstruction': True, 'scope': 'Authentic numeric transport receipt plus exact downloaded bytes and owned no-model source-import closure; no GPU/runtime/scientific success.'}
    put(output / 'MOUNT-RECEIPT.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate-root', 'code-root', 'code-receipt-path', 'code-receipt-sha', 'output-root', 'manifest-sha', 'inventory-sha'):
        parser.add_argument('--' + name, required=True)
    print(encoded(accept(**vars(parser.parse_args()))).decode(), end='')


if __name__ == '__main__':
    main()

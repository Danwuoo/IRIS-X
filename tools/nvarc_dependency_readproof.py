"""Five selected opaque dependency files, read only before explicit native setup.

This is an additive byte-equality gate, not import/build/license/safety or
provider-mount/startup attestation. It neither imports nor discovers files.
"""
from __future__ import annotations
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import stat
import time

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical, digest, require, write

FORMAT = 'irisx/stage4-selected-dependency-readproof-v1'
RECEIPT_FORMAT = 'irisx/stage4-selected-dependency-verification-v1'
PROOF_FILE = 'dependency-readproof.json'
RECEIPT_FILE = 'dependency-readproof-receipt.json'
DEPENDENCY_REF = 'sorokin/pip-install-unsloth-flash-patch'
VERSIONED_REF = DEPENDENCY_REF+'/2'
SELECTED_PATHS = frozenset(('qwen3.patch', 'unsloth/models/qwen3.py',
    'flash_attn-2.8.2.dist-info/METADATA', 'flash_attn-2.8.2.dist-info/RECORD',
    'flash_attn_2_cuda.cpython-311-x86_64-linux-gnu.so'))
LIMITATIONS = {'full_import_inventory_verified': False, 'independent_build_provenance_verified': False,
    'license_closure_verified': False, 'import_safety_verified': False,
    'provider_resolved_version_verified': False, 'platform_parent_startup_attested': False}


def validate_contract(value):
    require(isinstance(value, dict) and set(value) == {'format', 'dependency_ref', 'version_number',
        'script_version_id', 'selected_files', 'evidence_sha256', 'read_limits', 'limitations'} and
        value['format'] == FORMAT and value['dependency_ref'] == DEPENDENCY_REF and
        type(value['version_number']) is int and value['version_number'] == 2 and
        type(value['script_version_id']) is int and value['script_version_id'] == 272622465 and
        value['limitations'] == LIMITATIONS and all(v is False for v in value['limitations'].values()),
        'closed selected-byte read-proof identity/scope required')
    rows = value['selected_files']
    require(isinstance(rows, dict) and set(rows) == SELECTED_PATHS and all(isinstance(row, dict) and
        set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int and 0 < row['bytes'] <= 1024**3 and
        isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']) for row in rows.values()),
        'exact five selected relative paths/positive sizes/SHA256 pins required')
    evidence = value['evidence_sha256']
    require(isinstance(evidence, dict) and set(evidence) == {'minimal_manifest', 'native_manifest',
        'installer_source', 'installer_log'} and all(isinstance(v, str) and
        re.fullmatch('[0-9a-f]{64}', v) for v in evidence.values()), 'independent inert acquisition evidence pins required')
    limits = value['read_limits']
    require(isinstance(limits, dict) and set(limits) == {'maximum_wall_seconds', 'maximum_total_read_bytes',
        'maximum_chunk_bytes', 'minimum_free_working_bytes'} and
        type(limits['maximum_wall_seconds']) in (int, float) and
        math.isfinite(limits['maximum_wall_seconds']) and 0 < limits['maximum_wall_seconds'] <= 600 and
        all(type(limits[k]) is int and limits[k] > 0 for k in limits if k != 'maximum_wall_seconds') and
        limits['maximum_chunk_bytes'] <= 1024**2 and
        sum(row['bytes'] for row in rows.values())+len(rows) <= limits['maximum_total_read_bytes'] <= 2*1024**3 and
        limits['minimum_free_working_bytes'] <= 64*1024**3,
        'positive finite selected-byte deadline/disk/chunk/total-read caps required')
    require(len(canonical(value)) <= 16*1024, 'small selected-byte proof required')
    return value


def read_contract(path):
    path = Path(path)
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= 16*1024,
        'bounded regular read-proof payload required')
    return validate_contract(parse_json(path.read_bytes()))


def bind_contract(value, inventory):
    """Preserve the original inventory; only compare overlapping entries."""
    validate_contract(value)
    for name, row in value['selected_files'].items():
        if name in inventory:
            require(inventory[name] == row, 'selected proof contradicts unchanged source inventory: '+name)


def _root_fd(root):
    # Every ancestor and selected component is opened without following links.
    require(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX no-follow selected-byte gate required')
    path = Path(os.path.abspath(root)); fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        return fd
    except BaseException:
        os.close(fd); raise


def _selected_fd(root_fd, name):
    fd = os.dup(root_fd)
    try:
        parts = name.split('/')
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)


def verify_selected(dependency, contract, *, receipt_path, plan_digest, deadline, working_root,
                    now=time.monotonic, disk_free=lambda p: shutil.disk_usage(p).free):
    """Stream exactly the independently pinned five files. Always retain failure."""
    receipt_path = Path(receipt_path)
    require(not receipt_path.exists() and not receipt_path.is_symlink(), 'new immutable selected-byte receipt required')
    started = now(); receipt = {'format': RECEIPT_FORMAT, 'outcome': 'failed',
        'plan_digest': plan_digest, 'contract_digest': None,
        'dependency_root': os.path.abspath(dependency), 'selected_files': {}, 'file_bytes_read': 0,
        'read_bytes_including_eof_checks': 0, 'elapsed_host_seconds': 0, 'error': None,
        'limitations': dict(LIMITATIONS), 'discovered_code_executions': 0, 'model_calls': 0}
    fd = None
    try:
        validate_contract(contract); receipt['contract_digest'] = digest(contract); limits = contract['read_limits']
        require(type(deadline) in (int, float) and math.isfinite(deadline) and deadline > started,
            'positive finite unexpired selected-byte deadline required')
        deadline = min(deadline, started+limits['maximum_wall_seconds'])
        def check():
            require(now() < deadline, 'selected-byte read deadline exhausted')
        check()
        available = disk_free(working_root)
        require(type(available) is int and available >= limits['minimum_free_working_bytes'],
            'selected-byte free-working-disk reserve unavailable')
        receipt['free_working_bytes_before'] = available
        fd = _root_fd(dependency)
        for name, expected in sorted(contract['selected_files'].items()):
            check(); selected = _selected_fd(fd, name)
            try:
                before = os.fstat(selected)
                require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'],
                    'selected file must be regular, single-linked, and exact-size: '+name)
                result = hashlib.sha256(); count = 0
                while count < expected['bytes']:
                    check(); cap = min(limits['maximum_chunk_bytes'], expected['bytes']-count)
                    require(receipt['read_bytes_including_eof_checks']+cap <= limits['maximum_total_read_bytes'],
                        'selected-byte cumulative read cap exhausted')
                    body = os.read(selected, cap)
                    receipt['read_bytes_including_eof_checks'] += len(body)
                    receipt['file_bytes_read'] += len(body)
                    check()
                    count += len(body); result.update(body)
                    require(body, 'selected file ended before pinned size: '+name)
                check()
                require(receipt['read_bytes_including_eof_checks']+1 <= limits['maximum_total_read_bytes'],
                    'selected-byte EOF-check read cap exhausted')
                extra = os.read(selected, 1)
                receipt['read_bytes_including_eof_checks'] += len(extra)
                check()
                after = os.fstat(selected)
                require(not extra and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                    before.st_ctime_ns, before.st_nlink) == (after.st_dev, after.st_ino, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns, after.st_nlink), 'selected file changed during bounded read: '+name)
                observed = {'bytes': count, 'sha256': result.hexdigest()}
                receipt['selected_files'][name] = observed
                require(observed == expected, 'selected file SHA256 differs: '+name)
            finally:
                os.close(selected)
        check(); receipt['outcome'] = 'verified-selected-bytes'
    except BaseException as error:
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)[:500]}
        raise
    finally:
        if fd is not None: os.close(fd)
        receipt['elapsed_host_seconds'] = max(0, now()-started)
        write(receipt_path, receipt)
    return receipt


def verify_before_prepare(root, plan, dependency, started):
    proof = read_contract(Path(root)/PROOF_FILE)
    require(plan.get('dependency_readproof_digest') == digest(proof), 'immutable selected-byte proof binding differs')
    require(type(started) in (int, float) and math.isfinite(started) and started > 0,
        'positive finite probe start required for selected-byte deadline')
    return verify_selected(dependency, proof, receipt_path=Path(root)/RECEIPT_FILE, plan_digest=digest(plan),
        deadline=started+plan['startup_seconds'], working_root=root)


def require_worker_receipt(root, plan, dependency, expected_sha256):
    path = Path(root)/RECEIPT_FILE
    require(isinstance(expected_sha256, str) and re.fullmatch('[0-9a-f]{64}', expected_sha256) and
        not path.is_symlink() and path.is_file() and path.stat().st_size <= 16*1024,
        'bounded hash-bound parent selected-byte receipt required before worker import')
    body = path.read_bytes(); receipt = parse_json(body)
    proof = read_contract(Path(root)/PROOF_FILE)
    require(hashlib.sha256(body).hexdigest() == expected_sha256 and
        plan.get('dependency_readproof_digest') == digest(proof) == receipt['contract_digest'] and
        receipt['format'] == RECEIPT_FORMAT and receipt['outcome'] == 'verified-selected-bytes' and
        receipt['plan_digest'] == digest(plan) and receipt['dependency_root'] == os.path.abspath(dependency) and
        receipt['selected_files'] == proof['selected_files'] and receipt['error'] is None and
        receipt['limitations'] == LIMITATIONS and receipt['discovered_code_executions'] == receipt['model_calls'] == 0,
        'exact parent selected-byte verification required before worker import')
    return receipt

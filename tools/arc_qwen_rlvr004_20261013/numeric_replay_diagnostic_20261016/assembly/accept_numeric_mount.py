"""Owned no-model mount acceptance for the exact 260-member diagnostic.

The frozen run008 runner retains its receipt, closure, transport and CLI gates.
Only the reviewed diagnostic purpose/source/archive and fixed member count are
specialized. No provider action or production/runtime success is implied.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys
import types

BASE_SHA = 'd84e2aa27edc5cef4fe557a9c327a5b4bffebbadf638d80948927677f1bd70b9'
RUN_PURPOSE = 'training-only-numeric-diagnostic-v1'
SOURCE_SHA = '048e9d3ee8b588cbb2075ae785b3f09fa10e3846a3269001e0c7a5f102865fda'
ARCHIVE_SHA = '23281295453c2d31bf125afd26f84851e2a11ff9373f711961c21082b7e37e84'
ENTRY = Path(os.path.abspath(__file__))
BASE = ENTRY.parents[2] / 'admission_run008/accept_numeric_mount.py'


def source_bytes(path):
    """Read a bounded ordinary source with metadata and repeated-byte checks."""
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('ordinary mount runner source required')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 1024**2:
        raise ValueError('bounded single-link mount runner source required')
    key = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_size,
                         value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        if key(before) != key(os.fstat(stream.fileno())):
            raise ValueError('mount runner source replaced')
        raw = stream.read(1024**2 + 1)
        after = os.fstat(stream.fileno())
        repeated = os.pread(stream.fileno(), 1024**2 + 1, 0)
        final = os.fstat(stream.fileno())
    if (raw != repeated or key(before) != key(after) or key(after) != key(final)
            or key(final) != key(path.lstat()) or len(raw) != before.st_size):
        raise ValueError('mount runner source changed')
    return raw


_entry_raw = source_bytes(ENTRY)
_base_raw = source_bytes(BASE)
if hashlib.sha256(_base_raw).hexdigest() != BASE_SHA:
    raise ValueError('unreviewed frozen run008 mount runner source')
base = types.ModuleType('numeric_diagnostic_pinned_run008_mount')
base.__file__, base.__package__ = str(BASE), ''
exec(compile(_base_raw, str(BASE), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(base))
# Keep the original HERE and dependency-loader context; only receipt attribution
# changes to the real entry whose bytes include the exact frozen base digest.
base.__file__ = str(ENTRY)
_candidate_inputs = base.candidate_inputs
_read = base.read


def check_sources():
    base.need(source_bytes(ENTRY) == _entry_raw, 'diagnostic mount runner source changed')
    base.need(source_bytes(BASE) == _base_raw, 'frozen run008 mount runner source changed')


def read(path, cap=base.v.CAP):
    raw = _read(path, cap)
    if Path(os.path.abspath(path)) == ENTRY:
        check_sources()
        base.need(raw == _entry_raw, 'diagnostic mount runner receipt source changed')
    return raw


def candidate_inputs(root):
    check_sources()
    original = _candidate_inputs(root)
    manifest, _ = original
    base.need(manifest.get('run_purpose') == RUN_PURPOSE
              and manifest.get('runtime_source_sha256') == SOURCE_SHA
              and manifest['consumer_contract']['source_archive'].get('sha256') == ARCHIVE_SHA,
              'exact training-only numeric diagnostic purpose/source/archive required')
    return original


def check_helper(result):
    base.need(result.get('format') == 'irisx/rlvr-actual-local-code-mount-acceptance-v1'
         and result.get('status') == 'PASS'
         and all(type(result.get(k)) is int and result[k] == 0
                 for k in ('model_or_GPU_calls', 'public_evaluator_body_reads', 'provider_calls'))
         and result.get('production_execution_claim') is False
         and result.get('provider_provenance_verified_by_this_helper') is False
         and result.get('external_numeric_download_receipt_required') is True,
         'frozen no-model helper result')
    source, isolated = result['source_acceptance'], result['isolated_import']
    base.need(source['format'] == 'irisx/rlvr-no-model-source-acceptance-v1'
         and source['source_sha256'] == base.SOURCE_SHA and source['source_archive_sha256'] == base.ARCHIVE_SHA
         and source['manifest_sha256'] == base.CODE_MANIFEST_SHA
         and type(source['source_members']) is int and source['source_members'] == 260
         and source['exact_archive_bytes_available'] is True, 'exact complete diagnostic source260 acceptance')
    base.need(all(source[k] is False for k in ('model_imported', 'weights_read', 'evaluator_body_read', 'provider_mount_verified'))
         and isolated['source_sha256'] == base.SOURCE_SHA and isolated['source_only'] is True
         and isolated['model_libraries_imported'] is False, 'no model or evaluator execution')


base.read = read
base.candidate_inputs = candidate_inputs
base.check_helper = check_helper
accept = base.accept
main = base.main


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Offline, stdlib-only inventory of individually acquired provider output bytes.

This is not a Kaggle launcher or downloader. Run with Python -I -S from a
trusted local controller, never from a dependency-mounted notebook parent.
Discovered Python, startup, patch, archive and native files are opaque bytes.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time
import unicodedata
import zipfile


FORMAT = 'irisx/stage4-dependency-output-inventory-v1'
RECEIPT_FORMAT = 'irisx/stage4-dependency-output-receipt-v1'
PLAN_FORMAT = 'irisx/stage4-dependency-inventory-plan-v1'
REF = 'sorokin/pip-install-unsloth-flash-patch'
HISTORICAL_VERSION = 2
HISTORICAL_SCRIPT = 272622465
RUN_ID = 'stage4-dependency-inventory-api-001'
HEX = re.compile(r'[0-9a-f]{64}\Z')
CHUNK = 1024 * 1024


class InventoryError(Exception):
    """A bounded, non-sensitive failure code. No target contents in diagnostics."""


def require(condition, code):
    if not condition:
        raise InventoryError(code)


@dataclass(frozen=True)
class Limits:
    wall_seconds: int = 900
    file_count: int = 65536
    directory_count: int = 65536
    single_file_bytes: int = 2 * 1024**3
    total_file_bytes: int = 32 * 1024**3
    path_utf8_bytes: int = 1024
    path_depth: int = 32
    receipt_bytes: int = 16 * 1024**2
    evidence_file_bytes: int = 16 * 1024**2
    output_bytes: int = 32 * 1024**2


MAXIMUM = Limits()


def limits_valid(limits):
    require(isinstance(limits, Limits), 'limits-type')
    for key, value in asdict(limits).items():
        require(type(value) is int and 0 < value <= getattr(MAXIMUM, key), 'limits-range')


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, allow_nan=False,
                       sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


def sha(body):
    return hashlib.sha256(body).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate-json-key')
        result[key] = value
    return result


def parse(body):
    try:
        return json.loads(body, object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(InventoryError('json-constant')))
    except (UnicodeError, ValueError, RecursionError):
        raise InventoryError('invalid-json') from None


def path_parts(name, limits):
    require(type(name) is str and name and unicodedata.normalize('NFC', name) == name,
            'noncanonical-path')
    try:
        encoded = name.encode('utf-8')
    except UnicodeError:
        raise InventoryError('noncanonical-path') from None
    require(len(encoded) <= limits.path_utf8_bytes and
            not any(ord(c) < 32 or ord(c) == 127 for c in name) and
            '\\' not in name and ':' not in name, 'unsafe-path')
    parts = name.split('/')
    require(len(parts) <= limits.path_depth and all(p not in ('', '.', '..') for p in parts), 'unsafe-path')
    # These are not legitimate inputs to the public dependency-output question.
    forbidden = {'.kaggle', '.ssh', '.aws', '.env', 'kaggle.json', 'credentials',
                 'access_token', 'refresh_token', 'arc-agi_training_solutions.json',
                 'arc-agi_evaluation_solutions.json'}
    require(not any(p.lower() in forbidden or p.lower().endswith('_solutions.json') for p in parts),
            'out-of-scope-path')
    return parts


def platform_valid():
    require(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY')
            and os.open in os.supports_dir_fd and os.scandir in os.supports_fd
            and hasattr(signal, 'setitimer'), 'unsupported-platform')


def open_absolute_directory(path):
    """Open each absolute ancestor with O_NOFOLLOW, never resolve a symlink."""
    path = os.path.abspath(os.fspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open('/', flags)
    try:
        for part in path.split('/')[1:]:
            if part:
                newer = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = newer
        return fd
    except BaseException:
        os.close(fd)
        raise


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def regular_fd(directory, name):
    # NONBLOCK avoids waiting on a raced-in FIFO before fstat can reject it.
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise InventoryError('nonregular-or-hardlinked-file')
    return fd, info


def small_file(path, ceiling):
    path = Path(os.path.abspath(os.fspath(path)))
    directory = open_absolute_directory(path.parent)
    try:
        fd, before = regular_fd(directory, path.name)
        try:
            require(before.st_size <= ceiling, 'metadata-byte-cap')
            body = bytearray()
            while True:
                block = os.read(fd, min(CHUNK, ceiling - len(body) + 1))
                if not block:
                    break
                body.extend(block)
                require(len(body) <= ceiling, 'metadata-byte-cap')
            require(len(body) == before.st_size and signature(before) == signature(os.fstat(fd)),
                    'metadata-changed')
            return bytes(body)
        finally:
            os.close(fd)
    finally:
        os.close(directory)


def positive_int(value):
    return type(value) is int and value > 0


def validate_receipt(receipt, limits):
    keys = {'format', 'run_id', 'provider', 'ref', 'version_number', 'script_version_id',
            'observed_utc', 'listing_complete', 'listing_pages', 'identity_response_sha256',
            'listing_response_sha256', 'scope', 'provider_file_count', 'files'}
    require(type(receipt) is dict and set(receipt) == keys, 'receipt-schema')
    require(receipt['format'] == RECEIPT_FORMAT and receipt['run_id'] == RUN_ID and
            receipt['provider'] == 'kaggle' and receipt['ref'] == REF, 'receipt-identity')
    require(positive_int(receipt['version_number']) and positive_int(receipt['script_version_id'])
            and receipt['listing_complete'] is True and positive_int(receipt['listing_pages'])
            and receipt['listing_pages'] <= 128, 'incomplete-provider-listing')
    try:
        observed = datetime.fromisoformat(receipt['observed_utc'].replace('Z', '+00:00'))
        require(observed.utcoffset() is not None and observed.utcoffset().total_seconds() == 0,
                'receipt-timestamp')
    except (AttributeError, TypeError, ValueError):
        raise InventoryError('receipt-timestamp') from None
    for field in ('identity_response_sha256', 'listing_response_sha256'):
        require(type(receipt[field]) is str and HEX.fullmatch(receipt[field]), 'receipt-evidence-digest')
    rows = receipt['files']
    require(type(rows) is list and 0 < len(rows) <= limits.file_count, 'file-count-cap')
    require(receipt['scope'] in ('selected-provider-output-files', 'complete-provider-output-files')
            and positive_int(receipt['provider_file_count']) and
            len(rows) <= receipt['provider_file_count'] <= limits.file_count and
            (receipt['scope'] != 'complete-provider-output-files' or
             len(rows) == receipt['provider_file_count']), 'receipt-scope')
    files = {}
    total = 0
    for row in rows:
        require(type(row) is dict and set(row) == {'path', 'bytes', 'sha256', 'download_host',
                'download_status', 'download_path_script_version_id'}, 'receipt-file-schema')
        path_parts(row['path'], limits)
        require(row['path'] not in files, 'duplicate-provider-path')
        require(type(row['bytes']) is int and 0 <= row['bytes'] <= limits.single_file_bytes,
                'single-file-byte-cap')
        require(type(row['sha256']) is str and HEX.fullmatch(row['sha256']), 'receipt-file-digest')
        require(row['download_host'] == 'www.kaggleusercontent.com' and
                type(row['download_status']) is int and row['download_status'] == 200 and
                type(row['download_path_script_version_id']) is int and
                row['download_path_script_version_id'] == receipt['script_version_id'],
                'download-version-binding')
        total += row['bytes']
        require(total <= limits.total_file_bytes, 'total-file-byte-cap')
        files[row['path']] = row
    require(list(files) == sorted(files), 'ordered-provider-listing')
    # A file cannot also be the parent of another provider path.
    for name in files:
        parts = name.split('/')
        require(all('/'.join(parts[:i]) not in files for i in range(1, len(parts))),
                'provider-file-directory-alias')
    return files


def startup_kind(name):
    tail = name.split('/')[-1]
    if tail in ('sitecustomize.py', 'usercustomize.py') or tail.endswith('.pth'):
        return 'startup-candidate-opaque'
    if tail.endswith(('.so', '.dll', '.dylib', '.pyd')) or '.so.' in tail:
        return 'native-binary-opaque'
    if tail.endswith(('.whl', '.zip', '.tar', '.tgz', '.tar.gz', '.tar.bz2', '.tar.xz')):
        return 'archive-opaque-members-not-inventoried'
    if tail.endswith('.patch'):
        return 'patch-opaque'
    return 'file-opaque'


def inventory_tree(root, files, limits):
    """Metadata closure, then fd-anchored hashes. No discovery import/execution."""
    fd = open_absolute_directory(root)
    root_info = os.fstat(fd)
    metadata = {}
    directories = {}
    expected_dirs = set()
    for name in files:
        parts = name.split('/')
        for i in range(1, len(parts)):
            expected_dirs.add('/'.join(parts[:i]))
            require(len(expected_dirs) <= limits.directory_count, 'directory-count-cap')
    total_read = 0

    def visit(directory, prefix):
        nonlocal total_read
        before = os.fstat(directory)
        with os.scandir(directory) as entries:
            names = []
            for entry in entries:
                names.append(entry.name)
                require(len(names) <= limits.file_count + limits.directory_count, 'directory-entry-cap')
        for name in sorted(names):
            relative = prefix + name
            path_parts(relative, limits)
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            require(info.st_dev == root_info.st_dev, 'cross-device-entry')
            if stat.S_ISDIR(info.st_mode):
                require(relative in expected_dirs, 'unlisted-directory')
                directories[relative] = signature(info)
                require(len(directories) <= limits.directory_count, 'directory-count-cap')
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=directory)
                try:
                    require(signature(info) == signature(os.fstat(child)), 'directory-changed')
                    visit(child, relative + '/')
                finally:
                    os.close(child)
            else:
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'nonregular-or-hardlinked-file')
                require(relative in files, 'unlisted-file')
                require(len(metadata) < limits.file_count and info.st_size == files[relative]['bytes'],
                        'file-count-or-size-binding')
                source, opened = regular_fd(directory, name)
                try:
                    require(signature(info) == signature(opened), 'file-changed')
                    digest = hashlib.sha256()
                    count = 0
                    while True:
                        block = os.read(source, CHUNK)
                        if not block:
                            break
                        count += len(block)
                        total_read += len(block)
                        require(count <= limits.single_file_bytes and count <= files[relative]['bytes']
                                and total_read <= limits.total_file_bytes, 'read-byte-cap')
                        digest.update(block)
                    require(count == info.st_size and signature(info) == signature(os.fstat(source))
                            and signature(info) == signature(os.stat(name, dir_fd=directory, follow_symlinks=False)),
                            'file-changed')
                    require(digest.hexdigest() == files[relative]['sha256'], 'file-digest-binding')
                    metadata[relative] = {'bytes': count, 'sha256': digest.hexdigest(),
                                          'kind': startup_kind(relative)}
                finally:
                    os.close(source)
        require(signature(before) == signature(os.fstat(directory)), 'directory-changed')

    try:
        visit(fd, '')
        require(set(metadata) == set(files) and set(directories) == expected_dirs, 'provider-output-closure')
        require(signature(root_info) == signature(os.fstat(fd)), 'root-changed')
        return dict(sorted(metadata.items())), sorted(directories), total_read
    finally:
        os.close(fd)


def inventory(root, receipt_path, evidence, limits=MAXIMUM):
    limits_valid(limits)
    platform_valid()
    receipt_body = small_file(receipt_path, limits.receipt_bytes)
    receipt = parse(receipt_body)
    files = validate_receipt(receipt, limits)
    for name, field in (('identity-response.json', 'identity_response_sha256'),
                        ('listing-response.json', 'listing_response_sha256')):
        body = small_file(Path(evidence) / name, limits.evidence_file_bytes)
        require(sha(body) == receipt[field], 'provider-evidence-digest')
        require(isinstance(parse(body), (dict, list)), 'provider-evidence-json')
    observed, directories, total = inventory_tree(root, files, limits)
    binding = {key: receipt[key] for key in ('provider', 'ref', 'version_number', 'script_version_id',
               'observed_utc', 'listing_complete', 'listing_pages', 'identity_response_sha256',
               'listing_response_sha256')}
    binding['receipt_sha256'] = sha(receipt_body)
    return {'format': FORMAT, 'run_id': receipt['run_id'], 'state': 'complete-admitted-local-api-file-copy',
            'provider_binding': binding,
            'scope': receipt['scope'], 'provider_file_count': receipt['provider_file_count'],
            'all_provider_output_files_inventoried': receipt['scope'] == 'complete-provider-output-files',
            'binding_assurance': 'operator-normalized-receipt-byte-bound-not-provider-authenticated',
            'historical_reference': {'version_number': HISTORICAL_VERSION,
                'script_version_id': HISTORICAL_SCRIPT,
                'matches_observed_identity': receipt['version_number'] == HISTORICAL_VERSION and
                                            receipt['script_version_id'] == HISTORICAL_SCRIPT},
            'limits': asdict(limits), 'files': observed, 'directories': directories,
            'file_count': len(observed), 'total_file_bytes': total,
            'path_semantics': 'exact-NFC-UTF8-relative-POSIX-files-no-links-no-extraction',
            'archive_members_inventoried': False, 'actual_current_mount_inventoried': False,
            'api_output_to_mount_equivalence_verified': False, 'source_license_verified': False,
            'native_build_provenance_verified': False, 'safe_to_import_or_execute': False,
            'discovered_files_imported_or_executed': 0, 'model_calls': 0, 'paid_usd': 0}


def alarm_handler(_signum, _frame):
    raise InventoryError('wall-time-cap')


def arm_wall(seconds):
    old = signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    return old


def disarm_wall(old):
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


def write_new(path, body, ceiling):
    require(len(body) <= ceiling, 'output-byte-cap')
    path = Path(os.path.abspath(os.fspath(path)))
    parent = open_absolute_directory(path.parent)
    fd = None
    pending = path.name + '.pending'
    try:
        # Existing outputs and partial attempts are immutable identities.
        for name in (path.name, pending):
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise InventoryError('new-output-identity-required')
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=parent)
        view = memoryview(body)
        while view:
            n = os.write(fd, view[:CHUNK])
            require(n > 0, 'output-write-failed')
            view = view[n:]
        os.fsync(fd)
        os.close(fd)
        fd = None
        # Atomic no-replace finalization; no successful final file on a failed read.
        os.link(pending, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        os.unlink(pending, dir_fd=parent)
        os.fsync(parent)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def plan():
    return {'format': PLAN_FORMAT, 'run_id': RUN_ID, 'provider': 'kaggle', 'ref': REF,
            'approved': False, 'state': 'inert-offline-preparation-auth-checkpoint',
            'route': 'read-only-identity-and-complete-output-listing-then-individual-byte-acquisition',
            'historical_reference': {'version_number': HISTORICAL_VERSION, 'script_version_id': HISTORICAL_SCRIPT},
            'current_version_number': None, 'current_script_version_id': None,
            'safe_mount_only_startup_provenance_established': False,
            'kernel_sources': [], 'dataset_sources': [], 'competition_sources': [], 'model_sources': [],
            'maximum_kernel_pushes': 0, 'maximum_dataset_mutations': 0, 'maximum_gpu_sessions': 0,
            'maximum_model_calls': 0, 'maximum_paid_usd': 0, 'limits': asdict(MAXIMUM),
            'metadata_stage_limits': {'maximum_listing_pages': 128, 'maximum_provider_requests': 132,
                'maximum_wall_seconds': 120, 'maximum_output_file_byte_download_requests': 0,
                'maximum_identity_response_bytes': MAXIMUM.evidence_file_bytes,
                'maximum_all_listing_response_bytes': MAXIMUM.evidence_file_bytes},
            'byte_stage_admission': {'approved': False, 'maximum_file_requests': 0,
                'maximum_total_file_bytes': 0, 'exact_path_size_request_proposal_required': True,
                'explicit_literal_path_selection_required': True,
                'current_version_recheck_required': True, 'fresh_destination_disk_check_required': True,
                'minimum_disk_reserve_bytes': 5 * 1024**3,
                'parser_caps_are_not_acquisition_permission': True,
                'maximum_redirects_per_file_if_approved': 1,
                'automatic_retry_or_cap_enlargement': False},
            'minimum_remote_disclosure': {'code_files': [], 'datasets': [], 'task_or_evaluator_data': [],
                'requested_public_provider_ref': REF,
                'after_auth_read_only_calls': ['current identity/version', 'free quota', 'complete output listing'],
                'credentials_in_artifact': False},
            'launch_gate': 'No notebook launch: dependency source attachment may affect parent Python startup. '
                'Read-only acquisition still needs authorization; output-to-mount equivalence remains unverified.'}


def prepare_acquisition_proposal(listing_path, evidence, destination, selected_paths, limits=MAXIMUM):
    """Offline space/size proposal, never authority and never a downloader.

    The controller supplies independently reviewed normalized listing metadata.
    Response hashes bind evidence bytes, not normalization correctness. A missing
    current script ID blocks; the historical reference is never substituted.
    """
    limits_valid(limits)
    platform_valid()
    body = small_file(listing_path, limits.receipt_bytes)
    listing = parse(body)
    keys = {'format', 'ref', 'version_number', 'script_version_id', 'observed_utc',
            'listing_complete', 'listing_pages', 'identity_response_sha256',
            'listing_response_sha256', 'files'}
    require(type(listing) is dict and set(listing) == keys and
            listing['format'] == 'irisx/stage4-dependency-output-listing-v1', 'listing-schema')
    require(type(listing['files']) is list, 'listing-schema')
    normalized = dict(listing, format=RECEIPT_FORMAT, run_id=RUN_ID, provider='kaggle',
                      scope='complete-provider-output-files', provider_file_count=len(listing['files']))
    rows = []
    for row in listing['files']:
        require(type(row) is dict and set(row) == {'path', 'bytes'}, 'listing-file-schema')
        rows.append(dict(row, sha256='0'*64, download_host='www.kaggleusercontent.com',
                         download_status=200, download_path_script_version_id=listing['script_version_id']))
    normalized['files'] = rows
    files = validate_receipt(normalized, limits)
    require(type(selected_paths) in (list, tuple) and selected_paths and
            all(type(name) is str and name in files for name in selected_paths) and
            len(set(selected_paths)) == len(selected_paths), 'explicit-selected-paths')
    selected = [{'path': name, 'bytes': files[name]['bytes']} for name in sorted(selected_paths)]
    for name, field in (('identity-response.json', 'identity_response_sha256'),
                        ('listing-response.json', 'listing_response_sha256')):
        require(sha(small_file(Path(evidence)/name, limits.evidence_file_bytes)) == listing[field],
                'provider-evidence-digest')
    total = sum(row['bytes'] for row in selected)
    parent = open_absolute_directory(destination)
    try:
        space = os.fstatvfs(parent)
        available = space.f_bavail * space.f_frsize
    finally:
        os.close(parent)
    reserve = 5 * 1024**3
    overhead = limits.output_bytes + limits.receipt_bytes + 2 * limits.evidence_file_bytes
    require(available >= total + reserve + overhead, 'destination-free-disk-reserve')
    return {'format': 'irisx/stage4-dependency-byte-acquisition-proposal-v1', 'run_id': RUN_ID,
            'approved': False, 'maximum_byte_download_requests_until_approval': 0,
            'maximum_byte_download_bytes_until_approval': 0,
            'binding_assurance': 'operator-normalized-listing-byte-bound-not-provider-authenticated',
            'normalized_listing_sha256': sha(body),
            'provider_binding': {key: listing[key] for key in ('ref', 'version_number',
                'script_version_id', 'observed_utc', 'identity_response_sha256', 'listing_response_sha256')},
            'provider_file_count': len(files),
            'scope': 'complete-provider-output-files' if len(selected) == len(files) else 'selected-provider-output-files',
            'proposed_files': selected, 'proposed_exact_file_requests': len(selected),
            'proposed_total_file_bytes': total,
            'proposed_single_file_byte_ceiling': max(row['bytes'] for row in selected),
            'proposed_wall_seconds': limits.wall_seconds, 'maximum_redirects_per_file': 1,
            'automatic_retry_or_cap_enlargement': False,
            'disk_check': {'measured_utc': datetime.now(timezone.utc).isoformat(),
                'destination': os.path.abspath(os.fspath(destination)),
                'available_bytes': available, 'minimum_reserve_bytes': reserve,
                'metadata_and_report_headroom_bytes': overhead,
                'required_available_bytes': total + reserve + overhead,
                'fresh_recheck_required_before_first_byte': True},
            'current_identity_recheck_required_before_first_byte': True,
            'actual_current_mount_inventoried': False,
            'api_output_to_mount_equivalence_verified': False,
            'no_download_authority': True}


PACKAGE_README = b'''IRIS-X Stage 4 dependency inventory, inert API-output route\n\nNo provider client, authentication, downloader, notebook, Dataset or model is included.\nDo not launch a notebook with kernel_sources to run this package. The provider may\nput dependency paths on the parent interpreter before the first cell. Clearing\nsys.path or starting a later -I -S child cannot prove the parent's startup safe.\n\nAfter separately authorized read-only identity/version/quota/listing checks, stop\nbefore bytes. Review an exact path/size/request proposal and measured free disk\nwith a 5-GiB reserve. Parser caps are not download approval. Only after specific\nbyte-stage admission may the exact admitted files be acquired. Preserve redacted\nraw identity/listing JSON outside the\noutput-byte tree. No URLs, tokens, credentials or domain data belong in receipts.\nThe controller must independently review normalized provider/version bindings.\n\nRun on trusted local POSIX storage, from a trusted interpreter/controller:\npython -I -S inventory.py --root OUTPUT_BYTES --receipt receipt.json --evidence EVIDENCE --output NEW_REPORT.json\nUse an external 900-second supervisor as well. Do not set dependency PYTHONPATH.\n\nEvery discovered file, including Python startup code, patches, native binaries\nand archives, is read only as opaque bytes. Archives are not extracted or opened\nfor member inventory. Symlinks, hardlinks, special files, unlisted paths, changed\nfiles, incomplete listings and exceeded caps fail. No automatic retry/enlargement.\nThe report binds exactly this local API-output copy. It does not identify an\nactual notebook mount or certify import safety, licenses or native build provenance.\n'''


def build_package(output):
    """Deterministic closed ZIP of our own source and an inert plan, offline only."""
    import io
    source = small_file(__file__, MAXIMUM.single_file_bytes)
    payload = {'inventory.py': source, 'inventory-plan.json': canonical(plan()), 'README.txt': PACKAGE_README}
    bindings = {'format': 'irisx/stage4-dependency-inventory-package-bindings-v1', 'run_id': RUN_ID,
                'files': {name: {'bytes': len(body), 'sha256': sha(body)} for name, body in sorted(payload.items())}}
    payload['package-bindings.json'] = canonical(bindings)
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, body in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(info, body)
    body = out.getvalue()
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        require(archive.namelist() == sorted(payload), 'closed-package-members')
        for member in archive.infolist():
            require(member.filename in payload and member.file_size == len(payload[member.filename])
                    and archive.read(member) == payload[member.filename], 'package-member-binding')
    write_new(output, body, MAXIMUM.output_bytes)
    return {'state': 'inert-package-created', 'run_id': RUN_ID, 'bytes': len(body), 'sha256': sha(body),
            'members': {name: {'bytes': len(value), 'sha256': sha(value)} for name, value in sorted(payload.items())}}


def main(argv=None):
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1, 'python-I-S-required')
    platform_valid()
    old = arm_wall(MAXIMUM.wall_seconds)
    started = time.monotonic()
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--build-package', type=Path)
        parser.add_argument('--prepare-acquisition', type=Path)
        parser.add_argument('--select', action='append')
        for name in ('root', 'receipt', 'evidence', 'output'):
            parser.add_argument('--' + name, type=Path)
        args = parser.parse_args(argv)
        if args.build_package:
            require(not any((args.prepare_acquisition, args.select, args.root, args.receipt, args.evidence, args.output)),
                    'package-mode-arguments')
            result = build_package(args.build_package)
        elif args.prepare_acquisition:
            require(all((args.root, args.evidence, args.output)) and not args.receipt, 'proposal-mode-arguments')
            proposal = prepare_acquisition_proposal(args.prepare_acquisition, args.evidence, args.root, args.select)
            body = canonical(proposal)
            write_new(args.output, body, MAXIMUM.output_bytes)
            result = {'state': 'unapproved-exact-byte-proposal', 'run_id': RUN_ID,
                      'proposal_bytes': len(body), 'proposal_sha256': sha(body),
                      'proposed_exact_file_requests': proposal['proposed_exact_file_requests'],
                      'proposed_total_file_bytes': proposal['proposed_total_file_bytes'],
                      'byte_downloads_approved': False}
        else:
            require(all((args.root, args.receipt, args.evidence, args.output)) and not args.select,
                    'inventory-mode-arguments')
            root = Path(os.path.abspath(os.fspath(args.root)))
            for path in (args.receipt, args.evidence, args.output):
                absolute = Path(os.path.abspath(os.fspath(path)))
                require(not absolute.is_relative_to(root), 'control-file-inside-target')
            result = inventory(args.root, args.receipt, args.evidence)
            body = canonical(result)
            write_new(args.output, body, MAXIMUM.output_bytes)
            result = {'state': result['state'], 'run_id': result['run_id'], 'file_count': result['file_count'],
                      'total_file_bytes': result['total_file_bytes'], 'report_bytes': len(body),
                      'report_sha256': sha(body), 'actual_current_mount_inventoried': False}
        require(time.monotonic() - started <= MAXIMUM.wall_seconds, 'wall-time-cap')
        print(canonical(result).decode('ascii').rstrip())
        return 0
    finally:
        disarm_wall(old)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (InventoryError, OSError, MemoryError, RecursionError) as error:
        code = str(error) if isinstance(error, InventoryError) else type(error).__name__
        print(json.dumps({'state': 'failed-no-safety-claim', 'code': code}), file=sys.stderr)
        raise SystemExit(124 if code == 'wall-time-cap' else 2)

"""Read-only normalization of non-secret Kaggle evidence for Stage 4.

No credentials, HTTP clients, uploads or competition APIs are used here.
Provider responses must come from a separately authorized authenticated client.
These parsers reject mismatched facts; they cannot authenticate caller-supplied
bytes or attest physical hardware. Raw HTTP headers and signed URLs are excluded.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import math
import re

from tools.arc_kaggle_submission import parse_json
from tools.inspect_nvarc_free_resource import reconcile_quota
from tools.stage4_execution_ledger import canonical, sha, require, timestamp, finite


def quota_cost(*, wall_seconds, gpu_count, allocated_gpu_hours_per_quota_hour):
    """Keep physical allocated GPU time separate from provider-charged quota."""
    finite(wall_seconds, positive=True)
    require(type(gpu_count) is int and 1 <= gpu_count <= 4, 'one to four actual GPUs required')
    finite(allocated_gpu_hours_per_quota_hour, positive=True)
    charged_rate = gpu_count / allocated_gpu_hours_per_quota_hour
    finite(charged_rate, positive=True)
    require(charged_rate >= 1, 'unverified sub-wall-time quota discounts are not admitted')
    allocated = finite(wall_seconds * gpu_count, positive=True)
    charged = finite(wall_seconds * charged_rate, positive=True)
    return {'allocated_gpu_seconds': allocated,
            'charged_quota_seconds': charged,
            'charged_quota_seconds_per_wall_second': charged_rate,
            'allocation_ratio_units': 'allocated GPU-hours per charged quota-hour'}


def _primary_duration(value):
    # Primary protobuf JSON is not the historically broken SDK to_dict() text.
    # Duration fractions have at most nine decimal places; a second decimal
    # point must not be repaired into purported primary evidence.
    require(type(value) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]{1,9})?s', value),
            'valid primary protobuf duration required')
    return finite(float(value[:-1]))


def _quota_object(value, *, required):
    required_durations = {'timeUsed', 'timeReserved', 'totalTimeAllowed'}
    duration_keys = required_durations | {'minimumTimeAllowed'}
    flags = {'isPayToScaleEnabled', 'hasEverRun'}
    require(type(value) is dict and set(value) <= duration_keys | flags
            and (not required or required_durations <= set(value)), 'closed primary accelerator quota required')
    for key in duration_keys & set(value):
        _primary_duration(value[key])
    for key in flags & set(value):
        require(type(value[key]) is bool, 'typed accelerator flag required: ' + key)
    if {'minimumTimeAllowed', 'totalTimeAllowed'} <= set(value):
        require(Decimal(value['minimumTimeAllowed'][:-1]) <= Decimal(value['totalTimeAllowed'][:-1]),
                'minimum guaranteed quota exceeds total allowance')


def normalize_quota(primary_body, typed, *, account, observed_at):
    """Cross-check primary protobuf JSON and typed SDK timedelta totals.

    Never use SDK to_dict() for durations: historical serialization discarded
    complete days. Output carries identity/provenance, not a permission grant.
    """
    require(type(primary_body) is bytes and len(primary_body) <= 1024 * 1024,
            'bounded original primary quota bytes required')
    require(type(account) is str and re.fullmatch('[a-z0-9_-]{1,64}', account),
            'authenticated noncredential account slug required')
    at = timestamp(observed_at)
    raw = parse_json(primary_body)
    require(type(raw) is dict and set(raw) == {'gpuQuota', 'tpuQuota', 'quotaRefreshTime'},
            'closed primary quota response required')
    gpu = raw['gpuQuota']
    _quota_object(gpu, required=True)
    _quota_object(raw['tpuQuota'], required=False)
    require(type(typed) is dict and set(typed) == {'gpu_used_seconds', 'gpu_reserved_seconds',
        'gpu_total_seconds', 'gpu_pay_to_scale_enabled'}, 'closed typed quota projection required')
    refresh = timestamp(raw['quotaRefreshTime'])
    require(refresh > at, 'quota window already ended before observation')
    reconcile_quota(raw, typed)
    # The cross-check permits microsecond rounding differences. Normalize with
    # conservative min(total)/max(used,reserved) so the output is internally
    # coherent and can never resurrect the tolerated difference as free quota.
    used = max(_primary_duration(gpu['timeUsed']), typed['gpu_used_seconds'])
    reserved = max(_primary_duration(gpu['timeReserved']), typed['gpu_reserved_seconds'])
    total = min(_primary_duration(gpu['totalTimeAllowed']), typed['gpu_total_seconds'])
    remaining = finite(total - used - reserved)
    return {'format': 'irisx/stage4-quota-observation-v1', 'provider': 'kaggle',
        'account': account, 'observed_at': at.isoformat(), 'refresh_at': refresh.isoformat(),
        'primary_sha256': sha(primary_body), 'typed_projection_sha256': sha(canonical(typed)),
        'used_seconds': used, 'reserved_seconds': reserved, 'total_seconds': total,
        'remaining_free_seconds': remaining, 'pay_to_scale_enabled': False,
        'duration_units': 'provider charged quota seconds', 'permission_granted': False}


def ledger_quota(snapshot_body, *, expected_account, now):
    """Bind the ledger's bounded projection to one current normalized snapshot."""
    require(type(snapshot_body) is bytes, 'snapshot bytes required')
    require(type(expected_account) is str and re.fullmatch('[a-z0-9_-]{1,64}', expected_account),
            'exact authenticated account slug required')
    value = parse_json(snapshot_body)
    fields = {'format', 'provider', 'account', 'observed_at', 'refresh_at', 'primary_sha256',
        'typed_projection_sha256', 'used_seconds', 'reserved_seconds', 'total_seconds',
        'remaining_free_seconds', 'pay_to_scale_enabled', 'duration_units', 'permission_granted'}
    require(type(value) is dict and set(value) == fields and value['format'] == 'irisx/stage4-quota-observation-v1'
            and value['provider'] == 'kaggle' and value['account'] == expected_account
            and value['pay_to_scale_enabled'] is False and value['permission_granted'] is False
            and value['duration_units'] == 'provider charged quota seconds', 'foreign or unsafe quota snapshot')
    for key in ('primary_sha256', 'typed_projection_sha256'):
        require(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}', value[key]), 'quota evidence hash required')
    for key in ('used_seconds', 'reserved_seconds', 'total_seconds', 'remaining_free_seconds'):
        finite(value[key])
    require(abs(value['total_seconds'] - value['used_seconds'] - value['reserved_seconds']
                - value['remaining_free_seconds']) <= 1e-6, 'quota arithmetic differs')
    current = timestamp(now)
    require(0 <= (current - timestamp(value['observed_at'])).total_seconds() <= 900
            and current < timestamp(value['refresh_at']), 'fresh current-window quota required')
    return {'snapshot_sha256': sha(snapshot_body), 'observed_at': value['observed_at'],
            'remaining_free_seconds': value['remaining_free_seconds'], 'pay_to_scale_enabled': False}


def execution_source_digest(notebook):
    """Hash executable cells explicitly, not provider reformatted notebook bytes."""
    require(type(notebook) is dict and type(notebook.get('nbformat')) is int
            and notebook['nbformat'] == 4 and type(notebook.get('cells')) is list
            and 0 < len(notebook['cells']) <= 64, 'bounded notebook v4 required')
    cells = []
    for cell in notebook['cells']:
        require(type(cell) is dict and cell.get('cell_type') in ('code', 'markdown'),
                'only code and non-executable documentation cells admitted')
        source = cell.get('source')
        require(type(source) is str or (type(source) is list and all(type(s) is str for s in source)),
                'literal notebook source required')
        source = source if type(source) is str else ''.join(source)
        require(len(source.encode()) <= 16 * 1024 * 1024, 'bounded source cell required')
        if cell['cell_type'] == 'code':
            cells.append(source)
    require(bool(cells), 'at least one executable code cell required')
    return sha(canonical({'nbformat': 4, 'ordered_code_cells': cells}))


def validate_current_kernel(metadata, notebook, *, expected_identity, expected_source_digest):
    """Check source/version/settings before and after a current-version SDK read.

    Some older explicit numeric-version APIs were denied. This does not retry or
    bypass those endpoints. The eventual controller must use the supported read
    path initially, retain this observed-version evidence, and stop on a denial.
    The status SDK does not echo a version, so an isolated status response alone
    never proves which saved version it describes.
    """
    require(type(expected_identity) is dict and set(expected_identity) == {'kernel_id', 'version'}
            and type(expected_identity['kernel_id']) is str
            and re.fullmatch(r'[a-z0-9_-]+/[a-z0-9_-]+', expected_identity['kernel_id'])
            and type(expected_identity['version']) is int and expected_identity['version'] > 0,
            'exact expected kernel/version required')
    require(type(metadata) is dict, 'provider metadata projection required')
    required = {'kernel_id', 'version', 'private', 'internet', 'gpu', 'tpu', 'machine_shape'}
    require(set(metadata) == required and metadata['kernel_id'] == expected_identity['kernel_id']
            and type(metadata['version']) is int and metadata['version'] == expected_identity['version']
            and metadata['private'] is True and metadata['internet'] is False
            and metadata['gpu'] is True and metadata['tpu'] is False
            and metadata['machine_shape'] == 'NvidiaL4', 'observed source version/settings differ')
    require(type(expected_source_digest) is str and re.fullmatch('[0-9a-f]{64}', expected_source_digest),
            'exact admitted executable source digest required')
    require(execution_source_digest(notebook) == expected_source_digest, 'provider executable source differs')
    return {'identity': dict(expected_identity), 'source_digest': expected_source_digest,
            'settings_verified': True, 'metadata_sha256': sha(canonical(metadata)),
            'binding_kind': 'observed current metadata and ordered executable source'}


def normalize_status(typed_name, *, before, after):
    """Require consistent bracketing observations; never invent default success."""
    fields = {'identity', 'source_digest', 'settings_verified', 'metadata_sha256', 'binding_kind'}
    require(type(before) is dict and type(after) is dict and set(before) == fields
            and canonical(before) == canonical(after) and before.get('settings_verified') is True
            and before.get('binding_kind') == 'observed current metadata and ordered executable source',
            'stable exact-source/version observations required around status read')
    identity = before['identity']
    require(type(identity) is dict and set(identity) == {'kernel_id', 'version'}
            and type(identity['kernel_id']) is str
            and re.fullmatch(r'[a-z0-9_-]+/[a-z0-9_-]+', identity['kernel_id'])
            and type(identity['version']) is int and identity['version'] > 0,
            'typed exact observed identity required')
    for key in ('source_digest', 'metadata_sha256'):
        require(type(before[key]) is str and re.fullmatch('[0-9a-f]{64}', before[key]), 'exact observation hash required')
    states = {'QUEUED': 'queued', 'RUNNING': 'running', 'COMPLETE': 'complete',
              'ERROR': 'error', 'CANCEL_ACKNOWLEDGED': 'cancelled'}
    require(type(typed_name) is str and typed_name in states, 'unknown provider state remains pending')
    return {'identity': dict(before['identity']), 'status': states[typed_name],
            'source_digest': before['source_digest'], 'notebook_exit_inferred': False,
            'official_score': None, 'permission_granted': False}

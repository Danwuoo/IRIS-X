"""Typed E13 admission, using only the standard library.

Default INERT packages require an actual owner's config declaration. A separate
explicit RUN admission binds the exact chat authorization, historical provider
quota observation and policy; its runtime receipt never invents owner actions.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

RUN_ID = 'stage4-e13-search-budget-20261008-001'
BUDGET_PROFILE = 'conservative-60min-inert'
RUN_BUDGET_PROFILE = 'bounded-60min-run'
RUN_START_FILE = 'e13-agent-run-start.json'
AUTHORIZATION_REF = 'Sentinel_4b0cec11ab188191abe81f31076ec619'
CONSERVATIVE_POLICY = 'conservative-four-gpu-hours-v1'
WAIVER_POLICY = 'owner-positive-free-quota-waiver-v1'
RUN_TRUE_FIELDS = {'approved_for_runtime', 'agent_execution_authorized', 'publication_authorized'}
CONFIG_NAME = 'E13_CONFIRM_RUN_001'
CONFIRMATION_FILE = 'e13-owner-confirmation.json'
FORMAT = 'irisx/e13-owner-config-confirmation-v1'
FALSE_FIELDS = ('approved_for_runtime', 'approved_for_owner_editor',
    'agent_execution_authorized', 'publication_authorized',
    'official_submission_authorized', 'official_submission_ready',
    'correctness_scored', 'promotion', 'official_submission',
    'full_screen_feasibility_established', 'causal_quality_comparison',
    'full_E10_first_six_controls_replaced')
NO_RUN = ('No run started. Review the exact E13 run001 native stack, workload and '
    'quota instructions above; only then set E13_CONFIRM_RUN_001 = True and run '
    'all cells. No setup, native imports or worker processes have started.')
SCOPE_FIELDS = ('run_id', 'source_commit', 'model_material_digest',
    'dependency_readproof_digest', 'dependency_script_version_id', 'arm_contracts',
    'arm_order', 'task_order', 'test_counts', 'optimizer_steps',
    'maximum_training_forwards', 'maximum_training_backwards',
    'maximum_training_input_tokens', 'maximum_training_supervised_tokens',
    'maximum_generation_forwards', 'maximum_verification_forwards',
    'maximum_inference_input_tokens', 'maximum_processed_sequences_total',
    'generation_seconds', 'per_test_seconds', 'maximum_notebook_wall_seconds',
    'maximum_training_seconds', 'startup_seconds', 'reset_reserve_seconds',
    'finalization_reserve_seconds', 'inference_reserve_seconds',
    'e13_process_policy', 'source_replay_policy')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return 'sha256:' + hashlib.sha256(canonical(value)).hexdigest()


def parse(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate E13 JSON key')
            result[key] = value
        return result
    value = json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('finite JSON required')))
    canonical(value)
    return value


def scope(plan):
    require(type(plan) is dict and
        plan.get('run_id') == plan.get('screen_id') == RUN_ID and
        plan.get('resource_budget_profile') == (RUN_BUDGET_PROFILE if is_run(plan) else BUDGET_PROFILE) and
        type(plan.get('source_commit')) is str and
        re.fullmatch('[0-9a-f]{40}', plan['source_commit']) and
        plan.get('kernel_execution_type') in ('INERT', 'RUN') and
        (is_run(plan) or plan.get('resource_admission') is None) and
        plan.get('owner_editor_only') is (not is_run(plan)) and plan.get('local_fixture') is False and
        all(plan.get(key) is (is_run(plan) and key in RUN_TRUE_FIELDS) for key in FALSE_FIELDS) and
        all(type(plan.get(key)) is int and plan[key] == value for key, value in (
            ('maximum_notebook_wall_seconds', 3600), ('optimizer_steps', 512),
            ('maximum_training_forwards', 512), ('maximum_training_backwards', 512),
            ('per_worker_training_steps', 128), ('expected_notebook_version', 12),
            ('notebook_numeric_id', 137327571))),
        'exact E13 run001, unchanged 60-minute workload and typed admission mode required')
    return {key: plan[key] for key in SCOPE_FIELDS}


def admission(plan):
    require(not is_run(plan), 'INERT owner config contract cannot authorize automatic RUN')
    return dict(format='irisx/e13-owner-config-admission-v1', run_id=RUN_ID,
        config_name=CONFIG_NAME, default_config_value=False,
        confirmation_file=CONFIRMATION_FILE, exact_scope_digest=digest(scope(plan)),
        publication_authorized=False, publication_authorization_ref=None,
        agent_execution_authorized=False, runtime_authorized=False,
        execution_chat_ref=None, minimum_owner_declared_free_gpu_hours=4,
        mode='INERT; owner may explicitly enable this exact run once in a fresh Editor session',
        resource_information='owner declarations only; no independent quota or provider Editor timeout attestation')


def declarations(plan):
    require(not is_run(plan), 'automatic RUN cannot fabricate owner-edited config declarations')
    return dict(format=FORMAT, run_id=RUN_ID, plan_digest=digest(plan),
        source_commit=plan['source_commit'], exact_scope_digest=digest(scope(plan)),
        config_name=CONFIG_NAME, confirmed_by='owner-edited-notebook-config',
        owner_enabled_exact_run=True, owner_declared_fresh_session=True,
        owner_declared_single_attempt=True, owner_declared_minimum_free_gpu_hours=4,
        owner_declared_no_conflicting_reservation=True,
        owner_declared_pay_to_scale_disabled=True,
        owner_accepted_original_native_stack=True,
        owner_declared_stop_editor_after_download=True,
        publication_authorized=False, publication_authorization_ref=None,
        execution_chat_ref=None, agent_execution_authorized=False,
        quota_independently_verified=False, provider_editor_timeout_attested=False)


def write_confirmation(root, plan, confirmed, started_monotonic, *,
                       now=time.time, monotonic=time.monotonic):
    require(type(confirmed) is bool and confirmed is True,
        'owner exact-run config must be literal True')
    require(type(started_monotonic) in (int, float) and math.isfinite(started_monotonic)
        and 0 <= started_monotonic <= monotonic(), 'actual notebook start clock required')
    require(canonical(plan.get('owner_editor_admission')) == canonical(admission(plan)),
        'exact optional E13 owner configuration contract required')
    value = dict(declarations(plan), confirmed_epoch=now(), started_monotonic=started_monotonic)
    require(type(value['confirmed_epoch']) in (int, float) and
        math.isfinite(value['confirmed_epoch']) and value['confirmed_epoch'] >= 0,
        'finite actual owner confirmation clock required')
    path = Path(root) / CONFIRMATION_FILE
    require(not any(p.is_symlink() for p in (path, *path.parents)),
        'regular exclusive E13 owner confirmation required')
    with path.open('xb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    return value


def verify_confirmation(root, plan, *, current=True, now=time.time, monotonic=time.monotonic):
    path = Path(root) / CONFIRMATION_FILE
    require(not any(p.is_symlink() for p in (path, *path.parents)) and
        path.is_file() and path.stat().st_size <= 16 * 1024,
        'bounded regular E13 owner config confirmation required before runtime')
    value = parse(path.read_bytes()); expected = declarations(plan)
    require(canonical(plan.get('owner_editor_admission')) == canonical(admission(plan)),
        'exact E13 owner admission declaration required')
    require(type(value) is dict and set(value) == set(expected) | {'confirmed_epoch', 'started_monotonic'} and
        all(type(value.get(key)) is type(item) and value[key] == item for key, item in expected.items()) and
        all(type(value[key]) in (int, float) and math.isfinite(value[key]) and value[key] >= 0
            for key in ('confirmed_epoch', 'started_monotonic')),
        'exact typed E13 owner declaration, plan, source and native scope required')
    if current:
        require(0 <= now() - value['confirmed_epoch'] <= 3600 and
            0 <= monotonic() - value['started_monotonic'] <= 3600,
            'E13 owner confirmation belongs to this fresh bounded session only')
    return value


def is_run(plan):
    return type(plan) is dict and plan.get('kernel_execution_type') == 'RUN'


def _timestamp(value):
    require(type(value) is str, 'timezone-qualified quota timestamp required')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(stamp.utcoffset() is not None, 'timezone-qualified quota timestamp required')
    return stamp.timestamp()


def validate_resource_snapshot(value, *, current=True, now=time.time):
    """Validate the exact normalized provider projection; no permission is inferred.

    This standard-library projection matches stage4_provider_evidence. The
    authenticated publisher must retain and independently reconcile both raw
    primary and typed responses; caller-supplied hashes do not authenticate them.
    Freshness belongs to submission, never a fictitious offline runtime refresh.
    """
    fields = {'format', 'provider', 'account', 'observed_at', 'refresh_at', 'primary_sha256',
        'typed_projection_sha256', 'used_seconds', 'reserved_seconds', 'total_seconds',
        'remaining_free_seconds', 'pay_to_scale_enabled', 'duration_units', 'permission_granted'}
    require(type(value) is dict and set(value) == fields and
        value['format'] == 'irisx/stage4-quota-observation-v1' and value['provider'] == 'kaggle' and
        value['account'] == 'danielwuu' and value['pay_to_scale_enabled'] is False and
        value['permission_granted'] is False and value['duration_units'] == 'provider charged quota seconds',
        'exact authenticated account and paid-disabled normalized quota required')
    require(all(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}', value[k])
        for k in ('primary_sha256', 'typed_projection_sha256')), 'raw and typed quota evidence hashes required')
    require(all(type(value[k]) in (int, float) and math.isfinite(value[k]) and value[k] >= 0
        for k in ('used_seconds', 'reserved_seconds', 'total_seconds', 'remaining_free_seconds')) and
        value['reserved_seconds'] == 0 and value['remaining_free_seconds'] > 0 and
        abs(value['total_seconds'] - value['used_seconds'] - value['reserved_seconds'] -
            value['remaining_free_seconds']) <= 1e-6,
        'real positive free quota and no conflicting provider reservation required')
    observed, refresh = _timestamp(value['observed_at']), _timestamp(value['refresh_at'])
    require(0 <= observed < refresh, 'quota observation must precede its refresh')
    if current:
        stamp = now()
        require(type(stamp) in (int, float) and math.isfinite(stamp) and
            0 <= stamp - observed <= 900 and stamp < refresh,
            'submission quota must be fresh within 900 seconds and current window')
    return value


def run_admission(plan, resource_snapshot, authorization_ref, *, quota_policy=CONSERVATIVE_POLICY,
                  current=True, now=time.time):
    require(is_run(plan) and authorization_ref == AUTHORIZATION_REF and
        type(authorization_ref) is str, 'exact owner authorization for distinct automatic RUN required')
    validate_resource_snapshot(resource_snapshot, current=current, now=now)
    require(quota_policy in (CONSERVATIVE_POLICY, WAIVER_POLICY), 'explicit recognized quota policy required')
    require(quota_policy == WAIVER_POLICY or resource_snapshot['remaining_free_seconds'] >= 14400,
        'conservative four-GPU-hour rule requires explicit per-run owner waiver below four hours')
    return dict(format='irisx/e13-automatic-run-admission-v1', run_id=RUN_ID,
        authorization_ref=authorization_ref, exact_scope_digest=digest(scope(plan)),
        resource_snapshot=parse(canonical(resource_snapshot)), resource_snapshot_digest=digest(resource_snapshot),
        quota_policy=quota_policy, conservative_required_quota_seconds=14400,
        allocated_gpu_hours_per_quota_hour=1, quota_rate_is_conservative_planning_assumption=True,
        quota_rate_independently_verified=False, conservative_reservation_waived=quota_policy == WAIVER_POLICY,
        minimum_positive_free_quota_required=True, paid_usd_ceiling=0,
        quota_observation_role='historical submission observation; not current offline-runtime quota',
        provider_may_reject_or_terminate=True, completion_guaranteed=False,
        owner_edited_notebook_config=False, owner_minimum_four_hour_declaration=False)


def validate_plan(plan, *, current_resource=False, now=time.time):
    scope(plan)
    if is_run(plan):
        value = plan.get('resource_admission')
        require(type(value) is dict and plan.get('owner_editor_admission') is None,
            'RUN requires separate resource admission and no owner-Editor declaration')
        expected = run_admission(plan, value.get('resource_snapshot'), value.get('authorization_ref'),
            quota_policy=value.get('quota_policy'), current=current_resource, now=now)
        require(canonical(value) == canonical(expected), 'exact typed RUN admission and scope binding required')
    else:
        require(canonical(plan.get('owner_editor_admission')) == canonical(admission(plan)),
            'exact INERT owner declaration contract required')
    return plan


def run_start_fields(plan):
    validate_plan(plan)
    require(is_run(plan), 'automatic run receipt cannot admit INERT packages')
    value = plan['resource_admission']
    return dict(format='irisx/e13-automatic-run-start-v1', run_id=RUN_ID,
        plan_digest=digest(plan), source_commit=plan['source_commit'],
        exact_scope_digest=digest(scope(plan)), resource_admission_digest=digest(value),
        resource_snapshot_digest=value['resource_snapshot_digest'], authorization_ref=value['authorization_ref'],
        quota_policy=value['quota_policy'], mode='agent-automatic-RUN',
        owner_edited_notebook_config=False, owner_minimum_four_hour_declaration=False,
        quota_current_at_runtime=False, provider_hardware_verified_at_start=False)


def verify_start_value(value, plan, *, current=True, now=time.time, monotonic=time.monotonic):
    expected = run_start_fields(plan)
    require(type(value) is dict and set(value) == set(expected) | {'started_epoch', 'started_monotonic'} and
        all(type(value.get(k)) is type(v) and value[k] == v for k, v in expected.items()) and
        all(type(value[k]) in (int, float) and math.isfinite(value[k]) and value[k] >= 0
            for k in ('started_epoch', 'started_monotonic')), 'exact honest RUN start receipt required')
    if current:
        require(0 <= now() - value['started_epoch'] <= 3600 and
            0 <= monotonic() - value['started_monotonic'] <= 3600,
            'RUN receipt belongs to this actual bounded session only')
    return value


def write_run_start(root, plan, started_monotonic, *, now=time.time, monotonic=time.monotonic):
    require(type(started_monotonic) in (int, float) and math.isfinite(started_monotonic) and
        0 <= started_monotonic <= monotonic(), 'actual automatic run start clock required')
    value = dict(run_start_fields(plan), started_epoch=now(), started_monotonic=started_monotonic)
    verify_start_value(value, plan, now=now, monotonic=monotonic)
    path = Path(root) / RUN_START_FILE
    require(not any(p.is_symlink() for p in (path, *path.parents)) and
        not (Path(root) / CONFIRMATION_FILE).exists(), 'fresh exclusive RUN receipt without owner declarations required')
    require(bool(getattr(os, 'O_NOFOLLOW', 0)), 'no-follow RUN receipt creation required')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    return value


def verify_execution(root, plan, *, current=True, now=time.time, monotonic=time.monotonic):
    validate_plan(plan)
    if not is_run(plan):
        return verify_confirmation(root, plan, current=current, now=now, monotonic=monotonic)
    path = Path(root) / RUN_START_FILE
    require(not any(p.is_symlink() for p in (path, *path.parents)) and
        not (Path(root) / CONFIRMATION_FILE).exists(), 'regular RUN receipt and absent owner confirmation required')
    raw = read_regular(path, maximum=16384)
    value = parse(raw)
    require(raw == canonical(value), 'canonical RUN receipt required')
    return verify_start_value(value, plan, current=current, now=now, monotonic=monotonic)


def read_regular(path, *, maximum=8 * 1024**2):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)) and
        bool(getattr(os, 'O_NOFOLLOW', 0)), 'regular no-follow E13 path required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= maximum,
            'bounded singly linked regular E13 file required')
        body = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        require(len(body) == before.st_size and len(body) <= maximum and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            'E13 file changed during admission read')
    return body


def read_plan(root):
    root = Path(root)
    body = read_regular(root / 'plan.json', maximum=1024**2)
    plan = parse(body)
    require(body == canonical(plan) == read_regular(root / 'screen.json', maximum=1024**2),
        'identical canonical bounded E13 plan and screen required')
    validate_plan(plan)
    return plan


def verify_payload(root, plan):
    """Check every staged payload before importing any runtime/native module."""
    root = Path(root)
    payload, sources = plan.get('payload_sha256'), plan.get('source_files_sha256')
    require(type(payload) is dict and type(sources) is dict and 0 < len(payload) <= 4096 and
        set(sources) <= set(payload) and not {'plan.json', 'screen.json', RUN_START_FILE, CONFIRMATION_FILE} & set(payload) and
        {'tools/nvarc_e13_admission.py', 'tools/nvarc_e13_entry.py',
         'tools/stage_nvarc_e13_search_budget.py', 'tools/nvarc_e13_runtime.py',
         'tools/nvarc_e13_delivery_envelope.py'} <= set(sources), 'closed admission/runtime source inventory required')
    require(len({name.casefold() for name in payload}) == len(payload), 'unique E13 payload paths required')
    total = 0
    for name, expected in payload.items():
        require(type(name) is str and 0 < len(name) <= 240 and not name.startswith('/') and
            '\\' not in name and ':' not in name and
            all(p not in ('', '.', '..') for p in name.split('/')) and
            not any(ord(c) < 32 or ord(c) == 127 for c in name) and
            type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected), 'safe E13 payload digest/path required')
        body = read_regular(root / name)
        total += len(body)
        require(total <= 512 * 1024**2 and hashlib.sha256(body).hexdigest() == expected,
            'exact immutable E13 payload differs before runtime imports: ' + name)
    require(all(sources[name] == payload[name] for name in sources), 'source/payload binding differs')
    return plan

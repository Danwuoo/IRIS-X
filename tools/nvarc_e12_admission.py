"""Exact E12 owner opt-in declarations. This module uses only the standard library.

Staged packages grant neither publication nor agent execution authority. The
optional sidecar records a person's declarations; it never attests provider
quota, paid settings, or a provider-enforced Editor timeout.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

RUN_ID = 'stage4-e12-probe-prefix-20261007-001'
BUDGET_PROFILE = 'conservative-60min-inert'
CONFIG_NAME = 'E12_CONFIRM_RUN_001'
CONFIRMATION_FILE = 'e12-owner-confirmation.json'
FORMAT = 'irisx/e12-owner-config-confirmation-v1'
FALSE_FIELDS = ('approved_for_runtime', 'approved_for_owner_editor',
    'agent_execution_authorized', 'publication_authorized',
    'official_submission_authorized', 'official_submission_ready',
    'correctness_scored', 'promotion', 'official_submission',
    'full_screen_feasibility_established', 'causal_quality_comparison',
    'full_E10_first_six_controls_replaced')
NO_RUN = ('No run started. Review the exact E12 run001 native stack, workload and '
    'quota instructions above; only then set E12_CONFIRM_RUN_001 = True and run '
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
    'e12_process_policy', 'source_replay_policy')


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
            require(key not in result, 'duplicate E12 JSON key')
            result[key] = value
        return result
    value = json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('finite JSON required')))
    canonical(value)
    return value


def scope(plan):
    require(type(plan) is dict and
        plan.get('run_id') == plan.get('screen_id') == RUN_ID and
        plan.get('resource_budget_profile') == BUDGET_PROFILE and
        type(plan.get('source_commit')) is str and
        re.fullmatch('[0-9a-f]{40}', plan['source_commit']) and
        plan.get('kernel_execution_type') == 'INERT' and
        plan.get('resource_admission') is None and
        plan.get('owner_editor_only') is True and plan.get('local_fixture') is False and
        all(plan.get(key) is False for key in FALSE_FIELDS) and
        all(type(plan.get(key)) is int and plan[key] == value for key, value in (
            ('maximum_notebook_wall_seconds', 3600), ('optimizer_steps', 768),
            ('maximum_training_forwards', 768), ('maximum_training_backwards', 768),
            ('per_worker_training_steps', 192), ('expected_notebook_version', 10),
            ('notebook_numeric_id', 137327571))),
        'exact INERT E12 run001, 60-minute profile and disabled publication/agent authority required')
    return {key: plan[key] for key in SCOPE_FIELDS}


def admission(plan):
    return dict(format='irisx/e12-owner-config-admission-v1', run_id=RUN_ID,
        config_name=CONFIG_NAME, default_config_value=False,
        confirmation_file=CONFIRMATION_FILE, exact_scope_digest=digest(scope(plan)),
        publication_authorized=False, publication_authorization_ref=None,
        agent_execution_authorized=False, runtime_authorized=False,
        execution_chat_ref=None, minimum_owner_declared_free_gpu_hours=4,
        mode='INERT; owner may explicitly enable this exact run once in a fresh Editor session',
        resource_information='owner declarations only; no independent quota or provider Editor timeout attestation')


def declarations(plan):
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
        'exact optional E12 owner configuration contract required')
    value = dict(declarations(plan), confirmed_epoch=now(), started_monotonic=started_monotonic)
    require(type(value['confirmed_epoch']) in (int, float) and
        math.isfinite(value['confirmed_epoch']) and value['confirmed_epoch'] >= 0,
        'finite actual owner confirmation clock required')
    path = Path(root) / CONFIRMATION_FILE
    require(not any(p.is_symlink() for p in (path, *path.parents)),
        'regular exclusive E12 owner confirmation required')
    with path.open('xb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    return value


def verify_confirmation(root, plan, *, current=True, now=time.time, monotonic=time.monotonic):
    path = Path(root) / CONFIRMATION_FILE
    require(not any(p.is_symlink() for p in (path, *path.parents)) and
        path.is_file() and path.stat().st_size <= 16 * 1024,
        'bounded regular E12 owner config confirmation required before runtime')
    value = parse(path.read_bytes()); expected = declarations(plan)
    require(canonical(plan.get('owner_editor_admission')) == canonical(admission(plan)),
        'exact E12 owner admission declaration required')
    require(type(value) is dict and set(value) == set(expected) | {'confirmed_epoch', 'started_monotonic'} and
        all(type(value.get(key)) is type(item) and value[key] == item for key, item in expected.items()) and
        all(type(value[key]) in (int, float) and math.isfinite(value[key]) and value[key] >= 0
            for key in ('confirmed_epoch', 'started_monotonic')),
        'exact typed E12 owner declaration, plan, source and native scope required')
    if current:
        require(0 <= now() - value['confirmed_epoch'] <= 3600 and
            0 <= monotonic() - value['started_monotonic'] <= 3600,
            'E12 owner confirmation belongs to this fresh bounded session only')
    return value

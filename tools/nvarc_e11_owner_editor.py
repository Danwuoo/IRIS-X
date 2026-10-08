"""Exact E11 owner-edited confirmation contract; standard library only.

Publication consent does not grant execution. The sidecar records a human's
self-reported config choice, never provider quota or runtime attestation.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import time

RUN_ID='stage4-e11-probe-paired-dfs-floor-20261007-003'
BUDGET_PROFILE='owner-editor-45min-v9'
CONFIG_NAME='E11_CONFIRM_RUN_003'
CONFIRMATION_FILE='owner-editor-confirmation.json'
PUBLICATION_REF='Sentinel_f9098b5538e48191bfe94c278bfa6107'
FORMAT='irisx/e11-owner-editor-config-confirmation-v1'
NO_RUN='No run started. Review the exact run003 stack, workload and quota instructions above; only then set E11_CONFIRM_RUN_003 = True and run all cells. No setup, native imports or worker processes have started.'
SCOPE_FIELDS=('run_id','source_commit','model_material_digest','dependency_readproof_digest',
    'dependency_script_version_id','arm_contracts','arm_order','task_order','test_counts','optimizer_steps',
    'maximum_training_forwards','maximum_training_backwards','maximum_training_input_tokens',
    'maximum_training_supervised_tokens','maximum_generation_forwards','maximum_verification_forwards',
    'maximum_inference_input_tokens','maximum_processed_sequences_total','generation_seconds','per_test_seconds',
    'maximum_notebook_wall_seconds','maximum_training_seconds','startup_seconds','reset_reserve_seconds',
    'finalization_reserve_seconds','inference_reserve_seconds','e11_process_policy','source_replay_policy')


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def digest(value):return 'sha256:'+hashlib.sha256(canonical(value)).hexdigest()


def require(ok,message):
    if not ok:raise RuntimeError(message)


def parse(body):
    def pairs(rows):
        value={}
        for key,item in rows:
            require(key not in value,'duplicate owner-Editor JSON key')
            value[key]=item
        return value
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('finite JSON required')))


def scope(plan):
    require(plan.get('run_id')==plan.get('screen_id')==RUN_ID and plan.get('resource_budget_profile')==BUDGET_PROFILE,
        'exact distinct owner-Editor E11 run003 required')
    return {key:plan[key] for key in SCOPE_FIELDS}


def admission(plan):
    return dict(format='irisx/e11-owner-editor-config-admission-v1',run_id=RUN_ID,
        publication_authorization_ref=PUBLICATION_REF,execution_chat_ref=None,
        config_name=CONFIG_NAME,default_config_value=False,confirmation_file=CONFIRMATION_FILE,
        exact_scope_digest=digest(scope(plan)),agent_execution_authorized=False,
        mode='QUICK_SAVE; owner manually sets exact-run config True before Run All',
        resource_information='owner declarations only; no independent quota or provider Editor timeout attestation')


def declarations(plan):
    return dict(format=FORMAT,run_id=RUN_ID,plan_digest=digest(plan),source_commit=plan['source_commit'],
        exact_scope_digest=digest(scope(plan)),config_name=CONFIG_NAME,
        confirmed_by='owner-edited-notebook-config',owner_enabled_exact_run=True,
        owner_declared_fresh_session=True,owner_declared_single_attempt=True,
        owner_declared_free_quota_sufficient=True,owner_declared_pay_to_scale_disabled=True,
        owner_accepted_original_native_stack=True,owner_declared_stop_editor_after_download=True,
        publication_authorization_ref=PUBLICATION_REF,execution_chat_ref=None,
        agent_execution_authorized=False,quota_independently_verified=False,
        provider_editor_timeout_attested=False)


def write_confirmation(root,plan,confirmed,started_monotonic,*,now=time.time,monotonic=time.monotonic):
    require(type(confirmed) is bool and confirmed is True,'owner exact-run config must be literal True')
    require(type(started_monotonic) in (int,float) and math.isfinite(started_monotonic) and
        0<=started_monotonic<=monotonic(),'actual notebook start clock required')
    value=dict(declarations(plan),confirmed_epoch=now(),started_monotonic=started_monotonic)
    path=Path(root)/CONFIRMATION_FILE
    require(not any(p.is_symlink() for p in (path,*path.parents)),'regular exclusive owner confirmation required')
    with path.open('xb') as stream:
        stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    return value


def verify_confirmation(root,plan,*,current=True,now=time.time,monotonic=time.monotonic):
    path=Path(root)/CONFIRMATION_FILE
    require(not any(p.is_symlink() for p in (path,*path.parents)) and path.is_file() and path.stat().st_size<=16*1024,
        'bounded regular owner config confirmation required before runtime')
    value=parse(path.read_bytes());expected=declarations(plan)
    require(type(value) is dict and set(value)==set(expected)|{'confirmed_epoch','started_monotonic'} and
        all(type(value.get(key)) is type(item) and value[key]==item for key,item in expected.items()) and
        all(type(value[key]) in (int,float) and math.isfinite(value[key]) and value[key]>=0
            for key in ('confirmed_epoch','started_monotonic')),
        'exact typed owner declaration, plan, source and native-scope confirmation required')
    if current:
        require(0<=now()-value['confirmed_epoch']<=2700 and
            0<=monotonic()-value['started_monotonic']<=2700,
            'owner confirmation belongs to this fresh bounded session only')
    return value

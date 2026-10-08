"""Build a distinct INERT end-to-end calibration from already frozen bytes.

Standard library only. No tokenizer/model import, acquisition, authentication,
provider operation, training, GPU or scoring. An admitted rebuild requires an
explicit exact-run owner reference, independent review and fresh quota binding.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical,digest,require,write,validate_challenges
from tools.nvarc_native_submission import reject_truth
from tools.stage_nvarc_e10_ttt_probe import (FILES as TRAINING_FILES, TASKS, BOUNDS as TRAINING_BOUNDS,
    frozen_specs, construct as training_construct, verify_runtime as verify_training_runtime)
from tools.stage_nvarc_e10_screen import CONFIG_FIELDS, material_files, sha
from tools.nvarc_dependency_readproof import PROOF_FILE, read_contract, VERSIONED_REF
from tools.nvarc_resource_attachment import attachment
from tools.nvarc_e10_generation_profile import HISTORICAL, LONGER, PROFILES, profile, for_plan
from tools.nvarc_e10_future_budget import proposal as future_budget

FORMAT='irisx/stage4-e10-end-to-end-v1'
RUN_ID='stage4-e10-probe-end-to-end-20261007-002'
NOTEBOOK='danielwuu/stage4-e10-probe-20261006-001'
SCOPE='frozen public solver-visible development challenges only'
PARENT_PLAN_SHA256='97713c7d1dc992afc0ebcac6cc3b7ca4e548b56b3826ae19b8c1c73ee20f3842'
CHALLENGES_SHA256='90c0afaf7e942e7d16eb6660e4dd428316fa4ea38983b48e9e3912dcc65d8dc8'
INFERENCE_PLAN_SHA256='88d5c2420a13fd0c13807b8c59c0734764491620edaf256719028a41b224bc38'
TEST_COUNTS=dict(zip(TASKS,(2,1,1,2)))
NEW_FILES=('tools/stage_nvarc_e10_end_to_end.py','tools/nvarc_e10_end_to_end.py',
    'tools/nvarc_e10_answer_evidence.py','tools/nvarc_e10_answer_archive.py',
    'tools/nvarc_e10_generation_profile.py','tools/nvarc_e10_future_budget.py')
FILES=tuple(sorted(set(TRAINING_FILES)|set(NEW_FILES)))
BOUNDS={k:v for k,v in TRAINING_BOUNDS.items() if k!='generations'}
BOUNDS.update(maximum_generation_forwards=24576,maximum_verification_forwards=768,
    maximum_inference_input_tokens=31457280,maximum_processed_sequences_per_test=64,
    maximum_processed_sequences_total=384,per_test_seconds=30,generation_seconds=20,
    verification_reserve_seconds=10,inference_reserve_seconds=60,maximum_teacher_calls=0,maximum_formal_submissions=0,
    maximum_inference_ledger_bytes=8*1024**2,maximum_inference_event_bytes=1024**2)
FALSE_FIELDS=('approved_for_runtime','approved_for_owner_editor','agent_execution_authorized',
    'publication_authorized','official_submission_authorized','official_submission_ready',
    'correctness_scored','promotion','official_submission','full_screen_feasibility_established',
    'causal_quality_comparison','full_E10_first_six_controls_replaced')
ADMISSION='irisx/stage4-end-to-end-single-run-admission-v1'
RUNTIME_FLAGS={'approved_for_runtime','agent_execution_authorized','publication_authorized'}
ADMISSION_FIELDS={'format','run_id','owner_instruction_ref','notebook_ref','notebook_numeric_id',
    'expected_notebook_version','expected_previous_version','expected_previous_script_version_id',
    'kernel_execution_type','provider_session_seconds','private','internet','paid_usd_ceiling',
    'charged_quota_seconds_reserved','quota_snapshot_sha256','quota_observed_at',
    'remaining_free_seconds','provider_reserved_seconds','monitor_after_submission',
    'approved_inert_plan_digest','approved_inert_package_manifest_sha256','independent_review_sha256','source_commit'}
V7_ADMISSION='irisx/stage4-end-to-end-v7-single-run-admission-v1'
V7_OWNER='Sentinel_b687a3f522c88191a82295fbea450b74'
V7_BASELINE={
    'source_commit':'bbf951b7f5f890d95b1c9340e5abe1c142bd558f',
    'inert_plan_digest':'sha256:65965a869e6ccd2203d4d55e353ad81486f7eab3418a99b57d8fcbebde604169',
    'inert_package_manifest_sha256':'8fcc0dea59fdf776f21682ebd864da16f4701099c505cf5b42999009e29a1b16',
    'inert_notebook_sha256':'7f092fa12afe37275e0e1e2d1d712b0d372a8be550955012c4283456bdcc2c23',
    'independent_review_sha256':'b35f02930a16bae0a26e529a1ff8ffb25233a44c62ea8c4da90e391a9975edc5'}
V7_ADMISSION_FIELDS=ADMISSION_FIELDS|{'approved_v7_baseline','quota_snapshot_json','quota_checked_at'}
QUOTA_FIELDS={'format','provider','account','observed_at','refresh_at','primary_sha256',
    'typed_projection_sha256','used_seconds','reserved_seconds','total_seconds',
    'remaining_free_seconds','pay_to_scale_enabled','duration_units','permission_granted'}


def admission_timestamp(value):
    require(type(value) is str,'timezone-qualified admission timestamp required')
    try: result=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError: raise RuntimeError('timezone-qualified admission timestamp required') from None
    require(result.utcoffset() is not None,'timezone-qualified admission timestamp required')
    return result


def validate_v7_admission(plan,value):
    """Bind the approved scientific bytes and the separately reviewed new guard.

    The snapshot is fresh at the recorded admission check. The publisher must
    check its age again immediately before Save; queued runtime is not a new
    provider action and does not require the snapshot still to be recent.
    """
    require(type(value) is dict and set(value)==V7_ADMISSION_FIELDS and value['format']==V7_ADMISSION,
        'closed exact v7 run admission required')
    require(value['run_id']==plan['run_id']==profile(LONGER)['run_id'] and
        value['owner_instruction_ref']==V7_OWNER and value['notebook_ref']==plan.get('notebook_ref')==NOTEBOOK and
        type(plan.get('notebook_numeric_id')) is int and plan['notebook_numeric_id']==137327571 and
        value['kernel_execution_type']==plan.get('kernel_execution_type')=='SAVE_AND_RUN_ALL' and
        value['private'] is True and value['internet'] is value['monitor_after_submission'] is False and
        plan.get('owner_editor_only') is False and plan.get('local_fixture') is False and
        all(plan.get(k) is True for k in RUNTIME_FLAGS) and
        all(type(value[k]) is int and value[k]==v for k,v in (
            ('notebook_numeric_id',137327571),('expected_notebook_version',7),('expected_previous_version',6),
            ('expected_previous_script_version_id',355924733),('provider_session_seconds',3600),
            ('paid_usd_ceiling',0),('charged_quota_seconds_reserved',14400))) and
        type(value['approved_v7_baseline']) is dict and value['approved_v7_baseline']==V7_BASELINE and
        type(value['source_commit']) is str and re.fullmatch('[0-9a-f]{40}',value['source_commit']) and
        value['source_commit']==plan.get('source_commit') and value['source_commit']!=V7_BASELINE['source_commit'] and
        all(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}',value[k]) and value[k]!='0'*64 for k in
            ('quota_snapshot_sha256','approved_inert_package_manifest_sha256','independent_review_sha256')) and
        value['independent_review_sha256']!=V7_BASELINE['independent_review_sha256'] and
        type(value['approved_inert_plan_digest']) is str and re.fullmatch('sha256:[0-9a-f]{64}',value['approved_inert_plan_digest']),
        'exact new owner-approved private free version-seven source/review admission required')
    require(type(value['quota_snapshot_json']) is str and len(value['quota_snapshot_json'].encode())<=1024*1024,
        'bounded exact quota snapshot bytes required')
    body=value['quota_snapshot_json'].encode()
    require(hashlib.sha256(body).hexdigest()==value['quota_snapshot_sha256'],'quota snapshot byte binding differs')
    try: snapshot=parse_json(body)
    except (ValueError,TypeError): raise RuntimeError('closed exact quota snapshot JSON required') from None
    require(type(snapshot) is dict and set(snapshot)==QUOTA_FIELDS and
        snapshot['format']=='irisx/stage4-quota-observation-v1' and snapshot['provider']=='kaggle' and
        snapshot['account']=='danielwuu' and snapshot['duration_units']=='provider charged quota seconds' and
        snapshot['pay_to_scale_enabled'] is snapshot['permission_granted'] is False and
        all(type(snapshot[k]) is str and re.fullmatch('[0-9a-f]{64}',snapshot[k]) for k in
            ('primary_sha256','typed_projection_sha256')) and
        all(type(snapshot[k]) in (int,float) and math.isfinite(snapshot[k]) and snapshot[k]>=0 for k in
            ('used_seconds','reserved_seconds','total_seconds','remaining_free_seconds')) and
        all(type(value[k]) in (int,float) and math.isfinite(value[k]) for k in
            ('remaining_free_seconds','provider_reserved_seconds')) and
        value['quota_observed_at']==snapshot['observed_at'] and
        value['remaining_free_seconds']==snapshot['remaining_free_seconds']>=14400 and
        value['provider_reserved_seconds']==snapshot['reserved_seconds']==0 and
        abs(snapshot['total_seconds']-snapshot['used_seconds']-snapshot['reserved_seconds']-
            snapshot['remaining_free_seconds'])<=1e-6,
        'closed consistent sufficient unpaid exact-account quota observation required')
    observed=admission_timestamp(value['quota_observed_at']);checked=admission_timestamp(value['quota_checked_at'])
    require(0<=(checked-observed).total_seconds()<=900 and checked<admission_timestamp(snapshot['refresh_at']),
        'fresh current-window quota required at admission; recheck immediately before Save')
    inert=dict(plan,resource_admission=None,kernel_execution_type='INERT',**{k:False for k in RUNTIME_FLAGS})
    require(value['approved_inert_plan_digest']==digest(inert),'admission must bind the exact current reviewed inert plan')


def validate_admission(plan, *, required=False):
    selected=for_plan(plan)
    value=plan.get('resource_admission')
    require(plan.get('owner_editor_admission') is None and all(plan.get(k) is False for k in set(FALSE_FIELDS)-RUNTIME_FLAGS),
        'no owner-Editor, scoring, promotion or official authority can be inherited')
    if selected['profile_id']==LONGER:
        if value is None:
            require(plan.get('kernel_execution_type')=='INERT' and all(plan.get(k) is False for k in RUNTIME_FLAGS),
                'v7 remains INERT without the new exact v7 run admission')
            require(not required,'new exact v7 run approval has not been granted')
        else:validate_v7_admission(plan,value)
        return
    if value is None:
        require(all(plan.get(k) is False for k in RUNTIME_FLAGS) and plan.get('kernel_execution_type')=='INERT',
            'new calibration remains inert without an exact single-run admission')
        require(not required,'new end-to-end runtime admission has not been granted')
        return
    require(type(value) is dict and set(value)==ADMISSION_FIELDS and value['format']==ADMISSION and
        value['run_id']==RUN_ID and value['notebook_ref']==NOTEBOOK and
        value['kernel_execution_type']==plan.get('kernel_execution_type')=='SAVE_AND_RUN_ALL' and
        value['private'] is True and value['internet'] is value['monitor_after_submission'] is False and
        all(plan.get(k) is True for k in RUNTIME_FLAGS) and
        all(type(value[k]) is int and value[k]==v for k,v in (
            ('notebook_numeric_id',137327571),('expected_notebook_version',6),('expected_previous_version',5),
            ('expected_previous_script_version_id',355913407),('provider_session_seconds',3600),
            ('paid_usd_ceiling',0),('charged_quota_seconds_reserved',14400))) and
        all(type(value[k]) in (int,float) and math.isfinite(value[k]) for k in ('remaining_free_seconds','provider_reserved_seconds')) and
        value['remaining_free_seconds']>=14400 and value['provider_reserved_seconds']==0 and
        value['owner_instruction_ref'] == 'Sentinel_f3562a99e4c08191aa38e0d9461e6641' and
        all(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}',value[k]) for k in
            ('quota_snapshot_sha256','approved_inert_package_manifest_sha256','independent_review_sha256')) and
        type(value['approved_inert_plan_digest']) is str and re.fullmatch('sha256:[0-9a-f]{64}',value['approved_inert_plan_digest']) and
        value['source_commit']==plan['source_commit'] and type(value['quota_observed_at']) is str and
        datetime.fromisoformat(value['quota_observed_at']).utcoffset() is not None,
        'exact owner-approved private free version-six admission/quota/source/review required')
    inert=dict(plan,resource_admission=None,kernel_execution_type='INERT',**{k:False for k in RUNTIME_FLAGS})
    require(value['approved_inert_plan_digest']==digest(inert),'admission must bind the exact reviewed inert plan')


def exact_sources(source_commit, *, repository=ROOT):
    require(re.fullmatch('[0-9a-f]{40}',source_commit or ''),'full immutable source commit required')
    result={}
    for name in FILES:
        path=Path(repository)/name
        require(not path.is_symlink(),'regular source file required')
        body=subprocess.run(['git','show',source_commit+':'+name],cwd=repository,capture_output=True,check=True).stdout
        require(body==path.read_bytes(),'exact committed implementation required: '+name)
        ast.parse(body,filename=name); result[name]=body
    return result


def native_symbol_guard(sources):
    """Fail at build/import time if the known deferred native symbols vanish."""
    module=ast.parse(sources['tools/nvarc_public_eval_runtime.py'])
    classes={n.name:n for n in module.body if isinstance(n,ast.ClassDef)}
    require({'NativeEngine','LightModel'}<=set(classes),'proven native engine/adapter required')
    native=classes['NativeEngine']; methods={n.name for n in native.body if isinstance(n,ast.FunctionDef)}
    require({'__init__','adapter','trainer','restore','inference','inventory'}<=methods,'complete native lifecycle required')
    imports={alias.asname or alias.name for n in ast.walk(native) if isinstance(n,ast.ImportFrom) for alias in n.names}
    require({'FastLanguageModel','UnslothTrainer','UnslothTrainingArguments','DataCollatorForLanguageModeling',
        'get_peft_model_state_dict','set_peft_model_state_dict','Dataset'}<=imports,
        'deferred native training/import symbol closure differs')
    for filename in NEW_FILES:
        tree=ast.parse(sources[filename],filename=filename)
        for node in tree.body:
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]]
                require(not set(names)&{'torch','numpy','tokenizers','unsloth','transformers','peft'},
                    'native dependencies cannot import before admission')


def construct(source_commit, external, config, contract, challenges, materials, proof,
              preprocessing_environment, sources, *, resource_admission=None, generation_profile=HISTORICAL):
    selected=profile(generation_profile)
    bounds=dict(BOUNDS,**{k:selected[k] for k in BOUNDS if k in selected})
    require(set(sources)==set(FILES),'closed committed source inventory required')
    native_symbol_guard(sources)
    require(hashlib.sha256(canonical(challenges)).hexdigest()==CHALLENGES_SHA256 and
        validate_challenges(challenges)==TEST_COUNTS,'same exposed four tasks and all six real tests required')
    # The original constructor verifies exact model/config/readproof/row/text
    # contracts, using only frozen material and standard-library hashing.
    plan,raw=training_construct(source_commit,external,config,contract,challenges,frozen_specs(),materials,proof,
        preprocessing_environment=preprocessing_environment)
    raw.update(sources)
    plan.pop('generations',None)
    plan.update(format=FORMAT,run_id=selected['run_id'],screen_id=selected['run_id'],**bounds,
        task_order=list(TASKS),task_ids=list(TASKS),test_counts=TEST_COUNTS,test_cases=6,
        verification_schedule='interleaved',generation_paths_enabled=True,
        kernel_execution_type='INERT',owner_editor_only=False,notebook_ref=NOTEBOOK,
        notebook_numeric_id=137327571,expected_notebook_version=selected['notebook_version'],
        selection='same four predeclared exposed public input-cost tasks; no answer-based selection',
        lineage={'accepted_training_plan_sha256':PARENT_PLAN_SHA256,'inference_plan_sha256':INFERENCE_PLAN_SHA256,
            'failed_end_to_end_run_id':'stage4-e10-probe-end-to-end-20261007-001',
            'failed_end_to_end_plan_sha256':'7b8829c2716b116f093dbdecd84f5b179d27344d9ec7efd9a546d33c5f5ec946',
            'failed_end_to_end_package_manifest_sha256':'e5b57c705564d64e2262d92ddc6c6651753edcc75c1dcb32a5346836bf3ec907',
            'failed_end_to_end_source_commit':'90560df5ad0a65e2ef14f5f7b03854d80bbd90b8',
            'repair':'restore native forward after Trainer AMP before inference; original workload and decoder unchanged'},
        processed_sequence_policy='64 parsed/invalid processed native-return sequences per test; raw returns may exceed 64',
        raw_returned_policy='retain counts and processed provenance only; raw returned <= 4 * completed generation forwards',
        output_policy='sealed exposed-subset answer envelope; null missing slots; not competition submission JSON',
        qualification_policy=f"all six nonempty fully verified native-complete tests inside actual {selected['per_test_seconds']}-second window, exact reset, stopped producers",
        numerical_replay='retained actual input/NLL receipts; no independent cross-platform logits replay claim',
        resource_attachment=attachment(SCOPE),**{k:False for k in FALSE_FIELDS})
    if generation_profile==LONGER:
        plan.update(generation_budget_profile=LONGER,forward_observer_required=True,
            future_generation_budget=future_budget(),expected_previous_version=selected['previous_version'],
            expected_previous_script_version_id=selected['previous_script_version_id'])
        plan['lineage'].update(previous_end_to_end_run_id=RUN_ID,
            previous_notebook_version=6,previous_script_version_id=355924733,
            previous_end_to_end_source_commit='55b97d4aee042e24b5e9a32b13b8644e8debea45',
            previous_end_to_end_plan_sha256='d664eb6a8b63d84329728d5e9d18f3a96ce06e80dc01d233b88f60b34e581b9e',
            previous_end_to_end_package_manifest_sha256='47aca0d5c1697392b094a966bdcb573d3b51be60e916517b0f23bc8598de41d8',
            repair='new inert generation budget and host observation; unchanged native workload, decoder and training/reset behavior')
    # No admission value survives from the accepted training-only ancestor.
    plan.update(resource_admission=None,owner_editor_admission=None,
        source_files_sha256={name:hashlib.sha256(body).hexdigest() for name,body in sorted(sources.items())})
    for name in ('plan.json','screen.json'): raw.pop(name,None)
    raw['material-contract.json']=canonical(contract)
    plan['payload_sha256']={name:hashlib.sha256(body).hexdigest() for name,body in sorted(raw.items())}
    if resource_admission is not None:
        require(type(resource_admission) is dict,'exact runtime admission object required')
        inert_raw=dict(raw,**{'plan.json':canonical(plan),'screen.json':canonical(plan)})
        require(resource_admission.get('approved_inert_package_manifest_sha256')==
            hashlib.sha256(canonical(package_manifest(plan,inert_raw))).hexdigest(),
            'runtime admission must bind exact reviewed inert package manifest')
        plan.update(resource_admission=resource_admission,kernel_execution_type='SAVE_AND_RUN_ALL',
            **{k:True for k in RUNTIME_FLAGS})
    validate_admission(plan); reject_truth(plan)
    raw['plan.json']=raw['screen.json']=canonical(plan)
    return plan,raw


def verify_runtime(root, *, require_approved=False):
    root=Path(root); require(not root.is_symlink(),'regular runtime root required')
    plan=parse_json((root/'plan.json').read_bytes())
    require(plan==parse_json((root/'screen.json').read_bytes()) and plan.get('format')==FORMAT and
        plan.get('run_id')==plan.get('screen_id') and plan.get('run_id') in
        {profile(name)['run_id'] for name in PROFILES},'exact distinct end-to-end identity required')
    selected=for_plan(plan)
    validate_admission(plan,required=require_approved)
    bounds=dict(BOUNDS,**{k:selected[k] for k in BOUNDS if k in selected})
    require(all(type(plan.get(k)) is int and plan[k]==v for k,v in bounds.items()) and
        plan['test_counts']==TEST_COUNTS and plan['task_order']==list(TASKS),'exact reviewed bounded workload required')
    for name,expected in plan['payload_sha256'].items():
        path=root/name
        require(path.resolve().is_relative_to(root.resolve()) and not any(p.is_symlink() for p in
            (path,*path.parents)) and sha(path)==expected,'immutable runtime member differs: '+name)
    contract=parse_json((root/'material-contract.json').read_bytes())
    external={name:(root/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json']=(root/'verified-tokenizer.json').read_bytes()
    # The trusted repository verifier supplies its own producer source bytes.
    # Runtime self-checks additionally depend on an independently pinned package
    # manifest; a digest is byte identity, never an execution attestation.
    sources={name:(ROOT/name).read_bytes() for name in FILES}
    expected,raw=construct(plan['source_commit'],external,
        {k:plan[k] for k in (*CONFIG_FIELDS,'native_source_learning_rates')},contract,
        parse_json((root/'challenges.json').read_bytes()),
        {k:parse_json((root/'materials'/f'{k}.json').read_bytes()) for k in TASKS},read_contract(root/PROOF_FILE),
        plan['preprocessing_environment'],sources,resource_admission=plan['resource_admission'],
        generation_profile=selected['profile_id'])
    require(plan==expected and all((root/name).read_bytes()==body for name,body in raw.items()),
        'exact independent plan/material/source reconstruction differs')
    return plan


def verify_embedded_payload(notebook,raw):
    """Reject overwritten literal keys and compare decoded bytes, without execution."""
    import base64,zlib
    body=''.join(notebook['cells'][1]['source']); tree=ast.parse(body)
    values={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('PACKED','HASHES'):
            name=node.targets[0].id
            require(name not in values and isinstance(node.value,ast.Dict),'one literal payload/hash mapping required')
            keys=[key.value if isinstance(key,ast.Constant) and type(key.value) is str else None for key in node.value.keys]
            require(None not in keys and len(keys)==len(set(keys)),'duplicate or nonliteral embedded payload key')
            values[name]=ast.literal_eval(node.value)
    require(set(values)=={'PACKED','HASHES'} and set(values['PACKED'])==set(values['HASHES'])==set(raw),
        'exact embedded runtime member set required')
    for name,expected in raw.items():
        packed=values['PACKED'][name]
        require(type(packed) is str and values['HASHES'][name]==hashlib.sha256(expected).hexdigest(),
            'embedded hash differs from runtime bytes: '+name)
        decoder=zlib.decompressobj();decoded=decoder.decompress(base64.b64decode(packed,validate=True),len(expected)+1)
        require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and decoded==expected,
            'embedded decoded runtime bytes differ: '+name)


def render(plan,raw):
    selected=for_plan(plan)
    if selected['profile_id']==LONGER:
        validate_admission(plan)
        require(raw.get('plan.json')==raw.get('screen.json')==canonical(plan),
            'render requires exact validated plan and embedded screen bytes')
        if plan['resource_admission'] is not None:
            require({name:hashlib.sha256(body).hexdigest() for name,body in raw.items()
                if name not in ('plan.json','screen.json')}==plan['payload_sha256'],
                'render requires exact admitted runtime payload bytes and inventory')
    from tools.stage_nvarc_e10_ttt_probe import render as training_render
    notebook=training_render(plan,raw)
    heading=('Approved bounded exposed public end-to-end calibration; one exact private run.\n'
        if plan.get('approved_for_runtime') is True else
        'INERT exposed public end-to-end calibration. Execution and publication are not admitted.\n')
    notebook['cells'][0]['source']=[heading,
        f"Four exact native epochs, six {selected['per_test_seconds']}-second test windows ({selected['generation_seconds']}-second generation + {selected['verification_reserve_seconds']}-second verifier tail).\n",
        '64 processed sequences/test; raw returns separately counted. Partial/missing output cannot qualify.\n',
        'No teacher, solver truth, ARC scoring, causal comparison, promotion or official submission.\n']
    if selected['profile_id']==LONGER:
        notebook['cells'][0]['source'].append(
            'Host forward observations required. A full 150-second test allocation is required before starting each test.\n')
    body=''.join(notebook['cells'][1]['source'])
    old="str(work/'tools/nvarc_e10_ttt_probe.py'),'--bootstrap','--root'"
    require(body.count(old)==1,'one exact bootstrap command hook required')
    body=body.replace(old,"str(work/'tools/nvarc_e10_end_to_end.py'),'--bootstrap','--root'",1)
    old='from tools.nvarc_e10_ttt_probe import finalize'
    require(body.count(old)==1,'one exact outer finalizer hook required')
    body=body.replace(old,'from tools.nvarc_e10_end_to_end import finalize',1)
    if selected['profile_id']==LONGER:
        gate="screen=json.loads(zlib.decompress(base64.b64decode(PACKED['screen.json'])))\n"
        require(body.count(gate)==1,'one exact decoded plan admission hook required')
        if plan['resource_admission'] is None:
            guard="raise RuntimeError('inert E10 v7 package: new exact v7 run approval has not been granted')\n"
        else:
            # Pin the entire validated admission/plan before creating a folder.
            # PACKED/HASHES alone are caller-controlled mappings; copied flags
            # and rehashed payloads cannot replace this reviewed literal pin.
            expected=hashlib.sha256(canonical(plan)).hexdigest()
            guard=("if hashlib.sha256(zlib.decompress(base64.b64decode(PACKED['screen.json']))).hexdigest()!="+
                repr(expected)+" or HASHES['screen.json']!="+repr(expected)+":\n"+
                "    raise RuntimeError('exact admitted v7 plan bytes differ before runtime setup')\n"+
                "expected_hashes=dict(screen['payload_sha256'],**{'plan.json':"+repr(expected)+",'screen.json':"+repr(expected)+"})\n"+
                "if HASHES!=expected_hashes or set(PACKED)!=set(expected_hashes):\n"+
                "    raise RuntimeError('exact admitted v7 runtime hashes and inventory differ before runtime setup')\n")
        body=body.replace(gate,gate+guard,1)
    # Inert notebook rejects before creating a working folder or importing native
    # code. The coordinator/worker independently enforce the same admission.
    compile(body,'inert-end-to-end-notebook','exec'); notebook['cells'][1]['source']=body.splitlines(keepends=True)
    verify_embedded_payload(notebook,raw)
    return notebook


def metadata(plan):
    return {'id':NOTEBOOK,'title':NOTEBOOK.split('/')[1],'code_file':'notebook.ipynb','language':'python',
        'kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,
        'machine_shape':'NvidiaL4','docker_image':plan['docker_image'],'docker_image_pinning_type':'original',
        'dataset_sources':[],'kernel_sources':[VERSIONED_REF],
        'competition_sources':plan['resource_attachment']['competition_sources'],'model_sources':plan['model_sources']}


def handoff(plan):
    selected=for_plan(plan)
    if selected['profile_id']==LONGER:validate_admission(plan)
    admitted=plan['resource_admission'] is not None
    value={'format':'irisx/end-to-end-transport-handoff-v1','run_id':plan['run_id'],'execute_commands':False,
        'publication_authorized':admitted,'runtime_authorized':admitted,'kernel_execution_type':plan['kernel_execution_type'],
        'notebook_ref':NOTEBOOK,'notebook_numeric_id':137327571,'expected_notebook_version':selected['notebook_version'],
        'monitor_after_submission':False,
        'maximum_processed_sequences_per_test':64,'maximum_processed_sequences_total':384,
        'raw_returned_may_exceed_processed_cap':True,'provider_seconds':3600,'paid_usd_ceiling':0}
    if selected['profile_id']==LONGER:
        value.update(expected_previous_version=selected['previous_version'],
            expected_previous_script_version_id=selected['previous_script_version_id'],
            generation_budget_profile=LONGER,forward_observer_required=True,approval_pending=not admitted,
            agent_execution_authorized=admitted,official_submission_authorized=False)
    return value


def stage(package, plan, raw):
    package=Path(package); require(not package.exists(),'new immutable package directory required')
    (package/'kernel').mkdir(parents=True)
    for name,body in raw.items():
        path=package/'runtime'/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(body)
    write(package/'kernel/notebook.ipynb',render(plan,raw));write(package/'kernel/kernel-metadata.json',metadata(plan))
    write(package/'cli-handoff.json',handoff(plan))
    write(package/'package-manifest.json',package_manifest(plan,raw))
    return preflight(package)


def package_manifest(plan,raw):
    files={'runtime/'+name:body for name,body in raw.items()}
    files.update({'kernel/notebook.ipynb':canonical(render(plan,raw)),
        'kernel/kernel-metadata.json':canonical(metadata(plan)),'cli-handoff.json':canonical(handoff(plan))})
    return {'format':'irisx/end-to-end-inert-package-v1','plan_digest':digest(plan),
        'files_sha256':{name:hashlib.sha256(body).hexdigest() for name,body in sorted(files.items())}}


def preflight(package, *, expected_manifest_sha256=None):
    package=Path(package); manifest=parse_json((package/'package-manifest.json').read_bytes())
    require(not any(p.is_symlink() for p in (package,*package.rglob('*'))) and
        set(manifest)=={'format','plan_digest','files_sha256'} and manifest['format']=='irisx/end-to-end-inert-package-v1' and
        manifest['files_sha256']=={p.relative_to(package).as_posix():sha(p) for p in package.rglob('*')
            if p.is_file() and p!=package/'package-manifest.json'},'closed immutable end-to-end package required')
    if expected_manifest_sha256 is not None:
        require(sha(package/'package-manifest.json')==expected_manifest_sha256,'independent manifest pin differs')
    root=package/'runtime';plan=verify_runtime(root)
    committed=exact_sources(plan['source_commit'])
    require(plan['source_files_sha256']=={name:hashlib.sha256(body).hexdigest() for name,body in committed.items()},
        'package source commit must identify these exact reviewed producer bytes')
    raw={name:(root/name).read_bytes() for name in (*plan['payload_sha256'],'plan.json','screen.json')}
    require(manifest['plan_digest']==digest(plan) and set(manifest['files_sha256'])==
        {'runtime/'+name for name in raw}|{'kernel/notebook.ipynb','kernel/kernel-metadata.json','cli-handoff.json'} and
        parse_json((package/'kernel/notebook.ipynb').read_bytes())==render(plan,raw) and
        parse_json((package/'kernel/kernel-metadata.json').read_bytes())==metadata(plan) and
        parse_json((package/'cli-handoff.json').read_bytes())==handoff(plan),'exact notebook/metadata/handoff required')
    return {'run_id':plan['run_id'],'plan_digest':digest(plan),'package_manifest_sha256':sha(package/'package-manifest.json'),
        'offline_package_verified':True,'runtime_authorized':plan['approved_for_runtime'],
        'publication_authorized':plan['publication_authorized'],
        'new_model_calls':0,'new_provider_calls':0,'gpu_probe_run':False}


def build_from_frozen(package, frozen_runtime, source_commit, inference_plan, *, resource_admission=None,
                      generation_profile=HISTORICAL):
    frozen_runtime=Path(frozen_runtime)
    require(sha(frozen_runtime/'plan.json')==PARENT_PLAN_SHA256 and sha(inference_plan)==INFERENCE_PLAN_SHA256,
        'exact accepted v4 and unchanged interleaved-r1 source plans required')
    parent=verify_training_runtime(frozen_runtime)
    require(parent['approved_for_runtime'] is True,'accepted training ancestor required as data only')
    sources=exact_sources(source_commit)
    inferred=parse_json(Path(inference_plan).read_bytes())
    for key,count in TEST_COUNTS.items():
        spec=inferred['task_specs'][key]
        require(spec['test_count']==count and spec['inference_forward_limits']=={
            'control':7,'generation':4096*count,'verification':128*count} and
            spec['per_test_limits']=={'generation':4096,'verification':128,'input_tokens':5242880} and
            spec['maximum_candidate_sequences_per_test']==64 and spec['inference_seconds']==30*count and
            spec['verification_schedule']=='interleaved','unchanged full-E10 inference recipe required')
    contract=parse_json((frozen_runtime/'material-contract.json').read_bytes())
    external={name:(frozen_runtime/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json']=(frozen_runtime/'verified-tokenizer.json').read_bytes()
    plan,raw=construct(source_commit,external,{k:parent[k] for k in (*CONFIG_FIELDS,'native_source_learning_rates')},
        contract,parse_json((frozen_runtime/'challenges.json').read_bytes()),
        {k:parse_json((frozen_runtime/'materials'/f'{k}.json').read_bytes()) for k in TASKS},
        read_contract(frozen_runtime/PROOF_FILE),parent['preprocessing_environment'],sources,
        resource_admission=resource_admission,generation_profile=generation_profile)
    return stage(package,plan,raw)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('stage','preflight'))
    p.add_argument('--package',type=Path,required=True);p.add_argument('--frozen-runtime',type=Path)
    p.add_argument('--source-commit');p.add_argument('--inference-plan',type=Path)
    p.add_argument('--resource-admission',type=Path)
    p.add_argument('--generation-profile',choices=PROFILES,default=HISTORICAL)
    p.add_argument('--expected-manifest-sha256');a=p.parse_args()
    value=preflight(a.package,expected_manifest_sha256=a.expected_manifest_sha256) if a.action=='preflight' else \
        build_from_frozen(a.package,a.frozen_runtime,a.source_commit,a.inference_plan,
            resource_admission=parse_json(a.resource_admission.read_bytes()) if a.resource_admission else None,
            generation_profile=a.generation_profile)
    print(json.dumps(value))


if __name__=='__main__':main()

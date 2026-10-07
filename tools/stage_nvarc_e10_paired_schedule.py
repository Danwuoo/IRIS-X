"""Stage exact v8 paired scheduling bytes. No provider/GPU calls.

One training epoch per task is reused by both inference arms. No existing
admission or consumed owner approval can grant authority to this new identity.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical,digest,require,write
from tools.nvarc_native_submission import reject_truth
from tools import stage_nvarc_e10_end_to_end as ancestor
from tools import nvarc_e10_answer_evidence as evidence
from tools.stage_nvarc_e10_screen import CONFIG_FIELDS,material_files,sha
from tools.nvarc_dependency_readproof import PROOF_FILE,read_contract
from tools.nvarc_e10_generation_profile import LONGER
from tools.nvarc_e10_paired_schedule import (FORMAT,RUN_ID,PROFILE,TIMING,CAPS,PER_ARM_CAPS,
    ARMS,counterbalanced_order,budget_report,profile_for_plan,verify_worker_result,seal_outputs)

NOTEBOOK=ancestor.NOTEBOOK
SCOPE=ancestor.SCOPE
WORKER_PATH='tools/nvarc_e10_paired_schedule.py'
NEW_FILES=('tools/nvarc_e10_paired_schedule.py','tools/stage_nvarc_e10_paired_schedule.py')
FILES=tuple(sorted(set(ancestor.FILES)|set(NEW_FILES)))
FALSE_FIELDS=ancestor.FALSE_FIELDS


RUNTIME_FLAGS=ancestor.RUNTIME_FLAGS
ADMISSION='irisx/stage4-paired-schedule-v8-single-run-admission-v1'
OWNER='Sentinel_a33677299af08191894d1a4dab5fa7cc'
OWNER_PROPOSAL='Sentinel_2eb82e6753ec8191bc611392abcba44c'
BASELINE={
    'source_commit':'62d38a79fecf8a4435b5d12b8ad0f7c0a5a4593e',
    'inert_plan_digest':'sha256:3a256b0ec9f122b02c0b2a2098a164f3d0d7669d61ea79cd0c94cd93e88c93af',
    'inert_package_manifest_sha256':'c848ab5ff1ae94d50bcc6da214d20a37016d879974feb11d97fc07c4314a0491',
    'inert_notebook_sha256':'4196d83afa8e43675128353a692403ec255fcb04835e3ae4b0a2ede66eff0b38',
    'independent_review_sha256':'d92ad5c03c647eea735687f4357649da59493892ce6c0f6f1e148e47dd124537'}
ADMISSION_FIELDS=ancestor.ADMISSION_FIELDS|{'approved_v8_baseline','quota_snapshot_json','quota_checked_at','owner_proposal_ref'}


def validate_run_admission(plan,value):
    """Bind the approved scientific bytes and the separately reviewed new guard.

    The snapshot is fresh at the recorded admission check. The publisher must
    check its age again immediately before Save; queued runtime is not a new
    provider action and does not require the snapshot still to be recent.
    """
    require(type(value) is dict and set(value)==ADMISSION_FIELDS and value['format']==ADMISSION,
        'closed exact v8 run admission required')
    require(value['run_id']==plan['run_id']==RUN_ID and
        value['owner_instruction_ref']==OWNER and value['owner_proposal_ref']==OWNER_PROPOSAL and value['notebook_ref']==plan.get('notebook_ref')==NOTEBOOK and
        type(plan.get('notebook_numeric_id')) is int and plan['notebook_numeric_id']==137327571 and
        value['kernel_execution_type']==plan.get('kernel_execution_type')=='SAVE_AND_RUN_ALL' and
        value['private'] is True and value['internet'] is value['monitor_after_submission'] is False and
        plan.get('owner_editor_only') is False and plan.get('local_fixture') is False and
        all(plan.get(k) is True for k in RUNTIME_FLAGS) and
        all(type(value[k]) is int and value[k]==v for k,v in (
            ('notebook_numeric_id',137327571),('expected_notebook_version',8),('expected_previous_version',7),
            ('expected_previous_script_version_id',355983651),('provider_session_seconds',3600),
            ('paid_usd_ceiling',0),('charged_quota_seconds_reserved',14400))) and
        type(value['approved_v8_baseline']) is dict and value['approved_v8_baseline']==BASELINE and
        type(value['source_commit']) is str and re.fullmatch('[0-9a-f]{40}',value['source_commit']) and
        value['source_commit']==plan.get('source_commit') and value['source_commit']!=BASELINE['source_commit'] and
        all(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}',value[k]) and value[k]!='0'*64 for k in
            ('quota_snapshot_sha256','approved_inert_package_manifest_sha256','independent_review_sha256')) and
        value['independent_review_sha256']!=BASELINE['independent_review_sha256'] and
        type(value['approved_inert_plan_digest']) is str and re.fullmatch('sha256:[0-9a-f]{64}',value['approved_inert_plan_digest']),
        'exact new owner-approved private free version-eight source/review admission required')
    require(type(value['quota_snapshot_json']) is str and len(value['quota_snapshot_json'].encode())<=1024*1024,
        'bounded exact quota snapshot bytes required')
    body=value['quota_snapshot_json'].encode()
    require(hashlib.sha256(body).hexdigest()==value['quota_snapshot_sha256'],'quota snapshot byte binding differs')
    try: snapshot=parse_json(body)
    except (ValueError,TypeError): raise RuntimeError('closed exact quota snapshot JSON required') from None
    require(type(snapshot) is dict and set(snapshot)==ancestor.QUOTA_FIELDS and
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
    observed=ancestor.admission_timestamp(value['quota_observed_at']);checked=ancestor.admission_timestamp(value['quota_checked_at'])
    require(0<=(checked-observed).total_seconds()<=900 and checked<ancestor.admission_timestamp(snapshot['refresh_at']),
        'fresh current-window quota required at admission; recheck immediately before Save')
    inert=dict(plan,resource_admission=None,kernel_execution_type='INERT',**{k:False for k in RUNTIME_FLAGS})
    require(value['approved_inert_plan_digest']==digest(inert),'admission must bind the exact current reviewed inert plan')



def validate_admission(plan,*,required=False):
    profile_for_plan(plan)
    require(plan.get('owner_editor_only') is False and plan.get('owner_editor_admission') is None and
        all(plan.get(k) is False for k in set(FALSE_FIELDS)-RUNTIME_FLAGS),
        'no owner-Editor, scoring, promotion or official authority can be inherited')
    value=plan.get('resource_admission')
    if value is None:
        require(plan.get('kernel_execution_type')=='INERT' and all(plan.get(k) is False for k in RUNTIME_FLAGS),
            'paired v8 remains INERT without its exact new admission')
        require(not required,'new exact paired v8 run approval has not been granted')
    else:validate_run_admission(plan,value)


def exact_sources(commit):
    require(re.fullmatch('[0-9a-f]{40}',commit or ''),'full committed paired implementation required')
    result={}
    for name in FILES:
        path=ROOT/name;require(not path.is_symlink(),'regular paired implementation source required')
        body=subprocess.run(['git','show',commit+':'+name],cwd=ROOT,capture_output=True,check=True).stdout
        require(body==path.read_bytes(),'exact paired source commit differs: '+name)
        ast.parse(body,filename=name);result[name]=body
    ancestor.native_symbol_guard({name:result[name] for name in ancestor.FILES})
    for name in NEW_FILES:
        for node in ast.parse(result[name]).body:
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]]
                require(not set(names)&{'torch','numpy','tokenizers','unsloth','transformers','peft'},
                    'paired native import forbidden before the admission gate')
    return result


def construct(commit,external,config,contract,challenges,materials,proof,preprocessing_environment,sources,*,resource_admission=None):
    require(set(sources)==set(FILES),'closed paired source inventory required')
    plan,raw=ancestor.construct(commit,external,config,contract,challenges,materials,proof,
        preprocessing_environment,{name:sources[name] for name in ancestor.FILES},generation_profile=LONGER)
    raw.update(sources)
    for name in ('plan.json','screen.json'):raw.pop(name,None)
    plan.pop('future_generation_budget',None)
    plan.update(format=FORMAT,run_id=RUN_ID,screen_id=RUN_ID,generation_budget_profile=PROFILE,
        verification_schedule='paired',verification_schedules=list(ARMS),arm_order=counterbalanced_order(plan['test_counts']),
        arm_order_rule='sorted public task IDs; alternate within one-test and two-test task strata',
        per_arm_caps=dict(PER_ARM_CAPS),**TIMING,**CAPS,expected_notebook_version=8,
        expected_previous_version=7,expected_previous_script_version_id=355983651,
        test_executions=12,training_reuse='one complete native epoch per task; retain model in memory for both arms; no additional training',
        rng_policy='capture and restore Python, NumPy, torch CPU and CUDA streams to identical trained-entry state before each arm',
        cache_policy='fresh AnswerModel/counters/observer per arm; every source batch starts with uncached prefill; no extra warmup/control calls',
        rotary_cache_policy='observe pinned LlamaRotaryEmbedding ordinary cache class/capacity/tensor metadata; require >=8192 and unchanged; unknown transitions fail; llama.py is outside the selected five-file readproof',
        paired_resource_proposal=budget_report(),
        qualification_policy='resource/output evidence only; separate six-test arm denominators, all eight verifier rows and unchanged trained hashes required; no retroqualification',
        output_policy='atomic paired envelope with separate per-arm exposed answers/audits; explicit null missing slots; no official submission JSON',
        resource_admission=None,owner_editor_admission=None,kernel_execution_type='INERT',
        **{k:False for k in FALSE_FIELDS})
    history={k:plan['lineage'][k] for k in tuple(plan['lineage']) if k.startswith('previous_')}
    for name in history:plan['lineage'].pop(name)
    plan['lineage'].update(historical_v6=history,previous_end_to_end_run_id='stage4-e10-probe-end-to-end-20261007-003',
        previous_notebook_version=7,previous_script_version_id=355983651,
        previous_end_to_end_source_commit='237ae881f5b7ed3cb1c0f9460bd3fa35f9c5049a',
        repair='paired scheduling from the same retained trained state; no comparison of separate stochastic TTT runs')
    plan['source_files_sha256']={name:hashlib.sha256(body).hexdigest() for name,body in sorted(sources.items())}
    plan['payload_sha256']={name:hashlib.sha256(body).hexdigest() for name,body in sorted(raw.items())}
    if resource_admission is not None:
        require(type(resource_admission) is dict,'exact paired admission object required')
        inert_raw=dict(raw,**{'plan.json':canonical(plan),'screen.json':canonical(plan)})
        require(resource_admission.get('approved_inert_package_manifest_sha256')==
            hashlib.sha256(canonical(package_manifest(plan,inert_raw))).hexdigest(),
            'paired admission must bind the exact independently reviewed inert package')
        plan.update(resource_admission=resource_admission,kernel_execution_type='SAVE_AND_RUN_ALL',
            **{k:True for k in RUNTIME_FLAGS})
    validate_admission(plan);reject_truth(plan)
    raw['plan.json']=raw['screen.json']=canonical(plan)
    return plan,raw


def verify_runtime(root,*,require_approved=False):
    root=Path(root);require(not root.is_symlink(),'regular paired runtime root required')
    plan=parse_json((root/'plan.json').read_bytes())
    require(plan==parse_json((root/'screen.json').read_bytes()),'identical paired plan/screen required')
    # Gate first. INERT direct coordinator and worker terminate here before
    # source replay, dependency preparation or any native import.
    validate_admission(plan,required=require_approved)
    require(set(plan['source_files_sha256'])==set(FILES) and set(FILES)<=set(plan['payload_sha256']),
        'closed paired implementation payload required')
    for name,expected in plan['payload_sha256'].items():
        path=root/name
        require(path.resolve().is_relative_to(root.resolve()) and not any(p.is_symlink() for p in (path,*path.parents)) and
            sha(path)==expected,'immutable paired member differs: '+name)
    contract=parse_json((root/'material-contract.json').read_bytes())
    external={name:(root/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json']=(root/'verified-tokenizer.json').read_bytes()
    sources={name:(ROOT/name).read_bytes() for name in FILES}
    expected,raw=construct(plan['source_commit'],external,{k:plan[k] for k in (*CONFIG_FIELDS,'native_source_learning_rates')},
        contract,parse_json((root/'challenges.json').read_bytes()),
        {key:parse_json((root/'materials'/f'{key}.json').read_bytes()) for key in ancestor.TASKS},
        read_contract(root/PROOF_FILE),plan['preprocessing_environment'],sources,resource_admission=plan['resource_admission'])
    require(plan==expected and all((root/name).read_bytes()==body for name,body in raw.items()),
        'exact paired source/material/plan reconstruction differs')
    return plan


def render(plan,raw):
    validate_admission(plan)
    require(raw.get('plan.json')==raw.get('screen.json')==canonical(plan),'exact inert paired plan bytes required')
    from tools.stage_nvarc_e10_ttt_probe import render as training_render
    notebook=training_render(plan,raw)
    heading=('Approved v8 paired scheduling; one exact private free run.\n' if plan['resource_admission'] is not None else
        'INERT v8 paired scheduling. No execution, save, publication or provider authority.\n')
    notebook['cells'][0]['source']=[heading,
        'Train four native epochs once (512 updates), then compare interleaved/deferred using unchanged trained weights.\n',
        'Each arm has six real tests with full120-second generation +30-second verifier tail; predeclared task-stratum arm order.\n',
        'Strict per-arm v7 caps; actual total12test executions. Partial/missing output stays unqualified.\n',
        'Conservative phase sum3480seconds;120seconds notebook margin is arithmetic only. Fresh quota and exact-run review remain required.\n',
        'No teacher, truth, ARC score, promotion, causal quality or official-submission claim.\n']
    body=''.join(notebook['cells'][1]['source'])
    hook="screen=json.loads(zlib.decompress(base64.b64decode(PACKED['screen.json'])))\n"
    require(body.count(hook)==1,'one paired boot admission hook required')
    if plan['resource_admission'] is None:
        guard="raise RuntimeError('inert paired v8 package: new exact run approval has not been granted')\n"
    else:
        expected=hashlib.sha256(canonical(plan)).hexdigest()
        require({name:hashlib.sha256(value).hexdigest() for name,value in raw.items()
            if name not in ('plan.json','screen.json')}==plan['payload_sha256'],
            'exact admitted paired payload bytes and inventory required')
        guard=("if hashlib.sha256(zlib.decompress(base64.b64decode(PACKED['screen.json']))).hexdigest()!="+
            repr(expected)+" or HASHES['screen.json']!="+repr(expected)+":\n"+
            "    raise RuntimeError('exact admitted v8 plan bytes differ before runtime setup')\n"+
            "expected_hashes=dict(screen['payload_sha256'],**{'plan.json':"+repr(expected)+",'screen.json':"+repr(expected)+"})\n"+
            "if HASHES!=expected_hashes or set(PACKED)!=set(expected_hashes):\n"+
            "    raise RuntimeError('exact admitted v8 runtime hashes and inventory differ before runtime setup')\n")
    body=body.replace(hook,hook+guard,1)
    old="str(work/'tools/nvarc_e10_ttt_probe.py'),'--bootstrap','--root'"
    require(body.count(old)==1,'one paired coordinator hook required')
    body=body.replace(old,"str(work/'tools/nvarc_e10_paired_schedule.py'),'--bootstrap','--root'",1)
    old='from tools.nvarc_e10_ttt_probe import finalize'
    require(body.count(old)==1,'one atomic finalizer hook required')
    body=body.replace(old,'from tools.nvarc_e10_end_to_end import finalize',1)
    compile(body,'inert-paired-v8-notebook','exec');notebook['cells'][1]['source']=body.splitlines(keepends=True)
    ancestor.verify_embedded_payload(notebook,raw)
    return notebook


def metadata(plan):return ancestor.metadata(plan)


def handoff(plan):
    validate_admission(plan)
    admitted=plan['resource_admission'] is not None
    return dict(format='irisx/paired-schedule-inert-handoff-v1',run_id=RUN_ID,execute_commands=False,
        publication_authorized=admitted,runtime_authorized=admitted,agent_execution_authorized=admitted,
        owner_editor_authorized=False,approval_pending=not admitted,kernel_execution_type=plan['kernel_execution_type'],notebook_ref=NOTEBOOK,
        notebook_numeric_id=137327571,expected_notebook_version=8,expected_previous_version=7,
        expected_previous_script_version_id=355983651,maximum_processed_sequences_total=768,
        training_updates=512,test_executions=12,provider_seconds=3600,paid_usd_ceiling=0,
        charged_gpu_seconds_ceiling=14400,monitor_after_submission=False,official_submission_authorized=False)


def package_manifest(plan,raw):
    files={'runtime/'+name:body for name,body in raw.items()}
    files.update({'kernel/notebook.ipynb':canonical(render(plan,raw)),
        'kernel/kernel-metadata.json':canonical(metadata(plan)),'cli-handoff.json':canonical(handoff(plan))})
    return dict(format='irisx/paired-schedule-inert-package-v1',plan_digest=digest(plan),
        files_sha256={name:hashlib.sha256(body).hexdigest() for name,body in sorted(files.items())})


def stage(package,plan,raw):
    package=Path(package);require(not package.exists(),'new immutable paired package directory required')
    (package/'kernel').mkdir(parents=True)
    for name,body in raw.items():
        path=package/'runtime'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    write(package/'kernel/notebook.ipynb',render(plan,raw));write(package/'kernel/kernel-metadata.json',metadata(plan))
    write(package/'cli-handoff.json',handoff(plan));write(package/'package-manifest.json',package_manifest(plan,raw))
    return preflight(package)


def preflight(package,*,expected_manifest_sha256=None):
    package=Path(package);manifest=parse_json((package/'package-manifest.json').read_bytes())
    require(not any(p.is_symlink() for p in (package,*package.rglob('*'))) and
        manifest['files_sha256']=={p.relative_to(package).as_posix():sha(p) for p in package.rglob('*')
            if p.is_file() and p!=package/'package-manifest.json'},'closed immutable paired package required')
    if expected_manifest_sha256 is not None:require(sha(package/'package-manifest.json')==expected_manifest_sha256,'independent paired manifest pin differs')
    plan=verify_runtime(package/'runtime');sources=exact_sources(plan['source_commit'])
    require(plan['source_files_sha256']=={name:hashlib.sha256(body).hexdigest() for name,body in sources.items()},
        'exact committed paired implementation binding required')
    raw={name:(package/'runtime'/name).read_bytes() for name in (*plan['payload_sha256'],'plan.json','screen.json')}
    require(manifest==package_manifest(plan,raw) and
        parse_json((package/'kernel/notebook.ipynb').read_bytes())==render(plan,raw) and
        parse_json((package/'kernel/kernel-metadata.json').read_bytes())==metadata(plan) and
        parse_json((package/'cli-handoff.json').read_bytes())==handoff(plan),'exact paired notebook/metadata/handoff differs')
    return dict(run_id=RUN_ID,plan_digest=digest(plan),package_manifest_sha256=sha(package/'package-manifest.json'),
        offline_package_verified=True,runtime_authorized=plan['resource_admission'] is not None,
        publication_authorized=plan['resource_admission'] is not None,
        new_model_calls=0,new_provider_calls=0,gpu_probe_run=False,budget=budget_report())


def build_from_frozen(package,frozen_runtime,commit,inference_plan):
    frozen_runtime=Path(frozen_runtime)
    require(sha(frozen_runtime/'plan.json')==ancestor.PARENT_PLAN_SHA256 and
        sha(inference_plan)==ancestor.INFERENCE_PLAN_SHA256,'exact accepted training and interleaved inference plans required')
    # Ancestor admissions are data only. Validate and derive material, then
    # construct independently resets every authority field to false/null.
    parent=parse_json((frozen_runtime/'plan.json').read_bytes());inferred=parse_json(Path(inference_plan).read_bytes())
    for key,count in ancestor.TEST_COUNTS.items():
        spec=inferred['task_specs'][key]
        require(spec['test_count']==count and spec['per_test_limits']==evidence.PER_TEST and
            spec['maximum_candidate_sequences_per_test']==64 and spec['verification_schedule']=='interleaved',
            'same frozen solver/cap recipe required')
    contract=parse_json((frozen_runtime/'material-contract.json').read_bytes())
    external={name:(frozen_runtime/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json']=(frozen_runtime/'verified-tokenizer.json').read_bytes()
    plan,raw=construct(commit,external,{k:parent[k] for k in (*CONFIG_FIELDS,'native_source_learning_rates')},
        contract,parse_json((frozen_runtime/'challenges.json').read_bytes()),
        {key:parse_json((frozen_runtime/'materials'/f'{key}.json').read_bytes()) for key in ancestor.TASKS},
        read_contract(frozen_runtime/PROOF_FILE),parent['preprocessing_environment'],exact_sources(commit))
    return stage(package,plan,raw)


def build_from_approved_inert(package,baseline,commit,*,resource_admission=None):
    """Rebind only source/admission around the exact reviewed v8 proposal."""
    baseline=Path(baseline)
    require(sha(baseline/'package-manifest.json')==BASELINE['inert_package_manifest_sha256'] and
        sha(baseline/'runtime/plan.json')==BASELINE['inert_plan_digest'].split(':')[1] and
        sha(baseline/'kernel/notebook.ipynb')==BASELINE['inert_notebook_sha256'],
        'exact reviewed v8 baseline pins required')
    manifest=parse_json((baseline/'package-manifest.json').read_bytes())
    require(not any(p.is_symlink() for p in (baseline,*baseline.rglob('*'))) and
        manifest['files_sha256']=={p.relative_to(baseline).as_posix():sha(p) for p in baseline.rglob('*')
            if p.is_file() and p!=baseline/'package-manifest.json'},'closed immutable approved baseline required')
    root=baseline/'runtime';parent=parse_json((root/'plan.json').read_bytes())
    require(parent['source_commit']==BASELINE['source_commit'],'approved baseline source differs')
    sources=exact_sources(commit)
    require(all(body==(root/name).read_bytes() for name,body in sources.items()
        if name!='tools/stage_nvarc_e10_paired_schedule.py'),
        'only the paired admission/renderer source may differ from the reviewed baseline')
    contract=parse_json((root/'material-contract.json').read_bytes())
    external={name:(root/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json']=(root/'verified-tokenizer.json').read_bytes()
    plan,raw=construct(commit,external,{k:parent[k] for k in (*CONFIG_FIELDS,'native_source_learning_rates')},
        contract,parse_json((root/'challenges.json').read_bytes()),
        {key:parse_json((root/'materials'/f'{key}.json').read_bytes()) for key in ancestor.TASKS},
        read_contract(root/PROOF_FILE),parent['preprocessing_environment'],sources,resource_admission=resource_admission)
    excluded={'source_commit','source_files_sha256','payload_sha256','resource_admission','kernel_execution_type'}|RUNTIME_FLAGS
    require({k:v for k,v in plan.items() if k not in excluded}==
        {k:v for k,v in parent.items() if k not in excluded},'approved paired scientific plan must remain unchanged')
    return stage(package,plan,raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--frozen-runtime',type=Path)
    parser.add_argument('--source-commit');parser.add_argument('--inference-plan',type=Path)
    parser.add_argument('--expected-manifest-sha256');parser.add_argument('--approved-inert-package',type=Path)
    parser.add_argument('--resource-admission',type=Path);args=parser.parse_args()
    result=preflight(args.package,expected_manifest_sha256=args.expected_manifest_sha256) if args.action=='preflight' else \
        build_from_approved_inert(args.package,args.approved_inert_package,args.source_commit,
            resource_admission=parse_json(args.resource_admission.read_bytes()) if args.resource_admission else None) if args.approved_inert_package else \
        build_from_frozen(args.package,args.frozen_runtime,args.source_commit,args.inference_plan)
    print(json.dumps(result))


if __name__=='__main__':main()

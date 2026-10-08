"""Build and verify exact INERT E11 paired DFS-floor bytes; no runtime admission.

No native dependencies, provider calls, publication or original solver edits.
The default 60-minute reservation remains blocked by the observed free quota.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
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
from tools import stage_nvarc_e10_paired_schedule as ancestor
from tools import nvarc_e10_answer_evidence as evidence
from tools.stage_nvarc_e10_screen import CONFIG_FIELDS,material_files,sha
from tools.nvarc_dependency_readproof import PROOF_FILE,read_contract
from tools.nvarc_e11_paired_floor import (FORMAT,RUN_ID,PROFILE,TIMING,CAPS,PER_ARM_CAPS,
    ARMS,BUDGET_PROFILE,BUDGET_45,OWNER_BUDGET_45,RESOURCE_PROFILES,MODEL_LAYOUT,PROCESS_45,arm_contract,counterbalanced_order,budget_report,profile_for_plan,
    verify_worker_result,seal_outputs,record_worker_launch)

NOTEBOOK=ancestor.NOTEBOOK
SCOPE=ancestor.SCOPE
WORKER_PATH='tools/nvarc_e11_paired_floor.py'
NEW_FILES=('tools/nvarc_e11_dfs_contract.py','tools/nvarc_e11_cleanup.py','tools/nvarc_e11_paired_floor.py','tools/stage_nvarc_e11_paired_floor.py')
FILES=tuple(sorted(set(ancestor.FILES)|set(NEW_FILES)))
FALSE_FIELDS=ancestor.FALSE_FIELDS
SOLVER_SHA256='1387c5b0b188dcc8570659dd5905ec2e824e5e0dfd7b20d8be9c2e13d0f12962'
V8_PLAN_SHA256='c6d0a7e86c54402c8c7aafaccadf53db4161691ad270472bf207c0f9fec7a1d3'


def validate_admission(plan,*,required=False):
    profile_for_plan(plan)
    require(plan.get('resource_admission') is None and plan.get('owner_editor_admission') is None and
        plan.get('owner_editor_only') is False and plan.get('kernel_execution_type')=='INERT' and
        all(plan.get(k) is False for k in FALSE_FIELDS),
        'E11 is INERT: no inherited or new runtime/publication/Editor admission is implemented')
    require(not required,'INERT E11: no new exact runtime admission is implemented')


def exact_sources(commit):
    require(re.fullmatch('[0-9a-f]{40}',commit or ''),'full committed paired implementation required')
    result={}
    for name in FILES:
        path=ROOT/name;require(not path.is_symlink(),'regular paired implementation source required')
        body=subprocess.run(['git','show',commit+':'+name],cwd=ROOT,capture_output=True,check=True).stdout
        require(body==path.read_bytes(),'exact paired source commit differs: '+name)
        ast.parse(body,filename=name);result[name]=body
    ancestor.ancestor.native_symbol_guard({name:result[name] for name in ancestor.ancestor.FILES})
    for name in NEW_FILES:
        for node in ast.parse(result[name]).body:
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]]
                require(not set(names)&{'torch','numpy','tokenizers','unsloth','transformers','peft'},
                    'paired native import forbidden before the admission gate')
    return result


def construct(commit,external,config,contract,challenges,materials,proof,preprocessing_environment,sources,*,budget_profile=BUDGET_PROFILE):
    require(set(sources)==set(FILES),'closed E11 source inventory required')
    require(hashlib.sha256(external['solver.py']).hexdigest()==SOLVER_SHA256,
        'unchanged original solver.py required for both floors')
    plan,raw=ancestor.construct(commit,external,config,contract,challenges,materials,proof,
        preprocessing_environment,{name:sources[name] for name in ancestor.FILES})
    raw.update(sources)
    for name in ('plan.json','screen.json'):raw.pop(name,None)
    require(budget_profile in RESOURCE_PROFILES,'closed E11 resource profile required')
    timing=dict(RESOURCE_PROFILES[budget_profile]);run_id=timing.pop('run_id')
    plan.update(format=FORMAT,run_id=run_id,screen_id=run_id,generation_budget_profile=PROFILE,
        **timing,resource_budget_profile=budget_profile,retained_model_layout=dict(MODEL_LAYOUT),
        e11_process_policy=dict(PROCESS_45) if budget_profile in (BUDGET_45,OWNER_BUDGET_45) else None,arm_contracts={a:arm_contract(a) for a in ARMS},
        verification_schedule='interleaved',verification_schedules=['interleaved'],
        arm_order=counterbalanced_order(plan['test_counts']),expected_notebook_version=9,
        expected_previous_version=8,expected_previous_script_version_id=356039440,
        paired_resource_proposal=budget_report(budget_profile),
        scientific_factor='cumulative sequence probability floor only; p02=.2, p01=.1; strict max_score=-log(floor)',
        source_replay_policy='caller-bound arm floor governs source call and returned EOS scores; formatter/verifier/ranker CPU replay is not native logit numerical replay',
        resource_admission=None,owner_editor_admission=None,kernel_execution_type='INERT',
        **{k:False for k in FALSE_FIELDS})
    plan['cleanup_reserve_seconds']=310 if budget_profile in (BUDGET_45,OWNER_BUDGET_45) else 600
    plan['lineage']['historical_v8']=dict(run_id=ancestor.RUN_ID,plan_sha256=V8_PLAN_SHA256,
        source_commit='46b2ff78b7003d1de7e194d251aaccc38228b5db',consumed=True)
    plan['lineage']['repair']='single DFS probability-floor contrast on shared trained state; both interleaved; no scheduling promotion'
    plan['source_files_sha256']={name:hashlib.sha256(body).hexdigest() for name,body in sorted(sources.items())}
    plan['payload_sha256']={name:hashlib.sha256(body).hexdigest() for name,body in sorted(raw.items())}
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
        {key:parse_json((root/'materials'/f'{key}.json').read_bytes()) for key in ancestor.ancestor.TASKS},
        read_contract(root/PROOF_FILE),plan['preprocessing_environment'],sources,budget_profile=plan['resource_budget_profile'])
    require(plan==expected and all((root/name).read_bytes()==body for name,body in raw.items()),
        'exact paired source/material/plan reconstruction differs')
    return plan


def render(plan,raw):
    validate_admission(plan)
    require(raw.get('plan.json')==raw.get('screen.json')==canonical(plan),'exact E11 plan bytes required')
    from tools.stage_nvarc_e10_ttt_probe import render as training_render
    notebook=training_render(plan,raw)
    notebook['cells'][0]['source']=[
        'INERT E11: paired p02=.2 versus p01=.1 cumulative sequence probability floor.\n',
        'Both interleaved, 120-second generation and 150-second total per test; same six test cases per arm.\n',
        '512 native updates once; retained model/RNG/input/cache gates; original solver bytes unchanged.\n',
        ('Original 60-minute resource profile is BLOCKED: four GPU-hours exceed observed free quota.\n'
            if plan['resource_budget_profile']==BUDGET_PROFILE else
            'Separate 45-minute INERT cutoff proposal: finalization feasibility is not worst-case certified.\n'),
        'No admission, publication, provider, native execution, correctness or promotion authority.\n']
    body=''.join(notebook['cells'][1]['source'])
    old="str(work/'tools/nvarc_e10_ttt_probe.py'),'--bootstrap','--root'"
    require(body.count(old)==1,'one E11 coordinator hook required')
    body=body.replace(old,"str(work/'tools/nvarc_e11_paired_floor.py'),'--bootstrap','--root'",1)
    old='from tools.nvarc_e10_ttt_probe import finalize'
    require(body.count(old)==1,'one finalizer hook required')
    body=body.replace(old,'from tools.nvarc_e11_paired_floor import finalize',1)
    if plan['resource_budget_profile']==BUDGET_45:
        old='from tools.nvarc_process_supervisor import supervise'
        require(body.count(old)==1,'one E11 supervisor hook required')
        body=body.replace(old,'from tools.nvarc_e11_cleanup import supervise',1)
    old="or not diagnostics.get('final_archive_created'):"
    require(body.count(old)==1,'one E11 finalization qualification hook required')
    body=body.replace(old,"or not diagnostics.get('final_archive_created') or not diagnostics.get('finalization_qualified'):",1)
    # Before even stdlib imports, filesystem writes, unpacking or subprocesses.
    body="raise RuntimeError('INERT E11: no new exact runtime admission is implemented')\n"+body
    compile(body,'inert-e11-v9-notebook','exec')
    notebook['cells'][1]['source']=body.splitlines(keepends=True)
    ancestor.ancestor.verify_embedded_payload(notebook,raw)
    return notebook


def metadata(plan):return ancestor.metadata(plan)


def manual_editor_proposal(plan):
    validate_admission(plan)
    return dict(format='irisx/e11-manual-editor-proposal-v1',run_id=plan['run_id'],
        notebook_ref=NOTEBOOK,expected_notebook_version=9,proposed_publication_mode='QUICK_SAVE',
        agent_execution_authorized=False,owner_editor_authorized=False,runtime_authorized=False,
        publication_authorized=False,owner_execution_consent_ref=None,
        admission_status='INERT; exact manual-Editor admission remains absent')


def handoff(plan):
    validate_admission(plan)
    return dict(format='irisx/paired-dfs-floor-inert-handoff-v1',run_id=plan['run_id'],
        execute_commands=False,publication_authorized=False,runtime_authorized=False,
        agent_execution_authorized=False,owner_editor_authorized=False,approval_pending=True,
        kernel_execution_type='INERT',notebook_ref=NOTEBOOK,notebook_numeric_id=137327571,
        expected_notebook_version=9,expected_previous_version=8,training_updates=512,
        test_executions=12,maximum_processed_sequences_total=768,provider_seconds=plan['maximum_notebook_wall_seconds'],
        charged_gpu_seconds_ceiling=budget_report(plan['resource_budget_profile'])['charged_gpu_seconds_ceiling'],paid_usd_ceiling=0,monitor_after_submission=False,
        official_submission_authorized=False,resource_status=budget_report(plan['resource_budget_profile'])['status'],
        proposed_next_delivery=manual_editor_proposal(plan))


def package_manifest(plan,raw):
    files={'runtime/'+name:body for name,body in raw.items()}
    files.update({'kernel/notebook.ipynb':canonical(render(plan,raw)),
        'kernel/kernel-metadata.json':canonical(metadata(plan)),'cli-handoff.json':canonical(handoff(plan))})
    return dict(format='irisx/paired-dfs-floor-inert-package-v1',plan_digest=digest(plan),
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
    return dict(run_id=plan['run_id'],plan_digest=digest(plan),package_manifest_sha256=sha(package/'package-manifest.json'),
        offline_package_verified=True,runtime_authorized=plan['resource_admission'] is not None,
        publication_authorized=plan['resource_admission'] is not None,
        new_model_calls=0,new_provider_calls=0,gpu_probe_run=False,budget=budget_report(plan['resource_budget_profile']))

def build_from_frozen(package,frozen_runtime,commit,inference_plan,*,budget_profile=BUDGET_PROFILE):
    frozen_runtime=Path(frozen_runtime)
    require(sha(frozen_runtime/'plan.json')==ancestor.ancestor.PARENT_PLAN_SHA256 and
        sha(inference_plan)==ancestor.ancestor.INFERENCE_PLAN_SHA256,'exact accepted training and interleaved inference plans required')
    # Ancestor admissions are data only. Validate and derive material, then
    # construct independently resets every authority field to false/null.
    parent=parse_json((frozen_runtime/'plan.json').read_bytes());inferred=parse_json(Path(inference_plan).read_bytes())
    for key,count in ancestor.ancestor.TEST_COUNTS.items():
        spec=inferred['task_specs'][key]
        require(spec['test_count']==count and spec['per_test_limits']==evidence.PER_TEST and
            spec['maximum_candidate_sequences_per_test']==64 and spec['verification_schedule']=='interleaved',
            'same frozen solver/cap recipe required')
    contract=parse_json((frozen_runtime/'material-contract.json').read_bytes())
    external={name:(frozen_runtime/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json']=(frozen_runtime/'verified-tokenizer.json').read_bytes()
    plan,raw=construct(commit,external,{k:parent[k] for k in (*CONFIG_FIELDS,'native_source_learning_rates')},
        contract,parse_json((frozen_runtime/'challenges.json').read_bytes()),
        {key:parse_json((frozen_runtime/'materials'/f'{key}.json').read_bytes()) for key in ancestor.ancestor.TASKS},
        read_contract(frozen_runtime/PROOF_FILE),parent['preprocessing_environment'],exact_sources(commit),budget_profile=budget_profile)
    return stage(package,plan,raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--budget-profile',choices=tuple(RESOURCE_PROFILES),default=BUDGET_PROFILE)
    parser.add_argument('--frozen-runtime',type=Path);parser.add_argument('--source-commit')
    parser.add_argument('--inference-plan',type=Path);parser.add_argument('--expected-manifest-sha256')
    args=parser.parse_args()
    result=preflight(args.package,expected_manifest_sha256=args.expected_manifest_sha256) if args.action=='preflight' else \
        build_from_frozen(args.package,args.frozen_runtime,args.source_commit,args.inference_plan,budget_profile=args.budget_profile)
    print(json.dumps(result))


if __name__=='__main__':main()

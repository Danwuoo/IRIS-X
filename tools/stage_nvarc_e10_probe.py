"""Immutable offline native synthetic probe package. Never contacts a provider."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical,digest,require,write
from tools.stage_nvarc_e10_screen import read_materials,validate_baseline,render,sha,LOCAL_FILES,material_files,native_notice_closure
from tools.nvarc_resource_attachment import attachment,validate_attachment
from tools.nvarc_notebook_controls import cli_handoff
from tools.nvarc_dependency_readproof import (PROOF_FILE, VERSIONED_REF, bind_contract, read_contract)

FORMAT='irisx/stage4-e10-native-resource-probe-v1'
SCIENTIFIC_SCOPE='synthetic control tensors only'
OWNER_EDITOR_ADMISSION='irisx/stage4-native-probe-owner-editor-admission-v1'
OWNER_EDITOR_RUN='stage4-e10-probe-20261006-002'
OWNER_EDITOR_NOTEBOOK='danielwuu/stage4-e10-probe-20261006-001'
OWNER_EDITOR_NOTEBOOK_ID=137327571
OWNER_EDITOR_NOTEBOOK_VERSION=2
OWNER_EDITOR_RELEASES={OWNER_EDITOR_RUN:OWNER_EDITOR_NOTEBOOK_VERSION,
    'stage4-e10-probe-20261006-003':3}
UNAVAILABLE_RESOURCE_FIELDS=('quota_hours_available','quota_observed_at','allocated_gpu_hours_per_quota_hour',
    'provider_reserved_seconds','campaign_pending_actions','historical_sessions_terminal_verified',
    'owner_editor_sessions_closed')
FILES=tuple(sorted(set(LOCAL_FILES)|{'tools/nvarc_public_eval_runtime.py','tools/nvarc_e10_probe.py',
    'tools/stage_nvarc_e10_probe.py','tools/nvarc_resource_attachment.py',
    'tools/nvarc_native_ttt_budget.py','tools/nvarc_native_ttt_schedule.py','tools/nvarc_dependency_readproof.py',
    'tools/nvarc_probe_bootstrap.py'}))


def construct(probe_id,source_commit,external,config,contract,*,resource_admission=None,fixture=False,resource_check_current=True,
              dependency_readproof=None,notebook_ref=None,owner_editor_admission=None):
    require(re.fullmatch(r'stage4-e10-probe-[a-z0-9-]+',probe_id) and re.fullmatch('[0-9a-f]{40}',source_commit),
            'new immutable probe identity/full implementation commit required')
    require(owner_editor_admission is None or resource_admission is None,
            'owner-Editor save cannot reuse automatic resource admission')
    require(notebook_ref is None or owner_editor_admission is not None,
            'separate notebook identity requires explicit owner-Editor admission')
    admitted=resource_admission is not None or owner_editor_admission is not None
    if not fixture:
        validate_baseline(config,external,contract)
        if admitted:
            require(native_notice_closure(contract,external),'native source license/notice closure required before probe admission')
    raw={name:(ROOT/name).read_bytes() for name in FILES};raw.update(external)
    require(not admitted or fixture or dependency_readproof is not None,
            'admitted native probe requires separately supplied immutable selected-byte read-proof')
    if dependency_readproof is not None:
        bind_contract(dependency_readproof,parse_json(external['source-inventory.json']))
        require(config['dependency_script_version_id']==dependency_readproof['script_version_id'],
                'selected-byte proof must agree with preserved dependency script version')
        raw[PROOF_FILE]=canonical(dependency_readproof)
    for name in ('nvarc_native_ttt_budget.py','nvarc_native_ttt_schedule.py'):raw[name]=(ROOT/'tools'/name).read_bytes()
    raw['tools/__init__.py']=b''
    plan={**config,'format':FORMAT,'screen_id':probe_id,'run_id':probe_id,'source_commit':source_commit,
        'owner_decision':'Decision 0061','material_contract_digest':digest(contract),
        'approved_for_runtime':resource_admission is not None and not fixture,'resource_admission':resource_admission,
        'local_fixture':fixture,'parallel_workers':4,'worker_ids':[str(rank) for rank in range(4)],
        'hardware':'four distinct BF16 L4s; all four execute synthetic controls',
        'runtime_torch_version':'2.8.0+cu128',
        'resource_attachment':attachment(SCIENTIFIC_SCOPE),
        'maximum_notebook_wall_seconds':1800,'startup_seconds':900,'maximum_worker_seconds':600,
        'finalization_reserve_seconds':300,'allocated_gpu_hours_upper_bound':2,'paid_usd_ceiling':0,
        'maximum_forwards':28,'maximum_physical_input_tokens':672,'optimizer_steps':0,'generations':0,
        'scientific_task_runs':0,'per_worker_forwards':7,'per_worker_physical_input_tokens':168,
        'maximum_worker_host_rss_bytes':16*1024**3,'maximum_aggregate_host_rss_bytes':64*1024**3,
        'maximum_worker_cuda_allocated_bytes':24*1024**3,'minimum_free_working_bytes':10*1024**3,
        'maximum_archive_uncompressed_bytes':1024**3,'correctness_scored':False,'promotion':False,
        'ttt128_feasibility_established':False,'full_screen_scientific_task_run_ceiling':96,
        'full_screen_relationship':'separate synthetic resource probe; all first-six scientific controls remain inside the subsequent complete96-task-run screen; no cross-session result splice',
        'source_provenance':contract['source_provenance'],
        'native_notebook_notice_closure':False if fixture else native_notice_closure(contract,external),
        'complete_dependency_license_closure':False,
        'dependency_readproof_digest':None if dependency_readproof is None else digest(dependency_readproof),
        'declared_dependency_source':VERSIONED_REF,
        'provider_resolved_dependency_version_verified':False,
        'platform_parent_startup_attested':False,
        'payload_sha256':{name:hashlib.sha256(body).hexdigest() for name,body in sorted(raw.items())}}
    if owner_editor_admission is not None:
        plan.update(notebook_ref=notebook_ref,notebook_numeric_id=OWNER_EDITOR_NOTEBOOK_ID,
            expected_notebook_version=OWNER_EDITOR_RELEASES.get(probe_id),owner_editor_admission=owner_editor_admission,
            approved_for_owner_editor=not fixture,owner_editor_only=True,agent_execution_authorized=False,
            kernel_execution_type='QUICK_SAVE',resource_information_status='unavailable',
            resource_sufficiency_verified=False,resource_information={key:None for key in UNAVAILABLE_RESOURCE_FIELDS},
            provider_timeout_enforcement_observed=False,manual_editor_timeout_attested=False)
        validate_owner_editor(plan)
    if resource_admission is not None:validate_resource(resource_admission,plan,current=resource_check_current)
    raw['plan.json']=canonical(plan);raw['screen.json']=canonical(plan);raw['material-contract.json']=canonical(contract)
    return plan,raw


def validate_owner_editor(plan,*,require_approved=False):
    """An exact manual save permission, never automatic resource admission."""
    admission=plan.get('owner_editor_admission')
    require(type(admission) is dict and set(admission)=={'format','probe_id','owner_instruction_ref',
        'notebook_ref','notebook_numeric_id','expected_notebook_version','kernel_execution_type',
        'agent_execution_authorized'} and admission['format']==OWNER_EDITOR_ADMISSION and
        admission['probe_id']==plan['screen_id']==plan['run_id'] and plan['run_id'] in OWNER_EDITOR_RELEASES and
        admission['notebook_ref']==plan.get('notebook_ref')==OWNER_EDITOR_NOTEBOOK and
        type(admission['notebook_numeric_id']) is int and type(plan.get('notebook_numeric_id')) is int and
        admission['notebook_numeric_id']==plan['notebook_numeric_id']==OWNER_EDITOR_NOTEBOOK_ID and
        type(admission['expected_notebook_version']) is int and type(plan.get('expected_notebook_version')) is int and
        admission['expected_notebook_version']==plan['expected_notebook_version']==OWNER_EDITOR_RELEASES[plan['run_id']] and
        type(admission['owner_instruction_ref']) is str and bool(admission['owner_instruction_ref'].strip()) and
        admission['kernel_execution_type']==plan.get('kernel_execution_type')=='QUICK_SAVE' and
        admission['agent_execution_authorized'] is plan.get('agent_execution_authorized') is False,
        'exact reviewed owner-Editor release save admission required')
    require(plan.get('owner_editor_only') is True and plan['approved_for_runtime'] is False and
        plan['resource_admission'] is None and type(plan.get('approved_for_owner_editor')) is bool and
        type(plan['local_fixture']) is bool and
        plan['approved_for_owner_editor'] is (not plan['local_fixture']) and
        (not require_approved or plan['approved_for_owner_editor'] is True and plan['local_fixture'] is False),
        'owner-Editor admission cannot authorize automatic execution or fixtures')
    require(plan.get('resource_information_status')=='unavailable' and plan.get('resource_sufficiency_verified') is False and
        plan.get('resource_information')=={key:None for key in UNAVAILABLE_RESOURCE_FIELDS} and
        plan.get('provider_timeout_enforcement_observed') is False and plan.get('manual_editor_timeout_attested') is False,
        'owner-Editor save must not invent current quota/session or provider-timeout facts')
    bounds={'parallel_workers':4,'maximum_notebook_wall_seconds':1800,'startup_seconds':900,
        'maximum_worker_seconds':600,'finalization_reserve_seconds':300,'maximum_forwards':28,
        'maximum_physical_input_tokens':672,'optimizer_steps':0,'generations':0,'scientific_task_runs':0,
        'per_worker_forwards':7,'per_worker_physical_input_tokens':168,'paid_usd_ceiling':0}
    require(all(type(plan.get(key)) is int and plan[key]==value for key,value in bounds.items()) and
        plan.get('worker_ids')==['0','1','2','3'] and plan.get('runtime_torch_version')=='2.8.0+cu128' and
        plan.get('correctness_scored') is plan.get('promotion') is False,
        'owner-Editor exact four-L4 bounded synthetic-only workload required')
    validate_attachment(plan['resource_attachment'],SCIENTIFIC_SCOPE)
    return admission


def notebook_identity(plan):
    if 'owner_editor_admission' in plan:
        validate_owner_editor(plan)
        return plan['notebook_ref'],plan['notebook_ref'].split('/',1)[1]
    require('notebook_ref' not in plan,'separate notebook identity requires owner-Editor admission')
    return 'danielwuu/'+plan['screen_id'],plan['screen_id']


def validate_resource(value,plan,*,current=True):
    from datetime import datetime
    import math
    require(isinstance(value,dict) and set(value)=={'format','probe_id','paid_usd_ceiling','quota_hours_available',
        'allocated_gpu_hours_per_quota_hour','quota_observed_at','provider_session_seconds','private','internet',
        'current_resource_reconciliation','rules_materials_review_ref'} and
        value['format']=='irisx/stage4-native-probe-resource-admission-v2' and value['probe_id']==plan['screen_id'] and
        type(value['paid_usd_ceiling']) is int and value['paid_usd_ceiling']==0 and value['private'] is True and
        value['internet'] is False and
        isinstance(value['rules_materials_review_ref'],str) and bool(value['rules_materials_review_ref']) and
        all(type(value[k]) in (int,float) and math.isfinite(value[k]) and value[k]>0 for k in
            ('quota_hours_available','allocated_gpu_hours_per_quota_hour','provider_session_seconds')) and
        value['quota_hours_available']>=2/value['allocated_gpu_hours_per_quota_hour'] and
        value['provider_session_seconds']>=1800,'verified finite free native probe resource admission required')
    reconciliation=value['current_resource_reconciliation']
    require(type(reconciliation) is dict and set(reconciliation)=={
        'quota_snapshot_sha256','provider_reserved_seconds','campaign_pending_actions',
        'historical_sessions_terminal_verified','scope'} and
        type(reconciliation['quota_snapshot_sha256']) is str and
        re.fullmatch('[0-9a-f]{64}',reconciliation['quota_snapshot_sha256']) and
        type(reconciliation['provider_reserved_seconds']) in (int,float) and
        reconciliation['provider_reserved_seconds']==0 and
        type(reconciliation['campaign_pending_actions']) is int and
        reconciliation['campaign_pending_actions']==0 and
        reconciliation['historical_sessions_terminal_verified'] is False and
        reconciliation['scope']=='current-provider-quota-and-local-campaign-only',
        'fresh zero-reservation provider snapshot and clear local campaign required; historical states stay unknown')
    require(datetime.fromisoformat(value['quota_observed_at'].replace('Z','+00:00')).utcoffset() is not None,
            'timezone-qualified probe quota observation required')
    if current:
        import time
        age=time.time()-datetime.fromisoformat(value['quota_observed_at'].replace('Z','+00:00')).timestamp()
        require(-5<=age<=3600,'probe quota observation must be current within one hour and not future')


def verify_runtime(root,*,require_approved=False,require_owner_editor=False):
    root=Path(root);plan=parse_json((root/'plan.json').read_bytes())
    require(not (require_approved and require_owner_editor),'one explicit execution admission context required')
    require(plan['format']==FORMAT and plan==parse_json((root/'screen.json').read_bytes()) and
        (not require_approved or plan['approved_for_runtime'] is True and plan['local_fixture'] is False),
        'distinct admitted native resource probe required')
    manual='owner_editor_admission' in plan
    require(not require_owner_editor or manual,'explicit owner-Editor admission required')
    if manual:validate_owner_editor(plan,require_approved=require_owner_editor)
    validate_attachment(plan['resource_attachment'],SCIENTIFIC_SCOPE)
    require(plan['runtime_torch_version']=='2.8.0+cu128','exact native CUDA-build version required')
    for name,expected in plan['payload_sha256'].items():
        path=root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and sha(path)==expected,
                'immutable native probe source/material differs: '+name)
    if plan['approved_for_runtime'] or plan.get('approved_for_owner_editor') is True:
        proof=read_contract(root/PROOF_FILE)
        require(plan['dependency_readproof_digest']==digest(proof) and
            PROOF_FILE in plan['payload_sha256'] and plan['declared_dependency_source']==VERSIONED_REF and
            plan['provider_resolved_dependency_version_verified'] is plan['platform_parent_startup_attested'] is False,
            'admitted probe requires immutable selected-byte proof with limited mount/startup claims')
        bind_contract(proof,parse_json((root/'source-inventory.json').read_bytes()))
        require(plan['dependency_script_version_id']==proof['script_version_id'],
                'selected-byte proof must retain dependency script identity')
        contract=parse_json((root/'material-contract.json').read_bytes())
        external={name:(root/name).read_bytes() for name in material_files(contract)}
        require(plan['native_notebook_notice_closure'] is True and native_notice_closure(contract,external),
            'admitted probe requires exact native source notice closure')
        if not manual:validate_resource(plan['resource_admission'],plan,current=require_approved)
    return plan


def stage(package,plan,raw):
    package=Path(package);require(not package.exists(),'new immutable native probe package required')
    (package/'runtime').mkdir(parents=True);(package/'kernel').mkdir()
    for name,body in raw.items():
        path=package/'runtime'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    notebook=render(plan,raw,entrypoint='tools/nvarc_e10_probe.py',description=[
        'Private native SFT139 synthetic load/cache/reset probe.\n',
        'Four L4s; at most28 forwards/672 physical synthetic tokens; zero optimizer/generation/ARC task-runs.\n',
        'This does not establish full TTT128 resource feasibility or E10 quality.\n'])
    write(package/'kernel/notebook.ipynb',notebook)
    notebook_ref,notebook_title=notebook_identity(plan)
    write(package/'kernel/kernel-metadata.json',{'id':notebook_ref,'title':notebook_title,
        'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':True,
        'enable_internet':False,'machine_shape':'NvidiaL4','docker_image':plan['docker_image'],'docker_image_pinning_type':'original',
        'dataset_sources':[],'kernel_sources':[VERSIONED_REF],
        'competition_sources':plan['resource_attachment']['competition_sources'],'model_sources':plan['model_sources']})
    write(package/'cli-handoff.json',cli_handoff(plan))
    write(package/'package-manifest.json',{'format':'irisx/e10-probe-package-v1','plan_digest':digest(plan),
        'files_sha256':{path.relative_to(package).as_posix():sha(path) for path in sorted(package.rglob('*')) if path.is_file()}})
    return preflight(package)


def preflight(package,*,expected_manifest_sha256=None):
    package=Path(package);manifest=parse_json((package/'package-manifest.json').read_bytes())
    require(not package.is_symlink() and not any(path.is_symlink() for path in package.rglob('*')) and
        manifest['files_sha256']=={path.relative_to(package).as_posix():sha(path) for path in package.rglob('*')
            if path.is_file() and path.relative_to(package).as_posix()!='package-manifest.json'},'closed immutable probe package inventory differs')
    if expected_manifest_sha256 is not None:require(sha(package/'package-manifest.json')==expected_manifest_sha256,
                                                   'independent probe package pin differs')
    plan=verify_runtime(package/'runtime')
    require(manifest['plan_digest']==digest(plan),'native probe plan binding differs')
    contract=parse_json((package/'runtime/material-contract.json').read_bytes())
    external={name:(package/'runtime'/name).read_bytes() for name in (
        __import__('tools.stage_nvarc_e10_screen',fromlist=['EXTERNAL_FILES']).EXTERNAL_FILES if plan['local_fixture'] else material_files(contract))}
    external['verified-tokenizer.json']=(package/'runtime/verified-tokenizer.json').read_bytes()
    config={key:plan[key] for key in __import__('tools.stage_nvarc_e10_screen',fromlist=['CONFIG_FIELDS']).CONFIG_FIELDS}
    config['native_source_learning_rates']=plan['native_source_learning_rates']
    expected,raw=construct(plan['screen_id'],plan['source_commit'],external,config,
        parse_json((package/'runtime/material-contract.json').read_bytes()),fixture=plan['local_fixture'],
        resource_admission=plan['resource_admission'],resource_check_current=False,
        dependency_readproof=read_contract(package/'runtime'/PROOF_FILE) if plan['dependency_readproof_digest'] is not None else None,
        notebook_ref=plan.get('notebook_ref'),owner_editor_admission=plan.get('owner_editor_admission'))
    closed_names={'runtime/'+name for name in raw}|{'kernel/notebook.ipynb','kernel/kernel-metadata.json','cli-handoff.json'}
    require(set(manifest['files_sha256'])==closed_names,'exact closed probe package membership differs')
    require(parse_json((package/'cli-handoff.json').read_bytes())==cli_handoff(plan),
            'exact offline probe CLI provider-cap handoff differs')
    require(plan==expected and all((package/'runtime'/name).read_bytes()==body for name,body in raw.items()),
            'exact native probe source/config/budget reconstruction differs')
    require(parse_json((package/'kernel/notebook.ipynb').read_bytes())==render(plan,raw,
        entrypoint='tools/nvarc_e10_probe.py',description=['Private native SFT139 synthetic load/cache/reset probe.\n',
            'Four L4s; at most28 forwards/672 physical synthetic tokens; zero optimizer/generation/ARC task-runs.\n',
            'This does not establish full TTT128 resource feasibility or E10 quality.\n']),
        'exact native probe notebook differs')
    notebook_ref,notebook_title=notebook_identity(plan)
    require(parse_json((package/'kernel/kernel-metadata.json').read_bytes())=={
        'id':notebook_ref,'title':notebook_title,'code_file':'notebook.ipynb','language':'python',
        'kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,'machine_shape':'NvidiaL4',
        'docker_image':plan['docker_image'],'docker_image_pinning_type':'original','dataset_sources':[],
        'kernel_sources':[VERSIONED_REF],
        'competition_sources':attachment(SCIENTIFIC_SCOPE)['competition_sources'],'model_sources':plan['model_sources']},
        'exact private offline probe metadata differs')
    return {'probe_id':plan['screen_id'],'plan_digest':digest(plan),'package_manifest_sha256':sha(package/'package-manifest.json'),
        'offline_package_verified':True,'approved_for_runtime':plan['approved_for_runtime'],'new_model_calls':0,
        'planned_maximum_model_calls':28,'scientific_task_runs':0,'gpu_probe_run':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True)
    for name in ('materials','material-contract','template','tokenizer','resource-admission','dependency-readproof','owner-editor-admission'):parser.add_argument('--'+name,type=Path)
    parser.add_argument('--notebook-ref')
    parser.add_argument('--probe-id');parser.add_argument('--source-commit');parser.add_argument('--expected-manifest-sha256')
    args=parser.parse_args()
    if args.action=='preflight':value=preflight(args.package,expected_manifest_sha256=args.expected_manifest_sha256)
    else:
        for name in FILES:
            require(subprocess.run(['git','show',args.source_commit+':'+name],cwd=ROOT,capture_output=True,check=True).stdout==
                    (ROOT/name).read_bytes(),'native probe needs exact committed implementation: '+name)
        external,config,contract=read_materials(args.materials,args.material_contract,args.template,args.tokenizer)
        admission=parse_json(args.resource_admission.read_bytes()) if args.resource_admission else None
        plan,raw=construct(args.probe_id,args.source_commit,external,config,contract,resource_admission=admission,
            dependency_readproof=read_contract(args.dependency_readproof) if args.dependency_readproof else None,
            notebook_ref=args.notebook_ref,
            owner_editor_admission=parse_json(args.owner_editor_admission.read_bytes()) if args.owner_editor_admission else None)
        value=stage(args.package,plan,raw)
    print(json.dumps(value))


if __name__=='__main__':main()

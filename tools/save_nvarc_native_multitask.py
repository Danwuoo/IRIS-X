"""Offline preparation; one explicitly admitted owner-Editor QUICK_SAVE only.

Uses the successful native-solve SDK transport. No run/status/log/output API.
Review packages remain immutable: admission stages a distinct derived identity.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,read,sha
from tools.execute_nvarc_overnight_sft import token,client_for,utc,bindings
from tools.nvarc_native_multitask import canonical,digest,require,FORMAT
from tools import stage_nvarc_native_multitask as stage

REVIEW_COMMIT='c2079c9132fe855ca69e359109069e29fa6eb707'
REVIEW_SHA='2755f5c7f3498c2eef826a4e3c2cf3b0e77bd2490c48da7bef25c958a746a3a1'
REVIEW_FILE=ROOT/'.irisx/control-review-c2079c9-caadb179/acceptance.json'
ADMISSION_FORMAT='irisx/native-multitask-editor-admission-v2'
SAVE_ONLY_ADMISSION_FORMAT='irisx/native-multitask-editor-save-only-admission-v3'
RESOURCE_EXCEPTION_REF='docs/decisions/0057-save-native-multitask-with-unavailable-quota.md'
RESOURCE_EXCEPTION_RUN='nvarc-original-qwen3-native-multitask-008'
RESOURCE_EXCEPTION_REVIEW_RUN='nvarc-original-qwen3-native-multitask-007'
RESOURCE_EXCEPTION_PLAN='sha256:ccacce536d11058dd9d3d0b531f68a0c6e6dc1a49ba52c2bc8e263e76534abef'
RESOURCE_EXCEPTION_NOTEBOOK='a4d9d481fa2693f8b9a1d79a363e804532171d396d3fbf1dc6b0cac7131e1e19'
UNAVAILABLE_QUOTA_FIELDS=('reserved_quota_hours','quota_observed_at','l4_quota_multiplier','quota_reservation_id')
EXPORT_SAVE_ADMISSION_FORMAT='irisx/native-multitask-editor-save-only-admission-v4'
EXPORT_SAVE_REF='docs/decisions/0058-save-native-multitask-export-repair.md'
EXPORT_SAVE_RUN='nvarc-original-qwen3-native-multitask-010'
EXPORT_REVIEW_RUN='nvarc-original-qwen3-native-multitask-009'
EXPORT_REVIEW_PLAN='sha256:02ac331440fdb44642225bc5f9977fb18f7af8c1ccab32ffb532f4a6292bb75d'
EXPORT_REVIEW_NOTEBOOK='8641f929504f77182992d362669af532fbde4f134a5154237c8473d781fa9b32'
EXPORT_SOURCE_COMMIT='425d3e0f96b05df95e933ee524815c58545ebe4b'
UNAVAILABLE_EXPORT_FACTS=UNAVAILABLE_QUOTA_FIELDS+('prior_sessions_reconciled','owner_editor_sessions_closed')
SAVE_URL='https://api.kaggle.com/v1/kernels.KernelsApiService/SaveKernel'


def identity(value):
    require(isinstance(value,str) and re.fullmatch(r'nvarc-original-qwen3-native-multitask-\d{3}',value),
        'exact native multi-task identity required')
    return value


def paths(run):
    root=ROOT/'.irisx/nvarc-original/runs'/identity(run)
    return root,root/'package-l4',root/'editor-save-final'


def validate_admission(path,run):
    value=read(path)
    if value.get('format')==EXPORT_SAVE_ADMISSION_FORMAT:
        return validate_export_save_admission(value,run)
    fields={'format','run_id','reviewed_run_id','reviewed_plan_digest','reviewed_notebook_sha256',
        'source_commit','control_review_sha256','maximum_paid_usd','prior_sessions_reconciled',
        'quota_reservation_id','reserved_quota_hours','quota_observed_at','local_resource_admission',
        'ui_operator','private','internet','owner_editor_sessions_closed','owner_clearance_ref',
        'l4_quota_multiplier','quick_save_authorized','maximum_quick_saves','agent_execution_authorized'}
    save_only=value.get('format')==SAVE_ONLY_ADMISSION_FORMAT
    if save_only:
        fields|={'resource_information_status','resource_information_unavailable',
            'owner_resource_exception_ref','owner_resource_exception_sha256'}
    require(set(value)==fields and value['format'] in (ADMISSION_FORMAT,SAVE_ONLY_ADMISSION_FORMAT) and value['run_id']==identity(run) and
        identity(value['reviewed_run_id'])!=run and value['source_commit']==REVIEW_COMMIT and
        value['control_review_sha256']==REVIEW_SHA and sha(REVIEW_FILE)==REVIEW_SHA and
        type(value['maximum_paid_usd']) is int and value['maximum_paid_usd']==0 and
        value['prior_sessions_reconciled'] is value['owner_editor_sessions_closed'] is
            value['quick_save_authorized'] is value['private'] is True and
        value['internet'] is value['agent_execution_authorized'] is False and value['ui_operator']=='user' and
        type(value['maximum_quick_saves']) is int and value['maximum_quick_saves']==1 and
        isinstance(value['owner_clearance_ref'],str) and bool(value['owner_clearance_ref'].strip()),
        'exact owner/controller save clearance required')
    if save_only:
        # The owner explicitly waived missing resource information for this one
        # save. Nulls remain unknown; this never asserts a quota reservation.
        require(run==RESOURCE_EXCEPTION_RUN and value['reviewed_run_id']==RESOURCE_EXCEPTION_REVIEW_RUN and
            value['reviewed_plan_digest']==RESOURCE_EXCEPTION_PLAN and
            value['reviewed_notebook_sha256']==RESOURCE_EXCEPTION_NOTEBOOK and
            value['local_resource_admission'] is False and
            all(value[k] is None for k in UNAVAILABLE_QUOTA_FIELDS) and
            value['resource_information_status']=='unavailable' and
            value['resource_information_unavailable']==list(UNAVAILABLE_QUOTA_FIELDS) and
            value['owner_resource_exception_ref']==RESOURCE_EXCEPTION_REF and
            value['owner_resource_exception_sha256']==sha(ROOT/RESOURCE_EXCEPTION_REF),
            'only exact 008 owner-authorized save exception with explicitly unavailable quota permitted')
    else:
        require(value['local_resource_admission'] is True and
            isinstance(value['quota_reservation_id'],str) and bool(value['quota_reservation_id'].strip()) and
            type(value['reserved_quota_hours']) in (int,float) and math.isfinite(value['reserved_quota_hours']) and
            value['reserved_quota_hours']>=2.5 and type(value['l4_quota_multiplier']) in (int,float) and
            value['l4_quota_multiplier']==2 and isinstance(value['quota_observed_at'],str),
            'exact owner/controller admission with real closed sessions and reserved quota required')
        require(datetime.fromisoformat(value['quota_observed_at'].replace('Z','+00:00')).utcoffset() is not None,
            'timezone-qualified quota observation required')
    _,reviewed,_=paths(value['reviewed_run_id'])
    checked=stage.preflight(reviewed)
    require(checked['approved_for_runtime'] is False and checked['plan_digest']==value['reviewed_plan_digest'] and
        sha(reviewed/'kernel/notebook.ipynb')==value['reviewed_notebook_sha256'],
        'exact frozen unapproved review candidate required')
    return value


def validate_export_save_admission(value,run):
    """Exact 009-to-010 save approval; unavailable facts remain null."""
    fields={'format','run_id','reviewed_run_id','reviewed_plan_digest','reviewed_notebook_sha256',
        'source_commit','control_review_sha256','maximum_paid_usd','prior_sessions_reconciled',
        'quota_reservation_id','reserved_quota_hours','quota_observed_at','local_resource_admission',
        'ui_operator','private','internet','owner_editor_sessions_closed','owner_clearance_ref',
        'l4_quota_multiplier','quick_save_authorized','maximum_quick_saves','agent_execution_authorized',
        'resource_information_status','resource_information_unavailable',
        'owner_resource_exception_ref','owner_resource_exception_sha256'}
    require(set(value)==fields and value['format']==EXPORT_SAVE_ADMISSION_FORMAT and
        run==value['run_id']==EXPORT_SAVE_RUN and value['reviewed_run_id']==EXPORT_REVIEW_RUN and
        value['reviewed_plan_digest']==EXPORT_REVIEW_PLAN and
        value['reviewed_notebook_sha256']==EXPORT_REVIEW_NOTEBOOK and
        value['source_commit']==EXPORT_SOURCE_COMMIT and value['control_review_sha256']==REVIEW_SHA and
        sha(REVIEW_FILE)==REVIEW_SHA and type(value['maximum_paid_usd']) is int and value['maximum_paid_usd']==0 and
        value['quick_save_authorized'] is value['private'] is True and
        value['internet'] is value['agent_execution_authorized'] is value['local_resource_admission'] is False and
        value['ui_operator']=='user' and type(value['maximum_quick_saves']) is int and value['maximum_quick_saves']==1 and
        value['owner_clearance_ref']=='Decision 0058; owner instruction: 提交' and
        all(value[k] is None for k in UNAVAILABLE_EXPORT_FACTS) and
        value['resource_information_status']=='unavailable' and
        value['resource_information_unavailable']==list(UNAVAILABLE_EXPORT_FACTS) and
        value['owner_resource_exception_ref']==EXPORT_SAVE_REF and
        value['owner_resource_exception_sha256']==sha(ROOT/EXPORT_SAVE_REF),
        'only exact owner-authorized 009-to-010 save with unavailable resource/session facts permitted')
    _,reviewed,_=paths(EXPORT_REVIEW_RUN)
    checked=stage.preflight(reviewed)
    require(checked['approved_for_runtime'] is False and checked['plan_digest']==EXPORT_REVIEW_PLAN and
        sha(reviewed/'kernel/notebook.ipynb')==EXPORT_REVIEW_NOTEBOOK,
        'exact frozen unapproved export-repair review candidate required')
    return value


def prepare_admitted(reviewed,package,path):
    """Local only. Requires supplied genuine facts; never writes an admission."""
    value=read(path);run=identity(value['run_id']);_,expected,_=paths(run)
    require(package.resolve()==expected.resolve() and reviewed.resolve()==paths(value['reviewed_run_id'])[1].resolve(),
        'fixed new package and exact reviewed candidate required')
    validate_admission(path,run)
    return stage.stage(package,run,path)


def request_fields(package,*,admitted=True):
    plan=read(package/'plan.json');run=identity(plan['run_id']);meta=read(package/'kernel/kernel-metadata.json')
    require(plan['format']==FORMAT and plan['kernel_id']==meta['id']=='danielwuu/'+run and meta['title']==run and
        plan['owner_editor_only'] is True and plan['agent_execution_authorized'] is False and
        plan['kernel_execution_type']=='QUICK_SAVE' and plan['maximum_notebook_wall_seconds']==3600 and
        plan['maximum_child_wall_seconds']==1000,'exact manual multi-task save envelope required')
    if admitted:
        admission=validate_admission(package/'controller-admission.json',run)
        require(plan['approved'] is True and plan['controller_admission']==admission and
            plan['controller_admission_sha256']==sha(package/'controller-admission.json') and
            plan['approved_proposal_plan_digest']==admission['reviewed_plan_digest'],
            'save requires separately admitted immutable derived package')
    require(set(meta)=={'code_file','competition_sources','dataset_sources','docker_image','enable_gpu',
        'enable_internet','id','is_private','kernel_sources','kernel_type','language','model_sources','title'} and
        meta['is_private'] is meta['enable_gpu'] is True and meta['enable_internet'] is False and
        meta['code_file']=='notebook.ipynb' and meta['language']=='python' and meta['kernel_type']=='notebook' and
        meta['dataset_sources']==[] and meta['competition_sources']==['arc-prize-2026-arc-agi-2'] and
        meta['model_sources']==['sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'] and
        meta['kernel_sources']==['sorokin/pip-install-unsloth-flash-patch'] and
        meta['docker_image']==plan['docker_image'],'exact native008 material mounts required')
    notebook=read(package/'kernel/notebook.ipynb')
    for cell in notebook['cells']:
        require(cell['cell_type']=='code' and cell['execution_count'] is None and cell['outputs']==[],
            'unexecuted exact notebook required')
        if isinstance(cell['source'],list):cell['source']=''.join(cell['source'])
    return dict(slug=meta['id'],new_title=meta['title'],text=json.dumps(notebook,ensure_ascii=False),
        language='python',kernel_type='notebook',is_private=True,enable_gpu=True,enable_tpu=False,
        enable_internet=False,session_timeout_seconds=3600,dataset_data_sources=meta['dataset_sources'],
        competition_data_sources=meta['competition_sources'],kernel_data_sources=meta['kernel_sources'],
        model_data_sources=meta['model_sources'],machine_shape='NvidiaL4',docker_image=meta['docker_image'],
        kernel_execution_type='QUICK_SAVE')


def request(package,*,admitted=True):
    from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
    from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
    req=ApiSaveKernelRequest();fields=request_fields(package,admitted=admitted)
    for key,value in fields.items():
        require(hasattr(req,key),'installed SDK lacks legal SaveKernel field: '+key)
        setattr(req,key,KernelExecutionType.QUICK_SAVE if key=='kernel_execution_type' else value)
    wire=req.to_dict()
    expected={''.join([key.split('_')[0]]+[part.title() for part in key.split('_')[1:]]):value
        for key,value in fields.items() if key not in {'enable_tpu','enable_internet','dataset_data_sources'}}
    # The installed SDK omits zero/default fields. Accept only those omissions.
    require({k:v for k,v in wire.items() if k not in {'enableTpu','enableInternet','datasetDataSources'}}==expected and
        wire.get('enableTpu',False) is False and wire.get('enableInternet',False) is False and
        wire.get('datasetDataSources',[])==[],'SDK wire fields or QUICK_SAVE semantics differ')
    return req,wire


def execute(action,package):
    plan=read(package/'plan.json');run=identity(plan['run_id']);root,expected,journal_dir=paths(run)
    require(package.resolve()==expected.resolve(),'identity has one fixed package/journal')
    require(action in {'review','init','save'},'save-only action required')
    checked=stage.preflight(package)
    ledger,wire_path,receipt_path=(journal_dir/name for name in ('save-ledger.json','save-request.json','save-receipt.json'))
    claim=root/'quick-save-reservation.json'
    if action in {'review','init'}:
        require(not claim.exists(),'reserved identity cannot be prepared again')
        require(not journal_dir.exists(),'identity already prepared; preserve its sole journal')
        require((plan['approved'] is False) if action=='review' else (plan['approved'] is True),
            'review is inert; init requires admitted package')
        _,wire=request(package,admitted=action=='init')
        journal_dir.mkdir(parents=True,exist_ok=False)
        atomic(journal_dir/'preflight.json',checked);atomic(wire_path,wire)
        atomic(ledger,{'format':'irisx/native-multitask-editor-save-v1','run_id':run,
            'execution_type':'QUICK_SAVE','review_only':action=='review','push_reserved':0,
            'status_checks_reserved':0,'retrieval_reserved':0,'agent_execution_authorized':False,
            'bindings':bindings(package),'request_sha256':sha(wire_path),'prepared_utc':utc(),'events':[]})
        return dict(checked,review_only=action=='review',request_sha256=sha(wire_path),provider_calls=0)
    journal=read(ledger)
    require(journal['format']=='irisx/native-multitask-editor-save-v1' and journal['run_id']==run and
        journal['execution_type']=='QUICK_SAVE' and journal['review_only'] is False and
        journal['agent_execution_authorized'] is False and
        all(type(journal[k]) is int and journal[k]==0 for k in ('push_reserved','status_checks_reserved','retrieval_reserved')) and
        journal['events']==[] and journal['bindings']==bindings(package) and journal['request_sha256']==sha(wire_path) and
        not receipt_path.exists(),'exact unused admitted save journal required')
    req,wire=request(package);require(wire==read(wire_path),'prepared request differs')
    event={'action':'SaveKernel','execution_type':'QUICK_SAVE','reserved_utc':utc(),'outcome':'unknown-no-retry'}
    # Exclusive durable claim survives crashes and alternate init paths. Reserve
    # before credential/provider IO. No exception or unknown outcome revives it.
    with claim.open('xb') as stream:
        stream.write(canonical({'run_id':run,'request_sha256':sha(wire_path),'reserved_utc':event['reserved_utc']}))
        stream.flush();os.fsync(stream.fileno())
    journal['push_reserved']=1;journal['events'].append(event);atomic(ledger,journal)
    sends=[]
    try:
        with client_for(token()) as client:
            http=client.http_client();http._init_session();session=http._session;original=session.send
            def exact_send(prepared,**kwargs):
                require(prepared.method=='POST' and prepared.url==SAVE_URL and not sends and
                    json.loads(prepared.body)==wire,'only one exact QUICK_SAVE POST permitted')
                sends.append('SaveKernel/QUICK_SAVE');return original(prepared,**kwargs)
            session.send=exact_send
            response=client.kernels.kernels_api_client.save_kernel(req)
            receipt=response.to_dict();atomic(receipt_path,receipt)
            invalid=any(receipt.get(k) for k in ('invalidDatasetSources','invalidCompetitionSources','invalidKernelSources','invalidModelSources'))
            accepted=(len(sends)==1 and not response.error and type(response.version_number) is int and
                response.version_number==1 and not invalid and response.url=='https://www.kaggle.com/code/danielwuu/'+run)
            journal.update(accepted=accepted,provider_version=response.version_number,url=response.url)
            event.update(completed_utc=utc(),sends=len(sends),receipt_sha256=sha(receipt_path),
                outcome='accepted-save-only' if accepted else 'rejected-or-unknown-no-retry')
            atomic(ledger,journal)
            require(accepted,'rejected or unknown QUICK_SAVE; identity frozen')
            return {'accepted':True,'run_id':run,'provider_version':1,'url':response.url,
                'agent_execution_started':False,'runtime':'unobserved','status_or_output_calls':0}
    except BaseException as error:
        event.update(completed_utc=utc(),sends=len(sends),error_type=type(error).__name__)
        if getattr(error,'response',None) is not None:event['http_status']=error.response.status_code
        atomic(ledger,journal)
        raise RuntimeError('QUICK_SAVE failed or unknown; identity frozen; no retry') from None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('review','admit','init','save'))
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--reviewed-package',type=Path);parser.add_argument('--admission',type=Path)
    args=parser.parse_args()
    result=prepare_admitted(args.reviewed_package,args.package,args.admission) if args.action=='admit' else execute(args.action,args.package)
    print(json.dumps(result))


if __name__=='__main__':main()

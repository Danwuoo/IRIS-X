"""Offline immutable native multi-task validation package; never calls Kaggle."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import subprocess
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools import stage_nvarc_native_solve as frozen
from tools import nvarc_native_multitask_render as render
from tools.nvarc_native_multitask import canonical,digest,require,write,FORMAT,validate_challenges,public_training_material
from tools.nvarc_native_solve_runtime import load_sources,SOURCE_HASHES

CHALLENGES=ROOT/'.irisx/nvarc-source-bundle-9198fd4-v4/NVARC/external/TinyRecursiveModels/kaggle/combined/arc-agi_training2_challenges.json'
CHALLENGES_SHA='779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5'
TASKS=('44f52bb0','833966f4')
MODEL=ROOT/'.irisx/nvarc-original/materials/qwen3-published-sft139-20261002-001'
# Historical 001..010 constructors must not silently rebind old identities to
# later instrumentation. Their reviewed native producers are immutable Git data.
LEGACY_PRODUCER_COMMIT='cd3d93242f4a46c553ae349002778ea2885faa21'
FILES={'solver.py':'solver','arc_loader.py':'loader','arc_decoder.py':'decoder','inspection.py':'worker',
    'inspection_helpers.py':'helper','nvarc_native_ttt_budget.py':'budget','nvarc_native_ttt_schedule.py':'schedule',
    'hardware_helpers.py':'hardware','challenges.json':'challenges','tools/arc_kaggle_submission.py':'exporter',
    'tools/nvarc_native_solve_runtime.py':'solve_runtime','tools/nvarc_native_multitask.py':'multitask',
    'tools/nvarc_native_submission.py':'bridge','editor-archive.py':'editor_archive'}


def files_for(raw):
    files=dict(FILES)
    if 'native_export' in raw:files['tools/nvarc_native_export.py']='native_export'
    if 'output_lifecycle' in raw:files['tools/nvarc_output_lifecycle.py']='output_lifecycle'
    return files


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def producer_bytes(run_id,name):
    if int(run_id.rsplit('-',1)[1])<=10:
        return subprocess.run(['git','show',LEGACY_PRODUCER_COMMIT+':tools/'+name],
            cwd=ROOT,capture_output=True,check=True).stdout
    return (ROOT/'tools'/name).read_bytes()


def training_material(challenges, directory, tokenizer):
    import numpy as np
    loader,_,_=load_sources(directory,SimpleNamespace(no_grad=lambda:lambda f:f),np)
    return {task_id:public_training_material(loader,tokenizer,task_id,task) for task_id,task in challenges.items()}


def admission_for(path,run_id):
    if path is None:return None
    from datetime import datetime
    import math
    value=json.loads(Path(path).read_bytes())
    if value.get('format') in ('irisx/native-multitask-editor-admission-v2',
            'irisx/native-multitask-editor-save-only-admission-v3',
            'irisx/native-multitask-editor-save-only-admission-v4'):
        from tools.save_nvarc_native_multitask import validate_admission
        return validate_admission(Path(path),run_id)
    fields={'format','run_id','control_sha256','source_commit','maximum_paid_usd','prior_sessions_reconciled',
        'quota_reservation_id','reserved_quota_hours','quota_observed_at','local_resource_admission','ui_operator',
        'private','internet','owner_editor_sessions_closed','owner_clearance_ref','l4_quota_multiplier'}
    require(set(value)==fields and value['format']=='irisx/controller-gpu-admission-v1' and
        value['run_id']==run_id and value['source_commit']=='a1f68d2981c820e0256cf551c47a8b31894df1a1' and
        value['control_sha256']==frozen.CONTROL_SHA and type(value['maximum_paid_usd']) is int and value['maximum_paid_usd']==0 and
        value['prior_sessions_reconciled'] is value['owner_editor_sessions_closed'] is value['local_resource_admission'] is True and
        value['private'] is True and value['internet'] is False and value['ui_operator']=='user' and
        isinstance(value['owner_clearance_ref'],str) and bool(value['owner_clearance_ref']) and
        isinstance(value['quota_reservation_id'],str) and bool(value['quota_reservation_id']) and
        type(value['reserved_quota_hours']) in (int,float) and math.isfinite(value['reserved_quota_hours']) and
        value['reserved_quota_hours']>=2.5 and type(value['l4_quota_multiplier']) in (int,float) and
        value['l4_quota_multiplier']==2,'explicit exact owner-Editor resource admission required')
    require(datetime.fromisoformat(value['quota_observed_at'].replace('Z','+00:00')).utcoffset() is not None,
        'timezone-qualified quota observation required')
    return value


def construct(run_id,admission_path=None):
    require(re.fullmatch(r'nvarc-original-qwen3-native-multitask-\d{3}',run_id),'new distinct multi-task identity required')
    isolated_export=int(run_id.rsplit('-',1)[1])>=9
    previous,raw,_,bodies=frozen.frozen_inputs()
    require(sha(CHALLENGES)==CHALLENGES_SHA,'exact retained public training2 source required')
    challenges={k:json.loads(CHALLENGES.read_bytes())[k] for k in TASKS}
    validate_challenges(challenges)
    inventory=json.loads((MODEL/'independent-verification.json').read_bytes())['inventory']
    require(sha(MODEL/'model/tokenizer.json')==inventory['tokenizer.json']['sha256'] and
            digest(inventory)==previous['model_material_digest'],'exact published tokenizer/material identity required')
    from tokenizers import Tokenizer
    tok=Tokenizer.from_file(str(MODEL/'model/tokenizer.json'))
    class Tokens:
        def encode(self,text):return tok.encode(text).ids
        def decode(self,values):return tok.decode(values,skip_special_tokens=False)
    directory=frozen.LONG_PACKAGE/'source-bundle/kaggle-qwen'
    # Retained material contains a notebook, not extracted cells. Use a fresh
    # code-only temporary directory under the new local staging namespace.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='iris-native-code-') as temp:
        for name,body in bodies.items():(Path(temp)/name).write_bytes(body)
        materials=training_material(challenges,temp,Tokens())
    raw.update(loader=bodies['arc_loader.py'],decoder=bodies['arc_decoder.py'],visible=b'{}',
        solve_runtime=producer_bytes(run_id,'nvarc_native_solve_runtime.py'),
        multitask=producer_bytes(run_id,'nvarc_native_multitask.py'),bridge=producer_bytes(run_id,'nvarc_native_submission.py'),
        exporter=producer_bytes(run_id,'arc_kaggle_submission.py'),challenges=canonical(challenges),
        task_materials_gzip=gzip.compress(canonical(materials),mtime=0))
    raw['worker']=render.worker(raw['worker'])
    raw['editor_archive']=raw['editor_archive'].replace(b'limit = 16 * 1024**2',b"limit = plan['maximum_result_uncompressed_bytes']")
    raw['helper']=raw['helper'].replace(b"len(trainer.train_dataset) == len(expected_rows) == 128",b"len(trainer.train_dataset) == len(expected_rows)")
    raw.pop('texts_gzip');raw.pop('expected_rows');raw.pop('visible')
    producer_names=('worker','helper','budget','schedule','solve_runtime','multitask','bridge','exporter')
    if isolated_export:
        raw['native_export']=producer_bytes(run_id,'nvarc_native_export.py') if int(run_id.rsplit('-',1)[1])>10 else subprocess.run(
            ['git','show','089589652f6f4f9b3d9c3d68f4b65a2dbe331641:tools/nvarc_native_export.py'],
            cwd=ROOT,capture_output=True,check=True).stdout
        if int(run_id.rsplit('-',1)[1])>10:
            raw['output_lifecycle']=(ROOT/'tools/nvarc_output_lifecycle.py').read_bytes()
    producer={k:hashlib.sha256(raw[k]).hexdigest() for k in producer_names}
    specs={}
    for task_id,material in materials.items():
        rows=material['rows'];count=len(challenges[task_id]['test'])
        specs[task_id]={'test_count':count,'training_forwards':len(rows),'optimizer_steps':len(rows),
            'training_input_tokens':sum(r['input_tokens'] for r in rows),
            'training_supervised_tokens':sum(r['supervised_tokens'] for r in rows),
            'maximum_sequence_tokens':max(r['input_tokens'] for r in rows),
            'expected_rows_digest':digest(rows),'texts_digest':digest(material['texts']),
            'source_learning_rates':previous['source_learning_rates'],
            'inference_forward_limits':{'control':7,'generation':4096*count,'verification':128*count},
            'maximum_inference_input_tokens':5*1024**2*count,'maximum_candidate_sequences_per_test':64,
            'per_test_limits':{'generation':4096,'verification':128,'input_tokens':5*1024**2},
            'task_seconds':800,'inference_seconds':450,'inference_reserve_seconds':300,'reset_reserve_seconds':60}
    attempts=[{'attempt_id':k,'task_id':k,'mode':'solve'} for k in TASKS]+[
        {'attempt_id':'fault-first','task_id':TASKS[0],'mode':'fault-after-two-updates'},
        {'attempt_id':'baseline-after-fault','task_id':TASKS[1],'mode':'baseline-only'}]
    plan=dict(previous)
    for key in ('source_view_count','source_input_tokens','source_supervised_tokens','source_rows_digest','texts_digest',
                'source_learning_rates','uncompressed_text_bytes','source_maximum_sequence_length','views_proof_sha256',
                'approved_proposal_plan_digest','owner_execution_instruction_ref'):
        plan.pop(key,None)
    plan.update(format=FORMAT,run_id=run_id,kernel_id='danielwuu/'+run_id,approved=False,
        controller_admission=None,controller_admission_sha256=None,agent_execution_authorized=False,
        baseline_native008_plan_digest=frozen.OLD_PLAN_DIGEST,
        baseline_native008_archive_sha256='2a8acbc25e5f4b673e3982c550914728ddf8db350191cc4b9cf823db8014dfec',
        source_commit='a1f68d2981c820e0256cf551c47a8b31894df1a1',
        implementation_binding_policy='source_commit is the reviewed development baseline; new implementation bytes bind through producer_files and payload hashes',
        owner_decision='local-stage2-development-only; separate owner resource admission required',
        task_order=list(TASKS),task_specs=specs,worker_attempts=attempts,challenges_digest=digest(challenges),
        challenges_sha256=hashlib.sha256(raw['challenges']).hexdigest(),producer_sha256=digest(producer),producer_files=producer,
        original_solve_source_sha256=SOURCE_HASHES,public_source={'path':CHALLENGES.relative_to(ROOT).as_posix(),
            'sha256':CHALLENGES_SHA,'selection':'two smallest retained training2 tasks: multi-test first, single-test second',
            'test_answers_opened':False,'exposure':'published NVARC training2; prior-source exposure unresolved; no clean/holdout claim'},
        parent_ids=list(TASKS),exposure_tags=['public-training2','source-published','prior-training-exposure-unresolved'],
        hardware_gate='four distinct BF16 L4s; four sequential fresh processes on physical rank zero, other GPUs idle',
        parallel_workers=1,selected_gpu_indices=[0],maximum_notebook_wall_seconds=3600,maximum_child_wall_seconds=1000,
        packaging_reserve_seconds=240,minimum_worker_admission_seconds=240,maximum_training_forwards=258,
        maximum_training_microsteps=259,
        maximum_optimizer_steps=258,maximum_generations=12,maximum_teacher_calls=0,maximum_paid_usd=0,
        maximum_outer_forwards=258+3*(4096+128)+28,
        maximum_training_tokens=sum(s['training_input_tokens'] for s in specs.values())+
            2*specs[TASKS[0]]['maximum_sequence_tokens'],
        maximum_supervised_tokens=sum(s['training_supervised_tokens'] for s in specs.values())+
            2*specs[TASKS[0]]['maximum_sequence_tokens'],
        maximum_result_uncompressed_bytes=96*1024**2,minimum_free_working_bytes=4*1024**3,
        required_quota_reservation_hours=2.5,quota_observed_at=None,owner_editor_sessions_closed=None,
        kernel_execution_type='QUICK_SAVE',owner_editor_only=True,pythonhashseed=0,correctness_scored=False,
        scope='local inert proposal: existing original SFT -> per-task native TTT -> all tests -> eight-view ranked evidence -> submission',
        source_batch_schedule='same sixteen views and per-test partition; finish all four batches of one test before the next, rather than upstream cross-test interleaving',
        acceptance={'normal_tests':3,'nonempty_ranking_required_for_each_test':True,
            'cache_controls':'raw native deep/sibling vs full-prefix before TTT; no cache cloning',
            'isolation':'identical second-task baseline after normal task and after injected two-update first-task failure',
            'export':'all three tests and six slots; native_complete need not supply two model attempts',
            'gpu_runtime_status':'unverified'},
        expected_zip_members=['plan.json','payload-bindings.json','hardware.json','model-verification.json',
            'source-verification.json','worker-receipts.json','terminal.json','native-evidence.json','submission.json',
            'submission-audit.json','tasks/<attempt>/native/{prepared-rows,training-ledger,native-schedule,baseline-inventory,reset-inventory,result}.json',
            'tasks/<normal-task>/native/{events.jsonl,checkpoint.json,prepared-tokens.i16le}',
            'all exact producer/source scripts and public challenge bytes','manifest.json'])
    admission=admission_for(admission_path,run_id)
    if isolated_export:
        plan.update(source_commit='425d3e0f96b05df95e933ee524815c58545ebe4b',
            owner_decision='local-008-export-repair-proposal-only',
            export_verification_process='fresh-cpu-startup-hashseed-0',maximum_export_process_seconds=240,
            export_helper_sha256=hashlib.sha256(raw['native_export']).hexdigest())
        if 'output_lifecycle' in raw:
            plan['output_lifecycle_sha256']=hashlib.sha256(raw['output_lifecycle']).hexdigest()
    if admission is not None:
        plan.update(approved=True,controller_admission=admission,controller_admission_sha256=sha(admission_path))
        if admission['format'] in ('irisx/native-multitask-editor-admission-v2',
                'irisx/native-multitask-editor-save-only-admission-v3',
                'irisx/native-multitask-editor-save-only-admission-v4'):
            plan.update(source_commit=admission['source_commit'],
                owner_decision='explicit-stage3-owner-Editor-clearance',
                owner_execution_instruction_ref=admission['owner_clearance_ref'],
                approved_proposal_plan_digest=admission['reviewed_plan_digest'],
                reviewed_proposal_run_id=admission['reviewed_run_id'],
                quota_observed_at=admission['quota_observed_at'],
                owner_editor_sessions_closed=(admission['owner_editor_sessions_closed']
                    if admission['format']=='irisx/native-multitask-editor-save-only-admission-v4' else True))
            if admission['format']=='irisx/native-multitask-editor-save-only-admission-v3':
                plan.update(owner_decision='Decision 0057: owner-authorized save with quota information unavailable',
                    resource_information_status='unavailable',resource_sufficiency_verified=False)
            if admission['format']=='irisx/native-multitask-editor-save-only-admission-v4':
                plan.update(owner_decision='Decision 0058: owner-authorized export-repair save with resource/session information unavailable',
                    resource_information_status='unavailable',resource_sufficiency_verified=False)
    raw['plan']=canonical(plan)
    source=frozen.old.proposal.predecessor.base.render(run_id,
        {k:__import__('base64').b64encode(v).decode() for k,v in raw.items()},
        {k:hashlib.sha256(v).hexdigest() for k,v in raw.items()})
    source=render.parent(source,files_for(raw),raw['editor_archive'].decode(),isolated_export=isolated_export)
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
                  'source':s.splitlines(keepends=True)} for s in (source,frozen.download_cell(plan).replace('>16*1024**2','>96*1024**2'))]}
    metadata=frozen.old.proposal.predecessor.metadata(plan)
    return plan,raw,notebook,metadata


def stage(package,run_id,admission_path=None):
    require(not package.exists(),'new immutable multi-task package directory required')
    # Never create a second package for a retained identity, even in another
    # staging directory. Old stage/preflight bytes are otherwise unchanged.
    roots=ROOT/'.irisx'
    retained=list((roots/'nvarc-original/runs').glob('*/package-*/plan.json'))
    retained+=list(roots.glob('native-solve-stage*/**/plan.json'))
    require(not any(json.loads(p.read_bytes()).get('run_id')==run_id for p in retained),
        'retained native multi-task identity cannot be reused')
    plan,raw,notebook,metadata=construct(run_id,admission_path)
    (package/'kernel').mkdir(parents=True);write(package/'plan.json',plan)
    write(package/'kernel/notebook.ipynb',notebook);write(package/'kernel/kernel-metadata.json',metadata)
    if admission_path is not None:(package/'controller-admission.json').write_bytes(Path(admission_path).read_bytes())
    write(package/'stage-summary.json',{'run_id':run_id,'plan_digest':digest(plan),
        'payload_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in raw.items()},
        'inventory':{p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    saved=json.loads((package/'plan.json').read_bytes());admission=package/'controller-admission.json'
    plan,raw,notebook,metadata=construct(saved['run_id'],admission if admission.is_file() else None)
    summary=json.loads((package/'stage-summary.json').read_bytes())
    require(saved==plan and (package/'plan.json').read_bytes()==canonical(plan) and
        summary['run_id']==plan['run_id'] and summary['plan_digest']==digest(plan) and
        summary['inventory']=={p.relative_to(package).as_posix():sha(p) for p in package.rglob('*')
            if p.is_file() and p.relative_to(package).as_posix()!='stage-summary.json'} and
        not package.is_symlink() and not any(p.is_symlink() for p in package.rglob('*')) and
        json.loads((package/'kernel/notebook.ipynb').read_bytes())==notebook and
        json.loads((package/'kernel/kernel-metadata.json').read_bytes())==metadata and
        summary['payload_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()},
        'closed exact multi-task plan/material/program bytes differ')
    result={'run_id':plan['run_id'],'plan_digest':digest(plan),'offline_package_verified':True,
        'approved_for_runtime':plan['approved'],'gpu_runtime':'unverified','tasks':len(plan['task_order']),
        'test_inputs':sum(s['test_count'] for s in plan['task_specs'].values()),'external_calls':0}
    if plan.get('resource_information_status')=='unavailable':
        result.update(approved_for_runtime=False,approved_for_save=True,approved_for_owner_editor=True,
            resource_information_status='unavailable',resource_sufficiency_verified=False)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    parser.add_argument('--controller-admission',type=Path)
    args=parser.parse_args();print(json.dumps(stage(args.package,args.run_id,args.controller_admission) if args.action=='stage' else preflight(args.package)))

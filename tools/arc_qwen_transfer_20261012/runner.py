"""Owned true-ARC transfer run and separately bounded persistent checkpoint export."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import stat
import time
import zipfile
from .protocol import PROTOCOL,require,validate_config,file_sha,digest,canonical,checked_json
from .call_policy import check_active_call, finite_clock
from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard,verify_closed_proof

ROOT=Path(__file__).resolve().parents[2]
MAX_FILE_BYTES=16*1024**2
MAX_DIAGNOSTIC_BYTES=64*1024**2
LARGE_DIAGNOSTICS={'full-diagnostics.json','experiment/full-report.json','training-receipts-at-exit.json'}
MAX_TOTAL_BYTES=512*1024**2

def source_identity():
    return {p.relative_to(ROOT).as_posix():file_sha(p) for p in sorted(ROOT.rglob('*'))
            if p.is_file() and p.suffix in ('.py','.json','.jinja') and '__pycache__' not in p.parts}

def source_check(expected):
    require(source_identity()==expected,'probe source closure changed')

def operational_success(report,child):
    return bool(report.get('science_complete') and child and child.get('operational_success') and
        not any(report.get(k) for k in ('public_evaluation_error','main_scoring_error','archive_error')))


def project(report):
    keys=('format','status','science_complete','operational_success','error','reason','denominators','main_complete',
        'selection','dev_seal','holdout_seal','public_branch','physical_usage','pending_work','cpu_fixture_only',
        'dataset_path','ttt_predictions_path','ttt_predictions_sha256','interpretation','model_identity','runtime_evidence')
    result={k:report[k] for k in keys if k in report}
    if 'ttt' in report:
        result['ttt']={k:report['ttt'][k] for k in ('status','reason','denominators','planned_counts') if k in report['ttt']}
    require(len(canonical(result))<=256*1024,'bounded summary projection exceeded')
    return result

ASSET_PREFIX='experiment/checkpoint-assets'
MAX_ASSET_BYTES=2*1024**3

def checkpoint_inventory(root):
    root=Path(root);base=root/ASSET_PREFIX;files={};size=0
    if not base.exists():return {'format':'irisx/portfolio-checkpoint-assets-v1','files':{},'bytes':0,'complete_store':False}
    require(not base.is_symlink() and base.is_dir(),'regular checkpoint store required')
    for p in sorted(base.rglob('*')):
        require(not p.is_symlink(),'checkpoint asset symlink forbidden')
        mode=p.lstat().st_mode;require(stat.S_ISREG(mode) or stat.S_ISDIR(mode),'nonregular checkpoint asset')
        if stat.S_ISDIR(mode):continue
        n=p.relative_to(root).as_posix();s=p.stat().st_size
        require(s<=32*1024**2,'checkpoint asset shard/metadata bound')
        size+=s;require(size<=MAX_ASSET_BYTES and len(files)<1024,'checkpoint store aggregate bound')
        files[n]={'bytes':s,'sha256':file_sha(p)}
    manifests=[n for n in files if n.endswith('/manifest.json')]
    return {'format':'irisx/portfolio-checkpoint-assets-v1','files':files,'bytes':size,
            'checkpoint_manifest_paths':manifests,'complete_store':sum('/global_grid/' in n for n in manifests)==3,
            'contents':'separate adapter and full logical resume state; no base model weights',
            'physical_ledger_included':False}

def _zip_member(archive,path,name,expected_sha256,deadline):
    checksum=hashlib.sha256()
    with Path(path).open('rb') as source, archive.open(name,'w',force_zip64=True) as target:
        while True:
            require(time.monotonic()<deadline,'bounded archive stream deadline')
            block=source.read(1024**2)
            if not block:break
            checksum.update(block);target.write(block)
            require(time.monotonic()<deadline,'bounded archive write deadline')
    require(checksum.hexdigest()==expected_sha256,'archive member changed while streaming')


def export_checkpoints(root,inventory,*,deadline):
    import shutil
    root=Path(root);require(shutil.disk_usage(root).free>=inventory['bytes']+4*1024**3,'checkpoint export needs4GiB reserve')
    path=root/'checkpoints.zip'
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for name,row in inventory['files'].items():
            require(time.monotonic()<deadline,'checkpoint export deadline')
            p=root/name;require(file_sha(p)==row['sha256'],'closed checkpoint bytes changed')
            _zip_member(z,p,name,row['sha256'],deadline)
        _zip_member(z,root/'checkpoint-assets-manifest.json','checkpoint-assets-manifest.json',file_sha(root/'checkpoint-assets-manifest.json'),deadline)
    require(path.stat().st_size<=MAX_ASSET_BYTES+2*1024**2,'checkpoint ZIP bound')
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':file_sha(path),'files':len(inventory['files'])+1}

def _output_inventory(root):
    files={};size=0
    for p in sorted(Path(root).rglob('*')):
        require(not p.is_symlink(),'output symlink forbidden')
        mode=p.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode),'nonregular output entry denied')
        if stat.S_ISDIR(mode):continue
        n=p.relative_to(root).as_posix()
        if n in ('evidence.zip','archive-manifest.json','checkpoints.zip'):continue
        if n.startswith(ASSET_PREFIX+'/'):continue
        s=p.stat().st_size;require(s<=(MAX_DIAGNOSTIC_BYTES if n in LARGE_DIAGNOSTICS else MAX_FILE_BYTES),'output member byte ceiling exceeded')
        size+=s;require(size<=MAX_TOTAL_BYTES and len(files)<12000,'output archive bound exceeded')
        files[n]={'bytes':s,'sha256':file_sha(p)}
    return files

def archive_closed(root,proof,*,deadline):
    verify_closed_proof(proof)
    require(proof.get('closed') is True,'only stopped owner evidence may be archived')
    root=Path(root)
    if (root/ASSET_PREFIX).exists():
        asset_manifest=root/'checkpoint-assets-manifest.json'
        require(asset_manifest.is_file() and not asset_manifest.is_symlink() and asset_manifest.stat().st_size<=1024**2,'closed checkpoint inventory required before exclusion')
        require(json.loads(asset_manifest.read_bytes())==checkpoint_inventory(root),'checkpoint exclusion inventory differs')
    files=_output_inventory(root)
    manifest={'format':'irisx/qwen14b-probe-archive-v1','files':files,'owned_process_closed':True,'public_score':None}
    require(sum(e['bytes'] for e in files.values())+len(canonical(manifest))<=MAX_TOTAL_BYTES and len(files)+1<=12000,'archive manifest-inclusive bound exceeded')
    atomic_json(root/'archive-manifest.json',manifest,exclusive=True)
    with zipfile.ZipFile(root/'evidence.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for n,item in files.items():
            require(time.monotonic()<deadline,'evidence export deadline')
            p=root/n;require(file_sha(p)==item['sha256'],'output bytes changed after closure');_zip_member(z,p,n,item['sha256'],deadline)
        _zip_member(z,root/'archive-manifest.json','archive-manifest.json',file_sha(root/'archive-manifest.json'),deadline)
    return {'path':str(root/'evidence.zip'),'sha256':file_sha(root/'evidence.zip'),'files':len(files)+1,
            'bytes':(root/'evidence.zip').stat().st_size}

def run_owned_transfer(config,output,*,python_command=None):
    """Callable after independently source-bound offline interpreter preparation.

    python_command is the exact verified production offline-run.py command, or
    the explicitly tiny CPU test interpreter. The child rechecks actual runtime.
    No install/download/network/weight-copy action is performed by this function.
    """
    config=validate_config(config);root=Path(output).absolute()
    require(not any(p.is_symlink() for p in (root,*root.parents)),'regular output root required')
    require(not root.exists() and not root.is_relative_to(ROOT) and not ROOT.is_relative_to(root),'fresh nonoverlapping output root required')
    for key in ('tokenizer_path','training_root','public_solver_root','public_evaluator_root'):
        if config.get(key):
            p=Path(config[key]).absolute();require(not root.is_relative_to(p) and not p.is_relative_to(root),'input/output overlap')
    root.mkdir(parents=True);began=time.monotonic();now=time.time()
    require(config['started_epoch']<=now+2,'future pre-dispatch epoch forbidden')
    duration=config.get('maximum_seconds',PROTOCOL['maximum_seconds'])
    effective_duration=duration if config.get('tiny_cpu') else min(duration,PROTOCOL['execution_cutoff_seconds'])
    hard=began+max(0,min(effective_duration,config['started_epoch']+effective_duration-now,config['started_epoch']+PROTOCOL['maximum_session_seconds']-now))
    work_reserve=60 if config.get('tiny_cpu') else 600
    stop_reserve=30 if config.get('tiny_cpu') else 540
    require(hard-began>work_reserve+10,'probe time exhausted before launch')
    command=list(python_command or [sys.executable,'-I','-B'])
    require(command and all(type(x) is str and x for x in command),'verified interpreter command required')
    if not config.get('tiny_cpu'):
        require(len(command)==5 and command[1:4]==['-I','-B','-S'] and Path(command[4]).name=='offline-run.py',
                'production requires unchanged verified offline installer launcher')
    child_config={k:v for k,v in config.items() if k not in ('public_evaluator_root','public_evaluator_manifest_sha256')}
    request={'format':'irisx/true-arc-transfer-request-v1','config':child_config,'output_root':str(root),
             'work_deadline':hard-work_reserve,'hard_deadline':hard,'source_identity':source_identity()}
    atomic_json(root/'request.json',request,exclusive=True)
    guard=None;proof=None;error=None;forced=False;timed_out=False
    try:
        with (root/'process.log').open('xb') as log:
            guard=OwnedProcessGuard.spawn([*command,str(Path(__file__).with_name('child.py')),str(root/'request.json'),file_sha(root/'request.json')],
                evidence_dir=root/'owned-tree',cwd=str(root),stdout=log,stderr=log,start_new_session=True,close_fds=True,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
                     'HF_DATASETS_OFFLINE':'1','CUBLAS_WORKSPACE_CONFIG':':4096:8',
                     **({'CUDA_VISIBLE_DEVICES':''} if config.get('tiny_cpu') else {})})
            while guard.poll() is None:
                if time.monotonic()>=hard-stop_reserve:forced=True;break
                require((root/'process.log').stat().st_size<=1024**2,'process log exceeded1MiB')
                marker=root/'active-stage.json'
                if marker.is_file():
                    require(marker.stat().st_size<=65536 and not marker.is_symlink(),'bounded active stage required')
                    state=json.loads(marker.read_bytes())
                    stage_end=finite_clock(state.get('deadline_monotonic'),'stage deadline')
                    require(stage_end<=request['work_deadline'],'stage deadline exceeds owner work cutoff')
                    if state.get('status')=='active' and time.monotonic()>=stage_end:
                        raise TimeoutError('owned stage deadline: '+state.get('stage','unknown'))
                call=root/'active-call.json'
                if call.is_file():
                    require(call.stat().st_size<=65536 and not call.is_symlink(),'bounded active call required')
                    state=json.loads(call.read_bytes())
                    check_active_call(state,now=time.monotonic(),owner_deadline=request['work_deadline'])
                time.sleep(.2)
    except BaseException as exc:
        timed_out=isinstance(exc,TimeoutError)
        error=type(exc).__name__+': '+str(exc)[:512]
    finally:
        if guard is not None:
            try:
                try:proof=guard.closed_proof()
                except BaseException:proof=None
                if not proof or not proof.get('closed'):proof=guard.stop(timeout=5)
                verify_closed_proof(proof)
            except BaseException as exc:error='closure failure: '+type(exc).__name__+': '+str(exc)[:512]
    try:source_check(request['source_identity'])
    except BaseException as exc:error='terminal source mismatch: '+str(exc)[:512]
    clean=bool(proof and proof.get('closed') and proof.get('returncode')==0 and proof.get('worker_returncode')==0 and not proof.get('forced'))
    child=None
    p=root/'child-summary.json'
    try:
        if p.is_file():
            require(not p.is_symlink() and p.stat().st_size<=256*1024,'child summary bound exceeded');child=json.loads(p.read_bytes())
    except BaseException as exc:error='child result invalid: '+str(exc)[:512]
    report={'format':'irisx/true-arc-transfer-owned-v1',
        'status':child['status'] if clean and child and child.get('status') in ('TRANSFER_COMPLETE','TRANSFER_PARTIAL','TRANSFER_NOT_ADMITTED') and not error and not forced else 'TRANSFER_FAILED',
        'child':child,'error':error,'timed_out':forced or timed_out,'owned_process_closed':bool(proof and proof.get('closed')),
        'closure_proof':proof,'elapsed_seconds':time.monotonic()-began,'maximum_seconds':duration,
        'predispatch_started_epoch':config['started_epoch'],'global_deadline_epoch':config['started_epoch']+PROTOCOL['maximum_session_seconds'],
        'execution_cutoff_seconds':effective_duration,'provider_runtime_seconds':PROTOCOL['provider_runtime_seconds'],
        'source_identity_sha256':digest(request['source_identity']),'public_score':None,
        'public_solving_admitted':bool(child and child.get('public_branch',{}).get('status') in ('PUBLIC_PREDICTIONS_SEALED','PUBLIC_PARTIAL')),
        'goal_met':False,
        'fp8_executed':False,'four_l4_executed':False,
        'completed_epoch':time.time(),'within_probe_deadline':time.time()<=config['started_epoch']+effective_duration,
        'effective_deadline_epoch':config['started_epoch']+effective_duration,
        'within_absolute_deadline':time.time()<=config['started_epoch']+effective_duration,
        'work_reserve_seconds':work_reserve,'owner_stop_reserve_seconds':stop_reserve}
    report['science_complete']=report['status']=='TRANSFER_COMPLETE'
    report['operational_success']=operational_success(report,child)
    if clean and child and child.get('holdout_seal') and proof and proof.get('closed'):
        try:
            from .experiment import score_closed
            dataset=checked_json(child['dataset_path'],file_sha(child['dataset_path']),cap=MAX_FILE_BYTES)
            report['main_scoring']=score_closed(dataset,child,proof)
            atomic_json(root/'main-scoring.json',report['main_scoring'],exclusive=True)
        except BaseException as exc:
            report['main_scoring_error']=type(exc).__name__+': '+str(exc)[:1024]
            report['status']='TRANSFER_FAILED';report['science_complete']=report['operational_success']=False
    if clean and child and child.get('public_branch',{}).get('status')=='PUBLIC_PREDICTIONS_SEALED':
        if config.get('public_evaluator_root') and config.get('public_evaluator_manifest_sha256'):
            try:
                from .public_evaluation import seal_predictions,evaluate_sealed
                pred_root=root/'public-prediction-seal'
                sealed=seal_predictions(pred_root,solver_root=config['public_solver_root'],
                    solver_manifest_sha256=config['public_solver_manifest_sha256'],
                    evaluator_manifest_sha256=config['public_evaluator_manifest_sha256'],request_path=root/'request.json',
                    result_path=root/'child-summary.json',owner_proof=proof)
                report['public_evaluation']=evaluate_sealed(pred_root,sealed['sha256'],solver_root=config['public_solver_root'],
                    evaluator_root=config['public_evaluator_root'],output_root=root/'public-evaluation',deadline=hard-60)
                report['goal_met']=report['public_evaluation'].get('goal_met') is True
                report['public_score']=report['public_evaluation'].get('development_metrics')
                if report['public_evaluation'].get('status') not in ('PUBLIC_EVALUATION_COMPLETE','PUBLIC_EVALUATION_PARTIAL'):
                    report['public_evaluation_error']='public scoring incomplete: '+str(report['public_evaluation'].get('status'))
                    report['operational_success']=False
            except BaseException as exc:
                report['public_evaluation_error']=type(exc).__name__+': '+str(exc)[:1024]
                report['operational_success']=False
        else:report['public_evaluation_status']='SEALED_NOT_SCORED_EVALUATOR_ASSETS_ABSENT'
    atomic_json(root/'summary.json',report,exclusive=True)
    if proof and proof.get('closed'):
        try:
            assets=checkpoint_inventory(root)
            atomic_json(root/'checkpoint-assets-manifest.json',assets,exclusive=True)
            if assets['files']:
                report['checkpoint_archive']=export_checkpoints(root,assets,deadline=hard-5)
                atomic_json(root/'checkpoint-export.json',report['checkpoint_archive'],exclusive=True)
            if report['status']=='TRANSFER_COMPLETE':require(assets['complete_store'],'complete run requires all three persisted global checkpoints')
            report['archive']=archive_closed(root,proof,deadline=hard-5)
        except BaseException as exc:
            report['archive_error']=type(exc).__name__+': '+str(exc)[:512];report['status']='TRANSFER_FAILED'
        report['completed_epoch']=time.time()
        report['within_probe_deadline']=report['completed_epoch']<=config['started_epoch']+effective_duration
        report['within_absolute_deadline']=report['within_probe_deadline']
        if not report['within_probe_deadline']:report['status']='TRANSFER_FAILED'
        report['science_complete']=report['status']=='TRANSFER_COMPLETE'
        report['operational_success']=operational_success(report,child)
        atomic_json(root/'terminal-receipt.json',report,exclusive=True)
    return report


run_owned_probe = run_owned_transfer  # Explicit compatibility alias; new protocol/namespace remain bound.

"""Owned whole-process probe; no public data admission, scoring or publication."""
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
from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard,verify_closed_proof

ROOT=Path(__file__).resolve().parents[2]
MAX_FILE_BYTES=16*1024**2
MAX_DIAGNOSTIC_BYTES=64*1024**2
LARGE_DIAGNOSTICS={'full-diagnostics.json','experiment/full-report.json','training-receipts-at-exit.json'}
MAX_TOTAL_BYTES=256*1024**2

def source_identity():
    return {p.relative_to(ROOT).as_posix():file_sha(p) for p in sorted(ROOT.rglob('*'))
            if p.is_file() and p.suffix in ('.py','.json','.jinja') and '__pycache__' not in p.parts}

def source_check(expected):
    require(source_identity()==expected,'probe source closure changed')

def project(report):
    branches={}
    for name,b in report.get('branches',{}).items():
        branches[name]={k:b[k] for k in ('status','objective','best_update','optimizer_updates','completion_tokens','checkpoint_summaries','selected_replay_exact','physical_usage','elapsed_seconds')}
    result={k:report[k] for k in ('format','status','protocol_sha256','baseline','denominators','physical_usage','final_clean_reset_exact','public_solving_admitted','public_score','confirmation_evaluated','ttt_executed','science_profile','decoder_mode','decoder_policy_sha256','profile_sha256','science_complete','operational_success','selected_case_ids','omitted_case_ids','strict_numerical_allclose','bounded_empirical_cache_fidelity','cache_fidelity_scope') if k in report}
    result['branches']=branches;result['diagnostics_projection']=True
    require(len(canonical(result))<=128*1024,'bounded summary projection exceeded')
    return result

def _output_inventory(root):
    files={};size=0
    for p in sorted(Path(root).rglob('*')):
        require(not p.is_symlink(),'output symlink forbidden')
        mode=p.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode),'nonregular output entry denied')
        if stat.S_ISDIR(mode):continue
        n=p.relative_to(root).as_posix()
        if n in ('evidence.zip','archive-manifest.json'):continue
        s=p.stat().st_size;require(s<=(MAX_DIAGNOSTIC_BYTES if n in LARGE_DIAGNOSTICS else MAX_FILE_BYTES),'output member byte ceiling exceeded')
        size+=s;require(size<=MAX_TOTAL_BYTES and len(files)<12000,'output archive bound exceeded')
        files[n]={'bytes':s,'sha256':file_sha(p)}
    return files

def archive_closed(root,proof):
    verify_closed_proof(proof)
    require(proof.get('closed') is True,'only stopped owner evidence may be archived')
    root=Path(root);files=_output_inventory(root)
    manifest={'format':'irisx/qwen14b-probe-archive-v1','files':files,'owned_process_closed':True,'public_score':None}
    require(sum(e['bytes'] for e in files.values())+len(canonical(manifest))<=MAX_TOTAL_BYTES and len(files)+1<=12000,'archive manifest-inclusive bound exceeded')
    atomic_json(root/'archive-manifest.json',manifest,exclusive=True)
    with zipfile.ZipFile(root/'evidence.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for n,item in files.items():
            p=root/n;require(file_sha(p)==item['sha256'],'output bytes changed after closure');z.write(p,n)
        z.write(root/'archive-manifest.json','archive-manifest.json')
    return {'path':str(root/'evidence.zip'),'sha256':file_sha(root/'evidence.zip'),'files':len(files)+1,
            'bytes':(root/'evidence.zip').stat().st_size}

def run_owned_probe(config,output,*,python_command=None):
    """Callable after independently source-bound offline interpreter preparation.

    python_command is the exact verified production offline-run.py command, or
    the explicitly tiny CPU test interpreter. The child rechecks actual runtime.
    No install/download/network/weight-copy action is performed by this function.
    """
    config=validate_config(config);root=Path(output).absolute()
    require(not any(p.is_symlink() for p in (root,*root.parents)),'regular output root required')
    require(not root.exists() and not root.is_relative_to(ROOT) and not ROOT.is_relative_to(root),'fresh nonoverlapping output root required')
    for key in ('tokenizer_path','development_panel_path','training_root'):
        if config.get(key):
            p=Path(config[key]).absolute();require(not root.is_relative_to(p) and not p.is_relative_to(root),'input/output overlap')
    root.mkdir(parents=True);began=time.monotonic();now=time.time()
    require(config['started_epoch']<=now+2,'future pre-dispatch epoch forbidden')
    duration=config.get('maximum_seconds',PROTOCOL['maximum_probe_seconds'])
    hard=began+max(0,min(duration,config['started_epoch']+duration-now,config['started_epoch']+PROTOCOL['maximum_session_seconds']-now))
    work_reserve=60 if config.get('tiny_cpu') else 600
    stop_reserve=30 if config.get('tiny_cpu') else 540
    require(hard-began>work_reserve+10,'probe time exhausted before launch')
    command=list(python_command or [sys.executable,'-I','-B'])
    require(command and all(type(x) is str and x for x in command),'verified interpreter command required')
    if not config.get('tiny_cpu'):
        require(len(command)==5 and command[1:4]==['-I','-B','-S'] and Path(command[4]).name=='offline-run.py',
                'production requires unchanged verified offline installer launcher')
    request={'format':'irisx/qwen14b-learning-probe-request-v1','config':config,'output_root':str(root),
             'work_deadline':hard-work_reserve,'hard_deadline':hard,'source_identity':source_identity()}
    atomic_json(root/'request.json',request,exclusive=True)
    guard=None;proof=None;error=None;forced=False
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
                    if state.get('status')=='active' and time.monotonic()>state['deadline_monotonic']:
                        raise TimeoutError('owned stage deadline: '+state.get('stage','unknown'))
                call=root/'active-call.json'
                if call.is_file():
                    require(call.stat().st_size<=65536 and not call.is_symlink(),'bounded active call required')
                    state=json.loads(call.read_bytes())
                    if state.get('status')=='active' and time.monotonic()>state['deadline_monotonic']:
                        raise TimeoutError('owned native call deadline')
                time.sleep(.2)
    except BaseException as exc:error=type(exc).__name__+': '+str(exc)[:512]
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
    report={'format':'irisx/qwen14b-owned-learning-probe-v1',
        'status':child['status'] if clean and child and child.get('status') in ('PROBE_PILOT_COMPLETE','PROBE_DIAGNOSTICS_ONLY') and not error and not forced else 'PROBE_FAILED',
        'child':child,'error':error,'timed_out':forced,'owned_process_closed':bool(proof and proof.get('closed')),
        'closure_proof':proof,'elapsed_seconds':time.monotonic()-began,'maximum_seconds':duration,
        'predispatch_started_epoch':config['started_epoch'],'global_deadline_epoch':config['started_epoch']+PROTOCOL['maximum_session_seconds'],
        'source_identity_sha256':digest(request['source_identity']),'public_score':None,'public_solving_admitted':False,
        'fp8_executed':False,'four_l4_executed':False,
        'completed_epoch':time.time(),'within_probe_deadline':time.time()<=config['started_epoch']+duration,
        'effective_deadline_epoch':config['started_epoch']+duration,
        'within_absolute_deadline':time.time()<=config['started_epoch']+duration,
        'work_reserve_seconds':work_reserve,'owner_stop_reserve_seconds':stop_reserve}
    report['science_complete']=report['status']=='PROBE_PILOT_COMPLETE'
    report['operational_success']=report['science_complete']
    atomic_json(root/'summary.json',report,exclusive=True)
    if proof and proof.get('closed'):
        try:report['archive']=archive_closed(root,proof)
        except BaseException as exc:
            report['archive_error']=type(exc).__name__+': '+str(exc)[:512];report['status']='PROBE_FAILED'
        report['completed_epoch']=time.time()
        report['within_probe_deadline']=report['completed_epoch']<=config['started_epoch']+duration
        report['within_absolute_deadline']=report['within_probe_deadline']
        if not report['within_probe_deadline']:report['status']='PROBE_FAILED'
        report['science_complete']=report['status']=='PROBE_PILOT_COMPLETE'
        report['operational_success']=report['science_complete']
        atomic_json(root/'terminal-receipt.json',report,exclusive=True)
    return report

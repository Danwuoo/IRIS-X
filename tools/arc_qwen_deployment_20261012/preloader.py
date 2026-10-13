"""Default-inert, stdlib-only deadline supervisor for the whole reviewed notebook.

The notebook coordinator never loads model weights. One owned child performs
source admission, offline installation and the complete session. Immutable
process-guard source is reused, including pidfd/subreaper/parent-death handling.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

MAX_SESSION_SECONDS = 43200
CLEANUP_RESERVE_SECONDS = 30


def _need(value, message):
    if not value: raise ValueError(message)


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)+'\n').encode()


def _hash(raw): return hashlib.sha256(raw).hexdigest()


def _path(value):
    _need(type(value) is str and value and len(value)<=4096 and not any(ord(c)<32 for c in value), 'invalid path')
    _need('\\' not in value and ':' not in value and '..' not in value.split('/'), 'ambiguous path')
    return Path(os.path.abspath(value))


def _overlap(a,b): return a==b or a in b.parents or b in a.parents


def _links(path):
    _need(not any(p.is_symlink() for p in (path,*path.parents)), 'symlink path')


def _fresh_write(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def _load_guard(path,expected_sha):
    _need(_hash(path.read_bytes())==expected_sha,'guard bytes changed')
    spec=importlib.util.spec_from_file_location('_irisx_owned_notebook_guard',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def _run_owned(argv, *, guard_module, launcher_root, output_root, started_epoch,
               hard_deadline_epoch, cleanup_reserve=CLEANUP_RESERVE_SECONDS, poll_seconds=0.2):
    """Only called with the fixed reviewed bootstrap, or explicit CPU tests."""
    remaining=hard_deadline_epoch-time.time()
    _need(remaining>cleanup_reserve, 'deadline reserve already reached before child launch')
    hard_mono=time.monotonic()+remaining
    work_mono=hard_mono-cleanup_reserve
    forced=False;reason=None;next_progress=0.0
    with (launcher_root/'stdout.txt').open('xb') as out,(launcher_root/'stderr.txt').open('xb') as err:
        guard=guard_module.OwnedProcessGuard.spawn(argv,evidence_dir=launcher_root/'owned-tree',
            stdout=out,stderr=err,cwd=str(Path.cwd()),close_fds=True,start_new_session=True,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
        try:
            while guard.poll() is None:
                _need((launcher_root/'stdout.txt').stat().st_size+(launcher_root/'stderr.txt').stat().st_size<=4*1024**2,'bounded launcher logs exceeded')
                if time.monotonic()>=work_mono or time.time()>=hard_deadline_epoch-cleanup_reserve:
                    forced=True;reason='absolute-session-deadline';guard.stop(timeout=min(10.0,max(0.1,hard_mono-time.monotonic())));break
                if time.monotonic()>=next_progress:
                    # Operational labels only. Never open scorer metrics or task answers.
                    marker=output_root/'active-stage.json';stage='source-admission-or-bootstrap'
                    if marker.is_file() and not marker.is_symlink() and marker.stat().st_size<=65536:
                        state=json.loads(marker.read_bytes());stage=str(state.get('stage','unknown'))[:80]
                    print(json.dumps({'event':'LEARNING_PROGRESS','stage':stage,
                        'elapsed_seconds':round(max(0,time.time()-started_epoch),1),
                        'remaining_seconds':round(max(0,min(hard_mono-time.monotonic(),hard_deadline_epoch-time.time())),1)}),flush=True)
                    next_progress=time.monotonic()+30
                time.sleep(poll_seconds)
        except BaseException:
            forced=True;reason='coordinator-error';guard.stop(timeout=10);raise
        finally:
            proof=guard.closed_proof()
            if not proof.get('closed') or proof.get('remaining'):
                forced=True;reason=reason or 'unclosed-owned-tree';proof=guard.stop(timeout=10)
            completed_epoch=time.time()
            receipt={'format':'irisx/learning-notebook-closure-v1','started_epoch':started_epoch,
                'hard_deadline_epoch':hard_deadline_epoch,'global_deadline_epoch':started_epoch+MAX_SESSION_SECONDS,'completed_epoch':completed_epoch,
                'within_absolute_deadline':completed_epoch<=hard_deadline_epoch and time.monotonic()<=hard_mono,
                'forced':forced,'reason':reason,'process_tree_proof':proof,
                'scope':'owned notebook child execution; no VM/billing/queue SLA claim'}
            _fresh_write(launcher_root/'launcher-closure.json',_canonical(receipt))
    guard_module.verify_closed_proof(proof)
    if forced or not receipt['within_absolute_deadline'] or proof['returncode']!=0 or proof['worker_returncode']!=0 or proof['forced']:
        raise RuntimeError('owned notebook execution stopped or failed; inspect launcher closure/stdout/stderr')
    return receipt


PROBE_SECONDS = 21600
PROFILE = 'QWEN14B_CACHED_PILOT6H'
OUTER_RESERVE_SECONDS = 360


def launch_reviewed_qwen_notebook(*, pins, config, loader_source, guard_source,
                                  expected_loader_sha256, expected_guard_sha256):
    """No source, task, model or installer input is opened before supervision."""
    required={'manual_start','enable_model','profile','session_seconds','probe_seconds',
              'predispatch_epoch','output_root','source_parent','input_root','code_root','data_root','training_root'}
    _need(type(config) is dict and set(config)==required,'exact Qwen launcher config required')
    _need(type(config['manual_start']) is bool and type(config['enable_model']) is bool,'exact switches required')
    if not config['manual_start']:return {'status':'DISABLED','gpu_executed':False,'public_score':None}
    _need(config['enable_model'] is True and config['profile']==PROFILE,'explicit Qwen model probe required')
    _need(type(config['session_seconds']) is int and config['session_seconds']==MAX_SESSION_SECONDS,'frozen global session cap')
    _need(type(config['probe_seconds']) is int and config['probe_seconds']==PROBE_SECONDS,'frozen probe cap')
    epoch=config['predispatch_epoch']
    _need(type(epoch) in (int,float) and math.isfinite(epoch) and 0<=epoch<=time.time()+2,'fresh finite predispatch epoch required')
    hard_epoch=min(epoch+MAX_SESSION_SECONDS,epoch+PROBE_SECONDS)
    _need(hard_epoch-time.time()>OUTER_RESERVE_SECONDS,'submission clock expired; no new session')
    _need(_hash(loader_source.encode())==expected_loader_sha256 and _hash(guard_source.encode())==expected_guard_sha256,'embedded executable source differs')
    inputs=[_path(config['input_root'])]+[_path(config[k]) for k in ('code_root','data_root','training_root') if config[k] is not None]
    output=_path(config['output_root']); source=_path(config['source_parent'])
    launcher=output.parent/(output.name+'-launcher');environment=output.parent/(output.name+'-environment')
    writes=[output,source,launcher,environment]
    for i,a in enumerate(writes):
        for b in inputs+writes[i+1:]:_need(not _overlap(a,b),'write root overlaps immutable input or another output')
    for p in writes:_links(p);_need(not p.exists(),'fresh launcher/source/output/environment identity required')
    launcher.mkdir(parents=True,mode=0o700,exist_ok=False)
    guard_path=launcher/'owned_process_guard.py';_fresh_write(guard_path,guard_source.encode())
    driver=loader_source+'''\n\nif __name__ == '__main__':
    import hashlib,json,sys
    from pathlib import Path
    request_path,request_sha=sys.argv[1:]
    raw=Path(request_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=request_sha:raise ValueError('launcher request changed')
    request=json.loads(raw); c=request['config']
    ready=load_reviewed_qwen_source(pins=request['pins'],input_root=c['input_root'],
        code_root=c['code_root'],data_root=c['data_root'],training_root=c['training_root'],
        source_parent=c['source_parent'],output_root=c['output_root'],model_config={},resume=False)
    from tools.arc_qwen_deployment_20261012.bootstrap import bootstrap_probe
    result=bootstrap_probe(request,ready)
    print(json.dumps({'status':result['status'],'public_score':None}),flush=True)
    raise SystemExit(0 if result['status'] in ('PROBE_PILOT_COMPLETE','PROBE_DIAGNOSTICS_ONLY') else 2)
'''
    driver_path=launcher/'bootstrap.py';_fresh_write(driver_path,driver.encode())
    request={'pins':pins,'config':config,'started_epoch':epoch,'hard_deadline_epoch':hard_epoch,
             'global_deadline_epoch':epoch+MAX_SESSION_SECONDS,'launcher_root':str(launcher),
             'environment_root':str(environment),'loader_sha256':expected_loader_sha256,
             'guard_sha256':expected_guard_sha256,'driver_sha256':_hash(driver.encode())}
    raw=_canonical(request);request_path=launcher/'request.json';_fresh_write(request_path,raw)
    module=_load_guard(guard_path,expected_guard_sha256)
    receipt=_run_owned([sys.executable,'-I','-B',str(driver_path),str(request_path),_hash(raw)],guard_module=module,
        launcher_root=launcher,output_root=output,started_epoch=epoch,hard_deadline_epoch=hard_epoch,
        cleanup_reserve=OUTER_RESERVE_SECONDS)
    result_path=launcher/'result.json';_need(result_path.is_file() and not result_path.is_symlink() and result_path.stat().st_size<=1024*1024,'bounded child result required')
    result=json.loads(result_path.read_bytes())
    return {**result,'notebook_owner_closure':{'path':str(launcher/'launcher-closure.json'),'sha256':_hash(_canonical(receipt))}}

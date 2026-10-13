"""Owned, zero-model acceptance of an exact downloaded code Dataset mount.

Non-code mounts are explicitly synthetic manifest-only fixtures. This does not
attest downloaded training data, evaluator content, model weights or GPU fit.
"""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def need(value,message):
    if not value:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def regular(path):
    path=Path(path);need(not any(p.is_symlink() for p in (path,*path.parents)),'symlink forbidden')
    need(path.is_file() and path.stat().st_size<=16*1024**2,'bounded regular input required')
    return path.read_bytes()


def write(path,value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return raw


WORKER = r'''import builtins,hashlib,json,sys
from pathlib import Path
request_path,expected=sys.argv[1:]
raw=Path(request_path).read_bytes()
if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('request changed')
r=json.loads(raw)
if hashlib.sha256(r['loader_source'].encode()).hexdigest()!=r['loader_sha256']:raise ValueError('loader changed')
original=builtins.__import__
def guarded(name,*a,**k):
    if name.split('.')[0] in ('torch','transformers','peft','kaggle','requests','httpx'):raise AssertionError('model/network import denied')
    return original(name,*a,**k)
builtins.__import__=guarded
scope={}
exec(compile(r['loader_source'],'<exact-embedded-loader>','exec'),scope)
ready=scope['load_reviewed_qwen_source'](pins=r['pins'],input_root=r['input_root'],code_root=r['code_root'],
    data_root=r['data_root'],training_root=r['training_root'],source_parent=r['source_parent'],
    output_root=r['output_root'],model_config={},resume=False)
result={'status':'PASS','model_calls':0,'source_transport_mode':ready['source_transport_mode'],
        'source_archive_bytes_verified':ready['source_archive_bytes_verified'],'entry_provenance':ready['entry_provenance'],
        'synthetic_non_code_metadata_only':True}
with Path(r['result_path']).open('xb') as f:f.write((json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode())
'''


def accept(candidate,code_root,code_receipt,output):
    candidate=Path(candidate).absolute();code_root=Path(code_root).absolute();output=Path(output).absolute()
    need(not output.exists() and not any(p.is_symlink() for p in (output,*output.parents)),'fresh output required')
    for p in (candidate,code_root):
        need(output!=p and output not in p.parents and p not in output.parents,'output/input overlap')
    manifest_raw=regular(candidate/'publication-manifest.json');manifest=json.loads(manifest_raw)
    need(manifest['datasets'][0]['id']==12504696 and manifest['datasets'][0]['expected_version']==11,'exact code11 required')
    need(manifest['source_review_only'] is False,'reviewed source required for publication mount acceptance')
    code_receipt_raw=regular(code_receipt)
    notebook_row=next(n for n in manifest['notebooks'] if n['role']=='inactive')
    notebook_raw=regular(candidate/notebook_row['path']);need(sha(notebook_raw)==notebook_row['sha256'],'notebook changed')
    notebook=json.loads(notebook_raw);scope={}
    for cell in notebook['cells'][1:3]:exec(compile(''.join(cell['source']),'<reviewed-inactive-notebook>','exec'),scope)
    pins=copy.deepcopy(scope['PINS']);need(pins['code']['reference'].endswith('/11'),'notebook code11 required')
    loader=scope['LOADER_SOURCE'];need(sha(loader.encode())==scope['EXPECTED_LOADER_SHA256'],'exact loader hash required')
    guard_row=manifest['terminal_contract']['outer_executable_files']['owned_process_guard.py']
    guard_raw=regular(candidate/guard_row['path']);need(sha(guard_raw)==guard_row['sha256'],'guard changed')
    output.mkdir(parents=True)
    fixtures=output/'metadata-only-fixtures';fixtures.mkdir()
    data=fixtures/'data';data.mkdir();training=fixtures/'training';training.mkdir()
    roles={'solver':'1'*64,'evaluator':'2'*64}
    raw=write(data/'public-data-material.json',{'format':'irisx/public120-data-material-v1','reference':pins['data']['reference'],'role_manifests':roles})
    pins['data'].update(manifest_sha256=sha(raw),role_manifests=roles)
    raw=write(training/'manifest.json',{'format':'irisx/learning-training-material-v1','reference':pins['training']['reference'],'tasks':1000,'public_evaluation_files':0,'files':{}})
    pins['training']['manifest_sha256']=sha(raw)
    worker=output/'loader-worker.py';worker.write_text(WORKER)
    request={'pins':pins,'loader_source':loader,'loader_sha256':sha(loader.encode()),'code_root':str(code_root),
             'input_root':str(fixtures),'data_root':str(data),'training_root':str(training),
             'source_parent':str(output/'source'),'output_root':str(output/'unused-model-output'),
             'result_path':str(output/'worker-result.json')}
    request_path=output/'request.json';request_raw=write(request_path,request)
    guard_path=output/'owned_process_guard.py';guard_path.write_bytes(guard_raw)
    spec=importlib.util.spec_from_file_location('_downloaded_code_mount_guard',guard_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    guard=None;proof=None;error=None;deadline=time.monotonic()+120
    try:
        with (output/'stdout.txt').open('xb') as out,(output/'stderr.txt').open('xb') as err:
            guard=module.OwnedProcessGuard.spawn([sys.executable,'-I','-B',str(worker),str(request_path),sha(request_raw)],
                evidence_dir=output/'owned-tree',cwd=str(output),stdout=out,stderr=err,close_fds=True,start_new_session=True,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','CUDA_VISIBLE_DEVICES':'','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
            while guard.poll() is None:
                need(time.monotonic()<deadline,'mount acceptance deadline')
                need((output/'stdout.txt').stat().st_size+(output/'stderr.txt').stat().st_size<=1024**2,'bounded logs')
                time.sleep(.05)
    except BaseException as exc:error=type(exc).__name__+': '+str(exc)[:500]
    finally:
        if guard is not None:
            try:
                try:proof=guard.closed_proof()
                except BaseException:proof=None
                if not proof or not proof.get('closed'):proof=guard.stop(timeout=10)
                module.verify_closed_proof(proof)
            except BaseException as exc:error='closure: '+type(exc).__name__+': '+str(exc)[:500]
    worker_result=None
    try:
        worker_result=json.loads(regular(output/'worker-result.json'))
    except BaseException as exc:error=error or ('worker result: '+type(exc).__name__+': '+str(exc)[:500])
    success=bool(not error and proof and proof.get('closed') and not proof.get('forced') and proof.get('returncode')==0 and proof.get('worker_returncode')==0 and worker_result and worker_result.get('status')=='PASS')
    receipt={'format':'irisx/transfer-downloaded-code-mount-acceptance-v1','status':'PASS' if success else 'FAIL',
             'publication_manifest_sha256':sha(manifest_raw),'code_dataset_version':11,'code_receipt_sha256':sha(code_receipt_raw),
             'model_calls':0,'owned_tree_closed':bool(proof and proof.get('closed')),'process_tree_proof':proof,
             'worker_source_sha256':sha(WORKER.encode()),'guard_source_sha256':sha(guard_raw),'loader_sha256':sha(loader.encode()),
             'code_root':str(code_root),'worker_result':worker_result,'error':error,
             'scope':'Only actual downloaded code mount and exact embedded loader. Data/training role metadata are synthetic; no tasks, evaluator answers, model or provider API.'}
    write(output/'receipt.json',receipt)
    need(success,'downloaded code mount acceptance failed; inspect receipt')
    return {'path':str(output/'receipt.json'),'sha256':sha(regular(output/'receipt.json')),'status':'PASS'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','code_root','code_receipt','output'):parser.add_argument(n,type=Path)
    args=parser.parse_args();print(json.dumps(accept(**vars(args)),indent=2))

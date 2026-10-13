"""Execute the emitted active notebook's exact config construction without a model.

Only clock, runtime approval (for previews), filesystem routing and owner runner
are fixture substitutes. The final run cell and preloader config schema execute
unchanged. The emitted request retains the exact production config values.
"""
from __future__ import annotations
import argparse
import builtins
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch


def sha(raw):return hashlib.sha256(raw).hexdigest()


def exercise(candidate,output):
    candidate=Path(candidate).absolute();output=Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output,*output.parents)):
        raise ValueError('fresh unlinked config-fixture output required')
    raw=(candidate/'iris-x-qwen14b-transfer-active-template.ipynb').read_bytes()
    notebook=json.loads(raw);scope={};output.mkdir(parents=True)
    original_import=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name.split('.')[0] in ('torch','transformers','peft','kaggle','requests','httpx'):
            raise AssertionError('model/network import denied')
        return original_import(name,*args,**kwargs)
    with patch('builtins.__import__',side_effect=guarded):
        for cell in notebook['cells'][1:3]:
            exec(compile(''.join(cell['source']),'<exact-emitted-notebook>','exec'),scope)
        original_reviewed=scope['PINS']['release']['runtime_reviewed']
        scope['PINS']=copy.deepcopy(scope['PINS'])
        scope['PINS']['release']['runtime_reviewed']=True
        epoch=2000000000
        scope['PREDISPATCH_EPOCH']=epoch
        original_path=scope['_path']
        def route(value):
            path=original_path(value)
            return output/'filesystem'/path.relative_to('/')
        def no_model_owner(*args,**kwargs):
            (kwargs['launcher_root']/'result.json').write_text(json.dumps({'status':'SYNTHETIC_CONFIG_ONLY'}))
            return {'synthetic_fixture_only':True,'no_owner_spawned':True,'model_calls':0}
        with patch.dict(scope,{'_path':route,'_load_guard':lambda *args:None,'_run_owned':no_model_owner}),patch.object(scope['time'],'time',return_value=epoch):
            # This is the unchanged final cell, including its full real config.
            exec(compile(''.join(notebook['cells'][3]['source']),'<exact-emitted-run-cell>','exec'),scope)
    request_path=output/'filesystem'/Path(scope['OUTPUT_ROOT']).relative_to('/').parent/(Path(scope['OUTPUT_ROOT']).name+'-launcher')/'request.json'
    request=json.loads(request_path.read_bytes())
    required={'manual_start','enable_model','profile','session_seconds','probe_seconds','predispatch_epoch',
              'execution_cutoff_seconds','outer_cutoff_seconds','provider_runtime_seconds','output_root','source_parent','input_root','code_root','data_root','training_root'}
    if set(request['config'])!=required:raise ValueError('emitted config schema differs')
    for k,v in request['config'].items():
        if v!=scope[k.upper()]:raise ValueError('config does not equal emitted notebook constant: '+k)
    for k,seconds in (('execution_deadline_epoch',42000),('hard_deadline_epoch',42180),('provider_deadline_epoch',42300),('global_deadline_epoch',43200)):
        if request[k]!=epoch+seconds:raise ValueError('emitted same-origin clock differs')
    receipt={'format':'irisx/exact-emitted-notebook-config-fixture-v1','status':'PASS','synthetic_fixture_only':True,
             'notebook_sha256':sha(raw),'publication_manifest_sha256':sha((candidate/'publication-manifest.json').read_bytes()),
             'runtime_review_was_originally_true':original_reviewed,'exact_run_cell_executed':True,
             'exact_preloader_config_schema_executed':True,'request_config':request['config'],
             'request':{'path':request_path.relative_to(output).as_posix(),'bytes':request_path.stat().st_size,'sha256':sha(request_path.read_bytes())},
             'fixture_substitutions':['finite epoch','preview runtime_reviewed flag when necessary','local filesystem route','no-model owner stub'],
             'no_real_owner_spawned':True,'model_calls':0,'provider_calls':0}
    (output/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();print(json.dumps(exercise(a.candidate,a.output),indent=2))

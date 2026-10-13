"""Exact final source owned-process tiny integration; no real ARC/public data."""
import json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'final-source-freeze-002';sys.path[:0]=[str(source),str(source/'src')]
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
from tools.arc_qwen_transfer_20261012.runner import run_owned_transfer
name=sys.argv[1];assert name in ('main','before-load')
config={'enabled':True,'tiny_cpu':True,'test_fixture_dataset':True,
 'tokenizer_path':str(source/'materials/qwen14b/hf-overlay'),'tiny_hidden_size':8,
 'started_epoch':time.time(),'maximum_seconds':1800,'test_checkpoint_updates':[1,2],
 'test_generation_cap':4,'test_skip_ttt':True,'test_calibration_lengths':[128,512]}
if name=='before-load':config['test_failure']='before_load'
out=ROOT/'evidence'/('owned-final-fixture-'+name)
print(json.dumps({'output':str(out),'source':str(source),'explicit_tiny_fixture':True}),flush=True)
result=run_owned_transfer(config,out)
print(json.dumps(result,indent=2),flush=True)
assert result['status']==('TRANSFER_COMPLETE' if name=='main' else 'TRANSFER_FAILED'),result
assert result.get('archive') and (out/'evidence.zip').is_file(),result
if name=='main':assert result['operational_success'],result

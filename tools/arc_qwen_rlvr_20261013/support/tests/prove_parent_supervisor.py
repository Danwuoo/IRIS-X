"""Actual CPU subprocess wrapper proof; no model, provider or benchmark work."""
from pathlib import Path
import json,os,sys,tempfile,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deployment'))
from launch_notebook import load_file,run_bounded
GUARD=ROOT.parent/'portfolio63-rl-batched-20261012/baseline/tools/arc_learning_agent_20261011/process_guard.py'
guard=load_file('proof_owned_process_guard',GUARD)
with tempfile.TemporaryDirectory(prefix='rlvr-parent-proof-') as tmp:
    root=Path(tmp);results={}
    for name,code in [('success','print("bounded CPU child")'),('nonzero','raise SystemExit(7)'),('log_cap','import os\nfor i in range(256): os.write(1,b"x"*65536)')]:
        try:
            receipt=run_bounded([sys.executable,'-I','-B','-c',code],guard_module=guard,directory=root/name,
                deadline_epoch=time.time()+25,env={'PATH':os.defpath,'LANG':'C.UTF-8'},scope='synthetic-CPU-wrapper-'+name)
            ok=name=='success'
        except RuntimeError:
            receipt=json.loads((root/name/'closure.json').read_text());ok=name!='success'
        if not ok or not receipt['proof']['closed'] or receipt['proof']['remaining'] or receipt['log_bytes']>8*1024**2:raise AssertionError(name)
        if name=='log_cap' and receipt['reason']!='bounded-launcher-log-cap':raise AssertionError('cap not enforced')
        results[name]={'closed':True,'forced':receipt['forced'],'reason':receipt['reason'],'log_bytes':receipt['log_bytes']}
    print(json.dumps({'format':'rlvr-parent-supervisor-no-model-proof-v1','status':'PASS','fixture':True,'cases':results,
        'model_loaded':False,'provider_calls':0,'source_scope':'actual bounded parent wrapper and unchanged source-owned process guard'},sort_keys=True))

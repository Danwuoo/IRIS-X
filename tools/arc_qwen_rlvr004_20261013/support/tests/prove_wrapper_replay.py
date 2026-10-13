"""Retained real CPU wrapper raw proofs. Explicit synthetic argv, no model/provider."""
from pathlib import Path
import importlib.util,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deployment'))
from launch_notebook import load_file,run_bounded
v=load_file('independent_wrapper_replay',ROOT/'assembly/verify_parent_wrappers.py')
guard_path=ROOT.parent/'portfolio63-rl-batched-20261012/baseline/tools/arc_learning_agent_20261011/process_guard.py'
guard=load_file('fixture_source_guard',guard_path)
root=Path(sys.argv[1]).absolute();root.mkdir(exist_ok=False)
epoch=int(time.time());fixtures={}
for name,returncode in [('success',0),('nonzero',7)]:
    case=root/name;case.mkdir()
    child_argv=[sys.executable,'-I','-B','-c','import time;time.sleep(.15);raise SystemExit('+str(returncode)+')']
    nested="""from pathlib import Path
import json,sys,types
path=Path(%r);m=types.ModuleType('fixture_launch');m.__file__=str(path);sys.modules[m.__name__]=m
exec(compile(path.read_bytes(),str(path),'exec'),vars(m))
g=m.load_file('nested_guard',%r)
try:m.run_bounded(%r,guard_module=g,directory=%r,deadline_epoch=%r,env=%r,scope='synthetic-installed-parent')
except RuntimeError:raise SystemExit(1)
"""%(str(ROOT/'deployment/launch_notebook.py'),str(guard_path),child_argv,str(case/'installed-parent'),epoch+42180,{'PATH':os.defpath,'LANG':'C.UTF-8'})
    argv=[sys.executable,'-I','-B','-c',nested]
    try:run_bounded(argv,guard_module=guard,directory=case/'preparation',deadline_epoch=epoch+42180,env={'PATH':os.defpath,'LANG':'C.UTF-8'},scope='synthetic-preparation')
    except RuntimeError:
        if name=='success':raise
    a=v.verify_stage(case/'preparation',expected_argv=argv,epoch=epoch,scope='synthetic-preparation')
    b=v.verify_stage(case/'installed-parent',expected_argv=child_argv,epoch=epoch,scope='synthetic-installed-parent')
    if not a['closure_valid'] or not b['closure_valid'] or v.identity(b['coordinator_identity'])!=v.identity(a['worker_identity']) or not v.identities(b['owned_identities'])<=v.identities(a['owned_identities']):raise AssertionError('actual nested lineage')
    if b['operational']!=(name=='success'):raise AssertionError('separate operational axis')
    fixtures[name]={'epoch':epoch,'preparation_argv':argv,'installed_parent_argv':child_argv,'preparation':a,'installed_parent':b}
receipt={'format':'rlvr-actual-parent-wrapper-replay-fixture-v1','fixture':True,'synthetic_argv':True,'production_admitted':False,'provider_calls':0,'model_loaded':False,'helper_sha256':v.sha((ROOT/'assembly/verify_parent_wrappers.py').read_bytes()),'cases':fixtures}
(root/'FIXTURE.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
print(json.dumps({'status':'PASS','fixture':True,'actual_nested_processes':True,'source_helper_sha256':receipt['helper_sha256'],'path':str(root)}))

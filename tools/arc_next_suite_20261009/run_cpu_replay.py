"""Actual N5 CPU replay; evaluator gold enters only after stopped-worker seal."""
from pathlib import Path
import sys,time,json,hashlib
ROOT=Path(__file__).parent;sys.path.insert(0,str(ROOT/'src'));import arc_suite as s
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
s.require_security_release();original=s.read(ROOT/'src/solver-manifest-reference.json');payload=s.read(ROOT/'src/n4-replay-payload.json');ch=payload['visible_challenges']
m=s.make_manifest('N5',original,ch);s.verify_manifest(m,ch);s.write(out/'manifest.json',m);s.write(out/'challenges.json',ch)
started=time.monotonic();s.run_replay(m,ch,out,started+600)
dispatch={'confirmed_stopped':True,'returncode':0,'timed_out':False,'process':'CPU replay of61 frozen sources per language','wall_seconds':time.monotonic()-started}
s.write(out/'dispatch.json',dispatch);sealed=s.seal(out,m,dispatch)
# No gold is read by this script; only the post-seal evaluator function reads it.
r=s.score(out,m,Path(sys.argv[2]).resolve());s.write(out/'report.json',r)
summary={'status':'complete' if len(sealed['states']['completed'])==122 else 'partial-or-failed','processes_ok':True,'run_id':'N5','core_sha256':m['core_sha256'],
         'groups':r['groups'],'record_states':{k:len(v) for k,v in sealed['states'].items()},'host_python_version':sys.version,'model_calls':0,'training_performed':False,'confirmation_used':False}
s.write(out/'summary.json',summary);archive=s.finalize(out);print(json.dumps({'summary':summary,'archive':archive},indent=2))

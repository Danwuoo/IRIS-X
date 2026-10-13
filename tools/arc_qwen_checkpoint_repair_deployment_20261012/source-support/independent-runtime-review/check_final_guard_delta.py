"""Exact negative-only source bridge and actual checkpoint inspection replay."""
from copy import deepcopy
import difflib,hashlib,json,shutil,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
OLD=ROOT/'final-source-freeze-001';NEW=ROOT/'final-source-freeze-002'
sys.path[:0]=[str(NEW),str(NEW/'src')]
from tools.arc_qwen_portfolio_20261012 import checkpoints as cp
path='tools/arc_qwen_portfolio_20261012/checkpoints.py'
old=(OLD/path).read_text();new=(NEW/path).read_text()
guard="""    require(schedule is not None or binding.get('model', {}).get('native_identity', {}).get('profile_id') !=
            'qwen3-14b-native-bf16-r8-c4096-transfer-v1',
            'stored TransferTrainer identity requires an explicit checkpoint schedule')
"""
if new.replace(guard,'',1)!=old or new.count(guard)!=1:raise RuntimeError('delta exceeds exact negative-only guard')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=lambda root:{p.relative_to(root).as_posix():h(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
a,b=files(OLD),files(NEW)
if [k for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)]!=[path]:raise RuntimeError('unexpected other source changes')
observations=[]
for update in (0,64,256):
    p=HERE/'native-replay/checkpoints/global_grid'/('update-%08d'%update)
    inspected=cp.inspect_checkpoint(p,expected_manifest_sha256=h(p/'manifest.json'))
    if inspected['update']!=update:raise RuntimeError('valid production label failed final inspector')
    observations.append({'update':update,'path':str(p),'manifest_sha256':h(p/'manifest.json'),'final_inspector_accepted':True})
p=HERE/'native-replay/checkpoints/global_grid/update-00000000'
root=Path(tempfile.mkdtemp(prefix='final-inspector-omission-',dir=HERE));shutil.copytree(p,root/'checkpoint');target=root/'checkpoint'
v=json.loads((target/'manifest.json').read_text());v['binding'].pop('checkpoint_schedule');v['binding_sha256']=cp.digest(v['binding']);(target/'manifest.json').write_text(json.dumps(v))
try:cp.inspect_checkpoint(target)
except ValueError as exc:error=str(exc)
else:raise RuntimeError('final inspector still accepts omitted transfer schedule')
receipt={'format':'irisx/independent-negative-only-checkpoint-guard-bridge-v1','status':'passed','source001_native_evidence_preserved':True,
 'old_source_identity_sha256':'949bc2535b19f6e7f0bc8794e80a3ffdc3f1306cadad7f00dc0023252f71738f',
 'final_source_identity_sha256':'d485de95b68e0147e0d122143d25e983b7c60800259fdf8e44315b4537818b86',
 'changed_file':path,'before_sha256':a[path],'after_sha256':b[path],
 'exact_diff':''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='source001/'+path,tofile='source002/'+path)),
 'valid_real_checkpoints':observations,'removed_schedule_rejected':error,
 'reasoning':'For every valid transfer artifact schedule is non-null, so the inserted require short-circuits true without changing execution. It adds only rejection for a schedule-less stored transfer profile. All other source bytes are identical.',
 'qualification':'Actual272-update neural evidence remains source001 evidence. Final source002 is separately exercised by native fixture0/1/2 plus task0/8/16 and metadata64/256 orchestration; this report does not relabel source001 checkpoints.'}
(HERE/'final-guard-delta-review.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

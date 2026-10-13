"""Actual isolated before/copy/after proof with local Git objects/index only.

Never opens or modifies the main checkout's .git, and never creates a commit,
sets a remote, fetches, pushes or connects to any provider. Historical base
requires exact independently retained baseline bytes, never hash placeholders.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys
BASE=Path(__file__).resolve().parents[2]
PRIOR=BASE/'portfolio63-checkpoint-repair-20261012/owner-handoff/complete-source-transfer003'

def need(ok,reason):
    if not ok:raise ValueError(reason)
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',choices=('prior-snapshot','owner-base'),required=True);p.add_argument('--historical-worker',type=Path);p.add_argument('--baseline-recovery-receipt',type=Path);a=p.parse_args()
    package=a.package.absolute();out=a.output.absolute();need(not out.exists(),'fresh isolated proof required');out.mkdir(parents=True)
    root=out/'checkout';root.mkdir();home=out/'empty-home';home.mkdir()
    full=json.loads((package/'FULL-FILE-MANIFEST.json').read_bytes());target={r['path']:r for r in full['files']};delta=json.loads((package/('CHANGED-VS-'+a.baseline.upper()+'.json')).read_bytes())
    before=dict(target)
    for row in delta['files']:
        if row['change']=='added':del before[row['path']]
        else:before[row['path']]=row['baseline']
    for name,row in before.items():
        source=PRIOR/'repository'/name;raw=source.read_bytes()
        if sha(raw)!=row['sha256']:
            need(a.baseline=='owner-base' and name=='tools/arc_learning_agent_20261011/worker.py' and a.historical_worker is not None,'genuine historical baseline member is unavailable: '+name)
            raw=a.historical_worker.read_bytes()
            need(a.baseline_recovery_receipt is not None,'explicit reconstructed-baseline provenance required')
            recovery=json.loads(a.baseline_recovery_receipt.read_bytes())
            need(recovery['reconstructed_sha256']==sha(raw) and recovery['reconstructed_git_blob_sha']==row['git_blob_sha'] and recovery['directly_retained_original'] is False,'hash-verified baseline reconstruction provenance')
        need(len(raw)==row['bytes'] and sha(raw)==row['sha256'],'actual baseline bytes differ')
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);dest.chmod(int(row['mode'][-3:],8))
    env={'PATH':os.defpath,'LANG':'C.UTF-8','HOME':str(home),'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','PYTHONDONTWRITEBYTECODE':'1'}
    logs=[]
    def run(argv):
        c=subprocess.run(argv,cwd=root,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        logs.append({'argv':argv,'returncode':c.returncode,'output':c.stdout});need(c.returncode==0,'isolated verification failed: '+c.stdout[:500]);return c.stdout.strip()
    run([sys.executable,'-B',str(package/'verify-owner-checkout.py'),'--repo',str(root),'--phase','before','--baseline',a.baseline])
    run(['git','init','-q',str(root)])
    pathspec=out/'before.pathspec';pathspec.write_text(''.join(':(literal)'+name+'\n' for name in before))
    run(['git','-c','core.autocrlf=false','add','-f','--pathspec-from-file='+str(pathspec)])
    before_tree=run(['git','write-tree']);need(before_tree==delta['comparison_tree'],'actual baseline Git tree differs')
    for row in delta['files']:
        raw=(package/'repository'/row['path']).read_bytes();need(sha(raw)==row['sha256'],'new exact source changed')
        dest=root/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);dest.chmod(int(row['mode'][-3:],8))
    run([sys.executable,'-B',str(package/'verify-owner-checkout.py'),'--repo',str(root),'--phase','after','--baseline',a.baseline])
    run(['git','-c','core.autocrlf=false','add','-f','--pathspec-from-file='+str(package/('CHANGED-VS-'+a.baseline.upper()+'.git-pathspec'))])
    after_tree=run(['git','write-tree']);need(after_tree==full['target_tree'],'actual final Git index tree differs')
    need(not run(['git','remote']),'isolated proof unexpectedly has a remote')
    result={'format':'irisx/rlvr-actual-owner-copy-proof-v1','status':'PASS','baseline':a.baseline,'actual_before_files':len(before),'actual_after_files':len(target),'before_tree':before_tree,'after_tree':after_tree,'actual_raw_bytes_and_modes_checked':True,'historical_worker_recovery':None if a.baseline_recovery_receipt is None else {'path':str(a.baseline_recovery_receipt),'sha256':sha(a.baseline_recovery_receipt.read_bytes()),'directly_retained_original':False,'two_hash_verified_reconstruction':True},'isolated_local_git_objects_and_index':True,'commits_created':0,'main_checkout_Git_writes':0,'remote_Git_or_provider_calls':0,'commands':logs}
    (out/'COPY-PROOF.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='commands'},sort_keys=True))
if __name__=='__main__':main()

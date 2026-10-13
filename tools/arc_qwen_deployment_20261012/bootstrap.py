"""Owned offline bootstrap. Does not import torch or load model weights."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROBE_SECONDS = 21600
SESSION_SECONDS = 43200
OUTER_RESERVE_SECONDS = 360
INSTALL_FREE_RESERVE = 4 * 1024**3
CONTRACT_RELATIVE = 'materials/qwen14b/material-contract.json'
CONTRACT_SHA256 = '8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0'


def require(value, message):
    if not value: raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def safe(path, directory=False):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path forbidden')
    require(path.is_dir() if directory else path.is_file(), 'required regular material missing')
    return path


def write(path, value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())


def remaining(request):
    left=request['hard_deadline_epoch']-time.time()-OUTER_RESERVE_SECONDS
    require(left>0, 'absolute probe deadline reserve reached')
    return left


def resolve_datasets(input_root):
    from tools.arc_consolidated_20261010.offline_bootstrap import PINS
    root=safe(input_root,directory=True); result={}
    for role in ('runtime','wheels','interpreter'):
        owner,slug,_=PINS[role]['reference'].split('/')
        present=[p for p in (root/slug,root/'datasets'/owner/slug) if p.is_dir()]
        require(len(present)==1,'exactly one pinned Dataset required: '+role)
        candidate=safe(present[0],directory=True)
        require(sha(safe(candidate/PINS[role]['manifest']))==PINS[role]['manifest_sha256'], 'Dataset manifest pin differs: '+role)
        result[role]=str(candidate)
    return result


def runtime_lock(roots):
    from tools.arc_consolidated_20261010.offline_bootstrap import PINS,SOURCE_LOCK_SHA256,_read_json
    root=Path(roots['runtime'])
    require(sha(safe(root/'bundle-manifest.json'))==PINS['runtime']['manifest_sha256'],'runtime manifest changed')
    # Metadata and exact source lock only. No public task/evaluator bytes opened.
    manifest=_read_json(root/'bundle-manifest.json')
    name='runtime/research/arc-next-line/model-source-lock.json'
    lock=safe(root/name)
    require(sha(lock)==SOURCE_LOCK_SHA256,'runtime source lock differs')
    require(manifest['files'][name]['sha256']==SOURCE_LOCK_SHA256,'runtime lock inventory differs')
    return lock


def prepare_environment(request, source_root, roots):
    from tools.arc_consolidated_20261010.offline_bootstrap import _helpers,PINS
    helpers=_helpers(); lock=runtime_lock(roots)
    work=Path(request['environment_root'])
    require(not work.exists(),'fresh isolated environment required')
    work.mkdir(parents=True)
    wheel=helpers['arc_next_offline_environment.py'].validate_wheelhouse(lock,roots['wheels'],check_runtime=False)
    remaining(request)
    # Reserve installation expansion, largest-wheel temporary extraction, and4GiB.
    require(shutil.disk_usage(work).free>=13583143106,'insufficient disk for offline install and4GiB reserve')
    interpreter=helpers['arc_next_offline_interpreter.py'].prepare_interpreter(
        roots['interpreter'],PINS['interpreter']['manifest_sha256'],work/'cpython312')
    install_request={'request':request,'roots':roots,'source_root':str(source_root)}
    path=work/'install-request.json';write(path,install_request)
    script=Path(__file__).absolute()
    with (work/'installation.log').open('xb') as log:
        completed=subprocess.run([interpreter['python_executable'],'-I','-B',str(script),'--install',str(path),sha(path)],
            stdout=log,stderr=log,timeout=remaining(request),check=False,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_DATASETS_OFFLINE':'1'})
    require(completed.returncode==0,'offline installation child failed; inspect installation.log')
    receipt=json.loads((work/'installation-receipt.json').read_bytes())
    require(receipt['installed_offline'] is True,'verified installer receipt required')
    return receipt


def install_child(path, expected):
    require(sha(safe(path))==expected,'installer request changed')
    data=json.loads(Path(path).read_bytes()); request=data['request']; roots=data['roots']
    source=safe(data['source_root'],directory=True); sys.path[:0]=[str(source),str(source/'src')]
    from tools.arc_consolidated_20261010.offline_bootstrap import _helpers,PINS
    helpers=_helpers(); work=Path(request['environment_root']); remaining(request)
    verified=helpers['arc_next_offline_interpreter.py'].validate_interpreter(
        roots['interpreter'],PINS['interpreter']['manifest_sha256'],work/'cpython312')
    require(Path(sys.executable).resolve()==Path(verified['python_executable']).resolve(),'exact prepared interpreter required')
    lock=runtime_lock(roots); environment=work/'environment-cp312-cu128'
    helpers['arc_next_offline_environment.py'].install_offline(lock,roots['wheels'],environment,enabled=True)
    remaining(request)
    installed=helpers['arc_next_offline_runtime.py']._runtime_environment({
        'environment_dir':str(environment),'runtime_root':roots['runtime'],'wheels_root':roots['wheels'],'pins':PINS})
    receipt={'python_command':installed['python_command'],'installed_offline':True,'reused_environment':False,
        'actual_environment_lock_path':installed['environment_lock'],'actual_environment_lock_sha256':sha(installed['environment_lock']),
        'interpreter':{k:verified[k] for k in ('manifest_sha256','archive_sha256','executable_sha256','verified_member_count')}}
    write(work/'installation-receipt.json',receipt)


def nonmodel_input_roots(input_root, references):
    """Lexically exclude only the retained Dataset/competition identities."""
    root=Path(input_root).absolute(); excluded=[]
    require(len(set(references))==8,'exact eight retained Dataset references required')
    for reference in references:
        owner,slug,version=reference.split('/')
        require(owner and slug and version.isdigit(),'versioned Dataset reference required')
        excluded.extend((root/slug,root/'datasets'/owner/slug))
    competition='arc-prize-2026-arc-agi-3'
    excluded.extend((root/competition,root/'competitions'/competition))
    return excluded


def discover_model(input_root, contract_path, excluded=()):
    """Bounded no-follow candidate discovery, then exact config/index/shard identity."""
    contract=json.loads(safe(contract_path).read_bytes()); rows=contract['provider_files']
    root=safe(input_root,directory=True); ignored={Path(p).absolute() for p in excluded}
    stack=[(root,0)]; candidates=[]; visited=0
    while stack:
        directory,depth=stack.pop()
        if directory in ignored: continue
        entries=[]
        with os.scandir(directory) as iterator:
            for entry in iterator:
                visited+=1
                require(visited<=8192,'bounded model discovery inventory exceeded')
                entries.append(entry)
        names={e.name:e for e in entries}
        if 'model.safetensors.index.json' in names and 'config.json' in names:
            require(all(not e.is_symlink() for e in entries),'model candidate symlink forbidden')
            exact=set(names)==set(rows) and all(e.is_file(follow_symlinks=False) for e in entries)
            if exact:
                exact=all(names[n].stat(follow_symlinks=False).st_size==r['size_bytes'] for n,r in rows.items())
            if exact:
                exact=all(sha(directory/n)==rows[n]['sha256'] for n in ('config.json','model.safetensors.index.json'))
            if exact:candidates.append(directory)
            continue
        if depth<7:
            for entry in entries:
                if entry.is_symlink(): continue
                if entry.is_dir(follow_symlinks=False):stack.append((Path(entry.path),depth+1))
    require(len(candidates)==1,'exactly one exact Qwen provider model mount required')
    return str(candidates[0])


def bootstrap_probe(request, ready):
    remaining(request); source=safe(ready['source_root'],directory=True)
    contract=safe(source/CONTRACT_RELATIVE)
    require(sha(contract)==CONTRACT_SHA256,'source-pinned material contract differs')
    roots=resolve_datasets(request['config']['input_root'])
    from tools.arc_consolidated_20261010.offline_bootstrap import PINS
    references=[p['reference'] for p in PINS.values()]+[request['pins'][role]['reference'] for role in ('code','data','training')]
    excluded=nonmodel_input_roots(request['config']['input_root'],references)
    model_root=discover_model(request['config']['input_root'],contract,excluded=excluded)
    installed=prepare_environment(request,source,roots)
    remaining(request)
    from tools.arc_qwen_probe_20261012.runner import run_owned_probe
    config={'enabled':True,'tiny_cpu':False,'training_root':ready['training_root'],
        'model':{'enabled':True,'model_key':'qwen3-14b','profile_id':'qwen3-14b-native-bf16-r8-c2048-probe-v1',
            'reviewed_deployment_id':'qwen3-14b-kaggle-v1-hf40c069-bf16-r8-c2048-first-probe-20261012',
            'model_path':model_root,'tokenizer_path':str(contract.parent/'hf-overlay'),'wheel_root_path':roots['wheels'],
            'contract_path':str(contract),'environment_lock_path':str(contract.parent/'environment-lock.json')},
        'started_epoch':request['started_epoch'],'maximum_seconds':PROBE_SECONDS}
    write(Path(request['launcher_root'])/'bootstrap-receipt.json',{'source_admission':ready['entry_provenance'],
        'offline_environment':installed,'model_mount':model_root,'public_answers_opened':False,
        'started_epoch':request['started_epoch'],'hard_deadline_epoch':request['hard_deadline_epoch']})
    result=run_owned_probe(config,ready['output_root'],python_command=installed['python_command'])
    write(Path(request['launcher_root'])/'result.json',result)
    return result


if __name__=='__main__':
    require(len(sys.argv)==4 and sys.argv[1]=='--install','owned installer entry required')
    install_child(sys.argv[2],sys.argv[3])

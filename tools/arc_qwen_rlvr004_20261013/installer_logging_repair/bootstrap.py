"""Owned offline bootstrap. Does not import torch or load model weights."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

PROBE_SECONDS = 43200
SESSION_SECONDS = 43200
OUTER_RESERVE_SECONDS = 120
INSTALL_FREE_RESERVE = 4 * 1024**3
CONTRACT_RELATIVE = 'materials/qwen14b/material-contract.json'
CONTRACT_SHA256 = '8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0'
INSTALL_LOG_BYTES = 8 * 1024**2
INSTALL_READ_BYTES = 64 * 1024
INSTALL_POLL_SECONDS = 0.1


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
    left=min(request['execution_deadline_epoch'],request['hard_deadline_epoch'])-time.time()-OUTER_RESERVE_SECONDS
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


def _installer_time_left(deadline_epoch, deadline_monotonic, now_epoch, now_monotonic):
    """The earlier wall/monotonic bound wins; neither clock can renew a budget."""
    require(all(math.isfinite(value) for value in
                (deadline_epoch, deadline_monotonic, now_epoch, now_monotonic)),
            'finite original installer deadlines required')
    left = min(deadline_epoch - now_epoch, deadline_monotonic - now_monotonic)
    if left <= 0:
        raise TimeoutError('offline installation original deadline reserve reached; inspect installation.log')
    return left


def _installer_cleanup(child, error):
    """Keep the first failure; secondary cleanup must never hide its cause."""
    if child is None:
        return error
    if error is not None:
        try:
            if child.poll() is None:
                child.kill()
            # Cleanup consumes the existing outer reserve, not a renewed work
            # budget. Never block propagation/outer tree closure indefinitely.
            child.wait(timeout=1)
        except BaseException:
            try:
                error.add_note('installer direct-child cleanup failed; enclosing owned tree closure is still required')
            except BaseException:
                pass
    if child.stdout is not None:
        try:
            child.stdout.close()
        except BaseException as close_error:
            if error is None:
                error = close_error
            else:
                try:
                    error.add_note('installer pipe close also failed; original failure preserved')
                except BaseException:
                    pass
    return error


def run_installer_bounded(argv, *, log, request, env):
    """Stream the combined log without escaping the enclosing OwnedProcessGuard.

    This is not an independent tree owner or a new session clock. The outer
    dedicated subreaper remains responsible for descendants and closure proof.
    On any failure, kill/reap this direct child and propagate the failure so
    that the existing owner closes the complete tree, including escaped sessions.
    """
    observed_monotonic = time.monotonic()
    available = remaining(request)
    require(math.isfinite(available), 'finite original installer budget required')
    deadline_monotonic = observed_monotonic + available
    deadline_epoch = min(request['execution_deadline_epoch'], request['hard_deadline_epoch']) - OUTER_RESERVE_SECONDS

    def time_left():
        return _installer_time_left(deadline_epoch, deadline_monotonic, time.time(), time.monotonic())

    child = None
    failure = None
    completed = None
    try:
        time_left()
        # No new session, shell, process group or nested subreaper. Inherit the
        # current owned tree; descendants cannot inherit the private log file.
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 env=env, bufsize=0, close_fds=True, start_new_session=False)
        with selectors.DefaultSelector() as selector:
            os.set_blocking(child.stdout.fileno(), False)
            selector.register(child.stdout, selectors.EVENT_READ)
            total = 0
            eof = False
            while not eof:
                for key, _ in selector.select(min(INSTALL_POLL_SECONDS, time_left())):
                    try:
                        block = os.read(key.fd, min(INSTALL_READ_BYTES, INSTALL_LOG_BYTES - total + 1))
                    except BlockingIOError:
                        continue
                    if not block:
                        eof = True
                        break
                    time_left()
                    capacity = INSTALL_LOG_BYTES - total
                    retained = memoryview(block)[:capacity]
                    while retained:
                        time_left()
                        written = log.write(retained)
                        if type(written) is not int or not 0 < written <= len(retained):
                            raise OSError('offline installation log write did not make valid progress')
                        total += written
                        retained = retained[written:]
                    if len(block) > capacity:
                        # The read is at most one byte beyond the remaining cap.
                        # Only its bounded prefix was retained, never a success.
                        raise ValueError('offline installation log byte ceiling exceeded; inspect installation.log')
        while child.poll() is None:
            try:
                child.wait(timeout=min(INSTALL_POLL_SECONDS, time_left()))
            except subprocess.TimeoutExpired:
                pass
        time_left()
        log.flush()
        time_left()
        completed = subprocess.CompletedProcess(argv, child.returncode)
    except BaseException as error:
        failure = error
    finally:
        failure = _installer_cleanup(child, failure)
    if failure is not None:
        raise failure
    return completed


def prepare_environment(request, source_root, roots):
    from tools.arc_consolidated_20261010.offline_bootstrap import _helpers,PINS
    helpers=_helpers(); lock=runtime_lock(roots)
    work=Path(request['environment_root'])
    require(not work.exists(),'fresh isolated environment required')
    work.mkdir(parents=True)
    wheel=helpers['arc_next_offline_environment.py'].validate_wheelhouse(lock,roots['wheels'],check_runtime=False)
    remaining(request)
    # Reserve installation expansion, largest-wheel temporary extraction, and4GiB.
    require(shutil.disk_usage(work).free>=17878110402,'insufficient disk for offline install, checkpoint store/export and4GiB reserve')
    interpreter=helpers['arc_next_offline_interpreter.py'].prepare_interpreter(
        roots['interpreter'],PINS['interpreter']['manifest_sha256'],work/'cpython312')
    install_request={'request':request,'roots':roots,'source_root':str(source_root)}
    path=work/'install-request.json';write(path,install_request)
    script=Path(__file__).absolute()
    with (work/'installation.log').open('xb') as log:
        completed=run_installer_bounded([interpreter['python_executable'],'-I','-B',str(script),'--install',str(path),sha(path)],
            log=log,request=request,
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
    from tools.arc_qwen_transfer_20261012.runner import run_owned_transfer
    from tools.arc_qwen_transfer_20261012.model_profile import PROFILE_ID, DEPLOYMENT_ID, MATERIAL_ADDENDUM_SHA256
    config={'enabled':True,'tiny_cpu':False,'training_root':ready['training_root'],
        'model':{'enabled':True,'model_key':'qwen3-14b','profile_id':PROFILE_ID,
            'reviewed_deployment_id':DEPLOYMENT_ID,'material_addendum_sha256':MATERIAL_ADDENDUM_SHA256,
            'context_limit':4096,'prompt_cap':3072,'output_cap':1024,'tensor_parallel_size':1,
            'precision':'bf16-base-fp32-lora','seed':1917,
            'model_path':model_root,'tokenizer_path':str(contract.parent/'hf-overlay'),'wheel_root_path':roots['wheels'],
            'contract_path':str(contract),'environment_lock_path':str(contract.parent/'environment-lock.json')},
        'started_epoch':request['started_epoch'],'maximum_seconds':PROBE_SECONDS,
        'public_exclusions_path':str(source/'panel-freeze/public120-exclusions.json'),
        'public_exclusions_sha256':'ef1d0f2812f42b221a24b6938ed1ee2b64b6165a3d071a5d2d55bb951976be9e',
        'public_solver_root':ready['solver_root'],'public_solver_manifest_sha256':ready['solver_manifest_sha256'],
        'public_evaluator_root':ready['evaluator_root'],'public_evaluator_manifest_sha256':ready['evaluator_manifest_sha256']}
    write(Path(request['launcher_root'])/'bootstrap-receipt.json',{'source_admission':ready['entry_provenance'],
        'offline_environment':installed,'model_mount':model_root,'public_answers_opened':False,
        'started_epoch':request['started_epoch'],'hard_deadline_epoch':request['hard_deadline_epoch'],
        'global_deadline_epoch':request['global_deadline_epoch'],
        'execution_deadline_epoch':request['execution_deadline_epoch'],
        'provider_deadline_epoch':request['provider_deadline_epoch']})
    result=run_owned_transfer(config,ready['output_root'],python_command=installed['python_command'])
    write(Path(request['launcher_root'])/'result.json',result)
    return result


if __name__=='__main__':
    require(len(sys.argv)==4 and sys.argv[1]=='--install','owned installer entry required')
    install_child(sys.argv[2],sys.argv[3])

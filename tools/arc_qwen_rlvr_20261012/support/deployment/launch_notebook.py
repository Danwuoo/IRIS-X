"""Verified parent notebook launch; model work is delegated to the owned runtime."""
from pathlib import Path
import json, os, selectors, subprocess, sys, time, types


def load_file(name,path):
    # Hash-bound .py bytes are always compiled directly. Never consult pyc caches.
    path=Path(path).absolute();module=types.ModuleType(name)
    module.__file__=str(path);module.__package__=name.rpartition('.')[0]
    sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(module))
    return module


def run_bounded(argv, *, guard_module, directory, deadline_epoch, env, scope):
    directory=Path(directory);directory.mkdir(exist_ok=False)
    started_epoch=time.time();started_monotonic=time.monotonic()
    remaining=deadline_epoch-started_epoch
    if remaining<=15:raise ValueError('original outer reserve exhausted')
    deadline_mono=time.monotonic()+remaining;forced=False;reason=None;proof=None
    with (directory/'stdout.txt').open('xb') as out,(directory/'stderr.txt').open('xb') as err:
        guard=guard_module.OwnedProcessGuard.spawn(argv,evidence_dir=directory/'owned-tree',stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            cwd=str(directory),close_fds=True,start_new_session=True,env=env)
        selector=selectors.DefaultSelector();total=0
        for stream,target in ((guard.child.stdout,out),(guard.child.stderr,err)):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,target)
        try:
            while True:
                exited=guard.poll() is not None
                for key,_ in selector.select(0 if exited else .2):
                    block=os.read(key.fileobj.fileno(),65536)
                    if not block:
                        selector.unregister(key.fileobj);continue
                    left=8*1024**2-total
                    if left>0:key.data.write(block[:left]);total+=min(left,len(block))
                    if len(block)>left:forced=True;reason='bounded-launcher-log-cap';break
                if forced or exited and not selector.get_map():break
                if time.monotonic()>=deadline_mono-10 or time.time()>=deadline_epoch-10:
                    forced=True;reason='original-outer-deadline';break
        except BaseException:
            forced=True;reason='parent-exception';raise
        finally:
            selector.close()
            proof=guard.stop(timeout=min(10,max(.1,deadline_mono-time.monotonic()))) if forced else guard.closed_proof()
            if not proof.get('closed') or proof.get('remaining'):
                forced=True;proof=guard.stop(timeout=min(10,max(.1,deadline_mono-time.monotonic())))
            receipt={'format':'irisx/rlvr-outer-process-closure-v1','scope':scope,'deadline_epoch':deadline_epoch,
                'started_epoch':started_epoch,'started_monotonic':started_monotonic,'completed_monotonic':time.monotonic(),
                'completed_epoch':time.time(),'within_deadline':time.time()<=deadline_epoch and time.monotonic()<=deadline_mono,
                'forced':forced,'reason':reason,'proof':proof,'log_bytes':total,'log_cap_bytes':8*1024**2,'VM_teardown_or_billing_claim':False}
            raw=(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
            if len(raw)>4*1024**2:raise ValueError('bounded parent closure receipt')
            (directory/'closure.json').write_bytes(raw)
    guard_module.verify_closed_proof(proof)
    if forced or not receipt['within_deadline'] or proof['returncode']!=0 or proof['worker_returncode']!=0 or proof['forced']:
        raise RuntimeError('owned parent preparation/runtime failed; preserve closure and logs')
    return receipt


def launch(*,ready,release,finalized,loader_source,output_root,input_root,epoch):
    here=Path(__file__).resolve().parent
    loader=load_file('rlvr_checked_loader',here/'source_loader.py')
    builder=load_file('rlvr_checked_builder',here/'notebook_builder.py')
    need=loader.need
    need(release.get('production_admitted') is True and release.get('release_role')=='rlvr001','production release admission absent')
    need(type(epoch) is int and 0<=time.time()-epoch<=42000-1800,'original clock is future/expired before preparation')
    output=loader.clean_path(output_root);parent=loader.clean_path(ready['source_root']).parent
    launcher=output.with_name(output.name+'-launcher');environment=Path('/tmp/irisx-qwen14b-rlvr-20261012-environment001')
    for path in (output,launcher,environment):
        loader.clean_path(path);need(not path.exists(),'fresh run and auxiliary paths required')
        need(not path.is_relative_to(parent) and not parent.is_relative_to(path),'source/output overlap')
    need(output_root==builder.OUTPUT and str(parent)==builder.SOURCE,'exact run001/source001 paths required')
    launcher.mkdir()
    notebook=builder.build(release,loader_source,kind='active-finalized',finalized=finalized)
    for name,value in (('outer.ipynb',notebook),('original-request.json',finalized['owner_request']),('operator.json',finalized['operator'])):
        with (launcher/name).open('xb') as stream:stream.write(builder.encoded(value))
    request={'format':'irisx/rlvr-parent-preparation-request-v1','ready':ready,'release':release,'finalized':finalized,
        'notebook_python_executable':sys.executable,'output_root':output_root,'input_root':input_root,'epoch':epoch,'launcher_root':str(launcher),'environment_root':str(environment)}
    request_path=launcher/'preparation-request.json';request_path.write_bytes(builder.encoded(request))
    source=Path(ready['source_root'])
    guard=load_file('rlvr_outer_guard',source/'baseline/tools/arc_learning_agent_20261011/process_guard.py')
    # Source-owned closed environment policy, evaluated before any preparation subprocess.
    loader.source_import_paths(source)
    from owned_runtime.parent_scoring import worker_environment
    env=worker_environment(fixture=False)
    receipt=run_bounded([sys.executable,'-I','-B',str(here/'prepare_entry.py'),str(request_path),loader.digest(request_path.read_bytes())],
        guard_module=guard,directory=launcher/'preparation',deadline_epoch=epoch+42180,env=env,scope='entire-owned-preparation-and-runtime')
    result=loader.parse(loader.read_regular(launcher/'result.json',2*1024**2))
    return {'status':result['status'],'source_sha256':ready['source_sha256'],'terminal_export':result.get('terminal_export'),
            'launcher_closed':receipt['proof']['closed'],'production_admitted':result.get('production_admitted',False)}

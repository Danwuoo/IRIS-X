"""Finite synthetic SFT139 load/cache/reset probe; zero ARC task-runs.

Four L4s are required by the unchanged native hardware boundary and all four
do bounded work. No optimizer, generation, evaluator, provider or scoring IO.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import Events, digest, require, write
from tools.nvarc_native_solve_runtime import SourceModel, reset_control, compare_vectors
from tools.nvarc_output_lifecycle import cleanup_workers, diagnostic, terminal_attempt
from tools.nvarc_public_eval import PhaseTelemetry, install_owner_guard
from tools.nvarc_public_eval_parent import prepare, stop_process
from tools.nvarc_public_eval_runtime import NativeEngine
from tools.nvarc_e10_screen import archive
from tools.nvarc_resource_attachment import verify_mount
from tools.nvarc_dependency_readproof import (RECEIPT_FILE, verify_before_prepare, require_worker_receipt)


def control_adapter(model,torch,emit,telemetry):
    # Legacy SourceModel requires positive limits in all slots. Its unused
    # generation/verification slots remain inaccessible through this closed
    # control-only scope and the event gate, rather than changing that contract.
    adapter=SourceModel(model,torch,emit,forward_limits={'control':7,'generation':1,'verification':1},
                        input_token_limit=168,generation_deadline=0)
    original_scope=adapter.scope
    from contextlib import contextmanager
    @contextmanager
    def scoped(phase):
        require(phase=='control','probe cannot enter generation/verification')
        with telemetry.scope('control'),original_scope(phase):yield
    adapter.scope=scoped
    return adapter


def verify_observations(events):
    reserved = [row for row in events if row['event'] == 'forward_reserved']
    completed = [row for row in events if row['event'] == 'forward_completed']
    require(len(reserved) <= 7 and all(row['phase'] == 'control' for row in reserved+completed) and
        sum(row['physical_input_tokens'] for row in reserved) <= 168 and
        len({row['call_id'] for row in completed}) == len(completed) and
        {row['call_id'] for row in completed} <= {row['call_id'] for row in reserved},
        'finite synthetic control-only probe ceilings differ')
    return {'reserved_forwards': len(reserved), 'completed_forwards': len(completed),
            'reserved_physical_input_tokens': sum(row['physical_input_tokens'] for row in reserved)}


def probe_binding(plan,rank):
    return {'probe_id':plan['screen_id'],'plan_digest':digest(plan),'rank':rank,
        'model_material_digest':plan['model_material_digest']}


def verify_worker_result(root,plan,rank,uuid):
    """Independent CPU receipt replay; this does not attest physical model IO."""
    root=Path(root);directory=root/'workers'/str(rank);binding=probe_binding(plan,rank)
    def read(name):
        path=directory/name;require(not path.is_symlink() and path.stat().st_size<=1024**2,
            'bounded confined probe receipt required')
        return parse_json(path.read_bytes())
    result=read('result.json');ready=read('ready.json')
    fields={'binding','outcome','errors','accounting','telemetry','baseline_restored','post_reset_control',
        'peak_host_rss_bytes','peak_cuda_allocated_bytes','optimizer_steps','generations','scientific_task_runs',
        'correctness_scored','ttt128_feasibility_established','gpu_kernel_timing_attestation',
        'cache_control','baseline_inventory_digest','reset_inventory_digest'}
    require(set(result)==fields and result['binding']==binding and type(result['binding']['rank']) is int and result['outcome']=='complete' and
        result['errors']==[] and result['baseline_restored'] is True and
        all(type(result[key]) is int and result[key]==0 for key in ('optimizer_steps','generations','scientific_task_runs')) and
        all(result[key] is False for key in ('correctness_scored','ttt128_feasibility_established','gpu_kernel_timing_attestation')),
        'exact completed control-only probe result binding required')
    require(type(ready['rank']) is int and type(ready['binding']['rank']) is int and ready=={'rank':rank,'uuid':uuid,'model_material_digest':plan['model_material_digest'],
        'baseline_digest':result['baseline_inventory_digest'],'torch':plan['runtime_torch_version'],
        'initial_control_forwards':{'control':6,'generation':0,'verification':0},'binding':binding} and
        result['baseline_inventory_digest']==result['reset_inventory_digest'] and
        isinstance(result['baseline_inventory_digest'],str) and
        __import__('re').fullmatch(r'sha256:[0-9a-f]{64}',result['baseline_inventory_digest']),
        'exact assigned-device native readiness/reset inventory required')
    for key,cap in (('peak_host_rss_bytes',plan['maximum_worker_host_rss_bytes']),
                    ('peak_cuda_allocated_bytes',plan['maximum_worker_cuda_allocated_bytes'])):
        require(type(result[key]) is int and 0<=result[key]<=cap,'observed finite probe memory bound required')
    ledger=directory/'events.jsonl'
    require(not ledger.is_symlink() and ledger.stat().st_size<=1024**2,'bounded confined probe ledger required')
    body=ledger.read_bytes();require(body.endswith(b'\n'),
        'complete bounded probe event ledger required')
    events=[];head=digest(binding)
    details={'forward_reserved':{'call_id','phase','batch_shape','physical_input_tokens','cached','position_start','position_end'},
        'forward_completed':{'call_id','phase','output_contract'},
        'cache_control_result':{'comparisons','baseline_prefill','deep_cached','sibling_cached','deep_reference','sibling_reference'}}
    for sequence,line in enumerate(body.splitlines()):
        row=parse_json(line);event=row['event']
        require(event in details and set(row)==set(binding)|{'sequence','previous','event','digest'}|details[event] and
            all(row[k]==v for k,v in binding.items()) and type(row['rank']) is int and type(row['sequence']) is int and row['sequence']==sequence and
            row['previous']==head and row['digest']==digest({k:v for k,v in row.items() if k!='digest'}),
            'exact probe event chain/binding differs')
        head=row['digest'];events.append(row)
    expected_order=[event for _ in range(6) for event in ('forward_reserved','forward_completed')]+[
        'cache_control_result','forward_reserved','forward_completed']
    require([row['event'] for row in events]==expected_order,'seven complete native controls/cache/reset order required')
    reservations=[r for r in events if r['event']=='forward_reserved']
    completions=[r for r in events if r['event']=='forward_completed']
    for index,(width,cached,start) in enumerate(((9,False,0),(1,True,9),(1,True,10),(1,True,9),
            (11,False,0),(10,False,0),(9,False,0)),1):
        r=reservations[index-1];c=completions[index-1]
        require(type(r['call_id']) is type(c['call_id']) is int and r['call_id']==c['call_id']==index and
            r['phase']==c['phase']=='control' and r['batch_shape']==[4,width] and
            type(r['physical_input_tokens']) is int and r['physical_input_tokens']==4*width and r['cached'] is cached and
            type(r['position_start']) is type(r['position_end']) is int and r['position_start']==start and r['position_end']==start+width-1 and
            c['output_contract'] in ('tuple-logits-cache','model-output-logits-cache'),
            'exact synthetic control forward/token/cache/position sequence required')
    require(result['accounting']==verify_observations(events)=={
        'reserved_forwards':7,'completed_forwards':7,'reserved_physical_input_tokens':168},
        'exact seven-forward/168-token completed accounting required')
    cache=events[12];comparisons={'deep':compare_vectors(cache['deep_reference'],cache['deep_cached']),
        'sibling_after_deep':compare_vectors(cache['sibling_reference'],cache['sibling_cached'])}
    # Also validate the full finite four-by-sixteen baseline vectors.
    compare_vectors(cache['baseline_prefill'],cache['baseline_prefill'])
    require(cache['comparisons']==comparisons and all(v['gate_passed'] for v in comparisons.values()) and
        result['cache_control']=={'comparisons':comparisons,'baseline_prefill':cache['baseline_prefill'],
            'model_calls':6,'synthetic_tokens_only':True,'full_numerical_parity_claim':False} and
        result['cache_control']['synthetic_tokens_only'] is True and result['cache_control']['full_numerical_parity_claim'] is False and
        type(result['post_reset_control']['additional_model_calls']) is int and
        result['post_reset_control']['synthetic_tokens_only'] is result['post_reset_control']['prefill_bitwise_equal'] is True and
        result['post_reset_control']=={'prefill_bitwise_equal':True,'prefill':cache['baseline_prefill'],
            'synthetic_tokens_only':True,'additional_model_calls':1},
        'independent native synthetic cache/reset control replay differs')
    telemetry=result['telemetry'];template=PhaseTelemetry().snapshot()
    require(set(telemetry)==set(template) and all(telemetry[k]==template[k] for k in
        ('format','clock','gpu_kernel_seconds','gpu_timing_semantics','aggregation','unobserved_phase_policy',
         'added_device_synchronizations','per_token_telemetry_writes','detailed_profiling','detail_inclusive_host_seconds',
         'training_forwards','tests','events')),
        'closed diagnostic probe host-observation semantics required')
    inclusive=telemetry['inclusive_host_seconds'];exclusive=telemetry['exclusive_host_seconds']
    require(set(inclusive)==set(exclusive)==set(PhaseTelemetry.PHASES) and
        all(v is None or type(v) in (int,float) and math.isfinite(v) and v>=0 for v in list(inclusive.values())+list(exclusive.values())) and
        all((inclusive[p] is None)==(exclusive[p] is None) and
            (exclusive[p] is None or exclusive[p]<=inclusive[p]+1e-9) for p in inclusive) and
        all(inclusive[p] is not None for p in ('load','reset','control')) and
        all(inclusive[p] is exclusive[p] is None for p in set(PhaseTelemetry.PHASES)-{'load','reset','control'}) and
        all(type(telemetry[k]) in (int,float) and math.isfinite(telemetry[k]) and telemetry[k]>=0 for k in
            ('elapsed_host_seconds','unscoped_host_seconds')) and
        all(v is None or v<=telemetry['elapsed_host_seconds']+1e-6 for v in inclusive.values()) and
        math.isclose(sum(v or 0 for v in exclusive.values())+telemetry['unscoped_host_seconds'],
            telemetry['elapsed_host_seconds'],abs_tol=1e-6),'consistent diagnostic probe host phase partition required')
    return result


def worker(root, dependency, model, rank, deadline, parent_pid, dependency_receipt_sha256=None):
    install_owner_guard(parent_pid, signal.SIGKILL)
    plan = parse_json((root/'plan.json').read_bytes()); output = root/'workers'/str(rank)
    binding = probe_binding(plan,rank)
    events = Events(output/'events.jsonl', binding); observed = []; adapters = []
    telemetry = PhaseTelemetry(); errors = []; engine = None; reset = None
    rss=None;peak=None;baseline_digest=None;reset_digest=None
    def emit(event, **details):
        if event == 'forward_reserved': require(time.time() < deadline, 'probe cooperative forward deadline exhausted')
        row = {'event': event, **details}; observed.append(row)
        if event.startswith('forward_'): verify_observations(observed)
        events.emit(event, **details)
    class ProbeEngine(NativeEngine):
        def adapter(self, _emit, tests=1):
            adapter=control_adapter(self.model,self.torch,emit,telemetry)
            adapters.append(adapter);return adapter
    try:
        require_worker_receipt(root,plan,dependency,dependency_receipt_sha256)
        with telemetry.scope('load'): engine = ProbeEngine(root, plan, model, dependency, rank)
        require(len(adapters) == 1, 'one bounded native warm adapter required')
        ready=parse_json((output/'ready.json').read_bytes());ready['binding']=binding
        write(output/'ready.json',ready)
        baseline_digest=digest(engine.baseline)
        with telemetry.scope('reset'):
            engine.restore(); engine.inference()
            restored=engine.inventory();reset_digest=digest(restored)
            require(restored == engine.baseline, 'synthetic probe baseline restoration differs')
        reset = reset_control(adapters[0], engine.initial_control)
        require(all(parameter.grad is None for parameter in engine.model.parameters()), 'probe created optimizer gradients')
        require(verify_observations(observed)=={'reserved_forwards':7,'completed_forwards':7,'reserved_physical_input_tokens':168},
            'complete probe requires exactly six cache and one reset control calls')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        peak = engine.torch.cuda.max_memory_allocated()
        require(rss <= plan['maximum_worker_host_rss_bytes'] and peak <= plan['maximum_worker_cuda_allocated_bytes'],
            'probe memory cap exceeded')
    except BaseException as error: errors.append(diagnostic(error, 'native-synthetic-load-cache-reset'))
    accounting = verify_observations(observed)
    value = {'binding': binding, 'outcome': 'failed' if errors else 'complete', 'errors': errors,
        'accounting': accounting, 'telemetry': telemetry.snapshot(), 'baseline_restored': reset is not None,
        'post_reset_control': reset, 'peak_host_rss_bytes': rss, 'peak_cuda_allocated_bytes': peak,
        'optimizer_steps':0, 'generations':0, 'scientific_task_runs':0, 'correctness_scored':False,
        'ttt128_feasibility_established':False, 'gpu_kernel_timing_attestation':False}
    value.update(cache_control=None if engine is None else engine.initial_control,
        baseline_inventory_digest=baseline_digest,reset_inventory_digest=reset_digest)
    published=terminal_attempt(value,lambda:write(output/'result.json',value),phase='probe-worker-result')
    return 1 if errors or not published else 0


def publish_terminal(root,terminal):
    def action():
        try:write(root/'terminal.json',terminal)
        except BaseException:
            terminal['outcome']='failed';raise
    ok=terminal_attempt(terminal,action,phase='probe-terminal')
    if not ok:
        terminal_attempt(terminal,lambda:write(root/'terminal-fallback.json',terminal),phase='probe-terminal-fallback')
    return ok


def execute(root, dependency, started):
    from tools.stage_nvarc_e10_probe import verify_runtime
    root = Path(root)
    # The runtime may be started by the owner from a save-only notebook. This
    # context does not admit the package to the automatic execution controller.
    owner_editor='owner_editor_admission' in parse_json((root/'plan.json').read_bytes())
    plan = verify_runtime(root, require_approved=not owner_editor, require_owner_editor=owner_editor)
    write(root/'coordinator-admitted.json', {'format':'irisx/probe-coordinator-admitted-v1',
        'run_id':plan['screen_id'], 'plan_digest':digest(plan)})

    states = {}; errors = []; results = {}; cleanup = {'all_producers_stopped':True}
    try:
        verify_before_prepare(root,plan,dependency,started)
        dependency_receipt_sha256=hashlib.sha256((root/RECEIPT_FILE).read_bytes()).hexdigest()
        write(root/'mount-policy.json',verify_mount(plan,'synthetic control tensors only'))
        model, hardware = prepare(root, plan, dependency)
        require(time.monotonic()-started <= plan['startup_seconds'], 'probe initial material/hardware budget exhausted')
        end = min(started+plan['maximum_notebook_wall_seconds']-plan['finalization_reserve_seconds'],
                  time.monotonic()+plan['maximum_worker_seconds'])
        deadline = time.time()+max(0,end-time.monotonic())
        for rank in range(4):
            directory = root/'workers'/str(rank); directory.mkdir(parents=True, exist_ok=False)
            state = {'identity':rank,'process':None,'streams':{}}; states[rank] = state
            for name in ('stdout','stderr'): state['streams'][name] = (directory/(name+'.log')).open('wb')
            environment = dict(os.environ,PYTHONHASHSEED='0',CUDA_VISIBLE_DEVICES=hardware[rank]['uuid'],
                PYTHONPATH=str(root)+os.pathsep+str(dependency),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                HF_DATASETS_OFFLINE='1',UNSLOTH_DISABLE_STATISTICS='1',WANDB_DISABLED='true',OMP_NUM_THREADS='2',
                TRITON_CACHE_DIR=str(directory/'triton-cache'),TRITON_PTXAS_PATH='/usr/local/cuda/bin/ptxas')
            write(directory/'launch-reservation.json',{'binding':digest(plan),'rank':rank,'deadline_epoch':deadline,
                'maximum_forwards':7,'maximum_physical_input_tokens':168})
            command = [sys.executable,str(root/'tools/nvarc_e10_probe.py'),'--root',str(root),'--dependency',str(dependency),
                '--model',str(model),'--rank',str(rank),'--deadline',str(deadline),'--parent-pid',str(os.getpid()),
                '--dependency-receipt-sha256',dependency_receipt_sha256]
            state['process'] = subprocess.Popen(command,env=environment,cwd=directory,start_new_session=True,
                stdout=state['streams']['stdout'],stderr=state['streams']['stderr'])
        while time.monotonic() < end and any(state['process'].poll() is None for state in states.values()): time.sleep(.1)
        for rank,state in states.items():
            require(state['process'].poll() == 0, 'native probe process failed or exceeded its finite deadline: '+str(rank))
            result = verify_worker_result(root,plan,rank,hardware[rank]['uuid'])
            results[str(rank)] = result
        require(sum(value['peak_host_rss_bytes'] for value in results.values()) <= plan['maximum_aggregate_host_rss_bytes'],
                'probe aggregate peak-RSS bound exceeded')
    except BaseException as error: errors.append(diagnostic(error,'probe-coordinator'))
    finally:
        try: cleanup = cleanup_workers(list(states.values()),stop_process,primary=sys.exception())
        except BaseException as error:
            errors.append(diagnostic(error,'probe-cleanup'));cleanup=getattr(error,'cleanup_report',{'all_producers_stopped':False})
    terminal = {'probe_id':plan['screen_id'],'plan_digest':digest(plan),'outcome':'failed' if errors else 'complete',
        'errors':errors,'results':results,'cleanup':cleanup,'host_wall_seconds':time.monotonic()-started,
        'allocated_gpu_hours_proxy':4*(time.monotonic()-started)/3600,'paid_usd':0,
        'optimizer_steps':0,'generations':0,'scientific_task_runs':0,'correctness_scored':False,
        'ttt128_feasibility_established':False,'promotion':False,'official_submission':False}
    publish_terminal(root,terminal)
    if cleanup['all_producers_stopped']:
        try: archive(root,root.parent/(plan['screen_id']+'.zip'),plan['maximum_archive_uncompressed_bytes'])
        except BaseException as error:
            terminal['outcome']='failed';terminal['errors'].append(diagnostic(error,'probe-archive'));publish_terminal(root,terminal)
    print(json.dumps(terminal),flush=True)
    return 0 if terminal['outcome']=='complete' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','dependency','model'):parser.add_argument('--'+name,type=Path,required=name!='model')
    parser.add_argument('--rank',type=int);parser.add_argument('--deadline',type=float);parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--dependency-receipt-sha256')
    parser.add_argument('--started',type=float);parser.add_argument('--owner-pid',type=int);args=parser.parse_args()
    require(os.environ.get('PYTHONHASHSEED')=='0' and sys.flags.hash_randomization==0,'fresh seed-zero probe process required')
    if args.rank is not None:return worker(args.root,args.dependency,args.model,args.rank,args.deadline,args.parent_pid,
        args.dependency_receipt_sha256)
    install_owner_guard(args.owner_pid,signal.SIGTERM)
    signal.signal(signal.SIGTERM,lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt('probe owner exited')))
    return execute(args.root,args.dependency,args.started)


if __name__=='__main__':raise SystemExit(main())

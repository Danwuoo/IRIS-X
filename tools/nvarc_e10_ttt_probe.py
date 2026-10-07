"""Four bounded native training epochs; no solve, generation or provider path.

Imports are CPU/standard-library orchestration only. Both coordinator and worker
must pass explicit execution admission before native dependency/model import.
The outer notebook alone finalizes the archive after coordinator/producer stop.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
import zipfile
import subprocess

# Keep startup capture available even if a packaged orchestration import fails.
# The recursively invoked copy has this flag removed; no native code is run here.
if __name__ == '__main__' and '--bootstrap' in sys.argv:
    root = Path(sys.argv[sys.argv.index('--root')+1])
    sys.argv.remove('--bootstrap')
    try:
        import runpy
        runpy.run_path(__file__,run_name='__main__')
    except BaseException as error:
        if not (isinstance(error,SystemExit) and error.code in (None,0)):
            value = {'format':'irisx/ttt-probe-entry-failure-v1','run_id':root.name,
                'type':type(error).__name__,'message':str(error)[:2400],
                'traceback':''.join(traceback.format_exception(error))[-12000:],
                'correctness_scored':False,'promotion':False}
            with (root/'bootstrap-failure.json').open('xb') as stream:
                stream.write(json.dumps(value,sort_keys=True).encode()); stream.flush(); os.fsync(stream.fileno())
        raise
    raise SystemExit(0)

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import Events, canonical, digest, require, write, public_training_material, training_deadline
from tools.nvarc_native_solve_runtime import reset_control, compare_vectors, discard_optimizer_state
from tools.nvarc_output_lifecycle import cleanup_workers, diagnostic, terminal_attempt
from tools.nvarc_public_eval import PhaseTelemetry, install_owner_guard
from tools.nvarc_public_eval_parent import prepare, stop_process
from tools.nvarc_public_eval_runtime import NativeEngine
from tools.nvarc_e10_probe import control_adapter, verify_observations, publish_terminal
from tools.nvarc_resource_attachment import verify_mount
from tools.nvarc_dependency_readproof import RECEIPT_FILE, verify_before_prepare, require_worker_receipt
from tools.nvarc_native_ttt_budget import EpochBudget
from tools.nvarc_native_ttt_schedule import native_schedule, ulp_distance, SOURCES, FUNCTIONS
from tools.nvarc_probe_bootstrap import _write_new, _read, _truth_free, OUTPUT_FILE, FAILURE_FILE, MAX_OUTPUT_BYTES


def binding(plan, rank):
    return {'probe_id':plan['screen_id'], 'plan_digest':digest(plan), 'rank':rank,
        'task_id':plan['task_order'][rank], 'model_material_digest':plan['model_material_digest']}


def preparation_guard(torch, record):
    from inspection_helpers import zero_work_guard
    return zero_work_guard(torch, record)


def training_accounting(ledger, spec, *, complete=False):
    keys = ('forwards','training_steps','optimizer_steps')
    require(all(isinstance(ledger.get(key),list) and len(ledger[key]) <= 128 for key in keys) and
        type(ledger.get('generation_calls')) is type(ledger.get('teacher_calls')) is int and
        ledger['generation_calls'] == ledger['teacher_calls'] == 0 and
        len(ledger.get('optimizer_constructions',[])) <= 1, 'finite native epoch counters required')
    require(all(type(row.get('completed')) is bool for key in (*keys,'optimizer_constructions') for row in ledger[key]) and
        all(type(row.get(field)) is int and row[field] >= 0 for row in ledger['forwards']
            for field in ('input_tokens','supervised_tokens')), 'strict native reservation/completion token types required')
    forwards = ledger['forwards']; steps = ledger['optimizer_steps']
    value = {'reserved_forwards':len(forwards), 'completed_forwards':sum(r['completed'] for r in forwards),
        'reserved_backwards':len(ledger['training_steps']),
        'completed_backwards':sum(r['completed'] for r in ledger['training_steps']),
        'reserved_updates':len(steps), 'completed_updates':sum(r['completed'] for r in steps),
        'reserved_input_tokens':sum(r['input_tokens'] for r in forwards),
        'reserved_supervised_tokens':sum(r['supervised_tokens'] for r in forwards)}
    require(value['reserved_input_tokens'] <= spec['training_input_tokens'] and
        value['reserved_supervised_tokens'] <= spec['training_supervised_tokens'], 'native token caps exceeded')
    if complete:
        require(all(value[key] == 128 for key in ('reserved_forwards','completed_forwards','reserved_backwards',
            'completed_backwards','reserved_updates','completed_updates')) and
            value['reserved_input_tokens'] == spec['training_input_tokens'] and
            value['reserved_supervised_tokens'] == spec['training_supervised_tokens'] and
            ledger['optimizer_constructions'] == [{'completed':True}], 'complete single native epoch required')
    return value


def wait_for_release(root, plan, rank, deadline):
    path = root/'training-release.json'
    while time.time() < deadline:
        if path.is_file():
            value = parse_json(path.read_bytes())
            require(value['plan_digest'] == digest(plan) and value['ranks'] == [0,1,2,3] and
                all(type(v) is int for v in value['ranks']) and
                type(value['training_deadline_epoch']) in (int,float) and
                math.isfinite(value['training_deadline_epoch']) and value['training_deadline_epoch'] <= deadline,
                'exact all-four-worker training barrier required')
            return value['training_deadline_epoch']
        time.sleep(.05)
    raise RuntimeError('four-worker preparation barrier deadline exhausted before training')


def worker(root, dependency, model, rank, deadline, parent_pid, dependency_receipt_sha256=None):
    from tools.stage_nvarc_e10_ttt_probe import verify_runtime
    root = Path(root); plan = verify_runtime(root, require_approved=True)
    require(type(rank) is int and 0 <= rank < 4 and math.isfinite(deadline), 'finite assigned worker required')
    install_owner_guard(parent_pid, signal.SIGKILL)
    output = root/'workers'/str(rank); key = plan['task_order'][rank]; spec = plan['task_specs'][key]
    bound = binding(plan,rank); events = Events(output/'events.jsonl',bound)
    observed = []; adapters = []; telemetry = PhaseTelemetry(); errors = []
    engine = trainer = budget = reset = None; baseline = trained = restored = moments = None
    training_start = training_end = None; optimizer_discarded = False; peak = rss = None
    def emit(event, **details):
        require(event in ('forward_reserved','forward_completed','cache_control_result'), 'control-only event required')
        if event == 'forward_reserved': require(time.time() < deadline, 'worker control deadline exhausted')
        observed.append({'event':event, **details}); verify_observations(observed); events.emit(event,**details)
    class TrainingEngine(NativeEngine):
        def adapter(self, _emit, tests=1):
            adapter = control_adapter(self.model,self.torch,emit,telemetry); adapters.append(adapter); return adapter
    try:
        require_worker_receipt(root,plan,dependency,dependency_receipt_sha256)
        with telemetry.scope('load'): engine = TrainingEngine(root,plan,model,dependency,rank)
        require(len(adapters) == 1, 'one native six-forward control adapter required')
        baseline = engine.inventory(); require(baseline == engine.baseline and len(baseline) == 506,
            'all 506 native saved tensors required before training')
        write(output/'baseline-inventory.json',baseline); write(output/'cache-control.json',engine.initial_control)
        ready = parse_json((output/'ready.json').read_bytes()); ready['binding'] = bound; write(output/'ready.json',ready)
        blocked = []
        with telemetry.scope('preparation'), preparation_guard(engine.torch,blocked.append) as guard:
            material = public_training_material(engine.loader,engine.tokenizer,key,
                parse_json((root/'challenges.json').read_bytes())[key])
            expected = parse_json((root/'materials'/f'{key}.json').read_bytes())
            require(material == expected and digest(material['rows']) == spec['expected_rows_digest'] and
                digest(material['texts']) == spec['texts_digest'], 'exact public-demo-only native material required')
            write(output/'texts.json',material['texts']); write(output/'expected-rows.json',material['rows'])
            trainer = engine.trainer(material['texts'],material['rows'],output)
            rates,schedule = native_schedule(engine.dependency,trainer.args,plan['native_source_learning_rates'])
            write(output/'native-schedule.json',schedule); guard()
        require(not blocked, 'unaccounted model/optimizer work during Trainer preparation')
        def retain(value):
            training_accounting(value,spec)
            with telemetry.detail('training_ledger_io'): write(output/'training-ledger.json',value)
        budget = EpochBudget(engine.torch,engine.model,trainer,material['rows'],rates,retain,
            expected_parameters=528564224,expected_dtype='torch.bfloat16')
        write(output/'training-ready.json', {'binding':bound, 'prepared_rows':128,
            'prepared_rows_digest':digest(material['rows']), 'control_forwards':6,
            'training_updates':0, 'ready_monotonic':time.monotonic()})
        released_deadline = wait_for_release(root,plan,rank,deadline-plan['reset_reserve_seconds'])
        training_start = time.monotonic()
        write(output/'training-window.json',{'start_monotonic':training_start,'end_monotonic':None})
        with telemetry.scope('training'):
            epoch_deadline = min(released_deadline,time.time()+plan['maximum_training_seconds'],
                deadline-plan['reset_reserve_seconds'])
            try:
                with training_deadline(budget,epoch_deadline): trainer.train(); moments = budget.complete()
            finally:
                training_end = time.monotonic()
                write(output/'training-window.json',{'start_monotonic':training_start,'end_monotonic':training_end})
            require(trainer.state.global_step == 128 and trainer.state.epoch == 1 and len(moments) == 506,
                'complete 128-step epoch and all 506 finite Adam moment states required')
            training_accounting(budget.state,spec,complete=True)
            write(output/'optimizer-state.json',moments)
            trained = engine.inventory()
            require(changed_tensors(baseline,trained) > 0,
                'native saved tensor inventory must change during full TTT')
            write(output/'trained-inventory.json',trained)
    except BaseException as error: errors.append(diagnostic(error,'native-ttt-resource-worker'))
    finally:
        if engine is not None:
            try:
                with telemetry.scope('reset'):
                    if trainer is not None: discard_optimizer_state(engine.model,trainer,budget)
                    optimizer_discarded = (trainer is None or trainer.optimizer is trainer.lr_scheduler is None and
                        not trainer.accelerator._optimizers and not trainer.accelerator._schedulers and
                        (budget is None or budget.optimizer is None)) and all(p.grad is None for p in engine.model.parameters())
                    require(optimizer_discarded, 'optimizer/gradient state survived discard')
                    engine.restore(); engine.inference(); restored = engine.inventory()
                    write(output/'reset-inventory.json',restored)
                    require(restored == baseline == engine.baseline, 'all saved native tensors must restore exactly')
                    reset = reset_control(adapters[0],engine.initial_control)
                    write(output/'post-reset-control.json',reset)
                rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
                peak = engine.torch.cuda.max_memory_allocated()
                require(rss <= plan['maximum_worker_host_rss_bytes'] and peak <= plan['maximum_worker_cuda_allocated_bytes'],
                    'resource probe memory cap exceeded')
            except BaseException as error: errors.append(diagnostic(error,'native-ttt-resource-reset'))
    ledger = budget.state if budget is not None else {'forwards':[],'training_steps':[],'optimizer_steps':[],
        'optimizer_constructions':[],'generation_calls':0,'teacher_calls':0}
    value = {'binding':bound, 'outcome':'failed' if errors else 'complete', 'errors':errors,
        'training':training_accounting(ledger,spec), 'controls':verify_observations(observed),
        'telemetry':telemetry.snapshot(), 'optimizer_discarded':optimizer_discarded,
        'baseline_inventory_digest':None if baseline is None else digest(baseline),
        'trained_inventory_digest':None if trained is None else digest(trained),
        'changed_saved_tensor_count':None if trained is None or baseline is None else
            sum(a['sha256'] != b['sha256'] for a,b in zip(trained,baseline)),
        'reset_inventory_digest':None if restored is None else digest(restored),
        'post_reset_control':reset, 'peak_host_rss_bytes':rss, 'peak_cuda_allocated_bytes':peak,
        'training_start_monotonic':training_start, 'training_end_monotonic':training_end,
        'generations':0, 'correctness_scored':False, 'promotion':False, 'gpu_kernel_timing_attestation':False}
    ok = terminal_attempt(value,lambda:write(output/'result.json',value),phase='ttt-probe-worker-result')
    return 1 if errors or not ok else 0


def changed_tensors(baseline, trained):
    require(len(baseline) == len(trained) == 506 and all(
        {k:v for k,v in a.items() if k != 'sha256'} == {k:v for k,v in b.items() if k != 'sha256'} and
        all(type(r.get('sha256')) is str and len(r['sha256']) == 64 and
            all(c in '0123456789abcdef' for c in r['sha256']) for r in (a,b))
        for a,b in zip(baseline,trained)), 'unchanged tensor layout and exact SHA256 values required')
    return sum(a['sha256'] != b['sha256'] for a,b in zip(baseline,trained))


RESULT_FIELDS = frozenset(('binding','outcome','errors','training','controls','telemetry','optimizer_discarded',
    'baseline_inventory_digest','trained_inventory_digest','changed_saved_tensor_count','reset_inventory_digest',
    'post_reset_control','peak_host_rss_bytes','peak_cuda_allocated_bytes','training_start_monotonic',
    'training_end_monotonic','generations','correctness_scored','promotion','gpu_kernel_timing_attestation'))


def verify_worker_result(root, plan, rank, uuid):
    """CPU replay of retained rows, updates, rates, controls and reset evidence."""
    directory = Path(root)/'workers'/str(rank); spec = plan['task_specs'][plan['task_order'][rank]]
    def read(name): return parse_json(_read(directory/name,8*1024**2))
    result = read('result.json'); bound = binding(plan,rank)
    require(set(result) == RESULT_FIELDS and result['binding'] == bound and type(result['binding']['rank']) is int and
        result['outcome'] == 'complete' and result['errors'] == [] and
        result['optimizer_discarded'] is True and type(result['generations']) is int and result['generations'] == 0 and
        result['correctness_scored'] is result['promotion'] is result['gpu_kernel_timing_attestation'] is False,
        'complete bound resource-only worker required')
    ready = read('ready.json')
    require(type(ready['rank']) is type(ready['binding']['rank']) is int and
        all(type(v) is int for v in ready['initial_control_forwards'].values()) and
        ready == {'rank':rank,'uuid':uuid,'model_material_digest':plan['model_material_digest'],
        'baseline_digest':result['baseline_inventory_digest'],'torch':plan['runtime_torch_version'],
        'initial_control_forwards':{'control':6,'generation':0,'verification':0},'binding':bound},
        'exact assigned-device load/cache readiness required')
    rows = read('expected-rows.json'); texts = read('texts.json'); ledger = read('training-ledger.json')
    require(digest(rows) == spec['expected_rows_digest'] and digest(texts) == spec['texts_digest'] and
        len(rows) == len(texts) == 128 and result['training'] == training_accounting(ledger,spec,complete=True) and
        Counter((r['input_ids_digest'],r['labels_digest'],r['input_tokens'],r['supervised_tokens']) for r in rows) ==
        Counter((r['input_ids_digest'],r['labels_digest'],r['input_tokens'],r['supervised_tokens']) for r in ledger['forwards']),
        'exact 128-row native multiset and actual training ledger required')
    schedule = read('native-schedule.json'); rates = schedule['rates']
    distances = [ulp_distance(a,b) for a,b in zip(rates,plan['native_source_learning_rates'])]
    require(set(schedule) == {'source_sha256','function_sha256','warmup_steps','epoch_steps','rates',
        'reference_rates_sha256','reference_ulp_distances','maximum_reference_ulp_distance','platform','python',
        'model_calls','optimizer_steps','policy'} and schedule['source_sha256'] == SOURCES and
        schedule['function_sha256'] == FUNCTIONS and
        all(type(schedule[k]) is int and schedule[k] == v for k,v in
            (('warmup_steps',13),('epoch_steps',128),('model_calls',0),('optimizer_steps',0))) and
        schedule['reference_rates_sha256'] == hashlib.sha256(json.dumps(plan['native_source_learning_rates'],
            separators=(',',':')).encode()).hexdigest() and schedule['reference_ulp_distances'] == distances and
        all(type(v) is int for v in schedule['reference_ulp_distances']) and
        type(schedule['maximum_reference_ulp_distance']) is int and
        schedule['maximum_reference_ulp_distance'] == max(distances) and
        all(type(schedule[k]) is str and bool(schedule[k]) for k in ('platform','python')) and
        schedule['policy'] == 'optimizer rate must exactly equal same-platform pinned scalar replay; reference differs by at most four ULPs',
        'exact native scalar schedule provenance required')
    require(len(rates) == 129 and all(ulp_distance(a,b) <= 4 for a,b in zip(rates,plan['native_source_learning_rates'])) and
        rates[0] == rates[-1] == 0 and rates[13] == 5e-5 and
        all(type(r['learning_rate']) in (int,float) and r['learning_rate'] == rates[i] and
            type(r['gradient_tensors']) is int and r['gradient_tensors'] == 506 and
            type(r['gradient_norm_after_clip']) in (float,int) and math.isfinite(r['gradient_norm_after_clip']) and
            0 <= r['gradient_norm_after_clip'] <= 1.05 for i,r in enumerate(ledger['optimizer_steps'])) and
        all(type(r['loss']) in (int,float) and math.isfinite(r['loss']) for r in ledger['forwards']),
        'same-platform exact rates and all 506 finite gradients required')
    moments = read('optimizer-state.json')
    require(len(moments) == 506 and sum(r['elements'] for r in moments) == 528564224 and all(
        all(type(r[k]) is int for k in ('step','elements','moment_bytes')) and r['elements'] > 0 and
        r['step'] == 128 and r['finite'] is True and r['parameter_dtype'] == 'torch.bfloat16' and
        r['parameter_device'] == 'cuda:0' and r['moment_bytes'] == 4*r['elements'] for r in moments),
        'all 506 finite BF16 CUDA Adam states at step 128 required')
    baseline = read('baseline-inventory.json'); trained = read('trained-inventory.json'); restored = read('reset-inventory.json')
    changed = changed_tensors(baseline,trained)
    require(restored == baseline and changed > 0 and
        all(r['finite'] is True and r['dtype'] == 'torch.bfloat16' for inv in (baseline,trained,restored) for r in inv) and
        type(result['changed_saved_tensor_count']) is int and result['changed_saved_tensor_count'] == changed and
        [digest(v) for v in (baseline,trained,restored)] == [result[k+'_inventory_digest'] for k in ('baseline','trained','reset')],
        'all 506 trained and exactly restored tensor inventories required')
    observed = []; head = digest(bound); body = _read(directory/'events.jsonl',1024**2)
    require(body.endswith(b'\n'), 'complete control event chain required')
    for i,line in enumerate(body.splitlines()):
        row = parse_json(line)
        require(all(row[k] == v for k,v in bound.items()) and type(row['rank']) is type(row['sequence']) is int and
            row['sequence'] == i and row['previous'] == head and
            row['digest'] == digest({k:v for k,v in row.items() if k != 'digest'}), 'control event chain differs')
        head = row['digest']; observed.append(row)
    require([r['event'] for r in observed] == ['forward_reserved','forward_completed']*6+
        ['cache_control_result','forward_reserved','forward_completed'] and
        result['controls'] == verify_observations(observed) == {
            'reserved_forwards':7,'completed_forwards':7,'reserved_physical_input_tokens':168}, 'exact seven controls required')
    reservations = [r for r in observed if r['event'] == 'forward_reserved']
    completions = [r for r in observed if r['event'] == 'forward_completed']
    for i,(width,cached,start) in enumerate(((9,False,0),(1,True,9),(1,True,10),(1,True,9),
            (11,False,0),(10,False,0),(9,False,0))):
        r = reservations[i]
        require(all(type(r[k]) is int for k in ('call_id','physical_input_tokens','position_start','position_end')) and
            all(type(v) is int for v in r['batch_shape']) and
            r['call_id'] == i+1 and r['batch_shape'] == [4,width] and r['physical_input_tokens'] == 4*width and
            r['cached'] is cached and r['position_start'] == start and r['position_end'] == start+width-1,
            'exact cache/reset synthetic sequence required')
        require(type(completions[i]['call_id']) is int and completions[i]['call_id'] == i+1 and
            completions[i]['output_contract'] in ('tuple-logits-cache','model-output-logits-cache'),
            'exact completed synthetic forward required')
    cache = observed[12]; comparisons = {'deep':compare_vectors(cache['deep_reference'],cache['deep_cached']),
        'sibling_after_deep':compare_vectors(cache['sibling_reference'],cache['sibling_cached'])}
    reset = read('post-reset-control.json')
    vectors = [cache[k] for k in ('baseline_prefill','deep_reference','deep_cached','sibling_reference','sibling_cached')]
    vectors.append(reset['prefill'])
    require(all(type(v) is list and len(v) == 4 and all(type(row) is list and len(row) == 16 and
        all(type(x) in (int,float) and math.isfinite(x) for x in row) for row in v) for v in vectors) and
        all(r['prefill_bitwise_equal'] is True and r['synthetic_tokens_only'] is True and
            type(r['additional_model_calls']) is int and r['additional_model_calls'] == 1
            for r in (reset,result['post_reset_control'])),
        'finite complete synthetic vectors and strict reset flags required')
    require(cache['comparisons'] == comparisons and all(v['gate_passed'] for v in comparisons.values()) and
        reset == result['post_reset_control'] == {'prefill_bitwise_equal':True,'prefill':cache['baseline_prefill'],
            'synthetic_tokens_only':True,'additional_model_calls':1}, 'actual cache and seventh reset control required')
    window = read('training-window.json')
    require(window == {'start_monotonic':result['training_start_monotonic'],'end_monotonic':result['training_end_monotonic']} and
        all(type(v) in (int,float) and math.isfinite(v) for v in window.values()) and
        0 <= window['end_monotonic']-window['start_monotonic'] <= plan['maximum_training_seconds'],
        'bounded actual shared-host training window required')
    for field, cap in (('peak_host_rss_bytes',plan['maximum_worker_host_rss_bytes']),
                       ('peak_cuda_allocated_bytes',plan['maximum_worker_cuda_allocated_bytes'])):
        require(type(result[field]) is int and 0 <= result[field] <= cap, 'bounded observed memory required')
    return result


def execute(root, dependency, started):
    from tools.stage_nvarc_e10_ttt_probe import verify_runtime, SCOPE
    root = Path(root); plan = verify_runtime(root,require_approved=True)
    write(root/'coordinator-admitted.json',{'run_id':plan['run_id'],'plan_digest':digest(plan)})
    states = {}; results = {}; errors = []; cleanup = {'all_producers_stopped':True}; overlap = None
    try:
        verify_before_prepare(root,plan,dependency,started)
        receipt_sha = hashlib.sha256((root/RECEIPT_FILE).read_bytes()).hexdigest()
        write(root/'mount-policy.json',verify_mount(plan,SCOPE)); model,hardware = prepare(root,plan,dependency)
        require(time.monotonic()-started < plan['startup_seconds'], 'initial material/hardware budget exhausted')
        end = min(started+plan['maximum_notebook_wall_seconds']-plan['finalization_reserve_seconds'],
            time.monotonic()+plan['maximum_worker_seconds'])
        deadline = time.time()+max(0,end-time.monotonic())
        for rank in range(4):
            directory = root/'workers'/str(rank); directory.mkdir(parents=True,exist_ok=False)
            state = {'identity':rank,'process':None,'streams':{}}; states[rank] = state
            for name in ('stdout','stderr'): state['streams'][name] = (directory/(name+'.log')).open('wb')
            environment = dict(os.environ,PYTHONHASHSEED='0',CUDA_VISIBLE_DEVICES=hardware[rank]['uuid'],
                PYTHONPATH=str(root)+os.pathsep+str(dependency),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                HF_DATASETS_OFFLINE='1',UNSLOTH_DISABLE_STATISTICS='1',WANDB_DISABLED='true',OMP_NUM_THREADS='2',
                MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',PYTHONIOENCODING='utf-8',
                TRITON_CACHE_DIR=str(directory/'triton-cache'),TRITON_PTXAS_PATH='/usr/local/cuda/bin/ptxas')
            write(directory/'launch-reservation.json',{'binding':binding(plan,rank),'deadline_epoch':deadline,
                'training_updates':128,'control_forwards':7,'attempt':1})
            command = [sys.executable,str(root/'tools/nvarc_e10_ttt_probe.py'),'--root',str(root),'--dependency',str(dependency),
                '--model',str(model),'--rank',str(rank),'--deadline',str(deadline),'--parent-pid',str(os.getpid()),
                '--dependency-receipt-sha256',receipt_sha]
            state['process'] = subprocess.Popen(command,env=environment,cwd=directory,start_new_session=True,
                stdout=state['streams']['stdout'],stderr=state['streams']['stderr'])
        ready = {}
        while time.monotonic() < min(started+plan['startup_seconds'],end-plan['reset_reserve_seconds']):
            for rank,state in states.items():
                require(state['process'].poll() is None, 'worker failed before all-four preparation barrier: '+str(rank))
                path = root/'workers'/str(rank)/'training-ready.json'
                if path.is_file():
                    value = parse_json(path.read_bytes()); spec = plan['task_specs'][plan['task_order'][rank]]
                    require(value['binding'] == binding(plan,rank) and type(value['binding']['rank']) is int and
                        all(type(value[k]) is int for k in ('prepared_rows','control_forwards','training_updates')) and
                        value['prepared_rows'] == 128 and
                        value['prepared_rows_digest'] == spec['expected_rows_digest'] and
                        value['control_forwards'] == 6 and value['training_updates'] == 0,
                        'exact six-control/full-Trainer preparation barrier required')
                    ready[str(rank)] = value
            if len(ready) == 4: break
            time.sleep(.05)
        require(len(ready) == 4, 'all four native Trainers must be ready inside startup allowance')
        write(root/'training-release.json',{'plan_digest':digest(plan),'ranks':[0,1,2,3], 'ready':ready,
            'release_monotonic':time.monotonic(),
            'training_deadline_epoch':min(time.time()+plan['maximum_training_seconds'],deadline-plan['reset_reserve_seconds'])})
        while time.monotonic() < end and any(s['process'].poll() is None for s in states.values()):
            require(not any(s['process'].poll() not in (None,0) for s in states.values()),
                'native worker failed; remaining workers stopped without retry')
            time.sleep(.1)
        for rank,state in states.items():
            require(state['process'].poll() == 0, 'native training process failed or exceeded finite deadline: '+str(rank))
            results[str(rank)] = verify_worker_result(root,plan,rank,hardware[rank]['uuid'])
        require(sum(r['peak_host_rss_bytes'] for r in results.values()) <= plan['maximum_aggregate_host_rss_bytes'],
            'aggregate host memory cap exceeded')
        overlap = min(r['training_end_monotonic'] for r in results.values())-max(r['training_start_monotonic'] for r in results.values())
        require(overlap > 0, 'all four native training windows must overlap on the shared host clock')
    except BaseException as error: errors.append(diagnostic(error,'ttt-probe-coordinator'))
    finally:
        try: cleanup = cleanup_workers(list(states.values()),stop_process,primary=sys.exception())
        except BaseException as error:
            errors.append(diagnostic(error,'ttt-probe-cleanup')); cleanup = getattr(error,'cleanup_report',{'all_producers_stopped':False})
    terminal = {'probe_id':plan['screen_id'],'plan_digest':digest(plan),'outcome':'failed' if errors else 'complete',
        'errors':errors,'results':results,'cleanup':cleanup,'host_wall_seconds':time.monotonic()-started,
        'simultaneous_training_overlap_host_seconds':overlap, 'paid_usd':0,'generations':0,
        'correctness_scored':False,'promotion':False,'official_submission':False,
        'full_screen_feasibility_established':False,'gpu_kernel_timing_attestation':False,
        'archive_finalization':'outer notebook after coordinator stop and finalized stdout capture'}
    publish_terminal(root,terminal); print(json.dumps(terminal),flush=True)
    return 0 if terminal['outcome'] == 'complete' else 1


def finalize(root, observation, expected_plan_sha256):
    """Finalize NEW output once after capture closes; never alter an older ZIP."""
    from tools.nvarc_runtime_archive import validate_members, runtime_files
    root = Path(root); destination = root.parent/(root.name+'.zip')
    result = {'final_archive_created':False,'diagnostic_only_archive_created':False,
        'existing_archive_preserved':destination.exists(),'diagnostic_errors':[],'coordinator_diagnostic_excerpt':''}
    if destination.exists(): return result
    hard = observation.get('hard_deadline_monotonic')
    def remaining():
        require(type(hard) in (int,float) and math.isfinite(hard) and time.monotonic() < hard,
            'outer absolute notebook deadline exhausted or missing during finalization')
    def read(path,limit):
        remaining(); body = _read(path,limit); remaining(); return body
    def add(archive,name,body):
        remaining()
        with archive.open(name,'w') as stream:
            for offset in range(0,len(body),65536):
                remaining(); stream.write(body[offset:offset+65536])
        remaining()
    stopped = False
    try:
        screen = read(root/'screen.json',8*1024**2)
        require(hashlib.sha256(screen).hexdigest() == expected_plan_sha256 and
            parse_json(screen)['screen_id'] == root.name, 'exact immutable finalization plan required')
        require(observation.get('confirmed_stopped') is True, 'confirmed outer coordinator stop required')
        capture = read(root/OUTPUT_FILE,MAX_OUTPUT_BYTES)
        require(observation.get('output_capture',{}).get('written') is True and
            observation['output_capture']['bytes_retained'] == len(capture), 'finalized bounded output capture required')
        result['coordinator_diagnostic_excerpt'] = capture[-12000:].decode('utf-8',errors='replace')
        remaining(); _write_new(root/'outer-supervision.json',observation); remaining()
        terminal = None
        for name in ('terminal.json','terminal-fallback.json'):
            if (root/name).exists(): terminal = parse_json(read(root/name,1024**2)); break
        startup_only = (root/FAILURE_FILE).is_file() and not (root/'coordinator-admitted.json').exists() and not (root/'workers').exists()
        stopped = startup_only or type(terminal) is dict and terminal.get('cleanup',{}).get('all_producers_stopped') is True
        require(stopped,
            'confirmed model producer cleanup or pre-admission startup failure required')
        cap = parse_json(screen)['maximum_archive_uncompressed_bytes']; sizes = {}; total = 0
        for path in runtime_files(root):
            remaining()
            parts = path.relative_to(root).parts
            if any(part in ('__pycache__','triton-cache','unsloth_compiled_cache') for part in parts): continue
            size = path.stat(follow_symlinks=False).st_size; total += size
            require(size <= min(cap,8*1024**2) and total <= cap, 'bounded TTT evidence archive required before reading')
            sizes[path] = size
        def bounded_read(path):
            require(path in sizes, 'only size-admitted evidence may be read')
            return read(path,sizes[path])
        interrupted = []; files = validate_members(root,interrupted=interrupted,read_bytes=bounded_read)
        index = canonical({'format':'irisx/unqualified-interrupted-artifacts-v1',
            'artifacts':interrupted,'promotion':False,'candidate_qualification':False}) if interrupted else None
        require(total+(len(index) if index else 0) <= cap,
            'bounded TTT evidence archive required')
        temporary = destination.with_suffix('.zip.tmp')
        with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
            for path in files: add(archive,path.relative_to(root).as_posix(),bounded_read(path))
            if index and not (root/'interrupted-retention.json').exists():add(archive,'interrupted-retention.json',index)
        remaining(); os.link(temporary,destination); temporary.unlink(); result['final_archive_created'] = True
    except BaseException as error:
        result['diagnostic_errors'].append(type(error).__name__+': '+str(error)[:1000])
        # Bounded startup/failure diagnostics may still be recovered, but never
        # disguise missing runtime evidence or an unconfirmed producer stop.
        if observation.get('confirmed_stopped') is True and stopped and not destination.exists():
            try:
                screen = read(root/'screen.json',8*1024**2)
                require(hashlib.sha256(screen).hexdigest() == expected_plan_sha256, 'exact diagnostic plan required')
                members = {'screen.json':screen}
                for name,limit in ((FAILURE_FILE,32*1024),('outer-supervision.json',16*1024),
                        (OUTPUT_FILE,MAX_OUTPUT_BYTES),('terminal.json',1024**2),('terminal-fallback.json',1024**2)):
                    if (root/name).exists():
                        body = read(root/name,limit)
                        if name.endswith('.json'): _truth_free(parse_json(body))
                        members[name] = body
                require('outer-supervision.json' in members and OUTPUT_FILE in members,
                    'diagnostic archive requires actual post-stop receipt and capture')
                members['diagnostic-only.json'] = canonical({'format':'irisx/ttt-probe-diagnostic-only-v1',
                    'complete_runtime_evidence':False,'promotion':False,'errors':result['diagnostic_errors']})
                temporary = destination.with_suffix('.diagnostic.zip.tmp')
                with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_DEFLATED) as archive:
                    for name,body in sorted(members.items()): add(archive,name,body)
                remaining(); os.link(temporary,destination); temporary.unlink(); result['diagnostic_only_archive_created'] = True
            except BaseException as secondary: result['diagnostic_errors'].append(str(secondary)[:1000])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root','dependency','model'): parser.add_argument('--'+name,type=Path,required=name != 'model')
    parser.add_argument('--rank',type=int); parser.add_argument('--deadline',type=float); parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--dependency-receipt-sha256'); parser.add_argument('--started',type=float)
    parser.add_argument('--owner-pid',type=int); parser.add_argument('--bootstrap',action='store_true'); args = parser.parse_args()
    try:
        require(os.environ.get('PYTHONHASHSEED') == '0' and sys.flags.hash_randomization == 0,
            'fresh seed-zero TTT probe process required')
        if args.rank is not None:
            return worker(args.root,args.dependency,args.model,args.rank,args.deadline,args.parent_pid,args.dependency_receipt_sha256)
        from tools.stage_nvarc_e10_ttt_probe import verify_runtime
        verify_runtime(args.root,require_approved=True)
        install_owner_guard(args.owner_pid,signal.SIGTERM)
        signal.signal(signal.SIGTERM,lambda *_a: (_ for _ in ()).throw(KeyboardInterrupt('TTT probe owner exited')))
        return execute(args.root,args.dependency,args.started)
    except BaseException as error:
        if args.bootstrap:
            _write_new(args.root/FAILURE_FILE,{'format':'irisx/ttt-probe-entry-failure-v1','run_id':args.root.name,
                'type':type(error).__name__,'message':str(error)[:2400],
                'traceback':''.join(traceback.format_exception(error))[-12000:],
                'correctness_scored':False,'promotion':False})
        raise


if __name__ == '__main__': raise SystemExit(main())

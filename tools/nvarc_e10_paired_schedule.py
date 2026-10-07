"""Truth-free paired inference from one retained native trained state.

No provider operations. The entry points reject INERT admission before native
imports. Pairing adds no training, warmup, synthetic controls or model forwards.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import signal
import sys
import time
import traceback

# Retain bounded startup diagnostics even if an orchestration import fails.
# No native/model import or producer launch occurs in this outer wrapper.
if __name__=='__main__' and '--bootstrap' in sys.argv:
    root=Path(sys.argv[sys.argv.index('--root')+1]);sys.argv.remove('--bootstrap')
    try:
        import runpy
        runpy.run_path(__file__,run_name='__main__')
    except BaseException as error:
        if not (isinstance(error,SystemExit) and error.code in (None,0)):
            value={'format':'irisx/ttt-probe-entry-failure-v1','run_id':root.name,
                'type':type(error).__name__,'message':str(error)[:2400],
                'traceback':''.join(traceback.format_exception(error))[-12000:],
                'correctness_scored':False,'promotion':False}
            with (root/'bootstrap-failure.json').open('xb') as stream:
                stream.write(json.dumps(value,sort_keys=True).encode());stream.flush();os.fsync(stream.fileno())
        raise
    raise SystemExit(0)

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical,digest,require,write,allocation_deadlines
from tools.nvarc_native_submission import reject_truth
from tools.nvarc_output_lifecycle import diagnostic,GenerationStore
from tools import nvarc_e10_answer_evidence as evidence
from tools import nvarc_e10_end_to_end as native_epoch
from tools.nvarc_public_eval import PhaseTelemetry,install_owner_guard

FORMAT='irisx/stage4-e10-paired-schedule-v1'
RUN_ID='stage4-e10-probe-paired-schedule-20261007-001'
PROFILE='paired-schedule-v8'
ARMS=('interleaved','deferred')
TASK_COUNTS={'195c6913':2,'aa4ec2a5':1,'a47bf94d':1,'a25697e4':2}
TIMING=dict(generation_seconds=120,verification_reserve_seconds=30,per_test_seconds=150,
    startup_seconds=900,maximum_training_seconds=1200,inference_reserve_seconds=600,
    reset_reserve_seconds=180,finalization_reserve_seconds=600,maximum_worker_seconds=2880,
    maximum_notebook_wall_seconds=3600)
CAPS=dict(maximum_generation_forwards=49152,maximum_verification_forwards=1536,
    maximum_inference_input_tokens=62914560,maximum_processed_sequences_total=768)
PER_ARM_CAPS=dict(maximum_generation_forwards=24576,maximum_verification_forwards=768,
    maximum_inference_input_tokens=31457280,maximum_processed_sequences_total=384)


def counterbalanced_order(counts):
    """Alternate by sorted public task ID independently within each test-count stratum."""
    require(counts==TASK_COUNTS and all(type(v) is int for v in counts.values()),
        'same predeclared public four-task/six-test denominator required')
    result={}
    for count in (1,2):
        for position,key in enumerate(sorted(k for k,n in counts.items() if n==count)):
            result[key]=list(ARMS if position%2==0 else reversed(ARMS))
    return result


def budget_report():
    pipeline=sum(TIMING[k] for k in ('startup_seconds','maximum_training_seconds',
        'inference_reserve_seconds','reset_reserve_seconds'))
    return dict(phase_seconds=pipeline+TIMING['finalization_reserve_seconds'],
        worker_phase_seconds=pipeline,notebook_margin_seconds=120,
        parent_worker_cutoff_seconds=3000,charged_gpu_seconds_ceiling=14400,
        charged_gpu_hours_ceiling=4,paid_usd_ceiling=0,resource_qualification=False,
        overhead_policy='inventory/RNG/cache cleanup, checkpoint and replay consume the same absolute phase deadlines; no extra window',
        feasibility='arithmetic-only; tight margin and future fresh quota/independent exact-run review required')


def profile_for_plan(plan):
    require(plan.get('format')==FORMAT and plan.get('run_id')==plan.get('screen_id')==RUN_ID and
        plan.get('generation_budget_profile')==PROFILE and plan.get('forward_observer_required') is True and
        canonical(plan.get('test_counts'))==canonical(TASK_COUNTS) and
        canonical(plan.get('arm_order'))==canonical(counterbalanced_order(TASK_COUNTS)) and
        plan.get('arm_order_rule')=='sorted public task IDs; alternate within one-test and two-test task strata' and
        canonical(plan.get('per_arm_caps'))==canonical(PER_ARM_CAPS) and
        all(type(plan.get(k)) is int and plan[k]==v for k,v in {**TIMING,**CAPS}.items()) and
        type(plan.get('expected_notebook_version')) is int and plan['expected_notebook_version']==8,
        'exact inert paired identity, truth-free order and reviewed timing/caps required')
    require(all(type(plan.get(key)) is int and plan[key]==value for key,value in
        (('maximum_training_forwards',512),('maximum_training_backwards',512),('optimizer_steps',512),('per_worker_training_steps',128))),
        'paired arms must share one complete epoch per task, 512 updates total')
    return dict(profile_id=PROFILE,run_id=RUN_ID,forward_observer_required=True,**TIMING)


def paired_allocation(bound,index,start,deadline):
    value=dict(format='irisx/nvarc-paired-test-allocation-v1',binding=dict(bound),test_index=index,
        started_epoch=start,session_deadline_epoch=deadline,generation_seconds=120,total_seconds=150,
        verification_reserve_seconds=30)
    allocation_deadlines(value,bound,index)
    return value


def capture_rng(engine):
    """Capture existing RNG streams; this performs no model/warmup call."""
    numpy=engine.np.random.get_state()
    return dict(python=random.getstate(),numpy=(numpy[0],numpy[1].copy(),*numpy[2:]),
        torch_cpu=engine.torch.get_rng_state().clone(),
        torch_cuda=[state.clone() for state in engine.torch.cuda.get_rng_state_all()])


def restore_rng(engine,state):
    random.setstate(state['python']);engine.np.random.set_state(state['numpy'])
    engine.torch.set_rng_state(state['torch_cpu']);engine.torch.cuda.set_rng_state_all(state['torch_cuda'])


def rng_digests(state):
    numpy=state['numpy']
    return dict(python=digest(state['python']),numpy=digest([numpy[0],numpy[1].tolist(),*numpy[2:]]),
        torch_cpu=digest(state['torch_cpu'].tolist()),
        torch_cuda=digest([value.tolist() for value in state['torch_cuda']]))


def model_metadata(model):
    """Observe every parameter/buffer without full backbone copies or forwards."""
    def rows(items):
        return [dict(name=name,identity=id(value),storage=value.data_ptr(),dtype=str(value.dtype),
            device=str(value.device),shape=list(value.shape),version=value._version,requires_grad=value.requires_grad)
            for name,value in items]
    return dict(model_identity=id(model),training=model.training,parameters=rows(model.named_parameters()),
        buffers=rows(model.named_buffers()),rotary_caches=rotary_metadata(model))


def rotary_metadata(model):
    """Inspect pinned ordinary RoPE caches, including inference-mode tensors.

    These are ordinary attributes rather than named buffers. No tensor version
    access, readback, allocation or warmup occurs here.
    """
    def tensor(value):
        return dict(identity=id(value),storage=value.data_ptr(),device=str(value.device),
            dtype=str(value.dtype),shape=list(value.shape))
    result=[]
    for name,module in model.named_modules():
        if not (hasattr(module,'multi_gpu_cos_cached') or hasattr(module,'multi_gpu_sin_cached')):continue
        kind=type(module)
        require((kind.__module__,kind.__name__)==('unsloth.models.llama','LlamaRotaryEmbedding'),
            'only the observed pinned native rotary cache class is supported; unknown transition fails closed')
        result.append(dict(name=name,class_module=kind.__module__,class_name=kind.__name__,
            current_rope_size=module.current_rope_size,dim=module.dim,max_position_embeddings=module.max_position_embeddings,
            base=module.base,multi_gpu_cos_cached=[tensor(value) for value in module.multi_gpu_cos_cached],
            multi_gpu_sin_cached=[tensor(value) for value in module.multi_gpu_sin_cached],
            cos_cached=tensor(module.cos_cached),sin_cached=tensor(module.sin_cached)))
    require(result,'actual pinned rotary cache observations are required before paired inference')
    return result


def verify_rng_digests(value):
    require(type(value) is dict and set(value)=={'python','numpy','torch_cpu','torch_cuda'} and
        all(type(item) is str and re.fullmatch('sha256:[0-9a-f]{64}',item) for item in value.values()),
        'complete canonical Python/NumPy/torch CPU/CUDA RNG fingerprints required')


def verify_model_metadata(value,plan):
    require(type(value) is dict and set(value)=={'model_identity','training','parameters','buffers','rotary_caches'} and
        type(value['model_identity']) is int and value['model_identity']>0 and value['training'] is False and
        type(value['parameters']) is list and value['parameters'] and type(value['buffers']) is list,
        'complete retained inference model metadata required')
    for kind in ('parameters','buffers'):
        names=[]
        for row in value[kind]:
            require(type(row) is dict and set(row)=={'name','identity','storage','dtype','device','shape','version','requires_grad'} and
                type(row['name']) is str and bool(row['name']) and type(row['requires_grad']) is bool and
                all(type(row[k]) is int for k in ('identity','storage','version')) and row['identity']>0 and
                row['storage']>=0 and row['version']>=0 and type(row['dtype']) is str and
                re.fullmatch('torch\\.[a-z0-9]+',row['dtype']) and row['device'] in ('cpu','cuda:0') and
                type(row['shape']) is list and all(type(n) is int and n>=0 for n in row['shape']) and
                (kind=='buffers' or math.prod(row['shape'])>0 and row['storage']>0),
                'strict retained parameter/buffer name/storage/version/type/shape metadata required')
            names.append(row['name'])
        require(len(names)==len(set(names)),'unique retained parameter/buffer names required')
    actual={row['name']:row for row in value['parameters']}
    require(all(name in actual and actual[name]['requires_grad'] is True and actual[name]['shape']==shape
        for name,shape in plan['source_inferred_trainable_layout'].items()),
        'all original trainable tensor names/shapes must be covered by full model metadata')
    rotaries=value['rotary_caches'];require(type(rotaries) is list and rotaries,'nonempty observed rotary caches required')
    names=[]
    for row in rotaries:
        require(type(row) is dict and set(row)=={'name','class_module','class_name','current_rope_size','dim',
            'max_position_embeddings','base','multi_gpu_cos_cached','multi_gpu_sin_cached','cos_cached','sin_cached'} and
            type(row['name']) is str and row['name'] and row['class_module']=='unsloth.models.llama' and
            row['class_name']=='LlamaRotaryEmbedding' and
            all(type(row[k]) is int for k in ('current_rope_size','dim','max_position_embeddings')) and
            row['current_rope_size']>=8192 and row['max_position_embeddings']>=8192 and row['dim']>0 and
            type(row['base']) in (int,float) and math.isfinite(row['base']) and row['base']>0 and
            type(row['multi_gpu_cos_cached']) is type(row['multi_gpu_sin_cached']) is list and
            len(row['multi_gpu_cos_cached'])==len(row['multi_gpu_sin_cached'])==1,
            'pinned single-device rotary class/capacity/layout required')
        for tensor in [*row['multi_gpu_cos_cached'],*row['multi_gpu_sin_cached'],row['cos_cached'],row['sin_cached']]:
            require(type(tensor) is dict and set(tensor)=={'identity','storage','device','dtype','shape'} and
                type(tensor['identity']) is type(tensor['storage']) is int and tensor['identity']>0 and tensor['storage']>0 and
                tensor['device'] in ('cuda:0','cpu') and type(tensor['dtype']) is str and
                re.fullmatch('torch\\.[a-z0-9]+',tensor['dtype']) and type(tensor['shape']) is list and
                all(type(n) is int and n>0 for n in tensor['shape']), 'strict ordinary rotary tensor metadata required')
        require(all(tensor['shape']==[row['current_rope_size'],row['dim']] and tensor['device']=='cuda:0'
            for tensor in [*row['multi_gpu_cos_cached'],*row['multi_gpu_sin_cached']]) and
            row['cos_cached']['shape']==row['sin_cached']['shape']==[1],
            'actual native rotary capacity/dummy cache tensor shapes differ')
        names.append(row['name'])
    require(len(names)==len(set(names)),'unique observed rotary module names required')


def _read(path):
    path=Path(path);require(not path.is_symlink() and path.stat().st_size<=8*1024**2,
        'bounded regular paired evidence required')
    value=parse_json(path.read_bytes());reject_truth(value);return value


def solve_pair(engine,root,plan,rank,deadline,telemetry,*,observe_forwards=False):
    profile_for_plan(plan);require(observe_forwards,'paired arms require forward observations')
    root=Path(root);directory=root/'workers'/str(rank);key=plan['task_order'][rank]
    bound=native_epoch.binding(plan,rank);trained=engine.inventory();state=capture_rng(engine)
    require(trained==_read(directory/'trained-inventory.json'), 'retained trained state differs before paired entry')
    original=rng_digests(state);arms={};receipts={}
    record=dict(format='irisx/paired-task-inference-v1',binding=bound,arm_order=plan['arm_order'][key],
        trained_inventory_digest=digest(trained),rng_start_digests=original,rng_restored_after_pair=False,
        arms=arms,arm_receipts=receipts,errors=[],paired_state_verified=False,
        finished_epoch=None,clock_overrun=None,
        model_forwards_for_isolation=0,correctness_scored=False,promotion=False)
    def checkpoint():write(directory/'answer-checkpoint.json',record)
    checkpoint()
    try:
        for ordinal,schedule in enumerate(record['arm_order']):
            require(time.time()<deadline,'paired absolute inference/reset cutoff exhausted')
            arm=directory/'arms'/schedule;arm.mkdir(parents=True,exist_ok=False)
            started=time.monotonic()
            # The retained model is the trained state. Hash every saved tensor;
            # never retrain or silently restore changed trained tensors.
            before=engine.inventory();require(before==trained,'trained state changed before schedule arm')
            before_metadata=model_metadata(engine.model)
            verify_model_metadata(before_metadata,plan)
            restore_rng(engine,state);before_rng=rng_digests(capture_rng(engine))
            require(before_rng==original,'all RNG streams must match before each arm')
            write(arm/'trained-before-inventory.json',before)
            write(arm/'model-before-metadata.json',before_metadata)
            receipt=dict(schedule=schedule,ordinal=ordinal,started_monotonic=started,started_epoch=time.time(),
                finished_monotonic=None,finished_epoch=None,clock_overrun=None,
                before_inventory_digest=digest(before),after_inventory_digest=None,
                rng_before_digests=before_rng,rng_after_digests=None,model_identity_preserved=False,
                model_before_metadata_digest=digest(before_metadata),model_after_metadata_digest=None,
                no_extra_model_forwards=True,fresh_adapter=False,fresh_caches=False,
                absolute_inference_cutoff_epoch=deadline,status='active',errors=[])
            receipts[schedule]=receipt;write(arm/'arm-receipt.json',receipt);checkpoint()
            model=engine.model
            try:
                # New AnswerModel + observer + per-arm counters/caches. DFS cache
                # objects remain call-local and no second NativeEngine is made.
                arm_telemetry=PhaseTelemetry()
                arms[schedule]=evidence.solve_task(engine,root,plan,rank,deadline,arm_telemetry,
                    observe_forwards=True,schedule=schedule,directory=arm)
                after=engine.inventory();write(arm/'trained-after-inventory.json',after)
                after_metadata=model_metadata(engine.model);write(arm/'model-after-metadata.json',after_metadata)
                entry=_read(arm/'adapter-entry.json')
                fresh=canonical(entry)==canonical(dict(constructor='tools.nvarc_e10_answer_evidence.AnswerModel',
                    reserved={'control':0,'generation':0,'verification':0},completed={'control':0,'generation':0,'verification':0},
                    input_tokens=0,observed_verifications=0,verification_rows=None,active=None,observer_rows=0))
                ledger=evidence.read_events(arm/'inference-events.jsonl',arms[schedule]['binding']);first={}
                for row in ledger:
                    if row['event']=='forward_reserved' and row['phase']=='generation':first.setdefault(row['test_index'],row)
                receipt.update(after_inventory_digest=digest(after),rng_after_digests=rng_digests(capture_rng(engine)),
                    model_identity_preserved=engine.model is model,model_after_metadata_digest=digest(after_metadata),
                    fresh_adapter=fresh,fresh_caches=all(row['cached'] is False and row['position_start']==0 for row in first.values()))
                require(after==trained and before_metadata==after_metadata and receipt['model_identity_preserved'] and
                    receipt['fresh_adapter'] and receipt['fresh_caches'],
                    'schedule arm mutated retained trained state/model identity')
                gc.collect()
                receipt['finished_monotonic']=time.monotonic()
                require(time.time()<=deadline,'arm evidence/cleanup exceeded the fixed inference cutoff')
                receipt['status']='complete'
            except BaseException as error:
                receipt['status']='failed';receipt['errors'].append(diagnostic(error,'paired-arm'));raise
            finally:
                receipt['finished_monotonic']=time.monotonic()
                receipt['finished_epoch']=time.time();receipt['clock_overrun']=receipt['finished_epoch']>deadline
                if receipt['clock_overrun']:
                    receipt['status']='failed'
                    receipt['errors'].append({'phase':'paired-arm-finalization','type':'InferenceDeadline',
                        'message':'arm evidence/cleanup exceeded fixed inference cutoff'})
                write(arm/'arm-receipt.json',receipt);checkpoint()
        record['paired_state_verified']=len(arms)==len(receipts)==2 and all(r['status']=='complete' for r in receipts.values())
    except BaseException as error:
        record['errors'].append(diagnostic(error,'paired-schedule'));raise
    finally:
        primary=sys.exception()
        restore_rng(engine,state)
        record['rng_restored_after_pair']=rng_digests(capture_rng(engine))==original
        checkpoint()
        record['finished_epoch']=time.time();record['clock_overrun']=record['finished_epoch']>deadline
        checkpoint()
        if record['clock_overrun'] or time.time()>deadline:
            record['paired_state_verified']=False
            record['finished_epoch']=time.time();record['clock_overrun']=True
            record['errors'].append({'phase':'paired-final-rng-checkpoint','type':'InferenceDeadline',
                'message':'paired RNG restoration/checkpoint exceeded fixed inference cutoff'})
            checkpoint()
            if primary is None:raise RuntimeError('paired cleanup exceeded fixed inference cutoff')
            primary.add_note('paired cleanup also exceeded fixed inference cutoff')
    return record


def verify_pair(root,plan,rank):
    profile_for_plan(plan);root=Path(root);directory=root/'workers'/str(rank)
    record=_read(directory/'answer-checkpoint.json');key=plan['task_order'][rank]
    expected={'format','binding','arm_order','trained_inventory_digest','rng_start_digests',
        'rng_restored_after_pair','arms','arm_receipts','errors','paired_state_verified',
        'finished_epoch','clock_overrun',
        'model_forwards_for_isolation','correctness_scored','promotion'}
    require(set(record)==expected and record['format']=='irisx/paired-task-inference-v1' and
        record['binding']==native_epoch.binding(plan,rank) and record['arm_order']==plan['arm_order'][key] and
        record['errors']==[] and record['paired_state_verified'] is record['rng_restored_after_pair'] is True and
        type(record['model_forwards_for_isolation']) is int and record['model_forwards_for_isolation']==0 and
        record['correctness_scored'] is record['promotion'] is False and
        set(record['arms'])==set(record['arm_receipts'])==set(ARMS), 'complete bound paired task required')
    trained=_read(directory/'trained-inventory.json');require(record['trained_inventory_digest']==digest(trained),
        'paired trained-state binding differs')
    verify_rng_digests(record['rng_start_digests'])
    launch=_read(directory/'launch-reservation.json')
    require(launch['binding']==native_epoch.binding(plan,rank) and type(launch['deadline_epoch']) in (int,float) and
        math.isfinite(launch['deadline_epoch']),'exact launch deadline receipt required')
    cutoff=launch['deadline_epoch']-plan['reset_reserve_seconds']
    require(type(record['finished_epoch']) in (int,float) and math.isfinite(record['finished_epoch']) and
        record['clock_overrun'] is (record['finished_epoch']>cutoff) is False,
        'paired final RNG/checkpoint must finish inside launch-owned inference cutoff')
    sources={};previous=None;retained_metadata=None
    for ordinal,schedule in enumerate(record['arm_order']):
        arm=directory/'arms'/schedule;receipt=_read(arm/'arm-receipt.json')
        require(receipt==record['arm_receipts'][schedule] and set(receipt)=={
            'schedule','ordinal','started_monotonic','finished_monotonic','started_epoch','finished_epoch','clock_overrun','before_inventory_digest',
            'after_inventory_digest','rng_before_digests','rng_after_digests','model_identity_preserved',
            'model_before_metadata_digest','model_after_metadata_digest','errors',
            'no_extra_model_forwards','fresh_adapter','fresh_caches','absolute_inference_cutoff_epoch','status'} and
            receipt['schedule']==schedule and type(receipt['ordinal']) is int and receipt['ordinal']==ordinal and
            receipt['status']=='complete' and receipt['model_identity_preserved'] is receipt['no_extra_model_forwards'] is
            receipt['fresh_adapter'] is receipt['fresh_caches'] is True and
            receipt['rng_before_digests']==record['rng_start_digests'] and
            receipt['errors']==[] and receipt['absolute_inference_cutoff_epoch']==cutoff and
            all(type(receipt[k]) in (int,float) and math.isfinite(receipt[k]) for k in
                ('started_monotonic','finished_monotonic','started_epoch','finished_epoch','absolute_inference_cutoff_epoch')) and
            receipt['finished_epoch']>=receipt['started_epoch'] and receipt['clock_overrun'] is
                (receipt['finished_epoch']>cutoff) is False and record['finished_epoch']>=receipt['finished_epoch'] and
            receipt['finished_monotonic']>=receipt['started_monotonic'] and
            (previous is None or receipt['started_monotonic']>=previous), 'ordered paired arm/RNG/isolation receipt differs')
        previous=receipt['finished_monotonic']
        verify_rng_digests(receipt['rng_before_digests']);verify_rng_digests(receipt['rng_after_digests'])
        require(_read(arm/'trained-before-inventory.json')==_read(arm/'trained-after-inventory.json')==trained and
            receipt['before_inventory_digest']==receipt['after_inventory_digest']==digest(trained),
            'all 506 retained trained tensor hashes must match across both arms')
        before_metadata=_read(arm/'model-before-metadata.json');after_metadata=_read(arm/'model-after-metadata.json')
        verify_model_metadata(before_metadata,plan);verify_model_metadata(after_metadata,plan)
        require(before_metadata==after_metadata and
            receipt['model_before_metadata_digest']==receipt['model_after_metadata_digest']==digest(before_metadata) and
            (retained_metadata is None or retained_metadata==before_metadata),
            'all retained model parameter/buffer metadata must remain unchanged')
        retained_metadata=before_metadata
        require(canonical(_read(arm/'adapter-entry.json'))==canonical(dict(constructor='tools.nvarc_e10_answer_evidence.AnswerModel',
            reserved={'control':0,'generation':0,'verification':0},completed={'control':0,'generation':0,'verification':0},
            input_tokens=0,observed_verifications=0,verification_rows=None,active=None,observer_rows=0)),
            'fresh adapter and empty observed/cache/counter entry state required')
        allocations=_read(arm/'test-allocations.json')
        require(all(allocation.get('session_deadline_epoch')==cutoff for allocation in allocations.values()),
            'caller allocations must share the launch-owned inference/reset cutoff')
        require(record['arms'][schedule]==evidence.verify_task(root,plan,rank,schedule=schedule,
            directory=arm,admitted_allocations=allocations),'paired arm checkpoint differs')
        events=evidence.read_events(arm/'inference-events.jsonl',record['arms'][schedule]['binding'])
        sources[schedule]={e['test_index']:{k:e[k] for k in ('base_key','source_views','source_input_digests')}
            for e in events if e['event']=='test_started'}
        for index in sources[schedule]:
            first=next((e for e in events if e['event']=='forward_reserved' and e['phase']=='generation' and e['test_index']==index),None)
            require(first is None or first['cached'] is False and first['position_start']==0,
                'each arm/test must start with an uncached source prefill')
    shared=set(sources[ARMS[0]])&set(sources[ARMS[1]])
    require(all(sources[ARMS[0]][i]==sources[ARMS[1]][i] for i in shared),
        'paired formatter/base-key/augmentation/input digests differ')
    return record


def verify_worker_result(root,plan,rank,uuid):
    return native_epoch.verify_worker_result(root,plan,rank,uuid,verify_inference=verify_pair)


def seal_outputs(root,plan,results,errors):
    """One atomic envelope, separate per-arm answers/audits and missing slots."""
    values={};coverage={};timings={};audits={};recovery_errors=[]
    for schedule in ARMS:
        answers={};audit=[];pools={};stamps={}
        for rank,key in enumerate(plan['task_order']):
            result=results.get(str(rank));pair=None if result is None else result['inference']
            arm=None if pair is None else pair['arms'].get(schedule)
            recovered=False
            if arm is None:
                directory=Path(root)/'workers'/str(rank)/'arms'/schedule
                if (directory/'test-allocations.json').is_file():
                    try:
                        arm=evidence.recover_completed_tests(root,plan,rank,schedule=schedule,
                            directory=directory,admitted_allocations=_read(directory/'test-allocations.json'))
                        recovered=arm is not None
                    except BaseException as error:
                        recovery_errors.append(dict(rank=rank,schedule=schedule,**diagnostic(error,'paired-prefix-recovery')))
            answers[key]=[];pools[key]=[];stamps[key]=[]
            for index in range(plan['test_counts'][key]):
                test=None if arm is None else arm['tests'][index];attempts=[] if test is None else test.get('attempts',[])
                answers[key].append({'attempt_1':attempts[0] if attempts else None,
                    'attempt_2':attempts[1] if len(attempts)>1 else None})
                pools[key].append([] if test is None else test.get('ranked_grids',[]))
                audit.append(dict(task_id=key,test_index=index,actual_candidates=len(attempts),
                    missing_attempts=2-len(attempts),output_qualified=bool(result and test and test.get('output_qualified')),
                    status='no_verified_worker' if test is None else test['status'],paired_state_verified=pair is not None,
                    started=bool(test and test.get('started_epoch') is not None),
                    provenance='unqualified-committed-prefix' if recovered else 'verified-paired-worker' if pair else 'unavailable',
                    test_digest=None if test is None else digest(test)))
                stamps[key].append(None if test is None else {k:test.get(k) for k in
                    ('started_epoch','finished_epoch','deadline_epoch','clock_overrun','coverage','termination_reason','telemetry')})
        values[schedule+'-answers.json']=dict(format='irisx/exposed-calibration-answers-v1',tasks=answers,official_submission_ready=False)
        values[schedule+'-audit.json']=audit;values[schedule+'-candidate-pools.json']=pools
        coverage[schedule]=dict(test_cases=6,actual_attempts=sum(r['actual_candidates'] for r in audit),
            missing_attempts=sum(r['missing_attempts'] for r in audit),qualified_test_cases=sum(r['output_qualified'] for r in audit),
            output_qualified=not errors and len(results)==4 and all(r['output_qualified'] for r in audit))
        timings[schedule]=stamps;audits[schedule]=audit
    slots=[]
    for left,right in zip(audits[ARMS[0]],audits[ARMS[1]]):
        require((left['task_id'],left['test_index'])==(right['task_id'],right['test_index']),'same fixed paired denominator required')
        both=left['paired_state_verified'] and right['paired_state_verified'] and left['started'] and right['started']
        slots.append(dict(task_id=left['task_id'],test_index=left['test_index'],arm_order=plan['arm_order'][left['task_id']],
            arm_statuses={ARMS[0]:left['status'],ARMS[1]:right['status']},
            arm_started={ARMS[0]:left['started'],ARMS[1]:right['started']},
            matching_public_inputs_verified=both,resource_comparison_eligible=both,
            both_outputs_qualified=left['output_qualified'] and right['output_qualified']))
    observed_updates=sum(result['training']['completed_updates'] for result in results.values())
    summary=dict(format='irisx/paired-schedule-output-v1',run_id=plan['run_id'],plan_digest=digest(plan),
        arm_order=plan['arm_order'],per_arm=coverage,planned_test_executions=12,planned_training_updates=512,
        verified_completed_training_updates=observed_updates,
        actual_training_updates_all_workers=observed_updates if len(results)==4 else None,
        recovered_or_verified_started_tests=sum(row['started'] for audit in audits.values() for row in audit),
        paired_slots=slots,paired_workers_verified=len(results),unverified_workers=4-len(results),
        errors=errors,recovery_errors=recovery_errors,correctness_scored=False,promotion=False,
        official_submission_ready=False,quality_comparison_qualified=False,
        missing_slot_semantics='no independently verified sealed attempt; interrupted arm evidence remains archived')
    values.update({'paired-summary.json':summary,'paired-task-timings.json':timings})
    for value in values.values():reject_truth(value)
    store=GenerationStore(root,'paired',{'run_id':plan['run_id'],'plan_digest':digest(plan),
        'challenges_digest':plan['challenges_digest']})
    require(not (Path(root)/'output-commit.json').exists(),'one immutable paired output generation only')
    manifest=store.publish(values,evidence_qualified=not errors and len(results)==4 and
        all(item['output_qualified'] for item in coverage.values()));store.read()
    return dict(manifest_digest=digest(manifest),**summary)


def worker(root,dependency,model,rank,deadline,parent_pid,dependency_receipt_sha256=None):
    from tools.stage_nvarc_e10_paired_schedule import verify_runtime
    plan=verify_runtime(root,require_approved=True)
    return native_epoch.run_worker(root,dependency,model,rank,deadline,parent_pid,
        dependency_receipt_sha256,plan,solve=solve_pair)


def execute(root,dependency,started):
    from tools import stage_nvarc_e10_paired_schedule as api
    return native_epoch.execute(root,dependency,started,runtime_api=api)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','dependency','model'):parser.add_argument('--'+name,type=Path,required=name!='model')
    parser.add_argument('--rank',type=int);parser.add_argument('--deadline',type=float);parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--dependency-receipt-sha256');parser.add_argument('--started',type=float)
    parser.add_argument('--owner-pid',type=int);parser.add_argument('--bootstrap',action='store_true');args=parser.parse_args()
    from tools.stage_nvarc_e10_paired_schedule import verify_runtime
    # No admission can be inherited. Reject before NativeEngine or any native
    # dependency import, runtime directory creation or producer launch.
    verify_runtime(args.root,require_approved=True)
    require(os.environ.get('PYTHONHASHSEED')=='0' and sys.flags.hash_randomization==0,'fresh hashseed-zero process required')
    if args.rank is not None:return worker(args.root,args.dependency,args.model,args.rank,args.deadline,args.parent_pid,args.dependency_receipt_sha256)
    install_owner_guard(args.owner_pid,signal.SIGTERM)
    return execute(args.root,args.dependency,args.started)


if __name__=='__main__':raise SystemExit(main())

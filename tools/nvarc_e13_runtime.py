"""Native E13 paired search120/search240 from one full native TTT128 state.

The task-local model is trained once. Both arms start at the same retained
trained tensors and post-training RNG, with separate adapters/caches/telemetry.
Only the interleaved generation window changes; no quality or cost claim follows.
"""
from __future__ import annotations
from contextlib import contextmanager
import copy
import functools
import gc
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

from tools.nvarc_native_multitask import Events,canonical,digest,require,write,public_training_material,training_deadline
from tools.nvarc_native_submission import reject_truth
from tools.nvarc_output_lifecycle import diagnostic,terminal_attempt
from tools.nvarc_e13_output_lifecycle import GenerationStore
from tools.nvarc_public_eval import PhaseTelemetry,install_owner_guard
from tools.nvarc_e10_paired_schedule import capture_rng,restore_rng,model_metadata,_read
from tools.nvarc_e11_paired_floor import verify_model_metadata
from tools import nvarc_e10_end_to_end as native_epoch
from tools import nvarc_e10_ttt_probe as native_training
from tools.nvarc_native_solve_runtime import discard_optimizer_state,reset_control,compare_vectors
from tools.nvarc_dependency_readproof import require_worker_receipt,verify_before_prepare,RECEIPT_FILE
from tools.nvarc_resource_attachment import verify_mount
from tools.nvarc_public_eval_parent import prepare,stop_process
from tools.nvarc_public_eval_runtime import NativeEngine
from tools.nvarc_native_ttt_schedule import native_schedule,SOURCES,FUNCTIONS,ulp_distance
from tools.nvarc_e10_probe import control_adapter,verify_observations,publish_terminal
from tools.nvarc_e12_training import PrefixBudget,rng_observation,reset_observation,PROFILES
from tools import nvarc_e12_prefix_contract as prefix

FORMAT='irisx/stage4-e13-search-budget-v1'
RUN_ID='stage4-e13-search-budget-20261008-001'
PROFILE='native-paired-search-budget-v12'
BUDGET_PROFILE='conservative-60min-inert'
ARMS=('search120','search240')
TASK_COUNTS={'195c6913':2,'aa4ec2a5':1,'a47bf94d':1,'a25697e4':2}
TIMING=dict(generation_seconds=240,verification_reserve_seconds=30,per_test_seconds=270,
    startup_seconds=900,maximum_training_seconds=1200,inference_reserve_seconds=840,
    reset_reserve_seconds=180,finalization_reserve_seconds=300,maximum_worker_seconds=3120,
    maximum_notebook_wall_seconds=3600)
CAPS=dict(maximum_generation_forwards=49152,maximum_verification_forwards=1536,
    maximum_inference_input_tokens=62914560,maximum_processed_sequences_total=768)
PER_ARM_CAPS=dict(maximum_generation_forwards=24576,maximum_verification_forwards=768,
    maximum_inference_input_tokens=31457280,maximum_processed_sequences_total=384)
MODEL_LAYOUT=dict(parameter_count=905,buffer_count=0,
    digest='sha256:06a1ed5e10ce2c741cb661ba3e883952e3fbce3e0931ce151485b9ac4d31a479')
PROCESS_POLICY=dict(term_seconds=3290,kill_seconds=3299.8,stop_seconds=3300,final_seconds=3600,
    worker_cleanup_deadline_seconds=3299.8,requires_owned_group_absence=True)
ALLOCATION='irisx/e13-search-budget-test-allocation-v1'
INFERENCE_TELEMETRY_FORMAT='irisx/e13-arm-inference-telemetry-v1'
INFERENCE_TELEMETRY_AGGREGATION=(
    'independent inference collectors per arm; overlap worker elapsed/unscoped time; '
    'do not add collector elapsed times or infer allocated-GPU cost')


def arm_contract(arm):
    require(arm in ARMS,'exact E13 arm required')
    seconds=120 if arm=='search120' else 240
    return dict(experiment='paired-search-budget-v12',arm_id=arm,training_updates=128,
        generation_seconds=seconds,per_test_seconds=seconds+30,verification_reserve_seconds=30,
        schedule='interleaved',dfs_probability_floor=.2,dfs_max_score=-math.log(.2))


def counterbalanced_order(counts):
    require(canonical(counts)==canonical(TASK_COUNTS),'same four tasks/six tests required')
    return {key:list(ARMS if position%2==0 else reversed(ARMS)) for count in (1,2)
        for position,key in enumerate(sorted(k for k,n in counts.items() if n==count))}


def budget_report():
    return dict(budget_profile=BUDGET_PROFILE,phase_seconds=3420,worker_phase_seconds=2220,
        notebook_margin_seconds=180,parent_worker_cutoff_seconds=3300,
        charged_gpu_seconds_ceiling=14400,charged_gpu_hours_ceiling=4,paid_usd_ceiling=0,
        resource_qualification=False,status='INERT_NOT_ADMITTED',
        feasibility='planning only; fresh quota and exact package review required; no 45-minute shrink',
        total_cost_reduction=None,full_screen_feasibility_established=False)


def profile_for_plan(plan):
    from tools.nvarc_e13_admission import validate_plan
    validate_plan(plan)
    require(plan.get('format')==FORMAT and plan.get('run_id')==plan.get('screen_id')==RUN_ID and
        plan.get('generation_budget_profile')==PROFILE and plan.get('resource_budget_profile') in (BUDGET_PROFILE,'bounded-60min-run') and
        plan.get('forward_observer_required') is True and
        canonical(plan.get('test_counts'))==canonical(TASK_COUNTS) and plan.get('task_order')==list(TASK_COUNTS) and
        canonical(plan.get('arm_order'))==canonical(counterbalanced_order(TASK_COUNTS)) and
        canonical(plan.get('arm_contracts'))==canonical({a:arm_contract(a) for a in ARMS}) and
        canonical(plan.get('per_arm_caps'))==canonical(PER_ARM_CAPS) and
        canonical(plan.get('retained_model_layout'))==canonical(MODEL_LAYOUT) and
        canonical(plan.get('e13_process_policy'))==canonical(PROCESS_POLICY) and
        plan.get('verification_schedule')=='interleaved' and plan.get('verification_schedules')==['interleaved'] and
        all(type(plan.get(k)) is int and plan[k]==v for k,v in {**TIMING,**CAPS,
            'cleanup_reserve_seconds':310,'maximum_training_forwards':512,'maximum_training_backwards':512,
            'optimizer_steps':512,'per_worker_training_steps':128,'maximum_control_forwards':28,
            'per_worker_forwards':7,'expected_notebook_version':12,'expected_previous_version':11}.items()),
        'closed E13 native paired-search 60-minute profile required')
    return dict(profile_id=PROFILE,run_id=RUN_ID,forward_observer_required=True,**TIMING)


def validate_binding(bound,arm_id=None):
    require(type(bound) is dict,'exact E13 binding object required')
    arm=bound.get('arm_id') if arm_id is None else arm_id
    expected=arm_contract(arm)
    require(bound.get('run_id')==RUN_ID and all(type(bound.get(k)) is type(v) and bound[k]==v
        for k,v in expected.items()),'exact E13 search arm and unchanged p02 binding required')
    return expected


def allocation_deadlines(value,bound,index):
    contract=validate_binding(bound);seconds=contract['generation_seconds'];total=contract['per_test_seconds']
    require(type(value) is dict and set(value)=={'format','binding','test_index','started_epoch',
        'session_deadline_epoch','generation_seconds','total_seconds','verification_reserve_seconds'} and
        value['format']==ALLOCATION and type(value['binding']) is dict and set(value['binding'])==set(bound) and
        all(type(value['binding'][k]) is type(v) and value['binding'][k]==v for k,v in bound.items()) and
        type(value['test_index']) is int and value['test_index']==index and
        all(type(value[k]) is int and value[k]==v for k,v in
            (('generation_seconds',seconds),('total_seconds',total),('verification_reserve_seconds',30))) and
        all(type(value[k]) in (int,float) and math.isfinite(value[k]) for k in ('started_epoch','session_deadline_epoch')) and
        value['started_epoch']+total<=value['session_deadline_epoch'],
        'full E13 arm-bound 120/150 or 240/270-second test allocation required')
    return value['started_epoch']+seconds,value['started_epoch']+total


def paired_allocation(bound,index,start,deadline):
    contract=validate_binding(bound)
    value=dict(format=ALLOCATION,binding=dict(bound),test_index=index,started_epoch=start,
        session_deadline_epoch=deadline,generation_seconds=contract['generation_seconds'],
        total_seconds=contract['per_test_seconds'],verification_reserve_seconds=30)
    allocation_deadlines(value,bound,index);return value


def binding(plan,rank):return native_epoch.binding(plan,rank)


def training_sources(plan,key):
    return dict(challenge_digest=plan['challenges_digest'],model_digest=plan['model_material_digest'],
        dependency_digest=plan['dependency_readproof_digest'],configuration_digest=digest(plan['original_training_arguments']),
        inference_contract_digest=digest(dict(schedule='interleaved',dfs_probability_floor=.2,
            arms={a:arm_contract(a) for a in ARMS},per_test_limits={'generation':4096,'verification':128,'input_tokens':5242880})),
        native_sampler_digest='sha256:'+'0'*64)


def unchanged_model_layout(before,after,plan):
    # Training is intentional; require complete 905 metadata and frozen tensor
    # versions/storage unchanged. All 506 adapted bytes are separately hashed.
    for value in (before,after):
        projected=copy.deepcopy(value);projected['training']=False
        verify_model_metadata(projected,plan)
    require(before['model_identity']==after['model_identity'] and before['buffers']==after['buffers'] and
        before['rotary_caches']==after['rotary_caches'],'resident model and complete cache/buffer identity required')
    for a,b in zip(before['parameters'],after['parameters']):
        require({k:v for k,v in a.items() if k!='version'}=={k:v for k,v in b.items() if k!='version'} and
            (a['requires_grad'] or a==b),'frozen model parameter metadata mutated during adaptation')


def optimizer_disposed(engine,trainer,budget):
    return (trainer is None or trainer.optimizer is trainer.lr_scheduler is None and
        not trainer.accelerator._optimizers and not trainer.accelerator._schedulers and
        (budget is None or budget.optimizer is None)) and all(p.grad is None for p in engine.model.parameters())


def training_phase_deadline(plan,key,deadline,now_epoch):
    profile_for_plan(plan)
    require(key in TASK_COUNTS and all(type(v) in (int,float) and math.isfinite(v)
        for v in (deadline,now_epoch)),'finite E13 training reservation required')
    # Full paired inference plus one terminal baseline reset remain reserved.
    cutoff=min(now_epoch+plan['maximum_training_seconds'],
        deadline-plan['reset_reserve_seconds']-TASK_COUNTS[key]*420)
    require(cutoff>now_epoch,'training or full future inference/reset reserve exhausted')
    return cutoff


def arm_inference_deadline(plan,key,ordinal,deadline):
    profile_for_plan(plan)
    require(key in TASK_COUNTS and type(ordinal) is int and ordinal in (0,1) and
        type(deadline) in (int,float) and math.isfinite(deadline),'finite E13 arm reservation required')
    future=plan['arm_order'][key][ordinal+1:]
    return deadline-plan['reset_reserve_seconds']-TASK_COUNTS[key]*sum(arm_contract(a)['per_test_seconds'] for a in future)


@contextmanager
def arm_inference_telemetry(snapshots,arm_id):
    """Keep test indexes local to one arm and freeze its final host observation."""
    require(arm_id in ARMS and arm_id not in snapshots,'one inference telemetry collector per E13 arm required')
    snapshots[arm_id]=None
    collector=PhaseTelemetry()
    try:
        yield collector
    finally:
        # PhaseTelemetry snapshots include live test dictionaries. Freeze them
        # here so later work cannot mutate an already completed arm's evidence.
        snapshots[arm_id]=copy.deepcopy(collector.snapshot())


def inference_telemetry_result(snapshots):
    return dict(format=INFERENCE_TELEMETRY_FORMAT,aggregation=INFERENCE_TELEMETRY_AGGREGATION,
        arms=copy.deepcopy(snapshots))


def verify_inference_telemetry(value,answers):
    require(type(value) is dict and set(value)=={'format','aggregation','arms'} and
        value['format']==INFERENCE_TELEMETRY_FORMAT and value['aggregation']==INFERENCE_TELEMETRY_AGGREGATION and
        type(value['arms']) is dict and set(value['arms'])==set(answers)==set(ARMS),
        'closed separate E13 arm inference telemetry required')
    template=PhaseTelemetry().snapshot()
    variable={'elapsed_host_seconds','inclusive_host_seconds','exclusive_host_seconds','unscoped_host_seconds','tests','events'}
    for arm_id,tests in answers.items():
        observed=value['arms'][arm_id]
        require(type(observed) is dict and set(observed)==set(template) and
            all(canonical(observed[k])==canonical(template[k]) for k in set(template)-variable),
            'closed original host telemetry shape and semantics required')
        # The native solver catches these cooperative inference guards and
        # returns a checkpoint. PhaseTelemetry still retains the scoped event;
        # a normal bounded stop must not be turned into a worker failure.
        eligible=sum(t.get('termination_reason') in {'forward_limit','input_token_limit','inference_deadline'}
            for t in tests['tests'])
        require(type(observed['events']) is list and len(observed['events'])<=eligible and
            all(type(event) is dict and set(event)=={'event','phase','type'} and
                event['event']=='phase_exception' and event['type']=='InferenceLimitReached' and
                event['phase'] in {'generation','verification'} for event in observed['events']),
            'only retained native cooperative inference guard events permitted')
        inclusive=observed['inclusive_host_seconds'];exclusive=observed['exclusive_host_seconds']
        require(type(inclusive) is type(exclusive) is dict and
            set(inclusive)==set(exclusive)==set(PhaseTelemetry.PHASES) and
            all(v is None or type(v) in (int,float) and math.isfinite(v) and v>=0
                for v in [*inclusive.values(),*exclusive.values()]) and
            all(type(observed[k]) in (int,float) and math.isfinite(observed[k]) and observed[k]>=0
                for k in ('elapsed_host_seconds','unscoped_host_seconds')) and
            all((inclusive[p] is None)==(exclusive[p] is None) and
                (inclusive[p] is None or exclusive[p]<=inclusive[p]+1e-9 and
                    inclusive[p]<=observed['elapsed_host_seconds']+1e-6) for p in inclusive) and
            all(inclusive[p] is None for p in set(PhaseTelemetry.PHASES)-{'generation','verification','parse_dedup','ranking'}) and
            math.isclose(sum(v or 0 for v in exclusive.values())+observed['unscoped_host_seconds'],
                observed['elapsed_host_seconds'],abs_tol=1e-6),
            'separate inference host phase partition required')
        require(type(observed['tests']) is dict and set(observed['tests'])=={str(i) for i in range(len(tests['tests']))} and
            all(t.get('test_index')==i and 'telemetry' in t and
                canonical(observed['tests'][str(i)])==canonical(t['telemetry']) for i,t in enumerate(tests['tests'])),
            'arm inference telemetry differs from independently replayed checkpoint')


def adapter_entry():
    return dict(constructor='tools.nvarc_e13_answer_evidence.AnswerModel',
        reserved={'control':0,'generation':0,'verification':0},completed={'control':0,'generation':0,'verification':0},
        input_tokens=0,observed_verifications=0,verification_rows=None,active=None,observer_rows=0)


def first_prefills(rows,count):
    first={}
    for row in rows:
        if row['event']=='forward_reserved' and row['phase']=='generation':
            first.setdefault(row['test_index'],{k:row[k] for k in
                ('input_ids_digest','batch_shape','cached','position_start')})
    require(set(first)==set(range(count)) and all(r['cached'] is False and r['position_start']==0
        for r in first.values()),'each actual test requires a fresh uncached prefill')
    return first


def verify_arm_isolation(directory,trained,metadata,post_rng,receipt,count,rows):
    directory=Path(directory)
    require(_read(directory/'trained-before-inventory.json')==_read(directory/'trained-after-inventory.json')==trained and
        _read(directory/'model-before-metadata.json')==_read(directory/'model-after-metadata.json')==metadata and
        receipt['before_inventory_digest']==receipt['after_inventory_digest']==digest(trained) and
        receipt['model_before_metadata_digest']==receipt['model_after_metadata_digest']==digest(metadata) and
        receipt['generation_rng_before']==post_rng and receipt['model_identity_preserved'] is True and
        receipt['fresh_adapter'] is receipt['fresh_caches'] is True and
        canonical(_read(directory/'adapter-entry.json'))==canonical(adapter_entry()),
        'both E13 arms must preserve the one trained state and restore its RNG with fresh adapters')
    prefix.validate_rng(receipt['generation_rng_before']);prefix.validate_rng(receipt['generation_rng_after'])
    return first_prefills(rows,count)


def worker(root,dependency,model,rank,deadline,parent_pid,dependency_receipt_sha256=None,*,runtime_api=None,expected_plan_sha256=None):
    if runtime_api is None:from tools import stage_nvarc_e13_search_budget as runtime_api
    root=Path(root);plan=runtime_api.verify_runtime(root,require_approved=True,expected_plan_sha256=expected_plan_sha256);profile_for_plan(plan)
    require(expected_plan_sha256 == digest(plan).removeprefix('sha256:'),
        'worker retains trusted parent plan pin before native work')
    from tools import nvarc_e13_answer_evidence as evidence
    require(type(rank) is int and 0<=rank<4 and type(deadline) in (int,float) and math.isfinite(deadline),'assigned E13 worker required')
    install_owner_guard(parent_pid,signal.SIGKILL)
    output=root/'workers'/str(rank);key=plan['task_order'][rank];spec=plan['task_specs'][key];bound=binding(plan,rank)
    training_dir=output/'training'
    events=Events(output/'events.jsonl',bound);observed=[];adapters=[];telemetry=PhaseTelemetry();errors=[]
    engine=trainer=budget=None;baseline=None;arms={};training_elapsed=0.;reset=None;peak=rss=None
    post_state=None;post_rng=None;paired_rng_restored=False;inference_telemetry={};paired_complete=False
    training=dict(binding=bound,training_updates=128,status='not_started',started_monotonic=None,
        finished_monotonic=None,training_seconds=None,completed_updates=0,optimizer_discarded=False,
        baseline_restored=False,trace_complete=False,errors=[])
    def emit(event,**details):
        require(event in ('forward_reserved','forward_completed','cache_control_result'),'only counted controls required')
        if event=='forward_reserved':require(time.time()<deadline,'absolute control deadline exhausted')
        observed.append(dict(event=event,**details));verify_observations(observed);events.emit(event,**details)
    class TrainingEngine(NativeEngine):
        def adapter(self,_emit,tests=1):
            adapter=control_adapter(self.model,self.torch,emit,telemetry);adapters.append(adapter);return adapter
    try:
        require_worker_receipt(root,plan,dependency,dependency_receipt_sha256)
        with telemetry.scope('load'):engine=TrainingEngine(root,plan,model,dependency,rank)
        require(len(adapters)==1,'exactly one six-control initialization per resident model required')
        baseline=engine.inventory();require(baseline==engine.baseline and len(baseline)==506,'all506 baseline bytes required')
        write(output/'baseline-inventory.json',baseline);write(output/'cache-control.json',engine.initial_control)
        base_metadata=model_metadata(engine.model);verify_model_metadata(base_metadata,plan)
        write(output/'baseline-model-metadata.json',base_metadata)
        ready=_read(output/'ready.json');ready['binding']=bound;write(output/'ready.json',ready)
        common_rng=capture_rng(engine);blocked=[]
        with telemetry.scope('preparation'),native_training.preparation_guard(engine.torch,blocked.append) as guard:
            material=public_training_material(engine.loader,engine.tokenizer,key,_read(root/'challenges.json')[key])
            require(material==_read(root/'materials'/f'{key}.json') and digest(material['rows'])==spec['expected_rows_digest'] and
                digest(material['texts'])==spec['texts_digest'],'same exact128 public demonstration rows required')
            write(output/'texts.json',material['texts']);write(output/'expected-rows.json',material['rows']);guard()
        require(not blocked,'unexpected native work during material preparation')
        training_dir.mkdir(parents=True,exist_ok=False);write(training_dir/'baseline-inventory.json',baseline)
        restore_rng(engine,common_rng);blocked=[]
        with native_training.preparation_guard(engine.torch,blocked.append) as guard:
            trainer=engine.trainer(material['texts'],material['rows'],training_dir)
            rates,schedule=native_schedule(engine.dependency,trainer.args,plan['native_source_learning_rates'])
            write(training_dir/'native-schedule.json',schedule);guard()
        require(not blocked,'unaccounted work during single native Trainer preparation')
        write(output/'training-ready.json',dict(binding=bound,prepared_rows=128,prepared_rows_digest=digest(material['rows']),
            control_forwards=6,training_updates=0,ready_monotonic=time.monotonic()))
        native_training.wait_for_release(root,plan,rank,deadline-plan['reset_reserve_seconds'])
        require(engine.inventory()==baseline,'single full training epoch must start at exact506 baseline')
        before=model_metadata(engine.model);unchanged_model_layout(base_metadata,before,plan)
        write(training_dir/'training-before-metadata.json',before)
        # Reuse the reviewed E12 full-128 observer unchanged. It receives its
        # historical ttt128 support label, never an E13 inference arm label.
        budget=PrefixBudget(engine,trainer,material['rows'],rates,schedule,plan['native_source_learning_rates'],
            training_dir,training_sources(plan,key),'ttt128')
        train_deadline=training_phase_deadline(plan,key,deadline,time.time())
        training.update(status='active',started_monotonic=time.monotonic())
        write(training_dir/'training-receipt.json',training)
        try:
            with telemetry.scope('training'),training_deadline(budget,train_deadline):
                trainer.train();moments=budget.complete()
            training['completed_updates']=128
        finally:
            training_elapsed=time.monotonic()-training['started_monotonic'];training['training_seconds']=training_elapsed
        require(training_elapsed<=plan['maximum_training_seconds'] and time.time()<=train_deadline,
            'single128-update training reservation exceeded')
        write(training_dir/'optimizer-state.json',moments)
        trained=engine.inventory();require(native_training.changed_tensors(baseline,trained)>0,'adapted weights must change')
        write(training_dir/'trained-inventory.json',trained)
        after=model_metadata(engine.model);write(training_dir/'training-after-metadata.json',after)
        unchanged_model_layout(before,after,plan)
        post_state=capture_rng(engine);post_rng=rng_observation(post_state)
        write(training_dir/'post-training-rng.json',post_rng)
        discard_optimizer_state(engine.model,trainer,budget)
        require(optimizer_disposed(engine,trainer,budget),'no Adam or gradient state may enter inference')
        training['optimizer_discarded']=True
        native_epoch.inference_transition(engine,trainer,training_dir,bound,'trained')
        engine.torch.cuda.empty_cache();gc.collect()
        trained_metadata=model_metadata(engine.model);verify_model_metadata(trained_metadata,plan)
        try:
            for ordinal,arm_id in enumerate(plan['arm_order'][key]):
                inference_cutoff=arm_inference_deadline(plan,key,ordinal,deadline)
                require(time.time()<inference_cutoff and engine.inventory()==trained,
                    'retained trained state and complete future-arm window required')
                arm=output/'arms'/arm_id;arm.mkdir(parents=True,exist_ok=False)
                before_inference=model_metadata(engine.model)
                require(before_inference==trained_metadata,'resident trained model metadata changed between arms')
                write(arm/'model-before-metadata.json',before_inference);write(arm/'trained-before-inventory.json',engine.inventory())
                restore_rng(engine,post_state);before_rng=rng_observation(capture_rng(engine))
                require(before_rng==post_rng,'all post-training RNG streams must match before each arm')
                receipt=dict(**arm_contract(arm_id),ordinal=ordinal,status='active',errors=[],
                    started_monotonic=time.monotonic(),started_epoch=time.time(),finished_monotonic=None,finished_epoch=None,
                    inference_started_monotonic=None,inference_finished_monotonic=None,
                    absolute_inference_cutoff_epoch=inference_cutoff,clock_overrun=None,
                    before_inventory_digest=digest(trained),after_inventory_digest=None,
                    model_before_metadata_digest=digest(before_inference),model_after_metadata_digest=None,
                    generation_rng_before=before_rng,generation_rng_after=None,
                    model_identity_preserved=False,fresh_adapter=False,fresh_caches=False)
                arms[arm_id]=receipt;write(arm/'arm-receipt.json',receipt);resident=engine.model
                try:
                    receipt['inference_started_monotonic']=time.monotonic()
                    with arm_inference_telemetry(inference_telemetry,arm_id) as arm_telemetry:
                        answers=evidence.solve_task(engine,root,plan,rank,inference_cutoff,arm_telemetry,
                            observe_forwards=True,schedule='interleaved',directory=arm,arm_id=arm_id)
                    receipt['inference_finished_monotonic']=time.monotonic()
                    receipt['generation_rng_after']=rng_observation(capture_rng(engine))
                    after_inference=model_metadata(engine.model);write(arm/'model-after-metadata.json',after_inference)
                    after_inventory=engine.inventory();write(arm/'trained-after-inventory.json',after_inventory)
                    rows=evidence.read_events(arm/'inference-events.jsonl',answers['binding'])
                    first_prefills(rows,plan['test_counts'][key])
                    receipt.update(after_inventory_digest=digest(after_inventory),model_after_metadata_digest=digest(after_inference),
                        model_identity_preserved=engine.model is resident,
                        fresh_adapter=canonical(_read(arm/'adapter-entry.json'))==canonical(adapter_entry()),fresh_caches=True)
                    verify_arm_isolation(arm,trained,trained_metadata,post_rng,receipt,plan['test_counts'][key],rows)
                    gc.collect();engine.torch.cuda.empty_cache()
                    require(time.time()<=inference_cutoff,'arm evidence/cleanup exceeded reserved inference cutoff')
                    receipt['status']='complete'
                except BaseException as error:
                    receipt['status']='failed';receipt['errors'].append(diagnostic(error,'e13-search-arm'));raise
                finally:
                    receipt['finished_monotonic']=time.monotonic();receipt['finished_epoch']=time.time()
                    receipt['clock_overrun']=receipt['finished_epoch']>inference_cutoff
                    if receipt['clock_overrun']:
                        receipt['status']='failed';receipt['errors'].append(dict(phase='e13-search-arm',type='InferenceDeadline',
                            message='arm finalization exceeded reserved inference cutoff'))
                    write(arm/'arm-receipt.json',receipt)
                require(receipt['status']=='complete','failed arm cannot proceed')
            paired_complete=True
        finally:
            restore_rng(engine,post_state);paired_rng_restored=rng_observation(capture_rng(engine))==post_rng
            require(paired_rng_restored,'post-training RNG restoration after pair required')
    except BaseException as error:errors.append(diagnostic(error,'e13-search-budget-worker'))
    finally:
        if engine is not None:
            def attempt(action,phase):
                try:return action()
                except BaseException as error:
                    detail=diagnostic(error,phase);errors.append(detail);training['errors'].append(detail);return None
            if trainer is not None:attempt(lambda:discard_optimizer_state(engine.model,trainer,budget),'terminal-discard')
            training['optimizer_discarded']=optimizer_disposed(engine,trainer,budget)
            attempt(engine.restore,'terminal-restore')
            if training_dir.is_dir():
                attempt(lambda:native_epoch.inference_transition(engine,trainer,training_dir,bound,'reset'),'terminal-inference')
            else:attempt(engine.inference,'terminal-inference')
            restored=attempt(engine.inventory,'terminal-inventory')
            if restored is not None:
                attempt(lambda:write(output/'final-reset-inventory.json',restored),'terminal-inventory-write')
                if training_dir.is_dir():attempt(lambda:write(training_dir/'reset-inventory.json',restored),'training-reset-write')
            training['baseline_restored']=restored==baseline
            attempt(lambda:require(training['baseline_restored'],'terminal baseline reset required'),'terminal-reset-check')
            if budget is not None and training['completed_updates']==128 and training['baseline_restored'] and not training['errors']:
                training['trace_complete']=attempt(budget.finish,'full128-trace-finish') is not None
            reset=attempt(lambda:reset_control(adapters[0],engine.initial_control),'seventh-reset-control')
            if reset is not None:attempt(lambda:write(output/'post-reset-control.json',reset),'control-write')
            peak=attempt(engine.torch.cuda.max_memory_allocated,'cuda-memory');rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
            attempt(lambda:require(peak is not None and peak<=plan['maximum_worker_cuda_allocated_bytes'] and
                rss<=plan['maximum_worker_host_rss_bytes'],'worker memory ceiling exceeded'),'memory-check')
        training['finished_monotonic']=time.monotonic()
        training['status']='complete' if training['trace_complete'] and training['optimizer_discarded'] and training['baseline_restored'] and not training['errors'] else 'failed'
        if training_dir.is_dir():write(training_dir/'training-receipt.json',training)
        if time.time()>deadline:errors.append(dict(phase='e13-worker-finalization',type='WorkerDeadline',message='absolute worker deadline exceeded'))
    shared=paired_complete and paired_rng_restored and training['status']=='complete'
    if not shared and not errors:errors.append(dict(phase='e13-worker',type='SharedStateIncomplete',message='shared state proof incomplete'))
    value=dict(binding=bound,outcome='failed' if errors else 'complete',errors=errors,arms=arms,training=training,
        training_elapsed_seconds=training_elapsed,controls=verify_observations(observed),post_reset_control=reset,
        peak_host_rss_bytes=rss,peak_cuda_allocated_bytes=peak,telemetry=telemetry.snapshot(),
        inference_telemetry=inference_telemetry_result(inference_telemetry),post_training_rng=post_rng,
        paired_rng_restored=paired_rng_restored,shared_training_verified=shared,
        native_model_instances=1 if engine is not None else 0,model_forwards_for_isolation=0,
        completed_training_updates=training['completed_updates'],finished_epoch=time.time(),
        correctness_scored=False,promotion=False,total_cost_reduction=None)
    ok=terminal_attempt(value,lambda:write(output/'result.json',value),phase='e13-worker-result')
    return 1 if errors or not ok else 0


def verify_controls(directory,result,bound):
    def read(name):return _read(directory/name)
    observed = []; head = digest(bound); body = native_epoch._read(directory/'events.jsonl',1024**2)
    require(body.endswith(b'\n'), 'complete control event chain required')
    for i,line in enumerate(body.splitlines()):
        row = json.loads(line)
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
    return result['controls']


def verify_training(root,plan,rank):
    arm_id='ttt128'
    directory=Path(root)/'workers'/str(rank)/'training'
    read=lambda name:_read(directory/name)
    key=plan['task_order'][rank];spec=plan['task_specs'][key];limit=128
    material=_read(Path(root)/'materials'/f'{key}.json');contract=read('prefix-contract.json');trace=read('prefix-trace.json')
    prefix.validate_trace(contract,trace)
    require(contract['evidence_kind']=='native-observed' and trace['profile']==PROFILES[arm_id] and
        contract['prepared_rows']==[{k:r[k] for k in prefix.ROW_FIELDS} for r in material['rows']] and
        len(material['rows'])==len(material['texts'])==128 and digest(material['rows'])==spec['expected_rows_digest'] and
        digest(material['texts'])==spec['texts_digest'],'exact native-prepared source rows and128horizon contract required')
    schedule=read('native-schedule.json');sampler=read('sampler.json')
    require(set(sampler)=={'module','name','source_path','source_sha256','iterator_source_path','iterator_source_sha256','replacement','num_samples','order'} and
        (sampler['module'],sampler['name'],sampler['source_path']) in
            {('torch.utils.data.sampler','RandomSampler','torch/utils/data/sampler.py'),
             ('accelerate.data_loader','SeedableRandomSampler','accelerate/data_loader.py')} and
        sampler['iterator_source_path']=='torch/utils/data/sampler.py' and
        type(sampler['iterator_source_sha256']) is str and len(sampler['iterator_source_sha256'])==64 and
        all(c in '0123456789abcdef' for c in sampler['iterator_source_sha256']) and type(sampler['source_sha256']) is str and
        len(sampler['source_sha256'])==64 and all(c in '0123456789abcdef' for c in sampler['source_sha256']) and
        sampler['replacement'] is False and type(sampler['num_samples']) is int and sampler['num_samples']==128 and
        sampler['order']==contract['sampler_order'],'observed unchanged native full sampler required')
    sources=training_sources(plan,key);sources['native_sampler_digest']=digest({k:v for k,v in sampler.items() if k!='order'})
    expected=prefix.build_native_contract(rows=contract['prepared_rows'],sampler_order=sampler['order'],
        reset=contract['reset'],sources=sources,rates=schedule['rates'],reference_rates=plan['native_source_learning_rates'],
        schedule_receipt=schedule)
    require(expected==contract,'native schedule/source provenance differs from trusted caller plan')
    ledger=read('training-ledger.json')
    require(set(ledger)=={'forwards','training_steps','optimizer_steps','optimizer_constructions','generation_calls','teacher_calls'} and
        ledger['optimizer_constructions']==[{'completed':True}] and
        type(ledger['generation_calls']) is type(ledger['teacher_calls']) is int and
        ledger['generation_calls']==ledger['teacher_calls']==0 and
        all(type(ledger[k]) is list and len(ledger[k])==limit for k in ('forwards','training_steps','optimizer_steps')),
        'one optimizer and exact completed E13 full128 counters required')
    for i,event in enumerate(trace['steps']):
        forward=ledger['forwards'][i];step=ledger['optimizer_steps'][i]
        require(set(forward)==prefix.ROW_FIELDS|{'completed','loss'} and
            {k:forward[k] for k in prefix.ROW_FIELDS}==event['row'] and forward['loss']==event['loss'] and
            forward['completed'] is True and ledger['training_steps'][i]=={'completed':True} and
            set(step)=={'learning_rate','gradient_tensors','gradient_norm_after_clip','completed'} and
            step['completed'] is True and step['learning_rate']==contract['learning_rates'][i] and
            type(step['gradient_tensors']) is int and step['gradient_tensors']==506 and
            type(step['gradient_norm_after_clip']) in (float,int) and math.isfinite(step['gradient_norm_after_clip']) and
            0<=step['gradient_norm_after_clip']<=1.05,'actual native forward/backward/Adam ledger differs from prefix trace')
    moments=read('optimizer-state.json')
    require(type(moments) is list and len(moments)==506 and sum(r['elements'] for r in moments)==528564224 and
        all(set(r)=={'elements','parameter_dtype','parameter_device','moment_bytes','step','finite'} and
            type(r['step']) is type(r['elements']) is type(r['moment_bytes']) is int and r['step']==limit and
            r['elements']>0 and r['moment_bytes']==4*r['elements'] and r['finite'] is True and
            r['parameter_dtype']=='torch.bfloat16' and r['parameter_device']=='cuda:0' for r in moments),
        'all506 finite native Adam states including zero-LR update required')
    status=read('native-hook-status.json')
    require(status==dict(format='irisx/e12-native-hooks-v1',arm_id=arm_id,sampler_iterations=1,callback_steps=limit,errors=[]),
        'all actual callback/sampler hooks must complete without failure')
    preparation=read('preparation.json')
    require(preparation==dict(checkpoint_flags=plan['native_checkpoint_flags'],trainer_origins=plan['native_trainer_origins']),
        'pinned native original Trainer and checkpoint policy required')
    prepared=read('prepared-rows.json')
    require(type(prepared) is list and len(prepared)==128 and all(
        set(r)==prefix.ROW_FIELDS|{'row','collator_preserved_input_ids','source_input_ids_equal','source_labels_equal'} and
        type(r['row']) is int and r['row']==i and {k:r[k] for k in prefix.ROW_FIELDS}==contract['prepared_rows'][i] and
        r['source_input_ids_equal'] is r['source_labels_equal'] is r['collator_preserved_input_ids'] is True
        for i,r in enumerate(prepared)), 'all128 actual prepared collator row/label digests required')
    baseline=read('baseline-inventory.json');trained=read('trained-inventory.json');restored=read('reset-inventory.json')
    require(baseline==restored==_read(Path(root)/'workers'/str(rank)/'baseline-inventory.json') and
        contract['reset']['model_inventory_digest']==digest(baseline) and
        native_training.changed_tensors(baseline,trained)>0 and
        all(r['finite'] is True and r['dtype']=='torch.bfloat16' for inv in (baseline,trained,restored) for r in inv),
        'exact baseline/changed506trained/reset bytes required')
    unchanged_model_layout(read('training-before-metadata.json'),read('training-after-metadata.json'),plan)
    for phase in ('trained','reset'):
        native_epoch.verify_inference_transition(read(phase+'-inference-transition.json'),binding(plan,rank),phase)
    return contract,trace


def verify_worker_result(root,plan,rank,uuid):
    profile_for_plan(plan);root=Path(root);directory=root/'workers'/str(rank);key=plan['task_order'][rank]
    from tools import nvarc_e13_answer_evidence as evidence
    result=_read(directory/'result.json');bound=binding(plan,rank)
    fields={'binding','outcome','errors','arms','training','training_elapsed_seconds','controls','post_reset_control',
        'peak_host_rss_bytes','peak_cuda_allocated_bytes','telemetry','inference_telemetry','native_model_instances',
        'model_forwards_for_isolation','completed_training_updates','finished_epoch','correctness_scored','promotion',
        'total_cost_reduction','post_training_rng','paired_rng_restored','shared_training_verified'}
    require(set(result)==fields and result['binding']==bound and result['outcome']=='complete' and result['errors']==[] and
        set(result['arms'])==set(ARMS) and type(result['completed_training_updates']) is int and result['completed_training_updates']==128 and
        type(result['native_model_instances']) is type(result['model_forwards_for_isolation']) is int and
        result['native_model_instances']==1 and result['model_forwards_for_isolation']==0 and
        result['shared_training_verified'] is result['paired_rng_restored'] is True and
        result['correctness_scored'] is result['promotion'] is False and result['total_cost_reduction'] is None,
        'complete native E13 resident worker with single128updates required')
    baseline=_read(directory/'baseline-inventory.json')
    require(_read(directory/'final-reset-inventory.json')==baseline,'terminal baseline must restore exactly')
    ready=_read(directory/'ready.json')
    require(ready==dict(rank=rank,uuid=uuid,model_material_digest=plan['model_material_digest'],
        baseline_digest=digest(baseline),torch=plan['runtime_torch_version'],
        initial_control_forwards={'control':6,'generation':0,'verification':0},binding=bound),
        'exact assigned-device initial6control proof required')
    verify_controls(directory,result,bound);verify_model_metadata(_read(directory/'baseline-model-metadata.json'),plan)
    training_dir=directory/'training';training=_read(training_dir/'training-receipt.json')
    training_fields={'binding','training_updates','status','started_monotonic','finished_monotonic','training_seconds',
        'completed_updates','optimizer_discarded','baseline_restored','trace_complete','errors'}
    require(set(training)==training_fields and training==result['training'] and training['binding']==bound and
        type(training['training_updates']) is type(training['completed_updates']) is int and
        training['training_updates']==training['completed_updates']==128 and training['status']=='complete' and
        training['errors']==[] and training['optimizer_discarded'] is training['baseline_restored'] is training['trace_complete'] is True and
        all(type(training[k]) in (int,float) and math.isfinite(training[k]) for k in
            ('started_monotonic','finished_monotonic','training_seconds')) and
        0<=training['started_monotonic']<=training['finished_monotonic'] and
        0<=training['training_seconds']==result['training_elapsed_seconds']<=plan['maximum_training_seconds'],
        'single native128 training and one final baseline reset receipt required')
    contract,trace=verify_training(root,plan,rank)
    unchanged_model_layout(_read(directory/'baseline-model-metadata.json'),_read(training_dir/'training-before-metadata.json'),plan)
    trained=_read(training_dir/'trained-inventory.json');post_rng=_read(training_dir/'post-training-rng.json')
    prefix.validate_rng(post_rng)
    require(result['post_training_rng']==post_rng and post_rng==trace['steps'][-1]['rng_after'],
        'captured generation RNG must be actual terminal full128 training RNG')
    launch=_read(directory/'launch-reservation.json')
    require(launch['binding']==bound and type(launch['training_updates']) is type(launch['control_forwards']) is int and
        launch['training_updates']==128 and launch['control_forwards']==7 and
        type(launch['deadline_epoch']) in (int,float) and math.isfinite(launch['deadline_epoch']),
        'correct finite worker launch reservation required')
    require(type(result['finished_epoch']) in (float,int) and math.isfinite(result['finished_epoch']) and
        result['finished_epoch']<=launch['deadline_epoch'],'worker final reset/control/evidence must finish before absolute deadline')
    answers={};prefills={};previous=None;metadata=None
    for ordinal,arm_id in enumerate(plan['arm_order'][key]):
        arm=directory/'arms'/arm_id;receipt=_read(arm/'arm-receipt.json')
        expected=set(arm_contract(arm_id))|{'ordinal','status','errors','started_monotonic','started_epoch',
            'finished_monotonic','finished_epoch','inference_started_monotonic','inference_finished_monotonic',
            'absolute_inference_cutoff_epoch','clock_overrun','before_inventory_digest','after_inventory_digest',
            'model_before_metadata_digest','model_after_metadata_digest','generation_rng_before','generation_rng_after',
            'model_identity_preserved','fresh_adapter','fresh_caches'}
        cutoff=arm_inference_deadline(plan,key,ordinal,launch['deadline_epoch'])
        require(set(receipt)==expected and receipt==result['arms'][arm_id] and
            all(type(receipt[k]) is type(v) and receipt[k]==v for k,v in arm_contract(arm_id).items()) and
            type(receipt['ordinal']) is int and receipt['ordinal']==ordinal and receipt['status']=='complete' and
            receipt['errors']==[] and receipt['clock_overrun'] is False and
            receipt['absolute_inference_cutoff_epoch']==cutoff and
            all(type(receipt[k]) in (float,int) and math.isfinite(receipt[k]) for k in
                ('started_monotonic','finished_monotonic','started_epoch','finished_epoch',
                 'inference_started_monotonic','inference_finished_monotonic')) and
            training['started_monotonic']+training['training_seconds']<=receipt['started_monotonic']<=
                receipt['inference_started_monotonic']<=receipt['inference_finished_monotonic']<=
                receipt['finished_monotonic']<=training['finished_monotonic'] and
            receipt['started_epoch']<=receipt['finished_epoch']<=cutoff and
            (previous is None or receipt['started_monotonic']>=previous),
            'strict sequential shared-state arm completion and reserved cutoff receipt required')
        previous=receipt['finished_monotonic']
        before=_read(arm/'model-before-metadata.json');after=_read(arm/'model-after-metadata.json')
        verify_model_metadata(before,plan);verify_model_metadata(after,plan)
        if metadata is None:metadata=before
        allocations=_read(arm/'test-allocations.json')
        require(all(a['session_deadline_epoch']==cutoff for a in allocations.values()),
            'caller-owned full future-arm and terminal reset reserve required')
        answers[arm_id]=evidence.verify_task(root,plan,rank,directory=arm,schedule='interleaved',arm_id=arm_id,
            admitted_allocations=allocations)
        rows=evidence.read_events(arm/'inference-events.jsonl',answers[arm_id]['binding'])
        prefills[arm_id]=verify_arm_isolation(arm,trained,metadata,post_rng,receipt,plan['test_counts'][key],rows)
    verify_inference_telemetry(result['inference_telemetry'],answers)
    require(result['telemetry']['tests']=={} and all(result['telemetry'][kind][p] is None
        for kind in ('inclusive_host_seconds','exclusive_host_seconds')
        for p in ('generation','verification','parse_dedup','ranking')),
        'worker load/control/training telemetry must remain separate from arm inference')
    require(prefills['search120']==prefills['search240'],'both search arms must share the same original input prefix')
    for field,cap in (('peak_host_rss_bytes',plan['maximum_worker_host_rss_bytes']),
            ('peak_cuda_allocated_bytes',plan['maximum_worker_cuda_allocated_bytes'])):
        require(type(result[field]) is int and 0<=result[field]<=cap,'observed memory within perworker reservation required')
    return dict(result,verified_inference=answers,shared_training_verified=True)


def worker_deadline_monotonic(plan,started,spawned):
    profile_for_plan(plan)
    require(all(type(v) in (int,float) and math.isfinite(v) for v in (started,spawned)) and
        started<=spawned<started+plan['startup_seconds'],'worker launch must remain in original startup allowance')
    # A worker's resident-model load consumes the remaining shared startup
    # allowance. 3120 = full900 startup +1200 training +840 inference +180reset;
    # the outer3290 cutoff leaves its separate300-second finalizer reserve.
    return min(started+3290,spawned+plan['maximum_worker_seconds'])


def execute(root, dependency, started, *, runtime_api=None, expected_plan_sha256=None):
    if runtime_api is None:
        from tools import stage_nvarc_e13_search_budget as runtime_api
    from tools.nvarc_e13_cleanup import cleanup_workers
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('E13 coordinator stop requested')))
    cleanup_hook=functools.partial(cleanup_workers,deadline_monotonic=started+3299.8)
    verify_runtime, SCOPE = runtime_api.verify_runtime, runtime_api.SCOPE
    root = Path(root); plan = verify_runtime(root,require_approved=True,expected_plan_sha256=expected_plan_sha256)
    require(expected_plan_sha256 == digest(plan).removeprefix('sha256:'),
        'coordinator retains trusted notebook plan pin before native work')
    write(root/'coordinator-admitted.json',{'run_id':plan['run_id'],'plan_digest':digest(plan)})
    states = {}; results = {}; errors = []; cleanup = {'all_producers_stopped':True}; overlap = None
    try:
        verify_before_prepare(root,plan,dependency,started)
        receipt_sha = hashlib.sha256((root/RECEIPT_FILE).read_bytes()).hexdigest()
        write(root/'mount-policy.json',verify_mount(plan,SCOPE)); model,hardware = prepare(root,plan,dependency)
        require(time.monotonic()-started < plan['startup_seconds'], 'initial material/hardware budget exhausted')
        end = worker_deadline_monotonic(plan,started,time.monotonic())
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
                'training_updates':128,'control_forwards':7,'attempt':1,
                'test_count':plan['test_counts'][plan['task_order'][rank]]})
            worker_path = getattr(runtime_api,'WORKER_PATH','tools/nvarc_e10_end_to_end.py')
            command = [sys.executable,str(root/worker_path),'--root',str(root),'--dependency',str(dependency),
                '--model',str(model),'--rank',str(rank),'--deadline',str(deadline),'--parent-pid',str(os.getpid()),
                '--dependency-receipt-sha256',receipt_sha,
                '--expected-plan-sha256',expected_plan_sha256]
            state['process'] = subprocess.Popen(command,env=environment,cwd=directory,start_new_session=True,
                stdout=state['streams']['stdout'],stderr=state['streams']['stderr'])
            launch_observer=getattr(runtime_api,'record_worker_launch',None)
            if launch_observer is not None:launch_observer(root,plan,rank,state['process'])
        ready = {}
        while time.monotonic() < min(started+plan['startup_seconds'],end-plan['reset_reserve_seconds']):
            for rank,state in states.items():
                require(state['process'].poll() is None, 'worker failed before all-four preparation barrier: '+str(rank))
                path = root/'workers'/str(rank)/'training-ready.json'
                if path.is_file():
                    value = json.loads(path.read_bytes()); spec = plan['task_specs'][plan['task_order'][rank]]
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
            'training_deadline_epoch':deadline-plan['reset_reserve_seconds']})
        while time.monotonic() < end and any(s['process'].poll() is None for s in states.values()):
            require(not any(s['process'].poll() not in (None,0) for s in states.values()),
                'native worker failed; remaining workers stopped without retry')
            time.sleep(.1)
        for rank,state in states.items():
            require(state['process'].poll() == 0, 'native training process failed or exceeded finite deadline: '+str(rank))
            verifier = getattr(runtime_api,'verify_worker_result',verify_worker_result)
            results[str(rank)] = verifier(root,plan,rank,hardware[rank]['uuid'])
        require(sum(r['peak_host_rss_bytes'] for r in results.values()) <= plan['maximum_aggregate_host_rss_bytes'],
            'aggregate host memory cap exceeded')
        require(sum(r['completed_training_updates'] for r in results.values())==512,'all4workers exact512completed updates required')
    except BaseException as error: errors.append(diagnostic(error,'ttt-probe-coordinator'))
    finally:
        try:
            cleanup = (cleanup_workers(list(states.values()),stop_process,primary=sys.exception())
                if cleanup_hook is None else cleanup_hook(list(states.values()),stop_process,primary=sys.exception()))
        except BaseException as error:
            errors.append(diagnostic(error,'ttt-probe-cleanup')); cleanup = getattr(error,'cleanup_report',{'all_producers_stopped':False})
    sealed = None
    try:
        if cleanup.get('all_producers_stopped') is True and (cleanup_hook is None or cleanup.get('complete_before_deadline') is True):
            sealer = getattr(runtime_api,'seal_outputs',seal_outputs)
            sealed = sealer(root,plan,results,errors)
    except BaseException as error: errors.append(diagnostic(error,'sealed-output'))
    terminal = {'probe_id':plan['screen_id'],'plan_digest':digest(plan),'outcome':'failed' if errors else 'complete',
        'errors':errors,'results':results,'cleanup':cleanup,'host_wall_seconds':time.monotonic()-started,
        'total_cost_reduction':None,'pilot_scope':'engineering/cost mechanism only; no original24task/fullscreen or BASE0 claim', 'paid_usd':0,'sealed_output':sealed,
        'correctness_scored':False,'promotion':False,'official_submission':False,
        'full_screen_feasibility_established':False,'gpu_kernel_timing_attestation':False,
        'archive_finalization':'outer notebook after coordinator stop and finalized stdout capture'}
    publish_terminal(root,terminal); print(json.dumps(terminal),flush=True)
    return 0 if terminal['outcome'] == 'complete' else 1



def validate_stop_receipts(observation,terminal,plan,root,*,allow_observation_errors=False):
    """Recompute the exact 60-minute caller policy, never trust a success flag."""
    require(plan['resource_budget_profile'] in (BUDGET_PROFILE,'bounded-60min-run'),'exact60minute E13 stop receipt required')
    receipt=observation.get('e13_supervision',{});start=receipt.get('started_monotonic')
    finite=lambda value:type(value) in (int,float) and math.isfinite(value)
    require(finite(start) and start>=0 and receipt.get('format')=='irisx/e13-supervision-v1' and
        all(finite(receipt.get(key)) and receipt[key]==start+offset for key,offset in (
            ('term_deadline_monotonic',3290),('kill_deadline_monotonic',3299.8),
            ('stop_deadline_monotonic',3300),('finalizer_deadline_monotonic',3600))) and
        observation.get('hard_deadline_monotonic')==start+3600 and
        observation.get('confirmed_stopped') is True and
        type(receipt.get('errors')) is list and
        (receipt['errors']==[] or allow_observation_errors) and
        observation.get('reserve_preserved') is receipt.get('reserve_preserved') is (not bool(receipt['errors'])) and
        observation.get('launched') is True and type(observation.get('returncode')) is int and
        receipt.get('coordinator_group_absent') is True and
        all(finite(receipt.get(key)) for key in ('coordinator_stopped_monotonic','capture_finished_monotonic','finished_monotonic')) and
        start<=receipt['coordinator_stopped_monotonic']<=receipt['capture_finished_monotonic']<=receipt['finished_monotonic']<=start+3300 and
        receipt.get('finalization_remaining_seconds')==start+3600-receipt['finished_monotonic'] and
        observation.get('output_capture',{}).get('written') is True,
        'exact E13 outer stop/capture/deadline receipt required')
    error_cleanup=False
    if receipt.get('failure_cleanup_started_monotonic') is not None:
        failure_start=receipt['failure_cleanup_started_monotonic']
        error_cleanup=(allow_observation_errors and receipt.get('supervisor_error_cleanup') is True and
            bool(receipt['errors']) and finite(failure_start) and
            start<=failure_start<=receipt['coordinator_stopped_monotonic'] and
            receipt.get('failure_cleanup_deadline_monotonic')==min(failure_start+10,start+3300) and
            receipt['coordinator_stopped_monotonic']<=receipt['failure_cleanup_deadline_monotonic'])
        require(error_cleanup,'exact bounded E13 supervision-error cleanup receipt required')
    for key,offset in (('term_requested_monotonic',3290),('kill_requested_monotonic',3299.8)):
        stamp=receipt.get(key)
        require(stamp is None or finite(stamp) and start<=stamp<=receipt['finished_monotonic'] and
            (stamp>=start+offset or key=='kill_requested_monotonic' and
                (receipt.get('orphaned_group_observed') is True or error_cleanup and
                    receipt['failure_cleanup_started_monotonic']<=stamp)),
            'E13 signal request timing differs')
    cleanup=terminal.get('cleanup',{})
    require(terminal.get('plan_digest')==digest(plan) and cleanup.get('format')=='irisx/e13-collective-cleanup-v1' and
        cleanup.get('deadline_monotonic')==start+3299.8 and
        cleanup.get('all_producers_stopped') is cleanup.get('complete_before_deadline') is True and
        cleanup.get('timed_out') is False and cleanup.get('secondary_errors')==[] and
        all(finite(cleanup.get(key)) for key in ('started_monotonic','finished_monotonic')) and
        start<=cleanup['started_monotonic']<=cleanup['finished_monotonic']<=start+3299.8 and
        cleanup['finished_monotonic']<=receipt['coordinator_stopped_monotonic'] and
        type(cleanup.get('workers')) is list and len(cleanup['workers'])<=4,
        'all owned E13 producers must stop within the exact shared cleanup deadline')
    require(type(observation.get('coordinator_pid')) is int and observation['coordinator_pid']>1 and
        observation.get('coordinator_process_group_id')==observation['coordinator_pid'] and
        observation.get('coordinator_start_new_session') is True,'actual owned coordinator group required')
    root=Path(root);worker_root=root/'workers'
    registered={path.name for path in worker_root.iterdir() if path.is_dir()} if worker_root.exists() else set()
    require(all(name in ('0','1','2','3') for name in registered) and
        {row.get('identity') for row in cleanup['workers']}==registered,
        'every registered worker directory requires its cleanup receipt')
    identities=set();pids=set()
    for worker in cleanup['workers']:
        require(worker.get('identity') in ('0','1','2','3') and worker['identity'] not in identities,
            'unique registered E13 cleanup worker required')
        identities.add(worker['identity'])
        launch_path=worker_root/worker['identity']/'process-launch.json'
        if worker.get('pid') is None:
            require(worker.get('stop_attempted') is False and not launch_path.exists(),
                'unlaunched worker cannot claim signal or omit its recorded PID')
        else:
            require(type(worker['pid']) is int and worker['pid']>1 and worker['pid'] not in pids and worker['pid']!=observation['coordinator_pid'] and
                worker.get('stop_attempted') is worker.get('group_absent') is worker.get('stop_confirmed') is True and
                type(worker.get('returncode')) is int and finite(worker.get('kill_requested_monotonic')) and
                finite(worker.get('stop_confirmed_monotonic')) and
                cleanup['started_monotonic']<=worker['kill_requested_monotonic']<=worker['stop_confirmed_monotonic']<=cleanup['finished_monotonic'],
                'actual owned worker group absence and ordered kill/stop observations required')
            launch=_read(launch_path)
            require(set(launch)=={'format','binding','pid','process_group_id','started_monotonic','start_new_session'} and
                launch['format']=='irisx/e13-owned-worker-launch-v1' and launch['binding']==native_epoch.binding(plan,int(worker['identity'])) and
                type(launch['pid']) is type(launch['process_group_id']) is int and
                launch['pid']==launch['process_group_id']==worker['pid'] and launch['start_new_session'] is True and
                finite(launch['started_monotonic']) and start<=launch['started_monotonic']<=cleanup['started_monotonic'],
                'cleanup PID/group must match the actual caller-owned launch receipt')
            pids.add(worker['pid'])
    return receipt



def record_worker_launch(root,plan,rank,process):
    profile_for_plan(plan)
    require(type(rank) is int and 0<=rank<4 and type(process.pid) is int and process.pid>1 and
        process.pid not in (os.getpid(),os.getpgrp()),'actual owned E13 worker launch required')
    write(Path(root)/'workers'/str(rank)/'process-launch.json',dict(format='irisx/e13-owned-worker-launch-v1',
        binding=binding(plan,rank),pid=process.pid,process_group_id=process.pid,started_monotonic=time.monotonic(),start_new_session=True))


def seal_outputs(root,plan,results,errors):
    from tools import nvarc_e13_answer_evidence as evidence
    profile_for_plan(plan);root=Path(root);values={};coverage={};audits={};timings={};recovery_errors=[]
    for arm in ARMS:
        answers={};pools={};audit=[];times={}
        for rank,key in enumerate(plan['task_order']):
            result=results.get(str(rank));inference=None;recovered=False
            if result is not None:inference=result['verified_inference'][arm]
            else:
                path=root/'workers'/str(rank)/'arms'/arm
                if (path/'answer-checkpoint.json').is_file() and (path/'test-allocations.json').is_file():
                    try:
                        inference=evidence.recover_completed_tests(root,plan,rank,directory=path,arm_id=arm,
                            schedule='interleaved',admitted_allocations=_read(path/'test-allocations.json'));recovered=True
                    except BaseException as error:recovery_errors.append(diagnostic(error,'e13-committed-prefix-replay'))
            answers[key]=[];pools[key]=[];times[key]=[]
            for index in range(plan['test_counts'][key]):
                test=None if inference is None else inference['tests'][index]
                attempts=[] if test is None else test.get('attempts',[])
                answers[key].append(dict(attempt_1=attempts[0] if attempts else None,attempt_2=attempts[1] if len(attempts)>1 else None))
                pools[key].append([] if test is None else test.get('ranked_grids',[]))
                audit.append(dict(**arm_contract(arm),task_id=key,test_index=index,actual_candidates=len(attempts),
                    missing_attempts=2-len(attempts),output_qualified=bool(result and test and test.get('output_qualified')),
                    shared_training_verified=result is not None,status='unavailable' if test is None else test['status'],
                    provenance='unqualified-committed-prefix' if recovered else 'verified-shared-state-worker' if result else 'unavailable'))
                times[key].append(None if test is None else {k:test.get(k) for k in
                    ('started_epoch','finished_epoch','deadline_epoch','clock_overrun','coverage','termination_reason','telemetry')})
        values[arm+'-answers.json']=dict(format='irisx/exposed-calibration-answers-v1',tasks=answers,official_submission_ready=False)
        values[arm+'-audit.json']=audit;values[arm+'-candidate-pools.json']=dict(**arm_contract(arm),tasks=pools)
        coverage[arm]=dict(test_cases=6,actual_attempts=sum(r['actual_candidates'] for r in audit),
            missing_attempts=sum(r['missing_attempts'] for r in audit),qualified_test_cases=sum(r['output_qualified'] for r in audit),
            output_qualified=not errors and len(results)==4 and all(r['output_qualified'] for r in audit))
        audits[arm]=audit;timings[arm]=times
    summary=dict(format='irisx/e13-search-budget-output-v1',run_id=RUN_ID,plan_digest=digest(plan),arm_order=plan['arm_order'],
        arm_contracts={a:arm_contract(a) for a in ARMS},per_arm=coverage,planned_training_updates=512,
        verified_completed_training_updates=sum(r['completed_training_updates'] for r in results.values()),
        actual_training_updates_all_workers=sum(r['completed_training_updates'] for r in results.values()) if len(results)==4 else None,
        planned_test_executions=12,paired_workers_verified=len(results),errors=errors,recovery_errors=recovery_errors,
        full_screen_feasibility_established=False,original_fullscreen_scope='24tasks/35tests x2arms x2repeats remains unexecuted',
        total_cost_reduction=None,quality_comparison_qualified=False,correctness_scored=False,promotion=False,
        official_submission_ready=False,base0_causal_claim=False)
    values.update({'paired-summary.json':summary,'paired-task-timings.json':timings})
    for value in values.values():reject_truth(value)
    store=GenerationStore(root,'e13-search-budget-pilot',dict(run_id=RUN_ID,plan_digest=digest(plan),challenges_digest=plan['challenges_digest']))
    require(not (root/'output-commit.json').exists(),'single immutable E13 output publication required')
    manifest=store.publish(values,evidence_qualified=not errors and len(results)==4 and all(c['output_qualified'] for c in coverage.values()))
    store.read();return dict(manifest_digest=digest(manifest),**summary)


def finalize(root,observation,expected_plan_sha256):
    from tools.nvarc_e13_archive import finalize as close
    return close(root,observation,expected_plan_sha256)

"""Native E12 64-prefix/128-control engineering pilot; admission is external.

One resident model per GPU, fresh independent Trainer/optimizer per arm. The
original 128-row epoch and its scheduler remain unchanged. No quality or total
allocated-GPU cost claim follows from this shared-session pilot.
"""
from __future__ import annotations
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
from tools.nvarc_e12_output_lifecycle import GenerationStore
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

FORMAT='irisx/stage4-e12-prefix-probe-v1'
RUN_ID='stage4-e12-probe-prefix-20261007-001'
PROFILE='native-prefix-stop-v10'
BUDGET_PROFILE='conservative-60min-inert'
ARMS=('ttt64','ttt128')
TASK_COUNTS={'195c6913':2,'aa4ec2a5':1,'a47bf94d':1,'a25697e4':2}
TIMING=dict(generation_seconds=120,verification_reserve_seconds=30,per_test_seconds=150,
    startup_seconds=900,maximum_training_seconds=1200,inference_reserve_seconds=600,
    reset_reserve_seconds=360,finalization_reserve_seconds=300,maximum_worker_seconds=3060,
    maximum_notebook_wall_seconds=3600)
CAPS=dict(maximum_generation_forwards=49152,maximum_verification_forwards=1536,
    maximum_inference_input_tokens=62914560,maximum_processed_sequences_total=768)
PER_ARM_CAPS=dict(maximum_generation_forwards=24576,maximum_verification_forwards=768,
    maximum_inference_input_tokens=31457280,maximum_processed_sequences_total=384)
MODEL_LAYOUT=dict(parameter_count=905,buffer_count=0,
    digest='sha256:06a1ed5e10ce2c741cb661ba3e883952e3fbce3e0931ce151485b9ac4d31a479')
PROCESS_POLICY=dict(term_seconds=3290,kill_seconds=3299.8,stop_seconds=3300,final_seconds=3600,
    worker_cleanup_deadline_seconds=3299.8,requires_owned_group_absence=True)
ALLOCATION='irisx/e12-prefix-test-allocation-v1'


def arm_contract(arm):
    require(arm in ARMS,'exact E12 arm required')
    return dict(experiment='prefix-stop-v10',arm_id=arm,training_updates=64 if arm=='ttt64' else 128,
        schedule='interleaved',dfs_probability_floor=.2,dfs_max_score=-math.log(.2))


def counterbalanced_order(counts):
    require(canonical(counts)==canonical(TASK_COUNTS),'same four tasks/six tests required')
    return {key:list(ARMS if position%2==0 else reversed(ARMS)) for count in (1,2)
        for position,key in enumerate(sorted(k for k,n in counts.items() if n==count))}


def budget_report():
    return dict(budget_profile=BUDGET_PROFILE,phase_seconds=3360,worker_phase_seconds=2160,
        notebook_margin_seconds=240,parent_worker_cutoff_seconds=3300,
        charged_gpu_seconds_ceiling=14400,charged_gpu_hours_ceiling=4,paid_usd_ceiling=0,
        resource_qualification=False,status='INERT_NOT_ADMITTED',
        feasibility='planning only; fresh quota and exact package review required; no 45-minute shrink',
        total_cost_reduction=None,full_screen_feasibility_established=False)


def profile_for_plan(plan):
    require(plan.get('format')==FORMAT and plan.get('run_id')==plan.get('screen_id')==RUN_ID and
        plan.get('generation_budget_profile')==PROFILE and plan.get('resource_budget_profile')==BUDGET_PROFILE and
        plan.get('forward_observer_required') is True and
        canonical(plan.get('test_counts'))==canonical(TASK_COUNTS) and plan.get('task_order')==list(TASK_COUNTS) and
        canonical(plan.get('arm_order'))==canonical(counterbalanced_order(TASK_COUNTS)) and
        canonical(plan.get('arm_contracts'))==canonical({a:arm_contract(a) for a in ARMS}) and
        canonical(plan.get('per_arm_caps'))==canonical(PER_ARM_CAPS) and
        canonical(plan.get('retained_model_layout'))==canonical(MODEL_LAYOUT) and
        canonical(plan.get('e12_process_policy'))==canonical(PROCESS_POLICY) and
        plan.get('verification_schedule')=='interleaved' and plan.get('verification_schedules')==['interleaved'] and
        all(type(plan.get(k)) is int and plan[k]==v for k,v in {**TIMING,**CAPS,
            'cleanup_reserve_seconds':310,'maximum_training_forwards':768,'maximum_training_backwards':768,
            'optimizer_steps':768,'per_worker_training_steps':192,'maximum_control_forwards':28,
            'per_worker_forwards':7,'expected_notebook_version':10,'expected_previous_version':9}.items()),
        'closed E12 native prefix-only 60-minute profile required')
    return dict(profile_id=PROFILE,run_id=RUN_ID,forward_observer_required=True,**TIMING)


def validate_binding(bound,arm_id=None):
    require(type(bound) is dict,'exact E12 binding object required')
    arm=bound.get('arm_id') if arm_id is None else arm_id
    expected=arm_contract(arm)
    require(bound.get('run_id')==RUN_ID and all(type(bound.get(k)) is type(v) and bound[k]==v
        for k,v in expected.items()),'exact E12 prefix arm and unchanged p02 binding required')
    return expected


def allocation_deadlines(value,bound,index):
    validate_binding(bound)
    require(type(value) is dict and set(value)=={'format','binding','test_index','started_epoch',
        'session_deadline_epoch','generation_seconds','total_seconds','verification_reserve_seconds'} and
        value['format']==ALLOCATION and value['binding']==bound and type(value['test_index']) is int and
        value['test_index']==index and all(type(value[k]) is int and value[k]==v for k,v in
            (('generation_seconds',120),('total_seconds',150),('verification_reserve_seconds',30))) and
        all(type(value[k]) in (int,float) and math.isfinite(value[k]) for k in ('started_epoch','session_deadline_epoch')) and
        value['started_epoch']+150<=value['session_deadline_epoch'],
        'full unchanged E12 120/150-second test allocation required')
    return value['started_epoch']+120,value['started_epoch']+150


def paired_allocation(bound,index,start,deadline):
    value=dict(format=ALLOCATION,binding=bound,test_index=index,started_epoch=start,
        session_deadline_epoch=deadline,generation_seconds=120,total_seconds=150,verification_reserve_seconds=30)
    allocation_deadlines(value,bound,index);return value


def binding(plan,rank):return native_epoch.binding(plan,rank)


def training_sources(plan,key):
    return dict(challenge_digest=plan['challenges_digest'],model_digest=plan['model_material_digest'],
        dependency_digest=plan['dependency_readproof_digest'],configuration_digest=digest(plan['original_training_arguments']),
        inference_contract_digest=digest(dict(schedule='interleaved',dfs_probability_floor=.2,
            generation_seconds=120,per_test_seconds=150,per_test_limits={'generation':4096,'verification':128,'input_tokens':5242880})),
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


def arm_phase_deadlines(plan,key,ordinal,deadline,now_epoch,training_elapsed):
    profile_for_plan(plan)
    require(key in TASK_COUNTS and type(ordinal) is int and ordinal in (0,1) and
        all(type(v) in (int,float) and math.isfinite(v) for v in (deadline,now_epoch,training_elapsed)) and
        0<=training_elapsed<=plan['maximum_training_seconds'],'finite original E12 phase reservation required')
    remaining=2-ordinal
    training=min(now_epoch+plan['maximum_training_seconds']-training_elapsed,
        deadline-180*remaining-TASK_COUNTS[key]*150*remaining)
    inference=deadline-180*remaining
    require(training>now_epoch,'combined training or fixed future inference/reset reserve exhausted')
    return training,inference


def worker(root,dependency,model,rank,deadline,parent_pid,dependency_receipt_sha256=None,*,runtime_api=None):
    if runtime_api is None:from tools import stage_nvarc_e12_prefix_probe as runtime_api
    root=Path(root);plan=runtime_api.verify_runtime(root,require_approved=True);profile_for_plan(plan)
    from tools import nvarc_e12_answer_evidence as evidence
    require(type(rank) is int and 0<=rank<4 and math.isfinite(deadline),'assigned E12 worker required')
    install_owner_guard(parent_pid,signal.SIGKILL)
    output=root/'workers'/str(rank);key=plan['task_order'][rank];spec=plan['task_specs'][key];bound=binding(plan,rank)
    events=Events(output/'events.jsonl',bound);observed=[];adapters=[];telemetry=PhaseTelemetry();errors=[]
    engine=trainer=budget=None;baseline=None;arms={};training_elapsed=0.;reset=None;peak=rss=None
    common_rng=None
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
        common_rng=capture_rng(engine)
        blocked=[]
        with telemetry.scope('preparation'),native_training.preparation_guard(engine.torch,blocked.append) as guard:
            material=public_training_material(engine.loader,engine.tokenizer,key,_read(root/'challenges.json')[key])
            require(material==_read(root/'materials'/f'{key}.json') and digest(material['rows'])==spec['expected_rows_digest'] and
                digest(material['texts'])==spec['texts_digest'],'same exact128 public demonstration rows required')
            write(output/'texts.json',material['texts']);write(output/'expected-rows.json',material['rows']);guard()
        require(not blocked,'unexpected native work during material preparation')
        first_arm=output/'arms'/plan['arm_order'][key][0];first_arm.mkdir(parents=True,exist_ok=False)
        restore_rng(engine,common_rng);blocked=[]
        with native_training.preparation_guard(engine.torch,blocked.append) as guard:
            trainer=engine.trainer(material['texts'],material['rows'],first_arm)
            rates,schedule=native_schedule(engine.dependency,trainer.args,plan['native_source_learning_rates'])
            write(first_arm/'native-schedule.json',schedule);guard()
        require(not blocked,'unaccounted work during first native Trainer preparation')
        prepared=(trainer,rates,schedule)
        write(output/'training-ready.json',dict(binding=bound,prepared_rows=128,prepared_rows_digest=digest(material['rows']),
            control_forwards=6,training_updates=0,ready_monotonic=time.monotonic()))
        released=native_training.wait_for_release(root,plan,rank,deadline-plan['reset_reserve_seconds'])
        for ordinal,arm_id in enumerate(plan['arm_order'][key]):
            arm=output/'arms'/arm_id
            if ordinal:arm.mkdir(parents=True,exist_ok=False)
            receipt=dict(**arm_contract(arm_id),ordinal=ordinal,status='active',errors=[],started_monotonic=time.monotonic(),
                finished_monotonic=None,training_seconds=None,inference_started_monotonic=None,
                inference_finished_monotonic=None,optimizer_discarded=False,baseline_restored=False,
                generation_rng_before=None,generation_rng_after=None,trace_complete=False)
            arms[arm_id]=receipt;write(arm/'arm-receipt.json',receipt)
            trainer=prepared[0] if ordinal==0 else None;budget=None
            try:
                require(time.time()<deadline and engine.inventory()==baseline,'independent arm must start at exact506 baseline')
                write(arm/'baseline-inventory.json',engine.inventory())
                training_start=time.monotonic()
                if ordinal==0:
                    trainer,rates,schedule=prepared;prepared=None
                else:
                    restore_rng(engine,common_rng);blocked=[]
                    with native_training.preparation_guard(engine.torch,blocked.append) as guard:
                        trainer=engine.trainer(material['texts'],material['rows'],arm)
                        rates,schedule=native_schedule(engine.dependency,trainer.args,plan['native_source_learning_rates'])
                        write(arm/'native-schedule.json',schedule);guard()
                    require(not blocked,'unaccounted native work during fresh arm Trainer preparation')
                before=model_metadata(engine.model);unchanged_model_layout(base_metadata,before,plan)
                write(arm/'training-before-metadata.json',before)
                budget=PrefixBudget(engine,trainer,material['rows'],rates,schedule,plan['native_source_learning_rates'],
                    arm,training_sources(plan,key),arm_id)
                # The combined training reservation never grows after saved work.
                # Both arms receive the same fixed inference window and no saved
                # training time is assigned to generation or verifier work.
                train_deadline,inference_cutoff=arm_phase_deadlines(plan,key,ordinal,deadline,time.time(),training_elapsed)
                try:
                    with telemetry.scope('training'),training_deadline(budget,train_deadline):
                        trainer.train();moments=budget.complete()
                finally:
                    duration=time.monotonic()-training_start;training_elapsed+=duration
                    receipt['training_seconds']=duration
                require(training_elapsed<=plan['maximum_training_seconds'],'combined192-update training reservation exceeded')
                write(arm/'optimizer-state.json',moments)
                trained=engine.inventory();require(native_training.changed_tensors(baseline,trained)>0,'adapted weights must change')
                write(arm/'trained-inventory.json',trained)
                after=model_metadata(engine.model);write(arm/'training-after-metadata.json',after)
                unchanged_model_layout(before,after,plan)
                discard_optimizer_state(engine.model,trainer,budget)
                require(optimizer_disposed(engine,trainer,budget),'no Adam or gradient state may enter inference')
                receipt['optimizer_discarded']=True
                native_epoch.inference_transition(engine,trainer,arm,bound,'trained')
                engine.torch.cuda.empty_cache();gc.collect()
                before_inference=model_metadata(engine.model);verify_model_metadata(before_inference,plan)
                write(arm/'model-before-metadata.json',before_inference);write(arm/'trained-before-inventory.json',engine.inventory())
                restore_rng(engine,common_rng);receipt['generation_rng_before']=rng_observation(capture_rng(engine))
                receipt['inference_started_monotonic']=time.monotonic()
                # Small host setup before solve_task would otherwise clip the
                # last window; the absolute worker cutoff remains authoritative.
                answers=evidence.solve_task(engine,root,plan,rank,inference_cutoff,telemetry,
                    observe_forwards=True,schedule='interleaved',directory=arm,arm_id=arm_id)
                receipt['inference_finished_monotonic']=time.monotonic()
                receipt['generation_rng_after']=rng_observation(capture_rng(engine))
                after_inference=model_metadata(engine.model);write(arm/'model-after-metadata.json',after_inference)
                write(arm/'trained-after-inventory.json',engine.inventory())
                require(engine.inventory()==trained and after_inference==before_inference,'inference mutated arm trained model')
                receipt['status']='complete'
            except BaseException as error:
                receipt['status']='failed';receipt['errors'].append(diagnostic(error,'e12-arm'));raise
            finally:
                reset_errors=[]
                def attempt(action,phase):
                    try:return action()
                    except BaseException as error:reset_errors.append(diagnostic(error,phase));return None
                if trainer is not None:attempt(lambda:discard_optimizer_state(engine.model,trainer,budget),'discard')
                receipt['optimizer_discarded']=optimizer_disposed(engine,trainer,budget)
                attempt(engine.restore,'restore')
                attempt(lambda:native_epoch.inference_transition(engine,trainer,arm,bound,'reset'),'reset-mode')
                restored=attempt(engine.inventory,'reset-inventory')
                if restored is not None:attempt(lambda:write(arm/'reset-inventory.json',restored),'reset-write')
                receipt['baseline_restored']=restored==baseline
                if budget is not None and not receipt['errors'] and not reset_errors and receipt['baseline_restored']:
                    trace=attempt(budget.finish,'prefix-finish');receipt['trace_complete']=trace is not None
                if reset_errors:receipt['errors'].extend(reset_errors);receipt['status']='failed'
                receipt['finished_monotonic']=time.monotonic();write(arm/'arm-receipt.json',receipt)
                # Drop Trainer references before a second preparation; keep only
                # the model and detached baseline, never a second NativeEngine.
                trainer=budget=None;gc.collect();engine.torch.cuda.empty_cache()
                require(receipt['status']=='complete' and receipt['optimizer_discarded'] and
                    receipt['baseline_restored'] and receipt['trace_complete'],'arm/reset failed; no next arm')
        short=_read(output/'arms/ttt64/prefix-trace.json');control=_read(output/'arms/ttt128/prefix-trace.json')
        first=_read(output/'arms/ttt64/prefix-contract.json');second=_read(output/'arms/ttt128/prefix-contract.json')
        require(first==second,'separate native arms must share complete preparation/sampler/RNG/LR contract')
        prefix.validate_pair(first,short,control)
    except BaseException as error:errors.append(diagnostic(error,'e12-prefix-worker'))
    finally:
        if engine is not None:
            def attempt(action,phase):
                try:return action()
                except BaseException as error:errors.append(diagnostic(error,phase));return None
            if trainer is not None:attempt(lambda:discard_optimizer_state(engine.model,trainer,budget),'terminal-discard')
            attempt(engine.restore,'terminal-restore');attempt(engine.inference,'terminal-inference')
            restored=attempt(engine.inventory,'terminal-inventory')
            if restored is not None:attempt(lambda:write(output/'final-reset-inventory.json',restored),'terminal-inventory-write')
            attempt(lambda:require(restored==baseline,'terminal baseline reset required'),'terminal-reset-check')
            reset=attempt(lambda:reset_control(adapters[0],engine.initial_control),'seventh-reset-control')
            if reset is not None:attempt(lambda:write(output/'post-reset-control.json',reset),'control-write')
            peak=attempt(engine.torch.cuda.max_memory_allocated,'cuda-memory')
            rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
            attempt(lambda:require(peak is not None and peak<=plan['maximum_worker_cuda_allocated_bytes'] and
                rss<=plan['maximum_worker_host_rss_bytes'],'worker memory ceiling exceeded'),'memory-check')
    value=dict(binding=bound,outcome='failed' if errors else 'complete',errors=errors,arms=arms,
        training_elapsed_seconds=training_elapsed,controls=verify_observations(observed),post_reset_control=reset,
        peak_host_rss_bytes=rss,peak_cuda_allocated_bytes=peak,telemetry=telemetry.snapshot(),
        native_model_instances=1 if engine is not None else 0,model_forwards_for_isolation=0,
        completed_training_updates=sum(arm_contract(a)['training_updates'] for a,r in arms.items() if r['trace_complete']),
        finished_epoch=time.time(),correctness_scored=False,promotion=False,total_cost_reduction=None)
    ok=terminal_attempt(value,lambda:write(output/'result.json',value),phase='e12-worker-result')
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


def verify_arm_training(root,plan,rank,arm_id):
    directory=Path(root)/'workers'/str(rank)/'arms'/arm_id
    read=lambda name:_read(directory/name)
    key=plan['task_order'][rank];spec=plan['task_specs'][key];limit=arm_contract(arm_id)['training_updates']
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
        'one independent optimizer and exact completed E12 prefix counters required')
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
    from tools import nvarc_e12_answer_evidence as evidence
    result=_read(directory/'result.json');bound=binding(plan,rank)
    fields={'binding','outcome','errors','arms','training_elapsed_seconds','controls','post_reset_control',
        'peak_host_rss_bytes','peak_cuda_allocated_bytes','telemetry','native_model_instances','model_forwards_for_isolation',
        'completed_training_updates','finished_epoch','correctness_scored','promotion','total_cost_reduction'}
    require(set(result)==fields and result['binding']==bound and result['outcome']=='complete' and result['errors']==[] and
        set(result['arms'])==set(ARMS) and result['completed_training_updates']==192 and
        type(result['native_model_instances']) is type(result['model_forwards_for_isolation']) is int and
        result['native_model_instances']==1 and result['model_forwards_for_isolation']==0 and
        result['correctness_scored'] is result['promotion'] is False and result['total_cost_reduction'] is None,
        'complete native E12 resident worker with192updates required')
    baseline=_read(directory/'baseline-inventory.json')
    require(_read(directory/'final-reset-inventory.json')==baseline,'terminal baseline must restore exactly')
    ready=_read(directory/'ready.json')
    require(ready==dict(rank=rank,uuid=uuid,model_material_digest=plan['model_material_digest'],
        baseline_digest=digest(baseline),torch=plan['runtime_torch_version'],
        initial_control_forwards={'control':6,'generation':0,'verification':0},binding=bound),
        'exact assigned-device initial6control proof required')
    verify_controls(directory,result,bound)
    verify_model_metadata(_read(directory/'baseline-model-metadata.json'),plan)
    contracts={};traces={};answers={};prefills={};generation_rng=None;previous=None;training_seconds=0.
    launch=_read(directory/'launch-reservation.json')
    require(launch['binding']==bound and launch['training_updates']==192 and launch['control_forwards']==7,
        'correct finite worker launch reservation required')
    require(type(result['finished_epoch']) in (float,int) and math.isfinite(result['finished_epoch']) and
        result['finished_epoch']<=launch['deadline_epoch'],'worker final reset/control/evidence must finish before absolute deadline')
    for ordinal,arm_id in enumerate(plan['arm_order'][key]):
        arm=directory/'arms'/arm_id;receipt=_read(arm/'arm-receipt.json')
        expected={'experiment','arm_id','training_updates','schedule','dfs_probability_floor','dfs_max_score','ordinal',
            'status','errors','started_monotonic','finished_monotonic','training_seconds','inference_started_monotonic',
            'inference_finished_monotonic','optimizer_discarded','baseline_restored','generation_rng_before',
            'generation_rng_after','trace_complete'}
        require(set(receipt)==expected and receipt==result['arms'][arm_id] and
            all(type(receipt[k]) is type(v) and receipt[k]==v for k,v in arm_contract(arm_id).items()) and
            type(receipt['ordinal']) is int and receipt['ordinal']==ordinal and receipt['status']=='complete' and
            receipt['errors']==[] and receipt['optimizer_discarded'] is receipt['baseline_restored'] is receipt['trace_complete'] is True and
            all(type(receipt[k]) in (float,int) and math.isfinite(receipt[k]) for k in ('started_monotonic','finished_monotonic',
                'training_seconds','inference_started_monotonic','inference_finished_monotonic')) and
            0<=receipt['started_monotonic']<=receipt['inference_started_monotonic']<=receipt['inference_finished_monotonic']<=receipt['finished_monotonic'] and
            receipt['training_seconds']>=0 and (previous is None or receipt['started_monotonic']>=previous),
            'strict sequential independent arm/reset completion receipt required')
        previous=receipt['finished_monotonic'];training_seconds+=receipt['training_seconds']
        prefix.validate_rng(receipt['generation_rng_before']);prefix.validate_rng(receipt['generation_rng_after'])
        require(generation_rng is None or generation_rng==receipt['generation_rng_before'],'same generationRNG per trained arm required')
        generation_rng=receipt['generation_rng_before']
        contracts[arm_id],traces[arm_id]=verify_arm_training(root,plan,rank,arm_id)
        unchanged_model_layout(_read(directory/'baseline-model-metadata.json'),_read(arm/'training-before-metadata.json'),plan)
        before=_read(arm/'model-before-metadata.json');after=_read(arm/'model-after-metadata.json')
        verify_model_metadata(before,plan);verify_model_metadata(after,plan)
        require(before==after and _read(arm/'trained-before-inventory.json')==_read(arm/'trained-after-inventory.json')==
            _read(arm/'trained-inventory.json'),'all905 metadata and506 trained bytes immutable during inference')
        allocations=_read(arm/'test-allocations.json')
        require(all(a['session_deadline_epoch']==launch['deadline_epoch']-180*(2-ordinal) for a in allocations.values()),
            'caller-owned fixed inference/reset cutoff required')
        answers[arm_id]=evidence.verify_task(root,plan,rank,directory=arm,schedule='interleaved',arm_id=arm_id,
            admitted_allocations=allocations)
        rows=evidence.read_events(arm/'inference-events.jsonl',answers[arm_id]['binding']);prefills[arm_id]={}
        for row in rows:
            if row['event']=='forward_reserved' and row['phase']=='generation':
                prefills[arm_id].setdefault(row['test_index'],dict(input_ids_digest=row['input_ids_digest'],
                    batch_shape=row['batch_shape'],cached=row['cached'],position_start=row['position_start']))
        require(set(prefills[arm_id])==set(range(plan['test_counts'][key])) and
            all(r['cached'] is False and r['position_start']==0 for r in prefills[arm_id].values()),
            'every actual test must start with fresh uncached prefill')
    require(contracts['ttt64']==contracts['ttt128'] and prefills['ttt64']==prefills['ttt128'],
        'independent reset runs must share exact128 source/sampler/RNG/LR and inference input prefix')
    prefix.validate_pair(contracts['ttt64'],traces['ttt64'],traces['ttt128'])
    require(result['training_elapsed_seconds']==training_seconds<=plan['maximum_training_seconds'],
        'combined192update training cap required')
    for field,cap in (('peak_host_rss_bytes',plan['maximum_worker_host_rss_bytes']),
            ('peak_cuda_allocated_bytes',plan['maximum_worker_cuda_allocated_bytes'])):
        require(type(result[field]) is int and 0<=result[field]<=cap,'observed memory within perworker reservation required')
    return dict(result,verified_inference=answers,prefix_verified=True)


def worker_deadline_monotonic(plan,started,spawned):
    profile_for_plan(plan)
    require(all(type(v) in (int,float) and math.isfinite(v) for v in (started,spawned)) and
        started<=spawned<started+plan['startup_seconds'],'worker launch must remain in original startup allowance')
    # A worker's resident-model load consumes the remaining shared startup
    # allowance. 3060 = full900 startup +1200 training +600 inference +360reset;
    # the outer3290 cutoff leaves its separate300-second finalizer reserve.
    return min(started+3290,spawned+plan['maximum_worker_seconds'])


def execute(root, dependency, started, *, runtime_api=None):
    if runtime_api is None:
        from tools import stage_nvarc_e12_prefix_probe as runtime_api
    from tools.nvarc_e12_cleanup import cleanup_workers
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('E12 coordinator stop requested')))
    cleanup_hook=functools.partial(cleanup_workers,deadline_monotonic=started+3299.8)
    verify_runtime, SCOPE = runtime_api.verify_runtime, runtime_api.SCOPE
    root = Path(root); plan = verify_runtime(root,require_approved=True)
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
                'training_updates':192,'control_forwards':7,'attempt':1,
                'test_count':plan['test_counts'][plan['task_order'][rank]]})
            worker_path = getattr(runtime_api,'WORKER_PATH','tools/nvarc_e10_end_to_end.py')
            command = [sys.executable,str(root/worker_path),'--root',str(root),'--dependency',str(dependency),
                '--model',str(model),'--rank',str(rank),'--deadline',str(deadline),'--parent-pid',str(os.getpid()),
                '--dependency-receipt-sha256',receipt_sha]
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
        require(sum(r['completed_training_updates'] for r in results.values())==768,'all4workers exact768completed updates required')
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
    require(plan['resource_budget_profile']==BUDGET_PROFILE,'exact60minute E12 stop receipt required')
    receipt=observation.get('e12_supervision',{});start=receipt.get('started_monotonic')
    finite=lambda value:type(value) in (int,float) and math.isfinite(value)
    require(finite(start) and start>=0 and receipt.get('format')=='irisx/e12-supervision-v1' and
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
        'exact E12 outer stop/capture/deadline receipt required')
    error_cleanup=False
    if receipt.get('failure_cleanup_started_monotonic') is not None:
        failure_start=receipt['failure_cleanup_started_monotonic']
        error_cleanup=(allow_observation_errors and receipt.get('supervisor_error_cleanup') is True and
            bool(receipt['errors']) and finite(failure_start) and
            start<=failure_start<=receipt['coordinator_stopped_monotonic'] and
            receipt.get('failure_cleanup_deadline_monotonic')==min(failure_start+10,start+3300) and
            receipt['coordinator_stopped_monotonic']<=receipt['failure_cleanup_deadline_monotonic'])
        require(error_cleanup,'exact bounded E12 supervision-error cleanup receipt required')
    for key,offset in (('term_requested_monotonic',3290),('kill_requested_monotonic',3299.8)):
        stamp=receipt.get(key)
        require(stamp is None or finite(stamp) and start<=stamp<=receipt['finished_monotonic'] and
            (stamp>=start+offset or key=='kill_requested_monotonic' and
                (receipt.get('orphaned_group_observed') is True or error_cleanup and
                    receipt['failure_cleanup_started_monotonic']<=stamp)),
            'E12 signal request timing differs')
    cleanup=terminal.get('cleanup',{})
    require(terminal.get('plan_digest')==digest(plan) and cleanup.get('format')=='irisx/e12-collective-cleanup-v1' and
        cleanup.get('deadline_monotonic')==start+3299.8 and
        cleanup.get('all_producers_stopped') is cleanup.get('complete_before_deadline') is True and
        cleanup.get('timed_out') is False and cleanup.get('secondary_errors')==[] and
        all(finite(cleanup.get(key)) for key in ('started_monotonic','finished_monotonic')) and
        start<=cleanup['started_monotonic']<=cleanup['finished_monotonic']<=start+3299.8 and
        cleanup['finished_monotonic']<=receipt['coordinator_stopped_monotonic'] and
        type(cleanup.get('workers')) is list and len(cleanup['workers'])<=4,
        'all owned E12 producers must stop within the exact shared cleanup deadline')
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
            'unique registered E12 cleanup worker required')
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
                launch['format']=='irisx/e12-owned-worker-launch-v1' and launch['binding']==native_epoch.binding(plan,int(worker['identity'])) and
                type(launch['pid']) is type(launch['process_group_id']) is int and
                launch['pid']==launch['process_group_id']==worker['pid'] and launch['start_new_session'] is True and
                finite(launch['started_monotonic']) and start<=launch['started_monotonic']<=cleanup['started_monotonic'],
                'cleanup PID/group must match the actual caller-owned launch receipt')
            pids.add(worker['pid'])
    return receipt



def record_worker_launch(root,plan,rank,process):
    profile_for_plan(plan)
    require(type(rank) is int and 0<=rank<4 and type(process.pid) is int and process.pid>1 and
        process.pid not in (os.getpid(),os.getpgrp()),'actual owned E12 worker launch required')
    write(Path(root)/'workers'/str(rank)/'process-launch.json',dict(format='irisx/e12-owned-worker-launch-v1',
        binding=binding(plan,rank),pid=process.pid,process_group_id=process.pid,started_monotonic=time.monotonic(),start_new_session=True))


def seal_outputs(root,plan,results,errors):
    from tools import nvarc_e12_answer_evidence as evidence
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
                    except BaseException as error:recovery_errors.append(diagnostic(error,'e12-committed-prefix-replay'))
            answers[key]=[];pools[key]=[];times[key]=[]
            for index in range(plan['test_counts'][key]):
                test=None if inference is None else inference['tests'][index]
                attempts=[] if test is None else test.get('attempts',[])
                answers[key].append(dict(attempt_1=attempts[0] if attempts else None,attempt_2=attempts[1] if len(attempts)>1 else None))
                pools[key].append([] if test is None else test.get('ranked_grids',[]))
                audit.append(dict(**arm_contract(arm),task_id=key,test_index=index,actual_candidates=len(attempts),
                    missing_attempts=2-len(attempts),output_qualified=bool(result and test and test.get('output_qualified')),
                    prefix_verified=result is not None,status='unavailable' if test is None else test['status'],
                    provenance='unqualified-committed-prefix' if recovered else 'verified-prefix-worker' if result else 'unavailable'))
                times[key].append(None if test is None else {k:test.get(k) for k in
                    ('started_epoch','finished_epoch','deadline_epoch','clock_overrun','coverage','termination_reason','telemetry')})
        values[arm+'-answers.json']=dict(format='irisx/exposed-calibration-answers-v1',tasks=answers,official_submission_ready=False)
        values[arm+'-audit.json']=audit;values[arm+'-candidate-pools.json']=dict(**arm_contract(arm),tasks=pools)
        coverage[arm]=dict(test_cases=6,actual_attempts=sum(r['actual_candidates'] for r in audit),
            missing_attempts=sum(r['missing_attempts'] for r in audit),qualified_test_cases=sum(r['output_qualified'] for r in audit),
            output_qualified=not errors and len(results)==4 and all(r['output_qualified'] for r in audit))
        audits[arm]=audit;timings[arm]=times
    summary=dict(format='irisx/e12-prefix-pilot-output-v1',run_id=RUN_ID,plan_digest=digest(plan),arm_order=plan['arm_order'],
        arm_contracts={a:arm_contract(a) for a in ARMS},per_arm=coverage,planned_training_updates=768,
        verified_completed_training_updates=sum(r['completed_training_updates'] for r in results.values()),
        actual_training_updates_all_workers=sum(r['completed_training_updates'] for r in results.values()) if len(results)==4 else None,
        planned_test_executions=12,paired_workers_verified=len(results),errors=errors,recovery_errors=recovery_errors,
        full_screen_feasibility_established=False,original_fullscreen_scope='24tasks/35tests x2arms x2repeats remains unexecuted',
        total_cost_reduction=None,quality_comparison_qualified=False,correctness_scored=False,promotion=False,
        official_submission_ready=False,base0_causal_claim=False)
    values.update({'paired-summary.json':summary,'paired-task-timings.json':timings})
    for value in values.values():reject_truth(value)
    store=GenerationStore(root,'e12-prefix-pilot',dict(run_id=RUN_ID,plan_digest=digest(plan),challenges_digest=plan['challenges_digest']))
    require(not (root/'output-commit.json').exists(),'single immutable E12 output publication required')
    manifest=store.publish(values,evidence_qualified=not errors and len(results)==4 and all(c['output_qualified'] for c in coverage.values()))
    store.read();return dict(manifest_digest=digest(manifest),**summary)


def finalize(root,observation,expected_plan_sha256):
    from tools.nvarc_e12_archive import finalize as close
    return close(root,observation,expected_plan_sha256)

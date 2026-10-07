"""INERT E11 paired p=.2/.1 orchestration from one retained native epoch.

The direct executable is deliberately disabled before orchestration imports.
CPU fake fixtures call the bounded producer and replay functions explicitly.
"""

if __name__ == '__main__':
    raise RuntimeError('INERT E11: no new exact runtime admission is implemented')

import argparse
import functools
import gc
import hashlib
import os
import signal
import math
from pathlib import Path
import sys
import time

from tools.nvarc_native_multitask import canonical,digest,require,write,allocation_deadlines
from tools.nvarc_native_submission import reject_truth
from tools.nvarc_output_lifecycle import diagnostic,GenerationStore
from tools import nvarc_e10_answer_evidence as evidence
from tools import nvarc_e10_end_to_end as native_epoch
from tools.nvarc_public_eval import PhaseTelemetry
from tools.nvarc_e10_paired_schedule import (capture_rng,restore_rng,rng_digests,
    model_metadata,verify_model_metadata as _verify_model_metadata,verify_rng_digests,_read)
from tools.nvarc_e11_dfs_contract import FORMAT,RUN_ID,RUN_ID_45,OWNER_RUN_ID,PROFILE,ALLOCATION,ARMS,arm_contract,validate_binding

TASK_COUNTS={'195c6913':2,'aa4ec2a5':1,'a47bf94d':1,'a25697e4':2}
TIMING=dict(generation_seconds=120,verification_reserve_seconds=30,per_test_seconds=150,
    startup_seconds=900,maximum_training_seconds=1200,inference_reserve_seconds=600,
    reset_reserve_seconds=180,finalization_reserve_seconds=600,maximum_worker_seconds=2880,
    maximum_notebook_wall_seconds=3600)
CAPS=dict(maximum_generation_forwards=49152,maximum_verification_forwards=1536,
    maximum_inference_input_tokens=62914560,maximum_processed_sequences_total=768)
PER_ARM_CAPS=dict(maximum_generation_forwards=24576,maximum_verification_forwards=768,
    maximum_inference_input_tokens=31457280,maximum_processed_sequences_total=384)
BUDGET_PROFILE='original-60min-blocked'
BUDGET_45='bounded-45min-inert'
OWNER_BUDGET_45='owner-editor-45min-v9'
RESOURCE_PROFILES={BUDGET_PROFILE:dict(run_id=RUN_ID,**TIMING),
    BUDGET_45:dict(TIMING,run_id=RUN_ID_45,maximum_training_seconds=600,
        finalization_reserve_seconds=300,maximum_worker_seconds=2280,maximum_notebook_wall_seconds=2700),
    OWNER_BUDGET_45:dict(TIMING,run_id=OWNER_RUN_ID,maximum_training_seconds=600,
        finalization_reserve_seconds=300,maximum_worker_seconds=2280,maximum_notebook_wall_seconds=2700)}
MODEL_LAYOUT=dict(parameter_count=905,buffer_count=0,
    digest='sha256:06a1ed5e10ce2c741cb661ba3e883952e3fbce3e0931ce151485b9ac4d31a479')
PROCESS_45=dict(term_seconds=2390,kill_seconds=2399.8,stop_seconds=2400,final_seconds=2700,
    worker_cleanup_deadline_seconds=2399.8,requires_owned_group_absence=True)


def counterbalanced_order(counts):
    require(canonical(counts)==canonical(TASK_COUNTS),'same four tasks and six tests required')
    result={}
    for count in (1,2):
        for position,key in enumerate(sorted(k for k,n in counts.items() if n==count)):
            result[key]=list(ARMS if position%2==0 else reversed(ARMS))
    return result


def budget_report(budget_profile=BUDGET_PROFILE):
    require(budget_profile in RESOURCE_PROFILES,'closed E11 resource profile required')
    short=budget_profile in (BUDGET_45,OWNER_BUDGET_45)
    return dict(budget_profile=budget_profile,phase_seconds=2580 if short else 3480,
        worker_phase_seconds=2280 if short else 2880,notebook_margin_seconds=120,
        parent_worker_cutoff_seconds=2400 if short else 3000,
        charged_gpu_seconds_ceiling=10800 if short else 14400,
        charged_gpu_hours_ceiling=3 if short else 4,paid_usd_ceiling=0,
        resource_qualification=False,remaining_free_hours_observed=3.8927411993,
        status='INERT_NOT_ADMITTED' if short else 'BLOCKED_NOT_ADMITTED',
        feasibility=('distinct planned cutoff; finalization not worst-case certified; fresh quota/review/admission required'
            if short else '60-minute original proposal exceeds observed free quota; no new resource admission'))


def profile_for_plan(plan):
    selected=RESOURCE_PROFILES.get(plan.get('resource_budget_profile'))
    require(selected is not None,'closed E11 resource profile required')
    timing={k:v for k,v in selected.items() if k!='run_id'}
    require(plan.get('format')==FORMAT and plan.get('run_id')==plan.get('screen_id')==selected['run_id'] and
        plan.get('generation_budget_profile')==PROFILE and
        plan.get('forward_observer_required') is True and
        canonical(plan.get('retained_model_layout'))==canonical(MODEL_LAYOUT) and
        canonical(plan.get('e11_process_policy'))==canonical(PROCESS_45 if plan['resource_budget_profile'] in (BUDGET_45,OWNER_BUDGET_45) else None) and
        plan.get('cleanup_reserve_seconds')==(310 if plan['resource_budget_profile'] in (BUDGET_45,OWNER_BUDGET_45) else 600) and
        canonical(plan.get('test_counts'))==canonical(TASK_COUNTS) and
        plan.get('task_order')==list(TASK_COUNTS) and
        canonical(plan.get('arm_order'))==canonical(counterbalanced_order(TASK_COUNTS)) and
        plan.get('arm_order_rule')=='sorted public task IDs; alternate within one-test and two-test task strata' and
        canonical(plan.get('arm_contracts'))==canonical({a:arm_contract(a) for a in ARMS}) and
        plan.get('verification_schedule')=='interleaved' and plan.get('verification_schedules')==['interleaved'] and
        canonical(plan.get('per_arm_caps'))==canonical(PER_ARM_CAPS) and
        all(type(plan.get(k)) is int and plan[k]==v for k,v in {**timing,**CAPS}.items()) and
        type(plan.get('expected_notebook_version')) is int and plan['expected_notebook_version']==9 and
        type(plan.get('expected_previous_version')) is int and plan['expected_previous_version']==8 and
        type(plan.get('expected_previous_script_version_id')) is int and plan['expected_previous_script_version_id']==356039440,
        'exact E11 p02/p01 factor, interleaved schedule, identity, order and resource profile required')
    require(all(type(plan.get(key)) is int and plan[key]==value for key,value in
        (('maximum_training_forwards',512),('maximum_training_backwards',512),('optimizer_steps',512),('per_worker_training_steps',128))),
        'E11 shares one complete epoch per task, exactly 512 updates total')
    return dict(profile_id=PROFILE,run_id=selected['run_id'],forward_observer_required=True,**timing)



def verify_model_metadata(value,plan):
    _verify_model_metadata(value,plan)
    projection={kind:[{k:row[k] for k in ('name','dtype','device','shape','requires_grad')}
        for row in value[kind]] for kind in ('parameters','buffers')}
    require(len(value['parameters'])==MODEL_LAYOUT['parameter_count'] and
        len(value['buffers'])==MODEL_LAYOUT['buffer_count'] and digest(projection)==MODEL_LAYOUT['digest'],
        'complete fixed 905-parameter and zero-buffer E11 retained model layout required')


def paired_allocation(bound,index,start,deadline):
    validate_binding(bound)
    value=dict(format=ALLOCATION,binding=dict(bound),test_index=index,started_epoch=start,
        session_deadline_epoch=deadline,generation_seconds=120,total_seconds=150,verification_reserve_seconds=30)
    allocation_deadlines(value,bound,index)
    return value


def solve_pair(engine,root,plan,rank,deadline,telemetry,*,observe_forwards=False):
    profile_for_plan(plan);require(observe_forwards,'paired arms require forward observations')
    root=Path(root);directory=root/'workers'/str(rank);key=plan['task_order'][rank]
    bound=native_epoch.binding(plan,rank);trained=engine.inventory();state=capture_rng(engine)
    require(trained==_read(directory/'trained-inventory.json'), 'retained trained state differs before paired entry')
    original=rng_digests(state);arms={};receipts={}
    record=dict(format='irisx/dfs-floor-paired-task-inference-v1',binding=bound,arm_order=plan['arm_order'][key],
        trained_inventory_digest=digest(trained),rng_start_digests=original,rng_restored_after_pair=False,
        arms=arms,arm_receipts=receipts,errors=[],paired_state_verified=False,
        finished_epoch=None,clock_overrun=None,
        model_forwards_for_isolation=0,correctness_scored=False,promotion=False)
    def checkpoint():write(directory/'answer-checkpoint.json',record)
    checkpoint()
    try:
        for ordinal,arm_id in enumerate(record['arm_order']):
            require(time.time()<deadline,'paired absolute inference/reset cutoff exhausted')
            arm=directory/'arms'/arm_id;arm.mkdir(parents=True,exist_ok=False)
            started=time.monotonic()
            # The retained model is the trained state. Hash every saved tensor;
            # never retrain or silently restore changed trained tensors.
            before=engine.inventory();require(before==trained,'trained state changed before DFS floor arm')
            before_metadata=model_metadata(engine.model)
            verify_model_metadata(before_metadata,plan)
            restore_rng(engine,state);before_rng=rng_digests(capture_rng(engine))
            require(before_rng==original,'all RNG streams must match before each arm')
            write(arm/'trained-before-inventory.json',before)
            write(arm/'model-before-metadata.json',before_metadata)
            receipt=dict(**arm_contract(arm_id),ordinal=ordinal,started_monotonic=started,started_epoch=time.time(),
                finished_monotonic=None,finished_epoch=None,clock_overrun=None,
                before_inventory_digest=digest(before),after_inventory_digest=None,
                rng_before_digests=before_rng,rng_after_digests=None,model_identity_preserved=False,
                model_before_metadata_digest=digest(before_metadata),model_after_metadata_digest=None,
                no_extra_model_forwards=True,fresh_adapter=False,fresh_caches=False,
                absolute_inference_cutoff_epoch=deadline,status='active',errors=[])
            receipts[arm_id]=receipt;write(arm/'arm-receipt.json',receipt);checkpoint()
            model=engine.model
            try:
                # New AnswerModel + observer + per-arm counters/caches. DFS cache
                # objects remain call-local and no second NativeEngine is made.
                arm_telemetry=PhaseTelemetry()
                arms[arm_id]=evidence.solve_task(engine,root,plan,rank,deadline,arm_telemetry,
                    observe_forwards=True,schedule='interleaved',arm_id=arm_id,directory=arm)
                after=engine.inventory();write(arm/'trained-after-inventory.json',after)
                after_metadata=model_metadata(engine.model);write(arm/'model-after-metadata.json',after_metadata)
                entry=_read(arm/'adapter-entry.json')
                fresh=canonical(entry)==canonical(dict(constructor='tools.nvarc_e10_answer_evidence.AnswerModel',
                    reserved={'control':0,'generation':0,'verification':0},completed={'control':0,'generation':0,'verification':0},
                    input_tokens=0,observed_verifications=0,verification_rows=None,active=None,observer_rows=0))
                ledger=evidence.read_events(arm/'inference-events.jsonl',arms[arm_id]['binding']);first={}
                for row in ledger:
                    if row['event']=='forward_reserved' and row['phase']=='generation':first.setdefault(row['test_index'],row)
                receipt.update(after_inventory_digest=digest(after),rng_after_digests=rng_digests(capture_rng(engine)),
                    model_identity_preserved=engine.model is model,model_after_metadata_digest=digest(after_metadata),
                    fresh_adapter=fresh,fresh_caches=all(row['cached'] is False and row['position_start']==0 for row in first.values()))
                require(after==trained and before_metadata==after_metadata and receipt['model_identity_preserved'] and
                    receipt['fresh_adapter'] and receipt['fresh_caches'],
                    'DFS floor arm mutated retained trained state/model identity')
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
        record['errors'].append(diagnostic(error,'paired-dfs-floor'));raise
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
    require(set(record)==expected and record['format']=='irisx/dfs-floor-paired-task-inference-v1' and
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
    sources={};prefills={};previous=None;retained_metadata=None
    for ordinal,arm_id in enumerate(record['arm_order']):
        arm=directory/'arms'/arm_id;receipt=_read(arm/'arm-receipt.json')
        require(receipt==record['arm_receipts'][arm_id] and set(receipt)=={
            'experiment','arm_id','schedule','dfs_probability_floor','dfs_max_score','ordinal','started_monotonic','finished_monotonic','started_epoch','finished_epoch','clock_overrun','before_inventory_digest',
            'after_inventory_digest','rng_before_digests','rng_after_digests','model_identity_preserved',
            'model_before_metadata_digest','model_after_metadata_digest','errors',
            'no_extra_model_forwards','fresh_adapter','fresh_caches','absolute_inference_cutoff_epoch','status'} and
            all(type(receipt[k]) is type(v) and receipt[k]==v for k,v in arm_contract(arm_id).items()) and type(receipt['ordinal']) is int and receipt['ordinal']==ordinal and
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
        require(record['arms'][arm_id]==evidence.verify_task(root,plan,rank,schedule='interleaved',arm_id=arm_id,
            directory=arm,admitted_allocations=allocations),'paired arm checkpoint differs')
        events=evidence.read_events(arm/'inference-events.jsonl',record['arms'][arm_id]['binding'])
        sources[arm_id]={e['test_index']:{k:e[k] for k in ('base_key','source_views','source_input_digests')}
            for e in events if e['event']=='test_started'}
        prefills[arm_id]={(e['test_index'],e['batch_index']):
            (e['source_views'],e['prefix_digests']) for e in events if e['event']=='generation_reserved'}
        for index in sources[arm_id]:
            first=next((e for e in events if e['event']=='forward_reserved' and e['phase']=='generation' and e['test_index']==index),None)
            require(first is None or first['cached'] is False and first['position_start']==0,
                'each arm/test must start with an uncached source prefill')
    shared=set(sources[ARMS[0]])&set(sources[ARMS[1]])
    require(all(sources[ARMS[0]][i]==sources[ARMS[1]][i] for i in shared),
        'paired formatter/base-key/augmentation/input digests differ')
    common_prefills=set(prefills[ARMS[0]])&set(prefills[ARMS[1]])
    require(all(prefills[ARMS[0]][i]==prefills[ARMS[1]][i] for i in common_prefills),
        'corresponding shared source batch prefills differ')
    return record


def verify_worker_result(root,plan,rank,uuid):
    return native_epoch.verify_worker_result(root,plan,rank,uuid,verify_inference=verify_pair)


def seal_outputs(root,plan,results,errors):
    """One atomic envelope, separate per-arm answers/audits and missing slots."""
    values={};coverage={};timings={};audits={};recovery_errors=[]
    for arm_id in ARMS:
        answers={};audit=[];pools={};stamps={}
        for rank,key in enumerate(plan['task_order']):
            result=results.get(str(rank));pair=None if result is None else result['inference']
            arm=None if pair is None else pair['arms'].get(arm_id)
            recovered=False
            if arm is None:
                directory=Path(root)/'workers'/str(rank)/'arms'/arm_id
                if (directory/'test-allocations.json').is_file():
                    try:
                        arm=evidence.recover_completed_tests(root,plan,rank,schedule='interleaved',arm_id=arm_id,
                            directory=directory,admitted_allocations=_read(directory/'test-allocations.json'))
                        recovered=arm is not None
                    except BaseException as error:
                        recovery_errors.append(dict(rank=rank,schedule='interleaved',arm_id=arm_id,**diagnostic(error,'paired-prefix-recovery')))
            answers[key]=[];pools[key]=[];stamps[key]=[]
            for index in range(plan['test_counts'][key]):
                test=None if arm is None else arm['tests'][index];attempts=[] if test is None else test.get('attempts',[])
                answers[key].append({'attempt_1':attempts[0] if attempts else None,
                    'attempt_2':attempts[1] if len(attempts)>1 else None})
                pools[key].append([] if test is None else test.get('ranked_grids',[]))
                audit.append(dict(**arm_contract(arm_id),task_id=key,test_index=index,actual_candidates=len(attempts),
                    missing_attempts=2-len(attempts),output_qualified=bool(result and test and test.get('output_qualified')),
                    status='no_verified_worker' if test is None else test['status'],paired_state_verified=pair is not None,
                    started=bool(test and test.get('started_epoch') is not None),
                    provenance='unqualified-committed-prefix' if recovered else 'verified-paired-worker' if pair else 'unavailable',
                    test_digest=None if test is None else digest(test)))
                stamps[key].append(None if test is None else {k:test.get(k) for k in
                    ('started_epoch','finished_epoch','deadline_epoch','clock_overrun','coverage','termination_reason','telemetry')})
        values[arm_id+'-answers.json']=dict(format='irisx/exposed-calibration-answers-v1',tasks=answers,official_submission_ready=False)
        values[arm_id+'-audit.json']=audit;values[arm_id+'-candidate-pools.json']=dict(**arm_contract(arm_id),tasks=pools)
        coverage[arm_id]=dict(test_cases=6,actual_attempts=sum(r['actual_candidates'] for r in audit),
            missing_attempts=sum(r['missing_attempts'] for r in audit),qualified_test_cases=sum(r['output_qualified'] for r in audit),
            output_qualified=not errors and len(results)==4 and all(r['output_qualified'] for r in audit))
        timings[arm_id]=stamps;audits[arm_id]=audit
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
    summary=dict(format='irisx/paired-dfs-floor-output-v1',run_id=plan['run_id'],plan_digest=digest(plan),
        arm_order=plan['arm_order'],arm_contracts={a:arm_contract(a) for a in ARMS},per_arm=coverage,planned_test_executions=12,planned_training_updates=512,
        verified_completed_training_updates=observed_updates,
        actual_training_updates_all_workers=observed_updates if len(results)==4 else None,
        recovered_or_verified_started_tests=sum(row['started'] for audit in audits.values() for row in audit),
        paired_slots=slots,paired_workers_verified=len(results),unverified_workers=4-len(results),
        errors=errors,recovery_errors=recovery_errors,correctness_scored=False,promotion=False,
        official_submission_ready=False,quality_comparison_qualified=False,
        missing_slot_semantics='no independently verified sealed attempt; interrupted arm evidence remains archived')
    values.update({'paired-summary.json':summary,'paired-task-timings.json':timings})
    for value in values.values():reject_truth(value)
    store=GenerationStore(root,'paired-dfs-floor',{'run_id':plan['run_id'],'plan_digest':digest(plan),
        'challenges_digest':plan['challenges_digest']})
    require(not (Path(root)/'output-commit.json').exists(),'one immutable paired output generation only')
    manifest=store.publish(values,evidence_qualified=not errors and len(results)==4 and
        all(item['output_qualified'] for item in coverage.values()));store.read()
    return dict(manifest_digest=digest(manifest),**summary)



def worker(root,dependency,model,rank,deadline,parent_pid,dependency_receipt_sha256=None,*,runtime_api=None):
    if runtime_api is None:
        from tools import stage_nvarc_e11_paired_floor as runtime_api
    plan=runtime_api.verify_runtime(root,require_approved=True)
    return native_epoch.run_worker(root,dependency,model,rank,deadline,parent_pid,
        dependency_receipt_sha256,plan,solve=solve_pair)


def record_worker_launch(root,plan,rank,process):
    profile_for_plan(plan)
    require(type(rank) is int and 0<=rank<4 and type(process.pid) is int and process.pid>1 and process.pid!=os.getpid() and process.pid!=os.getpgrp(),
        'actual owned E11 worker process launch required')
    write(Path(root)/'workers'/str(rank)/'process-launch.json',
        dict(format='irisx/e11-owned-worker-launch-v1',binding=native_epoch.binding(plan,rank),
            pid=process.pid,process_group_id=process.pid,started_monotonic=time.monotonic(),
            start_new_session=True))


def execute(root,dependency,started,*,runtime_api=None):
    if runtime_api is None:
        from tools import stage_nvarc_e11_paired_floor as runtime_api
    api=runtime_api
    plan=api.verify_runtime(root,require_approved=True)
    # Catch outer TERM before execute so the finally block collectively stops
    # every separately registered producer group. No model call is added.
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('E11 coordinator stop requested')))
    hook=None
    if plan['resource_budget_profile'] in (BUDGET_45,OWNER_BUDGET_45):
        from tools.nvarc_e11_cleanup import cleanup_workers
        hook=functools.partial(cleanup_workers,deadline_monotonic=started+2399.8)
    return native_epoch.execute(root,dependency,started,runtime_api=api,cleanup_hook=hook)


def validate_stop_receipts(observation,terminal,plan,root,*,allow_observation_errors=False):
    """Recompute the exact 45-minute caller policy, never trust a success flag."""
    require(plan['resource_budget_profile'] in (BUDGET_45,OWNER_BUDGET_45),'45-minute E11 stop receipt required')
    receipt=observation.get('e11_supervision',{});start=receipt.get('started_monotonic')
    finite=lambda value:type(value) in (int,float) and math.isfinite(value)
    require(finite(start) and start>=0 and receipt.get('format')=='irisx/e11-supervision-v1' and
        all(finite(receipt.get(key)) and receipt[key]==start+offset for key,offset in (
            ('term_deadline_monotonic',2390),('kill_deadline_monotonic',2399.8),
            ('stop_deadline_monotonic',2400),('finalizer_deadline_monotonic',2700))) and
        observation.get('hard_deadline_monotonic')==start+2700 and
        observation.get('confirmed_stopped') is True and
        type(receipt.get('errors')) is list and
        (receipt['errors']==[] or allow_observation_errors) and
        observation.get('reserve_preserved') is receipt.get('reserve_preserved') is (not bool(receipt['errors'])) and
        observation.get('launched') is True and type(observation.get('returncode')) is int and
        receipt.get('coordinator_group_absent') is True and
        all(finite(receipt.get(key)) for key in ('coordinator_stopped_monotonic','capture_finished_monotonic','finished_monotonic')) and
        start<=receipt['coordinator_stopped_monotonic']<=receipt['capture_finished_monotonic']<=receipt['finished_monotonic']<=start+2400 and
        receipt.get('finalization_remaining_seconds')==start+2700-receipt['finished_monotonic'] and
        observation.get('output_capture',{}).get('written') is True,
        'exact E11 outer stop/capture/deadline receipt required')
    error_cleanup=False
    if receipt.get('failure_cleanup_started_monotonic') is not None:
        failure_start=receipt['failure_cleanup_started_monotonic']
        error_cleanup=(allow_observation_errors and receipt.get('supervisor_error_cleanup') is True and
            bool(receipt['errors']) and finite(failure_start) and
            start<=failure_start<=receipt['coordinator_stopped_monotonic'] and
            receipt.get('failure_cleanup_deadline_monotonic')==min(failure_start+10,start+2400) and
            receipt['coordinator_stopped_monotonic']<=receipt['failure_cleanup_deadline_monotonic'])
        require(error_cleanup,'exact bounded E11 supervision-error cleanup receipt required')
    for key,offset in (('term_requested_monotonic',2390),('kill_requested_monotonic',2399.8)):
        stamp=receipt.get(key)
        require(stamp is None or finite(stamp) and start<=stamp<=receipt['finished_monotonic'] and
            (stamp>=start+offset or key=='kill_requested_monotonic' and
                (receipt.get('orphaned_group_observed') is True or error_cleanup and
                    receipt['failure_cleanup_started_monotonic']<=stamp)),
            'E11 signal request timing differs')
    cleanup=terminal.get('cleanup',{})
    require(terminal.get('plan_digest')==digest(plan) and cleanup.get('format')=='irisx/e11-collective-cleanup-v1' and
        cleanup.get('deadline_monotonic')==start+2399.8 and
        cleanup.get('all_producers_stopped') is cleanup.get('complete_before_deadline') is True and
        cleanup.get('timed_out') is False and cleanup.get('secondary_errors')==[] and
        all(finite(cleanup.get(key)) for key in ('started_monotonic','finished_monotonic')) and
        start<=cleanup['started_monotonic']<=cleanup['finished_monotonic']<=start+2399.8 and
        cleanup['finished_monotonic']<=receipt['coordinator_stopped_monotonic'] and
        type(cleanup.get('workers')) is list and len(cleanup['workers'])<=4,
        'all owned E11 producers must stop within the exact shared cleanup deadline')
    root=Path(root);worker_root=root/'workers'
    registered={path.name for path in worker_root.iterdir() if path.is_dir()} if worker_root.exists() else set()
    require(all(name in ('0','1','2','3') for name in registered) and
        {row.get('identity') for row in cleanup['workers']}==registered,
        'every registered worker directory requires its cleanup receipt')
    identities=set();pids=set()
    for worker in cleanup['workers']:
        require(worker.get('identity') in ('0','1','2','3') and worker['identity'] not in identities,
            'unique registered E11 cleanup worker required')
        identities.add(worker['identity'])
        launch_path=worker_root/worker['identity']/'process-launch.json'
        if worker.get('pid') is None:
            require(worker.get('stop_attempted') is False and not launch_path.exists(),
                'unlaunched worker cannot claim signal or omit its recorded PID')
        else:
            require(type(worker['pid']) is int and worker['pid']>1 and worker['pid'] not in pids and
                worker.get('stop_attempted') is worker.get('group_absent') is worker.get('stop_confirmed') is True and
                type(worker.get('returncode')) is int and finite(worker.get('kill_requested_monotonic')) and
                finite(worker.get('stop_confirmed_monotonic')) and
                cleanup['started_monotonic']<=worker['kill_requested_monotonic']<=worker['stop_confirmed_monotonic']<=cleanup['finished_monotonic'],
                'actual owned worker group absence and ordered kill/stop observations required')
            launch=_read(launch_path)
            require(set(launch)=={'format','binding','pid','process_group_id','started_monotonic','start_new_session'} and
                launch['format']=='irisx/e11-owned-worker-launch-v1' and launch['binding']==native_epoch.binding(plan,int(worker['identity'])) and
                type(launch['pid']) is type(launch['process_group_id']) is int and
                launch['pid']==launch['process_group_id']==worker['pid'] and launch['start_new_session'] is True and
                finite(launch['started_monotonic']) and start<=launch['started_monotonic']<=cleanup['started_monotonic'],
                'cleanup PID/group must match the actual caller-owned launch receipt')
            pids.add(worker['pid'])
    return receipt


def prepare_supervision_diagnostic(root,observation,plan,*,no_launch=False):
    """Retain a diagnostic ZIP only after independently checked stop evidence."""
    receipt=observation.get('e11_supervision',{});start=receipt.get('started_monotonic')
    finite=lambda value:type(value) in (int,float) and math.isfinite(value)
    require(plan['resource_budget_profile'] in (BUDGET_45,OWNER_BUDGET_45) and finite(start) and start>=0 and
        all(finite(receipt.get(key)) and receipt[key]==start+offset for key,offset in (
            ('term_deadline_monotonic',2390),('kill_deadline_monotonic',2399.8),
            ('stop_deadline_monotonic',2400),('finalizer_deadline_monotonic',2700))) and
        observation.get('hard_deadline_monotonic')==start+2700 and observation.get('confirmed_stopped') is True and
        observation.get('output_capture',{}).get('written') is True and
        finite(receipt.get('capture_finished_monotonic')) and finite(receipt.get('finished_monotonic')) and
        start<=receipt['capture_finished_monotonic']<=receipt['finished_monotonic']<=start+2400 and
        type(receipt.get('errors')) is list and bool(receipt['errors']),
        'bounded exact stopped supervision failure and finalized capture required')
    if no_launch:
        require(observation.get('launched') is False and observation.get('launch_failed') is True and
            observation.get('returncode') is None and
            not (root/'coordinator-admitted.json').exists() and not (root/'workers').exists(),
            'diagnostic prelaunch failure cannot hide any admitted coordinator or worker')
        native_epoch._write_new(root/native_epoch.FAILURE_FILE,dict(
            format='irisx/ttt-probe-entry-failure-v1',run_id=plan['run_id'],type='CoordinatorLaunchFailure',
            message='Outer supervisor could not create its coordinator process',
            errors=receipt['errors'],correctness_scored=False,promotion=False))
    native_epoch._write_new(root/'diagnostic-only.json',dict(format='irisx/e11-supervision-diagnostic-v1',
        plan_digest=digest(plan),complete_runtime_evidence=False,native_execution_qualified=False,
        supervision_errors=receipt['errors'],correctness_scored=False,promotion=False))


def finalize(root,observation,expected_plan_sha256):
    """Retain actual closure timings separately from the closed archive bytes."""
    root=Path(root)
    receipt=dict(format='irisx/e11-finalization-timing-v1',plan_sha256=expected_plan_sha256,
        stages={},hard_deadline_monotonic=observation.get('hard_deadline_monotonic'),
        finalization_qualified=False,receipt_written=False,correctness_scored=False,promotion=False)
    hard=receipt['hard_deadline_monotonic'];observation_retained=False
    def observe(stage):
        stamp=time.monotonic()
        receipt['stages'][stage]=dict(monotonic=stamp,remaining_seconds=hard-stamp)
    result=dict(final_archive_created=False,diagnostic_only_archive_created=False,
        existing_archive_preserved=(root.parent/(root.name+'.zip')).exists(),
        diagnostic_errors=[],coordinator_diagnostic_excerpt='')
    try:
        raw=(root/'plan.json').read_bytes()
        require(hashlib.sha256(raw).hexdigest()==expected_plan_sha256,'exact E11 finalization plan required')
        plan=_read(root/'plan.json');profile_for_plan(plan)
        require(type(hard) in (int,float) and math.isfinite(hard),'absolute finalization cutoff required')
        if plan['resource_budget_profile']==OWNER_BUDGET_45:
            from tools.nvarc_e11_owner_editor import verify_confirmation
            confirmation=verify_confirmation(root,plan,current=False)
            require(confirmation['started_monotonic']==observation.get('e11_supervision',{}).get('started_monotonic'),
                'owner config and outer supervisor must bind the same notebook start')
        if plan['resource_budget_profile'] in (BUDGET_45,OWNER_BUDGET_45):
            reject_truth(observation)
            require(len(canonical(observation))<=16*1024 and time.monotonic()<hard,
                'bounded raw E11 supervisor observation inside finalizer deadline required')
            native_epoch._write_new(root/'e11-supervision-observation.json',observation)
            observation_retained=True
        supervision_diagnostic=False
        if plan['resource_budget_profile'] in (BUDGET_45,OWNER_BUDGET_45):
            no_launch=observation.get('launch_failed') is True and observation.get('launched') is False
            if no_launch:
                prepare_supervision_diagnostic(root,observation,plan,no_launch=True)
                supervision_diagnostic=True
            else:
                terminal=_read(root/'terminal.json') if (root/'terminal.json').is_file() else _read(root/'terminal-fallback.json')
                supervision_diagnostic=bool(observation.get('e11_supervision',{}).get('errors'))
                validate_stop_receipts(observation,terminal,plan,root,allow_observation_errors=supervision_diagnostic)
                if supervision_diagnostic:prepare_supervision_diagnostic(root,observation,plan)
        result=native_epoch.finalize(root,observation,expected_plan_sha256,stage_observer=observe)
        observe('finalizer_returned')
        if supervision_diagnostic and result['final_archive_created']:
            result['final_archive_created']=False;result['diagnostic_only_archive_created']=True
        receipt['finalization_qualified']=result['final_archive_created'] and time.monotonic()<hard
    except BaseException as error:
        result['diagnostic_errors'].append(type(error).__name__+': '+str(error)[:1000])
    # An after-close timing receipt cannot be written into that already closed
    # archive. Keep this separate, bound to its immutable plan and ZIP digest.
    destination=root.parent/(root.name+'.zip')
    receipt.update(archive_exists=False,archive_size=None,archive_sha256=None)
    try:
        receipt['archive_exists']=destination.exists()
        receipt['archive_size']=destination.stat().st_size if destination.exists() else None
        created=result['final_archive_created'] or result['diagnostic_only_archive_created']
        if created and destination.exists() and type(hard) in (int,float):
            hasher=hashlib.sha256()
            with destination.open('rb') as stream:
                while block:=stream.read(1024*1024):
                    if time.monotonic()>=hard:
                        receipt['finalization_qualified']=False;break
                    hasher.update(block)
                else:receipt['archive_sha256']=hasher.hexdigest()
        if not result['existing_archive_preserved'] and type(hard) in (int,float) and time.monotonic()<hard:
            # The immutable sidecar stays unqualified until its write returns.
            native_epoch._write_new(root.parent/(root.name+'-finalization-receipt.json'),
                dict(receipt,finalization_qualified=False))
            receipt['receipt_written']=True
            receipt['receipt_write_finished_monotonic']=time.monotonic()
    except BaseException as error:
        receipt['finalization_qualified']=False
        result['diagnostic_errors'].append('finalization receipt: '+type(error).__name__+': '+str(error)[:1000])
    receipt['finalization_qualified']=bool(receipt['finalization_qualified'] and receipt['receipt_written'] and
        receipt['archive_sha256'] is not None and type(hard) in (int,float) and time.monotonic()<hard)
    result['finalization_qualified']=receipt['finalization_qualified']
    result['finalization_timing']=receipt
    result['supervision_observation_retained']=observation_retained
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','dependency','model'):parser.add_argument('--'+name,type=Path,required=name!='model')
    parser.add_argument('--rank',type=int);parser.add_argument('--deadline',type=float);parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--dependency-receipt-sha256');parser.add_argument('--started',type=float)
    parser.add_argument('--owner-pid',type=int);parser.add_argument('--bootstrap',action='store_true');args=parser.parse_args()
    from tools.stage_nvarc_e11_paired_floor import verify_runtime
    verify_runtime(args.root,require_approved=True)
    require(os.environ.get('PYTHONHASHSEED')=='0' and sys.flags.hash_randomization==0,'fresh hashseed-zero process required')
    if args.rank is not None:return worker(args.root,args.dependency,args.model,args.rank,args.deadline,args.parent_pid,args.dependency_receipt_sha256)
    from tools.nvarc_public_eval import install_owner_guard
    install_owner_guard(args.owner_pid,signal.SIGTERM)
    return execute(args.root,args.dependency,args.started)

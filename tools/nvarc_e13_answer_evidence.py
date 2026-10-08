"""E13 paired-search native answer production and CPU evidence checks; never read truth.

The existing source DFS, augmentation, inverse transforms and score_kgmon run
unchanged. Retained NLL receipts bind the real padded verifier inputs. This is
resource/output evidence, not an independent numerical replay or ARC score.
"""
from __future__ import annotations

import math
from pathlib import Path
import time

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import Events, canonical, digest, require, solve_test as native_solve_test, write
from tools.nvarc_native_solve_runtime import grid_key, HostForwardObserver
from tools.nvarc_native_submission import reject_truth
from tools.nvarc_output_lifecycle import diagnostic
from tools.nvarc_public_eval_runtime import LightModel

PHASES = ('generation', 'verification')
PER_TEST = {'generation':4096, 'verification':128, 'input_tokens':5242880}
MAX_LEDGER_BYTES = 8*1024**2
MAX_EVENT_BYTES = 1024**2
EVENT_FIELDS={
    'test_allocation':{'started_epoch','generation_deadline','verification_deadline'},
    'test_started':{'base_key','source_views','source_input_digests'},
    'generation_reserved':{'batch_index','source_views','prefix_digests'},
    'generation_completed':{'batch_index','raw_returned','returned_rows','returned_prefix','coverage',
        'source_clock_summary','source_end_time'},
    'forward_reserved':{'call_id','phase','batch_shape','physical_input_tokens','cached',
        'position_start','position_end','input_ids_digest'},
    'forward_completed':{'call_id','phase','output_contract'},
    'verification_observed':{'call_id','rows'},
    'candidate_invalid':{'source_view','source_tokens'},
    'candidate_parsed':{'source_view','source_tokens','candidate_grid','beam_score','already_verified'},
    'candidate_ranked':{'source_view','source_tokens','candidate_grid','beam_score','score_aug','verification_call_ids'},
    'test_terminal':{'result'},'test_committed':{'result'}}


def for_plan(plan, arm_id=None):
    """Recognize only E13; never change the frozen E10/E11 profile gates."""
    require(type(plan) is dict, 'exact E13 inference plan required')
    from tools.nvarc_e13_runtime import profile_for_plan, arm_contract
    profile = profile_for_plan(plan)
    if arm_id is not None:
        contract = arm_contract(arm_id)
        profile.update(generation_seconds=contract['generation_seconds'],
            per_test_seconds=contract['per_test_seconds'])
    return profile


def task_binding(plan, challenges, rank, *, schedule=None, arm_id=None):
    from tools.nvarc_e13_runtime import arm_contract, validate_binding
    for_plan(plan)
    require(schedule == 'interleaved', 'E13 binding requires interleaved verification')
    require(type(rank) is int and 0 <= rank < len(plan['task_order']),
        'exact E13 task rank required')
    key = plan['task_order'][rank]
    require(digest(challenges) == plan['challenges_digest'] and
        len(challenges[key]['test']) == plan['test_counts'][key],
        'exact E13 public challenge/test binding required')
    value = {'run_id':plan['run_id'], 'plan_digest':digest(plan), 'rank':rank,
        'task_id':key, 'task_digest':digest(challenges[key]),
        'challenges_digest':digest(challenges), 'model_material_digest':plan['model_material_digest']}
    value.update(arm_contract(arm_id))
    validate_binding(value, arm_id)
    return value


def inference_contract(plan, schedule, arm_id):
    from tools.nvarc_e13_runtime import arm_contract
    for_plan(plan)
    require(schedule == 'interleaved', 'E13 permits only interleaved verification')
    contract = arm_contract(arm_id)
    require(contract['dfs_probability_floor'] == .2 and
        contract['dfs_max_score'] == -math.log(.2), 'E13 preserves the original p=.2 DFS')
    return contract['dfs_max_score']


def validate_allocations(admitted_allocations, bound, count):
    """Require caller-owned exact typed allocations before native replay imports."""
    from tools.nvarc_e13_runtime import allocation_deadlines, validate_binding
    require(type(bound) is dict, 'exact E13 caller task binding required')
    validate_binding(bound)
    require(type(admitted_allocations) is dict, 'separate E13 caller allocation map required')
    for index, admission in admitted_allocations.items():
        require(type(index) is str and index.isdigit() and str(int(index)) == index and
            0 <= int(index) < count and type(admission) is dict and
            type(admission.get('binding')) is dict and set(admission['binding']) == set(bound) and
            all(type(admission['binding'][k]) is type(v) and admission['binding'][k] == v
                for k, v in bound.items()), 'independent exact typed task/run/arm allocation binding required')
        allocation_deadlines(admission, bound, int(index))


def solve_test(challenges, task_id, test_index, loader, solver, decoder, tokenizer,
               adapter, *, maximum_candidates, emit, verification_schedule='interleaved',
               test_allocation=None, arm_id=None):
    """Admit E13, then execute the frozen original interleaved p=.2 solver."""
    from tools.nvarc_e13_runtime import allocation_deadlines, validate_binding
    require(verification_schedule == 'interleaved' and type(maximum_candidates) is int and
        maximum_candidates == 64, 'E13 requires interleaved verification and 64 processed sequences')
    require(type(test_allocation) is dict and arm_id is not None,
        'E13 source call requires its exact caller allocation and explicit arm')
    binding = test_allocation.get('binding')
    require(type(binding) is dict, 'exact E13 source allocation binding required')
    validate_binding(binding, arm_id)
    require(all(type(binding.get(k)) is type(v) and binding[k] == v for k, v in {
        'task_id':task_id, 'task_digest':digest(challenges[task_id]),
        'challenges_digest':digest(challenges)}.items()), 'E13 allocation visible task/test binding differs')
    require((adapter.generation_deadline, getattr(adapter, 'verification_deadline', None)) ==
        allocation_deadlines(test_allocation, binding, test_index), 'E13 caller deadlines differ')
    return native_solve_test(challenges, task_id, test_index, loader, solver, decoder, tokenizer,
        adapter, maximum_candidates=64, emit=emit, verification_schedule='interleaved',
        test_allocation=test_allocation, dfs_arm=None)


class BoundedEvents(Events):
    def __init__(self, path, binding):
        super().__init__(path,binding)
        self.bytes = 0

    def emit(self, event, **details):
        body = canonical({**self.binding, 'sequence':self.sequence, 'previous':self.head,
            'event':event, **details, 'digest':'sha256:'+'0'*64})+b'\n'
        require(len(body) <= MAX_EVENT_BYTES and self.bytes+len(body) <= MAX_LEDGER_BYTES,
            'bounded inference event/artifact byte ceiling reached before write')
        value = super().emit(event,**details)
        self.bytes += len(body)
        return value


class AnswerModel(LightModel):
    """Use the proven native adapter, retain actual call/input/NLL provenance."""
    def __call__(self, *, input_ids, **kwargs):
        emit = self.emit
        def bound(event, **details):
            if event == 'forward_reserved': details['input_ids_digest'] = digest(input_ids.tolist())
            emit(event,**details)
        self.emit = bound
        try:
            value = super().__call__(input_ids=input_ids,**kwargs)
        finally:
            self.emit = emit
        if self.active == 'verification':
            call = sum(self.reserved.values())
            emit('verification_observed',call_id=call,
                rows=[dict(row,**observed) for row,observed in zip(self.verification_rows,self.observed[call])])
        return value


def adapter_counts(adapter):
    return {phase:{'reserved':adapter.reserved[phase], 'completed':adapter.completed[phase],
        'input_tokens_reserved':adapter.input_by_phase[phase],
        'input_tokens_completed':adapter.completed_input_by_phase[phase]} for phase in PHASES}


def solve_task(engine, root, plan, rank, deadline, telemetry, *, observe_forwards=False,
               schedule='interleaved', directory=None, arm_id=None):
    require(type(observe_forwards) is bool, 'explicit forward observation switch required')
    selected = for_plan(plan,arm_id)
    require(not selected['forward_observer_required'] or observe_forwards,
        'E13 requires the host forward observer')
    inference_contract(plan,schedule,arm_id)
    root = Path(root); output = Path(directory) if directory is not None else root/'workers'/str(rank)
    challenges = parse_json((root/'challenges.json').read_bytes())
    bound = task_binding(plan,challenges,rank,schedule=schedule,arm_id=arm_id)
    key = bound['task_id']; count = plan['test_counts'][key]
    events = BoundedEvents(output/'inference-events.jsonl',bound)
    events.path.touch(exist_ok=False)  # An empty ledger binds a wholly unexecuted test set.
    record = {'binding':bound, 'tests':[{'test_index':i,'status':'not_executed','attempts':[],
        'missing_attempts':2} for i in range(count)], 'accounting':None,'errors':[],
        'output_qualified':False,'correctness_scored':False,'promotion':False}
    current = None; raw_returned = 0; processed = 0; allocations = {}
    def emit(event, **details):
        nonlocal raw_returned, processed
        # Native DFS can return more than 64 raw beams in one call. Only 64
        # processed sequences are admitted per test. Do not archive the raw
        # beam stream or an unbounded sequence of native clock reads.
        if event == 'generation_completed':
            result = details.pop('source_result')
            from tools.nvarc_native_solve_runtime import source_result_rows
            rows = source_result_rows(result)
            returned = sum(len(beams) for beams in rows.values())
            raw_returned += returned
            details['raw_returned'] = returned
            details['returned_rows'] = [{'row_index':n,'sequences':len(beams)} for n,beams in rows.items()]
            prefix=[]
            for row_index,beams in rows.items():
                for score,tokens in beams:
                    if len(prefix)>=64-processed: break
                    prefix.append({'row_index':row_index,'beam_score':float(score),'source_tokens':tokens})
                if len(prefix)>=64-processed: break
            details['returned_prefix']=prefix
            clocks = details.pop('source_clock_reads')
            details['source_clock_summary'] = {'count':len(clocks),
                'first':clocks[0] if clocks else None,'last':clocks[-1] if clocks else None}
        if event in ('candidate_invalid','candidate_parsed'): processed+=1
        details.setdefault('test_index',current)
        events.emit(event,**details)
    observer = HostForwardObserver(count*(PER_TEST['generation']+PER_TEST['verification'])) if observe_forwards else None
    adapter = AnswerModel(engine.model,engine.torch,emit,
        forward_limits={'control':7,'generation':4096*count,'verification':128*count},
        input_token_limit=5242880*count,generation_deadline=0,per_test_limits=dict(PER_TEST),
        forward_observer=observer)
    adapter.telemetry = telemetry
    write(output/'adapter-entry.json',{'constructor':'tools.nvarc_e13_answer_evidence.AnswerModel',
            'reserved':dict(adapter.reserved),'completed':dict(adapter.completed),'input_tokens':adapter.input_tokens,
            'observed_verifications':len(adapter.observed),'verification_rows':adapter.verification_rows,
            'active':adapter.active,'observer_rows':observer.snapshot()['observed_rows']})
    def checkpoint():
        record['accounting'] = adapter_counts(adapter)
        write(output/'answer-checkpoint.json',record)
        write(output/'test-allocations.json',allocations)
        if observer is not None:
            observation = dict(observer.snapshot(), binding=bound)
            require(len(canonical(observation)) <= MAX_LEDGER_BYTES,
                'bounded host forward observation artifact required')
            write(output/'inference-forward-diagnostics.json',observation)
    checkpoint()
    try:
        for current in range(count):
            start = time.time()
            if start + selected['per_test_seconds'] > deadline:
                break  # Every test receives its complete arm-specific window, without clipping.
            if observer is not None: observer.begin_test(current)
            stop = min(deadline,start+selected['per_test_seconds'])
            adapter.generation_deadline = max(start,stop-selected['verification_reserve_seconds'])
            adapter.verification_deadline = stop
            adapter.observed.clear(); raw_returned = 0; processed = 0
            events.emit('test_allocation',test_index=current,started_epoch=start,
                generation_deadline=adapter.generation_deadline,verification_deadline=stop)
            from tools.nvarc_e13_runtime import paired_allocation
            allocation = paired_allocation(bound,current,start,deadline)
            allocations[str(current)] = allocation
            write(output/'test-allocations.json',allocations)
            with engine.torch.inference_mode():
                test = solve_test(challenges,key,current,engine.loader,engine.solver,engine.decoder,
                    engine.tokenizer,adapter,maximum_candidates=64,emit=emit,
                    verification_schedule=schedule,test_allocation=allocation,arm_id=arm_id)
            end = time.time()
            test.update(raw_returned=raw_returned,
                raw_unprocessed=raw_returned-test['returned_sequences_processed'],
                started_epoch=start,finished_epoch=end,deadline_epoch=stop,
                clock_overrun=end>stop,
                candidate_path_exercised=bool(test['attempts']),
                output_qualified=(test['native_complete'] is True and bool(test['attempts']) and end<=stop))
            record['tests'][current] = test
            events.emit('test_committed',test_index=current,result=test)
            checkpoint()
        record['output_qualified'] = all(test.get('output_qualified') is True for test in record['tests'])
    except BaseException as error:
        record['errors'].append(diagnostic(error,'candidate-generation-verification'))
        raise
    finally:
        checkpoint()
    return record


def read_events(path, bound, *, allow_incomplete_tail=False):
    from tools.nvarc_e13_runtime import validate_binding
    validate_binding(bound)
    path = Path(path)
    require(not path.is_symlink() and path.stat().st_size <= MAX_LEDGER_BYTES,'bounded regular inference ledger required')
    body = path.read_bytes()
    if not body.endswith(b'\n') and allow_incomplete_tail:
        body=body[:body.rfind(b'\n')+1]
    require(not body or body.endswith(b'\n'),'complete inference event ledger required')
    events = []; head = digest(bound)
    for sequence,line in enumerate(body.splitlines()):
        require(len(line) <= MAX_EVENT_BYTES,'bounded retained event required')
        row = parse_json(line); reject_truth(row)
        require(row.get('event') in EVENT_FIELDS and set(row)==set(bound)|{
            'sequence','previous','event','digest','test_index'}|EVENT_FIELDS[row['event']],
            'closed declared inference event fields required')
        require(all(row.get(k)==v and type(row.get(k)) is type(v) for k,v in bound.items()) and
            type(row.get('sequence')) is int and row['sequence']==sequence and row['previous']==head and
            row['digest']==digest({k:v for k,v in row.items() if k!='digest'}), 'exact inference chain/input binding required')
        head = row['digest']; events.append(row)
    return events


def finite(value): return type(value) in (int,float) and math.isfinite(value)


def verify_forward_observation(path, bound, events, count):
    """Bind required host diagnostics to actual calls; never attest GPU timing."""
    path = Path(path)
    require(not path.is_symlink() and path.stat().st_size <= MAX_LEDGER_BYTES,
        'bounded regular host forward observation required')
    value = parse_json(path.read_bytes()); reject_truth(value)
    expected = HostForwardObserver(count*(PER_TEST['generation']+PER_TEST['verification'])).snapshot()
    dynamic = {'rows', 'observed_rows', 'truncated', 'dropped_rows'}
    require(set(value) == set(expected)|{'binding'} and type(value['binding']) is dict and
        set(value['binding']) == set(bound) and all(type(value['binding'][key]) is type(item) and
            value['binding'][key] == item for key,item in bound.items()) and
        all(type(value[key]) is type(item) and value[key] == item for key,item in expected.items()
            if key not in dynamic) and
        type(value['rows']) is list and type(value['observed_rows']) is int and
        value['observed_rows'] == len(value['rows']) <= value['maximum_rows'] and
        value['truncated'] is False and type(value['dropped_rows']) is int and value['dropped_rows'] == 0,
        'complete exact bound host observation metadata required')
    calls = [row for row in events if row['event'] == 'forward_reserved']
    require(len(value['rows']) == len(calls), 'every actual inference call must have host observation')
    fields = {'call_id','test_index','phase','batch_shape','cached','position_start','position_end',
        'batched_source_depth','position_backtrack','state','error_type','host_monotonic'}
    stages = ('call_entered','reservation','model_entered','model_returned','guard_completed','call_finished')
    replay = HostForwardObserver(value['maximum_rows'],clock=lambda:0.)
    for row,call in zip(value['rows'],calls):
        replay.begin_test(call['test_index'])
        shape = replay.reserve(call['call_id'],call['phase'],call['batch_shape'],call['cached'],
            call['position_start'],call['position_end'],0.)
        require(type(row) is dict and set(row) == fields and all(
            type(row[key]) is type(call[key]) and row[key] == call[key] for key in
                ('call_id','test_index','phase','batch_shape','cached','position_start','position_end')) and
            all(type(dimension) is int for dimension in row['batch_shape']) and
            row['state'] == 'complete' and row['error_type'] is None and
            all(type(row[key]) is type(shape[key]) and row[key] == shape[key] for key in
                ('batched_source_depth','position_backtrack')) and
            type(row['host_monotonic']) is dict and set(row['host_monotonic']) == set(stages) and
            all(finite(row['host_monotonic'][stage]) for stage in stages) and
            all(row['host_monotonic'][a] <= row['host_monotonic'][b] for a,b in zip(stages,stages[1:])),
            'exact call/input and ordered host timing observations required')
    return value


def check_inference(events, tests, count, *, plan=None, schedule='interleaved', admitted_allocations=None, arm_id=None):
    """Recompute actual reservations, completions, NLL/ranking and coverage."""
    selected = for_plan(plan,arm_id)
    max_score = inference_contract(plan,schedule,arm_id)
    require(type(admitted_allocations) is dict, 'separate E13 caller allocation map required')
    reservations = {}; completed = set(); observed = {}; allocations = {}; commits = {}
    counts = {p:dict(reserved=0,completed=0,input_tokens_reserved=0,input_tokens_completed=0) for p in PHASES}
    per_test = {}; parsed = {}; ranked = {}; raw = {}; terminals = {}
    allowed = {'test_allocation','test_started','generation_reserved','generation_completed','forward_reserved',
        'forward_completed','verification_observed','candidate_invalid','candidate_parsed','candidate_ranked',
        'test_terminal','test_committed'}
    active = None; processed = {}; parsed_sources = {}; voted_sources = set()
    for row in events:
        from tools.nvarc_e13_runtime import validate_binding
        validate_binding(row,arm_id)
        require(type(row.get('rank')) is int and 0 <= row['rank'] < len(plan['task_order']) and
            row.get('task_id') == plan['task_order'][row['rank']] and
            count == plan['test_counts'][row['task_id']] and
            all(type(row.get(k)) is type(v) and row[k] == v for k,v in {
                'run_id':plan['run_id'],'plan_digest':digest(plan),
                'challenges_digest':plan['challenges_digest'],
                'model_material_digest':plan['model_material_digest']}.items()),
            'exact E13 event plan/task/run binding required')
        event = row['event']; index = row['test_index']
        require(event in allowed and type(index) is int and 0<=index<count,'declared inference event/test required')
        if event == 'test_allocation':
            require(index == len(allocations) and (active is None or active in commits), 'one ordered test allocation required')
            require(all(finite(row[k]) for k in ('started_epoch','generation_deadline','verification_deadline')) and
                row['started_epoch'] <= row['generation_deadline'] <= row['verification_deadline'] <=
                    row['started_epoch']+selected['per_test_seconds'] and
                row['generation_deadline']==max(row['started_epoch'],
                    row['verification_deadline']-selected['verification_reserve_seconds']) and
                row['verification_deadline']==row['started_epoch']+selected['per_test_seconds'],
                'exact E13 generation/verifier allocation required; no clipped test window')
            from tools.nvarc_e13_runtime import allocation_deadlines
            admission = admitted_allocations.get(str(index))
            require(type(admission) is dict and type(admission.get('binding')) is dict,
                'separate E13 caller test allocation required')
            event_bound = {k:row[k] for k in admission['binding'] if k in row}
            require(set(event_bound) == set(admission['binding']) and all(
                type(event_bound[k]) is type(v) and event_bound[k] == v
                for k,v in admission['binding'].items()), 'caller allocation and event bindings differ')
            require(allocation_deadlines(admission,event_bound,index)==
                (row['generation_deadline'],row['verification_deadline']) and
                admission['started_epoch']==row['started_epoch'], 'caller admission and inference allocation differ')
            active=index; allocations[index]=row
            per_test[index]={'generation':0,'verification':0,'input_tokens':0}
            parsed[index]={}; ranked[index]=[]; raw[index]=0; processed[index]=0; parsed_sources[index]=[]
        require(index==active and index in allocations,'inference outside caller test allocation')
        if event == 'forward_reserved':
            call=row['call_id']; phase=row['phase']; shape=row['batch_shape']; tokens=row['physical_input_tokens']
            require(phase in PHASES and type(call) is int and call==len(reservations)+1 and
                type(shape) is list and len(shape)==2 and all(type(v) is int for v in shape) and
                shape[0]==4 and 1<=shape[1]<=8192 and type(tokens) is int and tokens==4*shape[1] and
                type(row['cached']) is bool and all(type(row[k]) is int for k in ('position_start','position_end')) and
                row['position_end']-row['position_start']==shape[1]-1 and 0<=row['position_start']<=row['position_end']<8192 and
                (row['cached'] or row['position_start']==0), 'actual bounded native forward reservation required')
            reservations[call]=row; counts[phase]['reserved']+=1; counts[phase]['input_tokens_reserved']+=tokens
            per_test[index][phase]+=1; per_test[index]['input_tokens']+=tokens
            require(all(per_test[index][p]<=PER_TEST[p] for p in PER_TEST),'per-test physical inference cap exceeded')
        elif event == 'forward_completed':
            call=row['call_id']; require(type(call) is int and call in reservations and call not in completed and
                row['phase']==reservations[call]['phase'] and index==reservations[call]['test_index'],
                'unique matching actual forward completion required')
            completed.add(call); phase=row['phase']; counts[phase]['completed']+=1
            counts[phase]['input_tokens_completed']+=reservations[call]['physical_input_tokens']
        elif event == 'verification_observed':
            call=row['call_id']; rows=row['rows']
            require(type(call) is int and call in completed and call not in observed and reservations[call]['phase']=='verification' and
                type(rows) is list and len(rows)==4,'four actual completed verifier rows required')
            for item in rows:
                require(set(item)=={'source_view','query_ids','answer_ids','query_digest','answer_digest','score'} and
                    all(type(item[k]) is list and item[k] and all(type(t) is int and 0<=t<=15 for t in item[k])
                        for k in ('query_ids','answer_ids')) and
                    digest(item['query_ids'])==item['query_digest'] and digest(item['answer_ids'])==item['answer_digest'] and
                    finite(item['score']) and item['score']>=0, 'finite NLL and exact source token binding required')
            padded=[r['query_ids']+r['answer_ids'] for r in rows]; width=max(map(len,padded))
            require(reservations[call]['batch_shape']==[4,width] and reservations[call]['input_ids_digest']==
                digest([r+[13]*(width-len(r)) for r in padded]), 'actual padded verifier input digest differs')
            observed[call]=row
        elif event == 'generation_completed':
            require(type(row['raw_returned']) is int and row['raw_returned']>=0,'raw returned count required')
            raw[index]+=row['raw_returned']
        elif event in ('candidate_invalid','candidate_parsed'):
            processed[index]+=1; require(processed[index]<=64,'processed sequence cap exceeded')
            tokens=row['source_tokens']
            require(type(tokens) is list and 1<=len(tokens)<=931 and tokens[-1]==15 and
                all(type(t) is int and 0<=t<=10 for t in tokens[:-1]), 'native EOS processed sequence required')
            if event=='candidate_parsed':
                identity=grid_key(row['candidate_grid']); parsed[index][identity]=row['candidate_grid']
                require(finite(row['beam_score']) and 0<=row['beam_score']<max_score,'native beam threshold required')
                parsed_sources[index].append(row)
        elif event == 'candidate_ranked':
            identity=grid_key(row['candidate_grid']); calls=row['verification_call_ids']
            require(identity in parsed[index] and len(calls)==len(set(calls))==2 and
                all(c in observed and observed[c]['test_index']==index for c in calls),
                'ranked candidate needs two distinct actual four-view verifier calls')
            scores=[item['score'] for c in calls for item in observed[c]['rows']]
            require(scores==row['score_aug'] and len(scores)==8,'all eight actual verifier NLLs required')
            matches=[p for p in parsed_sources[index] if all(p[k]==row[k] for k in
                ('source_view','source_tokens','candidate_grid','beam_score')) and p['sequence'] not in voted_sources]
            require(matches,'vote must come from one unconsumed processed source occurrence')
            voted_sources.add(matches[0]['sequence']); ranked[index].append(row)
        elif event == 'test_terminal':
            require(index not in terminals,'one terminal per test required'); terminals[index]=row['result']
        elif event == 'test_committed':
            require(index not in commits and index in terminals,'one completed terminal before task commit required')
            test=row['result']; original={k:v for k,v in test.items() if k not in
                ('raw_returned','raw_unprocessed','started_epoch','finished_epoch','deadline_epoch','clock_overrun',
                 'candidate_path_exercised','output_qualified')}
            require(original==terminals[index] and test==tests[index], 'checkpoint must match exact terminal event')
            require(type(test['returned_sequences_processed']) is int and test['returned_sequences_processed']==processed[index] and
                test['raw_returned']==raw[index] and test['raw_unprocessed']==raw[index]-processed[index]>=0,
                'raw/processed/unprocessed counts differ')
            a=allocations[index]
            require(type(test['test_index']) is int and test['test_index']==index and test['started_epoch']==a['started_epoch'] and
                test['deadline_epoch']==a['verification_deadline'] and finite(test['finished_epoch']) and
                test['finished_epoch']>=test['started_epoch'] and test['clock_overrun'] is (test['finished_epoch']>test['deadline_epoch']),
                'actual per-test clock receipt differs')
            groups={}
            for vote in ranked[index]: groups.setdefault(grid_key(vote['candidate_grid']),[]).append(vote)
            # This checks membership; verify_source_provenance below replays
            # the exact frozen native score_kgmon ranking and tie order.
            require(len(test['ranked_grids'])==len(groups) and {grid_key(g) for g in test['ranked_grids']}==set(groups) and
                test['attempts']==test['ranked_grids'][:2] and test['missing_attempts']==max(0,2-len(groups)),
                'ranked output must contain only fully verified candidate grids')
            qualified=test['native_complete'] is True and bool(test['attempts']) and not test['clock_overrun']
            require(test['native_complete'] is (test['completed_generation_batches']==4 and bool(groups) and
                test['termination_reason']=='all_source_batches_completed') and test['output_qualified'] is qualified and
                test['candidate_path_exercised'] is bool(test['attempts']),
                'deadline/empty/partial output must never be qualified')
            commits[index]=test
    require(len(tests)==count,'all real test denominator slots required')
    require(all('verification_schedule' not in test for test in tests),
        'interleaved results cannot inherit deferred queue evidence')
    require(set(reservations)==completed and
        {c for c in completed if reservations[c]['phase']=='verification'}==set(observed),
        'successful inference checkpoint requires every reserved forward and every actual verifier receipt; retain failures unqualified')
    require(set(commits)=={i for i,t in enumerate(tests) if t.get('status')!='not_executed'},'committed test coverage differs')
    require(set(admitted_allocations)=={str(i) for i in allocations},'caller allocation coverage differs')
    require(all(counts[p]['reserved']<=count*PER_TEST[p] for p in PHASES) and
        sum(counts[p]['input_tokens_reserved'] for p in PHASES)<=count*PER_TEST['input_tokens'],'task inference cap exceeded')
    return counts


def verify_source_provenance(root, challenges, key, events, tests, *, plan=None,
                             schedule='interleaved', admitted_allocations=None, arm_id=None):
    """Replay frozen formatter/inverses/eight-view inputs/native ranking on CPU.

Never import Torch or execute notebook statements. The retained bounded return
prefix establishes processed-source provenance; it does not numerically replay
DFS logits, and that limitation remains explicit in the protocol.
    """
    selected = for_plan(plan,arm_id)
    max_score = inference_contract(plan,schedule,arm_id)
    require(key in plan['task_order'], 'declared E13 source-replay task required')
    bound = task_binding(plan,challenges,plan['task_order'].index(key),schedule=schedule,arm_id=arm_id)
    validate_allocations(admitted_allocations,bound,plan['test_counts'][key])
    require(len(tests) == plan['test_counts'][key] and
        set(admitted_allocations) == {str(i) for i,test in enumerate(tests) if test.get('status') != 'not_executed'},
        'exact E13 source-replay test/allocation coverage required')
    require(all(all(type(row.get(k)) is type(v) and row[k] == v for k,v in bound.items())
        for row in events), 'exact E13 source-replay arm/task binding required')
    import numpy as np
    from tokenizers import Tokenizer
    from types import SimpleNamespace
    from tools.nvarc_native_solve_runtime import load_sources
    from tools.nvarc_native_multitask import test_views,verifier_rows
    loader,_,decoder=load_sources(root,SimpleNamespace(no_grad=lambda:lambda f:f),np)
    tok=Tokenizer.from_file(str(Path(root)/'verified-tokenizer.json'))
    class Tokens:
        def encode(self,text):return tok.encode(text).ids
        def decode(self,values):return tok.decode(values,skip_special_tokens=False)
    tokenizer=Tokens()
    for index,test in enumerate(tests):
        local=[row for row in events if row['test_index']==index]
        if test.get('status')=='not_executed':
            require(not local,'uncommitted test cannot be qualified'); continue
        base,puzzle,views,formatter,batches=test_views(challenges,key,index,loader,tokenizer)
        starts=[r for r in local if r['event']=='test_started']
        require(len(starts)==1 and starts[0]['base_key']==base and starts[0]['source_views']==views.keys and
            starts[0]['source_input_digests']=={k:digest(tokenizer.encode(views.get(k,formatter)['input'])) for k in views.keys},
            'real task/test source views and prefixes differ')
        reservations=[r for r in local if r['event']=='generation_reserved']
        generated=[r for r in local if r['event']=='generation_completed']
        require([r['batch_index'] for r in reservations]==list(range(len(reservations))) and len(reservations)<=4 and
            [r['batch_index'] for r in generated]==list(range(len(generated))) and len(generated)<=len(reservations),
            'ordered native batch coverage required')
        prefix=[]
        for r in reservations:
            b=r['batch_index']
            require(r['source_views']==batches[b] and r['prefix_digests']==[
                digest(tokenizer.encode(views.get(k,formatter)['input'])) for k in batches[b]],
                'generation prefix source binding differs')
            next_sequence = reservations[b+1]['sequence'] if b+1 < len(reservations) else math.inf
            forwarded = [f for f in local if f['event']=='forward_reserved' and f['phase']=='generation' and
                r['sequence'] < f['sequence'] < next_sequence]
            if forwarded:
                expected = [tokenizer.encode(views.get(k,formatter)['input']) for k in batches[b]]
                require(forwarded[0]['cached'] is False and forwarded[0]['input_ids_digest']==digest(expected),
                    'actual first prefill must match original task/test source inputs')
        for g in generated:
            b=g['batch_index']; r=reservations[b]
            forwards=[f for f in local if f['event']=='forward_reserved' and f['phase']=='generation' and r['sequence']<f['sequence']<g['sequence']]
            completions={f['call_id'] for f in local if f['event']=='forward_completed' and f['phase']=='generation' and r['sequence']<f['sequence']<g['sequence']}
            require(forwards and forwards[0]['cached'] is False and forwards[0]['input_ids_digest']==digest([
                tokenizer.encode(views.get(k,formatter)['input']) for k in batches[b]]) and
                all(f['call_id'] in completions for f in forwards) and g['raw_returned']<=4*len(completions),
                'returned candidates need actual completed native generation and finite raw cap')
            rows=g['returned_rows']
            require(type(rows) is list and len(rows)<=4 and all(set(r)=={'row_index','sequences'} and
                type(r['row_index']) is type(r['sequences']) is int and 0<=r['row_index']<4 and r['sequences']>=0
                for r in rows) and len({r['row_index'] for r in rows})==len(rows) and
                g['raw_returned']==sum(r['sequences'] for r in rows) and
                g['coverage']['batch_index']==b and g['coverage']['returned_row_ids']==sorted(r['row_index'] for r in rows) and
                g['coverage']['empty_rows']==4-sum(r['sequences']>0 for r in rows),
                'all native returned row counts and empty-row coverage must agree')
            require(len(g['returned_prefix'])==min(g['raw_returned'],64-len(prefix)), 'bounded complete processed-return prefix required')
            row_order=[]
            for row in rows:
                row_order.extend([row['row_index']]*min(row['sequences'],64-len(prefix)-len(row_order)))
            require([item['row_index'] for item in g['returned_prefix']]==row_order,
                'returned prefix must follow native returned row order and exact counts')
            for item in g['returned_prefix']:
                require(set(item)=={'row_index','beam_score','source_tokens'} and type(item['row_index']) is int and
                    0<=item['row_index']<4 and finite(item['beam_score']) and 0<=item['beam_score']<max_score and
                    type(item['source_tokens']) is list and 1<=len(item['source_tokens'])<=931 and item['source_tokens'][-1]==15 and
                    all(type(t) is int and 0<=t<=10 for t in item['source_tokens'][:-1]),'native returned view/beam/EOS contract required')
                prefix.append((batches[b][item['row_index']],item['beam_score'],item['source_tokens']))
            clocks=g['source_clock_summary']; coverage=g['coverage']
            require(set(clocks)=={'count','first','last'} and type(clocks['count']) is int and clocks['count']>=0 and
                ((clocks['count']==0 and clocks['first'] is clocks['last'] is None) or
                 (clocks['count']>0 and finite(clocks['first']) and finite(clocks['last']) and clocks['last']>=clocks['first'])) and
                finite(g['source_end_time']) and g['source_end_time']==max(test['started_epoch'],
                    test['deadline_epoch']-selected['verification_reserve_seconds']) and
                coverage['source_dfs_deadline_observed'] is bool(clocks['count'] and
                    (clocks['last']>=g['source_end_time'] or clocks['last']-clocks['first']>=540)),
                'source deadline evidence differs')
        processed=[r for r in local if r['event'] in ('candidate_parsed','candidate_invalid')]
        require(len(processed)==test['returned_sequences_processed']<=len(prefix),'processed return prefix coverage differs')
        for r,(view,score,tokens) in zip(processed,prefix):
            require(r['source_view']==view and r['source_tokens']==tokens,'candidate source return provenance differs')
            array=formatter.convert_tokens_to_array(tokens)
            if array is None:require(r['event']=='candidate_invalid','invalid parse differs')
            else:
                require(r['event']=='candidate_parsed' and r['beam_score']==score and
                    r['candidate_grid']==loader.ArcDataset.invert_mod(array,view,inv_perm=True).tolist(),
                    'native source parse/inverse grid differs')
                earlier=any(v['event']=='candidate_ranked' and v['sequence']<r['sequence'] and
                    v['candidate_grid']==r['candidate_grid'] for v in local)
                require(r['already_verified'] is earlier,'actual prior completed duplicate verification differs')
        observed={r['call_id']:r for r in local if r['event']=='verification_observed'}
        votes={}; verified={}
        for r in (r for r in local if r['event']=='candidate_ranked'):
            identity=grid_key(r['candidate_grid'])
            rows=[row for call in r['verification_call_ids'] for row in observed[call]['rows']]
            _,expected=verifier_rows(puzzle,base,r['candidate_grid'],loader,formatter,tokenizer)
            require([{k:row[k] for k in ('source_view','query_ids','answer_ids')} for row in rows]==expected,
                'eight actual verifier views must derive from this exact candidate/task/test')
            prior=verified.setdefault(identity,(r['score_aug'],r['verification_call_ids']))
            require(prior==(r['score_aug'],r['verification_call_ids']),'duplicate candidate verifier reuse differs')
            votes[str(len(votes))]={'solution':np.asarray(r['candidate_grid']),
                'beam_score':r['beam_score'],'score_aug':r['score_aug']}
        grids=[g.tolist() for g in decoder.score_kgmon(votes)]
        stop=test['termination_reason']
        require(test['ranked_grids']==grids and test['base_key']==base and
            type(test['invalid_candidates']) is int and test['invalid_candidates']==sum(
                r['event']=='candidate_invalid' for r in processed) and
            test['source_view_denominator']==16 and test['reserved_generation_batches']==len(reservations) and
            test['completed_generation_batches']==len(generated) and
            test['unfinished_source_views']==4*(len(reservations)-len(generated)) and
            test['undispatched_source_views']==16-4*len(reservations) and test['coverage']==[g['coverage'] for g in generated] and
            test['search_exhaustiveness_claim'] is False and
            stop in {'all_source_batches_completed','forward_limit','input_token_limit','inference_deadline','candidate_limit','source_dfs_deadline'} and
            (stop!='all_source_batches_completed' or len(generated)==4 and test['raw_unprocessed']==0 and
                len(votes)==sum(r['event']=='candidate_parsed' for r in processed) and not any(
                g['coverage']['source_dfs_deadline_observed'] for g in generated)) and
            test['status']==(('complete' if len(grids)>=2 else 'missing-candidate') if stop=='all_source_batches_completed'
                else ('partial-candidates' if grids else 'budget_stop')),
            'native ranking/termination/full real-view denominator differs')


def verify_task(root, plan, rank, *, schedule='interleaved', directory=None, admitted_allocations=None, arm_id=None):
    root=Path(root); directory=Path(directory) if directory is not None else root/'workers'/str(rank)
    inference_contract(plan,schedule,arm_id)
    challenges=parse_json((root/'challenges.json').read_bytes())
    bound=task_binding(plan,challenges,rank,schedule=schedule,arm_id=arm_id)
    validate_allocations(admitted_allocations,bound,plan['test_counts'][bound['task_id']])
    record=parse_json((directory/'answer-checkpoint.json').read_bytes()); reject_truth(record)
    require(set(record)=={'binding','tests','accounting','errors','output_qualified','correctness_scored','promotion'} and
        type(record['binding']) is dict and set(record['binding']) == set(bound) and
        all(type(record['binding'][k]) is type(v) and record['binding'][k] == v for k,v in bound.items()) and record['errors']==[] and record['correctness_scored'] is record['promotion'] is False,
        'exact successful bound inference checkpoint required')
    events=read_events(directory/'inference-events.jsonl',bound)
    require(record['accounting']==check_inference(events,record['tests'],plan['test_counts'][bound['task_id']],plan=plan,
        schedule=schedule,admitted_allocations=admitted_allocations,arm_id=arm_id) and
        record['output_qualified'] is all(t.get('output_qualified') is True for t in record['tests']),
        'actual inference counters/qualification differ')
    verify_source_provenance(root,challenges,bound['task_id'],events,record['tests'],plan=plan,
        schedule=schedule,admitted_allocations=admitted_allocations,arm_id=arm_id)
    if for_plan(plan)['forward_observer_required']:
        verify_forward_observation(directory/'inference-forward-diagnostics.json',bound,events,
            plan['test_counts'][bound['task_id']])
    return record


def recover_completed_tests(root, plan, rank, *, schedule='interleaved', directory=None, admitted_allocations=None, arm_id=None):
    """Retain only independently replayed committed prefix after later failure.

Training/reset/worker acceptance never follows from this recovery. All later
reservations remain in the original checkpoint/ledger and archive. Missing
slots mean no independently recoverable sealed attempt, not no model work.
    """
    root=Path(root); challenges=parse_json((root/'challenges.json').read_bytes())
    inference_contract(plan,schedule,arm_id)
    bound=task_binding(plan,challenges,rank,schedule=schedule,arm_id=arm_id)
    directory=Path(directory) if directory is not None else root/'workers'/str(rank)
    validate_allocations(admitted_allocations,bound,plan['test_counts'][bound['task_id']])
    if not (directory/'inference-events.jsonl').is_file():return None
    events=read_events(directory/'inference-events.jsonl',bound,allow_incomplete_tail=True)
    commits=[e for e in events if e['event']=='test_committed']
    if not commits:return None
    prefix=events[:commits[-1]['sequence']+1]
    count=plan['test_counts'][bound['task_id']]
    tests=[{'test_index':i,'status':'not_executed','attempts':[],'missing_attempts':2} for i in range(count)]
    for event in commits:
        require(event['test_index']<count,'declared committed recovery test required')
        tests[event['test_index']]=event['result']
    require(all(str(e['test_index']) in admitted_allocations for e in commits),
        'every recovered test needs its separate E13 caller allocation')
    admitted_allocations={str(e['test_index']):admitted_allocations[str(e['test_index'])] for e in commits}
    accounting=check_inference(prefix,tests,count,plan=plan,schedule=schedule,admitted_allocations=admitted_allocations,arm_id=arm_id)
    verify_source_provenance(root,challenges,bound['task_id'],prefix,tests,plan=plan,
        schedule=schedule,admitted_allocations=admitted_allocations,arm_id=arm_id)
    return {'binding':bound,'tests':tests,'accounting':accounting,'output_qualified':False,
        'recovery':'committed-source-verified-prefix-only; later work remains in original ledger',
        'training_and_reset_qualified':False,'correctness_scored':False,'promotion':False}

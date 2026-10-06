"""Independent native producer -> two-attempt export verification.

Hashes establish retained byte identity, not an attestation of model execution.
The reviewed GPU archive must additionally pass its hardware/training gates.
Raw caller grids are never input to this bridge.
"""
from __future__ import annotations
import math
import json
import hashlib
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from tools.arc_kaggle_submission import (build_submission, EVALUATOR_FIELDS, canonical as export_bytes)
from tools.nvarc_native_solve_runtime import require, grid_key, load_sources
from tools.nvarc_native_multitask import digest, test_views, verifier_rows, validate_challenges, FORMAT,public_training_material


def reject_truth(value):
    if isinstance(value, dict):
        require(not EVALUATOR_FIELDS.intersection(value), 'evaluator fields forbidden in native evidence')
        require(value.get('contains_evaluator_truth', False) is False and value.get('correctness_scored', False) is False,
                'evaluated native evidence forbidden')
        for child in value.values(): reject_truth(child)
    elif isinstance(value, list):
        for child in value: reject_truth(child)


def task_binding(plan, challenges, task_id):
    return {'run_id': plan['run_id'], 'plan_digest': digest(plan), 'task_id': task_id,
            'task_digest': digest(challenges[task_id]), 'challenges_digest': digest(challenges),
            'producer_sha256': plan['producer_sha256'], 'attempt_id': task_id}


def read_task_evidence(root, plan, challenges, receipts):
    """Recover only committed tests from even a killed worker's durable prefix."""
    from tools.arc_kaggle_submission import parse_json
    output=[]
    for task_id in plan['task_order']:
        matches=[r for r in receipts if r['attempt_id']==task_id]
        require(len(matches)<=1,'duplicate parent dispatch receipt')
        receipt=matches[0] if matches else {'task_id':task_id,'attempt_id':task_id,'status':'not_executed',
            'launched':False,'returncode':None,'reset_inferred':False}
        directory=Path(root)/'tasks'/task_id/'native'
        path=directory/'events.jsonl';events=[];truncated=False
        if path.is_file():
            body=path.read_bytes();lines=body.splitlines(keepends=True)
            for i,line in enumerate(lines):
                if not line.endswith(b'\n'):
                    require(i==len(lines)-1,'partial event in ledger middle');truncated=True;break
                events.append(parse_json(line))
        path=directory/'checkpoint.json'
        checkpoint=parse_json(path.read_bytes()) if path.is_file() else None
        output.append({'task_id':task_id,'binding':task_binding(plan,challenges,task_id),
            'receipt':receipt,'checkpoint':checkpoint,'events':events,'ledger_truncated':truncated,
            'provenance':'native-model'})
    return output


def check_events(events, binding, limits):
    head = digest(binding); reserved = {}; completed = set(); observed = {}
    counts = {p: 0 for p in ('control', 'generation', 'verification')}; tokens = dict(counts)
    allowed = {'test_started', 'generation_reserved', 'generation_completed', 'candidate_invalid',
               'candidate_parsed', 'candidate_ranked', 'test_terminal', 'forward_reserved',
               'forward_completed', 'verification_observed', 'generation_observed', 'cache_control_result',
               'verification_schedule'}
    details={
        'test_started':{'test_index','base_key','source_views','source_input_digests'},
        'verification_schedule':{'test_index','schedule','maximum_processed','generation_deadline','verification_deadline'},
        'generation_reserved':{'test_index','batch_index','source_views','prefix_digests'},
        'generation_completed':{'test_index','batch_index','source_result','coverage','source_clock_reads','source_end_time'},
        'candidate_invalid':{'test_index','source_view','source_tokens'},
        'candidate_parsed':{'test_index','source_view','source_tokens','candidate_grid','beam_score','already_verified'},
        'candidate_ranked':{'test_index','source_view','source_tokens','candidate_grid','beam_score','score_aug','verification_call_ids'},
        'test_terminal':{'result'},
        'forward_reserved':{'call_id','phase','batch_shape','physical_input_tokens','cached','position_start','position_end','input_ids_digest'},
        'forward_completed':{'call_id','phase','output_contract'},
        'verification_observed':{'call_id','rows'},'generation_observed':{'call_id','last_logits'},
        'cache_control_result':{'comparisons','baseline_prefill','deep_cached','sibling_cached','deep_reference','sibling_reference'}}
    logit_observed=set()
    for i, row in enumerate(events):
        require(all(row.get(k) == v for k, v in binding.items()) and row['sequence'] == i and
                row['previous'] == head and row['digest'] == digest({k:v for k,v in row.items() if k != 'digest'}) and
                row['event'] in allowed, 'native producer chain/binding differs')
        require(set(row)==set(binding)|{'sequence','previous','event','digest'}|details[row['event']],
                'unknown/evaluator fields in native event')
        head = row['digest']; kind = row['event']
        if kind == 'forward_reserved':
            p, shape, call = row['phase'], row['batch_shape'], row['call_id']
            require(p in counts and type(call) is int and call == len(reserved)+1 and
                    isinstance(shape, list) and len(shape) == 2 and shape[0] == 4 and type(shape[1]) is int and
                    1 <= shape[1] <= 8192 and type(row['physical_input_tokens']) is int and
                    row['physical_input_tokens'] == 4*shape[1] and type(row['cached']) is bool and
                    type(row['position_start']) is int and type(row['position_end']) is int and
                    0 <= row['position_start'] <= row['position_end'] < 8192 and
                    row['position_end']-row['position_start'] == shape[1]-1 and
                    (row['cached'] or row['position_start'] == 0), 'actual native call reservation differs')
            reserved[call] = row; counts[p] += 1; tokens[p] += row['physical_input_tokens']
        elif kind == 'forward_completed':
            call = row['call_id']
            require(call in reserved and call not in completed and row['phase'] == reserved[call]['phase'] and
                    row['output_contract'] in {'tuple-logits-cache', 'model-output-logits-cache'},
                    'native completion must follow reservation')
            completed.add(call)
        elif kind == 'verification_observed':
            call = row['call_id']
            require(call in completed and reserved[call]['phase'] == 'verification' and call not in observed and
                    len(row['rows']) == 4, 'native verifier needs one actual completed call')
            for r in row['rows']:
                require(set(r)=={'source_view','query_ids','answer_ids','answer_log_probabilities','score'},
                        'closed native verifier row required')
                ids = r['query_ids'] + r['answer_ids']; logp = r['answer_log_probabilities']
                require(r['query_ids'] and r['answer_ids'] and r['answer_ids'][-1] == 15 and
                        all(type(t) is int and 0 <= t < 16 for t in ids) and
                        len(logp) == len(r['answer_ids']) and
                        all(type(s) in (int,float) and math.isfinite(s) and s <= 0 for s in logp) and
                        type(r['score']) in (int,float) and math.isfinite(r['score']) and r['score'] >= 0 and
                        math.isclose(-math.fsum(logp), r['score'], rel_tol=2e-6, abs_tol=2e-6),
                        'EOS-inclusive actual verifier NLL differs')
            width = max(len(r['query_ids'])+len(r['answer_ids']) for r in row['rows'])
            ids=[r['query_ids']+r['answer_ids'] for r in row['rows']]
            require(reserved[call]['batch_shape'] == [4,width] and reserved[call]['input_ids_digest']==
                    digest([r+[13]*(width-len(r)) for r in ids]), 'verifier physical shape/input differs')
            observed[call] = row['rows']
        elif kind == 'generation_observed':
            require(row['call_id'] in completed and row['call_id'] not in logit_observed and reserved[row['call_id']]['phase']=='generation' and
                    len(row['last_logits'])==4 and all(len(v)==16 and all(type(x) in (int,float) and
                    math.isfinite(x) for x in v) for v in row['last_logits']), 'actual generation logits required')
            logit_observed.add(row['call_id'])
        elif kind == 'cache_control_result':
            from tools.nvarc_native_solve_runtime import compare_vectors
            recomputed={'deep':compare_vectors(row['deep_reference'],row['deep_cached']),
                'sibling_after_deep':compare_vectors(row['sibling_reference'],row['sibling_cached'])}
            require(row['comparisons']==recomputed,'cache control comparison evidence differs')
    require(all(counts[p] <= limits['inference_forward_limits'][p] for p in counts) and tokens['control'] <= 168 and
            tokens['generation']+tokens['verification'] <= limits['maximum_inference_input_tokens'],
            'task inference ceilings differ')
    return observed, counts, tokens


def replay_generation(events, reserved, completed, prefixes, source_directory):
    """Replay the exact DFS against retained real last-logit tensors and clocks.

    This invokes no model; it rejects changed generation scores/tokens/branch
    order/prefixes/cached positions even if the event chain was recomputed.
    """
    import torch
    import numpy as np
    _,solver,_=load_sources(source_directory,torch,np)
    calls=[e for e in events if e['event']=='forward_reserved' and e['phase']=='generation' and
           reserved['sequence'] < e['sequence'] < completed['sequence']]
    outputs={e['call_id']:e for e in events if e['event']=='generation_observed'}
    cursor=0;clock_cursor=0;clock_reads=completed['source_clock_reads']
    require(isinstance(clock_reads,list) and all(type(x) in (int,float) and math.isfinite(x) for x in clock_reads) and
            type(completed['source_end_time']) in (int,float) and math.isfinite(completed['source_end_time']),
            'exact bounded source-clock transcript required')
    class Clock:
        @staticmethod
        def time():
            nonlocal clock_cursor
            require(clock_cursor<len(clock_reads),'extra source DFS clock read')
            value=clock_reads[clock_cursor];clock_cursor+=1;return value
    solver.turbo_dfs.__globals__['time']=Clock
    class Replay:
        device='cpu'
        def __call__(self,*,input_ids,**kwargs):
            nonlocal cursor
            require(cursor<len(calls),'extra source DFS model entry')
            row=calls[cursor];cursor+=1
            require(row['input_ids_digest']==digest(input_ids.tolist()) and
                    row['cached'] is (kwargs.get('past_key_values') is not None),'source DFS actual token path differs')
            positions=kwargs.get('position_ids')
            start=0 if positions is None else positions[0,0].item()
            require(row['position_start']==start and row['batch_shape']==list(input_ids.shape),
                    'source DFS cache/position path differs')
            require(row['call_id'] in outputs,'source generation logits missing')
            return SimpleNamespace(logits=torch.tensor(outputs[row['call_id']]['last_logits'],dtype=torch.float32)[:,None],
                                   past_key_values=object())
    actual=solver.inference_turbo_dfs(Replay(),prefixes,931,-math.log(.2),completed['source_end_time'])
    require(cursor==len(calls) and clock_cursor==len(clock_reads) and digest(actual)==digest(completed['source_result']),
            'original source DFS token/beam/clock replay differs')


def verify_test(challenges, task_id, result, events, loader, decoder, tokenizer, observed, maximum_candidates,
                source_directory, per_test_limits, *, injected=False, verification_schedule='interleaved'):
    require(verification_schedule in ('interleaved', 'deferred'), 'known planned verification schedule required')
    index = result['test_index']
    base, puzzle, views, formatter, batches = test_views(challenges, task_id, index, loader, tokenizer)
    local = [e for e in events if e.get('test_index') == index]
    starts = [e for e in local if e['event'] == 'test_started']
    require(len(starts) == 1 and starts[0]['base_key'] == base and starts[0]['source_views'] == views.keys and
            starts[0]['source_input_digests'] == {k:digest(tokenizer.encode(views.get(k,formatter)['input'])) for k in views.keys},
            'real test index/source formatter input binding differs')
    terminals = [e for e in events if e['event']=='test_terminal' and e['result']['test_index']==index]
    require(len(terminals)==1 and terminals[0]['result']==result and starts[0]['sequence']<terminals[0]['sequence'],
            'exact immutable test terminal required')
    forwards=[e for e in events if e['event']=='forward_reserved' and
              starts[0]['sequence'] < e['sequence'] < terminals[0]['sequence']]
    require(all(sum(e['phase']==p for e in forwards)<=per_test_limits[p] for p in ('generation','verification')) and
            sum(e['physical_input_tokens'] for e in forwards)<=per_test_limits['input_tokens'],
            'per-test reserved forward/token ceiling differs')
    reservations = [e for e in local if e['event'] == 'generation_reserved']
    generated = [e for e in local if e['event'] == 'generation_completed']
    require([e['batch_index'] for e in reservations] == list(range(len(reservations))) and
            [e['batch_index'] for e in generated] == list(range(len(generated))) and
            len(generated) <= len(reservations) <= 4, 'source generation coverage differs')
    beam_candidates = []; invalid = 0
    for r in reservations:
        b = r['batch_index']; batch = batches[b]
        require(r['source_views'] == batch and r['prefix_digests'] ==
                [digest(tokenizer.encode(views.get(k, formatter)['input'])) for k in batch],
                'reserved source batch/prefix differs')
        if b >= len(generated): continue
        e = generated[b]
        require(r['sequence'] < e['sequence'], 'generation completion before reservation')
        forwards=[f for f in events if f['event']=='forward_reserved' and f['phase']=='generation' and
                  r['sequence'] < f['sequence'] < e['sequence']]
        require(forwards and forwards[0]['cached'] is False and forwards[0]['input_ids_digest']==
                digest([tokenizer.encode(views.get(k,formatter)['input']) for k in batches[b]]) and
                all(any(o['event']=='generation_observed' and o['call_id']==f['call_id'] and
                        f['sequence'] < o['sequence'] < e['sequence'] for o in events) for f in forwards),
                'generation batch needs bound completed native model transcript')
        if not injected:
            replay_generation(events,r,e,[tokenizer.encode(views.get(k,formatter)['input']) for k in batches[b]],source_directory)
        ids = []; nonempty = 0
        for row_index, beams in e['source_result']:
            require(type(row_index) is int and 0 <= row_index < 4 and row_index not in ids and isinstance(beams,list),
                    'duplicate/invalid returned source row')
            ids.append(row_index); nonempty += bool(beams)
            for score, tokens in beams:
                beam_candidates.append((batches[b][row_index],score,tokens))
        clocks=e['source_clock_reads']
        require(e['coverage'] == {'batch_index':b,'returned_row_ids':sorted(ids),'empty_rows':4-nonempty,
                    'source_dfs_deadline_observed':bool(clocks and
                        (clocks[-1]>=e['source_end_time'] or clocks[-1]-clocks[0]>=540))},
                'sparse source row denominator differs')
    require(type(result['returned_sequences_processed']) is int and
            0 <= result['returned_sequences_processed'] <= min(len(beam_candidates),maximum_candidates),
            'finite candidate processing ceiling differs')
    processed = beam_candidates[:result['returned_sequences_processed']]
    parsed = [e for e in local if e['event'] == 'candidate_parsed']
    bad = [e for e in local if e['event'] == 'candidate_invalid']
    ranked = [e for e in local if e['event'] == 'candidate_ranked']
    valid = []; sequence_indices = []
    for sequence_index, (key,score,tokens) in enumerate(processed):
        require(isinstance(tokens,list) and 1 <= len(tokens) <= 931 and tokens[-1] == 15 and
                all(type(t) is int and 0 <= t <= 10 for t in tokens[:-1]) and
                type(score) in (int,float) and math.isfinite(score) and 0 <= score < -math.log(.2),
                'exact source beam contract differs')
        a = formatter.convert_tokens_to_array(tokens)
        if a is None:
            require(invalid < len(bad) and bad[invalid]['source_view'] == key and bad[invalid]['source_tokens'] == tokens,
                    'invalid parse evidence differs'); invalid += 1; continue
        valid.append((key,float(score),tokens,loader.ArcDataset.invert_mod(a,key,inv_perm=True).tolist()))
        sequence_indices.append(sequence_index)
    require(len(parsed) == len(valid) and len(ranked) <= len(parsed) and len(bad) == invalid == result['invalid_candidates'],
            'parsed/ranked evidence coverage differs')
    votes = {}; verified = {}
    if verification_schedule == 'deferred':
        votes, verified = verify_deferred_votes(result, local, events, starts[0], terminals[0],
            parsed, ranked, valid, sequence_indices, puzzle, base, loader, formatter, tokenizer,
            observed, maximum_candidates)
    else:
        require('verification_schedule' not in result and
            not any(e['event']=='verification_schedule' for e in local),
            'unplanned deferred evidence forbidden')
    for n, (key,score,tokens,solution) in enumerate(valid):
        if verification_schedule == 'deferred': break
        r = parsed[n]; identity = grid_key(solution)
        require(r['source_view'] == key and r['source_tokens'] == tokens and r['candidate_grid'] == solution and
                r['beam_score'] == score and r['already_verified'] is (identity in verified),
                'source parse/inverse evidence differs')
        if n >= len(ranked):
            require(n == len(valid)-1 and result['termination_reason'] in
                    {'forward_limit','input_token_limit','inference_deadline'}, 'only final interrupted verification may lack rank')
            continue
        r = ranked[n]
        require(r['source_view'] == key and r['source_tokens'] == tokens and r['candidate_grid'] == solution and
                r['beam_score'] == score and r['sequence'] > parsed[n]['sequence'], 'ranked vote provenance differs')
        if identity not in verified:
            _, bindings = verifier_rows(puzzle,base,solution,loader,formatter,tokenizer)
            calls = r['verification_call_ids']
            require(len(calls) == 2 and len(set(calls)) == 2 and all(c in observed for c in calls),
                    'all eight native verifier rows required')
            observed_rows = sum((observed[c] for c in calls), [])
            require([{k:r[k] for k in ('source_view','query_ids','answer_ids')} for r in observed_rows] == bindings,
                    'eight-view actual source verification input/answer differs')
            require(all(parsed[n]['sequence'] < next(e['sequence'] for e in events if
                    e['event']=='verification_observed' and e['call_id']==c) < r['sequence'] for c in calls),
                    'verification replay/order differs')
            verified[identity] = ([r['score'] for r in observed_rows],calls)
        require((r['score_aug'],r['verification_call_ids']) == verified[identity], 'duplicate vote/ranking scores differ')
        votes[str(n)] = {'solution':loader.np.asarray(solution),'score_aug':r['score_aug'],'beam_score':score}
    grids = [g.tolist() for g in decoder.score_kgmon(votes)]
    stop = result['termination_reason']
    require(stop in {'all_source_batches_completed','forward_limit','input_token_limit','inference_deadline','candidate_limit','source_dfs_deadline'} and
            (stop != 'all_source_batches_completed' or len(generated) == 4) and
            result['base_key'] == base and result['ranked_grids'] == grids and result['attempts'] == grids[:2] and
            result['missing_attempts'] == max(0,2-len(grids)) and result['source_view_denominator'] == 16 and
            result['reserved_generation_batches'] == len(reservations) and result['completed_generation_batches'] == len(generated) and
            result['unfinished_source_views'] == 4*(len(reservations)-len(generated)) and
            result['undispatched_source_views'] == 16-4*len(reservations) and
            result['coverage'] == [e['coverage'] for e in generated] and result['search_exhaustiveness_claim'] is False and
            result['native_complete'] is (len(generated)==4 and bool(grids) and stop=='all_source_batches_completed'),
            'independent ranking/termination/attempt denominator differs')
    expected_status = ('complete' if len(grids)>=2 else 'missing-candidate') if stop=='all_source_batches_completed' else (
                       'partial-candidates' if grids else 'budget_stop')
    require(result['status'] == expected_status, 'native complete is distinct from two model attempt slots')
    if 'telemetry' in result:
        verify_candidate_telemetry(result, processed, valid, sequence_indices, verified,
            local, events, starts[0], terminals[0], observed, verification_schedule)
    return {'test_index':index, 'attempts':grids[:2], 'missing_attempts':max(0,2-len(grids)),
            'status':'complete' if len(grids)>=2 else 'missing-candidate', 'native_result_digest':digest(result)}


def verify_deferred_votes(result, local, events, start, terminal, parsed, ranked, valid,
                          sequence_indices, puzzle, base, loader, formatter, tokenizer,
                          observed, maximum_candidates):
    """Reconstruct FIFO and every vote from source returns and actual NLL rows.

    No model call, queue-supplied grid, score or duplicate count is trusted.
    This additional gate does not replace the native DFS/reset/source gates.
    """
    proof = result.get('verification_schedule', {})
    fields = {'format','schedule','fifo_policy','maximum_processed','generation_deadline',
        'verification_deadline','generation_finished_at','verification_started_at',
        'verification_finished_at','generation_termination','verification_termination','queue'}
    require(set(proof) == fields and proof['format']=='irisx/nvarc-verification-schedule-v1' and
        proof['schedule']=='deferred' and proof['fifo_policy']==
        'first_processed_occurrence; batch order, returned row order, beam order' and
        type(proof['maximum_processed']) is int and proof['maximum_processed']==maximum_candidates<=64,
        'closed bounded deferred schedule required')
    declarations = [e for e in local if e['event']=='verification_schedule']
    require(len(declarations)==1 and declarations[0]['schedule']=='deferred' and
        declarations[0]['maximum_processed']==maximum_candidates and
        start['sequence'] < declarations[0]['sequence'] < min(
            (e['sequence'] for e in local if e['event']=='generation_reserved'), default=terminal['sequence']) and
        all(type(proof[k]) in (int,float) and math.isfinite(proof[k]) for k in (
            'generation_deadline','verification_deadline','generation_finished_at',
            'verification_started_at','verification_finished_at')) and
        all(declarations[0][k]==proof[k] for k in ('generation_deadline','verification_deadline')) and
        proof['generation_deadline']<=proof['verification_deadline'] and
        proof['verification_started_at']==proof['generation_finished_at']<=proof['verification_finished_at'],
        'same absolute deferred deadline/phase declaration required')
    generation_reasons = {'all_source_batches_completed','forward_limit','input_token_limit',
        'inference_deadline','candidate_limit','source_dfs_deadline'}
    require(proof['generation_termination'] in generation_reasons and
        proof['verification_termination'] in {'queue_completed','forward_limit','input_token_limit','inference_deadline'} and
        result['termination_reason']==(proof['generation_termination'] if
            proof['verification_termination']=='queue_completed' else proof['verification_termination']),
        'separate generation/verification termination required')
    unique = {}
    for index, (key,score,tokens,solution) in zip(sequence_indices,valid):
        identity=grid_key(solution)
        unique.setdefault(identity, (index,solution))
    queue=proof['queue']
    require(isinstance(queue,list) and len(queue)==len(unique)<=maximum_candidates,
            'deferred unique queue closure differs')
    verification_events=[e for e in events if e['event']=='verification_observed' and
        start['sequence']<e['sequence']<terminal['sequence']]
    generation_end=max((e['sequence'] for e in local if e['event'] in
        {'generation_completed','candidate_parsed','candidate_invalid'}), default=start['sequence'])
    verification_reservations=[e for e in events if e['event']=='forward_reserved' and
        e['phase']=='verification' and start['sequence']<e['sequence']<terminal['sequence']]
    require(all(e['sequence']>generation_end for e in verification_events) and
        all(e['sequence']>generation_end for e in verification_reservations) and
        [e['call_id'] for e in verification_reservations]==[e['call_id'] for e in verification_events] and
        all(e['source_end_time']==proof['generation_deadline'] for e in local if e['event']=='generation_completed') and
        all(e['sequence']>max((v['sequence'] for v in verification_events),default=generation_end)
            for e in ranked), 'deferred verification must follow generation/parse and precede votes')
    cursor=0; verified={}; stopped=False
    for q,(identity,(index,solution)) in zip(queue,unique.items()):
        require(set(q)=={'candidate_digest','first_sequence_index','state','completed_views','call_ids'} and
            q['candidate_digest']==digest(solution) and type(q['first_sequence_index']) is int and
            q['first_sequence_index']==index and q['state'] in {'full','partial','unfinished','pending'} and
            type(q['completed_views']) is int and q['completed_views'] in (0,4,8) and
            q['completed_views']==4*len(q['call_ids']) and
            q['state']==('full' if q['completed_views']==8 else 'partial' if q['completed_views']==4
                         else q['state']) and
            (not stopped or q['state']=='pending'), 'first-occurrence FIFO/partial closure differs')
        if q['state']=='full': require(q['completed_views']==8,'full requires eight views')
        if q['state'] in {'pending','unfinished'}: require(q['completed_views']==0,'pending cannot have scores')
        if q['state']!='full': stopped=True
        count=len(q['call_ids']); selected=verification_events[cursor:cursor+count];cursor+=count
        require(q['call_ids']==[e['call_id'] for e in selected] and
            all(c in observed for c in q['call_ids']), 'FIFO actual verifier call order differs')
        _,bindings=verifier_rows(puzzle,base,solution,loader,formatter,tokenizer)
        actual=sum((observed[c] for c in q['call_ids']),[])
        require([{k:r[k] for k in ('source_view','query_ids','answer_ids')} for r in actual]==
            bindings[:q['completed_views']], 'deferred eight-view actual token binding differs')
        if q['state']=='full': verified[identity]=([r['score'] for r in actual],q['call_ids'])
    require(cursor==len(verification_events) and (not stopped or proof['verification_termination']!='queue_completed'),
        'no orphan verifier observations or unfinished successful queue')
    expected=[(p,v) for p,v in zip(parsed,valid) if grid_key(v[3]) in verified]
    require(len(expected)==len(ranked),'all original fully verified occurrences must vote')
    for p,(key,score,tokens,solution) in zip(parsed,valid):
        require((p['source_view'],p['source_tokens'],p['candidate_grid'],p['beam_score'],p['already_verified'])==
            (key,tokens,solution,score,False), 'deferred original parse/inverse provenance differs')
    votes={}
    for n,(r,(p,(key,score,tokens,solution))) in enumerate(zip(ranked,expected)):
        scores,calls=verified[grid_key(solution)]
        require((r['source_view'],r['source_tokens'],r['candidate_grid'],r['beam_score'],
            r['score_aug'],r['verification_call_ids'])==(key,tokens,solution,score,scores,calls) and
            p['sequence']<r['sequence'], 'deferred vote multiplicity/source/ranking differs')
        votes[str(n)]={'solution':loader.np.asarray(solution),'score_aug':scores,'beam_score':score}
    return votes,verified


def verify_candidate_telemetry(result, processed, valid, sequence_indices, verified,
                               local, events, start, terminal, observed, schedule):
    """Recount optional E00/E10 observations; telemetry never grants qualification."""
    life=result['telemetry'];unique={};sources=[];valid_by_index=dict(zip(sequence_indices,valid))
    for index,(key,score,tokens) in enumerate(processed):
        value=valid_by_index.get(index);identity=None if value is None else grid_key(value[3])
        sources.append({'sequence_index':index,'source_view':key,'source_tokens_digest':digest(tokens),
            'returned_token_count':len(tokens),'candidate_digest':None if value is None else digest(value[3]),
            'duplicate':identity in unique if value is not None else False,
            'voted':identity in verified if value is not None else False})
        if value is not None:unique.setdefault(identity,value[3])
    verification_events=[e for e in events if e['event']=='verification_observed' and
        start['sequence']<e['sequence']<terminal['sequence']]
    if schedule=='deferred':
        expected=[{'candidate_digest':q['candidate_digest'],'completed_views':q['completed_views'],
            'required_views':8,'state':q['state'],'call_ids':q['call_ids']}
            for q in result['verification_schedule']['queue'] if q['state']!='pending']
    else:
        expected=[];used=set()
        for identity,solution in unique.items():
            if identity in verified:
                calls=verified[identity][1];used.update(calls);state='full'
            else:
                calls=[e['call_id'] for e in verification_events if e['call_id'] not in used]
                state='partial' if calls else 'unfinished'
            expected.append({'candidate_digest':digest(solution),'completed_views':4*len(calls),
                'required_views':8,'state':state,'call_ids':calls})
    counters={'raw_returned':sum(len(beams) for e in local if e['event']=='generation_completed'
        for _,beams in e['source_result']), 'processed':len(processed),'invalid':len(processed)-len(valid),
        'duplicate':len(valid)-len(unique),'parsed_unique':len(unique),'verification_started':len(expected),
        'partial_verified':sum(v['state']=='partial' for v in expected),
        'full_verified':len(verified),'ranked':len(verified),'votes_ranked':sum(s['voted'] for s in sources)}
    if schedule=='deferred':
        counters.update(queued=len(unique),pending=sum(q['state']=='pending' for q in result['verification_schedule']['queue']))
    require(all(type(v) is int for v in life['counters'].values()) and
        all(type(s['sequence_index']) is int and type(s['returned_token_count']) is int and
            type(s['duplicate']) is bool and type(s['voted']) is bool for s in life['sequences']) and
        life['counters']==counters and life['sequences']==sources and life['verifications']==expected and
        life['termination_reason']==result['termination_reason'], 'independent candidate telemetry recount differs')
    reserved=[e for e in events if e['event']=='forward_reserved' and start['sequence']<e['sequence']<terminal['sequence']]
    completed={e['call_id'] for e in events if e['event']=='forward_completed' and
        start['sequence']<e['sequence']<terminal['sequence']}
    phases=('control','generation','verification')
    require(life['forward_reservations']=={p:sum(e['phase']==p for e in reserved) for p in phases} and
        life['forward_completions']=={p:sum(e['phase']==p and e['call_id'] in completed for e in reserved) for p in phases} and
        life['reserved_physical_input_tokens']=={p:sum(e['physical_input_tokens'] for e in reserved if e['phase']==p) for p in phases} and
        life['completed_physical_input_tokens']=={p:sum(e['physical_input_tokens'] for e in reserved
            if e['phase']==p and e['call_id'] in completed) for p in phases}, 'actual telemetry forward/token deltas differ')


def verify_native_training_gate(root,plan,challenges,task_id,loader,tokenizer):
    """Native attempts require the reviewed process/material and full TTT gate.

    A killed worker may have no final result/reset; its completed TTT and test
    checkpoint can still qualify earlier candidates. Reset is never inferred.
    """
    from tools.arc_kaggle_submission import parse_json
    from tools.nvarc_native_solve_runtime import compare_vectors
    def read(name):
        path=Path(root)/name;require(path.is_file(),'native hardware/training provenance artifact missing: '+name)
        value=parse_json(path.read_bytes());reject_truth(value);return value
    hardware=read('hardware.json');devices=hardware['inventory']
    require(hardware['torch']=='2.8.0+cu128' and hardware['cuda']=='12.8' and
        len(devices)==len({r['uuid'] for r in devices})==4 and
        all(r['name']=='NVIDIA L4' and r['bf16'] is True for r in devices),'native four-L4 envelope required')
    model=read('model-verification.json');source=read('source-verification.json');parent=read('parent-verification.json')
    require(model['all_ten_files_verified'] is True and model['model_material_digest']==plan['model_material_digest'] and
        digest(source['inventory'])==plan['source_inventory_digest'] and parent['plan_digest']==digest(plan) and
        parent['source_inventory_verified'] is parent['four_distinct_bf16_l4s'] is True and
        parent['model_material_digest']==plan['model_material_digest'],'native exact source/published-model gate required')
    prefix='tasks/'+task_id+'/native/'
    require(read(prefix+'hardware.json')['device_uuid']==devices[0]['uuid'],'task native UUID mapping differs')
    spec=plan['task_specs'][task_id]
    material=public_training_material(loader,tokenizer,task_id,challenges[task_id]);expected=material['rows']
    require(digest(expected)==spec['expected_rows_digest'] and digest(material['texts'])==spec['texts_digest'],
        'public-only task epoch material differs')
    preparation=read(prefix+'preparation.json');prepared=read(prefix+'prepared-rows.json')
    require(preparation['trainer_origins']==plan['native_trainer_origins'] and
        preparation['checkpoint_flags']==plan['native_checkpoint_flags'] and
        preparation['prepared_rows_digest']==digest(prepared) and preparation['blocked_attempts']==0 and
        len(prepared)==len(expected)==spec['training_forwards'] and all(
            r['input_ids_digest']==e['input_ids_digest'] and r['labels_digest']==e['labels_digest'] and
            r['source_input_ids_equal'] is r['source_labels_equal'] is r['collator_preserved_input_ids'] is True
            for r,e in zip(prepared,expected)),'native actual collator/preparation gate differs')
    ledger=read(prefix+'training-ledger.json')
    require(all(len(ledger[k])==len(expected) and all(r['completed'] is True for r in ledger[k])
            for k in ('forwards','training_steps','optimizer_steps')) and
        Counter((r['input_ids_digest'],r['labels_digest']) for r in ledger['forwards'])==
        Counter((r['input_ids_digest'],r['labels_digest']) for r in expected),
        'native model attempts require complete exact public-demo epoch')
    before,trained=read(prefix+'baseline-inventory.json'),read(prefix+'trained-inventory.json')
    require(len(before)==len(trained)==506 and [r['name'] for r in before]==[r['name'] for r in trained] and
        all(r['finite'] is True and r['dtype']=='torch.bfloat16' for r in before+trained) and before!=trained,
        'native finite changed BF16 tensor evidence required')
    control=read(prefix+'cache-control.json')
    require(all(v['gate_passed'] for v in control['comparisons'].values()),'native cache control failed')
    return {'full_task_epoch_verified':True,'model_material_digest':plan['model_material_digest'],
            'preparation_digest':digest(preparation),'training_ledger_digest':digest(ledger),
            'trained_inventory_digest':digest(trained),'reset_verified_by_this_gate':False}


def build_native_submission(challenges, plan, evidence, source_directory, tokenizer, *, allow_fixture=False):
    """Only evidence with exact planned producer bindings reaches the exporter."""
    reject_truth(evidence); counts = validate_challenges(challenges)
    require(plan['format']==FORMAT and plan['challenges_digest']==digest(challenges) and
            plan['task_order']==list(counts) and len(evidence)==len(counts), 'complete planned task denominator required')
    producer_paths={'worker':'inspection.py','helper':'inspection_helpers.py','budget':'nvarc_native_ttt_budget.py',
        'schedule':'nvarc_native_ttt_schedule.py','solve_runtime':'tools/nvarc_native_solve_runtime.py',
        'multitask':'tools/nvarc_native_multitask.py','bridge':'tools/nvarc_native_submission.py','exporter':'tools/arc_kaggle_submission.py'}
    require(set(plan['producer_files'])==set(producer_paths) and digest(plan['producer_files'])==plan['producer_sha256'] and
        all(hashlib.sha256((Path(source_directory)/name).read_bytes()).hexdigest()==plan['producer_files'][key]
            for key,name in producer_paths.items()), 'exact planned native producer program bytes required')
    import numpy as np
    loader, _, decoder = load_sources(source_directory,SimpleNamespace(no_grad=lambda:lambda f:f),np)
    records=[]; audits=[]; seen=set()
    for data in evidence:
        require(set(data)=={'task_id','binding','receipt','checkpoint','events','ledger_truncated','provenance'} and
                type(data['ledger_truncated']) is bool,'closed producer envelope required')
        task_id = data['task_id']; require(task_id in counts and task_id not in seen,'duplicate/unknown producer task')
        seen.add(task_id); binding=task_binding(plan,challenges,task_id)
        require(data['binding']==binding and data['provenance'] in {'native-model','injected-fixture','tiny-cpu-model'} and
                (data['provenance']=='native-model' or allow_fixture), 'native producer provenance/binding required')
        receipt=data['receipt']
        require(receipt['task_id']==task_id and receipt['status'] in
                {'complete','failed','timeout','oom','worker_crash','not_executed','session_limit','interrupted_pending'} and
                type(receipt['launched']) is bool and (receipt['launched'] or receipt['status'] in {'not_executed','session_limit'}),
                'parent process receipt required')
        require(set(receipt)<= {'task_id','attempt_id','status','launched','returncode','reset_inferred','reserved_seconds',
                    'error_type','error_message'} and receipt.get('reset_inferred') is False,
                'closed parent receipt cannot infer reset')
        if data['provenance']=='native-model' and receipt['status']=='complete':
            require(receipt.get('returncode')==0 and type(receipt.get('returncode')) is int,
                    'native completed receipt requires successful process return')
        events=data['events']; spec=plan['task_specs'][task_id]
        observed,forwards,tokens=check_events(events,binding,spec)
        require(all(type(e.get('test_index',0)) is int and 0<=e.get('test_index',0)<counts[task_id] and
                    (e['event']!='test_terminal' or type(e['result']['test_index']) is int and
                     0<=e['result']['test_index']<counts[task_id]) for e in events), 'unknown/duplicate source test identity')
        checkpoint=data['checkpoint']; tests=[]
        native_gate=None
        if data['provenance']=='native-model' and checkpoint is not None and any(t.get('attempts') for t in checkpoint['tests']):
            native_gate=verify_native_training_gate(source_directory,plan,challenges,task_id,loader,tokenizer)
        if checkpoint is not None:
            require(set(checkpoint)=={'binding','tests','event_count','event_head'} and receipt['launched'] and checkpoint['binding']==binding and
                    type(checkpoint['event_count']) is int and 0 <= checkpoint['event_count'] <= len(events) and
                    checkpoint['event_head']==(digest(binding) if checkpoint['event_count']==0 else events[checkpoint['event_count']-1]['digest']) and
                    len(checkpoint['tests'])==counts[task_id] and
                    [t['test_index'] for t in checkpoint['tests']]==list(range(counts[task_id])),
                    'committed producer checkpoint/test denominator differs')
            committed=events[:checkpoint['event_count']]
            for result in checkpoint['tests']:
                if 'ranked_grids' in result:
                    tests.append(verify_test(challenges,task_id,result,committed,loader,decoder,tokenizer,observed,
                                             spec['maximum_candidate_sequences_per_test'],source_directory,spec['per_test_limits'],
                                             injected=data['provenance']=='injected-fixture',
                                             verification_schedule=spec.get('verification_schedule','interleaved')))
                else:
                    require(set(result)=={'test_index','status','attempts','missing_attempts'} and
                            result['status'] in {'not_executed','budget_stop','timeout','oom','failed','interrupted_pending'} and
                            result['attempts']==[] and result['missing_attempts']==2,'uncommitted test cannot claim candidates')
                    tests.append({**result,'status':'session_limit' if result['status']=='budget_stop' else result['status']})
        else:
            require(receipt['status']!='complete','completed worker needs committed test evidence')
        status=receipt['status']
        if status=='complete':
            status='complete' if len(tests)==counts[task_id] and all(len(t['attempts'])==2 for t in tests) else 'missing-candidate'
        records.append({'task_id':task_id,'status':status,'tests':tests})
        audits.append({'task_id':task_id,'binding':binding,'checkpoint_digest':digest(checkpoint),
                       'events_digest':digest(events),'receipt':receipt,'provenance':data['provenance'],
                       'inference_forwards_reserved':forwards,'physical_input_tokens':tokens,'native_training_gate':native_gate})
    submission,audit=build_submission(challenges,records)
    audit.update(native_plan_digest=digest(plan),native_evidence_digest=digest(evidence),native_tasks=audits,
                 producer_sha256=plan['producer_sha256'],native_records_digest=digest(records),
                 digest_is_execution_attestation=False)
    for row in audit['rows']:
        data=next(d for d in evidence if d['task_id']==row['task_id'])
        cp=data['checkpoint'];result=None if cp is None else cp['tests'][row['test_index']]
        index=row['test_index']
        row.update(test_input_digest=digest(challenges[row['task_id']]['test'][index]),
            native_result_digest=digest(result),native_status=None if result is None else result['status'],
            native_complete=False if result is None else result.get('native_complete',False),
            ranked_candidate_digests=[] if result is None else [digest(g) for g in result.get('ranked_grids',[])],
            source_parse_ranking_digest=digest([e for e in data['events'] if e.get('test_index')==index and
                e['event'] in {'candidate_parsed','candidate_ranked'}]))
        if data['provenance']!='native-model':
            label='injected_fixture' if data['provenance']=='injected-fixture' else 'tiny_cpu_model'
            row['attempt_sources']=[label if p=='model' else p for p in row['attempt_sources']]
    return submission,audit

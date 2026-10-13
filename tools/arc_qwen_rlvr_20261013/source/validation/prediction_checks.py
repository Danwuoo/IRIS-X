"""Target-free generation replay and dev/held-out scores. Never reads PUBLIC gold."""
from .safe_io import need, integer, finite, digest, sha, same, is_sha
from . import grid_checks


def reference(root, value, original_root):
    need(type(value) is dict and is_sha(value.get('file_sha256')), 'file reference hash required')
    name=root.remap(value.get('path'),original_root)
    need(root.file_sha(name)==value['file_sha256'], 'referenced artifact bytes differ: '+name)
    return root.json(name)


def generation(receipt, *, case, operation, adapter, events, inference, synthetic, identities=None, codec=None):
    need(receipt.get('case_id')==case['case_id'] and type(receipt.get('transform')) is int and receipt['transform']==operation, 'generation case/transform differs')
    need(receipt.get('query_targets_used') is False and receipt.get('adapter_sha256')==adapter['adapter_sha256'], 'generation target-free/adapter binding differs')
    status=receipt.get('status');g=receipt.get('generation');p=receipt.get('packing')
    need(status in ('complete','invalid','context-excluded','infrastructure-excluded'), 'closed generation status')
    need(type(g) is dict and type(p) is dict and type(receipt.get('dispatched')) is bool, 'actual generation and prompt packing required')
    need(g.get('dispatched') is receipt['dispatched'] and type(g.get('valid')) is bool, 'generation dispatch/valid type differs')
    if status=='context-excluded':
        need(not g['dispatched'] and not g['valid'] and receipt.get('prediction') is None and p.get('admitted') is False, 'context exclusion cannot become attempted prediction')
        return None
    need(p.get('admitted') is True, 'dispatched generation requires admitted packing')
    grid_checks.packing(p,g,case,operation)
    if codec is not None:codec.generation(g,p)
    ids=g.get('output_token_ids')
    need(type(ids) is list and all(integer(x,0,151935) for x in ids), 'raw output token IDs required')
    need(integer(g.get('output_tokens')) and g['output_tokens']==len(ids) and g.get('output_sha256')==digest(ids), 'raw output token commitment differs')
    # The frozen Qwen grid DFA admits digit15..24, newline198 and EOS151643/151645.
    # No model/tokenizer code is imported to reconstruct this constrained stream.
    mapping={i+15:str(i) for i in range(10)};mapping[198]='\n'
    eos=g.get('native_eos_ids')
    need(eos==[151645,151643], 'fixed native EOS identity differs')
    need(all(x in mapping or x in eos for x in ids), 'token outside pinned native grid alphabet')
    text=''.join(mapping[x] for x in ids if x not in eos)
    need(g.get('text')==text, 'raw tokens and decoded text differ')
    need(len(ids)<=inference['max_new_tokens'], 'generation output cap differs')
    need(g.get('seed')==1917 and type(g.get('seed')) is int and same(g.get('sampling'),{'do_sample':False,'temperature':1.,'top_p':1.}), 'fixed greedy inference/seed differs')
    need(g.get('full_vocabulary_rows')==151936 and g.get('model_identity_sha256')==adapter['base_identity_sha256'], 'actual native model identity differs')
    need(g.get('adapter_state_sha256')==adapter['adapter_sha256'] and g.get('rl_policy_identity',{}).get('policy_version')==adapter['policy_version'], 'generation actual policy differs')
    need(g.get('rl_policy_identity',{}).get('adapter_sha256')==adapter['adapter_sha256'], 'generation RL adapter identity differs')
    for k in ('tokenizer_sha256','native_policy_sha256','constraint_sha256','prompt_contract_sha256','prompt_sha256','rendered_prompt_sha256'):
        need(is_sha(g.get(k)), 'native identity absent: '+k)
        if identities and k in identities:
            need(g[k]==identities[k], 'source-pinned native identity differs: '+k)
    if not synthetic:
        need(g.get('tiny_cpu') is False and g.get('pretrained_weights_loaded') is True and g.get('production_admitted') is True, 'native production material provenance absent')
    event=events.get(g.get('physical_event_id'))
    need(event is not None and event.get('phase') in ('evaluation-generation','public-generation') and event.get('dispatched') is receipt['dispatched'], 'generation physical event missing/misclassified')
    timing=g.get('native_timing',{})
    start,end=timing.get('entered_monotonic'),timing.get('returned_monotonic')
    need(finite(start) and finite(end) and event['started']-0.001<=start<=end<=event['ended']+0.001, 'generation timing outside physical event')
    trace=g.get('forward_trace');need(type(trace) is list and integer(g.get('forward_calls')) and len(trace)==g['forward_calls'], 'physical native forward trace coverage')
    total=0
    for row in trace:
        need(integer(row.get('input_tokens'),1,4096) and finite(row.get('started_monotonic')) and finite(row.get('completed_monotonic')), 'physical forward token/time receipt')
        need(start<=row['started_monotonic']<=row['completed_monotonic']<=end and row.get('finite_full_head') is True, 'physical forward time/finite logit boundary')
        total+=row['input_tokens']
    need(g.get('forward_input_tokens')==total and event.get('input_tokens')==total, 'generation token accounting differs')
    derived=grid_checks.prediction(g,operation)
    if status=='complete':
        need(g['valid'] and derived is not None and same(receipt.get('prediction'),derived), 'complete prediction not actual inverse-transformed valid output')
    else:
        need(not g['valid'] and receipt.get('prediction') is None, 'invalid generation cannot contain successful prediction')
    if status=='invalid':
        need(g.get('finish_reason') not in ('deadline','error','rejected'), 'infrastructure failure mislabeled model-invalid')
    return derived


def validate_scope(root,scope,*,cases,checkpoints,plan,events,original_root,synthetic,identities=None,codec=None):
    seal=root.json(scope+'-prediction-seal.json')
    need(seal.get('sealed') is True and seal.get('scope')==scope, 'scope seal identity')
    payload=reference(root,seal,original_root)
    need(seal.get('payload_sha256')==digest(payload), 'prediction payload SHA differs')
    need(set(payload)=={'format','scope','case_ids','plan_sha256','experiment_plan_sha256','inference_contract','adapter_identities','methods','query_targets_used'}, 'closed prediction payload inventory')
    need(payload.get('scope')==scope and payload.get('format')=='irisx/transfer-sealed-predictions-v1', 'prediction payload format/scope')
    need(payload.get('query_targets_used') is False and payload.get('experiment_plan_sha256')==digest(plan), 'prediction plan/target boundary differs')
    need(same(payload.get('inference_contract'),plan['inference']), 'paired inference policy differs')
    need(set(payload.get('methods',{}))==set(payload.get('adapter_identities',{}))=={'A','B','C'}, 'exact paired arm inventory')
    expected=[c['case_id'] for c in cases]
    need(len(expected)==len(set(expected)) and payload.get('case_ids')==expected, 'fixed ordered case coverage differs')
    generation_events=set();signatures={}
    for arm in ('A','B','C'):
        need(payload['adapter_identities'][arm]==checkpoints[arm]['adapter_sha256'], 'sealed actual adapter differs')
        rows=payload['methods'][arm];need(type(rows) is list and [r.get('case_id') for r in rows]==expected, 'exact ordered arm cases required')
        signatures[arm]=[]
        for index,(row,case) in enumerate(zip(rows,cases)):
            need(set(row)=={'case_id','answers','complete','generations','status'} and type(row['generations']) is list and len(row['generations'])==2, 'exact two-view case structure')
            need(same(root.json(scope+'/'+arm+'/'+str(index).zfill(3)+'-prediction.json'),row), 'durable case row differs')
            answers=[];raw_signatures=[]
            for op,ref in enumerate(row['generations']):
                need(ref is not None, 'missing required generation artifact')
                raw=reference(root,ref,original_root)
                need(same(root.json(scope+'/'+arm+'/'+str(index).zfill(3)+'-'+str(op)+'.json'),raw), 'raw generation file alias')
                for key in ('prediction','status','dispatched','transform'):
                    need(same(raw.get(key),ref.get(key)), 'derived generation reference differs')
                pred=generation(raw,case=case,operation=op,adapter=checkpoints[arm],events=events,inference=plan['inference'],synthetic=synthetic,identities=identities,codec=codec)
                if pred is not None and pred not in answers:
                    answers.append(pred)
                g=raw['generation'];eid=g.get('physical_event_id')
                if raw['dispatched']:
                    need(eid not in generation_events, 'physical generation reused for two views');generation_events.add(eid)
                raw_signatures.append([g.get('output_token_ids'),g.get('text'),g.get('finish_reason'),raw['status'],pred])
            complete=all(g['status']!='infrastructure-excluded' for g in row['generations'])
            need(row['complete'] is complete and row['status']==('complete' if complete else 'incomplete') and same(row['answers'],answers), 'case completeness/dedup answers not derived')
            signatures[arm].append(raw_signatures)
    if checkpoints['B']['counts']['rl_updates']==0:
        need(same(signatures['A'],signatures['B']), 'no-update A/B actual deterministic tokens/text/finish reasons differ')
    return payload,seal,generation_events


def exact_scores(payload,targets):
    need(set(targets)==set(payload['case_ids']), 'authenticated score targets exact coverage')
    scores={}
    for arm,rows in payload['methods'].items():
        need(all(r['complete'] for r in rows), 'incomplete scope cannot be scored')
        hits=[r['case_id'] for r in rows if targets[r['case_id']] in r['answers']]
        scores[arm]={'exact':len(hits),'denominator':len(rows),'exact_case_ids':hits,'prediction_file_bound':True}
    return scores


def validate_scores(root, dev, holdout, devseal, holdoutseal, targets):
    devscores=exact_scores(dev,targets['dev']);selection=root.json('dev-selection.json')
    selected=max(('A','B','C'),key=lambda a:devscores[a]['exact'])
    need(same(selection,{'selected_arm':selected,'rule':'dev-exact-fixed-tie-A-B-C','scores':devscores,
                         'dev_prediction_file_sha256':devseal['file_sha256'],'holdout_labels_opened':False}), 'dev-only exact selection or tie rule differs')
    heldscores=exact_scores(holdout,targets['holdout']);held=root.json('holdout-scores.json')
    paired={a:{'gained_case_ids':sorted(set(heldscores[a]['exact_case_ids'])-set(heldscores['A']['exact_case_ids'])),
               'lost_case_ids':sorted(set(heldscores['A']['exact_case_ids'])-set(heldscores[a]['exact_case_ids']))} for a in ('B','C')}
    need(held.get('scope')=='reused-experiment-heldout-not-pristine-confirmation' and held.get('selection')==selected and
         held.get('prediction_file_sha256')==holdoutseal['file_sha256'] and same(held.get('scores'),heldscores) and same(held.get('paired_vs_A'),paired), 'held-out sealed score/paired cases differ')
    return {'selected_arm':selected,'dev_scores':devscores,'holdout_scores':heldscores,'paired_vs_A':paired}

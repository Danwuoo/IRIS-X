"""Persist-first bounded empirical cache fidelity; raw allclose is diagnostic only.

Neither this experiment nor its four-step controls assert universal equality.
Invalid, late, nonfinite, nondeterministic reference or reset evidence is fatal.
"""
from copy import deepcopy
from pathlib import Path
import time
from .protocol import require,digest
from .decoder import cache_length,cache_metadata
from tools.arc_learning_agent_20261011.budget import atomic_json

CACHE_POLICY={
 'format':'irisx/qwen14b-cache-behavior-policy-v2',
 'length_ladder':[128,512,2048], 'states':['base','updated','restored'],
 'kinds':['grid','program'], 'steps':4, 'minimum_steps_per_kind':2, 'stress_fixture_not_arc_prompt':True, 'atol':0.01,'rtol':0.01,
 'head_rows':151936,'max_grid_allowed_tokens':128,'top_k':8,'max_failure_examples':16,
 'prefix':'exact prepared rung input_ids minus final three tokens',
 'trajectory':'prefill full reference chooses initial token; both paths then consume the same reference-selected history',
 'grid_choice':'native grid DFA allowed_tokens from generated reference suffix, including EOS',
 'program_choice':'unconstrained full-native-head greedy argmax',
 'reference_repeat':'bitwise identical full-prefix logits at every compared step',
 'admission':'finite complete head, exact cache/position/mask invariants, deterministic repeat-full and every chosen token identical including the exact-rung unconstrained argmax',
 'numeric_rule':'original torch.allclose(.01,.01) retained unchanged and separately disclosed',
 'mismatch':'behavior mismatch denies cache only; fatal invalid/late/nonfinite/reference-repeat/reset denies all science',
 'claim':'bounded empirical greedy fidelity on synthetic128/512/2048 controls; no ARC-semantic or universal equivalence claim',
}


def choose(logits,allowed=None):
    import torch
    if allowed is None:return int(logits.argmax().item())
    require(bool(allowed),'empty grid DFA admissible set')
    ids=torch.tensor(allowed,dtype=torch.long,device=logits.device)
    return int(ids[logits.index_select(0,ids).argmax()].item())


def comparison(cached,full,allowed=None):
    """Input tensors are materialized CPU float32; metrics serialize without NaN."""
    import torch
    require(allowed is None or len(allowed)<=128,'bounded native grid admissible set exceeded')
    a=cached.detach().float().cpu().flatten();b=full.detach().float().cpu().flatten()
    finite=bool(torch.isfinite(a).all() and torch.isfinite(b).all())
    result={'atol':.01,'rtol':.01,'head_rows':int(b.numel()),'finite':finite,
            'cached_nonfinite':int((~torch.isfinite(a)).sum()),'full_nonfinite':int((~torch.isfinite(b)).sum()),
            'strict_allclose':False,'strict_original_violating_logits':None,'chosen_token_equal':False,'metrics':None}
    if not finite or a.shape!=b.shape:return result
    ad=a.double();bd=b.double();error=(ad-bd).abs();den=.01+.01*bd.abs();violations=~torch.isclose(a,b,atol=.01,rtol=.01)
    ca,cb=ad-ad.mean(),bd-bd.mean();pa=torch.softmax(a.double(),-1);pb=torch.softmax(b.double(),-1)
    kl=float((pb*(torch.log_softmax(b.double(),-1)-torch.log_softmax(a.double(),-1))).sum())
    def head(x):
        vals,ids=x.topk(min(8,x.numel()))
        eligible=x if allowed is None else x[torch.tensor(allowed)]
        top=eligible.topk(min(2,eligible.numel())).values
        return {'argmax':int(x.argmax()),'top_tokens':ids.tolist(),'top_logits':vals.tolist(),
                'chosen_token':choose(x,allowed),'chosen_token_logit':float(x[choose(x,allowed)]),
                'allowed_logits':x[torch.tensor(allowed)].tolist() if allowed is not None else None,'choice_margin':float(top[0].double()-top[1].double()) if len(top)>1 else None}
    ids=violations.nonzero().flatten()[:16].tolist()
    result.update(strict_allclose=bool(torch.allclose(a,b,atol=.01,rtol=.01)),strict_original_violating_logits=int(violations.sum()),
        chosen_token_equal=choose(a,allowed)==choose(b,allowed), cached=head(a),full=head(b),
        allowed_token_count=len(allowed) if allowed is not None else int(b.numel()),
        allowed_token_ids=list(allowed) if allowed is not None else None,
        metrics={'max_abs_error':float(error.max()),'mean_signed_offset':float((ad-bd).mean()),
            'abs_error_quantiles':{str(q):float(torch.quantile(error,q)) for q in (0.,.5,.9,.99,1.)},
            'violating_logits':int(violations.sum()),'max_normalized_error':float((error/den).max()),
            'centered_max_abs_error':float((ca-cb).abs().max()),'reference_to_cached_kl':kl,
            'probability_total_variation':float((pa-pb).abs().sum()/2)},
        failure_examples=[{'token_id':i,'cached':float(a[i]),'full':float(b[i]),'abs_error':float(error[i])} for i in ids])
    return result


def token_cache_panel(model,ledger,token_ids,event,deadline,path):
    import torch
    from transformers import __version__ as transformers_version
    import peft
    require(len(token_ids) in CACHE_POLICY['length_ladder'],'exact rung required')
    raw=model.model;device=next(raw.parameters()).device;old_training=raw.training;raw.eval()
    start=time.monotonic();before=dict(ledger.used)
    receipt={'format':'irisx/qwen14b-cache-panel-v1','event':event,'length':len(token_ids),
        'policy':deepcopy(CACHE_POLICY),'policy_sha256':digest(CACHE_POLICY),'status':'running','fatal_error':None,
        'strict_numerical_allclose':False,'behavioral_cache_admitted':False,'forwards':[],'panels':[],'numerical_rung':{'status':'not_attempted','metrics':None},
        'environment':{'torch':str(torch.__version__),'transformers':transformers_version,'peft':peft.__version__,
            'device':str(device),'attention_implementation':getattr(raw.config,'_attn_implementation',None),
            'deterministic_algorithms':bool(torch.are_deterministic_algorithms_enabled()),
            'tf32':bool(torch.backends.cuda.matmul.allow_tf32),'training_before':bool(old_training)}}
    def persist():
        receipt['elapsed_seconds']=time.monotonic()-start
        receipt['physical_usage']={k:ledger.used[k]-before[k] for k in ledger.used}
        atomic_json(path,receipt)
    def forward(ids,history,past,suffix,use_cache):
        eid=event+'-'+suffix;cache_before=cache_length(past,raw.config,device) if past is not None else 0
        position_start=len(history)-len(ids)
        row={'event_id':eid,'input_ids':list(ids),'history_sha256':digest(history),'input_ids_sha256':digest(ids),
             'input_tokens':len(ids),'history_tokens':len(history),'attention_mask_tokens':len(history),
             'attention_mask_all_ones':True,'position_ids':list(range(position_start,len(history))),
             'cache_position':list(range(position_start,len(history))), 'cache_before':cache_before,
             'use_cache':use_cache,'past_supplied':past is not None,'work_deadline_monotonic':deadline,'deadline_monotonic':min(deadline,time.monotonic()+120),'cache_after':None,'status':'not_dispatched',
             'logit_shape':None,'nonfinite_logits':None,'finite_full_head':False,'late':False,'elapsed_seconds':0.0}
        receipt['forwards'].append(row);persist();began=time.monotonic();row['started_monotonic']=began;row['deadline_monotonic']=min(deadline,began+120)
        try:
            require(began<row['deadline_monotonic'],'cache forward deadline before dispatch')
            require(ids==history[-len(ids):] and (not use_cache or cache_before==position_start),'input/cache-position invariant failed')
            ledger.reserve(eid,{'scoring_forwards':1,'input_tokens':len(ids)})
            row['status']='dispatched';persist()
            atomic_json(ledger.path.parent/'active-call.json',{'event_id':eid,'status':'active','deadline_monotonic':row['deadline_monotonic'],'work_deadline_monotonic':deadline})
            positions=torch.tensor(row['position_ids'],device=device,dtype=torch.long)
            out=raw(input_ids=torch.tensor([ids],device=device),attention_mask=torch.ones((1,len(history)),device=device,dtype=torch.long),
                    past_key_values=past,position_ids=positions.unsqueeze(0),cache_position=positions,
                    use_cache=use_cache,logits_to_keep=1)
            # Materialize first. Timing/deadline decisions must include queued CUDA work.
            values=out.logits.detach().float().cpu().clone()
            if device.type=='cuda':torch.cuda.synchronize(device)
            completed=time.monotonic()
            row.update(completed_monotonic=completed,elapsed_seconds=completed-began,late=completed>=row['deadline_monotonic'],
                       logit_shape=list(values.shape),nonfinite_logits=int((~torch.isfinite(values)).sum()))
            row['finite_full_head']=list(values.shape)==[1,1,151936] and row['nonfinite_logits']==0
            row['logits_sha256']=__import__('hashlib').sha256(values.numpy().tobytes()).hexdigest()
            row['cache_layers']=cache_metadata(out.past_key_values,raw.config) if use_cache and out.past_key_values is not None else []
            row['cache_after']=int(out.past_key_values.get_seq_length()) if use_cache and out.past_key_values is not None else None
            row['returned_cache']=out.past_key_values is not None
            ledger.complete(eid,{'scoring_forwards':1,'input_tokens':len(ids)})
            row['status']='complete';persist()
            if use_cache:cache_length(out.past_key_values,raw.config,device)
            require(row['finite_full_head'],'nonfinite/non-native full cache head')
            require(not row['late'],'late synchronized cache forward')
            require(not use_cache or row['cache_after']==len(history),'cache length did not grow exactly')
            require(use_cache or not row['returned_cache'],'full-prefix unexpectedly returned cache')
            return values[0,-1],out.past_key_values if use_cache else None
        except BaseException as exc:
            if eid in ledger.pending:ledger.unknown(eid,type(exc).__name__)
            row.update(status='failed',error=type(exc).__name__+': '+str(exc)[:512],elapsed_seconds=time.monotonic()-began)
            persist();raise
        finally:
            atomic_json(ledger.path.parent/'active-call.json',{'event_id':eid,'status':'closed','deadline_monotonic':row['deadline_monotonic'],'work_deadline_monotonic':deadline})
    persist()
    try:
        with torch.inference_mode():
            # Exact-rung all-logit diagnostic is always measured, independently of EOS.
            receipt['numerical_rung']={'status':'attempted_incomplete','metrics':None};persist()
            pre,past=forward(token_ids[:-1],token_ids[:-1],None,'numeric-prefill',True)
            numeric_ids=token_ids[:-1]+[choose(pre)]
            receipt['numerical_reference_token']=numeric_ids[-1]
            cached,_=forward(numeric_ids[-1:],numeric_ids,past,'numeric-cached',True)
            full,_=forward(numeric_ids,numeric_ids,None,'numeric-full',False)
            repeat,_=forward(numeric_ids,numeric_ids,None,'numeric-repeat',False)
            receipt['numerical_rung']={**comparison(cached,full),'status':'complete','completed_monotonic':time.monotonic(),'deadline_monotonic':deadline}
            receipt['numerical_reference_repeat_exact']=bool(torch.equal(full,repeat));persist()
            require(receipt['numerical_reference_repeat_exact'],'full-prefix reference repeat differs')
            require(time.monotonic()<deadline,'late numerical comparison')
            for kind in CACHE_POLICY['kinds']:
                sequence=list(token_ids[:-3]);suffix=[];past=None
                panel={'kind':kind,'prefix_sha256':digest(sequence),'prefix_tokens':len(sequence),
                       'planned_max_steps':4,'actual_steps':0,'terminated_on_eos':False,'steps':[]}
                receipt['panels'].append(panel)
                for step in range(CACHE_POLICY['steps']):
                    allowed=model.constraint.allowed_tokens(suffix) if kind=='grid' else None
                    cached,past=forward(sequence if past is None else sequence[-1:],sequence,past,kind+'-'+str(step)+'-cached',True)
                    full,_=forward(sequence,sequence,None,kind+'-'+str(step)+'-full',False)
                    repeat,_=forward(sequence,sequence,None,kind+'-'+str(step)+'-repeat',False)
                    result=comparison(cached,full,allowed)
                    row={'step':step,'history_tokens':len(sequence),'history_sha256':digest(sequence),
                         'reference_suffix_ids':list(suffix),'reference_repeat_exact':bool(torch.equal(full,repeat)),
                         'comparison':result,'comparison_completed_monotonic':time.monotonic(),'deadline_monotonic':deadline,'reference_selected_token':choose(full,allowed)}
                    panel['steps'].append(row);panel['actual_steps']=len(panel['steps']);persist()
                    require(row['reference_repeat_exact'],'full-prefix reference repeat differs')
                    require(time.monotonic()<deadline,'late behavioral comparison')
                    sequence.append(row['reference_selected_token']);suffix.append(row['reference_selected_token'])
                    if row['reference_selected_token'] in model.eos_ids:
                        panel['terminated_on_eos']=True;break
        comparisons=[receipt['numerical_rung']]+[s['comparison'] for p in receipt['panels'] for s in p['steps']]
        behavioral=[s['comparison'] for p in receipt['panels'] for s in p['steps']]
        receipt['strict_numerical_allclose']=all(c['strict_allclose'] for c in comparisons)
        receipt['coverage_sufficient']=all(p['actual_steps']>=2 for p in receipt['panels'])
        receipt['behavioral_cache_admitted']=receipt['coverage_sufficient'] and all(c['chosen_token_equal'] for c in comparisons)
        require(time.monotonic()<deadline,'late cache panel admission')
        receipt['status']='complete'
    except BaseException as exc:
        receipt['status']='fatal';receipt['fatal_error']=type(exc).__name__+': '+str(exc)[:512]
        raise
    finally:
        raw.train(old_training);persist()
    return receipt

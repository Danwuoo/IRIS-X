"""Source-declared successor profiles and a replayable cost-only decision tree."""
from copy import deepcopy
import math
import time
from .protocol import PROTOCOL,require,digest
from .cache_policy import CACHE_POLICY
from tools.arc_learning_agent_20261011.grid_codec import grid_messages,program_messages
from tools.arc_learning_agent_20261011.budget import BudgetExceeded

PROFILES={
 'full-cache-16':{'decoder_mode':'cached','denominators':{'authored_train_control':6,'authored_disjoint_query':6,'exposed_development':4},
    'grid_output_cap':256,'program_output_cap':256,'checkpoint_updates':[8,16,32],'base_representation':True,
    'development_case_ids':list(PROTOCOL['dev_native_lengths']), 'dev_nll_eligible_case_ids':list(PROTOCOL['dev_nll_eligible_case_ids'])},
 'pilot-cached-13':{'decoder_mode':'cached','denominators':{'authored_train_control':6,'authored_disjoint_query':6,'exposed_development':1},
    'grid_output_cap':64,'program_output_cap':128,'checkpoint_updates':[8,16],'base_representation':False,
    'development_case_ids':['training-dev:b1948b0a'],'dev_nll_eligible_case_ids':['training-dev:b1948b0a']},
 'pilot-full-prefix-13':{'decoder_mode':'full_prefix','denominators':{'authored_train_control':6,'authored_disjoint_query':6,'exposed_development':1},
    'grid_output_cap':64,'program_output_cap':128,'checkpoint_updates':[8,16],'base_representation':False,
    'development_case_ids':['training-dev:b1948b0a'],'dev_nll_eligible_case_ids':['training-dev:b1948b0a']},
}
SELECTABLE_PROFILES=['pilot-cached-13','pilot-full-prefix-13']
REFERENCE_ONLY_PROFILES=['full-cache-16']
FORECAST={'format':'irisx/qwen14b-cost-decision-v2','safety_multiplier':1.5,'fixed_overhead_seconds':600,
    'cpu_fixture_overhead_seconds':120,'common_overhead_fraction':0.5,'post_common_overhead_fraction':0.5,'per_generation_work_seconds':115,
    'common_evaluations':2,'branch_evaluations':'len(checkpoint_updates)+1',
    'score_cost_equation':'1.5 * max(2048 * full_seconds_per_input, training_seconds_per_step)',
    'timing':'max synchronized seconds/input for full-prefix and prefill; max single cached decode seconds; max ladder update seconds',
    'fairness':'subtract common forecast and fixed overhead, then identical independent wall/input budgets for grid/program; no transfer',
    'selection':'pilot-cached-13 iff unchanged behavioral admission and feasible; otherwise pilot-full-prefix-13 iff feasible; otherwise diagnostics-only; full-cache-16 is reference-only and nonselectable',
    'forecast_is_guarantee':False,'failure_policy':'stop entire science on any incomplete/late/invalid branch; persist charged work and restore clean state'}


def profile_cases(dataset,name):
    p=PROFILES[name];selected=[c for c in dataset['cases'] if c['scope']!='exposed_development' or c['case_id'] in p['development_case_ids']]
    omitted=[c['case_id'] for c in dataset['cases'] if c not in selected]
    return selected,omitted


def measurements(ladder):
    panels=[s['cache'] for r in ladder['observations'] for s in r['states'].values()]
    forwards=[f for p in panels for f in p['forwards']]
    require(forwards and all(f['status']=='complete' and not f['late'] and f['finite_full_head'] for f in forwards),'invalid capability timing evidence')
    full=[f for f in forwards if not f['use_cache']]
    prefill=[f for f in forwards if f['use_cache'] and not f['past_supplied']]
    decode=[f for f in forwards if f['use_cache'] and f['past_supplied']]
    updates=[r['update'] for r in ladder['observations']]
    require(full and prefill and decode and updates,'complete measured forward/update classes required')
    return {'full_seconds_per_input':max(f['elapsed_seconds']/f['input_tokens'] for f in full),
        'prefill_seconds_per_input':max(f['elapsed_seconds']/f['input_tokens'] for f in prefill),
        'decode_seconds_per_call':max(f['elapsed_seconds'] for f in decode),
        'training_seconds_per_step':max(r['elapsed_seconds'] for r in updates),
        'forward_samples':[{'event_id':f['event_id'],'use_cache':f['use_cache'],'past_supplied':f['past_supplied'],
            'input_tokens':f['input_tokens'],'elapsed_seconds':f['elapsed_seconds']} for f in forwards],
        'update_samples':updates}


def candidate(model,dataset,name,stats,remaining_seconds,remaining_inputs,*,tiny=False,checkpoints=None):
    from .experiment import dimensional_messages
    p=deepcopy(PROFILES[name]);cases,omitted=profile_cases(dataset,name)
    if tiny:
        p.update(grid_output_cap=4,program_output_cap=8,checkpoint_updates=checkpoints or [1,2])
    rows=[]
    def cost(messages,kind):
        cap=p[kind+'_output_cap']
        try:
            _,ids=model._prompt(messages);n=len(ids)
            require(n+cap<=2048,'context: fixed profile prompt reservation exceeds context')
        except ValueError as exc:
            if 'context' not in str(exc).lower():raise
            return {'kind':kind,'prompt_tokens':0,'output_cap':cap,'forward_input_tokens':0,'forecast_seconds':0.,
                    'dispatch_eligible':False,'exclusion':str(exc)}
        forwarded=n+cap-1 if p['decoder_mode']=='cached' else cap*n+cap*(cap-1)//2
        seconds=(n*stats['prefill_seconds_per_input']+(cap-1)*stats['decode_seconds_per_call']) if p['decoder_mode']=='cached' else forwarded*stats['full_seconds_per_input']
        return {'kind':kind,'dispatch_eligible':True,'exclusion':None,'prompt_tokens':n,'output_cap':cap,'forward_input_tokens':forwarded,'forecast_seconds':1.5*seconds}
    for c in cases:
        task={'train':c['demos'],'test':[{'input':c['query_input']}]}
        gens=[cost(grid_messages(c['demos'],c['query_input']),'grid'),cost(program_messages(task),'program')]
        rows.append({'case_id':c['case_id'],'generations':gens})
    rep=[cost(dimensional_messages(c),'grid') for c in cases] if p['base_representation'] else []
    # Bound TF by full 2048-token score even for excluded targets; no savings inferred from correctness or EOS.
    score_inputs=len(cases)*2048
    eval_inputs=sum(g['forward_input_tokens'] for r in rows for g in r['generations'])+score_inputs
    score_seconds=1.5*max(2048*stats['full_seconds_per_input'],stats['training_seconds_per_step'])
    eval_seconds=sum(g['forecast_seconds'] for r in rows for g in r['generations'])+len(cases)*score_seconds
    common_inputs=2*eval_inputs+sum(g['forward_input_tokens'] for g in rep)
    common_seconds=2*eval_seconds+sum(g['forecast_seconds'] for g in rep)
    n_eval=len(p['checkpoint_updates'])+1;steps=max(p['checkpoint_updates'])
    branch_inputs=n_eval*eval_inputs+steps*2048
    branch_seconds=n_eval*eval_seconds+1.5*steps*stats['training_seconds_per_step']
    overhead=120 if tiny else 600
    # Reserve a full worst-case native generation in addition to planned work because the inherited Qwen meter reserves before dispatch.
    reservation_slack=max(sum(1792+i for i in range(p[k+'_output_cap'])) for k in ('grid','program'))+8192
    allowance_inputs=max(0,(remaining_inputs-common_inputs-reservation_slack)//2)
    allowance_seconds=max(0.,(remaining_seconds-common_seconds-overhead)/2)
    max_call=max([g['forecast_seconds'] for r in rows for g in r['generations']]+[g['forecast_seconds'] for g in rep])
    fits=branch_inputs+reservation_slack<=allowance_inputs and branch_seconds<=allowance_seconds and max_call<=115 and score_seconds<=115
    return {'profile_name':name,'profile':p,'profile_sha256':digest(p),'cpu_fixture_only':tiny,
        'selected_case_ids':[c['case_id'] for c in cases],'omitted_case_ids':omitted,
        'case_costs':rows,'representation_costs':rep,'evaluation_count':2+2*n_eval,
        'generation_call_count':len(cases)*2*(2+2*n_eval)+len(rep),
        'score_forecast_seconds_per_call':score_seconds,'score_cost_equation':FORECAST['score_cost_equation'],
        'teacher_forcing_input_bound_per_evaluation':score_inputs,'evaluation_input_tokens':eval_inputs,
        'evaluation_forecast_seconds':eval_seconds,'common_input_tokens':common_inputs,'common_forecast_seconds':common_seconds,
        'per_branch_input_tokens':branch_inputs,'per_branch_forecast_seconds':branch_seconds,
        'per_branch_allowance_input_tokens':allowance_inputs,'per_branch_allowance_seconds':allowance_seconds,
        'reservation_slack_input_tokens':reservation_slack,'fixed_overhead_seconds':overhead,
        'maximum_generation_forecast_seconds':max_call,'total_input_tokens':common_inputs+2*branch_inputs,
        'total_forecast_seconds':common_seconds+2*branch_seconds+overhead,'feasible':fits}


def decide(model,dataset,ladder,ledger,deadline,*,tiny=False,checkpoints=None,test_decoder_mode=None):
    now=time.monotonic();remaining=max(0.,deadline-now);inputs=ledger.caps['input_tokens']-ledger.used['input_tokens']
    stats=measurements(ladder);behavior=ladder['behavioral_cache_admitted']
    require(test_decoder_mode is None or tiny,'test decoder override forbidden in production')
    if test_decoder_mode=='full_prefix':behavior=False
    candidates={n:candidate(model,dataset,n,stats,remaining,inputs,tiny=tiny,checkpoints=checkpoints) for n in SELECTABLE_PROFILES}
    chosen='pilot-cached-13' if behavior and candidates['pilot-cached-13']['feasible'] else 'pilot-full-prefix-13' if candidates['pilot-full-prefix-13']['feasible'] else None
    result={'format':'irisx/qwen14b-feasibility-v2','selectable_profile_ids':SELECTABLE_PROFILES,'reference_only_profile_ids':REFERENCE_ONLY_PROFILES,'forecast_policy':FORECAST,'forecast_policy_sha256':digest(FORECAST),
        'measurements':stats,'decision_monotonic':now,'deadline_monotonic':deadline,'remaining_seconds':remaining,
        'remaining_input_tokens':inputs,'physical_usage_at_decision':dict(ledger.used),'physical_caps':dict(ledger.caps),
        'ledger_head_sha256':ledger._previous,'ledger_event_count':len(ledger.events),'candidates':candidates,'behavioral_cache_admitted':behavior,
        'strict_numerical_allclose':ladder['strict_numerical_allclose'],'selected_profile':chosen,
        'cpu_fixture_only':tiny,'test_decoder_mode':test_decoder_mode,'task_correctness_or_nll_used':False}
    return result


def make_policy(ladder,feasibility):
    name=feasibility['selected_profile'];require(name is None or name in SELECTABLE_PROFILES,'only preregistered pilot profiles selectable');p=feasibility['candidates'][name]['profile'] if name else None
    return {'format':'irisx/qwen14b-decoder-policy-v1','selected_mode':p['decoder_mode'] if p else None,
        'selected_profile':name,'profile':p,'profile_sha256':digest(p) if p else None,
        'cache_policy_sha256':digest(CACHE_POLICY),'protocol_sha256':digest(PROTOCOL),
        'ladder_sha256':digest(ladder),'feasibility_sha256':digest(feasibility),
        'bounded_empirical_cache_fidelity':feasibility['behavioral_cache_admitted'],
        'strict_numerical_allclose':ladder['strict_numerical_allclose'],'immutable':True,
        'numerical_mismatch_disclosure':'raw all-logit .01/.01 diagnostic failed' if not ladder['strict_numerical_allclose'] else None,
        'claim':CACHE_POLICY['claim'],'cpu_fixture_only':feasibility['cpu_fixture_only']}


class BranchLedger:
    """An immutable independent allowance over the one physical ledger."""
    def __init__(self,ledger,*,input_tokens,seconds,name):
        self.parent=ledger;self.name=name;self.before=dict(ledger.used)
        self.input_cap=input_tokens;self.seconds=seconds;self.started=time.monotonic();self.deadline=self.started+seconds
    def __getattr__(self,key):return getattr(self.parent,key)
    def reserve(self,event,amounts):
        if time.monotonic()>=self.deadline:raise BudgetExceeded('independent branch wall allowance exhausted')
        if self.parent.used['input_tokens']-self.before['input_tokens']+amounts.get('input_tokens',0)>self.input_cap:
            raise BudgetExceeded('independent branch input allowance exhausted')
        return self.parent.reserve(event,amounts)
    def receipt(self):
        return {'branch':self.name,'input_allowance':self.input_cap,'seconds_allowance':self.seconds,
            'started_monotonic':self.started,'deadline_monotonic':self.deadline,
            'charged_input_tokens':self.parent.used['input_tokens']-self.before['input_tokens'],
            'elapsed_seconds':time.monotonic()-self.started,'budget_transfer_allowed':False}


def paired_admission(candidate,feasibility,deadline,now):
    retained=candidate['fixed_overhead_seconds']*.5
    required=2*candidate['per_branch_allowance_seconds']+candidate['evaluation_forecast_seconds']+retained
    predicted_common=candidate['common_forecast_seconds']-candidate['evaluation_forecast_seconds']
    elapsed=now-feasibility['decision_monotonic']
    return {'checked_monotonic':now,'global_deadline_monotonic':deadline,
        'retained_overhead_seconds':retained,'common_overhead_allowance_seconds':retained,
        'common_elapsed_seconds':elapsed,'common_forecast_seconds':predicted_common,
        'common_overhead_consumed_seconds':max(0.,elapsed-predicted_common),
        'required_remaining_seconds':required,'remaining_seconds':deadline-now,'admitted':deadline-now>=required}

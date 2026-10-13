"""Measured, target-free cost admission for one fixed prospective portfolio."""
from copy import deepcopy
import time
from .protocol import PROTOCOL,require,digest
from tools.arc_qwen_probe_20261012.cache_policy import CACHE_POLICY
from tools.arc_qwen_probe_20261012.science_profiles import measurements,BranchLedger
from tools.arc_learning_agent_20261011.grid_codec import grid_messages,program_messages

PROFILE_ID='portfolio-cached-63'
FORECAST={'format':'irisx/portfolio-cost-policy-v1','safety_multiplier':1.5,
    'fixed_io_and_closure_seconds':3600,'cpu_fixture_fixed_seconds':300,
    'checkpoint_panel_count':5,'extra_reload_canary_panels':10,
    'canary_score_cases':8,'generation_seconds_per_call_ceiling':115,
    'checkpoint_store_bytes':2*1024**3,'budget_transfer_allowed':False,
    'basis':'same-call synchronized native ladder timings; full reserved outputs; no gold or correctness',
    'no_full_prefix_fallback':True,'forecast_is_guarantee':False}

def decide(model,dataset,ladder,ledger,deadline,*,tiny=False):
    cases=dataset['solver_cases'];require(len(cases)==63,'fixed63 solver panel required')
    require(all('target' not in c for c in cases),'targets denied in forecast')
    stats=measurements(ladder);now=time.monotonic();remaining=max(0.,deadline-now)
    caps={'grid':4,'program':8} if tiny else {'grid':256,'program':256}
    rows=[]
    for case in cases:
        task={'train':case['demos'],'test':[{'input':case['query_input']}]}
        gens=[]
        for kind,messages in (('grid',grid_messages(case['demos'],case['query_input'])),('program',program_messages(task))):
            try:
                _,ids=model._prompt(messages);n=len(ids)
                require(n+caps[kind]<=2048,'context: full prompt/output reservation exceeds2048')
                seconds=1.5*(n*stats['prefill_seconds_per_input']+(caps[kind]-1)*stats['decode_seconds_per_call'])
                gens.append({'kind':kind,'eligible':True,'prompt_tokens':n,'output_cap':caps[kind],
                    'input_bound':n+caps[kind]-1,'forecast_seconds':seconds,'exclusion':None})
            except ValueError as exc:
                if 'context' not in str(exc).lower():raise
                gens.append({'kind':kind,'eligible':False,'prompt_tokens':None,'output_cap':caps[kind],
                    'input_bound':0,'forecast_seconds':0.,'exclusion':str(exc)[:256]})
        rows.append({'case_id':case['case_id'],'scope':case['scope'],'generations':gens})
    panel_seconds=sum(g['forecast_seconds'] for row in rows for g in row['generations'])
    panel_inputs=sum(g['input_bound'] for row in rows for g in row['generations'])
    canary_rows=[r for r in rows if r['scope']=='canary'];require(len(canary_rows)==8,'eight fixed canaries required')
    canary_gen_seconds=sum(g['forecast_seconds'] for row in canary_rows for g in row['generations'])
    canary_gen_inputs=sum(g['input_bound'] for row in canary_rows for g in row['generations'])
    score_seconds=1.5*max(2048*stats['full_seconds_per_input'],stats['training_seconds_per_step'])
    overhead=FORECAST['cpu_fixture_fixed_seconds'] if tiny else FORECAST['fixed_io_and_closure_seconds']
    # One common base panel; each branch two disk-reloaded checkpoint panels.
    # Ten extra full-canary panels conservatively cover before/after reload checks.
    common_seconds=panel_seconds+8*score_seconds+2*canary_gen_seconds+16*score_seconds
    common_inputs=panel_inputs+24*2048+2*canary_gen_inputs
    branch_seconds=2*panel_seconds+16*score_seconds+4*canary_gen_seconds+32*score_seconds+1.5*16*stats['training_seconds_per_step']
    branch_inputs=2*panel_inputs+48*2048+4*canary_gen_inputs+16*2048
    slack=max(sum(1792+i for i in range(caps[k])) for k in caps)+8192
    left_inputs=ledger.caps['input_tokens']-ledger.used['input_tokens']
    allowance_seconds=max(0.,(remaining-common_seconds-overhead)/2)
    allowance_inputs=max(0,(left_inputs-common_inputs-slack)//2)
    maximum_call=max([g['forecast_seconds'] for row in rows for g in row['generations']]+[score_seconds])
    eligible_canaries=all(all(g['eligible'] for g in row['generations']) for row in canary_rows)
    fits=branch_seconds<=allowance_seconds and branch_inputs+slack<=allowance_inputs and maximum_call<=115 and eligible_canaries
    admitted=bool(ladder['behavioral_cache_admitted'] and fits)
    profile={'profile_id':PROFILE_ID,'decoder_mode':'cached','grid_output_cap':caps['grid'],'program_output_cap':caps['program'],
        'checkpoint_updates':[8,16],'denominators':deepcopy(PROTOCOL['denominators']),
        'selected_case_ids':[c['case_id'] for c in cases],'cpu_fixture_only':tiny}
    return {'format':'irisx/portfolio-feasibility-v1','admitted':admitted,'selected_profile':PROFILE_ID if admitted else None,
        'profile':profile,'profile_sha256':digest(profile),'forecast_policy':FORECAST,'forecast_policy_sha256':digest(FORECAST),
        'measurements':stats,'case_costs':rows,'decision_monotonic':now,'deadline_monotonic':deadline,
        'remaining_seconds':remaining,'remaining_input_tokens':left_inputs,'physical_usage_at_decision':dict(ledger.used),
        'ledger_head_sha256':ledger._previous,'ledger_event_count':len(ledger.events),'behavioral_cache_admitted':ladder['behavioral_cache_admitted'],
        'strict_numerical_allclose':ladder['strict_numerical_allclose'],'all_canaries_prompt_eligible':eligible_canaries,
        'common_forecast_seconds':common_seconds,'common_input_tokens':common_inputs,'fixed_overhead_seconds':overhead,
        'common_reserve_seconds':overhead,'fresh_backend_reconstruction_included':True,
        'per_branch_forecast_seconds':branch_seconds,'per_branch_allowance_seconds':allowance_seconds,
        'per_branch_input_bound':branch_inputs,'per_branch_allowance_input_tokens':allowance_inputs,
        'maximum_call_forecast_seconds':maximum_call,'total_forecast_seconds':common_seconds+2*branch_seconds+overhead,
        'task_correctness_or_targets_used':False,'cpu_fixture_only':tiny,'budget_transfer_allowed':False,
        'reason':'admitted' if admitted else 'cache-behavior-not-admitted' if not ladder['behavioral_cache_admitted'] else 'fixed-panel-cost-or-canary-context-not-admitted'}

def make_policy(ladder,feasibility):
    profile=feasibility['profile'] if feasibility['admitted'] else None
    return {'format':'irisx/qwen14b-decoder-policy-v1','selected_mode':'cached' if profile else None,
        'selected_profile':PROFILE_ID if profile else None,'profile':profile,'profile_sha256':digest(profile) if profile else None,
        'cache_policy_sha256':digest(CACHE_POLICY),'protocol_sha256':digest(PROTOCOL),'ladder_sha256':digest(ladder),
        'feasibility_sha256':digest(feasibility),'bounded_empirical_cache_fidelity':ladder['behavioral_cache_admitted'],
        'strict_numerical_allclose':ladder['strict_numerical_allclose'],'immutable':True,
        'numerical_mismatch_disclosure':None if ladder['strict_numerical_allclose'] else 'raw .01/.01 allclose diagnostic failed',
        'claim':CACHE_POLICY['claim'],'cpu_fixture_only':feasibility['cpu_fixture_only']}

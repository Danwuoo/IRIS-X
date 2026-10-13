"""Target-free complete-panel cost admission; optional branches never shrink panels."""
from copy import deepcopy
import math
import time
from .protocol import PROTOCOL,require,digest
from .call_policy import generation_window, policy as call_policy, finite_clock

PROFILE_ID='true-arc-transfer-c4096'


def counts(cases,ttt_ids):
    chosen=[c for c in cases if c['parent_id'] in ttt_ids]
    require(len(chosen)==len(set(ttt_ids)),'complete fixed TTT subset required')
    D=sum(len(c['demos']) for c in chosen);N=len(chosen)
    return {'parents':N,'demonstrations':D,'training_updates':16*(D+N),
        'fold_generations':3*D,'fold_scores':3*D,'query_generations':6*N,
        'generation_calls':3*D+6*N,'full_demo_retrains':N,'outer_fold_retrains':D}


def forecast(stats,*,updates,generations,scores=0,reloads=0,tiny=False,generation_cap=None):
    for key in ('training_seconds_per_step','prefill_seconds_per_input','decode_seconds_per_call','full_seconds_per_input'):
        require(type(stats.get(key)) in (int,float) and math.isfinite(stats[key]) and stats[key]>=0,'measured finite timing required')
    cap=generation_cap if generation_cap is not None else 4 if tiny else PROTOCOL['grid_output_cap']
    fixed=stats.get('generation_fixed_seconds',0)
    require(type(fixed) in (int,float) and math.isfinite(fixed) and fixed>=0,'finite fixed generation overhead required')
    gen=fixed+PROTOCOL['prompt_cap']*stats['prefill_seconds_per_input']+(cap-1)*stats['decode_seconds_per_call']
    score=max(PROTOCOL['context_limit']*stats['full_seconds_per_input'],stats['training_seconds_per_step'])
    # Each full14B reread gets the measured original load duration plus150s IO.
    reload_seconds=max(2 if tiny else 150,stats.get('backend_load_seconds',0))
    seconds=1.5*(updates*stats['training_seconds_per_step']+generations*gen+scores*score+reloads*reload_seconds)
    return {'updates':updates,'generations':generations,'scores':scores,'fresh_reloads':reloads,
        'forecast_seconds':seconds,'input_tokens':updates*4096+generations*(3072+cap-1)+scores*4096,
        'generation_seconds':gen,'generation_fixed_seconds':fixed,'score_seconds':score,'safety_multiplier':1.5,
        'output_cap_reserved':cap,'forecast_is_guarantee':False,'target_outcomes_used':False}


def admission(estimate,ledger,deadline,*,tiny=False):
    reserve=5 if tiny else 600
    # Native meter reserves a full-prefix bound before a cached call; reserve it,
    # although actual receipts charge cached forwards only.
    cap=estimate['output_cap_reserved']; slack=sum(3072+i for i in range(cap))+4096
    now=time.monotonic();finite_clock(deadline,'forecast branch deadline')
    remaining=max(0,deadline-now)
    generation_work=max(0,generation_window(deadline,now=now)['work_deadline_monotonic']-now) if remaining else 0
    score_hard=min(120.,remaining);score_work=score_hard-min(5.,score_hard*.1)
    generation_fits=not estimate['generations'] or 1.5*estimate['generation_seconds']<=generation_work
    score_fits=not estimate['scores'] or 1.5*estimate['score_seconds']<=score_work
    call_fits=generation_fits and score_fits
    allowed=call_fits and estimate['forecast_seconds']+reserve<=remaining and estimate['input_tokens']+slack<=ledger.caps['input_tokens']-ledger.used['input_tokens']
    return {**estimate,'admitted':bool(allowed),'decision_monotonic':now,'branch_deadline_monotonic':deadline,'remaining_seconds':remaining,'closure_reserve_seconds':reserve,
        'reservation_slack_input_tokens':slack,'ledger_head_sha256':ledger._previous,'physical_usage_at_decision':dict(ledger.used),
        'generation_call_policy':call_policy(),'generation_work_seconds_available':generation_work,
        'score_work_seconds_available':score_work,'generation_per_call_admitted':generation_fits,'score_per_call_admitted':score_fits,
        'per_call_admitted':call_fits,'actual_timeout_observed':False,
        'reason':'complete-fixed-panel-fits' if allowed else 'forecast-per-call-not-admitted' if not call_fits else 'forecast-complete-fixed-panel-not-admitted'}


def decide(model,dataset,calibration,ledger,deadline,*,tiny=False,checkpoints=None,generation_cap=None,backend_load_seconds=0):
    complete=calibration.get('completed_lengths')==[128,512,2048,4096]
    shortened=tiny and calibration.get('fixture_calibration_lengths')==[128,512] and calibration.get('completed_lengths')==[128,512] and calibration.get('cpu_fixture_only') is True
    require((complete or shortened) and calibration.get('full_state_restoration_verified') is True,'production requires fresh4096 calibration; only explicitly qualifiedtiny may shorten')
    stats=deepcopy(calibration['measurements']);stats['backend_load_seconds']=backend_load_seconds
    checkpoints=checkpoints or ([1,2] if tiny else [64,256])
    estimate=forecast(stats,updates=checkpoints[-1],generations=2*(3*16+2*32),reloads=3,tiny=tiny,generation_cap=generation_cap)
    result=admission(estimate,ledger,deadline,tiny=tiny)
    result['admitted']=result['admitted'] and calibration.get('behavioral_cache_admitted') is True
    result.update(profile_id=PROFILE_ID,measurements=stats,denominators=dataset['denominators'],
        calibration_sha256=digest(calibration),cpu_fixture_only=tiny)
    if not calibration.get('behavioral_cache_admitted'):result['reason']='fresh4096-cache-not-admitted'
    return result


def make_policy(calibration,feasibility):
    return {'format':'irisx/qwen14b-decoder-policy-v1','selected_mode':'cached',
        'selected_profile':PROFILE_ID,'profile':{'profile_id':PROFILE_ID,'decoder_mode':'cached','context_limit':4096,
            'grid_output_cap':1024,'program_output_cap':1024},'calibration_sha256':digest(calibration),
        'protocol_sha256':digest(PROTOCOL),'feasibility_sha256':digest(feasibility),
        'bounded_empirical_cache_fidelity':calibration['behavioral_cache_admitted'],
        'strict_numerical_allclose':calibration['strict_numerical_allclose'],'immutable':True,
        'cpu_fixture_only':feasibility['cpu_fixture_only']}

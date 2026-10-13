"""Measured admission arithmetic only; no extrapolated SFT decoding throughput."""
from dataclasses import dataclass
import math
from .common import need
from .plan import POLICY

def seconds(x,label):
    need(type(x) in (int,float) and math.isfinite(x) and x>=0,'finite '+label)
    return float(x)

def matching_tolerance(b_seconds):
    b=seconds(b_seconds,'B time')
    return min(120.,max(5.,.05*b))

@dataclass(frozen=True)
class PhaseForecast:
    measurement_sha256:str
    evaluation_ABC_seconds:float
    selected_public_seconds:float
    reload_persistence_seconds:float
    cleanup_seconds:float
    control_step_seconds:float
    sample_attempt_seconds:float
    replay_attempt_seconds:float
    control_finalization_seconds:float=300.
    def __post_init__(self):
        need(type(self.measurement_sha256) is str and len(self.measurement_sha256)==64 and
             all(c in '0123456789abcdef' for c in self.measurement_sha256),'actual measurement source digest')
        for k,v in vars(self).items():
            if k!='measurement_sha256':seconds(v,k)
        need(self.control_step_seconds>0 and self.sample_attempt_seconds>0 and self.replay_attempt_seconds>0,
             'positive independently measured phase costs')
    @property
    def protected_seconds(self):
        return self.evaluation_ABC_seconds+self.selected_public_seconds+self.reload_persistence_seconds+self.cleanup_seconds


def admit_next_B(*,forecast,remaining_seconds,b_seconds,c_seconds,next_B_seconds):
    """Every increment reserves its matched control too, before model dispatch.

    Forecast estimates must be supplied by the later source-bound measured plan.
    A caller-created digest is not release authority; production stays closed.
    """
    need(type(forecast) is PhaseForecast,'measured phase forecast')
    remaining=seconds(remaining_seconds,'remaining');b=seconds(b_seconds,'B');c=seconds(c_seconds,'C')
    nxt=seconds(next_B_seconds,'next B work')
    target=b+nxt;owed=max(0.,target-c)
    needed=nxt+owed+matching_tolerance(target)+forecast.protected_seconds
    blockers=[]
    if target>POLICY['audit_rl_cap_seconds']:blockers.append('RL/audit-phase-cap')
    if target+matching_tolerance(target)>POLICY['control_cap_seconds']:blockers.append('matched-control-cap')
    if needed>remaining:blockers.append('paired-evaluation-PUBLIC-closure-reserve')
    return {'admitted':not blockers,'blockers':blockers,'required_remaining_seconds':needed,
        'B_projected_seconds':target,'C_owed_seconds':owed,'matching_slack_seconds':matching_tolerance(target),'protected_seconds':forecast.protected_seconds,
        'scope':'arithmetic-only-not-production-authority','measurement_sha256':forecast.measurement_sha256}


def admit_next_control(*,forecast,b_seconds,c_seconds,remaining_seconds):
    b=seconds(b_seconds,'B');c=seconds(c_seconds,'C');remaining=seconds(remaining_seconds,'remaining')
    epsilon=matching_tolerance(b)
    # Persistence/verification is reserved independently, never padded with sleep.
    nxt=forecast.control_step_seconds
    return {'admitted':c+nxt+forecast.control_finalization_seconds<=min(POLICY['control_cap_seconds'],b+epsilon) and
             nxt+forecast.protected_seconds<=remaining,
            'target_seconds':b,'tolerance_seconds':epsilon,'next_step_seconds':nxt,
            'finalization_reserved_within_target':forecast.control_finalization_seconds,
            'idle_padding_permitted':False,'already_matched':abs(b-c)<=epsilon}


def provisional_forecast():
    return PhaseForecast('222308b47d2a5bdf872d77cbd8969615d38ce61bc3107aff6f6da22bf82ed02c',
        12960.,15030.,2400.,600.,3.,45.,30.,300.)

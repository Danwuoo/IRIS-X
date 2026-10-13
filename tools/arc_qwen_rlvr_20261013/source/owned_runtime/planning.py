"""Frozen source-bound plans, deliberately separate tiny and production shapes."""
from pathlib import Path
import json
from . import ROOT
from .release import source_freeze,need,file_sha

def build_plan(clock, *, fixture):
    from experiment_flow.contracts import ExperimentPlan,Forecast,FixtureShape,canonical
    from rl_session.plan import production_numeric_gate
    if fixture:
        gate={'maximum_absolute_gap':.20,'minimum_unclipped_fraction':1.,'maximum_replay_seconds':30.,
              'maximum_peak_bytes':2**30,'fixture_only':True,'maximum_p95_gap':.05}
        forecast=Forecast('f'*64,'controlled-fixture',1.,18.,1.,1.,120.,10.,5.,5.)
        shape=FixtureShape(dev_cases=2,holdout_cases=2,max_control_updates=16)
    else:
        from .policy import POLICY_SHA256,COST_EVIDENCE_SHA256,load_policy,measured_batch_forecast
        p,e=load_policy();r=p['reserves_seconds'];gate=vars(production_numeric_gate())
        forecast=Forecast(COST_EVIDENCE_SHA256,'v25-source-bound-pending-review',
            float(r['common_setup_calibration_anchor']),measured_batch_forecast([])['seconds'],
            float(p['cost_model']['control_step_forecast_seconds']),float(r['B_finalization']),
            float(r['paired_ABC']),float(r['selected_PUBLIC']),
            float(r['future_common_reload_persistence']),float(r['closure']))
        shape=FixtureShape(anchor_updates=256,parents=32,group_size=8,dev_cases=16,holdout_cases=32,
                           max_sweeps=4,max_control_updates=8192,batch_parents=8)
    return ExperimentPlan(source_freeze(),forecast,clock.origin_monotonic,canonical(gate),shape=shape,
                          output_cap=1 if fixture else 1024,policy_sha256=None if fixture else POLICY_SHA256)

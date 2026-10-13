"""Measured finite batch policy. Cost evidence is not dispatch authority."""
from pathlib import Path
import json, math
from . import ROOT
from .release import need, file_sha
POLICY_SHA256='3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda'
COST_EVIDENCE_SHA256='ae7dbc7584fe9f54db0444f54c72fed8ac2b56031d74f1e0d18f46bb38c8b1f2'

def load_policy():
    p=ROOT/'design/MEASURED-POLICY.json';e=ROOT/'design/COST-EVIDENCE.json'
    need(file_sha(p)==POLICY_SHA256 and file_sha(e)==COST_EVIDENCE_SHA256,'sealed measured policy/cost drift')
    value=json.loads(p.read_text()); evidence=json.loads(e.read_text())
    need(value['evidence_sha256']==COST_EVIDENCE_SHA256 and value['production_admitted'] is False and value['dispatch_authorized'] is False,'cost policy has no release authority')
    return value,evidence

def initial_rollout_forecast():
    p,e=load_policy()
    return p['cost_model']['rollout_factor']*e['public']['observed_generation_metrics']['elapsed_seconds']['sum']/e['public']['views']

def observed_rollout_costs(events):
    rows=[]
    for event in events:
        if event.get('phase')=='rollout-generation' and event.get('dispatched') is True:
            seconds=event.get('seconds')
            need(type(seconds) in (int,float) and math.isfinite(seconds) and seconds>=0,'settled rollout cost including failures required')
            rows.append({'event_id':event['event_id'],'seconds':seconds,'status':event['status']})
    return rows

def measured_batch_forecast(events):
    p,_=load_policy(); rows=observed_rollout_costs(events)
    need(len(rows) in (0,64,128,192,256),'only completed fixed64-slot batch histories admit a next batch')
    # Monotone history includes every dispatched call, even failures. No
    # outcome or reward is available to this cost-only estimator.
    rollout=initial_rollout_forecast();total=0.
    for n,row in enumerate(rows,1):
        total+=row['seconds']
        need(math.isfinite(total),'rollout forecast arithmetic overflow')
        if n%64==0:rollout=max(rollout,1.25*total/n)
    need(math.isfinite(rollout),'finite rollout forecast')
    return {'seconds':64*(rollout+p['cost_model']['replay_forecast_per_trajectory_seconds'])+p['cost_model']['batch_bookkeeping_seconds'],
            'rollout_seconds':rollout,'observations':rows,'completed_batch_boundaries':len(rows)//64,
            'incomplete_dispatched_cost_count':len(rows)%64,'outcome_conditioning':False,
            'policy_sha256':POLICY_SHA256,'cost_evidence_sha256':COST_EVIDENCE_SHA256}

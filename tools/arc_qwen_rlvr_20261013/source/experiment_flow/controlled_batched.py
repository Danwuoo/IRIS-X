"""Source-bound production-shaped controller simulation, no model or real rewards.

Uses real fixed parent metadata and target-free PUBLIC challenges only. Every
sampling/replay/model duration and outcome is explicitly synthetic. It cannot
issue an owned process/scorer or production capability.
"""
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict
import json
from .tests.test_flow import FakeAdapter,Clock,Dataset,GATE
from .contracts import ExperimentPlan,FixtureShape,Forecast,canonical,digest,require,RecoverableWorkError
from .flow import run_local_experiment
from owned_runtime.release import ROOT,source_freeze
from owned_runtime.policy import POLICY_SHA256,COST_EVIDENCE_SHA256,load_policy,measured_batch_forecast
from owned_runtime.public_bridge import PublicSuccessorBridge

class FixedPanel:
    scope='controlled-adapter-fixture';group_size=8
    def __init__(self):
        from tools.arc_qwen_transfer_20261012.data import load_inventory,freeze_panels
        exclusions=json.loads((ROOT/'baseline/panel-freeze/public120-exclusions.json').read_text())
        _,plan=freeze_panels(load_inventory(),exclusions)
        self.parent_ids=tuple(plan['train_ids']);self.plan_sha256=plan['plan_sha256']
    def receipt(self,exposure):
        return {'scope':'controlled-synthetic-no-actual-training-rewards','parent_ids':list(self.parent_ids),
                'plan_sha256':self.plan_sha256,'actual_training_rewards_observed':False,
                'committed_synthetic_exposure':list(exposure),'seeds_independent_of_exposure':True}

class BatchedAdapter(FakeAdapter):
    def __init__(self,clock,branch='mixed',generation_seconds=10.,save_cost=150.,remaining=None):
        super().__init__(clock,branch,step_cost=4.,save_cost=save_cost)
        self.generation_seconds=generation_seconds;self.phase_deadline=float('inf')
        self.attempted_batches=0;self.pending=None;self.phase_order=[]
    def set_phase_deadline(self,deadline):
        require(self.clock()<deadline,'controlled phase expired');self.phase_deadline=deadline
    def _op(self,name,seconds=1.,failed=False):
        if self.clock()+seconds>self.phase_deadline:
            super()._op(name,max(0.,self.phase_deadline-self.clock()),True)
            raise TimeoutError('controlled phase deadline: '+name)
        return super()._op(name,seconds,failed)
    def begin(self,kind,*,deadline):
        require(self.state['stage']=='anchor' and self.state['anchor_updates']==256,'controlled SFT256 required')
        self._op('setup-'+kind);self.state['stage']=kind
    def collect(self,panel,*,sweep,max_new_tokens,deadline):
        require(sweep==self.attempted_batches and self.pending is None,'fixed disjoint controlled prefix')
        self.attempted_batches+=1;parents=panel.parent_ids[sweep*8:(sweep+1)*8]
        rows=[];stopped=False;version=self.identity()['policy_version']
        for parent in parents:
            for slot in range(8):
                row={'parent_id':parent,'slot':slot,'eligible':False,'reward':None,'trajectory':None,'status':'not-reached'}
                rows.append(row)
                if stopped:continue
                if self.branch=='partial' and sweep==1 and len(rows)>5:
                    stopped=True;continue
                if self.clock()+self.generation_seconds>deadline:
                    stopped=True;continue
                self._op('rollout-generation',self.generation_seconds)
                reward=0 if self.branch in ('zero','partial-zero') else 1 if self.branch=='one' else slot%2
                seed=int(digest(['rl-fixed-batch-sampling-v1',POLICY_SHA256,panel.plan_sha256,sweep,parent,slot])[:15],16)
                row.update(eligible=True,reward=reward,status='eligible',trajectory={
                    'dispatched':True,'dispatched_forwards':1,'steps':[{'token':slot}],
                    'seed':seed,'policy_version':version,'synthetic_only':True})
        batch={'id':'controlled-batch-'+str(sweep),'rows':rows,'sweep':sweep,'batch_index':sweep,
            'parent_ids':list(parents),'planned_attempts':64,'session_planned_attempts':256,'planned_parents':32,
            'group_size':8,'sampling_policy_sha256':POLICY_SHA256,'policy_version':version,
            'closed':True,'all_slots_reached':not stopped,'fatal_native_state':False,
            'attempted_batches':self.attempted_batches,'synthetic_only':True}
        self.batches.append(batch);self.pending=batch['id'];return batch
    def acknowledge_batch(self,batch,*,status):
        require(self.pending==batch['id'],'controlled batch acknowledgment');self.pending=None
    def update(self,batch,*,gate_json,deadline):
        require(self.pending==batch['id'] and all(r['eligible'] for r in batch['rows']),'complete pending batch only')
        self.update_calls+=1;self._op('synthetic-replay-backward-commit',158.)
        self.pending=None
        if self.branch=='numeric' and batch['batch_index']==1:
            return {'optimizer_committed':False,'status':'numeric-nonadmission-no-update','synthetic_only':True}
        self.state['weight']+=1;self.state['rl_updates']+=1
        return {'optimizer_committed':True,'status':'committed','synthetic_only':True}
    def reload(self,path,*,deadline):
        require(self.clock()<deadline,'no reload after phase deadline')
        return super().reload(path,deadline=deadline)
    def predict(self,case,*,transform,seed,max_new_tokens,deadline):
        self.phase_order.append(case['scope'])
        if self.clock()>=deadline:raise TimeoutError('controlled prediction deadline')
        self._op('predict',.1);self.predictions+=1
        return {'case_id':case['case_id'],'prediction':[[0]],'dispatched':True,'transform':transform,
                'status':'infrastructure-excluded' if self.branch=='partial-held' and case['scope']=='holdout' else 'complete',
                'adapter_sha256':self.identity()['adapter_sha256'],'query_targets_used':False} if not (self.branch=='partial-held' and case['scope']=='holdout') else {
                'case_id':case['case_id'],'prediction':None,'dispatched':True,'transform':transform,
                'status':'infrastructure-excluded','adapter_sha256':self.identity()['adapter_sha256'],'query_targets_used':False}
    def predict_public(self,case,**kwargs):return self.predict(case,**kwargs)


def run_simulation(output,*,branch='mixed',generation_seconds=10.,remaining=42000.,public=True):
    p,e=load_policy();r=p['reserves_seconds'];clock=Clock()
    shape=FixtureShape(anchor_updates=256,parents=32,group_size=8,dev_cases=16,holdout_cases=32,
                       max_sweeps=4,max_control_updates=8192,batch_parents=8)
    forecast=Forecast(COST_EVIDENCE_SHA256,'controlled-fixture',r['common_setup_calibration_anchor'],
        measured_batch_forecast([])['seconds'],4.,300.,4200.,18000.,2400.,600.)
    plan=ExperimentPlan(source_freeze(),forecast,clock()-(42000.-remaining),GATE,shape=shape,output_cap=1024,policy_sha256=POLICY_SHA256)
    backend=BatchedAdapter(clock,branch,generation_seconds);dataset=Dataset(shape);panel=FixedPanel()
    root=Path(output)
    bridge=PublicSuccessorBridge(plan.sources,solver_root=ROOT.parent/'portfolio63-next-20261012/materials/public120-solver/solver',output_root=root/'public') if public else None
    result=run_local_experiment(backend,dataset,panel,plan,root,clock=clock,public_bridge=bridge)
    return result,backend,dataset,plan

"""Source-bound finite policy and honest admission/phase APIs, not a launcher."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math, time
from .common import need, digest, source_identity
from owned_runtime.policy import POLICY_SHA256,COST_EVIDENCE_SHA256,load_policy
_MEASURED_POLICY,_COST_EVIDENCE=load_policy()

POLICY={
 'format':'local-rl-fixed-batches-plan-v2','anchor_updates':256,'groups':32,'group_size':8,
 'groups_per_batch':8,'batch_slots':64,'planned_attempts':256,'max_batches':4,
 'sampling_policy_sha256':POLICY_SHA256,'cost_evidence_sha256':COST_EVIDENCE_SHA256,
 'max_sweeps':4,'max_rl_updates':4,'max_control_updates':8192,
 'audit_rl_cap_seconds':7200.,'control_cap_seconds':7200.,
 'global_seconds':43200.,'inner_seconds':42000.,'outer_seconds':42180.,'provider_seconds':42300.,
 'anchor_learning_rate':2e-4,'anchor_schedule':'historical-full256-warmup4-cosine-minratio0.1',
 'training_sampler':'native-objective-family-order-v1-grid-only-seed1917-continuous-anchor-control',
 'rl_learning_rate':1e-6,'control_learning_rate':2e-4,'continuation_schedule':'constant-new-optimizer',
 'sampling':{'temperature':1.,'top_p':1.,'order':'fixed-disjoint-batch-parent-then-sample','seed_rule':'sha256-policy-original-panel-batch-parent-sample'},
 'reward_record':'identity-transform-last-original-demonstration-LOO',
 'invalid_model_output_reward':0,'infrastructure_reward':None,
 'selection':'dev16-only-fixed-order-tie-break-A-B-C','holdout':'reused-experiment-held-out32',
 'comparison':'intervention-packages-not-objective-only-causal-estimate',
 'public_goal_authority':'original-sealed-scorer-only',
 'production_release_review_sha256':None,'v25_measurements_sha256':None,
 'numeric_gate':{'maximum_p95_gap':.05,'maximum_absolute_gap':.20,'minimum_unclipped_fraction':1.},
 'peak_memory_gate_bytes':{'allocated':72*1024**3,'reserved':80*1024**3},
 'phase_estimates':{'ABC_evaluation':4200.,'selected_PUBLIC':18000.,'reload_persistence':2400.,'closure':600.,
                    'setup_anchor':1800.,'scope':'v25-cost-only-measured-policy-requires-independent-review'},
 'control_matching_tolerance_seconds':'min(120,max(5,0.05*W_B))',
 'measurement_archive_sha256':'222308b47d2a5bdf872d77cbd8969615d38ce61bc3107aff6f6da22bf82ed02c',
 'provisional_defaults_sha256':'ade18b1b05ce9f90d590d94332b406a516b3c89b1cfc02f72a84a483ee6c1d2b',
 'batch_replay_backward_seconds':float(_MEASURED_POLICY['gates']['proposed_cumulative_replay_backward_commit_batch_seconds']),
 'generation_hard_seconds':180.,'replay_backward_soft_seconds':30.,'non_generation_hard_seconds':120.,
}

@dataclass(frozen=True)
class NumericGate:
    maximum_absolute_gap:float
    minimum_unclipped_fraction:float
    maximum_replay_seconds:float
    maximum_peak_bytes:int
    fixture_only:bool=True
    maximum_p95_gap:float=0.05
    maximum_reserved_bytes:int=2**63-1
    maximum_batch_replay_backward_seconds:float|None=None
    def __post_init__(self):
        need(type(self.fixture_only) is bool,'explicit fixture gate scope')
        need(self.maximum_batch_replay_backward_seconds is None or
             type(self.maximum_batch_replay_backward_seconds) in (int,float) and math.isfinite(self.maximum_batch_replay_backward_seconds) and
             0<self.maximum_batch_replay_backward_seconds<=POLICY['audit_rl_cap_seconds'],'separate bounded cumulative replay/backward budget')
        need(all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in
            (self.maximum_absolute_gap,self.maximum_replay_seconds)),'finite gate bounds')
        need(type(self.maximum_p95_gap) in (int,float) and math.isfinite(self.maximum_p95_gap) and self.maximum_p95_gap>=0,
             'finite p95 bound')
        need(type(self.minimum_unclipped_fraction) in (int,float) and 0<=self.minimum_unclipped_fraction<=1 and self.maximum_replay_seconds>0,
             'gate range')
        need(type(self.maximum_reserved_bytes) is int and self.maximum_reserved_bytes>0,'reserved memory gate')
        need(type(self.maximum_peak_bytes) is int and self.maximum_peak_bytes>0,'memory gate')


def plan_receipt():
    return {'policy':POLICY.copy(),'sources_sha256':digest(source_identity()),
            'production_admitted':False,'status':'not-admitted',
            'blockers':['independent-runtime-review-pending','production-release-pins-absent',
                        'same-session-full14B-numerical-memory-runtime-admission-pending']}


class Phase(str,Enum):
    CREATED='created'; ANCHOR='anchor'; AUDIT_RL='audit-rl'; CONTROL='control'; EVALUATE='evaluate'; CLOSED='closed'

class PhaseMachine:
    """No callbacks perform hidden model work. Every failed phase still closes.

    External global clock is never reset. Matching uses synchronized model-phase
    wall time (not CUDA-event GPU-active time), including reward/checkpoint/failed
    work. Queue/setup remain separately visible in the unchanged global clock.
    """
    def __init__(self, global_started, *, fixture=False, clock=time.monotonic):
        need(type(global_started) in (int,float) and math.isfinite(global_started),'global origin')
        need(type(fixture) is bool,'explicit fixture')
        self.clock=clock; self.global_started=global_started; self.fixture=fixture
        self.phase=Phase.CREATED; self.arms={}; self.audit=None; self.events=[]; self.sweeps=0
        self._active=None; self._phase_start=None
        self.inference_contract=None; self.evaluations={}; self.selected=None
    def deadline(self): return self.global_started+POLICY['inner_seconds']
    def remaining(self): return max(0.,self.deadline()-self.clock())
    def start(self):
        need(self.fixture,'production phase admission is closed pending measured reviewed plan')
        need(self.phase==Phase.CREATED and self.remaining()>0,'phase/global deadline')
        self.phase=Phase.ANCHOR
    def anchor(self, proof):
        need(self.phase==Phase.ANCHOR and proof.get('reload_verified') is True,'reload-verified anchor required')
        need(proof.get('same_source') is True and proof.get('updates')==(1 if self.fixture else 256),'same-source SFT anchor count')
        self.arms['A']=dict(proof); self.phase=Phase.AUDIT_RL
    def begin_work(self, kind):
        need(self._active is None and self.remaining()>0,'active/expired phase work')
        need(self.phase in (Phase.AUDIT_RL,Phase.CONTROL),'not continuation phase')
        spent=self.additional_seconds('B' if self.phase==Phase.AUDIT_RL else 'C')
        need(spent<7200,'phase cap exhausted')
        event={'arm':'B' if self.phase==Phase.AUDIT_RL else 'C','kind':kind,
               'started':self.clock(),'status':'started','dispatched':False}
        self.events.append(event); self._active=event
        return min(self.deadline(),self.clock()+7200-spent)
    def dispatched(self):
        need(self._active is not None,'no work');self._active['dispatched']=True
    def finish_work(self, status):
        need(self._active is not None and status in ('complete','failed','rolled-back','excluded'),'work status')
        self._active.update(status=status,ended=self.clock(),seconds=self.clock()-self._active['started'])
        self._active=None
    def additional_seconds(self,arm):
        return sum(e.get('seconds',0.) for e in self.events if e['arm']==arm)
    def audit_closed(self, summary, b_proof):
        need(self.phase==Phase.AUDIT_RL and self._active is None,'audit closure boundary')
        need(summary.get('planned_attempts',summary.get('fixed_attempts'))==(2 if self.fixture else 256) and summary.get('closed') is True,
             'closed audit retains planned denominator even incomplete')
        need(summary.get('fatal_native_state') in (None,False) and summary.get('ledger_settled',True) is True,
             'fatal/unsettled native work cannot fall back to evaluation')
        need(summary.get('batches',summary.get('sweeps',1))<=(1 if self.fixture else 4),'fixed batch cap')
        need(b_proof.get('reload_verified') is True and b_proof.get('same_source') is True,'B persisted/reloaded even no-update')
        self.audit=dict(summary);self.arms['B']=dict(b_proof)
        self.arms['B']['no_update']=summary.get('rl_updates',0)==0
        self.arms['B']['audit_complete']=summary.get('not_reached',0)==0
        need(summary.get('partial_batch_optimizer_committed',False) is False,
             'partial current batch cannot commit; previous complete batch updates may remain')
        self.phase=Phase.CONTROL
    def control_closed(self,c_proof,*,tolerance_seconds=None):
        need(self.phase==Phase.CONTROL and self._active is None,'control boundary')
        need(c_proof.get('reload_verified') is True and c_proof.get('same_source') is True,'C reload proof')
        b,c=self.additional_seconds('B'),self.additional_seconds('C')
        # No data-dependent tolerance. Fixture supplies an explicit synthetic one;
        # production has none until reviewed v25-grounded time admission.
        need(self.fixture and type(tolerance_seconds) in (int,float) and math.isfinite(tolerance_seconds) and tolerance_seconds>=0,'source-bound tolerance pending')
        self.arms['C']={**c_proof,'time_match':{'B_seconds':b,'C_seconds':c,
              'tolerance_seconds':tolerance_seconds,'matched':abs(b-c)<=tolerance_seconds,
              'clock':'synchronized-model-phase-wall-includes-failure-and-checkpoint'}}
        self.phase=Phase.EVALUATE
    def evaluation(self, arm, scope, answers, *, inference_contract):
        need(self.phase==Phase.EVALUATE and arm in self.arms and scope in ('dev','holdout'),'evaluation role')
        need((arm,scope) not in self.evaluations,'no repeated adaptive evaluation')
        need(type(answers) is list and len(answers)==(1 if self.fixture else (16 if scope=='dev' else 32)),'paired answer denominator')
        need(all(type(a) is dict and set(a)=={'case_id','answer','status'} for a in answers),'actual answers required')
        need(len({a['case_id'] for a in answers})==len(answers),'duplicate evaluation case')
        previous=next((value for (a,s),value in self.evaluations.items() if s==scope),None)
        need(previous is None or [a['case_id'] for a in previous]==[a['case_id'] for a in answers],
             'paired case order/coverage differs')
        if self.inference_contract is None: self.inference_contract=digest(inference_contract)
        need(self.inference_contract==digest(inference_contract),'arm inference/TTT budget differs')
        if scope=='holdout': need(self.selected is not None,'dev-only selection must precede holdout')
        self.evaluations[arm,scope]=answers
    def select_from_dev(self, counts):
        need(all((a,'dev') in self.evaluations for a in ('A','B','C')),'all paired dev answers first')
        need(set(counts)=={'A','B','C'} and all(type(v) is int and 0<=v<=16 for v in counts.values()),'dev exact counts')
        need(self.selected is None,'selection is frozen')
        self.selected=max(('A','B','C'),key=lambda a:counts[a]);return self.selected
    def close(self,reason='complete'):
        need(self._active is None,'active work must finish/record failure before closure')
        if reason=='complete':need(len(self.evaluations)==6,'all paired dev/holdout actual answers required')
        self.phase=Phase.CLOSED
        return {'status':reason,'arms':self.arms,'selected_from_dev':self.selected,
                'physical_events':self.events,'global_elapsed':self.clock()-self.global_started,
                'production_admitted':False,'holdout_status':'reused-experiment-held-out-not-pristine-confirmation'}


def anchor_lr_multiplier(step):
    need(type(step) is int and step>=0,'integer anchor schedule step')
    if step<4:return (step+1)/4
    progress=min(1.,max(0.,(step-4)/252))
    return .1+.9*.5*(1+math.cos(math.pi*progress))


def production_numeric_gate():
    # Exact source-bound provisional values. Release and v25 measurement freeze
    # remain separate gates; callers cannot substitute a permissive fixture.
    return NumericGate(.20,1.,30.,72*1024**3,False,.05,80*1024**3,POLICY['batch_replay_backward_seconds'])


def cumulative_batch_deadline(gate,admitted_deadline,started,*,fixture):
    need(type(gate) is NumericGate and type(fixture) is bool,'source numeric gate and batch scope')
    need(all(type(v) in (int,float) and math.isfinite(v) for v in (admitted_deadline,started)) and admitted_deadline>started,'finite unexpired admitted batch window')
    budget=gate.maximum_batch_replay_backward_seconds
    need(fixture or budget is not None,'production cumulative replay/backward/commit budget must be source-bound')
    return min(admitted_deadline,started+budget) if budget is not None else admitted_deadline

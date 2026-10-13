"""Explicit test-backend metadata/state-machine E2E, never native/science evidence.
Exercises actual orchestration/selection/sealing/PUBLIC/TTT callsites. Test seams
replace model work, serialization and cost timings with labeled synthetic values.
"""
from contextlib import contextmanager,ExitStack
from copy import deepcopy
import json,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path('/workspace/scratch/3c2b2502fb1e/portfolio63-checkpoint-repair-20261012');SOURCE=Path('/workspace/scratch/3c2b2502fb1e/portfolio63-checkpoint-repair-20261012/final-source-freeze-001');sys.path[:0]=[str(SOURCE),str(SOURCE/'src')]
from tools.arc_qwen_transfer_20261012 import experiment as ex,data as d,checkpoint_policy as cp,decoder
from tools.arc_qwen_portfolio_20261012.checkpoints import _check_update
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json
from tools.arc_qwen_transfer_20261012.protocol import digest,file_sha
from tools.arc_public_research_20261010 import public_data
out=Path('/workspace/scratch/3c2b2502fb1e/portfolio63-checkpoint-repair-20261012/independent-runtime-review/metadata-e2e-replay');out.mkdir(parents=True,exist_ok=False)
dataset=d.build_dataset({'tiny_cpu':True},out/'dataset')
# Only authored fixture DEV targets are opened to define deterministic selector control.
dev_targets=json.loads(Path(dataset['escrow']['dev']['path']).read_text())
ledger=WorkLedger(out/'physical-work.jsonl');events=[]
class Trainer:
    def __init__(self):
        self.trainer=self;self.ledger=ledger;self._counter=0;self.training_receipts=[]
        self.config={'tiny_cpu':True,'task_augmentations':1};self.global_update=0;self.task_update=0;self._task_id=None;self._task_seed=1917
    def freeze_decoder_identity(self,p):events.append({'event':'decoder_identity_handoff','test_backend':True})
    def fingerprint(self):return {'sha256':digest([self.global_update,self._task_id,self.task_update])}
    def state(self):return {'global_update':self.global_update,'task_update':self.task_update,'task_id':self._task_id}
    def charge(self,n):
        self._counter+=1;event='metadata-train-'+str(self._counter);ledger.reserve(event,{'training_steps':n,'input_tokens':n})
        ledger.complete(event,{'training_steps':n,'input_tokens':n},status='complete')
    def train(self,records,*,max_steps,deadline):
        self.charge(max_steps);self.global_update+=max_steps
        r={'status':'complete','optimizer_steps':max_steps,'total_steps':self.global_update,'test_backend':True};self.training_receipts.append(r);return r
    def freeze_global(self):self.selected=self.global_update;events.append({'event':'freeze_selected_global','update':self.global_update})
    def begin_task(self,key):
        assert self._task_id is None;self._task_id=key;self.task_update=0;events.append({'event':'begin_task','global_update':self.global_update,'task':key})
    def adapt_task(self,key,demos,*,max_steps,deadline):
        assert self._task_id==key;self.charge(max_steps);self.task_update+=max_steps
        return {'status':'complete','optimizer_steps':max_steps,'total_steps':self.task_update,'test_backend':True}
    def end_task(self):
        self._task_id=None;self.task_update=0;assert self.global_update==self.selected
        events.append({'event':'reset_task','global_update':self.global_update});return {'adapter_sha256':self.fingerprint()['sha256']}
class Model:
    def __init__(self,tr):self.tr=tr;self.ledger=ledger;self._counter=0;self.identity={'explicit_test_backend':True};self.mode='trained'
    @contextmanager
    def adapter_branch(self,name):
        old=self.mode;self.mode=name
        try:yield
        finally:self.mode=old
    def score_completion(self,*args,**kwargs):return {'valid':True,'dispatched':True,'token_count':1,'nll_sum':1.0,'test_backend':True}
    def close(self):pass

def factory():
    t=Trainer();return Model(t),t

def save(t,root,*,branch_id,update,records,provenance=None,checkpoint_schedule=None,**kw):
    contract=cp.contract(checkpoint_schedule,branch_id);binding={'branch_id':branch_id,'checkpoint_schedule':contract,'config':t.config}
    _check_update(update,binding)
    assert update==(t.task_update if branch_id=='representative_ttt' else t.global_update)
    state=t.state();path=Path(root)/branch_id/('update-%08d'%update);path.mkdir(parents=True,exist_ok=False)
    manifest={'format':'explicit-test-backend-checkpoint-v1','binding':binding,'update':update,'state_sha256':digest(state),'adapter_sha256':t.fingerprint()['sha256'],'test_backend':True}
    atomic_json(path/'manifest.json',manifest,exclusive=True);atomic_json(path/'resume/state.json',state,exclusive=True)
    atomic_json(path/'inference/adapter_model.safetensors.index.json',{'test_backend':True,'binding':binding,'update':update},exclusive=True)
    events.append({'event':'save','branch':branch_id,'update':update,'schedule':checkpoint_schedule})
    return {'path':str(path),'update':update,'manifest_sha256':file_sha(path/'manifest.json'),'state_sha256':digest(state),'adapter_sha256':t.fingerprint()['sha256']}

def load(t,path,*,branch_id,records,expected_manifest_sha256=None,provenance=None,checkpoint_schedule=None,**kw):
    path=Path(path);assert file_sha(path/'manifest.json')==expected_manifest_sha256
    m=json.loads((path/'manifest.json').read_text());s=json.loads((path/'resume/state.json').read_text())
    assert m['binding']['checkpoint_schedule']==cp.contract(checkpoint_schedule,branch_id);_check_update(m['update'],m['binding'])
    assert digest(s)==m['state_sha256'];t.global_update=s['global_update'];t.task_update=s['task_update'];t._task_id=s['task_id']
    events.append({'event':'reload','branch':branch_id,'update':m['update'],'schedule':checkpoint_schedule})
    return {'state_sha256':m['state_sha256'],'update':m['update'],'loaded':True,'test_backend':True}

def generate(model,case,op,path,deadline,*,cap=1024,capture_timing=False):
    # No holdout or PUBLIC target is used; all non-dev outputs are fixed zeros.
    prediction=dev_targets[case['case_id']] if model.mode=='base' and case['case_id'] in dev_targets else [[0]]
    model._counter+=1;event='metadata-generate-'+str(model._counter)
    ledger.reserve(event,{'generation_calls':1,'input_tokens':1,'output_tokens':1});ledger.complete(event,{'generation_calls':1,'input_tokens':1,'output_tokens':1},status='complete')
    path=Path(path);atomic_json(path,{'test_backend':True,'prediction':prediction,'physical_event_id':event},exclusive=True)
    if capture_timing:atomic_json(path.with_suffix('.timing.json'),{'test_backend':True},exclusive=True)
    return {'transform_d4':op,'inverse_applied':True,'prediction':prediction,'dispatched':True,'physical_event_id':event,'receipt_sha256':file_sha(path),'receipt_path':str(path.absolute())}

stats={k:0.0 for k in ('training_seconds_per_step','prefill_seconds_per_input','decode_seconds_per_call','full_seconds_per_input')}
def refresh(root,**kw):
    payload={'selected_estimate':ex.forecast(stats,updates=0,generations=334,reloads=2),'selected_measurements':stats,'test_backend':True}
    path=Path(root)/'test-only-cost-refresh.json';atomic_json(path,payload,exclusive=True)
    return payload,{'path':str(path),'sha256':file_sha(path)}
def pack(model,demos,query,**kw):return [],{'selected_demo_ids':[str(i) for i in range(len(demos))]}
public={'query_inputs':{f'synthetic-{i:03d}':[[[i%10]]] for i in range(167)},
        'demos_tasks':{f'synthetic-{i:03d}':{'demos':[{'input':[[1]],'output':[[2]]}]} for i in range(167)}}
orig_checked=d.checked_json
def guarded(path,*a,**kw):
    assert str(path)!=dataset['escrow']['holdout']['path'],'holdout gold must never open in this test'
    return orig_checked(path,*a,**kw)
model,tr=factory();session=ex.SessionBackend(model,tr,ledger,factory,{'test_backend':True},{'test_backend':True},dataset['manifest'])
with ExitStack() as stack:
    for obj,name,value in [(ex,'save_branch_checkpoint',save),(ex,'load_branch_checkpoint',load),
            (ex,'generate_variant',generate),(ex,'pack_prompt',pack),(ex,'freeze_public_refresh',refresh),
            (ex,'dispose_backend',lambda m,t:{'test_backend_disposed':True}),
            (ex,'_native_admission',lambda model,records,ids:(records,{'test_backend':True})),
            (decoder,'authorize_calibration_reload',lambda *a:None),
            (public_data,'load_solver_tasks',lambda *a:deepcopy(public)),(d,'checked_json',guarded)]:
        stack.enter_context(patch.object(obj,name,value))
    result=ex.run_experiment(session,dataset,out/'experiment',time.monotonic()+43200,
        feasibility={'measurements':stats},config={'tiny_cpu':True,'test_fixture_dataset':True,
        'test_checkpoint_updates':[64,256],'public_solver_root':'explicit-test-backend-public-inputs','public_solver_manifest_sha256':'0'*64})
assert result['error'] is None,result['error']
assert result['status']=='TRANSFER_COMPLETE' and result['operational_success']
assert set(result['checkpoints'])=={'base','sft64','sft256'}
assert result['selection']['candidate_id']=='sft64'
assert result['public_branch']['status']=='PUBLIC_PREDICTIONS_SEALED' and result['public_branch']['method']['candidate_id']=='base'
assert result['public_branch']['cases']==167 and result['public_branch']['actual_generation_calls']==334
assert result['ttt']['status']=='TTT_COMPLETE' and len(result['ttt']['rows'])==16
assert all(r['global_reset_verified'] and set(r['candidate_state_hashes'])=={'ttt0','ttt8','ttt16'} for r in result['ttt']['rows'])
assert len([r for r in result['ttt']['rows'] if r['representative_checkpoint']])==1
reloads=[e['update'] for e in events if e['event']=='reload' and e['branch']=='global_grid']
assert reloads==[64,256,64,0,64],reloads
assert [r['loaded']['update'] for r in result['fresh_backend_reload_receipts']]==reloads
assert session.trainer.global_update==64 and session.trainer._task_id is None and not ledger.pending
receipt={'status':'passed','explicit_test_backend':True,'native_training_claim':False,'scientific_effectiveness_claim':False,
    'production_checkpoint_labels':['base','sft64','sft256'],'global_reload_order':reloads,'global_save_updates':[0,64,256],
    'dev_count':16,'holdout_count':32,'public_input_slots':167,'public_calls':334,'ttt_parents':16,'ttt_labels':[0,8,16],
    'main_selected':'sft64','public_selected':'base','holdout_or_public_gold_opened':False,'events':events,
    'experiment_report_path':str(out/'experiment/full-report.json'),'physical':ledger.summary(),
    'test_seams':['model/backend','checkpoint payload serialization','native admission','calibration handoff','generation','prompt packing','timing estimator','synthetic PUBLIC input source']}
atomic_json(out/'receipt.json',receipt,exclusive=True);print(json.dumps({k:v for k,v in receipt.items() if k not in ('events','physical')},indent=2))

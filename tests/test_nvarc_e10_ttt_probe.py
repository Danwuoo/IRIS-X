"""Literal finite fake-CPU checks. No ML import, model, GPU or provider call."""
from tests.platform_requirements import requires_linux
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import zipfile

from tools import stage_nvarc_e10_ttt_probe as stage
from tools.nvarc_native_multitask import canonical,digest,write
from tools.nvarc_native_solve_runtime import cache_controls
from tools.nvarc_native_ttt_budget import EpochBudget
from tests.test_nvarc_e10_probe import FakeTensor,FakeTorch


def _load_linux_runtime():
    global probe
    from tools import nvarc_e10_ttt_probe as probe

class Number:
    def __init__(self,value=0.001,elements=1):
        self.value=value;self.elements=elements;self.shape=(elements,)
        self.dtype='torch.bfloat16';self.device='cuda:0';self.is_cuda=False;self.requires_grad=True;self.grad=None
    def numel(self):return self.elements
    def element_size(self):return 2
    def detach(self):return self
    def float(self):return self
    def cpu(self):return self
    def square(self):return Number(self.value**2)
    def sum(self):return self
    def sqrt(self):return Number(self.value**.5)
    def __float__(self):return self.value
    def __add__(self,other):return Number(self.value+other.value)


class Finite:
    def all(self):return self
    def item(self):return True
    def __bool__(self):return True


class FakeModel:
    guarded=False
    def __init__(self):
        self.device='synthetic-cpu';self.params=[Number(elements=1044593+(i<166)) for i in range(506)]
        self.pre=[];self.post=[];self.changed=False;self.native_calls=0;self.updates=0
    def parameters(self):return self.params
    def zero_grad(self,set_to_none=True):
        for p in self.params:p.grad=None
    def register_forward_pre_hook(self,fn,with_kwargs):
        self.pre.append(fn);return NS(remove=lambda:self.pre.remove(fn))
    def register_forward_hook(self,fn):
        self.post.append(fn);return NS(remove=lambda:self.post.remove(fn))
    def __call__(self,input_ids,**kwargs):
        if self.guarded:raise RuntimeError('zero-work preparation guard')
        if 'labels' in kwargs:
            for fn in self.pre:fn(self,(),dict(input_ids=input_ids,**kwargs))
            self.native_calls+=1;out={'loss':Number(.125)}
            for fn in self.post:fn(self,(),out)
            return out
        rows,width=input_ids.shape
        return NS(logits=FakeTensor([[[0.]*16 for _ in range(width)] for _ in range(rows)]),past_key_values=object())


class AdamW:
    model=None
    def __init__(self,parameters,lr):
        self.param_groups=[{'params':list(parameters),'lr':lr,'betas':(.9,.999),'eps':1e-8,'weight_decay':0}]
        self.state={}
    def step(self):
        for p in self.param_groups[0]['params']:
            old=self.state.get(p,{}).get('step',0)
            self.state[p]={'step':old+1,'exp_avg':Number(elements=p.numel()),'exp_avg_sq':Number(elements=p.numel())}
        self.model.changed=True;self.model.updates+=1
    def zero_grad(self,set_to_none=True):
        for p in self.param_groups[0]['params']:p.grad=None


class Torch(FakeTorch):
    def __init__(self):
        super().__init__();self.optim=NS(AdamW=AdamW)
    def isfinite(self,_):return Finite()


class Trainer:
    fail_at=None
    def __init__(self,model,material,rates):
        self.model=model;self.material=material;self.rates=rates;self.args=NS()
        self.state=NS(global_step=0,epoch=0);self.optimizer=None;self.lr_scheduler=None
        self.accelerator=NS(_optimizers=[],_schedulers=[])
    def training_step(self,batch):
        if self.fail_at==self.state.global_step:raise RuntimeError('literal fake training failure')
        out=self.model(**batch)
        for p in self.model.parameters():p.grad=Number(elements=p.numel())
        return out['loss']
    def train(self):
        AdamW.model=self.model;self.optimizer=AdamW(self.model.parameters(),self.rates[0])
        self.accelerator._optimizers.append(self.optimizer)
        for i,row in enumerate(self.material['rows']):
            self.training_step({'input_ids':FakeTensor([[i]*row['input_tokens']]),
                'labels':FakeTensor([[-100]*(row['input_tokens']-row['supervised_tokens'])+[i]*row['supervised_tokens']])})
            self.optimizer.param_groups[0]['lr']=self.rates[i]
            self.optimizer.step();self.optimizer.zero_grad(set_to_none=True);self.state.global_step+=1
        self.state.epoch=1


class Engine:
    instances=[];bad_preparation=False
    def __init__(self,root,plan,model,dependency,rank):
        self.root=root;self.plan=plan;self.dependency=dependency;self.torch=Torch();self.model=FakeModel()
        self.loader=self.tokenizer=None;self.rank=rank
        self.baseline=self.inventory();self.instances.append(self)
        adapter=self.adapter(None);self.initial_control=cache_controls(adapter)
        write(root/'workers'/str(rank)/'ready.json',{'rank':rank,'uuid':'fake-'+str(rank),
            'model_material_digest':plan['model_material_digest'],'baseline_digest':digest(self.baseline),
            'torch':'2.8.0+cu128','initial_control_forwards':adapter.completed})
    def inventory(self):
        return [{'name':'p'+str(i),'sha256':('b' if self.model.changed else 'a')*64,
            'shape':[p.numel()],'elements':p.numel(),'finite':True,'dtype':'torch.bfloat16'}
            for i,p in enumerate(self.model.params)]
    def inference(self):pass
    def restore(self):self.model.changed=False
    def trainer(self,texts,rows,output):
        if self.bad_preparation:self.model(input_ids=FakeTensor([[1]]))
        return Trainer(self.model,{'texts':texts,'rows':rows},self.plan['native_source_learning_rates'])


@contextlib.contextmanager
def guard(_torch,_record):
    FakeModel.guarded=True
    try:yield lambda:None
    finally:FakeModel.guarded=False


def fixture(root):
    rates=[0.]+[5e-5]*127+[0.]
    plan={'format':stage.FORMAT,'screen_id':stage.RUN_ID,'run_id':stage.RUN_ID,**stage.BOUNDS,
        'task_order':list(stage.TASKS),'task_ids':list(stage.TASKS),'worker_ids':['0','1','2','3'],
        'model_material_digest':'sha256:'+'a'*64,'runtime_torch_version':'2.8.0+cu128',
        'native_source_learning_rates':rates,'maximum_worker_host_rss_bytes':16*1024**3,
        'maximum_worker_cuda_allocated_bytes':24*1024**3,'maximum_aggregate_host_rss_bytes':64*1024**3,
        'maximum_archive_uncompressed_bytes':64*1024**2,'payload_sha256':{},'task_specs':{}}
    materials={};(root/'materials').mkdir()
    for key,cost in zip(stage.TASKS,stage.COSTS):
        rows=[];texts=[]
        for i in range(128):
            tokens=cost[0]//128+(i<cost[0]%128);supervised=cost[1]//128+(i<cost[1]%128)
            ids=[i]*tokens;labels=[-100]*(tokens-supervised)+[i]*supervised
            rows.append({'row':i,'source_view':str(i),'input_tokens':tokens,'supervised_tokens':supervised,
                'input_ids_digest':digest(ids),'labels_digest':digest(labels),'original_text_sha256':'c'*64})
            texts.append({'text':'fake-demo-'+str(i),'key':str(i)})
        material={'rows':rows,'texts':texts};materials[key]=material
        plan['task_specs'][key]={'training_input_tokens':cost[0],'training_supervised_tokens':cost[1],
            'maximum_sequence_tokens':cost[2],'expected_rows_digest':digest(rows),'texts_digest':digest(texts)}
        write(root/'materials'/f'{key}.json',material)
    write(root/'challenges.json',{key:{'train':[],'test':[]} for key in stage.TASKS})
    for path in [root/'challenges.json',*(root/'materials').iterdir()]:
        plan['payload_sha256'][path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    write(root/'plan.json',plan);write(root/'screen.json',plan)
    return plan,materials


def schedule_fixture(rates):
    from tools.nvarc_native_ttt_schedule import SOURCES, FUNCTIONS
    return {'rates':rates,'source_sha256':SOURCES,'function_sha256':FUNCTIONS,
        'warmup_steps':13,'epoch_steps':128,'reference_rates_sha256':hashlib.sha256(
            json.dumps(rates,separators=(',',':')).encode()).hexdigest(),
        'reference_ulp_distances':[0]*129,'maximum_reference_ulp_distance':0,
        'platform':'literal fake CPU','python':'literal fake Python','model_calls':0,'optimizer_steps':0,
        'policy':'optimizer rate must exactly equal same-platform pinned scalar replay; reference differs by at most four ULPs'}


@requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
class TrainingProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_linux_runtime()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/stage.RUN_ID;self.root.mkdir()
        self.plan,self.materials=fixture(self.root);Engine.instances=[];Engine.bad_preparation=False;Trainer.fail_at=None
    def tearDown(self):self.tmp.cleanup()
    def worker(self,rank=0,expired=False):
        (self.root/'workers'/str(rank)).mkdir(parents=True,exist_ok=True)
        def material(_loader,_tok,key,_task):return self.materials[key]
        with patch.object(stage,'verify_runtime',return_value=self.plan),patch.object(probe,'NativeEngine',Engine),\
             patch.object(probe,'install_owner_guard'),patch.object(probe,'require_worker_receipt'),\
             patch.object(probe,'preparation_guard',side_effect=guard),patch.object(probe,'public_training_material',side_effect=material),\
             patch.object(probe,'native_schedule',return_value=(self.plan['native_source_learning_rates'],
                schedule_fixture(self.plan['native_source_learning_rates']))),\
             patch.object(probe,'wait_for_release',return_value=time.time()+(-1 if expired else 600)):
            return probe.worker(self.root,Path('fake-dependency'),Path('fake-model'),rank,time.time()+2000,os.getpid())
    def test_four_real_budget_fake_epochs_exact_512_updates_28_controls_and_reset(self):
        results=[]
        for rank in range(4):
            self.assertEqual(self.worker(rank),0)
            results.append(probe.verify_worker_result(self.root,self.plan,rank,'fake-'+str(rank)))
        self.assertEqual(sum(r['training']['completed_updates'] for r in results),512)
        self.assertEqual(sum(r['training']['completed_backwards'] for r in results),512)
        self.assertEqual(sum(r['training']['reserved_input_tokens'] for r in results),1588992)
        self.assertEqual(sum(r['training']['reserved_supervised_tokens'] for r in results),789888)
        self.assertEqual(sum(r['controls']['completed_forwards'] for r in results),28)
        self.assertEqual(sum(r['controls']['reserved_physical_input_tokens'] for r in results),672)
        self.assertTrue(all(r['optimizer_discarded'] for r in results))
        self.assertTrue(all(not e.model.changed and all(p.grad is None for p in e.model.params) for e in Engine.instances))
    def test_failure_reservation_counted_no_retry_and_optimizer_discarded(self):
        Trainer.fail_at=7;self.assertEqual(self.worker(),1)
        result=json.loads((self.root/'workers/0/result.json').read_bytes())
        self.assertEqual(result['training']['completed_updates'],7)
        self.assertEqual(result['training']['reserved_backwards'],8)
        self.assertTrue(result['optimizer_discarded']);self.assertEqual(result['controls']['completed_forwards'],7)
        self.assertEqual(Engine.instances[0].model.updates,7)
    def test_preparation_guard_blocks_model_before_any_training(self):
        Engine.bad_preparation=True;self.assertEqual(self.worker(),1)
        result=json.loads((self.root/'workers/0/result.json').read_bytes())
        self.assertEqual(result['training']['completed_updates'],0)
        self.assertIn('zero-work',result['errors'][0]['message'])
        self.assertEqual(Engine.instances[0].model.native_calls,0)
    def test_training_deadline_blocks_model_and_still_resets(self):
        self.assertEqual(self.worker(expired=True),1)
        result=json.loads((self.root/'workers/0/result.json').read_bytes())
        self.assertEqual(result['training']['completed_updates'],0)
        self.assertEqual(result['controls']['completed_forwards'],7)
        self.assertTrue(result['optimizer_discarded'])
    def test_tampered_learning_rate_gradient_and_row_rejected(self):
        self.assertEqual(self.worker(),0)
        path=self.root/'workers/0/training-ledger.json';original=path.read_bytes()
        for mutate in (lambda v:v['optimizer_steps'][13].update(learning_rate=0),
                       lambda v:v['optimizer_steps'][3].update(gradient_tensors=505),
                       lambda v:v['forwards'][3].update(input_ids_digest='sha256:'+'0'*64)):
            value=json.loads(original);mutate(value);write(path,value)
            with self.assertRaises(RuntimeError):probe.verify_worker_result(self.root,self.plan,0,'fake-0')
    def test_literal_over_budget_and_generation_rejected(self):
        state={'forwards':[],'training_steps':[],'optimizer_steps':[{'completed':False}]*129,
            'optimizer_constructions':[],'generation_calls':0,'teacher_calls':0}
        with self.assertRaisesRegex(RuntimeError,'counters'):probe.training_accounting(state,self.plan['task_specs']['195c6913'])
        model=FakeModel();trainer=Trainer(model,{'rows':[]},[0.,0.]);budget=EpochBudget(Torch(),model,trainer,
            [{'input_ids_digest':'x','labels_digest':'y'}],[0.,0.],lambda _:None,
            expected_parameters=528564224,expected_dtype='torch.bfloat16')
        with budget.installed(),self.assertRaisesRegex(RuntimeError,'generation authority'):model.generate()
    def outer(self,code=0):
        capture=b'final coordinator stdout\n';(self.root/probe.OUTPUT_FILE).write_bytes(capture)
        return {'returncode':code,'timed_out':code!=0,'confirmed_stopped':True,'launched':True,
            'hard_deadline_monotonic':time.monotonic()+60,
            'output_capture':{'written':True,'bytes_received':len(capture),'bytes_retained':len(capture),'truncated':False}}
    def test_success_and_failure_zip_contains_post_stop_outer_capture_and_excludes_cache(self):
        self.assertEqual(self.worker(),0)
        cache=self.root/'workers/0/unsloth_compiled_cache';cache.mkdir()
        (cache/'payload.py').write_text('raise AssertionError("cache must never execute")')
        write(self.root/'terminal.json',{'outcome':'failed','cleanup':{'all_producers_stopped':True}})
        observation=self.outer(code=1)
        result=probe.finalize(self.root,observation,hashlib.sha256((self.root/'screen.json').read_bytes()).hexdigest())
        self.assertTrue(result['final_archive_created'],result)
        path=self.root.parent/(self.root.name+'.zip')
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(json.loads(archive.read('outer-supervision.json')),observation)
            self.assertEqual(archive.read('coordinator-output.log'),b'final coordinator stdout\n')
            self.assertIn('workers/0/training-ledger.json',archive.namelist())
            self.assertFalse(any('compiled_cache' in n for n in archive.namelist()))
        original=path.read_bytes();self.assertFalse(probe.finalize(self.root,observation,'bad')['final_archive_created'])
        self.assertEqual(path.read_bytes(),original)
    def test_startup_failure_zip_has_receipt_and_no_reconstructed_model_evidence(self):
        write(self.root/probe.FAILURE_FILE,{'message':'import failed','correctness_scored':False})
        result=probe.finalize(self.root,self.outer(code=1),hashlib.sha256((self.root/'screen.json').read_bytes()).hexdigest())
        self.assertTrue(result['final_archive_created'],result)
        with zipfile.ZipFile(self.root.parent/(self.root.name+'.zip')) as archive:
            self.assertIn('bootstrap-failure.json',archive.namelist());self.assertIn('outer-supervision.json',archive.namelist())
            self.assertFalse(any(n.startswith('workers/') for n in archive.namelist()))
    def test_unconfirmed_producer_cleanup_cannot_archive(self):
        write(self.root/'terminal.json',{'outcome':'failed','cleanup':{'all_producers_stopped':False}})
        result=probe.finalize(self.root,self.outer(1),hashlib.sha256((self.root/'screen.json').read_bytes()).hexdigest())
        self.assertFalse(result['final_archive_created']);self.assertFalse(result['diagnostic_only_archive_created'])
    def test_finalization_deadline_and_oversized_file_fail_before_read(self):
        write(self.root/'terminal.json',{'outcome':'complete','cleanup':{'all_producers_stopped':True}})
        observation=self.outer();observation['hard_deadline_monotonic']=time.monotonic()-1
        pin=hashlib.sha256((self.root/'screen.json').read_bytes()).hexdigest()
        with patch.object(probe,'_read',wraps=probe._read) as reader:
            result=probe.finalize(self.root,observation,pin)
            self.assertFalse(result['final_archive_created']);reader.assert_not_called()
        observation['hard_deadline_monotonic']=time.monotonic()+60
        huge=self.root/'dependency-setup.log'
        with huge.open('wb') as stream:stream.truncate(9*1024**2)
        with patch.object(probe,'_read',wraps=probe._read) as reader:
            result=probe.finalize(self.root,observation,pin)
            self.assertFalse(result['final_archive_created']);self.assertTrue(result['diagnostic_only_archive_created'])
            self.assertFalse(any(call.args[0]==huge for call in reader.call_args_list))
    def test_inert_worker_rejected_before_engine_or_native_import(self):
        write(self.root/'plan.json',{'format':stage.FORMAT,'screen_id':stage.RUN_ID,'run_id':stage.RUN_ID,
            'approved_for_runtime':False,'agent_execution_authorized':False,'resource_admission':None,
            'owner_editor_admission':None,'approved_for_owner_editor':False,'owner_editor_only':True,'kernel_execution_type':'INERT'})
        (self.root/'screen.json').write_bytes((self.root/'plan.json').read_bytes())
        with patch.object(probe,'NativeEngine') as engine,self.assertRaisesRegex(RuntimeError,'approval'):
            probe.worker(self.root,Path('absent'),Path('absent'),0,time.time()+10,os.getpid())
        engine.assert_not_called()
    def test_runtime_import_does_not_import_ml_modules(self):
        command=[sys.executable,'-c',
            "import sys; import tools.nvarc_e10_ttt_probe; assert not {'torch','transformers','unsloth','peft','numpy','tokenizers'} & set(sys.modules)"]
        result=subprocess.run(command,cwd=stage.ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_real_bootstrap_captures_import_failure_before_runtime_admission(self):
        from tools.nvarc_process_supervisor import supervise
        directory=self.root/'tools';directory.mkdir()
        entry=directory/'nvarc_e10_ttt_probe.py';entry.write_bytes(Path(probe.__file__).read_bytes())
        environment=dict(os.environ,PYTHONHASHSEED='0',PYTHONPATH=str(self.root))
        observation=supervise([sys.executable,str(entry),'--bootstrap','--root',str(self.root),'--dependency','absent'],
            env=environment,cwd=self.root,started=time.monotonic(),total_seconds=60,cleanup_seconds=10,
            capture_path=self.root/probe.OUTPUT_FILE)
        self.assertEqual(observation['returncode'],1);self.assertTrue(observation['confirmed_stopped'])
        failure=json.loads((self.root/probe.FAILURE_FILE).read_bytes())
        self.assertEqual(failure['type'],'ModuleNotFoundError')
        self.assertFalse((self.root/'coordinator-admitted.json').exists())
        result=probe.finalize(self.root,observation,hashlib.sha256((self.root/'screen.json').read_bytes()).hexdigest())
        self.assertTrue(result['diagnostic_only_archive_created'],result)
    def test_rendered_inert_notebook_rejects_before_files_or_model_imports(self):
        plan={**self.plan,'approved_for_runtime':False,'local_fixture':False,'approved_for_owner_editor':False}
        raw={'screen.json':canonical(plan)}
        notebook=stage.render(plan,raw)
        with self.assertRaisesRegex(RuntimeError,'inert E10 package'):
            exec(compile(''.join(notebook['cells'][1]['source']),'inert-test','exec'),{})
    def test_barrier_missing_release_times_out(self):
        with self.assertRaisesRegex(RuntimeError,'barrier deadline'):
            probe.wait_for_release(self.root,self.plan,0,time.time()-1)
    def test_frozen_literals_and_admission_reject_automatic_execution(self):
        self.assertEqual(stage.TASKS,('195c6913','aa4ec2a5','a47bf94d','a25697e4'))
        self.assertEqual(stage.BOUNDS['maximum_training_forwards'],512)
        self.assertEqual(stage.BOUNDS['maximum_control_forwards'],28)
        self.assertEqual(stage.BOUNDS['maximum_notebook_wall_seconds'],3600)
        with self.assertRaisesRegex(RuntimeError,'automatic'):
            stage.validate_admission({'approved_for_runtime':True})
    def test_single_run_admission_is_exact_and_separate_from_manual(self):
        from tools.nvarc_notebook_controls import provider_cap_fields,cli_handoff
        admission={'format':stage.RUN_ADMISSION,'run_id':stage.RUN_ID,'owner_instruction_ref':'literal user approval',
            'notebook_ref':stage.NOTEBOOK,'notebook_numeric_id':137327571,'expected_notebook_version':4,
            'kernel_execution_type':'SAVE_AND_RUN_ALL','provider_session_seconds':3600,'private':True,'internet':False,
            'paid_usd_ceiling':0,'charged_quota_seconds_reserved':14400,'quota_snapshot_sha256':'a'*64,
            'quota_observed_at':'2026-10-06T16:00:00+00:00','remaining_free_seconds':20000.,
            'provider_reserved_seconds':0.,'monitor_after_submission':False}
        plan={**self.plan,'resource_admission':admission,'owner_editor_admission':None,
            'approved_for_runtime':True,'agent_execution_authorized':True,'approved_for_owner_editor':False,
            'owner_editor_only':False,'kernel_execution_type':'SAVE_AND_RUN_ALL','notebook_ref':stage.NOTEBOOK,
            'notebook_numeric_id':137327571,'expected_notebook_version':4}
        stage.validate_admission(plan,required=True)
        self.assertEqual(provider_cap_fields(plan)['provider_session_timeout_seconds'],3600)
        self.assertFalse(cli_handoff(plan)['monitor_after_submission'])
        for key,value in [('remaining_free_seconds',14399),('provider_reserved_seconds',1),
                ('paid_usd_ceiling',1),('private',False),('internet',True),('monitor_after_submission',True),
                ('provider_session_seconds',3601),('expected_notebook_version',True),('quota_snapshot_sha256','x')]:
            changed=copy.deepcopy(plan);changed['resource_admission'][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):stage.validate_admission(changed,required=True)
        changed=copy.deepcopy(plan);changed['owner_editor_admission']={}
        with self.assertRaises(RuntimeError):stage.validate_admission(changed)
    def coordinator(self,*,failed_rank=None,overlap=True,ready=True):
        launched=[];stopped=[];root=self.root;plan=self.plan
        class Process:
            pid=1234
            def __init__(self,rank):self.rank=rank;self.stopped=False
            def poll(self):
                if self.rank==failed_rank:return 1
                if self.stopped:return -9
                return 0 if (root/'training-release.json').exists() else None
        def launch(command,**_kwargs):
            rank=int(command[command.index('--rank')+1]);launched.append(rank)
            if ready:write(root/'workers'/str(rank)/'training-ready.json',{'binding':probe.binding(plan,rank),
                'prepared_rows':128,'prepared_rows_digest':plan['task_specs'][plan['task_order'][rank]]['expected_rows_digest'],
                'control_forwards':6,'training_updates':0,'ready_monotonic':10.})
            return Process(rank)
        def stop(process):
            if process.poll() is None:stopped.append(process.rank);process.stopped=True
        def verify(_root,_plan,rank,_uuid):
            return {'peak_host_rss_bytes':100,'training_start_monotonic':10.+rank if overlap else 10.+rank*100,
                'training_end_monotonic':100.+rank if overlap else 20.+rank*100}
        clock=[0.]
        def now():clock[0]+=1 if ready else 100;return clock[0]
        def proof(*_a):write(root/probe.RECEIPT_FILE,{'fake':'receipt'})
        with patch.object(stage,'verify_runtime',return_value=plan),patch.object(probe,'verify_before_prepare',side_effect=proof),\
             patch.object(probe,'verify_mount',return_value={}),patch.object(probe,'prepare',return_value=(Path('fake'),
                [{'uuid':'fake-'+str(i)} for i in range(4)])),patch.object(probe.subprocess,'Popen',side_effect=launch),\
             patch.object(probe,'stop_process',side_effect=stop),patch.object(probe,'verify_worker_result',side_effect=verify),\
             patch.object(probe.time,'monotonic',side_effect=now),patch.object(probe.time,'sleep'),\
             contextlib.redirect_stdout(io.StringIO()):
            code=probe.execute(root,Path('fake'),0.)
        return code,launched,stopped,json.loads((root/'terminal.json').read_bytes())
    def test_parent_barrier_requires_all_four_and_observes_overlap(self):
        code,launched,stopped,terminal=self.coordinator()
        self.assertEqual(code,0);self.assertEqual(launched,[0,1,2,3]);self.assertEqual(stopped,[])
        release=json.loads((self.root/'training-release.json').read_bytes())
        self.assertEqual(release['ranks'],[0,1,2,3]);self.assertEqual(len(release['ready']),4)
        self.assertEqual(terminal['simultaneous_training_overlap_host_seconds'],87.)
        self.assertTrue(terminal['cleanup']['all_producers_stopped'])
        self.assertFalse((self.root.parent/(self.root.name+'.zip')).exists())
    def test_parent_preparation_failure_stops_other_workers_no_release_or_retry(self):
        code,launched,stopped,terminal=self.coordinator(failed_rank=2)
        self.assertEqual(code,1);self.assertEqual(launched,[0,1,2,3]);self.assertEqual(set(stopped),{0,1,3})
        self.assertFalse((self.root/'training-release.json').exists());self.assertTrue(terminal['cleanup']['all_producers_stopped'])
    def test_parent_barrier_deadline_stops_all_unready_workers(self):
        code,launched,stopped,terminal=self.coordinator(ready=False)
        self.assertEqual(code,1);self.assertEqual(set(stopped),{0,1,2,3})
        self.assertFalse((self.root/'training-release.json').exists())
    def test_parent_rejects_nonoverlapping_complete_epochs(self):
        code,_,_,terminal=self.coordinator(overlap=False)
        self.assertEqual(code,1);self.assertLess(terminal['simultaneous_training_overlap_host_seconds'],0)
    def test_fake_counter_booleans_and_float_integers_are_not_receipts(self):
        self.assertEqual(self.worker(),0)
        path=self.root/'workers/0/training-ledger.json';original=json.loads(path.read_bytes())
        for field,value in (('input_tokens',3458.0),('completed',1)):
            ledger=copy.deepcopy(original);ledger['forwards'][0][field]=value
            with self.assertRaises(RuntimeError):probe.training_accounting(ledger,self.plan['task_specs']['195c6913'])
    def test_valid_inventory_can_leave_some_tensors_unchanged(self):
        self.assertEqual(self.worker(),0)
        directory=self.root/'workers/0';trained=json.loads((directory/'trained-inventory.json').read_bytes())
        trained[0]['sha256']='a'*64;write(directory/'trained-inventory.json',trained)
        result=json.loads((directory/'result.json').read_bytes());result['trained_inventory_digest']=digest(trained)
        result['changed_saved_tensor_count']=505;write(directory/'result.json',result)
        self.assertEqual(probe.verify_worker_result(self.root,self.plan,0,'fake-0')['changed_saved_tensor_count'],505)


if __name__=='__main__':unittest.main()

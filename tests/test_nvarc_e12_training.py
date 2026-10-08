"""Exercise installed E12 hooks through literal fake Trainer/Adam operations.

No Torch is installed or imported. These tests establish adapter sequencing and
failure handling, not CUDA/numerical/native runtime qualification.
"""
import copy
import contextlib
from pathlib import Path
import tempfile
from types import ModuleType,SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools import nvarc_e12_training as native
from tools import nvarc_e12_prefix_contract as contract
from tools.nvarc_e12_prefix_fixture import trainer_args
from tools.nvarc_native_multitask import digest
from tools.nvarc_native_solve_runtime import discard_optimizer_state
from tests.test_nvarc_e10_ttt_probe import FakeModel,Number,AdamW,Torch,schedule_fixture
from tests.test_nvarc_e10_probe import FakeTensor


class RandomSampler:
    def __init__(self,data):self.data_source=data;self.num_samples=len(data);self.replacement=False
    def __len__(self):return self.num_samples
    def __iter__(self):yield from reversed(range(len(self.data_source)))
RandomSampler.__module__='torch.utils.data.sampler'


class SeedableRandomSampler(RandomSampler):
    def __iter__(self):yield from super().__iter__()
SeedableRandomSampler.__module__='accelerate.data_loader'


class Trainer:
    def __init__(self,engine,tokens,rates,*,ignore_stop=False,skip_scheduler=False,fail_backward=None):
        self.engine=engine;self.model=engine.model;self.tokens=tokens;self.rates=rates
        self.args=trainer_args();self.state=NS(global_step=0,max_steps=128,epoch=0.)
        self.control=NS(should_training_stop=False);self.optimizer=self.lr_scheduler=None
        self.accelerator=NS(_optimizers=[],_schedulers=[]);self.callbacks=[]
        self.ignore_stop=ignore_stop;self.skip_scheduler=skip_scheduler;self.fail_backward=fail_backward
        self.sampler_converted=False;self.update_calls=0
    def add_callback(self,callback):self.callbacks.append(callback)
    def remove_callback(self,callback):self.callbacks.remove(callback)
    def _get_train_sampler(self):return RandomSampler(self.tokens)
    def create_scheduler(self,num_training_steps,optimizer=None):
        if num_training_steps!=128:raise AssertionError('scheduler horizon changed')
        trainer=self
        class Scheduler:
            def __init__(self):self.index=0
            def step(self):
                self.index+=1
                for group in trainer.optimizer.param_groups:group['lr']=trainer.rates[self.index]
        self.lr_scheduler=Scheduler();self.accelerator._schedulers.append(self.lr_scheduler)
        return self.lr_scheduler
    def training_step(self,batch):
        output=self.model(**batch)
        self.engine.rng+=1
        if self.fail_backward==self.state.global_step:raise RuntimeError('literal failed backward')
        for p in self.model.parameters():p.grad=Number(elements=p.numel())
        return output['loss']
    def train(self):
        # Mirror the important pinned Accelerate conditional: a wrapper object
        # would prevent this conversion and invalidate the source sampler.
        sampler=self._get_train_sampler()
        if isinstance(sampler,RandomSampler):sampler=SeedableRandomSampler(sampler.data_source);self.sampler_converted=True
        AdamW.model=self.model;self.optimizer=AdamW(self.model.parameters(),self.rates[0])
        self.accelerator._optimizers.append(self.optimizer);self.create_scheduler(128)
        for c in self.callbacks:c.on_train_begin(self.args,self.state,self.control)
        for index in sampler:
            token=self.tokens[index]
            self.training_step({'input_ids':FakeTensor([token['input_ids']]),'labels':FakeTensor([token['labels']])})
            self.optimizer.step();self.update_calls+=1;self.optimizer.zero_grad(set_to_none=True)
            if not self.skip_scheduler:self.lr_scheduler.step()
            self.state.global_step+=1;self.state.epoch=self.state.global_step/128
            for c in self.callbacks:c.on_step_end(self.args,self.state,self.control)
            if self.control.should_training_stop and not self.ignore_stop:break


class Engine:
    def __init__(self,root):self.dependency=root;self.model=FakeModel();self.torch=Torch();self.rng=0
    def inventory(self):return [{'state':'changed' if self.model.changed else 'baseline'}]
    def restore(self):self.model.changed=False


SOURCE='''def __iter__(self):
    if self.generator is None:
        seed = int(torch.empty((),dtype=torch.int64).random_().item())
        generator = torch.Generator()
        generator.manual_seed(seed)
    else:
        generator = self.generator
    yield from torch.randperm(n,generator=generator).tolist()
'''


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for path in ('torch/utils/data/sampler.py','accelerate/data_loader.py'):
            target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(SOURCE)
        self.tokens=[dict(input_ids=[1,i+3,2],labels=[-100,i+3,2]) for i in range(128)]
        self.rows=[contract.row_observation(**t) for t in self.tokens]
        self.rates=contract.scalar_reference();self.saved={}
        self.modules={name:ModuleType(name) for name in ('torch','torch.utils','torch.utils.data','torch.utils.data.sampler','transformers')}
        self.modules['torch.utils.data.sampler'].RandomSampler=RandomSampler
        self.modules['transformers'].TrainerCallback=type('TrainerCallback',(),{})
    def tearDown(self):self.temp.cleanup()
    @contextlib.contextmanager
    def environment(self,engine):
        def sourcefile(value):
            return str(self.root/('accelerate/data_loader.py' if value is SeedableRandomSampler else 'torch/utils/data/sampler.py'))
        def rng(state):return dict(python=digest(['p',state]),numpy=digest(['n',state]),torch_cpu=digest(['t',state]),torch_cuda=[digest(['c',state])])
        with patch.dict('sys.modules',self.modules),patch.object(native.inspect,'getsourcefile',side_effect=sourcefile),\
            patch.object(native.inspect,'getsource',return_value=SOURCE),\
            patch.object(native,'capture_rng',side_effect=lambda e:e.rng),\
            patch.object(native,'restore_rng',side_effect=lambda e,s:setattr(e,'rng',s)),\
            patch.object(native,'rng_observation',side_effect=rng),\
            patch.object(native,'write',side_effect=lambda p,v:self.saved.__setitem__(p.name,copy.deepcopy(v))):yield
    def setup(self,arm='ttt64',**kwargs):
        engine=Engine(self.root);trainer=Trainer(engine,self.tokens,self.rates,**kwargs)
        budget=native.PrefixBudget(engine,trainer,self.rows,self.rates,schedule_fixture(self.rates),self.rates,
            self.root,{k:digest(k) for k in contract.SOURCE_FIELDS},arm)
        return engine,trainer,budget
    def run_arm(self,arm):
        engine,trainer,budget=self.setup(arm)
        with self.environment(engine):
            with budget.installed():trainer.train();moments=budget.complete()
            discard_optimizer_state(engine.model,trainer,budget);engine.restore();trace=budget.finish()
        return engine,trainer,budget,moments,trace
    def test_real_hook_sequence64_and128_keeps_sampler_type_and_original_schedule(self):
        _,short,budget,moments,trace=self.run_arm('ttt64')
        self.assertTrue(short.sampler_converted);self.assertEqual(short.update_calls,64)
        self.assertEqual(trace['steps'][0]['prepared_index'],127)
        self.assertEqual(trace['steps'][-1]['prepared_index'],64)
        self.assertEqual(trace['steps'][0]['learning_rates'],[0.])
        self.assertEqual(trace['steps'][0]['parameter_steps_after'],[1]*506)
        self.assertEqual(len(moments),506);self.assertTrue(all(m['step']==64 for m in moments))
        self.assertEqual(short.args.max_steps,-1);self.assertEqual(short.state.max_steps,128)
        self.assertEqual(short.state.epoch,.5);self.assertEqual(short.callbacks,[])
        self.assertIsNone(short.optimizer);self.assertIsNone(budget.optimizer)
        _,long,long_budget,long_moments,long_trace=self.run_arm('ttt128')
        self.assertEqual(long.update_calls,128);self.assertEqual(long.state.epoch,1.)
        self.assertTrue(contract.validate_pair(budget.contract,trace,long_trace)['prefix_verified'])
    def test_ignored_callback_cannot_enter65th_forward_or_optimizer(self):
        engine,trainer,budget=self.setup(ignore_stop=True)
        with self.environment(engine),self.assertRaisesRegex(RuntimeError,'one ordered step|finite dependent'),budget.installed():trainer.train()
        self.assertEqual(engine.model.native_calls,64);self.assertEqual(trainer.update_calls,64)
        self.assertFalse(self.saved['prefix-trace.json']['complete']);self.assertTrue(self.saved['native-hook-status.json']['errors'])
    def test_backward_failure_cannot_be_counted_as_update_and_hooks_restore(self):
        engine,trainer,budget=self.setup(fail_backward=3)
        original_init,original_step,original_iter=AdamW.__init__,AdamW.step,RandomSampler.__iter__
        with self.environment(engine),self.assertRaisesRegex(RuntimeError,'failed backward'),budget.installed():trainer.train()
        self.assertEqual(engine.model.native_calls,4);self.assertEqual(trainer.update_calls,3)
        self.assertIs(AdamW.__init__,original_init);self.assertIs(AdamW.step,original_step);self.assertIs(RandomSampler.__iter__,original_iter)
        self.assertEqual(trainer.callbacks,[])
    def test_missing_scheduler_return_fails_before_next_model_entry(self):
        engine,trainer,budget=self.setup(skip_scheduler=True)
        with self.environment(engine),self.assertRaisesRegex(RuntimeError,'post-optimizer'),budget.installed():trainer.train()
        self.assertEqual(engine.model.native_calls,1);self.assertEqual(trainer.update_calls,1)
    def test_global_rng_after_yield_source_is_rejected_before_forward(self):
        engine,trainer,budget=self.setup()
        bad='def __iter__(self):\n    yield from torch.randperm(n,generator=generator).tolist()\n    seed=torch.empty(()).random_()\n'
        with self.environment(engine),patch.object(native.inspect,'getsource',return_value=bad),\
            self.assertRaisesRegex(RuntimeError,'global seed draw'),budget.installed():trainer.train()
        self.assertEqual(engine.model.native_calls,0)
    def test_full_128_rows_required_even_for_short_arm(self):
        engine,trainer,budget=self.setup()
        with self.assertRaisesRegex(RuntimeError,'full prepared epoch'):
            native.PrefixBudget(engine,trainer,self.rows[:64],self.rates,schedule_fixture(self.rates),self.rates,
                self.root,{k:digest(k) for k in contract.SOURCE_FIELDS},'ttt64')


if __name__=='__main__':unittest.main()

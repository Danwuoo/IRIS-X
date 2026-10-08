"""Install E12 observations on the actual native Trainer, sampler and AdamW.

No native imports occur at module import. The unchanged Trainer still prepares a
128-row epoch and a 128-step scheduler; only the post-update callback stops early.
"""
from collections import Counter
import ast
from contextlib import contextmanager
import hashlib
import inspect
from pathlib import Path
from types import MethodType, SimpleNamespace

from tools.nvarc_native_ttt_budget import EpochBudget
from tools.nvarc_native_multitask import digest, require, write
from tools.nvarc_e10_paired_schedule import capture_rng, restore_rng
from tools import nvarc_e12_prefix_contract as contract

PROFILES = {'ttt64':'E12-TTT64-PREFIX', 'ttt128':'E12-TTT128-CONTROL'}


def rng_observation(state):
    np = state['numpy']
    return dict(python=digest(state['python']), numpy=digest([np[0],np[1].tolist(),*np[2:]]),
        torch_cpu=digest(state['torch_cpu'].tolist()),
        torch_cuda=[digest(value.tolist()) for value in state['torch_cuda']])


def reset_observation(engine, optimizer=None):
    return dict(model_inventory_digest=digest(engine.inventory()),
        rng=rng_observation(capture_rng(engine)),
        optimizer_state_entries=0 if optimizer is None else len(optimizer.state),
        gradient_tensor_count=sum(p.grad is not None for p in engine.model.parameters()))


class PrefixBudget(EpochBudget):
    def __init__(self, engine, trainer, rows, rates, schedule, reference_rates, output, sources, arm_id):
        self.engine, self.output, self.schedule, self.reference_rates = engine, Path(output), schedule, reference_rates
        self.sources, self.arm_id = dict(sources), arm_id
        self.controller = self.contract = self.train_start_rng = self.start_reset = None
        self.start_state = self.sampler_receipt = None
        self.sampler_iterations = 0
        self.callback_steps = 0
        self.native_errors = []
        require(arm_id in PROFILES and len(rows)==128 and len(rates)==129,
            'original full prepared epoch and distinct E12 stop arm required')
        super().__init__(engine.torch, engine.model, trainer, rows, rates,
            lambda state:write(self.output/'training-ledger.json',state),
            expected_parameters=528564224, expected_dtype='torch.bfloat16')
        self.count = 64 if arm_id=='ttt64' else 128

    def snapshot(self):
        if self.controller is not None:
            write(self.output/'prefix-trace.json',self.controller.snapshot())
        write(self.output/'native-hook-status.json',dict(format='irisx/e12-native-hooks-v1',
            arm_id=self.arm_id, sampler_iterations=self.sampler_iterations,
            callback_steps=self.callback_steps, errors=self.native_errors))

    def before_forward(self,module,args,kwargs):
        require(self.controller is not None,'actual full sampler must be observed before training entry')
        ids=kwargs['input_ids'].tolist(); labels=kwargs['labels'].tolist()
        require(len(ids)==len(labels)==1,'one native full row required')
        self.controller.begin_step(self.trainer.state.global_step,ids[0],labels[0],
            rng_observation(capture_rng(self.engine)))
        super().before_forward(module,args,kwargs)

    def after_forward(self,module,args,output):
        super().after_forward(module,args,output)
        self.controller.forward_return(self.state['forwards'][-1]['loss'])

    def counters(self,optimizer):
        result=[]
        for p in self.parameters.values():
            state=optimizer.state.get(p,{})
            raw=state.get('step',0)
            value=float(raw)
            require(value.is_integer() and value>=0,'every actual Adam step must be an exact integer')
            result.append(int(value))
        return result

    def observe_sampler(self, sampler, original):
        actual=(type(sampler).__module__,type(sampler).__name__)
        require(actual in {('torch.utils.data.sampler','RandomSampler'),
            ('accelerate.data_loader','SeedableRandomSampler')} and sampler.replacement is False and
            sampler.num_samples==128 and len(sampler.data_source)==128,
            'unchanged native full RandomSampler or Accelerate SeedableRandomSampler required')
        self.sampler_iterations+=1
        require(self.sampler_iterations==1 and self.start_state is not None,
            'one actual full sampler iteration after native train begin required')
        source=Path(inspect.getsourcefile(type(sampler))).resolve()
        parent_source=Path(inspect.getsourcefile(original)).resolve()
        require(all(p.is_relative_to(self.engine.dependency.resolve()) for p in (source,parent_source)),
            'native sampler sources must be in pinned dependency')
        source_receipt=dict(module=actual[0],name=actual[1],
            source_path=source.relative_to(self.engine.dependency.resolve()).as_posix(),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            iterator_source_path=parent_source.relative_to(self.engine.dependency.resolve()).as_posix(),
            iterator_source_sha256=hashlib.sha256(parent_source.read_bytes()).hexdigest(),
            replacement=False,num_samples=128)
        # Observe the original instance at the base iterator. Do not replace its
        # type: Accelerate must retain its original seedable-sampler conversion.
        # The pinned iterator draws the global seed once before creating a local
        # Generator. Every permutation draw uses that local generator, so eager
        # materialization cannot move a later global/dropout RNG draw earlier.
        source_text=inspect.getsource(original)
        import textwrap
        tree=ast.parse(textwrap.dedent(source_text))
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        permutation=[n for n in calls if n.func.attr in ('randperm','randint')]
        require(permutation and all(any(k.arg=='generator' and isinstance(k.value,ast.Name) and
            k.value.id=='generator' for k in n.keywords) for n in permutation),
            'every original permutation draw must use its local generator')
        random_seed=[n for n in calls if n.func.attr=='random_']
        yields=[n for n in ast.walk(tree) if isinstance(n,(ast.Yield,ast.YieldFrom))]
        require(len(random_seed)==1 and yields and random_seed[0].lineno<min(n.lineno for n in yields),
            'only one native global seed draw before all yields required')
        order=list(original(sampler))
        require(len(order)==128 and all(type(i) is int for i in order) and sorted(order)==list(range(128)),
            'native sampler must yield exactly one128row permutation')
        self.sampler_receipt=dict(source_receipt,order=order)
        self.sources['native_sampler_digest']=digest(source_receipt)
        self.contract=contract.build_native_contract(
            rows=[{k:r[k] for k in contract.ROW_FIELDS} for r in self.rows],sampler_order=order,
            reset=self.start_reset,sources=self.sources,rates=self.rates,schedule_receipt=self.schedule,
            reference_rates=self.reference_rates)
        self.controller=contract.PrefixStopController(self.contract,PROFILES[self.arm_id])
        self.controller.start(self.trainer.args,self.start_state,self.start_reset)
        write(self.output/'prefix-contract.json',self.contract)
        write(self.output/'sampler.json',self.sampler_receipt);self.snapshot()
        return iter(order)

    @contextmanager
    def installed(self):
        # Admission is owned by the worker, before this method can be reached.
        from transformers import TrainerCallback
        from torch.utils.data.sampler import RandomSampler
        owner=self
        original_sampler=RandomSampler.__iter__
        original_scheduler=self.trainer.create_scheduler
        scheduler_restore=[]
        class Callback(TrainerCallback):
            def on_train_begin(self,args,state,control,**kwargs):
                require(owner.start_state is None and state.global_step==0 and state.max_steps==128,
                    'native Trainer must derive the original 128-step horizon')
                owner.train_start_rng=capture_rng(owner.engine)
                owner.start_reset=reset_observation(owner.engine,owner.optimizer)
                owner.start_state=SimpleNamespace(global_step=state.global_step,max_steps=state.max_steps)
                return control
            def on_step_end(self,args,state,control,**kwargs):
                require(owner.controller is not None,'native callback needs actual sampler/controller')
                result=owner.controller.on_step_end(args,state,control)
                owner.callback_steps+=1;owner.snapshot();return result
        callback=Callback()
        def observed_sampler(sampler):
            return owner.observe_sampler(sampler,original_sampler)
        def create_scheduler(_trainer,*args,**kwargs):
            value=original_scheduler(*args,**kwargs)
            scheduler=owner.trainer.lr_scheduler
            require(scheduler is not None and not scheduler_restore,'one native scheduler required')
            original=scheduler.step
            def step(*a,**kw):
                result=original(*a,**kw)
                require(owner.controller is not None,'scheduler update before actual training forbidden')
                owner.controller.scheduler_return([g['lr'] for g in owner.optimizer.param_groups])
                return result
            scheduler.step=step;scheduler_restore.append((scheduler,original));return value
        RandomSampler.__iter__=observed_sampler
        self.trainer.create_scheduler=MethodType(create_scheduler,self.trainer)
        self.trainer.add_callback(callback)
        try:
            with super().installed():
                original_training=self.trainer.training_step
                original_step=self.torch.optim.AdamW.step
                def training(*args,**kwargs):
                    result=original_training(*args,**kwargs)
                    self.controller.backward_return(rng_observation(capture_rng(self.engine)))
                    return result
                def step(optimizer,*args,**kwargs):
                    require(self.controller is not None,'optimizer needs native prefix controller')
                    self.controller.optimizer_enter([g['lr'] for g in optimizer.param_groups],self.counters(optimizer))
                    result=original_step(optimizer,*args,**kwargs)
                    self.controller.optimizer_return(self.counters(optimizer));return result
                self.trainer.training_step=training;self.torch.optim.AdamW.step=step
                try:yield self
                finally:
                    self.trainer.training_step=original_training;self.torch.optim.AdamW.step=original_step
        except BaseException as error:
            self.native_errors.append(dict(type=type(error).__name__,message=str(error)[:1000]))
            if self.controller is not None:self.controller.fail('native-training',str(error))
            self.snapshot();raise
        finally:
            for scheduler,original in scheduler_restore:scheduler.step=original
            self.trainer.remove_callback(callback)
            RandomSampler.__iter__=original_sampler
            self.trainer.create_scheduler=original_scheduler

    def complete(self):
        require(self.controller is not None and not self.native_errors and self.callback_steps==self.count and
            len(self.state['optimizer_constructions'])==1 and self.state['optimizer_constructions'][0]['completed'] and
            all(len(self.state[key])==self.count and all(r['completed'] for r in self.state[key])
                for key in ('forwards','training_steps','optimizer_steps')),
            'all actual prefix forwards/backwards/updates and post-update callbacks must complete')
        expected=Counter((r['input_ids_digest'],r['labels_digest']) for r in self.rows)
        expected.subtract((self.rows[i]['input_ids_digest'],self.rows[i]['labels_digest'])
            for i in self.contract['sampler_order'][:self.count])
        require(+self.remaining==+expected,'only the exact original sampler prefix may be consumed')
        moments=[]
        for p in self.parameters.values():
            state=self.optimizer.state[p]
            require(float(state['step'])==self.count,'all 506 Adam states must include zero-LR update')
            for key in ('exp_avg','exp_avg_sq'):
                value=state[key]
                require(value.shape==p.shape and value.dtype==p.dtype and value.device==p.device and
                    bool(self.torch.isfinite(value).all()),'all finite original Adam moments required')
            moments.append(dict(elements=p.numel(),parameter_dtype=str(p.dtype),parameter_device=str(p.device),
                moment_bytes=sum(state[k].numel()*state[k].element_size() for k in ('exp_avg','exp_avg_sq')),
                step=self.count,finite=True))
        require(len(moments)==506,'all 506 moment tensors required');return moments

    def finish(self):
        require(self.optimizer is None and self.train_start_rng is not None,'optimizer must be disposed before final reset')
        restore_rng(self.engine,self.train_start_rng)
        trace=self.controller.finish(self.trainer.args,self.trainer.state,self.trainer.control,
            reset_observation(self.engine))
        self.snapshot();return trace

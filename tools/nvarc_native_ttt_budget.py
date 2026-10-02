"""Actual source-row, Trainer-step and AdamW guards for one complete native epoch."""
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import math
from types import MethodType


def digest(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def require(value,message):
    if not value:raise RuntimeError(message)


class EpochBudget:
    def __init__(self,torch,model,trainer,rows,rates,retain,*,expected_parameters,expected_dtype):
        self.torch,self.model,self.trainer,self.retain=torch,model,trainer,retain
        self.rows=rows;self.rates=rates;self.count=len(rows);self.optimizer=None;self.active=None
        require(1<=self.count<=128 and len(rates)==self.count+1,'finite complete source epoch required')
        self.remaining=Counter((row['input_ids_digest'],row['labels_digest']) for row in rows)
        self.parameters={id(p):p for p in model.parameters() if p.requires_grad}
        require(sum(p.numel() for p in self.parameters.values())==expected_parameters and
            all(str(p.dtype)==expected_dtype for p in self.parameters.values()),'exact native trainable layout/dtype required')
        self.state={'forwards':[],'training_steps':[],'optimizer_steps':[],
            'optimizer_constructions':[],'generation_calls':0,'teacher_calls':0}
        self._save()

    def _save(self):self.retain(self.state)

    def before_forward(self,module,args,kwargs):
        i=len(self.state['forwards'])
        require(i<self.count and self.active==i,'one reserved Trainer microstep required before model entry')
        ids=kwargs['input_ids'].tolist();labels=kwargs['labels'].tolist()
        require(len(ids)==len(labels)==1 and len(ids[0])==len(labels[0]),'one full source view and labels required')
        pair=(digest(ids[0]),digest(labels[0]))
        require(self.remaining[pair]>0 and kwargs.get('past_key_values') is None,'unconsumed exact source row/labels required')
        self.remaining[pair]-=1
        self.state['forwards'].append({'input_ids_digest':pair[0],'labels_digest':pair[1],
            'input_tokens':len(ids[0]),'supervised_tokens':sum(v>=0 for v in labels[0][1:]),'completed':False})
        self._save()

    def after_forward(self,module,args,output):
        row=self.state['forwards'][-1]
        loss=output['loss'] if isinstance(output,dict) else output[0]
        require(not row['completed'] and loss.numel()==1 and bool(self.torch.isfinite(loss)),'finite native scalar loss required')
        row.update(completed=True,loss=float(loss.detach().float().cpu()));self._save()

    def check_optimizer(self,optimizer):
        values=[p for group in optimizer.param_groups for p in group['params']]
        require(len(values)==len(self.parameters) and len({id(p) for p in values})==len(values) and
            {id(p) for p in values}==set(self.parameters),'every native trainable parameter must be optimized once')
        require(all(tuple(group['betas'])==(.9,.999) and group['eps']==1e-8 and group['weight_decay']==0
            for group in optimizer.param_groups),'original TTT AdamW recipe required')

    @contextmanager
    def installed(self):
        torch=self.torch;cls=torch.optim.AdamW
        constructor,step=cls.__init__,cls.step
        original_training=self.trainer.training_step
        hooks=[];generation_present='generate' in self.model.__dict__
        generation_old=self.model.__dict__.get('generate')

        def construct(owner,*args,**kwargs):
            require(not self.state['optimizer_constructions'],'one actual native AdamW construction allowed')
            row={'completed':False};self.state['optimizer_constructions'].append(row);self._save()
            constructor(owner,*args,**kwargs);self.check_optimizer(owner);self.optimizer=owner
            row['completed']=True;self._save()

        def optimizer_step(owner,*args,**kwargs):
            i=len(self.state['optimizer_steps'])
            require(owner is self.optimizer and self.active is None and i<self.count and
                len(self.state['training_steps'])==len(self.state['forwards'])==i+1 and
                self.state['training_steps'][-1]['completed'] and self.state['forwards'][-1]['completed'],
                'one completed source forward/backward required before each optimizer entry')
            self.check_optimizer(owner)
            require(all(group['lr']==self.rates[i] for group in owner.param_groups),'exact native cosine learning rate required')
            total=None
            for p in self.parameters.values():
                require(p.grad is not None and p.grad.shape==p.shape and bool(torch.isfinite(p.grad).all()),
                    'every native gradient must be present and finite')
                value=p.grad.detach().float().square().sum();total=value if total is None else total+value
            norm=float(total.sqrt().cpu())
            require(math.isfinite(norm) and norm<=1.05,'source clipping must finish before AdamW entry')
            row={'learning_rate':self.rates[i],'gradient_tensors':len(self.parameters),
                'gradient_norm_after_clip':norm,'completed':False}
            self.state['optimizer_steps'].append(row);self._save()
            result=step(owner,*args,**kwargs)
            if next(iter(self.parameters.values())).is_cuda:torch.cuda.synchronize()
            row['completed']=True;self._save();return result

        def training_step(owner,*args,**kwargs):
            i=len(self.state['training_steps'])
            require(self.active is None and i<self.count and len(self.state['optimizer_steps'])==i and
                len(self.state['forwards'])==i,'finite dependent Trainer step required')
            row={'completed':False};self.state['training_steps'].append(row);self.active=i;self._save()
            try:
                result=original_training(*args,**kwargs)
                require(len(self.state['forwards'])==i+1 and self.state['forwards'][-1]['completed'],
                    'one exact outer forward must return in each native training step')
                row['completed']=True;self._save();return result
            finally:self.active=None

        def no_generation(*args,**kwargs):raise RuntimeError('native epoch has no generation authority')
        try:
            cls.__init__,cls.step=construct,optimizer_step
            self.trainer.training_step=MethodType(training_step,self.trainer)
            self.model.generate=no_generation
            hooks=[self.model.register_forward_pre_hook(self.before_forward,with_kwargs=True),
                self.model.register_forward_hook(self.after_forward)]
            yield self
        finally:
            for hook in hooks:hook.remove()
            cls.__init__,cls.step=constructor,step
            self.trainer.training_step=original_training
            if generation_present:self.model.generate=generation_old
            else:delattr(self.model,'generate')

    def complete(self):
        require(not +self.remaining and len(self.state['optimizer_constructions'])==1 and
            self.state['optimizer_constructions'][0]['completed'] and all(len(self.state[key])==self.count and
                all(row['completed'] for row in self.state[key]) for key in ('forwards','training_steps','optimizer_steps')),
            'all exact views, native backwards and optimizer steps must complete')
        observations=[]
        for p in self.parameters.values():
            state=self.optimizer.state[p]
            require(float(state['step'])==self.count,'every trainable parameter must complete the full epoch')
            for key in ('exp_avg','exp_avg_sq'):
                value=state[key]
                require(value.shape==p.shape and value.dtype==p.dtype and value.device==p.device and
                    bool(self.torch.isfinite(value).all()),'finite original same-dtype/device Adam moments required')
            observations.append({'elements':p.numel(),'parameter_dtype':str(p.dtype),'parameter_device':str(p.device),
                'moment_bytes':sum(state[k].numel()*state[k].element_size() for k in ('exp_avg','exp_avg_sq')),
                'step':self.count,'finite':True})
        return observations

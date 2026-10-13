"""Owned native Qwen/PEFT actor and original-token causal replay.

Separate successor, not a relaxation of the sealed tiny prototype. Production
constructor stays release-gated. The implementation uses the same native loader,
material/tokenizer, PEFT recipe and calibrated cache choice as the admitted base.
No frozen-base tensor copies or hashes occur per token or trajectory.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import inspect, math, threading, time, uuid
import torch
from .common import need, digest, canonical, source_identity, tensor_signature, finite, rl_math
from .data import Prompt
from .plan import NumericGate, plan_receipt
from tools.arc_qwen_transfer_20261012.decoder import TransferModel
from tools.arc_qwen_transfer_20261012.backend import TransferTrainer
from tools.arc_qwen_probe_20261012.decoder import cache_length
from tools.arc_learning_agent_20261011.qwen14b_training import validate_qwen_peft_recipe

class PhysicalLedger:
    def __init__(self,device,global_deadline,on_fatal):
        self.device=device;self.events=[];self.global_deadline=global_deadline;self.on_fatal=on_fatal;self.closed=False
    def sync(self):
        if self.device.type=='cuda':torch.cuda.synchronize(self.device)
    @contextmanager
    def work(self,phase,deadline):
        need(not self.closed,'session physical ledger permanently closed')
        need(type(deadline) in (int,float) and math.isfinite(deadline) and deadline<=self.global_deadline,
             'finite work deadline within original global limit required')
        event={'event_id':len(self.events),'phase':phase,'started':time.monotonic(),
               'dispatched':False,'status':'reserved','clock':'synchronized-wall-time',
               'device_time_measured':False}
        self.events.append(event)
        try:
            if time.monotonic()>=deadline:raise TimeoutError('deadline before '+phase)
            self.sync()
            yield event
            self.sync()
            if time.monotonic()>=deadline:raise TimeoutError('deadline after '+phase)
            event['status']='complete'
        except BaseException as exc:
            if isinstance(exc,RuntimeError):self.on_fatal(exc)
            event.update(status='failed' if event['dispatched'] else 'excluded',error=type(exc).__name__+': '+str(exc)[:256])
            raise
        finally:
            try:self.sync()
            except BaseException as exc:
                self.on_fatal(exc)
                event.update(status='unclosed-device-error',closure_error=type(exc).__name__+': '+str(exc)[:256])
                raise
            finally:event.update(ended=time.monotonic(),seconds=time.monotonic()-event['started'])

@dataclass
class Replay:
    log_pi:torch.Tensor
    log_mu:torch.Tensor
    diagnostic:dict

class NativeActor:
    def __init__(self,native,trainer,*,global_deadline,fixture=False,_owned_grant=None):
        need(type(native) is TransferModel and type(trainer) is TransferTrainer,'exact native transfer backend required')
        need(trainer.native is native and trainer.model is native.model,'owned trainer/native model required')
        need(type(fixture) is bool and native.tiny_cpu is fixture,'explicit fixture/backend scope')
        owned_ledger=None
        if _owned_grant is not None:
            from owned_runtime.admission import consume
            owned_ledger=consume(_owned_grant,native,trainer,global_deadline,fixture)
        if not fixture:
            need(owned_ledger is not None,'production needs one-use owned loader/calibration/source grant')
        else:
            need(native.identity.get('random_test_weights') is True and
                 not native.identity.get('pretrained_weights_loaded'),'tiny random fixture identity')
        self._owned_grant=_owned_grant
        self.native,self.trainer,self.fixture=native,trainer,fixture
        self.model=native.model;self.device=next(self.model.parameters()).device
        self.global_deadline=global_deadline
        need(type(global_deadline) in (float,int) and math.isfinite(global_deadline) and
             time.monotonic()<global_deadline,'finite global deadline required')
        self.fatal_error=None;self._closed=False;self.ledger=owned_ledger if owned_ledger is not None else PhysicalLedger(self.device,global_deadline,self._mark_fatal);self._lock=threading.RLock()
        self.ledger.on_fatal=self._mark_fatal
        self._owned={};self._sweeps={};self._generation_epoch=0
        self.policy_version='anchor:'+uuid.uuid4().hex
        self._sources=source_identity()
        self._base_signature=tensor_signature((n,p) for n,p in self.model.named_parameters() if 'lora_' not in n)
        self._buffer_signature=tensor_signature(self.model.named_buffers())
        self._hook_signature=self._hooks(initial=True)
        self._function_signature=self._functions()
        self._structural=self._structure()
        self._adapter_sha=trainer.fingerprint()['sha256']
        self.cache_mode='cached' if fixture else native.decoder_policy['selected_mode']
        self._selected_cache_mode=self.cache_mode
        self._identity=digest(self._live_identity())
        self._check_live()
    def _mark_fatal(self,exc):
        if self.fatal_error is None:self.fatal_error=type(exc).__name__+': '+str(exc)[:256]
    def _hooks(self,initial=False):
        names=('_forward_hooks','_forward_pre_hooks','_backward_hooks','_backward_pre_hooks')
        rows=[]
        for n,m in self.model.named_modules():
            for key in names:
                for index,hook in getattr(m,key,{}).items():
                    if initial:
                        need(m is self.model.get_input_embeddings() and key=='_forward_hooks' and
                             getattr(hook,'__qualname__','')=='PreTrainedModel.enable_input_require_grads.<locals>.make_inputs_require_grads',
                             'only native checkpointing input-gradient hook admitted')
                    rows.append((n,key,index,id(hook)))
        need(all(not getattr(p,'_backward_hooks',None) and not getattr(p,'_post_accumulate_grad_hooks',None)
                 for p in self.model.parameters()),'parameter gradient hooks forbidden')
        from torch.nn.modules import module as module_api
        need(all(not getattr(module_api,key,{}) for key in ('_global_forward_hooks','_global_forward_pre_hooks',
             '_global_backward_hooks','_global_backward_pre_hooks')),'global module hooks forbidden')
        return tuple(rows)
    def _functions(self):
        funcs=[m.forward for m in self.model.modules()]
        funcs += [self.native._prompt,self.native.constraint.allowed_tokens,self.native.constraint.prefix_state,
                  self.native.constraint.validate_completion,self.native.constraint.transition]
        from transformers.models.qwen3 import modeling_qwen3 as q3
        funcs += [q3.apply_rotary_pos_emb,q3.rotate_half,q3.repeat_kv,
                  q3.ALL_ATTENTION_FUNCTIONS.get_interface(self.model.config._attn_implementation,q3.eager_attention_forward)]
        return tuple((id(getattr(f,'__self__',None)),id(getattr(f,'__func__',f))) for f in funcs)
    def _structure(self):
        cfg=self.model.config
        checkpoint_functions={}
        for n,m in self.model.named_modules():
            f=getattr(m,'_gradient_checkpointing_func',None)
            if f is not None:
                from functools import partial
                from torch.utils.checkpoint import checkpoint
                need(isinstance(f,partial) and f.func is checkpoint and not f.args and
                     f.keywords=={'use_reentrant':False},'native nonreentrant checkpoint callable required')
                checkpoint_functions[n]={'function':id(f),'kwargs':dict(f.keywords)}
        return {'native_config':deepcopy(self.native.config),'checkpoint_functions':checkpoint_functions,'config':cfg.to_dict(),'attention':cfg._attn_implementation,
                'checkpointing':self.model.is_gradient_checkpointing,
                'recipe':validate_qwen_peft_recipe(self.model,torch),
                'scalars':{n:{k:v for k,v in vars(m).items() if not k.startswith('_') and
                             k!='training' and (v is None or type(v) in (bool,int,float,str))}
                           for n,m in self.model.named_modules()},
                'trainer_config':deepcopy(self.trainer.config)}
    def _live_identity(self):
        return {'cache_mode':self.cache_mode,'native':self.native.identity,'adapter_sha256':self.trainer.fingerprint()['sha256'],
                'policy_version':self.policy_version,'source_sha256':digest(self._sources),
                'prompt':self.native.prompt_contract.contract_sha256,'dfa':self.native.constraint.receipt,
                'structure':self._structure()}
    def _check_structure(self):
        need(not self._closed,'session permanently closed')
        need(self.fatal_error is None,'fatal native state: '+str(self.fatal_error))
        need(self.cache_mode==self._selected_cache_mode,'actor cache policy drift')
        self.native._open()
        need(self._hooks()==self._hook_signature,'module hook drift')
        need(self._functions()==self._function_signature,'execution function drift')
        need(self._structure()==self._structural,'structural execution drift')
        need(source_identity()==self._sources,'source drift')
        need(tensor_signature((n,p) for n,p in self.model.named_parameters() if 'lora_' not in n)==self._base_signature,
             'owned frozen base changed')
        need(tensor_signature(self.model.named_buffers())==self._buffer_signature,'model buffer changed')
        need(all((p.dtype==torch.float32 and p.requires_grad) if 'lora_' in n else
                 (p.dtype==torch.bfloat16 and not p.requires_grad and p.grad is None)
                 for n,p in self.model.named_parameters()),'BF16 frozen base/FP32 LoRA only')
        need(self.model.config.attention_dropout==0. and all(not isinstance(m,torch.nn.Dropout) or m.p==0 for m in self.model.modules()),'dropout must be zero')
        need(not torch.is_autocast_enabled(self.device.type),'external autocast forbidden')
        self.native._assert_tokenizer_backend();self.native.prompt_contract._assert_tokenizer_unchanged()
        self.native.assert_decoder_policy()
        need(self.native._current_policy()==self.native.native_policy,'native EOS policy drift')
        need(self.native.constraint.tokenizer is self.native.tokenizer and tuple(self.native.constraint.eos_ids)==tuple(self.native.eos_ids),
             'DFA/tokenizer identity drift')
    def _check_live(self):
        self._check_structure()
        need(finite(self.trainer.parameters),'nonfinite adapter')
        need(digest(self._live_identity())==self._identity,'policy/adapter drift')
    def _refresh(self):
        self.trainer._publish_fingerprint();self._identity=digest(self._live_identity())
    def _deadline(self,deadline):
        need(type(deadline) in (float,int) and math.isfinite(deadline) and deadline<=self.global_deadline,
             'deadline exceeds original global deadline')
        if time.monotonic()>=deadline:raise TimeoutError('session deadline')
    def _support(self,suffix):
        self.native.constraint._allowed_cache.clear()
        support=self.native.constraint.allowed_tokens(suffix)
        need(len(support)<=27,'pinned native digit/newline25-piece plus twoEOS support expansion')
        return support
    @contextmanager
    def _mode(self,training):
        modes={n:m.training for n,m in self.model.named_modules()}
        self.model.train(training)
        try:yield
        finally:
            for n,m in self.model.named_modules():m.training=modes[n]
    def _forward(self,sequence,past,deadline):
        cached=self.cache_mode=='cached'; before=cache_length(past,self.model.config,self.device) if past is not None else 0
        tokens=sequence[-1:] if cached and past is not None else sequence
        need(not cached or before==len(sequence)-len(tokens),'actor cache prefix mismatch')
        positions=torch.arange(len(sequence)-len(tokens),len(sequence),device=self.device)
        with (self.ledger.forward_work('sample-forward',deadline) if hasattr(self.ledger,'forward_work') else self.ledger.work('sample-forward',deadline)) as e:
            e.update(dispatched=True,input_tokens=len(tokens),cache_before=before)
            out=self.model(input_ids=torch.tensor([tokens],device=self.device),
                attention_mask=torch.ones((1,len(sequence)),dtype=torch.long,device=self.device),
                position_ids=positions[None,:],cache_position=positions,
                past_key_values=past if cached else None,use_cache=cached,logits_to_keep=1)
            logits=out.logits[0,-1]
            need(logits.shape==(self.native.vocab_size,) and bool(torch.isfinite(logits).all()),'finite full actor head')
            need(not cached or cache_length(out.past_key_values,self.model.config,self.device)==len(sequence),'cache length mismatch')
            return logits,out.past_key_values,e['event_id'],e.get('forward_index')
    def sample(self,prompt,*,seed,max_new_tokens,deadline):
        # A whole generation watchdog spans all token forwards and host work.
        with self.ledger.work('rollout-generation',deadline) as event:
            event.update(reserved_forward_calls=max_new_tokens,reserved_input_tokens=max_new_tokens*self.native.context_limit,dispatched=True)
            bounded=min(deadline,event.get('soft_deadline',deadline))
            result=self._sample_impl(prompt,seed=seed,max_new_tokens=max_new_tokens,deadline=bounded)
            event.update(trajectory_id=result['trajectory_id'],
                         output_tokens=len(result['generated_ids']))
            return result

    def _sample_impl(self,prompt,*,seed,max_new_tokens,deadline):
        with self._lock:
            self._check_live();self._deadline(deadline)
            deadline=min(deadline,time.monotonic()+175.)
            need(type(prompt) is Prompt and prompt.exclusion is None,'admitted target-free prompt')
            need(type(seed) is int and 0<=seed<2**63,'integer seed')
            need(type(max_new_tokens) is int and 1<=max_new_tokens<=self.native.output_cap,'output bound')
            receipt={'trajectory_id':uuid.uuid4().hex,'parent_id':prompt.parent_id,'record_id':prompt.record_id,
                'messages_sha256':digest(prompt.messages()),'policy_version':self.policy_version,'identity':self._identity,
                'generation_epoch':self._generation_epoch,'seed':seed,'generated_ids':[],'steps':[],
                'finish_reason':'length','infrastructure_excluded':False,'format_text':None,
                'sampling':{'temperature':1.,'top_p':1.,'dfa':True,'cache_mode':self.cache_mode}}
            past=None;event_start=len(self.ledger.events)
            try:
                _,ids=self.native._prompt(prompt.messages())
                need(len(ids)+max_new_tokens<=self.native.context_limit,'context budget exclusion')
                receipt['prompt_ids']=ids
                sequence=list(ids);generator=torch.Generator(device=self.device).manual_seed(seed)
                with self._mode(False),torch.inference_mode():
                    for i in range(max_new_tokens):
                        self._deadline(deadline)
                        suffix=receipt['generated_ids'];support=self._support(suffix)
                        logits,past,event,forward_index=self._forward(sequence,past,deadline)
                        allowed=torch.zeros_like(logits,dtype=torch.bool);allowed[support]=True
                        logp=rl_math.masked_log_probs(logits.detach(),allowed)
                        probabilities=logp[support].exp()
                        need(bool((probabilities>0).all()),'legal probability underflow')
                        token=support[int(torch.multinomial(probabilities,1,generator=generator).item())]
                        receipt['steps'].append({'token':token,'position':len(sequence)-1,
                            'support':support,'prefix_sha256':digest(sequence),
                            'dfa_state':list(self.native.constraint.prefix_state(suffix)),
                            'log_mu':float(logp[token]),'actor_event_id':event,
                            **({'actor_forward_index':forward_index} if forward_index is not None else {})})
                        from owned_runtime.evidence import MAX_TOKEN_STEP_BYTES
                        need(len(canonical(receipt['steps'][-1]))<=MAX_TOKEN_STEP_BYTES,'complete original token step expansion cap')
                        suffix.append(token);sequence.append(token)
                        if token in self.native.eos_ids:
                            receipt['finish_reason']='eos'
                            receipt['format_text']=self.native.constraint.validate_completion(suffix);break
                self._check_live();self._deadline(deadline)
            except Exception as exc:
                failed_dispatch=any(e['dispatched'] and e['status']!='complete' for e in self.ledger.events[event_start:])
                if any(e['status']=='unclosed-device-error' for e in self.ledger.events[event_start:]) or isinstance(exc,RuntimeError):
                    self.fatal_error=type(exc).__name__+': '+str(exc)[:256]
                receipt['fatal_native_state']=self.fatal_error is not None
                receipt.update(finish_reason='deadline' if isinstance(exc,TimeoutError) else 'infrastructure-error',
                    infrastructure_excluded=True,error=type(exc).__name__+': '+str(exc)[:256])
            finally:past=None
            receipt['cache_discarded']=True
            parent=self.ledger.current_event() if hasattr(self.ledger,'current_event') else None
            compact=parent is not None and parent['phase']=='rollout-generation'
            receipt['physical_event_ids']=[parent['event_id']] if compact else list(range(event_start,len(self.ledger.events)))
            receipt['dispatched_forwards']=self.ledger.current_forward_counts()['forward_calls'] if compact else sum(e['dispatched'] for e in self.ledger.events[event_start:])
            receipt['physical_accounting']='one-durable-generation-with-dense-original-forward-indices' if compact else 'per-forward-events'
            receipt['original_ids']=receipt.get('prompt_ids',[])+receipt['generated_ids']
            receipt['attention_mask']=[1]*len(receipt['original_ids'])
            receipt['origins']=['prompt']*len(receipt.get('prompt_ids',[]))+['assistant_generated']*len(receipt['generated_ids'])
            from owned_runtime.evidence import MAX_TOKEN_STEP_BYTES,MAX_TRAJECTORY_METADATA_BYTES
            need(len(canonical({k:v for k,v in receipt.items() if k!='steps'}))<=MAX_TRAJECTORY_METADATA_BYTES,'complete trajectory metadata expansion cap')
            self._owned[receipt['trajectory_id']]=canonical(receipt)
            return deepcopy(receipt)
    def _admit(self,row):
        need(type(row) is dict and self._owned.get(row.get('trajectory_id'))==canonical(row),'unknown/mutated original trajectory')
        self._check_live()
        need(row['policy_version']==self.policy_version and row['identity']==self._identity and
             row['generation_epoch']==self._generation_epoch,'stale trajectory')
        need(not row['infrastructure_excluded'] and row['generated_ids'],'excluded/empty trajectory')
        need(row['original_ids']==row['prompt_ids']+row['generated_ids'] and
             row['attention_mask']==[1]*len(row['original_ids']) and
             row['origins']==['prompt']*len(row['prompt_ids'])+['assistant_generated']*len(row['generated_ids']),
             'original causal token layout differs')
        for i,(token,step) in enumerate(zip(row['generated_ids'],row['steps'])):
            need(step['position']==len(row['prompt_ids'])+i-1 and step['token']==token and
                 step['prefix_sha256']==digest(row['prompt_ids']+row['generated_ids'][:i]) and
                 step['support']==self._support(row['generated_ids'][:i]) and
                 step['dfa_state']==list(self.native.constraint.prefix_state(row['generated_ids'][:i])),
                 'causal DFA support/prefix mismatch')
            need(token in step['support'] and math.isfinite(step['log_mu']) and step['log_mu']<=1e-6,'actor probability')
            need(len(step['support'])!=1 or step['log_mu']==0.,'forced-token probability')
    def replay(self,row,*,deadline,update_batch_id=None):
        with self._lock:
            self._deadline(deadline);self._admit(row)
            need(torch.is_grad_enabled() and not torch.is_inference_mode_enabled(),'replay needs autograd')
            tokens=row['original_ids'][:-1];positions=list(range(len(row['prompt_ids'])-1,len(tokens)))
            if self.device.type=='cuda':torch.cuda.reset_peak_memory_stats(self.device)
            with self._mode(True),self.ledger.work('causal-replay',deadline) as e:
                # train mode is essential: Qwen's checkpointing is conditioned on
                # self.training. All dropout is exactly zero; cache is disabled.
                e.update(trajectory_id=row['trajectory_id'],update_batch_id=update_batch_id,reserved_cost={'forward_calls':1,'input_tokens':len(tokens)},dispatched=True,input_tokens=len(tokens),checkpointing=self.model.is_gradient_checkpointing)
                ids=torch.tensor([tokens],device=self.device);pos=torch.arange(len(tokens),device=self.device)
                selected=torch.tensor(positions,device=self.device,dtype=torch.long)
                out=self.model(input_ids=ids,attention_mask=torch.ones_like(ids),position_ids=pos[None,:],
                    cache_position=pos,past_key_values=None,use_cache=False,logits_to_keep=selected)
                need(out.past_key_values is None,'replay cannot retain KV cache')
                logits=out.logits[0]
                need(logits.shape==(len(positions),self.native.vocab_size),'exact generated causal head rows')
                allowed=torch.zeros_like(logits,dtype=torch.bool)
                for i,step in enumerate(row['steps']):allowed[i,step['support']]=True
                pi=rl_math.selected_log_probs(logits,allowed,torch.tensor(row['generated_ids'],device=self.device))
                mu=torch.tensor([s['log_mu'] for s in row['steps']],device=self.device,dtype=torch.float32)
                need(pi.requires_grad and not mu.requires_grad,'replay graph/behavior separation')
                delta=(pi.detach().double()-mu.double());nonforced=torch.tensor([len(s['support'])>1 for s in row['steps']],device=self.device)
                report={}
                for label,mask in [('all_tokens',torch.ones_like(nonforced)),('nonforced_tokens',nonforced)]:
                    x=delta[mask];r=x.clamp(-20,20).exp();inside=(r>.8)&(r<1.28)
                    report[label]={'tokens':x.numel(),'max_abs_gap':float(x.abs().max()) if x.numel() else 0.,
                        'p95_abs_gap':float(torch.quantile(x.abs(),.95)) if x.numel() else 0.,
                        'unclipped_fraction':float(inside.double().mean()) if x.numel() else 1.,
                        'clipped_tokens':int((~inside).sum())}
                report.update(parent_id=row['parent_id'],trajectory_id=row['trajectory_id'],replay_event_id=e['event_id'],
                    backward_event_id=None,update_batch_id=update_batch_id,log_pi=pi.detach().tolist(),log_mu=mu.tolist(),
                    peak_memory_bytes=torch.cuda.max_memory_allocated(self.device) if self.device.type=='cuda' else None,
                    peak_reserved_bytes=torch.cuda.max_memory_reserved(self.device) if self.device.type=='cuda' else None,
                    checkpointing_active=self.model.is_gradient_checkpointing,training_mode=True,
                    prompt_and_tool_loss_masked=True,forced_tokens=int((~nonforced).sum()),
                    original_token_replay=True,cache_mode=row['sampling']['cache_mode'])
                e['actual_cost']={'forward_calls':1,'input_tokens':len(tokens)}
            report['seconds']=e['seconds']
            from owned_runtime.evidence import MAX_REPLAY_BYTES
            need(len(canonical(report))<=MAX_REPLAY_BYTES,'complete replay diagnostic expansion cap')
            self._check_live();self._deadline(deadline)
            return Replay(pi,mu,report)
    @staticmethod
    def numerical_admission(replays,gate):
        need(type(gate) is NumericGate and replays,'predeclared numeric gate required')
        failures=[]
        for r in replays:
            d=r['nonforced_tokens']
            if d['max_abs_gap']>gate.maximum_absolute_gap or d['p95_abs_gap']>gate.maximum_p95_gap or d['unclipped_fraction']<gate.minimum_unclipped_fraction:
                failures.append(r['parent_id']+':ratio-gap')
            if r['seconds']>gate.maximum_replay_seconds:failures.append(r['parent_id']+':runtime')
            if not gate.fixture_only and (r['peak_memory_bytes'] is None or r['peak_memory_bytes']>gate.maximum_peak_bytes or
                    r['peak_reserved_bytes'] is None or r['peak_reserved_bytes']>gate.maximum_reserved_bytes):
                failures.append(r['parent_id']+':memory')
        return {'admitted':not failures,'failures':failures,'gate':vars(gate),
                'per_trajectory':replays,'per_parent_ids':list(dict.fromkeys(r['parent_id'] for r in replays))}

    def policy_identity(self):
        self._check_live()
        return {'policy_version':self.policy_version,'adapter_sha256':self.trainer.fingerprint()['sha256'],
                'source_sha256':digest(self._sources),'generation_epoch':self._generation_epoch}
    def evaluate(self,messages,*,seed,max_new_tokens,deadline):
        """Actual baseline inference, no target/reward callback, owned physical cost."""
        with self._lock:
            self._check_live();self._deadline(deadline)
            deadline=min(deadline,time.monotonic()+175.)
            identity=self.policy_identity()
            with self._mode(False),self.ledger.work('evaluation-generation',deadline) as e:
                e.update(reserved_forward_calls=max_new_tokens,reserved_input_tokens=max_new_tokens*self.native.context_limit,dispatched=True)
                deadline=min(deadline,e.get('soft_deadline',deadline))
                result=self.native.generate(messages,kind='grid',seed=seed,max_new_tokens=max_new_tokens,deadline=deadline)
                e.update(input_tokens=result.get('forward_input_tokens',0),output_tokens=result.get('output_tokens',0),
                         forward_input_tokens=result.get('forward_input_tokens',0),forward_calls=result.get('forward_calls',0))
                if result.get('fatal_error'):
                    self._mark_fatal(RuntimeError(result.get('error','native evaluation fatal error')))
                    raise RuntimeError(self.fatal_error)
            self._check_live()
            need(identity==self.policy_identity(),'evaluation changed adapter policy')
            return {**result,'rl_policy_identity':identity,'physical_event_id':e['event_id']}

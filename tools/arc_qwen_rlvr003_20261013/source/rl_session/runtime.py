"""Fixed disjoint batch updates, bounded state, physical-cost-preserving rollback."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json, time, uuid
import torch
from safetensors.torch import save_file, load_file
from .actor import NativeActor
from .common import need, digest, canonical, clone, tree_sha, finite, file_sha, rl_math
from .data import RewardPanel, Prompt
from .plan import POLICY,anchor_lr_multiplier,production_numeric_gate,cumulative_batch_deadline
from tools.arc_learning_agent_20261011.data import validate_records,semantic_sample_id
from tools.arc_qwen_transfer_20261012.data import prepare_record

def constant_lr_multiplier(step):
    need(type(step) is int and step>=0,'integer constant schedule step')
    return 1.


def schedule_recipe(stage,fixture):
    need(stage in ('anchor','rl','control') and type(fixture) is bool,'closed schedule role/scope')
    if stage=='anchor':return 'tiny-anchor-constant-2e4-v1' if fixture else 'historical-anchor-2e4-w4-c256-min01-v1'
    return 'rl-constant-1e6-v1' if stage=='rl' else 'control-constant-2e4-v1'


def schedule_definition(recipe):
    # Closed source recipes only: never deserialize a supplied callable.
    if recipe=='historical-anchor-2e4-w4-c256-min01-v1':return 2e-4,anchor_lr_multiplier,256
    if recipe=='tiny-anchor-constant-2e4-v1':return 2e-4,constant_lr_multiplier,64
    if recipe=='rl-constant-1e6-v1':return 1e-6,constant_lr_multiplier,4
    if recipe=='control-constant-2e4-v1':return 2e-4,constant_lr_multiplier,8192
    raise ValueError('unknown source-owned schedule recipe')


def make_source_scheduler(optimizer,recipe):
    base_lr,function,_=schedule_definition(recipe)
    need(type(optimizer) is torch.optim.AdamW and all(g['lr']==base_lr for g in optimizer.param_groups),
         'source schedule optimizer/base learning rate differs')
    return torch.optim.lr_scheduler.LambdaLR(optimizer,function)


def validate_source_scheduler_state(scheduler,recipe,state):
    base_lr,function,maximum=schedule_definition(recipe)
    need(type(scheduler) is torch.optim.lr_scheduler.LambdaLR,'owned LambdaLR required')
    step=state.get('last_epoch');groups=len(scheduler.optimizer.param_groups)
    need(type(step) is int and 0<=step<=maximum and type(state.get('_step_count')) is int and state['_step_count']==step+1,
         'source schedule step/count differs')
    need(all(state.get(key,False) is False for key in ('_get_lr_called_within_step','_is_initial')),
         'scheduler is not at a settled step boundary')
    need(all(type(state.get(k)) is list and all(type(x) in (int,float) for x in state[k])
             for k in ('base_lrs','_last_lr')),'source schedule scalar rate lists required')
    need(state.get('base_lrs')==[base_lr]*groups and state.get('_last_lr')==[base_lr*function(step)]*groups,
         'source schedule rate/state differs')
    need(state.get('lr_lambdas')==[None]*groups,'serialized callable state forbidden')
    need(all(type(g.get('initial_lr')) in (int,float) and type(g['lr']) in (int,float) and
             g['initial_lr']==base_lr and g['lr']==base_lr*function(step)
             for g in scheduler.optimizer.param_groups),'restored optimizer/schedule rate differs')
    return function


def restore_source_scheduler(scheduler,recipe,state):
    function=validate_source_scheduler_state(scheduler,recipe,state)
    groups=len(scheduler.optimizer.param_groups)
    scheduler.lr_lambdas=[function]*groups
    scheduler.load_state_dict(clone(state))
    need(all(f is function for f in scheduler.lr_lambdas),'owned schedule callable restore failed')


class Session(NativeActor):
    def __init__(self,*args,fixture_batch_count=1,**kwargs):
        super().__init__(*args,**kwargs)
        need(type(fixture_batch_count) is int and fixture_batch_count in (1,2) and
             (self.fixture or fixture_batch_count==1),'explicit one/two-batch CPU fixture only')
        self._fixture_batch_count=fixture_batch_count
        self.stage='anchor';self.counters={'anchor_updates':0,'rl_updates':0,'control_updates':0,
            'optimizer_steps':0,'scheduler_steps':0,'backward_calls':0,'sampler_cursor':0}
        self._training_pool=None;self._training_manifest=None;self._training_identity=None
        self._attempted_batches=0;self._rl_stop_reason=None
        self._pending_batch_id=None;self._batch_history=[];self._rl_continuation_identity=None
        self._phase_deadline=self.global_deadline
        self.sft_exposed=[];self._snapshots={};self._checkpoints={};self._batch_registry={}
        self._new_optimizer(2e-4,anchor=True)
    def _new_optimizer(self,lr,anchor=False):
        self.optimizer=torch.optim.AdamW(list(self.trainer.parameters.values()),lr=lr,
            betas=(.9,.999),eps=1e-8,weight_decay=0.,foreach=False)
        need(anchor is (self.stage=='anchor'),'optimizer stage/anchor declaration differs')
        self._schedule_recipe=schedule_recipe(self.stage,self.fixture)
        self.scheduler=make_source_scheduler(self.optimizer,self._schedule_recipe)
        self.counters['optimizer_steps']=self.counters['scheduler_steps']=0
        self._optimizer_ids=tuple(id(p) for p in self.trainer.parameters.values())
        self._optimizer_execution=self._optimizer_signature()
    def _optimizer_signature(self):
        def fn(f):return (id(getattr(f,'__self__',None)),id(getattr(f,'__func__',f)))
        return {'schedule_recipe':self._schedule_recipe,'optimizer':id(self.optimizer),'step':fn(self.optimizer.step),'defaults':tree_sha(self.optimizer.defaults),
                'scheduler':id(self.scheduler),'scheduler_optimizer':id(self.scheduler.optimizer),
                'scheduler_step':fn(self.scheduler.step),'scheduler_get_lr':fn(self.scheduler.get_lr),
                'lambdas':[fn(f) for f in self.scheduler.lr_lambdas],
                'param_groups':tree_sha([{k:v for k,v in g.items() if k!='params'} for g in self.optimizer.param_groups])}
    def _check_optimizer(self,*,check_counts=True):
        need(self._schedule_recipe==schedule_recipe(self.stage,self.fixture),'live schedule recipe/role differs')
        need(self._optimizer_signature()==self._optimizer_execution,'optimizer/scheduler execution drift')
        need(type(self.optimizer) is torch.optim.AdamW and type(self.scheduler) is torch.optim.lr_scheduler.LambdaLR,
             'owned optimizer/scheduler')
        need(self.scheduler.optimizer is self.optimizer,'scheduler optimizer ownership differs')
        need(getattr(self.scheduler,'_get_lr_called_within_step',None) is False and
             getattr(self.scheduler,'_is_initial',None) is False,'live scheduler step boundary differs')
        validate_source_scheduler_state(self.scheduler,self._schedule_recipe,self.scheduler.state_dict())
        need(tuple(id(p) for g in self.optimizer.param_groups for p in g['params'])==self._optimizer_ids,
             'optimizer parameter ownership differs')
        if check_counts:
            expected=self.counters['optimizer_steps']
            need(self.scheduler.last_epoch==self.counters['scheduler_steps'],'actual scheduler counter differs')
            need(not self.optimizer.state if expected==0 else set(self.optimizer.state)==set(self.trainer.parameters.values()),
                 'actual Adam parameter state inventory differs')
            if expected:
                need(all(torch.is_tensor(v.get('step')) and v['step'].numel()==1 and
                         bool(torch.isfinite(v['step'])) and float(v['step'])==expected
                         for v in self.optimizer.state.values()),'actual Adam step differs')
        need(not self.optimizer._optimizer_step_pre_hooks and not self.optimizer._optimizer_step_post_hooks,'optimizer hooks forbidden')
    def _counts(self):
        limits={'anchor_updates':256,'rl_updates':4,'control_updates':8192,'optimizer_steps':8192,
                'scheduler_steps':8192,'backward_calls':256+4*64+8192,'sampler_cursor':10_000_000}
        need(set(self.counters)==set(limits) and all(type(self.counters[k]) is int and 0<=self.counters[k]<=v
             for k,v in limits.items()),'source-bound variable counter range')
        need(self.counters['optimizer_steps']==self.counters['scheduler_steps'],'optimizer/scheduler counts differ')
    def _state(self):
        need(all(p.grad is None for p in self.trainer.parameters.values()),'state persistence requires cleared gradient boundary')
        self._counts();self._check_optimizer()
        need(self.stage in ('anchor','rl','control') and
             self.counters['optimizer_steps']==self.counters[self.stage+'_updates'],'stage optimizer count differs')
        need(self.counters['sampler_cursor']==self.counters['anchor_updates']+self.counters['control_updates']==len(self.sft_exposed),
             'committed SFT sampler/exposure counter differs')
        return clone({'adapters':self.trainer.parameters,'optimizer':self.optimizer.state_dict(),
            'optimizer_defaults':self.optimizer.defaults,'schedule_recipe':self._schedule_recipe,
            'scheduler':self.scheduler.state_dict(),'rng':self.trainer._get_rng(),'counters':self.counters,
            'training_identity':self._training_identity,
            'policy_version':self.policy_version,'stage':self.stage,'sft_exposed':self.sft_exposed,
            'training_modes':{n:m.training for n,m in self.model.named_modules()},
            'source_sha256':digest(self._sources),'base_identity_sha256':digest(self.native.identity),
            'structure_sha256':digest(self._structural),'counter_policy':{'id':'rl-fixed-disjoint-batches-v2',
                'anchor_max':256,'rl_max':4,'control_max':8192,'batches_max':4,
                'batch_slots':64,'planned_attempts':256}})
    def set_phase_deadline(self,deadline):
        import math
        need(type(deadline) in (int,float) and math.isfinite(deadline) and
             time.monotonic()<deadline<=self.global_deadline,'finite active phase deadline inside original session')
        self._phase_deadline=deadline
    def snapshot(self,label,*,deadline=None):
        deadline=min(self._phase_deadline,self.global_deadline if deadline is None else deadline)
        with self._lock,self.ledger.work('snapshot',deadline) as physical:
            physical.update(reserved_cost={'state_snapshots':1},dispatched=True)
            self._check_live();self._check_optimizer()
            need(all(p.grad is None for p in self.trainer.parameters.values()),'checkpoint only cleared boundary')
            need(len(self._snapshots)<8,'bounded snapshot registry full; release a held branch')
            payload=self._state();handle={'id':uuid.uuid4().hex,'label':label,'sha256':tree_sha(payload)}
            self._snapshots[handle['id']]=(deepcopy(handle),payload);physical['actual_cost']={'state_snapshots':1};return deepcopy(handle)
    def release_snapshot(self,handle):
        need(type(handle) is dict and handle.get('id') in self._snapshots and
             self._snapshots[handle['id']][0]==handle,'unknown snapshot release')
        del self._snapshots[handle['id']]
    def _restore_payload(self,payload):
        # Never load the 29GB frozen base. Immutable loader identity+versions
        # establish base ownership, while actual adapters/Adam/RNG are restored.
        self._check_structure();self._check_optimizer(check_counts=False)
        need(payload['source_sha256']==digest(self._sources) and payload['base_identity_sha256']==digest(self.native.identity)
             and payload['structure_sha256']==digest(self._structural),'cross-source/base/structure resume forbidden')
        need(payload.get('schedule_recipe')==schedule_recipe(payload['stage'],self.fixture),'saved schedule recipe/role differs')
        need(payload['training_identity']==self._training_identity,'training sampler/data identity differs')
        need(set(payload['adapters'])==set(self.trainer.parameters),'adapter tensor inventory')
        with torch.no_grad():
            for n,p in self.trainer.parameters.items():
                q=payload['adapters'][n]
                need(q.shape==p.shape and q.dtype==p.dtype,'adapter tensor shape/dtype')
                p.copy_(q.to(p.device))
        self.optimizer.load_state_dict(clone(payload['optimizer']));self.optimizer.defaults=clone(payload['optimizer_defaults'])
        restore_source_scheduler(self.scheduler,payload['schedule_recipe'],payload['scheduler'])
        self._schedule_recipe=payload['schedule_recipe']
        self.trainer._set_rng(payload['rng']);self.counters=deepcopy(payload['counters'])
        self.policy_version=payload['policy_version'];self.stage=payload['stage'];self.sft_exposed=list(payload['sft_exposed'])
        for n,m in self.model.named_modules():m.training=payload['training_modes'][n]
        self.optimizer.zero_grad(set_to_none=True);self._optimizer_execution=self._optimizer_signature()
        self._generation_epoch+=1 # Monotonic trajectory invalidation is physical, never rolled back.
        if self._pending_batch_id is not None:
            self._rl_stop_reason='unacknowledged-batch-invalidated-by-restore'
            self._pending_batch_id=None
        if self.stage=='rl' and self._rl_continuation_identity is not None and self._rl_continuation_identity!=(self.policy_version,self.counters['rl_updates']):
            self._rl_stop_reason='acknowledged-batch-state-rollback'
        self._owned.clear();self._batch_registry.clear();self._refresh();self._counts()
        need(tree_sha(self._state())==tree_sha(payload),'restored actual tensor/Adam/schedule/RNG state differs')
    def restore(self,handle,*,deadline):
        with self._lock,self.ledger.work('restore',min(deadline,self._phase_deadline)) as e:
            need(type(handle) is dict and handle.get('id') in self._snapshots,'unknown snapshot')
            original,payload=self._snapshots[handle['id']]
            need(handle==original and tree_sha(payload)==handle['sha256'],'snapshot mutation')
            e.update(reserved_cost={'state_restores':1},dispatched=True);self._restore_payload(payload);e['actual_cost']={'state_restores':1}
            return {'restored':True,'state_sha256':tree_sha(payload),'physical_events_preserved':len(self.ledger.events),
                    'logical_counters_restored':True,'trajectory_epoch_monotonic':self._generation_epoch,
                    'physical_attempted_batches':self._attempted_batches,'rl_stop_reason':self._rl_stop_reason}
    def begin_continuation(self,kind,*,deadline):
        with self._lock,self.ledger.work('continuation-optimizer-setup',min(deadline,self._phase_deadline)) as e:
            need(kind in ('rl','control') and self.stage=='anchor','continuation starts only from A')
            need(self.counters['anchor_updates']==(1 if self.fixture else 256),'exact SFT256 production anchor required')
            self._check_live();e['dispatched']=True;self.stage=kind
            self._new_optimizer(POLICY['rl_learning_rate'] if kind=='rl' else POLICY['control_learning_rate'])
            self.policy_version=kind+':'+uuid.uuid4().hex;self._generation_epoch+=1
            self._owned.clear();self._batch_registry.clear();self._refresh()
    def _commit(self,kind,deadline,event):
        self._deadline(deadline);self._check_optimizer()
        ps=list(self.trainer.parameters.values())
        with self.ledger.work('optimizer-commit',deadline) as e:
            e.update(update_batch_id=event.get('update_batch_id'),trajectory_id=None,reserved_cost={'optimizer_steps':1},dispatched=True)
            need(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in ps),'finite complete adapter gradients')
            need(any(bool((p.grad!=0).any()) for p in ps),'all-zero adapter gradient')
            norm=torch.nn.utils.clip_grad_norm_(ps,1.,error_if_nonfinite=True)
            event['optimizer_dispatched']=True
            self.optimizer.step();self.scheduler.step();e['actual_cost']={'optimizer_steps':1}
            self._optimizer_execution=self._optimizer_signature()
        need(finite(self.trainer.parameters) and finite(self.optimizer.state_dict()),'nonfinite committed state')
        self.counters[kind+'_updates']+=1;self.counters['optimizer_steps']+=1;self.counters['scheduler_steps']+=1
        self._optimizer_execution=self._optimizer_signature()
        self.policy_version=kind+':'+uuid.uuid4().hex;self._generation_epoch+=1
        self._owned.clear();self._batch_registry.clear();self.optimizer.zero_grad(set_to_none=True)
        self._refresh();self._counts();self._deadline(deadline)
        event.update(optimizer_event_id=e['event_id'],gradient_norm=float(norm),optimizer_committed=True,policy_version=self.policy_version)
    def bind_training_data(self,dataset,*,training_root=None):
        self._check_live()
        need(self.stage=='anchor' and self.counters['anchor_updates']==0 and self._training_pool is None,'bind training pool once before anchor')
        if not self.fixture:
            need(self.trainer.config['seed']==1917 and self.trainer.config['stability_mode'] is True and
                 self.trainer.config['accumulation_max_microbatches']==1,'historical production sampler/batch policy')
        panel=RewardPanel(dataset,training_root=training_root)
        need(all(p.exclusion is None for p in panel.prompts),'SFT source admission requires all fixed parents')
        records=dataset['records'];manifest=dataset['manifest']
        validate_records(records,manifest,())
        need(all(r['split']=='train' and r['kind']=='grid' for r in records),'fixed train-only grid pool')
        self._training_pool=deepcopy(records);self._training_manifest=deepcopy(manifest)
        self._training_identity=digest({'records':records,'manifest':manifest,'sampler':POLICY['training_sampler']})
        self.trainer._schedule_records=[{**{k:r[k] for k in ('kind','family_id','record_id')},'semantic_id':semantic_sample_id(r)} for r in records]
        self.trainer._effective_cycle=['grid']
        return {'training_identity':self._training_identity,'records':len(records),'selection_before_outcomes':True}
    def next_sft(self,*,deadline):
        need(self._training_pool is not None,'source-bound training stream required')
        epoch,offset=divmod(self.counters['sampler_cursor'],len(self._training_pool))
        order=self.trainer._order(len(self._training_pool),epoch)
        row=self._training_pool[order[offset]]
        return self._sft(row['messages'],row['completion'],row['record_id'],deadline,
                         prepared=self.native.validate_prepared(prepare_record(self.native,row)))
    def fixture_sft(self,*,deadline):
        need(self.fixture,'fixture only')
        return self._sft([{'role':'user','content':'Return a small rectangular grid of digits. Grid only.'}],
                         '1','fixed-fabricated-optimizer-fixture',deadline)
    def _sft(self,messages,completion,record_id,deadline,prepared=None):
        with self.ledger.work('owned-sft-step',min(deadline,self._phase_deadline)) as physical:
            physical['dispatched']=True
            return self._sft_impl(messages,completion,record_id,min(deadline,self._phase_deadline,physical.get('soft_deadline',deadline)),prepared=prepared)

    def _sft_impl(self,messages,completion,record_id,deadline,prepared=None):
        with self._lock:
            self._check_live();self._deadline(deadline)
            kind='anchor' if self.stage=='anchor' else 'control'
            need(self.stage in ('anchor','control'),'SFT role')
            need(self.counters[kind+'_updates']<(1 if self.fixture and kind=='anchor' else 256 if kind=='anchor' else 8192),'bounded SFT policy')
            snap=self.snapshot('before-'+kind,deadline=deadline);event={'optimizer_committed':False,'optimizer_dispatched':False}
            try:
                row=prepared if prepared is not None else self.native.validate_prepared(self.native.prepare_completion(messages,completion))
                with self._mode(True),self.ledger.work(kind+'-sft-forward-backward',deadline) as e:
                    ids=torch.tensor([row['input_ids']],device=self.device);labels=torch.tensor([row['labels']],device=self.device)
                    e.update(reserved_cost={'forward_calls':1,'backward_calls':1,'input_tokens':ids.numel()},dispatched=True,input_tokens=ids.numel())
                    if self.fixture:
                        out=self.model(input_ids=ids,attention_mask=torch.ones_like(ids),labels=labels,use_cache=False)
                        need(bool(torch.isfinite(out.loss)),'finite SFT loss');event['loss']=float(out.loss.detach())
                        out.loss.backward()
                    else:
                        result=self.trainer._accumulate(row)
                        for parameter in self.trainer.parameters.values():parameter.grad.div_(result['supervised_tokens'])
                        event['loss']=result['loss_sum']/result['supervised_tokens']
                    e['actual_cost']={'forward_calls':1,'backward_calls':1,'input_tokens':ids.numel()}
                    self.counters['backward_calls']+=1
                self._commit(kind,deadline,event)
                self.counters['sampler_cursor']+=1;self.sft_exposed.append(record_id)
                return event
            except Exception:
                self.optimizer.zero_grad(set_to_none=True)
                if self.fatal_error is None:self.restore(snap,deadline=self._phase_deadline)
                raise
            finally:self.release_snapshot(snap)
    def _admit_next_batch(self,batch_index):
        self._check_live()
        need(self.stage=='rl','RL phase required')
        need(self._rl_stop_reason is None,'RL arm already stopped: '+str(self._rl_stop_reason))
        need(self._pending_batch_id is None and not self._batch_registry,'previous batch must be acknowledged before collection')
        need(type(batch_index) is int and batch_index==self._attempted_batches and
             0<=batch_index<(self._fixture_batch_count if self.fixture else 4),'fixed attempted batch order')
        need(self._rl_continuation_identity is None or
             self._rl_continuation_identity==(self.policy_version,self.counters['rl_updates']),
             'next batch must retain the last acknowledged policy')
        self._attempted_batches+=1 # Physical attempts survive every branch restore.

    def collect_batch(self,panel,*,batch_index,max_new_tokens,deadline):
        with self._lock:
            need(type(panel) is RewardPanel and not self.fixture,'production train-only reward panel/phase')
            need(not panel.fixture_only,'fixture panel cannot enter production')
            prompts=panel.batch_prompts(batch_index)
            deadline=min(deadline,self._phase_deadline)
            self._admit_next_batch(batch_index)
            rows=[{'parent_id':p.parent_id,'slot':k,'trajectory':None,'reward':None,
                   'eligible':False,'status':'not-reached'} for p in prompts for k in range(8)]
            version=self.policy_version;error=None
            for index,slot in enumerate(rows):
                prompt=prompts[index//8];k=slot['slot']
                if time.monotonic()>=deadline or self.fatal_error:break
                try:
                    if prompt.exclusion:
                        slot.update(status='infrastructure-excluded',reason=prompt.exclusion);continue
                    panel.admit_prompt(prompt)
                    trajectory=self.sample(prompt,seed=panel.seed(batch_index,prompt.parent_id,k),max_new_tokens=max_new_tokens,deadline=deadline)
                    slot['trajectory']=trajectory
                    with self.ledger.work('strict-reward',min(deadline,self.global_deadline)) as e:
                        e['dispatched']=True;reward=panel.reward(prompt,trajectory)
                    slot.update(**reward,status='eligible' if reward['eligible'] else 'infrastructure-excluded')
                except Exception as exc:
                    slot.update(status='infrastructure-excluded',reason=type(exc).__name__+': '+str(exc)[:256])
                    error=slot['reason'];break
            if error or any(not r['eligible'] for r in rows):self._rl_stop_reason='incomplete-audit'
            return self._seal_batch(rows,64,version,batch_index,panel.panel_sha256)

    def collect_sweep(self,panel,*,sweep,max_new_tokens,deadline):
        # Compatibility at the controller boundary only; this is ONE disjoint G8 batch.
        return self.collect_batch(panel,batch_index=sweep,max_new_tokens=max_new_tokens,deadline=deadline)

    def _seal_batch(self,rows,planned,version,batch_index,panel_sha):
        from owned_runtime.policy import POLICY_SHA256
        need(version==self.policy_version,'actor version changed during complete batch')
        need(self._pending_batch_id is None and not self._batch_registry,'only one live batch')
        batch={'id':uuid.uuid4().hex,'planned_attempts':planned,'rows':rows,'policy_version':version,
               'generation_epoch':self._generation_epoch,'sweep':batch_index,'batch_index':batch_index,
               'parent_ids':list(dict.fromkeys(r['parent_id'] for r in rows)),
               'group_size':2 if self.fixture else 8,'planned_parents':self._fixture_batch_count if self.fixture else 32,
               'session_planned_attempts':2*self._fixture_batch_count if self.fixture else 256,
               'sampling_policy_sha256':None if self.fixture else POLICY_SHA256,
               'panel_sha256':panel_sha,'attempted_batches':self._attempted_batches,'stop_reason':self._rl_stop_reason,
               'fatal_native_state':self.fatal_error,'closed':len(rows)==planned,
               'all_slots_reached':all(r['status']!='not-reached' for r in rows)}
        self._pending_batch_id=batch['id'];self._batch_registry[batch['id']]=canonical(batch)
        return deepcopy(batch)

    def _check_batch(self,batch):
        need(type(batch) is dict and self._pending_batch_id==batch.get('id') and
             self._batch_registry.get(batch.get('id'))==canonical(batch),'unknown/mutated or consumed batch')
        need(self.stage=='rl' and batch['policy_version']==self.policy_version and
             batch['generation_epoch']==self._generation_epoch,'stale batch')
        need(batch['closed'] and batch['planned_attempts']==(2 if self.fixture else 64),'fixed batch-local denominator')
        need(batch['batch_index']==self._attempted_batches-1,'batch physical order differs')

    def _finish_batch(self,batch,status):
        # Called only after source-owned admission. Physical history is not checkpoint state.
        need(not any(r['batch_id']==batch['id'] for r in self._batch_history),'batch already consumed')
        receipt={'batch_id':batch['id'],'batch_index':batch['batch_index'],'parent_ids':batch['parent_ids'],
                 'status':status,'before_policy_version':batch['policy_version'],
                 'after_policy_version':self.policy_version,'rl_updates':self.counters['rl_updates'],
                 'physical_attempted_batches':self._attempted_batches,'rl_stop_reason':self._rl_stop_reason}
        self._batch_history.append(deepcopy(receipt))
        self._pending_batch_id=None;self._owned.clear();self._batch_registry.clear();self._generation_epoch+=1
        self._rl_continuation_identity=(self.policy_version,self.counters['rl_updates'])
        return receipt

    def acknowledge_batch(self,batch,*,status):
        with self._lock:
            self._check_live();self._check_batch(batch)
            need(status in ('zero-signal','incomplete-audit'),'closed no-update acknowledgment status')
            complete=all(r['eligible'] and r['status']=='eligible' for r in batch['rows'])
            if status=='zero-signal':
                need(complete,'incomplete batch is not zero signal')
                need(all(len({r['reward'] for r in batch['rows'] if r['parent_id']==parent})==1
                         for parent in batch['parent_ids']),'mixed rewards require numerical update admission')
            else:
                need(not complete,'complete batch cannot be relabeled incomplete')
                self._rl_stop_reason='incomplete-audit'
            return self._finish_batch(batch,status)

    def fixture_group(self,*,deadline,batch_index=0):
        """Predeclared one/two disjoint fabricated G2 batches, target16/seeds7,8."""
        with self._lock:
            need(self.fixture,'tiny fixture only')
            self._admit_next_batch(batch_index)
            messages=[{'role':'user','content':'Return a small rectangular grid of digits. Grid only.'}]
            parent='fabricated' if batch_index==0 else 'fabricated-second'
            prompt=Prompt(parent,'fixed-fixture' if batch_index==0 else 'fixed-fixture-second',canonical(messages),digest([[1,6]]),None)
            rows=[]
            for k,seed in enumerate((7,8)):
                t=self.sample(prompt,seed=seed,max_new_tokens=32,deadline=deadline)
                rows.append({'parent_id':prompt.parent_id,'slot':k,'trajectory':t,
                    'reward':None if t['infrastructure_excluded'] else int(t['format_text']=='16'),
                    'eligible':not t['infrastructure_excluded'],'status':'infrastructure-excluded' if t['infrastructure_excluded'] else 'eligible'})
            if any(not r['eligible'] for r in rows):self._rl_stop_reason='incomplete-audit'
            return self._seal_batch(rows,2,self.policy_version,batch_index,'explicit-fabricated-not-ARC')
    def update(self,batch,*,gate,deadline,failure_fixture=None):
        # A complete batch is an algorithmic phase, not one native operation.
        # Its cumulative source-bound budget is separate from each supervised
        # replay/backward/optimizer115/120-second physical window.
        return self._update_impl(batch,gate=gate,deadline=deadline,failure_fixture=failure_fixture)

    def _update_impl(self,batch,*,gate,deadline,failure_fixture=None):
        with self._lock:
            deadline=min(deadline,self._phase_deadline)
            self._check_live();self._deadline(deadline)
            self._check_batch(batch)
            need(self.fixture or gate==production_numeric_gate(),'production update requires exact source-bound numeric gate')
            need(self.stage=='rl' and batch['policy_version']==self.policy_version and
                 batch['generation_epoch']==self._generation_epoch,'stale batch')
            need(batch['closed'] and batch['planned_attempts']==(2 if self.fixture else 64),'fixed batch-local denominator')
            need(failure_fixture is None or self.fixture and failure_fixture=='after-step','failure fixture scope')
            batch_budget=gate.maximum_batch_replay_backward_seconds
            need(self.fixture or batch_budget is not None,'production cumulative replay/backward/commit budget must be source-bound')
            batch_started=time.monotonic()
            deadline=cumulative_batch_deadline(gate,deadline,batch_started,fixture=self.fixture)
            rows=batch['rows'];eligible=torch.tensor([r['eligible'] for r in rows],device=self.device)
            rewards=torch.tensor([r['reward'] if r['eligible'] else 0 for r in rows],device=self.device,dtype=torch.float32)
            groups=[r['parent_id'] for r in rows];versions=[batch['policy_version']]*len(rows)
            advantage,sizes,summary=rl_math.reward_groups(rewards,groups,eligible,versions)
            report={'optimizer_committed':False,'optimizer_dispatched':False,'groups':summary,
                'planned_attempts':batch['planned_attempts'],'batch_index':batch['batch_index'],
                'parent_ids':batch['parent_ids'],'session_planned_attempts':batch['session_planned_attempts'],
                'eligible_attempts':int(eligible.sum()),
                'not_reached':sum(r['status']=='not-reached' for r in rows),
                'infrastructure_excluded':sum(r['status']=='infrastructure-excluded' for r in rows),
                'actually_dispatched':sum(bool(r['trajectory'] and r['trajectory'].get('dispatched_forwards')) for r in rows),
                'replays':[],'backward_calls':0,'update_batch_id':batch['id'],
                'maximum_batch_replay_backward_seconds':batch_budget,'batch_id':batch['id'],
                'batch_started_monotonic':batch_started,'batch_deadline':deadline}
            for g in summary:
                g['pass_at_8']=int(g['successes']>0) if g['eligible']==8 and g['total']==8 else None
            mixed=sum(g['mixed'] for g in summary)
            if not bool(eligible.all()) or not batch['all_slots_reached'] or not mixed:
                complete=bool(eligible.all()) and batch['all_slots_reached']
                acknowledgment=self.acknowledge_batch(batch,status='zero-signal' if complete else 'incomplete-audit')
                return {**report,'batch_finished_monotonic':time.monotonic(),
                        'batch_acknowledgment':acknowledgment,
                        'status':'no-mixed-reward-no-update' if complete else 'incomplete-audit-no-update'}
            need(self.counters['rl_updates']<4,'RL update cap')
            snap=self.snapshot('before-complete-batch',deadline=deadline); replay_started=time.monotonic()
            report.update(batch_replay_started=replay_started,batch_deadline=deadline)
            try:
                # Every admitted trajectory gets its unchanged-policy diagnostic.
                # Graphs are released one by one. Backward may accumulate before
                # the final gate, but no parameter update occurs until ALL pass.
                for i,row in enumerate(rows):
                    if not row['eligible']:continue
                    replay=self.replay(row['trajectory'],deadline=deadline,update_batch_id=batch['id']);report['replays'].append(replay.diagnostic)
                    replay.diagnostic.update(group_advantage=float(advantage[i]),eligible_group_size=int(sizes[i]),
                        mixed_group_count=mixed,original_generated_length=len(replay.log_pi),
                        gradient_weight=(1./(mixed*int(sizes[i])*len(replay.log_pi)) if float(advantage[i])!=0. else 0.),
                        detached_DDIS_loss=0.)
                    if float(advantage[i])!=0.:
                        ratio=(replay.log_pi.float()-replay.log_mu.detach()).clamp(-20,20).exp()
                        mask=(ratio>.8)&(ratio<1.28)
                        loss=-(ratio.detach()*advantage[i]*replay.log_pi*mask).sum()/(mixed*int(sizes[i])*len(replay.log_pi))
                        need(bool(torch.isfinite(loss)),'finite full-batch micro contribution')
                        replay.diagnostic['detached_DDIS_loss']=float(loss.detach())
                        with self._mode(True),self.ledger.work('ddis-backward',deadline) as e:
                            e.update(trajectory_id=row['trajectory']['trajectory_id'],update_batch_id=batch['id'],reserved_cost={'backward_calls':1,'input_tokens':len(row['trajectory']['original_ids'])-1},dispatched=True);loss.backward()
                            e['actual_cost']={'backward_calls':1,'input_tokens':len(row['trajectory']['original_ids'])-1}
                        replay.diagnostic['backward_event_id']=e['event_id']
                        replay.diagnostic['backward_seconds']=e['seconds']
                        replay.diagnostic['seconds']+=e['seconds']
                        if self.device.type=='cuda':
                            replay.diagnostic['peak_memory_bytes']=torch.cuda.max_memory_allocated(self.device)
                            replay.diagnostic['peak_reserved_bytes']=torch.cuda.max_memory_reserved(self.device)
                        report['backward_calls']+=1;self.counters['backward_calls']+=1
                        del loss
                    del replay
                from owned_runtime.evidence import MAX_REPLAY_BYTES
                need(all(len(canonical(r))<=MAX_REPLAY_BYTES for r in report['replays']),'complete replay/backward diagnostic expansion cap')
                report['numerical_gate']=self.numerical_admission(report['replays'],gate)
                report['whole_replay_backward_seconds']=time.monotonic()-replay_started
                report['peak_allocated_bytes']=max((r.get('peak_memory_bytes') or 0 for r in report['replays']),default=0) if self.device.type=='cuda' else None
                report['peak_reserved_bytes']=max((r.get('peak_reserved_bytes') or 0 for r in report['replays']),default=0) if self.device.type=='cuda' else None
                if batch_budget is not None and report['whole_replay_backward_seconds']>batch_budget:
                    report['numerical_gate']['failures'].append('whole-replay-backward:runtime')
                    report['numerical_gate']['admitted']=False
                if not report['numerical_gate']['admitted']:
                    self.optimizer.zero_grad(set_to_none=True);self.restore(snap,deadline=self._phase_deadline)
                    self._rl_stop_reason='numeric-nonadmission'
                    return {**report,'batch_finished_monotonic':time.monotonic(),'status':'numeric-nonadmission-no-update',
                            'batch_acknowledgment':self._finish_batch(batch,'numeric-nonadmission-no-update')}
                self._commit('rl',deadline,report)
                if failure_fixture=='after-step':raise TimeoutError('explicit after-step rollback fixture')
                return {**report,'batch_finished_monotonic':time.monotonic(),'status':'committed',
                        'batch_acknowledgment':self._finish_batch(batch,'committed'),'gradient_divisor':'mixed-groups * eligible-group-size * original-generated-length'}
            except Exception as exc:
                self.optimizer.zero_grad(set_to_none=True)
                try:
                    if self.fatal_error is None:report['rollback']=self.restore(snap,deadline=self._phase_deadline)
                except Exception as rollback_exc:
                    report['rollback_error']=type(rollback_exc).__name__+': '+str(rollback_exc)[:256]
                    self._rl_stop_reason='rollback-failed'
                    report.update(status='update-failed',batch_finished_monotonic=time.monotonic(),
                                  error=type(exc).__name__+': '+str(exc)[:256])
                    rollback_exc.update_report=deepcopy(report)
                    raise
                self._rl_stop_reason='update-failed'
                report['rolled_back_optimizer_commit']=bool(report.get('optimizer_committed'))
                report['optimizer_committed']=False
                report['physical_update_event_ids']=[e['event_id'] for e in self.ledger.events if e.get('update_batch_id')==batch['id']]
                report.update(status='update-failed',batch_finished_monotonic=time.monotonic(),
                              error=type(exc).__name__+': '+str(exc)[:256],
                              batch_acknowledgment=self._finish_batch(batch,'update-failed'))
                exc.update_report=deepcopy(report)
                raise
            finally:self.release_snapshot(snap)
    def save(self,directory,*,deadline):
        with self._lock,self.ledger.work('checkpoint-save',min(deadline,self._phase_deadline)) as e:
            self._check_live();e.update(reserved_cost={'checkpoint_saves':1},dispatched=True);payload=self._state();directory=Path(directory)
            need(not directory.exists(),'new immutable checkpoint directory required')
            from owned_runtime.storage import before_save
            before_save(directory,fixture=self.fixture)
            directory.mkdir(parents=True);e['dispatched']=True
            # Real adapter safetensors plus optimizer/scheduler/RNG tensor state.
            self.model.save_pretrained(directory/'adapter',safe_serialization=True)
            torch.save(payload,directory/'state.pt')
            from owned_runtime.storage import summarize_state
            from experiment_flow.contracts import write_json
            summary=summarize_state(payload,self.trainer.fingerprint()['sha256'],list(self.trainer.parameters))
            need(summary['state_sha256']==tree_sha(payload),'actual state summary differs')
            write_json(directory/'state-summary.json',summary)
            manifest={'format':'rl-owned-same-source-state-v1','state_sha256':tree_sha(payload),'physical_event_id':e['event_id'],
                'source_sha256':digest(self._sources),'policy_version':self.policy_version,
                'counts':deepcopy(self.counters),'files':{p.relative_to(directory).as_posix():file_sha(p)
                    for p in directory.rglob('*') if p.is_file()},'physical_ledger_imported_as_state':False}
            manifest['state_summary_file_sha256']=manifest['files']['state-summary.json']
            (directory/'manifest.json').write_bytes(canonical(manifest))
            self._checkpoints[str(directory.resolve())]=canonical(manifest)
            e.update(checkpoint_path=str(directory.resolve()),manifest_sha256=file_sha(directory/'manifest.json'),
                     state_sha256=manifest['state_sha256'])
            e['actual_cost']={'checkpoint_saves':1}
            return deepcopy(manifest)
    def reload(self,directory,*,deadline):
        with self._lock,self.ledger.work('checkpoint-reload',min(deadline,self._phase_deadline)) as e:
            directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
            need(self._checkpoints.get(str(directory.resolve()))==canonical(manifest),'unknown/cross-session checkpoint')
            need({p.relative_to(directory).as_posix():file_sha(p) for p in directory.rglob('*')
                  if p.is_file() and p.name!='manifest.json'}==manifest['files'],'checkpoint file drift')
            e.update(reserved_cost={'checkpoint_reloads':1},dispatched=True)
            tensors=load_file(str(directory/'adapter/adapter_model.safetensors'))
            from peft import get_peft_model_state_dict
            payload=torch.load(directory/'state.pt',map_location='cpu',weights_only=True)
            need(tree_sha(payload)==manifest['state_sha256'],'state tensor/RNG digest mismatch')
            self._restore_payload(payload)
            need(tree_sha(tensors)==tree_sha(get_peft_model_state_dict(self.model)),'real safetensors adapter parity')
            from owned_runtime.storage import summarize_state
            summary=json.loads((directory/'state-summary.json').read_text())
            actual_summary=summarize_state(self._state(),self.trainer.fingerprint()['sha256'],list(self.trainer.parameters))
            need(summary==actual_summary and file_sha(directory/'state-summary.json')==manifest['state_summary_file_sha256'],'actual restored state summary parity')
            e.update(checkpoint_path=str(directory.resolve()),manifest_sha256=file_sha(directory/'manifest.json'),
                     state_sha256=manifest['state_sha256'])
            e['actual_cost']={'checkpoint_reloads':1}
            return {'reload_verified':True,'same_source':True,'physical_event_id':e['event_id'],
                    'checkpoint_path':str(directory.resolve()),'manifest_sha256':file_sha(directory/'manifest.json'),
                    'updates':self.counters['anchor_updates'],
                    'state_sha256':tree_sha(self._state()),'safetensors_verified':True,
                    'counter_policy':payload['counter_policy'],'physical_ledger_preserved':True,
                    'physical_attempted_batches':self._attempted_batches,'rl_stop_reason':self._rl_stop_reason,
                    'batch_history':deepcopy(self._batch_history),
                    'state_summary_file_sha256':manifest['state_summary_file_sha256'],'state_summary_verified':True}

    def close(self,*,deadline=None,ledger_path=None):
        """Always release owned references, including after a fatal device error.

        CPU reference closure is separate from verified device synchronization.
        Failed synchronization never becomes a successful model-stopped claim.
        Returned/optional persisted ledger includes cleanup and never rolls back.
        """
        with self._lock:
            if self._closed:return deepcopy(self._closure)
            if deadline is None:deadline=self.global_deadline
            import math
            need(type(deadline) in (int,float) and math.isfinite(deadline) and deadline<=self.global_deadline,
                 'closure deadline cannot extend original global deadline')
            event={'event_id':len(self.ledger.events),'phase':'session-cleanup','started':time.monotonic(),
                   'dispatched':True,'status':'started','clock':'synchronized-wall-time','device_time_measured':False}
            if hasattr(self.ledger,'start_cleanup'):
                event=self.ledger.start_cleanup(deadline=deadline)
            else:
                self.ledger.events.append(event)
            identity={'policy_version':self.policy_version,'source_sha256':digest(self._sources),
                      'adapter_identity_verified':False};errors=[];synchronized=False
            try:
                if self.fatal_error is None:
                    identity={**self.policy_identity(),'adapter_identity_verified':True}
                self.ledger.sync();synchronized=True
            except Exception as exc:
                self._mark_fatal(exc);errors.append(type(exc).__name__+': '+str(exc)[:256])
            finally:
                self._snapshots.clear();self._owned.clear();self._batch_registry.clear()
                self._training_pool=None;self._training_manifest=None
                self.optimizer=None;self.scheduler=None
                self.trainer.model=None;self.trainer.parameters.clear()
                self.trainer.optimizer=None;self.trainer.scheduler=None
                self.trainer._snapshots.clear();self.trainer._training_snapshots.clear()
                self.native.close();self.model=None;self._closed=True
            try:self.ledger.sync()
            except Exception as exc:
                synchronized=False;self._mark_fatal(exc);errors.append(type(exc).__name__+': '+str(exc)[:256])
            event.update(ended=time.monotonic(),seconds=time.monotonic()-event['started'],
                         status='complete' if synchronized else 'unclosed-device-error',
                         late=time.monotonic()>=deadline,errors=errors)
            settled=all('ended' in e and e['status'] not in ('started','reserved','unclosed-device-error','unknown') for e in self.ledger.events)
            self.ledger.closed=True
            if self._owned_grant is not None:
                from owned_runtime.admission import revoke
                revoke(self._owned_grant)
            self._closure={'closed':True,'future_operations_blocked':True,'final_policy_identity':identity,
                'logical_counters':deepcopy(self.counters),'physical_attempted_batches':self._attempted_batches,
                'batch_history':deepcopy(self._batch_history),'rl_stop_reason':self._rl_stop_reason,
                'model_references_released':True,'device_synchronized':synchronized,
                'model_stopped':synchronized and settled,'ledger_settled':settled,'fatal_native_state':self.fatal_error,
                'closed_monotonic':event['ended'],'original_global_deadline':self.global_deadline,
                'physical_events':deepcopy(self.ledger.events),'physical_events_sha256':digest(list(self.ledger.events))}
            if hasattr(self.ledger,'summary'):
                self._closure['durable_ledger']=self.ledger.summary()
            if ledger_path is not None:
                path=Path(ledger_path);need(not path.exists(),'new closure ledger path required')
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(self._closure))
                self._closure['persisted_ledger_path']=str(path.resolve());self._closure['persisted_ledger_sha256']=file_sha(path)
            return deepcopy(self._closure)

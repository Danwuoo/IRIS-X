"""Source TRM pretraining step, persistent ACT carry, EMA and exact resume.

The model/loss/sparse optimizer and EMA execute pinned original source. Bounded
prefix checks do not establish the original eight-H100, global-3072 epoch.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import fields,is_dataclass
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

from .arc_nvarc_m3_trm import _initial_carry_on_device
from .arc_nvarc_trm_runtime import construct_source_model
from .canonical import digest_value
from .canonical import canonical_bytes
from .errors import ValidationError

REFERENCE_HASHES={
    'pretrain-no-eval.py':'59dfb2523507046af3126790c473f371111f7b7ded77233266a71ea13d3104ac',
    'ema.py':'41f92b2ec89a53ebcd69ced5903ccc4519a199ec2208d9694dd49ec398379ece'}
FUNCTION_HASHES={
    'cosine_schedule_with_warmup_lr_lambda':'27286171d14bbc8d0b0ba4e16ac75a2b5c8610404aaed9c2004d636fd6b3367c',
    'compute_lr':'adf79420e4493052c43cc80226cbe25b3596652b7666e81493dc76fadbd62f32',
    'train_batch':'caa4968e0c81efb1a87f1dd6d810eefcc70845f0ef73629c71cd97917063589d'}


def reference_functions(root):
    import torch
    actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
    if actual!=REFERENCE_HASHES or any(p.is_symlink() for p in root.iterdir()):
        raise ValidationError('TRM training reference inventory differs')
    tree=ast.parse((root/'pretrain-no-eval.py').read_text(encoding='utf-8'))
    functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in FUNCTION_HASHES]
    if {node.name:hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest() for node in functions}!=FUNCTION_HASHES:
        raise ValidationError('TRM original training function AST differs')
    namespace={'torch':torch,'dist':torch.distributed,'math':math,'Any':object,
        'PretrainConfig':SimpleNamespace,'TrainState':SimpleNamespace}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(root/'pretrain-no-eval.py'),'exec'),namespace)
    ema_namespace={'copy':copy,'nn':torch.nn}
    exec(compile((root/'ema.py').read_text(encoding='utf-8'),str(root/'ema.py'),'exec'),ema_namespace)
    namespace['EMAHelper']=ema_namespace['EMAHelper']
    return namespace


def build_training_reference(source,output):
    if output.exists():raise ValidationError('new TRM training reference required')
    paths={'pretrain-no-eval.py':source/'TRM/pretrain-no-eval.py',
        'ema.py':source/'external/TinyRecursiveModels/models/ema.py'}
    if any(hashlib.sha256(path.read_bytes()).hexdigest()!=REFERENCE_HASHES[name] for name,path in paths.items()):
        raise ValidationError('TRM retained training source differs')
    output.mkdir(parents=True)
    for name,path in paths.items():(output/name).write_bytes(path.read_bytes())
    reference_functions(output)
    return digest_value(REFERENCE_HASHES)


def pack_tree(value):
    import torch
    if isinstance(value,torch.Tensor):return value.detach().cpu().clone()
    if is_dataclass(value):return {field.name:pack_tree(getattr(value,field.name)) for field in fields(value)}
    if isinstance(value,dict):return {key:pack_tree(item) for key,item in value.items()}
    if isinstance(value,list):return [pack_tree(item) for item in value]
    if isinstance(value,tuple):return tuple(pack_tree(item) for item in value)
    if value is None or isinstance(value,(str,int,float,bool)):return value
    raise ValidationError('unsupported TRM checkpoint tree')


def restore_carry(template,saved,device):
    import torch
    if is_dataclass(template):
        if set(saved)!={field.name for field in fields(template)}:raise ValidationError('TRM checkpoint carry fields differ')
        return type(template)(**{field.name:restore_carry(getattr(template,field.name),saved[field.name],device) for field in fields(template)})
    if isinstance(template,dict):
        if set(saved)!=set(template):raise ValidationError('TRM checkpoint data keys differ')
        return {key:restore_carry(item,saved[key],device) for key,item in template.items()}
    if isinstance(template,torch.Tensor):
        if not isinstance(saved,torch.Tensor) or saved.shape!=template.shape or saved.dtype!=template.dtype:
            raise ValidationError('TRM checkpoint carry tensor differs')
        return saved.to(device)
    raise ValidationError('unsupported TRM checkpoint carry')


def tensor_tree_inventory(value,prefix='root'):
    import torch
    result={}
    def walk(item,name):
        if isinstance(item,torch.Tensor):
            h=hashlib.sha256();flat=item.detach().reshape(-1)
            for offset in range(0,flat.numel(),1048576):
                chunk=flat[offset:offset+1048576].cpu().contiguous()
                if chunk.is_floating_point() and not bool(torch.isfinite(chunk).all()):
                    raise ValidationError('TRM state tensor non-finite: '+name)
                h.update(chunk.view(torch.uint8).numpy().tobytes())
            result[name]={'shape':list(item.shape),'dtype':str(item.dtype),'sha256':h.hexdigest()}
        elif is_dataclass(item):
            for field in fields(item):walk(getattr(item,field.name),name+'/'+field.name)
        elif isinstance(item,dict):
            for key,child in item.items():walk(child,name+'/'+str(key))
        elif isinstance(item,(list,tuple)):
            for index,child in enumerate(item):walk(child,name+'/'+str(index))
        elif item is None or isinstance(item,(str,int,float,bool)):
            result[name]={'scalar':item}
        else:raise ValidationError('unsupported TRM state inventory')
    walk(value,prefix)
    return result


class SourceTRMTrainer:
    def __init__(self,classes,model_config,config,reference,identity,device='cpu'):
        self.device=device;self.config=SimpleNamespace(**config);self.identity=identity
        self.reference=reference;self.model=construct_source_model(classes,model_config,device)
        self.model_config=model_config
        self.model.train()
        _,_,sparse,adam=classes
        self.optimizers=[sparse(self.model.model.puzzle_emb.buffers(),world_size=1,lr=0.,
            weight_decay=self.config.puzzle_emb_weight_decay),adam(self.model.parameters(),lr=.001,
            weight_decay=self.config.weight_decay,betas=(self.config.beta1,self.config.beta2))]
        self.base_lrs=[self.config.puzzle_emb_lr,self.config.lr]
        self.ema=reference['EMAHelper'](mu=self.config.ema_rate);self.ema.register(self.model)
        self.step=0;self.carry=None

    def train(self,batch):
        import torch
        if self.step>=self.config.total_steps:raise ValidationError('TRM training step ceiling reached')
        self.step+=1
        batch={key:value.to(self.device) for key,value in batch.items()}
        if len(batch['inputs'])!=self.config.global_batch_size:raise ValidationError('TRM reduced batch size differs')
        if self.carry is None:self.carry=_initial_carry_on_device(self.model,batch)
        self.carry,loss,metrics,_,_=self.model(carry=self.carry,batch=batch,return_keys=[])
        normalized=loss/self.config.global_batch_size
        if not bool(torch.isfinite(normalized)):raise ValidationError('TRM source loss non-finite')
        normalized.backward()
        gradients=[value.grad for value in (*self.model.parameters(),*self.model.buffers()) if value.grad is not None]
        if not gradients or any(not bool(torch.isfinite(value).all()) for value in gradients):
            raise ValidationError('TRM source gradient missing/non-finite')
        nonzero=sum(int(bool(torch.any(value!=0))) for value in gradients)
        rates=[]
        for optimizer,base in zip(self.optimizers,self.base_lrs):
            rate=self.reference['compute_lr'](base,self.config,SimpleNamespace(step=self.step,total_steps=self.config.total_steps))
            for group in optimizer.param_groups:group['lr']=rate
            rates.append(rate);optimizer.step();optimizer.zero_grad()
        self.ema.update(self.model)
        return {'step':self.step,'loss':float(normalized.detach().cpu()),'learning_rates':rates,
            'nonzero_gradient_tensors':nonzero,'carry_steps':self.carry.steps.detach().cpu().tolist(),
            'halted':self.carry.halted.detach().cpu().tolist(),'input_tokens':int(batch['inputs'].numel()),
            'supervised_tokens':int((batch['labels']!=-100).sum())}

    def state(self):
        import torch
        return {'identity':self.identity,'model_config':self.model_config,'config':vars(self.config),
            'step':self.step,'model':pack_tree(self.model.state_dict()),
            'optimizers':[pack_tree(optimizer.state_dict()) for optimizer in self.optimizers],
            'ema':pack_tree(self.ema.state_dict()),'carry':pack_tree(self.carry),
            'rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state(self.device) if str(self.device).startswith('cuda') else None}

    def save(self,path):
        import torch
        if path.exists():raise ValidationError('new TRM checkpoint path required')
        torch.save(self.state(),path)

    def restore(self,path,batch):
        import torch
        saved=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
        if saved['identity']!=self.identity or saved['model_config']!=self.model_config or saved['config']!=vars(self.config):
            raise ValidationError('TRM checkpoint identity/config differs')
        self.model.load_state_dict(saved['model'],strict=True)
        if len(saved['optimizers'])!=len(self.optimizers):raise ValidationError('TRM checkpoint optimizer count differs')
        for optimizer,state in zip(self.optimizers,saved['optimizers']):optimizer.load_state_dict(state)
        self.ema.load_state_dict({key:value.to(self.device) for key,value in saved['ema'].items()})
        template=_initial_carry_on_device(self.model,{key:value.to(self.device) for key,value in batch.items()})
        self.carry=restore_carry(template,saved['carry'],self.device) if saved['carry'] is not None else None
        self.step=saved['step'];torch.set_rng_state(saved['rng'])
        if saved['cuda_rng'] is not None:torch.cuda.set_rng_state(saved['cuda_rng'],self.device)


def training_config():
    return {'global_batch_size':8,'lr':.0003,'lr_min_ratio':1.,'lr_warmup_steps':2000,
        'beta1':.9,'beta2':.95,'weight_decay':.1,'puzzle_emb_weight_decay':.1,
        'puzzle_emb_lr':.01,'ema_rate':.999,'total_steps':2}


def training_model_config():
    from .arc_nvarc_trm_checkpoint import published_model_config
    return {**published_model_config(device_dtype='bfloat16'),'batch_size':8,
        'num_puzzle_identifiers':1041208,'H_cycles':3,'halt_max_steps':16,'halt_exploration_prob':.1}


def verify_trm_export(folder,expected_digest):
    import torch
    manifest=json.loads((folder/'material.json').read_bytes())
    if set(p.name for p in folder.iterdir() if p.is_file())!={'material.json','trm-ema.pt'} or digest_value(manifest)!=expected_digest:
        raise ValidationError('TRM exported closed material differs')
    path=folder/'trm-ema.pt'
    with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=manifest['checkpoint_sha256']:raise ValidationError('TRM exported checkpoint bytes differ')
    state=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
    if tensor_tree_inventory(state)!=manifest['tensor_inventory']:
        raise ValidationError('TRM exported actual tensor bytes differ')
    return manifest


def run_prefix(plan_path,bundle,reference_path,prefix_path,checkpoint,mode,output,export):
    import numpy as np
    import torch
    from .arc_nvarc_trm_runtime import runtime_classes
    plan=json.loads(plan_path.read_bytes())
    if (plan['format']!='irisx/nvarc-source-trm-training-v1' or not plan['approved'] or
            plan['owner_decision']!='Decision 0053' or plan['config']!=training_config() or
            plan['model_config']!=training_model_config() or plan['maximum_optimizer_steps']!=2 or
            plan['maximum_generations']!=0 or plan['maximum_teacher_calls']!=0 or plan['maximum_paid_usd']!=0):
        raise ValidationError('TRM bounded pretraining plan differs')
    with prefix_path.open('rb') as stream:prefix_sha=hashlib.file_digest(stream,'sha256').hexdigest()
    if prefix_sha!=plan['prefix_sha256']:raise ValidationError('TRM training prefix digest differs')
    with np.load(prefix_path,allow_pickle=False) as prefix:
        if set(prefix.files)!={'inputs','labels','puzzle_identifiers'}:raise ValidationError('TRM training prefix columns differ')
        inputs,labels,ids=[prefix[name].copy() for name in ('inputs','labels','puzzle_identifiers')]
    if inputs.shape!=(8,900) or labels.shape!=inputs.shape or ids.shape!=(8,) or np.any(inputs>11) or np.any(labels>11):
        raise ValidationError('TRM training prefix shapes/vocabulary differ')
    batch={'inputs':torch.from_numpy(inputs.astype(np.int32)),
        'labels':torch.from_numpy(np.where(labels==0,-100,labels.astype(np.int32))),
        'puzzle_identifiers':torch.from_numpy(ids.astype(np.int32))}
    if output.exists():raise ValidationError('new TRM training output required')
    output.mkdir(parents=True)
    def save(name,value):(output/name).write_bytes(canonical_bytes(value,newline=True))
    reference=reference_functions(reference_path)
    if plan['training_reference_digest']!=digest_value(REFERENCE_HASHES):raise ValidationError('TRM source reference binding differs')
    torch.manual_seed(0);torch.cuda.manual_seed_all(0)
    with runtime_classes(bundle,plan['source_bundle_digest']) as classes:
        trainer=SourceTRMTrainer(classes,plan['model_config'],plan['config'],reference,plan['identity_digest'],'cuda:0')
        torch.cuda.reset_peak_memory_stats(0)
        if mode=='resume':
            trainer.restore(checkpoint,batch)
            if trainer.step!=1:raise ValidationError('TRM exact step-one checkpoint required')
            saved=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)
            if tensor_tree_inventory(trainer.state())!=tensor_tree_inventory(saved):
                raise ValidationError('TRM restart model/optimizer/carry/EMA/RNG differs')
            save('restart.json',{'exact_model_optimizer_carry_ema_rng':True,'step':1,
                'checkpoint_sha256':hashlib.file_digest(checkpoint.open('rb'),'sha256').hexdigest()})
        elif mode!='pause':raise ValidationError('TRM runtime mode differs')
        observation=trainer.train(batch);save('step.json',observation)
        state=trainer.state();inventory=tensor_tree_inventory(state)
        checkpoint_out=checkpoint if mode=='pause' else checkpoint.with_name('checkpoint-2.pt')
        if checkpoint_out.exists():raise ValidationError('new TRM checkpoint bytes required')
        torch.save(state,checkpoint_out)
        save('checkpoint-manifest.json',{'step':trainer.step,'identity_digest':trainer.identity,
            'tensor_inventory':inventory,'checkpoint_bytes':checkpoint_out.stat().st_size,
            'checkpoint_sha256':hashlib.file_digest(checkpoint_out.open('rb'),'sha256').hexdigest(),
            'optimizer_checkpoint_bytes_retained':False})
        if mode=='resume':
            trainer.ema.ema(trainer.model)
            export.mkdir(parents=True)
            exported=pack_tree(trainer.model.state_dict())
            torch.save(exported,export/'trm-ema.pt')
            material={'format':'irisx/nvarc-source-trm-export-v1','training_identity_digest':trainer.identity,
                'model_config':trainer.model_config,'tensor_inventory':tensor_tree_inventory(exported),
                'checkpoint_sha256':hashlib.file_digest((export/'trm-ema.pt').open('rb'),'sha256').hexdigest(),
                'optimizer_steps':2,'contains_evaluator_truth':False,'full_scale_training_verified':False}
            (export/'material.json').write_bytes(canonical_bytes(material,newline=True))
            verify_trm_export(export,digest_value(material))
            save('result.json',{'run_id':plan['run_id'],'plan_digest':digest_value(plan),'identity_digest':trainer.identity,
                'export_material_digest':digest_value(material),'optimizer_steps':2,'generation_calls':0,
                'process_restart_exact':True,'ema_export_actual_tensor_reload':True,
                'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(0),
                'cuda_peak_reserved_bytes':torch.cuda.max_memory_reserved(0),
                'input_tokens':14400,'supervised_tokens':1584,'full_scale_training_verified':False,
                'contains_evaluator_truth':False,'correctness_scored':False})
    return observation


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('pause','resume'),required=True)
    for name in ('plan','bundle','reference','prefix','checkpoint','output','export'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    run_prefix(args.plan,args.bundle,args.reference,args.prefix,args.checkpoint,args.mode,args.output,args.export)

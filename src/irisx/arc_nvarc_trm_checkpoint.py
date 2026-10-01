"""Strict published TRM state loading with the source puzzle-embedding reset.

The original NVARC evaluator replaces a differently sized puzzle embedding by
its mean. Only the compiler wrapper prefix and that explicit reset may differ;
all other state names, shapes and tensors must load without dropped keys.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

from .errors import ValidationError


PUZZLE_EMBEDDING='model.inner.puzzle_emb.weights'


def load_published_state(model,checkpoint:Path,expected_sha256:str,*,compiler_prefix='_orig_mod.'):
    import torch
    if checkpoint.is_symlink() or not checkpoint.is_file():
        raise ValidationError('published TRM checkpoint path differs')
    with checkpoint.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=expected_sha256:raise ValidationError('published TRM checkpoint digest differs')
    if compiler_prefix not in {'_orig_mod.',''}:raise ValidationError('explicit TRM compiler prefix differs')
    raw=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)
    if (not isinstance(raw,dict) or not raw or
            any(not isinstance(name,str) or not name.startswith(compiler_prefix) or
                not isinstance(value,torch.Tensor) for name,value in raw.items())):
        raise ValidationError('published TRM tensor-only compiler state differs')
    state={name.removeprefix(compiler_prefix):value for name,value in raw.items()}
    target=model.state_dict()
    if set(state)!=set(target):raise ValidationError('published TRM closed state names differ')
    source_shape=list(state[PUZZLE_EMBEDDING].shape);target_shape=list(target[PUZZLE_EMBEDDING].shape)
    reset=source_shape!=target_shape
    if reset:
        if (len(source_shape)!=2 or len(target_shape)!=2 or source_shape[1]!=target_shape[1] or
                source_shape[0]<1 or target_shape[0]<1):
            raise ValidationError('published TRM puzzle embedding dimensions differ')
        state[PUZZLE_EMBEDDING]=state[PUZZLE_EMBEDDING].mean(dim=0,keepdim=True).expand(target_shape).contiguous()
    for name,value in state.items():
        if value.shape!=target[name].shape or not value.is_floating_point() or not bool(torch.isfinite(value).all()):
            raise ValidationError('published TRM finite state shape differs: '+name)
    model.load_state_dict(state,strict=True)
    for name,value in model.state_dict().items():
        if not torch.equal(value.detach().cpu(),state[name].to(dtype=value.dtype)):
            raise ValidationError('published TRM copied tensor bytes differ: '+name)
    return {'checkpoint_sha256':actual,'checkpoint_bytes':checkpoint.stat().st_size,'state_tensor_count':len(state),
        'source_puzzle_embedding_shape':source_shape,'target_puzzle_embedding_shape':target_shape,
        'source_mean_reset_applied':reset,'dropped_state_keys':0,'loaded_tensors_exact_after_explicit_dtype_cast':True,
        'original_notebook_v18_verified':False,'explicit_compiler_prefix':compiler_prefix}


def published_model_config(*,device_dtype='float32'):
    return {'batch_size':1,'seq_len':900,'puzzle_emb_ndim':512,'num_puzzle_identifiers':1,
        'vocab_size':12,'H_cycles':4,'L_cycles':4,'H_layers':0,'L_layers':2,'hidden_size':512,
        'expansion':4,'num_heads':8,'pos_encodings':'rope','halt_max_steps':10,
        'halt_exploration_prob':0.,'forward_dtype':device_dtype,'puzzle_emb_len':16,'no_ACT_continue':True}

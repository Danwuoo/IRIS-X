"""One original-family full-gradient global-256 packed throughput observation.

This is a precisely bound FSDP resource backend, not historical NeMo TP/CP
parity, a trained checkpoint, a full SFT epoch or ARC quality evidence.
"""
from __future__ import annotations
import argparse
from functools import partial
import json
import os
from pathlib import Path
import re
import time

from .arc_nvarc_combined import atomic
from .arc_nvarc_gpu_preflight_v2 import (RECIPE,initialize_groups,cpu_fingerprint,
    record,require_cpu_residency)
from .arc_nvarc_packing import pack_sequences
from .arc_nvarc_qwen3_packing import TORCH_VARLEN,execution_slices,register_torch_varlen
from .arc_nvarc_sft_step import source_optimizer,train_source_step
from .canonical import digest_value
from .errors import ValidationError

FORMAT='irisx/nvarc-original-qwen3-packed-step-v1'
PREFIX_SHA='82d5e1f60f7d8a2748d9aa4011e7cd5478106405f06089b6cea7b9085b9521e6'
BASE='sha256:6c93bb738c9203ef19cc02deeac67c6a659e3128807f5c5d02a74104a479d430'


def schedule(rows,ceiling=32768):
    ranks=[]
    for rank in range(4):
        logical=pack_sequences(rows[rank::4],capacity=256000,length_multiple=64)
        physical=[p for pack in logical for p in execution_slices(pack,ceiling)]
        ranks.append({'rank':rank,'logical_digests':[digest_value(p) for p in logical],
            'physical_digests':[digest_value(p) for p in physical],
            'physical_input_tokens':[p['input_tokens'] for p in physical],
            'input_tokens':sum(p['input_tokens'] for p in logical),
            'supervised_tokens':sum(p['supervised_tokens'] for p in logical)})
    slots=max(len(r['physical_digests']) for r in ranks)
    return {'ranks':ranks,'collective_slots_per_rank':slots,
        'real_outer_forwards':sum(len(r['physical_digests']) for r in ranks),
        'dummy_outer_forwards':slots*4-sum(len(r['physical_digests']) for r in ranks)}


def check_plan(plan,rows):
    integers=('world_size','maximum_optimizer_steps','maximum_paid_usd','maximum_generations','maximum_teacher_calls',
        'maximum_physical_input_tokens','packing_capacity','packing_length_multiple','maximum_notebook_wall_seconds',
        'maximum_worker_wall_seconds','scheduled_input_tokens','scheduled_supervised_tokens','maximum_outer_forwards','maximum_input_tokens')
    if any(type(plan.get(key)) is not int for key in integers):
        raise ValidationError('integer original one-step bounds required')
    if (plan.get('format')!=FORMAT or plan.get('owner_decision')!='Decision 0054' or
            not re.fullmatch(r'nvarc-original-qwen3-packed-step-\d{3}',plan.get('run_id','')) or
            plan.get('world_size')!=4 or plan.get('source_recipe')!=RECIPE or len(rows)!=256 or
            plan.get('data_digest')!=digest_value(rows) or plan.get('source_prefix_sha256')!=PREFIX_SHA or
            plan.get('model_material_digest')!=BASE or
            plan.get('maximum_optimizer_steps')!=1 or plan.get('maximum_paid_usd')!=0 or
            plan.get('maximum_generations')!=0 or plan.get('maximum_teacher_calls')!=0 or
            plan.get('retain_export') is not False or plan.get('maximum_physical_input_tokens')!=32768 or
            plan.get('packing_capacity')!=256000 or plan.get('packing_length_multiple')!=64 or
            plan.get('maximum_notebook_wall_seconds')!=4500 or plan.get('maximum_worker_wall_seconds')!=4200 or
            [r['shuffle_position'] for r in rows]!=list(range(256)) or
            plan.get('scheduled_input_tokens')!=sum(len(r['input_ids']) for r in rows) or
            plan.get('scheduled_supervised_tokens')!=sum(sum(v>=0 for v in r['labels'][1:]) for r in rows)):
        raise ValidationError('exact original source global-256 one-step resource plan required')
    expected=schedule(rows)
    if (plan.get('physical_schedule')!=expected or
            plan.get('maximum_outer_forwards')!=expected['collective_slots_per_rank']*4 or
            plan.get('maximum_input_tokens')!=plan['scheduled_input_tokens']+2*expected['dummy_outer_forwards']):
        raise ValidationError('original logical placement or whole-sample physical budget differs')
    return expected


def run(plan,rows,compact,output):
    import torch
    import torch.distributed as dist
    from torch.distributed.fsdp import FullyShardedDataParallel as FSDP,MixedPrecision,CPUOffload
    from torch.distributed.fsdp.wrap import ModuleWrapPolicy
    from torch.distributed.algorithms._checkpoint.checkpoint_wrapper import (
        apply_activation_checkpointing,checkpoint_wrapper,CheckpointImpl,CheckpointWrapper)
    from transformers import Qwen3ForCausalLM
    expected=check_plan(plan,rows)
    rank,local,world=(int(os.environ.get(k,'-1')) for k in ('RANK','LOCAL_RANK','WORLD_SIZE'))
    if world!=4 or rank not in range(4) or local!=rank:
        raise ValidationError('four rank-local distinct L4 workers required')
    device,hardware,group=initialize_groups(rank,local,world,True)
    phase='output-gate';started=time.monotonic();wrapped=optimizer=None
    try:
        if rank==0:
            if output.exists():raise ValidationError('new immutable training observation required')
            output.mkdir(parents=True)
        dist.barrier()
        phase='model-load';register_torch_varlen();torch.manual_seed(24)
        model=Qwen3ForCausalLM.from_pretrained(compact,local_files_only=True,
            dtype=torch.float32,attn_implementation=TORCH_VARLEN)
        if (model.config.model_type!='qwen3' or model.config.num_hidden_layers!=36 or
                model.config.vocab_size!=16 or not model.config.tie_word_embeddings or
                model.get_input_embeddings().weight.data_ptr()!=model.get_output_embeddings().weight.data_ptr()):
            raise ValidationError('exact original tied compact 4B architecture required')
        model.gradient_checkpointing_disable();layer_type=type(model.model.layers[0])
        phase='fsdp-wrap'
        wrapped=FSDP(model,auto_wrap_policy=ModuleWrapPolicy({layer_type}),device_id=device,
            process_group=group,cpu_offload=CPUOffload(offload_params=True),use_orig_params=True,
            backward_prefetch=None,forward_prefetch=False,limit_all_gathers=True,
            mixed_precision=MixedPrecision(param_dtype=torch.bfloat16,reduce_dtype=torch.float32,
                buffer_dtype=torch.bfloat16))
        apply_activation_checkpointing(wrapped,checkpoint_wrapper_fn=partial(checkpoint_wrapper,
            checkpoint_impl=CheckpointImpl.NO_REENTRANT),check_fn=lambda m:isinstance(m,layer_type))
        checkpointed=sum(isinstance(m,CheckpointWrapper) for m in wrapped.modules())
        if checkpointed!=36:raise ValidationError('all original decoder layers must be checkpointed')
        optimizer,scheduler=source_optimizer(wrapped,RECIPE)
        before=cpu_fingerprint(wrapped)
        require_cpu_residency(record(output,rank,'model-ready',model=wrapped,optimizer=optimizer,
            device=device,hardware=hardware,checkpointed_layers=checkpointed))
        phase='one-source-step'
        atomic(output/f'rank-{rank}-reservation.json',{'run_id':plan['run_id'],'plan_digest':digest_value(plan),
            'optimizer_steps_reserved':1,'outer_forwards_reserved':expected['collective_slots_per_rank'],
            'input_tokens_reserved':expected['ranks'][rank]['input_tokens'],
            'dummy_input_tokens_reserved':2*(expected['collective_slots_per_rank']-len(expected['ranks'][rank]['physical_digests'])),
            'generation_calls':0,'teacher_calls':0,'maximum_paid_usd':0})
        torch.cuda.synchronize(device);step_start=time.monotonic()
        observation=train_source_step(wrapped,optimizer,scheduler,rows[rank::4],device=device,
            recipe=RECIPE,capacity=256000,length_multiple=64,distributed=True,
            packed_backend='torch-varlen-flash',maximum_packed_input_tokens=32768)
        torch.cuda.synchronize(device);elapsed=time.monotonic()-step_start
        planned=expected['ranks'][rank]
        if (observation['packing_layout_digests']!=planned['logical_digests'] or
                observation['physical_packing_layout_digests']!=planned['physical_digests'] or
                observation['real_forward_calls']!=len(planned['physical_digests']) or
                observation['missing_owned_gradient_shards'] or
                observation['global_input_tokens']!=plan['scheduled_input_tokens'] or
                observation['global_supervised_tokens']!=plan['scheduled_supervised_tokens']):
            raise ValidationError('actual source packing/gradient/token coverage differs')
        after=cpu_fingerprint(wrapped)
        if before==after:raise ValidationError('global full-parameter fingerprint did not change')
        observation.update(hardware=hardware,checkpointed_layers=checkpointed,
            synchronized_step_wall_seconds=elapsed)
        atomic(output/f'rank-{rank}-step.json',observation)
        observations=[None]*4;dist.all_gather_object(observations,observation)
        result={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'outcome':'complete',
            'model_material_digest':plan['model_material_digest'],'optimizer_steps':1,
            'input_tokens':plan['scheduled_input_tokens'],'supervised_tokens':plan['scheduled_supervised_tokens'],
            'outer_forwards':sum(r['real_forward_calls']+r['dummy_forward_calls'] for r in observations),
            'weight_fingerprint_before':before,'weight_fingerprint_after':after,
            'rank_observations':observations,'step_wall_seconds':max(r['synchronized_step_wall_seconds'] for r in observations),
            'worker_wall_seconds':time.monotonic()-started,'generation_calls':0,'teacher_calls':0,
            'checkpoint_exported':False,'optimizer_checkpoint_exported':False,'full_sft_completed':False,
            'historical_nemo_unsloth_parity':False,'contains_evaluator_truth':False,
            'timing_repetitions':1,'timing_scope':'one cold first source optimizer step including CPU accumulation and Adam'}
        if rank==0:atomic(output/'worker-result.json',result)
        dist.barrier();return result
    except BaseException as error:
        if output.is_dir():
            atomic(output/f'rank-{rank}-failure.json',{'run_id':plan['run_id'],'rank':rank,'phase':phase,
                'error_type':type(error).__name__,'message':str(error)[:1200],'worker_wall_seconds':time.monotonic()-started})
        raise
    finally:
        if optimizer is not None:optimizer.zero_grad(set_to_none=True)
        if dist.is_initialized():dist.destroy_process_group()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('plan','samples','compact','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(json.loads(args.plan.read_bytes()),json.loads(args.samples.read_bytes()),args.compact,args.output)

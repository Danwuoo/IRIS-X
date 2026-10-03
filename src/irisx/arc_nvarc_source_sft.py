"""Reusable source-order Qwen3.5 SFT with CPU shard accumulation and resume.

The segmented packing execution preserves sequence isolation. Its throughput
does not establish fused NeMo/Megatron packing or original Qwen3 parity.
"""
from __future__ import annotations

import argparse
from functools import partial
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time

from .arc_nvarc_fsdp_sft import (_broadcast_error, _load_checkpoint, _save_checkpoint,
    _verify_compact_base, verify_checkpoint)
from .arc_nvarc_gpu_preflight_v2 import (BASE, CORPUS_SHA, RECIPE, initialize_groups,
    cpu_fingerprint, record, require_cpu_residency)
from .arc_nvarc_packing import pack_sequences
from .arc_nvarc_sft_step import source_optimizer, train_source_step
from .arc_nvarc_training import load_compact_model
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


class FrozenSequences:
    """Explicit bounded integration material; never wraps or claims full shuffle."""
    def __init__(self, path: Path, plan: dict):
        self.rows = json.loads(path.read_bytes())
        if not isinstance(self.rows, list) or digest_value(self.rows) != plan['data_digest']:
            raise ValidationError('frozen source integration rows differ')
        pack_sequences(self.rows, capacity=plan['packing_capacity'], length_multiple=64)
        required = plan['global_batch_size'] * plan['maximum_optimizer_steps']
        if len(self.rows) != required or sum(len(row['input_ids']) for row in self.rows) != plan['scheduled_input_tokens']:
            raise ValidationError('frozen integration schedule differs')
        if any(len(row['input_ids']) > plan['maximum_sequence_length'] for row in self.rows):
            raise ValidationError('frozen whole sequence exceeds planned length')
        self.identity_digest = digest_value({'kind':plan['data_kind'],'rows_digest':plan['data_digest']})

    def batch(self, cursor, size, *, rank=0, world=1):
        if cursor < 0 or cursor + size > len(self.rows):
            raise ValidationError('frozen source schedule cannot wrap')
        return self.rows[cursor+rank:cursor+size:world]

    def close(self):
        pass


def check_plan(plan: dict, world: int) -> None:
    if (plan.get('format') != 'irisx/nvarc-source-sft-v1' or
            not re.fullmatch(r'nvarc-overnight-[a-z0-9-]+',plan.get('run_id','')) or
            plan.get('source_recipe') != RECIPE or plan.get('world_size') != world or world not in {2,4} or
            plan.get('maximum_paid_usd') != 0 or plan.get('maximum_generations') != 0 or
            plan.get('maximum_teacher_calls') != 0 or plan.get('packing_execution') != 'isolated-segments' or
            plan.get('packing_capacity') != 256000 or plan.get('packing_length_multiple') != 64 or
            type(plan.get('global_batch_size')) is not int or not 1 <= plan['global_batch_size'] <= 256 or
            type(plan.get('maximum_optimizer_steps')) is not int or not 2 <= plan['maximum_optimizer_steps'] <= 12716 or
            type(plan.get('maximum_training_tokens')) is not int or plan['maximum_training_tokens'] < 1 or
            type(plan.get('maximum_sequence_length')) is not int or plan['maximum_sequence_length'] < 2 or
            not isinstance(plan.get('checkpoint_steps'),list) or not plan['checkpoint_steps'] or
            any(type(x) is not int for x in plan['checkpoint_steps']) or
            plan['checkpoint_steps'] != sorted(set(plan['checkpoint_steps'])) or
            1 not in plan['checkpoint_steps'] or plan['maximum_optimizer_steps'] not in plan['checkpoint_steps'] or
            any(type(x) is not int or not 1 <= x <= plan['maximum_optimizer_steps'] for x in plan['checkpoint_steps']) or
            plan.get('seed') != 24 or plan.get('data_kind') not in {'original-corpus','published-sample-integration','synthetic-fixture'}):
        raise ValidationError('source SFT plan/settings differ')
    if plan.get('backend') == 'cuda-l4':
        if (world != 4 or plan.get('owner_decision') != 'Decision 0053' or plan.get('approved') is not True or
                plan.get('base_material_digest') != BASE or plan.get('corpus_manifest_sha256') != CORPUS_SHA or
                plan.get('data_kind') == 'synthetic-fixture'):
            raise ValidationError('new free private Goal runtime authority required')
    elif not (plan.get('backend') == 'cpu' and world == 2 and plan.get('data_kind') == 'synthetic-fixture'):
        raise ValidationError('source SFT backend differs')
    if plan['data_kind'] == 'original-corpus' and plan['global_batch_size'] != 256:
        raise ValidationError('original corpus requires the source global batch of 256')


def open_data(path: Path, plan: dict):
    if plan['data_kind'] == 'original-corpus':
        from .arc_nvarc_source_stream import OriginalSequenceStream
        return OriginalSequenceStream(path,plan['corpus_manifest_sha256'])
    return FrozenSequences(path,plan)


def identity_for(plan: dict, data) -> str:
    return digest_value({'plan':plan,'source_stream_identity':data.identity_digest})


def _retain(output: Path, scratch: Path, reference: dict, identity: str, world: int):
    manifest = verify_checkpoint(scratch/reference['path'],identity,world)
    if digest_value(manifest) != reference['manifest_digest']:
        raise ValidationError('source checkpoint reference differs')
    (output/f"checkpoint-{reference['step']}-manifest.json").write_bytes(canonical_bytes(manifest,newline=True))


def run(plan_path: Path, compact: Path, data_path: Path, output: Path, scratch: Path,
        *, resume=False, stop_after_step=None, _policy=None):
    import torch
    import torch.distributed as dist
    from torch.distributed.fsdp import FullyShardedDataParallel as FSDP, CPUOffload, MixedPrecision
    from torch.distributed.fsdp.wrap import ModuleWrapPolicy
    from torch.distributed.algorithms._checkpoint.checkpoint_wrapper import (
        apply_activation_checkpointing, checkpoint_wrapper, CheckpointImpl, CheckpointWrapper)
    plan = json.loads(plan_path.read_bytes())
    rank, local, world = (int(os.environ.get(key,'-1')) for key in ('RANK','LOCAL_RANK','WORLD_SIZE'))
    (check_plan if _policy is None else _policy.check_plan)(plan,world)
    if rank not in range(world) or local not in range(world):
        raise ValidationError('source SFT requires torchrun ranks')
    if stop_after_step is not None and (type(stop_after_step) is not int or not 1 <= stop_after_step <= plan['maximum_optimizer_steps']):
        raise ValidationError('controlled stop must be a planned optimizer step')
    data = (open_data if _policy is None else _policy.open_data)(data_path,plan)
    identity = identity_for(plan,data)
    device, hardware, group = initialize_groups(rank,local,world,plan['backend']=='cuda-l4')
    phase, step, cursor, tokens, supervised, calls = 'material-gate', 0, 0, 0, 0, 0
    wrapped = optimizer = None
    started = time.monotonic()
    try:
        error = None
        if rank == 0:
            try:
                if _policy is None:
                    _verify_compact_base(compact,plan['base_material_digest'])
                else:
                    _policy.verify_model(compact,plan)
                if not resume and (output.exists() or scratch.exists()):
                    raise ValidationError('source SFT needs new output and scratch')
                if resume and not (scratch/'latest.json').is_file():
                    raise ValidationError('source SFT resume reference missing')
                if not resume:
                    output.mkdir(parents=True)
                    scratch.mkdir(parents=True)
            except Exception as caught:
                error = f'{type(caught).__name__}: {caught}'
        _broadcast_error(error,rank)
        dist.barrier()
        torch.manual_seed(plan['seed']+rank)
        phase = 'model-load'
        model = (load_compact_model(compact,dtype='float32') if _policy is None
                 else _policy.load_model(compact,plan))
        model.gradient_checkpointing_disable()
        layers = model.model.language_model.layers if _policy is None else model.model.layers
        layer_type = type(layers[0])
        expected_layers = len(layers)
        gpu = device.type == 'cuda'
        wrapped = FSDP(model,auto_wrap_policy=ModuleWrapPolicy({layer_type}),device_id=device,
            process_group=group,cpu_offload=CPUOffload(offload_params=gpu),use_orig_params=True,
            backward_prefetch=None,forward_prefetch=False,limit_all_gathers=True,
            mixed_precision=MixedPrecision(param_dtype=torch.bfloat16,reduce_dtype=torch.float32,
                buffer_dtype=torch.bfloat16) if gpu else None)
        apply_activation_checkpointing(wrapped,checkpoint_wrapper_fn=partial(checkpoint_wrapper,
            checkpoint_impl=CheckpointImpl.NO_REENTRANT),check_fn=lambda module:isinstance(module,layer_type))
        checkpointed = sum(isinstance(module,CheckpointWrapper) for module in wrapped.modules())
        if checkpointed != expected_layers:
            raise ValidationError('source SFT decoder checkpoint coverage differs')
        optimizer,scheduler = source_optimizer(wrapped,plan['source_recipe'])
        before = cpu_fingerprint(wrapped)
        require_cpu_residency(record(output,rank,'model-ready',model=wrapped,optimizer=optimizer,
            device=device,hardware=hardware,checkpointed_layers=checkpointed))
        restored = None
        if resume:
            phase = 'checkpoint-restore'
            state,reference = _load_checkpoint(wrapped,optimizer,scheduler,scratch,identity,rank,world,device)
            step,cursor,tokens,supervised,calls = (state[key] for key in
                ('step','cursor','tokens_seen','supervised_tokens_seen','forwards'))
            if cursor != step*plan['global_batch_size'] or step >= plan['maximum_optimizer_steps']:
                raise ValidationError('source SFT checkpoint cursor/step differs')
            restored = cpu_fingerprint(wrapped)
            if restored != state['weight_fingerprint_after']:
                raise ValidationError('source SFT checkpoint weights differ')
            error = None
            if rank == 0:
                try:
                    _retain(output,scratch,reference,identity,world)
                    if _policy is None:
                        shutil.rmtree(scratch/reference['path'])
                except Exception as caught:
                    error = f'{type(caught).__name__}: {caught}'
            _broadcast_error(error,rank)
            dist.barrier()
        histories = []
        after = restored if restored is not None else before
        while step < plan['maximum_optimizer_steps']:
            rows = data.batch(cursor,plan['global_batch_size'],rank=rank,world=world)
            scheduled = torch.tensor([sum(len(row['input_ids']) for row in rows),
                max([len(row['input_ids']) for row in rows],default=0)],dtype=torch.int64)
            total = scheduled[:1].clone();dist.all_reduce(total)
            longest = scheduled[1:].clone();dist.all_reduce(longest,op=dist.ReduceOp.MAX)
            if tokens+total.item() > plan['maximum_training_tokens'] or longest.item() > plan['maximum_sequence_length']:
                raise ValidationError('source step must fit whole, untruncated planned material')
            phase = f'step-{step+1}-accumulation'
            observation = (train_source_step(wrapped,optimizer,scheduler,rows,device=device,recipe=plan['source_recipe'])
                           if _policy is None else _policy.train_step(wrapped,optimizer,scheduler,rows,device,plan))
            changed = cpu_fingerprint(wrapped)
            if changed == after:
                raise ValidationError('source SFT optimizer did not change weights')
            after = changed
            observation.update(step=step+1,hardware=hardware,checkpointed_layers=checkpointed,
                source_lineage=[{key:value for key,value in row.items() if key not in {'input_ids','labels'}} for row in rows])
            observed = [None]*world;dist.all_gather_object(observed,observation)
            histories.append(observed)
            step += 1
            cursor += plan['global_batch_size']
            tokens += observation['global_input_tokens']
            supervised += observation['global_supervised_tokens']
            calls += sum(value['real_forward_calls'] for value in observed)
            record(output,rank,'optimizer-complete',model=wrapped,optimizer=optimizer,device=device,
                step=step,cursor=cursor,observation=observation)
            if step in plan['checkpoint_steps'] or step == stop_after_step:
                phase = f'step-{step}-checkpoint'
                state = {'identity_digest':identity,'world_size':world,'step':step,'cursor':cursor,
                    'tokens_seen':tokens,'supervised_tokens_seen':supervised,'forwards':calls,
                    'weight_fingerprint_after':after,'source_stream_identity':data.identity_digest,
                    'contains_evaluator_truth':False}
                optimizer.zero_grad(set_to_none=True)
                gc.collect()
                if gpu:torch.cuda.empty_cache()
                old_reference = json.loads((scratch/'latest.json').read_bytes()) if (scratch/'latest.json').is_file() else None
                reference = (_save_checkpoint(wrapped,optimizer,scheduler,scratch,state,rank,world,device)
                    if _policy is None else _policy.save_checkpoint(wrapped,optimizer,scheduler,scratch,state,rank,world,device))
                error = None
                if rank == 0:
                    try:
                        _retain(output,scratch,reference,identity,world)
                        if _policy is None and old_reference is not None and old_reference['path'] != reference['path']:
                            old = scratch/old_reference['path']
                            if old.parent.resolve() != scratch.resolve() or not old.name.startswith('checkpoint-step-'):
                                raise ValidationError('source checkpoint eviction path differs')
                            if old.exists():shutil.rmtree(old)
                    except Exception as caught:
                        error = f'{type(caught).__name__}: {caught}'
                _broadcast_error(error,rank)
                dist.barrier()
            if stop_after_step == step:break
        result = {'format':'irisx/nvarc-source-sft-result-v1','run_id':plan['run_id'],
            'identity_digest':identity,'plan_digest':digest_value(plan),'source_stream_identity':data.identity_digest,
            'step':step,'cursor':cursor,'input_tokens':tokens,'supervised_tokens':supervised,'forwards':calls,
            'checkpoint':reference,'weight_fingerprint_before':before,'weight_fingerprint_after':after,
            'restored_fingerprint':restored,'observations':histories,'wall_seconds':time.monotonic()-started,
            'packing_execution':'isolated-segments','fused_packing_verified':False,
            'full_sft_completed':plan['data_kind']=='original-corpus' and step==12716,
            'original_qwen3_nemo_parity':False,'generation_calls':0,'teacher_calls':0,'contains_evaluator_truth':False}
        if _policy is not None:
            _policy.finish_result(result,plan)
        if rank == 0:
            (output/('final-result.json' if step==plan['maximum_optimizer_steps'] else 'pause-result.json')).write_bytes(canonical_bytes(result,newline=True))
        dist.barrier()
        return result
    except BaseException as caught:
        if output.is_dir():
            failure = {'run_id':plan['run_id'],'identity_digest':identity,'rank':rank,'phase':phase,
                'step':step,'cursor':cursor,'input_tokens':tokens,'error_type':type(caught).__name__,
                'error_message':str(caught)[:1200],'contains_evaluator_truth':False}
            (output/f'rank-{rank}-failure.json').write_bytes(canonical_bytes(failure,newline=True))
        raise
    finally:
        data.close()
        if dist.is_initialized():
            dist.destroy_process_group(group)
            dist.destroy_process_group()


def tensor_inventory(model):
    """Exact per-tensor export/reload proof, including buffers and tied aliases."""
    import torch
    result = {}
    for name,tensor in model.state_dict().items():
        value = tensor.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy()
        result[name] = {'shape':list(tensor.shape),'dtype':str(tensor.dtype),
            'sha256':hashlib.sha256(memoryview(value).cast('B')).hexdigest()}
    return result


def export(plan_path: Path, compact: Path, data_path: Path, output: Path, scratch: Path, target: Path, *, _policy=None):
    import torch
    import torch.distributed.checkpoint as dcp
    from .arc_nvarc_representation import export_trained_model, verify_model_material
    plan = json.loads(plan_path.read_bytes())
    (check_plan if _policy is None else _policy.check_plan)(plan,plan['world_size'])
    data = (open_data if _policy is None else _policy.open_data)(data_path,plan)
    try:identity = identity_for(plan,data)
    finally:data.close()
    if _policy is None:
        _verify_compact_base(compact,plan['base_material_digest'])
    else:
        _policy.verify_model(compact,plan)
    result = json.loads((output/'final-result.json').read_bytes())
    reference = json.loads((scratch/'latest.json').read_bytes())
    if (result['identity_digest'] != identity or result['checkpoint'] != reference or
            result['step'] != plan['maximum_optimizer_steps']):
        raise ValidationError('complete source SFT checkpoint required for export')
    checkpoint = scratch/reference['path']
    manifest = verify_checkpoint(checkpoint,identity,plan['world_size'])
    if digest_value(manifest) != reference['manifest_digest'] or target.exists():
        raise ValidationError('checkpoint digest or new export target differs')
    model = (load_compact_model(compact,dtype='float32') if _policy is None else _policy.load_model(compact,plan))
    tensors = model.state_dict()
    dcp.load({'model':tensors},checkpoint_id=checkpoint/'dcp',no_dist=True)
    model.load_state_dict(tensors);del tensors
    fingerprint = [sum(float(value.detach().double().sum()) for value in model.parameters()),
        sum(float(value.detach().double().square().sum()) for value in model.parameters())]
    expected = manifest['state']['weight_fingerprint_after']
    if any(abs(left-right)>1e-9*max(1.,abs(right)) for left,right in zip(fingerprint,expected)):
        raise ValidationError('consolidated FP32 checkpoint fingerprint differs')
    if plan['backend']=='cuda-l4':model.to(dtype=torch.bfloat16)
    inventory = tensor_inventory(model)
    if _policy is None:
        material = export_trained_model(model,compact,target,training_identity_digest=identity)
        verify_model_material(target,material)
    else:
        material = _policy.export_model(model,compact,target,identity,plan)
    del model;gc.collect()
    reloaded = (load_compact_model(target,dtype='bfloat16' if plan['backend']=='cuda-l4' else 'float32')
                if _policy is None else _policy.load_model(target,plan,exported=True))
    if inventory != tensor_inventory(reloaded):
        raise ValidationError('source export tensor bytes changed on reload')
    del reloaded;gc.collect()
    chain = {'format':'irisx/nvarc-source-sft-export-v1','identity_digest':identity,
        'plan_digest':digest_value(plan),'checkpoint_manifest_digest':reference['manifest_digest'],
        'checkpoint_step':reference['step'],'base_material_digest':plan['base_material_digest'],
        'export_material_digest':material,'fp32_saved_fingerprint':expected,'fp32_consolidated_fingerprint':fingerprint,
        'export_tensor_inventory':inventory,'reload_tensor_bytes_identical':True,
        'full_sft_completed':result['full_sft_completed'],'original_qwen3_nemo_parity':False,'contains_evaluator_truth':False}
    if _policy is not None:
        chain.update(format='irisx/nvarc-original-qwen3-sft-export-v1',model_family='qwen3',
                     optimizer_checkpoint_retained=True)
    (output/'export-chain.json').write_bytes(canonical_bytes(chain,newline=True))
    return chain


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    for name in ('plan','compact','data','output','scratch'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--stop-after-step',type=int)
    parser.add_argument('--export',type=Path)
    args = parser.parse_args()
    if args.export:
        if args.resume or args.stop_after_step:parser.error('export runs after workers exit')
        export(args.plan,args.compact,args.data,args.output,args.scratch,args.export)
    else:
        run(args.plan,args.compact,args.data,args.output,args.scratch,resume=args.resume,stop_after_step=args.stop_after_step)

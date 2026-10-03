"""Original Qwen3 source SFT policy over the shared FSDP checkpoint engine.

This path retains original WordLevel chat, whole rows and segmented GEMMs.
Historical NeMo versions/numerics and original-scale training remain separate.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import time

from .arc_nvarc_combined import atomic, sha
from .arc_nvarc_gpu_preflight_v2 import RECIPE
from .arc_nvarc_packing import pack_sequences
from .arc_nvarc_source_recipe import SourceTextTokenizer
from .canonical import digest_value
from .errors import ValidationError

FORMAT = 'irisx/nvarc-original-qwen3-source-sft-v1'
BASE = 'sha256:6c93bb738c9203ef19cc02deeac67c6a659e3128807f5c5d02a74104a479d430'


def require(value, message):
    if not value:
        raise ValidationError(message)


def encode_source_pair(pair):
    require([m['role'] for m in pair] == ['user', 'assistant'], 'original alternating source roles required')
    tokenizer = SourceTextTokenizer()
    user = tokenizer.encode('<|im_start|>user\n' + pair[0]['content'] + '<|im_end|>')
    assistant = tokenizer.encode('<|im_start|>assistant\n' + pair[1]['content'] + '<|im_end|>')
    return user + assistant, [-100] * (len(user) + 3) + assistant[3:]


def file_inventory(root):
    require(root.is_dir() and not root.is_symlink() and
            all(p.is_file() and not p.is_symlink() for p in root.iterdir()), 'closed regular original model directory required')
    return {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(root.iterdir())}


def check_plan(plan, world):
    require(plan.get('format') == FORMAT and plan.get('model_family') == 'qwen3' and
            re.fullmatch(r'nvarc-original-qwen3-sft-\d{3}', plan.get('run_id', '')) and
            plan.get('source_recipe') == RECIPE and plan.get('world_size') == world and world in {2, 4},
            'distinct original Qwen3 source SFT plan required')
    limits = ('global_batch_size', 'maximum_optimizer_steps', 'maximum_training_tokens',
              'maximum_sequence_length', 'maximum_physical_input_tokens', 'maximum_worker_wall_seconds',
              'maximum_outer_forwards', 'maximum_input_tokens', 'maximum_paid_usd', 'maximum_generations', 'maximum_teacher_calls')
    require(all(type(plan.get(k)) is int for k in limits) and
            1 <= plan['global_batch_size'] <= 256 and 2 <= plan['maximum_optimizer_steps'] <= 12716 and
            0 < plan['maximum_training_tokens'] <= plan['maximum_input_tokens'] and plan['maximum_outer_forwards'] > 0 and
            2 <= plan['maximum_sequence_length'] <= plan['maximum_physical_input_tokens'] <= 32768 and
            1 <= plan['maximum_worker_wall_seconds'] <= 43200 and
            all(plan[k] == 0 for k in ('maximum_paid_usd', 'maximum_generations', 'maximum_teacher_calls')),
            'finite original SFT call/token/step/time bounds required')
    require(plan.get('packing_capacity') == 256000 and plan.get('packing_length_multiple') == 64 and
            plan.get('packing_execution') == 'segmented-gemm-whole-sample-packing' and
            plan.get('seed') == 24 and plan.get('checkpoint_storage') == 'durable-retained' and
            plan.get('checkpoint_keep_last') == 2 and
            isinstance(plan.get('checkpoint_steps'),list) and plan['checkpoint_steps'] and
            all(type(x) is int and 1 <= x <= plan['maximum_optimizer_steps'] for x in plan['checkpoint_steps']) and
            plan['checkpoint_steps'] == sorted(set(plan['checkpoint_steps'])) and
            plan['checkpoint_steps'][0] == 1 and plan['checkpoint_steps'][-1] == plan['maximum_optimizer_steps'] and
            digest_value(plan.get('model_inventory')) == plan.get('base_material_digest'),
            'source packing and complete retained checkpoint binding required')
    require(plan.get('data_kind') in {'synthetic-fixture', 'original-corpus', 'original-source-prefix'},
            'explicit original SFT material kind required')
    if plan.get('backend') == 'cuda-l4':
        require(world == 4 and plan.get('owner_decision') == 'Decision 0054' and plan.get('approved') is True and
                plan['global_batch_size'] == 256 and plan['base_material_digest'] == BASE and
                plan['data_kind'] != 'synthetic-fixture' and
                plan.get('cuda_differential_prerequisite', {}).get('segmented_linear_observed') is True,
                'verified original GPU packing prerequisite and private free authority required')
    else:
        require(plan.get('backend') == 'cpu' and world == 2 and plan['data_kind'] == 'synthetic-fixture',
                'tiny original CPU differential requires explicit fixture material')


def open_data(path, plan):
    if plan['data_kind'] == 'original-corpus':
        from .arc_nvarc_source_stream import OriginalSequenceStream
        return OriginalSequenceStream(path, plan['corpus_manifest_sha256'], representation='original-qwen3')
    from .arc_nvarc_source_sft import FrozenSequences
    return FrozenSequences(path, plan)


def verify_model(root, plan):
    actual = file_inventory(root)
    core = {k:v for k,v in actual.items() if k in plan['model_inventory']}
    extras = {k:v for k,v in actual.items() if k not in core}
    allowed = plan.get('model_sidecars',{})
    require(set(allowed) <= {'material-manifest.json','dataset-metadata.json'} and
            all(allowed.get(k) == v for k,v in extras.items()) and
            core == plan['model_inventory'] and digest_value(core) == plan['base_material_digest'],
            'exact closed original model bytes required')


def load_model(root, plan, *, exported=False):
    import torch
    from transformers import Qwen3ForCausalLM
    from .arc_nvarc_qwen3_packing import TORCH_VARLEN, register_torch_varlen
    gpu = plan['backend'] == 'cuda-l4'
    if gpu:
        register_torch_varlen()
    model = Qwen3ForCausalLM.from_pretrained(root, local_files_only=True,
        dtype=torch.bfloat16 if exported and gpu else torch.float32,
        attn_implementation='sdpa' if exported or not gpu else TORCH_VARLEN)
    require(model.config.model_type == 'qwen3' and model.config.vocab_size == 16 and
            model.config.tie_word_embeddings and model.get_input_embeddings().weight.data_ptr() ==
            model.get_output_embeddings().weight.data_ptr(), 'original tied 16-symbol Qwen3 family required')
    if gpu:
        require(model.config.hidden_size == 2560 and len(model.model.layers) == 36,
                'original 4B decoder topology required')
    return model


def export_model(model, compact, target, identity, plan):
    require(not target.exists(), 'new original inference export required')
    model.save_pretrained(target, safe_serialization=True, max_shard_size='2GB')
    # These are original WordLevel files, never Qwen3.5 grid material metadata.
    for name in ('tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json'):
        if (compact / name).is_file():
            shutil.copyfile(compact / name, target / name)
    inventory = file_inventory(target)
    atomic(target.parent / (target.name + '-material.json'), {
        'format': 'irisx/nvarc-original-qwen3-trained-material-v1', 'model_family': 'qwen3',
        'base_material_digest': plan['base_material_digest'], 'training_identity_digest': identity,
        'inventory': inventory, 'material_digest': digest_value(inventory),
        'historical_nemo_parity': False, 'contains_evaluator_truth': False})
    return digest_value(inventory)


class Policy:
    check_plan = staticmethod(check_plan)
    open_data = staticmethod(open_data)
    verify_model = staticmethod(verify_model)
    load_model = staticmethod(load_model)
    export_model = staticmethod(export_model)

    def __init__(self, output, *, fault_before_step=None):
        self.output, self.fault_before_step = output, fault_before_step
        self.started = time.monotonic()
        self.step = 0

    def save_checkpoint(self, model, optimizer, scheduler, root, state, rank, world, device):
        from .arc_nvarc_fsdp_sft import _save_checkpoint, verify_checkpoint, _broadcast_error
        import torch.distributed as dist
        name = [None]
        if rank == 0:
            prefix = f"checkpoint-step-{state['step']:04d}-attempt-"
            attempt = 1
            while (root / (prefix + f'{attempt:04d}')).exists():
                attempt += 1
            name[0] = prefix + f'{attempt:04d}'
        dist.broadcast_object_list(name, src=0)
        def durable(directory):
            for path in directory.rglob('*'):
                if path.is_file():
                    with path.open('rb+') as stream:
                        os.fsync(stream.fileno())
        reference = _save_checkpoint(model,optimizer,scheduler,root,state,rank,world,device,
                                     directory_name=name[0],before_publish=durable)
        cleanup_error = None
        if rank == 0:
            try:
                # Directory fsync makes the committed latest rename durable.
                if os.name == 'posix':
                    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                # Evict only verified transactions after the pointer commits.
                committed = []
                for path in root.glob('checkpoint-step-*'):
                    if (path/'manifest.json').is_file():
                        manifest = verify_checkpoint(path,state['identity_digest'],world)
                        committed.append((manifest['state']['step'],path))
                for _, path in sorted(committed,key=lambda row:(row[0],row[1].name))[:-2]:
                    require(path.resolve().parent == root.resolve() and not path.is_symlink() and
                            path.name != reference['path'], 'bounded original checkpoint eviction path required')
                    shutil.rmtree(path)
            except Exception as caught:
                cleanup_error = f'{type(caught).__name__}: {caught}'
        _broadcast_error(cleanup_error,rank)
        dist.barrier()
        return reference

    def train_step(self, model, optimizer, scheduler, rows, device, plan):
        import torch
        import torch.distributed as dist
        from .arc_nvarc_qwen3_packing import execution_slices
        from .arc_nvarc_segmented_linear import segmented_linear
        from .arc_nvarc_sft_step import train_source_step
        self.step += 1
        if self.fault_before_step == self.step:
            require(device.type == 'cpu', 'failure injection is local CPU only')
            raise ValidationError('injected local failure before source step')
        require(time.monotonic() - self.started < plan['maximum_worker_wall_seconds'], 'original worker time bound reached')
        rank = dist.get_rank()
        packs = pack_sequences(rows, capacity=256000, length_multiple=64)
        pieces = [p for pack in packs for p in execution_slices(pack, plan['maximum_physical_input_tokens'])]
        slots = torch.tensor([len(pieces)], dtype=torch.int64)
        dist.all_reduce(slots, op=dist.ReduceOp.MAX)
        # All old reservations survive process restart; unfinished work consumes
        # its allowance, so replay cannot silently expand the finite workload.
        prior = list(self.output.glob(f'rank-{rank}-call-reservation-*.json'))
        used_calls = sum(json.loads(p.read_bytes())['outer_forwards'] for p in prior)
        used_tokens = sum(json.loads(p.read_bytes())['input_tokens'] for p in prior)
        local_tokens = sum(len(r['input_ids']) for r in rows)
        actual_tokens = local_tokens + 2 * (int(slots.item()) - len(pieces))
        totals = torch.tensor([used_calls + slots.item(), used_tokens + actual_tokens], dtype=torch.int64)
        dist.all_reduce(totals)
        require(totals[0].item() <= plan['maximum_outer_forwards'] and totals[1].item() <= plan['maximum_input_tokens'],
                'original cumulative call/token reservations exhausted')
        reservation = self.output / f'rank-{rank}-call-reservation-{len(prior):05d}.json'
        atomic(reservation, {'outer_forwards':int(slots.item()), 'input_tokens':actual_tokens, 'source_input_tokens':local_tokens,
            'plan_digest':digest_value(plan), 'completed':False})
        dummy = pack_sequences([{'input_ids':[14,15],'labels':[-100,15]}],capacity=256000,length_multiple=64)[0]
        expected = []
        for pack in pieces + [dummy]*(int(slots.item())-len(pieces)):
            ids,positions,offsets = [],[],[0]
            for segment in pack['segments']:
                values = pack['input_ids'][segment['start']:segment['valid_end']]
                ids.extend(values); positions.extend(range(len(values))); offsets.append(len(ids))
            expected.append({'input_ids_digest':digest_value([ids]),'position_ids_digest':digest_value([positions]),
                             'cu_seqlens':offsets,'input_tokens':len(ids)})
        events = []
        ledger = reservation.with_name(reservation.stem.replace('call-reservation','forward-ledger')+'.json')
        def before(module,args,kwargs):
            require(len(events)<len(expected) and (not events or events[-1]['completed']) and
                    time.monotonic()-self.started < plan['maximum_worker_wall_seconds'], 'unreserved or expired original forward entry')
            wanted = expected[len(events)]
            require(digest_value(kwargs['input_ids'].tolist()) == wanted['input_ids_digest'] and
                    digest_value(kwargs['position_ids'].tolist()) == wanted['position_ids_digest'] and
                    kwargs.get('use_cache') is False and kwargs.get('past_key_values') is None,
                    'exact original packed input/position/cache required before model entry')
            if device.type == 'cuda':
                require(kwargs['cu_seq_lens_q'].tolist() == kwargs['cu_seq_lens_k'].tolist() == wanted['cu_seqlens'],
                        'exact original causal sequence boundaries required')
            events.append({**wanted,'completed':False}); atomic(ledger,events)
        def after(module,args,result):
            require(events and not events[-1]['completed'], 'reserved original forward completion required')
            events[-1]['completed'] = True; atomic(ledger,events)
        hooks = [model.register_forward_pre_hook(before,with_kwargs=True),model.register_forward_hook(after)]
        policies = []
        @contextmanager
        def linear_scope(pack):
            offsets = [0]
            for segment in pack['segments']:
                offsets.append(offsets[-1] + segment['valid_end'] - segment['start'])
            with segmented_linear(model, offsets, maximum_segments=256, maximum_invocations_per_module=2) as value:
                policies.append(value)
                yield value
        try:
            result = train_source_step(model, optimizer, scheduler, rows, device=device, recipe=RECIPE,
                capacity=256000, length_multiple=64, distributed=True,
                packed_backend='torch-varlen-flash' if device.type == 'cuda' else 'dense-sdpa-reference',
                maximum_packed_input_tokens=plan['maximum_physical_input_tokens'], packed_linear_context=linear_scope)
        finally:
            for hook in hooks:
                hook.remove()
        require(len(events) == len(expected) and all(e['completed'] for e in events) and
                not result['missing_owned_gradient_shards'], 'every original full-gradient forward/shard must complete')
        for parameter,state in optimizer.state.items():
            require(all(key in state and state[key].shape == parameter.shape and state[key].dtype == torch.float32 and
                        state[key].device.type == 'cpu' and bool(torch.isfinite(state[key]).all()) for key in ('exp_avg','exp_avg_sq')),
                    'every complete finite original Adam moment shard required')
        result['segmented_linear_policies'] = policies
        value = json.loads(reservation.read_bytes())
        value.update(completed=True, real_forwards=result['real_forward_calls'], dummy_forwards=result['dummy_forward_calls'])
        require(result['real_forward_calls'] + result['dummy_forward_calls'] == value['outer_forwards'], 'actual original calls differ')
        atomic(reservation, value)
        return result

    def finish_result(self, result, plan):
        result.update(format='irisx/nvarc-original-qwen3-source-sft-result-v1', model_family='qwen3',
            packing_execution=plan['packing_execution'], full_sft_completed=False,
            source_schedule_completed=plan['data_kind'] == 'original-corpus' and result['step'] == 12716,
            optimizer_checkpoints_retained=True, historical_nemo_version=None, historical_megatron_version=None)


def run(plan, compact, data, output, checkpoints, *, resume=False, stop_after_step=None, fault_before_step=None):
    from .arc_nvarc_source_sft import run as engine
    return engine(plan, compact, data, output, checkpoints, resume=resume, stop_after_step=stop_after_step,
                  _policy=Policy(output, fault_before_step=fault_before_step))


def export(plan, compact, data, output, checkpoints, target):
    from .arc_nvarc_source_sft import export as engine
    return engine(plan, compact, data, output, checkpoints, target, _policy=Policy(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('plan', 'compact', 'data', 'output', 'checkpoints'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--stop-after-step', type=int)
    parser.add_argument('--export', type=Path)
    parser.add_argument('--fault-before-step', type=int)
    args = parser.parse_args()
    if args.export:
        require(not args.resume and args.stop_after_step is None and args.fault_before_step is None,
                'original export runs only after training workers exit')
        export(args.plan, args.compact, args.data, args.output, args.checkpoints, args.export)
    else:
        run(args.plan, args.compact, args.data, args.output, args.checkpoints, resume=args.resume,
            stop_after_step=args.stop_after_step, fault_before_step=args.fault_before_step)

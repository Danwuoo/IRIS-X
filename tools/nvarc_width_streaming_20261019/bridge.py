"""Bounded, CPU-only streaming reconstruction of the existing width-v1 tensors.

This prototype cannot construct official 2B: the source-parameter cap is fixed
at 100 million. It establishes allocation and exact-reconstruction mechanics
without changing WidthEngine admission or the existing release capsule.

The native Qwen3 skeleton is built on meta. Before real PEFT initialization,
its native Parameters are replaced by independent two-byte BF16 zero-stride
placeholders. Those placeholders supply only shape/device/dtype; a forward hook
rejects execution. PEFT therefore executes its original, version-specific CPU
initialization in the original module traversal, including discarded Linear
initialization draws and the BF16 rounding step. No hand-coded RNG simulator
or changed-shape initialization is used. Source-derived native tensors are then
allocated directly at their final FP32 shapes and assigned one at a time.

The placeholder model never leaves this function. The final model must have no
meta parameters, no overlapping/zero-stride storage, and exact FP32 geometry.
A failed build is discarded, never admitted. This is not WidthEngine and does
not claim full-model, full-context, GPU, optimizer, or capability admission.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Mapping

import torch
from torch import nn

from tools.nvarc_capacity_20261017.factory import _geometry
from tools.nvarc_posttrain_20261017.engine import PROJECTIONS
from tools.nvarc_posttrain_20261017.precision import install_policy, install_checkpoint_policy
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
from tools.nvarc_width_20261018.expansion import DELTA_FRACTION, replica_indices

MAX_PROTOTYPE_SOURCE_PARAMETERS = 100_000_000
MAX_PROTOTYPE_FINAL_PARAMETER_BYTES = 512 * 1024**2
MAX_PROTOTYPE_KNOWN_TENSOR_PEAK_BYTES = 768 * 1024**2
DEFAULT_CHUNK_ROWS = 128


def _need(value, message):
    if not value:
        raise ValueError(message)


def tensor_sha256(value, *, chunk_elements=262_144):
    """Same raw byte digest as expansion._sha, with bounded host byte copies."""
    _need(value.device.type == 'cpu' and value.dtype == torch.float32,
          'CPU FP32 tensor required for bounded digest')
    result = hashlib.sha256()
    # Row-wise processing avoids a full contiguous copy for column slices.
    rows = value.reshape(1, -1) if value.ndim <= 1 else value
    for row in rows:
        flat = row.detach().reshape(-1)
        for part in flat.split(chunk_elements):
            result.update(part.contiguous().view(torch.uint8).numpy().tobytes())
    return result.hexdigest()


class MappingSource:
    """Small-fixture reader. Unlike SafetensorSource, it retains its input map."""
    def __init__(self, values: Mapping[str, torch.Tensor]):
        self.values = values
        self.manifest = {name: (tuple(value.shape), value.dtype) for name, value in values.items()}

    @contextmanager
    def tensor(self, name):
        yield self.values[name]


class SafetensorSource:
    """One mmap lifetime per tensor, not a whole-file retained tensor dictionary.

    `names` permits a bounded subset or renaming of an already verified local
    source, e.g. an actual official layer. This reader does not establish model
    provenance. The caller must verify official files using verify_model first.
    """
    def __init__(self, path, *, names=None):
        from safetensors import safe_open
        self.path = Path(path)
        _need(self.path.is_file() and not self.path.is_symlink(), 'regular local safetensors file required')
        with safe_open(str(self.path), framework='pt', device='cpu') as handle:
            all_keys = set(handle.keys())
            self.names = dict(names) if names is not None else {name: name for name in all_keys}
            _need(all(name in all_keys for name in self.names.values()), 'source tensor is missing')
            self.manifest = {}
            for name, source_name in self.names.items():
                view = handle.get_slice(source_name)
                _need(view.get_dtype() == 'BF16', 'only BF16 source tensors are supported')
                self.manifest[name] = (tuple(view.get_shape()), torch.bfloat16)

    @contextmanager
    def tensor(self, name):
        from safetensors import safe_open
        with safe_open(str(self.path), framework='pt', device='cpu') as handle:
            value = handle.get_tensor(self.names[name])
            try:
                yield value
            finally:
                # Caller must not retain a view. Destinations always own storage.
                del value


def memory_plan(geometry, target_width, *, rank=64, chunk_rows=DEFAULT_CHUNK_ROWS):
    """Known live tensor sizes, NOT an RSS bound or full-model permission.

    Sources are BF16, destinations FP32. There is no complete dense FP32 model
    or complete BF16 model alongside the destination. The scratch allowance is
    intentionally conservative for up-row gathers/signs/arithmetic/hash bytes.
    Python/PyTorch/allocator/kernel/activation overhead is explicitly excluded.
    """
    keys = ('hidden_size', 'intermediate_size', 'num_hidden_layers',
            'num_attention_heads', 'num_key_value_heads', 'head_dim')
    _need(all(type(geometry.get(key)) is int and geometry[key] > 0 for key in keys)
          and geometry['num_hidden_layers'] <= 64
          and geometry['num_attention_heads'] % geometry['num_key_value_heads'] == 0,
          'positive integer Qwen3 geometry and divisible GQA required')
    h, old, layers = (geometry[k] for k in ('hidden_size', 'intermediate_size', 'num_hidden_layers'))
    _need(type(target_width) is int and old < target_width <= 2 * old, 'bounded larger FFN width required')
    _need(type(chunk_rows) is int and 1 <= chunk_rows <= 1024, 'chunk_rows must be in 1..1024')
    _need(type(rank) is int and 1 <= rank <= 64, 'bounded positive LoRA rank required')
    native = sum(math.prod(shape) for shape in _geometry(geometry).values())
    q, kv = geometry['num_attention_heads'] * geometry['head_dim'], geometry['num_key_value_heads'] * geometry['head_dim']
    lora = layers * rank * (2 * (h + q) + 2 * (h + kv) + 3 * (h + target_width)) + 32 * h
    resident = (native + layers * 3 * h * (target_width - old) + lora) * 4
    source_window = max(math.prod(shape) for shape in _geometry(geometry).values()) * 2
    signs = (target_width - old) * h
    extra = target_width - old
    # Separate operation geometries matter: with very wide source FFNs, the
    # down-column gather and source hashing can exceed up-row scratch. Include
    # the previous loop iteration's still-live Python locals in each allowance.
    up_scratch = 8 * min(chunk_rows, extra) * h * 4
    down_scratch = 3 * min(chunk_rows, h) * extra * 4
    hash_scratch = 3 * max(min(chunk_rows, shape[0]) * math.prod(shape[1:])
                          for shape in _geometry(geometry).values()) * 4
    adapter_scratch = 4 * rank * extra * 4
    arithmetic = max(up_scratch, down_scratch, hash_scratch, adapter_scratch)
    old_adapter = max(rank * old, old * rank) * 4
    indices = old * 8
    hash_copy = 2 * 262_144 * 4
    transient = source_window + signs + arithmetic + old_adapter + indices + hash_copy
    return {'final_parameter_bytes': resident, 'largest_BF16_source_window_bytes': source_window,
            'sign_tensor_bytes': signs, 'arithmetic_scratch_allowance_bytes': arithmetic,
            'per_operation_scratch_bytes': {'up': up_scratch, 'down': down_scratch,
                'source_hash': hash_scratch, 'adapter': adapter_scratch},
            'replaced_old_adapter_allowance_bytes': old_adapter, 'index_allowance_bytes': indices,
            'hash_copy_allowance_bytes': hash_copy, 'known_tensor_peak_allowance_bytes': resident + transient,
            'known_tensor_transient_allowance_bytes': transient,
            'whole_dense_source_copy_bytes': 0, 'chunk_rows': chunk_rows,
            'runtime_allocator_and_activation_overhead_included': False,
            'measured_peak': False, 'full_model_execution_authorized': False}


def _promoted_source_hash(source, chunk_rows):
    digest = hashlib.sha256()
    rows = source.reshape(1, -1) if source.ndim == 1 else source
    for start in range(0, rows.shape[0], chunk_rows):
        part = rows[start:start + chunk_rows].float()
        _need(bool(torch.isfinite(part).all()), 'finite BF16 source required')
        for flat in part.reshape(-1).split(262_144):
            digest.update(flat.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _native_destination(source, *, projection=None, target_width=None,
                        layer_index=0, chunk_rows=DEFAULT_CHUNK_ROWS):
    """Allocate exactly one final native tensor; selected-row work is bounded."""
    _need(source.device.type == 'cpu' and source.dtype == torch.bfloat16
          and source.is_contiguous(), 'contiguous CPU BF16 source required')
    source_hash = _promoted_source_hash(source, chunk_rows)
    if projection is None:
        out = torch.empty(source.shape, dtype=torch.float32)
        out.copy_(source)
        return out, source_hash
    _need(projection in ('gate_proj', 'up_proj', 'down_proj'), 'native SwiGLU projection required')
    old, hidden = source.shape if projection != 'down_proj' else tuple(reversed(source.shape))
    selected, generator = replica_indices(old, target_width, layer_index)
    extra = target_width - old
    shape = (target_width, hidden) if projection != 'down_proj' else (hidden, target_width)
    out = torch.empty(shape, dtype=torch.float32)
    if projection == 'down_proj':
        out[:, :old].copy_(source)
        # Chunk hidden rows, avoiding a whole hidden-by-selected gather.
        for start in range(0, hidden, chunk_rows):
            chosen = source[start:start + chunk_rows].index_select(1, selected).float()
            chosen.mul_(.5)
            out[start:start + chunk_rows, old:].copy_(chosen)
            out[start:start + chunk_rows].index_copy_(1, selected, chosen)
    else:
        out[:old].copy_(source)
        signs = (torch.randint(0, 2, (extra, hidden), generator=generator, dtype=torch.int8)
                 if projection == 'up_proj' else None)
        for start in range(0, extra, chunk_rows):
            idx = selected[start:start + chunk_rows]
            original = source.index_select(0, idx).float()
            if projection == 'gate_proj':
                out[old + start:old + start + len(idx)].copy_(original)
            else:
                sign = signs[start:start + len(idx)].float().mul_(2).sub_(1)
                # Same multiplication sequence as the unchanged implementation.
                delta = original * sign * DELTA_FRACTION
                first, second = original + delta, original - delta
                _need(bool(torch.isfinite(first).all()) and bool(torch.isfinite(second).all())
                      and bool(torch.isfinite(2 * original).all())
                      and torch.equal(first + second, 2 * original),
                      'finite exact paired FP32 source sum required')
                out.index_copy_(0, idx, first)
                out[old + start:old + start + len(idx)].copy_(second)
    return out, source_hash


def _set_weight(module, value, *, trainable):
    module.weight = nn.Parameter(value, requires_grad=trainable)
    if isinstance(module, nn.Linear):
        module.out_features, module.in_features = value.shape


def _map_adapters(mlp, target_width, layer_index):
    old, hidden = mlp.up_proj.lora_B['default'].out_features, mlp.hidden_size
    selected, generator = replica_indices(old, target_width, layer_index)
    # Consume exactly the existing algorithm's full int8 sign draw. No chunked
    # RNG equivalence is assumed, and the 4 MiB official temporary is bounded.
    torch.randint(0, 2, (target_width - old, hidden), generator=generator, dtype=torch.int8)
    old_hashes = {name: tensor_sha256(value) for name, value in mlp.named_parameters()
                  if '.lora_' in name}
    for projection in ('gate_proj', 'up_proj'):
        linear = getattr(mlp, projection)
        b = linear.lora_B['default']
        _need(not bool(b.weight.count_nonzero()), 'pristine zero-B adapter required')
        _set_weight(b, torch.cat((b.weight, b.weight.new_zeros((target_width - old, b.in_features)))), trainable=True)
    down = mlp.down_proj
    _need(not bool(down.lora_B['default'].weight.count_nonzero()), 'pristine zero-B adapter required')
    a = down.lora_A['default']
    appended = torch.empty((a.out_features, target_width - old), dtype=torch.float32).uniform_(
        -1 / math.sqrt(old), 1 / math.sqrt(old), generator=generator).bfloat16().float()
    _set_weight(a, torch.cat((a.weight, appended), dim=1), trainable=True)
    for name, value in mlp.named_parameters():
        if '.lora_' not in name:
            continue
        original = value
        if name in ('gate_proj.lora_B.default.weight', 'up_proj.lora_B.default.weight'):
            original = value[:old]
        elif name == 'down_proj.lora_A.default.weight':
            original = value[:, :old]
        _need(tensor_sha256(original) == old_hashes[name], 'original adapter bytes changed')
    for projection in ('gate_proj', 'up_proj', 'down_proj'):
        linear = getattr(mlp, projection)
        linear.in_features, linear.out_features = linear.base_layer.in_features, linear.base_layer.out_features
    mlp.intermediate_size = target_width
    return {'source_adapter_sha256': old_hashes, 'new_down_A_sha256': tensor_sha256(appended)}


@dataclass(frozen=True)
class PrototypeBuild:
    model: nn.Module
    receipt: dict


def build_bounded_model(config, source, *, target_width, rank=64, alpha=16,
                        adapter_seed=731, chunk_rows=DEFAULT_CHUNK_ROWS, progress=None):
    """Exact tensor bridge on <=100M source parameters; no full-engine admission.

    Independently caps final parameter storage at 512 MiB and known live tensor
    allowance at 768 MiB: a native-parameter cap alone cannot bound LoRA when
    rank is large relative to hidden width.

    `source` must expose manifest and tensor(name). Source identities are the
    caller's responsibility. The hard cap cannot be raised by an argument.
    A callback may log completed allocations, but must not retain the model or
    tensor views. Global RNG is restored even if construction fails.
    """
    from peft import LoraConfig, get_peft_model
    from transformers import Qwen3ForCausalLM
    from transformers.models.qwen3.modeling_qwen3 import Qwen3RotaryEmbedding
    _need(type(adapter_seed) is int and 0 <= adapter_seed < 2**63, 'bounded integer adapter seed required')
    _need(type(alpha) in (int, float) and math.isfinite(alpha) and alpha > 0, 'positive finite alpha required')
    # Bound Python/module metadata before deepcopy, list multiplication, or
    # _geometry: tensor byte caps alone cannot bound millions of tiny layers.
    _need(type(config.num_hidden_layers) is int and 1 <= config.num_hidden_layers <= 4
          and type(config.hidden_size) is int and 1 <= config.hidden_size <= 2048
          and type(rank) is int and 1 <= rank <= min(64, config.hidden_size),
          'bounded prototype layer count, hidden width, and LoRA rank required; full 2B forbidden')
    config = copy.deepcopy(config)
    _need(config.model_type == 'qwen3' and config.hidden_act == 'silu'
          and not config.tie_word_embeddings and not config.attention_bias
          and config.vocab_size == 16 and config.attention_dropout == 0
          and isinstance(config.layer_types, (tuple, list))
          and len(config.layer_types) == config.num_hidden_layers
          and all(kind == 'full_attention' for kind in config.layer_types),
          'untied compact full-attention Qwen3 SwiGLU configuration required')
    geometry = {key: getattr(config, key) for key in ('hidden_size', 'intermediate_size',
        'num_hidden_layers', 'num_attention_heads', 'num_key_value_heads', 'head_dim')}
    _need(all(type(value) is int and value > 0 for value in geometry.values())
          and geometry['num_attention_heads'] % geometry['num_key_value_heads'] == 0,
          'positive integer Qwen3 geometry and divisible GQA required')
    shapes = _geometry(geometry)
    count = sum(math.prod(shape) for shape in shapes.values())
    _need(count <= MAX_PROTOTYPE_SOURCE_PARAMETERS,
          'prototype source cap forbids full official 2B construction; coordinate separately')
    plan = memory_plan(geometry, target_width, rank=rank, chunk_rows=chunk_rows)
    _need(plan['final_parameter_bytes'] <= MAX_PROTOTYPE_FINAL_PARAMETER_BYTES
          and plan['known_tensor_peak_allowance_bytes'] <= MAX_PROTOTYPE_KNOWN_TENSOR_PEAK_BYTES,
          'prototype final/peak tensor allocation cap exceeded before construction')
    _need(set(source.manifest) == set(shapes) and all(source.manifest[name] == (shape, torch.bfloat16)
          for name, shape in shapes.items()), 'exact complete BF16 native source inventory required')
    config._attn_implementation = 'sdpa'
    config.use_cache = False
    source_hashes, adapter_receipts = {}, []
    with torch.random.fork_rng(devices=[]), torch.no_grad():
        with torch.device('meta'):
            raw = Qwen3ForCausalLM(config)
        _need(set(dict(raw.named_parameters())) == set(shapes), 'unexpected native model parameters')
        for name, parameter in list(raw.named_parameters()):
            module_name, parameter_name = name.rsplit('.', 1)
            module = raw.get_submodule(module_name)
            placeholder = torch.zeros((), dtype=torch.bfloat16).expand(parameter.shape)
            setattr(module, parameter_name, nn.Parameter(placeholder, requires_grad=False))
        # The baseline casts its original rotary buffers to BF16 before later
        # exact FP32 promotion. Recomputing straight in FP32 would change bytes.
        raw.model.rotary_emb = Qwen3RotaryEmbedding(config, device='cpu').bfloat16()
        def forbid_forward(*_args, **_kwargs):
            raise RuntimeError('unmaterialized streaming prototype must never execute')
        # Guard every native submodule, not just raw(...): direct MLP or
        # embedding calls must also fail. modules_to_save deepcopy carries these
        # hooks into both saved-module copies; function identity is preserved.
        for native_module in raw.modules():
            native_module.register_forward_pre_hook(forbid_forward)
        torch.random.default_generator.manual_seed(adapter_seed)
        model = get_peft_model(raw, LoraConfig(r=rank, lora_alpha=alpha, lora_dropout=0.0,
            use_rslora=True, bias='none', task_type='CAUSAL_LM', target_modules=list(PROJECTIONS),
            modules_to_save=['embed_tokens', 'lm_head']))
        for parameter in model.parameters():
            if parameter.requires_grad:
                parameter.data = parameter.data.float()
        for name in shapes:
            module_name = name.rsplit('.', 1)[0]
            module = raw.get_submodule(module_name)
            is_mlp = '.mlp.' in name
            index = int(name.split('.')[2]) if is_mlp else 0
            projection = name.split('.')[-2] if is_mlp else None
            with source.tensor(name) as value:
                _need(isinstance(value, torch.Tensor) and tuple(value.shape) == shapes[name]
                      and value.device.type == 'cpu' and value.dtype == torch.bfloat16
                      and value.is_contiguous(), 'actual source shape/dtype/device/contiguity differs: ' + name)
                destination, source_hash = _native_destination(value, projection=projection,
                    target_width=target_width if is_mlp else None, layer_index=index, chunk_rows=chunk_rows)
            # Explicitly release the context's mmap tensor before the next open.
            del value
            source_hashes[name] = source_hash
            if hasattr(module, 'base_layer'):
                _set_weight(module.base_layer, destination, trainable=False)
            elif hasattr(module, 'modules_to_save'):
                _set_weight(module.original_module, destination, trainable=False)
                _set_weight(module.modules_to_save['default'], destination.clone(), trainable=True)
            else:
                _set_weight(module, destination, trainable=False)
            del destination
            if progress is not None:
                progress(name)
        for index, layer in enumerate(raw.model.layers):
            adapter_receipts.append(_map_adapters(layer.mlp, target_width, index))
        model.config.intermediate_size = target_width
        install_policy(model, FP32_BACKBONE_POLICY)
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        install_checkpoint_policy(model, FP32_BACKBONE_POLICY)
        model.enable_input_require_grads()
        parameters = list(model.parameters())
        _need(all(p.device.type == 'cpu' and p.dtype == torch.float32 and p.is_contiguous()
                  and all(stride > 0 for stride in p.stride()) for p in parameters),
              'unmaterialized or overlapping native placeholders remain')
        _need(len({p.untyped_storage().data_ptr() for p in parameters}) == len(parameters),
              'final independent parameter storage required')
        _need(sum(p.numel() * p.element_size() for p in parameters) == plan['final_parameter_bytes'],
              'final parameter allocation differs from exact width accounting')
        _need(all(b.device.type == 'cpu' and b.dtype == torch.float32 for b in model.buffers()),
              'unmaterialized or non-FP32 native buffer remains')
        for materialized_module in model.modules():
            for hook_id, function in list(materialized_module._forward_pre_hooks.items()):
                if function is forbid_forward:
                    del materialized_module._forward_pre_hooks[hook_id]
    return PrototypeBuild(model, {'format': 'irisx/bounded-streaming-width-prototype-v1',
        'source_parameter_count': count, 'source_promoted_sha256': source_hashes,
        'adapter_mapping': adapter_receipts, 'memory_plan': plan,
        'full_model_admitted': False, 'width_engine_admitted': False,
        'official_provenance_verified_by_this_builder': False,
        'capability_gain_established': False, 'gpu_executed': False})

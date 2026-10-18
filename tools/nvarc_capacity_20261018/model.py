"""Source-preserving compact capacity-v2, separate from the BF16 depth-v1 receipt.

Official source + zero-B rsLoRA are initialized by the unchanged CompactEngine
in BF16, then exactly promoted by fp32-backbone-math-v1. Only then are frozen
identity blocks or sparse cloned FFNs added. No shared engine contract changes.
This is executable architecture, not official-weight/GPU effectiveness evidence.
"""
from __future__ import annotations

import copy
import math
import re

import torch
from torch import nn

from tools.nvarc_posttrain_20261017.engine import (
    CompactEngine, validate_tokenizer,
)
from tools.nvarc_posttrain_20261017.precision import (
    full_precision_compute, install_checkpoint_policy, validate_policy, validate_checkpoint_policy,
)
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
from tools.nvarc_posttrain_20261017.materials import verify_model
from tools.nvarc_capacity_20261017.factory import _digest, _geometry, _probe
from tools.nvarc_capacity_20261017.training import _module_numerics

FORMAT = 'irisx/compact-capacity-fp32-v2'
TREATMENTS = ('baseline', 'depth32', 'moe4_top2')
LAYERS = (6, 13, 20, 27)
EXPERTS, TOP_K = 4, 2
ROUTER_SEED = 20261018
_LAYER = re.compile(r'^(base_model\.model\.model\.layers\.)(\d+)(\..+)$')


def _need(value, message):
    if not value:
        raise ValueError(message)


def accounting(base, treatment, *, rank=64, layers=None):
    """Exact geometry counts; FLOPs are analytic linear arithmetic, NOT timing.

    PEFT stores frozen original heads as well as active trainable copies. Total
    includes both; potentially-active counts exclude the unused originals and
    unselected experts. Token embedding table is counted conventionally, not as
    though all embedding rows are read by every token. Attention quadratic work,
    activations, normalization, routing top-k and optimizer work are excluded
    from the linear-forward estimate, and must not be called measured FLOPs.
    """
    _need(treatment in TREATMENTS, 'explicit baseline/depth32/moe4_top2 required')
    layers = LAYERS if layers is None else tuple(layers)
    n, h, inter = (base[k] for k in ('num_hidden_layers', 'hidden_size', 'intermediate_size'))
    q, kv = base['num_attention_heads'] * base['head_dim'], base['num_key_value_heads'] * base['head_dim']
    _need(layers and tuple(sorted(set(layers))) == layers and all(type(i) is int and 0 <= i < n for i in layers),
          'unique increasing selected original layers required')
    _need(type(rank) is int and 0 < rank <= 64, 'bounded positive rank required')
    native = sum(math.prod(shape) for shape in _geometry(base).values())
    attention = 2 * h * q + 2 * h * kv
    ffn = 3 * h * inter
    norms = 2 * h + 2 * base['head_dim']
    attn_lora = rank * (2 * (h + q) + 2 * (h + kv))
    ffn_lora = rank * 3 * (h + inter)
    lora = n * (attn_lora + ffn_lora)
    blocks = len(layers) if treatment == 'depth32' else 0
    moe_layers = len(layers) if treatment == 'moe4_top2' else 0
    extra_native = blocks * (attention + ffn + norms) + moe_layers * (EXPERTS - 1) * ffn
    extra_lora = blocks * (attn_lora + ffn_lora) + moe_layers * (EXPERTS - 1) * ffn_lora
    router = moe_layers * h * EXPERTS
    trainable = lora + extra_lora + 32 * h + router
    total = native + extra_native + trainable
    inactive = 32 * h + moe_layers * (EXPERTS - TOP_K) * (ffn + ffn_lora)
    linear = (n + blocks) * (attention + ffn + attn_lora + ffn_lora) + 16 * h
    linear += moe_layers * ((TOP_K - 1) * (ffn + ffn_lora) + h * EXPERTS)
    return {'source_native_parameters': native, 'added_native_parameters': extra_native,
        'frozen_parameters': native + extra_native, 'trainable_parameters': trainable,
        'total_resident_parameters': total, 'potentially_active_parameters_per_token': total - inactive,
        'resident_parameter_bytes_fp32': total * 4, 'router_parameters': router,
        'layers': n + blocks, 'selected_original_layers': list(layers) if treatment != 'baseline' else [],
        'experts_per_selected_layer': EXPERTS if moe_layers else 1,
        'experts_executed_per_token': TOP_K if moe_layers else 1,
        'linear_forward_flops_per_token': 2 * linear,
        'flops_kind': 'analytic linear forward only; excludes quadratic attention/backward/recompute/optimizer',
        'equal_compute_claimed': False, 'actual_wall_seconds': None, 'actual_peak_memory_bytes': None}


def official_accounting(treatment):
    # The canonical official contract carries untouched GQA/RoPE/RMSNorm values.
    from tools.nvarc_posttrain_20261017.matched_controller import _official_model_contract
    return accounting(_official_model_contract(), treatment)


class SparseTopKFFN(nn.Module):
    """True token-dispatched normalized top-2 expert FFNs; no dense all-E pass.

    Every expert is the native Qwen3 SwiGLU (frozen cloned weights + rsLoRA).
    Only selected tokens enter an expert. Identical inherited functions make
    upcycling mathematically preserving; FP32 dispatch/reduction can round.
    Zero B gives zero task router gradient initially. Distinct seeded A matrices
    break expert symmetry on the first update; router task gradients then wake.
    No auxiliary/load-balance loss, capacity dropping, jitter or shared expert.
    """
    def __init__(self, original, *, seed):
        super().__init__()
        _need(type(original).__name__ == 'Qwen3MLP', 'native PEFT Qwen3 FFN required')
        self.experts = nn.ModuleList([original] + [copy.deepcopy(original) for _ in range(EXPERTS - 1)])
        weight = original.up_proj.base_layer.weight
        self.router = nn.Linear(weight.shape[1], EXPERTS, bias=False,
                                device=weight.device, dtype=torch.float32)
        generator = torch.Generator(device='cpu').manual_seed(seed)
        with torch.no_grad():
            self.router.weight.copy_(torch.randn(self.router.weight.shape, generator=generator) * .01)
            for expert in self.experts[1:]:
                for name in ('gate_proj', 'up_proj', 'down_proj'):
                    module = getattr(expert, name)
                    # New adapters use the original BF16 initializer distribution
                    # then exact FP32 promotion, never new FP32 source precision.
                    a = module.lora_A['default'].weight
                    seeded = torch.empty(a.shape, dtype=torch.float32).uniform_(
                        -1 / math.sqrt(a.shape[1]), 1 / math.sqrt(a.shape[1]), generator=generator)
                    a.copy_(seeded.to(torch.bfloat16).to(device=a.device, dtype=torch.float32))
                    _need(not bool(torch.count_nonzero(module.lora_B['default'].weight)),
                          'fresh zero-B expert required')
        self.top_k = TOP_K
        self.expert_count = EXPERTS
        self.dispatch_calls = 0
        self.expert_token_attempts = [0] * EXPERTS
        self.expert_token_successes = [0] * EXPERTS
        self.last_dispatch = None
        self.routing_tokens = 0
        self.routing_entropy_sum = None
        self.selected_entropy_sum = None

    def forward(self, x):
        _need(self.top_k == TOP_K and self.expert_count == EXPERTS and len(self.experts) == EXPERTS,
              'actual sparse top-2/four-expert dispatch required before execution')
        flat = x.reshape(-1, x.shape[-1])
        scores = self.router(flat)
        values, chosen = torch.topk(scores, self.top_k, dim=-1, sorted=True)
        weights = torch.softmax(values, dim=-1)
        # Detached device scalars avoid a host synchronization on every expert
        # call. These diagnostics count recomputation too and never enter loss.
        with torch.no_grad():
            probabilities = torch.softmax(scores.detach(), dim=-1)
            entropy = -(probabilities * probabilities.clamp_min(1e-30).log()).sum()
            selected_entropy = -(weights.detach() * weights.detach().clamp_min(1e-30).log()).sum()
            self.routing_entropy_sum = entropy if self.routing_entropy_sum is None else self.routing_entropy_sum + entropy
            self.selected_entropy_sum = selected_entropy if self.selected_entropy_sum is None else self.selected_entropy_sum + selected_entropy
            self.routing_tokens += flat.shape[0]
        result = torch.zeros_like(flat)
        counts = []
        self.dispatch_calls += 1
        for expert_id, expert in enumerate(self.experts):
            tokens, slots = torch.where(chosen == expert_id)
            count = tokens.numel()
            counts.append(count)
            if count == 0:
                continue
            self.expert_token_attempts[expert_id] += count
            output = expert(flat.index_select(0, tokens))
            self.expert_token_successes[expert_id] += count
            result = result.index_add(0, tokens, output * weights[tokens, slots, None])
        self.last_dispatch = {'input_tokens': flat.shape[0], 'expert_token_counts': counts,
            'selected_token_expert_pairs': sum(counts), 'dense_all_experts_executed': False}
        return result.reshape_as(x)


def _transformed_inventory(named, layout, selected, treatment):
    result = {}
    for name, value in named.items():
        match = _LAYER.fullmatch(name)
        if match is None:
            result[name] = tuple(value.shape)
            continue
        prefix, index, suffix = match.groups()
        index = int(index)
        for row in layout:
            if row['original_index'] != index:
                continue
            stem = prefix + str(row['index'])
            if treatment == 'moe4_top2' and index in selected and suffix.startswith('.mlp.'):
                for expert in range(EXPERTS):
                    result[stem + '.mlp.experts.' + str(expert) + suffix[len('.mlp'):]] = tuple(value.shape)
            else:
                result[stem + suffix] = tuple(value.shape)
    return result


def _inventory(model):
    return {name: {'shape': list(p.shape), 'dtype': str(p.dtype)}
            for name, p in sorted(model.named_parameters()) if p.requires_grad}


def _numerics(model):
    result = _module_numerics(model)
    for name, module in model.named_modules():
        for key in ('attention_scaling', 'rope_type', 'max_seq_len_cached', 'original_max_seq_len'):
            if hasattr(module, key):
                result.setdefault(name, {})[key] = copy.deepcopy(getattr(module, key))
    return result


def _source_values(model, layout, treatment, selected):
    """Map inherited tensors to their original names without copying the model."""
    raw = dict(model.named_parameters())
    result = {}
    for name, value in raw.items():
        match = _LAYER.fullmatch(name)
        if match is None:
            result[name] = value
            continue
        prefix, index, suffix = match.groups()
        row = layout[int(index)]
        if row['new']:
            continue
        if treatment == 'moe4_top2' and row['original_index'] in selected and suffix.startswith('.mlp.'):
            if not suffix.startswith('.mlp.experts.0.'):
                continue
            suffix = '.mlp.' + suffix[len('.mlp.experts.0.'):]
        result[prefix + str(row['original_index']) + suffix] = value
    return result


class CapacityEngine(CompactEngine):
    """Capacity-v2 inventory with unchanged compact safety/update/generation/I/O.

    Construct through from_dense/load_engine. An expanded model never reuses an
    optimizer or KV cache. Checkpoints reconstruct architecture first and then
    restore exact named trainables; native weights are always source-derived.
    """
    def _healthy(self):
        super()._healthy()
        self._structure_admission(check_values=False)

    def _structure_admission(self, *, check_values=False):
        validate_policy(self.model, self.probability_policy)
        validate_checkpoint_policy(self.model, self.probability_policy)
        _need(self.probability_policy == FP32_BACKBONE_POLICY and self.base_dtype == torch.float32
              and self.source_base_dtype == torch.bfloat16, 'capacity-v2 exact source/resident policy required')
        _need(self.model.config.to_dict() == self._capacity_config
              and self.model.config._attn_implementation == 'sdpa'
              and _numerics(self.model) == self._capacity_numerics,
              'capacity config, RMSNorm/GQA/RoPE or indexed residual numerics changed')
        _need(validate_tokenizer(self.tokenizer) == self.tokenizer_admission, 'compact tokenizer changed')
        _need({n: c.to_dict() for n, c in self.model.peft_config.items()} == self._capacity_peft_config
              and self.model.active_adapter == 'default', 'capacity PEFT policy changed')
        _need(self.trainable_inventory == self._capacity_bound_trainables,
              'capacity complete trainable metadata changed')
        named = dict(self.model.named_parameters())
        trainables = {n: p for n, p in named.items() if p.requires_grad}
        frozen = {n: p for n, p in named.items() if not p.requires_grad}
        _need(_inventory(self.model) == self.trainable_inventory['tensors']
              and set(named) == set(self._capacity_shapes)
              and all(tuple(p.shape) == self._capacity_shapes[n] and p.dtype == torch.float32
                      and p.device == self.device and id(p) == self._capacity_parameter_ids[n]
                      for n, p in named.items())
              and {id(p) for p in trainables.values()} == {id(p) for p in self.parameters}
              and len(trainables) == len(self.parameters), 'capacity trainable/frozen tensor inventory changed')
        _need(len(list(self.model.named_parameters(remove_duplicate=False))) == len(named)
              and len({p.untyped_storage().data_ptr() for p in named.values()}) == len(named),
              'capacity parameters must have independent storage')
        _need({name: id(module) for name, module in self.model.named_modules()} == self._capacity_module_ids,
              'capacity live module replaced')
        _need(tuple((name, p._version) for name, p in sorted(frozen.items())) == self._capacity_frozen_versions,
              'frozen source tensor version changed')
        _need(tuple((n, id(b), tuple(b.shape), str(b.dtype), str(b.device), b._version)
                    for n, b in sorted(self.model.named_buffers())) == self._capacity_buffer_identity,
              'capacity RoPE/native buffer identity or version changed')
        _need(self.contract == self._capacity_bound_contract, 'capacity reconstruction receipt changed')
        for module in self.model.modules():
            if isinstance(module, SparseTopKFFN):
                _need(module.top_k == TOP_K and module.expert_count == EXPERTS and len(module.experts) == EXPERTS,
                      'actual sparse routing contract changed')
            if hasattr(module, 'lora_A') and 'default' in module.lora_A:
                _need(module.scaling['default'] == self.trainable_inventory['alpha'] /
                      math.sqrt(self.trainable_inventory['rank']) and module.active_adapter == ['default']
                      and not module.disable_adapters and not module.merged
                      and isinstance(module.lora_dropout['default'], nn.Identity),
                      'active expert rsLoRA policy changed')
        if check_values:
            _need(_digest(frozen) == self.contract['capacity_v2']['frozen_native_sha256'],
                  'capacity frozen native content changed')
            _need(_digest(dict(self.model.named_buffers())) == self.contract['capacity_v2']['buffers_sha256'],
                  'capacity RoPE/native buffers changed')
            _need(all(bool(torch.isfinite(p).all()) for p in trainables.values()), 'nonfinite capacity trainable')

    def commit(self, optimizer):
        self._structure_admission()
        self.last_router_gradient_norms = {name: None if module.router.weight.grad is None
            else module.router.weight.grad.detach().norm().item()
            for name, module in self.model.named_modules() if isinstance(module, SparseTopKFFN)}
        result = super().commit(optimizer)
        self._structure_admission()
        return result

    def dispatch_receipt(self):
        return {name: {'forward_calls_including_checkpoint_recompute': module.dispatch_calls,
                'expert_token_attempts': list(module.expert_token_attempts),
                'expert_token_successes': list(module.expert_token_successes),
                'dead_experts_in_observed_calls': [i for i, count in enumerate(module.expert_token_attempts) if count == 0],
                'mean_full_router_entropy_nats': None if not module.routing_tokens else module.routing_entropy_sum.item() / module.routing_tokens,
                'mean_selected_router_entropy_nats': None if not module.routing_tokens else module.selected_entropy_sum.item() / module.routing_tokens,
                'routing_tokens_including_recompute': module.routing_tokens,
                'last_task_router_gradient_norm': self.last_router_gradient_norms.get(name),
                'balance_loss_added': False,
                'last_dispatch': copy.deepcopy(module.last_dispatch)}
                for name, module in self.model.named_modules() if isinstance(module, SparseTopKFFN)}


def from_dense(engine, treatment, *, fixture_layers=None):
    """Consume a fresh exact-policy dense engine; never silently promote v1.

    This factory does NOT accept the old BF16 capacity receipt. The initial
    short full/cached probe is a local numerical admission, not a full-context
    probability gate or official-weight/GPU evidence. All source tensors and
    inherited adapters are preserved exactly under an explicit name mapping.
    """
    _need(type(engine) is CompactEngine and engine.capacity_receipt is None,
          'fresh ordinary dense CompactEngine required, not historical capacity receipt')
    engine._checkpoint_admission()
    _need(engine.probability_policy == FP32_BACKBONE_POLICY and not engine._checkpoint_loaded
          and not engine.optimizer_attempts and not engine.optimizer_steps and not engine.forward_calls
          and all(p.grad is None for p in engine.model.parameters()),
          'unused BF16-initialized then FP32/math engine required')
    _need(all(not bool(torch.count_nonzero(m.lora_B['default'].weight)) for m in engine.model.modules()
              if hasattr(m, 'lora_B') and 'default' in m.lora_B), 'exact zero-B initial adapters required')
    base = copy.deepcopy(engine.contract)
    tiny = base['variant'] == 'tiny'
    _need(base['variant'] in ('tiny', '2b') and (fixture_layers is None or tiny),
          'official2B only; custom layer selection is CPU-fixture-only')
    selected = tuple(fixture_layers) if fixture_layers is not None else LAYERS
    _need(not tiny or engine.device.type == 'cpu', 'tiny fixture cannot claim GPU admission')
    counts = accounting(base, treatment, rank=engine.trainable_inventory['rank'], layers=selected)
    model, raw = engine.model, engine.model.get_base_model()
    inherited = dict(model.named_parameters())
    inherited_trainable = {n: p for n, p in inherited.items() if p.requires_grad}
    inherited_digest = _digest(inherited)
    with full_precision_compute(engine.device.type):
        model.eval()
        before = _probe(model)
    old_layers = raw.model.layers
    old_config = copy.deepcopy(model.config.to_dict())
    layout = []
    for index in range(base['num_hidden_layers']):
        layout.append({'index': len(layout), 'original_index': index, 'new': False})
        if treatment == 'depth32' and index in selected:
            layout.append({'index': len(layout), 'original_index': index, 'new': True})
    try:
        blocks = []
        for row in layout:
            layer = old_layers[row['original_index']]
            if row['new']:
                layer = copy.deepcopy(layer)
                with torch.no_grad():
                    layer.self_attn.o_proj.base_layer.weight.zero_()
                    layer.mlp.down_proj.base_layer.weight.zero_()
            blocks.append(layer)
        raw.model.layers = nn.ModuleList(blocks)
        if treatment == 'moe4_top2':
            # Preserve process RNG even though nn.Linear's constructor initializes
            # a value that is immediately overwritten by the private CPU stream.
            devices = [engine.device.index] if engine.device.type == 'cuda' else []
            with torch.random.fork_rng(devices=devices):
                for index in selected:
                    raw.model.layers[index].mlp = SparseTopKFFN(raw.model.layers[index].mlp,
                                                               seed=ROUTER_SEED + index)
        model.config.num_hidden_layers = len(layout)
        model.config.layer_types = ['full_attention'] * len(layout)
        for index, layer in enumerate(raw.model.layers):
            layer.self_attn.layer_idx = index
            layer.self_attn.config = model.config
            if isinstance(layer.mlp, SparseTopKFFN):
                for expert in layer.mlp.experts:
                    expert.config = model.config
            else:
                layer.mlp.config = model.config
        # A deep-copied block retains the exact FP32 recomputation function.
        install_checkpoint_policy(model, FP32_BACKBONE_POLICY)
        shapes = _transformed_inventory(inherited, layout, selected, treatment)
        train_shapes = _transformed_inventory(inherited_trainable, layout, selected, treatment)
        if treatment == 'moe4_top2':
            for index in selected:
                name = f'base_model.model.model.layers.{index}.mlp.router.weight'
                shapes[name] = train_shapes[name] = (EXPERTS, base['hidden_size'])
        named = dict(model.named_parameters())
        _need(set(named) == set(shapes) and all(tuple(named[n].shape) == s for n, s in shapes.items()),
              'expanded actual parameter geometry differs')
        _need({n for n, p in named.items() if p.requires_grad} == set(train_shapes),
              'expanded exact trainable scope differs')
        _need(_digest(_source_values(model, layout, treatment, selected)) == inherited_digest,
              'inherited exact BF16-source/adapter values changed during expansion')
        _need(sum(p.numel() for p in named.values()) == counts['total_resident_parameters']
              and sum(p.numel() for p in named.values() if p.requires_grad) == counts['trainable_parameters'],
              'actual expanded parameter accounting differs')
        with full_precision_compute(engine.device.type):
            model.eval()
            after = _probe(model)
        gap = max((before[0] - after[0]).abs().max().item(), (before[1] - after[1]).abs().max().item())
        limit = 0. if treatment in ('baseline', 'depth32') else 1e-5 if tiny else 1e-4
        _need(math.isfinite(gap) and gap <= limit and before[2] == after[2],
              'short initial full/cached function preservation probe failed')
        _need(after[3] == len(layout), 'expanded KV cache layout differs')
        receipt = {'format': FORMAT, 'treatment': treatment, 'base_model_contract': base,
            'layout': layout, 'selected_original_layers': list(selected) if treatment != 'baseline' else [],
            'probability_policy': FP32_BACKBONE_POLICY, 'source_base_dtype': 'torch.bfloat16',
            'resident_dtype': 'torch.float32', 'adapter_seed': engine.adapter_seed,
            'router_seed': ROUTER_SEED if treatment == 'moe4_top2' else None,
            'inherited_source_and_adapter_sha256': inherited_digest,
            'frozen_native_sha256': _digest({n: p for n, p in named.items() if not p.requires_grad}),
            'buffers_sha256': _digest(dict(model.named_buffers())), 'accounting': counts,
            'initial_function_contract': {'predeclared_max_absolute_logit_gap': limit,
                'greedy_tokens_equal_required': True, 'probe_tokens': 13, 'cached_steps': 4,
                'full_context_admitted': False, 'probability_gate_unchanged': .05 if not tiny else 1e-5},
            'optimizer_reuse_allowed': False, 'native_weights_trainable': False,
            'router_trainable': treatment == 'moe4_top2', 'router_auxiliary_loss': None,
            'requires_full_workload_gpu_validation': True, 'capability_gain_established': False}
        result = object.__new__(CapacityEngine)
        result.__dict__.update(engine.__dict__)
        result.treatment = treatment
        result.last_router_gradient_norms = {}
        # Measured last-bit differences are evidence, not reconstruction identity:
        # a different admitted device can round the same sparse dispatch slightly
        # differently without changing any tensor bytes or checkpoint contract.
        result.initial_function_receipt = {
            **receipt['initial_function_contract'], 'full_and_cached_max_absolute_logit_gap': gap,
            'greedy_tokens_equal': True, 'exact_bitwise_preservation': gap == 0.,
            'actual_device_type': engine.device.type}
        result.contract = {**base, 'num_hidden_layers': len(layout),
                           'layer_types': ['full_attention'] * len(layout), 'capacity_v2': receipt}
        result.capacity_receipt = None  # Never impersonate/relax depth-v1.
        result.trainable_inventory = {**engine.trainable_inventory, 'tensors': _inventory(model),
            'tensor_count': len(train_shapes), 'parameter_count': counts['trainable_parameters'],
            'capacity_format': FORMAT, 'treatment': treatment, 'router_parameters': counts['router_parameters']}
        result.parameters = [p for p in model.parameters() if p.requires_grad]
        result._capacity_shapes = shapes
        result._capacity_parameter_ids = {n: id(p) for n, p in named.items()}
        result._capacity_module_ids = {n: id(m) for n, m in model.named_modules()}
        result._capacity_frozen_versions = tuple((n, p._version) for n, p in sorted(named.items()) if not p.requires_grad)
        result._capacity_buffer_identity = tuple((n, id(b), tuple(b.shape), str(b.dtype), str(b.device), b._version)
            for n, b in sorted(model.named_buffers()))
        result._capacity_config = copy.deepcopy(model.config.to_dict())
        result._capacity_peft_config = copy.deepcopy({n: c.to_dict() for n, c in model.peft_config.items()})
        result._capacity_numerics = _numerics(model)
        result._capacity_bound_contract = copy.deepcopy(result.contract)
        result._capacity_bound_trainables = copy.deepcopy(result.trainable_inventory)
        result._checkpoint_admission()
        for module in model.modules():
            if isinstance(module, SparseTopKFFN):
                module.dispatch_calls = 0
                module.expert_token_attempts = [0] * EXPERTS
                module.expert_token_successes = [0] * EXPERTS
                module.routing_tokens = 0
                module.routing_entropy_sum = module.selected_entropy_sum = module.last_dispatch = None
        return result
    except BaseException:
        if treatment == 'moe4_top2':
            for index in selected:
                module = old_layers[index].mlp
                if isinstance(module, SparseTopKFFN):
                    old_layers[index].mlp = module.experts[0]
        raw.model.layers = old_layers
        model.config.num_hidden_layers = old_config['num_hidden_layers']
        model.config.layer_types = old_config['layer_types']
        for index, layer in enumerate(old_layers):
            layer.self_attn.layer_idx = index
            layer.self_attn.config = model.config
            layer.mlp.config = model.config
        raise


def load_engine(path, treatment='baseline', *, device='cuda', seed=20261018, adapter_seed=731):
    """Only exact locally verified official2B SFT141; no ReArc or remote loads."""
    identity = verify_model(path, '2b')
    engine = CompactEngine.load(path, base_identity=identity, variant='2b', device=device,
        seed=seed, adapter_seed=adapter_seed, probability_policy=FP32_BACKBONE_POLICY)
    return from_dense(engine, treatment)


def probability_admission(engine, prompt_ids, *, deadline, max_new_tokens=32):
    """Distinct capacity-v2 no-update sampled-versus-full preflight for SFT.

    Reuses unchanged compact trace validation and eval/train replay helpers,
    not the original probe's deliberately strict dense-engine type admission.
    It does not pretend to be the AF3 full-pool gate, validate backward, or
    perform forced cached replay. Original sampled values are never replaced.
    Every attempted call is physically charged by the engine/helpers; vectors
    and a failed trace are returned before a caller rejects training.
    """
    from tools.nvarc_posttrain_20261017.probability_probe import _additional_full, _modes, _restore_modes
    from tools.nvarc_posttrain_20261017.probability_trace import validate_trace, validate_rows
    from tools.nvarc_posttrain_20261017.precision_contract import probability_tolerance
    _need(type(engine) is CapacityEngine, 'explicit capacity-v2 engine required')
    engine._checkpoint_admission()
    _need(type(max_new_tokens) is int and 1 <= max_new_tokens <= 931
          and type(deadline) in (int, float) and math.isfinite(deadline), 'bounded finite capacity preflight required')
    _need(all(p.grad is None for p in engine.model.parameters()), 'preflight requires no pending gradients')
    modes, private_rng = _modes(engine.model), engine.generator.get_state().clone()
    versions = [(p, p._version) for p in engine.model.parameters()]
    counters = ('forward_calls', 'sampled_tokens', 'optimizer_steps', 'optimizer_attempts',
        'generation_forward_attempts', 'generation_input_tokens', 'generation_row_token_slots',
        'generation_finished_row_token_slots', 'generation_padding_tokens')
    before = {key: getattr(engine, key) for key in counters}
    result = {'format': 'irisx/capacity-sampled-full-admission-v1', 'passed': False,
        'probability_policy': FP32_BACKBONE_POLICY, 'tolerance': probability_tolerance(engine),
        'trace': {}, 'rows': [], 'replays': {}, 'error': None,
        'cached_replay_performed': False, 'backward_validated': False,
        'rl_full_pool_admitted': False, 'optimizer_updates': 0}
    devices = [engine.device.index] if engine.device.type == 'cuda' else []
    try:
        with torch.random.fork_rng(devices=devices):
            generator = torch.Generator(device=engine.device).manual_seed(20261018)
            result['rows'] = engine.generate(prompt_ids, count=2, max_new_tokens=max_new_tokens,
                sample=True, deadline=deadline, generator=generator, trace=result['trace'])
            validate_trace(result['trace'], expected_trace_sha256=result['trace']['sha256'])
            validate_rows(result['rows'], result['trace'])
            for mode in ('eval_nograd', 'train_grad'):
                result['replays'][mode] = _additional_full(engine, result['rows'], mode=mode, deadline=deadline)
            result['passed'] = all(stage['status'] == 'completed' and len(stage['rows']) == 2
                and stage['metrics']['max_abs_logp_gap'] is not None
                and 0 <= stage['metrics']['max_abs_logp_gap'] <= result['tolerance']
                for stage in result['replays'].values())
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)[:1024]}
    finally:
        _restore_modes(modes)
        result['physical_counter_deltas'] = {key: getattr(engine, key) - before[key] for key in counters}
        _need(torch.equal(private_rng, engine.generator.get_state())
              and all(p._version == version and p.grad is None for p, version in versions)
              and result['physical_counter_deltas']['optimizer_steps'] == 0
              and result['physical_counter_deltas']['optimizer_attempts'] == 0,
              'capacity preflight changed parameters, gradients, optimizer or private RNG')
    return result

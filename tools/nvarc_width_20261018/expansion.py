"""Deterministic function-preserving SwiGLU width expansion, no model loading.

For each selected source channel j, gate rows are copied and down columns are
halved. Paired up rows u_j + delta_j and u_j - delta_j have mean u_j. Thus their
sum contributes d_j * silu(g_j x) * (u_j x), in real arithmetic. Unlike equal
replicas, the two hidden features differ. Delta is fixed before any task scoring:
independent Rademacher signs times each BF16-source weight times 2**-5, so every
coefficient changes by at most 3.125%, remains exactly FP32-representable, and
paired sums recover twice the source exactly. Native expanded weights stay FP32;
re-quantization to BF16 is NOT this policy and can break cancellation.

Only pristine zero-B default PEFT adapters are accepted. Gate/up A and all old
B rows are preserved; zero B rows are appended. Down-A old columns are preserved
and independent BF16-valued columns are appended, scaled to the original fan-in
initialization range. Down-B stays exact zero. No optimizer/cache state is mapped.
"""
from __future__ import annotations
import hashlib
import math
import torch
from torch import nn

WIDTH = 8192
EXPANSION_SEED = 20261018
DELTA_FRACTION = 2.0 ** -5
CONSTRUCTION = {
    'version': 'paired-up-antisymmetric-swiglu-v1',
    'target_intermediate_size': WIDTH,
    'selection': 'CPU randperm(source_width) prefix; seed + original_layer_index',
    'seed': EXPANSION_SEED,
    'delta_fraction': DELTA_FRACTION,
    'delta_rule': 'source_up * independent CPU Rademacher signs * 2**-5',
    'down_split': [0.5, 0.5],
    'source_gate_rows_replicated': True,
    'old_lora_A_preserved': True,
    'new_down_A': 'independent CPU uniform original-fan-in range, BF16 then FP32',
    'all_lora_B_zero_required': True,
    'bf16_requantization_permitted': False,
}


def _need(value, message):
    if not value:
        raise ValueError(message)


def _sha(tensor):
    return hashlib.sha256(tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()).hexdigest()


def replica_indices(old_width, new_width, layer_index):
    _need(type(old_width) is int and type(new_width) is int and old_width < new_width <= 2 * old_width,
          'strict width growth by at most one copy per channel required')
    g = torch.Generator(device='cpu').manual_seed(EXPANSION_SEED + layer_index)
    return torch.randperm(old_width, generator=g)[:new_width-old_width], g


def _replace_linear_weight(module, tensor, *, trainable):
    # Keep native/PEFT module objects and hooks, but update their true geometry.
    module.weight = nn.Parameter(tensor.contiguous(), requires_grad=trainable)
    module.out_features, module.in_features = tensor.shape


def widen_mlp(mlp, new_width, *, layer_index):
    _need(type(mlp).__name__ == 'Qwen3MLP', 'native PEFT Qwen3 SwiGLU required')
    modules = [getattr(mlp, name) for name in ('gate_proj','up_proj','down_proj')]
    for m in modules:
        _need(hasattr(m, 'base_layer') and set(m.lora_A) == {'default'} and set(m.lora_B) == {'default'}
              and m.base_layer.bias is None and m.active_adapter == ['default'] and not m.merged
              and not m.disable_adapters and isinstance(m.lora_dropout['default'], nn.Identity),
              'unmerged active zero-dropout default LoRA required')
        _need(not bool(m.lora_B['default'].weight.count_nonzero()), 'only pristine zero-B adapters can widen')
        _need(all(p.dtype == torch.float32 and p.grad is None for p in m.parameters()),
              'unused FP32 source-promoted tensors required')
        _need(not m.base_layer.weight.requires_grad, 'frozen native tensors required')
    gate, up, down = modules
    old_width, hidden = gate.base_layer.weight.shape
    _need(tuple(up.base_layer.weight.shape) == (old_width,hidden)
          and tuple(down.base_layer.weight.shape) == (hidden,old_width), 'native SwiGLU geometry differs')
    for m in modules:
        w = m.base_layer.weight
        _need(torch.equal(w, w.bfloat16().float()), 'exact BF16-valued original source required')
    selected, generator = replica_indices(old_width, new_width, layer_index)
    device = gate.base_layer.weight.device
    index = selected.to(device)
    old_hashes = {name: _sha(p) for name,p in mlp.named_parameters()}
    rank = gate.lora_A['default'].weight.shape[0]
    _need(all(m.lora_A['default'].weight.shape[0] == rank for m in modules), 'one common LoRA rank required')
    with torch.no_grad():
        original = up.base_layer.weight.index_select(0, index)
        signs = torch.randint(0, 2, original.shape, generator=generator, dtype=torch.int8).float().mul_(2).sub_(1)
        delta = original * signs.to(device) * DELTA_FRACTION
        first, second = original + delta, original - delta
        _need(torch.equal(first + second, 2 * original), 'paired FP32 up rows must exactly recover source sum')
        gate_weight = torch.cat((gate.base_layer.weight, gate.base_layer.weight.index_select(0,index)), dim=0)
        up_weight = torch.cat((up.base_layer.weight, second), dim=0)
        up_weight.index_copy_(0, index, first)
        down_weight = torch.cat((down.base_layer.weight, down.base_layer.weight.index_select(1,index) * .5), dim=1)
        down_weight[:, index] *= .5
        # Complete expected transformation, explicitly checked before replacement.
        _need(torch.equal(down_weight[:, index] * 2, down.base_layer.weight[:,index]), 'exact down compensation required')
        _need(torch.equal(gate_weight[old_width:], gate.base_layer.weight[index]), 'exact gate replication required')
        for m, weight in zip(modules, (gate_weight,up_weight,down_weight)):
            _replace_linear_weight(m.base_layer, weight, trainable=False)
            m.in_features, m.out_features = m.base_layer.in_features, m.base_layer.out_features
        for m in (gate,up):
            b = m.lora_B['default']
            _replace_linear_weight(b, torch.cat((b.weight, torch.zeros((new_width-old_width,rank),device=device)),dim=0),trainable=True)
        a = down.lora_A['default']
        appended = torch.empty((rank,new_width-old_width),dtype=torch.float32).uniform_(
            -1 / math.sqrt(old_width), 1 / math.sqrt(old_width), generator=generator).bfloat16().float().to(device)
        _replace_linear_weight(a,torch.cat((a.weight,appended),dim=1),trainable=True)
    # Original LoRA slices remain byte-identical, including untouched A matrices.
    for name,p in mlp.named_parameters():
        if '.base_layer.' in '.'+name: continue
        original = p
        if name in ('gate_proj.lora_B.default.weight','up_proj.lora_B.default.weight'): original = p[:old_width]
        if name == 'down_proj.lora_A.default.weight': original = p[:,:old_width]
        _need(_sha(original) == old_hashes[name], 'original PEFT state mapping changed: '+name)
    mlp.intermediate_size = new_width
    return {'original_layer_index':layer_index, 'source_width':old_width, 'target_width':new_width,
        'selected_indices_sha256':_sha(selected), 'paired_source_sum_exact_fp32':True,
        'source_parameter_sha256':old_hashes,
        'new_down_A_sha256':_sha(appended), 'perturbation_nonzero_coefficients':int(delta.count_nonzero()),
        'perturbation_rms_relative':DELTA_FRACTION,
        'full_function_equality_mathematical_only':True}

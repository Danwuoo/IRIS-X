"""Separately admitted identity-depth + rsLoRA treatment for official compact 2B.

The native 28-layer model is reconstructed only from locally verified official
material, then four copied residual blocks get zero output projections. All
native tensors, including the added blocks, stay frozen. The actual CompactEngine
adds its unchanged seven-projection rsLoRA and full compact heads afterwards.
This is NOT the full-new-block treatment in the CPU-only training.py fixture.
Width/MoE are not admitted. No dataset, GPU launch, or effectiveness claim lives
here. A successful short starting-function probe is not full-context admission.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re

import torch
from torch import nn

from tools.nvarc_posttrain_20261017.engine import (
    CompactEngine, PROJECTIONS, load_compact_tokenizer, model_contract,
    validate_tokenizer, validate_trainables,
)
from tools.nvarc_posttrain_20261017.materials import verify_model

FORMAT = 'irisx/compact-identity-depth-rslora-v1'
TREATMENT = 'identity-depth-frozen-native-rslora'
OFFICIAL_AFTER = (6, 13, 20, 27)
PROBE_IDS = (14, 11, 10, 1, 0, 10, 0, 1, 15, 10, 14, 12, 10)
PROBE_STEPS = 4
_SCOPE = {'native_added_blocks_trainable': False, 'native_inherited_weights_trainable': False,
          'compact_heads_trainable': True, 'capability_gain_established': False,
          'gpu_admitted': False, 'full_context_admitted': False,
          'cache_and_optimizer_reuse_allowed': False}


def _need(value, message):
    if not value:
        raise ValueError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _digest(named):
    """Stream one tensor at a time; never duplicate the complete official model."""
    digest = hashlib.sha256()
    for name, value in sorted(named.items()):
        digest.update(_canonical([name, list(value.shape), str(value.dtype)]))
        flat = value.detach().reshape(-1)
        for chunk in flat.split(1024 * 1024):
            digest.update(chunk.cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _geometry(contract):
    h, inter, layers = (contract[k] for k in ('hidden_size', 'intermediate_size', 'num_hidden_layers'))
    q = contract['num_attention_heads'] * contract['head_dim']
    kv = contract['num_key_value_heads'] * contract['head_dim']
    result = {'model.embed_tokens.weight': (16, h), 'lm_head.weight': (16, h),
              'model.norm.weight': (h,)}
    block = {'self_attn.q_proj': (q, h), 'self_attn.k_proj': (kv, h),
             'self_attn.v_proj': (kv, h), 'self_attn.o_proj': (h, q),
             'self_attn.q_norm': (contract['head_dim'],),
             'self_attn.k_norm': (contract['head_dim'],),
             'mlp.gate_proj': (inter, h), 'mlp.up_proj': (inter, h),
             'mlp.down_proj': (h, inter), 'input_layernorm': (h,),
             'post_attention_layernorm': (h,)}
    for index in range(layers):
        result.update({f'model.layers.{index}.{key}.weight': shape for key, shape in block.items()})
    return result


def _core(base, after, rank, alpha, base_dtype):
    _need(base['variant'] in ('2b', 'tiny'), 'only official compact 2B or explicit tiny fixture supported')
    _need(base['hidden_act'] == 'silu' and base['layer_types'] == ['full_attention'] * base['num_hidden_layers']
          and base['num_attention_heads'] % base['num_key_value_heads'] == 0,
          'native full-attention SwiGLU geometry required')
    _need(isinstance(after, (tuple, list)) and after and all(type(i) is int for i in after)
          and tuple(sorted(set(after))) == tuple(after)
          and 0 <= after[0] <= after[-1] < base['num_hidden_layers'],
          'unique increasing original insertion indices required')
    _need(type(rank) is int and 0 < rank <= 64 and type(alpha) in (int, float)
          and math.isfinite(alpha) and alpha > 0, 'bounded positive rsLoRA rank/alpha required')
    _need(base_dtype in ('torch.bfloat16', 'torch.float32'), 'BF16 or tiny FP32 required')
    if base['variant'] == '2b':
        _need(tuple(after) == OFFICIAL_AFTER and rank == 64 and alpha == 16
              and base_dtype == 'torch.bfloat16', 'official depth28-to32/rank64/alpha16/BF16 required')
    layout = []
    for original in range(base['num_hidden_layers']):
        layout.append({'index': len(layout), 'original_index': original, 'new': False})
        if original in after:
            layout.append({'index': len(layout), 'original_index': original, 'new': True})
    expanded = {**base, 'num_hidden_layers': len(layout)}
    old, new = _geometry(base), _geometry(expanded)
    base_count, expanded_count = (sum(math.prod(s) for s in g.values()) for g in (old, new))
    h, inter = base['hidden_size'], base['intermediate_size']
    q, kv = base['num_attention_heads'] * base['head_dim'], base['num_key_value_heads'] * base['head_dim']
    lora = len(layout) * rank * (2 * (h + q) + 2 * (h + kv) + 3 * (h + inter))
    return {'format': FORMAT, 'treatment': TREATMENT, 'base_model_contract': copy.deepcopy(base),
            'after_layers': list(after), 'layout': layout, 'rank': rank, 'alpha': alpha,
            'attention_backend': 'sdpa',
            'base_dtype': base_dtype, 'base_parameters': base_count,
            'expanded_parameters': expanded_count, 'added_parameters': expanded_count - base_count,
            'base_native_tensor_count': len(old), 'expanded_native_tensor_count': len(new),
            'trainable_parameters': lora + 32 * h, 'trainable_tensor_count': len(layout) * 14 + 2,
            'peft_total_parameters': expanded_count + lora + 32 * h,
            'scope': copy.deepcopy(_SCOPE)}


def capacity_model_contract(config, receipt):
    """Pure strict expanded contract, without weakening ordinary model_contract."""
    _need(type(receipt) is dict and type(receipt.get('base_model_contract')) is dict,
          'complete deterministic capacity receipt required')
    base = receipt['base_model_contract']
    if not isinstance(config, dict):
        _need(config._attn_implementation == 'sdpa', 'capacity treatment requires SDPA attention')
    data = copy.deepcopy(config if isinstance(config, dict) else config.to_dict())
    expanded_layers = data.get('num_hidden_layers')
    _need(data.get('layer_types') == ['full_attention'] * len(receipt.get('layout', [])),
          'expanded full-attention layout differs')
    data['num_hidden_layers'] = base.get('num_hidden_layers')
    data['layer_types'] = ['full_attention'] * data['num_hidden_layers']
    recovered = model_contract(data, variant=base.get('variant'), test_fixture=base.get('variant') == 'tiny')
    _need(recovered == base, 'inherited model contract differs')
    core = _core(base, receipt.get('after_layers'), receipt.get('rank'), receipt.get('alpha'), receipt.get('base_dtype'))
    variable = {'base_native_sha256', 'expanded_native_sha256', 'native_buffers_sha256', 'initial_function'}
    _need(set(receipt) == set(core) | variable and all(receipt[k] == v for k, v in core.items())
          and expanded_layers == len(core['layout']), 'capacity recipe/accounting differs')
    _need(all(type(receipt[k]) is str and re.fullmatch('[0-9a-f]{64}', receipt[k])
              for k in ('base_native_sha256', 'expanded_native_sha256', 'native_buffers_sha256')),
          'exact native tensor hashes required')
    probe = receipt['initial_function']
    _need(probe == {'probe_ids': list(PROBE_IDS), 'cached_decode_steps': PROBE_STEPS,
                   'full_logits_equal': True, 'cached_logits_equal': True,
                   'greedy_tokens_equal': True, 'max_absolute_logit_difference': 0.0,
                   'base_cache_layers': base['num_hidden_layers'],
                   'expanded_cache_layers': len(core['layout'])},
          'measured exact initial-function admission required')
    result = copy.deepcopy(base)
    result.update(num_hidden_layers=expanded_layers, layer_types=['full_attention'] * expanded_layers,
                  capacity_receipt=copy.deepcopy(receipt))
    return result


def _native_named(model, *, peft=False):
    from transformers import Qwen3ForCausalLM
    from transformers.models.qwen3.modeling_qwen3 import Qwen3DecoderLayer, Qwen3Attention, Qwen3MLP, Qwen3RMSNorm
    raw = model.get_base_model() if peft else model
    _need(type(raw) is Qwen3ForCausalLM, 'actual native Qwen3ForCausalLM required')
    c = raw.config
    _need(len(raw.model.layers) == c.num_hidden_layers and type(raw.model.norm) is Qwen3RMSNorm,
          'actual native depth/norm differs')
    named = {'model.norm.weight': raw.model.norm.weight}
    for key, module in (('model.embed_tokens.weight', raw.get_input_embeddings()),
                        ('lm_head.weight', raw.get_output_embeddings())):
        named[key] = module.original_module.weight if peft else module.weight
    for index, layer in enumerate(raw.model.layers):
        _need(type(layer) is Qwen3DecoderLayer and type(layer.self_attn) is Qwen3Attention
              and type(layer.mlp) is Qwen3MLP and layer.self_attn.config is c
              and layer.mlp.config is c and layer.self_attn.layer_idx == index
              and layer.self_attn.attention_dropout == 0
              and layer.self_attn.head_dim == c.head_dim
              and layer.self_attn.num_key_value_groups == c.num_attention_heads // c.num_key_value_heads
              and layer.self_attn.scaling == c.head_dim ** -0.5
              and layer.self_attn.is_causal is True and layer.self_attn.sliding_window is None,
              'native indexed dropout-zero blocks required')
        for name in ('input_layernorm', 'post_attention_layernorm', 'self_attn.q_norm', 'self_attn.k_norm'):
            module = layer.get_submodule(name)
            _need(type(module) is Qwen3RMSNorm and module.variance_epsilon == c.rms_norm_eps,
                  'native RMSNorm numerics differ')
            named[f'model.layers.{index}.{name}.weight'] = module.weight
        for projection in PROJECTIONS:
            group = 'self_attn' if projection in PROJECTIONS[:4] else 'mlp'
            module = layer.get_submodule(f'{group}.{projection}')
            module = module.get_base_layer() if peft else module
            _need(type(module) is nn.Linear and module.bias is None, 'native bias-free projections required')
            named[f'model.layers.{index}.{group}.{projection}.weight'] = module.weight
    expected = _geometry(c.to_dict())
    _need(set(named) == set(expected) and all(tuple(named[k].shape) == s for k, s in expected.items()),
          'exact native tensor geometry required')
    _need(len({p.untyped_storage().data_ptr() for p in named.values()}) == len(named),
          'independent native tensor storage required')
    if not peft:
        _need(set(dict(raw.named_parameters())) == set(expected), 'unexpected native parameters')
    return named


def validate_capacity_base(model, receipt):
    """Validate actual newly expanded native tensors before PEFT mutation."""
    capacity_model_contract(model.config, receipt)
    named = _native_named(model)
    devices = {p.device for p in named.values()}
    _need(len(devices) == 1 and (receipt['base_model_contract']['variant'] != 'tiny'
          or (next(iter(devices)).type == 'cpu' and receipt['base_parameters'] <= 1000000)),
          'single-device native base and CPU-only bounded tiny fixture required')
    _need(not model.training and receipt == getattr(model, '_nvarc_capacity_receipt', None),
          'fresh evaluation-mode factory-owned capacity model required')
    _need(all(p.grad is None and str(p.dtype) == receipt['base_dtype']
              and bool(torch.isfinite(p).all()) for p in named.values()),
          'finite fresh uniform native tensors required')
    _need(_digest(named) == receipt['expanded_native_sha256'], 'expanded native tensor digest differs')
    _need(_digest(dict(model.named_buffers())) == receipt['native_buffers_sha256'], 'native buffer digest differs')
    for row in receipt['layout']:
        if row['new']:
            for path in ('self_attn.o_proj', 'mlp.down_proj'):
                _need(not bool(torch.count_nonzero(model.model.layers[row['index']].get_submodule(path).weight)),
                      'new-block output projections must initialize to zero')


def validate_capacity_engine(engine, *, check_values=True):
    """Check expanded actual CompactEngine; frozen hashes are checked at I/O gates."""
    from tools.nvarc_posttrain_20261017.engine import bind_trainable_contract
    receipt = engine.capacity_receipt
    expected = capacity_model_contract(engine.model.config, receipt)
    _need(engine.contract == expected, 'live expanded architecture contract differs')
    named = _native_named(engine.model, peft=True)
    _need({p.device for p in named.values()} == {engine.device}
          and (receipt['base_model_contract']['variant'] != 'tiny' or engine.device.type == 'cpu'),
          'actual resident device differs or synthetic fixture left CPU')
    _need(all(not p.requires_grad and str(p.dtype) == receipt['base_dtype'] for p in named.values()),
          'all inherited and added native tensors must stay frozen')
    current = validate_trainables(engine.model, rank=receipt['rank'], alpha=receipt['alpha'],
                                 base_dtype=engine.base_dtype)
    _need(bind_trainable_contract(current, engine.probability_policy) == engine.trainable_inventory
          and current['parameter_count'] == receipt['trainable_parameters']
          and current['tensor_count'] == receipt['trainable_tensor_count']
          and sum(p.numel() for p in engine.model.parameters()) == receipt['peft_total_parameters'],
          'actual expanded rsLoRA/heads accounting differs')
    guard = tuple((name, id(p), p._version) for name, p in sorted(named.items()))
    prior = getattr(engine, '_capacity_frozen_guard', None)
    _need(prior is None or guard == prior, 'frozen native tensor identity/version changed')
    if check_values:
        _need(_digest(named) == receipt['expanded_native_sha256'], 'frozen native tensor content changed')
        _need(_digest(dict(engine.model.get_base_model().named_buffers())) == receipt['native_buffers_sha256'],
              'native buffer content changed')
    if prior is None:
        engine._capacity_frozen_guard = guard


@torch.no_grad()
def _probe(model):
    device = next(model.parameters()).device
    ids = torch.tensor([PROBE_IDS], dtype=torch.long, device=device)
    full = model(ids, use_cache=False).logits.detach().float().cpu()
    _need(bool(torch.isfinite(full).all()), 'nonfinite initial full logits')
    current, cache, steps, tokens = ids, None, [], []
    for _ in range(PROBE_STEPS):
        result = model(current, past_key_values=cache, use_cache=True)
        cache = result.past_key_values
        logits = result.logits[:, -1].detach().float()
        _need(bool(torch.isfinite(logits).all()), 'nonfinite initial cached logits')
        steps.append(logits.cpu())
        current = logits.argmax(-1).unsqueeze(-1)
        tokens.append(current.item())
    return full, torch.stack(steps), tokens, len(cache.layers)


def expand_depth(model, *, after_layers=None, rank=64, alpha=16, test_fixture=False):
    """Expand a fresh native model transactionally; require measured exact parity."""
    _need(type(test_fixture) is bool and not model.training
          and not hasattr(model, '_nvarc_capacity_receipt') and not hasattr(model, '_capacity_receipt'),
          'fresh unexpanded evaluation-mode model required')
    _need(model.config._attn_implementation == 'sdpa', 'capacity treatment requires SDPA attention')
    base = model_contract(model.config, variant='tiny' if test_fixture else '2b', test_fixture=test_fixture)
    validate = _native_named(model)
    dtypes = {str(p.dtype) for p in validate.values()}
    devices = {p.device for p in validate.values()}
    _need(len(dtypes) == 1 and len(devices) == 1 and all(p.grad is None for p in validate.values()),
          'single-device fresh uniform base required')
    _need(all(bool(torch.isfinite(p).all()) for p in validate.values()), 'finite inherited weights required')
    _need(not test_fixture or (next(iter(devices)).type == 'cpu' and sum(p.numel() for p in validate.values()) <= 1000000),
          'bounded CPU-only synthetic fixture required')
    after = OFFICIAL_AFTER if after_layers is None else after_layers
    core = _core(base, after, rank, alpha, next(iter(dtypes)))
    before = _probe(model)
    base_hash = _digest(validate)
    old_layers, old_count, old_types = model.model.layers, model.config.num_hidden_layers, model.config.layer_types
    copies = {}
    for index in after:
        block = copy.deepcopy(old_layers[index])
        with torch.no_grad():
            block.self_attn.o_proj.weight.zero_()
            block.mlp.down_proj.weight.zero_()
        copies[index] = block
    try:
        model.model.layers = nn.ModuleList([copies[row['original_index']] if row['new']
            else old_layers[row['original_index']] for row in core['layout']])
        model.config.num_hidden_layers = len(core['layout'])
        model.config.layer_types = ['full_attention'] * len(core['layout'])
        for index, layer in enumerate(model.model.layers):
            layer.self_attn.layer_idx = index
            layer.self_attn.config = model.config
            layer.mlp.config = model.config
        after_probe = _probe(model)
        _need(torch.equal(before[0], after_probe[0]) and torch.equal(before[1], after_probe[1])
              and before[2] == after_probe[2], 'exact starting-function full/cached parity failed')
        _need(before[3] == old_count and after_probe[3] == len(core['layout']), 'actual cache depth differs')
        receipt = {**core, 'base_native_sha256': base_hash, 'expanded_native_sha256': _digest(_native_named(model)),
                   'native_buffers_sha256': _digest(dict(model.named_buffers())),
                   'initial_function': {'probe_ids': list(PROBE_IDS), 'cached_decode_steps': PROBE_STEPS,
                   'full_logits_equal': True, 'cached_logits_equal': True, 'greedy_tokens_equal': True,
                   'max_absolute_logit_difference': 0.0, 'base_cache_layers': before[3],
                   'expanded_cache_layers': after_probe[3]}}
        model._nvarc_capacity_receipt = copy.deepcopy(receipt)
        validate_capacity_base(model, receipt)
        return receipt
    except BaseException:
        model.model.layers = old_layers
        model.config.num_hidden_layers, model.config.layer_types = old_count, old_types
        for index, layer in enumerate(old_layers):
            layer.self_attn.layer_idx = index
        if hasattr(model, '_nvarc_capacity_receipt'):
            del model._nvarc_capacity_receipt
        raise


def from_base_depth(model, tokenizer, *, base_identity, after_layers=None, device=None,
                    seed=0, adapter_seed=None, rank=64, alpha=16, base_dtype=torch.bfloat16,
                    test_fixture=False, probability_policy='fp32-compact-head-v1'):
    """Use the genuine compact engine, not the tiny full-new-block fixture engine."""
    validate_tokenizer(tokenizer)
    _need(type(base_identity) is dict and base_identity, 'verified nonempty inherited base identity required')
    _canonical(base_identity)
    _need(base_dtype in (torch.bfloat16, torch.float32), 'BF16 or synthetic FP32 dtype required')
    _need(test_fixture or base_dtype == torch.bfloat16, 'official inherited weights require BF16')
    _need(all(type(value) is int and 0 <= value < 2**63 for value in
              (seed, seed if adapter_seed is None else adapter_seed)), 'bounded rollout and adapter seeds required')
    requested_device = torch.device(device or next(model.parameters()).device)
    _need(not test_fixture or requested_device.type == 'cpu', 'synthetic fixtures must stay on CPU')
    original = model_contract(model.config, variant='tiny' if test_fixture else '2b', test_fixture=test_fixture)
    _core(original, OFFICIAL_AFTER if after_layers is None else after_layers, rank, alpha, str(base_dtype))
    model.to(device=device or next(model.parameters()).device, dtype=base_dtype).eval()
    receipt = expand_depth(model, after_layers=after_layers, rank=rank, alpha=alpha, test_fixture=test_fixture)
    engine = CompactEngine.from_base(model, tokenizer, base_identity=base_identity,
        variant='tiny' if test_fixture else '2b', rank=rank, alpha=alpha, device=device,
        seed=seed, adapter_seed=adapter_seed, base_dtype=base_dtype, test_fixture=test_fixture,
        capacity_receipt=receipt, probability_policy=probability_policy)
    _need(all(not bool(torch.count_nonzero(module.lora_B['default'].weight))
              for module in engine.model.modules() if hasattr(module, 'lora_B') and 'default' in module.lora_B),
          'all inserted adapters must start with exact zero B matrices')
    validate_capacity_engine(engine)
    return engine


def load_depth_engine(path, *, device='cuda', seed=0, adapter_seed=None,
                      probability_policy='fp32-compact-head-v1'):
    """Verify every official file BEFORE local-only config/tokenizer/weight load."""
    from transformers import AutoConfig, Qwen3ForCausalLM
    path = Path(path)
    identity = verify_model(path, '2b')
    raw = json.loads((path / 'config.json').read_bytes())
    expected = model_contract(raw, variant='2b')
    config = AutoConfig.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    _need(model_contract(config, variant='2b') == expected, 'loaded official metadata differs')
    tokenizer = load_compact_tokenizer(path)
    model = Qwen3ForCausalLM.from_pretrained(path, config=config, local_files_only=True,
        trust_remote_code=False, dtype=torch.bfloat16, attn_implementation='sdpa', device_map={'': device}).eval()
    return from_base_depth(model, tokenizer, base_identity=identity, device=device, seed=seed,
                           adapter_seed=adapter_seed, probability_policy=probability_policy)


def assess_compute_match(baseline, expanded, *, declaration):
    """Validate supplied measurement receipts, never infer time from budget caps.

    Receipt validation cannot attest the runtime that produced those receipts.
    The caller must independently bind both to closed owned-worker evidence.
    Synthetic contract tests are explicitly never eligible GPU comparisons.
    Equal exclusive GPU wall is the stated resource control, NOT equal FLOPs,
    optimizer steps, memory or accuracy. Unequal physical counts stay visible.
    """
    from tools.nvarc_posttrain_20261017.matched_controls import COUNTERS
    from tools.nvarc_posttrain_20261017.materials import model_pin
    fields = {'format', 'declared_at_epoch', 'maximum_relative_wall_gap', 'shared_protocol_sha256',
              'data_admission_sha256', 'source_sha256', 'adapter_seed', 'probability_policy'}
    _need(type(declaration) is dict and set(declaration) == fields
          and declaration['format'] == 'irisx/depth-gpu-wall-declaration-v1',
          'exact prospectively sealed comparison declaration required')
    tolerance = declaration['maximum_relative_wall_gap']
    _need(type(tolerance) in (int, float) and math.isfinite(tolerance) and 0 <= tolerance <= .1,
          'predeclared relative GPU-wall tolerance in 0..0.1 required')
    _need(type(declaration['declared_at_epoch']) in (int, float)
          and math.isfinite(declaration['declared_at_epoch'])
          and type(declaration['adapter_seed']) is int and 0 <= declaration['adapter_seed'] < 2**63,
          'finite declaration time and bounded adapter seed required')
    _need(all(type(declaration[k]) is str and re.fullmatch('[0-9a-f]{64}', declaration[k])
              for k in ('shared_protocol_sha256', 'data_admission_sha256', 'source_sha256')),
          'exact shared protocol/data/source hashes required')
    _need(declaration['probability_policy'] == 'fp32-compact-head-v1', 'same admitted probability policy required')
    declaration_sha = hashlib.sha256(_canonical(declaration)).hexdigest()
    run_fields = {'format', 'treatment', 'complete', 'base_identity', 'declaration_sha256',
                  'shared_protocol_sha256', 'data_admission_sha256', 'source_sha256', 'adapter_seed',
                  'probability_policy', 'hardware_identity', 'started_at_epoch', 'physical', 'timing',
                  'evidence_kind', 'closed_evidence_sha256'}
    physical_keys = set(COUNTERS) | {'model_forward_attempts', 'model_input_tokens'}
    times = []
    reasons = []
    for run, treatment in ((baseline, 'baseline-depth28-rslora64'), (expanded, 'identity-depth32-rslora64')):
        _need(type(run) is dict and set(run) == run_fields and run['format'] == 'irisx/depth-gpu-wall-run-v1'
              and run['treatment'] == treatment and type(run['complete']) is bool,
              'exact distinct baseline/depth measured run receipts required')
        _need(run['declaration_sha256'] == declaration_sha
              and all(run[k] == declaration[k] for k in ('shared_protocol_sha256', 'data_admission_sha256',
                  'source_sha256', 'adapter_seed', 'probability_policy')),
              'paired source/data/protocol/seed/precision declaration differs')
        _need(type(run['started_at_epoch']) in (int, float) and math.isfinite(run['started_at_epoch'])
              and run['started_at_epoch'] > declaration['declared_at_epoch'],
              'declaration must predate both executions')
        _need(type(run['hardware_identity']) is str and 0 < len(run['hardware_identity']) <= 512
              and run['evidence_kind'] in ('owned-gpu-measurement', 'synthetic-contract-test')
              and type(run['closed_evidence_sha256']) is str
              and re.fullmatch('[0-9a-f]{64}', run['closed_evidence_sha256']),
              'bounded actual hardware identity and closed evidence hash required')
        physical = run['physical']
        _need(type(physical) is dict and set(physical) == physical_keys
              and all(type(n) is int and n >= 0 for n in physical.values())
              and 0 < physical['optimizer_steps'] <= physical['optimizer_attempts']
              and physical['forward_calls'] <= physical['model_forward_attempts']
              and physical['generation_forward_attempts'] <= physical['model_forward_attempts']
              and physical['generation_padding_tokens'] + physical['generation_finished_row_token_slots']
                  <= physical['generation_row_token_slots'], 'exact conserved nonnegative physical counters required')
        timing = run['timing']
        timing_keys = {'scope', 'clock', 'elapsed_seconds', 'started_monotonic', 'finished_monotonic',
                       'exclusive_device', 'synchronized_before', 'synchronized_after',
                       'failed_and_no_signal_work_included', 'idle_padding_seconds'}
        _need(type(timing) is dict and set(timing) == timing_keys
              and timing['scope'] == 'training-only-exclusive-gpu-wall'
              and timing['clock'] == 'time.monotonic', 'exact measured training-only timing schema required')
        numeric = ('elapsed_seconds', 'started_monotonic', 'finished_monotonic', 'idle_padding_seconds')
        _need(all(type(timing[k]) in (int, float) and math.isfinite(timing[k]) for k in numeric)
              and timing['elapsed_seconds'] > 0 and timing['idle_padding_seconds'] >= 0
              and math.isclose(timing['finished_monotonic'] - timing['started_monotonic'],
                               timing['elapsed_seconds'], rel_tol=1e-9, abs_tol=1e-9),
              'positive actual monotonic duration required, not a budget cap')
        for key in ('exclusive_device', 'synchronized_before', 'synchronized_after', 'failed_and_no_signal_work_included'):
            _need(type(timing[key]) is bool, 'explicit measured timing conditions required')
            if not timing[key]:
                reasons.append(treatment + ':' + key)
        if timing['idle_padding_seconds'] != 0:
            reasons.append(treatment + ':idle-padding')
        if not run['complete']:
            reasons.append(treatment + ':incomplete')
        if run['evidence_kind'] != 'owned-gpu-measurement':
            reasons.append(treatment + ':synthetic-evidence')
        times.append(timing['elapsed_seconds'])
    _need(baseline['base_identity'] == expanded['base_identity'], 'same original verified base identity required')
    identity = baseline['base_identity']
    if all(run['evidence_kind'] == 'owned-gpu-measurement' for run in (baseline, expanded)):
        official = model_pin('2b')
        _need(type(identity) is dict and all(identity.get(k) == v for k, v in official.items())
              and identity.get('material_identity_sha256') == hashlib.sha256(_canonical(official)).hexdigest()
              and identity.get('verified_parameters') == official['parameters']
              and identity.get('verified_tensors') == 311 and identity.get('remote_code_executed') is False,
              'independently verified exact official2B material receipt required')
    if baseline['hardware_identity'] != expanded['hardware_identity']:
        reasons.append('hardware-mismatch')
    relative_gap = abs(times[1] - times[0]) / max(times)
    if relative_gap > tolerance:
        reasons.append('measured-wall-gap-exceeds-declared-tolerance')
    return {'eligible': not reasons, 'compute_matched': not reasons,
            'match_basis': 'exclusive synchronized measured training GPU wall, not FLOPs',
            'relative_wall_gap': relative_gap, 'maximum_relative_wall_gap': tolerance,
            'baseline_seconds': times[0], 'expanded_seconds': times[1], 'reasons': reasons,
            'declaration_sha256': declaration_sha,
            'physical_counters_equal': baseline['physical'] == expanded['physical'],
            'physical': {'baseline': copy.deepcopy(baseline['physical']), 'expanded': copy.deepcopy(expanded['physical'])},
            'measurement_authenticity_independently_verified': False,
            'effectiveness_established': False, 'flops_matched': False,
            'limitation': 'Receipt consistency only; independently audit closed runtime evidence before a scientific claim.'}

"""Source-derived compact width-v1, separate from the BF16 depth-v1 receipt.

Official source + zero-B rsLoRA are initialized by the unchanged CompactEngine
in BF16, then exactly promoted by fp32-backbone-math-v1. Only then are all frozen
FFNs widened by paired antisymmetric up perturbations and split down columns. No shared engine contract changes.
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

FORMAT = 'irisx/compact-width-fp32-v1'
TREATMENTS = ('initial_anchor', 'baseline', 'width8192')
LAYERS = tuple(range(28))
from .expansion import WIDTH, CONSTRUCTION, widen_mlp


def _need(value, message):
    if not value:
        raise ValueError(message)


def accounting(base, treatment, *, rank=64, layers=None, target_width=None):
    """Exact dense width geometry; active linear work rises, not equal compute."""
    _need(treatment in TREATMENTS, 'explicit baseline/width8192 treatment required')
    n, h, inter = (base[k] for k in ('num_hidden_layers','hidden_size','intermediate_size'))
    target = WIDTH if target_width is None else target_width
    _need(type(target) is int and inter < target <= 2 * inter, 'bounded larger FFN width required')
    _need(layers is None or tuple(layers) in ((), tuple(range(n))), 'all original FFNs or baseline required')
    q, kv = base['num_attention_heads'] * base['head_dim'], base['num_key_value_heads'] * base['head_dim']
    native = sum(math.prod(shape) for shape in _geometry(base).values())
    attention = 2*h*q + 2*h*kv
    actual = target if treatment == 'width8192' else inter
    extra = n*3*h*(actual-inter)
    trainable = n*rank*(2*(h+q)+2*(h+kv)+3*(h+actual)) + 32*h
    total = native + extra + trainable
    linear = n*(attention+3*h*actual + rank*(2*(h+q)+2*(h+kv)+3*(h+actual))) + 16*h
    return {'source_native_parameters':native,'added_native_parameters':extra,
        'frozen_parameters':native+extra,'trainable_parameters':trainable,
        'total_resident_parameters':total,'potentially_active_parameters_per_token':total-32*h,
        'resident_parameter_bytes_fp32':total*4,'router_parameters':0,
        'layers':n,'selected_original_layers':list(range(n)) if treatment == 'width8192' else [],
        'source_intermediate_size':inter,'actual_intermediate_size':actual,
        'linear_forward_flops_per_token':2*linear,
        'flops_kind':'analytic linear forward only; excludes quadratic attention/backward/recompute/optimizer',
        'equal_compute_claimed':False,'actual_wall_seconds':None,'actual_peak_memory_bytes':None}


def official_accounting(treatment):
    # Geometry only: do not import Linux-owned controller/process machinery in
    # this portable model helper. Runtime config admission remains unchanged.
    from tools.nvarc_posttrain_20261017.engine import OFFICIAL_SHAPES
    return accounting(OFFICIAL_SHAPES['2b'], treatment)


def _inventory(model):
    return {name: {'shape': list(p.shape), 'dtype': str(p.dtype)}
            for name, p in sorted(model.named_parameters()) if p.requires_grad}


def _numerics(model):
    result = _module_numerics(model)
    for name, module in model.named_modules():
        for key in ('attention_scaling', 'rope_type', 'max_seq_len_cached', 'original_max_seq_len',
                    'in_features','out_features','hidden_size','intermediate_size','r','lora_alpha'):
            if hasattr(module, key):
                result.setdefault(name, {})[key] = copy.deepcopy(getattr(module, key))
    return result


class WidthEngine(CompactEngine):
    """Width-v1 inventory with unchanged compact safety/update/generation/I/O.

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
              and self.source_base_dtype == torch.bfloat16, 'width-v1 exact source/resident policy required')
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
            if hasattr(module, 'lora_A') and 'default' in module.lora_A:
                _need(module.scaling['default'] == self.trainable_inventory['alpha'] /
                      math.sqrt(self.trainable_inventory['rank']) and module.active_adapter == ['default']
                      and not module.disable_adapters and not module.merged
                      and isinstance(module.lora_dropout['default'], nn.Identity),
                      'active rsLoRA policy changed')
        if check_values:
            _need(_digest(frozen) == self.contract['width_v1']['frozen_native_sha256'],
                  'capacity frozen native content changed')
            _need(_digest(dict(self.model.named_buffers())) == self.contract['width_v1']['buffers_sha256'],
                  'capacity RoPE/native buffers changed')
            _need(all(bool(torch.isfinite(p).all()) for p in trainables.values()), 'nonfinite capacity trainable')

    def commit(self, optimizer):
        self._structure_admission()
        result = super().commit(optimizer)
        self._structure_admission()
        return result

    def dispatch_receipt(self):
        return {}  # Every widened channel executes; no sparse/router mechanism.


def from_dense(engine, treatment, *, fixture_width=None):
    """Consume a pristine source-promoted engine; reject used/nonzero-B state.

    Fresh PEFT tensors are mapped explicitly, not reinitialized through a changed
    traversal. No optimizer, trained adapter or cache state is reused. Failure
    invalidates the consumed engine; callers must abort that arm, never retry it.
    """
    _need(type(engine) is CompactEngine and engine.capacity_receipt is None,
          'fresh ordinary dense CompactEngine required')
    engine._checkpoint_admission()
    _need(engine.probability_policy == FP32_BACKBONE_POLICY and not engine._checkpoint_loaded
          and not engine.optimizer_attempts and not engine.optimizer_steps and not engine.forward_calls
          and all(p.grad is None for p in engine.model.parameters()), 'unused FP32/math engine required')
    _need(all(not bool(m.lora_B['default'].weight.count_nonzero()) for m in engine.model.modules()
              if hasattr(m, 'lora_B') and 'default' in m.lora_B), 'exact zero-B adapters required')
    base = copy.deepcopy(engine.contract)
    tiny = base['variant'] == 'tiny'
    _need(base['variant'] in ('tiny','2b') and (fixture_width is None or tiny),
          'official2B only; custom width is CPU-fixture-only')
    _need(not tiny or engine.device.type == 'cpu', 'tiny fixture cannot claim GPU admission')
    target = (base['intermediate_size'] + base['intermediate_size']//3 if tiny else WIDTH) if fixture_width is None else fixture_width
    counts = accounting(base,treatment,rank=engine.trainable_inventory['rank'],target_width=target)
    model, raw = engine.model, engine.model.get_base_model()
    inherited = dict(model.named_parameters())
    inherited_digest = _digest(inherited)
    untouched_digest = _digest({n:p for n,p in inherited.items() if '.mlp.' not in n})
    shapes = {n:tuple(p.shape) for n,p in inherited.items()}
    train_shapes = {n:tuple(p.shape) for n,p in inherited.items() if p.requires_grad}
    del inherited
    with full_precision_compute(engine.device.type):
        model.eval(); before = _probe(model)
    layout = [{'index':i,'original_index':i,'new':False} for i in range(base['num_hidden_layers'])]
    expansions = []
    try:
        if treatment == 'width8192':
            for index,layer in enumerate(raw.model.layers):
                expansions.append(widen_mlp(layer.mlp,target,layer_index=index))
            for name,shape in list(shapes.items()):
                if '.mlp.' not in name: continue
                changed = list(shape)
                if name.endswith(('gate_proj.base_layer.weight','up_proj.base_layer.weight',
                                  'gate_proj.lora_B.default.weight','up_proj.lora_B.default.weight')):
                    changed[0] = target
                elif name.endswith(('down_proj.base_layer.weight','down_proj.lora_A.default.weight')):
                    changed[1] = target
                shapes[name] = tuple(changed)
                if name in train_shapes: train_shapes[name] = tuple(changed)
        model.config.intermediate_size = counts['actual_intermediate_size']
        install_checkpoint_policy(model,FP32_BACKBONE_POLICY)
        named = dict(model.named_parameters())
        _need(_digest({n:p for n,p in named.items() if '.mlp.' not in n}) == untouched_digest,
              'non-FFN source/adapter bytes changed')
        if treatment != 'width8192':
            _need(_digest(named) == inherited_digest, 'unchanged dense initialization bytes changed')
        _need(set(named) == set(shapes) and all(tuple(named[n].shape)==shape for n,shape in shapes.items()),
              'actual expanded geometry differs')
        _need({n for n,p in named.items() if p.requires_grad} == set(train_shapes), 'actual trainable scope differs')
        _need(sum(p.numel() for p in named.values()) == counts['total_resident_parameters']
              and sum(p.numel() for p in named.values() if p.requires_grad) == counts['trainable_parameters'],
              'actual expanded parameter accounting differs')
        with full_precision_compute(engine.device.type):
            model.eval(); after = _probe(model)
        gap = max((before[0]-after[0]).abs().max().item(),(before[1]-after[1]).abs().max().item())
        limit = 0. if treatment != 'width8192' else 1e-5 if tiny else 1e-4
        _need(math.isfinite(gap) and gap <= limit and before[2] == after[2],
              'short initial full/cached function preservation probe failed')
        _need(after[3] == len(layout), 'KV cache layout differs')
        receipt = {'format':FORMAT,'treatment':treatment,'base_model_contract':base,
            'layout':layout,'selected_original_layers':counts['selected_original_layers'],
            'probability_policy':FP32_BACKBONE_POLICY,'source_base_dtype':'torch.bfloat16',
            'resident_dtype':'torch.float32','adapter_seed':engine.adapter_seed,
            'construction':{**copy.deepcopy(CONSTRUCTION),'target_intermediate_size':target} if treatment == 'width8192' else None,
            'expansions':expansions,
            'inherited_source_and_adapter_sha256':inherited_digest,
            'untouched_non_FFN_source_and_adapter_sha256':untouched_digest,
            'frozen_native_sha256':_digest({n:p for n,p in named.items() if not p.requires_grad}),
            'buffers_sha256':_digest(dict(model.named_buffers())),'accounting':counts,
            'initial_function_contract':{'predeclared_max_absolute_logit_gap':limit,
                'greedy_tokens_equal_required':True,'probe_tokens':13,'cached_steps':4,
                'full_context_admitted':False,'probability_gate_unchanged':.05 if not tiny else 1e-5},
            'optimizer_reuse_allowed':False,'native_weights_trainable':False,
            'router_trainable':False,'router_auxiliary_loss':None,
            'requires_full_workload_gpu_validation':True,'capability_gain_established':False}
        result = object.__new__(WidthEngine)
        result.__dict__.update(engine.__dict__)
        result.treatment = treatment
        result.last_router_gradient_norms = {}
        # Measured last-bit differences are evidence, not reconstruction identity:
        # a different admitted device can round the same larger GEMM slightly
        # differently without changing any tensor bytes or checkpoint contract.
        result.initial_function_receipt = {
            **receipt['initial_function_contract'], 'full_and_cached_max_absolute_logit_gap': gap,
            'greedy_tokens_equal': True, 'exact_bitwise_preservation': gap == 0.,
            'actual_device_type': engine.device.type}
        result.contract = {**base, 'intermediate_size': counts['actual_intermediate_size'], 'width_v1': receipt}
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
        return result
    except BaseException:
        engine._fatal_update = True
        raise


def load_engine(path, treatment='baseline', *, device='cuda', seed=20261018, adapter_seed=731):
    """Only exact locally verified official2B SFT141; no ReArc or remote loads."""
    identity = verify_model(path, '2b')
    engine = CompactEngine.load(path, base_identity=identity, variant='2b', device=device,
        seed=seed, adapter_seed=adapter_seed, probability_policy=FP32_BACKBONE_POLICY)
    return from_dense(engine, treatment)


def probability_admission(engine, prompt_ids, *, deadline, max_new_tokens=32):
    """Distinct width-v1 no-update sampled-versus-full preflight for SFT.

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
    _need(type(engine) is WidthEngine, 'explicit width-v1 engine required')
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
    result = {'format': 'irisx/width-sampled-full-admission-v1', 'passed': False,
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

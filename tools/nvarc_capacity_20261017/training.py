"""CPU-tiny-only depth post-training bridge, not a production expanded model.

The frozen PEFT engine constructor/checkpoint contract is not weakened. This
separate engine owns full new blocks plus compact heads, and reuses only its
reviewed numerical sampling/update methods. No provider, model loader, dataset,
checkpoint promotion, or accuracy claim exists here.
"""
from __future__ import annotations

import copy
import math

import torch

from tools.arc2_goal_sprint_20261017.model import (
    Engine, adapter_state, check_deadline, restore_state, state_digest,
)
from tools.nvarc_posttrain_20261017.engine import (
    CompactEngine, FatalUpdateError, validate_tokenizer,
)
from .prototype import count_parameters, train_only_new_depth

MAX_FIXTURE_PARAMETERS = 1_000_000


def _validate_fixture(model, receipt):
    """Validate actual native tensor geometry before changing any training flags."""
    from transformers import Qwen3ForCausalLM
    if type(model) is not Qwen3ForCausalLM or model.training:
        raise ValueError('Bare evaluation-mode Qwen3 depth fixture required')
    c = model.config
    dimensions = (c.hidden_size, c.intermediate_size, c.num_hidden_layers,
                  c.num_attention_heads, c.num_key_value_heads, c.head_dim)
    if (any(type(n) is not int or n <= 0 for n in dimensions)
            or c.model_type != 'qwen3' or c.vocab_size != 16
            or c.tie_word_embeddings is not False or c.attention_bias is not False
            or c.attention_dropout != 0 or c.hidden_act != 'silu'
            or c.bos_token_id != 13 or c.eos_token_id != 15
            or c.layer_types != ['full_attention'] * c.num_hidden_layers
            or len(model.model.layers) != c.num_hidden_layers
            or c.num_attention_heads % c.num_key_value_heads):
        raise ValueError('Untied dropout-zero full-attention compact Qwen3 required')
    named = dict(model.named_parameters())
    unshared = list(model.named_parameters(remove_duplicate=False))
    if (len(unshared) != len(named)
            or len({p.untyped_storage().data_ptr() for p in named.values()}) != len(named)):
        raise ValueError('Independent untied parameter storage required')
    h, intermediate, q, kv = (c.hidden_size, c.intermediate_size,
                              c.num_attention_heads * c.head_dim,
                              c.num_key_value_heads * c.head_dim)
    expected = {'model.embed_tokens.weight': (16, h), 'lm_head.weight': (16, h),
                'model.norm.weight': (h,)}
    projections = {'self_attn.q_proj': (q, h), 'self_attn.k_proj': (kv, h),
        'self_attn.v_proj': (kv, h), 'self_attn.o_proj': (h, q),
        'self_attn.q_norm': (c.head_dim,), 'self_attn.k_norm': (c.head_dim,),
        'mlp.gate_proj': (intermediate, h), 'mlp.up_proj': (intermediate, h),
        'mlp.down_proj': (h, intermediate), 'input_layernorm': (h,),
        'post_attention_layernorm': (h,)}
    for index, layer in enumerate(model.model.layers):
        if (type(layer).__name__ != 'Qwen3DecoderLayer'
                or type(layer.mlp).__name__ != 'Qwen3MLP'
                or layer.self_attn.config is not c or layer.mlp.config is not c
                or layer.self_attn.layer_idx != index or layer.self_attn.attention_dropout != 0):
            raise ValueError('Native dropout-zero indexed depth blocks required')
        expected.update({f'model.layers.{index}.{name}.weight': shape
                         for name, shape in projections.items()})
    if set(named) != set(expected) or any(tuple(named[n].shape) != shape for n, shape in expected.items()):
        raise ValueError('Exact native compact-head and block parameter geometry required')
    if any(not bool(torch.isfinite(p).all()) for p in named.values()):
        raise ValueError('Finite inherited and newly added parameters required')
    if any(b.device.type != 'cpu' or not bool(torch.isfinite(b).all()) for b in model.buffers()):
        raise ValueError('Finite CPU model buffers required')
    layout = receipt.get('layout') if isinstance(receipt, dict) else None
    if (receipt != getattr(model, '_capacity_receipt', None)
            or not isinstance(layout, list) or len(layout) != len(model.model.layers)
            or receipt.get('parameters') != count_parameters(model)):
        raise ValueError('Matching complete live depth receipt required')
    original, added = -1, []
    for index, row in enumerate(layout):
        if not isinstance(row, dict) or type(row.get('new')) is not bool:
            raise ValueError('Exact depth layout required')
        if not row['new']:
            original += 1
        elif index == 0 or layout[index - 1]['new']:
            raise ValueError('New depth block must immediately follow its original')
        if row != {'index': index, 'original_index': original, 'new': row['new']}:
            raise ValueError('Exact depth layout required')
        if row['new']:
            added.append(index)
            block = model.model.layers[index]
            if any(bool(torch.count_nonzero(p.weight)) for p in (block.self_attn.o_proj, block.mlp.down_proj)):
                raise ValueError('Fresh function-preserving zero-output depth initialization required')
    if (not added or receipt.get('added_layers') != added
            or receipt.get('base_parameters') != count_parameters(model) - sum(
                count_parameters(model.model.layers[i]) for i in added)):
        raise ValueError('Exact added-block and inherited parameter counts required')


def _module_numerics(model):
    """Bind mutable non-parameter settings used by native attention and RMSNorm."""
    keys = ('layer_idx', 'attention_dropout', 'head_dim', 'num_key_value_groups',
            'scaling', 'is_causal', 'sliding_window', 'variance_epsilon')
    return {name: {key: copy.deepcopy(getattr(module, key)) for key in keys if hasattr(module, key)}
            for name, module in model.named_modules()}


class DepthFixtureEngine(Engine):
    """Explicit experimental full-block contract; never impersonates PEFT."""

    def __init__(self, model, tokenizer, receipt, *, fixture_only, seed=0):
        if fixture_only is not True or count_parameters(model) > MAX_FIXTURE_PARAMETERS:
            raise ValueError('Only bounded CPU tiny fixtures are admitted; official/GPU models are not')
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError('Explicit bounded fixture sampling seed required')
        if any(p.device.type != 'cpu' or p.grad is not None for p in model.parameters()):
            raise ValueError('Fresh CPU model without pending gradients required')
        dtypes = {p.dtype for p in model.parameters()}
        if len(dtypes) != 1 or next(iter(dtypes)) not in (torch.float32, torch.bfloat16):
            raise ValueError('Uniform FP32 or BF16 inherited fixture required')
        _validate_fixture(model, receipt)
        token_admission = validate_tokenizer(tokenizer)
        base_dtype = next(iter(dtypes))
        # This validates the actual live model/receipt/layout before flags change.
        trainables = train_only_new_depth(model, receipt, include_compact_heads=True)
        intended = {name for name, _ in model.named_parameters() if name in {
            'model.embed_tokens.weight', 'lm_head.weight'} or any(
                name.startswith(f'model.layers.{index}.') for index in receipt['added_layers'])}
        actual = {name for name, value in model.named_parameters() if value.requires_grad}
        if not intended or actual != intended:
            raise ValueError('Full new-block and compact-head inventory differs')
        for value in model.parameters():
            if value.requires_grad:
                value.data = value.data.float()
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        model.enable_input_require_grads()
        super().__init__(model, tokenizer, device='cpu')
        # The fixture reuses the actual sampler, including its physical-work
        # accounting. This is not a production loader or capacity promotion.
        self.generation_forward_attempts = 0
        self.generation_input_tokens = 0
        self.generation_row_token_slots = 0
        self.generation_finished_row_token_slots = 0
        self.generation_padding_tokens = 0
        self.base_dtype = base_dtype
        self.generator = torch.Generator(device='cpu').manual_seed(seed)
        self._fatal_update = False
        self._receipt = copy.deepcopy(receipt)
        self._layout = tuple(id(layer) for layer in model.model.layers)
        self._owned = dict(model.named_parameters())
        self._modules = {name: id(module) for name, module in model.named_modules()}
        self._config = copy.deepcopy(model.config.to_dict())
        self._attention_backend = model.config._attn_implementation
        self._module_numerics = _module_numerics(model)
        self._buffers = {name: (id(value), value.detach().clone()) for name, value in model.named_buffers()}
        self._tokenizer_admission = token_admission
        self._inventory = {name: (id(value), tuple(value.shape)) for name, value in model.named_parameters() if value.requires_grad}
        self._frozen = {name: value.detach().clone() for name, value in model.named_parameters() if not value.requires_grad}
        self._frozen_digest = state_digest(self._frozen)
        self.base_identity = {'synthetic_fixture': True, 'capacity': 'identity-depth',
                              'inherited_frozen_state_sha256': self._frozen_digest}
        self.contract = {'format': 'irisx/cpu-depth-training-fixture-v1',
            'trainables': trainables, 'trainable_dtype': 'torch.float32',
            'frozen_dtype': str(base_dtype), 'added_layers': list(receipt['added_layers']),
            'tokenizer': token_admission, 'production_validated': False,
            'gpu_admitted': False, 'capability_gain_claimed': False, 'equal_compute_claimed': False}
        self._healthy()

    @classmethod
    def load(cls, *args, **kwargs):
        raise ValueError('No production loader or GPU admission exists for this CPU fixture bridge')

    def _healthy(self):
        if self._fatal_update:
            raise FatalUpdateError('Poisoned depth fixture; optimizer/RNG cannot be resumed')
        named = dict(self.model.named_parameters())
        buffers = dict(self.model.named_buffers())
        try:
            config_ok = (self._config == self.model.config.to_dict()
                and self._attention_backend == self.model.config._attn_implementation
                and self._module_numerics == _module_numerics(self.model)
                and self._tokenizer_admission == validate_tokenizer(self.tokenizer))
        except (AttributeError, TypeError, ValueError):
            config_ok = False
        trainable = {name: p for name, p in named.items() if p.requires_grad}
        frozen = {name: p for name, p in named.items() if not p.requires_grad}
        valid = (config_ok
            and self._modules == {name: id(module) for name, module in self.model.named_modules()}
            and len(list(self.model.named_parameters(remove_duplicate=False))) == len(named)
            and len({p.untyped_storage().data_ptr() for p in named.values()}) == len(named)
            and {id(p) for p in self.parameters} == {row[0] for row in self._inventory.values()}
            and len(self.parameters) == len(self._inventory)
            and set(buffers) == set(self._buffers)
            and all(id(b) == self._buffers[n][0] and b.device.type == 'cpu'
                    and b.dtype == self._buffers[n][1].dtype
                    and torch.equal(b, self._buffers[n][1]) for n, b in buffers.items())
            and self._receipt == getattr(self.model, '_capacity_receipt', None)
            and self._layout == tuple(id(layer) for layer in self.model.model.layers)
            and set(trainable) == set(self._inventory) and set(frozen) == set(self._frozen)
            and state_digest(frozen) == self._frozen_digest
            and all(id(p) == self._inventory[name][0] and tuple(p.shape) == self._inventory[name][1]
                    and p.dtype == torch.float32 and p.device.type == 'cpu'
                    and bool(torch.isfinite(p).all()) for name, p in trainable.items())
            and all(p is self._owned[name] and p.grad is None
                    and p.device.type == 'cpu' and p.dtype == self.base_dtype
                    and torch.equal(p, self._frozen[name]) for name, p in frozen.items()))
        if not valid:
            self._fatal_update = True
            raise FatalUpdateError('Depth fixture live inventory, frozen bytes, dtype, config or layout changed')

    # Reuse compact token validation, literal EOS15/full16 sampling and finite
    # rollback numerics, not the incompatible PEFT constructor/export contract.
    _tokens = CompactEngine._tokens
    autocast = CompactEngine.autocast
    _generate_batch = CompactEngine._generate_batch
    generate = CompactEngine.generate
    generate_prompts = CompactEngine.generate_prompts

    def completion_logps(self, ids, prompt_length):
        self._healthy(); self._tokens(ids)
        return super().completion_logps(ids, prompt_length)

    def masked_logps(self, ids, mask):
        self._healthy(); self._tokens(ids)
        return super().masked_logps(ids, mask)

    def _validate_optimizer(self, optimizer):
        supplied = [p for group in optimizer.param_groups for p in group['params']]
        if len(supplied) != len(self.parameters) or {id(p) for p in supplied} != {id(p) for p in self.parameters}:
            raise ValueError('Optimizer must own exact new blocks/heads, never inherited weights')

    def _rollback_bytes(self, before):
        with torch.no_grad():
            for name, value in {**self._frozen, **before}.items():
                self._owned[name].copy_(value)
            for name, (_, value) in self._buffers.items():
                dict(self.model.named_buffers())[name].copy_(value)
        if any(not torch.equal(self._owned[n], v) for n, v in {**self._frozen, **before}.items()):
            raise RuntimeError('Parameter byte rollback did not verify')

    def commit(self, optimizer):
        self._healthy()
        self._validate_optimizer(optimizer)
        before, committed = adapter_state(self.model), self.optimizer_steps
        try:
            report = CompactEngine.commit(self, optimizer)
            self._healthy()
            return report
        except BaseException as error:
            self._fatal_update = True
            self.optimizer_steps = committed
            try:
                self._rollback_bytes(before)
                optimizer.zero_grad(set_to_none=True)
            except BaseException as rollback_error:
                raise FatalUpdateError('Update failed; rollback incomplete; abort fixture') from rollback_error
            raise FatalUpdateError('Update failed; parameter bytes restored; optimizer/RNG not resumed') from error

    def sft_step(self, example, optimizer, *, deadline=math.inf):
        self._healthy()
        self._validate_optimizer(optimizer)
        try:
            result = super().sft_step(example, optimizer, deadline=deadline)
        except BaseException:
            optimizer.zero_grad(set_to_none=True)
            raise
        check_deadline(deadline)
        return result

    def af3_update(self, rows, optimizer, *, expected_groups, group_size, deadline=math.inf):
        self._healthy()
        self._validate_optimizer(optimizer)
        check_deadline(deadline)
        result = super().af3_update(rows, optimizer, expected_groups=expected_groups,
                                    group_size=group_size, deadline=deadline)
        check_deadline(deadline)
        return result

    def snapshot(self):
        self._healthy()
        return adapter_state(self.model)

    def restore(self, state):
        self._healthy()
        # Validate and clone all input before changing parameters or gradients.
        if not isinstance(state, dict) or set(state) != set(self._inventory):
            raise ValueError('Exact depth trainable snapshot inventory required')
        for name, value in state.items():
            if (type(value) is not torch.Tensor or value.device.type != 'cpu'
                    or value.layout != torch.strided or value.dtype != torch.float32
                    or tuple(value.shape) != self._inventory[name][1]
                    or not bool(torch.isfinite(value).all())):
                raise ValueError('Finite CPU FP32 snapshot tensors with exact shapes required')
        prepared = {name: value.detach().clone() for name, value in state.items()}
        before = adapter_state(self.model)
        try:
            restore_state(self.model, prepared)
            if state_digest(self.snapshot()) != state_digest(prepared):
                raise RuntimeError('Exact depth trainable restoration failed')
        except BaseException as error:
            self._fatal_update = True
            try:
                self._rollback_bytes(before)
            except BaseException as rollback_error:
                raise FatalUpdateError('Snapshot restore failed; rollback incomplete; abort fixture') from rollback_error
            raise FatalUpdateError('Snapshot restore failed; parameter bytes restored; abort fixture') from error
        # Restoration is parameters only, never an optimizer/RNG continuation.
        for parameter in self.parameters:
            parameter.grad = None

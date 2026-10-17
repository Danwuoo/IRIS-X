"""CPU-only capacity-initialization experiments, not a production NVARC engine.

These transforms add untrained capacity. They do not change the running dual-
specialist source, erase inherited exposure, load data or claim capability gains.
All existing KV caches/optimizers must be discarded after transformation.
"""
from __future__ import annotations

import copy
import uuid

import torch
from torch import nn

MAX_ADDED_PARAMETERS = 512_000_000


def count_parameters(model):
    return sum(p.numel() for p in model.parameters())


def _admit(model):
    from transformers import Qwen3ForCausalLM
    if type(model) is not Qwen3ForCausalLM or model.training:
        raise ValueError("bare evaluation-mode Qwen3 model required")
    if getattr(model, "_capacity_receipt", None) is not None:
        raise ValueError("one transform per fresh model; composition is not admitted")
    c = model.config
    if (c.model_type != "qwen3" or c.vocab_size != 16 or c.tie_word_embeddings
            or c.hidden_act != "silu" or c.attention_dropout != 0
            or c.attention_bias or len(model.model.layers) != c.num_hidden_layers
            or c.layer_types != ["full_attention"] * c.num_hidden_layers):
        raise ValueError("dropout-zero full-attention SwiGLU Qwen3 required")
    if any(p.device.type != "cpu" or p.grad is not None for p in model.parameters()):
        raise ValueError("CPU-only fresh model without pending gradients required")
    if any(not bool(torch.isfinite(p).all()) for p in model.parameters()):
        raise ValueError("finite inherited parameters required")
    if any(type(layer.mlp).__name__ != "Qwen3MLP" for layer in model.model.layers):
        raise ValueError("unexpanded native FFNs required")
    return count_parameters(model)


def _budget(added, before):
    if not 0 < added <= min(MAX_ADDED_PARAMETERS, before):
        raise ValueError("bounded added parameter budget exceeded before allocation")


def _bind(model, receipt):
    receipt["local_instance_id"] = str(uuid.uuid4())
    model._capacity_receipt = copy.deepcopy(receipt)
    model._capacity_layers = tuple(id(layer) for layer in model.model.layers)
    return receipt


def _fresh_scope(model, receipt, kind):
    if (not isinstance(receipt, dict) or receipt.get("kind") != kind
            or receipt != getattr(model, "_capacity_receipt", None)
            or tuple(id(layer) for layer in model.model.layers) != getattr(model, "_capacity_layers", None)):
        raise ValueError("matching live transformed model and immutable receipt required")
    if any(p.grad is not None or p.device.type != "cpu" for p in model.parameters()):
        raise ValueError("fresh CPU training scope without pending gradients required")


def expand_identity_depth(model, *, after_layers):
    """Insert copied identity residual blocks after zero-indexed original layers."""
    before = _admit(model)
    after = tuple(after_layers)
    old = list(model.model.layers)
    if (not after or any(type(i) is not int or not 0 <= i < len(old) for i in after)
            or tuple(sorted(set(after))) != after):
        raise ValueError("unique increasing original layer indices required")
    _budget(sum(count_parameters(old[i]) for i in after), before)
    # Build every new block before changing the model's layout or configuration.
    copies = {}
    for i in after:
        block = copy.deepcopy(old[i])
        with torch.no_grad():
            for projection in (block.self_attn.o_proj, block.mlp.down_proj):
                projection.weight.zero_()
                if projection.bias is not None:
                    projection.bias.zero_()
        copies[i] = block
    expanded, layout, added = [], [], []
    for i, layer in enumerate(old):
        layout.append({"index": len(expanded), "original_index": i, "new": False})
        expanded.append(layer)
        if i in copies:
            added.append(len(expanded))
            layout.append({"index": len(expanded), "original_index": i, "new": True})
            expanded.append(copies[i])
    model.model.layers = nn.ModuleList(expanded)
    model.config.num_hidden_layers = len(expanded)
    model.config.layer_types = ["full_attention"] * len(expanded)
    for i, layer in enumerate(expanded):
        layer.self_attn.layer_idx = i
        layer.self_attn.config = model.config
        layer.mlp.config = model.config
    model.eval()
    return _bind(model, {"kind": "identity-depth", "base_parameters": before,
        "parameters": count_parameters(model), "added_layers": added, "layout": layout,
        "cache_and_optimizer_reuse_allowed": False, "capability_gain_established": False})


def train_only_new_depth(model, receipt, *, include_compact_heads=True):
    _fresh_scope(model, receipt, "identity-depth")
    if (len(receipt["layout"]) != len(model.model.layers)
            or receipt["added_layers"] != [r["index"] for r in receipt["layout"] if r["new"]]
            or any(type(i) is not int or not 0 <= i < len(model.model.layers)
                   for i in receipt["added_layers"])):
        raise ValueError("complete validated depth layout required before changing training scope")
    model.requires_grad_(False)
    for index in receipt["added_layers"]:
        model.model.layers[index].requires_grad_(True)
    if include_compact_heads:
        model.get_input_embeddings().requires_grad_(True)
        model.get_output_embeddings().requires_grad_(True)
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


class ParallelFFNUnits(nn.Module):
    """Exactly inherited FFN plus new SwiGLU units with zero output columns.

    Separate tensors make freezing old units genuine, including weight decay.
    Folding into native wide matrices is a separate, numerically checked step.
    """
    def __init__(self, original, units, *, std):
        super().__init__()
        self.original = original
        self.extra_units = units
        weight = original.up_proj.weight
        kwargs = {"device": weight.device, "dtype": weight.dtype, "bias": False}
        hidden = weight.shape[1]
        self.gate_proj = nn.Linear(hidden, units, **kwargs)
        self.up_proj = nn.Linear(hidden, units, **kwargs)
        self.down_proj = nn.Linear(units, hidden, **kwargs)
        with torch.no_grad():
            self.gate_proj.weight.normal_(std=std)
            self.up_proj.weight.normal_(std=std)
            self.down_proj.weight.zero_()

    def forward(self, x):
        return self.original(x) + self.down_proj(
            self.original.act_fn(self.gate_proj(x)) * self.up_proj(x))


def expand_ffn_width(model, *, intermediate_size, seed=0):
    before = _admit(model)
    old_size = model.config.intermediate_size
    if type(intermediate_size) is not int or intermediate_size <= old_size:
        raise ValueError("strictly larger integer intermediate width required")
    units = intermediate_size - old_size
    _budget(len(model.model.layers) * 3 * model.config.hidden_size * units, before)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        replacements = [ParallelFFNUnits(layer.mlp, units, std=model.config.initializer_range)
                        for layer in model.model.layers]
    for layer, replacement in zip(model.model.layers, replacements):
        layer.mlp = replacement
    model.config.intermediate_size = intermediate_size
    model.eval()
    return _bind(model, {"kind": "ffn-only-width", "base_parameters": before,
        "parameters": count_parameters(model), "old_intermediate_size": old_size,
        "intermediate_size": intermediate_size, "cache_and_optimizer_reuse_allowed": False,
        "native_checkpoint_ready": False, "capability_gain_established": False})


def train_only_new_width(model, *, include_compact_heads=True):
    _fresh_scope(model, getattr(model, "_capacity_receipt", None), "ffn-only-width")
    if not all(isinstance(layer.mlp, ParallelFFNUnits) for layer in model.model.layers):
        raise ValueError("parallel new-unit FFNs required")
    model.requires_grad_(False)
    for layer in model.model.layers:
        for name in ("gate_proj", "up_proj", "down_proj"):
            getattr(layer.mlp, name).requires_grad_(True)
    if include_compact_heads:
        model.get_input_embeddings().requires_grad_(True)
        model.get_output_embeddings().requires_grad_(True)
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def fold_width_to_native(model):
    """CPU export transform; caller must validate numerical parity before saving."""
    from transformers.models.qwen3.modeling_qwen3 import Qwen3MLP
    _fresh_scope(model, getattr(model, "_capacity_receipt", None), "ffn-only-width")
    if not all(isinstance(layer.mlp, ParallelFFNUnits) for layer in model.model.layers):
        raise ValueError("all FFNs must be new-unit wrappers")
    replacements = []
    for layer in model.model.layers:
        wrapper = layer.mlp
        weight = wrapper.original.up_proj.weight
        target = Qwen3MLP(model.config).to(device=weight.device, dtype=weight.dtype)
        with torch.no_grad():
            for name in ("gate_proj", "up_proj"):
                getattr(target, name).weight.copy_(torch.cat([
                    getattr(wrapper.original, name).weight, getattr(wrapper, name).weight], dim=0))
            target.down_proj.weight.copy_(torch.cat([
                wrapper.original.down_proj.weight, wrapper.down_proj.weight], dim=1))
        replacements.append(target)
    for layer, replacement in zip(model.model.layers, replacements):
        layer.mlp = replacement
    model.eval()
    return {"kind": "native-wide-export", "numerical_parity_must_be_checked": True,
            "training_scope_must_be_reconfigured": True, "capability_gain_established": False}


class TwoExpertRoutingControl(nn.Module):
    """Tiny CPU mechanism control, not a performant production MoE implementation."""
    def __init__(self, original, *, routing):
        super().__init__()
        if routing not in {"normalized-top1", "unnormalized-top1", "soft-top2"}:
            raise ValueError("explicit supported routing rule required")
        if next(original.parameters()).device.type != "cpu":
            raise ValueError("CPU-only mechanism control")
        if count_parameters(original) > 1_000_000:
            raise ValueError("tiny FFN mechanism control only, not a model converter")
        self.experts = nn.ModuleList([copy.deepcopy(original), copy.deepcopy(original)])
        self.routing = routing
        weight = original.up_proj.weight
        self.router = nn.Linear(weight.shape[1], 2, bias=False, device=weight.device, dtype=weight.dtype)
        nn.init.zeros_(self.router.weight)

    def forward(self, x):
        if x.device.type != "cpu" or x.numel() // x.shape[-1] > 512:
            raise ValueError("bounded CPU mechanism inputs required")
        flat = x.reshape(-1, x.shape[-1])
        probabilities = self.router(flat).softmax(dim=-1)
        if self.routing == "soft-top2":
            out = sum(self.experts[i](flat) * probabilities[:, i:i+1] for i in range(2))
        else:
            index = probabilities.argmax(dim=-1)
            out = torch.zeros_like(flat)
            for i in range(2):
                mask = index == i
                if not mask.any():
                    continue
                selected = probabilities[mask, i:i+1]
                if self.routing == "normalized-top1":
                    selected = selected / selected
                out[mask] = self.experts[i](flat[mask]) * selected
        return out.reshape_as(x)

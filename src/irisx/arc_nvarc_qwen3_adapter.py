"""Explicit original Qwen3 LoRA targets; no hybrid/DeltaNet assumptions."""
from __future__ import annotations
from .errors import ValidationError


def lora_targets(model):
    import torch
    if model.config.model_type!='qwen3' or model.config.vocab_size!=16:
        raise ValidationError('compact original Qwen3 required for source LoRA targets')
    projections=('q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj')
    layers=model.config.num_hidden_layers
    expected={f'model.layers.{i}.{branch}.{name}' for i in range(layers)
        for branch,names in [('self_attn',projections[:4]),('mlp',projections[4:])] for name in names}
    linear={name for name,module in model.named_modules() if isinstance(module,torch.nn.Linear)}
    embeddings={name for name,module in model.named_modules() if isinstance(module,torch.nn.Embedding)}
    if not expected<=linear or 'lm_head' not in linear or 'model.embed_tokens' not in embeddings:
        raise ValidationError('every original attention/MLP/embedding/head target required')
    return sorted(expected|{'model.embed_tokens','lm_head'})

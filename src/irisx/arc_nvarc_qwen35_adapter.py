"""Qwen3.5-only vocabulary, LoRA and hybrid-state boundary for NVARC."""

from __future__ import annotations

from typing import Any

from .arc_nvarc_representation import GridTokenizer
from .errors import ValidationError


def lora_targets(model: Any) -> list[str]:
    """Cover full attention, DeltaNet, MLP and compact input/output rows."""
    import torch

    linear = [name for name, module in model.named_modules()
              if isinstance(module, torch.nn.Linear) and "model.language_model.layers." in name]
    attention = [name for name in linear if ".self_attn." in name and
                 name.endswith(("q_proj", "k_proj", "v_proj", "o_proj"))]
    delta = [name for name in linear if ".linear_attn." in name]
    mlp = [name for name in linear if ".mlp." in name and
           name.endswith(("gate_proj", "up_proj", "down_proj"))]
    embedding = [name for name, module in model.named_modules()
                 if isinstance(module, torch.nn.Embedding) and name == "model.language_model.embed_tokens"]
    head = [name for name, module in model.named_modules()
            if isinstance(module, torch.nn.Linear) and name == "lm_head"]
    if not all((attention, delta, mlp, embedding, head)):
        raise ValidationError("Qwen3.5 attention/DeltaNet/MLP/embedding/head LoRA coverage unverified")
    return sorted(set(attention + delta + mlp + embedding + head))


def full_prefix_log_probs(model: Any, prefix: list[int]) -> list[float]:
    """Correctness reference: no mutable attention or recurrent state crosses branches."""
    import torch

    if not prefix or any(type(token) is not int or not 0 <= token < 16 for token in prefix):
        raise ValidationError("invalid compact Qwen prefix")
    device = next(model.parameters()).device
    with torch.inference_mode():
        ids = torch.tensor([prefix], dtype=torch.long, device=device)
        logits = model(input_ids=ids, use_cache=False).logits[0, -1]
        values = torch.log_softmax(logits.float(), dim=-1).cpu().tolist()
    if len(values) != GridTokenizer.vocab_size:
        raise ValidationError("Qwen checkpoint is not the 16-symbol compact model")
    return values


def answer_nll(model: Any, query: list[int], answer: list[int], *,
               normalize: bool = True) -> float:
    """Answer NLL including EOS; source Qwen ranking uses the unnormalized sum."""
    import torch

    if not query or not answer or any(type(token) is not int or not 0 <= token < 16
                                       for token in query + answer):
        raise ValidationError("invalid compact Qwen sequence")
    device = next(model.parameters()).device
    tokens = query + answer
    with torch.inference_mode():
        logits = model(input_ids=torch.tensor([tokens], dtype=torch.long, device=device),
                       use_cache=False).logits[0]
        log_probs = torch.log_softmax(logits[len(query) - 1:-1].float(), dim=-1)
        nll = -log_probs.gather(1, torch.tensor(answer, device=device).unsqueeze(1)).sum().item()
    return nll / len(answer) if normalize else nll

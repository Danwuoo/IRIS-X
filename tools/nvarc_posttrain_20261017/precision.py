"""Explicit FP32 compact output projection inside a BF16 backbone.

Only the active untied 16-way trainable head is replaced by an nn.Linear
subclass using the SAME Parameter objects. Both generation and differentiable
teacher forcing pass through it. An output cast after BF16 GEMM is not enough.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from .precision_contract import LEGACY_POLICY, FP32_HEAD_POLICY, admit_policy


class FP32CompactHead(torch.nn.Linear):
    def forward(self, inputs):
        if self.weight.dtype != torch.float32 or self.bias is not None:
            raise ValueError("untied bias-free FP32 compact head required")
        with torch.autocast(inputs.device.type, enabled=False):
            return F.linear(inputs.float(), self.weight, None)


def active_head(model):
    wrapper = model.get_output_embeddings()
    if (not hasattr(wrapper, "modules_to_save")
            or set(wrapper.modules_to_save) != {"default"}
            or model.active_adapter != "default"):
        raise ValueError("one active default compact output head required")
    return wrapper.modules_to_save["default"]


def install_policy(model, policy):
    admit_policy(policy)
    head = active_head(model)
    if (type(head) is not torch.nn.Linear or head.out_features != 16
            or head.bias is not None or head.weight.dtype != torch.float32):
        raise ValueError("fresh unmodified FP32 compact Linear required")
    if policy == FP32_HEAD_POLICY:
        # Meta allocation consumes neither memory for values nor an RNG draw.
        replacement = FP32CompactHead(head.in_features, head.out_features,
                                      bias=False, device="meta", dtype=torch.float32)
        replacement.weight = head.weight
        replacement.training = head.training
        model.get_output_embeddings().modules_to_save["default"] = replacement
    validate_policy(model, policy)


def validate_policy(model, policy):
    admit_policy(policy)
    head = active_head(model)
    expected = FP32CompactHead if policy == FP32_HEAD_POLICY else torch.nn.Linear
    if (type(head) is not expected or head.out_features != 16 or head.bias is not None
            or head.weight.dtype != torch.float32 or not head.weight.requires_grad
            or "forward" in head.__dict__):
        raise ValueError("actual compact output-head computation policy differs")
    return {"policy": policy, "head_class": type(head).__name__,
            "weight_dtype": str(head.weight.dtype),
            "output_dtype": "torch.float32" if policy == FP32_HEAD_POLICY else "outer-autocast-dependent",
            "backbone_autocast_changed": False, "old_behavior_relabeling_permitted": False}

"""Explicit compact numerical policies, never a behavior-logp substitution.

Only the active untied 16-way trainable head is replaced by an nn.Linear
subclass using the SAME Parameter objects. Both generation and differentiable
teacher forcing pass through it. An output cast after BF16 GEMM is not enough.
The separate full-FP32/math policy promotes the already initialized original
BF16-valued model, fixes actual scoped backends, and binds recomputation too.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import partial
import torch
import torch.nn.functional as F

from .precision_contract import (LEGACY_POLICY, FP32_HEAD_POLICY, FP32_BACKBONE_POLICY,
                                 admit_policy, output_head_contract)


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
    if policy in (FP32_HEAD_POLICY, FP32_BACKBONE_POLICY):
        # Meta allocation consumes neither memory for values nor an RNG draw.
        replacement = FP32CompactHead(head.in_features, head.out_features,
                                      bias=False, device="meta", dtype=torch.float32)
        replacement.weight = head.weight
        replacement.training = head.training
        model.get_output_embeddings().modules_to_save["default"] = replacement
    if policy == FP32_BACKBONE_POLICY:
        # Called only AFTER the original BF16 base and adapter initialization.
        # Promotion is exact for BF16 values and consumes no random numbers.
        model.float()
    validate_policy(model, policy)


def validate_policy(model, policy):
    admit_policy(policy)
    head = active_head(model)
    expected = FP32CompactHead if policy in (FP32_HEAD_POLICY, FP32_BACKBONE_POLICY) else torch.nn.Linear
    if (type(head) is not expected or head.out_features != 16 or head.bias is not None
            or head.weight.dtype != torch.float32 or not head.weight.requires_grad
            or "forward" in head.__dict__):
        raise ValueError("actual compact output-head computation policy differs")
    if policy == FP32_BACKBONE_POLICY and (
            any(p.dtype != torch.float32 for p in model.parameters())
            or any(b.is_floating_point() and b.dtype != torch.float32 for b in model.buffers())
            or model.config._attn_implementation != 'sdpa'):
        raise ValueError("actual FP32 backbone/math SDPA policy differs")
    return output_head_contract(policy)


@contextmanager
def full_precision_compute(device_type):
    """Scope actual forward AND backward arithmetic; restore process settings.

    The worker owns a single model computation stream. These PyTorch backend
    switches are process-global, so concurrent numerical policies in one
    process are not supported. Nested same-policy scopes are safe.
    """
    from torch.nn.attention import SDPBackend, sdpa_kernel
    previous = (torch.get_float32_matmul_precision(), torch.backends.cuda.matmul.allow_tf32,
                torch.backends.cudnn.allow_tf32)
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        with torch.autocast(device_type, enabled=False), sdpa_kernel(SDPBackend.MATH):
            yield
    finally:
        torch.set_float32_matmul_precision(previous[0])
        torch.backends.cuda.matmul.allow_tf32 = previous[1]
        torch.backends.cudnn.allow_tf32 = previous[2]


def _full_precision_checkpoint(function, *args, use_reentrant=False):
    """Preserve policy when backward recomputes outside the forward scope."""
    from torch.utils.checkpoint import checkpoint
    if use_reentrant is not False or not args or not isinstance(args[0], torch.Tensor):
        raise ValueError('nonreentrant tensor-input FP32 checkpoint required')
    device_type = args[0].device.type
    def contexts():
        return full_precision_compute(device_type), full_precision_compute(device_type)
    return checkpoint(function, *args, use_reentrant=False, context_fn=contexts)


def install_checkpoint_policy(model, policy):
    if policy == FP32_BACKBONE_POLICY:
        for module in model.modules():
            if getattr(module, 'gradient_checkpointing', False):
                # Keep kwargs JSON-serializable for the frozen-policy identity.
                module._gradient_checkpointing_func = partial(_full_precision_checkpoint, use_reentrant=False)
    validate_checkpoint_policy(model, policy)


def validate_checkpoint_policy(model, policy):
    if policy != FP32_BACKBONE_POLICY:
        return
    found = False
    for module in model.modules():
        if getattr(module, 'gradient_checkpointing', False):
            found = True
            function = getattr(module, '_gradient_checkpointing_func', None)
            if (not isinstance(function, partial) or function.func is not _full_precision_checkpoint
                    or function.keywords != {'use_reentrant': False} or function.args):
                raise ValueError('actual FP32 checkpoint recomputation policy differs')
    if not found:
        raise ValueError('actual FP32 checkpoint recomputation policy missing')


def execution_receipt(model, policy, device_type):
    """Attest active flags INSIDE the computation scope, never infer dispatch."""
    contract = validate_policy(model, policy)
    validate_checkpoint_policy(model, policy)
    receipt = {'policy': policy, 'autocast_enabled': torch.is_autocast_enabled(device_type),
        'float32_matmul_precision': torch.get_float32_matmul_precision(),
        'cuda_matmul_allow_tf32': torch.backends.cuda.matmul.allow_tf32,
        'cudnn_allow_tf32': torch.backends.cudnn.allow_tf32,
        'sdpa_backends': {'math': torch.backends.cuda.math_sdp_enabled(),
            'flash': torch.backends.cuda.flash_sdp_enabled(),
            'memory_efficient': torch.backends.cuda.mem_efficient_sdp_enabled(),
            'cudnn': torch.backends.cuda.cudnn_sdp_enabled()},
        'resident_parameter_dtypes': sorted({str(p.dtype) for p in model.parameters()}),
        'output_head_contract': contract}
    if policy == FP32_BACKBONE_POLICY and (
            receipt['autocast_enabled'] or receipt['float32_matmul_precision'] != 'highest'
            or receipt['cuda_matmul_allow_tf32'] or receipt['cudnn_allow_tf32']
            or receipt['sdpa_backends'] != {'math': True, 'flash': False, 'memory_efficient': False, 'cudnn': False}):
        raise ValueError('actual active FP32/math computation backend differs')
    return receipt

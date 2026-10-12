"""Inert deployment arithmetic, not GPU/model admission.

No downloads, CUDA discovery or optional imports occur here. Four L4s are four
separate devices. Every positive budget remains an estimate pending a measured
full-model, target-backend load/prefill/decode/adaptation probe.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from tools.arc_next_models import MODELS

GiB = 1 << 30


@dataclass(frozen=True)
class ModelProfile:
    key: str
    repository: str
    revision: str | None
    parameters_total: int
    parameters_active: int | None
    parameter_evidence: str
    admission: str
    attention_layers: int | None = None
    query_heads: int | None = None
    kv_heads: int | None = None
    head_dim: int | None = None
    hybrid_state: bool = False
    moe: bool = False
    experimental: bool = False
    notes: str = ""
    shape_evidence: str = "unpinned_official_config_observed_2026-10-11"


def _registry_profiles() -> dict[str, ModelProfile]:
    profiles = {}
    for key, spec in MODELS.items():
        c = spec.config_fields
        hybrid = key == "qwen3.5-9b"
        profiles[key] = ModelProfile(
            key=key, repository=spec.repository, revision=spec.revision,
            parameters_total=spec.parameters,
            parameters_active=None if hybrid else spec.parameters,
            parameter_evidence="pinned_source_inventory_envelope",
            admission="PINNED_MATERIAL_GPU_UNVERIFIED",
            attention_layers=(c["num_hidden_layers"] // c["full_attention_interval"]
                              if hybrid else c["num_hidden_layers"]),
            query_heads=c["num_attention_heads"], kv_heads=c["num_key_value_heads"],
            head_dim=c["hidden_size"] // c["num_attention_heads"],
            hybrid_state=hybrid, experimental=spec.experimental,
            shape_evidence="pinned_registry_config_subset",
            notes=("Full multimodal/MTP source envelope, not exact live text residency. "
                   "Recurrent-state size and backend remain unmeasured." if hybrid else
                   "Source storage dtype is not the requested live inference dtype."),
        )
    return profiles


PROFILES = _registry_profiles()
# Official model-card rounded counts, NOT pins or admitted material manifests.
# Sources observed 2026-10-11: https://huggingface.co/<repository>/
# Shapes: each official repository /raw/main/config.json (not revision-pinned).
for _p in (
    ModelProfile("qwen3.5-27b", "Qwen/Qwen3.5-27B", None, 27_000_000_000,
                 None, "rounded_card_estimate", "UNADMITTED", attention_layers=16,
                 query_heads=24, kv_heads=4, head_dim=256, hybrid_state=True,
                 experimental=True, notes="Exact config, tokenizer, inventory and backend pending."),
    ModelProfile("qwen3-14b", "Qwen/Qwen3-14B", None, 14_800_000_000,
                 14_800_000_000, "rounded_card_estimate", "UNADMITTED",
                 attention_layers=40, query_heads=40, kv_heads=8, head_dim=128),
    ModelProfile("qwen3-32b", "Qwen/Qwen3-32B", None, 32_800_000_000,
                 32_800_000_000, "rounded_card_estimate", "UNADMITTED",
                 attention_layers=64, query_heads=64, kv_heads=8, head_dim=128),
    ModelProfile("qwen3-coder-30b-a3b-instruct", "Qwen/Qwen3-Coder-30B-A3B-Instruct",
                 None, 30_500_000_000, 3_300_000_000, "rounded_card_estimate",
                 "UNADMITTED", attention_layers=48, query_heads=32, kv_heads=4, head_dim=128,
                 moe=True, notes="All experts are resident; active count is not storage."),
):
    PROFILES[_p.key] = _p


PRECISIONS = {
    "bf16": {"weight_bits": 16, "activation": "bf16", "compute": "bf16"},
    "w8a8_fp8": {"weight_bits": 8, "activation": "scaled_fp8",
                  "compute": "backend_verified_fp8_gemm_required"},
    "w8a16": {"weight_bits": 8, "activation": "bf16_or_fp16",
               "compute": "weight_only_dequantization_not_w8a8"},
    "w4a16": {"weight_bits": 4, "activation": "bf16_or_fp16",
               "compute": "weight_only_dequantization_not_fp8"},
    "mixed_fp8_training": {"weight_bits": 16, "activation": "selected_scaled_fp8",
                           "compute": "selected_forward_backward_gemms_only"},
}


def get_profile(key: str) -> ModelProfile:
    try:
        return PROFILES[key]
    except KeyError as error:
        raise ValueError("unknown deployment model: " + key) from error


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(name + " must be an integer >= " + str(minimum))
    return value


def weight_floor_bytes(parameters_total: int, bits: int) -> int:
    """Optimistic all-parameter payload floor, no scales or exceptions."""
    _integer(parameters_total, "parameters_total", 1)
    if bits not in (4, 8, 16, 32):
        raise ValueError("unsupported weight width")
    return (parameters_total * bits + 7) // 8


def plan_deployment(
    profile: str | ModelProfile,
    *,
    precision: str = "bf16",
    tensor_parallel: int = 1,
    device_count: int = 4,
    device_memory_bytes: int = 24 * GiB,
    batch_size: int | None = 1,
    context_tokens: int | None = 8192,
    kv_precision: str = "bf16",
    high_precision_parameters: int | None = None,
    replicated_parameters: int = 0,
    scale_group_size: int = 128,
    scale_bytes_per_group: int = 4,
    workspace_bytes_per_gpu: int = 2 * GiB,
    reserve_bytes_per_gpu: int = 2 * GiB,
    adapter_bytes_per_gpu: int = 0,
    hybrid_state_bytes_per_gpu: int | None = None,
    kv_scale_bytes_per_gpu: int | None = None,
    backend_tp_verified: bool = False,
    nccl_verified: bool = False,
    target_sm: tuple[int, int] = (8, 9),
    fp8_recipe: str = "per_tensor",
) -> dict[str, Any]:
    """Return a conservative scenario plus explicit unresolved fit obligations.

    TP assumes sharding of non-replicated weights and attention heads, not pooled
    VRAM. Quantized estimates default to 15% BF16 exceptions and one FP32 scale
    per 128 weights; these are planning allowances, not an audited tensor map.
    Runtime batch means simultaneous live sequences, including augmentations.
    Callers must budget full prefill/decode context and temporary load peaks.
    The 24-GiB default is a scenario, not an observed L4 capacity: marketed GB
    and usable CUDA bytes differ. Supply the actual per-device usable bytes.
    """
    model = get_profile(profile) if isinstance(profile, str) else profile
    if not isinstance(model, ModelProfile):
        raise ValueError("profile must be a registered key or ModelProfile")
    total = _integer(model.parameters_total, "parameters_total", 1)
    if model.parameters_active is not None:
        _integer(model.parameters_active, "parameters_active", 1)
        if model.parameters_active > total:
            raise ValueError("active parameters exceed total")
    if precision not in PRECISIONS or kv_precision not in ("bf16", "fp8"):
        raise ValueError("unknown precision")
    for name, value in (("tensor_parallel", tensor_parallel), ("device_count", device_count),
                        ("device_memory_bytes", device_memory_bytes),
                        ("scale_group_size", scale_group_size)):
        _integer(value, name, 1)
    for name, value in (("replicated_parameters", replicated_parameters),
                        ("scale_bytes_per_group", scale_bytes_per_group),
                        ("workspace_bytes_per_gpu", workspace_bytes_per_gpu),
                        ("reserve_bytes_per_gpu", reserve_bytes_per_gpu),
                        ("adapter_bytes_per_gpu", adapter_bytes_per_gpu)):
        _integer(value, name)
    if tensor_parallel not in (1, 2, 4) or device_count % tensor_parallel:
        raise ValueError("TP must be 1, 2 or 4 and divide the physical device count")
    for name, value in (("batch_size", batch_size), ("context_tokens", context_tokens)):
        if value is not None:
            _integer(value, name, 1)
    for name, value in (("hybrid_state_bytes_per_gpu", hybrid_state_bytes_per_gpu),
                        ("kv_scale_bytes_per_gpu", kv_scale_bytes_per_gpu)):
        if value is not None:
            _integer(value, name)
    bits = PRECISIONS[precision]["weight_bits"]
    if high_precision_parameters is not None:
        _integer(high_precision_parameters, "high_precision_parameters")
    exceptions_assumed = high_precision_parameters is None and bits < 16
    exceptions = (math.ceil(total * 0.15) if exceptions_assumed else
                  (high_precision_parameters or 0))
    _integer(exceptions, "high_precision_parameters")
    if exceptions > total or replicated_parameters > total:
        raise ValueError("exception/replicated parameters exceed total")
    # Assign exceptions to replicated parameters first, conservative for the
    # common replicated embedding/head case. Remaining exceptions are sharded.
    replicated_hi = min(exceptions, replicated_parameters)
    sharded_hi = exceptions - replicated_hi
    replicated_low = replicated_parameters - replicated_hi
    sharded_low = total - exceptions - replicated_low
    scale = (lambda n: ((n + scale_group_size - 1) // scale_group_size) * scale_bytes_per_group
             if bits < 16 else 0)
    local_low = (sharded_low + tensor_parallel - 1) // tensor_parallel
    local_hi = (sharded_hi + tensor_parallel - 1) // tensor_parallel
    local_weights = (replicated_low * bits + 7) // 8 + replicated_hi * 2
    local_weights += (local_low * bits + 7) // 8 + local_hi * 2
    local_scales = scale(replicated_low) + scale(local_low)
    blockers: list[str] = []
    unknowns = ["Full-model target-backend peak memory and task-time probe is required.",
                "Capacity is a scenario input; use observed usable CUDA bytes, not nominal marketed GB.",
                "Workspace/reserve are explicit estimates, not measured load/prefill peaks."]
    if model.admission == "UNADMITTED":
        unknowns.append("Exact material revision, tensor inventory and backend are unadmitted.")
    if bits < 16:
        unknowns.append("Quantization exception map, scales and conversion/load peak need measurement.")
    if model.moe:
        unknowns.append("Expert placement, routing buffers and expert kernels need verification.")
    if precision == "mixed_fp8_training":
        blockers.append("Whole-model mixed-FP8 training is unvalidated; inference arithmetic cannot admit it.")
    if fp8_recipe not in ("per_tensor", "mxfp8", "block_scaling"):
        raise ValueError("unknown FP8 recipe")
    if precision in ("w8a8_fp8", "mixed_fp8_training"):
        if target_sm not in ((8, 9), (9, 0), (10, 0), (10, 3), (12, 0)):
            blockers.append("Target SM has no supported per-tensor FP8 route in this planner.")
        if fp8_recipe == "mxfp8" and target_sm not in ((10, 0), (10, 3)):
            blockers.append("TE MXFP8 is not supported on L4 SM8.9 or RTX SM12.0 in the checked matrix.")
        if fp8_recipe == "block_scaling" and target_sm == (8, 9):
            blockers.append("TE block-scaling FP8 is not supported on L4 SM8.9.")
        unknowns.append("Installed runtime/kernel support must be checked; hardware capability is insufficient.")
    if tensor_parallel > 1:
        if not backend_tp_verified:
            unknowns.append("Backend weight sharding and replicated tensors are not verified.")
        if not nccl_verified:
            unknowns.append("Actual PCIe/NCCL collective correctness and latency are unmeasured.")
    for field in ("query_heads", "kv_heads"):
        value = getattr(model, field)
        if value is None:
            unknowns.append(field + " is unknown; TP divisibility cannot be established.")
        else:
            _integer(value, field, 1)
            if value % tensor_parallel:
                blockers.append(field + " is not divisible by TP; no implicit KV replication fallback.")
    kv_bytes = None
    shape = (model.attention_layers, model.kv_heads, model.head_dim, batch_size, context_tokens)
    if all(v is not None for v in shape):
        for name, value in zip(("attention_layers", "kv_heads", "head_dim", "batch_size", "context_tokens"), shape):
            _integer(value, name, 1)
        if model.kv_heads % tensor_parallel == 0:
            kv_bytes = (2 * model.attention_layers * (model.kv_heads // tensor_parallel)
                        * model.head_dim * batch_size * context_tokens
                        * (2 if kv_precision == "bf16" else 1))
    if kv_bytes is None:
        unknowns.append("Attention KV size is unknown for the requested shape/batch/TP.")
    if kv_precision == "fp8":
        unknowns.append("FP8 KV requires separate calibrated cache/backend and task-quality admission.")
        if kv_scale_bytes_per_gpu is None:
            unknowns.append("FP8 KV scale storage is unknown.")
    if model.hybrid_state and hybrid_state_bytes_per_gpu is None:
        unknowns.append("Hybrid recurrent state/workspace is unknown; ordinary KV excludes it.")
    hybrid_bytes = hybrid_state_bytes_per_gpu if model.hybrid_state else 0
    components = {
        "weights": local_weights, "weight_scales": local_scales,
        "attention_kv": kv_bytes, "kv_scales": (kv_scale_bytes_per_gpu if kv_precision == "fp8" else 0),
        "hybrid_state": hybrid_bytes, "workspace": workspace_bytes_per_gpu,
        "allocator_reserve": reserve_bytes_per_gpu, "adapters": adapter_bytes_per_gpu,
    }
    if precision == "mixed_fp8_training":
        components.update(fp8_weight_copies=None, fp8_scale_and_amax_history=None,
                          trainable_gradients=None, master_parameters=None,
                          optimizer_state=None, saved_training_activations=None)
        unknowns.append("Mixed training copies/scales/amax, gradients, master parameters, optimizer and saved activations are unmeasured.")
    known_bytes = sum(v for v in components.values() if v is not None)
    complete = all(v is not None for v in components.values())
    if known_bytes >= device_memory_bytes:
        blockers.append("Per-GPU known budget reaches/exceeds capacity; zero unmodeled headroom is blocked.")
    result = {
        "format": "irisx/deployment-plan-v1", "model": asdict(model),
        "precision": dict(PRECISIONS[precision], key=precision, kv_precision=kv_precision),
        "status": "BLOCKED" if blockers else "ESTIMATE_ONLY",
        "execution_admitted": False, "fit_claim": "NOT_MEASURED",
        "physical_devices": device_count, "tensor_parallel": tensor_parallel,
        "independent_workers": device_count // tensor_parallel,
        "per_gpu_capacity_bytes": device_memory_bytes,
        "capacity_evidence": "caller_supplied_scenario_not_observed_hardware",
        "pooled_memory": False, "interconnect_assumption": "PCIe/NCCL; no NVLink assumed",
        "weight_floor_bytes_per_model": weight_floor_bytes(total, bits),
        "weight_floor_gib_per_model": weight_floor_bytes(total, bits) / GiB,
        "high_precision_parameters": exceptions, "exception_count_is_assumed": exceptions_assumed,
        "replicated_parameters": replicated_parameters,
        "scale_assumption": {"group_size": scale_group_size, "bytes_per_group": scale_bytes_per_group},
        "per_gpu_bytes": components, "known_bytes_per_gpu": known_bytes,
        "estimate_complete": complete,
        "estimated_bytes_per_gpu": known_bytes if complete else None,
        "remaining_after_known_bytes_per_gpu": device_memory_bytes - known_bytes,
        "blockers": blockers, "measurement_obligations": unknowns,
    }
    return result


def require_measured_deployment(plan: dict[str, Any]) -> None:
    """Analytical plans cannot serve as future worker-admission receipts."""
    raise ValueError("Deployment is unadmitted: require an independently validated full-model runtime receipt")

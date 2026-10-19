"""Explicit architecture admission for the existing shared-group trainer.

Admission is structural only. It does not replace the forced cached/full
probability probe, per-group replay gate or actual gradient-bearing AF3 gate.
Only the three reviewed concrete engine classes are accepted, never arbitrary
subclasses. Dense historical precision policies remain admitted by the probe;
expanded engines and the fusion trainer require the existing FP32 policy.
"""
from __future__ import annotations

import hashlib

from tools.arc2_goal_sprint_20261017.data import canonical
from tools.arc2_goal_sprint_20261017.launch import require
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY


def admit_engine(engine, *, require_fp32=False):
    # Lazy imports avoid making the dense engine depend on architecture loading
    # at module import time. This allowlist is intentionally not isinstance().
    from transformers import Qwen3ForCausalLM
    from tools.nvarc_posttrain_20261017.engine import CompactEngine
    from tools.nvarc_capacity_20261018.model import CapacityEngine, TREATMENTS
    from tools.nvarc_width_20261018.model import WidthEngine

    cls = type(engine)
    require(cls in (CompactEngine, CapacityEngine, WidthEngine),
            'explicit reviewed CompactEngine, CapacityEngine or WidthEngine required')
    require(type(engine.model.get_base_model()) is Qwen3ForCausalLM,
            'actual native Qwen3ForCausalLM required')
    if require_fp32 or cls is not CompactEngine:
        require(engine.probability_policy == FP32_BACKBONE_POLICY,
                'expanded/fusion engine requires unchanged FP32-backbone policy')
    # Each concrete engine validates its exact source-derived module mapping,
    # frozen tensor versions, numerics, PEFT configuration and named trainables.
    engine._checkpoint_admission()
    if cls is CapacityEngine:
        kind, key = 'capacity-v2', 'capacity_v2'
        require(engine.treatment in TREATMENTS, 'known capacity treatment required')
    elif cls is WidthEngine:
        kind, key = 'width-v1', 'width_v1'
        require(engine.treatment in ('initial_anchor', 'baseline', 'width8192'),
                'known width treatment required')
    else:
        kind, key = 'compact', None
    if key is not None:
        receipt = engine.contract.get(key)
        require(type(receipt) is dict and receipt['treatment'] == engine.treatment
                and receipt['native_weights_trainable'] is False
                and receipt['optimizer_reuse_allowed'] is False
                and receipt['probability_policy'] == FP32_BACKBONE_POLICY,
                'exact source-derived architecture receipt required')
    return {
        'format': 'irisx/fusion-architecture-admission-v1',
        'kind': kind,
        'treatment': engine.treatment if key is not None else 'dense',
        'model_contract_sha256': hashlib.sha256(canonical(engine.contract)).hexdigest(),
        'trainable_contract_sha256': hashlib.sha256(canonical(engine.trainable_inventory)).hexdigest(),
        'probability_policy': engine.probability_policy,
        'structure_verified': True,
        'probability_gate_replaced': False,
        'gradient_gate_replaced': False,
        'official_gpu_feasibility_established': False,
    }

"""Candidate-only paired threshold comparison, on a supplied authorized backend.

No model loading, source acquisition, provider call, scoring or execution CLI.
External use needs a NEW owner envelope. Local tiny-model validation uses this
same implementation. All arms share one adapted model and fixed source views.
"""

import copy
import hashlib

from .arc_nvarc_candidates import QwenCandidateBackend, candidate_score_limit, solve_task
from .canonical import digest_value
from .errors import ValidationError


def _state_identity(model):
    # Inference must not replace tensors or perform in-place weight changes.
    # This is a mutation guard, not a replacement for pinned material digests.
    return [(name, id(value), value._version) for name, value in model.named_parameters()]


def _adapter_digest(model):
    import torch
    from peft import get_peft_model_state_dict
    return digest_value({name: {"shape": list(value.shape), "dtype": str(value.dtype),
        "sha256": hashlib.sha256(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
        for name,value in get_peft_model_state_dict(model).items()})


def compare_thresholds(task, backend, config, arms, *, call_observer=None):
    task, config, arms = copy.deepcopy((task, config, arms))
    if type(backend) is not QwenCandidateBackend or backend.decoding != "bounded-dfs":
        raise ValidationError("threshold comparison requires bounded Qwen backend")
    if (len(arms) != 3 or len({a["id"] for a in arms}) != 3 or
            [a["cumulative_probability_threshold"] for a in arms] != [.2, .1, .02] or
            config.get("maximum_calls_per_task") != 4 or config.get("beams_per_call") != 2 or
            config.get("maximum_new_tokens") != 64 or config.get("representation") != "source-qwen" or
            config.get("seed") != 2 or config.get("source_generation_seed") != 2 or config.get("color_repeats") != 2 or
            config.get("augmentation") != "source-qwen" or config.get("ranking") != "source-kgmon" or
            backend.dfs_max_expansions != 128 or len(task["test"]) != 1):
        raise ValidationError("reviewed threshold trial workload differs")
    expected_adaptation = {"seed":42,"rank":2,"alpha":4,"learning_rate":.00005,
        "steps":1,"max_sequence_length":128,"augmentation_count":1,"source_augmentation_seed":1,"source_qwen":True}
    if backend.adapter is None or any(backend.adapter.config.get(k) != v for k,v in expected_adaptation.items()):
        raise ValidationError("reviewed threshold trial adaptation differs")
    original_base, original_adapter, original_score = backend.base_model, backend.adapter, backend.dfs_max_score
    reports = []
    try:
        if call_observer is not None:
            call_observer({"kind": "ttt", "status": "reserved", "steps": 1, "task_id": task["task_id"]})
        backend.begin_task(task)  # The ONLY adaptation across all arms.
        adapted = backend.model
        frozen = _state_identity(adapted)
        adapted_digest = _adapter_digest(adapted)
        adaptation = original_adapter.last_observation if original_adapter is not None else None
        if call_observer is not None:
            call_observer({"kind": "ttt", "status": "complete", "observation": adaptation, "task_id": task["task_id"]})
        backend.base_model = adapted
        backend.adapter = None
        for arm in arms:
            arm_config = {**config, "cumulative_probability_threshold": arm["cumulative_probability_threshold"]}
            backend.dfs_max_score = candidate_score_limit(arm_config)
            def observer(event):
                if call_observer is not None:
                    call_observer({**event, "arm_id": arm["id"]})
            results = solve_task(task, backend, arm_config, call_observer=observer)
            if _state_identity(adapted) != frozen or _adapter_digest(adapted) != adapted_digest:
                raise ValidationError("adapted model changed during paired inference")
            queries = [o["query_digest"] for row in results for o in row["generation_observations"]]
            if reports and queries != reports[0]["query_digests"]:
                raise ValidationError("paired threshold queries differ")
            reports.append({"arm_id": arm["id"], "config_digest": digest_value(arm_config),
                "query_digests": queries, "shared_adapter_digest": adapted_digest,
                "results": results, "generation_calls": results[-1]["generation_calls_so_far"],
                "explicit_forwards": backend.forward_calls, "verification_calls": backend.verification_calls,
                "model_mutation_guard_passed": True})
        return {"format": "irisx/nvarc-root-threshold-comparison-v1", "arms": reports,
                "task_visible_digest": digest_value(task), "shared_adaptation": adaptation,
                "shared_adapter_digest": adapted_digest,
                "generation_calls": sum(r["generation_calls"] for r in reports),
                "claim": "candidate availability and cost; no exact-match score or method promotion"}
    finally:
        backend.base_model, backend.adapter, backend.dfs_max_score = original_base, original_adapter, original_score
        backend.end_task()

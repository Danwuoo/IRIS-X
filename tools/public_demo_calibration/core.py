"""Gold-free LOO plans, audited receipts, and fixed same-pool rankers.

No evaluator, model loader, optimizer, network, or private implementation is
imported. The base package supplies its independently implemented public codec.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

from tools.public_sft141_diagnostic import contract
from tools.public_sft141_diagnostic.model_pins import MODEL_FILES, MODEL_HANDLE
from tools.public_sft141_diagnostic.model_worker import validate_plan

BASE_COMMIT = "afb2dfaa3a5c3f6e09338fd38487e29f77a0c47c"
PUBLIC_COMMIT = "f3283f727488ad98fe575ea6a5ac981e4a188e49"
TEMPERATURE = 1.0
CONTEXT_CAP = 8192
VIEWS = tuple(range(8))
PROTOCOL = {
    "schema": "public-demo-calibration-method-v1",
    "temperature": TEMPERATURE,
    "normalization": "mean-over-supports-of-sum-answer-NLL-including-EOS/answer-token-count",
    "views": list(VIEWS), "support_order": "original; leave exactly one out",
    "generation": "all original support; native greedy; eight D4; max_new_tokens=931",
    "ranking": "sum fixed calibration weight of views producing each inverse-transformed grid",
    "tie_break": "ascending compact JSON canonical grid key",
    "incomplete_calibration": "uniform-vote fallback; never partial-weight promotion",
    "single_demo": "uniform-vote fallback; no empty-conditioned adaptation",
    "query_candidate_likelihood_mix": False, "training": False,
    "weight_underflow": "uniform-vote fallback rather than silently suppress any view",
}
MODEL_IDENTITY = {"handle": MODEL_HANDLE, "files": {
    name: {"bytes": size, "sha256": digest} for name, (size, digest) in MODEL_FILES.items()}}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _exact(value: Any, fields: set[str], what: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"unexpected or missing {what} fields")


def _number(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{what} must be finite and nonnegative")
    return float(value)


def _integer(value: Any, what: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{what} must be an integer >= {minimum}")
    return value


def _key(grid: list[list[int]]) -> str:
    return json.dumps(grid, separators=(",", ":"))


def validate_gold_free(plan: Any) -> None:
    validate_plan(plan)  # Preserve the base test-input contract unchanged.
    forbidden = {"answer", "answers", "gold", "groundtruth", "solution", "solutions",
                 "label", "labels", "testlabel", "testlabels", "testoutput", "testoutputs",
                 "output", "outputs", "target", "targets", "expectedoutput", "expectedoutputs"}
    def clean_metadata(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str) or "".join(c for c in key.lower() if c.isalnum()) in forbidden:
                    raise ValueError("label-bearing metadata is not an inference input")
                clean_metadata(child)
        elif isinstance(value, list):
            for child in value:
                clean_metadata(child)
    clean_metadata(plan.get("provenance", {}))
    clean_metadata(plan.get("protocol", {}))
    for parent in plan["parents"]:
        clean_metadata(parent.get("selection", {}))
    if set(plan) != {"schema", "parents", "provenance", "protocol"}:
        raise ValueError("all frozen plan fields are required")
    # Bind to the original public-source panel in a real experiment. Synthetic
    # fixtures remain useful but cannot be mistaken for an executed public run.
    if plan["provenance"].get("commit") not in (None, PUBLIC_COMMIT):
        raise ValueError("unexpected public data revision")


def _case(parent: dict, held: int, view: int) -> tuple[dict, list[int], list[int]]:
    train = parent["train"]
    indices = [i for i in range(len(train)) if i != held]
    if not indices:
        raise ValueError("single-demo LOO must not create empty conditioning")
    prompt = contract.prompt_ids([train[i] for i in indices], train[held]["input"], view)
    answer = contract.answer_ids(contract.transform(train[held]["output"], view))
    p, a = len(prompt), len(answer)
    spec = {"case_id": f"{parent['task_id']}:support:{held}:view:{view}",
            "task_id": parent["task_id"], "held_support_index": held, "view": view,
            "conditioned_support_indices": indices,
            "conditioned_pair_sha256": [digest(train[i]) for i in indices],
            "held_pair_sha256": digest(train[held]),
            "held_input_sha256": digest(train[held]["input"]),
            "held_output_sha256": digest(train[held]["output"]),
            "prompt_sha256": digest(prompt), "answer_sha256": digest(answer),
            "model_input_sha256": digest(prompt + answer[:-1]),
            "prompt_tokens": p, "answer_tokens": a, "input_tokens": p + a - 1,
            "loss_mask": {"logit_start_inclusive": p - 1,
                          "logit_end_exclusive": p - 1 + a,
                          "target_count": a, "last_target_id": contract.EOS_ID,
                          "prompt_targets_included": False, "padding_included": False,
                          "held_support_pair_in_conditioning": False}}
    return spec, prompt, answer


def cases(plan: dict) -> list[tuple[dict, list[int], list[int]]]:
    validate_gold_free(plan)
    return [_case(parent, held, view) for parent in plan["parents"]
            if len(parent["train"]) > 1 for held in range(len(parent["train"])) for view in VIEWS]


def generation_specs(plan: dict) -> list[dict]:
    validate_gold_free(plan)
    records = []
    for parent in plan["parents"]:
        for query in parent["test"]:
            for view in VIEWS:
                prompt = contract.prompt_ids(parent["train"], query["input"], view)
                records.append({"query_id": query["query_id"], "task_id": parent["task_id"],
                    "test_index": query["test_index"], "view": view,
                    "support_indices": list(range(len(parent["train"]))),
                    "support_pair_sha256": [digest(pair) for pair in parent["train"]],
                    "query_input_sha256": digest(query["input"]),
                    "prompt_sha256": digest(prompt), "prompt_tokens": len(prompt),
                    "max_new_tokens": contract.MAX_NEW_TOKENS})
    return records


def prepare(plan: dict, max_context: int = CONTEXT_CAP, budget_seconds: float = 7200) -> dict:
    """Plan every operation before execution, never shorten or replace a task."""
    _integer(max_context, "max_context", 1)
    budget = _number(budget_seconds, "budget_seconds")
    if not 60 <= budget <= 7200:
        raise ValueError("whole-session budget must be 60..7200 seconds")
    limit = min(max_context, CONTEXT_CAP)
    loo = [spec for spec, _, _ in cases(plan)]
    generation = generation_specs(plan)
    # Match the base backend's conservative prompt + full answer admission,
    # although the actual teacher-forced input omits the final EOS target.
    failures = [{"case_id": s["case_id"], "required_tokens": s["input_tokens"] + 1}
                for s in loo if s["input_tokens"] + 1 > limit]
    failures += [{"query_id": s["query_id"], "view": s["view"],
                  "required_tokens": s["prompt_tokens"] + contract.MAX_NEW_TOKENS}
                 for s in generation if s["prompt_tokens"] + contract.MAX_NEW_TOKENS > limit]
    return {"schema": "public-demo-calibration-plan-v1", "plan_sha256": digest(plan),
        "protocol": copy.deepcopy(PROTOCOL), "protocol_sha256": digest(PROTOCOL),
        "base_commit": BASE_COMMIT, "public_commit": PUBLIC_COMMIT,
        "model_identity_sha256": digest(MODEL_IDENTITY), "context_cap": limit,
        "context_admitted": not failures, "context_failures": failures,
        "budget_seconds": budget, "hard_watchdog_required_before_real_execution": True,
        "calibration_cases": loo, "generation_cases": generation,
        "task_count": len(plan["parents"]), "query_count": sum(len(p["test"]) for p in plan["parents"]),
        "calibration_forward_calls": len(loo),
        "calibration_input_tokens": sum(s["input_tokens"] for s in loo),
        "calibration_answer_tokens": sum(s["answer_tokens"] for s in loo),
        "generation_calls": len(generation),
        "candidate_rescore_forward_upper_bound": 8 * len(generation),
        "gpu_seconds": None, "peak_gpu_bytes": None, "model_executed": False}


def receipt_header(plan: dict, kind: str, session_id: str) -> dict:
    if kind not in ("synthetic_cpu", "public_model"):
        raise ValueError("unknown receipt execution kind")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("session identity is required")
    return {"plan_sha256": digest(plan), "protocol_sha256": digest(PROTOCOL),
            "model_identity_sha256": digest(MODEL_IDENTITY), "execution_kind": kind,
            "session_id": session_id, "training": False, "model_immutable": True}


HEADER_FIELDS = set(receipt_header({}, "synthetic_cpu", "schema-only"))


def _header(plan: dict, bundle: dict) -> None:
    expected = receipt_header(plan, bundle.get("execution_kind"), bundle.get("session_id"))
    if any(digest(bundle.get(k)) != digest(v) for k, v in expected.items()):
        raise ValueError("receipt provenance, protocol, model, or plan binding mismatch")


def calibration_bundle(plan: dict, rows: list[dict], *, kind: str = "synthetic_cpu",
                       session_id: str = "synthetic", completed_event: int = 0,
                       status: str | None = None) -> dict:
    return {"schema": "public-demo-calibration-receipts-v1", **receipt_header(plan, kind, session_id),
            "completed_event": completed_event, "rows": rows,
            "status": status or ("complete" if len(rows) == len(cases(plan)) and
                                  all(r.get("status") == "complete" for r in rows) else "partial")}


def complete_row(spec: dict, nll_sum: float, seconds: float, event: int, memory: dict | None = None) -> dict:
    """Freeze a backend result; the caller must not mistake a fixture for a run."""
    return {"spec": copy.deepcopy(spec), "status": "complete", "nll_sum": nll_sum,
            "seconds": seconds, "event": event, "forward_calls": 1,
            "actual_input_tokens": spec["input_tokens"],
            "actual_answer_tokens": spec["answer_tokens"], "memory": copy.deepcopy(memory)}


def validate_calibration(plan: dict, bundle: dict) -> dict[str, dict]:
    _exact(bundle, HEADER_FIELDS | {"schema", "completed_event", "rows", "status"}, "calibration bundle")
    if bundle["schema"] != "public-demo-calibration-receipts-v1":
        raise ValueError("unsupported calibration schema")
    _header(plan, bundle)
    if bundle["status"] not in ("complete", "partial"):
        raise ValueError("unknown calibration completion status")
    end = _integer(bundle["completed_event"], "completed_event")
    if not isinstance(bundle["rows"], list):
        raise ValueError("calibration rows must be a list")
    expected = {s["case_id"]: s for s, _, _ in cases(plan)}
    found, events = {}, set()
    for row in bundle["rows"]:
        _exact(row, {"spec", "status", "nll_sum", "seconds", "event", "forward_calls",
                     "actual_input_tokens", "actual_answer_tokens", "memory"}, "calibration row")
        spec = row["spec"]
        case_id = spec.get("case_id") if isinstance(spec, dict) else None
        if case_id not in expected or digest(spec) != digest(expected[case_id]) or case_id in found:
            raise ValueError("LOO support/output/mask binding mismatch or duplicate case")
        if row["status"] not in ("complete", "failed"):
            raise ValueError("unknown calibration status")
        event = _integer(row["event"], "calibration event")
        if event >= end or event in events:
            raise ValueError("calibration event order is invalid")
        events.add(event)
        _number(row["seconds"], "calibration seconds")
        memory = row["memory"]
        if memory is not None:
            allowed = {"allocated_bytes", "reserved_bytes", "peak_allocated_bytes", "peak_reserved_bytes", "free_bytes", "total_bytes"}
            if not isinstance(memory, dict) or set(memory) - allowed:
                raise ValueError("unknown memory receipt fields")
            for value in memory.values():
                _integer(value, "memory bytes")
        if row["status"] == "complete":
            _number(row["nll_sum"], "answer NLL")
            if (type(row["forward_calls"]) is not int or row["forward_calls"] != 1 or
                    type(row["actual_input_tokens"]) is not int or row["actual_input_tokens"] != spec["input_tokens"] or
                    type(row["actual_answer_tokens"]) is not int or row["actual_answer_tokens"] != spec["answer_tokens"]):
                raise ValueError("actual token/forward counts disagree with full causal mask")
        elif any(row[k] is not None for k in ("nll_sum", "forward_calls", "actual_input_tokens", "actual_answer_tokens")):
            raise ValueError("failed operation must retain unknown counters, not fabricated zero cost")
        found[case_id] = row
    if bundle["status"] == "complete" and (set(found) != set(expected) or
            any(r["status"] != "complete" for r in found.values())):
        raise ValueError("incomplete calibration cannot claim complete")
    return found


def weights_from_means(means: list[float]) -> dict:
    """Stable T=1 centered softmax. Underflow cannot silently drop a view."""
    if len(means) != 8:
        raise ValueError("all eight view losses are required")
    values = [_number(value, "mean NLL") for value in means]
    center = math.fsum(v / 8 for v in values)
    minimum = min(values)
    # Algebraically identical to softmax(-(mean-center)/T), avoiding both
    # overflow in exp and cancellation of a large shared offset.
    exps = [math.exp(-(v - minimum) / TEMPERATURE) for v in values]
    total = math.fsum(exps)
    weights = [v / total for v in exps]
    underflow = sum(w == 0.0 for w in weights)
    if underflow:
        weights = [1 / 8] * 8
    return {"weights": weights, "means": values, "centered_means": [v - center for v in values],
            "temperature": TEMPERATURE, "effective_view_count": 1 / math.fsum(w * w for w in weights),
            "weight_min": min(weights), "weight_max": max(weights),
            "weight_range": max(weights) - min(weights), "underflow_views": underflow}


def calibrate(plan: dict, bundle: dict) -> dict[str, dict]:
    found = validate_calibration(plan, bundle)
    result = {}
    for parent in plan["parents"]:
        n = len(parent["train"])
        per_view = [[] for _ in VIEWS]
        coverage = [0] * n
        completed = []
        for held in range(n):
            for view in VIEWS:
                row = found.get(f"{parent['task_id']}:support:{held}:view:{view}")
                if row is not None and row["status"] == "complete":
                    per_view[view].append(row["nll_sum"] / row["spec"]["answer_tokens"])
                    coverage[held] += 1
                    completed.append(row)
        ready = bundle["status"] == "complete" and n > 1 and coverage == [8] * n
        summary = weights_from_means([math.fsum(v / n for v in values) for values in per_view]) if ready else weights_from_means([0.] * 8)
        status = "complete" if ready else "single_demo_fallback" if n == 1 else "partial_calibration_fallback"
        if summary["underflow_views"]:
            ready, status = False, "numeric_underflow_fallback"
        summary.update({"status": status, "adaptation_eligible": ready,
            "support_count": n, "support_view_coverage": coverage,
            "required_cells": 8 * n if n > 1 else 0, "completed_cells": len(completed),
            "support_token_mean_nll_by_view": per_view,
            "completed_forward_calls": len(completed),
            "completed_input_tokens": sum(r["actual_input_tokens"] for r in completed),
            "completed_answer_tokens": sum(r["actual_answer_tokens"] for r in completed),
            "peak_allocated_bytes": max((r["memory"]["peak_allocated_bytes"] for r in completed if r["memory"] and "peak_allocated_bytes" in r["memory"]), default=None),
            "recorded_seconds": math.fsum(r["seconds"] for r in found.values() if r["spec"]["task_id"] == parent["task_id"]),
            "missing_or_failed_cost_unknown": not (n == 1 or len(completed) == 8 * n),
            "uncertainty": "LOO conditions overlap; supports/views are dependent; ESS describes concentration, not independent sample size"})
        if not ready and status != "numeric_underflow_fallback":
            summary["means"] = summary["centered_means"] = None
        result[parent["task_id"]] = summary
    return result


def pool_bundle(plan: dict, calibration: dict, rows: list[dict]) -> dict:
    return {"schema": "public-demo-pool-receipts-v1",
            **receipt_header(plan, calibration["execution_kind"], calibration["session_id"]),
            "calibration_sha256": digest(calibration), "rows": rows}


def pool_row(spec: dict, tokens: list[int], seconds: float, event: int, status: str = "complete") -> dict:
    return {"spec": copy.deepcopy(spec), "token_ids": list(tokens), "seconds": seconds,
            "event": event, "status": status}


def validate_pool(plan: dict, calibration: dict, pool: dict) -> dict[tuple[str, int], dict]:
    _exact(pool, HEADER_FIELDS | {"schema", "calibration_sha256", "rows"}, "candidate pool")
    if pool["schema"] != "public-demo-pool-receipts-v1":
        raise ValueError("unsupported pool schema")
    _header(plan, pool)
    if any(pool[k] != calibration[k] for k in HEADER_FIELDS) or pool["calibration_sha256"] != digest(calibration):
        raise ValueError("pool must bind the same session, model, plan and frozen calibration")
    expected = {(s["query_id"], s["view"]): s for s in generation_specs(plan)}
    if not isinstance(pool["rows"], list):
        raise ValueError("pool rows must be a list")
    found, events = {}, set()
    for row in pool["rows"]:
        _exact(row, {"spec", "token_ids", "seconds", "event", "status"}, "pool row")
        spec = row["spec"]
        key = (spec.get("query_id"), spec.get("view")) if isinstance(spec, dict) else None
        if key not in expected or digest(spec) != digest(expected[key]) or key in found:
            raise ValueError("full-support query/view binding mismatch or duplicate generation")
        event = _integer(row["event"], "generation event")
        if event <= calibration["completed_event"] or event in events:
            raise ValueError("calibration must be frozen before every task.test generation")
        events.add(event)
        _number(row["seconds"], "generation seconds")
        if row["status"] not in ("complete", "failed", "deadline"):
            raise ValueError("unknown generation status")
        tokens = row["token_ids"]
        if not isinstance(tokens, list) or len(tokens) > contract.MAX_NEW_TOKENS or any(type(t) is not int or not 0 <= t < 16 for t in tokens):
            raise ValueError("raw native token IDs required")
        found[key] = row
    return found


def rank(plan: dict, calibration: dict, pool: dict) -> dict:
    summaries = calibrate(plan, calibration)
    rows = validate_pool(plan, calibration, pool)
    queries = []
    rescore_tokens, rescore_targets, rescore_calls = 0, 0, 0
    for parent in plan["parents"]:
        summary = summaries[parent["task_id"]]
        for query in parent["test"]:
            candidates, invalid, missing, failed = {}, [], [], []
            for view in VIEWS:
                row = rows.get((query["query_id"], view))
                if row is None:
                    missing.append(view)
                    continue
                if row["status"] != "complete":
                    failed.append(view)
                    continue
                try:
                    grid = contract.inverse(contract.parse_answer(row["token_ids"]), view)
                except ValueError:
                    invalid.append(view)
                    continue
                key = _key(grid)
                candidates.setdefault(key, {"canonical_key": key, "grid": grid, "views": []})["views"].append(view)
            for candidate in candidates.values():
                candidate["count"] = len(candidate["views"])
                candidate["weighted_vote"] = math.fsum(summary["weights"][v] for v in candidate["views"])
                for view in VIEWS:
                    p = contract.prompt_ids(parent["train"], query["input"], view)
                    a = contract.answer_ids(contract.transform(candidate["grid"], view))
                    rescore_calls += 1
                    rescore_tokens += len(p) + len(a) - 1
                    rescore_targets += len(a)
            uniform = sorted(candidates.values(), key=lambda c: (-c["count"], c["canonical_key"]))
            weighted = sorted(candidates.values(), key=lambda c: (-c["weighted_vote"], c["canonical_key"]))
            pool_complete = not missing and not failed
            # Never make an adaptation promotion from a partial pool/calibration.
            use_weighted = pool_complete and summary["adaptation_eligible"]
            selected = weighted if use_weighted else uniform
            queries.append({"query_id": query["query_id"], "task_id": parent["task_id"],
                "test_index": query["test_index"], "pool_complete": pool_complete,
                "missing_views": missing, "failed_views": failed, "invalid_views": invalid,
                "valid_view_weight": math.fsum(summary["weights"][v] for c in candidates.values() for v in c["views"]),
                "invalid_view_weight_not_redistributed": math.fsum(summary["weights"][v] for v in invalid),
                "candidates": sorted(candidates.values(), key=lambda c: c["canonical_key"]),
                "uniform_ranking": [c["grid"] for c in uniform],
                "weighted_ranking": [c["grid"] for c in selected],
                "uniform_top2": [c["grid"] for c in uniform[:2]],
                "weighted_top2": [c["grid"] for c in selected[:2]],
                "adaptation_applied": use_weighted,
                "status": "complete" if use_weighted else "incomplete_pool_fallback" if not pool_complete else summary["status"]})
    forward = sum(s["completed_forward_calls"] for s in summaries.values())
    tokens = sum(s["completed_input_tokens"] for s in summaries.values())
    incomplete = any(s["missing_or_failed_cost_unknown"] for s in summaries.values())
    return {"schema": "public-demo-ranking-v1", "plan_sha256": digest(plan),
        "calibration_sha256": digest(calibration), "pool_sha256": digest(pool),
        "protocol_sha256": digest(PROTOCOL), "execution_kind": calibration["execution_kind"],
        "calibration": summaries, "queries": queries,
        "fixed_task_denominator": len(plan["parents"]), "fixed_query_denominator": len(queries),
        "all_pools_complete": all(q["pool_complete"] for q in queries),
        "all_eligible_calibrations_complete": all(s["status"] in ("complete", "single_demo_fallback") for s in summaries.values()),
        "cost": {"calibration_completed_forward_calls": forward,
            "calibration_completed_input_tokens": tokens,
            "calibration_completed_answer_tokens": sum(s["completed_answer_tokens"] for s in summaries.values()),
            "calibration_recorded_seconds": math.fsum(s["recorded_seconds"] for s in summaries.values()),
            "calibration_peak_allocated_bytes": max((s["peak_allocated_bytes"] for s in summaries.values() if s["peak_allocated_bytes"] is not None), default=None),
            "calibration_missing_or_failed_cost_unknown": incomplete,
            "generation_recorded_calls": len(rows),
            "generation_recorded_prompt_tokens": sum(r["spec"]["prompt_tokens"] for r in rows.values()),
            "generation_recorded_output_tokens": sum(len(r["token_ids"]) for r in rows.values()),
            "generation_recorded_seconds": math.fsum(r["seconds"] for r in rows.values()),
            "same_pool_original_rescore_forward_calls_counterfactual": rescore_calls,
            "same_pool_original_rescore_input_tokens_counterfactual": rescore_tokens,
            "same_pool_original_rescore_answer_tokens_counterfactual": rescore_targets,
            "calibration_token_difference_vs_rescore": None if incomplete or not all(q["pool_complete"] for q in queries) else tokens - rescore_tokens,
            "original_rescore_gpu_seconds": None, "gpu_time_saving": None,
            "uniform_vote_extra_forward_calls": 0,
            "qualification": "Counterfactual rescore token counts are exact for observed candidates, not measured runtime or FLOPs; incomplete work costs are lower bounds."},
        "scientific_effectiveness_established": False,
        "qualification": "Receipt replay only; public and possibly exposed data; neither hashes nor CPU tests authenticate model execution or establish gain."}

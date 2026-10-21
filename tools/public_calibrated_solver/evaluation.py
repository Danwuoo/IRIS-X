"""Pure, post-model-exit audit for the public demonstration-calibrated solver.

Only the evaluator leaf may import this module and pass gold to ``evaluate``.
There is no file, network, model, or subprocess operation here. Receipt/schema
validation is shared; all derived calibration and candidate ranking arithmetic
is reconstructed here without calling the production calibrator or ranker.
Public-panel outcomes, and particularly synthetic outcomes, establish no gain.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any

from tools.public_demo_calibration import core
from tools.public_sft141_diagnostic import contract

__all__ = ["evaluate", "audit_predictions"]
_VIEWS = tuple(range(8))
_PARENTS = 12
_QUERIES = 15
_BOOTSTRAP_SEED = 20261021
_BOOTSTRAP_DRAWS = 10000


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _key(grid: list[list[int]]) -> str:
    return json.dumps(grid, separators=(",", ":"))


def _same(actual: Any, expected: Any, path: str) -> None:
    """Compare every declared field, retaining exact structural/order checks."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError(f"{path}: missing or unexpected fields")
        for key, value in expected.items():
            _same(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{path}: inventory mismatch")
        for index, value in enumerate(expected):
            _same(actual[index], value, f"{path}[{index}]")
    elif isinstance(expected, float):
        if (type(actual) not in (int, float) or not math.isfinite(actual)
                or not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)):
            raise ValueError(f"{path}: independently reconstructed number differs")
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError(f"{path}: independently reconstructed value differs")


def _calibration(plan: dict, bundle: dict) -> dict[str, dict]:
    rows = core.validate_calibration(plan, bundle)
    summaries = {}
    for parent in plan["parents"]:
        task, supports = parent["task_id"], len(parent["train"])
        losses = [[] for _ in _VIEWS]
        coverage = [0] * supports
        completed = []
        for held in range(supports):
            for view in _VIEWS:
                row = rows.get(f"{task}:support:{held}:view:{view}")
                if row is not None and row["status"] == "complete":
                    # The shared validator checks full causal answer/EOS masks
                    # and actual target count, not a truncated or prompt loss.
                    losses[view].append(row["nll_sum"] / row["spec"]["answer_tokens"])
                    coverage[held] += 1
                    completed.append(row)
        ready = (bundle["status"] == "complete" and supports > 1
                 and coverage == [8] * supports)
        means = [math.fsum(value / supports for value in values) for values in losses] if ready else [0.] * 8
        center = math.fsum(value / 8 for value in means)
        # T=1 is fixed before outcomes. Subtract the minimum only for numerical
        # stability: this is softmax(-(mean - center)/1), not a new temperature.
        exponents = [math.exp(-(value - min(means))) for value in means]
        total = math.fsum(exponents)
        weights = [value / total for value in exponents]
        underflow = sum(value == 0. for value in weights)
        status = ("complete" if ready else "single_demo_fallback" if supports == 1
                  else "partial_calibration_fallback")
        if underflow:
            ready, status, weights = False, "numeric_underflow_fallback", [1 / 8] * 8
        centered = [value - center for value in means]
        if not ready and not underflow:
            means = centered = None
        summaries[task] = {
            "weights": weights, "means": means, "centered_means": centered,
            "temperature": 1.0,
            "effective_view_count": 1 / math.fsum(value * value for value in weights),
            "weight_min": min(weights), "weight_max": max(weights),
            "weight_range": max(weights) - min(weights), "underflow_views": underflow,
            "status": status, "adaptation_eligible": ready, "support_count": supports,
            "support_view_coverage": coverage, "required_cells": 8 * supports if supports > 1 else 0,
            "completed_cells": len(completed), "support_token_mean_nll_by_view": losses,
            "completed_forward_calls": len(completed),
            "completed_input_tokens": sum(row["actual_input_tokens"] for row in completed),
            "completed_answer_tokens": sum(row["actual_answer_tokens"] for row in completed),
            "peak_allocated_bytes": max((row["memory"]["peak_allocated_bytes"] for row in completed
                if row["memory"] and "peak_allocated_bytes" in row["memory"]), default=None),
            "recorded_seconds": math.fsum(row["seconds"] for row in rows.values()
                                         if row["spec"]["task_id"] == task),
            "missing_or_failed_cost_unknown": not (supports == 1 or len(completed) == 8 * supports),
            "uncertainty": "LOO conditions overlap; supports/views are dependent; ESS describes concentration, not independent sample size",
        }
    return summaries


def _queries(plan: dict, summaries: dict, rows: dict) -> tuple[list[dict], dict]:
    queries = []
    counterfactual = {"calls": 0, "inputs": 0, "answers": 0}
    for parent in plan["parents"]:
        summary = summaries[parent["task_id"]]
        for query in parent["test"]:
            candidates, missing, failed, invalid = {}, [], [], []
            for view in _VIEWS:
                row = rows.get((query["query_id"], view))
                if row is None:
                    missing.append(view)
                elif row["status"] != "complete":
                    failed.append(view)
                else:
                    try:
                        grid = contract.inverse(contract.parse_answer(row["token_ids"]), view)
                    except ValueError:
                        invalid.append(view)
                        continue
                    key = _key(grid)
                    candidates.setdefault(key, {"canonical_key": key, "grid": grid, "views": []})["views"].append(view)
            for candidate in candidates.values():
                candidate["count"] = len(candidate["views"])
                candidate["weighted_vote"] = math.fsum(summary["weights"][view] for view in candidate["views"])
                for view in _VIEWS:
                    prompt = contract.prompt_ids(parent["train"], query["input"], view)
                    answer = contract.answer_ids(contract.transform(candidate["grid"], view))
                    counterfactual["calls"] += 1
                    counterfactual["inputs"] += len(prompt) + len(answer) - 1
                    counterfactual["answers"] += len(answer)
            uniform = sorted(candidates.values(), key=lambda item: (-item["count"], item["canonical_key"]))
            weighted = sorted(candidates.values(), key=lambda item: (-item["weighted_vote"], item["canonical_key"]))
            complete = not missing and not failed
            eligible = complete and summary["adaptation_eligible"]
            selected = weighted if eligible else uniform
            queries.append({
                "query_id": query["query_id"], "task_id": parent["task_id"], "test_index": query["test_index"],
                "pool_complete": complete, "missing_views": missing, "failed_views": failed,
                "invalid_views": invalid,
                "valid_view_weight": math.fsum(summary["weights"][view]
                    for candidate in candidates.values() for view in candidate["views"]),
                "invalid_view_weight_not_redistributed": math.fsum(summary["weights"][view] for view in invalid),
                "candidates": sorted(candidates.values(), key=lambda item: item["canonical_key"]),
                "uniform_ranking": [candidate["grid"] for candidate in uniform],
                "weighted_ranking": [candidate["grid"] for candidate in selected],
                "uniform_top2": [candidate["grid"] for candidate in uniform[:2]],
                "weighted_top2": [candidate["grid"] for candidate in selected[:2]],
                "adaptation_applied": eligible,
                "status": "complete" if eligible else "incomplete_pool_fallback" if not complete else summary["status"],
            })
    return queries, counterfactual


def _audit_ranking(plan: dict, calibration: dict, pool: dict, ranking: dict) -> tuple[dict, list[dict], dict]:
    summaries = _calibration(plan, calibration)
    raw = core.validate_pool(plan, calibration, pool)
    queries, rescoring = _queries(plan, summaries, raw)
    incomplete = any(value["missing_or_failed_cost_unknown"] for value in summaries.values())
    tokens = sum(value["completed_input_tokens"] for value in summaries.values())
    all_pools = all(query["pool_complete"] for query in queries)
    cost = {
        "calibration_completed_forward_calls": sum(value["completed_forward_calls"] for value in summaries.values()),
        "calibration_completed_input_tokens": tokens,
        "calibration_completed_answer_tokens": sum(value["completed_answer_tokens"] for value in summaries.values()),
        "calibration_recorded_seconds": math.fsum(value["recorded_seconds"] for value in summaries.values()),
        "calibration_peak_allocated_bytes": max((value["peak_allocated_bytes"] for value in summaries.values()
                                                if value["peak_allocated_bytes"] is not None), default=None),
        "calibration_missing_or_failed_cost_unknown": incomplete,
        "generation_recorded_calls": len(raw),
        "generation_recorded_prompt_tokens": sum(row["spec"]["prompt_tokens"] for row in raw.values()),
        "generation_recorded_output_tokens": sum(len(row["token_ids"]) for row in raw.values()),
        "generation_recorded_seconds": math.fsum(row["seconds"] for row in raw.values()),
        "same_pool_original_rescore_forward_calls_counterfactual": rescoring["calls"],
        "same_pool_original_rescore_input_tokens_counterfactual": rescoring["inputs"],
        "same_pool_original_rescore_answer_tokens_counterfactual": rescoring["answers"],
        "calibration_token_difference_vs_rescore": None if incomplete or not all_pools else tokens - rescoring["inputs"],
        "original_rescore_gpu_seconds": None, "gpu_time_saving": None,
        "uniform_vote_extra_forward_calls": 0,
        "qualification": "Counterfactual rescore token counts are exact for observed candidates, not measured runtime or FLOPs; incomplete work costs are lower bounds.",
    }
    expected = {
        "schema": "public-demo-ranking-v1", "plan_sha256": _digest(plan),
        "calibration_sha256": _digest(calibration), "pool_sha256": _digest(pool),
        "protocol_sha256": _digest(core.PROTOCOL), "execution_kind": calibration["execution_kind"],
        "calibration": summaries, "queries": queries,
        "fixed_task_denominator": _PARENTS, "fixed_query_denominator": _QUERIES,
        "all_pools_complete": all_pools,
        "all_eligible_calibrations_complete": all(value["status"] in ("complete", "single_demo_fallback") for value in summaries.values()),
        "cost": cost, "scientific_effectiveness_established": False,
        "qualification": "Receipt replay only; public and possibly exposed data; neither hashes nor CPU tests authenticate model execution or establish gain.",
    }
    _same(ranking, expected, "ranking")
    return summaries, queries, raw


def _audit_same_pool(plan: dict, result: dict, pool_rows: dict, queries: list[dict], session_complete: bool) -> dict:
    expected_ids = {query["query_id"] for parent in plan["parents"] for query in parent["test"]}
    source = result.get("queries", [])
    if not isinstance(source, list):
        raise ValueError("base query inventory must be a list")
    base_rows = {}
    for row in source:
        if not isinstance(row, dict):
            raise ValueError("invalid base query row")
        key = row.get("query_id")
        if key not in expected_ids or key in base_rows:
            raise ValueError("unexpected or duplicate base query")
        base_rows[key] = row
    late, differing_accepted_pools = [], []
    statuses = {"missing": 0, "failed": 0, "deadline": 0, "complete": 0}
    for query in queries:
        key = query["query_id"]
        base_query = base_rows.get(key, {})
        views = base_query.get("views", [])
        if not isinstance(views, list):
            raise ValueError("base views must be a list")
        by_view = {}
        for view in views:
            number = view.get("view") if isinstance(view, dict) else None
            if type(number) is not int or number not in _VIEWS or number in by_view:
                raise ValueError("invalid or duplicate base raw view")
            by_view[number] = view
        query_late = False
        for number in _VIEWS:
            base = by_view.get(number, {"status": "missing"})
            status = base.get("status")
            if status not in statuses:
                raise ValueError("unsupported base generation status")
            raw = pool_rows.get((key, number))
            mapped = status
            if status == "complete" and (base.get("termination") == "deadline"
                                         or raw is not None and raw["status"] == "deadline"):
                # The tracing adapter also detects a forward returning after
                # its deadline with EOS. The unchanged base receipt need not
                # say deadline in that case; the whole session must be partial.
                mapped = "deadline"
            statuses[mapped] += 1
            if mapped == "missing":
                if raw is not None or base.get("token_ids") not in (None, []):
                    raise ValueError("missing base view differs from paired pool")
                continue
            if raw is None or raw["status"] != mapped:
                raise ValueError("base and weighted raw view completion/failure status differs")
            tokens = base.get("token_ids")
            if tokens is None and mapped == "failed":
                tokens = []
            if type(tokens) is not list or tokens != raw["token_ids"]:
                raise ValueError("base and weighted raw token views differ")
            if base.get("prompt_sha256") is not None and base["prompt_sha256"] != raw["spec"]["prompt_sha256"]:
                raise ValueError("base and weighted generation prompts differ")
            if mapped == "deadline":
                if session_complete:
                    raise ValueError("late generation cannot belong to a completed session")
                late.append({"query_id": key, "view": number})
                query_late = True
        base_candidates = base_query.get("candidates", [])
        counts = {_key(candidate["grid"]): candidate["count"] for candidate in base_candidates}
        rebuilt = {candidate["canonical_key"]: candidate["count"] for candidate in query["candidates"]}
        if counts != rebuilt:
            # The original base worker calls a late EOS-bearing generation
            # complete. Preserve that evidence; never make a weighted claim
            # from this non-comparable accepted pool.
            if not query_late:
                raise ValueError("base and weighted accepted candidate pools differ")
            differing_accepted_pools.append(key)
    return {
        "raw_query_view_inventory_equal": True, "compared_query_view_cells": _QUERIES * 8,
        "status_mapping": "base complete with deadline termination or trace-observed lateness -> pool deadline in a partial session; failed None tokens -> []; missing -> absent",
        "mapped_view_status_counts": statuses, "late_generation_rows": late,
        "accepted_candidate_pools_equal": not differing_accepted_pools,
        "late_query_accepted_pool_differences": differing_accepted_pools,
    }


def _metrics(attempts: dict, expected: dict, parent_queries: dict, eligible: dict) -> dict:
    outcomes = {}
    for key, target in expected.items():
        candidates = attempts[key]
        if not isinstance(candidates, list) or len(candidates) > 2:
            raise ValueError("invalid strategy attempt inventory")
        for candidate in candidates:
            contract.validate_grid(candidate)
        if len(candidates) == 2 and candidates[0] == candidates[1]:
            raise ValueError("duplicate strategy attempts")
        outcomes[key] = [bool(candidates and candidates[0] == target), target in candidates]
    first = sum(value[0] for value in outcomes.values())
    second = sum(value[1] for value in outcomes.values())
    present = sum(bool(value) for value in attempts.values())
    return {
        "query_denominator": _QUERIES, "parent_denominator": _PARENTS,
        "queries_with_candidates": present, "queries_without_candidates": _QUERIES - present,
        "eligible_query_count": sum(eligible.values()), "ineligible_query_count": _QUERIES - sum(eligible.values()),
        "pass1_count": first, "pass2_count": second, "pass1": first / _QUERIES, "pass2": second / _QUERIES,
        "task_macro_pass1": math.fsum(sum(outcomes[key][0] for key in keys) / len(keys)
                                      for keys in parent_queries.values()) / _PARENTS,
        "task_macro_pass2": math.fsum(sum(outcomes[key][1] for key in keys) / len(keys)
                                      for keys in parent_queries.values()) / _PARENTS,
        "all_queries_task_pass2_count": sum(all(outcomes[key][1] for key in keys) for keys in parent_queries.values()),
        "per_query": outcomes,
    }


def _percentile(values: list[float], quantile: float) -> float:
    position = (len(values) - 1) * quantile
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def _comparison(name: str, reference: str, metrics: dict, parents: dict, complete: bool, kind: str) -> dict:
    a, b = metrics[name]["per_query"], metrics[reference]["per_query"]
    clusters = [{"task_id": task, "query_count": len(keys),
                 "pass2_success_count_difference": sum(int(a[key][1]) - int(b[key][1]) for key in keys)}
                for task, keys in parents.items()]
    differences = [cluster["pass2_success_count_difference"] for cluster in clusters]
    observed = sum(differences)
    # Integer sums avoid floating tie tolerances. One sign per parent, not one
    # per query; keeping /15 gives exactly the primary query-micro statistic.
    extreme = sum(abs(sum(value if bits & (1 << index) else -value
                          for index, value in enumerate(differences))) >= abs(observed)
                  for bits in range(1 << _PARENTS))
    rng = random.Random(_BOOTSTRAP_SEED)
    bootstrap = []
    for _ in range(_BOOTSTRAP_DRAWS):
        sample = [clusters[rng.randrange(_PARENTS)] for _ in range(_PARENTS)]
        bootstrap.append(sum(row["pass2_success_count_difference"] for row in sample)
                         / sum(row["query_count"] for row in sample))
    bootstrap.sort()
    return {
        "strategy": name, "reference": reference,
        "query_micro_pass2_difference": observed / _QUERIES,
        "task_macro_pass2_difference": metrics[name]["task_macro_pass2"] - metrics[reference]["task_macro_pass2"],
        "strategy_only": sum(a[key][1] and not b[key][1] for key in a),
        "reference_only": sum(b[key][1] and not a[key][1] for key in a),
        "clusters": clusters,
        "exact_parent_signflip": {
            "two_sided_pvalue": extreme / (1 << _PARENTS), "extreme_assignments": extreme,
            "enumerated_assignments": 1 << _PARENTS, "parent_cluster_count": _PARENTS,
            "nonzero_parent_differences": sum(value != 0 for value in differences),
            "statistic": "sum(parent signed query-success-count differences) / fixed 15 queries",
            "query_micro_weighting": "each query has weight 1/15; multi-query parents retain their query counts; one sign is shared within each parent",
            "assumption": "independent parent clusters and sign-exchangeable paired differences under the null; independence is an assumption, not proven by task IDs",
            "unadjusted_for_multiple_comparisons": True,
        },
        "descriptive_parent_cluster_bootstrap": {
            "confidence_level": .95, "interval": [_percentile(bootstrap, .025), _percentile(bootstrap, .975)],
            "draws": _BOOTSTRAP_DRAWS, "seed": _BOOTSTRAP_SEED,
            "method": "percentile; sample 12 whole parents with replacement; ratio of sampled success-count difference to sampled query count",
            "small_cluster_count_warning": True,
        },
        "complete_public_model_comparison": complete and kind == "public_model",
        "qualification": "Descriptive public-panel statistics only. Missing/ineligible attempts remain failures on the full denominator; incomplete or synthetic comparisons are not effect evidence. No generalization or causal guarantee.",
    }


def audit_predictions(plan, base_result, calibration, pool, ranking, session_complete):
    """Gold-free independent reconstruction before the evaluator opens labels."""
    core.validate_gold_free(plan)
    summaries, queries, raw = _audit_ranking(plan, calibration, pool, ranking)
    same_pool = _audit_same_pool(plan, base_result, raw, queries, session_complete)
    return summaries, queries, same_pool


def evaluate(plan: dict, gold: dict, base_result: dict, calibration: dict, pool: dict,
             ranking: dict, execution_kind: str, session_complete: bool, *, protocol_audit: dict | None = None) -> dict:
    """Audit sealed in-memory evidence, then score at the evaluator-only boundary.

    The caller must establish model-process exit and immutable byte sealing
    before calling. A separately recomputed complete ``protocol_audit`` is
    required for scientific_audit_complete; otherwise this is ranking replay
    only. ``session_complete`` is the caller's closure assertion, not
    a process-exit proof. This pure helper never reads an answer file or tunes
    a parameter. Ineligible weighted rows contribute empty attempts, never the
    production ranker's uniform fallback, to the fixed 12-parent/15-query score.
    """
    if execution_kind not in ("synthetic_cpu", "public_model") or type(session_complete) is not bool:
        raise ValueError("explicit execution kind and boolean session completion are required")
    core.validate_gold_free(plan)
    if len(plan["parents"]) != _PARENTS or sum(len(parent["test"]) for parent in plan["parents"]) != _QUERIES:
        raise ValueError("paired diagnostic requires the full 12-parent/15-query denominator")
    if calibration.get("execution_kind") != execution_kind or pool.get("execution_kind") != execution_kind:
        raise ValueError("execution kind differs from bound receipts")
    summaries, queries, same_pool = audit_predictions(plan, base_result, calibration, pool, ranking, session_complete)

    # Gold is first accessed below, after reconstruction/validation of every
    # gold-free selection. The unchanged auditor checks original vote/NLL ranks.
    from tools.public_sft141_diagnostic.evaluate import evaluate as evaluate_base
    base_audit = evaluate_base(plan, gold, base_result)
    parent_queries = {parent["task_id"]: [query["query_id"] for query in parent["test"]]
                      for parent in plan["parents"]}
    expected = {query["query_id"]: gold["answers"][parent["task_id"]][query["test_index"]]
                for parent in plan["parents"] for query in parent["test"]}
    base_rows = {row["query_id"]: row for row in base_result.get("queries", [])}
    weighted_rows = {query["query_id"]: query for query in queries}
    metrics, attempts, eligibility = {}, {}, {}
    for name in ("vote", "rescored", "demo_weighted"):
        attempts[name], eligibility[name] = {}, {}
        for key in expected:
            if name == "demo_weighted":
                eligible = weighted_rows[key]["adaptation_applied"]
                selected = weighted_rows[key]["weighted_top2"] if eligible else []
            else:
                row = base_rows.get(key, {})
                eligible = (len(row.get("views", [])) == 8
                            and all(view.get("status") == "complete" and view.get("termination") != "deadline"
                                    for view in row.get("views", [])))
                if name == "rescored":
                    eligible = eligible and row.get("rescoring_complete") is True
                selected = row.get(name, [])
            attempts[name][key], eligibility[name][key] = selected, bool(eligible)
        metrics[name] = _metrics(attempts[name], expected, parent_queries, eligibility[name])
        if name != "demo_weighted":
            for field, value in base_audit["coverage_inclusive_metrics"][name].items():
                _same(metrics[name][field], value, f"metrics.{name}.{field}")
    all_calibrations = all(value["status"] in ("complete", "single_demo_fallback") for value in summaries.values())
    all_pools = all(query["pool_complete"] for query in queries)
    late_nll = [{"query_id": row["query_id"], "candidate_index": index, "view": entry.get("view")}
                for row in base_rows.values() for index, candidate in enumerate(row.get("candidates", []))
                for entry in candidate.get("view_nll", [])
                if entry.get("status") == "deadline" or entry.get("termination") == "deadline"]
    protocol_complete = (isinstance(protocol_audit, dict) and protocol_audit.get("audit_passed") is True
                         and protocol_audit.get("strict_complete") is True)
    complete = (protocol_complete and base_audit["scientific_complete"] is True and all_calibrations and all_pools
                and not same_pool["late_generation_rows"] and not late_nll
                and same_pool["accepted_candidate_pools_equal"] and session_complete)
    paired_rows = [{"query_id": query["query_id"], "task_id": query["task_id"],
                    "test_index": query["test_index"],
                    **{f"{name}_{field}": metrics[name]["per_query"][query["query_id"]][index]
                       for name in metrics for index, field in enumerate(("pass1", "pass2"))},
                    "strategy_eligible": {name: eligibility[name][query["query_id"]] for name in metrics},
                    "demo_weighted_ineligibility": None if query["adaptation_applied"] else query["status"]}
                   for query in queries]
    comparisons = {}
    for name, reference in (("demo_weighted", "vote"), ("demo_weighted", "rescored"), ("rescored", "vote")):
        pair_complete = complete and all(eligibility[name].values()) and all(eligibility[reference].values())
        comparisons[f"{name}_minus_{reference}"] = _comparison(name, reference, metrics, parent_queries,
                                                              pair_complete, execution_kind)
    return {
        "protocol_trace_audit": protocol_audit,
        "protocol_trace_audit_required_for_scientific_completion": True,
        "schema": "public-calibrated-solver-evaluation-v1", "execution_kind": execution_kind,
        "session_complete": session_complete, "fixed_task_denominator": _PARENTS,
        "fixed_query_denominator": _QUERIES, "primary_metric": "query_micro_pass2",
        "sensitivity_metric": "task_macro_pass2", "scientific_audit_complete": complete,
        "scientific_effectiveness_established": False,
        "independent_audit": {
            "base_vote_and_full_answer_nll_audit": base_audit,
            "calibration_and_weighted_ranking_reconstructed": True,
            "all_eligible_calibrations_complete": all_calibrations, "all_pools_complete": all_pools,
            "same_pool": same_pool, "late_nll_rows": late_nll,
            "process_exit_and_sealing_must_be_verified_by_caller": True,
            "successful_audit_is_mechanics_not_model_authentication_or_effectiveness": True,
        },
        "coverage_inclusive_metrics": metrics, "paired": {"rows": paired_rows, "comparisons": comparisons},
        "calibration": summaries,
        "fallback_diagnostics": {
            "excluded_from_demo_weighted_metrics": True,
            "rows": [{"query_id": query["query_id"], "reason": query["status"],
                      "uniform_fallback_top2": query["weighted_top2"],
                      "scored_demo_weighted_attempts": []}
                     for query in queries if not query["adaptation_applied"]],
        },
        "qualification": "Public and possibly pretraining-exposed fixed panel, not hidden generalization or private-checkpoint reproduction. CPU fixtures validate mechanics only. Full 12/15 denominators are retained; incomplete calibration or pools never promote uniform fallback as weighted improvement. Statistical summaries are descriptive and cannot establish scientific effectiveness.",
    }

"""Pure training-only stability decisions; no data access or public gold inputs.

The caller constructs a fixed admitted train/dev canary and performs the actual
forwards through its physical meter. This helper cannot establish generalization
or substitute for autoregressive exact/grid/program checks.
"""
from __future__ import annotations

import math


def canary_decision(baseline, candidate, *, expected_ids, comparison_complete,
                    max_loss_ratio=1.05, min_improvement=0.0):
    """Compare complete matched token-weighted NLL receipts, deterministically.

    baseline/candidate are lists of {sample_id, nll_sum, token_count, valid}.
    expected_ids is the nonempty unique, frozen canary sample-ID sequence.
    comparison_complete must explicitly be True AND all rows must independently
    validate. A tolerated non-improvement is stable, but is never promoted.
    """
    if (type(max_loss_ratio) not in (int, float) or not math.isfinite(max_loss_ratio) or max_loss_ratio < 1 or
            type(min_improvement) not in (int, float) or not math.isfinite(min_improvement) or min_improvement < 0):
        raise ValueError("finite nonnegative stability thresholds required")
    if (type(expected_ids) not in (list, tuple) or not expected_ids or
            any(type(key) is not str or not key for key in expected_ids) or len(set(expected_ids)) != len(expected_ids)):
        raise ValueError("nonempty unique frozen canary sample IDs required")
    result = {"comparison_complete": False, "stable": False, "improved": False, "accepted": False,
              "reason": "incomplete_comparison", "expected_count": len(expected_ids),
              "max_loss_ratio": max_loss_ratio, "min_improvement": min_improvement,
              "selection_metric": "matched-completion-token-weighted-NLL", "generalization_claim": False}
    if comparison_complete is not True:
        return result
    def checked(rows):
        if type(rows) is not list or len(rows) != len(expected_ids):
            return None
        indexed = {}
        for row in rows:
            if (type(row) is not dict or row.get("sample_id") not in expected_ids or row["sample_id"] in indexed or
                    row.get("valid") is not True or type(row.get("token_count")) is not int or row["token_count"] <= 0 or
                    type(row.get("nll_sum")) not in (int, float) or not math.isfinite(row["nll_sum"]) or row["nll_sum"] < 0):
                return None
            indexed[row["sample_id"]] = row
        return indexed
    left, right = checked(baseline), checked(candidate)
    if left is None or right is None:
        result["reason"] = "missing_duplicate_or_invalid_canary_rows"
        return result
    if any(left[key]["token_count"] != right[key]["token_count"] for key in expected_ids):
        result["reason"] = "canary_token_counts_differ"
        return result
    ordered = sorted(expected_ids)
    count = sum(left[key]["token_count"] for key in ordered)
    base_nll = math.fsum(left[key]["nll_sum"] for key in ordered) / count
    candidate_nll = math.fsum(right[key]["nll_sum"] for key in ordered) / count
    stable = candidate_nll <= base_nll * max_loss_ratio
    improved = candidate_nll < base_nll and base_nll - candidate_nll >= min_improvement
    result.update(comparison_complete=True, stable=stable, improved=improved, accepted=stable and improved,
                  reason="improved" if stable and improved else ("loss_regression" if not stable else "no_improvement"),
                  baseline_mean_nll=base_nll, candidate_mean_nll=candidate_nll, token_count=count,
                  sample_count=len(ordered), loss_ratio=candidate_nll / base_nll if base_nll > 0 else None)
    return result

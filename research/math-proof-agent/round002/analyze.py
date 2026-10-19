"""Analyze fixed planned denominators; absence is unknown, never exclusion."""
from __future__ import annotations
from collections import Counter
import math
from common import digest, validate_scoring_identity


def generation_observed(row):
    return any("model_text" in event or event.get("model_cost", {}).get("consumed_prompt_tokens", 0) > 0
               for event in row.get("events", []))


def analyze(panel, records, seeds, expected_identities=None):
    arms = ("M-DIRECT", "M-SAMPLE", "M-REPAIR")
    if len({p["id"] for p in panel}) != len(panel) or len(set(seeds)) != len(seeds):
        raise ValueError("duplicate planned problem or seed")
    if records or expected_identities is not None:
        validate_scoring_identity(expected_identities)
        if expected_identities["panel_semantic_sha256"] != digest(panel):
            raise ValueError("analysis panel identity mismatch")
    lookup = {}
    for row in records:
        if expected_identities is None or row.get("identities") != expected_identities:
            raise ValueError("results must bind the expected source/model/protocol/panel identities")
        key = row["problem_id"], row["seed"], row["arm"]
        if key in lookup:
            raise ValueError("duplicate observation")
        lookup[key] = row
    expected = {(p["id"], s, a) for p in panel for s in seeds for a in arms}
    if set(lookup) - expected:
        raise ValueError("unplanned observation")
    by_id = {p["id"]: p for p in panel}
    for row in records:
        problem = by_id[row["problem_id"]]
        if row.get("statement_sha256") != problem["statement_sha256"]:
            raise ValueError("result statement identity mismatch")
        if row.get("answer_mode") != problem["answer_mode"]:
            raise ValueError("result answer mode mismatch")
        if row.get("status") == "proof_accepted":
            selected = [event for event in row.get("events", []) if event.get("status") == "accepted"]
            if len(selected) != 1:
                raise ValueError("proof success requires one selected candidate")
            tool = selected[0].get("tool", {})
            if (tool.get("proof_status") != "kernel_verified" or tool.get("trust_policy_passed") is not True
                    or tool.get("statement_sha256") != problem["statement_sha256"]):
                raise ValueError("proof success lacks matching trusted verifier receipt")
    summary = {}
    for arm in arms:
        counts = Counter()
        tokens = Counter()
        costs = Counter()
        for p in panel:
            for seed in seeds:
                row = lookup.get((p["id"], seed, arm), {})
                counts["generation_observed_rows"] += int(generation_observed(row))
                counts[row.get("status", "not_completed")] += 1
                if p["answer_mode"] == "find_answer":
                    counts["joint_denominator"] += 1
                    # No answer-proof binding is qualified. Never promote a
                    # caller-supplied success flag into a joint result.
                    counts["joint_unqualified"] += 1
                    counts["answer_correct"] += int(row.get("answer_status") == "correct")
                for key in ("verifier_setup_seconds", "wall_seconds"):
                    value = row.get(key)
                    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                        costs[key] += value
                    else:
                        costs[key + "_missing_rows"] += 1
                for event in row.get("events", []):
                    costs["generation_attempts"] += 1
                    costs["incomplete_model_cost_receipts"] += int(event.get("model_cost_complete") is not True)
                    costs["tool_calls"] += int(event.get("tool_attempted") is True)
                    if event.get("tool_attempted") is True:
                        value = event.get("tool_wall_seconds")
                        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                            costs["tool_wall_seconds"] += value
                        else:
                            costs["tool_wall_missing_calls"] += 1
                    for name, value in event.get("model_cost", {}).items():
                        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                            tokens[name] += value
        n = len(panel) * len(seeds)
        summary[arm] = {"planned": n, "counts": dict(counts), "observed_model_cost_lower_bound": dict(tokens),
                        "observed_execution_cost": dict(costs),
                        "cost_complete": (counts["not_completed"] == 0 and costs["incomplete_model_cost_receipts"] == 0
                                          and costs["wall_seconds_missing_rows"] == 0
                                          and costs["verifier_setup_seconds_missing_rows"] == 0
                                          and costs["tool_wall_missing_calls"] == 0),
                        "proof_rate": counts["proof_accepted"] / n if n and counts["generation_observed_rows"] else None,
                        "proof_rate_scope": "known successes over planned denominator; missing items retained; null when no generation observed",
                        "joint_rate": None,
                        "joint_status": "unqualified_answer_proof_binding" if counts["joint_denominator"] else "not_applicable"}
    paired = Counter()
    for p in panel:
        for seed in seeds:
            a = lookup.get((p["id"], seed, "M-SAMPLE"), {}).get("status")
            b = lookup.get((p["id"], seed, "M-REPAIR"), {}).get("status")
            if a is None or b is None:
                paired["incomplete_pair"] += 1
            else:
                paired["gain" if b == "proof_accepted" and a != b else
                       "loss" if a == "proof_accepted" and b != a else "tie"] += 1
    return {"arms": summary, "paired": dict(paired), "unit": "problem; seeds are repeated measures",
            "conclusion": "descriptive_pilot_only" if any(generation_observed(row) for row in records) else "not_estimable"}

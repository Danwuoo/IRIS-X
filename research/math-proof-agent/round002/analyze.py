"""Analyze fixed planned denominators; absence is unknown, never exclusion."""
from __future__ import annotations
from collections import Counter
import math
from common import digest, validate_scoring_identity
from evaluator import bound_answer_matches, supported_answer_problem


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
            if supported_answer_problem(problem) and not bound_answer_matches(selected[0], problem):
                raise ValueError("joint-task proof lacks exact candidate witness binding")
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
                    counts["joint_unqualified"] += int(not supported_answer_problem(p))
                    counts["joint_generation_observed_rows"] += int(generation_observed(row))
                    counts["answer_correct"] += int(row.get("answer_status") == "correct")
                    selected = next((event for event in row.get("events", []) if event.get("status") == "accepted"), {})
                    counts["joint_success"] += int(row.get("status") == "proof_accepted"
                                                   and row.get("joint_status") == "kernel_verified"
                                                   and row.get("answer_status") == "correct"
                                                   and bound_answer_matches(selected, p))
                    counts["evaluator_key_disagreements"] += int(row.get("joint_status") == "blocked_key_disagreement")
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
                        "joint_rate": (counts["joint_success"] / counts["joint_denominator"]
                                       if counts["joint_denominator"] and not counts["joint_unqualified"]
                                       and counts["joint_generation_observed_rows"] and not counts["evaluator_key_disagreements"] else None),
                        "joint_status": ("not_applicable" if not counts["joint_denominator"] else
                                         "unqualified_answer_proof_binding" if counts["joint_unqualified"] else
                                         "blocked_key_disagreement" if counts["evaluator_key_disagreements"] else
                                         "not_estimable" if not counts["joint_generation_observed_rows"] else "kernel_bound_witness")}
    paired = Counter()
    for p in panel:
        for seed in seeds:
            rows = [lookup.get((p["id"], seed, arm)) for arm in ("M-SAMPLE", "M-REPAIR")]
            if any(row is None for row in rows):
                paired["incomplete_pair"] += 1
            elif not all(generation_observed(row) for row in rows):
                paired["no_generation_pair"] += 1
            else:
                a, b = (row.get("status") for row in rows)
                paired["gain" if b == "proof_accepted" and a != b else
                       "loss" if a == "proof_accepted" and b != a else "tie"] += 1
    paired_joint = Counter()
    for p in panel:
        if p["answer_mode"] != "find_answer":
            continue
        for seed in seeds:
            rows = [lookup.get((p["id"], seed, arm)) for arm in ("M-SAMPLE", "M-REPAIR")]
            if not supported_answer_problem(p) or any(row is None for row in rows):
                paired_joint["incomplete_or_unqualified_pair"] += 1
                continue
            if not all(generation_observed(row) for row in rows):
                paired_joint["no_generation_pair"] += 1
                continue
            if any(row.get("joint_status") == "blocked_key_disagreement" for row in rows):
                paired_joint["blocked_key_disagreement"] += 1
                continue
            success = []
            for row in rows:
                selected = next((event for event in row.get("events", []) if event.get("status") == "accepted"), {})
                success.append(row.get("status") == "proof_accepted" and row.get("joint_status") == "kernel_verified"
                               and row.get("answer_status") == "correct" and bound_answer_matches(selected, p))
            a, b = success
            paired_joint["gain" if b and not a else "loss" if a and not b else "tie"] += 1
    return {"arms": summary, "paired": dict(paired), "paired_joint": dict(paired_joint), "unit": "problem; seeds are repeated measures",
            "conclusion": "descriptive_pilot_only" if any(generation_observed(row) for row in records) else "not_estimable"}

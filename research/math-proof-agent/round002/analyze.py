"""Analyze fixed planned denominators; absence is unknown, never exclusion."""
from __future__ import annotations
from collections import Counter


def analyze(panel, records, seeds, expected_identities=None):
    arms = ("M-DIRECT", "M-SAMPLE", "M-REPAIR")
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
    summary = {}
    for arm in arms:
        counts = Counter()
        tokens = Counter()
        for p in panel:
            for seed in seeds:
                row = lookup.get((p["id"], seed, arm), {})
                counts[row.get("status", "not_completed")] += 1
                if p["answer_mode"] == "find_answer":
                    counts["joint_denominator"] += 1
                    counts["joint_success"] += int(row.get("status") == "proof_accepted" and row.get("answer_status") == "correct")
                for event in row.get("events", []):
                    for name, value in event.get("model_cost", {}).items():
                        if isinstance(value, (int, float)):
                            tokens[name] += value
        n = len(panel) * len(seeds)
        summary[arm] = {"planned": n, "counts": dict(counts), "actual_model_cost": dict(tokens),
                        "proof_rate": counts["proof_accepted"] / n if n else None,
                        "joint_rate": counts["joint_success"] / counts["joint_denominator"] if counts["joint_denominator"] else None}
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
            "conclusion": "not_estimable" if not records else "descriptive_pilot_only"}

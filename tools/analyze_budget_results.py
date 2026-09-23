"""Write a compact evaluator-side paired report for Decision 0020."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

from irisx import arc_budget_ablation as budget
from irisx.transport import digest_path


ROOT = Path(".irisx/arc-agi-2/budget-ablation")
OLD = Path("C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot")


def _pair(left: dict[str, bool], right: dict[str, bool]) -> dict:
    if set(left) != set(right):
        raise RuntimeError("paired comparison case IDs differ")
    wins = sorted(task_id for task_id in left if right[task_id] and not left[task_id])
    losses = sorted(task_id for task_id in left if left[task_id] and not right[task_id])
    return {"left_correct": sum(left.values()), "right_correct": sum(right.values()),
            "wins": wins, "losses": losses, "net": len(wins) - len(losses)}


def main() -> int:
    diagnostic = json.loads((ROOT / "diagnostic/score.json").read_bytes())
    cohort = json.loads((ROOT / "cohort.json").read_bytes())
    ids = set(sum(cohort["strata"].values(), []))
    old_score = json.loads((OLD / "search/baseline-score.json").read_bytes())
    old_by_id = {record["task_id"]: record for record in old_score["records"] if record["task_id"] in ids}
    with zipfile.ZipFile(OLD / "repair-002/recovered-v1/result.zip") as archive:
        old_predictions = {record["task_id"]: record for record in json.loads(archive.read("predictions/predictions.json"))["records"] if record["task_id"] in ids}
    b0_records = []
    for task_id in sorted(ids):
        prediction = old_predictions[task_id]
        b0_records.append({"task_id": task_id, "group": "optimization-train", "arm": "B0", "job_key": f"{task_id}:B0",
                           "status": prediction["status"], "correct": old_by_id[task_id]["correct"],
                           "baseline_correct": old_by_id[task_id]["correct"],
                           "stop_reason": prediction["generation"]["stop_reason"],
                           "parse_state": prediction["generation"]["parse_state"],
                           "split_state": "thinking_off", "final_complete": prediction["generation"]["stop_reason"] == "eos_token",
                           "elapsed_seconds": prediction["timing"]["generation_seconds"],
                           "generated_tokens": prediction["tokens"]["generated"], "reasoning_tokens": 0,
                           "final_tokens": prediction["tokens"]["generated"]})
    summaries = {"B0": budget._summarize(b0_records), **diagnostic["arms"]}
    by_arm = {arm: {record["task_id"]: record["correct"] for record in records}
              for arm, records in {"B0": b0_records, **{arm: [record for record in diagnostic["records"] if record["arm"] == arm]
                                                        for arm in budget.ARMS}}.items()}
    pairs = {label: _pair(by_arm[left], by_arm[right]) for label, left, right in
             (("A1_vs_B0", "B0", "A1"), ("A2_vs_A1", "A1", "A2"),
              ("A3_vs_A2", "A2", "A3"), ("A2_vs_B0", "B0", "A2"), ("A3_vs_B0", "B0", "A3"))}
    gate = budget.choose_validation_arm(diagnostic)
    extra = {}
    for arm in budget.ARMS:
        net = pairs[f"{arm}_vs_B0"]["net"]
        extra[arm] = (summaries[arm]["elapsed_total_seconds"] - summaries["B0"]["elapsed_total_seconds"]) / net if net > 0 else None
    report = {"format": "irisx/arc-budget-analysis", "format_version": "1.0", "trial_id": budget.TRIAL_ID,
              "diagnostic_score_digest": digest_path(ROOT / "diagnostic/score.json"),
              "cohort_digest": digest_path(ROOT / "cohort.json"),
              "diagnostic": {"arms": summaries, "paired": pairs, "additional_generation_seconds_per_net_correct": extra,
                             "qualification": gate, "selected_on_historical_train_outcomes": True}}
    validation_path = ROOT / "validation/score.json"
    if validation_path.is_file():
        validation = json.loads(validation_path.read_bytes())
        report["validation"] = {"score_digest": digest_path(validation_path), "arms": validation["arms"],
                                "selection_dev_previously_used": True}
    budget.atomic_json(ROOT / "analysis.json", report)
    print(json.dumps({"diagnostic_correct": {arm: value["correct"] for arm, value in summaries.items()},
                      "qualified": gate["qualified_arms"], "selected": gate["selected_arm"],
                      "validation_available": "validation" in report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

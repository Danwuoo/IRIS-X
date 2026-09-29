"""Local public-development cell agreement for frozen ABC 003 candidates."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_combined import read
from tools.score_nvarc_abc_003_dev import ZIP, PLAN, PUBLIC, score


def diagnose() -> dict:
    evidence = score()
    plan = read(PLAN)
    solutions = read(PUBLIC / "arc-agi_training2_solutions.json")
    result = {"run_id": plan["run_id"], "zip_sha256": evidence["zip_sha256"], "tasks": {}}
    with zipfile.ZipFile(ZIP) as archive:
        for task_id in plan["task_ids"]:
            expected = solutions[task_id][0]
            task = {"expected_cells": sum(len(row) for row in expected), "arms": {}}
            for arm in (item["id"] for item in plan["arms"]):
                row = json.loads(archive.read(f"worker/{arm}-{task_id}.json"))
                candidates = [candidate["grid"] for candidate in row["ranked"]]
                agreements = []
                for candidate in candidates:
                    if (len(candidate) != len(expected) or
                            any(len(left) != len(right) for left, right in zip(candidate, expected))):
                        agreements.append(None)
                    else:
                        agreements.append(sum(left == right for predicted, actual in
                                              zip(candidate, expected) for left, right in
                                              zip(predicted, actual)))
                task["arms"][arm] = {"ranked_cell_agreement": agreements,
                    "ttt_steps": (row.get("ttt") or {}).get("steps")}
            result["tasks"][task_id] = task
    return result


if __name__ == "__main__":
    print(json.dumps(diagnose(), indent=2))

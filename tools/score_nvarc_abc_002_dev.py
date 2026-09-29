"""Score frozen ABC 002 on three public development parents, outside the solver."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_combined import read
from irisx.canonical import digest_value
from tools.analyze_nvarc_abc import inspect

PLAN = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-002.json"
ZIP = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-002-result.zip"
NVARC = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/source/NVARC"
PUBLIC = NVARC / "external/TinyRecursiveModels/kaggle/combined"
SOURCE_COMMIT = "846d0198efa752534594e321fc3289fc0a06c657"
SOLUTION_SHA256 = "9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9"
ZIP_SHA256 = "965ac0622546efe2d2e996e925ab376f4e219e5657d705cbe45685e8e060f37e"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score() -> dict:
    plan = read(PLAN)
    if plan["run_id"] != "nvarc-compact-abc-editor-002" or _sha(ZIP) != ZIP_SHA256:
        raise RuntimeError("frozen ABC 002 result binding differs")
    actual_commit = subprocess.run(["git", "-C", str(NVARC), "rev-parse", "HEAD"],
                                   capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if actual_commit != SOURCE_COMMIT:
        raise RuntimeError("public development source commit differs")
    challenge_path = PUBLIC / "arc-agi_training2_challenges.json"
    solution_path = PUBLIC / "arc-agi_training2_solutions.json"
    if (_sha(challenge_path) != plan["source_file_sha256"] or
            _sha(solution_path) != SOLUTION_SHA256):
        raise RuntimeError("public development challenge or solution bytes differ")
    challenges = read(challenge_path)
    solutions = read(solution_path)
    ids = tuple(plan["task_ids"])
    with zipfile.ZipFile(ZIP) as archive:
        visible = json.loads(archive.read("visible.json"))
    if set(visible) != set(ids) or any(
            visible[task_id] != challenges[task_id] or
            len(visible[task_id]["test"]) != 1 or
            any("output" in test for test in visible[task_id]["test"]) or
            len(solutions[task_id]) != 1
            for task_id in ids):
        raise RuntimeError("public development input/demo binding differs")
    truth = {task_id: {"test": [{"output": solutions[task_id][0]}]}
             for task_id in ids}
    analysis = inspect(ZIP, truth, plan_path=PLAN)
    arms = {}
    for arm, rows in analysis["arms"].items():
        clean = []
        for row in rows:
            if row["status"] != "complete":
                error_type = "missing-or-incomplete"
            elif row["oracle_coverage"] is False:
                error_type = "candidate-pool-miss"
            elif row["pass_at_1"] is False:
                error_type = "ranking-miss"
            else:
                error_type = "top-correct"
            clean.append({"task_id": row["task_id"], "status": row["status"],
                          "candidate_count": row["candidate_count"],
                          "generation_calls": row.get("generation_calls"),
                          "verification_calls": row.get("verification_calls"),
                          "pass_at_1": row["pass_at_1"], "pass_at_2": row["pass_at_2"],
                          "oracle_coverage": row["oracle_coverage"],
                          "error_type": error_type,
                          "previously_explored": row["previously_explored"]})
        arms[arm] = {"rows": clean, "totals": {metric: sum(x[metric] is True for x in clean)
                                              for metric in ("pass_at_1", "pass_at_2",
                                                             "oracle_coverage")}}
    return {"format": "irisx/nvarc-abc-002-public-dev-score-v1",
            "run_id": plan["run_id"], "plan_digest": digest_value(plan),
            "zip_sha256": ZIP_SHA256, "source_commit": SOURCE_COMMIT,
            "challenge_sha256": plan["source_file_sha256"],
            "solution_file_sha256": SOLUTION_SHA256,
            "split": "public-training2/dev-parents-repeatedly-examined",
            "task_ids": list(ids), "test_outputs_in_solver": False,
            "denominator_per_arm": len(ids), "arms": arms}


if __name__ == "__main__":
    print(json.dumps(score(), ensure_ascii=False, indent=2))

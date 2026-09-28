"""Verify a returned ABC ZIP; score only with an explicit isolated truth file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_abc import ARMS, TASKS
from irisx.arc_nvarc_analysis_zip_abc import verify_abc_zip
from irisx.arc_nvarc_combined import read
from irisx.arc_nvarc_data import grid
from irisx.canonical import digest_value

PLAN = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-001.json"
PUBLIC_STRATA = {"00576224": "2x2-to-6x6/public-palette-preserved",
                 "c9e6f938": "3x3-to-3x6/public-palette-preserved",
                 "0d3d703e": "3x3-to-3x3/public-palette-changes"}


def inspect(path: Path, truth: dict | None = None) -> dict:
    plan = read(PLAN)
    manifest = verify_abc_zip(path, run_id=plan["run_id"], plan_digest=digest_value(plan))
    with zipfile.ZipFile(path) as archive:
        def item(name):
            return json.loads(archive.read(name)) if name in manifest["files"] else None
        saved_plan = item("plan.json")
        if saved_plan is not None and saved_plan != plan:
            raise RuntimeError("returned ABC plan differs")
        terminal = item("aggregate-terminal.json")
        summary = {"format": "irisx/nvarc-abc-local-analysis-v1", "run_id": plan["run_id"],
                   "plan_digest": digest_value(plan), "zip_sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                   "terminal": terminal, "arms": {}, "scoring": "unknown-no-isolated-truth"}
        if truth is not None and set(truth) != set(TASKS):
            raise RuntimeError("isolated truth task coverage differs")
        for arm in ARMS:
            rows = []
            for task_id in TASKS:
                row = item("worker/" + arm + "-" + task_id + ".json")
                if row is None:
                    rows.append({"task_id": task_id, "status": "not-run-or-unretained",
                                 "public_shape_palette_stratum": PUBLIC_STRATA[task_id],
                                 "sft_parent_overlap": False,
                                 "previously_explored": task_id in plan["exploratory_previously_run_ids"],
                                 "candidate_count": None, "pass_at_1": None,
                                 "pass_at_2": None, "oracle_coverage": None})
                    continue
                ranked = row.get("ranked", [])
                record = {"task_id": task_id, "status": row["status"],
                          "public_shape_palette_stratum": PUBLIC_STRATA[task_id],
                          "sft_parent_overlap": False,
                          "previously_explored": task_id in plan["exploratory_previously_run_ids"],
                          "candidate_count": len(ranked) if "ranked" in row else None,
                          "generation_calls": row.get("generation_calls"),
                          "verification_calls": row.get("verification_calls"),
                          "pass_at_1": None, "pass_at_2": None, "oracle_coverage": None}
                if truth is not None and "ranked" in row:
                    expected = grid(truth[task_id]["test"][0]["output"])
                    values = [grid(x["grid"]) for x in ranked]
                    record.update(pass_at_1=bool(values and values[0] == expected),
                                  pass_at_2=any(x == expected for x in values[:2]),
                                  oracle_coverage=any(x == expected for x in values))
                rows.append(record)
            summary["arms"][arm] = rows
        if truth is not None:
            summary["scoring"] = "explicit-isolated-truth"
        return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--isolated-truth", type=Path,
                        help="Separate legally available evaluator file; never supplied to the notebook")
    args = parser.parse_args()
    truth = read(args.isolated_truth) if args.isolated_truth else None
    print(json.dumps(inspect(args.zip, truth), ensure_ascii=False, indent=2))

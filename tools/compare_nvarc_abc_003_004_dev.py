"""Compare frozen 003 and 004 candidate pools without exposing answer grids."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools.score_nvarc_abc_003_dev import ZIP as OLD_ZIP, score as old_score
from tools.score_nvarc_abc_004_dev import ZIP as NEW_ZIP, score as new_score


def compare() -> dict:
    old, new = old_score(), new_score()
    tasks = old["task_ids"]
    if tasks != new["task_ids"]:
        raise RuntimeError("public development task bindings differ")
    result = {"old_zip_sha256": old["zip_sha256"], "new_zip_sha256": new["zip_sha256"],
              "task_ids": tasks}
    with zipfile.ZipFile(OLD_ZIP) as left, zipfile.ZipFile(NEW_ZIP) as right:
        for old_arm, new_arm in (("A", "A"), ("B", "B"), ("C0", "C")):
            rows = {}
            for task_id in tasks:
                def pool(archive, arm):
                    row = json.loads(archive.read(f"worker/{arm}-{task_id}.json"))
                    return {json.dumps(item["grid"], separators=(",", ":"))
                            for item in row["ranked"]}
                a, b = pool(left, old_arm), pool(right, new_arm)
                rows[task_id] = {"old_candidates": len(a), "new_candidates": len(b),
                                 "shared_candidates": len(a & b),
                                 "new_only_candidates": len(b - a)}
            result[old_arm + "->" + new_arm] = rows
    return result


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))

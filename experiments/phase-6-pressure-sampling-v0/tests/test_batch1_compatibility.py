from __future__ import annotations

import subprocess
import json
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BASELINE = "a0ca60de39cc291fb9ad185d7de40cd6b4b5909d"
PROTECTED = (
    "experiments/capability-pressure-attribution-v0",
    "experiments/substrates/model-execution-qualification-v0",
    "irisx/core",
    "sources",
    "references/papers",
)


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=REPOSITORY_ROOT, check=True, text=True,
        encoding="utf-8", stdout=subprocess.PIPE,
    ).stdout.strip()


class Batch1CompatibilityTests(unittest.TestCase):
    def test_all_protected_trees_match_batch2_baseline(self) -> None:
        for path in PROTECTED:
            self.assertEqual(git("rev-parse", f"HEAD:{path}"), git("rev-parse", f"{BASELINE}:{path}"), path)

    def test_batch1_offline_summary_remains_result_a(self) -> None:
        summary = REPOSITORY_ROOT / "experiments/capability-pressure-attribution-v0/runs/batch-1-offline/summary.json"
        payload = json.loads(summary.read_bytes())
        self.assertTrue(payload["result_category"].startswith("Result A"))
        self.assertEqual(payload["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()

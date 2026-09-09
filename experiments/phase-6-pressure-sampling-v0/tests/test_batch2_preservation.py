from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BASELINE = "07a71392a59f78e41ca32f1c9c377e2a43be41e6"
PRESERVED = (
    "experiments/phase-6-pressure-sampling-v0/runs/batch-2",
    "research/phase-6-direct-pressure-sampling.md",
    "docs/phase-6-direct-pressure-sampling-handoff.md",
    "docs/plans/TEMP_PHASE_6_MECHANISM_FREE_DIRECT_PRESSURE_SAMPLING.md",
)


class Batch2PreservationTests(unittest.TestCase):
    def test_batch2_evidence_and_conclusions_match_required_baseline(self) -> None:
        completed = subprocess.run(
            ["git", "diff", "--exit-code", BASELINE, "--", *PRESERVED],
            cwd=REPOSITORY_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout.decode("utf-8", errors="replace"))

    def test_batch2_run_file_inventory_has_no_added_or_missing_files(self) -> None:
        relative_root = PRESERVED[0]
        expected = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", BASELINE, "--", relative_root],
            cwd=REPOSITORY_ROOT,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
        ).stdout.splitlines()
        root = REPOSITORY_ROOT / relative_root
        observed = sorted(
            path.relative_to(REPOSITORY_ROOT).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        )
        self.assertEqual(sorted(expected), observed)


if __name__ == "__main__":
    unittest.main()

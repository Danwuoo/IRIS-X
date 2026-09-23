"""The pre-version rejection repair has a new short, fail-closed identity."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_nvarc_4b_pilot_003 import stage  # noqa: E402


class FourBPilot003Tests(unittest.TestCase):
    def test_draft_metadata_and_notebook_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            summary = stage(Path(temp) / "stage")
            kernel = Path(summary["local_kernel_path"])
            meta = json.loads((kernel / "kernel-metadata.json").read_bytes())
            code = "".join(json.loads((kernel / "kaggle-notebook.ipynb").read_bytes())
                           ["cells"][0]["source"])
            self.assertFalse(summary["approved"])
            self.assertEqual(summary["run_id"], "nvarc-4b-compat-pilot-003")
            self.assertTrue(meta["id"].startswith("DRAFT-DO-NOT-PUSH/"))
            self.assertEqual(meta["title"], "IRIS-X 4B LoRA pilot 003")
            self.assertLessEqual(len(meta["title"]), 50)
            self.assertEqual(meta["competition_sources"],
                             ["arc-prize-2026-arc-agi-2"])
            self.assertTrue(meta["is_private"])
            self.assertFalse(meta["enable_internet"])
            self.assertIn("nvarc-4b-pilot-hardware-preflight.json", code)
            self.assertIn("arc-agi_training_challenges.json", code)
            self.assertNotIn("arc-agi_training_solutions.json", code)
            with self.assertRaisesRegex(RuntimeError, "no exact owner launch authorization"):
                exec(compile(code, "draft-notebook", "exec"), {})


if __name__ == "__main__":
    unittest.main()

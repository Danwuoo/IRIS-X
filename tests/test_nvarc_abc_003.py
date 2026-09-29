"""Boundaries for the distinct, truth-free ABC adaptation sensitivity save."""

from pathlib import Path
import unittest

from irisx.arc_nvarc_abc_003 import ARMS
from irisx.arc_nvarc_combined import read
from tools.stage_nvarc_abc_003 import PLAN, make_plan, metadata, save_fields

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-003-submission-final"


class ABCTuningBoundaries(unittest.TestCase):
    def test_control_treatments_and_total_ceiling(self):
        plan = read(PLAN)
        self.assertEqual(make_plan(), plan)
        self.assertEqual(ARMS, tuple(arm["id"] for arm in plan["arms"]))
        self.assertEqual([0, 0, 1, 2, 1],
                         [arm["ttt_steps_per_task"] for arm in plan["arms"]])
        self.assertEqual([5e-5, 5e-5, 1e-4],
                         [arm["adaptation_override"]["learning_rate"]
                          for arm in plan["arms"][2:]])
        self.assertEqual(30, plan["limits"]["maximum_total_generation_calls"])
        self.assertEqual(60, plan["limits"]["maximum_total_returned_sequences"])
        self.assertEqual(12, plan["limits"]["maximum_total_ttt_steps"])
        self.assertEqual(3072, plan["limits"]["maximum_total_ttt_training_tokens"])
        self.assertEqual(["arc-prize-2026-arc-agi-2"], metadata(plan)["competition_sources"])
        self.assertEqual("QUICK_SAVE", save_fields(PACKAGE)["kernel_execution_type"])


if __name__ == "__main__":
    unittest.main()

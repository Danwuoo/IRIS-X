"""Material routing and bounded save for paired base/SFT task TTT."""

from pathlib import Path
import unittest

from irisx.arc_nvarc_abc_005 import ARMS, BASE, SFT, material_for_arm
from irisx.arc_nvarc_combined import read
from irisx.errors import ValidationError
from tools.analyze_nvarc_abc import inspect
from tools.stage_nvarc_abc_005 import PLAN, make_plan, metadata, preflight, save_fields

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-005-submission"
PREDECESSOR = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-004-result.zip"
PREDECESSOR_PLAN = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-004.json"


class ABCPairedBoundaries(unittest.TestCase):
    def test_base_and_sft_arm_routes_are_distinct(self):
        self.assertEqual(("A", "AT", "B", "C"), ARMS)
        self.assertEqual(BASE, material_for_arm("A"))
        self.assertEqual(BASE, material_for_arm("AT"))
        self.assertEqual(SFT, material_for_arm("B"))
        self.assertEqual(SFT, material_for_arm("C"))
        with self.assertRaises(ValidationError):
            material_for_arm("C0")

    def test_exact_plan_and_quick_save_projection(self):
        plan = read(PLAN)
        self.assertEqual(make_plan(), plan)
        self.assertEqual([0, 1, 0, 1], [arm["ttt_steps_per_task"] for arm in plan["arms"]])
        self.assertEqual(["base", "base", "sft", "sft"],
                         [arm["checkpoint"] for arm in plan["arms"]])
        self.assertEqual(24, plan["limits"]["maximum_total_generation_calls"])
        self.assertEqual(48, plan["limits"]["maximum_total_returned_sequences"])
        self.assertEqual(6, plan["limits"]["maximum_total_ttt_steps"])
        self.assertEqual(["arc-prize-2026-arc-agi-2"], metadata(plan)["competition_sources"])
        self.assertEqual("QUICK_SAVE", save_fields(PACKAGE, retained_review=True)["kernel_execution_type"])
        # Historical success must never claim compatibility with changed main.
        with self.assertRaisesRegex(ValidationError, 'installed wheel source differs'):
            preflight(PACKAGE)

    def test_004_predecessor_analysis_has_three_approved_arms(self):
        result = inspect(PREDECESSOR, plan_path=PREDECESSOR_PLAN)
        self.assertEqual({"A", "B", "C"}, set(result["arms"]))
        self.assertEqual("unknown-no-isolated-truth", result["scoring"])


if __name__ == "__main__":
    unittest.main()

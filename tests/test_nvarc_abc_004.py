"""Bounded model beam and save boundaries for the distinct ABC 004 package."""

from pathlib import Path
import unittest

from irisx.arc_nvarc_abc_004 import ARMS, grammar_sequences
from irisx.arc_nvarc_combined import read
from irisx.errors import ValidationError
from tools.analyze_nvarc_abc import inspect
from tools.stage_nvarc_abc_004 import PLAN, make_plan, metadata, save_fields

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-004-submission"
PREDECESSOR = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-003-result.zip"
PREDECESSOR_PLAN = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-003.json"


class ABCBeamBoundaries(unittest.TestCase):
    def test_second_path_can_diverge_after_first_digit(self):
        grammar = {"status": "supported", "shape": [1, 2],
                   "legal_colors": [1, 2], "palette_rule": False}
        def logits(prefix):
            values = [-20.0] * 16
            if len(prefix) == 1:
                values[1], values[2] = 0.0, -5.0
            elif len(prefix) == 2:
                values[1], values[2] = 0.0, -0.1
            else:
                values[15] = 0.0
            return values
        result = grammar_sequences([99], logits, grammar,
                                   maximum_tokens=64, maximum_expansions=128)
        self.assertEqual([[1, 1, 15], [1, 2, 15]],
                         [row["tokens"] for row in result["sequences"]])
        self.assertEqual(5, result["expansions"])
        self.assertEqual("public-grammar-beam-complete", result["stop_reason"])
        with self.assertRaises(ValidationError):
            grammar_sequences([99], logits, grammar,
                              maximum_tokens=64, maximum_expansions=5)

    def test_exact_plan_and_quick_save_projection(self):
        plan = read(PLAN)
        self.assertEqual(make_plan(), plan)
        self.assertEqual(("A", "B", "C"), ARMS)
        self.assertEqual([0, 0, 1], [arm["ttt_steps_per_task"] for arm in plan["arms"]])
        self.assertEqual(18, plan["limits"]["maximum_total_generation_calls"])
        self.assertEqual(36, plan["limits"]["maximum_total_returned_sequences"])
        self.assertEqual(3, plan["limits"]["maximum_total_ttt_steps"])
        self.assertEqual(["arc-prize-2026-arc-agi-2"], metadata(plan)["competition_sources"])
        self.assertEqual("QUICK_SAVE", save_fields(PACKAGE)["kernel_execution_type"])

    def test_003_analysis_uses_all_five_approved_arms(self):
        result = inspect(PREDECESSOR, plan_path=PREDECESSOR_PLAN)
        self.assertEqual({"A", "B", "C0", "C2", "CH"}, set(result["arms"]))
        self.assertEqual("unknown-no-isolated-truth", result["scoring"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUBSTRATE / "scripts"))
import qualify  # noqa: E402


def view(outcome: str, evidence: str, cost: int) -> dict:
    return {
        "actual_outcome": outcome,
        "empirical_evidence_status": evidence,
        "runtime_cost": {"cost_units": cost},
    }


class RegressionSubstrateTests(unittest.TestCase):
    def test_regression_and_evidence_regression_are_independent_dimensions(self) -> None:
        dimensions = qualify.classify_change(
            view("success", "sufficient", 1),
            view("failure", "insufficient", 1),
        )
        self.assertEqual(dimensions, ["regression", "evidence_regression"])

    def test_improvement_and_cost_decrease_are_supported(self) -> None:
        dimensions = qualify.classify_change(
            view("failure", "insufficient", 3),
            view("success", "sufficient", 1),
        )
        self.assertEqual(dimensions, ["improvement", "cost_decrease"])

    def test_unchanged_failure_and_unchanged_success_are_supported(self) -> None:
        self.assertEqual(
            qualify.classify_change(
                view("failure", "insufficient", 1),
                view("failure", "insufficient", 1),
            ),
            ["unchanged_failure"],
        )
        self.assertEqual(
            qualify.classify_change(
                view("success", "sufficient", 1),
                view("success", "sufficient", 1),
            ),
            ["unchanged_success"],
        )

    def test_cost_increase_can_coexist_with_unchanged_success(self) -> None:
        self.assertEqual(
            qualify.classify_change(
                view("success", "sufficient", 1),
                view("success", "sufficient", 3),
            ),
            ["unchanged_success", "cost_increase"],
        )

    def test_identity_mismatch_invalidates_comparison(self) -> None:
        self.assertEqual(
            qualify.classify_change(
                view("success", "sufficient", 1),
                view("failure", "insufficient", 1),
                identity_equal=False,
            ),
            ["invalid_comparison"],
        )


if __name__ == "__main__":
    unittest.main()

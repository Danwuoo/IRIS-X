from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import pressure_tasks as tasks  # noqa: E402


class FailureAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        payload = tasks.load_object(ROOT / "definition/failure-attribution-rules.json")
        cls.rules = {row["id"]: row for row in payload["rules"]}

    def test_nonsemantic_failures_are_not_task_misses(self) -> None:
        for rule_id in (
            "admission-rejection", "identity-definition-binding-failure",
            "provider-systemic-failure", "verifier-integrity-failure",
        ):
            self.assertIsNot(self.rules[rule_id]["task_level_pressure_observed"], True, rule_id)
            self.assertEqual(self.rules[rule_id]["model_intrinsic_capability_failure"], "Not established")

    def test_valid_semantic_miss_preserves_bounded_attribution(self) -> None:
        rule = self.rules["valid-semantic-miss"]
        self.assertTrue(rule["task_level_pressure_observed"])
        self.assertEqual(rule["shortfall_axis"], "task_success")
        self.assertEqual(rule["failure_locus"], "execution_producer")
        self.assertEqual(rule["frozen_configuration_shortfall"], "directly_supported")
        for field in (
            "model_intrinsic_capability_failure", "retry_benefit",
            "stronger_allocation_benefit", "routing_benefit",
        ):
            self.assertEqual(rule[field], "Not established")

    def test_semantic_miss_requires_every_authority_precondition(self) -> None:
        self.assertEqual(len(self.rules["valid-semantic-miss"]["preconditions"]), 8)


if __name__ == "__main__":
    unittest.main()


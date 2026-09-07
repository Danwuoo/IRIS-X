from __future__ import annotations

import sys
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import assess_pressure as pressure  # noqa: E402


class FailureAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate_map, cls.vocabulary, _ = pressure.load_definitions()
        cases = pressure.load_cases(cls.gate_map, cls.vocabulary)
        cls.assessments = {
            item["case_id"]: pressure.assess_case(item, cls.gate_map, cls.vocabulary)
            for item in cases
            if item["suite"] == "attribution_boundaries"
        }

    def test_exactly_eight_collision_boundary_cases(self) -> None:
        self.assertEqual(len(self.assessments), 8)

    def test_configuration_failure_is_not_model_capability(self) -> None:
        record = self.assessments["attribution-configuration-not-capability"]
        self.assertEqual(record["failure_stage"], "admission_configuration")
        self.assertNotEqual(record["failure_stage"], "allocation_capability")
        self.assertEqual(record["trigger_results"]["general_recovery_retry"], "not_triggered")

    def test_two_collision_cases_preserve_ambiguity(self) -> None:
        ambiguous = [
            item for item in self.assessments.values() if item["attribution_status"] == "ambiguous"
        ]
        self.assertEqual(len(ambiguous), 2)
        self.assertTrue(all(item["failure_stage"] == "unknown" for item in ambiguous))

    def test_verifier_insufficiency_is_not_producer_failure(self) -> None:
        record = self.assessments["attribution-verifier-rejects-correct-output"]
        self.assertEqual(record["failure_stage"], "verification")
        self.assertNotEqual(record["failure_stage"], "execution_producer")

    def test_crossed_evidence_is_identity_authority_failure(self) -> None:
        record = self.assessments["attribution-crossed-identity-evidence"]
        self.assertEqual(record["shortfall_axes"], ["evidence"])
        self.assertEqual(record["failure_stage"], "identity_authority")

    def test_state_continuity_does_not_become_workflow_failure(self) -> None:
        record = self.assessments["attribution-restart-continuity-not-workflow"]
        self.assertEqual(record["failure_stage"], "state_continuity")
        self.assertEqual(record["trigger_results"]["H-W1"], "not_triggered")

    def test_control_flow_does_not_become_escalation(self) -> None:
        record = self.assessments["attribution-control-flow-not-escalation"]
        self.assertEqual(record["failure_stage"], "control_flow")
        self.assertEqual(record["trigger_results"]["H-C1"], "not_triggered")

    def test_cost_pressure_does_not_invent_task_failure(self) -> None:
        record = self.assessments["attribution-dominated-cost-with-success"]
        self.assertEqual(record["shortfall_axes"], ["lifecycle_cost"])
        self.assertEqual(record["failure_stage"], "resource_cost")
        self.assertNotIn("task_success", record["shortfall_axes"])


if __name__ == "__main__":
    unittest.main()


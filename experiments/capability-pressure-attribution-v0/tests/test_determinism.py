from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import assess_pressure as pressure  # noqa: E402
from summarize_assessments import summarize_assessments  # noqa: E402


class DeterminismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate_map, cls.vocabulary, _ = pressure.load_definitions()
        cls.cases = pressure.load_cases(cls.gate_map, cls.vocabulary)

    def test_same_frozen_input_produces_same_normalized_assessments(self) -> None:
        first = pressure.assess_all(self.cases, self.gate_map, self.vocabulary)
        second = pressure.assess_all(self.cases, self.gate_map, self.vocabulary)
        self.assertEqual(pressure.canonical_json_bytes(first), pressure.canonical_json_bytes(second))

    def test_fixture_order_does_not_change_per_case_semantics(self) -> None:
        forward = pressure.assess_all(self.cases, self.gate_map, self.vocabulary)
        reverse = pressure.assess_all(reversed(self.cases), self.gate_map, self.vocabulary)
        self.assertEqual(forward, reverse)

    def test_summary_generation_is_deterministic(self) -> None:
        assessments = pressure.assess_all(self.cases, self.gate_map, self.vocabulary)
        first = summarize_assessments(assessments, pressure.EXPECTED_GATE_IDS)
        second = summarize_assessments(reversed(assessments), pressure.EXPECTED_GATE_IDS)
        self.assertEqual(pressure.canonical_json_bytes(first), pressure.canonical_json_bytes(second))

    def test_malformed_case_cannot_partially_pass_a_gate(self) -> None:
        case = next(item for item in self.cases if item["case_id"] == "pressure-h-r1-positive")
        malformed = copy.deepcopy(case)
        del malformed["gate_predicates"]["H-R1"]["multiple_admissible_allocations_compared"]
        with self.assertRaisesRegex(pressure.AssessmentError, "predicate inventory mismatch"):
            pressure.validate_case(malformed, self.gate_map, self.vocabulary)

    def test_authoritative_payloads_have_no_timestamp_fields(self) -> None:
        assessments = pressure.assess_all(self.cases, self.gate_map, self.vocabulary)
        payload = pressure.canonical_json_bytes(assessments).decode("utf-8")
        self.assertNotIn("timestamp", payload)
        self.assertNotIn("created_at", payload)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import sys
import unittest
from collections import Counter
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import assess_pressure as pressure  # noqa: E402


class TriggerGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate_map, cls.vocabulary, _ = pressure.load_definitions()
        cls.cases = [
            item
            for item in pressure.load_cases(cls.gate_map, cls.vocabulary)
            if item["suite"] == "synthetic_pressure"
        ]

    def test_exactly_three_primary_cases_per_gate(self) -> None:
        counts = Counter(item["capability_trigger_candidates"][0] for item in self.cases)
        self.assertEqual(counts, Counter({gate_id: 3 for gate_id in pressure.EXPECTED_GATE_IDS}))

    def test_each_gate_has_negative_near_and_positive(self) -> None:
        for gate_id in pressure.EXPECTED_GATE_IDS:
            roles = {
                item["fixture_role"]
                for item in self.cases
                if item["capability_trigger_candidates"] == [gate_id]
            }
            self.assertEqual(roles, {"negative_control", "near_trigger", "synthetic_positive"})

    def test_surface_only_negatives_remain_not_triggered(self) -> None:
        for case in self.cases:
            if case["fixture_role"] != "negative_control":
                continue
            assessment = pressure.assess_case(case, self.gate_map, self.vocabulary)
            self.assertEqual(list(assessment["trigger_results"].values()), ["not_triggered"])

    def test_near_trigger_cases_remain_insufficient(self) -> None:
        for case in self.cases:
            if case["fixture_role"] != "near_trigger":
                continue
            assessment = pressure.assess_case(case, self.gate_map, self.vocabulary)
            self.assertEqual(
                list(assessment["trigger_results"].values()), ["insufficient_or_ambiguous"]
            )

    def test_synthetic_positives_trigger_fixture_only(self) -> None:
        for case in self.cases:
            if case["fixture_role"] != "synthetic_positive":
                continue
            assessment = pressure.assess_case(case, self.gate_map, self.vocabulary)
            self.assertEqual(list(assessment["trigger_results"].values()), ["triggered_by_fixture"])
            self.assertEqual(
                assessment["architecture_research_decision"],
                "fixture_only_no_direct_capability_decision",
            )

    def test_removing_each_required_positive_predicate_breaks_trigger(self) -> None:
        positives = {
            item["capability_trigger_candidates"][0]: item
            for item in self.cases
            if item["fixture_role"] == "synthetic_positive"
        }
        for gate_id, gate in self.gate_map.items():
            case = positives[gate_id]
            for predicate in gate["required_predicates"]:
                values = copy.deepcopy(case["gate_predicates"][gate_id])
                values[predicate] = False
                result = pressure.evaluate_gate(gate, values, "synthetic_fixture")
                self.assertEqual(result, "insufficient_or_ambiguous", (gate_id, predicate))

    def test_gate_predicate_inventory_fails_closed(self) -> None:
        gate = self.gate_map["H-G1"]
        with self.assertRaisesRegex(pressure.AssessmentError, "predicate inventory mismatch"):
            pressure.evaluate_gate(gate, {gate["required_predicates"][0]: True}, "synthetic_fixture")

    def test_all_gate_phase5_statuses_remain_not_triggered(self) -> None:
        self.assertTrue(
            all(item["trigger_status_at_phase5_close"] == "Not triggered" for item in self.gate_map.values())
        )


if __name__ == "__main__":
    unittest.main()


from __future__ import annotations

import sys
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import assess_pressure as pressure  # noqa: E402
from summarize_assessments import summarize_assessments  # noqa: E402


class Phase5ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate_map, cls.vocabulary, _ = pressure.load_definitions()
        cls.cases = [
            item
            for item in pressure.load_cases(cls.gate_map, cls.vocabulary)
            if item["suite"] == "historical_replay"
        ]
        cls.assessments = {
            item["case_id"]: pressure.assess_case(item, cls.gate_map, cls.vocabulary)
            for item in cls.cases
        }

    def test_two_selected_historical_replays_match(self) -> None:
        self.assertEqual(len(self.assessments), 2)
        self.assertTrue(all(item["expected_result_match"] for item in self.assessments.values()))
        self.assertTrue(all(not item["conflicts"] for item in self.assessments.values()))

    def test_batch4_remains_configuration_lineage(self) -> None:
        record = self.assessments["replay-phase5-batch4-configuration-lineage"]
        self.assertEqual(record["failure_stage"], "admission_configuration")
        self.assertEqual(record["attribution_status"], "directly_supported")
        self.assertEqual(record["trigger_results"]["H-C1"], "not_triggered")
        self.assertEqual(record["trigger_results"]["general_recovery_retry"], "not_triggered")
        self.assertEqual(record["historical_distinctions"]["retry_count"], 0)
        self.assertEqual(record["historical_distinctions"]["escalation_count"], 0)

    def test_batch6_shared_allocation_is_not_routing_evidence(self) -> None:
        record = self.assessments["replay-phase5-batch6-shared-allocation-family"]
        self.assertEqual(record["shortfall_axes"], [])
        self.assertEqual(record["attribution_status"], "not_attributable")
        self.assertEqual(record["trigger_results"]["H-R1"], "not_triggered")
        self.assertEqual(record["trigger_results"]["H-C1"], "not_triggered")
        self.assertEqual(record["trigger_results"]["general_recovery_retry"], "not_triggered")
        self.assertEqual(record["trigger_results"]["runtime_persistence"], "not_triggered")
        self.assertEqual(record["historical_distinctions"]["verified_successes"], 3)

    def test_replay_reads_do_not_modify_historical_sources(self) -> None:
        refs = [ref for case in self.cases for ref in case["source_refs"]]
        before = {
            ref["path"]: pressure.sha256_file(pressure.REPOSITORY_ROOT / ref["path"])
            for ref in refs
        }
        for case in self.cases:
            pressure.assess_case(case, self.gate_map, self.vocabulary)
        after = {
            ref["path"]: pressure.sha256_file(pressure.REPOSITORY_ROOT / ref["path"])
            for ref in refs
        }
        self.assertEqual(before, after)

    def test_direct_evidence_trigger_ledger_remains_empty(self) -> None:
        summary = summarize_assessments(self.assessments.values(), pressure.EXPECTED_GATE_IDS)
        self.assertTrue(all(not cases for cases in summary["direct_evidence_triggers_by_gate"].values()))


if __name__ == "__main__":
    unittest.main()

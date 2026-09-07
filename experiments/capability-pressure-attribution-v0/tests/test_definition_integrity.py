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


class DefinitionIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gates_document = pressure.load_json(pressure.GATES_PATH)
        self.vocabulary = pressure.load_json(pressure.VOCABULARY_PATH)
        self.schema = pressure.load_json(pressure.SCHEMA_PATH)
        self.gate_map = pressure.validate_definitions(
            self.gates_document, self.vocabulary, self.schema
        )

    def test_valid_definitions_and_all_34_cases_load(self) -> None:
        cases = pressure.load_cases(self.gate_map, self.vocabulary)
        self.assertEqual(len(self.gate_map), 8)
        self.assertEqual(len(cases), 34)

    def test_duplicate_gate_ids_reject(self) -> None:
        document = copy.deepcopy(self.gates_document)
        document["gates"][1]["gate_id"] = document["gates"][0]["gate_id"]
        with self.assertRaisesRegex(pressure.DefinitionError, "duplicate gate ID"):
            pressure.validate_definitions(document, self.vocabulary, self.schema)

    def test_missing_required_gate_field_rejects(self) -> None:
        document = copy.deepcopy(self.gates_document)
        del document["gates"][0]["negative_controls"]
        with self.assertRaisesRegex(pressure.DefinitionError, "missing required fields"):
            pressure.validate_definitions(document, self.vocabulary, self.schema)

    def test_unknown_gate_id_rejects(self) -> None:
        document = copy.deepcopy(self.gates_document)
        document["gates"][0]["gate_id"] = "H-UNKNOWN"
        with self.assertRaisesRegex(pressure.DefinitionError, "unknown or missing gate IDs"):
            pressure.validate_definitions(document, self.vocabulary, self.schema)

    def test_invalid_attribution_status_vocabulary_rejects(self) -> None:
        vocabulary = copy.deepcopy(self.vocabulary)
        vocabulary["attribution_statuses"].append("certain")
        with self.assertRaisesRegex(pressure.DefinitionError, "invalid attribution_statuses"):
            pressure.validate_definitions(self.gates_document, vocabulary, self.schema)

    def test_synthetic_evidence_cannot_claim_direct_trigger(self) -> None:
        case = next(
            item
            for item in pressure.load_cases(self.gate_map, self.vocabulary)
            if item["case_id"] == "pressure-h-g1-positive"
        )
        case = copy.deepcopy(case)
        case["expected_trigger_results"]["H-G1"] = "triggered_by_direct_evidence"
        with self.assertRaisesRegex(
            pressure.DefinitionError, "synthetic evidence cannot masquerade"
        ):
            pressure.validate_case(case, self.gate_map, self.vocabulary)

    def test_direct_repository_evidence_requires_source_refs(self) -> None:
        case = next(
            item
            for item in pressure.load_cases(self.gate_map, self.vocabulary)
            if item["case_id"] == "pressure-h-w1-negative"
        )
        case = copy.deepcopy(case)
        case["evidence_class"] = "direct_repository_evidence"
        case["source_refs"] = []
        with self.assertRaisesRegex(pressure.DefinitionError, "requires source references"):
            pressure.validate_case(case, self.gate_map, self.vocabulary)

    def test_malformed_source_reference_rejects(self) -> None:
        case = next(
            item
            for item in pressure.load_cases(self.gate_map, self.vocabulary)
            if item["case_id"] == "replay-phase5-batch4-configuration-lineage"
        )
        case = copy.deepcopy(case)
        case["source_refs"][0]["sha256"] = "not-a-digest"
        with self.assertRaisesRegex(pressure.DefinitionError, "malformed source reference"):
            pressure.validate_case(case, self.gate_map, self.vocabulary)

    def test_assessment_schema_requires_layer_separation_fields(self) -> None:
        schema = copy.deepcopy(self.schema)
        schema["required_fields"].remove("architecture_research_decision")
        with self.assertRaisesRegex(pressure.DefinitionError, "missing required record fields"):
            pressure.validate_definitions(self.gates_document, self.vocabulary, schema)


if __name__ == "__main__":
    unittest.main()


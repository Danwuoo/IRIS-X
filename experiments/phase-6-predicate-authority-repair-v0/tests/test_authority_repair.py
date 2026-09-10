from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import derive_repair as repair  # noqa: E402
import validate_repair as validator  # noqa: E402


class PredicateAuthorityRepairTests(unittest.TestCase):
    def test_definition_and_evaluator_identities_validate(self) -> None:
        result = validator.validate(require_run=False)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["batch3_terminal_source_count"], 6)

    def test_existing_any_equals_is_any_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary)
            paths = []
            for index, value in enumerate((False, False, False, True, False, False)):
                path = source_root / f"source-{index}.json"
                path.write_text(json.dumps({"observed": value}), encoding="utf-8")
                paths.append({"path": path.name, "pointer": "/observed"})
            rule = {
                "derivation_rule_id": "test-any-match-v0",
                "expected": True,
                "gate_id": "test",
                "operator": "any_equals",
                "predicate_id": "any_match",
                "sources": paths,
            }
            rule["derivation_rule_sha256"] = repair.engine.rule_sha256(rule)
            record = repair.engine.derive_rule(rule, source_root=source_root)
            self.assertEqual(record["predicate_value"], "true")

    def test_all_batch3_terminal_sources_are_hash_and_pointer_bound(self) -> None:
        derived = repair.derive_all()
        record = next(
            row for row in derived["predicate_records"]
            if row["predicate_id"] == "cheaper_admitted_configuration_misses_requirement"
        )
        self.assertEqual(record["predicate_value"], "true")
        self.assertEqual(len(record["source_refs"]), 6)
        self.assertEqual(
            [source["observed_value"] for source in record["source_refs"]],
            [False, False, False, True, False, False],
        )
        for source in record["source_refs"]:
            self.assertTrue(source["path"].startswith("runs/batch-3/"))
            self.assertEqual(source["pointer_or_field"], "/attribution/task_level_pressure_observed")
            self.assertEqual(len(source["sha256"]), 64)
        repair.engine.validate_source_refs(record, source_root=repair.SOURCE_ROOT)

    def test_hc1_first_prerequisite_is_not_hc1_trigger(self) -> None:
        derived = repair.derive_all()
        records = {
            row["predicate_id"]: row["predicate_value"]
            for row in derived["predicate_records"] if row["gate_id"] == "H-C1"
        }
        self.assertEqual(records["cheaper_admitted_configuration_misses_requirement"], "true")
        self.assertEqual(records["stronger_candidate_resolves_miss"], "unknown")
        self.assertEqual(records["decision_relevant_tradeoff_established"], "unknown")
        self.assertEqual(derived["gate_results"]["H-C1"], "insufficient_or_ambiguous")

    def test_retry_benefit_remains_unknown_and_untriggered(self) -> None:
        derived = repair.derive_all()
        record = next(row for row in derived["predicate_records"] if row["gate_id"] == "retry-recovery")
        self.assertEqual(record["predicate_value"], "unknown")
        self.assertEqual(derived["gate_results"]["retry-recovery"], "insufficient_or_ambiguous")

    def test_all_eight_gate_statuses_and_zero_triggers(self) -> None:
        derived = repair.derive_all()
        self.assertEqual(derived["gate_results"], repair.EXPECTED_GATE_RESULTS)
        self.assertNotIn("triggered_by_direct_evidence", derived["gate_results"].values())

    def test_repeated_derivation_is_byte_identical(self) -> None:
        first = repair.engine.pretty_json_bytes(repair.derive_all())
        second = repair.engine.pretty_json_bytes(repair.derive_all())
        self.assertEqual(first, second)

    def test_manual_boolean_override_remains_prohibited(self) -> None:
        definition = repair.load_definition()
        request = {"rule": definition["rules"][0], "predicate_value": "true"}
        with self.assertRaisesRegex(repair.engine.PredicateDerivationError, "manual direct predicate override"):
            repair.engine.derive_request(request, source_root=repair.SOURCE_ROOT)

    def test_bad_rule_hash_fails_closed(self) -> None:
        definition = repair.load_definition()
        rule = dict(definition["rules"][0])
        rule["expected"] = "manual"
        with self.assertRaisesRegex(repair.engine.PredicateDerivationError, "rule hash mismatch"):
            repair.engine.derive_rule(rule, source_root=repair.SOURCE_ROOT)

    def test_source_hash_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary)
            source = source_root / "source.json"
            source.write_text('{"observed":true}\n', encoding="utf-8")
            rule = {
                "derivation_rule_id": "test-source-drift-v0",
                "expected": True,
                "gate_id": "test",
                "operator": "equals",
                "predicate_id": "source_drift",
                "sources": [{"path": "source.json", "pointer": "/observed"}],
            }
            rule["derivation_rule_sha256"] = repair.engine.rule_sha256(rule)
            record = repair.engine.derive_rule(rule, source_root=source_root)
            source.write_text('{"observed":false}\n', encoding="utf-8")
            with self.assertRaisesRegex(repair.engine.PredicateDerivationError, "source hash mismatch"):
                repair.engine.validate_source_refs(record, source_root=source_root)


if __name__ == "__main__":
    unittest.main()

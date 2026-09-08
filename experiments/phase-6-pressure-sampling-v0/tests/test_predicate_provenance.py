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

import derive_direct_predicates as predicates  # noqa: E402
import pressure_tasks as tasks  # noqa: E402


def frozen_rule(**overrides):
    rule = {
        "derivation_rule_id": "test-rule-v0",
        "gate_id": "test-gate",
        "predicate_id": "test-predicate",
        "operator": "equals",
        "expected": True,
        "sources": [{"path": "source.json", "pointer": "/observed"}],
    }
    rule.update(overrides)
    rule["derivation_rule_sha256"] = predicates.rule_sha256(rule)
    return rule


class PredicateProvenanceTests(unittest.TestCase):
    def test_direct_source_ref_and_hash_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.json").write_text('{"observed":true}\n', encoding="utf-8")
            record = predicates.derive_rule(frozen_rule(), source_root=root)
            self.assertEqual(record["predicate_value"], "true")
            predicates.validate_source_refs(record, source_root=root)

    def test_source_hash_mismatch_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "source.json"
            path.write_text('{"observed":true}\n', encoding="utf-8")
            record = predicates.derive_rule(frozen_rule(), source_root=root)
            path.write_text('{"observed":false}\n', encoding="utf-8")
            with self.assertRaisesRegex(predicates.PredicateDerivationError, "source hash mismatch"):
                predicates.validate_source_refs(record, source_root=root)

    def test_bad_source_pointer_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.json").write_text('{"observed":true}\n', encoding="utf-8")
            rule = frozen_rule(sources=[{"path": "source.json", "pointer": "/absent"}])
            with self.assertRaisesRegex(predicates.PredicateDerivationError, "pointer not found"):
                predicates.derive_rule(rule, source_root=root)

    def test_derivation_rule_hash_mismatch_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.json").write_text('{"observed":true}\n', encoding="utf-8")
            rule = frozen_rule()
            rule["expected"] = False
            with self.assertRaisesRegex(predicates.PredicateDerivationError, "rule hash mismatch"):
                predicates.derive_rule(rule, source_root=root)

    def test_manual_direct_predicate_override_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = {"rule": frozen_rule(), "predicate_value": "true"}
            with self.assertRaisesRegex(predicates.PredicateDerivationError, "manual direct predicate override"):
                predicates.derive_request(request, source_root=Path(temporary))

    def test_missing_observation_remains_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = predicates.derive_rule(frozen_rule(), source_root=Path(temporary))
            self.assertEqual(record["predicate_value"], "unknown")
            self.assertEqual(record["derivation_status"], "missing_observation")

    def test_contradictory_observations_become_conflicting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "one.json").write_text('{"observed":true}\n', encoding="utf-8")
            (root / "two.json").write_text('{"observed":false}\n', encoding="utf-8")
            rule = frozen_rule(
                operator="consensus_equals",
                sources=[
                    {"path": "one.json", "pointer": "/observed"},
                    {"path": "two.json", "pointer": "/observed"},
                ],
            )
            record = predicates.derive_rule(rule, source_root=root)
            self.assertEqual(record["predicate_value"], "conflicting")

    def test_synthetic_evidence_cannot_masquerade_as_direct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = {"rule": frozen_rule(), "evidence_class": "synthetic_fixture"}
            with self.assertRaisesRegex(predicates.PredicateDerivationError, "synthetic evidence"):
                predicates.derive_request(request, source_root=Path(temporary))

    def test_resolved_direct_predicate_requires_source_refs(self) -> None:
        record = {
            "predicate_record_id": "x", "gate_id": "g", "predicate_id": "p",
            "predicate_value": "true", "evidence_class": "direct_repository_evidence",
            "derivation_rule_id": "r", "derivation_rule_sha256": "0" * 64,
            "source_refs": [], "derivation_status": "derived", "derivation_notes": "x",
        }
        with self.assertRaisesRegex(predicates.PredicateDerivationError, "requires source refs"):
            predicates.validate_predicate_record(record)

    def test_negative_control_is_not_a_veto(self) -> None:
        gate = {"gate_id": "g", "required_predicates": ["p"]}
        positive = [{"gate_id": "g", "predicate_id": "p", "predicate_value": "true"}]
        result = predicates.evaluate_gate(gate, positive, negative_controls=[{"surface_only": True}])
        self.assertEqual(result, "triggered_by_direct_evidence")

    def test_surface_negative_control_does_not_trigger_by_itself(self) -> None:
        gate = {"gate_id": "g", "required_predicates": ["p"]}
        result = predicates.evaluate_gate(gate, [], negative_controls=[{"surface_only": True}])
        self.assertNotEqual(result, "triggered_by_direct_evidence")

    def test_genuine_negative_control_contradiction_is_ambiguous(self) -> None:
        gate = {"gate_id": "g", "required_predicates": ["p"]}
        positive = [{"gate_id": "g", "predicate_id": "p", "predicate_value": "true"}]
        control = {"conflicts_with_predicate_id": "p", "conflict_observed": True}
        self.assertEqual(
            predicates.evaluate_gate(gate, positive, negative_controls=[control]),
            "insufficient_or_ambiguous",
        )

    def test_prelaunch_gate_semantics_match_frozen_scope(self) -> None:
        derived = predicates.derive_all(source_root=ROOT)
        self.assertEqual(derived["gate_results"]["H-G1"], "not_triggered")
        self.assertEqual(derived["gate_results"]["H-W1"], "not_triggered")
        self.assertEqual(derived["gate_results"]["H-C1"], "insufficient_or_ambiguous")
        self.assertEqual(derived["gate_results"]["H-R1"], "not_triggered")
        self.assertEqual(derived["gate_results"]["persistence"], "not_triggered")
        self.assertEqual(derived["gate_results"]["nondeterministic-verifier"], "not_triggered")
        self.assertEqual(derived["gate_results"]["external-action"], "not_triggered")
        self.assertEqual(derived["gate_results"]["retry-recovery"], "insufficient_or_ambiguous")
        self.assertNotIn("triggered_by_direct_evidence", derived["gate_results"].values())


if __name__ == "__main__":
    unittest.main()

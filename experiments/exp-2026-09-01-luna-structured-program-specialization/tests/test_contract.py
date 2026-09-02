from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT / "scripts"))
import common  # noqa: E402


class HPIaContractTests(unittest.TestCase):
    def test_frozen_artifact_hashes_match_exact_bytes(self) -> None:
        identities = common.load_json(common.DEFINITION / "artifact-identities.json")
        for record in identities["artifacts"].values():
            path = Path(record["path"])
            if not path.is_absolute():
                path = common.ROOT / path if str(path).startswith(("experiments", "research", "docs", "tools")) else common.EXPERIMENT / path
            self.assertEqual(common.sha_file(path), record["sha256"], record["path"])
            self.assertEqual(path.stat().st_size, record["bytes"], record["path"])

    def test_seed_is_reasonable_bounded_utf8_and_shared_by_c0_c2(self) -> None:
        seed = common.SEED_PROGRAM_PATH.read_bytes()
        self.assertEqual(common.validate_program(seed), [])
        self.assertLessEqual(len(seed), 12_288)
        self.assertTrue(seed.endswith(b"\n"))
        self.assertNotIn(b"\r\n", seed)
        definition = common.load_json(common.DEFINITION / "experiment-definition.json")
        self.assertEqual(definition["configurations"]["C0"]["program"], definition["configurations"]["C2"]["program"])

    def test_output_schema_accepts_exact_family_envelopes_and_rejects_extra(self) -> None:
        schema = common.load_json(common.OUTPUT_SCHEMA_PATH)
        validator = Draft202012Validator(schema)
        examples = {
            "traceability-extraction-v0": {"direct_references": ["DOC-2"]},
            "terminology-consistency-v0": {"violations": []},
            "path-action-guard-v0": {"decisions": []},
            "structured-simulation-v0": {"records": [], "changed_paths": []},
        }
        for family_id, answer in examples.items():
            value = {"schema_version": 1, "instance_id": "i", "family_id": family_id, "answer": answer}
            self.assertFalse(list(validator.iter_errors(value)))
            value["extra"] = True
            self.assertTrue(list(validator.iter_errors(value)))

    def test_exact_family_provider_schemas_are_preflight_clean(self) -> None:
        paths = common.frozen_provider_schema_paths()
        self.assertEqual(len(paths), 6)
        for schema_id, path in paths.items():
            self.assertEqual(common.provider_schema_findings(common.load_json(path)), [], schema_id)
        examples = {
            "traceability-extraction-v0": {"direct_references": ["DOC-2"]},
            "terminology-consistency-v0": {"violations": []},
            "path-action-guard-v0": {"decisions": []},
            "structured-simulation-v0": {"records": [], "changed_paths": []},
        }
        for family_id, answer in examples.items():
            schema = common.load_json(common.provider_output_schema_path(family_id))
            value = {"schema_version": 1, "instance_id": "i", "family_id": family_id, "answer": answer}
            self.assertFalse(list(Draft202012Validator(schema).iter_errors(value)))

    def test_preflight_rejects_prior_deterministic_provider_errors(self) -> None:
        all_of_schema = {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
            "allOf": [],
        }
        findings = common.provider_schema_findings(all_of_schema)
        self.assertTrue(any("allOf" in finding for finding in findings))
        missing_type = {
            "type": "object",
            "properties": {"schema_version": {"const": 1}},
            "required": ["schema_version"],
            "additionalProperties": False,
        }
        findings = common.provider_schema_findings(missing_type)
        self.assertTrue(any("missing-explicit-type" in finding for finding in findings))

    def test_optimizer_schema_const_has_explicit_integer_type(self) -> None:
        schema = common.load_json(common.OPTIMIZER_SCHEMA_PATH)
        self.assertEqual(schema["properties"]["schema_version"], {"type": "integer", "const": 1})
        self.assertEqual(common.provider_schema_findings(schema), [])

    def test_clear_terminal_failure_is_canonical(self) -> None:
        record = {
            "actual_outcome": "failure",
            "empirical_evidence_status": "sufficient",
            "acceptance_decision": "not_applicable",
            "terminal_execution_status": "failed",
        }
        common.validate_terminal_semantics(record)
        record["actual_outcome"] = "Unknown"
        with self.assertRaises(ValueError):
            common.validate_terminal_semantics(record)

    def test_generator_reproduction_and_public_oracle_sufficiency(self) -> None:
        seed = "11" * 32
        with tempfile.TemporaryDirectory(prefix="irisx-hp1a-test-") as temporary:
            inventory = common.generate_split(
                "dev",
                seed,
                1,
                Path(temporary) / "dev",
                "not-applicable-preoptimization-split",
                common.git_head(),
                common.git_head(),
            )
            self.assertEqual(inventory["total_instances"], 4)
            self.assertTrue(all(inventory["audit"].values()))

    def test_evaluator_separates_acceptance_from_empirical_success(self) -> None:
        instance = common.GENERATOR.generate_instance(
            "traceability-extraction-v0",
            1234,
            "not-applicable",
            common.sha_file(common.GENERATOR_PATH),
            {"count": 4},
        )
        instance["manifest"].update({"split": "dev", "evaluator_id": "test", "evaluator_version_sha256": "test"})
        wrong = {
            "schema_version": 1,
            "instance_id": instance["manifest"]["instance_id"],
            "family_id": instance["manifest"]["family_id"],
            "answer": {"direct_references": []},
        }
        result = common.output_evaluation(instance, common.canonical_bytes(wrong))
        self.assertEqual(result["acceptance_decision"], "accept")
        self.assertEqual(result["actual_outcome"], "failure")
        self.assertEqual(result["joint_interpretation"], "false_success")

    def test_selection_prefers_verified_success_before_resource_ties(self) -> None:
        base = {
            "verified_success_count": 1,
            "actual_success_count": 1,
            "false_success_count": 0,
            "malformed_output_count": 0,
            "invalid_terminal_count": 0,
            "model_calls": 16,
            "input_tokens": "Unknown",
            "output_tokens": "Unknown",
            "reasoning_tokens": "Unknown",
            "total_wall_time_ns": 100,
        }
        better = dict(base, verified_success_count=2, total_wall_time_ns=1000)
        self.assertLess(
            common.selection_key(better, b"b", common.sha_bytes(b"b")),
            common.selection_key(base, b"a", common.sha_bytes(b"a")),
        )


if __name__ == "__main__":
    unittest.main()

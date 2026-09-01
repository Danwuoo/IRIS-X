from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUBSTRATE / "scripts"))
import dry_run  # noqa: E402


TASK = dry_run.load_json(SUBSTRATE / "inputs" / "dry-run-task.json")
SUCCESS_PATH = SUBSTRATE / "candidates" / "success-candidate.json"
FAILURE_PATH = SUBSTRATE / "candidates" / "failure-candidate.json"


class ExecutionContractTests(unittest.TestCase):
    def test_hidden_oracle_never_enters_candidate_input(self) -> None:
        package = dry_run.candidate_visible_package(TASK)
        dry_run.assert_candidate_package_separation(package)
        encoded = json.dumps(package, sort_keys=True)
        self.assertNotIn("hidden_oracle", encoded)
        self.assertNotIn("generation_seed", encoded)
        self.assertNotIn("evaluator_id", encoded)

    def test_modifying_candidate_changes_sha(self) -> None:
        original = dry_run.candidate_identity(SUCCESS_PATH)
        with tempfile.TemporaryDirectory(prefix="irisx-specialization-candidate-") as temporary:
            changed_path = Path(temporary) / "candidate.json"
            changed = dry_run.load_json(SUCCESS_PATH)
            changed["program_or_workflow_definition"] += " Changed."
            changed_path.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
            changed_identity = dry_run.candidate_identity(changed_path)
        self.assertNotEqual(original["candidate_sha256"], changed_identity["candidate_sha256"])

    def test_generation_manifest_binds_candidate_sha(self) -> None:
        identity = dry_run.candidate_identity(SUCCESS_PATH)
        manifest = dry_run.generation_manifest(TASK, identity)
        self.assertEqual(manifest["candidate_freeze_sha"], identity["candidate_sha256"])
        self.assertTrue(manifest["generated_after_candidate_sha_computed"])

    def test_success_and_failure_paths_keep_separate_ledgers_and_unknown_cost(self) -> None:
        success = dry_run.run_candidate(SUCCESS_PATH, TASK)
        failure = dry_run.run_candidate(FAILURE_PATH, TASK)
        self.assertEqual(success["terminal_execution_status"], "completed")
        self.assertTrue(success["verified_success_eligibility"])
        self.assertTrue(success["evaluator_invoked"])
        self.assertEqual(failure["terminal_execution_status"], "failed")
        self.assertEqual(failure["actual_outcome"], "failure")
        self.assertEqual(failure["empirical_evidence_status"], "sufficient")
        self.assertFalse(failure["evaluator_invoked"])
        self.assertIsNotNone(failure["error"])
        for record in (success, failure):
            self.assertIn("design_time_cost_ledger", record)
            self.assertIn("runtime_cost_ledger", record)
            self.assertEqual(record["design_time_cost_ledger"]["provider_cost_usd"], "Unknown")
            self.assertEqual(record["runtime_cost_ledger"]["provider_cost_usd"], "Unknown")
            self.assertEqual(record["model_calls"], 0)
            self.assertEqual(record["paid_api_calls"], 0)

    def test_canonical_vocabulary_rejects_historical_placeholders(self) -> None:
        record = dry_run.run_candidate(FAILURE_PATH, TASK)
        dry_run.validate_terminal_semantics(record)
        for field, forbidden in (
            ("actual_outcome", "Unknown"),
            ("empirical_evidence_status", "unavailable"),
        ):
            changed = dict(record)
            changed[field] = forbidden
            with self.assertRaises(ValueError):
                dry_run.validate_terminal_semantics(changed)

    def test_clear_failure_and_genuinely_unresolved_are_distinct(self) -> None:
        failure = dry_run.adjudicate_terminal_noncompletion(completion_known=True)
        unresolved = dry_run.adjudicate_terminal_noncompletion(completion_known=False)
        self.assertEqual(failure["actual_outcome"], "failure")
        self.assertEqual(failure["empirical_evidence_status"], "sufficient")
        self.assertEqual(unresolved["actual_outcome"], "unresolved")
        self.assertEqual(unresolved["empirical_evidence_status"], "unresolved")

    def test_new_manifest_commit_fields_require_full_resolving_shas(self) -> None:
        head = dry_run.git_head()
        dry_run.require_full_commit_sha(head, "definition_commit")
        dry_run.require_full_commit_sha(head, "code_commit")
        with self.assertRaises(ValueError):
            dry_run.require_full_commit_sha(head[:12], "definition_commit")

    def test_existing_run_directory_cannot_be_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(prefix="irisx-specialization-run-") as temporary:
            with self.assertRaises(FileExistsError):
                dry_run.ensure_new_run(Path(temporary))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from irisx.arc_prompt_kaggle import KaggleCandidateEvaluator
from irisx import arc_prompt_optimizer as optimizer
from irisx.canonical import digest_value, write_json
from irisx.errors import ValidationError


class PromptOptimizerTests(unittest.TestCase):
    def test_ledger_counts_attempt_before_proposal_finishes(self) -> None:
        score = {
            "trial_id": optimizer.TRIAL_ID,
            "run_id": optimizer.RUN_ID,
            "bindings": {"run_identity_digest": "sha256:" + "1" * 64, "outbound_digest": "sha256:" + "2" * 64, "result_digest": "sha256:" + "3" * 64},
            "groups": {"optimization-train": {"correct": 1, "denominator": 2, "accuracy": 0.5}, "selection-dev": {"correct": 1, "denominator": 2, "accuracy": 0.5}},
            "holdout": {"opened": False, "scored": False, "record_count": 0},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "score.json", score)
            optimizer.initialize_ledger(root / "ledger.json", root / "score.json")
            optimizer.begin_proposal_attempt(root / "ledger.json", parent_candidate="B1", parent_instruction=optimizer.BASE_INSTRUCTION)
            ledger = optimizer.load_ledger(root / "ledger.json")
            self.assertEqual(1, ledger["budget"]["proposal_attempts_used"])
            self.assertEqual("running", ledger["rounds"][0]["proposal_status"])

    def test_duplicate_proposal_is_recorded_and_skips_gpu(self) -> None:
        score = {
            "trial_id": optimizer.TRIAL_ID,
            "run_id": optimizer.RUN_ID,
            "bindings": {"run_identity_digest": "sha256:" + "1" * 64, "outbound_digest": "sha256:" + "2" * 64, "result_digest": "sha256:" + "3" * 64},
            "groups": {"optimization-train": {"correct": 1, "denominator": 2, "accuracy": 0.5}, "selection-dev": {"correct": 1, "denominator": 2, "accuracy": 0.5}},
            "holdout": {"opened": False, "scored": False, "record_count": 0},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "score.json", score)
            optimizer.initialize_ledger(root / "ledger.json", root / "score.json")
            optimizer.begin_proposal_attempt(root / "ledger.json", parent_candidate="B1", parent_instruction=optimizer.BASE_INSTRUCTION)
            item = optimizer.finish_proposal_attempt(root / "ledger.json", instruction=optimizer.BASE_INSTRUCTION, status="valid", wall_seconds=1.0, input_digest="sha256:" + "4" * 64, output_digest="sha256:" + "5" * 64)
            self.assertTrue(item["duplicate"])
            self.assertEqual("skipped", item["gpu_status"])

    def test_codex_request_uses_at_most_three_complete_examples_and_32k(self) -> None:
        examples = [{"inputs": {"task": str(index)}, "outputs": {"grid": [[index]]}, "feedback": "wrong"} for index in range(5)]
        prompt, evidence = optimizer.build_codex_proposal_request({"solve": "current"}, {"solve": examples}, ["solve"])
        self.assertLessEqual(evidence["reflective_example_count"], 3)
        self.assertLessEqual(len(prompt.encode("utf-8")), optimizer.MAX_PROPOSER_INPUT_BYTES)
        self.assertEqual(digest_value("current"), evidence["parent_instruction_digest"])

    def test_codex_request_rejects_multiple_components(self) -> None:
        with self.assertRaises(ValidationError):
            optimizer.build_codex_proposal_request({"a": "x", "b": "y"}, {"a": [], "b": []}, ["a", "b"])

    def test_duplicate_dataset_versions_can_be_reconciled_once(self) -> None:
        score = {
            "trial_id": optimizer.TRIAL_ID,
            "run_id": optimizer.RUN_ID,
            "bindings": {"run_identity_digest": "sha256:" + "1" * 64, "outbound_digest": "sha256:" + "2" * 64, "result_digest": "sha256:" + "3" * 64},
            "groups": {"optimization-train": {"correct": 1, "denominator": 2, "accuracy": 0.5}, "selection-dev": {"correct": 1, "denominator": 2, "accuracy": 0.5}},
            "holdout": {"opened": False, "scored": False, "record_count": 0},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "score.json", score)
            ledger_path = root / "ledger.json"
            optimizer.initialize_ledger(ledger_path, root / "score.json")
            optimizer.begin_proposal_attempt(ledger_path, parent_candidate="B1", parent_instruction=optimizer.BASE_INSTRUCTION)
            item = optimizer.finish_proposal_attempt(ledger_path, instruction="new", status="valid", wall_seconds=1.0, input_digest="sha256:" + "4" * 64, output_digest="sha256:" + "5" * 64)
            optimizer.record_candidate_staged(ledger_path, round_index=1, run_id="run", run_identity_digest="sha256:" + "6" * 64, configuration_digest="sha256:" + "7" * 64, outbound_digest="sha256:" + "8" * 64, dataset_version=3)
            write_json(root / "incident.json", {"versions": [3, 4, 5]})
            item = optimizer.reconcile_duplicate_dataset_versions(ledger_path, round_index=1, observed_version=5, duplicate_versions=[3, 4, 5], evidence_path=root / "incident.json")
            self.assertEqual("dataset-ready", item["gpu_status"])
            self.assertEqual(5, item["dataset_version"])
            self.assertEqual(0, item["generation_invocations"])
            self.assertEqual("duplicate-identical-dataset-versions", item["incidents"][0]["type"])

    def test_dataset_upload_waits_when_old_version_still_reports_ready(self) -> None:
        score = {
            "trial_id": optimizer.TRIAL_ID,
            "run_id": optimizer.RUN_ID,
            "bindings": {"run_identity_digest": "sha256:" + "1" * 64, "outbound_digest": "sha256:" + "2" * 64, "result_digest": "sha256:" + "3" * 64},
            "groups": {"optimization-train": {"correct": 1, "denominator": 2, "accuracy": 0.5}, "selection-dev": {"correct": 1, "denominator": 2, "accuracy": 0.5}},
            "holdout": {"opened": False, "scored": False, "record_count": 0},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "score.json", score)
            ledger_path = root / "ledger.json"
            optimizer.initialize_ledger(ledger_path, root / "score.json")
            optimizer.begin_proposal_attempt(ledger_path, parent_candidate="B1", parent_instruction=optimizer.BASE_INSTRUCTION)
            optimizer.finish_proposal_attempt(ledger_path, instruction="new", status="valid", wall_seconds=1.0, input_digest="sha256:" + "4" * 64, output_digest="sha256:" + "5" * 64)
            item = optimizer.record_candidate_staged(ledger_path, round_index=1, run_id="run", run_identity_digest="sha256:" + "6" * 64, configuration_digest="sha256:" + "7" * 64, outbound_digest="sha256:" + "8" * 64, dataset_version=3)
            evaluator = object.__new__(KaggleCandidateEvaluator)
            evaluator.search_root = root
            evaluator.ledger_path = ledger_path
            statuses = iter([
                {"status": "ready", "current_version_number": 2},
                {"status": "ready", "current_version_number": 2},
                {"status": "updating", "current_version_number": 2},
                {"status": "ready", "current_version_number": 3},
            ])
            evaluator._dataset_status = lambda: next(statuses)
            commands = []
            evaluator._run = lambda arguments: commands.append(arguments)
            with mock.patch("irisx.arc_prompt_kaggle.time.sleep"):
                item = evaluator._upload_dataset(1, item)
            self.assertEqual("dataset-ready", item["gpu_status"])
            self.assertEqual(1, len(commands))
            self.assertEqual(["kaggle", "datasets", "version"], commands[0][:3])


if __name__ == "__main__":
    unittest.main()

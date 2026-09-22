from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()

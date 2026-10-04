"""Synthetic-only conformance checks for the offline competition exporter."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import arc_kaggle_submission as export


def challenges():
    return {"a": {"train": [{"input": [[1]], "output": [[2]]}],
                  "test": [{"input": [[3]]}, {"input": [[4]]}]},
            "b": {"train": [{"input": [[5]], "output": [[6]]}],
                  "test": [{"input": [[7]]}]}}


class KaggleSubmissionTests(unittest.TestCase):
    def test_multitest_order_two_attempts_and_full_denominator(self):
        records = [{"task_id": "a", "tests": [
            {"test_index": 1, "attempts": [[[8]], [[9]]]},
            {"test_index": 0, "attempts": [[[2]]]}]}]
        original = copy.deepcopy(records)
        result, audit = export.build_submission(challenges(), records)
        self.assertEqual(result["a"][0], {"attempt_1": [[2]], "attempt_2": [[2]]})
        self.assertEqual(result["a"][1], {"attempt_1": [[8]], "attempt_2": [[9]]})
        self.assertEqual(result["b"][0], {"attempt_1": [[0]], "attempt_2": [[0]]})
        self.assertEqual((audit["task_count"], audit["test_output_count"]), (2, 3))
        self.assertEqual(audit["tests_without_model_candidates"], 1)
        self.assertEqual(audit["model_attempt_slots_missing"], 3)
        self.assertFalse(audit["correctness_scored"])
        self.assertEqual(original, records)

    def test_entire_failed_run_retains_every_test(self):
        result, audit = export.build_submission(challenges(), [])
        self.assertEqual(sum(len(rows) for rows in result.values()), 3)
        self.assertEqual(audit["tests_without_model_candidates"], 3)
        self.assertEqual(audit["model_supplied_attempts"], 0)

    def test_boolean_float_ragged_empty_oversized_or_out_of_palette_grids_fail(self):
        for value in ([[True]], [[1.0]], [[-1]], [[10]], [], [[]], [[1], [1, 2]],
                      [[1] * 31], [[1]] * 31):
            with self.subTest(value=value), self.assertRaises(export.SubmissionError):
                export.grid(value)

    def test_truth_cannot_enter_challenges(self):
        raw = challenges(); raw["a"]["test"][0]["output"] = [[0]]
        with self.assertRaisesRegex(export.SubmissionError, "truth"):
            export.build_submission(raw, [])

    def test_failed_test_is_audited_and_cannot_claim_candidates(self):
        records = [{"task_id": "a", "tests": [
            {"test_index": 0, "attempts": [], "status": "timeout", "missing_attempts": 2}]}]
        _, audit = export.build_submission(challenges(), records)
        self.assertEqual(audit["rows"][0]["input_test_status"], "timeout")
        self.assertEqual(audit["tests_without_model_candidates"], 3)
        records[0]["tests"][0]["attempts"] = [[[1]]]
        with self.assertRaisesRegex(export.SubmissionError, "failed test"):
            export.build_submission(challenges(), records)

    def test_status_and_missing_attempt_count_must_agree(self):
        for fields in ({"status": "complete", "attempts": []},
                       {"status": "missing-candidate", "attempts": [[[1]], [[2]]]},
                       {"missing_attempts": True, "attempts": [[[1]]]},
                       {"missing_attempts": 0, "attempts": [[[1]]]}):
            records = [{"task_id": "a", "tests": [{"test_index": 0, **fields}]}]
            with self.subTest(fields=fields), self.assertRaises(export.SubmissionError):
                export.build_submission(challenges(), records)

    def test_omitted_tests_preserve_declared_task_failure(self):
        _, audit = export.build_submission(challenges(), [
            {"task_id": "a", "status": "timeout", "tests": []}])
        self.assertEqual(audit["task_status_counts"], {"timeout": 1, "not_supplied": 1})
        self.assertEqual(audit["rows"][0]["input_task_status"], "timeout")
        self.assertEqual(audit["rows"][0]["input_test_status"], "not_supplied")
        self.assertEqual(audit["rows"][1]["input_task_status"], "timeout")
        self.assertEqual(audit["tests_without_model_candidates"], 3)

    def test_task_status_is_validated_even_without_test_rows(self):
        for status in ("unknown", None, [], {}, True, 1):
            with self.subTest(status=status), self.assertRaises(export.SubmissionError):
                export.build_submission(challenges(), [
                    {"task_id": "a", "status": status, "tests": []}])

    def test_declared_complete_task_cannot_hide_omitted_tests(self):
        for tests in ([], [{"test_index": 0, "attempts": [[[1]], [[2]]]}]):
            with self.assertRaisesRegex(export.SubmissionError, "complete task"):
                export.build_submission(challenges(), [
                    {"task_id": "a", "status": "complete", "tests": tests}])

    def test_extra_ids_duplicate_tasks_indices_and_third_attempt_fail(self):
        good = {"task_id": "a", "tests": [{"test_index": 0, "attempts": [[[1]]]}]}
        invalid = [
            [{"task_id": "unknown", "tests": []}], [good, good],
            [{"task_id": "a", "tests": good["tests"] * 2}],
            [{"task_id": "a", "tests": [{"test_index": True, "attempts": []}]}],
            [{"task_id": "a", "tests": [{"test_index": 2, "attempts": []}]}],
            [{"task_id": "a", "tests": [{"test_index": 0, "attempts": [[[1]]] * 3}]}],
        ]
        for records in invalid:
            with self.subTest(records=records), self.assertRaises(export.SubmissionError):
                export.build_submission(challenges(), records)

    def test_submission_missing_task_test_or_attempt_is_rejected(self):
        full, _ = export.build_submission(challenges(), [])
        variants = []
        value = copy.deepcopy(full); del value["b"]; variants.append(value)
        value = copy.deepcopy(full); value["a"].pop(); variants.append(value)
        value = copy.deepcopy(full); del value["a"][0]["attempt_2"]; variants.append(value)
        value = copy.deepcopy(full); value["a"][0]["attempt_3"] = [[0]]; variants.append(value)
        for value in variants:
            with self.assertRaises(export.SubmissionError):
                export.validate_submission(challenges(), value)

    def test_duplicate_json_keys_and_nonfinite_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            for body in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
                path.write_text(body)
                with self.assertRaises(export.SubmissionError):
                    export.load_json(path)

    def test_cli_is_offline_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "challenges.json").write_text(json.dumps(challenges()))
            (root / "records.json").write_text("[]")
            command = [sys.executable, "-S", str(Path(export.__file__)),
                       "--challenges", str(root / "challenges.json"),
                       "--records", str(root / "records.json"),
                       "--output", str(root / "submission.json"),
                       "--audit-output", str(root / "audit.json")]
            first = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = (root / "submission.json").read_bytes()
            second = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(before, (root / "submission.json").read_bytes())
            self.assertEqual(export.load_json(root / "audit.json")["test_output_count"], 3)


if __name__ == "__main__":
    unittest.main()

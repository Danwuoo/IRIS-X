"""Regression tests for the Stage 1 ARC-AGI-1 local-reference core."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from spex_arc.domain.arc_a1 import (  # noqa: E402
    CandidateSet,
    Grid,
    Prediction,
    parse_candidate_set_json,
    parse_task_json,
)
from spex_arc.evaluator.arc_a1 import (  # noqa: E402
    EVALUATOR_VERSION,
    LOCAL_REFERENCE_STATUS,
    LocalReferenceEvaluator,
    Submission,
    build_submission,
    load_evaluator_identity,
    parse_submission_json,
    read_submission,
    serialize_submission,
    write_submission,
)


FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "arc_a1"
RULES_PATH = REPOSITORY_ROOT / "artifacts" / "arc-agi-1" / "rules.json"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class ArcA1EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        identity_result = load_evaluator_identity(RULES_PATH)
        assert identity_result.value is not None, identity_result.failures
        cls.identity = identity_result.value
        evaluator_result = LocalReferenceEvaluator.from_rules_snapshot(RULES_PATH)
        assert evaluator_result.value is not None, evaluator_result.failures
        cls.evaluator = evaluator_result.value

    def task(self, fixture_name: str, task_id: str):
        result = parse_task_json(fixture_text(fixture_name), task_id)
        self.assertTrue(result.valid, result.failures)
        assert result.value is not None
        return result.value

    def candidate_set(self, fixture_name: str):
        result = parse_candidate_set_json(fixture_text(fixture_name))
        self.assertTrue(result.valid, result.failures)
        assert result.value is not None
        return result.value

    def test_strict_task_parser_and_solver_view_hide_test_outputs(self) -> None:
        single = self.task("task-single-test.json", "single")
        multiple = self.task("task-multiple-tests.json", "multiple")

        view = multiple.solver_view()
        self.assertEqual(len(single.test), 1)
        self.assertEqual(len(multiple.test), 2)
        self.assertEqual(view.test[0].input.to_json(), [[2]])
        self.assertFalse(hasattr(view.test[0], "output"))

        malformed = parse_task_json(fixture_text("task-malformed.json"), "malformed")
        self.assertFalse(malformed.valid)
        self.assertIn("missing_field", {failure.code for failure in malformed.failures})

        named_payload = json.loads(fixture_text("task-single-test.json"))
        named_payload["name"] = "single"
        named = parse_task_json(json.dumps(named_payload), "single")
        self.assertTrue(named.valid, named.failures)
        named_payload["name"] = "a-different-task"
        name_mismatch = parse_task_json(json.dumps(named_payload), "single")
        self.assertFalse(name_mismatch.valid)
        self.assertIn("task_name_mismatch", {failure.code for failure in name_mismatch.failures})
        named_payload["name"] = "single"
        named_payload["unrecognized"] = True
        unknown_field = parse_task_json(json.dumps(named_payload), "single")
        self.assertFalse(unknown_field.valid)
        self.assertIn("unexpected_field", {failure.code for failure in unknown_field.failures})

    def test_exact_at_one_requires_all_test_outputs(self) -> None:
        task = self.task("task-single-test.json", "single")
        score = self.evaluator.score_task(task, self.candidate_set("prediction-correct-single.json"))

        self.assertTrue(score.exact_at_1)
        self.assertTrue(score.exact_at_native)
        self.assertTrue(score.first_attempt_solved)
        self.assertFalse(score.additional_attempt_salvage)
        self.assertEqual(score.pixel_accuracy, 1.0)
        self.assertEqual(score.shape_accuracy, 1.0)
        self.assertFalse(score.invalid_output)

        multiple = self.task("task-multiple-tests.json", "multiple")
        incomplete = CandidateSet(
            task_id="multiple",
            candidates=(
                Prediction(attempt=1, outputs=(Grid(((2,),)),)),
            ),
        )
        incomplete_score = self.evaluator.score_task(multiple, incomplete)
        self.assertFalse(incomplete_score.exact_at_1)
        self.assertTrue(incomplete_score.invalid_output)
        self.assertIn("test_count_mismatch", {failure.code for failure in incomplete_score.failures})

    def test_native_attempt_scoring_and_salvage(self) -> None:
        task = self.task("task-single-test.json", "single")
        score = self.evaluator.score_task(task, self.candidate_set("prediction-later-attempt.json"))

        self.assertFalse(score.exact_at_1)
        self.assertTrue(score.exact_at_native)
        self.assertTrue(score.additional_attempt_salvage)
        self.assertEqual(score.pixel_accuracy, 0.75)
        self.assertEqual(score.shape_accuracy, 1.0)

    def test_wrong_cell_and_wrong_shape_are_scored_or_structured_failures(self) -> None:
        task = self.task("task-single-test.json", "single")
        wrong_cell = CandidateSet(
            task_id="single",
            candidates=(Prediction(attempt=1, outputs=(Grid(((2, 0), (0, 1))),)),),
        )
        wrong_cell_score = self.evaluator.score_task(task, wrong_cell)
        self.assertFalse(wrong_cell_score.exact_at_1)
        self.assertFalse(wrong_cell_score.invalid_output)
        self.assertEqual(wrong_cell_score.pixel_accuracy, 0.75)

        wrong_shape = CandidateSet(
            task_id="single",
            candidates=(Prediction(attempt=1, outputs=(Grid(((2, 0),)),)),),
        )
        wrong_shape_score = self.evaluator.score_task(task, wrong_shape)
        self.assertTrue(wrong_shape_score.invalid_output)
        self.assertIn("output_shape_mismatch", {failure.code for failure in wrong_shape_score.failures})

    def test_malformed_and_invalid_prediction_outputs_never_escape_as_exceptions(self) -> None:
        task = self.task("task-single-test.json", "single")
        cases = {
            "empty_grid": {"task_id": "single", "attempts": [{"attempt": 1, "outputs": [[]]}]},
            "ragged_grid": {"task_id": "single", "attempts": [{"attempt": 1, "outputs": [[[2, 0], [2]]]}]},
            "illegal_value": {"task_id": "single", "attempts": [{"attempt": 1, "outputs": [[[2, 10], [0, 2]]]}]},
            "missing_output": {"task_id": "single", "attempts": [{"attempt": 1, "outputs": []}]},
            "extra_output": {
                "task_id": "single",
                "attempts": [{"attempt": 1, "outputs": [[[2, 0], [0, 2]], [[2, 0], [0, 2]]]}],
            },
        }
        expected_failure = {
            "empty_grid": "empty_grid",
            "ragged_grid": "ragged_grid",
            "illegal_value": "cell_value_out_of_range",
            "missing_output": "test_count_mismatch",
            "extra_output": "test_count_mismatch",
        }
        for name, payload in cases.items():
            with self.subTest(name=name):
                score = self.evaluator.score_candidate_set_json(task, json.dumps(payload))
                self.assertTrue(score.invalid_output)
                self.assertIn(expected_failure[name], {failure.code for failure in score.failures})

        malformed = self.evaluator.score_candidate_set_json(task, "{this is invalid JSON")
        self.assertTrue(malformed.invalid_output)
        self.assertIn("malformed_prediction_json", {failure.code for failure in malformed.failures})

    def test_duplicate_and_too_many_candidates_are_rejected(self) -> None:
        task = self.task("task-single-test.json", "single")
        correct_output = [[2, 0], [0, 2]]
        duplicate = {
            "task_id": "single",
            "attempts": [
                {"attempt": 1, "outputs": [correct_output]},
                {"attempt": 2, "outputs": [correct_output]},
            ],
        }
        duplicate_score = self.evaluator.score_candidate_set_json(task, json.dumps(duplicate))
        self.assertIn("duplicate_candidate", {failure.code for failure in duplicate_score.failures})

        too_many = {
            "task_id": "single",
            "attempts": [
                {"attempt": 1, "outputs": [[[2, 0], [0, 1]]]},
                {"attempt": 2, "outputs": [[[2, 0], [1, 2]]]},
                {"attempt": 3, "outputs": [[[2, 1], [0, 2]]]},
                {"attempt": 4, "outputs": [correct_output]},
            ],
        }
        too_many_score = self.evaluator.score_candidate_set_json(task, json.dumps(too_many))
        self.assertIn("too_many_candidates", {failure.code for failure in too_many_score.failures})
        self.assertIn("attempt_out_of_range", {failure.code for failure in too_many_score.failures})

    def test_submission_serialization_is_deterministic_and_reader_checks_identity(self) -> None:
        single = self.task("task-single-test.json", "single")
        multiple = self.task("task-multiple-tests.json", "multiple")
        single_candidates = self.candidate_set("prediction-correct-single.json")
        multiple_candidates = CandidateSet(
            task_id="multiple",
            candidates=(Prediction(attempt=1, outputs=(Grid(((2,),)), Grid(((3, 3),)))),),
        )
        submission = build_submission(self.identity, (single_candidates, multiple_candidates))

        first = serialize_submission(submission, self.identity)
        second = serialize_submission(submission, self.identity)
        self.assertTrue(first.valid, first.failures)
        self.assertEqual(first.value, second.value)
        assert first.value is not None
        serialized = json.loads(first.value)
        self.assertEqual([task["task_id"] for task in serialized["tasks"]], ["multiple", "single"])

        parsed = parse_submission_json(first.value, self.identity)
        self.assertTrue(parsed.valid, parsed.failures)
        report = self.evaluator.score_submission((single, multiple), parsed.value)
        self.assertTrue(report.valid, report.failures)
        self.assertEqual(report.metrics()["exact_at_1"], 1.0)
        self.assertEqual(report.to_json()["scorer_status"], LOCAL_REFERENCE_STATUS)
        self.assertEqual(report.to_json()["evaluator"]["official_status"], "Unavailable in checkout")

        with tempfile.TemporaryDirectory() as temporary:
            submission_path = Path(temporary) / "submission.json"
            written = write_submission(submission_path, submission, self.identity)
            self.assertTrue(written.valid, written.failures)
            reread = read_submission(submission_path, self.identity)
            self.assertTrue(reread.valid, reread.failures)

        raw = json.loads(first.value)
        raw["evaluator_version"] = "different-evaluator"
        version_mismatch = parse_submission_json(json.dumps(raw), self.identity)
        self.assertFalse(version_mismatch.valid)
        self.assertIn("evaluator_version_mismatch", {failure.code for failure in version_mismatch.failures})
        raw["evaluator_version"] = EVALUATOR_VERSION
        raw["rules_sha256"] = "0" * 64
        hash_mismatch = parse_submission_json(json.dumps(raw), self.identity)
        self.assertFalse(hash_mismatch.valid)
        self.assertIn("rules_hash_mismatch", {failure.code for failure in hash_mismatch.failures})

    def test_aggregate_metrics_keep_additional_attempt_salvage_separate(self) -> None:
        task = self.task("task-single-test.json", "single")
        correct = self.candidate_set("prediction-correct-single.json")
        salvage = CandidateSet(
            task_id="second",
            candidates=(
                Prediction(attempt=1, outputs=(Grid(((2, 0), (0, 1))),)),
                Prediction(attempt=2, outputs=(Grid(((2, 0), (0, 2))),)),
            ),
        )
        second_task = parse_task_json(fixture_text("task-single-test.json"), "second")
        self.assertTrue(second_task.valid, second_task.failures)
        assert second_task.value is not None
        submission = build_submission(self.identity, (correct, salvage))
        report = self.evaluator.score_submission((task, second_task.value), submission)
        metrics = report.metrics()
        self.assertEqual(metrics["exact_at_1"], 0.5)
        self.assertEqual(metrics["exact_at_native"], 1.0)
        self.assertEqual(metrics["additional_attempt_salvage_count"], 1)
        self.assertEqual(metrics["additional_attempt_salvage_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()

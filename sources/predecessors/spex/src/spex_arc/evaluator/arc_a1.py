"""Deterministic local-reference scoring for frozen ARC-AGI-1 rules.

The official ARC parser, scorer, evaluator, and submission writer are
``Unavailable in checkout``.  This module is intentionally labelled as a
local reference and must not be used to claim official or parity-validated
scores.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from spex_arc.domain.arc_a1 import (
    CandidateSet,
    Grid,
    Prediction,
    Task,
    ValidationFailure,
    ValidationResult,
    candidate_set_to_json,
    parse_candidate_set_json,
    parse_candidate_set_object,
    unique_failures,
    validate_candidate_set,
)


EVALUATOR_VERSION = "spex-arc-a1-local-reference-v0.1"
SUBMISSION_SCHEMA_VERSION = "1.0"
LOCAL_REFERENCE_STATUS = "local-reference-non-official"
OFFICIAL_STATUS = "Unavailable in checkout"
PARITY_STATUS = "not-established"


@dataclass(frozen=True)
class EvaluatorIdentity:
    """The frozen local rules identity required for every score."""

    evaluator_version: str
    rules_snapshot_id: str
    rules_sha256: str
    max_attempts: int
    scorer_status: str = LOCAL_REFERENCE_STATUS
    official_status: str = OFFICIAL_STATUS
    parity_status: str = PARITY_STATUS

    def to_json(self) -> dict[str, Any]:
        return {
            "evaluator_version": self.evaluator_version,
            "official_status": self.official_status,
            "parity_status": self.parity_status,
            "rules_sha256": self.rules_sha256,
            "rules_snapshot_id": self.rules_snapshot_id,
            "scorer_status": self.scorer_status,
        }


@dataclass(frozen=True)
class Submission:
    """A deterministic local-reference submission envelope."""

    evaluator_version: str
    rules_sha256: str
    scorer_status: str
    candidate_sets: tuple[CandidateSet, ...]


@dataclass(frozen=True)
class TaskScore:
    """Exact and diagnostic metrics for a single ARC task."""

    task_id: str
    exact_at_1: bool
    exact_at_native: bool
    pixel_accuracy: float
    shape_accuracy: float
    invalid_output: bool
    first_attempt_solved: bool
    additional_attempt_salvage: bool
    failures: tuple[ValidationFailure, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "additional_attempt_salvage": self.additional_attempt_salvage,
            "exact_at_1": self.exact_at_1,
            "exact_at_native": self.exact_at_native,
            "failure_types": [failure.code for failure in self.failures],
            "failures": [failure.to_json() for failure in self.failures],
            "first_attempt_solved": self.first_attempt_solved,
            "invalid_output": self.invalid_output,
            "pixel_accuracy": self.pixel_accuracy,
            "shape_accuracy": self.shape_accuracy,
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class EvaluationReport:
    """A traceable aggregate derived only from task-level scores."""

    identity: EvaluatorIdentity
    task_scores: tuple[TaskScore, ...]
    failures: tuple[ValidationFailure, ...]

    @property
    def valid(self) -> bool:
        return not self.failures and all(not score.invalid_output for score in self.task_scores)

    def metrics(self) -> dict[str, Any]:
        task_count = len(self.task_scores)
        if not task_count:
            return {
                "additional_attempt_salvage_count": 0,
                "additional_attempt_salvage_rate": 0.0,
                "exact_at_1": 0.0,
                "exact_at_native": 0.0,
                "first_attempt_solve_rate": 0.0,
                "invalid_output_rate": 0.0,
                "pixel_accuracy": 0.0,
                "shape_accuracy": 0.0,
                "task_count": 0,
            }
        return {
            "additional_attempt_salvage_count": sum(score.additional_attempt_salvage for score in self.task_scores),
            "additional_attempt_salvage_rate": sum(score.additional_attempt_salvage for score in self.task_scores) / task_count,
            "exact_at_1": sum(score.exact_at_1 for score in self.task_scores) / task_count,
            "exact_at_native": sum(score.exact_at_native for score in self.task_scores) / task_count,
            "first_attempt_solve_rate": sum(score.first_attempt_solved for score in self.task_scores) / task_count,
            "invalid_output_rate": sum(score.invalid_output for score in self.task_scores) / task_count,
            "pixel_accuracy": sum(score.pixel_accuracy for score in self.task_scores) / task_count,
            "shape_accuracy": sum(score.shape_accuracy for score in self.task_scores) / task_count,
            "task_count": task_count,
        }

    def to_json(self) -> dict[str, Any]:
        failure_counts = Counter(
            failure.code for score in self.task_scores for failure in score.failures
        )
        failure_counts.update(failure.code for failure in self.failures)
        return {
            "aggregate_metrics": self.metrics(),
            "evaluator": self.identity.to_json(),
            "failure_type_counts": dict(sorted(failure_counts.items())),
            "failures": [failure.to_json() for failure in self.failures],
            "scorer_status": LOCAL_REFERENCE_STATUS,
            "task_scores": [score.to_json() for score in self.task_scores],
        }


def _failure(code: str, path: str, message: str) -> ValidationFailure:
    return ValidationFailure(code=code, path=path, message=message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def load_evaluator_identity(rules_path: Path) -> ValidationResult[EvaluatorIdentity]:
    """Load and validate the frozen local A1 rules snapshot identity."""
    try:
        raw_bytes = rules_path.read_bytes()
        rules = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return ValidationResult(
            None,
            (_failure("rules_snapshot_unreadable", str(rules_path), f"Cannot load rules snapshot: {error}."),),
        )
    if not isinstance(rules, dict):
        return ValidationResult(None, (_failure("invalid_rules_snapshot", "$", "Rules snapshot must be a JSON object."),))

    failures: list[ValidationFailure] = []
    snapshot_id = rules.get("snapshot_id")
    attempt_policy = rules.get("native_attempt_policy")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        failures.append(_failure("invalid_rules_snapshot", "$.snapshot_id", "Rules snapshot_id must be a non-empty string."))
    if not isinstance(attempt_policy, dict):
        failures.append(
            _failure("invalid_rules_snapshot", "$.native_attempt_policy", "Native attempt policy must be an object.")
        )
        max_attempts: Any = None
    else:
        max_attempts = attempt_policy.get("max_attempts")
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
        failures.append(
            _failure("invalid_rules_snapshot", "$.native_attempt_policy.max_attempts", "max_attempts must be a positive integer.")
        )
    if failures:
        return ValidationResult(None, tuple(failures))
    return ValidationResult(
        EvaluatorIdentity(
            evaluator_version=EVALUATOR_VERSION,
            rules_snapshot_id=snapshot_id,
            rules_sha256=_sha256_file(rules_path),
            max_attempts=max_attempts,
        )
    )


def _exact_match(candidate: Prediction, task: Task) -> bool:
    return len(candidate.outputs) == len(task.test) and all(
        output.cells == test_case.output.cells for output, test_case in zip(candidate.outputs, task.test, strict=True)
    )


def _first_attempt_diagnostics(task: Task, candidate_set: CandidateSet | None) -> tuple[float, float]:
    """Measure the first supplied attempt; absent cells are counted as wrong."""
    if candidate_set is None or not candidate_set.candidates:
        return 0.0, 0.0
    candidate = candidate_set.candidates[0]
    if not isinstance(candidate, Prediction):
        return 0.0, 0.0
    correct_pixels = 0
    expected_pixels = sum(len(row) for test_case in task.test for row in test_case.output.cells)
    shape_matches = 0
    for index, expected_case in enumerate(task.test):
        if index >= len(candidate.outputs) or not isinstance(candidate.outputs[index], Grid):
            continue
        actual = candidate.outputs[index]
        expected = expected_case.output
        if actual.height == expected.height and actual.width == expected.width:
            shape_matches += 1
        for row_index, expected_row in enumerate(expected.cells):
            if row_index >= len(actual.cells):
                continue
            actual_row = actual.cells[row_index]
            for column_index, expected_cell in enumerate(expected_row):
                if column_index < len(actual_row) and actual_row[column_index] == expected_cell:
                    correct_pixels += 1
    return (
        correct_pixels / expected_pixels if expected_pixels else 0.0,
        shape_matches / len(task.test) if task.test else 0.0,
    )


class LocalReferenceEvaluator:
    """Score A1 tasks against the pinned local-reference rules snapshot."""

    def __init__(self, identity: EvaluatorIdentity) -> None:
        self.identity = identity

    @classmethod
    def from_rules_snapshot(cls, rules_path: Path) -> ValidationResult["LocalReferenceEvaluator"]:
        identity_result = load_evaluator_identity(rules_path)
        if identity_result.value is None:
            return ValidationResult(None, identity_result.failures)
        return ValidationResult(cls(identity_result.value))

    def score_task(self, task: Task, candidate_set: CandidateSet | None, extra_failures: Iterable[ValidationFailure] = ()) -> TaskScore:
        """Score one task without allowing malformed output to escape as an exception."""
        failures = list(extra_failures)
        if candidate_set is None:
            failures.append(_failure("missing_prediction", "$.tasks", "No prediction was supplied for this task."))
            return TaskScore(
                task_id=task.task_id,
                exact_at_1=False,
                exact_at_native=False,
                pixel_accuracy=0.0,
                shape_accuracy=0.0,
                invalid_output=True,
                first_attempt_solved=False,
                additional_attempt_salvage=False,
                failures=unique_failures(failures),
            )

        failures.extend(validate_candidate_set(task, candidate_set, self.identity.max_attempts))
        pixel_accuracy, shape_accuracy = _first_attempt_diagnostics(task, candidate_set)
        if failures:
            return TaskScore(
                task_id=task.task_id,
                exact_at_1=False,
                exact_at_native=False,
                pixel_accuracy=pixel_accuracy,
                shape_accuracy=shape_accuracy,
                invalid_output=True,
                first_attempt_solved=False,
                additional_attempt_salvage=False,
                failures=unique_failures(failures),
            )

        first_attempt_solved = _exact_match(candidate_set.candidates[0], task)
        native_solved = any(_exact_match(candidate, task) for candidate in candidate_set.candidates)
        return TaskScore(
            task_id=task.task_id,
            exact_at_1=first_attempt_solved,
            exact_at_native=native_solved,
            pixel_accuracy=pixel_accuracy,
            shape_accuracy=shape_accuracy,
            invalid_output=False,
            first_attempt_solved=first_attempt_solved,
            additional_attempt_salvage=native_solved and not first_attempt_solved,
            failures=(),
        )

    def score_candidate_set_json(self, task: Task, text: str | bytes) -> TaskScore:
        """Parse and score one raw solver result, returning failures as data."""
        parsed = parse_candidate_set_json(text)
        if parsed.value is None:
            return self.score_task(task, None, parsed.failures)
        return self.score_task(task, parsed.value)

    def score_submission(self, tasks: Iterable[Task], submission: Submission) -> EvaluationReport:
        """Score a submission deterministically in task-id order."""
        task_by_id: dict[str, Task] = {}
        report_failures: list[ValidationFailure] = []
        for task in tasks:
            if task.task_id in task_by_id:
                report_failures.append(
                    _failure("duplicate_task_id", "$.tasks", f"Evaluation task identifier is duplicated: {task.task_id}."))
            task_by_id[task.task_id] = task

        report_failures.extend(_validate_submission_identity(submission, self.identity))
        candidates_by_task: dict[str, CandidateSet] = {}
        for candidate_set in submission.candidate_sets:
            if candidate_set.task_id in candidates_by_task:
                report_failures.append(
                    _failure("duplicate_submission_task", "$.tasks", f"Submission repeats task: {candidate_set.task_id}."))
                continue
            candidates_by_task[candidate_set.task_id] = candidate_set
        for task_id in sorted(set(candidates_by_task) - set(task_by_id)):
            report_failures.append(
                _failure("unknown_submission_task", "$.tasks", f"Submission contains unknown task: {task_id}."))

        contract_failures = tuple(report_failures) if report_failures else ()
        scores = tuple(
            self.score_task(task, candidates_by_task.get(task_id), contract_failures)
            for task_id, task in sorted(task_by_id.items())
        )
        return EvaluationReport(identity=self.identity, task_scores=scores, failures=unique_failures(report_failures))


def _validate_submission_identity(submission: Submission, identity: EvaluatorIdentity) -> tuple[ValidationFailure, ...]:
    failures: list[ValidationFailure] = []
    if submission.evaluator_version != identity.evaluator_version:
        failures.append(
            _failure(
                "evaluator_version_mismatch",
                "$.evaluator_version",
                "Submission evaluator version does not match the active evaluator.",
            )
        )
    if submission.rules_sha256 != identity.rules_sha256:
        failures.append(
            _failure("rules_hash_mismatch", "$.rules_sha256", "Submission rules hash does not match the active rules snapshot.")
        )
    if submission.scorer_status != LOCAL_REFERENCE_STATUS:
        failures.append(
            _failure(
                "invalid_scorer_status",
                "$.scorer_status",
                f"Submission scorer_status must be {LOCAL_REFERENCE_STATUS!r}.",
            )
        )
    return tuple(failures)


def build_submission(identity: EvaluatorIdentity, candidate_sets: Iterable[CandidateSet]) -> Submission:
    """Build the only supported local-reference submission envelope."""
    return Submission(
        evaluator_version=identity.evaluator_version,
        rules_sha256=identity.rules_sha256,
        scorer_status=LOCAL_REFERENCE_STATUS,
        candidate_sets=tuple(candidate_sets),
    )


def _parse_submission_object(value: Any, identity: EvaluatorIdentity) -> ValidationResult[Submission]:
    failures: list[ValidationFailure] = []
    if not isinstance(value, dict):
        return ValidationResult(None, (_failure("invalid_submission", "$", "Submission must be a JSON object."),))
    required = {"artifact_type", "evaluator_version", "rules_sha256", "schema_version", "scorer_status", "tasks"}
    for key in sorted(required - set(value)):
        failures.append(_failure("missing_field", "$", f"Missing required field: {key}."))
    for key in sorted(set(value) - required):
        failures.append(_failure("unexpected_field", "$", f"Unexpected field: {key}."))
    if value.get("artifact_type") != "arc-agi-1-local-reference-submission":
        failures.append(_failure("invalid_artifact_type", "$.artifact_type", "Submission artifact type is not supported."))
    if value.get("schema_version") != SUBMISSION_SCHEMA_VERSION:
        failures.append(
            _failure("unsupported_submission_schema", "$.schema_version", "Submission schema version is not supported.")
        )
    for field in ("evaluator_version", "rules_sha256", "scorer_status"):
        if not isinstance(value.get(field), str):
            failures.append(_failure("invalid_submission_field", f"$.{field}", f"{field} must be a string."))
    tasks = value.get("tasks")
    candidate_sets: list[CandidateSet] = []
    if not isinstance(tasks, list):
        failures.append(_failure("invalid_submission_tasks", "$.tasks", "tasks must be a JSON array."))
    else:
        for index, raw_candidate_set in enumerate(tasks):
            parsed = parse_candidate_set_object(raw_candidate_set)
            failures.extend(
                _failure(failure.code, f"$.tasks[{index}]{failure.path[1:]}", failure.message)
                for failure in parsed.failures
            )
            if parsed.value is not None:
                candidate_sets.append(parsed.value)
    if failures:
        return ValidationResult(None, unique_failures(failures))
    submission = Submission(
        evaluator_version=value["evaluator_version"],
        rules_sha256=value["rules_sha256"],
        scorer_status=value["scorer_status"],
        candidate_sets=tuple(candidate_sets),
    )
    identity_failures = _validate_submission_identity(submission, identity)
    if identity_failures:
        return ValidationResult(None, identity_failures)
    return ValidationResult(submission)


def parse_submission_json(text: str | bytes, identity: EvaluatorIdentity) -> ValidationResult[Submission]:
    """Read a strict local-reference submission without treating it as official."""
    try:
        value = json.loads(text)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return ValidationResult(
            None,
            (_failure("malformed_submission_json", "$", f"Submission JSON could not be parsed: {error}."),),
        )
    return _parse_submission_object(value, identity)


def read_submission(path: Path, identity: EvaluatorIdentity) -> ValidationResult[Submission]:
    """Read a submission file, returning an explicit failure on I/O errors."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return ValidationResult(None, (_failure("submission_unreadable", str(path), f"Cannot read submission: {error}."),))
    return parse_submission_json(text, identity)


def serialize_submission(submission: Submission, identity: EvaluatorIdentity) -> ValidationResult[bytes]:
    """Serialize a validated submission canonically, sorted by task identifier."""
    failures = list(_validate_submission_identity(submission, identity))
    seen_task_ids: set[str] = set()
    for candidate_set in submission.candidate_sets:
        if candidate_set.task_id in seen_task_ids:
            failures.append(
                _failure("duplicate_submission_task", "$.tasks", f"Submission repeats task: {candidate_set.task_id}."))
        seen_task_ids.add(candidate_set.task_id)
        if not candidate_set.candidates:
            failures.append(_failure("missing_output", "$.tasks", "Each submission task needs at least one candidate."))
        attempts = [candidate.attempt for candidate in candidate_set.candidates]
        if attempts != list(range(1, len(candidate_set.candidates) + 1)):
            failures.append(
                _failure(
                    "noncanonical_attempt_order",
                    "$.tasks",
                    "Submission attempts must be ordered contiguously as 1, 2, ..., K.",
                )
            )
        if len(candidate_set.candidates) > identity.max_attempts:
            failures.append(
                _failure(
                    "too_many_candidates",
                    "$.tasks",
                    f"At most {identity.max_attempts} candidate attempts are allowed.",
                )
            )
    if failures:
        return ValidationResult(None, unique_failures(failures))
    payload = {
        "artifact_type": "arc-agi-1-local-reference-submission",
        "evaluator_version": submission.evaluator_version,
        "rules_sha256": submission.rules_sha256,
        "schema_version": SUBMISSION_SCHEMA_VERSION,
        "scorer_status": submission.scorer_status,
        "tasks": [
            candidate_set_to_json(candidate_set)
            for candidate_set in sorted(submission.candidate_sets, key=lambda item: item.task_id)
        ],
    }
    return ValidationResult(_canonical_json_bytes(payload))


def write_submission(path: Path, submission: Submission, identity: EvaluatorIdentity) -> ValidationResult[Path]:
    """Write a canonical submission only after validation succeeds."""
    serialized = serialize_submission(submission, identity)
    if serialized.value is None:
        return ValidationResult(None, serialized.failures)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(serialized.value)
    except OSError as error:
        return ValidationResult(None, (_failure("submission_unwritable", str(path), f"Cannot write submission: {error}."),))
    return ValidationResult(path)

"""Strict, model-independent ARC-AGI-1 task and prediction contracts.

The parser implements the structural and semantic checks recorded in
``schemas/arc-agi-1-task.schema.json`` and
``schemas/arc-agi-1-prediction.schema.json`` without depending on a JSON
Schema runtime.  Parsing failures are data, not exceptions, so callers can
archive invalid solver output deterministically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Iterable, TypeVar


MAX_GRID_DIMENSION = 30
MIN_CELL_VALUE = 0
MAX_CELL_VALUE = 9

T = TypeVar("T")


@dataclass(frozen=True)
class ValidationFailure:
    """A stable, machine-readable contract failure."""

    code: str
    path: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class ValidationResult(Generic[T]):
    """The result of parsing or validating untrusted ARC data."""

    value: T | None
    failures: tuple[ValidationFailure, ...] = ()

    @property
    def valid(self) -> bool:
        return self.value is not None and not self.failures


@dataclass(frozen=True)
class Grid:
    """An ARC grid.  Use :func:`parse_grid` for untrusted JSON values."""

    cells: tuple[tuple[int, ...], ...]

    @property
    def height(self) -> int:
        return len(self.cells)

    @property
    def width(self) -> int:
        return len(self.cells[0]) if self.cells else 0

    def to_json(self) -> list[list[int]]:
        return [list(row) for row in self.cells]


@dataclass(frozen=True)
class TrainPair:
    """A fully observed ARC training input/output pair."""

    input: Grid
    output: Grid


@dataclass(frozen=True)
class TestCase:
    """A fully observed test case, retained only in the evaluator-side task."""

    input: Grid
    output: Grid


@dataclass(frozen=True)
class SolverTestCase:
    """A solver-safe test case that deliberately has no output field."""

    input: Grid


@dataclass(frozen=True)
class TaskView:
    """The only task representation intended for a solver or model."""

    task_id: str
    train: tuple[TrainPair, ...]
    test: tuple[SolverTestCase, ...]


@dataclass(frozen=True)
class Task:
    """A fully observed ARC task used only by parsing and scoring code."""

    task_id: str
    train: tuple[TrainPair, ...]
    test: tuple[TestCase, ...]

    def solver_view(self) -> TaskView:
        """Return a view that cannot expose held test outputs by attribute."""
        return TaskView(
            task_id=self.task_id,
            train=self.train,
            test=tuple(SolverTestCase(input=test_case.input) for test_case in self.test),
        )


@dataclass(frozen=True)
class Prediction:
    """One ordered, whole-task prediction attempt."""

    attempt: int
    outputs: tuple[Grid, ...]


@dataclass(frozen=True)
class CandidateSet:
    """Ordered predictions for one task under an attempt allowance."""

    task_id: str
    candidates: tuple[Prediction, ...]


def _failure(code: str, path: str, message: str) -> ValidationFailure:
    return ValidationFailure(code=code, path=path, message=message)


def _exact_keys(
    value: dict[str, Any],
    required: set[str],
    path: str,
    failures: list[ValidationFailure],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    for key in sorted(required - set(value)):
        failures.append(_failure("missing_field", path, f"Missing required field: {key}."))
    for key in sorted(set(value) - allowed):
        failures.append(_failure("unexpected_field", path, f"Unexpected field: {key}."))


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_grid(value: Any, path: str) -> ValidationResult[Grid]:
    """Parse one non-empty 30x30-or-smaller rectangular ARC grid."""
    failures: list[ValidationFailure] = []
    if not isinstance(value, list):
        return ValidationResult(None, (_failure("invalid_grid", path, "Grid must be a JSON array of rows."),))
    if not value:
        return ValidationResult(None, (_failure("empty_grid", path, "Grid must contain at least one row."),))
    if len(value) > MAX_GRID_DIMENSION:
        return ValidationResult(
            None,
            (_failure("grid_height_exceeds_limit", path, f"Grid height exceeds {MAX_GRID_DIMENSION}."),),
        )

    parsed_rows: list[tuple[int, ...]] = []
    expected_width: int | None = None
    for row_index, row in enumerate(value):
        row_path = f"{path}[{row_index}]"
        if not isinstance(row, list):
            failures.append(_failure("invalid_grid_row", row_path, "Grid row must be a JSON array."))
            continue
        if not row:
            failures.append(_failure("empty_grid_row", row_path, "Grid row must contain at least one cell."))
            continue
        if len(row) > MAX_GRID_DIMENSION:
            failures.append(
                _failure("grid_width_exceeds_limit", row_path, f"Grid width exceeds {MAX_GRID_DIMENSION}.")
            )
        if expected_width is None:
            expected_width = len(row)
        elif len(row) != expected_width:
            failures.append(_failure("ragged_grid", row_path, "All grid rows must have the same width."))

        parsed_row: list[int] = []
        for cell_index, cell in enumerate(row):
            cell_path = f"{row_path}[{cell_index}]"
            if not _is_integer(cell):
                failures.append(_failure("invalid_cell_type", cell_path, "Grid cells must be integers."))
            elif not MIN_CELL_VALUE <= cell <= MAX_CELL_VALUE:
                failures.append(
                    _failure(
                        "cell_value_out_of_range",
                        cell_path,
                        f"Grid cells must be between {MIN_CELL_VALUE} and {MAX_CELL_VALUE}.",
                    )
                )
            else:
                parsed_row.append(cell)
        parsed_rows.append(tuple(parsed_row))

    if failures:
        return ValidationResult(None, tuple(failures))
    return ValidationResult(Grid(cells=tuple(parsed_rows)))


def validate_grid(grid: Any, path: str) -> tuple[ValidationFailure, ...]:
    """Validate a programmatically created grid with the same parser rules."""
    if not isinstance(grid, Grid):
        return (_failure("invalid_grid_type", path, "Expected a Grid instance."),)
    return parse_grid(grid.to_json(), path).failures


def _parse_pair(value: Any, path: str, pair_type: type[TrainPair] | type[TestCase]) -> ValidationResult[TrainPair | TestCase]:
    failures: list[ValidationFailure] = []
    if not isinstance(value, dict):
        return ValidationResult(None, (_failure("invalid_pair", path, "Task pair must be a JSON object."),))
    _exact_keys(value, {"input", "output"}, path, failures)
    input_grid = parse_grid(value.get("input"), f"{path}.input") if "input" in value else ValidationResult(None)
    output_grid = parse_grid(value.get("output"), f"{path}.output") if "output" in value else ValidationResult(None)
    failures.extend(input_grid.failures)
    failures.extend(output_grid.failures)
    if failures or input_grid.value is None or output_grid.value is None:
        return ValidationResult(None, tuple(failures))
    return ValidationResult(pair_type(input=input_grid.value, output=output_grid.value))


def parse_task_object(value: Any, task_id: str) -> ValidationResult[Task]:
    """Strictly validate an ARC task object with fully observed test outputs."""
    failures: list[ValidationFailure] = []
    if not isinstance(task_id, str) or not task_id:
        failures.append(_failure("invalid_task_id", "$.task_id", "Task identifier must be a non-empty string."))
    if not isinstance(value, dict):
        return ValidationResult(None, tuple(failures + [_failure("invalid_task", "$", "Task must be a JSON object.")]))
    _exact_keys(value, {"train", "test"}, "$", failures, optional={"name"})
    if "name" in value:
        name = value["name"]
        if not isinstance(name, str) or not name:
            failures.append(_failure("invalid_task_name", "$.name", "Optional task name must be a non-empty string."))
        elif name != task_id:
            failures.append(
                _failure(
                    "task_name_mismatch",
                    "$.name",
                    "Optional task name must match the external task identifier.",
                )
            )

    parsed_train: list[TrainPair] = []
    parsed_test: list[TestCase] = []
    for field, pair_type, parsed_pairs in (
        ("train", TrainPair, parsed_train),
        ("test", TestCase, parsed_test),
    ):
        raw_pairs = value.get(field)
        field_path = f"$.{field}"
        if field not in value:
            continue
        if not isinstance(raw_pairs, list):
            failures.append(_failure("invalid_pair_list", field_path, "Task pair collection must be a JSON array."))
            continue
        if not raw_pairs:
            failures.append(_failure("empty_pair_list", field_path, "Task must contain at least one pair."))
            continue
        for index, raw_pair in enumerate(raw_pairs):
            parsed = _parse_pair(raw_pair, f"{field_path}[{index}]", pair_type)
            failures.extend(parsed.failures)
            if parsed.value is not None:
                parsed_pairs.append(parsed.value)  # type: ignore[arg-type]

    if failures:
        return ValidationResult(None, tuple(failures))
    return ValidationResult(Task(task_id=task_id, train=tuple(parsed_train), test=tuple(parsed_test)))


def parse_task_json(text: str | bytes, task_id: str) -> ValidationResult[Task]:
    """Parse strict UTF-8 JSON task content into a fully observed task."""
    try:
        value = json.loads(text)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return ValidationResult(
            None,
            (_failure("malformed_task_json", "$", f"Task JSON could not be parsed: {error.msg if isinstance(error, json.JSONDecodeError) else error}."),),
        )
    return parse_task_object(value, task_id)


def parse_task_file(path: Path, task_id: str | None = None) -> ValidationResult[Task]:
    """Read a task file, deriving its identifier from the filename by default."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return ValidationResult(None, (_failure("task_file_unreadable", str(path), f"Cannot read task file: {error}."),))
    return parse_task_json(text, task_id or path.stem)


def parse_candidate_set_object(value: Any) -> ValidationResult[CandidateSet]:
    """Strictly parse the local-reference whole-task prediction contract."""
    failures: list[ValidationFailure] = []
    if not isinstance(value, dict):
        return ValidationResult(None, (_failure("invalid_prediction", "$", "Prediction must be a JSON object."),))
    _exact_keys(value, {"task_id", "attempts"}, "$", failures)
    task_id = value.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        failures.append(_failure("invalid_task_id", "$.task_id", "Task identifier must be a non-empty string."))

    candidates: list[Prediction] = []
    attempts = value.get("attempts")
    if "attempts" in value and not isinstance(attempts, list):
        failures.append(_failure("invalid_attempt_list", "$.attempts", "Attempts must be a JSON array."))
    elif isinstance(attempts, list):
        for candidate_index, raw_candidate in enumerate(attempts):
            candidate_path = f"$.attempts[{candidate_index}]"
            if not isinstance(raw_candidate, dict):
                failures.append(_failure("invalid_candidate", candidate_path, "Attempt must be a JSON object."))
                continue
            _exact_keys(raw_candidate, {"attempt", "outputs"}, candidate_path, failures)
            attempt = raw_candidate.get("attempt")
            if not _is_integer(attempt):
                failures.append(_failure("invalid_attempt_number", f"{candidate_path}.attempt", "Attempt must be an integer."))
            outputs = raw_candidate.get("outputs")
            parsed_outputs: list[Grid] = []
            if "outputs" in raw_candidate and not isinstance(outputs, list):
                failures.append(
                    _failure("invalid_output_list", f"{candidate_path}.outputs", "Outputs must be a JSON array of grids.")
                )
            elif isinstance(outputs, list):
                for output_index, raw_output in enumerate(outputs):
                    parsed_output = parse_grid(raw_output, f"{candidate_path}.outputs[{output_index}]")
                    failures.extend(parsed_output.failures)
                    if parsed_output.value is not None:
                        parsed_outputs.append(parsed_output.value)
            if _is_integer(attempt) and (not isinstance(outputs, list) or len(parsed_outputs) == len(outputs)):
                candidates.append(Prediction(attempt=attempt, outputs=tuple(parsed_outputs)))

    if failures:
        return ValidationResult(None, tuple(failures))
    return ValidationResult(CandidateSet(task_id=task_id, candidates=tuple(candidates)))


def parse_candidate_set_json(text: str | bytes) -> ValidationResult[CandidateSet]:
    """Parse a strict local-reference candidate-set JSON document."""
    try:
        value = json.loads(text)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return ValidationResult(
            None,
            (_failure("malformed_prediction_json", "$", f"Prediction JSON could not be parsed: {error.msg if isinstance(error, json.JSONDecodeError) else error}."),),
        )
    return parse_candidate_set_object(value)


def _candidate_signature(candidate: Prediction) -> tuple[tuple[tuple[int, ...], ...], ...]:
    return tuple(grid.cells for grid in candidate.outputs)


def validate_candidate_set(task: Task, candidate_set: Any, max_attempts: int) -> tuple[ValidationFailure, ...]:
    """Validate task-bound output shape, ordering, uniqueness, and allowance."""
    failures: list[ValidationFailure] = []
    if not isinstance(task, Task):
        return (_failure("invalid_task_type", "$.task", "Expected a Task instance."),)
    if not isinstance(candidate_set, CandidateSet):
        return (_failure("invalid_candidate_set_type", "$.prediction", "Expected a CandidateSet instance."),)
    if candidate_set.task_id != task.task_id:
        failures.append(
            _failure("task_id_mismatch", "$.task_id", f"Prediction task_id must equal {task.task_id!r}.")
        )
    if not candidate_set.candidates:
        failures.append(_failure("missing_output", "$.attempts", "At least one candidate attempt is required."))
        return tuple(failures)
    if len(candidate_set.candidates) > max_attempts:
        failures.append(
            _failure("too_many_candidates", "$.attempts", f"At most {max_attempts} candidate attempts are allowed.")
        )

    expected_attempts = list(range(1, len(candidate_set.candidates) + 1))
    actual_attempts: list[int] = []
    signatures: set[tuple[tuple[tuple[int, ...], ...], ...]] = set()
    for candidate_index, candidate in enumerate(candidate_set.candidates):
        candidate_path = f"$.attempts[{candidate_index}]"
        if not isinstance(candidate, Prediction):
            failures.append(_failure("invalid_candidate_type", candidate_path, "Expected a Prediction instance."))
            continue
        actual_attempts.append(candidate.attempt)
        if not _is_integer(candidate.attempt) or not 1 <= candidate.attempt <= max_attempts:
            failures.append(
                _failure("attempt_out_of_range", f"{candidate_path}.attempt", f"Attempt must be between 1 and {max_attempts}.")
            )
        if len(candidate.outputs) != len(task.test):
            failures.append(
                _failure(
                    "test_count_mismatch",
                    f"{candidate_path}.outputs",
                    f"Prediction supplies {len(candidate.outputs)} outputs for {len(task.test)} test inputs.",
                )
            )
        for output_index, output in enumerate(candidate.outputs):
            failures.extend(validate_grid(output, f"{candidate_path}.outputs[{output_index}]"))
            if output_index < len(task.test) and isinstance(output, Grid):
                expected_output = task.test[output_index].output
                if output.height != expected_output.height or output.width != expected_output.width:
                    failures.append(
                        _failure(
                            "output_shape_mismatch",
                            f"{candidate_path}.outputs[{output_index}]",
                            "Prediction grid shape must match the corresponding test output shape.",
                        )
                    )
        try:
            signature = _candidate_signature(candidate)
        except (AttributeError, TypeError):
            failures.append(_failure("invalid_candidate", candidate_path, "Candidate outputs could not be canonicalized."))
        else:
            if signature in signatures:
                failures.append(_failure("duplicate_candidate", candidate_path, "Candidate output duplicates an earlier attempt."))
            signatures.add(signature)

    if len(set(actual_attempts)) != len(actual_attempts):
        failures.append(_failure("duplicate_attempt_number", "$.attempts", "Attempt numbers must be unique."))
    if actual_attempts != expected_attempts:
        failures.append(
            _failure(
                "noncanonical_attempt_order",
                "$.attempts",
                "Attempts must be ordered contiguously as 1, 2, ..., K.",
            )
        )
    return tuple(failures)


def candidate_set_to_json(candidate_set: CandidateSet) -> dict[str, Any]:
    """Return the deterministic JSON-compatible form for one candidate set."""
    return {
        "task_id": candidate_set.task_id,
        "attempts": [
            {"attempt": candidate.attempt, "outputs": [grid.to_json() for grid in candidate.outputs]}
            for candidate in candidate_set.candidates
        ],
    }


def unique_failures(failures: Iterable[ValidationFailure]) -> tuple[ValidationFailure, ...]:
    """Deduplicate failures while retaining deterministic first-occurrence order."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[ValidationFailure] = []
    for failure in failures:
        key = (failure.code, failure.path, failure.message)
        if key not in seen:
            unique.append(failure)
            seen.add(key)
    return tuple(unique)

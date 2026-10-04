"""Truth-free ARC-AGI-2 two-attempt submission export; no provider or scoring API.

This tool deliberately never opens solutions. It keeps every challenge test in
the output, including failed/unfinished tests, and reports deterministic filler
attempts separately. A valid file is not evidence of an official score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


class SubmissionError(ValueError):
    pass


FAILURE_STATUSES = {"invalid", "timeout", "worker_crash", "oom",
                    "interrupted_pending", "not_executed", "session_limit", "failed"}
TEST_STATUSES = FAILURE_STATUSES | {"complete", "missing-candidate"}
EVALUATOR_FIELDS = {"expected_output", "expected_outputs", "evaluator_truth", "solutions",
                    "correct_output", "correct_outputs", "exact_match", "official_score"}


def require(condition, message):
    if not condition:
        raise SubmissionError(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse_json(body):
    def invalid_constant(_value):
        raise SubmissionError("non-finite JSON number")
    return json.loads(body, object_pairs_hook=_object, parse_constant=invalid_constant)


def load_json(path):
    return parse_json(Path(path).read_bytes())


def grid(value):
    require(isinstance(value, list) and 1 <= len(value) <= 30,
            "grid must have 1..30 rows")
    require(isinstance(value[0], list) and 1 <= len(value[0]) <= 30,
            "grid must have 1..30 columns")
    width = len(value[0])
    require(all(isinstance(row, list) and len(row) == width and
                all(type(cell) is int and 0 <= cell <= 9 for cell in row)
                for row in value), "rectangular integer color grid required")
    return [row[:] for row in value]


def challenge_counts(challenges):
    require(isinstance(challenges, dict) and challenges, "nonempty challenge mapping required")
    counts = {}
    for task_id, task in challenges.items():
        require(isinstance(task_id, str) and task_id, "nonempty task ID required")
        require(isinstance(task, dict) and set(task) == {"train", "test"},
                "challenge must contain only train and test")
        require(isinstance(task["train"], list) and task["train"] and
                isinstance(task["test"], list) and task["test"], "nonempty train/test lists required")
        for pair in task["train"]:
            require(isinstance(pair, dict) and set(pair) == {"input", "output"},
                    "demonstration schema differs")
            grid(pair["input"]); grid(pair["output"])
        for pair in task["test"]:
            require(isinstance(pair, dict) and set(pair) == {"input"},
                    "test truth or extra test field is forbidden")
            grid(pair["input"])
        counts[task_id] = len(task["test"])
    return counts


def validate_submission(challenges, submission):
    counts = challenge_counts(challenges)
    require(isinstance(submission, dict) and set(submission) == set(counts),
            "submission task denominator differs")
    for task_id, count in counts.items():
        outputs = submission[task_id]
        require(isinstance(outputs, list) and len(outputs) == count,
                "submission test-output denominator differs")
        for item in outputs:
            require(isinstance(item, dict) and set(item) == {"attempt_1", "attempt_2"},
                    "exactly two named attempts required")
            grid(item["attempt_1"]); grid(item["attempt_2"])
    return {"task_count": len(counts), "test_output_count": sum(counts.values())}


def build_submission(challenges, records):
    """Export retained runtime records without consulting answers or rankings.

    Each record is {task_id, tests:[{test_index, attempts, ...}], ...}. Missing
    tasks/tests or empty attempts are retained as explicit filler slots. Extra
    IDs, duplicate indices, invalid grids or more than two attempts fail closed.
    """
    counts = challenge_counts(challenges)
    require(isinstance(records, list), "prediction records must be a list")
    def reject_evaluator_fields(value):
        if isinstance(value, dict):
            require(not EVALUATOR_FIELDS.intersection(value), "evaluator fields are forbidden in prediction records")
            require(value.get("contains_evaluator_truth", False) is False and
                    value.get("correctness_scored", False) is False,
                    "evaluated records cannot cross the submission boundary")
            for child in value.values():
                reject_evaluator_fields(child)
        elif isinstance(value, list):
            for child in value:
                reject_evaluator_fields(child)
    reject_evaluator_fields(records)
    by_task = {}
    for record in records:
        require(isinstance(record, dict) and isinstance(record.get("task_id"), str) and
                record["task_id"] in counts, "prediction names an unknown task")
        task_id = record["task_id"]
        require(task_id not in by_task, "duplicate prediction task")
        require(isinstance(record.get("tests"), list), "prediction tests must be a list")
        task_status = record.get("status", "unspecified")
        require(isinstance(task_status, str) and
                (task_status == "unspecified" or task_status in TEST_STATUSES),
                "unknown task status")
        outputs = {}
        for item in record["tests"]:
            require(isinstance(item, dict), "prediction test must be an object")
            index = item.get("test_index")
            require(type(index) is int and 0 <= index < counts[task_id] and index not in outputs,
                    "duplicate or invalid test index")
            attempts = item.get("attempts")
            require(isinstance(attempts, list) and len(attempts) <= 2,
                    "prediction must supply at most two ordered attempts")
            status = item.get("status", "unspecified")
            require(isinstance(status, str) and (status == "unspecified" or status in TEST_STATUSES),
                    "unknown prediction status")
            require(status not in FAILURE_STATUSES or not attempts,
                    "failed test cannot claim model candidates")
            require(status != "complete" or len(attempts) == 2,
                    "complete test requires two model attempts")
            require(status != "missing-candidate" or len(attempts) < 2,
                    "missing-candidate status contradicts attempts")
            if "missing_attempts" in item:
                require(type(item["missing_attempts"]) is int and
                        item["missing_attempts"] == 2 - len(attempts),
                        "missing-attempt accounting differs")
            require(task_status not in FAILURE_STATUSES or not attempts or
                    status in {"complete", "missing-candidate"},
                    "failed task candidates need explicit per-test nonfailure status")
            outputs[index] = {"attempts": [grid(value) for value in attempts], "status": status}
        if task_status == "complete":
            require(len(outputs) == counts[task_id] and
                    all(len(item["attempts"]) == 2 for item in outputs.values()),
                    "complete task must supply both attempts for every test")
        if task_status == "missing-candidate":
            require(len(outputs) < counts[task_id] or
                    any(len(item["attempts"]) < 2 for item in outputs.values()),
                    "missing-candidate task contradicts complete attempts")
        by_task[task_id] = {"tests": outputs, "status": task_status}
    submission = {}
    audit_rows = []
    for task_id, count in counts.items():
        submission[task_id] = []
        for index in range(count):
            record = by_task.get(task_id)
            item = None if record is None else record["tests"].get(index)
            attempts = [] if item is None else item["attempts"]
            supplied = len(attempts)
            # Duplicate a sole model candidate; with no candidate use a fixed
            # legal grid. Never infer a test answer from task metadata.
            first = attempts[0] if supplied else [[0]]
            second = attempts[1] if supplied == 2 else first
            submission[task_id].append({"attempt_1": grid(first), "attempt_2": grid(second)})
            audit_rows.append({"task_id": task_id, "test_index": index,
                               "supplied_attempts": supplied,
                               "input_task_status": "not_supplied" if record is None else record["status"],
                               "input_test_status": "not_supplied" if item is None else item["status"],
                               "model_attempt_slots_missing": 2 - supplied,
                               "attempt_sources": ["model" if slot < supplied else "filler"
                                                   for slot in range(2)],
                               "fill_policy": "none" if supplied == 2 else
                               "duplicate_first" if supplied == 1 else "constant_zero_1x1"})
    coverage = validate_submission(challenges, submission)
    task_status_counts = {}
    for task_id in counts:
        status = by_task[task_id]["status"] if task_id in by_task else "not_supplied"
        task_status_counts[status] = task_status_counts.get(status, 0) + 1
    audit = {"format": "irisx/arc-kaggle-export-audit-v1", **coverage,
             "task_status_counts": task_status_counts,
             "model_supplied_attempts": sum(row["supplied_attempts"] for row in audit_rows),
             "model_attempt_slots_missing": sum(row["model_attempt_slots_missing"] for row in audit_rows),
             "tests_without_model_candidates": sum(row["supplied_attempts"] == 0 for row in audit_rows),
             "filler_is_model_prediction": False, "correctness_scored": False,
             "official_score": None, "rows": audit_rows}
    return submission, audit


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def write_new(path, body):
    """An existing result is never overwritten, including on a retry."""
    with Path(path).open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("challenges", "records", "output", "audit-output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    require(args.output.name == "submission.json", "Kaggle output must be named submission.json")
    paths = [p.resolve() for p in (args.challenges, args.records, args.output, args.audit_output)]
    require(len(set(paths)) == 4, "input/output paths must be distinct")
    require(not args.output.exists() and not args.audit_output.exists(), "new output paths required")
    challenge_bytes, record_bytes = args.challenges.read_bytes(), args.records.read_bytes()
    submission, audit = build_submission(parse_json(challenge_bytes), parse_json(record_bytes))
    body = canonical(submission)
    audit.update(challenges_sha256=hashlib.sha256(challenge_bytes).hexdigest(),
                 records_sha256=hashlib.sha256(record_bytes).hexdigest(),
                 submission_sha256=hashlib.sha256(body).hexdigest())
    # The audit is created first. If writing the submission fails, retain that
    # incomplete transaction, report failure and use a new directory next time.
    write_new(args.audit_output, canonical(audit))
    write_new(args.output, body)
    print(json.dumps({key: audit[key] for key in ("task_count", "test_output_count",
          "tests_without_model_candidates", "submission_sha256", "correctness_scored")}))


if __name__ == "__main__":
    main()

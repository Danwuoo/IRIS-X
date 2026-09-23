"""Truth-free NVARC workload, atomic task ledger, result and sealed scorer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Mapping

from .arc_nvarc_data import grid, visible_task
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError
from .transport import RESULT_LIMITS, TRIAL_LIMITS, verify_zip, write_zip


TRIAL_ID = "arc-agi-2-qwen35-nvarc"
OUTBOUND_KIND = "irisx/nvarc-qwen35-input"
RESULT_KIND = "irisx/nvarc-qwen35-result"
OUTBOUND_MEMBERS = {"bindings/run.json", "cases/visible-tasks.json"}
RESULT_MEMBERS = {"bindings/run.json", "checkpoint/checkpoint.json",
                  "predictions/predictions.json", "observations/execution.json"}


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_bytes(canonical_bytes(value, newline=True))
    os.replace(temporary, path)


def make_workload(tasks: Mapping[str, Mapping[str, Any]], *, source_digest: str) -> dict[str, Any]:
    if not source_digest.startswith("sha256:") or not tasks:
        raise ValidationError("source digest and tasks required")
    cases = [visible_task(task_id, raw) for task_id, raw in sorted(tasks.items())]
    return {"format": "irisx/nvarc-visible-workload", "trial_id": TRIAL_ID,
            "source_digest": source_digest, "cases": cases,
            "task_count": len(cases),
            "test_output_count": sum(len(case["test"]) for case in cases)}


def make_binding(workload: Mapping[str, Any], *, run_id: str, model_digest: str,
                 data_digest: str, tokenizer_digest: str, runtime_digest: str,
                 config: Mapping[str, Any]) -> dict[str, Any]:
    if not run_id or any(not value.startswith("sha256:") for value in
                         (model_digest, data_digest, tokenizer_digest, runtime_digest)):
        raise ValidationError("run and immutable materials required")
    required = {"worker_count", "task_deadline_seconds", "session_budget_seconds",
                "finalization_reserve_seconds", "maximum_calls_per_task",
                "beams_per_call", "maximum_new_tokens"}
    if not required.issubset(config) or config["worker_count"] != 4:
        raise ValidationError("four-worker configuration or limits missing")
    if any(type(config[key]) is not int or config[key] < 1 for key in required - {"worker_count"}):
        raise ValidationError("runtime limit must be positive integer")
    if config["finalization_reserve_seconds"] >= config["session_budget_seconds"]:
        raise ValidationError("finalization reserve consumes whole session")
    if config.get("full_coverage") and any(
        len(case["test"]) * 8 * int(config.get("color_repeats", 2)) > config["maximum_calls_per_task"]
        for case in workload["cases"]):
        raise ValidationError("candidate call ceiling cannot cover every test input")
    binding = {"format": "irisx/nvarc-run-binding", "trial_id": TRIAL_ID,
               "run_id": run_id, "workload_digest": digest_value(workload),
               "task_count": workload["task_count"],
               "test_output_count": workload["test_output_count"],
               "source_digest": workload["source_digest"],
               "model_digest": model_digest, "data_digest": data_digest,
               "tokenizer_digest": tokenizer_digest, "runtime_digest": runtime_digest,
               "config": dict(config), "configuration_digest": digest_value(config),
               "source_view": "full-task", "truth_free": True}
    binding["identity_digest"] = digest_value(binding)
    return binding


def _truth_free(value: Any) -> None:
    forbidden = {"expected_output", "evaluator_truth", "answer_digest", "feedback",
                 "correct", "accuracy", "score_report"}
    if isinstance(value, dict):
        if forbidden & set(value):
            raise ValidationError("evaluator material in truth-free artifact")
        for child in value.values():
            _truth_free(child)
    elif isinstance(value, list):
        for child in value:
            _truth_free(child)


def build_outbound(path: Path, binding: Mapping[str, Any], workload: Mapping[str, Any]) -> str:
    if binding["workload_digest"] != digest_value(workload):
        raise ValidationError("workload binding differs")
    _truth_free(binding)
    _truth_free(workload)
    files = {"bindings/run.json": canonical_bytes(binding, newline=True),
             "cases/visible-tasks.json": canonical_bytes(workload, newline=True)}
    result = write_zip(path, OUTBOUND_KIND, binding["run_id"], files,
                       {"trial_id": TRIAL_ID, "identity_digest": binding["identity_digest"], "truth_free": True},
                       limits=TRIAL_LIMITS)
    verify_outbound(path)
    return result


def verify_outbound(path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    manifest, contents, digest = verify_zip(path, limits=TRIAL_LIMITS, package_kind=OUTBOUND_KIND)
    if set(contents) != OUTBOUND_MEMBERS:
        raise ValidationError("NVARC outbound membership differs")
    binding = json.loads(contents["bindings/run.json"])
    workload = json.loads(contents["cases/visible-tasks.json"])
    _truth_free(binding)
    _truth_free(workload)
    if (binding["workload_digest"] != digest_value(workload) or
            binding["identity_digest"] != digest_value({key: value for key, value in binding.items() if key != "identity_digest"}) or
            manifest["package_id"] != binding["run_id"]):
        raise ValidationError("NVARC outbound binding differs")
    return binding, workload, digest


def new_checkpoint(binding: Mapping[str, Any], workload: Mapping[str, Any]) -> dict[str, Any]:
    return {"format": "irisx/nvarc-task-checkpoint", "run_id": binding["run_id"],
            "identity_digest": binding["identity_digest"],
            "expected_tasks": [case["task_id"] for case in workload["cases"]],
            "reserved": {}, "completed": {}, "model_ready": {},
            "counters": {"generation_calls_reserved": 0, "sequences_reserved": 0,
                         "generation_calls_observed": 0, "sequences_observed": 0,
                         "sgd_steps": 0, "training_tokens": 0, "sdg_calls": 0},
            "sessions": [], "complete": False}


def validate_checkpoint(checkpoint: Mapping[str, Any], binding: Mapping[str, Any],
                        workload: Mapping[str, Any]) -> None:
    expected = [case["task_id"] for case in workload["cases"]]
    if (checkpoint.get("run_id") != binding["run_id"] or
            checkpoint.get("identity_digest") != binding["identity_digest"] or
            checkpoint.get("expected_tasks") != expected):
        raise ValidationError("task checkpoint identity differs")
    keys = set(expected)
    if not set(checkpoint["reserved"]).issubset(keys) or not set(checkpoint["completed"]).issubset(keys):
        raise ValidationError("task checkpoint contains an unexpected task")
    if set(checkpoint["reserved"]) & set(checkpoint["completed"]):
        raise ValidationError("task cannot be reserved and complete")
    if checkpoint["counters"]["generation_calls_reserved"] > len(expected) * binding["config"]["maximum_calls_per_task"]:
        raise ValidationError("generation call ceiling exceeded")
    if (checkpoint["counters"]["generation_calls_observed"] > checkpoint["counters"]["generation_calls_reserved"] or
            checkpoint["counters"]["sequences_observed"] > checkpoint["counters"]["sequences_reserved"]):
        raise ValidationError("observed calls or sequences exceed reservations")


def reserve_task(checkpoint: dict[str, Any], binding: Mapping[str, Any], task_id: str,
                 *, rank: int, at_utc: str) -> None:
    if task_id not in checkpoint["expected_tasks"] or task_id in checkpoint["reserved"] or task_id in checkpoint["completed"]:
        raise ValidationError("duplicate or unexpected task dispatch")
    calls = binding["config"]["maximum_calls_per_task"]
    sequences = calls * binding["config"]["beams_per_call"]
    checkpoint["reserved"][task_id] = {"rank": rank, "started_utc": at_utc,
                                        "generation_calls_reserved": calls,
                                        "sequences_reserved": sequences}
    checkpoint["counters"]["generation_calls_reserved"] += calls
    checkpoint["counters"]["sequences_reserved"] += sequences


def finish_task(checkpoint: dict[str, Any], task_id: str, record: Mapping[str, Any]) -> None:
    if task_id not in checkpoint["reserved"]:
        raise ValidationError("task was not reserved")
    reservation = checkpoint["reserved"].pop(task_id)
    if record["task_id"] != task_id or len(record["tests"]) < 1:
        raise ValidationError("terminal task record differs")
    _truth_free(record)
    observed_calls = record["tests"][-1].get("generation_calls_so_far")
    if observed_calls is not None:
        if type(observed_calls) is not int or observed_calls > reservation["generation_calls_reserved"]:
            raise ValidationError("observed generation calls exceed reservation")
        checkpoint["counters"]["generation_calls_observed"] += observed_calls
        checkpoint["counters"]["sequences_observed"] += sum(test.get("returned_sequences", 0)
                                                            for test in record["tests"])
    checkpoint["counters"]["sgd_steps"] += record.get("adaptation", {}).get("steps", 0)
    checkpoint["counters"]["training_tokens"] += record.get("adaptation", {}).get("training_tokens", 0)
    checkpoint["completed"][task_id] = {**record, "reservation": reservation}


def finalize_interrupted(checkpoint: dict[str, Any], workload: Mapping[str, Any], *, reason: str) -> None:
    by_id = {case["task_id"]: case for case in workload["cases"]}
    for task_id in list(checkpoint["reserved"]):
        tests = [{"test_index": index, "attempts": [], "status": reason, "missing_attempts": 2}
                 for index in range(len(by_id[task_id]["test"]))]
        finish_task(checkpoint, task_id, {"task_id": task_id, "tests": tests, "status": reason,
                                          "timing": {"load_seconds": None, "ttt_seconds": None,
                                                     "generate_seconds": None, "rank_seconds": None},
                                          "peak_memory_mib": None})
    for task_id in checkpoint["expected_tasks"]:
        if task_id not in checkpoint["completed"]:
            tests = [{"test_index": index, "attempts": [], "status": "not_executed", "missing_attempts": 2}
                     for index in range(len(by_id[task_id]["test"]))]
            checkpoint["completed"][task_id] = {"task_id": task_id, "tests": tests,
                                                "status": "not_executed", "reservation": None,
                                                "timing": {"load_seconds": None, "ttt_seconds": None,
                                                           "generate_seconds": None, "rank_seconds": None},
                                                "peak_memory_mib": None}
    checkpoint["complete"] = True


def build_result(path: Path, binding: Mapping[str, Any], workload: Mapping[str, Any],
                 checkpoint: Mapping[str, Any], observations: Mapping[str, Any]) -> str:
    validate_checkpoint(checkpoint, binding, workload)
    if not checkpoint["complete"] or set(checkpoint["completed"]) != set(checkpoint["expected_tasks"]):
        raise ValidationError("result needs all terminal task records")
    records = [checkpoint["completed"][key] for key in checkpoint["expected_tasks"]]
    validate_result_records(records, workload)
    _truth_free(records)
    _truth_free(checkpoint)
    _truth_free(observations)
    files = {"bindings/run.json": canonical_bytes(binding, newline=True),
             "checkpoint/checkpoint.json": canonical_bytes(checkpoint, newline=True),
             "predictions/predictions.json": canonical_bytes({"records": records}, newline=True),
             "observations/execution.json": canonical_bytes(observations, newline=True)}
    result = write_zip(path, RESULT_KIND, binding["run_id"], files,
                       {"trial_id": TRIAL_ID, "identity_digest": binding["identity_digest"],
                        "truth_free": True}, limits=RESULT_LIMITS)
    verify_result(path, binding, workload)
    return result


def validate_result_records(records: list[Mapping[str, Any]], workload: Mapping[str, Any]) -> None:
    if len(records) != len(workload["cases"]):
        raise ValidationError("result task denominator differs")
    for case, record in zip(workload["cases"], records):
        if case["task_id"] != record["task_id"] or len(case["test"]) != len(record["tests"]):
            raise ValidationError("result test denominator differs")
        for index, test in enumerate(record["tests"]):
            if test["test_index"] != index or len(test["attempts"]) > 2:
                raise ValidationError("result attempt identity differs")
            if test.get("missing_attempts") != 2 - len(test["attempts"]):
                raise ValidationError("result missing-attempt count differs")
            for attempt in test["attempts"]:
                grid(attempt)


def verify_result(path: Path, binding: Mapping[str, Any], workload: Mapping[str, Any]) -> str:
    manifest, contents, digest = verify_zip(path, limits=RESULT_LIMITS, package_kind=RESULT_KIND)
    if set(contents) != RESULT_MEMBERS or manifest["package_id"] != binding["run_id"]:
        raise ValidationError("result membership or run differs")
    if json.loads(contents["bindings/run.json"]) != binding:
        raise ValidationError("result binding differs")
    checkpoint = json.loads(contents["checkpoint/checkpoint.json"])
    _truth_free(checkpoint)
    validate_checkpoint(checkpoint, binding, workload)
    records = json.loads(contents["predictions/predictions.json"])["records"]
    _truth_free(records)
    validate_result_records(records, workload)
    if records != [checkpoint["completed"][key] for key in checkpoint["expected_tasks"]]:
        raise ValidationError("result predictions differ from checkpoint")
    _truth_free(json.loads(contents["observations/execution.json"]))
    return digest


def score_sealed(truth: Mapping[str, Any], records: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Evaluator-only, full-task pass@1/pass@2; outputs never enter packages."""
    by_id = {record["task_id"]: record for record in records}
    if len(by_id) != len(records) or set(by_id) != set(truth):
        raise ValidationError("score task denominator differs")
    pass1 = pass2 = total = complete = invalid = 0
    task_all = 0
    for task_id, raw in truth.items():
        tests = raw["test"]
        predicted = by_id[task_id]["tests"]
        if len(predicted) != len(tests):
            raise ValidationError("score test denominator differs")
        all_hit = True
        for index, item in enumerate(tests):
            if predicted[index]["test_index"] != index:
                raise ValidationError("score test index differs")
            expected = grid(item["output"])
            attempts = predicted[index]["attempts"]
            hit1 = bool(attempts) and attempts[0] == expected
            hit2 = hit1 or any(attempt == expected for attempt in attempts[1:2])
            total += 1
            pass1 += int(hit1)
            pass2 += int(hit2)
            complete += int(predicted[index]["status"] == "complete")
            invalid += int(predicted[index]["status"] in {"invalid", "missing-candidate"})
            all_hit &= hit2
        task_all += int(all_hit)
    return {"format": "irisx/nvarc-sealed-score", "metric": "test-output exact-match",
            "pass_at_1": pass1 / total, "pass_at_2": pass2 / total,
            "passed_at_1": pass1, "passed_at_2": pass2, "test_outputs": total,
            "task_all_correct": task_all, "task_count": len(truth),
            "complete_tests": complete, "invalid_or_missing_tests": invalid}

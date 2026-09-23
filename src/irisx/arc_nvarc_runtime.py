"""Truth-free NVARC workload, atomic task ledger, result and sealed scorer."""

from __future__ import annotations

import json
import math
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
TASK_TERMINAL = {"complete", "missing-candidate", "timeout", "worker_crash",
                 "oom", "interrupted_pending", "not_executed", "session_limit"}
FAILURE_TERMINAL = TASK_TERMINAL - {"complete", "missing-candidate"}
COUNTER_FIELDS = {"generation_calls_reserved", "sequences_reserved",
                  "verification_calls_reserved", "dfs_forwards_reserved",
                  "ttt_steps_reserved", "ttt_tokens_reserved",
                  "generation_calls_observed", "sequences_observed",
                  "verification_calls_observed", "explicit_forward_calls_observed",
                  "sgd_steps", "training_tokens", "sdg_calls"}
RESERVATION_FIELDS = {"generation_calls_reserved", "sequences_reserved",
                      "verification_calls_reserved", "dfs_forwards_reserved",
                      "ttt_steps_reserved", "ttt_tokens_reserved"}
CONFIG_FIELDS = {"method", "worker_count", "task_deadline_seconds", "session_budget_seconds",
                 "finalization_reserve_seconds", "maximum_calls_per_task",
                 "beams_per_call", "maximum_new_tokens", "seed", "color_repeats",
                 "ranking", "full_coverage", "decoding", "dfs_max_score",
                 "dfs_max_expansions", "dfs_cache_mode", "ttt"}
TTT_FIELDS = {"enabled", "rank", "alpha", "dropout", "use_rslora", "seed",
              "steps", "augmentation_count", "max_sequence_length", "learning_rate"}


def _is_digest(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 71 and value.startswith("sha256:") and
            all(char in "0123456789abcdef" for char in value[7:]))


def validate_workload(workload: Mapping[str, Any]) -> None:
    if (not isinstance(workload, dict) or set(workload) !=
            {"format", "trial_id", "source_digest", "cases", "task_count", "test_output_count"} or
            workload["format"] != "irisx/nvarc-visible-workload" or
            workload["trial_id"] != TRIAL_ID or
            not _is_digest(workload["source_digest"]) or
            not isinstance(workload["cases"], list) or not workload["cases"]):
        raise ValidationError("visible workload schema differs")
    names = []
    tests = 0
    for case in workload["cases"]:
        if (not isinstance(case, dict) or set(case) != {"task_id", "train", "test"} or
                not isinstance(case["task_id"], str) or not case["task_id"] or
                not isinstance(case["train"], list) or not case["train"] or
                not isinstance(case["test"], list) or not case["test"]):
            raise ValidationError("visible task schema differs")
        names.append(case["task_id"])
        for demo in case["train"]:
            if not isinstance(demo, dict) or set(demo) != {"input", "output"}:
                raise ValidationError("demonstration needs only input and output")
            grid(demo["input"]); grid(demo["output"])
        for test in case["test"]:
            if not isinstance(test, dict) or set(test) != {"input"}:
                raise ValidationError("test input contains an output or extra field")
            grid(test["input"])
            tests += 1
    if (names != sorted(set(names)) or type(workload["task_count"]) is not int or
            workload["task_count"] != len(names) or type(workload["test_output_count"]) is not int or
            workload["test_output_count"] != tests):
        raise ValidationError("visible task identities or denominator differ")


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
    validate_workload(workload)
    if not isinstance(run_id, str) or not run_id or any(not _is_digest(value) for value in
                         (model_digest, data_digest, tokenizer_digest, runtime_digest)):
        raise ValidationError("run and immutable materials required")
    if not isinstance(config, Mapping) or set(config) - CONFIG_FIELDS:
        raise ValidationError("candidate config has an unsupported field")
    if "ttt" in config and (not isinstance(config["ttt"], Mapping) or
                            set(config["ttt"]) - TTT_FIELDS):
        raise ValidationError("task adaptation config has an unsupported field")
    required = {"worker_count", "task_deadline_seconds", "session_budget_seconds",
                "finalization_reserve_seconds", "maximum_calls_per_task",
                "beams_per_call", "maximum_new_tokens"}
    if not required.issubset(config) or type(config["worker_count"]) is not int or config["worker_count"] not in {1, 4}:
        raise ValidationError("one- or four-worker configuration or limits missing")
    if config.get("method", "qwen35-compact-sft-plus-task-lora-bounded-dfs") != "qwen35-compact-sft-plus-task-lora-bounded-dfs":
        raise ValidationError("unsupported candidate method")
    if "method" in config and config.get("decoding", "bounded-dfs") != "bounded-dfs":
        raise ValidationError("candidate method and decoder differ")
    if any(type(config[key]) is not int or config[key] < 1 for key in required - {"worker_count"}):
        raise ValidationError("runtime limit must be positive integer")
    if config["finalization_reserve_seconds"] >= config["session_budget_seconds"]:
        raise ValidationError("finalization reserve consumes whole session")
    if config.get("decoding", "bounded-dfs") not in {"bounded-dfs", "hf-beam"}:
        raise ValidationError("unknown candidate decoding mode")
    if config.get("decoding", "bounded-dfs") == "bounded-dfs":
        score = config.get("dfs_max_score", 1.6094379124341003)
        expansions = config.get("dfs_max_expansions", 256)
        if (type(score) not in (int, float) or not math.isfinite(score) or
                score <= 0 or type(expansions) is not int or expansions < 1):
            raise ValidationError("bounded DFS requires finite score and expansion ceilings")
        if config.get("dfs_cache_mode", "full-prefix-recompute") not in {
                "full-prefix-recompute", "full-prefix-logit-cache"}:
            raise ValidationError("unsupported Qwen3.5 hybrid DFS cache mode")
    ttt = config.get("ttt", {})
    if "enabled" in ttt and type(ttt["enabled"]) is not bool:
        raise ValidationError("task adaptation enabled flag must be boolean")
    if ttt.get("enabled") and any(type(ttt.get(key)) is not int or ttt[key] < 1
                                  for key in ("steps", "max_sequence_length")):
        raise ValidationError("task adaptation needs positive step and token ceilings")
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


def validate_binding(binding: Mapping[str, Any], workload: Mapping[str, Any]) -> None:
    validate_workload(workload)
    fields = {"format", "trial_id", "run_id", "workload_digest", "task_count",
              "test_output_count", "source_digest", "model_digest", "data_digest",
              "tokenizer_digest", "runtime_digest", "config", "configuration_digest",
              "source_view", "truth_free", "identity_digest"}
    if not isinstance(binding, dict) or set(binding) != fields:
        raise ValidationError("run binding schema differs")
    try:
        expected = make_binding(workload, run_id=binding["run_id"],
                                model_digest=binding["model_digest"],
                                data_digest=binding["data_digest"],
                                tokenizer_digest=binding["tokenizer_digest"],
                                runtime_digest=binding["runtime_digest"],
                                config=binding["config"])
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValidationError("run binding field is invalid") from exc
    if binding != expected:
        raise ValidationError("run binding and visible workload differ")


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
    validate_binding(binding, workload)
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
    validate_binding(binding, workload)
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
                         "verification_calls_reserved": 0,
                         "dfs_forwards_reserved": 0,
                         "ttt_steps_reserved": 0, "ttt_tokens_reserved": 0,
                         "generation_calls_observed": 0, "sequences_observed": 0,
                         "verification_calls_observed": 0,
                         "explicit_forward_calls_observed": 0,
                         "sgd_steps": 0, "training_tokens": 0, "sdg_calls": 0},
            "sessions": [], "complete": False}


def _bound_reservation(config: Mapping[str, Any]) -> dict[str, int]:
    """Derive all six per-task ceilings solely from the bound configuration."""
    calls = config["maximum_calls_per_task"]
    sequences = calls * config["beams_per_call"]
    ttt = config.get("ttt", {})
    steps = ttt["steps"] if ttt.get("enabled") is True else 0
    tokens = steps * ttt["max_sequence_length"] if steps else 0
    dfs = (calls * config.get("dfs_max_expansions", 256)
           if config.get("decoding", "bounded-dfs") == "bounded-dfs" else 0)
    return {"generation_calls_reserved": calls, "sequences_reserved": sequences,
            "verification_calls_reserved": sequences, "dfs_forwards_reserved": dfs,
            "ttt_steps_reserved": steps, "ttt_tokens_reserved": tokens}


def validate_checkpoint(checkpoint: Mapping[str, Any], binding: Mapping[str, Any],
                        workload: Mapping[str, Any]) -> None:
    validate_binding(binding, workload)
    expected = [case["task_id"] for case in workload["cases"]]
    if (not isinstance(checkpoint, dict) or checkpoint.get("format") != "irisx/nvarc-task-checkpoint" or
            checkpoint.get("run_id") != binding["run_id"] or
            checkpoint.get("identity_digest") != binding["identity_digest"] or
            checkpoint.get("expected_tasks") != expected):
        raise ValidationError("task checkpoint identity differs")
    if (type(checkpoint.get("complete")) is not bool or
            not isinstance(checkpoint.get("reserved"), dict) or
            not isinstance(checkpoint.get("completed"), dict) or
            not isinstance(checkpoint.get("counters"), dict) or
            set(checkpoint["counters"]) != COUNTER_FIELDS or
            any(type(value) is not int or value < 0 for value in checkpoint["counters"].values())):
        raise ValidationError("task checkpoint counters or completion flag differ")
    if checkpoint["counters"]["sdg_calls"] != 0:
        raise ValidationError("inference checkpoint cannot record SDG calls")
    keys = set(expected)
    if not set(checkpoint["reserved"]).issubset(keys) or not set(checkpoint["completed"]).issubset(keys):
        raise ValidationError("task checkpoint contains an unexpected task")
    if set(checkpoint["reserved"]) & set(checkpoint["completed"]):
        raise ValidationError("task cannot be reserved and complete")
    if checkpoint["complete"] and (checkpoint["reserved"] or set(checkpoint["completed"]) != keys):
        raise ValidationError("completed checkpoint has pending or missing tasks")
    reservations = list(checkpoint["reserved"].values())
    by_id = {case["task_id"]: case for case in workload["cases"]}
    for task_id, record in checkpoint["completed"].items():
        if not isinstance(record, dict) or record.get("task_id") != task_id:
            raise ValidationError("completed task identity differs")
        reservation = record.get("reservation")
        if record.get("status") == "not_executed":
            if reservation is not None:
                raise ValidationError("unexecuted task has a reservation")
        elif not isinstance(reservation, dict):
            raise ValidationError("executed task lacks its reservation")
        if reservation is not None:
            reservations.append(reservation)
        validate_result_records([record], {"cases": [by_id[task_id]]})
    for reservation in reservations:
        if (not isinstance(reservation, dict) or
                set(reservation) != {"rank", "started_utc"} | RESERVATION_FIELDS or
                type(reservation["rank"]) is not int or not 0 <= reservation["rank"] < binding["config"]["worker_count"] or
                not isinstance(reservation["started_utc"], str) or
                any(type(reservation[key]) is not int or reservation[key] < 0
                    for key in RESERVATION_FIELDS)):
            raise ValidationError("task reservation schema differs")
        config = binding["config"]
        if any(reservation[key] != value for key, value in _bound_reservation(config).items()):
            raise ValidationError("task reservation does not match run limits")
    for field in RESERVATION_FIELDS:
        if checkpoint["counters"][field] != sum(item[field] for item in reservations):
            raise ValidationError("task reservation accounting differs")
    observed = {"generation_calls_observed": 0, "sequences_observed": 0,
                "verification_calls_observed": 0, "explicit_forward_calls_observed": 0,
                "sgd_steps": 0, "training_tokens": 0}
    for record in checkpoint["completed"].values():
        tests = record.get("tests")
        if not isinstance(tests, list) or not tests:
            raise ValidationError("completed task tests missing")
        observed["generation_calls_observed"] += tests[-1].get("generation_calls_so_far", 0)
        observed["sequences_observed"] += sum(test.get("returned_sequences", 0) for test in tests)
        observed["verification_calls_observed"] += tests[-1].get("verification_calls_so_far", 0)
        observed["explicit_forward_calls_observed"] += record.get("explicit_forward_calls", 0)
        observed["sgd_steps"] += record.get("adaptation", {}).get("steps", 0)
        observed["training_tokens"] += record.get("adaptation", {}).get("training_tokens", 0)
        reservation = record.get("reservation")
        if reservation is not None:
            last = tests[-1]
            per_task = {"generation_calls_observed": last.get("generation_calls_so_far", 0),
                        "sequences_observed": sum(test.get("returned_sequences", 0) for test in tests),
                        "verification_calls_observed": last.get("verification_calls_so_far", 0),
                        "explicit_forward_calls_observed": record.get("explicit_forward_calls", 0),
                        "sgd_steps": record.get("adaptation", {}).get("steps", 0),
                        "training_tokens": record.get("adaptation", {}).get("training_tokens", 0)}
            ceilings = {"generation_calls_observed": reservation["generation_calls_reserved"],
                        "sequences_observed": reservation["sequences_reserved"],
                        "verification_calls_observed": reservation["verification_calls_reserved"],
                        "explicit_forward_calls_observed": reservation["dfs_forwards_reserved"] +
                            8 * reservation["verification_calls_reserved"],
                        "sgd_steps": reservation["ttt_steps_reserved"],
                        "training_tokens": reservation["ttt_tokens_reserved"]}
            if any(type(per_task[key]) is not int or not 0 <= per_task[key] <= value
                   for key, value in ceilings.items()):
                raise ValidationError("task observations exceed bound reservation")
        elif any((record.get("explicit_forward_calls", 0),
                  record.get("adaptation", {}).get("steps", 0),
                  record.get("adaptation", {}).get("training_tokens", 0))):
            raise ValidationError("unexecuted task has observed model work")
    if any(checkpoint["counters"][field] != value for field, value in observed.items()):
        raise ValidationError("observed task accounting differs")
    if checkpoint["counters"]["generation_calls_reserved"] > len(expected) * binding["config"]["maximum_calls_per_task"]:
        raise ValidationError("generation call ceiling exceeded")
    if (checkpoint["counters"]["generation_calls_observed"] > checkpoint["counters"]["generation_calls_reserved"] or
            checkpoint["counters"]["sequences_observed"] > checkpoint["counters"]["sequences_reserved"] or
            checkpoint["counters"].get("verification_calls_observed", 0) > checkpoint["counters"]["verification_calls_reserved"] or
            checkpoint["counters"].get("explicit_forward_calls_observed", 0) >
            checkpoint["counters"]["dfs_forwards_reserved"] + 8 * checkpoint["counters"]["verification_calls_reserved"] or
            checkpoint["counters"]["sgd_steps"] > checkpoint["counters"]["ttt_steps_reserved"] or
            checkpoint["counters"]["training_tokens"] > checkpoint["counters"]["ttt_tokens_reserved"]):
        raise ValidationError("observed calls or sequences exceed reservations")


def reserve_task(checkpoint: dict[str, Any], binding: Mapping[str, Any], task_id: str,
                 *, rank: int, at_utc: str) -> None:
    if (type(rank) is not int or not 0 <= rank < binding["config"]["worker_count"] or
            task_id not in checkpoint["expected_tasks"] or task_id in checkpoint["reserved"] or task_id in checkpoint["completed"]):
        raise ValidationError("duplicate or unexpected task dispatch")
    limits = _bound_reservation(binding["config"])
    checkpoint["reserved"][task_id] = {"rank": rank, "started_utc": at_utc,
                                        **limits}
    for key, value in limits.items():
        checkpoint["counters"][key] += value


def finish_task(checkpoint: dict[str, Any], task_id: str, record: Mapping[str, Any]) -> None:
    if task_id not in checkpoint["reserved"]:
        raise ValidationError("task was not reserved")
    reservation = checkpoint["reserved"][task_id]
    if record["task_id"] != task_id or len(record["tests"]) < 1:
        raise ValidationError("terminal task record differs")
    _truth_free(record)
    observed_calls = record["tests"][-1].get("generation_calls_so_far")
    sequences = 0
    verification = 0
    if observed_calls is not None:
        if (type(observed_calls) is not int or observed_calls < 0 or
                observed_calls > reservation["generation_calls_reserved"]):
            raise ValidationError("observed generation calls exceed reservation")
        sequences = sum(test.get("returned_sequences", 0) for test in record["tests"])
        verification = record["tests"][-1].get("verification_calls_so_far", 0)
        if (type(sequences) is not int or sequences < 0 or
                type(verification) is not int or verification < 0 or
                verification > sequences or sequences > reservation["sequences_reserved"]):
            raise ValidationError("candidate or verification count exceeds reservation")
    forwards = record.get("explicit_forward_calls", 0)
    steps = record.get("adaptation", {}).get("steps", 0)
    tokens = record.get("adaptation", {}).get("training_tokens", 0)
    if (type(forwards) is not int or forwards < 0 or
            forwards > reservation["dfs_forwards_reserved"] + 8 * reservation["verification_calls_reserved"] or
            type(steps) is not int or steps < 0 or steps > reservation["ttt_steps_reserved"] or
            type(tokens) is not int or tokens < 0 or tokens > reservation["ttt_tokens_reserved"]):
        raise ValidationError("model forward or TTT observations exceed reservation")
    checkpoint["reserved"].pop(task_id)
    if observed_calls is not None:
        checkpoint["counters"]["generation_calls_observed"] += observed_calls
        checkpoint["counters"]["sequences_observed"] += sequences
        checkpoint["counters"]["verification_calls_observed"] += verification
    checkpoint["counters"]["explicit_forward_calls_observed"] += forwards
    checkpoint["counters"]["sgd_steps"] += steps
    checkpoint["counters"]["training_tokens"] += tokens
    checkpoint["completed"][task_id] = {**record, "reservation": reservation}


def finalize_interrupted(checkpoint: dict[str, Any], workload: Mapping[str, Any], *, reason: str) -> None:
    by_id = {case["task_id"]: case for case in workload["cases"]}
    for task_id in list(checkpoint["reserved"]):
        tests = [{"test_index": index, "attempts": [], "status": reason, "missing_attempts": 2}
                 for index in range(len(by_id[task_id]["test"]))]
        finish_task(checkpoint, task_id, {"task_id": task_id, "tests": tests, "status": reason,
                                          "failure": reason,
                                          "timing": {"load_seconds": None, "ttt_seconds": None,
                                                     "generate_seconds": None, "rank_seconds": None},
                                          "peak_memory_mib": None})
    for task_id in checkpoint["expected_tasks"]:
        if task_id not in checkpoint["completed"]:
            tests = [{"test_index": index, "attempts": [], "status": "not_executed", "missing_attempts": 2}
                     for index in range(len(by_id[task_id]["test"]))]
            checkpoint["completed"][task_id] = {"task_id": task_id, "tests": tests,
                                                "status": "not_executed", "reservation": None,
                                                "failure": reason,
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
        if (not isinstance(record, dict) or case["task_id"] != record.get("task_id") or
                not isinstance(record.get("tests"), list) or
                len(case["test"]) != len(record["tests"]) or
                record.get("status") not in TASK_TERMINAL):
            raise ValidationError("result test denominator differs")
        prior_calls = prior_verifications = 0
        has_missing = False
        for index, test in enumerate(record["tests"]):
            if (not isinstance(test, dict) or type(test.get("test_index")) is not int or
                    test["test_index"] != index or not isinstance(test.get("attempts"), list) or
                    len(test["attempts"]) > 2 or test.get("status") not in TASK_TERMINAL):
                raise ValidationError("result attempt identity differs")
            if (type(test.get("missing_attempts")) is not int or
                    test["missing_attempts"] != 2 - len(test["attempts"])):
                raise ValidationError("result missing-attempt count differs")
            if test["status"] == "complete" and len(test["attempts"]) != 2:
                raise ValidationError("complete test requires two candidates")
            if test["status"] == "missing-candidate" and len(test["attempts"]) == 2:
                raise ValidationError("missing-candidate test is not missing")
            if test["status"] in FAILURE_TERMINAL and test["attempts"]:
                raise ValidationError("failed test cannot claim model candidates")
            has_missing |= test["status"] == "missing-candidate"
            for field, prior in (("generation_calls_so_far", prior_calls),
                                 ("verification_calls_so_far", prior_verifications)):
                value = test.get(field)
                if value is not None and (type(value) is not int or value < prior):
                    raise ValidationError("result call counters are invalid or regressed")
            returned = test.get("returned_sequences")
            if returned is not None and (type(returned) is not int or returned < 0):
                raise ValidationError("result returned-sequence count differs")
            prior_calls = test.get("generation_calls_so_far", prior_calls)
            prior_verifications = test.get("verification_calls_so_far", prior_verifications)
            for attempt in test["attempts"]:
                grid(attempt)
        if record["status"] == "complete" and any(test["status"] != "complete" for test in record["tests"]):
            raise ValidationError("complete task contains incomplete tests")
        if record["status"] == "missing-candidate" and not has_missing:
            raise ValidationError("missing-candidate task has no missing test")
        if record["status"] in FAILURE_TERMINAL and any(test["status"] != record["status"]
                                                        for test in record["tests"]):
            raise ValidationError("failed task test statuses differ")


def verify_result(path: Path, binding: Mapping[str, Any], workload: Mapping[str, Any]) -> str:
    manifest, contents, digest = verify_zip(path, limits=RESULT_LIMITS, package_kind=RESULT_KIND)
    if set(contents) != RESULT_MEMBERS or manifest["package_id"] != binding["run_id"]:
        raise ValidationError("result membership or run differs")
    if json.loads(contents["bindings/run.json"]) != binding:
        raise ValidationError("result binding differs")
    checkpoint = json.loads(contents["checkpoint/checkpoint.json"])
    _truth_free(checkpoint)
    validate_checkpoint(checkpoint, binding, workload)
    if checkpoint["complete"] is not True:
        raise ValidationError("result checkpoint is not terminal")
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

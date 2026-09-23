"""Decision 0020 source audit and bounded, truth-free ablation helpers."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping
import zipfile

from . import arc_prompt_pilot as pilot
from .arc_prompt_pilot import BASE_INSTRUCTION, visible_projection
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError
from .transport import RESULT_LIMITS, TRIAL_LIMITS, digest_path, verify_zip, write_zip

TRIAL_ID = "arc-agi-2-budget-ablation"
DIAGNOSTIC_RUN = "budget-ablation-diagnostic-001"
VALIDATION_RUN = "budget-ablation-validation-001"
ARMS = {"A1": (False, 1024), "A2": (False, 4096), "A3": (True, 4096)}
MAX_GENERATIONS = 576
TIMEOUT_SECONDS = 300
MODEL_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
ACTIVE_REFLECTION_PROFILE = {"model": "gpt-6-sol", "reasoning_effort": "xhigh"}
COMPETITION_SHA256 = "779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5"
OUTBOUND_KIND = "irisx/arc-budget-ablation-input"
RESULT_KIND = "irisx/arc-budget-ablation-result"
OUTBOUND_PATHS = {"bindings/run.json", "cases/jobs.json", "sources/model-manifest.json",
                  "sources/base-wheel-manifest.json", "runtime/dependencies.json"}
RESULT_PATHS = {"bindings/run.json", "checkpoint/checkpoint.json", "predictions/predictions.json",
                "observations/execution.json", "logs/progress.jsonl"}
MODEL_REPOSITORY = pilot.MODEL_REPOSITORY
COMPETITION_CHALLENGE_FILENAME = pilot.COMPETITION_CHALLENGE_FILENAME
WORKER_COUNT = 4
SESSION_BUDGET_SECONDS = 39_600
FINALIZATION_RESERVE_SECONDS = 900
TASK_DEADLINE_SECONDS = TIMEOUT_SECONDS
DispatchState = pilot.DispatchState
render_candidate = pilot.render_candidate
parse_grid_text = pilot.parse_grid_text
validate_grid = pilot.validate_grid
validate_material_manifest = pilot.validate_material_manifest


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_bytes(canonical_bytes(value, newline=True))
    os.replace(temporary, path)


def _read_solver_zip(path: Path) -> Mapping[str, Any]:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("cases/solver-cases.json"))


def _differences(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    if left == right:
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left) | set(right))
        return sum((_differences(left.get(key), right.get(key), f"{path}.{key}" if path else key) for key in keys), [])
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [{"path": path, "kind": "length", "pinned_length": len(left), "competition_length": len(right)}]
        if left and isinstance(left[0], list) and right and isinstance(right[0], list) and all(isinstance(row, list) for row in left + right):
            cells = sum(a != b for row_a, row_b in zip(left, right) for a, b in zip(row_a, row_b))
            if cells:
                return [{"path": path, "kind": "grid_cells", "differing_cells": cells}]
        return sum((_differences(a, b, f"{path}[{i}]") for i, (a, b) in enumerate(zip(left, right))), [])
    return [{"path": path, "kind": "value", "pinned": left, "competition": right}]


def audit_visible_source(
    competition_path: Path, baseline_solver_path: Path, holdout_outbound_path: Path,
    split_path: Path, training_source_root: Path,
) -> dict[str, Any]:
    """Audit every selected visible case without opening holdout answer material."""
    if digest_path(competition_path) != f"sha256:{COMPETITION_SHA256}":
        raise ValidationError("official challenge digest differs from the expected snapshot")
    competition = json.loads(competition_path.read_bytes())
    split = json.loads(split_path.read_bytes())
    baseline = json.loads(baseline_solver_path.read_bytes())
    holdout = _read_solver_zip(holdout_outbound_path)
    cases = baseline["cases"] + holdout["cases"]
    groups = {r["task_id"]: r["group"] for r in split["records"]}
    if len(cases) != 512 or len(groups) != 512 or len({c["task_id"] for c in cases}) != 512:
        raise ValidationError("visible source audit lacks all 512 selected cases")
    reports = []
    execution_view_errors = []
    for case in cases:
        task_id = case["task_id"]
        if case["group"] != groups[task_id] or task_id not in competition:
            raise ValidationError(f"selected case identity differs: {task_id}")
        if case["group"] == "locked-holdout":
            pinned = {"train": case["train"], "test": case["test"]}
        else:
            pinned = visible_projection(json.loads((training_source_root / f"{task_id}.json").read_bytes()))
            expected_index_zero = {"train": pinned["train"], "test": pinned["test"][:1]}
            if expected_index_zero != {"train": case["train"], "test": case["test"]}:
                execution_view_errors.append(task_id)
        mounted = visible_projection(competition[task_id])
        differences = _differences(pinned, mounted)
        if differences:
            reports.append({"task_id": task_id, "group": case["group"], "differences": differences,
                            "pinned_visible_digest": digest_value(pinned), "competition_visible_digest": digest_value(mounted)})
    blocked = sorted(set(execution_view_errors + [r["task_id"] for r in reports if r["group"] != "locked-holdout"]))
    return {"format": "irisx/arc-budget-visible-audit", "format_version": "1.0",
            "competition_challenge_digest": digest_path(competition_path),
            "baseline_solver_digest": digest_path(baseline_solver_path),
            "holdout_outbound_digest": digest_path(holdout_outbound_path),
            "split_digest": digest_path(split_path), "audited_case_count": 512,
            "executable_case_count": 384, "executable_parity": not blocked,
            "executable_mismatches": blocked, "holdout_mismatch_count": sum(r["group"] == "locked-holdout" for r in reports),
            "mismatches": sorted(reports, key=lambda item: item["task_id"]),
            "holdout_status": "incompatible-unscored" if any(r["group"] == "locked-holdout" for r in reports) else "compatible-unscored",
            "f3e62deb_old_gate": {"source_visible_equal": not any(r["task_id"] == "f3e62deb" for r in reports),
                                  "pinned_test_input_count": len(next(c for c in holdout["cases"] if c["task_id"] == "f3e62deb")["test"]) if any(c["task_id"] == "f3e62deb" for c in holdout["cases"]) else None,
                                  "old_runtime_selected_test_input_count": 1,
                                  "cause": "old holdout runtime compared test-index-0 projection against full multi-test solver case"}}


def build_diagnostic_cohort(baseline_result: Path, baseline_score: Path) -> dict[str, Any]:
    with zipfile.ZipFile(baseline_result) as archive:
        records = json.loads(archive.read("predictions/predictions.json"))["records"]
    score = json.loads(baseline_score.read_bytes())
    by_id = {record["task_id"]: record for record in records}
    strata: dict[str, list[str]] = {"baseline-correct": [], "capped": [], "wrong-size": [], "wrong-content": []}
    for item in score["records"]:
        if item["group"] != "optimization-train":
            continue
        task_id = item["task_id"]
        record = by_id[task_id]
        if item["correct"]:
            strata["baseline-correct"].append(task_id)
        elif record["generation"]["stop_reason"] == "maximum_new_tokens":
            strata["capped"].append(task_id)
        elif item["predicted_output"] is None or (len(item["predicted_output"]), len(item["predicted_output"][0])) != (len(item["expected_output"]), len(item["expected_output"][0])):
            strata["wrong-size"].append(task_id)
        else:
            strata["wrong-content"].append(task_id)
    if len(strata["baseline-correct"]) != 18 or len(strata["capped"]) != 22:
        raise ValidationError(f"baseline strata differ from authorized cohort: {dict((k,len(v)) for k,v in strata.items())}")
    rank = lambda task_id: (hashlib.sha256(f"arc-budget-diagnostic-20260923:{task_id}".encode()).hexdigest(), task_id)
    selected = {"baseline-correct": sorted(strata["baseline-correct"], key=rank),
                "capped": sorted(strata["capped"], key=rank),
                "wrong-size": sorted(strata["wrong-size"], key=rank)[:12],
                "wrong-content": sorted(strata["wrong-content"], key=rank)[:12]}
    if len(set(sum(selected.values(), []))) != 64:
        raise ValidationError("diagnostic cohort is not 64 unique cases")
    manifest = {"format": "irisx/arc-budget-diagnostic-cohort", "format_version": "1.0",
                "selection_seed": "arc-budget-diagnostic-20260923", "strata": selected,
                "baseline_result_digest": digest_path(baseline_result), "baseline_score_digest": digest_path(baseline_score)}
    manifest["manifest_digest"] = digest_value(manifest)
    return manifest


def ordered_diagnostic_jobs(cohort: Mapping[str, Any]) -> list[dict[str, Any]]:
    ids = sum(cohort["strata"].values(), [])
    ids.sort(key=lambda task_id: hashlib.sha256(f"arc-budget-dispatch-20260923:{task_id}".encode()).hexdigest())
    return [{"job_key": f"{task_id}:{arm}", "task_id": task_id, "arm": arm,
             "enable_thinking": ARMS[arm][0], "maximum_new_tokens": ARMS[arm][1]}
            for task_id in ids for arm in ("A1", "A2", "A3")]


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    if ledger.get("trial_id") != TRIAL_ID or ledger.get("generation_ceiling") != MAX_GENERATIONS:
        raise ValidationError("ablation ledger identity or ceiling differs")
    if ({key: ledger.get("development", {}).get(key) for key in ACTIVE_REFLECTION_PROFILE} != ACTIVE_REFLECTION_PROFILE
            or ledger.get("reflection") != {**ACTIVE_REFLECTION_PROFILE, "proposer_calls": 0}):
        raise ValidationError("ablation permits no proposer calls")
    if ledger["diagnostic"]["reserved_generations"] != 192 or ledger["validation"]["reserved_generations"] != 384:
        raise ValidationError("ablation generation reservations differ")
    if ledger["diagnostic"].get("consumed_generations", 0) + ledger["validation"].get("consumed_generations", 0) > MAX_GENERATIONS:
        raise ValidationError("ablation generation ceiling exceeded")


def update_ledger(path: Path, section: str, **updates: Any) -> dict[str, Any]:
    ledger = json.loads(path.read_bytes())
    validate_ledger(ledger)
    ledger[section].update(updates)
    validate_ledger(ledger)
    atomic_json(path, ledger)
    return ledger


def make_workload(baseline_solver: Path, *, run_id: str, cohort: Mapping[str, Any] | None = None,
                  validation_arm: str | None = None) -> dict[str, Any]:
    baseline = json.loads(baseline_solver.read_bytes())
    by_id = {case["task_id"]: case for case in baseline["cases"]}
    if run_id == DIAGNOSTIC_RUN and cohort is not None and validation_arm is None:
        planned = ordered_diagnostic_jobs(cohort)
    elif run_id == VALIDATION_RUN and cohort is None and validation_arm in ARMS:
        planned = [{"job_key": f"{case['task_id']}:{validation_arm}", "task_id": case["task_id"],
                    "arm": validation_arm, "enable_thinking": ARMS[validation_arm][0],
                    "maximum_new_tokens": ARMS[validation_arm][1]} for case in baseline["cases"]]
    else:
        raise ValidationError("ablation run identity, cohort, or validation arm is invalid")
    jobs = []
    for item in planned:
        source = by_id[item["task_id"]]
        if source["group"] not in {"optimization-train", "selection-dev"}:
            raise ValidationError("ablation workload includes holdout")
        jobs.append({**item, "group": source["group"], "train": source["train"], "test": source["test"]})
    expected = 192 if run_id == DIAGNOSTIC_RUN else 384
    if len(jobs) != expected or len({job["job_key"] for job in jobs}) != expected:
        raise ValidationError("ablation workload denominator is invalid")
    return {"format": "irisx/arc-budget-jobs", "format_version": "1.0", "trial_id": TRIAL_ID,
            "run_id": run_id, "instruction": BASE_INSTRUCTION, "jobs": jobs}


def make_run_binding(workload: Mapping[str, Any], *, source_audit: Mapping[str, Any],
                     model_manifest_digest: str, base_wheel_manifest_digest: str,
                     baseline_split_digest: str, cohort_digest: str | None = None) -> dict[str, Any]:
    if not source_audit["executable_parity"] or source_audit["audited_case_count"] != 512:
        raise ValidationError("all 384 executable cases must pass the 512-case source audit")
    run_id = workload["run_id"]
    configuration = {"worker_count": 4, "task_deadline_seconds": TIMEOUT_SECONDS,
                     "session_budget_seconds": SESSION_BUDGET_SECONDS,
                     "finalization_reserve_seconds": FINALIZATION_RESERVE_SECONDS,
                     "generation": {"invocation_quota": len(workload["jobs"]), "num_return_sequences": 1,
                                    "num_beams": 1, "do_sample": False, "seed": 20260923},
                     "retry": False, "warmup_generation": False}
    run = {"format": "irisx/arc-budget-run-binding", "format_version": "1.0", "trial_id": TRIAL_ID,
           "run_id": run_id, "source": {"competition_slug": pilot.COMPETITION_SLUG,
                                      "competition_challenge_digest": source_audit["competition_challenge_digest"],
                                      "visible_audit_digest": digest_value(source_audit), "solutions_opened_in_runtime": False},
           "model": {"repository": MODEL_REPOSITORY, "revision": MODEL_REVISION,
                     "model_manifest_digest": model_manifest_digest},
           "baseline_split_digest": baseline_split_digest, "diagnostic_cohort_digest": cohort_digest,
           "prompt": {"candidate": "B1", "instruction_digest": digest_value(BASE_INSTRUCTION)},
           "workload_digest": digest_value(workload), "base_wheel_manifest_digest": base_wheel_manifest_digest,
           "configuration": configuration, "configuration_digest": digest_value(configuration)}
    run["run_identity_digest"] = digest_value(run)
    validate_run_binding(run, workload)
    return run


def validate_run_binding(run: Mapping[str, Any], workload: Mapping[str, Any]) -> None:
    run_id = run.get("run_id")
    if run.get("trial_id") != TRIAL_ID or run_id not in {DIAGNOSTIC_RUN, VALIDATION_RUN} or workload.get("run_id") != run_id or workload.get("trial_id") != TRIAL_ID:
        raise ValidationError("ablation run identity is invalid")
    if run.get("run_identity_digest") != digest_value({key: value for key, value in run.items() if key != "run_identity_digest"}):
        raise ValidationError("ablation run digest is invalid")
    if run.get("workload_digest") != digest_value(workload) or workload.get("instruction") != BASE_INSTRUCTION:
        raise ValidationError("ablation workload or B1 instruction changed")
    if run.get("model", {}).get("revision") != MODEL_REVISION or run.get("model", {}).get("repository") != MODEL_REPOSITORY:
        raise ValidationError("ablation solver model changed")
    if run.get("source", {}).get("competition_challenge_digest") != f"sha256:{COMPETITION_SHA256}" or run["source"].get("solutions_opened_in_runtime") is not False:
        raise ValidationError("ablation source changed")
    configuration = run["configuration"]
    if (configuration.get("worker_count") != 4 or configuration.get("task_deadline_seconds") != TIMEOUT_SECONDS
            or configuration.get("session_budget_seconds") != SESSION_BUDGET_SECONDS
            or configuration.get("finalization_reserve_seconds") != FINALIZATION_RESERVE_SECONDS
            or configuration.get("retry") is not False or configuration.get("warmup_generation") is not False
            or configuration.get("generation") != {"invocation_quota": 192 if run_id == DIAGNOSTIC_RUN else 384,
                                                   "num_return_sequences": 1, "num_beams": 1,
                                                   "do_sample": False, "seed": 20260923}
            or run.get("configuration_digest") != digest_value(configuration)):
        raise ValidationError("ablation generation configuration changed")
    jobs = workload.get("jobs", [])
    expected = 192 if run_id == DIAGNOSTIC_RUN else 384
    if len(jobs) != expected or configuration["generation"].get("invocation_quota") != expected or len({job.get("job_key") for job in jobs}) != expected:
        raise ValidationError("ablation job quota or keys changed")
    counts = Counter(job.get("arm") for job in jobs)
    if run_id == DIAGNOSTIC_RUN and counts != Counter({"A1": 64, "A2": 64, "A3": 64}):
        raise ValidationError("diagnostic arm counts changed")
    if run_id == DIAGNOSTIC_RUN and (Counter(job["task_id"] for job in jobs) != Counter({job["task_id"]: 3 for job in jobs})
                                     or any(job["group"] != "optimization-train" for job in jobs)):
        raise ValidationError("diagnostic cohort is not 64 train cases crossed with three arms")
    if run_id == VALIDATION_RUN and (len(counts) != 1 or list(counts.values()) != [384]):
        raise ValidationError("validation arm counts changed")
    if run_id == VALIDATION_RUN and Counter(job["group"] for job in jobs) != Counter({"optimization-train": 256, "selection-dev": 128}):
        raise ValidationError("validation group denominator changed")
    for job in jobs:
        arm = job.get("arm")
        if arm not in ARMS or (job.get("enable_thinking"), job.get("maximum_new_tokens")) != ARMS[arm]:
            raise ValidationError("ablation job generation configuration changed")
        if job.get("job_key") != f"{job.get('task_id')}:{arm}" or job.get("group") not in {"optimization-train", "selection-dev"} or len(job.get("test", [])) != 1 or set(job["test"][0]) != {"input"}:
            raise ValidationError("ablation job identity or visible inputs changed")


def build_outbound(path: Path, run: Mapping[str, Any], workload: Mapping[str, Any],
                   old_baseline_outbound: Path) -> str:
    validate_run_binding(run, workload)
    with zipfile.ZipFile(old_baseline_outbound) as archive:
        model_manifest = archive.read("sources/model-manifest.json")
        base_wheels = archive.read("sources/base-wheel-manifest.json")
        dependencies = json.loads(archive.read("runtime/dependencies.json"))
    if digest_value(json.loads(model_manifest)["files"]) != run["model"]["model_manifest_digest"] or json.loads(base_wheels)["manifest_digest"] != run["base_wheel_manifest_digest"]:
        raise ValidationError("reused model or wheel manifest differs")
    dependencies["runtime_wheel_manifest_digest"] = None
    files = {"bindings/run.json": canonical_bytes(run, newline=True),
             "cases/jobs.json": canonical_bytes(workload, newline=True),
             "sources/model-manifest.json": model_manifest,
             "sources/base-wheel-manifest.json": base_wheels,
             "runtime/dependencies.json": canonical_bytes(dependencies, newline=True)}
    metadata = {"trial_id": TRIAL_ID, "run_id": run["run_id"], "run_identity_digest": run["run_identity_digest"],
                "workload_digest": run["workload_digest"], "truth_free": True}
    digest = write_zip(path, OUTBOUND_KIND, run["run_id"], files, metadata, limits=TRIAL_LIMITS)
    verify_outbound(path)
    return digest


def verify_outbound(path: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    manifest, contents, digest = verify_zip(path, limits=TRIAL_LIMITS, package_kind=OUTBOUND_KIND)
    if set(contents) != OUTBOUND_PATHS:
        raise ValidationError("ablation outbound members differ")
    run = json.loads(contents["bindings/run.json"])
    workload = json.loads(contents["cases/jobs.json"])
    validate_run_binding(run, workload)
    if manifest.get("package_id") != run["run_id"]:
        raise ValidationError("ablation outbound package identity differs")
    if any(marker in payload for payload in contents.values() for marker in (b"evaluator-truth", b'"expected_output"', b'"score"', b'"feedback"')):
        raise ValidationError("ablation outbound contains evaluator material")
    return manifest, contents, digest


def validate_competition_mount(path: Path, run: Mapping[str, Any], workload: Mapping[str, Any]) -> dict[str, Any]:
    if digest_path(path) != run["source"]["competition_challenge_digest"]:
        raise ValidationError("runtime competition source digest differs")
    competition = json.loads(path.read_bytes())
    if len(competition) != 1000:
        raise ValidationError("runtime competition source count differs")
    for job in workload["jobs"]:
        mounted = competition[job["task_id"]]
        if {"train": mounted["train"], "test": mounted["test"][:1]} != {"train": job["train"], "test": job["test"]}:
            raise ValidationError(f"runtime competition case differs: {job['task_id']}")
    return {"challenge_digest": digest_path(path), "available_task_count": len(competition),
            "selected_job_count": len(workload["jobs"]), "selected_test_index": 0, "solutions_opened": False}


def new_checkpoint(run: Mapping[str, Any], workload: Mapping[str, Any]) -> dict[str, Any]:
    return {"format": "irisx/arc-budget-checkpoint", "format_version": "1.0", "trial_id": TRIAL_ID,
            "run_id": run["run_id"], "run_identity_digest": run["run_identity_digest"],
            "expected_jobs": [job["job_key"] for job in workload["jobs"]],
            "model_ready": {}, "generation_invocations": {}, "completed": {}, "sessions": [], "complete": False}


def validate_checkpoint(checkpoint: Mapping[str, Any], run: Mapping[str, Any], workload: Mapping[str, Any]) -> None:
    expected = [job["job_key"] for job in workload["jobs"]]
    if checkpoint.get("trial_id") != TRIAL_ID or checkpoint.get("run_id") != run["run_id"] or checkpoint.get("run_identity_digest") != run["run_identity_digest"] or checkpoint.get("expected_jobs") != expected:
        raise ValidationError("ablation checkpoint identity differs")
    if len(checkpoint.get("generation_invocations", {})) > len(expected) or not set(checkpoint.get("generation_invocations", {})).issubset(expected) or not set(checkpoint.get("completed", {})).issubset(expected):
        raise ValidationError("ablation checkpoint has unexpected or excess jobs")
    if not set(checkpoint.get("model_ready", {})).issubset({"0", "1", "2", "3"}):
        raise ValidationError("ablation checkpoint worker keys differ")


def build_result_package(output: Path, run: Mapping[str, Any], workload: Mapping[str, Any],
                         checkpoint: Mapping[str, Any], observations: Mapping[str, Any], progress: bytes) -> str:
    validate_checkpoint(checkpoint, run, workload)
    records = [checkpoint["completed"][key] for key in checkpoint["expected_jobs"] if key in checkpoint["completed"]]
    files = {"bindings/run.json": canonical_bytes(run, newline=True),
             "checkpoint/checkpoint.json": canonical_bytes(checkpoint, newline=True),
             "predictions/predictions.json": canonical_bytes({"format": "irisx/arc-budget-predictions", "format_version": "1.0", "trial_id": TRIAL_ID, "run_id": run["run_id"], "records": records}, newline=True),
             "observations/execution.json": canonical_bytes(observations, newline=True), "logs/progress.jsonl": progress}
    metadata = {"trial_id": TRIAL_ID, "run_id": run["run_id"], "run_identity_digest": run["run_identity_digest"],
                "expected_job_count": len(checkpoint["expected_jobs"]), "terminal_job_count": len(records), "truth_free": True}
    return write_zip(output, RESULT_KIND, run["run_id"], files, metadata, limits=RESULT_LIMITS)


def verify_result_package(path: Path, outbound: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    _, input_contents, _ = verify_outbound(outbound)
    run, workload = json.loads(input_contents["bindings/run.json"]), json.loads(input_contents["cases/jobs.json"])
    manifest, contents, digest = verify_zip(path, limits=RESULT_LIMITS, package_kind=RESULT_KIND)
    if set(contents) != RESULT_PATHS or manifest.get("package_id") != run["run_id"] or json.loads(contents["bindings/run.json"]) != run:
        raise ValidationError("ablation result membership or binding differs")
    checkpoint = json.loads(contents["checkpoint/checkpoint.json"])
    validate_checkpoint(checkpoint, run, workload)
    predictions = json.loads(contents["predictions/predictions.json"])
    records = predictions["records"]
    expected_records = [checkpoint["completed"][key] for key in checkpoint["expected_jobs"] if key in checkpoint["completed"]]
    if (len(records) != len({item["job_key"] for item in records})
            or {item["job_key"] for item in records} != set(checkpoint["completed"])
            or records != expected_records):
        raise ValidationError("ablation predictions differ from checkpoint")
    if any(marker in payload for payload in contents.values() for marker in (b"evaluator-truth", b'"expected_output"', b'"score"', b'"feedback"')):
        raise ValidationError("ablation result contains evaluator material")
    return manifest, contents, digest


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _summarize(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    times = [float(record["elapsed_seconds"]) for record in records if isinstance(record.get("elapsed_seconds"), (int, float))]
    tokens = [int(record["generated_tokens"]) for record in records if isinstance(record.get("generated_tokens"), int)]
    return {"correct": sum(bool(record["correct"]) for record in records), "denominator": len(records),
            "valid_grid": sum(record["status"] == "valid" for record in records),
            "parse_failures": sum(record["status"] == "invalid" for record in records),
            "cap_hits": sum(record["stop_reason"] == "maximum_new_tokens" for record in records),
            "raw_completions_truncated": sum(bool(record.get("raw_completion_truncated")) for record in records),
            "timeouts": sum(record["status"] == "timeout" for record in records),
            "elapsed_p50_seconds": _percentile(times, .5), "elapsed_p95_seconds": _percentile(times, .95),
            "elapsed_total_seconds": sum(times), "generated_tokens_p50": _percentile(tokens, .5),
            "generated_tokens_p95": _percentile(tokens, .95), "generated_tokens_total": sum(tokens),
            "reasoning_tokens_total": sum(record["reasoning_tokens"] for record in records if isinstance(record["reasoning_tokens"], int)),
            "final_tokens_total": sum(record["final_tokens"] for record in records if isinstance(record["final_tokens"], int))}


def score_ablation_result(result: Path, outbound: Path, baseline_score: Path,
                          baseline_result: Path, cohort: Mapping[str, Any] | None = None) -> dict[str, Any]:
    _, contents, result_digest = verify_result_package(result, outbound)
    _, input_contents, outbound_digest = verify_outbound(outbound)
    run = json.loads(input_contents["bindings/run.json"])
    workload = json.loads(input_contents["cases/jobs.json"])
    predictions = json.loads(contents["predictions/predictions.json"])["records"]
    by_job = {record["job_key"]: record for record in predictions}
    baseline = json.loads(baseline_score.read_bytes())
    base_by_id = {record["task_id"]: record for record in baseline["records"] if record["group"] != "locked-holdout"}
    with zipfile.ZipFile(baseline_result) as archive:
        baseline_pred = {record["task_id"]: record for record in json.loads(archive.read("predictions/predictions.json"))["records"]}
    expected = {job["job_key"] for job in workload["jobs"]}
    if expected != set(by_job):
        raise ValidationError("ablation score requires every job terminal record")
    details = []
    for job in workload["jobs"]:
        raw = by_job[job["job_key"]]
        original = base_by_id[job["task_id"]]
        if raw["task_id"] != job["task_id"] or raw["group"] != job["group"] or raw["arm"] != job["arm"]:
            raise ValidationError("ablation prediction job binding differs")
        predicted = raw.get("attempts", [])
        correct = raw["status"] == "valid" and len(predicted) == 1 and predicted[0] == original["expected_output"]
        if raw["status"] == "valid" and len(predicted) != 1:
            raise ValidationError("valid ablation prediction lacks one grid")
        detail = {"task_id": job["task_id"], "group": job["group"], "arm": job["arm"],
                  "job_key": job["job_key"], "status": raw["status"], "correct": correct,
                  "baseline_correct": original["correct"], "stop_reason": raw.get("generation", {}).get("stop_reason"),
                  "parse_state": raw.get("generation", {}).get("parse_state"),
                  "raw_completion_truncated": raw.get("generation", {}).get("raw_completion_truncated"),
                  "split_state": raw.get("generation", {}).get("split_state"),
                  "final_complete": raw.get("generation", {}).get("final_complete"),
                  "elapsed_seconds": raw.get("timing", {}).get("generation_seconds"),
                  "generated_tokens": raw.get("tokens", {}).get("generated"),
                  "reasoning_tokens": raw.get("tokens", {}).get("reasoning"),
                  "final_tokens": raw.get("tokens", {}).get("final")}
        details.append(detail)
    arms = sorted(set(record["arm"] for record in details))
    summaries = {}
    for arm in arms:
        subset = [record for record in details if record["arm"] == arm]
        wins = [record["task_id"] for record in subset if record["correct"] and not record["baseline_correct"]]
        losses = [record["task_id"] for record in subset if not record["correct"] and record["baseline_correct"]]
        summary = _summarize(subset)
        summary.update({"paired_wins": wins, "paired_losses": losses,
                        "net_additional_correct": len(wins) - len(losses),
                        "baseline_correct_retained": sum(record["correct"] and record["baseline_correct"] for record in subset)})
        if cohort is not None:
            summary["strata"] = {stratum: _summarize([record for record in subset if record["task_id"] in ids])
                                 for stratum, ids in cohort["strata"].items()}
        else:
            summary["groups"] = {group: _summarize([record for record in subset if record["group"] == group])
                                 for group in ("optimization-train", "selection-dev")}
        summaries[arm] = summary
    return {"format": "irisx/arc-budget-score", "format_version": "1.0", "trial_id": TRIAL_ID,
            "run_id": run["run_id"], "result_digest": result_digest, "outbound_digest": outbound_digest,
            "baseline_result_digest": digest_path(baseline_result), "baseline_score_digest": digest_path(baseline_score),
            "arms": summaries, "records": details, "holdout_scored": False}


def choose_validation_arm(score: Mapping[str, Any]) -> dict[str, Any]:
    if score.get("run_id") != DIAGNOSTIC_RUN or set(score.get("arms", {})) != set(ARMS):
        raise ValidationError("validation gate requires complete diagnostic score")
    qualified = [arm for arm, summary in score["arms"].items()
                 if summary["net_additional_correct"] >= 4 and summary["baseline_correct_retained"] >= 16]
    ordered = sorted(qualified, key=lambda arm: (-score["arms"][arm]["correct"],
                                               score["arms"][arm]["elapsed_p95_seconds"] if score["arms"][arm]["elapsed_p95_seconds"] is not None else float("inf"),
                                               ARMS[arm][1], ARMS[arm][0], arm))
    return {"qualified_arms": ordered, "selected_arm": ordered[0] if ordered else None,
            "rule": "net correct >=4 and retained B1 correct >=16; rank correct, p95 elapsed, token cap, thinking off"}

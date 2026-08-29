#!/usr/bin/env python3
"""Run the H-O1a structured instrumentation completeness experiment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_snapshot_assertion import SourceSnapshotAssertionError  # noqa: E402
from tools.source_snapshot_assertion import assert_registered_source_snapshot  # noqa: E402


EXPERIMENT_ID = "exp-2026-08-30-docops-profile-instrumentation"
DISTRIBUTION_ID = "taskdist-2026-08-28-vanta-docops-readonly-12"
PROFILE_CONTRACT_ID = "profile-contract-2026-08-30-docops-runtime-v1"
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = EXPERIMENT_ROOT / "runs"
BASELINE_RUNNER_PATH = (
    ROOT / "experiments" / "exp-2026-08-28-docops-readonly-baseline" / "scripts" / "run_baseline.py"
)
ARMS = ("instrumentation-off-v0", "instrumentation-on-v0")


class DefinitionError(ValueError):
    """Raised when a frozen experiment definition or boundary is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_within(path: Path, boundary: Path) -> bool:
    resolved = path.resolve()
    root = boundary.resolve()
    return resolved == root or root in resolved.parents


def resolve_repo_path(value: str, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise DefinitionError(f"{label} must be a non-empty repository-relative path")
    path = (ROOT / value).resolve()
    if not is_within(path, ROOT):
        raise DefinitionError(f"{label} escapes repository: {value}")
    return path


def relative_posix(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def load_baseline_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("phase3_docops_baseline_runner", BASELINE_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Phase 3 baseline runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_profile_contract(document: Any) -> list[str]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise DefinitionError("profile contract schema_version must be 1")
    if document.get("experiment_id") != EXPERIMENT_ID or document.get("profile_contract_id") != PROFILE_CONTRACT_ID:
        raise DefinitionError("profile contract identity mismatch")
    if document.get("frozen_before_execution") is not True:
        raise DefinitionError("profile contract must be frozen before execution")
    required = document.get("required_fields")
    if not isinstance(required, list) or len(required) != 17 or len(set(required)) != len(required):
        raise DefinitionError("profile contract must contain 17 unique required fields")
    if not all(isinstance(field, str) and field for field in required):
        raise DefinitionError("profile required fields must be non-empty strings")
    expected_events = [
        "episode_started",
        "invocation_started",
        "invocation_finished",
        "evaluation_finished",
        "episode_finished",
    ]
    if document.get("instrumentation_events") != expected_events:
        raise DefinitionError("profile instrumentation event contract mismatch")
    return required


def nested_present(value: Any, dotted_path: str) -> bool:
    current = value
    for component in dotted_path.split("."):
        if not isinstance(current, dict) or component not in current:
            return False
        current = current[component]
    return True


def profile_coverage(profile: dict[str, Any] | None, required_fields: list[str]) -> tuple[int, list[str]]:
    missing = [field for field in required_fields if profile is None or not nested_present(profile, field)]
    return len(required_fields) - len(missing), missing


def build_profile(
    *,
    episode_id: str,
    task_id: str,
    repetition: int,
    arm: str,
    invocation_wall_ms: float,
    invocation_cpu_ms: float,
    evaluation_wall_ms: float,
    resources: dict[str, Any],
    terminal_status: str,
    event_names: list[str],
    profiler_error: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "profile_contract_id": PROFILE_CONTRACT_ID,
        "episode_id": episode_id,
        "task_id": task_id,
        "repetition": repetition,
        "arm": arm,
        "stages": {
            "invocation": {
                "stage_id": "structured-control-invocation",
                "wall_ms": invocation_wall_ms,
                "process_cpu_ms": invocation_cpu_ms,
            },
            "evaluation": {
                "stage_id": "task-contract-evaluation",
                "wall_ms": evaluation_wall_ms,
            },
        },
        "io": {
            "read_operation_count": resources["tool_read_count"],
            "bytes_read": resources["bytes_read"],
        },
        "output": {"serialized_output_bytes": resources["output_bytes"]},
        "terminal": {"status": terminal_status},
        "instrumentation": {"event_count": len(event_names), "events": event_names},
        "profiler": {"error": profiler_error},
    }


def execute_episode(
    baseline: ModuleType,
    *,
    run_id: str,
    row: dict[str, Any],
    config: dict[str, Any],
    repetition: int,
    arm: str,
    required_fields: list[str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if arm not in ARMS:
        raise DefinitionError(f"unsupported arm: {arm}")
    fixture = baseline.resolve_repo_path(row["fixture_path"], f"{row['task_id']}.fixture_path")
    task = baseline.load_json(fixture / "task.json")
    expected = baseline.load_json((fixture / row["expected_path"]).resolve())
    inputs = baseline.declared_inputs(fixture, task)
    snapshot_before = baseline.input_snapshot(inputs)
    episode_id = f"{row['task_id']}::{repetition}::{arm}"
    event_names: list[str] = []
    total_wall_start = time.perf_counter_ns()
    total_cpu_start = time.process_time_ns()
    if arm == "instrumentation-on-v0":
        event_names.extend(["episode_started", "invocation_started"])
    invocation_wall_start = time.perf_counter_ns()
    invocation_cpu_start = time.process_time_ns()
    episode_status = "valid"
    terminal_error: dict[str, str] | None = None
    profiler_error: str | None = None
    try:
        produced, resources = baseline.invoke_control(config, row, task, fixture)
    except Exception as exc:  # preserve unexpected harness failures
        produced = {
            "task_id": row["task_id"],
            "configuration_id": config["id"],
            "claimed_outcome": "failure",
            "observation": None,
            "evidence": [],
            "handler": "harness-exception",
            "refusal_reason": "harness exception",
            "execution_path": {"retry_count": 0, "repair_count": 0, "escalation_count": 0, "recovery_count": 0},
        }
        resources = {
            "bytes_read": 0,
            "tool_read_count": 0,
            "output_bytes": len(canonical_json_bytes(produced)),
            "model_calls": 0,
            "model_api_cost_usd": 0.0,
        }
        episode_status = "invalid"
        terminal_error = {"type": type(exc).__name__, "message": str(exc)}
    invocation_cpu_ms = (time.process_time_ns() - invocation_cpu_start) / 1_000_000
    invocation_wall_ms = (time.perf_counter_ns() - invocation_wall_start) / 1_000_000
    if arm == "instrumentation-on-v0":
        event_names.append("invocation_finished")
    evaluation_start = time.perf_counter_ns()
    snapshot_after = baseline.input_snapshot(inputs)
    actual_outcome, evidence_status, joint_status, outcome_reasons = baseline.evaluate_episode(
        produced, expected, snapshot_before, snapshot_after
    )
    evaluation_wall_ms = (time.perf_counter_ns() - evaluation_start) / 1_000_000
    if arm == "instrumentation-on-v0":
        event_names.extend(["evaluation_finished", "episode_finished"])
    if snapshot_before != snapshot_after:
        episode_status = "invalid"
        terminal_error = {"type": "SourceMutation", "message": "selected fixture input changed"}
    terminal_status = episode_status
    profile: dict[str, Any] | None = None
    if arm == "instrumentation-on-v0":
        try:
            profile = build_profile(
                episode_id=episode_id,
                task_id=row["task_id"],
                repetition=repetition,
                arm=arm,
                invocation_wall_ms=invocation_wall_ms,
                invocation_cpu_ms=invocation_cpu_ms,
                evaluation_wall_ms=evaluation_wall_ms,
                resources=resources,
                terminal_status=terminal_status,
                event_names=event_names,
                profiler_error=None,
            )
        except Exception as exc:
            profiler_error = f"{type(exc).__name__}: {exc}"
            episode_status = "invalid"
            terminal_status = "invalid"
            terminal_error = {"type": "ProfilerError", "message": profiler_error}
            profile = build_profile(
                episode_id=episode_id,
                task_id=row["task_id"],
                repetition=repetition,
                arm=arm,
                invocation_wall_ms=invocation_wall_ms,
                invocation_cpu_ms=invocation_cpu_ms,
                evaluation_wall_ms=evaluation_wall_ms,
                resources=resources,
                terminal_status=terminal_status,
                event_names=event_names,
                profiler_error=profiler_error,
            )
    present_count, missing_fields = profile_coverage(profile, required_fields)
    profile_bytes = len(canonical_json_bytes(profile)) if profile is not None else 0
    total_cpu_ms = (time.process_time_ns() - total_cpu_start) / 1_000_000
    total_wall_ms = (time.perf_counter_ns() - total_wall_start) / 1_000_000
    record = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "episode_id": episode_id,
        "task_id": row["task_id"],
        "task_order": row["task_order"],
        "stratum": row["stratum"],
        "output_kind": row["output_kind"],
        "configuration_id": config["id"],
        "arm": arm,
        "repetition": repetition,
        "produced": produced,
        "produced_sha256": sha256_bytes(canonical_json_bytes(produced)),
        "expected": expected,
        "actual_outcome": actual_outcome,
        "claimed_outcome": produced["claimed_outcome"],
        "evidence_status": evidence_status,
        "joint_status": joint_status,
        "outcome_reasons": outcome_reasons,
        "terminal_status": terminal_status,
        "episode_status": episode_status,
        "input_snapshot_before": snapshot_before,
        "input_snapshot_after": snapshot_after,
        "profile": profile,
        "profile_coverage": {
            "declared_field_count": len(required_fields),
            "present_field_count": present_count,
            "missing_required_fields": missing_fields,
        },
        "resources": {
            **resources,
            "invocation_wall_ms": invocation_wall_ms,
            "invocation_process_cpu_ms": invocation_cpu_ms,
            "evaluation_wall_ms": evaluation_wall_ms,
            "episode_total_wall_ms": total_wall_ms,
            "episode_total_process_cpu_ms": total_cpu_ms,
            "instrumentation_profile_bytes": profile_bytes,
            "instrumentation_event_count": len(event_names),
        },
        "profiler_error": profiler_error,
        "terminal_error": terminal_error,
    }
    record["resources"]["terminal_record_bytes_excluding_self"] = len(canonical_json_bytes(record))
    return record, profile


def aggregate(
    records: list[dict[str, Any]],
    task_count: int,
    repetitions: int,
    required_fields: list[str],
    profiles_artifact_bytes: int,
) -> dict[str, Any]:
    by_arm: dict[str, Any] = {}
    for arm in ARMS:
        subset = [record for record in records if record["arm"] == arm]
        valid = [record for record in subset if record["episode_status"] == "valid"]
        present = sum(record["profile_coverage"]["present_field_count"] for record in valid)
        declared_instances = len(valid) * len(required_fields)
        by_arm[arm] = {
            "attempted_episodes": len(subset),
            "valid_episodes": len(valid),
            "invalid_episodes": len(subset) - len(valid),
            "outcome_counts": {
                name: sum(record["actual_outcome"] == name for record in valid)
                for name in ("success", "partial", "failure")
            },
            "profile_field_coverage": {
                "declared_field_count": len(required_fields),
                "present_field_instances": present,
                "missing_required_field_instances": declared_instances - present,
                "coverage_rate": present / declared_instances if declared_instances else None,
                "episodes_with_complete_profile": sum(
                    not record["profile_coverage"]["missing_required_fields"] for record in valid
                ),
            },
            "profiler_error_count": sum(record["profiler_error"] is not None for record in subset),
            "resource_totals": {
                "producer_output_bytes": sum(record["resources"]["output_bytes"] for record in valid),
                "instrumentation_profile_bytes": sum(
                    record["resources"]["instrumentation_profile_bytes"] for record in valid
                ),
                "terminal_record_bytes_excluding_self": sum(
                    record["resources"]["terminal_record_bytes_excluding_self"] for record in valid
                ),
                "episode_total_wall_ms": sum(record["resources"]["episode_total_wall_ms"] for record in valid),
                "episode_total_process_cpu_ms": sum(
                    record["resources"]["episode_total_process_cpu_ms"] for record in valid
                ),
                "invocation_wall_ms": sum(record["resources"]["invocation_wall_ms"] for record in valid),
                "evaluation_wall_ms": sum(record["resources"]["evaluation_wall_ms"] for record in valid),
                "read_operation_count": sum(record["resources"]["tool_read_count"] for record in valid),
                "bytes_read": sum(record["resources"]["bytes_read"] for record in valid),
            },
        }
    paired_mismatches: list[dict[str, Any]] = []
    wall_deltas: list[float] = []
    cpu_deltas: list[float] = []
    for repetition in range(1, repetitions + 1):
        task_ids = sorted({record["task_id"] for record in records})
        for task_id in task_ids:
            pair = [record for record in records if record["task_id"] == task_id and record["repetition"] == repetition]
            if len(pair) != 2:
                paired_mismatches.append({"task_id": task_id, "repetition": repetition, "reason": "pair_count"})
                continue
            off = next(record for record in pair if record["arm"] == "instrumentation-off-v0")
            on = next(record for record in pair if record["arm"] == "instrumentation-on-v0")
            differing = [
                field
                for field in ("produced_sha256", "actual_outcome", "terminal_status", "evidence_status", "input_snapshot_after")
                if off[field] != on[field]
            ]
            if differing:
                paired_mismatches.append(
                    {"task_id": task_id, "repetition": repetition, "reason": "fixed_behavior", "fields": differing}
                )
            wall_deltas.append(on["resources"]["episode_total_wall_ms"] - off["resources"]["episode_total_wall_ms"])
            cpu_deltas.append(
                on["resources"]["episode_total_process_cpu_ms"]
                - off["resources"]["episode_total_process_cpu_ms"]
            )
    repeat_disagreements: list[dict[str, str]] = []
    for arm in ARMS:
        for task_id in sorted({record["task_id"] for record in records}):
            subset = [record for record in records if record["arm"] == arm and record["task_id"] == task_id]
            signatures = {(record["produced_sha256"], record["actual_outcome"], record["terminal_status"]) for record in subset}
            if len(subset) != repetitions or len(signatures) != 1:
                repeat_disagreements.append({"arm": arm, "task_id": task_id})
    positive = sum(delta > 0 for delta in wall_deltas)
    negative = sum(delta < 0 for delta in wall_deltas)
    direction = "mixed" if positive and negative else ("positive" if positive else ("negative" if negative else "zero"))
    timing_status = (
        "Timing overhead magnitude/direction: Not established under this horizon."
        if direction == "mixed"
        else "Observed direction is descriptive only; stable timing overhead is Not established."
    )
    complete = len(records) == task_count * repetitions * len(ARMS) and not any(
        record["episode_status"] == "invalid" for record in records
    )
    support_checks = {
        "instrumentation_improves_frozen_profile_coverage": by_arm["instrumentation-on-v0"][
            "profile_field_coverage"
        ]["coverage_rate"]
        > by_arm["instrumentation-off-v0"]["profile_field_coverage"]["coverage_rate"],
        "paired_outputs_unchanged": not any(
            mismatch.get("fields") and "produced_sha256" in mismatch["fields"] for mismatch in paired_mismatches
        ),
        "paired_actual_outcomes_unchanged": not any(
            mismatch.get("fields") and "actual_outcome" in mismatch["fields"] for mismatch in paired_mismatches
        ),
        "paired_terminal_status_unchanged": not any(
            mismatch.get("fields") and "terminal_status" in mismatch["fields"] for mismatch in paired_mismatches
        ),
        "no_new_invalid_episodes": by_arm["instrumentation-on-v0"]["invalid_episodes"] == 0,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "expected_episode_count": task_count * repetitions * len(ARMS),
        "complete_episode_count": len(records),
        "run_status": "complete" if complete and not paired_mismatches else "invalid",
        "declared_profile_fields": required_fields,
        "arms": by_arm,
        "paired_invariance": {"all_pairs_invariant": not paired_mismatches, "mismatches": paired_mismatches},
        "repeat_agreement": {
            "all_arm_task_pairs_agree": not repeat_disagreements,
            "disagreements": repeat_disagreements,
        },
        "timing_deltas_on_minus_off_ms": {
            "wall": {
                "count": len(wall_deltas),
                "positive_count": positive,
                "negative_count": negative,
                "zero_count": len(wall_deltas) - positive - negative,
                "mean": statistics.fmean(wall_deltas),
                "median": statistics.median(wall_deltas),
                "minimum": min(wall_deltas),
                "maximum": max(wall_deltas),
                "direction": direction,
            },
            "process_cpu": {
                "mean": statistics.fmean(cpu_deltas),
                "median": statistics.median(cpu_deltas),
                "minimum": min(cpu_deltas),
                "maximum": max(cpu_deltas),
            },
            "interpretation": timing_status,
        },
        "profiles_artifact_bytes": profiles_artifact_bytes,
        "support_checks": support_checks,
        "support_status": "Supported — task-local" if complete and not paired_mismatches and all(support_checks.values()) else "Not established",
        "interpretation_boundary": "profile completeness and paired deterministic behavior only; stable performance overhead not established",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--configurations", required=True)
    parser.add_argument("--profile-contract", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    manifest_path = resolve_repo_path(args.manifest, "--manifest")
    configurations_path = resolve_repo_path(args.configurations, "--configurations")
    profile_contract_path = resolve_repo_path(args.profile_contract, "--profile-contract")
    registry_path = resolve_repo_path(args.registry, "--registry")
    manifest = load_json(manifest_path)
    configurations = load_json(configurations_path)
    profile_contract = load_json(profile_contract_path)
    required_fields = validate_profile_contract(profile_contract)
    baseline = load_baseline_runner()
    tasks, configs = baseline.validate_definitions(manifest, configurations)
    structured = next((config for config in configs if config["id"] == "structured-readonly-v0"), None)
    if structured is None:
        raise DefinitionError("structured-readonly-v0 configuration is unavailable")
    task_rows = [{**row, "task_order": index} for index, row in enumerate(tasks, start=1)]
    repetitions = 3
    code_commit = git_output("rev-parse", "HEAD")
    try:
        source_identity = assert_registered_source_snapshot(
            ROOT,
            registry_path,
            manifest["source_id"],
            manifest["source_snapshot_id"],
            code_commit,
        )
    except SourceSnapshotAssertionError as exc:
        raise DefinitionError(f"source snapshot assertion failed [{exc.code}]: {exc}") from exc
    if args.validate_only:
        print(
            f"definition validation: PASS (12 tasks, 2 arms, 3 repetitions, 17 profile fields, source tree {source_identity.observed_tree_oid})"
        )
        return 0
    if not args.output_dir or not args.run_id:
        parser.error("--output-dir and --run-id are required unless --validate-only is used")
    output_dir = resolve_repo_path(args.output_dir, "--output-dir")
    if not is_within(output_dir, RUNS_ROOT):
        raise DefinitionError("--output-dir must be under this experiment's runs directory")
    if output_dir.exists():
        raise DefinitionError(f"output directory already exists: {relative_posix(output_dir)}")

    started_at = utc_now()
    git_status_before = git_output("status", "--short")
    source_status_before = git_output("status", "--short", "--", "sources", "references/papers")
    registry_sha_before = sha256_file(registry_path)
    output_dir.mkdir(parents=True)
    terminal_path = output_dir / "raw" / "terminal-records.jsonl"
    profiles_path = output_dir / "raw" / "profiles.jsonl"
    terminal_path.parent.mkdir()
    records: list[dict[str, Any]] = []
    with terminal_path.open("w", encoding="utf-8", newline="\n") as terminal_stream, profiles_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as profile_stream:
        for repetition in range(1, repetitions + 1):
            for row in task_rows:
                for arm in ARMS:
                    record, profile = execute_episode(
                        baseline,
                        run_id=args.run_id,
                        row=row,
                        config=structured,
                        repetition=repetition,
                        arm=arm,
                        required_fields=required_fields,
                    )
                    records.append(record)
                    terminal_stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                    terminal_stream.flush()
                    if profile is not None:
                        profile_stream.write(json.dumps(profile, ensure_ascii=False, sort_keys=True) + "\n")
                        profile_stream.flush()

    results = aggregate(records, len(task_rows), repetitions, required_fields, profiles_path.stat().st_size)
    results["run_id"] = args.run_id
    results["terminal_artifact_bytes"] = terminal_path.stat().st_size
    source_status_after = git_output("status", "--short", "--", "sources", "references/papers")
    registry_sha_after = sha256_file(registry_path)
    if source_status_before != source_status_after or source_status_after or registry_sha_before != registry_sha_after:
        results["run_status"] = "invalid"
        results["support_status"] = "Not established"
        results["source_preservation_failure"] = True
    else:
        results["source_preservation_failure"] = False
    manifest_output = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": args.run_id,
        "status": results["run_status"],
        "started_at": started_at,
        "finished_at": utc_now(),
        "command": [sys.executable, *sys.argv],
        "working_directory": str(ROOT),
        "git_commit": code_commit,
        "git_status_before": git_status_before.splitlines(),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "os_name": os.name,
        "distribution_id": manifest["distribution_id"],
        "contract_id": manifest["contract_id"],
        "task_manifest_path": relative_posix(manifest_path),
        "task_manifest_sha256": sha256_file(manifest_path),
        "configurations_path": relative_posix(configurations_path),
        "configurations_sha256": sha256_file(configurations_path),
        "control_configuration_id": structured["id"],
        "control_implementation_path": relative_posix(BASELINE_RUNNER_PATH),
        "control_implementation_sha256": sha256_file(BASELINE_RUNNER_PATH),
        "profile_contract_path": relative_posix(profile_contract_path),
        "profile_contract_sha256": sha256_file(profile_contract_path),
        "profile_contract_frozen_before_execution": True,
        "declared_profile_field_count": len(required_fields),
        "registry_path": relative_posix(registry_path),
        "registry_sha256_before": registry_sha_before,
        "registry_sha256_after": registry_sha_after,
        "source_id": source_identity.source_id,
        "source_snapshot_id": source_identity.snapshot_id,
        "source_registered_path": source_identity.source_path,
        "source_registered_tree_oid": source_identity.registered_tree_oid,
        "source_tree_oid_at_code_commit": source_identity.observed_tree_oid,
        "source_snapshot_assertion": "passed",
        "source_status_before": source_status_before.splitlines(),
        "source_status_after": source_status_after.splitlines(),
        "arms": list(ARMS),
        "task_count": len(task_rows),
        "repetitions": repetitions,
        "expected_episode_count": len(task_rows) * repetitions * len(ARMS),
        "network_access": False,
        "model_calls": 0,
        "token_usage": 0,
        "paid_cost_usd": 0.0,
        "credentials_used": False,
        "retries": 0,
        "recoveries": 0,
        "verifier_gating": False,
        "routing": False,
        "cache_policy_change": False,
        "optimization": False,
    }
    write_json(output_dir / "run-manifest.json", manifest_output)
    write_json(output_dir / "results.json", results)
    if results["run_status"] != "complete":
        write_json(
            output_dir / "failure.json",
            {
                "run_id": args.run_id,
                "status": "invalid",
                "reason": "incomplete/invalid episodes, paired-invariance failure, or source-preservation failure",
                "completed_artifacts_must_not_be_cited": True,
            },
        )
    print(
        f"H-O1a run: {results['run_status'].upper()} "
        f"({len(records)}/{results['expected_episode_count']} episodes, support={results['support_status']})"
    )
    return 0 if results["run_status"] == "complete" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DefinitionError, OSError, RuntimeError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"H-O1a run: FAIL ({exc})", file=sys.stderr)
        raise SystemExit(1)

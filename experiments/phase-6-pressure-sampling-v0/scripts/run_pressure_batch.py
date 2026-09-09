#!/usr/bin/env python3
"""Run the six frozen tasks sequentially into external staging, once each."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_SCRIPTS = REPOSITORY_ROOT / "experiments/substrates/model-execution-qualification-v0/scripts"
for candidate in (MODEL_SCRIPTS, SCRIPT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import check_admission  # noqa: E402
import pressure_tasks as tasks  # noqa: E402
import run_qualification as qualified  # noqa: E402
import validate_definitions  # noqa: E402


PROFILE_PATH = REPOSITORY_ROOT / "experiments/substrates/model-execution-qualification-v0/admission/codex-cli-0.147.0-run-03-profile.json"
ALLOWED_POST_FREEZE_PATHS = {
    "experiments/phase-6-pressure-sampling-v0/runs/batch-3/admission-record.json",
    "experiments/phase-6-pressure-sampling-v0/runs/batch-3/launch-manifest.json",
}
EXPECTED_BATCH_ID = "phase-6-batch-3-sampling-path-requalification-v0"


class BatchRunError(RuntimeError):
    """A launch identity, systemic, or safety boundary failed closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPOSITORY_ROOT, check=True, text=True,
        encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    write_new(path, tasks.pretty_json_bytes(dict(value)))


def _extended_audit(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    audit = dict(qualified.audit_provider_events(events))
    encoded = [json.dumps(event, ensure_ascii=False, sort_keys=True).lower() for event in events]
    audit["escalation_event_count"] = sum("escalat" in row for row in encoded)
    audit["recovery_event_count"] = sum("recovery" in row for row in encoded)
    return audit


def observed_provider_acceptance(
    events: list[Mapping[str, Any]], *, final_message: str | None
) -> bool | str:
    """Return only what the provider event stream directly establishes."""
    if final_message is not None:
        return True
    for event in events:
        if event.get("type") not in {"error", "turn.failed"}:
            continue
        encoded = json.dumps(event, ensure_ascii=False, sort_keys=True).lower()
        if "invalid_request_error" in encoded or "invalid_json_schema" in encoded:
            return False
    return "Unknown"


def require_launch_state(manifest: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    if git("status", "--porcelain"):
        raise BatchRunError("launch requires a clean tree")
    launch_ready_sha = git("rev-parse", "HEAD")
    if manifest.get("batch_id") != EXPECTED_BATCH_ID:
        raise BatchRunError("Batch 3 launch manifest identity mismatch")
    freeze_sha = manifest["definition_code_freeze_sha"]
    git("merge-base", "--is-ancestor", freeze_sha, launch_ready_sha)
    changed = set(filter(None, git("diff", "--name-only", f"{freeze_sha}..{launch_ready_sha}").splitlines()))
    if changed != ALLOWED_POST_FREEZE_PATHS:
        raise BatchRunError(f"unexpected post-freeze paths: {sorted(changed)}")
    validate_definitions.validate()
    admission_path = REPOSITORY_ROOT / manifest["admission"]["record_path"]
    admission = tasks.load_object(admission_path)
    if tasks.sha256_bytes(admission_path.read_bytes()) != manifest["admission"]["record_sha256"]:
        raise BatchRunError("admission record hash mismatch")
    if admission.get("status") != "admitted":
        raise BatchRunError("admission record is not admitted")
    if admission.get("compatibility_profile_id") != "codex-cli-0.147.0-run-03-admission-v0":
        raise BatchRunError("admission profile identity mismatch")
    sample_path = REPOSITORY_ROOT / manifest["definition_bindings"]["sample_manifest_path"]
    if tasks.sha256_bytes(sample_path.read_bytes()) != manifest["definition_bindings"]["sample_manifest_sha256"]:
        raise BatchRunError("sample manifest hash mismatch")
    return launch_ready_sha, admission


def execute_task(
    task: tasks.FrozenPressureTask,
    *,
    staging_root: Path,
    manifest: Mapping[str, Any],
    admission: Mapping[str, Any],
    launch_ready_sha: str,
) -> tuple[dict[str, Any], bool]:
    task_root = staging_root / task.key
    task_root.mkdir(parents=False, exist_ok=False)
    started_at = utc_now()
    attempt_start = {
        "schema_version": 1,
        "task_key": task.key,
        "task_id": task.contract["task_id"],
        "contract_id": task.contract["contract_id"],
        "program_id": task.contract["program_id"],
        "definition_code_freeze_sha": manifest["definition_code_freeze_sha"],
        "launch_ready_sha": launch_ready_sha,
        "admission_record_sha256": manifest["admission"]["record_sha256"],
        "admission_status": "admitted",
        "started_at": started_at,
        "provider_attempt": 1,
        "model_call_ceiling": 1,
        "retry_count": 0,
        "route_count": 0,
        "fallback_count": 0,
        "escalation_count": 0,
        "recovery_count": 0,
        "tool_call_count": 0,
        "api_key_environment_removed_from_child": True,
    }
    provider_events = task_root / "provider-events.jsonl"
    provider_stderr = task_root / "provider-stderr.txt"
    raw_output = task_root / "raw-output.txt"
    model_call_crossed = False
    return_code: int | str = "not_started"
    timed_out = False
    start_ns = time.perf_counter_ns()
    with tempfile.TemporaryDirectory(prefix=f"irisx-p6b2-{task.key}-", dir=staging_root) as temporary:
        workspace = Path(temporary)
        schema_copy = workspace / "output-schema.json"
        schema_copy.write_bytes((task.root / "output-schema.json").read_bytes())
        catalog_copy = workspace / "model-catalog.json"
        catalog_copy.write_bytes(qualified.MODEL_CATALOG_PATH.read_bytes())
        command = qualified.build_provider_command(
            str(admission["observed_cli_path"]), workspace, schema_copy, catalog_copy, raw_output
        )
        profile = check_admission.load_object(PROFILE_PATH)
        if check_admission.normalize_command(command) != profile["canonical_argv"]:
            raise BatchRunError("provider command differs from admitted profile")
        attempt_start["command"] = command
        write_json(task_root / "attempt-start.json", attempt_start)
        try:
            with provider_events.open("xb") as stdout_stream, provider_stderr.open("xb") as stderr_stream:
                model_call_crossed = True
                completed = subprocess.run(
                    command,
                    input=task.prompt.encode("utf-8"),
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    cwd=REPOSITORY_ROOT,
                    env=qualified.codex_environment(),
                    timeout=600,
                    check=False,
                )
                return_code = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            return_code = "timeout"
        except Exception as exc:
            return_code = "process_start_failure"
            if not provider_stderr.exists():
                write_new(provider_stderr, b"")
            with provider_stderr.open("ab") as stream:
                stream.write(f"\n{type(exc).__name__}: {exc}\n".encode("utf-8", errors="replace"))
    wall_time_ns = time.perf_counter_ns() - start_ns
    event_bytes = provider_events.read_bytes() if provider_events.exists() else b""
    stderr_bytes = provider_stderr.read_bytes() if provider_stderr.exists() else b""
    output_bytes = raw_output.read_bytes() if raw_output.exists() else None
    events, parse_errors = qualified.parse_provider_events(event_bytes)
    audit = _extended_audit(events)
    event_message = qualified.final_agent_message(events)
    file_message = output_bytes.decode("utf-8", errors="replace") if output_bytes is not None else None
    provider_acceptance = observed_provider_acceptance(events, final_message=event_message)
    forbidden = {
        "tool_calls": audit["tool_attempt_count"],
        "retries": audit["retry_event_count"],
        "routes": audit["route_event_count"],
        "fallbacks": audit["fallback_event_count"],
        "escalations": audit["escalation_event_count"],
        "recovery_actions": audit["recovery_event_count"],
    }
    systemic_reasons = []
    if return_code != 0:
        systemic_reasons.append("provider_process_failed")
    if timed_out:
        systemic_reasons.append("provider_process_timed_out")
    if output_bytes is None:
        systemic_reasons.append("provider_output_missing")
    if parse_errors:
        systemic_reasons.append("provider_event_stream_malformed")
    if event_message is None:
        systemic_reasons.append("provider_final_message_missing")
    if event_message is not None and file_message is not None and event_message.strip() != file_message.strip():
        systemic_reasons.append("raw_output_event_mismatch")
    systemic_reasons.extend(f"prohibited_{name}_observed" for name, count in forbidden.items() if count)
    verification = (
        {"semantic_valid": False, "status": "not_assessed", "reasons": systemic_reasons}
        if systemic_reasons
        else tasks.verify_raw_output(task, file_message)
    )
    write_json(task_root / "verification-record.json", {
        "schema_version": 1,
        "task_id": task.contract["task_id"],
        "deterministic_oracle_id": task.contract["deterministic_oracle_id"],
        "verifier_integrity_valid": True,
        **verification,
    })
    semantic_miss = not systemic_reasons and not verification["semantic_valid"]
    usable_result_observed = bool(file_message and file_message.strip()) and not systemic_reasons
    attribution = (
        {
            "failure_stage": "systemic_execution_failure",
            "task_level_pressure_observed": "Not established",
            "model_intrinsic_capability_failure": "Not established",
            "retry_benefit": "Not established",
        }
        if systemic_reasons
        else {
            "failure_stage": "execution_producer" if semantic_miss else "not_applicable",
            "task_level_pressure_observed": semantic_miss,
            "shortfall_axis": "task_success" if semantic_miss else "not_applicable",
            "failure_locus": "execution_producer" if semantic_miss else "not_applicable",
            "frozen_configuration_shortfall": "directly_supported" if semantic_miss else "not_observed",
            "model_intrinsic_capability_failure": "Not established",
            "retry_benefit": "Not established",
            "stronger_allocation_benefit": "Not established",
            "routing_benefit": "Not established",
        }
    )
    terminal = {
        "schema_version": 1,
        "task_key": task.key,
        "task_id": task.contract["task_id"],
        "terminal_status": "systemic_failure" if systemic_reasons else verification["status"],
        "verified_success": verification["semantic_valid"] and not systemic_reasons,
        "semantic_miss": semantic_miss,
        "systemic_failure_reasons": systemic_reasons,
        "identity_binding_valid": True,
        "evidence_binding_sufficient": True,
        "usable_model_result": bool(file_message and file_message.strip()) and not systemic_reasons,
        "provider_acceptance": provider_acceptance,
        "usable_result_observed": usable_result_observed,
        "model_inference_execution": "Unknown",
        "model_call_boundary_crossed": model_call_crossed,
        "verification": {
            "verifier_integrity_valid": True,
            "deterministic_oracle_id": task.contract["deterministic_oracle_id"],
            "semantic_valid": verification["semantic_valid"],
        },
        "attribution": attribution,
        "completed_at": utc_now(),
    }
    write_json(task_root / "terminal-record.json", terminal)
    resources = {
        "schema_version": 2,
        "task_id": task.contract["task_id"],
        "invocation_boundary_crossed": model_call_crossed,
        "model_call_boundaries": 1 if model_call_crossed else 0,
        "provider_acceptance": provider_acceptance,
        "usable_result_observed": usable_result_observed,
        "model_inference_execution": "Unknown",
        "network_calls": "Unknown",
        "transport_request_count": "Unknown",
        "provider_cost_usd": "Unknown",
        "paid_api_calls": 0,
        "tool_calls": forbidden["tool_calls"],
        "retry_count": forbidden["retries"],
        "route_count": forbidden["routes"],
        "fallback_count": forbidden["fallbacks"],
        "escalation_count": forbidden["escalations"],
        "recovery_count": forbidden["recovery_actions"],
        "wall_time_ns": wall_time_ns,
        "token_usage": qualified.extract_usage(events),
        "provider_stderr_bytes": len(stderr_bytes),
    }
    write_json(task_root / "resource-record.json", resources)
    write_json(task_root / "predicate-source-map.json", {
        "schema_version": 1,
        "task_id": task.contract["task_id"],
        "authoritative_source": "terminal-record.json",
        "task_level_pressure_pointer": "/attribution/task_level_pressure_observed",
        "derivation_deferred_to_turn_b": True,
    })
    write_json(task_root / "run-manifest.json", {
        "schema_version": 1,
        "task_id": task.contract["task_id"],
        "definition_code_freeze_sha": manifest["definition_code_freeze_sha"],
        "launch_ready_sha": launch_ready_sha,
        "admission_record_sha256": manifest["admission"]["record_sha256"],
        "artifacts": [
            {"path": path.name, "bytes": len(path.read_bytes()), "sha256": tasks.sha256_bytes(path.read_bytes())}
            for path in sorted(task_root.iterdir()) if path.is_file() and path.name != "run-manifest.json"
        ],
    })
    return terminal, bool(systemic_reasons)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch-manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = tasks.load_object(args.launch_manifest)
        launch_ready_sha, admission = require_launch_state(manifest)
        staging_root = Path(manifest["external_staging"]["staging_root"])
        staging_root.mkdir(parents=True, exist_ok=True)
        if any(staging_root.iterdir()):
            allowed = {Path(manifest["external_staging"]["runner_stdout_path"]), Path(manifest["external_staging"]["runner_stderr_path"])}
            unexpected = [path for path in staging_root.iterdir() if path not in allowed]
            if unexpected:
                raise BatchRunError("external staging root is not empty")
        attempted = []
        stopped = False
        for task_key in manifest["task_order"]:
            terminal, systemic = execute_task(
                tasks.load_task(task_key), staging_root=staging_root, manifest=manifest,
                admission=admission, launch_ready_sha=launch_ready_sha,
            )
            attempted.append({"task_key": task_key, "terminal_status": terminal["terminal_status"]})
            if systemic:
                stopped = True
                break
        write_json(staging_root / "batch-completion.json", {
            "schema_version": 1,
            "batch_id": manifest["batch_id"],
            "definition_code_freeze_sha": manifest["definition_code_freeze_sha"],
            "launch_ready_sha": launch_ready_sha,
            "attempted": attempted,
            "stopped_on_systemic_or_safety_failure": stopped,
            "completed_at": utc_now(),
        })
        return 0 if not stopped else 2
    except Exception as exc:
        print(f"Phase 6 Batch 3 runner: FAIL ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run once or deterministically validate the frozen Phase 5 Batch 6 task family."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import check_admission as admission_checker  # noqa: E402
from model_adapter import TaskFamilyModelAdapter  # noqa: E402
from task_family import (  # noqa: E402
    PROFILE_ID,
    PROFILE_PATH,
    PROFILE_SHA256,
    TASK_FAMILY_ROOT,
    TASK_SPECS,
    bound_evidence,
    canonical_json_bytes,
    definition_record,
    load_object,
    load_task,
    pretty_json_bytes,
    sha256_bytes,
    verifier_for,
)

from irisx.core.execution import execute, terminal_record_to_dict  # noqa: E402
from irisx.core.records import UNKNOWN  # noqa: E402


FULL_SHA = re.compile(r"[0-9a-f]{40}")
SUMMARY_PATH = TASK_FAMILY_ROOT / "summaries" / "batch-6-summary.json"
FROZEN_PATHS = (
    "experiments/substrates/model-execution-qualification-v0/task-family/definitions",
    "experiments/substrates/model-execution-qualification-v0/task-family/inputs",
    "experiments/substrates/model-execution-qualification-v0/task-family/programs",
    "experiments/substrates/model-execution-qualification-v0/task-family/schemas",
    "experiments/substrates/model-execution-qualification-v0/task-family/fixtures",
    "experiments/substrates/model-execution-qualification-v0/scripts/task_family.py",
    "experiments/substrates/model-execution-qualification-v0/scripts/model_adapter.py",
    "experiments/substrates/model-execution-qualification-v0/scripts/run_task_family_case.py",
    "experiments/substrates/model-execution-qualification-v0/scripts/check_admission.py",
    "experiments/substrates/model-execution-qualification-v0/scripts/run_qualification.py",
    "experiments/substrates/model-execution-qualification-v0/tests/test_task_family.py",
    "experiments/substrates/model-execution-qualification-v0/tests/test_cross_task_isolation.py",
    "experiments/substrates/model-execution-qualification-v0/admission/codex-cli-0.147.0-run-03-profile.json",
    "experiments/substrates/model-execution-qualification-v0/definition/tool-free-luna-model-catalog.json",
    "experiments/configurations/provider-model-baseline-v0.json",
)


class TaskFamilyRunError(RuntimeError):
    """A live-run prerequisite or immutable evidence check failed closed."""


def git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise TaskFamilyRunError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip() or completed.stderr.strip()


def write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def repository_relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()


def artifact_record(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": repository_relative(path),
        "bytes": len(content),
        "sha256": sha256_bytes(content),
    }


def require_full_commit(value: str, label: str) -> None:
    if FULL_SHA.fullmatch(value) is None:
        raise TaskFamilyRunError(f"{label} must be a full lowercase Git SHA")
    git("cat-file", "-e", f"{value}^{{commit}}")


def require_frozen_launch_state(definition_code_freeze_sha: str, launch_head: str) -> None:
    require_full_commit(definition_code_freeze_sha, "definition_code_freeze_sha")
    require_full_commit(launch_head, "launch_head")
    head = git("rev-parse", "HEAD")
    if head != launch_head:
        raise TaskFamilyRunError("launch_head must equal current HEAD")
    if git("status", "--porcelain"):
        raise TaskFamilyRunError("live task requires a clean working tree")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", definition_code_freeze_sha, launch_head],
        cwd=REPOSITORY_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if ancestor.returncode != 0:
        raise TaskFamilyRunError("definition/code freeze is not an ancestor of launch HEAD")
    changed = git(
        "diff",
        "--name-only",
        definition_code_freeze_sha,
        launch_head,
        "--",
        *FROZEN_PATHS,
    )
    if changed:
        raise TaskFamilyRunError(f"executable task-family surface changed after freeze: {changed}")


def validate_admission_snapshot(path: Path, *, refresh_current: bool) -> dict[str, Any]:
    resolved = path.resolve()
    admission_root = (TASK_FAMILY_ROOT / "admission").resolve()
    if admission_root not in resolved.parents:
        raise TaskFamilyRunError("admission snapshot must be inside task-family/admission")
    relative = repository_relative(resolved)
    git("ls-files", "--error-unmatch", "--", relative)
    record = load_object(resolved)
    if record.get("status") != "admitted" or record.get("reasons") != []:
        raise TaskFamilyRunError("committed current admission snapshot is not admitted")
    if record.get("compatibility_profile_id") != PROFILE_ID:
        raise TaskFamilyRunError("admission snapshot profile ID mismatch")
    if record.get("compatibility_profile_sha256") != PROFILE_SHA256:
        raise TaskFamilyRunError("admission snapshot profile hash mismatch")
    if sha256_bytes(PROFILE_PATH.read_bytes()) != PROFILE_SHA256:
        raise TaskFamilyRunError("Batch 5 admission profile bytes drifted")
    if record.get("provider_attempts") != 0 or record.get("live_model_calls") != 0:
        raise TaskFamilyRunError("admission snapshot is not zero-call")
    if record.get("future_model_execution_authorized") is not False:
        raise TaskFamilyRunError("admission snapshot improperly claims execution authority")
    if refresh_current:
        current = admission_checker.current_environment()
        if current.get("status") != "admitted":
            raise TaskFamilyRunError(
                "current Batch 5 admission rejected: " + ",".join(current.get("reasons", []))
            )
        if canonical_json_bytes(current) != canonical_json_bytes(record):
            raise TaskFamilyRunError("current admission no longer matches committed snapshot")
    return record


def _tracked_run(run_dir: Path) -> bool:
    manifest = run_dir / "run-manifest.json"
    if not manifest.is_file():
        return False
    relative = repository_relative(manifest)
    completed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=REPOSITORY_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode == 0


def require_task_order(task_key: str) -> None:
    order = tuple(TASK_SPECS)
    index = order.index(task_key)
    for earlier in order[:index]:
        definition = load_task(earlier)
        if not _tracked_run(definition.run_dir):
            raise TaskFamilyRunError(f"Task {earlier} evidence must be validated and committed first")
        result = validate_run(earlier)
        if result["classification"] == "systemic_failure":
            raise TaskFamilyRunError(f"Task {earlier} systemic failure stops remaining live tasks")
    for later in order[index:]:
        definition = load_task(later)
        if definition.run_dir.exists():
            raise TaskFamilyRunError(f"immutable Task {later} run directory already exists")
    prior_calls = 0
    for earlier in order[:index]:
        resources = load_object(load_task(earlier).run_dir / "resource-record.json")
        prior_calls += resources["model_calls"]
    if prior_calls != index or prior_calls >= 3:
        raise TaskFamilyRunError("Batch 6 call ledger is inconsistent with ordered execution")


def execute_live_task(
    *,
    task_key: str,
    definition_code_freeze_sha: str,
    launch_head: str,
    admission_record_path: Path,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    key = task_key.upper()
    definition = load_task(key)
    require_frozen_launch_state(definition_code_freeze_sha, launch_head)
    require_task_order(key)
    admission_record = validate_admission_snapshot(admission_record_path, refresh_current=True)
    admission_hash = sha256_bytes(admission_record_path.read_bytes())
    adapter = TaskFamilyModelAdapter(
        definition=definition,
        admission_record=admission_record,
        admission_record_path=Path(repository_relative(admission_record_path)),
        admission_record_sha256=admission_hash,
        definition_code_freeze_sha=definition_code_freeze_sha,
        launch_head=launch_head,
        runner=runner,
    )
    terminal = execute(
        contract=definition.core_contract(),
        program=definition.program_artifact(),
        supplied_identity=definition.execution_identity(),
        request=definition.execution_request(),
        state=definition.initial_state(),
        executor=adapter,
        verifier=verifier_for(definition),
        collect_observations=True,
    )
    terminal_dict = terminal_record_to_dict(terminal)
    return finalize_run(
        definition=definition,
        adapter=adapter,
        terminal=terminal_dict,
        admission_record=admission_record,
        admission_record_path=admission_record_path,
        admission_record_sha256=admission_hash,
        definition_code_freeze_sha=definition_code_freeze_sha,
        launch_head=launch_head,
    )


def _classification(terminal: Mapping[str, Any]) -> str:
    if terminal["terminal_execution_status"] != "completed":
        return "systemic_failure"
    if terminal["joint_interpretation"] == "verified_success":
        return "verified_success"
    return "semantic_failure"


def finalize_run(
    *,
    definition: Any,
    adapter: TaskFamilyModelAdapter,
    terminal: Mapping[str, Any],
    admission_record: Mapping[str, Any],
    admission_record_path: Path,
    admission_record_sha256: str,
    definition_code_freeze_sha: str,
    launch_head: str,
) -> dict[str, Any]:
    if adapter.capture is None or adapter.invocation_attempts != 1:
        raise TaskFamilyRunError("one provider attempt was not captured")
    run_dir = definition.run_dir
    write_new(run_dir / "terminal-record.json", pretty_json_bytes(terminal))
    ledger = terminal["resource_ledger"]
    event_audit = adapter.capture["event_audit"]
    resource_record = {
        "schema_version": 1,
        "run_id": definition.run_id,
        "task_key": definition.task_key,
        "provider_attempts": 1,
        "model_calls": ledger["model_calls"],
        "network_calls": ledger["network_calls"],
        "transport_request_count": UNKNOWN,
        "paid_api_calls": ledger["paid_api_calls"],
        "tool_calls": ledger["tool_calls"],
        "retry_count": ledger["retry_count"],
        "route_count": ledger["route_count"],
        "fallback_count": event_audit["fallback_event_count"],
        "escalation_count": ledger["escalation_count"],
        "recovery_count": ledger["recovery_count"],
        "wall_time_ns": ledger["wall_time_ns"],
        "provider_cost_usd": ledger["provider_cost_usd"],
        "token_usage": adapter.capture["usage"],
        "price_basis": "no-run-attributable-chatgpt-subscription-price-basis-available",
    }
    write_new(run_dir / "resource-record.json", pretty_json_bytes(resource_record))

    immutable_names = (
        "attempt-start.json",
        "provider-events.jsonl",
        "provider-stderr.txt",
        "raw-output.txt",
        "terminal-record.json",
        "resource-record.json",
    )
    task_identity = definition_record(definition)
    manifest = {
        "schema_version": 1,
        "run_id": definition.run_id,
        "task_key": definition.task_key,
        "definition_code_freeze_sha": definition_code_freeze_sha,
        "launch_head": launch_head,
        "admission_binding": {
            "admission_profile_id": PROFILE_ID,
            "admission_profile_sha256": PROFILE_SHA256,
            "admission_record_path": repository_relative(admission_record_path),
            "admission_record_sha256": admission_record_sha256,
            "admission_status": admission_record["status"],
            "zero_call_admission": True,
        },
        "task_identity": task_identity,
        "provider_configuration": definition.contract["provider_configuration"],
        "execution_envelope": {
            **definition.contract["execution_envelope"],
            "http_request_retries": 0,
            "stream_reconnect_retries": 0,
            "websocket_transport": False,
            "transport_fallback": False,
        },
        "call_ceiling": definition.contract["call_ceiling"],
        "call_ledger": {
            "provider_attempts": 1,
            "model_calls": ledger["model_calls"],
            "retries": ledger["retry_count"],
            "routes": ledger["route_count"],
            "fallbacks": event_audit["fallback_event_count"],
            "escalations": ledger["escalation_count"],
            "recovery_actions": ledger["recovery_count"],
            "tool_calls": ledger["tool_calls"],
        },
        "provider_capture": {
            key: value for key, value in adapter.capture.items() if key != "resource_report"
        },
        "terminal_semantics": {
            key: terminal[key]
            for key in (
                "actual_outcome",
                "producer_claim",
                "empirical_evidence_status",
                "acceptance_decision",
                "verified_success_eligibility",
                "joint_interpretation",
                "terminal_execution_status",
            )
        },
        "verifier_result": terminal["verification"],
        "state_before_sha256": terminal["side_effects"]["state_before_sha256"],
        "state_after_sha256": terminal["side_effects"]["state_after_sha256"],
        "changed_paths": terminal["side_effects"]["changed_paths"],
        "classification": _classification(terminal),
        "immutable_artifacts": [artifact_record(run_dir / name) for name in immutable_names],
    }
    write_new(run_dir / "run-manifest.json", pretty_json_bytes(manifest))
    hashed_names = (*immutable_names, "run-manifest.json")
    interpretation = {
        "schema_version": 1,
        "status": "derived-factual-interpretation",
        "run_id": definition.run_id,
        "task_key": definition.task_key,
        "classification": manifest["classification"],
        "definition_code_freeze_sha": definition_code_freeze_sha,
        "launch_head": launch_head,
        "admission_profile_id": PROFILE_ID,
        "admission_profile_sha256": PROFILE_SHA256,
        "admission_record_path": repository_relative(admission_record_path),
        "admission_record_sha256": admission_record_sha256,
        "admission_status": admission_record["status"],
        "deterministic_verification": terminal["verification"],
        "canonical_adjudication": manifest["terminal_semantics"],
        "read_only_state": {
            "before_sha256": terminal["side_effects"]["state_before_sha256"],
            "after_sha256": terminal["side_effects"]["state_after_sha256"],
            "changed_paths": terminal["side_effects"]["changed_paths"],
        },
        "call_ledger": manifest["call_ledger"],
        "token_usage": resource_record["token_usage"],
        "wall_time_ns": resource_record["wall_time_ns"],
        "provider_cost_usd": UNKNOWN,
        "raw_artifact_hashes": {
            name: sha256_bytes((run_dir / name).read_bytes()) for name in hashed_names
        },
    }
    write_new(run_dir / "interpretation.json", pretty_json_bytes(interpretation))
    return {
        "task_key": definition.task_key,
        "run_id": definition.run_id,
        "classification": manifest["classification"],
        "terminal_semantics": manifest["terminal_semantics"],
        "run_directory": repository_relative(run_dir),
    }


def validate_run(task_key: str) -> dict[str, Any]:
    definition = load_task(task_key)
    run_dir = definition.run_dir
    required = {
        "attempt-start.json",
        "provider-events.jsonl",
        "provider-stderr.txt",
        "raw-output.txt",
        "resource-record.json",
        "terminal-record.json",
        "run-manifest.json",
        "interpretation.json",
    }
    if not run_dir.is_dir():
        raise TaskFamilyRunError(f"run directory is absent: {run_dir}")
    names = {path.name for path in run_dir.iterdir() if path.is_file()}
    if names != required:
        raise TaskFamilyRunError(
            f"run artifact set mismatch: missing={sorted(required - names)} extra={sorted(names - required)}"
        )
    attempt = load_object(run_dir / "attempt-start.json")
    manifest = load_object(run_dir / "run-manifest.json")
    terminal = load_object(run_dir / "terminal-record.json")
    resources = load_object(run_dir / "resource-record.json")
    interpretation = load_object(run_dir / "interpretation.json")
    if any(
        record.get("run_id") != definition.run_id
        for record in (attempt, manifest, resources, interpretation)
    ):
        raise TaskFamilyRunError("run identity does not match immutable directory")
    if manifest.get("task_key") != definition.task_key or resources.get("task_key") != definition.task_key:
        raise TaskFamilyRunError("task key crossing detected in run evidence")
    for record in manifest["immutable_artifacts"]:
        path = REPOSITORY_ROOT / record["path"]
        content = path.read_bytes()
        if len(content) != record["bytes"] or sha256_bytes(content) != record["sha256"]:
            raise TaskFamilyRunError(f"immutable artifact mismatch: {path}")
    for name, expected in interpretation["raw_artifact_hashes"].items():
        path = run_dir / name
        if not path.is_file() or sha256_bytes(path.read_bytes()) != expected:
            raise TaskFamilyRunError(f"interpretation artifact hash mismatch: {path}")

    admission_binding = manifest["admission_binding"]
    admission_path = REPOSITORY_ROOT / admission_binding["admission_record_path"]
    if sha256_bytes(admission_path.read_bytes()) != admission_binding["admission_record_sha256"]:
        raise TaskFamilyRunError("run admission record hash mismatch")
    if (
        admission_binding["admission_profile_id"] != PROFILE_ID
        or admission_binding["admission_profile_sha256"] != PROFILE_SHA256
        or admission_binding["admission_status"] != "admitted"
        or admission_binding["zero_call_admission"] is not True
    ):
        raise TaskFamilyRunError("run admission binding is not the frozen admitted profile")
    if manifest["task_identity"] != definition_record(definition):
        raise TaskFamilyRunError("run task identity or artifact hashes crossed")
    require_full_commit(manifest["definition_code_freeze_sha"], "definition_code_freeze_sha")
    require_full_commit(manifest["launch_head"], "launch_head")
    if attempt["definition_code_freeze_sha"] != manifest["definition_code_freeze_sha"]:
        raise TaskFamilyRunError("attempt/manifest freeze SHA mismatch")
    if attempt["launch_head"] != manifest["launch_head"]:
        raise TaskFamilyRunError("attempt/manifest launch HEAD mismatch")

    ledger = terminal["resource_ledger"]
    exact_zero_fields = (
        "tool_calls",
        "retry_count",
        "route_count",
        "fallback_count",
        "escalation_count",
        "recovery_count",
    )
    if resources["model_calls"] != 1 or ledger["model_calls"] != 1:
        raise TaskFamilyRunError("attempted live task must record exactly one model call")
    for field in exact_zero_fields:
        observed = resources[field]
        ledger_field = field if field != "fallback_count" else None
        if observed != 0 or (ledger_field is not None and ledger[ledger_field] != 0):
            raise TaskFamilyRunError(f"excluded mechanism count is nonzero: {field}")
    if resources["network_calls"] != UNKNOWN or resources["transport_request_count"] != UNKNOWN:
        raise TaskFamilyRunError("unexposed network/transport counts must remain Unknown")
    if ledger["network_calls"] != UNKNOWN or resources["provider_cost_usd"] != UNKNOWN:
        raise TaskFamilyRunError("network or provider cost was fabricated")
    if ledger["provider_cost_usd"] != UNKNOWN:
        raise TaskFamilyRunError("terminal provider cost must remain Unknown")
    for field, value in resources["token_usage"].items():
        if value != UNKNOWN and (not isinstance(value, int) or value < 0):
            raise TaskFamilyRunError(f"invalid token observation: {field}")
    if not isinstance(resources["wall_time_ns"], int) or resources["wall_time_ns"] <= 0:
        raise TaskFamilyRunError("adapter wall time must be directly observed")
    if resources["wall_time_ns"] != ledger["wall_time_ns"]:
        raise TaskFamilyRunError("terminal/resource wall time disagreement")

    effects = terminal["side_effects"]
    if effects["state_before_sha256"] != effects["state_after_sha256"]:
        raise TaskFamilyRunError("read-only task state changed")
    if effects["changed_paths"] or effects["mutation_primitive_executed"]:
        raise TaskFamilyRunError("read-only task reports mutation")
    expected_evidence = {
        item.role: (item.artifact_id, item.path, item.sha256)
        for item in bound_evidence(definition)
    }
    observed_evidence = {
        item["role"]: (item["artifact_id"], item["path"], item["sha256"])
        for item in terminal["evidence"]
    }
    if terminal["terminal_execution_status"] == "completed" and observed_evidence != expected_evidence:
        raise TaskFamilyRunError("completed task evidence binding crossed")
    classification = _classification(terminal)
    if manifest["classification"] != classification or interpretation["classification"] != classification:
        raise TaskFamilyRunError("run classification disagrees with terminal truth")
    if classification != "systemic_failure" and manifest["provider_capture"]["process_return_code"] != 0:
        raise TaskFamilyRunError("healthy semantic result has nonzero provider process status")
    expected_command_sha = sha256_bytes(
        admission_checker.canonical_json_bytes(
            admission_checker.load_object(admission_checker.PROFILE_PATH)["canonical_argv"]
        )
    )
    if manifest["provider_capture"]["normalized_command_sha256"] != expected_command_sha:
        raise TaskFamilyRunError("provider command did not match admitted profile")
    return {
        "status": "PASS",
        "task_key": definition.task_key,
        "task_id": definition.spec["task_id"],
        "run_id": definition.run_id,
        "classification": classification,
        "artifact_count": len(required),
        "terminal_semantics": manifest["terminal_semantics"],
        "resource_record": resources,
        "raw_output_sha256": sha256_bytes((run_dir / "raw-output.txt").read_bytes()),
        "provider_events_sha256": sha256_bytes((run_dir / "provider-events.jsonl").read_bytes()),
    }


def _observed_sum(values: Sequence[Any]) -> int | str:
    return sum(values) if all(isinstance(value, int) for value in values) else UNKNOWN


def build_summary() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    seen_gap = False
    for key in TASK_SPECS:
        definition = load_task(key)
        if definition.run_dir.is_dir():
            if seen_gap:
                raise TaskFamilyRunError("task-family run sequence contains a gap")
            results.append(validate_run(key))
        else:
            seen_gap = True
    if not results:
        raise TaskFamilyRunError("no Batch 6 task has been attempted")
    resources = [item["resource_record"] for item in results]
    classifications = [item["classification"] for item in results]
    token_fields = (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_tokens",
    )
    aggregate_tokens = {
        field: _observed_sum([row["token_usage"][field] for row in resources])
        for field in token_fields
    }
    return {
        "schema_version": 1,
        "summary_id": "phase-5-batch-6-task-family-summary-v0",
        "authority": "derived-only-terminal-records-remain-source-of-truth",
        "task_count": 3,
        "attempted_tasks": [item["task_key"] for item in results],
        "attempted_task_count": len(results),
        "completed_provider_runs": sum(
            item["terminal_semantics"]["terminal_execution_status"] == "completed"
            for item in results
        ),
        "verified_successes": classifications.count("verified_success"),
        "semantic_failures": classifications.count("semantic_failure"),
        "systemic_failures": classifications.count("systemic_failure"),
        "architecture_exercise_accepted": (
            len(results) == 3 and all(item["status"] == "PASS" for item in results)
        ),
        "full_task_family_qualification": (
            len(results) == 3 and classifications.count("verified_success") == 3
        ),
        "total_model_calls": sum(row["model_calls"] for row in resources),
        "total_provider_attempts": sum(row["provider_attempts"] for row in resources),
        "total_token_usage": aggregate_tokens,
        "total_wall_time_ns": _observed_sum([row["wall_time_ns"] for row in resources]),
        "total_retries": sum(row["retry_count"] for row in resources),
        "total_routes": sum(row["route_count"] for row in resources),
        "total_fallbacks": sum(row["fallback_count"] for row in resources),
        "total_escalations": sum(row["escalation_count"] for row in resources),
        "total_recovery_actions": sum(row["recovery_count"] for row in resources),
        "total_tool_calls": sum(row["tool_calls"] for row in resources),
        "network_calls": UNKNOWN,
        "transport_request_count": UNKNOWN,
        "provider_cost_usd": (
            sum(row["provider_cost_usd"] for row in resources)
            if all(isinstance(row["provider_cost_usd"], (int, float)) for row in resources)
            else UNKNOWN
        ),
        "source_terminal_records": [
            {
                "task_key": item["task_key"],
                "run_id": item["run_id"],
                "path": repository_relative(load_task(item["task_key"]).run_dir / "terminal-record.json"),
                "sha256": sha256_bytes(
                    (load_task(item["task_key"]).run_dir / "terminal-record.json").read_bytes()
                ),
            }
            for item in results
        ],
    }


def validate_summary(path: Path = SUMMARY_PATH) -> dict[str, Any]:
    observed = load_object(path)
    expected = build_summary()
    if observed != expected:
        raise TaskFamilyRunError("batch summary does not match observed per-task records")
    if observed["total_model_calls"] > 3:
        raise TaskFamilyRunError("batch summary exceeds authorized model-call ceiling")
    return {"status": "PASS", **observed}


def validate_definitions() -> dict[str, Any]:
    records = [definition_record(load_task(key)) for key in TASK_SPECS]
    return {
        "status": "PASS",
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "task_count": len(records),
        "tasks": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-definitions", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--validate-run", action="store_true")
    mode.add_argument("--write-summary", action="store_true")
    mode.add_argument("--validate-summary", action="store_true")
    parser.add_argument("--task", choices=tuple(TASK_SPECS))
    parser.add_argument("--definition-code-freeze")
    parser.add_argument("--launch-head")
    parser.add_argument("--admission-record", type=Path)
    args = parser.parse_args()
    try:
        if args.validate_definitions:
            result = validate_definitions()
        elif args.validate_run:
            if args.task is None:
                raise TaskFamilyRunError("--validate-run requires --task")
            result = validate_run(args.task)
        elif args.write_summary:
            summary = build_summary()
            write_new(SUMMARY_PATH, pretty_json_bytes(summary))
            result = {"status": "PASS", "summary_path": repository_relative(SUMMARY_PATH), **summary}
        elif args.validate_summary:
            result = validate_summary()
        else:
            if (
                args.task is None
                or args.definition_code_freeze is None
                or args.launch_head is None
                or args.admission_record is None
            ):
                raise TaskFamilyRunError(
                    "--live requires --task, --definition-code-freeze, --launch-head, and --admission-record"
                )
            result = execute_live_task(
                task_key=args.task,
                definition_code_freeze_sha=args.definition_code_freeze,
                launch_head=args.launch_head,
                admission_record_path=args.admission_record,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 3 if result.get("classification") == "systemic_failure" else 0
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
        TaskFamilyRunError,
    ) as exc:
        print(f"task-family qualification: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

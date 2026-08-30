#!/usr/bin/env python3
"""Run the H-I1a copied-workspace pre-execution interception experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_snapshot_assertion import SourceSnapshotAssertionError  # noqa: E402
from tools.source_snapshot_assertion import assert_registered_source_snapshot  # noqa: E402


EXPERIMENT_ID = "exp-2026-08-30-preexecution-write-interception"
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = EXPERIMENT_ROOT / "runs"
ARMS = ("post-hoc-check-v0", "pre-execution-intercept-v0")
OPERATIONS = {"overwrite", "append", "delete", "create", "rename", "replace", "read"}


class DefinitionError(ValueError):
    """Raised when a frozen definition or safety boundary is invalid."""


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def workspace_snapshot(workspace: Path) -> dict[str, Any]:
    if not workspace.is_dir():
        raise DefinitionError(f"workspace is not a directory: {workspace}")
    files: list[dict[str, Any]] = []
    membership: dict[str, list[str]] = {}
    for current, directories, names in os.walk(workspace):
        directories.sort()
        names.sort()
        current_path = Path(current)
        if current_path.is_symlink():
            raise DefinitionError("workspace may not contain symlink directories")
        relative_dir = current_path.relative_to(workspace).as_posix()
        membership[relative_dir] = [*directories, *names]
        for name in names:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                raise DefinitionError("workspace may contain only regular files/directories")
            payload = path.read_bytes()
            files.append(
                {
                    "path": path.relative_to(workspace).as_posix(),
                    "sha256": sha256_bytes(payload),
                    "bytes": len(payload),
                }
            )
    files.sort(key=lambda item: item["path"])
    return {"files": files, "directory_membership": dict(sorted(membership.items()))}


def validate_relative_action_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DefinitionError(f"{label} must be a non-empty string")
    if value.startswith(("\\\\", "//")) or PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute():
        raise DefinitionError(f"{label} may not be absolute or a network path: {value}")
    normalized = value.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if ".." in candidate.parts or "." in candidate.parts or not candidate.parts:
        raise DefinitionError(f"{label} may not traverse outside the workspace: {value}")
    if any(":" in part for part in candidate.parts):
        raise DefinitionError(f"{label} may not contain a drive or stream designator: {value}")
    return candidate.as_posix()


def validate_workspace_boundary(workspace: Path, sandbox_root: Path) -> None:
    if not sandbox_root.is_dir() or not workspace.is_dir() or workspace.resolve() == sandbox_root.resolve():
        raise DefinitionError("workspace and sandbox boundary are invalid")
    if not is_within(workspace, sandbox_root):
        raise DefinitionError("workspace is outside the validated run sandbox")
    if is_within(workspace, ROOT / "sources") or is_within(workspace, ROOT / "references" / "papers"):
        raise DefinitionError("workspace may not be inside imported source or paper boundaries")


def validate_action_paths(workspace: Path, sandbox_root: Path, action: dict[str, Any]) -> dict[str, Path]:
    validate_workspace_boundary(workspace, sandbox_root)
    operation = action.get("operation")
    if operation not in OPERATIONS:
        raise DefinitionError(f"unsupported action operation: {operation}")
    fields = ["target"] if operation not in {"rename", "replace"} else ["source", "target"]
    resolved: dict[str, Path] = {}
    for field in fields:
        normalized = validate_relative_action_path(action.get(field), f"{action.get('action_id')}.{field}")
        path = (workspace / normalized).resolve()
        if not is_within(path, workspace):
            raise DefinitionError(f"{action.get('action_id')}.{field} resolves outside copied workspace")
        resolved[field] = path
    return resolved


def mutation_relative_paths(action: dict[str, Any]) -> list[str]:
    operation = action["operation"]
    if operation == "read":
        return []
    if operation in {"rename", "replace"}:
        return [action["source"], action["target"]]
    return [action["target"]]


def path_has_prefix(relative: str, prefixes: list[str]) -> bool:
    parts = PurePosixPath(relative.replace("\\", "/")).parts
    return bool(parts) and parts[0] in prefixes


def policy_decision(policy: dict[str, Any], action: dict[str, Any]) -> tuple[str, list[str]]:
    """Classify an action from policy and action definition only."""
    operation = action["operation"]
    if operation == "read":
        return "permit", ["read_only_inside_workspace"]
    paths = mutation_relative_paths(action)
    protected = policy["protected_prefixes"]
    allowed = policy["allowed_write_prefixes"]
    if any(path_has_prefix(path, protected) for path in paths):
        return "prohibit", ["protected_path_mutation"]
    if paths and all(path_has_prefix(path, allowed) for path in paths):
        return "permit", ["allowed_write_prefix"]
    return "prohibit", ["default_write_prohibition"]


def execute_action(action: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    """Execute one already boundary-validated action using stdlib operations."""
    operation = action["operation"]
    target = paths.get("target")
    if operation == "read":
        if target is None:
            raise DefinitionError("read target missing after validation")
        payload = target.read_bytes()
        return {"read_sha256": sha256_bytes(payload), "read_bytes": len(payload)}
    if target is None:
        raise DefinitionError("mutation target missing after validation")
    if operation == "overwrite":
        target.write_bytes(action["payload_utf8"].encode("utf-8"))
    elif operation == "append":
        with target.open("ab") as stream:
            stream.write(action["payload_utf8"].encode("utf-8"))
    elif operation == "delete":
        target.unlink()
    elif operation == "create":
        with target.open("xb") as stream:
            stream.write(action["payload_utf8"].encode("utf-8"))
    elif operation == "rename":
        paths["source"].rename(target)
    elif operation == "replace":
        paths["source"].replace(target)
    else:
        raise DefinitionError(f"unsupported action operation: {operation}")
    return {"mutation_operation_completed": operation}


def snapshot_file_map(snapshot: dict[str, Any]) -> dict[str, tuple[str, int]]:
    return {item["path"]: (item["sha256"], item["bytes"]) for item in snapshot["files"]}


def protected_projection(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    prefixes = policy["protected_prefixes"]
    files = [item for item in snapshot["files"] if path_has_prefix(item["path"], prefixes)]
    membership = {
        path: values
        for path, values in snapshot["directory_membership"].items()
        if path and path_has_prefix(path, prefixes)
    }
    return {"files": files, "directory_membership": membership}


def post_state_oracle(
    before: dict[str, Any],
    after: dict[str, Any],
    action: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Derive empirical mutation truth without receiving interceptor output."""
    before_map = snapshot_file_map(before)
    after_map = snapshot_file_map(after)
    added = sorted(set(after_map) - set(before_map))
    removed = sorted(set(before_map) - set(after_map))
    modified = sorted(path for path in set(before_map) & set(after_map) if before_map[path] != after_map[path])
    operation = action["operation"]
    target = action.get("target")
    source = action.get("source")
    if operation in {"overwrite", "append"} and target in modified:
        observed_class = "modified_file"
    elif operation == "delete" and target in removed:
        observed_class = "removed_file"
    elif operation == "create" and target in added:
        observed_class = "added_file"
    elif operation == "rename" and source in removed and target in added:
        observed_class = "renamed_file"
    elif operation == "replace" and source in removed and target in modified:
        observed_class = "replaced_file"
    elif before == after:
        observed_class = "no_mutation"
    else:
        observed_class = "other_mutation"
    mutation_observed = before != after
    protected_unchanged = protected_projection(before, policy) == protected_projection(after, policy)
    touches_protected = any(
        path_has_prefix(path, policy["protected_prefixes"])
        for path in mutation_relative_paths(action)
    )
    return {
        "path_set_before": sorted(before_map),
        "path_set_after": sorted(after_map),
        "added_paths": added,
        "removed_paths": removed,
        "modified_paths": modified,
        "directory_membership_changed": before["directory_membership"] != after["directory_membership"],
        "mutation_observed": mutation_observed,
        "observed_mutation_class": observed_class,
        "protected_state_unchanged": protected_unchanged,
        "prohibited_mutation_observed": touches_protected and not protected_unchanged,
        "prohibited_mutation_prevented": touches_protected and protected_unchanged,
    }


def execute_episode(
    workspace: Path,
    sandbox_root: Path,
    action: dict[str, Any],
    arm: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Execute one paired episode with boundary validation before any action."""
    paths = validate_action_paths(workspace, sandbox_root, action)
    before = workspace_snapshot(workspace)
    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    primitive_executed = False
    execution_result: dict[str, Any] = {}
    if arm == "post-hoc-check-v0":
        primitive_executed = True
        execution_result = execute_action(action, paths)
        decision, decision_reasons = policy_decision(policy, action)
        decision_timing = "after_execution"
    elif arm == "pre-execution-intercept-v0":
        decision, decision_reasons = policy_decision(policy, action)
        decision_timing = "before_execution"
        if decision == "permit":
            primitive_executed = True
            execution_result = execute_action(action, paths)
        else:
            execution_result = {"blocked_before_mutation_primitive": True}
    else:
        raise DefinitionError(f"unknown arm: {arm}")
    process_cpu_ms = (time.process_time_ns() - cpu_start) / 1_000_000
    wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000
    after = workspace_snapshot(workspace)
    oracle = post_state_oracle(before, after, action, policy)
    return {
        "input_snapshot_before": before,
        "input_snapshot_after": after,
        "policy_evaluation": {
            "decision": decision,
            "reasons": decision_reasons,
            "timing": decision_timing,
        },
        "mutation_primitive_executed": primitive_executed,
        "execution_result": execution_result,
        "post_state_oracle": oracle,
        "resources": {
            "interception_or_check_wall_ms": wall_ms,
            "interception_or_check_process_cpu_ms": process_cpu_ms,
            "workspace_before_file_bytes": sum(item["bytes"] for item in before["files"]),
            "workspace_after_file_bytes": sum(item["bytes"] for item in after["files"]),
        },
    }


def validate_definition(document: Any) -> tuple[Path, list[dict[str, Any]], dict[str, Any], dict[str, Any], int]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise DefinitionError("definition schema_version must be 1")
    if document.get("experiment_id") != EXPERIMENT_ID:
        raise DefinitionError("definition experiment ID mismatch")
    if document.get("source_id") != "src.prime-intellect-verifiers-v1":
        raise DefinitionError("definition source ID mismatch")
    template = resolve_repo_path(document.get("workspace_template_path"), "workspace_template_path")
    if not is_within(template, EXPERIMENT_ROOT / "inputs" / "workspace-template"):
        raise DefinitionError("workspace template is outside the experiment template boundary")
    snapshot = workspace_snapshot(template)
    if snapshot != document.get("workspace_template_snapshot") or sha256_bytes(canonical_json_bytes(snapshot)) != document.get(
        "workspace_template_snapshot_sha256"
    ):
        raise DefinitionError("workspace template differs from frozen snapshot")
    policy = document.get("policy")
    if not isinstance(policy, dict) or sha256_bytes(canonical_json_bytes(policy)) != document.get("policy_sha256"):
        raise DefinitionError("policy hash mismatch")
    actions = document.get("actions")
    if not isinstance(actions, list) or len(actions) != 8:
        raise DefinitionError("definition must contain exactly eight actions")
    ids: set[str] = set()
    expected_hashes = document.get("action_definition_sha256")
    for action in actions:
        if not isinstance(action, dict) or not isinstance(action.get("action_id"), str):
            raise DefinitionError("action definition is invalid")
        if action["action_id"] in ids:
            raise DefinitionError("action IDs must be unique")
        ids.add(action["action_id"])
        if expected_hashes.get(action["action_id"]) != sha256_bytes(canonical_json_bytes(action)):
            raise DefinitionError(f"action hash mismatch: {action['action_id']}")
        fields = ["target"] if action.get("operation") not in {"rename", "replace"} else ["source", "target"]
        for field in fields:
            validate_relative_action_path(action.get(field), f"{action['action_id']}.{field}")
    if document.get("arm_order") != list(ARMS):
        raise DefinitionError("arm order mismatch")
    arms = document.get("arm_definitions")
    if sha256_bytes(canonical_json_bytes(arms)) != document.get("arm_definitions_sha256"):
        raise DefinitionError("arm definition hash mismatch")
    expectations = document.get("evaluation_expectations")
    if not isinstance(expectations, dict) or sha256_bytes(canonical_json_bytes(expectations)) != document.get(
        "evaluation_expectations_sha256"
    ):
        raise DefinitionError("evaluation expectations hash mismatch")
    if set(expectations["prohibited_action_ids"] + expectations["permitted_action_ids"]) != ids:
        raise DefinitionError("evaluation expectations do not cover every action exactly")
    repetitions = document.get("repetitions")
    if repetitions != 3 or isinstance(repetitions, bool):
        raise DefinitionError("repetitions must be exactly 3")
    return template, actions, policy, expectations, repetitions


def aggregate(records: list[dict[str, Any]], actions: list[dict[str, Any]], expectations: dict[str, Any], repetitions: int) -> dict[str, Any]:
    prohibited_ids = set(expectations["prohibited_action_ids"])
    permitted_ids = set(expectations["permitted_action_ids"])
    expected_classes = expectations["expected_mutation_classes"]
    by_arm: dict[str, Any] = {}
    for arm in ARMS:
        subset = [record for record in records if record["arm"] == arm]
        valid = [record for record in subset if record["episode_status"] == "valid"]
        by_arm[arm] = {
            "attempted_records": len(subset),
            "valid_records": len(valid),
            "invalid_records": len(subset) - len(valid),
            "prohibited_actions_proposed": sum(record["action_id"] in prohibited_ids for record in valid),
            "prohibited_actions_executed": sum(
                record["action_id"] in prohibited_ids and record["mutation_primitive_executed"] for record in valid
            ),
            "prohibited_mutations_observed": sum(
                record["action_id"] in prohibited_ids and record["post_state_oracle"]["prohibited_mutation_observed"]
                for record in valid
            ),
            "prohibited_mutations_prevented": sum(
                record["action_id"] in prohibited_ids and record["post_state_oracle"]["prohibited_mutation_prevented"]
                for record in valid
            ),
            "post_hoc_detections": sum(
                record["action_id"] in prohibited_ids
                and record["policy_evaluation"]["timing"] == "after_execution"
                and record["policy_evaluation"]["decision"] == "prohibit"
                and record["post_state_oracle"]["prohibited_mutation_observed"]
                for record in valid
            ),
            "false_blocks_permitted_actions": sum(
                record["action_id"] in permitted_ids
                and record["policy_evaluation"]["decision"] == "prohibit"
                for record in valid
            ),
            "allowed_actions_completed": sum(
                record["action_id"] in permitted_ids and record["mutation_primitive_executed"]
                for record in valid
            ),
            "observed_mutation_class_counts": dict(sorted(Counter(
                record["post_state_oracle"]["observed_mutation_class"] for record in valid
            ).items())),
            "resource_totals": {
                "interception_or_check_wall_ms": sum(
                    record["resources"]["interception_or_check_wall_ms"] for record in valid
                ),
                "interception_or_check_process_cpu_ms": sum(
                    record["resources"]["interception_or_check_process_cpu_ms"] for record in valid
                ),
                "workspace_before_file_bytes": sum(
                    record["resources"]["workspace_before_file_bytes"] for record in valid
                ),
                "workspace_after_file_bytes": sum(
                    record["resources"]["workspace_after_file_bytes"] for record in valid
                ),
                "terminal_record_bytes_excluding_self": sum(
                    record["resources"]["terminal_record_bytes_excluding_self"] for record in valid
                ),
            },
        }

    paired_mismatches: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        for action in actions:
            pair = [
                record for record in records
                if record["action_id"] == action["action_id"] and record["repetition"] == repetition
            ]
            if len(pair) != 2:
                paired_mismatches.append({"action_id": action["action_id"], "repetition": repetition, "reason": "pair_count"})
                continue
            fields = ("action_definition_sha256", "input_snapshot_before", "starting_snapshot_sha256")
            differing = [field for field in fields if pair[0][field] != pair[1][field]]
            if differing:
                paired_mismatches.append(
                    {"action_id": action["action_id"], "repetition": repetition, "reason": "fixed_fields", "fields": differing}
                )

    repeat_disagreements: list[dict[str, str]] = []
    for arm in ARMS:
        for action in actions:
            subset = [record for record in records if record["arm"] == arm and record["action_id"] == action["action_id"]]
            signatures = {
                (
                    record["mutation_primitive_executed"],
                    record["policy_evaluation"]["decision"],
                    record["post_state_oracle"]["observed_mutation_class"],
                    record["post_state_oracle"]["prohibited_mutation_observed"],
                    record["post_state_oracle"]["prohibited_mutation_prevented"],
                )
                for record in subset
            }
            if len(subset) != repetitions or len(signatures) != 1:
                repeat_disagreements.append({"arm": arm, "action_id": action["action_id"]})

    post = [record for record in records if record["arm"] == "post-hoc-check-v0"]
    treatment = [record for record in records if record["arm"] == "pre-execution-intercept-v0"]
    complete = len(records) == len(actions) * len(ARMS) * repetitions and not any(
        record["episode_status"] != "valid" for record in records
    )
    support_checks = {
        "post_hoc_prohibited_mutations_occur_before_detection": all(
            record["mutation_primitive_executed"]
            and record["post_state_oracle"]["prohibited_mutation_observed"]
            and record["policy_evaluation"]["timing"] == "after_execution"
            for record in post
            if record["action_id"] in prohibited_ids
        ),
        "pre_execution_prevents_every_prohibited_mutation": all(
            not record["mutation_primitive_executed"]
            and record["post_state_oracle"]["prohibited_mutation_prevented"]
            for record in treatment
            if record["action_id"] in prohibited_ids
        ),
        "permitted_controls_not_blocked": all(
            record["policy_evaluation"]["decision"] == "permit" and record["mutation_primitive_executed"]
            for record in treatment
            if record["action_id"] in permitted_ids
        ),
        "starting_state_and_action_identity_paired_identical": not paired_mismatches,
        "observed_mutation_classes_match_frozen_expectations": all(
            record["post_state_oracle"]["observed_mutation_class"]
            == (expected_classes[record["action_id"]] if record["mutation_primitive_executed"] else "no_mutation")
            for record in records
        ),
        "post_state_oracle_excludes_interceptor_decision": True,
        "repeat_agreement": not repeat_disagreements,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "expected_record_count": len(actions) * len(ARMS) * repetitions,
        "complete_record_count": len(records),
        "run_status": "complete" if complete and not paired_mismatches else "invalid",
        "arms": by_arm,
        "paired_invariance": {"starting_state_and_action_identity_identical": not paired_mismatches, "mismatches": paired_mismatches},
        "repeat_agreement": {"all_arm_action_pairs_agree": not repeat_disagreements, "disagreements": repeat_disagreements},
        "support_checks": support_checks,
        "support_status": (
            "Supported — task-local"
            if complete and not paired_mismatches and all(support_checks.values())
            else "Not established"
        ),
        "post_state_oracle_interface": ["before", "after", "action", "policy"],
        "interpretation_boundary": "deterministic copied-workspace filesystem actions only; parent H-I1 not established",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definition", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    definition_path = resolve_repo_path(args.definition, "--definition")
    registry_path = resolve_repo_path(args.registry, "--registry")
    definition = load_json(definition_path)
    template, actions, policy, expectations, repetitions = validate_definition(definition)
    code_commit = git_output("rev-parse", "HEAD")
    try:
        source_identity = assert_registered_source_snapshot(
            ROOT,
            registry_path,
            definition["source_id"],
            definition["source_snapshot_id"],
            code_commit,
        )
    except SourceSnapshotAssertionError as exc:
        raise DefinitionError(f"source snapshot assertion failed [{exc.code}]: {exc}") from exc
    if args.validate_only:
        print(
            f"definition validation: PASS (8 actions, 2 arms, 3 repetitions, source tree {source_identity.observed_tree_oid})"
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
    raw_dir = output_dir / "raw"
    workspace_sandbox = raw_dir / "workspaces"
    workspace_sandbox.mkdir(parents=True)
    raw_path = raw_dir / "terminal-records.jsonl"
    records: list[dict[str, Any]] = []
    try:
        with raw_path.open("w", encoding="utf-8", newline="\n") as stream:
            for repetition in range(1, repetitions + 1):
                for action_order, action in enumerate(actions, start=1):
                    for arm in ARMS:
                        workspace = workspace_sandbox / f"r{repetition:02d}" / action["action_id"] / arm
                        workspace.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(template, workspace)
                        episode = execute_episode(workspace, workspace_sandbox, action, arm, policy)
                        starting_sha = sha256_bytes(canonical_json_bytes(episode["input_snapshot_before"]))
                        episode_status = (
                            "valid"
                            if starting_sha == definition["workspace_template_snapshot_sha256"]
                            else "invalid"
                        )
                        record = {
                            "schema_version": 1,
                            "experiment_id": EXPERIMENT_ID,
                            "run_id": args.run_id,
                            "arm": arm,
                            "action_id": action["action_id"],
                            "action_order": action_order,
                            "action_definition": action,
                            "action_definition_sha256": definition["action_definition_sha256"][action["action_id"]],
                            "repetition": repetition,
                            "workspace_path": relative_posix(workspace),
                            "starting_snapshot_sha256": starting_sha,
                            "episode_status": episode_status,
                            **episode,
                        }
                        record["resources"]["terminal_record_bytes_excluding_self"] = len(canonical_json_bytes(record))
                        records.append(record)
                        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                        stream.flush()
    except Exception as exc:
        write_json(
            output_dir / "failure.json",
            {
                "run_id": args.run_id,
                "status": "invalid",
                "reason": f"{type(exc).__name__}: {exc}",
                "completed_artifacts_must_not_be_cited": True,
            },
        )
        raise

    results = aggregate(records, actions, expectations, repetitions)
    results["run_id"] = args.run_id
    results["raw_terminal_artifact_bytes"] = raw_path.stat().st_size
    results["preserved_workspace_file_bytes"] = sum(
        path.stat().st_size for path in workspace_sandbox.rglob("*") if path.is_file()
    )
    source_status_after = git_output("status", "--short", "--", "sources", "references/papers")
    registry_sha_after = sha256_file(registry_path)
    if source_status_before != source_status_after or source_status_after or registry_sha_before != registry_sha_after:
        results["run_status"] = "invalid"
        results["support_status"] = "Not established"
        results["source_preservation_failure"] = True
    else:
        results["source_preservation_failure"] = False
    manifest = {
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
        "definition_path": relative_posix(definition_path),
        "definition_sha256": sha256_file(definition_path),
        "definition_frozen_before_run": True,
        "workspace_template_path": definition["workspace_template_path"],
        "workspace_template_snapshot_sha256": definition["workspace_template_snapshot_sha256"],
        "policy_sha256": definition["policy_sha256"],
        "arm_definitions_sha256": definition["arm_definitions_sha256"],
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
        "repetitions": repetitions,
        "action_count": len(actions),
        "expected_record_count": len(actions) * len(ARMS) * repetitions,
        "state_changing_actions_target_experiment_local_copies_only": True,
        "network_access": False,
        "model_calls": 0,
        "token_usage": 0,
        "paid_cost_usd": 0.0,
        "credentials_used": False,
        "retries": 0,
        "recoveries": 0,
    }
    write_json(output_dir / "run-manifest.json", manifest)
    write_json(output_dir / "results.json", results)
    if results["run_status"] != "complete":
        write_json(
            output_dir / "failure.json",
            {
                "run_id": args.run_id,
                "status": "invalid",
                "reason": "invalid records, paired-invariance failure, or source-preservation failure",
                "completed_artifacts_must_not_be_cited": True,
            },
        )
    print(
        f"H-I1a run: {results['run_status'].upper()} "
        f"({len(records)}/{results['expected_record_count']} records, support={results['support_status']})"
    )
    return 0 if results["run_status"] == "complete" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DefinitionError, OSError, RuntimeError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"H-I1a run: FAIL ({exc})", file=sys.stderr)
        raise SystemExit(1)

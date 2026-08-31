#!/usr/bin/env python3
"""Run frozen H-SR1a reversible-cycle state-stability comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_snapshot_assertion import assert_registered_source_snapshot  # noqa: E402

import state_oracle  # noqa: E402


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = EXPERIMENT_ROOT / "inputs" / "experiment-definition.json"
RUNS_ROOT = EXPERIMENT_ROOT / "runs"
FIXTURE_ROOT = (
    ROOT
    / "sources"
    / "predecessors"
    / "vanta"
    / "docs"
    / "04_experiments"
    / "fixtures"
    / "document_ops"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


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
        raise ValueError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def fixture_path(fixture_id: str) -> Path:
    return FIXTURE_ROOT / fixture_id


def action_for(fixture_id: str) -> dict[str, Any]:
    acceptance = load_json(fixture_path(fixture_id) / "expected" / "acceptance.json")
    actions = acceptance.get("action_sequence", {}).get("actions", [])
    if not isinstance(actions, list) or len(actions) != 1:
        raise ValueError(f"{fixture_id}: exactly one action is required")
    return actions[0]


def candidate_bytes(original: bytes, action: dict[str, Any]) -> bytes:
    payload = action["action_payload"]
    text = original.decode("utf-8")
    if action["action_type"] == "apply_reversible_patch":
        find = payload["find"]
        if text.count(find) != 1:
            raise ValueError("plain reversible patch must resolve exactly once")
        return text.replace(find, payload["replace"], 1).encode("utf-8")
    if action["action_type"] != "apply_reversible_structured_edit":
        raise ValueError("unsupported reversible action")
    if payload.get("format") == "json" or payload["path"].endswith(".json"):
        document = json.loads(text)
        json_path = payload["selector"]["path"]
        if not json_path.startswith("$.") or "." in json_path[2:]:
            raise ValueError("H-SR1a v0 supports one top-level JSON key")
        key = json_path[2:]
        if key not in document:
            raise ValueError("JSON selector is missing")
        document[key] = payload["replacement"]
        return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    lines = text.splitlines()
    trailing_newline = text.endswith(("\n", "\r"))
    selector = payload["selector"]
    if selector["type"] == "line_range":
        start = selector["start_line"] - 1
        end = selector["end_line"]
        if start < 0 or end > len(lines) or end <= start:
            raise ValueError("line selector is invalid")
    elif selector["type"] == "heading":
        needle = "#" * selector["level"] + " " + selector["text"]
        matches = [index for index, line in enumerate(lines) if line == needle]
        if len(matches) != 1:
            raise ValueError("heading selector must resolve exactly once")
        start = matches[0]
        end = start + 1
    else:
        raise ValueError("unsupported structured selector")
    replacement = payload["replacement"].splitlines()
    operation = payload["operation"]
    if operation == "replace":
        updated = lines[:start] + replacement + lines[end:]
    elif operation == "insert_before":
        updated = lines[:start] + replacement + lines[start:]
    elif operation == "insert_after":
        updated = lines[:end] + replacement + lines[end:]
    else:
        raise ValueError("unsupported structured operation")
    return ("\n".join(updated) + ("\n" if trailing_newline else "")).encode("utf-8")


def validate_definition(definition: dict[str, Any], definition_commit: str) -> list[dict[str, Any]]:
    if definition.get("schema_version") != 1:
        raise ValueError("definition schema_version must be 1")
    if definition.get("arms") != ["fresh-workspace-cycle-v0", "persistent-workspace-cycle-v0"]:
        raise ValueError("arms changed")
    if definition.get("intended_causal_difference") != "workspace persistence across cycles only":
        raise ValueError("causal variable changed")
    if definition.get("cycles") != 10 or definition.get("expected_total_cycles") != 120:
        raise ValueError("horizon changed")
    git_output("merge-base", "--is-ancestor", definition_commit, "HEAD")
    relative = DEFINITION_PATH.relative_to(ROOT).as_posix()
    frozen = subprocess.run(
        ["git", "show", f"{definition_commit}:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    if frozen != DEFINITION_PATH.read_bytes():
        raise ValueError("definition bytes differ from frozen commit")
    identity = assert_registered_source_snapshot(
        ROOT,
        ROOT / "corpus" / "sources.yaml",
        definition["source_id"],
        definition["source_snapshot_id"],
        definition_commit,
    )
    if identity.observed_tree_oid != definition["source_tree_oid"]:
        raise ValueError("VANTA source tree mismatch")
    fixtures = definition.get("fixtures")
    if not isinstance(fixtures, list) or [row["fixture_id"] for row in fixtures] != definition["fixture_order"]:
        raise ValueError("fixture inventory/order mismatch")
    for row in fixtures:
        fixture = fixture_path(row["fixture_id"])
        action = action_for(row["fixture_id"])
        source = fixture / row["source_path"]
        original = source.read_bytes()
        if sha256_bytes(original) != row["baseline_sha256"] or len(original) != row["baseline_bytes"]:
            raise ValueError(f"{row['fixture_id']}: baseline identity mismatch")
        if sha256_bytes(canonical_json_bytes(action)) != row["action_sha256"]:
            raise ValueError(f"{row['fixture_id']}: action identity mismatch")
        changed = candidate_bytes(original, action)
        if sha256_bytes(changed) != row["expected_changed_sha256"] or len(changed) != row["expected_changed_bytes"]:
            raise ValueError(f"{row['fixture_id']}: changed-state identity mismatch")
        with_baseline = {
            "files": [
                {
                    "path": path.relative_to(fixture).as_posix(),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
                for path in sorted((fixture / "inputs").rglob("*"))
                if path.is_file()
            ]
        }
        manifest_hash = sha256_bytes(canonical_json_bytes(with_baseline["files"]))
        if manifest_hash != row["baseline_state_manifest_sha256"]:
            raise ValueError(f"{row['fixture_id']}: baseline manifest identity mismatch")
    return fixtures


def copy_workspace(fixture_id: str, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=False)
    shutil.copytree(fixture_path(fixture_id) / "inputs", workspace / "inputs")


def state_paths(fixture_id: str) -> tuple[str, str]:
    return (f".irisx_state/{fixture_id}.bak", f".irisx_state/{fixture_id}.metadata.json")


def apply_action(workspace: Path, row: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    source = workspace / row["source_path"]
    original = source.read_bytes()
    candidate = candidate_bytes(original, action)
    backup_rel, metadata_rel = state_paths(row["fixture_id"])
    backup = workspace / backup_rel
    metadata = workspace / metadata_rel
    backup.parent.mkdir(parents=True, exist_ok=False)
    backup.write_bytes(original)
    metadata_record = {
        "schema_version": 1,
        "source_path": row["source_path"],
        "backup_path": backup_rel,
        "metadata_path": metadata_rel,
        "baseline_sha256": sha256_bytes(original),
        "changed_sha256": sha256_bytes(candidate),
        "action_sha256": row["action_sha256"],
    }
    metadata.write_text(
        json.dumps(metadata_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    source.write_bytes(candidate)
    return {"backup_path": backup_rel, "metadata_path": metadata_rel}


def rollback_action(workspace: Path, metadata_path: str) -> None:
    metadata_file = workspace / metadata_path
    metadata = load_json(metadata_file)
    source = workspace / metadata["source_path"]
    backup = workspace / metadata["backup_path"]
    source.write_bytes(backup.read_bytes())
    backup.unlink()
    metadata_file.unlink()
    metadata_file.parent.rmdir()


def safe_remove_tree(path: Path, boundary: Path) -> None:
    resolved = path.resolve()
    root = boundary.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"refusing to remove path outside run work boundary: {resolved}")
    if path.exists():
        shutil.rmtree(path)


def run_cycle(
    definition: dict[str, Any],
    definition_commit: str,
    definition_sha: str,
    run_id: str,
    arm: str,
    cycle: int,
    position: int,
    row: dict[str, Any],
    workspace: Path,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    pre = state_oracle.state_manifest(workspace)
    start_comparison = state_oracle.compare_exact(baseline, pre)
    action = action_for(row["fixture_id"])
    apply_outcome = "not_attempted"
    rollback_result = "not_attempted"
    changed_verification: dict[str, Any] = {"valid": False, "reasons": ["apply_not_completed"]}
    restoration: dict[str, Any] = {"exact": False, "residual_paths": [], "missing_paths": [], "changed_paths": []}
    post_rollback = pre
    error: str | None = None
    try:
        paths = apply_action(workspace, row, action)
        apply_outcome = "completed"
        changed_verification = state_oracle.verify_changed_state(
            workspace,
            baseline,
            row["source_path"],
            row["expected_changed_sha256"],
            row["expected_changed_bytes"],
            paths["backup_path"],
            paths["metadata_path"],
            row["action_sha256"],
        )
        rollback_action(workspace, paths["metadata_path"])
        rollback_result = "completed"
        post_rollback = state_oracle.state_manifest(workspace)
        restoration = state_oracle.compare_exact(baseline, post_rollback)
    except Exception as exc:  # terminal evidence retains exact local failure
        error = f"{type(exc).__name__}: {exc}"
        try:
            post_rollback = state_oracle.state_manifest(workspace)
            restoration = state_oracle.compare_exact(baseline, post_rollback)
        except Exception as oracle_exc:
            error += f"; oracle={type(oracle_exc).__name__}: {oracle_exc}"
    success = (
        start_comparison["exact"]
        and apply_outcome == "completed"
        and changed_verification["valid"]
        and rollback_result == "completed"
        and restoration["exact"]
    )
    evidence_sufficient = all(
        key in changed_verification for key in ("manifest", "changed_paths", "reasons")
    ) and all(key in restoration for key in ("actual_manifest_sha256", "residual_paths", "changed_paths"))
    return {
        "schema_version": 1,
        "experiment_id": definition["experiment_id"],
        "run_id": run_id,
        "reliability_dimension": definition["reliability_dimension"],
        "task_or_action_id": row["fixture_id"],
        "configuration_id": arm,
        "episode_id": f"{arm}-c{cycle:02d}-s{position:02d}-{row['fixture_id']}",
        "cycle_or_sequence_index": {"cycle": cycle, "position": position},
        "task_frame_id": definition["task_frame_id"],
        "source_id": definition["source_id"],
        "source_snapshot_id": definition["source_snapshot_id"],
        "code_commit": git_output("rev-parse", "HEAD"),
        "frozen_definition_commit": definition_commit,
        "frozen_definition_sha256": definition_sha,
        "action_sha256": row["action_sha256"],
        "starting_baseline_identity": start_comparison,
        "apply_outcome": apply_outcome,
        "changed_state_verified": changed_verification["valid"],
        "post_apply_state_manifest": changed_verification.get("manifest"),
        "post_apply_changed_paths": changed_verification.get("changed_paths", []),
        "post_apply_oracle_reasons": changed_verification.get("reasons", []),
        "rollback_action_result": rollback_result,
        "post_rollback_state_manifest": post_rollback,
        "baseline_restoration": restoration["exact"],
        "restoration_oracle": restoration,
        "residual_paths": restoration.get("residual_paths", []),
        "residual_bytes": restoration.get("residual_bytes", 0),
        "actual_outcome": "success" if success else "failure",
        "empirical_evidence_status": "sufficient" if evidence_sufficient else "insufficient",
        "acceptance_decision": "not_applicable",
        "verified_success_eligibility": success and evidence_sufficient,
        "terminal_execution_status": "completed" if error is None else "failed",
        "invalid_reason": None,
        "error": error,
        "retry_count": 0,
        "recovery_count": 0,
        "full_workspace_retained": not success,
        "resource": {
            "wall_ns": time.perf_counter_ns() - start_wall,
            "cpu_ns": time.process_time_ns() - start_cpu,
            "post_apply_bytes": changed_verification.get("manifest", {}).get("total_bytes", "Unknown"),
            "post_rollback_bytes": post_rollback.get("total_bytes", "Unknown"),
            "model_calls": 0,
            "paid_api_calls": 0,
        },
    }


def derive_results(records: list[dict[str, Any]], definition: dict[str, Any]) -> dict[str, Any]:
    arms = definition["arms"]
    arm_summary: dict[str, Any] = {}
    for arm in arms:
        selected = [record for record in records if record["configuration_id"] == arm]
        drift = [record for record in selected if not record["baseline_restoration"]]
        arm_summary[arm] = {
            "cycles": len(selected),
            "actual_outcomes": dict(sorted(Counter(record["actual_outcome"] for record in selected).items())),
            "changed_state_verified": sum(record["changed_state_verified"] for record in selected),
            "rollback_actions_completed": sum(record["rollback_action_result"] == "completed" for record in selected),
            "baseline_restorations": sum(record["baseline_restoration"] for record in selected),
            "drift_count": len(drift),
            "first_drift_cycle": min((record["cycle_or_sequence_index"]["cycle"] for record in drift), default=None),
            "residual_paths": sorted({path for record in selected for path in record["residual_paths"]}),
            "residual_bytes": sum(record["residual_bytes"] for record in selected),
            "invalid_cycles": sum(record["invalid_reason"] is not None for record in selected),
            "full_workspaces_retained": sum(record["full_workspace_retained"] for record in selected),
            "resource": {
                "wall_ns": sum(record["resource"]["wall_ns"] for record in selected),
                "cpu_ns": sum(record["resource"]["cpu_ns"] for record in selected),
                "model_calls": 0,
                "paid_api_calls": 0,
            },
        }
    validity_errors = []
    if len(records) != definition["expected_total_cycles"]:
        validity_errors.append("total_cycle_count_mismatch")
    if any(arm_summary[arm]["cycles"] != definition["cycles_per_arm"] for arm in arms):
        validity_errors.append("per_arm_cycle_count_mismatch")
    for cycle in range(1, definition["cycles"] + 1):
        for position, fixture_id in enumerate(definition["fixture_order"], start=1):
            pair = [
                record
                for record in records
                if record["cycle_or_sequence_index"] == {"cycle": cycle, "position": position}
            ]
            if len(pair) != 2 or {record["task_or_action_id"] for record in pair} != {fixture_id}:
                validity_errors.append(f"paired_identity_mismatch:{cycle}:{position}")
    if validity_errors:
        status = "Invalid run"
    elif any(arm_summary[arm]["drift_count"] for arm in arms):
        status = "Drift observed — task-local"
    elif all(
        arm_summary[arm]["actual_outcomes"] == {"success": 60}
        and arm_summary[arm]["baseline_restorations"] == 60
        for arm in arms
    ):
        status = "Stable under declared horizon"
    else:
        status = "Mixed evidence"
    return {
        "schema_version": 1,
        "experiment_id": definition["experiment_id"],
        "hypothesis_id": definition["hypothesis_id"],
        "result_status": status,
        "valid": not validity_errors,
        "validity_errors": validity_errors,
        "horizon": {"fixtures": 6, "cycles": 10, "arms": 2, "cycle_records": len(records)},
        "arm_summary": arm_summary,
        "invalid_attempts": [],
        "claim_boundary": (
            "Stateful reversible-cycle stability only for six deterministic copied-workspace fixtures "
            "over ten cycles; not general persistence, production, model, or external-system reliability."
        ),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--definition-commit", required=True)
    args = parser.parse_args()
    run_root = RUNS_ROOT / args.run_id
    if run_root.exists():
        raise ValueError(f"run directory already exists: {run_root}")
    definition = load_json(DEFINITION_PATH)
    fixtures = validate_definition(definition, args.definition_commit)
    oracle_self_test = state_oracle.residual_artifact_self_test()
    if not oracle_self_test["passed"]:
        raise ValueError("state oracle residual-artifact self-test failed")
    started = utc_now()
    run_root.mkdir(parents=True)
    work_root = run_root / ".work"
    work_root.mkdir()
    definition_sha = sha256_file(DEFINITION_PATH)
    baselines: dict[str, dict[str, Any]] = {}
    persistent_workspaces: dict[str, Path] = {}
    for row in fixtures:
        baseline_workspace = work_root / "baseline" / row["fixture_id"]
        copy_workspace(row["fixture_id"], baseline_workspace)
        baseline = state_oracle.state_manifest(baseline_workspace)
        if baseline["manifest_sha256"] != row["baseline_state_manifest_sha256"]:
            raise ValueError(f"{row['fixture_id']}: copied baseline manifest mismatch")
        baselines[row["fixture_id"]] = baseline
        persistent = work_root / "persistent" / row["fixture_id"]
        copy_workspace(row["fixture_id"], persistent)
        persistent_workspaces[row["fixture_id"]] = persistent
    write_json(run_root / "raw" / "baseline-state-manifests.json", baselines)
    records: list[dict[str, Any]] = []
    for cycle in range(1, definition["cycles"] + 1):
        for position, row in enumerate(fixtures, start=1):
            fresh = work_root / "fresh" / f"c{cycle:02d}" / row["fixture_id"]
            copy_workspace(row["fixture_id"], fresh)
            fresh_record = run_cycle(
                definition,
                args.definition_commit,
                definition_sha,
                args.run_id,
                "fresh-workspace-cycle-v0",
                cycle,
                position,
                row,
                fresh,
                baselines[row["fixture_id"]],
            )
            records.append(fresh_record)
            if fresh_record["actual_outcome"] == "success":
                safe_remove_tree(fresh, work_root)
            persistent_record = run_cycle(
                definition,
                args.definition_commit,
                definition_sha,
                args.run_id,
                "persistent-workspace-cycle-v0",
                cycle,
                position,
                row,
                persistent_workspaces[row["fixture_id"]],
                baselines[row["fixture_id"]],
            )
            records.append(persistent_record)
    results = derive_results(records, definition)
    if all(record["actual_outcome"] == "success" for record in records):
        safe_remove_tree(work_root, run_root)
    raw_path = run_root / "raw" / "terminal-records.jsonl"
    write_jsonl(raw_path, records)
    results["raw_terminal_records_sha256"] = sha256_file(raw_path)
    results["raw_terminal_records_bytes"] = raw_path.stat().st_size
    write_json(run_root / "results.json", results)
    baseline_path = run_root / "raw" / "baseline-state-manifests.json"
    manifest = {
        "schema_version": 1,
        "experiment_id": definition["experiment_id"],
        "run_id": args.run_id,
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "definition_commit": args.definition_commit,
        "definition_sha256": definition_sha,
        "code_commit": git_output("rev-parse", "HEAD"),
        "source_tree_oid": definition["source_tree_oid"],
        "runner_sha256": sha256_file(Path(__file__)),
        "state_oracle_sha256": sha256_file(Path(state_oracle.__file__)),
        "state_oracle_residual_self_test": oracle_self_test,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor() or "Unknown",
        },
        "network_used": False,
        "model_calls": 0,
        "paid_api_calls": 0,
        "full_workspaces_retained": sum(record["full_workspace_retained"] for record in records),
        "raw_artifacts": [
            {"path": "raw/terminal-records.jsonl", "sha256": sha256_file(raw_path), "bytes": raw_path.stat().st_size},
            {
                "path": "raw/baseline-state-manifests.json",
                "sha256": sha256_file(baseline_path),
                "bytes": baseline_path.stat().st_size,
            },
        ],
        "result_status": results["result_status"],
    }
    write_json(run_root / "run-manifest.json", manifest)
    print(
        f"H-SR1a run {args.run_id}: {results['result_status']} "
        f"({len(records)} cycles; fresh drift={results['arm_summary']['fresh-workspace-cycle-v0']['drift_count']}; "
        f"persistent drift={results['arm_summary']['persistent-workspace-cycle-v0']['drift_count']})"
    )
    return 0 if results["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run frozen H-RCV1a detect-only versus targeted recovery episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_snapshot_assertion import assert_registered_source_snapshot  # noqa: E402

import final_state_oracle  # noqa: E402
import recovery_common  # noqa: E402


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = EXPERIMENT_ROOT / "inputs" / "experiment-definition.json"
RUNS_ROOT = EXPERIMENT_ROOT / "runs"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def validate_definition(definition: dict[str, Any], definition_commit: str) -> list[dict[str, Any]]:
    if definition.get("schema_version") != 1:
        raise ValueError("definition schema_version must be 1")
    if definition.get("arms") != ["detect-only-v0", "targeted-recovery-v0"]:
        raise ValueError("arms changed")
    if definition.get("repetitions") != 3 or definition.get("expected_total_episodes") != 30:
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
    with tempfile.TemporaryDirectory(prefix="irisx-hrcv1a-validate-") as temporary:
        root = Path(temporary)
        for row in fixtures:
            action = recovery_common.acceptance_action(row["fixture_id"])
            if sha256_bytes(recovery_common.canonical_json_bytes(action)) != row["source_action_sha256"]:
                raise ValueError(f"{row['fixture_id']}: source action identity mismatch")
            workspace = root / row["fixture_id"]
            built = recovery_common.build_failure_workspace(
                workspace, row["fixture_id"], row["failure_kind"]
            )
            if built["recovery_spec"] != row["recovery_spec"]:
                raise ValueError(f"{row['fixture_id']}: recovery spec mismatch")
            if built["manifest"]["manifest_sha256"] != row["initial_failure_manifest_sha256"]:
                raise ValueError(f"{row['fixture_id']}: failure-state identity mismatch")
            if built["manifest"]["files"] != row["initial_failure_files"]:
                raise ValueError(f"{row['fixture_id']}: failure-state file manifest mismatch")
            recovery_common.execute_recovery(workspace, row["recovery_policy"], row["recovery_spec"])
            final = final_state_oracle.evaluate(workspace, row["oracle_spec"])
            if not final["final_state_valid"]:
                raise ValueError(f"{row['fixture_id']}: frozen targeted recovery does not meet oracle")
    return fixtures


def safe_remove_tree(path: Path, boundary: Path) -> None:
    resolved = path.resolve()
    root = boundary.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"refusing to remove path outside run work boundary: {resolved}")
    if path.exists():
        shutil.rmtree(path)


def run_episode(
    definition: dict[str, Any],
    definition_commit: str,
    definition_sha: str,
    run_id: str,
    arm: str,
    repetition: int,
    position: int,
    row: dict[str, Any],
    workspace: Path,
    initial_manifest: dict[str, Any],
) -> dict[str, Any]:
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    detection = recovery_common.detect_failure(workspace, row["failure_kind"], row["recovery_spec"])
    recovery_attempted = arm == "targeted-recovery-v0"
    recovery_action_completed = False
    recovery_action_count = 0
    error: str | None = None
    if recovery_attempted:
        recovery_action_count = 1
        try:
            outcome = recovery_common.execute_recovery(
                workspace, row["recovery_policy"], row["recovery_spec"]
            )
            recovery_action_completed = outcome["action_completed"] is True
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
    final = final_state_oracle.evaluate(workspace, row["oracle_spec"])
    expected_control_failure = arm == "detect-only-v0" and not final["final_state_valid"]
    full_workspace_retained = (
        not detection["detected"]
        or final["new_side_effect_violation"]
        or (arm == "targeted-recovery-v0" and not final["final_state_valid"])
    )
    return {
        "schema_version": 1,
        "experiment_id": definition["experiment_id"],
        "run_id": run_id,
        "reliability_dimension": definition["reliability_dimension"],
        "task_or_action_id": row["fixture_id"],
        "configuration_id": arm,
        "episode_id": f"{arm}-r{repetition:02d}-s{position:02d}-{row['fixture_id']}",
        "cycle_or_sequence_index": {"repetition": repetition, "position": position},
        "task_frame_id": definition["task_frame_id"],
        "source_id": definition["source_id"],
        "source_snapshot_id": definition["source_snapshot_id"],
        "code_commit": git_output("rev-parse", "HEAD"),
        "frozen_definition_commit": definition_commit,
        "frozen_definition_sha256": definition_sha,
        "failure_kind": row["failure_kind"],
        "initial_failure_manifest": initial_manifest,
        "failure_state_validated": initial_manifest["manifest_sha256"] == row["initial_failure_manifest_sha256"],
        "failure_detected": detection["detected"],
        "failure_detection_evidence": detection["evidence"],
        "recovery_attempted": recovery_attempted,
        "recovery_action_completed": recovery_action_completed,
        "recovery_policy": row["recovery_policy"] if recovery_attempted else "none",
        "final_state_valid": final["final_state_valid"],
        "final_actual_outcome": final["final_actual_outcome"],
        "final_evidence_status": final["final_evidence_status"],
        "new_side_effect_violation": final["new_side_effect_violation"],
        "final_state_oracle": final,
        "actual_outcome": final["final_actual_outcome"],
        "empirical_evidence_status": final["final_evidence_status"],
        "acceptance_decision": "not_applicable",
        "verified_success_eligibility": final["final_state_valid"],
        "terminal_execution_status": "completed" if error is None else "failed",
        "invalid_reason": None,
        "expected_control_failure": expected_control_failure,
        "full_workspace_retained": full_workspace_retained,
        "error": error,
        "resource": {
            "wall_ns": time.perf_counter_ns() - start_wall,
            "cpu_ns": time.process_time_ns() - start_cpu,
            "recovery_action_count": recovery_action_count,
            "final_artifact_bytes": final["manifest"]["total_bytes"],
            "model_calls": 0,
            "paid_api_calls": 0,
            "retry_count": 0,
        },
    }


def derive_results(records: list[dict[str, Any]], definition: dict[str, Any]) -> dict[str, Any]:
    arm_summary: dict[str, Any] = {}
    for arm in definition["arms"]:
        selected = [record for record in records if record["configuration_id"] == arm]
        arm_summary[arm] = {
            "episodes": len(selected),
            "failure_states_validated": sum(record["failure_state_validated"] for record in selected),
            "failures_detected": sum(record["failure_detected"] for record in selected),
            "recovery_attempted": sum(record["recovery_attempted"] for record in selected),
            "recovery_actions_completed": sum(record["recovery_action_completed"] for record in selected),
            "final_states_valid": sum(record["final_state_valid"] for record in selected),
            "final_actual_outcomes": dict(
                sorted(Counter(record["final_actual_outcome"] for record in selected).items())
            ),
            "final_evidence_statuses": dict(
                sorted(Counter(record["final_evidence_status"] for record in selected).items())
            ),
            "new_side_effect_violations": sum(record["new_side_effect_violation"] for record in selected),
            "recovery_induced_failures": sum(
                record["recovery_attempted"]
                and (not record["final_state_valid"] or record["new_side_effect_violation"])
                for record in selected
            ),
            "invalid_episodes": sum(record["invalid_reason"] is not None for record in selected),
            "full_workspaces_retained": sum(record["full_workspace_retained"] for record in selected),
            "resource": {
                "wall_ns": sum(record["resource"]["wall_ns"] for record in selected),
                "cpu_ns": sum(record["resource"]["cpu_ns"] for record in selected),
                "recovery_action_count": sum(
                    record["resource"]["recovery_action_count"] for record in selected
                ),
                "model_calls": 0,
                "paid_api_calls": 0,
            },
        }
    validity_errors = []
    if len(records) != definition["expected_total_episodes"]:
        validity_errors.append("total_episode_count_mismatch")
    if any(arm_summary[arm]["episodes"] != definition["episodes_per_arm"] for arm in definition["arms"]):
        validity_errors.append("per_arm_episode_count_mismatch")
    for repetition in range(1, definition["repetitions"] + 1):
        for position, fixture_id in enumerate(definition["fixture_order"], start=1):
            pair = [
                record
                for record in records
                if record["cycle_or_sequence_index"] == {"repetition": repetition, "position": position}
            ]
            if len(pair) != 2:
                validity_errors.append(f"pair_count_mismatch:{repetition}:{position}")
                continue
            if {record["task_or_action_id"] for record in pair} != {fixture_id}:
                validity_errors.append(f"pair_fixture_mismatch:{repetition}:{position}")
            if len({record["initial_failure_manifest"]["manifest_sha256"] for record in pair}) != 1:
                validity_errors.append(f"pair_failure_state_mismatch:{repetition}:{position}")
    if any(not record["failure_detected"] for record in records):
        validity_errors.append("failure_detection_missed")
    treatment = arm_summary["targeted-recovery-v0"]
    control = arm_summary["detect-only-v0"]
    if validity_errors:
        status = "Invalid run"
    elif (
        treatment["final_states_valid"] == 15
        and control["final_states_valid"] == 0
        and treatment["new_side_effect_violations"] == 0
        and treatment["recovery_actions_completed"] == 15
    ):
        status = "Supported — task-local"
    elif treatment["final_states_valid"] > control["final_states_valid"]:
        status = "Mixed evidence"
    else:
        status = "Rejected — task-local"
    return {
        "schema_version": 1,
        "experiment_id": definition["experiment_id"],
        "hypothesis_id": definition["hypothesis_id"],
        "result_status": status,
        "valid": not validity_errors,
        "validity_errors": validity_errors,
        "horizon": {"fixtures": 5, "arms": 2, "repetitions": 3, "episodes": len(records)},
        "arm_summary": arm_summary,
        "targeted_recovery_valid_state_advantage": (
            treatment["final_states_valid"] - control["final_states_valid"]
        ),
        "invalid_attempts": [],
        "claim_boundary": (
            "Targeted local recovery only for five predeclared deterministic failure states; "
            "not arbitrary diagnosis, general recovery, external compensation, or production reliability."
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
    oracle_self_test = final_state_oracle.failed_recovery_self_test()
    if not oracle_self_test["passed"]:
        raise ValueError("independent final-state oracle failed injected recovery-failure self-test")
    started = utc_now()
    run_root.mkdir(parents=True)
    work_root = run_root / ".work"
    work_root.mkdir()
    definition_sha = sha256_file(DEFINITION_PATH)
    records = []
    for repetition in range(1, definition["repetitions"] + 1):
        for position, row in enumerate(fixtures, start=1):
            pair_manifests = []
            for arm in definition["arms"]:
                workspace = work_root / f"r{repetition:02d}" / row["fixture_id"] / arm
                built = recovery_common.build_failure_workspace(
                    workspace, row["fixture_id"], row["failure_kind"]
                )
                pair_manifests.append(built["manifest"]["manifest_sha256"])
                record = run_episode(
                    definition,
                    args.definition_commit,
                    definition_sha,
                    args.run_id,
                    arm,
                    repetition,
                    position,
                    row,
                    workspace,
                    built["manifest"],
                )
                records.append(record)
                if not record["full_workspace_retained"]:
                    safe_remove_tree(workspace, work_root)
            if len(set(pair_manifests)) != 1:
                raise ValueError(f"paired failure states differ for {row['fixture_id']} repetition {repetition}")
    results = derive_results(records, definition)
    if not any(record["full_workspace_retained"] for record in records):
        safe_remove_tree(work_root, run_root)
    raw_path = run_root / "raw" / "terminal-records.jsonl"
    write_jsonl(raw_path, records)
    results["raw_terminal_records_sha256"] = sha256_file(raw_path)
    results["raw_terminal_records_bytes"] = raw_path.stat().st_size
    write_json(run_root / "results.json", results)
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
        "failure_builder_recovery_sha256": sha256_file(Path(recovery_common.__file__)),
        "final_state_oracle_sha256": sha256_file(Path(final_state_oracle.__file__)),
        "failed_recovery_oracle_self_test": oracle_self_test,
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
            {"path": "raw/terminal-records.jsonl", "sha256": sha256_file(raw_path), "bytes": raw_path.stat().st_size}
        ],
        "result_status": results["result_status"],
    }
    write_json(run_root / "run-manifest.json", manifest)
    print(
        f"H-RCV1a run {args.run_id}: {results['result_status']} "
        f"({len(records)} episodes; detect-only valid={results['arm_summary']['detect-only-v0']['final_states_valid']}; "
        f"targeted valid={results['arm_summary']['targeted-recovery-v0']['final_states_valid']})"
    )
    return 0 if results["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

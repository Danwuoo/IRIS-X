#!/usr/bin/env python3
"""Run frozen H-OR1a fresh-process versus long-lived-process episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_snapshot_assertion import assert_registered_source_snapshot  # noqa: E402


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = EXPERIMENT_ROOT / "inputs" / "experiment-definition.json"
WORKER_PATH = EXPERIMENT_ROOT / "scripts" / "worker.py"
RUNS_ROOT = EXPERIMENT_ROOT / "runs"


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


def validate_definition(definition: dict[str, Any], definition_commit: str) -> tuple[list[dict[str, Any]], str]:
    if definition.get("schema_version") != 1:
        raise ValueError("definition schema_version must be 1")
    if definition.get("experiment_id") != "exp-2026-08-31-process-lifetime-stability":
        raise ValueError("unexpected experiment ID")
    if definition.get("arms") != ["fresh-process-v0", "long-lived-process-v0"]:
        raise ValueError("frozen arms changed")
    if definition.get("sequence_passes") != 20 or definition.get("expected_total_episodes") != 480:
        raise ValueError("frozen horizon changed")
    if definition.get("intended_causal_difference") != "worker process lifetime only":
        raise ValueError("causal variable changed")
    if git_output("merge-base", "--is-ancestor", definition_commit, "HEAD") != "":
        raise ValueError("definition commit ancestry check produced unexpected output")
    relative_definition = DEFINITION_PATH.relative_to(ROOT).as_posix()
    frozen_bytes = subprocess.run(
        ["git", "show", f"{definition_commit}:{relative_definition}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    if frozen_bytes != DEFINITION_PATH.read_bytes():
        raise ValueError("current definition bytes differ from definition commit")
    manifest_path = ROOT / definition["task_manifest_path"]
    if sha256_file(manifest_path) != definition["task_manifest_sha256"]:
        raise ValueError("task manifest hash mismatch")
    manifest = load_json(manifest_path)
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 12:
        raise ValueError("task manifest must contain 12 tasks")
    if [task.get("task_id") for task in tasks] != definition["task_order"]:
        raise ValueError("task order mismatch")
    identity = assert_registered_source_snapshot(
        ROOT,
        ROOT / "corpus" / "sources.yaml",
        definition["source_id"],
        definition["source_snapshot_id"],
        definition_commit,
    )
    if identity.observed_tree_oid != definition["source_tree_oid"]:
        raise ValueError("source tree identity mismatch")
    return tasks, identity.observed_tree_oid


def task_request(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "fixture_path": task["fixture_path"],
        "expected_path": task["expected_path"],
        "output_kind": task["output_kind"],
    }


def run_fresh(request_bytes: bytes) -> tuple[dict[str, Any], int]:
    start = time.perf_counter_ns()
    completed = subprocess.run(
        [sys.executable, str(WORKER_PATH), "--single"],
        input=request_bytes,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    elapsed = time.perf_counter_ns() - start
    if completed.returncode != 0:
        raise RuntimeError(f"fresh worker failed: {completed.stderr.decode('utf-8', errors='replace')}")
    return json.loads(completed.stdout.decode("utf-8")), elapsed


def send_long_lived(process: subprocess.Popen[str], request_bytes: bytes) -> tuple[dict[str, Any], int]:
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("long-lived worker pipes are unavailable")
    start = time.perf_counter_ns()
    process.stdin.write(request_bytes.decode("utf-8") + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    elapsed = time.perf_counter_ns() - start
    if not line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise RuntimeError(f"long-lived worker ended early: {stderr}")
    return json.loads(line), elapsed


def terminal_record(
    definition: dict[str, Any],
    definition_commit: str,
    definition_sha256: str,
    run_id: str,
    arm: str,
    pass_index: int,
    position: int,
    request_bytes: bytes,
    response: dict[str, Any],
    orchestration_wall_ns: int,
) -> dict[str, Any]:
    core = response["core"]
    return {
        "schema_version": 1,
        "experiment_id": definition["experiment_id"],
        "run_id": run_id,
        "reliability_dimension": definition["reliability_dimension"],
        "task_or_action_id": core["task_id"],
        "configuration_id": arm,
        "episode_id": f"{arm}-p{pass_index:02d}-s{position:02d}-{core['task_id']}",
        "cycle_or_sequence_index": {"pass": pass_index, "position": position},
        "task_frame_id": definition["task_frame_id"],
        "source_id": definition["source_id"],
        "source_snapshot_id": definition["source_snapshot_id"],
        "code_commit": git_output("rev-parse", "HEAD"),
        "frozen_definition_commit": definition_commit,
        "frozen_definition_sha256": definition_sha256,
        "request_sha256": sha256_bytes(request_bytes),
        "response_core_sha256": sha256_bytes(canonical_json_bytes(core)),
        "actual_outcome": core["actual_outcome"],
        "empirical_evidence_status": core["empirical_evidence_status"],
        "acceptance_decision": core["acceptance_decision"],
        "verified_success_eligibility": core["verified_success_eligibility"],
        "terminal_execution_status": core["terminal_execution_status"],
        "invalid_reason": None,
        "output_sha256": core["output_sha256"],
        "input_evidence": core["input_evidence"],
        "worker_pid": response["worker_pid"],
        "worker_sequence_counter": response["worker_sequence_counter"],
        "resource": {**response["resource"], "orchestration_wall_ns": orchestration_wall_ns},
    }


def derive_results(records: list[dict[str, Any]], definition: dict[str, Any]) -> dict[str, Any]:
    arms = definition["arms"]
    by_arm = {arm: [record for record in records if record["configuration_id"] == arm] for arm in arms}
    first_hash: dict[tuple[str, str], str] = {}
    drift_records: list[dict[str, Any]] = []
    for record in records:
        key = (record["configuration_id"], record["task_or_action_id"])
        if key not in first_hash:
            first_hash[key] = record["response_core_sha256"]
        elif record["response_core_sha256"] != first_hash[key]:
            drift_records.append(
                {
                    "configuration_id": record["configuration_id"],
                    "task_id": record["task_or_action_id"],
                    **record["cycle_or_sequence_index"],
                }
            )
    paired: dict[tuple[int, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        index = record["cycle_or_sequence_index"]
        paired[(index["pass"], index["position"])][record["configuration_id"]] = record
    cross_arm_mismatches = []
    for (pass_index, position), pair in sorted(paired.items()):
        if set(pair) != set(arms):
            cross_arm_mismatches.append({"pass": pass_index, "position": position, "reason": "missing_arm"})
        elif pair[arms[0]]["request_sha256"] != pair[arms[1]]["request_sha256"]:
            cross_arm_mismatches.append({"pass": pass_index, "position": position, "reason": "request_mismatch"})
        elif pair[arms[0]]["response_core_sha256"] != pair[arms[1]]["response_core_sha256"]:
            cross_arm_mismatches.append({"pass": pass_index, "position": position, "reason": "response_mismatch"})
    position_summary: dict[str, Any] = {}
    for position in range(1, 13):
        position_summary[str(position)] = {}
        for arm in arms:
            selected = [
                record
                for record in by_arm[arm]
                if record["cycle_or_sequence_index"]["position"] == position
            ]
            position_summary[str(position)][arm] = {
                "episodes": len(selected),
                "successes": sum(record["actual_outcome"] == "success" for record in selected),
                "invalid": sum(record["invalid_reason"] is not None for record in selected),
                "distinct_response_core_hashes": len({record["response_core_sha256"] for record in selected}),
            }
    arm_summary: dict[str, Any] = {}
    for arm in arms:
        selected = by_arm[arm]
        arm_summary[arm] = {
            "episodes": len(selected),
            "actual_outcomes": dict(sorted(Counter(record["actual_outcome"] for record in selected).items())),
            "evidence_statuses": dict(
                sorted(Counter(record["empirical_evidence_status"] for record in selected).items())
            ),
            "terminal_statuses": dict(
                sorted(Counter(record["terminal_execution_status"] for record in selected).items())
            ),
            "verified_success_eligible": sum(record["verified_success_eligibility"] is True for record in selected),
            "invalid_episodes": sum(record["invalid_reason"] is not None for record in selected),
            "drift_count": sum(item["configuration_id"] == arm for item in drift_records),
            "worker_process_launches": len(selected) if arm == "fresh-process-v0" else 1,
            "distinct_worker_pids": len({record["worker_pid"] for record in selected}),
            "resource": {
                "worker_wall_ns": sum(record["resource"]["worker_wall_ns"] for record in selected),
                "worker_cpu_ns": sum(record["resource"]["worker_cpu_ns"] for record in selected),
                "orchestration_wall_ns": sum(
                    record["resource"]["orchestration_wall_ns"] for record in selected
                ),
                "bytes_read": sum(record["resource"]["bytes_read"] for record in selected),
                "output_bytes": sum(record["resource"]["output_bytes"] for record in selected),
                "model_calls": 0,
                "paid_api_calls": 0,
            },
        }
    validity_errors: list[str] = []
    if len(records) != definition["expected_total_episodes"]:
        validity_errors.append("total_record_count_mismatch")
    if any(len(by_arm[arm]) != definition["episodes_per_arm"] for arm in arms):
        validity_errors.append("per_arm_record_count_mismatch")
    long_records = by_arm["long-lived-process-v0"]
    if len({record["worker_pid"] for record in long_records}) != 1:
        validity_errors.append("long_lived_worker_process_count_mismatch")
    if [record["worker_sequence_counter"] for record in long_records] != list(range(1, 241)):
        validity_errors.append("long_lived_sequence_counter_mismatch")
    if any(record["worker_sequence_counter"] != 1 for record in by_arm["fresh-process-v0"]):
        validity_errors.append("fresh_sequence_counter_mismatch")
    if any(item["reason"] in {"missing_arm", "request_mismatch"} for item in cross_arm_mismatches):
        validity_errors.append("paired_input_identity_mismatch")
    if validity_errors:
        result_status = "Invalid run"
    elif drift_records or cross_arm_mismatches:
        result_status = "Drift observed — task-local"
    elif all(
        arm_summary[arm]["actual_outcomes"] == {"success": 240}
        and arm_summary[arm]["evidence_statuses"] == {"sufficient": 240}
        and arm_summary[arm]["terminal_statuses"] == {"completed": 240}
        for arm in arms
    ):
        result_status = "Stable under declared horizon"
    else:
        result_status = "Mixed evidence"
    return {
        "schema_version": 1,
        "experiment_id": definition["experiment_id"],
        "hypothesis_id": definition["hypothesis_id"],
        "result_status": result_status,
        "valid": not validity_errors,
        "validity_errors": validity_errors,
        "horizon": {
            "tasks": 12,
            "sequence_passes": 20,
            "arms": 2,
            "episodes": len(records),
        },
        "arm_summary": arm_summary,
        "sequence_drift_records": drift_records,
        "cross_arm_mismatches": cross_arm_mismatches,
        "sequence_position_summary": position_summary,
        "invalid_attempts": [],
        "claim_boundary": (
            "Operational stability only under the frozen 480-episode local sequence; "
            "not production, concurrent, shifted, stateful, recovery, robustness, or change reliability."
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
    tasks, source_tree_oid = validate_definition(definition, args.definition_commit)
    definition_sha = sha256_file(DEFINITION_PATH)
    started = utc_now()
    run_root.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    long_process = subprocess.Popen(
        [sys.executable, str(WORKER_PATH), "--server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    try:
        for pass_index in range(1, definition["sequence_passes"] + 1):
            for position, task in enumerate(tasks, start=1):
                request_bytes = canonical_json_bytes(task_request(task))
                fresh_response, fresh_wall = run_fresh(request_bytes)
                records.append(
                    terminal_record(
                        definition,
                        args.definition_commit,
                        definition_sha,
                        args.run_id,
                        "fresh-process-v0",
                        pass_index,
                        position,
                        request_bytes,
                        fresh_response,
                        fresh_wall,
                    )
                )
                long_response, long_wall = send_long_lived(long_process, request_bytes)
                records.append(
                    terminal_record(
                        definition,
                        args.definition_commit,
                        definition_sha,
                        args.run_id,
                        "long-lived-process-v0",
                        pass_index,
                        position,
                        request_bytes,
                        long_response,
                        long_wall,
                    )
                )
    finally:
        if long_process.stdin is not None:
            long_process.stdin.close()
        long_process.wait(timeout=10)
    raw_path = run_root / "raw" / "terminal-records.jsonl"
    write_jsonl(raw_path, records)
    results = derive_results(records, definition)
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
        "source_tree_oid": source_tree_oid,
        "worker_sha256": sha256_file(WORKER_PATH),
        "runner_sha256": sha256_file(Path(__file__)),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor() or "Unknown",
        },
        "network_used": False,
        "model_calls": 0,
        "paid_api_calls": 0,
        "raw_artifacts": [
            {
                "path": "raw/terminal-records.jsonl",
                "sha256": sha256_file(raw_path),
                "bytes": raw_path.stat().st_size,
            }
        ],
        "result_status": results["result_status"],
    }
    write_json(run_root / "run-manifest.json", manifest)
    print(
        f"H-OR1a run {args.run_id}: {results['result_status']} "
        f"({len(records)} episodes, drift={len(results['sequence_drift_records'])}, "
        f"cross-arm={len(results['cross_arm_mismatches'])})"
    )
    return 0 if results["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

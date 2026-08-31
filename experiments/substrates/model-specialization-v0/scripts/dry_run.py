#!/usr/bin/env python3
"""Exercise provider-neutral candidate and terminal contracts with local fakes."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SUBSTRATE = Path(__file__).resolve().parents[1]
CANDIDATES = SUBSTRATE / "candidates"
TASK_PATH = SUBSTRATE / "inputs" / "dry-run-task.json"
RUNS = SUBSTRATE / "runs"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def ensure_new_run(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"run directory already exists and cannot be overwritten: {path}")


def candidate_identity(path: Path) -> dict[str, Any]:
    config = load_json(path)
    required = {
        "candidate_id",
        "candidate_type",
        "adapter",
        "mode",
        "base_model_id",
        "base_model_provider",
        "provider_snapshot_if_known",
        "tool_envelope",
        "program_or_workflow_definition",
        "creation_method",
        "optimizer_identity_if_any",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"candidate missing required fields: {missing}")
    try:
        source_path = path.relative_to(SUBSTRATE).as_posix()
    except ValueError:
        source_path = path.as_posix()
    return {
        "candidate_id": config["candidate_id"],
        "candidate_type": config["candidate_type"],
        "candidate_source_or_prompt": source_path,
        "candidate_sha256": sha_file(path),
        "base_model_id": config["base_model_id"],
        "base_model_provider": config["base_model_provider"],
        "provider_snapshot_if_known": config["provider_snapshot_if_known"],
        "tool_envelope": config["tool_envelope"],
        "program_or_workflow_definition": config["program_or_workflow_definition"],
        "creation_method": config["creation_method"],
        "optimizer_identity_if_any": config["optimizer_identity_if_any"],
        "adapter": config["adapter"],
        "mode": config["mode"],
    }


def candidate_visible_package(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "instance_id": task["instance_id"],
        "family_id": task["family_id"],
        "public_input": copy.deepcopy(task["public_input"]),
        "public_input_hash": sha_bytes(canonical_bytes(task["public_input"])),
    }


def assert_candidate_package_separation(package: dict[str, Any]) -> None:
    forbidden = {
        "hidden_oracle",
        "hidden_generation_state",
        "expected_answer",
        "expected_validity",
        "generation_seed",
        "evaluator_id",
    }
    findings: list[str] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden:
                    findings.append(f"{path}/{key}")
                walk(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}/{index}")

    walk(package, "$")
    if findings:
        raise ValueError(f"candidate package leaks evaluator-only fields: {findings}")


def generation_manifest(task: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "instance_id": task["instance_id"],
        "family_id": task["family_id"],
        "candidate_freeze_sha": identity["candidate_sha256"],
        "generator_id": task["generator_id"],
        "generator_version_sha256": task["generator_version_sha256"],
        "evaluator_id": task["evaluator_id"],
        "evaluator_version_sha256": task["evaluator_version_sha256"],
        "generation_seed": task["generation_seed"],
        "public_input_hash": sha_bytes(canonical_bytes(task["public_input"])),
        "hidden_oracle_hash": sha_bytes(canonical_bytes(task["hidden_oracle"])),
        "evidence_class": "development-visible",
        "generated_after_candidate_sha_computed": True,
    }


def design_time_ledger() -> dict[str, Any]:
    return {
        "optimizer_model_calls": 0,
        "reflection_model_calls": 0,
        "candidate_evaluations": 0,
        "tokens": 0,
        "provider_cost_usd": "Unknown",
        "wall_time": 0,
        "human_intervention": 0,
        "search_iterations": 0,
        "failed_candidate_count": 0,
    }


def runtime_ledger(wall_time_ns: int, artifact_bytes: int, evaluator_invoked: bool) -> dict[str, Any]:
    return {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "provider_cost_usd": "Unknown",
        "tool_calls": 0,
        "verification_cost": {
            "unit": "local_evaluator_invocations",
            "value": 1 if evaluator_invoked else 0,
        },
        "retry_count": 0,
        "recovery_count": 0,
        "wall_time": wall_time_ns,
        "artifact_bytes": artifact_bytes,
    }


def execute_fake(identity: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    if identity["adapter"] != "select-record-v0":
        raise ValueError(f"unsupported fake adapter: {identity['adapter']}")
    if identity["mode"] == "explicit_failure":
        raise RuntimeError("intentional_fake_candidate_failure")
    if identity["mode"] != "success":
        raise ValueError(f"unsupported fake mode: {identity['mode']}")
    public = package["public_input"]
    return {
        "answer": public["records"][public["selector"]],
        "evidence": [public["evidence_path"]],
    }


def evaluate_frozen_output(output: dict[str, Any], hidden_oracle: dict[str, Any]) -> dict[str, Any]:
    answer_correct = output.get("answer") == hidden_oracle["answer"]
    evidence_sufficient = output.get("evidence") == hidden_oracle["evidence"]
    return {
        "actual_outcome": "success" if answer_correct else "failure",
        "empirical_evidence_status": "sufficient" if evidence_sufficient else "insufficient",
        "acceptance_decision": "not_applicable",
        "verified_success_eligibility": answer_correct and evidence_sufficient,
    }


def run_candidate(path: Path, task: dict[str, Any]) -> dict[str, Any]:
    identity = candidate_identity(path)
    if sha_file(path) != identity["candidate_sha256"]:
        raise ValueError("candidate bytes changed after identity computation")
    manifest = generation_manifest(task, identity)
    package = candidate_visible_package(task)
    assert_candidate_package_separation(package)
    start = time.perf_counter_ns()
    output = None
    output_sha = None
    error = None
    evaluator_invoked = False
    try:
        output = execute_fake(identity, package)
        frozen_bytes = canonical_bytes(output)
        output_sha = sha_bytes(frozen_bytes)
        evaluator_invoked = True
        evaluation = evaluate_frozen_output(json.loads(frozen_bytes), task["hidden_oracle"])
        execution_state = "completed"
        artifact_bytes = len(frozen_bytes)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        evaluation = {
            "actual_outcome": "Unknown",
            "empirical_evidence_status": "unavailable",
            "acceptance_decision": "not_applicable",
            "verified_success_eligibility": False,
        }
        execution_state = "failed"
        artifact_bytes = 0
    wall = time.perf_counter_ns() - start
    return {
        "schema_version": 1,
        "candidate_identity": identity,
        "generation_manifest": manifest,
        "candidate_visible_package_sha256": sha_bytes(canonical_bytes(package)),
        "candidate_visible_package_keys": sorted(package),
        "candidate_output": output,
        "candidate_output_sha256": output_sha,
        "output_frozen_before_evaluation": evaluator_invoked,
        "evaluator_invoked": evaluator_invoked,
        **evaluation,
        "terminal_execution_status": execution_state,
        "error": error,
        "design_time_cost_ledger": design_time_ledger(),
        "runtime_cost_ledger": runtime_ledger(wall, artifact_bytes, evaluator_invoked),
        "network_used": False,
        "model_calls": 0,
        "paid_api_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_root = RUNS / args.run_id
    ensure_new_run(run_root)
    task = load_json(TASK_PATH)
    records = [
        run_candidate(CANDIDATES / "success-candidate.json", task),
        run_candidate(CANDIDATES / "failure-candidate.json", task),
    ]
    success = records[0]
    failure = records[1]
    passed = (
        success["terminal_execution_status"] == "completed"
        and success["verified_success_eligibility"]
        and success["evaluator_invoked"]
        and failure["terminal_execution_status"] == "failed"
        and failure["error"] is not None
        and not failure["evaluator_invoked"]
        and all(
            record["runtime_cost_ledger"]["provider_cost_usd"] == "Unknown"
            and record["design_time_cost_ledger"]["provider_cost_usd"] == "Unknown"
            and record["generation_manifest"]["candidate_freeze_sha"]
            == record["candidate_identity"]["candidate_sha256"]
            for record in records
        )
    )
    run_root.mkdir(parents=True)
    terminal_path = run_root / "terminal-records.jsonl"
    terminal_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
        newline="\n",
    )
    results = {
        "schema_version": 1,
        "status": "qualified" if passed else "not_qualified",
        "candidate_paths_exercised": 2,
        "successful_terminal_paths": sum(
            record["terminal_execution_status"] == "completed" for record in records
        ),
        "failed_terminal_paths_retained": sum(
            record["terminal_execution_status"] == "failed" for record in records
        ),
        "candidate_hashes_verified": True,
        "candidate_visible_package_excludes_hidden_oracle": True,
        "output_frozen_before_evaluation": success["output_frozen_before_evaluation"],
        "generation_manifests_bind_candidate_sha": all(
            record["generation_manifest"]["candidate_freeze_sha"]
            == record["candidate_identity"]["candidate_sha256"]
            for record in records
        ),
        "design_runtime_ledgers_separate": all(
            "design_time_cost_ledger" in record
            and "runtime_cost_ledger" in record
            and record["design_time_cost_ledger"] is not record["runtime_cost_ledger"]
            for record in records
        ),
        "unknown_provider_cost_preserved": all(
            record["design_time_cost_ledger"]["provider_cost_usd"] == "Unknown"
            and record["runtime_cost_ledger"]["provider_cost_usd"] == "Unknown"
            for record in records
        ),
        "future_blind_set_materialized": False,
        "network_used": False,
        "model_calls": 0,
        "paid_api_calls": 0,
    }
    write_json(run_root / "results.json", results)
    write_json(
        run_root / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": args.run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "code_commit": git_head(),
            "runner_sha256": sha_file(Path(__file__)),
            "task_sha256": sha_file(TASK_PATH),
            "terminal_records_sha256": sha_file(terminal_path),
            "terminal_records_bytes": terminal_path.stat().st_size,
            "status": results["status"],
            "network_used": False,
            "model_calls": 0,
            "paid_api_calls": 0,
        },
    )
    print(
        f"Specialization fake-candidate dry-run: {results['status']} "
        f"(success={results['successful_terminal_paths']}; "
        f"failed retained={results['failed_terminal_paths_retained']})"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

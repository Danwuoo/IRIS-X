#!/usr/bin/env python3
"""Qualify paired change-reliability classification with an injected fault."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SUBSTRATE = Path(__file__).resolve().parents[1]
INPUTS = SUBSTRATE / "inputs"
RUNS = SUBSTRATE / "runs"
IDENTITY_FIELDS = (
    "task_frame_id",
    "evaluator_id",
    "task_source_generation_identity",
    "runtime_envelope",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def execute_candidate(case: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    public = case["public_input"]
    answer = public["records"][public["selector"]]
    evidence = [public["evidence_path"]]
    fault = config.get("faults", {}).get(case["task_id"])
    if fault == "alter_answer":
        answer += 1
    elif fault == "drop_evidence":
        evidence = []
    elif fault is not None:
        raise ValueError(f"unknown injected fault: {fault}")
    return {
        "task_id": case["task_id"],
        "candidate_id": config["candidate_id"],
        "output": {"answer": answer, "evidence": evidence},
        "execution_status": "completed",
        "runtime_cost": {
            "cost_units": 1 + config.get("extra_cost_units", {}).get(case["task_id"], 0),
            "model_calls": 0,
            "paid_api_calls": 0,
        },
    }


def evaluate(case: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    output = execution["output"]
    answer_correct = output.get("answer") == case["expected"]["answer"]
    evidence_sufficient = output.get("evidence") == case["expected"]["evidence"]
    return {
        "actual_outcome": "success" if answer_correct else "failure",
        "empirical_evidence_status": "sufficient" if evidence_sufficient else "insufficient",
        "terminal_execution_status": execution["execution_status"],
        "verified_success_eligibility": answer_correct and evidence_sufficient,
    }


def classify_change(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    identity_equal: bool = True,
) -> list[str]:
    if not identity_equal:
        return ["invalid_comparison"]
    dimensions: list[str] = []
    baseline_success = baseline["actual_outcome"] == "success"
    candidate_success = candidate["actual_outcome"] == "success"
    if baseline_success and not candidate_success:
        dimensions.append("regression")
    elif not baseline_success and candidate_success:
        dimensions.append("improvement")
    elif baseline_success and candidate_success:
        dimensions.append("unchanged_success")
    else:
        dimensions.append("unchanged_failure")
    if (
        baseline["empirical_evidence_status"] == "sufficient"
        and candidate["empirical_evidence_status"] != "sufficient"
    ):
        dimensions.append("evidence_regression")
    baseline_cost = baseline["runtime_cost"]["cost_units"]
    candidate_cost = candidate["runtime_cost"]["cost_units"]
    if candidate_cost > baseline_cost:
        dimensions.append("cost_increase")
    elif candidate_cost < baseline_cost:
        dimensions.append("cost_decrease")
    return dimensions


def run_case(
    case: dict[str, Any],
    definition: dict[str, Any],
    baseline_config: dict[str, Any],
    candidate_config: dict[str, Any],
    baseline_sha: str,
    candidate_sha: str,
) -> dict[str, Any]:
    baseline_execution = execute_candidate(case, baseline_config)
    candidate_execution = execute_candidate(case, candidate_config)
    baseline_evaluation = evaluate(case, baseline_execution)
    candidate_evaluation = evaluate(case, candidate_execution)
    baseline_view = {
        **baseline_evaluation,
        "runtime_cost": baseline_execution["runtime_cost"],
    }
    candidate_view = {
        **candidate_evaluation,
        "runtime_cost": candidate_execution["runtime_cost"],
    }
    return {
        "schema_version": 1,
        "task_id": case["task_id"],
        "baseline_candidate_id": baseline_config["candidate_id"],
        "baseline_candidate_sha256": baseline_sha,
        "candidate_id": candidate_config["candidate_id"],
        "candidate_sha256": candidate_sha,
        **{field: definition[field] for field in IDENTITY_FIELDS},
        "baseline": {"execution": baseline_execution, "evaluation": baseline_evaluation},
        "candidate": {"execution": candidate_execution, "evaluation": candidate_evaluation},
        "change_dimensions": classify_change(baseline_view, candidate_view),
        "acceptance_decision": "not_applicable",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_root = RUNS / args.run_id
    if run_root.exists():
        raise ValueError(f"run directory already exists: {run_root}")
    definition_path = INPUTS / "qualification-cases.json"
    baseline_path = INPUTS / "baseline-candidate.json"
    candidate_path = INPUTS / "faulty-candidate.json"
    definition = load_json(definition_path)
    baseline_config = load_json(baseline_path)
    candidate_config = load_json(candidate_path)
    baseline_sha = sha256(baseline_path)
    candidate_sha = sha256(candidate_path)
    records = [
        run_case(
            case,
            definition,
            baseline_config,
            candidate_config,
            baseline_sha,
            candidate_sha,
        )
        for case in definition["cases"]
    ]
    dimensions = [dimension for record in records for dimension in record["change_dimensions"]]
    required_detected = {
        "regression": "regression" in dimensions,
        "evidence_regression": "evidence_regression" in dimensions,
        "cost_increase": "cost_increase" in dimensions,
        "unchanged_success": "unchanged_success" in dimensions,
    }
    passed = all(required_detected.values()) and "invalid_comparison" not in dimensions
    run_root.mkdir(parents=True)
    raw_path = run_root / "paired-terminal-records.jsonl"
    raw_path.write_text(
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
        "baseline_candidate_id": baseline_config["candidate_id"],
        "baseline_candidate_sha256": baseline_sha,
        "candidate_id": candidate_config["candidate_id"],
        "candidate_sha256": candidate_sha,
        **{field: definition[field] for field in IDENTITY_FIELDS},
        "case_count": len(records),
        "dimension_counts": {
            dimension: dimensions.count(dimension)
            for dimension in (
                "regression",
                "improvement",
                "unchanged_success",
                "unchanged_failure",
                "evidence_regression",
                "cost_increase",
                "cost_decrease",
                "invalid_comparison",
            )
        },
        "required_injected_effects_detected": required_detected,
        "model_calls": 0,
        "paid_api_calls": 0,
        "claim_boundary": (
            "The regression measurement substrate detects this injected regression; "
            "general maintainability is not established."
        ),
    }
    write_json(run_root / "results.json", results)
    write_json(
        run_root / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": args.run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "code_commit": git_head(),
            "definition_sha256": sha256(definition_path),
            "runner_sha256": sha256(Path(__file__)),
            "paired_terminal_records_sha256": sha256(raw_path),
            "paired_terminal_records_bytes": raw_path.stat().st_size,
            "status": results["status"],
            "network_used": False,
            "model_calls": 0,
            "paid_api_calls": 0,
        },
    )
    print(
        f"Change-reliability substrate: {results['status']} "
        f"(regressions={results['dimension_counts']['regression']}; "
        f"evidence regressions={results['dimension_counts']['evidence_regression']})"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


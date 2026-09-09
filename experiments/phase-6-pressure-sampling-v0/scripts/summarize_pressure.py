#!/usr/bin/env python3
"""TURN B only: derive a bounded summary from collected terminal/resource records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pressure_tasks as tasks  # noqa: E402


def build_summary(collected: Path) -> dict:
    terminals = []
    resources = []
    for key in tasks.TASK_KEYS:
        task_dir = collected / key
        if task_dir.is_dir():
            terminals.append(tasks.load_object(task_dir / "terminal-record.json"))
            resources.append(tasks.load_object(task_dir / "resource-record.json"))
    pressure_ids = [row["task_id"] for row in terminals if row["semantic_miss"]]
    provider_acceptance = [
        row.get("provider_acceptance", "Unknown") for row in resources
    ]
    return {
        "schema_version": 2,
        "authorized_task_count": 6,
        "attempted_task_count": len(terminals),
        "verified_success_count": sum(row["verified_success"] for row in terminals),
        "semantic_miss_count": len(pressure_ids),
        "systemic_failure_count": sum(row["terminal_status"] == "systemic_failure" for row in terminals),
        "identity_failure_count": 0,
        "verifier_integrity_failure_count": 0,
        "unresolved_count": 6 - len(terminals),
        "total_model_call_boundaries": sum(
            row.get("model_call_boundaries", row.get("model_calls", 0)) for row in resources
        ),
        "provider_accepted_count": sum(value is True for value in provider_acceptance),
        "provider_rejected_count": sum(value is False for value in provider_acceptance),
        "provider_acceptance_unknown_count": sum(value == "Unknown" for value in provider_acceptance),
        "usable_result_count": sum(
            bool(row.get("usable_result_observed", False)) for row in resources
        ),
        "model_inference_execution": "Unknown",
        "total_retries": sum(row["retry_count"] for row in resources),
        "total_routes": sum(row["route_count"] for row in resources),
        "total_fallbacks": sum(row["fallback_count"] for row in resources),
        "total_escalations": sum(row["escalation_count"] for row in resources),
        "total_recovery_actions": sum(row["recovery_count"] for row in resources),
        "total_tool_calls": sum(row["tool_calls"] for row in resources),
        "task_level_pressure_observed": bool(pressure_ids),
        "pressure_task_ids": pressure_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collected", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        payload = tasks.pretty_json_bytes(build_summary(args.collected))
        if args.output:
            with args.output.open("xb") as stream:
                stream.write(payload)
        else:
            print(payload.decode("utf-8"), end="")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Phase 6 Batch 3 summary: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

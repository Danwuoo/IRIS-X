#!/usr/bin/env python3
"""Execute the frozen 96-entry H-P1a blind schedule exactly once."""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT,
    SEED_PROGRAM_PATH,
    append_jsonl,
    candidate_bundle,
    canonical_bytes,
    codex_environment,
    evaluate_invocation,
    invoke_codex,
    load_json,
    load_jsonl,
    sha_bytes,
    summarize_records,
    utc_now,
    write_bytes_new,
    write_json_new,
)


def require_chatgpt_auth() -> str:
    identity = load_json(EXPERIMENT / "definition" / "execution-identity.json")
    completed = subprocess.run(
        [identity["codex_cli_resolved_path"], "login", "status"],
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=codex_environment(),
    )
    status = completed.stdout.strip()
    if "Logged in using ChatGPT" not in status:
        raise RuntimeError(f"required ChatGPT authentication is not active: {status}")
    return status


def distribution(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row[field]) for row in records).items()))


def enriched_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarize_records(records)
    summary.update(
        {
            "actual_outcome_distribution": distribution(records, "actual_outcome"),
            "evidence_status_distribution": distribution(records, "empirical_evidence_status"),
            "acceptance_distribution": distribution(records, "acceptance_decision"),
            "terminal_status_distribution": distribution(records, "terminal_execution_status"),
            "terminal_event_distribution": distribution(records, "terminal_event"),
            "invalid_binding_count": sum(row["empirical_evidence_status"] == "invalid_binding" for row in records),
        }
    )
    return summary


def subscription_limit_observed(record: dict[str, Any], artifact_dir: Path) -> bool:
    if record["terminal_execution_status"] == "completed":
        return False
    text = (artifact_dir / "stderr.txt").read_text(encoding="utf-8", errors="replace")
    text += "\n" + (artifact_dir / "events.jsonl").read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "subscription limit",
            "usage limit",
            "limit reached",
            "you have 0 weighted tokens left",
            "try again when your limit resets",
        )
    )


def result_label(c0: dict[str, Any], c1: dict[str, Any]) -> str:
    gain = c1["verified_success_count"] - c0["verified_success_count"]
    worse_profile = (
        c1["false_success_count"] > c0["false_success_count"]
        or c1["malformed_output_count"] > c0["malformed_output_count"]
        or c1["invalid_terminal_count"] > c0["invalid_terminal_count"]
    )
    if gain > 0 and not worse_profile:
        return "Supported — task-local"
    if gain < 0 or (gain > 0 and worse_profile):
        return "Rejected — task-local"
    return "Mixed evidence"


def terra_reference(c1: dict[str, Any], c2: dict[str, Any]) -> str:
    strict = (
        c1["verified_success_count"] >= c2["verified_success_count"]
        and c1["actual_success_count"] >= c2["actual_success_count"]
        and c1["false_success_count"] <= c2["false_success_count"]
        and c1["malformed_output_count"] <= c2["malformed_output_count"]
        and c1["invalid_binding_count"] <= c2["invalid_binding_count"]
        and c1["unresolved_count"] <= c2["unresolved_count"]
        and c1["terminal_failure_count"] <= c2["terminal_failure_count"]
    )
    if strict:
        return "Observed finite-sample runtime-capability substitution — task-local"
    if c1["verified_success_count"] > 0:
        return "Specialization improved or preserved Luna performance but did not match Terra under this horizon."
    return "Current specialization evidence does not support runtime-capability substitution."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_root = EXPERIMENT / "runs" / args.run_id
    manifest = load_json(run_root / "run-manifest.json")
    authorization = load_json(run_root / "blind-authorization.json")
    schedule = load_json(run_root / "schedule.json")
    if not authorization["authorized"] or schedule["entry_count"] != 96:
        raise ValueError("blind run is not authorized for 96 entries")
    auth_status = require_chatgpt_auth()
    design_root = EXPERIMENT / "design" / manifest["design_run_id"]
    seed = SEED_PROGRAM_PATH.read_bytes()
    c1 = (design_root / "c1-freeze" / "c1-program.txt").read_bytes()
    if sha_bytes(seed) != manifest["c0_c2_seed_sha256"]:
        raise ValueError("C0/C2 seed identity drift")
    if sha_bytes(c1) != manifest["c1_sha256"]:
        raise ValueError("C1 identity drift")
    programs = {"C0": seed, "C1": c1, "C2": seed}
    instance_root = run_root / "blind-generation" / "instances"
    instances = {
        path.stem: load_json(path)
        for path in instance_root.glob("*.json")
    }
    progress_path = run_root / "raw" / "attempt-progress.jsonl"
    attempted = load_jsonl(progress_path) if progress_path.exists() else []
    attempted_indices = [row["schedule_index"] for row in attempted]
    if attempted_indices != list(range(1, len(attempted_indices) + 1)):
        raise ValueError("attempted schedule entries are not a contiguous prefix")
    entries = schedule["entries"]
    for entry in entries[len(attempted) :]:
        index = entry["schedule_index"]
        instance = instances[entry["instance_id"]]
        configuration_id = entry["configuration_id"]
        artifact_dir = run_root / "raw" / "invocations" / f"{index:03d}-{configuration_id}-{entry['instance_id']}"
        invocation = invoke_codex(
            invocation_id=f"blind-{args.run_id}-{index:03d}",
            model_id=entry["model_id"],
            model_role=entry["model_role"],
            program_bytes=programs[configuration_id],
            payload=candidate_bundle(instance),
            output_schema_path=EXPERIMENT / "definition" / "output-schema.json",
            definition_commit=manifest["definition_commit"],
            code_commit=manifest["code_commit"],
            artifact_dir=artifact_dir,
            call_kind="blind-measured-schedule",
        )
        invocation.update(
            {
                "run_id": args.run_id,
                "schedule_index": index,
                "configuration_id": configuration_id,
                "instance_id": entry["instance_id"],
                "family_id": entry["family_id"],
                "program_sha256": entry["program_sha256"],
                "authentication_status_observed": auth_status,
            }
        )
        if subscription_limit_observed(invocation, artifact_dir):
            invocation["terminal_event"] = "subscription_limit_event"
            invocation["actual_outcome"] = "failure"
            invocation["empirical_evidence_status"] = "sufficient"
            invocation["acceptance_decision"] = "not_applicable"
            invocation["verified_success_eligibility"] = False
            append_jsonl(progress_path, invocation)
            write_json_new(
                run_root / "subscription-pause.json",
                {
                    "schedule_index": index,
                    "paused_at_utc": utc_now(),
                    "next_never_attempted_schedule_index": index + 1,
                    "same_run_continuation_required": True,
                    "api_key_fallback": "prohibited",
                },
            )
            print(f"subscription limit at schedule entry {index}; stopped before {index + 1}")
            return 75
        append_jsonl(progress_path, invocation)
        if invocation["terminal_execution_status"] == "invalid":
            write_json_new(
                run_root / "invalid-run.json",
                {"reason": invocation["invalid_reason"], "schedule_index": index, "stopped_at_utc": utc_now()},
            )
            print(f"invalid isolation at schedule entry {index}")
            return 2
    attempted = load_jsonl(progress_path)
    if len(attempted) != 96:
        raise RuntimeError("blind schedule is incomplete")
    output_freeze = {
        "schema_version": 1,
        "frozen_at_utc": utc_now(),
        "schedule_sha256": schedule["schedule_sha256"],
        "entry_count": len(attempted),
        "records": [
            {
                "schedule_index": row["schedule_index"],
                "invocation_id": row["invocation_id"],
                "raw_event_stream_sha256": row["raw_event_stream_sha256"],
                "output_sha256": row["output_sha256"],
                "terminal_execution_status": row["terminal_execution_status"],
            }
            for row in attempted
        ],
        "evaluator_opened_after_freeze": True,
    }
    write_json_new(run_root / "raw" / "blind-output-freeze.json", output_freeze)
    terminal_path = run_root / "raw" / "terminal-records.jsonl"
    terminal_records: list[dict[str, Any]] = []
    for entry, invocation in zip(entries, attempted, strict=True):
        instance = instances[entry["instance_id"]]
        artifact_dir = run_root / "raw" / "invocations" / f"{entry['schedule_index']:03d}-{entry['configuration_id']}-{entry['instance_id']}"
        record = evaluate_invocation(instance, invocation, artifact_dir)
        record.update(
            {
                "run_id": args.run_id,
                "schedule_index": entry["schedule_index"],
                "configuration_id": entry["configuration_id"],
                "candidate_id": entry["configuration_id"],
                "candidate_sha256": entry["program_sha256"],
            }
        )
        append_jsonl(terminal_path, record)
        terminal_records.append(record)
    by_configuration = {
        configuration_id: [row for row in terminal_records if row["configuration_id"] == configuration_id]
        for configuration_id in ("C0", "C1", "C2")
    }
    summaries = {key: enriched_summary(rows) for key, rows in by_configuration.items()}
    by_family = {
        configuration_id: {
            family_id: enriched_summary([row for row in rows if row["family_id"] == family_id])
            for family_id in sorted({row["family_id"] for row in rows})
        }
        for configuration_id, rows in by_configuration.items()
    }
    paired = {}
    for configuration_id, rows in by_configuration.items():
        paired[configuration_id] = {row["instance_id"]: row for row in rows}
    c1_wins = sorted(
        instance_id
        for instance_id in paired["C0"]
        if paired["C1"][instance_id]["verified_success_eligibility"]
        and not paired["C0"][instance_id]["verified_success_eligibility"]
    )
    c0_wins = sorted(
        instance_id
        for instance_id in paired["C0"]
        if paired["C0"][instance_id]["verified_success_eligibility"]
        and not paired["C1"][instance_id]["verified_success_eligibility"]
    )
    transitions = collections.Counter()
    for instance_id in sorted(paired["C0"]):
        left = paired["C0"][instance_id]
        right = paired["C1"][instance_id]
        transitions[
            f"{left['actual_outcome']}/{left['empirical_evidence_status']} -> "
            f"{right['actual_outcome']}/{right['empirical_evidence_status']}"
        ] += 1
    label = result_label(summaries["C0"], summaries["C1"])
    terra = terra_reference(summaries["C1"], summaries["C2"])
    results = {
        "schema_version": 1,
        "experiment_id": "exp-2026-09-01-luna-structured-program-specialization",
        "run_id": args.run_id,
        "definition_commit": manifest["definition_commit"],
        "code_commit": manifest["code_commit"],
        "candidate_freeze_commit": manifest["candidate_freeze_commit"],
        "schedule_sha256": schedule["schedule_sha256"],
        "attempted_schedule_entries": len(terminal_records),
        "one_attempt_coverage": len({row["schedule_index"] for row in terminal_records}) == 96,
        "by_configuration": summaries,
        "by_family": by_family,
        "paired_discordant": {"C1_success_C0_not": c1_wins, "C0_success_C1_not": c0_wins},
        "c0_to_c1_transition_matrix": dict(sorted(transitions.items())),
        "delta_verified_success": summaries["C1"]["verified_success_count"] - summaries["C0"]["verified_success_count"],
        "hp1a_result_label": label,
        "terra_reference_conclusion": terra,
        "provider_cost_usd": "Unknown",
        "monetary_lifecycle_cost_advantage": "Not established",
        "invalid_attempts": [],
    }
    write_json_new(run_root / "results.json", results)
    runtime_ledger = {
        "schema_version": 1,
        "ledger": "runtime-measured-blind-only",
        "provider_id": "openai",
        "execution_surface": "codex-cli",
        "authentication_mode": "chatgpt",
        "billing_mode": "chatgpt-subscription",
        "api_key_fallback": "prohibited",
        "provider_cost_usd": "Unknown",
        "by_configuration": summaries,
        "total_luna_calls": summaries["C0"]["model_calls"] + summaries["C1"]["model_calls"],
        "total_terra_calls": summaries["C2"]["model_calls"],
        "total_model_calls": sum(summary["model_calls"] for summary in summaries.values()),
        "retry_count": 0,
        "recovery_count": 0,
        "routing": "none",
        "escalation": "none",
        "design_time_usage_included": False,
    }
    write_json_new(run_root / "runtime-ledger.json", runtime_ledger)
    interpretation = (
        "# H-P1a blind interpretation\n\n"
        f"Result: **{label}**\n\n"
        f"C0 verified success: {summaries['C0']['verified_success_count']}/32. "
        f"C1 verified success: {summaries['C1']['verified_success_count']}/32. "
        f"Delta: {results['delta_verified_success']}.\n\n"
        f"Terra reference: **{terra}** C2 verified success was "
        f"{summaries['C2']['verified_success_count']}/32. This is a bounded finite-sample "
        "reference, not model equivalence or a second H-P1 treatment.\n\n"
        "Provider monetary cost is `Unknown`; monetary lifecycle-cost advantage is `Not established`. "
        "Design-time and blind runtime ledgers remain separate.\n"
    )
    write_bytes_new(run_root / "interpretation.md", interpretation.encode("utf-8"))
    write_json_new(
        run_root / "completion-manifest.json",
        {
            "schema_version": 1,
            "status": "complete-valid-blind-run",
            "completed_at_utc": utc_now(),
            "definition_commit": manifest["definition_commit"],
            "code_commit": manifest["code_commit"],
            "candidate_freeze_commit": manifest["candidate_freeze_commit"],
            "terminal_records_sha256": sha_bytes(terminal_path.read_bytes()),
            "results_sha256": sha_bytes(canonical_bytes(results)),
            "schedule_entries": 96,
            "attempted_entries": 96,
            "luna_calls": runtime_ledger["total_luna_calls"],
            "terra_calls": runtime_ledger["total_terra_calls"],
            "subscription_limit_events": sum(row["terminal_event"] == "subscription_limit_event" for row in terminal_records),
            "hp1a_result_label": label,
        },
    )
    print(
        f"blind complete: {label}; C0={summaries['C0']['verified_success_count']}; "
        f"C1={summaries['C1']['verified_success_count']}; C2={summaries['C2']['verified_success_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

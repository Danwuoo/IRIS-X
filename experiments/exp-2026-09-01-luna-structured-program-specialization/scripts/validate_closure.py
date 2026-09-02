#!/usr/bin/env python3
"""Reconstruct the complete Phase 4 H-P1a result and preservation boundary."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

from common import (
    EXPERIMENT,
    FROZEN_INPUTS_PATH,
    ROOT,
    SEED_PROGRAM_PATH,
    canonical_bytes,
    generate_split,
    load_json,
    load_jsonl,
    output_evaluation,
    selection_key,
    sha_bytes,
    summarize_records,
    validate_terminal_semantics,
)


START_COMMIT = "a859399eafb294ea03290123c285c127426dfb5b"
START_SOURCES_TREE = "10e28d83184c789fc468ca1edc3bebf42ba40b46"
START_PAPERS_TREE = "ed29ebcde3f01b00a0e49eb33eef1688566dcad3"
ORIGINAL_DRY_RUN = "experiments/substrates/model-specialization-v0/runs/dry-run-20260901-local-01"
DESIGN_01_TREE = "653ab82f1eb1a4d8f99e09c50ca54ae25bcb1a98"
DESIGN_02_TREE = "49b98340d2c10951dd04d42c564cec114582dd65"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
OUTCOMES = {"success", "partial", "failure", "unresolved"}
EVIDENCE = {"sufficient", "insufficient", "invalid_binding", "not_assessed", "unresolved"}


def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=check,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_value(*arguments: str) -> str:
    return git(*arguments).stdout.strip()


def require_equal(left: Any, right: Any, label: str) -> None:
    if left != right:
        raise AssertionError(f"{label}: {left!r} != {right!r}")


def require_commit(value: Any, label: str) -> None:
    if not isinstance(value, str) or not FULL_SHA.fullmatch(value):
        raise AssertionError(f"{label} is not a full commit SHA: {value!r}")
    if git("cat-file", "-e", f"{value}^{{commit}}", check=False).returncode != 0:
        raise AssertionError(f"{label} does not resolve to a commit: {value}")


def require_commit_fields(records: Iterable[dict[str, Any]], source: str) -> int:
    count = 0
    for index, record in enumerate(records, start=1):
        for field in ("definition_commit", "code_commit", "candidate_freeze_commit", "admission_commit"):
            if field in record:
                require_commit(record[field], f"{source}[{index}].{field}")
                count += 1
    return count


def reproduce(inventory_path: Path) -> dict[str, Any]:
    inventory = load_json(inventory_path)
    with tempfile.TemporaryDirectory(prefix=f"irisx-close-{inventory['split']}-") as temporary:
        reproduced = generate_split(
            inventory["split"],
            inventory["master_seed_hex"],
            inventory["per_family"],
            Path(temporary) / inventory["split"],
            inventory["candidate_freeze_sha"],
            inventory["definition_commit"],
            inventory["code_commit"],
            inventory.get("candidate_freeze_commit"),
        )
    require_equal(reproduced, inventory, f"{inventory['split']} generation")
    if not all(bool(value) for value in inventory["audit"].values()):
        raise AssertionError(f"{inventory['split']} audit failed: {inventory['audit']}")
    return inventory


def enriched_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarize_records(records)
    summary.update(
        {
            "actual_outcome_distribution": dict(
                sorted(collections.Counter(row["actual_outcome"] for row in records).items())
            ),
            "evidence_status_distribution": dict(
                sorted(collections.Counter(row["empirical_evidence_status"] for row in records).items())
            ),
            "acceptance_distribution": dict(
                sorted(collections.Counter(row["acceptance_decision"] for row in records).items())
            ),
            "terminal_status_distribution": dict(
                sorted(collections.Counter(row["terminal_execution_status"] for row in records).items())
            ),
            "terminal_event_distribution": dict(
                sorted(collections.Counter(row["terminal_event"] for row in records).items())
            ),
            "invalid_binding_count": sum(
                row["empirical_evidence_status"] == "invalid_binding" for row in records
            ),
        }
    )
    return summary


def hp1a_label(c0: dict[str, Any], c1: dict[str, Any]) -> str:
    gain = c1["verified_success_count"] - c0["verified_success_count"]
    worse = (
        c1["false_success_count"] > c0["false_success_count"]
        or c1["malformed_output_count"] > c0["malformed_output_count"]
        or c1["invalid_terminal_count"] > c0["invalid_terminal_count"]
    )
    if gain > 0 and not worse:
        return "Supported — task-local"
    if gain < 0 or (gain > 0 and worse):
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


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserve_starting_runs() -> int:
    names = git_value("ls-tree", "-r", "--name-only", START_COMMIT, "experiments").splitlines()
    run_dirs = set()
    for name in names:
        parts = name.split("/")
        if "runs" in parts:
            index = parts.index("runs")
            if len(parts) > index + 1:
                run_dirs.add("/".join(parts[: index + 2]))
    for run_dir in sorted(run_dirs):
        if git("diff", "--quiet", START_COMMIT, "--", run_dir, check=False).returncode != 0:
            raise AssertionError(f"pre-existing run changed: {run_dir}")
    return len(run_dirs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design-run-id", required=True)
    parser.add_argument("--blind-run-id", required=True)
    args = parser.parse_args()

    design = EXPERIMENT / "design" / args.design_run_id
    blind = EXPERIMENT / "runs" / args.blind_run_id
    design_manifest = load_json(design / "run-manifest.json")
    blind_manifest = load_json(blind / "run-manifest.json")
    completion = load_json(blind / "completion-manifest.json")
    c1_freeze = load_json(design / "c1-freeze" / "c1-freeze.json")
    schedule = load_json(blind / "schedule.json")
    results = load_json(blind / "results.json")
    design_ledger = load_json(design / "design-ledger.json")
    runtime_ledger = load_json(blind / "runtime-ledger.json")

    commit_field_count = require_commit_fields(
        [design_manifest, blind_manifest, completion, c1_freeze, schedule, results, design_ledger],
        "manifests",
    )

    inventories = [
        reproduce(FROZEN_INPUTS_PATH / "dev" / "inventory.json"),
        reproduce(FROZEN_INPUTS_PATH / "validation" / "inventory.json"),
        reproduce(blind / "blind-generation" / "inventory.json"),
    ]
    for field in ("generation_seed", "instance_id", "public_input_hash"):
        values = [{row[field] for row in inventory["records"]} for inventory in inventories]
        if any(values[left] & values[right] for left in range(3) for right in range(left + 1, 3)):
            raise AssertionError(f"split overlap: {field}")
    cross_split = load_json(blind / "blind-generation" / "cross-split-audit.json")
    require_equal(cross_split, {"passed": True, "overlaps": []}, "cross-split audit")

    seed = SEED_PROGRAM_PATH.read_bytes()
    c1 = (design / "c1-freeze" / "c1-program.txt").read_bytes()
    require_equal(sha_bytes(seed), blind_manifest["c0_c2_seed_sha256"], "C0/C2 seed SHA")
    require_equal(sha_bytes(c1), c1_freeze["candidate_sha256"], "C1 SHA")
    require_equal(len(seed), 1389, "seed bytes")
    require_equal(len(c1), 2764, "C1 bytes")

    dev = load_jsonl(design / "dev-terminal-records.jsonl")
    optimizer = load_jsonl(design / "optimizer-terminal-records.jsonl")
    validation = load_jsonl(design / "validation-terminal-records.jsonl")
    require_equal((len(dev), len(optimizer), len(validation)), (168, 6, 112), "design record counts")
    require_equal(sum(row["model_calls"] for row in dev + validation), 280, "design Luna calls")
    require_equal(sum(row["model_calls"] for row in optimizer), 6, "optimizer Terra calls")
    commit_field_count += require_commit_fields(dev + optimizer + validation, "design terminals")

    grouped_validation: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in validation:
        grouped_validation[row["candidate_id"]].append(row)
    eligible = []
    candidate_shas = set()
    for candidate_id, rows in grouped_validation.items():
        if candidate_id == "seed":
            continue
        program = (design / "candidates" / f"{candidate_id}.txt").read_bytes()
        candidate_sha = sha_bytes(program)
        candidate_shas.add(candidate_sha)
        eligible.append((selection_key(summarize_records(rows), program, candidate_sha), candidate_id, candidate_sha))
    eligible.sort()
    require_equal(len(eligible), 6, "eligible candidate count")
    require_equal(len(candidate_shas), 6, "unique candidate SHA count")
    require_equal(eligible[0][1], c1_freeze["selected_candidate_id"], "selected candidate")
    require_equal(eligible[0][2], c1_freeze["candidate_sha256"], "selected candidate SHA")

    stored_schedule_hash = schedule["schedule_sha256"]
    schedule_without_hash = dict(schedule)
    schedule_without_hash.pop("schedule_sha256")
    require_equal(sha_bytes(canonical_bytes(schedule_without_hash)), stored_schedule_hash, "schedule SHA")
    entries = schedule["entries"]
    require_equal(len(entries), 96, "schedule entry count")
    require_equal(
        collections.Counter(entry["configuration_id"] for entry in entries),
        collections.Counter({"C0": 32, "C1": 32, "C2": 32}),
        "schedule configuration counts",
    )

    attempts = load_jsonl(blind / "raw" / "attempt-progress.jsonl")
    terminals = load_jsonl(blind / "raw" / "terminal-records.jsonl")
    output_freeze = load_json(blind / "raw" / "blind-output-freeze.json")
    require_equal(len(attempts), 96, "attempt count")
    require_equal(len(terminals), 96, "terminal count")
    require_equal(len(output_freeze["records"]), 96, "output-freeze count")
    require_equal([row["schedule_index"] for row in attempts], list(range(1, 97)), "attempt order")
    require_equal([row["schedule_index"] for row in terminals], list(range(1, 97)), "terminal order")
    commit_field_count += require_commit_fields(attempts + terminals, "blind records")

    instances = {
        path.stem: load_json(path)
        for path in (blind / "blind-generation" / "instances").glob("*.json")
    }
    for entry, attempt, terminal, frozen in zip(
        entries, attempts, terminals, output_freeze["records"], strict=True
    ):
        index = entry["schedule_index"]
        require_equal(index, attempt["schedule_index"], f"attempt schedule {index}")
        require_equal(index, terminal["schedule_index"], f"terminal schedule {index}")
        require_equal(index, frozen["schedule_index"], f"freeze schedule {index}")
        for field in ("configuration_id", "instance_id", "family_id", "model_id"):
            require_equal(entry[field], attempt[field], f"attempt {index} {field}")
            require_equal(entry[field], terminal[field], f"terminal {index} {field}")
        require_equal(entry["program_sha256"], terminal["candidate_sha256"], f"candidate SHA {index}")
        require_equal(frozen["output_sha256"], attempt["output_sha256"], f"output freeze {index}")
        require_equal(
            frozen["raw_event_stream_sha256"],
            attempt["raw_event_stream_sha256"],
            f"event freeze {index}",
        )
        validate_terminal_semantics(terminal)
        if terminal["actual_outcome"] not in OUTCOMES:
            raise AssertionError(f"noncanonical outcome at {index}: {terminal['actual_outcome']}")
        if terminal["empirical_evidence_status"] not in EVIDENCE:
            raise AssertionError(
                f"noncanonical evidence at {index}: {terminal['empirical_evidence_status']}"
            )
        expected = {
            "provider_id": "openai",
            "execution_surface": "codex-cli",
            "authentication_mode": "chatgpt",
            "billing_mode": "chatgpt-subscription",
            "api_key_fallback": "prohibited",
            "provider_cost_usd": "Unknown",
            "reasoning_effort": "medium",
            "retry_count": 0,
            "recovery_count": 0,
            "routing": "none",
            "escalation": "none",
            "tool_calls": 0,
            "terminal_execution_status": "completed",
            "terminal_event": "completed",
            "model_calls": 1,
        }
        for field, value in expected.items():
            require_equal(terminal[field], value, f"terminal {index} {field}")
        require_equal(
            terminal["authentication_status_observed"],
            "Logged in using ChatGPT",
            f"terminal {index} auth status",
        )
        artifact_dir = (
            blind
            / "raw"
            / "invocations"
            / f"{index:03d}-{entry['configuration_id']}-{entry['instance_id']}"
        )
        require_equal(hash_file(artifact_dir / "output.json"), attempt["output_sha256"], f"raw output {index}")
        require_equal(
            hash_file(artifact_dir / "events.jsonl"),
            attempt["raw_event_stream_sha256"],
            f"raw events {index}",
        )
        require_equal(hash_file(artifact_dir / "stderr.txt"), attempt["stderr_sha256"], f"stderr {index}")
        invocation_record = load_json(artifact_dir / "invocation-record.json")
        require_equal(
            invocation_record,
            {key: attempt[key] for key in invocation_record},
            f"invocation record {index}",
        )
        evaluation = output_evaluation(
            instances[entry["instance_id"]], (artifact_dir / "output.json").read_bytes()
        )
        for field, value in evaluation.items():
            require_equal(terminal[field], value, f"re-evaluation {index} {field}")

    by_configuration = {
        configuration_id: [
            row for row in terminals if row["configuration_id"] == configuration_id
        ]
        for configuration_id in ("C0", "C1", "C2")
    }
    summaries = {
        configuration_id: enriched_summary(rows)
        for configuration_id, rows in by_configuration.items()
    }
    for configuration_id, summary in summaries.items():
        require_equal(
            summary,
            results["by_configuration"][configuration_id],
            f"{configuration_id} result summary",
        )
        require_equal(
            summary,
            runtime_ledger["by_configuration"][configuration_id],
            f"{configuration_id} runtime ledger",
        )
    by_family = {
        configuration_id: {
            family_id: enriched_summary(
                [row for row in rows if row["family_id"] == family_id]
            )
            for family_id in sorted({row["family_id"] for row in rows})
        }
        for configuration_id, rows in by_configuration.items()
    }
    require_equal(by_family, results["by_family"], "family results")

    paired = {
        configuration_id: {row["instance_id"]: row for row in rows}
        for configuration_id, rows in by_configuration.items()
    }
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
    require_equal(
        {"C1_success_C0_not": c1_wins, "C0_success_C1_not": c0_wins},
        results["paired_discordant"],
        "paired discordance",
    )
    transitions = collections.Counter()
    for instance_id in sorted(paired["C0"]):
        left = paired["C0"][instance_id]
        right = paired["C1"][instance_id]
        transitions[
            f"{left['actual_outcome']}/{left['empirical_evidence_status']} -> "
            f"{right['actual_outcome']}/{right['empirical_evidence_status']}"
        ] += 1
    require_equal(dict(sorted(transitions.items())), results["c0_to_c1_transition_matrix"], "transitions")
    require_equal(hp1a_label(summaries["C0"], summaries["C1"]), results["hp1a_result_label"], "H-P1a label")
    require_equal(terra_reference(summaries["C1"], summaries["C2"]), results["terra_reference_conclusion"], "Terra reference")

    require_equal(runtime_ledger["total_luna_calls"], 64, "runtime Luna calls")
    require_equal(runtime_ledger["total_terra_calls"], 32, "runtime Terra calls")
    require_equal(runtime_ledger["total_model_calls"], 96, "runtime total calls")
    require_equal(design_ledger["luna_calls"], 280, "ledger design Luna calls")
    require_equal(design_ledger["terra_optimizer_calls"], 6, "ledger optimizer calls")
    require_equal(design_ledger["total_model_calls"], 286, "ledger design total calls")
    require_equal(
        (
            design_ledger["luna_calls"] + runtime_ledger["total_luna_calls"],
            design_ledger["terra_optimizer_calls"] + runtime_ledger["total_terra_calls"],
            design_ledger["total_model_calls"] + runtime_ledger["total_model_calls"],
        ),
        (344, 38, 382),
        "combined call ceiling",
    )
    require_equal(
        sha_bytes((blind / "raw" / "terminal-records.jsonl").read_bytes()),
        completion["terminal_records_sha256"],
        "terminal-record file SHA",
    )
    require_equal(sha_bytes(canonical_bytes(results)), completion["results_sha256"], "results SHA")
    if (blind / "subscription-pause.json").exists() or (blind / "invalid-run.json").exists():
        raise AssertionError("unexpected subscription pause or invalid-run marker")

    qualification = EXPERIMENT.parents[0] / "substrates" / "model-specialization-v0" / "runs" / "qualification-20260901-local-02"
    qualification_records = load_jsonl(qualification / "terminal-records.jsonl")
    for row in qualification_records:
        if row["actual_outcome"] not in OUTCOMES or row["empirical_evidence_status"] not in EVIDENCE:
            raise AssertionError("new fake qualification uses noncanonical vocabulary")

    require_equal(git_value("rev-parse", "HEAD:sources"), START_SOURCES_TREE, "sources tree")
    require_equal(git_value("rev-parse", "HEAD:references/papers"), START_PAPERS_TREE, "papers tree")
    if git("diff", "--quiet", "HEAD", "--", "sources", "references/papers", check=False).returncode != 0:
        raise AssertionError("uncommitted source or paper change")
    if git("diff", "--cached", "--quiet", "HEAD", "--", "sources", "references/papers", check=False).returncode != 0:
        raise AssertionError("staged source or paper change")
    historical_run_count = preserve_starting_runs()
    if git("diff", "--quiet", START_COMMIT, "--", ORIGINAL_DRY_RUN, check=False).returncode != 0:
        raise AssertionError("original specialization dry-run changed")
    require_equal(
        git_value(
            "rev-parse",
            "HEAD:experiments/exp-2026-09-01-luna-structured-program-specialization/design/design-20260901-chatgpt-01",
        ),
        DESIGN_01_TREE,
        "design attempt 01 tree",
    )
    require_equal(
        git_value(
            "rev-parse",
            "HEAD:experiments/exp-2026-09-01-luna-structured-program-specialization/design/design-20260901-chatgpt-02",
        ),
        DESIGN_02_TREE,
        "design attempt 02 tree",
    )

    print("PHASE4_CLOSURE_RECONSTRUCTION_PASS")
    print(
        f"splits=24/16/32; candidates=6 unique; blind=96 exactly once; "
        f"commit_fields={commit_field_count} full/resolved"
    )
    print(
        f"C0={summaries['C0']['verified_success_count']}/32; "
        f"C1={summaries['C1']['verified_success_count']}/32; "
        f"C2={summaries['C2']['verified_success_count']}/32; "
        f"paired_wins={len(c1_wins)}; paired_losses={len(c0_wins)}"
    )
    print(
        "calls Luna=344/344 Terra=38/38 total=382/382; subscription=0; "
        "retry=0; recovery=0; tools=0; provider_cost=Unknown"
    )
    print(
        f"historical_runs={historical_run_count} preserved; sources/papers/original-dry-run/"
        "design-01/design-02 preserved"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PHASE4_CLOSURE_RECONSTRUCTION_FAIL: {error}", file=sys.stderr)
        raise

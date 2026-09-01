#!/usr/bin/env python3
"""Reconstruct H-P1a identities, generation, selection, coverage, and ledgers."""

from __future__ import annotations

import argparse
import collections
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT,
    ROOT,
    SEED_PROGRAM_PATH,
    canonical_bytes,
    generate_split,
    load_json,
    load_jsonl,
    require_commit,
    selection_key,
    sha_bytes,
    summarize_records,
    validate_terminal_semantics,
)


START_COMMIT = "a859399eafb294ea03290123c285c127426dfb5b"
START_SOURCES_TREE = "10e28d83184c789fc468ca1edc3bebf42ba40b46"
START_PAPERS_TREE = "ed29ebcde3f01b00a0e49eb33eef1688566dcad3"


def git_value(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def assert_equal(left: Any, right: Any, message: str) -> None:
    if left != right:
        raise AssertionError(f"{message}: {left!r} != {right!r}")


def reproduce_split(split_root: Path) -> None:
    inventory = load_json(split_root / "inventory.json")
    with tempfile.TemporaryDirectory(prefix=f"irisx-hp1a-reproduce-{inventory['split']}-") as temporary:
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
    assert_equal(reproduced, inventory, f"{inventory['split']} generation reproduction")


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
        result = subprocess.run(
            ["git", "diff", "--quiet", START_COMMIT, "--", run_dir], cwd=ROOT, check=False
        )
        if result.returncode != 0:
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
    for manifest in (design_manifest, blind_manifest):
        require_commit(manifest["definition_commit"], "definition_commit")
        require_commit(manifest["code_commit"], "code_commit")
        assert_equal(manifest["authentication_mode"], "chatgpt", "authentication mode")
        assert_equal(manifest["billing_mode"], "chatgpt-subscription", "billing mode")
        assert_equal(manifest["provider_cost_usd"], "Unknown", "provider cost")
    reproduce_split(EXPERIMENT / "inputs" / "dev")
    reproduce_split(EXPERIMENT / "inputs" / "validation")
    reproduce_split(blind / "blind-generation")
    inventories = [
        load_json(EXPERIMENT / "inputs" / "dev" / "inventory.json"),
        load_json(EXPERIMENT / "inputs" / "validation" / "inventory.json"),
        load_json(blind / "blind-generation" / "inventory.json"),
    ]
    for field in ("generation_seed", "instance_id", "public_input_hash"):
        sets = [{row[field] for row in inventory["records"]} for inventory in inventories]
        if any(sets[i] & sets[j] for i in range(3) for j in range(i + 1, 3)):
            raise AssertionError(f"split overlap for {field}")
    seed = SEED_PROGRAM_PATH.read_bytes()
    c1 = (design / "c1-freeze" / "c1-program.txt").read_bytes()
    c1_freeze = load_json(design / "c1-freeze" / "c1-freeze.json")
    assert_equal(sha_bytes(seed), blind_manifest["c0_c2_seed_sha256"], "C0/C2 seed identity")
    assert_equal(sha_bytes(c1), c1_freeze["candidate_sha256"], "C1 identity")
    schedule = load_json(blind / "schedule.json")
    stored_schedule_hash = schedule.pop("schedule_sha256")
    assert_equal(sha_bytes(canonical_bytes(schedule)), stored_schedule_hash, "schedule hash")
    schedule["schedule_sha256"] = stored_schedule_hash
    terminal = load_jsonl(blind / "raw" / "terminal-records.jsonl")
    assert_equal(len(terminal), 96, "terminal coverage")
    assert_equal(sorted(row["schedule_index"] for row in terminal), list(range(1, 97)), "schedule indices")
    for row in terminal:
        validate_terminal_semantics(row)
        assert_equal(row["authentication_mode"], "chatgpt", "terminal auth")
        assert_equal(row["billing_mode"], "chatgpt-subscription", "terminal billing")
        assert_equal(row["provider_cost_usd"], "Unknown", "terminal provider cost")
        assert_equal(row["retry_count"], 0, "retry count")
        assert_equal(row["recovery_count"], 0, "recovery count")
        assert_equal(row["routing"], "none", "routing")
        assert_equal(row["escalation"], "none", "escalation")
    design_ledger = load_json(design / "design-ledger.json")
    runtime_ledger = load_json(blind / "runtime-ledger.json")
    luna_calls = design_ledger["luna_calls"] + runtime_ledger["total_luna_calls"]
    terra_calls = design_ledger["terra_optimizer_calls"] + runtime_ledger["total_terra_calls"]
    total_calls = design_ledger["total_model_calls"] + runtime_ledger["total_model_calls"]
    if luna_calls > 344 or terra_calls > 38 or total_calls > 382:
        raise AssertionError("model call ceiling exceeded")
    validation = load_jsonl(design / "validation-terminal-records.jsonl")
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in validation:
        grouped[row["candidate_id"]].append(row)
    eligible = []
    for candidate_id, rows in grouped.items():
        if candidate_id == "seed":
            continue
        program = (design / "candidates" / f"{candidate_id}.txt").read_bytes()
        summary = summarize_records(rows)
        candidate_sha = sha_bytes(program)
        eligible.append((selection_key(summary, program, candidate_sha), candidate_id, candidate_sha))
    eligible.sort()
    assert_equal(eligible[0][1], c1_freeze["selected_candidate_id"], "selected candidate")
    assert_equal(eligible[0][2], c1_freeze["candidate_sha256"], "selected candidate SHA")
    assert_equal(git_value("rev-parse", "HEAD:sources"), START_SOURCES_TREE, "sources preservation")
    assert_equal(git_value("rev-parse", "HEAD:references/papers"), START_PAPERS_TREE, "papers preservation")
    historical_run_count = preserve_starting_runs()
    print(
        "H-P1a validation: PASS "
        f"(96 blind entries; {total_calls} total calls reconstructed; {historical_run_count} starting runs preserved)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

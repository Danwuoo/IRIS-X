#!/usr/bin/env python3
"""Generate, audit, and authorize the post-C1-freeze H-P1a blind schedule."""

from __future__ import annotations

import argparse
import hashlib
import secrets
import subprocess
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT,
    FROZEN_INPUTS_PATH,
    SEED_PROGRAM_PATH,
    canonical_bytes,
    generate_split,
    load_json,
    require_commit,
    sha_bytes,
    utc_now,
    write_json_new,
)


def committed_bytes(commit: str, path: Path) -> bytes:
    relative = path.relative_to(EXPERIMENT.parents[1]).as_posix()
    return subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=EXPERIMENT.parents[1],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def cross_split_audit(blind_inventory: dict[str, Any]) -> dict[str, Any]:
    inventories = {
        "dev": load_json(FROZEN_INPUTS_PATH / "dev" / "inventory.json"),
        "validation": load_json(FROZEN_INPUTS_PATH / "validation" / "inventory.json"),
        "blind": blind_inventory,
    }
    dimensions = {
        "generation_seed": {},
        "instance_id": {},
        "public_input_hash": {},
    }
    for field, split_values in dimensions.items():
        for split, inventory in inventories.items():
            split_values[split] = {row[field] for row in inventory["records"]}
    overlaps = []
    splits = ("dev", "validation", "blind")
    for field, split_values in dimensions.items():
        for left_index, left in enumerate(splits):
            for right in splits[left_index + 1 :]:
                shared = sorted(split_values[left] & split_values[right])
                if shared:
                    overlaps.append({"field": field, "left": left, "right": right, "values": shared})
    return {"passed": not overlaps, "overlaps": overlaps}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--definition-commit", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--candidate-freeze-commit", required=True)
    parser.add_argument("--design-run-id", required=True)
    args = parser.parse_args()
    require_commit(args.definition_commit, "definition_commit")
    require_commit(args.code_commit, "code_commit")
    require_commit(args.candidate_freeze_commit, "candidate_freeze_commit")
    run_root = EXPERIMENT / "runs" / args.run_id
    if run_root.exists():
        raise FileExistsError(f"blind run already exists: {run_root}")
    design_root = EXPERIMENT / "design" / args.design_run_id
    c1_path = design_root / "c1-freeze" / "c1-program.txt"
    c1_freeze_path = design_root / "c1-freeze" / "c1-freeze.json"
    c1 = c1_path.read_bytes()
    c1_freeze = load_json(c1_freeze_path)
    if sha_bytes(c1) != c1_freeze["candidate_sha256"]:
        raise ValueError("current C1 bytes do not match the design freeze")
    if committed_bytes(args.candidate_freeze_commit, c1_path) != c1:
        raise ValueError("candidate-freeze commit does not contain the current C1 bytes")
    seed = SEED_PROGRAM_PATH.read_bytes()
    seed_sha = sha_bytes(seed)
    master_seed = secrets.token_hex(32)
    blind_root = run_root / "blind-generation"
    inventory = generate_split(
        "blind",
        master_seed,
        8,
        blind_root,
        c1_freeze["candidate_sha256"],
        args.definition_commit,
        args.code_commit,
        args.candidate_freeze_commit,
    )
    split_audit = cross_split_audit(inventory)
    if not split_audit["passed"]:
        write_json_new(run_root / "blind-generation" / "cross-split-audit.json", split_audit)
        raise ValueError("blind split collides with DEV or validation")
    write_json_new(run_root / "blind-generation" / "cross-split-audit.json", split_audit)
    records = inventory["records"]
    sorted_records = sorted(
        records,
        key=lambda row: hashlib.sha256(bytes.fromhex(master_seed) + row["instance_id"].encode("utf-8")).hexdigest(),
    )
    rotations = (("C0", "C1", "C2"), ("C1", "C2", "C0"), ("C2", "C0", "C1"))
    schedule = []
    schedule_index = 1
    for task_index, record in enumerate(sorted_records):
        for configuration_id in rotations[task_index % 3]:
            program_sha = c1_freeze["candidate_sha256"] if configuration_id == "C1" else seed_sha
            schedule.append(
                {
                    "schedule_index": schedule_index,
                    "task_order_index": task_index + 1,
                    "configuration_id": configuration_id,
                    "model_id": "gpt-5.6-terra" if configuration_id == "C2" else "gpt-5.6-luna",
                    "model_role": "strong" if configuration_id == "C2" else "cheaper",
                    "program_sha256": program_sha,
                    "instance_id": record["instance_id"],
                    "family_id": record["family_id"],
                    "public_input_hash": record["public_input_hash"],
                    "attempt_limit": 1,
                    "retry_count": 0,
                    "recovery_count": 0,
                    "routing": "none",
                    "escalation": "none",
                }
            )
            schedule_index += 1
    schedule_value = {
        "schema_version": 1,
        "run_id": args.run_id,
        "definition_commit": args.definition_commit,
        "code_commit": args.code_commit,
        "candidate_freeze_commit": args.candidate_freeze_commit,
        "master_blind_seed_hex": master_seed,
        "algorithm": "sort-sha256(master-seed-bytes||instance-id)-rotate-configurations-by-zero-based-task-index-mod-3",
        "entry_count": len(schedule),
        "entries": schedule,
    }
    schedule_hash = sha_bytes(canonical_bytes(schedule_value))
    schedule_value["schedule_sha256"] = schedule_hash
    write_json_new(run_root / "schedule.json", schedule_value)
    write_json_new(
        run_root / "run-manifest.json",
        {
            "schema_version": 1,
            "experiment_id": "exp-2026-09-01-luna-structured-program-specialization",
            "run_id": args.run_id,
            "status": "blind-authorized",
            "authorized_at_utc": utc_now(),
            "definition_commit": args.definition_commit,
            "code_commit": args.code_commit,
            "candidate_freeze_commit": args.candidate_freeze_commit,
            "design_run_id": args.design_run_id,
            "c1_candidate_id": c1_freeze["selected_candidate_id"],
            "c1_sha256": c1_freeze["candidate_sha256"],
            "c1_bytes": len(c1),
            "c0_c2_seed_sha256": seed_sha,
            "c0_c2_seed_byte_identical": True,
            "blind_inventory_records_sha256": inventory["records_sha256"],
            "blind_instance_count": inventory["total_instances"],
            "cross_split_audit": split_audit,
            "schedule_sha256": schedule_hash,
            "schedule_entries": len(schedule),
            "provider_id": "openai",
            "execution_surface": "codex-cli",
            "authentication_mode": "chatgpt",
            "billing_mode": "chatgpt-subscription",
            "api_key_fallback": "prohibited",
            "provider_cost_usd": "Unknown",
            "retries": 0,
            "recovery": 0,
            "routing": "none",
            "escalation": "none",
        },
    )
    write_json_new(
        run_root / "blind-authorization.json",
        {
            "authorized": True,
            "authorized_before_model_calls": True,
            "all_32_slots_valid": inventory["total_instances"] == 32,
            "all_generation_attempts_once": inventory["audit"]["all_generation_attempts_once"],
            "leakage_audit_passed": inventory["audit"]["leakage"],
            "cross_split_audit_passed": split_audit["passed"],
            "schedule_entries": len(schedule),
            "schedule_sha256": schedule_hash,
            "candidate_modification_prohibited": True,
        },
    )
    print(f"blind authorized: 32 instances; 96 entries; schedule={schedule_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Qualify generated task families with development-visible seeds only."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import generator


ROOT = Path(__file__).resolve().parents[4]
SUBSTRATE = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = SUBSTRATE / "inputs" / "qualification-protocol.json"
RUNS = SUBSTRATE / "runs"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def qualify_family(
    family_id: str,
    seeds: list[int],
    protocol: dict[str, Any],
    generator_sha: str,
) -> dict[str, Any]:
    if len(seeds) < 2 or len(set(seeds)) != len(seeds):
        raise ValueError(f"{family_id}: at least two distinct qualification seeds required")
    instances = [
        generator.generate_instance(
            family_id,
            seed,
            protocol["candidate_freeze_sha"],
            generator_sha,
            protocol["generator_config"],
        )
        for seed in seeds
    ]
    repeated = generator.generate_instance(
        family_id,
        seeds[0],
        protocol["candidate_freeze_sha"],
        generator_sha,
        protocol["generator_config"],
    )
    same_seed_reproducible = instances[0] == repeated
    distinct = len({instance["manifest"]["public_input_hash"] for instance in instances}) == len(instances)
    instance_records = []
    for instance in instances:
        visible = generator.candidate_visible_bundle(instance)
        oracle_first = generator.oracle_from_hidden_state(
            family_id, instance["hidden_generation_state"]
        )
        oracle_second = generator.oracle_from_hidden_state(
            family_id, instance["hidden_generation_state"]
        )
        public_solution = generator.solve_from_public(family_id, visible["public_input"])
        audit = generator.leakage_audit(visible, instance)
        instance_records.append(
            {
                **instance["manifest"],
                "evidence_class": protocol["evidence_class"],
                "same_seed_reproducible": same_seed_reproducible,
                "different_seed_variation": distinct,
                "oracle_deterministic": oracle_first == oracle_second == instance["hidden_oracle"],
                "public_input_sufficient": public_solution == instance["hidden_oracle"],
                "hidden_oracle_separated": "hidden_oracle" not in visible,
                "leakage_audit": audit,
                "candidate_executed": False,
                "model_calls": 0,
                "paid_api_calls": 0,
            }
        )
    qualified = all(
        record["same_seed_reproducible"]
        and record["different_seed_variation"]
        and record["oracle_deterministic"]
        and record["public_input_sufficient"]
        and record["hidden_oracle_separated"]
        and record["leakage_audit"]["passed"]
        for record in instance_records
    )
    return {
        "family_id": family_id,
        "qualified": qualified,
        "qualification_seed_count": len(seeds),
        "records": instance_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_root = RUNS / args.run_id
    if run_root.exists():
        raise ValueError(f"run directory already exists: {run_root}")
    protocol = load_json(PROTOCOL_PATH)
    if protocol["evidence_class"] != "development-visible":
        raise ValueError("qualification seeds must remain development-visible")
    if protocol["future_blind_set_materialized"] is not False:
        raise ValueError("qualification must not materialize future blind set")
    generator_path = Path(generator.__file__)
    generator_sha = sha_bytes(generator_path.read_bytes())
    families = [
        qualify_family(family_id, seeds, protocol, generator_sha)
        for family_id, seeds in protocol["families"].items()
    ]
    invalid_rejected = False
    invalid_reason = None
    try:
        generator.generate_instance(
            generator.FAMILIES[0],
            9999,
            protocol["candidate_freeze_sha"],
            generator_sha,
            protocol["invalid_config_self_test"],
        )
    except ValueError as exc:
        invalid_rejected = True
        invalid_reason = str(exc)
    flat_records = [record for family in families for record in family["records"]]
    passed = all(family["qualified"] for family in families) and invalid_rejected
    run_root.mkdir(parents=True)
    raw_path = run_root / "qualification-records.jsonl"
    raw_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in flat_records
        ),
        encoding="utf-8",
        newline="\n",
    )
    results = {
        "schema_version": 1,
        "substrate_id": protocol["substrate_id"],
        "status": "qualified" if passed else "not_qualified",
        "evidence_class": protocol["evidence_class"],
        "qualified_families": [family["family_id"] for family in families if family["qualified"]],
        "qualified_family_count": sum(family["qualified"] for family in families),
        "attempted_family_count": len(families),
        "qualification_instance_count": len(flat_records),
        "same_seed_reproducibility_passed": all(record["same_seed_reproducible"] for record in flat_records),
        "different_seed_variation_passed": all(record["different_seed_variation"] for record in flat_records),
        "oracle_determinism_passed": all(record["oracle_deterministic"] for record in flat_records),
        "public_input_sufficiency_passed": all(record["public_input_sufficient"] for record in flat_records),
        "hidden_oracle_separation_passed": all(record["hidden_oracle_separated"] for record in flat_records),
        "leakage_audit_passed": all(record["leakage_audit"]["passed"] for record in flat_records),
        "invalid_generator_configuration_rejected": invalid_rejected,
        "invalid_generator_configuration_reason": invalid_reason,
        "future_blind_set_materialized": False,
        "candidate_executions": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "uncertainty": {
            "difficulty_calibration": "Unclear",
            "real_world_representativeness": "Unclear",
            "future_candidate_performance": "Not evaluated"
        },
    }
    write_json(run_root / "results.json", results)
    write_json(
        run_root / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": args.run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "code_commit": git_head(),
            "protocol_sha256": sha_bytes(PROTOCOL_PATH.read_bytes()),
            "generator_version_sha256": generator_sha,
            "qualification_runner_sha256": sha_bytes(Path(__file__).read_bytes()),
            "qualification_records_sha256": sha_bytes(raw_path.read_bytes()),
            "qualification_records_bytes": raw_path.stat().st_size,
            "status": results["status"],
            "network_used": False,
            "model_calls": 0,
            "paid_api_calls": 0,
        },
    )
    print(
        f"Generated task substrate: {results['status']} "
        f"({results['qualified_family_count']}/{results['attempted_family_count']} families; "
        f"{len(flat_records)} development-visible qualification instances)"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

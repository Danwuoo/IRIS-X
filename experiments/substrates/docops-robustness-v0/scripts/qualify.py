#!/usr/bin/env python3
"""Qualify deterministic robustness transformations without running candidates."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SUBSTRATE = Path(__file__).resolve().parents[1]
CASES_PATH = SUBSTRATE / "inputs" / "qualification-cases.json"
RUNS = SUBSTRATE / "runs"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def canonical_relative(path: str) -> str:
    candidate = PurePosixPath(path)
    if candidate.is_absolute():
        raise ValueError("absolute paths are not admitted")
    parts: list[str] = []
    for part in candidate.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ValueError("path escapes declared root")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ValueError("empty canonical path is not admitted")
    return "/".join(parts)


def oracle_projection(value: dict[str, Any], transformation_id: str) -> Any:
    if transformation_id in ("irrelevant-context-insertion-v0", "selector-modification-negative-v0"):
        task = value["task"]
        selected = next(row for row in task["records"] if row["id"] == task["selector"])
        return {"selector": task["selector"], "selected": selected}
    if transformation_id == "equivalent-json-serialization-v0":
        return value
    if transformation_id == "order-permutation-under-set-contract-v0":
        return sorted(value["items"], key=lambda row: row["id"])
    if transformation_id == "equivalent-relative-path-presentation-v0":
        return {"path": canonical_relative(value["path"]), "action": value["action"]}
    raise ValueError(f"unknown transformation: {transformation_id}")


def build(case: dict[str, Any]) -> tuple[Any, bytes]:
    source = copy.deepcopy(case["source"])
    transformation_id = case["transformation_id"]
    if transformation_id == "irrelevant-context-insertion-v0":
        transformed = copy.deepcopy(source)
        transformed.setdefault("context", {})["irrelevant"] = case["parameters"]["text"]
        return transformed, canonical_bytes(transformed)
    if transformation_id == "equivalent-json-serialization-v0":
        reordered = {key: source[key] for key in reversed(list(source))}
        payload = json.dumps(
            reordered,
            ensure_ascii=False,
            indent=case["parameters"]["indent"],
        ).encode()
        return json.loads(payload), payload
    if transformation_id == "order-permutation-under-set-contract-v0":
        transformed = copy.deepcopy(source)
        random.Random(case["parameters"]["seed"]).shuffle(transformed["items"])
        if transformed["items"] == source["items"]:
            transformed["items"].reverse()
        return transformed, canonical_bytes(transformed)
    if transformation_id == "equivalent-relative-path-presentation-v0":
        transformed = copy.deepcopy(source)
        transformed["path"] = case["parameters"]["presentation"]
        return transformed, canonical_bytes(transformed)
    if transformation_id == "selector-modification-negative-v0":
        transformed = copy.deepcopy(source)
        transformed["task"]["selector"] = case["parameters"]["new_selector"]
        return transformed, canonical_bytes(transformed)
    raise ValueError(f"unknown transformation: {transformation_id}")


def validate(case: dict[str, Any], transformed: Any) -> dict[str, Any]:
    source = case["source"]
    transformation_id = case["transformation_id"]
    reason = ""
    accepted = False
    if transformation_id == "irrelevant-context-insertion-v0":
        source_projection = copy.deepcopy(source)
        transformed_projection = copy.deepcopy(transformed)
        source_projection.pop("context", None)
        transformed_projection.pop("context", None)
        accepted = (
            source_projection == transformed_projection
            and "irrelevant" in transformed.get("context", {})
        )
        reason = (
            "task projection unchanged and only declared ignored context was inserted"
            if accepted
            else "oracle-relevant task projection changed"
        )
    elif transformation_id == "equivalent-json-serialization-v0":
        accepted = source == transformed
        reason = (
            "independently parsed JSON values are equal"
            if accepted
            else "parsed JSON values differ"
        )
    elif transformation_id == "order-permutation-under-set-contract-v0":
        unique = len({row["id"] for row in source["items"]}) == len(source["items"])
        accepted = (
            source.get("order_semantics") == "set"
            and unique
            and sorted(source["items"], key=lambda row: row["id"])
            == sorted(transformed["items"], key=lambda row: row["id"])
        )
        reason = (
            "unique items equal under declared set semantics"
            if accepted
            else "set-semantics precondition or item identity failed"
        )
    elif transformation_id == "equivalent-relative-path-presentation-v0":
        try:
            accepted = (
                canonical_relative(source["path"]) == canonical_relative(transformed["path"])
                and source["action"] == transformed["action"]
            )
            reason = (
                "relative paths canonicalize to the same in-boundary identity"
                if accepted
                else "canonical path or action differs"
            )
        except ValueError as exc:
            reason = str(exc)
    elif transformation_id == "selector-modification-negative-v0":
        accepted = oracle_projection(source, transformation_id) == oracle_projection(
            transformed, transformation_id
        )
        reason = (
            "oracle-relevant selector projection unchanged"
            if accepted
            else "oracle-relevant selector and selected record changed"
        )
    source_oracle = oracle_projection(source, transformation_id)
    try:
        transformed_oracle = oracle_projection(transformed, transformation_id)
        transformed_oracle_hash: str | None = sha(canonical_bytes(transformed_oracle))
    except ValueError:
        transformed_oracle_hash = None
    return {
        "accepted_as_semantics_preserving": accepted,
        "reason": reason,
        "source_oracle_sha256": sha(canonical_bytes(source_oracle)),
        "transformed_oracle_sha256": transformed_oracle_hash,
    }


def qualify_case(case: dict[str, Any]) -> dict[str, Any]:
    transformed, transformed_bytes = build(case)
    adjudication = validate(case, transformed)
    negative = case["expected_effect"] == "must_reject_semantics_preserving_claim"
    qualified = (
        not adjudication["accepted_as_semantics_preserving"]
        if negative
        else (
            adjudication["accepted_as_semantics_preserving"]
            and adjudication["source_oracle_sha256"]
            == adjudication["transformed_oracle_sha256"]
        )
    )
    return {
        "schema_version": 1,
        "case_id": case["case_id"],
        "transformation_id": case["transformation_id"],
        "precondition": case["precondition"],
        "deterministic_builder": case["builder_id"],
        "seed_or_parameters": case["parameters"],
        "equivalence_validator": case["validator_id"],
        "expected_effect": case["expected_effect"],
        "source_input_sha256": sha(canonical_bytes(case["source"])),
        "transformed_input_sha256": sha(transformed_bytes),
        "validator": adjudication,
        "qualification_passed": qualified,
        "candidate_executed": False,
        "model_calls": 0,
        "paid_api_calls": 0,
    }


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_root = RUNS / args.run_id
    if run_root.exists():
        raise ValueError(f"run directory already exists: {run_root}")
    definition = json_file(CASES_PATH)
    records = [qualify_case(case) for case in definition["cases"]]
    positives = [record for record in records if record["expected_effect"] == "same_oracle"]
    negatives = [record for record in records if record["expected_effect"] != "same_oracle"]
    passed = all(record["qualification_passed"] for record in records)
    run_root.mkdir(parents=True)
    raw_path = run_root / "terminal-records.jsonl"
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
        "substrate_id": definition["substrate_id"],
        "status": "qualified" if passed else "not_qualified",
        "qualified_positive_families": [
            record["transformation_id"]
            for record in positives
            if record["qualification_passed"]
        ],
        "positive_cases_passed": sum(record["qualification_passed"] for record in positives),
        "positive_cases_total": len(positives),
        "negative_sensitivity_cases_rejected": sum(
            record["qualification_passed"] for record in negatives
        ),
        "negative_sensitivity_cases_total": len(negatives),
        "candidate_executions": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "claim_boundary": (
            "Measurement-substrate qualification only; system robustness not established."
        ),
    }
    write_json(run_root / "results.json", results)
    write_json(
        run_root / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": args.run_id,
            "code_commit": git_head(),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "qualification_cases_sha256": sha(CASES_PATH.read_bytes()),
            "runner_sha256": sha(Path(__file__).read_bytes()),
            "terminal_records_sha256": sha(raw_path.read_bytes()),
            "terminal_records_bytes": raw_path.stat().st_size,
            "status": results["status"],
            "network_used": False,
            "model_calls": 0,
            "paid_api_calls": 0,
        },
    )
    print(
        f"Robustness substrate: {results['status']} "
        f"({len(positives)} positive families; {len(negatives)} negative sensitivity case)"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

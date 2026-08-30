#!/usr/bin/env python3
"""Build the deterministic frozen evidence-binding challenges for H-V1b."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ID = "exp-2026-08-30-docops-evidence-binding"
DISTRIBUTION_ID = "taskdist-2026-08-28-vanta-docops-readonly-12"
VARIANT_ORDER = (
    "complete-correct",
    "missing-required-entry",
    "wrong-hash",
    "stale-hash",
    "crossed-evidence",
    "unrelated-existing-file",
    "conflicting-duplicate",
    "correct-hash-wrong-path",
)


class BuildError(ValueError):
    """Raised when deterministic challenge construction cannot be validated."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def resolve_repo_path(value: str, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise BuildError(f"{label} must be a repository-relative path")
    path = (ROOT / value).resolve()
    if ROOT.resolve() not in path.parents:
        raise BuildError(f"{label} escapes repository: {value}")
    return path


def evidence_entry(fixture: Path, relative: str, role: str) -> dict[str, Any]:
    normalized = relative.replace("\\", "/")
    path = (fixture / normalized).resolve()
    if fixture.resolve() not in path.parents or not path.is_file():
        raise BuildError(f"input path missing or escaping fixture: {normalized}")
    payload = path.read_bytes()
    return {
        "path": normalized,
        "role": role,
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
    }


def declared_evidence(fixture: Path, task: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, artifact in enumerate(task.get("input_artifacts", [])):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            raise BuildError(f"{task.get('task_id')}: invalid input_artifacts[{index}]")
        result.append(evidence_entry(fixture, artifact["path"], str(artifact.get("role", "unknown"))))
    if not result:
        raise BuildError(f"{task.get('task_id')}: no declared input artifacts")
    return result


def altered_hash(value: str) -> str:
    return ("1" if value[0] != "1" else "0") + value[1:]


def build_document(manifest_path: Path, stale_fixture: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("distribution_id") != DISTRIBUTION_ID or manifest.get("source_id") != "src.vanta":
        raise BuildError("baseline manifest distribution/source mismatch")
    rows = manifest.get("tasks")
    if not isinstance(rows, list) or len(rows) != 12:
        raise BuildError("baseline manifest must enumerate 12 tasks")
    stale_payload = stale_fixture.read_bytes()
    stale_hash = sha256_bytes(stale_payload)

    task_data: list[dict[str, Any]] = []
    for task_order, row in enumerate(rows, start=1):
        fixture = resolve_repo_path(row.get("fixture_path"), f"tasks[{task_order}].fixture_path")
        task_path = fixture / "task.json"
        expected_path = (fixture / row.get("expected_path", "")).resolve()
        task = json.loads(task_path.read_text(encoding="utf-8"))
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        if task.get("task_id") != row.get("task_id") or not isinstance(expected, dict):
            raise BuildError(f"{row.get('task_id')}: task/oracle identity invalid")
        task_data.append(
            {
                "row": row,
                "fixture": fixture,
                "task": task,
                "task_path": task_path,
                "expected_path": expected_path,
                "expected": expected,
                "complete": declared_evidence(fixture, task),
            }
        )

    cases: list[dict[str, Any]] = []
    fallback_counts = {"multi_input_swap": 0, "single_input_next_task": 0}
    for task_order, item in enumerate(task_data, start=1):
        row = item["row"]
        fixture = item["fixture"]
        complete = item["complete"]
        variants: list[tuple[str, list[dict[str, Any]], str]] = []

        variants.append(("complete-correct", copy.deepcopy(complete), "all declared inputs with actual hashes"))

        missing = copy.deepcopy(complete[:-1])
        variants.append(("missing-required-entry", missing, "omit last declared input by task order"))

        wrong = copy.deepcopy(complete)
        wrong[0]["sha256"] = altered_hash(wrong[0]["sha256"])
        variants.append(("wrong-hash", wrong, "alter first hex digit of first declared input hash"))

        stale = copy.deepcopy(complete)
        stale[0]["sha256"] = stale_hash
        stale[0]["bytes"] = len(stale_payload)
        variants.append(("stale-hash", stale, "use authored deterministic stale fixture hash and size"))

        if len(complete) >= 2:
            crossed = copy.deepcopy(complete)
            crossed[0]["sha256"], crossed[1]["sha256"] = crossed[1]["sha256"], crossed[0]["sha256"]
            crossed[0]["bytes"], crossed[1]["bytes"] = crossed[1]["bytes"], crossed[0]["bytes"]
            cross_note = "swap first two declared input hash/size associations"
            fallback_counts["multi_input_swap"] += 1
        else:
            other = task_data[task_order % len(task_data)]
            crossed_entry = copy.deepcopy(other["complete"][0])
            crossed_entry["path"] = Path(
                os.path.relpath(
                    other["fixture"] / crossed_entry["path"],
                    fixture,
                )
            ).as_posix()
            crossed = [crossed_entry]
            cross_note = "single-input fallback: next task's first input relative to current fixture"
            fallback_counts["single_input_next_task"] += 1
        variants.append(("crossed-evidence", crossed, cross_note))

        unrelated = copy.deepcopy(complete)
        unrelated_relative = item["expected_path"].relative_to(fixture).as_posix()
        unrelated.append(evidence_entry(fixture, unrelated_relative, "unrelated_expected_observation"))
        variants.append(
            ("unrelated-existing-file", unrelated, "append existing expected observation with its actual hash")
        )

        duplicate = copy.deepcopy(complete)
        conflicting = copy.deepcopy(complete[0])
        conflicting["sha256"] = altered_hash(conflicting["sha256"])
        duplicate.append(conflicting)
        variants.append(("conflicting-duplicate", duplicate, "duplicate first path with conflicting hash"))

        wrong_path = copy.deepcopy(complete)
        wrong_path[0]["path"] = "task.json"
        variants.append(
            (
                "correct-hash-wrong-path",
                wrong_path,
                "associate correct intended-input hash and size with existing task.json path",
            )
        )

        if tuple(variant[0] for variant in variants) != VARIANT_ORDER:
            raise BuildError("variant ordering changed")
        output_json = canonical_json_bytes(item["expected"]).decode("utf-8")
        if json.loads(output_json) != item["expected"]:
            raise BuildError(f"{row['task_id']}: producer output is not semantically correct")
        for variant_order, (variant_id, supplied_evidence, note) in enumerate(variants, start=1):
            envelope_sha = sha256_bytes(canonical_json_bytes(supplied_evidence))
            cases.append(
                {
                    "case_id": f"{row['task_id']}--{variant_id}",
                    "case_order": (task_order - 1) * len(VARIANT_ORDER) + variant_order,
                    "task_id": row["task_id"],
                    "task_order": task_order,
                    "stratum": row["stratum"],
                    "output_kind": row["output_kind"],
                    "fixture_path": row["fixture_path"],
                    "expected_path": row["expected_path"],
                    "task_sha256": sha256_file(item["task_path"]),
                    "expected_sha256": sha256_file(item["expected_path"]),
                    "producer_output_json": output_json,
                    "producer_output_sha256": sha256_bytes(output_json.encode("utf-8")),
                    "producer_output_bytes": len(output_json.encode("utf-8")),
                    "system_claim": "success",
                    "supplied_evidence": supplied_evidence,
                    "evidence_envelope_sha256": envelope_sha,
                    "challenge_metadata": {
                        "variant_id": variant_id,
                        "deterministic_transform": note,
                    },
                }
            )

    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "distribution_id": DISTRIBUTION_ID,
        "contract_id": manifest["contract_id"],
        "source_id": manifest["source_id"],
        "source_snapshot_id": manifest["source_snapshot_id"],
        "builder": "build_challenges.py:v1",
        "task_manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "task_manifest_sha256": sha256_file(manifest_path),
        "stale_fixture_path": stale_fixture.relative_to(ROOT).as_posix(),
        "stale_fixture_sha256": stale_hash,
        "variant_order": list(VARIANT_ORDER),
        "crossed_evidence_applicability": {
            "multi_input_rule": "swap first two declared input hash/size associations",
            "single_input_fallback": "use next task's first input relative to current fixture, wrapping task order",
            "counts": fallback_counts,
        },
        "repetitions": 3,
        "case_count": len(cases),
        "construction_validation": {
            "task_count": len(task_data),
            "cases_per_task": len(VARIANT_ORDER),
            "all_producer_outputs_semantically_correct": True,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--stale-fixture", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest_path = resolve_repo_path(args.manifest, "--manifest")
    stale_fixture = resolve_repo_path(args.stale_fixture, "--stale-fixture")
    output_path = resolve_repo_path(args.output, "--output")
    document = build_document(manifest_path, stale_fixture)
    expected_bytes = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if args.check:
        if not output_path.is_file() or output_path.read_bytes() != expected_bytes:
            raise BuildError("frozen challenge artifact does not match deterministic regeneration")
        print(f"challenge check: PASS (96 cases, sha256={sha256_bytes(expected_bytes)})")
        return 0
    if output_path.exists():
        raise BuildError(f"refusing to overwrite existing challenge artifact: {output_path.relative_to(ROOT)}")
    write_json(output_path, document)
    print(f"challenge build: COMPLETE (96 cases, sha256={sha256_file(output_path)})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BuildError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"challenge build: FAIL ({exc})")
        raise SystemExit(1)

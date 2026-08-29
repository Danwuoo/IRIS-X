#!/usr/bin/env python3
"""Build the deterministic frozen challenge artifact for H-V1a."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ID = "exp-2026-08-30-docops-acceptance-verification"
DISTRIBUTION_ID = "taskdist-2026-08-28-vanta-docops-readonly-12"
VARIANT_ORDER = (
    "canonical-valid",
    "semantic-equivalent-valid",
    "omission-invalid",
    "fabrication-invalid",
    "corruption-invalid",
)


class BuildError(ValueError):
    """Raised when deterministic challenge construction cannot be validated."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pretty_reordered_json(value: Any) -> str:
    def reorder(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: reorder(item[key]) for key in reversed(list(item.keys()))}
        if isinstance(item, list):
            return [reorder(element) for element in item]
        return item

    return json.dumps(reorder(value), ensure_ascii=False, indent=2) + "\n"


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


def omission_mutation(expected: dict[str, Any]) -> tuple[dict[str, Any], str]:
    result = copy.deepcopy(expected)
    key = sorted(result)[0]
    value = result[key]
    if isinstance(value, list) and value:
        result[key] = value[1:]
        note = f"removed first item from required list field {key}"
    else:
        del result[key]
        note = f"removed required top-level field {key} (fallback for empty/non-list field)"
    return result, note


def fabrication_mutation(expected: dict[str, Any]) -> tuple[dict[str, Any], str]:
    result = copy.deepcopy(expected)
    for key in sorted(result):
        if isinstance(result[key], list):
            result[key].append({"__fabricated__": "h-v1a-synthetic"})
            return result, f"appended deterministic fabricated item to list field {key}"
    result["__fabricated__"] = "h-v1a-synthetic"
    return result, "added deterministic fabricated top-level field (no list field available)"


def corrupt_value(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1_000_003
    if isinstance(value, float):
        return value + 1_000_003.0
    if isinstance(value, str):
        return value + "__h_v1a_corrupted"
    if value is None:
        return "__h_v1a_corrupted_null"
    if isinstance(value, list):
        if value:
            result = copy.deepcopy(value)
            result[0] = corrupt_value(result[0])
            return result
        return [{"__corrupted__": "h-v1a-synthetic"}]
    if isinstance(value, dict):
        if value:
            result = copy.deepcopy(value)
            key = sorted(result)[0]
            result[key] = corrupt_value(result[key])
            return result
        return {"__corrupted__": "h-v1a-synthetic"}
    raise BuildError(f"unsupported value type for corruption: {type(value).__name__}")


def corruption_mutation(expected: dict[str, Any]) -> tuple[dict[str, Any], str]:
    key = sorted(expected)[0]
    result = copy.deepcopy(expected)
    result[key] = corrupt_value(result[key])
    return result, f"corrupted first deterministic scalar/container under field {key}"


def evidence_for_task(fixture: Path, task: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for index, artifact in enumerate(task.get("input_artifacts", [])):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            raise BuildError(f"{task.get('task_id')}: invalid input_artifacts[{index}]")
        relative = artifact["path"].replace("\\", "/")
        path = (fixture / relative).resolve()
        if fixture.resolve() not in path.parents or not path.is_file():
            raise BuildError(f"{task.get('task_id')}: input path missing or escaping fixture: {relative}")
        evidence.append(
            {
                "path": relative,
                "role": str(artifact.get("role", "unknown")),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    if not evidence:
        raise BuildError(f"{task.get('task_id')}: no declared input artifacts")
    return evidence


def variant_payloads(expected: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    canonical = canonical_json_bytes(expected).decode("utf-8")
    semantic = pretty_reordered_json(expected)
    omission, omission_note = omission_mutation(expected)
    fabrication, fabrication_note = fabrication_mutation(expected)
    corruption, corruption_note = corruption_mutation(expected)
    values = [
        ("canonical-valid", canonical, "equal", "canonical compact sorted JSON"),
        ("semantic-equivalent-valid", semantic, "equal", "reversed object insertion order and pretty formatting"),
        ("omission-invalid", canonical_json_bytes(omission).decode("utf-8"), "unequal", omission_note),
        ("fabrication-invalid", canonical_json_bytes(fabrication).decode("utf-8"), "unequal", fabrication_note),
        ("corruption-invalid", canonical_json_bytes(corruption).decode("utf-8"), "unequal", corruption_note),
    ]
    if tuple(item[0] for item in values) != VARIANT_ORDER:
        raise BuildError("variant ordering changed")
    if canonical == semantic:
        raise BuildError("semantic-equivalent serialization must differ from canonical serialization")
    for variant_id, output_json, relation, _note in values:
        parsed = json.loads(output_json)
        observed_relation = "equal" if parsed == expected else "unequal"
        if observed_relation != relation:
            raise BuildError(f"{variant_id}: expected {relation}, observed {observed_relation}")
    return values


def build_document(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("distribution_id") != DISTRIBUTION_ID or manifest.get("source_id") != "src.vanta":
        raise BuildError("baseline manifest distribution/source mismatch")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 12:
        raise BuildError("baseline manifest must enumerate 12 tasks")
    cases: list[dict[str, Any]] = []
    equal_count = 0
    unequal_count = 0
    for task_order, row in enumerate(tasks, start=1):
        fixture = resolve_repo_path(row.get("fixture_path"), f"tasks[{task_order}].fixture_path")
        task_path = fixture / "task.json"
        expected_path = (fixture / row.get("expected_path", "")).resolve()
        task = json.loads(task_path.read_text(encoding="utf-8"))
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        if task.get("task_id") != row.get("task_id") or not isinstance(expected, dict):
            raise BuildError(f"{row.get('task_id')}: task/oracle identity invalid")
        evidence = evidence_for_task(fixture, task)
        evidence_sha = sha256_bytes(canonical_json_bytes(evidence))
        for variant_order, (variant_id, output_json, relation, note) in enumerate(
            variant_payloads(expected), start=1
        ):
            equal_count += relation == "equal"
            unequal_count += relation == "unequal"
            output_bytes = output_json.encode("utf-8")
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
                    "task_sha256": sha256_file(task_path),
                    "expected_sha256": sha256_file(expected_path),
                    "producer_output_json": output_json,
                    "producer_output_sha256": sha256_bytes(output_bytes),
                    "producer_output_bytes": len(output_bytes),
                    "system_claim": "success",
                    "evidence": evidence,
                    "evidence_envelope_sha256": evidence_sha,
                    "challenge_metadata": {
                        "variant_id": variant_id,
                        "expected_semantic_relation": relation,
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
        "variant_order": list(VARIANT_ORDER),
        "repetitions": 3,
        "case_count": len(cases),
        "construction_validation": {
            "semantic_equal_case_count": equal_count,
            "semantic_unequal_case_count": unequal_count,
            "all_relations_verified_before_freeze": True,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest_path = resolve_repo_path(args.manifest, "--manifest")
    output_path = resolve_repo_path(args.output, "--output")
    document = build_document(manifest_path)
    expected_bytes = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if args.check:
        if not output_path.is_file() or output_path.read_bytes() != expected_bytes:
            raise BuildError("frozen challenge artifact does not match deterministic regeneration")
        print(f"challenge check: PASS (60 cases, sha256={sha256_bytes(expected_bytes)})")
        return 0
    if output_path.exists():
        raise BuildError(f"refusing to overwrite existing challenge artifact: {output_path.relative_to(ROOT)}")
    write_json(output_path, document)
    print(f"challenge build: COMPLETE (60 cases, sha256={sha256_file(output_path)})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BuildError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"challenge build: FAIL ({exc})")
        raise SystemExit(1)

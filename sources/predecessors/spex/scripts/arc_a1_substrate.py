#!/usr/bin/env python3
"""Freeze and validate the local ARC-AGI-1 task substrate.

This is deliberately a Stage 0 integrity tool.  It does not parse tasks for
solver use, score predictions, or claim parity with an official evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_VERSION = "0.1"
MANIFEST_SCHEMA_VERSION = "1.0"
TIER_SPECS = (
    {
        "id": "training",
        "directory": "data/training",
        "label": "training",
        "exposure_status": "training",
    },
    {
        "id": "public_evaluation",
        "directory": "data/evaluation",
        "label": "public-exposed",
        "exposure_status": "public-exposed",
    },
)


class SubstrateError(RuntimeError):
    """An invalid or unverifiable Stage 0 substrate condition."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically for all manifest hashes."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SubstrateError("invalid_json", f"Cannot read JSON object at {path}: {error}") from error
    if not isinstance(value, dict):
        raise SubstrateError("invalid_json", f"Expected a JSON object at {path}.")
    return value


def git_value(dataset_root: Path, *arguments: str) -> str:
    command = ["git", *arguments]
    try:
        result = subprocess.run(
            command,
            cwd=dataset_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SubstrateError(
            "repository_identity_unavailable",
            f"Cannot determine repository identity from {dataset_root}: {error}",
        ) from error
    return result.stdout.strip()


def checkout_identity(dataset_root: Path) -> dict[str, str]:
    """Return the immutable Git identity of the local canonical checkout."""
    return {
        "repository_url": git_value(dataset_root, "remote", "get-url", "origin"),
        "commit": git_value(dataset_root, "rev-parse", "HEAD"),
        "tree": git_value(dataset_root, "show", "-s", "--format=%T", "HEAD"),
    }


def scan_tier(dataset_root: Path, specification: dict[str, str]) -> tuple[list[dict[str, Any]], list[str]]:
    """List direct JSON tasks and separately identify invalid nested task files."""
    tier_directory = dataset_root / specification["directory"]
    if not tier_directory.is_dir():
        raise SubstrateError("missing_tier_directory", f"Missing tier directory: {tier_directory}")

    direct_files = sorted(
        (path for path in tier_directory.glob("*.json") if path.is_file()),
        key=lambda path: path.name,
    )
    files = [
        {
            "tier": specification["id"],
            "path": f"{specification['id']}/{path.name}",
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in direct_files
    ]
    nested = sorted(
        (
            path.relative_to(tier_directory).as_posix()
            for path in tier_directory.rglob("*.json")
            if path.is_file() and path.parent != tier_directory
        )
    )
    return files, nested


def relative_to_project(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as error:
        raise SubstrateError(
            "rules_snapshot_outside_project",
            f"Rules snapshot must be inside project root: {path}",
        ) from error


def build_manifest(dataset_root: Path, project_root: Path, rules_snapshot: Path) -> dict[str, Any]:
    """Build a deterministic file-level ARC-AGI-1 manifest without writing it."""
    if not rules_snapshot.is_file():
        raise SubstrateError("missing_rules_snapshot", f"Missing rules snapshot: {rules_snapshot}")

    inventories: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for specification in TIER_SPECS:
        tier_files, nested = scan_tier(dataset_root, specification)
        if nested:
            raise SubstrateError(
                "unexpected_nested_task_file",
                f"Non-recursive tier {specification['id']} contains nested JSON task files: {nested}",
            )
        inventories.append(
            {
                "id": specification["id"],
                "directory": specification["directory"],
                "task_file_glob": "*.json",
                "scan_mode": "non-recursive",
                "tier_label": specification["label"],
                "exposure_status": specification["exposure_status"],
                "task_file_count": len(tier_files),
            }
        )
        files.extend(tier_files)

    payload: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_type": "arc-agi-1-dataset-manifest",
        "generator": {"path": "scripts/arc_a1_substrate.py", "version": SCRIPT_VERSION},
        "canonical_source": checkout_identity(dataset_root),
        "inventories": inventories,
        "files": files,
        "rules_snapshot": {
            "path": relative_to_project(rules_snapshot, project_root),
            "sha256": sha256_file(rules_snapshot),
        },
    }
    payload["dataset_manifest_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(manifest))


def validation_failure(code: str, message: str, **detail: Any) -> dict[str, Any]:
    failure: dict[str, Any] = {"code": code, "message": message}
    if detail:
        failure["detail"] = detail
    return failure


def validate_manifest(manifest_path: Path, dataset_root: Path, project_root: Path) -> dict[str, Any]:
    """Validate the frozen manifest and report all observable integrity failures."""
    failures: list[dict[str, Any]] = []
    try:
        manifest = read_json_object(manifest_path)
    except SubstrateError as error:
        return {"valid": False, "manifest": str(manifest_path), "failures": [validation_failure(error.code, str(error))]}

    stored_hash = manifest.get("dataset_manifest_sha256")
    unhashed_manifest = {key: value for key, value in manifest.items() if key != "dataset_manifest_sha256"}
    if not isinstance(stored_hash, str) or stored_hash != sha256_bytes(canonical_json_bytes(unhashed_manifest)):
        failures.append(validation_failure("manifest_hash_mismatch", "Dataset manifest hash does not match its contents."))

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        failures.append(
            validation_failure(
                "unsupported_manifest_schema",
                "Dataset manifest schema version is unsupported.",
                expected=MANIFEST_SCHEMA_VERSION,
                actual=manifest.get("schema_version"),
            )
        )

    rules = manifest.get("rules_snapshot")
    if not isinstance(rules, dict) or not isinstance(rules.get("path"), str) or not isinstance(rules.get("sha256"), str):
        failures.append(validation_failure("invalid_rules_snapshot", "Manifest rules snapshot identity is missing or malformed."))
    else:
        rules_path = project_root / rules["path"]
        if not rules_path.is_file():
            failures.append(validation_failure("missing_rules_snapshot", "Rules snapshot is missing.", path=rules["path"]))
        elif sha256_file(rules_path) != rules["sha256"]:
            failures.append(
                validation_failure("rules_snapshot_mismatch", "Rules snapshot hash does not match the frozen manifest.", path=rules["path"])
            )

    try:
        actual_source = checkout_identity(dataset_root)
    except SubstrateError as error:
        failures.append(validation_failure(error.code, str(error)))
    else:
        expected_source = manifest.get("canonical_source")
        if not isinstance(expected_source, dict):
            failures.append(validation_failure("invalid_source_identity", "Manifest canonical source identity is missing or malformed."))
        else:
            for field, actual_value in actual_source.items():
                if expected_source.get(field) != actual_value:
                    failures.append(
                        validation_failure(
                            "source_identity_mismatch",
                            "Local canonical source identity differs from frozen manifest.",
                            field=field,
                            expected=expected_source.get(field),
                            actual=actual_value,
                        )
                    )

    expected_files = manifest.get("files")
    inventories = manifest.get("inventories")
    if not isinstance(expected_files, list) or not isinstance(inventories, list):
        failures.append(validation_failure("invalid_manifest_layout", "Manifest inventories or file list is missing or malformed."))
    else:
        expected_by_path = {
            item.get("path"): item
            for item in expected_files
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        if len(expected_by_path) != len(expected_files):
            failures.append(validation_failure("invalid_manifest_layout", "Manifest task paths must be unique strings."))

        expected_inventory_ids = [item.get("id") for item in inventories if isinstance(item, dict)]
        if expected_inventory_ids != [specification["id"] for specification in TIER_SPECS]:
            failures.append(
                validation_failure(
                    "inventory_definition_mismatch",
                    "Manifest inventories do not match the Stage 0 training/public-evaluation tiers.",
                )
            )

        actual_by_path: dict[str, dict[str, Any]] = {}
        for specification in TIER_SPECS:
            try:
                current_files, nested = scan_tier(dataset_root, specification)
            except SubstrateError as error:
                failures.append(validation_failure(error.code, str(error)))
                continue
            for nested_path in nested:
                failures.append(
                    validation_failure(
                        "unexpected_nested_task_file",
                        "A non-recursive task tier contains an unexpected nested JSON file.",
                        tier=specification["id"],
                        path=nested_path,
                    )
                )
            actual_by_path.update({item["path"]: item for item in current_files})

        for path in sorted(set(expected_by_path) - set(actual_by_path)):
            failures.append(validation_failure("missing_task_file", "Frozen task file is missing.", path=path))
        for path in sorted(set(actual_by_path) - set(expected_by_path)):
            failures.append(validation_failure("unexpected_task_file", "Unexpected task file is present.", path=path))
        for path in sorted(set(expected_by_path) & set(actual_by_path)):
            expected = expected_by_path[path]
            actual = actual_by_path[path]
            if expected.get("sha256") != actual["sha256"]:
                failures.append(validation_failure("modified_task_file", "Task file hash differs from frozen manifest.", path=path))
            if expected.get("size_bytes") != actual["size_bytes"]:
                failures.append(validation_failure("task_file_size_mismatch", "Task file size differs from frozen manifest.", path=path))

        expected_counts = {
            item.get("id"): item.get("task_file_count")
            for item in inventories
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for specification in TIER_SPECS:
            actual_count = sum(1 for path in actual_by_path if path.startswith(f"{specification['id']}/"))
            if expected_counts.get(specification["id"]) != actual_count:
                failures.append(
                    validation_failure(
                        "task_inventory_count_mismatch",
                        "Non-recursive task inventory count differs from frozen manifest.",
                        tier=specification["id"],
                        expected=expected_counts.get(specification["id"]),
                        actual=actual_count,
                    )
                )

    return {
        "valid": not failures,
        "manifest": str(manifest_path),
        "dataset_root": str(dataset_root),
        "failures": failures,
    }


def project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "validate"))
    parser.add_argument("--project-root", default=".", help="Repository root (default: current directory).")
    parser.add_argument(
        "--dataset-root",
        default="data/arc-datasets/ARC-AGI-1",
        help="ARC-AGI-1 checkout relative to project root.",
    )
    parser.add_argument(
        "--rules-snapshot",
        default="artifacts/arc-agi-1/rules.json",
        help="Frozen rules snapshot relative to project root.",
    )
    parser.add_argument(
        "--manifest",
        default="artifacts/arc-agi-1/manifest.json",
        help="Dataset manifest relative to project root.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    project_root = Path(arguments.project_root).resolve()
    dataset_root = project_path(project_root, arguments.dataset_root).resolve()
    rules_snapshot = project_path(project_root, arguments.rules_snapshot).resolve()
    manifest_path = project_path(project_root, arguments.manifest).resolve()

    try:
        if arguments.command == "generate":
            manifest = build_manifest(dataset_root, project_root, rules_snapshot)
            write_manifest(manifest_path, manifest)
            print(json.dumps({"written": str(manifest_path), "dataset_manifest_sha256": manifest["dataset_manifest_sha256"]}, sort_keys=True))
            return 0

        result = validate_manifest(manifest_path, dataset_root, project_root)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["valid"] else 1
    except SubstrateError as error:
        print(json.dumps({"valid": False, "failures": [validation_failure(error.code, str(error))]}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())

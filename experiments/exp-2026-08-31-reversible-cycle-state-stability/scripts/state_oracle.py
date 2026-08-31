#!/usr/bin/env python3
"""Independent filesystem-state oracle for H-SR1a."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def state_manifest(workspace: Path) -> dict[str, Any]:
    root = workspace.resolve()
    files = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file():
            payload = path.read_bytes()
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_bytes(payload),
                    "bytes": len(payload),
                }
            )
    return {
        "files": files,
        "path_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "manifest_sha256": sha256_bytes(canonical_json_bytes(files)),
    }


def compare_exact(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_by_path = {item["path"]: item for item in expected["files"]}
    actual_by_path = {item["path"]: item for item in actual["files"]}
    expected_paths = set(expected_by_path)
    actual_paths = set(actual_by_path)
    residual_paths = sorted(actual_paths - expected_paths)
    missing_paths = sorted(expected_paths - actual_paths)
    changed_paths = sorted(
        path
        for path in expected_paths & actual_paths
        if expected_by_path[path]["sha256"] != actual_by_path[path]["sha256"]
        or expected_by_path[path]["bytes"] != actual_by_path[path]["bytes"]
    )
    return {
        "exact": not residual_paths and not missing_paths and not changed_paths,
        "expected_manifest_sha256": expected["manifest_sha256"],
        "actual_manifest_sha256": actual["manifest_sha256"],
        "residual_paths": residual_paths,
        "missing_paths": missing_paths,
        "changed_paths": changed_paths,
        "residual_bytes": sum(actual_by_path[path]["bytes"] for path in residual_paths),
    }


def verify_changed_state(
    workspace: Path,
    baseline: dict[str, Any],
    source_path: str,
    expected_changed_sha256: str,
    expected_changed_bytes: int,
    backup_path: str,
    metadata_path: str,
    action_sha256: str,
) -> dict[str, Any]:
    actual = state_manifest(workspace)
    baseline_by_path = {item["path"]: item for item in baseline["files"]}
    actual_by_path = {item["path"]: item for item in actual["files"]}
    expected_paths = set(baseline_by_path) | {backup_path, metadata_path}
    reasons: list[str] = []
    if set(actual_by_path) != expected_paths:
        reasons.append("post_apply_path_membership_mismatch")
    source = actual_by_path.get(source_path)
    if source is None or source["sha256"] != expected_changed_sha256 or source["bytes"] != expected_changed_bytes:
        reasons.append("changed_source_identity_mismatch")
    backup = actual_by_path.get(backup_path)
    baseline_source = baseline_by_path.get(source_path)
    if backup is None or baseline_source is None or backup["sha256"] != baseline_source["sha256"]:
        reasons.append("backup_identity_mismatch")
    for path, expected in baseline_by_path.items():
        if path == source_path:
            continue
        actual_item = actual_by_path.get(path)
        if actual_item != expected:
            reasons.append(f"unrelated_path_changed:{path}")
    metadata_file = workspace / metadata_path
    metadata: dict[str, Any] | None = None
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        reasons.append("metadata_unreadable")
    if metadata is not None:
        required = {
            "source_path": source_path,
            "backup_path": backup_path,
            "metadata_path": metadata_path,
            "baseline_sha256": baseline_source["sha256"] if baseline_source else None,
            "changed_sha256": expected_changed_sha256,
            "action_sha256": action_sha256,
        }
        if any(metadata.get(key) != value for key, value in required.items()):
            reasons.append("metadata_required_fields_mismatch")
    changed_paths = sorted(
        path
        for path in set(actual_by_path) | set(baseline_by_path)
        if actual_by_path.get(path) != baseline_by_path.get(path)
    )
    return {
        "valid": not reasons,
        "reasons": reasons,
        "changed_paths": changed_paths,
        "manifest": actual,
        "metadata": metadata,
    }


def residual_artifact_self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="irisx-hsr1a-oracle-") as temporary:
        workspace = Path(temporary)
        (workspace / "baseline.txt").write_bytes(b"baseline\n")
        baseline = state_manifest(workspace)
        residual = workspace / "residual.tmp"
        residual.write_bytes(b"must be detected\n")
        comparison = compare_exact(baseline, state_manifest(workspace))
        passed = not comparison["exact"] and comparison["residual_paths"] == ["residual.tmp"]
        return {"passed": passed, "comparison": comparison}

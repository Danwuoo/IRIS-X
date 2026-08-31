#!/usr/bin/env python3
"""Independent exact-state adjudicator for H-RCV1a."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from recovery_common import state_manifest


def evaluate(workspace: Path, oracle_spec: dict[str, Any]) -> dict[str, Any]:
    actual = state_manifest(workspace)
    actual_by_path = {item["path"]: item for item in actual["files"]}
    expected_by_path = {item["path"]: item for item in oracle_spec["expected_final_files"]}
    initial_paths = set(oracle_spec["initial_failure_paths"])
    expected_paths = set(expected_by_path)
    actual_paths = set(actual_by_path)
    missing_paths = sorted(expected_paths - actual_paths)
    residual_paths = sorted(actual_paths - expected_paths)
    changed_paths = sorted(
        path
        for path in expected_paths & actual_paths
        if expected_by_path[path] != actual_by_path[path]
    )
    final_valid = (
        not missing_paths
        and not residual_paths
        and not changed_paths
        and actual["manifest_sha256"] == oracle_spec["expected_final_manifest_sha256"]
    )
    new_side_effect_paths = sorted(actual_paths - expected_paths - initial_paths)
    return {
        "final_state_valid": final_valid,
        "final_actual_outcome": "success" if final_valid else "failure",
        "final_evidence_status": "sufficient",
        "expected_final_manifest_sha256": oracle_spec["expected_final_manifest_sha256"],
        "actual_final_manifest_sha256": actual["manifest_sha256"],
        "missing_paths": missing_paths,
        "residual_paths": residual_paths,
        "changed_paths": changed_paths,
        "new_side_effect_violation": bool(new_side_effect_paths),
        "new_side_effect_paths": new_side_effect_paths,
        "manifest": actual,
    }


def failed_recovery_self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="irisx-hrcv1a-oracle-") as temporary:
        workspace = Path(temporary)
        target = workspace / "target.txt"
        target.write_bytes(b"valid\n")
        expected = state_manifest(workspace)
        oracle_spec = {
            "expected_final_files": expected["files"],
            "expected_final_manifest_sha256": expected["manifest_sha256"],
            "initial_failure_paths": ["target.txt"],
        }
        target.write_bytes(b"failed recovery\n")
        adjudication = evaluate(workspace, oracle_spec)
        return {
            "passed": not adjudication["final_state_valid"] and adjudication["changed_paths"] == ["target.txt"],
            "adjudication": adjudication,
        }

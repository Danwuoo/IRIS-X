#!/usr/bin/env python3
"""Mechanically check declared D1a role information boundaries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    D1aValidationError,
    flatten_strings,
    load_json,
    pretty_json,
    safe_asset_path,
    unique_paths_casefold,
)


ROLE_PROHIBITED_TOKENS = {
    "task_oracle": {
        "perturbation_assignment",
        "evidence_perturbation",
        "authority_perturbation",
        "policy_decisions",
        "heldout_producer_outputs",
    },
    "authority_policy": {
        "realized_correctness",
        "heldout_outcomes",
        "policy_scores",
        "whoever_was_correct",
    },
    "semantic_verifier": {
        "heldout_oracle_labels",
        "authority_mapping",
        "authority_map",
        "perturbation_labels",
        "policy_outputs",
        "authorization_conformance",
    },
    "calibration": {
        "heldout_d1_outcomes",
        "d1_warrant_labels",
        "authority_labels",
        "semantic_verifier_decision",
        "policy_outputs",
    },
    "analysis": {"unsealed_heldout_results"},
}

ROLE_REQUIRED_UNOBSERVED = {
    "task_oracle": {"perturbation_assignment", "future_policy_decisions", "heldout_producer_outputs"},
    "authority_policy": {"realized_correctness", "heldout_outcomes", "policy_scores"},
    "semantic_verifier": {"heldout_oracle_labels", "authority_map", "perturbation_labels", "policy_outputs"},
    "calibration": {"heldout_d1_outcomes", "d1_warrant_labels", "authority_labels", "policy_outputs"},
    "analysis": {"heldout_results_before_analysis_freeze", "ability_to_revise_upstream_assets"},
}


def _dependency_key(value: dict[str, Any]) -> tuple[str, str]:
    return str(value.get("bundle_id")), str(value.get("custodian_role"))


def _scan_text_asset(path: Path) -> tuple[str | None, bool]:
    try:
        return path.read_text(encoding="utf-8").casefold(), True
    except (UnicodeError, OSError):
        return None, False


def validate_boundaries(bundle: dict[str, Any], bundle_root: Path) -> dict[str, Any]:
    role = bundle.get("custodian_role")
    errors: list[str] = []
    warnings: list[str] = []
    scanned_paths: list[str] = []
    unscannable_paths: list[str] = []
    discovered_dependency_markers: set[str] = set()

    if role not in ROLE_PROHIBITED_TOKENS:
        return {
            "status": "rejected",
            "information_boundary_declared": False,
            "information_boundary_mechanically_checkable": False,
            "errors": [f"unknown custodian role: {role!r}"],
            "warnings": [],
            "scanned_paths": [],
        }

    declared = {_dependency_key(item) for item in bundle.get("declared_dependencies", [])}
    observed = {_dependency_key(item) for item in bundle.get("observed_dependencies", [])}
    undeclared = sorted(observed - declared)
    if undeclared:
        errors.append(f"undeclared_dependencies:{undeclared}")

    prohibited_dependencies = {str(value).casefold() for value in bundle.get("prohibited_dependencies", [])}
    for bundle_id, dependency_role in observed:
        if bundle_id.casefold() in prohibited_dependencies or dependency_role.casefold() in prohibited_dependencies:
            errors.append(f"prohibited_dependency_observed:{bundle_id}:{dependency_role}")

    not_observed = {
        str(value).casefold() for value in bundle.get("information_not_observed_before_freeze", [])
    }
    missing_declarations = sorted(ROLE_REQUIRED_UNOBSERVED[role] - not_observed)
    if missing_declarations:
        errors.append(f"missing_required_unobserved_declarations:{missing_declarations}")

    asset_paths = [str(item.get("path", "")) for item in bundle.get("assets", [])]
    evidence_paths = [str(item.get("path", "")) for item in bundle.get("independence_evidence", [])]
    if not unique_paths_casefold(asset_paths + evidence_paths):
        errors.append("case_ambiguous_or_duplicate_asset_reference")

    prohibited_tokens = ROLE_PROHIBITED_TOKENS[role]
    for value in asset_paths:
        try:
            path = safe_asset_path(bundle_root, value)
        except D1aValidationError as exc:
            errors.append(str(exc))
            continue
        text, scannable = _scan_text_asset(path)
        if not scannable or text is None:
            unscannable_paths.append(value)
            continue
        scanned_paths.append(value)
        normalized = text.replace("-", "_").replace(" ", "_")
        discovered_dependency_markers.update(
            match.group(1) for match in re.finditer(r"d1a-dependency:([a-z0-9._-]+)", text)
        )
        for token in sorted(prohibited_tokens):
            if token in normalized:
                errors.append(f"prohibited_information_token:{value}:{token}")

    observed_strings = {value.casefold() for value in flatten_strings(bundle.get("information_observed_before_freeze", []))}
    for token in sorted(prohibited_tokens):
        if token in observed_strings:
            errors.append(f"prohibited_information_declared_observed:{token}")

    if unscannable_paths:
        warnings.append(f"unscannable_assets:{sorted(unscannable_paths)}")

    declared_bundle_ids = {bundle_id.casefold() for bundle_id, _ in declared}
    undeclared_markers = sorted(discovered_dependency_markers - declared_bundle_ids)
    if undeclared_markers:
        errors.append(f"undeclared_asset_dependency_markers:{undeclared_markers}")

    declared_complete = not missing_declarations
    mechanically_checkable = declared_complete and not errors and not unscannable_paths
    return {
        "status": "rejected" if errors else ("mechanically_checkable" if mechanically_checkable else "declared_only"),
        "information_boundary_declared": declared_complete,
        "information_boundary_mechanically_checkable": mechanically_checkable,
        "errors": errors,
        "warnings": warnings,
        "scanned_paths": sorted(scanned_paths),
        "unscannable_paths": sorted(unscannable_paths),
        "discovered_dependency_markers": sorted(discovered_dependency_markers),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        bundle = load_json(args.bundle)
        result = validate_boundaries(bundle, args.bundle.resolve().parent)
    except D1aValidationError as exc:
        result = {"status": "rejected", "errors": [str(exc)]}
    sys.stdout.write(pretty_json(result))
    return 1 if result["status"] == "rejected" else 0


if __name__ == "__main__":
    raise SystemExit(main())

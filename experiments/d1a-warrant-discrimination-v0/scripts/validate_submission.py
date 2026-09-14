#!/usr/bin/env python3
"""Fail-closed schema, seal, provenance, and boundary validation for D1a bundles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from common import (
    COORDINATOR_ID,
    D1aValidationError,
    ROLE_SCHEMA_PATHS,
    bundle_manifest_sha256,
    load_json,
    pretty_json,
    safe_asset_path,
    schema_errors,
    sha256_path,
)
from validate_information_boundaries import validate_boundaries


def _validate_digest_entries(
    entries: list[dict[str, Any]], bundle_root: Path, label: str
) -> list[str]:
    errors: list[str] = []
    for index, entry in enumerate(entries):
        value = entry.get("path")
        try:
            path = safe_asset_path(bundle_root, value)
        except D1aValidationError as exc:
            errors.append(f"{label}[{index}]:{exc}")
            continue
        expected = entry.get("sha256")
        observed = sha256_path(path)
        if observed != expected:
            errors.append(f"{label}[{index}]:digest_mismatch:{value}")
    return errors


def _role_asset_references(value: Any, key: str = "") -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            references.extend(_role_asset_references(child, child_key))
    elif isinstance(value, list):
        for child in value:
            references.extend(_role_asset_references(child, key))
    elif isinstance(value, str) and key.endswith("_path"):
        references.append(value)
    return references


def validate_bundle_document(bundle: dict[str, Any], bundle_root: Path) -> dict[str, Any]:
    role = bundle.get("custodian_role")
    schema_path = ROLE_SCHEMA_PATHS.get(role)
    errors: list[str] = []
    warnings: list[str] = []

    if schema_path is None:
        schema_findings = [f"unknown custodian role: {role!r}"]
    else:
        schema_findings = schema_errors(bundle, schema_path)
    schema_valid = not schema_findings
    errors.extend(f"schema:{finding}" for finding in schema_findings)

    provenance_complete = schema_valid
    digest_errors: list[str] = []
    boundary = {
        "information_boundary_declared": False,
        "information_boundary_mechanically_checkable": False,
        "errors": [],
        "warnings": [],
    }
    seal_valid = False

    if schema_valid:
        digest_errors.extend(_validate_digest_entries(bundle["assets"], bundle_root, "assets"))
        digest_errors.extend(
            _validate_digest_entries(bundle["independence_evidence"], bundle_root, "independence_evidence")
        )
        if bundle["seal"]["status"] != "sealed":
            errors.append("seal:bundle_not_sealed")
        elif bundle["seal"]["sealed_at"] is None:
            errors.append("seal:sealed_at_missing")
        else:
            expected_manifest = bundle["seal"]["manifest_sha256"]
            actual_manifest = bundle_manifest_sha256(bundle)
            if expected_manifest != actual_manifest:
                errors.append("seal:manifest_digest_mismatch")
            else:
                seal_valid = True
        if bundle["post_seal_mutations"]:
            errors.append("seal:post_seal_mutation_requires_new_bundle")
        if bundle["bundle_version"] > 1 and not bundle["version_history"]:
            errors.append("provenance:versioned_bundle_missing_history")
        declared_asset_paths = {entry["path"] for entry in bundle["assets"]}
        missing_role_assets = sorted(
            set(_role_asset_references(bundle["role_payload"])) - declared_asset_paths
        )
        if missing_role_assets:
            errors.append(f"provenance:role_asset_references_not_in_manifest:{missing_role_assets}")
        errors.extend(digest_errors)
        boundary = validate_boundaries(bundle, bundle_root)
        errors.extend(f"boundary:{finding}" for finding in boundary["errors"])
        warnings.extend(boundary["warnings"])

    attestation = bundle.get("attestation", {})
    identity = bundle.get("provenance_identity", {})
    evidence = bundle.get("independence_evidence", [])
    reviewers_distinct = bool(evidence) and all(
        entry.get("reviewer_id") != identity.get("custodian_id") for entry in evidence
    )
    independence_supported = bool(
        schema_valid
        and provenance_complete
        and seal_valid
        and not digest_errors
        and boundary.get("information_boundary_mechanically_checkable")
        and attestation.get("independent_authorship_claim") is True
        and attestation.get("coordinator_session_not_used_for_authorship") is True
        and attestation.get("prohibited_information_observed") is False
        and identity.get("custodian_id") != COORDINATOR_ID
        and identity.get("authoring_session_id") != COORDINATOR_ID
        and reviewers_distinct
        and not errors
    )
    independence_not_established = schema_valid and not independence_supported and not errors

    if errors:
        primary_status = "rejected"
    elif independence_supported:
        primary_status = "independence_supported"
    else:
        primary_status = "independence_not_established"

    return {
        "bundle_id": bundle.get("bundle_id", "unknown"),
        "custodian_role": role,
        "primary_status": primary_status,
        "schema_valid": schema_valid,
        "provenance_complete": provenance_complete and not digest_errors,
        "information_boundary_declared": boundary.get("information_boundary_declared", False),
        "information_boundary_mechanically_checkable": boundary.get(
            "information_boundary_mechanically_checkable", False
        ),
        "independence_supported": independence_supported,
        "independence_not_established": independence_not_established,
        "rejected": bool(errors),
        "seal_valid": seal_valid,
        "errors": errors,
        "warnings": warnings,
    }


def validate_bundle_path(bundle_path: Path) -> dict[str, Any]:
    document = load_json(bundle_path)
    if not isinstance(document, dict):
        raise D1aValidationError("bundle top level must be an object")
    return validate_bundle_document(document, bundle_path.resolve().parent)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_bundle_path(args.bundle)
    except D1aValidationError as exc:
        result = {
            "primary_status": "rejected",
            "schema_valid": False,
            "provenance_complete": False,
            "information_boundary_declared": False,
            "information_boundary_mechanically_checkable": False,
            "independence_supported": False,
            "independence_not_established": False,
            "rejected": True,
            "errors": [str(exc)],
            "warnings": [],
        }
    sys.stdout.write(pretty_json(result))
    return 1 if result["rejected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

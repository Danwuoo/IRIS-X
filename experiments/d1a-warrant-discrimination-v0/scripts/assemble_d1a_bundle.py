#!/usr/bin/env python3
"""Fail-closed assembly gate for real independently authored D1a bundles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from common import D1aValidationError, load_json, pretty_json
from validate_submission import validate_bundle_path


REQUIRED_ROLES = {"task_oracle", "authority_policy", "semantic_verifier", "calibration", "analysis"}


def assemble(submissions_dir: Path | None, meta_qualified: bool) -> dict[str, Any]:
    if submissions_dir is None or not submissions_dir.exists():
        return {
            "state": "ready_for_independent_custodian_submission" if meta_qualified else "ready_for_meta_qualification",
            "present_roles": [],
            "missing_roles": sorted(REQUIRED_ROLES),
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }
    if not submissions_dir.is_dir():
        return {"state": "rejected", "errors": ["submissions path is not a directory"]}

    bundle_paths = sorted(submissions_dir.glob("*.bundle.json"))
    if not bundle_paths:
        return {
            "state": "ready_for_independent_custodian_submission" if meta_qualified else "ready_for_meta_qualification",
            "present_roles": [],
            "missing_roles": sorted(REQUIRED_ROLES),
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }

    documents: dict[str, dict[str, Any]] = {}
    reports: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for path in bundle_paths:
        try:
            document = load_json(path)
            role = document.get("custodian_role")
            if role in documents:
                errors.append(f"duplicate role bundle:{role}")
                continue
            documents[role] = document
            reports[role] = validate_bundle_path(path)
        except (D1aValidationError, AttributeError) as exc:
            errors.append(f"{path.name}:{exc}")
    if errors or any(report["rejected"] for report in reports.values()):
        return {
            "state": "rejected",
            "errors": errors + [
                f"{role}:{finding}"
                for role, report in reports.items()
                for finding in report["errors"]
            ],
            "bundle_reports": reports,
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }

    present = set(documents)
    missing = REQUIRED_ROLES - present
    if missing:
        return {
            "state": "independent_assets_incomplete",
            "present_roles": sorted(present),
            "missing_roles": sorted(missing),
            "bundle_reports": reports,
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }

    calibration = documents["calibration"]["role_payload"]
    if calibration["calibration_status"] == "P0_unavailable":
        return {
            "state": "calibration_unavailable",
            "present_roles": sorted(present),
            "missing_roles": [],
            "bundle_reports": reports,
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }

    if not all(report["independence_supported"] for report in reports.values()):
        return {
            "state": "independence_not_established",
            "present_roles": sorted(present),
            "bundle_reports": reports,
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }

    custodian_ids = [documents[role]["provenance_identity"]["custodian_id"] for role in sorted(REQUIRED_ROLES)]
    session_ids = [documents[role]["provenance_identity"]["authoring_session_id"] for role in sorted(REQUIRED_ROLES)]
    if len(custodian_ids) != len(set(custodian_ids)) or len(session_ids) != len(set(session_ids)):
        return {
            "state": "independence_not_established",
            "errors": ["cross_role_custodian_or_session_identity_not_distinct"],
            "bundle_reports": reports,
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }

    component_ids = {
        documents[role]["bundle_id"] for role in REQUIRED_ROLES - {"analysis"}
    }
    analysis_dependencies = {
        item["bundle_id"] for item in documents["analysis"]["declared_dependencies"]
        if item["custodian_role"] != "public_definition"
    }
    if analysis_dependencies != component_ids:
        return {
            "state": "rejected",
            "errors": ["analysis_dependencies_do_not_match_exact_component_bundle_ids"],
            "bundle_reports": reports,
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }
    if not meta_qualified:
        return {
            "state": "ready_for_meta_qualification",
            "present_roles": sorted(present),
            "bundle_reports": reports,
            "fabricated_assets": 0,
            "ready_for_d1a_qualification": False,
        }
    return {
        "state": "ready_for_d1a_qualification",
        "present_roles": sorted(present),
        "bundle_ids": {role: documents[role]["bundle_id"] for role in sorted(REQUIRED_ROLES)},
        "bundle_reports": reports,
        "fabricated_assets": 0,
        "ready_for_d1a_qualification": True,
        "d1b_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submissions-dir", type=Path)
    parser.add_argument("--meta-qualified", action="store_true")
    args = parser.parse_args()
    result = assemble(args.submissions_dir, args.meta_qualified)
    sys.stdout.write(pretty_json(result))
    return 1 if result["state"] == "rejected" else 0


if __name__ == "__main__":
    raise SystemExit(main())

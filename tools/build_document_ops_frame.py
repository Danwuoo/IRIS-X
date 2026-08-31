#!/usr/bin/env python3
"""Build and validate the qualified IRIS-X Document Ops task frame v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = (
    ROOT
    / "sources"
    / "predecessors"
    / "vanta"
    / "docs"
    / "04_experiments"
    / "fixtures"
    / "document_ops"
)
OUTPUT = ROOT / "research" / "task-frames" / "document-ops-v1.json"
SOURCE_ID = "src.vanta"
SOURCE_SNAPSHOT_ID = "snap.src.vanta.initial-import"
SOURCE_TREE_OID = "4e095233520418705168f40a556177477839b052"

QUALIFICATION_STATUSES = {
    "qualified-local",
    "qualified-with-copied-workspace",
    "qualified-for-substrate-only",
    "deferred-framework-dependent",
    "deferred-contract-unclear",
    "rejected-for-current-frame",
}

STRATA: dict[str, list[str]] = {
    "traceability-extraction": [
        "docops_read_traceability_001",
        "docops_struct_inspect_001",
        "docops_ps1_traceability_multisource_001",
        "docops_ps1_traceability_cross_doc_refs_001",
        "docops_ps1_traceability_missing_target_001",
        "docops_ps1_traceability_structured_outline_001",
    ],
    "terminology-consistency": [
        "docops_detect_terms_001",
        "docops_struct_contract_pass_001",
        "docops_struct_contract_fail_001",
        "docops_ps1_terms_alias_conflict_001",
        "docops_ps1_terms_clean_canonical_001",
        "docops_ps1_terms_contract_inline_001",
    ],
    "simulated-patch-and-diff": [
        "docops_simulate_patch_001",
        "docops_multistep_commit_001",
        "docops_struct_simulate_md_001",
        "docops_struct_simulate_json_001",
        "docops_struct_insert_before_001",
        "docops_struct_insert_after_001",
    ],
    "reversible-edit-and-commit": [
        "docops_reversible_edit_001",
        "docops_struct_apply_reversible_001",
        "docops_ps1_reversible_append_section_001",
        "docops_ps1_reversible_replace_heading_001",
        "docops_ps1_reversible_json_path_replace_001",
        "docops_ps1_reversible_patch_multiline_001",
    ],
    "invalid-action-and-path-guard": [
        "docops_action_not_allowed_001",
        "docops_path_escape_001",
        "docops_struct_path_escape_001",
        "docops_struct_selector_missing_001",
        "docops_struct_selector_ambiguous_001",
        "docops_ps1_invalid_reversible_in_readonly_001",
    ],
    "evidence-and-verifier-challenge": [
        "docops_wrong_diff_001",
        "docops_struct_wrong_diff_001",
        "docops_struct_simulation_mutation_001",
        "docops_struct_missing_backup_metadata_001",
        "docops_ps1_wrong_diff_multiline_001",
        "docops_ps1_struct_backup_files_dropped_001",
    ],
    "journal-replay-and-recovery": [
        "docops_rollback_failure_001",
        "docops_audit_gap_001",
        "docops_compensable_action_001",
        "docops_ps1_recovery_structured_rollback_001",
        "docops_ps1_recovery_audit_gap_complete_refs_001",
        "docops_ps1_replay_multistep_structured_commit_001",
    ],
    "working-set-long-context": [
        "docops_ws_evidence_packet_001",
        "docops_ws_irrelevant_context_001",
        "docops_ws_omission_trap_001",
        "docops_ws_recovery_context_001",
        "docops_ws_traceability_long_001",
        "docops_ps1_ws_structured_edit_context_001",
    ],
}

SIMULATION_SUBSTRATE = set(STRATA["simulated-patch-and-diff"])
REVERSIBLE_COPIED = set(STRATA["reversible-edit-and-commit"])
EVIDENCE_COPIED = {
    "docops_struct_simulation_mutation_001",
    "docops_struct_missing_backup_metadata_001",
    "docops_ps1_struct_backup_files_dropped_001",
}
RECOVERY_COPIED = {
    "docops_rollback_failure_001",
    "docops_audit_gap_001",
    "docops_compensable_action_001",
    "docops_ps1_recovery_structured_rollback_001",
    "docops_ps1_recovery_audit_gap_complete_refs_001",
}
REPLAY_SUBSTRATE = {"docops_ps1_replay_multistep_structured_commit_001"}
WORKING_SET_DEFERRED = set(STRATA["working-set-long-context"])


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_stratum(fixture_id: str) -> str:
    matches = [stratum for stratum, fixture_ids in STRATA.items() if fixture_id in fixture_ids]
    if len(matches) != 1:
        raise ValueError(f"{fixture_id}: expected exactly one stratum, found {matches}")
    return matches[0]


def qualification(fixture_id: str, stratum: str) -> tuple[str, list[str]]:
    if fixture_id in WORKING_SET_DEFERRED:
        return (
            "deferred-framework-dependent",
            [
                "The fixture-local candidate refs, budget, and expected selection are explicit.",
                "Executable success depends on VANTA Working Set Compiler ordering, budgeting, and reference-selection semantics; no framework-independent IRIS-X working-set contract is frozen.",
            ],
        )
    if fixture_id in SIMULATION_SUBSTRATE:
        return (
            "qualified-for-substrate-only",
            [
                "The action payload, local inputs, no-mutation invariant, and deterministic source-side mechanism are explicit.",
                "Candidate-content and diff oracle artifacts are not uniform across all six fixtures, so this batch retains them as substrate candidates rather than declaring a common executable IRIS-X arm.",
            ],
        )
    if fixture_id in REPLAY_SUBSTRATE:
        return (
            "qualified-for-substrate-only",
            [
                "The action sequence and expected diff are explicit and local.",
                "Audit-complete and replay-consistent success depends on predecessor journal/runtime identity; the fixture is excluded from H-RCV1a because it does not freeze a recovery failure state.",
            ],
        )
    if fixture_id in REVERSIBLE_COPIED:
        return (
            "qualified-with-copied-workspace",
            [
                "The reversible mutation payload, baseline input, and expected changed state are deterministic and fixture-local.",
                "Independent baseline-restoration truth requires a validated copied workspace; the fixture is eligible for H-SR1a.",
            ],
        )
    if fixture_id in EVIDENCE_COPIED:
        return (
            "qualified-with-copied-workspace",
            [
                "The injected mutation or backup fault and expected rejection condition are explicit.",
                "Empirical state truth requires execution only inside a copied workspace; the fixture is not selected for H-SR1a or H-RCV1a.",
            ],
        )
    if fixture_id in RECOVERY_COPIED:
        return (
            "qualified-with-copied-workspace",
            [
                "The initial failure contract, targeted recovery policy, and local inputs are explicit.",
                "The failure state and recovery output can be frozen in a copied workspace and independently adjudicated; the fixture is eligible for H-RCV1a.",
            ],
        )
    if stratum in {"traceability-extraction", "terminology-consistency"}:
        return (
            "qualified-local",
            [
                "The task is read-only, local, credential-free, and has a deterministic fixture-local expected observation.",
                "The task already has an IRIS-X read-only execution/evaluation contract and is eligible for H-OR1a.",
            ],
        )
    if stratum == "invalid-action-and-path-guard":
        return (
            "qualified-local",
            [
                "The invalid proposal and expected rejection condition are explicit and locally adjudicable before mutation.",
                "No predecessor runtime type is required as IRIS-X architecture authority.",
            ],
        )
    if stratum == "evidence-and-verifier-challenge":
        return (
            "qualified-local",
            [
                "The proposed output/diff and expected rejection oracle are fixture-local and deterministic.",
                "The fixture requires no source mutation and can be evaluated without network, credentials, or paid services.",
            ],
        )
    raise ValueError(f"{fixture_id}: qualification policy is missing")


def action_mode(side_effect_classes: list[str]) -> str:
    return "+".join(value.lower().replace("_", "-") for value in side_effect_classes)


def expected_output_shape(fixture: Path, acceptance: dict[str, Any]) -> dict[str, Any]:
    artifact_files = sorted(
        path.relative_to(fixture).as_posix()
        for path in (fixture / "expected").iterdir()
        if path.is_file() and path.name != "acceptance.json"
    )
    return {
        "acceptance_runtime_status": acceptance.get("expected_runtime_status"),
        "artifact_files": artifact_files,
        "task_success_value": acceptance.get("expected_task_success"),
    }


def oracle_types(stratum: str, status: str) -> list[str]:
    values = ["fixture-acceptance-contract"]
    if stratum in {"traceability-extraction", "terminology-consistency"}:
        values.append("deterministic-expected-observation")
    if stratum in {"simulated-patch-and-diff", "evidence-and-verifier-challenge"}:
        values.append("deterministic-action-and-diff-oracle")
    if status == "qualified-with-copied-workspace":
        values.append("independent-copied-workspace-state-oracle")
    if stratum == "journal-replay-and-recovery":
        values.append("recovery-final-state-or-record-oracle")
    if stratum == "working-set-long-context":
        values.append("predecessor-working-set-selection-oracle")
    return values


def record_for(fixture_id: str) -> dict[str, Any]:
    fixture = FIXTURE_ROOT / fixture_id
    task = load_json(fixture / "task.json")
    acceptance = load_json(fixture / "expected" / "acceptance.json")
    stratum = fixture_stratum(fixture_id)
    status, reasons = qualification(fixture_id, stratum)
    copied = status == "qualified-with-copied-workspace"
    recovery_required = fixture_id in RECOVERY_COPIED
    framework_dependencies = (
        ["VANTA Working Set Compiler v0 selection/budget semantics"]
        if fixture_id in WORKING_SET_DEFERRED
        else []
    )
    source_fixture_path = fixture.relative_to(ROOT).as_posix()
    expected_files = sorted((fixture / "expected").glob("*"))
    input_files = []
    for artifact in task.get("input_artifacts", []):
        relative = artifact["path"]
        path = (fixture / relative).resolve()
        input_files.append(
            {
                "path": relative,
                "role": artifact.get("role", "Unknown"),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return {
        "fixture_id": fixture_id,
        "source_id": SOURCE_ID,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "source_fixture_path": source_fixture_path,
        "stratum": stratum,
        "source_stated_purpose": task.get("prompt"),
        "action_mode": action_mode(task.get("side_effect_classes", [])),
        "requires_mutation": copied,
        "requires_copied_workspace": copied,
        "oracle_location": [path.relative_to(ROOT).as_posix() for path in expected_files],
        "oracle_type": oracle_types(stratum, status),
        "expected_output_shape": expected_output_shape(fixture, acceptance),
        "state_oracle_required": True,
        "evidence_oracle_required": bool(
            {"evidence_packets", "verifier_outputs"}.intersection(task.get("required_logs", []))
            or stratum in {"evidence-and-verifier-challenge", "journal-replay-and-recovery"}
        ),
        "recovery_state_required": recovery_required,
        "long_context_required": stratum == "working-set-long-context",
        "known_external_dependency": [],
        "known_framework_dependency": framework_dependencies,
        "safe_local_candidate": status not in {
            "deferred-framework-dependent",
            "deferred-contract-unclear",
            "rejected-for-current-frame",
        },
        "qualification_status": status,
        "qualification_reasons": reasons,
        "declared_inputs": input_files,
        "action_sequence_sha256": hashlib.sha256(
            json.dumps(
                acceptance.get("action_sequence", {}),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }


def eligible_group(records: list[dict[str, Any]], stratum: str) -> list[str]:
    return [
        record["fixture_id"]
        for record in records
        if record["stratum"] == stratum and record["safe_local_candidate"]
    ]


def build_frame() -> dict[str, Any]:
    ordered_ids = [fixture_id for fixture_ids in STRATA.values() for fixture_id in fixture_ids]
    records = [record_for(fixture_id) for fixture_id in ordered_ids]
    status_counts = Counter(record["qualification_status"] for record in records)
    stratum_counts = Counter(record["stratum"] for record in records)
    return {
        "schema_version": 1,
        "frame_id": "document-ops-task-frame-v1",
        "status": "qualified-local-task-frame",
        "claim_boundary": (
            "A broader research/evaluation substrate over preserved local fixtures; "
            "not a representative, general, or validated benchmark."
        ),
        "source_identity": {
            "source_id": SOURCE_ID,
            "source_snapshot_id": SOURCE_SNAPSHOT_ID,
            "registered_tree_oid": SOURCE_TREE_OID,
            "fixture_catalog_path": (
                "sources/predecessors/vanta/docs/04_experiments/fixtures/README.md"
            ),
        },
        "qualification_method": {
            "inspection_scope": [
                "all 48 task.json files",
                "all 48 expected/acceptance.json files",
                "all declared fixture inputs",
                "all fixture-local expected artifacts",
                "relevant VANTA action, structured-edit, path-guard, recovery, replay, and working-set definitions",
            ],
            "network_allowed": False,
            "credentials_allowed": False,
            "imported_source_mutation_allowed": False,
        },
        "summary": {
            "fixture_count": len(records),
            "status_counts": dict(sorted(status_counts.items())),
            "stratum_counts": dict(sorted(stratum_counts.items())),
        },
        "eligible_groups": {
            "frame_v1_readonly": eligible_group(records, "traceability-extraction")
            + eligible_group(records, "terminology-consistency"),
            "frame_v1_simulation": eligible_group(records, "simulated-patch-and-diff"),
            "frame_v1_reversible_state": eligible_group(records, "reversible-edit-and-commit"),
            "frame_v1_guard": eligible_group(records, "invalid-action-and-path-guard"),
            "frame_v1_evidence": eligible_group(records, "evidence-and-verifier-challenge"),
            "frame_v1_recovery": sorted(RECOVERY_COPIED),
            "frame_v1_long_context": [],
        },
        "deferred_groups": {
            "frame_v1_long_context": sorted(WORKING_SET_DEFERRED),
        },
        "fixtures": records,
    }


def git_tree_oid() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD:sources/predecessors/vanta"],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise ValueError(f"cannot resolve VANTA tree: {completed.stderr.strip()}")
    return completed.stdout.strip()


def validate_frame(frame: dict[str, Any]) -> None:
    actual_dirs = {path.name for path in FIXTURE_ROOT.iterdir() if path.is_dir()}
    declared_ids = [fixture_id for values in STRATA.values() for fixture_id in values]
    if len(declared_ids) != 48 or len(set(declared_ids)) != 48:
        raise ValueError("stratum inventory must contain exactly 48 unique fixture IDs")
    if actual_dirs != set(declared_ids):
        raise ValueError(
            f"fixture inventory mismatch: missing={sorted(actual_dirs - set(declared_ids))}, "
            f"extra={sorted(set(declared_ids) - actual_dirs)}"
        )
    if git_tree_oid() != SOURCE_TREE_OID:
        raise ValueError("registered VANTA source tree changed")
    records = frame.get("fixtures")
    if not isinstance(records, list) or len(records) != 48:
        raise ValueError("frame must contain exactly 48 fixture records")
    fixture_ids = [record.get("fixture_id") for record in records]
    if len(set(fixture_ids)) != 48 or set(fixture_ids) != actual_dirs:
        raise ValueError("frame fixture IDs must account for all source fixtures exactly once")
    required_fields = {
        "fixture_id",
        "source_id",
        "source_snapshot_id",
        "source_fixture_path",
        "stratum",
        "source_stated_purpose",
        "action_mode",
        "requires_mutation",
        "requires_copied_workspace",
        "oracle_location",
        "oracle_type",
        "expected_output_shape",
        "state_oracle_required",
        "evidence_oracle_required",
        "recovery_state_required",
        "long_context_required",
        "known_external_dependency",
        "known_framework_dependency",
        "safe_local_candidate",
        "qualification_status",
        "qualification_reasons",
    }
    for record in records:
        missing = required_fields - record.keys()
        if missing:
            raise ValueError(f"{record.get('fixture_id')}: missing fields {sorted(missing)}")
        if record["qualification_status"] not in QUALIFICATION_STATUSES:
            raise ValueError(f"{record['fixture_id']}: invalid qualification status")
        fixture = ROOT / record["source_fixture_path"]
        task = load_json(fixture / "task.json")
        acceptance = load_json(fixture / "expected" / "acceptance.json")
        if task.get("task_id") != record["fixture_id"]:
            raise ValueError(f"{record['fixture_id']}: task ID mismatch")
        if acceptance.get("task_id") != record["fixture_id"]:
            raise ValueError(f"{record['fixture_id']}: acceptance ID mismatch")
        for artifact in task.get("input_artifacts", []):
            path = (fixture / artifact["path"]).resolve()
            if fixture.resolve() not in path.parents or not path.is_file():
                raise ValueError(f"{record['fixture_id']}: invalid declared input path")
    expected = build_frame()
    if frame != expected:
        raise ValueError("document-ops-v1.json is stale; rebuild with --write")


def write_frame(frame: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(frame, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the generated frame before validation")
    args = parser.parse_args()
    frame = build_frame()
    if args.write:
        write_frame(frame)
    if not OUTPUT.is_file():
        raise ValueError(f"generated frame is missing: {OUTPUT}")
    validate_frame(load_json(OUTPUT))
    counts = frame["summary"]["status_counts"]
    print(f"document ops frame validation: PASS (48 fixtures; statuses={counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

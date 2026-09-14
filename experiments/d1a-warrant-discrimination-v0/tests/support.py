from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import common  # noqa: E402


UNOBSERVED = {
    "task_oracle": ["perturbation_assignment", "future_policy_decisions", "heldout_producer_outputs"],
    "authority_policy": ["realized_correctness", "heldout_outcomes", "policy_scores"],
    "semantic_verifier": ["heldout_oracle_labels", "authority_map", "perturbation_labels", "policy_outputs"],
    "calibration": ["heldout_d1_outcomes", "d1_warrant_labels", "authority_labels", "policy_outputs"],
    "analysis": ["heldout_results_before_analysis_freeze", "ability_to_revise_upstream_assets"],
}


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def role_payload(role: str, asset_path: str) -> dict[str, Any]:
    if role == "task_oracle":
        return {
            "task_families": [
                {"task_family_id": "family-a", "task_contract_path": asset_path, "instance_ids_path": asset_path, "oracle_id": "oracle-a", "post_state_oracle_path": asset_path},
                {"task_family_id": "family-b", "task_contract_path": asset_path, "instance_ids_path": asset_path, "oracle_id": "oracle-b", "post_state_oracle_path": asset_path},
            ],
            "oracle_rules_path": asset_path,
            "stable_instance_id_rule": "custodian supplied stable IDs",
            "perturbation_assignment_observed": False,
            "future_policy_decisions_observed": False,
            "heldout_producer_outputs_observed": False,
            "task_truth_separate_from_authorization": True,
            "consequential_action_family": "included_reversible",
        }
    if role == "authority_policy":
        return {
            "policy_id": "authority-v1",
            "policy_path": asset_path,
            "principal_registry_path": asset_path,
            "authorization_classes_path": asset_path,
            "conformance_rule_path": asset_path,
            "derived_from_realized_correctness": False,
            "realized_correctness_observed": False,
            "correctness_authorization_divergence_supported": True,
        }
    if role == "semantic_verifier":
        return {
            "verifier_id": "semantic-v1",
            "verifier_version": "1",
            "verifier_path": asset_path,
            "semantic_scope_path": asset_path,
            "development_material_path": asset_path,
            "development_heldout_disjoint": True,
            "heldout_oracle_labels_observed": False,
            "authority_map_observed": False,
            "perturbation_labels_observed": False,
            "policy_outputs_observed": False,
            "failure_cases": {
                "false_accept": ["fa-1"], "false_reject": ["fr-1"],
                "disagreement": ["d-1"], "error": ["e-1"], "unknown": ["u-1"]
            },
            "known_blind_spots": ["bounded fixture blind spot"],
        }
    if role == "calibration":
        return {
            "calibration_status": "available",
            "producer_configuration_id": "exact-producer-v1",
            "configuration_identity_path": asset_path,
            "score_construction_path": asset_path,
            "score_excludes_warrant_authority_labels": True,
            "calibration_split_path": asset_path,
            "heldout_split_path": asset_path,
            "splits_disjoint": True,
            "heldout_d1_outcomes_observed": False,
            "sample_size": 20,
            "diagnostics_path": asset_path,
            "thresholds_path": asset_path,
            "thresholds_frozen_before_heldout": True,
            "unavailability_reason": None,
        }
    if role == "analysis":
        return {
            "analysis_plan_path": asset_path,
            "sealed_inputs_only": True,
            "heldout_results_observed_before_analysis_freeze": False,
            "may_revise_upstream_assets": False,
            "full_vector_reporting": True,
            "rivals_compared": ["R1", "R2", "R3", "R4", "R5"],
            "r5_decomposition_required": True,
            "non_identifying_strata_quarantined": True,
            "weighted_loss_enabled": False,
        }
    raise ValueError(role)


def reseal(bundle: dict[str, Any]) -> None:
    bundle["seal"]["manifest_sha256"] = common.bundle_manifest_sha256(bundle)


def make_bundle(role: str, root: Path, *, independent: bool = True) -> dict[str, Any]:
    asset_name = f"{role}-asset.json"
    evidence_name = f"{role}-independence.txt"
    asset_path = root / asset_name
    evidence_path = root / evidence_name
    write_text(asset_path, json.dumps({"role": role, "content": "bounded neutral asset"}, sort_keys=True))
    write_text(evidence_path, f"independent authoring record for {role}\n")
    bundle = {
        "schema_version": 1,
        "d1_contract_version": "d1a-v0",
        "bundle_id": f"bundle-{role}-v1",
        "bundle_version": 1,
        "custodian_role": role,
        "provenance_identity": {
            "custodian_id": f"custodian-{role}",
            "authoring_session_id": f"session-{role}",
            "identity_kind": "human",
        },
        "created_at": "2026-09-14T10:00:00+08:00",
        "assets": [{"path": asset_name, "sha256": common.sha256_path(asset_path), "media_type": "application/json"}],
        "declared_dependencies": [],
        "observed_dependencies": [],
        "prohibited_dependencies": ["coordinator_authored_heldout_assets"],
        "information_observed_before_freeze": ["public_d1a_contract"],
        "information_not_observed_before_freeze": UNOBSERVED[role],
        "independence_evidence": [{
            "path": evidence_name,
            "sha256": common.sha256_path(evidence_path),
            "evidence_kind": "independent_authoring_record",
            "reviewer_id": f"reviewer-{role}",
        }],
        "seal": {"status": "sealed", "sealed_at": "2026-09-14T11:00:00+08:00", "manifest_sha256": None},
        "post_seal_mutations": [],
        "version_history": [],
        "attestation": {
            "attestation_id": f"attestation-{role}",
            "attested_by": f"custodian-{role}",
            "attested_at": "2026-09-14T11:00:00+08:00",
            "independent_authorship_claim": independent,
            "coordinator_session_not_used_for_authorship": True,
            "prohibited_information_observed": False,
            "statements": ["information boundary observed"],
        },
        "role_payload": role_payload(role, asset_name),
    }
    reseal(bundle)
    return bundle


def write_bundle(root: Path, bundle: dict[str, Any]) -> Path:
    path = root / f"{bundle['custodian_role']}.bundle.json"
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

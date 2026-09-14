#!/usr/bin/env python3
"""Run deterministic instrument-only D1a meta-qualification."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from common import (
    DEFINITION_ROOT,
    D1aValidationError,
    PACKAGE_ROOT,
    canonical_json_bytes,
    load_json,
    pretty_json,
    sha256_bytes,
    validate_all_schemas,
)
from evaluate_policies import evaluate_batch, validate_episode


META_ROOT = PACKAGE_ROOT / "meta-fixtures"


def _digest(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def expand_case(case: dict[str, Any]) -> dict[str, Any]:
    group = case["identity_group"]
    evidence_state = case["evidence_state"]
    evidence_items = [
        {"evidence_id": "required-evidence", "digest": _digest(group + ":required-evidence"), "required": True, "relevant": True}
    ]
    validity = [{"evidence_id": "required-evidence", "status": "valid"}]
    binding = [{"evidence_id": "required-evidence", "status": "bound"}]
    if evidence_state == "invalid":
        validity[0]["status"] = "invalid"
    elif evidence_state == "non_binding":
        binding[0]["status"] = "non_binding"
    elif evidence_state == "absent":
        validity[0]["status"] = "absent"
        binding[0]["status"] = "absent"
    elif evidence_state == "unknown":
        validity[0]["status"] = "unknown"
        binding[0]["status"] = "unknown"
    elif evidence_state == "valid_bound_extra":
        evidence_items.append(
            {"evidence_id": "irrelevant-extra", "digest": _digest(group + ":irrelevant-extra"), "required": False, "relevant": False}
        )
        validity.append({"evidence_id": "irrelevant-extra", "status": "valid"})
        binding.append({"evidence_id": "irrelevant-extra", "status": "bound"})
    elif evidence_state != "valid_bound":
        raise D1aValidationError(f"unknown meta evidence state: {evidence_state}")

    semantic = case["semantic_verifier_decision"]
    actual = case["actual_outcome"]
    if semantic == "error":
        disagreement = {"status": "error", "reference_decision": "unknown"}
    elif semantic == "unknown":
        disagreement = {"status": "unknown", "reference_decision": "unknown"}
    elif semantic == "disagreement":
        disagreement = {"status": "disagreement", "reference_decision": "unknown"}
    elif (semantic == "accept" and actual == "failure"):
        disagreement = {"status": "disagreement", "reference_decision": "reject"}
    elif (semantic == "reject" and actual == "success"):
        disagreement = {"status": "disagreement", "reference_decision": "accept"}
    else:
        disagreement = {
            "status": "agreement" if actual != "unknown" else "unknown",
            "reference_decision": "accept" if actual == "success" else ("reject" if actual == "failure" else "unknown"),
        }

    action = case["action_outcome"]
    raw_outcome_digest = _digest(f"{group}:actual={actual}:action={action}")
    return {
        "episode_id": case["case_id"],
        "task_family_id": case["task_family_id"],
        "task_instance_id": group,
        "task_contract_digest": _digest(case["task_family_id"] + ":contract"),
        "producer_configuration_id": "meta-producer-v0",
        "producer_output_digest": _digest(group + ":producer-output"),
        "producer_claim": {"status": "success", "content_digest": _digest(group + ":producer-claim")},
        "producer_score_or_calibrated_probability": case["calibrated_probability"],
        "actual_outcome": actual,
        "actual_outcome_oracle_id": "meta-oracle-v0",
        "evidence_items": evidence_items,
        "evidence_validity": validity,
        "evidence_binding": binding,
        "authority_required": case["authority_required"],
        "authority_policy_id": "meta-authority-v0" if case["authority_required"] else "not_applicable",
        "authority_mapping": case["authority_mapping"],
        "authorization_conformance": case["authorization_conformance"],
        "semantic_verifier_id": "meta-semantic-verifier-v0",
        "semantic_verifier_decision": semantic,
        "semantic_verifier_confidence_or_not_measured": "not_measured",
        "independent_disagreement_record": disagreement,
        "policy_decisions": {},
        "commitment_record": {
            "consequential_action_exposed": case["consequential_action_exposed"],
            "action_class": "meta-reversible-commit" if case["consequential_action_exposed"] else "record-only",
            "reversible": True if case["consequential_action_exposed"] else "not_applicable",
        },
        "action_outcome": action,
        "resource_record": {
            "execution_units": 1,
            "semantic_verification_units": 1,
            "evidence_verification_units": 1,
            "authority_adjudication_units": 1,
            "base_adjudication_units": 1,
            "provider_model_calls": 0,
            "retries": 0,
            "latency_ms": "unknown",
            "latency_credible": False,
            "human_manual_cost": "unknown",
        },
        "provenance": {
            "fixture_only": True,
            "source_bundle_ids": [],
            "sealed_input_digest": sha256_bytes(canonical_json_bytes(case)),
        },
        "meta": {
            "region_ids": case["region_ids"],
            "semantic_input_digest": _digest(group + ":semantic-input"),
            "raw_outcome_digest": raw_outcome_digest,
            "audit_resolution_improved": case["audit_resolution_improved"],
            "decomposition_assessment": case["decomposition_assessment"],
        },
    }


def load_meta() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases_doc = load_json(META_ROOT / "cases.json")
    if cases_doc.get("fixture_only") is not True:
        raise D1aValidationError("meta cases must be marked fixture_only")
    episodes = [expand_case(case) for case in cases_doc["cases"]]
    calibration = load_json(META_ROOT / "calibration.json")
    if calibration.get("fixture_only") is not True:
        raise D1aValidationError("meta calibration must be marked fixture_only")
    return episodes, calibration


def _indexed(evaluation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["episode_id"]: row for row in evaluation["evaluated_episodes"]}


def qualify() -> dict[str, Any]:
    schema_findings = validate_all_schemas()
    definition_findings: list[str] = []
    for path in sorted(DEFINITION_ROOT.glob("*.json")):
        value = load_json(path)
        if not isinstance(value, dict):
            definition_findings.append(f"{path.name}:top_level_not_object")

    episodes, calibration = load_meta()
    episode_findings = {
        row["episode_id"]: validate_episode(row) for row in episodes if validate_episode(row)
    }
    first = evaluate_batch(episodes, calibration)
    second = evaluate_batch(episodes, calibration)
    deterministic = canonical_json_bytes(first) == canonical_json_bytes(second)
    rows = _indexed(first)

    def decision(case_id: str, policy_id: str) -> dict[str, str]:
        return rows[case_id]["decisions"][policy_id]

    no_authority = decision("control-no-authority", "P3") == decision("control-no-authority", "P2")
    no_warrant = (
        decision("control-no-warrant-increment", "P1")
        == decision("control-no-warrant-increment", "P2")
        == decision("control-no-warrant-increment", "P3")
    )
    volume = all(
        decision("control-evidence-volume-base", policy_id)
        == decision("control-evidence-volume-extra", policy_id)
        for policy_id in ("P2", "P3")
    )

    episode_map = {row["episode_id"]: row for row in episodes}
    authority_a = episode_map["control-authority-canonical"]
    authority_b = episode_map["control-authority-unauthorized"]
    fixed_fields = [
        "task_family_id", "task_instance_id", "task_contract_digest", "producer_configuration_id",
        "producer_output_digest", "producer_claim", "producer_score_or_calibrated_probability",
        "actual_outcome", "actual_outcome_oracle_id", "semantic_verifier_id",
        "semantic_verifier_decision", "action_outcome"
    ]
    authority_invariance = (
        all(authority_a[field] == authority_b[field] for field in fixed_fields)
        and authority_a["meta"]["semantic_input_digest"] == authority_b["meta"]["semantic_input_digest"]
        and authority_a["meta"]["raw_outcome_digest"] == authority_b["meta"]["raw_outcome_digest"]
        and all(
            decision("control-authority-canonical", policy_id)
            == decision("control-authority-unauthorized", policy_id)
            for policy_id in ("P0", "P1", "P2")
        )
        and decision("control-authority-canonical", "P3")
        != decision("control-authority-unauthorized", "P3")
    )

    r1 = (
        decision("r1-calibration-preserves-success", "P0")["decision"] == "accept_commit"
        and decision("r1-calibration-preserves-success", "P1")["decision"] == "reject"
        and episode_map["r1-calibration-preserves-success"]["actual_outcome"] == "success"
        and len(rows["r1-calibration-preserves-success"]["field_access"]["P0"])
        < len(rows["r1-calibration-preserves-success"]["field_access"]["P1"])
    )
    r2 = (
        decision("r2-semantic-catches-failure", "P0")["decision"] == "accept_commit"
        and decision("r2-semantic-catches-failure", "P1")["decision"] == "reject"
        and decision("r2-semantic-catches-failure", "P1")
        == decision("r2-semantic-catches-failure", "P2")
        == decision("r2-semantic-catches-failure", "P3")
        and episode_map["r2-semantic-catches-failure"]["actual_outcome"] == "failure"
    )
    r3 = (
        episode_map["r3-record-only-resolution"]["meta"]["audit_resolution_improved"]
        and episode_map["r3-record-only-resolution"]["commitment_record"]["consequential_action_exposed"] is False
        and episode_map["r3-record-only-resolution"]["action_outcome"] == "not_applicable"
    )
    r4 = (
        decision("r4-incremental-authority-prevents-harm", "P2")["decision"] == "accept_commit"
        and decision("r4-incremental-authority-prevents-harm", "P3")["decision"] == "reject"
        and episode_map["r4-incremental-authority-prevents-harm"]["actual_outcome"] == "success"
        and episode_map["r4-incremental-authority-prevents-harm"]["action_outcome"] == "failure"
        and episode_map["r4-incremental-authority-prevents-harm"]["meta"]["decomposition_assessment"] == "not_exhausted"
    )
    r5_cases = [row for row in episodes if "R5" in row["meta"]["region_ids"]]
    r5 = (
        len(r5_cases) >= 2
        and all(row["meta"]["decomposition_assessment"] == "exhaustive" for row in r5_cases)
        and decision("r5-factorized-evidence-term", "P1")["decision"] == "accept_commit"
        and decision("r5-factorized-evidence-term", "P2")["decision"] == "reject"
        and decision("r5-factorized-authorization-term", "P2")["decision"] == "accept_commit"
        and decision("r5-factorized-authorization-term", "P3")["decision"] == "reject"
    )

    verifier_control = (
        episode_map["control-verifier-false-accept"]["actual_outcome"] == "failure"
        and episode_map["control-verifier-false-accept"]["semantic_verifier_decision"] == "accept"
        and episode_map["control-verifier-false-reject"]["actual_outcome"] == "success"
        and episode_map["control-verifier-false-reject"]["semantic_verifier_decision"] == "reject"
        and episode_map["control-verifier-disagreement"]["semantic_verifier_decision"] == "disagreement"
        and episode_map["control-verifier-error"]["semantic_verifier_decision"] == "error"
        and episode_map["control-verifier-unknown"]["semantic_verifier_decision"] == "unknown"
    )

    vector = first["outcome_vectors"]
    required_vector_keys = {
        "episode_count", "actual_task", "false_commitment_actual", "false_commitment_action",
        "false_rejection", "unverified_success", "abstention", "authorization_error",
        "verifier", "invalid_record_count", "adjudication_reproducibility", "resources"
    }
    complete_vector = all(
        required_vector_keys.issubset(vector[policy_id]["all"])
        and vector[policy_id]["task_families"]
        for policy_id in ("P0", "P1", "P2", "P3")
    )
    unknown_preserved = all(
        vector[policy_id]["all"]["actual_task"]["unknown"]["count"] > 0
        and vector[policy_id]["all"]["resources"]["human_manual_cost"]["value"] == "unknown"
        and vector[policy_id]["all"]["resources"]["latency_ms"]["value"] == "unknown"
        for policy_id in ("P0", "P1", "P2", "P3")
    )
    zero_calls = all(
        vector[policy_id]["all"]["resources"]["provider_model_calls"]["value"] == 0
        and vector[policy_id]["all"]["resources"]["retries"]["value"] == 0
        for policy_id in ("P0", "P1", "P2", "P3")
    )

    checks = {
        "definition_json_valid": not definition_findings,
        "submission_schemas_valid": not schema_findings,
        "episodes_schema_valid": not episode_findings,
        "R1_win_region": r1,
        "R2_win_region": r2,
        "R3_win_region": r3,
        "R4_win_region": r4,
        "R5_win_region": r5,
        "no_authority_P3_equals_P2_bit_for_bit": no_authority,
        "no_warrant_increment_P1_equals_P2_equals_P3": no_warrant,
        "evidence_volume_invariance": volume,
        "outcome_fixed_authority_invariance": authority_invariance,
        "verifier_failures_represented": verifier_control,
        "record_only_no_action_benefit": r3,
        "unknown_preserved": unknown_preserved,
        "complete_outcome_vector": complete_vector,
        "deterministic_rerun_identity": deterministic,
        "provider_model_calls_and_retries_zero": zero_calls,
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "status": "PASS" if passed else "FAIL",
        "evidence_class": "instrument_behavior_only",
        "d1_empirical_qualification": False,
        "checks": checks,
        "findings": {
            "schema": schema_findings,
            "definition": definition_findings,
            "episode": episode_findings,
        },
        "episode_count": len(episodes),
        "task_family_count": len({row["task_family_id"] for row in episodes}),
        "terminal_readiness_state": "ready_for_independent_custodian_submission" if passed else "ready_for_meta_qualification",
        "provider_model_calls": 0,
    }


def main() -> int:
    try:
        result = qualify()
    except (D1aValidationError, KeyError, TypeError, ValueError) as exc:
        result = {"status": "FAIL", "errors": [str(exc)], "provider_model_calls": 0}
    sys.stdout.write(pretty_json(result))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

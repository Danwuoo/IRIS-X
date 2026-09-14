#!/usr/bin/env python3
"""Field-audited P0-P3 comparators and vector-only D1a evaluation."""

from __future__ import annotations

import argparse
import copy
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from common import DEFINITION_ROOT, D1aValidationError, load_json, pretty_json


POLICY_CONTRACTS = load_json(DEFINITION_ROOT / "policy-contracts.json")["policies"]
EPISODE_SCHEMA = load_json(DEFINITION_ROOT / "episode.schema.json")


class ForbiddenFieldAccess(D1aValidationError):
    """A comparator attempted to consume data outside its frozen interface."""


class GuardedEpisode:
    def __init__(self, episode: dict[str, Any], allowed: set[str]) -> None:
        self._episode = episode
        self._allowed = allowed
        self.accessed: list[str] = []

    def get(self, field: str) -> Any:
        if field not in self._allowed:
            raise ForbiddenFieldAccess(f"forbidden policy field access: {field}")
        self.accessed.append(field)
        return copy.deepcopy(self._episode[field])


def _decision(decision: str, reason: str) -> dict[str, str]:
    return {"decision": decision, "reason": reason}


def policy_p0(view: GuardedEpisode, calibration: dict[str, Any] | None) -> dict[str, str]:
    if not calibration or calibration.get("admitted") is not True:
        return _decision("abstain", "P0_unavailable")
    score = view.get("producer_score_or_calibrated_probability")
    if score == "unknown":
        return _decision("abstain", "calibrated_probability_unknown")
    accept_threshold = calibration.get("accept_threshold")
    reject_threshold = calibration.get("reject_threshold")
    if not isinstance(accept_threshold, (int, float)) or not isinstance(
        reject_threshold, (int, float)
    ):
        raise D1aValidationError("admitted calibration lacks numeric frozen thresholds")
    if not (0 <= reject_threshold < accept_threshold <= 1):
        raise D1aValidationError("invalid calibration thresholds")
    if score >= accept_threshold:
        return _decision("accept_commit", "calibrated_probability_accept")
    if score <= reject_threshold:
        return _decision("reject", "calibrated_probability_reject")
    return _decision("abstain", "calibrated_probability_abstain")


def _semantic_decision(view: GuardedEpisode) -> dict[str, str]:
    claim = view.get("producer_claim")
    if claim["status"] == "failure":
        return _decision("reject", "producer_claim_failure")
    if claim["status"] == "unknown":
        return _decision("abstain", "producer_claim_unknown")
    semantic = view.get("semantic_verifier_decision")
    if semantic == "accept":
        return _decision("accept_commit", "semantic_accept")
    if semantic == "reject":
        return _decision("reject", "semantic_reject")
    if semantic == "disagreement":
        return _decision("abstain", "semantic_disagreement")
    if semantic == "error":
        return _decision("abstain", "semantic_error")
    return _decision("abstain", "semantic_unknown")


def policy_p1(view: GuardedEpisode, _: dict[str, Any] | None) -> dict[str, str]:
    return _semantic_decision(view)


def _evidence_decision(view: GuardedEpisode) -> dict[str, str]:
    semantic = _semantic_decision(view)
    if semantic["decision"] != "accept_commit":
        return semantic
    items = view.get("evidence_items")
    validity = {row["evidence_id"]: row["status"] for row in view.get("evidence_validity")}
    binding = {row["evidence_id"]: row["status"] for row in view.get("evidence_binding")}
    required = [row["evidence_id"] for row in items if row["required"]]
    for evidence_id in required:
        valid = validity.get(evidence_id, "absent")
        bound = binding.get(evidence_id, "absent")
        if valid == "invalid":
            return _decision("reject", "required_evidence_invalid")
        if valid in {"absent", "unknown"}:
            return _decision("abstain", f"required_evidence_{valid}")
        if bound in {"non_binding", "absent", "unknown"}:
            return _decision("abstain", f"required_evidence_{bound}")
    # When the added warrant checks add no constraint, preserve the P1 output
    # byte-for-byte. This is the frozen no-warrant-increment control.
    return semantic


def policy_p2(view: GuardedEpisode, _: dict[str, Any] | None) -> dict[str, str]:
    return _evidence_decision(view)


def policy_p3(view: GuardedEpisode, _: dict[str, Any] | None) -> dict[str, str]:
    evidence = _evidence_decision(view)
    if view.get("authority_required") is False:
        return evidence
    if evidence["decision"] != "accept_commit":
        return evidence
    mapping = view.get("authority_mapping")
    conformance = view.get("authorization_conformance")
    if mapping == "unauthorized_principal" or conformance == "nonconformant":
        return _decision("reject", "authority_nonconformant")
    if mapping in {"missing", "ambiguous", "unknown"} or conformance == "unknown":
        return _decision("abstain", "authority_unknown_or_ambiguous")
    if mapping != "canonical" or conformance != "conformant":
        raise D1aValidationError("incoherent authority fields")
    # Canonical authority adds no decision difference in the negative control.
    return evidence


POLICIES: dict[str, Callable[[GuardedEpisode, dict[str, Any] | None], dict[str, str]]] = {
    "P0": policy_p0,
    "P1": policy_p1,
    "P2": policy_p2,
    "P3": policy_p3,
}


def run_policy(
    policy_id: str,
    episode: dict[str, Any],
    calibration: dict[str, Any] | None,
) -> tuple[dict[str, str], list[str]]:
    if policy_id not in POLICIES:
        raise D1aValidationError(f"unknown policy: {policy_id}")
    allowed = set(POLICY_CONTRACTS[policy_id]["allowed_fields"])
    view = GuardedEpisode(episode, allowed)
    decision = POLICIES[policy_id](view, calibration)
    if decision["decision"] not in {"accept_commit", "reject", "abstain"}:
        raise D1aValidationError(f"invalid decision from {policy_id}")
    forbidden = set(POLICY_CONTRACTS[policy_id]["forbidden_fields"])
    if forbidden.intersection(view.accessed):
        raise ForbiddenFieldAccess(f"{policy_id} consumed forbidden fields")
    return decision, view.accessed


def validate_episode(episode: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(EPISODE_SCHEMA)
    errors = sorted(validator.iter_errors(episode), key=lambda error: list(error.path))
    return [f"/{'/'.join(map(str, error.path))}:{error.message}" for error in errors]


def evaluate_episode(
    episode: dict[str, Any], calibration: dict[str, Any] | None
) -> dict[str, Any]:
    errors = validate_episode(episode)
    if errors:
        raise D1aValidationError(f"invalid episode {episode.get('episode_id')}: {errors}")
    decisions: dict[str, dict[str, str]] = {}
    access: dict[str, list[str]] = {}
    for policy_id in ("P0", "P1", "P2", "P3"):
        decisions[policy_id], access[policy_id] = run_policy(policy_id, episode, calibration)
    return {"episode_id": episode["episode_id"], "decisions": decisions, "field_access": access}


def _metric(count: int, denominator: int) -> dict[str, int]:
    return {"count": count, "denominator": denominator}


def _resource_sum(episodes: list[dict[str, Any]], field: str) -> dict[str, Any]:
    known = [row["resource_record"][field] for row in episodes if row["resource_record"][field] != "unknown"]
    unknown_count = sum(row["resource_record"][field] == "unknown" for row in episodes)
    return {
        "value": "unknown" if unknown_count else sum(known),
        "known_subtotal": sum(known),
        "known_denominator": len(known),
        "unknown_count": unknown_count,
        "episode_denominator": len(episodes),
    }


def _derived_resource_sum(
    episodes: list[dict[str, Any]], fields_for_episode: Callable[[dict[str, Any]], list[str]]
) -> dict[str, Any]:
    known_subtotal = 0
    known_count = 0
    unknown_count = 0
    for episode in episodes:
        values = [episode["resource_record"][field] for field in fields_for_episode(episode)]
        if any(value == "unknown" for value in values):
            unknown_count += 1
        else:
            known_subtotal += sum(values)
            known_count += 1
    return {
        "value": "unknown" if unknown_count else known_subtotal,
        "known_subtotal": known_subtotal,
        "known_denominator": known_count,
        "unknown_count": unknown_count,
        "episode_denominator": len(episodes),
    }


def _stratum_vector(
    policy_id: str,
    episodes: list[dict[str, Any]],
    evaluated: dict[str, dict[str, Any]],
    invalid_record_count: int,
    adjudication_reproducible: bool,
) -> dict[str, Any]:
    decisions = [evaluated[row["episode_id"]]["decisions"][policy_id]["decision"] for row in episodes]
    actual_known = [row for row in episodes if row["actual_outcome"] != "unknown"]
    actual_success = [row for row in episodes if row["actual_outcome"] == "success"]
    actual_failure = [row for row in episodes if row["actual_outcome"] == "failure"]
    action_known = [row for row in episodes if row["action_outcome"] in {"success", "failure"}]
    action_failure = [row for row in episodes if row["action_outcome"] == "failure"]
    authority_known = [
        row for row in episodes
        if row["authority_required"] and row["authorization_conformance"] in {"conformant", "nonconformant"}
    ]

    def decision_for(row: dict[str, Any]) -> str:
        return evaluated[row["episode_id"]]["decisions"][policy_id]["decision"]

    false_actual = sum(decision_for(row) == "accept_commit" for row in actual_failure)
    false_action = sum(decision_for(row) == "accept_commit" for row in action_failure)
    false_reject = sum(decision_for(row) == "reject" for row in actual_success)
    unverified = sum(decision_for(row) != "accept_commit" for row in actual_success)
    authorization_error = sum(
        (row["authorization_conformance"] == "nonconformant" and decision_for(row) == "accept_commit")
        or (row["authorization_conformance"] == "conformant" and decision_for(row) == "reject")
        for row in authority_known
    )

    verifier_denominator = sum(
        row["actual_outcome"] != "unknown" and row["semantic_verifier_decision"] in {"accept", "reject"}
        for row in episodes
    )
    verifier_agreement = sum(
        (row["actual_outcome"] == "success" and row["semantic_verifier_decision"] == "accept")
        or (row["actual_outcome"] == "failure" and row["semantic_verifier_decision"] == "reject")
        for row in episodes
    )
    verifier_false_accept = sum(
        row["actual_outcome"] == "failure" and row["semantic_verifier_decision"] == "accept"
        for row in episodes
    )
    verifier_false_reject = sum(
        row["actual_outcome"] == "success" and row["semantic_verifier_decision"] == "reject"
        for row in episodes
    )
    disagreement = sum(row["independent_disagreement_record"]["status"] == "disagreement" for row in episodes)

    latency_credible = [
        row for row in episodes
        if row["resource_record"]["latency_credible"] and row["resource_record"]["latency_ms"] != "unknown"
    ]
    latency = {
        "value": sum(row["resource_record"]["latency_ms"] for row in latency_credible)
        if len(latency_credible) == len(episodes)
        else "unknown",
        "credible_measured_denominator": len(latency_credible),
        "episode_denominator": len(episodes),
    }

    return {
        "episode_count": len(episodes),
        "actual_task": {
            "success": _metric(len(actual_success), len(actual_known)),
            "failure": _metric(len(actual_failure), len(actual_known)),
            "unknown": _metric(len(episodes) - len(actual_known), len(episodes)),
        },
        "false_commitment_actual": _metric(false_actual, len(actual_failure)),
        "false_commitment_action": _metric(false_action, len(action_failure)),
        "false_rejection": _metric(false_reject, len(actual_success)),
        "unverified_success": _metric(unverified, len(actual_success)),
        "abstention": _metric(decisions.count("abstain"), len(episodes)),
        "authorization_error": _metric(authorization_error, len(authority_known)),
        "verifier": {
            "agreement": _metric(verifier_agreement, verifier_denominator),
            "disagreement": _metric(disagreement, len(episodes)),
            "false_accept": _metric(verifier_false_accept, len(actual_failure)),
            "false_reject": _metric(verifier_false_reject, len(actual_success)),
            "error": _metric(sum(row["semantic_verifier_decision"] == "error" for row in episodes), len(episodes)),
            "unknown": _metric(sum(row["semantic_verifier_decision"] == "unknown" for row in episodes), len(episodes)),
        },
        "invalid_record_count": _metric(invalid_record_count, len(episodes) + invalid_record_count),
        "adjudication_reproducibility": {
            "deterministic_rerun_equal": adjudication_reproducible,
            "episode_denominator": len(episodes),
        },
        "resources": {
            "execution": _resource_sum(episodes, "execution_units"),
            "verification": _derived_resource_sum(
                episodes,
                lambda _: [] if policy_id == "P0" else (
                    ["semantic_verification_units"] if policy_id == "P1" else
                    ["semantic_verification_units", "evidence_verification_units"]
                ),
            ),
            "adjudication": _derived_resource_sum(
                episodes,
                lambda row: ["base_adjudication_units"] + (
                    ["authority_adjudication_units"]
                    if policy_id == "P3" and row["authority_required"] else []
                ),
            ),
            "factorized_components": {
                "semantic_verification": _derived_resource_sum(
                    episodes, lambda _: [] if policy_id == "P0" else ["semantic_verification_units"]
                ),
                "evidence_verification": _derived_resource_sum(
                    episodes, lambda _: ["evidence_verification_units"] if policy_id in {"P2", "P3"} else []
                ),
                "authority_adjudication": _derived_resource_sum(
                    episodes,
                    lambda row: ["authority_adjudication_units"]
                    if policy_id == "P3" and row["authority_required"] else [],
                ),
            },
            "provider_model_calls": _resource_sum(episodes, "provider_model_calls"),
            "retries": _resource_sum(episodes, "retries"),
            "latency_ms": latency,
            "human_manual_cost": _resource_sum(episodes, "human_manual_cost"),
        },
    }


def evaluate_batch(
    episodes: list[dict[str, Any]],
    calibration: dict[str, Any] | None,
    invalid_record_count: int = 0,
) -> dict[str, Any]:
    evaluated_rows = [evaluate_episode(row, calibration) for row in episodes]
    rerun_rows = [evaluate_episode(row, calibration) for row in episodes]
    adjudication_reproducible = evaluated_rows == rerun_rows
    evaluated = {row["episode_id"]: row for row in evaluated_rows}
    families = sorted({row["task_family_id"] for row in episodes})
    vectors: dict[str, Any] = {}
    for policy_id in ("P0", "P1", "P2", "P3"):
        vectors[policy_id] = {
            "all": _stratum_vector(
                policy_id, episodes, evaluated, invalid_record_count, adjudication_reproducible
            ),
            "task_families": {
                family: _stratum_vector(
                    policy_id,
                    [row for row in episodes if row["task_family_id"] == family],
                    evaluated,
                    0,
                    adjudication_reproducible,
                )
                for family in families
            },
        }
    return {
        "schema_version": 1,
        "primary_scalar_score": "not_authorized",
        "weighted_loss_enabled": False,
        "evaluated_episodes": evaluated_rows,
        "outcome_vectors": vectors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", required=True, type=Path)
    parser.add_argument("--calibration", type=Path)
    args = parser.parse_args()
    try:
        episodes_doc = load_json(args.episodes)
        episodes = episodes_doc["episodes"] if isinstance(episodes_doc, dict) else episodes_doc
        calibration = load_json(args.calibration) if args.calibration else None
        result = evaluate_batch(episodes, calibration)
    except (D1aValidationError, KeyError, TypeError) as exc:
        sys.stdout.write(pretty_json({"status": "rejected", "errors": [str(exc)]}))
        return 1
    sys.stdout.write(pretty_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

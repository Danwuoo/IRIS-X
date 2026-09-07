"""Finite deterministic pressure/attribution evaluator for Phase 6 Batch 1.

This is an offline research instrument. It evaluates explicit fixture
predicates and selected immutable Phase 5 artifacts; it does not execute any
deferred capability.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from summarize_assessments import summarize_assessments


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFINITION_DIR = SUBSTRATE / "definition"
GATES_PATH = DEFINITION_DIR / "trigger-gates.json"
VOCABULARY_PATH = DEFINITION_DIR / "attribution-vocabulary.json"
SCHEMA_PATH = DEFINITION_DIR / "assessment-schema.json"
FIXTURE_PATHS = (
    SUBSTRATE / "fixtures" / "synthetic-pressure" / "trigger-cases.json",
    SUBSTRATE / "fixtures" / "attribution-boundaries" / "attribution-cases.json",
    SUBSTRATE / "fixtures" / "phase-5-replay" / "replay-cases.json",
)
EXPECTED_GATE_IDS = (
    "H-G1",
    "H-W1",
    "H-C1",
    "H-R1",
    "runtime_persistence",
    "nondeterministic_verifier",
    "external_action_interception",
    "general_recovery_retry",
)
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class DefinitionError(ValueError):
    """Frozen definition or fixture is malformed."""


class AssessmentError(ValueError):
    """An assessment cannot be derived without violating the finite rules."""


class ReplayConflict(AssessmentError):
    """Direct historical evidence conflicts with the accepted replay contract."""


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def compact_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DefinitionError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DefinitionError(f"top-level JSON object required: {path}")
    return value


def _require_unique_strings(values: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
        raise DefinitionError(f"{label} must be a list of non-empty strings")
    if not allow_empty and not values:
        raise DefinitionError(f"{label} must not be empty")
    if len(values) != len(set(values)):
        raise DefinitionError(f"{label} contains duplicate values")
    return values


def _validate_source_ref(ref: Any, *, verify_bytes: bool) -> None:
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise DefinitionError("malformed source reference")
    path_text = ref["path"]
    digest = ref["sha256"]
    if (
        not isinstance(path_text, str)
        or not path_text
        or "\\" in path_text
        or Path(path_text).is_absolute()
        or ".." in Path(path_text).parts
    ):
        raise DefinitionError("malformed source reference path")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise DefinitionError("malformed source reference SHA-256")
    if verify_bytes:
        path = REPOSITORY_ROOT / path_text
        if not path.is_file():
            raise DefinitionError(f"direct evidence source is missing: {path_text}")
        if sha256_file(path) != digest:
            raise DefinitionError(f"direct evidence source hash mismatch: {path_text}")


def validate_definitions(
    gates_document: dict[str, Any],
    vocabulary: dict[str, Any],
    schema: dict[str, Any],
    *,
    verify_authority: bool = True,
) -> dict[str, dict[str, Any]]:
    if gates_document.get("schema_version") != 1:
        raise DefinitionError("trigger gate schema_version must be 1")
    gates = gates_document.get("gates")
    if not isinstance(gates, list):
        raise DefinitionError("gates must be a list")
    gate_ids = [gate.get("gate_id") for gate in gates if isinstance(gate, dict)]
    if len(gate_ids) != len(gates):
        raise DefinitionError("every gate must be an object with gate_id")
    if len(gate_ids) != len(set(gate_ids)):
        raise DefinitionError("duplicate gate ID")
    if set(gate_ids) != set(EXPECTED_GATE_IDS):
        unknown = sorted(set(gate_ids) - set(EXPECTED_GATE_IDS))
        missing = sorted(set(EXPECTED_GATE_IDS) - set(gate_ids))
        raise DefinitionError(f"unknown or missing gate IDs: unknown={unknown}, missing={missing}")

    required_gate_fields = {
        "gate_id",
        "capability_name",
        "research_status_at_phase5_close",
        "trigger_status_at_phase5_close",
        "required_predicates",
        "negative_controls",
        "source_authority",
    }
    gate_map: dict[str, dict[str, Any]] = {}
    for gate in gates:
        missing_fields = required_gate_fields - set(gate)
        if missing_fields:
            raise DefinitionError(f"{gate['gate_id']} missing required fields: {sorted(missing_fields)}")
        if gate["research_status_at_phase5_close"] != "Not evaluated":
            raise DefinitionError(f"{gate['gate_id']} invalid Phase 5 research status")
        if gate["trigger_status_at_phase5_close"] != "Not triggered":
            raise DefinitionError(f"{gate['gate_id']} invalid Phase 5 trigger status")
        _require_unique_strings(gate["required_predicates"], f"{gate['gate_id']} predicates")
        _require_unique_strings(gate["negative_controls"], f"{gate['gate_id']} controls")
        authority = gate["source_authority"]
        if not isinstance(authority, dict) or set(authority) != {"path", "section", "sha256"}:
            raise DefinitionError(f"{gate['gate_id']} malformed source authority")
        _validate_source_ref(
            {"path": authority["path"], "sha256": authority["sha256"]},
            verify_bytes=verify_authority,
        )
        if not isinstance(authority["section"], str) or not authority["section"]:
            raise DefinitionError(f"{gate['gate_id']} source section is required")
        gate_map[gate["gate_id"]] = gate

    expected_vocabulary = {
        "shortfall_axes": {"task_success", "evidence", "reliability", "lifecycle_cost"},
        "failure_stages": {
            "admission_configuration",
            "identity_authority",
            "execution_producer",
            "verification",
            "state_continuity",
            "control_flow",
            "allocation_capability",
            "external_effect",
            "resource_cost",
            "unknown",
        },
        "attribution_statuses": {
            "directly_supported",
            "inferred",
            "ambiguous",
            "not_attributable",
        },
        "evidence_classes": {
            "direct_repository_evidence",
            "synthetic_fixture",
            "inferred_interpretation",
            "unknown",
            "conflicting_evidence",
        },
        "trigger_results": {
            "not_triggered",
            "triggered_by_fixture",
            "triggered_by_direct_evidence",
            "insufficient_or_ambiguous",
            "conflicting_evidence",
            "invalid_assessment",
        },
        "uncertainty_statuses": {
            "Unknown",
            "Unclear",
            "Not established",
            "Not evaluated",
            "Conflicting evidence",
        },
    }
    if vocabulary.get("schema_version") != 1:
        raise DefinitionError("attribution vocabulary schema_version must be 1")
    if vocabulary.get("status") != "research-local-provisional-non-normative":
        raise DefinitionError("candidate vocabulary must remain research-local and non-normative")
    for field, expected in expected_vocabulary.items():
        values = _require_unique_strings(vocabulary.get(field), field)
        if set(values) != expected:
            raise DefinitionError(f"invalid {field} vocabulary")

    if schema.get("schema_version") != 1:
        raise DefinitionError("assessment schema_version must be 1")
    if schema.get("record_type") != "capability-pressure-assessment-v0":
        raise DefinitionError("unexpected assessment record type")
    if schema.get("status") != "research-local-provisional":
        raise DefinitionError("assessment schema must remain research-local")
    required_assessment_fields = {
        "assessment_id",
        "case_id",
        "suite",
        "fixture_role",
        "evidence_class",
        "source_refs",
        "observed_conditions",
        "shortfall_axes",
        "failure_stage",
        "attribution_status",
        "attribution_reasons",
        "candidate_interventions",
        "capability_trigger_candidates",
        "trigger_results",
        "architecture_research_decision",
        "conflicts",
        "unknowns",
    }
    schema_fields = set(_require_unique_strings(schema.get("required_fields"), "required_fields"))
    if not required_assessment_fields <= schema_fields:
        raise DefinitionError("assessment schema is missing required record fields")
    if schema.get("source_ref_required_fields") != ["path", "sha256"]:
        raise DefinitionError("assessment schema source reference fields changed")
    if schema.get("source_ref_path_policy") != "repository-relative-no-parent-segments":
        raise DefinitionError("assessment schema source reference policy changed")
    if set(schema.get("case_id_prefixes", [])) != {"pressure-", "attribution-", "replay-"}:
        raise DefinitionError("assessment schema case prefixes changed")
    if set(schema.get("suite_values", [])) != {
        "synthetic_pressure",
        "attribution_boundaries",
        "historical_replay",
    }:
        raise DefinitionError("assessment schema suite vocabulary changed")
    if set(schema.get("fixture_roles", [])) != {
        "negative_control",
        "near_trigger",
        "synthetic_positive",
        "collision_boundary",
        "historical_replay",
    }:
        raise DefinitionError("assessment schema fixture-role vocabulary changed")
    return gate_map


def load_definitions() -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    gates_document = load_json(GATES_PATH)
    vocabulary = load_json(VOCABULARY_PATH)
    schema = load_json(SCHEMA_PATH)
    gate_map = validate_definitions(gates_document, vocabulary, schema)
    return gate_map, vocabulary, schema


def evaluate_gate(
    gate: dict[str, Any],
    predicates: dict[str, Any],
    evidence_class: str,
    *,
    negative_controls: Iterable[str] = (),
) -> str:
    required = gate["required_predicates"]
    if set(predicates) != set(required):
        raise AssessmentError(f"{gate['gate_id']} predicate inventory mismatch")
    if any(not isinstance(predicates[item], bool) for item in required):
        raise AssessmentError(f"{gate['gate_id']} predicates must be Boolean")
    controls = list(negative_controls)
    if any(item not in gate["negative_controls"] for item in controls):
        raise AssessmentError(f"{gate['gate_id']} unknown negative control")
    if evidence_class == "conflicting_evidence":
        return "conflicting_evidence"
    if controls:
        return "not_triggered"
    values = [predicates[item] for item in required]
    if all(values):
        if evidence_class == "synthetic_fixture":
            return "triggered_by_fixture"
        if evidence_class == "direct_repository_evidence":
            return "triggered_by_direct_evidence"
        if evidence_class in {"inferred_interpretation", "unknown"}:
            return "insufficient_or_ambiguous"
        raise AssessmentError("invalid evidence class")
    if not any(values):
        return "not_triggered"
    return "insufficient_or_ambiguous"


def _derive_attribution(case: dict[str, Any], vocabulary: dict[str, Any]) -> tuple[list[str], str, str]:
    facts = case.get("attribution_facts")
    if not isinstance(facts, dict) or set(facts) != {"shortfall_axes", "stage_support", "support_kind"}:
        raise AssessmentError(f"{case['case_id']} malformed attribution facts")
    axis_facts = facts["shortfall_axes"]
    stage_facts = facts["stage_support"]
    if not isinstance(axis_facts, dict) or any(
        key not in vocabulary["shortfall_axes"] or not isinstance(value, bool)
        for key, value in axis_facts.items()
    ):
        raise AssessmentError(f"{case['case_id']} invalid shortfall-axis facts")
    if not isinstance(stage_facts, dict) or any(
        key not in vocabulary["failure_stages"] or key == "unknown" or not isinstance(value, bool)
        for key, value in stage_facts.items()
    ):
        raise AssessmentError(f"{case['case_id']} invalid stage-support facts")
    support_kind = facts["support_kind"]
    if support_kind not in {"direct", "inferred", "none"}:
        raise AssessmentError(f"{case['case_id']} invalid support kind")
    axes = [axis for axis in vocabulary["shortfall_axes"] if axis_facts.get(axis, False)]
    stages = [stage for stage in vocabulary["failure_stages"] if stage_facts.get(stage, False)]
    if len(stages) > 1:
        return axes, "unknown", "ambiguous"
    if len(stages) == 1:
        if support_kind == "none":
            raise AssessmentError(f"{case['case_id']} stage support cannot have support_kind none")
        return axes, stages[0], "directly_supported" if support_kind == "direct" else "inferred"
    if support_kind != "none":
        raise AssessmentError(f"{case['case_id']} support kind requires at least one stage")
    return axes, "unknown", "not_attributable"


def _source_objects(case: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for ref in case["source_refs"]:
        path = REPOSITORY_ROOT / ref["path"]
        if path.suffix == ".json":
            values[ref["path"]] = json.loads(path.read_text(encoding="utf-8"))
        else:
            values[ref["path"]] = path.read_text(encoding="utf-8")
    return values


def _batch4_replay_case(case: dict[str, Any]) -> dict[str, Any]:
    sources = _source_objects(case)
    run_ids = ("qualification-20260905-01", "qualification-20260905-02")
    interpretations = []
    terminals = []
    stderr_values = []
    for run_id in run_ids:
        prefix = f"experiments/substrates/model-execution-qualification-v0/runs/{run_id}"
        interpretations.append(sources[f"{prefix}/interpretation.json"])
        terminals.append(sources[f"{prefix}/terminal-record.json"])
        stderr_values.append(sources[f"{prefix}/provider-stderr.txt"])
    expected_classes = {
        "codex-local-config-rejection-before-model-result",
        "codex-local-strict-config-rejection-before-model-result",
    }
    if {item.get("failure_classification") for item in interpretations} != expected_classes:
        raise ReplayConflict("Batch 4 failure classifications changed")
    if any(item.get("model_result_observed") is not False for item in interpretations):
        raise ReplayConflict("Batch 4 unexpectedly contains a model result")
    zero_fields = ("manual_retries", "automatic_retries", "routes", "escalations", "recovery_actions")
    if any(item.get(field) != 0 for item in interpretations for field in zero_fields):
        raise ReplayConflict("Batch 4 zero retry/route/escalation/recovery lineage changed")
    if any(
        terminal.get("actual_outcome") != "failure"
        or terminal.get("terminal_execution_status") != "failed"
        or terminal.get("producer_claim") is not None
        or terminal.get("empirical_evidence_status") != "not_assessed"
        or terminal.get("resource_ledger", {}).get("model_calls") != 1
        or any(
            terminal.get("resource_ledger", {}).get(field) != 0
            for field in ("retry_count", "route_count", "escalation_count", "recovery_count")
        )
        for terminal in terminals
    ):
        raise ReplayConflict("Batch 4 terminal semantics or mechanism counts changed")
    if "reserved built-in provider IDs" not in stderr_values[0] or "tools.view_image" not in stderr_values[1]:
        raise ReplayConflict("Batch 4 exact configuration failure evidence changed")

    derived = copy.deepcopy(case)
    derived.update(
        {
            "observed_conditions": [
                "Run 01 local configuration rejected a reserved provider override before a model result",
                "Run 02 strict configuration rejected tools.view_image before a model result",
                "both accepted terminal records preserve zero retries routes escalations and recovery actions",
            ],
            "attribution_facts": {
                "shortfall_axes": {"task_success": True, "evidence": True},
                "stage_support": {"admission_configuration": True},
                "support_kind": "direct",
            },
            "attribution_reasons": [
                "direct stderr identifies local configuration incompatibility",
                "no model result exists from which model capability could be assessed",
            ],
            "candidate_interventions": ["pre-execution admission for the known configuration class"],
            "capability_trigger_candidates": ["H-C1", "general_recovery_retry"],
            "gate_predicates": {
                "H-C1": {
                    "cheaper_admitted_configuration_misses_requirement": False,
                    "stronger_candidate_plausibly_resolves_miss": False,
                    "decision_relevant_tradeoff_exists": False,
                },
                "general_recovery_retry": {
                    "concrete_failure_class_exists": True,
                    "bounded_recovery_action_specified": False,
                    "side_effect_boundary_safe_and_known": True,
                    "independent_comparison_shows_benefit": False,
                    "action_does_not_hide_configuration_or_semantic_failure": False,
                },
            },
            "gate_negative_controls": {
                "general_recovery_retry": [
                    "configuration_incompatibility_requires_admission_rejection"
                ]
            },
            "unknowns": [
                "model capability failure: Not established",
                "retry requirement: Not established",
                "escalation requirement: Not established",
            ],
            "historical_distinctions": case["expected_historical_distinctions"],
        }
    )
    return derived


def _batch6_replay_case(case: dict[str, Any]) -> dict[str, Any]:
    sources = _source_objects(case)
    summary_path = next(path for path in sources if path.endswith("summaries/batch-6-summary.json"))
    admission_path = next(path for path in sources if path.endswith("admission/current-environment-20260906.json"))
    terminal_paths = sorted(path for path in sources if path.endswith("terminal-record.json"))
    summary = sources[summary_path]
    admission = sources[admission_path]
    terminals = [sources[path] for path in terminal_paths]
    if admission.get("status") != "admitted" or admission.get("live_model_calls") != 0:
        raise ReplayConflict("Batch 6 admission snapshot changed")
    if len(terminals) != 3 or len({item["task_identity"]["task_id"] for item in terminals}) != 3:
        raise ReplayConflict("Batch 6 three-task identity boundary changed")
    configurations = {item["execution_identity"]["configuration_id"] for item in terminals}
    if configurations != {admission.get("configuration_identity")}:
        raise ReplayConflict("Batch 6 no longer uses one shared admitted allocation")
    for terminal in terminals:
        ledger = terminal.get("resource_ledger", {})
        if (
            terminal.get("joint_interpretation") != "verified_success"
            or terminal.get("verified_success_eligibility") is not True
            or terminal.get("actual_outcome") != "success"
            or terminal.get("empirical_evidence_status") != "sufficient"
            or terminal.get("side_effects", {}).get("state_before_sha256")
            != terminal.get("side_effects", {}).get("state_after_sha256")
            or terminal.get("side_effects", {}).get("changed_paths") != []
            or any(
                ledger.get(field) != 0
                for field in ("retry_count", "route_count", "escalation_count", "recovery_count")
            )
        ):
            raise ReplayConflict("Batch 6 terminal success/read-only/mechanism boundary changed")
    if (
        summary.get("verified_successes") != 3
        or summary.get("task_count") != 3
        or any(
            summary.get(field) != 0
            for field in (
                "total_retries",
                "total_routes",
                "total_escalations",
                "total_recovery_actions",
            )
        )
    ):
        raise ReplayConflict("Batch 6 derived summary changed")
    summary_hashes = {item["path"]: item["sha256"] for item in summary["source_terminal_records"]}
    for path in terminal_paths:
        if summary_hashes.get(path) != sha256_file(REPOSITORY_ROOT / path):
            raise ReplayConflict("Batch 6 summary-to-terminal identity changed")

    derived = copy.deepcopy(case)
    derived.update(
        {
            "observed_conditions": [
                "three semantically distinct frozen task identities are present",
                "one shared admitted configuration is used",
                "three of three terminal records are read-only verified successes",
                "retry route escalation and recovery counts are zero",
            ],
            "attribution_facts": {
                "shortfall_axes": {},
                "stage_support": {},
                "support_kind": "none",
            },
            "attribution_reasons": ["no failure is present to attribute"],
            "candidate_interventions": [],
            "capability_trigger_candidates": [
                "H-R1",
                "H-C1",
                "general_recovery_retry",
                "runtime_persistence",
            ],
            "gate_predicates": {
                "H-R1": {
                    "heterogeneous_frozen_task_features_exist": True,
                    "multiple_admissible_allocations_compared": False,
                    "material_outcome_or_resource_difference_observed": False,
                    "feature_dependent_allocation_changes_target_frontier": False,
                },
                "H-C1": {
                    "cheaper_admitted_configuration_misses_requirement": False,
                    "stronger_candidate_plausibly_resolves_miss": False,
                    "decision_relevant_tradeoff_exists": False,
                },
                "general_recovery_retry": {
                    "concrete_failure_class_exists": False,
                    "bounded_recovery_action_specified": False,
                    "side_effect_boundary_safe_and_known": False,
                    "independent_comparison_shows_benefit": False,
                    "action_does_not_hide_configuration_or_semantic_failure": False,
                },
                "runtime_persistence": {
                    "runtime_continuity_required_across_boundary": False,
                    "observable_restoration_or_continuity_oracle_exists": False,
                },
            },
            "gate_negative_controls": {"H-R1": ["semantic_heterogeneity_alone"]},
            "unknowns": [],
            "historical_distinctions": case["expected_historical_distinctions"],
        }
    )
    return derived


def materialize_replay(case: dict[str, Any]) -> dict[str, Any]:
    if case.get("replay_kind") == "phase5_batch4_configuration_failures":
        return _batch4_replay_case(case)
    if case.get("replay_kind") == "phase5_batch6_shared_allocation_success":
        return _batch6_replay_case(case)
    raise AssessmentError(f"{case['case_id']} unknown replay kind")


def validate_case(
    case: dict[str, Any], gate_map: dict[str, dict[str, Any]], vocabulary: dict[str, Any]
) -> None:
    required = {
        "case_id",
        "fixture_role",
        "evidence_class",
        "source_refs",
        "expected_trigger_results",
    }
    if not required <= set(case):
        raise DefinitionError(f"case missing required fields: {sorted(required - set(case))}")
    if not isinstance(case["case_id"], str) or not CASE_ID_RE.fullmatch(case["case_id"]):
        raise DefinitionError("invalid case ID")
    if case["fixture_role"] not in {
        "negative_control",
        "near_trigger",
        "synthetic_positive",
        "collision_boundary",
        "historical_replay",
    }:
        raise DefinitionError(f"{case['case_id']} invalid fixture role")
    if case["evidence_class"] not in vocabulary["evidence_classes"]:
        raise DefinitionError(f"{case['case_id']} invalid evidence class")
    refs = case["source_refs"]
    if not isinstance(refs, list):
        raise DefinitionError(f"{case['case_id']} source_refs must be a list")
    if case["evidence_class"] == "direct_repository_evidence" and not refs:
        raise DefinitionError(f"{case['case_id']} direct evidence requires source references")
    for ref in refs:
        _validate_source_ref(ref, verify_bytes=case["evidence_class"] == "direct_repository_evidence")
    if case["evidence_class"] == "synthetic_fixture" and any(
        value == "triggered_by_direct_evidence"
        for value in case["expected_trigger_results"].values()
    ):
        raise DefinitionError("synthetic evidence cannot masquerade as direct evidence")
    if case["fixture_role"] == "historical_replay" and "gate_predicates" not in case:
        if case.get("replay_kind") not in {
            "phase5_batch4_configuration_failures",
            "phase5_batch6_shared_allocation_success",
        }:
            raise DefinitionError(f"{case['case_id']} unknown replay kind")
        expected_results = case["expected_trigger_results"]
        if not isinstance(expected_results, dict) or any(
            gate_id not in gate_map or result not in vocabulary["trigger_results"]
            for gate_id, result in expected_results.items()
        ):
            raise DefinitionError(f"{case['case_id']} invalid replay trigger expectation")
        expected_attribution = case.get("expected_attribution")
        if (
            not isinstance(expected_attribution, dict)
            or expected_attribution.get("failure_stage") not in vocabulary["failure_stages"]
            or expected_attribution.get("attribution_status") not in vocabulary["attribution_statuses"]
            or not isinstance(expected_attribution.get("shortfall_axes"), list)
            or any(axis not in vocabulary["shortfall_axes"] for axis in expected_attribution["shortfall_axes"])
        ):
            raise DefinitionError(f"{case['case_id']} invalid replay attribution expectation")
        if not isinstance(case.get("expected_historical_distinctions"), dict):
            raise DefinitionError(f"{case['case_id']} historical distinctions are required")
        return

    for field in (
        "observed_conditions",
        "attribution_reasons",
        "candidate_interventions",
        "capability_trigger_candidates",
    ):
        _require_unique_strings(case.get(field), f"{case['case_id']} {field}", allow_empty=True)
    candidates = case["capability_trigger_candidates"]
    if any(gate_id not in gate_map for gate_id in candidates):
        raise DefinitionError(f"{case['case_id']} unknown gate ID")
    predicates_by_gate = case.get("gate_predicates")
    if not isinstance(predicates_by_gate, dict) or set(predicates_by_gate) != set(candidates):
        raise DefinitionError(f"{case['case_id']} gate predicate candidates do not match")
    expected_results = case["expected_trigger_results"]
    if not isinstance(expected_results, dict) or set(expected_results) != set(candidates):
        raise DefinitionError(f"{case['case_id']} expected gate candidates do not match")
    controls_by_gate = case.get("gate_negative_controls", {})
    if not isinstance(controls_by_gate, dict) or any(key not in candidates for key in controls_by_gate):
        raise DefinitionError(f"{case['case_id']} invalid negative-control mapping")
    for gate_id in candidates:
        expected = expected_results[gate_id]
        if expected not in vocabulary["trigger_results"]:
            raise DefinitionError(f"{case['case_id']} invalid expected trigger result")
        actual = evaluate_gate(
            gate_map[gate_id],
            predicates_by_gate[gate_id],
            case["evidence_class"],
            negative_controls=controls_by_gate.get(gate_id, []),
        )
        if actual != expected:
            raise DefinitionError(
                f"{case['case_id']} contradictory expected result for {gate_id}: "
                f"declared={expected}, derived={actual}"
            )
    axes, stage, status = _derive_attribution(case, vocabulary)
    expected_attribution = case.get("expected_attribution")
    if expected_attribution is not None:
        expected_value = {
            "shortfall_axes": axes,
            "failure_stage": stage,
            "attribution_status": status,
        }
        if expected_attribution != expected_value:
            raise DefinitionError(f"{case['case_id']} contradictory expected attribution")


def load_cases(
    gate_map: dict[str, dict[str, Any]], vocabulary: dict[str, Any]
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in FIXTURE_PATHS:
        document = load_json(path)
        if document.get("schema_version") != 1 or not isinstance(document.get("suite"), str):
            raise DefinitionError(f"invalid fixture document: {path}")
        file_cases = document.get("cases")
        if not isinstance(file_cases, list):
            raise DefinitionError(f"fixture cases must be a list: {path}")
        for original in file_cases:
            if not isinstance(original, dict):
                raise DefinitionError(f"fixture case must be an object: {path}")
            case = copy.deepcopy(original)
            case["suite"] = document["suite"]
            validate_case(case, gate_map, vocabulary)
            if case["case_id"] in seen:
                raise DefinitionError(f"duplicate case ID: {case['case_id']}")
            seen.add(case["case_id"])
            cases.append(case)
    return cases


def assess_case(
    original: dict[str, Any], gate_map: dict[str, dict[str, Any]], vocabulary: dict[str, Any]
) -> dict[str, Any]:
    if original["fixture_role"] == "historical_replay":
        try:
            case = materialize_replay(original)
        except ReplayConflict as exc:
            gate_ids = [
                gate_id for gate_id in EXPECTED_GATE_IDS
                if gate_id in original["expected_trigger_results"]
            ]
            return {
                "schema_version": 1,
                "assessment_id": f"assessment:{original['case_id']}",
                "case_id": original["case_id"],
                "suite": original["suite"],
                "fixture_role": original["fixture_role"],
                "assessment_valid": True,
                "expected_result_match": False,
                "evidence_class": "conflicting_evidence",
                "source_refs": sorted(original["source_refs"], key=lambda item: item["path"]),
                "observed_conditions": ["historical replay assertion conflict"],
                "shortfall_axes": [],
                "failure_stage": "unknown",
                "attribution_status": "ambiguous",
                "attribution_reasons": ["accepted historical distinction could not be reproduced"],
                "candidate_interventions": [],
                "capability_trigger_candidates": gate_ids,
                "trigger_results": {gate_id: "conflicting_evidence" for gate_id in gate_ids},
                "architecture_research_decision": "stop_architecture_interpretation",
                "conflicts": [str(exc)],
                "unknowns": [],
            }
        validate_case(case, gate_map, vocabulary)
    else:
        case = original
    axes, failure_stage, attribution_status = _derive_attribution(case, vocabulary)
    gate_ids = [gate_id for gate_id in EXPECTED_GATE_IDS if gate_id in case["capability_trigger_candidates"]]
    controls = case.get("gate_negative_controls", {})
    trigger_results = {
        gate_id: evaluate_gate(
            gate_map[gate_id],
            case["gate_predicates"][gate_id],
            case["evidence_class"],
            negative_controls=controls.get(gate_id, []),
        )
        for gate_id in gate_ids
    }
    attribution = {
        "shortfall_axes": axes,
        "failure_stage": failure_stage,
        "attribution_status": attribution_status,
    }
    expected_match = trigger_results == case["expected_trigger_results"]
    if case.get("expected_attribution") is not None:
        expected_match = expected_match and attribution == case["expected_attribution"]
    if not expected_match:
        raise AssessmentError(f"{case['case_id']} assessment does not match its frozen expectation")
    evidence_class = case["evidence_class"]
    if evidence_class == "synthetic_fixture":
        decision = "fixture_only_no_direct_capability_decision"
    elif evidence_class == "direct_repository_evidence":
        decision = "preserve_phase5_direct_evidence_not_triggered"
    else:
        decision = "no_architecture_decision"
    record = {
        "schema_version": 1,
        "assessment_id": f"assessment:{case['case_id']}",
        "case_id": case["case_id"],
        "suite": case["suite"],
        "fixture_role": case["fixture_role"],
        "assessment_valid": True,
        "expected_result_match": True,
        "evidence_class": evidence_class,
        "source_refs": sorted(case["source_refs"], key=lambda item: item["path"]),
        "observed_conditions": sorted(case["observed_conditions"]),
        "shortfall_axes": axes,
        "failure_stage": failure_stage,
        "attribution_status": attribution_status,
        "attribution_reasons": sorted(case["attribution_reasons"]),
        "candidate_interventions": sorted(case["candidate_interventions"]),
        "capability_trigger_candidates": gate_ids,
        "trigger_results": trigger_results,
        "architecture_research_decision": decision,
        "conflicts": sorted(case.get("conflicts", [])),
        "unknowns": sorted(case.get("unknowns", [])),
    }
    if "historical_distinctions" in case:
        record["historical_distinctions"] = case["historical_distinctions"]
    return record


def assess_all(
    cases: Iterable[dict[str, Any]],
    gate_map: dict[str, dict[str, Any]],
    vocabulary: dict[str, Any],
) -> list[dict[str, Any]]:
    return sorted(
        (assess_case(case, gate_map, vocabulary) for case in cases),
        key=lambda item: item["case_id"],
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def fixture_inventory() -> tuple[list[dict[str, str]], str]:
    inventory = [{"path": _relative(path), "sha256": sha256_file(path)} for path in FIXTURE_PATHS]
    return inventory, sha256_bytes(compact_json_bytes(inventory))


def definition_code_inventory() -> list[dict[str, str]]:
    paths: list[Path] = []
    for directory in (DEFINITION_DIR, SUBSTRATE / "fixtures", SUBSTRATE / "scripts", SUBSTRATE / "tests"):
        paths.extend(path for path in directory.rglob("*") if path.is_file() and path.suffix != ".pyc")
    return [
        {"path": _relative(path), "sha256": sha256_file(path)}
        for path in sorted(set(paths), key=lambda item: item.as_posix())
        if "__pycache__" not in path.parts
    ]


def current_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _validate_full_sha(value: str, label: str) -> None:
    if not FULL_SHA_RE.fullmatch(value):
        raise AssessmentError(f"{label} must be a full lowercase Git SHA")
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{value}^{{commit}}"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise AssessmentError(f"{label} does not resolve to a commit")


def create_authoritative_run(output_dir: Path, starting_sha: str, freeze_sha: str) -> dict[str, Any]:
    _validate_full_sha(starting_sha, "starting_sha")
    _validate_full_sha(freeze_sha, "freeze_sha")
    head = current_head()
    if head != freeze_sha:
        raise AssessmentError("authoritative execution HEAD must equal the definition/code freeze SHA")
    if output_dir.exists():
        raise AssessmentError("authoritative run directory already exists; overwrite is prohibited")

    gate_map, vocabulary, _ = load_definitions()
    cases = load_cases(gate_map, vocabulary)
    assessments = assess_all(cases, gate_map, vocabulary)
    summary = summarize_assessments(assessments, EXPECTED_GATE_IDS)
    output_dir.mkdir(parents=True)
    assessments_path = output_dir / "assessments.json"
    summary_path = output_dir / "summary.json"
    assessments_path.write_bytes(canonical_json_bytes({"schema_version": 1, "assessments": assessments}))
    summary_path.write_bytes(canonical_json_bytes(summary))

    fixtures, fixture_digest = fixture_inventory()
    frozen_inventory = definition_code_inventory()
    historical_refs = sorted(
        (ref for case in cases for ref in case["source_refs"]),
        key=lambda item: item["path"],
    )
    command = (
        "python experiments\\capability-pressure-attribution-v0\\scripts\\assess_pressure.py "
        "--output-dir experiments\\capability-pressure-attribution-v0\\runs\\batch-1-offline "
        f"--starting-sha {starting_sha} --freeze-sha {freeze_sha}"
    )
    manifest = {
        "schema_version": 1,
        "run_id": "phase-6-batch-1-offline",
        "phase": "Phase 6",
        "batch": "Batch 1",
        "authority": "immutable_authoritative_offline_research_instrument_run",
        "starting_sha": starting_sha,
        "definition_code_freeze_sha": freeze_sha,
        "execution_sha": head,
        "model_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
        "model_subprocesses": 0,
        "fixture_inventory": fixtures,
        "fixture_inventory_sha256": fixture_digest,
        "gate_definition_sha256": sha256_file(GATES_PATH),
        "attribution_vocabulary_sha256": sha256_file(VOCABULARY_PATH),
        "assessment_schema_sha256": sha256_file(SCHEMA_PATH),
        "definition_code_inventory": frozen_inventory,
        "definition_code_inventory_sha256": sha256_bytes(compact_json_bytes(frozen_inventory)),
        "historical_replay_sources": historical_refs,
        "historical_replay_sources_sha256": sha256_bytes(compact_json_bytes(historical_refs)),
        "commands_or_procedures": [
            "python experiments\\capability-pressure-attribution-v0\\scripts\\validate_definitions.py",
            "python -m unittest discover -s experiments\\capability-pressure-attribution-v0\\tests -v",
            "python tools\\repository_check.py",
            command,
        ],
        "validation_results": {
            "definition_and_fixture_validation": "PASS",
            "frozen_expectation_evaluation": "PASS",
            "historical_replay_compatibility": "PASS",
            "synthetic_direct_evidence_separation": "PASS",
        },
        "output_artifacts": {
            "assessments.json": sha256_file(assessments_path),
            "summary.json": sha256_file(summary_path),
        },
        "result_category": summary["result_category"],
    }
    (output_dir / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    return manifest


def validate_authoritative_run(output_dir: Path) -> dict[str, Any]:
    manifest_path = output_dir / "manifest.json"
    assessments_path = output_dir / "assessments.json"
    summary_path = output_dir / "summary.json"
    if not all(path.is_file() for path in (manifest_path, assessments_path, summary_path)):
        raise AssessmentError("authoritative run is incomplete")
    manifest = load_json(manifest_path)
    if manifest.get("run_id") != "phase-6-batch-1-offline":
        raise AssessmentError("unexpected authoritative run identity")
    if any(manifest.get(field) != 0 for field in ("model_calls", "provider_calls", "paid_api_calls", "model_subprocesses")):
        raise AssessmentError("authoritative offline run records nonzero provider/model activity")
    for name, expected in manifest["output_artifacts"].items():
        if sha256_file(output_dir / name) != expected:
            raise AssessmentError(f"authoritative output hash mismatch: {name}")
    if sha256_file(GATES_PATH) != manifest["gate_definition_sha256"]:
        raise AssessmentError("gate definitions changed after freeze")
    if sha256_file(VOCABULARY_PATH) != manifest["attribution_vocabulary_sha256"]:
        raise AssessmentError("attribution vocabulary changed after freeze")
    if sha256_file(SCHEMA_PATH) != manifest["assessment_schema_sha256"]:
        raise AssessmentError("assessment schema changed after freeze")
    fixtures, fixture_digest = fixture_inventory()
    if fixtures != manifest["fixture_inventory"] or fixture_digest != manifest["fixture_inventory_sha256"]:
        raise AssessmentError("fixture inventory changed after freeze")
    current_inventory = definition_code_inventory()
    if current_inventory != manifest["definition_code_inventory"]:
        raise AssessmentError("definition/code inventory changed after authoritative execution")
    if sha256_bytes(compact_json_bytes(current_inventory)) != manifest["definition_code_inventory_sha256"]:
        raise AssessmentError("definition/code inventory identity mismatch")
    freeze_sha = manifest["definition_code_freeze_sha"]
    _validate_full_sha(freeze_sha, "definition_code_freeze_sha")
    for item in manifest["definition_code_inventory"]:
        completed = subprocess.run(
            ["git", "show", f"{freeze_sha}:{item['path']}"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
        )
        if completed.returncode != 0 or sha256_bytes(completed.stdout) != item["sha256"]:
            raise AssessmentError(f"freeze commit does not contain frozen bytes: {item['path']}")
    for ref in manifest["historical_replay_sources"]:
        _validate_source_ref(ref, verify_bytes=True)
    gate_map, vocabulary, _ = load_definitions()
    cases = load_cases(gate_map, vocabulary)
    expected_assessments = {"schema_version": 1, "assessments": assess_all(cases, gate_map, vocabulary)}
    if canonical_json_bytes(expected_assessments) != assessments_path.read_bytes():
        raise AssessmentError("authoritative assessments are not deterministic from frozen inputs")
    expected_summary = summarize_assessments(expected_assessments["assessments"], EXPECTED_GATE_IDS)
    if canonical_json_bytes(expected_summary) != summary_path.read_bytes():
        raise AssessmentError("authoritative summary is not deterministic from assessments")
    if any(expected_summary["direct_evidence_triggers_by_gate"].values()):
        raise AssessmentError("selected direct repository evidence unexpectedly triggers a capability")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--starting-sha", required=True)
    parser.add_argument("--freeze-sha", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = create_authoritative_run(args.output_dir, args.starting_sha, args.freeze_sha)
    except (DefinitionError, AssessmentError, OSError, subprocess.SubprocessError) as exc:
        print(f"offline assessment: FAIL ({exc})", file=sys.stderr)
        return 1
    print(
        "offline assessment: PASS "
        f"({manifest['result_category']}; model/provider calls 0/0)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

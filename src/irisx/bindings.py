"""Shared cross-contract and source-provenance validation for P1."""

from __future__ import annotations

from typing import Any

from .artifacts import artifact_ref, validate_artifact
from .canonical import digest_value
from .contracts import (
    DomainSpecification,
    EngineeringTrial,
    RequirementSet,
    SelectionDecision,
    WorkloadDefinition,
    assert_binding,
)
from .errors import ValidationError


def validate_trial_bindings(
    trial: EngineeringTrial,
    specification: DomainSpecification,
    workload: WorkloadDefinition,
    requirements: RequirementSet,
    evaluator: dict[str, Any],
) -> None:
    """Bind the trial authority graph to the exact artifacts being evaluated."""

    evaluator = validate_artifact(evaluator, kind="irisx/evaluator-definition")
    assert_binding(trial.payload["domain_specification_ref"], specification, "trial.domain_specification_ref")
    assert_binding(trial.payload["workload_ref"], workload, "trial.workload_ref")
    assert_binding(trial.payload["requirement_set_ref"], requirements, "trial.requirement_set_ref")
    assert_binding(specification.payload["workload_ref"], workload, "specification.workload_ref")
    assert_binding(specification.payload["requirement_set_ref"], requirements, "specification.requirement_set_ref")
    evaluator_ref = artifact_ref(evaluator)
    if trial.payload["evaluator_ref"] != evaluator_ref:
        raise ValidationError("trial.evaluator_ref: stale or substituted evaluator")
    if workload.payload["evaluator_ref"] != evaluator_ref:
        raise ValidationError("workload.evaluator_ref: stale or substituted evaluator")


def validate_decision_bindings(
    decision: SelectionDecision,
    trial: EngineeringTrial,
    workload: WorkloadDefinition,
    evaluator: dict[str, Any],
) -> None:
    """Bind a selection decision to its exact trial, workload, and evaluator."""

    evaluator = validate_artifact(evaluator, kind="irisx/evaluator-definition")
    assert_binding(decision.payload["trial_ref"], trial, "decision.trial_ref")
    assert_binding(decision.payload["workload_ref"], workload, "decision.workload_ref")
    if decision.payload["evaluator_ref"] != artifact_ref(evaluator):
        raise ValidationError("decision.evaluator_ref: stale or substituted evaluator")


def resolve_case_source(
    cases_artifact: dict[str, Any],
    workload_case: dict[str, Any],
    field: str,
) -> Any:
    """Resolve one case field and verify its complete logical provenance."""

    if field not in {"input", "expected"}:
        raise ValidationError(f"unsupported case source field: {field}")
    cases_artifact = validate_artifact(cases_artifact, kind="irisx/source-collection")
    case_id = workload_case["case_id"]
    cases = cases_artifact["payload"].get("cases")
    if not isinstance(cases, list):
        raise ValidationError("source collection payload.cases must be an array")
    matches = [item for item in cases if isinstance(item, dict) and item.get("case_id") == case_id]
    if len(matches) != 1:
        raise ValidationError(f"case source missing or duplicated: {case_id}")
    source_case = matches[0]
    if source_case.get("segment") != workload_case["segment"]:
        raise ValidationError(f"case source segment mismatch: {case_id}")
    if source_case.get("critical") is not workload_case["critical"]:
        raise ValidationError(f"case source criticality mismatch: {case_id}")
    if field not in source_case:
        raise ValidationError(f"case source field is missing: {case_id}/{field}")
    ref = workload_case[f"{field}_ref"]
    expected_source_id = f"{case_id}-{field}"
    expected_locator = f"cases.json/{case_id}/{field}"
    if ref["source_id"] != expected_source_id:
        raise ValidationError(f"source identity mismatch for {case_id}/{field}")
    if ref["media_type"] != "application/json":
        raise ValidationError(f"source media type mismatch for {case_id}/{field}")
    if ref["locator"] != expected_locator:
        raise ValidationError(f"source locator mismatch for {case_id}/{field}")
    value = source_case[field]
    if digest_value(value) != ref["content_digest"]:
        raise ValidationError(f"source digest mismatch for {case_id}/{field}")
    return value


def validate_source_collection_bindings(
    specification: DomainSpecification,
    workload: WorkloadDefinition,
    cases_artifact: dict[str, Any],
) -> None:
    """Validate Domain Specification material and every workload case source."""

    cases_artifact = validate_artifact(cases_artifact, kind="irisx/source-collection")
    payload = cases_artifact["payload"]
    matches = [
        ref
        for ref in specification.payload["material_refs"]
        if ref["source_id"] == cases_artifact["artifact_id"]
        and ref["media_type"] == "application/json"
        and ref["locator"] == "cases.json"
        and ref["content_digest"] == digest_value(payload)
    ]
    if len(matches) != 1:
        raise ValidationError("Domain Specification must bind exactly one matching source collection")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValidationError("source collection payload.cases must be an array")
    source_ids = [item.get("case_id") for item in cases if isinstance(item, dict)]
    workload_ids = [item["case_id"] for item in workload.payload["cases"]]
    if len(source_ids) != len(cases) or len(set(source_ids)) != len(source_ids) or set(source_ids) != set(workload_ids):
        raise ValidationError("source collection cases do not exactly match the frozen workload")
    for workload_case in workload.payload["cases"]:
        resolve_case_source(cases_artifact, workload_case, "input")
        resolve_case_source(cases_artifact, workload_case, "expected")

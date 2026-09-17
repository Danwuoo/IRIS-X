"""Reproducible Domain Package construction and independent verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import artifact_ref, make_artifact, validate_artifact
from .bundle import document_ref, load_document
from .canonical import digest_bytes, digest_value, read_json, write_json
from .contracts import (
    CandidateConfiguration,
    DomainPackageManifest,
    DomainSpecification,
    EngineeringTrial,
    EvaluationResult,
    RequirementSet,
    SelectionDecision,
    VersionedContract,
    WorkloadDefinition,
    assert_binding,
    load_contract,
)
from .errors import ValidationError
from .engine import satisfies_hard_requirements, validate_result_evidence


def _ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValidationError(f"output directory must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _load_selected(run_dir: Path, decision: SelectionDecision) -> tuple[CandidateConfiguration, EvaluationResult]:
    if decision.payload["outcome"] != "promote":
        raise ValidationError("a Domain Package can only be built from a promote decision")
    config_ref = decision.payload["selected_configuration_ref"]
    result_ref = decision.payload["selected_result_ref"]
    config_paths = [run_dir / "baseline.json", run_dir / "candidate.json"]
    configurations = [load_contract(path, CandidateConfiguration) for path in config_paths if path.is_file()]
    configuration = next((item for item in configurations if item.ref() == config_ref), None)
    if configuration is None:
        raise ValidationError("selected configuration is missing or stale")
    result_paths = sorted((run_dir / "results").glob("*.json"))
    results = [load_contract(path, EvaluationResult) for path in result_paths]
    result = next((item for item in results if item.ref() == result_ref), None)
    if result is None:
        raise ValidationError("selected measured result is missing or stale")
    assert isinstance(configuration, CandidateConfiguration)
    assert isinstance(result, EvaluationResult)
    assert_binding(result.payload["configuration_ref"], configuration, "result.configuration_ref")
    return configuration, result


def _write_document(path: Path, document: VersionedContract | dict[str, Any]) -> None:
    value = document.to_dict() if isinstance(document, VersionedContract) else document
    write_json(path, value)


def build_package(run_dir: Path, output: Path) -> DomainPackageManifest:
    if not run_dir.is_dir():
        raise ValidationError(f"run directory does not exist: {run_dir}")
    _ensure_empty(output)
    specification = load_contract(run_dir / "specification.json", DomainSpecification)
    workload = load_contract(run_dir / "workload.json", WorkloadDefinition)
    requirements = load_contract(run_dir / "requirements.json", RequirementSet)
    trial = load_contract(run_dir / "trial.json", EngineeringTrial)
    decision = load_contract(run_dir / "decision.json", SelectionDecision)
    assert isinstance(specification, DomainSpecification)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    assert isinstance(trial, EngineeringTrial)
    assert isinstance(decision, SelectionDecision)
    configuration, result = _load_selected(run_dir, decision)
    validate_result_evidence(result, workload)
    if not satisfies_hard_requirements(result, requirements):
        raise ValidationError("selected result does not satisfy every hard requirement")
    assert_binding(specification.payload["workload_ref"], workload, "specification.workload_ref")
    assert_binding(specification.payload["requirement_set_ref"], requirements, "specification.requirement_set_ref")
    assert_binding(decision.payload["trial_ref"], trial, "decision.trial_ref")
    assert_binding(result.payload["trial_ref"], trial, "result.trial_ref")
    assert_binding(result.payload["workload_ref"], workload, "result.workload_ref")
    if result.payload["evaluator_ref"] != workload.payload["evaluator_ref"]:
        raise ValidationError("selected result evaluator does not match the frozen workload")

    evaluator = validate_artifact(read_json(run_dir / "evaluator.json"), kind="irisx/evaluator-definition")
    cases = validate_artifact(read_json(run_dir / "cases.json"), kind="irisx/source-collection")
    if artifact_ref(evaluator) != workload.payload["evaluator_ref"]:
        raise ValidationError("evaluator artifact is missing or stale")
    component_ref = configuration.payload["components"].get("workflow_control")
    component_candidates = [run_dir / "baseline-component.json", run_dir / "candidate-component.json"]
    components = [validate_artifact(read_json(path), kind="irisx/reference-component") for path in component_candidates if path.is_file()]
    component = next((item for item in components if artifact_ref(item) == component_ref), None)
    if component is None:
        raise ValidationError("selected configuration component is missing or stale")

    deployment = make_artifact(
        "irisx/deployment-metadata",
        "qualification-deployment-placeholder",
        "1.0.0",
        {
            "status": "placeholder",
            "deployable": False,
            "configuration_ref": configuration.ref(),
            "notes": "P1 does not select a deployment form or production runtime.",
        },
    )
    limitation_values = sorted(set(
        specification.payload["known_limitations"]
        + configuration.payload["known_limitations"]
        + result.payload["known_limitations"]
        + decision.payload["known_limitations"]
    ))
    limitations = make_artifact(
        "irisx/known-limitations",
        "qualification-known-limitations",
        "1.0.0",
        {"limitations": limitation_values},
    )

    documents: dict[str, VersionedContract | dict[str, Any]] = {
        "domain/specification.json": specification,
        "evaluation/workload.json": workload,
        "evaluation/requirements.json": requirements,
        "evaluation/evaluator.json": evaluator,
        "evaluation/cases.json": cases,
        "evaluation/result.json": result,
        "specialization/configuration.json": configuration,
        "specialization/component.json": component,
        "selection/decision.json": decision,
        "trial/trial.json": trial,
        "deployment/metadata.json": deployment,
        "known-limitations.json": limitations,
    }
    for relative, document in sorted(documents.items()):
        _write_document(output / relative, document)

    artifact_entries = []
    for relative, document in sorted(documents.items()):
        path = output / relative
        ref = document_ref(document)
        artifact_entries.append({"path": relative, "kind": ref["kind"], "content_digest": digest_bytes(path.read_bytes())})
    manifest = DomainPackageManifest(
        "qualification-domain-package",
        "1.0.0",
        {
            "domain_specification_ref": specification.ref(),
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "selected_configuration_ref": configuration.ref(),
            "measured_result_ref": result.ref(),
            "selection_decision_ref": decision.ref(),
            "deployment_metadata_ref": artifact_ref(deployment),
            "known_limitations": limitation_values,
            "artifacts": artifact_entries,
        },
    )
    manifest.write(output / "manifest.json")
    verify_package(output)
    return manifest


def _expect_contract(root: Path, relative: str, expected: type[VersionedContract]) -> VersionedContract:
    document = load_document(root / relative)
    if not isinstance(document, expected):
        raise ValidationError(f"{relative}: expected {expected.SCHEMA}")
    return document


def verify_package(root: Path) -> DomainPackageManifest:
    if not root.is_dir():
        raise ValidationError(f"package directory does not exist: {root}")
    manifest = load_contract(root / "manifest.json", DomainPackageManifest)
    assert isinstance(manifest, DomainPackageManifest)
    declared = {entry["path"]: entry for entry in manifest.payload["artifacts"]}
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    expected = set(declared) | {"manifest.json"}
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        raise ValidationError(f"package is missing declared files: {sorted(missing)}")
    if unexpected:
        raise ValidationError(f"package contains unexpected files: {sorted(unexpected)}")

    documents: dict[str, VersionedContract | dict[str, Any]] = {}
    for relative, entry in sorted(declared.items()):
        path = root / relative
        actual_digest = digest_bytes(path.read_bytes())
        if actual_digest != entry["content_digest"]:
            raise ValidationError(f"{relative}: package artifact digest mismatch")
        document = load_document(path)
        if document_ref(document)["kind"] != entry["kind"]:
            raise ValidationError(f"{relative}: package artifact kind mismatch")
        documents[relative] = document

    specification = _expect_contract(root, "domain/specification.json", DomainSpecification)
    workload = _expect_contract(root, "evaluation/workload.json", WorkloadDefinition)
    requirements = _expect_contract(root, "evaluation/requirements.json", RequirementSet)
    result = _expect_contract(root, "evaluation/result.json", EvaluationResult)
    configuration = _expect_contract(root, "specialization/configuration.json", CandidateConfiguration)
    decision = _expect_contract(root, "selection/decision.json", SelectionDecision)
    trial = _expect_contract(root, "trial/trial.json", EngineeringTrial)
    evaluator = documents["evaluation/evaluator.json"]
    deployment = documents["deployment/metadata.json"]
    if not isinstance(evaluator, dict) or not isinstance(deployment, dict):
        raise ValidationError("supporting package artifacts have invalid types")
    refs = manifest.payload
    for field, target in (
        ("domain_specification_ref", specification),
        ("workload_ref", workload),
        ("requirement_set_ref", requirements),
        ("selected_configuration_ref", configuration),
        ("measured_result_ref", result),
        ("selection_decision_ref", decision),
    ):
        if refs[field] != target.ref():
            raise ValidationError(f"manifest.{field}: stale or substituted artifact")
    if refs["evaluator_ref"] != artifact_ref(evaluator):
        raise ValidationError("manifest.evaluator_ref: stale or substituted evaluator")
    if refs["deployment_metadata_ref"] != artifact_ref(deployment):
        raise ValidationError("manifest.deployment_metadata_ref: stale or substituted metadata")
    assert_binding(specification.payload["workload_ref"], workload, "specification.workload_ref")
    assert_binding(specification.payload["requirement_set_ref"], requirements, "specification.requirement_set_ref")
    assert_binding(result.payload["trial_ref"], trial, "result.trial_ref")
    assert_binding(result.payload["workload_ref"], workload, "result.workload_ref")
    assert_binding(result.payload["configuration_ref"], configuration, "result.configuration_ref")
    assert_binding(decision.payload["trial_ref"], trial, "decision.trial_ref")
    if decision.payload["outcome"] != "promote":
        raise ValidationError("packaged decision is not a promotion")
    if decision.payload["selected_configuration_ref"] != configuration.ref() or decision.payload["selected_result_ref"] != result.ref():
        raise ValidationError("packaged decision selection binding failed")
    if result.payload["evaluator_ref"] != artifact_ref(evaluator) or workload.payload["evaluator_ref"] != artifact_ref(evaluator):
        raise ValidationError("package workload/result evaluator binding failed")
    if not satisfies_hard_requirements(result, requirements):
        raise ValidationError("packaged selected result does not satisfy every hard requirement")
    validate_result_evidence(result, workload)
    component = documents["specialization/component.json"]
    if not isinstance(component, dict) or configuration.payload["components"].get("workflow_control") != artifact_ref(component):
        raise ValidationError("package configuration component binding failed")
    if deployment["payload"].get("configuration_ref") != configuration.ref():
        raise ValidationError("deployment metadata configuration binding failed")
    cases = documents["evaluation/cases.json"]
    if not isinstance(cases, dict):
        raise ValidationError("package cases artifact has invalid type")
    for ref in specification.payload["material_refs"]:
        if ref["locator"] != "cases.json" or digest_value(cases["payload"]) != ref["content_digest"]:
            raise ValidationError("package material source binding failed")
    case_by_id = {item.get("case_id"): item for item in cases["payload"].get("cases", [])}
    for case in workload.payload["cases"]:
        source = case_by_id.get(case["case_id"])
        if source is None:
            raise ValidationError(f"package source case is missing: {case['case_id']}")
        for field in ("input", "expected"):
            ref = case[f"{field}_ref"]
            if digest_value(source.get(field)) != ref["content_digest"]:
                raise ValidationError(f"package source digest mismatch: {case['case_id']}/{field}")
    return manifest

"""Reproducible Domain Package construction and independent verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .artifacts import artifact_ref, make_artifact, validate_artifact
from .bindings import validate_decision_bindings, validate_source_collection_bindings, validate_trial_bindings
from .bundle import Document, document_ref, load_bundle, load_document, require_contract, resolve_ref
from .canonical import digest_bytes, read_json, write_json
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
    resolve_logical_path,
)
from .engine import select_configuration, satisfies_hard_requirements, validate_result_evidence
from .errors import ValidationError


RefKey = tuple[str, str, str, str]


def _ref_key(ref: dict[str, Any]) -> RefKey:
    values = tuple(ref[field] for field in ("kind", "artifact_id", "version", "content_digest"))
    return values  # type: ignore[return-value]


def _ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValidationError(f"output directory must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _write_document(path: Path, document: Document) -> None:
    value = document.to_dict() if isinstance(document, VersionedContract) else document
    write_json(path, value)


def _document_index(documents: Iterable[Document]) -> dict[RefKey, Document]:
    index: dict[RefKey, Document] = {}
    for document in documents:
        ref = document_ref(document)
        key = _ref_key(ref)
        if key in index:
            raise ValidationError(f"duplicate packaged document identity: {ref}")
        index[key] = document
    return index


def _semantic_decision_fields(decision: SelectionDecision) -> dict[str, Any]:
    fields = (
        "outcome",
        "trial_ref",
        "workload_ref",
        "evaluator_ref",
        "baseline_result_ref",
        "considered_result_refs",
        "eligible_result_refs",
        "selected_configuration_ref",
        "selected_result_ref",
        "tie_break_rule",
    )
    return {field: decision.payload[field] for field in fields}


def _validate_selection_evidence(
    decision: SelectionDecision,
    trial: EngineeringTrial,
    workload: WorkloadDefinition,
    requirements: RequirementSet,
    index: dict[RefKey, Document],
) -> tuple[CandidateConfiguration, EvaluationResult, list[EvaluationResult], list[CandidateConfiguration]]:
    """Resolve every decision reference and independently recompute selection."""

    baseline_result = require_contract(
        resolve_ref(index, decision.payload["baseline_result_ref"], "decision.baseline_result_ref"),
        EvaluationResult,
        "decision.baseline_result_ref",
    )
    considered = [
        require_contract(
            resolve_ref(index, ref, f"decision.considered_result_refs[{position}]"),
            EvaluationResult,
            f"decision.considered_result_refs[{position}]",
        )
        for position, ref in enumerate(decision.payload["considered_result_refs"])
    ]
    eligible = [
        require_contract(
            resolve_ref(index, ref, f"decision.eligible_result_refs[{position}]"),
            EvaluationResult,
            f"decision.eligible_result_refs[{position}]",
        )
        for position, ref in enumerate(decision.payload["eligible_result_refs"])
    ]
    considered_keys = {_ref_key(item.ref()) for item in considered}
    if _ref_key(baseline_result.ref()) not in considered_keys:
        raise ValidationError("decision baseline result is not part of considered evidence")
    if not {_ref_key(item.ref()) for item in eligible} <= considered_keys:
        raise ValidationError("decision eligible results are not a subset of considered evidence")

    configuration_refs = [trial.payload["baseline_configuration_ref"], *trial.payload["candidate_configuration_refs"]]
    configurations = [
        require_contract(
            resolve_ref(index, ref, f"trial.configuration_refs[{position}]"),
            CandidateConfiguration,
            f"trial.configuration_refs[{position}]",
        )
        for position, ref in enumerate(configuration_refs)
    ]
    configuration_by_digest = {item.content_digest: item for item in configurations}
    if baseline_result.payload["configuration_ref"] != configurations[0].ref():
        raise ValidationError("decision baseline result does not bind the trial baseline configuration")

    result_by_configuration: dict[str, EvaluationResult] = {}
    for result in considered:
        validate_result_evidence(result, workload)
        assert_binding(result.payload["trial_ref"], trial, "result.trial_ref")
        if result.payload["evaluator_ref"] != workload.payload["evaluator_ref"]:
            raise ValidationError("considered result evaluator does not match the frozen workload")
        configuration_digest = result.payload["configuration_ref"]["content_digest"]
        configuration = configuration_by_digest.get(configuration_digest)
        if configuration is None or configuration.ref() != result.payload["configuration_ref"]:
            raise ValidationError("considered result configuration is absent, stale, or outside the trial")
        if configuration_digest in result_by_configuration:
            raise ValidationError("decision contains multiple results for one trial configuration")
        result_by_configuration[configuration_digest] = result

    expected_configuration_digests = {item.content_digest for item in configurations}
    if set(result_by_configuration) != expected_configuration_digests:
        raise ValidationError("decision considered evidence does not cover exactly the trial configurations")
    candidates = [result_by_configuration[item.content_digest] for item in configurations[1:]]
    recomputed = select_configuration(
        trial,
        workload,
        requirements,
        baseline_result,
        candidates,
        configuration_by_digest,
        decision_id=decision.artifact_id,
    )
    if _semantic_decision_fields(decision) != _semantic_decision_fields(recomputed):
        raise ValidationError("selection decision semantics do not match the packaged evidence")
    if decision.payload["outcome"] != "promote":
        raise ValidationError("a Domain Package requires a promote decision")
    selected_result = require_contract(
        resolve_ref(index, decision.payload["selected_result_ref"], "decision.selected_result_ref"),
        EvaluationResult,
        "decision.selected_result_ref",
    )
    selected_configuration = require_contract(
        resolve_ref(index, decision.payload["selected_configuration_ref"], "decision.selected_configuration_ref"),
        CandidateConfiguration,
        "decision.selected_configuration_ref",
    )
    assert_binding(selected_result.payload["configuration_ref"], selected_configuration, "selected_result.configuration_ref")
    if not satisfies_hard_requirements(selected_result, requirements, workload):
        raise ValidationError("selected result does not satisfy every hard requirement")
    return selected_configuration, selected_result, considered, configurations


def build_package(run_dir: Path, output: Path) -> DomainPackageManifest:
    if not run_dir.is_dir():
        raise ValidationError(f"run directory does not exist: {run_dir}")
    _ensure_empty(output)
    run_index = load_bundle(run_dir)
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
    evaluator_document = resolve_ref(run_index, workload.payload["evaluator_ref"], "workload.evaluator_ref")
    if not isinstance(evaluator_document, dict):
        raise ValidationError("evaluator must be a supporting artifact")
    evaluator = validate_artifact(evaluator_document, kind="irisx/evaluator-definition")
    cases = validate_artifact(read_json(run_dir / "cases.json"), kind="irisx/source-collection")
    validate_trial_bindings(trial, specification, workload, requirements, evaluator)
    validate_decision_bindings(decision, trial, workload, evaluator)
    validate_source_collection_bindings(specification, workload, cases)
    selected_configuration, selected_result, considered_results, configurations = _validate_selection_evidence(
        decision, trial, workload, requirements, run_index
    )
    supporting: dict[RefKey, dict[str, Any]] = {}
    for configuration in configurations:
        for component_name, ref in configuration.payload["components"].items():
            document = resolve_ref(run_index, ref, f"configuration.components.{component_name}")
            if not isinstance(document, dict):
                raise ValidationError(f"configuration component {component_name} must be a supporting artifact")
            supporting[_ref_key(ref)] = document
    supporting.pop(_ref_key(artifact_ref(evaluator)), None)

    deployment = make_artifact(
        "irisx/deployment-metadata",
        "qualification-deployment-placeholder",
        "1.0.0",
        {
            "status": "placeholder",
            "deployable": False,
            "configuration_ref": selected_configuration.ref(),
            "notes": "P1 does not select a deployment form or production runtime.",
        },
    )
    limitation_values = sorted(set(
        specification.payload["known_limitations"]
        + selected_configuration.payload["known_limitations"]
        + selected_result.payload["known_limitations"]
        + decision.payload["known_limitations"]
    ))
    limitations = make_artifact(
        "irisx/known-limitations",
        "qualification-known-limitations",
        "1.0.0",
        {"limitations": limitation_values},
    )

    documents: dict[str, Document] = {
        "domain/specification.json": specification,
        "evaluation/workload.json": workload,
        "evaluation/requirements.json": requirements,
        "evaluation/evaluator.json": evaluator,
        "evaluation/cases.json": cases,
        "selection/decision.json": decision,
        "trial/trial.json": trial,
        "deployment/metadata.json": deployment,
        "known-limitations.json": limitations,
    }
    for result in considered_results:
        documents[f"evaluation/results/{result.artifact_id}.json"] = result
    for configuration in configurations:
        documents[f"specialization/configurations/{configuration.artifact_id}.json"] = configuration
    for component in supporting.values():
        documents[f"specialization/components/{component['artifact_id']}.json"] = component
    for relative, document in sorted(documents.items()):
        _write_document(resolve_logical_path(output, relative, f"package artifact {relative}"), document)

    artifact_entries = []
    for relative, document in sorted(documents.items()):
        path = resolve_logical_path(output, relative, f"package artifact {relative}")
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
            "selected_configuration_ref": selected_configuration.ref(),
            "measured_result_ref": selected_result.ref(),
            "selection_decision_ref": decision.ref(),
            "deployment_metadata_ref": artifact_ref(deployment),
            "known_limitations": limitation_values,
            "artifacts": artifact_entries,
        },
    )
    manifest.write(output / "manifest.json")
    verify_package(output)
    return manifest


def _expect_document(documents: dict[str, Document], relative: str, expected: type[VersionedContract]) -> VersionedContract:
    document = documents.get(relative)
    if not isinstance(document, expected):
        raise ValidationError(f"{relative}: expected {expected.SCHEMA}")
    return document


def verify_package(root: Path) -> DomainPackageManifest:
    if not root.is_dir():
        raise ValidationError(f"package directory does not exist: {root}")
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink():
        raise ValidationError("manifest.json must not be a symbolic link")
    manifest = load_contract(manifest_path, DomainPackageManifest)
    assert isinstance(manifest, DomainPackageManifest)
    declared = {entry["path"]: entry for entry in manifest.payload["artifacts"]}
    all_paths = list(root.rglob("*"))
    if any(path.is_symlink() for path in all_paths):
        raise ValidationError("Domain Package must not contain symbolic links")
    actual = {path.relative_to(root).as_posix() for path in all_paths if path.is_file()}
    expected = set(declared) | {"manifest.json"}
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        raise ValidationError(f"package is missing declared files: {sorted(missing)}")
    if unexpected:
        raise ValidationError(f"package contains unexpected files: {sorted(unexpected)}")

    documents: dict[str, Document] = {}
    for relative, entry in sorted(declared.items()):
        path = resolve_logical_path(root, relative, f"manifest artifact {relative}")
        actual_digest = digest_bytes(path.read_bytes())
        if actual_digest != entry["content_digest"]:
            raise ValidationError(f"{relative}: package artifact digest mismatch")
        document = load_document(path)
        if document_ref(document)["kind"] != entry["kind"]:
            raise ValidationError(f"{relative}: package artifact kind mismatch")
        documents[relative] = document
    package_index = _document_index(documents.values())

    specification = _expect_document(documents, "domain/specification.json", DomainSpecification)
    workload = _expect_document(documents, "evaluation/workload.json", WorkloadDefinition)
    requirements = _expect_document(documents, "evaluation/requirements.json", RequirementSet)
    decision = _expect_document(documents, "selection/decision.json", SelectionDecision)
    trial = _expect_document(documents, "trial/trial.json", EngineeringTrial)
    assert isinstance(specification, DomainSpecification)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    assert isinstance(decision, SelectionDecision)
    assert isinstance(trial, EngineeringTrial)
    evaluator_document = resolve_ref(package_index, manifest.payload["evaluator_ref"], "manifest.evaluator_ref")
    deployment_document = resolve_ref(package_index, manifest.payload["deployment_metadata_ref"], "manifest.deployment_metadata_ref")
    if not isinstance(evaluator_document, dict) or not isinstance(deployment_document, dict):
        raise ValidationError("supporting package artifacts have invalid types")
    evaluator = validate_artifact(evaluator_document, kind="irisx/evaluator-definition")
    deployment = validate_artifact(deployment_document, kind="irisx/deployment-metadata")

    refs = manifest.payload
    for field, target in (
        ("domain_specification_ref", specification),
        ("workload_ref", workload),
        ("requirement_set_ref", requirements),
        ("selection_decision_ref", decision),
    ):
        if refs[field] != target.ref():
            raise ValidationError(f"manifest.{field}: stale or substituted artifact")
    validate_trial_bindings(trial, specification, workload, requirements, evaluator)
    validate_decision_bindings(decision, trial, workload, evaluator)
    selected_configuration, selected_result, _, configurations = _validate_selection_evidence(
        decision, trial, workload, requirements, package_index
    )
    if refs["selected_configuration_ref"] != selected_configuration.ref():
        raise ValidationError("manifest.selected_configuration_ref: stale or substituted configuration")
    if refs["measured_result_ref"] != selected_result.ref():
        raise ValidationError("manifest.measured_result_ref: stale or substituted result")
    if refs["evaluator_ref"] != artifact_ref(evaluator):
        raise ValidationError("manifest.evaluator_ref: stale or substituted evaluator")
    if refs["deployment_metadata_ref"] != artifact_ref(deployment):
        raise ValidationError("manifest.deployment_metadata_ref: stale or substituted metadata")
    if workload.payload["evaluator_ref"] != artifact_ref(evaluator):
        raise ValidationError("package workload evaluator binding failed")
    for configuration in configurations:
        for component_name, ref in configuration.payload["components"].items():
            component = resolve_ref(package_index, ref, f"configuration.components.{component_name}")
            if not isinstance(component, dict):
                raise ValidationError(f"configuration component {component_name} has invalid type")
    if deployment["payload"].get("configuration_ref") != selected_configuration.ref():
        raise ValidationError("deployment metadata configuration binding failed")

    cases_document = next(
        (document for document in documents.values() if isinstance(document, dict) and document["schema"] == "irisx/source-collection"),
        None,
    )
    if cases_document is None:
        raise ValidationError("package cases artifact is missing")
    validate_source_collection_bindings(specification, workload, cases_document)
    return manifest

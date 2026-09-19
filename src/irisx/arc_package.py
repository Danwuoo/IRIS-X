"""Profile-specific ARC-AGI-2 Domain Package build and verification."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from .arc_agi2 import SourceProfile, p2_acceptance, score_predictions, validate_source, validate_trial_bundle
from .artifacts import artifact_ref, make_artifact, validate_artifact, write_artifact
from .canonical import digest_bytes, read_json
from .contracts import (
    CandidateConfiguration,
    DomainPackageManifest,
    DomainSpecification,
    EngineeringTrial,
    EvaluationResult,
    RequirementSet,
    SelectionDecision,
    WorkloadDefinition,
    load_contract,
)
from .engine import select_configuration
from .errors import ValidationError
from .kaggle import verify_model_package, verify_result_package
from .transport import digest_path


ARC_LIMITATIONS = [
    "Evaluation covers only the pinned public ARC-AGI-2 evaluation snapshot.",
    "No claim is made about semi-private or private performance.",
    "No ARC Prize or state-of-the-art claim is made.",
    "Only the first minimal specialization intervention was tested.",
]


def _ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValidationError(f"Domain Package output must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _copy_tree(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        relative = path.relative_to(source)
        if ".git" in relative.parts or "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        destination = target / relative
        if path.is_symlink():
            raise ValidationError(f"symbolic link cannot enter Domain Package: {path}")
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)


def _kind(path: Path) -> str:
    if path.suffix == ".json":
        value = read_json(path)
        if isinstance(value, dict) and isinstance(value.get("schema"), str):
            return value["schema"]
        return "application/json"
    if path.suffix == ".zip":
        return "application/zip"
    if path.suffix == ".py":
        return "text/x-python"
    return "application/octet-stream"


def build_arc_package(
    trial_root: Path,
    source_root: Path,
    run_dir: Path,
    model_package: Path,
    outbound_package: Path,
    result_package: Path,
    output: Path,
    *,
    _source_profile: SourceProfile | None = None,
) -> DomainPackageManifest:
    trial = validate_trial_bundle(
        trial_root,
        expected_evaluation_count=(_source_profile or SourceProfile()).evaluation_count,
    )
    validate_artifact(read_json(source_root / "provenance.json"), kind="irisx/arc-source-provenance")
    validate_source(
        source_root,
        profile=_source_profile or SourceProfile(require_git_identity=False),
    )
    _, model_digest = verify_model_package(model_package)
    _, _, result_digest = verify_result_package(result_package, outbound_package, trial_root)
    import_evidence = read_json(run_dir / "import-evidence.json")
    if (
        not isinstance(import_evidence, dict)
        or import_evidence.get("quarantine_package_digest") != result_digest
        or import_evidence.get("trial_package_digest") != digest_path(outbound_package)
        or import_evidence.get("status") != "validated-and-normalized"
    ):
        raise ValidationError("normalized run import evidence is stale or incomplete")
    evaluation = run_dir / "local-evaluation"
    baseline_result = load_contract(evaluation / "baseline-result.json", EvaluationResult)
    candidate_result = load_contract(evaluation / "candidate-result.json", EvaluationResult)
    decision = load_contract(evaluation / "selection.json", SelectionDecision)
    acceptance = validate_artifact(read_json(evaluation / "p2-acceptance.json"), kind="irisx/p2-acceptance")
    assert isinstance(baseline_result, EvaluationResult)
    assert isinstance(candidate_result, EvaluationResult)
    assert isinstance(decision, SelectionDecision)
    if decision.payload["outcome"] != "promote" or decision.payload["selected_result_ref"] != candidate_result.ref():
        raise ValidationError("ARC Domain Package requires generic selection of the Trial 001 candidate")
    if acceptance["payload"].get("accepted") is not True or acceptance["payload"].get("package_eligible") is not True:
        raise ValidationError("ARC Domain Package requires a passing five-point P2 acceptance decision")
    _ensure_empty(output)
    _copy_tree(trial_root, output / "trial-input")
    _copy_tree(source_root / "upstream", output / "source/upstream")
    (output / "source").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_root / "provenance.json", output / "source/provenance.json")
    _copy_tree(evaluation, output / "evaluation/local")
    (output / "evaluation/transport").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(outbound_package, output / "evaluation/transport/trial-input.zip")
    shutil.copyfile(result_package, output / "evaluation/transport/result-package.zip")
    shutil.copyfile(run_dir / "import-evidence.json", output / "evaluation/transport/import-evidence.json")
    (output / "deployment").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(model_package, output / "deployment/model-package.zip")
    runner_source = Path(__file__).with_name("kaggle_runner.py")
    shutil.copyfile(runner_source, output / "deployment/kaggle_runner.py")
    candidate = load_contract(trial_root / "candidate.json", CandidateConfiguration)
    assert isinstance(candidate, CandidateConfiguration)
    deployment = make_artifact(
        "irisx/deployment-metadata",
        "arc-agi-2-offline-research-solver",
        "1.0.0",
        {
            "status": "trial-qualified-offline-research-package",
            "deployable": True,
            "configuration_ref": candidate.ref(),
            "model_package_digest": model_digest,
            "runner_digest": digest_bytes(runner_source.read_bytes()),
            "target": "self-contained single-machine offline ARC-AGI-2 research solver package",
            "network_required": False,
            "known_limitations": ARC_LIMITATIONS,
        },
    )
    write_artifact(output / "deployment/metadata.json", deployment)

    specification = load_contract(trial_root / "specification.json", DomainSpecification)
    workload = load_contract(trial_root / "workload.json", WorkloadDefinition)
    requirements = load_contract(trial_root / "requirements.json", RequirementSet)
    evaluator = validate_artifact(read_json(trial_root / "evaluator.json"), kind="irisx/evaluator-definition")
    assert isinstance(specification, DomainSpecification)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    artifacts = []
    for path in sorted(output.rglob("*"), key=lambda item: item.relative_to(output).as_posix()):
        if path.is_file():
            relative = path.relative_to(output).as_posix()
            artifacts.append({"path": relative, "kind": _kind(path), "content_digest": digest_path(path)})
    manifest = DomainPackageManifest(
        "arc-agi-2-trial-001-domain-package",
        "1.0.0",
        {
            "domain_specification_ref": specification.ref(),
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "selected_configuration_ref": candidate.ref(),
            "measured_result_ref": candidate_result.ref(),
            "selection_decision_ref": decision.ref(),
            "deployment_metadata_ref": artifact_ref(deployment),
            "known_limitations": ARC_LIMITATIONS,
            "artifacts": artifacts,
        },
    )
    manifest.write(output / "manifest.json")
    verify_arc_package(output, _source_profile=_source_profile)
    return manifest


def verify_arc_package(
    root: Path,
    *,
    _source_profile: SourceProfile | None = None,
) -> DomainPackageManifest:
    if not root.is_dir():
        raise ValidationError(f"ARC Domain Package directory does not exist: {root}")
    manifest = load_contract(root / "manifest.json", DomainPackageManifest)
    assert isinstance(manifest, DomainPackageManifest)
    all_paths = list(root.rglob("*"))
    if any(path.is_symlink() for path in all_paths):
        raise ValidationError("ARC Domain Package must not contain symbolic links")
    actual = {path.relative_to(root).as_posix() for path in all_paths if path.is_file()}
    declared_entries = manifest.payload["artifacts"]
    declared = {entry["path"]: entry for entry in declared_entries}
    if len(declared) != len(declared_entries):
        raise ValidationError("ARC Domain Package manifest contains duplicate paths")
    if actual != set(declared) | {"manifest.json"}:
        raise ValidationError("ARC Domain Package closed-world membership mismatch")
    for relative, entry in declared.items():
        path = root.joinpath(*relative.split("/"))
        if digest_path(path) != entry["content_digest"] or _kind(path) != entry["kind"]:
            raise ValidationError(f"ARC Domain Package artifact binding mismatch: {relative}")

    trial_root = root / "trial-input"
    validate_artifact(read_json(trial_root / "solver-cases.json"), kind="irisx/arc-solver-cases")
    validate_trial_bundle(
        trial_root,
        expected_evaluation_count=(_source_profile or SourceProfile()).evaluation_count,
    )
    validate_artifact(read_json(root / "source/provenance.json"), kind="irisx/arc-source-provenance")
    validate_source(
        root / "source",
        profile=_source_profile or SourceProfile(require_git_identity=False),
    )
    _, model_digest = verify_model_package(root / "deployment/model-package.zip")
    _, result_contents, result_digest = verify_result_package(
        root / "evaluation/transport/result-package.zip",
        root / "evaluation/transport/trial-input.zip",
        trial_root,
    )
    import_evidence = read_json(root / "evaluation/transport/import-evidence.json")
    if (
        not isinstance(import_evidence, dict)
        or import_evidence.get("quarantine_package_digest") != result_digest
        or import_evidence.get("trial_package_digest") != digest_path(root / "evaluation/transport/trial-input.zip")
        or import_evidence.get("status") != "validated-and-normalized"
    ):
        raise ValidationError("ARC Domain Package import evidence is stale or incomplete")
    deployment = validate_artifact(read_json(root / "deployment/metadata.json"), kind="irisx/deployment-metadata")
    runner_digest = digest_bytes((root / "deployment/kaggle_runner.py").read_bytes())
    if deployment["payload"].get("model_package_digest") != model_digest or deployment["payload"].get("runner_digest") != runner_digest:
        raise ValidationError("ARC deployment closure is stale or corrupted")
    if deployment["payload"].get("known_limitations") != ARC_LIMITATIONS or manifest.payload["known_limitations"] != ARC_LIMITATIONS:
        raise ValidationError("ARC Domain Package limitations are incomplete or substituted")

    specification = load_contract(trial_root / "specification.json", DomainSpecification)
    workload = load_contract(trial_root / "workload.json", WorkloadDefinition)
    requirements = load_contract(trial_root / "requirements.json", RequirementSet)
    trial = load_contract(trial_root / "trial.json", EngineeringTrial)
    baseline_config = load_contract(trial_root / "baseline.json", CandidateConfiguration)
    candidate_config = load_contract(trial_root / "candidate.json", CandidateConfiguration)
    baseline_result = load_contract(root / "evaluation/local/baseline-result.json", EvaluationResult)
    candidate_result = load_contract(root / "evaluation/local/candidate-result.json", EvaluationResult)
    decision = load_contract(root / "evaluation/local/selection.json", SelectionDecision)
    acceptance = validate_artifact(read_json(root / "evaluation/local/p2-acceptance.json"), kind="irisx/p2-acceptance")
    evaluator = validate_artifact(read_json(trial_root / "evaluator.json"), kind="irisx/evaluator-definition")
    assert isinstance(specification, DomainSpecification)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    assert isinstance(trial, EngineeringTrial)
    assert isinstance(baseline_config, CandidateConfiguration)
    assert isinstance(candidate_config, CandidateConfiguration)
    assert isinstance(baseline_result, EvaluationResult)
    assert isinstance(candidate_result, EvaluationResult)
    assert isinstance(decision, SelectionDecision)
    import json

    observations = json.loads(result_contents["observations/execution.json"].decode("utf-8"))
    baseline_predictions = json.loads(result_contents["predictions/baseline.json"].decode("utf-8"))
    candidate_predictions = json.loads(result_contents["predictions/candidate.json"].decode("utf-8"))
    recomputed_baseline_result = score_predictions(
        trial_root,
        baseline_predictions,
        baseline_config,
        observations,
        result_id=baseline_result.artifact_id,
    )
    recomputed_candidate_result = score_predictions(
        trial_root,
        candidate_predictions,
        candidate_config,
        observations,
        result_id=candidate_result.artifact_id,
    )
    if baseline_result.to_dict() != recomputed_baseline_result.to_dict() or candidate_result.to_dict() != recomputed_candidate_result.to_dict():
        raise ValidationError("ARC Domain Package EvaluationResults do not match recomputed prediction evidence")
    recomputed = select_configuration(
        trial,
        workload,
        requirements,
        baseline_result,
        [candidate_result],
        {baseline_config.content_digest: baseline_config, candidate_config.content_digest: candidate_config},
        decision_id=decision.artifact_id,
    )
    if decision.to_dict() != recomputed.to_dict():
        raise ValidationError("ARC Domain Package selection does not match recomputed evidence")
    recomputed_acceptance = p2_acceptance(baseline_result, candidate_result, requirements, workload)
    if acceptance != recomputed_acceptance:
        raise ValidationError("ARC Domain Package P2 acceptance does not match recomputed evidence")
    if acceptance["payload"]["accepted"] is not True:
        raise ValidationError("ARC Domain Package is ineligible under the P2 acceptance gate")
    refs = manifest.payload
    expected_refs = {
        "domain_specification_ref": specification.ref(),
        "workload_ref": workload.ref(),
        "requirement_set_ref": requirements.ref(),
        "evaluator_ref": artifact_ref(evaluator),
        "selected_configuration_ref": candidate_config.ref(),
        "measured_result_ref": candidate_result.ref(),
        "selection_decision_ref": decision.ref(),
        "deployment_metadata_ref": artifact_ref(deployment),
    }
    for field, expected in expected_refs.items():
        if refs[field] != expected:
            raise ValidationError(f"ARC Domain Package manifest reference is stale: {field}")
    return manifest

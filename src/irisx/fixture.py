"""Synthetic, deterministic, offline P1 qualification fixture."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from .artifacts import artifact_ref, make_artifact, validate_artifact, write_artifact
from .bundle import load_bundle, resolve_ref, require_contract
from .canonical import digest_value, read_json
from .contracts import (
    CandidateConfiguration,
    DomainSpecification,
    EngineeringTrial,
    EvaluationResult,
    RequirementSet,
    WorkloadDefinition,
    assert_binding,
    load_contract,
    resolve_logical_path,
)
from .engine import requirement_verdicts, select_configuration
from .errors import ValidationError


def _source_ref(source_id: str, locator: str, value: Any) -> dict[str, str]:
    return {
        "source_id": source_id,
        "media_type": "application/json",
        "content_digest": digest_value(value),
        "locator": locator,
    }


def _ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValidationError(f"output directory must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def prepare_fixture(output: Path) -> None:
    """Write a wholly synthetic fixture; it is not a product-effectiveness trial."""

    _ensure_empty(output)
    raw_cases = [
        {"case_id": "case-01", "segment": "common", "critical": False, "input": {"token": "alpha"}, "expected": {"label": "allow"}},
        {"case_id": "case-02", "segment": "common", "critical": False, "input": {"token": "beta"}, "expected": {"label": "deny"}},
        {"case_id": "case-03", "segment": "edge", "critical": True, "input": {"token": "gamma"}, "expected": {"label": "deny"}},
        {"case_id": "case-04", "segment": "edge", "critical": False, "input": {"token": "delta"}, "expected": {"label": "allow"}},
    ]
    cases_artifact = make_artifact("irisx/source-collection", "qualification-cases", "1.0.0", {"cases": raw_cases})
    evaluator = make_artifact(
        "irisx/evaluator-definition",
        "exact-label-evaluator",
        "1.0.0",
        {"method": "exact-label-match", "aggregate": ["accuracy", "critical_failures", "segment_accuracy"], "offline": True},
    )
    baseline_component = make_artifact(
        "irisx/reference-component",
        "deterministic-baseline",
        "1.0.0",
        {"adapter": "bounded-lookup", "predictions": {"case-01": "allow", "case-02": "allow", "case-03": "allow", "case-04": "allow"}, "latency_ms": 8},
    )
    candidate_component = make_artifact(
        "irisx/reference-component",
        "deterministic-intervention",
        "1.0.0",
        {"adapter": "bounded-lookup", "predictions": {"case-01": "allow", "case-02": "deny", "case-03": "deny", "case-04": "allow"}, "latency_ms": 10},
    )

    workload_cases = []
    for item in raw_cases:
        case_id = item["case_id"]
        workload_cases.append(
            {
                "case_id": case_id,
                "segment": item["segment"],
                "critical": item["critical"],
                "input_ref": _source_ref(f"{case_id}-input", f"cases.json/{case_id}/input", item["input"]),
                "expected_ref": _source_ref(f"{case_id}-expected", f"cases.json/{case_id}/expected", item["expected"]),
            }
        )
    workload = WorkloadDefinition(
        "qualification-workload",
        "1.0.0",
        {
            "name": "Synthetic label workload",
            "description": "Four fixed synthetic cases used only to qualify the P1 contract flow.",
            "frozen": True,
            "evaluator_ref": artifact_ref(evaluator),
            "cases": workload_cases,
        },
    )
    requirements = RequirementSet(
        "qualification-requirements",
        "1.0.0",
        {
            "name": "P1 qualification requirements",
            "requirements": [
                {"requirement_id": "minimum-accuracy", "metric": "accuracy", "comparator": ">=", "threshold": 0.75, "hard": True, "objective": "maximize", "unit": "ratio", "description": "At least three of four cases must pass."},
                {"requirement_id": "no-critical-failures", "metric": "critical_failures", "comparator": "<=", "threshold": 0, "hard": True, "objective": "minimize", "unit": "count", "description": "Critical fixture cases may not fail."},
                {"requirement_id": "latency-objective", "metric": "latency_ms", "comparator": "<=", "threshold": 12, "hard": False, "objective": "minimize", "unit": "ms", "description": "A soft deterministic latency objective."},
                {"requirement_id": "cost-objective", "metric": "monetary_cost", "comparator": "<=", "threshold": 0, "hard": False, "objective": "minimize", "unit": "usd", "description": "The qualification fixture has observed zero monetary cost."},
            ],
        },
    )
    specification = DomainSpecification(
        "qualification-domain",
        "1.0.0",
        {
            "name": "Synthetic P1 qualification domain",
            "description": "A deliberately non-real domain used only for deterministic product-contract qualification.",
            "material_refs": [_source_ref("qualification-source", "cases.json", cases_artifact["payload"])],
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "operating_constraints": ["offline-only", "no-provider-or-model-calls", "zero-paid-execution"],
            "known_limitations": ["Synthetic labels do not represent a customer domain or demonstrate product effectiveness."],
        },
    )
    baseline = CandidateConfiguration(
        "qualification-baseline",
        "1.0.0",
        {
            "name": "Deterministic baseline",
            "description": "Fixed lookup behavior for qualification only.",
            "components": {"workflow_control": artifact_ref(baseline_component)},
            "complexity": 1,
            "maintainability": "high",
            "known_limitations": ["Intentionally fails selected synthetic cases."],
        },
    )
    candidate = CandidateConfiguration(
        "qualification-candidate",
        "1.0.0",
        {
            "name": "Deterministic candidate intervention",
            "description": "A second fixed lookup table demonstrating an intervention without AI execution.",
            "components": {"workflow_control": artifact_ref(candidate_component), "validation": artifact_ref(evaluator)},
            "complexity": 2,
            "maintainability": "high",
            "known_limitations": ["Behavior is bounded to four fixture case identifiers."],
        },
    )
    trial = EngineeringTrial(
        "qualification-trial",
        "1.0.0",
        {
            "name": "P1 offline qualification fixture",
            "goal": "Prove contract binding, deterministic evaluation, selection, packaging, and verification.",
            "qualification_fixture": True,
            "domain_specification_ref": specification.ref(),
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "baseline_configuration_ref": baseline.ref(),
            "candidate_configuration_refs": [candidate.ref()],
            "stop_conditions": ["any network access", "any provider or model execution", "any non-zero monetary cost"],
        },
    )

    for name, value in (
        ("cases.json", cases_artifact),
        ("evaluator.json", evaluator),
        ("baseline-component.json", baseline_component),
        ("candidate-component.json", candidate_component),
    ):
        write_artifact(output / name, value)
    for name, contract in (
        ("workload.json", workload),
        ("requirements.json", requirements),
        ("specification.json", specification),
        ("baseline.json", baseline),
        ("candidate.json", candidate),
        ("trial.json", trial),
    ):
        contract.write(output / name)


def validate_specification(path: Path) -> DomainSpecification:
    specification = load_contract(path, DomainSpecification)
    assert isinstance(specification, DomainSpecification)
    index = load_bundle(path.parent)
    workload = require_contract(resolve_ref(index, specification.payload["workload_ref"], "specification.workload_ref"), WorkloadDefinition, "specification.workload_ref")
    requirements = require_contract(resolve_ref(index, specification.payload["requirement_set_ref"], "specification.requirement_set_ref"), RequirementSet, "specification.requirement_set_ref")
    if workload.ref() != specification.payload["workload_ref"] or requirements.ref() != specification.payload["requirement_set_ref"]:
        raise ValidationError("specification evidence binding failed")
    resolve_ref(index, workload.payload["evaluator_ref"], "workload.evaluator_ref")
    for ref in specification.payload["material_refs"]:
        source_path = resolve_logical_path(path.parent, ref["locator"], "specification.material_refs.locator")
        source = validate_artifact(read_json(source_path))
        if digest_value(source["payload"]) != ref["content_digest"]:
            raise ValidationError(f"material source digest mismatch: {ref['source_id']}")
    return specification


def validate_trial(path: Path) -> EngineeringTrial:
    trial = load_contract(path, EngineeringTrial)
    assert isinstance(trial, EngineeringTrial)
    index = load_bundle(path.parent)
    specification = require_contract(resolve_ref(index, trial.payload["domain_specification_ref"], "trial.domain_specification_ref"), DomainSpecification, "trial.domain_specification_ref")
    workload = require_contract(resolve_ref(index, trial.payload["workload_ref"], "trial.workload_ref"), WorkloadDefinition, "trial.workload_ref")
    requirements = require_contract(resolve_ref(index, trial.payload["requirement_set_ref"], "trial.requirement_set_ref"), RequirementSet, "trial.requirement_set_ref")
    baseline = require_contract(resolve_ref(index, trial.payload["baseline_configuration_ref"], "trial.baseline_configuration_ref"), CandidateConfiguration, "trial.baseline_configuration_ref")
    assert_binding(specification.payload["workload_ref"], workload, "specification.workload_ref")
    assert_binding(specification.payload["requirement_set_ref"], requirements, "specification.requirement_set_ref")
    for ref in specification.payload["material_refs"]:
        source_path = resolve_logical_path(path.parent, ref["locator"], "specification.material_refs.locator")
        source = validate_artifact(read_json(source_path))
        if digest_value(source["payload"]) != ref["content_digest"]:
            raise ValidationError(f"material source digest mismatch: {ref['source_id']}")
    if workload.payload["evaluator_ref"] != trial.payload["evaluator_ref"]:
        raise ValidationError("trial evaluator does not match frozen workload evaluator")
    resolve_ref(index, trial.payload["evaluator_ref"], "trial.evaluator_ref")
    for index_number, ref in enumerate(trial.payload["candidate_configuration_refs"]):
        require_contract(resolve_ref(index, ref, f"trial.candidate_configuration_refs[{index_number}]"), CandidateConfiguration, f"trial.candidate_configuration_refs[{index_number}]")
    for configuration in [baseline, *(resolve_ref(index, ref, "trial.candidate") for ref in trial.payload["candidate_configuration_refs"])]:
        assert isinstance(configuration, CandidateConfiguration)
        for component_name, component_ref in configuration.payload["components"].items():
            resolve_ref(index, component_ref, f"configuration.components.{component_name}")
    return trial


def _resolve_case_source(cases_artifact: dict[str, Any], case_id: str, field: str, ref: dict[str, Any]) -> Any:
    cases = cases_artifact["payload"]["cases"]
    matches = [item for item in cases if item.get("case_id") == case_id]
    if len(matches) != 1:
        raise ValidationError(f"case source missing or duplicated: {case_id}")
    value = matches[0].get(field)
    if digest_value(value) != ref["content_digest"]:
        raise ValidationError(f"source digest mismatch for {case_id}/{field}")
    expected_locator = f"cases.json/{case_id}/{field}"
    if ref["locator"] != expected_locator:
        raise ValidationError(f"source locator mismatch for {case_id}/{field}")
    return value


def _evaluate(
    trial: EngineeringTrial,
    workload: WorkloadDefinition,
    evaluator: dict[str, Any],
    cases_artifact: dict[str, Any],
    configuration: CandidateConfiguration,
    component: dict[str, Any],
) -> EvaluationResult:
    if evaluator["payload"].get("method") != "exact-label-match" or evaluator["payload"].get("offline") is not True:
        raise ValidationError("unsupported or non-offline evaluator")
    if component["payload"].get("adapter") != "bounded-lookup":
        raise ValidationError("unsupported reference adapter")
    predictions = component["payload"].get("predictions")
    if not isinstance(predictions, dict):
        raise ValidationError("reference component predictions must be an object")
    case_outcomes = []
    segment_totals: dict[str, list[int]] = {}
    for case in workload.payload["cases"]:
        case_id = case["case_id"]
        _resolve_case_source(cases_artifact, case_id, "input", case["input_ref"])
        expected = _resolve_case_source(cases_artifact, case_id, "expected", case["expected_ref"])
        if case_id not in predictions:
            raise ValidationError(f"missing bounded prediction for {case_id}")
        passed = predictions[case_id] == expected["label"]
        critical_failure = bool(case["critical"] and not passed)
        case_outcomes.append(
            {"case_id": case_id, "segment": case["segment"], "passed": passed, "critical_failure": critical_failure, "score": 1 if passed else 0, "detail": "exact match" if passed else "label mismatch"}
        )
        segment = segment_totals.setdefault(case["segment"], [0, 0])
        segment[0] += int(passed)
        segment[1] += 1
    total = len(case_outcomes)
    passed_count = sum(item["passed"] for item in case_outcomes)
    metrics: dict[str, Any] = {
        "accuracy": {"state": "observed", "value": passed_count / total, "unit": "ratio"},
        "critical_failures": {"state": "observed", "value": sum(item["critical_failure"] for item in case_outcomes), "unit": "count"},
        "latency_ms": {"state": "observed", "value": component["payload"]["latency_ms"], "unit": "ms"},
        "monetary_cost": {"state": "observed", "value": 0, "unit": "usd"},
        "complexity": {"state": "observed", "value": configuration.payload["complexity"], "unit": "ordinal"},
        "maintainability": {"state": "not_evaluated", "value": None, "unit": "ordinal"},
    }
    for segment, counts in sorted(segment_totals.items()):
        metrics[f"accuracy.{segment}"] = {"state": "observed", "value": counts[0] / counts[1], "unit": "ratio"}
    return EvaluationResult(
        f"{configuration.artifact_id}-result",
        "1.0.0",
        {
            "trial_ref": trial.ref(),
            "workload_ref": workload.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "configuration_ref": configuration.ref(),
            "cases": case_outcomes,
            "metrics": metrics,
            "resource_use": {
                "network_calls": {"state": "observed", "value": 0, "unit": "count"},
                "provider_calls": {"state": "observed", "value": 0, "unit": "count"},
                "monetary_cost": {"state": "observed", "value": 0, "unit": "usd"},
                "gpu_seconds": {"state": "unknown", "value": None, "unit": "seconds"},
            },
            "known_limitations": ["Synthetic fixed lookup outcomes are qualification evidence only, not product-effectiveness evidence."],
        },
    )


def run_trial(trial_path: Path, output: Path) -> dict[str, Any]:
    trial = validate_trial(trial_path)
    _ensure_empty(output)
    source = trial_path.parent
    index = load_bundle(source)
    workload = require_contract(resolve_ref(index, trial.payload["workload_ref"], "trial.workload_ref"), WorkloadDefinition, "trial.workload_ref")
    requirements = require_contract(resolve_ref(index, trial.payload["requirement_set_ref"], "trial.requirement_set_ref"), RequirementSet, "trial.requirement_set_ref")
    baseline = require_contract(resolve_ref(index, trial.payload["baseline_configuration_ref"], "trial.baseline_configuration_ref"), CandidateConfiguration, "trial.baseline_configuration_ref")
    candidates = [require_contract(resolve_ref(index, ref, "trial.candidate"), CandidateConfiguration, "trial.candidate") for ref in trial.payload["candidate_configuration_refs"]]
    evaluator_doc = resolve_ref(index, trial.payload["evaluator_ref"], "trial.evaluator_ref")
    if not isinstance(evaluator_doc, dict):
        raise ValidationError("evaluator must be a supporting artifact")
    cases_doc = next((doc for doc in index.values() if isinstance(doc, dict) and doc["schema"] == "irisx/source-collection"), None)
    if cases_doc is None:
        raise ValidationError("fixture source collection is missing")

    results: list[EvaluationResult] = []
    for configuration in [baseline, *candidates]:
        component_ref = configuration.payload["components"].get("workflow_control")
        if component_ref is None:
            raise ValidationError("qualification configuration lacks workflow_control component")
        component_doc = resolve_ref(index, component_ref, "configuration.workflow_control")
        if not isinstance(component_doc, dict):
            raise ValidationError("qualification component must be a supporting artifact")
        results.append(_evaluate(trial, workload, evaluator_doc, cases_doc, configuration, component_doc))

    configurations = {item.content_digest: item for item in [baseline, *candidates]}
    decision = select_configuration(trial, workload, requirements, results[0], results[1:], configurations)
    for path in sorted(source.glob("*.json")):
        shutil.copyfile(path, output / path.name)
    results_dir = output / "results"
    results_dir.mkdir()
    for result in results:
        result.write(results_dir / f"{result.artifact_id}.json")
    decision.write(output / "decision.json")
    verdict_artifact = make_artifact(
        "irisx/requirement-verdicts",
        "qualification-verdicts",
        "1.0.0",
        {result.artifact_id: requirement_verdicts(result, requirements) for result in results},
    )
    write_artifact(output / "verdicts.json", verdict_artifact)
    summary = {"outcome": decision.payload["outcome"], "decision_digest": decision.content_digest, "results": [item.content_digest for item in results]}
    summary_artifact = make_artifact("irisx/run-summary", "qualification-run-summary", "1.0.0", summary)
    write_artifact(output / "run-summary.json", summary_artifact)
    return summary

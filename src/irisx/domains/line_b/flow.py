"""Independent synthetic label contracts using the common P1 qualification flow."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys
from typing import Any

from ...artifacts import artifact_ref, make_artifact, write_artifact
from ...bindings import QUALIFICATION_EVALUATOR_PROFILE
from ...canonical import digest_value, read_json, write_json
from ...contracts import (
    CandidateConfiguration, DomainPackageManifest, DomainSpecification,
    EngineeringTrial, EvaluationResult, RequirementSet, WorkloadDefinition,
    load_contract,
)
from ...engine import requirement_verdicts, select_configuration
from ...errors import IrisxError, ValidationError
from ...fixture import run_trial
from ...package import build_package, verify_package


PREFIX = "line-b-synthetic"
LIMITATION = "Synthetic engineering-only and non-deployable; the real line-b domain is unassigned."
VARIANTS = ("candidate", "unmet", "missing")


def _new_root(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ValidationError(f"line-b output already exists: {output}")
    output.mkdir(parents=True)


def _source_ref(source_id: str, locator: str, value: Any) -> dict[str, str]:
    return {"source_id": source_id, "media_type": "application/json", "content_digest": digest_value(value), "locator": locator}


def prepare(output: Path, variant: str = "candidate") -> None:
    """Create a wholly authored six-case graph; no inherited domain fixtures."""
    if variant not in VARIANTS:
        raise ValidationError(f"unknown line-b synthetic variant: {variant}")
    _new_root(output)
    descriptions = (
        ("copper", "accept", "routine", False),
        ("cobalt", "reject", "routine", False),
        ("amber", "defer", "routine", False),
        ("violet", "accept", "edge", True),
        ("silver", "reject", "edge", True),
        ("pearl", "defer", "edge", False),
    )
    cases = [
        {"case_id": f"{PREFIX}-case-{position:02}", "segment": segment, "critical": critical,
         "input": {"token": token}, "expected": {"label": label}}
        for position, (token, label, segment, critical) in enumerate(descriptions, 1)
    ]
    source = make_artifact("irisx/source-collection", f"{PREFIX}-cases", "1.0.0", {"cases": cases})
    evaluator = make_artifact("irisx/evaluator-definition", f"{PREFIX}-label-evaluator", "1.0.0", dict(QUALIFICATION_EVALUATOR_PROFILE))
    baseline_predictions = {case["case_id"]: "reject" for case in cases}
    candidate_predictions = ({case["case_id"]: case["expected"]["label"] for case in cases}
                             if variant != "unmet" else dict(baseline_predictions))
    baseline_component = make_artifact("irisx/reference-component", f"{PREFIX}-baseline-lookup", "1.0.0",
                                       {"adapter": "bounded-lookup", "predictions": baseline_predictions, "latency_ms": 4})
    candidate_component = make_artifact("irisx/reference-component", f"{PREFIX}-candidate-lookup", "1.0.0",
                                        {"adapter": "bounded-lookup", "predictions": candidate_predictions, "latency_ms": 5})
    workload = WorkloadDefinition(f"{PREFIX}-workload", "1.0.0", {
        "name": "line-b synthetic six-case label workload", "description": LIMITATION,
        "frozen": True, "evaluator_ref": artifact_ref(evaluator),
        "cases": [{"case_id": case["case_id"], "segment": case["segment"], "critical": case["critical"],
                   **{f"{field}_ref": _source_ref(f"{case['case_id']}-{field}", f"cases.json/{case['case_id']}/{field}", case[field])
                      for field in ("input", "expected")}} for case in cases],
    })
    requirements = RequirementSet(f"{PREFIX}-requirements", "1.0.0", {
        "name": "line-b synthetic qualification requirements",
        "requirements": [
            {"requirement_id": f"{PREFIX}-accuracy", "metric": "accuracy", "comparator": ">=", "threshold": 5 / 6,
             "hard": True, "objective": "maximize", "unit": "ratio", "description": "At least five of six synthetic labels correct."},
            {"requirement_id": f"{PREFIX}-critical", "metric": "critical_failures", "comparator": "<=", "threshold": 0,
             "hard": True, "objective": "minimize", "unit": "count", "description": "No synthetic critical case may fail."},
            {"requirement_id": f"{PREFIX}-zero-cost", "metric": "monetary_cost", "comparator": "==", "threshold": 0,
             "hard": True, "objective": "satisfy", "unit": "usd", "description": "Engineering only; no paid execution."},
        ],
    })
    specification = DomainSpecification(f"{PREFIX}-domain", "1.0.0", {
        "name": "line-b synthetic scaffold", "description": LIMITATION,
        "material_refs": [_source_ref(source["artifact_id"], "cases.json", source["payload"])],
        "workload_ref": workload.ref(), "requirement_set_ref": requirements.ref(),
        "operating_constraints": ["synthetic-only", "offline-only", "no-model-or-provider-calls", "non-deployable"],
        "known_limitations": [LIMITATION],
    })
    configurations = []
    for role, component, complexity in (("baseline", baseline_component, 1), ("candidate", candidate_component, 2)):
        configurations.append(CandidateConfiguration(f"{PREFIX}-{role}", "1.0.0", {
            "name": f"line-b synthetic {role}", "description": "Bounded six-case label lookup; engineering only.",
            "components": {"workflow_control": artifact_ref(component)}, "complexity": complexity,
            "maintainability": "high", "known_limitations": [LIMITATION],
        }))
    baseline, candidate = configurations
    trial = EngineeringTrial(f"{PREFIX}-trial", "1.0.0", {
        "name": "line-b synthetic engineering loop", "goal": "Qualify independent contracts, selection and packaging.",
        "qualification_fixture": True, "domain_specification_ref": specification.ref(), "workload_ref": workload.ref(),
        "requirement_set_ref": requirements.ref(), "evaluator_ref": artifact_ref(evaluator),
        "baseline_configuration_ref": baseline.ref(), "candidate_configuration_refs": [candidate.ref()],
        "stop_conditions": ["network or provider call", "real data or model invocation", "nonzero monetary cost"],
    })
    for filename, artifact in (("cases.json", source), ("evaluator.json", evaluator), ("baseline-component.json", baseline_component)):
        write_artifact(output / filename, artifact)
    if variant != "missing":
        write_artifact(output / "candidate-component.json", candidate_component)
    for filename, contract in (("workload.json", workload), ("requirements.json", requirements), ("specification.json", specification),
                               ("baseline.json", baseline), ("candidate.json", candidate), ("trial.json", trial)):
        contract.write(output / filename)


def _bind_line_b_results(run_root: Path) -> dict[str, Any]:
    """Assign only newly generated synthetic outputs their domain identities."""
    trial = load_contract(run_root / "trial.json", EngineeringTrial)
    workload = load_contract(run_root / "workload.json", WorkloadDefinition)
    requirements = load_contract(run_root / "requirements.json", RequirementSet)
    configurations = [load_contract(run_root / f"{role}.json", CandidateConfiguration) for role in ("baseline", "candidate")]
    results = [load_contract(run_root / "results" / f"{config.artifact_id}-result.json", EvaluationResult) for config in configurations]
    decision = select_configuration(trial, workload, requirements, results[0], results[1:],
                                    {config.content_digest: config for config in configurations}, decision_id=f"{PREFIX}-selection")
    decision.write(run_root / "decision.json")
    verdicts = {result.artifact_id: requirement_verdicts(result, requirements, workload) for result in results}
    write_artifact(run_root / "verdicts.json", make_artifact("irisx/requirement-verdicts", f"{PREFIX}-verdicts", "1.0.0", verdicts))
    summary = {"outcome": decision.payload["outcome"], "decision_digest": decision.content_digest,
               "results": [result.content_digest for result in results]}
    write_artifact(run_root / "run-summary.json", make_artifact("irisx/run-summary", f"{PREFIX}-run-summary", "1.0.0", summary))
    return summary


def run(output: Path, variant: str = "candidate") -> dict[str, Any]:
    """Finish an independent, reproducible engineering loop in a new root."""
    if variant not in VARIANTS:
        raise ValidationError(f"unknown line-b synthetic variant: {variant}")
    _new_root(output)
    prepare(output / "fixture", variant)
    run_trial(output / "fixture/trial.json", output / "run")
    summary = _bind_line_b_results(output / "run")
    manifest_digest = None
    if summary["outcome"] == "promote":
        common_manifest = build_package(output / "run", output / "package")
        manifest = DomainPackageManifest(f"{PREFIX}-domain-package", common_manifest.version, common_manifest.payload)
        manifest.write(output / "package/manifest.json")
        manifest_digest = verify_package(output / "package").content_digest
    report = {"schema": "irisx/line-b-synthetic-engineering-v1", "workstream": "line-b", "task_id": f"{PREFIX}-engineering-loop",
              "scope": "synthetic engineering-only non-deployable", "variant": variant, "outcome": summary["outcome"],
              "decision_digest": summary["decision_digest"], "package_created": manifest_digest is not None,
              "package_digest": manifest_digest, "real_domain": "unassigned", "independent_review": "pending"}
    write_json(output / "handoff.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", choices=VARIANTS, default="candidate")
    args = parser.parse_args(argv)
    try:
        report = run(args.output.resolve(), args.variant)
    except (IrisxError, OSError) as error:
        print(json.dumps({"status": "blocked", "scope": "synthetic engineering-only non-deployable", "error": str(error)}), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

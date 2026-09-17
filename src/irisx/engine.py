"""Deterministic evaluation verdicts and provider-neutral selection semantics."""

from __future__ import annotations

from typing import Any

from .bindings import validate_qualification_result_evidence
from .contracts import (
    CandidateConfiguration,
    EngineeringTrial,
    EvaluationResult,
    RequirementSet,
    SelectionDecision,
    WorkloadDefinition,
)
from .errors import ValidationError


def _metric_is_valid_for_result(
    result: EvaluationResult,
    metric: str,
    workload: WorkloadDefinition | None,
) -> bool:
    if not metric.startswith("accuracy."):
        return True
    if workload is None:
        return False
    segment = metric.removeprefix("accuracy.")
    return segment in {item["segment"] for item in workload.payload["cases"]}


def requirement_verdicts(
    result: EvaluationResult,
    requirements: RequirementSet,
    workload: WorkloadDefinition | None = None,
) -> list[dict[str, Any]]:
    verdicts: list[dict[str, Any]] = []
    metrics = result.payload["metrics"]
    for requirement in requirements.payload["requirements"]:
        if not _metric_is_valid_for_result(result, requirement["metric"], workload):
            state = "invalid_metric"
            observed = None
        else:
            observation = metrics.get(requirement["metric"])
            if observation is None or observation["state"] != "observed":
                state = "unknown"
                observed = None
            elif observation["unit"] != requirement["unit"]:
                state = "unit_mismatch"
                observed = None
            else:
                observed = observation["value"]
                comparator = requirement["comparator"]
                threshold = requirement["threshold"]
                passed = {
                    ">=": observed >= threshold,
                    "<=": observed <= threshold,
                    "==": observed == threshold,
                }[comparator]
                state = "pass" if passed else "fail"
        verdicts.append(
            {
                "requirement_id": requirement["requirement_id"],
                "metric": requirement["metric"],
                "hard": requirement["hard"],
                "state": state,
                "observed": observed,
                "threshold": requirement["threshold"],
                "comparator": requirement["comparator"],
            }
        )
    return verdicts


def satisfies_hard_requirements(
    result: EvaluationResult,
    requirements: RequirementSet,
    workload: WorkloadDefinition | None = None,
) -> bool:
    hard = [item for item in requirement_verdicts(result, requirements, workload) if item["hard"]]
    return bool(hard) and all(item["state"] == "pass" for item in hard)


def validate_result_evidence(result: EvaluationResult, workload: WorkloadDefinition) -> None:
    """Check case completeness and recomputable aggregate evidence."""

    if result.payload["workload_ref"] != workload.ref():
        raise ValidationError("result.workload_ref: stale or substituted workload")
    expected = {item["case_id"]: item for item in workload.payload["cases"]}
    actual = {item["case_id"]: item for item in result.payload["cases"]}
    if set(actual) != set(expected):
        raise ValidationError("result cases do not exactly match the frozen workload")
    for case_id, outcome in actual.items():
        workload_case = expected[case_id]
        if outcome["segment"] != workload_case["segment"]:
            raise ValidationError(f"result case segment mismatch: {case_id}")
        derived_critical = bool(workload_case["critical"] and not outcome["passed"])
        if outcome["critical_failure"] is not derived_critical:
            raise ValidationError(f"result critical_failure is inconsistent with workload criticality: {case_id}")
        if outcome["score"] != (1 if outcome["passed"] else 0):
            raise ValidationError(f"result score is inconsistent with passed state: {case_id}")
    metrics = result.payload["metrics"]
    accuracy = metrics.get("accuracy")
    critical = metrics.get("critical_failures")
    expected_accuracy = sum(item["passed"] for item in actual.values()) / len(actual)
    expected_critical = sum(
        expected[case_id]["critical"] and not outcome["passed"]
        for case_id, outcome in actual.items()
    )
    if accuracy != {"state": "observed", "value": expected_accuracy, "unit": "ratio"}:
        raise ValidationError("result accuracy is missing or inconsistent with case outcomes")
    if critical != {"state": "observed", "value": expected_critical, "unit": "count"}:
        raise ValidationError("result critical_failures is missing or inconsistent with case outcomes")
    segments = {item["segment"] for item in workload.payload["cases"]}
    segment_metrics = {name.removeprefix("accuracy.") for name in metrics if name.startswith("accuracy.")}
    if segment_metrics != segments:
        raise ValidationError("result segment accuracy namespace does not exactly match the frozen workload")
    for segment in segments:
        outcomes = [item for item in actual.values() if item["segment"] == segment]
        expected_segment_accuracy = sum(item["passed"] for item in outcomes) / len(outcomes)
        metric_name = f"accuracy.{segment}"
        expected_observation = {"state": "observed", "value": expected_segment_accuracy, "unit": "ratio"}
        if metrics.get(metric_name) != expected_observation:
            raise ValidationError(f"result {metric_name} is missing or inconsistent with case outcomes")


def _assert_comparable(trial: EngineeringTrial, results: list[EvaluationResult]) -> None:
    if not results:
        raise ValidationError("selection requires at least one result")
    expected_trial = trial.ref()
    workload = results[0].payload["workload_ref"]
    evaluator = results[0].payload["evaluator_ref"]
    seen: set[str] = set()
    for index, result in enumerate(results):
        if result.payload["trial_ref"] != expected_trial:
            raise ValidationError(f"results[{index}].trial_ref: stale or cross-trial evidence")
        if result.payload["workload_ref"] != workload:
            raise ValidationError(f"results[{index}].workload_ref: results are not comparable")
        if result.payload["evaluator_ref"] != evaluator:
            raise ValidationError(f"results[{index}].evaluator_ref: results are not comparable")
        configuration_digest = result.payload["configuration_ref"]["content_digest"]
        if configuration_digest in seen:
            raise ValidationError("duplicate configuration result")
        seen.add(configuration_digest)


def _objective_value(
    result: EvaluationResult,
    requirement: dict[str, Any],
    workload: WorkloadDefinition,
) -> float | None:
    if not _metric_is_valid_for_result(result, requirement["metric"], workload):
        return None
    observation = result.payload["metrics"].get(requirement["metric"])
    if (
        observation is None
        or observation["state"] != "observed"
        or observation["unit"] != requirement["unit"]
    ):
        return None
    value = float(observation["value"])
    if requirement["objective"] == "maximize":
        value = -value
    return value


def _strictly_better(
    candidate: EvaluationResult,
    baseline: EvaluationResult,
    requirements: RequirementSet,
    workload: WorkloadDefinition,
) -> bool:
    objectives = [
        req for req in requirements.payload["requirements"]
        if req["objective"] in {"minimize", "maximize"}
    ]
    better = False
    for requirement in objectives:
        candidate_value = _objective_value(candidate, requirement, workload)
        baseline_value = _objective_value(baseline, requirement, workload)
        if candidate_value is None or baseline_value is None:
            return False
        if candidate_value > baseline_value:
            return False
        if candidate_value < baseline_value:
            better = True
    return better


def select_configuration(
    trial: EngineeringTrial,
    workload: WorkloadDefinition,
    requirements: RequirementSet,
    baseline: EvaluationResult,
    candidates: list[EvaluationResult],
    configurations: dict[str, CandidateConfiguration],
    *,
    decision_id: str = "qualification-selection",
) -> SelectionDecision:
    all_results = [baseline, *candidates]
    _assert_comparable(trial, all_results)
    for result in all_results:
        validate_result_evidence(result, workload)
        validate_qualification_result_evidence(trial, result)
    expected_baseline = trial.payload["baseline_configuration_ref"]
    if baseline.payload["configuration_ref"] != expected_baseline:
        raise ValidationError("baseline result does not bind the trial baseline configuration")
    expected_candidates = {ref["content_digest"] for ref in trial.payload["candidate_configuration_refs"]}
    actual_candidates = {item.payload["configuration_ref"]["content_digest"] for item in candidates}
    if actual_candidates != expected_candidates:
        raise ValidationError("candidate results do not exactly match the trial candidates")

    eligible = [item for item in all_results if satisfies_hard_requirements(item, requirements, workload)]
    eligible_candidates = [item for item in candidates if item in eligible]
    baseline_eligible = baseline in eligible
    selected: EvaluationResult | None = None
    promotion_candidates = eligible_candidates if not baseline_eligible else [
        item for item in eligible_candidates if _strictly_better(item, baseline, requirements, workload)
    ]
    if promotion_candidates:
        pareto_front = [
            item
            for item in promotion_candidates
            if not any(
                other is not item and _strictly_better(other, item, requirements, workload)
                for other in promotion_candidates
            )
        ]
        selected = sorted(
            pareto_front,
            key=lambda item: item.payload["configuration_ref"]["artifact_id"],
        )[0]

    if selected is not None:
        outcome = "promote"
        config_ref = selected.payload["configuration_ref"]
        config = configurations.get(config_ref["content_digest"])
        if config is None or config.ref() != config_ref:
            raise ValidationError("selected result configuration evidence is missing or stale")
        selected_config_ref: dict[str, Any] | None = config.ref()
        selected_result_ref: dict[str, Any] | None = selected.ref()
        reason = "Candidate satisfies every hard requirement and is deterministically preferred to the baseline."
    elif baseline_eligible:
        outcome = "no_promotion"
        selected_config_ref = None
        selected_result_ref = None
        reason = "No candidate both satisfies hard requirements and strictly improves the eligible baseline."
    else:
        outcome = "infeasible"
        selected_config_ref = None
        selected_result_ref = None
        reason = "No evaluated configuration satisfies every hard requirement."

    return SelectionDecision(
        decision_id,
        "1.0.0",
        {
            "outcome": outcome,
            "trial_ref": trial.ref(),
            "workload_ref": baseline.payload["workload_ref"],
            "evaluator_ref": baseline.payload["evaluator_ref"],
            "baseline_result_ref": baseline.ref(),
            "considered_result_refs": [item.ref() for item in all_results],
            "eligible_result_refs": [item.ref() for item in eligible],
            "selected_configuration_ref": selected_config_ref,
            "selected_result_ref": selected_result_ref,
            "reason": reason,
            "tie_break_rule": "Pareto front over declared objectives, then lexical configuration artifact_id.",
            "known_limitations": ["P1 selection handles deterministic scalar observations; uncertainty intervals are deferred."],
        },
    )

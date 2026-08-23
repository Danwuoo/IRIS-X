"""Frozen G0/S1 configuration, calibration, and paired-comparison contracts.

All outputs remain development-only and local-reference when backed by the
repository evaluator.  These helpers make the comparison boundary explicit;
they do not select a provider, model snapshot, numerical compute tier, or
formal preregistration on behalf of the project owner.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from spex_arc.domain.arc_a1 import ValidationFailure
from spex_arc.runner.arc_a1 import ArcA1Runner, InferenceBudget, RunManifest, RunResult
from spex_arc.solvers.arc_a1 import G0Solver, ModelAdapter, ModelIdentity, PromptPolicy, S1Solver


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _failure(code: str, path: str, message: str) -> ValidationFailure:
    return ValidationFailure(code=code, path=path, message=message)


@dataclass(frozen=True)
class BaselineConfiguration:
    """The fully disclosed non-secret configuration for one G0 or S1 run."""

    configuration_id: str
    label: str
    unit: str
    model: ModelIdentity
    prompt_policy: PromptPolicy
    retry_policy: Mapping[str, Any]
    tools: tuple[str, ...]
    network_access: bool
    context_policy: str
    request_date: str
    development_scope: str = "development-only"

    def payload(self) -> dict[str, Any]:
        return {
            "configuration_id": self.configuration_id,
            "context_policy": self.context_policy,
            "development_scope": self.development_scope,
            "label": self.label,
            "model": self.model.to_json(),
            "network_access": self.network_access,
            "prompt_policy": self.prompt_policy.to_json(),
            "request_date": self.request_date,
            "retry_policy": dict(self.retry_policy),
            "tools": list(self.tools),
            "unit": self.unit,
        }

    @property
    def sha256(self) -> str:
        return _sha256_json(self.payload())

    def to_json(self) -> dict[str, Any]:
        return {**self.payload(), "configuration_sha256": self.sha256}

    def binding_failures(self, manifest: RunManifest) -> tuple[ValidationFailure, ...]:
        """Require manifest identity/policy fields to match this exact config."""
        failures: list[ValidationFailure] = []
        expected = {
            "configuration_id": self.configuration_id,
            "configuration_sha256": self.sha256,
            "unit": self.unit,
            "model_provider": self.model.provider,
            "model_id": self.model.model_id,
            "model_snapshot": self.model.model_snapshot,
            "weights_hash": self.model.weights_hash,
            "provider_adapter_id": self.model.adapter_id,
            "provider_request_parameters": dict(self.model.request_parameters),
            "provider_request_parameters_sha256": self.model.request_parameters_sha256,
            "prompt_policy": self.prompt_policy.to_json(),
            "prompt_policy_hash": self.prompt_policy.sha256,
            "retry_policy": dict(self.retry_policy),
            "tools": self.tools,
            "network_access": self.network_access,
            "evaluation_date": self.request_date,
        }
        for field_name, expected_value in expected.items():
            actual = getattr(manifest, field_name)
            if actual != expected_value:
                failures.append(
                    _failure(
                        "baseline_manifest_mismatch",
                        f"$.{field_name}",
                        f"Manifest {field_name} does not match frozen configuration {self.configuration_id!r}.",
                    )
                )
        if self.label not in {"G0", "S1"}:
            failures.append(_failure("invalid_baseline_label", "$.label", "Baseline label must be G0 or S1."))
        for field_name in ("configuration_id", "context_policy", "request_date", "development_scope"):
            if not isinstance(getattr(self, field_name), str) or not getattr(self, field_name):
                failures.append(_failure("invalid_configuration_field", f"$.{field_name}", f"{field_name} must be a non-empty string."))
        expected_unit = "G" if self.label == "G0" else "S"
        if self.unit != expected_unit or self.prompt_policy.unit != expected_unit:
            failures.append(
                _failure("baseline_unit_mismatch", "$.unit", "Baseline label, configuration unit, and prompt-policy unit must agree.")
            )
        if not isinstance(self.retry_policy.get("max_retries"), int) or isinstance(self.retry_policy.get("max_retries"), bool) or self.retry_policy["max_retries"] < 0:
            failures.append(_failure("invalid_retry_policy", "$.retry_policy.max_retries", "max_retries must be a non-negative integer."))
        if not isinstance(self.network_access, bool):
            failures.append(_failure("invalid_network_access", "$.network_access", "network_access must be boolean."))
        return tuple(failures)


@dataclass(frozen=True)
class BaselineSolverFactory:
    """Create only the solver that is bound to a frozen G0 or S1 manifest."""

    configuration: BaselineConfiguration
    adapter: ModelAdapter

    def create(self, manifest: RunManifest, budget: InferenceBudget):
        failures = list(self.configuration.binding_failures(manifest))
        if self.adapter.identity.to_json() != self.configuration.model.to_json():
            failures.append(_failure("adapter_identity_mismatch", "$.model", "Adapter identity does not match the frozen baseline configuration."))
        if self.adapter.requires_network != self.configuration.network_access:
            failures.append(_failure("adapter_network_mismatch", "$.network_access", "Adapter network requirement does not match the frozen configuration."))
        if self.adapter.required_tools != self.configuration.tools:
            failures.append(_failure("adapter_tool_mismatch", "$.tools", "Adapter tools do not match the frozen configuration."))
        if budget != manifest.budget:
            failures.append(_failure("factory_budget_mismatch", "$.budget", "Runner budget does not match the frozen manifest budget."))
        if failures:
            raise ValueError(f"Frozen baseline configuration is invalid: {[failure.to_json() for failure in failures]}")
        if self.configuration.label == "G0":
            return G0Solver(self.adapter)
        if self.configuration.label == "S1":
            return S1Solver(self.adapter)
        raise ValueError(f"Unsupported baseline label: {self.configuration.label!r}")


def run_baseline(
    configuration: BaselineConfiguration,
    manifest: RunManifest,
    evaluator: Any,
    adapter: ModelAdapter,
    artifact_root: Path,
    tasks: Iterable[Any],
) -> RunResult:
    """Execute one bound development baseline with the frozen retry policy."""
    factory = BaselineSolverFactory(configuration=configuration, adapter=adapter)
    return ArcA1Runner(
        manifest,
        evaluator,
        factory,
        artifact_root,
        max_retries=configuration.retry_policy["max_retries"],
    ).run(tasks)


_PAIRED_MANIFEST_FIELDS = (
    "benchmark",
    "benchmark_snapshot",
    "evaluator_version",
    "evaluation_date",
    "model_provider",
    "model_id",
    "model_snapshot",
    "weights_hash",
    "provider_adapter_id",
    "provider_request_parameters",
    "provider_request_parameters_sha256",
    "solver_commit",
    "training_data_manifest",
    "synthetic_data_manifest",
    "tools",
    "verifier",
    "memory_policy",
    "search_policy",
    "budget",
    "hardware",
    "network_access",
    "random_seed",
    "estimated_cost_usd",
    "contamination_status",
    "result_status",
    "task_ids",
    "rules_snapshot_id",
    "rules_sha256",
    "scorer_status",
    "official_status",
    "parity_status",
)


def paired_precondition_failures(
    g0_configuration: BaselineConfiguration,
    g0_manifest: RunManifest,
    s1_configuration: BaselineConfiguration,
    s1_manifest: RunManifest,
) -> tuple[ValidationFailure, ...]:
    """Validate that G0/S1 differ only in the declared prompt intervention."""
    failures = [*g0_configuration.binding_failures(g0_manifest), *s1_configuration.binding_failures(s1_manifest)]
    if g0_configuration.label != "G0" or s1_configuration.label != "S1":
        failures.append(_failure("invalid_paired_labels", "$.label", "Paired comparison requires a G0 configuration and an S1 configuration."))
    if g0_configuration.model.to_json() != s1_configuration.model.to_json():
        failures.append(_failure("backbone_mismatch", "$.model", "G0 and S1 must use the same provider, model, snapshot, weights, adapter, and request parameters."))
    for field_name in ("retry_policy", "tools", "network_access", "context_policy", "request_date", "development_scope"):
        if getattr(g0_configuration, field_name) != getattr(s1_configuration, field_name):
            failures.append(_failure("configuration_asymmetry", f"$.{field_name}", f"G0 and S1 must share {field_name}."))
    for field_name in _PAIRED_MANIFEST_FIELDS:
        if getattr(g0_manifest, field_name) != getattr(s1_manifest, field_name):
            failures.append(_failure("paired_manifest_asymmetry", f"$.{field_name}", f"G0 and S1 manifests differ at {field_name}."))
    if g0_manifest.unit != "G" or s1_manifest.unit != "S":
        failures.append(_failure("paired_unit_mismatch", "$.unit", "Paired manifests must be G0/G and S1/S."))
    if g0_manifest.prompt_policy == s1_manifest.prompt_policy or g0_manifest.prompt_policy_hash == s1_manifest.prompt_policy_hash:
        failures.append(_failure("missing_system_intervention", "$.prompt_policy", "G0 and S1 must have different frozen prompt policies."))
    if g0_manifest.run_id == s1_manifest.run_id:
        failures.append(_failure("duplicate_paired_run_id", "$.run_id", "G0 and S1 must have distinct run IDs."))
    return tuple(failures)


@dataclass(frozen=True)
class CalibrationObservation:
    """Observed per-task usage from one completed development run bundle."""

    run_id: str
    task_usage: tuple[Mapping[str, Any], ...]
    source_bundle: Path

    def maxima(self) -> dict[str, float]:
        fields = (
            "input_tokens",
            "output_tokens",
            "model_calls",
            "rollouts",
            "wall_clock_seconds",
            "estimated_cost_usd",
        )
        maxima = {field: 0.0 for field in fields}
        for usage in self.task_usage:
            for field in fields:
                value = usage.get(field, 0)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                    maxima[field] = max(maxima[field], float(value))
        return maxima


def load_calibration_observation(bundle: Path) -> CalibrationObservation:
    """Read only immutable ledger data from a completed Stage 2/3 run bundle."""
    try:
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        costs = json.loads((bundle / "costs.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read calibration bundle: {error}") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("run_id"), str):
        raise ValueError("Calibration bundle manifest lacks a run_id.")
    per_task = costs.get("per_task") if isinstance(costs, dict) else None
    if not isinstance(per_task, list):
        raise ValueError("Calibration bundle cost ledger lacks per_task usage.")
    usage: list[Mapping[str, Any]] = []
    for record in per_task:
        if not isinstance(record, dict) or not isinstance(record.get("task_id"), str) or not isinstance(record.get("usage"), dict):
            raise ValueError("Calibration cost ledger has an invalid per-task record.")
        usage.append(record["usage"])
    return CalibrationObservation(run_id=manifest["run_id"], task_usage=tuple(usage), source_bundle=bundle)


@dataclass(frozen=True)
class BudgetTierMultipliers:
    """An explicit proposal rule supplied by the authorized calibration plan."""

    low: float
    matched: float
    high: float

    def validate(self) -> None:
        values = (self.low, self.matched, self.high)
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError("Budget tier multipliers must be positive finite numbers.")
        if not self.low <= self.matched <= self.high:
            raise ValueError("Budget tier multipliers must satisfy low <= matched <= high.")


@dataclass(frozen=True)
class BudgetTierProposal:
    """One non-authoritative budget proposal derived from observed usage."""

    label: str
    budget: InferenceBudget
    estimated_cost_usd: float

    def to_json(self) -> dict[str, Any]:
        return {
            "budget": self.budget.to_json(),
            "estimated_cost_usd": self.estimated_cost_usd,
            "label": self.label,
        }


@dataclass(frozen=True)
class BudgetProposal:
    """Low/Matched/High proposals and their exact derivation inputs."""

    source_run_ids: tuple[str, ...]
    observed_maxima: Mapping[str, float]
    multipliers: BudgetTierMultipliers
    tiers: tuple[BudgetTierProposal, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "artifact_type": "arc-agi-1-development-budget-proposal",
            "multipliers": {"high": self.multipliers.high, "low": self.multipliers.low, "matched": self.multipliers.matched},
            "observed_maxima": dict(self.observed_maxima),
            "source_run_ids": list(self.source_run_ids),
            "tiers": [tier.to_json() for tier in self.tiers],
        }


def derive_budget_proposal(
    observations: Iterable[CalibrationObservation],
    multipliers: BudgetTierMultipliers,
    *,
    num_attempts: int,
    concurrency_limit: int = 1,
) -> BudgetProposal:
    """Derive proposals from observed maxima without declaring them approved tiers."""
    multipliers.validate()
    observations = tuple(observations)
    if not observations:
        raise ValueError("At least one calibration observation is required.")
    if not isinstance(num_attempts, int) or isinstance(num_attempts, bool) or num_attempts < 1:
        raise ValueError("num_attempts must be a positive integer.")
    if concurrency_limit != 1:
        raise ValueError("The current deterministic runner supports concurrency_limit=1 only.")
    maxima = {field: 0.0 for field in ("input_tokens", "output_tokens", "model_calls", "rollouts", "wall_clock_seconds", "estimated_cost_usd")}
    for observation in observations:
        for field, value in observation.maxima().items():
            maxima[field] = max(maxima[field], value)

    def scaled_limit(field: str, multiplier: float) -> int:
        return max(1, math.ceil(maxima[field] * multiplier))

    def tier(label: str, multiplier: float) -> BudgetTierProposal:
        return BudgetTierProposal(
            label=label,
            budget=InferenceBudget(
                num_attempts=num_attempts,
                max_input_tokens=scaled_limit("input_tokens", multiplier),
                max_output_tokens=scaled_limit("output_tokens", multiplier),
                max_model_calls_per_task=scaled_limit("model_calls", multiplier),
                max_rollouts_per_task=scaled_limit("rollouts", multiplier),
                wall_clock_limit_seconds=max(0.001, maxima["wall_clock_seconds"] * multiplier),
                concurrency_limit=concurrency_limit,
            ),
            estimated_cost_usd=maxima["estimated_cost_usd"] * multiplier,
        )

    return BudgetProposal(
        source_run_ids=tuple(observation.run_id for observation in observations),
        observed_maxima=maxima,
        multipliers=multipliers,
        tiers=(tier("Low", multipliers.low), tier("Matched", multipliers.matched), tier("High", multipliers.high)),
    )


@dataclass(frozen=True)
class PairedTaskComparison:
    """Task-level G0/S1 Exact@1 comparison with no aggregate-only shortcut."""

    task_rows: tuple[Mapping[str, Any], ...]

    def to_json(self) -> dict[str, Any]:
        g0_only = sum(row["g0_exact_at_1"] and not row["s1_exact_at_1"] for row in self.task_rows)
        s1_only = sum(row["s1_exact_at_1"] and not row["g0_exact_at_1"] for row in self.task_rows)
        g0_solved = sum(row["g0_exact_at_1"] for row in self.task_rows)
        s1_solved = sum(row["s1_exact_at_1"] for row in self.task_rows)
        task_count = len(self.task_rows)
        return {
            "artifact_type": "arc-agi-1-development-paired-comparison",
            "g0_exact_at_1": g0_solved / task_count if task_count else 0.0,
            "g0_only_solved": g0_only,
            "s1_exact_at_1": s1_solved / task_count if task_count else 0.0,
            "s1_minus_g0_exact_at_1": (s1_solved - g0_solved) / task_count if task_count else 0.0,
            "s1_only_solved": s1_only,
            "task_count": task_count,
            "task_rows": [dict(row) for row in self.task_rows],
        }


def _load_task_exact_at_1(bundle: Path) -> dict[str, bool]:
    path = bundle / "predictions.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"Cannot read prediction artifact {path}: {error}") from error
    result: dict[str, bool] = {}
    for line_number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Malformed prediction record {line_number}: {error}") from error
        task_id = record.get("task_id") if isinstance(record, dict) else None
        score = record.get("task_score") if isinstance(record, dict) else None
        exact = score.get("exact_at_1") if isinstance(score, dict) else None
        if not isinstance(task_id, str) or not isinstance(exact, bool):
            raise ValueError(f"Prediction record {line_number} lacks task_id or task_score.exact_at_1.")
        if task_id in result:
            raise ValueError(f"Prediction artifact repeats task {task_id!r}.")
        result[task_id] = exact
    return result


def summarize_paired_task_comparison(g0_bundle: Path, s1_bundle: Path) -> PairedTaskComparison:
    """Create a task-level paired summary from two frozen run bundles."""
    g0 = _load_task_exact_at_1(g0_bundle)
    s1 = _load_task_exact_at_1(s1_bundle)
    if set(g0) != set(s1):
        raise ValueError("G0 and S1 bundles do not contain the same terminal task IDs.")
    return PairedTaskComparison(
        task_rows=tuple(
            {
                "g0_exact_at_1": g0[task_id],
                "s1_exact_at_1": s1[task_id],
                "task_id": task_id,
            }
            for task_id in sorted(g0)
        )
    )

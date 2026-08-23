"""Reconstructable development runs for the local ARC-AGI-1 evaluator.

This module deliberately stops at the Stage 2 runner boundary.  It contains
no model-provider adapter, prompt policy, search policy, baseline, or formal
ARC result.  A solver receives only :class:`~spex_arc.domain.arc_a1.TaskView`;
the evaluator is invoked only after the solver has returned its immutable
candidate set.

The in-process solver interface is a development contract, not a security
sandbox.  ``network_access`` and ``tools`` are enforced against a solver's
declared requirements and captured in the run manifest.  A future provider or
executable-solver boundary must enforce those policies outside the process.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from spex_arc.domain.arc_a1 import (
    CandidateSet,
    Task,
    TaskView,
    ValidationFailure,
    ValidationResult,
    candidate_set_to_json,
    parse_candidate_set_object,
)
from spex_arc.evaluator.arc_a1 import EvaluatorIdentity, LocalReferenceEvaluator, TaskScore


RUN_MANIFEST_SCHEMA_VERSION = "1.1"
RUN_MANIFEST_ARTIFACT_TYPE = "arc-agi-1-development-run"
RUN_BUNDLE_ARTIFACT_TYPE = "arc-agi-1-development-run-bundle"
RUN_MANIFEST_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "arc-agi-1-run-manifest.schema.json"

_MANIFEST_REQUIRED_FIELDS = (
    "artifact_type",
    "schema_version",
    "run_id",
    "benchmark",
    "benchmark_snapshot",
    "evaluator_version",
    "evaluation_date",
    "unit",
    "model_provider",
    "model_id",
    "model_snapshot",
    "weights_hash",
    "configuration_id",
    "configuration_sha256",
    "provider_adapter_id",
    "provider_request_parameters",
    "provider_request_parameters_sha256",
    "prompt_policy",
    "prompt_policy_hash",
    "retry_policy",
    "solver_commit",
    "training_data_manifest",
    "synthetic_data_manifest",
    "tools",
    "verifier",
    "memory_policy",
    "search_policy",
    "num_attempts",
    "max_input_tokens",
    "max_output_tokens",
    "max_model_calls_per_task",
    "max_rollouts_per_task",
    "wall_clock_limit_seconds",
    "concurrency_limit",
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

_BUNDLE_FILENAMES = {
    "manifest": "manifest.json",
    "predictions": "predictions.jsonl",
    "events": "events.jsonl",
    "metrics": "metrics.json",
    "costs": "costs.json",
    "failures": "failures.jsonl",
    "deviations": "deviations.json",
}


def _failure(code: str, path: str, message: str) -> ValidationFailure:
    return ValidationFailure(code=code, path=path, message=message)


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _jsonl_bytes(records: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_json_bytes(record) for record in records)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


@dataclass(frozen=True)
class InferenceBudget:
    """Per-task resource ceilings captured in every run manifest."""

    num_attempts: int
    max_input_tokens: int
    max_output_tokens: int
    max_model_calls_per_task: int
    max_rollouts_per_task: int
    wall_clock_limit_seconds: float
    concurrency_limit: int = 1

    def to_json(self) -> dict[str, Any]:
        return {
            "concurrency_limit": self.concurrency_limit,
            "max_input_tokens": self.max_input_tokens,
            "max_model_calls_per_task": self.max_model_calls_per_task,
            "max_output_tokens": self.max_output_tokens,
            "max_rollouts_per_task": self.max_rollouts_per_task,
            "num_attempts": self.num_attempts,
            "wall_clock_limit_seconds": self.wall_clock_limit_seconds,
        }


@dataclass(frozen=True)
class TaskUsage:
    """Instrumented resource and cost use accumulated for one task."""

    input_tokens: int = 0
    output_tokens: int = 0
    model_calls: int = 0
    rollouts: int = 0
    solver_invocations: int = 0
    estimated_cost_usd: float = 0.0
    wall_clock_seconds: float = 0.0

    def plus(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model_calls: int = 0,
        rollouts: int = 0,
        solver_invocations: int = 0,
        estimated_cost_usd: float = 0.0,
        wall_clock_seconds: float = 0.0,
    ) -> "TaskUsage":
        return TaskUsage(
            input_tokens=self.input_tokens + input_tokens,
            output_tokens=self.output_tokens + output_tokens,
            model_calls=self.model_calls + model_calls,
            rollouts=self.rollouts + rollouts,
            solver_invocations=self.solver_invocations + solver_invocations,
            estimated_cost_usd=self.estimated_cost_usd + estimated_cost_usd,
            wall_clock_seconds=self.wall_clock_seconds + wall_clock_seconds,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "estimated_cost_usd": self.estimated_cost_usd,
            "input_tokens": self.input_tokens,
            "model_calls": self.model_calls,
            "output_tokens": self.output_tokens,
            "rollouts": self.rollouts,
            "solver_invocations": self.solver_invocations,
            "wall_clock_seconds": self.wall_clock_seconds,
        }


@dataclass(frozen=True)
class RunManifest:
    """The frozen, machine-readable identity and budget for one development run."""

    run_id: str
    benchmark_snapshot: str
    evaluator_version: str
    evaluation_date: str
    unit: str
    model_provider: str
    model_id: str
    model_snapshot: str
    weights_hash: str
    configuration_id: str
    configuration_sha256: str
    provider_adapter_id: str
    provider_request_parameters: Mapping[str, Any]
    provider_request_parameters_sha256: str
    prompt_policy: Mapping[str, Any]
    prompt_policy_hash: str
    retry_policy: Mapping[str, Any]
    solver_commit: str
    training_data_manifest: str
    synthetic_data_manifest: str
    tools: tuple[str, ...]
    verifier: str
    memory_policy: str
    search_policy: str
    budget: InferenceBudget
    hardware: str
    network_access: bool
    random_seed: int
    estimated_cost_usd: float
    contamination_status: str
    result_status: str
    task_ids: tuple[str, ...]
    rules_snapshot_id: str
    rules_sha256: str
    scorer_status: str
    official_status: str
    parity_status: str
    artifact_type: str = RUN_MANIFEST_ARTIFACT_TYPE
    schema_version: str = RUN_MANIFEST_SCHEMA_VERSION
    benchmark: str = "arc-agi-1"

    def to_json(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "benchmark": self.benchmark,
            "benchmark_snapshot": self.benchmark_snapshot,
            "concurrency_limit": self.budget.concurrency_limit,
            "configuration_id": self.configuration_id,
            "configuration_sha256": self.configuration_sha256,
            "contamination_status": self.contamination_status,
            "estimated_cost_usd": self.estimated_cost_usd,
            "evaluation_date": self.evaluation_date,
            "evaluator_version": self.evaluator_version,
            "hardware": self.hardware,
            "max_input_tokens": self.budget.max_input_tokens,
            "max_model_calls_per_task": self.budget.max_model_calls_per_task,
            "max_output_tokens": self.budget.max_output_tokens,
            "max_rollouts_per_task": self.budget.max_rollouts_per_task,
            "memory_policy": self.memory_policy,
            "model_id": self.model_id,
            "model_provider": self.model_provider,
            "model_snapshot": self.model_snapshot,
            "network_access": self.network_access,
            "num_attempts": self.budget.num_attempts,
            "official_status": self.official_status,
            "parity_status": self.parity_status,
            "prompt_policy": dict(self.prompt_policy),
            "prompt_policy_hash": self.prompt_policy_hash,
            "provider_adapter_id": self.provider_adapter_id,
            "provider_request_parameters": dict(self.provider_request_parameters),
            "provider_request_parameters_sha256": self.provider_request_parameters_sha256,
            "random_seed": self.random_seed,
            "retry_policy": dict(self.retry_policy),
            "result_status": self.result_status,
            "rules_sha256": self.rules_sha256,
            "rules_snapshot_id": self.rules_snapshot_id,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "scorer_status": self.scorer_status,
            "search_policy": self.search_policy,
            "solver_commit": self.solver_commit,
            "synthetic_data_manifest": self.synthetic_data_manifest,
            "task_ids": list(self.task_ids),
            "tools": list(self.tools),
            "training_data_manifest": self.training_data_manifest,
            "unit": self.unit,
            "verifier": self.verifier,
            "wall_clock_limit_seconds": self.budget.wall_clock_limit_seconds,
            "weights_hash": self.weights_hash,
        }


def validate_run_manifest(manifest: RunManifest, identity: EvaluatorIdentity) -> ValidationResult[RunManifest]:
    """Validate the shipped run-manifest schema and A1 identity semantics.

    The repository intentionally uses the standard library only.  This checks
    the structural requirements represented in the JSON Schema plus the
    cross-field rules that JSON Schema cannot express (identity, task ordering,
    and native-attempt policy).
    """
    if not isinstance(manifest, RunManifest):
        return ValidationResult(None, (_failure("invalid_run_manifest_type", "$", "Expected a RunManifest instance."),))

    payload = manifest.to_json()
    failures: list[ValidationFailure] = []
    if not RUN_MANIFEST_SCHEMA_PATH.is_file():
        failures.append(_failure("run_manifest_schema_unavailable", "$", "Run manifest schema is unavailable in checkout."))
    missing = set(_MANIFEST_REQUIRED_FIELDS) - set(payload)
    extra = set(payload) - set(_MANIFEST_REQUIRED_FIELDS)
    for name in sorted(missing):
        failures.append(_failure("missing_manifest_field", "$", f"Missing required manifest field: {name}."))
    for name in sorted(extra):
        failures.append(_failure("unexpected_manifest_field", "$", f"Unexpected manifest field: {name}."))

    if manifest.artifact_type != RUN_MANIFEST_ARTIFACT_TYPE:
        failures.append(_failure("invalid_artifact_type", "$.artifact_type", "Unsupported run-manifest artifact type."))
    if manifest.schema_version != RUN_MANIFEST_SCHEMA_VERSION:
        failures.append(_failure("unsupported_run_manifest_schema", "$.schema_version", "Unsupported run-manifest schema version."))
    if manifest.benchmark != "arc-agi-1":
        failures.append(_failure("invalid_benchmark", "$.benchmark", "Stage 2 runner supports only arc-agi-1."))
    if manifest.unit not in {"G", "M", "S", "H", "N"}:
        failures.append(_failure("invalid_unit", "$.unit", "unit must be one of G, M, S, H, or N."))
    if manifest.result_status not in {"exploratory", "confirmatory", "official"}:
        failures.append(_failure("invalid_result_status", "$.result_status", "Unsupported result_status."))
    if not isinstance(manifest.network_access, bool):
        failures.append(_failure("invalid_network_access", "$.network_access", "network_access must be a boolean."))
    if not _is_int(manifest.random_seed):
        failures.append(_failure("invalid_random_seed", "$.random_seed", "random_seed must be an integer."))
    if not isinstance(manifest.tools, tuple) or not all(_is_nonempty_string(tool) for tool in manifest.tools):
        failures.append(_failure("invalid_tools", "$.tools", "tools must be an ordered tuple of non-empty strings."))
    elif len(set(manifest.tools)) != len(manifest.tools):
        failures.append(_failure("duplicate_tool", "$.tools", "tools must not contain duplicates."))
    if tuple(sorted(manifest.task_ids)) != manifest.task_ids or len(set(manifest.task_ids)) != len(manifest.task_ids):
        failures.append(
            _failure("noncanonical_task_order", "$.task_ids", "task_ids must be unique and sorted lexicographically.")
        )
    if not manifest.task_ids:
        failures.append(_failure("empty_task_selection", "$.task_ids", "A run must select at least one task."))
    for field_name in (
        "run_id",
        "benchmark_snapshot",
        "evaluator_version",
        "evaluation_date",
        "model_provider",
        "model_id",
        "model_snapshot",
        "weights_hash",
        "configuration_id",
        "configuration_sha256",
        "provider_adapter_id",
        "provider_request_parameters_sha256",
        "prompt_policy_hash",
        "solver_commit",
        "training_data_manifest",
        "synthetic_data_manifest",
        "verifier",
        "memory_policy",
        "search_policy",
        "hardware",
        "contamination_status",
        "rules_snapshot_id",
        "rules_sha256",
        "scorer_status",
        "official_status",
        "parity_status",
    ):
        if not _is_nonempty_string(getattr(manifest, field_name)):
            failures.append(_failure("invalid_manifest_string", f"$.{field_name}", f"{field_name} must be a non-empty string."))
    for field_name in ("configuration_sha256", "provider_request_parameters_sha256", "prompt_policy_hash", "rules_sha256"):
        value = getattr(manifest, field_name)
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            failures.append(_failure("invalid_sha256", f"$.{field_name}", f"{field_name} must be a lowercase SHA-256 hex digest."))
    for field_name in ("provider_request_parameters", "prompt_policy", "retry_policy"):
        value = getattr(manifest, field_name)
        if not isinstance(value, Mapping):
            failures.append(_failure("invalid_manifest_object", f"$.{field_name}", f"{field_name} must be a JSON object."))
    retry_count = manifest.retry_policy.get("max_retries") if isinstance(manifest.retry_policy, Mapping) else None
    if not _is_int(retry_count) or retry_count < 0:
        failures.append(_failure("invalid_retry_policy", "$.retry_policy.max_retries", "retry_policy.max_retries must be a non-negative integer."))
    if not isinstance(manifest.estimated_cost_usd, (int, float)) or isinstance(manifest.estimated_cost_usd, bool) or not math.isfinite(manifest.estimated_cost_usd) or manifest.estimated_cost_usd < 0:
        failures.append(_failure("invalid_estimated_cost", "$.estimated_cost_usd", "estimated_cost_usd must be a non-negative finite number."))

    budget = manifest.budget
    for field_name in (
        "num_attempts",
        "max_input_tokens",
        "max_output_tokens",
        "max_model_calls_per_task",
        "max_rollouts_per_task",
        "concurrency_limit",
    ):
        value = getattr(budget, field_name)
        if not _is_int(value) or value < 1:
            failures.append(_failure("invalid_budget_limit", f"$.{field_name}", f"{field_name} must be a positive integer."))
    if not isinstance(budget.wall_clock_limit_seconds, (int, float)) or isinstance(budget.wall_clock_limit_seconds, bool) or not math.isfinite(budget.wall_clock_limit_seconds) or budget.wall_clock_limit_seconds <= 0:
        failures.append(_failure("invalid_wall_clock_limit", "$.wall_clock_limit_seconds", "wall_clock_limit_seconds must be a positive finite number."))
    if budget.concurrency_limit != 1:
        failures.append(
            _failure(
                "unsupported_concurrency_limit",
                "$.concurrency_limit",
                "The deterministic in-process Stage 2 runner supports concurrency_limit=1 only.",
            )
        )
    if budget.num_attempts > identity.max_attempts:
        failures.append(
            _failure(
                "attempt_policy_exceeded",
                "$.num_attempts",
                "num_attempts exceeds the frozen local A1 native attempt policy.",
            )
        )
    if manifest.evaluator_version != identity.evaluator_version:
        failures.append(_failure("evaluator_version_mismatch", "$.evaluator_version", "Manifest evaluator version does not match the active evaluator."))
    if manifest.rules_snapshot_id != identity.rules_snapshot_id:
        failures.append(_failure("rules_snapshot_mismatch", "$.rules_snapshot_id", "Manifest rules snapshot ID does not match the active evaluator."))
    if manifest.rules_sha256 != identity.rules_sha256:
        failures.append(_failure("rules_hash_mismatch", "$.rules_sha256", "Manifest rules hash does not match the active evaluator."))
    if manifest.scorer_status != identity.scorer_status:
        failures.append(_failure("scorer_status_mismatch", "$.scorer_status", "Manifest scorer status does not match the active evaluator."))
    if manifest.official_status != identity.official_status:
        failures.append(_failure("official_status_mismatch", "$.official_status", "Manifest official status does not match the active evaluator."))
    if manifest.parity_status != identity.parity_status:
        failures.append(_failure("parity_status_mismatch", "$.parity_status", "Manifest parity status does not match the active evaluator."))
    return ValidationResult(manifest if not failures else None, tuple(failures))


@runtime_checkable
class Solver(Protocol):
    """The minimum, model-independent Stage 2 solver contract."""

    def solve(self, task: TaskView, budget: InferenceBudget) -> CandidateSet:
        """Return ordered candidates for one solver-safe ARC task."""


@runtime_checkable
class SolverFactory(Protocol):
    """Construct a solver after the run manifest and budget are frozen."""

    def create(self, manifest: RunManifest, budget: InferenceBudget) -> Solver:
        """Initialize the solver for this frozen development run."""


class BudgetExceeded(RuntimeError):
    """Raised when instrumented usage attempts to reserve more than the budget."""

    def __init__(self, failure: ValidationFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


class SolverTimeout(TimeoutError):
    """A timeout with an explicit cooperative-cancellation outcome."""

    def __init__(self, cooperative: bool) -> None:
        super().__init__("Solver exceeded the frozen wall-clock limit.")
        self.cooperative = cooperative


class _UsageTracker:
    def __init__(
        self,
        budget: InferenceBudget,
        task_id: str,
        attempt: int,
        on_usage: Callable[[TaskUsage, TaskUsage], None],
    ) -> None:
        self._budget = budget
        self._task_id = task_id
        self._attempt = attempt
        self._on_usage = on_usage
        self._usage = TaskUsage()
        self._cancelled = False
        self._lock = threading.Lock()

    @property
    def usage(self) -> TaskUsage:
        with self._lock:
            return self._usage

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    def begin_invocation(self) -> None:
        self.reserve(solver_invocations=1)

    def reserve(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model_calls: int = 0,
        rollouts: int = 0,
        solver_invocations: int = 0,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        values = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model_calls": model_calls,
            "rollouts": rollouts,
            "solver_invocations": solver_invocations,
        }
        if any(not _is_int(value) or value < 0 for value in values.values()):
            raise BudgetExceeded(_failure("invalid_usage_delta", "$.usage", "Usage counters must be non-negative integers."))
        if not isinstance(estimated_cost_usd, (int, float)) or isinstance(estimated_cost_usd, bool) or not math.isfinite(estimated_cost_usd) or estimated_cost_usd < 0:
            raise BudgetExceeded(_failure("invalid_cost_delta", "$.usage.estimated_cost_usd", "Cost must be a non-negative finite number."))
        with self._lock:
            if self._cancelled:
                raise BudgetExceeded(_failure("solver_cancelled", "$.task", "The solver invocation was cancelled by the runner."))
            proposed = self._usage.plus(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_calls=model_calls,
                rollouts=rollouts,
                solver_invocations=solver_invocations,
                estimated_cost_usd=float(estimated_cost_usd),
            )
            limits = {
                "input_tokens": self._budget.max_input_tokens,
                "output_tokens": self._budget.max_output_tokens,
                "model_calls": self._budget.max_model_calls_per_task,
                "rollouts": self._budget.max_rollouts_per_task,
            }
            for name, limit in limits.items():
                if getattr(proposed, name) > limit:
                    raise BudgetExceeded(
                        _failure(
                            "budget_exceeded",
                            f"$.usage.{name}",
                            f"Task {self._task_id!r} attempt {self._attempt} would exceed {name} limit {limit}.",
                        )
                    )
            previous = self._usage
            self._usage = proposed
        self._on_usage(previous, proposed)

    def release(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        """Release an unused pre-request reservation after a provider response.

        Adapters must reserve the upper bound before an external request.  A
        response can then disclose smaller observed input/output usage or cost.
        Calls and rollouts are never releasable because the external work has
        already occurred.
        """
        values = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        if any(not _is_int(value) or value < 0 for value in values.values()):
            raise BudgetExceeded(_failure("invalid_usage_release", "$.usage", "Released token counts must be non-negative integers."))
        if not isinstance(estimated_cost_usd, (int, float)) or isinstance(estimated_cost_usd, bool) or not math.isfinite(estimated_cost_usd) or estimated_cost_usd < 0:
            raise BudgetExceeded(_failure("invalid_cost_release", "$.usage.estimated_cost_usd", "Released cost must be a non-negative finite number."))
        with self._lock:
            if input_tokens > self._usage.input_tokens or output_tokens > self._usage.output_tokens or float(estimated_cost_usd) > self._usage.estimated_cost_usd:
                raise BudgetExceeded(_failure("usage_release_exceeds_reservation", "$.usage", "Adapter attempted to release more usage than was reserved."))
            previous = self._usage
            self._usage = self._usage.plus(
                input_tokens=-input_tokens,
                output_tokens=-output_tokens,
                estimated_cost_usd=-float(estimated_cost_usd),
            )
            current = self._usage
        self._on_usage(previous, current)


_ACTIVE_USAGE_TRACKER: ContextVar[_UsageTracker | None] = ContextVar("spex_arc_active_usage_tracker", default=None)


def record_usage(
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model_calls: int = 0,
    rollouts: int = 0,
    estimated_cost_usd: float = 0.0,
) -> None:
    """Reserve instrumented resource use before a solver performs that work.

    Provider adapters introduced in a later stage must call this before each
    request or rollout.  A solver that performs undeclared external work is
    outside this development-only in-process contract and cannot support a
    resource-attribution claim.
    """
    tracker = _ACTIVE_USAGE_TRACKER.get()
    if tracker is None:
        raise RuntimeError("record_usage() may be called only while ArcA1Runner invokes a solver.")
    tracker.reserve(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_calls=model_calls,
        rollouts=rollouts,
        estimated_cost_usd=estimated_cost_usd,
    )


def release_usage(
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
) -> None:
    """Settle unused pre-request provider reservations in the active task.

    This may only reduce tokens or estimated cost reserved before a model call;
    it cannot reduce model calls, rollouts, or solver invocations.
    """
    tracker = _ACTIVE_USAGE_TRACKER.get()
    if tracker is None:
        raise RuntimeError("release_usage() may be called only while ArcA1Runner invokes a solver.")
    tracker.release(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )


@dataclass(frozen=True)
class RunResult:
    """A development-run summary derived from the immutable run bundle."""

    run_id: str
    artifact_directory: Path
    completed_task_ids: tuple[str, ...]
    executed_task_ids: tuple[str, ...]
    resumed_task_ids: tuple[str, ...]
    metrics: Mapping[str, Any]


@dataclass
class _ArtifactStore:
    root: Path
    manifest: RunManifest
    _predictions: dict[str, dict[str, Any]] = field(default_factory=dict)
    _events: list[dict[str, Any]] = field(default_factory=list)
    _failures: dict[str, dict[str, Any]] = field(default_factory=dict)
    _deviations: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def open(cls, root: Path, manifest: RunManifest) -> "_ArtifactStore":
        root.mkdir(parents=True, exist_ok=True)
        manifest_path = root / _BUNDLE_FILENAMES["manifest"]
        if manifest_path.exists():
            existing = _read_json_object(manifest_path, "manifest")
            if existing != manifest.to_json():
                raise ValueError("Existing run bundle manifest does not exactly match the frozen manifest.")
        else:
            _atomic_write(manifest_path, _canonical_json_bytes(manifest.to_json()))

        store = cls(root=root, manifest=manifest)
        store._predictions = _read_jsonl_by_task(root / _BUNDLE_FILENAMES["predictions"], "predictions")
        store._events = _read_jsonl(root / _BUNDLE_FILENAMES["events"], "events")
        store._failures = _read_jsonl_by_task(root / _BUNDLE_FILENAMES["failures"], "failures")
        store._deviations = _read_json_array(root / _BUNDLE_FILENAMES["deviations"], "deviations")
        store._ensure_files()
        store._reconcile_failure_index()
        return store

    @property
    def completed_task_ids(self) -> set[str]:
        return set(self._predictions)

    def unfinished_started_task_ids(self) -> set[str]:
        started = {
            event["task_id"]
            for event in self._events
            if event.get("event_type") == "task_attempt_started" and isinstance(event.get("task_id"), str)
        }
        finalized = {
            event["task_id"]
            for event in self._events
            if event.get("event_type") == "task_finalized" and isinstance(event.get("task_id"), str)
        }
        return started - finalized - self.completed_task_ids

    def append_event(self, event_type: str, **fields: Any) -> None:
        event = {"event_type": event_type, "sequence": len(self._events) + 1, **fields}
        self._events.append(event)
        _atomic_write(self.root / _BUNDLE_FILENAMES["events"], _jsonl_bytes(self._events))

    def record_usage(self, task_id: str, attempt: int, previous: TaskUsage, current: TaskUsage) -> None:
        delta = TaskUsage(
            input_tokens=current.input_tokens - previous.input_tokens,
            output_tokens=current.output_tokens - previous.output_tokens,
            model_calls=current.model_calls - previous.model_calls,
            rollouts=current.rollouts - previous.rollouts,
            solver_invocations=current.solver_invocations - previous.solver_invocations,
            estimated_cost_usd=current.estimated_cost_usd - previous.estimated_cost_usd,
            wall_clock_seconds=current.wall_clock_seconds - previous.wall_clock_seconds,
        )
        event_type = "usage_reserved" if all(
            value >= 0
            for value in (
                delta.input_tokens,
                delta.output_tokens,
                delta.model_calls,
                delta.rollouts,
                delta.solver_invocations,
                delta.estimated_cost_usd,
            )
        ) else "usage_released"
        self.append_event(
            event_type,
            attempt=attempt,
            task_id=task_id,
            usage_delta=delta.to_json(),
            usage_total=current.to_json(),
        )
        self.write_costs()

    def record_wall_clock(self, task_id: str, attempt: int, elapsed_seconds: float) -> None:
        self.append_event(
            "wall_clock_observed",
            attempt=attempt,
            elapsed_seconds=elapsed_seconds,
            task_id=task_id,
        )
        self.write_costs()

    def finalize_task(self, record: dict[str, Any], failure_record: dict[str, Any] | None) -> None:
        task_id = record["task_id"]
        if task_id in self._predictions:
            raise ValueError(f"Run bundle already has a terminal record for task {task_id!r}.")
        self._predictions[task_id] = record
        _atomic_write(
            self.root / _BUNDLE_FILENAMES["predictions"],
            _jsonl_bytes(self._predictions[task_id] for task_id in sorted(self._predictions)),
        )
        if failure_record is not None:
            self._failures[task_id] = failure_record
        self._reconcile_failure_index()
        self.append_event("task_finalized", task_id=task_id, terminal_status=record["terminal_status"])
        self.write_costs()

    def add_deviation(self, code: str, message: str) -> None:
        deviation = {"code": code, "message": message}
        if deviation not in self._deviations:
            self._deviations.append(deviation)
            _atomic_write(self.root / _BUNDLE_FILENAMES["deviations"], _canonical_json_bytes(self._deviations))

    def write_costs(self) -> dict[str, Any]:
        totals_by_task: dict[str, TaskUsage] = {}
        for event in self._events:
            task_id = event.get("task_id")
            if not isinstance(task_id, str):
                continue
            if event.get("event_type") in {"usage_reserved", "usage_released"}:
                raw_delta = event.get("usage_delta")
                if not isinstance(raw_delta, dict):
                    continue
                delta = _usage_from_json(raw_delta)
            elif event.get("event_type") == "wall_clock_observed":
                elapsed = event.get("elapsed_seconds")
                if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
                    continue
                delta = TaskUsage(wall_clock_seconds=float(elapsed))
            else:
                continue
            totals_by_task[task_id] = totals_by_task.get(task_id, TaskUsage()).plus(
                input_tokens=delta.input_tokens,
                output_tokens=delta.output_tokens,
                model_calls=delta.model_calls,
                rollouts=delta.rollouts,
                solver_invocations=delta.solver_invocations,
                estimated_cost_usd=delta.estimated_cost_usd,
                wall_clock_seconds=delta.wall_clock_seconds,
            )
        observed_cost = sum(usage.estimated_cost_usd for usage in totals_by_task.values())
        payload = {
            "artifact_type": "arc-agi-1-development-cost-ledger",
            "currency": "USD",
            "estimated_run_cost_usd": self.manifest.estimated_cost_usd,
            "observed_run_cost_usd": observed_cost,
            "per_task": [
                {"task_id": task_id, "usage": totals_by_task[task_id].to_json()}
                for task_id in sorted(totals_by_task)
            ],
            "run_id": self.manifest.run_id,
            "schema_version": "1.0",
        }
        _atomic_write(self.root / _BUNDLE_FILENAMES["costs"], _canonical_json_bytes(payload))
        return payload

    def usage_for_task(self, task_id: str) -> TaskUsage:
        """Reconstruct one task's usage from immutable event records."""
        total = TaskUsage()
        for event in self._events:
            if event.get("task_id") != task_id:
                continue
            if event.get("event_type") in {"usage_reserved", "usage_released"} and isinstance(event.get("usage_delta"), dict):
                delta = _usage_from_json(event["usage_delta"])
            elif event.get("event_type") == "wall_clock_observed":
                elapsed = event.get("elapsed_seconds")
                if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
                    continue
                delta = TaskUsage(wall_clock_seconds=float(elapsed))
            else:
                continue
            total = _add_usage(total, delta)
        return total

    def write_metrics(self, evaluator: LocalReferenceEvaluator, tasks_by_id: Mapping[str, Task]) -> dict[str, Any]:
        scores: list[TaskScore] = []
        for task_id in self.manifest.task_ids:
            record = self._predictions.get(task_id)
            if record is None:
                continue
            task = tasks_by_id[task_id]
            candidate = _candidate_from_record(record)
            failures = _failures_from_json(record.get("runner_failures", []))
            scores.append(evaluator.score_task(task, candidate, failures))
        task_count = len(self.manifest.task_ids)
        completed_task_count = len(self._predictions)
        if scores:
            exact_at_1 = sum(score.exact_at_1 for score in scores) / task_count
            exact_at_native = sum(score.exact_at_native for score in scores) / task_count
            invalid_output_rate = sum(score.invalid_output for score in scores) / task_count
            pixel_accuracy = sum(score.pixel_accuracy for score in scores) / task_count
            shape_accuracy = sum(score.shape_accuracy for score in scores) / task_count
        else:
            exact_at_1 = exact_at_native = invalid_output_rate = pixel_accuracy = shape_accuracy = 0.0
        failure_counts = Counter(
            failure.code
            for score in scores
            for failure in score.failures
        )
        payload = {
            "aggregate_metrics": {
                "exact_at_1": exact_at_1,
                "exact_at_native": exact_at_native,
                "invalid_output_rate": invalid_output_rate,
                "pixel_accuracy": pixel_accuracy,
                "shape_accuracy": shape_accuracy,
                "task_count": task_count,
            },
            "artifact_type": "arc-agi-1-development-run-metrics",
            "completed_task_count": completed_task_count,
            "evaluator": evaluator.identity.to_json(),
            "failure_type_counts": dict(sorted(failure_counts.items())),
            "record_sources": {
                "failures": _BUNDLE_FILENAMES["failures"],
                "predictions": _BUNDLE_FILENAMES["predictions"],
            },
            "run_id": self.manifest.run_id,
            "schema_version": "1.0",
            "task_scores": [score.to_json() for score in scores],
        }
        _atomic_write(self.root / _BUNDLE_FILENAMES["metrics"], _canonical_json_bytes(payload))
        return payload

    def _ensure_files(self) -> None:
        for key in ("predictions", "events", "failures"):
            path = self.root / _BUNDLE_FILENAMES[key]
            if not path.exists():
                _atomic_write(path, b"")
        for key in ("deviations",):
            path = self.root / _BUNDLE_FILENAMES[key]
            if not path.exists():
                _atomic_write(path, _canonical_json_bytes([]))
        for key in ("metrics", "costs"):
            path = self.root / _BUNDLE_FILENAMES[key]
            if not path.exists():
                _atomic_write(path, _canonical_json_bytes({}))

    def _reconcile_failure_index(self) -> None:
        for task_id, record in self._predictions.items():
            failures = record.get("runner_failures", [])
            attempt_failures = record.get("attempt_failures", [])
            score = record.get("task_score", {})
            score_failures = score.get("failures", []) if isinstance(score, dict) else []
            if failures or attempt_failures or score_failures:
                self._failures[task_id] = {
                    "classification": record.get("terminal_status", "invalid_output"),
                    "run_id": self.manifest.run_id,
                    "attempt_failures": attempt_failures,
                    "runner_failures": failures,
                    "score_failures": score_failures,
                    "task_id": task_id,
                }
        _atomic_write(
            self.root / _BUNDLE_FILENAMES["failures"],
            _jsonl_bytes(self._failures[task_id] for task_id in sorted(self._failures)),
        )


def _atomic_write(path: Path, data: bytes) -> None:
    """Durably replace one artifact, never exposing a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except OSError:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"Cannot read {label} artifact {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} artifact {path} must be a JSON object.")
    return value


def _read_json_array(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"Cannot read {label} artifact {path}: {error}") from error
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{label} artifact {path} must be a JSON array of objects.")
    return value


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"Cannot read {label} artifact {path}: {error}") from error
    for line_number, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Malformed {label} JSONL record {line_number}: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"{label} JSONL record {line_number} must be an object.")
        records.append(value)
    return records


def _read_jsonl_by_task(path: Path, label: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in _read_jsonl(path, label):
        task_id = record.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"{label} record lacks a non-empty task_id.")
        if task_id in records:
            raise ValueError(f"{label} contains duplicate terminal records for task {task_id!r}.")
        records[task_id] = record
    return records


def _usage_from_json(value: Mapping[str, Any]) -> TaskUsage:
    return TaskUsage(
        input_tokens=value.get("input_tokens", 0) if _is_int(value.get("input_tokens", 0)) else 0,
        output_tokens=value.get("output_tokens", 0) if _is_int(value.get("output_tokens", 0)) else 0,
        model_calls=value.get("model_calls", 0) if _is_int(value.get("model_calls", 0)) else 0,
        rollouts=value.get("rollouts", 0) if _is_int(value.get("rollouts", 0)) else 0,
        solver_invocations=value.get("solver_invocations", 0) if _is_int(value.get("solver_invocations", 0)) else 0,
        estimated_cost_usd=float(value.get("estimated_cost_usd", 0.0)) if isinstance(value.get("estimated_cost_usd", 0.0), (int, float)) else 0.0,
        wall_clock_seconds=float(value.get("wall_clock_seconds", 0.0)) if isinstance(value.get("wall_clock_seconds", 0.0), (int, float)) else 0.0,
    )


def _failures_from_json(value: Any) -> tuple[ValidationFailure, ...]:
    if not isinstance(value, list):
        return ()
    failures: list[ValidationFailure] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        code, path, message = item.get("code"), item.get("path"), item.get("message")
        if all(isinstance(field, str) for field in (code, path, message)):
            failures.append(ValidationFailure(code=code, path=path, message=message))
    return tuple(failures)


def _candidate_from_record(record: Mapping[str, Any]) -> CandidateSet | None:
    raw_candidate = record.get("candidate_set")
    if raw_candidate is None:
        return None
    parsed = parse_candidate_set_object(raw_candidate)
    return parsed.value


class ArcA1Runner:
    """Execute a frozen development run and preserve its complete run bundle."""

    def __init__(
        self,
        manifest: RunManifest,
        evaluator: LocalReferenceEvaluator,
        solver_factory: SolverFactory | Callable[[RunManifest, InferenceBudget], Solver],
        artifact_root: Path,
        *,
        max_retries: int = 0,
    ) -> None:
        self.manifest = manifest
        self.evaluator = evaluator
        self.solver_factory = solver_factory
        self.artifact_root = artifact_root
        self.max_retries = max_retries

    def run(self, tasks: Iterable[Task]) -> RunResult:
        """Execute or resume the manifest's task selection in stable task-ID order."""
        manifest_result = validate_run_manifest(self.manifest, self.evaluator.identity)
        if manifest_result.value is None:
            raise ValueError(f"Invalid run manifest: {[failure.to_json() for failure in manifest_result.failures]}")
        if not _is_int(self.max_retries) or self.max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer.")
        if self.max_retries != self.manifest.retry_policy["max_retries"]:
            raise ValueError("Runner max_retries must match the frozen manifest retry_policy.max_retries.")

        tasks_by_id = self._index_tasks(tasks)
        selected = tuple(tasks_by_id[task_id] for task_id in self.manifest.task_ids)
        store = _ArtifactStore.open(self.artifact_root / self.manifest.run_id, self.manifest)
        store.append_event("run_opened", run_id=self.manifest.run_id)

        resumed: list[str] = []
        for task in selected:
            if task.task_id in store.unfinished_started_task_ids():
                failure = _failure(
                    "interrupted_before_finalization",
                    "$.task",
                    "A prior process stopped after this task began; it is terminally recorded without rerun to avoid double counting.",
                )
                self._finalize_task(store, task, None, store.usage_for_task(task.task_id), "interrupted", (failure,))
                resumed.append(task.task_id)

        pending = [task for task in selected if task.task_id not in store.completed_task_ids]
        if pending:
            try:
                solver = self._initialize_solver(store)
            except RuntimeError as error:
                initialization_failures = (
                    _failure("solver_initialization_failed", "$.solver", str(error)),
                )
                store.add_deviation("solver_initialization_failed", "The solver could not be initialized under the frozen run configuration.")
                for task in pending:
                    self._finalize_task(store, task, None, TaskUsage(), "solver_initialization_failed", initialization_failures)
            else:
                policy_failures = self._validate_solver_policy(solver)
                if policy_failures:
                    store.add_deviation("solver_policy_rejected", "Solver requirements violate the frozen network/tool policy.")
                    for task in pending:
                        self._finalize_task(store, task, None, TaskUsage(), "policy_violation", policy_failures)
                else:
                    for index, task in enumerate(pending):
                        if self._run_one_task(store, task, solver):
                            continue
                        store.add_deviation(
                            "noncooperative_timeout",
                            "A timed-out solver did not terminate after cancellation; remaining tasks were not invoked.",
                        )
                        for remaining_task in pending[index + 1 :]:
                            failure = _failure(
                                "run_aborted_after_noncooperative_timeout",
                                "$.solver",
                                "Runner did not invoke this task because an earlier solver thread did not terminate after timeout cancellation.",
                            )
                            self._finalize_task(
                                store,
                                remaining_task,
                                None,
                                TaskUsage(),
                                "run_aborted_after_timeout",
                                (failure,),
                            )
                        break

        metrics = store.write_metrics(self.evaluator, tasks_by_id)
        store.write_costs()
        store.append_event("run_completed", run_id=self.manifest.run_id)
        return RunResult(
            run_id=self.manifest.run_id,
            artifact_directory=store.root,
            completed_task_ids=tuple(sorted(store.completed_task_ids)),
            executed_task_ids=tuple(task.task_id for task in pending),
            resumed_task_ids=tuple(resumed),
            metrics=metrics,
        )

    def _index_tasks(self, tasks: Iterable[Task]) -> dict[str, Task]:
        indexed: dict[str, Task] = {}
        for task in tasks:
            if not isinstance(task, Task):
                raise ValueError("Runner tasks must be Task instances from the strict parser.")
            if task.task_id in indexed:
                raise ValueError(f"Duplicate task ID supplied to runner: {task.task_id!r}.")
            indexed[task.task_id] = task
        missing = [task_id for task_id in self.manifest.task_ids if task_id not in indexed]
        if missing:
            raise ValueError(f"Manifest-selected tasks are unavailable to runner: {missing!r}.")
        return indexed

    def _initialize_solver(self, store: _ArtifactStore) -> Solver:
        try:
            create = getattr(self.solver_factory, "create", None)
            solver = create(self.manifest, self.manifest.budget) if callable(create) else self.solver_factory(self.manifest, self.manifest.budget)
        except Exception as error:
            store.append_event("solver_initialization_failed", failure_type=type(error).__name__)
            raise RuntimeError(f"Solver initialization failed: {type(error).__name__}: {error}") from error
        if not isinstance(solver, Solver):
            raise RuntimeError("Solver factory did not return an object with solve(task, budget).")
        store.append_event("solver_initialized", solver_type=type(solver).__name__)
        return solver

    def _validate_solver_policy(self, solver: Solver) -> tuple[ValidationFailure, ...]:
        failures: list[ValidationFailure] = []
        if getattr(solver, "requires_network", False) and not self.manifest.network_access:
            failures.append(
                _failure("network_policy_violation", "$.network_access", "Solver declares network access but the manifest forbids it.")
            )
        required_tools = getattr(solver, "required_tools", ())
        if not isinstance(required_tools, tuple) or not all(isinstance(tool, str) for tool in required_tools):
            failures.append(_failure("invalid_solver_tools", "$.solver", "required_tools must be a tuple of strings."))
        else:
            disallowed = sorted(set(required_tools) - set(self.manifest.tools))
            if disallowed:
                failures.append(
                    _failure("tool_policy_violation", "$.tools", f"Solver requires disallowed tools: {', '.join(disallowed)}.")
                )
        return tuple(failures)

    def _run_one_task(self, store: _ArtifactStore, task: Task, solver: Solver) -> bool:
        total_usage = TaskUsage()
        failures: tuple[ValidationFailure, ...] = ()
        attempt_failures: list[dict[str, Any]] = []
        candidate: CandidateSet | None = None
        terminal_status = "solver_failure"
        for invocation in range(1, self.max_retries + 2):
            store.append_event("task_attempt_started", attempt=invocation, task_id=task.task_id)
            tracker = _UsageTracker(
                self.manifest.budget,
                task.task_id,
                invocation,
                lambda previous, current: store.record_usage(task.task_id, invocation, previous, current),
            )
            started = time.monotonic()
            try:
                candidate = self._solve_with_timeout(solver, task.solver_view(), tracker, invocation)
            except BudgetExceeded as error:
                elapsed = time.monotonic() - started
                total_usage = _add_usage(total_usage, tracker.usage.plus(wall_clock_seconds=elapsed))
                store.record_wall_clock(task.task_id, invocation, elapsed)
                failures = (error.failure,)
                attempt_failures.append(
                    {"attempt": invocation, "classification": "budget_exceeded", "failures": [error.failure.to_json()]}
                )
                terminal_status = "budget_exceeded"
                store.append_event("task_attempt_failed", attempt=invocation, task_id=task.task_id, failure_type=error.failure.code)
                break
            except SolverTimeout as error:
                elapsed = time.monotonic() - started
                total_usage = _add_usage(total_usage, tracker.usage.plus(wall_clock_seconds=elapsed))
                store.record_wall_clock(task.task_id, invocation, elapsed)
                failures = (_failure("timeout", "$.wall_clock_limit_seconds", "Solver did not finish within the frozen wall-clock limit."),)
                terminal_status = "timeout" if error.cooperative else "timeout_unterminated"
                attempt_failures.append(
                    {"attempt": invocation, "classification": terminal_status, "failures": [failure.to_json() for failure in failures]}
                )
                store.append_event("task_attempt_failed", attempt=invocation, task_id=task.task_id, failure_type="timeout")
                if error.cooperative and invocation <= self.max_retries:
                    failures = ()
                    continue
                break
            except Exception as error:
                elapsed = time.monotonic() - started
                total_usage = _add_usage(total_usage, tracker.usage.plus(wall_clock_seconds=elapsed))
                store.record_wall_clock(task.task_id, invocation, elapsed)
                failures = (
                    _failure(
                        "solver_exception",
                        "$.solver",
                        f"Solver raised {type(error).__name__}: {error}",
                    ),
                )
                terminal_status = "solver_exception"
                attempt_failures.append(
                    {"attempt": invocation, "classification": terminal_status, "failures": [failure.to_json() for failure in failures]}
                )
                store.append_event("task_attempt_failed", attempt=invocation, task_id=task.task_id, failure_type=type(error).__name__)
                if invocation <= self.max_retries:
                    failures = ()
                    continue
                break
            elapsed = time.monotonic() - started
            total_usage = _add_usage(total_usage, tracker.usage.plus(wall_clock_seconds=elapsed))
            store.record_wall_clock(task.task_id, invocation, elapsed)
            if not isinstance(candidate, CandidateSet):
                candidate = None
                failures = (_failure("invalid_solver_return", "$.solver", "Solver must return a CandidateSet instance."),)
                terminal_status = "invalid_solver_return"
            elif len(candidate.candidates) > self.manifest.budget.num_attempts:
                failures = (
                    _failure(
                        "manifest_attempt_limit_exceeded",
                        "$.attempts",
                        "Solver returned more candidates than frozen num_attempts permits.",
                    ),
                )
                terminal_status = "invalid_output"
            else:
                terminal_status = "scored"
            store.append_event(
                "task_solver_finished",
                attempt=invocation,
                elapsed_seconds=elapsed,
                task_id=task.task_id,
                usage=tracker.usage.to_json(),
            )
            break
        self._finalize_task(store, task, candidate, total_usage, terminal_status, failures, attempt_failures)
        return terminal_status != "timeout_unterminated"

    def _solve_with_timeout(self, solver: Solver, view: TaskView, tracker: _UsageTracker, invocation: int) -> CandidateSet:
        def invoke() -> CandidateSet:
            task_seed = _task_seed(self.manifest.random_seed, view.task_id, invocation)
            random.seed(task_seed)
            token = _ACTIVE_USAGE_TRACKER.set(tracker)
            try:
                tracker.begin_invocation()
                return solver.solve(view, self.manifest.budget)
            finally:
                _ACTIVE_USAGE_TRACKER.reset(token)

        context = copy_context()
        # ThreadPoolExecutor is imported lazily to keep the runner's public
        # dependency surface to the standard library and permit cooperative
        # cancellation around an arbitrary in-process development solver.
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="spex-arc-solver")
        future = pool.submit(context.run, invoke)
        wait_for_shutdown = False
        try:
            result = future.result(timeout=self.manifest.budget.wall_clock_limit_seconds)
            wait_for_shutdown = True
            return result
        except FutureTimeoutError as error:
            tracker.cancel()
            cancel = getattr(solver, "cancel", None)
            if callable(cancel):
                try:
                    cancel(view.task_id)
                except Exception:
                    pass
            future.cancel()
            try:
                future.result(timeout=0.1)
            except FutureTimeoutError:
                cooperative = False
            except BaseException:
                cooperative = True
            else:
                cooperative = True
            wait_for_shutdown = cooperative
            raise SolverTimeout(cooperative) from error
        finally:
            # A timed-out, non-cooperative in-process solver cannot be killed
            # safely by Python.  The tracker is cancelled, no later usage can
            # be recorded, and the run never rescoring/reuses its output.
            pool.shutdown(wait=wait_for_shutdown, cancel_futures=True)

    def _finalize_task(
        self,
        store: _ArtifactStore,
        task: Task,
        candidate: CandidateSet | None,
        usage: TaskUsage,
        terminal_status: str,
        failures: tuple[ValidationFailure, ...],
        attempt_failures: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        runner_failures = failures
        candidate_payload: dict[str, Any] | None = None
        if candidate is not None:
            try:
                candidate_payload = candidate_set_to_json(candidate)
            except (AttributeError, TypeError) as error:
                runner_failures = (
                    *runner_failures,
                    _failure(
                        "candidate_serialization_failed",
                        "$.solver",
                        f"Solver returned a candidate set that cannot be serialized: {type(error).__name__}: {error}",
                    ),
                )
                terminal_status = "invalid_output"
        score = self.evaluator.score_task(task, candidate, runner_failures)
        record = {
            "attempt_failures": list(attempt_failures),
            "candidate_set": candidate_payload,
            "run_id": self.manifest.run_id,
            "runner_failures": [failure.to_json() for failure in runner_failures],
            "task_id": task.task_id,
            "task_score": score.to_json(),
            "terminal_status": terminal_status,
            "usage": usage.to_json(),
        }
        failure_record = None
        if runner_failures or score.failures or record["attempt_failures"]:
            failure_record = {
                "classification": terminal_status,
                "run_id": self.manifest.run_id,
                "attempt_failures": record["attempt_failures"],
                "runner_failures": [failure.to_json() for failure in runner_failures],
                "score_failures": [failure.to_json() for failure in score.failures],
                "task_id": task.task_id,
            }
        store.finalize_task(record, failure_record)


def _add_usage(first: TaskUsage, second: TaskUsage) -> TaskUsage:
    return first.plus(
        input_tokens=second.input_tokens,
        output_tokens=second.output_tokens,
        model_calls=second.model_calls,
        rollouts=second.rollouts,
        solver_invocations=second.solver_invocations,
        estimated_cost_usd=second.estimated_cost_usd,
        wall_clock_seconds=second.wall_clock_seconds,
    )


def _task_seed(run_seed: int, task_id: str, invocation: int) -> int:
    material = f"{run_seed}:{task_id}:{invocation}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")

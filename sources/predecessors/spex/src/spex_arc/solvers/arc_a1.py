"""Provider-independent G0 and S1 development solvers for ARC-AGI-1.

These classes deliberately provide no concrete network provider.  An approved
provider adapter must supply its exact identity and request parameters, reserve
the request upper bound before invoking the provider, and settle unused budget
after it receives a response.  This keeps resource accounting in the common
runner rather than trusting provider-specific reporting after the fact.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable

from spex_arc.domain.arc_a1 import CandidateSet, TaskView, parse_candidate_set_json
from spex_arc.runner.arc_a1 import InferenceBudget, record_usage, release_usage


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


@dataclass(frozen=True)
class ModelIdentity:
    """Identity and non-secret request parameters for one approved model."""

    provider: str
    model_id: str
    model_snapshot: str
    weights_hash: str
    adapter_id: str
    request_parameters: Mapping[str, Any]

    @property
    def request_parameters_sha256(self) -> str:
        return _sha256_json(dict(self.request_parameters))

    def to_json(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "model_id": self.model_id,
            "model_snapshot": self.model_snapshot,
            "provider": self.provider,
            "request_parameters": dict(self.request_parameters),
            "request_parameters_sha256": self.request_parameters_sha256,
            "weights_hash": self.weights_hash,
        }


@dataclass(frozen=True)
class ModelRequest:
    """One fully specified model request without credentials or test outputs."""

    task_id: str
    messages: tuple[Mapping[str, str], ...]
    request_parameters: Mapping[str, Any]
    output_protocol: str = "arc-a1-candidate-set-json-v1"

    def to_json(self) -> dict[str, Any]:
        return {
            "messages": [dict(message) for message in self.messages],
            "output_protocol": self.output_protocol,
            "request_parameters": dict(self.request_parameters),
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class RequestReservation:
    """Maximum resource use reserved before the provider receives a request."""

    input_tokens: int
    max_output_tokens: int
    max_cost_usd: float
    model_calls: int = 1
    rollouts: int = 1

    def validate(self) -> None:
        for name in ("input_tokens", "max_output_tokens", "model_calls", "rollouts"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        if self.model_calls != 1 or self.rollouts != 1:
            raise ValueError("A G0/S1 provider completion must reserve exactly one model call and one rollout.")
        if not isinstance(self.max_cost_usd, (int, float)) or isinstance(self.max_cost_usd, bool) or not math.isfinite(self.max_cost_usd) or self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be a non-negative finite number.")


@dataclass(frozen=True)
class PreparedModelRequest:
    """A provider-ready request whose maximum use was calculated locally."""

    request: ModelRequest
    reservation: RequestReservation


@dataclass(frozen=True)
class ModelResponse:
    """A provider response and its observed use, excluding secret provider data."""

    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

    def validate_against(self, reservation: RequestReservation) -> None:
        for name in ("input_tokens", "output_tokens"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"Observed {name} must be a non-negative integer.")
        if not isinstance(self.cost_usd, (int, float)) or isinstance(self.cost_usd, bool) or not math.isfinite(self.cost_usd) or self.cost_usd < 0:
            raise ValueError("Observed cost_usd must be a non-negative finite number.")
        if self.input_tokens > reservation.input_tokens:
            raise ValueError("Provider reported input tokens above the pre-request reservation.")
        if self.output_tokens > reservation.max_output_tokens:
            raise ValueError("Provider reported output tokens above the pre-request reservation.")
        if float(self.cost_usd) > float(reservation.max_cost_usd):
            raise ValueError("Provider reported cost above the pre-request reservation.")


@runtime_checkable
class ModelAdapter(Protocol):
    """Provider boundary required by the G0/S1 solvers.

    ``prepare`` must not contact the provider.  ``complete`` is the only
    method allowed to do so, after the solver records the reservation.
    """

    identity: ModelIdentity
    requires_network: bool
    required_tools: tuple[str, ...]

    def prepare(self, request: ModelRequest, budget: InferenceBudget) -> PreparedModelRequest:
        """Build a request and calculate a hard upper bound before dispatch."""

    def complete(self, prepared: PreparedModelRequest) -> ModelResponse:
        """Invoke the configured provider and return its observable response."""


@dataclass(frozen=True)
class PromptPolicy:
    """A frozen prompt template and ARC JSON output protocol."""

    policy_id: str
    unit: str
    intervention: str
    system_instruction: str
    task_instruction: str
    representation: str

    def to_json(self) -> dict[str, str]:
        return {
            "intervention": self.intervention,
            "output_protocol": "arc-a1-candidate-set-json-v1",
            "policy_id": self.policy_id,
            "representation": self.representation,
            "system_instruction": self.system_instruction,
            "task_instruction": self.task_instruction,
            "unit": self.unit,
        }

    @property
    def sha256(self) -> str:
        return _sha256_json(self.to_json())

    def request_for(self, task: TaskView, request_parameters: Mapping[str, Any]) -> ModelRequest:
        task_payload = {
            "task_id": task.task_id,
            "test": [{"input": case.input.to_json()} for case in task.test],
            "train": [
                {"input": pair.input.to_json(), "output": pair.output.to_json()}
                for pair in task.train
            ],
        }
        protocol = {
            "attempts": [
                {
                    "attempt": 1,
                    "outputs": [["integer grid for each test input"]],
                }
            ],
            "task_id": task.task_id,
        }
        user_content = "\n\n".join(
            (
                self.task_instruction,
                "Task (test outputs deliberately omitted):\n" + json.dumps(task_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                "Return only a JSON object following this output shape:\n" + json.dumps(protocol, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            )
        )
        return ModelRequest(
            task_id=task.task_id,
            messages=(
                {"role": "system", "content": self.system_instruction},
                {"role": "user", "content": user_content},
            ),
            request_parameters=dict(request_parameters),
        )


class G0MinimalPromptPolicy(PromptPolicy):
    """The direct generalist prompt: no ARC-specific representation scaffold."""

    def __init__(self) -> None:
        super().__init__(
            policy_id="arc-a1-g0-minimal-v1",
            unit="G",
            intervention="none",
            system_instruction="Solve the supplied grid-transformation task. Return only the requested JSON object.",
            task_instruction="Infer the output grid or grids from the examples. Do not explain your reasoning.",
            representation="raw ARC train/test JSON only",
        )


class StructuredPromptPolicy(PromptPolicy):
    """The fixed S1 structured-prompt intervention, with no tools or search."""

    def __init__(self) -> None:
        super().__init__(
            policy_id="arc-a1-s1-structured-v1",
            unit="S",
            intervention="fixed-structured-prompt",
            system_instruction="Solve the supplied grid-transformation task. Return only the requested JSON object.",
            task_instruction=(
                "Use this fixed representation while solving: identify objects by color and connected components; "
                "compare each training input with its output for object selection, movement, recoloring, repetition, "
                "or grid completion; apply one consistent transformation to every test input. Do not explain your reasoning."
            ),
            representation="fixed object/component and transformation checklist",
        )


class _PromptedModelSolver:
    """Common one-call implementation used by G0 and S1."""

    required_tools: tuple[str, ...] = ()

    def __init__(self, adapter: ModelAdapter, policy: PromptPolicy) -> None:
        if not isinstance(adapter, ModelAdapter):
            raise TypeError("adapter must implement ModelAdapter.")
        self.adapter = adapter
        self.policy = policy
        self.requires_network = adapter.requires_network
        self.required_tools = adapter.required_tools

    def solve(self, task: TaskView, budget: InferenceBudget) -> CandidateSet:
        request = self.policy.request_for(task, self.adapter.identity.request_parameters)
        prepared = self.adapter.prepare(request, budget)
        if prepared.request != request:
            raise ValueError("Model adapter returned a prepared request that differs from the frozen prompt request.")
        prepared.reservation.validate()
        reservation = prepared.reservation
        if reservation.max_output_tokens > budget.max_output_tokens:
            raise ValueError("Provider reservation exceeds the frozen output-token budget.")
        record_usage(
            input_tokens=reservation.input_tokens,
            output_tokens=reservation.max_output_tokens,
            model_calls=reservation.model_calls,
            rollouts=reservation.rollouts,
            estimated_cost_usd=reservation.max_cost_usd,
        )
        response = self.adapter.complete(prepared)
        response.validate_against(reservation)
        release_usage(
            input_tokens=reservation.input_tokens - response.input_tokens,
            output_tokens=reservation.max_output_tokens - response.output_tokens,
            estimated_cost_usd=float(reservation.max_cost_usd) - float(response.cost_usd),
        )
        parsed = parse_candidate_set_json(response.text)
        if parsed.value is not None:
            return parsed.value
        # CandidateSet keeps the failure in the evaluator's structured
        # invalid-output path without exposing any test output to the solver.
        return CandidateSet(task_id=task.task_id, candidates=())


class G0Solver(_PromptedModelSolver):
    """Direct generalist configuration with the minimal frozen prompt."""

    def __init__(self, adapter: ModelAdapter) -> None:
        super().__init__(adapter, G0MinimalPromptPolicy())


class S1Solver(_PromptedModelSolver):
    """Same-backbone system configuration with only the frozen S1 prompt."""

    def __init__(self, adapter: ModelAdapter) -> None:
        super().__init__(adapter, StructuredPromptPolicy())

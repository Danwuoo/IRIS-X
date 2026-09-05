"""Immutable records for the provisional IRIS-X execution boundary.

The records preserve distinctions supported by the Phase 3/4 evidence. They do
not define fixture operations, provider types, persistence, or recovery logic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping


UNKNOWN = "Unknown"

ACTUAL_OUTCOMES = frozenset({"success", "partial", "failure", "unresolved"})
EVIDENCE_STATUSES = frozenset(
    {"sufficient", "insufficient", "invalid_binding", "not_assessed", "unresolved"}
)
ACCEPTANCE_DECISIONS = frozenset({"accept", "reject", "abstain", "not_applicable"})
TERMINAL_EXECUTION_STATUSES = frozenset({"completed", "failed", "rejected", "invalid"})


def sha256_bytes(content: bytes) -> str:
    """Return the SHA-256 identity of exact bytes."""

    return hashlib.sha256(content).hexdigest()


def _require_identity(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")


def _require_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class EvidenceRequirement:
    """An evidence declaration carried by the immutable task contract."""

    role: str
    artifact_id: str
    path: str

    def __post_init__(self) -> None:
        _require_identity(self.role, "role")
        _require_identity(self.artifact_id, "artifact_id")
        _require_identity(self.path, "path")


@dataclass(frozen=True)
class BoundEvidenceRequirement:
    """A contract declaration bound to exact execution-context bytes."""

    requirement: EvidenceRequirement
    sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.sha256, "sha256")

    @property
    def role(self) -> str:
        return self.requirement.role

    @property
    def artifact_id(self) -> str:
        return self.requirement.artifact_id

    @property
    def path(self) -> str:
        return self.requirement.path


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    contract_id: str
    expected_program_id: str
    expected_program_sha256: str
    execution_id: str
    configuration_id: str
    content: bytes
    evidence_requirements: tuple[EvidenceRequirement, ...]

    def __post_init__(self) -> None:
        for label in (
            "task_id",
            "contract_id",
            "expected_program_id",
            "execution_id",
            "configuration_id",
        ):
            _require_identity(getattr(self, label), label)
        _require_sha256(self.expected_program_sha256, "expected_program_sha256")
        if not isinstance(self.content, bytes):
            raise TypeError("contract content must be exact bytes")
        if not isinstance(self.evidence_requirements, tuple) or not all(
            isinstance(item, EvidenceRequirement) for item in self.evidence_requirements
        ):
            raise TypeError("evidence_requirements must be an immutable tuple")
        roles = tuple(item.role for item in self.evidence_requirements)
        if len(set(roles)) != len(roles):
            raise ValueError("evidence requirement roles must be unique")
        if set(roles) != {"task_contract", "program"}:
            raise ValueError("task_contract and program evidence requirements are required")
        requirements = {item.role: item for item in self.evidence_requirements}
        if requirements["task_contract"].artifact_id != self.contract_id:
            raise ValueError("task_contract requirement must identify this contract")
        if requirements["program"].artifact_id != self.expected_program_id:
            raise ValueError("program requirement must identify the expected program")

    @property
    def content_sha256(self) -> str:
        return sha256_bytes(self.content)

    @property
    def content_bytes(self) -> int:
        return len(self.content)


@dataclass(frozen=True)
class ProgramArtifact:
    program_id: str
    path: str
    content: bytes

    def __post_init__(self) -> None:
        _require_identity(self.program_id, "program_id")
        _require_identity(self.path, "path")
        if not isinstance(self.content, bytes):
            raise TypeError("program content must be exact bytes")

    @property
    def content_sha256(self) -> str:
        return sha256_bytes(self.content)

    @property
    def content_bytes(self) -> int:
        return len(self.content)


@dataclass(frozen=True)
class ExecutionIdentity:
    task_id: str
    contract_id: str
    program_id: str
    execution_id: str
    configuration_id: str

    def __post_init__(self) -> None:
        for label in self.__dataclass_fields__:
            _require_identity(getattr(self, label), label)


@dataclass(frozen=True)
class ExecutionContext:
    contract: TaskContract
    program: ProgramArtifact
    identity: ExecutionIdentity
    evidence_requirements: tuple[BoundEvidenceRequirement, ...]


@dataclass(frozen=True)
class ExecutionRequest:
    action_id: str
    operation: str
    target: str
    value: Any
    requires_mutation_prevention: bool

    def __post_init__(self) -> None:
        _require_identity(self.action_id, "action_id")
        _require_identity(self.operation, "operation")
        _require_identity(self.target, "target")
        if not isinstance(self.requires_mutation_prevention, bool):
            raise TypeError("requires_mutation_prevention must be Boolean")


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reasons: tuple[str, ...]
    timing: str
    mutation_primitive_executed: bool = False


@dataclass(frozen=True)
class EvidenceRef:
    role: str
    artifact_id: str
    path: str
    sha256: str

    def __post_init__(self) -> None:
        _require_identity(self.role, "role")
        _require_identity(self.artifact_id, "artifact_id")
        _require_identity(self.path, "path")
        _require_sha256(self.sha256, "sha256")


@dataclass(frozen=True)
class RawResult:
    producer_claim: str
    reported_value: Any
    evidence: tuple[EvidenceRef, ...]
    executor_calls: int
    mutation_primitive_calls: int

    def __post_init__(self) -> None:
        if self.executor_calls < 0 or self.mutation_primitive_calls < 0:
            raise ValueError("execution counts cannot be negative")


@dataclass(frozen=True)
class VerificationResult:
    semantic_valid: bool
    semantic_reasons: tuple[str, ...]
    evidence_status: str
    evidence_reasons: tuple[str, ...]
    observed_post_state_sha256: str

    def __post_init__(self) -> None:
        if self.evidence_status not in EVIDENCE_STATUSES:
            raise ValueError("evidence_status is outside the provisional vocabulary")
        _require_sha256(self.observed_post_state_sha256, "observed_post_state_sha256")


@dataclass(frozen=True)
class AdjudicationResult:
    """Canonical terminal semantics for the currently supported verifier result."""

    actual_outcome: str
    acceptance_decision: str
    verified_success_eligibility: bool
    joint_interpretation: str


def adjudicate(
    verification: VerificationResult,
    *,
    terminal_execution_status: str,
) -> AdjudicationResult:
    """Derive bounded terminal semantics from authoritative execution inputs."""

    if terminal_execution_status not in TERMINAL_EXECUTION_STATUSES:
        raise ValueError("terminal_execution_status is outside the provisional vocabulary")
    actual_outcome = "success" if verification.semantic_valid else "failure"
    accepted = (
        verification.semantic_valid
        and verification.evidence_status == "sufficient"
        and terminal_execution_status == "completed"
    )
    if accepted:
        joint_interpretation = "verified_success"
    elif verification.semantic_valid:
        joint_interpretation = "unverified_success"
    else:
        joint_interpretation = "correctly_recognized_failure"
    return AdjudicationResult(
        actual_outcome=actual_outcome,
        acceptance_decision="accept" if accepted else "reject",
        verified_success_eligibility=accepted,
        joint_interpretation=joint_interpretation,
    )


@dataclass(frozen=True)
class Observation:
    sequence: int
    stage: str
    fields: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("observation sequence must start at one")
        _require_identity(self.stage, "stage")


@dataclass(frozen=True)
class ResourceLedger:
    artifact_reads: int
    executor_calls: int
    model_calls: int = 0
    network_calls: int = 0
    paid_api_calls: int = 0
    tool_calls: int = 0
    retry_count: int = 0
    route_count: int = 0
    escalation_count: int = 0
    recovery_count: int = 0
    wall_time_ns: int | str = UNKNOWN
    provider_cost_usd: float | str = UNKNOWN

    def __post_init__(self) -> None:
        counted = (
            self.artifact_reads,
            self.executor_calls,
            self.model_calls,
            self.network_calls,
            self.paid_api_calls,
            self.tool_calls,
            self.retry_count,
            self.route_count,
            self.escalation_count,
            self.recovery_count,
        )
        if any(not isinstance(value, int) or value < 0 for value in counted):
            raise ValueError("resource counts must be non-negative integers")


@dataclass(frozen=True)
class TerminalRecord:
    requested_identity: ExecutionIdentity
    contract: TaskContract
    program: ProgramArtifact | None
    actual_outcome: str
    producer_claim: str | None
    empirical_evidence_status: str
    acceptance_decision: str
    verified_success_eligibility: bool
    joint_interpretation: str
    terminal_execution_status: str
    policy_decision: PolicyDecision
    state_before_sha256: str
    state_after_sha256: str
    changed_paths: tuple[str, ...]
    verification: VerificationResult
    evidence: tuple[EvidenceRef, ...]
    observations: tuple[Observation, ...]
    resource_ledger: ResourceLedger
    recovery_attempted: bool = False
    recovery_action_id: str | None = None
    recovery_target_failure_state: str | None = None
    recovery_result: str = "not_applicable"
    silent_retry: bool = False

    def __post_init__(self) -> None:
        if self.actual_outcome not in ACTUAL_OUTCOMES:
            raise ValueError("actual_outcome is outside the provisional vocabulary")
        if self.empirical_evidence_status not in EVIDENCE_STATUSES:
            raise ValueError("empirical_evidence_status is outside the provisional vocabulary")
        if self.acceptance_decision not in ACCEPTANCE_DECISIONS:
            raise ValueError("acceptance_decision is outside the provisional vocabulary")
        if self.terminal_execution_status not in TERMINAL_EXECUTION_STATUSES:
            raise ValueError("terminal_execution_status is outside the provisional vocabulary")
        _require_sha256(self.state_before_sha256, "state_before_sha256")
        _require_sha256(self.state_after_sha256, "state_after_sha256")
        if self.empirical_evidence_status != self.verification.evidence_status:
            raise ValueError("terminal evidence status must come from independent verification")
        canonical = adjudicate(
            self.verification,
            terminal_execution_status=self.terminal_execution_status,
        )
        if self.actual_outcome != canonical.actual_outcome:
            raise ValueError("terminal actual outcome is inconsistent with canonical adjudication")
        if self.acceptance_decision != canonical.acceptance_decision:
            raise ValueError("terminal acceptance is inconsistent with canonical adjudication")
        if self.verified_success_eligibility != canonical.verified_success_eligibility:
            raise ValueError("verified-success eligibility is inconsistent with canonical adjudication")
        if self.joint_interpretation != canonical.joint_interpretation:
            raise ValueError("joint interpretation is inconsistent with canonical adjudication")
        if self.recovery_attempted or self.recovery_action_id is not None:
            raise ValueError("recovery is not implemented in this provisional core")
        if self.silent_retry or self.resource_ledger.retry_count:
            raise ValueError("implicit or explicit retry is not implemented")

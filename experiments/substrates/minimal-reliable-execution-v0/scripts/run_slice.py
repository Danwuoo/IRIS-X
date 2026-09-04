#!/usr/bin/env python3
"""Run one local deterministic IRIS-X execution-boundary vertical slice."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, MutableMapping, Protocol, Sequence


SUBSTRATE = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = SUBSTRATE / "inputs" / "task-contract.json"
ACTUAL_OUTCOMES = {"success", "partial", "failure", "unresolved"}
EVIDENCE_STATUSES = {
    "sufficient",
    "insufficient",
    "invalid_binding",
    "not_assessed",
    "unresolved",
}
ACCEPTANCE_DECISIONS = {"accept", "reject", "abstain", "not_applicable"}
TERMINAL_EXECUTION_STATUSES = {"completed", "failed", "rejected", "invalid"}


class ContractError(ValueError):
    """The frozen task contract is invalid."""


class BindingError(ValueError):
    """Artifact or execution identity could not be bound."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ContractError("task contract must be a JSON object")
    return value, payload


def normalized_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{label} must be a non-empty relative path")
    if value.startswith(("\\\\", "//")) or PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute():
        raise ContractError(f"{label} may not be absolute or a network path")
    normalized = value.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if not candidate.parts or any(part in {".", ".."} or ":" in part for part in candidate.parts):
        raise ContractError(f"{label} may not traverse or contain a drive/stream designator")
    return candidate.as_posix()


def validate_contract(contract: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "task_id",
        "contract_id",
        "program",
        "execution",
        "request",
        "initial_state",
        "success_condition",
        "policy",
        "evidence_requirements",
    }
    if contract.get("schema_version") != 1 or required - set(contract):
        raise ContractError("task contract schema or required fields are invalid")
    for field in ("task_id", "contract_id"):
        if not isinstance(contract.get(field), str) or not contract[field]:
            raise ContractError(f"{field} must be a non-empty string")
    program = contract["program"]
    if not isinstance(program, dict) or set(program) != {"program_id", "path", "sha256"}:
        raise ContractError("program identity is invalid")
    if not isinstance(program["program_id"], str) or len(program["sha256"]) != 64:
        raise ContractError("program ID or SHA-256 is invalid")
    normalized_relative_path(program["path"], "program.path")
    execution = contract["execution"]
    if not isinstance(execution, dict) or set(execution) != {"execution_id", "configuration_id"}:
        raise ContractError("execution identity is invalid")
    request = contract["request"]
    if not isinstance(request, dict) or set(request) != {"action_id", "operation", "target", "value"}:
        raise ContractError("execution request is invalid")
    if request["operation"] != "set":
        raise ContractError("the minimal slice supports only one set operation")
    normalized_relative_path(request["target"], "request.target")
    if not isinstance(contract["initial_state"], dict):
        raise ContractError("initial_state must be an object")
    condition = contract["success_condition"]
    if not isinstance(condition, dict) or set(condition) != {"path", "equals"}:
        raise ContractError("success_condition is invalid")
    normalized_relative_path(condition["path"], "success_condition.path")
    policy = contract["policy"]
    if not isinstance(policy, dict) or set(policy) != {"protected_prefixes", "allowed_write_prefixes"}:
        raise ContractError("policy is invalid")
    for name in ("protected_prefixes", "allowed_write_prefixes"):
        values = policy[name]
        if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
            raise ContractError(f"policy.{name} must be a non-empty string list")
    requirements = contract["evidence_requirements"]
    if not isinstance(requirements, list) or {row.get("role") for row in requirements if isinstance(row, dict)} != {
        "task_contract",
        "program",
    }:
        raise ContractError("evidence requirements must contain task_contract and program roles")
    if len(requirements) != 2 or any(
        not isinstance(row, dict) or set(row) != {"role", "artifact_id", "path"} for row in requirements
    ):
        raise ContractError("evidence requirements are invalid")
    for row in requirements:
        normalized_relative_path(row["path"], f"evidence.{row['role']}.path")
    by_role = {row["role"]: row for row in requirements}
    if by_role["task_contract"]["artifact_id"] != contract["contract_id"]:
        raise ContractError("task contract evidence identity is crossed")
    if by_role["program"]["artifact_id"] != program["program_id"]:
        raise ContractError("program evidence identity is crossed")


@dataclass(frozen=True)
class ExecutionIdentity:
    task_id: str
    contract_id: str
    program_id: str
    execution_id: str
    configuration_id: str


@dataclass(frozen=True)
class ProgramArtifact:
    program_id: str
    path: str
    content_sha256: str
    content_bytes: int


@dataclass(frozen=True)
class ExecutionContext:
    task_id: str
    contract_id: str
    contract_sha256: str
    program: ProgramArtifact
    execution_id: str
    configuration_id: str


@dataclass(frozen=True)
class EvidenceRef:
    role: str
    artifact_id: str
    path: str
    sha256: str


@dataclass(frozen=True)
class ExecutionRequest:
    action_id: str
    operation: str
    target: str
    value: Any


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reasons: tuple[str, ...]
    timing: str
    mutation_primitive_executed: bool


@dataclass(frozen=True)
class RawResult:
    producer_claim: str
    reported_value: Any
    evidence: tuple[EvidenceRef, ...]
    mutation_primitive_calls: int


@dataclass(frozen=True)
class VerificationResult:
    semantic_valid: bool
    semantic_reasons: tuple[str, ...]
    evidence_status: str
    evidence_reasons: tuple[str, ...]
    observed_post_state_sha256: str


@dataclass(frozen=True)
class BoundExecution:
    contract: dict[str, Any]
    context: ExecutionContext
    contract_path: Path
    program_path: Path


class ExecutorAdapter(Protocol):
    def execute(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        state: MutableMapping[str, Any],
        expected_evidence: Sequence[EvidenceRef],
    ) -> RawResult: ...


class LocalSetAdapter:
    """Replaceable local test double with no I/O, retry, route, or recovery."""

    def __init__(
        self,
        *,
        state_value: Any | None = None,
        reported_value: Any | None = None,
        producer_claim: str = "success",
        evidence_hash_overrides: dict[str, str] | None = None,
    ) -> None:
        self.state_value = state_value
        self.reported_value = reported_value
        self.producer_claim = producer_claim
        self.evidence_hash_overrides = evidence_hash_overrides or {}
        self.primitive_calls = 0

    def execute(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        state: MutableMapping[str, Any],
        expected_evidence: Sequence[EvidenceRef],
    ) -> RawResult:
        del context
        if request.operation != "set":
            raise ValueError("local adapter supports only set")
        self.primitive_calls += 1
        applied = request.value if self.state_value is None else self.state_value
        state[request.target] = applied
        reported = applied if self.reported_value is None else self.reported_value
        evidence = tuple(
            replace(item, sha256=self.evidence_hash_overrides.get(item.role, item.sha256))
            for item in expected_evidence
        )
        return RawResult(
            producer_claim=self.producer_claim,
            reported_value=reported,
            evidence=evidence,
            mutation_primitive_calls=1,
        )


def declared_identity(contract: dict[str, Any]) -> ExecutionIdentity:
    return ExecutionIdentity(
        task_id=contract["task_id"],
        contract_id=contract["contract_id"],
        program_id=contract["program"]["program_id"],
        execution_id=contract["execution"]["execution_id"],
        configuration_id=contract["execution"]["configuration_id"],
    )


def bind_execution(
    contract: dict[str, Any],
    contract_bytes: bytes,
    contract_path: Path,
    program_path: Path,
    identity: ExecutionIdentity,
) -> BoundExecution:
    expected = declared_identity(contract)
    for field in asdict(expected):
        if getattr(identity, field) != getattr(expected, field):
            raise BindingError(f"identity_mismatch:{field}")
    if not program_path.is_file():
        raise BindingError("program_artifact_missing")
    program_bytes = program_path.read_bytes()
    observed_program_sha = sha256_bytes(program_bytes)
    if observed_program_sha != contract["program"]["sha256"]:
        raise BindingError("program_hash_mismatch")
    context = ExecutionContext(
        task_id=identity.task_id,
        contract_id=identity.contract_id,
        contract_sha256=sha256_bytes(contract_bytes),
        program=ProgramArtifact(
            program_id=identity.program_id,
            path=contract["program"]["path"],
            content_sha256=observed_program_sha,
            content_bytes=len(program_bytes),
        ),
        execution_id=identity.execution_id,
        configuration_id=identity.configuration_id,
    )
    return BoundExecution(contract, context, contract_path.resolve(), program_path.resolve())


def expected_evidence(bound: BoundExecution) -> tuple[EvidenceRef, ...]:
    hashes = {
        "task_contract": bound.context.contract_sha256,
        "program": bound.context.program.content_sha256,
    }
    return tuple(
        EvidenceRef(row["role"], row["artifact_id"], row["path"], hashes[row["role"]])
        for row in bound.contract["evidence_requirements"]
    )


def path_has_prefix(path: str, prefixes: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix.replace("\\", "/")) for prefix in prefixes)


def evaluate_policy(contract: dict[str, Any], request: ExecutionRequest) -> PolicyDecision:
    try:
        target = normalized_relative_path(request.target, "request.target")
    except ContractError:
        return PolicyDecision("deny", ("invalid_target",), "before_mutation_primitive", False)
    policy = contract["policy"]
    if path_has_prefix(target, policy["protected_prefixes"]):
        return PolicyDecision("deny", ("protected_path_mutation",), "before_mutation_primitive", False)
    if not path_has_prefix(target, policy["allowed_write_prefixes"]):
        return PolicyDecision("deny", ("default_write_prohibition",), "before_mutation_primitive", False)
    return PolicyDecision("permit", ("allowed_write_prefix",), "before_mutation_primitive", False)


def evidence_binding(
    required: Sequence[EvidenceRef], supplied: Sequence[EvidenceRef]
) -> tuple[str, tuple[str, ...]]:
    required_by_role = {item.role: item for item in required}
    supplied_by_role: dict[str, list[EvidenceRef]] = {}
    reasons: list[str] = []
    for item in supplied:
        supplied_by_role.setdefault(item.role, []).append(item)
        expected = required_by_role.get(item.role)
        if expected is None:
            reasons.append("unexpected_evidence_role")
        elif item != expected:
            reasons.append(f"{item.role}_binding_mismatch")
    for role in required_by_role:
        matches = supplied_by_role.get(role, [])
        if not matches:
            reasons.append(f"missing_{role}_evidence")
        elif len(matches) > 1:
            reasons.append(f"duplicate_{role}_evidence")
    unique = tuple(sorted(set(reasons)))
    if not unique:
        return "sufficient", ("complete_correct_binding",)
    if all(reason.startswith("missing_") for reason in unique):
        return "insufficient", unique
    return "invalid_binding", unique


def independent_verify(
    bound: BoundExecution,
    request: ExecutionRequest,
    raw: RawResult,
    after_state: dict[str, Any],
) -> VerificationResult:
    condition = bound.contract["success_condition"]
    semantic_reasons: list[str] = []
    if after_state.get(condition["path"]) != condition["equals"]:
        semantic_reasons.append("post_state_condition_mismatch")
    if raw.reported_value != after_state.get(request.target):
        semantic_reasons.append("reported_value_state_mismatch")
    status, evidence_reasons = evidence_binding(expected_evidence(bound), raw.evidence)
    return VerificationResult(
        semantic_valid=not semantic_reasons,
        semantic_reasons=tuple(semantic_reasons or ["independent_post_state_match"]),
        evidence_status=status,
        evidence_reasons=evidence_reasons,
        observed_post_state_sha256=sha256_bytes(canonical_json_bytes(after_state)),
    )


def changed_paths(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def resource_ledger(*, artifact_reads: int, executor_calls: int) -> dict[str, Any]:
    return {
        "artifact_reads": artifact_reads,
        "executor_calls": executor_calls,
        "model_calls": 0,
        "network_calls": 0,
        "paid_api_calls": 0,
        "tool_calls": 0,
        "retry_count": 0,
        "route_count": 0,
        "escalation_count": 0,
        "recovery_count": 0,
        "wall_time_ns": "Unknown",
        "provider_cost_usd": "Unknown",
    }


def joint_interpretation(actual: str, evidence: str, acceptance: str, eligible: bool) -> str:
    if actual == "success" and evidence == "sufficient" and acceptance == "accept" and eligible:
        return "verified_success"
    if actual == "success" and evidence != "sufficient":
        return "unverified_success"
    if actual in {"partial", "failure"} and acceptance == "accept":
        return "false_success"
    if actual == "failure" and acceptance == "reject":
        return "correctly_recognized_failure"
    return "unresolved"


def validate_terminal_record(record: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "task_identity",
        "program_identity",
        "execution_identity",
        "actual_outcome",
        "producer_claim",
        "empirical_evidence_status",
        "acceptance_decision",
        "verified_success_eligibility",
        "joint_interpretation",
        "terminal_execution_status",
        "policy_decision",
        "side_effects",
        "verification",
        "evidence",
        "recovery",
        "observations",
        "resource_ledger",
    }
    if required - set(record) or "status" in record:
        raise ValueError("terminal record fields are incomplete or collapsed")
    if record["actual_outcome"] not in ACTUAL_OUTCOMES:
        raise ValueError("actual_outcome is outside the canonical vocabulary")
    if record["empirical_evidence_status"] not in EVIDENCE_STATUSES:
        raise ValueError("empirical_evidence_status is outside the canonical vocabulary")
    if record["acceptance_decision"] not in ACCEPTANCE_DECISIONS:
        raise ValueError("acceptance_decision is outside the canonical vocabulary")
    if record["terminal_execution_status"] not in TERMINAL_EXECUTION_STATUSES:
        raise ValueError("terminal_execution_status is outside the slice vocabulary")


def execute_slice(
    contract_path: Path = DEFAULT_CONTRACT,
    *,
    program_path: Path | None = None,
    identity: ExecutionIdentity | None = None,
    adapter: ExecutorAdapter | None = None,
    collect_observations: bool = True,
) -> dict[str, Any]:
    contract_path = Path(contract_path)
    contract, contract_bytes = load_json_bytes(contract_path)
    validate_contract(contract)
    state = copy.deepcopy(contract["initial_state"])
    before_state = copy.deepcopy(state)
    observations: list[dict[str, Any]] = []

    def observe(stage: str, **fields: Any) -> None:
        if collect_observations:
            observations.append({"sequence": len(observations) + 1, "stage": stage, **fields})

    observe("contract_loaded", task_id=contract["task_id"], contract_id=contract["contract_id"])
    declared = declared_identity(contract)
    supplied_identity = identity or declared
    resolved_program = Path(program_path) if program_path is not None else SUBSTRATE / contract["program"]["path"]
    try:
        bound = bind_execution(contract, contract_bytes, contract_path, resolved_program, supplied_identity)
    except BindingError as exc:
        observe("binding_rejected", reason=str(exc))
        record = {
            "schema_version": 1,
            "task_identity": {"task_id": supplied_identity.task_id, "contract_id": supplied_identity.contract_id},
            "program_identity": {
                "program_id": supplied_identity.program_id,
                "expected_sha256": contract["program"]["sha256"],
                "observed_sha256": sha256_file(resolved_program) if resolved_program.is_file() else None,
            },
            "execution_identity": {
                "execution_id": supplied_identity.execution_id,
                "configuration_id": supplied_identity.configuration_id,
            },
            "actual_outcome": "failure",
            "producer_claim": None,
            "empirical_evidence_status": "invalid_binding",
            "acceptance_decision": "reject",
            "verified_success_eligibility": False,
            "joint_interpretation": "correctly_recognized_failure",
            "terminal_execution_status": "rejected",
            "policy_decision": {
                "decision": "not_evaluated",
                "reasons": ["binding_failed_before_policy"],
                "timing": "not_applicable",
                "mutation_primitive_executed": False,
            },
            "side_effects": {
                "state_before_sha256": sha256_bytes(canonical_json_bytes(before_state)),
                "state_after_sha256": sha256_bytes(canonical_json_bytes(state)),
                "changed_paths": [],
                "mutation_primitive_executed": False,
            },
            "verification": {"semantic_valid": False, "reasons": [str(exc)]},
            "evidence": [],
            "recovery": {
                "attempted": False,
                "action_id": None,
                "target_failure_state": None,
                "result": "not_applicable",
                "silent_retry": False,
            },
            "observations": observations,
            "resource_ledger": resource_ledger(
                artifact_reads=2 if resolved_program.is_file() else 1,
                executor_calls=0,
            ),
        }
        validate_terminal_record(record)
        return record

    observe("execution_identity_bound", program_sha256=bound.context.program.content_sha256)
    request = ExecutionRequest(**contract["request"])
    policy = evaluate_policy(contract, request)
    observe("policy_evaluated", decision=policy.decision, timing=policy.timing)
    if policy.decision != "permit":
        observe("execution_skipped", reason=policy.reasons[0])
        record = {
            "schema_version": 1,
            "task_identity": {"task_id": bound.context.task_id, "contract_id": bound.context.contract_id},
            "program_identity": asdict(bound.context.program),
            "execution_identity": {
                "execution_id": bound.context.execution_id,
                "configuration_id": bound.context.configuration_id,
            },
            "actual_outcome": "failure",
            "producer_claim": None,
            "empirical_evidence_status": "sufficient",
            "acceptance_decision": "reject",
            "verified_success_eligibility": False,
            "joint_interpretation": "correctly_recognized_failure",
            "terminal_execution_status": "rejected",
            "policy_decision": asdict(policy),
            "side_effects": {
                "state_before_sha256": sha256_bytes(canonical_json_bytes(before_state)),
                "state_after_sha256": sha256_bytes(canonical_json_bytes(state)),
                "changed_paths": [],
                "mutation_primitive_executed": False,
            },
            "verification": {
                "semantic_valid": False,
                "semantic_reasons": ["execution_prohibited_before_mutation"],
                "evidence_status": "not_assessed",
                "evidence_reasons": ["no_execution_evidence_produced"],
                "observed_post_state_sha256": sha256_bytes(canonical_json_bytes(state)),
            },
            "evidence": [],
            "recovery": {
                "attempted": False,
                "action_id": None,
                "target_failure_state": None,
                "result": "not_applicable",
                "silent_retry": False,
            },
            "observations": observations,
            "resource_ledger": resource_ledger(artifact_reads=2, executor_calls=0),
        }
        validate_terminal_record(record)
        return record

    executor = adapter or LocalSetAdapter()
    try:
        raw = executor.execute(bound.context, request, state, expected_evidence(bound))
        executed_policy = replace(policy, mutation_primitive_executed=raw.mutation_primitive_calls > 0)
        observe("executor_completed", mutation_primitive_calls=raw.mutation_primitive_calls)
        verification = independent_verify(bound, request, raw, state)
        observe(
            "independent_verification_completed",
            semantic_valid=verification.semantic_valid,
            evidence_status=verification.evidence_status,
        )
        actual = "success" if verification.semantic_valid else "failure"
        accepted = verification.semantic_valid and verification.evidence_status == "sufficient"
        acceptance = "accept" if accepted else "reject"
        eligible = actual == "success" and accepted
        observe("adjudication_completed", actual_outcome=actual, acceptance_decision=acceptance)
        terminal_status = "completed"
        verification_record = asdict(verification)
        evidence_record = [asdict(item) for item in raw.evidence]
        producer_claim = raw.producer_claim
        executor_calls = raw.mutation_primitive_calls
    except Exception as exc:
        executed_policy = policy
        actual = "failure"
        acceptance = "reject"
        eligible = False
        terminal_status = "failed"
        verification_record = {
            "semantic_valid": False,
            "semantic_reasons": [f"executor_failure:{type(exc).__name__}"],
            "evidence_status": "not_assessed",
            "evidence_reasons": ["no_result_to_verify"],
            "observed_post_state_sha256": sha256_bytes(canonical_json_bytes(state)),
        }
        evidence_record = []
        producer_claim = None
        executor_calls = 0
        observe("executor_failed", error_type=type(exc).__name__)

    record = {
        "schema_version": 1,
        "task_identity": {"task_id": bound.context.task_id, "contract_id": bound.context.contract_id},
        "program_identity": asdict(bound.context.program),
        "execution_identity": {
            "execution_id": bound.context.execution_id,
            "configuration_id": bound.context.configuration_id,
        },
        "actual_outcome": actual,
        "producer_claim": producer_claim,
        "empirical_evidence_status": verification_record["evidence_status"],
        "acceptance_decision": acceptance,
        "verified_success_eligibility": eligible,
        "joint_interpretation": joint_interpretation(
            actual,
            verification_record["evidence_status"],
            acceptance,
            eligible,
        ),
        "terminal_execution_status": terminal_status,
        "policy_decision": asdict(executed_policy),
        "side_effects": {
            "state_before_sha256": sha256_bytes(canonical_json_bytes(before_state)),
            "state_after_sha256": sha256_bytes(canonical_json_bytes(state)),
            "changed_paths": changed_paths(before_state, state),
            "mutation_primitive_executed": executed_policy.mutation_primitive_executed,
        },
        "verification": verification_record,
        "evidence": evidence_record,
        "recovery": {
            "attempted": False,
            "action_id": None,
            "target_failure_state": None,
            "result": "not_applicable",
            "silent_retry": False,
        },
        "observations": observations,
        "resource_ledger": resource_ledger(artifact_reads=2, executor_calls=executor_calls),
    }
    validate_terminal_record(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    record = execute_slice(args.contract)
    print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if record["verified_success_eligibility"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""One explicit, deterministic execution ordering for the provisional core."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, replace
from typing import Any, Mapping, MutableMapping, Sequence

from .interfaces import ExecutorAdapter, IndependentVerifier, PolicyGate
from .records import (
    EvidenceRef,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRequest,
    Observation,
    PolicyDecision,
    ProgramArtifact,
    ResourceLedger,
    TaskContract,
    TerminalRecord,
    VerificationResult,
    sha256_bytes,
)


class BindingError(ValueError):
    """Declared execution or artifact identity failed closed."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def state_sha256(state: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(state))


def declared_identity(contract: TaskContract) -> ExecutionIdentity:
    return ExecutionIdentity(
        task_id=contract.task_id,
        contract_id=contract.contract_id,
        program_id=contract.expected_program_id,
        execution_id=contract.execution_id,
        configuration_id=contract.configuration_id,
    )


def bind_execution(
    contract: TaskContract,
    program: ProgramArtifact | None,
    supplied_identity: ExecutionIdentity,
) -> ExecutionContext:
    expected = declared_identity(contract)
    for field_name in expected.__dataclass_fields__:
        if getattr(supplied_identity, field_name) != getattr(expected, field_name):
            raise BindingError(f"identity_mismatch:{field_name}")
    if program is None:
        raise BindingError("program_artifact_missing")
    if program.program_id != contract.expected_program_id:
        raise BindingError("program_identity_mismatch")
    if program.content_sha256 != contract.expected_program_sha256:
        raise BindingError("program_hash_mismatch")
    return ExecutionContext(contract=contract, program=program, identity=supplied_identity)


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


def changed_paths(before: Mapping[str, Any], after: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path)))


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


def _resource_ledger(*, artifact_reads: int, executor_calls: int) -> ResourceLedger:
    return ResourceLedger(artifact_reads=artifact_reads, executor_calls=executor_calls)


def execute(
    *,
    contract: TaskContract,
    program: ProgramArtifact | None,
    supplied_identity: ExecutionIdentity,
    request: ExecutionRequest,
    state: MutableMapping[str, Any],
    expected_evidence: Sequence[EvidenceRef],
    executor: ExecutorAdapter,
    verifier: IndependentVerifier,
    policy_gate: PolicyGate | None = None,
    collect_observations: bool = True,
) -> TerminalRecord:
    """Bind, conditionally gate, execute once, independently verify, adjudicate."""

    before_state = copy.deepcopy(dict(state))
    before_sha = state_sha256(before_state)
    observations: list[Observation] = []

    def observe(stage: str, **fields: Any) -> None:
        if collect_observations:
            observations.append(Observation(len(observations) + 1, stage, fields))

    observe("contract_loaded", task_id=contract.task_id, contract_id=contract.contract_id)
    artifact_reads = 1 + int(program is not None)
    try:
        context = bind_execution(contract, program, supplied_identity)
    except BindingError as exc:
        reason = str(exc)
        observe("binding_rejected", reason=reason)
        verification = VerificationResult(
            False, (reason,), "invalid_binding", (reason,), state_sha256(state)
        )
        return TerminalRecord(
            supplied_identity, contract, program, "failure", None,
            verification.evidence_status, "reject", False,
            "correctly_recognized_failure", "rejected",
            PolicyDecision("not_evaluated", ("binding_failed_before_policy",), "not_applicable"),
            before_sha, state_sha256(state), changed_paths(before_state, state),
            verification, (), tuple(observations),
            _resource_ledger(artifact_reads=artifact_reads, executor_calls=0),
        )

    observe("execution_identity_bound", program_sha256=context.program.content_sha256)
    if request.requires_mutation_prevention:
        if policy_gate is None:
            policy = PolicyDecision("deny", ("mutation_policy_gate_missing",), "before_mutation_primitive")
        else:
            try:
                policy = policy_gate.evaluate(context, request)
            except Exception as exc:
                policy = PolicyDecision(
                    "deny", (f"policy_error:{type(exc).__name__}",), "before_mutation_primitive"
                )
        observe("policy_evaluated", decision=policy.decision, timing=policy.timing)
        if policy.decision != "permit":
            observe("execution_skipped", reason=policy.reasons[0])
            verification = VerificationResult(
                False,
                ("execution_prohibited_before_mutation",),
                "not_assessed",
                ("no_execution_evidence_produced",),
                state_sha256(state),
            )
            return TerminalRecord(
                supplied_identity, contract, program, "failure", None,
                verification.evidence_status, "reject", False,
                "correctly_recognized_failure", "rejected", policy,
                before_sha, state_sha256(state), changed_paths(before_state, state),
                verification, (), tuple(observations),
                _resource_ledger(artifact_reads=artifact_reads, executor_calls=0),
            )
    else:
        policy = PolicyDecision("not_required", ("read_only_request",), "not_applicable")
        observe("policy_not_required", decision=policy.decision, timing=policy.timing)

    try:
        raw_result = executor.execute(context, request, state, expected_evidence)
        if raw_result.executor_calls != 1:
            raise ValueError("executor adapter must report exactly one call")
        if raw_result.mutation_primitive_calls not in {0, 1}:
            raise ValueError("adapter may report at most one mutation primitive")
        if not request.requires_mutation_prevention and raw_result.mutation_primitive_calls != 0:
            raise ValueError("read-only request reported a mutation primitive")
    except Exception as exc:
        observe("executor_failed", error_type=type(exc).__name__)
        after_sha = state_sha256(state)
        changed = changed_paths(before_state, state)
        executed_policy = replace(policy, mutation_primitive_executed=bool(changed))
        verification = VerificationResult(
            False,
            (f"executor_failure:{type(exc).__name__}",),
            "not_assessed",
            ("no_result_to_verify",),
            after_sha,
        )
        return TerminalRecord(
            supplied_identity, contract, program, "failure", None,
            verification.evidence_status, "reject", False,
            "correctly_recognized_failure", "failed", executed_policy,
            before_sha, after_sha, changed, verification, (), tuple(observations),
            _resource_ledger(artifact_reads=artifact_reads, executor_calls=1),
        )

    executed_policy = replace(policy, mutation_primitive_executed=raw_result.mutation_primitive_calls > 0)
    observe(
        "executor_completed",
        executor_calls=raw_result.executor_calls,
        mutation_primitive_calls=raw_result.mutation_primitive_calls,
    )
    try:
        verification = verifier.verify(
            context, request, raw_result, before_state, dict(state), expected_evidence
        )
    except Exception as exc:
        verification = VerificationResult(
            False,
            (f"verifier_failure:{type(exc).__name__}",),
            "not_assessed",
            ("verification_did_not_complete",),
            state_sha256(state),
        )
        terminal_status = "failed"
        observe("independent_verification_failed", error_type=type(exc).__name__)
    else:
        terminal_status = "completed"
        observe(
            "independent_verification_completed",
            semantic_valid=verification.semantic_valid,
            evidence_status=verification.evidence_status,
        )

    actual = "success" if verification.semantic_valid else "failure"
    acceptance = (
        "accept"
        if verification.semantic_valid and verification.evidence_status == "sufficient"
        else "reject"
    )
    eligible = actual == "success" and acceptance == "accept"
    observe("adjudication_completed", actual_outcome=actual, acceptance_decision=acceptance)
    return TerminalRecord(
        supplied_identity, contract, program, actual, raw_result.producer_claim,
        verification.evidence_status, acceptance, eligible,
        joint_interpretation(actual, verification.evidence_status, acceptance, eligible),
        terminal_status, executed_policy, before_sha, state_sha256(state),
        changed_paths(before_state, state), verification, raw_result.evidence,
        tuple(observations),
        _resource_ledger(artifact_reads=artifact_reads, executor_calls=raw_result.executor_calls),
    )


def terminal_record_to_dict(record: TerminalRecord) -> dict[str, Any]:
    if record.program is None:
        program_identity: dict[str, Any] = {
            "program_id": record.requested_identity.program_id,
            "expected_sha256": record.contract.expected_program_sha256,
            "observed_sha256": None,
        }
    else:
        program_identity = {
            "program_id": record.program.program_id,
            "path": record.program.path,
            "content_sha256": record.program.content_sha256,
            "content_bytes": record.program.content_bytes,
        }
    verification = asdict(record.verification)
    if record.terminal_execution_status == "rejected" and record.policy_decision.decision == "not_evaluated":
        verification = {"semantic_valid": False, "reasons": list(record.verification.semantic_reasons)}
    return {
        "schema_version": 1,
        "task_identity": {
            "task_id": record.requested_identity.task_id,
            "contract_id": record.requested_identity.contract_id,
        },
        "program_identity": program_identity,
        "execution_identity": {
            "execution_id": record.requested_identity.execution_id,
            "configuration_id": record.requested_identity.configuration_id,
        },
        "actual_outcome": record.actual_outcome,
        "producer_claim": record.producer_claim,
        "empirical_evidence_status": record.empirical_evidence_status,
        "acceptance_decision": record.acceptance_decision,
        "verified_success_eligibility": record.verified_success_eligibility,
        "joint_interpretation": record.joint_interpretation,
        "terminal_execution_status": record.terminal_execution_status,
        "policy_decision": asdict(record.policy_decision),
        "side_effects": {
            "state_before_sha256": record.state_before_sha256,
            "state_after_sha256": record.state_after_sha256,
            "changed_paths": list(record.changed_paths),
            "mutation_primitive_executed": record.policy_decision.mutation_primitive_executed,
        },
        "verification": verification,
        "evidence": [asdict(item) for item in record.evidence],
        "recovery": {
            "attempted": record.recovery_attempted,
            "action_id": record.recovery_action_id,
            "target_failure_state": record.recovery_target_failure_state,
            "result": record.recovery_result,
            "silent_retry": record.silent_retry,
        },
        "observations": [
            {"sequence": item.sequence, "stage": item.stage, **dict(item.fields)}
            for item in record.observations
        ],
        "resource_ledger": asdict(record.resource_ledger),
    }

#!/usr/bin/env python3
"""Run the preserved deterministic mutation slice through ``irisx.core``."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping, MutableMapping, Sequence


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from irisx.core.execution import (  # noqa: E402
    evidence_binding,
    execute,
    state_sha256,
    terminal_record_to_dict,
)
from irisx.core.records import (  # noqa: E402
    ACCEPTANCE_DECISIONS,
    ACTUAL_OUTCOMES,
    EVIDENCE_STATUSES,
    TERMINAL_EXECUTION_STATUSES,
    EvidenceRef,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRequest,
    PolicyDecision,
    ProgramArtifact,
    RawResult,
    TaskContract,
    VerificationResult,
    sha256_bytes,
)


DEFAULT_CONTRACT = SUBSTRATE / "inputs" / "task-contract.json"


class ContractError(ValueError):
    """The frozen mutation-slice task contract is invalid."""


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


def declared_identity(contract: dict[str, Any]) -> ExecutionIdentity:
    return ExecutionIdentity(
        task_id=contract["task_id"],
        contract_id=contract["contract_id"],
        program_id=contract["program"]["program_id"],
        execution_id=contract["execution"]["execution_id"],
        configuration_id=contract["execution"]["configuration_id"],
    )


def path_has_prefix(path: str, prefixes: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix.replace("\\", "/")) for prefix in prefixes)


class PrefixPolicyGate:
    """Fixture-local prefix policy for the one preserved mutation operation."""

    def __init__(self, policy: Mapping[str, Sequence[str]]) -> None:
        self.policy = policy

    def evaluate(self, context: ExecutionContext, request: ExecutionRequest) -> PolicyDecision:
        del context
        try:
            target = normalized_relative_path(request.target, "request.target")
        except ContractError:
            return PolicyDecision("deny", ("invalid_target",), "before_mutation_primitive")
        if path_has_prefix(target, self.policy["protected_prefixes"]):
            return PolicyDecision("deny", ("protected_path_mutation",), "before_mutation_primitive")
        if not path_has_prefix(target, self.policy["allowed_write_prefixes"]):
            return PolicyDecision("deny", ("default_write_prohibition",), "before_mutation_primitive")
        return PolicyDecision("permit", ("allowed_write_prefix",), "before_mutation_primitive")


class LocalSetAdapter:
    """Fixture-local in-memory set adapter with no I/O or hidden retry."""

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
            executor_calls=1,
            mutation_primitive_calls=1,
        )


class SetResultVerifier:
    """Fixture-local semantic oracle plus core evidence-binding comparison."""

    def __init__(self, success_condition: Mapping[str, Any]) -> None:
        self.success_condition = success_condition

    def verify(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        raw_result: RawResult,
        before_state: Mapping[str, Any],
        after_state: Mapping[str, Any],
        expected_evidence: Sequence[EvidenceRef],
    ) -> VerificationResult:
        del context, before_state
        semantic_reasons: list[str] = []
        if after_state.get(self.success_condition["path"]) != self.success_condition["equals"]:
            semantic_reasons.append("post_state_condition_mismatch")
        if raw_result.reported_value != after_state.get(request.target):
            semantic_reasons.append("reported_value_state_mismatch")
        evidence_status, evidence_reasons = evidence_binding(expected_evidence, raw_result.evidence)
        return VerificationResult(
            semantic_valid=not semantic_reasons,
            semantic_reasons=tuple(semantic_reasons or ["independent_post_state_match"]),
            evidence_status=evidence_status,
            evidence_reasons=evidence_reasons,
            observed_post_state_sha256=state_sha256(after_state),
        )


def expected_evidence(
    contract: dict[str, Any], core_contract: TaskContract
) -> tuple[EvidenceRef, ...]:
    hashes = {
        "task_contract": core_contract.content_sha256,
        "program": core_contract.expected_program_sha256,
    }
    return tuple(
        EvidenceRef(row["role"], row["artifact_id"], row["path"], hashes[row["role"]])
        for row in contract["evidence_requirements"]
    )


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
    adapter: LocalSetAdapter | None = None,
    collect_observations: bool = True,
) -> dict[str, Any]:
    contract_path = Path(contract_path)
    contract, contract_bytes = load_json_bytes(contract_path)
    validate_contract(contract)
    resolved_program = Path(program_path) if program_path is not None else SUBSTRATE / contract["program"]["path"]
    program = (
        ProgramArtifact(contract["program"]["program_id"], contract["program"]["path"], resolved_program.read_bytes())
        if resolved_program.is_file()
        else None
    )
    core_contract = TaskContract(
        task_id=contract["task_id"],
        contract_id=contract["contract_id"],
        expected_program_id=contract["program"]["program_id"],
        expected_program_sha256=contract["program"]["sha256"],
        execution_id=contract["execution"]["execution_id"],
        configuration_id=contract["execution"]["configuration_id"],
        content=contract_bytes,
    )
    request = ExecutionRequest(**contract["request"], requires_mutation_prevention=True)
    state = copy.deepcopy(contract["initial_state"])
    terminal = execute(
        contract=core_contract,
        program=program,
        supplied_identity=identity or declared_identity(contract),
        request=request,
        state=state,
        expected_evidence=expected_evidence(contract, core_contract),
        policy_gate=PrefixPolicyGate(contract["policy"]),
        executor=adapter or LocalSetAdapter(),
        verifier=SetResultVerifier(contract["success_condition"]),
        collect_observations=collect_observations,
    )
    record = terminal_record_to_dict(terminal)
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

#!/usr/bin/env python3
"""Run one deterministic read-only lookup through ``irisx.core``."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import replace
from pathlib import Path
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
from irisx.core.interfaces import PolicyGate  # noqa: E402
from irisx.core.records import (  # noqa: E402
    EvidenceRequirement,
    EvidenceRef,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRequest,
    ProgramArtifact,
    RawResult,
    TaskContract,
    VerificationResult,
    sha256_bytes,
)


DEFAULT_CONTRACT = SUBSTRATE / "inputs" / "task-contract.json"


class ContractError(ValueError):
    """The read-only integration contract is invalid."""


def load_contract(path: Path) -> tuple[dict[str, Any], bytes]:
    content = path.read_bytes()
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ContractError("task contract must be an object")
    required = {
        "schema_version",
        "task_id",
        "contract_id",
        "program",
        "execution",
        "request",
        "initial_state",
        "success_condition",
        "evidence_requirements",
    }
    if value.get("schema_version") != 1 or required - set(value):
        raise ContractError("task contract schema or required fields are invalid")
    if value["request"].get("operation") != "lookup":
        raise ContractError("integration path supports exactly one lookup operation")
    if value["request"].get("target") not in value["initial_state"]:
        raise ContractError("lookup target must exist in the frozen in-memory state")
    if value["success_condition"].get("target") != value["request"]["target"]:
        raise ContractError("success condition must bind the requested target")
    roles = {row.get("role") for row in value["evidence_requirements"]}
    if len(value["evidence_requirements"]) != 2 or roles != {"task_contract", "program"}:
        raise ContractError("task_contract and program evidence are required")
    return value, content


def declared_identity(contract: Mapping[str, Any]) -> ExecutionIdentity:
    return ExecutionIdentity(
        contract["task_id"],
        contract["contract_id"],
        contract["program"]["program_id"],
        contract["execution"]["execution_id"],
        contract["execution"]["configuration_id"],
    )


def expected_evidence(
    contract: Mapping[str, Any], core_contract: TaskContract
) -> tuple[EvidenceRef, ...]:
    hashes = {
        "task_contract": core_contract.content_sha256,
        "program": core_contract.expected_program_sha256,
    }
    return tuple(
        EvidenceRef(row["role"], row["artifact_id"], row["path"], hashes[row["role"]])
        for row in contract["evidence_requirements"]
    )


class ReadOnlyLookupAdapter:
    """Different concrete adapter: one map lookup and no mutation primitive."""

    def __init__(self, *, evidence_hash_overrides: Mapping[str, str] | None = None) -> None:
        self.evidence_hash_overrides = dict(evidence_hash_overrides or {})
        self.lookup_calls = 0
        self.mutation_primitive_calls = 0

    def execute(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        state: MutableMapping[str, Any],
        expected_evidence_refs: Sequence[EvidenceRef],
    ) -> RawResult:
        del context
        if request.operation != "lookup" or request.requires_mutation_prevention:
            raise ValueError("read-only adapter accepts only a classified lookup")
        self.lookup_calls += 1
        result = copy.deepcopy(state[request.target])
        evidence = tuple(
            replace(item, sha256=self.evidence_hash_overrides.get(item.role, item.sha256))
            for item in expected_evidence_refs
        )
        return RawResult("success", result, evidence, 1, 0)


class LookupVerifier:
    def __init__(self, success_condition: Mapping[str, Any]) -> None:
        self.success_condition = success_condition

    def verify(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        raw_result: RawResult,
        before_state: Mapping[str, Any],
        after_state: Mapping[str, Any],
        expected_evidence_refs: Sequence[EvidenceRef],
    ) -> VerificationResult:
        del context
        reasons: list[str] = []
        if before_state != after_state:
            reasons.append("read_only_state_changed")
        if raw_result.reported_value != before_state.get(request.target):
            reasons.append("lookup_result_mismatch")
        if raw_result.reported_value != self.success_condition["equals"]:
            reasons.append("success_condition_mismatch")
        evidence_status, evidence_reasons = evidence_binding(
            expected_evidence_refs, raw_result.evidence
        )
        return VerificationResult(
            not reasons,
            tuple(reasons or ["independent_lookup_match"]),
            evidence_status,
            evidence_reasons,
            state_sha256(after_state),
        )


def execute_lookup(
    contract_path: Path = DEFAULT_CONTRACT,
    *,
    adapter: ReadOnlyLookupAdapter | None = None,
    identity: ExecutionIdentity | None = None,
    policy_gate: PolicyGate | None = None,
    collect_observations: bool = True,
) -> dict[str, Any]:
    contract_path = Path(contract_path)
    contract, contract_bytes = load_contract(contract_path)
    program_path = SUBSTRATE / contract["program"]["path"]
    program = ProgramArtifact(
        contract["program"]["program_id"], contract["program"]["path"], program_path.read_bytes()
    )
    core_contract = TaskContract(
        task_id=contract["task_id"],
        contract_id=contract["contract_id"],
        expected_program_id=contract["program"]["program_id"],
        expected_program_sha256=contract["program"]["sha256"],
        execution_id=contract["execution"]["execution_id"],
        configuration_id=contract["execution"]["configuration_id"],
        content=contract_bytes,
        evidence_requirements=tuple(
            EvidenceRequirement(**row) for row in contract["evidence_requirements"]
        ),
    )
    request = ExecutionRequest(**contract["request"], requires_mutation_prevention=False)
    state = copy.deepcopy(contract["initial_state"])
    terminal = execute(
        contract=core_contract,
        program=program,
        supplied_identity=identity or declared_identity(contract),
        request=request,
        state=state,
        expected_evidence=expected_evidence(contract, core_contract),
        executor=adapter or ReadOnlyLookupAdapter(),
        verifier=LookupVerifier(contract["success_condition"]),
        policy_gate=policy_gate,
        collect_observations=collect_observations,
    )
    return terminal_record_to_dict(terminal)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    record = execute_lookup(args.contract)
    print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if record["verified_success_eligibility"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import dataclasses
import hashlib
import unittest

from irisx.core.interfaces import ExecutorAdapter, IndependentVerifier, PolicyGate
from irisx.core.execution import bind_execution
from irisx.core.records import (
    UNKNOWN,
    EvidenceRequirement,
    EvidenceRef,
    ExecutionIdentity,
    ProgramArtifact,
    ResourceLedger,
    TaskContract,
)


def requirements(
    contract_id: str = "contract", program_id: str = "program"
) -> tuple[EvidenceRequirement, ...]:
    return (
        EvidenceRequirement("task_contract", contract_id, "task-contract.json"),
        EvidenceRequirement("program", program_id, "program.txt"),
    )


def task_contract(
    *, evidence_requirements: tuple[EvidenceRequirement, ...] | None = None
) -> TaskContract:
    return TaskContract(
        task_id="task",
        contract_id="contract",
        expected_program_id="program",
        expected_program_sha256="0" * 64,
        execution_id="execution",
        configuration_id="configuration",
        content=b"exact bytes",
        evidence_requirements=(
            requirements() if evidence_requirements is None else evidence_requirements
        ),
    )


class CoreRecordInvariantTests(unittest.TestCase):
    def test_identity_records_are_immutable(self) -> None:
        identity = ExecutionIdentity("task", "contract", "program", "execution", "configuration")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            identity.task_id = "crossed"  # type: ignore[misc]

    def test_artifact_records_bind_exact_bytes(self) -> None:
        contract = task_contract()
        self.assertEqual(contract.content_bytes, 11)
        self.assertEqual(len(contract.content_sha256), 64)

    def test_evidence_requirement_rejects_empty_fields(self) -> None:
        for values in (("", "artifact", "path"), ("role", "", "path"), ("role", "artifact", "")):
            with self.subTest(values=values), self.assertRaises(ValueError):
                EvidenceRequirement(*values)

    def test_task_contract_rejects_duplicate_requirement_roles(self) -> None:
        duplicate = (
            EvidenceRequirement("task_contract", "contract", "one.json"),
            EvidenceRequirement("task_contract", "contract", "two.json"),
        )
        with self.assertRaisesRegex(ValueError, "roles must be unique"):
            task_contract(evidence_requirements=duplicate)

    def test_task_contract_requirement_identifies_current_contract(self) -> None:
        crossed = requirements(contract_id="contract.crossed")
        with self.assertRaisesRegex(ValueError, "must identify this contract"):
            task_contract(evidence_requirements=crossed)

    def test_program_requirement_identifies_expected_program(self) -> None:
        crossed = requirements(program_id="program.crossed")
        with self.assertRaisesRegex(ValueError, "must identify the expected program"):
            task_contract(evidence_requirements=crossed)

    def test_bound_requirement_hashes_come_from_exact_artifact_bytes(self) -> None:
        program_content = b"program bytes"
        contract = TaskContract(
            task_id="task",
            contract_id="contract",
            expected_program_id="program",
            expected_program_sha256=hashlib.sha256(program_content).hexdigest(),
            execution_id="execution",
            configuration_id="configuration",
            content=b"contract bytes",
            evidence_requirements=requirements(),
        )
        program = ProgramArtifact("program", "program.txt", program_content)
        context = bind_execution(
            contract,
            program,
            ExecutionIdentity("task", "contract", "program", "execution", "configuration"),
        )
        bound = {item.role: item for item in context.evidence_requirements}
        self.assertEqual(bound["task_contract"].sha256, contract.content_sha256)
        self.assertEqual(bound["program"].sha256, program.content_sha256)

    def test_resource_unknowns_and_observed_zeroes_stay_distinct(self) -> None:
        ledger = ResourceLedger(artifact_reads=2, executor_calls=1)
        self.assertEqual(ledger.model_calls, 0)
        self.assertEqual(ledger.network_calls, 0)
        self.assertEqual(ledger.retry_count, 0)
        self.assertEqual(ledger.recovery_count, 0)
        self.assertEqual(ledger.wall_time_ns, UNKNOWN)
        self.assertEqual(ledger.provider_cost_usd, UNKNOWN)

    def test_evidence_requires_a_concrete_hash(self) -> None:
        with self.assertRaises(ValueError):
            EvidenceRef("program", "program", "program.txt", "Unknown")

    def test_core_exposes_only_the_three_replaceable_protocols(self) -> None:
        self.assertTrue(getattr(PolicyGate, "_is_protocol", False))
        self.assertTrue(getattr(ExecutorAdapter, "_is_protocol", False))
        self.assertTrue(getattr(IndependentVerifier, "_is_protocol", False))


if __name__ == "__main__":
    unittest.main()

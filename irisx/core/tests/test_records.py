from __future__ import annotations

import dataclasses
import unittest

from irisx.core.interfaces import ExecutorAdapter, IndependentVerifier, PolicyGate
from irisx.core.records import (
    UNKNOWN,
    EvidenceRef,
    ExecutionIdentity,
    ResourceLedger,
    TaskContract,
)


class CoreRecordInvariantTests(unittest.TestCase):
    def test_identity_records_are_immutable(self) -> None:
        identity = ExecutionIdentity("task", "contract", "program", "execution", "configuration")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            identity.task_id = "crossed"  # type: ignore[misc]

    def test_artifact_records_bind_exact_bytes(self) -> None:
        contract = TaskContract(
            task_id="task",
            contract_id="contract",
            expected_program_id="program",
            expected_program_sha256="0" * 64,
            execution_id="execution",
            configuration_id="configuration",
            content=b"exact bytes",
        )
        self.assertEqual(contract.content_bytes, 11)
        self.assertEqual(len(contract.content_sha256), 64)

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


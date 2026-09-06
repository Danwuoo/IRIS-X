from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import task_family  # noqa: E402

from irisx.core.execution import execute  # noqa: E402
from irisx.core.records import ExecutionIdentity, ProgramArtifact  # noqa: E402


class CrossTaskIsolationTests(unittest.TestCase):
    def binding_record(
        self,
        contract_key: str,
        program_key: str,
        *,
        identity: ExecutionIdentity | None = None,
    ):
        contract_definition = task_family.load_task(contract_key)
        program_definition = task_family.load_task(program_key)
        adapter = task_family.OfflineOutputAdapter("{}")
        terminal = execute(
            contract=contract_definition.core_contract(),
            program=program_definition.program_artifact(),
            supplied_identity=identity or contract_definition.execution_identity(),
            request=contract_definition.execution_request(),
            state=contract_definition.initial_state(),
            executor=adapter,
            verifier=task_family.verifier_for(contract_definition),
        )
        return terminal, adapter

    def test_task_a_contract_with_task_b_program_rejects_before_execution(self) -> None:
        terminal, adapter = self.binding_record("A", "B")
        self.assertEqual(terminal.terminal_execution_status, "rejected")
        self.assertEqual(terminal.empirical_evidence_status, "invalid_binding")
        self.assertEqual(adapter.calls, 0)

    def test_task_a_contract_with_task_c_program_rejects_before_execution(self) -> None:
        terminal, adapter = self.binding_record("A", "C")
        self.assertEqual(terminal.terminal_execution_status, "rejected")
        self.assertEqual(terminal.empirical_evidence_status, "invalid_binding")
        self.assertEqual(adapter.calls, 0)

    def test_task_a_evidence_cannot_satisfy_task_b(self) -> None:
        evidence = task_family.bound_evidence(task_family.load_task("A"))
        terminal, _ = task_family.execute_offline("B", '{"total":43}', evidence=evidence)
        self.assertTrue(terminal.verification.semantic_valid)
        self.assertEqual(terminal.empirical_evidence_status, "invalid_binding")
        self.assertEqual(terminal.acceptance_decision, "reject")

    def test_task_b_evidence_cannot_satisfy_task_c(self) -> None:
        evidence = task_family.bound_evidence(task_family.load_task("B"))
        output = '{"ranked":[{"id":"b","rank":1},{"id":"c","rank":2}]}'
        terminal, _ = task_family.execute_offline("C", output, evidence=evidence)
        self.assertTrue(terminal.verification.semantic_valid)
        self.assertEqual(terminal.empirical_evidence_status, "invalid_binding")
        self.assertFalse(terminal.verified_success_eligibility)

    def test_task_a_output_under_task_b_verifier_rejects(self) -> None:
        terminal, _ = task_family.execute_offline("B", '{"selected_ids":["b","d"]}')
        self.assertFalse(terminal.verification.semantic_valid)
        self.assertIn("aggregation_output_schema_mismatch", terminal.verification.semantic_reasons)

    def test_task_b_output_under_task_c_verifier_rejects(self) -> None:
        terminal, _ = task_family.execute_offline("C", '{"total":43}')
        self.assertFalse(terminal.verification.semantic_valid)
        self.assertIn("ranking_output_schema_mismatch", terminal.verification.semantic_reasons)

    def test_task_c_output_under_task_a_verifier_rejects(self) -> None:
        output = '{"ranked":[{"id":"b","rank":1},{"id":"c","rank":2}]}'
        terminal, _ = task_family.execute_offline("A", output)
        self.assertFalse(terminal.verification.semantic_valid)
        self.assertIn("filter_output_schema_mismatch", terminal.verification.semantic_reasons)

    def test_task_b_schema_used_for_task_c_rejects(self) -> None:
        wrong_path = task_family.TASK_SPECS["B"]["schema_path"]
        with mock.patch.dict(task_family.TASK_SPECS["C"], {"schema_path": wrong_path}):
            with self.assertRaises(task_family.TaskFamilyError):
                task_family.load_task("C")

    def test_wrong_program_hash_rejects_before_execution(self) -> None:
        definition = task_family.load_task("A")
        wrong_program = ProgramArtifact(
            definition.spec["program_id"],
            definition.spec["program_path"],
            definition.program_bytes + b"drift",
        )
        adapter = task_family.OfflineOutputAdapter('{"selected_ids":["b","d"]}')
        terminal = execute(
            contract=definition.core_contract(),
            program=wrong_program,
            supplied_identity=definition.execution_identity(),
            request=definition.execution_request(),
            state=definition.initial_state(),
            executor=adapter,
            verifier=task_family.verifier_for(definition),
        )
        self.assertEqual(terminal.terminal_execution_status, "rejected")
        self.assertIn("program_hash_mismatch", terminal.verification.semantic_reasons)
        self.assertEqual(adapter.calls, 0)

    def test_task_c_program_identity_paired_with_task_a_rejects(self) -> None:
        task_a = task_family.load_task("A")
        task_c = task_family.load_task("C")
        crossed = replace(task_a.execution_identity(), program_id=task_c.spec["program_id"])
        terminal, adapter = self.binding_record("A", "A", identity=crossed)
        self.assertEqual(terminal.terminal_execution_status, "rejected")
        self.assertIn("identity_mismatch:program_id", terminal.verification.semantic_reasons)
        self.assertEqual(adapter.calls, 0)

    def test_task_specific_evidence_path_cannot_substitute(self) -> None:
        definition = task_family.load_task("B")
        evidence = list(task_family.bound_evidence(definition))
        evidence[1] = replace(
            evidence[1],
            path=task_family.TASK_SPECS["A"]["program_path"],
        )
        terminal, _ = task_family.execute_offline("B", '{"total":43}', evidence=tuple(evidence))
        self.assertEqual(terminal.empirical_evidence_status, "invalid_binding")
        self.assertIn("program_binding_mismatch", terminal.verification.evidence_reasons)

    def test_contract_and_program_evidence_hashes_are_task_specific(self) -> None:
        bindings = {
            key: {(item.role, item.path, item.sha256) for item in task_family.bound_evidence(task_family.load_task(key))}
            for key in task_family.TASK_SPECS
        }
        self.assertEqual(len({frozenset(value) for value in bindings.values()}), 3)


if __name__ == "__main__":
    unittest.main()

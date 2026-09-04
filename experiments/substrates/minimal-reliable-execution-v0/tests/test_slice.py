from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUBSTRATE / "scripts"))
import run_slice  # noqa: E402


CONTRACT_PATH = SUBSTRATE / "inputs" / "task-contract.json"
PROGRAM_PATH = SUBSTRATE / "inputs" / "specialization-program.txt"


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def write_contract(directory: Path, value: dict) -> Path:
    path = directory / "task-contract.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


class MinimalReliableExecutionSliceTests(unittest.TestCase):
    def test_valid_identity_result_and_evidence_produce_verified_success(self) -> None:
        adapter = run_slice.LocalSetAdapter()
        record = run_slice.execute_slice(adapter=adapter)
        self.assertEqual(record["actual_outcome"], "success")
        self.assertEqual(record["producer_claim"], "success")
        self.assertEqual(record["empirical_evidence_status"], "sufficient")
        self.assertEqual(record["acceptance_decision"], "accept")
        self.assertTrue(record["verified_success_eligibility"])
        self.assertEqual(record["joint_interpretation"], "verified_success")
        self.assertEqual(adapter.primitive_calls, 1)
        self.assertEqual(record["side_effects"]["changed_paths"], ["scratch/result"])

    def test_identity_mismatch_rejects_before_executor(self) -> None:
        contract = load_contract()
        expected = run_slice.declared_identity(contract)
        crossed = run_slice.ExecutionIdentity(
            task_id="task.crossed.v0",
            contract_id=expected.contract_id,
            program_id=expected.program_id,
            execution_id=expected.execution_id,
            configuration_id=expected.configuration_id,
        )
        adapter = run_slice.LocalSetAdapter()
        record = run_slice.execute_slice(identity=crossed, adapter=adapter)
        self.assertEqual(record["empirical_evidence_status"], "invalid_binding")
        self.assertEqual(record["acceptance_decision"], "reject")
        self.assertFalse(record["verified_success_eligibility"])
        self.assertEqual(record["terminal_execution_status"], "rejected")
        self.assertEqual(adapter.primitive_calls, 0)
        self.assertFalse(record["side_effects"]["mutation_primitive_executed"])

    def test_success_claim_does_not_override_independent_semantic_failure(self) -> None:
        adapter = run_slice.LocalSetAdapter(state_value="incorrect", producer_claim="success")
        record = run_slice.execute_slice(adapter=adapter)
        self.assertEqual(record["producer_claim"], "success")
        self.assertEqual(record["actual_outcome"], "failure")
        self.assertFalse(record["verification"]["semantic_valid"])
        self.assertEqual(record["acceptance_decision"], "reject")
        self.assertFalse(record["verified_success_eligibility"])

    def test_stale_program_evidence_denies_eligibility_without_rewriting_outcome(self) -> None:
        adapter = run_slice.LocalSetAdapter(evidence_hash_overrides={"program": "0" * 64})
        record = run_slice.execute_slice(adapter=adapter)
        self.assertEqual(record["actual_outcome"], "success")
        self.assertEqual(record["empirical_evidence_status"], "invalid_binding")
        self.assertEqual(record["acceptance_decision"], "reject")
        self.assertFalse(record["verified_success_eligibility"])
        self.assertEqual(record["joint_interpretation"], "unverified_success")

    def test_prohibited_mutation_is_denied_before_primitive_and_state_is_unchanged(self) -> None:
        contract = load_contract()
        contract["request"] = {
            "action_id": "action.prohibited.v0",
            "operation": "set",
            "target": "protected/record",
            "value": "changed",
        }
        with tempfile.TemporaryDirectory(prefix="irisx-minimal-slice-contract-") as temporary:
            path = write_contract(Path(temporary), contract)
            adapter = run_slice.LocalSetAdapter()
            record = run_slice.execute_slice(path, adapter=adapter)
        self.assertEqual(record["policy_decision"]["decision"], "deny")
        self.assertEqual(record["policy_decision"]["timing"], "before_mutation_primitive")
        self.assertFalse(record["policy_decision"]["mutation_primitive_executed"])
        self.assertEqual(adapter.primitive_calls, 0)
        self.assertEqual(record["side_effects"]["state_before_sha256"], record["side_effects"]["state_after_sha256"])
        self.assertEqual(record["side_effects"]["changed_paths"], [])

    def test_structured_observations_do_not_change_adjudication(self) -> None:
        with_observations = run_slice.execute_slice(collect_observations=True)
        without_observations = run_slice.execute_slice(collect_observations=False)
        fields = (
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
        )
        self.assertTrue(with_observations["observations"])
        self.assertEqual(without_observations["observations"], [])
        for field in fields:
            self.assertEqual(with_observations[field], without_observations[field])

    def test_modification_after_program_freeze_is_detected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="irisx-minimal-slice-program-") as temporary:
            changed = Path(temporary) / "specialization-program.txt"
            changed.write_bytes(PROGRAM_PATH.read_bytes() + b"changed\n")
            adapter = run_slice.LocalSetAdapter()
            record = run_slice.execute_slice(program_path=changed, adapter=adapter)
        self.assertEqual(record["empirical_evidence_status"], "invalid_binding")
        self.assertEqual(record["verification"]["reasons"], ["program_hash_mismatch"])
        self.assertEqual(adapter.primitive_calls, 0)

    def test_terminal_record_preserves_separate_semantics_and_zero_or_unknown_resources(self) -> None:
        record = run_slice.execute_slice()
        run_slice.validate_terminal_record(record)
        self.assertNotIn("status", record)
        self.assertIn("actual_outcome", record)
        self.assertIn("producer_claim", record)
        self.assertIn("empirical_evidence_status", record)
        self.assertIn("acceptance_decision", record)
        self.assertIn("verified_success_eligibility", record)
        resources = record["resource_ledger"]
        self.assertEqual(resources["model_calls"], 0)
        self.assertEqual(resources["network_calls"], 0)
        self.assertEqual(resources["retry_count"], 0)
        self.assertEqual(resources["route_count"], 0)
        self.assertEqual(resources["escalation_count"], 0)
        self.assertEqual(resources["recovery_count"], 0)
        self.assertEqual(resources["provider_cost_usd"], "Unknown")
        self.assertFalse(record["recovery"]["attempted"])
        self.assertFalse(record["recovery"]["silent_retry"])

    def test_contract_fixture_can_be_reloaded_without_changing_program_hash(self) -> None:
        contract = load_contract()
        self.assertEqual(contract["program"]["sha256"], run_slice.sha256_file(PROGRAM_PATH))
        copied = copy.deepcopy(contract)
        run_slice.validate_contract(copied)


if __name__ == "__main__":
    unittest.main()

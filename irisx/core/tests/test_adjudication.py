from __future__ import annotations

import hashlib
import unittest
from typing import Any

from irisx.core.execution import terminal_record_to_dict
from irisx.core.records import (
    AdjudicationResult,
    EvidenceRequirement,
    ExecutionIdentity,
    Observation,
    PolicyDecision,
    ProgramArtifact,
    ResourceLedger,
    TaskContract,
    TerminalRecord,
    VerificationResult,
    adjudicate,
)


STATE_SHA256 = hashlib.sha256(b"state").hexdigest()
PROGRAM_BYTES = b"program"


def verification(*, semantic_valid: bool = True, evidence_status: str = "sufficient") -> VerificationResult:
    return VerificationResult(
        semantic_valid=semantic_valid,
        semantic_reasons=("bounded_semantic_result",),
        evidence_status=evidence_status,
        evidence_reasons=("bounded_evidence_result",),
        observed_post_state_sha256=STATE_SHA256,
    )


def terminal_record(
    verifier_result: VerificationResult,
    *,
    terminal_execution_status: str = "completed",
    **overrides: Any,
) -> TerminalRecord:
    contract = TaskContract(
        task_id="task",
        contract_id="contract",
        expected_program_id="program",
        expected_program_sha256=hashlib.sha256(PROGRAM_BYTES).hexdigest(),
        execution_id="execution",
        configuration_id="configuration",
        content=b"contract",
        evidence_requirements=(
            EvidenceRequirement("task_contract", "contract", "task-contract.json"),
            EvidenceRequirement("program", "program", "program.txt"),
        ),
    )
    canonical = adjudicate(
        verifier_result,
        terminal_execution_status=terminal_execution_status,
    )
    values: dict[str, Any] = {
        "requested_identity": ExecutionIdentity(
            "task", "contract", "program", "execution", "configuration"
        ),
        "contract": contract,
        "program": ProgramArtifact("program", "program.txt", PROGRAM_BYTES),
        "actual_outcome": canonical.actual_outcome,
        "producer_claim": "success",
        "empirical_evidence_status": verifier_result.evidence_status,
        "acceptance_decision": canonical.acceptance_decision,
        "verified_success_eligibility": canonical.verified_success_eligibility,
        "joint_interpretation": canonical.joint_interpretation,
        "terminal_execution_status": terminal_execution_status,
        "policy_decision": PolicyDecision("not_required", (), "not_applicable"),
        "state_before_sha256": STATE_SHA256,
        "state_after_sha256": STATE_SHA256,
        "changed_paths": (),
        "verification": verifier_result,
        "evidence": (),
        "observations": (),
        "resource_ledger": ResourceLedger(artifact_reads=2, executor_calls=1),
    }
    values.update(overrides)
    return TerminalRecord(**values)


def semantics(record: TerminalRecord) -> AdjudicationResult:
    return AdjudicationResult(
        record.actual_outcome,
        record.acceptance_decision,
        record.verified_success_eligibility,
        record.joint_interpretation,
    )


class CanonicalAdjudicationTests(unittest.TestCase):
    def test_supported_bounded_semantics_are_canonical(self) -> None:
        cases = (
            (
                verification(),
                AdjudicationResult("success", "accept", True, "verified_success"),
            ),
            (
                verification(evidence_status="insufficient"),
                AdjudicationResult("success", "reject", False, "unverified_success"),
            ),
            (
                verification(evidence_status="invalid_binding"),
                AdjudicationResult("success", "reject", False, "unverified_success"),
            ),
            (
                verification(semantic_valid=False),
                AdjudicationResult(
                    "failure", "reject", False, "correctly_recognized_failure"
                ),
            ),
        )
        for verifier_result, expected in cases:
            with self.subTest(verifier_result=verifier_result):
                self.assertEqual(
                    adjudicate(verifier_result, terminal_execution_status="completed"),
                    expected,
                )

    def test_verified_success_requires_completed_execution(self) -> None:
        self.assertEqual(
            adjudicate(verification(), terminal_execution_status="failed"),
            AdjudicationResult("success", "reject", False, "unverified_success"),
        )

    def test_invalid_terminal_execution_status_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "terminal_execution_status"):
            adjudicate(verification(), terminal_execution_status="unknown")

    def test_semantic_validity_cannot_be_rewritten_as_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "actual outcome"):
            terminal_record(verification(), actual_outcome="failure")

    def test_semantic_failure_cannot_be_rewritten_as_success(self) -> None:
        with self.assertRaisesRegex(ValueError, "actual outcome"):
            terminal_record(verification(semantic_valid=False), actual_outcome="success")

    def test_noncanonical_acceptance_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "terminal acceptance"):
            terminal_record(verification(evidence_status="insufficient"), acceptance_decision="accept")

    def test_noncanonical_eligibility_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "verified-success eligibility"):
            terminal_record(
                verification(evidence_status="invalid_binding"),
                verified_success_eligibility=True,
            )

    def test_noncanonical_joint_interpretation_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "joint interpretation"):
            terminal_record(verification(), joint_interpretation="unresolved")

    def test_terminal_evidence_status_must_match_verifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "independent verification"):
            terminal_record(verification(), empirical_evidence_status="insufficient")

    def test_eligibility_true_for_failure_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "verified-success eligibility"):
            terminal_record(
                verification(semantic_valid=False),
                verified_success_eligibility=True,
            )

    def test_eligibility_true_without_sufficient_evidence_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "verified-success eligibility"):
            terminal_record(
                verification(evidence_status="insufficient"),
                verified_success_eligibility=True,
            )

    def test_eligibility_true_without_acceptance_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "terminal acceptance"):
            terminal_record(
                verification(),
                acceptance_decision="reject",
                verified_success_eligibility=True,
            )

    def test_producer_claim_cannot_forge_verifier_failure(self) -> None:
        verifier_result = verification(semantic_valid=False)
        record = terminal_record(verifier_result, producer_claim="success")
        self.assertEqual(
            semantics(record),
            adjudicate(verifier_result, terminal_execution_status="completed"),
        )
        with self.assertRaisesRegex(ValueError, "actual outcome"):
            terminal_record(
                verifier_result,
                producer_claim="success",
                actual_outcome="success",
            )

    def test_producer_observations_and_resources_are_non_authoritative(self) -> None:
        verifier_result = verification()
        baseline = terminal_record(verifier_result, producer_claim="success")
        challenged = terminal_record(
            verifier_result,
            producer_claim="failure",
            observations=(
                Observation(1, "non_authoritative", {"claimed_outcome": "failure"}),
            ),
            resource_ledger=ResourceLedger(
                artifact_reads=99,
                executor_calls=7,
                wall_time_ns=123456,
            ),
        )
        self.assertEqual(semantics(challenged), semantics(baseline))
        self.assertEqual(
            semantics(challenged),
            adjudicate(verifier_result, terminal_execution_status="completed"),
        )

    def test_terminal_serialization_preserves_schema_version_and_keys(self) -> None:
        serialized = terminal_record_to_dict(terminal_record(verification()))
        self.assertEqual(serialized["schema_version"], 1)
        self.assertEqual(
            set(serialized),
            {
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
            },
        )


if __name__ == "__main__":
    unittest.main()

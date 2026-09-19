from __future__ import annotations

import contextlib
import copy
import hashlib
import io
from pathlib import Path
import unittest

import support  # noqa: F401

from irisx import cli
from irisx.admission import GATE_IDS, admission_summary, validate_admission_document, validate_admission_file
from irisx.canonical import digest_value, read_json
from irisx.errors import ValidationError


ROOT = Path(__file__).resolve().parents[1]
ADMISSION = ROOT / "trials/p2-admission/admission.json"


def resign(value: dict) -> dict:
    value = copy.deepcopy(value)
    unsigned = {key: value[key] for key in ("schema", "schema_version", "artifact_id", "version", "payload")}
    value["content_digest"] = digest_value(unsigned)
    return value


class AdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.value = read_json(ADMISSION)

    def test_tracked_admission_is_valid_and_blocked(self) -> None:
        document = validate_admission_file(ADMISSION, ROOT)
        summary = admission_summary(document)
        self.assertEqual(summary["status"], "admission_blocked")
        self.assertEqual(summary["unresolved_gates"], list(GATE_IDS))
        self.assertFalse(summary["execution_eligible"])
        self.assertFalse(summary["promotion_eligible"])
        self.assertFalse(summary["domain_package_eligible"])

    def test_historical_snapshot_does_not_claim_current_agents_bytes(self) -> None:
        current_agents = (ROOT / "AGENTS.md").read_bytes()
        self.assertNotEqual(
            self.value["payload"]["authority_refs"][0]["content_digest"],
            "sha256:" + hashlib.sha256(current_agents).hexdigest(),
        )
        validate_admission_file(ADMISSION, ROOT)

    def test_external_execution_cannot_be_self_authorized(self) -> None:
        changed = copy.deepcopy(self.value)
        changed["payload"]["scope"]["external_execution"] = True
        with self.assertRaisesRegex(ValidationError, "is not authorized"):
            validate_admission_document(resign(changed), ROOT)

    def test_owner_options_remain_mutually_exclusive_execution_paths(self) -> None:
        changed = copy.deepcopy(self.value)
        changed["payload"]["decision_options"][1]["execution_mode"] = "local_offline"
        with self.assertRaisesRegex(ValidationError, "do not match the option"):
            validate_admission_document(resign(changed), ROOT)

    def test_missing_rights_or_provenance_cannot_clear_gate(self) -> None:
        changed = copy.deepcopy(self.value)
        gate = next(item for item in changed["payload"]["gates"] if item["gate_id"] == "data-rights-and-provenance")
        gate["status"] = "authorized"
        gate["owner_decision"] = "Approved without evidence"
        with self.assertRaisesRegex(ValidationError, "authorized gates require"):
            validate_admission_document(resign(changed), ROOT)

    def test_synthetic_evidence_cannot_masquerade_as_real(self) -> None:
        changed = copy.deepcopy(self.value)
        changed["payload"]["trial_draft"]["provided_evidence_class"] = "synthetic"
        changed["payload"]["eligibility"]["promotion"] = True
        with self.assertRaisesRegex(ValidationError, "synthetic evidence cannot be presented as real"):
            validate_admission_document(resign(changed), ROOT)

    def test_stale_or_wrong_authority_reference_is_rejected(self) -> None:
        changed = copy.deepcopy(self.value)
        changed["payload"]["authority_refs"][0]["content_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValidationError, "stale or wrong authority reference"):
            validate_admission_document(resign(changed), ROOT)

    def test_unapproved_provider_or_budget_is_rejected(self) -> None:
        base = copy.deepcopy(self.value)
        authorization = base["payload"]["execution_authorization"]
        authorization.update(
            {
                "state": "authorized",
                "mode": "external_provider",
                "provider": None,
                "model": "unapproved-model",
                "permitted_data_classes": ["public"],
                "maximum_budget": {"state": "observed", "value": 1, "unit": "usd"},
                "retention": "no-retention",
            }
        )
        with self.assertRaisesRegex(ValidationError, "approved provider and model"):
            validate_admission_document(resign(base), ROOT)

        changed = copy.deepcopy(self.value)
        authorization = changed["payload"]["execution_authorization"]
        authorization.update(
            {
                "state": "authorized",
                "mode": "external_provider",
                "provider": "unapproved-provider",
                "model": "unapproved-model",
                "permitted_data_classes": ["public"],
                "retention": "no-retention",
            }
        )
        with self.assertRaisesRegex(ValidationError, "non-negative observed USD limit"):
            validate_admission_document(resign(changed), ROOT)

    def test_invalid_execution_promotion_or_package_eligibility_is_rejected(self) -> None:
        for field in ("engineering_trial_execution", "promotion", "domain_package"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.value)
                changed["payload"]["eligibility"][field] = True
                with self.assertRaisesRegex(ValidationError, "must be false while admission is blocked"):
                    validate_admission_document(resign(changed), ROOT)

    def test_draft_reference_cannot_be_bound_without_later_decision(self) -> None:
        changed = copy.deepcopy(self.value)
        ref = changed["payload"]["trial_draft"]["workload_ref"]
        ref.update(
            {
                "state": "bound",
                "artifact_id": "unapproved-workload",
                "version": "1.0.0",
                "content_digest": "sha256:" + "0" * 64,
            }
        )
        with self.assertRaisesRegex(ValidationError, "draft artifact references must remain Unknown"):
            validate_admission_document(resign(changed), ROOT)

    def test_cli_reports_blocked_status_and_rejects_bad_digest(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(["admission", "validate", str(ADMISSION)]), 0)
        self.assertIn("admission_blocked", output.getvalue())
        self.assertIn("8 unresolved gates", output.getvalue())

        changed = copy.deepcopy(self.value)
        changed["payload"]["eligibility"]["reason"] = "tampered"
        with self.assertRaisesRegex(ValidationError, "digest mismatch"):
            validate_admission_document(changed, ROOT)


if __name__ == "__main__":
    unittest.main()

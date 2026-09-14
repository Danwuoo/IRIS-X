from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from support import PACKAGE_ROOT, make_bundle, reseal, write_bundle, write_text


SCRIPTS = PACKAGE_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import common  # noqa: E402
import validate_submission as validator  # noqa: E402


ROLES = ["task_oracle", "authority_policy", "semantic_verifier", "calibration", "analysis"]


class SubmissionValidationTests(unittest.TestCase):
    def test_every_submission_schema_accepts_a_complete_bundle(self) -> None:
        self.assertEqual(common.validate_all_schemas(), [])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for role in ROLES:
                bundle = make_bundle(role, root)
                report = validator.validate_bundle_document(bundle, root)
                self.assertTrue(report["schema_valid"], (role, report))
                self.assertEqual(report["primary_status"], "independence_supported", (role, report))

    def test_custodian_attestation_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = make_bundle("task_oracle", Path(temporary))
            self.assertEqual(
                common.schema_errors(bundle["attestation"], common.BASE_SCHEMA_PATH), []
            )

    def test_digest_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("task_oracle", root)
            write_text(root / bundle["assets"][0]["path"], "changed after seal\n")
            report = validator.validate_bundle_document(bundle, root)
            self.assertTrue(report["rejected"])
            self.assertTrue(any("digest_mismatch" in value for value in report["errors"]))

    def test_manifest_seal_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("authority_policy", root)
            bundle["seal"]["manifest_sha256"] = "0" * 64
            report = validator.validate_bundle_document(bundle, root)
            self.assertIn("seal:manifest_digest_mismatch", report["errors"])

    def test_path_traversal_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("analysis", root)
            bundle["assets"][0]["path"] = "../escape.json"
            reseal(bundle)
            report = validator.validate_bundle_document(bundle, root)
            self.assertTrue(report["rejected"])
            self.assertFalse(report["schema_valid"])

    def test_undeclared_dependency_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("task_oracle", root)
            bundle["observed_dependencies"].append({
                "bundle_id": "hidden-dependency", "custodian_role": "authority_policy", "purpose": "undeclared"
            })
            reseal(bundle)
            report = validator.validate_bundle_document(bundle, root)
            self.assertTrue(any("undeclared_dependencies" in value for value in report["errors"]))

    def test_undeclared_dependency_marker_in_asset_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("task_oracle", root)
            asset_path = root / bundle["assets"][0]["path"]
            write_text(asset_path, "d1a-dependency:hidden-bundle\n")
            bundle["assets"][0]["sha256"] = common.sha256_path(asset_path)
            reseal(bundle)
            report = validator.validate_bundle_document(bundle, root)
            self.assertTrue(any("undeclared_asset_dependency_markers" in value for value in report["errors"]))

    def test_role_information_barriers_reject_prohibited_tokens(self) -> None:
        tokens = {
            "task_oracle": "perturbation_assignment",
            "authority_policy": "realized_correctness",
            "semantic_verifier": "heldout_oracle_labels",
            "calibration": "heldout_d1_outcomes",
            "analysis": "unsealed_heldout_results",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for role, token in tokens.items():
                bundle = make_bundle(role, root)
                asset_path = root / bundle["assets"][0]["path"]
                write_text(asset_path, token + "\n")
                bundle["assets"][0]["sha256"] = common.sha256_path(asset_path)
                reseal(bundle)
                report = validator.validate_bundle_document(bundle, root)
                self.assertTrue(any("prohibited_information_token" in value for value in report["errors"]), (role, report))

    def test_unversioned_post_seal_mutation_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("semantic_verifier", root)
            bundle["post_seal_mutations"] = [{"description": "changed"}]
            reseal(bundle)
            report = validator.validate_bundle_document(bundle, root)
            self.assertIn("seal:post_seal_mutation_requires_new_bundle", report["errors"])

    def test_schema_valid_declaration_is_not_automatic_independence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("calibration", root, independent=False)
            report = validator.validate_bundle_document(bundle, root)
            self.assertTrue(report["schema_valid"])
            self.assertFalse(report["rejected"])
            self.assertTrue(report["independence_not_established"])
            self.assertFalse(report["independence_supported"])

    def test_role_payload_path_must_be_in_asset_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("analysis", root)
            bundle["role_payload"]["analysis_plan_path"] = "unlisted.json"
            reseal(bundle)
            report = validator.validate_bundle_document(bundle, root)
            self.assertTrue(any("role_asset_references_not_in_manifest" in value for value in report["errors"]))

    def test_unsealed_bundle_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle("task_oracle", root)
            bundle["seal"] = {"status": "unsealed", "sealed_at": None, "manifest_sha256": None}
            report = validator.validate_bundle_document(bundle, root)
            self.assertIn("seal:bundle_not_sealed", report["errors"])


if __name__ == "__main__":
    unittest.main()

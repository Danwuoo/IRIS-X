from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from support import PACKAGE_ROOT, make_bundle, reseal, write_bundle


SCRIPTS = PACKAGE_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import assemble_d1a_bundle as assembly  # noqa: E402
import common  # noqa: E402
import evaluate_policies as policies  # noqa: E402
import qualify_instrument as qualification  # noqa: E402


ROLES = ["task_oracle", "authority_policy", "semantic_verifier", "calibration", "analysis"]


class QualificationTests(unittest.TestCase):
    def test_meta_qualification_passes_all_required_checks(self) -> None:
        result = qualification.qualify()
        self.assertEqual(result["status"], "PASS", result)
        self.assertTrue(all(result["checks"].values()), result)
        self.assertFalse(result["d1_empirical_qualification"])
        self.assertEqual(result["terminal_readiness_state"], "ready_for_independent_custodian_submission")

    def test_coherent_r1_r2_r3_r4_r5_regions(self) -> None:
        checks = qualification.qualify()["checks"]
        for rival in ("R1", "R2", "R3", "R4", "R5"):
            self.assertTrue(checks[f"{rival}_win_region"])

    def test_record_only_r3_has_no_action_benefit(self) -> None:
        episodes, _ = qualification.load_meta()
        record = next(row for row in episodes if row["episode_id"] == "r3-record-only-resolution")
        self.assertTrue(record["meta"]["audit_resolution_improved"])
        self.assertFalse(record["commitment_record"]["consequential_action_exposed"])
        self.assertEqual(record["action_outcome"], "not_applicable")

    def test_deterministic_rerun_identity(self) -> None:
        episodes, calibration = qualification.load_meta()
        first = policies.evaluate_batch(episodes, calibration)
        second = policies.evaluate_batch(episodes, calibration)
        self.assertEqual(common.canonical_json_bytes(first), common.canonical_json_bytes(second))

    def test_absent_submissions_expose_next_state_without_fabrication(self) -> None:
        result = assembly.assemble(None, meta_qualified=True)
        self.assertEqual(result["state"], "ready_for_independent_custodian_submission")
        self.assertEqual(result["fabricated_assets"], 0)
        self.assertFalse(result["ready_for_d1a_qualification"])

    def test_incomplete_independent_assets_fail_assembly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_bundle(root, make_bundle("task_oracle", root))
            result = assembly.assemble(root, meta_qualified=True)
            self.assertEqual(result["state"], "independent_assets_incomplete")
            self.assertIn("semantic_verifier", result["missing_roles"])
            self.assertEqual(result["fabricated_assets"], 0)

    def test_explicit_p0_unavailable_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundles = {role: make_bundle(role, root) for role in ROLES}
            calibration = bundles["calibration"]
            calibration["role_payload"]["calibration_status"] = "P0_unavailable"
            calibration["role_payload"]["sample_size"] = 0
            calibration["role_payload"]["unavailability_reason"] = "no fair exact-configuration score"
            reseal(calibration)
            component_ids = [bundles[role]["bundle_id"] for role in ROLES if role != "analysis"]
            bundles["analysis"]["declared_dependencies"] = [
                {"bundle_id": bundles[role]["bundle_id"], "custodian_role": role, "purpose": "sealed component"}
                for role in ROLES if role != "analysis"
            ]
            reseal(bundles["analysis"])
            for bundle in bundles.values():
                write_bundle(root, bundle)
            result = assembly.assemble(root, meta_qualified=True)
            self.assertEqual(result["state"], "calibration_unavailable", result)
            self.assertFalse(result["ready_for_d1a_qualification"])

    def test_declared_but_unsupported_independence_blocks_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundles = {role: make_bundle(role, root) for role in ROLES}
            bundles["semantic_verifier"]["attestation"]["independent_authorship_claim"] = False
            reseal(bundles["semantic_verifier"])
            bundles["analysis"]["declared_dependencies"] = [
                {"bundle_id": bundles[role]["bundle_id"], "custodian_role": role, "purpose": "sealed component"}
                for role in ROLES if role != "analysis"
            ]
            reseal(bundles["analysis"])
            for bundle in bundles.values():
                write_bundle(root, bundle)
            result = assembly.assemble(root, meta_qualified=True)
            self.assertEqual(result["state"], "independence_not_established", result)

    def test_complete_distinct_bundles_can_reach_qualification_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundles = {role: make_bundle(role, root) for role in ROLES}
            bundles["analysis"]["declared_dependencies"] = [
                {"bundle_id": bundles[role]["bundle_id"], "custodian_role": role, "purpose": "sealed component"}
                for role in ROLES if role != "analysis"
            ]
            reseal(bundles["analysis"])
            for bundle in bundles.values():
                write_bundle(root, bundle)
            result = assembly.assemble(root, meta_qualified=True)
            self.assertEqual(result["state"], "ready_for_d1a_qualification", result)
            self.assertTrue(result["ready_for_d1a_qualification"])
            self.assertFalse(result["d1b_authorized"])

    def test_analysis_dependency_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundles = {role: make_bundle(role, root) for role in ROLES}
            bundles["analysis"]["declared_dependencies"] = [
                {"bundle_id": "wrong-component", "custodian_role": "task_oracle", "purpose": "wrong"}
            ]
            reseal(bundles["analysis"])
            for bundle in bundles.values():
                write_bundle(root, bundle)
            result = assembly.assemble(root, meta_qualified=True)
            self.assertEqual(result["state"], "rejected", result)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest

from support import PACKAGE_ROOT


SCRIPTS = PACKAGE_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import common  # noqa: E402
import evaluate_policies as policies  # noqa: E402
import qualify_instrument as qualification  # noqa: E402


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.episodes, cls.calibration = qualification.load_meta()
        cls.by_id = {row["episode_id"]: row for row in cls.episodes}
        cls.evaluation = policies.evaluate_batch(cls.episodes, cls.calibration)
        cls.rows = {row["episode_id"]: row for row in cls.evaluation["evaluated_episodes"]}

    def decision(self, case_id: str, policy_id: str) -> dict[str, str]:
        return self.rows[case_id]["decisions"][policy_id]

    def test_forbidden_field_access_is_enforced(self) -> None:
        view = policies.GuardedEpisode(self.by_id["control-no-authority"], {"producer_claim"})
        with self.assertRaises(policies.ForbiddenFieldAccess):
            view.get("authority_mapping")

    def test_policy_contract_allowed_and_forbidden_fields_are_disjoint(self) -> None:
        for policy_id, contract in policies.POLICY_CONTRACTS.items():
            self.assertFalse(set(contract["allowed_fields"]) & set(contract["forbidden_fields"]), policy_id)
            accessed = set(self.rows["control-no-warrant-increment"]["field_access"][policy_id])
            self.assertTrue(accessed <= set(contract["allowed_fields"]), policy_id)

    def test_missing_calibration_makes_p0_unavailable(self) -> None:
        decision, accessed = policies.run_policy("P0", self.by_id["control-no-authority"], None)
        self.assertEqual(decision, {"decision": "abstain", "reason": "P0_unavailable"})
        self.assertEqual(accessed, [])

    def test_no_authority_p3_equals_p2_bit_for_bit(self) -> None:
        self.assertEqual(self.decision("control-no-authority", "P3"), self.decision("control-no-authority", "P2"))

    def test_no_warrant_increment_all_equal(self) -> None:
        self.assertEqual(
            self.decision("control-no-warrant-increment", "P1"),
            self.decision("control-no-warrant-increment", "P2"),
        )
        self.assertEqual(
            self.decision("control-no-warrant-increment", "P2"),
            self.decision("control-no-warrant-increment", "P3"),
        )

    def test_evidence_volume_invariance(self) -> None:
        for policy_id in ("P2", "P3"):
            self.assertEqual(
                self.decision("control-evidence-volume-base", policy_id),
                self.decision("control-evidence-volume-extra", policy_id),
            )

    def test_outcome_fixed_authority_changes_only_authority_consumer(self) -> None:
        canonical = self.by_id["control-authority-canonical"]
        unauthorized = self.by_id["control-authority-unauthorized"]
        self.assertEqual(canonical["actual_outcome"], unauthorized["actual_outcome"])
        self.assertEqual(canonical["action_outcome"], unauthorized["action_outcome"])
        self.assertEqual(canonical["producer_output_digest"], unauthorized["producer_output_digest"])
        self.assertEqual(canonical["meta"]["semantic_input_digest"], unauthorized["meta"]["semantic_input_digest"])
        self.assertEqual(canonical["meta"]["raw_outcome_digest"], unauthorized["meta"]["raw_outcome_digest"])
        for policy_id in ("P0", "P1", "P2"):
            self.assertEqual(self.decision(canonical["episode_id"], policy_id), self.decision(unauthorized["episode_id"], policy_id))
        self.assertNotEqual(self.decision(canonical["episode_id"], "P3"), self.decision(unauthorized["episode_id"], "P3"))

    def test_verifier_false_accept_false_reject_error_and_unknown(self) -> None:
        self.assertEqual(self.by_id["control-verifier-false-accept"]["actual_outcome"], "failure")
        self.assertEqual(self.by_id["control-verifier-false-accept"]["semantic_verifier_decision"], "accept")
        self.assertEqual(self.by_id["control-verifier-false-reject"]["actual_outcome"], "success")
        self.assertEqual(self.by_id["control-verifier-false-reject"]["semantic_verifier_decision"], "reject")
        self.assertEqual(self.by_id["control-verifier-error"]["semantic_verifier_decision"], "error")
        self.assertEqual(self.by_id["control-verifier-unknown"]["semantic_verifier_decision"], "unknown")

    def test_unknown_is_preserved_in_outcome_vector(self) -> None:
        for policy_id in ("P0", "P1", "P2", "P3"):
            vector = self.evaluation["outcome_vectors"][policy_id]["all"]
            self.assertGreater(vector["actual_task"]["unknown"]["count"], 0)
            self.assertEqual(vector["resources"]["human_manual_cost"]["value"], "unknown")
            self.assertEqual(vector["resources"]["latency_ms"]["value"], "unknown")

    def test_complete_vector_has_explicit_denominators_and_family_strata(self) -> None:
        metric_keys = [
            "false_commitment_actual", "false_commitment_action", "false_rejection",
            "unverified_success", "abstention", "authorization_error", "invalid_record_count"
        ]
        for policy_id in ("P0", "P1", "P2", "P3"):
            policy = self.evaluation["outcome_vectors"][policy_id]
            self.assertGreaterEqual(len(policy["task_families"]), 2)
            for stratum in [policy["all"], *policy["task_families"].values()]:
                for key in metric_keys:
                    self.assertIn("denominator", stratum[key])
                for key in ("agreement", "disagreement", "false_accept", "false_reject", "error", "unknown"):
                    self.assertIn("denominator", stratum["verifier"][key])

    def test_no_primary_scalar_and_weighted_loss_disabled(self) -> None:
        self.assertEqual(self.evaluation["primary_scalar_score"], "not_authorized")
        self.assertFalse(self.evaluation["weighted_loss_enabled"])

    def test_provider_calls_and_retries_are_zero(self) -> None:
        for policy_id in ("P0", "P1", "P2", "P3"):
            resources = self.evaluation["outcome_vectors"][policy_id]["all"]["resources"]
            self.assertEqual(resources["provider_model_calls"]["value"], 0)
            self.assertEqual(resources["retries"]["value"], 0)

    def test_policy_resource_accounting_follows_consumed_components(self) -> None:
        vectors = self.evaluation["outcome_vectors"]
        self.assertLess(
            vectors["P0"]["all"]["resources"]["verification"]["value"],
            vectors["P1"]["all"]["resources"]["verification"]["value"],
        )
        self.assertLess(
            vectors["P1"]["all"]["resources"]["verification"]["value"],
            vectors["P2"]["all"]["resources"]["verification"]["value"],
        )
        self.assertGreater(
            vectors["P3"]["all"]["resources"]["factorized_components"]["authority_adjudication"]["value"],
            0,
        )

    def test_adjudication_reproducibility_is_explicit(self) -> None:
        for policy_id in ("P0", "P1", "P2", "P3"):
            record = self.evaluation["outcome_vectors"][policy_id]["all"]["adjudication_reproducibility"]
            self.assertTrue(record["deterministic_rerun_equal"])
            self.assertEqual(record["episode_denominator"], len(self.episodes))


if __name__ == "__main__":
    unittest.main()

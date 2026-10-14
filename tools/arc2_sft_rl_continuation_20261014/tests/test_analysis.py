"""Synthetic full-shape JSON contracts, never actual experiment results."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("continuation_analysis", Path(__file__).resolve().parents[1] / "analysis.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
analyze_report = MODULE.analyze_report


def scores(scope, counts):
    denominator = 16 if scope == "dev" else 32
    return {arm: {"exact": count, "denominator": denominator,
                  "exact_case_ids": [f"{scope}:synthetic-{i:02d}" for i in range(count)],
                  "prediction_file_bound": True} for arm, count in zip("ABC", counts)}


def report():
    """Small fabricated reports with real consumer field names and full shape."""
    groups = [{"parent_id": f"synthetic-parent-{i}", "planned": 8, "eligible": 8,
               "successes": 4, "mixed": True, "all_zero": False, "all_one": False,
               "pass_at_8": 1, "fixture_full_group_success": 1} for i in range(32)]
    held = scores("holdout", (5, 8, 7))
    base = set(held["A"]["exact_case_ids"])
    paired = {arm: {"gained_case_ids": sorted(set(held[arm]["exact_case_ids"]) - base),
                    "lost_case_ids": sorted(base - set(held[arm]["exact_case_ids"]))} for arm in ("B", "C")}
    return {
        "format": "irisx/owned-rl-offline-validation-v1",
        "status": "REVIEWED_PRODUCTION_CONTENT_COMPLETE", "provider_status": "COMPLETE",
        "evidence_valid": True, "diagnostic_evidence_valid": True,
        "authenticated_collection_verified": True, "external_owner_envelope_verified": True,
        "production_admitted": True, "operational_complete": True, "operational_success": True,
        "comparison_complete": True, "compute_matched": True, "comparison_eligible": True,
        "public_benchmark_evidence_eligible": True, "public_goal_met": False,
        "scientific_goal_met": False, "goal_met": False,
        "phase_status": {"owner_process_closed": True},
        "audit": {"planned_batches": 4, "physical_attempted_batches": 4, "planned_parents": 32,
                  "planned_attempts": 256, "committed_updates": 4, "all_zero_panel": False,
                  "full_panel_summary": {
                      "planned_attempts": 256, "actual_dispatched_attempts": 256,
                      "reward_eligible_attempts": 256, "infrastructure_exclusions": 0,
                      "context_exclusions": 0, "not_reached": 0, "complete": True,
                      "all_slots_reached": True, "mixed_groups": 32, "groups": groups,
                      "eligible_mean_reward": 0.5, "eligible_mean_denominator": 256,
                      "fatal_native_state": False}},
        "evaluation": {"selected_arm": "B", "dev_scores": scores("dev", (3, 5, 4)),
                       "holdout_scores": held, "paired_vs_A": paired, "comparison_complete": True},
        "metering": {"time_matching": {"B_seconds": 1000.0, "C_seconds": 1020.0,
                     "epsilon_seconds": 50.0, "matched": True,
                     "includes_failures_rollback_setup_save_reload_verification": True,
                     "clock": "whole-synchronized-model-phase-wall", "idle_padding": False}},
        "public": {"status": "SEALED_SCORER_ROWS_REPLAYED", "selected_arm": "B",
                   "scorer_rows_complete": True, "metric_threshold_reached": False,
                   "micro_pass_at_2": {"numerator": 20, "denominator": 167, "value": 20 / 167, "unit": "test"},
                   "coverage": {"planned_queries": 167, "observed_queries": 167,
                                "planned_views": 334, "observed_views": 334,
                                "actual_generation_calls": 334, "complete_prediction_coverage": True,
                                "deadline_exceeded": False, "query_targets_used": False}},
        "checkpoints": {"A": {"adapter_sha256": "a" * 64, "counts": {"anchor_updates": 256}},
                        "B": {"adapter_sha256": "b" * 64, "counts": {"rl_updates": 4}}},
    }


def constant_report(successes):
    r = report()
    audit = r["audit"]
    audit["committed_updates"] = 0
    audit["all_zero_panel"] = successes == 0
    s = audit["full_panel_summary"]
    s["eligible_mean_reward"] = successes / 8
    s["mixed_groups"] = 0
    for group in s["groups"]:
        group.update(successes=successes, mixed=False, all_zero=successes == 0, all_one=successes == 8)
    r["checkpoints"]["B"] = {"adapter_sha256": "a" * 64, "counts": {"rl_updates": 0}}
    for scope in ("dev_scores", "holdout_scores"):
        r["evaluation"][scope]["B"] = deepcopy(r["evaluation"][scope]["A"])
    r["evaluation"]["paired_vs_A"]["B"] = {"gained_case_ids": [], "lost_case_ids": []}
    r["evaluation"]["selected_arm"] = r["public"]["selected_arm"] = "C"
    return r


class AnalysisTests(unittest.TestCase):
    def issue(self, data, code):
        result = analyze_report(data)
        self.assertIn(code, result["issues"])
        self.assertFalse(result["analysis_authenticated"])
        self.assertFalse(result["dispatch_authorized"])
        return result

    def test_full_shape_counts_are_conditional_not_authenticated(self):
        result = analyze_report(report())
        self.assertTrue(result["structurally_consistent"])
        self.assertFalse(result["analysis_authenticated"])
        self.assertFalse(result["dispatch_authorized"])
        self.assertFalse(result["method_efficacy_established"])
        self.assertFalse(result["comparison"]["case_universe_verified"])
        self.assertFalse(result["comparison"]["paired_comparison_qualified"])
        self.assertEqual(result["comparison"]["paired_deltas"]["B_minus_C"]["net"], 1)
        self.assertEqual(result["audit"]["signal_classification"], "mixed-groups-observed")
        self.assertIsNone(result["public"]["reported_task_count"])

    def test_deterministic_no_mutation_and_no_ids(self):
        data = report()
        original = deepcopy(data)
        one, two = analyze_report(data), analyze_report(data)
        self.assertEqual(one, two)
        self.assertEqual(data, original)
        serialized = json.dumps(one, allow_nan=False)
        self.assertNotIn("synthetic-parent", serialized)
        self.assertNotIn("synthetic-00", serialized)
        self.assertNotIn("exact_case_ids", serialized)

    def test_missing_scores_stay_null(self):
        result = analyze_report({"status": "STOPPED_INCOMPLETE", "provider_status": "ERROR"})
        self.assertIsNone(result["public"]["micro_pass_at_2"])
        self.assertIsNone(result["comparison"]["holdout"])
        self.assertIsNone(result["audit"]["counts"])
        self.assertIsNone(result["time_matching"]["derived_matched"])

    def test_private_errors_are_not_copied(self):
        result = analyze_report({"status": "secret-status", "error": "private-error-content",
                                 "errors": ["private-error-content"], "provider_status": "secret-provider"})
        text = json.dumps(result)
        self.assertNotIn("private-error-content", text)
        self.assertNotIn("secret-status", text)
        self.assertNotIn("secret-provider", text)

    def test_bad_root(self):
        self.issue([], "REPORT_NOT_OBJECT")

    def test_duplicate_hitset_rejected(self):
        r = report(); r["evaluation"]["dev_scores"]["A"]["exact_case_ids"][1] = "dev:synthetic-00"
        self.assertIsNone(self.issue(r, "DEV_HITSET_DUPLICATE")["comparison"]["dev"])

    def test_wrong_scope_hitset_rejected(self):
        r = report(); r["evaluation"]["holdout_scores"]["A"]["exact_case_ids"][0] = "dev:synthetic-00"
        self.issue(r, "HOLDOUT_HITSET_INVALID")

    def test_count_hitset_disagreement_rejected(self):
        r = report(); r["evaluation"]["dev_scores"]["A"]["exact"] = 4
        self.issue(r, "DEV_HITSET_INVALID")

    def test_bool_is_not_score_count(self):
        r = report(); r["evaluation"]["dev_scores"]["A"]["exact"] = True
        self.issue(r, "DEV_SCORE_COUNTS_INVALID")

    def test_fixed_denominator_not_shrunk(self):
        r = report(); r["evaluation"]["holdout_scores"]["B"]["denominator"] = 31
        self.issue(r, "HOLDOUT_SCORE_COUNTS_INVALID")

    def test_tie_prefers_A(self):
        r = report(); r["evaluation"]["dev_scores"] = scores("dev", (5, 5, 5))
        self.issue(r, "DEV_SELECTION_OR_TIE_RULE_INCONSISTENT")
        r["evaluation"]["selected_arm"] = r["public"]["selected_arm"] = "A"
        self.assertTrue(analyze_report(r)["comparison"]["dev_selection_consistent"])

    def test_public_selected_arm(self):
        r = report(); r["public"]["selected_arm"] = "C"
        self.issue(r, "PUBLIC_SELECTED_ARM_INCONSISTENT")

    def test_paired_claim_disagreement(self):
        r = report(); r["evaluation"]["paired_vs_A"]["B"]["gained_case_ids"] = []
        result = self.issue(r, "PAIRED_VS_A_COUNTS_INCONSISTENT")
        self.assertIsNone(result["comparison"]["paired_deltas"])

    def test_hitsets_cannot_fit_common_denominator(self):
        r = report(); d = r["evaluation"]["dev_scores"]
        for j, arm in enumerate("ABC"):
            d[arm]["exact"] = 10
            d[arm]["exact_case_ids"] = [f"dev:arm{j}-{i}" for i in range(10)]
        self.issue(r, "DEV_HITSET_UNION_EXCEEDS_DENOMINATOR")

    def test_partial_held_null_is_honest(self):
        r = report(); r["comparison_complete"] = r["comparison_eligible"] = False
        r["evaluation"].update(comparison_complete=False, holdout_scores=None, paired_vs_A=None)
        result = analyze_report(r)
        self.assertTrue(result["structurally_consistent"])
        self.assertIsNone(result["comparison"]["paired_deltas"])

    def test_partial_held_cannot_have_scores(self):
        r = report(); r["comparison_complete"] = False
        self.issue(r, "INCOMPLETE_COMPARISON_HAS_HELD_SCORES")

    def test_complete_comparison_requires_scores(self):
        r = report(); r["evaluation"]["holdout_scores"] = None
        self.issue(r, "COMPLETE_COMPARISON_MISSING_VALID_SCORES")

    def test_complete_zero_and_one_audits(self):
        for n, expected in ((0, "complete-all-zero-groups"), (8, "complete-all-one-groups")):
            with self.subTest(n=n):
                result = analyze_report(constant_report(n))
                self.assertTrue(result["structurally_consistent"])
                self.assertEqual(result["audit"]["signal_classification"], expected)

    def test_partial_zero_is_not_zero_signal(self):
        r = constant_report(0); a = r["audit"]; s = a["full_panel_summary"]
        a.update(physical_attempted_batches=1, all_zero_panel=False)
        s.update(actual_dispatched_attempts=64, reward_eligible_attempts=64, not_reached=192,
                 eligible_mean_denominator=64, complete=False, all_slots_reached=False)
        for group in s["groups"][8:]:
            group.update(eligible=0, all_zero=False)
        result = self.issue(r, "PARTIAL_AUDIT_CANNOT_ESTABLISH_ZERO_SIGNAL")
        self.assertEqual(result["audit"]["signal_classification"], "partial-audit-not-zero-signal")
        a["all_zero_panel"] = True
        self.issue(r, "AUDIT_ALL_ZERO_DECLARATION_INCONSISTENT")

    def test_exclusions_retained_without_zero_reward_inference(self):
        r = constant_report(0); a = r["audit"]; s = a["full_panel_summary"]
        a["all_zero_panel"] = False
        s.update(actual_dispatched_attempts=255, reward_eligible_attempts=254,
                 infrastructure_exclusions=1, context_exclusions=1,
                 eligible_mean_denominator=254, complete=False)
        s["groups"][-1].update(eligible=6, all_zero=False)
        result = self.issue(r, "PARTIAL_AUDIT_CANNOT_ESTABLISH_ZERO_SIGNAL")
        self.assertEqual(result["audit"]["counts"]["infrastructure_exclusions"], 1)

    def test_audit_count_partition(self):
        r = report(); r["audit"]["full_panel_summary"]["not_reached"] = 1
        self.issue(r, "AUDIT_COUNTS_INVALID")

    def test_audit_duplicate_parent(self):
        r = report(); gs = r["audit"]["full_panel_summary"]["groups"]
        gs[1]["parent_id"] = gs[0]["parent_id"]
        self.issue(r, "AUDIT_GROUP_INVALID_OR_DUPLICATE")

    def test_audit_flags_cannot_fabricate_mixed(self):
        r = report(); r["audit"]["full_panel_summary"]["groups"][0]["mixed"] = False
        self.issue(r, "AUDIT_GROUP_FLAGS_INCONSISTENT")

    def test_audit_mean_inconsistent(self):
        r = report(); r["audit"]["full_panel_summary"]["eligible_mean_reward"] = 0
        self.issue(r, "AUDIT_GROUP_AGGREGATE_INCONSISTENT")

    def test_fatal_state_cannot_be_zero_signal(self):
        r = constant_report(0); r["audit"]["full_panel_summary"]["fatal_native_state"] = True
        result = self.issue(r, "AUDIT_FATAL_NATIVE_STATE_DECLARED")
        self.assertEqual(result["audit"]["signal_classification"], "unknown")

    def test_no_update_adapter_must_equal_A(self):
        r = constant_report(0); r["checkpoints"]["B"]["adapter_sha256"] = "c" * 64
        self.issue(r, "NO_UPDATE_B_ADAPTER_DIFFERS_FROM_A")

    def test_no_update_same_counts_different_dev_hits_detected(self):
        r = constant_report(0); r["evaluation"]["dev_scores"]["B"]["exact_case_ids"][0] = "dev:synthetic-15"
        self.issue(r, "NO_UPDATE_B_DETERMINISTIC_HITSETS_DIFFER")

    def test_checkpoint_audit_update_disagreement(self):
        r = report(); r["checkpoints"]["B"]["counts"]["rl_updates"] = 3
        self.issue(r, "CHECKPOINT_AUDIT_UPDATE_COUNTS_DIFFER")

    def test_whole_wall_tolerance_fixed(self):
        r = report(); r["metering"]["time_matching"]["epsilon_seconds"] = 100
        self.issue(r, "WHOLE_WALL_CONTRACT_INVALID")

    def test_unmatched_wall_is_not_invalid(self):
        r = report(); r["metering"]["time_matching"].update(C_seconds=1100, matched=False)
        r["compute_matched"] = r["comparison_eligible"] = False
        result = analyze_report(r)
        self.assertTrue(result["structurally_consistent"])
        self.assertFalse(result["time_matching"]["derived_matched"])

    def test_idle_padding_invalid(self):
        r = report(); r["metering"]["time_matching"]["idle_padding"] = True
        self.issue(r, "WHOLE_WALL_CONTRACT_INVALID")

    def test_nan_and_huge_integer_do_not_raise(self):
        for value in (float("nan"), float("inf"), 10 ** 1000, True):
            with self.subTest(kind=type(value)):
                r = report(); r["metering"]["time_matching"]["B_seconds"] = value
                result = self.issue(r, "WHOLE_WALL_INTERVAL_INVALID")
                json.dumps(result, allow_nan=False)

    def test_public_original_denominator(self):
        r = report(); r["public"]["micro_pass_at_2"]["denominator"] = 120
        result = self.issue(r, "PUBLIC_ORIGINAL_DENOMINATOR_METRIC_INVALID")
        self.assertIsNone(result["public"]["micro_pass_at_2"])

    def test_public_partial_generation_keeps_original_denominator(self):
        r = report(); r["public"]["coverage"].update(actual_generation_calls=100, complete_prediction_coverage=False)
        result = analyze_report(r)
        self.assertTrue(result["structurally_consistent"])
        self.assertEqual(result["public"]["micro_pass_at_2"]["denominator"], 167)

    def test_public_threshold_does_not_authenticate_or_promote(self):
        r = report(); r["public"]["micro_pass_at_2"].update(numerator=151, value=151 / 167)
        r["public"]["metric_threshold_reached"] = True
        r["public_goal_met"] = r["scientific_goal_met"] = r["goal_met"] = True
        result = analyze_report(r)
        self.assertTrue(result["public"]["derived_threshold_reached"])
        self.assertFalse(result["analysis_authenticated"])
        self.assertFalse(result["method_efficacy_established"])

    def test_provider_ERROR_does_not_erase_reported_scientific_score(self):
        r = report(); r.update(provider_status="ERROR", operational_success=False, operational_complete=False)
        result = analyze_report(r)
        self.assertEqual(result["public"]["micro_pass_at_2"]["numerator"], 20)
        self.assertFalse(result["declared_axes"]["operational_success"])

    def test_provider_COMPLETE_does_not_create_score(self):
        result = analyze_report({"status": "INCOMPLETE_DIAGNOSTIC_EVIDENCE", "provider_status": "COMPLETE"})
        self.assertIsNone(result["public"]["micro_pass_at_2"])
        self.assertFalse(result["method_efficacy_established"])

    def test_boolean_axes_strict(self):
        r = report(); r["production_admitted"] = 1
        result = self.issue(r, "DECLARED_AXIS_TYPE_INVALID")
        self.assertIsNone(result["declared_axes"]["production_admitted"])


if __name__ == "__main__":
    unittest.main()

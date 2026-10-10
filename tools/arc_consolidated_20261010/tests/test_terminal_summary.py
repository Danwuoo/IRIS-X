"""Synthetic bounded-display regressions; no actual model/GPU acceptance."""
import copy
import json
import unittest

from tools.arc_consolidated_20261010 import terminal_summary as terminal


def result_fixture():
    return {"status": "complete", "output_root": "/synthetic/run", "session_id": "a" * 32,
            "archive": {"archive": "/synthetic/run/archives/evidence.zip", "sha256": "b" * 64},
            "report": {"profile": "FULL", "source_sha256": "c" * 64,
                       "gate": {"passed": True}, "controls": {"all_expected": True},
                       "coverage": {"complete": True, "tasks": []},
                       "model": {"status": "complete", "planned_denominator": 80},
                       "processes": {"model_owner_stopped": True, "verifier_descendants_stopped": True},
                       "final_accounting": {"charged": {"cpu_checks": 52536,
                           "coverage_checks": 47848, "physical_calls": 79}}}}


class NoRepresentation:
    def __repr__(self):
        raise AssertionError("must not repr a full result or arbitrary field")

    __str__ = __repr__


class TerminalSummaryTests(unittest.TestCase):
    def summary(self, value):
        text = terminal.render(value)
        self.assertLessEqual(len(text.encode("ascii")) + 1, terminal.MAX_SUMMARY_BYTES)
        return json.loads(text)

    def test_full_success_reports_charged_calls_gate_paths_hash_and_stop(self):
        summary = self.summary(result_fixture())
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["profile"], "FULL")
        self.assertIs(summary["gate_passed"], True)
        self.assertEqual(summary["cpu_checks_charged"], 52536)
        self.assertEqual(summary["coverage_checks_charged"], 47848)
        self.assertEqual(summary["model_calls_charged"], 79)
        self.assertEqual(summary["report_path"], "/synthetic/run/stages/summary-" + "a" * 32 + ".json")
        self.assertEqual(summary["archive_sha256"], "b" * 64)
        self.assertIs(summary["model_owner_stopped"], True)
        self.assertIs(summary["verifier_descendants_stopped"], True)
        self.assertIn("do not stop VM billing", summary["billing"])

    def test_nested_model_failure_shows_exact_cause_and_zero_calls(self):
        result = result_fixture()
        result["status"] = "partial-inconclusive"
        result["report"]["model"] = {"status": "partial", "error": {
            "type": "ModelContractError", "message": "empty or invalid native token IDs"}}
        result["report"]["final_accounting"]["charged"]["physical_calls"] = 0
        summary = self.summary(result)
        self.assertIs(summary["gate_passed"], True)
        self.assertEqual(summary["model_calls_charged"], 0)
        self.assertEqual(summary["model_error"], result["report"]["model"]["error"])
        self.assertEqual(summary["workflow_error"], {"type": None, "message": None})

    def test_withheld_archive_and_unconfirmed_stop_are_not_success(self):
        result = result_fixture()
        result["status"] = "partial-inconclusive"
        result["archive"] = None
        result["report"]["global_seal"] = "withheld: owned resource stop is unconfirmed"
        result["report"]["processes"]["model_owner_stopped"] = False
        summary = self.summary(result)
        self.assertIs(summary["model_owner_stopped"], False)
        self.assertIsNone(summary["archive_path"])
        self.assertIsNone(summary["archive_sha256"])
        self.assertEqual(summary["global_seal"], result["report"]["global_seal"])

    def test_resumed_noop_ledger_shape_keeps_missing_prior_facts_unknown(self):
        summary = self.summary({"status": "complete", "resumed_noop": True,
            "output_root": "/synthetic/existing", "archive": None,
            "report": {"state": "complete", "charged": {"cpu_checks": 47848, "physical_calls": 0}}})
        self.assertIs(summary["resumed_noop"], True)
        self.assertEqual(summary["cpu_checks_charged"], 47848)
        self.assertEqual(summary["model_calls_charged"], 0)
        for key in ("gate_passed", "profile", "report_path", "archive_path", "model_owner_stopped"):
            self.assertIsNone(summary[key])

    def test_inactive_or_malformed_result_remains_bounded_without_invented_counts(self):
        for result in ({"status": "INACTIVE"}, None, NoRepresentation(), {"report": [1]}):
            summary = self.summary(result)
            self.assertIsNone(summary["cpu_checks_charged"])
            self.assertIsNone(summary["model_calls_charged"])

    def test_full_result_and_deep_rows_untouched_and_never_serialized(self):
        result = result_fixture()
        result["report"]["coverage"]["tasks"] = [NoRepresentation()] * 100000
        result["report"]["model"]["rows"] = [NoRepresentation()] * 100000
        rows = result["report"]["coverage"]["tasks"]
        self.summary(result)
        self.assertIs(result["report"]["coverage"]["tasks"], rows)
        self.assertEqual(len(rows), 100000)
        simple = result_fixture()
        before = copy.deepcopy(simple)
        self.summary(simple)
        self.assertEqual(simple, before)

    def test_adversarial_strings_have_fixed_encoded_byte_bound(self):
        result = result_fixture()
        huge = "\U0001f9ea\ud800\n\x00" * 200000
        result.update(status=huge, output_root=huge, session_id=huge,
                      archive={"archive": huge, "sha256": huge})
        result["report"].update(profile=huge, source_sha256=huge, global_seal=huge,
            error={"type": huge, "message": huge},
            model={"status": huge, "error": {"type": huge, "message": huge}})
        summary = self.summary(result)
        self.assertNotEqual(summary["status"], "summary_limit_exceeded")
        self.assertIn("[truncated]", summary["model_error"]["message"])
        self.assertIsNone(summary["archive_sha256"])
        self.assertIsNone(summary["report_path"])

    def test_invalid_counters_flags_and_scalar_objects_are_not_coerced(self):
        result = result_fixture()
        result["report"]["final_accounting"]["charged"].update(
            cpu_checks=True, coverage_checks=10**10000, physical_calls=1.5)
        result["report"]["gate"]["passed"] = 1
        result["report"]["model"]["error"] = {"type": NoRepresentation(), "message": NoRepresentation()}
        summary = self.summary(result)
        for key in ("cpu_checks_charged", "coverage_checks_charged", "model_calls_charged", "gate_passed"):
            self.assertIsNone(summary[key])
        self.assertEqual(summary["model_error"], {"type": None, "message": None})

    def test_partial_ledger_fallback_preserves_workflow_error(self):
        result = result_fixture()
        result["report"]["ledger"] = result["report"].pop("final_accounting")
        result["report"]["error"] = {"type": "RuntimeError", "message": "synthetic failure"}
        summary = self.summary(result)
        self.assertEqual(summary["workflow_error"], result["report"]["error"])
        self.assertEqual(summary["model_calls_charged"], 79)


if __name__ == "__main__":
    unittest.main()

"""R2 constant-only cost receipt controls; no model/Lean/provider execution."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import validate_model_cost
from controller import execute_arm
import controls as control_fixtures
from controls import ScriptedModel, ScriptedVerifier
from analyze import analyze, generation_observed
from model_adapter import GenerationTimeout

VALID = {"prompt_tokens": 7, "output_tokens": 5, "wall_seconds": 0.125}


class CostSchemaControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        control_fixtures.Controls.setUpClass()

    def setUp(self):
        self.fixture = control_fixtures.Controls(methodName="runTest")
        self.fixture.setUp()

    def summary(self, cost, *, claimed=True, cached=None, event_status="generated"):
        event = {"status": event_status, "model_text": "scripted text", "model_cost": copy.deepcopy(cost),
                 "model_cost_complete": claimed, "model_cost_validation": cached,
                 "tool_attempted": False}
        row = self.fixture.row(events=[event])
        return analyze(self.fixture.panel, [row], [0], self.fixture.identities)["arms"]["M-DIRECT"]

    def execute(self, cost=None, *, error=None):
        response = {"text": json.dumps({"answer": None, "proof_body": "by\n  trivial"}),
                    "stop_reason": "eos", "cost": cost}
        model = ScriptedModel(response=response, error=error)
        f = self.fixture
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "arm"
            row = execute_arm(f.problem, "M-DIRECT", 0, model, ScriptedVerifier(), f.protocol,
                              output, f.identities, panel=f.panel, source_files=f.source_files,
                              execution_manifest=f.manifest)
            saved = json.loads((output / "candidate-0.json").read_text())
        return row, saved

    def test_complete_minimal_positive(self):
        checked = validate_model_cost(VALID)
        self.assertTrue(checked["complete"])
        self.assertEqual(checked["issues"], [])
        self.assertEqual(checked["observed_lower_bound"], VALID)
        self.assertTrue(self.summary(VALID)["cost_complete"])

    def test_complete_all_adapter_fields_positive(self):
        cost = dict(VALID, consumed_prompt_tokens=7, partial=False, cold_compile_seconds=0,
                    cache_allocation_seconds=0.01, prefill_seconds=0.02, decode_seconds=0.03)
        self.assertTrue(validate_model_cost(cost)["complete"])
        self.assertTrue(self.summary(cost)["cost_complete"])

    def test_zero_counts_and_times_are_valid(self):
        self.assertTrue(validate_model_cost(dict.fromkeys(VALID, 0))["complete"])

    def test_each_missing_required_field_is_explicit(self):
        for key in VALID:
            with self.subTest(key=key):
                cost = {k: v for k, v in VALID.items() if k != key}
                checked = validate_model_cost(cost)
                self.assertFalse(checked["complete"])
                self.assertIn({"field": key, "reason": "missing"}, checked["issues"])
                self.assertFalse(self.summary(cost)["cost_complete"])

    def test_counts_reject_bool_fraction_negative_nonfinite_and_text(self):
        for key in ("prompt_tokens", "output_tokens", "consumed_prompt_tokens"):
            for value in (True, False, -1, 1.5, 7.0, float("nan"), float("inf"), "7", None):
                with self.subTest(key=key, value=repr(value)):
                    checked = validate_model_cost(dict(VALID, **{key: value}))
                    self.assertFalse(checked["complete"])
                    self.assertNotIn(key, checked["observed_lower_bound"])
                    self.assertTrue(any(issue["field"] == key for issue in checked["issues"]))

    def test_times_reject_bool_negative_nonfinite_and_text(self):
        for key in ("wall_seconds", "cold_compile_seconds", "cache_allocation_seconds", "prefill_seconds", "decode_seconds"):
            for value in (True, -0.01, float("nan"), float("inf"), -float("inf"), "0.1", None, 10**1000):
                with self.subTest(key=key, value=repr(value)):
                    checked = validate_model_cost(dict(VALID, **{key: value}))
                    self.assertFalse(checked["complete"])
                    self.assertNotIn(key, checked["observed_lower_bound"])

    def test_partial_flag_requires_boolean(self):
        for value in (0, 1, None, "false"):
            with self.subTest(value=value):
                self.assertFalse(validate_model_cost(dict(VALID, partial=value))["complete"])

    def test_partial_valid_values_remain_lower_bounds(self):
        cost = dict(VALID, partial=True)
        checked = validate_model_cost(cost)
        self.assertFalse(checked["complete"])
        self.assertEqual(checked["observed_lower_bound"], VALID)
        summary = self.summary(cost)
        self.assertFalse(summary["cost_complete"])
        self.assertEqual(summary["observed_model_cost_lower_bound"], VALID)
        self.assertTrue(summary["model_cost_issues"][0]["partial"])

    def test_unknown_field_is_explicit_not_summed(self):
        checked = validate_model_cost(dict(VALID, invented_seconds=1))
        self.assertFalse(checked["complete"])
        self.assertIn({"field": "invented_seconds", "reason": "unknown_field"}, checked["issues"])
        self.assertNotIn("invented_seconds", checked["observed_lower_bound"])

    def test_non_object_receipts_are_incomplete(self):
        for cost in (None, [], "cost", True, 42):
            with self.subTest(cost=cost):
                self.assertFalse(validate_model_cost(cost)["complete"])
                self.assertFalse(self.summary(cost)["cost_complete"])

    def test_consumed_count_cannot_exceed_prompt(self):
        checked = validate_model_cost(dict(VALID, consumed_prompt_tokens=8))
        self.assertFalse(checked["complete"])
        self.assertNotIn("consumed_prompt_tokens", checked["observed_lower_bound"])

    def test_analyzer_rechecks_five_independent_review_counterexamples(self):
        examples = [dict(VALID, prompt_tokens=-1), dict(VALID, output_tokens=float("nan")),
                    dict(VALID, wall_seconds=-1), dict(VALID, prompt_tokens=True),
                    {k: v for k, v in VALID.items() if k != "output_tokens"}]
        for cost in examples:
            with self.subTest(cost=cost):
                summary = self.summary(cost, claimed=True, cached={"complete": True, "issues": []})
                self.assertFalse(summary["cost_complete"])
                self.assertEqual(summary["observed_execution_cost"]["incomplete_model_cost_receipts"], 1)
                self.assertTrue(summary["model_cost_issues"][0]["issues"])

    def test_producer_complete_flag_is_not_authoritative(self):
        self.assertTrue(self.summary(VALID, claimed=False, cached={"complete": False})["cost_complete"])
        self.assertFalse(self.summary({}, claimed=True, cached={"complete": True})["cost_complete"])

    def test_controller_ingestion_preserves_invalid_raw_values(self):
        examples = [dict(VALID, prompt_tokens=-1), dict(VALID, output_tokens=float("nan")),
                    dict(VALID, wall_seconds=-1), dict(VALID, prompt_tokens=True),
                    {k: v for k, v in VALID.items() if k != "output_tokens"}]
        for cost in examples:
            with self.subTest(cost=cost):
                row, saved = self.execute(cost)
                self.assertEqual(row["status"], "proof_accepted")
                event = row["events"][0]
                self.assertFalse(event["model_cost_complete"])
                self.assertFalse(saved["model_cost_complete"])
                self.assertTrue(saved["model_cost_validation"]["issues"])
                for key, value in cost.items():
                    if isinstance(value, float) and math.isnan(value):
                        self.assertTrue(math.isnan(saved["model_cost"][key]))
                    else:
                        self.assertEqual(saved["model_cost"][key], value)

    def test_controller_valid_cost_positive(self):
        row, saved = self.execute(VALID)
        self.assertTrue(saved["model_cost_complete"])
        self.assertEqual(row["status"], "proof_accepted")

    def test_timeout_cost_is_partial_even_without_flag(self):
        row, saved = self.execute(error=GenerationTimeout("synthetic timeout", cost=VALID, phase="prefill"))
        self.assertEqual(saved["status"], "timeout")
        self.assertFalse(saved["model_cost_complete"])
        summary = analyze(self.fixture.panel, [row], [0], self.fixture.identities)["arms"]["M-DIRECT"]
        self.assertFalse(summary["cost_complete"])
        self.assertEqual(summary["observed_model_cost_lower_bound"], VALID)

    def test_valid_parts_survive_mixed_invalid_receipt(self):
        summary = self.summary({"prompt_tokens": -1, "output_tokens": 5, "wall_seconds": float("nan"),
                                "decode_seconds": 0.25})
        self.assertFalse(summary["cost_complete"])
        self.assertEqual(summary["observed_model_cost_lower_bound"], {"output_tokens": 5, "decode_seconds": 0.25})
        self.assertEqual(len(summary["model_cost_issues"][0]["issues"]), 2)

    def test_generation_probe_does_not_trust_invalid_counts(self):
        for cost in (None, [], {"consumed_prompt_tokens": True}, {"consumed_prompt_tokens": "1"},
                     {"consumed_prompt_tokens": 0.5}, {"consumed_prompt_tokens": -1}):
            with self.subTest(cost=cost):
                self.assertFalse(generation_observed({"events": [{"model_cost": cost}]}))
        self.assertTrue(generation_observed({"events": [{"model_cost": {"consumed_prompt_tokens": 1}}]}))

    def test_finite_individual_times_cannot_overflow_into_complete_total(self):
        event = {"model_cost_complete": True, "model_cost": dict(VALID, wall_seconds=1e308),
                 "model_text": "synthetic", "tool_attempted": False}
        row = self.fixture.row(events=[copy.deepcopy(event), copy.deepcopy(event)])
        summary = analyze(self.fixture.panel, [row], [0], self.fixture.identities)["arms"]["M-DIRECT"]
        self.assertFalse(summary["cost_complete"])
        self.assertEqual(summary["observed_model_cost_lower_bound"]["wall_seconds"], 1e308)
        self.assertEqual(summary["model_cost_issues"][0]["issues"][0]["reason"], "sum_not_finite")


if __name__ == "__main__":
    unittest.main()

"""Offline controls for zero-candidate diagnosis and the inert permutation profile."""

import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

from irisx.arc_nvarc_candidates import bounded_dfs_search, solve_task, FixtureCandidateBackend
from irisx.arc_nvarc_representation import END
from irisx.arc_nvarc_sdg import (BoundedLocalHFTeacher, SavedTeacher, run_teacher_pipeline,
                               render_source_teacher_prompt, validate_teacher_response)
from irisx.arc_nvarc_teacher_spec import PROFILE, PROMPTS, parse_spec, paired_seed
from irisx.arc_nvarc_teacher_profile import LIMITS, TOTAL_TOKENS
from irisx.arc_nvarc_combined import completion_failure, require_live_authorization, read
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools.stage_nvarc_combined_candidate import PLAN, RUN, render
from tools.preflight_nvarc_combined import probe_guard

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = {"puzzle1": {"input_shape": [5, 1], "rule": "Swap the first two and last two rows."},
           "puzzle2": {"input_shape": [3, 3], "rule": "Rotate the grid by 180 degrees."}}
MIX = {"shape": [3, 3], "output_from_input": [7, 8, 6, 5, 4, 3, 2, 0, 1]}
INPUT_CODE = "import numpy as np\ndef generate_puzzle_input(seed: int):\n return np.random.default_rng(seed).integers(0, 10, size=(3, 3))"
OUTPUT_CODE = "import numpy as np\ndef generate_puzzle_output(input_grid):\n return np.asarray(input_grid).reshape(-1)[[7,8,6,5,4,3,2,0,1]].reshape(3,3)"


def response(text, finish="eos"):
    return {"text": text, "finish_reason": finish, "input_tokens": 100, "output_tokens": 40}


class SpecSavedTeacher(SavedTeacher):
    def __init__(self, responses):
        super().__init__(responses)
        self.rendered = []
        self.validator = BoundedLocalHFTeacher(None, None, model_material_digest="sha256:" + "0" * 64,
            maximum_input_tokens=8192, maximum_output_tokens=3072, maximum_total_tokens=TOTAL_TOKENS,
            stage_limits=LIMITS, enable_thinking=False, require_complete=True, validation_profile=PROFILE)
        self.identity += ":" + self.validator.identity

    def complete(self, stage, item, prompt):
        self.rendered.append((stage, render_source_teacher_prompt(stage, item, prompt, profile=PROFILE)))
        return copy.deepcopy(super().complete(stage, item, prompt))

    def validate_response(self, stage, value):
        self.validator.validate_response(stage, value)


class SearchDiagnosticsTests(unittest.TestCase):
    def search(self, callback, **bounds):
        return bounded_dfs_search([14], callback, max_new_tokens=bounds.get("tokens", 64),
            max_expansions=bounds.get("expansions", 128), max_sequences=2,
            max_score=-math.log(0.2), deadline=bounds.get("deadline"), now=lambda: 0)

    def test_uniform_digits_and_forbidden_root_have_distinct_evidence_without_renormalizing(self):
        uniform = [math.log(1 / 16)] * 16
        diffuse = self.search(lambda _: uniform)
        self.assertEqual((1, [], "no_valid_candidate"),
            (diffuse["expansions"], diffuse["sequences"], diffuse["stop_reason"]))
        diag = diffuse["diagnostics"]
        self.assertEqual(list(range(10)), diag["root"]["allowed_token_ids"])
        self.assertEqual([], diag["root"]["score_surviving_token_ids"])
        self.assertEqual(10, diag["score_pruned_edges"])
        self.assertEqual("root_legal_tokens_below_score_threshold", diag["no_candidate_reason"])
        for blocked in (10, 11, 12, 13, 14, END):
            with self.subTest(blocked=blocked):
                values = [math.log(0.1 / 15)] * 16
                values[blocked] = math.log(0.9)
                result = self.search(lambda _: values)
                root = result["diagnostics"]["root"]
                self.assertEqual(blocked, root["best_token_id"])
                self.assertFalse(root["best_token_allowed"])
                self.assertEqual(1, result["expansions"])
                self.assertFalse(result["sequences"])

    def test_cumulative_pruning_limits_and_deadline_are_separate_and_bounded(self):
        def cumul(prefix):
            values = [-100.0] * 16
            values[1 if len(prefix) == 1 else END] = -0.9
            return values
        cumulative = self.search(cumul)
        self.assertEqual(2, cumulative["expansions"])
        self.assertEqual([1], cumulative["diagnostics"]["root"]["score_surviving_token_ids"])
        self.assertEqual("cumulative_score_or_grammar_exhaustion", cumulative["diagnostics"]["no_candidate_reason"])
        def long_path(prefix):
            return [-100.0, 0.0] + [-100.0] * 14
        for bounds, reason in (({"tokens": 1}, "token_limit"), ({"expansions": 2}, "expansion_limit"),
                               ({"deadline": 0}, "deadline")):
            report = self.search(long_path, **bounds)
            self.assertEqual(reason, report["stop_reason"])
            self.assertEqual(reason, report["diagnostics"]["no_candidate_reason"])
            self.assertLess(len(canonical_bytes(report["diagnostics"])), 2000)
        with self.assertRaisesRegex(ValidationError, "compact logits"):
            self.search(lambda _: [-1.0] * 17)

    def test_returned_invalid_grids_and_missing_eos_are_counted_before_ranking(self):
        class MalformedBackend(FixtureCandidateBackend):
            def generate(self, query, **kwargs):
                return [{"tokens": [1, 10, 2, 3, END], "eos": True, "beam_nll": 0.0},
                        {"tokens": [1], "eos": False, "beam_nll": 0.0}]
        task = {"task_id": "fixture", "train": [{"input": [[1]], "output": [[2]]}],
                "test": [{"input": [[3]]}]}
        result = solve_task(task, MalformedBackend({}), {"seed": 2, "maximum_calls_per_task": 1,
                           "beams_per_call": 2, "maximum_new_tokens": 64})[0]
        self.assertEqual({"missing_eos": 1, "invalid_grid": 1}, result["parse_rejections"])
        self.assertEqual((2, 0, "missing-candidate"),
                         (result["returned_sequences"], result["verification_calls_so_far"], result["status"]))

    def test_completed_call_diagnostics_survive_a_later_generation_failure(self):
        class PartialBackend(FixtureCandidateBackend):
            def generate(self, query, **kwargs):
                self.calls += 1
                if self.calls == 2:
                    raise ValidationError("second fixture call failed")
                self.last_generation_observation = bounded_dfs_search(query, lambda _: [-4.0]*16,
                    max_new_tokens=64, max_score=-math.log(.2), max_expansions=128, max_sequences=2)
                return []
        task = {"task_id": "fixture", "train": [{"input": [[1]], "output": [[2]]}],
                "test": [{"input": [[3]]}]}
        events = []
        with self.assertRaisesRegex(ValidationError, "second fixture call failed"):
            solve_task(task, PartialBackend({}), {"seed": 2, "maximum_calls_per_task": 2,
                "beams_per_call": 2, "maximum_new_tokens": 64}, call_observer=events.append)
        self.assertEqual(["reserved", "complete", "reserved"], [e["status"] for e in events])
        self.assertEqual("root_legal_tokens_below_score_threshold",
                         events[1]["generation_observation"]["diagnostics"]["no_candidate_reason"])


class StructuredTeacherTests(unittest.TestCase):
    def seed(self):
        demo1 = {"input": [[1], [2], [3], [4], [5]], "output": [[2], [1], [3], [5], [4]]}
        demo2 = {"input": [[1,2,3], [4,5,6], [7,8,9]], "output": [[9,8,7], [6,5,4], [3,2,1]]}
        return paired_seed({"record": {"record_id": "fixture", "train_demos": [demo1, demo1],
            "second_description": "Second public ARC training puzzle demonstrations: " + json.dumps([demo2, demo2])}})

    def test_profile_does_not_lower_eos_or_token_reservations(self):
        with self.assertRaisesRegex(ValidationError, "EOS"):
            validate_teacher_response("mix", response(json.dumps(MIX), "length"), profile=PROFILE)
        with self.assertRaises(ValidationError):
            BoundedLocalHFTeacher(None, None, model_material_digest="sha256:" + "0" * 64,
                maximum_input_tokens=8192, maximum_output_tokens=3072, maximum_total_tokens=TOTAL_TOKENS,
                stage_limits=LIMITS, enable_thinking=False, require_complete=False, validation_profile=PROFILE)

    def test_schema_rejects_seven_cells_duplicates_booleans_unknown_fields_and_unclosed_json(self):
        invalid = [{**MIX, "output_from_input": list(range(7))},
                   {**MIX, "output_from_input": [0] * 9},
                   {**MIX, "output_from_input": [False] + list(range(1, 9))},
                   {**MIX, "shape": [3, 2]}, {**MIX, "extra": "analysis"}]
        for value in invalid:
            with self.assertRaises(ValidationError):
                parse_spec("mix", json.dumps(value))
        for text in ('{"shape":[3,3],', '```json\n' + json.dumps(MIX) + '\n```',
                     '{"shape":[3,3],"shape":[3,3],"output_from_input":[0,1,2,3,4,5,6,7,8]}'):
            with self.assertRaises(ValidationError):
                parse_spec("mix", text)
        self.assertEqual(MIX, parse_spec("mix", json.dumps(MIX)))

    def test_paired_descriptions_four_dependent_saved_stages_and_fail_closed_replay(self):
        seed = self.seed()["record"]
        saved = {"summary:fixture": response(json.dumps(SUMMARY)), "mix:fixture": response(json.dumps(MIX)),
                 "input-logic:fixture": response(INPUT_CODE), "output-logic:fixture": response(OUTPUT_CODE)}
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx") as temp:
            provider = SpecSavedTeacher(saved)
            result = run_teacher_pipeline([seed], PROMPTS, provider, Path(temp)/"good", seed=24, maximum_calls=0)
            self.assertEqual((0, 4), (result["reserved_calls"], len(result["stages"])))
            self.assertIn('"input_shape": [5, 1]', provider.rendered[1][1])
            self.assertIn('"input_shape": [3, 3]', provider.rendered[1][1])
            self.assertNotIn("Second public ARC training puzzle demonstrations", provider.rendered[1][1])
            broken = {**saved, "mix:fixture": response(json.dumps(MIX), "length")}
            failed_provider = SpecSavedTeacher(broken)
            failed = run_teacher_pipeline([seed], PROMPTS, failed_provider, Path(temp)/"bad", seed=24, maximum_calls=0)
            self.assertEqual(["summary", "mix"], list(failed["stages"]))
            self.assertEqual("rejected", failed["stages"]["mix"]["records"]["fixture"]["status"])
            self.assertEqual(2, len(failed_provider.rendered))
            self.assertEqual(0, provider.validator.reserved_tokens)

    def test_candidate_guard_rejects_exact_package_before_ml_or_setup(self):
        plan = read(PLAN)
        self.assertEqual(RUN, plan["run_id"])
        self.assertFalse(plan["approved"])
        self.assertTrue(all(v == 0 for v in plan["external_allowances"].values()))
        with self.assertRaises(ValidationError):
            require_live_authorization(plan)
        source = render({"plan": PLAN.read_bytes()}, {"plan": "plan.json"})
        probe_guard(source, digest_value(plan), run_id=RUN)

    def test_new_teacher_profile_cannot_reuse_consumed_standalone_approval(self):
        from irisx.arc_nvarc_sdg_teacher import run
        child = read(PLAN)["branches"]["m3"]
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx") as temp:
            path = Path(temp)/"plan.json"
            for changed in (child, {**child, "approved": True, "run_id": "nvarc-m3-teacher-small-004",
                                    "owner_decision": "Decision 0033"}):
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValidationError, "structured teacher profile is inert"):
                    run(path, Path("ABSENT"), Path("ABSENT"), Path("ABSENT"), Path("ABSENT"), Path(temp)/"work")

    def test_partial_error_retains_completed_m2_and_precise_mix_failure(self):
        manifest = {"outcome": "partial", "branches": {
            "m2": {"outcome": "complete", "last_phase": "verified", "actual_counters": {"ranked_candidates": 0}},
            "m3": {"outcome": "failed", "last_phase": "teacher/mix", "stage_outcomes": [
                {"stage": "summary", "status": "complete"},
                {"stage": "mix", "status": "rejected", "reason": "teacher output did not finish with EOS"}]}}}
        before = copy.deepcopy(manifest)
        message = completion_failure(manifest)
        self.assertIn("m2 complete at verified (ranked_candidates=0; missing-candidate)", message)
        self.assertIn("mix rejected: teacher output did not finish with EOS", message)
        self.assertEqual(before, manifest)
        self.assertIsNone(completion_failure({"outcome": "complete"}))


if __name__ == "__main__":
    unittest.main()

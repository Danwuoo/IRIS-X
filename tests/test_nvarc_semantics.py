"""Offline semantics, independent rule controls and immutable negative replay."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from irisx.arc_nvarc_semantics import (PROFILE, PROMPTS, apply_rule, compose_order,
    validate_summary, validate_mix, legacy_rotation_claim, accept_program_pairs,
    accept_semantic_record)
from irisx.arc_nvarc_sdg import BoundedLocalHFTeacher, SavedTeacher, run_teacher_pipeline
from irisx.arc_nvarc_teacher_profile import LIMITS, TOTAL_TOKENS
from irisx.canonical import digest_value
from irisx.errors import ValidationError

FIXTURE = Path(__file__).parent / "fixtures/nvarc_combined_003_semantic_negative.json"
SUMMARY = {"puzzle1": {"input_shape": [5, 1], "operations": ["boundary-pair-swap"]},
           "puzzle2": {"input_shape": [3, 3], "operations": ["rotate180"]}}
MIX = {"shape": [3, 3], "output_from_input": [7, 8, 6, 5, 4, 3, 2, 0, 1]}
INPUT = "import numpy as np\ndef generate_puzzle_input(seed):\n return np.random.default_rng(seed).integers(0,10,size=(3,3))"
OUTPUT = "import numpy as np\ndef generate_puzzle_output(input_grid):\n return np.asarray(input_grid).reshape(-1)[[7,8,6,5,4,3,2,0,1]].reshape(3,3)"


def retained():
    return json.loads(FIXTURE.read_bytes())


def item():
    return {**retained()["seed"]["record"], "composition_shape": [3, 3]}


def response(text):
    return {"text": text, "finish_reason": "eos"}


class SemanticSavedTeacher(SavedTeacher):
    def __init__(self, replies):
        super().__init__(replies)
        self.validator = BoundedLocalHFTeacher(None, None, model_material_digest="sha256:" + "0" * 64,
            maximum_input_tokens=8192, maximum_output_tokens=3072, maximum_total_tokens=TOTAL_TOKENS,
            stage_limits=LIMITS, enable_thinking=False, require_complete=True, validation_profile=PROFILE)
        self.identity += ":" + self.validator.identity

    def complete(self, stage, record, prompt):
        from irisx.arc_nvarc_sdg import render_source_teacher_prompt
        render_source_teacher_prompt(stage, record, prompt, profile=PROFILE)
        return copy.deepcopy(super().complete(stage, record, prompt))

    def validate_item_response(self, stage, value, record):
        self.validator.validate_item_response(stage, value, record)


class SemanticsTests(unittest.TestCase):
    def test_retained_wrong_summary_rejected_against_actual_demos_and_raw_unchanged(self):
        fixture = retained()
        before = copy.deepcopy(fixture)
        for stage, value in fixture["responses"].items():
            self.assertEqual(fixture["stage_bindings"][stage]["response_digest"], digest_value(value))
        summary = legacy_rotation_claim(json.loads(fixture["responses"]["summary"]["content"]))
        with self.assertRaisesRegex(ValidationError, "summary_demo_mismatch:puzzle1:0"):
            validate_summary(summary, {"puzzle1": item()["train_demos"], "puzzle2": item()["second_train_demos"]})
        with self.assertRaisesRegex(ValidationError, "mix_composition_mismatch"):
            validate_mix(json.loads(fixture["responses"]["mix"]["content"]), [3, 3],
                         [["boundary-pair-swap"], ["rotate180"]])
        self.assertEqual(before, fixture)

    def test_general_rules_rectangular_composition_and_every_demo_checked(self):
        # Independent oracle: explicit array manipulation, two non-ARC parents.
        samples = [[[1, 2, 3], [4, 5, 6]], [[6, 5, 4], [3, 2, 1]]]
        groups = {"left": [{"input": g, "output": [row[::-1] for row in g]} for g in samples],
                  "right": [{"input": g, "output": g[::-1]} for g in samples]}
        summary = {"left": {"input_shape": [2, 3], "operations": ["flip-columns"]},
                   "right": {"input_shape": [2, 3], "operations": ["flip-rows"]}}
        self.assertEqual(summary, validate_summary(summary, groups))
        self.assertEqual([5, 4, 3, 2, 1, 0], compose_order([2, 3], [["flip-columns"], ["flip-rows"]]))
        self.assertEqual([1, 0, 2, 3, 5, 4], compose_order([2, 3], [["boundary-pair-swap"]]))
        self.assertEqual(list(range(6)), compose_order([2, 3], [["rotate180"], ["rotate180"]]))
        groups["left"].append({"input": samples[0], "output": samples[0]})
        with self.assertRaisesRegex(ValidationError, "summary_demo_mismatch:left:2"):
            validate_summary(summary, groups)
        with self.assertRaisesRegex(ValidationError, "rule_operation_unsupported"):
            apply_rule(samples[0], ["some plausible prose"])
        with self.assertRaisesRegex(ValidationError, "boundary_pairs_overlap"):
            apply_rule([[1, 2, 3]], ["boundary-pair-swap"])

    def test_declared_rules_must_match_data_and_composition_order_matters(self):
        groups = {"puzzle1": item()["train_demos"], "puzzle2": item()["second_train_demos"]}
        self.assertEqual(SUMMARY, validate_summary(SUMMARY, groups))
        self.assertEqual(MIX, validate_mix(MIX, [3, 3], [SUMMARY[k]["operations"] for k in SUMMARY]))
        a = compose_order([2, 3], [["boundary-pair-swap"], ["flip-rows"]])
        b = compose_order([2, 3], [["flip-rows"], ["boundary-pair-swap"]])
        self.assertNotEqual(a, b)
        with self.assertRaisesRegex(ValidationError, "mix_composition_mismatch"):
            validate_mix({"shape": [2, 3], "output_from_input": b}, [2, 3], [["boundary-pair-swap"], ["flip-rows"]])
        with self.assertRaisesRegex(ValidationError, "mix_indices_invalid"):
            validate_mix({"shape": [3, 3], "output_from_input": [False] + list(range(1, 9))}, [3, 3], [["identity"]])

    def test_stage_rejection_preserves_reply_stops_pipeline_and_does_not_accept_schema(self):
        record = item(); identifier = record["record_id"]
        replies = {"summary:" + identifier: response(json.dumps(SUMMARY)),
                   "mix:" + identifier: copy.deepcopy(retained()["responses"]["mix"])}
        with tempfile.TemporaryDirectory() as temp:
            result = run_teacher_pipeline([record], PROMPTS, SemanticSavedTeacher(replies), Path(temp), seed=24, maximum_calls=0)
            self.assertEqual(["summary", "mix"], list(result["stages"]))
            rejected = result["stages"]["mix"]["records"][identifier]
            self.assertEqual("rejected", rejected["status"])
            self.assertEqual("mix_composition_mismatch", rejected["rejection_reason"])
            self.assertEqual(replies["mix:" + identifier]["text"], rejected["response"]["text"])
            self.assertEqual(digest_value(rejected["response"]), rejected["response_digest"])
            self.assertEqual(0, result["reserved_calls"])
            # Rejected stage never retried even with a changed provider reply.
            self.assertEqual(result, run_teacher_pipeline([record], PROMPTS, SemanticSavedTeacher(replies), Path(temp), seed=24, maximum_calls=0))

    def test_no_trusted_executor_no_program_execution_or_pair_acceptance(self):
        with self.assertRaisesRegex(ValidationError, "verified_semantic_program_executor_required"):
            accept_program_pairs(INPUT, OUTPUT, MIX, object())
        replies = {stage: response(text) for stage, text in {
            "summary": json.dumps(SUMMARY), "mix": json.dumps(MIX), "input-logic": INPUT, "output-logic": OUTPUT}.items()}
        with self.assertRaisesRegex(ValidationError, "verified_semantic_program_executor_required"):
            accept_semantic_record(item(), replies, None)

    def test_complete_stage_pipeline_keeps_programs_pending_and_requires_semantic_context(self):
        from irisx.arc_nvarc_sdg import validate_teacher_response
        with self.assertRaisesRegex(ValidationError, "semantic_teacher_context_required"):
            validate_teacher_response("summary", response(json.dumps(SUMMARY)), profile=PROFILE)
        record = item(); key = record["record_id"]
        replies = {stage + ":" + key: response(text) for stage, text in {
            "summary": json.dumps(SUMMARY), "mix": json.dumps(MIX), "input-logic": INPUT, "output-logic": OUTPUT}.items()}
        with tempfile.TemporaryDirectory() as temp:
            result = run_teacher_pipeline([record], PROMPTS, SemanticSavedTeacher(replies), Path(temp), seed=24, maximum_calls=0)
            self.assertEqual(4, len(result["stages"]))
            for stage in ("input-logic", "output-logic"):
                value = result["stages"][stage]["records"][key]
                self.assertEqual("complete", value["status"])
                self.assertEqual("program-contract-pending-sandbox", value["response"]["semantic_status"])
            self.assertNotIn("pairs", result)

    def test_semantic_profile_cannot_reuse_consumed_runtime_envelopes(self):
        from irisx.arc_nvarc_sdg_teacher import run, _run_bound
        plan = {"teacher_profile": PROFILE, "approved": True, "owner_decision": "Decision 0037"}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "plan.json"
            path.write_text(json.dumps(plan))
            absent = Path(temp) / "ABSENT"
            with self.assertRaisesRegex(ValidationError, "profile is inert"):
                run(path, absent, absent, absent, absent, absent)
            with self.assertRaisesRegex(ValidationError, "profile is inert"):
                _run_bound(plan, absent, absent, absent, absent, absent)

    def test_semantic_rejection_consumes_reserved_call_and_is_not_retried(self):
        from irisx.arc_nvarc_sdg import run_stage
        record = item(); key = record["record_id"]
        bad = copy.deepcopy(SUMMARY); bad["puzzle1"]["operations"] = ["rotate180"]
        provider = SemanticSavedTeacher({"summary:" + key: response(json.dumps(bad))})
        provider.billed_calls = 1  # accounting fixture; never a real model call
        with tempfile.TemporaryDirectory() as temp:
            result = run_stage("summary", [record], PROMPTS["summary"], provider, Path(temp), seed=24, maximum_calls=1)
            self.assertEqual(1, result["reserved_calls"])
            self.assertEqual("rejected", result["records"][key]["status"])
            self.assertEqual("summary_demo_mismatch:puzzle1:0", result["records"][key]["rejection_reason"])
            provider.responses = {}  # any accidental retry would fail
            self.assertEqual(result, run_stage("summary", [record], PROMPTS["summary"], provider, Path(temp), seed=24, maximum_calls=1))


if __name__ == "__main__":
    unittest.main()

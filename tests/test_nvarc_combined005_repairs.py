"""Offline controls for the distinct combined 005 repair profiles."""

import copy
import json
import math
import unittest

from irisx.arc_nvarc_candidates import bounded_dfs_search
from irisx.arc_nvarc_representation import END, GridTokenizer
from irisx.arc_nvarc_semantics_v4 import PROFILE, PROMPTS, single_operation_hints, json_object
from irisx.arc_nvarc_sdg import validate_teacher_response, render_source_teacher_prompt
from irisx.errors import ValidationError
from tests.test_nvarc_semantics import SUMMARY, MIX, item, response


class Combined005RepairTests(unittest.TestCase):
    def test_shape_floor_reaches_full_grid_without_relaxing_old_cumulative_search(self):
        target = GridTokenizer().encode_grid([[7] * 6 for _ in range(6)]) + [END]
        def next_probs(prefix):
            suffix = prefix[1:]
            values = [math.log(.001)] * 16
            values[target[len(suffix)]] = math.log(.7)
            return values
        old = bounded_dfs_search([12],next_probs,max_new_tokens=64,max_score=-math.log(.02),
                                 max_expansions=128,max_sequences=2)
        self.assertEqual([],old["sequences"])
        repaired = bounded_dfs_search([12],next_probs,max_new_tokens=64,max_score=-math.log(.02),
                                      max_expansions=128,max_sequences=2,
                                      token_probability_floor=.02,required_shape=(6,6))
        self.assertEqual(target,repaired["sequences"][0]["tokens"])
        self.assertEqual("irisx/nvarc-shape-token-floor-diagnostics-v1",repaired["diagnostics"]["format"])
        self.assertLessEqual(repaired["expansions"],128)

    def test_public_hint_and_fence_keep_semantic_gate(self):
        record = item()
        hints = single_operation_hints(record["train_demos"])
        self.assertEqual(["boundary-pair-swap"],hints["matching_single_operations"])
        rendered = render_source_teacher_prompt("summary",record,PROMPTS["summary"],profile=PROFILE)
        self.assertIn("boundary-pair-swap",rendered)
        raw = "```json\n" + json.dumps(SUMMARY) + "\n```"
        checked = response(raw)
        validate_teacher_response("summary",checked,profile=PROFILE,item=record)
        self.assertEqual(raw,checked["text"])
        self.assertEqual(PROFILE,checked["validation_profile"])
        mix_context = {**record,"stage_responses":{"summary":checked}}
        mix_prompt = render_source_teacher_prompt("mix",mix_context,PROMPTS["mix"],profile=PROFILE)
        self.assertIn("single ```json fenced block",mix_prompt.lower())
        mix = response("```json\n"+json.dumps(MIX)+"\n```")
        validate_teacher_response("mix",mix,profile=PROFILE,item=mix_context)
        self.assertEqual(MIX,json.loads(mix["content"]))
        bad = copy.deepcopy(SUMMARY)
        bad["puzzle1"]["operations"] = ["flip-rows"]
        with self.assertRaisesRegex(ValidationError,"summary_demo_mismatch"):
            validate_teacher_response("summary",response("```json\n"+json.dumps(bad)+"\n```"),
                                      profile=PROFILE,item=record)
        with self.assertRaisesRegex(ValidationError,"semantic_json"):
            json_object(raw+"\nextra text")


if __name__ == "__main__":
    unittest.main()

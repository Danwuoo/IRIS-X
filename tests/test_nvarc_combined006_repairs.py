"""Offline controls for the distinct combined 006 palette and mix guidance."""

import json
import math
import unittest

from irisx.arc_nvarc_candidates import bounded_dfs_search
from irisx.arc_nvarc_representation import END, GridTokenizer
from irisx.arc_nvarc_semantics_v5 import PROFILE, PROMPTS, expected_mix
from irisx.arc_nvarc_sdg import render_source_teacher_prompt, validate_teacher_response
from irisx.errors import ValidationError
from tests.test_nvarc_semantics import SUMMARY, MIX, item, response


class Combined006RepairTests(unittest.TestCase):
    def test_palette_and_shape_apply_before_model_branch_expansion(self):
        target = GridTokenizer().encode_grid([[1, 2], [2, 1]]) + [END]
        def next_probs(prefix):
            values = [math.log(.001)] * 16
            values[3] = math.log(.8)  # High-probability color absent from the public input.
            values[target[len(prefix) - 1]] = math.log(.7)
            return values
        repaired = bounded_dfs_search([12],next_probs,max_new_tokens=6,max_score=-math.log(.2),
            max_expansions=30,max_sequences=1,token_probability_floor=.02,
            required_shape=(2,2),required_colors=(1,2))
        self.assertEqual(target,repaired["sequences"][0]["tokens"])
        root = repaired["diagnostics"]["root"]
        self.assertEqual([1,2],root["allowed_token_ids"])
        self.assertEqual("irisx/nvarc-shape-palette-token-floor-diagnostics-v1",
                         repaired["diagnostics"]["format"])

    def test_mix_prompt_contains_exact_public_rule_composition_and_retains_gate(self):
        record = item()
        summary = response("```json\n"+json.dumps(SUMMARY)+"\n```")
        validate_teacher_response("summary",summary,profile=PROFILE,item=record)
        context = {**record,"stage_responses":{"summary":summary}}
        self.assertEqual(MIX,expected_mix(context))
        rendered = render_source_teacher_prompt("mix",context,PROMPTS["mix"],profile=PROFILE)
        self.assertIn('"shape":[3,3]',rendered)
        self.assertIn('"output_from_input":[7,8,6,5,4,3,2,0,1]',rendered)
        wrong = response('```json\n{"output_from_input":[4,2,0,5,3,1]}\n```')
        with self.assertRaisesRegex(ValidationError,"mix_schema_invalid"):
            validate_teacher_response("mix",wrong,profile=PROFILE,item=context)
        right = response("```json\n"+json.dumps(MIX)+"\n```")
        validate_teacher_response("mix",right,profile=PROFILE,item=context)
        self.assertEqual(MIX,json.loads(right["content"]))


if __name__ == "__main__":
    unittest.main()

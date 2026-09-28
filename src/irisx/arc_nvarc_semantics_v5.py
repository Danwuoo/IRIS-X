"""Distinct teacher profile with a trusted public-rule mix target."""

from __future__ import annotations

import copy
import json

from .arc_nvarc_semantics import (compose_order, validate_mix, validate_summary,
                                  accept_program_pairs)
from .arc_nvarc_semantics_v4 import PROMPTS as V4_PROMPTS, json_object, semantic_stage
from .canonical import digest_value

PROFILE = "qwen-rule-guided-v5"
PROMPTS = {**V4_PROMPTS,
    "mix": """The two public-demo rules have already passed their checks. The trusted
interpreter has composed them in order for the declared 3x3 shape. Return
EXACTLY the JSON object below, with both keys, all nine indices, and no
changes. A single ```json fenced block is allowed; no prose or extra blocks.
Expected JSON: {EXPECTED_MIX_JSON}
"""}


def expected_mix(item):
    groups = {"puzzle1":item["train_demos"],"puzzle2":item["second_train_demos"]}
    summary = validate_summary(json_object(item["stage_responses"]["summary"]["content"]), groups)
    rules = [summary[key]["operations"] for key in ("puzzle1","puzzle2")]
    shape = item["composition_shape"]
    return validate_mix({"shape":shape,"output_from_input":compose_order(shape,rules)}, shape, rules)


def prompt_values(stage, item):
    from .arc_nvarc_semantics_v4 import prompt_values as v4_values
    if stage == "mix":
        return {"EXPECTED_MIX_JSON":json.dumps(expected_mix(item),sort_keys=True,separators=(",",":"))}
    return v4_values(stage,item)


def accept_semantic_record(item, responses, executor):
    """Recheck all four raw responses under the unchanged semantic/program gates."""
    from .arc_nvarc_sdg import validate_teacher_response
    checked = copy.deepcopy(responses)
    stage_item = copy.deepcopy(item)
    for stage in ("summary","mix","input-logic","output-logic"):
        validate_teacher_response(stage,checked[stage],profile=PROFILE,item=stage_item)
        stage_item["stage_responses"] = {**stage_item.get("stage_responses",{}),stage:checked[stage]}
    summary = semantic_stage("summary",checked["summary"]["content"],item)
    spec = expected_mix({**item,"stage_responses":{"summary":checked["summary"]}})
    # The teacher still has to return that exact validated composition.
    semantic_stage("mix",checked["mix"]["content"],
                   {**item,"stage_responses":{"summary":checked["summary"]}})
    accepted = accept_program_pairs(checked["input-logic"]["content"],
                                    checked["output-logic"]["content"],spec,executor)
    return {**accepted,"profile":PROFILE,"record_id":item["record_id"],
        "public_parent_binding":digest_value({"train_demos":item["train_demos"],
            "second_train_demos":item["second_train_demos"]}),
        "summary_digest":digest_value(summary),"mix_digest":digest_value(spec),
        "raw_response_digests":{stage:digest_value(value) for stage,value in responses.items()}}

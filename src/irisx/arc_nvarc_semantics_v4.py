"""Public-demo rule hints and strict JSON-envelope repair for a distinct M3 profile.

The hints are recomputed from every supplied public training demonstration.
Raw model replies remain intact; an optional single JSON fence changes parsing
only, never the underlying semantic, composition, or generated-program gates.
"""

from __future__ import annotations

import copy
import json
import re

from .arc_nvarc_semantics import (PROMPTS as V3_PROMPTS, apply_rule,
    validate_summary, validate_mix, accept_program_pairs)
from .arc_nvarc_data import grid
from .canonical import digest_value
from .errors import ValidationError

PROFILE = "qwen-rule-hinted-v4"

PROMPTS = {
    **V3_PROMPTS,
    "summary": """Return exactly one JSON object with puzzle1 and puzzle2; a single
```json fenced block is allowed, but no prose or extra blocks. Each value must
contain input_shape [rows,columns] and ordered operations from identity,
boundary-pair-swap, rotate180, flip-rows, flip-columns. Boundary-pair-swap
flattens row-major, swaps cells 0 and 1 and the last two cells, keeps the
middle cells, then reshapes. For each puzzle, test your proposed rule against
EVERY public demonstration before answering. A syntactically valid but wrong
rule is rejected; use the public-demo-derived single-operation checks below
as hints, not as new labels. The checks are exhaustive over the five listed
SINGLE operations only and do not prove the underlying rule is unique.
Puzzle 1 demonstrations: {PUZZLE1_DEMOS}
Puzzle 1 single-operation checks: {PUZZLE1_HINTS}
Puzzle 2 demonstrations: {PUZZLE2_DEMOS}
Puzzle 2 single-operation checks: {PUZZLE2_HINTS}
""",
    "mix": V3_PROMPTS["mix"] + "\nReturn exactly one JSON object. A single ```json fenced block is allowed; no prose or extra blocks.\n",
}


def single_operation_hints(demos):
    if not isinstance(demos, list) or len(demos) < 2:
        raise ValidationError("rule_hint_demos_missing")
    samples = []
    common_shape = None
    for example in demos:
        if set(example) != {"input", "output"}:
            raise ValidationError("rule_hint_demo_fields_differ")
        before, after = grid(example["input"]), grid(example["output"])
        current_shape = [len(before), len(before[0])]
        if common_shape is None:
            common_shape = current_shape
        if common_shape != current_shape:
            raise ValidationError("rule_hint_input_shapes_differ")
        samples.append((before, after))
    # Explicit stable order; no answer ID or parent-specific special case.
    operations = ("identity", "boundary-pair-swap", "rotate180", "flip-rows", "flip-columns")
    rows = []
    for operation in operations:
        matches = []
        for before, after in samples:
            try:
                matches.append(apply_rule(before, [operation]) == after)
            except ValidationError:
                matches.append(False)
        rows.append({"operation": operation, "matches_each_demo": matches})
    return {"input_shape": common_shape, "single_operation_checks": rows,
            "matching_single_operations": [r["operation"] for r in rows if all(r["matches_each_demo"])]}


def prompt_values(stage, item):
    from .arc_nvarc_semantics import prompt_values as v3_values
    values = v3_values(stage, item)
    if stage == "summary":
        values["PUZZLE1_HINTS"] = json.dumps(single_operation_hints(item["train_demos"]),separators=(",",":"))
        values["PUZZLE2_HINTS"] = json.dumps(single_operation_hints(item["second_train_demos"]),separators=(",",":"))
    return values


def json_object(text):
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("semantic_json_empty")
    stripped = text.strip()
    if stripped.startswith("```"):
        match = re.fullmatch(r"```json\s*\n(.*?)\n```",stripped,re.DOTALL)
        if match is None or "```" in match.group(1):
            raise ValidationError("semantic_json_fence_invalid")
        stripped = match.group(1)
    if "```" in stripped:
        raise ValidationError("semantic_json_extra_block")
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as error:
        raise ValidationError("semantic_json_invalid") from error
    if not isinstance(value,dict):
        raise ValidationError("semantic_json_object_required")
    return value


def semantic_stage(stage, text, item):
    groups = {"puzzle1":item["train_demos"],"puzzle2":item["second_train_demos"]}
    if stage == "summary":
        return validate_summary(json_object(text),groups)
    summary = validate_summary(json_object(item["stage_responses"]["summary"]["content"]),groups)
    if stage == "mix":
        return validate_mix(json_object(text),item["composition_shape"],
            [summary[name]["operations"] for name in ("puzzle1","puzzle2")])
    raise ValidationError("unknown_semantic_stage")


def accept_semantic_record(item, responses, executor):
    """Recheck saved raw replies in stage order before any isolated program call."""
    from .arc_nvarc_sdg import validate_teacher_response
    checked = copy.deepcopy(responses)
    stage_item = copy.deepcopy(item)
    for stage in ("summary","mix","input-logic","output-logic"):
        validate_teacher_response(stage,checked[stage],profile=PROFILE,item=stage_item)
        stage_item["stage_responses"] = {**stage_item.get("stage_responses",{}),stage:checked[stage]}
    summary = semantic_stage("summary",checked["summary"]["content"],item)
    spec = semantic_stage("mix",checked["mix"]["content"],
        {**item,"stage_responses":{"summary":checked["summary"]}})
    accepted = accept_program_pairs(checked["input-logic"]["content"],
        checked["output-logic"]["content"],spec,executor)
    return {**accepted,"profile":PROFILE,"record_id":item["record_id"],
        "public_parent_binding":digest_value({"train_demos":item["train_demos"],
                                         "second_train_demos":item["second_train_demos"]}),
        "summary_digest":digest_value(summary),
        "raw_response_digests":{stage:digest_value(value) for stage,value in responses.items()}}

"""Distinct M3 prompt repair for the one-argument output entry contract."""

import json

from .arc_nvarc_semantics_v5 import (PROMPTS as V5_PROMPTS, expected_mix,
                                      prompt_values as v5_prompt_values)

PROFILE = "qwen-signature-guided-v6"
PROMPTS = {**V5_PROMPTS,
    "output-logic": """Write one complete Python code block with the exact function entry
`def generate_puzzle_output(input_grid):`. The entry takes ONE argument;
do not add shape, output_from_input, or any other parameter. All constants
must be inside the function. The public-rule-checked output shape is
{EXPECTED_SHAPE} and the exact row-major source-index order is
{EXPECTED_ORDER}. Return a 2D numpy integer array. The following complete
implementation is the contract example; you may copy it exactly:

```python
import numpy as np

def generate_puzzle_output(input_grid):
    flat = np.asarray(input_grid, dtype=np.int64).reshape(-1)
    return flat[np.asarray({EXPECTED_ORDER}, dtype=np.int64)].reshape({EXPECTED_SHAPE})
```

Return code only, with no prose, extra functions, filesystem, network,
randomness or external dependencies. The independent sandbox checks the
actual returned program against public-rule composition, varied seed inputs,
one-hot grids and offset colors. Puzzle: {PUZZLE}
Input generator for context: {INPUT_CODE}
"""}


def prompt_values(stage, item):
    values = v5_prompt_values(stage, item)
    if stage == "output-logic":
        spec = expected_mix(item)
        values.update(EXPECTED_SHAPE=json.dumps(spec["shape"], separators=(",", ":")),
                      EXPECTED_ORDER=json.dumps(spec["output_from_input"], separators=(",", ":")))
    return values


def accept_semantic_record(item, responses, executor):
    from .arc_nvarc_sdg import validate_teacher_response
    from .arc_nvarc_semantics import accept_program_pairs
    from .canonical import digest_value
    import copy
    checked = copy.deepcopy(responses)
    stage_item = copy.deepcopy(item)
    for stage in ("summary", "mix", "input-logic", "output-logic"):
        validate_teacher_response(stage, checked[stage], profile=PROFILE, item=stage_item)
        stage_item["stage_responses"] = {**stage_item.get("stage_responses", {}), stage: checked[stage]}
    spec = expected_mix({**item, "stage_responses": {"summary": checked["summary"]}})
    result = accept_program_pairs(checked["input-logic"]["content"],
                                  checked["output-logic"]["content"], spec, executor)
    return {**result, "profile": PROFILE, "record_id": item["record_id"],
            "public_parent_binding": digest_value({"train_demos": item["train_demos"],
                "second_train_demos": item["second_train_demos"]}),
            "mix_digest": digest_value(spec),
            "raw_response_digests": {stage: digest_value(value) for stage, value in responses.items()}}

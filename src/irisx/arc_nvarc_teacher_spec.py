"""Inert candidate: paired public descriptions and a small permutation puzzle.

This narrows the free-form v1 method; it is neither upstream parity nor a new
execution authorization. JSON structure is not SDG pair acceptance.
"""

from __future__ import annotations

import json

from .arc_nvarc_data import grid
from .errors import ValidationError
from .arc_nvarc_teacher_profile import PROMPTS as LEGACY_PROMPTS

PROFILE = "qwen-direct-permutation-v2"
PROMPTS = {
    **LEGACY_PROMPTS,
    "summary": """Describe two separate public grid puzzles from their demonstrations.
Return only one JSON object with keys puzzle1 and puzzle2. Each value has exactly
input_shape (two integers: rows, columns) and rule (one concise sentence, <=60 words).
Use the same grid terminology for both; preserve each puzzle's rule separately.
Count every cell: a 5x1 grid has 5 cells; a 3x3 grid has 9 cells. No analysis or code.
Puzzle 1 demonstrations: {PUZZLE1_DEMOS}
Puzzle 2 demonstrations: {PUZZLE2_DEMOS}
""",
    "mix": """Combine the two rules into one small fixed-shape permutation puzzle.
Return only JSON with exactly shape and output_from_input. shape is [3,3].
Flatten all 9 input cells in row-major order (indices 0..8). Generalize puzzle1's
boundary-pair swaps to this 9-cell list (swap 0/1 and 7/8, keep 2..6), then apply
puzzle2's 180-degree grid rotation. List the final 9 source indices in output order.
Each index 0..8 occurs exactly once. Inputs vary by drawing each color from 0..9
using the supplied seed. Reshape the resulting 9 cells to 3x3. No examples, code,
reasoning, self-corrections, markdown or other fields. A single final object only.
Puzzle 1 description: {PUZZLE1}
Puzzle 2 description: {PUZZLE2}
""",
    "input-logic": """Write one complete Python code block defining generate_puzzle_input(seed: int).
The puzzle below is validated JSON: shape gives rows/columns, output_from_input
is a row-major source-index permutation. Generate a numpy integer grid with that
shape, colors 0..9, all randomness seeded from seed. Vary inputs across seeds.
Include every helper. Only Python/numpy; no prose, analysis, ellipses, main,
filesystem, network or external dependencies.
Puzzle: {PUZZLE}
""",
    "output-logic": """Write one complete Python code block defining generate_puzzle_output(input_grid).
The puzzle JSON supplies shape and output_from_input: flatten input row-major,
select those source indices in order, reshape to shape, return numpy integer grid.
Deterministic, no randomness. Include every helper. Only Python/numpy; no prose,
analysis, ellipses, main, filesystem, network or external dependencies.
Puzzle: {PUZZLE}
Input generator (reference only):
{INPUT_CODE}
"""}


def _object(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValidationError("teacher spec repeats a JSON key")
            result[key] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=unique)
    except (ValueError, TypeError) as error:
        raise ValidationError("teacher spec requires one complete JSON object") from error
    if not isinstance(value, dict):
        raise ValidationError("teacher spec requires a JSON object")
    return value


def parse_spec(stage, text):
    value = _object(text)
    if stage == "summary":
        if set(value) != {"puzzle1", "puzzle2"}:
            raise ValidationError("teacher summary requires both puzzle descriptions")
        for key, shape in (("puzzle1", [5, 1]), ("puzzle2", [3, 3])):
            item = value[key]
            if (not isinstance(item, dict) or set(item) != {"input_shape", "rule"} or
                    item["input_shape"] != shape or
                    any(type(v) is not int for v in item["input_shape"]) or
                    not isinstance(item["rule"], str) or not 1 <= len(item["rule"].split()) <= 60):
                raise ValidationError("teacher summary shape or concise rule differs: " + key)
    elif stage == "mix":
        if set(value) != {"shape", "output_from_input"} or value["shape"] != [3, 3] or any(
                type(v) is not int for v in value["shape"]):
            raise ValidationError("teacher mix requires exact 3x3 permutation schema")
        order = value["output_from_input"]
        if (not isinstance(order, list) or len(order) != 9 or
                any(type(v) is not int for v in order) or sorted(order) != list(range(9))):
            raise ValidationError("teacher mix requires all nine unique source indices 0..8")
    else:
        raise ValidationError("unknown structured teacher stage")
    return value


def paired_seed(legacy):
    """Normalize the exact existing second-parent demos; no inferred truth."""
    import copy
    value = copy.deepcopy(legacy)
    text = value["record"].pop("second_description")
    prefix = "Second public ARC training puzzle demonstrations: "
    if not text.startswith(prefix):
        raise ValidationError("retained second public description prefix differs")
    try:
        second = json.loads(text[len(prefix):])
    except ValueError as error:
        raise ValidationError("retained second public demonstrations differ") from error
    value["record"]["second_train_demos"] = second
    for demos, shape in ((value["record"]["train_demos"], [5, 1]), (second, [3, 3])):
        if not isinstance(demos, list) or len(demos) < 2:
            raise ValidationError("paired seed requires two demos per puzzle")
        for demo in demos:
            if set(demo) != {"input", "output"}:
                raise ValidationError("paired seed exposes only public input/output demos")
            for rows in demo.values():
                checked = grid(rows)
                if [len(checked), len(checked[0])] != shape:
                    raise ValidationError("paired seed public demonstration shape differs")
    return value


def prompt_values(stage, item):
    history = item.get("stage_responses", {})
    if stage == "summary":
        return {"PUZZLE1_DEMOS": json.dumps(item["train_demos"][:2]),
                "PUZZLE2_DEMOS": json.dumps(item["second_train_demos"][:2])}
    if stage == "mix":
        summary = parse_spec("summary", history["summary"]["content"])
        return {"PUZZLE1": json.dumps(summary["puzzle1"], sort_keys=True),
                "PUZZLE2": json.dumps(summary["puzzle2"], sort_keys=True)}
    spec = parse_spec("mix", history["mix"]["content"])
    values = {"PUZZLE": json.dumps(spec, sort_keys=True)}
    if stage == "output-logic":
        values["INPUT_CODE"] = history["input-logic"]["content"]
    elif stage != "input-logic":
        raise ValidationError("unknown structured teacher prompt stage")
    return values

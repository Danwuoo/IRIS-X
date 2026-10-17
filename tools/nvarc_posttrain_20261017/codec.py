"""Literal 16-token grid chat; no natural-language tokenizer approximation.

This is an explicitly new continuation recipe for the official NVARC SFT139
and SFT141 weights. It does not claim numerical parity with Unsloth training.
"""
from __future__ import annotations

from tools.arc2_goal_sprint_20261017.data import valid_grid

NEWLINE, USER, ASSISTANT, EOT, START, END = range(10, 16)
MAX_GRID_TOKENS = 30 * 30 + 29 + 1
GENERATION_TOKENS = MAX_GRID_TOKENS + 1
PROBE_TEXT = "<|im_start|>user\n12<|im_end|><|im_start|>assistant\n34<|im_end|>"
PROBE_IDS = [14, 11, 10, 1, 2, 15, 14, 12, 10, 3, 4, 15]


def admit_tokenizer(tokenizer):
    if (len(tokenizer) != 16 or tokenizer.eos_token_id != END
            or tokenizer.encode(PROBE_TEXT, add_special_tokens=False) != PROBE_IDS):
        raise ValueError("official compact tokenizer identity differs")
    for digit in range(10):
        if tokenizer.encode(str(digit), add_special_tokens=False) != [digit]:
            raise ValueError("digit token identity differs")
    return {"vocabulary": 16, "eos": END, "probe_ids": PROBE_IDS, "format": "literal-compact-grid-chat"}


def grid_tokens(grid):
    if not valid_grid(grid):
        raise ValueError("complete rectangular 1..30 grid with colors 0..9 required")
    tokens = []
    for row in grid:
        if tokens:
            tokens.append(NEWLINE)
        tokens.extend(row)
    return tokens


def parse_completion(tokens):
    """Strict EOS-complete rectangular grid; never crop or repair a candidate."""
    if (not isinstance(tokens, (list, tuple)) or not 2 <= len(tokens) <= MAX_GRID_TOKENS
            or any(type(x) is not int for x in tokens) or tokens[-1] != END
            or any(not 0 <= x <= NEWLINE for x in tokens[:-1])):
        return None
    rows = [[]]
    for token in tokens[:-1]:
        if token == NEWLINE:
            rows.append([])
        else:
            rows[-1].append(token)
    return rows if valid_grid(rows) else None


def _query(grid):
    return [START, USER, NEWLINE] + grid_tokens(grid) + [END, START, ASSISTANT, NEWLINE]


def encode_example(demos, query, target=None, *, context=8192,
                   generation=GENERATION_TOKENS, loss_mode="final"):
    """Drop whole largest demonstrations only; never truncate any grid.

    Causal-output mode also supervises retained demo answers after the first;
    target query answers are always supervised. Every user/role token is masked.
    """
    if (type(context) is not int or context < 1 or type(generation) is not int
            or generation < 1 or loss_mode not in {"final", "causal_outputs"}
            or (target is None and loss_mode != "final")):
        raise ValueError("invalid compact context/loss configuration")
    if not isinstance(demos, list) or any(not isinstance(p, dict) or set(p) != {"input", "output"} for p in demos):
        raise ValueError("exact demonstration pairs required")
    pairs = [(_query(p["input"]), grid_tokens(p["output"]) + [END]) for p in demos]
    final_prompt = _query(query)
    completion = [] if target is None else grid_tokens(target) + [END]
    reserve = generation if target is None else len(completion)
    retained = list(range(len(pairs)))
    while len(final_prompt) + reserve + sum(sum(map(len, pairs[i])) for i in retained) > context:
        if not retained:
            raise ValueError("complete query/target exceeds context; truncation forbidden")
        retained.remove(max(retained, key=lambda i: sum(map(len, pairs[i]))))
    prompt, mask = [], []
    for position, i in enumerate(retained):
        prefix, answer = pairs[i]
        prompt.extend(prefix + answer)
        mask.extend([0] * len(prefix) + [int(loss_mode == "causal_outputs" and position > 0)] * len(answer))
    prompt.extend(final_prompt)
    mask.extend([0] * len(final_prompt) + [1] * len(completion))
    result = {"prompt_ids": prompt, "completion_ids": completion, "demos_used": len(retained),
              "demos_dropped": len(demos) - len(retained), "retained_demo_indices": retained,
              "loss_mode": loss_mode}
    if target is not None:
        result["loss_mask"] = mask
    return result

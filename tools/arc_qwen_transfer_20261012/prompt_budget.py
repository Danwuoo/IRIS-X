"""Whole-example prompt packing with exact tokenizer callbacks and no gold query.

The caller must provide the actual reviewed renderer/tokenizer; CPU fixture tests
do not admit a larger-context GPU profile. No grid, row, or answer is truncated.
"""
from itertools import combinations
from .demo_selector import _closed, _identifier, digest, grid


def pack_demonstrations(task, *, render, encode, context_limit=4096,
                        output_cap=1024, withheld_demo_id=None):
    _closed(task, ("task_id", "demonstrations", "query_input"), "task")
    _identifier(task["task_id"])
    grid(task["query_input"])
    if type(context_limit) is not int or type(output_cap) is not int:
        raise ValueError("integer token bounds required")
    # 30x30 ASCII digits + 29 separators + one EOS = 930 tokens at most,
    # but only once the production tokenizer's atomic alphabet is verified.
    if not 1024 <= output_cap < context_limit <= 8192:
        raise ValueError("unreviewed context/output bounds")
    demos = task["demonstrations"]
    if not isinstance(demos, list) or not 1 <= len(demos) <= 10:
        raise ValueError("invalid demo count")
    ids = []
    for demo in demos:
        _closed(demo, ("demo_id", "input", "output"), "demonstration")
        ids.append(_identifier(demo["demo_id"]))
        grid(demo["input"])
        grid(demo["output"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate demo IDs")
    if withheld_demo_id is not None and withheld_demo_id not in ids:
        raise ValueError("unknown withheld demo")
    if withheld_demo_id is not None:
        held = demos[ids.index(withheld_demo_id)]
        if grid(task["query_input"]) != grid(held["input"]):
            raise ValueError("LOO query must be the withheld demonstration input")
    eligible = [i for i, did in enumerate(ids) if did != withheld_demo_id]
    prompt_cap = context_limit - output_cap
    checked = 0
    for count in range(len(eligible), -1, -1):
        for chosen in combinations(eligible, count):
            # Fresh immutable copies prevent a callback mutating the task.
            projected = [{"demo_id": demos[i]["demo_id"],
                          "input": [list(row) for row in grid(demos[i]["input"])],
                          "output": [list(row) for row in grid(demos[i]["output"])]}
                         for i in chosen]
            query = [list(row) for row in grid(task["query_input"])]
            prompt = render(projected, query)
            if not isinstance(prompt, str):
                raise ValueError("renderer must return exact text")
            tokens = encode(prompt)
            if not isinstance(tokens, list) or any(type(t) is not int or t < 0 for t in tokens):
                raise ValueError("tokenizer must return exact nonnegative IDs")
            checked += 1
            if len(tokens) <= prompt_cap:
                selected = [ids[i] for i in chosen]
                return {"format": "irisx/whole-demonstration-packing-v1", "task_id": task["task_id"],
                        "admitted": bool(selected), "reason": "complete-demonstrations-fit" if selected else "no-complete-demonstration-fits",
                        "selected_demo_ids": selected, "omitted_demo_ids": [did for did in ids if did not in selected and did != withheld_demo_id],
                        "withheld_demo_id": withheld_demo_id, "prompt": prompt,
                        "prompt_sha256": digest(prompt), "prompt_tokens": len(tokens),
                        "context_limit": context_limit, "output_cap": output_cap,
                        "subsets_checked": checked, "query_targets_used": False,
                        "partial_grids_or_targets_truncated": False,
                        "selection_policy": "maximum complete demonstration count, then original-index lexicographic order"}
    return {"format": "irisx/whole-demonstration-packing-v1", "task_id": task["task_id"],
            "admitted": False, "reason": "query-only-prompt-exceeds-budget",
            "context_limit": context_limit, "output_cap": output_cap,
            "subsets_checked": checked, "query_targets_used": False,
            "partial_grids_or_targets_truncated": False}


def validate_training_completion(token_ids, output_cap):
    """Reject oversize supervision; callers must retain the exclusion denominator."""
    if type(output_cap) is not int or output_cap < 1 or not isinstance(token_ids, list):
        raise ValueError("invalid token budget")
    if not token_ids or any(type(t) is not int or t < 0 for t in token_ids):
        raise ValueError("invalid training completion")
    return {"eligible": len(token_ids) <= output_cap, "tokens": len(token_ids),
            "output_cap": output_cap, "truncated": False,
            "reason": None if len(token_ids) <= output_cap else "complete-target-exceeds-output-cap"}

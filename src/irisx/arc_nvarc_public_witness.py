"""A separate, answer-free positional witness from every public train pair."""

from .arc_nvarc_data import grid
from .canonical import digest_value
from .errors import ValidationError


def public_index_witness(task):
    train, tests = task["train"], task["test"]
    if len(train) < 2 or len(tests) != 1:
        raise ValidationError("public index witness workload differs")
    examples = [(grid(row["input"]), grid(row["output"])) for row in train]
    before = grid(tests[0]["input"])
    if (any((len(inp), len(inp[0])) != (2, 2) or (len(out), len(out[0])) != (6, 6)
            for inp, out in examples) or (len(before), len(before[0])) != (2, 2)):
        raise ValidationError("public index witness shapes differ")
    order = []
    for row in range(6):
        for column in range(6):
            matches = [index for index in range(4) if all(
                inp[index // 2][index % 2] == out[row][column]
                for inp, out in examples)]
            if len(matches) != 1:
                raise ValidationError("public demos do not identify a unique source cell")
            order.append(matches[0])
    result = [[before[order[row * 6 + column] // 2][order[row * 6 + column] % 2]
               for column in range(6)] for row in range(6)]
    return {"format": "irisx/nvarc-public-index-witness-v1", "grid": result,
            "source_index_order": order, "public_train_pairs": len(examples),
            "public_train_digest": digest_value(task["train"]),
            "claim": "source-visible positional candidate only; not a Qwen completion or ARC score"}

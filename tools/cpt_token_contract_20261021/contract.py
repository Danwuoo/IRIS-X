"""Length-derived next-token masks for the public Qwen Base tokenizer.

One document per row, no truncation, no cross-document attention.  In this Base
snapshot EOS equals PAD.  Token identity therefore cannot determine whether an
EOS target contributes to loss.  These lists are CPU reference values, not an
assertion that an unmodified MaxText parser accepts or preserves these arrays.
"""
from __future__ import annotations

FORMAT = "irisx/unpacked-token-contract-v1"


def build_row(ids, loss_on_token, *, length, eos_id, vocab_size, objective):
    """Shift one pretokenized document, retain true EOS, and pad explicitly.

    ``ids`` includes exactly one terminal EOS; no implicit BOS is inserted.
    SFT token masks specify the boundary *after* encoding the joined document.
    Separately encoding prompt and answer can change BPE boundaries and is not
    implemented here.  CPT and SFT are labels on this test contract, not recipes.
    """
    if type(length) is not int or length < 1:
        raise ValueError("length must be a positive integer")
    if type(vocab_size) is not int or vocab_size < 2:
        raise ValueError("invalid vocabulary size")
    if type(eos_id) is not int or not 0 <= eos_id < vocab_size:
        raise ValueError("invalid EOS/PAD")
    if objective not in {"cpt", "sft"}:
        raise ValueError("objective must be cpt or sft")
    if not isinstance(ids, (list, tuple)) or not 2 <= len(ids) <= length + 1:
        raise ValueError("document empty or overlong; truncation is forbidden")
    if any(type(x) is not int or not 0 <= x < vocab_size for x in ids):
        raise ValueError("invalid token ID")
    if ids[-1] != eos_id or eos_id in ids[:-1]:
        raise ValueError("exactly one final EOS required; packing is unsupported")
    if not isinstance(loss_on_token, (list, tuple)) or len(ids) != len(loss_on_token):
        raise ValueError("loss mask must align with original tokens")
    if any(type(x) is not bool for x in loss_on_token):
        raise ValueError("loss mask must contain literal booleans")
    if not loss_on_token[-1]:
        raise ValueError("true terminal EOS must remain a supervised target")
    if objective == "cpt" and not all(loss_on_token):
        raise ValueError("all-token CPT cannot silently become masked CPT")
    if objective == "sft":
        if loss_on_token[0] or all(loss_on_token):
            raise ValueError("SFT requires a nonempty prompt")
        first = loss_on_token.index(True)
        if not all(loss_on_token[first:]) or first == len(ids) - 1:
            raise ValueError("SFT requires one nonempty completion followed by EOS")
    real = len(ids) - 1
    pad = length - real
    active = [1] * real + [0] * pad
    positions = list(range(real)) + [0] * pad
    labels = [int(x) for x in loss_on_token[1:]] + [0] * pad
    row = {
        "format": FORMAT,
        "objective": objective,
        "inputs": list(ids[:-1]) + [eos_id] * pad,
        "targets": list(ids[1:]) + [eos_id] * pad,
        "inputs_segmentation": active,
        "targets_segmentation": labels,
        "inputs_position": positions,
        "targets_position": list(positions),
        "stored_tokens": len(ids),
        "real_positions": real,
        "loss_positions": sum(labels),
        "padded_positions": pad,
        "true_eos_target_position": real - 1,
    }
    return row


def token_ledger(rows):
    """Aggregate measured quantities without calling padded tokens useful data."""
    rows = list(rows)
    keys = ("stored_tokens", "real_positions", "loss_positions", "padded_positions")
    return {"format": FORMAT, "documents": len(rows),
            **{key: sum(row[key] for row in rows) for key in keys},
            "processed_positions": sum(len(row["inputs"]) for row in rows)}

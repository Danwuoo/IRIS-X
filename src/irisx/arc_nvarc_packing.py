# MFFD placement adapted from NVIDIA/NeMo-RL v0.3.0.
# Copyright (c) 2025, NVIDIA CORPORATION. All rights reserved.
# Licensed under Apache-2.0; see licenses/NeMo-RL-LICENSE.txt.
# Modifications: dependency-free placement, compact layouts and hybrid isolation.
"""Source MFFD layouts and explicit isolation for the Qwen3.5 hybrid port.

The reference executor runs each segment with a fresh recurrent/attention state.
It establishes packing semantics without claiming fused FlashAttention/NeMo
performance. Historical unpacked entry points and consumed probes stay frozen.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .canonical import digest_value
from .errors import ValidationError
from .arc_nvarc_representation import PAD

REFERENCE = {"repository": "NVIDIA/NeMo-RL", "reference": "v0.3.0",
    "commit": "b1c86a816c5e2b4ca41ece193624a38dc62e6fdf",
    "algorithm_sha256": "4b946e5913b50ae96891138b508352a1ce75a4e1bfe14aea14a31179ced64011",
    "original_training_exact_nemo_version_known": False}


def modified_first_fit_decreasing(lengths: Sequence[int], capacity: int) -> list[list[int]]:
    """Stable MFFD placement, compared against the pinned NeMo implementation."""
    if type(capacity) is not int or capacity < 1 or any(
            type(n) is not int or not 0 < n <= capacity for n in lengths):
        raise ValidationError("positive whole sequences within packing capacity required")
    classes = [[], [], [], []]
    for index, length in enumerate(lengths):
        category = 0 if length > capacity / 2 else 1 if length > capacity / 3 else 2 if length > capacity / 6 else 3
        classes[category].append((index, length))
    large, medium, small, tiny = classes
    large.sort(key=lambda item: item[1], reverse=True)
    medium.sort(key=lambda item: item[1], reverse=True)
    small.sort(key=lambda item: item[1])
    tiny.sort(key=lambda item: item[1])
    bins = [[item] for item in large]
    for group in bins:
        available = capacity - sum(n for _, n in group)
        chosen = next((i for i, (_, n) in enumerate(medium) if n <= available), None)
        if chosen is not None:
            group.append(medium.pop(chosen))
    for group in reversed(bins):
        if any(capacity / 3 < n <= capacity / 2 for _, n in group) or len(small) < 2:
            continue
        available = capacity - sum(n for _, n in group)
        if small[0][1] + small[1][1] > available:
            continue
        first = small.pop(0)
        chosen = next((i for i in range(len(small) - 1, -1, -1)
                       if small[i][1] <= available - first[1]), None)
        if chosen is None:
            raise ValidationError("MFFD feasible pair disappeared")
        group.extend((first, small.pop(chosen)))
    remaining = sorted(medium + small + tiny, key=lambda item: item[1], reverse=True)
    for group in bins:
        while remaining:
            available = capacity - sum(n for _, n in group)
            chosen = next((i for i, (_, n) in enumerate(remaining) if n <= available), None)
            if chosen is None:
                break
            group.append(remaining.pop(chosen))
    leftovers = []
    for item in remaining:
        chosen = next((group for group in leftovers
                       if item[1] <= capacity - sum(n for _, n in group)), None)
        if chosen is None:
            leftovers.append([item])
        else:
            chosen.append(item)
    return [[index for index, _ in group] for group in bins + leftovers]


def pack_sequences(rows: Sequence[Mapping[str, Any]], *, capacity: int = 256000,
                   length_multiple: int = 64) -> list[dict]:
    """Retain every full sequence, lineage and next-token supervision boundary."""
    if type(length_multiple) is not int or length_multiple < 1:
        raise ValidationError("positive sequence alignment required")
    lengths = []
    for row in rows:
        ids, labels = row.get("input_ids"), row.get("labels")
        if (not isinstance(ids, list) or len(ids) < 2 or not isinstance(labels, list) or
                len(ids) != len(labels) or labels[0] != -100 or
                any(type(x) is not int or not 0 <= x < 16 for x in ids) or
                any(type(y) is not int or y != -100 and y != x for x, y in zip(ids, labels)) or
                not any(y >= 0 for y in labels[1:])):
            raise ValidationError("complete compact sequence and assistant labels required")
        lengths.append((len(ids) + length_multiple - 1) // length_multiple * length_multiple)
    groups = modified_first_fit_decreasing(lengths, capacity)
    result = []
    for group in groups:
        ids, labels, positions, mask, segments, offsets = [], [], [], [], [], [0]
        for index in group:
            row, start, padded = rows[index], len(ids), lengths[index]
            actual = len(row["input_ids"])
            ids.extend(row["input_ids"] + [PAD] * (padded - actual))
            # Independent causal losses never predict the first token of a sample.
            labels.extend([-100] + row["labels"][1:] + [-100] * (padded - actual))
            positions.extend(range(padded))
            mask.extend([1] * actual + [0] * (padded - actual))
            segments.append({"row_index": index, "start": start, "valid_end": start + actual,
                "end": start + padded, "input_tokens": actual,
                "supervised_tokens": sum(y >= 0 for y in row["labels"][1:]),
                "sequence_digest": digest_value(row),
                "lineage": {k: v for k, v in row.items() if k not in {"input_ids", "labels"}}})
            offsets.append(start + padded)
        pack = {"format": "irisx/nvarc-segmented-pack-v1", "algorithm": "modified_first_fit_decreasing",
            "capacity": capacity, "length_multiple": length_multiple, "reference": REFERENCE,
            "input_ids": ids, "labels": labels, "position_ids": positions, "attention_mask": mask,
            "cu_seqlens": offsets, "segments": segments,
            "input_tokens": sum(x["input_tokens"] for x in segments),
            "supervised_tokens": sum(x["supervised_tokens"] for x in segments)}
        validate_pack(pack)
        result.append(pack)
    return result


def validate_pack(pack: Mapping[str, Any]) -> None:
    if (pack.get("format") != "irisx/nvarc-segmented-pack-v1" or
            pack.get("algorithm") != "modified_first_fit_decreasing" or
            pack.get("reference") != REFERENCE or not pack.get("segments")):
        raise ValidationError("source packing layout identity differs")
    ids, labels, positions, mask = (pack[key] for key in ("input_ids", "labels", "position_ids", "attention_mask"))
    if not len(ids) == len(labels) == len(positions) == len(mask) <= pack["capacity"]:
        raise ValidationError("packing tensor lengths/capacity differ")
    cursor, row_indices, tokens, supervised, offsets = 0, set(), 0, 0, [0]
    for segment in pack["segments"]:
        start, valid, end = (segment[key] for key in ("start", "valid_end", "end"))
        if (start != cursor or not start + 2 <= valid <= end <= len(ids) or
                segment["row_index"] in row_indices or
                end - start != (valid - start + pack["length_multiple"] - 1) // pack["length_multiple"] * pack["length_multiple"] or
                positions[start:end] != list(range(end - start)) or
                mask[start:end] != [1] * (valid - start) + [0] * (end - valid) or
                ids[valid:end] != [PAD] * (end - valid) or
                labels[start] != -100 or labels[valid:end] != [-100] * (end - valid) or
                any(type(x) is not int or not 0 <= x < 16 for x in ids[start:valid]) or
                any(type(y) is not int or y != -100 and y != x for x, y in zip(ids[start:valid], labels[start:valid])) or
                segment["input_tokens"] != valid - start or
                segment["supervised_tokens"] != sum(y >= 0 for y in labels[start:valid]) or
                segment["sequence_digest"] != digest_value({**segment["lineage"],
                    "input_ids": ids[start:valid], "labels": labels[start:valid]})):
            raise ValidationError("sample boundary, positions, labels or lineage differ")
        row_indices.add(segment["row_index"])
        tokens += valid - start
        supervised += segment["supervised_tokens"]
        cursor = end
        offsets.append(end)
    if (cursor != len(ids) or pack["cu_seqlens"] != offsets or
            pack["input_tokens"] != tokens or pack["supervised_tokens"] != supervised):
        raise ValidationError("packing coverage/counts differ")


def iter_isolated_forwards(model: Any, pack: Mapping[str, Any], device: Any) -> Iterable[dict]:
    """Fresh state per segment, including DeltaNet convolutions and recurrence.

    Backpropagate each yielded loss before requesting another item for bounded
    activation memory. No dense 256k-square mask or shared mutable KV is built.
    """
    import torch
    validate_pack(pack)
    for segment in pack["segments"]:
        start, end = segment["start"], segment["valid_end"]
        ids = torch.tensor([pack["input_ids"][start:end]], dtype=torch.long, device=device)
        positions = torch.tensor([pack["position_ids"][start:end]], dtype=torch.long, device=device)
        output = model(input_ids=ids, attention_mask=torch.ones_like(ids),
                       position_ids=positions, use_cache=False, past_key_values=None)
        labels = torch.tensor([pack["labels"][start:end]], dtype=torch.long, device=device)
        total = torch.nn.functional.cross_entropy(output.logits[:, :-1].float().reshape(-1, 16),
            labels[:, 1:].reshape(-1), ignore_index=-100, reduction="sum")
        yield {"segment": segment, "logits": output.logits, "loss_sum": total,
               "supervised_tokens": segment["supervised_tokens"]}
        del output, ids, positions, labels, total


def isolated_pack_loss(model: Any, pack: Mapping[str, Any], device: Any) -> Any:
    """Small-reference token mean; production callers backpropagate each segment."""
    losses = [item["loss_sum"] for item in iter_isolated_forwards(model, pack, device)]
    return sum(losses) / pack["supervised_tokens"]

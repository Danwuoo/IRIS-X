"""Torch-free exact sampled-trace contract for producer and CPU consumer.

Content hashes bind retained bytes, not stochastic provenance or model identity.
Completed traces only are admitted for replay; failed traces remain evidence,
never successful probability verification.
"""
from __future__ import annotations
import hashlib
import json
import math

VOCAB_SIZE, EOS_ID, PAD_ID, MAX_GENERATION, MAX_CONTEXT = 16, 15, 13, 931, 8192
MAX_BATCH = 8
TRACE_FORMAT = "irisx/nvarc-probability-trace-v1"
TRACE_CONVENTIONS = {
    "padding": "left_pad_id13_mask0",
    "prefill_positions": "clamp(cumsum(attention_mask)-1,min=0)",
    "decode_positions": "prompt_length+step-1",
    "decode_attention": "append_one_for_every_row_including_finished",
    "model_mode": "eval", "grad_enabled": False, "use_cache": True,
    "logits_to_keep": 1, "vocabulary": 16, "temperature": 1,
    "normalization": "float32_selected_logit_minus_logsumexp_full_vocabulary",
}

_TRACE_COUNTERS = {"generation_forward_attempts", "generation_input_tokens", "generation_row_token_slots",
    "generation_finished_row_token_slots", "generation_padding_tokens", "forward_calls", "sampled_tokens"}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode() + b"\n"

def _sha(trace):
    return hashlib.sha256(_canonical({k: v for k, v in trace.items() if k != "sha256"})).hexdigest()


def validate_trace(trace, *, expected_trace_sha256):
    """Strict bounded schema/causal/EOS/counter validation plus independent seal.

    A seal binds bytes, not provenance or model identity. The caller must retain
    the seal from its trusted generation and independently bind frozen weights.
    Failed/partial traces can be preserved but are never admitted for replay.
    """
    keys = {"format", "prompts", "prompt_lengths", "batch_size", "padding_width", "max_new_tokens",
            "sample", "conventions", "steps", "status", "error", "completion_ids",
            "completion_log_probs", "stops", "work", "sha256"}
    _need(type(trace) is dict and set(trace) == keys, "strict trace schema required")
    count, width, limit = trace["batch_size"], trace["padding_width"], trace["max_new_tokens"]
    _need(type(count) is int and 1 <= count <= MAX_BATCH, "trace batch must be in 1..8")
    _need(type(width) is int and 1 <= width < MAX_CONTEXT, "bounded trace padding width required")
    _need(type(limit) is int and 1 <= limit <= MAX_GENERATION and width + limit <= MAX_CONTEXT,
          "bounded trace generation/context required")
    _need(trace["format"] == TRACE_FORMAT and type(trace["sample"]) is bool
          and type(trace["conventions"]) is dict and set(trace["conventions"]) == set(TRACE_CONVENTIONS)
          and all(type(trace["conventions"][k]) is type(v) and trace["conventions"][k] == v
                  for k, v in TRACE_CONVENTIONS.items()), "trace conventions differ")
    prompts = trace["prompts"]
    _need(type(prompts) is list and len(prompts) == count, "trace prompt rows differ")
    for prompt in prompts:
        _need(type(prompt) is list and 1 <= len(prompt) <= width
              and all(type(t) is int and 0 <= t < 16 for t in prompt), "invalid trace prompt IDs")
    lengths = list(map(len, prompts))
    _need(type(trace["prompt_lengths"]) is list and trace["prompt_lengths"] == lengths
          and all(type(v) is int for v in trace["prompt_lengths"])
          and width == max(lengths), "trace prompt lengths/padding differ")
    steps = trace["steps"]
    _need(type(steps) is list and 1 <= len(steps) <= limit, "nonempty bounded selected trace required")
    _need(trace["status"] == "completed" and trace["error"] is None, "complete successful trace required")
    generated, logps, finished = [[] for _ in prompts], [[] for _ in prompts], [False] * count
    finished_slots, selected_tokens = 0, 0
    for index, row in enumerate(steps):
        _need(type(row) is dict and set(row) == {"step", "selected_ids", "selected_log_probs", "retained", "committed"},
              "strict trace step schema required")
        _need(type(row["step"]) is int and row["step"] == index and row["committed"] is True,
              "trace step index/commit differs")
        _need(not all(finished), "trace continued after all rows finished")
        ids, values, retained = row["selected_ids"], row["selected_log_probs"], row["retained"]
        _need(type(ids) is list and len(ids) == count and all(type(t) is int and 0 <= t < 16 for t in ids),
              "trace selected IDs differ")
        _need(type(values) is list and len(values) == count
              and all(type(v) is float and math.isfinite(v) and v <= 1e-6 for v in values),
              "finite nonpositive selected log probabilities required")
        _need(type(retained) is list and len(retained) == count and all(type(v) is bool for v in retained)
              and retained == [not done for done in finished], "trace retained/EOS mask differs")
        finished_slots += sum(finished)
        selected_tokens += sum(retained)
        for i in range(count):
            if retained[i]:
                generated[i].append(ids[i]); logps[i].append(values[i])
                finished[i] = ids[i] == EOS_ID
    _need(all(finished) or len(steps) == limit, "trace stopped before EOS or generation bound")
    for field, scalar_type in (("completion_ids", int), ("completion_log_probs", float)):
        values = trace[field]
        _need(type(values) is list and len(values) == count
              and all(type(row) is list and len(row) <= limit
                      and all(type(value) is scalar_type for value in row) for row in values),
              "bounded trace completion vectors required")
    _need(type(trace["stops"]) is list and len(trace["stops"]) == count
          and all(type(v) is str and v in {"completed", "length"} for v in trace["stops"]),
          "bounded trace stop values required")
    for field, expected in (("completion_ids", generated), ("completion_log_probs", logps),
                            ("stops", ["completed" if done else "length" for done in finished])):
        _need(type(trace[field]) is list and _canonical(trace[field]) == _canonical(expected),
              "trace " + field + " differs from committed selections")
    work = trace["work"]
    expected = {"generation_forward_attempts": len(steps), "generation_input_tokens": count * (width + len(steps) - 1),
                "generation_row_token_slots": count * len(steps), "generation_finished_row_token_slots": finished_slots,
                "generation_padding_tokens": count * width - sum(lengths), "forward_calls": len(steps),
                "sampled_tokens": selected_tokens}
    _need(type(work) is dict and set(work) == _TRACE_COUNTERS
          and all(type(v) is int and v >= 0 for v in work.values()) and work == expected,
          "trace physical counters differ")
    _need(type(expected_trace_sha256) is str and len(expected_trace_sha256) == 64
          and all(c in "0123456789abcdef" for c in expected_trace_sha256)
          and trace["sha256"] == expected_trace_sha256 == _sha(trace), "independently retained trace SHA differs")


def validate_rows(rows, trace):
    _need(type(rows) is list and len(rows) == trace["batch_size"], "returned trajectory count differs")
    keys = {"input_ids", "prompt_length", "completion_ids", "behavior_log_probs", "text", "completion_tokens", "stop"}
    for index, row in enumerate(rows):
        prompt, completion = trace["prompts"][index], trace["completion_ids"][index]
        _need(type(row) is dict and set(row) == keys, "returned trajectory schema differs")
        _need(row["input_ids"] == prompt + completion and row["prompt_length"] == len(prompt)
              and row["completion_ids"] == completion and row["completion_tokens"] == len(completion)
              and row["behavior_log_probs"] == [0.0] * len(prompt) + trace["completion_log_probs"][index]
              and row["stop"] == trace["stops"][index], "returned trajectory differs from original trace")

"""Bounded fixed-view inference for the actual compact NVARC engine.

This is a distinct inference protocol, not a numerical-parity claim: BF16
batching can change near-tie greedy choices. The compact codec, view order,
inverse transforms and vote/mean-own-view-NLL ranker are unchanged. No task
answers, legacy text codec, length-based reordering or sampling are used.

Work counters measure submitted forward inputs and prediction slots, including
failed forwards and already-finished rows. They are not completed FLOPs. A
failed multirow OOM can receive one singleton attempt per member, within its
original deadline. All later work in the query stays singleton; other failures
are never silently retried. Exception objects/tracebacks are not kept in logs.
"""
from __future__ import annotations

import gc
import hashlib
import math
import time

from tools.arc2_goal_sprint_20261017.data import canonical, inference_views, transform, view_inputs
from .codec import encode_example, parse_completion


PROTOCOL_VERSION = "compact-fixed-view-batching-v1"
RANKING = "votes-descending-mean-own-view-nll-tie-v1"
# Completed forward_calls and active selected sampled_tokens keep their existing
# meaning. The generation_* counters must be incremented BEFORE model dispatch.
WORK_COUNTERS = (
    "forward_calls", "sampled_tokens", "generation_forward_attempts",
    "generation_input_tokens", "generation_row_token_slots",
    "generation_finished_row_token_slots", "generation_padding_tokens",
)


def protocol_identity(cfg):
    """Include this complete identity in development/checkpoint selection pins."""
    size = cfg.get("inference_batch_size", 1)
    if type(size) is not int or size not in (1, 2):
        raise ValueError("inference_batch_size must be an exact integer in {1, 2}")
    return {
        "version": PROTOCOL_VERSION,
        "inference_batch_size": size,
        "view_order": "fixed-contiguous-no-length-sort",
        "codec": "literal-compact-16-token-grid-chat",
        "ranking": RANKING,
        "deadline_policy": "remaining-view-share-original-deadline-v1",
        "oom_policy": "multirow-once-per-member-then-singletons-v1",
        "batch_numerical_parity_claimed": False,
    }


def _runtime():
    # Keep protocol validation and fake unit tests usable without optional ML
    # dependencies. Real execution always uses the engine's actual exceptions.
    import torch
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, check_deadline

    def release_oom():
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return PhaseDeadline, torch.cuda.OutOfMemoryError, check_deadline, release_oom


def _snapshot(engine):
    result = {}
    for name in WORK_COUNTERS:
        value = getattr(engine, name, None)
        if type(value) is not int or value < 0:
            raise ValueError("nonnegative engine work counter required: " + name)
        result[name] = value
    return result


def _delta(engine, before):
    after = _snapshot(engine)
    result = {name: after[name] - before[name] for name in WORK_COUNTERS}
    if any(value < 0 for value in result.values()):
        raise RuntimeError("engine work counters decreased during inference")
    return result


def _checked_rows(rows, entries, max_new_tokens):
    """Validate the entire compact batch before any member can cast a vote."""
    if not isinstance(rows, list) or len(rows) != len(entries):
        raise ValueError("one complete compact result per submitted prompt required")
    checked = []
    for row, (_, example) in zip(rows, entries):
        if not isinstance(row, dict):
            raise ValueError("compact result must be a mapping")
        ids, length, count = row.get("input_ids"), row.get("prompt_length"), row.get("completion_tokens")
        logps, stop = row.get("behavior_log_probs"), row.get("stop")
        if (not isinstance(ids, list) or type(length) is not int
                or length != len(example["prompt_ids"])
                or ids[:length] != example["prompt_ids"]
                or type(count) is not int or not 1 <= count <= max_new_tokens
                or len(ids) != length + count
                or any(type(token) is not int or not 0 <= token < 16 for token in ids)
                or not isinstance(logps, list) or len(logps) != len(ids)
                or not isinstance(stop, str) or stop not in {"completed", "length"}):
            raise ValueError("bounded complete compact result contract differs")
        try:
            finite = all(type(value) in (int, float) and math.isfinite(value) for value in logps)
            nll = -sum(logps[length:]) / count if finite else math.inf
        except (TypeError, OverflowError):
            raise ValueError("finite compact behavior log probabilities required") from None
        if not math.isfinite(nll):
            raise ValueError("finite compact behavior log probabilities required")
        completion = ids[length:]
        if (15 in completion[:-1] or (stop == "completed") != (completion[-1] == 15)
                or (stop == "length" and count != max_new_tokens)
                or ("completion_ids" in row and row["completion_ids"] != completion)):
            raise ValueError("compact EOS/length/completion identity differs")
        # Retain only validated plain data, not arbitrary model-return objects.
        checked.append({"completion_ids": completion, "completion_tokens": count,
                        "stop": stop, "nll": nll})
    return checked


def infer_query_batched(engine, task, query, cfg, *, task_id, views, deadline):
    """Generate ordered compact views with auditable bounded batch1/batch2 work.

    Returns the historical infer_query candidate/ranking fields plus a protocol
    identity, every requested view receipt, and every generation attempt. A
    completed invalid grid counts as a completed view but never as a candidate.
    Failed/expired views have tokens=0; their physical work remains in attempts.
    """
    protocol = protocol_identity(cfg)
    if (type(deadline) not in (int, float) or math.isnan(deadline)
            or deadline == -math.inf):
        raise ValueError("finite absolute deadline or positive infinity required")
    if (type(cfg.get("generation_tokens")) is not int
            or not 1 <= cfg["generation_tokens"] <= 931
            or type(cfg.get("context_tokens")) is not int
            or not 1 <= cfg["context_tokens"] <= 8192):
        raise ValueError("bounded compact context/generation required")
    specs = inference_views(views, seed=cfg.get("evaluation_seed", 20261017),
                            task_id=task_id, demo_count=len(task["train"]))
    PhaseDeadline, OutOfMemoryError, check_deadline, release_oom = _runtime()
    initial_work = _snapshot(engine)
    receipts = [{"view": index, "status": "failed", "valid": False, "tokens": 0,
                 "attempts": []} for index in range(len(specs))]
    attempts, generated, candidates = [], {}, []
    oom_demoted = False

    def attempt(entries, until, mode):
        began, before = time.time(), _snapshot(engine)
        prompt_lengths = [len(example["prompt_ids"]) for _, example in entries]
        receipt = {"attempt": len(attempts), "mode": mode,
                   "views": [index for index, _ in entries], "batch_size": len(entries),
                   "status": "failed", "generation_invoked": False,
                   "prompt_tokens": sum(prompt_lengths),
                   "padded_prompt_tokens": len(entries) * max(prompt_lengths),
                   "budget_seconds": max(0.0, until - began) if math.isfinite(until) else None,
                   "committed_completion_tokens": 0}
        result, failure = None, None
        try:
            check_deadline(until)
            receipt["generation_invoked"] = True
            result = engine.generate_prompts([example["prompt_ids"] for _, example in entries],
                        max_new_tokens=cfg["generation_tokens"], deadline=until)
            check_deadline(until)
            result = _checked_rows(result, entries, cfg["generation_tokens"])
            receipt["status"] = "complete"
            receipt["committed_completion_tokens"] = sum(row["completion_tokens"] for row in result)
        except (PhaseDeadline, OutOfMemoryError, FloatingPointError, ValueError) as error:
            failure = type(error).__name__
            receipt["failure"] = failure
            receipt["oom"] = isinstance(error, OutOfMemoryError)
            result = None
            # No OOM traceback, causal exception or model frame crosses into a
            # fallback invocation, even if a framework retained tensor locals.
            if receipt["oom"]:
                error.__traceback__ = error.__cause__ = error.__context__ = None
        finally:
            receipt.update(wall_seconds=max(0.0, time.time() - began), **_delta(engine, before))
            attempts.append(receipt)
            for index, _ in entries:
                receipts[index]["attempts"].append(receipt["attempt"])
                if failure is not None:
                    receipts[index]["failure"] = failure
        # Deliberately outside the except scope: sys.exc_info() and traceback
        # owners must be released before empty_cache and the next model call.
        if receipt.get("oom"):
            release_oom()
        return result, receipt.get("oom", False)

    size = protocol["inference_batch_size"]
    for start in range(0, len(specs), size):
        end = min(start + size, len(specs))
        now = time.time()
        group_deadline = min(deadline, now + max(0.0, deadline - now) * (end - start) / (len(specs) - start))
        entries = []
        for index in range(start, end):
            try:
                check_deadline(group_deadline)
                demos, transformed_query = view_inputs(task, query, specs[index])
                example = encode_example(demos, transformed_query,
                            context=cfg["context_tokens"], generation=cfg["generation_tokens"])
                check_deadline(group_deadline)
                receipts[index]["demos_dropped"] = example["demos_dropped"]
                entries.append((index, example))
            except (PhaseDeadline, ValueError) as error:
                receipts[index]["failure"] = type(error).__name__
        if not entries:
            continue
        if not oom_demoted:
            result, oom = attempt(entries, group_deadline, "batch")
            if result is not None:
                generated.update((index, row) for (index, _), row in zip(entries, result))
                continue
            if not oom:
                continue
            oom_demoted = True
            # One attempt at an already-singleton view is enough. Do not retry
            # an OOM from a configured batch1 or one surviving encoded member.
            if len(entries) == 1:
                continue
            mode = "singleton_oom_fallback"
        else:
            mode = "singleton_after_oom"
        for offset, entry in enumerate(entries):
            now = time.time()
            until = min(group_deadline, now + max(0.0, group_deadline - now) / (len(entries) - offset))
            result, _ = attempt([entry], until, mode)
            if result is not None:
                generated[entry[0]] = result[0]

    # Candidate first appearance and tie resolution follow the original view
    # order, never return timing or whether the row needed OOM fallback.
    for index, receipt in enumerate(receipts):
        if index not in generated:
            continue
        row = generated[index]
        grid = parse_completion(row["completion_ids"])
        receipt.update(status="complete", valid=grid is not None,
                       tokens=row["completion_tokens"], stop=row["stop"])
        receipt.pop("failure", None)
        if grid is not None:
            original = transform(grid, **specs[index]["transform"], inverse=True)
            found = next((i for i, candidate in enumerate(candidates) if candidate["grid"] == original), None)
            if found is None:
                found = len(candidates)
                candidates.append({"grid": original, "votes": 0, "nll_sum": 0.0, "views": []})
            candidates[found]["votes"] += 1
            candidates[found]["nll_sum"] += row["nll"]
            candidates[found]["views"].append(index)
            receipt["candidate"] = found
    order = sorted(range(len(candidates)), key=lambda i: (-candidates[i]["votes"],
        candidates[i]["nll_sum"] / candidates[i]["votes"], i))
    work = _delta(engine, initial_work)
    work.update(committed_completion_tokens=sum(row["tokens"] for row in receipts),
                completed_views=len(generated), requested_views=len(specs),
                accounting="submitted-inputs-and-row-slots-not-completed-flops-v1")
    return {"ranked_grids": [candidates[i]["grid"] for i in order[:2]], "candidates": candidates,
            "ranked_candidate_indices": order, "views": receipts, "ranking": RANKING,
            "complete": len(generated) == len(specs), "inference_protocol": protocol,
            "view_specs_sha256": hashlib.sha256(canonical(specs)).hexdigest(),
            "generation_attempts": attempts, "generation_work": work,
            "oom_demoted_to_singletons": oom_demoted}

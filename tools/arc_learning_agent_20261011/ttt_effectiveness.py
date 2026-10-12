"""Fixed training-dev generated-grid selection for physical TTT ceilings.

Every option generates before any held-out completion is teacher forced. A
bounded adapter snapshot retains each option for the later NLL-only tie break;
adaptation is never repeated or refunded. Public answers are never admitted.
"""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import time

from tools.arc_next_models import digest, require
from .budget import atomic_json, digest as declared_order_digest
from .data import _demos, _validate_manifest
from .effectiveness import _evidence_mode, _integer, _receipt_ok, greedy_scope
from .grid_codec import decode_grid, encode_grid, grid_messages
from .metering import TrainingStageFailed


FORMAT = "irisx/training-dev-ttt-effectiveness-v1"
POLICY = {
    "selection_order": ["exact", "dimension_correct", "valid_grid", "lower_mean_nll", "lower_microbatches"],
    "activation": "strict generated-metric tuple improvement over zero; no aggregate exact or dimension regression",
    "nll_alone_activates_ttt": False,
    "comparison": "all fixed tasks and all options; no complete-case subset selection",
    "step_unit": "physical_attempted_microbatches",
    "mean_nll_weighting": "equal-task mean of completion-token mean NLL",
}


class _StopNewNeuralWork(RuntimeError):
    """A failed optimizer boundary forbids every dependent neural dispatch."""


def _rank_ids(ids, seed):
    return sorted(ids, key=lambda key: (declared_order_digest(["declared-task-order", seed, key]), key))


def _error(exc):
    return type(exc).__name__ + ": " + str(exc)[:256]


def _portable(value):
    # Invalid numerical receipts still belong in an auditable JSON report.
    # Their receipt-completeness flags have already failed closed.
    if type(value) is float and not math.isfinite(value):
        return "nonfinite:" + repr(value)
    if type(value) is dict:
        return {key: _portable(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return [_portable(item) for item in value]
    return value


def _active(trainer):
    return getattr(trainer, "active_task_id", getattr(trainer, "_task_id", None))


def _adaptation_complete(receipt, ceiling):
    """Optimizer updates may be fewer than the ceiling under accumulation."""
    if ceiling == 0:
        return receipt is None
    if type(receipt) is not dict or receipt.get("status") != "complete" or receipt.get("usage_known") is not True:
        return False
    for key in ("attempted_microbatches", "completed_microbatches", "physical_microbatch_ceiling"):
        if not _integer(receipt.get(key)) or receipt[key] != ceiling:
            return False
    if not _integer(receipt.get("optimizer_steps")) or not 0 < receipt["optimizer_steps"] <= ceiling:
        return False
    if receipt.get("steps") != receipt["optimizer_steps"] or receipt.get("optimizer_state_consistent") is not True:
        return False
    if any(not _integer(receipt.get(key)) for key in ("input_tokens", "supervised_tokens")):
        return False
    return all(key not in receipt or receipt[key] == ceiling for key in ("requested_steps", "admitted_steps"))


def _observed_usage(rows, attempted, ledgers):
    def total(receipts, key):
        return sum(r.get(key, 0) for r in receipts if _integer(r.get(key)))
    generations = [r["generation"] for r in rows if type(r["generation"]) is dict]
    scores = [r["score"] for r in rows if type(r["score"]) is dict]
    adaptations = [r["adaptation"] for r in rows if type(r["adaptation"]) is dict]
    calls = generations + scores
    usage = {
        "attempted_calls": dict(attempted),
        "generation_calls": sum(r.get("dispatched") is True for r in generations),
        "scoring_calls": sum(r.get("dispatched") is True for r in scores),
        "attempted_microbatches": total(adaptations, "attempted_microbatches"),
        "completed_microbatches": total(adaptations, "completed_microbatches"),
        "optimizer_updates": total(adaptations, "optimizer_steps"),
        "input_tokens": total(calls + adaptations, "input_tokens"),
        "output_tokens": total(generations, "output_tokens"),
        "supervised_tokens": total(adaptations, "supervised_tokens"),
        "forward_calls": total(calls, "forward_calls"),
        "usage_known": (len(generations) == attempted["generation_calls"] and
                        len(scores) == attempted["scoring_calls"] and
                        len(adaptations) == attempted["adaptation_calls"] and
                        all(r["generation_receipt_complete"] for r in rows if r["generation_attempted"]) and
                        all(r["scoring_receipt_complete"] for r in rows if r["scoring_attempted"]) and
                        all(r.get("usage_known") is True for r in adaptations)),
        "count_basis": "observed receipts; lower bounds when usage is unknown; ledger reservations are never refunded by restore",
        "ledgers": [],
    }
    for ledger, before, start in ledgers:
        item = {"charged_delta": {key: ledger.used[key] - before[key] for key in ledger.used},
                "events": deepcopy(ledger.events[start:]), "pending": deepcopy(ledger.pending)}
        usage["ledgers"].append(item)
        usage["usage_known"] = usage["usage_known"] and not bool(ledger.pending)
    return usage


def select_ttt(tasks, manifest, model, trainer, deadline, output, config, protected_ids=()):
    """Select 0/8/16 physical microbatches (0/1 in explicitly tiny CPU mode).

    The last demonstration of up to four fixed dev tasks is held out. Missing
    work defaults to zero with the original denominator. A nonzero option must
    improve generated behavior without aggregate exact/dimension regression;
    lower NLL cannot activate an otherwise tied or worse option. Complete caller
    state (including Adam, schedule, RNG, global snapshot and task ownership) is
    restored, while physical meters remain charged. Requires a frozen global.
    """
    require(type(config) is dict, "selector configuration required")
    require(type(deadline) in (int, float) and math.isfinite(deadline), "finite absolute deadline required")
    seed, count, cap = config.get("seed", 0), config.get("dev_tasks", 4), config.get("max_new_tokens", 1024)
    require(type(seed) is int and 0 <= seed < 2**63, "bounded selector seed required")
    require(type(count) is int and 1 <= count <= 4, "one to four fixed dev tasks required")
    require(type(cap) is int and 1 <= cap <= 2048, "bounded explicit generation cap required")
    require(type(config.get("tiny_cpu", False)) is bool, "explicit tiny CPU switch required")
    _validate_manifest(manifest, protected_ids)
    require(type(tasks) is dict and set(tasks) <= set(manifest["tasks"]), "manifest-bound training task sources required")
    for key, task in tasks.items():
        require(digest({"train": _demos(task)}) == manifest["tasks"][key]["task_sha256"],
                "task source hash differs: " + key)
    evidence = _evidence_mode(model, config.get("evidence_mode", "native"))
    require(getattr(trainer, "_global", None) is not None, "freeze_global required before TTT selection")
    options = [0, 1] if config.get("tiny_cpu") else [0, 8, 16]
    eligible = [key for key, item in manifest["tasks"].items()
                if item["split"] == "dev" and len(item["demonstrations"]) >= 3]
    chosen = _rank_ids(eligible, seed)[:count]
    rows = [{"task_id": key, "steps": steps, "physical_microbatch_ceiling": steps,
             "held_out_demo_index": len(manifest["tasks"][key]["demonstrations"]) - 1,
             "visible_demo_indices": list(range(len(manifest["tasks"][key]["demonstrations"]) - 1)),
             "target_used_for_adaptation": False, "generation": None, "score": None, "adaptation": None,
             "generation_attempted": False, "scoring_attempted": False, "adaptation_attempted": False,
             "generation_receipt_complete": False, "scoring_receipt_complete": False,
             "adaptation_complete": False, "exact": False, "dimension_correct": False,
             "shape_correct": False, "valid_grid": False, "begin": None, "reset": None,
             "snapshot": None, "score_restore": None, "errors": []}
            for key in chosen for steps in options]
    ledgers = []
    for owner in (model, trainer):
        ledger = getattr(owner, "ledger", None)
        if ledger is not None and all(ledger is not item[0] for item in ledgers):
            ledgers.append((ledger, dict(ledger.used), len(ledger.events)))
    attempted = {"generation_calls": 0, "scoring_calls": 0, "adaptation_calls": 0}
    handles, errors, releases = {}, [], []
    stop_all_new_neural_work = False
    if len(chosen) != count:
        errors.append("insufficient fixed dev tasks: requested %d, available %d" % (count, len(chosen)))
    caller = trainer.snapshot_training_state("ttt-selector-caller")
    started, peak_handles, restored = time.monotonic(), 0, None
    try:
        if _active(trainer) is not None:
            trainer.end_task()
        with greedy_scope(model):
            # No held-out completion may reach any model method during phase 1.
            for index, row in enumerate(rows):
                key, steps = row["task_id"], row["steps"]
                if key not in tasks or time.monotonic() >= deadline:
                    row["errors"].append("generation not admitted: missing source or deadline")
                    continue
                demos = manifest["tasks"][key]["demonstrations"]
                begun = False
                try:
                    row["begin"] = trainer.begin_task("dev:" + key)
                    begun = True
                    if steps:
                        attempted["adaptation_calls"] += 1
                        row["adaptation_attempted"] = True
                        row["adaptation"] = trainer.adapt_task("dev:" + key, deepcopy(demos[:-1]),
                                                               max_steps=steps, deadline=deadline)
                        if type(row["adaptation"]) is dict and (row["adaptation"].get("status") in
                                ("failed", "error", "failed_update") or row["adaptation"].get("usage_known") is False):
                            stop_all_new_neural_work = True
                            raise _StopNewNeuralWork("failed or unknown optimizer boundary; dependent inference forbidden")
                    row["adaptation_complete"] = _adaptation_complete(row["adaptation"], steps)
                    if not row["adaptation_complete"]:
                        row["errors"].append("physical adaptation ceiling or optimizer boundary incomplete")
                        continue
                    if time.monotonic() >= deadline:
                        row["errors"].append("generation not admitted: deadline")
                        continue
                    # Snapshot before generation also protects later scoring from
                    # an implementation which mutates its adapter while generating.
                    handle = trainer.snapshot("ttt-dev-%d-%d" % (index, steps))
                    handles[index] = handle
                    peak_handles = max(peak_handles, len(handles))
                    row["snapshot"] = {k: deepcopy(v) for k, v in handle.items() if k != "snapshot_id"}
                    row["generation_attempted"] = True
                    attempted["generation_calls"] += 1
                    row["generation"] = model.generate(grid_messages(deepcopy(demos[:-1]), deepcopy(demos[-1]["input"])),
                        kind="grid", seed=seed, max_new_tokens=cap, deadline=deadline)
                    row["generation_receipt_complete"] = _receipt_ok(row["generation"], generation=True, cap=cap)
                except Exception as exc:
                    if row["adaptation"] is None and type(getattr(exc, "receipt", None)) is dict:
                        row["adaptation"] = deepcopy(exc.receipt)
                    row["errors"].append(_error(exc))
                    if (isinstance(exc, (TrainingStageFailed, _StopNewNeuralWork)) or
                            (row["adaptation_attempted"] and row["adaptation"] is None) or
                            any(item[0].pending for item in ledgers)):
                        stop_all_new_neural_work = True
                        raise _StopNewNeuralWork("failed or unknown physical work; all new neural work stopped") from exc
                finally:
                    # adapt_task may already have reset itself on an exception.
                    if begun:
                        row["reset"] = trainer.end_task()
                        require(row["reset"].get("restored") is True and _active(trainer) is None,
                                "exact dev task reset required")
            # All generations are now fixed. Only this phase may read targets
            # into teacher-forcing calls, always under the matching adapter.
            for index, row in enumerate(rows):
                demos = manifest["tasks"][row["task_id"]]["demonstrations"]
                generated = row["generation"] or {}
                if row["generation_receipt_complete"] and generated.get("valid") and generated.get("finish_reason") == "eos":
                    try:
                        prediction = decode_grid(generated["text"])
                        target = demos[-1]["output"]
                        row["valid_grid"] = True
                        row["dimension_correct"] = (len(prediction), len(prediction[0])) == (len(target), len(target[0]))
                        row["shape_correct"] = row["dimension_correct"]
                        row["exact"] = prediction == target
                    except ValueError as exc:
                        row["errors"].append("grid: " + str(exc))
                if index not in handles or time.monotonic() >= deadline:
                    row["errors"].append("scoring not admitted: missing option snapshot or deadline")
                    continue
                try:
                    require(_active(trainer) is None, "no task ownership during held-out scoring")
                    row["score_restore"] = trainer.restore(handles[index])
                    require(row["score_restore"].get("restored") is True, "matching option restore required")
                    attempted["scoring_calls"] += 1
                    row["scoring_attempted"] = True
                    row["score"] = model.score_completion(grid_messages(deepcopy(demos[:-1]), deepcopy(demos[-1]["input"])),
                        encode_grid(demos[-1]["output"]), deadline=deadline)
                    row["scoring_receipt_complete"] = _receipt_ok(row["score"], generation=False)
                except Exception as exc:
                    row["errors"].append(_error(exc))
                    if any(item[0].pending for item in ledgers):
                        stop_all_new_neural_work = True
                        raise _StopNewNeuralWork("unknown scoring work; all new neural work stopped") from exc
    except Exception as exc:
        errors.append(_error(exc))
    finally:
        try:
            restored = trainer.restore_training_state(caller)
            require(restored.get("restored") is True and restored.get("complete_training_state") is True,
                    "exact complete caller restore required")
        finally:
            for handle in handles.values():
                try:
                    releases.append(trainer.release_snapshot(handle))
                except Exception as exc:
                    errors.append("release option: " + _error(exc))
            trainer.release_training_state(caller)

    for row in rows:
        row["complete"] = (row["adaptation_complete"] and row["generation_receipt_complete"] and
                           row["scoring_receipt_complete"] and bool(row["reset"] and row["reset"].get("restored")))
    # The fixed held-out completion must account for identical token counts.
    for key in chosen:
        group = [r for r in rows if r["task_id"] == key]
        counts = {(r["score"] or {}).get("token_count") for r in group if r["scoring_receipt_complete"]}
        if len(counts) > 1:
            for row in group:
                row["complete"] = False
                row["errors"].append("held-out target token count differs across options")
    matched = [key for key in chosen if all(r["complete"] for r in rows if r["task_id"] == key)]
    matched_options = [steps for steps in options if len(chosen) == count and
                       all(r["complete"] for r in rows if r["steps"] == steps)]
    usage = _observed_usage(rows, attempted, ledgers)
    complete = len(chosen) == count and len(matched) == count and not errors and usage["usage_known"]
    summaries = {}
    for steps in options:
        group = [r for r in rows if r["steps"] == steps]
        summary = {"denominator": count, "completed_rows": sum(r["complete"] for r in group),
                   **{key: sum(r[key] for r in group) for key in ("exact", "dimension_correct", "valid_grid")},
                   "mean_nll": sum(r["score"]["mean_nll"] for r in group) / len(chosen)
                               if len(chosen) == count and all(r["scoring_receipt_complete"] for r in group) else None,
                   "attempted_microbatches": sum(r["adaptation"]["attempted_microbatches"] for r in group
                       if type(r["adaptation"]) is dict and _integer(r["adaptation"].get("attempted_microbatches"))),
                   "optimizer_updates": sum(r["adaptation"]["optimizer_steps"] for r in group
                       if type(r["adaptation"]) is dict and _integer(r["adaptation"].get("optimizer_steps")))}
        summaries[str(steps)] = summary
    selected, candidates = 0, []
    if complete:
        def behavior(steps):
            return tuple(summaries[str(steps)][key] for key in ("exact", "dimension_correct", "valid_grid"))
        baseline = behavior(0)
        candidates = [steps for steps in options if steps and behavior(steps) > baseline and
                      behavior(steps)[0] >= baseline[0] and behavior(steps)[1] >= baseline[1]]
        if candidates:
            selected = min(candidates, key=lambda steps: tuple(-x for x in behavior(steps)) +
                           (summaries[str(steps)]["mean_nll"], steps))
    report = {"format": FORMAT, "selected_ttt_steps": selected,
              "status": "selected" if complete else "inconclusive-default-zero",
              "selection_reason": ("generated-behavior-improvement" if selected else
                                   "no-generated-improvement" if complete else "incomplete-fixed-comparison"),
              "predeclared_options": options, "predeclared_tasks": chosen,
              "complete_matched_tasks": matched, "complete_matched_options": matched_options,
              "comparison_complete": complete, "eligible_nonzero_options": candidates,
              "mean_nll": {key: value["mean_nll"] for key, value in summaries.items()},
              "option_metrics": summaries, "rows": rows, "usage": usage, "physical": deepcopy(usage),
              "metric": "held-out training-demo autoregressive exact, dimension, valid grid; NLL tie-break only after behavioral improvement",
              "policy": deepcopy(POLICY), "evidence": evidence, "errors": errors,
              "stop_all_new_neural_work": stop_all_new_neural_work,
              "public_answers_used": False, "public_accuracy_inferred": False,
              "manifest_sha256": manifest["manifest_sha256"], "seed": seed,
              "budgets": {"maximum_dev_tasks": count, "max_generation_calls": count * len(options),
                          "max_scoring_calls": count * len(options), "max_new_tokens": cap,
                          "maximum_attempted_microbatches": count * sum(options),
                          "maximum_option_snapshot_handles": 12},
              "peak_option_snapshot_handles": peak_handles, "released_option_snapshots": len(releases),
              "reset": restored, "elapsed_seconds": time.monotonic() - started}
    report = _portable(report)
    atomic_json(Path(output) / "dev-selection.json", report, exclusive=True)
    return report

"""Post-exit, gold-free reconciliation of the owned leaf's atomic evidence.

This is an integrity audit, not execution attestation. It never loads a model,
reads labels, or imports an evaluator. Raw backend results are counted once per
trace start, even where admission costs also occur in aggregate projections.
Malformed/partial evidence returns a fail-closed ledger, not an empty cost bill.
"""
from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
import re

from tools.public_demo_calibration import core
from tools.public_sft141_diagnostic import contract
from tools.public_sft141_submission.files import load_json

SCHEMA = "public-calibrated-operation-audit-v1"
LABELS = ("short", "median", "longest")
MEMORY = ("allocated_bytes", "reserved_bytes", "peak_allocated_bytes", "peak_reserved_bytes",
          "free_bytes", "total_bytes")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _equal(a, b):
    try:
        return core.digest(a) == core.digest(b)
    except (TypeError, ValueError):
        return False


def _near(a, b):
    return _number(a) and _number(b) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-9)


def _bucket():
    return {"attempted": 0, "completed": 0, "failed": 0, "unknown": 0,
            "measured_seconds": 0.0, "observed_call_wall_seconds": 0.0,
            "prompt_tokens": 0, "input_tokens": 0, "answer_tokens": 0,
            "generated_tokens": 0, "cost_unknown_calls": 0, "memory_peaks": {}}


def _queries(plan):
    out = []
    for parent in plan["parents"]:
        for query in parent["test"]:
            prompts = [contract.prompt_ids(parent["train"], query["input"], v) for v in range(8)]
            out.append({"task_id": parent["task_id"], "test_index": query["test_index"],
                        "query_id": query["query_id"], "prompts": prompts,
                        "prompt_tokens_by_view": list(map(len, prompts)),
                        "views": [{"view": v, "status": "missing"} for v in range(8)],
                        "candidates": [], "vote_complete": False})
    return out


def _rank(query):
    candidates = {}
    for row in query["views"]:
        if row.get("status") == "complete" and row.get("valid"):
            grid = contract.inverse(contract.parse_answer(row["token_ids"]), row["view"])
            key = core._key(grid)
            candidate = candidates.setdefault(key, {"canonical_key": key, "grid": grid, "count": 0,
                "view_nll": [{"view": v, "status": "missing"} for v in range(8)],
                "mean_nll": None, "combined_score": None})
            candidate["count"] += 1
    query["candidates"] = sorted(candidates.values(), key=lambda row: row["canonical_key"])
    query["vote_complete"] = all(row.get("status") == "complete" for row in query["views"])
    query["vote"] = [c["grid"] for c in sorted(query["candidates"], key=lambda c: (-c["count"], c["canonical_key"]))[:2]]


def _generation(result, prompt):
    row = copy.deepcopy(result)
    tokens = row.get("token_ids")
    if not isinstance(tokens, list) or any(type(t) is not int for t in tokens) or len(tokens) > contract.MAX_NEW_TOKENS:
        raise ValueError("generation result lacks bounded raw integer tokens")
    if not _number(row.get("seconds")) or row.get("generated_tokens") != len(tokens):
        raise ValueError("generation timing/count mismatch")
    if row.get("termination") not in ("eos", "deadline", "max_tokens"):
        raise ValueError("unknown generation termination")
    if (row["termination"] == "eos") != bool(tokens and tokens[-1] == contract.EOS_ID):
        raise ValueError("generation termination/EOS mismatch")
    row.update(prompt_tokens=len(prompt), prompt_sha256=core.digest(prompt),
        max_new_tokens=contract.MAX_NEW_TOKENS, generated_tokens=len(tokens),
        eos_seen=contract.EOS_ID in tokens, truncated=not (tokens and tokens[-1] == contract.EOS_ID),
        valid=False, grid=None)
    try:
        row["grid"] = contract.parse_answer(tokens)
        row.update(valid=True, parse_error=None)
    except ValueError as exc:
        row["parse_error"] = str(exc)
    return row


def _score(result, prompt, answer):
    row = copy.deepcopy(result)
    if not _number(row.get("seconds")) or not _number(row.get("nll")):
        raise ValueError("invalid backend score cost/NLL")
    if (row.get("input_tokens") != len(prompt) + len(answer) - 1 or
            row.get("answer_tokens") != len(answer) or row.get("batch_size") != 1 or
            row.get("use_cache") is not False):
        raise ValueError("backend full-answer/cache/batch counters differ from plan")
    row.update(prompt_tokens=len(prompt), answer_tokens=len(answer), input_tokens=len(prompt) + len(answer) - 1,
        prompt_sha256=core.digest(prompt), answer_sha256=core.digest(answer), includes_eos=True,
        normalization="sum-not-token-mean")
    return row


def _projection(queries, generation, scores, stage):
    """Independently recompute the deterministic, non-clock projection fields."""
    eos = [r for r in generation if not r["truncated"]]
    observed = eos or generation
    if not observed or not scores:
        raise ValueError("projection before measured admission costs")
    def nearest(rows, field, target):
        return min(rows, key=lambda r: (abs(r[field] - target), -r["seconds"]))
    def scaled(r, target):
        return r["seconds"] * max(1.0, target / max(1, r["input_tokens"])) ** 2
    missing = [(q, v) for q in queries for v in range(8) if q["views"][v]["status"] == "missing"]
    gen_est, gen_max, score_est, score_max, count = 0.0, 0.0, 0.0, 0.0, 0
    rate = max(r["seconds"] / max(1, r["generated_tokens"]) for r in generation)
    max_prompt = max(r["prompt_tokens"] for r in generation)
    for q, v in missing:
        length = len(q["prompts"][v])
        row = nearest(observed, "prompt_tokens", length)
        gen_est += row["seconds"] * max(1.0, length / max(1, row["prompt_tokens"]))
        gen_max += rate * contract.MAX_NEW_TOKENS * max(1.0, length / max_prompt)
    for q in queries:
        if q["vote_complete"]:
            for c in q["candidates"]:
                for v in range(8):
                    if c["view_nll"][v]["status"] == "complete":
                        continue
                    length = len(q["prompts"][v])
                    target = length + len(contract.answer_ids(contract.transform(c["grid"], v))) - 1
                    count += 1
                    score_est += scaled(nearest(scores, "input_tokens", target), target)
                    score_max += max(scaled(r, length + contract.MAX_NEW_TOKENS - 1) for r in scores)
        else:
            for v in range(8):
                length = len(q["prompts"][v])
                target = length + nearest(observed, "prompt_tokens", length)["generated_tokens"] - 1
                count += 8
                score_est += 8 * scaled(nearest(scores, "input_tokens", target), target)
                score_max += 8 * max(scaled(r, length + contract.MAX_NEW_TOKENS - 1) for r in scores)
    return {"stage": stage, "remaining_generation_calls": len(missing), "remaining_score_calls_upper_bound": count,
        "measured_generation_calls": len(generation), "measured_score_calls": len(scores),
        "measured_generation_seconds": sum(r["seconds"] for r in generation),
        "measured_scoring_seconds": sum(r["seconds"] for r in scores),
        "estimated_generation_seconds": gen_est, "estimated_scoring_seconds": score_est,
        "safety_factor": 1.25, "estimated_remaining_work_seconds": 1.25 * (gen_est + score_est),
        "worst_case_envelope_seconds": 1.25 * (gen_max + score_max),
        "worst_case_generation_seconds": gen_max, "worst_case_scoring_seconds": score_max,
        "observed_eos_calibration_calls": len(eos),
        "admission_basis": "measured-completed-EOS-calibration-not-worst-case-envelope" if eos else "measured-capped-generation-no-valid-EOS-observed"}


def audit(plan, calibration, base_result, worker_path, session_complete):
    """Return a deterministic full ledger. Call only after the owned worker exits.

    ``audit_passed`` means all available evidence reconciles. ``strict_complete``
    additionally requires complete planned operations and a complete session.
    Unknown/failed work remains visible and must never be assigned zero cost.
    The caller independently establishes process exit and seals these files.
    """
    root = Path(worker_path)
    errors, traces, files, raw_bytes = [], [], {}, {}
    ledger = {"schema": SCHEMA, "audit_passed": False, "strict_complete": False,
        "session_complete": session_complete, "errors": errors, "operations": [],
        "by_phase": {}, "by_category": {}, "totals": _bucket(),
        "untraced_raw_receipts": [], "unbound_finished_operations": [],
        "integrity_only_not_execution_attestation": True, "evaluator_imported": False,
        "timings_counted_once_per_trace_start": True, "scientific_effectiveness_established": False}
    def check(condition, message):
        if not condition:
            errors.append(message)
        return bool(condition)
    def guarded(label, fn, default=None):
        try:
            return fn()
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
            return default
    def read(relative):
        path = root / relative
        if not path.exists() and not path.is_symlink():
            return None
        def get():
            value, raw = load_json(path)
            raw_bytes[relative] = raw
            return value
        return guarded(relative, get)
    for directory, pattern in (("receipts", r"(?:trace-\d{5}|bound-view-\d{4}-[0-7])\.json"),
            ("calibration/receipts", r"loo-\d{5}\.json"),
            ("generation/receipts", r"(?:admission-(?:short|median|longest)-(?:generation|scoring)|view-\d{4}-[0-7]|nll-\d{4}-\d+-[0-7]|projection-\d{4})\.json")):
        directory_path = root / directory
        if directory_path.is_symlink():
            errors.append("linked receipt directory: " + directory)
            continue
        for path in sorted(directory_path.glob("*")):
            if path.name.startswith(".pending-"):
                # A killed atomic writer can leave its unpublished temporary file.
                check(not session_complete, "complete session has unpublished temporary receipt")
                continue
            relative = directory + "/" + path.name
            check(bool(re.fullmatch(pattern, path.name)), "unexpected raw receipt path: " + relative)
            files[relative] = read(relative)
    trace_paths = sorted(p for p in files if p.startswith("receipts/trace-"))
    for index, path in enumerate(trace_paths, 1):
        row = files[path]
        if not check(isinstance(row, dict), "invalid trace object: " + path):
            continue
        check(path == f"receipts/trace-{index:05d}.json" and type(row.get("event")) is int and row["event"] == index,
              "trace sequence missing, duplicate, or filename/event mismatch: " + path)
        traces.append(row)
    ledger["trace_events"] = len(traces)
    check(type(session_complete) is bool, "session_complete must be boolean")
    original = traces[0].get("original_started_monotonic") if traces else None
    previous, active, load_start, load_finish, freeze_event = -1.0, None, None, None, None
    starts, terminals, published = [], {}, {}
    for row in traces:
        event, kind, phase = row.get("event"), row.get("kind"), row.get("phase")
        check(_number(row.get("elapsed_seconds")) and row["elapsed_seconds"] >= previous,
              f"trace {event}: elapsed clock regressed or is invalid")
        if _number(row.get("elapsed_seconds")):
            previous = row["elapsed_seconds"]
        check(_number(original) and _equal(row.get("original_started_monotonic"), original),
              f"trace {event}: original monotonic clock changed")
        if kind == "model_load_start":
            check(load_start is None and not starts and freeze_event is None and phase == "load", "model load is duplicated or reordered")
            load_start = row
        elif kind == "model_load_finished":
            check(load_start is not None and load_finish is None and phase == "load" and row.get("model_load_count") == 1,
                  "model load terminal is missing/duplicated/reordered")
            load_finish = row
        elif kind == "calibration_frozen":
            check(load_finish is not None and freeze_event is None and active is None and phase == "calibration",
                  "calibration freeze is duplicated or out of order")
            freeze_event = row
        elif kind == "operation_start":
            check(load_finish is not None and active is None, f"trace {event}: operation before load or overlapping call")
            check(row.get("operation") in ("score", "generate"), f"trace {event}: unknown operation")
            expected_phase = "task_test" if freeze_event is not None else "calibration"
            check(phase == expected_phase and (phase != "calibration" or row.get("operation") == "score"),
                  f"trace {event}: operation crossed frozen calibration boundary")
            check(row.get("operation") != "generate" or row.get("answer_sha256") is None,
                  f"trace {event}: generation unexpectedly has answer hash")
            starts.append(row)
            active = event
        elif kind in ("operation_finished", "operation_failed"):
            start_event = row.get("start_event")
            check(active is not None and start_event == active and start_event not in terminals,
                  f"trace {event}: terminal lacks its unique active start")
            start = next((s for s in reversed(starts) if s.get("event") == start_event), None)
            check(start is not None and phase == start.get("phase") and row.get("operation") == start.get("operation"),
                  f"trace {event}: terminal operation/phase differs from start")
            if type(start_event) is int:
                terminals[start_event] = row
            if kind == "operation_finished":
                check(isinstance(row.get("result"), dict) and _equal(row.get("result_sha256"), guarded("result digest", lambda: core.digest(row.get("result")))),
                      f"trace {event}: raw backend result/hash mismatch")
                check(type(row.get("late")) is bool, f"trace {event}: missing late flag")
            else:
                check(row.get("cost_unknown") is True, f"trace {event}: failed call must retain unknown cost")
            active = None
        elif kind == "raw_view_published":
            relative = row.get("relative")
            check(freeze_event is not None and phase == "task_test" and active is None,
                  f"trace {event}: raw view publication before freeze or call completion")
            check(isinstance(relative, str) and relative not in published, f"trace {event}: duplicate raw view publication")
            if isinstance(relative, str):
                published[relative] = row
        else:
            errors.append(f"trace {event}: unknown event kind {kind!r}")
    ledger["original_started_monotonic"] = original
    ledger["last_trace_elapsed_seconds"] = previous if traces else None
    check(not session_complete or active is None, "complete session has an unterminated operation")
    check(not starts or load_finish is not None, "operations lack completed model load")
    freeze = read("calibration_freeze.json")
    calibration_file = read("calibration/calibration.json")
    if freeze_event is not None:
        check(isinstance(freeze, dict), "freeze trace lacks atomic calibration freeze receipt")
        if isinstance(freeze, dict):
            check(freeze.get("event") == freeze_event.get("event") and freeze.get("calibration_sha256") == core.digest(calibration)
                  and freeze_event.get("calibration_sha256") == core.digest(calibration), "calibration freeze digest/event differs")
            check("calibration/calibration.json" in raw_bytes and freeze.get("calibration_file_sha256") == hashlib.sha256(raw_bytes.get("calibration/calibration.json", b"")).hexdigest(), "frozen calibration byte hash differs")
            check(_equal(calibration_file, calibration), "supplied calibration differs from frozen worker aggregate")
    else:
        check(freeze is None, "orphan calibration freeze receipt")
    valid_plan = guarded("gold-free plan", lambda: (core.validate_gold_free(plan), True)[1], False)
    cases = guarded("LOO schedule", lambda: core.cases(plan), []) if valid_plan else []
    queries = guarded("query schedule", lambda: _queries(plan), []) if valid_plan else []
    guarded("calibration contract", lambda: core.validate_calibration(plan, calibration))
    kind = calibration.get("execution_kind") if isinstance(calibration, dict) else None
    expected_loo = 256 if kind == "public_model" else 192 if kind == "synthetic_cpu" else None
    check(expected_loo is not None and len(cases) == expected_loo, "fixed experiment LOO count/execution kind differs")
    check(len(queries) == 15, "fixed experiment requires fifteen true test queries")
    loo_paths = sorted(p for p in files if p.startswith("calibration/receipts/loo-"))
    raw_loo = [files[p] for p in loo_paths]
    for i, path in enumerate(loo_paths):
        check(path == f"calibration/receipts/loo-{i:05d}.json", "noncontiguous/duplicate LOO receipt filename")
        row = files[path]
        check(isinstance(row, dict) and i < len(cases) and _equal(row.get("spec"), cases[i][0]) and row.get("event") == i,
              "LOO raw receipt is not the chronological planned case: " + path)
    check(isinstance(calibration, dict) and _equal(calibration.get("rows"), raw_loo), "calibration aggregate rows differ from raw receipts")
    expected, by_path = [], {}
    def add(path, phase, category, operation, prompt, answer=None, identity=None):
        item = {"path": path, "phase": phase, "category": category, "operation": operation,
                "prompt": prompt, "answer": answer, "identity": identity or {}}
        expected.append(item)
        by_path[path] = item
        return item
    calibration_starts = [s for s in starts if s.get("phase") == "calibration"]
    # Before freeze, calibration follows the full deterministic LOO sequence.
    for i, (spec, prompt, answer) in enumerate(cases[:max(len(raw_loo), len(calibration_starts))]):
        add(f"calibration/receipts/loo-{i:05d}.json", "calibration", "calibration_score", "score", prompt, answer, {"spec": spec, "event": i})
    task_expected = []
    if any(s.get("phase") == "task_test" for s in starts):
        check(isinstance(calibration, dict) and calibration.get("status") == "complete" and len(raw_loo) == expected_loo,
              "task.test operations started without complete frozen calibration")
    if queries:
        ordered = sorted(enumerate(queries), key=lambda pair: (max(pair[1]["prompt_tokens_by_view"]), pair[1]["query_id"]))
        for label, (qi, query) in zip(LABELS, (ordered[0], ordered[len(ordered)//2], ordered[-1])):
            view = max(range(8), key=lambda v: query["prompt_tokens_by_view"][v])
            identity = {"length_class": label, "query_id": query["query_id"], "query_index": qi,
                        "view": view, "prompt_tokens_by_view": query["prompt_tokens_by_view"]}
            p = f"generation/receipts/admission-{label}-generation.json"
            task_expected.append(add(p, "task_test", "admission_generation", "generate", query["prompts"][view], identity=identity))
            raw = files.get(p)
            answer = raw.get("token_ids") if isinstance(raw, dict) and raw.get("status") == "complete" and raw.get("valid") else contract.answer_ids([[0]*30 for _ in range(30)])
            source = "full-generated-answer-cost-calibration" if isinstance(raw, dict) and raw.get("status") == "complete" and raw.get("valid") else "synthetic-30x30-zero-grid-cost-only"
            p = f"generation/receipts/admission-{label}-scoring.json"
            task_expected.append(add(p, "task_test", "admission_score", "score", query["prompts"][view], answer,
                {"status": "complete", "query_id": query["query_id"], "view": view, "source": source, "length_class": label}))
        for qi, query in enumerate(queries):
            for view in range(8):
                p = f"generation/receipts/view-{qi:04d}-{view}.json"
                task_expected.append(add(p, "task_test", "panel_generation", "generate", query["prompts"][view],
                    identity={"query_id": query["query_id"], "view": view}))
                raw = files.get(p)
                if isinstance(raw, dict):
                    query["views"][view] = raw
            guarded("candidate derivation " + query["query_id"], lambda q=query: _rank(q))
        for qi, query in enumerate(queries):
            for ci, candidate in enumerate(query["candidates"]):
                for view in range(8):
                    p = f"generation/receipts/nll-{qi:04d}-{ci}-{view}.json"
                    task_expected.append(add(p, "task_test", "panel_rescoring", "score", query["prompts"][view],
                        contract.answer_ids(contract.transform(candidate["grid"], view)),
                        {"query_id": query["query_id"], "candidate_index": ci, "view": view}))
                    raw = files.get(p)
                    if isinstance(raw, dict):
                        candidate["view_nll"][view] = raw
    expected_by_phase = {"calibration": [e for e in expected if e["phase"] == "calibration"], "task_test": task_expected}
    phase_indices, bound_paths = {"calibration": 0, "task_test": 0}, set()
    for index, start in enumerate(starts):
        phase, event = start.get("phase"), start.get("event")
        position = phase_indices.get(phase, 0)
        options = expected_by_phase.get(phase, [])
        planned = options[position] if position < len(options) else None
        phase_indices[phase] = position + 1
        terminal = terminals.get(event)
        state = "unknown" if terminal is None else "completed" if terminal.get("kind") == "operation_finished" else "failed"
        result = terminal.get("result") if terminal and state == "completed" else None
        if state in ("failed", "unknown"):
            check(index == len(starts)-1, "another operation follows an interrupted or failed call")
        row = {"start_event": event, "terminal_event": terminal.get("event") if terminal else None,
               "phase": phase, "operation": start.get("operation"), "state": state,
               "category": planned["category"] if planned else "unplanned",
               "raw_receipt": planned["path"] if planned else None,
               "cost_unknown": state != "completed" or not isinstance(result, dict),
               "result_sha256": terminal.get("result_sha256") if terminal else None}
        ledger["operations"].append(row)
        check(planned is not None, f"trace {event}: extra unplanned operation")
        if planned:
            check(start.get("operation") == planned["operation"] and start.get("prompt_sha256") == core.digest(planned["prompt"])
                  and start.get("answer_sha256") == (core.digest(planned["answer"]) if planned["answer"] is not None else None),
                  f"trace {event}: chronological operation prompt/answer differs from plan")
            raw = files.get(planned["path"])
            if raw is not None:
                bound_paths.add(planned["path"])
            if raw is None:
                ledger["unbound_finished_operations"].append(event) if state == "completed" else None
                check(not session_complete and index == len(starts)-1, f"trace {event}: nonfinal or complete operation lacks raw receipt")
            elif isinstance(raw, dict):
                check(raw.get("status") in ("complete", "failed"), "invalid raw status: " + planned["path"])
                if raw.get("status") == "failed":
                    for field, value in planned["identity"].items():
                        if field != "status":
                            check(_equal(raw.get(field), value), "failed raw receipt identity differs: " + planned["path"] + ":" + field)
                    check(index == len(starts)-1, "another operation follows a failed raw receipt")
                if state == "failed":
                    check(raw.get("status") == "failed", "failed trace promoted to completed raw receipt")
                elif state == "unknown":
                    check(False, "unterminated trace has a published raw operation receipt")
                elif isinstance(result, dict) and raw.get("status") == "complete":
                    def reconstructed():
                        if phase == "calibration":
                            _score(result, planned["prompt"], planned["answer"])
                            return core.complete_row(planned["identity"]["spec"], result["nll"], result["seconds"], planned["identity"]["event"], result.get("memory"))
                        output = _generation(result, planned["prompt"]) if planned["operation"] == "generate" else _score(result, planned["prompt"], planned["answer"])
                        output.update(planned["identity"], status="complete")
                        if planned["category"] == "panel_generation":
                            output["canonical_grid"] = contract.inverse(output["grid"], output["view"]) if output["valid"] else None
                        return output
                    want = guarded("raw result reconstruction " + planned["path"], reconstructed)
                    check(want is not None and _equal(raw, want), "raw receipt differs from trace backend result: " + planned["path"])
                elif raw.get("status") == "failed":
                    row["raw_validation_failed"] = True
                if raw.get("status") == "failed":
                    row["failure_wall_seconds"] = raw.get("seconds") if _number(raw.get("seconds")) else None
        if terminal is not None and _number(terminal.get("elapsed_seconds")) and _number(start.get("elapsed_seconds")):
            row["observed_call_wall_seconds"] = max(0.0, terminal["elapsed_seconds"] - start["elapsed_seconds"])
        for name in ("seconds", "input_tokens", "answer_tokens", "generated_tokens"):
            if isinstance(result, dict) and _number(result.get(name)):
                row["measured_seconds" if name == "seconds" else name] = result[name]
        if isinstance(result, dict) and planned:
            row["prompt_tokens"] = len(planned["prompt"])
            if planned["operation"] == "generate":
                # Prefill input is the complete prompt. Decode work is reported
                # separately as generated tokens, not invented teacher forcing.
                row["input_tokens"] = len(planned["prompt"])
            row["memory"] = result.get("memory")
            if not _number(result.get("seconds")):
                row["cost_unknown"] = True
        if state == "failed" and planned and isinstance(files.get(planned["path"]), dict):
            row["memory"] = files[planned["path"]].get("memory")
        targets = [ledger["totals"], ledger["by_phase"].setdefault(str(phase), _bucket()), ledger["by_category"].setdefault(row["category"], _bucket())]
        for target in targets:
            target["attempted"] += 1
            target[state] += 1
            target["cost_unknown_calls"] += int(row["cost_unknown"])
            for field in ("measured_seconds", "observed_call_wall_seconds", "prompt_tokens", "input_tokens", "answer_tokens", "generated_tokens"):
                target[field] += row.get(field, 0)
            memory = row.get("memory")
            if isinstance(memory, dict):
                for field, value in memory.items():
                    if field in MEMORY and type(value) is int and value >= 0:
                        target["memory_peaks"][field] = max(target["memory_peaks"].get(field, 0), value)
                    elif field != "unavailable":
                        check(False, f"trace {event}: invalid memory metric {field}")
    for path, raw in files.items():
        if (path.startswith("calibration/receipts/") or path.startswith("generation/receipts/") and not "/projection-" in path) and path not in bound_paths:
            ledger["untraced_raw_receipts"].append(path)
            # A failed calibration deadline preflight can produce a final row
            # without invoking the backend. It is not a forward-call receipt.
            preflight = path.startswith("calibration/receipts/") and isinstance(raw, dict) and raw.get("status") == "failed" and path == (loo_paths[-1] if loo_paths else None) and raw.get("event") == len(calibration_starts)
            check(preflight and not session_complete, "orphan or duplicate raw operation receipt: " + path)
    ledger["raw_preflight_or_untraced_failure_seconds"] = sum(files[p].get("seconds", 0) for p in ledger["untraced_raw_receipts"] if isinstance(files.get(p), dict) and _number(files[p].get("seconds")))
    # Every scientific raw view is bound to its trace publication and the
    # immutable calibration, not merely a caller-controlled aggregate row.
    for path in [p for p in files if p.startswith("generation/receipts/view-")]:
        relative = path[len("generation/"):]
        publication, bound = published.get(relative), files.get("receipts/bound-" + Path(path).name)
        if publication is None or bound is None:
            check(not session_complete and starts and path == ledger["operations"][-1].get("raw_receipt"), "raw view lacks publication/calibration binding: " + path)
            continue
        check(isinstance(bound, dict) and isinstance(freeze, dict) and bound.get("event") == publication.get("event") and
              bound.get("raw_sha256") == hashlib.sha256(raw_bytes[path]).hexdigest() and
              bound.get("calibration_sha256") == core.digest(calibration) and
              publication.get("calibration_sha256") == core.digest(calibration) and
              bound.get("source_identity_sha256") == freeze.get("source_identity_sha256") and type(bound.get("late")) is bool,
              "raw view binding mismatch: " + path)
        op = next((r for r in ledger["operations"] if r["raw_receipt"] == path), None)
        if op:
            check(op["terminal_event"] is not None and publication["event"] > op["terminal_event"], "view publication precedes operation terminal")
            later = next((r for r in ledger["operations"] if type(r["start_event"]) is int and r["start_event"] > op["start_event"]), None)
            check(later is None or publication["event"] < later["start_event"], "view publication occurs after the next operation")
    for relative in published:
        check("generation/" + relative in files, "orphan raw-view publication: " + relative)
    for path in files:
        if path.startswith("receipts/bound-"):
            check("generation/receipts/" + Path(path).name[len("bound-"):] in files, "orphan raw-view binding: " + path)
    declared = read("generation/result.json")
    if declared is not None:
        check(_equal(declared, base_result), "supplied base_result differs from worker result.json")
    else:
        check(not session_complete, "complete session lacks base result aggregate")
    def reconcile_aggregate():
        rows = base_result.get("queries", [])
        check(len(rows) == len(queries), "base aggregate query count differs")
        for query, row in zip(queries, rows):
            for field in ("task_id", "query_id", "test_index", "views", "vote", "vote_complete"):
                check(_equal(row.get(field), query.get(field)), "base aggregate/raw query differs: " + query["query_id"] + ":" + field)
            if "prompt_tokens_by_view" in row:
                check(_equal(row["prompt_tokens_by_view"], query["prompt_tokens_by_view"]), "base aggregate prompt lengths differ")
            check(len(row.get("candidates", [])) == len(query["candidates"]), "candidate inventory differs")
            for raw_c, agg_c in zip(query["candidates"], row.get("candidates", [])):
                for field in ("canonical_key", "grid", "count", "view_nll"):
                    check(_equal(raw_c[field], agg_c.get(field)), "candidate raw/aggregate differs: " + field)
                ready = all(r.get("status") == "complete" for r in raw_c["view_nll"])
                mean = sum(r["nll"] for r in raw_c["view_nll"]) / 8 if ready else None
                if agg_c.get("mean_nll") is not None or session_complete:
                    check(_equal(agg_c.get("mean_nll"), mean) and _equal(agg_c.get("combined_score"), raw_c["count"]-mean if mean is not None else None), "candidate mean/combined score differs")
            if row.get("rescoring_complete"):
                check(query["vote_complete"] and all(all(r.get("status") == "complete" for r in c["view_nll"]) for c in query["candidates"]), "rescoring completion exceeds raw evidence")
                ranked = sorted(query["candidates"], key=lambda c: (-(c["count"] - sum(r["nll"] for r in c["view_nll"])/8), c["canonical_key"]))
                check(_equal(row.get("rescored"), [c["grid"] for c in ranked[:2]]), "rescored ranking differs from raw evidence")
        if declared is None:
            return
        admission = []
        for label in LABELS:
            raw = files.get(f"generation/receipts/admission-{label}-generation.json")
            if raw is not None:
                row = copy.deepcopy(raw)
                score = files.get(f"generation/receipts/admission-{label}-scoring.json")
                if score is not None:
                    row["scoring_receipt"] = score
                admission.append(row)
        check(_equal(base_result.get("context_admission"), admission), "base context_admission/scoring_receipt differs from atomic receipts")
        views = [r for q in queries for r in q["views"]]
        counts = {"queries": len(queries), "expected_views": 8*len(queries),
            "missing_views": sum(r["status"] == "missing" for r in views), "failed_views": sum(r["status"] == "failed" for r in views),
            "invalid_views": sum(r["status"] == "complete" and not r["valid"] for r in views),
            "truncated_views": sum(r.get("truncated", False) for r in views), "valid_views": sum(r.get("valid", False) for r in views),
            "vote_complete_queries": sum(q["vote_complete"] for q in queries),
            "rescoring_complete_queries": sum(q.get("rescoring_complete", False) for q in rows)}
        check(_equal(base_result.get("counts"), counts), "base counts differ from raw receipts")
        timings = {"admission_generation_seconds": sum(r.get("seconds", 0.0) for r in admission),
            "admission_scoring_seconds": sum(r.get("scoring_receipt", {}).get("seconds", 0.0) for r in admission),
            "panel_generation_seconds": sum(r.get("seconds", 0.0) for r in views),
            "panel_rescoring_seconds": sum(r.get("seconds", 0.0) for q in queries for c in q["candidates"] for r in c["view_nll"])}
        check(_equal(base_result.get("timings"), timings), "base timings differ from once-counted raw rows")
        check(base_result.get("full_panel_complete") == (base_result.get("status") == "complete" and all(q.get("vote_complete") and q.get("rescoring_complete") for q in rows)), "base full_panel_complete disagrees with raw completion")
    guarded("base aggregate reconciliation", reconcile_aggregate)
    projection_paths = sorted(p for p in files if p.startswith("generation/receipts/projection-"))
    projections = [files[p] for p in projection_paths]
    for i, path in enumerate(projection_paths):
        check(path == f"generation/receipts/projection-{i:04d}.json", "noncontiguous or duplicate projection receipt")
    if declared is not None:
        check(_equal(declared.get("projections"), projections), "aggregate projections differ from atomic projections")
    def reconcile_projections():
        simulated, generation, scores, expected_projections = _queries(plan), [], [], []
        for label in LABELS:
            gen = files.get(f"generation/receipts/admission-{label}-generation.json")
            score = files.get(f"generation/receipts/admission-{label}-scoring.json")
            if not isinstance(gen, dict) or gen.get("status") != "complete" or gen.get("termination") == "deadline" or not isinstance(score, dict) or score.get("status") != "complete":
                break
            generation.append(gen)
            scores.append(score)
        if len(scores) == 3:
            expected_projections.append(_projection(simulated, generation, scores, "after_admission"))
            for qi, q in enumerate(simulated):
                for view in range(8):
                    raw = files.get(f"generation/receipts/view-{qi:04d}-{view}.json")
                    if not isinstance(raw, dict) or raw.get("status") != "complete":
                        continue
                    q["views"][view] = raw
                    _rank(q)
                    generation.append(raw)
                    if raw.get("termination") != "deadline":
                        expected_projections.append(_projection(simulated, generation, scores, "panel_generation"))
            for qi, q in enumerate(simulated):
                for ci, c in enumerate(q["candidates"]):
                    for view in range(8):
                        raw = files.get(f"generation/receipts/nll-{qi:04d}-{ci}-{view}.json")
                        if not isinstance(raw, dict) or raw.get("status") != "complete":
                            continue
                        c["view_nll"][view] = raw
                        scores.append(raw)
                        expected_projections.append(_projection(simulated, generation, scores, "panel_rescoring"))
        check(len(projections) == len(expected_projections) or not session_complete and len(projections) == max(0, len(expected_projections)-1), "projection inventory differs from completed operations")
        last_elapsed = -1.0
        for raw, expected_projection in zip(projections, expected_projections):
            for field, value in expected_projection.items():
                check(_near(raw.get(field), value) if type(value) is float else _equal(raw.get(field), value), "projection recomputation differs: " + field)
            remaining = raw.get("work_remaining_seconds")
            check(_number(remaining), "projection lacks measured remaining budget")
            if _number(remaining):
                check(raw.get("fits") == (expected_projection["estimated_remaining_work_seconds"] <= remaining) and
                      raw.get("generation_fits") == (1.25*expected_projection["estimated_generation_seconds"] <= remaining) and
                      raw.get("worst_case_fits") == (expected_projection["worst_case_envelope_seconds"] <= remaining), "projection fits flags differ")
            elapsed = raw.get("observed_elapsed_seconds")
            check(_number(elapsed) and elapsed >= last_elapsed, "projection elapsed clock regressed")
            if _number(elapsed):
                last_elapsed = elapsed
            budget = base_result.get("budget", {}) if isinstance(base_result, dict) else {}
            if _number(budget.get("budget_seconds")) and _number(elapsed) and _number(remaining):
                reserve = min(120.0, max(15.0, budget["budget_seconds"]*.02))
                check(raw.get("closure_reserve_seconds") == reserve and abs(remaining-max(0.0, budget["budget_seconds"]-reserve-elapsed)) < .1, "projection does not use original budget clock/reserve")
    guarded("projection reconciliation", reconcile_projections)
    load = _bucket()
    load["attempted"] = int(load_start is not None)
    load["completed"] = int(load_finish is not None)
    load["unknown"] = int(load_start is not None and load_finish is None)
    load["cost_unknown_calls"] = load["unknown"]
    if load_start and load_finish and _number(load_start.get("elapsed_seconds")) and _number(load_finish.get("elapsed_seconds")):
        load["observed_call_wall_seconds"] = load_finish["elapsed_seconds"] - load_start["elapsed_seconds"]
        backend = load_finish.get("backend", {})
        if isinstance(backend, dict) and _number(backend.get("load_seconds")):
            load["measured_seconds"] = backend["load_seconds"]
        else:
            load["measured_seconds"] = load["observed_call_wall_seconds"]
        if declared is not None:
            check(_equal(declared.get("backend"), backend), "base aggregate/backend model-load metadata differs")
    ledger["model_load"] = load
    ledger["by_phase"]["load"] = copy.deepcopy(load)
    ledger["expected"] = {"model_loads": 1, "calibration_scores": expected_loo,
        "admission_generations": 3, "admission_scores": 3, "scientific_generations": 120,
        "distinct_candidates": sum(len(q["candidates"]) for q in queries),
        "candidate_scores": 8*sum(len(q["candidates"]) for q in queries)}
    ledger["admission_costs"] = {name: copy.deepcopy(ledger["by_category"].get(name, _bucket())) for name in ("admission_generation", "admission_score")}
    ledger["projection_receipts"] = len(projections)
    ledger["costs_unknown"] = bool(ledger["totals"]["cost_unknown_calls"] or load["cost_unknown_calls"] or ledger["untraced_raw_receipts"])
    ledger["measured_model_and_operation_seconds"] = load["measured_seconds"] + ledger["totals"]["measured_seconds"]
    complete_counts = {"calibration_score": expected_loo, "admission_generation": 3, "admission_score": 3,
                       "panel_generation": 120, "panel_rescoring": ledger["expected"]["candidate_scores"]}
    inventory_complete = load["attempted"] == load["completed"] == 1 and freeze_event is not None
    for name, count in complete_counts.items():
        bucket = ledger["by_category"].get(name, _bucket())
        ready = count is not None and bucket["attempted"] == bucket["completed"] == count and bucket["failed"] == bucket["unknown"] == 0
        inventory_complete = inventory_complete and ready
        if session_complete:
            check(ready, "complete session lacks exact planned operation inventory: " + name)
    if session_complete:
        check(load["attempted"] == load["completed"] == 1 and freeze_event is not None, "complete session lacks exactly one model load and freeze")
        check(isinstance(calibration, dict) and calibration.get("status") == "complete" and len(raw_loo) == expected_loo, "complete session lacks all LOO raw receipts")
        check(isinstance(base_result, dict) and base_result.get("full_panel_complete") is True, "complete session lacks complete base panel")
        check(not any(t.get("late") is True for t in terminals.values()) and not any(isinstance(r, dict) and r.get("late") is True for p, r in files.items() if p.startswith("receipts/bound-")), "complete session contains late operation/view")
    ledger["audit_passed"] = not errors
    ledger["strict_complete"] = bool(session_complete and inventory_complete and not errors and not ledger["costs_unknown"])
    return ledger

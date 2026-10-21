"""Gold-free plans, immutable records, and deterministic raw-token reconstruction."""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import time

from tools.public_sft141_diagnostic import contract as codec
from tools.public_sft141_submission import contract as wire
from tools.public_sft141_submission import files

SCHEMA = "iris-public-sft141-solver-v1"
CONTEXT_CAP = 8192
SCHEDULER = {
    "name": "view-major-round-robin-v1", "views": list(range(8)),
    "query_order": "original-task-insertion-order-then-original-test-index",
    "max_new_tokens": 931, "context_cap": CONTEXT_CAP,
    "supports": "all-visible-train-in-original-order", "context_overflow": "skip-entire-affected-query",
    "ranking": "uniform-occurrence-count-descending-then-base-grid-json-lexical",
    "partial_views": "allowed-and-labelled-incomplete", "answer_driven_priority": False,
    "per_query_slices": False, "retry": False, "resume": False,
    "adaptation": False, "nll_scoring": False,
}
ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATHS = (
    "tools/__init__.py", "tools/public_sft141_diagnostic/__init__.py",
    "tools/public_sft141_diagnostic/contract.py", "tools/public_sft141_diagnostic/model_worker.py",
    "tools/public_sft141_diagnostic/model_pins.py", "tools/public_sft141_submission/__init__.py",
    "tools/public_sft141_submission/contract.py", "tools/public_sft141_submission/files.py",
    "tools/public_sft141_solver/__init__.py", "tools/public_sft141_solver/__main__.py",
    "tools/public_sft141_solver/core.py", "tools/public_sft141_solver/worker.py",
    "tools/public_sft141_solver/controller.py", "tools/public_sft141_solver/supervisor.py",
)


def source_identity():
    entries = {name: wire.digest(files.read_bytes(ROOT / name)) for name in SOURCE_PATHS}
    return {"files": entries, "sha256": wire.digest(wire.canonical(entries))}


def publish(path, value=None, *, raw=None):
    """Use the existing no-follow, atomic-exclusive publication primitive."""
    data = wire.canonical(value) if raw is None else raw
    with files.parent_directory(path) as (path, fd):
        files._atomic_file(path.parent, fd, path.name, data)
    return wire.digest(data)


class SharedDeadline:
    """Original controller monotonic clock, carried unchanged into the worker."""
    def __init__(self, start, seconds, *, clock=time.monotonic):
        if type(start) not in (int, float) or not math.isfinite(start):
            raise ValueError("invalid original monotonic start")
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 7200:
            raise ValueError("whole-session budget must be positive and at most 7200 seconds")
        self.clock, self.start, self.seconds = clock, start, float(seconds)
        self.end = start + seconds
        self.reserve = min(seconds * .25, max(.25, seconds * .02))
        self.work_end = self.end - self.reserve

    def check(self):
        if self.expired():
            raise TimeoutError("original work deadline reached; closure reserve is not reusable")

    def expired(self):
        return self.clock() >= self.work_end

    def remaining(self):
        return max(0., self.end - self.clock())

    def work_remaining(self):
        return max(0., self.work_end - self.clock())

    def receipt(self):
        return {"original_start_monotonic": self.start, "budget_seconds": self.seconds,
                "elapsed_seconds": self.clock() - self.start, "remaining_seconds": self.remaining(),
                "closure_reserve_seconds": self.reserve, "resume_supported": False}


def make_plan(challenge, challenge_hash):
    wire.validate_challenge(challenge)
    parents = []
    for task, value in challenge.items():
        parents.append({"task_id": task, "train": value["train"],
                        "test": [{"input": pair["input"], "test_index": i,
                                  "query_id": f"{task}:{i}"} for i, pair in enumerate(value["test"])]})
    return {"schema": SCHEMA, "challenge_sha256": challenge_hash,
            "parents": parents, "scheduler": deepcopy(SCHEDULER)}


def validate_plan(plan, challenge, challenge_hash):
    if wire.canonical(plan) != wire.canonical(make_plan(challenge, challenge_hash)):
        raise ValueError("plan differs from complete gold-free challenge or fixed scheduler")


def inventory(plan):
    rows = []
    for parent in plan["parents"]:
        for query in parent["test"]:
            prompts = [codec.prompt_ids(parent["train"], query["input"], v) for v in codec.VIEWS]
            rows.append({"task_id": parent["task_id"], "test_index": query["test_index"],
                         "query_id": query["query_id"], "support_count": len(parent["train"]),
                         "prompt_tokens_by_view": [len(p) for p in prompts],
                         "prompt_sha256_by_view": [wire.digest(wire.canonical(p)) for p in prompts]})
    return rows


def admitted(row, cap=CONTEXT_CAP):
    return max(row["prompt_tokens_by_view"]) + codec.MAX_NEW_TOKENS <= cap


def schedule(rows, cap=CONTEXT_CAP):
    if type(cap) is not int or not 1 <= cap <= CONTEXT_CAP:
        raise ValueError("effective context must be a positive integer no greater than 8192")
    return [(v * len(rows) + i, i, v) for v in codec.VIEWS
            for i, row in enumerate(rows) if admitted(row, cap)]


def operation_identity(rows, ordinal, i, view):
    return {"ordinal": ordinal, "query_index": i, "view": view,
            "task_id": rows[i]["task_id"], "test_index": rows[i]["test_index"],
            "prompt_tokens": rows[i]["prompt_tokens_by_view"][view],
            "prompt_sha256": rows[i]["prompt_sha256_by_view"][view], "max_new_tokens": 931}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def reconstruct(plan, records, *, effective_context=CONTEXT_CAP, state_guard="unknown", timing_bounds=None):
    """Reparse raw answers, invert D4, and count occurrences after worker exit.

    Input records are verified by the controller's exited seal first. No claimed
    candidate grid, selected answer, validity flag, or precomputed count is trusted.
    """
    rows = inventory(plan)
    expected = schedule(rows, effective_context)
    allowed = {f"{ordinal:08d}-{kind}.json" for ordinal, _, _ in expected for kind in ("start", "end")}
    if set(records) - allowed:
        raise ValueError("unexpected or context-inadmissible operation receipt")
    started = [(o, i, v) for o, i, v in expected if f"{o:08d}-start.json" in records]
    if started != expected[:len(started)]:
        raise ValueError("operation receipts violate preregistered view-major prefix")
    result, selections = [], {}
    counts = {"planned_views": 8 * len(rows), "admissible_views": len(expected),
              "started_operations": 0, "returned_operations": 0, "failed_operations": 0,
              "unknown_operations": 0, "valid_views": 0, "invalid_views": 0,
              "known_generated_tokens": 0, "known_operation_seconds": 0.,
              "failed_or_unknown_cost_is_complete": True}
    by_query = {i: {} for i in range(len(rows))}
    previous_end = None
    for n, (ordinal, i, view) in enumerate(expected):
        start = records.get(f"{ordinal:08d}-start.json")
        end = records.get(f"{ordinal:08d}-end.json")
        identity = operation_identity(rows, ordinal, i, view)
        if start is None:
            if end is not None:
                raise ValueError("end receipt without an immutable start")
            continue
        wire.exact_fields(start, {"operation", "started_monotonic"}, "operation start")
        if wire.canonical(start["operation"]) != wire.canonical(identity) or not _finite(start["started_monotonic"]):
            raise ValueError("operation start identity mismatch")
        begun = start["started_monotonic"]
        if previous_end is not None and begun < previous_end:
            raise ValueError("operation timings overlap or reverse scheduler order")
        if timing_bounds is not None and not timing_bounds[0] <= begun <= timing_bounds[1]:
            raise ValueError("operation started outside original work clock")
        counts["started_operations"] += 1
        if end is None:
            if (ordinal, i, view) != started[-1]:
                raise ValueError("unknown operation is not the final dispatched operation")
            counts["unknown_operations"] += 1
            counts["failed_or_unknown_cost_is_complete"] = False
            by_query[i][view] = {"view": view, "status": "unknown-interrupted", "grid": None}
            continue
        wire.exact_fields(end, {"operation", "outcome", "elapsed_seconds", "raw", "error"}, "operation end")
        if wire.canonical(end["operation"]) != wire.canonical(identity) or not _finite(end["elapsed_seconds"]):
            raise ValueError("operation end identity/timing mismatch")
        previous_end = begun + end["elapsed_seconds"]
        if timing_bounds is not None and previous_end > timing_bounds[2]:
            raise ValueError("operation ended after observed worker closure")
        counts["known_operation_seconds"] += end["elapsed_seconds"]
        if end["outcome"] == "failed":
            if end["raw"] is not None or not isinstance(end["error"], str):
                raise ValueError("invalid failed-operation evidence")
            if (ordinal, i, view) != started[-1]:
                raise ValueError("execution continued after failed operation")
            counts["failed_operations"] += 1
            counts["failed_or_unknown_cost_is_complete"] = False
            by_query[i][view] = {"view": view, "status": "failed", "grid": None, "error": end["error"]}
            continue
        if end["outcome"] != "returned" or end["error"] is not None:
            raise ValueError("invalid operation outcome")
        raw = end["raw"]
        wire.exact_fields(raw, {"token_ids", "generated_tokens", "seconds", "memory", "termination"}, "raw generation")
        tokens = raw["token_ids"]
        if (not isinstance(tokens, list) or any(type(t) is not int for t in tokens)
                or len(tokens) > 931 or type(raw["generated_tokens"]) is not int
                or raw["generated_tokens"] != len(tokens) or not _finite(raw["seconds"])):
            raise ValueError("raw generation violates integer-token, token ceiling, or cost contract")
        if raw["termination"] not in ("eos", "deadline", "max_tokens"):
            raise ValueError("unknown generation termination")
        if (raw["termination"] == "eos") != bool(tokens and tokens[-1] == codec.EOS_ID):
            raise ValueError("generation termination disagrees with raw token suffix")
        counts["returned_operations"] += 1
        counts["known_generated_tokens"] += len(tokens)
        try:
            grid = codec.inverse(codec.parse_answer(tokens), view)
            status, error = "valid", None
            counts["valid_views"] += 1
        except ValueError as exc:
            grid, status, error = None, "invalid", str(exc)
            counts["invalid_views"] += 1
        by_query[i][view] = {"view": view, "status": status, "grid": grid, "parse_error": error}
    for i, row in enumerate(rows):
        views = [by_query[i].get(v, {"view": v, "status": "missing", "grid": None}) for v in codec.VIEWS]
        pool = {}
        for view in views:
            if view["status"] == "valid" and state_guard != "changed":
                grid = view["grid"]
                key = wire.grid_key(grid)
                pool.setdefault(key, {"canonical_key": key, "grid": grid, "count": 0})["count"] += 1
        candidates = sorted(pool.values(), key=lambda c: (-c["count"], c["canonical_key"]))
        selected = [c["grid"] for c in candidates[:2]]
        completed = [v["view"] for v in views if v["status"] in ("valid", "invalid")]
        missing = [v for v in codec.VIEWS if v not in completed]
        result.append({**row, "context_admissible": admitted(row, effective_context),
                       "skip_reason": None if admitted(row, effective_context) else "full-support-prompt-plus-931-exceeds-context",
                       "views": views, "completed_views": completed, "missing_views": missing,
                       "all_eight_views_completed": not missing,
                       "candidate_pool": candidates, "selected": selected,
                       "scientific_complete": False})
        selections[(row["task_id"], row["test_index"])] = selected
    return {"schema": SCHEMA, "queries": result, "counts": counts,
            "all_queries_eight_views_completed": all(r["all_eight_views_completed"] for r in result),
            "model_state_guard": state_guard, "scientific_complete": False,
            "accuracy_evaluated": False, "official_submission_performed": False}, selections

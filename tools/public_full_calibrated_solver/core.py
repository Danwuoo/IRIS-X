"""Dynamic gold-free contract and strict deterministic reconstruction.

The fixed-panel calibration validator is deliberately NOT called or patched.
Only its public LOO specification and stable weight math are reused.
"""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import time

from tools.public_demo_calibration import core as calibration
from tools.public_sft141_diagnostic import contract as codec
from tools.public_sft141_submission import contract as wire, files
from tools.public_sft141_solver.core import publish, _finite

SCHEMA = "iris-public-full-calibrated-solver-v1"
ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ("vote", "rescored", "demo_weighted")
SCHEDULER = {
    "calibration": "parent-original-order/support-original-order/view-0-through-7",
    "generation": "view-major-round-robin-original-query-order",
    "rescoring": "original-query-order/canonical-candidate-order/view-0-through-7",
    "supports": "all-original-supports; leave-exactly-one-out-for-calibration-only",
    "max_new_tokens": 931, "views": list(range(8)),
    "vote": "count-descending/canonical-grid-key-ascending",
    "rescored": "count-minus-mean-eight-full-answer-summed-NLL; canonical-ties",
    "demo_weighted": "sum-frozen-LOO-view-weights; canonical-ties; uniform-incomplete-fallback",
    "calibration_math": deepcopy(calibration.PROTOCOL),
    "cost_probes": "none; no-measured-runtime-admission-or-fit-promise",
    "context_overflow": "reject-whole-panel-before-model-load; no-support-truncation",
    "retry": False, "resume": False, "training": False, "answer_driven_scheduling": False,
}


def source_identity():
    from tools.public_sft141_solver.core import SOURCE_PATHS
    paths = set(SOURCE_PATHS)
    paths.add("tools/public_demo_calibration/core.py")
    paths.add("tools/public_demo_calibration/__init__.py")
    for name in ("public_full_calibrated_solver",):
        paths.update(str(p.relative_to(ROOT)) for p in (ROOT / "tools" / name).glob("*.py"))
    entries = {name: wire.digest(files.read_bytes(ROOT / name)) for name in sorted(paths)}
    return {"files": entries, "sha256": wire.digest(wire.canonical(entries))}


class SharedDeadline:
    """New explicit contract, original whole-session clock; not a legacy override."""
    def __init__(self, start, seconds, *, clock=time.monotonic):
        if not _finite(start) or start > clock():
            raise ValueError("invalid original monotonic start")
        if not _finite(seconds) or not 0 < seconds <= 39600:
            raise ValueError("finite total budget must be positive and at most 39600 seconds")
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


def config(context_cap=10240, budget_seconds=14400., strategy="vote"):
    if type(context_cap) is not int or not 1 <= context_cap <= 262144:
        raise ValueError("configured context must be an explicit integer in 1..262144")
    SharedDeadline(0., budget_seconds)
    if strategy not in STRATEGIES:
        raise ValueError("freeze one explicit strategy before query generation and gold access")
    return {"context_cap": context_cap, "budget_seconds": float(budget_seconds), "strategy": strategy}


def make_plan(challenge, challenge_hash, *, context_cap=10240, budget_seconds=14400., strategy="vote"):
    wire.validate_challenge(challenge)
    if not isinstance(challenge_hash, str) or len(challenge_hash) != 64 or any(c not in "0123456789abcdef" for c in challenge_hash):
        raise ValueError("exact original challenge SHA256 required")
    return {"schema": SCHEMA, "challenge_sha256": challenge_hash,
        "configuration": config(context_cap, budget_seconds, strategy), "scheduler": deepcopy(SCHEDULER),
        "parents": [{"task_id": task, "train": deepcopy(value["train"]),
                     "test": [{"input": deepcopy(q["input"]), "test_index": i,
                               "query_id": f"{task}:{i}"} for i, q in enumerate(value["test"])]}
                    for task, value in challenge.items()]}


def challenge_from_plan(plan):
    wire.exact_fields(plan, {"schema", "challenge_sha256", "configuration", "scheduler", "parents"}, "dynamic plan")
    wire.exact_fields(plan["configuration"], {"context_cap", "budget_seconds", "strategy"}, "configuration")
    if not isinstance(plan["parents"], list):
        raise ValueError("parents must be a list")
    challenge = {}
    for p in plan["parents"]:
        wire.exact_fields(p, {"task_id", "train", "test"}, "parent")
        if p["task_id"] in challenge or not isinstance(p["test"], list):
            raise ValueError("duplicate parent or invalid test inventory")
        tests = []
        for i, q in enumerate(p["test"]):
            wire.exact_fields(q, {"input", "test_index", "query_id"}, "query")
            if type(q["test_index"]) is not int or q["test_index"] != i or q["query_id"] != f"{p['task_id']}:{i}":
                raise ValueError("query identity/order mismatch")
            tests.append({"input": q["input"]})
        challenge[p["task_id"]] = {"train": p["train"], "test": tests}
    wire.validate_challenge(challenge)
    return challenge


def validate_plan(plan, challenge=None, challenge_hash=None):
    rebuilt = challenge_from_plan(plan)
    challenge = rebuilt if challenge is None else challenge
    challenge_hash = plan["challenge_sha256"] if challenge_hash is None else challenge_hash
    expected = make_plan(challenge, challenge_hash, **plan["configuration"])
    if wire.canonical(plan) != wire.canonical(expected):
        raise ValueError("plan differs from entire gold-free challenge, original order, or frozen protocol")


def loo_cases(plan):
    validate_plan(plan)
    return [calibration._case(p, held, v) for p in plan["parents"] if len(p["train"]) > 1
            for held in range(len(p["train"])) for v in codec.VIEWS]


def query_cases(plan):
    return [(p, q) for p in plan["parents"] for q in p["test"]]


def generation_cases(plan):
    validate_plan(plan)
    return [({"query_index": i, "task_id": p["task_id"], "test_index": q["test_index"],
              "query_id": q["query_id"], "view": v,
              "support_indices": list(range(len(p["train"]))),
              "support_pair_sha256": [calibration.digest(pair) for pair in p["train"]],
              "prompt_sha256": calibration.digest(prompt), "prompt_tokens": len(prompt),
              "max_new_tokens": codec.MAX_NEW_TOKENS}, prompt)
            for v in codec.VIEWS for i, (p, q) in enumerate(query_cases(plan))
            for prompt in [codec.prompt_ids(p["train"], q["input"], v)]]


def prepare(plan):
    validate_plan(plan)
    loo, generation = loo_cases(plan), generation_cases(plan)
    cap = plan["configuration"]["context_cap"]
    failures = [{"phase": "loo", "id": s["case_id"], "required_tokens": len(p) + len(a)}
                for s, p, a in loo if len(p) + len(a) > cap]
    failures += [{"phase": "generation", "id": f"{s['query_id']}:{s['view']}",
                  "required_tokens": len(p) + 931} for s, p in generation if len(p) + 931 > cap]
    return {"schema": SCHEMA, "challenge_sha256": plan["challenge_sha256"],
            "plan_sha256": wire.digest(wire.canonical(plan)),
            "configuration": plan["configuration"], "context_admitted": not failures,
            "context_failures": failures, "task_count": len(plan["parents"]),
            "query_count": len(query_cases(plan)), "support_count": sum(len(p["train"]) for p in plan["parents"]),
            "loo_calls": len(loo), "generation_calls": len(generation),
            "rescore_calls_upper_bound": 8 * len(generation), "calibration_probe_calls": 0,
            "loo_input_tokens": sum(s["input_tokens"] for s, _, _ in loo),
            "loo_answer_tokens": sum(len(a) for _, _, a in loo),
            "max_loo_required_tokens": max((len(p) + len(a) for _, p, a in loo), default=0),
            "max_generation_required_tokens": max(len(p) + 931 for _, p in generation),
            "measured_fit": False, "quota_or_runtime_promise": False}


def score_spec(phase, query_index, candidate, view, prompt, answer):
    return {"query_index": query_index, "canonical_key": wire.grid_key(candidate), "view": view,
            "prompt_sha256": calibration.digest(prompt), "answer_sha256": calibration.digest(answer),
            "model_input_sha256": calibration.digest(prompt + answer[:-1]),
            "prompt_tokens": len(prompt), "answer_tokens": len(answer),
            "input_tokens": len(prompt) + len(answer) - 1,
            "loss_mask": {"logit_start_inclusive": len(prompt) - 1,
                          "logit_end_exclusive": len(prompt) - 1 + len(answer),
                          "last_target_id": codec.EOS_ID, "prompt_targets_included": False}}


def operation(ordinal, phase, spec, freeze_hash=None):
    return {"ordinal": ordinal, "phase": phase, "spec": spec, "calibration_freeze_sha256": freeze_hash}


def clean_score(raw, spec):
    wire.exact_fields(raw, {"nll", "seconds", "memory", "answer_tokens", "input_tokens", "batch_size", "use_cache"}, "score result")
    if not _finite(raw["nll"]) or not _finite(raw["seconds"]):
        raise ValueError("score must have finite nonnegative full-answer NLL and seconds")
    if (type(raw["answer_tokens"]) is not int or raw["answer_tokens"] != spec["answer_tokens"] or
        type(raw["input_tokens"]) is not int or raw["input_tokens"] != spec["input_tokens"] or
        type(raw["batch_size"]) is not int or raw["batch_size"] != 1 or raw["use_cache"] is not False):
        raise ValueError("score does not cover batch-one cache-free complete causal answer/EOS")
    validate_memory(raw["memory"])
    return raw


def validate_memory(memory):
    allowed = {"allocated_bytes", "reserved_bytes", "peak_allocated_bytes", "peak_reserved_bytes", "free_bytes", "total_bytes"}
    if memory is not None and (not isinstance(memory, dict) or set(memory) - allowed or
                              any(type(v) is not int or v < 0 for v in memory.values())):
        raise ValueError("memory measurements must be explicit nonnegative byte counts or unknown")


def calibration_summary(plan, successful, complete):
    summaries = {}
    for parent in plan["parents"]:
        n = len(parent["train"])
        values = [[] for _ in codec.VIEWS]
        for spec, raw in successful:
            if spec["task_id"] == parent["task_id"]:
                values[spec["view"]].append(raw["nll"] / spec["answer_tokens"])
        ready = complete and n > 1 and all(len(v) == n for v in values)
        summary = calibration.weights_from_means([math.fsum(x / n for x in v) for v in values] if ready else [0.] * 8)
        status = "complete" if ready else "single_demo_fallback" if n == 1 else "partial_calibration_fallback"
        if summary["underflow_views"]:
            ready, status = False, "numeric_underflow_fallback"
        if not ready and status != "numeric_underflow_fallback":
            summary["means"] = summary["centered_means"] = None
        summaries[parent["task_id"]] = {**summary, "status": status, "adaptation_eligible": ready,
                                        "support_count": n, "support_token_mean_nll_by_view": values}
    return summaries


def freeze_value(plan, successful, completed_monotonic):
    return {"schema": SCHEMA, "plan_sha256": wire.digest(wire.canonical(plan)),
            "loo_result_sha256": calibration.digest(successful), "loo_completed": len(successful),
            "completed_monotonic": completed_monotonic,
            "weights": calibration_summary(plan, successful, True), "strategy": plan["configuration"]["strategy"]}


class Replay:
    """Validate every actual operation against the deterministic expected prefix."""
    def __init__(self, records, bounds):
        self.records, self.bounds, self.index, self.last_end = records, bounds, 0, None
        self.stopped = False
        self.last_status = "missing"
        self.counts = {p: {"started": 0, "returned": 0, "failed": 0, "unknown": 0,
                          "known_seconds": 0., "known_input_tokens": 0, "known_answer_tokens": 0,
                          "known_generated_tokens": 0, "unknown_cost": False} for p in ("loo", "generation", "nll")}

    def consume(self, phase, spec, freeze_hash=None):
        ordinal = self.index
        key = f"{ordinal:08d}"
        start, end = self.records.get(key + "-start.json"), self.records.get(key + "-end.json")
        if start is None:
            self.last_status = "missing"
            self.stopped = True
            return None
        if self.stopped:
            raise ValueError("operation continued after interruption/failure/late result")
        self.index += 1
        op = operation(ordinal, phase, spec, freeze_hash)
        wire.exact_fields(start, {"operation", "started_monotonic"}, "start receipt")
        if wire.canonical(start["operation"]) != wire.canonical(op) or not _finite(start["started_monotonic"]):
            raise ValueError("raw operation identity differs from deterministic full-support schedule")
        begun = start["started_monotonic"]
        if (self.last_end is not None and begun < self.last_end) or (self.bounds and not self.bounds[0] <= begun < self.bounds[1]):
            raise ValueError("start outside original work clock or sequential order")
        count = self.counts[phase]
        count["started"] += 1
        if end is None:
            self.last_status = "unknown-interrupted"
            count["unknown"] += 1
            count["unknown_cost"] = self.stopped = True
            return None
        wire.exact_fields(end, {"operation", "outcome", "elapsed_seconds", "raw", "error"}, "end receipt")
        if wire.canonical(end["operation"]) != wire.canonical(op) or not _finite(end["elapsed_seconds"]):
            raise ValueError("invalid end identity/timing")
        self.last_end = begun + end["elapsed_seconds"]
        if self.bounds and self.last_end > self.bounds[2]:
            raise ValueError("operation ended after worker closure")
        count["known_seconds"] += end["elapsed_seconds"]
        if end["outcome"] == "failed":
            if end["raw"] is not None or not isinstance(end["error"], str):
                raise ValueError("failed operation cannot invent zero model costs")
            self.last_status = "failed"
            count["failed"] += 1
            count["unknown_cost"] = self.stopped = True
            return None
        if end["outcome"] != "returned" or end["error"] is not None:
            raise ValueError("unknown raw operation outcome")
        raw = end["raw"]
        if phase == "generation":
            from tools.public_sft141_solver.worker import clean_raw
            wire.exact_fields(raw, {"token_ids", "generated_tokens", "seconds", "memory", "termination"}, "generation result")
            if (type(raw["generated_tokens"]) is not int or wire.canonical(clean_raw(raw)) != wire.canonical(raw)
                    or any(not 0 <= t < 16 for t in raw["token_ids"])):
                raise ValueError("raw generation contract mismatch")
            validate_memory(raw["memory"])
            count["known_generated_tokens"] += len(raw["token_ids"])
            count["known_input_tokens"] += spec["prompt_tokens"]
        else:
            clean_score(raw, spec)
            count["known_input_tokens"] += raw["input_tokens"]
            count["known_answer_tokens"] += raw["answer_tokens"]
        count["returned"] += 1
        if (self.bounds and self.last_end >= self.bounds[1]) or (phase == "generation" and raw["termination"] == "deadline"):
            self.last_status = "late-returned"
            self.stopped = True
            return None
        self.last_status = "returned"
        return raw

    def finish(self):
        allowed = {f"{i:08d}-{kind}.json" for i in range(self.index) for kind in ("start", "end")}
        if set(self.records) - allowed:
            raise ValueError("unexpected, reordered, gapped, or post-failure operation receipt")


def reconstruct(plan, records, *, freeze=None, state_guard="unknown", timing_bounds=None):
    validate_plan(plan)
    replay = Replay(records, timing_bounds)
    successful = []
    loo = loo_cases(plan)
    for spec, _, _ in loo:
        raw = replay.consume("loo", spec)
        if raw is not None:
            successful.append((spec, raw))
    loo_complete = len(successful) == len(loo)
    freeze_hash = None
    if freeze is not None:
        if not loo_complete or not _finite(freeze.get("completed_monotonic")):
            raise ValueError("calibration freeze requires all LOO operations")
        expected = freeze_value(plan, successful, freeze["completed_monotonic"])
        if wire.canonical(freeze) != wire.canonical(expected):
            raise ValueError("frozen calibration differs from independently rebuilt all-support weights")
        if (replay.last_end is not None and freeze["completed_monotonic"] < replay.last_end) or (timing_bounds and not timing_bounds[0] <= freeze["completed_monotonic"] < timing_bounds[1]):
            raise ValueError("calibration freeze outside original phase boundary")
        replay.last_end = freeze["completed_monotonic"]
        freeze_hash = wire.digest(wire.canonical(freeze))
    summaries = calibration_summary(plan, successful, loo_complete and freeze is not None)
    queries = [{"task_id": p["task_id"], "query_id": q["query_id"], "test_index": q["test_index"],
                "views": [], "candidates": [], "vote": [], "rescored": [], "demo_weighted": []}
               for p, q in query_cases(plan)]
    pools = [{} for _ in queries]
    generation_complete = True
    if freeze is not None:
        for spec, _ in generation_cases(plan):
            raw = replay.consume("generation", spec, freeze_hash)
            row = {"view": spec["view"], "status": replay.last_status, "grid": None}
            if raw is not None:
                try:
                    grid = codec.inverse(codec.parse_answer(raw["token_ids"]), spec["view"])
                    row.update(status="valid", grid=grid)
                    key = wire.grid_key(grid)
                    pools[spec["query_index"]].setdefault(key, {"canonical_key": key, "grid": grid, "views": [], "view_nll": []})["views"].append(spec["view"])
                except ValueError:
                    row["status"] = "invalid"
            else:
                generation_complete = False
            queries[spec["query_index"]]["views"].append(row)
    else:
        generation_complete = False
    # NLL schedule is a deterministic function of the complete shared raw pool.
    nll_complete = generation_complete
    for i, ((parent, query), pool) in enumerate(zip(query_cases(plan), pools)):
        candidates = [pool[k] for k in sorted(pool)]
        summary = summaries[parent["task_id"]]
        pool_complete = len(queries[i]["views"]) == 8 and all(r["status"] in ("valid", "invalid") for r in queries[i]["views"])
        query_nll_complete = generation_complete
        for candidate in candidates:
            candidate["count"] = len(candidate["views"])
            candidate["weighted_vote"] = math.fsum(summary["weights"][v] for v in candidate["views"])
            if generation_complete:
                for view in codec.VIEWS:
                    prompt = codec.prompt_ids(parent["train"], query["input"], view)
                    answer = codec.answer_ids(codec.transform(candidate["grid"], view))
                    spec = score_spec("nll", i, candidate["grid"], view, prompt, answer)
                    raw = replay.consume("nll", spec, freeze_hash)
                    candidate["view_nll"].append(raw["nll"] if raw is not None else None)
            ready = len(candidate["view_nll"]) == 8 and all(x is not None for x in candidate["view_nll"])
            query_nll_complete = query_nll_complete and ready
            candidate["mean_nll"] = sum(candidate["view_nll"]) / 8 if ready else None
            candidate["combined_score"] = candidate["count"] - candidate["mean_nll"] if ready else None
        vote = sorted(candidates, key=lambda c: (-c["count"], c["canonical_key"]))
        weighted = sorted(candidates, key=lambda c: (-c["weighted_vote"], c["canonical_key"])) if pool_complete and summary["adaptation_eligible"] else vote
        rescored = sorted(candidates, key=lambda c: (-c["combined_score"], c["canonical_key"])) if query_nll_complete else []
        queries[i].update(candidates=candidates, vote=[c["grid"] for c in vote[:2]],
                          demo_weighted=[c["grid"] for c in weighted[:2]], rescored=[c["grid"] for c in rescored[:2]],
                          pool_complete=pool_complete, nll_complete=query_nll_complete,
                          weighted_adaptation_applied=pool_complete and summary["adaptation_eligible"])
        nll_complete = nll_complete and query_nll_complete
    replay.finish()
    for i, q in enumerate(queries):
        by_view = {v["view"]: v for v in q["views"]}
        q["views"] = [by_view.get(v, {"view": v, "status": "missing", "grid": None}) for v in codec.VIEWS]
        q["calibration_cost_task_id"] = q["task_id"]
        q["physical_cost"] = {phase: physical_cost(records, phase, i) for phase in ("generation", "nll")}
        if state_guard == "changed":
            q["vote"] = q["rescored"] = q["demo_weighted"] = []
            q["weighted_adaptation_applied"] = False
    selections = {strategy: {(q["task_id"], q["test_index"]): q[strategy] for q in queries} for strategy in STRATEGIES}
    return {"schema": SCHEMA, "queries": queries, "calibration": summaries,
            "calibration_freeze_sha256": freeze_hash, "calibration_complete": loo_complete and freeze is not None,
            "generation_complete": generation_complete, "nll_complete": nll_complete,
            "all_planned_calls_returned": loo_complete and freeze is not None and generation_complete and nll_complete,
            "candidate_coverage_complete": state_guard != "changed" and all(q["candidates"] for q in queries),
            "all_generated_answers_valid": generation_complete and all(v["status"] == "valid" for q in queries for v in q["views"]),
            "all_queries_eight_views_completed": generation_complete,
            "fixed_task_denominator": len(plan["parents"]), "fixed_query_denominator": len(queries),
            "counts": {phase: {**value, **physical_cost(records, phase)} for phase, value in replay.counts.items()}, "calibration_probe_calls": 0, "model_state_guard": state_guard,
            "scientific_complete": False, "accuracy_established": False}, selections


def physical_cost(records, phase, query_index=None):
    """Exact completed lower bounds plus explicit unknown totals, never unknown=0."""
    result = {"started": 0, "returned": 0, "failed": 0, "unknown": 0, "known_seconds": 0.,
              "known_input_tokens": 0, "known_answer_tokens": 0, "known_generated_tokens": 0,
              "unknown_cost": False, "peak_allocated_bytes": None}
    for name, start in records.items():
        if not name.endswith("-start.json") or start["operation"]["phase"] != phase:
            continue
        spec = start["operation"]["spec"]
        if query_index is not None and spec.get("query_index") != query_index:
            continue
        result["started"] += 1
        end = records.get(name.replace("-start.json", "-end.json"))
        if end is None:
            result["unknown"] += 1
            result["unknown_cost"] = True
            continue
        result["known_seconds"] += end["elapsed_seconds"]
        if end["outcome"] == "failed":
            result["failed"] += 1
            result["unknown_cost"] = True
            continue
        result["returned"] += 1
        raw = end["raw"]
        result["known_input_tokens"] += spec["prompt_tokens"] if phase == "generation" else raw["input_tokens"]
        result["known_answer_tokens"] += 0 if phase == "generation" else raw["answer_tokens"]
        result["known_generated_tokens"] += raw["generated_tokens"] if phase == "generation" else 0
        if raw.get("memory") and "peak_allocated_bytes" in raw["memory"]:
            result["peak_allocated_bytes"] = max(result["peak_allocated_bytes"] or 0, raw["memory"]["peak_allocated_bytes"])
    result["total_input_tokens"] = None if result["unknown_cost"] else result["known_input_tokens"]
    result["total_answer_tokens"] = None if result["unknown_cost"] else result["known_answer_tokens"]
    result["total_generated_tokens"] = None if result["unknown_cost"] else result["known_generated_tokens"]
    result["qualification"] = "Known values are completed lower bounds when a dispatched operation has failed or not returned; wall time includes failures separately."
    return result

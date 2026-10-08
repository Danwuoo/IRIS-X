"""Small truth-free candidate/provenance adapter; no native likelihood fiction.

DSL records reference replayed programs/demo fit. Native evidence remains in
the native artifact; a ranked pool reference never certifies eight native views.
Scores from different solvers are never compared. Fixed slot policies must be
measured for complementary coverage before choosing a combined configuration.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict

from .arc_symbolic_dsl import GRAMMAR_SPEC, Limits, SOLVER_ID, execute_program, grid, require, validate_task
from .canonical import canonical_bytes, digest_value

FORMAT = "irisx/arc-neutral-candidates-v2"
POOL_FORMAT = "irisx/arc-offline-pools-v1"
TIMINGS = {"training_seconds", "search_seconds", "verification_seconds", "other_seconds",
           "solve_seconds", "reset_seconds", "total_seconds"}


def validate_challenges(challenges: object) -> dict:
    require(isinstance(challenges, dict) and bool(challenges), "nonempty challenge mapping required")
    return {task_id: validate_task(task) for task_id, task in challenges.items()
            if _task_id(task_id)}


def _task_id(value: object) -> bool:
    require(type(value) is str and 0 < len(value) <= 128, "bounded task ID required")
    return True


def _digest(value: object) -> None:
    require(isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None,
            "canonical sha256 digest required")


def _seconds(value: object) -> None:
    require(value is None or type(value) in (float, int) and math.isfinite(value) and value >= 0,
            "finite nonnegative measured seconds or null required")


def _limits(value: object, config_digest: str) -> Limits:
    require(isinstance(value, dict) and set(value) == set(asdict(Limits())), "complete frozen limits required")
    limits = Limits(**value)
    limits.validate()
    require(digest_value(value) == config_digest, "embedded limits/config digest differs")
    return limits


def _complete_cost_bounds(cost: dict, limits: Limits) -> None:
    require(type(cost["states"]) is int and 0 <= cost["states"] <= limits.max_states and
            type(cost["serialized_cache_bytes"]) is int and 0 <= cost["serialized_cache_bytes"] <= limits.cache_bytes,
            "state/serialized-cache cost exceeds frozen config")
    for name in ("parent_wall_seconds", "search_wall_seconds"):
        require(type(cost[name]) in (int, float) and 0 <= cost[name] < limits.wall_seconds,
                "complete worker wall exceeds frozen config")
    require(type(cost["cpu_seconds"]) in (int, float) and 0 <= cost["cpu_seconds"] <= limits.wall_seconds,
            "CPU cost exceeds frozen config")
    require(cost["peak_rss_bytes"] is None or cost["peak_rss_bytes"] <= limits.address_space_bytes,
            "RSS cost exceeds frozen address-space cap")


def from_dsl_worker(task_id: str, task: dict, worker: dict, source_code_digest: str) -> dict:
    """Replay every retained program on demos/tests before neutral export.

    A digest is an integrity identity, never a proof of correctness or native
    verification. Test-output fields are rejected before this replay.
    """
    _task_id(task_id)
    task = validate_task(task)
    _digest(source_code_digest)
    require(isinstance(worker, dict) and set(worker) == {"format", "status", "solver_id", "task_digest",
        "config_digest", "limits", "result", "parent_wall_seconds", "peak_rss_bytes", "memory_enforcement", "correctness_scored"}
        and worker.get("format") == "irisx/arc-dsl-worker-v1" and
            worker.get("solver_id") == SOLVER_ID and worker.get("task_digest") == digest_value(task)
            and worker.get("correctness_scored") is False, "worker task/solver identity differs")
    _seconds(worker.get("parent_wall_seconds"))
    limits = _limits(worker["limits"], worker["config_digest"])
    require(worker["memory_enforcement"] in {"linux-RLIMIT_AS", "synthetic-cooperative-reference"},
            "memory enforcement provenance differs")
    result = worker.get("result")
    candidates = []
    if worker.get("status") == "complete":
        require(isinstance(result, dict) and set(result) == {"format", "solver_id", "task_digest", "config_digest",
            "grammar_digest", "limits", "candidates", "stop_reason", "cache_bytes", "unique_states",
            "invalid_expansions", "states", "loo_support", "wall_seconds", "cpu_seconds", "native_verification",
            "correctness_scored"} and result.get("grammar_digest") == digest_value(GRAMMAR_SPEC)
                and result.get("task_digest") == digest_value(task) and
                result.get("config_digest") == worker.get("config_digest") and
                result.get("native_verification") is None and result.get("correctness_scored") is False,
                "DSL evidence must stay distinct from native verification")
        require(result["limits"] == worker["limits"] and
                type(result["states"]) is int and 0 <= result["states"] <= limits.max_states and
                result["stop_reason"] in {"exhausted", "state_limit", "cache_limit"},
                "search cost/config/cutoff identity differs")
        require(isinstance(result.get("candidates"), list) and len(result["candidates"]) <= limits.max_candidates,
                "bounded DSL candidates required")
        for candidate in result["candidates"]:
            require(isinstance(candidate, dict) and set(candidate) == {"program", "outputs", "ast_nodes"},
                    "DSL candidate schema differs")
            program = candidate["program"]
            require(isinstance(program, list) and 1 <= len(program) <= limits.max_depth, "bounded macro program required")
            require(candidate["ast_nodes"] == 4 * len(program) and candidate["ast_nodes"] <= limits.max_ast_nodes,
                    "expanded AST cost differs")
            require(all(execute_program(pair["input"], program) == pair["output"]
                        for pair in task["train"]), "program does not fit every demonstration")
            outputs = [execute_program(pair["input"], program) for pair in task["test"]]
            require(candidate["outputs"] == outputs, "candidate output differs from program replay")
            candidates.append({"record_kind": "symbolic-program", "solver_id": SOLVER_ID,
                "candidate_outputs": outputs, "candidate_digest": digest_value(outputs),
                "program": program, "program_digest": digest_value(program),
                "ast_nodes": candidate["ast_nodes"],
                "evidence": {"kind": "all-demonstrations-exact-fit",
                             "demonstrations": len(task["train"]), "loo_support": result["loo_support"],
                             "native_verification": None}})
    else:
        require(result is None, "failed worker must not retain partial candidates")
    record = {"format": FORMAT, "task_id": task_id, "task_digest": digest_value(task),
              "test_input_digests": [digest_value(p["input"]) for p in task["test"]],
              "solver_id": SOLVER_ID, "config_digest": worker["config_digest"],
              "limits": asdict(limits), "memory_enforcement": worker["memory_enforcement"],
              "grammar_digest": digest_value(GRAMMAR_SPEC), "source_code_digest": source_code_digest,
              "status": worker["status"], "candidates": candidates,
              "search_stop_reason": None if result is None else result["stop_reason"],
              "cost": {"parent_wall_seconds": worker["parent_wall_seconds"],
                       "search_wall_seconds": None if result is None else result["wall_seconds"],
                       "cpu_seconds": None if result is None else result["cpu_seconds"],
                       "states": None if result is None else result["states"],
                       "serialized_cache_bytes": None if result is None else result["cache_bytes"],
                       "peak_rss_bytes": worker.get("peak_rss_bytes")},
              "correctness_scored": False}
    validate_record(task, record)
    return record


def validate_record(task: dict, record: object) -> None:
    task = validate_task(task)
    require(isinstance(record, dict) and set(record) == {"format", "task_id", "task_digest",
        "test_input_digests", "solver_id", "config_digest", "grammar_digest", "source_code_digest",
        "limits", "memory_enforcement", "status", "search_stop_reason", "candidates", "cost", "correctness_scored"},
        "neutral record schema differs")
    _task_id(record["task_id"])
    require(record["format"] == FORMAT and record["solver_id"] == SOLVER_ID and
            record["correctness_scored"] is False and record["task_digest"] == digest_value(task),
            "truth-free neutral task identity required")
    require(record["test_input_digests"] == [digest_value(p["input"]) for p in task["test"]],
            "complete ordered test-input identity required")
    for name in ("config_digest", "grammar_digest", "source_code_digest"):
        _digest(record[name])
    limits = _limits(record["limits"], record["config_digest"])
    require(record["memory_enforcement"] in {"linux-RLIMIT_AS", "synthetic-cooperative-reference"},
            "memory enforcement provenance differs")
    require(record["grammar_digest"] == digest_value(GRAMMAR_SPEC), "frozen grammar differs")
    require(record["status"] in {"complete", "wall_limit", "memory_limit", "worker_fault",
                                 "unsupported_memory_enforcement"}, "worker status differs")
    require(isinstance(record["cost"], dict) and set(record["cost"]) == {"parent_wall_seconds",
        "search_wall_seconds", "cpu_seconds", "states", "serialized_cache_bytes", "peak_rss_bytes"},
        "measured cost schema differs")
    for name in ("parent_wall_seconds", "search_wall_seconds", "cpu_seconds"):
        _seconds(record["cost"][name])
    for name in ("states", "serialized_cache_bytes", "peak_rss_bytes"):
        value = record["cost"][name]
        require(value is None or type(value) is int and value >= 0, "nonnegative count or null required")
    candidates = record["candidates"]
    require(isinstance(candidates, list) and len(candidates) <= limits.max_candidates and
            (record["status"] == "complete" or not candidates), "bounded nonfailure candidates required")
    if record["status"] == "complete":
        _complete_cost_bounds(record["cost"], limits)
        require(record["search_stop_reason"] in {"exhausted", "state_limit", "cache_limit"},
                "completed search cutoff differs")
        require(record["search_stop_reason"] != "state_limit" or record["cost"]["states"] == limits.max_states,
                "state cutoff accounting differs")
    else:
        require(record["search_stop_reason"] is None, "failed worker cannot claim a completed search cutoff")
    seen = set()
    for candidate in candidates:
        require(isinstance(candidate, dict) and set(candidate) == {"record_kind", "solver_id",
            "candidate_outputs", "candidate_digest", "program", "program_digest", "ast_nodes", "evidence"},
            "symbolic candidate schema differs")
        require(candidate["record_kind"] == "symbolic-program" and candidate["solver_id"] == SOLVER_ID,
                "symbolic candidate cannot claim native evidence")
        outputs = candidate["candidate_outputs"]
        require(isinstance(outputs, list) and len(outputs) == len(task["test"]), "full ordered output vector required")
        for output in outputs:
            grid(output)
        require(candidate["candidate_digest"] == digest_value(outputs) and
                candidate["candidate_digest"] not in seen, "unique output-vector digest required")
        seen.add(candidate["candidate_digest"])
        program = candidate["program"]
        require(isinstance(program, list) and 1 <= len(program) <= limits.max_depth, "bounded macro program required")
        require(candidate["program_digest"] == digest_value(program) and type(candidate["ast_nodes"]) is int
                and candidate["ast_nodes"] == 4 * len(program) <= limits.max_ast_nodes, "program cost/digest differs")
        require(all(execute_program(p["input"], program) == p["output"] for p in task["train"])
                and [execute_program(p["input"], program) for p in task["test"]] == outputs,
                "program/demo/test replay differs")
        evidence = candidate["evidence"]
        require(isinstance(evidence, dict) and set(evidence) == {"kind", "demonstrations", "loo_support",
            "native_verification"} and evidence["kind"] == "all-demonstrations-exact-fit" and
            evidence["demonstrations"] == len(task["train"]) and evidence["native_verification"] is None,
            "demonstration evidence must not claim native views")
        support = evidence["loo_support"]
        require(limits.loo or support is None, "unrequested LOO support forbidden")
        require(support is None or isinstance(support, dict) and set(support) == {"kind", "folds", "supported",
            "shared_task_budget"} and support["kind"] == "leave-one-demonstration-out-top-one" and
            type(support["folds"]) is int and support["folds"] == len(task["train"]) >= 3 and
            type(support["supported"]) is int and 0 <= support["supported"] <= support["folds"] and
            support["shared_task_budget"] is True, "LOO support schema differs")
    require(candidates == sorted(candidates, key=lambda c: (c["ast_nodes"], canonical_bytes(c["program"]))),
            "symbolic ranking must use complexity and canonical program order only")


def to_offline_pools(challenges: dict, records: list[dict], run_id: str, parent_wall_seconds: float) -> dict:
    challenges = validate_challenges(challenges)
    require(isinstance(records, list), "neutral record array required")
    require(type(run_id) is str and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run_id), "bounded run ID required")
    _seconds(parent_wall_seconds)
    seen, pool_records = set(), []
    for record in records:
        key = record["task_id"]
        require(key in challenges and key not in seen, "unique known task record required")
        validate_record(challenges[key], record)
        seen.add(key)
        tests = []
        for i, pair in enumerate(challenges[key]["test"]):
            ranked, grid_seen = [], set()
            for candidate in record["candidates"]:
                output = candidate["candidate_outputs"][i]
                identity = digest_value(output)
                if identity not in grid_seen:
                    grid_seen.add(identity)
                    ranked.append(grid(output))
            tests.append({"test_index": i, "input_digest": digest_value(pair["input"]),
                          "ranked_grids": ranked, "status": "complete" if len(ranked) >= 2 else
                          "partial" if ranked else "failed"})
        pool_records.append({"task_id": key, "task_digest": record["task_digest"], "tests": tests,
            "timings": {"search_seconds": record["cost"]["search_wall_seconds"],
                        "total_seconds": record["cost"]["parent_wall_seconds"]}})
    return {"format": POOL_FORMAT, "run_id": run_id, "method": SOLVER_ID,
            "challenges_digest": digest_value(challenges), "records": pool_records,
            "parent_wall_seconds": parent_wall_seconds}


def validate_pools(challenges: dict, pools: object) -> dict:
    """Production-side validation, without importing the evaluator module."""
    challenges = validate_challenges(challenges)
    require(isinstance(pools, dict) and set(pools) == {"format", "run_id", "method", "challenges_digest",
            "records", "parent_wall_seconds"} and pools["format"] == POOL_FORMAT,
            "truth-free pool envelope schema differs")
    require(type(pools["run_id"]) is str and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", pools["run_id"])
            and type(pools["method"]) is str and 0 < len(pools["method"]) <= 200, "run/method required")
    require(pools["challenges_digest"] == digest_value(challenges), "full challenge identity differs")
    _seconds(pools["parent_wall_seconds"])
    require(isinstance(pools["records"], list), "pool record array required")
    records = {}
    for record in pools["records"]:
        require(isinstance(record, dict) and set(record) == {"task_id", "task_digest", "tests", "timings"},
                "pool task schema differs")
        key = record["task_id"]
        require(key in challenges and key not in records and record["task_digest"] == digest_value(challenges[key]),
                "unique known task identity required")
        require(isinstance(record["timings"], dict) and set(record["timings"]) <= TIMINGS, "timing fields differ")
        for value in record["timings"].values():
            _seconds(value)
        require(isinstance(record["tests"], list), "pool test array required")
        seen = set()
        for test in record["tests"]:
            require(isinstance(test, dict) and set(test) == {"test_index", "input_digest", "ranked_grids", "status"},
                    "truth-free pool test schema differs")
            i = test["test_index"]
            require(type(i) is int and 0 <= i < len(challenges[key]["test"]) and i not in seen and
                    test["input_digest"] == digest_value(challenges[key]["test"][i]["input"]), "test identity differs")
            seen.add(i)
            ranked = test["ranked_grids"]
            require(isinstance(ranked, list) and len(ranked) <= 64, "bounded grid pool required")
            for value in ranked:
                grid(value)
            require(len({digest_value(value) for value in ranked}) == len(ranked), "unique grids required")
            require(test["status"] in {"complete", "partial", "failed", "not_executed"} and
                    (not ranked or test["status"] in {"complete", "partial"}), "pool status contradicts grids")
        records[key] = record
    return records


def combine_pools(challenges: dict, baseline: dict, symbolic: dict, *, policy: str, run_id: str) -> tuple[dict, dict]:
    """Truth-free fixed ranking; union oracle is measured separately downstream.

    baseline-first preserves its first two unique baseline grids. one-each-v2
    puts the first baseline grid and first distinct symbolic grid in the slots.
    Neither uses task
    ID, test labels, likelihood comparisons, or learned routing features.
    """
    challenges = validate_challenges(challenges)
    left, right = validate_pools(challenges, baseline), validate_pools(challenges, symbolic)
    require(policy in {"baseline-first", "one-each"}, "unknown fixed slot policy")
    require(type(run_id) is str and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run_id), "bounded run ID required")
    records, sources = [], []
    for key, task in challenges.items():
        maps = [{t["test_index"]: t["ranked_grids"] for t in records.get(key, {}).get("tests", [])}
                for records in (left, right)]
        tests = []
        for i, pair in enumerate(task["test"]):
            a, b = maps[0].get(i, []), maps[1].get(i, [])
            if policy == "baseline-first":
                ordered = [(g, "baseline") for g in a] + [(g, "symbolic") for g in b]
            else:
                novel = next((g for g in b if not a or g != a[0]), None)
                ordered = ([(g, "baseline") for g in a[:1]] +
                           ([] if novel is None else [(novel, "symbolic")]) +
                           [(g, "baseline") for g in a] + [(g, "symbolic") for g in b])
            seen, ranked, provenance = set(), [], []
            for output, source in ordered:
                identity = digest_value(output)
                if identity not in seen and len(ranked) < 64:
                    seen.add(identity)
                    ranked.append(grid(output))
                    provenance.append({"grid_digest": identity, "rank_origin": source})
            tests.append({"test_index": i, "input_digest": digest_value(pair["input"]), "ranked_grids": ranked,
                          "status": "complete" if len(ranked) >= 2 else "partial" if ranked else "failed"})
            sources.append({"task_id": key, "test_index": i, "ranked_sources": provenance})
        records.append({"task_id": key, "task_digest": digest_value(task), "tests": tests, "timings": {}})
    method = "fixed-one-each-v2" if policy == "one-each" else "fixed-baseline-first-v1"
    pools = {"format": POOL_FORMAT, "run_id": run_id, "method": method,
             "challenges_digest": digest_value(challenges), "records": records, "parent_wall_seconds": None}
    provenance = {"format": "irisx/arc-fixed-selection-v2", "policy": policy,
        "policy_version": 2 if policy == "one-each" else 1,
        "baseline_pool_digest": digest_value(baseline), "symbolic_pool_digest": digest_value(symbolic),
        "native_evidence": "retained solely in originating native artifact; not certified by this adapter",
        "correctness_scored": False, "rows": sources}
    return pools, provenance


def submission_records(challenges: dict, pools: dict) -> list[dict]:
    records = validate_pools(challenges, pools)
    return [{"task_id": key, "tests": [{"test_index": t["test_index"],
              "attempts": [grid(g) for g in t["ranked_grids"][:2]],
              "status": "complete" if len(t["ranked_grids"]) >= 2 else "missing-candidate"}
             for t in record["tests"]]} for key, record in records.items()]

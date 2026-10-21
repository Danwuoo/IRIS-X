"""Public ARC wire contracts, implemented independently with the standard library."""

import hashlib
import json
import math

FROZEN_SCHEMA = "iris-public-sft141-frozen-candidates-v1"
CLOSURE_SCHEMA = "iris-public-sft141-submission-closure-v1"
STRATEGIES = ("frozen", "vote", "rescored")
_FORBIDDEN = {"gold", "groundtruth", "answer", "answers", "solution", "solutions",
              "label", "labels", "target", "targets", "output", "outputs",
              "testoutput", "testoutputs", "expectedoutput", "expectedoutputs",
              "testlabel", "testlabels", "testanswer", "testanswers",
              "correctanswer", "correctanswers"}


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def grid_key(grid):
    return json.dumps(grid, separators=(",", ":"))


def exact_fields(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{label}: missing or unexpected fields")


def reject_gold(value):
    """Reject label-bearing structured fields, including nested metadata."""
    if isinstance(value, dict):
        if any("".join(c for c in key.casefold() if c.isalnum()) in _FORBIDDEN for key in value):
            raise ValueError("gold/answer/output fields are forbidden outside training demonstrations")
        for child in value.values():
            reject_gold(child)
    elif isinstance(value, list):
        for child in value:
            reject_gold(child)


def validate_grid(grid):
    if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
        raise ValueError("grid must have 1..30 rows")
    width = None
    copied = []
    for row in grid:
        if not isinstance(row, list) or not 1 <= len(row) <= 30:
            raise ValueError("grid rows must have 1..30 cells")
        if width is None:
            width = len(row)
        if width != len(row):
            raise ValueError("grid must be rectangular")
        if any(type(cell) is not int or not 0 <= cell <= 9 for cell in row):
            raise ValueError("grid cells must be integer colors 0..9, not booleans or floats")
        copied.append(list(row))
    return copied


def validate_challenge(challenge):
    if not isinstance(challenge, dict) or not challenge:
        raise ValueError("challenge must be a nonempty task-ID object")
    inventory = {}
    for task_id, task in challenge.items():
        if not isinstance(task_id, str) or not task_id or any(ord(c) < 32 for c in task_id):
            raise ValueError("task IDs must be nonempty strings without control characters")
        # IDs remain JSON keys, never filesystem paths. Preserve them verbatim.
        exact_fields(task, {"train", "test"}, "task")
        for name in ("train", "test"):
            if not isinstance(task[name], list) or not task[name]:
                raise ValueError("every task requires demonstrations and at least one test input")
        for pair in task["train"]:
            exact_fields(pair, {"input", "output"}, "training pair")
            validate_grid(pair["input"])
            validate_grid(pair["output"])
        for index, pair in enumerate(task["test"]):
            exact_fields(pair, {"input"}, "test pair must be gold-free")
            inventory[(task_id, index)] = validate_grid(pair["input"])
    return inventory


def validate_candidates(candidates):
    if not isinstance(candidates, list) or len(candidates) > 2:
        raise ValueError("each query must contain zero, one or two candidate grids")
    grids = [validate_grid(grid) for grid in candidates]
    if len(grids) == 2 and grids[0] == grids[1]:
        raise ValueError("duplicate source candidate: provide one grid; padding is explicitly recorded")
    return grids


def read_frozen(value, challenge, challenge_hash, strategy):
    exact_fields(value, {"schema", "challenge_sha256", "strategy",
                         "strategy_chosen_before_gold", "queries"}, "frozen candidates")
    if value["schema"] != FROZEN_SCHEMA:
        raise ValueError("unsupported frozen-candidate schema")
    if value["challenge_sha256"] != challenge_hash:
        raise ValueError("candidate/challenge SHA-256 mismatch")
    if value["strategy"] != strategy or value["strategy_chosen_before_gold"] is not True:
        raise ValueError("candidate strategy must match explicit pre-gold strategy declaration")
    queries = value["queries"]
    if not isinstance(queries, dict) or set(queries) != set(challenge):
        raise ValueError("missing or unexpected candidate task IDs")
    rows = {}
    for task_id, task in challenge.items():
        indexed = queries[task_id]
        expected = {str(i) for i in range(len(task["test"]))}
        if not isinstance(indexed, dict) or set(indexed) != expected:
            raise ValueError("missing, noncanonical, unexpected or gapped test indices")
        for i in range(len(task["test"])):
            rows[(task_id, i)] = validate_candidates(indexed[str(i)])
    return rows, {"level": "challenge-hash-bound-frozen-selection",
                  "scientific_audit_verified": False,
                  "ranking_or_model_execution_verified": False}


def _diagnostic_plan(plan, challenge):
    if not isinstance(plan, dict) or plan.get("schema") != "iris-public-sft141-plan-v1":
        raise ValueError("unsupported diagnostic plan")
    if set(plan) - {"schema", "parents", "provenance", "protocol"}:
        raise ValueError("unexpected diagnostic plan fields")
    reject_gold(plan.get("provenance", {}))
    reject_gold(plan.get("protocol", {}))
    parents = plan.get("parents")
    if not isinstance(parents, list):
        raise ValueError("diagnostic parents must be a list")
    rebuilt = {}
    for parent in parents:
        if not isinstance(parent, dict) or set(parent) - {"task_id", "train", "test", "selection"}:
            raise ValueError("unexpected diagnostic parent fields")
        task = parent.get("task_id")
        if not isinstance(task, str) or task not in challenge or task in rebuilt:
            raise ValueError("unexpected or duplicate diagnostic parent")
        reject_gold(parent.get("selection", {}))
        tests = parent.get("test")
        if not isinstance(tests, list):
            raise ValueError("diagnostic tests must be a list")
        stripped = []
        for i, query in enumerate(tests):
            exact_fields(query, {"input", "test_index", "query_id"}, "diagnostic test")
            if type(query["test_index"]) is not int or query["test_index"] != i or query["query_id"] != f"{task}:{i}":
                raise ValueError("diagnostic test identity/order mismatch")
            stripped.append({"input": query["input"]})
        rebuilt[task] = {"train": parent.get("train"), "test": stripped}
    validate_challenge(rebuilt)
    if rebuilt != challenge:
        raise ValueError("diagnostic plan does not match the entire challenge")


def read_diagnostic(value, challenge, plan, seal, candidate_hash, strategy):
    """Adapt selected grids, not evaluator results or a claimed scientific pass.

    Check actual inventory, pool membership, frequency ordering, and declared
    finite rank ordering. NLL/token/conditioning audits deliberately remain the
    responsibility of the independent scientific auditor, not this exporter.
    """
    if strategy not in ("vote", "rescored"):
        raise ValueError("diagnostic source requires explicit vote or rescored strategy")
    _diagnostic_plan(plan, challenge)
    reject_gold(value)
    reject_gold(seal)
    if not isinstance(seal, dict) or set(seal) - {"worker_exited", "returncode", "timed_out", "result_sha256", "receipts"}:
        raise ValueError("unexpected diagnostic seal fields")
    if not isinstance(seal, dict) or seal.get("worker_exited") is not True or seal.get("result_sha256") != candidate_hash:
        raise ValueError("diagnostic result is not bound to an exited-worker prediction seal")
    result_fields = {"schema", "status", "phase", "queries", "backend", "context_admission",
                     "projections", "ranking_formula", "errors", "declared_initial_context_cap",
                     "timings", "counts", "budget", "full_panel_complete", "capability_claim",
                     "planned_budget_mode"}
    if not isinstance(value, dict) or set(value) - result_fields:
        raise ValueError("unexpected diagnostic worker result fields")
    if not isinstance(value, dict) or value.get("schema") != "iris-public-sft141-worker-v1":
        raise ValueError("unsupported diagnostic worker result")
    expected = validate_challenge(challenge)
    source_rows = value.get("queries")
    if not isinstance(source_rows, list):
        raise ValueError("diagnostic queries must be a list")
    rows = {}
    allowed = {"task_id", "test_index", "query_id", "prompt_tokens_by_view", "views",
               "candidates", "vote", "rescored", "vote_complete", "rescoring_complete", "status"}
    for row in source_rows:
        if not isinstance(row, dict) or set(row) - allowed:
            raise ValueError("unexpected diagnostic query fields")
        task, index = row.get("task_id"), row.get("test_index")
        if not isinstance(task, str) or type(index) is not int:
            raise ValueError("invalid diagnostic task/index types")
        key = task, index
        if key not in expected or key in rows or row.get("query_id") != f"{task}:{index}":
            raise ValueError("unexpected, duplicate or mismatched diagnostic query identity")
        pool = row.get("candidates")
        if not isinstance(pool, list) or len(pool) > 8:
            raise ValueError("invalid diagnostic candidate inventory")
        by_key = {}
        for candidate in pool:
            exact_fields(candidate, {"canonical_key", "grid", "count", "view_nll", "mean_nll", "combined_score"}, "diagnostic candidate")
            grid = validate_grid(candidate["grid"])
            ckey = grid_key(grid)
            if ckey != candidate["canonical_key"] or ckey in by_key:
                raise ValueError("duplicate or mismatched diagnostic candidate grid identity")
            if type(candidate["count"]) is not int or not 1 <= candidate["count"] <= 8:
                raise ValueError("invalid diagnostic occurrence count")
            by_key[ckey] = candidate
        if sum(c["count"] for c in pool) > 8:
            raise ValueError("diagnostic counts exceed eight generation views")
        # Validate both selections, even when only one strategy will be used.
        selections = {}
        for name in ("vote", "rescored"):
            selections[name] = validate_candidates(row.get(name))
            if any(grid_key(grid) not in by_key for grid in selections[name]):
                raise ValueError("selected grid is absent from diagnostic candidate pool")
        voted = [by_key[k]["grid"] for k in sorted(by_key, key=lambda k: (-by_key[k]["count"], k))[:2]]
        if selections["vote"] != voted:
            raise ValueError("vote selection differs from declared candidate occurrence ordering")
        if selections["rescored"]:
            for candidate in pool:
                score = candidate["combined_score"]
                try:
                    finite_score = type(score) in (int, float) and math.isfinite(score)
                except OverflowError:
                    finite_score = False
                if not finite_score:
                    raise ValueError("rescored selection lacks finite scores for the complete pool")
            ranked = [by_key[k]["grid"] for k in sorted(by_key, key=lambda k: (-by_key[k]["combined_score"], k))[:2]]
            if selections["rescored"] != ranked:
                raise ValueError("rescored selection differs from declared complete-pool score ordering")
        rows[key] = selections[strategy]
    if set(rows) != set(expected):
        raise ValueError("missing or gapped diagnostic query identities; use explicit empty query selections")
    return rows, {"level": "sealed-result-and-plan-inventory-checked-scientifically-unaudited",
                  "scientific_audit_verified": False,
                  "ranking_or_model_execution_verified": False,
                  "seal_is_signature": False,
                  "nll_and_raw_token_audit_performed": False,
                  "complete_flags_trusted": False}


def validate_submission(challenge, submission):
    validate_challenge(challenge)
    if not isinstance(submission, dict) or set(submission) != set(challenge):
        raise ValueError("submission task IDs must exactly match challenge")
    for task_id, task in challenge.items():
        entries = submission[task_id]
        if not isinstance(entries, list) or len(entries) != len(task["test"]):
            raise ValueError("submission must preserve every test query in original order")
        for entry in entries:
            exact_fields(entry, {"attempt_1", "attempt_2"}, "submission query")
            validate_grid(entry["attempt_1"])
            validate_grid(entry["attempt_2"])


def build_submission(challenge, rows, *, fallback="fail"):
    inventory = validate_challenge(challenge)
    if set(rows) != set(inventory):
        raise ValueError("candidate identity inventory must exactly equal challenge")
    if fallback not in ("fail", "copy-input"):
        raise ValueError("unsupported fallback policy")
    # Validate the entire source before constructing output, including later rows.
    selected = {key: validate_candidates(value) for key, value in rows.items()}
    missing = [key for key, candidates in selected.items() if not candidates]
    if missing and fallback == "fail":
        raise ValueError(f"{len(missing)} queries have no candidates; default is fail-closed")
    submission, queries = {}, []
    counts = {"tasks": len(challenge), "queries": len(inventory),
              "two_distinct_selected_queries": 0, "singleton_duplicated_queries": 0,
              "fallback_queries": 0, "selected_attempts": 0,
              "duplicate_padding_attempts": 0, "fallback_attempts": 0}
    for task_id, task in challenge.items():
        submission[task_id] = []
        for i in range(len(task["test"])):
            grids = selected[(task_id, i)]
            n = len(grids)
            if n == 0:
                first = second = inventory[(task_id, i)]
                mode = "copy-input-fallback"
                counts["fallback_queries"] += 1
                counts["fallback_attempts"] += 2
            elif n == 1:
                first = second = grids[0]
                mode = "one-selection-duplicated"
                counts["singleton_duplicated_queries"] += 1
                counts["selected_attempts"] += 1
                counts["duplicate_padding_attempts"] += 1
            else:
                first, second = grids
                mode = "two-distinct-selections"
                counts["two_distinct_selected_queries"] += 1
                counts["selected_attempts"] += 2
            submission[task_id].append({"attempt_1": first, "attempt_2": second})
            queries.append({"task_id": task_id, "test_index": i, "selected_candidates": n,
                            "mode": mode, "attempts_equal": first == second})
    validate_submission(challenge, submission)
    return submission, counts, queries

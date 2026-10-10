"""Demos-only stage bookkeeping and reproducible ordering diagnostics.

This module never executes generated code or loads a model. ``verify_callback``
must be the runner's accounted, isolated verifier; cached ordering diagnostics
are not replacements for fresh budgeted search checks. Demo fit is evidence of
expressibility on exposed demonstrations, never query accuracy or N14 promotion.
"""
from __future__ import annotations

import hashlib
import json
import math

ENGINEERING_TASK_IDS = (
    "68bc2e87", "fafffa47", "33067df9", "996ec1f3",
    "66e6c45b", "c444b776", "7ec998c9", "b25e450b",
)
KNOWN_STATUSES = {"fit", "mismatch", "out_of_domain", "admission_rejected"}
STATUSES = KNOWN_STATUSES | {"unavailable", "missing", "unknown"}
ARMS = ("uniform", "smoothed", "hard_pruned")
FULL_BASE_CANDIDATES = 5965


class StageError(ValueError):
    """Malformed stage input; never silently coerce types or schemas."""


class StopCoverage(RuntimeError):
    """Runner budget/deadline stop. Unvisited checks stay in the denominator.

    ``current_status='unknown'`` is appropriate only if the current check was
    reserved/dispatched and its outcome cannot be established. The default
    describes a stop before dispatch. Accounting remains the runner's duty.
    """

    def __init__(self, reason, *, current_status="missing"):
        if current_status not in {"missing", "unknown"}:
            raise StageError("stop status must be missing or unknown")
        super().__init__(str(reason))
        self.current_status = current_status


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise StageError("value is not bounded JSON-compatible data") from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _clone(value):
    return json.loads(canonical(value))


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise StageError(name + " must be an integer >= " + str(minimum))
    return value


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise StageError(name + " must be finite and nonnegative")
    return value


def _grid(value):
    if (type(value) is not list or not 1 <= len(value) <= 30
            or any(type(row) is not list for row in value)
            or not 1 <= len(value[0]) <= 30
            or any(len(row) != len(value[0]) for row in value)
            or any(type(cell) is not int or not 0 <= cell <= 9
                   for row in value for cell in row)):
        raise StageError("grid must be rectangular 1..30 with integer colors 0..9")


def validate_task(task):
    if type(task) is not dict or set(task) != {"task_id", "demos"}:
        raise StageError("task must contain exactly task_id and demos")
    if (type(task["task_id"]) is not str or not task["task_id"]
            or len(task["task_id"].encode("utf-8")) > 128):
        raise StageError("task_id must be a nonempty bounded string")
    if type(task["demos"]) is not list or not 1 <= len(task["demos"]) <= 10:
        raise StageError("task requires one to ten demonstrations")
    for pair in task["demos"]:
        if type(pair) is not dict or set(pair) != {"input", "output"}:
            raise StageError("demonstration must contain exactly input and output")
        _grid(pair["input"])
        _grid(pair["output"])
    return _clone(task)


def validate_tasks(tasks, expected_task_ids=ENGINEERING_TASK_IDS):
    if type(tasks) is not list or not tasks:
        raise StageError("tasks must be a nonempty list")
    result = [validate_task(task) for task in tasks]
    ids = [task["task_id"] for task in result]
    if len(ids) != len(set(ids)):
        raise StageError("duplicate task_id")
    if expected_task_ids is not None and ids != list(expected_task_ids):
        raise StageError("task IDs/order differ from the frozen exposed set")
    return result


def parse_tasks(text, expected_task_ids=ENGINEERING_TASK_IDS):
    if type(text) is not str or len(text.encode("utf-8")) > 2_000_000:
        raise StageError("task JSON byte limit")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise StageError("duplicate JSON key")
            result[key] = value
        return result

    def no_float(_):
        raise StageError("floating-point/nonfinite task data forbidden")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_float=no_float,
                           parse_constant=no_float)
        return validate_tasks(value, expected_task_ids)
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        if isinstance(exc, StageError):
            raise
        raise StageError("invalid bounded task JSON") from exc


def _pool(candidates, *, base_sha=None, receipts=None):
    plans = [row["plan"] for row in candidates]
    pool_sha = digest(plans)
    return {"candidates": candidates, "pool_sha256": pool_sha,
            "base_inventory_sha256": base_sha or pool_sha,
            "pool_kind": "base" if all(row["origin"] == "base" for row in candidates)
            else "base_plus_roots", "receipts": receipts or []}


def _read_pool(value):
    """Normalize a raw inventory or validate a previously frozen pool binding."""
    if type(value) is list:
        rows = [{"candidate_id": digest(plan), "plan": _clone(plan), "origin": "base"}
                for plan in value]
        result = _pool(rows)
    elif type(value) is dict and type(value.get("candidates")) is list:
        result = _clone(value)
        rows = result["candidates"]
        for row in rows:
            if (type(row) is not dict or row.get("candidate_id") != digest(row.get("plan"))
                    or row.get("origin") not in {"base", "proposal"}):
                raise StageError("invalid candidate binding")
        if result.get("pool_sha256") != digest([row["plan"] for row in rows]):
            raise StageError("pool hash mismatch")
        base = [row["plan"] for row in rows if row["origin"] == "base"]
        if result.get("base_inventory_sha256") != digest(base):
            raise StageError("base inventory hash mismatch")
        expected_kind = "base" if len(base) == len(rows) else "base_plus_roots"
        if result.get("pool_kind") != expected_kind:
            raise StageError("pool kind mismatch")
    else:
        raise StageError("inventory must be plans or a frozen common pool")
    if not rows or len({row["candidate_id"] for row in rows}) != len(rows):
        raise StageError("inventory must be nonempty with unique plans")
    return result


def freeze_base_inventory(inventory, compile_callback):
    """Compile once, then reuse the exact bound base pool for all task arms."""
    pool = _read_pool(inventory)
    if pool["pool_kind"] != "base":
        raise StageError("base freeze cannot contain proposals")
    for row in pool["candidates"]:
        source = compile_callback(_clone(row["plan"]))
        if type(source) is not str or not source:
            raise StageError("compiler did not return bounded source text")
        row["source_sha256"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return pool


def build_common_pool(base_inventory, proposals, compile_callback, *, max_additions=2):
    """Append at most two legal roots, with a receipt for every proposal.

    Every root is compiled before admission, including three-step plans and
    overflow candidates. Duplicate and overflow are provenance outcomes, not
    claims that a legal program lies outside the language.
    """
    if type(max_additions) is not int or not 0 <= max_additions <= 2:
        raise StageError("root additions must be an integer within 0..2")
    if type(proposals) is not list:
        raise StageError("proposals must be a list")
    base = _read_pool(base_inventory)
    if base["pool_kind"] != "base":
        raise StageError("common pool must begin with base only")
    # A precompiled base avoids repeating thousands of identical compilations.
    if not all(type(row.get("source_sha256")) is str for row in base["candidates"]):
        base = freeze_base_inventory(base, compile_callback)
    rows, receipts = base["candidates"], []
    seen = {row["candidate_id"] for row in rows}
    added = 0
    for index, plan in enumerate(proposals):
        receipt = {"proposal_index": index}
        try:
            source = compile_callback(_clone(plan))
            if type(source) is not str or not source:
                raise StageError("compiler returned no bounded source")
            candidate_id = digest(plan)
            receipt.update(candidate_id=candidate_id, legal=True,
                           source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest())
            if candidate_id in seen:
                receipt["status"] = "duplicate"
            elif added >= max_additions:
                receipt["status"] = "overflow"
            else:
                receipt["status"] = "added"
                rows.append({"candidate_id": candidate_id, "plan": _clone(plan),
                             "origin": "proposal", "source_sha256": receipt["source_sha256"]})
                seen.add(candidate_id)
                added += 1
        except Exception as exc:
            receipt.update(status="out_of_domain", legal=False,
                           reason=type(exc).__name__ + ": " + str(exc)[:300])
        receipts.append(receipt)
    return _pool(rows, base_sha=base["base_inventory_sha256"], receipts=receipts)


def _receipt(value):
    if type(value) is not dict or value.get("status") not in STATUSES:
        raise StageError("verifier receipt has invalid status")
    status = value["status"]
    fit = value.get("all_demos_fit", False)
    known = value.get("known", status in KNOWN_STATUSES)
    if type(fit) is not bool or type(known) is not bool:
        raise StageError("receipt booleans must be exact booleans")
    if fit != (status == "fit") or known != (status in KNOWN_STATUSES):
        raise StageError("verifier receipt is internally inconsistent")
    for key in ("gas", "gas_charged", "checks", "prompt_tokens", "output_tokens"):
        if key in value and value[key] is not None:
            _integer(value[key], key)
    for key in ("wall_seconds", "worker_cpu_seconds"):
        if key in value and value[key] is not None:
            _finite(value[key], key)
    result = _clone(value)
    result.update(all_demos_fit=fit, known=known)
    return result


def _unvisited(reason, status="missing"):
    return {"status": status, "known": False, "all_demos_fit": False,
            "gas": None, "wall_seconds": 0, "reason": str(reason)[:400]}


def _counts(results):
    counts = {status: 0 for status in sorted(STATUSES)}
    for receipt in results:
        counts[receipt["status"]] += 1
    return {"status_counts": counts,
            "executed": sum(counts[status] for status in KNOWN_STATUSES),
            "missing": counts["missing"] + counts["unavailable"],
            "unknown": counts["unknown"], "planned": len(results)}


def _evaluate_checks(jobs, verify_callback):
    """Use the controller's bounded batch API, or the serial callback contract."""
    batch = getattr(verify_callback, "batch", None)
    if callable(batch):
        report = batch((_clone(task), _clone(plan)) for task, plan in jobs)
        rows = []
        for value in report["results"]:
            try:
                rows.append(_receipt(value))
            except Exception as exc:
                rows.append(_unvisited(type(exc).__name__ + ": " + str(exc), "unknown"))
        return rows, report["stop_reason"], report["callback_invocations"], report["workers_used"]
    rows, stopped, invocations = [], None, 0
    for task, plan in jobs:
        if stopped is not None:
            receipt = _unvisited(stopped)
        else:
            invocations += 1
            try:
                receipt = _receipt(verify_callback(_clone(task), _clone(plan)))
            except StopCoverage as exc:
                stopped = str(exc)
                receipt = _unvisited(stopped, exc.current_status)
            except Exception as exc:
                receipt = _unvisited(type(exc).__name__ + ": " + str(exc), "unknown")
        rows.append(receipt)
    return rows, stopped, invocations, int(invocations > 0)


def run_coverage(tasks, inventory, verify_callback, *, profile="SMOKE",
                 expected_task_ids=ENGINEERING_TASK_IDS):
    """Retain a closed diagnostic denominator even when CPU verification stops."""
    if profile not in {"SMOKE", "FULL"}:
        raise StageError("coverage profile must be SMOKE or FULL")
    tasks = validate_tasks(tasks, expected_task_ids)
    pool = _read_pool(inventory)
    evaluated, stopped, callback_invocations, workers_used = _evaluate_checks(
        ((task, candidate["plan"]) for task in tasks for candidate in pool["candidates"]),
        verify_callback)
    if len(evaluated) != len(tasks) * len(pool["candidates"]):
        raise StageError("batch verifier did not preserve the coverage denominator")
    receipts, task_results = iter(evaluated), []
    for task in tasks:
        results = []
        for candidate in pool["candidates"]:
            receipt = next(receipts)
            if "candidate_id" in receipt and receipt["candidate_id"] != candidate["candidate_id"]:
                receipt = _unvisited("verifier candidate binding differs", "unknown")
            results.append({**receipt, "candidate_id": candidate["candidate_id"]})
        counts = _counts(results)
        witnesses = [row["candidate_id"] for row in results if row["status"] == "fit"]
        complete = counts["missing"] == counts["unknown"] == 0
        task_results.append({"task_id": task["task_id"], "task_sha256": digest(task),
                             "results": results, **counts, "complete": complete,
                             "demo_fit": bool(witnesses), "witness_ids": witnesses,
                             "conclusion": "demo_fit" if witnesses else
                             "no_witness_in_inventory" if complete else "inconclusive"})
    all_results = [row for task in task_results for row in task["results"]]
    counts = _counts(all_results)
    return {"profile": profile, "scope": "exposed_demos_only",
            "pool_kind": pool["pool_kind"], "pool_sha256": pool["pool_sha256"],
            "base_inventory_sha256": pool["base_inventory_sha256"],
            "candidate_count": len(pool["candidates"]), "task_denominator": len(tasks),
            "task_ids": [task["task_id"] for task in tasks], "tasks": task_results,
            **counts, "callback_invocations": callback_invocations,
            "workers_used": workers_used,
            "complete": counts["missing"] == counts["unknown"] == 0,
            "demo_fit_tasks": sum(task["demo_fit"] for task in task_results),
            "stop_reason": stopped, "n14_promotion": False,
            "interpretation": "No witness means no fit in this fixed inventory under the pinned gas/runtime domain; "
                              "out_of_domain includes runtime/gas exclusions. Unknown and unvisited checks are not negatives."}


def run_controls(controls, verify_callback):
    if type(controls) is not list or not controls:
        raise StageError("nonempty positive and negative controls required")
    definitions, seen = [], set()
    for control in controls:
        required = {"control_id", "task", "plan", "expected_status"}
        if type(control) is not dict or not required <= set(control):
            raise StageError("invalid control definition")
        control_id = control["control_id"]
        if type(control_id) is not str or not control_id or control_id in seen:
            raise StageError("control IDs must be nonempty and unique")
        expected = control["expected_status"]
        if expected not in KNOWN_STATUSES:
            raise StageError("control must expect a known verifier status")
        seen.add(control_id)
        definitions.append({**_clone(control), "task": validate_task(control["task"])})
    evaluated, stopped, invocations, workers_used = _evaluate_checks(
        ((control["task"], control["plan"]) for control in definitions), verify_callback)
    if len(evaluated) != len(definitions):
        raise StageError("batch verifier did not preserve the control denominator")
    rows = []
    for control, receipt in zip(definitions, evaluated):
        rows.append({"control_id": control["control_id"],
                     "definition_sha256": digest(control),
                     "expected_status": control["expected_status"],
                     "category": "positive" if control["expected_status"] == "fit" else "negative",
                     "as_expected": receipt["status"] == control["expected_status"],
                     "receipt": receipt})
    counts = _counts([row["receipt"] for row in rows])
    positive = sum(row["category"] == "positive" for row in rows)
    negative = len(rows) - positive
    return {"controls": rows, "definitions_sha256": digest(definitions), **counts,
            "callback_invocations": invocations, "workers_used": workers_used,
            "positive_count": positive, "negative_count": negative,
            "all_expected": bool(positive and negative) and all(row["as_expected"] for row in rows),
            "complete": counts["missing"] == counts["unknown"] == 0,
            "stop_reason": stopped}


def testability_gate(controls, coverage, ledger_complete, *, profile="FULL",
                     expected_base_inventory_sha256=None, expected_candidate_count=None):
    """A base-only research testability gate; no query evaluation or promotion."""
    if type(ledger_complete) is not bool:
        raise StageError("ledger_complete must be an exact boolean")
    reasons = []
    if profile != "FULL" or coverage.get("profile") != "FULL":
        reasons.append("FULL profile required; SMOKE never enables models")
    if (coverage.get("pool_kind") != "base"
            or coverage.get("pool_sha256") != coverage.get("base_inventory_sha256")):
        reasons.append("gate requires base inventory only")
    if (type(expected_base_inventory_sha256) is not str
            or coverage.get("base_inventory_sha256") != expected_base_inventory_sha256):
        reasons.append("frozen base inventory binding missing or different")
    if (type(expected_candidate_count) is not int or expected_candidate_count != FULL_BASE_CANDIDATES
            or type(coverage.get("candidate_count")) is not int
            or coverage.get("candidate_count") != FULL_BASE_CANDIDATES):
        reasons.append("frozen base inventory count missing or different")
    if (coverage.get("task_ids") != list(ENGINEERING_TASK_IDS)
            or coverage.get("task_denominator") != len(ENGINEERING_TASK_IDS)):
        reasons.append("full fixed exposed-task denominator required")
    if coverage.get("complete") is not True or coverage.get("missing") != 0 or coverage.get("unknown") != 0:
        reasons.append("base coverage incomplete or uncertain")
    if (controls.get("complete") is not True or controls.get("all_expected") is not True
            or type(controls.get("positive_count")) is not int or controls["positive_count"] != 64
            or type(controls.get("negative_count")) is not int or controls["negative_count"] != 64):
        reasons.append("all 64 positive and 64 negative controls must meet expectations")
    if not ledger_complete:
        reasons.append("physical-call ledger incomplete")
    fit_count = coverage.get("demo_fit_tasks")
    if type(fit_count) is not int or fit_count < 2:
        reasons.append("at least two exposed tasks must have base-inventory demo fit")
    return {"passed": not reasons, "reasons": reasons, "profile": profile,
            "gate": "research_testability_only", "n14_promotion": False,
            "generalization_claim": False, "diagnostic_archive_required": True}


def order_diagnostics(pool, results, production_support, seed, budget, *,
                      production_ids_callback, task_id=None, smoothing=1.0):
    """Rank one common pool three ways without dispatching any CPU/model work.

    Hard-pruned candidates remain in the bound pool and in the full ranking,
    but are explicitly ineligible for that arm's logical expansion window.
    Physical matched-budget search must separately reverify chosen candidates.
    """
    pool = _read_pool(pool)
    _integer(seed, "seed")
    _integer(budget, "budget")
    _finite(smoothing, "smoothing")
    if smoothing == 0:
        raise StageError("smoothing must be positive")
    if type(production_support) is not dict:
        raise StageError("production support must map production IDs to counts")
    for key, value in production_support.items():
        if type(key) is not str:
            raise StageError("production ID must be a string")
        _integer(value, "production support")
    if type(results) is dict and "results" in results:
        results = results["results"]
    if type(results) is dict:
        result_map = {key: _receipt(value) for key, value in results.items()}
    elif type(results) is list:
        result_map = {}
        for row in results:
            candidate_id = row.get("candidate_id") if type(row) is dict else None
            if type(candidate_id) is not str or candidate_id in result_map:
                raise StageError("duplicate or missing result candidate binding")
            result_map[candidate_id] = _receipt(row)
    else:
        raise StageError("results must be candidate-bound receipts")
    ids = [row["candidate_id"] for row in pool["candidates"]]
    if set(result_map) - set(ids):
        raise StageError("result contains a candidate outside common pool")
    features = {}
    for row in pool["candidates"]:
        values = production_ids_callback(_clone(row["plan"]))
        if type(values) not in (list, tuple) or not values or any(type(x) is not str for x in values):
            raise StageError("compiler production IDs must be a nonempty string list")
        features[row["candidate_id"]] = list(values)
    vocabulary = set(x for values in features.values() for x in values)
    denominator = sum(production_support.get(x, 0) for x in vocabulary) + smoothing * len(vocabulary)
    scores = {cid: sum(math.log((production_support.get(x, 0) + smoothing) / denominator)
                       for x in values) for cid, values in features.items()}
    supported = {cid: all(production_support.get(x, 0) > 0 for x in values)
                 for cid, values in features.items()}
    tie = {cid: digest({"seed": seed, "pool_sha256": pool["pool_sha256"], "candidate_id": cid})
           for cid in ids}
    orderings = {
        "uniform": sorted(ids, key=lambda cid: (tie[cid], cid)),
        "smoothed": sorted(ids, key=lambda cid: (-scores[cid], tie[cid], cid)),
        "hard_pruned": sorted(ids, key=lambda cid: (not supported[cid], -scores[cid], tie[cid], cid)),
    }
    arms = {}
    for arm, ordered in orderings.items():
        eligible = [cid for cid in ordered if arm != "hard_pruned" or supported[cid]]
        expanded = eligible[:budget]
        receipts = [result_map.get(cid, _unvisited("no accounted cached result")) for cid in expanded]
        witness = next(((index + 1, cid) for index, (cid, receipt) in
                        enumerate(zip(expanded, receipts)) if receipt["status"] == "fit"), None)
        counts = _counts(receipts)
        arms[arm] = {"pool_sha256": pool["pool_sha256"], "pool_size": len(ids),
                     "ordering_sha256": digest(ordered), "ordering": ordered,
                     "eligible_count": len(eligible), "excluded_count": len(ids) - len(eligible),
                     "expansion_budget": budget, "expanded_ids": expanded,
                     "logical_expansions": len(expanded), **counts,
                     "first_witness_expansion": witness[0] if witness else None,
                     "first_witness_id": witness[1] if witness else None,
                     "success_at_expansions": [bool(witness and witness[0] <= n)
                                               for n in range(1, budget + 1)],
                     "success": witness is not None,
                     "conclusive": counts["missing"] == counts["unknown"] == 0}
    return {"task_id": task_id, "seed": seed, "pool_sha256": pool["pool_sha256"],
            "production_support_sha256": digest(production_support), "arms": arms,
            "physical_verifier_calls": 0, "physical_model_calls": 0,
            "reexecution_required": True, "scope": "cached_ordering_diagnostic_only"}


def summarize_ordering(diagnostics, *, expected_task_ids=ENGINEERING_TASK_IDS):
    """Keep missing task diagnostics in every success denominator."""
    if type(diagnostics) is not dict or set(diagnostics) - set(expected_task_ids):
        raise StageError("ordering diagnostics must be keyed by expected task ID")
    denominator = len(expected_task_ids)
    if not denominator:
        raise StageError("empty task denominator")
    arms = {}
    for arm in ARMS:
        observed = [diagnostics[tid]["arms"][arm] for tid in expected_task_ids if tid in diagnostics]
        budgets = {row["expansion_budget"] for row in observed}
        if len(budgets) > 1:
            raise StageError("cannot aggregate unmatched expansion budgets")
        budget = next(iter(budgets), 0)
        arms[arm] = {"task_denominator": denominator,
                     "missing_tasks": [tid for tid in expected_task_ids if tid not in diagnostics],
                     "successful_tasks": sum(row["success"] for row in observed),
                     "success_rate": sum(row["success"] for row in observed) / denominator,
                     "success_at_expansions": [sum(row["success_at_expansions"][n] for row in observed)
                                               / denominator for n in range(budget)],
                     "inconclusive_tasks": sum(not row["conclusive"] for row in observed)
                     + denominator - len(observed)}
    return {"arms": arms, "scope": "cached_ordering_diagnostic_only",
            "physical_verifier_calls": 0, "reexecution_required": True}

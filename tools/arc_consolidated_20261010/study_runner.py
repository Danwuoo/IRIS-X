"""Fixed eighty-slot study and separately charged matched-budget CPU search.

Production owns one exact G4 backend in the prepared offline interpreter. Synthetic backends require an explicit
internal evidence label bound into the durable ledger; notebooks cannot supply
one. This controller does not train, install, score queries or change N14.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, replace
import json
import time

from . import arc_object_ir as ir, assets, model_provider as mp, stages
from .ledger import BindingMismatch, BudgetExceeded, digest as ledger_digest

RUNTIME_MANIFEST_SHA256 = "c2e7913e8ae208deb26e06f37fcd76c79c1a87b6c49ffb3de7b2ee054fee7e67"
SEARCH_SEEDS = (0, 1, 2)
SEARCH_BUDGET = 64


def _validated_plan(value):
    plan = ir.validate_plan(value)
    ir.compile_plan(plan)
    return plan


def _feedback(task, root, receipt):
    status = receipt.get("status", "unknown")
    matches = [None] * len(task["demos"])
    for index, demo in enumerate(receipt.get("demos", [])):
        if index < len(matches) and type(demo.get("match")) is bool:
            matches[index] = demo["match"]
    if status == "fit":
        matches = [True] * len(matches)
    if status in ("unknown", "missing", "unavailable", "excluded_token_budget", "excluded_missing_root"):
        feedback_status = "unknown"
    elif status in ("fit", "mismatch"):
        feedback_status = "verified"
    elif status == "invalid_plan" or root.status == "invalid":
        feedback_status = "invalid_plan"
    else:
        feedback_status = "verification_failed"
    return {"status": feedback_status,
            "demo_matches": matches, "response_sha256": root.response_sha256}


def _configuration(config, evidence_mode, backend_factory):
    if evidence_mode not in ("production", "synthetic-test-only") or type(config) is not dict:
        raise ValueError("explicit model configuration and evidence mode required")
    expected = {"environment_sha256"}
    if evidence_mode == "production":
        expected |= {"prepared_bootstrap", "source_identity"}
        if backend_factory is not None:
            raise ValueError("production cannot inject a backend")
    elif not callable(backend_factory):
        raise ValueError("synthetic mode requires an internal synthetic backend")
    if set(config) != expected:
        raise ValueError("model configuration must have exactly the frozen fields")
    if evidence_mode == "production":
        return None
    return backend_factory


def _closed_slot(ledger, request, status, details):
    """Persist exclusions without claiming a physical generation happened."""
    call_id = "slot/" + request.spec.call_id
    operation = ledger.operation(call_id)
    payload = {"request_sha256": request.sha256, "status": status, "details": details}
    if operation is not None:
        saved = ledger.get_response(call_id)
        if saved != payload:
            raise BindingMismatch("excluded slot binding changed")
        if operation["status"] == "responded":
            ledger.finish(call_id)
        return saved
    ledger.reserve("overhead", call_id, {"physical_calls": 0}, metadata={"request_sha256": request.sha256})
    ledger.record_response(call_id, payload)
    ledger.finish(call_id)
    return payload


def _search(tasks, base_pool, coverage, roots, ledger, verify_callback):
    cached, physical, pools = [], [], []
    before_checks = ledger.summary()["charged"].get("search_checks", 0)
    coverage_by_id = {row["task_id"]: row for row in coverage.get("tasks", [])}
    for task in tasks:
        tid = task["task_id"]
        task_roots = [root for root in roots.values() if root.call_id.startswith(tid + "/root/")]
        proposals = [json.loads(root.plan_json) for root in task_roots if root.plan_json is not None]
        pool = stages.build_common_pool(base_pool, proposals, ir.compile_plan, max_additions=2)
        support = Counter(p for plan in proposals for p in ir.production_ids(plan))
        by_id = {row["candidate_id"]: row for row in pool["candidates"]}
        pools.append({k: v for k, v in pool.items() if k != "candidates"})
        for seed in SEARCH_SEEDS:
            diagnostic = stages.order_diagnostics(pool, coverage_by_id.get(tid, {}).get("results", []),
                dict(support), seed, SEARCH_BUDGET, production_ids_callback=ir.production_ids, task_id=tid)
            cached.append({**diagnostic, "arms": {arm: {k: v for k, v in row.items() if k != "ordering"}
                                                   for arm, row in diagnostic["arms"].items()}})
            for arm in stages.ARMS:
                selected = diagnostic["arms"][arm]["expanded_ids"]
                results = []
                for position in range(SEARCH_BUDGET):
                    if position >= len(selected):
                        results.append({"position": position + 1, "status": "excluded_hard_pruned" if arm == "hard_pruned" else "excluded_pool_exhausted",
                                        "known": True, "all_demos_fit": False, "dispatched": False})
                        continue
                    cid = selected[position]
                    call_id = "/".join((tid, "tie", str(seed), arm, cid))
                    try:
                        ledger.check_deadline()
                        receipt = verify_callback(task, by_id[cid]["plan"], scope="search", call_id=call_id)
                    except Exception as exc:
                        receipt = {"status": "unknown", "known": False, "all_demos_fit": False,
                                   "reason": type(exc).__name__ + ": " + str(exc)[:300]}
                    results.append({**receipt, "candidate_id": cid, "position": position + 1})
                physical.append({"task_id": tid, "tie_seed": seed, "arm": arm,
                    "pool_sha256": pool["pool_sha256"], "planned": SEARCH_BUDGET,
                    "logical_eligible": len(selected), "results": results,
                    "first_witness_expansion": next((r["position"] for r in results if r["status"] == "fit"), None),
                    "scope": "separately_accounted_matched_budget_search"})
    curves = []
    for seed in SEARCH_SEEDS:
        for arm in stages.ARMS:
            rows = [r for r in physical if r["tie_seed"] == seed and r["arm"] == arm]
            curves.append({"tie_seed": seed, "arm": arm, "task_denominator": 8,
                "success_at_expansions": [sum(r["first_witness_expansion"] is not None and
                   r["first_witness_expansion"] <= n for r in rows) / 8 for n in range(1, SEARCH_BUDGET + 1)],
                "unknown_tasks": [r["task_id"] for r in rows if any(v["status"] in
                                   ("unknown", "missing", "unavailable") for v in r["results"])]})
    return {"planned": 8 * 3 * 3 * 64, "expansion_budget": SEARCH_BUDGET, "tie_seeds": list(SEARCH_SEEDS),
            "common_pools": pools, "cached_ordering_diagnostics": cached, "physical_search": physical,
            "actual_search_curves": curves,
            "new_physical_checks": ledger.summary()["charged"].get("search_checks", 0) - before_checks,
            "scope": "demo_fit_only", "cache_hits_are_not_physical_search": True}


def run_model_studies(tasks, base_pool, coverage, ledger, *, session_id, model_config,
                      evidence_mode="production", backend_factory=None, verify_callback):
    """The caller must pass the FULL testability gate and own ledger session.

    Roots are shared once; two feedback arms and two memory arms use frozen
    roots, never adaptive replacements. Every pair receives actual token
    admission before either member reserves a physical model call.
    """
    factory = _configuration(model_config, evidence_mode, backend_factory)
    grammar = {"version": ir.IR_VERSION, "contract": ir.plan_contract()}
    study = mp.build_study_plan(tasks, grammar=grammar,
                               environment_sha256=model_config["environment_sha256"])
    expected = {"mode": ledger_digest(evidence_mode), "model": study.model_sha256,
                "environment": study.environment_sha256, "task": assets.digest(tasks),
                "prompt": study.prompt_template_sha256, "sampling": assets.digest(asdict(study.sampling))}
    if any(ledger.bindings.get(k) != v for k, v in expected.items()):
        raise BindingMismatch("study task/model/prompt/sampling/environment/evidence binding differs")
    if evidence_mode == "production":
        from .remote_model_owner import RemoteModelOwner
        # Construction is inert. The prepared child starts only after durable
        # owner/load reservations below; this process never imports torch.
        owner = RemoteModelOwner(model_config["prepared_bootstrap"],
            environment_plan_sha256=study.environment_sha256,
            source_identity=model_config["source_identity"], enabled=True,
            deadline_monotonic=time.monotonic() + max(0, ledger.remaining_wall_seconds - 60))
    else:
        owner = mp.SingleModelOwner(factory, enabled=True, model_sha256=study.model_sha256,
            environment_sha256=study.environment_sha256, execution_mode="synthetic-test")
    report = {"status": "partial", "evidence_mode": evidence_mode, "profile": study.summary(),
              "planned": 80, "rows": [], "initial_token_audit": [], "actual_pair_admission": [],
              "training_performed": False,
              "runtime_verification": "post_gate_opaque_complete_runtime_integrity" if evidence_mode == "production" else "synthetic_only_no_asset_acceptance"}
    rows = {s.call_id: {"call_id": s.call_id, "task_id": s.task_id, "stage": s.stage, "arm": s.arm,
                       "attribution_arms": list(s.attribution_arms), "status": "missing"} for s in study.calls}
    by_task = {task["task_id"]: task for task in tasks}
    roots, feedback, prepared, requests = {}, {}, {}, {}
    available_roots = set()
    stop_ack = {"model_owner_stopped": False, "vm_billing_stopped": False}
    load_id, load_started, load_open = "load/" + session_id, time.monotonic(), False
    ownership_id, ownership_open = "owner/" + session_id, False
    unresolved_prior = []
    for old_id, old in ledger.summary()["operations"].items():
        if old["kind"] == "model" or old_id.startswith(("load/", "owner/")):
            if old["status"] in ("unknown", "reserved"):
                unresolved_prior.append(old_id)
            elif old_id.startswith("owner/") and "response" in old:
                if ledger.get_response(old_id).get("model_owner_stopped") is not True:
                    unresolved_prior.append(old_id)

    def verify(request, response):
        spec = request.spec
        try:
            plan = ir.parse_plan(response["text"])
            ir.compile_plan(plan)
        except ValueError:
            return None, {"status": "invalid_plan", "all_demos_fit": False, "known": True}
        if response.get("truncated") or response.get("late"):
            return None, {"status": "truncated_or_late", "all_demos_fit": False, "known": True}
        try:
            result = verify_callback(by_task[spec.task_id], plan, scope="model", call_id=spec.call_id)
        except Exception as exc:
            result = {"status": "unknown", "known": False, "all_demos_fit": False,
                      "reason": type(exc).__name__ + ": " + str(exc)[:300]}
        return plan, result

    def consume(request, item):
        spec, operation_id = request.spec, "model/" + request.spec.call_id
        previous = ledger.operation(operation_id)
        reused = previous is not None
        if previous is not None:
            if previous["metadata"] != item.reservation():
                raise BindingMismatch("durable prepared prompt/token/cache binding changed")
            if "response" not in previous:
                rows[spec.call_id].update(status="unknown", cache_reused=False, reason="reserved model call is never retried")
                return None, {"status": "unknown", "known": False, "all_demos_fit": False}
            response = ledger.get_response(operation_id)
            if any(response.get(k) != v for k, v in (("request_sha256", item.sha256),
                ("cache_sha256", item.cache_sha256), ("model_sha256", study.model_sha256),
                ("environment_sha256", study.environment_sha256))):
                raise BindingMismatch("durable response token/model/environment binding differs")
        else:
            duration = min(mp.MAX_MODEL_SECONDS, ledger.remaining_wall_seconds - 1)
            if duration <= 0:
                raise BudgetExceeded("no remaining physical model wall allowance")
            budget = {"prompt_tokens": item.prompt_tokens,
                      "output_tokens": study.sampling.max_output_tokens, "model_seconds": duration}
            if "unknown_model_calls" in ledger.limits:
                budget["unknown_model_calls"] = 1
            ledger.reserve("model", operation_id, budget, metadata=item.reservation())
            model_seconds_before = owner.model_seconds
            try:
                response = owner.dispatch(item, deadline_monotonic=time.monotonic() + duration)
            except Exception as exc:
                # The owner returned control and released its dispatch lock.
                # Its finally block measures generation even when the backend
                # raises. Keep uncertain token/time reservations, but never hide
                # observed time above the reservation. finish persists an excess
                # and raises BudgetExceeded before another slot can dispatch.
                observed_model_seconds = max(0.0, owner.model_seconds - model_seconds_before)
                response = {"request_sha256": item.sha256, "cache_sha256": item.cache_sha256,
                    "model_sha256": study.model_sha256, "environment_sha256": study.environment_sha256,
                    "unknown_physical_call": True, "error_type": type(exc).__name__,
                    "observed_model_seconds": observed_model_seconds,
                    "model_seconds": max(duration, observed_model_seconds)}
                ledger.record_response(operation_id, response)
                rows[spec.call_id].update(status="unknown", cache_reused=False,
                                         reason="dispatch failed after durable reservation; no automatic retry",
                                         error_type=type(exc).__name__, observed_model_seconds=observed_model_seconds)
                ledger.finish(operation_id, {"model_seconds": response["model_seconds"]}, outcome="fail")
                return None, {"status": "unknown", "known": False, "all_demos_fit": False}
            ledger.record_response(operation_id, response)
        if response.get("unknown_physical_call"):
            rows[spec.call_id].update(status="unknown", cache_reused=True,
                                     reason="durable uncertain physical call is never retried")
            if previous["status"] == "responded":
                elapsed_debit = max(previous["budget"]["model_seconds"],
                                    response.get("model_seconds", 0), response.get("observed_model_seconds", 0))
                ledger.finish(operation_id, {"model_seconds": elapsed_debit}, outcome="fail")
            return None, {"status": "unknown", "known": False, "all_demos_fit": False}
        if previous is None or previous["status"] == "responded":
            usage = {k: response[k] for k in ("prompt_tokens", "output_tokens", "model_seconds")}
            if "unknown_model_calls" in ledger.limits:
                usage["unknown_model_calls"] = 0
            ledger.finish(operation_id, usage)
        plan, receipt = verify(request, response)
        rows[spec.call_id].update(status=receipt["status"], response=response, verification=receipt,
                                  cache_reused=reused, plan=plan)
        return response, receipt

    try:
        ledger.reserve("overhead", ownership_id, {"physical_calls": 0}, metadata={"resource": "single_model_owner"})
        ownership_open = True
        available = ledger.limits["load_seconds"] - ledger.summary()["charged"]["load_seconds"]
        allowance = min(1200, available, ledger.remaining_wall_seconds - 65)
        if allowance <= 0:
            raise BudgetExceeded("no tokenizer/model initialization allowance")
        ledger.reserve("overhead", load_id, {"load_seconds": allowance}, metadata={"phase": "tokenizer_audit_and_single_model_load"})
        load_open = True
        if evidence_mode == "production":
            owner.set_initialization_deadline(load_started + allowance)
        owner.initialize_tokenizer()
        root_specs = study.calls[:16]
        placeholder_roots, placeholder_feedback = {}, {}
        for spec in root_specs:
            request = mp.materialize_request(study, spec)
            requests[spec.call_id] = request
            group, admission = owner.prepare_group([request])
            report["initial_token_audit"].append(admission)
            if group:
                old = ledger.operation("model/" + spec.call_id)
                if old is not None and old["metadata"] != group[0].reservation():
                    raise BindingMismatch("initial native token admission differs from durable call")
                if ledger.operation("slot/" + spec.call_id) is not None:
                    raise BindingMismatch("closed root exclusion changed admission")
                prepared[spec.call_id] = group[0]
            else:
                if ledger.operation("model/" + spec.call_id) is not None:
                    raise BindingMismatch("previously reserved root no longer fits token budget")
                saved = _closed_slot(ledger, request, "excluded_token_budget", admission)
                rows[spec.call_id].update(status=saved["status"], admission=admission)
            placeholder = mp.freeze_root(request, '{"steps":[{"op":"identity"}]}', _validated_plan)
            placeholder_roots[spec.call_id] = placeholder
            placeholder_feedback[spec.call_id] = _feedback(by_task[spec.task_id], placeholder, {"status": "unknown"})
        # Predictable templates are audited without registering them as actual
        # dispatch prompts. Actual root text/feedback is admitted again in pairs.
        for spec in study.calls[16:]:
            request = mp.materialize_request(study, spec, frozen_roots=placeholder_roots,
                                             feedback_by_root=placeholder_feedback)
            try:
                audit = owner.prepare(request, register=False)
                report["initial_token_audit"].append({"call_id": spec.call_id, "status": "fits_template",
                                                     "prompt_tokens": audit.prompt_tokens})
            except mp.TokenAdmissionError as exc:
                report["initial_token_audit"].append({"call_id": spec.call_id, "status": "template_overflow",
                                                     "prompt_tokens": exc.observed, "limit": exc.limit})
        needs_generation = any(ledger.operation("model/" + s.call_id) is None and s.call_id in prepared for s in root_specs)
        needs_generation |= any(ledger.operation("model/" + s.call_id) is None and
                                ledger.operation("slot/" + s.call_id) is None for s in study.calls[16:])
        if needs_generation and prepared:
            owner.ensure_model_loaded()
        ledger.record_response(load_id, {"token_audit": report["initial_token_audit"], "accounting": owner.accounting()})
        ledger.finish(load_id, {"load_seconds": time.monotonic() - load_started})
        load_open = False
        for index, spec in enumerate(study.calls):
            if spec.stage == "root":
                request = requests[spec.call_id]
                if spec.call_id in prepared:
                    response, receipt = consume(request, prepared[spec.call_id])
                else:
                    response, receipt = None, {"status": "excluded_token_budget"}
                root = mp.freeze_root(request, response["text"] if response else "", _validated_plan)
                if response is None or response.get("truncated") or response.get("late"):
                    root = replace(root, plan_json=None, status=rows[spec.call_id]["status"])
                roots[spec.call_id] = root
                feedback[spec.call_id] = _feedback(by_task[spec.task_id], root, receipt)
                if response is not None:
                    available_roots.add(spec.call_id)
                continue
            if spec.arm in ("true", "off"):
                pair_specs = study.calls[index:index + 2]
                pair_requests = [mp.materialize_request(study, s, frozen_roots=roots, feedback_by_root=feedback) for s in pair_specs]
                requests.update({r.spec.call_id: r for r in pair_requests})
                required_roots = [spec.root_id] if spec.stage == "feedback" else [
                    r.call_id for r in root_specs if r.task_id == spec.task_id]
                if any(root_id not in available_roots for root_id in required_roots):
                    admission = {"status": "excluded_missing_root", "required_roots": required_roots,
                                 "denominator": 2, "truncated": False}
                    report["actual_pair_admission"].append(admission)
                    for request in pair_requests:
                        saved = _closed_slot(ledger, request, "excluded_missing_root", admission)
                        rows[request.spec.call_id].update(status=saved["status"], admission=admission)
                    continue
                group, admission = owner.prepare_group(pair_requests)
                report["actual_pair_admission"].append(admission)
                if group:
                    for item in group:
                        old = ledger.operation("model/" + item.request.spec.call_id)
                        if old is not None and old["metadata"] != item.reservation():
                            raise BindingMismatch("paired native token admission differs from durable call")
                        if ledger.operation("slot/" + item.request.spec.call_id) is not None:
                            raise BindingMismatch("closed pair exclusion changed admission")
                    prepared.update({item.request.spec.call_id: item for item in group})
                else:
                    for request in pair_requests:
                        if ledger.operation("model/" + request.spec.call_id) is not None:
                            raise BindingMismatch("previously reserved pair no longer fits token budget")
                        saved = _closed_slot(ledger, request, "excluded_token_budget", admission)
                        rows[request.spec.call_id].update(status=saved["status"], admission=admission)
            if spec.call_id in prepared:
                consume(requests[spec.call_id], prepared[spec.call_id])
        stop_ack = owner.close()
        report["search"] = _search(tasks, base_pool, coverage, roots, ledger, verify_callback)
        search_known = all(r["status"] not in ("missing", "unknown", "unavailable")
                           for arm in report["search"]["physical_search"] for r in arm["results"])
        incomplete = {"missing", "unknown", "unavailable", "excluded_token_budget", "excluded_missing_root", "truncated_or_late"}
        report["status"] = "complete" if search_known and all(r["status"] not in incomplete for r in rows.values()) else "partial"
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:2000]}
    finally:
        if load_open:
            try:
                ledger.finish(load_id, {"load_seconds": time.monotonic() - load_started}, outcome="fail")
            except Exception as exc:
                report["load_accounting_error"] = type(exc).__name__ + ": " + str(exc)[:300]
        try:
            stop_ack = owner.close()
        except Exception as exc:
            stop_ack["error"] = type(exc).__name__ + ": " + str(exc)[:300]
        if ownership_open:
            try:
                ledger.record_response(ownership_id, stop_ack)
                ledger.finish(ownership_id, outcome="complete" if stop_ack["model_owner_stopped"] else "fail")
            except Exception as exc:
                stop_ack = {"model_owner_stopped": False, "vm_billing_stopped": False,
                            "error": "ownership receipt persistence failed: " + str(exc)[:300]}
        if unresolved_prior:
            stop_ack = {**stop_ack, "current_owner_stopped": stop_ack["model_owner_stopped"],
                        "model_owner_stopped": False, "prior_uncertain_operations": unresolved_prior,
                        "reconciliation_required": True}
            report["status"] = "partial"
        report["stop_ack"] = stop_ack
        report["owner_accounting"] = owner.accounting()
    report["rows"] = [rows[s.call_id] for s in study.calls]
    known = [row["response"] for row in report["rows"] if "response" in row]
    ledger_snapshot = ledger.summary()
    model_operation_map = {key: op for key, op in ledger_snapshot["operations"].items() if key.startswith("model/")}
    model_operations = list(model_operation_map.values())
    report["physical_usage"] = {"responses": len(known), "known_prompt_tokens": sum(r["prompt_tokens"] for r in known),
        "known_output_tokens": sum(r["output_tokens"] for r in known), "known_model_seconds": sum(r["model_seconds"] for r in known),
        "physical_reservations": len(model_operations),
        "unknown_model_calls_charged": ledger_snapshot["charged"].get("unknown_model_calls", 0),
        "conservative_charged": {k: ledger_snapshot["charged"].get(k, 0) for k in
                                  ("physical_calls", "prompt_tokens", "output_tokens", "model_seconds")},
        "charge_policy": "shared roots physically charged once; arm attributions are counterfactual standalone costs"}
    arms = sorted({arm for row in report["rows"] for arm in row["attribution_arms"]})
    def attributed(selected):
        responses = [row["response"] for row in selected if "response" in row]
        charged = [op.get("usage", op["budget"]) for row in selected
                   if (op := model_operation_map.get("model/" + row["call_id"])) is not None]
        return {"planned": len(selected), "responses": len(responses),
                "known_prompt_tokens": sum(r["prompt_tokens"] for r in responses),
                "known_output_tokens": sum(r["output_tokens"] for r in responses),
                "known_model_seconds": sum(r["model_seconds"] for r in responses),
                "conservative_charged": {key: sum(row.get(key, 0) for row in charged) for key in
                    ("physical_calls", "prompt_tokens", "output_tokens", "model_seconds", "unknown_model_calls")},
                "status_counts": dict(Counter(row["status"] for row in selected)),
                "fitting_tasks": sorted({row["task_id"] for row in selected if row["status"] == "fit"})}
    report["arm_attribution"] = {arm: {**attributed([r for r in report["rows"] if arm in r["attribution_arms"]]),
        "task_denominator": 8, "cost_scope": "standalone_counterfactual_includes_shared_roots_do_not_sum_arms"} for arm in arms}
    feasibility = {row["task_id"]: row.get("demo_fit") if row.get("complete", True) else None
                   for row in coverage.get("tasks", [])}
    report["feasibility_strata"] = {label: {"task_ids": [t["task_id"] for t in tasks if feasibility.get(t["task_id"]) is expected],
        "task_denominator": sum(feasibility.get(t["task_id"]) is expected for t in tasks),
        "overall_task_denominator": 8,
        "arms": {arm: attributed([r for r in report["rows"] if arm in r["attribution_arms"] and
                  feasibility.get(r["task_id"]) is expected]) for arm in arms}}
        for label, expected in (("base_witness", True), ("no_base_witness", False), ("unavailable", None))}
    report["comparison_limit"] = "Matched ceilings and fixed slots; realized prompt/output tokens and time may differ. No equal actual cost claim."
    report.setdefault("search", {"planned": 4608, "status": "not_reached", "physical_search": [], "cached_ordering_diagnostics": []})
    return report

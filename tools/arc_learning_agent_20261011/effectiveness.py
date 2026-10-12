"""Predeclared training/dev capability gates, never public-answer selection.

Exact generated grids are primary. NLL cannot rescue a wrong grid. The authored
controls measure learnability only; they are not held-out ARC generalization.
No target is passed to generation, and all generations precede teacher forcing.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import math
from pathlib import Path
import time
from types import MappingProxyType

from tools.arc_next_models import digest, require
from tools.arc_learning_agent_20261011.budget import digest as declared_order_digest
from tools.arc_learning_agent_20261011.data import _validate_manifest, _demos
from tools.arc_learning_agent_20261011.grid_codec import (
    decode_grid, encode_grid, grid_messages, program_messages, validate_grid)

FORMAT = "irisx/training-dev-effectiveness-panel-v1"
DEFAULT_GATE_POLICY = MappingProxyType({"require_all_authored_controls_exact": True,
                                        "minimum_held_out_dev_exact": 1})
POLICY = {
    "name": "generated-exact-compact-controls-and-dev-v1",
    "control_requirement": "all_predeclared_controls_exact",
    "dev_requirement": "at_least_one_predeclared_held_out_dev_exact",
    "selection_order": ["dev_exact", "control_exact", "dimension_correct", "valid_grid", "lower_mean_nll"],
    "no_public_accuracy_claim": True,
}


def _authored_controls():
    # Independent hand-authored fixtures. These may be explicitly learned as
    # controls, so their successes MUST NOT enter a held-out dev denominator.
    specs = [
        ("reverse-columns", [
            {"input": [[1, 2], [3, 4]], "output": [[2, 1], [4, 3]]},
            {"input": [[0, 5, 6]], "output": [[6, 5, 0]]}],
            [[5, 6, 7], [8, 9, 0]], [[7, 6, 5], [0, 9, 8]]),
        ("transpose", [
            {"input": [[1, 2], [3, 4]], "output": [[1, 3], [2, 4]]},
            {"input": [[5, 6, 7]], "output": [[5], [6], [7]]}],
            [[1, 2, 3], [4, 5, 6]], [[1, 4], [2, 5], [3, 6]]),
    ]
    return [{"case_id": "authored-control:" + name, "scope": "authored_learnability_only",
             "source": {"kind": "independently-authored-known-transform", "transform": name,
                        "generalization_evidence": False,
                        "training_exposure": "not-established-by-this-panel",
                        "interpretation": "simple-transform diagnostic; memorization learnability only if explicitly trained"},
             "demos": demos, "query_input": query, "target": target}
            for name, demos, query, target in specs]


def _rank_ids(ids, seed):
    return sorted(ids, key=lambda key: (declared_order_digest(["declared-task-order", seed, key]), key))


def _dev_case(key, task):
    demos = task["demonstrations"]
    return {"case_id": "training-dev:" + key, "scope": "training_dev_held_out_demo",
            "source": {"kind": "exact-split-manifest", "task_id": key,
                       "task_sha256": task["task_sha256"], "split": "dev",
                       "ancestor_ids": task["ancestor_ids"], "parent_ids": task["parent_ids"],
                       "held_out_demo_index": len(demos) - 1,
                       "visible_demo_indices": list(range(len(demos) - 1))},
            "demos": demos[:-1], "query_input": demos[-1]["input"], "target": demos[-1]["output"]}


def build_panel(tasks, manifest, *, seed=0, dev_tasks=4, protected_ids=(), include_controls=True, gate_policy=None):
    """Freeze exact manifest dev IDs in the existing declared hash order.

    The full manifest remains required at evaluation: a self-rehashed forged
    target in a panel cannot become its own authority. Fewer eligible tasks than
    requested is rejected rather than quietly reducing the denominator.
    """
    require(type(seed) is int and 0 <= seed < 2**63, "bounded panel seed required")
    require(type(dev_tasks) is int and 1 <= dev_tasks <= 64, "one to 64 dev tasks required")
    require(type(include_controls) is bool, "exact control switch required")
    gate_policy = dict(DEFAULT_GATE_POLICY) if gate_policy is None else deepcopy(gate_policy)
    require(type(gate_policy) is dict and set(gate_policy) == set(DEFAULT_GATE_POLICY) and
            gate_policy["require_all_authored_controls_exact"] is True and
            type(gate_policy["minimum_held_out_dev_exact"]) is int and
            1 <= gate_policy["minimum_held_out_dev_exact"] <= dev_tasks, "strict predeclared gate policy required")
    _validate_manifest(manifest, protected_ids)
    require(type(tasks) is dict and set(tasks) == set(manifest["tasks"]), "exact manifest source task set required")
    for key, value in tasks.items():
        require(digest({"train": _demos(value)}) == manifest["tasks"][key]["task_sha256"],
                "task source hash differs: " + key)
    eligible = [key for key, item in manifest["tasks"].items()
                if item["split"] == "dev" and len(item["demonstrations"]) >= 3]
    chosen = _rank_ids(eligible, seed)[:dev_tasks]
    require(len(chosen) == dev_tasks, "insufficient predeclared eligible training dev tasks")
    panel = {"format": FORMAT, "seed": seed, "requested_dev_tasks": dev_tasks,
             "include_controls": include_controls, "manifest_sha256": manifest["manifest_sha256"],
             "source_identity_sha256": digest(manifest["source_identity"]),
             "protected_ids": sorted(set(protected_ids) | set(manifest["protected_ids"])),
             "predeclared_dev_ids": chosen, "policy": deepcopy(POLICY), "gate_policy": gate_policy,
             "cases": [deepcopy(_dev_case(key, manifest["tasks"][key])) for key in chosen] +
                      (_authored_controls() if include_controls else []),
             "public_answers_used": False}
    panel["panel_sha256"] = digest(panel)
    return panel


def validate_panel(panel, *, manifest, protected_ids=()):
    require(type(panel) is dict and panel.get("format") == FORMAT, "effectiveness panel required")
    require(digest({k: v for k, v in panel.items() if k != "panel_sha256"}) == panel.get("panel_sha256"),
            "panel digest changed")
    require(manifest is not None, "exact source split manifest required")
    protected = set(protected_ids) | set(panel.get("protected_ids", []))
    _validate_manifest(manifest, protected)
    # Rebuild every prompt/target/lineage from its original authoritative source.
    source_tasks = {key: {"train": item["demonstrations"]} for key, item in manifest["tasks"].items()}
    expected = build_panel(source_tasks, manifest, seed=panel["seed"],
        dev_tasks=panel["requested_dev_tasks"], protected_ids=protected,
        include_controls=panel["include_controls"], gate_policy=panel["gate_policy"])
    require(panel == expected, "panel differs from exact source, order, policy, or authored controls")
    for case in panel["cases"]:
        validate_grid(case["target"])
        grid_messages(case["demos"], case["query_input"])
    return True


@contextmanager
def greedy_scope(model):
    """Do not leave inference sampling changed after success or any exception."""
    config = model.config
    require(type(config) is dict, "native sampling configuration required")
    keys = ("do_sample", "temperature", "top_p")
    previous = {key: config[key] for key in keys if key in config}
    config.update(do_sample=False, temperature=1.0, top_p=1.0)
    try:
        yield
    finally:
        for key in keys:
            config.pop(key, None)
        config.update(previous)


def _evidence_mode(model, requested):
    require(requested in ("native", "mock_fixture"), "unknown effectiveness evidence mode")
    if requested == "mock_fixture":
        return "mock_fixture_not_neural_proof"
    from tools.arc_learning_agent_20261011.native_model import NativeModel
    from tools.arc_learning_agent_20261011.metering import MeteredModel
    native = model.native if isinstance(model, MeteredModel) else model
    require(isinstance(native, NativeModel), "real NativeModel/MeteredModel required; fixtures must opt in")
    return "tiny_cpu_neural_not_pretrained" if native.tiny_cpu else "production_native_neural"


def _integer(value):
    return type(value) is int and value >= 0


def _receipt_ok(receipt, *, generation, cap=None):
    if type(receipt) is not dict or type(receipt.get("valid")) is not bool or \
            receipt.get("dispatched") is not True or receipt.get("model_forward_started") is not True:
        return False
    if any(not _integer(receipt.get(key)) for key in ("input_tokens", "output_tokens", "forward_calls", "forward_input_tokens")):
        return False
    if receipt["forward_calls"] <= 0 or receipt["input_tokens"] <= 0 or receipt["forward_input_tokens"] <= 0:
        return False
    if generation:
        return (type(receipt.get("text")) is str and 0 < receipt["output_tokens"] <= cap and
                receipt.get("finish_reason") in ("eos", "length") and
                receipt.get("sampling") == {"do_sample": False, "temperature": 1.0, "top_p": 1.0})
    return (receipt["valid"] and _integer(receipt.get("token_count")) and receipt["token_count"] > 0 and
            all(type(receipt.get(key)) in (int, float) and math.isfinite(receipt[key]) and receipt[key] >= 0
                for key in ("mean_nll", "nll_sum")) and
            math.isclose(receipt["mean_nll"] * receipt["token_count"], receipt["nll_sum"], rel_tol=1e-5, abs_tol=1e-7))


def _summary(rows, scope):
    selected = [row for row in rows if row["scope"] == scope]
    n = len(selected)
    counts = {key: sum(bool(row.get(key)) for row in selected)
              for key in ("exact", "dimension_correct", "valid_grid")}
    return {"denominator": n, **counts,
            **{key + "_rate": value / n if n else None for key, value in counts.items()}}


def evaluate_panel(model, panel, deadline, *, manifest=None, protected_ids=(),
                   max_generation_calls=None, max_scoring_calls=None, max_new_tokens=1024,
                   include_program=False, program_output_dir=None, evidence_mode="native"):
    """Measure actual generated behavior under equal explicit physical budgets.

    Calls are sequential; the model never sees the panel or target in generate.
    Every generation finishes before ANY target is teacher-forced, protecting
    later cases even against stateful score implementations. Invalid/missing
    receipts stay in the denominator and cannot qualify a checkpoint.
    """
    validate_panel(panel, manifest=manifest, protected_ids=protected_ids)
    evidence = _evidence_mode(model, evidence_mode)
    require(type(deadline) in (int, float) and math.isfinite(deadline), "finite absolute deadline required")
    require(type(include_program) is bool, "exact program switch required")
    require(type(max_new_tokens) is int and 1 <= max_new_tokens <= 2048, "bounded explicit output cap required")
    total = len(panel["cases"])
    generation_cap = total * (2 if include_program else 1) if max_generation_calls is None else max_generation_calls
    scoring_cap = total if max_scoring_calls is None else max_scoring_calls
    for value in (generation_cap, scoring_cap):
        require(type(value) is int and 0 <= value <= 256, "bounded exact physical-call caps required")
    require(not include_program or program_output_dir is not None, "bounded program artifact directory required")
    rows = [{"case_id": case["case_id"], "sample_id": case["case_id"], "scope": case["scope"], "exact": False,
             "valid_grid": False, "dimension_correct": False, "shape_correct": False, "generation": None, "score": None,
             "generation_receipt_complete": False, "scoring_receipt_complete": False,
             "program": None, "errors": []} for case in panel["cases"]]
    attempted = {"generation_calls": 0, "scoring_calls": 0}
    started = time.monotonic()
    ledger = getattr(model, "ledger", None)
    ledger_before = dict(ledger.used) if ledger is not None else None
    ledger_event_start = len(ledger.events) if ledger is not None else None
    with greedy_scope(model):
        # Phase 1: target-free generation. No score call can teach subsequent queries.
        for case, row in zip(panel["cases"], rows):
            for kind in (("grid", "program") if include_program else ("grid",)):
                if attempted["generation_calls"] >= generation_cap or time.monotonic() >= deadline:
                    row["errors"].append(kind + " generation not admitted: budget/deadline")
                    continue
                messages = grid_messages(case["demos"], case["query_input"]) if kind == "grid" else program_messages(
                    {"train": case["demos"], "test": [{"input": case["query_input"]}]})
                attempted["generation_calls"] += 1
                try:
                    receipt = model.generate(deepcopy(messages), kind=kind, seed=panel["seed"],
                                             max_new_tokens=max_new_tokens, deadline=deadline)
                    if kind == "program":
                        row["program"] = {"generation": receipt, "complete": _receipt_ok(receipt, generation=True, cap=max_new_tokens)}
                    else:
                        row["generation"] = receipt
                        row["generation_receipt_complete"] = _receipt_ok(receipt, generation=True, cap=max_new_tokens)
                except Exception as exc:
                    row["errors"].append(kind + ": " + type(exc).__name__ + ": " + str(exc)[:256])
        # Phase 2: evaluator-only train/dev targets, after all generation.
        for case, row in zip(panel["cases"], rows):
            receipt = row["generation"] or {}
            if row["generation_receipt_complete"] and receipt.get("valid") and receipt.get("finish_reason") == "eos":
                try:
                    predicted = decode_grid(receipt["text"])
                    row["valid_grid"] = True
                    row["dimension_correct"] = (len(predicted), len(predicted[0])) == (len(case["target"]), len(case["target"][0]))
                    row["shape_correct"] = row["dimension_correct"]
                    row["exact"] = predicted == case["target"]
                except ValueError as exc:
                    row["errors"].append("grid: " + str(exc))
            if attempted["scoring_calls"] < scoring_cap and time.monotonic() < deadline:
                attempted["scoring_calls"] += 1
                try:
                    row["score"] = model.score_completion(grid_messages(case["demos"], case["query_input"]),
                                                          encode_grid(case["target"]), deadline=deadline)
                    row["scoring_receipt_complete"] = _receipt_ok(row["score"], generation=False)
                except Exception as exc:
                    row["errors"].append("score: " + type(exc).__name__ + ": " + str(exc)[:256])
            else:
                row["errors"].append("scoring not admitted: budget/deadline")
            if include_program:
                program = row["program"]
                if program and program["complete"] and program["generation"].get("valid"):
                    from tools.arc_learning_agent_20261011.program_tools import verify_program
                    try:
                        proof = verify_program(program["generation"]["text"], case["demos"],
                            Path(program_output_dir), "effectiveness-" + digest([panel["panel_sha256"], case["case_id"]])[:20], deadline=deadline)
                        program.update(demo_fit=proof["all_demos_fit"], proof=proof,
                            complete=proof["receipt"].get("known") is True and
                                     proof["receipt"].get("owned_descendants_stopped") is True)
                    except Exception as exc:
                        program.update(complete=False, error=type(exc).__name__ + ": " + str(exc)[:256])
    complete = all(row["generation_receipt_complete"] and row["scoring_receipt_complete"] and
                   (not include_program or bool(row["program"] and row["program"]["complete"])) for row in rows)
    dev = _summary(rows, "training_dev_held_out_demo")
    controls = _summary(rows, "authored_learnability_only")
    # A zero-control panel is useful diagnostics but can never pass the gate.
    gate_pass = (complete and controls["denominator"] == len(_authored_controls()) and
                 controls["exact"] == controls["denominator"] and dev["exact"] >= panel["gate_policy"]["minimum_held_out_dev_exact"])
    scores = [row["score"] for row in rows if row["scoring_receipt_complete"]]
    receipts = [row[key] for row in rows for key in ("generation", "score") if type(row[key]) is dict]
    receipts += [row["program"]["generation"] for row in rows if row["program"] and type(row["program"].get("generation")) is dict]
    physical = {"generation_calls": sum(r.get("dispatched") is True for row in rows for r in
                    ([row["generation"] or {}] + ([row["program"]["generation"] or {}] if row["program"] else []))),
                "scoring_calls": sum((row["score"] or {}).get("dispatched") is True for row in rows),
                "forward_calls": sum(r.get("forward_calls", 0) for r in receipts if _integer(r.get("forward_calls"))),
                "input_tokens": sum(r.get("input_tokens", 0) for r in receipts if _integer(r.get("input_tokens"))),
                "output_tokens": sum(r.get("output_tokens", 0) for r in receipts if _integer(r.get("output_tokens"))),
                "usage_known": complete, "count_basis": "observed dispatch receipts; lower bounds if usage unknown"}
    if ledger is not None:
        physical["ledger_charged_delta"] = {key: ledger.used[key] - ledger_before[key] for key in ledger.used}
        physical["ledger_events"] = deepcopy(ledger.events[ledger_event_start:])
        physical["ledger_pending"] = deepcopy(ledger.pending)
        physical["usage_known"] = physical["usage_known"] and not bool(ledger.pending)
    report = {"format": "irisx/training-dev-effectiveness-result-v1", "panel_sha256": panel["panel_sha256"], "panel_id": panel["panel_sha256"],
              "gate_policy": deepcopy(panel["gate_policy"]), "policy": deepcopy(POLICY), "seed": panel["seed"], "evidence": evidence,
              "budgets": {"max_generation_calls": generation_cap, "max_scoring_calls": scoring_cap,
                          "max_new_tokens": max_new_tokens, "include_program": include_program},
              "attempted": attempted, "physical": physical, "complete": complete,
              "status": "pass" if gate_pass else "gate_blocked", "gate_pass": gate_pass,
              "eligible_for_public_run": gate_pass and evidence == "production_native_neural",
              "dev": dev, "learnability_controls": controls, "rows": rows,
              "denominator": total, "exact": sum(r["exact"] for r in rows),
              "shape_correct": sum(r["shape_correct"] for r in rows), "valid_grid": sum(r["valid_grid"] for r in rows),
              "mean_nll": sum(r["mean_nll"] for r in scores) / len(scores) if complete and scores else None,
              "public_answers_used": False, "public_accuracy_inferred": False,
              "program_demo_fit": sum(bool(row["program"] and row["program"].get("demo_fit")) for row in rows) if include_program else None,
              "elapsed_seconds": time.monotonic() - started}
    report["report_sha256"] = digest(report)
    return report


def compare_checkpoints(model, trainer, snapshots, panel, *, deadline, manifest,
                        base_name="base", required_names=("base", "early", "best", "final"), **evaluate_kwargs):
    """Evaluate every required checkpoint equally; preserve a real base fallback.

    Missing/incomplete comparisons block rather than selecting an easier subset.
    A restore exception also blocks, and the base is restored in that path.
    Snapshot handles are kept private; returned receipts contain no tensors.
    """
    require(type(snapshots) is dict and base_name in snapshots, "frozen base checkpoint required")
    names = list(required_names)
    require(names and len(names) == len(set(names)) and base_name in names, "unique required checkpoints including base required")
    reports, errors, selected = {}, {}, base_name
    try:
        for name in names:
            if name not in snapshots:
                errors[name] = "required checkpoint missing"
                continue
            if time.monotonic() >= deadline:
                errors[name] = "comparison deadline exhausted"
                continue
            try:
                trainer.restore(snapshots[name])
                kwargs = dict(evaluate_kwargs)
                if kwargs.get("include_program") and kwargs.get("program_output_dir") is not None:
                    kwargs["program_output_dir"] = Path(kwargs["program_output_dir"]) / ("checkpoint-" + digest(name)[:16])
                reports[name] = evaluate_panel(model, panel, deadline, manifest=manifest, **kwargs)
            except Exception as exc:
                errors[name] = type(exc).__name__ + ": " + str(exc)[:256]
        complete = not errors and len(reports) == len(names) and all(r["complete"] for r in reports.values())
        qualified = [name for name in names if complete and reports[name]["gate_pass"]]
        if qualified:
            def rank(name):
                report = reports[name]
                return (-report["dev"]["exact"], -report["learnability_controls"]["exact"],
                        -sum(row["dimension_correct"] for row in report["rows"]),
                        -sum(row["valid_grid"] for row in report["rows"]), report["mean_nll"], names.index(name))
            selected = min(qualified, key=rank)
    finally:
        reset = trainer.restore(snapshots[selected])
    gate_pass = complete and bool(qualified)
    return {"format": "irisx/effectiveness-checkpoint-comparison-v1", "selected": selected,
            "required_checkpoints": names, "reports": reports, "errors": errors,
            "comparison_complete": complete, "gate_pass": gate_pass,
            "status": "selected" if gate_pass else "gate_blocked_base_fallback",
            "eligible_for_public_run": gate_pass and reports[selected]["eligible_for_public_run"],
            "panel_sha256": panel["panel_sha256"], "reset": reset,
            "selection_metric": deepcopy(POLICY["selection_order"]), "public_answers_used": False}

"""Demo-only checkpoint/augmentation selection; no query target input exists.

This is a standalone next-cycle component. Backend receipts and the final source
bundle must bind it before production admission. It does not assert ARC efficacy.
"""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def grid(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 30:
        raise ValueError("invalid grid height")
    width = len(value[0]) if isinstance(value[0], list) else 0
    if not 1 <= width <= 30:
        raise ValueError("invalid grid width")
    if any(not isinstance(row, list) or len(row) != width or
           any(type(c) is not int or not 0 <= c <= 9 for c in row) for row in value):
        raise ValueError("invalid grid cells")
    return tuple(tuple(row) for row in value)


def _closed(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError("unexpected " + label + " fields")


def _identifier(value):
    if not isinstance(value, str) or not value or len(value) > 160:
        raise ValueError("invalid identifier")
    return value


def _sha(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("invalid receipt digest")
    return value


def select_answers(task, policy, candidates):
    """Rank complete LOO evidence, then choose up to two distinct valid grids.

    Each fold is prompted with OTHER demonstrations; TTT folds adapt only to those.
    Targets here are exclusively
    visible demonstration outputs. Runtime must substantiate the fold lineage and
    native receipt hashes; these structural checks alone cannot prove execution.
    No target length, test gold, exact-test score, or public outcome is accepted.
    """
    _closed(task, ("task_id", "demonstrations", "query_input"), "task")
    task_id = _identifier(task["task_id"])
    grid(task["query_input"])
    demos = task["demonstrations"]
    if not isinstance(demos, list) or not 2 <= len(demos) <= 10:
        raise ValueError("require two to ten demonstrations")
    targets = {}
    for row in demos:
        _closed(row, ("demo_id", "input", "output"), "demonstration")
        did = _identifier(row["demo_id"])
        if did in targets:
            raise ValueError("duplicate demonstration")
        grid(row["input"])
        targets[did] = grid(row["output"])

    _closed(policy, ("format", "candidate_order", "candidate_specs", "fold_conditioning_demo_ids", "transform_order", "maximum_answers", "reference_candidate_id", "reference_role", "frozen_global_checkpoint_sha256"), "policy")
    if policy["format"] != "irisx/demo-only-grid-portfolio-v1" or type(policy["maximum_answers"]) is not int or policy["maximum_answers"] != 2:
        raise ValueError("unsupported policy")
    order, transforms = policy["candidate_order"], policy["transform_order"]
    if policy["reference_role"] != "global_sft" or policy["reference_candidate_id"] != "ttt0":
        raise ValueError("selected global-SFT adaptation reference required")
    _sha(policy["frozen_global_checkpoint_sha256"])
    for sequence in (order, transforms):
        if not isinstance(sequence, list) or not 1 <= len(sequence) <= 32 or len(set(sequence)) != len(sequence):
            raise ValueError("invalid registered order")
        for value in sequence:
            _identifier(value)
    fold_context = policy["fold_conditioning_demo_ids"]
    if not isinstance(fold_context, dict) or set(fold_context) != set(targets):
        raise ValueError("registered fold context coverage differs")
    for did, context_ids in fold_context.items():
        if not isinstance(context_ids, list) or not context_ids or len(context_ids) != len(set(context_ids)) or not set(context_ids) <= set(targets) - {did}:
            raise ValueError("invalid or leaked registered fold context")
    specs = policy["candidate_specs"]
    if not isinstance(specs, dict) or set(specs) != set(order):
        raise ValueError("registered candidate specs differ")
    for index, cid in enumerate(order):
        spec = specs[cid]
        _closed(spec, ("role", "checkpoint_sha256", "adaptation_scope"), "candidate spec")
        _sha(spec["checkpoint_sha256"])
        if spec["role"] not in ("frozen_base", "global_sft", "task_ttt"):
            raise ValueError("invalid registered role")
        if index == 0:
            if cid != policy["reference_candidate_id"] or spec["role"] != "global_sft" or spec["checkpoint_sha256"] != policy["frozen_global_checkpoint_sha256"]:
                raise ValueError("reference must match frozen selected global-SFT artifact")
        elif spec["role"] != "task_ttt":
            raise ValueError("only adapted successors may follow the reference")
        expected = "task-demonstrations" if spec["role"] == "task_ttt" else "none"
        if spec["adaptation_scope"] != expected:
            raise ValueError("role and adaptation scope differ")
    if not isinstance(candidates, list) or len(candidates) != len(order):
        raise ValueError("missing registered candidate")
    by_id = {}
    for candidate in candidates:
        _closed(candidate, ("candidate_id", "task_id", "checkpoint_sha256", "adaptation_scope", "folds", "query_predictions"), "candidate")
        cid = _identifier(candidate["candidate_id"])
        if cid not in order or cid in by_id or candidate["task_id"] != task_id:
            raise ValueError("candidate identity differs")
        if candidate["adaptation_scope"] not in ("none", "task-demonstrations"):
            raise ValueError("unknown adaptation scope")
        _sha(candidate["checkpoint_sha256"])
        if candidate["checkpoint_sha256"] != specs[cid]["checkpoint_sha256"] or candidate["adaptation_scope"] != specs[cid]["adaptation_scope"]:
            raise ValueError("candidate differs from registered state")
        by_id[cid] = candidate

    rankings, all_answers = [], []
    for priority, cid in enumerate(order):
        candidate = by_id[cid]
        folds = candidate["folds"]
        if not isinstance(folds, list) or len(folds) != len(targets):
            raise ValueError("incomplete LOO coverage")
        seen, exact, shape, valid = set(), 0, 0, 0
        nll_sum, token_count = Fraction(0), 0
        for fold in folds:
            _closed(fold, ("heldout_demo_id", "conditioning_demo_ids", "adaptation_demo_ids", "prediction", "nll_sum", "token_count", "receipt_sha256"), "fold")
            did = fold["heldout_demo_id"]
            if did not in targets or did in seen:
                raise ValueError("fold identity differs")
            seen.add(did)
            trained = fold["conditioning_demo_ids"]
            if not isinstance(trained, list) or len(trained) != len(set(trained)) or trained != fold_context[did]:
                raise ValueError("held-out demo leaked or conditioning lineage incomplete")
            adapted = fold["adaptation_demo_ids"]
            expected_adapted = set(targets) - {did} if candidate["adaptation_scope"] == "task-demonstrations" else set()
            if not isinstance(adapted, list) or len(adapted) != len(set(adapted)) or set(adapted) != expected_adapted:
                raise ValueError("held-out demo leaked or adaptation lineage differs")
            _sha(fold["receipt_sha256"])
            if fold["prediction"] is not None:
                prediction = grid(fold["prediction"])
                valid += 1
                exact += prediction == targets[did]
                shape += (len(prediction), len(prediction[0])) == (len(targets[did]), len(targets[did][0]))
            loss, tokens = fold["nll_sum"], fold["token_count"]
            if type(loss) not in (int, float) or not math.isfinite(loss) or loss < 0 or type(tokens) is not int or tokens <= 0:
                raise ValueError("invalid demonstration NLL")
            nll_sum += Fraction(loss)
            token_count += tokens
        key = (-exact, -shape, -valid, nll_sum / token_count, priority)
        rankings.append((key, {"candidate_id": cid, "demo_exact_count": exact,
                              "demo_shape_count": shape, "demo_valid_count": valid,
                              "demo_denominator": len(targets),
                              "token_weighted_demo_nll": float(nll_sum / token_count)}))
        predictions = candidate["query_predictions"]
        if not isinstance(predictions, list) or len(predictions) != len(transforms):
            raise ValueError("incomplete query transform coverage")
        present, groups = set(), {}
        for prediction in predictions:
            _closed(prediction, ("transform_id", "grid", "inverse_applied", "receipt_sha256"), "query prediction")
            transform = prediction["transform_id"]
            if transform not in transforms or transform in present or prediction["inverse_applied"] is not True:
                raise ValueError("transform identity or inverse differs")
            present.add(transform)
            _sha(prediction["receipt_sha256"])
            if prediction["grid"] is None:
                continue
            g = grid(prediction["grid"])
            groups.setdefault(g, []).append(transform)
        for g, voters in groups.items():
            # Checkpoint evidence dominates; votes only rank transforms within it.
            answer_key = key + (-len(voters), min(transforms.index(v) for v in voters))
            all_answers.append((answer_key, g, cid, voters))

    chosen, seen_grids = [], set()
    for _, g, cid, voters in sorted(all_answers, key=lambda row: row[0]):
        if g in seen_grids:
            continue
        seen_grids.add(g)
        chosen.append({"grid": [list(row) for row in g], "candidate_id": cid,
                       "transform_votes": len(voters), "transform_ids": voters})
        if len(chosen) == 2:
            break
    receipt = {"format": "irisx/demo-only-grid-selection-receipt-v1", "task_id": task_id,
               "policy_sha256": digest(policy), "input_sha256": digest({"task": task, "candidates": candidates}),
               "rankings": [row for _, row in sorted(rankings, key=lambda item: item[0])],
               "answers": chosen, "abstention": not chosen, "query_targets_accessed": False,
               "candidate_order": list(order), "maximum_answers": 2,
               "reference_candidate_id": policy["reference_candidate_id"], "reference_role": "global_sft",
               "frozen_global_checkpoint_sha256": policy["frozen_global_checkpoint_sha256"],
               "qualification": "structural demo-only selection; native receipt authenticity requires runtime validation"}
    receipt["selection_sha256"] = digest(receipt)
    return receipt

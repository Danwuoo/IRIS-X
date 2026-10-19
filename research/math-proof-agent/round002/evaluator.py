"""Evaluator-only exact answers, called after candidate selection, never by solver.

Private answer keys are inputs at analysis time. No benchmark keys ship here.
Unsupported formats remain unknown rather than falling back to Python eval.
"""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import re
from lean_worker import answer_binding_digest, answer_candidate_digest, _validate_closed_exists_nat


def rational(text):
    if not isinstance(text, str) or len(text) > 128:
        raise ValueError("unsupported exact answer")
    text = text.strip()
    if not re.fullmatch(r"[+-]?[0-9]{1,60}(?:/[0-9]{1,60})?", text):
        raise ValueError("unsupported exact answer")
    return Fraction(text)


def supported_answer_problem(problem):
    spec = problem.get("answer_binding", {})
    try:
        answer_binding_digest(spec)
        _validate_closed_exists_nat(problem["statement"]["declaration"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
    return (problem.get("answer_mode") == "find_answer" and isinstance(spec, dict)
            and set(spec) == {"kind", "statement_sha256", "review_ref", "answer_mode"}
            and spec.get("kind") == "closed_exists_nat_v1"
            and spec.get("answer_mode") == "find_answer"
            and spec.get("statement_sha256") == problem.get("statement_sha256")
            and isinstance(spec.get("review_ref"), str) and bool(spec["review_ref"]))


def bound_answer_matches(event, problem):
    """Recheck the selected candidate against a trusted worker receipt, never gold.

    Receipt authenticity comes from the committed worker and verified run
    artifact; these hashes detect mixing, not signatures for arbitrary input.
    """
    if not supported_answer_problem(problem) or event.get("status") != "accepted":
        return False
    try:
        result, candidate = event["tool"], event["candidate"]
        binding = result["answer_binding"]
        candidate_sha = answer_candidate_digest(candidate["answer"], candidate["proof_body"])
        return (result.get("proof_status") == "kernel_verified" and result.get("trust_policy_passed") is True
                and result.get("statement_sha256") == problem["statement_sha256"]
                and result.get("candidate_sha256") == candidate_sha
                and binding.get("kind") == "closed_exists_nat_v1" and binding.get("status") == "kernel_verified"
                and binding.get("statement_sha256") == problem["statement_sha256"]
                and binding.get("spec_sha256") == answer_binding_digest(problem["answer_binding"])
                and binding.get("candidate_sha256") == candidate_sha
                and binding.get("normalized_answer_sha256") == hashlib.sha256(candidate["answer"].encode()).hexdigest())
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def evaluate_selected(records, private_key=None, *, panel=None):
    """Kernel-bound witnesses need no gold. Optional keys are consistency checks.

    A separate key comparison alone never qualifies a joint result. The frozen
    original proposition must express the complete source problem; that fidelity
    gate cannot be established by this evaluator or by authored controls.
    """
    private_key = private_key or {}
    problems = {problem["id"]: problem for problem in (panel or [])}
    if panel is not None and len(problems) != len(panel):
        raise ValueError("duplicate evaluator panel problem")
    evaluated = copy.deepcopy(records)
    for record in evaluated:
        mode = record["answer_mode"]
        if mode == "proof_only":
            record["answer_status"] = "not_applicable"
            record["joint_status"] = "not_applicable"
            continue
        record["answer_status"] = "unknown"
        record["joint_status"] = "unqualified" if mode == "find_answer" else "not_applicable"
        if mode != "find_answer":
            continue
        # The controller selects first qualifying proof, not an answer-key oracle.
        selected = next((e for e in record.get("events", []) if e["status"] == "accepted"), None)
        if selected is None:
            continue
        problem = problems.get(record["problem_id"], {})
        bound = (record.get("status") == "proof_accepted" and bound_answer_matches(selected, problem))
        if bound:
            record.update(answer_status="correct", joint_status="kernel_verified", answer_evidence="kernel_witness")
        if record["problem_id"] not in private_key:
            continue
        try:
            answer = rational(selected["candidate"]["answer"])
            expected = rational(private_key[record["problem_id"]])
            if bound and answer != expected:
                record.update(answer_status="inconsistent_evaluator_key", joint_status="blocked_key_disagreement")
            elif not bound:
                record["answer_status"] = "correct" if answer == expected else "incorrect"
        except (ValueError, KeyError, ZeroDivisionError):
            pass
    return evaluated

"""Evaluator-only exact answers, called after candidate selection, never by solver.

Private answer keys are inputs at analysis time. No benchmark keys ship here.
Unsupported formats remain unknown rather than falling back to Python eval.
"""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import json
import re
from lean_worker import (answer_binding_digest, answer_candidate_digest,
                         normalized_answer_sha256, statement_digest, _validate_closed_exists_nat)


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


def _model_text_matches(candidate, model_text):
    """Mirror the candidate JSON envelope without normalizing proof-body bytes."""
    if (not isinstance(candidate, dict) or set(candidate) != {"answer", "proof_body"}
            or not isinstance(candidate["proof_body"], str) or not candidate["proof_body"].strip()
            or candidate["answer"] is not None and not isinstance(candidate["answer"], str)
            or not isinstance(model_text, str) or len(model_text.encode("utf-8")) > 65536):
        return False
    if model_text.startswith("```json\n") and model_text.rstrip().endswith("```"):
        model_text = model_text[8:].rstrip()[:-3]
    return json.loads(model_text) == candidate


def verified_receipt_matches(result, problem, candidate, *, model_text):
    """Bind a coherent successful receipt to the exact selected candidate.

    Receipt authenticity comes from the committed worker and verified run
    artifact; hashes detect mixing, not signatures for arbitrary input. Both
    controller selection and later analysis must call this validator. Model text
    is re-parsed to prevent an edited candidate object from obscuring what was
    generated. JSON envelope whitespace may differ, but proof text is never
    stripped, reformatted, or replaced with the worker's parsed tactic body.
    """
    try:
        if (not isinstance(result, dict) or not isinstance(problem, dict)
                or result.get("status") != "accepted" or result.get("accepted") is not True
                or result.get("proof_status") != "kernel_verified"
                or result.get("trust_policy_passed") is not True
                or not _model_text_matches(candidate, model_text)):
            return False
        digest = statement_digest(problem["statement"])
        if (problem["statement"].get("sha256") != digest or problem.get("statement_sha256") != digest
                or result.get("statement_sha256") != digest):
            return False
        mode = problem.get("answer_mode")
        if mode in {"proof_only", "answer_given"}:
            if mode == "proof_only" and candidate["answer"] is not None:
                return False
            return result.get("candidate_sha256") == hashlib.sha256(
                candidate["proof_body"].encode("utf-8")).hexdigest()
        if mode != "find_answer" or not supported_answer_problem(problem):
            return False
        binding = result["answer_binding"]
        candidate_sha = answer_candidate_digest(candidate["answer"], candidate["proof_body"])
        return (result.get("candidate_sha256") == candidate_sha
                and binding.get("kind") == "closed_exists_nat_v1" and binding.get("status") == "kernel_verified"
                and binding.get("statement_sha256") == problem["statement_sha256"]
                and binding.get("spec_sha256") == answer_binding_digest(problem["answer_binding"])
                and binding.get("candidate_sha256") == candidate_sha
                and binding.get("normalized_answer_sha256") == normalized_answer_sha256(candidate["answer"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def verified_event_matches(event, problem):
    """Require accepted event state as well as the mode-specific worker receipt."""
    try:
        return (event.get("status") == "accepted"
                and verified_receipt_matches(event["tool"], problem, event["candidate"],
                                             model_text=event["model_text"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def bound_answer_matches(event, problem):
    return problem.get("answer_mode") == "find_answer" and verified_event_matches(event, problem)


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

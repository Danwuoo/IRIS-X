"""Evaluator-only exact answers, called after candidate selection, never by solver.

Private answer keys are inputs at analysis time. No benchmark keys ship here.
Unsupported formats remain unknown rather than falling back to Python eval.
"""
from __future__ import annotations
import copy
from fractions import Fraction
import re


def rational(text):
    if not isinstance(text, str) or len(text) > 128:
        raise ValueError("unsupported exact answer")
    text = text.strip()
    if not re.fullmatch(r"[+-]?[0-9]{1,60}(?:/[0-9]{1,60})?", text):
        raise ValueError("unsupported exact answer")
    return Fraction(text)


def evaluate_selected(records, private_key):
    """Accept only find-answer keys; supplied-answer tasks never count discovery."""
    evaluated = copy.deepcopy(records)
    for record in evaluated:
        mode = record["answer_mode"]
        if mode == "proof_only":
            record["answer_status"] = "not_applicable"
            record["joint_status"] = "not_applicable"
            continue
        record["answer_status"] = "unknown"
        # A correct separate string and a proof of a fixed existential/other
        # theorem do not establish that the proof certifies this answer.
        # No reviewed answer-binding implementation is qualified in this round.
        record["joint_status"] = "unqualified" if mode == "find_answer" else "not_applicable"
        if mode != "find_answer":
            continue
        # The controller selects first qualifying proof, not an answer-key oracle.
        selected = next((e for e in record.get("events", []) if e["status"] == "accepted"), None)
        if selected is None or record["problem_id"] not in private_key:
            continue
        try:
            answer = rational(selected["candidate"]["answer"])
            expected = rational(private_key[record["problem_id"]])
            record["answer_status"] = "correct" if answer == expected else "incorrect"
        except (ValueError, KeyError, ZeroDivisionError):
            pass
    return evaluated

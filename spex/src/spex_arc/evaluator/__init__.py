"""Local-reference ARC-AGI-1 evaluator and submission contract."""

from .arc_a1 import (
    EVALUATOR_VERSION,
    EvaluationReport,
    EvaluatorIdentity,
    LocalReferenceEvaluator,
    Submission,
    TaskScore,
    load_evaluator_identity,
    parse_submission_json,
    read_submission,
    serialize_submission,
    write_submission,
)

__all__ = [
    "EVALUATOR_VERSION",
    "EvaluationReport",
    "EvaluatorIdentity",
    "LocalReferenceEvaluator",
    "Submission",
    "TaskScore",
    "load_evaluator_identity",
    "parse_submission_json",
    "read_submission",
    "serialize_submission",
    "write_submission",
]

"""Domain models for ARC tasks and solver-safe task views."""

from .arc_a1 import (
    CandidateSet,
    Grid,
    Prediction,
    Task,
    TaskView,
    TestCase,
    TrainPair,
    ValidationFailure,
    ValidationResult,
    parse_candidate_set_json,
    parse_task_json,
    validate_candidate_set,
)

__all__ = [
    "CandidateSet",
    "Grid",
    "Prediction",
    "Task",
    "TaskView",
    "TestCase",
    "TrainPair",
    "ValidationFailure",
    "ValidationResult",
    "parse_candidate_set_json",
    "parse_task_json",
    "validate_candidate_set",
]

"""Offline grid-corpus prerequisites, not a trainer or a corpus approval grant."""

from .admission import AdmissionError, admit, canonical_task, validate_task

__all__ = ["AdmissionError", "admit", "canonical_task", "validate_task"]

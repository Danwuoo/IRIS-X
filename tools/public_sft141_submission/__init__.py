"""Independent, gold-free ARC submission serialization; no solver or evaluator."""

from .contract import build_submission, validate_challenge, validate_submission

__all__ = ["build_submission", "validate_challenge", "validate_submission"]

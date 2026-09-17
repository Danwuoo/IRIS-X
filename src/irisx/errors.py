"""IRIS-X error hierarchy."""


class IrisxError(Exception):
    """Base class for expected user-facing IRIS-X failures."""


class ValidationError(IrisxError):
    """A contract, binding, or package failed closed validation."""

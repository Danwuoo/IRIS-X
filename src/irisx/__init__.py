"""IRIS-X P1 product contracts and deterministic reference flow."""

from .contracts import (
    CandidateConfiguration,
    DomainPackageManifest,
    DomainSpecification,
    EngineeringTrial,
    EvaluationResult,
    RequirementSet,
    SelectionDecision,
    WorkloadDefinition,
)
from .errors import IrisxError, ValidationError

__all__ = [
    "CandidateConfiguration",
    "DomainPackageManifest",
    "DomainSpecification",
    "EngineeringTrial",
    "EvaluationResult",
    "IrisxError",
    "RequirementSet",
    "SelectionDecision",
    "ValidationError",
    "WorkloadDefinition",
]

__version__ = "0.1.0"

"""IRIS-X product contracts, qualification flow, and P2 admission checks."""

from .admission import admission_summary, validate_admission_file
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
    "admission_summary",
    "validate_admission_file",
]

__version__ = "0.2.0"

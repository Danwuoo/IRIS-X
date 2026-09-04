"""Evidence-backed provisional execution boundaries for IRIS-X."""

from .execution import BindingError, bind_execution, evidence_binding, execute
from .interfaces import ExecutorAdapter, IndependentVerifier, PolicyGate
from .records import (
    UNKNOWN,
    EvidenceRef,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRequest,
    Observation,
    PolicyDecision,
    ProgramArtifact,
    RawResult,
    ResourceLedger,
    TaskContract,
    TerminalRecord,
    VerificationResult,
)

__all__ = [
    "UNKNOWN",
    "BindingError",
    "EvidenceRef",
    "ExecutionContext",
    "ExecutionIdentity",
    "ExecutionRequest",
    "ExecutorAdapter",
    "IndependentVerifier",
    "Observation",
    "PolicyDecision",
    "PolicyGate",
    "ProgramArtifact",
    "RawResult",
    "ResourceLedger",
    "TaskContract",
    "TerminalRecord",
    "VerificationResult",
    "bind_execution",
    "evidence_binding",
    "execute",
]

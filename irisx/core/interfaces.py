"""Only the replaceable interfaces justified for the provisional core."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Protocol, Sequence, runtime_checkable

from .records import (
    EvidenceRef,
    ExecutionContext,
    ExecutionRequest,
    PolicyDecision,
    RawResult,
    VerificationResult,
)


@runtime_checkable
class PolicyGate(Protocol):
    def evaluate(self, context: ExecutionContext, request: ExecutionRequest) -> PolicyDecision: ...


@runtime_checkable
class ExecutorAdapter(Protocol):
    def execute(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        state: MutableMapping[str, Any],
        expected_evidence: Sequence[EvidenceRef],
    ) -> RawResult: ...


@runtime_checkable
class IndependentVerifier(Protocol):
    def verify(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        raw_result: RawResult,
        before_state: Mapping[str, Any],
        after_state: Mapping[str, Any],
        expected_evidence: Sequence[EvidenceRef],
    ) -> VerificationResult: ...


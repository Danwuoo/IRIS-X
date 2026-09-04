"""Only the replaceable interfaces justified for the provisional core."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Protocol, runtime_checkable

from .records import (
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
    ) -> VerificationResult: ...

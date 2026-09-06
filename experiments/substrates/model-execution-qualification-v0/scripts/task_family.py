#!/usr/bin/env python3
"""Frozen Batch 6 task definitions and deterministic task-local verifiers."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
TASK_FAMILY_ROOT = SUBSTRATE / "task-family"
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from irisx.core.execution import bind_execution, evidence_binding, execute, state_sha256  # noqa: E402
from irisx.core.records import (  # noqa: E402
    AdapterResourceReport,
    EvidenceRef,
    EvidenceRequirement,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRequest,
    ProgramArtifact,
    RawResult,
    TaskContract,
    VerificationResult,
)


PROFILE_PATH = SUBSTRATE / "admission" / "codex-cli-0.147.0-run-03-profile.json"
MODEL_CATALOG_PATH = SUBSTRATE / "definition" / "tool-free-luna-model-catalog.json"
BASELINE_PATH = (
    REPOSITORY_ROOT / "experiments" / "configurations" / "provider-model-baseline-v0.json"
)
PROFILE_ID = "codex-cli-0.147.0-run-03-admission-v0"
PROFILE_SHA256 = "ab21119f80141456e7327e276fa3e470abf288cf6a3535ac5fceeace68302033"
BASELINE_ID = "irisx-openai-codex-dual-model-v0"
BASELINE_SHA256 = "a1a85c7464fbc090c2bf2e1682bee9a22957146e50abf11ab5c41f1544046d74"
CONFIGURATION_ID = "openai-codex-luna-medium-readonly-zero-retry-run-03-v0"

TASK_SPECS: dict[str, dict[str, str]] = {
    "A": {
        "task_id": "task-family-filter-threshold-v0",
        "contract_id": "contract-task-family-filter-threshold-v0",
        "program_id": "program-task-family-filter-threshold-v0",
        "schema_id": "schema-task-family-filter-threshold-v0",
        "verifier_id": "filter-selection-verifier-v0",
        "oracle_id": "oracle-filter-score-gte-threshold-input-order-v0",
        "operation": "filter_records",
        "semantic_family": "filter-set-selection",
        "run_id": "task-family-20260906-a-filter",
        "contract_path": "task-family/definitions/task-a-filter.contract.json",
        "program_path": "task-family/programs/task-a-filter.txt",
        "input_path": "task-family/inputs/task-a-filter.json",
        "schema_path": "task-family/schemas/task-a-filter.schema.json",
        "fixture_path": "task-family/fixtures/task-a-negative-outputs.json",
    },
    "B": {
        "task_id": "task-family-aggregation-region-v0",
        "contract_id": "contract-task-family-aggregation-region-v0",
        "program_id": "program-task-family-aggregation-region-v0",
        "schema_id": "schema-task-family-aggregation-region-v0",
        "verifier_id": "aggregation-total-verifier-v0",
        "oracle_id": "oracle-sum-amount-for-target-region-v0",
        "operation": "aggregate_records",
        "semantic_family": "grouped-numeric-aggregation",
        "run_id": "task-family-20260906-b-aggregation",
        "contract_path": "task-family/definitions/task-b-aggregation.contract.json",
        "program_path": "task-family/programs/task-b-aggregation.txt",
        "input_path": "task-family/inputs/task-b-aggregation.json",
        "schema_path": "task-family/schemas/task-b-aggregation.schema.json",
        "fixture_path": "task-family/fixtures/task-b-negative-outputs.json",
    },
    "C": {
        "task_id": "task-family-ranking-top-n-v0",
        "contract_id": "contract-task-family-ranking-top-n-v0",
        "program_id": "program-task-family-ranking-top-n-v0",
        "schema_id": "schema-task-family-ranking-top-n-v0",
        "verifier_id": "ordered-ranking-verifier-v0",
        "oracle_id": "oracle-score-desc-id-ascending-top-n-v0",
        "operation": "rank_records",
        "semantic_family": "ordered-ranking-transformation",
        "run_id": "task-family-20260906-c-ranking",
        "contract_path": "task-family/definitions/task-c-ranking.contract.json",
        "program_path": "task-family/programs/task-c-ranking.txt",
        "input_path": "task-family/inputs/task-c-ranking.json",
        "schema_path": "task-family/schemas/task-c-ranking.schema.json",
        "fixture_path": "task-family/fixtures/task-c-negative-outputs.json",
    },
}


class TaskFamilyError(RuntimeError):
    """A frozen task-family artifact or binding failed closed."""


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise TaskFamilyError(f"JSON top level must be an object: {path}")
    return value


def _require_equal(observed: Any, expected: Any, reason: str) -> None:
    if observed != expected:
        raise TaskFamilyError(reason)


def derive_filter_oracle(task_input: Mapping[str, Any]) -> dict[str, Any]:
    records = task_input.get("records")
    threshold = task_input.get("threshold")
    if not isinstance(records, list) or type(threshold) is not int:
        raise TaskFamilyError("task A input shape invalid")
    selected: list[str] = []
    for row in records:
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "score"}
            or not isinstance(row["id"], str)
            or type(row["score"]) is not int
        ):
            raise TaskFamilyError("task A record shape invalid")
        if row["score"] >= threshold:
            selected.append(row["id"])
    return {"selected_ids": selected}


def derive_aggregation_oracle(task_input: Mapping[str, Any]) -> dict[str, Any]:
    records = task_input.get("records")
    target = task_input.get("target_region")
    if not isinstance(records, list) or not isinstance(target, str):
        raise TaskFamilyError("task B input shape invalid")
    total = 0
    for row in records:
        if (
            not isinstance(row, dict)
            or set(row) != {"amount", "region"}
            or type(row["amount"]) is not int
            or not isinstance(row["region"], str)
        ):
            raise TaskFamilyError("task B record shape invalid")
        if row["region"] == target:
            total += row["amount"]
    return {"total": total}


def derive_ranking_oracle(task_input: Mapping[str, Any]) -> dict[str, Any]:
    records = task_input.get("records")
    limit = task_input.get("limit")
    tie_break = task_input.get("tie_break")
    if (
        not isinstance(records, list)
        or type(limit) is not int
        or limit < 0
        or tie_break != "id_ascending"
    ):
        raise TaskFamilyError("task C input shape invalid")
    normalized: list[dict[str, Any]] = []
    for row in records:
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "score"}
            or not isinstance(row["id"], str)
            or type(row["score"]) is not int
        ):
            raise TaskFamilyError("task C record shape invalid")
        normalized.append(dict(row))
    ordered = sorted(normalized, key=lambda row: (-row["score"], row["id"]))[:limit]
    return {
        "ranked": [
            {"id": row["id"], "rank": index}
            for index, row in enumerate(ordered, start=1)
        ]
    }


ORACLE_DERIVERS = {
    "A": derive_filter_oracle,
    "B": derive_aggregation_oracle,
    "C": derive_ranking_oracle,
}


@dataclass(frozen=True)
class FrozenTaskDefinition:
    task_key: str
    contract_path: Path
    contract_bytes: bytes
    contract: Mapping[str, Any]
    program_path: Path
    program_bytes: bytes
    input_path: Path
    task_input: Mapping[str, Any]
    schema_path: Path
    output_schema: Mapping[str, Any]
    oracle: Mapping[str, Any]

    @property
    def spec(self) -> Mapping[str, str]:
        return TASK_SPECS[self.task_key]

    @property
    def contract_sha256(self) -> str:
        return sha256_bytes(self.contract_bytes)

    @property
    def program_sha256(self) -> str:
        return sha256_bytes(self.program_bytes)

    @property
    def input_sha256(self) -> str:
        return sha256_bytes(self.input_path.read_bytes())

    @property
    def schema_sha256(self) -> str:
        return sha256_bytes(self.schema_path.read_bytes())

    @property
    def prompt(self) -> str:
        return (
            self.program_bytes.decode("utf-8")
            + "\nFrozen task input (canonical JSON):\n"
            + canonical_json_bytes(self.task_input).decode("utf-8")
            + "\n"
        )

    @property
    def prompt_sha256(self) -> str:
        return sha256_bytes(self.prompt.encode("utf-8"))

    @property
    def run_id(self) -> str:
        return self.spec["run_id"]

    @property
    def run_dir(self) -> Path:
        return SUBSTRATE / self.contract["run_artifacts"]["run_directory"]

    def core_contract(self) -> TaskContract:
        return TaskContract(
            task_id=str(self.contract["task_id"]),
            contract_id=str(self.contract["contract_id"]),
            expected_program_id=str(self.contract["program"]["program_id"]),
            expected_program_sha256=str(self.contract["program"]["sha256"]),
            execution_id=str(self.contract["execution"]["execution_id"]),
            configuration_id=str(self.contract["execution"]["configuration_id"]),
            content=self.contract_bytes,
            evidence_requirements=tuple(
                EvidenceRequirement(**row) for row in self.contract["evidence_requirements"]
            ),
        )

    def program_artifact(self) -> ProgramArtifact:
        return ProgramArtifact(
            str(self.contract["program"]["program_id"]),
            str(self.contract["program"]["path"]),
            self.program_bytes,
        )

    def execution_identity(self) -> ExecutionIdentity:
        return ExecutionIdentity(
            str(self.contract["task_id"]),
            str(self.contract["contract_id"]),
            str(self.contract["program"]["program_id"]),
            str(self.contract["execution"]["execution_id"]),
            str(self.contract["execution"]["configuration_id"]),
        )

    def execution_request(self) -> ExecutionRequest:
        return ExecutionRequest(
            **self.contract["request"],
            requires_mutation_prevention=False,
        )

    def initial_state(self) -> dict[str, Any]:
        return {
            "task_id": self.spec["task_id"],
            "task_input": copy.deepcopy(dict(self.task_input)),
        }


def load_task(task_key: str) -> FrozenTaskDefinition:
    key = task_key.upper()
    if key not in TASK_SPECS:
        raise TaskFamilyError(f"unknown task key: {task_key}")
    spec = TASK_SPECS[key]
    contract_path = SUBSTRATE / spec["contract_path"]
    program_path = SUBSTRATE / spec["program_path"]
    input_path = SUBSTRATE / spec["input_path"]
    schema_path = SUBSTRATE / spec["schema_path"]
    contract_bytes = contract_path.read_bytes()
    contract = load_object(contract_path)
    program_bytes = program_path.read_bytes()
    task_input = load_object(input_path)
    output_schema = load_object(schema_path)

    exact_contract_fields = {
        "task_id": spec["task_id"],
        "contract_id": spec["contract_id"],
        "semantic_family": spec["semantic_family"],
        "verifier_id": spec["verifier_id"],
    }
    for field, expected in exact_contract_fields.items():
        _require_equal(contract.get(field), expected, f"{key} contract {field} drifted")
    _require_equal(
        contract.get("program", {}).get("program_id"),
        spec["program_id"],
        f"{key} program identity drifted",
    )
    _require_equal(
        contract.get("program", {}).get("path"), spec["program_path"], f"{key} program path drifted"
    )
    _require_equal(
        contract.get("task_input", {}).get("path"), spec["input_path"], f"{key} input path drifted"
    )
    _require_equal(
        contract.get("output_schema", {}).get("schema_id"),
        spec["schema_id"],
        f"{key} schema identity drifted",
    )
    _require_equal(
        contract.get("output_schema", {}).get("path"),
        spec["schema_path"],
        f"{key} schema path drifted",
    )
    _require_equal(
        contract.get("execution", {}).get("execution_id"), spec["run_id"], f"{key} execution ID drifted"
    )
    _require_equal(
        contract.get("execution", {}).get("configuration_id"),
        CONFIGURATION_ID,
        f"{key} configuration identity drifted",
    )
    _require_equal(
        contract.get("request", {}).get("operation"), spec["operation"], f"{key} operation drifted"
    )
    _require_equal(
        contract.get("run_artifacts", {}).get("run_id"), spec["run_id"], f"{key} run ID drifted"
    )
    _require_equal(
        contract.get("run_artifacts", {}).get("run_directory"),
        f"task-family/runs/{spec['run_id']}",
        f"{key} run directory drifted",
    )

    artifact_rows = (
        (program_path, contract["program"]["sha256"], "program"),
        (input_path, contract["task_input"]["sha256"], "task input"),
        (schema_path, contract["output_schema"]["sha256"], "output schema"),
        (PROFILE_PATH, PROFILE_SHA256, "admission profile"),
        (BASELINE_PATH, BASELINE_SHA256, "provider baseline"),
    )
    for path, expected, label in artifact_rows:
        _require_equal(sha256_bytes(path.read_bytes()), expected, f"{key} {label} hash drifted")

    _require_equal(contract["program"]["sha256"], sha256_bytes(program_bytes), f"{key} program hash drifted")
    admission = contract.get("admission_requirement", {})
    _require_equal(admission.get("profile_id"), PROFILE_ID, f"{key} admission profile ID drifted")
    _require_equal(admission.get("profile_sha256"), PROFILE_SHA256, f"{key} admission profile hash drifted")
    _require_equal(admission.get("required_status"), "admitted", f"{key} admission status drifted")
    provider = contract.get("provider_configuration", {})
    _require_equal(
        provider,
        {
            "api_key_fallback": "prohibited",
            "authentication_mode": "chatgpt",
            "billing_mode": "chatgpt-subscription",
            "codex_model_provider_config_id": "irisx_openai_no_retry",
            "execution_surface": "codex-cli",
            "model_id": "gpt-5.6-luna",
            "model_role": "cheaper",
            "provider_baseline_id": BASELINE_ID,
            "provider_baseline_sha256": BASELINE_SHA256,
            "provider_cost_usd": "Unknown",
            "provider_id": "openai",
            "reasoning_effort": "medium",
        },
        f"{key} provider configuration drifted",
    )
    _require_equal(
        contract.get("call_ceiling"),
        {
            "escalations": 0,
            "fallbacks": 0,
            "http_request_retries": 0,
            "manual_retries": 0,
            "provider_invocations": 1,
            "recovery_actions": 0,
            "routes": 0,
            "stream_reconnect_retries": 0,
            "tool_calls": 0,
        },
        f"{key} call ceiling drifted",
    )
    expected_oracle = ORACLE_DERIVERS[key](task_input)
    _require_equal(
        contract.get("deterministic_oracle", {}).get("oracle_id"),
        spec["oracle_id"],
        f"{key} oracle identity drifted",
    )
    _require_equal(
        contract.get("deterministic_oracle", {}).get("expected_output"),
        expected_oracle,
        f"{key} oracle does not derive from frozen input",
    )
    definition = FrozenTaskDefinition(
        key,
        contract_path,
        contract_bytes,
        contract,
        program_path,
        program_bytes,
        input_path,
        task_input,
        schema_path,
        output_schema,
        expected_oracle,
    )
    definition.core_contract()
    bind_execution(
        definition.core_contract(),
        definition.program_artifact(),
        definition.execution_identity(),
    )
    return definition


def _parse_output(raw_result: RawResult, reasons: list[str]) -> Any:
    if not isinstance(raw_result.reported_value, str) or not raw_result.reported_value.strip():
        reasons.append("provider_output_not_captured")
        return None
    try:
        return json.loads(raw_result.reported_value)
    except json.JSONDecodeError:
        reasons.append("provider_output_malformed_json")
        return None


def _verification(
    *,
    context: ExecutionContext,
    raw_result: RawResult,
    before_state: Mapping[str, Any],
    after_state: Mapping[str, Any],
    reasons: Sequence[str],
    success_reason: str,
) -> VerificationResult:
    all_reasons = list(reasons)
    if before_state != after_state:
        all_reasons.append("read_only_state_changed")
    evidence_status, evidence_reasons = evidence_binding(
        context.evidence_requirements, raw_result.evidence
    )
    return VerificationResult(
        semantic_valid=not all_reasons,
        semantic_reasons=tuple(all_reasons or (success_reason,)),
        evidence_status=evidence_status,
        evidence_reasons=evidence_reasons,
        observed_post_state_sha256=state_sha256(after_state),
    )


class FilterSelectionVerifier:
    verifier_id = "filter-selection-verifier-v0"

    def __init__(self, expected: Mapping[str, Any]) -> None:
        self.expected = copy.deepcopy(dict(expected))

    def verify(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        raw_result: RawResult,
        before_state: Mapping[str, Any],
        after_state: Mapping[str, Any],
    ) -> VerificationResult:
        del request
        reasons: list[str] = []
        parsed = _parse_output(raw_result, reasons)
        if parsed is not None:
            if not isinstance(parsed, dict) or set(parsed) != {"selected_ids"}:
                reasons.append("filter_output_schema_mismatch")
            elif not isinstance(parsed["selected_ids"], list) or not all(
                isinstance(item, str) for item in parsed["selected_ids"]
            ):
                reasons.append("selected_ids_type_mismatch")
            elif parsed["selected_ids"] != self.expected["selected_ids"]:
                if sorted(parsed["selected_ids"]) == sorted(self.expected["selected_ids"]):
                    reasons.append("selected_ids_order_mismatch")
                else:
                    reasons.append("selected_ids_oracle_mismatch")
        return _verification(
            context=context,
            raw_result=raw_result,
            before_state=before_state,
            after_state=after_state,
            reasons=reasons,
            success_reason="deterministic_filter_selection_match",
        )


class AggregationVerifier:
    verifier_id = "aggregation-total-verifier-v0"

    def __init__(self, expected: Mapping[str, Any]) -> None:
        self.expected = copy.deepcopy(dict(expected))

    def verify(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        raw_result: RawResult,
        before_state: Mapping[str, Any],
        after_state: Mapping[str, Any],
    ) -> VerificationResult:
        del request
        reasons: list[str] = []
        parsed = _parse_output(raw_result, reasons)
        if parsed is not None:
            if not isinstance(parsed, dict) or set(parsed) != {"total"}:
                reasons.append("aggregation_output_schema_mismatch")
            elif type(parsed["total"]) is not int:
                reasons.append("aggregation_total_type_mismatch")
            elif parsed["total"] != self.expected["total"]:
                reasons.append("aggregation_total_oracle_mismatch")
        return _verification(
            context=context,
            raw_result=raw_result,
            before_state=before_state,
            after_state=after_state,
            reasons=reasons,
            success_reason="deterministic_aggregation_match",
        )


class OrderedRankingVerifier:
    verifier_id = "ordered-ranking-verifier-v0"

    def __init__(self, expected: Mapping[str, Any]) -> None:
        self.expected = copy.deepcopy(dict(expected))

    def verify(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        raw_result: RawResult,
        before_state: Mapping[str, Any],
        after_state: Mapping[str, Any],
    ) -> VerificationResult:
        del request
        reasons: list[str] = []
        parsed = _parse_output(raw_result, reasons)
        if parsed is not None:
            if not isinstance(parsed, dict) or set(parsed) != {"ranked"}:
                reasons.append("ranking_output_schema_mismatch")
            elif not isinstance(parsed["ranked"], list) or not all(
                isinstance(row, dict)
                and set(row) == {"id", "rank"}
                and isinstance(row["id"], str)
                and type(row["rank"]) is int
                for row in parsed["ranked"]
            ):
                reasons.append("ranking_item_schema_mismatch")
            else:
                ranked = parsed["ranked"]
                expected = self.expected["ranked"]
                if len(ranked) != len(expected):
                    reasons.append("ranking_length_mismatch")
                elif [row["rank"] for row in ranked] != list(range(1, len(expected) + 1)):
                    reasons.append("ranking_rank_assignment_mismatch")
                elif ranked != expected:
                    if {row["id"] for row in ranked} == {row["id"] for row in expected}:
                        reasons.append("ranking_order_or_tie_break_mismatch")
                    else:
                        reasons.append("ranking_oracle_mismatch")
        return _verification(
            context=context,
            raw_result=raw_result,
            before_state=before_state,
            after_state=after_state,
            reasons=reasons,
            success_reason="deterministic_ordered_ranking_match",
        )


def verifier_for(definition: FrozenTaskDefinition) -> Any:
    verifier_types = {
        "A": FilterSelectionVerifier,
        "B": AggregationVerifier,
        "C": OrderedRankingVerifier,
    }
    verifier = verifier_types[definition.task_key](definition.oracle)
    _require_equal(
        verifier.verifier_id,
        definition.contract["verifier_id"],
        f"{definition.task_key} verifier identity drifted",
    )
    return verifier


def bound_evidence(definition: FrozenTaskDefinition) -> tuple[EvidenceRef, ...]:
    context = bind_execution(
        definition.core_contract(),
        definition.program_artifact(),
        definition.execution_identity(),
    )
    return tuple(
        EvidenceRef(item.role, item.artifact_id, item.path, item.sha256)
        for item in context.evidence_requirements
    )


class OfflineOutputAdapter:
    """Synthetic zero-model-call adapter for frozen negative-output tests."""

    def __init__(
        self,
        output: Any,
        *,
        producer_claim: str = "success",
        evidence: tuple[EvidenceRef, ...] | None = None,
        resource_report: AdapterResourceReport | None = None,
    ) -> None:
        self.output = output
        self.producer_claim = producer_claim
        self.evidence = evidence
        self.resource_report = resource_report or AdapterResourceReport()
        self.calls = 0

    def execute(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        state: MutableMapping[str, Any],
    ) -> RawResult:
        del request, state
        self.calls += 1
        supplied = self.evidence
        if supplied is None:
            supplied = tuple(
                EvidenceRef(item.role, item.artifact_id, item.path, item.sha256)
                for item in context.evidence_requirements
            )
        return RawResult(
            producer_claim=self.producer_claim,
            reported_value=self.output,
            evidence=supplied,
            executor_calls=1,
            mutation_primitive_calls=0,
            resource_report=self.resource_report,
        )


def execute_offline(
    task_key: str,
    output: Any,
    *,
    producer_claim: str = "success",
    evidence: tuple[EvidenceRef, ...] | None = None,
    resource_report: AdapterResourceReport | None = None,
) -> tuple[Any, OfflineOutputAdapter]:
    definition = load_task(task_key)
    adapter = OfflineOutputAdapter(
        output,
        producer_claim=producer_claim,
        evidence=evidence,
        resource_report=resource_report,
    )
    terminal = execute(
        contract=definition.core_contract(),
        program=definition.program_artifact(),
        supplied_identity=definition.execution_identity(),
        request=definition.execution_request(),
        state=definition.initial_state(),
        executor=adapter,
        verifier=verifier_for(definition),
        collect_observations=True,
    )
    return terminal, adapter


def definition_record(definition: FrozenTaskDefinition) -> dict[str, Any]:
    return {
        "task_key": definition.task_key,
        "task_id": definition.spec["task_id"],
        "semantic_family": definition.spec["semantic_family"],
        "run_id": definition.run_id,
        "contract_id": definition.spec["contract_id"],
        "contract_path": definition.contract_path.relative_to(SUBSTRATE).as_posix(),
        "contract_sha256": definition.contract_sha256,
        "program_id": definition.spec["program_id"],
        "program_path": definition.program_path.relative_to(SUBSTRATE).as_posix(),
        "program_sha256": definition.program_sha256,
        "input_path": definition.input_path.relative_to(SUBSTRATE).as_posix(),
        "input_sha256": definition.input_sha256,
        "schema_id": definition.spec["schema_id"],
        "schema_path": definition.schema_path.relative_to(SUBSTRATE).as_posix(),
        "schema_sha256": definition.schema_sha256,
        "oracle_id": definition.spec["oracle_id"],
        "verifier_id": definition.spec["verifier_id"],
        "prompt_sha256": definition.prompt_sha256,
        "configuration_id": CONFIGURATION_ID,
    }

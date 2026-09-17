"""Versioned, provider-neutral IRIS-X P1 product contracts."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import re
from typing import Any, ClassVar, TypeVar

from .canonical import digest_value, read_json, write_json
from .errors import ValidationError


SCHEMA_VERSION = "1.0"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def _fail(path: str, message: str) -> None:
    raise ValidationError(f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    return value


def _exact(obj: Mapping[str, Any], required: set[str], path: str, optional: set[str] | None = None) -> None:
    optional = optional or set()
    missing = required - obj.keys()
    unexpected = obj.keys() - required - optional
    if missing:
        _fail(path, f"missing fields {sorted(missing)}")
    if unexpected:
        _fail(path, f"unexpected fields {sorted(unexpected)}")


def _string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        _fail(path, "must be a non-empty string" if nonempty else "must be a string")
    return value


def _identifier(value: Any, path: str) -> str:
    value = _string(value, path)
    if not ID_RE.fullmatch(value):
        _fail(path, "must match [a-z0-9][a-z0-9._-]{0,127}")
    return value


def _digest(value: Any, path: str) -> str:
    value = _string(value, path)
    if not DIGEST_RE.fullmatch(value):
        _fail(path, "must be a lowercase sha256:<64 hex> digest")
    return value


def _version(value: Any, path: str) -> str:
    value = _string(value, path)
    if not VERSION_RE.fullmatch(value):
        _fail(path, "must be a semantic human version such as 1.0.0")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    return value


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "must be a boolean")
    return value


def _number(value: Any, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(path, "must be a number")
    return value


def validate_ref(value: Any, path: str, *, kind: str | None = None) -> dict[str, Any]:
    obj = _object(value, path)
    _exact(obj, {"kind", "artifact_id", "version", "content_digest"}, path)
    _string(obj["kind"], f"{path}.kind")
    _identifier(obj["artifact_id"], f"{path}.artifact_id")
    _version(obj["version"], f"{path}.version")
    _digest(obj["content_digest"], f"{path}.content_digest")
    if kind is not None and obj["kind"] != kind:
        _fail(f"{path}.kind", f"must be {kind!r}")
    return obj


def validate_source_ref(value: Any, path: str) -> dict[str, Any]:
    obj = _object(value, path)
    _exact(obj, {"source_id", "media_type", "content_digest", "locator"}, path)
    _identifier(obj["source_id"], f"{path}.source_id")
    _string(obj["media_type"], f"{path}.media_type")
    _digest(obj["content_digest"], f"{path}.content_digest")
    locator = _string(obj["locator"], f"{path}.locator")
    if "://" in locator or locator.startswith(("/", "\\")) or ".." in PurePosixPath(locator).parts:
        _fail(f"{path}.locator", "must be a bounded relative logical locator")
    return obj


def validate_observation(value: Any, path: str) -> dict[str, Any]:
    obj = _object(value, path)
    _exact(obj, {"state", "value", "unit"}, path)
    state = obj["state"]
    if state not in {"observed", "unknown", "not_evaluated"}:
        _fail(f"{path}.state", "must be observed, unknown, or not_evaluated")
    _string(obj["unit"], f"{path}.unit")
    if state == "observed":
        _number(obj["value"], f"{path}.value")
    elif obj["value"] is not None:
        _fail(f"{path}.value", "must be null unless state is observed")
    return obj


T = TypeVar("T", bound="VersionedContract")


class VersionedContract:
    """Common envelope separating schema, identity, human version, and digest."""

    SCHEMA: ClassVar[str]

    def __init__(
        self,
        artifact_id: str,
        version: str,
        payload: dict[str, Any],
        *,
        schema_version: str = SCHEMA_VERSION,
        content_digest: str | None = None,
    ) -> None:
        _identifier(artifact_id, "$.artifact_id")
        _version(version, "$.version")
        if schema_version != SCHEMA_VERSION:
            _fail("$.schema_version", f"unsupported version {schema_version!r}")
        self.validate_payload(_object(payload, "$.payload"), "$.payload")
        self.artifact_id = artifact_id
        self.version = version
        self.schema_version = schema_version
        self.payload = payload
        expected = digest_value(self._unsigned_dict())
        if content_digest is not None:
            _digest(content_digest, "$.content_digest")
            if content_digest != expected:
                _fail("$.content_digest", f"digest mismatch; expected {expected}")
        self.content_digest = expected

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        raise NotImplementedError

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "version": self.version,
            "payload": self.payload,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._unsigned_dict(), "content_digest": self.content_digest}

    def ref(self) -> dict[str, str]:
        return {
            "kind": self.SCHEMA,
            "artifact_id": self.artifact_id,
            "version": self.version,
            "content_digest": self.content_digest,
        }

    def write(self, path: Path) -> None:
        write_json(path, self.to_dict())

    @classmethod
    def from_dict(cls: type[T], value: Any) -> T:
        obj = _object(value, "$")
        _exact(obj, {"schema", "schema_version", "artifact_id", "version", "content_digest", "payload"}, "$")
        if obj["schema"] != cls.SCHEMA:
            _fail("$.schema", f"must be {cls.SCHEMA!r}")
        return cls(
            obj["artifact_id"],
            obj["version"],
            obj["payload"],
            schema_version=obj["schema_version"],
            content_digest=obj["content_digest"],
        )


class WorkloadDefinition(VersionedContract):
    SCHEMA = "irisx/workload-definition"

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        _exact(payload, {"name", "description", "frozen", "evaluator_ref", "cases"}, path)
        _string(payload["name"], f"{path}.name")
        _string(payload["description"], f"{path}.description")
        if not _bool(payload["frozen"], f"{path}.frozen"):
            _fail(f"{path}.frozen", "P1 workloads must be frozen")
        validate_ref(payload["evaluator_ref"], f"{path}.evaluator_ref", kind="irisx/evaluator-definition")
        cases = _list(payload["cases"], f"{path}.cases")
        if not cases:
            _fail(f"{path}.cases", "must contain at least one case")
        seen: set[str] = set()
        for index, value in enumerate(cases):
            case_path = f"{path}.cases[{index}]"
            case = _object(value, case_path)
            _exact(case, {"case_id", "segment", "critical", "input_ref", "expected_ref"}, case_path)
            case_id = _identifier(case["case_id"], f"{case_path}.case_id")
            if case_id in seen:
                _fail(f"{case_path}.case_id", "must be unique")
            seen.add(case_id)
            _identifier(case["segment"], f"{case_path}.segment")
            _bool(case["critical"], f"{case_path}.critical")
            validate_source_ref(case["input_ref"], f"{case_path}.input_ref")
            validate_source_ref(case["expected_ref"], f"{case_path}.expected_ref")


class RequirementSet(VersionedContract):
    SCHEMA = "irisx/requirement-set"

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        _exact(payload, {"name", "requirements"}, path)
        _string(payload["name"], f"{path}.name")
        requirements = _list(payload["requirements"], f"{path}.requirements")
        if not requirements:
            _fail(f"{path}.requirements", "must not be empty")
        seen: set[str] = set()
        for index, value in enumerate(requirements):
            req_path = f"{path}.requirements[{index}]"
            req = _object(value, req_path)
            _exact(req, {"requirement_id", "metric", "comparator", "threshold", "hard", "objective", "unit", "description"}, req_path)
            requirement_id = _identifier(req["requirement_id"], f"{req_path}.requirement_id")
            if requirement_id in seen:
                _fail(f"{req_path}.requirement_id", "must be unique")
            seen.add(requirement_id)
            _identifier(req["metric"], f"{req_path}.metric")
            if req["comparator"] not in {">=", "<=", "=="}:
                _fail(f"{req_path}.comparator", "must be >=, <=, or ==")
            _number(req["threshold"], f"{req_path}.threshold")
            _bool(req["hard"], f"{req_path}.hard")
            if req["objective"] not in {"satisfy", "minimize", "maximize"}:
                _fail(f"{req_path}.objective", "must be satisfy, minimize, or maximize")
            _string(req["unit"], f"{req_path}.unit")
            _string(req["description"], f"{req_path}.description")


class DomainSpecification(VersionedContract):
    SCHEMA = "irisx/domain-specification"

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        _exact(payload, {"name", "description", "material_refs", "workload_ref", "requirement_set_ref", "operating_constraints", "known_limitations"}, path)
        _string(payload["name"], f"{path}.name")
        _string(payload["description"], f"{path}.description")
        for index, ref in enumerate(_list(payload["material_refs"], f"{path}.material_refs")):
            validate_source_ref(ref, f"{path}.material_refs[{index}]")
        validate_ref(payload["workload_ref"], f"{path}.workload_ref", kind=WorkloadDefinition.SCHEMA)
        validate_ref(payload["requirement_set_ref"], f"{path}.requirement_set_ref", kind=RequirementSet.SCHEMA)
        for field in ("operating_constraints", "known_limitations"):
            for index, item in enumerate(_list(payload[field], f"{path}.{field}")):
                _string(item, f"{path}.{field}[{index}]")


class CandidateConfiguration(VersionedContract):
    SCHEMA = "irisx/candidate-configuration"
    COMPONENTS = {"model", "prompts_programs", "context_retrieval", "workflow_control", "adaptation", "validation"}

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        _exact(payload, {"name", "description", "components", "complexity", "maintainability", "known_limitations"}, path)
        _string(payload["name"], f"{path}.name")
        _string(payload["description"], f"{path}.description")
        components = _object(payload["components"], f"{path}.components")
        unexpected = components.keys() - cls.COMPONENTS
        if unexpected:
            _fail(f"{path}.components", f"unsupported components {sorted(unexpected)}")
        if not components:
            _fail(f"{path}.components", "must contain at least one optional component")
        for name, ref in components.items():
            validate_ref(ref, f"{path}.components.{name}")
        complexity = _number(payload["complexity"], f"{path}.complexity")
        if complexity < 0:
            _fail(f"{path}.complexity", "must be non-negative")
        if payload["maintainability"] not in {"low", "medium", "high", "unknown"}:
            _fail(f"{path}.maintainability", "must be low, medium, high, or unknown")
        for index, item in enumerate(_list(payload["known_limitations"], f"{path}.known_limitations")):
            _string(item, f"{path}.known_limitations[{index}]")


class EngineeringTrial(VersionedContract):
    SCHEMA = "irisx/engineering-trial"

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        _exact(payload, {"name", "goal", "qualification_fixture", "domain_specification_ref", "workload_ref", "requirement_set_ref", "evaluator_ref", "baseline_configuration_ref", "candidate_configuration_refs", "stop_conditions"}, path)
        _string(payload["name"], f"{path}.name")
        _string(payload["goal"], f"{path}.goal")
        _bool(payload["qualification_fixture"], f"{path}.qualification_fixture")
        validate_ref(payload["domain_specification_ref"], f"{path}.domain_specification_ref", kind=DomainSpecification.SCHEMA)
        validate_ref(payload["workload_ref"], f"{path}.workload_ref", kind=WorkloadDefinition.SCHEMA)
        validate_ref(payload["requirement_set_ref"], f"{path}.requirement_set_ref", kind=RequirementSet.SCHEMA)
        validate_ref(payload["evaluator_ref"], f"{path}.evaluator_ref", kind="irisx/evaluator-definition")
        validate_ref(payload["baseline_configuration_ref"], f"{path}.baseline_configuration_ref", kind=CandidateConfiguration.SCHEMA)
        candidates = _list(payload["candidate_configuration_refs"], f"{path}.candidate_configuration_refs")
        if not candidates:
            _fail(f"{path}.candidate_configuration_refs", "must contain at least one candidate")
        for index, ref in enumerate(candidates):
            validate_ref(ref, f"{path}.candidate_configuration_refs[{index}]", kind=CandidateConfiguration.SCHEMA)
        for index, item in enumerate(_list(payload["stop_conditions"], f"{path}.stop_conditions")):
            _string(item, f"{path}.stop_conditions[{index}]")


class EvaluationResult(VersionedContract):
    SCHEMA = "irisx/evaluation-result"

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        _exact(payload, {"trial_ref", "workload_ref", "evaluator_ref", "configuration_ref", "cases", "metrics", "resource_use", "known_limitations"}, path)
        validate_ref(payload["trial_ref"], f"{path}.trial_ref", kind=EngineeringTrial.SCHEMA)
        validate_ref(payload["workload_ref"], f"{path}.workload_ref", kind=WorkloadDefinition.SCHEMA)
        validate_ref(payload["evaluator_ref"], f"{path}.evaluator_ref", kind="irisx/evaluator-definition")
        validate_ref(payload["configuration_ref"], f"{path}.configuration_ref", kind=CandidateConfiguration.SCHEMA)
        cases = _list(payload["cases"], f"{path}.cases")
        if not cases:
            _fail(f"{path}.cases", "must not be empty")
        seen: set[str] = set()
        for index, value in enumerate(cases):
            case_path = f"{path}.cases[{index}]"
            case = _object(value, case_path)
            _exact(case, {"case_id", "segment", "passed", "critical_failure", "score", "detail"}, case_path)
            case_id = _identifier(case["case_id"], f"{case_path}.case_id")
            if case_id in seen:
                _fail(f"{case_path}.case_id", "must be unique")
            seen.add(case_id)
            _identifier(case["segment"], f"{case_path}.segment")
            _bool(case["passed"], f"{case_path}.passed")
            _bool(case["critical_failure"], f"{case_path}.critical_failure")
            _number(case["score"], f"{case_path}.score")
            _string(case["detail"], f"{case_path}.detail")
        for field in ("metrics", "resource_use"):
            observations = _object(payload[field], f"{path}.{field}")
            for name, observation in observations.items():
                _identifier(name, f"{path}.{field} key")
                validate_observation(observation, f"{path}.{field}.{name}")
        for index, item in enumerate(_list(payload["known_limitations"], f"{path}.known_limitations")):
            _string(item, f"{path}.known_limitations[{index}]")


class SelectionDecision(VersionedContract):
    SCHEMA = "irisx/selection-decision"

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        _exact(payload, {"outcome", "trial_ref", "workload_ref", "evaluator_ref", "baseline_result_ref", "considered_result_refs", "eligible_result_refs", "selected_configuration_ref", "selected_result_ref", "reason", "tie_break_rule", "known_limitations"}, path)
        if payload["outcome"] not in {"promote", "no_promotion", "infeasible"}:
            _fail(f"{path}.outcome", "must be promote, no_promotion, or infeasible")
        validate_ref(payload["trial_ref"], f"{path}.trial_ref", kind=EngineeringTrial.SCHEMA)
        validate_ref(payload["workload_ref"], f"{path}.workload_ref", kind=WorkloadDefinition.SCHEMA)
        validate_ref(payload["evaluator_ref"], f"{path}.evaluator_ref", kind="irisx/evaluator-definition")
        validate_ref(payload["baseline_result_ref"], f"{path}.baseline_result_ref", kind=EvaluationResult.SCHEMA)
        for field in ("considered_result_refs", "eligible_result_refs"):
            refs = _list(payload[field], f"{path}.{field}")
            for index, ref in enumerate(refs):
                validate_ref(ref, f"{path}.{field}[{index}]", kind=EvaluationResult.SCHEMA)
        selected_config = payload["selected_configuration_ref"]
        selected_result = payload["selected_result_ref"]
        if payload["outcome"] == "promote":
            validate_ref(selected_config, f"{path}.selected_configuration_ref", kind=CandidateConfiguration.SCHEMA)
            validate_ref(selected_result, f"{path}.selected_result_ref", kind=EvaluationResult.SCHEMA)
            eligible_digests = {item["content_digest"] for item in payload["eligible_result_refs"]}
            if selected_result["content_digest"] not in eligible_digests:
                _fail(f"{path}.selected_result_ref", "must be an eligible result")
        elif selected_config is not None or selected_result is not None:
            _fail(path, "non-promote outcomes must not select a configuration or result")
        _string(payload["reason"], f"{path}.reason")
        _string(payload["tie_break_rule"], f"{path}.tie_break_rule")
        for index, item in enumerate(_list(payload["known_limitations"], f"{path}.known_limitations")):
            _string(item, f"{path}.known_limitations[{index}]")


class DomainPackageManifest(VersionedContract):
    SCHEMA = "irisx/domain-package-manifest"

    @classmethod
    def validate_payload(cls, payload: dict[str, Any], path: str) -> None:
        _exact(payload, {"domain_specification_ref", "workload_ref", "requirement_set_ref", "evaluator_ref", "selected_configuration_ref", "measured_result_ref", "selection_decision_ref", "deployment_metadata_ref", "known_limitations", "artifacts"}, path)
        kinds = {
            "domain_specification_ref": DomainSpecification.SCHEMA,
            "workload_ref": WorkloadDefinition.SCHEMA,
            "requirement_set_ref": RequirementSet.SCHEMA,
            "evaluator_ref": "irisx/evaluator-definition",
            "selected_configuration_ref": CandidateConfiguration.SCHEMA,
            "measured_result_ref": EvaluationResult.SCHEMA,
            "selection_decision_ref": SelectionDecision.SCHEMA,
            "deployment_metadata_ref": "irisx/deployment-metadata",
        }
        for field, kind in kinds.items():
            validate_ref(payload[field], f"{path}.{field}", kind=kind)
        for index, item in enumerate(_list(payload["known_limitations"], f"{path}.known_limitations")):
            _string(item, f"{path}.known_limitations[{index}]")
        artifacts = _list(payload["artifacts"], f"{path}.artifacts")
        if not artifacts:
            _fail(f"{path}.artifacts", "must not be empty")
        seen: set[str] = set()
        for index, value in enumerate(artifacts):
            artifact_path = f"{path}.artifacts[{index}]"
            artifact = _object(value, artifact_path)
            _exact(artifact, {"path", "kind", "content_digest"}, artifact_path)
            relative = _string(artifact["path"], f"{artifact_path}.path")
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or relative == "manifest.json":
                _fail(f"{artifact_path}.path", "must be a safe relative non-manifest path")
            if relative in seen:
                _fail(f"{artifact_path}.path", "must be unique")
            seen.add(relative)
            _string(artifact["kind"], f"{artifact_path}.kind")
            _digest(artifact["content_digest"], f"{artifact_path}.content_digest")


CONTRACT_TYPES: dict[str, type[VersionedContract]] = {
    contract.SCHEMA: contract
    for contract in (
        DomainSpecification,
        WorkloadDefinition,
        RequirementSet,
        CandidateConfiguration,
        EngineeringTrial,
        EvaluationResult,
        SelectionDecision,
        DomainPackageManifest,
    )
}


def load_contract(path: Path, expected: type[T] | None = None) -> VersionedContract | T:
    value = read_json(path)
    if not isinstance(value, dict):
        _fail("$", "contract must be an object")
    schema = value.get("schema")
    contract_type = CONTRACT_TYPES.get(schema)
    if contract_type is None:
        _fail("$.schema", f"unknown contract schema {schema!r}")
    if expected is not None and contract_type is not expected:
        _fail("$.schema", f"expected {expected.SCHEMA!r}, got {schema!r}")
    return contract_type.from_dict(value)


def assert_binding(ref: Any, target: VersionedContract, path: str) -> None:
    validate_ref(ref, path, kind=target.SCHEMA)
    if ref != target.ref():
        _fail(path, f"identity mismatch for {target.artifact_id!r}")


def write_contract(path: Path, contract: VersionedContract) -> None:
    write_json(path, contract.to_dict())

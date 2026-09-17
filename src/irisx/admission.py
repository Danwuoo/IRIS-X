"""Fail-closed validation for the first real-domain P2 admission package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical import digest_bytes, digest_value, read_json
from .contracts import (
    DIGEST_RE,
    SCHEMA_VERSION,
    VERSION_RE,
    _exact,
    _identifier,
    _list,
    _object,
    _string,
    validate_logical_path,
    validate_ref,
)
from .errors import ValidationError


ADMISSION_SCHEMA = "irisx/p2-admission"
ADMISSION_STATUS = "admission_blocked"
AUTHORITY_PATHS = (
    "AGENTS.md",
    "PRODUCT_THESIS.md",
    "docs/decisions/0001-adopt-product-oriented-domain-ai-specialization.md",
    "docs/decisions/0002-adopt-p1-contract-and-serialization-foundation.md",
    "docs/decisions/0003-record-p2-admission-block.md",
)
DECISION_OPTIONS = (
    "local-offline-real-domain",
    "authorized-external-provider",
    "defer-p2",
)
GATE_IDS = (
    "real-domain-and-workload",
    "data-rights-and-provenance",
    "baseline",
    "specialization-intervention",
    "evaluation-and-acceptance",
    "external-execution",
    "provider-model-and-budget",
    "deployment-target",
)
TRIAL_REF_KINDS = {
    "domain_specification_ref": "irisx/domain-specification",
    "workload_ref": "irisx/workload-definition",
    "requirement_set_ref": "irisx/requirement-set",
    "evaluator_ref": "irisx/evaluator-definition",
    "baseline_configuration_ref": "irisx/candidate-configuration",
}
CANDIDATE_REF_KIND = "irisx/candidate-configuration"
ACCEPTANCE_CRITERIA_IDS = (
    "authorized-real-evidence",
    "same-frozen-workload",
    "baseline-and-candidate-comparable",
    "hard-requirements-satisfied",
    "resource-use-accounted",
    "selection-reproducible",
    "domain-package-verifiable",
)
FALSIFIER_IDS = (
    "unrepresentative-workload",
    "missing-rights-or-provenance",
    "synthetic-evidence-presented-as-real",
    "unauthorized-external-execution",
    "unapproved-provider-model-or-budget",
    "stale-or-wrong-reference",
    "hard-requirement-failure",
    "non-reproducible-selection-or-package",
)


def _fail(path: str, message: str) -> None:
    raise ValidationError(f"{path}: {message}")


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "must be a boolean")
    return value


def _nullable_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _string(value, path)


def _find_repository_root(path: Path) -> Path:
    start = path.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / "PRODUCT_THESIS.md").is_file():
            return candidate
    raise ValidationError(f"cannot locate repository root from {path}")


def _validate_file_ref(value: Any, path: str, repository_root: Path) -> None:
    obj = _object(value, path)
    _exact(obj, {"path", "content_digest"}, path)
    relative = validate_logical_path(obj["path"], f"{path}.path")
    digest = _string(obj["content_digest"], f"{path}.content_digest")
    if not DIGEST_RE.fullmatch(digest):
        _fail(f"{path}.content_digest", "must be a lowercase sha256:<64 hex> digest")
    target = repository_root.joinpath(*relative.split("/"))
    try:
        target.resolve().relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ValidationError(f"{path}.path: resolves outside the repository") from exc
    if not target.is_file():
        _fail(f"{path}.path", "referenced authority file is missing")
    if digest_bytes(target.read_bytes()) != digest:
        _fail(f"{path}.content_digest", "stale or wrong authority reference")


def _validate_unknown_ref(value: Any, path: str, kind: str) -> None:
    obj = _object(value, path)
    _exact(obj, {"state", "kind", "artifact_id", "version", "content_digest"}, path)
    if obj["kind"] != kind:
        _fail(f"{path}.kind", f"must be {kind!r}")
    if obj["state"] == "unknown":
        if any(obj[field] is not None for field in ("artifact_id", "version", "content_digest")):
            _fail(path, "unknown references must use null identity fields")
        return
    if obj["state"] != "bound":
        _fail(f"{path}.state", "must be unknown or bound")
    validate_ref(
        {field: obj[field] for field in ("kind", "artifact_id", "version", "content_digest")},
        path,
        kind=kind,
    )


def _validate_authority_refs(value: Any, repository_root: Path) -> None:
    refs = _list(value, "$.payload.authority_refs")
    paths: list[str] = []
    for index, ref in enumerate(refs):
        _validate_file_ref(ref, f"$.payload.authority_refs[{index}]", repository_root)
        paths.append(ref["path"])
    if tuple(paths) != AUTHORITY_PATHS:
        _fail("$.payload.authority_refs", f"must list the exact ordered authority set {list(AUTHORITY_PATHS)}")


def _validate_decision_options(value: Any) -> None:
    options = _list(value, "$.payload.decision_options")
    identifiers: list[str] = []
    for index, option_value in enumerate(options):
        path = f"$.payload.decision_options[{index}]"
        option = _object(option_value, path)
        _exact(option, {"option_id", "label", "execution_mode", "requires", "effect"}, path)
        identifiers.append(_identifier(option["option_id"], f"{path}.option_id"))
        _string(option["label"], f"{path}.label")
        if option["execution_mode"] not in {"local_offline", "external_provider", "none"}:
            _fail(f"{path}.execution_mode", "must be local_offline, external_provider, or none")
        requires = _list(option["requires"], f"{path}.requires")
        for requirement_index, gate_id in enumerate(requires):
            if gate_id not in GATE_IDS:
                _fail(f"{path}.requires[{requirement_index}]", "must name an admission gate")
        if len(requires) != len(set(requires)):
            _fail(f"{path}.requires", "must not contain duplicate gates")
        _string(option["effect"], f"{path}.effect")
    if tuple(identifiers) != DECISION_OPTIONS:
        _fail("$.payload.decision_options", f"must contain the exact mutually exclusive options {list(DECISION_OPTIONS)}")
    expected = {
        "local-offline-real-domain": ("local_offline", GATE_IDS[0:5] + (GATE_IDS[7],)),
        "authorized-external-provider": ("external_provider", GATE_IDS),
        "defer-p2": ("none", ()),
    }
    for index, option in enumerate(options):
        mode, gates = expected[option["option_id"]]
        if option["execution_mode"] != mode or tuple(option["requires"]) != gates:
            _fail(f"$.payload.decision_options[{index}]", "execution mode and required gates do not match the option")


def _validate_gates(value: Any, repository_root: Path) -> None:
    gates = _list(value, "$.payload.gates")
    identifiers: list[str] = []
    for index, gate_value in enumerate(gates):
        path = f"$.payload.gates[{index}]"
        gate = _object(gate_value, path)
        _exact(gate, {"gate_id", "status", "owner_decision", "evidence_refs"}, path)
        identifiers.append(_identifier(gate["gate_id"], f"{path}.gate_id"))
        if gate["status"] not in {"unknown", "authorized", "not_required"}:
            _fail(f"{path}.status", "must be unknown, authorized, or not_required")
        decision = _string(gate["owner_decision"], f"{path}.owner_decision")
        refs = _list(gate["evidence_refs"], f"{path}.evidence_refs")
        for ref_index, ref in enumerate(refs):
            _validate_file_ref(ref, f"{path}.evidence_refs[{ref_index}]", repository_root)
        if gate["status"] == "unknown" and (decision != "Unknown" or refs):
            _fail(path, "unknown gates must use owner_decision 'Unknown' and no evidence refs")
        if gate["status"] == "authorized" and (decision == "Unknown" or not refs):
            _fail(path, "authorized gates require a concrete owner decision and evidence ref")
        if gate["status"] == "not_required" and decision == "Unknown":
            _fail(path, "not_required gates require an explicit owner decision")
    if tuple(identifiers) != GATE_IDS:
        _fail("$.payload.gates", f"must contain the exact ordered gate set {list(GATE_IDS)}")


def _validate_execution_authorization(value: Any) -> None:
    path = "$.payload.execution_authorization"
    authorization = _object(value, path)
    _exact(
        authorization,
        {"state", "mode", "provider", "model", "permitted_data_classes", "maximum_budget", "stop_conditions", "retention"},
        path,
    )
    if authorization["state"] not in {"unknown", "authorized"}:
        _fail(f"{path}.state", "must be unknown or authorized")
    if authorization["mode"] not in {"unknown", "local_offline", "external_provider"}:
        _fail(f"{path}.mode", "must be unknown, local_offline, or external_provider")
    provider = _nullable_string(authorization["provider"], f"{path}.provider")
    model = _nullable_string(authorization["model"], f"{path}.model")
    data_classes = _list(authorization["permitted_data_classes"], f"{path}.permitted_data_classes")
    for index, item in enumerate(data_classes):
        _string(item, f"{path}.permitted_data_classes[{index}]")
    budget = _object(authorization["maximum_budget"], f"{path}.maximum_budget")
    _exact(budget, {"state", "value", "unit"}, f"{path}.maximum_budget")
    if budget["state"] not in {"unknown", "observed"}:
        _fail(f"{path}.maximum_budget.state", "must be unknown or observed")
    if budget["unit"] != "usd":
        _fail(f"{path}.maximum_budget.unit", "must be 'usd'")
    stop_conditions = _list(authorization["stop_conditions"], f"{path}.stop_conditions")
    for index, item in enumerate(stop_conditions):
        _string(item, f"{path}.stop_conditions[{index}]")
    retention = _string(authorization["retention"], f"{path}.retention")

    if authorization["state"] == "unknown":
        if (
            authorization["mode"] != "unknown"
            or provider is not None
            or model is not None
            or data_classes
            or budget != {"state": "unknown", "value": None, "unit": "usd"}
            or retention != "Unknown"
        ):
            _fail(path, "unknown execution authorization must not imply provider, model, data, budget, or retention approval")
        return

    if authorization["mode"] == "unknown":
        _fail(f"{path}.mode", "authorized execution requires a concrete mode")
    if budget["state"] != "observed" or isinstance(budget["value"], bool) or not isinstance(budget["value"], (int, float)) or budget["value"] < 0:
        _fail(f"{path}.maximum_budget", "authorized execution requires a non-negative observed USD limit")
    if not data_classes or not stop_conditions or retention == "Unknown":
        _fail(path, "authorized execution requires permitted data, stop conditions, and retention")
    if authorization["mode"] == "external_provider" and (provider is None or model is None):
        _fail(path, "external execution requires an approved provider and model")
    if authorization["mode"] == "local_offline" and (provider is not None or model is not None or budget["value"] != 0):
        _fail(path, "local offline execution requires no provider/model and a zero USD limit")


def _validate_criteria(value: Any, path: str, expected: tuple[str, ...]) -> None:
    entries = _list(value, path)
    identifiers: list[str] = []
    for index, entry_value in enumerate(entries):
        entry_path = f"{path}[{index}]"
        entry = _object(entry_value, entry_path)
        _exact(entry, {"criterion_id", "statement"}, entry_path)
        identifiers.append(_identifier(entry["criterion_id"], f"{entry_path}.criterion_id"))
        _string(entry["statement"], f"{entry_path}.statement")
    if tuple(identifiers) != expected:
        _fail(path, f"must contain the exact ordered identifiers {list(expected)}")


def _validate_trial_draft(value: Any) -> None:
    path = "$.payload.trial_draft"
    draft = _object(value, path)
    _exact(
        draft,
        {
            "contract_schema",
            "artifact_id",
            "version",
            "name",
            "goal",
            "qualification_fixture",
            "required_evidence_class",
            "provided_evidence_class",
            *TRIAL_REF_KINDS,
            "candidate_configuration_refs",
            "directory",
            "acceptance_criteria",
            "falsifiers",
            "stop_conditions",
            "unknowns",
        },
        path,
    )
    if draft["contract_schema"] != "irisx/engineering-trial":
        _fail(f"{path}.contract_schema", "must target the existing EngineeringTrial contract")
    _identifier(draft["artifact_id"], f"{path}.artifact_id")
    version = _string(draft["version"], f"{path}.version")
    if not VERSION_RE.fullmatch(version):
        _fail(f"{path}.version", "must be a semantic version")
    _string(draft["name"], f"{path}.name")
    _string(draft["goal"], f"{path}.goal")
    if _bool(draft["qualification_fixture"], f"{path}.qualification_fixture"):
        _fail(f"{path}.qualification_fixture", "a real P2 trial must not be a P1 qualification fixture")
    if draft["required_evidence_class"] != "real":
        _fail(f"{path}.required_evidence_class", "must be 'real'")
    if draft["provided_evidence_class"] not in {"unknown", "real", "synthetic"}:
        _fail(f"{path}.provided_evidence_class", "must be unknown, real, or synthetic")
    for field, kind in TRIAL_REF_KINDS.items():
        _validate_unknown_ref(draft[field], f"{path}.{field}", kind)
    candidate_refs = _list(draft["candidate_configuration_refs"], f"{path}.candidate_configuration_refs")
    if not candidate_refs:
        _fail(f"{path}.candidate_configuration_refs", "must contain at least one candidate draft reference")
    for index, ref in enumerate(candidate_refs):
        _validate_unknown_ref(ref, f"{path}.candidate_configuration_refs[{index}]", CANDIDATE_REF_KIND)
    directory = validate_logical_path(draft["directory"], f"{path}.directory")
    if not directory.startswith("trials/") or directory == "trials/p2-admission":
        _fail(f"{path}.directory", "must reserve a real trial directory below trials/, separate from admission")
    _validate_criteria(draft["acceptance_criteria"], f"{path}.acceptance_criteria", ACCEPTANCE_CRITERIA_IDS)
    _validate_criteria(draft["falsifiers"], f"{path}.falsifiers", FALSIFIER_IDS)
    stop_conditions = _list(draft["stop_conditions"], f"{path}.stop_conditions")
    if not stop_conditions:
        _fail(f"{path}.stop_conditions", "must not be empty")
    for index, item in enumerate(stop_conditions):
        _string(item, f"{path}.stop_conditions[{index}]")
    unknowns = _list(draft["unknowns"], f"{path}.unknowns")
    if set(unknowns) != set(GATE_IDS) or len(unknowns) != len(GATE_IDS):
        _fail(f"{path}.unknowns", "must explicitly mark every unresolved admission gate")


def validate_admission_document(value: Any, repository_root: Path) -> dict[str, Any]:
    """Validate a digest-bound admission snapshot and all local authority refs."""

    obj = _object(value, "$")
    _exact(obj, {"schema", "schema_version", "artifact_id", "version", "content_digest", "payload"}, "$")
    if obj["schema"] != ADMISSION_SCHEMA:
        _fail("$.schema", f"must be {ADMISSION_SCHEMA!r}")
    if obj["schema_version"] != SCHEMA_VERSION:
        _fail("$.schema_version", f"unsupported version {obj['schema_version']!r}")
    _identifier(obj["artifact_id"], "$.artifact_id")
    version = _string(obj["version"], "$.version")
    if not VERSION_RE.fullmatch(version):
        _fail("$.version", "must be a semantic version")
    digest = _string(obj["content_digest"], "$.content_digest")
    if not DIGEST_RE.fullmatch(digest):
        _fail("$.content_digest", "must be a lowercase sha256:<64 hex> digest")
    unsigned = {key: obj[key] for key in ("schema", "schema_version", "artifact_id", "version", "payload")}
    expected_digest = digest_value(unsigned)
    if digest != expected_digest:
        _fail("$.content_digest", f"digest mismatch; expected {expected_digest}")

    payload = _object(obj["payload"], "$.payload")
    _exact(
        payload,
        {
            "status",
            "scope",
            "authority_refs",
            "decision_options",
            "owner_selection",
            "gates",
            "execution_authorization",
            "trial_draft",
            "eligibility",
        },
        "$.payload",
    )
    if payload["status"] != ADMISSION_STATUS:
        _fail("$.payload.status", "this decision snapshot must remain admission_blocked")
    scope = _object(payload["scope"], "$.payload.scope")
    _exact(scope, {"authorized", "real_trial_execution", "external_execution", "paid_execution", "production_deployment"}, "$.payload.scope")
    if scope["authorized"] != "P2 admission preparation only":
        _fail("$.payload.scope.authorized", "must be 'P2 admission preparation only'")
    for field in ("real_trial_execution", "external_execution", "paid_execution", "production_deployment"):
        if _bool(scope[field], f"$.payload.scope.{field}"):
            _fail(f"$.payload.scope.{field}", "is not authorized by this admission snapshot")

    _validate_authority_refs(payload["authority_refs"], repository_root)
    _validate_decision_options(payload["decision_options"])
    selection = _object(payload["owner_selection"], "$.payload.owner_selection")
    _exact(selection, {"state", "option_id"}, "$.payload.owner_selection")
    if selection != {"state": "unknown", "option_id": None}:
        _fail("$.payload.owner_selection", "must remain Unknown until a later owner decision is recorded")
    _validate_gates(payload["gates"], repository_root)
    if any(gate["status"] != "unknown" for gate in payload["gates"]):
        _fail("$.payload.gates", "this snapshot must keep all unresolved gates Unknown")
    _validate_execution_authorization(payload["execution_authorization"])
    if payload["execution_authorization"]["state"] != "unknown":
        _fail("$.payload.execution_authorization", "this snapshot grants no execution authorization")
    _validate_trial_draft(payload["trial_draft"])
    evidence_class = payload["trial_draft"]["provided_evidence_class"]
    if evidence_class == "synthetic":
        _fail("$.payload.trial_draft.provided_evidence_class", "synthetic evidence cannot be presented as real P2 evidence")
    if evidence_class != "unknown":
        _fail("$.payload.trial_draft.provided_evidence_class", "this snapshot has not admitted real evidence")
    if any(payload["trial_draft"][field]["state"] != "unknown" for field in TRIAL_REF_KINDS):
        _fail("$.payload.trial_draft", "draft artifact references must remain Unknown until a later owner decision")
    if any(ref["state"] != "unknown" for ref in payload["trial_draft"]["candidate_configuration_refs"]):
        _fail("$.payload.trial_draft", "candidate draft references must remain Unknown until a later owner decision")

    eligibility = _object(payload["eligibility"], "$.payload.eligibility")
    _exact(eligibility, {"engineering_trial_execution", "promotion", "domain_package", "reason"}, "$.payload.eligibility")
    for field in ("engineering_trial_execution", "promotion", "domain_package"):
        if _bool(eligibility[field], f"$.payload.eligibility.{field}"):
            _fail(f"$.payload.eligibility.{field}", "must be false while admission is blocked")
    _string(eligibility["reason"], "$.payload.eligibility.reason")
    return obj


def validate_admission_file(path: Path, repository_root: Path | None = None) -> dict[str, Any]:
    """Load and validate an admission file relative to the active repository."""

    repository_root = repository_root.resolve() if repository_root is not None else _find_repository_root(path.parent)
    return validate_admission_document(read_json(path), repository_root)


def admission_summary(value: dict[str, Any]) -> dict[str, Any]:
    """Return stable status information for CLI and tests."""

    payload = value["payload"]
    unresolved = [gate["gate_id"] for gate in payload["gates"] if gate["status"] == "unknown"]
    return {
        "status": payload["status"],
        "unresolved_gates": unresolved,
        "owner_selection": payload["owner_selection"],
        "execution_eligible": payload["eligibility"]["engineering_trial_execution"],
        "promotion_eligible": payload["eligibility"]["promotion"],
        "domain_package_eligible": payload["eligibility"]["domain_package"],
    }

#!/usr/bin/env python3
"""Derive provenance-bound direct predicates from immutable JSON sources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = EXPERIMENT_ROOT / "definition" / "predicate-derivation-rules.json"
SCHEMA_PATH = EXPERIMENT_ROOT / "definition" / "direct-predicate-schema.json"
PREDICATE_VALUES = {"true", "false", "unknown", "conflicting"}


class PredicateDerivationError(ValueError):
    """A direct predicate cannot be derived with valid authority."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise PredicateDerivationError(f"JSON top level must be an object: {path}")
    return value


def rule_sha256(rule: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in rule.items() if key != "derivation_rule_sha256"}
    return sha256_bytes(canonical_json_bytes(payload))


def validate_rule_hash(rule: Mapping[str, Any]) -> None:
    observed = rule.get("derivation_rule_sha256")
    expected = rule_sha256(rule)
    if observed != expected:
        raise PredicateDerivationError(
            f"derivation rule hash mismatch: {rule.get('derivation_rule_id')}"
        )


def _decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve_pointer(document: Any, pointer: str) -> list[Any]:
    if pointer == "":
        return [document]
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise PredicateDerivationError(f"invalid JSON Pointer: {pointer!r}")
    current = [document]
    for raw_token in pointer[1:].split("/"):
        token = _decode_pointer_token(raw_token)
        next_values: list[Any] = []
        for value in current:
            if token == "*":
                if isinstance(value, list):
                    next_values.extend(value)
                elif isinstance(value, dict):
                    next_values.extend(value[key] for key in sorted(value))
                else:
                    raise PredicateDerivationError(f"wildcard applied to scalar at {pointer}")
            elif isinstance(value, list):
                try:
                    next_values.append(value[int(token)])
                except (ValueError, IndexError) as exc:
                    raise PredicateDerivationError(f"bad array pointer: {pointer}") from exc
            elif isinstance(value, dict) and token in value:
                next_values.append(value[token])
            else:
                raise PredicateDerivationError(f"source pointer not found: {pointer}")
        current = next_values
    return current


def _evaluate(operator: str, values: Sequence[Any], expected: Any) -> str:
    if not values:
        return "unknown"
    if operator == "equals":
        if len(values) > 1 and any(value != values[0] for value in values[1:]):
            return "conflicting"
        return "true" if values[0] == expected else "false"
    if operator == "consensus_equals":
        if any(value != values[0] for value in values[1:]):
            return "conflicting"
        return "true" if values[0] == expected else "false"
    if operator == "any_equals":
        return "true" if any(value == expected for value in values) else "false"
    if operator == "integer_at_least":
        if len(values) != 1 or isinstance(values[0], bool) or not isinstance(values[0], int):
            raise PredicateDerivationError("integer_at_least requires one integer observation")
        return "true" if values[0] >= expected else "false"
    if operator == "distinct_count_at_least":
        return "true" if len({json.dumps(value, sort_keys=True) for value in values}) >= expected else "false"
    raise PredicateDerivationError(f"unknown derivation operator: {operator}")


def validate_predicate_record(record: Mapping[str, Any]) -> None:
    schema = load_object(SCHEMA_PATH)
    if set(record) != set(schema["required"]):
        raise PredicateDerivationError("predicate record fields differ from frozen schema")
    if record["predicate_value"] not in PREDICATE_VALUES:
        raise PredicateDerivationError("invalid predicate value")
    if record["evidence_class"] != "direct_repository_evidence":
        raise PredicateDerivationError("synthetic evidence cannot masquerade as direct evidence")
    if record["predicate_value"] in {"true", "false", "conflicting"} and not record["source_refs"]:
        raise PredicateDerivationError("resolved direct evidence requires source refs")
    for source in record["source_refs"]:
        if set(source) != set(schema["source_ref_required"]):
            raise PredicateDerivationError("source ref fields differ from frozen schema")


def derive_rule(rule: Mapping[str, Any], *, source_root: Path = EXPERIMENT_ROOT) -> dict[str, Any]:
    validate_rule_hash(rule)
    observations: list[Any] = []
    source_refs: list[dict[str, Any]] = []
    missing: list[str] = []
    for source in rule["sources"]:
        relative = Path(source["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise PredicateDerivationError("source path must remain within the source root")
        path = source_root / relative
        if not path.is_file():
            missing.append(relative.as_posix())
            continue
        content = path.read_bytes()
        document = json.loads(content)
        values = resolve_pointer(document, source["pointer"])
        observations.extend(values)
        source_refs.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256_bytes(content),
                "pointer_or_field": source["pointer"],
                "observed_value": values[0] if len(values) == 1 else values,
            }
        )
    predicate_value = (
        "unknown"
        if missing
        else _evaluate(rule["operator"], observations, rule.get("expected"))
    )
    status = (
        "missing_observation"
        if missing
        else "conflicting_observations"
        if predicate_value == "conflicting"
        else "derived"
    )
    record = {
        "predicate_record_id": f"direct-{rule['gate_id']}-{rule['predicate_id']}-v0",
        "gate_id": rule["gate_id"],
        "predicate_id": rule["predicate_id"],
        "predicate_value": predicate_value,
        "evidence_class": "direct_repository_evidence",
        "derivation_rule_id": rule["derivation_rule_id"],
        "derivation_rule_sha256": rule["derivation_rule_sha256"],
        "source_refs": source_refs,
        "derivation_status": status,
        "derivation_notes": (
            "missing immutable source observation: " + ", ".join(missing)
            if missing
            else "derived deterministically from hash-bound source observations"
        ),
    }
    validate_predicate_record(record)
    return record


def derive_request(request: Mapping[str, Any], *, source_root: Path) -> dict[str, Any]:
    if "predicate_value" in request:
        raise PredicateDerivationError("manual direct predicate override is prohibited")
    if request.get("evidence_class", "direct_repository_evidence") != "direct_repository_evidence":
        raise PredicateDerivationError("synthetic evidence cannot masquerade as direct evidence")
    rule = request.get("rule")
    if not isinstance(rule, dict):
        raise PredicateDerivationError("derivation request requires a frozen rule")
    return derive_rule(rule, source_root=source_root)


def validate_source_refs(record: Mapping[str, Any], *, source_root: Path) -> None:
    validate_predicate_record(record)
    for source in record["source_refs"]:
        path = source_root / source["path"]
        if not path.is_file():
            raise PredicateDerivationError(f"source path absent: {source['path']}")
        content = path.read_bytes()
        if sha256_bytes(content) != source["sha256"]:
            raise PredicateDerivationError(f"source hash mismatch: {source['path']}")
        values = resolve_pointer(json.loads(content), source["pointer_or_field"])
        observed = values[0] if len(values) == 1 else values
        if observed != source["observed_value"]:
            raise PredicateDerivationError(f"observed source value mismatch: {source['path']}")


def evaluate_gate(
    gate: Mapping[str, Any],
    predicate_records: Sequence[Mapping[str, Any]],
    *,
    negative_controls: Sequence[Mapping[str, Any]] = (),
) -> str:
    records = {
        record["predicate_id"]: record
        for record in predicate_records
        if record["gate_id"] == gate["gate_id"]
    }
    values = [records.get(predicate_id, {}).get("predicate_value", "unknown") for predicate_id in gate["required_predicates"]]
    if any(value == "conflicting" for value in values):
        return "insufficient_or_ambiguous"
    for control in negative_controls:
        if control.get("conflicts_with_predicate_id") in gate["required_predicates"] and control.get("conflict_observed") is True:
            return "insufficient_or_ambiguous"
    if values and all(value == "true" for value in values):
        return "triggered_by_direct_evidence"
    if any(value == "unknown" for value in values):
        return "insufficient_or_ambiguous"
    return "not_triggered"


def derive_all(*, source_root: Path = EXPERIMENT_ROOT) -> dict[str, Any]:
    definitions = load_object(RULES_PATH)
    records = [derive_rule(rule, source_root=source_root) for rule in definitions["rules"]]
    gate_results = {
        gate["gate_id"]: evaluate_gate(gate, records) for gate in definitions["gates"]
    }
    return {"schema_version": 1, "predicate_records": records, "gate_results": gate_results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=EXPERIMENT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        payload = derive_all(source_root=args.source_root)
        content = pretty_json_bytes(payload)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(content)
        else:
            print(content.decode("utf-8"), end="")
        return 0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"direct predicate derivation: FAIL ({exc})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

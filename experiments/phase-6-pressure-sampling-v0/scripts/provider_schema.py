#!/usr/bin/env python3
"""Deterministic closed-world validation for the admitted response-schema boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = EXPERIMENT_ROOT / "definition" / "provider-response-schema-policy.json"
EXPECTED_PROFILE_ID = "codex-cli-0.147.0-run-03-admission-v0"
EXPECTED_DIALECT = "http://json-schema.org/draft-07/schema#"


class ProviderSchemaError(ValueError):
    """A response schema is outside the frozen admitted provider subset."""


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ProviderSchemaError("provider schema policy must be a JSON object")
    if value.get("admitted_profile_id") != EXPECTED_PROFILE_ID:
        raise ProviderSchemaError("provider schema policy profile mismatch")
    supported = value.get("supported_keywords")
    unsupported = value.get("known_unsupported_keywords")
    if not isinstance(supported, list) or not all(isinstance(item, str) for item in supported):
        raise ProviderSchemaError("supported_keywords must be a string list")
    if not isinstance(unsupported, list) or not all(isinstance(item, str) for item in unsupported):
        raise ProviderSchemaError("known_unsupported_keywords must be a string list")
    if set(supported) & set(unsupported):
        raise ProviderSchemaError("provider schema keyword policy overlaps")
    return value


def _pointer(parent: str, token: str) -> str:
    encoded = token.replace("~", "~0").replace("/", "~1")
    return f"{parent}/{encoded}" if parent else f"/{encoded}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProviderSchemaError(message)


def _validate_node(
    node: Any,
    *,
    pointer: str,
    supported_keywords: set[str],
    unsupported_keywords: set[str],
    supported_types: set[str],
) -> int:
    _require(isinstance(node, Mapping), f"schema node is not an object at {pointer or '/'}")
    keyword_count = 0
    for keyword in node:
        location = _pointer(pointer, str(keyword))
        if keyword in unsupported_keywords:
            raise ProviderSchemaError(f"known unsupported provider keyword at {location}: {keyword}")
        if keyword not in supported_keywords:
            raise ProviderSchemaError(f"keyword outside closed-world provider policy at {location}: {keyword}")
        keyword_count += 1

    schema_type = node.get("type")
    _require(isinstance(schema_type, str), f"schema type missing or invalid at {pointer or '/'}")
    _require(schema_type in supported_types, f"unsupported schema type at {_pointer(pointer, 'type')}: {schema_type}")

    if "$schema" in node:
        _require(pointer == "", f"$schema is permitted only at the root: {_pointer(pointer, '$schema')}")
        _require(node["$schema"] == EXPECTED_DIALECT, "response schema dialect mismatch")

    if schema_type == "object":
        properties = node.get("properties")
        required = node.get("required")
        _require(isinstance(properties, Mapping), f"object properties missing at {pointer or '/'}")
        _require(
            node.get("additionalProperties") is False,
            f"object must set additionalProperties=false at {pointer or '/'}",
        )
        _require(
            isinstance(required, list) and all(isinstance(item, str) for item in required),
            f"object required list missing or invalid at {pointer or '/'}",
        )
        _require(set(required) == set(properties), f"required/properties mismatch at {pointer or '/'}")
        _require(len(required) == len(set(required)), f"duplicate required property at {pointer or '/'}")
        for property_name, child in properties.items():
            _require(isinstance(property_name, str), f"non-string property name at {pointer or '/'}")
            keyword_count += _validate_node(
                child,
                pointer=_pointer(_pointer(pointer, "properties"), property_name),
                supported_keywords=supported_keywords,
                unsupported_keywords=unsupported_keywords,
                supported_types=supported_types,
            )

    if schema_type == "array":
        _require("items" in node, f"array items missing at {pointer or '/'}")
        keyword_count += _validate_node(
            node["items"],
            pointer=_pointer(pointer, "items"),
            supported_keywords=supported_keywords,
            unsupported_keywords=unsupported_keywords,
            supported_types=supported_types,
        )
        for bound in ("minItems", "maxItems"):
            if bound in node:
                value = node[bound]
                _require(
                    isinstance(value, int) and not isinstance(value, bool) and value >= 0,
                    f"invalid {bound} at {_pointer(pointer, bound)}",
                )
        if "minItems" in node and "maxItems" in node:
            _require(node["minItems"] <= node["maxItems"], f"array bounds conflict at {pointer or '/'}")

    if "minimum" in node:
        _require(
            schema_type in {"integer", "number"}
            and isinstance(node["minimum"], (int, float))
            and not isinstance(node["minimum"], bool),
            f"invalid minimum at {_pointer(pointer, 'minimum')}",
        )
    return keyword_count


def validate_provider_schema(
    schema: Mapping[str, Any], *, policy: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    active = dict(policy) if policy is not None else load_policy()
    if active.get("admitted_profile_id") != EXPECTED_PROFILE_ID:
        raise ProviderSchemaError("provider schema policy profile mismatch")
    supported_keywords = set(active["supported_keywords"])
    unsupported_keywords = set(active["known_unsupported_keywords"])
    keyword_count = _validate_node(
        schema,
        pointer="",
        supported_keywords=supported_keywords,
        unsupported_keywords=unsupported_keywords,
        supported_types=set(active["supported_type_values"]),
    )
    return {
        "status": "provider_schema_policy_admissible",
        "policy_id": active["policy_id"],
        "admitted_profile_id": active["admitted_profile_id"],
        "keyword_count": keyword_count,
    }

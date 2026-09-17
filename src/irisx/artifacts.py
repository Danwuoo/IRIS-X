"""Digest-bound supporting artifacts used by contracts and packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical import digest_value, read_json, write_json
from .contracts import SCHEMA_VERSION, _digest, _exact, _identifier, _object, _version
from .errors import ValidationError


def make_artifact(kind: str, artifact_id: str, version: str, payload: Any) -> dict[str, Any]:
    if not isinstance(kind, str) or not kind.startswith("irisx/"):
        raise ValidationError("$.schema: supporting artifact kind must start with 'irisx/'")
    _identifier(artifact_id, "$.artifact_id")
    _version(version, "$.version")
    unsigned = {
        "schema": kind,
        "schema_version": SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "version": version,
        "payload": payload,
    }
    return {**unsigned, "content_digest": digest_value(unsigned)}


def validate_artifact(value: Any, *, kind: str | None = None) -> dict[str, Any]:
    obj = _object(value, "$")
    _exact(obj, {"schema", "schema_version", "artifact_id", "version", "content_digest", "payload"}, "$")
    if not isinstance(obj["schema"], str) or not obj["schema"].startswith("irisx/"):
        raise ValidationError("$.schema: invalid supporting artifact kind")
    if kind is not None and obj["schema"] != kind:
        raise ValidationError(f"$.schema: expected {kind!r}, got {obj['schema']!r}")
    if obj["schema_version"] != SCHEMA_VERSION:
        raise ValidationError(f"$.schema_version: unsupported version {obj['schema_version']!r}")
    _identifier(obj["artifact_id"], "$.artifact_id")
    _version(obj["version"], "$.version")
    _digest(obj["content_digest"], "$.content_digest")
    unsigned = {key: obj[key] for key in ("schema", "schema_version", "artifact_id", "version", "payload")}
    expected = digest_value(unsigned)
    if obj["content_digest"] != expected:
        raise ValidationError(f"$.content_digest: digest mismatch; expected {expected}")
    return obj


def artifact_ref(value: dict[str, Any]) -> dict[str, str]:
    value = validate_artifact(value)
    return {
        "kind": value["schema"],
        "artifact_id": value["artifact_id"],
        "version": value["version"],
        "content_digest": value["content_digest"],
    }


def load_artifact(path: Path, *, kind: str | None = None) -> dict[str, Any]:
    return validate_artifact(read_json(path), kind=kind)


def write_artifact(path: Path, value: dict[str, Any]) -> None:
    validate_artifact(value)
    write_json(path, value)

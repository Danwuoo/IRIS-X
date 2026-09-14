#!/usr/bin/env python3
"""Shared deterministic helpers for the D1a qualification substrate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = PACKAGE_ROOT / "submission-schemas"
DEFINITION_ROOT = PACKAGE_ROOT / "definition"
BASE_SCHEMA_PATH = SCHEMA_ROOT / "custodian-attestation.schema.json"
COORDINATOR_ID = "d1a-coordinator-2026-09-14-sol-high"

ROLE_SCHEMA_PATHS = {
    "task_oracle": SCHEMA_ROOT / "task-oracle-bundle.schema.json",
    "authority_policy": SCHEMA_ROOT / "authority-policy-bundle.schema.json",
    "semantic_verifier": SCHEMA_ROOT / "semantic-verifier-bundle.schema.json",
    "calibration": SCHEMA_ROOT / "calibration-bundle.schema.json",
    "analysis": SCHEMA_ROOT / "analysis-bundle.schema.json",
}


class D1aValidationError(RuntimeError):
    """Raised when a deterministic D1a input cannot be safely interpreted."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise D1aValidationError(f"cannot load JSON {path}: {exc}") from exc


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def bundle_manifest_sha256(bundle: dict[str, Any]) -> str:
    normalized = json.loads(json.dumps(bundle))
    seal = normalized.get("seal")
    if isinstance(seal, dict):
        seal.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(normalized))


def schema_validator(schema_path: Path) -> Draft202012Validator:
    base = load_json(BASE_SCHEMA_PATH)
    schema = load_json(schema_path)
    registry = Registry().with_resource(
        base["$id"], Resource.from_contents(base)
    )
    return Draft202012Validator(
        schema, registry=registry, format_checker=FormatChecker()
    )


def schema_errors(document: Any, schema_path: Path) -> list[str]:
    errors = sorted(
        schema_validator(schema_path).iter_errors(document),
        key=lambda error: ([str(part) for part in error.absolute_path], error.message),
    )
    rendered: list[str] = []
    for error in errors:
        pointer = "/" + "/".join(str(part) for part in error.absolute_path)
        rendered.append(f"{pointer}: {error.message}")
    return rendered


def validate_all_schemas() -> list[str]:
    errors: list[str] = []
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = load_json(path)
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # jsonschema exposes several schema error classes
            errors.append(f"{path.name}: {exc}")
    return errors


def safe_asset_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise D1aValidationError("asset path must be a non-empty string")
    if "\\" in value:
        raise D1aValidationError(f"asset path must use POSIX separators: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise D1aValidationError(f"unsafe or ambiguous asset path: {value!r}")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise D1aValidationError(f"asset path escapes or is missing: {value!r}") from exc
    if not resolved.is_file():
        raise D1aValidationError(f"asset path is not a regular file: {value!r}")
    return resolved


def unique_paths_casefold(values: Iterable[str]) -> bool:
    materialized = [value.casefold() for value in values]
    return len(materialized) == len(set(materialized))


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for key, child in value.items():
            result.append(str(key))
            result.extend(flatten_strings(child))
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            result.extend(flatten_strings(child))
        return result
    return []


def digest_record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_path(path),
        "bytes": path.stat().st_size,
    }

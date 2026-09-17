"""Closed-world loading and reference resolution for local P1 bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import validate_artifact
from .canonical import read_json
from .contracts import CONTRACT_TYPES, VersionedContract, validate_ref
from .errors import ValidationError


Document = VersionedContract | dict[str, Any]


def document_ref(document: Document) -> dict[str, str]:
    if isinstance(document, VersionedContract):
        return document.ref()
    return {
        "kind": document["schema"],
        "artifact_id": document["artifact_id"],
        "version": document["version"],
        "content_digest": document["content_digest"],
    }


def load_document(path: Path) -> Document:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: document must be an object")
    schema = value.get("schema")
    contract_type = CONTRACT_TYPES.get(schema)
    if contract_type is not None:
        return contract_type.from_dict(value)
    return validate_artifact(value)


def load_bundle(root: Path) -> dict[tuple[str, str, str, str], Document]:
    if not root.is_dir():
        raise ValidationError(f"bundle directory does not exist: {root}")
    index: dict[tuple[str, str, str, str], Document] = {}
    paths = sorted(root.rglob("*.json"), key=lambda item: item.as_posix())
    if not paths:
        raise ValidationError(f"bundle contains no JSON documents: {root}")
    for path in paths:
        document = load_document(path)
        ref = document_ref(document)
        key = (ref["kind"], ref["artifact_id"], ref["version"], ref["content_digest"])
        if key in index:
            raise ValidationError(f"duplicate document identity in bundle: {ref}")
        index[key] = document
    return index


def resolve_ref(index: dict[tuple[str, str, str, str], Document], ref: Any, path: str) -> Document:
    ref = validate_ref(ref, path)
    key = (ref["kind"], ref["artifact_id"], ref["version"], ref["content_digest"])
    try:
        return index[key]
    except KeyError as exc:
        raise ValidationError(f"{path}: referenced evidence is missing from bundle") from exc


def require_contract(document: Document, expected: type[VersionedContract], path: str) -> VersionedContract:
    if not isinstance(document, expected):
        raise ValidationError(f"{path}: expected {expected.SCHEMA}")
    return document

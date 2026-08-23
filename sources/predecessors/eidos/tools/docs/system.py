from __future__ import annotations

import json
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from yaml.tokens import AliasToken, AnchorToken


MANIFEST_PATH = "eidos.yaml"
MANIFEST_SCHEMA_PATH = "docs/schema/eidos.schema.json"
RELATION_NAMES = ("depends_on", "supersedes", "informed_by")


class DocumentSystemError(ValueError):
    pass


class StrictSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise DocumentSystemError(f"unhashable YAML mapping key: {key!r}") from exc
            if duplicate:
                raise DocumentSystemError(f"duplicate YAML key: {key}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    StrictSafeLoader.construct_mapping,
)


def load_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocumentSystemError(f"cannot read YAML file {path}: {exc}") from exc
    try:
        for token in yaml.scan(text):
            if isinstance(token, (AliasToken, AnchorToken)):
                raise DocumentSystemError(f"YAML anchors and aliases are not allowed: {path}")
        data = yaml.load(text, Loader=StrictSafeLoader)
    except yaml.YAMLError as exc:
        raise DocumentSystemError(f"invalid YAML in {path}: {exc}") from exc
    if data is None:
        raise DocumentSystemError(f"YAML file is empty: {path}")
    return data


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DocumentSystemError(f"cannot read JSON file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DocumentSystemError(
            f"invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc


def schema_errors(instance: Any, schema: Any, label: str) -> list[str]:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return [f"invalid JSON Schema for {label}: {exc.message}"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(instance),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{label} at {location}: {error.message}")
    return errors


def schema_definition_errors(schema: Any, label: str) -> list[str]:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return [f"invalid JSON Schema for {label}: {exc.message}"]
    return []


def repo_path(root: Path, value: str, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise DocumentSystemError(f"{label} must be a non-empty repository-relative path")
    if "\\" in value:
        raise DocumentSystemError(f"{label} must use '/' separators: {value}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in (".", "..") for part in pure.parts):
        raise DocumentSystemError(f"{label} must be a normalized repository-relative path: {value}")
    resolved_root = root.resolve()
    resolved = (resolved_root / Path(*pure.parts)).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise DocumentSystemError(f"{label} resolves outside the repository: {value}")
    return resolved


def _cycle_nodes(graph: dict[str, list[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    cycles: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            start = stack.index(node)
            cycles.update(stack[start:])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for target in graph.get(node, []):
            if target in graph:
                visit(target)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return sorted(cycles)


def _expected_authority(record: dict[str, Any]) -> str:
    kind = record["kind"]
    status = record["status"]
    if (kind, status) in {
        ("governance", "active"),
        ("project", "active"),
        ("specification", "active"),
        ("decision", "accepted"),
    }:
        return "normative"
    return "non_normative"


def validate_sources(root: Path) -> tuple[dict[str, Any] | None, list[tuple[Path, dict[str, Any]]], list[str]]:
    root = root.resolve()
    errors: list[str] = []
    records: list[tuple[Path, dict[str, Any]]] = []

    try:
        manifest = load_yaml(root / MANIFEST_PATH)
        manifest_schema = load_json(root / MANIFEST_SCHEMA_PATH)
    except DocumentSystemError as exc:
        return None, records, [str(exc)]

    errors.extend(schema_errors(manifest, manifest_schema, MANIFEST_PATH))
    if errors or not isinstance(manifest, dict):
        return manifest if isinstance(manifest, dict) else None, records, sorted(errors)

    documentation = manifest["documentation"]
    try:
        records_dir = repo_path(root, documentation["records_directory"], "records_directory")
        document_schema_path = repo_path(root, documentation["document_schema"], "document_schema")
        document_schema = load_json(document_schema_path)
    except (KeyError, DocumentSystemError) as exc:
        errors.append(str(exc))
        return manifest, records, sorted(errors)

    errors.extend(schema_definition_errors(document_schema, documentation["document_schema"]))
    if errors:
        return manifest, records, sorted(errors)

    if not records_dir.is_dir():
        errors.append(f"records directory not found: {records_dir}")
        return manifest, records, sorted(errors)

    for path in sorted(records_dir.glob(documentation["record_pattern"])):
        try:
            record = load_yaml(path)
        except DocumentSystemError as exc:
            errors.append(str(exc))
            continue
        relative = path.relative_to(root).as_posix()
        record_errors = schema_errors(record, document_schema, relative)
        errors.extend(record_errors)
        if not record_errors and isinstance(record, dict):
            records.append((path, record))

    ids = [record["id"] for _, record in records]
    for document_id, count in sorted(Counter(ids).items()):
        if count > 1:
            errors.append(f"duplicate document ID: {document_id}")

    known_ids = set(ids)
    by_id = {record["id"]: record for _, record in records}
    for path, record in records:
        relative = path.relative_to(root).as_posix()
        expected_name = f"{record['id']}.yaml"
        if path.name != expected_name:
            errors.append(f"record filename must be {expected_name}: {relative}")
        expected_authority = _expected_authority(record)
        if record["authority"] != expected_authority:
            errors.append(
                f"{record['id']} authority must be {expected_authority} for "
                f"{record['kind']} status {record['status']}"
            )
        for relation_name in RELATION_NAMES:
            targets = record["relations"][relation_name]
            if targets != sorted(targets):
                errors.append(f"{record['id']} relations.{relation_name} must be sorted")
            for target in targets:
                if target == record["id"]:
                    errors.append(f"{record['id']} relations.{relation_name} cannot reference itself")
                elif target not in known_ids:
                    errors.append(
                        f"{record['id']} relations.{relation_name} references missing document {target}"
                    )
        for target in record["relations"]["supersedes"]:
            target_record = by_id.get(target)
            if target_record and target_record["kind"] != record["kind"]:
                errors.append(f"{record['id']} may only supersede the same document kind: {target}")

    for relation_name in ("depends_on", "supersedes"):
        graph = {
            record["id"]: list(record["relations"][relation_name])
            for _, record in records
        }
        cycle_nodes = _cycle_nodes(graph)
        if cycle_nodes:
            errors.append(f"{relation_name} cycle contains: {', '.join(cycle_nodes)}")

    return manifest, records, sorted(errors)


def expected_index(root: Path, manifest: dict[str, Any], records: Iterable[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    root = root.resolve()
    documentation = manifest["documentation"]
    generated_from = (
        f"{documentation['records_directory']}/{documentation['record_pattern']}"
    )
    entries = []
    for path, record in sorted(records, key=lambda item: item[1]["id"]):
        entries.append(
            {
                "id": record["id"],
                "kind": record["kind"],
                "status": record["status"],
                "title": record["title"],
                "language": record["language"],
                "authority": record["authority"],
                "summary": record["summary"],
                "path": path.relative_to(root).as_posix(),
                "relations": record["relations"],
            }
        )
    return {"schema_version": 1, "generated_from": generated_from, "documents": entries}


def validate_repository(root: Path) -> list[str]:
    root = root.resolve()
    manifest, records, errors = validate_sources(root)
    if errors or manifest is None:
        return errors

    documentation = manifest["documentation"]
    try:
        index_path = repo_path(root, documentation["index"], "index")
        index_schema_path = repo_path(root, documentation["index_schema"], "index_schema")
        index = load_json(index_path)
        index_schema = load_json(index_schema_path)
    except DocumentSystemError as exc:
        return [str(exc)]

    errors.extend(schema_errors(index, index_schema, documentation["index"]))
    expected = expected_index(root, manifest, records)
    if index != expected:
        errors.append(
            f"{documentation['index']} is stale; run: {documentation['commands']['build_index']}"
        )
    return sorted(errors)


def write_index(root: Path) -> Path:
    root = root.resolve()
    manifest, records, errors = validate_sources(root)
    if errors or manifest is None:
        raise DocumentSystemError("cannot build index:\n" + "\n".join(f"- {error}" for error in errors))
    index = expected_index(root, manifest, records)
    index_path = repo_path(root, manifest["documentation"]["index"], "index")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index_path

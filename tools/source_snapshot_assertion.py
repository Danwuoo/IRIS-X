"""Minimal registered source-snapshot assertion for local experiment startup."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OID_RE = re.compile(r"^[0-9a-f]{40}$")


class SourceSnapshotAssertionError(ValueError):
    """A fail-closed registry resolution or Git tree assertion failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SourceSnapshotIdentity:
    source_id: str
    source_path: str
    snapshot_id: str
    registered_tree_oid: str
    observed_tree_oid: str


def _is_within(path: Path, boundary: Path) -> bool:
    resolved = path.resolve()
    root = boundary.resolve()
    return resolved == root or root in resolved.parents


def _relative_source_path(repository_root: Path, value: Any, source_id: str) -> str:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise SourceSnapshotAssertionError("source_path_invalid", f"registered path is invalid for {source_id}")
    path = (repository_root / value).resolve()
    if not _is_within(path, repository_root / "sources"):
        raise SourceSnapshotAssertionError(
            "source_path_outside_boundary",
            f"registered path is outside sources/ for {source_id}: {value}",
        )
    return path.relative_to(repository_root.resolve()).as_posix()


def _registry_records(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or document.get("schema_version") != 2:
        raise SourceSnapshotAssertionError("registry_schema_invalid", "registry schema_version must be 2")
    if document.get("registry_type") != "iris-x-corpus-sources":
        raise SourceSnapshotAssertionError("registry_type_invalid", "unexpected registry_type")
    records = document.get("records")
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise SourceSnapshotAssertionError("registry_records_invalid", "registry records must be objects")
    return records


def _snapshot_owners(records: list[dict[str, Any]], snapshot_id: str) -> list[str]:
    owners: list[str] = []
    for record in records:
        snapshots = record.get("snapshots")
        if isinstance(snapshots, list) and any(
            isinstance(snapshot, dict) and snapshot.get("id") == snapshot_id for snapshot in snapshots
        ):
            owners.append(str(record.get("id")))
    return owners


def resolve_registered_snapshot(
    repository_root: Path,
    registry_document: Any,
    source_id: str,
    snapshot_id: str,
) -> tuple[str, str]:
    """Return registered source path and tree OID after active-relation checks."""
    records = _registry_records(registry_document)
    sources = [record for record in records if record.get("id") == source_id]
    if not sources:
        raise SourceSnapshotAssertionError("unknown_source_id", f"source_id is not registered: {source_id}")
    if len(sources) != 1:
        raise SourceSnapshotAssertionError("duplicate_source_id", f"source_id is duplicated: {source_id}")
    source = sources[0]
    if source.get("record_status") != "active":
        raise SourceSnapshotAssertionError("source_not_active", f"source record is not active: {source_id}")
    snapshots = source.get("snapshots")
    if not isinstance(snapshots, list):
        raise SourceSnapshotAssertionError("snapshots_invalid", f"snapshots are invalid for {source_id}")
    matches = [snapshot for snapshot in snapshots if isinstance(snapshot, dict) and snapshot.get("id") == snapshot_id]
    if not matches:
        owners = _snapshot_owners(records, snapshot_id)
        if owners:
            raise SourceSnapshotAssertionError(
                "snapshot_source_relationship_mismatch",
                f"snapshot_id belongs to {owners[0]}, not {source_id}",
            )
        raise SourceSnapshotAssertionError("unknown_snapshot_id", f"snapshot_id is not registered: {snapshot_id}")
    if len(matches) != 1:
        raise SourceSnapshotAssertionError("duplicate_snapshot_id", f"snapshot_id is duplicated: {snapshot_id}")
    snapshot = matches[0]
    if source.get("active_snapshot_id") != snapshot_id or snapshot.get("status") != "active":
        raise SourceSnapshotAssertionError(
            "active_snapshot_relationship_mismatch",
            f"snapshot is not active for source: {source_id} / {snapshot_id}",
        )
    if snapshot.get("kind") != "git-tree":
        raise SourceSnapshotAssertionError("snapshot_kind_invalid", "registered snapshot kind must be git-tree")
    tree_oid = snapshot.get("tree_oid")
    if not isinstance(tree_oid, str) or not OID_RE.fullmatch(tree_oid):
        raise SourceSnapshotAssertionError("registered_tree_oid_invalid", "registered tree_oid must be lowercase 40-hex")
    return _relative_source_path(repository_root, source.get("path"), source_id), tree_oid


def git_tree_oid(repository_root: Path, code_commit: str, source_path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"{code_commit}:{source_path}"],
        cwd=repository_root,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise SourceSnapshotAssertionError(
            "git_tree_resolution_failed",
            f"cannot resolve source tree at code commit: {completed.stderr.strip()}",
        )
    oid = completed.stdout.strip()
    if not OID_RE.fullmatch(oid):
        raise SourceSnapshotAssertionError("observed_tree_oid_invalid", f"Git returned an invalid tree OID: {oid}")
    return oid


def assert_registered_source_snapshot(
    repository_root: Path,
    registry_path: Path,
    source_id: str,
    snapshot_id: str,
    code_commit: str,
) -> SourceSnapshotIdentity:
    """Resolve the registered active snapshot and assert its Git tree exactly."""
    try:
        registry_document = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceSnapshotAssertionError("registry_read_failed", f"cannot read registry: {exc}") from exc
    source_path, registered_oid = resolve_registered_snapshot(
        repository_root.resolve(), registry_document, source_id, snapshot_id
    )
    observed_oid = git_tree_oid(repository_root.resolve(), code_commit, source_path)
    if observed_oid != registered_oid:
        raise SourceSnapshotAssertionError(
            "tree_oid_mismatch",
            f"observed tree OID {observed_oid} does not equal registered tree OID {registered_oid}",
        )
    return SourceSnapshotIdentity(source_id, source_path, snapshot_id, registered_oid, observed_oid)

#!/usr/bin/env python3
"""Check IRIS-X corpus inventory, provenance, boundaries, and authored links."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "corpus" / "sources.yaml"
ARTIFACTS = ROOT / "corpus" / "artifacts.yaml"

ID_RE = re.compile(r"^[a-z][a-z0-9.-]*$")
OID_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_REF_RE = re.compile(r"^([0-9a-f]{40}):(.+)$")

CLASSIFICATIONS = {"predecessor", "external-reference"}
LICENSE_STATUSES = {"identified", "conflicting-evidence", "unknown"}
RECORD_STATUSES = {"active", "deprecated"}
MODIFICATION_STATUSES = {"none-known", "documented", "unknown"}
SOURCE_VERIFICATION = {"registered-only", "local-snapshot-fingerprinted", "upstream-verified"}
ARTIFACT_VERIFICATION = {
    "registered-only",
    "local-fingerprinted",
    "primary-artifact-byte-verified",
}
REVISION_KINDS = {"commit", "tag", "release", "Unknown"}
IDENTITY_STATUSES = {
    "Unknown",
    "unclear",
    "verified-remote-title-match",
    "verified-primary-metadata",
}
SNAPSHOT_EVENTS = {"initial-import", "refresh", "migration-audit", "retirement"}
CLASSIFICATION_PREFIX = {
    "predecessor": "sources/predecessors/",
    "external-reference": "sources/external/",
}
ALLOWED_TOP_LEVEL_FILES = {".gitattributes", ".gitignore", "AGENTS.md", "README.md"}
ALLOWED_TOP_LEVEL_DIRS = {
    ".git",
    "corpus",
    "docs",
    "experiments",
    "references",
    "research",
    "sources",
    "tools",
}

SOURCE_REQUIRED = {
    "id",
    "path",
    "original_import_path",
    "current_path",
    "record_status",
    "classification",
    "research_role",
    "upstream_url",
    "upstream_url_status",
    "upstream_url_evidence",
    "upstream_revision_kind",
    "upstream_revision",
    "declared_version",
    "declared_version_evidence",
    "acquisition",
    "license",
    "local_modifications",
    "verification_status",
    "active_snapshot_id",
    "snapshots",
    "unresolved_questions",
}

ARTIFACT_REQUIRED = {
    "id",
    "path",
    "original_import_path",
    "current_path",
    "record_status",
    "artifact_type",
    "title",
    "related_source_id",
    "publication",
    "publication_identity_evidence",
    "license",
    "local_modifications",
    "verification_status",
    "active_snapshot_id",
    "snapshots",
    "fingerprint",
    "unresolved_questions",
}


def run_git(root: Path, args: list[str], env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def load_json_yaml(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return {}, [f"{path.name}: registry file does not exist"]
    except (OSError, UnicodeError) as exc:
        return {}, [f"{path.name}: cannot read registry: {exc}"]
    except json.JSONDecodeError as exc:
        return {}, [f"{path.name}: invalid JSON-compatible YAML: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{path.name}: top-level value must be an object"]
    return data, []


def safe_relative_path(value: Any, label: str) -> tuple[PurePosixPath | None, list[str]]:
    if not isinstance(value, str) or not value.strip():
        return None, [f"{label}: must be a non-empty relative path"]
    normalized = value.replace("\\", "/").strip("/")
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        return None, [f"{label}: unsafe path {value!r}"]
    return candidate, []


def check_path_exists(root: Path, value: Any, label: str, errors: list[str]) -> None:
    candidate, path_errors = safe_relative_path(value, label)
    errors.extend(path_errors)
    if candidate is not None and not (root / Path(*candidate.parts)).exists():
        errors.append(f"{label}: evidence path does not exist: {value}")


def check_evidence_list(
    root: Path,
    values: Any,
    label: str,
    errors: list[str],
    *,
    allow_empty: bool = True,
) -> None:
    if not isinstance(values, list):
        errors.append(f"{label}: must be a list")
        return
    if not values and not allow_empty:
        errors.append(f"{label}: must contain at least one evidence path")
        return
    for index, value in enumerate(values):
        check_path_exists(root, value, f"{label}[{index}]", errors)


def check_license(license_value: Any, label: str, root: Path, errors: list[str]) -> None:
    if not isinstance(license_value, dict):
        errors.append(f"{label}: must be an object")
        return
    status = license_value.get("status")
    if status not in LICENSE_STATUSES:
        errors.append(f"{label}.status: invalid value {status!r}")

    spdx = license_value.get("spdx")
    if not isinstance(spdx, str) or not spdx.strip():
        errors.append(f"{label}.spdx: must be a non-empty string")

    evidence = license_value.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append(f"{label}.evidence: must be a list")
        return
    if status == "identified":
        if spdx in {"", "Unknown", "Conflicting evidence"}:
            errors.append(f"{label}: identified license needs a concrete SPDX identifier")
        check_evidence_list(root, evidence, f"{label}.evidence", errors, allow_empty=False)
    elif status == "conflicting-evidence":
        if spdx != "Conflicting evidence":
            errors.append(f"{label}.spdx: conflicting-evidence requires 'Conflicting evidence'")
        check_evidence_list(root, evidence, f"{label}.evidence", errors, allow_empty=False)
        if len(set(evidence)) < 2:
            errors.append(f"{label}.evidence: conflicting-evidence requires two distinct paths")
    elif spdx != "Unknown":
        errors.append(f"{label}.spdx: unknown license must use 'Unknown'")
    elif evidence:
        errors.append(f"{label}.evidence: unknown license should not claim evidence")


def check_snapshot_common(snapshot: Any, label: str, errors: list[str]) -> tuple[str, str]:
    required = {"id", "kind", "status", "event", "source_ref", "acquired_at_commit", "evidence_paths"}
    missing = sorted(required - snapshot.keys())
    if missing:
        errors.append(f"{label}: missing fields: {', '.join(missing)}")
        return "", ""
    if snapshot["status"] not in {"active", "superseded", "retired"}:
        errors.append(f"{label}.status: invalid value {snapshot['status']!r}")
    if snapshot["event"] not in SNAPSHOT_EVENTS:
        errors.append(f"{label}.event: invalid value {snapshot['event']!r}")
    acquired = snapshot["acquired_at_commit"]
    if not isinstance(acquired, str) or not OID_RE.fullmatch(acquired):
        errors.append(f"{label}.acquired_at_commit: must be a 40-character lowercase OID")
    match = SOURCE_REF_RE.fullmatch(str(snapshot.get("source_ref", "")))
    if match is None:
        errors.append(f"{label}.source_ref: must be '<40-character commit>:<relative-path>'")
        return "", ""
    _, captured_path = match.groups()
    _, path_errors = safe_relative_path(captured_path, f"{label}.source_ref.path")
    errors.extend(path_errors)
    return str(snapshot.get("id", "")), captured_path


def check_source_record(record: Any, root: Path, context: ValidationContext, errors: list[str]) -> None:
    if not isinstance(record, dict):
        errors.append("sources.records[]: each record must be an object")
        return
    record_id = record.get("id")
    label = f"source {record_id!s}"
    missing = sorted(SOURCE_REQUIRED - record.keys())
    if missing:
        errors.append(f"{label}: missing fields: {', '.join(missing)}")
        return
    if not isinstance(record_id, str) or not ID_RE.fullmatch(record_id):
        errors.append(f"{label}: invalid stable ID {record_id!r}")
        return
    if record_id in context.record_ids:
        errors.append(f"{label}: duplicate stable ID")
    else:
        context.record_ids.add(record_id)

    original_path, original_errors = safe_relative_path(
        record["original_import_path"], f"{label}.original_import_path"
    )
    errors.extend(original_errors)
    current_path, current_errors = safe_relative_path(record["current_path"], f"{label}.current_path")
    errors.extend(current_errors)
    path_value, path_errors = safe_relative_path(record["path"], f"{label}.path")
    errors.extend(path_errors)

    classification = record["classification"]
    if classification not in CLASSIFICATIONS:
        errors.append(f"{label}.classification: invalid value {classification!r}")
    elif (
        original_path is not None
        and len(original_path.parts) != 1
        and original_path.as_posix() != record["original_import_path"]
    ):
        errors.append(f"{label}.original_import_path: initial import leaf expected")
    if classification in CLASSIFICATION_PREFIX and current_path is not None:
        prefix = CLASSIFICATION_PREFIX[classification]
        if not current_path.as_posix().startswith(prefix):
            errors.append(f"{label}.current_path: violates boundary {prefix}")
        if len(current_path.parts) != 3:
            errors.append(f"{label}.current_path: imported leaf names must remain one level deep")
    if path_value != current_path:
        errors.append(f"{label}.path: must equal current_path")

    if record["record_status"] not in RECORD_STATUSES:
        errors.append(f"{label}.record_status: invalid value {record['record_status']!r}")

    url = record["upstream_url"]
    url_status = record["upstream_url_status"]
    if url is None:
        if url_status != "Unknown":
            errors.append(f"{label}.upstream_url_status: null URL requires Unknown")
    elif not isinstance(url, str) or not url.startswith(("http://", "https://")):
        errors.append(f"{label}.upstream_url: must be null or HTTP(S)")
    check_evidence_list(
        root,
        record["upstream_url_evidence"],
        f"{label}.upstream_url_evidence",
        errors,
        allow_empty=url is None,
    )

    kind = record["upstream_revision_kind"]
    revision = record["upstream_revision"]
    if kind not in REVISION_KINDS:
        errors.append(f"{label}.upstream_revision_kind: invalid value {kind!r}")
    if kind == "Unknown" and revision != "Unknown":
        errors.append(f"{label}.upstream_revision: Unknown kind requires literal Unknown")
    if kind == "commit" and (not isinstance(revision, str) or not OID_RE.fullmatch(revision)):
        errors.append(f"{label}.upstream_revision: commits require a lowercase 40-character OID")

    declared = record["declared_version"]
    if not isinstance(declared, str) or not declared.strip():
        errors.append(f"{label}.declared_version: must be a non-empty string or Unknown")
    check_evidence_list(
        root,
        record["declared_version_evidence"],
        f"{label}.declared_version_evidence",
        errors,
        allow_empty=declared == "Unknown",
    )

    acquisition = record["acquisition"]
    if not isinstance(acquisition, dict):
        errors.append(f"{label}.acquisition: must be an object")
    else:
        if not isinstance(acquisition.get("method"), str) or not acquisition["method"]:
            errors.append(f"{label}.acquisition.method: must be a non-empty string or Unknown")
        subject = acquisition.get("commit_subject")
        if not isinstance(subject, str) or not subject:
            errors.append(f"{label}.acquisition.commit_subject: must be a non-empty string")
        check_evidence_list(
            root,
            acquisition.get("evidence_paths"),
            f"{label}.acquisition.evidence_paths",
            errors,
            allow_empty=False,
        )

    check_license(record["license"], f"{label}.license", root, errors)
    if record["local_modifications"] not in MODIFICATION_STATUSES:
        errors.append(f"{label}.local_modifications: invalid value")
    if record["verification_status"] not in SOURCE_VERIFICATION:
        errors.append(f"{label}.verification_status: invalid value")
    questions = record["unresolved_questions"]
    if not questions or not all(isinstance(item, str) and item for item in questions):
        errors.append(f"{label}.unresolved_questions: must be a non-empty string list")

    snapshots = record["snapshots"]
    active_id = record["active_snapshot_id"]
    active_seen = False
    active_snapshot: dict[str, Any] | None = None
    if not isinstance(snapshots, list) or not snapshots:
        errors.append(f"{label}.snapshots: append-only history requires at least one entry")
    else:
        for index, snapshot in enumerate(snapshots):
            snapshot_label = f"{label}.snapshots[{index}]"
            if not isinstance(snapshot, dict):
                errors.append(f"{snapshot_label}: must be an object")
                continue
            snapshot_id, _ = check_snapshot_common(snapshot, snapshot_label, errors)
            if snapshot["kind"] != "git-tree":
                errors.append(f"{snapshot_label}.kind: source snapshots require git-tree")
            tree_oid = snapshot.get("tree_oid")
            if not isinstance(tree_oid, str) or not OID_RE.fullmatch(tree_oid):
                errors.append(f"{snapshot_label}.tree_oid: must be a lowercase 40-character OID")
            check_evidence_list(
                root,
                snapshot.get("evidence_paths"),
                f"{snapshot_label}.evidence_paths",
                errors,
                allow_empty=False,
            )
            if not isinstance(snapshot_id, str) or not ID_RE.fullmatch(snapshot_id):
                errors.append(f"{snapshot_label}.id: invalid snapshot ID")
            elif snapshot_id in context.snapshot_ids:
                errors.append(f"{snapshot_label}: duplicate snapshot ID")
            else:
                context.snapshot_ids.add(snapshot_id)
            if snapshot_id == active_id:
                active_seen = True
                active_snapshot = snapshot
    if active_id is None or not isinstance(active_id, str) or not active_seen:
        errors.append(f"{label}.active_snapshot_id: must identify a row-local snapshot")
        active_snapshot = None

    target = root / Path(*(current_path.parts if current_path else ()))
    if target.exists() and not target.is_dir():
        errors.append(f"{label}.current_path: expected a directory")
    context.source_paths[current_path.as_posix() if current_path else ""] = active_snapshot


def check_artifact_record(
    record: Any,
    root: Path,
    context: ValidationContext,
    errors: list[str],
) -> None:
    if not isinstance(record, dict):
        errors.append("artifacts.records[]: each record must be an object")
        return
    record_id = record.get("id")
    label = f"artifact {record_id!s}"
    missing = sorted(ARTIFACT_REQUIRED - record.keys())
    if missing:
        errors.append(f"{label}: missing fields: {', '.join(missing)}")
        return
    if not isinstance(record_id, str) or not ID_RE.fullmatch(record_id):
        errors.append(f"{label}: invalid stable ID {record_id!r}")
        return
    if record_id in context.record_ids:
        errors.append(f"{label}: duplicate stable ID")
    else:
        context.record_ids.add(record_id)

    related = record["related_source_id"]
    if related is not None and (not isinstance(related, str) or related not in context.source_record_ids):
        errors.append(f"{label}.related_source_id: unknown source relationship")

    original_path, original_errors = safe_relative_path(
        record["original_import_path"], f"{label}.original_import_path"
    )
    errors.extend(original_errors)
    current_path, current_errors = safe_relative_path(record["current_path"], f"{label}.current_path")
    errors.extend(current_errors)
    path_value, path_errors = safe_relative_path(record["path"], f"{label}.path")
    errors.extend(path_errors)
    if current_path is not None and (
        len(current_path.parts) != 3 or current_path.parts[:2] != ("references", "papers")
    ):
        errors.append(f"{label}.current_path: artifacts must live at references/papers/<name>")
    if original_path is not None and len(original_path.parts) != 1:
        errors.append(f"{label}.original_import_path: initial import filename expected")
    if path_value != current_path:
        errors.append(f"{label}.path: must equal current_path")
    if record["record_status"] not in RECORD_STATUSES:
        errors.append(f"{label}.record_status: invalid value")

    if record["artifact_type"] != "paper":
        errors.append(f"{label}.artifact_type: currently only paper is allowed")
    title = record["title"]
    if not isinstance(title, str) or not title.strip():
        errors.append(f"{label}.title: must be a non-empty string")

    publication = record["publication"]
    if not isinstance(publication, dict):
        errors.append(f"{label}.publication: must be an object")
    else:
        pub_url = publication.get("url")
        if not isinstance(pub_url, str) or not pub_url.startswith(("http://", "https://")):
            errors.append(f"{label}.publication.url: must be HTTP(S)")
        if publication.get("identity_status") not in IDENTITY_STATUSES:
            errors.append(f"{label}.publication.identity_status: invalid value")
        if not DATE_RE.fullmatch(str(publication.get("identity_check_date", ""))):
            errors.append(f"{label}.publication.identity_check_date: must use YYYY-MM-DD")
        method = publication.get("identity_check_method")
        if not isinstance(method, str) or not method:
            errors.append(f"{label}.publication.identity_check_method: must be a non-empty string")
    check_evidence_list(
        root,
        record["publication_identity_evidence"],
        f"{label}.publication_identity_evidence",
        errors,
        allow_empty=False,
    )
    check_license(record["license"], f"{label}.license", root, errors)
    if record["local_modifications"] not in MODIFICATION_STATUSES:
        errors.append(f"{label}.local_modifications: invalid value")
    if record["verification_status"] not in ARTIFACT_VERIFICATION:
        errors.append(f"{label}.verification_status: invalid value")
    questions = record["unresolved_questions"]
    if not questions or not all(isinstance(item, str) and item for item in questions):
        errors.append(f"{label}.unresolved_questions: must be a non-empty string list")

    fingerprint = record["fingerprint"]
    if not isinstance(fingerprint, dict):
        errors.append(f"{label}.fingerprint: must be an object")
    else:
        blob_oid = fingerprint.get("blob_oid")
        digest = fingerprint.get("sha256")
        size = fingerprint.get("bytes")
        if not isinstance(blob_oid, str) or not OID_RE.fullmatch(blob_oid):
            errors.append(f"{label}.fingerprint.blob_oid: invalid Git blob OID")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"{label}.fingerprint.sha256: invalid SHA-256")
        if not isinstance(size, int) or size < 0:
            errors.append(f"{label}.fingerprint.bytes: invalid byte count")

    snapshots = record["snapshots"]
    active_id = record["active_snapshot_id"]
    active_seen = False
    if not isinstance(snapshots, list) or not snapshots:
        errors.append(f"{label}.snapshots: append-only history requires at least one entry")
    else:
        for index, snapshot in enumerate(snapshots):
            snapshot_label = f"{label}.snapshots[{index}]"
            if not isinstance(snapshot, dict):
                errors.append(f"{snapshot_label}: must be an object")
                continue
            snapshot_id, _ = check_snapshot_common(snapshot, snapshot_label, errors)
            if snapshot["kind"] != "blob":
                errors.append(f"{snapshot_label}.kind: artifact snapshots require blob")
            snapshot_blob = snapshot.get("blob_oid")
            snapshot_digest = snapshot.get("sha256")
            snapshot_bytes = snapshot.get("bytes")
            if not isinstance(snapshot_blob, str) or not OID_RE.fullmatch(snapshot_blob):
                errors.append(f"{snapshot_label}.blob_oid: invalid Git blob OID")
            if not isinstance(snapshot_digest, str) or not SHA256_RE.fullmatch(snapshot_digest):
                errors.append(f"{snapshot_label}.sha256: invalid SHA-256")
            if not isinstance(snapshot_bytes, int) or snapshot_bytes < 0:
                errors.append(f"{snapshot_label}.bytes: invalid byte count")
            check_evidence_list(
                root,
                snapshot.get("evidence_paths"),
                f"{snapshot_label}.evidence_paths",
                errors,
                allow_empty=False,
            )
            if not isinstance(snapshot_id, str) or not ID_RE.fullmatch(snapshot_id):
                errors.append(f"{snapshot_label}.id: invalid snapshot ID")
            elif snapshot_id in context.snapshot_ids:
                errors.append(f"{snapshot_label}: duplicate snapshot ID")
            else:
                context.snapshot_ids.add(snapshot_id)
            if snapshot_id == active_id:
                active_seen = True
    if active_id is None or not isinstance(active_id, str) or not active_seen:
        errors.append(f"{label}.active_snapshot_id: must identify a row-local snapshot")

    target = root / Path(*(current_path.parts if current_path else ()))
    if target.exists() and not target.is_file():
        errors.append(f"{label}.current_path: expected a file")
    context.artifact_paths[current_path.as_posix() if current_path else ""] = fingerprint


class ValidationContext:
    def __init__(self, source_record_ids: set[str]):
        self.record_ids: set[str] = set()
        self.snapshot_ids: set[str] = set()
        self.source_record_ids = source_record_ids
        self.source_paths: dict[str, dict[str, Any] | None] = {}
        self.artifact_paths: dict[str, Any] = {}


def validate_registries(
    root: Path,
    source_data: dict[str, Any],
    artifact_data: dict[str, Any],
    *,
    verify_hashes: bool,
    check_generated: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []

    if source_data.get("schema_version") != 2:
        errors.append("sources.schema_version: must be 2")
    if source_data.get("registry_type") != "iris-x-corpus-sources":
        errors.append("sources.registry_type: unexpected value")
    if source_data.get("phase") != "research-preparation":
        errors.append("sources.phase: unexpected value")
    import_commit = source_data.get("import_commit")
    if not isinstance(import_commit, str) or not OID_RE.fullmatch(import_commit):
        errors.append("sources.import_commit: invalid initial import OID")
    expected_sources = source_data.get("expected_counts", {}).get("sources")
    source_records = source_data.get("records")
    source_count = len(source_records) if isinstance(source_records, list) else -1
    if expected_sources != source_count:
        errors.append("sources.expected_counts.sources: does not match records")

    if artifact_data.get("schema_version") != 2:
        errors.append("artifacts.schema_version: must be 2")
    if artifact_data.get("registry_type") != "iris-x-corpus-artifacts":
        errors.append("artifacts.registry_type: unexpected value")
    if artifact_data.get("phase") != "research-preparation":
        errors.append("artifacts.phase: unexpected value")
    expected_artifacts = artifact_data.get("expected_counts", {}).get("artifacts")
    artifact_records = artifact_data.get("records")
    artifact_count = len(artifact_records) if isinstance(artifact_records, list) else -1
    if expected_artifacts != artifact_count:
        errors.append("artifacts.expected_counts.artifacts: does not match records")

    if not isinstance(source_records, list) or not source_records:
        errors.append("sources.records: must be a non-empty list")
        source_records = []
    if not isinstance(artifact_records, list) or not artifact_records:
        errors.append("artifacts.records: must be a non-empty list")
        artifact_records = []

    pre_source_ids = {
        record.get("id")
        for record in source_records
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    context = ValidationContext(pre_source_ids)
    for record in source_records:
        check_source_record(record, root, context, errors)
    for record in artifact_records:
        check_artifact_record(record, root, context, errors)

    try:
        current_trees = current_git_tree_oids(root, list(context.source_paths))
    except (OSError, RuntimeError) as exc:
        errors.append(f"semantic snapshot check unavailable: {exc}")
        current_trees = {}

    for path, snapshot in context.source_paths.items():
        if not snapshot:
            continue
        historical_tree = resolve_git_object(root, snapshot["source_ref"], "tree")
        if historical_tree is None:
            errors.append(
                f"source snapshot identity cannot resolve for {path}: {snapshot['source_ref']}"
            )
            continue
        recorded_tree = snapshot.get("tree_oid")
        if historical_tree is not None and historical_tree != recorded_tree:
            errors.append(
                f"source snapshot identity mismatch for {path}: "
                f"{snapshot['source_ref']} resolves to {historical_tree}, registry says {recorded_tree}"
            )
        current_tree = current_trees.get(path)
        if current_tree is not None and current_tree != recorded_tree:
            errors.append(
                f"current source tree differs from active snapshot: {path} "
                f"is {current_tree}, expected {recorded_tree}"
            )

    for path, fingerprint in context.artifact_paths.items():
        target = root / Path(*PurePosixPath(path).parts) if path else None
        if target is None or not target.is_file():
            continue
        if verify_hashes and isinstance(fingerprint, dict):
            try:
                data = target.read_bytes()
            except OSError as exc:
                errors.append(f"artifact cannot be read: {path}: {exc}")
                continue
            actual_blob = git_blob_oid(data)
            actual_digest = hashlib.sha256(data).hexdigest()
            actual_size = len(data)
            if actual_size != fingerprint.get("bytes"):
                errors.append(f"artifact byte count mismatch: {path}")
            if actual_blob != fingerprint.get("blob_oid"):
                errors.append(f"artifact Git blob mismatch: {path}")
            if actual_digest != fingerprint.get("sha256"):
                errors.append(f"artifact SHA-256 mismatch: {path}")

    warnings: list[str] = []
    if check_generated:
        expected_source_index = generated_source_index(source_records)
        expected_artifact_index = generated_artifact_index(artifact_records)
        errors.extend(
            check_generated_section(
                root / "sources" / "README.md",
                "GENERATED SOURCE INDEX",
                expected_source_index,
            )
        )
        errors.extend(
            check_generated_section(
                root / "references" / "README.md",
                "GENERATED ARTIFACT INDEX",
                expected_artifact_index,
            )
        )
    errors.extend(check_top_level_boundary(root))
    errors.extend(check_authored_links(root))
    return errors, warnings


def resolve_git_object(root: Path, source_ref: str, expected_kind: str) -> str | None:
    match = SOURCE_REF_RE.fullmatch(source_ref)
    if match is None:
        return None
    commit, path = match.groups()
    try:
        value = run_git(root, ["rev-parse", "--verify", "--quiet", f"{commit}:{path}"])
    except RuntimeError:
        return None
    kind_output = run_git(root, ["cat-file", "-t", value])
    return value if kind_output == expected_kind else None


def current_git_tree_oids(root: Path, paths: list[str]) -> dict[str, str]:
    existing_paths = [path for path in paths if path and (root / Path(*PurePosixPath(path).parts)).exists()]
    if not existing_paths:
        return {}
    descriptor, index_name = tempfile.mkstemp(prefix="irisx-repository-check-", suffix=".index")
    os.close(descriptor)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_name
    try:
        run_git(root, ["read-tree", "--empty"], env=env)
        run_git(root, ["add", "--force", "--", *existing_paths], env=env)
        tree = run_git(root, ["write-tree"], env=env)
        return {
            path: run_git(root, ["rev-parse", "--verify", "--quiet", f"{tree}:{path}"], env=env)
            for path in existing_paths
        }
    finally:
        try:
            os.unlink(index_name)
        except FileNotFoundError:
            pass


def git_blob_oid(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def generated_source_index(records: Any) -> str:
    if not isinstance(records, list):
        return "- Invalid source registry."
    lines: list[str] = []
    for classification, heading in (
        ("predecessor", "Predecessors"),
        ("external-reference", "External references"),
    ):
        lines.append(f"### {heading}")
        lines.append("")
        selected = [
            record
            for record in records
            if isinstance(record, dict) and record.get("classification") == classification
        ]
        if not selected:
            lines.append("- None registered.")
        for record in selected:
            version = record.get("declared_version", "Unknown")
            upstream = record.get("upstream_url")
            origin = "Unknown" if upstream is None else str(upstream)
            role = record.get("research_role", "Unknown")
            lines.append(
                f"- `{record.get('id')}` — `{record.get('path')}`; "
                f"declared version `{version}`; upstream: {origin}; role: {role}."
            )
        lines.append("")
    return "\n".join(lines).strip()


def generated_artifact_index(records: Any) -> str:
    if not isinstance(records, list):
        return "- Invalid artifact registry."
    lines = []
    for record in records:
        if not isinstance(record, dict):
            continue
        related = record.get("related_source_id") or "standalone"
        lines.append(
            f"- `{record.get('id')}` — `{record.get('path')}`; related: `{related}`."
        )
    return "\n".join(lines)


def render_generated_section(marker: str, content: str) -> str:
    return f"<!-- BEGIN {marker} -->\n{content}\n<!-- END {marker} -->"


def check_generated_section(path: Path, marker: str, expected: str) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"generated index unreadable: {path}: {exc}"]
    begin = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < 0 or stop < start:
        return [f"generated index markers missing: {path} ({marker})"]
    actual = text[start + len(begin) : stop].strip()
    if actual != expected:
        return [f"stale generated index: {path}; run repository_check.py --write-indexes"]
    return []


def write_generated_indexes(
    root: Path,
    source_data: dict[str, Any],
    artifact_data: dict[str, Any],
) -> None:
    update_generated_section(
        root / "sources" / "README.md",
        "GENERATED SOURCE INDEX",
        generated_source_index(source_data.get("records")),
    )
    update_generated_section(
        root / "references" / "README.md",
        "GENERATED ARTIFACT INDEX",
        generated_artifact_index(artifact_data.get("records")),
    )


def update_generated_section(path: Path, marker: str, content: str) -> None:
    begin = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    text = path.read_text(encoding="utf-8")
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < 0 or stop < start:
        raise RuntimeError(f"generated markers are missing in {path}")
    replacement = render_generated_section(marker, content)
    updated = text[:start] + replacement + text[stop + len(end) :]
    path.write_text(updated, encoding="utf-8", newline="\n")


def check_top_level_boundary(root: Path) -> list[str]:
    errors: list[str] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if entry.name.startswith(".") and entry.name not in ALLOWED_TOP_LEVEL_FILES:
            continue
        if entry.is_dir() and entry.name not in ALLOWED_TOP_LEVEL_DIRS:
            errors.append(f"top-level boundary: unexpected directory {entry.name}/")
        elif entry.is_file() and entry.name not in ALLOWED_TOP_LEVEL_FILES:
            errors.append(f"top-level boundary: unexpected file {entry.name}; PDFs belong under references/papers/")
    for required in ("sources/AGENTS.md", "research/AGENTS.md", "experiments/AGENTS.md", "tools/repository_check.py"):
        if not (root / required).is_file():
            errors.append(f"required authored boundary file missing: {required}")
    return errors


LINK_RE = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]+\")?\)")
AUTHORED_MD_ROOTS = (
    "AGENTS.md",
    "README.md",
    "corpus",
    "docs",
    "experiments",
    "references/README.md",
    "research",
    "sources/AGENTS.md",
    "sources/README.md",
    "tools/README.md",
)


def check_authored_links(root: Path) -> list[str]:
    errors: list[str] = []
    files: list[Path] = []
    for item in AUTHORED_MD_ROOTS:
        path = root / item
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob("*.md"))
    link_pattern = re.compile(LINK_RE.pattern)
    for markdown_file in sorted(set(files)):
        relative = markdown_file.relative_to(root).as_posix()
        try:
            text = markdown_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"authored document unreadable: {relative}: {exc}")
            continue
        for match in link_pattern.finditer(text):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            without_fragment = target.split("#", 1)[0]
            if not without_fragment:
                continue
            resolved = (markdown_file.parent / without_fragment).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"unsafe authored link in {relative}: {target}")
                continue
            if not resolved.exists():
                errors.append(f"broken authored link in {relative}: {target}")
    return errors


def build_self_repository(temporary: Path) -> None:
    run_git(temporary, ["init", "--quiet"])
    run_git(temporary, ["config", "user.name", "Repository Check Self Test"])
    run_git(temporary, ["config", "user.email", "self-test@invalid"])
    original_dir = temporary / "example-source"
    original_dir.mkdir()
    (original_dir / "file.txt").write_text("unchanged\n", encoding="utf-8")
    artifact_bytes = b"%PDF-1.4 self test\n"
    (temporary / "example.pdf").write_bytes(artifact_bytes)
    run_git(temporary, ["add", "example-source", "example.pdf"])
    run_git(temporary, ["commit", "--quiet", "-m", "self-test import"])
    commit = run_git(temporary, ["rev-parse", "HEAD"])
    original_tree = run_git(temporary, ["rev-parse", f"{commit}:example-source"])
    original_blob = run_git(temporary, ["rev-parse", f"{commit}:example.pdf"])

    classified_root = temporary / "sources" / "predecessors"
    papers_root = temporary / "references" / "papers"
    corpus_root = temporary / "corpus"
    research_root = temporary / "research" / "templates"
    experiments_root = temporary / "experiments"
    tools_root = temporary / "tools"
    docs_root = temporary / "docs"
    classified_root.mkdir(parents=True)
    papers_root.mkdir(parents=True)
    corpus_root.mkdir()
    research_root.mkdir(parents=True)
    experiments_root.mkdir()
    tools_root.mkdir()
    docs_root.mkdir()
    (original_dir).rename(classified_root / "example-source")
    (temporary / "example.pdf").rename(papers_root / "example.pdf")
    (temporary / "sources" / "AGENTS.md").write_text("Preserved.\n", encoding="utf-8")
    (temporary / "research" / "AGENTS.md").write_text("Research.\n", encoding="utf-8")
    (temporary / "experiments" / "AGENTS.md").write_text("Experiments.\n", encoding="utf-8")
    (temporary / "README.md").write_text("# Self Test\n", encoding="utf-8")
    (temporary / "sources" / "README.md").write_text(
        "<!-- BEGIN GENERATED SOURCE INDEX -->\n<!-- END GENERATED SOURCE INDEX -->\n",
        encoding="utf-8",
    )
    (temporary / "references" / "README.md").write_text(
        "<!-- BEGIN GENERATED ARTIFACT INDEX -->\n<!-- END GENERATED ARTIFACT INDEX -->\n",
        encoding="utf-8",
    )
    (temporary / "tools" / "repository_check.py").touch()

    source_record = {
        "id": "src.example",
        "path": "sources/predecessors/example-source",
        "original_import_path": "example-source",
        "current_path": "sources/predecessors/example-source",
        "record_status": "active",
        "classification": "predecessor",
        "research_role": "Self-test role.",
        "upstream_url": None,
        "upstream_url_status": "Unknown",
        "upstream_url_evidence": [],
        "upstream_revision_kind": "Unknown",
        "upstream_revision": "Unknown",
        "declared_version": "Unknown",
        "declared_version_evidence": [],
        "acquisition": {
            "method": "self-test",
            "evidence_paths": [".git"],
            "commit_subject": "self-test import",
        },
        "license": {"status": "unknown", "spdx": "Unknown", "evidence": []},
        "local_modifications": "unknown",
        "verification_status": "local-snapshot-fingerprinted",
        "active_snapshot_id": "snap.src.example.initial-import",
        "snapshots": [{
            "id": "snap.src.example.initial-import",
            "kind": "git-tree",
            "status": "active",
            "event": "initial-import",
            "source_ref": f"{commit}:example-source",
            "tree_oid": original_tree,
            "acquired_at_commit": commit,
            "evidence_paths": [".git"],
        }],
        "unresolved_questions": ["Self-test unknown."],
    }
    artifact_record = {
        "id": "art.example",
        "path": "references/papers/example.pdf",
        "original_import_path": "example.pdf",
        "current_path": "references/papers/example.pdf",
        "record_status": "active",
        "artifact_type": "paper",
        "title": "Example Paper",
        "related_source_id": "src.example",
        "publication": {
            "url": "https://example.com/paper",
            "identity_status": "verified-primary-metadata",
            "identity_check_date": "2026-08-24",
            "identity_check_method": "self-test",
        },
        "publication_identity_evidence": ["references/papers/example.pdf"],
        "license": {"status": "unknown", "spdx": "Unknown", "evidence": []},
        "local_modifications": "unknown",
        "verification_status": "local-fingerprinted",
        "active_snapshot_id": "snap.art.example.initial-import",
        "snapshots": [{
            "id": "snap.art.example.initial-import",
            "kind": "blob",
            "status": "active",
            "event": "initial-import",
            "source_ref": f"{commit}:example.pdf",
            "blob_oid": original_blob,
            "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            "bytes": len(artifact_bytes),
            "acquired_at_commit": commit,
            "evidence_paths": [".git"],
        }],
        "fingerprint": {
            "blob_oid": original_blob,
            "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            "bytes": len(artifact_bytes),
        },
        "unresolved_questions": ["Self-test unknown."],
    }
    source_registry = {
        "schema_version": 2,
        "registry_type": "iris-x-corpus-sources",
        "phase": "research-preparation",
        "import_commit": commit,
        "expected_counts": {"sources": 1},
        "records": [source_record],
    }
    artifact_registry = {
        "schema_version": 2,
        "registry_type": "iris-x-corpus-artifacts",
        "phase": "research-preparation",
        "expected_counts": {"artifacts": 1},
        "records": [artifact_record],
    }
    (corpus_root / "sources.yaml").write_text(
        json.dumps(source_registry, indent=2) + "\n", encoding="utf-8"
    )
    (corpus_root / "artifacts.yaml").write_text(
        json.dumps(artifact_registry, indent=2) + "\n", encoding="utf-8"
    )
    write_generated_indexes(temporary, source_registry, artifact_registry)
    (research_root / "research-note.md").touch()
    (docs_root / "repository-layout.md").touch()


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="irisx-repository-check-") as temporary_name:
        temporary = Path(temporary_name)
        build_self_repository(temporary)
        sources_path = temporary / "corpus" / "sources.yaml"
        artifacts_path = temporary / "corpus" / "artifacts.yaml"
        source_data, _ = load_json_yaml(sources_path)
        artifact_data, _ = load_json_yaml(artifacts_path)

        positive_errors, _ = validate_registries(
            temporary,
            source_data,
            artifact_data,
            verify_hashes=True,
            check_generated=True,
        )
        assert not positive_errors, positive_errors

        def expect_error(label: str, mutate: Any, fragment: str, *, hashes: bool = True) -> None:
            mutable_sources = json.loads(sources_path.read_text(encoding="utf-8"))
            mutable_artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
            mutate(mutable_sources, mutable_artifacts)
            found_errors, _ = validate_registries(
                temporary,
                mutable_sources,
                mutable_artifacts,
                verify_hashes=hashes,
                check_generated=False,
            )
            assert any(fragment in error for error in found_errors), (label, found_errors)

        expect_error(
            "duplicate ID",
            lambda s, a: s["records"].append(dict(s["records"][0])),
            "duplicate stable ID",
        )
        expect_error(
            "illegal enum",
            lambda s, a: s["records"][0].__setitem__("classification", "invalid"),
            "invalid value",
        )
        expect_error(
            "bad evidence path",
            lambda s, a: s["records"][0]["acquisition"]["evidence_paths"].append("missing.txt"),
            "does not exist",
        )
        expect_error(
            "wrong tree OID",
            lambda s, a: s["records"][0]["snapshots"][0].__setitem__("tree_oid", "1" * 40),
            "current source tree differs",
        )
        expect_error(
            "broken relationship",
            lambda s, a: a["records"][0].__setitem__("related_source_id", "src.missing"),
            "unknown source relationship",
        )
        expect_error(
            "missing inventory",
            lambda s, a: s["records"][0]["snapshots"][0]["source_ref"].replace(
                ":example-source", ":missing-source"
            ),
            "active snapshot",
        ) if False else None

        # Directly test semantic source-ref resolution failure.
        bad_semantic = json.loads(sources_path.read_text(encoding="utf-8"))
        bad_semantic["records"][0]["snapshots"][0]["source_ref"] = (
            bad_semantic["records"][0]["snapshots"][0]["acquired_at_commit"] + ":missing-source"
        )
        semantic_errors, _ = validate_registries(
            temporary,
            bad_semantic,
            artifact_data,
            verify_hashes=True,
            check_generated=False,
        )
        assert any(
            "snapshot identity cannot resolve" in error for error in semantic_errors
        ), semantic_errors

        # Hash-skip behavior: altered bytes fail when checked but pass when skipped.
        pdf = temporary / "references" / "papers" / "example.pdf"
        original_pdf_bytes = pdf.read_bytes()
        pdf.write_bytes(original_pdf_bytes + b"changed\n")
        changed_artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
        hash_errors, _ = validate_registries(
            temporary,
            source_data,
            changed_artifacts,
            verify_hashes=True,
            check_generated=False,
        )
        assert any("SHA-256 mismatch" in error for error in hash_errors), hash_errors
        skipped_errors, _ = validate_registries(
            temporary,
            source_data,
            changed_artifacts,
            verify_hashes=False,
            check_generated=False,
        )
        assert not any("mismatch" in error for error in skipped_errors), skipped_errors
        pdf.write_bytes(original_pdf_bytes)

        stale_sources = json.loads(sources_path.read_text(encoding="utf-8"))
        stale_sources["records"][0]["research_role"] = "Changed after index generation."
        stale_errors, _ = validate_registries(
            temporary,
            stale_sources,
            artifact_data,
            verify_hashes=True,
            check_generated=True,
        )
        assert any("stale generated index" in error for error in stale_errors), stale_errors

    print("self-test: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run positive/negative internal tests")
    parser.add_argument("--no-verify-hashes", action="store_true", help="skip current PDF byte/hash checks")
    parser.add_argument("--write-indexes", action="store_true", help="refresh mechanically checked index sections")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    try:
        source_data, source_load_errors = load_json_yaml(SOURCES)
        artifact_data, artifact_load_errors = load_json_yaml(ARTIFACTS)
        if args.write_indexes and not source_load_errors and not artifact_load_errors:
            write_generated_indexes(ROOT, source_data, artifact_data)
            print("generated indexes refreshed")
        errors, warnings = validate_registries(
            ROOT,
            source_data,
            artifact_data,
            verify_hashes=not args.no_verify_hashes,
            check_generated=True,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"repository validation: FAIL ({exc})")
        return 1

    for warning in warnings:
        print(f"warning: {warning}")
    if errors:
        print(f"repository validation: FAIL ({len(errors)} error(s))")
        for error in errors:
            print(f"- {error}")
        return 1
    source_count = len(source_data.get("records", []))
    artifact_count = len(artifact_data.get("records", []))
    hash_note = "hashes checked" if not args.no_verify_hashes else "hash checks skipped"
    print(
        f"repository validation: PASS ({source_count} sources, "
        f"{artifact_count} artifacts, {hash_note})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

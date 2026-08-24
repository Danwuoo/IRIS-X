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
import unicodedata
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
PHYSICAL_SOURCE_ROOTS = {
    "predecessor": Path("sources") / "predecessors",
    "external-reference": Path("sources") / "external",
}
PHYSICAL_ARTIFACT_ROOT = Path("references") / "papers"
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


def check_snapshot_common(
    snapshot: Any,
    label: str,
    errors: list[str],
) -> tuple[str | None, str | None]:
    if not isinstance(snapshot, dict):
        errors.append(f"{label}: must be an object")
        return None, None
    required = {"id", "kind", "status", "event", "source_ref", "acquired_at_commit", "evidence_paths"}
    missing = sorted(required - snapshot.keys())
    snapshot_id = snapshot.get("id")
    valid_snapshot_id = snapshot_id if isinstance(snapshot_id, str) else None
    if missing:
        errors.append(f"{label}: missing fields: {', '.join(missing)}")
        return valid_snapshot_id, None
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
        return valid_snapshot_id, None
    _, captured_path = match.groups()
    _, path_errors = safe_relative_path(captured_path, f"{label}.source_ref.path")
    if path_errors:
        errors.extend(path_errors)
        return valid_snapshot_id, None
    return valid_snapshot_id, captured_path


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

    current_path_text = current_path.as_posix() if current_path else None
    if current_path_text:
        if current_path_text in context.all_source_current_paths:
            errors.append(
                f"{label}: duplicate registered source current path {current_path_text}"
            )
        else:
            context.all_source_current_paths.add(current_path_text)

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
    active_count = 0
    active_snapshot: dict[str, Any] | None = None
    if not isinstance(snapshots, list) or not snapshots:
        errors.append(f"{label}.snapshots: append-only history requires at least one entry")
    else:
        for index, snapshot in enumerate(snapshots):
            snapshot_label = f"{label}.snapshots[{index}]"
            if not isinstance(snapshot, dict):
                errors.append(f"{snapshot_label}: must be an object")
                continue
            snapshot_id, source_ref_path = check_snapshot_common(
                snapshot, snapshot_label, errors
            )
            context.source_snapshots.append(
                (current_path_text or "", snapshot, snapshot_label, source_ref_path)
            )
            if snapshot.get("kind") != "git-tree":
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
            if "id" in snapshot:
                if not isinstance(snapshot_id, str) or not ID_RE.fullmatch(snapshot_id):
                    errors.append(f"{snapshot_label}.id: invalid snapshot ID")
                elif snapshot_id in context.snapshot_ids:
                    errors.append(f"{snapshot_label}: duplicate snapshot ID")
                else:
                    context.snapshot_ids.add(snapshot_id)
            if snapshot.get("status") == "active":
                active_count += 1
                if active_snapshot is None:
                    active_snapshot = snapshot
    if active_count != 1:
        errors.append(f"{label}: exactly one snapshot must have status active; found {active_count}")
    elif active_snapshot is not None:
        if not isinstance(active_id, str) or not ID_RE.fullmatch(active_id):
            errors.append(f"{label}.active_snapshot_id: invalid stable ID {active_id!r}")
        elif active_snapshot.get("id") != active_id:
            errors.append(f"{label}.active_snapshot_id: points to a different snapshot")
    if active_snapshot is not None and record["record_status"] == "active":
        context.active_source_records[current_path_text or ""] = record

    target = root / Path(*(current_path.parts if current_path else ()))
    if record["record_status"] == "active":
        if not target.exists():
            errors.append(f"physical inventory: active registered source is missing: {current_path_text}")
        elif not target.is_dir():
            errors.append(f"physical inventory: active registered source is not a directory: {current_path_text}")
    elif target.exists():
        errors.append(
            f"lifecycle: deprecated source remains at classified corpus path {current_path_text}; "
            "remove it after retaining its final snapshot"
        )
    context.source_paths[current_path_text or ""] = active_snapshot


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
    current_path_text = current_path.as_posix() if current_path else None
    if current_path_text:
        if current_path_text in context.all_artifact_current_paths:
            errors.append(
                f"{label}: duplicate registered artifact current path {current_path_text}"
            )
        else:
            context.all_artifact_current_paths.add(current_path_text)
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
    active_count = 0
    active_snapshot: dict[str, Any] | None = None
    if not isinstance(snapshots, list) or not snapshots:
        errors.append(f"{label}.snapshots: append-only history requires at least one entry")
    else:
        for index, snapshot in enumerate(snapshots):
            snapshot_label = f"{label}.snapshots[{index}]"
            if not isinstance(snapshot, dict):
                errors.append(f"{snapshot_label}: must be an object")
                continue
            snapshot_id, source_ref_path = check_snapshot_common(
                snapshot, snapshot_label, errors
            )
            context.artifact_snapshots.append(
                (current_path_text or "", snapshot, snapshot_label, source_ref_path)
            )
            if snapshot.get("kind") != "blob":
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
            if "id" in snapshot:
                if not isinstance(snapshot_id, str) or not ID_RE.fullmatch(snapshot_id):
                    errors.append(f"{snapshot_label}.id: invalid snapshot ID")
                elif snapshot_id in context.snapshot_ids:
                    errors.append(f"{snapshot_label}: duplicate snapshot ID")
                else:
                    context.snapshot_ids.add(snapshot_id)
            if snapshot.get("status") == "active":
                active_count += 1
                if active_snapshot is None:
                    active_snapshot = snapshot
    if active_count != 1:
        errors.append(f"{label}: exactly one snapshot must have status active; found {active_count}")
    elif active_snapshot is not None:
        if not isinstance(active_id, str) or not ID_RE.fullmatch(active_id):
            errors.append(f"{label}.active_snapshot_id: invalid stable ID {active_id!r}")
        elif active_snapshot.get("id") != active_id:
            errors.append(f"{label}.active_snapshot_id: points to a different snapshot")
    if active_snapshot is not None and record["record_status"] == "active":
        context.active_artifact_records[current_path_text or ""] = record

    target = root / Path(*(current_path.parts if current_path else ()))
    if record["record_status"] == "active":
        if not target.exists():
            errors.append(f"physical inventory: active registered artifact is missing: {current_path_text}")
        elif not target.is_file():
            errors.append(f"physical inventory: active registered artifact is not a file: {current_path_text}")
    elif target.exists():
        errors.append(
            f"lifecycle: deprecated artifact remains at classified corpus path {current_path_text}; "
            "remove it after retaining its final snapshot"
        )
    context.artifact_paths[current_path_text or ""] = fingerprint


class ValidationContext:
    def __init__(self, source_record_ids: set[str]):
        self.record_ids: set[str] = set()
        self.snapshot_ids: set[str] = set()
        self.source_record_ids = source_record_ids
        self.all_source_current_paths: set[str] = set()
        self.all_artifact_current_paths: set[str] = set()
        self.source_paths: dict[str, dict[str, Any] | None] = {}
        self.artifact_paths: dict[str, Any] = {}
        self.source_snapshots: list[tuple[str, dict[str, Any], str, str | None]] = []
        self.artifact_snapshots: list[tuple[str, dict[str, Any], str, str | None]] = []
        self.active_source_records: dict[str, dict[str, Any]] = {}
        self.active_artifact_records: dict[str, dict[str, Any]] = {}


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

    errors.extend(check_physical_inventory(root, context))

    try:
        current_trees = current_git_tree_oids(root, list(context.source_paths))
    except (OSError, RuntimeError) as exc:
        errors.append(f"semantic snapshot check unavailable: {exc}")
        current_trees = {}

    for path, snapshot, snapshot_label, source_ref_path in context.source_snapshots:
        if source_ref_path is None:
            continue
        historical_tree = resolve_git_object(root, snapshot["source_ref"], "tree")
        current_tree = current_trees.get(path)
        recorded_tree = snapshot.get("tree_oid")
        if historical_tree is None:
            errors.append(
                f"{snapshot_label}: source identity cannot resolve: {snapshot['source_ref']}"
            )
        elif historical_tree != recorded_tree:
            errors.append(
                f"{snapshot_label}: source identity mismatch; "
                f"{snapshot['source_ref']} resolves to {historical_tree}, registry says {recorded_tree}"
            )
        if (
            snapshot.get("status") == "active"
            and current_tree is not None
            and current_tree != recorded_tree
        ):
            errors.append(
                f"{snapshot_label}: current source tree differs from active snapshot: {path} "
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

    for path, snapshot, snapshot_label, source_ref_path in context.artifact_snapshots:
        if source_ref_path is None:
            continue
        resolved_blob = resolve_git_object(root, snapshot["source_ref"], "blob")
        if resolved_blob is None:
            errors.append(
                f"{snapshot_label}: artifact identity cannot resolve: {snapshot['source_ref']}"
            )
            continue
        recorded_blob = snapshot.get("blob_oid")
        if resolved_blob != recorded_blob:
            errors.append(
                f"{snapshot_label}: artifact identity mismatch; "
                f"{snapshot['source_ref']} resolves to {resolved_blob}, registry says {recorded_blob}"
            )
        try:
            historical_bytes = read_git_blob(root, resolved_blob)
        except (OSError, RuntimeError) as exc:
            errors.append(f"{snapshot_label}: cannot read historical artifact bytes: {exc}")
            continue
        actual_digest = hashlib.sha256(historical_bytes).hexdigest()
        if len(historical_bytes) != snapshot.get("bytes"):
            errors.append(
                f"{snapshot_label}: historical artifact byte count mismatch "
                f"({len(historical_bytes)} != {snapshot.get('bytes')})"
            )
        if actual_digest != snapshot.get("sha256"):
            errors.append(f"{snapshot_label}: historical artifact SHA-256 mismatch")

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


def read_git_blob(root: Path, object_id: str) -> bytes:
    completed = subprocess.run(
        ["git", "cat-file", "blob", object_id],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", "replace").strip())
    return completed.stdout


def check_physical_inventory(root: Path, context: ValidationContext) -> list[str]:
    errors: list[str] = []

    for classification, relative_root in PHYSICAL_SOURCE_ROOTS.items():
        boundary_root = root / relative_root
        if not boundary_root.is_dir():
            errors.append(f"physical inventory: missing source boundary {relative_root.as_posix()}/")
            continue
        physical_leaves = {
            entry.name: entry for entry in boundary_root.iterdir() if entry.is_dir()
        }
        registered_by_leaf: dict[str, list[str]] = {}
        for path, record in context.active_source_records.items():
            record_path = PurePosixPath(path)
            if (
                len(record_path.parts) == 3
                and record_path.parts[0] == relative_root.parts[0]
                and record_path.parts[1] == relative_root.parts[1]
            ):
                registered_by_leaf.setdefault(record_path.parts[2], []).append(record["id"])
        for leaf, ids in sorted(registered_by_leaf.items()):
            if len(ids) > 1:
                errors.append(
                    f"physical inventory: source leaf {relative_root.as_posix()}/{leaf} "
                    f"is claimed by multiple active records: {', '.join(sorted(ids))}"
                )
        for leaf in sorted(set(physical_leaves) - set(registered_by_leaf)):
            if leaf != ".keep":
                errors.append(
                    f"physical inventory: unregistered {classification} directory "
                    f"{relative_root.as_posix()}/{leaf}"
                )
        for leaf in sorted(set(registered_by_leaf) - set(physical_leaves)):
            errors.append(
                f"physical inventory: active registered source leaf is absent "
                f"{relative_root.as_posix()}/{leaf}"
            )

    papers_root = root / PHYSICAL_ARTIFACT_ROOT
    if not papers_root.is_dir():
        errors.append(f"physical inventory: missing paper boundary {PHYSICAL_ARTIFACT_ROOT.as_posix()}/")
    else:
        physical_pdfs = {
            entry.name: entry for entry in papers_root.iterdir() if entry.is_file() and entry.suffix.lower() == ".pdf"
        }
        non_pdf_files = [
            entry.name
            for entry in papers_root.iterdir()
            if entry.is_file() and entry.suffix.lower() != ".pdf"
        ]
        for name in sorted(non_pdf_files):
            errors.append(f"physical inventory: non-PDF file under references/papers/: {name}")
        registered_by_name: dict[str, list[str]] = {}
        for path, record in context.active_artifact_records.items():
            name = PurePosixPath(path).name
            registered_by_name.setdefault(name, []).append(record["id"])
        for name, ids in sorted(registered_by_name.items()):
            if len(ids) > 1:
                errors.append(
                    f"physical inventory: paper {name} is claimed by multiple active records: "
                    f"{', '.join(sorted(ids))}"
                )
        for name in sorted(set(physical_pdfs) - set(registered_by_name)):
            errors.append(f"physical inventory: unregistered PDF references/papers/{name}")
        for name in sorted(set(registered_by_name) - set(physical_pdfs)):
            errors.append(f"physical inventory: active registered PDF is absent references/papers/{name}")

    return errors


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
            role = str(role).strip()
            while role and (
                unicodedata.category(role[-1]).startswith("P") or role[-1].isspace()
            ):
                role = role[:-1]
            role += "."
            lines.append(
                f"- `{record.get('id')}` — `{record.get('path')}`; "
                f"declared version `{version}`; upstream: {origin}; role: {role}"
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
    external_root = temporary / "sources" / "external"
    papers_root = temporary / "references" / "papers"
    corpus_root = temporary / "corpus"
    research_root = temporary / "research" / "templates"
    experiments_root = temporary / "experiments"
    tools_root = temporary / "tools"
    docs_root = temporary / "docs"
    classified_root.mkdir(parents=True)
    external_root.mkdir(parents=True)
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
    (external_root / ".keep").write_text("", encoding="utf-8")

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

        def expect_errors(label: str, mutate: Any, *fragments: str) -> list[str]:
            mutable_sources = json.loads(sources_path.read_text(encoding="utf-8"))
            mutable_artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
            mutate(mutable_sources, mutable_artifacts)
            found_errors, _ = validate_registries(
                temporary,
                mutable_sources,
                mutable_artifacts,
                verify_hashes=True,
                check_generated=False,
            )
            for fragment in fragments:
                assert any(fragment in error for error in found_errors), (label, found_errors)
            return found_errors

        def expect_no_error(label: str, mutate: Any) -> None:
            mutable_sources = json.loads(sources_path.read_text(encoding="utf-8"))
            mutable_artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
            mutate(mutable_sources, mutable_artifacts)
            found_errors, _ = validate_registries(
                temporary,
                mutable_sources,
                mutable_artifacts,
                verify_hashes=True,
                check_generated=False,
            )
            assert not found_errors, (label, found_errors)

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
            "malformed source snapshot",
            lambda s, a: s["records"][0]["snapshots"][0].pop("source_ref"),
            "missing fields: source_ref",
        )
        expect_error(
            "malformed artifact snapshot",
            lambda s, a: a["records"][0]["snapshots"][0].pop("source_ref"),
            "missing fields: source_ref",
        )

        # Snapshot parse results must remain attached to the snapshot that produced
        # them.  These arrangements used to reuse the final snapshot's source_ref.
        def malformed_source_before_valid(sources: Any, artifacts: Any) -> None:
            record = sources["records"][0]
            original = dict(record["snapshots"][0])
            malformed = dict(original)
            malformed["status"] = "superseded"
            malformed.pop("source_ref")
            valid = {
                **original,
                "id": "snap.src.example.second-valid",
                "status": "active",
                "event": "refresh",
            }
            record["snapshots"] = [malformed, valid]
            record["active_snapshot_id"] = valid["id"]

        expect_error(
            "source malformed before valid snapshot",
            malformed_source_before_valid,
            "snapshots[0]: missing fields: source_ref",
        )

        def source_mismatch_before_malformed(sources: Any, artifacts: Any) -> None:
            record = sources["records"][0]
            original = dict(record["snapshots"][0])
            historical = {
                **original,
                "status": "superseded",
                "event": "refresh",
                "tree_oid": "1" * 40,
            }
            malformed = {
                **original,
                "id": "snap.src.example.malformed-active",
                "status": "active",
                "event": "refresh",
            }
            malformed.pop("source_ref")
            record["snapshots"] = [historical, malformed]
            record["active_snapshot_id"] = malformed["id"]

        expect_errors(
            "source historical mismatch before malformed snapshot",
            source_mismatch_before_malformed,
            "snapshots[0]: source identity mismatch",
            "snapshots[1]: missing fields: source_ref",
        )

        def malformed_artifact_before_valid(sources: Any, artifacts: Any) -> None:
            record = artifacts["records"][0]
            original = dict(record["snapshots"][0])
            malformed = dict(original)
            malformed["status"] = "superseded"
            malformed.pop("source_ref")
            valid = {
                **original,
                "id": "snap.art.example.second-valid",
                "status": "active",
                "event": "refresh",
            }
            record["snapshots"] = [malformed, valid]
            record["active_snapshot_id"] = valid["id"]

        expect_error(
            "artifact malformed before valid snapshot",
            malformed_artifact_before_valid,
            "snapshots[0]: missing fields: source_ref",
        )

        def artifact_mismatch_before_malformed(sources: Any, artifacts: Any) -> None:
            record = artifacts["records"][0]
            original = dict(record["snapshots"][0])
            historical = {
                **original,
                "status": "superseded",
                "event": "refresh",
                "blob_oid": "5" * 40,
            }
            malformed = {
                **original,
                "id": "snap.art.example.malformed-active",
                "status": "active",
                "event": "refresh",
            }
            malformed.pop("source_ref")
            record["snapshots"] = [historical, malformed]
            record["active_snapshot_id"] = malformed["id"]

        expect_errors(
            "artifact historical mismatch before malformed snapshot",
            artifact_mismatch_before_malformed,
            "snapshots[0]: artifact identity mismatch",
            "snapshots[1]: missing fields: source_ref",
        )

        # Missing shared snapshot fields are structural errors.  Retain a valid ID
        # for duplicate tracking without also reporting it as invalid.
        for registry_name in ("source", "artifact"):
            for field in (
                "id",
                "kind",
                "status",
                "event",
                "source_ref",
                "acquired_at_commit",
                "evidence_paths",
            ):
                def remove_required_snapshot_field(
                    sources: Any,
                    artifacts: Any,
                    *,
                    registry_name: str = registry_name,
                    field: str = field,
                ) -> None:
                    registry = sources if registry_name == "source" else artifacts
                    registry["records"][0]["snapshots"][0].pop(field)

                required_field_errors = expect_errors(
                    f"{registry_name} snapshot missing {field}",
                    remove_required_snapshot_field,
                    f"missing fields: {field}",
                )
                assert not any(
                    "snapshots[0].id: invalid snapshot ID" in error
                    for error in required_field_errors
                ), (registry_name, field, required_field_errors)

        # Missing registered source is checked by temporarily moving the physical tree.
        missing_source_registry = json.loads(sources_path.read_text(encoding="utf-8"))
        missing_source_dir = temporary / "sources" / "predecessors" / "example-source"
        hidden_missing_source = temporary / ".self-test-missing-source"
        missing_source_dir.rename(hidden_missing_source)
        try:
            missing_errors, _ = validate_registries(
                temporary,
                missing_source_registry,
                artifact_data,
                verify_hashes=True,
                check_generated=False,
            )
        finally:
            hidden_missing_source.rename(missing_source_dir)
        assert any(
            "active registered source is missing" in error for error in missing_errors
        ), missing_errors

        # Keep evidence valid so the test proves the artifact-presence check itself.
        missing_artifact_registry = json.loads(artifacts_path.read_text(encoding="utf-8"))
        missing_artifact_registry["records"][0]["publication_identity_evidence"] = [".git"]
        missing_pdf = temporary / "references" / "papers" / "example.pdf"
        hidden_missing_pdf = temporary / ".self-test-missing.pdf"
        missing_pdf.rename(hidden_missing_pdf)
        try:
            missing_artifact_errors, _ = validate_registries(
                temporary,
                source_data,
                missing_artifact_registry,
                verify_hashes=True,
                check_generated=False,
            )
        finally:
            hidden_missing_pdf.rename(missing_pdf)
        assert any(
            "active registered artifact is missing" in error
            for error in missing_artifact_errors
        ), missing_artifact_errors

        unregistered_predecessor = (
            temporary / "sources" / "predecessors" / "unregistered-source"
        )
        unregistered_predecessor.mkdir()
        try:
            errors_unregistered_pred, _ = validate_registries(
                temporary,
                source_data,
                artifact_data,
                verify_hashes=True,
                check_generated=False,
            )
        finally:
            unregistered_predecessor.rmdir()
        assert any(
            "unregistered predecessor directory" in error for error in errors_unregistered_pred
        ), errors_unregistered_pred

        unregistered_external = temporary / "sources" / "external" / "unregistered-source"
        unregistered_external.mkdir()
        try:
            errors_unregistered_external, _ = validate_registries(
                temporary,
                source_data,
                artifact_data,
                verify_hashes=True,
                check_generated=False,
            )
        finally:
            unregistered_external.rmdir()
        assert any(
            "unregistered external-reference directory" in error
            for error in errors_unregistered_external
        ), errors_unregistered_external

        unregistered_pdf = temporary / "references" / "papers" / "unregistered.pdf"
        unregistered_pdf.write_bytes(b"%PDF-1.4\n")
        try:
            errors_unregistered_pdf, _ = validate_registries(
                temporary,
                source_data,
                artifact_data,
                verify_hashes=True,
                check_generated=False,
            )
        finally:
            unregistered_pdf.unlink()
        assert any(
            "unregistered PDF references/papers/unregistered.pdf" in error
            for error in errors_unregistered_pdf
        ), errors_unregistered_pdf

        def append_bad_source_snapshot(sources: Any, artifacts: Any) -> None:
            record = sources["records"][0]
            record["snapshots"].append({
                "id": "snap.src.example.bad-historical",
                "kind": "git-tree",
                "status": "superseded",
                "event": "refresh",
                "source_ref": f"{record['snapshots'][0]['acquired_at_commit']}:missing-source",
                "tree_oid": "2" * 40,
                "acquired_at_commit": record["snapshots"][0]["acquired_at_commit"],
                "evidence_paths": [".git"],
            })

        expect_error(
            "invalid historical source snapshot",
            append_bad_source_snapshot,
            "source identity cannot resolve",
        )

        good_commit = json.loads(artifacts_path.read_text(encoding="utf-8"))["records"][0][
            "snapshots"
        ][0]["acquired_at_commit"]

        def append_bad_artifact_snapshot(sources: Any, artifacts: Any) -> None:
            record = artifacts["records"][0]
            record["snapshots"].append({
                "id": "snap.art.example.bad-historical",
                "kind": "blob",
                "status": "superseded",
                "event": "refresh",
                "source_ref": f"{good_commit}:missing.pdf",
                "blob_oid": "3" * 40,
                "sha256": "4" * 64,
                "bytes": 99999,
                "acquired_at_commit": good_commit,
                "evidence_paths": [".git"],
            })

        expect_error(
            "invalid historical artifact source ref",
            append_bad_artifact_snapshot,
            "artifact identity cannot resolve",
        )

        def append_wrong_metadata_artifact_snapshot(sources: Any, artifacts: Any) -> None:
            record = artifacts["records"][0]
            record["snapshots"].append({
                "id": "snap.art.example.wrong-metadata",
                "kind": "blob",
                "status": "superseded",
                "event": "refresh",
                "source_ref": f"{good_commit}:example.pdf",
                "blob_oid": "5" * 40,
                "sha256": "6" * 64,
                "bytes": 99999,
                "acquired_at_commit": good_commit,
                "evidence_paths": [".git"],
            })

        expect_error(
            "invalid historical artifact metadata",
            append_wrong_metadata_artifact_snapshot,
            "artifact identity mismatch",
        )

        # A refresh must compare the working tree with its own active snapshot,
        # while still resolving every superseded snapshot against its source_ref.
        source_file = temporary / "sources" / "predecessors" / "example-source" / "file.txt"
        original_source_bytes = source_file.read_bytes()
        source_file.write_text("refreshed\n", encoding="utf-8")
        run_git(
            temporary,
            ["add", "--force", "--", "sources/predecessors/example-source"],
        )
        run_git(temporary, ["commit", "--quiet", "-m", "self-test source refresh"])
        refresh_commit = run_git(temporary, ["rev-parse", "HEAD"])
        refresh_tree = run_git(
            temporary,
            ["rev-parse", f"{refresh_commit}:sources/predecessors/example-source"],
        )
        refreshed_sources = json.loads(sources_path.read_text(encoding="utf-8"))
        refreshed_record = refreshed_sources["records"][0]
        refreshed_record["snapshots"][0]["status"] = "superseded"
        refreshed_record["active_snapshot_id"] = "snap.src.example.refresh"
        refreshed_record["snapshots"].append({
            "id": "snap.src.example.refresh",
            "kind": "git-tree",
            "status": "active",
            "event": "refresh",
            "source_ref": f"{refresh_commit}:sources/predecessors/example-source",
            "tree_oid": refresh_tree,
            "acquired_at_commit": refresh_commit,
            "evidence_paths": [".git"],
        })
        refresh_errors, _ = validate_registries(
            temporary,
            refreshed_sources,
            artifact_data,
            verify_hashes=True,
            check_generated=False,
        )
        assert not refresh_errors, refresh_errors
        source_file.write_bytes(original_source_bytes)

        def duplicate_source_snapshot_id(sources: Any, artifacts: Any) -> None:
            record = sources["records"][0]
            duplicate = {
                **record["snapshots"][0],
                "status": "superseded",
                "event": "refresh",
            }
            record["snapshots"].append(duplicate)

        expect_error(
            "duplicate snapshot ID in source history",
            duplicate_source_snapshot_id,
            "duplicate snapshot ID",
        )

        def active_id_points_to_superseded_snapshot(sources: Any, artifacts: Any) -> None:
            record = sources["records"][0]
            original = dict(record["snapshots"][0])
            superseded = {
                **original,
                "id": "snap.src.example.superseded",
                "status": "superseded",
                "event": "refresh",
            }
            active = {
                **original,
                "id": "snap.src.example.replacement-active",
                "status": "active",
                "event": "refresh",
            }
            record["snapshots"] = [superseded, active]
            record["active_snapshot_id"] = superseded["id"]

        expect_error(
            "active ID points to superseded snapshot",
            active_id_points_to_superseded_snapshot,
            "active_snapshot_id: points to a different snapshot",
        )

        def add_second_active_source_snapshot(sources: Any, artifacts: Any) -> None:
            first = sources["records"][0]["snapshots"][0]
            sources["records"][0]["snapshots"].append({
                **first,
                "id": "snap.src.example.second-active",
                "event": "refresh",
            })

        expect_error(
            "multiple active snapshots",
            add_second_active_source_snapshot,
            "exactly one snapshot must have status active; found 2",
        )

        expect_error(
            "no active snapshot",
            lambda s, a: s["records"][0]["snapshots"][0].__setitem__("status", "superseded"),
            "exactly one snapshot must have status active; found 0",
        )

        expect_error(
            "active ID points to retired snapshot",
            lambda s, a: s["records"][0]["snapshots"][0].__setitem__("status", "retired"),
            "found 0",
        )

        deprecated_absent_registry = json.loads(sources_path.read_text(encoding="utf-8"))
        deprecated_absent_registry["records"][0]["record_status"] = "deprecated"
        deprecated_source_dir = temporary / "sources" / "predecessors" / "example-source"
        hidden_deprecated_source = temporary / ".self-test-deprecated-source"
        deprecated_source_dir.rename(hidden_deprecated_source)
        try:
            absent_deprecated_errors, _ = validate_registries(
                temporary,
                deprecated_absent_registry,
                artifact_data,
                verify_hashes=True,
                check_generated=False,
            )
        finally:
            hidden_deprecated_source.rename(deprecated_source_dir)
        assert not any("lifecycle:" in error for error in absent_deprecated_errors), (
            absent_deprecated_errors
        )

        deprecated_present_registry = json.loads(sources_path.read_text(encoding="utf-8"))
        deprecated_present_registry["records"][0]["record_status"] = "deprecated"
        present_deprecated_errors, _ = validate_registries(
            temporary,
            deprecated_present_registry,
            artifact_data,
            verify_hashes=True,
            check_generated=False,
        )
        assert any(
            "deprecated source remains at classified corpus path" in error
            for error in present_deprecated_errors
        ), present_deprecated_errors

        deprecated_wrong_active_registry = json.loads(sources_path.read_text(encoding="utf-8"))
        deprecated_wrong_active_registry["records"][0]["record_status"] = "deprecated"
        deprecated_wrong_active_registry["records"][0]["active_snapshot_id"] = (
            "snap.src.example.wrong-active"
        )
        wrong_active_source_dir = (
            temporary / "sources" / "predecessors" / "example-source"
        )
        hidden_wrong_active_source = temporary / ".self-test-wrong-active-source"
        wrong_active_source_dir.rename(hidden_wrong_active_source)
        try:
            wrong_active_errors, _ = validate_registries(
                temporary,
                deprecated_wrong_active_registry,
                artifact_data,
                verify_hashes=True,
                check_generated=False,
            )
        finally:
            hidden_wrong_active_source.rename(wrong_active_source_dir)
        assert any(
            "active_snapshot_id: points to a different snapshot" in error
            for error in wrong_active_errors
        ), wrong_active_errors
        assert not any("lifecycle:" in error for error in wrong_active_errors), (
            wrong_active_errors
        )

        expect_no_error(
            "normalized generated punctuation",
            lambda s, a: None,
        )
        punctuation_sources = json.loads(sources_path.read_text(encoding="utf-8"))
        punctuation_sources["records"][0]["research_role"] = "Trailing punctuation?"
        punctuation_index = generated_source_index(punctuation_sources["records"])
        punctuation_lines = [
            line for line in punctuation_index.splitlines() if "; role:" in line
        ]
        assert len(punctuation_lines) == 1, punctuation_lines
        assert punctuation_lines[0].endswith("; role: Trailing punctuation."), punctuation_lines[0]
        assert not any(line.endswith("..") for line in punctuation_lines), (
            punctuation_lines
        )

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
            "source identity cannot resolve" in error for error in semantic_errors
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

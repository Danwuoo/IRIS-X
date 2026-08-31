#!/usr/bin/env python3
"""Frozen failure-state builder and targeted procedures for H-RCV1a."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = (
    ROOT
    / "sources"
    / "predecessors"
    / "vanta"
    / "docs"
    / "04_experiments"
    / "fixtures"
    / "document_ops"
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def state_manifest(workspace: Path) -> dict[str, Any]:
    root = workspace.resolve()
    files = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file():
            payload = path.read_bytes()
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_bytes(payload),
                    "bytes": len(payload),
                }
            )
    return {
        "files": files,
        "path_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "manifest_sha256": sha256_bytes(canonical_json_bytes(files)),
    }


def acceptance_action(fixture_id: str) -> dict[str, Any]:
    acceptance = load_json(FIXTURE_ROOT / fixture_id / "expected" / "acceptance.json")
    actions = acceptance.get("action_sequence", {}).get("actions", [])
    if not isinstance(actions, list) or len(actions) != 1:
        raise ValueError(f"{fixture_id}: exactly one source action is required")
    return actions[0]


def build_failure_workspace(workspace: Path, fixture_id: str, failure_kind: str) -> dict[str, Any]:
    if workspace.exists():
        raise ValueError(f"failure workspace already exists: {workspace}")
    workspace.mkdir(parents=True)
    shutil.copytree(FIXTURE_ROOT / fixture_id / "inputs", workspace / "inputs")
    action = acceptance_action(fixture_id)
    if failure_kind == "rollback-missing-backup":
        payload = action["action_payload"]
        target = workspace / payload["path"]
        original = target.read_text(encoding="utf-8")
        if original.count(payload["find"]) != 1:
            raise ValueError("rollback failure injection must resolve exactly once")
        failed = original.replace(payload["find"], payload["replace"], 1)
        target.write_text(failed, encoding="utf-8", newline="")
        recovery_spec = {
            "target_path": payload["path"],
            "failed_text": payload["replace"],
            "restore_text": payload["find"],
            "output_path": "recovery/rollback-reconstruction.json",
        }
        failure_details = {
            "target_path": payload["path"],
            "baseline_sha256": sha256_bytes(original.encode("utf-8")),
            "failed_sha256": sha256_bytes(failed.encode("utf-8")),
            "backup_present": False,
        }
    elif failure_kind == "audit-reference-gap":
        payload = action["action_payload"]
        journal = load_json(workspace / payload["path"])
        if journal.get("evidence_refs") or journal.get("verifier_output_refs"):
            raise ValueError("audit failure state is unexpectedly complete")
        recovery_spec = {
            "journal_path": payload["path"],
            "artifacts_path": payload["artifacts_path"],
            "output_path": "recovery/repaired-journal.json",
        }
        failure_details = {
            "journal_path": payload["path"],
            "missing_fields": ["evidence_refs", "verifier_output_refs"],
        }
    elif failure_kind == "compensation-required":
        payload = action["action_payload"]
        receipt_path = "failure/receipt.json"
        receipt = {
            "schema_version": 1,
            "receipt_id": payload["receipt_id"],
            "result_summary": payload["result_summary"],
            "compensation_hint": payload["compensation_hint"],
            "compensation_required": True,
            "external_action_executed": False,
        }
        write_json(workspace / receipt_path, receipt)
        recovery_spec = {
            "receipt_path": receipt_path,
            "output_path": "recovery/compensation-record.json",
        }
        failure_details = {
            "receipt_path": receipt_path,
            "receipt_id": payload["receipt_id"],
            "compensation_required": True,
        }
    else:
        raise ValueError(f"unsupported failure kind: {failure_kind}")
    failure_state = {
        "schema_version": 1,
        "fixture_id": fixture_id,
        "failure_kind": failure_kind,
        "failure_detectable": True,
        "details": failure_details,
    }
    write_json(workspace / "failure-state.json", failure_state)
    return {
        "failure_state": failure_state,
        "recovery_spec": recovery_spec,
        "manifest": state_manifest(workspace),
    }


def detect_failure(workspace: Path, failure_kind: str, recovery_spec: dict[str, Any]) -> dict[str, Any]:
    if failure_kind == "rollback-missing-backup":
        target = (workspace / recovery_spec["target_path"]).read_text(encoding="utf-8")
        detected = target.count(recovery_spec["failed_text"]) == 1 and not (workspace / ".backup").exists()
        evidence = {"failed_text_present": recovery_spec["failed_text"] in target, "backup_present": False}
    elif failure_kind == "audit-reference-gap":
        journal = load_json(workspace / recovery_spec["journal_path"])
        missing = [field for field in ("evidence_refs", "verifier_output_refs") if not journal.get(field)]
        detected = missing == ["evidence_refs", "verifier_output_refs"]
        evidence = {"missing_fields": missing}
    elif failure_kind == "compensation-required":
        receipt = load_json(workspace / recovery_spec["receipt_path"])
        detected = receipt.get("compensation_required") is True
        evidence = {"receipt_id": receipt.get("receipt_id"), "compensation_required": detected}
    else:
        raise ValueError(f"unsupported failure kind: {failure_kind}")
    return {"detected": detected, "evidence": evidence}


def execute_recovery(workspace: Path, policy: str, recovery_spec: dict[str, Any]) -> dict[str, Any]:
    forbidden = {key for key in recovery_spec if "expected" in key or "oracle" in key or "success" in key}
    if forbidden:
        raise ValueError(f"recovery specification contains forbidden oracle/label fields: {sorted(forbidden)}")
    if policy == "reconstruct-rollback-from-payload-v0":
        target_path = recovery_spec["target_path"]
        target = workspace / target_path
        content = target.read_text(encoding="utf-8")
        failed_text = recovery_spec["failed_text"]
        if content.count(failed_text) != 1:
            raise ValueError("failed text does not resolve exactly once")
        restored = content.replace(failed_text, recovery_spec["restore_text"], 1)
        target.write_text(restored, encoding="utf-8", newline="")
        record = {
            "schema_version": 1,
            "policy": policy,
            "target_path": target_path,
            "recovered_sha256": sha256_bytes(target.read_bytes()),
        }
        write_json(workspace / recovery_spec["output_path"], record)
        return {"action_completed": True, "output_path": recovery_spec["output_path"]}
    if policy == "repair-audit-refs-v0":
        journal = load_json(workspace / recovery_spec["journal_path"])
        artifacts = load_json(workspace / recovery_spec["artifacts_path"])
        evidence_refs = [
            item["evidence_id"]
            for item in artifacts.get("evidence_packets", [])
            if isinstance(item.get("evidence_id"), str)
        ]
        verifier_refs = [
            item["verifier_output_id"]
            for item in artifacts.get("verifier_outputs", [])
            if isinstance(item.get("verifier_output_id"), str)
        ]
        if not evidence_refs or not verifier_refs:
            raise ValueError("supplied audit artifacts do not provide both reference classes")
        repaired = {**journal, "evidence_refs": evidence_refs, "verifier_output_refs": verifier_refs}
        write_json(workspace / recovery_spec["output_path"], repaired)
        return {"action_completed": True, "output_path": recovery_spec["output_path"]}
    if policy == "produce-compensation-record-v0":
        receipt = load_json(workspace / recovery_spec["receipt_path"])
        record = {
            "schema_version": 1,
            "receipt_id": receipt["receipt_id"],
            "compensation_status": "compensation_completed",
            "compensation_hint": receipt["compensation_hint"],
            "external_action_executed": False,
        }
        write_json(workspace / recovery_spec["output_path"], record)
        return {"action_completed": True, "output_path": recovery_spec["output_path"]}
    raise ValueError(f"unsupported recovery policy: {policy}")

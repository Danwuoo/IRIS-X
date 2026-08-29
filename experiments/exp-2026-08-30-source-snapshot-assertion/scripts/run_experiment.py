#!/usr/bin/env python3
"""Run the H-M1a registered source-snapshot assertion experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ID = "exp-2026-08-30-source-snapshot-assertion"
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = EXPERIMENT_ROOT / "runs"
EXPECTED_DISTRIBUTION = "taskdist-2026-08-28-vanta-docops-readonly-12"
OID_RE = re.compile(r"^[0-9a-f]{40}$")
ARMS = ("record-only-v0", "registry-assert-v0")


class DefinitionError(ValueError):
    """Raised when a frozen experiment definition is invalid."""


class IdentityAssertionError(ValueError):
    """Fail-closed source identity resolution or assertion result."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RegisteredSnapshot:
    source_id: str
    source_path: str
    snapshot_id: str
    tree_oid: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json_bytes(path: Path) -> tuple[Any, bytes]:
    payload = path.read_bytes()
    return json.loads(payload.decode("utf-8")), payload


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def is_within(path: Path, boundary: Path) -> bool:
    resolved = path.resolve()
    root = boundary.resolve()
    return resolved == root or root in resolved.parents


def resolve_repo_path(value: str, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise DefinitionError(f"{label} must be a non-empty repository-relative path")
    candidate = (ROOT / value).resolve()
    if not is_within(candidate, ROOT):
        raise DefinitionError(f"{label} escapes the repository: {value}")
    return candidate


def relative_posix(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def validate_challenges(document: Any) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise DefinitionError("challenge schema_version must be 1")
    if document.get("experiment_id") != EXPERIMENT_ID:
        raise DefinitionError("challenge experiment_id mismatch")
    if document.get("distribution_id") != EXPECTED_DISTRIBUTION:
        raise DefinitionError("challenge distribution_id mismatch")
    repetitions = document.get("repetitions")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        raise DefinitionError("repetitions must be a positive integer")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) < 5:
        raise DefinitionError("at least five challenge cases are required")
    seen: set[str] = set()
    valid_count = 0
    required_ids = {
        "valid-registered-vanta",
        "unknown-source-id",
        "unknown-snapshot-id",
        "observed-tree-oid-mismatch",
        "cross-source-snapshot-relationship",
    }
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise DefinitionError(f"cases[{index}] must be an object")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise DefinitionError(f"cases[{index}].case_id is invalid or duplicated")
        seen.add(case_id)
        for field in ("source_id", "source_snapshot_id"):
            if not isinstance(case.get(field), str) or not case[field]:
                raise DefinitionError(f"{case_id}.{field} must be a non-empty string")
        if not isinstance(case.get("mismatch_expected"), bool):
            raise DefinitionError(f"{case_id}.mismatch_expected must be boolean")
        valid_count += not case["mismatch_expected"]
        observation = case.get("observation")
        if not isinstance(observation, dict):
            raise DefinitionError(f"{case_id}.observation must be an object")
        kind = observation.get("kind")
        if kind not in {"git-at-code-commit", "synthetic-recorded", "synthetic-override"}:
            raise DefinitionError(f"{case_id}: unsupported observation kind")
        if kind in {"git-at-code-commit", "synthetic-override"}:
            path = resolve_repo_path(observation.get("control_source_path"), f"{case_id}.control_source_path")
            if not is_within(path, ROOT / "sources"):
                raise DefinitionError(f"{case_id}: control source path must be under sources/")
        if kind in {"synthetic-recorded", "synthetic-override"} and not OID_RE.fullmatch(
            str(observation.get("tree_oid", ""))
        ):
            raise DefinitionError(f"{case_id}: synthetic tree_oid must be a lowercase 40-hex OID")
    if not required_ids.issubset(seen):
        raise DefinitionError(f"required challenge cases are missing: {sorted(required_ids - seen)}")
    if valid_count != 1:
        raise DefinitionError("challenge set must contain exactly one valid identity")
    return cases, repetitions


def validate_registry(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or document.get("schema_version") != 2:
        raise IdentityAssertionError("registry_schema_invalid", "registry schema_version must be 2")
    if document.get("registry_type") != "iris-x-corpus-sources":
        raise IdentityAssertionError("registry_type_invalid", "unexpected registry_type")
    records = document.get("records")
    if not isinstance(records, list):
        raise IdentityAssertionError("registry_records_invalid", "registry records must be a list")
    return records


def resolve_registered_snapshot(document: Any, source_id: str, snapshot_id: str) -> RegisteredSnapshot:
    records = validate_registry(document)
    source_matches = [record for record in records if isinstance(record, dict) and record.get("id") == source_id]
    if not source_matches:
        raise IdentityAssertionError("unknown_source_id", f"source_id is not registered: {source_id}")
    if len(source_matches) != 1:
        raise IdentityAssertionError("duplicate_source_id", f"source_id is registered more than once: {source_id}")
    record = source_matches[0]
    if record.get("record_status") != "active":
        raise IdentityAssertionError("source_not_active", f"source record is not active: {source_id}")
    snapshots = record.get("snapshots")
    if not isinstance(snapshots, list):
        raise IdentityAssertionError("snapshots_invalid", f"source snapshots are not a list: {source_id}")
    snapshot_matches = [item for item in snapshots if isinstance(item, dict) and item.get("id") == snapshot_id]
    if not snapshot_matches:
        owners = [
            item.get("id")
            for item in records
            if isinstance(item, dict)
            and any(
                isinstance(snapshot, dict) and snapshot.get("id") == snapshot_id
                for snapshot in item.get("snapshots", [])
            )
        ]
        if owners:
            raise IdentityAssertionError(
                "snapshot_source_relationship_mismatch",
                f"snapshot_id belongs to {owners[0]}, not {source_id}",
            )
        raise IdentityAssertionError("unknown_snapshot_id", f"snapshot_id is not registered: {snapshot_id}")
    if len(snapshot_matches) != 1:
        raise IdentityAssertionError("duplicate_snapshot_id", f"snapshot_id is duplicated for source: {snapshot_id}")
    snapshot = snapshot_matches[0]
    if record.get("active_snapshot_id") != snapshot_id or snapshot.get("status") != "active":
        raise IdentityAssertionError(
            "active_snapshot_relationship_mismatch",
            f"snapshot is not the active snapshot for source: {source_id} / {snapshot_id}",
        )
    if snapshot.get("kind") != "git-tree":
        raise IdentityAssertionError("snapshot_kind_invalid", "registered snapshot kind must be git-tree")
    source_path = record.get("path")
    path = resolve_repo_path(source_path, f"registry path for {source_id}")
    if not is_within(path, ROOT / "sources"):
        raise IdentityAssertionError("source_path_outside_boundary", "registered source path is outside sources/")
    tree_oid = snapshot.get("tree_oid")
    if not isinstance(tree_oid, str) or not OID_RE.fullmatch(tree_oid):
        raise IdentityAssertionError("registered_tree_oid_invalid", "registered tree_oid must be lowercase 40-hex")
    return RegisteredSnapshot(source_id, relative_posix(path), snapshot_id, tree_oid)


def git_tree_oid(code_commit: str, source_path: str) -> str:
    oid = git_output("rev-parse", f"{code_commit}:{source_path}")
    if not OID_RE.fullmatch(oid):
        raise RuntimeError(f"git returned an invalid tree OID for {source_path}: {oid}")
    return oid


def control_observation(case: dict[str, Any], code_commit: str) -> tuple[str, str | None, int]:
    observation = case["observation"]
    kind = observation["kind"]
    if kind == "synthetic-recorded":
        return observation["tree_oid"], None, 0
    actual_git_oid = git_tree_oid(code_commit, observation["control_source_path"])
    if kind == "synthetic-override":
        return observation["tree_oid"], actual_git_oid, 1
    return actual_git_oid, actual_git_oid, 1


def run_case(
    arm: str,
    case: dict[str, Any],
    repetition: int,
    registry_path: Path,
    code_commit: str,
) -> dict[str, Any]:
    started_at = utc_now()
    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    decision = "accept"
    reason_code = "record_only_no_assertion"
    reason_detail = "identity fields recorded without registry resolution or equality assertion"
    registered_tree_oid: str | None = None
    observed_tree_oid: str | None = None
    actual_git_tree_oid: str | None = None
    registry_bytes_read = 0
    git_lookup_count = 0
    episode_status = "valid"
    terminal_error: dict[str, str] | None = None
    try:
        if arm == "record-only-v0":
            observed_tree_oid, actual_git_tree_oid, git_lookup_count = control_observation(case, code_commit)
        elif arm == "registry-assert-v0":
            registry, registry_bytes = load_json_bytes(registry_path)
            registry_bytes_read = len(registry_bytes)
            registered = resolve_registered_snapshot(registry, case["source_id"], case["source_snapshot_id"])
            registered_tree_oid = registered.tree_oid
            actual_git_tree_oid = git_tree_oid(code_commit, registered.source_path)
            git_lookup_count = 1
            if case["observation"]["kind"] == "synthetic-override":
                observed_tree_oid = case["observation"]["tree_oid"]
            else:
                observed_tree_oid = actual_git_tree_oid
            if observed_tree_oid != registered.tree_oid:
                raise IdentityAssertionError(
                    "tree_oid_mismatch",
                    f"observed tree OID {observed_tree_oid} does not equal registered tree OID {registered.tree_oid}",
                )
            reason_code = "registered_identity_match"
            reason_detail = "source, active snapshot, and observed Git tree OID match the registry"
        else:
            raise DefinitionError(f"unsupported arm: {arm}")
    except IdentityAssertionError as exc:
        decision = "reject"
        reason_code = exc.code
        reason_detail = str(exc)
    except Exception as exc:  # preserve unexpected harness failures as invalid evidence
        decision = "invalid"
        reason_code = "harness_exception"
        reason_detail = str(exc)
        episode_status = "invalid"
        terminal_error = {"type": type(exc).__name__, "message": str(exc)}
    wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000
    cpu_ms = (time.process_time_ns() - cpu_start) / 1_000_000
    mismatch_expected = case["mismatch_expected"]
    mismatch_detected = mismatch_expected and decision == "reject"
    missed_mismatch = mismatch_expected and decision == "accept"
    false_positive_rejection = not mismatch_expected and decision == "reject"
    core = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "episode_started_at": started_at,
        "arm": arm,
        "case_id": case["case_id"],
        "repetition": repetition,
        "source_id": case["source_id"],
        "source_snapshot_id": case["source_snapshot_id"],
        "observation_kind": case["observation"]["kind"],
        "mismatch_expected": mismatch_expected,
        "decision": decision,
        "mismatch_detected": mismatch_detected,
        "missed_mismatch": missed_mismatch,
        "false_positive_rejection": false_positive_rejection,
        "resolution_assertion_reason": {"code": reason_code, "detail": reason_detail},
        "registered_tree_oid": registered_tree_oid,
        "observed_tree_oid": observed_tree_oid,
        "actual_git_tree_oid": actual_git_tree_oid,
        "episode_status": episode_status,
        "terminal_error": terminal_error,
        "resources": {
            "verification_wall_ms": wall_ms,
            "verification_process_cpu_ms": cpu_ms,
            "registry_bytes_read": registry_bytes_read,
            "git_tree_lookup_count": git_lookup_count,
            "model_calls": 0,
            "model_api_cost_usd": 0.0,
        },
    }
    core["resources"]["terminal_record_bytes_excluding_self"] = len(canonical_json_bytes(core))
    return core


def aggregate(records: list[dict[str, Any]], cases: list[dict[str, Any]], repetitions: int) -> dict[str, Any]:
    by_arm: dict[str, Any] = {}
    repeat_disagreements: list[dict[str, str]] = []
    for arm in ARMS:
        subset = [record for record in records if record["arm"] == arm]
        valid = [record for record in subset if record["episode_status"] == "valid"]
        for case in cases:
            case_records = [record for record in valid if record["case_id"] == case["case_id"]]
            signatures = {
                (record["decision"], record["resolution_assertion_reason"]["code"], record["observed_tree_oid"])
                for record in case_records
            }
            if len(case_records) != repetitions or len(signatures) != 1:
                repeat_disagreements.append({"arm": arm, "case_id": case["case_id"]})
        true_accept = sum(not record["mismatch_expected"] and record["decision"] == "accept" for record in valid)
        true_reject = sum(record["mismatch_expected"] and record["decision"] == "reject" for record in valid)
        false_accept = sum(record["mismatch_expected"] and record["decision"] == "accept" for record in valid)
        false_reject = sum(not record["mismatch_expected"] and record["decision"] == "reject" for record in valid)
        by_arm[arm] = {
            "attempted_records": len(subset),
            "valid_records": len(valid),
            "invalid_records": len(subset) - len(valid),
            "identity_decision_counts": {
                "true_accept": true_accept,
                "true_reject": true_reject,
                "false_accept": false_accept,
                "false_reject": false_reject,
            },
            "mismatch_detected_count": sum(record["mismatch_detected"] for record in valid),
            "missed_mismatch_count": sum(record["missed_mismatch"] for record in valid),
            "false_positive_valid_rejection_count": sum(record["false_positive_rejection"] for record in valid),
            "verification_cost_totals": {
                "wall_ms": sum(record["resources"]["verification_wall_ms"] for record in valid),
                "process_cpu_ms": sum(record["resources"]["verification_process_cpu_ms"] for record in valid),
                "registry_bytes_read": sum(record["resources"]["registry_bytes_read"] for record in valid),
                "git_tree_lookup_count": sum(record["resources"]["git_tree_lookup_count"] for record in valid),
                "terminal_record_bytes_excluding_self": sum(
                    record["resources"]["terminal_record_bytes_excluding_self"] for record in valid
                ),
            },
        }
    treatment = by_arm["registry-assert-v0"]
    control = by_arm["record-only-v0"]
    expected_per_arm = len(cases) * repetitions
    support_checks = {
        "valid_identity_passes_treatment": treatment["identity_decision_counts"]["true_accept"] == repetitions,
        "all_predefined_mismatches_fail_treatment": treatment["identity_decision_counts"]["true_reject"]
        == (len(cases) - 1) * repetitions,
        "control_misses_treatment_detected_mismatch": control["missed_mismatch_count"] > 0
        and treatment["mismatch_detected_count"] > 0,
        "deterministic_under_declared_horizon": not repeat_disagreements,
    }
    complete = len(records) == expected_per_arm * len(ARMS) and not any(
        record["episode_status"] == "invalid" for record in records
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "expected_record_count": expected_per_arm * len(ARMS),
        "complete_record_count": len(records),
        "run_status": "complete" if complete else "invalid",
        "arms": by_arm,
        "repeat_agreement": {
            "all_arm_case_pairs_agree": not repeat_disagreements,
            "disagreements": repeat_disagreements,
        },
        "support_checks": support_checks,
        "support_status": "Supported — task-local" if complete and all(support_checks.values()) else "Not established",
        "interpretation_boundary": "task-local harness-integrity evidence only; complete H-M1 is not established",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--challenges", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    challenges_path = resolve_repo_path(args.challenges, "--challenges")
    registry_path = resolve_repo_path(args.registry, "--registry")
    challenges, _challenge_bytes = load_json_bytes(challenges_path)
    cases, repetitions = validate_challenges(challenges)
    registry, _registry_bytes = load_json_bytes(registry_path)
    validate_registry(registry)
    if args.validate_only:
        print(f"definition validation: PASS ({len(cases)} cases, {len(ARMS)} arms, {repetitions} repetitions)")
        return 0
    if not args.output_dir or not args.run_id:
        parser.error("--output-dir and --run-id are required unless --validate-only is used")
    output_dir = resolve_repo_path(args.output_dir, "--output-dir")
    if not is_within(output_dir, RUNS_ROOT):
        raise DefinitionError("--output-dir must be under this experiment's runs directory")
    if output_dir.exists():
        raise DefinitionError(f"output directory already exists: {relative_posix(output_dir)}")

    code_commit = git_output("rev-parse", "HEAD")
    git_status_before = git_output("status", "--short")
    source_status_before = git_output("status", "--short", "--", "sources", "references/papers")
    registry_sha_before = sha256_file(registry_path)
    started_at = utc_now()
    output_dir.mkdir(parents=True)
    raw_path = output_dir / "raw" / "terminal-records.jsonl"
    raw_path.parent.mkdir()
    records: list[dict[str, Any]] = []
    with raw_path.open("w", encoding="utf-8", newline="\n") as stream:
        for arm in ARMS:
            for repetition in range(1, repetitions + 1):
                for case in cases:
                    record = run_case(arm, case, repetition, registry_path, code_commit)
                    record["run_id"] = args.run_id
                    records.append(record)
                    stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                    stream.flush()

    results = aggregate(records, cases, repetitions)
    results["run_id"] = args.run_id
    source_status_after = git_output("status", "--short", "--", "sources", "references/papers")
    registry_sha_after = sha256_file(registry_path)
    if source_status_before != source_status_after or source_status_after or registry_sha_before != registry_sha_after:
        results["run_status"] = "invalid"
        results["support_status"] = "Not established"
        results["source_preservation_failure"] = True
    else:
        results["source_preservation_failure"] = False
    manifest = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": args.run_id,
        "status": results["run_status"],
        "started_at": started_at,
        "finished_at": utc_now(),
        "command": [sys.executable, *sys.argv],
        "working_directory": str(ROOT),
        "git_commit": code_commit,
        "git_status_before": git_status_before.splitlines(),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "os_name": os.name,
        "distribution_id": challenges["distribution_id"],
        "challenge_path": relative_posix(challenges_path),
        "challenge_sha256": sha256_file(challenges_path),
        "registry_path": relative_posix(registry_path),
        "registry_format_observed": "JSON object encoded as UTF-8 despite .yaml extension",
        "registry_sha256_before": registry_sha_before,
        "registry_sha256_after": registry_sha_after,
        "source_status_before": source_status_before.splitlines(),
        "source_status_after": source_status_after.splitlines(),
        "arms": list(ARMS),
        "case_count": len(cases),
        "repetitions": repetitions,
        "expected_record_count": len(cases) * repetitions * len(ARMS),
        "network_access": False,
        "model_calls": 0,
        "token_usage": 0,
        "paid_cost_usd": 0.0,
        "credentials_used": False,
    }
    write_json(output_dir / "run-manifest.json", manifest)
    write_json(output_dir / "results.json", results)
    if results["run_status"] != "complete":
        write_json(
            output_dir / "failure.json",
            {
                "run_id": args.run_id,
                "status": "invalid",
                "reason": "one or more terminal records were invalid, incomplete, or source preservation failed",
                "completed_artifacts_must_not_be_cited": True,
            },
        )
    print(
        f"H-M1a run: {results['run_status'].upper()} "
        f"({len(records)}/{results['expected_record_count']} records, support={results['support_status']})"
    )
    return 0 if results["run_status"] == "complete" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DefinitionError, IdentityAssertionError, OSError, RuntimeError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"H-M1a run: FAIL ({exc})", file=sys.stderr)
        raise SystemExit(1)

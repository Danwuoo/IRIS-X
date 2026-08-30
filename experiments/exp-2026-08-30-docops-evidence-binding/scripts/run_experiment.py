#!/usr/bin/env python3
"""Run the H-V1b evidence/provenance-binding experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_snapshot_assertion import SourceSnapshotAssertionError  # noqa: E402
from tools.source_snapshot_assertion import assert_registered_source_snapshot  # noqa: E402


EXPERIMENT_ID = "exp-2026-08-30-docops-evidence-binding"
DISTRIBUTION_ID = "taskdist-2026-08-28-vanta-docops-readonly-12"
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = EXPERIMENT_ROOT / "runs"
ARMS = ("semantic-only-v0", "evidence-bound-v0")
VARIANTS = (
    "complete-correct",
    "missing-required-entry",
    "wrong-hash",
    "stale-hash",
    "crossed-evidence",
    "unrelated-existing-file",
    "conflicting-duplicate",
    "correct-hash-wrong-path",
)


class DefinitionError(ValueError):
    """Raised when a frozen definition or execution boundary is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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
    path = (ROOT / value).resolve()
    if not is_within(path, ROOT):
        raise DefinitionError(f"{label} escapes repository: {value}")
    return path


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def declared_requirements(task: dict[str, Any]) -> list[dict[str, str]]:
    requirements: list[dict[str, str]] = []
    for index, artifact in enumerate(task.get("input_artifacts", [])):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            raise DefinitionError(f"{task.get('task_id')}: invalid input_artifacts[{index}]")
        requirements.append(
            {
                "path": artifact["path"].replace("\\", "/"),
                "role": str(artifact.get("role", "unknown")),
            }
        )
    if not requirements:
        raise DefinitionError(f"{task.get('task_id')}: no declared input artifacts")
    return requirements


def actual_input_snapshot(fixture: Path, requirements: list[dict[str, str]]) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for requirement in requirements:
        path = (fixture / requirement["path"]).resolve()
        if not is_within(path, fixture) or not path.is_file():
            raise DefinitionError(f"declared input is missing or escapes fixture: {requirement['path']}")
        payload = path.read_bytes()
        snapshot.append(
            {
                "path": requirement["path"],
                "role": requirement["role"],
                "sha256": sha256_bytes(payload),
                "bytes": len(payload),
            }
        )
    return snapshot


def adjudicate_actual_outcome(
    fixture: Path,
    expected_relative_path: str,
    producer_output_json: str,
    snapshot_before: list[dict[str, Any]],
    snapshot_after: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """Adjudicate actual outcome without consuming evidence-verifier output."""
    if snapshot_before != snapshot_after:
        return "failure", ["input_mutation_detected"]
    try:
        produced = json.loads(producer_output_json)
    except json.JSONDecodeError:
        return "failure", ["malformed_json"]
    expected_path = (fixture / expected_relative_path).resolve()
    if not is_within(expected_path, fixture) or not expected_path.is_file():
        raise DefinitionError("expected path is missing or escapes fixture")
    expected = load_json(expected_path)
    return ("success", []) if isinstance(produced, dict) and produced == expected else (
        "failure",
        ["semantic_oracle_mismatch"],
    )


def semantic_verifier_decision(
    fixture: Path,
    expected_relative_path: str,
    producer_output_json: str,
) -> tuple[str, str]:
    """Verify semantic output only; evidence fields are deliberately absent."""
    expected_path = (fixture / expected_relative_path).resolve()
    if not is_within(expected_path, fixture) or not expected_path.is_file():
        raise DefinitionError("semantic verifier expected path is missing or escapes fixture")
    try:
        produced = json.loads(producer_output_json)
    except json.JSONDecodeError:
        return "reject", "malformed_json"
    expected = load_json(expected_path)
    return ("accept", "semantic_oracle_match") if produced == expected else (
        "reject",
        "semantic_oracle_mismatch",
    )


def evidence_binding_decision(
    fixture: Path,
    required_inputs: list[dict[str, str]],
    supplied_evidence: list[dict[str, Any]],
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Recompute real paths/hashes and decide sufficiency without challenge labels."""
    reasons: list[str] = []
    observations: list[dict[str, Any]] = []
    required_by_path = {item["path"]: item for item in required_inputs}
    if len(required_by_path) != len(required_inputs):
        raise DefinitionError("declared input paths must be unique")
    if not isinstance(supplied_evidence, list):
        return "insufficient", ["evidence_envelope_not_list"], observations

    seen: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, entry in enumerate(supplied_evidence):
        if not isinstance(entry, dict):
            reasons.append("entry_not_object")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            reasons.append("path_invalid")
            continue
        normalized = relative.replace("\\", "/")
        seen[normalized].append(entry)
        candidate = (fixture / normalized).resolve()
        observation: dict[str, Any] = {"entry_index": index, "path": normalized}
        if not is_within(candidate, fixture):
            observation["path_status"] = "outside_fixture"
            reasons.append("path_outside_fixture")
            observations.append(observation)
            continue
        if not candidate.is_file():
            observation["path_status"] = "missing"
            reasons.append("path_missing")
            observations.append(observation)
            continue
        payload = candidate.read_bytes()
        actual_hash = sha256_bytes(payload)
        observation.update(
            {
                "path_status": "existing_file",
                "actual_sha256": actual_hash,
                "actual_bytes": len(payload),
                "declared_input": normalized in required_by_path,
            }
        )
        if normalized not in required_by_path:
            reasons.append("undeclared_input_path")
        else:
            requirement = required_by_path[normalized]
            if entry.get("role") != requirement["role"]:
                reasons.append("role_mismatch")
        if entry.get("sha256") != actual_hash:
            reasons.append("hash_mismatch")
        if entry.get("bytes") != len(payload):
            reasons.append("byte_count_mismatch")
        observations.append(observation)

    for path in required_by_path:
        entries = seen.get(path, [])
        if not entries:
            reasons.append("missing_required_entry")
        elif len(entries) > 1:
            signatures = {
                (entry.get("role"), entry.get("sha256"), entry.get("bytes"))
                for entry in entries
                if isinstance(entry, dict)
            }
            reasons.append("conflicting_duplicate" if len(signatures) > 1 else "duplicate_entry")

    unique_reasons = sorted(set(reasons))
    if not unique_reasons:
        return "sufficient", ["complete_correct_binding"], observations
    missing_only = set(unique_reasons) <= {"missing_required_entry"}
    return ("insufficient" if missing_only else "invalid_binding"), unique_reasons, observations


def validate_challenges(document: Any) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise DefinitionError("challenge schema_version must be 1")
    if document.get("experiment_id") != EXPERIMENT_ID or document.get("distribution_id") != DISTRIBUTION_ID:
        raise DefinitionError("challenge experiment/distribution identity mismatch")
    if document.get("source_id") != "src.vanta" or not isinstance(document.get("source_snapshot_id"), str):
        raise DefinitionError("challenge source identity is invalid")
    if document.get("variant_order") != list(VARIANTS):
        raise DefinitionError("challenge variant order mismatch")
    repetitions = document.get("repetitions")
    if repetitions != 3 or isinstance(repetitions, bool):
        raise DefinitionError("challenge repetitions must be exactly 3")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 96 or document.get("case_count") != 96:
        raise DefinitionError("challenge artifact must contain exactly 96 cases")
    seen: set[str] = set()
    per_task: dict[str, set[str]] = defaultdict(set)
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict) or case.get("case_order") != index:
            raise DefinitionError(f"challenge case order invalid at index {index}")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise DefinitionError(f"challenge case ID invalid/duplicated at index {index}")
        seen.add(case_id)
        variant = case.get("challenge_metadata", {}).get("variant_id")
        if variant not in VARIANTS:
            raise DefinitionError(f"{case_id}: variant invalid")
        per_task[str(case.get("task_id"))].add(variant)
        if case.get("system_claim") != "success":
            raise DefinitionError(f"{case_id}: every system claim must be success")
        output_json = case.get("producer_output_json")
        if not isinstance(output_json, str):
            raise DefinitionError(f"{case_id}: producer output must be frozen JSON text")
        output_payload = output_json.encode("utf-8")
        if sha256_bytes(output_payload) != case.get("producer_output_sha256") or len(output_payload) != case.get(
            "producer_output_bytes"
        ):
            raise DefinitionError(f"{case_id}: producer output hash/size mismatch")
        evidence = case.get("supplied_evidence")
        if not isinstance(evidence, list) or sha256_bytes(canonical_json_bytes(evidence)) != case.get(
            "evidence_envelope_sha256"
        ):
            raise DefinitionError(f"{case_id}: evidence envelope hash mismatch")
        fixture = resolve_repo_path(case.get("fixture_path"), f"{case_id}.fixture_path")
        if not is_within(fixture, ROOT / "sources" / "predecessors" / "vanta"):
            raise DefinitionError(f"{case_id}: fixture outside VANTA source boundary")
        task_path = fixture / "task.json"
        expected_path = (fixture / case.get("expected_path", "")).resolve()
        if sha256_file(task_path) != case.get("task_sha256") or sha256_file(expected_path) != case.get(
            "expected_sha256"
        ):
            raise DefinitionError(f"{case_id}: task/oracle bytes differ from frozen challenge")
        if json.loads(output_json) != load_json(expected_path):
            raise DefinitionError(f"{case_id}: every producer output must remain semantically correct")
    if len(per_task) != 12 or any(variants != set(VARIANTS) for variants in per_task.values()):
        raise DefinitionError("every task must contain exactly all eight variants")
    expected_construction = {
        "task_count": 12,
        "cases_per_task": 8,
        "all_producer_outputs_semantically_correct": True,
    }
    if document.get("construction_validation") != expected_construction:
        raise DefinitionError("challenge construction validation mismatch")
    return cases, repetitions


def build_terminal_record(
    *,
    run_id: str,
    arm: str,
    case: dict[str, Any],
    repetition: int,
    actual_outcome: str,
    actual_reasons: list[str],
    semantic_decision: str,
    semantic_reason: str,
    snapshot_before: list[dict[str, Any]],
    snapshot_after: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_status = "not_assessed"
    evidence_reasons = ["semantic_only_policy"]
    evidence_observations: list[dict[str, Any]] = []
    evidence_wall_ms = 0.0
    evidence_cpu_ms = 0.0
    if arm == "evidence-bound-v0":
        fixture = resolve_repo_path(case["fixture_path"], f"{case['case_id']}.fixture_path")
        task = load_json(fixture / "task.json")
        requirements = declared_requirements(task)
        wall_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()
        evidence_status, evidence_reasons, evidence_observations = evidence_binding_decision(
            fixture,
            requirements,
            case["supplied_evidence"],
        )
        evidence_cpu_ms = (time.process_time_ns() - cpu_start) / 1_000_000
        evidence_wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000

    eligible = (
        case["system_claim"] == "success"
        and semantic_decision == "accept"
        and (arm == "semantic-only-v0" or evidence_status == "sufficient")
    )
    joint_status = "verified_success" if eligible else "unverified_success"
    decision_artifact = {
        "semantic_decision": semantic_decision,
        "evidence_status": evidence_status,
        "evidence_reasons": evidence_reasons,
        "verified_success_eligible": eligible,
        "joint_status": joint_status,
    }
    record = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "arm": arm,
        "case_id": case["case_id"],
        "case_order": case["case_order"],
        "task_id": case["task_id"],
        "task_order": case["task_order"],
        "variant_id": case["challenge_metadata"]["variant_id"],
        "repetition": repetition,
        "producer_output_json": case["producer_output_json"],
        "producer_output_sha256": case["producer_output_sha256"],
        "producer_output_bytes": case["producer_output_bytes"],
        "system_claim": case["system_claim"],
        "supplied_evidence": case["supplied_evidence"],
        "evidence_envelope_sha256": case["evidence_envelope_sha256"],
        "actual_outcome": actual_outcome,
        "actual_outcome_reasons": actual_reasons,
        "semantic_verifier": {"decision": semantic_decision, "reason": semantic_reason},
        "evidence_verifier": {
            "status": evidence_status,
            "reasons": evidence_reasons,
            "path_hash_observations": evidence_observations,
        },
        "verified_success_eligible": eligible,
        "joint_status": joint_status,
        "input_snapshot_before": snapshot_before,
        "input_snapshot_after": snapshot_after,
        "episode_status": "valid" if actual_outcome == "success" and snapshot_before == snapshot_after else "invalid",
        "resources": {
            "evidence_verification_wall_ms": evidence_wall_ms,
            "evidence_verification_process_cpu_ms": evidence_cpu_ms,
            "evidence_artifact_bytes": len(canonical_json_bytes(case["supplied_evidence"])),
            "decision_artifact_bytes": len(canonical_json_bytes(decision_artifact)),
            "producer_output_bytes": case["producer_output_bytes"],
            "model_calls": 0,
            "model_api_cost_usd": 0.0,
        },
    }
    record["resources"]["terminal_record_bytes_excluding_self"] = len(canonical_json_bytes(record))
    return record


def aggregate(records: list[dict[str, Any]], cases: list[dict[str, Any]], repetitions: int) -> dict[str, Any]:
    by_arm: dict[str, Any] = {}
    for arm in ARMS:
        subset = [record for record in records if record["arm"] == arm]
        valid = [record for record in subset if record["episode_status"] == "valid"]
        reasons = Counter(
            reason
            for record in valid
            for reason in record["evidence_verifier"]["reasons"]
        )
        by_arm[arm] = {
            "attempted_records": len(subset),
            "valid_records": len(valid),
            "invalid_records": len(subset) - len(valid),
            "actual_success_count": sum(record["actual_outcome"] == "success" for record in valid),
            "verified_success_eligible_count": sum(record["verified_success_eligible"] for record in valid),
            "unverified_success_count": sum(record["joint_status"] == "unverified_success" for record in valid),
            "evidence_status_counts": dict(sorted(Counter(
                record["evidence_verifier"]["status"] for record in valid
            ).items())),
            "evidence_reason_counts": dict(sorted(reasons.items())),
            "false_verified_success_acceptance": sum(
                record["variant_id"] != "complete-correct" and record["verified_success_eligible"]
                for record in valid
            ),
            "false_rejection_complete_correct": sum(
                record["variant_id"] == "complete-correct" and not record["verified_success_eligible"]
                for record in valid
            ),
            "resource_totals": {
                "evidence_verification_wall_ms": sum(
                    record["resources"]["evidence_verification_wall_ms"] for record in valid
                ),
                "evidence_verification_process_cpu_ms": sum(
                    record["resources"]["evidence_verification_process_cpu_ms"] for record in valid
                ),
                "evidence_artifact_bytes": sum(record["resources"]["evidence_artifact_bytes"] for record in valid),
                "decision_artifact_bytes": sum(record["resources"]["decision_artifact_bytes"] for record in valid),
                "terminal_record_bytes_excluding_self": sum(
                    record["resources"]["terminal_record_bytes_excluding_self"] for record in valid
                ),
            },
        }

    paired_mismatches: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        for case in cases:
            pair = [
                record for record in records
                if record["case_id"] == case["case_id"] and record["repetition"] == repetition
            ]
            if len(pair) != 2:
                paired_mismatches.append({"case_id": case["case_id"], "repetition": repetition, "reason": "pair_count"})
                continue
            fields = (
                "task_id",
                "producer_output_sha256",
                "system_claim",
                "evidence_envelope_sha256",
                "actual_outcome",
                "semantic_verifier",
                "input_snapshot_before",
                "input_snapshot_after",
            )
            differing = [field for field in fields if pair[0][field] != pair[1][field]]
            if differing:
                paired_mismatches.append(
                    {"case_id": case["case_id"], "repetition": repetition, "reason": "fixed_fields", "fields": differing}
                )

    repeat_disagreements: list[dict[str, str]] = []
    for arm in ARMS:
        for case in cases:
            subset = [record for record in records if record["arm"] == arm and record["case_id"] == case["case_id"]]
            signatures = {
                (
                    record["actual_outcome"],
                    record["semantic_verifier"]["decision"],
                    record["evidence_verifier"]["status"],
                    tuple(record["evidence_verifier"]["reasons"]),
                    record["verified_success_eligible"],
                )
                for record in subset
            }
            if len(subset) != repetitions or len(signatures) != 1:
                repeat_disagreements.append({"arm": arm, "case_id": case["case_id"]})

    treatment = [record for record in records if record["arm"] == "evidence-bound-v0"]
    complete = len(records) == len(cases) * repetitions * len(ARMS) and not any(
        record["episode_status"] != "valid" for record in records
    )
    support_checks = {
        "complete_correct_accepted": all(
            record["verified_success_eligible"]
            for record in treatment
            if record["variant_id"] == "complete-correct"
        ),
        "all_invalid_variants_denied": all(
            not record["verified_success_eligible"]
            for record in treatment
            if record["variant_id"] != "complete-correct"
        ),
        "actual_outcome_success_and_arm_invariant": not paired_mismatches and all(
            record["actual_outcome"] == "success" for record in records
        ),
        "semantic_verifier_accept_and_arm_invariant": not paired_mismatches and all(
            record["semantic_verifier"]["decision"] == "accept" for record in records
        ),
        "challenge_validity_labels_excluded_from_treatment_interface": True,
        "repeat_agreement": not repeat_disagreements,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "expected_record_count": len(cases) * repetitions * len(ARMS),
        "complete_record_count": len(records),
        "run_status": "complete" if complete and not paired_mismatches else "invalid",
        "arms": by_arm,
        "paired_invariance": {"all_fixed_fields_identical": not paired_mismatches, "mismatches": paired_mismatches},
        "repeat_agreement": {"all_arm_case_pairs_agree": not repeat_disagreements, "disagreements": repeat_disagreements},
        "support_checks": support_checks,
        "support_status": (
            "Supported — task-local"
            if complete and not paired_mismatches and all(support_checks.values())
            else "Not established"
        ),
        "verifier_interfaces": {
            "semantic_verifier_fields": ["fixture", "expected_relative_path", "producer_output_json"],
            "evidence_verifier_fields": ["fixture", "required_inputs", "supplied_evidence"],
            "excluded_from_evidence_verifier": [
                "case_id",
                "variant_id",
                "challenge_metadata",
                "expected_evidence_validity",
                "actual_outcome",
                "semantic_verifier_decision",
            ],
        },
        "interpretation_boundary": "frozen development tasks and path/hash evidence variants only; parent H-V1 not established",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--challenges", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    challenge_path = resolve_repo_path(args.challenges, "--challenges")
    registry_path = resolve_repo_path(args.registry, "--registry")
    challenge = load_json(challenge_path)
    cases, repetitions = validate_challenges(challenge)
    code_commit = git_output("rev-parse", "HEAD")
    try:
        source_identity = assert_registered_source_snapshot(
            ROOT,
            registry_path,
            challenge["source_id"],
            challenge["source_snapshot_id"],
            code_commit,
        )
    except SourceSnapshotAssertionError as exc:
        raise DefinitionError(f"source snapshot assertion failed [{exc.code}]: {exc}") from exc
    if args.validate_only:
        print(
            f"definition validation: PASS (96 cases, 2 arms, 3 repetitions, source tree {source_identity.observed_tree_oid})"
        )
        return 0
    if not args.output_dir or not args.run_id:
        parser.error("--output-dir and --run-id are required unless --validate-only is used")
    output_dir = resolve_repo_path(args.output_dir, "--output-dir")
    if not is_within(output_dir, RUNS_ROOT):
        raise DefinitionError("--output-dir must be under this experiment's runs directory")
    if output_dir.exists():
        raise DefinitionError(f"output directory already exists: {relative_posix(output_dir)}")

    started_at = utc_now()
    git_status_before = git_output("status", "--short")
    source_status_before = git_output("status", "--short", "--", "sources", "references/papers")
    registry_sha_before = sha256_file(registry_path)
    output_dir.mkdir(parents=True)
    raw_path = output_dir / "raw" / "terminal-records.jsonl"
    raw_path.parent.mkdir()
    records: list[dict[str, Any]] = []
    with raw_path.open("w", encoding="utf-8", newline="\n") as stream:
        for repetition in range(1, repetitions + 1):
            for case in cases:
                fixture = resolve_repo_path(case["fixture_path"], f"{case['case_id']}.fixture_path")
                task = load_json(fixture / "task.json")
                requirements = declared_requirements(task)
                snapshot_before = actual_input_snapshot(fixture, requirements)
                snapshot_after_for_actual = actual_input_snapshot(fixture, requirements)
                actual_outcome, actual_reasons = adjudicate_actual_outcome(
                    fixture,
                    case["expected_path"],
                    case["producer_output_json"],
                    snapshot_before,
                    snapshot_after_for_actual,
                )
                semantic_decision, semantic_reason = semantic_verifier_decision(
                    fixture,
                    case["expected_path"],
                    case["producer_output_json"],
                )
                for arm in ARMS:
                    snapshot_after = actual_input_snapshot(fixture, requirements)
                    record = build_terminal_record(
                        run_id=args.run_id,
                        arm=arm,
                        case=case,
                        repetition=repetition,
                        actual_outcome=actual_outcome,
                        actual_reasons=actual_reasons,
                        semantic_decision=semantic_decision,
                        semantic_reason=semantic_reason,
                        snapshot_before=snapshot_before,
                        snapshot_after=snapshot_after,
                    )
                    records.append(record)
                    stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                    stream.flush()

    results = aggregate(records, cases, repetitions)
    results["run_id"] = args.run_id
    results["raw_terminal_artifact_bytes"] = raw_path.stat().st_size
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
        "distribution_id": challenge["distribution_id"],
        "contract_id": challenge["contract_id"],
        "challenge_path": relative_posix(challenge_path),
        "challenge_sha256": sha256_file(challenge_path),
        "challenge_case_count": len(cases),
        "challenge_frozen_before_run": True,
        "registry_path": relative_posix(registry_path),
        "registry_sha256_before": registry_sha_before,
        "registry_sha256_after": registry_sha_after,
        "source_id": source_identity.source_id,
        "source_snapshot_id": source_identity.snapshot_id,
        "source_registered_path": source_identity.source_path,
        "source_registered_tree_oid": source_identity.registered_tree_oid,
        "source_tree_oid_at_code_commit": source_identity.observed_tree_oid,
        "source_snapshot_assertion": "passed",
        "source_status_before": source_status_before.splitlines(),
        "source_status_after": source_status_after.splitlines(),
        "arms": list(ARMS),
        "repetitions": repetitions,
        "expected_record_count": len(cases) * repetitions * len(ARMS),
        "evidence_verifier_interface_fields": ["fixture", "required_inputs", "supplied_evidence"],
        "challenge_validity_labels_passed_to_evidence_verifier": False,
        "network_access": False,
        "model_calls": 0,
        "token_usage": 0,
        "paid_cost_usd": 0.0,
        "credentials_used": False,
        "retries": 0,
        "recoveries": 0,
    }
    write_json(output_dir / "run-manifest.json", manifest)
    write_json(output_dir / "results.json", results)
    if results["run_status"] != "complete":
        write_json(
            output_dir / "failure.json",
            {
                "run_id": args.run_id,
                "status": "invalid",
                "reason": "incomplete/invalid records, invariance failure, or source-preservation failure",
                "completed_artifacts_must_not_be_cited": True,
            },
        )
    print(
        f"H-V1b run: {results['run_status'].upper()} "
        f"({len(records)}/{results['expected_record_count']} records, support={results['support_status']})"
    )
    return 0 if results["run_status"] == "complete" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DefinitionError, OSError, RuntimeError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"H-V1b run: FAIL ({exc})", file=sys.stderr)
        raise SystemExit(1)

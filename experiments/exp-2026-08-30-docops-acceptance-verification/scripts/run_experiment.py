#!/usr/bin/env python3
"""Run the H-V1a independent acceptance-verification experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_snapshot_assertion import SourceSnapshotAssertionError  # noqa: E402
from tools.source_snapshot_assertion import assert_registered_source_snapshot  # noqa: E402


EXPERIMENT_ID = "exp-2026-08-30-docops-acceptance-verification"
DISTRIBUTION_ID = "taskdist-2026-08-28-vanta-docops-readonly-12"
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = EXPERIMENT_ROOT / "runs"
ARMS = ("claim-only-v0", "independent-verify-v0")
VARIANTS = (
    "canonical-valid",
    "semantic-equivalent-valid",
    "omission-invalid",
    "fabrication-invalid",
    "corruption-invalid",
)


class DefinitionError(ValueError):
    """Raised when the frozen challenge or experiment boundary is invalid."""


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


def declared_input_snapshot(fixture: Path, task: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for index, artifact in enumerate(task.get("input_artifacts", [])):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            raise DefinitionError(f"{task.get('task_id')}: invalid input_artifacts[{index}]")
        relative = artifact["path"].replace("\\", "/")
        path = (fixture / relative).resolve()
        if not is_within(path, fixture) or not path.is_file():
            raise DefinitionError(f"{task.get('task_id')}: input path missing or escaping fixture: {relative}")
        payload = path.read_bytes()
        snapshot.append(
            {
                "path": relative,
                "role": str(artifact.get("role", "unknown")),
                "sha256": sha256_bytes(payload),
                "bytes": len(payload),
            }
        )
    if not snapshot:
        raise DefinitionError(f"{task.get('task_id')}: no declared input artifacts")
    return snapshot


def has_exact_overlap(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict) and isinstance(actual, dict):
        return any(key in actual and has_exact_overlap(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list) and isinstance(actual, list):
        return any(item in actual for item in expected)
    return expected == actual


def adjudicate_actual_outcome(
    fixture: Path,
    expected_relative_path: str,
    producer_output_json: str,
    snapshot_before: list[dict[str, Any]],
    snapshot_after: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """Independently adjudicate task outcome; never consume verifier output."""
    reasons: list[str] = []
    if snapshot_before != snapshot_after:
        return "failure", ["input_mutation_detected"]
    try:
        produced = json.loads(producer_output_json)
    except json.JSONDecodeError:
        return "failure", ["malformed_json"]
    expected = load_json((fixture / expected_relative_path).resolve())
    if not isinstance(produced, dict):
        return "failure", ["unexpected_top_level_shape"]
    if produced == expected:
        return "success", reasons
    if has_exact_overlap(expected, produced):
        return "partial", ["observation_incomplete_or_contains_incorrect_additions"]
    return "failure", ["no_correct_required_observation"]


def independent_verifier_decision(
    fixture: Path,
    expected_relative_path: str,
    producer_output_json: str,
) -> tuple[str, str]:
    """Verify output against the declared oracle without any challenge label."""
    try:
        produced = json.loads(producer_output_json)
    except json.JSONDecodeError:
        return "reject", "malformed_json"
    expected_path = (fixture / expected_relative_path).resolve()
    if not is_within(expected_path, fixture) or not expected_path.is_file():
        raise DefinitionError("verifier expected path is missing or escapes fixture")
    expected = load_json(expected_path)
    if not isinstance(produced, dict):
        return "reject", "unexpected_top_level_shape"
    return ("accept", "semantic_oracle_match") if produced == expected else ("reject", "semantic_oracle_mismatch")


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
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions != 3:
        raise DefinitionError("challenge repetitions must be exactly 3")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 60 or document.get("case_count") != 60:
        raise DefinitionError("challenge artifact must contain exactly 60 cases")
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
        relation = case.get("challenge_metadata", {}).get("expected_semantic_relation")
        if variant not in VARIANTS or relation not in {"equal", "unequal"}:
            raise DefinitionError(f"{case_id}: challenge metadata invalid")
        per_task[str(case.get("task_id"))].add(variant)
        if case.get("system_claim") != "success":
            raise DefinitionError(f"{case_id}: every frozen system claim must be success")
        output_json = case.get("producer_output_json")
        if not isinstance(output_json, str):
            raise DefinitionError(f"{case_id}: producer output must be frozen JSON text")
        output_bytes = output_json.encode("utf-8")
        if sha256_bytes(output_bytes) != case.get("producer_output_sha256") or len(output_bytes) != case.get(
            "producer_output_bytes"
        ):
            raise DefinitionError(f"{case_id}: producer output hash/size mismatch")
        fixture = resolve_repo_path(case.get("fixture_path"), f"{case_id}.fixture_path")
        if not is_within(fixture, ROOT / "sources" / "predecessors" / "vanta"):
            raise DefinitionError(f"{case_id}: fixture is outside VANTA source boundary")
        task_path = fixture / "task.json"
        expected_path = (fixture / case.get("expected_path", "")).resolve()
        if sha256_file(task_path) != case.get("task_sha256") or sha256_file(expected_path) != case.get(
            "expected_sha256"
        ):
            raise DefinitionError(f"{case_id}: task/oracle bytes differ from frozen challenge")
        task = load_json(task_path)
        observed_evidence = declared_input_snapshot(fixture, task)
        if observed_evidence != case.get("evidence") or sha256_bytes(canonical_json_bytes(observed_evidence)) != case.get(
            "evidence_envelope_sha256"
        ):
            raise DefinitionError(f"{case_id}: complete evidence/path-hash substrate differs")
        parsed = json.loads(output_json)
        expected = load_json(expected_path)
        observed_relation = "equal" if parsed == expected else "unequal"
        if observed_relation != relation:
            raise DefinitionError(f"{case_id}: frozen semantic relation is invalid")
    if len(per_task) != 12 or any(variants != set(VARIANTS) for variants in per_task.values()):
        raise DefinitionError("every task must have exactly the five declared variants")
    validation = document.get("construction_validation")
    if validation != {
        "semantic_equal_case_count": 24,
        "semantic_unequal_case_count": 36,
        "all_relations_verified_before_freeze": True,
    }:
        raise DefinitionError("challenge construction validation summary mismatch")
    return cases, repetitions


def decision_category(actual_outcome: str, acceptance_decision: str) -> str:
    actual_valid = actual_outcome == "success"
    accepted = acceptance_decision == "accept"
    if actual_valid and accepted:
        return "true_accept"
    if not actual_valid and not accepted:
        return "true_reject"
    if not actual_valid and accepted:
        return "false_accept"
    return "false_reject"


def build_terminal_record(
    *,
    run_id: str,
    arm: str,
    case: dict[str, Any],
    repetition: int,
    actual_outcome: str,
    actual_reasons: list[str],
    actual_wall_ms: float,
    evidence_status: str,
    snapshot_before: list[dict[str, Any]],
    snapshot_after: list[dict[str, Any]],
) -> dict[str, Any]:
    verifier_decision = "not_invoked"
    verifier_reason = "claim_only_policy"
    verifier_wall_ms = 0.0
    verifier_cpu_ms = 0.0
    verifier_status = "not_applicable"
    fixture = resolve_repo_path(case["fixture_path"], f"{case['case_id']}.fixture_path")
    if arm == "independent-verify-v0":
        wall_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()
        try:
            verifier_decision, verifier_reason = independent_verifier_decision(
                fixture,
                case["expected_path"],
                case["producer_output_json"],
            )
            verifier_status = "valid"
        except Exception as exc:  # retain verifier failure separately
            verifier_decision = "invalid"
            verifier_reason = f"{type(exc).__name__}: {exc}"
            verifier_status = "invalid"
        verifier_cpu_ms = (time.process_time_ns() - cpu_start) / 1_000_000
        verifier_wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000
    acceptance = (
        "accept"
        if case["system_claim"] == "success"
        and (arm == "claim-only-v0" or verifier_decision == "accept")
        else "reject"
    )
    category = decision_category(actual_outcome, acceptance)
    decision_artifact = {
        "system_claim": case["system_claim"],
        "verifier_decision": verifier_decision,
        "verifier_reason": verifier_reason,
        "acceptance_decision": acceptance,
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
        "stratum": case["stratum"],
        "output_kind": case["output_kind"],
        "variant_id": case["challenge_metadata"]["variant_id"],
        "repetition": repetition,
        "producer_output_json": case["producer_output_json"],
        "producer_output_sha256": case["producer_output_sha256"],
        "producer_output_bytes": case["producer_output_bytes"],
        "system_claim": case["system_claim"],
        "evidence": case["evidence"],
        "evidence_envelope_sha256": case["evidence_envelope_sha256"],
        "evidence_status": evidence_status,
        "actual_outcome": actual_outcome,
        "actual_outcome_reasons": actual_reasons,
        "acceptance_decision": acceptance,
        "decision_category": category,
        "independent_verifier": {
            "status": verifier_status,
            "decision": verifier_decision,
            "reason": verifier_reason,
        },
        "input_snapshot_before": snapshot_before,
        "input_snapshot_after": snapshot_after,
        "episode_status": "valid" if evidence_status == "sufficient" and snapshot_before == snapshot_after else "invalid",
        "resources": {
            "paired_actual_adjudication_wall_ms": actual_wall_ms,
            "verification_wall_ms": verifier_wall_ms,
            "verification_process_cpu_ms": verifier_cpu_ms,
            "producer_output_bytes": case["producer_output_bytes"],
            "verification_decision_artifact_bytes": len(canonical_json_bytes(decision_artifact)),
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
        counts = {name: sum(record["decision_category"] == name for record in valid) for name in (
            "true_accept", "true_reject", "false_accept", "false_reject"
        )}
        by_arm[arm] = {
            "attempted_records": len(subset),
            "valid_records": len(valid),
            "invalid_records": len(subset) - len(valid),
            "decision_counts": counts,
            "finite_sample_rates": {
                name: counts[name] / len(valid) if valid else None for name in counts
            },
            "accepted_success_count": sum(record["acceptance_decision"] == "accept" for record in valid),
            "rejected_success_count": sum(record["acceptance_decision"] == "reject" for record in valid),
            "verifier_error_invalid_count": sum(
                record["independent_verifier"]["status"] == "invalid" for record in subset
            ),
            "verification_cost_totals": {
                "wall_ms": sum(record["resources"]["verification_wall_ms"] for record in valid),
                "process_cpu_ms": sum(record["resources"]["verification_process_cpu_ms"] for record in valid),
                "producer_output_bytes": sum(record["resources"]["producer_output_bytes"] for record in valid),
                "verification_decision_artifact_bytes": sum(
                    record["resources"]["verification_decision_artifact_bytes"] for record in valid
                ),
                "terminal_record_bytes_excluding_self": sum(
                    record["resources"]["terminal_record_bytes_excluding_self"] for record in valid
                ),
            },
        }
    paired_mismatches: list[dict[str, Any]] = []
    repeat_disagreements: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        for case in cases:
            pair = [
                record for record in records
                if record["case_id"] == case["case_id"] and record["repetition"] == repetition
            ]
            if len(pair) != 2:
                paired_mismatches.append({"case_id": case["case_id"], "repetition": repetition, "reason": "pair_count"})
                continue
            fixed_fields = (
                "task_id",
                "producer_output_sha256",
                "system_claim",
                "evidence_envelope_sha256",
                "evidence_status",
                "actual_outcome",
                "input_snapshot_before",
                "input_snapshot_after",
            )
            differing = [field for field in fixed_fields if pair[0][field] != pair[1][field]]
            if differing:
                paired_mismatches.append(
                    {"case_id": case["case_id"], "repetition": repetition, "reason": "fixed_fields", "fields": differing}
                )
    for arm in ARMS:
        for case in cases:
            subset = [record for record in records if record["arm"] == arm and record["case_id"] == case["case_id"]]
            signatures = {
                (record["actual_outcome"], record["acceptance_decision"], record["independent_verifier"]["decision"])
                for record in subset
            }
            if len(subset) != repetitions or len(signatures) != 1:
                repeat_disagreements.append({"arm": arm, "case_id": case["case_id"]})
    treatment_valid_variants = [
        record for record in records
        if record["arm"] == "independent-verify-v0"
        and record["variant_id"] in {"canonical-valid", "semantic-equivalent-valid"}
    ]
    complete = len(records) == len(cases) * repetitions * len(ARMS) and not any(
        record["episode_status"] == "invalid" for record in records
    )
    support_checks = {
        "treatment_false_accepts_lower_than_control": by_arm["independent-verify-v0"]["decision_counts"]["false_accept"]
        < by_arm["claim-only-v0"]["decision_counts"]["false_accept"],
        "canonical_valid_outputs_not_newly_rejected": not any(
            record["variant_id"] == "canonical-valid" and record["acceptance_decision"] != "accept"
            for record in treatment_valid_variants
        ),
        "semantic_equivalent_valid_outputs_not_newly_rejected": not any(
            record["variant_id"] == "semantic-equivalent-valid" and record["acceptance_decision"] != "accept"
            for record in treatment_valid_variants
        ),
        "paired_actual_outcomes_identical": not paired_mismatches,
        "challenge_labels_excluded_from_verifier_interface": True,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "expected_record_count": len(cases) * repetitions * len(ARMS),
        "complete_record_count": len(records),
        "run_status": "complete" if complete and not paired_mismatches else "invalid",
        "arms": by_arm,
        "paired_invariance": {
            "paired_actual_outcome_and_fixed_fields_identical": not paired_mismatches,
            "mismatches": paired_mismatches,
        },
        "repeat_agreement": {
            "all_arm_case_pairs_agree": not repeat_disagreements,
            "disagreements": repeat_disagreements,
        },
        "support_checks": support_checks,
        "support_status": (
            "Supported — task-local"
            if complete and not paired_mismatches and all(support_checks.values())
            else "Not established"
        ),
        "verifier_interface": {
            "passed_fields": ["fixture", "expected_relative_path", "producer_output_json"],
            "excluded_fields": [
                "actual_outcome",
                "challenge_metadata",
                "expected_semantic_relation",
                "expected_acceptance_label",
                "invalid_case_flag",
            ],
        },
        "interpretation_boundary": "fixed oracle-backed development challenges; H-V1b and general verifier reliability not evaluated",
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
            f"definition validation: PASS (60 cases, 2 arms, 3 repetitions, source tree {source_identity.observed_tree_oid})"
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
                snapshot_before = declared_input_snapshot(fixture, task)
                evidence_status = "sufficient" if snapshot_before == case["evidence"] else "insufficient"
                actual_start = time.perf_counter_ns()
                snapshot_after_for_actual = declared_input_snapshot(fixture, task)
                actual_outcome, actual_reasons = adjudicate_actual_outcome(
                    fixture,
                    case["expected_path"],
                    case["producer_output_json"],
                    snapshot_before,
                    snapshot_after_for_actual,
                )
                actual_wall_ms = (time.perf_counter_ns() - actual_start) / 1_000_000
                for arm in ARMS:
                    snapshot_after = declared_input_snapshot(fixture, task)
                    record = build_terminal_record(
                        run_id=args.run_id,
                        arm=arm,
                        case=case,
                        repetition=repetition,
                        actual_outcome=actual_outcome,
                        actual_reasons=actual_reasons,
                        actual_wall_ms=actual_wall_ms,
                        evidence_status=evidence_status,
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
        "verifier_interface_fields": ["fixture", "expected_relative_path", "producer_output_json"],
        "challenge_labels_passed_to_verifier": False,
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
                "reason": "incomplete/invalid records, paired-invariance failure, or source-preservation failure",
                "completed_artifacts_must_not_be_cited": True,
            },
        )
    print(
        f"H-V1a run: {results['run_status'].upper()} "
        f"({len(records)}/{results['expected_record_count']} records, support={results['support_status']})"
    )
    return 0 if results["run_status"] == "complete" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DefinitionError, OSError, RuntimeError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"H-V1a run: FAIL ({exc})", file=sys.stderr)
        raise SystemExit(1)

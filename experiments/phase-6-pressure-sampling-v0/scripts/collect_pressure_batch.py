#!/usr/bin/env python3
"""TURN B only: validate and copy Batch 3 staging into immutable run paths."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pressure_tasks as tasks  # noqa: E402


EXPECTED_BATCH_ID = "phase-6-batch-3-sampling-path-requalification-v0"
CORE_TASK_ARTIFACTS = {
    "attempt-start.json",
    "provider-events.jsonl",
    "provider-stderr.txt",
    "resource-record.json",
    "verification-record.json",
    "terminal-record.json",
    "predicate-source-map.json",
    "run-manifest.json",
}


class CollectionError(ValueError):
    """Staging evidence is incomplete, contradictory, or identity-invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CollectionError(message)


def _artifact_records(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = manifest.get("artifacts")
    _require(isinstance(records, list), "run manifest artifact inventory is absent")
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        _require(isinstance(record, Mapping), "run manifest artifact record is invalid")
        name = record.get("path")
        _require(isinstance(name, str) and Path(name).name == name, "unsafe artifact path in run manifest")
        _require(name not in indexed, f"duplicate artifact record: {name}")
        indexed[name] = record
    return indexed


def validate_task_artifacts(
    task_key: str,
    task_dir: Path,
    *,
    expected_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    names = {path.name for path in task_dir.iterdir() if path.is_file()}
    missing = CORE_TASK_ARTIFACTS - names
    _require(not missing, f"staging task artifacts missing for {task_key}: {sorted(missing)}")

    terminal = tasks.load_object(task_dir / "terminal-record.json")
    task = tasks.load_task(task_key)
    _require(terminal.get("task_key") == task_key, f"terminal task key mismatch: {task_key}")
    _require(
        terminal.get("task_id") == task.contract["task_id"],
        f"terminal task identity mismatch: {task_key}",
    )
    terminal_status = terminal.get("terminal_status")
    systemic = terminal_status == "systemic_failure"
    reasons = terminal.get("systemic_failure_reasons")
    _require(isinstance(reasons, list), f"systemic reason list missing: {task_key}")
    output_declared_missing = "provider_output_missing" in reasons
    raw_path = task_dir / "raw-output.txt"
    raw_exists = raw_path.is_file()
    usable = terminal.get("usable_result_observed", terminal.get("usable_model_result"))
    _require(isinstance(usable, bool), f"usable-result observation invalid: {task_key}")

    if systemic:
        _require(not usable, f"systemic terminal declares a usable result: {task_key}")
        if output_declared_missing:
            _require(
                not raw_exists,
                f"contradictory evidence: raw output exists but is declared missing: {task_key}",
            )
        else:
            _require(
                raw_exists,
                f"contradictory evidence: raw output absent without missing-output reason: {task_key}",
            )
    else:
        _require(not output_declared_missing, f"non-systemic terminal declares missing output: {task_key}")
        _require(raw_exists, f"non-systemic task raw output missing: {task_key}")
        _require(usable, f"non-systemic terminal lacks usable result: {task_key}")

    run_manifest = tasks.load_object(task_dir / "run-manifest.json")
    _require(
        run_manifest.get("task_id") == task.contract["task_id"],
        f"run manifest task identity mismatch: {task_key}",
    )
    if expected_identity is not None:
        for field in (
            "definition_code_freeze_sha",
            "launch_ready_sha",
            "admission_record_sha256",
        ):
            _require(
                run_manifest.get(field) == expected_identity.get(field),
                f"run manifest {field} mismatch: {task_key}",
            )
    indexed = _artifact_records(run_manifest)
    observed_artifacts = names - {"run-manifest.json"}
    _require(set(indexed) == observed_artifacts, f"run manifest artifact inventory mismatch: {task_key}")
    for name, record in indexed.items():
        content = (task_dir / name).read_bytes()
        _require(record.get("bytes") == len(content), f"artifact byte count mismatch: {task_key}/{name}")
        _require(
            record.get("sha256") == tasks.sha256_bytes(content),
            f"artifact hash mismatch: {task_key}/{name}",
        )
    return {
        "task_key": task_key,
        "terminal_status": terminal_status,
        "raw_output_presence": raw_exists,
        "systemic_output_absence_valid": systemic and output_declared_missing and not raw_exists,
    }


def _validate_completion(
    manifest: Mapping[str, Any], staging: Path
) -> tuple[Path, list[str], dict[str, Any]]:
    _require(manifest.get("batch_id") == EXPECTED_BATCH_ID, "Batch 3 launch identity mismatch")
    completion_path = staging / "batch-completion.json"
    _require(completion_path.is_file(), "batch completion artifact is absent")
    completion = tasks.load_object(completion_path)
    _require(completion.get("batch_id") == EXPECTED_BATCH_ID, "batch completion identity mismatch")
    _require(
        completion.get("definition_code_freeze_sha") == manifest.get("definition_code_freeze_sha"),
        "batch completion freeze identity mismatch",
    )
    launch_ready_sha = completion.get("launch_ready_sha")
    _require(
        isinstance(launch_ready_sha, str)
        and len(launch_ready_sha) == 40
        and all(character in "0123456789abcdef" for character in launch_ready_sha),
        "batch completion launch identity invalid",
    )
    attempted = completion.get("attempted")
    _require(isinstance(attempted, list), "batch completion attempted inventory missing")
    attempted_keys = [row.get("task_key") for row in attempted if isinstance(row, Mapping)]
    _require(len(attempted_keys) == len(attempted), "batch completion attempted record invalid")
    _require(
        attempted_keys == list(tasks.TASK_KEYS[: len(attempted_keys)]),
        "attempted task order is not the frozen prefix",
    )
    present_keys = [key for key in tasks.TASK_KEYS if (staging / key).is_dir()]
    _require(present_keys == attempted_keys, "staging task directories contradict attempted inventory")
    stopped = completion.get("stopped_on_systemic_or_safety_failure")
    _require(isinstance(stopped, bool), "batch completion stop state missing")
    if stopped:
        _require(bool(attempted_keys), "systemic stop without an attempted task")
    else:
        _require(attempted_keys == list(tasks.TASK_KEYS), "non-stopped batch is incomplete")
    return completion_path, attempted_keys, completion


def _destination_from_manifest(manifest: Mapping[str, Any]) -> Path:
    relative = manifest.get("repository_run_path")
    _require(
        relative == "experiments/phase-6-pressure-sampling-v0/runs/batch-3",
        "repository run destination identity mismatch",
    )
    return REPOSITORY_ROOT / relative


def collect(manifest_path: Path, *, destination: Path | None = None) -> dict[str, Any]:
    manifest = tasks.load_object(manifest_path)
    staging = Path(manifest["external_staging"]["staging_root"])
    _require(staging.is_dir(), "external staging root is absent")
    completion_path, attempted_keys, completion = _validate_completion(manifest, staging)
    expected_identity = {
        "definition_code_freeze_sha": manifest["definition_code_freeze_sha"],
        "launch_ready_sha": completion["launch_ready_sha"],
        "admission_record_sha256": manifest["admission"]["record_sha256"],
    }
    task_validation = [
        validate_task_artifacts(
            task_key,
            staging / task_key,
            expected_identity=expected_identity,
        )
        for task_key in attempted_keys
    ]

    target = destination if destination is not None else _destination_from_manifest(manifest)
    target.mkdir(parents=True, exist_ok=True)
    target_completion = target / completion_path.name
    _require(not target_completion.exists(), "immutable collected completion record already exists")
    for task_key in attempted_keys:
        _require(
            not (target / task_key).exists(),
            f"immutable collected task path already exists: {task_key}",
        )

    shutil.copy2(completion_path, target_completion)
    _require(
        target_completion.read_bytes() == completion_path.read_bytes(),
        "completion artifact changed during collection",
    )
    for task_key in attempted_keys:
        source = staging / task_key
        copied = target / task_key
        shutil.copytree(source, copied)
        for source_file in source.iterdir():
            if source_file.is_file():
                _require(
                    (copied / source_file.name).read_bytes() == source_file.read_bytes(),
                    f"artifact changed during collection: {task_key}/{source_file.name}",
                )
    return {
        "destination": str(target),
        "attempted_task_keys": attempted_keys,
        "task_validation": task_validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch-manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = collect(args.launch_manifest)
        print(result["destination"])
        return 0
    except (OSError, KeyError, CollectionError, tasks.PressureTaskError) as exc:
        print(f"Phase 6 Batch 3 collection: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

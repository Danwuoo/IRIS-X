#!/usr/bin/env python3
"""Create the zero-call admission snapshot and launch-ready metadata."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODEL_SCRIPTS = REPOSITORY_ROOT / "experiments/substrates/model-execution-qualification-v0/scripts"
for candidate in (MODEL_SCRIPTS, Path(__file__).resolve().parent):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import check_admission  # noqa: E402
import pressure_tasks as tasks  # noqa: E402
import validate_definitions  # noqa: E402


RUN_META = EXPERIMENT_ROOT / "runs/batch-3"
ADMISSION_PATH = RUN_META / "admission-record.json"
LAUNCH_MANIFEST_PATH = RUN_META / "launch-manifest.json"


class LaunchPreparationError(ValueError):
    """Launch readiness could not be established without a model call."""


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPOSITORY_ROOT, check=True, text=True,
        encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def write_new(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(tasks.pretty_json_bytes(payload))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-sha", required=True)
    parser.add_argument("--staging-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        validate_definitions.validate()
        if git("status", "--porcelain"):
            raise LaunchPreparationError("definition freeze must be a clean tree")
        if git("rev-parse", "HEAD") != args.freeze_sha:
            raise LaunchPreparationError("freeze SHA must equal current clean HEAD")
        if args.staging_root.resolve().is_relative_to(REPOSITORY_ROOT.resolve()):
            raise LaunchPreparationError("staging root must be outside the repository")
        if ADMISSION_PATH.exists() or LAUNCH_MANIFEST_PATH.exists():
            raise LaunchPreparationError("launch-ready metadata already exists")
        admission = check_admission.current_environment()
        if admission.get("status") != "admitted":
            raise LaunchPreparationError(
                "admission did not return admitted: " + ",".join(admission.get("reasons", []))
            )
        if admission.get("live_model_calls") != 0 or admission.get("provider_attempts") != 0:
            raise LaunchPreparationError("admission checker crossed the model boundary")
        write_new(ADMISSION_PATH, admission)
        admission_sha = tasks.sha256_bytes(ADMISSION_PATH.read_bytes())
        sample_manifest_path = EXPERIMENT_ROOT / "definition/sample-manifest.json"
        policy_path = EXPERIMENT_ROOT / "definition/launch-policy.json"
        staging = args.staging_root.resolve()
        manifest = {
            "schema_version": 1,
            "batch_id": "phase-6-batch-3-sampling-path-requalification-v0",
            "required_baseline_sha": "07a71392a59f78e41ca32f1c9c377e2a43be41e6",
            "definition_code_freeze_sha": args.freeze_sha,
            "launch_ready_commit_resolution": "git_head_at_runner_start",
            "task_order": list(tasks.TASK_KEYS),
            "admission": {
                "status": "admitted",
                "record_path": ADMISSION_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "record_sha256": admission_sha,
                "profile_id": admission["compatibility_profile_id"],
                "profile_sha256": admission["compatibility_profile_sha256"],
                "configuration_id": admission["configuration_identity"],
                "cli_path": admission["observed_cli_path"],
                "cli_version": admission["observed_cli_version"],
                "provider_slot": admission["provider_slot"],
                "model": admission["model_id"],
                "reasoning_effort": admission["reasoning_effort"],
            },
            "definition_bindings": {
                "sample_manifest_path": sample_manifest_path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sample_manifest_sha256": tasks.sha256_bytes(sample_manifest_path.read_bytes()),
                "launch_policy_path": policy_path.relative_to(REPOSITORY_ROOT).as_posix(),
                "launch_policy_sha256": tasks.sha256_bytes(policy_path.read_bytes()),
                "provider_schema_policy_path": "experiments/phase-6-pressure-sampling-v0/definition/provider-response-schema-policy.json",
                "provider_schema_policy_sha256": tasks.sha256_bytes(
                    (EXPERIMENT_ROOT / "definition/provider-response-schema-policy.json").read_bytes()
                ),
            },
            "external_staging": {
                "staging_root": str(staging),
                "runner_stdout_path": str(staging / "runner-stdout.txt"),
                "runner_stderr_path": str(staging / "runner-stderr.txt"),
                "batch_completion_path": str(staging / "batch-completion.json"),
                "per_task_raw_output_path": str(staging / "{task_key}" / "raw-output.txt"),
                "per_task_provider_events_path": str(staging / "{task_key}" / "provider-events.jsonl"),
                "per_task_provider_stderr_path": str(staging / "{task_key}" / "provider-stderr.txt"),
            },
            "resource_ceiling": {
                "model_calls": 6,
                "per_task_model_calls": 1,
                "retries": 0,
                "routes": 0,
                "fallbacks": 0,
                "escalations": 0,
                "recovery_actions": 0,
                "model_tools": 0,
            },
            "collection_status": "not_performed",
            "repository_run_path": "experiments/phase-6-pressure-sampling-v0/runs/batch-3",
        }
        write_new(LAUNCH_MANIFEST_PATH, manifest)
        print(json.dumps({
            "status": "launch_ready_metadata_prepared",
            "admission": "admitted",
            "admission_record_sha256": admission_sha,
            "staging_root": str(staging),
        }, indent=2, sort_keys=True))
        return 0
    except (LaunchPreparationError, OSError, KeyError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"Phase 6 Batch 3 launch preparation: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

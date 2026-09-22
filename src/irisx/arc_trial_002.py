"""ARC-AGI-2 Trial 002 preparation, transport, quarantine, and scoring.

This module is deliberately independent from the frozen Trial 001 profiles.
It contains no model imports and performs no network or GPU work at import time.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Iterable, Mapping
import zipfile

from .arc_agi2 import ARC_COMMIT, validate_grid, validate_source, validate_task
from .artifacts import load_artifact
from .canonical import canonical_bytes, digest_bytes, digest_value, read_json, write_json
from .errors import ValidationError
from .transport import (
    ArchiveLimits,
    RESULT_LIMITS,
    TRIAL_LIMITS,
    digest_path,
    extract_verified_zip,
    verify_zip,
    write_zip,
)


TRIAL_ID = "arc-agi-2-trial-002"
RUN_ID = "trial-002-smoke-002"
SOURCE_SPLIT = "training"
SELECTION_SEED = "arc-agi-2-trial-002-smoke-v1"
SMOKE_TASK_COUNT = 4
WORKER_COUNT = 4
PREDICTIONS_PER_TEST = 2
GENERATION_INVOCATION_QUOTA = 4
TASK_DEADLINE_SECONDS = 300
SESSION_BUDGET_SECONDS = 3600
FINALIZATION_RESERVE_SECONDS = 180

COMPETITION_SLUG = "arc-prize-2026-arc-agi-2"
COMPETITION_CHALLENGE_FILENAME = "arc-agi_training_challenges.json"
KAGGLE_MACHINE_SHAPE = "NvidiaL4"
KAGGLE_KERNEL_REF = "danielwuu/iris-x-arc-agi-2-trial-002-smoke-002"

MODEL_REPOSITORY = "Qwen/Qwen3.5-4B"
MODEL_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
MODEL_LICENSE = "Apache-2.0"
MODEL_FILES = {
    ".gitattributes",
    "LICENSE",
    "README.md",
    "chat_template.jinja",
    "config.json",
    "merges.txt",
    "model.safetensors-00001-of-00002.safetensors",
    "model.safetensors-00002-of-00002.safetensors",
    "model.safetensors.index.json",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "video_preprocessor_config.json",
    "vocab.json",
}

NVARC_REPOSITORY = "https://github.com/1ytic/NVARC.git"
NVARC_REVISION = "846d0198efa752534594e321fc3289fc0a06c657"
NVARC_LICENSE_STATE = "not-found-at-repository-root"

OUTBOUND_KIND = "irisx/arc-agi-2-trial-002-input"
RESULT_KIND = "irisx/arc-agi-2-trial-002-result"
OUTBOUND_PATHS = {
    "bindings/run.json",
    "cases/solver-cases.json",
    "runtime/dependencies.json",
    "runtime/runner.py",
    "runtime/core.py",
    "sources/nvarc-manifest.json",
    "sources/model-manifest.json",
    "sources/wheel-manifest.json",
}
RESULT_PATHS = {
    "bindings/run.json",
    "checkpoint/checkpoint.json",
    "predictions/predictions.json",
    "observations/execution.json",
    "logs/progress.jsonl",
}

TERMINAL_STATUSES = {
    "valid",
    "invalid",
    "timeout",
    "oom",
    "worker_crash",
    "not_executed",
}
FAILURE_STATUSES = TERMINAL_STATUSES - {"valid", "invalid"}


def _git(root: Path, *args: str) -> str:
    import subprocess

    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise ValidationError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _normalized_remote(value: str) -> str:
    return value.lower().removesuffix("/").removesuffix(".git").replace("git@github.com:", "https://github.com/")


def _ensure_empty(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValidationError(f"output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)


def _strict_json_bytes(value: Any) -> bytes:
    return canonical_bytes(value, newline=True)


def _load_canonical(path: Path) -> Any:
    value = read_json(path)
    if path.read_bytes() != canonical_bytes(value, newline=True):
        raise ValidationError(f"JSON is not canonical: {path}")
    return value


def grid_to_text(grid: list[list[int]]) -> str:
    validate_grid(grid, "grid")
    return "\n".join("".join(str(cell) for cell in row) for row in grid)


def parse_grid_text(value: str) -> list[list[int]] | None:
    """Extract the first rectangular digit-row block from a model response."""

    if not isinstance(value, str):
        return None
    blocks: list[list[list[int]]] = []
    current: list[list[int]] = []
    for raw in value.replace("```", "\n").splitlines():
        compact = "".join(character for character in raw if character.isdigit())
        if compact and all(character in "0123456789" for character in compact):
            row = [int(character) for character in compact]
            if len(row) <= 30 and (not current or len(row) == len(current[0])):
                current.append(row)
                continue
        if current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    for block in blocks:
        try:
            return validate_grid(block, "model_output")
        except ValidationError:
            continue
    return None


def _input_shape_signature(task: Mapping[str, Any]) -> dict[str, Any]:
    """Return the only task projection used by smoke selection.

    Outputs are intentionally never accessed, so changing truth cannot affect the
    selected task identities.
    """

    def shape(grid: Any) -> list[int]:
        if not isinstance(grid, list) or not grid or not isinstance(grid[0], list):
            raise ValidationError("task input grid is malformed")
        return [len(grid), len(grid[0])]

    return {
        "train_input_shapes": [shape(pair["input"]) for pair in task["train"]],
        "test_input_shapes": [shape(pair["input"]) for pair in task["test"]],
    }


def select_smoke_tasks(training_dir: Path, *, count: int = SMOKE_TASK_COUNT) -> list[str]:
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValidationError("smoke task count must be a positive integer")
    ranked: list[tuple[str, str]] = []
    for path in sorted(training_dir.glob("*.json")):
        task = read_json(path)
        signature = _input_shape_signature(task)
        total_input_cells = sum(height * width for height, width in signature["train_input_shapes"] + signature["test_input_shapes"])
        if total_input_cells > 4096:
            continue
        rank = hashlib.sha256(f"{SELECTION_SEED}:{path.stem}".encode("utf-8")).hexdigest()
        ranked.append((rank, path.stem))
    if len(ranked) < count:
        raise ValidationError("not enough input-shape-eligible training tasks for smoke selection")
    return [task_id for _, task_id in sorted(ranked)[:count]]


def expected_job_keys(solver_cases: Mapping[str, Any]) -> list[str]:
    jobs: list[str] = []
    for case in solver_cases.get("cases", []):
        task_id = case.get("task_id")
        tests = case.get("test")
        if not isinstance(task_id, str) or not isinstance(tests, list):
            raise ValidationError("solver case is malformed")
        jobs.extend(f"{task_id}:{index}" for index in range(len(tests)))
    if len(jobs) != len(set(jobs)) or not jobs:
        raise ValidationError("solver job keys are empty or duplicated")
    return jobs


def _run_configuration() -> dict[str, Any]:
    return {
        "worker_count": WORKER_COUNT,
        "jobs_per_gpu": 1,
        "accelerator_requirement": {"gpu_model_contains": "L4", "gpu_count": 4, "minimum_memory_mib_each": 22000},
        "session_budget_seconds": SESSION_BUDGET_SECONDS,
        "finalization_reserve_seconds": FINALIZATION_RESERVE_SECONDS,
        "task_deadline_seconds": TASK_DEADLINE_SECONDS,
        "predictions_per_test": PREDICTIONS_PER_TEST,
        "inference_only": True,
        "test_time_training": {"enabled": False},
        "generation": {
            "invocation_quota": GENERATION_INVOCATION_QUOTA,
            "num_return_sequences": 1,
            "num_beams": 1,
            "do_sample": False,
            "augmentation_views": ["identity"],
            "maximum_new_tokens": 512,
            "seed": 20260922,
            "selection": "one parseable grid from one deterministic completion",
        },
        "fallback_policy": "no fallback is accepted as a model prediction",
    }


def _load_competition_challenges(path: Path) -> dict[str, Any]:
    if path.name != COMPETITION_CHALLENGE_FILENAME or not path.is_file():
        raise ValidationError(f"expected Kaggle competition challenge file {COMPETITION_CHALLENGE_FILENAME}")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Kaggle competition challenge file is not valid JSON") from exc
    if not isinstance(value, dict) or not value:
        raise ValidationError("Kaggle competition challenge file must be a non-empty task map")
    return value


def _competition_solver_case(
    task_id: str,
    competition_task: Any,
    official_task: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(competition_task, dict) or set(competition_task) != {"train", "test"}:
        raise ValidationError(f"competition challenge task is missing or malformed: {task_id}")
    validated = validate_task(competition_task, f"competition/{task_id}", require_test_outputs=False)
    expected_projection = {
        "train": official_task["train"],
        "test": [{"input": pair["input"]} for pair in official_task["test"]],
    }
    if validated != expected_projection:
        raise ValidationError(f"competition challenge task differs from the pinned official source: {task_id}")
    if not validated["test"]:
        raise ValidationError(f"competition challenge task has no test input: {task_id}")
    return {
        "task_id": task_id,
        "train": validated["train"],
        "test": [{"input": validated["test"][0]["input"]}],
    }


def prepare_trial(source_root: Path, competition_challenges: Path, output: Path) -> dict[str, Any]:
    """Prepare four competition-mounted tasks with one inference each."""

    provenance = validate_source(source_root)
    upstream = source_root / "upstream"
    training_dir = upstream / "data" / SOURCE_SPLIT
    selected = select_smoke_tasks(training_dir)
    competition = _load_competition_challenges(competition_challenges)
    competition_digest = digest_path(competition_challenges)
    _ensure_empty(output)

    solver_cases: dict[str, Any] = {
        "format": "irisx/arc-agi-2-trial-002-solver-cases",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "split": SOURCE_SPLIT,
        "cases": [],
    }
    evaluator: dict[str, Any] = {
        "format": "irisx/arc-agi-2-trial-002-evaluator-truth",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "split": SOURCE_SPLIT,
        "cases": [],
    }
    workload_cases: list[dict[str, Any]] = []
    for task_id in selected:
        source_path = training_dir / f"{task_id}.json"
        task = validate_task(read_json(source_path), f"training/{task_id}.json", require_test_outputs=True)
        signature = _input_shape_signature(task)
        solver_case = _competition_solver_case(task_id, competition.get(task_id), task)
        solver_cases["cases"].append(solver_case)
        evaluator["cases"].append(
            {"task_id": task_id, "test": [{"output": task["test"][0]["output"]}]}
        )
        workload_cases.append(
            {
                "task_id": task_id,
                "source_path": f"data/training/{task_id}.json",
                "test_count": 1,
                "competition_test_count": len(task["test"]),
                "selected_test_index": 0,
                "train_input_shapes": signature["train_input_shapes"],
                "test_input_shapes": [signature["test_input_shapes"][0]],
            }
        )

    workload = {
        "format": "irisx/arc-agi-2-trial-002-workload",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "selection": {
            "split": SOURCE_SPLIT,
            "seed": SELECTION_SEED,
            "rank": "sha256(seed + ':' + task_id), ascending",
            "eligibility": "sum of training and test input cells <= 4096",
            "answer_blind": True,
            "task_count": SMOKE_TASK_COUNT,
        },
        "cases": workload_cases,
    }
    configuration = _run_configuration()
    run = {
        "format": "irisx/arc-agi-2-trial-002-run-binding",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "source": {
            "repository": "https://github.com/arcprize/ARC-AGI-2.git",
            "commit": ARC_COMMIT,
            "split": SOURCE_SPLIT,
            "provenance_digest": provenance["content_digest"],
            "competition_slug": COMPETITION_SLUG,
            "competition_challenge_file": COMPETITION_CHALLENGE_FILENAME,
            "competition_challenge_digest": competition_digest,
            "competition_selected_test_index": 0,
        },
        "model": {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "checkpoint_exposure": "unknown-general-pretraining; clean-of-project-ARC-answer-adaptation",
        },
        "solver": {
            "family": "Qwen3.5 direct grid inference with NVARC-compatible formatting",
            "upstream_repository": NVARC_REPOSITORY,
            "upstream_revision": NVARC_REVISION,
            "large_scale_sft_reproduced": False,
            "native_tokenizer_retained": True,
            "old_qwen3_adapter_reused": False,
            "nvarc_adaptation_retained_for_later": True,
        },
        "workload_digest": digest_value(workload),
        "solver_cases_digest": digest_value(solver_cases),
        "configuration": configuration,
        "configuration_digest": digest_value(configuration),
    }
    run["run_identity_digest"] = digest_value(run)
    write_json(output / "workload.json", workload)
    write_json(output / "solver-cases.json", solver_cases)
    write_json(output / "evaluator-truth.json", evaluator)
    write_json(output / "run-binding.json", run)
    validate_trial(output)
    return run


def validate_trial(root: Path) -> dict[str, Any]:
    workload = _load_canonical(root / "workload.json")
    solver = _load_canonical(root / "solver-cases.json")
    truth = _load_canonical(root / "evaluator-truth.json")
    run = _load_canonical(root / "run-binding.json")
    if workload.get("format") != "irisx/arc-agi-2-trial-002-workload" or workload.get("trial_id") != TRIAL_ID:
        raise ValidationError("Trial 002 workload identity is invalid")
    if solver.get("format") != "irisx/arc-agi-2-trial-002-solver-cases" or solver.get("trial_id") != TRIAL_ID:
        raise ValidationError("Trial 002 solver cases identity is invalid")
    if truth.get("format") != "irisx/arc-agi-2-trial-002-evaluator-truth" or truth.get("trial_id") != TRIAL_ID:
        raise ValidationError("Trial 002 evaluator truth identity is invalid")
    if run.get("trial_id") != TRIAL_ID or run.get("run_id") != RUN_ID:
        raise ValidationError("Trial 002 run identity is invalid")
    identity = {key: value for key, value in run.items() if key != "run_identity_digest"}
    if run.get("run_identity_digest") != digest_value(identity):
        raise ValidationError("Trial 002 run identity digest is stale")
    if run.get("workload_digest") != digest_value(workload) or run.get("solver_cases_digest") != digest_value(solver):
        raise ValidationError("Trial 002 workload or solver binding is stale")
    if run.get("configuration") != _run_configuration() or run.get("configuration_digest") != digest_value(_run_configuration()):
        raise ValidationError("Trial 002 configuration is stale")
    source = run.get("source")
    if (
        not isinstance(source, dict)
        or source.get("competition_slug") != COMPETITION_SLUG
        or source.get("competition_challenge_file") != COMPETITION_CHALLENGE_FILENAME
        or source.get("competition_selected_test_index") != 0
        or not isinstance(source.get("competition_challenge_digest"), str)
        or not source["competition_challenge_digest"].startswith("sha256:")
    ):
        raise ValidationError("Trial 002 competition source binding is invalid")
    if [case.get("task_id") for case in workload.get("cases", [])] != [case.get("task_id") for case in solver.get("cases", [])]:
        raise ValidationError("Trial 002 workload and solver task order differ")
    truth_by_id = {case.get("task_id"): case for case in truth.get("cases", [])}
    if len(truth_by_id) != len(truth.get("cases", [])):
        raise ValidationError("Trial 002 evaluator truth contains duplicate task ids")
    for case in solver.get("cases", []):
        if not isinstance(case, dict) or set(case) != {"task_id", "train", "test"}:
            raise ValidationError("Trial 002 solver case fields are invalid")
        if any(set(pair) != {"input"} for pair in case["test"]):
            raise ValidationError("solver-facing Trial 002 test cases contain truth or extra fields")
        reconstructed = {"train": case["train"], "test": case["test"]}
        validate_task(reconstructed, f"solver/{case['task_id']}", require_test_outputs=False)
        if len(case["test"]) != 1:
            raise ValidationError("Trial 002 repair smoke requires exactly one test input per task")
        local_truth = truth_by_id.get(case["task_id"])
        if not isinstance(local_truth, dict) or len(local_truth.get("test", [])) != len(case["test"]):
            raise ValidationError("Trial 002 truth does not align with solver test inputs")
        for index, pair in enumerate(local_truth["test"]):
            if not isinstance(pair, dict) or set(pair) != {"output"}:
                raise ValidationError("Trial 002 truth pair is malformed")
            validate_grid(pair["output"], f"truth/{case['task_id']}/{index}")
    jobs = expected_job_keys(solver)
    if len(jobs) != GENERATION_INVOCATION_QUOTA or len(solver.get("cases", [])) != SMOKE_TASK_COUNT:
        raise ValidationError("Trial 002 repair smoke must contain four distinct one-inference tasks")
    return run


def validate_competition_mount(
    path: Path,
    run: Mapping[str, Any],
    solver_cases: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and project the real Kaggle-mounted challenge file without reading solutions."""

    source = run.get("source", {})
    expected_digest = source.get("competition_challenge_digest")
    actual_digest = digest_path(path)
    if path.name != COMPETITION_CHALLENGE_FILENAME or actual_digest != expected_digest:
        raise ValidationError("Kaggle competition challenge mount is missing, substituted, or stale")
    competition = _load_competition_challenges(path)
    selected: list[str] = []
    for case in solver_cases.get("cases", []):
        task_id = case.get("task_id")
        mounted = competition.get(task_id)
        if not isinstance(task_id, str) or not isinstance(mounted, dict):
            raise ValidationError("selected task is absent from the Kaggle competition challenge mount")
        projected = {
            "task_id": task_id,
            "train": mounted.get("train"),
            "test": mounted.get("test", [])[:1],
        }
        if projected != case:
            raise ValidationError(f"Kaggle competition challenge projection differs from the bound solver case: {task_id}")
        selected.append(task_id)
    if len(selected) != SMOKE_TASK_COUNT or len(set(selected)) != SMOKE_TASK_COUNT:
        raise ValidationError("Kaggle competition challenge projection does not contain four distinct tasks")
    return {
        "competition_slug": COMPETITION_SLUG,
        "challenge_file": path.name,
        "challenge_digest": actual_digest,
        "available_task_count": len(competition),
        "selected_task_ids": selected,
        "selected_test_index": 0,
        "solutions_opened": False,
    }


def _regular_file_manifest(root: Path, *, include: Iterable[Path] | None = None) -> list[dict[str, Any]]:
    if include is None:
        paths = sorted((path for path in root.rglob("*") if path.is_file()), key=lambda path: path.relative_to(root).as_posix())
    else:
        paths = sorted(include, key=lambda path: path.relative_to(root).as_posix())
    entries: list[dict[str, Any]] = []
    for path in paths:
        if path.is_symlink():
            raise ValidationError(f"manifest source must not be a symlink: {path}")
        logical = path.relative_to(root).as_posix()
        if ".git" in Path(logical).parts or ".cache" in Path(logical).parts:
            continue
        entries.append({"path": logical, "byte_size": path.stat().st_size, "content_digest": digest_path(path)})
    if not entries:
        raise ValidationError(f"file manifest is empty: {root}")
    return entries


def create_model_manifest(model_root: Path) -> dict[str, Any]:
    actual = {path.name for path in model_root.iterdir() if path.is_file()}
    if actual != MODEL_FILES:
        raise ValidationError(f"Qwen3.5 model file set mismatch; missing={sorted(MODEL_FILES-actual)}, unexpected={sorted(actual-MODEL_FILES)}")
    config = read_json(model_root / "config.json")
    text = config.get("text_config", {})
    if config.get("model_type") != "qwen3_5" or text.get("hidden_size") != 2560 or text.get("num_hidden_layers") != 32:
        raise ValidationError("Qwen3.5 model architecture does not match the selected 4B profile")
    entries = _regular_file_manifest(model_root, include=[model_root / name for name in MODEL_FILES])
    return {
        "format": "irisx/model-material-manifest",
        "format_version": "1.0",
        "repository": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "license": MODEL_LICENSE,
        "files": entries,
        "total_bytes": sum(entry["byte_size"] for entry in entries),
        "manifest_digest": digest_value(entries),
    }


def create_nvarc_manifest(source_root: Path) -> dict[str, Any]:
    if _normalized_remote(_git(source_root, "remote", "get-url", "origin")) != _normalized_remote(NVARC_REPOSITORY):
        raise ValidationError("NVARC source remote is not the selected upstream")
    if _git(source_root, "rev-parse", "HEAD") != NVARC_REVISION:
        raise ValidationError("NVARC source revision is not pinned")
    if _git(source_root, "status", "--porcelain", "--untracked-files=no"):
        raise ValidationError("NVARC source contains modified tracked files")
    files = _regular_file_manifest(source_root)
    return {
        "format": "irisx/source-material-manifest",
        "format_version": "1.0",
        "repository": NVARC_REPOSITORY,
        "revision": NVARC_REVISION,
        "license_state": NVARC_LICENSE_STATE,
        "files": files,
        "manifest_digest": digest_value(files),
    }


def create_wheel_manifest(wheel_root: Path) -> dict[str, Any]:
    wheels = sorted(wheel_root.glob("*.whl"), key=lambda path: path.name.lower())
    entries = _regular_file_manifest(wheel_root, include=wheels)
    names = {entry["path"].lower() for entry in entries}
    for required in ("transformers-5.8.1", "peft-0.21.0", "accelerate-", "jinja2-3.1.6", "irisx-0.2.0"):
        if not any(name.startswith(required) for name in names):
            raise ValidationError(f"offline wheelhouse is missing {required}")
    return {
        "format": "irisx/offline-wheel-manifest",
        "format_version": "1.0",
        "python": "3.12",
        "files": entries,
        "manifest_digest": digest_value(entries),
    }


def validate_runtime_wheel_sources(
    wheel_root: Path,
    *,
    runner: bytes,
    core: bytes,
) -> None:
    wheels = list(wheel_root.glob("irisx-0.2.0-*.whl"))
    if len(wheels) != 1:
        raise ValidationError("offline wheelhouse must contain exactly one IRIS-X 0.2.0 wheel")
    try:
        with zipfile.ZipFile(wheels[0], "r") as archive:
            installed_runner = archive.read("irisx/kaggle_runner_trial002.py")
            installed_core = archive.read("irisx/arc_trial_002.py")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValidationError("offline IRIS-X wheel does not contain the Trial 002 runtime") from exc
    if installed_runner != runner or installed_core != core:
        raise ValidationError("offline IRIS-X wheel and bound Trial 002 runtime source differ")


def validate_material_manifest(root: Path, manifest: Mapping[str, Any]) -> None:
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("material manifest files are missing")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "byte_size", "content_digest"}:
            raise ValidationError("material manifest file entry is malformed")
        logical = entry["path"]
        if not isinstance(logical, str) or logical in seen or ".." in logical.split("/") or logical.startswith("/") or "\\" in logical:
            raise ValidationError("material manifest contains an unsafe or duplicate path")
        seen.add(logical)
        path = root.joinpath(*logical.split("/"))
        if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["byte_size"] or digest_path(path) != entry["content_digest"]:
            raise ValidationError(f"material manifest binding failed: {logical}")


def validate_kernel_staging(root: Path, *, expected_dataset_ref: str) -> dict[str, Any]:
    metadata_path = root / "kernel-metadata.json"
    try:
        metadata = json.loads(metadata_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Kaggle kernel metadata is missing or invalid") from exc
    required = {
        "id",
        "title",
        "code_file",
        "language",
        "kernel_type",
        "is_private",
        "enable_gpu",
        "enable_tpu",
        "enable_internet",
        "machine_shape",
        "dataset_sources",
        "competition_sources",
        "kernel_sources",
        "model_sources",
    }
    if set(metadata) != required:
        raise ValidationError("Kaggle kernel metadata contains missing or ignored fields")
    expected = {
        "id": KAGGLE_KERNEL_REF,
        "title": "IRIS-X ARC-AGI-2 Trial 002 Repair Smoke 002",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": False,
        "machine_shape": KAGGLE_MACHINE_SHAPE,
        "dataset_sources": [expected_dataset_ref],
        "competition_sources": [COMPETITION_SLUG],
        "kernel_sources": [],
        "model_sources": [],
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValidationError(f"Kaggle kernel metadata field was omitted or changed: {key}")
    code_file = metadata.get("code_file")
    if not isinstance(code_file, str) or Path(code_file).name != code_file:
        raise ValidationError("Kaggle kernel code_file is unsafe")
    notebook_path = root / code_file
    try:
        notebook = json.loads(notebook_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Kaggle notebook is missing or invalid") from exc
    source = "\n".join(
        "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        for cell in notebook.get("cells", [])
        if isinstance(cell, dict)
    )
    required_fragments = (
        RUN_ID,
        COMPETITION_CHALLENGE_FILENAME,
        "--competition-challenges",
        "EXPECTED_OUTBOUND_SHA256 =",
        "torch.cuda.device_count",
    )
    if any(fragment not in source for fragment in required_fragments) or "__IRISX_" in source:
        raise ValidationError("Kaggle notebook staging is stale or contains unresolved bindings")
    return metadata


def stage_kaggle_kernel(
    template_root: Path,
    output: Path,
    *,
    expected_dataset_ref: str,
    outbound_digest: str,
) -> dict[str, Any]:
    normalized_digest = outbound_digest.removeprefix("sha256:")
    if len(normalized_digest) != 64 or any(character not in "0123456789abcdef" for character in normalized_digest):
        raise ValidationError("Kaggle notebook outbound digest binding is invalid")
    _ensure_empty(output)
    template_metadata = read_json(template_root / "kernel-metadata.json")
    code_file = template_metadata.get("code_file")
    if not isinstance(code_file, str):
        raise ValidationError("Kaggle kernel template code_file is missing")
    notebook = json.loads((template_root / code_file).read_bytes())
    marker = "__IRISX_OUTBOUND_SHA256__"
    replacement = normalized_digest
    replacements = 0
    for cell in notebook.get("cells", []):
        source = cell.get("source") if isinstance(cell, dict) else None
        if isinstance(source, list):
            updated = []
            for line in source:
                replacements += line.count(marker)
                updated.append(line.replace(marker, replacement))
            cell["source"] = updated
        elif isinstance(source, str):
            replacements += source.count(marker)
            cell["source"] = source.replace(marker, replacement)
    if replacements != 1:
        raise ValidationError("Kaggle notebook template must contain one outbound digest marker")
    metadata = dict(template_metadata)
    metadata["dataset_sources"] = [expected_dataset_ref]
    (output / code_file).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (output / "kernel-metadata.json").write_bytes(_strict_json_bytes(metadata))
    return validate_kernel_staging(output, expected_dataset_ref=expected_dataset_ref)


def validate_dataset_staging(
    root: Path,
    outbound: Path,
    outbound_contents: Mapping[str, bytes],
    *,
    expected_dataset_ref: str,
) -> dict[str, Any]:
    metadata = read_json(root / "dataset-metadata.json")
    if metadata.get("id") != expected_dataset_ref:
        raise ValidationError("Kaggle Dataset staging id differs from the bound kernel source")
    model_manifest = json.loads(outbound_contents["sources/model-manifest.json"])
    wheel_manifest = json.loads(outbound_contents["sources/wheel-manifest.json"])
    validate_material_manifest(root, model_manifest)
    validate_material_manifest(root, wheel_manifest)
    staged_outbound = root / f"{RUN_ID}.zip"
    if not staged_outbound.is_file() or digest_path(staged_outbound) != digest_path(outbound):
        raise ValidationError("Kaggle Dataset staging contains a stale Trial 002 outbound")
    forbidden_names = {"evaluator-truth.json", "arc-agi_training_solutions.json", "arc-agi_evaluation_solutions.json"}
    if any(path.name in forbidden_names for path in root.rglob("*") if path.is_file()):
        raise ValidationError("Kaggle Dataset staging contains evaluator truth or competition solutions")
    return {
        "dataset_ref": expected_dataset_ref,
        "outbound_digest": digest_path(staged_outbound),
        "model_manifest_digest": model_manifest["manifest_digest"],
        "wheel_manifest_digest": wheel_manifest["manifest_digest"],
        "truth_free": True,
    }


def build_outbound_package(
    trial_root: Path,
    model_root: Path,
    nvarc_root: Path,
    wheel_root: Path,
    output: Path,
    *,
    repository_root: Path,
) -> str:
    run = validate_trial(trial_root)
    model_manifest = create_model_manifest(model_root)
    nvarc_manifest = create_nvarc_manifest(nvarc_root)
    wheel_manifest = create_wheel_manifest(wheel_root)
    runner = (repository_root / "src/irisx/kaggle_runner_trial002.py").read_bytes()
    core = (repository_root / "src/irisx/arc_trial_002.py").read_bytes()
    validate_runtime_wheel_sources(wheel_root, runner=runner, core=core)
    solver = (trial_root / "solver-cases.json").read_bytes()
    run_bytes = (trial_root / "run-binding.json").read_bytes()
    dependencies = {
        "format": "irisx/arc-agi-2-trial-002-dependencies",
        "format_version": "1.0",
        "python": "3.12",
        "torch": "kaggle-image-preinstalled",
        "transformers": "5.8.1",
        "peft": "0.21.0",
        "jinja2": "3.1.6",
        "network_install": False,
        "model_manifest_digest": model_manifest["manifest_digest"],
        "nvarc_manifest_digest": nvarc_manifest["manifest_digest"],
        "wheel_manifest_digest": wheel_manifest["manifest_digest"],
    }
    files = {
        "bindings/run.json": run_bytes,
        "cases/solver-cases.json": solver,
        "runtime/dependencies.json": _strict_json_bytes(dependencies),
        "runtime/runner.py": runner,
        "runtime/core.py": core,
        "sources/nvarc-manifest.json": _strict_json_bytes(nvarc_manifest),
        "sources/model-manifest.json": _strict_json_bytes(model_manifest),
        "sources/wheel-manifest.json": _strict_json_bytes(wheel_manifest),
    }
    metadata = {
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "run_identity_digest": run["run_identity_digest"],
        "solver_cases_digest": run["solver_cases_digest"],
        "configuration_digest": run["configuration_digest"],
        "model_manifest_digest": model_manifest["manifest_digest"],
        "nvarc_manifest_digest": nvarc_manifest["manifest_digest"],
        "wheel_manifest_digest": wheel_manifest["manifest_digest"],
        "runner_digest": digest_bytes(runner),
        "core_digest": digest_bytes(core),
        "truth_free": True,
    }
    return write_zip(output, OUTBOUND_KIND, RUN_ID, files, metadata, limits=TRIAL_LIMITS)


def verify_outbound_package(path: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    manifest, contents, archive_digest = verify_zip(path, limits=TRIAL_LIMITS, package_kind=OUTBOUND_KIND)
    if set(contents) != OUTBOUND_PATHS:
        raise ValidationError("Trial 002 outbound package membership is not the closed-world profile")
    run = json.loads(contents["bindings/run.json"].decode("utf-8"))
    solver = json.loads(contents["cases/solver-cases.json"].decode("utf-8"))
    json_values = {
        "bindings/run.json": run,
        "cases/solver-cases.json": solver,
        "runtime/dependencies.json": json.loads(contents["runtime/dependencies.json"]),
        "sources/nvarc-manifest.json": json.loads(contents["sources/nvarc-manifest.json"]),
        "sources/model-manifest.json": json.loads(contents["sources/model-manifest.json"]),
        "sources/wheel-manifest.json": json.loads(contents["sources/wheel-manifest.json"]),
    }
    for logical, value in json_values.items():
        if contents[logical] != canonical_bytes(value, newline=True):
            raise ValidationError(f"Trial 002 outbound JSON is not canonical: {logical}")
    if run.get("trial_id") != TRIAL_ID or run.get("run_id") != RUN_ID or manifest["package_id"] != RUN_ID:
        raise ValidationError("Trial 002 outbound run identity is invalid")
    if run.get("solver_cases_digest") != digest_value(solver):
        raise ValidationError("Trial 002 outbound solver binding is stale")
    identity = {key: value for key, value in run.items() if key != "run_identity_digest"}
    if run.get("run_identity_digest") != digest_value(identity):
        raise ValidationError("Trial 002 outbound run identity digest is stale")
    if run.get("configuration") != _run_configuration() or run.get("configuration_digest") != digest_value(_run_configuration()):
        raise ValidationError("Trial 002 outbound configuration is stale")
    for case in solver.get("cases", []):
        if any(set(pair) != {"input"} for pair in case.get("test", [])):
            raise ValidationError("Trial 002 outbound contains evaluator truth or derived test metadata")
    metadata = manifest["metadata"]
    expected = {
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "run_identity_digest": run["run_identity_digest"],
        "solver_cases_digest": run["solver_cases_digest"],
        "configuration_digest": run["configuration_digest"],
        "model_manifest_digest": json.loads(contents["sources/model-manifest.json"])["manifest_digest"],
        "nvarc_manifest_digest": json.loads(contents["sources/nvarc-manifest.json"])["manifest_digest"],
        "wheel_manifest_digest": json.loads(contents["sources/wheel-manifest.json"])["manifest_digest"],
        "runner_digest": digest_bytes(contents["runtime/runner.py"]),
        "core_digest": digest_bytes(contents["runtime/core.py"]),
        "truth_free": True,
    }
    if metadata != expected:
        raise ValidationError("Trial 002 outbound metadata bindings are stale")
    forbidden = (b"evaluator-truth", b'"output_digest"', b'"score"', b'"feedback"')
    structured_paths = set(contents) - {"runtime/runner.py", "runtime/core.py"}
    if any(marker in contents[logical] for marker in forbidden for logical in structured_paths):
        raise ValidationError("Trial 002 outbound contains prohibited truth, score, or feedback material")
    expected_job_keys(solver)
    return manifest, contents, archive_digest


def technical_preflight(
    trial_root: Path,
    outbound: Path,
    model_root: Path,
    nvarc_root: Path,
    wheel_root: Path,
    competition_challenges: Path,
    dataset_root: Path,
    kernel_root: Path,
    expected_dataset_ref: str,
) -> dict[str, Any]:
    run = validate_trial(trial_root)
    manifest, contents, outbound_digest = verify_outbound_package(outbound)
    model_manifest = json.loads(contents["sources/model-manifest.json"])
    nvarc_manifest = json.loads(contents["sources/nvarc-manifest.json"])
    wheel_manifest = json.loads(contents["sources/wheel-manifest.json"])
    validate_material_manifest(model_root, model_manifest)
    validate_material_manifest(nvarc_root, nvarc_manifest)
    validate_material_manifest(wheel_root, wheel_manifest)
    validate_runtime_wheel_sources(
        wheel_root,
        runner=contents["runtime/runner.py"],
        core=contents["runtime/core.py"],
    )
    if json.loads(contents["bindings/run.json"]) != run:
        raise ValidationError("Trial 002 local trial and outbound run bindings differ")
    competition_evidence = validate_competition_mount(
        competition_challenges,
        run,
        json.loads(contents["cases/solver-cases.json"]),
    )
    dataset_evidence = validate_dataset_staging(
        dataset_root,
        outbound,
        contents,
        expected_dataset_ref=expected_dataset_ref,
    )
    kernel_metadata = validate_kernel_staging(kernel_root, expected_dataset_ref=expected_dataset_ref)
    checks = {
        "trial_valid": True,
        "outbound_valid": True,
        "model_bytes_bound": True,
        "nvarc_source_bound": True,
        "offline_wheels_bound": True,
        "truth_absent_from_outbound": True,
        "competition_challenge_bound": True,
        "competition_source_staged": True,
        "dataset_staging_bound": True,
        "kernel_staging_bound": True,
        "exactly_four_generate_invocations_configured": True,
        "runtime_gpu_check_required": True,
        "runtime_internet_check_required": True,
    }
    return {
        "format": "irisx/arc-agi-2-trial-002-preflight",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "run_identity_digest": run["run_identity_digest"],
        "outbound_digest": outbound_digest,
        "outbound_manifest_digest": digest_value(manifest),
        "checks": checks,
        "competition": competition_evidence,
        "dataset": dataset_evidence,
        "kernel": {
            "id": kernel_metadata["id"],
            "machine_shape": kernel_metadata["machine_shape"],
            "competition_sources": kernel_metadata["competition_sources"],
            "dataset_sources": kernel_metadata["dataset_sources"],
        },
        "technical_ready": all(checks.values()),
        "limitations": [
            "Static preflight does not claim a Kaggle L4 x4 runtime until the notebook verifies it.",
            "This repair smoke is inference-only; the NVARC adaptation path is retained but not executed.",
            "Smoke training-split accuracy is execution evidence, not public-evaluation generalization evidence.",
        ],
    }


def new_checkpoint(run: Mapping[str, Any], solver_cases: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "format": "irisx/arc-agi-2-trial-002-checkpoint",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "run_identity_digest": run["run_identity_digest"],
        "expected_jobs": expected_job_keys(solver_cases),
        "generation_invocation_quota": GENERATION_INVOCATION_QUOTA,
        "generation_invocations": {},
        "completed": {},
        "sessions": [],
        "cumulative_charged_seconds": 0.0,
        "complete": False,
    }


def validate_prediction_record(record: Any, expected_jobs: set[str]) -> dict[str, Any]:
    required = {
        "job_key",
        "task_id",
        "test_index",
        "status",
        "attempts",
        "valid_model_output",
        "generated_candidate_count",
        "failure",
        "timing",
        "tokens",
        "generation",
        "gpu_peak_memory_mib",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise ValidationError("Trial 002 prediction record fields are invalid")
    key = record["job_key"]
    if key not in expected_jobs or key != f"{record['task_id']}:{record['test_index']}":
        raise ValidationError("Trial 002 prediction job key is unknown or inconsistent")
    if record["status"] not in TERMINAL_STATUSES:
        raise ValidationError("Trial 002 prediction status is unsupported")
    attempts = record["attempts"]
    if not isinstance(attempts, list) or len(attempts) > PREDICTIONS_PER_TEST:
        raise ValidationError("Trial 002 prediction attempts exceed pass@2")
    for index, grid in enumerate(attempts):
        validate_grid(grid, f"prediction[{key}].attempts[{index}]")
    if not isinstance(record["valid_model_output"], bool):
        raise ValidationError("Trial 002 valid_model_output must be boolean")
    if record["valid_model_output"] != bool(attempts):
        raise ValidationError("Trial 002 valid_model_output does not match valid attempts")
    if record["status"] == "valid" and not attempts:
        raise ValidationError("valid Trial 002 prediction has no valid model grid")
    if record["status"] in FAILURE_STATUSES and attempts:
        raise ValidationError("failure Trial 002 prediction must not contain fallback attempts")
    if record["status"] == "invalid" and attempts:
        raise ValidationError("invalid Trial 002 prediction must not contain accepted attempts")
    generation = record["generation"]
    required_generation = {
        "invocation_ordinal",
        "raw_completion",
        "raw_completion_bytes",
        "raw_completion_truncated",
        "parse_state",
        "stop_reason",
    }
    if not isinstance(generation, dict) or set(generation) != required_generation:
        raise ValidationError("Trial 002 generation evidence fields are invalid")
    ordinal = generation["invocation_ordinal"]
    if ordinal is not None and (isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1 or ordinal > GENERATION_INVOCATION_QUOTA):
        raise ValidationError("Trial 002 generation invocation ordinal is invalid")
    raw = generation["raw_completion"]
    raw_bytes = generation["raw_completion_bytes"]
    if raw is not None:
        if not isinstance(raw, str) or isinstance(raw_bytes, bool) or not isinstance(raw_bytes, int) or raw_bytes < len(raw.encode("utf-8")):
            raise ValidationError("Trial 002 raw completion evidence is invalid")
        if len(raw.encode("utf-8")) > 16_384:
            raise ValidationError("Trial 002 retained raw completion exceeds its bound")
    elif raw_bytes is not None:
        raise ValidationError("Trial 002 raw completion byte count is inconsistent")
    if not isinstance(generation["raw_completion_truncated"], bool) or not isinstance(generation["parse_state"], str) or not isinstance(generation["stop_reason"], str):
        raise ValidationError("Trial 002 generation evidence types are invalid")
    return record


def validate_checkpoint(checkpoint: Any, run: Mapping[str, Any], solver_cases: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "format",
        "format_version",
        "trial_id",
        "run_id",
        "run_identity_digest",
        "expected_jobs",
        "generation_invocation_quota",
        "generation_invocations",
        "completed",
        "sessions",
        "cumulative_charged_seconds",
        "complete",
    }
    if not isinstance(checkpoint, dict) or set(checkpoint) != required:
        raise ValidationError("Trial 002 checkpoint fields are invalid")
    expected = expected_job_keys(solver_cases)
    if (
        checkpoint["format"] != "irisx/arc-agi-2-trial-002-checkpoint"
        or checkpoint["format_version"] != "1.0"
        or checkpoint["trial_id"] != TRIAL_ID
        or checkpoint["run_id"] != RUN_ID
        or checkpoint["run_identity_digest"] != run["run_identity_digest"]
        or checkpoint["expected_jobs"] != expected
        or checkpoint["generation_invocation_quota"] != GENERATION_INVOCATION_QUOTA
    ):
        raise ValidationError("Trial 002 checkpoint identity is stale or substituted")
    invocations = checkpoint["generation_invocations"]
    if not isinstance(invocations, dict) or not set(invocations).issubset(expected):
        raise ValidationError("Trial 002 checkpoint contains unknown generation invocations")
    if len(invocations) > GENERATION_INVOCATION_QUOTA:
        raise ValidationError("Trial 002 generation invocation quota was exceeded")
    ordinals: list[int] = []
    for key, invocation in invocations.items():
        required_invocation = {"job_key", "ordinal", "gpu_rank", "started_utc", "terminal_utc", "status"}
        if not isinstance(invocation, dict) or set(invocation) != required_invocation or invocation.get("job_key") != key:
            raise ValidationError("Trial 002 generation invocation record is malformed")
        if invocation.get("status") not in {"started", "completed", "failed"}:
            raise ValidationError("Trial 002 generation invocation status is invalid")
        ordinal = invocation.get("ordinal")
        gpu_rank = invocation.get("gpu_rank")
        if (
            isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or isinstance(gpu_rank, bool)
            or not isinstance(gpu_rank, int)
            or gpu_rank < 0
            or gpu_rank >= WORKER_COUNT
            or not isinstance(invocation.get("started_utc"), str)
            or (invocation["status"] == "started") != (invocation.get("terminal_utc") is None)
            or (invocation.get("terminal_utc") is not None and not isinstance(invocation["terminal_utc"], str))
        ):
            raise ValidationError("Trial 002 generation invocation accounting is invalid")
        ordinals.append(ordinal)
    if sorted(ordinals) != list(range(1, len(ordinals) + 1)):
        raise ValidationError("Trial 002 generation invocation ordinals are not contiguous")
    completed = checkpoint["completed"]
    if not isinstance(completed, dict) or not set(completed).issubset(expected):
        raise ValidationError("Trial 002 checkpoint contains unknown completed jobs")
    for key, record in completed.items():
        if record.get("job_key") != key:
            raise ValidationError("Trial 002 checkpoint completed key mismatch")
        validate_prediction_record(record, set(expected))
        recorded_ordinal = record["generation"]["invocation_ordinal"]
        invocation = invocations.get(key)
        if invocation is None and recorded_ordinal is not None:
            raise ValidationError("Trial 002 terminal record invents a generation invocation")
        if invocation is not None and recorded_ordinal != invocation["ordinal"]:
            raise ValidationError("Trial 002 terminal record generation ordinal disagrees with checkpoint")
        if invocation is not None and invocation["status"] == "started":
            raise ValidationError("Trial 002 terminal record cannot reference an unfinished generation invocation")
    charged = checkpoint["cumulative_charged_seconds"]
    if isinstance(charged, bool) or not isinstance(charged, (int, float)) or charged < 0 or charged > SESSION_BUDGET_SECONDS:
        raise ValidationError("Trial 002 checkpoint cumulative budget is invalid")
    sessions = checkpoint["sessions"]
    if not isinstance(sessions, list):
        raise ValidationError("Trial 002 checkpoint sessions must be an array")
    total_session_charge = 0.0
    for index, session in enumerate(sessions):
        required_session = {"session_index", "started_utc", "hardware", "charged_seconds"}
        if not isinstance(session, dict) or set(session) != required_session:
            raise ValidationError("Trial 002 checkpoint session fields are invalid")
        session_charge = session["charged_seconds"]
        if (
            session["session_index"] != index
            or not isinstance(session["started_utc"], str)
            or not isinstance(session["hardware"], dict)
            or isinstance(session_charge, bool)
            or not isinstance(session_charge, (int, float))
            or session_charge < 0
            or session_charge > SESSION_BUDGET_SECONDS
        ):
            raise ValidationError("Trial 002 checkpoint session accounting is invalid")
        total_session_charge += float(session_charge)
    if abs(total_session_charge - float(charged)) > 1.0:
        raise ValidationError("Trial 002 checkpoint cumulative charge does not match its sessions")
    if checkpoint["complete"] != (set(completed) == set(expected)):
        raise ValidationError("Trial 002 checkpoint completeness flag is false or overstated")
    return checkpoint


def start_generation_invocation(
    checkpoint: dict[str, Any],
    job_key: str,
    gpu_rank: int,
    run: Mapping[str, Any],
    solver_cases: Mapping[str, Any],
) -> int:
    if job_key not in checkpoint["expected_jobs"] or job_key in checkpoint["generation_invocations"]:
        raise ValidationError(f"invalid or duplicate Trial 002 generation invocation: {job_key}")
    if len(checkpoint["generation_invocations"]) >= GENERATION_INVOCATION_QUOTA:
        raise ValidationError("Trial 002 generation invocation quota exhausted")
    ordinal = len(checkpoint["generation_invocations"]) + 1
    checkpoint["generation_invocations"][job_key] = {
        "job_key": job_key,
        "ordinal": ordinal,
        "gpu_rank": gpu_rank,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "terminal_utc": None,
        "status": "started",
    }
    validate_checkpoint(checkpoint, run, solver_cases)
    return ordinal


def finish_generation_invocation(
    checkpoint: dict[str, Any],
    job_key: str,
    status: str,
    run: Mapping[str, Any],
    solver_cases: Mapping[str, Any],
) -> None:
    invocation = checkpoint["generation_invocations"].get(job_key)
    if not isinstance(invocation, dict) or invocation.get("status") != "started" or status not in {"completed", "failed"}:
        raise ValidationError(f"cannot finish Trial 002 generation invocation: {job_key}")
    invocation["status"] = status
    invocation["terminal_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    validate_checkpoint(checkpoint, run, solver_cases)


def record_terminal(checkpoint: dict[str, Any], record: dict[str, Any], run: Mapping[str, Any], solver_cases: Mapping[str, Any]) -> None:
    expected = set(expected_job_keys(solver_cases))
    validate_prediction_record(record, expected)
    key = record["job_key"]
    if key in checkpoint["completed"]:
        raise ValidationError(f"duplicate terminal Trial 002 job: {key}")
    checkpoint["completed"][key] = record
    checkpoint["complete"] = set(checkpoint["completed"]) == expected
    validate_checkpoint(checkpoint, run, solver_cases)


def atomically_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_bytes(value, newline=True))
    os.replace(temporary, path)


def load_checkpoint(
    path: Path,
    run: Mapping[str, Any],
    solver_cases: Mapping[str, Any],
) -> dict[str, Any]:
    """Load a canonical, identity-bound checkpoint for a bounded resume."""

    checkpoint = _load_canonical(path)
    validate_checkpoint(checkpoint, run, solver_cases)
    return checkpoint


@dataclass
class SupervisorState:
    """Pure state machine used by the four-process Kaggle supervisor and tests."""

    expected_by_task: dict[str, list[str]]
    task_deadline_seconds: float = TASK_DEADLINE_SECONDS
    session_stop_seconds: float = SESSION_BUDGET_SECONDS - FINALIZATION_RESERVE_SECONDS
    dispatched_at: dict[str, float] = field(default_factory=dict)
    terminal: dict[str, dict[str, Any]] = field(default_factory=dict)

    def dispatch(self, task_id: str, now: float) -> None:
        if task_id not in self.expected_by_task or task_id in self.dispatched_at:
            raise ValidationError(f"invalid or duplicate task dispatch: {task_id}")
        self.dispatched_at[task_id] = now

    def accept(self, record: dict[str, Any]) -> None:
        key = record.get("job_key")
        expected = {item for values in self.expected_by_task.values() for item in values}
        validate_prediction_record(record, expected)
        if key in self.terminal:
            raise ValidationError(f"duplicate supervisor job result: {key}")
        self.terminal[key] = record

    def expired_tasks(self, now: float) -> list[str]:
        return sorted(
            task_id
            for task_id, started in self.dispatched_at.items()
            if now - started >= self.task_deadline_seconds
            and any(key not in self.terminal for key in self.expected_by_task[task_id])
        )

    def may_start_or_continue(self, session_elapsed: float) -> bool:
        return session_elapsed < self.session_stop_seconds


def build_result_package(
    output: Path,
    run: Mapping[str, Any],
    solver_cases: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    observations: Mapping[str, Any],
    progress_jsonl: bytes,
) -> str:
    validate_checkpoint(checkpoint, run, solver_cases)
    if not checkpoint["complete"]:
        raise ValidationError("Trial 002 result package requires terminal records for all specified jobs")
    predictions = {
        "format": "irisx/arc-agi-2-trial-002-predictions",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "records": [checkpoint["completed"][key] for key in checkpoint["expected_jobs"]],
    }
    files = {
        "bindings/run.json": _strict_json_bytes(dict(run)),
        "checkpoint/checkpoint.json": _strict_json_bytes(dict(checkpoint)),
        "predictions/predictions.json": _strict_json_bytes(predictions),
        "observations/execution.json": _strict_json_bytes(dict(observations)),
        "logs/progress.jsonl": progress_jsonl,
    }
    metadata = {
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "run_identity_digest": run["run_identity_digest"],
        "configuration_digest": run["configuration_digest"],
        "job_count": len(checkpoint["expected_jobs"]),
        "truth_free": True,
    }
    return write_zip(output, RESULT_KIND, RUN_ID, files, metadata, limits=RESULT_LIMITS)


def validate_progress_log(progress: bytes, selected_task_ids: Iterable[str]) -> None:
    allowed_task_ids = set(selected_task_ids)
    if not allowed_task_ids or any(not isinstance(task_id, str) for task_id in allowed_task_ids):
        raise ValidationError("Trial 002 progress log task binding is malformed")
    if not progress or not progress.endswith(b"\n"):
        raise ValidationError("Trial 002 progress log is empty or unterminated")
    for line in progress.splitlines():
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Trial 002 progress log contains invalid JSON") from exc
        if not isinstance(event, dict):
            raise ValidationError("Trial 002 progress log event is malformed")
        if isinstance(event.get("event"), str):
            continue
        rank = event.get("rank")
        if (
            event.get("type") == "stage"
            and event.get("stage") in {"model_load", "single_generate"}
            and event.get("task_id") in allowed_task_ids
            and isinstance(rank, int)
            and not isinstance(rank, bool)
            and 0 <= rank < WORKER_COUNT
        ):
            continue
        raise ValidationError("Trial 002 progress log event is malformed")


def verify_result_package(path: Path, outbound: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    _, outbound_contents, _ = verify_outbound_package(outbound)
    outbound_run = json.loads(outbound_contents["bindings/run.json"])
    solver = json.loads(outbound_contents["cases/solver-cases.json"])
    manifest, contents, result_digest = verify_zip(path, limits=RESULT_LIMITS, package_kind=RESULT_KIND)
    if set(contents) != RESULT_PATHS:
        raise ValidationError("Trial 002 result membership is not the closed-world profile")
    returned_run = json.loads(contents["bindings/run.json"])
    if returned_run != outbound_run:
        raise ValidationError("Trial 002 result run binding is stale or substituted")
    checkpoint = json.loads(contents["checkpoint/checkpoint.json"])
    validate_checkpoint(checkpoint, returned_run, solver)
    if not checkpoint["complete"]:
        raise ValidationError("partial Trial 002 checkpoint cannot masquerade as a complete result")
    predictions = json.loads(contents["predictions/predictions.json"])
    if set(predictions) != {"format", "format_version", "trial_id", "run_id", "records"} or (
        predictions["format"] != "irisx/arc-agi-2-trial-002-predictions"
        or predictions["format_version"] != "1.0"
        or predictions["trial_id"] != TRIAL_ID
        or predictions["run_id"] != RUN_ID
    ):
        raise ValidationError("Trial 002 prediction envelope identity is invalid")
    records = predictions.get("records")
    expected_records = [checkpoint["completed"][key] for key in checkpoint["expected_jobs"]]
    if records != expected_records:
        raise ValidationError("Trial 002 predictions differ from the identity-bound checkpoint")
    observations = json.loads(contents["observations/execution.json"])
    required_observations = {
        "format",
        "format_version",
        "trial_id",
        "run_id",
        "session_wall_seconds",
        "hardware",
        "nvidia_smi_rows",
        "software",
        "competition_input",
        "internet_enabled",
        "external_paid_cost_usd",
        "model_loads",
        "generation_invocation_quota",
        "generation_invocation_status_counts",
        "valid_generation_jobs",
        "terminal_status_counts",
        "ttft_state",
        "gpu_busy_time_state",
    }
    if not isinstance(observations, dict) or set(observations) != required_observations:
        raise ValidationError("Trial 002 execution observations are incomplete")
    if observations["internet_enabled"] is not False or observations["external_paid_cost_usd"] != 0:
        raise ValidationError("Trial 002 result reports prohibited network or paid execution")
    wall_seconds = observations["session_wall_seconds"]
    if isinstance(wall_seconds, bool) or not isinstance(wall_seconds, (int, float)) or wall_seconds < 0 or wall_seconds > SESSION_BUDGET_SECONDS:
        raise ValidationError("Trial 002 session exceeded its bound")
    if (
        observations["format"] != "irisx/arc-agi-2-trial-002-execution"
        or observations["format_version"] != "2.0"
        or observations["trial_id"] != TRIAL_ID
        or observations["run_id"] != RUN_ID
    ):
        raise ValidationError("Trial 002 execution observation identity is invalid")
    hardware = observations["hardware"]
    if not isinstance(hardware, list) or len(hardware) != WORKER_COUNT:
        raise ValidationError("Trial 002 result does not report exactly four GPUs")
    for device in hardware:
        if (
            not isinstance(device, dict)
            or "L4" not in str(device.get("name"))
            or not isinstance(device.get("memory_mib"), int)
            or device["memory_mib"] < 22000
        ):
            raise ValidationError("Trial 002 result reports an unsupported GPU")
    if not isinstance(observations["nvidia_smi_rows"], list) or len(observations["nvidia_smi_rows"]) != WORKER_COUNT:
        raise ValidationError("Trial 002 result lacks independent four-GPU nvidia-smi evidence")
    if observations["competition_input"] != {
        "competition_slug": COMPETITION_SLUG,
        "challenge_file": COMPETITION_CHALLENGE_FILENAME,
        "challenge_digest": returned_run["source"]["competition_challenge_digest"],
        "available_task_count": observations["competition_input"].get("available_task_count"),
        "selected_task_ids": [case["task_id"] for case in solver["cases"]],
        "selected_test_index": 0,
        "solutions_opened": False,
    } or not isinstance(observations["competition_input"].get("available_task_count"), int):
        raise ValidationError("Trial 002 result competition mount evidence is invalid")
    statuses = Counter(record["status"] for record in expected_records)
    if observations["valid_generation_jobs"] != statuses.get("valid", 0) or observations["terminal_status_counts"] != dict(sorted(statuses.items())):
        raise ValidationError("Trial 002 execution counts disagree with terminal records")
    if set(observations["software"]) != {"python", "torch", "transformers", "cuda", "cudnn"}:
        raise ValidationError("Trial 002 software observation fields are incomplete")
    if observations["software"]["transformers"] != "5.8.1":
        raise ValidationError("Trial 002 result used an unbound solver runtime")
    invocation_statuses = Counter(item["status"] for item in checkpoint["generation_invocations"].values())
    if (
        observations["generation_invocation_quota"] != GENERATION_INVOCATION_QUOTA
        or observations["generation_invocation_status_counts"] != dict(sorted(invocation_statuses.items()))
        or len(checkpoint["generation_invocations"]) > GENERATION_INVOCATION_QUOTA
    ):
        raise ValidationError("Trial 002 result generation invocation accounting is invalid")
    if observations["ttft_state"] != "unknown" or observations["gpu_busy_time_state"] != "unknown":
        raise ValidationError("Trial 002 unavailable metrics must remain explicitly unknown")
    for logical in (
        "bindings/run.json",
        "checkpoint/checkpoint.json",
        "predictions/predictions.json",
        "observations/execution.json",
    ):
        parsed = json.loads(contents[logical])
        if contents[logical] != canonical_bytes(parsed, newline=True):
            raise ValidationError(f"Trial 002 result JSON is not canonical: {logical}")
    validate_progress_log(
        contents["logs/progress.jsonl"],
        (case["task_id"] for case in solver["cases"]),
    )
    metadata = manifest["metadata"]
    if metadata != {
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "run_identity_digest": returned_run["run_identity_digest"],
        "configuration_digest": returned_run["configuration_digest"],
        "job_count": len(checkpoint["expected_jobs"]),
        "truth_free": True,
    }:
        raise ValidationError("Trial 002 result metadata binding is stale")
    forbidden = (b"evaluator-truth", b'"expected_output"', b'"score"', b'"feedback"')
    if any(marker in payload for marker in forbidden for payload in contents.values()):
        raise ValidationError("Trial 002 result contains evaluator truth, score, or feedback")
    return manifest, contents, result_digest


def import_quarantine(result: Path, outbound: Path, quarantine_root: Path) -> Path:
    _, _, result_digest = verify_result_package(result, outbound)
    target = quarantine_root / RUN_ID / result_digest.removeprefix("sha256:")
    if target.exists():
        raise ValidationError(f"Trial 002 quarantine target already exists: {target}")
    temporary = quarantine_root / f".{RUN_ID}-{time.time_ns()}.tmp"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        extract_verified_zip(result, temporary, limits=RESULT_LIMITS, package_kind=RESULT_KIND)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def score_predictions(truth: Mapping[str, Any], predictions: Mapping[str, Any]) -> dict[str, Any]:
    """Score exact-match pass@2 over test outputs, not all-or-nothing tasks."""

    truth_cases = truth.get("cases")
    records = predictions.get("records")
    if not isinstance(truth_cases, list) or not isinstance(records, list):
        raise ValidationError("Trial 002 scoring inputs are malformed")
    by_key: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record.get("job_key") if isinstance(record, dict) else None
        if not isinstance(key, str) or key in by_key:
            raise ValidationError("Trial 002 scoring predictions contain a missing or duplicate job key")
        by_key[key] = record
    passed = 0
    total = 0
    task_diagnostics: list[dict[str, Any]] = []
    for case in truth_cases:
        task_id = case["task_id"]
        task_passed = 0
        for test_index, pair in enumerate(case["test"]):
            total += 1
            expected = pair["output"]
            record = by_key.get(f"{task_id}:{test_index}")
            attempts = record.get("attempts", []) if isinstance(record, dict) else []
            hit = any(attempt == expected for attempt in attempts[:PREDICTIONS_PER_TEST])
            if hit:
                passed += 1
                task_passed += 1
        task_diagnostics.append(
            {
                "task_id": task_id,
                "passed_test_outputs": task_passed,
                "test_outputs": len(case["test"]),
                "task_all_correct": task_passed == len(case["test"]),
            }
        )
    expected_keys = {f"{case['task_id']}:{index}" for case in truth_cases for index in range(len(case["test"]))}
    if set(by_key) != expected_keys:
        raise ValidationError("Trial 002 score denominator and prediction job set differ")
    return {
        "format": "irisx/arc-agi-2-trial-002-score",
        "format_version": "1.0",
        "metric": "test-output exact-match pass@2 mean",
        "passed_test_outputs": passed,
        "total_test_outputs": total,
        "score": passed / total if total else 0.0,
        "task_all_correct_count": sum(item["task_all_correct"] for item in task_diagnostics),
        "task_count": len(task_diagnostics),
        "tasks": task_diagnostics,
    }


def score_quarantined(trial_root: Path, quarantined: Path) -> dict[str, Any]:
    truth = _load_canonical(trial_root / "evaluator-truth.json")
    predictions = _load_canonical(quarantined / "predictions/predictions.json")
    return score_predictions(truth, predictions)

"""ARC-AGI-2 prompt-pilot preparation and truth-free transport.

This is a new trial surface.  It deliberately does not mutate or reinterpret
the retained Trial 001/002 identities.  Model imports remain in the Kaggle
runner so local preparation and validation are offline and CPU-only.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
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
from .arc_trial_002 import (
    MODEL_FILES,
    MODEL_LICENSE,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    create_model_manifest,
    grid_to_text,
    parse_grid_text,
    validate_material_manifest,
)
from .canonical import canonical_bytes, digest_bytes, digest_value, read_json, write_json
from .errors import ValidationError
from .transport import RESULT_LIMITS, TRIAL_LIMITS, digest_path, verify_zip, write_zip


TRIAL_ID = "arc-agi-2-prompt-pilot"
RUN_ID = "prompt-pilot-baseline-001"
SOURCE_SPLIT = "training"
SPLIT_SEED = "arc-agi-2-prompt-pilot-split-v1"
TRAIN_COUNT = 256
DEV_COUNT = 128
HOLDOUT_COUNT = 128
BASELINE_JOB_COUNT = TRAIN_COUNT + DEV_COUNT
WORKER_COUNT = 4
TASK_DEADLINE_SECONDS = 300
SESSION_BUDGET_SECONDS = 39_600
FINALIZATION_RESERVE_SECONDS = 900

COMPETITION_SLUG = "arc-prize-2026-arc-agi-2"
COMPETITION_CHALLENGE_FILENAME = "arc-agi_training_challenges.json"
COMPETITION_CHALLENGE_SHA256 = "779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5"
KAGGLE_MACHINE_SHAPE = "NvidiaL4"
BASE_DATASET_REF = "danielwuu/irisx-arc-agi-2-trial-002-smoke-001"
BASE_DATASET_VERSION = 2
RUNTIME_DATASET_REF = "danielwuu/irisx-arc-agi-2-prompt-pilot-baseline-001"
KAGGLE_KERNEL_REF = "danielwuu/iris-x-arc-agi-2-prompt-pilot-baseline-001"

SMOKE_TASK_IDS = ("2dd70a9a", "992798f6", "305b1341", "d968ffd4")
BASE_INSTRUCTION = (
    "Infer the transformation from the examples. Return only the output grid as digit rows, "
    "with no explanation."
)

OUTBOUND_KIND = "irisx/arc-agi-2-prompt-pilot-input"
RESULT_KIND = "irisx/arc-agi-2-prompt-pilot-result"
OUTBOUND_PATHS = {
    "bindings/run.json",
    "cases/solver-cases.json",
    "runtime/dependencies.json",
    "runtime/runner.py",
    "runtime/core.py",
    "sources/model-manifest.json",
    "sources/base-wheel-manifest.json",
    "sources/runtime-wheel-manifest.json",
}
RESULT_PATHS = {
    "bindings/run.json",
    "checkpoint/checkpoint.json",
    "predictions/predictions.json",
    "observations/execution.json",
    "logs/progress.jsonl",
}
TERMINAL_STATUSES = {"valid", "invalid", "timeout", "oom", "worker_crash", "not_executed"}


def _ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValidationError(f"output directory must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _load_canonical(path: Path) -> Any:
    value = read_json(path)
    if path.read_bytes() != canonical_bytes(value, newline=True):
        raise ValidationError(f"JSON is not canonical: {path}")
    return value


def _shape(grid: Any) -> tuple[int, int]:
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        raise ValidationError("ARC grid is malformed")
    return len(grid), len(grid[0])


def visible_projection(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "train": [{"input": pair["input"], "output": pair["output"]} for pair in task["train"]],
        "test": [{"input": pair["input"]} for pair in task["test"]],
    }


def _normalize_colors(grids: list[list[list[int]]]) -> list[list[list[int]]]:
    mapping: dict[int, int] = {}
    normalized: list[list[list[int]]] = []
    for grid in grids:
        out: list[list[int]] = []
        for row in grid:
            target: list[int] = []
            for cell in row:
                if cell not in mapping:
                    mapping[cell] = len(mapping)
                target.append(mapping[cell])
            out.append(target)
        normalized.append(out)
    return normalized


def near_duplicate_fingerprint(task: Mapping[str, Any]) -> str:
    """Fingerprint visible content invariant to global color renaming.

    This intentionally conservative rule catches exact copies and color-renamed
    copies without grouping merely shape-similar tasks.
    """

    grids: list[list[list[int]]] = []
    layout: list[list[Any]] = []
    for pair in task["train"]:
        layout.extend((("train-input", len(grids)), ("train-output", len(grids) + 1)))
        grids.extend((pair["input"], pair["output"]))
    for pair in task["test"]:
        layout.append(["test-input", len(grids)])
        grids.append(pair["input"])
    payload = {"layout": [list(item) for item in layout], "grids": _normalize_colors(grids)}
    return digest_value(payload)


def task_stratum(task: Mapping[str, Any]) -> str:
    cells = sum(h * w for pair in task["train"] for h, w in (_shape(pair["input"]), _shape(pair["output"])))
    cells += sum(_shape(pair["input"])[0] * _shape(pair["input"])[1] for pair in task["test"])
    demo_bin = "1-2" if len(task["train"]) <= 2 else ("3" if len(task["train"]) == 3 else "4+")
    cell_bin = "small" if cells <= 256 else ("medium" if cells <= 1024 else "large")
    return f"demos={demo_bin};visible_cells={cell_bin}"


def freeze_split(training_dir: Path) -> dict[str, Any]:
    groups: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    by_fingerprint: dict[str, list[str]] = defaultdict(list)
    tasks: dict[str, Mapping[str, Any]] = {}
    for path in sorted(training_dir.glob("*.json")):
        task = validate_task(read_json(path), f"training/{path.name}", require_test_outputs=True)
        tasks[path.stem] = task
        by_fingerprint[near_duplicate_fingerprint(task)].append(path.stem)
    excluded = set(SMOKE_TASK_IDS)
    for fingerprint, ids in by_fingerprint.items():
        if excluded.intersection(ids):
            excluded.update(ids)
            continue
        representative = min(ids)
        task = tasks[representative]
        rank = hashlib.sha256(f"{SPLIT_SEED}:{representative}".encode()).hexdigest()
        groups[task_stratum(task)].append((rank, representative, fingerprint))
    queues = {key: deque(sorted(value)) for key, value in groups.items()}
    selected: list[tuple[str, str, str, str]] = []
    while len(selected) < TRAIN_COUNT + DEV_COUNT + HOLDOUT_COUNT:
        progressed = False
        for stratum in sorted(queues):
            if queues[stratum] and len(selected) < TRAIN_COUNT + DEV_COUNT + HOLDOUT_COUNT:
                rank, task_id, fingerprint = queues[stratum].popleft()
                selected.append((rank, task_id, fingerprint, stratum))
                progressed = True
        if not progressed:
            raise ValidationError("not enough distinct public-training tasks for the frozen split")
    lanes = ("optimization-train", "optimization-train", "selection-dev", "locked-holdout")
    records = [
        {"task_id": task_id, "group": lanes[index % 4], "stratum": stratum, "rank": rank, "visible_fingerprint": fingerprint}
        for index, (rank, task_id, fingerprint, stratum) in enumerate(selected)
    ]
    counts = Counter(item["group"] for item in records)
    expected = {"optimization-train": TRAIN_COUNT, "selection-dev": DEV_COUNT, "locked-holdout": HOLDOUT_COUNT}
    if dict(counts) != expected:
        raise ValidationError(f"frozen split count mismatch: {dict(counts)}")
    return {
        "format": "irisx/arc-agi-2-prompt-pilot-split",
        "format_version": "1.0",
        "seed": SPLIT_SEED,
        "source_split": SOURCE_SPLIT,
        "selection": "round-robin over fixed demonstration-count/visible-cell strata; sha256(seed:task_id) within stratum",
        "near_duplicate_rule": "visible demonstrations and test inputs, invariant to global first-seen color renaming",
        "excluded_smoke_task_ids": list(SMOKE_TASK_IDS),
        "excluded_task_ids": sorted(excluded),
        "counts": expected,
        "records": records,
    }


def render_messages(instruction: str, train: list[dict[str, Any]], test_input: list[list[int]]) -> list[dict[str, str]]:
    demonstrations = "\n\n".join(
        f"Example {index + 1} input:\n{grid_to_text(pair['input'])}\n"
        f"Example {index + 1} output:\n{grid_to_text(pair['output'])}"
        for index, pair in enumerate(train)
    )
    return [{"role": "user", "content": f"{instruction}\n\n{demonstrations}\n\nTest input:\n{grid_to_text(test_input)}"}]


def render_b0(case: Mapping[str, Any]) -> list[dict[str, str]]:
    return render_messages(BASE_INSTRUCTION, case["train"], case["test"][0]["input"])


def render_b1(case: Mapping[str, Any]) -> list[dict[str, str]]:
    # The DSPy-facing adapter is intentionally a pure instruction parameter.
    return render_messages(BASE_INSTRUCTION, case["train"], case["test"][0]["input"])


def assert_render_parity(cases: Iterable[Mapping[str, Any]], tokenizer: Any | None = None) -> dict[str, Any]:
    count = 0
    for case in cases:
        b0, b1 = render_b0(case), render_b1(case)
        if b0 != b1:
            raise ValidationError(f"B0/B1 rendered-message parity failed: {case['task_id']}")
        if tokenizer is not None:
            p0 = tokenizer.apply_chat_template(b0, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            p1 = tokenizer.apply_chat_template(b1, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            if p0 != p1 or tokenizer(p0, add_special_tokens=False)["input_ids"] != tokenizer(p1, add_special_tokens=False)["input_ids"]:
                raise ValidationError(f"B0/B1 token parity failed: {case['task_id']}")
        count += 1
    return {"case_count": count, "messages_equal": True, "token_ids_equal": tokenizer is not None}


def _configuration() -> dict[str, Any]:
    return {
        "worker_count": WORKER_COUNT,
        "scheduling": "four persistent one-model-per-GPU workers; initial rank assignment then dynamic dispatch",
        "accelerator_requirement": {"gpu_model_contains": "L4", "gpu_count": 4, "minimum_memory_mib_each": 22000},
        "session_budget_seconds": SESSION_BUDGET_SECONDS,
        "finalization_reserve_seconds": FINALIZATION_RESERVE_SECONDS,
        "task_deadline_seconds": TASK_DEADLINE_SECONDS,
        "generation": {"invocation_quota": BASELINE_JOB_COUNT, "num_return_sequences": 1, "num_beams": 1, "do_sample": False, "maximum_new_tokens": 512, "enable_thinking": False, "seed": 20260922},
        "retry": False,
        "warmup_generation": False,
    }


def _competition(path: Path) -> dict[str, Any]:
    if path.name != COMPETITION_CHALLENGE_FILENAME or digest_path(path) != f"sha256:{COMPETITION_CHALLENGE_SHA256}":
        raise ValidationError("competition challenge filename or digest is not the bound source")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict) or len(value) != 1000:
        raise ValidationError("competition challenge source must contain 1000 public-training tasks")
    return value


def prepare_trial(source_root: Path, competition_challenges: Path, output: Path) -> dict[str, Any]:
    provenance = validate_source(source_root)
    training = source_root / "upstream/data/training"
    split = freeze_split(training)
    competition = _competition(competition_challenges)
    _ensure_empty(output)
    solver_cases: list[dict[str, Any]] = []
    truth_cases: list[dict[str, Any]] = []
    group_by_id = {item["task_id"]: item["group"] for item in split["records"]}
    for item in split["records"]:
        task_id = item["task_id"]
        official = validate_task(read_json(training / f"{task_id}.json"), f"training/{task_id}.json", require_test_outputs=True)
        challenge = validate_task(competition[task_id], f"competition/{task_id}", require_test_outputs=False)
        projection = visible_projection(official)
        if challenge != projection:
            raise ValidationError(f"competition challenge differs from pinned source: {task_id}")
        truth_cases.append({"task_id": task_id, "group": item["group"], "test_index": 0, "output": official["test"][0]["output"]})
        if item["group"] != "locked-holdout":
            solver_cases.append({"task_id": task_id, "group": item["group"], "train": challenge["train"], "test": [{"input": challenge["test"][0]["input"]}]})
    solver = {"format": "irisx/arc-agi-2-prompt-pilot-solver-cases", "format_version": "1.0", "trial_id": TRIAL_ID, "run_id": RUN_ID, "instruction": BASE_INSTRUCTION, "cases": solver_cases}
    truth = {"format": "irisx/arc-agi-2-prompt-pilot-evaluator-truth", "format_version": "1.0", "trial_id": TRIAL_ID, "cases": truth_cases}
    config = _configuration()
    run = {
        "format": "irisx/arc-agi-2-prompt-pilot-run-binding", "format_version": "1.0", "trial_id": TRIAL_ID, "run_id": RUN_ID,
        "source": {"repository": "https://github.com/arcprize/ARC-AGI-2.git", "commit": ARC_COMMIT, "provenance_digest": provenance["content_digest"], "competition_slug": COMPETITION_SLUG, "competition_challenge_file": COMPETITION_CHALLENGE_FILENAME, "competition_challenge_digest": f"sha256:{COMPETITION_CHALLENGE_SHA256}", "solutions_opened_in_runtime": False},
        "model": {"repository": MODEL_REPOSITORY, "revision": MODEL_REVISION, "license": MODEL_LICENSE},
        "prompt": {"candidate": "B1", "instruction": BASE_INSTRUCTION, "instruction_digest": digest_value(BASE_INSTRUCTION), "b0_b1_render_parity": True},
        "split_digest": digest_value(split), "solver_cases_digest": digest_value(solver), "configuration": config, "configuration_digest": digest_value(config),
    }
    run["run_identity_digest"] = digest_value(run)
    write_json(output / "split.json", split)
    write_json(output / "solver-cases.json", solver)
    write_json(output / "evaluator-truth.json", truth)
    write_json(output / "run-binding.json", run)
    validate_trial(output)
    return run


def validate_trial(root: Path) -> dict[str, Any]:
    split, solver, truth, run = (_load_canonical(root / name) for name in ("split.json", "solver-cases.json", "evaluator-truth.json", "run-binding.json"))
    if run.get("trial_id") != TRIAL_ID or run.get("run_id") != RUN_ID:
        raise ValidationError("prompt-pilot run identity is invalid")
    if run.get("split_digest") != digest_value(split) or run.get("solver_cases_digest") != digest_value(solver):
        raise ValidationError("prompt-pilot split or solver binding is stale")
    identity = {key: value for key, value in run.items() if key != "run_identity_digest"}
    if run.get("run_identity_digest") != digest_value(identity) or run.get("configuration") != _configuration():
        raise ValidationError("prompt-pilot run digest or configuration is stale")
    counts = Counter(item["group"] for item in split["records"])
    if counts != Counter({"optimization-train": TRAIN_COUNT, "selection-dev": DEV_COUNT, "locked-holdout": HOLDOUT_COUNT}):
        raise ValidationError("prompt-pilot split counts are invalid")
    if len(solver.get("cases", [])) != BASELINE_JOB_COUNT or len(truth.get("cases", [])) != TRAIN_COUNT + DEV_COUNT + HOLDOUT_COUNT:
        raise ValidationError("prompt-pilot workload cardinality is invalid")
    if {item["task_id"] for item in solver["cases"]} & set(SMOKE_TASK_IDS):
        raise ValidationError("prompt-pilot baseline includes a prior smoke task")
    if any(set(pair) != {"input"} for case in solver["cases"] for pair in case["test"]):
        raise ValidationError("prompt-pilot solver cases contain evaluator truth")
    assert_render_parity(solver["cases"])
    return run


def validate_competition_mount(path: Path, run: Mapping[str, Any], solver: Mapping[str, Any]) -> dict[str, Any]:
    competition = _competition(path)
    if run["source"]["competition_challenge_digest"] != digest_path(path):
        raise ValidationError("runtime competition digest differs from run binding")
    for case in solver["cases"]:
        mounted = competition[case["task_id"]]
        selected = {"train": mounted["train"], "test": [{"input": mounted["test"][0]["input"]}]}
        if selected != {"train": case["train"], "test": case["test"]}:
            raise ValidationError(f"runtime competition case differs: {case['task_id']}")
    return {"competition_slug": COMPETITION_SLUG, "challenge_digest": digest_path(path), "available_task_count": len(competition), "selected_job_count": len(solver["cases"]), "selected_test_index": 0, "solutions_opened": False}


def _manifest_for_files(root: Path, files: Iterable[Path], kind: str) -> dict[str, Any]:
    entries = []
    for path in sorted(files, key=lambda item: item.name.lower()):
        entries.append({"path": path.relative_to(root).as_posix(), "byte_size": path.stat().st_size, "content_digest": digest_path(path)})
    return {"format": kind, "format_version": "1.0", "files": entries, "manifest_digest": digest_value(entries)}


def create_base_wheel_manifest(root: Path) -> dict[str, Any]:
    wheels = sorted(root.glob("*.whl"))
    required = ("transformers-5.8.1", "jinja2-3.1.6", "tokenizers-0.22.2", "safetensors-0.8.0")
    selected = [path for path in wheels if any(path.name.lower().startswith(prefix) for prefix in required)]
    if len(selected) != len(required):
        raise ValidationError("base Dataset is missing the pinned offline inference wheels")
    manifest = _manifest_for_files(root, selected, "irisx/prompt-pilot-base-wheel-manifest")
    manifest.update({"dataset_ref": BASE_DATASET_REF, "dataset_version": BASE_DATASET_VERSION})
    return manifest


def create_reused_model_manifest(root: Path) -> dict[str, Any]:
    paths = [root / name for name in MODEL_FILES]
    if any(not path.is_file() for path in paths):
        raise ValidationError("base Dataset is missing one or more pinned Qwen3.5-4B files")
    config = json.loads((root / "config.json").read_bytes())
    text = config.get("text_config", config)
    if text.get("model_type") != "qwen3_5_text" or text.get("hidden_size") != 2560 or text.get("num_hidden_layers") != 32:
        raise ValidationError("base Dataset model architecture differs from Qwen3.5-4B")
    manifest = _manifest_for_files(root, paths, "irisx/model-material-manifest")
    manifest.update({"repository": MODEL_REPOSITORY, "revision": MODEL_REVISION, "license": MODEL_LICENSE, "total_bytes": sum(path.stat().st_size for path in paths)})
    return manifest


def validate_runtime_wheel_sources(runtime_wheel: Path, *, runner: bytes, core: bytes) -> None:
    try:
        with zipfile.ZipFile(runtime_wheel, "r") as archive:
            installed_runner = archive.read("irisx/kaggle_runner_prompt_pilot.py")
            installed_core = archive.read("irisx/arc_prompt_pilot.py")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValidationError("runtime wheel does not contain the prompt-pilot implementation") from exc
    if installed_runner != runner or installed_core != core:
        raise ValidationError("runtime wheel and bound prompt-pilot sources differ")


def build_outbound_package(trial_root: Path, base_dataset_root: Path, runtime_wheel: Path, output: Path, *, repository_root: Path) -> str:
    run = validate_trial(trial_root)
    solver = _load_canonical(trial_root / "solver-cases.json")
    model_manifest = create_reused_model_manifest(base_dataset_root)
    base_wheels = create_base_wheel_manifest(base_dataset_root)
    runtime_manifest = _manifest_for_files(runtime_wheel.parent, [runtime_wheel], "irisx/prompt-pilot-runtime-wheel-manifest")
    runner = (repository_root / "src/irisx/kaggle_runner_prompt_pilot.py").read_bytes()
    core = (repository_root / "src/irisx/arc_prompt_pilot.py").read_bytes()
    validate_runtime_wheel_sources(runtime_wheel, runner=runner, core=core)
    dependencies = {"format": "irisx/arc-agi-2-prompt-pilot-dependencies", "format_version": "1.0", "python": "3.12", "torch": "kaggle-image-preinstalled", "transformers": "5.8.1", "internet_install": False, "base_dataset_ref": BASE_DATASET_REF, "base_dataset_version": BASE_DATASET_VERSION, "model_manifest_digest": model_manifest["manifest_digest"], "base_wheel_manifest_digest": base_wheels["manifest_digest"], "runtime_wheel_manifest_digest": runtime_manifest["manifest_digest"]}
    files = {
        "bindings/run.json": (trial_root / "run-binding.json").read_bytes(), "cases/solver-cases.json": (trial_root / "solver-cases.json").read_bytes(),
        "runtime/dependencies.json": canonical_bytes(dependencies, newline=True), "runtime/runner.py": runner, "runtime/core.py": core,
        "sources/model-manifest.json": canonical_bytes(model_manifest, newline=True), "sources/base-wheel-manifest.json": canonical_bytes(base_wheels, newline=True), "sources/runtime-wheel-manifest.json": canonical_bytes(runtime_manifest, newline=True),
    }
    metadata = {"trial_id": TRIAL_ID, "run_id": RUN_ID, "run_identity_digest": run["run_identity_digest"], "solver_cases_digest": run["solver_cases_digest"], "configuration_digest": run["configuration_digest"], "runner_digest": digest_bytes(runner), "core_digest": digest_bytes(core), "model_manifest_digest": model_manifest["manifest_digest"], "base_wheel_manifest_digest": base_wheels["manifest_digest"], "runtime_wheel_manifest_digest": runtime_manifest["manifest_digest"], "truth_free": True}
    return write_zip(output, OUTBOUND_KIND, RUN_ID, files, metadata, limits=TRIAL_LIMITS)


def verify_outbound_package(path: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    manifest, contents, digest = verify_zip(path, limits=TRIAL_LIMITS, package_kind=OUTBOUND_KIND)
    if set(contents) != OUTBOUND_PATHS or manifest.get("package_id") != RUN_ID:
        raise ValidationError("prompt-pilot outbound membership or identity is invalid")
    run = json.loads(contents["bindings/run.json"])
    solver = json.loads(contents["cases/solver-cases.json"])
    if run.get("trial_id") != TRIAL_ID or run.get("run_id") != RUN_ID or run.get("solver_cases_digest") != digest_value(solver):
        raise ValidationError("prompt-pilot outbound bindings are stale")
    identity = {key: value for key, value in run.items() if key != "run_identity_digest"}
    if run.get("run_identity_digest") != digest_value(identity) or len(solver.get("cases", [])) != BASELINE_JOB_COUNT:
        raise ValidationError("prompt-pilot outbound run digest or job count is invalid")
    for logical in OUTBOUND_PATHS - {"runtime/runner.py", "runtime/core.py"}:
        parsed = json.loads(contents[logical])
        if contents[logical] != canonical_bytes(parsed, newline=True):
            raise ValidationError(f"prompt-pilot outbound JSON is not canonical: {logical}")
    if any(set(pair) != {"input"} for case in solver["cases"] for pair in case["test"]):
        raise ValidationError("prompt-pilot outbound contains evaluator truth")
    forbidden = (b"evaluator-truth", b'"expected_output"', b'"score"', b'"feedback"')
    if any(marker in contents[logical] for marker in forbidden for logical in set(contents) - {"runtime/runner.py", "runtime/core.py"}):
        raise ValidationError("prompt-pilot outbound contains prohibited truth or feedback")
    return manifest, contents, digest


def stage_dataset(outbound: Path, runtime_wheel: Path, output: Path) -> dict[str, Any]:
    _ensure_empty(output)
    metadata = {"title": "IRIS-X ARC-AGI-2 Prompt Pilot Baseline 001", "id": RUNTIME_DATASET_REF, "description": "Private small truth-free runner and outbound transport; model and dependencies remain in the bound Trial 002 transport Dataset.", "licenses": [{"name": "other"}]}
    write_json(output / "dataset-metadata.json", metadata)
    shutil.copy2(outbound, output / outbound.name)
    shutil.copy2(runtime_wheel, output / runtime_wheel.name)
    return validate_dataset_staging(output, outbound, runtime_wheel)


def validate_dataset_staging(root: Path, outbound: Path, runtime_wheel: Path) -> dict[str, Any]:
    metadata = _load_canonical(root / "dataset-metadata.json")
    if metadata.get("id") != RUNTIME_DATASET_REF:
        raise ValidationError("runtime Dataset staging identity is stale")
    staged_outbound, staged_wheel = root / outbound.name, root / runtime_wheel.name
    if digest_path(staged_outbound) != digest_path(outbound) or digest_path(staged_wheel) != digest_path(runtime_wheel):
        raise ValidationError("runtime Dataset staging bytes are stale")
    if any(path.name in {"evaluator-truth.json", "arc-agi_training_solutions.json", "arc-agi_evaluation_solutions.json"} for path in root.rglob("*")):
        raise ValidationError("runtime Dataset staging contains evaluator truth")
    return {"dataset_ref": RUNTIME_DATASET_REF, "outbound_digest": digest_path(staged_outbound), "runtime_wheel_digest": digest_path(staged_wheel), "truth_free": True}


def validate_kernel_staging(root: Path, outbound_digest: str, runtime_wheel_digest: str) -> dict[str, Any]:
    metadata = _load_canonical(root / "kernel-metadata.json")
    expected = {"id": KAGGLE_KERNEL_REF, "is_private": True, "enable_gpu": True, "enable_internet": False, "machine_shape": KAGGLE_MACHINE_SHAPE, "dataset_sources": [BASE_DATASET_REF, RUNTIME_DATASET_REF], "competition_sources": [COMPETITION_SLUG]}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValidationError(f"Kaggle kernel metadata is stale: {key}")
    notebook = json.loads((root / metadata["code_file"]).read_bytes())
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"] if cell.get("cell_type") == "code")
    required = (RUN_ID, COMPETITION_CHALLENGE_FILENAME, outbound_digest.removeprefix("sha256:"), runtime_wheel_digest.removeprefix("sha256:"), "PYTHONUNBUFFERED", "kaggle_runner_prompt_pilot")
    if any(item not in source for item in required) or "__IRISX_" in source:
        raise ValidationError("Kaggle notebook contains unresolved or missing bindings")
    return metadata


def stage_kaggle_kernel(template_root: Path, output: Path, *, outbound_digest: str, runtime_wheel_digest: str) -> dict[str, Any]:
    _ensure_empty(output)
    metadata = read_json(template_root / "kernel-metadata.json")
    notebook = json.loads((template_root / metadata["code_file"]).read_bytes())
    replacements = {"__IRISX_OUTBOUND_SHA256__": outbound_digest.removeprefix("sha256:"), "__IRISX_RUNTIME_WHEEL_SHA256__": runtime_wheel_digest.removeprefix("sha256:")}
    counts = Counter()
    for cell in notebook["cells"]:
        if isinstance(cell.get("source"), list):
            updated = []
            for line in cell["source"]:
                for marker, value in replacements.items():
                    counts[marker] += line.count(marker)
                    line = line.replace(marker, value)
                updated.append(line)
            cell["source"] = updated
    if any(counts[marker] != 1 for marker in replacements):
        raise ValidationError("Kaggle notebook digest markers are missing or duplicated")
    (output / metadata["code_file"]).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_json(output / "kernel-metadata.json", metadata)
    return validate_kernel_staging(output, outbound_digest, runtime_wheel_digest)


def new_checkpoint(run: Mapping[str, Any], solver: Mapping[str, Any]) -> dict[str, Any]:
    jobs = [f"{case['task_id']}:0" for case in solver["cases"]]
    return {"format": "irisx/arc-agi-2-prompt-pilot-checkpoint", "format_version": "1.0", "trial_id": TRIAL_ID, "run_id": RUN_ID, "run_identity_digest": run["run_identity_digest"], "expected_jobs": jobs, "model_ready": {}, "generation_invocations": {}, "completed": {}, "sessions": [], "complete": False}


@dataclass
class DispatchState:
    """Pure parent-side dynamic dispatch state, independently unit-testable."""

    pending: deque[str]
    active: dict[int, tuple[str, float]] = field(default_factory=dict)
    terminal: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_jobs(cls, jobs: Iterable[str]) -> "DispatchState":
        values = list(jobs)
        if len(values) != len(set(values)):
            raise ValidationError("dispatch jobs are duplicated")
        return cls(deque(values))

    def dispatch(self, rank: int, deadline: float) -> str | None:
        if rank in self.active:
            raise ValidationError(f"worker {rank} is already active")
        if not self.pending:
            return None
        job = self.pending.popleft()
        self.active[rank] = (job, deadline)
        return job

    def finish(self, rank: int, job: str, status: str) -> None:
        if self.active.get(rank, (None,))[0] != job or job in self.terminal:
            raise ValidationError("dispatch terminal event is stale or duplicated")
        del self.active[rank]
        self.terminal[job] = status

    def expired(self, now: float) -> list[tuple[int, str]]:
        return sorted((rank, job) for rank, (job, deadline) in self.active.items() if now >= deadline)


def validate_checkpoint(checkpoint: Mapping[str, Any], run: Mapping[str, Any], solver: Mapping[str, Any]) -> None:
    expected = [f"{case['task_id']}:0" for case in solver["cases"]]
    if checkpoint.get("trial_id") != TRIAL_ID or checkpoint.get("run_id") != RUN_ID or checkpoint.get("run_identity_digest") != run["run_identity_digest"] or checkpoint.get("expected_jobs") != expected:
        raise ValidationError("prompt-pilot checkpoint identity or denominator is invalid")
    if len(checkpoint.get("generation_invocations", {})) > BASELINE_JOB_COUNT or not set(checkpoint.get("completed", {})).issubset(expected):
        raise ValidationError("prompt-pilot checkpoint exceeds its job quota")
    if not set(checkpoint.get("model_ready", {})).issubset({str(rank) for rank in range(WORKER_COUNT)}):
        raise ValidationError("prompt-pilot checkpoint has an invalid worker rank")


def atomically_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_bytes(canonical_bytes(value, newline=True))
    os.replace(temporary, path)


def build_result_package(output: Path, run: Mapping[str, Any], solver: Mapping[str, Any], checkpoint: Mapping[str, Any], observations: Mapping[str, Any], progress: bytes) -> str:
    validate_checkpoint(checkpoint, run, solver)
    records = [checkpoint["completed"][key] for key in checkpoint["expected_jobs"] if key in checkpoint["completed"]]
    files = {"bindings/run.json": canonical_bytes(run, newline=True), "checkpoint/checkpoint.json": canonical_bytes(checkpoint, newline=True), "predictions/predictions.json": canonical_bytes({"format": "irisx/arc-agi-2-prompt-pilot-predictions", "format_version": "1.0", "trial_id": TRIAL_ID, "run_id": RUN_ID, "records": records}, newline=True), "observations/execution.json": canonical_bytes(observations, newline=True), "logs/progress.jsonl": progress}
    metadata = {"trial_id": TRIAL_ID, "run_id": RUN_ID, "run_identity_digest": run["run_identity_digest"], "expected_job_count": BASELINE_JOB_COUNT, "terminal_job_count": len(records), "truth_free": True}
    return write_zip(output, RESULT_KIND, RUN_ID, files, metadata, limits=RESULT_LIMITS)


def verify_result_package(path: Path, outbound: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    _, outbound_contents, _ = verify_outbound_package(outbound)
    run, solver = json.loads(outbound_contents["bindings/run.json"]), json.loads(outbound_contents["cases/solver-cases.json"])
    manifest, contents, digest = verify_zip(path, limits=RESULT_LIMITS, package_kind=RESULT_KIND)
    if set(contents) != RESULT_PATHS or manifest.get("package_id") != RUN_ID:
        raise ValidationError("prompt-pilot result membership or identity is invalid")
    returned_run, checkpoint = json.loads(contents["bindings/run.json"]), json.loads(contents["checkpoint/checkpoint.json"])
    if returned_run != run:
        raise ValidationError("prompt-pilot result run binding differs from outbound")
    validate_checkpoint(checkpoint, run, solver)
    predictions = json.loads(contents["predictions/predictions.json"])
    records = predictions.get("records", [])
    if len(records) != len({item.get("job_key") for item in records}) or any(item.get("status") not in TERMINAL_STATUSES for item in records):
        raise ValidationError("prompt-pilot result records are duplicated or invalid")
    forbidden = (b"evaluator-truth", b'"expected_output"', b'"score"', b'"feedback"')
    if any(marker in payload for marker in forbidden for payload in contents.values()):
        raise ValidationError("prompt-pilot result contains evaluator truth or feedback")
    return manifest, contents, digest


def technical_preflight(trial_root: Path, outbound: Path, base_dataset_root: Path, runtime_wheel: Path, competition_challenges: Path, dataset_root: Path, kernel_root: Path, *, legacy_outbound: Path | None = None, legacy_result: Path | None = None) -> dict[str, Any]:
    run = validate_trial(trial_root)
    manifest, contents, outbound_digest = verify_outbound_package(outbound)
    model_manifest = json.loads(contents["sources/model-manifest.json"])
    base_wheels = json.loads(contents["sources/base-wheel-manifest.json"])
    runtime_manifest = json.loads(contents["sources/runtime-wheel-manifest.json"])
    validate_material_manifest(base_dataset_root, model_manifest)
    validate_material_manifest(base_dataset_root, base_wheels)
    validate_material_manifest(runtime_wheel.parent, runtime_manifest)
    validate_runtime_wheel_sources(runtime_wheel, runner=contents["runtime/runner.py"], core=contents["runtime/core.py"])
    solver = json.loads(contents["cases/solver-cases.json"])
    competition = validate_competition_mount(competition_challenges, run, solver)
    parity = assert_render_parity(solver["cases"])
    dataset = validate_dataset_staging(dataset_root, outbound, runtime_wheel)
    kernel = validate_kernel_staging(kernel_root, outbound_digest, digest_path(runtime_wheel))
    legacy = None
    if legacy_outbound is not None and legacy_result is not None:
        from . import arc_trial_002
        legacy_manifest, _, legacy_digest = arc_trial_002.verify_result_package(legacy_result, legacy_outbound)
        legacy = {"verified": True, "result_digest": legacy_digest, "manifest_digest": digest_value(legacy_manifest)}
    checks = {"trial_valid": True, "split_frozen": True, "outbound_valid": True, "truth_absent": True, "model_and_dependencies_reused_and_bound": True, "competition_bound": True, "render_parity": True, "persistent_four_worker_scheduler_configured": True, "task_timeout_and_checkpoint_configured": True, "small_dataset_staged": True, "kernel_staged": True, "legacy_verifier_regression": legacy is not None}
    return {"format": "irisx/arc-agi-2-prompt-pilot-preflight", "format_version": "1.0", "trial_id": TRIAL_ID, "run_id": RUN_ID, "run_identity_digest": run["run_identity_digest"], "outbound_digest": outbound_digest, "outbound_manifest_digest": digest_value(manifest), "runtime_wheel_digest": digest_path(runtime_wheel), "checks": checks, "competition": competition, "parity": parity, "dataset": dataset, "kernel": {"id": kernel["id"], "machine_shape": kernel["machine_shape"], "dataset_sources": kernel["dataset_sources"], "competition_sources": kernel["competition_sources"]}, "legacy_trial_002_result": legacy, "technical_ready": all(checks.values())}

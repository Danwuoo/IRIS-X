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
RUN_ID = "prompt-pilot-baseline-002"
SOURCE_SPLIT = "training"
SPLIT_SEED = "arc-agi-2-prompt-pilot-split-v1"
TRAIN_COUNT = 256
DEV_COUNT = 128
HOLDOUT_COUNT = 128
BASELINE_JOB_COUNT = TRAIN_COUNT + DEV_COUNT
BASELINE_SPLIT_DIGEST = "sha256:6176d88ce9a66dcc45584aa09c110898c0f782b1f97e42e1f268c3ef1f25bd2b"
MAX_PROPOSAL_ATTEMPTS = 10
MAX_GENERATION_INVOCATIONS = 4_480
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
RUNTIME_DATASET_VERSION = 2
KAGGLE_KERNEL_REF = "danielwuu/iris-x-arc-agi-2-prompt-pilot-baseline-002"
KAGGLE_SEARCH_KERNEL_REF = "danielwuu/iris-x-arc-agi-2-prompt-pilot-search"
KAGGLE_SEARCH_KERNEL_TITLE = "IRIS-X ARC-AGI-2 Prompt Pilot Search"
FINAL_HOLDOUT_RUN_ID = "prompt-pilot-final-holdout-b1"
DATASET_METADATA_FILENAME = "dataset-metadata.json"

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


def render_candidate(case: Mapping[str, Any], instruction: str) -> list[dict[str, str]]:
    return render_messages(instruction, case["train"], case["test"][0]["input"])


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


def _configuration(invocation_quota: int = BASELINE_JOB_COUNT) -> dict[str, Any]:
    return {
        "worker_count": WORKER_COUNT,
        "scheduling": "four persistent one-model-per-GPU workers; initial rank assignment then dynamic dispatch",
        "accelerator_requirement": {"gpu_model_contains": "L4", "gpu_count": 4, "minimum_memory_mib_each": 22000},
        "session_budget_seconds": SESSION_BUDGET_SECONDS,
        "finalization_reserve_seconds": FINALIZATION_RESERVE_SECONDS,
        "task_deadline_seconds": TASK_DEADLINE_SECONDS,
        "generation": {"invocation_quota": invocation_quota, "num_return_sequences": 1, "num_beams": 1, "do_sample": False, "maximum_new_tokens": 512, "enable_thinking": False, "seed": 20260922},
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
    manifest, contents, digest = verify_runtime_outbound_package(path)
    if manifest.get("package_id") != RUN_ID:
        raise ValidationError("prompt-pilot baseline outbound identity is invalid")
    return manifest, contents, digest


def _validate_runtime_binding(run: Mapping[str, Any], solver: Mapping[str, Any]) -> None:
    run_id = run.get("run_id")
    if run.get("trial_id") != TRIAL_ID or not isinstance(run_id, str) or solver.get("trial_id") != TRIAL_ID or solver.get("run_id") != run_id:
        raise ValidationError("prompt-pilot runtime identity is invalid")
    final_holdout = run_id == FINAL_HOLDOUT_RUN_ID
    if run_id != RUN_ID and not final_holdout:
        search = run.get("search")
        if not run_id.startswith("prompt-pilot-search-g") or not isinstance(search, dict):
            raise ValidationError("prompt-pilot search identity is invalid")
        round_index = search.get("round")
        if not isinstance(round_index, int) or not 1 <= round_index <= MAX_PROPOSAL_ATTEMPTS or run_id != f"prompt-pilot-search-g{round_index:02d}":
            raise ValidationError("prompt-pilot search round identity is invalid")
        if run.get("prompt", {}).get("candidate") != f"G{round_index}":
            raise ValidationError("prompt-pilot search candidate label is invalid")
    if run.get("split_digest") != BASELINE_SPLIT_DIGEST or run.get("solver_cases_digest") != digest_value(solver):
        raise ValidationError("prompt-pilot runtime split or solver binding is stale")
    identity = {key: value for key, value in run.items() if key != "run_identity_digest"}
    if run.get("run_identity_digest") != digest_value(identity):
        raise ValidationError("prompt-pilot runtime identity digest is stale")
    instruction = solver.get("instruction")
    prompt = run.get("prompt", {})
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction.encode("utf-8")) > 16_384:
        raise ValidationError("prompt-pilot instruction is invalid")
    if prompt.get("instruction") != instruction or prompt.get("instruction_digest") != digest_value(instruction):
        raise ValidationError("prompt-pilot instruction binding is stale")
    cases = solver.get("cases", [])
    expected_configuration = _configuration(HOLDOUT_COUNT if final_holdout else BASELINE_JOB_COUNT)
    if run.get("configuration") != expected_configuration or run.get("configuration_digest") != digest_value(expected_configuration):
        raise ValidationError("prompt-pilot runtime configuration changed")
    if run.get("model") != {"repository": MODEL_REPOSITORY, "revision": MODEL_REVISION, "license": MODEL_LICENSE}:
        raise ValidationError("prompt-pilot runtime model changed")
    source = run.get("source", {})
    if source.get("competition_slug") != COMPETITION_SLUG or source.get("competition_challenge_digest") != f"sha256:{COMPETITION_CHALLENGE_SHA256}" or source.get("solutions_opened_in_runtime") is not False:
        raise ValidationError("prompt-pilot runtime source binding changed")
    expected_groups = Counter({"locked-holdout": HOLDOUT_COUNT}) if final_holdout else Counter({"optimization-train": TRAIN_COUNT, "selection-dev": DEV_COUNT})
    expected_count = HOLDOUT_COUNT if final_holdout else BASELINE_JOB_COUNT
    if len(cases) != expected_count or Counter(item.get("group") for item in cases) != expected_groups:
        raise ValidationError("prompt-pilot runtime job denominator changed")
    if len({item.get("task_id") for item in cases}) != expected_count:
        raise ValidationError("prompt-pilot runtime cases are duplicated")
    if final_holdout and run.get("final_holdout") != {"decision": "0019", "selected_candidate": "B1", "comparison_candidates": ["B1"], "job_count": HOLDOUT_COUNT}:
        raise ValidationError("prompt-pilot final holdout binding is invalid")
    if any(set(pair) != {"input"} for case in cases for pair in case["test"]):
        raise ValidationError("prompt-pilot runtime cases contain evaluator truth")


def verify_runtime_outbound_package(path: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    manifest, contents, digest = verify_zip(path, limits=TRIAL_LIMITS, package_kind=OUTBOUND_KIND)
    if set(contents) != OUTBOUND_PATHS:
        raise ValidationError("prompt-pilot outbound membership or identity is invalid")
    run = json.loads(contents["bindings/run.json"])
    solver = json.loads(contents["cases/solver-cases.json"])
    if manifest.get("package_id") != run.get("run_id"):
        raise ValidationError("prompt-pilot outbound package and run identities differ")
    _validate_runtime_binding(run, solver)
    for logical in OUTBOUND_PATHS - {"runtime/runner.py", "runtime/core.py"}:
        parsed = json.loads(contents[logical])
        if contents[logical] != canonical_bytes(parsed, newline=True):
            raise ValidationError(f"prompt-pilot outbound JSON is not canonical: {logical}")
    forbidden = (b"evaluator-truth", b'"expected_output"', b'"score"', b'"feedback"')
    if any(marker in contents[logical] for marker in forbidden for logical in set(contents) - {"runtime/runner.py", "runtime/core.py"}):
        raise ValidationError("prompt-pilot outbound contains prohibited truth or feedback")
    return manifest, contents, digest


def build_search_outbound_package(
    baseline_trial_root: Path,
    baseline_outbound: Path,
    runtime_wheel: Path,
    output: Path,
    *,
    instruction: str,
    round_index: int,
    parent_instruction_digest: str,
    repository_root: Path,
) -> dict[str, Any]:
    """Build one truth-free search candidate from the frozen baseline workload."""

    baseline_run = validate_trial(baseline_trial_root)
    _, baseline_contents, _ = verify_outbound_package(baseline_outbound)
    if not 1 <= round_index <= MAX_PROPOSAL_ATTEMPTS:
        raise ValidationError("prompt-pilot search round is outside the authorized range")
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction.encode("utf-8")) > 16_384:
        raise ValidationError("prompt-pilot search instruction is invalid")
    run_id = f"prompt-pilot-search-g{round_index:02d}"
    solver = _load_canonical(baseline_trial_root / "solver-cases.json")
    solver = {**solver, "run_id": run_id, "instruction": instruction}
    run = {
        **baseline_run,
        "run_id": run_id,
        "prompt": {
            "candidate": f"G{round_index}",
            "instruction": instruction,
            "instruction_digest": digest_value(instruction),
            "b0_b1_render_parity": False,
        },
        "solver_cases_digest": digest_value(solver),
        "search": {
            "decision": "0019",
            "round": round_index,
            "parent_instruction_digest": parent_instruction_digest,
            "only_instruction_changed": True,
        },
    }
    run.pop("run_identity_digest", None)
    run["run_identity_digest"] = digest_value(run)
    _validate_runtime_binding(run, solver)

    runner = (repository_root / "src/irisx/kaggle_runner_prompt_pilot.py").read_bytes()
    core = (repository_root / "src/irisx/arc_prompt_pilot.py").read_bytes()
    validate_runtime_wheel_sources(runtime_wheel, runner=runner, core=core)
    runtime_manifest = _manifest_for_files(runtime_wheel.parent, [runtime_wheel], "irisx/prompt-pilot-runtime-wheel-manifest")
    dependencies = json.loads(baseline_contents["runtime/dependencies.json"])
    dependencies["runtime_wheel_manifest_digest"] = runtime_manifest["manifest_digest"]
    files = {
        "bindings/run.json": canonical_bytes(run, newline=True),
        "cases/solver-cases.json": canonical_bytes(solver, newline=True),
        "runtime/dependencies.json": canonical_bytes(dependencies, newline=True),
        "runtime/runner.py": runner,
        "runtime/core.py": core,
        "sources/model-manifest.json": baseline_contents["sources/model-manifest.json"],
        "sources/base-wheel-manifest.json": baseline_contents["sources/base-wheel-manifest.json"],
        "sources/runtime-wheel-manifest.json": canonical_bytes(runtime_manifest, newline=True),
    }
    metadata = {
        "trial_id": TRIAL_ID,
        "run_id": run_id,
        "run_identity_digest": run["run_identity_digest"],
        "solver_cases_digest": run["solver_cases_digest"],
        "configuration_digest": run["configuration_digest"],
        "instruction_digest": run["prompt"]["instruction_digest"],
        "runner_digest": digest_bytes(runner),
        "core_digest": digest_bytes(core),
        "model_manifest_digest": json.loads(files["sources/model-manifest.json"])["manifest_digest"],
        "base_wheel_manifest_digest": json.loads(files["sources/base-wheel-manifest.json"])["manifest_digest"],
        "runtime_wheel_manifest_digest": runtime_manifest["manifest_digest"],
        "truth_free": True,
    }
    outbound_digest = write_zip(output, OUTBOUND_KIND, run_id, files, metadata, limits=TRIAL_LIMITS)
    verify_runtime_outbound_package(output)
    return {"run": run, "solver": solver, "outbound_digest": outbound_digest, "metadata": metadata}


def build_final_holdout_outbound_package(
    baseline_trial_root: Path,
    source_training_root: Path,
    baseline_outbound: Path,
    runtime_wheel: Path,
    output: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Build the truth-free B1-only holdout workload authorized by Decision 0019."""

    baseline_run = validate_trial(baseline_trial_root)
    split = _load_canonical(baseline_trial_root / "split.json")
    _, baseline_contents, _ = verify_outbound_package(baseline_outbound)
    holdout_records = [item for item in split["records"] if item["group"] == "locked-holdout"]
    if len(holdout_records) != HOLDOUT_COUNT:
        raise ValidationError("prompt-pilot final holdout split denominator changed")
    cases = []
    for record in holdout_records:
        task_id = record["task_id"]
        official = validate_task(read_json(source_training_root / f"{task_id}.json"), f"training/{task_id}.json", require_test_outputs=True)
        visible = visible_projection(official)
        cases.append({"task_id": task_id, "group": "locked-holdout", "train": visible["train"], "test": visible["test"]})
    solver = {
        "format": "irisx/arc-agi-2-prompt-pilot-solver-cases",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": FINAL_HOLDOUT_RUN_ID,
        "instruction": BASE_INSTRUCTION,
        "cases": cases,
    }
    configuration = _configuration(HOLDOUT_COUNT)
    run = {
        **baseline_run,
        "run_id": FINAL_HOLDOUT_RUN_ID,
        "prompt": {"candidate": "B1", "instruction": BASE_INSTRUCTION, "instruction_digest": digest_value(BASE_INSTRUCTION), "b0_b1_render_parity": True},
        "solver_cases_digest": digest_value(solver),
        "configuration": configuration,
        "configuration_digest": digest_value(configuration),
        "final_holdout": {"decision": "0019", "selected_candidate": "B1", "comparison_candidates": ["B1"], "job_count": HOLDOUT_COUNT},
    }
    run.pop("run_identity_digest", None)
    run["run_identity_digest"] = digest_value(run)
    _validate_runtime_binding(run, solver)
    runner = (repository_root / "src/irisx/kaggle_runner_prompt_pilot.py").read_bytes()
    core = (repository_root / "src/irisx/arc_prompt_pilot.py").read_bytes()
    validate_runtime_wheel_sources(runtime_wheel, runner=runner, core=core)
    runtime_manifest = _manifest_for_files(runtime_wheel.parent, [runtime_wheel], "irisx/prompt-pilot-runtime-wheel-manifest")
    dependencies = json.loads(baseline_contents["runtime/dependencies.json"])
    dependencies["runtime_wheel_manifest_digest"] = runtime_manifest["manifest_digest"]
    files = {
        "bindings/run.json": canonical_bytes(run, newline=True),
        "cases/solver-cases.json": canonical_bytes(solver, newline=True),
        "runtime/dependencies.json": canonical_bytes(dependencies, newline=True),
        "runtime/runner.py": runner,
        "runtime/core.py": core,
        "sources/model-manifest.json": baseline_contents["sources/model-manifest.json"],
        "sources/base-wheel-manifest.json": baseline_contents["sources/base-wheel-manifest.json"],
        "sources/runtime-wheel-manifest.json": canonical_bytes(runtime_manifest, newline=True),
    }
    metadata = {
        "trial_id": TRIAL_ID,
        "run_id": FINAL_HOLDOUT_RUN_ID,
        "run_identity_digest": run["run_identity_digest"],
        "solver_cases_digest": run["solver_cases_digest"],
        "configuration_digest": run["configuration_digest"],
        "instruction_digest": run["prompt"]["instruction_digest"],
        "runner_digest": digest_bytes(runner),
        "core_digest": digest_bytes(core),
        "model_manifest_digest": json.loads(files["sources/model-manifest.json"])["manifest_digest"],
        "base_wheel_manifest_digest": json.loads(files["sources/base-wheel-manifest.json"])["manifest_digest"],
        "runtime_wheel_manifest_digest": runtime_manifest["manifest_digest"],
        "truth_free": True,
    }
    outbound_digest = write_zip(output, OUTBOUND_KIND, FINAL_HOLDOUT_RUN_ID, files, metadata, limits=TRIAL_LIMITS)
    verify_runtime_outbound_package(output)
    return {"run": run, "solver": solver, "outbound_digest": outbound_digest, "metadata": metadata}


def stage_dataset(outbound: Path, runtime_wheel: Path, output: Path) -> dict[str, Any]:
    _ensure_empty(output)
    metadata = {"title": "IRIS-X ARC-AGI-2 Prompt Pilot Baseline Transport", "id": RUNTIME_DATASET_REF, "description": "Private small truth-free baseline-002 repair transport; model and dependencies remain in the bound Trial 002 transport Dataset.", "licenses": [{"name": "other"}]}
    write_json(output / DATASET_METADATA_FILENAME, metadata)
    shutil.copy2(outbound, output / outbound.name)
    shutil.copy2(runtime_wheel, output / runtime_wheel.name)
    return validate_dataset_staging(output, outbound, runtime_wheel)


def validate_dataset_staging(root: Path, outbound: Path, runtime_wheel: Path) -> dict[str, Any]:
    metadata = _load_canonical(root / DATASET_METADATA_FILENAME)
    if metadata.get("id") != RUNTIME_DATASET_REF:
        raise ValidationError("runtime Dataset staging identity is stale")
    staged_outbound, staged_wheel = root / outbound.name, root / runtime_wheel.name
    if digest_path(staged_outbound) != digest_path(outbound) or digest_path(staged_wheel) != digest_path(runtime_wheel):
        raise ValidationError("runtime Dataset staging bytes are stale")
    if any(path.name in {"evaluator-truth.json", "arc-agi_training_solutions.json", "arc-agi_evaluation_solutions.json"} for path in root.rglob("*")):
        raise ValidationError("runtime Dataset staging contains evaluator truth")
    return {"dataset_ref": RUNTIME_DATASET_REF, "dataset_version": RUNTIME_DATASET_VERSION, "outbound_digest": digest_path(staged_outbound), "runtime_wheel_digest": digest_path(staged_wheel), "truth_free": True}


def stage_search_dataset(outbound: Path, runtime_wheel: Path, output: Path, *, expected_version: int) -> dict[str, Any]:
    if expected_version < 3:
        raise ValidationError("prompt-pilot search Dataset must follow retained baseline version 2")
    _ensure_empty(output)
    metadata = {
        "title": "IRIS-X ARC-AGI-2 Prompt Pilot Search Transport",
        "id": RUNTIME_DATASET_REF,
        "description": "Private small truth-free Decision 0019 candidate transport; model and offline inference dependencies remain in the bound Trial 002 Dataset.",
        "licenses": [{"name": "other"}],
    }
    write_json(output / DATASET_METADATA_FILENAME, metadata)
    shutil.copy2(outbound, output / outbound.name)
    shutil.copy2(runtime_wheel, output / runtime_wheel.name)
    staged_outbound, staged_wheel = output / outbound.name, output / runtime_wheel.name
    verify_runtime_outbound_package(staged_outbound)
    if digest_path(staged_outbound) != digest_path(outbound) or digest_path(staged_wheel) != digest_path(runtime_wheel):
        raise ValidationError("prompt-pilot search Dataset staging bytes are stale")
    if any(path.name in {"evaluator-truth.json", "arc-agi_training_solutions.json", "arc-agi_evaluation_solutions.json"} for path in output.rglob("*")):
        raise ValidationError("prompt-pilot search Dataset staging contains evaluator truth")
    return {"dataset_ref": RUNTIME_DATASET_REF, "expected_dataset_version": expected_version, "outbound_digest": digest_path(staged_outbound), "runtime_wheel_digest": digest_path(staged_wheel), "truth_free": True}


def validate_kernel_staging(root: Path, outbound_digest: str, runtime_wheel_digest: str) -> dict[str, Any]:
    metadata = _load_canonical(root / "kernel-metadata.json")
    expected = {"id": KAGGLE_KERNEL_REF, "is_private": True, "enable_gpu": True, "enable_internet": False, "machine_shape": KAGGLE_MACHINE_SHAPE, "dataset_sources": [BASE_DATASET_REF, RUNTIME_DATASET_REF], "competition_sources": [COMPETITION_SLUG]}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValidationError(f"Kaggle kernel metadata is stale: {key}")
    notebook = json.loads((root / metadata["code_file"]).read_bytes())
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"] if cell.get("cell_type") == "code")
    required = (
        RUN_ID,
        COMPETITION_CHALLENGE_FILENAME,
        outbound_digest.removeprefix("sha256:"),
        runtime_wheel_digest.removeprefix("sha256:"),
        "PYTHONUNBUFFERED",
        "kaggle_runner_prompt_pilot",
        "/kaggle/input/datasets/danielwuu/irisx-arc-agi-2-trial-002-smoke-001",
        "/kaggle/input/datasets/danielwuu/irisx-arc-agi-2-prompt-pilot-baseline-001",
        "/kaggle/input/competitions/arc-prize-2026-arc-agi-2",
        "mount_paths_resolved",
    )
    if any(item not in source for item in required) or "__IRISX_" in source or ".rglob(" in source:
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


def stage_search_kernel(
    template_root: Path,
    output: Path,
    *,
    run_id: str,
    outbound_digest: str,
    runtime_wheel_digest: str,
) -> dict[str, Any]:
    _ensure_empty(output)
    if not (run_id.startswith("prompt-pilot-search-g") or run_id == FINAL_HOLDOUT_RUN_ID):
        raise ValidationError("prompt-pilot search kernel run identity is invalid")
    metadata = read_json(template_root / "kernel-metadata.json")
    metadata.update({"id": KAGGLE_SEARCH_KERNEL_REF, "title": KAGGLE_SEARCH_KERNEL_TITLE})
    notebook = json.loads((template_root / metadata["code_file"]).read_bytes())
    replacements = {
        RUN_ID: run_id,
        "__IRISX_OUTBOUND_SHA256__": outbound_digest.removeprefix("sha256:"),
        "__IRISX_RUNTIME_WHEEL_SHA256__": runtime_wheel_digest.removeprefix("sha256:"),
        "Private, Internet-disabled, competition-mounted L4 x4 replacement authorized by Decision 0017.": "Private, Internet-disabled, competition-mounted L4 x4 candidate authorized by Decision 0019.",
    }
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
    if counts["__IRISX_OUTBOUND_SHA256__"] != 1 or counts["__IRISX_RUNTIME_WHEEL_SHA256__"] != 1 or counts[RUN_ID] < 4:
        raise ValidationError("prompt-pilot search notebook bindings are missing")
    (output / metadata["code_file"]).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_json(output / "kernel-metadata.json", metadata)
    returned = _load_canonical(output / "kernel-metadata.json")
    expected = {
        "id": KAGGLE_SEARCH_KERNEL_REF,
        "title": KAGGLE_SEARCH_KERNEL_TITLE,
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "machine_shape": KAGGLE_MACHINE_SHAPE,
        "dataset_sources": [BASE_DATASET_REF, RUNTIME_DATASET_REF],
        "competition_sources": [COMPETITION_SLUG],
    }
    if any(returned.get(key) != value for key, value in expected.items()):
        raise ValidationError("prompt-pilot search kernel metadata is stale")
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"] if cell.get("cell_type") == "code")
    required = (run_id, outbound_digest.removeprefix("sha256:"), runtime_wheel_digest.removeprefix("sha256:"), "kaggle_runner_prompt_pilot", "mount_paths_resolved")
    if any(item not in source for item in required) or RUN_ID in source or "__IRISX_" in source or ".rglob(" in source:
        raise ValidationError("prompt-pilot search notebook contains unresolved bindings")
    return returned


def new_checkpoint(run: Mapping[str, Any], solver: Mapping[str, Any]) -> dict[str, Any]:
    jobs = [f"{case['task_id']}:0" for case in solver["cases"]]
    return {"format": "irisx/arc-agi-2-prompt-pilot-checkpoint", "format_version": "1.0", "trial_id": TRIAL_ID, "run_id": run.get("run_id", RUN_ID), "run_identity_digest": run["run_identity_digest"], "expected_jobs": jobs, "model_ready": {}, "generation_invocations": {}, "completed": {}, "sessions": [], "complete": False}


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
    if checkpoint.get("trial_id") != TRIAL_ID or checkpoint.get("run_id") != run.get("run_id", RUN_ID) or checkpoint.get("run_identity_digest") != run["run_identity_digest"] or checkpoint.get("expected_jobs") != expected:
        raise ValidationError("prompt-pilot checkpoint identity or denominator is invalid")
    quota = run.get("configuration", {}).get("generation", {}).get("invocation_quota", len(expected))
    if quota != len(expected) or len(checkpoint.get("generation_invocations", {})) > quota or not set(checkpoint.get("completed", {})).issubset(expected):
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
    run_id = run.get("run_id", RUN_ID)
    records = [checkpoint["completed"][key] for key in checkpoint["expected_jobs"] if key in checkpoint["completed"]]
    files = {"bindings/run.json": canonical_bytes(run, newline=True), "checkpoint/checkpoint.json": canonical_bytes(checkpoint, newline=True), "predictions/predictions.json": canonical_bytes({"format": "irisx/arc-agi-2-prompt-pilot-predictions", "format_version": "1.0", "trial_id": TRIAL_ID, "run_id": run_id, "records": records}, newline=True), "observations/execution.json": canonical_bytes(observations, newline=True), "logs/progress.jsonl": progress}
    metadata = {"trial_id": TRIAL_ID, "run_id": run_id, "run_identity_digest": run["run_identity_digest"], "expected_job_count": len(checkpoint["expected_jobs"]), "terminal_job_count": len(records), "truth_free": True}
    return write_zip(output, RESULT_KIND, run_id, files, metadata, limits=RESULT_LIMITS)


def verify_result_package(path: Path, outbound: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    manifest, contents, digest = verify_runtime_result_package(path, outbound)
    if manifest.get("package_id") != RUN_ID:
        raise ValidationError("prompt-pilot baseline result identity is invalid")
    return manifest, contents, digest


def verify_runtime_result_package(path: Path, outbound: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    _, outbound_contents, _ = verify_runtime_outbound_package(outbound)
    run, solver = json.loads(outbound_contents["bindings/run.json"]), json.loads(outbound_contents["cases/solver-cases.json"])
    manifest, contents, digest = verify_zip(path, limits=RESULT_LIMITS, package_kind=RESULT_KIND)
    if set(contents) != RESULT_PATHS or manifest.get("package_id") != run["run_id"]:
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


def score_prediction_records(
    records: Iterable[Mapping[str, Any]],
    truth_cases: Iterable[Mapping[str, Any]],
    *,
    groups: tuple[str, ...] = ("optimization-train", "selection-dev"),
) -> dict[str, Any]:
    """Score selected-output pass@1 while preserving the full denominator.

    Parser-invalid and other terminal failures are incorrect, not omitted.  The
    returned per-case details are local evaluator material; callers must not
    place them in an outbound package or expose selection-dev details to the
    instruction proposer.
    """

    allowed = set(groups)
    truth_by_job: dict[str, Mapping[str, Any]] = {}
    for truth in truth_cases:
        if truth.get("group") not in allowed:
            continue
        task_id, test_index = truth.get("task_id"), truth.get("test_index")
        if not isinstance(task_id, str) or test_index != 0:
            raise ValidationError("prompt-pilot evaluator truth identity is invalid")
        job_key = f"{task_id}:{test_index}"
        if job_key in truth_by_job:
            raise ValidationError("prompt-pilot evaluator truth contains a duplicate job")
        validate_grid(truth.get("output"), f"evaluator truth {job_key}")
        truth_by_job[job_key] = truth

    record_by_job: dict[str, Mapping[str, Any]] = {}
    for record in records:
        job_key = record.get("job_key")
        if not isinstance(job_key, str) or job_key in record_by_job:
            raise ValidationError("prompt-pilot prediction records contain an invalid or duplicate job")
        record_by_job[job_key] = record
    if set(record_by_job) != set(truth_by_job):
        missing = sorted(set(truth_by_job) - set(record_by_job))
        extra = sorted(set(record_by_job) - set(truth_by_job))
        raise ValidationError(f"prompt-pilot score denominator differs: missing={missing[:3]} extra={extra[:3]}")

    details: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    for group in groups:
        group_truth = [truth for truth in truth_by_job.values() if truth["group"] == group]
        status_counts: Counter[str] = Counter()
        correct = 0
        for truth in sorted(group_truth, key=lambda item: item["task_id"]):
            job_key = f"{truth['task_id']}:0"
            record = record_by_job[job_key]
            if record.get("task_id") != truth["task_id"] or record.get("test_index") != 0 or record.get("group") != group:
                raise ValidationError(f"prompt-pilot prediction identity differs from truth: {job_key}")
            status = record.get("status")
            if status not in TERMINAL_STATUSES:
                raise ValidationError(f"prompt-pilot prediction status is invalid: {job_key}")
            status_counts[str(status)] += 1
            attempts = record.get("attempts")
            if not isinstance(attempts, list):
                raise ValidationError(f"prompt-pilot prediction attempts are invalid: {job_key}")
            predicted = None
            is_correct = False
            if status == "valid":
                if len(attempts) != 1:
                    raise ValidationError(f"valid prompt-pilot prediction must contain one attempt: {job_key}")
                predicted = validate_grid(attempts[0], f"prediction {job_key}")
                is_correct = predicted == truth["output"]
            elif attempts:
                raise ValidationError(f"non-valid prompt-pilot prediction contains an attempt: {job_key}")
            correct += int(is_correct)
            details.append(
                {
                    "job_key": job_key,
                    "task_id": truth["task_id"],
                    "group": group,
                    "status": status,
                    "correct": is_correct,
                    "predicted_output": predicted,
                    "expected_output": truth["output"],
                }
            )
        denominator = len(group_truth)
        summaries[group] = {
            "correct": correct,
            "denominator": denominator,
            "accuracy": correct / denominator if denominator else None,
            "terminal_status_counts": dict(sorted(status_counts.items())),
        }

    total_correct = sum(summary["correct"] for summary in summaries.values())
    total_denominator = sum(summary["denominator"] for summary in summaries.values())
    return {
        "groups": summaries,
        "overall": {
            "correct": total_correct,
            "denominator": total_denominator,
            "accuracy": total_correct / total_denominator if total_denominator else None,
        },
        "records": details,
    }


def score_result_package(trial_root: Path, result: Path, outbound: Path) -> dict[str, Any]:
    """Verify and deterministically score a baseline result against local truth."""

    trial_run = validate_trial(trial_root)
    result_manifest, contents, result_digest = verify_result_package(result, outbound)
    returned_run = json.loads(contents["bindings/run.json"])
    if returned_run != trial_run:
        raise ValidationError("prompt-pilot scored result differs from the local trial binding")
    truth_path = trial_root / "evaluator-truth.json"
    truth = _load_canonical(truth_path)
    predictions = json.loads(contents["predictions/predictions.json"])
    scored = score_prediction_records(predictions["records"], truth["cases"])
    return {
        "format": "irisx/arc-agi-2-prompt-pilot-score",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "metric": "selected-output-exact-match-pass@1",
        "invalid_policy": "incorrect-and-retained-in-denominator",
        "bindings": {
            "run_identity_digest": trial_run["run_identity_digest"],
            "split_digest": trial_run["split_digest"],
            "truth_digest": digest_path(truth_path),
            "outbound_digest": digest_path(outbound),
            "result_digest": result_digest,
            "result_manifest_digest": digest_value(result_manifest),
        },
        "groups": scored["groups"],
        "overall": scored["overall"],
        "records": scored["records"],
        "holdout": {"opened": False, "scored": False, "record_count": 0},
    }


def score_search_result_package(baseline_trial_root: Path, result: Path, outbound: Path) -> dict[str, Any]:
    """Score a verified search candidate against the frozen local train/dev truth."""

    baseline_run = validate_trial(baseline_trial_root)
    result_manifest, contents, result_digest = verify_runtime_result_package(result, outbound)
    candidate_run = json.loads(contents["bindings/run.json"])
    if candidate_run["run_id"] == RUN_ID or candidate_run.get("split_digest") != baseline_run["split_digest"]:
        raise ValidationError("prompt-pilot search result is not a distinct candidate on the frozen split")
    truth_path = baseline_trial_root / "evaluator-truth.json"
    truth = _load_canonical(truth_path)
    predictions = json.loads(contents["predictions/predictions.json"])
    scored = score_prediction_records(predictions["records"], truth["cases"])
    return {
        "format": "irisx/arc-agi-2-prompt-pilot-score",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": candidate_run["run_id"],
        "metric": "selected-output-exact-match-pass@1",
        "invalid_policy": "incorrect-and-retained-in-denominator",
        "bindings": {
            "run_identity_digest": candidate_run["run_identity_digest"],
            "split_digest": candidate_run["split_digest"],
            "instruction_digest": candidate_run["prompt"]["instruction_digest"],
            "truth_digest": digest_path(truth_path),
            "outbound_digest": digest_path(outbound),
            "result_digest": result_digest,
            "result_manifest_digest": digest_value(result_manifest),
        },
        "groups": scored["groups"],
        "overall": scored["overall"],
        "records": scored["records"],
        "holdout": {"opened": False, "scored": False, "record_count": 0},
    }


def score_final_holdout_result_package(baseline_trial_root: Path, result: Path, outbound: Path) -> dict[str, Any]:
    """Open and score only the frozen B1 holdout after search selection."""

    baseline_run = validate_trial(baseline_trial_root)
    result_manifest, contents, result_digest = verify_runtime_result_package(result, outbound)
    run = json.loads(contents["bindings/run.json"])
    if run.get("run_id") != FINAL_HOLDOUT_RUN_ID or run.get("split_digest") != baseline_run["split_digest"]:
        raise ValidationError("prompt-pilot final holdout differs from the frozen split")
    truth_path = baseline_trial_root / "evaluator-truth.json"
    truth = _load_canonical(truth_path)
    predictions = json.loads(contents["predictions/predictions.json"])
    scored = score_prediction_records(predictions["records"], truth["cases"], groups=("locked-holdout",))
    return {
        "format": "irisx/arc-agi-2-prompt-pilot-final-holdout-score",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": FINAL_HOLDOUT_RUN_ID,
        "selected_candidate": "B1",
        "metric": "selected-output-exact-match-pass@1",
        "invalid_policy": "incorrect-and-retained-in-denominator",
        "bindings": {
            "run_identity_digest": run["run_identity_digest"],
            "split_digest": run["split_digest"],
            "instruction_digest": run["prompt"]["instruction_digest"],
            "truth_digest": digest_path(truth_path),
            "outbound_digest": digest_path(outbound),
            "result_digest": result_digest,
            "result_manifest_digest": digest_value(result_manifest),
        },
        "groups": scored["groups"],
        "overall": scored["overall"],
        "records": scored["records"],
        "holdout": {"opened": True, "scored": True, "record_count": HOLDOUT_COUNT},
    }


def _load_canonical_progress(path: Path) -> tuple[list[dict[str, Any]], bytes]:
    raw = path.read_bytes()
    if not raw or not raw.endswith(b"\n"):
        raise ValidationError("recovery progress must be non-empty newline-terminated JSONL")
    events: list[dict[str, Any]] = []
    for index, line in enumerate(raw.splitlines(keepends=True), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"recovery progress line {index} is not JSON") from exc
        if not isinstance(event, dict) or line != canonical_bytes(event, newline=True):
            raise ValidationError(f"recovery progress line {index} is not a canonical JSON object")
        events.append(event)
    return events, raw


def recover_result_package(outbound: Path, checkpoint_path: Path, progress_path: Path, output: Path) -> dict[str, Any]:
    """Recover the completed baseline-002 result without another generation.

    This is deliberately strict and specific to the Decision 0018 recovery.
    It accepts the runtime's complete canonical checkpoint and progress stream,
    reconstructs the observations that failed only on integer rank keys, and
    produces the ordinary truth-free result package under the unchanged run
    identity.
    """

    _, contents, outbound_digest = verify_outbound_package(outbound)
    run = json.loads(contents["bindings/run.json"])
    solver = json.loads(contents["cases/solver-cases.json"])
    checkpoint = _load_canonical(checkpoint_path)
    validate_checkpoint(checkpoint, run, solver)
    expected = set(checkpoint["expected_jobs"])
    if not checkpoint.get("complete"):
        raise ValidationError("recovery checkpoint is not complete")
    if len(expected) != BASELINE_JOB_COUNT or set(checkpoint.get("generation_invocations", {})) != expected or set(checkpoint.get("completed", {})) != expected:
        raise ValidationError("recovery checkpoint does not contain the exact 384-job denominator")
    if any(item.get("status") != "completed" for item in checkpoint["generation_invocations"].values()):
        raise ValidationError("recovery checkpoint contains a non-completed invocation")
    statuses = Counter(item.get("status") for item in checkpoint["completed"].values())
    if statuses != Counter({"valid": 380, "invalid": 4}):
        raise ValidationError(f"recovery terminal counts differ from retained runtime evidence: {dict(statuses)}")
    if set(checkpoint.get("model_ready", {})) != {str(rank) for rank in range(WORKER_COUNT)}:
        raise ValidationError("recovery checkpoint lacks four string-keyed model-ready records")
    if len(checkpoint.get("sessions", [])) != 1:
        raise ValidationError("recovery checkpoint must contain exactly one runtime session")
    session = checkpoint["sessions"][0]
    if session.get("ended_utc") is None or not isinstance(session.get("wall_seconds"), (int, float)):
        raise ValidationError("recovery runtime session is not terminal")

    events, progress = _load_canonical_progress(progress_path)
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        kind = event.get("event")
        if not isinstance(kind, str):
            raise ValidationError("recovery progress event lacks an event name")
        by_kind[kind].append(event)
    required_counts = {
        "runtime_preflight_started": 1,
        "runtime_hardware_observed": 1,
        "competition_mount_validated": 1,
        "worker_process_started": WORKER_COUNT,
        "model_load_started": WORKER_COUNT,
        "model_ready": WORKER_COUNT,
        "all_workers_ready": 1,
        "generation_invocation_dispatched": BASELINE_JOB_COUNT,
        "job_started": BASELINE_JOB_COUNT,
        "job_terminal": BASELINE_JOB_COUNT,
        "session_complete": 1,
    }
    allowed = set(required_counts) | {"heartbeat"}
    if set(by_kind) - allowed:
        raise ValidationError(f"recovery progress contains unexpected events: {sorted(set(by_kind) - allowed)}")
    for kind, count in required_counts.items():
        if len(by_kind.get(kind, [])) != count:
            raise ValidationError(f"recovery progress {kind} count differs: {len(by_kind.get(kind, []))} != {count}")

    hardware_event = by_kind["runtime_hardware_observed"][0]
    if hardware_event.get("hardware") != session.get("hardware"):
        raise ValidationError("recovery checkpoint and progress hardware differ")
    ready_events: dict[int, dict[str, Any]] = {}
    for event in by_kind["model_ready"]:
        rank = event.get("rank")
        if not isinstance(rank, int) or rank in ready_events:
            raise ValidationError("recovery progress has duplicate or invalid model-ready rank")
        ready_events[rank] = {key: value for key, value in event.items() if key != "elapsed_seconds"}
    for rank in range(WORKER_COUNT):
        if ready_events.get(rank) != checkpoint["model_ready"][str(rank)]:
            raise ValidationError(f"recovery model-ready evidence differs for rank {rank}")

    dispatches = by_kind["generation_invocation_dispatched"]
    if {item.get("job_key") for item in dispatches} != expected or {item.get("invocation_ordinal") for item in dispatches} != set(range(1, BASELINE_JOB_COUNT + 1)):
        raise ValidationError("recovery dispatch evidence is incomplete or duplicated")
    for event in dispatches:
        job = event["job_key"]
        invocation = checkpoint["generation_invocations"][job]
        rank = invocation["worker_rank"]
        if event.get("rank") != rank or event.get("invocation_ordinal") != invocation["ordinal"] or event.get("gpu_uuid") != checkpoint["model_ready"][str(rank)]["gpu_uuid"]:
            raise ValidationError(f"recovery dispatch differs from checkpoint: {job}")
    terminals = by_kind["job_terminal"]
    if {item.get("job_key") for item in terminals} != expected:
        raise ValidationError("recovery terminal progress is incomplete or duplicated")
    for event in terminals:
        record = checkpoint["completed"][event["job_key"]]
        if event.get("status") != record["status"] or event.get("rank") != record["worker_rank"] or event.get("invocation_ordinal") != record["invocation_ordinal"] or event.get("gpu_uuid") != record["gpu_uuid"]:
            raise ValidationError(f"recovery terminal event differs from checkpoint: {event['job_key']}")
    complete_event = by_kind["session_complete"][0]
    if complete_event.get("completed_jobs") != BASELINE_JOB_COUNT or complete_event.get("terminal_status_counts") != dict(sorted(statuses.items())):
        raise ValidationError("recovery session-complete event differs from checkpoint")

    competition_event = by_kind["competition_mount_validated"][0]
    competition = {
        key: competition_event[key]
        for key in ("competition_slug", "challenge_digest", "available_task_count", "selected_job_count", "selected_test_index", "solutions_opened")
    }
    dependencies = json.loads(contents["runtime/dependencies.json"])
    hardware = session["hardware"]
    worker_counts = Counter(str(record["worker_rank"]) for record in checkpoint["completed"].values() if record["worker_rank"] >= 0)
    active_seconds: Counter[str] = Counter()
    for record in checkpoint["completed"].values():
        value = record.get("timing", {}).get("generation_seconds")
        if isinstance(value, (int, float)) and record["worker_rank"] >= 0:
            active_seconds[str(record["worker_rank"])] += value
    observations = {
        "format": "irisx/arc-agi-2-prompt-pilot-execution",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "session_wall_seconds": session["wall_seconds"],
        "hardware": hardware["gpus"],
        "nvidia_smi_rows": hardware["nvidia_smi_rows"],
        "software": {"python": hardware["python"], "torch": hardware["torch"], "transformers": dependencies["transformers"], "cuda": hardware["cuda"], "cudnn": hardware["cudnn"]},
        "competition_input": competition,
        "internet_enabled": False,
        "external_paid_cost_usd": 0,
        "model_ready": dict(sorted(checkpoint["model_ready"].items())),
        "model_load_count_by_worker": {str(rank): 1 for rank in range(WORKER_COUNT)},
        "jobs_by_worker": dict(sorted(worker_counts.items())),
        "job_active_seconds_by_worker": dict(sorted(active_seconds.items())),
        "terminal_status_counts": dict(sorted(statuses.items())),
        "generation_invocation_count": len(checkpoint["generation_invocations"]),
        "gpu_utilization_state": "not_sampled",
        "result_assembly": {
            "mode": "local-checkpoint-recovery",
            "decision": "0018",
            "source_checkpoint_digest": digest_path(checkpoint_path),
            "source_progress_digest": digest_path(progress_path),
            "source_outbound_digest": outbound_digest,
            "applied_fix": "serialize observations.model_ready worker-rank keys as strings",
            "new_generation_invocations": 0,
        },
    }
    result_digest = build_result_package(output, run, solver, checkpoint, observations, progress)
    result_manifest, _, verified_digest = verify_result_package(output, outbound)
    if verified_digest != result_digest:
        raise ValidationError("recovered result digest changed during verification")
    return {
        "format": "irisx/arc-agi-2-prompt-pilot-recovery",
        "format_version": "1.0",
        "trial_id": TRIAL_ID,
        "run_id": RUN_ID,
        "run_identity_digest": run["run_identity_digest"],
        "outbound_digest": outbound_digest,
        "checkpoint_digest": digest_path(checkpoint_path),
        "progress_digest": digest_path(progress_path),
        "result_digest": result_digest,
        "result_manifest_digest": digest_value(result_manifest),
        "generation_invocation_count": len(checkpoint["generation_invocations"]),
        "terminal_status_counts": dict(sorted(statuses.items())),
        "new_generation_invocations": 0,
        "truth_free": True,
        "verified": True,
        "scored": False,
    }


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

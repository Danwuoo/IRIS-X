"""Decision-0004 ARC-AGI-2 Trial 001 materialization and local evaluation."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any

from .artifacts import artifact_ref, load_artifact, make_artifact, validate_artifact, write_artifact
from .canonical import digest_bytes, digest_value, read_json
from .contracts import (
    CandidateConfiguration,
    DomainSpecification,
    EngineeringTrial,
    EvaluationResult,
    RequirementSet,
    WorkloadDefinition,
    assert_binding,
    load_contract,
)
from .engine import requirement_verdicts, satisfies_hard_requirements
from .errors import ValidationError


ARC_REPOSITORY = "https://github.com/arcprize/ARC-AGI-2.git"
ARC_REPOSITORY_ID = "arcprize/ARC-AGI-2"
ARC_COMMIT = "f3283f727488ad98fe575ea6a5ac981e4a188e49"
MODEL_REPOSITORY = "Qwen/Qwen3.8-27B"
MODEL_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
MODEL_LICENSE = "Apache-2.0"
PUBLIC_TRAINING_COUNT = 1000
PUBLIC_EVALUATION_COUNT = 120
P2_IMPROVEMENT_THRESHOLD = 0.05


@dataclass(frozen=True)
class SourceProfile:
    training_count: int = PUBLIC_TRAINING_COUNT
    evaluation_count: int = PUBLIC_EVALUATION_COUNT
    require_git_identity: bool = True


def _ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValidationError(f"output directory must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise ValidationError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _normalized_remote(value: str) -> str:
    value = value.removesuffix("/").removesuffix(".git")
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.removeprefix("git@github.com:")
    return value.lower()


def validate_grid(value: Any, path: str) -> list[list[int]]:
    if not isinstance(value, list) or not value or len(value) > 30:
        raise ValidationError(f"{path}: grid height must be between 1 and 30")
    width: int | None = None
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or not row or len(row) > 30:
            raise ValidationError(f"{path}[{row_index}]: grid width must be between 1 and 30")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValidationError(f"{path}: grid must be rectangular")
        for column_index, cell in enumerate(row):
            if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell <= 9:
                raise ValidationError(f"{path}[{row_index}][{column_index}]: cell must be an integer from 0 through 9")
    return value


def validate_task(value: Any, path: str, *, require_test_outputs: bool) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"train", "test"}:
        raise ValidationError(f"{path}: ARC task must contain exactly train and test")
    if not isinstance(value["train"], list) or not value["train"]:
        raise ValidationError(f"{path}.train: must be a non-empty array")
    if not isinstance(value["test"], list) or not value["test"]:
        raise ValidationError(f"{path}.test: must be a non-empty array")
    for split in ("train", "test"):
        for index, pair in enumerate(value[split]):
            pair_path = f"{path}.{split}[{index}]"
            required = {"input", "output"} if split == "train" or require_test_outputs else {"input"}
            if not isinstance(pair, dict) or set(pair) != required:
                raise ValidationError(f"{pair_path}: pair fields must be exactly {sorted(required)}")
            validate_grid(pair["input"], f"{pair_path}.input")
            if "output" in pair:
                validate_grid(pair["output"], f"{pair_path}.output")
    return value


def _source_files(upstream: Path) -> list[Path]:
    return sorted(
        (path for path in upstream.rglob("*") if path.is_file() and ".git" not in path.relative_to(upstream).parts),
        key=lambda path: path.relative_to(upstream).as_posix(),
    )


def _validate_split_index(upstream: Path, split: str, paths: list[Path]) -> None:
    index = upstream / f"data/{split}.txt"
    if not index.is_file():
        raise ValidationError(f"ARC source is missing data/{split}.txt")
    try:
        identifiers = [line.strip() for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
    except UnicodeDecodeError as exc:
        raise ValidationError(f"ARC data/{split}.txt is not UTF-8") from exc
    expected = [path.stem for path in paths]
    if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(expected):
        raise ValidationError(f"ARC data/{split}.txt does not exactly enumerate the {split} split")


def create_source_provenance(
    upstream: Path,
    output: Path,
    *,
    profile: SourceProfile = SourceProfile(),
) -> dict[str, Any]:
    """Record exact preserved bytes after verifying the approved source identity."""

    if not upstream.is_dir():
        raise ValidationError(f"ARC upstream directory does not exist: {upstream}")
    if profile.require_git_identity:
        remote = _git(upstream, "remote", "get-url", "origin")
        head = _git(upstream, "rev-parse", "HEAD")
        if _normalized_remote(remote) != _normalized_remote(ARC_REPOSITORY):
            raise ValidationError("ARC source remote is not the approved official upstream")
        if head != ARC_COMMIT:
            raise ValidationError("ARC source checkout is not at the pinned commit")
        if _git(upstream, "status", "--porcelain", "--untracked-files=no"):
            raise ValidationError("ARC source checkout contains modified tracked files")
    training = sorted((upstream / "data/training").glob("*.json"))
    evaluation = sorted((upstream / "data/evaluation").glob("*.json"))
    if len(training) != profile.training_count:
        raise ValidationError(f"ARC public training split must contain exactly {profile.training_count} tasks")
    if len(evaluation) != profile.evaluation_count:
        raise ValidationError(f"ARC public evaluation split must contain exactly {profile.evaluation_count} tasks")
    _validate_split_index(upstream, "training", training)
    _validate_split_index(upstream, "evaluation", evaluation)
    for split, paths in (("training", training), ("evaluation", evaluation)):
        seen: set[str] = set()
        for path in paths:
            task_id = path.stem
            if task_id in seen:
                raise ValidationError(f"duplicate ARC {split} task identifier: {task_id}")
            seen.add(task_id)
            validate_task(read_json(path), f"{split}/{path.name}", require_test_outputs=True)
    files = [
        {
            "path": path.relative_to(upstream).as_posix(),
            "byte_size": path.stat().st_size,
            "content_digest": digest_bytes(path.read_bytes()),
        }
        for path in _source_files(upstream)
    ]
    provenance = make_artifact(
        "irisx/arc-source-provenance",
        "arc-agi-2-official-source",
        "1.0.0",
        {
            "repository": ARC_REPOSITORY,
            "commit": ARC_COMMIT,
            "preserved_bytes": True,
            "training_task_count": len(training),
            "evaluation_task_count": len(evaluation),
            "files": files,
        },
    )
    write_artifact(output, provenance)
    return provenance


def materialize_source(output: Path) -> dict[str, Any]:
    """Deliberately acquire only the fixed official ARC source and commit."""

    _ensure_empty(output)
    upstream = output / "upstream"
    completed = subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", ARC_REPOSITORY, str(upstream)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise ValidationError(f"official ARC source clone failed: {completed.stderr.strip()}")
    _git(upstream, "checkout", "--detach", ARC_COMMIT)
    return create_source_provenance(upstream, output / "provenance.json")


def validate_source(root: Path, *, profile: SourceProfile = SourceProfile()) -> dict[str, Any]:
    upstream = root / "upstream"
    provenance = load_artifact(root / "provenance.json", kind="irisx/arc-source-provenance")
    payload = provenance["payload"]
    expected_identity = {
        "repository": ARC_REPOSITORY,
        "commit": ARC_COMMIT,
        "preserved_bytes": True,
        "training_task_count": profile.training_count,
        "evaluation_task_count": profile.evaluation_count,
    }
    for field, expected in expected_identity.items():
        if payload.get(field) != expected:
            raise ValidationError(f"source provenance {field} is stale or incorrect")
    if profile.require_git_identity:
        if _normalized_remote(_git(upstream, "remote", "get-url", "origin")) != _normalized_remote(ARC_REPOSITORY):
            raise ValidationError("ARC source remote is not the approved official upstream")
        if _git(upstream, "rev-parse", "HEAD") != ARC_COMMIT:
            raise ValidationError("ARC source checkout is not at the pinned commit")
    entries = payload.get("files")
    if not isinstance(entries, list):
        raise ValidationError("source provenance files must be an array")
    declared: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "byte_size", "content_digest"}:
            raise ValidationError("source provenance file entry is malformed")
        logical = entry["path"]
        if not isinstance(logical, str) or "\\" in logical or logical.startswith("/") or ".." in logical.split("/"):
            raise ValidationError("source provenance contains an unsafe path")
        if logical in declared:
            raise ValidationError(f"duplicate source provenance path: {logical}")
        declared[logical] = entry
    actual = {path.relative_to(upstream).as_posix(): path for path in _source_files(upstream)}
    if set(actual) != set(declared):
        raise ValidationError("source provenance does not exactly cover preserved upstream files")
    for logical, path in actual.items():
        entry = declared[logical]
        data = path.read_bytes()
        if entry["byte_size"] != len(data) or entry["content_digest"] != digest_bytes(data):
            raise ValidationError(f"source provenance digest mismatch: {logical}")
    training = sorted((upstream / "data/training").glob("*.json"))
    evaluation = sorted((upstream / "data/evaluation").glob("*.json"))
    if len(training) != profile.training_count or len(evaluation) != profile.evaluation_count:
        raise ValidationError("source split task counts no longer match provenance")
    _validate_split_index(upstream, "training", training)
    _validate_split_index(upstream, "evaluation", evaluation)
    for split, paths in (("training", training), ("evaluation", evaluation)):
        for path in paths:
            validate_task(read_json(path), f"{split}/{path.name}", require_test_outputs=True)
    return provenance


def _source_ref(source_id: str, locator: str, value: Any) -> dict[str, str]:
    return {
        "source_id": source_id,
        "media_type": "application/json",
        "content_digest": digest_value(value),
        "locator": locator,
    }


def _write_contracts(output: Path, values: list[tuple[str, Any]]) -> None:
    for name, value in values:
        value.write(output / name)


def prepare_trial(
    source_root: Path,
    output: Path,
    *,
    profile: SourceProfile = SourceProfile(),
) -> EngineeringTrial:
    """Create isolated views and the existing P1 contract graph from official bytes."""

    provenance = validate_source(source_root, profile=profile)
    _ensure_empty(output)
    upstream = source_root / "upstream"
    evaluation_paths = sorted((upstream / "data/evaluation").glob("*.json"))
    training_paths = sorted((upstream / "data/training").glob("*.json"))
    solver_cases: list[dict[str, Any]] = []
    truth_cases: list[dict[str, Any]] = []
    workload_cases: list[dict[str, Any]] = []
    for path in evaluation_paths:
        case_id = path.stem
        task = validate_task(read_json(path), case_id, require_test_outputs=True)
        solver_case = {
            "case_id": case_id,
            "train": copy.deepcopy(task["train"]),
            "test": [{"input": copy.deepcopy(pair["input"])} for pair in task["test"]],
        }
        expected = [copy.deepcopy(pair["output"]) for pair in task["test"]]
        truth_case = {"case_id": case_id, "expected": expected}
        solver_cases.append(solver_case)
        truth_cases.append(truth_case)
        workload_cases.append(
            {
                "case_id": case_id,
                "segment": "public_eval",
                "critical": False,
                "input_ref": _source_ref(f"{case_id}-input", f"solver-cases.json/{case_id}/input", solver_case),
                "expected_ref": _source_ref(f"{case_id}-expected", f"evaluator-truth.json/{case_id}/expected", expected),
            }
        )
    solver_artifact = make_artifact(
        "irisx/arc-solver-cases", "arc-agi-2-public-eval-solver-cases", "1.0.0", {"cases": solver_cases}
    )
    truth_artifact = make_artifact(
        "irisx/arc-evaluator-truth", "arc-agi-2-public-eval-truth", "1.0.0", {"cases": truth_cases}
    )
    evaluator = make_artifact(
        "irisx/evaluator-definition",
        "arc-agi-2-pass-at-2",
        "1.0.0",
        {
            "method": "arc-agi-2-exact-pass-at-2",
            "attempts_per_test_input": 2,
            "task_pass_requires_all_test_inputs": True,
            "partial_credit": False,
            "offline": True,
        },
    )
    training_entries_by_path = {entry["path"]: entry for entry in provenance["payload"]["files"]}
    training_refs = [
        {
            "path": path.relative_to(upstream).as_posix(),
            "content_digest": training_entries_by_path[path.relative_to(upstream).as_posix()]["content_digest"],
        }
        for path in training_paths
    ]
    training_statistics = {
        "task_count": len(training_paths),
        "demonstration_pair_count": 0,
        "heldout_test_pair_count": 0,
        "observed_colors": [],
        "maximum_grid_height": 0,
        "maximum_grid_width": 0,
    }
    observed_colors: set[int] = set()
    for path in training_paths:
        task = validate_task(read_json(path), f"training/{path.name}", require_test_outputs=True)
        training_statistics["demonstration_pair_count"] += len(task["train"])
        training_statistics["heldout_test_pair_count"] += len(task["test"])
        for pair in [*task["train"], *task["test"]]:
            for field in ("input", "output"):
                grid = pair[field]
                training_statistics["maximum_grid_height"] = max(training_statistics["maximum_grid_height"], len(grid))
                training_statistics["maximum_grid_width"] = max(training_statistics["maximum_grid_width"], len(grid[0]))
                observed_colors.update(cell for row in grid for cell in row)
    training_statistics["observed_colors"] = sorted(observed_colors)
    baseline_prompts = make_artifact(
        "irisx/prompts-programs",
        "arc-agi-2-common-interface",
        "1.0.0",
        {
            "instruction": "Infer the transformation from the demonstrations and return only one rectangular JSON grid of integers 0 through 9.",
            "validation": "Reject non-JSON, non-rectangular, out-of-range, or greater-than-30-by-30 grids.",
            "specialization": False,
        },
    )
    candidate_prompts = make_artifact(
        "irisx/prompts-programs",
        "arc-agi-2-training-derived-reasoning-policy",
        "1.0.0",
        {
            "instruction": baseline_prompts["payload"]["instruction"],
            "validation": baseline_prompts["payload"]["validation"],
            "specialization": True,
            "reasoning_policy": [
                "Compare dimensions, colors, connected components, symmetry, repetition, and object motion across every demonstration.",
                "Form the smallest transformation consistent with all demonstrations before constructing the test output.",
                "Check dimensions and every cell against the inferred transformation before returning the grid.",
            ],
        },
    )
    specialization = make_artifact(
        "irisx/specialization-provenance",
        "arc-agi-2-trial-001-specialization",
        "1.0.0",
        {
            "authorized_split": "official public training",
            "procedure": "Deterministically bind a static ARC reasoning checklist and its exact public-training provenance; no weights are changed.",
            "training_task_count": len(training_refs),
            "training_files": training_refs,
            "training_statistics": training_statistics,
            "prompts_programs_ref": artifact_ref(candidate_prompts),
            "evaluation_material_used": False,
            "result_feedback_used": False,
            "weight_changes": False,
        },
    )
    model = make_artifact(
        "irisx/model-descriptor",
        "qwen3.8-27b-trial-001",
        "1.0.0",
        {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "weights_frozen": True,
            "source_binding_state": "unbound",
            "model_source_provenance_digest": None,
        },
    )
    test_input_count = sum(len(case["test"]) for case in solver_cases)
    envelope = make_artifact(
        "irisx/execution-envelope",
        "arc-agi-2-trial-001-kaggle-envelope",
        "1.0.0",
        {
            "venue": "kaggle-network-disabled-notebook",
            "hardware": {"gpu_count": 1, "gpu_model": "NVIDIA RTX PRO 6000", "gpu_memory_gb": 96},
            "configuration_order": ["baseline", "candidate"],
            "attempts_per_test_input": 2,
            "invocation_limit_per_configuration": test_input_count * 2,
            "timeout_seconds_per_invocation": 600,
            "wall_clock_limit_seconds": 43200,
            "seed_policy": "sha256(configuration-ref,case-id,test-index,attempt-index) reduced to uint32",
            "decoding": {"do_sample": True, "temperature": 0.2, "top_p": 0.95},
            "output_limits": {"max_new_tokens": 32768, "max_response_bytes": 262144, "grid_height": 30, "grid_width": 30},
            "network_enabled": False,
            "provider_calls": False,
            "external_paid_cost_usd": 0,
        },
    )
    runtime = make_artifact(
        "irisx/offline-runtime",
        "arc-agi-2-kaggle-runtime",
        "1.0.0",
        {
            "python": "3.11",
            "required_modules": ["torch", "transformers"],
            "dependency_source": "preinstalled Kaggle image or separately digest-bound private input; no network installation",
            "model_loading": "local_files_only",
        },
    )
    baseline = CandidateConfiguration(
        "arc-agi-2-trial-001-baseline",
        "1.0.0",
        {
            "name": "ARC-AGI-2 Trial 001 baseline",
            "description": "Frozen Qwen checkpoint with the common ARC interface only.",
            "components": {
                "model": artifact_ref(model),
                "prompts_programs": artifact_ref(baseline_prompts),
                "workflow_control": artifact_ref(runtime),
                "validation": artifact_ref(evaluator),
            },
            "complexity": 1,
            "maintainability": "unknown",
            "known_limitations": ["No performance claim exists before the separately authorized real run."],
        },
    )
    candidate = CandidateConfiguration(
        "arc-agi-2-trial-001-candidate",
        "1.0.0",
        {
            "name": "ARC-AGI-2 Trial 001 specialized candidate",
            "description": "The same frozen checkpoint and envelope with only the training-derived prompts_programs component changed.",
            "components": {
                "model": artifact_ref(model),
                "prompts_programs": artifact_ref(candidate_prompts),
                "workflow_control": artifact_ref(runtime),
                "validation": artifact_ref(evaluator),
            },
            "complexity": 1,
            "maintainability": "unknown",
            "known_limitations": ["No performance claim exists before the separately authorized real run."],
        },
    )
    workload = WorkloadDefinition(
        "arc-agi-2-public-evaluation",
        "1.0.0",
        {
            "name": "ARC-AGI-2 complete public evaluation split",
            "description": "The 120 official public evaluation tasks at the pinned upstream commit.",
            "frozen": True,
            "evaluator_ref": artifact_ref(evaluator),
            "cases": workload_cases,
        },
    )
    requirements = RequirementSet(
        "arc-agi-2-trial-001-requirements",
        "1.0.0",
        {
            "name": "ARC-AGI-2 Trial 001 requirements",
            "requirements": [
                {"requirement_id": "zero-evaluation-leaks", "metric": "evaluation_leaks", "comparator": "==", "threshold": 0, "hard": True, "objective": "satisfy", "unit": "count", "description": "No evaluator truth or feedback reaches execution."},
                {"requirement_id": "zero-network-calls", "metric": "network_calls", "comparator": "==", "threshold": 0, "hard": True, "objective": "satisfy", "unit": "count", "description": "Measured execution makes no network calls."},
                {"requirement_id": "zero-provider-calls", "metric": "provider_calls", "comparator": "==", "threshold": 0, "hard": True, "objective": "satisfy", "unit": "count", "description": "Measured execution makes no external provider calls."},
                {"requirement_id": "zero-external-cost", "metric": "monetary_cost", "comparator": "==", "threshold": 0, "hard": True, "objective": "satisfy", "unit": "usd", "description": "External paid cost remains zero."},
                {"requirement_id": "complete-results", "metric": "malformed_or_missing_results", "comparator": "==", "threshold": 0, "hard": True, "objective": "satisfy", "unit": "count", "description": "Every required attempt is present and structurally valid."},
                {"requirement_id": "complete-workload", "metric": "workload_case_count", "comparator": "==", "threshold": len(workload_cases), "hard": True, "objective": "satisfy", "unit": "count", "description": "The complete frozen public evaluation workload is represented."},
                {"requirement_id": "exact-identity", "metric": "identity_binding_failures", "comparator": "==", "threshold": 0, "hard": True, "objective": "satisfy", "unit": "count", "description": "Every source, model, configuration, package, and envelope identity matches."},
                {"requirement_id": "arc-accuracy", "metric": "accuracy", "comparator": ">=", "threshold": 0, "hard": False, "objective": "maximize", "unit": "ratio", "description": "Maximize exact ARC task pass rate without changing other controls."},
            ],
        },
    )
    specification = DomainSpecification(
        "arc-agi-2",
        "1.0.0",
        {
            "name": "ARC-AGI-2",
            "description": "Pinned official ARC-AGI-2 public data for Trial 001.",
            "material_refs": [
                _source_ref("arc-agi-2-official-source", "source-provenance.json", provenance["payload"]),
                _source_ref("arc-agi-2-public-eval-solver-cases", "solver-cases.json", solver_artifact["payload"]),
            ],
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "operating_constraints": ["network-disabled measured execution", "official public ARC data only", "zero external paid cost", "frozen model weights"],
            "known_limitations": [
                "Evaluation covers only the pinned public ARC-AGI-2 evaluation snapshot.",
                "No claim is made about semi-private or private performance.",
                "No ARC Prize or state-of-the-art claim is made.",
                "Only the first minimal specialization intervention is tested.",
            ],
        },
    )
    trial = EngineeringTrial(
        "arc-agi-2-trial-001",
        "1.0.0",
        {
            "name": "ARC-AGI-2 Trial 001",
            "goal": "Measure one static public-training-derived prompts_programs intervention against the identical frozen-model baseline.",
            "qualification_fixture": False,
            "domain_specification_ref": specification.ref(),
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "baseline_configuration_ref": baseline.ref(),
            "candidate_configuration_refs": [candidate.ref()],
            "stop_conditions": ["identity mismatch", "evaluation leakage", "network or provider activity", "credentials present", "non-zero external paid cost", "incomplete evidence"],
        },
    )
    trial_profile = make_artifact(
        "irisx/arc-trial-profile",
        "arc-agi-2-trial-001-profile",
        "1.0.0",
        {
            "source_provenance_ref": artifact_ref(provenance),
            "solver_cases_ref": artifact_ref(solver_artifact),
            "evaluator_truth_ref": artifact_ref(truth_artifact),
            "specialization_ref": artifact_ref(specialization),
            "model_ref": artifact_ref(model),
            "execution_envelope_ref": artifact_ref(envelope),
            "runtime_ref": artifact_ref(runtime),
            "baseline_configuration_ref": baseline.ref(),
            "candidate_configuration_ref": candidate.ref(),
            "owner_run_authorized": False,
        },
    )
    for name, value in (
        ("source-provenance.json", provenance),
        ("solver-cases.json", solver_artifact),
        ("evaluator-truth.json", truth_artifact),
        ("evaluator.json", evaluator),
        ("baseline-prompts.json", baseline_prompts),
        ("candidate-prompts.json", candidate_prompts),
        ("specialization.json", specialization),
        ("model.json", model),
        ("execution-envelope.json", envelope),
        ("runtime.json", runtime),
        ("trial-profile.json", trial_profile),
    ):
        write_artifact(output / name, value)
    _write_contracts(
        output,
        [
            ("workload.json", workload),
            ("requirements.json", requirements),
            ("specification.json", specification),
            ("baseline.json", baseline),
            ("candidate.json", candidate),
            ("trial.json", trial),
        ],
    )
    validate_trial_bundle(output, expected_evaluation_count=profile.evaluation_count)
    return trial


def _artifact_at(root: Path, name: str, kind: str) -> dict[str, Any]:
    return load_artifact(root / name, kind=kind)


def validate_trial_bundle(root: Path, *, expected_evaluation_count: int = PUBLIC_EVALUATION_COUNT) -> EngineeringTrial:
    source_provenance = _artifact_at(root, "source-provenance.json", "irisx/arc-source-provenance")
    solver = _artifact_at(root, "solver-cases.json", "irisx/arc-solver-cases")
    truth = _artifact_at(root, "evaluator-truth.json", "irisx/arc-evaluator-truth")
    evaluator = _artifact_at(root, "evaluator.json", "irisx/evaluator-definition")
    baseline_prompts = _artifact_at(root, "baseline-prompts.json", "irisx/prompts-programs")
    candidate_prompts = _artifact_at(root, "candidate-prompts.json", "irisx/prompts-programs")
    specialization = _artifact_at(root, "specialization.json", "irisx/specialization-provenance")
    model = _artifact_at(root, "model.json", "irisx/model-descriptor")
    envelope = _artifact_at(root, "execution-envelope.json", "irisx/execution-envelope")
    runtime = _artifact_at(root, "runtime.json", "irisx/offline-runtime")
    profile = _artifact_at(root, "trial-profile.json", "irisx/arc-trial-profile")
    workload = load_contract(root / "workload.json", WorkloadDefinition)
    requirements = load_contract(root / "requirements.json", RequirementSet)
    specification = load_contract(root / "specification.json", DomainSpecification)
    baseline = load_contract(root / "baseline.json", CandidateConfiguration)
    candidate = load_contract(root / "candidate.json", CandidateConfiguration)
    trial = load_contract(root / "trial.json", EngineeringTrial)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    assert isinstance(specification, DomainSpecification)
    assert isinstance(baseline, CandidateConfiguration)
    assert isinstance(candidate, CandidateConfiguration)
    assert isinstance(trial, EngineeringTrial)
    if (
        source_provenance["payload"].get("repository") != ARC_REPOSITORY
        or source_provenance["payload"].get("commit") != ARC_COMMIT
        or source_provenance["payload"].get("evaluation_task_count") != expected_evaluation_count
    ):
        raise ValidationError("trial source provenance identity is stale or substituted")
    if trial.payload["qualification_fixture"]:
        raise ValidationError("ARC-AGI-2 Trial 001 must not be a qualification fixture")
    assert_binding(trial.payload["domain_specification_ref"], specification, "trial.domain_specification_ref")
    assert_binding(trial.payload["workload_ref"], workload, "trial.workload_ref")
    assert_binding(trial.payload["requirement_set_ref"], requirements, "trial.requirement_set_ref")
    assert_binding(trial.payload["baseline_configuration_ref"], baseline, "trial.baseline_configuration_ref")
    if trial.payload["candidate_configuration_refs"] != [candidate.ref()]:
        raise ValidationError("Trial 001 must bind exactly the one specialized candidate")
    if trial.payload["evaluator_ref"] != artifact_ref(evaluator) or workload.payload["evaluator_ref"] != artifact_ref(evaluator):
        raise ValidationError("ARC evaluator binding is stale or substituted")
    if len(workload.payload["cases"]) != expected_evaluation_count:
        raise ValidationError(f"ARC workload must contain exactly {expected_evaluation_count} cases")
    solver_cases = solver["payload"].get("cases")
    truth_cases = truth["payload"].get("cases")
    if not isinstance(solver_cases, list) or not isinstance(truth_cases, list):
        raise ValidationError("ARC solver and truth views must contain case arrays")
    solver_by_id = {case.get("case_id"): case for case in solver_cases if isinstance(case, dict)}
    truth_by_id = {case.get("case_id"): case for case in truth_cases if isinstance(case, dict)}
    workload_ids = [case["case_id"] for case in workload.payload["cases"]]
    if len(solver_by_id) != len(solver_cases) or len(truth_by_id) != len(truth_cases):
        raise ValidationError("ARC views contain duplicate or malformed case identifiers")
    if set(solver_by_id) != set(workload_ids) or set(truth_by_id) != set(workload_ids):
        raise ValidationError("ARC solver, truth, and workload views do not cover the same cases")
    for workload_case in workload.payload["cases"]:
        case_id = workload_case["case_id"]
        if workload_case["segment"] != "public_eval" or workload_case["critical"]:
            raise ValidationError("ARC workload segmentation or criticality was substituted")
        solver_case = solver_by_id[case_id]
        if set(solver_case) != {"case_id", "train", "test"}:
            raise ValidationError(f"solver-facing case contains forbidden fields: {case_id}")
        validate_task(
            {"train": solver_case["train"], "test": solver_case["test"]},
            f"solver/{case_id}",
            require_test_outputs=False,
        )
        truth_case = truth_by_id[case_id]
        if set(truth_case) != {"case_id", "expected"} or not isinstance(truth_case["expected"], list):
            raise ValidationError(f"evaluator truth case is malformed: {case_id}")
        for index, grid in enumerate(truth_case["expected"]):
            validate_grid(grid, f"truth/{case_id}/{index}")
        if len(truth_case["expected"]) != len(solver_case["test"]):
            raise ValidationError(f"solver/truth test-input count mismatch: {case_id}")
        if workload_case["input_ref"] != _source_ref(
            f"{case_id}-input", f"solver-cases.json/{case_id}/input", solver_case
        ):
            raise ValidationError(f"solver-facing workload reference is stale: {case_id}")
        if workload_case["expected_ref"] != _source_ref(
            f"{case_id}-expected", f"evaluator-truth.json/{case_id}/expected", truth_case["expected"]
        ):
            raise ValidationError(f"evaluator-only workload reference is stale: {case_id}")
    model_payload = model["payload"]
    if model_payload.get("repository") != MODEL_REPOSITORY or model_payload.get("revision") != MODEL_REVISION:
        raise ValidationError("Trial 001 model descriptor is not bound to the selected Qwen revision")
    if model_payload.get("license") != MODEL_LICENSE or model_payload.get("weights_frozen") is not True:
        raise ValidationError("Trial 001 model license or frozen-weight binding is invalid")
    if envelope["payload"].get("venue") != "kaggle-network-disabled-notebook":
        raise ValidationError("Trial 001 execution venue is not the Decision 0005 Kaggle path")
    if envelope["payload"].get("network_enabled") is not False or envelope["payload"].get("external_paid_cost_usd") != 0:
        raise ValidationError("Trial 001 envelope must disable network and external paid cost")
    hardware = envelope["payload"].get("hardware")
    if hardware != {"gpu_count": 1, "gpu_model": "NVIDIA RTX PRO 6000", "gpu_memory_gb": 96}:
        raise ValidationError("Trial 001 hardware binding is stale or substituted")
    common_components = {"model", "prompts_programs", "workflow_control", "validation"}
    if set(baseline.payload["components"]) != common_components or set(candidate.payload["components"]) != common_components:
        raise ValidationError("Trial 001 configurations contain unauthorized components")
    for name in common_components - {"prompts_programs"}:
        if baseline.payload["components"][name] != candidate.payload["components"][name]:
            raise ValidationError(f"Trial 001 baseline/candidate {name} components differ")
    if baseline.payload["components"]["model"] != artifact_ref(model):
        raise ValidationError("Trial 001 configurations do not bind the frozen model descriptor")
    if baseline.payload["components"]["workflow_control"] != artifact_ref(runtime):
        raise ValidationError("Trial 001 configurations do not bind the common runtime")
    if baseline.payload["components"]["validation"] != artifact_ref(evaluator):
        raise ValidationError("Trial 001 configurations do not bind the common evaluator")
    if baseline.payload["components"]["prompts_programs"] != artifact_ref(baseline_prompts):
        raise ValidationError("baseline prompts_programs binding is stale")
    if candidate.payload["components"]["prompts_programs"] != artifact_ref(candidate_prompts):
        raise ValidationError("candidate prompts_programs binding is stale")
    if specialization["payload"].get("prompts_programs_ref") != artifact_ref(candidate_prompts):
        raise ValidationError("specialization provenance does not bind the candidate prompts")
    if specialization["payload"].get("evaluation_material_used") is not False or specialization["payload"].get("result_feedback_used") is not False:
        raise ValidationError("specialization provenance reports prohibited evaluation influence")
    training_files = specialization["payload"].get("training_files")
    if not isinstance(training_files, list) or len(training_files) != specialization["payload"].get("training_task_count"):
        raise ValidationError("specialization training provenance is incomplete")
    if any(not isinstance(entry, dict) or set(entry) != {"path", "content_digest"} for entry in training_files):
        raise ValidationError("specialization training provenance entries are malformed")
    training_paths = [entry["path"] for entry in training_files]
    if (
        len(training_paths) != len(training_files)
        or len(set(training_paths)) != len(training_paths)
        or any(not isinstance(path, str) or not path.startswith("data/training/") or not path.endswith(".json") for path in training_paths)
    ):
        raise ValidationError("specialization provenance contains non-training or duplicate sources")
    source_files = source_provenance["payload"].get("files")
    if not isinstance(source_files, list) or any(
        not isinstance(entry, dict) or set(entry) != {"path", "byte_size", "content_digest"}
        for entry in source_files
    ):
        raise ValidationError("source provenance file entries are malformed")
    source_entries = {entry["path"]: entry["content_digest"] for entry in source_files}
    if any(source_entries.get(entry["path"]) != entry.get("content_digest") for entry in training_files):
        raise ValidationError("specialization training provenance is stale or outside the official source")
    statistics = specialization["payload"].get("training_statistics")
    if not isinstance(statistics, dict) or statistics.get("task_count") != len(training_files):
        raise ValidationError("specialization training statistics are missing or stale")
    expected_profile_refs = {
        "source_provenance_ref": artifact_ref(source_provenance),
        "solver_cases_ref": artifact_ref(solver),
        "evaluator_truth_ref": artifact_ref(truth),
        "specialization_ref": artifact_ref(specialization),
        "model_ref": artifact_ref(model),
        "execution_envelope_ref": artifact_ref(envelope),
        "runtime_ref": artifact_ref(runtime),
        "baseline_configuration_ref": baseline.ref(),
        "candidate_configuration_ref": candidate.ref(),
    }
    for field, expected in expected_profile_refs.items():
        if profile["payload"].get(field) != expected:
            raise ValidationError(f"trial profile {field} is stale or substituted")
    if profile["payload"].get("owner_run_authorized") is not False:
        raise ValidationError("repository implementation must not self-authorize the real run")
    return trial


def validate_predictions(
    value: Any,
    solver_cases: dict[str, Any],
    configuration_ref: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"format", "format_version", "configuration_ref", "cases"}:
        raise ValidationError("prediction document has unexpected fields")
    if value["format"] != "irisx/arc-agi-2-predictions" or value["format_version"] != "1.0":
        raise ValidationError("unsupported ARC prediction format")
    if value["configuration_ref"] != configuration_ref:
        raise ValidationError("prediction configuration binding is stale or substituted")
    expected_cases = solver_cases["payload"]["cases"]
    if not isinstance(value["cases"], list):
        raise ValidationError("prediction cases must be an array")
    actual_by_id = {case.get("case_id"): case for case in value["cases"] if isinstance(case, dict)}
    if len(actual_by_id) != len(value["cases"]) or set(actual_by_id) != {case["case_id"] for case in expected_cases}:
        raise ValidationError("predictions do not exactly cover the solver-facing cases")
    for expected_case in expected_cases:
        case_id = expected_case["case_id"]
        actual = actual_by_id[case_id]
        if set(actual) != {"case_id", "tests"} or not isinstance(actual["tests"], list):
            raise ValidationError(f"prediction case is malformed: {case_id}")
        if len(actual["tests"]) != len(expected_case["test"]):
            raise ValidationError(f"prediction test-input count mismatch: {case_id}")
        for index, test in enumerate(actual["tests"]):
            if not isinstance(test, dict) or set(test) != {"test_index", "attempts"} or test["test_index"] != index:
                raise ValidationError(f"prediction test index is malformed: {case_id}/{index}")
            attempts = test["attempts"]
            if not isinstance(attempts, list) or len(attempts) != 2:
                raise ValidationError(f"exactly two prediction attempts are required: {case_id}/{index}")
            for attempt_index, attempt in enumerate(attempts):
                if not isinstance(attempt, dict) or set(attempt) != {"attempt_index", "status", "grid", "raw_output_digest"}:
                    raise ValidationError(f"prediction attempt is malformed: {case_id}/{index}/{attempt_index}")
                if attempt["attempt_index"] != attempt_index or attempt["status"] not in {"ok", "malformed", "timeout", "error"}:
                    raise ValidationError(f"prediction attempt identity or status is invalid: {case_id}/{index}/{attempt_index}")
                if attempt["status"] == "ok":
                    validate_grid(attempt["grid"], f"prediction/{case_id}/{index}/{attempt_index}")
                elif attempt["grid"] is not None:
                    raise ValidationError(f"non-ok prediction attempts must use a null grid: {case_id}/{index}/{attempt_index}")
                digest = attempt["raw_output_digest"]
                if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
                    raise ValidationError(f"prediction raw output digest is invalid: {case_id}/{index}/{attempt_index}")
    return value


def score_predictions(
    trial_root: Path,
    predictions: dict[str, Any],
    configuration: CandidateConfiguration,
    observations: dict[str, Any],
    *,
    result_id: str,
) -> EvaluationResult:
    validate_trial_bundle(trial_root, expected_evaluation_count=len(load_artifact(trial_root / "solver-cases.json")["payload"]["cases"]))
    trial = load_contract(trial_root / "trial.json", EngineeringTrial)
    workload = load_contract(trial_root / "workload.json", WorkloadDefinition)
    evaluator = load_artifact(trial_root / "evaluator.json", kind="irisx/evaluator-definition")
    solver = load_artifact(trial_root / "solver-cases.json", kind="irisx/arc-solver-cases")
    truth = load_artifact(trial_root / "evaluator-truth.json", kind="irisx/arc-evaluator-truth")
    assert isinstance(trial, EngineeringTrial)
    assert isinstance(workload, WorkloadDefinition)
    validate_predictions(predictions, solver, configuration.ref())
    truth_by_id = {case["case_id"]: case["expected"] for case in truth["payload"]["cases"]}
    outcomes: list[dict[str, Any]] = []
    malformed = 0
    for case in predictions["cases"]:
        case_id = case["case_id"]
        test_passes: list[bool] = []
        for test in case["tests"]:
            expected = truth_by_id[case_id][test["test_index"]]
            success = False
            for attempt in test["attempts"]:
                if attempt["status"] != "ok":
                    malformed += 1
                elif attempt["grid"] == expected:
                    success = True
            test_passes.append(success)
        passed = all(test_passes)
        outcomes.append(
            {
                "case_id": case_id,
                "segment": "public_eval",
                "passed": passed,
                "critical_failure": False,
                "score": 1 if passed else 0,
                "detail": "all test inputs passed within two attempts" if passed else "one or more test inputs failed pass@2",
            }
        )
    accuracy = sum(item["passed"] for item in outcomes) / len(outcomes)
    metrics = {
        "accuracy": {"state": "observed", "value": accuracy, "unit": "ratio"},
        "accuracy.public_eval": {"state": "observed", "value": accuracy, "unit": "ratio"},
        "critical_failures": {"state": "observed", "value": 0, "unit": "count"},
        "evaluation_leaks": {"state": "observed", "value": observations["evaluation_leaks"], "unit": "count"},
        "network_calls": {"state": "observed", "value": observations["network_calls"], "unit": "count"},
        "provider_calls": {"state": "observed", "value": observations["provider_calls"], "unit": "count"},
        "monetary_cost": {"state": "observed", "value": observations["external_paid_cost_usd"], "unit": "usd"},
        "malformed_or_missing_results": {"state": "observed", "value": malformed, "unit": "count"},
        "workload_case_count": {"state": "observed", "value": len(outcomes), "unit": "count"},
        "identity_binding_failures": {"state": "observed", "value": observations["identity_binding_failures"], "unit": "count"},
    }
    return EvaluationResult(
        result_id,
        "1.0.0",
        {
            "trial_ref": trial.ref(),
            "workload_ref": workload.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "configuration_ref": configuration.ref(),
            "cases": outcomes,
            "metrics": metrics,
            "resource_use": {
                "network_calls": metrics["network_calls"],
                "provider_calls": metrics["provider_calls"],
                "monetary_cost": metrics["monetary_cost"],
                "wall_clock_seconds": {"state": "observed", "value": observations["wall_clock_seconds"], "unit": "seconds"},
                "gpu_seconds": {"state": observations["gpu_seconds_state"], "value": observations["gpu_seconds"], "unit": "seconds"},
            },
            "known_limitations": [
                "Evaluation covers only the pinned public ARC-AGI-2 evaluation snapshot.",
                "No claim is made about semi-private or private performance.",
            ],
        },
    )


def p2_acceptance(
    baseline: EvaluationResult,
    candidate: EvaluationResult,
    requirements: RequirementSet,
    workload: WorkloadDefinition,
) -> dict[str, Any]:
    baseline_score = baseline.payload["metrics"]["accuracy"]
    candidate_score = candidate.payload["metrics"]["accuracy"]
    if baseline_score["state"] != "observed" or candidate_score["state"] != "observed":
        raise ValidationError("P2 acceptance requires observed ARC accuracy for both configurations")
    improvement = candidate_score["value"] - baseline_score["value"]
    hard_pass = satisfies_hard_requirements(baseline, requirements, workload) and satisfies_hard_requirements(
        candidate, requirements, workload
    )
    accepted = bool(hard_pass and improvement >= P2_IMPROVEMENT_THRESHOLD)
    return make_artifact(
        "irisx/p2-acceptance",
        "arc-agi-2-trial-001-acceptance",
        "1.0.0",
        {
            "baseline_result_ref": baseline.ref(),
            "candidate_result_ref": candidate.ref(),
            "baseline_accuracy": baseline_score["value"],
            "candidate_accuracy": candidate_score["value"],
            "improvement": improvement,
            "required_improvement": P2_IMPROVEMENT_THRESHOLD,
            "all_hard_requirements_pass": hard_pass,
            "accepted": accepted,
            "package_eligible": accepted,
            "candidate_requirement_verdicts": requirement_verdicts(candidate, requirements, workload),
        },
    )

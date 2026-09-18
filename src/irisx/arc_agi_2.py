"""Bounded, offline ARC-AGI-2 Trial 001 preparation and evidence validation."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterable

from .artifacts import artifact_ref, make_artifact, validate_artifact, write_artifact
from .bindings import validate_decision_bindings, validate_trial_bindings
from .bundle import Document, document_ref, load_bundle, load_document, require_contract, resolve_ref
from .canonical import digest_bytes, digest_value, read_json, write_json
from .contracts import (
    CandidateConfiguration,
    DomainPackageManifest,
    DomainSpecification,
    EngineeringTrial,
    EvaluationResult,
    RequirementSet,
    SelectionDecision,
    VersionedContract,
    WorkloadDefinition,
    assert_binding,
    load_contract,
    resolve_logical_path,
)
from .engine import (
    select_configuration,
    satisfies_hard_requirements,
    validate_result_evidence,
)
from .errors import ValidationError


OFFICIAL_REPOSITORY = "arcprize/ARC-AGI-2"
OFFICIAL_REMOTE = "https://github.com/arcprize/ARC-AGI-2.git"
PINNED_COMMIT = "f3283f727488ad98fe575ea6a5ac981e4a188e49"
TRAINING_TASK_COUNT = 1000
EVALUATION_TASK_COUNT = 120
SEGMENT = "public_eval"
ATTEMPTS_PER_TEST_INPUT = 2
P2_ACCEPTANCE_DELTA = 0.05
P2_ACCEPTANCE_TASK_DELTA = 6
DECISION_PATH = "docs/decisions/0004-admit-first-p2-arc-agi-2-engineering-trial.md"
DECISION_SHA256 = "sha256:1fa8dac045964b5afd00b1ee8295f2b2457397a894bc7e628e777a9d1d570510"
UNBOUND_MODEL_LIMITATION = "A concrete immutable local model or solver is not yet bound."

P2_LIMITATIONS = [
    "Evaluation covers only the pinned public ARC-AGI-2 evaluation snapshot.",
    "No claim is made about semi-private or private performance.",
    "No ARC Prize or state-of-the-art claim is made.",
    "Only the first minimal specialization intervention was tested.",
]

ARC_EVALUATOR_PAYLOAD = {
    "method": "arc-agi-2-pass-at-2-exact-grid",
    "attempts_per_test_input": ATTEMPTS_PER_TEST_INPUT,
    "task_success": "all test inputs have an exact matching prediction within two attempts",
    "grid": {"min_dimension": 1, "max_dimension": 30, "cell_min": 0, "cell_max": 9},
    "partial_credit": False,
    "aggregate": ["accuracy", "accuracy.public_eval", "critical_failures"],
    "offline": True,
    "source": {"repository": OFFICIAL_REPOSITORY, "commit": PINNED_COMMIT},
}

TRIAL_FILES = {
    "source": "evidence/source-provenance.json",
    "solver_cases": "materialized/solver-cases.json",
    "truth": "materialized/evaluator-truth.json",
    "specialization": "materialized/specialization/derivation.json",
    "baseline_prompt": "components/baseline-prompt-program.json",
    "candidate_prompt": "components/candidate-prompt-program.json",
    "evaluator": "evaluator.json",
    "workload": "workload.json",
    "requirements": "requirements.json",
    "specification": "specification.json",
    "baseline": "baseline.json",
    "candidate": "candidate.json",
    "trial": "trial.json",
    "envelope": "execution-envelope.json",
    "profile": "trial-profile.json",
}

OPTIONAL_TRIAL_FILES = {
    "model": "local-solver.json",
}

PROVIDER_CREDENTIAL_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "HF_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
)


def _fail(message: str) -> None:
    raise ValidationError(message)


def _ensure_empty(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        _fail(f"output directory must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _write_document(path: Path, document: Document) -> None:
    value = document.to_dict() if isinstance(document, VersionedContract) else document
    write_json(path, value)


def _git(
    root: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
        }
    )
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        _fail(f"git {' '.join(args)} failed: {detail}")
    return completed


def _git_text(root: Path, *args: str) -> str:
    return _git(root, *args).stdout.decode("utf-8", "strict").strip()


def _tracked_paths(upstream: Path) -> list[str]:
    return sorted(line for line in _git_text(upstream, "ls-tree", "-r", "--name-only", "HEAD").splitlines() if line)


def _working_paths(upstream: Path) -> list[str]:
    paths: list[str] = []
    for path in upstream.rglob("*"):
        relative = path.relative_to(upstream)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            _fail(f"official source snapshot must not contain symbolic links: {relative.as_posix()}")
        if path.is_file():
            paths.append(relative.as_posix())
    return sorted(paths)


def _task_paths(upstream: Path, split: str) -> list[Path]:
    directory = upstream / "data" / split
    if not directory.is_dir():
        _fail(f"official source is missing data/{split}")
    paths = sorted(directory.glob("*.json"), key=lambda item: item.name)
    unexpected = sorted(
        path.relative_to(upstream).as_posix()
        for path in directory.iterdir()
        if not path.is_file() or path.suffix != ".json"
    )
    if unexpected:
        _fail(f"official data/{split} contains unsupported entries: {unexpected}")
    return paths


def validate_grid(value: Any, path: str = "grid") -> list[list[int]]:
    if not isinstance(value, list) or not value or len(value) > 30:
        _fail(f"{path}: must be a grid with 1..30 rows")
    width: int | None = None
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or not row or len(row) > 30:
            _fail(f"{path}[{row_index}]: must contain 1..30 cells")
        if width is None:
            width = len(row)
        elif len(row) != width:
            _fail(f"{path}: rows must have identical dimensions")
        for column_index, cell in enumerate(row):
            if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell <= 9:
                _fail(f"{path}[{row_index}][{column_index}]: must be an integer from 0 through 9")
    return value


def _validate_pair(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"input", "output"}:
        _fail(f"{path}: must contain exactly input and output")
    validate_grid(value["input"], f"{path}.input")
    validate_grid(value["output"], f"{path}.output")
    return value


def validate_task_document(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"train", "test"}:
        _fail(f"{path}: ARC task must contain exactly train and test")
    for split in ("train", "test"):
        pairs = value[split]
        if not isinstance(pairs, list) or not pairs:
            _fail(f"{path}.{split}: must be a non-empty array")
        for index, pair in enumerate(pairs):
            _validate_pair(pair, f"{path}.{split}[{index}]")
    return value


def _source_file_entries(upstream: Path, tracked: Iterable[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for relative in tracked:
        path = resolve_logical_path(upstream, relative, f"official source path {relative}")
        if not path.is_file() or path.is_symlink():
            _fail(f"official tracked source file is missing or invalid: {relative}")
        raw = path.read_bytes()
        entries.append({"path": relative, "byte_count": len(raw), "content_digest": digest_bytes(raw)})
    return entries


def _validate_source_git_identity(upstream: Path) -> tuple[str, list[str]]:
    if not (upstream / ".git").is_dir():
        _fail("official source snapshot must retain its Git identity")
    remote = _git_text(upstream, "remote", "get-url", "origin")
    if remote != OFFICIAL_REMOTE:
        _fail(f"official source remote mismatch: expected {OFFICIAL_REMOTE!r}")
    head = _git_text(upstream, "rev-parse", "HEAD")
    if head != PINNED_COMMIT:
        _fail(f"official source commit mismatch: expected {PINNED_COMMIT}")
    symbolic = _git(upstream, "symbolic-ref", "-q", "HEAD", check=False)
    if symbolic.returncode == 0:
        _fail("official source must be a detached checkout, not an unpinned branch head")
    if symbolic.returncode not in {0, 1}:
        _fail("could not verify detached official source checkout")
    status = _git_text(upstream, "status", "--porcelain", "--untracked-files=all")
    if status:
        _fail("official source checkout has changed, missing, or untracked files")
    tracked = _tracked_paths(upstream)
    if tracked != _working_paths(upstream):
        _fail("official source working files do not exactly match the pinned Git tree")
    return remote, tracked


def _build_source_payload(
    source_root: Path,
    *,
    materialized_at_utc: str,
) -> dict[str, Any]:
    upstream = source_root / "upstream"
    remote, tracked = _validate_source_git_identity(upstream)
    training = _task_paths(upstream, "training")
    evaluation = _task_paths(upstream, "evaluation")
    if len(training) != TRAINING_TASK_COUNT:
        _fail(f"official public training split must contain exactly {TRAINING_TASK_COUNT} tasks")
    if len(evaluation) != EVALUATION_TASK_COUNT:
        _fail(f"official public evaluation split must contain exactly {EVALUATION_TASK_COUNT} tasks")
    for split, paths in (("training", training), ("evaluation", evaluation)):
        for task_path in paths:
            validate_task_document(read_json(task_path), f"data/{split}/{task_path.name}")
    return {
        "repository": OFFICIAL_REPOSITORY,
        "remote_url": remote,
        "pinned_commit": PINNED_COMMIT,
        "head_commit": PINNED_COMMIT,
        "checkout": "detached",
        "materialized_at_utc": materialized_at_utc,
        "materialization_command": "python -m irisx arc-agi-2 source materialize --output <source-directory>",
        "splits": {
            "training": {
                "path": "data/training",
                "task_count": len(training),
                "task_ids": [path.stem for path in training],
            },
            "evaluation": {
                "path": "data/evaluation",
                "task_count": len(evaluation),
                "task_ids": [path.stem for path in evaluation],
            },
        },
        "files": _source_file_entries(upstream, tracked),
    }


def materialize_source(output: Path) -> dict[str, Any]:
    """Deliberately acquire only the fixed official source and pin it detached."""

    _ensure_empty(output)
    upstream = output / "upstream"
    _git(output, "clone", "--filter=blob:none", "--no-checkout", OFFICIAL_REMOTE, str(upstream))
    _git(upstream, "config", "core.autocrlf", "false")
    _git(upstream, "fetch", "--depth", "1", "origin", PINNED_COMMIT)
    _git(upstream, "checkout", "--detach", PINNED_COMMIT)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    provenance = make_artifact(
        "irisx/source-provenance",
        "arc-agi-2-official-source",
        "1.0.0",
        _build_source_payload(output, materialized_at_utc=timestamp),
    )
    write_artifact(output / "provenance.json", provenance)
    return validate_source(output)


def validate_source(source_root: Path) -> dict[str, Any]:
    provenance_path = source_root / "provenance.json"
    provenance = validate_artifact(read_json(provenance_path), kind="irisx/source-provenance")
    if provenance["artifact_id"] != "arc-agi-2-official-source" or provenance["version"] != "1.0.0":
        _fail("source provenance has unsupported identity")
    payload = provenance["payload"]
    if not isinstance(payload, dict):
        _fail("source provenance payload must be an object")
    timestamp = payload.get("materialized_at_utc")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        _fail("source provenance materialized_at_utc is missing or invalid")
    recomputed = _build_source_payload(source_root, materialized_at_utc=timestamp)
    if payload != recomputed:
        _fail("source provenance is stale or does not match the preserved official bytes")
    return provenance


def _source_ref(source_id: str, locator: str, value: Any) -> dict[str, str]:
    return {
        "source_id": source_id,
        "media_type": "application/json",
        "content_digest": digest_value(value),
        "locator": locator,
    }


def _policy_from_training_observations(observations: dict[str, Any]) -> list[str]:
    dimensions = observations["observed_grid_dimensions"]
    colors = observations["observed_colors"]
    pair_count = observations["observed_pair_count"]
    same_dimensions = observations["same_dimension_pair_count"]
    palette_preserving = observations["output_palette_subset_pair_count"]
    dimension_text = ", ".join(f"{height}x{width}" for height, width in dimensions)
    color_text = ", ".join(str(color) for color in colors)
    return [
        (
            f"Rank transformation hypotheses by whether they explain all demonstrations; "
            f"the pinned public-training split contributed {pair_count} observed input/output pairs."
        ),
        (
            f"Check shape preservation explicitly: {same_dimensions} of {pair_count} observed pairs "
            "kept identical input/output dimensions; follow the current task demonstrations when they differ."
        ),
        (
            f"Check palette preservation explicitly: {palette_preserving} of {pair_count} observed outputs "
            "used only colors present in their paired inputs; introduce colors only when the demonstrations support it."
        ),
        (
            f"Validate candidate grids against the public-training format evidence: observed colors [{color_text}] "
            f"and observed dimensions [{dimension_text}]."
        ),
    ]


def _training_derivation(
    training_documents: list[tuple[str, dict[str, Any], str]],
    source_ref: dict[str, str],
) -> dict[str, Any]:
    train_pairs = 0
    test_inputs = 0
    colors: set[int] = set()
    dimensions: set[tuple[int, int]] = set()
    observed_pairs = 0
    same_dimension_pairs = 0
    output_palette_subset_pairs = 0
    influences: list[dict[str, str]] = []
    for relative, task, content_digest in training_documents:
        train_pairs += len(task["train"])
        test_inputs += len(task["test"])
        influences.append({"path": relative, "content_digest": content_digest})
        for pair in [*task["train"], *task["test"]]:
            observed_pairs += 1
            if (len(pair["input"]), len(pair["input"][0])) == (len(pair["output"]), len(pair["output"][0])):
                same_dimension_pairs += 1
            input_colors = {cell for row in pair["input"] for cell in row}
            output_colors = {cell for row in pair["output"] for cell in row}
            if output_colors <= input_colors:
                output_palette_subset_pairs += 1
            for field in ("input", "output"):
                grid = pair[field]
                dimensions.add((len(grid), len(grid[0])))
                colors.update(cell for row in grid for cell in row)
    observations = {
        "task_count": len(training_documents),
        "training_demonstration_count": train_pairs,
        "training_test_input_count": test_inputs,
        "observed_pair_count": observed_pairs,
        "same_dimension_pair_count": same_dimension_pairs,
        "output_palette_subset_pair_count": output_palette_subset_pairs,
        "observed_colors": sorted(colors),
        "observed_grid_dimensions": [list(item) for item in sorted(dimensions)],
    }
    payload = {
        "source_provenance_ref": source_ref,
        "authorized_split": "public_training",
        "procedure": "scan every pinned public-training input/output pair, compute exact shape and palette observations, and render the static policy deterministically from those observations",
        "influenced_files": influences,
        "observations": observations,
        "policy": _policy_from_training_observations(observations),
        "forbidden_inputs": ["public evaluation expected outputs", "evaluation scores", "case correctness feedback", "third-party ARC data"],
    }
    return make_artifact("irisx/specialization-derivation", "arc-agi-2-training-policy", "1.0.0", payload)


def _requirements() -> RequirementSet:
    values = [
        ("zero-evaluation-leaks", "evaluation_leak_events", "<=", 0, True, "satisfy", "count", "No evaluation truth or feedback may enter solver or specialization inputs."),
        ("zero-network-calls", "network_calls", "<=", 0, True, "satisfy", "count", "Trial execution must remain offline."),
        ("zero-provider-calls", "provider_calls", "<=", 0, True, "satisfy", "count", "No external provider may be used."),
        ("zero-external-cost", "monetary_cost", "<=", 0, True, "satisfy", "usd", "External paid execution is prohibited."),
        ("complete-results", "malformed_or_missing_cases", "<=", 0, True, "satisfy", "count", "Every frozen case must have complete valid pass@2 evidence."),
        ("complete-workload", "workload_cases", "==", EVALUATION_TASK_COUNT, True, "satisfy", "count", "The complete public evaluation split must be represented."),
        ("exact-identity-bindings", "identity_binding_failures", "<=", 0, True, "satisfy", "count", "All source, evaluator, configuration, envelope, and result identities must match."),
        ("arc-accuracy", "accuracy", ">=", 0, False, "maximize", "ratio", "ARC task accuracy is the sole Trial 001 optimization objective."),
    ]
    return RequirementSet(
        "arc-agi-2-trial-001-requirements",
        "1.0.0",
        {
            "name": "ARC-AGI-2 Trial 001 requirements",
            "requirements": [
                {
                    "requirement_id": identifier,
                    "metric": metric,
                    "comparator": comparator,
                    "threshold": threshold,
                    "hard": hard,
                    "objective": objective,
                    "unit": unit,
                    "description": description,
                }
                for identifier, metric, comparator, threshold, hard, objective, unit, description in values
            ],
        },
    )


def prepare_trial(source_root: Path, output: Path) -> EngineeringTrial:
    provenance = validate_source(source_root)
    _ensure_empty(output)
    upstream = source_root / "upstream"
    file_digests = {item["path"]: item["content_digest"] for item in provenance["payload"]["files"]}

    training_documents: list[tuple[str, dict[str, Any], str]] = []
    for task_path in _task_paths(upstream, "training"):
        relative = task_path.relative_to(upstream).as_posix()
        training_documents.append((relative, validate_task_document(read_json(task_path), relative), file_digests[relative]))

    solver_cases: list[dict[str, Any]] = []
    truth_cases: list[dict[str, Any]] = []
    workload_cases: list[dict[str, Any]] = []
    for task_path in _task_paths(upstream, "evaluation"):
        case_id = task_path.stem
        task = validate_task_document(read_json(task_path), f"data/evaluation/{task_path.name}")
        solver_value = {
            "demonstrations": task["train"],
            "test_inputs": [pair["input"] for pair in task["test"]],
        }
        truth_value = {"expected_outputs": [pair["output"] for pair in task["test"]]}
        solver_cases.append({"case_id": case_id, "segment": SEGMENT, **solver_value})
        truth_cases.append({"case_id": case_id, "segment": SEGMENT, **truth_value})
        workload_cases.append(
            {
                "case_id": case_id,
                "segment": SEGMENT,
                "critical": False,
                "input_ref": _source_ref(
                    f"{case_id}-solver-input",
                    f"{TRIAL_FILES['solver_cases']}/{case_id}/input",
                    solver_value,
                ),
                "expected_ref": _source_ref(
                    f"{case_id}-evaluator-truth",
                    f"{TRIAL_FILES['truth']}/{case_id}/expected",
                    truth_value,
                ),
            }
        )

    provenance_copy = provenance
    solver_artifact = make_artifact(
        "irisx/arc-agi-2-solver-cases",
        "arc-agi-2-public-evaluation-solver-cases",
        "1.0.0",
        {"source_provenance_ref": artifact_ref(provenance_copy), "cases": solver_cases},
    )
    truth_artifact = make_artifact(
        "irisx/arc-agi-2-evaluator-truth",
        "arc-agi-2-public-evaluation-truth",
        "1.0.0",
        {"source_provenance_ref": artifact_ref(provenance_copy), "cases": truth_cases},
    )
    specialization = _training_derivation(training_documents, artifact_ref(provenance_copy))
    evaluator = make_artifact(
        "irisx/evaluator-definition",
        "arc-agi-2-pass-at-2-evaluator",
        "1.0.0",
        ARC_EVALUATOR_PAYLOAD,
    )
    baseline_prompt = make_artifact(
        "irisx/prompt-program",
        "arc-agi-2-common-interface",
        "1.0.0",
        {
            "role": "baseline",
            "instructions": [
                "Use only the provided demonstration input/output pairs and test input grids.",
                "Return exactly two valid ARC grid predictions for each test input.",
                "Do not request evaluator truth, scores, feedback, network access, providers, or external data.",
            ],
            "validation_ref": artifact_ref(evaluator),
        },
    )
    candidate_prompt = make_artifact(
        "irisx/prompt-program",
        "arc-agi-2-training-derived-interface",
        "1.0.0",
        {
            "role": "specialized",
            "common_instruction_ref": artifact_ref(baseline_prompt),
            "derivation_ref": artifact_ref(specialization),
            "policy": specialization["payload"]["policy"],
            "validation_ref": artifact_ref(evaluator),
        },
    )
    workload = WorkloadDefinition(
        "arc-agi-2-public-evaluation",
        "1.0.0",
        {
            "name": "ARC-AGI-2 complete public evaluation split",
            "description": "All 120 task-level cases from the pinned official public evaluation split.",
            "frozen": True,
            "evaluator_ref": artifact_ref(evaluator),
            "cases": workload_cases,
        },
    )
    requirements = _requirements()
    specification = DomainSpecification(
        "arc-agi-2-domain-specification",
        "1.0.0",
        {
            "name": "ARC-AGI-2",
            "description": "Pinned official ARC-AGI-2 public-training specialization and public-evaluation trial.",
            "material_refs": [
                _source_ref("arc-agi-2-official-source", TRIAL_FILES["source"], provenance_copy["payload"])
            ],
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "operating_constraints": [
                "local/offline execution only",
                "official public training and evaluation data only",
                "no provider credentials or calls",
                "zero external paid-execution cost",
                "exactly two predictions per test input",
            ],
            "known_limitations": P2_LIMITATIONS,
        },
    )
    envelope = make_artifact(
        "irisx/execution-envelope",
        "arc-agi-2-trial-001-execution-envelope",
        "1.0.0",
        {
            "model_solver_ref": None,
            "hardware_identity": None,
            "solver_invocation_limit_per_configuration": EVALUATION_TASK_COUNT,
            "attempt_limit_per_test_input": ATTEMPTS_PER_TEST_INPUT,
            "timeout_policy": {"per_task_seconds": 300, "total_seconds": 36000},
            "determinism_policy": {"required": True, "random_seed": 0},
            "output_limits": {"max_grid_height": 30, "max_grid_width": 30, "cell_min": 0, "cell_max": 9},
            "network_enabled": False,
            "provider_execution": False,
            "credentials_allowed": False,
            "maximum_external_cost_usd": 0,
        },
    )
    shared_configuration = {
        "complexity": 1,
        "maintainability": "unknown",
        "known_limitations": [UNBOUND_MODEL_LIMITATION],
    }
    baseline = CandidateConfiguration(
        "arc-agi-2-trial-001-baseline",
        "1.0.0",
        {
            "name": "ARC-AGI-2 Trial 001 baseline",
            "description": "Common ARC interface instruction with no training-derived specialization.",
            "components": {
                "prompts_programs": artifact_ref(baseline_prompt),
                "workflow_control": artifact_ref(envelope),
                "validation": artifact_ref(evaluator),
            },
            **shared_configuration,
        },
    )
    candidate = CandidateConfiguration(
        "arc-agi-2-trial-001-specialized",
        "1.0.0",
        {
            "name": "ARC-AGI-2 Trial 001 specialized candidate",
            "description": "The same unbound local execution path with one public-training-derived static reasoning policy.",
            "components": {
                "prompts_programs": artifact_ref(candidate_prompt),
                "workflow_control": artifact_ref(envelope),
                "validation": artifact_ref(evaluator),
            },
            **shared_configuration,
        },
    )
    trial = EngineeringTrial(
        "arc-agi-2-trial-001",
        "1.0.0",
        {
            "name": "ARC-AGI-2 Trial 001",
            "goal": "Measure whether one static public-training-derived reasoning policy improves public-evaluation ARC accuracy by at least 0.05 absolute.",
            "qualification_fixture": False,
            "domain_specification_ref": specification.ref(),
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "baseline_configuration_ref": baseline.ref(),
            "candidate_configuration_refs": [candidate.ref()],
            "stop_conditions": [
                "wrong, missing, changed, or stale official source identity",
                "evaluation truth or feedback reaches solver or specialization construction",
                "model substitution or execution-envelope mismatch",
                "network, provider, credential, or non-zero external cost activity",
                "missing or malformed result evidence",
            ],
        },
    )
    profile = make_artifact(
        "irisx/arc-agi-2-trial-profile",
        "arc-agi-2-trial-001-profile",
        "1.0.0",
        {
            "authority": {"path": DECISION_PATH, "content_digest": DECISION_SHA256},
            "source_provenance_ref": artifact_ref(provenance_copy),
            "solver_cases_ref": artifact_ref(solver_artifact),
            "evaluator_truth_ref": artifact_ref(truth_artifact),
            "specialization_derivation_ref": artifact_ref(specialization),
            "trial_ref": trial.ref(),
            "baseline_configuration_ref": baseline.ref(),
            "candidate_configuration_ref": candidate.ref(),
            "execution_envelope_ref": artifact_ref(envelope),
            "acceptance_delta": P2_ACCEPTANCE_DELTA,
            "run_authorization_ref": None,
        },
    )

    documents: dict[str, Document] = {
        TRIAL_FILES["source"]: provenance_copy,
        TRIAL_FILES["solver_cases"]: solver_artifact,
        TRIAL_FILES["truth"]: truth_artifact,
        TRIAL_FILES["specialization"]: specialization,
        TRIAL_FILES["baseline_prompt"]: baseline_prompt,
        TRIAL_FILES["candidate_prompt"]: candidate_prompt,
        TRIAL_FILES["evaluator"]: evaluator,
        TRIAL_FILES["workload"]: workload,
        TRIAL_FILES["requirements"]: requirements,
        TRIAL_FILES["specification"]: specification,
        TRIAL_FILES["baseline"]: baseline,
        TRIAL_FILES["candidate"]: candidate,
        TRIAL_FILES["trial"]: trial,
        TRIAL_FILES["envelope"]: envelope,
        TRIAL_FILES["profile"]: profile,
    }
    for relative, document in documents.items():
        _write_document(resolve_logical_path(output, relative, f"trial artifact {relative}"), document)
    validate_trial_bundle(output)
    return trial


def _load_trial_documents(root: Path) -> dict[str, Document]:
    documents: dict[str, Document] = {}
    for name, relative in TRIAL_FILES.items():
        path = resolve_logical_path(root, relative, f"trial artifact {name}")
        if not path.is_file() or path.is_symlink():
            _fail(f"trial artifact is missing or invalid: {relative}")
        documents[name] = load_document(path)
    for name, relative in OPTIONAL_TRIAL_FILES.items():
        path = resolve_logical_path(root, relative, f"optional trial artifact {name}")
        if path.exists():
            if not path.is_file() or path.is_symlink():
                _fail(f"optional trial artifact is invalid: {relative}")
            documents[name] = load_document(path)
    expected = set(TRIAL_FILES.values()) | {
        OPTIONAL_TRIAL_FILES[name]
        for name in OPTIONAL_TRIAL_FILES
        if name in documents
    }
    if "model" in documents:
        model = documents["model"]
        if not isinstance(model, dict):
            _fail("local solver descriptor must be a supporting artifact")
        model = validate_artifact(model, kind="irisx/local-solver-descriptor")
        asset_path = model["payload"].get("asset_path")
        if not isinstance(asset_path, str):
            _fail("local solver descriptor asset_path is missing")
        expected.add(asset_path)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        _fail(f"trial bundle membership mismatch; missing={sorted(expected - actual)} unexpected={sorted(actual - expected)}")
    return documents


def _expect_contract(documents: dict[str, Document], name: str, expected: type[VersionedContract]) -> VersionedContract:
    document = documents[name]
    if not isinstance(document, expected):
        _fail(f"{TRIAL_FILES[name]}: expected {expected.SCHEMA}")
    return document


def _expect_artifact(documents: dict[str, Document], name: str, kind: str) -> dict[str, Any]:
    document = documents[name]
    if not isinstance(document, dict):
        relative = TRIAL_FILES.get(name, OPTIONAL_TRIAL_FILES.get(name, name))
        _fail(f"{relative}: expected {kind}")
    return validate_artifact(document, kind=kind)


def _case_map(artifact: dict[str, Any], *, field: str) -> dict[str, dict[str, Any]]:
    cases = artifact["payload"].get("cases")
    if not isinstance(cases, list):
        _fail(f"{artifact['schema']} payload.cases must be an array")
    result: dict[str, dict[str, Any]] = {}
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            _fail(f"{artifact['schema']} payload.cases[{index}] is invalid")
        case_id = case["case_id"]
        if case_id in result:
            _fail(f"{artifact['schema']} duplicates case {case_id}")
        if case.get("segment") != SEGMENT or field not in case:
            _fail(f"{artifact['schema']} case {case_id} has invalid segment or fields")
        result[case_id] = case
    return result


def _resolve_arc_case_source(
    artifact: dict[str, Any],
    workload_case: dict[str, Any],
    field: str,
) -> dict[str, Any]:
    if field == "input":
        artifact = validate_artifact(artifact, kind="irisx/arc-agi-2-solver-cases")
        case_field = "test_inputs"
        value_fields = ("demonstrations", "test_inputs")
        ref_field = "input_ref"
        source_suffix = "solver-input"
        locator_root = TRIAL_FILES["solver_cases"]
    elif field == "expected":
        artifact = validate_artifact(artifact, kind="irisx/arc-agi-2-evaluator-truth")
        case_field = "expected_outputs"
        value_fields = ("expected_outputs",)
        ref_field = "expected_ref"
        source_suffix = "evaluator-truth"
        locator_root = TRIAL_FILES["truth"]
    else:
        _fail(f"unsupported ARC case source field: {field}")
    cases = _case_map(artifact, field=case_field)
    case_id = workload_case["case_id"]
    source_case = cases.get(case_id)
    if source_case is None:
        _fail(f"ARC case source is missing: {case_id}/{field}")
    if source_case["segment"] != workload_case["segment"]:
        _fail(f"ARC case source segment mismatch: {case_id}/{field}")
    value = {name: source_case[name] for name in value_fields}
    ref = workload_case[ref_field]
    expected_ref = _source_ref(
        f"{case_id}-{source_suffix}",
        f"{locator_root}/{case_id}/{field}",
        value,
    )
    if ref != expected_ref:
        _fail(f"ARC case source reference does not resolve exactly: {case_id}/{field}")
    return value


def _validate_configuration_equivalence(
    baseline: CandidateConfiguration,
    candidate: CandidateConfiguration,
) -> None:
    baseline_components = baseline.payload["components"]
    candidate_components = candidate.payload["components"]
    if set(baseline_components) != set(candidate_components):
        _fail("baseline and candidate component sets differ")
    for component in baseline_components:
        if component == "prompts_programs":
            if baseline_components[component] == candidate_components[component]:
                _fail("Trial 001 candidate must have exactly one distinct prompts_programs intervention")
        elif baseline_components[component] != candidate_components[component]:
            _fail(f"unauthorized Trial 001 candidate-component difference: {component}")
    for field in ("complexity", "maintainability", "known_limitations"):
        if baseline.payload[field] != candidate.payload[field]:
            _fail(f"baseline and candidate must match outside prompts_programs: {field}")


def validate_trial_bundle(root: Path) -> EngineeringTrial:
    if not root.is_dir():
        _fail(f"trial bundle directory does not exist: {root}")
    documents = _load_trial_documents(root)
    provenance = _expect_artifact(documents, "source", "irisx/source-provenance")
    solver_cases = _expect_artifact(documents, "solver_cases", "irisx/arc-agi-2-solver-cases")
    truth = _expect_artifact(documents, "truth", "irisx/arc-agi-2-evaluator-truth")
    specialization = _expect_artifact(documents, "specialization", "irisx/specialization-derivation")
    baseline_prompt = _expect_artifact(documents, "baseline_prompt", "irisx/prompt-program")
    candidate_prompt = _expect_artifact(documents, "candidate_prompt", "irisx/prompt-program")
    evaluator = _expect_artifact(documents, "evaluator", "irisx/evaluator-definition")
    envelope = _expect_artifact(documents, "envelope", "irisx/execution-envelope")
    profile = _expect_artifact(documents, "profile", "irisx/arc-agi-2-trial-profile")
    workload = _expect_contract(documents, "workload", WorkloadDefinition)
    requirements = _expect_contract(documents, "requirements", RequirementSet)
    specification = _expect_contract(documents, "specification", DomainSpecification)
    baseline = _expect_contract(documents, "baseline", CandidateConfiguration)
    candidate = _expect_contract(documents, "candidate", CandidateConfiguration)
    trial = _expect_contract(documents, "trial", EngineeringTrial)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    assert isinstance(specification, DomainSpecification)
    assert isinstance(baseline, CandidateConfiguration)
    assert isinstance(candidate, CandidateConfiguration)
    assert isinstance(trial, EngineeringTrial)

    if provenance["payload"].get("repository") != OFFICIAL_REPOSITORY or provenance["payload"].get("pinned_commit") != PINNED_COMMIT:
        _fail("trial source provenance does not bind the approved official repository and commit")
    splits = provenance["payload"].get("splits")
    if not isinstance(splits, dict) or splits.get("training", {}).get("task_count") != TRAINING_TASK_COUNT or splits.get("evaluation", {}).get("task_count") != EVALUATION_TASK_COUNT:
        _fail("trial source provenance has incomplete split identity")
    if evaluator["payload"] != ARC_EVALUATOR_PAYLOAD:
        _fail("ARC evaluator profile is stale or substituted")
    expected_material_ref = _source_ref(
        "arc-agi-2-official-source",
        TRIAL_FILES["source"],
        provenance["payload"],
    )
    if specification.payload["material_refs"] != [expected_material_ref]:
        _fail("Domain Specification material reference does not resolve to retained source provenance")
    validate_trial_bindings(trial, specification, workload, requirements, evaluator)
    if trial.payload["qualification_fixture"] is not False:
        _fail("ARC-AGI-2 Trial 001 must not claim to be the P1 qualification fixture")
    assert_binding(trial.payload["baseline_configuration_ref"], baseline, "trial.baseline_configuration_ref")
    if trial.payload["candidate_configuration_refs"] != [candidate.ref()]:
        _fail("Trial 001 must bind exactly the admitted specialized candidate")
    _validate_configuration_equivalence(baseline, candidate)
    if baseline.payload["components"].get("validation") != artifact_ref(evaluator):
        _fail("baseline validation component must bind the pinned evaluator")
    if baseline.payload["components"].get("prompts_programs") != artifact_ref(baseline_prompt):
        _fail("baseline prompt-program binding is stale")
    if candidate.payload["components"].get("prompts_programs") != artifact_ref(candidate_prompt):
        _fail("candidate prompt-program binding is stale")
    if candidate_prompt["payload"].get("derivation_ref") != artifact_ref(specialization):
        _fail("candidate prompt program does not bind the specialization derivation")
    if candidate_prompt["payload"].get("policy") != specialization["payload"].get("policy"):
        _fail("candidate prompt program does not contain the exact derived specialization policy")
    if specialization["payload"].get("authorized_split") != "public_training":
        _fail("specialization must derive only from the official public training split")
    if specialization["payload"].get("source_provenance_ref") != artifact_ref(provenance):
        _fail("specialization source provenance binding is stale")
    influences = specialization["payload"].get("influenced_files")
    if not isinstance(influences, list) or len(influences) != TRAINING_TASK_COUNT:
        _fail("specialization influence evidence must cover exactly the public training split")
    if any(not item.get("path", "").startswith("data/training/") for item in influences if isinstance(item, dict)):
        _fail("specialization influence evidence contains non-training material")
    source_files = {item["path"]: item["content_digest"] for item in provenance["payload"].get("files", []) if isinstance(item, dict) and "path" in item and "content_digest" in item}
    if any(source_files.get(item.get("path")) != item.get("content_digest") for item in influences if isinstance(item, dict)):
        _fail("specialization influence digest is stale")
    observations = specialization["payload"].get("observations")
    if not isinstance(observations, dict):
        _fail("specialization observations are missing")
    try:
        expected_policy = _policy_from_training_observations(observations)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("specialization observations are incomplete or invalid") from exc
    if specialization["payload"].get("policy") != expected_policy:
        _fail("specialization policy is not deterministically derived from its training observations")

    solver_map = _case_map(solver_cases, field="test_inputs")
    truth_map = _case_map(truth, field="expected_outputs")
    workload_map = {item["case_id"]: item for item in workload.payload["cases"]}
    if len(workload_map) != EVALUATION_TASK_COUNT or set(workload_map) != set(solver_map) or set(workload_map) != set(truth_map):
        _fail("workload, solver cases, and evaluator truth must represent exactly 120 identical task IDs")
    if workload.payload["frozen"] is not True or {item["segment"] for item in workload.payload["cases"]} != {SEGMENT}:
        _fail("ARC workload must be frozen in the public_eval segment")
    for case_id, workload_case in workload_map.items():
        solver_case = solver_map[case_id]
        truth_case = truth_map[case_id]
        if set(solver_case) != {"case_id", "segment", "demonstrations", "test_inputs"}:
            _fail(f"solver-facing case contains forbidden fields: {case_id}")
        if set(truth_case) != {"case_id", "segment", "expected_outputs"}:
            _fail(f"evaluator-only truth case has invalid fields: {case_id}")
        for pair_index, pair in enumerate(solver_case["demonstrations"]):
            _validate_pair(pair, f"solver case {case_id}.demonstrations[{pair_index}]")
        if not isinstance(solver_case["test_inputs"], list) or not solver_case["test_inputs"]:
            _fail(f"solver case has no test inputs: {case_id}")
        for test_index, grid in enumerate(solver_case["test_inputs"]):
            validate_grid(grid, f"solver case {case_id}.test_inputs[{test_index}]")
        if not isinstance(truth_case["expected_outputs"], list) or len(truth_case["expected_outputs"]) != len(solver_case["test_inputs"]):
            _fail(f"evaluator truth count does not match test inputs: {case_id}")
        for test_index, grid in enumerate(truth_case["expected_outputs"]):
            validate_grid(grid, f"truth case {case_id}.expected_outputs[{test_index}]")
        _resolve_arc_case_source(solver_cases, workload_case, "input")
        _resolve_arc_case_source(truth, workload_case, "expected")

    profile_payload = profile["payload"]
    expected_profile_refs = {
        "authority": {"path": DECISION_PATH, "content_digest": DECISION_SHA256},
        "source_provenance_ref": artifact_ref(provenance),
        "solver_cases_ref": artifact_ref(solver_cases),
        "evaluator_truth_ref": artifact_ref(truth),
        "specialization_derivation_ref": artifact_ref(specialization),
        "trial_ref": trial.ref(),
        "baseline_configuration_ref": baseline.ref(),
        "candidate_configuration_ref": candidate.ref(),
        "execution_envelope_ref": artifact_ref(envelope),
        "acceptance_delta": P2_ACCEPTANCE_DELTA,
        "run_authorization_ref": None,
    }
    if profile_payload != expected_profile_refs:
        _fail("Trial 001 profile is stale or substituted")
    envelope_payload = envelope["payload"]
    for field, expected in (
        ("solver_invocation_limit_per_configuration", EVALUATION_TASK_COUNT),
        ("attempt_limit_per_test_input", ATTEMPTS_PER_TEST_INPUT),
        ("timeout_policy", {"per_task_seconds": 300, "total_seconds": 36000}),
        ("determinism_policy", {"required": True, "random_seed": 0}),
        ("output_limits", {"max_grid_height": 30, "max_grid_width": 30, "cell_min": 0, "cell_max": 9}),
        ("network_enabled", False),
        ("provider_execution", False),
        ("credentials_allowed", False),
        ("maximum_external_cost_usd", 0),
    ):
        if envelope_payload.get(field) != expected:
            _fail(f"execution envelope has prohibited {field}")
    baseline_model = baseline.payload["components"].get("model")
    candidate_model = candidate.payload["components"].get("model")
    envelope_ref = artifact_ref(envelope)
    if baseline.payload["components"].get("workflow_control") != envelope_ref:
        _fail("baseline configuration does not bind the exact execution envelope")
    if candidate.payload["components"].get("workflow_control") != envelope_ref:
        _fail("candidate configuration does not bind the exact execution envelope")
    if baseline_model != candidate_model:
        _fail("baseline and candidate local model/solver bindings differ")
    if baseline_model is None:
        if baseline.payload["known_limitations"] != [UNBOUND_MODEL_LIMITATION]:
            _fail("unbound configurations must state the missing local model/solver limitation exactly")
        if "model" in documents or envelope_payload.get("model_solver_ref") is not None:
            _fail("unbound configurations must not carry a model descriptor or envelope binding")
    else:
        if UNBOUND_MODEL_LIMITATION in baseline.payload["known_limitations"]:
            _fail("bound configurations must not claim that the local model/solver is unbound")
        if "model" not in documents:
            _fail("bound configurations are missing the local solver descriptor")
        model = _expect_artifact(documents, "model", "irisx/local-solver-descriptor")
        if baseline_model != artifact_ref(model) or envelope_payload.get("model_solver_ref") != baseline_model:
            _fail("local solver descriptor, configurations, and execution envelope are not identically bound")
        asset_path = model["payload"].get("asset_path")
        asset_digest = model["payload"].get("asset_digest")
        if not isinstance(asset_path, str) or not isinstance(asset_digest, str):
            _fail("local solver descriptor asset identity is incomplete")
        asset = resolve_logical_path(root, asset_path, "local solver asset_path")
        if not asset.is_file() or asset.is_symlink() or digest_bytes(asset.read_bytes()) != asset_digest:
            _fail("local solver asset is missing, symbolic, or digest-mismatched")
    return trial


def solver_payload(root: Path) -> list[dict[str, Any]]:
    """Return only the solver-facing cases, never workload refs or truth."""

    validate_trial_bundle(root)
    artifact = validate_artifact(read_json(root / TRIAL_FILES["solver_cases"]), kind="irisx/arc-agi-2-solver-cases")
    return artifact["payload"]["cases"]


def _ref_key(ref: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(ref[field] for field in ("kind", "artifact_id", "version", "content_digest"))  # type: ignore[return-value]


def preflight_trial(root: Path, *, environment: dict[str, str] | None = None) -> dict[str, Any]:
    validate_trial_bundle(root)
    index = load_bundle(root)
    baseline = load_contract(root / TRIAL_FILES["baseline"], CandidateConfiguration)
    candidate = load_contract(root / TRIAL_FILES["candidate"], CandidateConfiguration)
    envelope = validate_artifact(read_json(root / TRIAL_FILES["envelope"]), kind="irisx/execution-envelope")
    profile = validate_artifact(read_json(root / TRIAL_FILES["profile"]), kind="irisx/arc-agi-2-trial-profile")
    assert isinstance(baseline, CandidateConfiguration)
    assert isinstance(candidate, CandidateConfiguration)
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    baseline_model = baseline.payload["components"].get("model")
    candidate_model = candidate.payload["components"].get("model")
    model_bound = baseline_model is not None and candidate_model is not None and baseline_model == candidate_model
    check("local-model-solver-binding", model_bound, "baseline and candidate must bind the same immutable local model/solver descriptor")
    model_valid = False
    if model_bound:
        document = resolve_ref(index, baseline_model, "configuration.components.model")
        if isinstance(document, dict):
            descriptor = validate_artifact(document, kind="irisx/local-solver-descriptor")
            payload = descriptor["payload"]
            asset_path = payload.get("asset_path") if isinstance(payload, dict) else None
            asset_digest = payload.get("asset_digest") if isinstance(payload, dict) else None
            if isinstance(asset_path, str) and isinstance(asset_digest, str):
                asset = resolve_logical_path(root, asset_path, "local solver asset_path")
                model_valid = asset.is_file() and not asset.is_symlink() and digest_bytes(asset.read_bytes()) == asset_digest
    check("local-model-solver-asset", model_valid, "descriptor asset must exist locally and match its immutable SHA-256 digest")
    envelope_model = envelope["payload"].get("model_solver_ref")
    check("execution-envelope-model-binding", model_bound and envelope_model == baseline_model, "execution envelope must bind the same local model/solver as both configurations")
    envelope_ref = artifact_ref(envelope)
    check(
        "configuration-envelope-binding",
        baseline.payload["components"].get("workflow_control") == envelope_ref
        and candidate.payload["components"].get("workflow_control") == envelope_ref,
        "baseline and candidate must each bind the exact same execution envelope",
    )
    hardware = envelope["payload"].get("hardware_identity")
    check("hardware-identity", isinstance(hardware, str) and bool(hardware.strip()), "immutable local hardware identity is required")
    check("attempt-limit", envelope["payload"].get("attempt_limit_per_test_input") == ATTEMPTS_PER_TEST_INPUT, "exactly two predictions are required per test input")
    check("solver-invocation-limit", envelope["payload"].get("solver_invocation_limit_per_configuration") == EVALUATION_TASK_COUNT, "baseline and candidate each receive exactly one bounded invocation per frozen task")
    check("network-disabled", envelope["payload"].get("network_enabled") is False, "trial execution must disable network use")
    check("provider-disabled", envelope["payload"].get("provider_execution") is False, "provider execution is prohibited")
    check("credentials-disabled", envelope["payload"].get("credentials_allowed") is False, "credential use is prohibited")
    check("external-cost-zero", envelope["payload"].get("maximum_external_cost_usd") == 0, "external paid-execution budget is USD 0")
    active_environment = os.environ if environment is None else environment
    present_credentials = sorted(name for name in PROVIDER_CREDENTIAL_NAMES if active_environment.get(name))
    check("provider-credentials-absent", not present_credentials, f"configured provider credential names: {present_credentials}")
    check(
        "separate-owner-run-authorization",
        False,
        (
            "Decision 0004 is not a run authorization; no later tracked owner decision is admitted by the "
            "current repository authority, and a trial-local artifact cannot authorize its own execution"
        ),
    )
    ready = all(item["passed"] for item in checks)
    return make_artifact(
        "irisx/preflight-report",
        "arc-agi-2-trial-001-preflight",
        "1.0.0",
        {
            "trial_ref": profile["payload"]["trial_ref"],
            "execution_envelope_ref": artifact_ref(envelope),
            "ready": ready,
            "checks": checks,
            "blockers": [item["check"] for item in checks if not item["passed"]],
        },
    )


def score_predictions(
    solver_cases: list[dict[str, Any]],
    truth_cases: list[dict[str, Any]],
    prediction_cases: Any,
) -> list[dict[str, Any]]:
    solver_map = {case["case_id"]: case for case in solver_cases}
    truth_map = {case["case_id"]: case for case in truth_cases}
    if not isinstance(prediction_cases, list):
        _fail("predictions.cases must be an array")
    prediction_map: dict[str, dict[str, Any]] = {}
    for position, case in enumerate(prediction_cases):
        if not isinstance(case, dict) or set(case) != {"case_id", "test_predictions"}:
            _fail(f"predictions.cases[{position}] must contain exactly case_id and test_predictions")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or case_id in prediction_map:
            _fail(f"predictions.cases[{position}].case_id is missing or duplicated")
        prediction_map[case_id] = case
    if set(prediction_map) != set(truth_map) or set(solver_map) != set(truth_map):
        _fail("prediction evidence must cover exactly every frozen workload case")

    outcomes: list[dict[str, Any]] = []
    for case_id in sorted(truth_map):
        expected_outputs = truth_map[case_id]["expected_outputs"]
        tests = prediction_map[case_id]["test_predictions"]
        if not isinstance(tests, list) or len(tests) != len(expected_outputs):
            _fail(f"prediction test-input coverage mismatch: {case_id}")
        by_index: dict[int, dict[str, Any]] = {}
        for test_position, test in enumerate(tests):
            if not isinstance(test, dict) or set(test) != {"test_index", "attempts"}:
                _fail(f"predictions {case_id}[{test_position}] must contain exactly test_index and attempts")
            test_index = test.get("test_index")
            if isinstance(test_index, bool) or not isinstance(test_index, int) or test_index in by_index:
                _fail(f"predictions {case_id}[{test_position}].test_index is invalid or duplicated")
            attempts = test.get("attempts")
            if not isinstance(attempts, list) or len(attempts) != ATTEMPTS_PER_TEST_INPUT:
                _fail(f"predictions {case_id}/{test_index} must contain exactly two attempts")
            for attempt_index, grid in enumerate(attempts):
                validate_grid(grid, f"predictions {case_id}/{test_index}/attempts[{attempt_index}]")
            by_index[test_index] = test
        if set(by_index) != set(range(len(expected_outputs))):
            _fail(f"prediction test indices are incomplete or hidden-extra for {case_id}")
        test_passes = [
            any(attempt == expected_outputs[test_index] for attempt in by_index[test_index]["attempts"])
            for test_index in range(len(expected_outputs))
        ]
        passed = all(test_passes)
        outcomes.append(
            {
                "case_id": case_id,
                "segment": SEGMENT,
                "passed": passed,
                "critical_failure": False,
                "score": 1 if passed else 0,
                "detail": f"{sum(test_passes)}/{len(test_passes)} test inputs matched exactly within two attempts",
            }
        )
    return outcomes


def _observed(value: int | float, unit: str) -> dict[str, Any]:
    return {"state": "observed", "value": value, "unit": unit}


def _require_authorized_execution(trial_root: Path) -> None:
    report = preflight_trial(trial_root, environment={})
    if report["payload"].get("ready") is not True:
        blockers = ", ".join(report["payload"].get("blockers", []))
        _fail(
            "ARC-AGI-2 execution evidence is not admissible before an exact later owner authorization "
            f"and passed preflight; blockers: {blockers}"
        )


def build_evaluation_result(
    trial_root: Path,
    predictions: dict[str, Any],
    observations: dict[str, Any],
    *,
    result_id: str,
) -> EvaluationResult:
    """Admit result evidence only after the repository recognizes an authorized run."""

    _require_authorized_execution(trial_root)
    return _build_evaluation_result_from_structural_evidence(
        trial_root,
        predictions,
        observations,
        result_id=result_id,
    )


def _build_evaluation_result_from_structural_evidence(
    trial_root: Path,
    predictions: dict[str, Any],
    observations: dict[str, Any],
    *,
    result_id: str,
) -> EvaluationResult:
    """Score structural fixtures; callers must not treat this as admitted run evidence."""

    validate_trial_bundle(trial_root)
    predictions = validate_artifact(predictions, kind="irisx/arc-agi-2-predictions")
    observations = validate_artifact(observations, kind="irisx/trial-observations")
    trial = load_contract(trial_root / TRIAL_FILES["trial"], EngineeringTrial)
    workload = load_contract(trial_root / TRIAL_FILES["workload"], WorkloadDefinition)
    evaluator = validate_artifact(read_json(trial_root / TRIAL_FILES["evaluator"]), kind="irisx/evaluator-definition")
    solver = validate_artifact(read_json(trial_root / TRIAL_FILES["solver_cases"]), kind="irisx/arc-agi-2-solver-cases")
    truth = validate_artifact(read_json(trial_root / TRIAL_FILES["truth"]), kind="irisx/arc-agi-2-evaluator-truth")
    assert isinstance(trial, EngineeringTrial)
    assert isinstance(workload, WorkloadDefinition)
    payload = predictions["payload"]
    if payload.get("trial_ref") != trial.ref() or payload.get("workload_ref") != workload.ref() or payload.get("evaluator_ref") != artifact_ref(evaluator):
        _fail("prediction evidence has stale trial, workload, or evaluator identity")
    configuration_ref = payload.get("configuration_ref")
    permitted = [trial.payload["baseline_configuration_ref"], *trial.payload["candidate_configuration_refs"]]
    if configuration_ref not in permitted:
        _fail("prediction evidence configuration is outside Trial 001")
    observation_payload = observations["payload"]
    if observation_payload.get("configuration_ref") != configuration_ref:
        _fail("trial observations do not bind the prediction configuration")
    expected_observations = {
        "evaluation_leak_events": ("count", int),
        "network_calls": ("count", int),
        "provider_calls": ("count", int),
        "monetary_cost": ("usd", (int, float)),
        "identity_binding_failures": ("count", int),
    }
    metric_observations: dict[str, Any] = {}
    for name, (unit, expected_type) in expected_observations.items():
        value = observation_payload.get(name)
        if isinstance(value, bool) or not isinstance(value, expected_type) or value < 0:
            _fail(f"trial observations {name} is missing or invalid")
        metric_observations[name] = _observed(value, unit)
    outcomes = score_predictions(solver["payload"]["cases"], truth["payload"]["cases"], payload.get("cases"))
    accuracy = sum(item["passed"] for item in outcomes) / len(outcomes)
    metrics = {
        "accuracy": _observed(accuracy, "ratio"),
        f"accuracy.{SEGMENT}": _observed(accuracy, "ratio"),
        "critical_failures": _observed(0, "count"),
        "malformed_or_missing_cases": _observed(0, "count"),
        "workload_cases": _observed(len(outcomes), "count"),
        **metric_observations,
    }
    resource_use = {
        "network_calls": metric_observations["network_calls"],
        "provider_calls": metric_observations["provider_calls"],
        "monetary_cost": metric_observations["monetary_cost"],
        "runtime_seconds": observation_payload.get("runtime_seconds", {"state": "unknown", "value": None, "unit": "seconds"}),
        "peak_memory_mb": observation_payload.get("peak_memory_mb", {"state": "unknown", "value": None, "unit": "mb"}),
    }
    return EvaluationResult(
        result_id,
        "1.0.0",
        {
            "trial_ref": trial.ref(),
            "workload_ref": workload.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "configuration_ref": configuration_ref,
            "cases": outcomes,
            "metrics": metrics,
            "resource_use": resource_use,
            "known_limitations": P2_LIMITATIONS,
        },
    )


def _run_trial_root(run_root: Path) -> Path:
    trial_root = run_root / "trial"
    if not trial_root.is_dir():
        _fail(f"run directory must contain a trial/ bundle: {run_root}")
    return trial_root


def _load_run_evidence(run_root: Path) -> tuple[
    EngineeringTrial,
    WorkloadDefinition,
    RequirementSet,
    CandidateConfiguration,
    CandidateConfiguration,
    EvaluationResult,
    EvaluationResult,
]:
    trial_root = _run_trial_root(run_root)
    validate_trial_bundle(trial_root)
    trial = load_contract(trial_root / TRIAL_FILES["trial"], EngineeringTrial)
    workload = load_contract(trial_root / TRIAL_FILES["workload"], WorkloadDefinition)
    requirements = load_contract(trial_root / TRIAL_FILES["requirements"], RequirementSet)
    baseline = load_contract(trial_root / TRIAL_FILES["baseline"], CandidateConfiguration)
    candidate = load_contract(trial_root / TRIAL_FILES["candidate"], CandidateConfiguration)
    assert isinstance(trial, EngineeringTrial)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    assert isinstance(baseline, CandidateConfiguration)
    assert isinstance(candidate, CandidateConfiguration)
    pairs = (
        ("baseline", baseline, "arc-agi-2-trial-001-baseline-result"),
        ("candidate", candidate, "arc-agi-2-trial-001-candidate-result"),
    )
    results: list[EvaluationResult] = []
    for name, configuration, result_id in pairs:
        predictions = validate_artifact(read_json(run_root / "predictions" / f"{name}.json"), kind="irisx/arc-agi-2-predictions")
        observations = validate_artifact(read_json(run_root / "observations" / f"{name}.json"), kind="irisx/trial-observations")
        if predictions["payload"].get("configuration_ref") != configuration.ref():
            _fail(f"{name} predictions bind the wrong configuration")
        recomputed = build_evaluation_result(trial_root, predictions, observations, result_id=result_id)
        stored = load_contract(run_root / "results" / f"{name}.json", EvaluationResult)
        assert isinstance(stored, EvaluationResult)
        if stored.to_dict() != recomputed.to_dict():
            _fail(f"{name} EvaluationResult does not match independently recomputed prediction evidence")
        validate_result_evidence(stored, workload)
        results.append(stored)
    return trial, workload, requirements, baseline, candidate, results[0], results[1]


def validate_run_results(run_root: Path) -> tuple[EvaluationResult, EvaluationResult]:
    *_, baseline_result, candidate_result = _load_run_evidence(run_root)
    return baseline_result, candidate_result


def _decision_semantics(decision: SelectionDecision) -> dict[str, Any]:
    fields = (
        "outcome",
        "trial_ref",
        "workload_ref",
        "evaluator_ref",
        "baseline_result_ref",
        "considered_result_refs",
        "eligible_result_refs",
        "selected_configuration_ref",
        "selected_result_ref",
        "tie_break_rule",
    )
    return {field: decision.payload[field] for field in fields}


def build_p2_acceptance(
    trial: EngineeringTrial,
    workload: WorkloadDefinition,
    requirements: RequirementSet,
    baseline_result: EvaluationResult,
    candidate_result: EvaluationResult,
    decision: SelectionDecision,
) -> dict[str, Any]:
    validate_result_evidence(baseline_result, workload)
    validate_result_evidence(candidate_result, workload)
    baseline_score = baseline_result.payload["metrics"]["accuracy"]["value"]
    candidate_score = candidate_result.payload["metrics"]["accuracy"]["value"]
    baseline_passed = sum(case["passed"] for case in baseline_result.payload["cases"])
    candidate_passed = sum(case["passed"] for case in candidate_result.payload["cases"])
    task_improvement = candidate_passed - baseline_passed
    improvement = task_improvement / len(workload.payload["cases"])
    hard_pass = satisfies_hard_requirements(candidate_result, requirements, workload)
    selected_candidate = (
        decision.payload["outcome"] == "promote"
        and decision.payload["selected_result_ref"] == candidate_result.ref()
        and decision.payload["selected_configuration_ref"] == candidate_result.payload["configuration_ref"]
    )
    accepted = hard_pass and selected_candidate and task_improvement >= P2_ACCEPTANCE_TASK_DELTA
    if accepted:
        reason = "Candidate passes every hard requirement and improves ARC accuracy by at least 0.05 absolute."
    elif not hard_pass:
        reason = "Candidate fails or lacks at least one hard requirement."
    elif task_improvement < P2_ACCEPTANCE_TASK_DELTA:
        reason = "Valid candidate improvement is below the 0.05 P2 acceptance threshold."
    else:
        reason = "Generic selection evidence does not promote the admitted candidate."
    return make_artifact(
        "irisx/p2-acceptance",
        "arc-agi-2-trial-001-acceptance",
        "1.0.0",
        {
            "trial_ref": trial.ref(),
            "baseline_result_ref": baseline_result.ref(),
            "candidate_result_ref": candidate_result.ref(),
            "selection_decision_ref": decision.ref(),
            "baseline_arc_score": baseline_score,
            "candidate_arc_score": candidate_score,
            "baseline_passed_tasks": baseline_passed,
            "candidate_passed_tasks": candidate_passed,
            "task_improvement": task_improvement,
            "required_task_improvement": P2_ACCEPTANCE_TASK_DELTA,
            "absolute_improvement": improvement,
            "required_improvement": P2_ACCEPTANCE_DELTA,
            "all_hard_requirements_pass": hard_pass,
            "generic_selection_promotes_candidate": selected_candidate,
            "accepted": accepted,
            "package_eligible": accepted,
            "reason": reason,
        },
    )


def select_run(run_root: Path, *, write: bool = True) -> tuple[SelectionDecision, dict[str, Any]]:
    trial, workload, requirements, baseline, candidate, baseline_result, candidate_result = _load_run_evidence(run_root)
    decision = select_configuration(
        trial,
        workload,
        requirements,
        baseline_result,
        [candidate_result],
        {baseline.content_digest: baseline, candidate.content_digest: candidate},
        decision_id="arc-agi-2-trial-001-selection",
    )
    acceptance = build_p2_acceptance(trial, workload, requirements, baseline_result, candidate_result, decision)
    if write:
        _write_or_validate(run_root / "selection.json", decision.to_dict())
        _write_or_validate(run_root / "acceptance.json", acceptance)
    return decision, acceptance


def _write_or_validate(path: Path, value: Any) -> None:
    if path.exists():
        if read_json(path) != value:
            _fail(f"existing evidence is stale or inconsistent and will not be overwritten: {path}")
        return
    write_json(path, value)


def validate_run_selection(run_root: Path) -> tuple[SelectionDecision, dict[str, Any]]:
    expected_decision, expected_acceptance = select_run(run_root, write=False)
    decision = load_contract(run_root / "selection.json", SelectionDecision)
    assert isinstance(decision, SelectionDecision)
    if _decision_semantics(decision) != _decision_semantics(expected_decision):
        _fail("selection decision does not match independently recomputed generic P1 selection")
    acceptance = validate_artifact(read_json(run_root / "acceptance.json"), kind="irisx/p2-acceptance")
    recomputed = build_p2_acceptance(
        load_contract(_run_trial_root(run_root) / TRIAL_FILES["trial"], EngineeringTrial),
        load_contract(_run_trial_root(run_root) / TRIAL_FILES["workload"], WorkloadDefinition),
        load_contract(_run_trial_root(run_root) / TRIAL_FILES["requirements"], RequirementSet),
        load_contract(run_root / "results" / "baseline.json", EvaluationResult),
        load_contract(run_root / "results" / "candidate.json", EvaluationResult),
        decision,
    )
    if acceptance != recomputed or acceptance != expected_acceptance:
        _fail("P2 acceptance evidence does not match independently recomputed results")
    return decision, acceptance


def _copy_closed_file(source: Path, destination: Path) -> None:
    if not source.is_file() or source.is_symlink():
        _fail(f"package source file is missing or invalid: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def build_p2_package(run_root: Path, output: Path) -> DomainPackageManifest:
    decision, acceptance = validate_run_selection(run_root)
    if acceptance["payload"].get("package_eligible") is not True:
        _fail("P2 Domain Package is ineligible because the five-point acceptance gate did not pass")
    preflight = validate_artifact(read_json(run_root / "preflight.json"), kind="irisx/preflight-report")
    recomputed_preflight = preflight_trial(_run_trial_root(run_root), environment={})
    if preflight != recomputed_preflight or preflight["payload"].get("ready") is not True:
        _fail("P2 Domain Package requires a passed immutable preflight report")
    trial_root = _run_trial_root(run_root)
    trial, workload, requirements, _, candidate, _, candidate_result = _load_run_evidence(run_root)
    specification = load_contract(trial_root / TRIAL_FILES["specification"], DomainSpecification)
    evaluator = validate_artifact(read_json(trial_root / TRIAL_FILES["evaluator"]), kind="irisx/evaluator-definition")
    assert isinstance(specification, DomainSpecification)
    model_ref = candidate.payload["components"].get("model")
    if model_ref is None:
        _fail("P2 Domain Package requires the bound local solver descriptor")
    index = load_bundle(trial_root)
    descriptor_document = resolve_ref(index, model_ref, "candidate.components.model")
    if not isinstance(descriptor_document, dict):
        _fail("local solver descriptor must be a supporting artifact")
    descriptor = validate_artifact(descriptor_document, kind="irisx/local-solver-descriptor")
    asset_relative = descriptor["payload"].get("asset_path")
    if not isinstance(asset_relative, str):
        _fail("local solver descriptor asset_path is missing")
    asset_source = resolve_logical_path(trial_root, asset_relative, "local solver asset_path")
    if digest_bytes(asset_source.read_bytes()) != descriptor["payload"].get("asset_digest"):
        _fail("local solver asset digest mismatch")

    _ensure_empty(output)
    source_files: dict[str, Path] = {}
    for path in sorted(trial_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            source_files[f"trial/{path.relative_to(trial_root).as_posix()}"] = path
    for directory in ("predictions", "observations", "results"):
        for path in sorted((run_root / directory).glob("*.json"), key=lambda item: item.name):
            source_files[f"evidence/{directory}/{path.name}"] = path
    for name in ("selection.json", "acceptance.json", "preflight.json"):
        source_files[f"evidence/{name}"] = run_root / name
    for relative, source in source_files.items():
        _copy_closed_file(source, output / relative)

    deployment = make_artifact(
        "irisx/deployment-metadata",
        "arc-agi-2-trial-001-offline-solver-package",
        "1.0.0",
        {
            "status": "self-contained-offline-research-solver",
            "deployable": True,
            "configuration_ref": candidate.ref(),
            "solver_descriptor_ref": artifact_ref(descriptor),
            "solver_asset_path": f"trial/{asset_relative}",
            "network_required": False,
        },
    )
    limitations = make_artifact(
        "irisx/known-limitations",
        "arc-agi-2-trial-001-known-limitations",
        "1.0.0",
        {"limitations": P2_LIMITATIONS},
    )
    write_artifact(output / "deployment" / "metadata.json", deployment)
    write_artifact(output / "known-limitations.json", limitations)
    artifact_entries: list[dict[str, Any]] = []
    for path in sorted(output.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            relative = path.relative_to(output).as_posix()
            kind = (
                document_ref(load_document(path))["kind"]
                if path.suffix == ".json"
                else "irisx/local-solver-asset"
            )
            artifact_entries.append(
                {"path": relative, "kind": kind, "content_digest": digest_bytes(path.read_bytes())}
            )
    manifest = DomainPackageManifest(
        "arc-agi-2-trial-001-domain-package",
        "1.0.0",
        {
            "domain_specification_ref": specification.ref(),
            "workload_ref": workload.ref(),
            "requirement_set_ref": requirements.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "selected_configuration_ref": candidate.ref(),
            "measured_result_ref": candidate_result.ref(),
            "selection_decision_ref": decision.ref(),
            "deployment_metadata_ref": artifact_ref(deployment),
            "known_limitations": P2_LIMITATIONS,
            "artifacts": artifact_entries,
        },
    )
    manifest.write(output / "manifest.json")
    verify_p2_package(output)
    return manifest


def verify_p2_package(root: Path) -> DomainPackageManifest:
    if not root.is_dir():
        _fail(f"package directory does not exist: {root}")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        _fail("P2 package manifest is missing or invalid")
    manifest = load_contract(manifest_path, DomainPackageManifest)
    assert isinstance(manifest, DomainPackageManifest)
    if manifest.artifact_id != "arc-agi-2-trial-001-domain-package":
        _fail("not an ARC-AGI-2 Trial 001 package")
    declared = {entry["path"]: entry for entry in manifest.payload["artifacts"]}
    all_paths = list(root.rglob("*"))
    if any(path.is_symlink() for path in all_paths):
        _fail("P2 Domain Package must not contain symbolic links")
    actual = {path.relative_to(root).as_posix() for path in all_paths if path.is_file()}
    expected = set(declared) | {"manifest.json"}
    if actual != expected:
        _fail(f"P2 package membership mismatch; missing={sorted(expected - actual)} unexpected={sorted(actual - expected)}")
    for relative, entry in declared.items():
        path = resolve_logical_path(root, relative, f"package artifact {relative}")
        if digest_bytes(path.read_bytes()) != entry["content_digest"]:
            _fail(f"P2 package artifact digest mismatch: {relative}")
        actual_kind = (
            document_ref(load_document(path))["kind"]
            if path.suffix == ".json"
            else "irisx/local-solver-asset"
        )
        if actual_kind != entry["kind"]:
            _fail(f"P2 package artifact kind mismatch: {relative}")

    package_trial = root / "trial"
    validate_trial_bundle(package_trial)
    # Reconstruct only an in-memory-compatible view by using the package paths
    # directly; no files are created inside the verified closed world.
    trial = load_contract(package_trial / TRIAL_FILES["trial"], EngineeringTrial)
    workload = load_contract(package_trial / TRIAL_FILES["workload"], WorkloadDefinition)
    requirements = load_contract(package_trial / TRIAL_FILES["requirements"], RequirementSet)
    candidate = load_contract(package_trial / TRIAL_FILES["candidate"], CandidateConfiguration)
    specification = load_contract(package_trial / TRIAL_FILES["specification"], DomainSpecification)
    evaluator = validate_artifact(read_json(package_trial / TRIAL_FILES["evaluator"]), kind="irisx/evaluator-definition")
    decision = load_contract(root / "evidence" / "selection.json", SelectionDecision)
    acceptance = validate_artifact(read_json(root / "evidence" / "acceptance.json"), kind="irisx/p2-acceptance")
    preflight = validate_artifact(read_json(root / "evidence" / "preflight.json"), kind="irisx/preflight-report")
    baseline_result = load_contract(root / "evidence" / "results" / "baseline.json", EvaluationResult)
    candidate_result = load_contract(root / "evidence" / "results" / "candidate.json", EvaluationResult)
    assert isinstance(trial, EngineeringTrial)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    assert isinstance(candidate, CandidateConfiguration)
    assert isinstance(specification, DomainSpecification)
    assert isinstance(decision, SelectionDecision)
    assert isinstance(baseline_result, EvaluationResult)
    assert isinstance(candidate_result, EvaluationResult)
    for name, result in (("baseline", baseline_result), ("candidate", candidate_result)):
        predictions = validate_artifact(read_json(root / "evidence" / "predictions" / f"{name}.json"), kind="irisx/arc-agi-2-predictions")
        observations = validate_artifact(read_json(root / "evidence" / "observations" / f"{name}.json"), kind="irisx/trial-observations")
        recomputed = build_evaluation_result(package_trial, predictions, observations, result_id=result.artifact_id)
        if recomputed.to_dict() != result.to_dict():
            _fail(f"packaged {name} result does not match predictions and evaluator truth")
    baseline = load_contract(package_trial / TRIAL_FILES["baseline"], CandidateConfiguration)
    assert isinstance(baseline, CandidateConfiguration)
    recomputed_decision = select_configuration(
        trial,
        workload,
        requirements,
        baseline_result,
        [candidate_result],
        {baseline.content_digest: baseline, candidate.content_digest: candidate},
        decision_id=decision.artifact_id,
    )
    if _decision_semantics(decision) != _decision_semantics(recomputed_decision):
        _fail("packaged generic selection does not match recomputed evidence")
    recomputed_acceptance = build_p2_acceptance(trial, workload, requirements, baseline_result, candidate_result, decision)
    if acceptance != recomputed_acceptance or acceptance["payload"].get("package_eligible") is not True:
        _fail("packaged P2 acceptance is false, stale, or inconsistent")
    recomputed_preflight = preflight_trial(package_trial, environment={})
    if preflight != recomputed_preflight or preflight["payload"].get("ready") is not True:
        _fail("packaged preflight is false, stale, or inconsistent")
    deployment = validate_artifact(read_json(root / "deployment" / "metadata.json"), kind="irisx/deployment-metadata")
    limitations = validate_artifact(read_json(root / "known-limitations.json"), kind="irisx/known-limitations")
    descriptor_ref = candidate.payload["components"].get("model")
    if descriptor_ref is None:
        _fail("packaged candidate has no local solver descriptor")
    trial_index = load_bundle(package_trial)
    descriptor_document = resolve_ref(trial_index, descriptor_ref, "candidate.components.model")
    if not isinstance(descriptor_document, dict):
        _fail("packaged local solver descriptor has invalid type")
    descriptor = validate_artifact(descriptor_document, kind="irisx/local-solver-descriptor")
    asset_path = descriptor["payload"].get("asset_path")
    if not isinstance(asset_path, str):
        _fail("packaged local solver asset path is missing")
    asset = resolve_logical_path(package_trial, asset_path, "packaged solver asset_path")
    if not asset.is_file() or digest_bytes(asset.read_bytes()) != descriptor["payload"].get("asset_digest"):
        _fail("packaged opaque local solver asset is missing or corrupt")
    expected_deployment = {
        "status": "self-contained-offline-research-solver",
        "deployable": True,
        "configuration_ref": candidate.ref(),
        "solver_descriptor_ref": artifact_ref(descriptor),
        "solver_asset_path": f"trial/{asset_path}",
        "network_required": False,
    }
    if deployment["payload"] != expected_deployment:
        _fail("packaged deployment metadata is stale or substituted")
    if limitations["payload"] != {"limitations": P2_LIMITATIONS} or manifest.payload["known_limitations"] != P2_LIMITATIONS:
        _fail("P2 package must state all four Decision 0004 limitations exactly")
    bindings = (
        ("domain_specification_ref", specification.ref()),
        ("workload_ref", workload.ref()),
        ("requirement_set_ref", requirements.ref()),
        ("evaluator_ref", artifact_ref(evaluator)),
        ("selected_configuration_ref", candidate.ref()),
        ("measured_result_ref", candidate_result.ref()),
        ("selection_decision_ref", decision.ref()),
        ("deployment_metadata_ref", artifact_ref(deployment)),
    )
    for field, expected_ref in bindings:
        if manifest.payload[field] != expected_ref:
            _fail(f"P2 package manifest has stale {field}")
    return manifest

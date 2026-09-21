"""Decision-0006 raw-model Kaggle handoff, quarantine import, and preflight."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from typing import Any
import zipfile

from .arc_agi2 import (
    ARC_COMMIT,
    ARC_REPOSITORY,
    MODEL_LICENSE,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    PUBLIC_EVALUATION_COUNT,
    p2_acceptance,
    score_predictions,
    validate_predictions,
    validate_task,
    validate_trial_bundle,
)
from .artifacts import artifact_ref, make_artifact, validate_artifact, write_artifact
from .canonical import canonical_bytes, digest_bytes, read_json, write_json
from .contracts import CandidateConfiguration, EngineeringTrial, RequirementSet, WorkloadDefinition, load_contract
from .engine import select_configuration
from .errors import ValidationError
from .kaggle_runner_v4 import CHECKPOINT_POLICY
from .kaggle_runner_v5 import (
    BENCHMARK_INVOCATION_LIMIT,
    BENCHMARK_RESULT_KIND,
    CHECKPOINT_POLICY as COMPLETION_BENCHMARK_POLICY,
    _identity as _benchmark_identity,
    _progress_events as _benchmark_progress_events,
    _tasks as _benchmark_tasks,
    _validate_state as _validate_benchmark_state,
)
from .transport import (
    RESULT_LIMITS,
    TRIAL_LIMITS,
    digest_path,
    extract_verified_zip,
    verify_zip,
    write_zip,
)


TRIAL_PACKAGE_KIND = "irisx/arc-agi-2-trial-input"
RESULT_PACKAGE_KIND = "irisx/arc-agi-2-result-package"
MODEL_REMOTE = "https://huggingface.co/Qwen/Qwen3.8-27B"

OUTBOUND_PATHS = {
    "cases/solver-cases.json",
    "configurations/baseline.json",
    "configurations/candidate.json",
    "components/baseline-prompts.json",
    "components/candidate-prompts.json",
    "components/specialization.json",
    "bindings/model.json",
    "bindings/model-source.json",
    "bindings/model-source-provenance.json",
    "bindings/execution-envelope.json",
    "bindings/run.json",
    "runtime/dependencies.json",
    "runtime/runner.py",
    "runtime/notebook.ipynb",
    "runtime/wheels.json",
}
CHECKPOINT_OUTBOUND_PATHS = OUTBOUND_PATHS | {"runtime/runner_core.py"}
RUNTIME_WHEEL_FILENAMES = (
    "accelerate-1.10.1-py3-none-any.whl",
    "annotated_doc-0.0.5-py3-none-any.whl",
    "anyio-4.15.1-py3-none-any.whl",
    "certifi-2026.7.22-py3-none-any.whl",
    "click-8.5.0-py3-none-any.whl",
    "colorama-0.4.6-py2.py3-none-any.whl",
    "filelock-4.0.1-py3-none-any.whl",
    "fsspec-2026.9.0-py3-none-any.whl",
    "h11-0.16.0-py3-none-any.whl",
    "hf_xet-1.6.0-cp38-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
    "httpcore-1.0.9-py3-none-any.whl",
    "httpx-0.28.1-py3-none-any.whl",
    "huggingface_hub-1.32.0-py3-none-any.whl",
    "idna-3.20-py3-none-any.whl",
    "markdown_it_py-4.2.0-py3-none-any.whl",
    "mdurl-0.1.2-py3-none-any.whl",
    "numpy-2.2.6-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "packaging-26.3-py3-none-any.whl",
    "psutil-7.1.0-cp36-abi3-manylinux_2_12_x86_64.manylinux2010_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "pygments-2.21.0-py3-none-any.whl",
    "pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
    "regex-2026.9.10-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
    "rich-15.0.0-py3-none-any.whl",
    "safetensors-0.8.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "shellingham-1.5.4-py2.py3-none-any.whl",
    "tokenizers-0.22.2-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "tqdm-4.70.1-py3-none-any.whl",
    "transformers-5.8.1-py3-none-any.whl",
    "typer-0.27.2-py3-none-any.whl",
    "typing_extensions-4.16.0-py3-none-any.whl",
)
RESULT_PATHS = {
    "predictions/baseline.json",
    "predictions/candidate.json",
    "observations/execution.json",
    "logs/runner.json",
}
BENCHMARK_RESULT_SHAPE = [
    "benchmark/result.json",
    "bindings/run.json",
    "checkpoint/checkpoint.json",
    "logs/progress.jsonl",
    "observations/execution.json",
    "outputs/<four-sequence-bound-raw-text-files>",
]
FORBIDDEN_OUTBOUND_KEYS = {
    "expected",
    "expected_ref",
    "expected_output",
    "expected_output_digest",
    "score",
    "scores",
    "correct",
    "correctness",
    "feedback",
    "evaluation_result",
    "selection_decision",
    "domain_package",
}


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


def _normalize_remote(value: str) -> str:
    return value.lower().removesuffix("/").removesuffix(".git")


def _json_bytes(value: Any) -> bytes:
    return canonical_bytes(value, newline=True)


def _json_from_bytes(data: bytes, path: str) -> Any:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: invalid UTF-8 JSON: {exc}") from exc
    if _json_bytes(value) != data:
        raise ValidationError(f"{path}: JSON must use canonical serialization")
    return value


def outbound_manifest_digest(manifest: dict[str, Any]) -> str:
    """Identify extracted trial content independently of its ZIP container bytes."""

    return digest_bytes(_json_bytes(manifest))


def _regular_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if ".git" in path.relative_to(root).parts:
            continue
        if path.relative_to(root).as_posix() == "dataset-metadata.json":
            continue
        if path.is_symlink():
            raise ValidationError(f"symbolic links are prohibited in model sources: {path}")
        if path.is_file():
            paths.append(path)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def model_source_layout(root: Path) -> tuple[Path, Path]:
    """Resolve either a materializer root or a directly unpacked model root."""

    nested = root / "source"
    if nested.is_dir():
        return nested, root / "provenance.json"
    return root, root.parent / f"{root.name}-provenance.json"


def create_model_provenance(source: Path, output: Path, *, require_git_identity: bool = True) -> dict[str, Any]:
    """Record the exact official model revision and every local source byte."""

    if not source.is_dir():
        raise ValidationError(f"model source directory does not exist: {source}")
    if require_git_identity:
        if _normalize_remote(_git(source, "remote", "get-url", "origin")) != _normalize_remote(MODEL_REMOTE):
            raise ValidationError("model source is not the selected official Qwen repository")
        if _git(source, "rev-parse", "HEAD") != MODEL_REVISION:
            raise ValidationError("model source is not at the selected immutable revision")
        if _git(source, "status", "--porcelain", "--untracked-files=no"):
            raise ValidationError("model source contains modified tracked files")
    files = _regular_files(source)
    relative = {path.relative_to(source).as_posix(): path for path in files}
    if "config.json" not in relative:
        raise ValidationError("model source is missing config.json")
    license_paths = [path for logical, path in relative.items() if logical.lower() in {"license", "license.md", "readme.md"}]
    license_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in license_paths).lower()
    if "apache" not in license_text and "license: apache-2.0" not in license_text:
        raise ValidationError("model source does not expose the selected Apache-2.0 license metadata")
    for path in files:
        with path.open("rb") as stream:
            prefix = stream.read(128)
        if prefix.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise ValidationError(f"model source contains an unresolved Git LFS pointer: {path.name}")
    entries = [
        {
            "path": path.relative_to(source).as_posix(),
            "byte_size": path.stat().st_size,
            "content_digest": digest_path(path),
        }
        for path in files
    ]
    provenance = make_artifact(
        "irisx/model-source-provenance",
        "qwen3.8-27b-official-source",
        "1.0.0",
        {
            "repository": MODEL_REPOSITORY,
            "remote": MODEL_REMOTE,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "weights_frozen": True,
            "files": entries,
        },
    )
    write_artifact(output, provenance)
    return provenance


def materialize_model(output: Path) -> dict[str, Any]:
    """Deliberately acquire the one selected model revision; never called by validation."""

    if output.exists() and any(output.iterdir()):
        raise ValidationError(f"model output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    source = output / "source"
    completed = subprocess.run(
        ["git", "clone", "--no-checkout", MODEL_REMOTE, str(source)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise ValidationError(f"official model clone failed: {completed.stderr.strip()}")
    _git(source, "checkout", "--detach", MODEL_REVISION)
    return create_model_provenance(source, output / "provenance.json")


def validate_model_source(root: Path, *, require_git_identity: bool = False) -> dict[str, Any]:
    source, provenance_path = model_source_layout(root)
    provenance = validate_model_provenance(read_json(provenance_path))
    payload = provenance["payload"]
    identity = {
        "repository": MODEL_REPOSITORY,
        "remote": MODEL_REMOTE,
        "revision": MODEL_REVISION,
        "license": MODEL_LICENSE,
        "weights_frozen": True,
    }
    if any(payload.get(field) != expected for field, expected in identity.items()):
        raise ValidationError("model source provenance identity is stale or substituted")
    if require_git_identity:
        if _normalize_remote(_git(source, "remote", "get-url", "origin")) != _normalize_remote(MODEL_REMOTE):
            raise ValidationError("model source remote is stale or substituted")
        if _git(source, "rev-parse", "HEAD") != MODEL_REVISION:
            raise ValidationError("model source revision is stale or substituted")
    entries = payload["files"]
    declared = {entry.get("path"): entry for entry in entries if isinstance(entry, dict)}
    actual = {path.relative_to(source).as_posix(): path for path in _regular_files(source)}
    if len(declared) != len(entries) or set(declared) != set(actual):
        raise ValidationError("model source provenance does not exactly cover source files")
    for logical, path in actual.items():
        size = path.stat().st_size
        if declared[logical] != {
            "path": logical,
            "byte_size": size,
            "content_digest": digest_path(path),
        }:
            raise ValidationError(f"model source digest mismatch: {logical}")
    return provenance


def validate_model_provenance(value: Any) -> dict[str, Any]:
    """Validate the portable identity and closed-world file map for raw model bytes."""

    provenance = validate_artifact(value, kind="irisx/model-source-provenance")
    payload = provenance["payload"]
    identity = {
        "repository": MODEL_REPOSITORY,
        "remote": MODEL_REMOTE,
        "revision": MODEL_REVISION,
        "license": MODEL_LICENSE,
        "weights_frozen": True,
    }
    if any(payload.get(field) != expected for field, expected in identity.items()):
        raise ValidationError("model source provenance identity is stale or substituted")
    entries = payload.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("model source provenance files must be a non-empty array")
    declared: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "byte_size", "content_digest"}:
            raise ValidationError("model source provenance file entry is malformed")
        logical = entry["path"]
        if (
            not isinstance(logical, str)
            or not logical
            or "\\" in logical
            or logical.startswith("/")
            or any(part in {"", ".", ".."} for part in logical.split("/"))
            or logical in declared
        ):
            raise ValidationError("model source provenance contains an unsafe or duplicate path")
        if isinstance(entry["byte_size"], bool) or not isinstance(entry["byte_size"], int) or entry["byte_size"] < 0:
            raise ValidationError(f"model source provenance byte size is invalid: {logical}")
        if not isinstance(entry["content_digest"], str) or not entry["content_digest"].startswith("sha256:"):
            raise ValidationError(f"model source provenance digest is invalid: {logical}")
        declared.add(logical)
    if "config.json" not in declared:
        raise ValidationError("model source provenance is missing config.json")
    return provenance


def _load_binding(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValidationError("Kaggle binding file must be an object")
    required = {"bundle_id", "model_dataset", "repository", "runtime_dependencies", "retention"}
    if set(value) != required:
        raise ValidationError(f"Kaggle binding file fields must be exactly {sorted(required)}")
    if not isinstance(value["bundle_id"], str) or not value["bundle_id"]:
        raise ValidationError("Kaggle bundle_id must be a non-empty string")
    _validate_dataset_binding(value["model_dataset"], "model_dataset")
    repository = value["repository"]
    if not isinstance(repository, dict) or set(repository) != {"revision", "clean"}:
        raise ValidationError("repository binding must contain revision and clean")
    if not isinstance(repository["revision"], str) or len(repository["revision"]) != 40:
        raise ValidationError("repository revision must be a full Git commit identity")
    if not isinstance(repository["clean"], bool):
        raise ValidationError("repository clean binding must be boolean")
    dependencies = value["runtime_dependencies"]
    if not isinstance(dependencies, dict) or set(dependencies) != {"python", "torch", "transformers", "source"}:
        raise ValidationError("runtime dependency binding is incomplete")
    if any(not isinstance(dependencies[field], str) or not dependencies[field] for field in dependencies):
        raise ValidationError("runtime dependencies must use non-empty exact identities")
    retention = value["retention"]
    if not isinstance(retention, dict) or set(retention) != {"model_dataset", "trial_dataset", "notebook_output", "local_evidence"}:
        raise ValidationError("retention binding is incomplete")
    if any(not isinstance(retention[field], str) or not retention[field] for field in retention):
        raise ValidationError("retention bindings must be non-empty strings")
    return value


def _validate_dataset_binding(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"owner", "slug", "version", "private", "immutable"}:
        raise ValidationError(f"{path}: dataset binding is incomplete")
    if any(not isinstance(value[field], str) or not value[field] for field in ("owner", "slug")):
        raise ValidationError(f"{path}: dataset owner and slug must be non-empty")
    if isinstance(value["version"], bool) or not isinstance(value["version"], int) or value["version"] < 1:
        raise ValidationError(f"{path}: dataset version must be a positive integer")
    if value["private"] is not True or value["immutable"] is not True:
        raise ValidationError(f"{path}: dataset must be private and immutable")
    return value


def _walk_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_OUTBOUND_KEYS:
                raise ValidationError(f"{path}.{key}: evaluator-derived metadata is prohibited from transport")
            _walk_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_keys(item, f"{path}[{index}]")


def _reject_secret_material(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        prohibited = {"credential", "credentials", "secret", "password", "api_key", "access_token", "private_key"}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in prohibited:
                raise ValidationError(f"{path}.{key}: secret or credential fields are prohibited from transport")
            _reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if value.startswith(("sk-", "ghp_", "github_pat_", "hf_")) or "-----begin private key-----" in lowered:
            raise ValidationError(f"{path}: probable secret material is prohibited from transport")


def _read_repo_file(root: Path, relative: str) -> bytes:
    path = root / relative
    if not path.is_file():
        raise ValidationError(f"required tracked Kaggle adapter file is missing: {relative}")
    return path.read_bytes()


def _adapter_files(
    repository_root: Path,
    bundle_id: str,
) -> tuple[bytes, bytes, bytes | None, dict[str, Any] | None]:
    """Select one immutable, run-identified Kaggle adapter."""

    if bundle_id == "run-001":
        return (
            _read_repo_file(repository_root, "src/irisx/kaggle_runner.py"),
            _read_repo_file(repository_root, "trials/first-real-domain/kaggle-notebook.ipynb"),
            None,
            None,
        )
    if bundle_id == "run-002":
        return (
            _read_repo_file(repository_root, "src/irisx/kaggle_runner_v4.py"),
            _read_repo_file(repository_root, "trials/first-real-domain/kaggle-notebook-v4.ipynb"),
            _read_repo_file(repository_root, "src/irisx/kaggle_runner.py"),
            CHECKPOINT_POLICY,
        )
    if bundle_id == "run-003":
        return (
            _read_repo_file(repository_root, "src/irisx/kaggle_runner_v5.py"),
            _read_repo_file(repository_root, "trials/first-real-domain/kaggle-notebook-v5.ipynb"),
            _read_repo_file(repository_root, "src/irisx/kaggle_runner.py"),
            COMPLETION_BENCHMARK_POLICY,
        )
    raise ValidationError("Trial 001 outbound bundle_id must be run-001, run-002, or run-003")


def _validate_outbound_destination(output: Path, bundle_id: str) -> None:
    """Keep the filesystem run identity aligned with the manifest package ID."""

    if output.name != "trial-input.zip" or output.parent.name != bundle_id:
        raise ValidationError(
            "outbound path must be outbound/<bundle-id>/trial-input.zip "
            "with the parent directory equal to binding.bundle_id"
        )


def _runtime_wheel_files(root: Path, dependencies: dict[str, str]) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Validate and bind the exact offline Python 3.12/Linux wheel closure."""

    if dependencies.get("transformers") != "5.8.1":
        raise ValidationError("runtime transformers must be exactly 5.8.1 for Qwen3.5")
    if not root.is_dir():
        raise ValidationError(f"runtime wheel directory does not exist: {root}")
    actual = {path.name: path for path in root.iterdir() if path.is_file()}
    if set(actual) != set(RUNTIME_WHEEL_FILENAMES):
        missing = sorted(set(RUNTIME_WHEEL_FILENAMES) - set(actual))
        unexpected = sorted(set(actual) - set(RUNTIME_WHEEL_FILENAMES))
        raise ValidationError(f"runtime wheel closure mismatch; missing={missing}, unexpected={unexpected}")
    files: dict[str, bytes] = {}
    entries: list[dict[str, Any]] = []
    for name in RUNTIME_WHEEL_FILENAMES:
        path = actual[name]
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if not members or not any(member.filename.endswith(".dist-info/METADATA") for member in members):
                    raise ValidationError(f"runtime wheel lacks package metadata: {name}")
                for member in members:
                    logical = member.filename
                    parts = logical.split("/")
                    path_parts = parts[:-1] if member.is_dir() and parts[-1] == "" else parts
                    if (
                        not logical
                        or not path_parts
                        or "\\" in logical
                        or logical.startswith("/")
                        or any(part in {"", ".", ".."} for part in path_parts)
                        or stat.S_ISLNK(member.external_attr >> 16)
                    ):
                        raise ValidationError(f"runtime wheel contains an unsafe member: {name}:{logical}")
        except zipfile.BadZipFile as exc:
            raise ValidationError(f"runtime wheel is not a valid ZIP archive: {name}") from exc
        data = path.read_bytes()
        logical = f"runtime/wheels/{name}"
        files[logical] = data
        entries.append({"path": logical, "byte_size": len(data), "content_digest": digest_bytes(data)})
    manifest = {
        "format": "irisx/offline-python-wheel-closure",
        "format_version": "1.0",
        "python_abi": "cp312",
        "platform": "manylinux2014_x86_64",
        "transformers": "5.8.1",
        "wheels": entries,
    }
    return files, manifest


def build_outbound_package(
    trial_root: Path,
    model_source: Path,
    binding_path: Path,
    runtime_wheels: Path,
    output: Path,
    *,
    repository_root: Path,
) -> str:
    validate_trial_bundle(trial_root)
    model_provenance = validate_model_source(model_source)
    model_provenance_digest = model_provenance["content_digest"]
    binding = _load_binding(binding_path)
    _validate_outbound_destination(output, binding["bundle_id"])
    wheel_files, wheel_manifest = _runtime_wheel_files(runtime_wheels, binding["runtime_dependencies"])
    runner, notebook, runner_core, adapter_policy = _adapter_files(repository_root, binding["bundle_id"])
    model = read_json(trial_root / "model.json")
    envelope = read_json(trial_root / "execution-envelope.json")
    baseline = read_json(trial_root / "baseline.json")
    candidate = read_json(trial_root / "candidate.json")
    run_binding = {
        "bundle_id": binding["bundle_id"],
        "run_id": binding["bundle_id"],
        "model_source_provenance_digest": model_provenance_digest,
        "model_dataset": binding["model_dataset"],
        "repository_revision": binding["repository"]["revision"],
        "repository_clean": binding["repository"]["clean"],
        "notebook_digest": digest_bytes(notebook),
        "runner_digest": digest_bytes(runner),
        "baseline_configuration_ref": {
            "kind": baseline["schema"], "artifact_id": baseline["artifact_id"], "version": baseline["version"], "content_digest": baseline["content_digest"]
        },
        "candidate_configuration_ref": {
            "kind": candidate["schema"], "artifact_id": candidate["artifact_id"], "version": candidate["version"], "content_digest": candidate["content_digest"]
        },
        "execution_envelope_ref": artifact_ref(validate_artifact(envelope, kind="irisx/execution-envelope")),
        "retention": binding["retention"],
    }
    if runner_core is not None:
        assert adapter_policy is not None
        run_binding.update(
            {
                "runner_core_digest": digest_bytes(runner_core),
                "checkpoint_policy": adapter_policy,
            }
        )
    model_binding = make_artifact(
        "irisx/model-source-binding",
        "qwen3.8-27b-trial-001-source",
        "1.0.0",
        {
            "model_ref": artifact_ref(validate_artifact(model, kind="irisx/model-descriptor")),
            "source_provenance_ref": artifact_ref(model_provenance),
            "dataset": binding["model_dataset"],
        },
    )
    files = {
        "cases/solver-cases.json": (trial_root / "solver-cases.json").read_bytes(),
        "configurations/baseline.json": (trial_root / "baseline.json").read_bytes(),
        "configurations/candidate.json": (trial_root / "candidate.json").read_bytes(),
        "components/baseline-prompts.json": (trial_root / "baseline-prompts.json").read_bytes(),
        "components/candidate-prompts.json": (trial_root / "candidate-prompts.json").read_bytes(),
        "components/specialization.json": (trial_root / "specialization.json").read_bytes(),
        "bindings/model.json": (trial_root / "model.json").read_bytes(),
        "bindings/model-source.json": _json_bytes(model_binding),
        "bindings/model-source-provenance.json": _json_bytes(model_provenance),
        "bindings/execution-envelope.json": (trial_root / "execution-envelope.json").read_bytes(),
        "bindings/run.json": _json_bytes(run_binding),
        "runtime/dependencies.json": _json_bytes(binding["runtime_dependencies"]),
        "runtime/runner.py": runner,
        "runtime/notebook.ipynb": notebook,
        "runtime/wheels.json": _json_bytes(wheel_manifest),
    }
    if runner_core is not None:
        files["runtime/runner_core.py"] = runner_core
    files.update(wheel_files)
    metadata = {
        "arc_source": {"repository": ARC_REPOSITORY, "commit": ARC_COMMIT},
        "model": {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "source_provenance_digest": model_provenance_digest,
        },
        "model_dataset": binding["model_dataset"],
        "repository": binding["repository"],
        "notebook_digest": digest_bytes(notebook),
        "runner_digest": digest_bytes(runner),
        "baseline_configuration_ref": run_binding["baseline_configuration_ref"],
        "candidate_configuration_ref": run_binding["candidate_configuration_ref"],
        "execution_envelope_ref": run_binding["execution_envelope_ref"],
        "runtime_dependencies": binding["runtime_dependencies"],
        "runtime_wheels_digest": digest_bytes(_json_bytes(wheel_manifest)),
        "retention": binding["retention"],
    }
    if runner_core is not None:
        assert adapter_policy is not None
        metadata.update(
            {
                "runner_core_digest": digest_bytes(runner_core),
                "checkpoint_policy": adapter_policy,
            }
        )
    digest = write_zip(
        output,
        TRIAL_PACKAGE_KIND,
        binding["bundle_id"],
        files,
        metadata,
        limits=TRIAL_LIMITS,
    )
    verify_outbound_package(output, expected_evaluation_count=PUBLIC_EVALUATION_COUNT)
    return digest


def verify_outbound_package(path: Path, *, expected_evaluation_count: int = PUBLIC_EVALUATION_COUNT) -> tuple[dict[str, Any], str]:
    manifest, contents, archive_digest = verify_zip(path, limits=TRIAL_LIMITS, package_kind=TRIAL_PACKAGE_KIND)
    wheel_paths = {f"runtime/wheels/{name}" for name in RUNTIME_WHEEL_FILENAMES}
    package_id = manifest["package_id"]
    if package_id == "run-001":
        expected_paths = OUTBOUND_PATHS | wheel_paths
        checkpointing = False
        adapter_policy = None
    elif package_id == "run-002":
        expected_paths = CHECKPOINT_OUTBOUND_PATHS | wheel_paths
        checkpointing = True
        adapter_policy = CHECKPOINT_POLICY
    elif package_id == "run-003":
        expected_paths = CHECKPOINT_OUTBOUND_PATHS | wheel_paths
        checkpointing = True
        adapter_policy = COMPLETION_BENCHMARK_POLICY
    else:
        raise ValidationError("Trial 001 outbound package ID must be run-001, run-002, or run-003")
    if set(contents) != expected_paths:
        raise ValidationError("trial input package membership is not the exact closed-world profile")
    solver = validate_artifact(_json_from_bytes(contents["cases/solver-cases.json"], "cases/solver-cases.json"), kind="irisx/arc-solver-cases")
    cases = solver["payload"].get("cases")
    if not isinstance(cases, list) or len(cases) != expected_evaluation_count:
        raise ValidationError(f"outbound solver view must contain exactly {expected_evaluation_count} cases")
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"case_id", "train", "test"}:
            raise ValidationError("outbound solver case contains forbidden fields")
        validate_task({"train": case["train"], "test": case["test"]}, f"outbound/{case.get('case_id')}", require_test_outputs=False)
    baseline = CandidateConfiguration.from_dict(_json_from_bytes(contents["configurations/baseline.json"], "baseline.json"))
    candidate = CandidateConfiguration.from_dict(_json_from_bytes(contents["configurations/candidate.json"], "candidate.json"))
    baseline_prompts = validate_artifact(_json_from_bytes(contents["components/baseline-prompts.json"], "baseline-prompts.json"), kind="irisx/prompts-programs")
    candidate_prompts = validate_artifact(_json_from_bytes(contents["components/candidate-prompts.json"], "candidate-prompts.json"), kind="irisx/prompts-programs")
    specialization = validate_artifact(_json_from_bytes(contents["components/specialization.json"], "specialization.json"), kind="irisx/specialization-provenance")
    model = validate_artifact(_json_from_bytes(contents["bindings/model.json"], "model.json"), kind="irisx/model-descriptor")
    model_binding = validate_artifact(
        _json_from_bytes(contents["bindings/model-source.json"], "model-source.json"),
        kind="irisx/model-source-binding",
    )
    model_provenance = validate_model_provenance(
        _json_from_bytes(contents["bindings/model-source-provenance.json"], "model-source-provenance.json")
    )
    envelope = validate_artifact(_json_from_bytes(contents["bindings/execution-envelope.json"], "execution-envelope.json"), kind="irisx/execution-envelope")
    run = _json_from_bytes(contents["bindings/run.json"], "run.json")
    dependencies = _json_from_bytes(contents["runtime/dependencies.json"], "dependencies.json")
    wheel_manifest = _json_from_bytes(contents["runtime/wheels.json"], "wheels.json")
    if model["payload"].get("repository") != MODEL_REPOSITORY or model["payload"].get("revision") != MODEL_REVISION:
        raise ValidationError("outbound model descriptor was substituted")
    expected_model_metadata = {
        "repository": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "source_provenance_digest": model_provenance["content_digest"],
    }
    if manifest["metadata"].get("model") != expected_model_metadata:
        raise ValidationError("outbound model metadata is stale or substituted")
    if set(model_binding["payload"]) != {"model_ref", "source_provenance_ref", "dataset"}:
        raise ValidationError("outbound model source binding fields are incomplete or unexpected")
    if model_binding["payload"].get("model_ref") != artifact_ref(model):
        raise ValidationError("outbound model source does not bind the model descriptor")
    if model_binding["payload"].get("source_provenance_ref") != artifact_ref(model_provenance):
        raise ValidationError("outbound model source provenance reference is stale")
    if model_provenance["content_digest"] != manifest["metadata"].get("model", {}).get("source_provenance_digest"):
        raise ValidationError("outbound model source provenance digest binding is stale")
    _validate_dataset_binding(model_binding["payload"].get("dataset"), "outbound model dataset")
    if model_binding["payload"]["dataset"] != manifest["metadata"].get("model_dataset"):
        raise ValidationError("outbound model Dataset binding is stale")
    for name, configuration, prompts in (
        ("baseline", baseline, baseline_prompts),
        ("candidate", candidate, candidate_prompts),
    ):
        if configuration.payload["components"].get("model") != artifact_ref(model):
            raise ValidationError(f"outbound {name} model binding is stale")
        if configuration.payload["components"].get("prompts_programs") != artifact_ref(prompts):
            raise ValidationError(f"outbound {name} prompts binding is stale")
    for component in {"model", "workflow_control", "validation"}:
        if baseline.payload["components"].get(component) != candidate.payload["components"].get(component):
            raise ValidationError(f"outbound baseline/candidate {component} bindings differ")
    if specialization["payload"].get("prompts_programs_ref") != artifact_ref(candidate_prompts):
        raise ValidationError("outbound specialization provenance is stale")
    if specialization["payload"].get("evaluation_material_used") is not False or specialization["payload"].get("result_feedback_used") is not False:
        raise ValidationError("outbound specialization reports prohibited evaluation influence")
    if envelope["payload"].get("network_enabled") is not False or envelope["payload"].get("provider_calls") is not False:
        raise ValidationError("outbound execution envelope must prohibit network and provider calls")
    expected_run = {
        "bundle_id": manifest["package_id"],
        "run_id": manifest["package_id"],
        "model_source_provenance_digest": manifest["metadata"]["model"]["source_provenance_digest"],
        "model_dataset": manifest["metadata"]["model_dataset"],
        "repository_revision": manifest["metadata"]["repository"]["revision"],
        "repository_clean": manifest["metadata"]["repository"]["clean"],
        "notebook_digest": manifest["metadata"]["notebook_digest"],
        "runner_digest": manifest["metadata"]["runner_digest"],
        "baseline_configuration_ref": baseline.ref(),
        "candidate_configuration_ref": candidate.ref(),
        "execution_envelope_ref": artifact_ref(envelope),
        "retention": manifest["metadata"]["retention"],
    }
    if checkpointing:
        expected_run.update(
            {
                "runner_core_digest": manifest["metadata"].get("runner_core_digest"),
                "checkpoint_policy": manifest["metadata"].get("checkpoint_policy"),
            }
        )
    if run != expected_run:
        raise ValidationError("outbound run binding is stale or contains unexpected fields")
    if digest_bytes(contents["runtime/runner.py"]) != run["runner_digest"]:
        raise ValidationError("outbound runner source digest mismatch")
    if digest_bytes(contents["runtime/notebook.ipynb"]) != run["notebook_digest"]:
        raise ValidationError("outbound notebook source digest mismatch")
    if checkpointing:
        if run["checkpoint_policy"] != adapter_policy:
            raise ValidationError("outbound checkpoint policy is stale or unsupported")
        if digest_bytes(contents["runtime/runner_core.py"]) != run["runner_core_digest"]:
            raise ValidationError("outbound runner core source digest mismatch")
    elif "runner_core_digest" in manifest["metadata"] or "checkpoint_policy" in manifest["metadata"]:
        raise ValidationError("legacy run-001 metadata contains checkpoint adapter fields")
    if (
        not isinstance(dependencies, dict)
        or set(dependencies) != {"python", "torch", "transformers", "source"}
        or not all(isinstance(value, str) and value for value in dependencies.values())
    ):
        raise ValidationError("outbound runtime dependencies are not fully bound")
    if dependencies != manifest["metadata"].get("runtime_dependencies"):
        raise ValidationError("outbound runtime dependency binding is stale")
    expected_wheels = [
        {
            "path": logical,
            "byte_size": len(contents[logical]),
            "content_digest": digest_bytes(contents[logical]),
        }
        for logical in sorted(wheel_paths)
    ]
    if wheel_manifest != {
        "format": "irisx/offline-python-wheel-closure",
        "format_version": "1.0",
        "python_abi": "cp312",
        "platform": "manylinux2014_x86_64",
        "transformers": "5.8.1",
        "wheels": expected_wheels,
    }:
        raise ValidationError("outbound runtime wheel closure is stale or substituted")
    if manifest["metadata"].get("runtime_wheels_digest") != digest_bytes(contents["runtime/wheels.json"]):
        raise ValidationError("outbound runtime wheel manifest digest is stale")
    if run.get("retention") != manifest["metadata"].get("retention"):
        raise ValidationError("outbound retention binding is stale")
    for logical, data in contents.items():
        if logical.endswith(".json"):
            value = _json_from_bytes(data, logical)
            _walk_keys(value)
            _reject_secret_material(value)
    for forbidden_schema in (b"irisx/arc-evaluator-truth", b"irisx/evaluation-result", b"irisx/selection-decision", b"irisx/domain-package-manifest"):
        if any(forbidden_schema in data for data in contents.values()):
            raise ValidationError("outbound package contains a prohibited evaluator or local-decision artifact")
    return manifest, archive_digest


def build_result_package(
    output: Path,
    package_id: str,
    baseline_predictions: dict[str, Any],
    candidate_predictions: dict[str, Any],
    observations: dict[str, Any],
    logs: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    files = {
        "predictions/baseline.json": _json_bytes(baseline_predictions),
        "predictions/candidate.json": _json_bytes(candidate_predictions),
        "observations/execution.json": _json_bytes(observations),
        "logs/runner.json": _json_bytes(logs),
    }
    return write_zip(output, RESULT_PACKAGE_KIND, package_id, files, metadata, limits=RESULT_LIMITS)


def _validate_observations(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("execution observations must be an object")
    base_required = {
        "format", "format_version", "hardware", "software", "internet_disabled", "credentials_present",
        "network_calls", "provider_calls", "external_paid_cost_usd", "evaluation_leaks", "identity_binding_failures",
        "wall_clock_seconds", "gpu_seconds_state", "gpu_seconds", "timeout_policy", "seed_policy",
        "attempts_per_test_input", "stop_conditions_triggered",
    }
    version = value.get("format_version")
    required = base_required | ({"checkpoint"} if version == "2.0" else set())
    if set(value) != required:
        raise ValidationError("execution observation fields are incomplete or unexpected")
    if value["format"] != "irisx/arc-agi-2-execution-observations" or version not in {"1.0", "2.0"}:
        raise ValidationError("unsupported execution observation format")
    hardware = value["hardware"]
    if not isinstance(hardware, dict) or hardware.get("gpu_count") != 1 or "NVIDIA RTX PRO 6000" not in hardware.get("gpu_model", "") or hardware.get("gpu_memory_mib", 0) < 96000:
        raise ValidationError("returned hardware does not match one NVIDIA RTX PRO 6000 96 GB")
    if value["internet_disabled"] is not True or value["credentials_present"] is not False:
        raise ValidationError("returned evidence does not prove Internet disabled and credentials absent")
    for field in ("network_calls", "provider_calls", "external_paid_cost_usd", "evaluation_leaks", "identity_binding_failures"):
        if value[field] != 0:
            raise ValidationError(f"returned stop-condition evidence is non-zero: {field}")
    if value["attempts_per_test_input"] != 2:
        raise ValidationError("returned attempt policy is not pass@2")
    if value["stop_conditions_triggered"] != []:
        raise ValidationError("returned evidence reports a triggered stop condition")
    if value["gpu_seconds_state"] not in {"observed", "unknown", "not_evaluated"}:
        raise ValidationError("returned gpu_seconds state is invalid")
    if value["gpu_seconds_state"] == "observed":
        if isinstance(value["gpu_seconds"], bool) or not isinstance(value["gpu_seconds"], (int, float)):
            raise ValidationError("observed gpu_seconds must be numeric")
    elif value["gpu_seconds"] is not None:
        raise ValidationError("unknown gpu_seconds must use null")
    if version == "2.0":
        checkpoint = value["checkpoint"]
        checkpoint_fields = {
            "format", "format_version", "resume_count", "session_count", "interrupted_attempts",
            "completed_invocations", "total_invocations", "cumulative_wall_clock_seconds", "sessions",
        }
        if not isinstance(checkpoint, dict) or set(checkpoint) != checkpoint_fields:
            raise ValidationError("checkpoint execution evidence is incomplete or unexpected")
        if checkpoint["format"] != "irisx/arc-agi-2-checkpoint" or checkpoint["format_version"] != "1.0":
            raise ValidationError("checkpoint execution evidence format is unsupported")
        for field in ("resume_count", "session_count", "interrupted_attempts", "completed_invocations", "total_invocations"):
            if isinstance(checkpoint[field], bool) or not isinstance(checkpoint[field], int) or checkpoint[field] < 0:
                raise ValidationError(f"checkpoint execution evidence is invalid: {field}")
        if (
            checkpoint["session_count"] < 1
            or checkpoint["session_count"] != checkpoint["resume_count"] + 1
            or checkpoint["interrupted_attempts"] > checkpoint["completed_invocations"]
        ):
            raise ValidationError("checkpoint execution counters are inconsistent")
        cumulative = checkpoint["cumulative_wall_clock_seconds"]
        if isinstance(cumulative, bool) or not isinstance(cumulative, (int, float)) or cumulative < 0:
            raise ValidationError("checkpoint cumulative wall-clock evidence is invalid")
        if cumulative != value["wall_clock_seconds"]:
            raise ValidationError("checkpoint cumulative wall clock does not match execution observations")
        sessions = checkpoint["sessions"]
        if not isinstance(sessions, list) or len(sessions) != checkpoint["session_count"]:
            raise ValidationError("checkpoint session evidence is incomplete")
        for index, session in enumerate(sessions):
            if not isinstance(session, dict) or set(session) != {"session_index", "hardware", "software"}:
                raise ValidationError("checkpoint session record is malformed")
            if session["session_index"] != index or session["hardware"] != hardware or session["software"] != value["software"]:
                raise ValidationError("checkpoint session identity changed across resumes")
    return value


def _validate_runner_logs(
    value: Any,
    solver: dict[str, Any],
    baseline_predictions: dict[str, Any],
    candidate_predictions: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"events"} or not isinstance(value["events"], list):
        raise ValidationError("runner log format is incomplete or unexpected")
    predictions = {
        "baseline": {case["case_id"]: case for case in baseline_predictions["cases"]},
        "candidate": {case["case_id"]: case for case in candidate_predictions["cases"]},
    }
    expected: set[tuple[str, str, int, int]] = set()
    for label in predictions:
        for case in solver["payload"]["cases"]:
            for test_index in range(len(case["test"])):
                for attempt_index in range(2):
                    expected.add((label, case["case_id"], test_index, attempt_index))
    actual: set[tuple[str, str, int, int]] = set()
    for position, event in enumerate(value["events"]):
        if not isinstance(event, dict) or set(event) != {
            "event", "configuration", "case_id", "test_index", "attempt_index", "status", "elapsed_seconds"
        }:
            raise ValidationError(f"runner log event is malformed: {position}")
        if event["event"] != "invocation_complete":
            raise ValidationError(f"runner log event type is unsupported: {position}")
        key = (event["configuration"], event["case_id"], event["test_index"], event["attempt_index"])
        if key in actual:
            raise ValidationError(f"runner log contains a duplicate invocation: {key}")
        actual.add(key)
        if key not in expected:
            raise ValidationError(f"runner log contains an unexpected invocation: {key}")
        attempt = predictions[key[0]][key[1]]["tests"][key[2]]["attempts"][key[3]]
        if event["status"] != attempt["status"]:
            raise ValidationError(f"runner log status does not match prediction evidence: {key}")
        elapsed = event["elapsed_seconds"]
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or elapsed < 0:
            raise ValidationError(f"runner log elapsed time is invalid: {key}")
    if actual != expected:
        raise ValidationError("runner logs do not exactly cover every required invocation")
    return value


def verify_result_package(
    path: Path,
    outbound_package: Path,
    trial_root: Path,
) -> tuple[dict[str, Any], dict[str, bytes], str]:
    outbound_manifest, outbound_digest = verify_outbound_package(
        outbound_package,
        expected_evaluation_count=len(validate_artifact(read_json(trial_root / "solver-cases.json"))["payload"]["cases"]),
    )
    manifest, contents, result_digest = verify_zip(path, limits=RESULT_LIMITS, package_kind=RESULT_PACKAGE_KIND)
    if set(contents) != RESULT_PATHS:
        raise ValidationError("result package membership is not the exact closed-world profile")
    solver = validate_artifact(read_json(trial_root / "solver-cases.json"), kind="irisx/arc-solver-cases")
    baseline = load_contract(trial_root / "baseline.json", CandidateConfiguration)
    candidate = load_contract(trial_root / "candidate.json", CandidateConfiguration)
    assert isinstance(baseline, CandidateConfiguration)
    assert isinstance(candidate, CandidateConfiguration)
    baseline_predictions = _json_from_bytes(contents["predictions/baseline.json"], "predictions/baseline.json")
    candidate_predictions = _json_from_bytes(contents["predictions/candidate.json"], "predictions/candidate.json")
    validate_predictions(baseline_predictions, solver, baseline.ref())
    validate_predictions(candidate_predictions, solver, candidate.ref())
    observations = _validate_observations(_json_from_bytes(contents["observations/execution.json"], "observations/execution.json"))
    logs = _validate_runner_logs(
        _json_from_bytes(contents["logs/runner.json"], "logs/runner.json"),
        solver,
        baseline_predictions,
        candidate_predictions,
    )
    metadata = manifest["metadata"]
    outbound_meta = outbound_manifest["metadata"]
    expected = {
        "trial_manifest_digest": outbound_manifest_digest(outbound_manifest),
        "model_source_provenance_digest": outbound_meta["model"]["source_provenance_digest"],
        "model_dataset": outbound_meta["model_dataset"],
        "bundle_id": outbound_manifest["package_id"],
        "repository_revision": outbound_meta["repository"]["revision"],
        "notebook_digest": outbound_meta["notebook_digest"],
        "runner_digest": outbound_meta["runner_digest"],
        "baseline_configuration_ref": baseline.ref(),
        "candidate_configuration_ref": candidate.ref(),
        "execution_envelope_ref": outbound_meta["execution_envelope_ref"],
    }
    checkpointing = outbound_manifest["package_id"] == "run-002"
    if checkpointing:
        expected.update(
            {
                "runner_core_digest": outbound_meta["runner_core_digest"],
                "checkpoint_policy": outbound_meta["checkpoint_policy"],
            }
        )
    if metadata != expected:
        raise ValidationError("result package upstream identity bindings are stale or substituted")
    if manifest["package_id"] != metadata["bundle_id"] or metadata["bundle_id"] != outbound_manifest["package_id"]:
        raise ValidationError("result package run identity does not match the outbound bundle")
    _, outbound_contents, _ = verify_zip(outbound_package, limits=TRIAL_LIMITS, package_kind=TRIAL_PACKAGE_KIND)
    dependencies = _json_from_bytes(outbound_contents["runtime/dependencies.json"], "runtime/dependencies.json")
    software = observations["software"]
    if not isinstance(software, dict) or any(software.get(field) != dependencies.get(field) for field in ("python", "torch", "transformers")):
        raise ValidationError("returned software versions do not match the bound offline runtime")
    envelope = validate_artifact(read_json(trial_root / "execution-envelope.json"), kind="irisx/execution-envelope")
    if observations["timeout_policy"] != envelope["payload"]["timeout_seconds_per_invocation"]:
        raise ValidationError("returned timeout policy does not match the common execution envelope")
    if observations["seed_policy"] != envelope["payload"]["seed_policy"]:
        raise ValidationError("returned seed policy does not match the common execution envelope")
    if (
        isinstance(observations["wall_clock_seconds"], bool)
        or not isinstance(observations["wall_clock_seconds"], (int, float))
        or observations["wall_clock_seconds"] < 0
        or observations["wall_clock_seconds"] > envelope["payload"]["wall_clock_limit_seconds"]
    ):
        raise ValidationError("returned wall-clock evidence exceeds the bound execution limit")
    if checkpointing:
        if observations["format_version"] != "2.0":
            raise ValidationError("run-002 requires checkpoint-aware execution observations")
        checkpoint = observations["checkpoint"]
        expected_invocations = sum(len(case["test"]) for case in solver["payload"]["cases"]) * 4
        if checkpoint["completed_invocations"] != expected_invocations or checkpoint["total_invocations"] != expected_invocations:
            raise ValidationError("checkpoint evidence does not cover every required invocation")
        if len(logs["events"]) != expected_invocations:
            raise ValidationError("checkpoint result log count is incomplete")
    elif observations["format_version"] != "1.0":
        raise ValidationError("run-001 cannot claim checkpoint-aware execution evidence")
    for logical, data in contents.items():
        if logical.endswith(".json"):
            value = _json_from_bytes(data, logical)
            _walk_keys(value)
            _reject_secret_material(value)
            if isinstance(value, dict) and value.get("schema") in {
                "irisx/arc-evaluator-truth", "irisx/evaluation-result", "irisx/selection-decision", "irisx/domain-package-manifest"
            }:
                raise ValidationError("result package contains prohibited local evaluator or decision evidence")
    return manifest, contents, result_digest


def verify_benchmark_result_package(
    path: Path,
    outbound_package: Path,
) -> tuple[dict[str, Any], dict[str, bytes], str]:
    """Verify an untrusted run-003 four-invocation ``result.zip`` offline."""

    outbound_manifest, outbound_digest = verify_outbound_package(outbound_package)
    if outbound_manifest["package_id"] != "run-003":
        raise ValidationError("four-invocation benchmark result requires the run-003 outbound package")
    _, outbound_contents, verified_outbound_digest = verify_zip(
        outbound_package,
        limits=TRIAL_LIMITS,
        package_kind=TRIAL_PACKAGE_KIND,
    )
    if verified_outbound_digest != outbound_digest:
        raise ValidationError("run-003 outbound digest changed during verification")

    manifest, contents, result_digest = verify_zip(
        path,
        limits=RESULT_LIMITS,
        package_kind=BENCHMARK_RESULT_KIND,
    )
    fixed = {
        "benchmark/result.json",
        "bindings/run.json",
        "checkpoint/checkpoint.json",
        "observations/execution.json",
        "logs/progress.jsonl",
    }
    raw_paths = {logical for logical in contents if logical.startswith("outputs/") and logical.endswith(".txt")}
    if set(contents) != fixed | raw_paths or len(raw_paths) != BENCHMARK_INVOCATION_LIMIT:
        raise ValidationError("benchmark result membership is not the exact four-invocation profile")

    run = _json_from_bytes(outbound_contents["bindings/run.json"], "outbound bindings/run.json")
    returned_run = _json_from_bytes(contents["bindings/run.json"], "bindings/run.json")
    if returned_run != run:
        raise ValidationError("benchmark result run binding is stale or substituted")
    identity = _benchmark_identity(run, outbound_manifest_digest(outbound_manifest))
    expected_metadata = {
        "trial_manifest_digest": identity["trial_manifest_digest"],
        "model_source_provenance_digest": identity["model_source_provenance_digest"],
        "model_dataset": run["model_dataset"],
        "bundle_id": identity["bundle_id"],
        "repository_revision": identity["repository_revision"],
        "notebook_digest": identity["notebook_digest"],
        "runner_digest": identity["runner_digest"],
        "runner_core_digest": identity["runner_core_digest"],
        "checkpoint_policy": identity["checkpoint_policy"],
        "baseline_configuration_ref": identity["baseline_configuration_ref"],
        "candidate_configuration_ref": identity["candidate_configuration_ref"],
        "execution_envelope_ref": identity["execution_envelope_ref"],
    }
    if manifest["package_id"] != "run-003" or manifest["metadata"] != expected_metadata:
        raise ValidationError("benchmark result upstream identity is stale or substituted")

    solver = _json_from_bytes(outbound_contents["cases/solver-cases.json"], "cases/solver-cases.json")
    baseline = _json_from_bytes(outbound_contents["configurations/baseline.json"], "configurations/baseline.json")
    candidate = _json_from_bytes(outbound_contents["configurations/candidate.json"], "configurations/candidate.json")
    baseline_prompts = _json_from_bytes(
        outbound_contents["components/baseline-prompts.json"], "components/baseline-prompts.json"
    )
    candidate_prompts = _json_from_bytes(
        outbound_contents["components/candidate-prompts.json"], "components/candidate-prompts.json"
    )
    tasks = _benchmark_tasks(solver, baseline, candidate, baseline_prompts, candidate_prompts)
    expected_keys = [task["key"] for task in tasks[:BENCHMARK_INVOCATION_LIMIT]]
    state = _json_from_bytes(contents["checkpoint/checkpoint.json"], "checkpoint/checkpoint.json")
    try:
        _validate_benchmark_state(state, identity, expected_keys)
        progress_events = _benchmark_progress_events(contents["logs/progress.jsonl"])
    except RuntimeError as exc:
        raise ValidationError(f"benchmark checkpoint evidence is invalid: {exc}") from exc
    if state["pending"] is not None or len(state["completed"]) != BENCHMARK_INVOCATION_LIMIT:
        raise ValidationError("benchmark result does not contain four completed invocations")
    complete_events = [event for event in progress_events if event.get("event") == "invocation_complete"]
    if (
        len(complete_events) != BENCHMARK_INVOCATION_LIMIT
        or not progress_events
        or progress_events[-1].get("event") != "benchmark_complete"
    ):
        raise ValidationError("benchmark progress log does not prove four completed invocations")
    for sequence, (event, record) in enumerate(zip(complete_events, state["completed"], strict=True)):
        if (
            event.get("sequence") != sequence
            or event.get("key") != record["key"]
            or event.get("status") != record["attempt"]["status"]
            or event.get("elapsed_seconds") != record["elapsed_seconds"]
        ):
            raise ValidationError("benchmark progress event does not match checkpoint state")

    benchmark = _json_from_bytes(contents["benchmark/result.json"], "benchmark/result.json")
    if (
        not isinstance(benchmark, dict)
        or set(benchmark) != {
            "format", "format_version", "run_id", "scope", "required_invocations",
            "completed_invocations", "records"
        }
        or benchmark["format"] != "irisx/arc-agi-2-four-invocation-benchmark"
        or benchmark["format_version"] != "1.0"
        or benchmark["run_id"] != "run-003"
        or benchmark["scope"] != COMPLETION_BENCHMARK_POLICY["scope"]
        or benchmark["required_invocations"] != BENCHMARK_INVOCATION_LIMIT
        or benchmark["completed_invocations"] != BENCHMARK_INVOCATION_LIMIT
        or not isinstance(benchmark["records"], list)
        or len(benchmark["records"]) != BENCHMARK_INVOCATION_LIMIT
    ):
        raise ValidationError("benchmark result summary is malformed or incomplete")
    expected_raw_paths = set()
    for sequence, (summary, state_record) in enumerate(zip(benchmark["records"], state["completed"], strict=True)):
        if not isinstance(summary, dict) or set(summary) != {
            "sequence", "key", "attempt", "elapsed_seconds", "started_at_utc",
            "finished_at_utc", "raw_output_path"
        }:
            raise ValidationError("benchmark invocation summary fields are incomplete")
        attempt_without_raw = {
            name: value for name, value in state_record["attempt"].items() if name != "raw_output"
        }
        if (
            summary["sequence"] != sequence
            or summary["key"] != state_record["key"]
            or summary["attempt"] != attempt_without_raw
            or summary["elapsed_seconds"] != state_record["elapsed_seconds"]
            or summary["started_at_utc"] != state_record["started_at_utc"]
            or summary["finished_at_utc"] != state_record["finished_at_utc"]
        ):
            raise ValidationError("benchmark invocation summary does not match checkpoint state")
        raw_path = summary["raw_output_path"]
        if not isinstance(raw_path, str) or raw_path not in raw_paths:
            raise ValidationError("benchmark raw output path is missing or unsafe")
        expected_raw_paths.add(raw_path)
        raw = state_record["attempt"]["raw_output"].encode("utf-8")
        if contents[raw_path] != raw or digest_bytes(raw) != state_record["attempt"]["raw_output_digest"]:
            raise ValidationError("benchmark raw output does not match its checkpoint digest")
    if expected_raw_paths != raw_paths:
        raise ValidationError("benchmark result contains an unreferenced raw output")

    observations = _json_from_bytes(contents["observations/execution.json"], "observations/execution.json")
    if (
        not isinstance(observations, dict)
        or observations.get("format") != "irisx/arc-agi-2-four-invocation-benchmark-observations"
        or observations.get("format_version") != "1.0"
        or observations.get("time_limit_policy") != {
            "invocation_time_limit_seconds": None,
            "cumulative_time_limit_seconds": None,
            "provider_session_limit_controlled": False,
        }
        or observations.get("checkpoint", {}).get("completed_invocations") != BENCHMARK_INVOCATION_LIMIT
        or observations.get("checkpoint", {}).get("required_invocations") != BENCHMARK_INVOCATION_LIMIT
        or observations.get("network_calls") != 0
        or observations.get("provider_calls") != 0
        or observations.get("evaluation_leaks") != 0
    ):
        raise ValidationError("benchmark execution observations are incomplete or unsafe")
    dependencies = _json_from_bytes(outbound_contents["runtime/dependencies.json"], "runtime/dependencies.json")
    software = observations.get("software")
    if not isinstance(software, dict) or any(
        software.get(field) != dependencies.get(field) for field in ("python", "torch", "transformers")
    ):
        raise ValidationError("benchmark software identity does not match the outbound runtime")
    last_session = state["sessions"][-1]
    model_identity = next(
        (session["model"] for session in reversed(state["sessions"]) if session["model"] is not None),
        None,
    )
    if (
        model_identity is None
        or
        observations.get("hardware") != last_session["hardware"]
        or software != last_session["software"]
        or observations.get("model") != model_identity
        or observations.get("recorded_wall_clock_seconds") != state["consumed_wall_clock_seconds"]
        or observations.get("checkpoint", {}).get("sessions") != state["sessions"]
        or observations.get("checkpoint", {}).get("interrupted_attempts") != state["interrupted_attempts"]
    ):
        raise ValidationError("benchmark runtime observations do not match checkpoint state")
    for logical, data in contents.items():
        if logical.endswith(".json"):
            value = _json_from_bytes(data, logical)
            _walk_keys(value)
            _reject_secret_material(value)
    return manifest, contents, result_digest


def import_quarantine(
    result_package: Path,
    outbound_package: Path,
    trial_root: Path,
    run_root: Path,
) -> Path:
    """Promote no bytes until the untrusted quarantine archive fully validates."""

    manifest, _, result_digest = verify_result_package(result_package, outbound_package, trial_root)
    run_id = manifest["package_id"]
    if result_package.name != "result-package.zip" or result_package.parent.name != run_id or result_package.parent.parent.name != "quarantine":
        raise ValidationError("result package is not at the required quarantine/<run-id>/result-package.zip path")
    target = run_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValidationError(f"normalized run target already exists: {target}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=run_root))
    try:
        extract_verified_zip(result_package, temporary, limits=RESULT_LIMITS, package_kind=RESULT_PACKAGE_KIND)
        write_json(
            temporary / "import-evidence.json",
            {
                "format": "irisx/arc-agi-2-import-evidence",
                "format_version": "1.0",
                "run_id": run_id,
                "quarantine_package_digest": result_digest,
                "trial_manifest_digest": manifest["metadata"]["trial_manifest_digest"],
                "status": "validated-and-normalized",
            },
        )
        temporary.replace(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def evaluate_imported_run(trial_root: Path, run_dir: Path) -> dict[str, Any]:
    validate_trial_bundle(trial_root, expected_evaluation_count=len(validate_artifact(read_json(trial_root / "solver-cases.json"))["payload"]["cases"]))
    observations = _validate_observations(read_json(run_dir / "observations/execution.json"))
    baseline_predictions = read_json(run_dir / "predictions/baseline.json")
    candidate_predictions = read_json(run_dir / "predictions/candidate.json")
    baseline_config = load_contract(trial_root / "baseline.json", CandidateConfiguration)
    candidate_config = load_contract(trial_root / "candidate.json", CandidateConfiguration)
    trial = load_contract(trial_root / "trial.json", EngineeringTrial)
    workload = load_contract(trial_root / "workload.json", WorkloadDefinition)
    requirements = load_contract(trial_root / "requirements.json", RequirementSet)
    assert isinstance(baseline_config, CandidateConfiguration)
    assert isinstance(candidate_config, CandidateConfiguration)
    assert isinstance(trial, EngineeringTrial)
    assert isinstance(workload, WorkloadDefinition)
    assert isinstance(requirements, RequirementSet)
    baseline_result = score_predictions(
        trial_root, baseline_predictions, baseline_config, observations, result_id="arc-agi-2-trial-001-baseline-result"
    )
    candidate_result = score_predictions(
        trial_root, candidate_predictions, candidate_config, observations, result_id="arc-agi-2-trial-001-candidate-result"
    )
    configurations = {baseline_config.content_digest: baseline_config, candidate_config.content_digest: candidate_config}
    decision = select_configuration(
        trial,
        workload,
        requirements,
        baseline_result,
        [candidate_result],
        configurations,
        decision_id="arc-agi-2-trial-001-selection",
    )
    acceptance = p2_acceptance(baseline_result, candidate_result, requirements, workload)
    evidence = run_dir / "local-evaluation"
    if evidence.exists() and any(evidence.iterdir()):
        raise ValidationError(f"local evaluation output already exists: {evidence}")
    evidence.mkdir(parents=True, exist_ok=True)
    baseline_result.write(evidence / "baseline-result.json")
    candidate_result.write(evidence / "candidate-result.json")
    decision.write(evidence / "selection.json")
    write_artifact(evidence / "p2-acceptance.json", acceptance)
    return {
        "baseline_accuracy": baseline_result.payload["metrics"]["accuracy"]["value"],
        "candidate_accuracy": candidate_result.payload["metrics"]["accuracy"]["value"],
        "selection_outcome": decision.payload["outcome"],
        "p2_accepted": acceptance["payload"]["accepted"],
        "package_eligible": acceptance["payload"]["package_eligible"],
    }


def preflight(
    trial_root: Path,
    model_source: Path,
    outbound_package: Path,
    preflight_binding_path: Path,
) -> dict[str, Any]:
    """Produce static technical readiness evidence, never owner authorization."""

    blockers: list[str] = []
    try:
        validate_trial_bundle(trial_root)
    except ValidationError as exc:
        blockers.append(f"trial_bundle:{exc}")
    try:
        model_provenance = validate_model_source(model_source)
        model_provenance_digest = model_provenance["content_digest"]
    except ValidationError as exc:
        blockers.append(f"model_source:{exc}")
        model_provenance_digest = None
    try:
        outbound_manifest, outbound_digest = verify_outbound_package(outbound_package)
    except ValidationError as exc:
        blockers.append(f"trial_package:{exc}")
        outbound_manifest = None
        outbound_digest = None
    try:
        binding = read_json(preflight_binding_path)
    except ValidationError as exc:
        blockers.append(f"preflight_binding:{exc}")
        binding = {}
    required = {
        "model_dataset", "trial_dataset", "repository_revision", "repository_clean", "notebook_digest", "runner_digest",
        "hardware", "internet_disabled", "credentials_present", "provider_calls_enabled", "external_paid_cost_usd",
        "execution_limits", "result_shape", "quarantine_path", "retention", "runtime_dependencies",
    }
    outbound_id = outbound_manifest.get("package_id") if outbound_manifest is not None else None
    checkpointing = outbound_id in {"run-002", "run-003"}
    completion_benchmark = outbound_id == "run-003"
    if checkpointing:
        required |= {"runner_core_digest", "checkpoint_policy"}
    if not isinstance(binding, dict) or set(binding) != required:
        blockers.append("preflight_binding:incomplete_or_unexpected_fields")
        binding = {} if not isinstance(binding, dict) else binding
    for field in ("model_dataset", "trial_dataset"):
        try:
            _validate_dataset_binding(binding.get(field), field)
        except ValidationError as exc:
            blockers.append(str(exc))
    if binding.get("repository_clean") is not True or not isinstance(binding.get("repository_revision"), str) or len(binding.get("repository_revision", "")) != 40:
        blockers.append("repository:requires_clean_full_revision")
    hardware = binding.get("hardware")
    if hardware != {"gpu_count": 1, "gpu_model": "NVIDIA RTX PRO 6000", "gpu_memory_gb": 96}:
        blockers.append("hardware:must_bind_one_nvidia_rtx_pro_6000_96gb")
    if binding.get("internet_disabled") is not True:
        blockers.append("internet:must_be_disabled")
    if binding.get("credentials_present") is not False:
        blockers.append("credentials:must_be_absent")
    if binding.get("provider_calls_enabled") is not False:
        blockers.append("provider_calls:must_be_disabled")
    if binding.get("external_paid_cost_usd") != 0:
        blockers.append("external_cost:must_be_zero_usd")
    expected_result_shape = BENCHMARK_RESULT_SHAPE if completion_benchmark else sorted(RESULT_PATHS)
    if binding.get("result_shape") != expected_result_shape:
        blockers.append("result_shape:must_bind_complete_result_package")
    quarantine = binding.get("quarantine_path")
    if not isinstance(quarantine, str) or ".irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/" not in quarantine.replace("\\", "/"):
        blockers.append("quarantine_path:must_use_designated_local_quarantine")
    retention = binding.get("retention")
    if not isinstance(retention, dict) or any(not isinstance(value, str) or not value for value in retention.values()):
        blockers.append("retention:all_dataset_output_and_local_behaviors_must_be_bound")
    runtime = binding.get("runtime_dependencies")
    if not isinstance(runtime, dict) or set(runtime) != {"python", "torch", "transformers", "source"} or any(not isinstance(value, str) or not value for value in runtime.values()):
        blockers.append("runtime_dependencies:must_be_exactly_bound")
    try:
        envelope = (
            validate_artifact(read_json(trial_root / "execution-envelope.json"), kind="irisx/execution-envelope")
            if (trial_root / "execution-envelope.json").is_file()
            else None
        )
    except ValidationError as exc:
        blockers.append(f"execution_envelope:{exc}")
        envelope = None
    if envelope is not None:
        expected_limits = (
            {
                "attempts_per_test_input": envelope["payload"]["attempts_per_test_input"],
                "invocation_limit": BENCHMARK_INVOCATION_LIMIT,
                "invocation_time_limit_seconds": None,
                "cumulative_time_limit_seconds": None,
                "provider_session_limit_controlled": False,
                "seed_policy": envelope["payload"]["seed_policy"],
                "decoding": envelope["payload"]["decoding"],
                "output_limits": envelope["payload"]["output_limits"],
            }
            if completion_benchmark
            else {
                field: envelope["payload"][field]
                for field in (
                    "attempts_per_test_input", "invocation_limit_per_configuration",
                    "timeout_seconds_per_invocation", "wall_clock_limit_seconds",
                    "seed_policy", "decoding", "output_limits",
                )
            }
        )
        if binding.get("execution_limits") != expected_limits:
            blockers.append("execution_limits:do_not_match_the_bound_adapter_policy")
    if outbound_manifest is not None:
        metadata = outbound_manifest["metadata"]
        identity_fields = ["repository_revision", "notebook_digest", "runner_digest"]
        if checkpointing:
            identity_fields.append("runner_core_digest")
        for field in identity_fields:
            expected = metadata["repository"]["revision"] if field == "repository_revision" else metadata[field]
            if binding.get(field) != expected:
                blockers.append(f"{field}:stale_or_substituted")
        if checkpointing and binding.get("checkpoint_policy") != metadata.get("checkpoint_policy"):
            blockers.append("checkpoint_policy:stale_or_substituted")
        if model_provenance_digest != metadata["model"]["source_provenance_digest"]:
            blockers.append("model_source_provenance_digest:stale_or_substituted")
        if binding.get("model_dataset") != metadata["model_dataset"]:
            blockers.append("model_dataset:stale_or_substituted")
        if binding.get("runtime_dependencies") != metadata.get("runtime_dependencies"):
            blockers.append("runtime_dependencies:stale_or_substituted")
        if binding.get("retention") != metadata.get("retention"):
            blockers.append("retention:stale_or_substituted")
    technical_ready = not blockers
    report = make_artifact(
        "irisx/kaggle-preflight",
        "arc-agi-2-trial-001-kaggle-preflight",
        "1.0.0",
        {
            "technical_ready": technical_ready,
            "run_authorized": False,
            "technical_blockers": blockers,
            "authorization_blockers": ["separate explicit owner real-run authorization is absent"],
            "model_source_provenance_digest": model_provenance_digest,
            "trial_package_digest": outbound_digest,
            "trial_manifest_digest": (
                outbound_manifest_digest(outbound_manifest) if outbound_manifest is not None else None
            ),
            "bindings": binding,
        },
    )
    return report

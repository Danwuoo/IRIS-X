"""Static private Kaggle staging for a future, separately authorized run."""

from __future__ import annotations

from pathlib import Path
import shutil
import zipfile
from typing import Any

from .arc_nvarc_runtime import verify_outbound
from .canonical import canonical_bytes
from .errors import ValidationError
from .transport import digest_path


REQUIRED_WHEEL_MODULES = {
    "irisx/arc_nvarc_data.py", "irisx/arc_nvarc_representation.py",
    "irisx/arc_nvarc_training.py", "irisx/arc_nvarc_candidates.py",
    "irisx/arc_nvarc_runtime.py", "irisx/arc_nvarc_kaggle.py",
    "irisx/arc_nvarc_trm.py",
}


def stage_runtime_dataset(outbound: Path, wheel: Path, output: Path,
                          dependency_wheels: list[Path] | None = None) -> dict[str, Any]:
    """Copy exact truth-free bytes; this never calls Kaggle or uploads data."""
    binding, workload, outbound_digest = verify_outbound(outbound)
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValidationError("runtime wheel is required")
    with zipfile.ZipFile(wheel) as archive:
        if not REQUIRED_WHEEL_MODULES.issubset(archive.namelist()):
            raise ValidationError("runtime wheel omits NVARC modules")
    if output.exists() and any(output.iterdir()):
        raise ValidationError("runtime staging output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(outbound, output / "outbound.zip")
    shutil.copyfile(wheel, output / wheel.name)
    dependencies = []
    for dependency in dependency_wheels or []:
        if (not dependency.is_file() or dependency.suffix != ".whl" or
                dependency.name == wheel.name or (output / dependency.name).exists()):
            raise ValidationError("runtime dependency wheel is missing or duplicated")
        shutil.copyfile(dependency, output / dependency.name)
        dependencies.append({"name": dependency.name, "digest": digest_path(dependency)})
    manifest = {"format": "irisx/nvarc-static-runtime-staging", "run_id": binding["run_id"],
                "run_identity_digest": binding["identity_digest"],
                "outbound_digest": outbound_digest, "wheel_digest": digest_path(wheel),
                "wheel_name": wheel.name, "workload_task_count": workload["task_count"],
                "dependency_wheels": dependencies,
                "contains_evaluator_truth": False, "uploaded": False}
    (output / "staging-manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


def resolve_exact_mount(candidates: list[Path], required_file: str) -> Path:
    """Only explicitly listed owner-qualified or legacy paths are permitted."""
    if not candidates or any(".." in path.parts or not path.is_absolute() for path in candidates):
        raise ValidationError("mount candidates must be explicit absolute paths")
    found = [path / required_file for path in candidates if (path / required_file).is_file()]
    if len(found) != 1:
        raise ValidationError(f"expected exactly one explicit mount for {required_file}")
    return found[0]

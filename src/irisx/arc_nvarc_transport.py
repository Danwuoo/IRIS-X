"""Static private Kaggle staging for a future, separately authorized run."""

from __future__ import annotations

from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import zipfile
from typing import Any, Callable, Iterable

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


def resume_digest_member(destination: Path, *, expected_bytes: int,
                         expected_sha256: str,
                         chunks_from_offset: Callable[[int], Iterable[bytes]]) -> Path:
    """Resume one immutable member, then promote only exact size/digest bytes.

    The caller supplies a range-capable stream for the requested offset. A
    broken stream leaves `.part` for a same-version continuation; no artifact
    is accepted solely because a download command returned successfully.
    """
    if (expected_bytes < 1 or len(expected_sha256) != 64 or
            any(char not in "0123456789abcdef" for char in expected_sha256)):
        raise ValidationError("retrieval member identity is incomplete")
    if destination.is_symlink():
        raise ValidationError("retrieval destination is unsafe")

    def matches(path: Path) -> bool:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return path.stat().st_size == expected_bytes and digest.hexdigest() == expected_sha256

    if destination.exists():
        if not destination.is_file() or not matches(destination):
            raise ValidationError("existing retrieved member identity differs")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if partial.is_symlink() or (partial.exists() and not partial.is_file()):
        raise ValidationError("retrieval partial path is unsafe")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > expected_bytes:
        raise ValidationError("retrieval partial exceeds expected size")
    with partial.open("ab") as stream:
        for chunk in chunks_from_offset(offset):
            if not isinstance(chunk, bytes) or not chunk or offset + len(chunk) > expected_bytes:
                raise ValidationError("retrieval stream chunk is invalid")
            stream.write(chunk)
            offset += len(chunk)
        stream.flush()
        os.fsync(stream.fileno())
    if offset != expected_bytes:
        raise ValidationError("retrieval member remains incomplete")
    if not matches(partial):
        raise ValidationError("retrieval member digest differs")
    os.replace(partial, destination)
    return destination


def run_utf8_logged_command(argv: list[str], log: Path, *, cwd: Path | None = None,
                            timeout: int = 60) -> int:
    """Capture raw UTF-8 child output without Windows console transcoding."""
    if not argv or timeout < 1 or log.exists():
        raise ValidationError("UTF-8 logged command needs new log and bounds")
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with log.open("wb") as stream:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout, check=False)
    return result.returncode

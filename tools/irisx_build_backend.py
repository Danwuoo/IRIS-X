"""Minimal dependency-free PEP 517/660 backend for the IRIS-X package."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
from pathlib import Path, PurePosixPath
import zipfile


NAME = "irisx"
VERSION = "0.2.0"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"
WHEEL_NAME = f"{NAME}-{VERSION}-py3-none-any.whl"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "irisx"
RESOURCE_ALLOWLIST = ("licenses/NeMo-RL-LICENSE.txt",)
REQUIRED_MODULES = ("__init__.py", "__main__.py", "cli.py")
EXCLUDED_DIRS = {"tests", "__pycache__", ".irisx", ".git"}


def _safe_file(path: Path) -> bytes:
    for parent in (path, *path.parents):
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError(f"linked build path: {path}")
        if parent == ROOT:
            break
    if not path.is_file() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"missing or unsafe build file: {path}")
    return path.read_bytes()


def _source_files() -> dict[str, bytes]:
    """Traverse Python packages only; resources have an explicit allowlist."""
    files = {}
    for name in REQUIRED_MODULES:
        _safe_file(SOURCE / name)

    def visit(directory: Path) -> None:
        for child in sorted(directory.iterdir()):
            if child.name.startswith(".") or child.name in EXCLUDED_DIRS:
                continue
            if child.is_symlink() or (hasattr(child, "is_junction") and child.is_junction()):
                raise ValueError(f"linked build path: {child}")
            if child.is_dir():
                if (child / "__init__.py").is_file():
                    if not child.name.isidentifier():
                        raise ValueError(f"invalid package directory: {child}")
                    visit(child)
            elif child.suffix == ".py" and not child.name.startswith("test_"):
                files[f"irisx/{child.relative_to(SOURCE).as_posix()}"] = _safe_file(child)

    visit(SOURCE)
    for name in RESOURCE_ALLOWLIST:
        data = _safe_file(SOURCE / name)
        files[f"irisx/{name}"] = data
        files[f"{DIST_INFO}/licenses/{Path(name).name}"] = data
    return files


def _metadata() -> bytes:
    return (
        "Metadata-Version: 2.4\n"
        "Name: irisx\n"
        f"Version: {VERSION}\n"
        "Summary: Provider-neutral product contracts, offline qualification, and P2 admission validation for IRIS-X\n"
        "Requires-Python: >=3.11\n"
        "License-Expression: LicenseRef-Proprietary\n"
        "License-File: NeMo-RL-LICENSE.txt\n"
        "\n"
    ).encode("utf-8")


def _wheel() -> bytes:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: irisx-build-backend\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
        "\n"
    ).encode("utf-8")


def _entry_points() -> bytes:
    return b"[console_scripts]\nirisx = irisx.cli:main\n"


def _hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    return f"sha256={digest}"


def _write_wheel(wheel_directory: str, files: dict[str, bytes]) -> str:
    files = dict(files)
    seen = set()
    for path in files:
        parts = PurePosixPath(path).parts
        if not parts or path.startswith("/") or "\\" in path or ":" in path or any(p in (".", "..", "") for p in path.split("/")):
            raise ValueError(f"unsafe wheel member: {path}")
        if path.casefold() in seen:
            raise ValueError(f"case collision in wheel: {path}")
        seen.add(path.casefold())
    record_path = f"{DIST_INFO}/RECORD"
    if record_path.casefold() in seen:
        raise ValueError("RECORD is reserved")
    records = io.StringIO(newline="")
    writer = csv.writer(records, lineterminator="\n")
    for path, data in sorted(files.items()):
        writer.writerow((path, _hash(data), len(data)))
    writer.writerow((record_path, "", ""))
    files[record_path] = records.getvalue().encode("utf-8")
    destination = Path(wheel_directory) / WHEEL_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return WHEEL_NAME


def _dist_info_files() -> dict[str, bytes]:
    return {
        f"{DIST_INFO}/METADATA": _metadata(),
        f"{DIST_INFO}/WHEEL": _wheel(),
        f"{DIST_INFO}/entry_points.txt": _entry_points(),
    }


def get_requires_for_build_wheel(config_settings=None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings=None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings=None) -> str:
    target = Path(metadata_directory) / DIST_INFO
    target.mkdir(parents=True, exist_ok=True)
    for path, data in _dist_info_files().items():
        (target / Path(path).name).write_bytes(data)
    for name in RESOURCE_ALLOWLIST:
        notice = target / "licenses" / Path(name).name
        notice.parent.mkdir(exist_ok=True)
        notice.write_bytes(_safe_file(SOURCE / name))
    return DIST_INFO


def prepare_metadata_for_build_editable(metadata_directory: str, config_settings=None) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    files = _dist_info_files()
    files.update(_source_files())
    return _write_wheel(wheel_directory, files)


def build_editable(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    files = _dist_info_files()
    for name in RESOURCE_ALLOWLIST:
        files[f"{DIST_INFO}/licenses/{Path(name).name}"] = _safe_file(SOURCE / name)
    source_path = str((ROOT / "src").resolve())
    files[f"__editable__.{NAME}-{VERSION}.pth"] = (source_path + "\n").encode("utf-8")
    return _write_wheel(wheel_directory, files)

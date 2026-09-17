"""Minimal dependency-free PEP 517/660 backend for the IRIS-X package."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import zipfile


NAME = "irisx"
VERSION = "0.2.0"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"
WHEEL_NAME = f"{NAME}-{VERSION}-py3-none-any.whl"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "irisx"


def _metadata() -> bytes:
    return (
        "Metadata-Version: 2.4\n"
        "Name: irisx\n"
        f"Version: {VERSION}\n"
        "Summary: Provider-neutral product contracts, offline qualification, and P2 admission validation for IRIS-X\n"
        "Requires-Python: >=3.11\n"
        "License-Expression: LicenseRef-Proprietary\n"
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
    records = [f"{path},{_hash(data)},{len(data)}" for path, data in sorted(files.items())]
    record_path = f"{DIST_INFO}/RECORD"
    files[record_path] = ("\n".join(records) + f"\n{record_path},,\n").encode("utf-8")
    destination = Path(wheel_directory) / WHEEL_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
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
    return DIST_INFO


def prepare_metadata_for_build_editable(metadata_directory: str, config_settings=None) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    files = _dist_info_files()
    for source in sorted(SOURCE.glob("*.py")):
        files[f"irisx/{source.name}"] = source.read_bytes()
    return _write_wheel(wheel_directory, files)


def build_editable(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    files = _dist_info_files()
    source_path = str((ROOT / "src").resolve())
    files[f"__editable__.{NAME}-{VERSION}.pth"] = (source_path + "\n").encode("utf-8")
    return _write_wheel(wheel_directory, files)

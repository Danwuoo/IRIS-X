"""Deterministic, closed-world ZIP transport for the ARC-AGI-2 handoff."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import shutil
import stat
import struct
from typing import Any, Mapping
import zipfile

from .canonical import canonical_bytes, digest_bytes
from .contracts import _exact, _identifier, _list, _object, _string, validate_logical_path
from .errors import ValidationError


TRANSPORT_VERSION = "1.0"
MANIFEST_PATH = "manifest.json"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ArchiveLimits:
    max_files: int
    max_file_bytes: int
    max_total_bytes: int
    max_archive_bytes: int
    max_compression_ratio: int = 100


TRIAL_LIMITS = ArchiveLimits(64, 64 * 1024 * 1024, 256 * 1024 * 1024, 300 * 1024 * 1024)
RESULT_LIMITS = ArchiveLimits(64, 256 * 1024 * 1024, 2 * 1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024)
MODEL_LIMITS = ArchiveLimits(4096, 32 * 1024 * 1024 * 1024, 100 * 1024 * 1024 * 1024, 100 * 1024 * 1024 * 1024)


def digest_path(path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(CHUNK_BYTES):
                hasher.update(chunk)
    except OSError as exc:
        raise ValidationError(f"cannot digest {path}: {exc}") from exc
    return f"sha256:{hasher.hexdigest()}"


def _regular_zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.flag_bits = 0
    info.extra = b""
    info.comment = b""
    return info


def _validate_files(files: Mapping[str, bytes], limits: ArchiveLimits) -> dict[str, bytes]:
    if not files:
        raise ValidationError("transport package must contain at least one declared file")
    if len(files) > limits.max_files:
        raise ValidationError("transport package exceeds the file-count limit")
    normalized: dict[str, bytes] = {}
    total = 0
    for path, data in files.items():
        logical = validate_logical_path(path, f"transport file {path!r}")
        if logical == MANIFEST_PATH:
            raise ValidationError("manifest.json is reserved by the transport format")
        if not isinstance(data, bytes):
            raise ValidationError(f"{logical}: transport content must be bytes")
        if len(data) > limits.max_file_bytes:
            raise ValidationError(f"{logical}: transport file exceeds the byte limit")
        total += len(data)
        if total > limits.max_total_bytes:
            raise ValidationError("transport package exceeds the expansion-size limit")
        normalized[logical] = data
    return normalized


def build_zip_bytes(
    package_kind: str,
    package_id: str,
    files: Mapping[str, bytes],
    metadata: dict[str, Any],
    *,
    limits: ArchiveLimits,
) -> bytes:
    """Build reproducible ZIP bytes with a canonical closed-world manifest."""

    _string(package_kind, "package_kind")
    _identifier(package_id, "package_id")
    normalized = _validate_files(files, limits)
    entries = [
        {"path": path, "byte_size": len(data), "content_digest": digest_bytes(data)}
        for path, data in sorted(normalized.items())
    ]
    manifest = {
        "format": "irisx/closed-world-zip",
        "format_version": TRANSPORT_VERSION,
        "package_kind": package_kind,
        "package_id": package_id,
        "files": entries,
        "metadata": metadata,
    }
    manifest_bytes = canonical_bytes(manifest, newline=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", allowZip64=True) as archive:
        archive.writestr(_regular_zip_info(MANIFEST_PATH), manifest_bytes)
        for path, data in sorted(normalized.items()):
            archive.writestr(_regular_zip_info(path), data)
    result = buffer.getvalue()
    if len(result) > limits.max_archive_bytes:
        raise ValidationError("transport package exceeds the archive-byte limit")
    return result


def write_zip(
    path: Path,
    package_kind: str,
    package_id: str,
    files: Mapping[str, bytes],
    metadata: dict[str, Any],
    *,
    limits: ArchiveLimits,
) -> str:
    data = build_zip_bytes(package_kind, package_id, files, metadata, limits=limits)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValidationError(f"transport output already exists: {path}")
    path.write_bytes(data)
    return digest_bytes(data)


def write_zip_from_paths(
    path: Path,
    package_kind: str,
    package_id: str,
    file_paths: Mapping[str, Path],
    byte_files: Mapping[str, bytes],
    metadata: dict[str, Any],
    *,
    limits: ArchiveLimits,
) -> str:
    """Build a deterministic archive without loading large source files into memory."""

    _string(package_kind, "package_kind")
    _identifier(package_id, "package_id")
    if set(file_paths) & set(byte_files):
        raise ValidationError("streamed and in-memory transport files must not overlap")
    if not file_paths and not byte_files:
        raise ValidationError("transport package must contain at least one declared file")
    if len(file_paths) + len(byte_files) > limits.max_files:
        raise ValidationError("transport package exceeds the file-count limit")
    entries: list[dict[str, Any]] = []
    normalized_paths: dict[str, Path] = {}
    normalized_bytes = _validate_files(byte_files, limits) if byte_files else {}
    total = sum(len(data) for data in normalized_bytes.values())
    for logical_value, source in file_paths.items():
        logical = validate_logical_path(logical_value, f"transport file {logical_value!r}")
        if logical == MANIFEST_PATH:
            raise ValidationError("manifest.json is reserved by the transport format")
        if source.is_symlink() or not source.is_file():
            raise ValidationError(f"{logical}: streamed transport source must be a regular file")
        size = source.stat().st_size
        if size > limits.max_file_bytes:
            raise ValidationError(f"{logical}: transport file exceeds the byte limit")
        total += size
        if total > limits.max_total_bytes:
            raise ValidationError("transport package exceeds the expansion-size limit")
        normalized_paths[logical] = source
    for logical, data in normalized_bytes.items():
        entries.append({"path": logical, "byte_size": len(data), "content_digest": digest_bytes(data)})
    for logical, source in normalized_paths.items():
        entries.append({"path": logical, "byte_size": source.stat().st_size, "content_digest": digest_path(source)})
    entries.sort(key=lambda entry: entry["path"])
    manifest = {
        "format": "irisx/closed-world-zip",
        "format_version": TRANSPORT_VERSION,
        "package_kind": package_kind,
        "package_id": package_id,
        "files": entries,
        "metadata": metadata,
    }
    manifest_bytes = canonical_bytes(manifest, newline=True)
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ValidationError("transport manifest exceeds its byte limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValidationError(f"transport output already exists: {path}")
    try:
        with zipfile.ZipFile(path, "w", allowZip64=True) as archive:
            archive.writestr(_regular_zip_info(MANIFEST_PATH), manifest_bytes)
            for entry in entries:
                logical = entry["path"]
                if logical in normalized_bytes:
                    archive.writestr(_regular_zip_info(logical), normalized_bytes[logical])
                else:
                    with normalized_paths[logical].open("rb") as source, archive.open(
                        _regular_zip_info(logical), "w", force_zip64=True
                    ) as destination:
                        shutil.copyfileobj(source, destination, CHUNK_BYTES)
    except OSError as exc:
        raise ValidationError(f"cannot build transport package {path}: {exc}") from exc
    if path.stat().st_size > limits.max_archive_bytes:
        raise ValidationError("transport package exceeds the archive-byte limit")
    return digest_path(path)


def _validate_manifest(value: Any, package_kind: str | None) -> dict[str, Any]:
    manifest = _object(value, "manifest")
    _exact(
        manifest,
        {"format", "format_version", "package_kind", "package_id", "files", "metadata"},
        "manifest",
    )
    if manifest["format"] != "irisx/closed-world-zip" or manifest["format_version"] != TRANSPORT_VERSION:
        raise ValidationError("unsupported closed-world ZIP format")
    _string(manifest["package_kind"], "manifest.package_kind")
    if package_kind is not None and manifest["package_kind"] != package_kind:
        raise ValidationError(
            f"manifest.package_kind: expected {package_kind!r}, got {manifest['package_kind']!r}"
        )
    _identifier(manifest["package_id"], "manifest.package_id")
    _object(manifest["metadata"], "manifest.metadata")
    entries = _list(manifest["files"], "manifest.files")
    if not entries:
        raise ValidationError("manifest.files must not be empty")
    seen: set[str] = set()
    for index, value in enumerate(entries):
        path = f"manifest.files[{index}]"
        entry = _object(value, path)
        _exact(entry, {"path", "byte_size", "content_digest"}, path)
        logical = validate_logical_path(entry["path"], f"{path}.path")
        if logical == MANIFEST_PATH or logical in seen:
            raise ValidationError(f"{path}.path: duplicate or reserved path")
        seen.add(logical)
        if isinstance(entry["byte_size"], bool) or not isinstance(entry["byte_size"], int) or entry["byte_size"] < 0:
            raise ValidationError(f"{path}.byte_size: must be a non-negative integer")
        digest = _string(entry["content_digest"], f"{path}.content_digest")
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise ValidationError(f"{path}.content_digest: invalid SHA-256 digest")
    return manifest


def _zip64_only(extra: bytes) -> bool:
    position = 0
    while position < len(extra):
        if position + 4 > len(extra):
            return False
        identifier, size = struct.unpack_from("<HH", extra, position)
        position += 4
        if identifier != 0x0001 or position + size > len(extra):
            return False
        position += size
    return True


def _validate_eocd(archive: zipfile.ZipFile, archive_size: int) -> None:
    stream = archive.fp
    if stream is None:
        raise ValidationError("transport ZIP stream is closed")
    original = stream.tell()
    try:
        window = min(archive_size, 65557)
        stream.seek(archive_size - window)
        tail = stream.read(window)
    finally:
        stream.seek(original)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or offset + 22 > len(tail):
        raise ValidationError("transport ZIP has no complete end-of-central-directory record")
    comment_length = struct.unpack_from("<H", tail, offset + 20)[0]
    if offset + 22 + comment_length != len(tail) or comment_length != 0:
        raise ValidationError("transport ZIP contains trailing bytes or an archive comment")


def _verify_archive(
    archive: zipfile.ZipFile,
    *,
    archive_size: int,
    limits: ArchiveLimits,
    package_kind: str | None,
    capture_paths: set[str] | None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    if archive_size > limits.max_archive_bytes:
        raise ValidationError("transport package exceeds the archive-byte limit")
    _validate_eocd(archive, archive_size)
    if archive.comment:
        raise ValidationError("transport ZIP archive comments are prohibited")
    infos = archive.infolist()
    if len(infos) > limits.max_files + 1:
        raise ValidationError("transport package exceeds the file-count limit")
    names: set[str] = set()
    total = 0
    for info in infos:
        logical = validate_logical_path(info.filename, f"ZIP entry {info.filename!r}")
        if logical in names:
            raise ValidationError(f"duplicate ZIP entry: {logical}")
        names.add(logical)
        mode = (info.external_attr >> 16) & 0xFFFF
        if info.is_dir() or stat.S_ISLNK(mode) or (mode and not stat.S_ISREG(mode)):
            raise ValidationError(f"unsafe non-regular ZIP entry: {logical}")
        if mode != (stat.S_IFREG | 0o644):
            raise ValidationError(f"non-canonical ZIP file mode: {logical}")
        if info.flag_bits != 0:
            raise ValidationError(f"non-canonical or encrypted ZIP flags: {logical}")
        if info.compress_type != zipfile.ZIP_STORED:
            raise ValidationError(f"transport ZIP entries must use deterministic stored compression: {logical}")
        if info.date_time != ZIP_TIMESTAMP or info.comment or not _zip64_only(info.extra):
            raise ValidationError(f"non-canonical ZIP metadata: {logical}")
        if info.file_size > limits.max_file_bytes:
            raise ValidationError(f"{logical}: ZIP entry exceeds the byte limit")
        total += info.file_size
        if total > limits.max_total_bytes:
            raise ValidationError("transport ZIP exceeds the expansion-size limit")
        if info.file_size and info.compress_size == 0:
            raise ValidationError(f"{logical}: invalid compressed size")
        if info.compress_size and info.file_size > info.compress_size * limits.max_compression_ratio:
            raise ValidationError(f"{logical}: unsafe ZIP expansion ratio")
    if MANIFEST_PATH not in names:
        raise ValidationError("transport ZIP is missing manifest.json")
    manifest_info = archive.getinfo(MANIFEST_PATH)
    if manifest_info.file_size > MAX_MANIFEST_BYTES:
        raise ValidationError("transport manifest exceeds its byte limit")
    try:
        import json

        manifest_raw = archive.read(MANIFEST_PATH)
        manifest = _validate_manifest(json.loads(manifest_raw.decode("utf-8")), package_kind)
    except (UnicodeDecodeError, ValueError, KeyError) as exc:
        raise ValidationError(f"invalid transport manifest: {exc}") from exc
    if canonical_bytes(manifest, newline=True) != manifest_raw:
        raise ValidationError("transport manifest is not canonical JSON")
    declared = {entry["path"]: entry for entry in manifest["files"]}
    actual = names - {MANIFEST_PATH}
    if set(declared) != actual:
        missing = sorted(set(declared) - actual)
        unexpected = sorted(actual - set(declared))
        raise ValidationError(
            f"transport closed-world mismatch; missing={missing}, unexpected={unexpected}"
        )
    if [info.filename for info in infos] != [MANIFEST_PATH, *sorted(declared)]:
        raise ValidationError("transport ZIP entry order is not canonical")
    contents: dict[str, bytes] = {}
    for path, entry in sorted(declared.items()):
        hasher = hashlib.sha256()
        observed_size = 0
        captured = bytearray() if capture_paths is None or path in capture_paths else None
        with archive.open(path, "r") as stream:
            while chunk := stream.read(CHUNK_BYTES):
                observed_size += len(chunk)
                hasher.update(chunk)
                if captured is not None:
                    captured.extend(chunk)
        if observed_size != entry["byte_size"]:
            raise ValidationError(f"{path}: declared byte size mismatch")
        if f"sha256:{hasher.hexdigest()}" != entry["content_digest"]:
            raise ValidationError(f"{path}: declared digest mismatch")
        if captured is not None:
            contents[path] = bytes(captured)
    return manifest, contents


def verify_zip_bytes(
    data: bytes,
    *,
    limits: ArchiveLimits,
    package_kind: str | None = None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Verify in-memory archive structure and every declared byte."""

    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            return _verify_archive(
                archive,
                archive_size=len(data),
                limits=limits,
                package_kind=package_kind,
                capture_paths=None,
            )
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValidationError(f"invalid transport ZIP: {exc}") from exc


def verify_zip(
    path: Path,
    *,
    limits: ArchiveLimits,
    package_kind: str | None = None,
    capture_paths: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, bytes], str]:
    if path.is_symlink():
        raise ValidationError(f"transport package must not be a symbolic link: {path}")
    try:
        size = path.stat().st_size
        with zipfile.ZipFile(path, "r") as archive:
            manifest, contents = _verify_archive(
                archive,
                archive_size=size,
                limits=limits,
                package_kind=package_kind,
                capture_paths=capture_paths,
            )
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValidationError(f"invalid transport ZIP {path}: {exc}") from exc
    return manifest, contents, digest_path(path)


def extract_verified_zip(
    path: Path,
    output: Path,
    *,
    limits: ArchiveLimits,
    package_kind: str | None = None,
) -> tuple[dict[str, Any], str]:
    manifest, contents, archive_digest = verify_zip(path, limits=limits, package_kind=package_kind)
    if output.exists() and any(output.iterdir()):
        raise ValidationError(f"normalized output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / MANIFEST_PATH).write_bytes(canonical_bytes(manifest, newline=True))
    root = output.resolve()
    for logical, payload in sorted(contents.items()):
        target = root.joinpath(*logical.split("/"))
        try:
            target.resolve().relative_to(root)
        except ValueError as exc:
            raise ValidationError(f"unsafe extraction target: {logical}") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return manifest, archive_digest

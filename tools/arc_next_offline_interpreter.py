"""Materialize a pinned, separately mounted CPython without network or execution.

The notebook host may be CPython 3.13; the unchanged wheel closure needs 3.12.
Only the approved Astral python-build-standalone release is accepted. A caller
must additionally pin the complete manifest digest. The archive and every
installed file are verified before an executable is returned. No target Python,
package manager, shell, compiler, or subprocess is run by this module.

The destination is a final, private writable path, never an input mount. It is
not relocatable after preparation: its two build configuration files contain
that path. Interrupted or changed trees fail closed instead of being repaired.
Callers MUST launch Python with -B (and their existing -I -S network guard) to
avoid changing the verified base interpreter. Create venvs outside this tree.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import struct
import tarfile
from typing import Any


ARCHIVE_NAME = "cpython-3.12.15+20261003-x86_64-unknown-linux-gnu-install_only.tar.gz"
# Kaggle auto-expands recognized archive suffixes. Preserve identical upstream
# bytes using a conservative transport filename; Kaggle strips plus signs.
# gzip is opened explicitly below.
STORED_ARCHIVE_NAME = ARCHIVE_NAME.replace("+", "-") + ".bin"
ARCHIVE_SHA256 = "f937814031eab4698ca6d07ec606ede1825768f3f3e99af76d9db3900bee03c5"
ARCHIVE_BYTES = 66924371
SOURCE_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/"
              "20261003/cpython-3.12.15%2B20261003-x86_64-unknown-linux-gnu-install_only.tar.gz")
MANIFEST_NAME = "interpreter-manifest.json"
RECEIPT_NAME = "interpreter-receipt.json"
INCOMPLETE_NAME = ".interpreter-incomplete"
FORMAT = "irisx/arc-next-offline-interpreter-v1"
TARGET = {"implementation": "CPython", "python": "3.12.15", "system": "Linux",
          "machine": "x86_64", "glibc_minimum": "2.28", "upstream_glibc_minimum": "2.17"}
EXECUTABLE = "python/bin/python3.12"
SYSCONFIG = "python/lib/python3.12/_sysconfigdata__linux_x86_64-linux-gnu.py"
MAKEFILE = "python/lib/python3.12/config-3.12-x86_64-linux-gnu/Makefile"
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_SAFE_DEST = re.compile(r"/[A-Za-z0-9_./-]+\Z")


class OfflineInterpreterError(ValueError):
    """Unverified interpreter bytes or an unsafe/incompatible host or path."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OfflineInterpreterError(message)


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _path(value: str | Path, *, exists: bool = True, directory: bool = False) -> Path:
    path = Path(value)
    _require(".." not in path.parts, "Path traversal is forbidden")
    path = path.absolute()
    for item in (path, *path.parents):
        _require(not item.is_symlink(), "Symlink input/destination ancestor: " + str(item))
    if exists:
        _require(path.is_dir() if directory else path.is_file(), "Missing local path: " + str(path))
    return path


def _relative(value: str) -> str:
    _require(isinstance(value, str) and bool(value) and "\\" not in value
             and not any(ord(c) < 32 for c in value), "Unsafe relative path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and not {".", "..", ""}.intersection(value.split("/"))
             and str(path) == value, "Unsafe relative path: " + value)
    return value


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out = {}
    for key, value in pairs:
        _require(key not in out, "Duplicate JSON key: " + key)
        out[key] = value
    return out


def _json(data: bytes) -> dict[str, Any]:
    try:
        value = json.loads(data, object_pairs_hook=_unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OfflineInterpreterError("Invalid JSON") from exc
    _require(isinstance(value, dict), "Expected JSON object")
    return value


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _host() -> dict[str, str]:
    system, machine = platform.system(), platform.machine()
    libc, version = platform.libc_ver()
    if libc != "glibc":
        try:
            libc, version = (os.confstr("CS_GNU_LIBC_VERSION") or "").split(" ", 1)
        except (AttributeError, OSError, ValueError):
            pass
    _require(system == "Linux" and machine == "x86_64", "Interpreter requires Linux x86_64")
    _require(libc == "glibc" and re.fullmatch(r"\d+\.\d+(?:\.\d+)*", version) is not None
             and tuple(map(int, version.split("."))) >= (2, 28),
             "Unchanged wheel closure requires glibc >= 2.28")
    return {"system": system, "machine": machine, "libc": libc, "glibc": version}


def _member_record(member: tarfile.TarInfo, archive: tarfile.TarFile) -> dict[str, Any]:
    name = _relative(member.name)
    _require(name.startswith("python/"), "Archive member outside python prefix")
    _require(not member.mode & ~0o777, "Special archive permission bits forbidden")
    _require(not member.pax_headers, "PAX member overrides are forbidden")
    if member.isreg():
        _require(0 <= member.size <= 256 * 1024 * 1024, "Oversized archive member")
        stream = archive.extractfile(member)
        _require(stream is not None, "Missing archive member body")
        digest = hashlib.sha256()
        size = 0
        header = b""
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            if not header:
                header = block[:64]
            size += len(block)
            digest.update(block)
        _require(size == member.size, "Truncated archive member")
        if header.startswith(b"\x7fELF") or name == EXECUTABLE:
            _require(len(header) >= 20 and header[:6] == b"\x7fELF\x02\x01"
                     and struct.unpack("<H", header[18:20])[0] == 62,
                     "Interpreter archive contains a non-x86_64 ELF")
        return {"kind": "file", "bytes": size, "sha256": digest.hexdigest(),
                "mode": 0o755 if member.mode & 0o111 else 0o644}
    _require(member.issym() and member.size == 0, "Only regular files/internal symlinks are accepted")
    target = member.linkname
    _require(bool(target) and not target.startswith("/") and "\\" not in target
             and not any(ord(c) < 32 for c in target), "Unsafe symlink target")
    return {"kind": "symlink", "target": target}


def _check_members(members: dict[str, Any]) -> None:
    _require(0 < len(members) < 20000, "Invalid archive member count")
    directories = set()
    for name in members:
        _relative(name)
        _require(name.startswith("python/"), "Member outside python prefix")
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
    _require(not directories.intersection(members), "Member is also an archive parent")
    for name, record in members.items():
        _require(isinstance(record, dict), "Invalid member record")
        if record.get("kind") == "file":
            _require(set(record) == {"kind", "bytes", "sha256", "mode"}
                     and type(record["bytes"]) is int and 0 <= record["bytes"] <= 256 * 1024 * 1024
                     and isinstance(record["sha256"], str) and _HASH.fullmatch(record["sha256"]) is not None
                     and record["mode"] in (0o644, 0o755), "Invalid regular-file record")
            continue
        _require(set(record) == {"kind", "target"} and record.get("kind") == "symlink",
                 "Invalid symlink record")
        visited = set()
        current = name
        while members[current]["kind"] == "symlink":
            _require(current not in visited, "Symlink cycle")
            visited.add(current)
            target = members[current]["target"]
            _require(isinstance(target, str) and bool(target) and not target.startswith("/")
                     and "\\" not in target and not any(ord(c) < 32 for c in target), "Unsafe symlink")
            parts = list(PurePosixPath(current).parent.parts)
            for part in target.split("/"):
                if part == "..":
                    _require(len(parts) > 1, "Symlink escapes interpreter prefix")
                    parts.pop()
                elif part not in ("", "."):
                    parts.append(part)
            current = "/".join(parts)
            _require(current in members, "Dangling or directory symlink forbidden")
    _require(sum(x.get("bytes", 0) for x in members.values()) <= 512 * 1024 * 1024,
             "Oversized unpacked interpreter")
    for name in (EXECUTABLE, SYSCONFIG, MAKEFILE, "python/include/python3.12/Python.h",
                 "python/lib/libpython3.12.so.1.0", "python/lib/python3.12/LICENSE.txt"):
        _require(name in members and members[name]["kind"] == "file", "Missing required interpreter file: " + name)
    _require(members[EXECUTABLE]["mode"] == 0o755, "Interpreter is not executable")


def _archive_records(path: Path) -> dict[str, Any]:
    records = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            _require(member.name not in records, "Duplicate archive member")
            _require(len(records) < 20000, "Too many archive members")
            records[member.name] = _member_record(member, archive)
    _check_members(records)
    return records


def _asset(asset_root: str | Path, expected_manifest_sha256: str) -> tuple[Path, dict[str, Any]]:
    _require(isinstance(expected_manifest_sha256, str) and _HASH.fullmatch(expected_manifest_sha256) is not None,
             "A pinned interpreter manifest SHA256 is required")
    root = _path(asset_root, directory=True)
    manifest_path = _path(root / MANIFEST_NAME)
    data = manifest_path.read_bytes()
    _require(_sha_bytes(data) == expected_manifest_sha256, "Interpreter manifest hash mismatch")
    manifest = _json(data)
    _require(set(manifest) == {"format", "target", "archive", "members", "companions"}
             and manifest["format"] == FORMAT and manifest["target"] == TARGET, "Unsupported interpreter manifest")
    _require(manifest["archive"] == {"filename": STORED_ARCHIVE_NAME, "upstream_filename": ARCHIVE_NAME, "bytes": ARCHIVE_BYTES,
             "sha256": ARCHIVE_SHA256, "source_url": SOURCE_URL}, "Unapproved interpreter archive")
    _check_members(manifest["members"])
    companions = manifest["companions"]
    _require(isinstance(companions, dict) and "source-receipt.json" in companions
             and any(x.startswith("licenses/") for x in companions), "Missing source/license companions")
    expected = {MANIFEST_NAME, STORED_ARCHIVE_NAME}
    for name, record in companions.items():
        _relative(name)
        _require(name not in expected and not name.startswith("python/"), "Conflicting companion path")
        expected.add(name)
        path = _path(root / name)
        _require(set(record) == {"bytes", "sha256"} and path.stat().st_size == record["bytes"]
                 and _sha(path) == record["sha256"], "Companion hash mismatch: " + name)
    actual = set()
    for path in root.rglob("*"):
        _require(not path.is_symlink(), "Symlink in interpreter asset")
        if path.is_file():
            _require(stat.S_ISREG(path.lstat().st_mode), "Nonregular asset file")
            actual.add(path.relative_to(root).as_posix())
        else:
            _require(path.is_dir(), "Special file in interpreter asset")
    _require(actual == expected, "Unexpected/missing interpreter asset files")
    archive = _path(root / STORED_ARCHIVE_NAME)
    _require(archive.stat().st_size == ARCHIVE_BYTES and _sha(archive) == ARCHIVE_SHA256,
             "Interpreter archive hash/size mismatch")
    return root, manifest


def _relocated(data: bytes, name: str, prefix: Path) -> bytes:
    """Narrow, deterministic install-prefix fixup; never eval imported code."""
    text = data.decode("utf-8")
    if name == SYSCONFIG:
        tree = ast.parse(text)
        _require(len(tree.body) == 1 and isinstance(tree.body[0], ast.Assign)
                 and len(tree.body[0].targets) == 1
                 and isinstance(tree.body[0].targets[0], ast.Name)
                 and tree.body[0].targets[0].id == "build_time_vars", "Unexpected sysconfig source")
        values = ast.literal_eval(tree.body[0].value)
        _require(isinstance(values, dict) and values.get("prefix") == "/install"
                 and values.get("LIBDIR") == "/install/lib", "Unexpected sysconfig build prefix")
        values = {key: re.sub(r"(?<![\w./-])/install(?=/|$|[\s'\"])", str(prefix), value)
                  if isinstance(value, str) else value
                  for key, value in values.items()}
        # The original AR refers to Astral's unavailable build toolchain.
        _require(values.get("AR") == "/tools/llvm/bin/llvm-ar", "Unexpected build archiver")
        values["AR"] = "ar"
        # Match uv's managed-Python compiler normalization; system cc/c++ avoid
        # depending on the build host's clang toolchain. Keep all other flags.
        for key in ("BLDSHARED", "CC", "LDSHARED", "LINKCC"):
            if isinstance(values.get(key), str):
                values[key] = re.sub(r"(?<!\S)clang(?!\S)", "cc", values[key])
        for key in ("CXX", "LDCXXSHARED"):
            if isinstance(values.get(key), str):
                values[key] = re.sub(r"(?<!\S)clang\+\+(?!\S)", "c++", values[key])
        values["PYTHON_BUILD_STANDALONE"] = 1
        return ("# Relocated offline from the SHA256-pinned Astral distribution.\n"
                "build_time_vars = " + repr(values) + "\n").encode()
    _require(name == MAKEFILE and re.search(r"^prefix=\s*/install$", text, re.M) is not None,
             "Unexpected Makefile build prefix")
    text = re.sub(r"(?<![\w./-])/install(?=/|$|[\s'\"])", str(prefix), text)
    text = text.replace("/tools/llvm/bin/llvm-ar", "ar")
    text = re.sub(r"^(CC=\s*)clang(?=\s|$)", r"\1cc", text, flags=re.M)
    text = re.sub(r"^(CXX=\s*)clang\+\+(?=\s|$)", r"\1c++", text, flags=re.M)
    return text.encode()


def _expected_files(root: Path, manifest: dict[str, Any], destination: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    records = {name: dict(record) for name, record in manifest["members"].items()}
    transformed = {}
    with tarfile.open(root / STORED_ARCHIVE_NAME, "r:gz") as archive:
        for name in (SYSCONFIG, MAKEFILE):
            stream = archive.extractfile(name)
            _require(stream is not None, "Missing relocation source")
            original = stream.read()
            _require(_sha_bytes(original) == records[name]["sha256"], "Relocation source mismatch")
            data = _relocated(original, name, destination / "python")
            transformed[name] = data
            records[name].update(bytes=len(data), sha256=_sha_bytes(data))
    return records, transformed


def _verify_tree(destination: Path, records: dict[str, Any], *, ready: bool) -> None:
    root_info = destination.lstat()
    _require(stat.S_ISDIR(root_info.st_mode) and stat.S_IMODE(root_info.st_mode) == 0o700
             and root_info.st_uid == os.geteuid(), "Prepared interpreter root must remain private/owned")
    expected_dirs = {str(p) for name in records for p in PurePosixPath(name).parents if str(p) != "."}
    found = set()
    for base, dirs, files in os.walk(destination, followlinks=False):
        for leaf in dirs + files:
            path = Path(base) / leaf
            relative = path.relative_to(destination).as_posix()
            info = path.lstat()
            _require(info.st_uid == os.geteuid(), "Prepared interpreter entry ownership changed")
            if relative in expected_dirs:
                _require(stat.S_ISDIR(info.st_mode) and not stat.S_IMODE(info.st_mode) & 0o022,
                         "Unexpected interpreter parent type/permissions")
                found.add(relative)
                continue
            if relative in (RECEIPT_NAME, INCOMPLETE_NAME):
                _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Unsafe preparation marker")
                _require(relative == (RECEIPT_NAME if ready else INCOMPLETE_NAME), "Interrupted interpreter preparation")
                continue
            _require(relative in records, "Unexpected file in prepared interpreter: " + relative)
            record = records[relative]
            if record["kind"] == "symlink":
                _require(stat.S_ISLNK(info.st_mode) and os.readlink(path) == record["target"], "Prepared symlink mismatch")
            else:
                _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                         and stat.S_IMODE(info.st_mode) == record["mode"]
                         and info.st_size == record["bytes"] and _sha(path) == record["sha256"],
                         "Prepared interpreter file mismatch: " + relative)
            found.add(relative)
    _require(found == set(records) | expected_dirs, "Missing prepared interpreter files")


def _receipt(destination: Path, manifest_sha: str, manifest: dict[str, Any], records: dict[str, Any]) -> dict[str, Any]:
    return {"format": FORMAT + "-receipt", "python_executable": str(destination / EXECUTABLE),
            "python_prefix": str(destination / "python"), "manifest_sha256": manifest_sha,
            "archive_sha256": ARCHIVE_SHA256, "executable_sha256": records[EXECUTABLE]["sha256"],
            "receipt_path": str(destination / RECEIPT_NAME), "target": TARGET,
            "relocations": {name: {"before_sha256": manifest["members"][name]["sha256"],
                                    "after_sha256": records[name]["sha256"]} for name in (SYSCONFIG, MAKEFILE)},
            "verified_member_count": len(records), "network_calls": 0, "interpreter_executions": 0}


def validate_interpreter(asset_root: str | Path, expected_manifest_sha256: str,
                         destination: str | Path) -> dict[str, Any]:
    """Fully revalidate immutable assets and the existing prepared tree; run nothing."""
    _host()
    root, manifest = _asset(asset_root, expected_manifest_sha256)
    destination = _path(destination, directory=True)
    _require(_SAFE_DEST.fullmatch(str(destination)) is not None, "Unsafe build-prefix characters")
    _require(not (destination / INCOMPLETE_NAME).exists(), "Interrupted interpreter preparation")
    records, _ = _expected_files(root, manifest, destination)
    _verify_tree(destination, records, ready=True)
    expected = _receipt(destination, expected_manifest_sha256, manifest, records)
    receipt = _path(destination / RECEIPT_NAME)
    _require(receipt.read_bytes() == _json_bytes(expected), "Prepared interpreter receipt mismatch")
    return expected


def prepare_interpreter(asset_root: str | Path, expected_manifest_sha256: str,
                        destination: str | Path) -> dict[str, Any]:
    """Safely extract into the final destination, or fully validate cached reuse."""
    _host()
    root, manifest = _asset(asset_root, expected_manifest_sha256)
    destination = _path(destination, exists=False)
    _require(_SAFE_DEST.fullmatch(str(destination)) is not None, "Unsafe build-prefix characters")
    _require(not destination.is_relative_to(root) and not root.is_relative_to(destination),
             "Interpreter destination must be separate from immutable input")
    if destination.exists():
        return validate_interpreter(root, expected_manifest_sha256, destination)
    _require(destination.parent.is_dir(), "Interpreter destination parent must already exist")
    _require(_archive_records(root / STORED_ARCHIVE_NAME) == manifest["members"], "Archive member manifest mismatch")
    records, transformed = _expected_files(root, manifest, destination)
    destination.mkdir(mode=0o700)
    destination.chmod(0o700)
    (destination / INCOMPLETE_NAME).write_bytes(b"Preparation is incomplete; do not execute.\n")
    # Files are written before symlinks, with exclusive create. tar.extract* is
    # never used to materialize a path, permission, link, device, or ownership.
    with tarfile.open(root / STORED_ARCHIVE_NAME, "r:gz") as archive:
        for member in archive:
            if not member.isreg():
                continue
            path = destination / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            _require(stream is not None, "Missing extraction body")
            with path.open("xb") as out:
                if member.name in transformed:
                    out.write(transformed[member.name])
                else:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        out.write(block)
            path.chmod(records[member.name]["mode"])
    for name, record in records.items():
        if record["kind"] == "symlink":
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(record["target"])
    # mkdir(parents=True) applies the process umask to intermediate parents.
    # Normalize our newly created directories without relaxing cached checks.
    directories = {str(p) for name in records for p in PurePosixPath(name).parents if str(p) != "."}
    for relative in directories:
        path = destination / relative
        _require(stat.S_ISDIR(path.lstat().st_mode), "Extraction directory changed type")
        path.chmod(0o755)
    _verify_tree(destination, records, ready=False)
    receipt = _receipt(destination, expected_manifest_sha256, manifest, records)
    with (destination / RECEIPT_NAME).open("xb") as stream:
        stream.write(_json_bytes(receipt))
        stream.flush()
        os.fsync(stream.fileno())
    (destination / INCOMPLETE_NAME).unlink()
    return validate_interpreter(root, expected_manifest_sha256, destination)

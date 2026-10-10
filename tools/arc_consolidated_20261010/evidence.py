"""Immutable stage snapshots and a global, stopped-owner evidence archive."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
import zipfile

from .assets import canonical


def fsync_directory(path):
    """Return False where the OS cannot durably flush directory entries."""
    if os.name != "posix":
        return False
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


def safe_root(root):
    root = Path(root)
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError("symlink output root")
    missing = []
    cursor = root
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        fsync_directory(directory.parent)
    return root


def write_new(path, value):
    """Write a new immutable record; an existing identical record is reusable."""
    path = Path(path)
    safe_root(path.parent)
    raw = canonical(value) + b"\n"
    if path.is_symlink():
        raise ValueError("symlink receipt")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("refusing changed immutable receipt: " + path.name)
        return path
    # A crash before the rename leaves a clearly named partial file. Never
    # guess that those bytes constitute a complete receipt.
    tmp = path.with_name(path.name + ".partial")
    with tmp.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fsync_directory(path.parent)
    return path


def stage_snapshot(root, stage_id, payload, *, session_id):
    if not stage_id.replace("-", "").isalnum():
        raise ValueError("unsafe stage identity")
    if not str(session_id).replace("-", "").isalnum():
        raise ValueError("unsafe session identity")
    return write_new(Path(root) / "stages" / (stage_id + "-" + str(session_id) + ".json"), {
        "stage_id": stage_id, "session_id": session_id,
        "closure_scope": "stage receipts only; model service may remain loaded",
        "payload": payload,
    })


def seal_and_archive(root, *, stopped, summary, session_id):
    """Snapshot only after every owned worker/model explicitly acknowledges stop.

    Journal may later append accounting for archive time. The snapshot names
    the exact journal prefix it includes; it does not pretend to include its
    own future completion record.
    """
    root = safe_root(root)
    expected = {"model_owner_stopped", "verifier_descendants_stopped"}
    if set(stopped) != expected or any(v is not True for v in stopped.values()):
        raise ValueError("global seal requires all owned processes stopped")
    started = time.monotonic()
    artifacts = safe_root(root / "archives")
    final = artifacts / ("evidence-" + str(session_id) + ".zip")
    if final.exists():
        raise ValueError("archive identity already consumed")
    inventory = {}
    paths = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink evidence member")
        if not path.is_file() or path.is_relative_to(artifacts):
            continue
        if path.name.endswith((".partial", ".lock")):
            continue
        name = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        inventory[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        paths.append((name, raw))
    seal = {"format": "irisx/consolidated-global-seal-v1", "session_id": session_id,
            "processes": stopped, "files": inventory, "summary": summary,
            "directory_fsync_supported": os.name == "posix",
            "scope": "immutable snapshot; archive completion accounting appended outside this snapshot",
            "billing": "Program return does not stop VM billing"}
    tmp = final.with_suffix(".zip.partial")
    with tmp.open("xb") as file:
        with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in paths:
                archive.writestr(name, raw)
            archive.writestr("global-seal.json", canonical(seal) + b"\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(tmp, final)
    fsync_directory(artifacts)
    with zipfile.ZipFile(final) as archive:
        if archive.testzip() is not None:
            raise ValueError("archive CRC verification failed")
        for name, expected_file in inventory.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected_file["sha256"]:
                raise ValueError("archive readback hash failed")
    return {"archive": str(final), "sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "seconds": time.monotonic() - started, "files": len(inventory),
            "directory_fsync_supported": os.name == "posix"}

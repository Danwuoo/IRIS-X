"""Stdlib-only truth-free ABC result ZIP finalizer and verifier."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import zipfile


def write_abc_zip(work: Path, target: Path, run_id: str, plan_digest: str) -> dict:
    if target.exists():
        raise RuntimeError("ABC result ZIP already exists")
    root_names = {"plan.json", "visible.json", "training-evidence.json", "startup-events.jsonl",
                  "hardware-raw.json", "hardware-inventory.json", "hardware.json",
                  "mount-preflight.json", "aggregate-terminal.json", "worker-stdout.log", "worker-stderr.log"}
    files = []
    for path in sorted(work.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("ABC evidence symlink")
        if not path.is_file():
            continue
        name = path.relative_to(work).as_posix()
        if name in root_names or name.startswith("worker/") and path.suffix in {".json", ".jsonl", ".log"}:
            if path.stat().st_size > 16 * 1024 * 1024:
                raise RuntimeError("ABC member exceeds size ceiling")
            files.append((name, path))
    inventory = {name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "bytes": path.stat().st_size} for name, path in files}
    if sum(v["bytes"] for v in inventory.values()) > 64 * 1024 * 1024:
        raise RuntimeError("ABC ZIP exceeds 64 MiB")
    manifest = {"format": "irisx/nvarc-abc-analysis-zip-v1", "run_id": run_id,
                "plan_digest": plan_digest, "files": inventory,
                "contains_evaluator_truth": False,
                "scoring": "unknown until separate authorized evaluator analysis"}
    temporary = target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for name, path in files:
            archive.write(path, name)
        archive.writestr("analysis-manifest.json", json.dumps(manifest, sort_keys=True,
                                                              ensure_ascii=False))
    verify_abc_zip(temporary, run_id=run_id, plan_digest=plan_digest)
    os.replace(temporary, target)
    return {"path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "artifacts": len(inventory)}


def verify_abc_zip(path: Path, *, run_id: str, plan_digest: str) -> dict:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ABC ZIP CRC failure")
        names = archive.namelist()
        if len(names) != len(set(names)) or "analysis-manifest.json" not in names:
            raise RuntimeError("ABC ZIP duplicate or missing manifest")
        manifest = json.loads(archive.read("analysis-manifest.json"))
        if (manifest.get("format") != "irisx/nvarc-abc-analysis-zip-v1" or
                manifest.get("run_id") != run_id or manifest.get("plan_digest") != plan_digest or
                manifest.get("contains_evaluator_truth") is not False or
                set(names) != set(manifest["files"]) | {"analysis-manifest.json"}):
            raise RuntimeError("ABC ZIP identity or inventory differs")
        for name, binding in manifest["files"].items():
            if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                raise RuntimeError("ABC ZIP unsafe path")
            data = archive.read(name)
            if len(data) != binding["bytes"] or hashlib.sha256(data).hexdigest() != binding["sha256"]:
                raise RuntimeError("ABC ZIP member digest differs")
        return manifest

"""Small digest-bound Qwen notebook source bundle, independent of a checkout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


FORMAT = "irisx/nvarc-qwen-runtime-source-v1"
NOTEBOOK = "kaggle-qwen/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb"
NOTEBOOK_SHA256 = "506b85db66f9949022e87935ccb06a73fd78cb690883bd600bfb5c7d36c2b3af"
FILES = {"source-manifest.json", NOTEBOOK}


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_bundle(root: Path, expected_digest: str) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("source bundle directory missing or symlinked")
    paths = list(root.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValidationError("source bundle contains symlink")
    actual = {path.relative_to(root).as_posix() for path in paths if path.is_file()}
    if actual != FILES | {"bundle-manifest.json"}:
        raise ValidationError("source bundle inventory differs")
    manifest = json.loads((root / "bundle-manifest.json").read_bytes())
    if (manifest.get("format") != FORMAT or digest_value(manifest) != expected_digest or
            set(manifest.get("files", {})) != FILES):
        raise ValidationError("source bundle identity differs")
    for name in sorted(FILES):
        payload = (root / name).read_bytes()
        if manifest["files"][name] != {"sha256": _sha(payload), "bytes": len(payload)}:
            raise ValidationError("source bundle member differs: " + name)
    binding = json.loads((root / "source-manifest.json").read_bytes())
    qwen = binding.get("notebooks", {}).get("qwen", {})
    if (binding.get("format") != "irisx/nvarc-source-manifest-v1" or
            qwen.get("path") != NOTEBOOK or qwen.get("sha256") != NOTEBOOK_SHA256 or
            manifest["files"][NOTEBOOK]["sha256"] != NOTEBOOK_SHA256):
        raise ValidationError("source bundle pinned notebook differs")
    notebook = json.loads((root / NOTEBOOK).read_bytes())
    if any(cell.get("outputs") for cell in notebook["cells"]):
        raise ValidationError("source runtime notebook must not contain output cells")
    return manifest


def build_bundle(source: Path, source_manifest: Path, output: Path) -> dict:
    if output.exists():
        raise ValidationError("new source bundle directory required")
    payloads = {"source-manifest.json": source_manifest.read_bytes(),
                NOTEBOOK: (source / NOTEBOOK).read_bytes()}
    if _sha(payloads[NOTEBOOK]) != NOTEBOOK_SHA256:
        raise ValidationError("pinned notebook changed before source packaging")
    manifest = {"format": FORMAT, "files": {
        name: {"sha256": _sha(payload), "bytes": len(payload)}
        for name, payload in payloads.items()}}
    for name, payload in payloads.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (output / "bundle-manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    digest = digest_value(manifest)
    verify_bundle(output, digest)
    return {"bundle_digest": digest, "notebook_sha256": NOTEBOOK_SHA256,
            "source_manifest_sha256": _sha(payloads["source-manifest.json"])}

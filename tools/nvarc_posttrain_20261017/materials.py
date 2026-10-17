"""Independently pinned public author weights; no executable remote code."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct

from tools.arc2_goal_sprint_20261017.data import canonical


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def model_pin(variant):
    pins = json.loads(Path(__file__).with_name("model-pins.json").read_bytes())
    if variant not in pins:
        raise ValueError("only explicitly selected official NVARC 2b/4b releases are admitted")
    return pins[variant]


def verify_model(root, variant):
    root = Path(root).absolute()
    if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("regular model directory required")
    pin = model_pin(variant)
    # The locally generated provenance receipt is not a model input. Anything
    # else extra, including remote Python code, is rejected before HF loading.
    extra = {p.name for p in root.iterdir()} - set(pin["files"])
    if extra - {"metadata-receipt.json"}:
        raise ValueError("unmanifested model material")
    tensors, total = {}, 0
    for name, row in pin["files"].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"] or sha_file(path) != row["sha256"]:
            raise ValueError("official model file digest/length differs: " + name)
        if name.endswith(".safetensors"):
            with path.open("rb") as stream:
                size = struct.unpack("<Q", stream.read(8))[0]
                if not 0 < size < 16 * 1024**2:
                    raise ValueError("bounded safetensors header required")
                header = json.loads(stream.read(size))
            for key, value in header.items():
                if key == "__metadata__":
                    continue
                if key in tensors or value["dtype"] != "BF16":
                    raise ValueError("unique BF16 base tensors required")
                tensors[key] = name
                total += math.prod(value["shape"])
    if total != pin["parameters"]:
        raise ValueError("official tensor parameter count differs")
    if variant == "4b":
        if json.loads((root / "model.safetensors.index.json").read_bytes())["weight_map"] != tensors:
            raise ValueError("official shard index differs")
    return {**pin, "material_identity_sha256": hashlib.sha256(canonical(pin)).hexdigest(),
            "verified_parameters": total, "verified_tensors": len(tensors), "remote_code_executed": False}

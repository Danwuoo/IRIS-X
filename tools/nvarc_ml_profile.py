"""Strict optional NVARC ML profile; never reports a missing dependency as pass."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    required = ("torch", "transformers", "peft", "safetensors")
    versions = {}
    missing = []
    for package in required:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
    report = {"python": sys.executable, "versions": versions, "missing": missing}
    print(json.dumps(report, indent=2))
    if missing:
        print("BLOCKED: missing optional ML dependencies: " + ", ".join(missing), file=sys.stderr)
        return 2
    import torch
    from transformers import Qwen3_5ForConditionalGeneration
    print("architecture:", Qwen3_5ForConditionalGeneration.__name__)
    print("torch distributed:", torch.distributed.is_available())
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    return subprocess.call([sys.executable, "-m", "unittest",
                            "tests.test_arc_nvarc_ml", "tests.test_arc_nvarc_distributed", "-v"],
                           env=env)


if __name__ == "__main__":
    raise SystemExit(main())

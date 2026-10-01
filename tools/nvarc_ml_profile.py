"""Strict optional NVARC ML profile; never reports a missing dependency as pass."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    required = ("torch", "transformers", "peft", "safetensors", "numpy",
                "datasets", "argdantic", "hydra-core", "numba",
                "adam-atan2-pytorch", "coolname", "einops")
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
    source_check = subprocess.call([sys.executable,
                                    str(Path(__file__).resolve().with_name("nvarc_source.py")),
                                    "verify"], env=env)
    if source_check:
        return source_check
    return subprocess.call([sys.executable, "-m", "unittest",
                            "tests.test_arc_nvarc_ml", "tests.test_arc_nvarc_distributed",
                            "tests.nvarc_source_differential", "tests.nvarc_m2_m3_strict",
                            "tests.nvarc_fsdp_sft_strict", "tests.nvarc_deployment_strict",
                            "tests.nvarc_combined_strict", "tests.nvarc_method_strict",
                            "tests.nvarc_packing_strict", "tests.nvarc_sft_step_strict",
                            "tests.nvarc_source_stream_strict", "tests.nvarc_source_sft_strict", "-v"],
                           env=env)


if __name__ == "__main__":
    raise SystemExit(main())

"""Build an offline, unapproved one-kernel Qwen3.5 GPU compatibility draft.

This utility only writes local files. It has no Kaggle client or network path.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import irisx_build_backend as build


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/draft-gpu-a.json"
OUT = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/gpu-a"


def stage(out: Path = OUT, config: Path = CONFIG) -> dict:
    manifest = json.loads(config.read_bytes())
    if manifest.get("approved") is not False or manifest.get("owner_authorization") is not None:
        raise ValueError("local draft must remain unapproved")
    if manifest.get("run_id") != "nvarc-acceptance-gpu-a-001":
        raise ValueError("unexpected draft run identity")
    wheel_dir = out / "wheel"
    wheel_name = build.build_wheel(str(wheel_dir))
    wheel_bytes = (wheel_dir / wheel_name).read_bytes()
    wheel_sha = hashlib.sha256(wheel_bytes).hexdigest()
    manifest_bytes = config.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    code = f'''import base64, hashlib, json, os, pathlib, subprocess, sys
MANIFEST = base64.b64decode("{base64.b64encode(manifest_bytes).decode('ascii')}")
WHEEL = base64.b64decode("{base64.b64encode(wheel_bytes).decode('ascii')}")
if hashlib.sha256(MANIFEST).hexdigest() != "{manifest_sha}":
    raise RuntimeError("embedded manifest digest differs")
if hashlib.sha256(WHEEL).hexdigest() != "{wheel_sha}":
    raise RuntimeError("embedded wheel digest differs")
manifest = json.loads(MANIFEST)
if manifest.get("approved") is not True or not manifest.get("owner_authorization"):
    raise RuntimeError("GPU draft is not owner-approved")
if any(value == "UNBOUND" for value in manifest["dependencies"].values()):
    raise RuntimeError("GPU dependency profile is not exact")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
work = pathlib.Path("/kaggle/working")
wheel = work / "{wheel_name}"
wheel.write_bytes(WHEEL)
subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
                "--force-reinstall", str(wheel)], check=True, timeout=120)
bound = work / "nvarc-gpu-a-manifest.json"
bound.write_bytes(MANIFEST)
subprocess.run([sys.executable, "-m", "irisx.arc_nvarc_gpu_smoke", "--manifest", str(bound),
                "--output", str(work / "nvarc-gpu-a-result.json")], check=True, timeout=1500,
               env=os.environ.copy())
'''
    compile(code, "nvarc-gpu-a-notebook", "exec")
    notebook = {"cells": [{"cell_type": "code", "execution_count": None,
                            "metadata": {}, "outputs": [], "source": code.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                             "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    kernel = out / "kernel"
    kernel.mkdir(parents=True, exist_ok=True)
    (kernel / "kaggle-notebook.ipynb").write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    metadata = {"id": "DRAFT-DO-NOT-PUSH/nvarc-acceptance-gpu-a-001",
                "title": "DRAFT IRIS-X tiny Qwen3.5 GPU compatibility",
                "code_file": "kaggle-notebook.ipynb", "language": "python",
                "kernel_type": "notebook", "is_private": True, "enable_gpu": True,
                "enable_tpu": False, "enable_internet": False,
                "machine_shape": "NvidiaL4", "competition_sources": [],
                "dataset_sources": [], "kernel_sources": [], "model_sources": []}
    (kernel / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    summary = {"approved": False, "run_id": manifest["run_id"],
               "manifest_sha256": manifest_sha, "wheel_sha256": wheel_sha,
               "notebook_sha256": hashlib.sha256((kernel / "kaggle-notebook.ipynb").read_bytes()).hexdigest(),
               "kernel_metadata_sha256": hashlib.sha256((kernel / "kernel-metadata.json").read_bytes()).hexdigest(),
               "local_kernel_path": str(kernel),
               "repair_baseline_commit": manifest["repair_baseline_commit"]}
    (out / "stage-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(stage(), indent=2))

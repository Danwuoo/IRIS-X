"""Stage the compact 4B pilot privately and offline; never calls Kaggle."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import irisx_build_backend as build
from irisx.arc_nvarc_compact_pilot import (FINAL_KERNEL_ID, RUN_ID, prepare,
                                           validate_plan)
from irisx.errors import ValidationError


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
PLAN = CONFIG / "compact-complete-001.json"
VISIBLE = CONFIG / "compact-complete-visible.json"
MODEL = CONFIG / "base-model-manifest.json"
WHEELS = CONFIG / "base-wheel-manifest.json"
TEMPLATE = ROOT / "tools/nvarc_compact_notebook.py.tmpl"
DEFAULT_OUT = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/compact-complete-draft"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stage(output: Path = DEFAULT_OUT, authorization: Path | None = None) -> dict:
    if output.exists() and any(output.iterdir()):
        raise ValidationError("compact package output must be new or empty")
    summary = prepare(PLAN, VISIBLE, MODEL, WHEELS)
    draft_bytes = PLAN.read_bytes()
    plan = json.loads(draft_bytes)
    if authorization is not None:
        binding = json.loads(authorization.read_bytes())
        if (binding.get("approved") is not True or
                binding.get("draft_plan_sha256") != sha(draft_bytes) or
                binding.get("run_id") != RUN_ID or
                binding.get("kernel_id") != FINAL_KERNEL_ID or
                not isinstance(binding.get("owner_decision"), str) or
                not binding["owner_decision"].strip()):
            raise ValidationError("exact owner authorization is absent or differs")
        plan.update(approved=True, owner_authorization=binding["owner_decision"],
                    kernel_id=FINAL_KERNEL_ID)
        validate_plan(plan, approved=True)
    plan_bytes = (json.dumps(plan, sort_keys=True, separators=(",", ":")) + "\n").encode()
    wheel_dir = output / "wheel"
    wheel_name = build.build_wheel(str(wheel_dir))
    wheel_bytes = (wheel_dir / wheel_name).read_bytes()
    with zipfile.ZipFile(wheel_dir / wheel_name) as archive:
        if "irisx/arc_nvarc_compact_pilot.py" not in archive.namelist():
            raise ValidationError("staged runtime wheel omitted compact pilot")
    payload = {"plan": plan_bytes, "visible": VISIBLE.read_bytes(),
               "model_manifest": MODEL.read_bytes(), "wheel_manifest": WHEELS.read_bytes(),
               "irisx_wheel": wheel_bytes}
    encoded = {name: base64.b64encode(value).decode() for name, value in payload.items()}
    hashes = {name: sha(value) for name, value in payload.items()}
    source = TEMPLATE.read_text(encoding="utf-8")
    source = (source.replace("__PAYLOADS__", json.dumps(encoded, sort_keys=True))
                    .replace("__HASHES__", json.dumps(hashes, sort_keys=True))
                    .replace("__IRISX_WHEEL_NAME__", wheel_name))
    compile(source, "compact-pilot-notebook", "exec")
    kernel = output / "kernel"
    kernel.mkdir(parents=True, exist_ok=True)
    notebook = {"cells": [{"cell_type": "code", "execution_count": None,
                            "metadata": {}, "outputs": [],
                            "source": source.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                             "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    notebook_path = kernel / "kaggle-notebook.ipynb"
    notebook_path.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
    metadata = {"id": plan["kernel_id"], "title": "IRIS X compact 4B pilot",
                "code_file": "kaggle-notebook.ipynb", "language": "python",
                "kernel_type": "notebook", "is_private": True, "enable_gpu": True,
                "enable_tpu": False, "enable_internet": False,
                "machine_shape": "NvidiaL4", "competition_sources": [plan["competition_ref"]],
                "dataset_sources": [plan["dataset_ref"]], "kernel_sources": [],
                "model_sources": []}
    metadata_path = kernel / "kernel-metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    summary.update({"approved": plan["approved"], "kernel_id": plan["kernel_id"],
                    "draft_plan_sha256": sha(draft_bytes),
                    "plan_sha256": hashes["plan"], "visible_sha256": hashes["visible"],
                    "model_manifest_sha256": hashes["model_manifest"],
                    "wheel_manifest_sha256": hashes["wheel_manifest"],
                    "runtime_wheel_sha256": hashes["irisx_wheel"],
                    "notebook_sha256": sha(notebook_path.read_bytes()),
                    "metadata_sha256": sha(metadata_path.read_bytes()),
                    "kernel_path": str(kernel)})
    (output / "stage-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.output, args.authorization), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

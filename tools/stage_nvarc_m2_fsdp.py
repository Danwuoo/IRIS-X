"""Stage one draft private 4-L4 feasibility package locally; no provider calls."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
import irisx_build_backend as build
from irisx.arc_nvarc_m2 import load_frozen_arc_sft_data
from irisx.arc_nvarc_representation import verify_model_material
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError

CONFIG = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
MODEL = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/compact-complete-launch-003/retrieved/compact-complete-003/compact-model"
DATA = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data"
DEFAULT_OUT = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/fsdp-feasibility-draft"


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stage(output: Path = DEFAULT_OUT, authorization: Path | None = None) -> dict:
    if output.exists():
        raise ValidationError("new FSDP package output directory required")
    draft_path = CONFIG / "m2-fsdp-feasibility-draft.json"
    draft_bytes = draft_path.read_bytes()
    plan = json.loads(draft_bytes)
    if (plan["approved"] is not False or plan["run_id"] != "nvarc-m2-fsdp-feasibility-001" or
            plan["maximum_paid_usd"] != 0 or plan["maximum_optimizer_steps"] != 1):
        raise ValidationError("FSDP draft boundaries differ")
    if authorization is not None:
        binding = json.loads(authorization.read_bytes())
        if (binding.get("approved") is not True or
                binding.get("draft_plan_sha256") != sha(draft_bytes) or
                binding.get("run_id") != plan["run_id"] or
                binding.get("kernel_id") != "danielwuu/nvarc-m2-fsdp-feasibility-001" or
                binding.get("model_dataset_id") != plan["model_dataset_id"] or
                not isinstance(binding.get("owner_decision"), str) or
                not binding["owner_decision"].strip()):
            raise ValidationError("exact FSDP owner authorization is absent or differs")
        plan["approved"] = True
        plan["owner_decision"] = binding["owner_decision"]
        plan["kernel_id"] = binding["kernel_id"]
    config = json.loads((CONFIG / "m2-m3-small.json").read_bytes())
    sequences = load_frozen_arc_sft_data(config, DATA)
    data_manifest = json.loads((DATA / "manifest.json").read_bytes())
    if len(sequences) != 128 or data_manifest["train_sequence_digest"] != digest_value(sequences):
        raise ValidationError("frozen ARC sequence binding differs")
    sequence_bytes = b"".join(canonical_bytes(item, newline=True) for item in sequences)
    plan["sequences_digest"] = digest_value(sequences)
    plan["sequences_sha256"] = sha(sequence_bytes)
    plan["source_data_manifest_digest"] = digest_value(data_manifest)
    if (max(len(item["input_ids"]) for item in sequences) > plan["max_sequence_length"] or
            max(len(item["input_ids"]) for item in sequences) > plan["maximum_tokens_per_rank"]):
        raise ValidationError("source sequence exceeds FSDP token/length bound")
    material = verify_model_material(MODEL, plan["compact_material_digest"])
    wheel_manifest = json.loads((CONFIG / "base-wheel-manifest.json").read_bytes())
    if wheel_manifest.get("format") != "irisx/offline-wheel-manifest":
        raise ValidationError("offline wheel manifest differs")
    wheel_dir = output / "wheel"
    wheel_name = build.build_wheel(str(wheel_dir))
    wheel_bytes = (wheel_dir / wheel_name).read_bytes()
    with zipfile.ZipFile(wheel_dir / wheel_name) as archive:
        if "irisx/arc_nvarc_fsdp.py" not in archive.namelist():
            raise ValidationError("runtime wheel omitted FSDP entry")
    payloads = {"plan": canonical_bytes(plan, newline=True), "sequences": sequence_bytes,
                "wheel_manifest": canonical_bytes(wheel_manifest, newline=True),
                "runtime_wheel": wheel_bytes}
    hashes = {name: sha(payload) for name, payload in payloads.items()}
    encoded = {name: base64.b64encode(payload).decode() for name, payload in payloads.items()}
    template = (ROOT / "tools/nvarc_m2_fsdp_notebook.py.tmpl").read_text(encoding="utf-8")
    source = template.replace("__PAYLOADS__", json.dumps(encoded, sort_keys=True)).replace(
        "__HASHES__", json.dumps(hashes, sort_keys=True))
    compile(source, "m2-fsdp-notebook", "exec")
    kernel = output / "kernel"
    kernel.mkdir(parents=True)
    notebook = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {},
                            "outputs": [], "source": source.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                             "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    notebook_path = kernel / "kaggle-notebook.ipynb"
    notebook_path.write_bytes(canonical_bytes(notebook, newline=True))
    kernel_metadata = {"id": plan["kernel_id"], "title": plan["run_id"],
                       "code_file": notebook_path.name, "language": "python",
                       "kernel_type": "notebook", "is_private": True, "enable_gpu": True,
                       "enable_tpu": False, "enable_internet": False,
                       "machine_shape": "NvidiaL4", "competition_sources": [],
                       "dataset_sources": [plan["model_dataset_id"],
                                           "danielwuu/irisx-arc-agi-2-trial-002-smoke-001"],
                       "kernel_sources": [], "model_sources": []}
    (kernel / "kernel-metadata.json").write_bytes(canonical_bytes(kernel_metadata, newline=True))
    model_dataset = output / "model-dataset"
    compact_dataset = model_dataset / "compact-model"
    compact_dataset.mkdir(parents=True)
    for member in sorted(MODEL.iterdir()):
        if not member.is_file():
            raise ValidationError("model material contains a nonfile member")
        os.link(member, compact_dataset / member.name)
    dataset_metadata = {"title": "IRIS-X NVARC M2 compact 4B 001",
                        "id": plan["model_dataset_id"], "licenses": [{"name": "other"}],
                        "isPrivate": True}
    (model_dataset / "dataset-metadata.json").write_bytes(canonical_bytes(dataset_metadata, newline=True))
    summary = {"format": "irisx/nvarc-m2-fsdp-stage-v1", "approved": plan["approved"],
               "run_id": plan["run_id"], "draft_plan_sha256": sha(draft_bytes),
               "plan_digest": digest_value(plan), "plan_sha256": hashes["plan"],
               "source_data_manifest_digest": plan["source_data_manifest_digest"],
               "sequences_digest": plan["sequences_digest"],
               "sequences_sha256": plan["sequences_sha256"],
               "compact_material_digest": plan["compact_material_digest"],
               "compact_weight_bytes": sum(item["bytes"] for item in material["files"]
                                           if item["path"].endswith(".safetensors")),
               "runtime_wheel_sha256": hashes["runtime_wheel"],
               "notebook_sha256": sha(notebook_path.read_bytes()),
               "kernel_metadata_sha256": sha((kernel / "kernel-metadata.json").read_bytes()),
               "dataset_metadata_sha256": sha((model_dataset / "dataset-metadata.json").read_bytes()),
               "model_dataset_id": plan["model_dataset_id"],
               "wheel_dataset_id": "danielwuu/irisx-arc-agi-2-trial-002-smoke-001",
               "output": str(output), "external_calls": 0,
               "claim": "offline package only; FSDP backend unexecuted"}
    (output / "stage-summary.json").write_bytes(canonical_bytes(summary, newline=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.output, args.authorization), indent=2))


if __name__ == "__main__":
    main()

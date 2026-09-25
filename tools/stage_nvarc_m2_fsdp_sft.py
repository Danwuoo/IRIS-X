"""Build an offline, inert 4B ARC-SFT and source-solve kernel package."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import irisx_build_backend as build
from irisx.arc_nvarc_data import visible_task
from irisx.arc_nvarc_m2 import load_frozen_arc_sft_data
from irisx.arc_nvarc_representation import verify_model_material
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError

CONFIG = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
MODEL = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/compact-complete-launch-003/retrieved/compact-complete-003/compact-model"
DATA = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stage(output: Path, *, authorization: Path | None = None,
          draft_path: Path = CONFIG / "m2-fsdp-sft-draft-001.json",
          data_root: Path = DATA, model_root: Path = MODEL) -> dict:
    if output.exists():
        raise ValidationError("new FSDP SFT package directory required")
    if draft_path.resolve() not in {(CONFIG / name).resolve() for name in
                                    ("m2-fsdp-sft-draft-001.json",
                                     "m2-fsdp-sft-draft-002.json")}:
        raise ValidationError("unknown immutable FSDP SFT draft")
    draft_bytes = draft_path.read_bytes()
    plan = json.loads(draft_bytes)
    run_id = plan.get("run_id")
    if (plan.get("approved") is not False or
            run_id not in {"nvarc-m2-fsdp-sft-001", "nvarc-m2-fsdp-sft-002"} or
            plan.get("kernel_id") != "DRAFT-DO-NOT-PUSH/" + run_id or
            plan.get("maximum_paid_usd") != 0 or
            plan.get("maximum_optimizer_steps") != 8 or
            plan.get("maximum_source_generation_calls") != 4):
        raise ValidationError("bounded FSDP SFT draft differs")
    if run_id.endswith("002") and (
            plan.get("checkpoint_storage") != "ephemeral-scratch" or
            plan.get("discard_resumed_checkpoint_after_load") is not True or
            plan.get("minimum_free_working_bytes") != 11_000_000_000 or
            plan.get("minimum_free_scratch_bytes") != 55_000_000_000 or
            plan.get("maximum_retained_output_bytes") != 12_000_000_000):
        raise ValidationError("bounded scratch SFT repair differs")
    if authorization is not None:
        binding = json.loads(authorization.read_bytes())
        if (binding.get("approved") is not True or
                binding.get("draft_plan_sha256") != _sha(draft_bytes) or
                binding.get("run_id") != plan["run_id"] or
                binding.get("kernel_id") != "danielwuu/" + plan["run_id"] or
                not isinstance(binding.get("owner_decision"), str) or
                not binding["owner_decision"].strip() or
                binding["owner_decision"].startswith(
                    ("Decision 0028", "Decision 0029", "Decision 0030") +
                    (("Decision 0031",) if run_id.endswith("002") else ()))):
            raise ValidationError("exact owner-approved FSDP SFT binding required")
        plan.update(approved=True, kernel_id=binding["kernel_id"],
                    owner_decision=binding["owner_decision"])
    small = json.loads((CONFIG / "m2-m3-small.json").read_bytes())
    sequences = load_frozen_arc_sft_data(small, data_root)
    data_manifest = json.loads((data_root / "manifest.json").read_bytes())
    if (len(sequences) != 128 or
            data_manifest.get("train_sequence_digest") != digest_value(sequences) or
            data_manifest.get("train_parents") != small["train"] or
            data_manifest.get("dev_parents") != small["dev"]):
        raise ValidationError("public ARC train/dev manifest differs")
    stride = plan["sample_stride"]
    if math.gcd(stride, len(sequences)) != 1:
        raise ValidationError("FSDP SFT schedule does not permute sequences")
    selected = [sequences[(plan["seed"] + index * stride) % len(sequences)]
                for index in range(plan["world_size"] * plan["maximum_optimizer_steps"])]
    parent_ids = sorted({item["source"].split(":")[0] for item in selected})
    if (sum(len(item["input_ids"]) for item in selected) != plan["scheduled_training_tokens"] or
            parent_ids != sorted(item["id"] for item in small["train"]) or
            max(len(item["input_ids"]) for item in sequences) > plan["max_sequence_length"]):
        raise ValidationError("FSDP SFT selected training tokens or parents differ")
    sequence_bytes = b"".join(canonical_bytes(item, newline=True) for item in sequences)
    plan["sequences_sha256"] = _sha(sequence_bytes)
    plan["sequences_digest"] = digest_value(sequences)
    plan["source_data_manifest_digest"] = digest_value(data_manifest)
    plan["scheduled_parent_ids"] = parent_ids
    model_material = verify_model_material(
        model_root, plan["compact_material_digest"],
        allowed_extra_files={"dataset-metadata.json"}
        if (model_root / "dataset-metadata.json").exists() else None)
    source_config_bytes = (CONFIG / "source-integration-sft-4b-001.json").read_bytes()
    source_config = json.loads(source_config_bytes)
    if (source_config["profiles"]["4b"]["material_digest"] != plan["compact_material_digest"] or
            source_config["candidate"]["maximum_calls_per_task"] !=
            plan["maximum_source_generation_calls"]):
        raise ValidationError("source solve config differs from SFT plan")
    visible_all = json.loads((data_root / "dev-visible.json").read_bytes())
    selected_id = sorted(visible_all)[0]
    visible = {selected_id: visible_all[selected_id]}
    visible_task(selected_id, visible[selected_id])
    if selected_id not in {item["id"] for item in data_manifest["dev_parents"]} or len(visible) != plan["maximum_source_tasks"]:
        raise ValidationError("source solve visible dev selection differs")
    visible_bytes = canonical_bytes(visible, newline=True)
    plan["source_config_sha256"] = _sha(source_config_bytes)
    plan["source_visible_sha256"] = _sha(visible_bytes)
    plan["source_visible_task_ids"] = [selected_id]
    wheel_manifest = json.loads((CONFIG / "base-wheel-manifest.json").read_bytes())
    wheel_dir = output / "wheel"
    wheel_dir.mkdir(parents=True)
    wheel_name = build.build_wheel(str(wheel_dir))
    wheel_bytes = (wheel_dir / wheel_name).read_bytes()
    with zipfile.ZipFile(wheel_dir / wheel_name) as archive:
        required = {"irisx/arc_nvarc_fsdp_sft.py", "irisx/arc_nvarc_source_runtime.py"}
        if not required.issubset(archive.namelist()):
            raise ValidationError("FSDP SFT wheel omitted runtime or source stage")
    payloads = {"plan": canonical_bytes(plan, newline=True),
                "sequences": sequence_bytes,
                "visible": visible_bytes,
                "source_config": source_config_bytes,
                "wheel_manifest": canonical_bytes(wheel_manifest, newline=True),
                "runtime_wheel": wheel_bytes}
    hashes = {name: _sha(payload) for name, payload in payloads.items()}
    review_names = {"plan": "plan.json", "sequences": "sequences.jsonl",
                    "visible": "visible.json", "source_config": "source-config.json",
                    "wheel_manifest": "wheel-manifest.json"}
    for name, filename in review_names.items():
        (output / filename).write_bytes(payloads[name])
    encoded = {name: base64.b64encode(payload).decode() for name, payload in payloads.items()}
    template_name = ("nvarc_m2_fsdp_sft_notebook_002.py.tmpl" if run_id.endswith("002")
                     else "nvarc_m2_fsdp_sft_notebook.py.tmpl")
    template = (ROOT / "tools" / template_name).read_text(encoding="utf-8")
    source = template.replace("__PAYLOADS__", json.dumps(encoded, sort_keys=True)).replace(
        "__HASHES__", json.dumps(hashes, sort_keys=True))
    compile(source, "nvarc-m2-fsdp-sft-notebook", "exec")
    kernel = output / "kernel"
    kernel.mkdir()
    notebook = {"cells": [{"cell_type": "code", "execution_count": None,
                            "metadata": {}, "outputs": [],
                            "source": source.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                             "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    notebook_path = kernel / "kaggle-notebook.ipynb"
    notebook_path.write_bytes(canonical_bytes(notebook, newline=True))
    metadata = {"id": plan["kernel_id"], "title": plan["run_id"],
                "code_file": notebook_path.name, "language": "python",
                "kernel_type": "notebook", "is_private": True, "enable_gpu": True,
                "enable_tpu": False, "enable_internet": False,
                "machine_shape": "NvidiaL4",
                "competition_sources": ["arc-prize-2026-arc-agi-2"],
                "dataset_sources": [plan["model_dataset_id"], plan["wheel_dataset_id"]],
                "kernel_sources": [], "model_sources": []}
    (kernel / "kernel-metadata.json").write_bytes(canonical_bytes(metadata, newline=True))
    summary = {"format": "irisx/nvarc-m2-fsdp-sft-stage-v1",
               "approved": plan["approved"], "run_id": plan["run_id"],
               "draft_plan_sha256": _sha(draft_bytes),
               "plan_sha256": hashes["plan"], "plan_digest": digest_value(plan),
               "data_manifest_digest": plan["source_data_manifest_digest"],
               "sequences_sha256": hashes["sequences"],
               "sequences_digest": plan["sequences_digest"],
               "selected_parent_ids": parent_ids,
               "scheduled_training_tokens": plan["scheduled_training_tokens"],
               "compact_material_digest": plan["compact_material_digest"],
               "compact_weight_bytes": sum(item["bytes"] for item in model_material["files"]
                                           if item["path"].endswith(".safetensors")),
               "source_config_sha256": hashes["source_config"],
               "source_visible_sha256": hashes["visible"],
               "source_visible_task_ids": [selected_id],
               "runtime_wheel_sha256": hashes["runtime_wheel"],
               "notebook_sha256": _sha(notebook_path.read_bytes()),
               "kernel_metadata_sha256": _sha((kernel / "kernel-metadata.json").read_bytes()),
               "maximum_paid_usd": 0, "external_calls": 0,
               "claim": "offline package only; 4B checkpoint and source solve unexecuted"}
    (output / "stage-summary.json").write_bytes(canonical_bytes(summary, newline=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--draft-plan", type=Path,
                        default=CONFIG / "m2-fsdp-sft-draft-001.json")
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--compact", type=Path, default=MODEL)
    args = parser.parse_args()
    print(json.dumps(stage(args.output, authorization=args.authorization,
                           draft_path=args.draft_plan,
                           data_root=args.data, model_root=args.compact), indent=2))


if __name__ == "__main__":
    main()

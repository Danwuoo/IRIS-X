"""Bounded, truth-free 4B LoRA compatibility pilot; no ARC inference or SFT."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


RUN_ID = "nvarc-4b-compat-pilot-001"
MODEL_DIGEST = "sha256:8f27407e1b0ee4dd7a5b4d62d39af9b356ba86b5701dd93eafba052febe9c72f"
MODEL_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def validate_plan(plan: dict[str, Any]) -> None:
    exact = {"format": "irisx/nvarc-4b-compatibility-pilot", "run_id": RUN_ID,
             "provider": "Kaggle", "dataset_ref": "danielwuu/irisx-arc-agi-2-trial-002-smoke-001",
             "dataset_version": 2, "model_repository": "Qwen/Qwen3.5-4B",
             "model_revision": MODEL_REVISION, "model_manifest_digest": MODEL_DIGEST,
             "wheel_manifest_digest": "sha256:d24d85f791788621166fa05d7db51c03f7c72c046af4923096b12863f7e7dfa1",
             "maximum_paid_usd": 0, "maximum_kernel_pushes": 1,
             "maximum_output_retrievals": 1, "maximum_wall_seconds": 1800,
             "worker_timeout_seconds": 1500, "finalization_reserve_seconds": 300,
             "maximum_training_steps": 2, "maximum_training_tokens": 128,
             "maximum_generation_calls": 0, "maximum_teacher_calls": 0,
             "python_major_minor": "3.12",
             "target_image_reference": "v170-GPU-bdf9e0538555f90453619adefb49ba40cfa136db44a9c9be7a42ea715c0aa068",
             "data": "one synthetic grid demonstration, no ARC task or evaluator truth"}
    if any(plan.get(key) != value for key, value in exact.items()):
        raise ValidationError("4B pilot identity or hard ceiling differs")
    if plan.get("runtime_wheels") != {
            "transformers": "transformers-5.8.1-py3-none-any.whl",
            "peft": "peft-0.21.0-py3-none-any.whl",
            "safetensors": "safetensors-0.8.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            "tokenizers": "tokenizers-0.22.2-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            "accelerate": "accelerate-1.10.1-py3-none-any.whl"}:
        raise ValidationError("4B pilot offline dependency binding differs")
    if (plan.get("approved") is not True or
            not isinstance(plan.get("owner_authorization"), str) or
            not plan["owner_authorization"].strip() or
            plan.get("kernel_id") != "danielwuu/irisx-nvarc-4b-compat-pilot-001"):
        raise ValidationError("4B pilot lacks exact owner execution authority")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise ValidationError("4B pilot must be offline")


def verify_model_material(root: Path, manifest: dict[str, Any]) -> None:
    if (manifest.get("format") != "irisx/model-material-manifest" or
            manifest.get("revision") != MODEL_REVISION or
            manifest.get("repository") != "Qwen/Qwen3.5-4B" or
            manifest.get("manifest_digest") != MODEL_DIGEST):
        raise ValidationError("base model source manifest differs")
    files = manifest.get("files")
    if (not isinstance(files, list) or not files or
            digest_value(files) != MODEL_DIGEST):
        raise ValidationError("base model file inventory differs")
    names = [item.get("path") for item in files if isinstance(item, dict)]
    if len(names) != len(files) or len(set(names)) != len(names) or any(
            not isinstance(name, str) or not name or Path(name).name != name or
            name in {".", ".."} for name in names):
        raise ValidationError("unsafe or duplicate base model member")
    required = {"config.json", "tokenizer.json", "model.safetensors.index.json",
                "model.safetensors-00001-of-00002.safetensors",
                "model.safetensors-00002-of-00002.safetensors"}
    if not required.issubset(names):
        raise ValidationError("base model essential files missing")
    index = json.loads((root / "model.safetensors.index.json").read_bytes())
    if set(index.get("weight_map", {}).values()) != {
            "model.safetensors-00001-of-00002.safetensors",
            "model.safetensors-00002-of-00002.safetensors"}:
        raise ValidationError("base model shard index differs")
    for item in files:
        path = root / item["path"]
        if not path.is_file() or path.is_symlink() or path.stat().st_size != item.get("byte_size"):
            raise ValidationError(f"base model member missing or wrong size: {path.name}")
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                sha.update(chunk)
        if "sha256:" + sha.hexdigest() != item.get("content_digest"):
            raise ValidationError(f"base model digest differs: {path.name}")


def _atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_bytes(value, newline=True))
    os.replace(temporary, path)


def run(plan: dict[str, Any], model_root: Path, model_manifest: dict[str, Any],
        output: Path, ledger_path: Path) -> dict[str, Any]:
    validate_plan(plan)
    if output.exists() or ledger_path.exists():
        raise ValidationError("4B pilot cannot resume or overwrite an identity")
    started = time.monotonic()
    ledger = {"format": "irisx/nvarc-4b-pilot-ledger", "run_id": RUN_ID,
              "plan_digest": digest_value(plan), "reserved_steps": 0,
              "completed_steps": 0, "reserved_training_tokens": 0,
              "completed_training_tokens": 0, "generation_calls": 0,
              "status": "material-gate"}
    _atomic(ledger_path, ledger)
    try:
        verify_model_material(model_root, model_manifest)
        versions = {name: importlib.metadata.version(name) for name in
                    ("torch", "transformers", "peft", "safetensors", "tokenizers", "accelerate")}
        if (versions["transformers"] != "5.8.1" or versions["peft"] != "0.21.0" or
                versions["safetensors"] != "0.8.0" or
                versions["tokenizers"] != "0.22.2" or
                versions["accelerate"] != "1.10.1" or
                f"{sys.version_info.major}.{sys.version_info.minor}" != "3.12"):
            raise ValidationError("4B pilot dependency versions differ")
        import torch
        from peft import get_peft_model_state_dict
        from transformers import Qwen3_5ForConditionalGeneration
        from .arc_nvarc_training import TaskLocalAdapter, collate, task_local_sequences

        if (not torch.cuda.is_available() or not 1 <= torch.cuda.device_count() <= 4 or
                "L4" not in torch.cuda.get_device_name(0) or
                torch.cuda.get_device_properties(0).total_memory < 22000 * 1024 * 1024):
            raise ValidationError("pilot requires one usable L4 with 22000 MiB")
        torch.manual_seed(7)
        model = Qwen3_5ForConditionalGeneration.from_pretrained(
            model_root, local_files_only=True, dtype=torch.bfloat16,
            device_map={"": "cuda:0"}, attn_implementation="sdpa")
        model.config.use_cache = False
        task = {"task_id": "synthetic-only", "train": [{"input": [[1]], "output": [[2]]}],
                "test": [{"input": [[3]]}]}
        sequences = task_local_sequences(task, seed=7, augmentation_count=1)
        if len(sequences) != 1 or len(sequences[0]["input_ids"]) * 2 > 128:
            raise ValidationError("synthetic workload exceeds token cap")
        adapter = TaskLocalAdapter(model, {"seed": 7, "rank": 2, "alpha": 4,
                                           "learning_rate": 0.001, "steps": 2,
                                           "max_sequence_length": 128,
                                           "augmentation_count": 1})
        optimizer = torch.optim.AdamW(
            (parameter for parameter in adapter.model.parameters() if parameter.requires_grad),
            lr=0.001)
        groups = {"attention": False, "delta": False, "embedding": False, "head": False}
        losses = []
        for step in range(2):
            tokens = len(sequences[0]["input_ids"])
            if ledger["reserved_training_tokens"] + tokens > 128:
                raise ValidationError("training token reservation exceeds cap")
            ledger.update(status="training", reserved_steps=step + 1,
                          reserved_training_tokens=ledger["reserved_training_tokens"] + tokens)
            _atomic(ledger_path, ledger)
            batch = {key: torch.tensor(value, device="cuda:0") for key, value in
                     collate(sequences, 128).items()}
            optimizer.zero_grad(set_to_none=True)
            loss = adapter.model(**batch).loss
            if not bool(torch.isfinite(loss)):
                raise ValidationError("4B pilot loss is nonfinite")
            loss.backward()
            for name, parameter in adapter.model.named_parameters():
                if parameter.grad is None or not bool(torch.any(parameter.grad != 0)):
                    continue
                if ".self_attn." in name:
                    groups["attention"] = True
                if ".linear_attn." in name:
                    groups["delta"] = True
                if "embed_tokens" in name:
                    groups["embedding"] = True
                if "lm_head" in name:
                    groups["head"] = True
            if not all(groups.values()):
                raise ValidationError("4B LoRA gradient group coverage incomplete")
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            ledger.update(completed_steps=step + 1,
                          completed_training_tokens=ledger["reserved_training_tokens"])
            _atomic(ledger_path, ledger)
            if time.monotonic() - started > 1500:
                raise ValidationError("4B pilot worker wall limit exhausted")
        updated = get_peft_model_state_dict(adapter.model)
        if not any(not torch.equal(value.cpu(), adapter.initial[name])
                   for name, value in updated.items()):
            raise ValidationError("4B adapter did not update")
        adapter.reset()
        reset = all(torch.equal(value.cpu(), adapter.initial[name])
                    for name, value in get_peft_model_state_dict(adapter.model).items())
        if not reset:
            raise ValidationError("4B adapter reset differs")
        ledger["status"] = "complete"
        _atomic(ledger_path, ledger)
        result = {"format": "irisx/nvarc-4b-pilot-result", "run_id": RUN_ID,
                  "plan_digest": digest_value(plan), "status": "complete",
                  "model_manifest_digest": MODEL_DIGEST, "dependencies": versions,
                  "gpu_name": torch.cuda.get_device_name(0),
                  "gpu_memory_mib": torch.cuda.get_device_properties(0).total_memory // (1024 * 1024),
                  "peak_allocated_mib": torch.cuda.max_memory_allocated(0) // (1024 * 1024),
                  "gradient_groups": groups, "losses": losses,
                  "adapter_reset": reset, "reserved_steps": ledger["reserved_steps"],
                  "completed_steps": ledger["completed_steps"],
                  "training_tokens": ledger["completed_training_tokens"],
                  "generation_calls": 0, "truth_free": True,
                  "elapsed_seconds": time.monotonic() - started}
    except Exception as exc:
        ledger["status"] = "failed"
        _atomic(ledger_path, ledger)
        result = {"format": "irisx/nvarc-4b-pilot-result", "run_id": RUN_ID,
                  "plan_digest": digest_value(plan), "status": "failed",
                  "failure_type": type(exc).__name__, "failure_detail": str(exc)[:300],
                  "reserved_steps": ledger["reserved_steps"],
                  "completed_steps": ledger["completed_steps"],
                  "reserved_training_tokens": ledger["reserved_training_tokens"],
                  "generation_calls": 0, "truth_free": True,
                  "elapsed_seconds": time.monotonic() - started}
    _atomic(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--model-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    args = parser.parse_args()
    result = run(json.loads(args.plan.read_bytes()), args.model_root,
                 json.loads(args.model_manifest.read_bytes()), args.output, args.ledger)
    print(json.dumps(result))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())

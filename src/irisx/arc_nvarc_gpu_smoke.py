"""Tiny, truth-free Qwen3.5/PEFT GPU compatibility probe for a future approved kernel."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import time
from unittest import mock

from .arc_nvarc_representation import GridTokenizer
from .arc_nvarc_training import TaskLocalAdapter, collate, task_local_sequences
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


def run(manifest: dict, output: Path) -> dict:
    if (manifest.get("approved") is not True or
            manifest.get("operation") != "tiny-qwen35-gpu-compatibility" or
            manifest.get("maximum_paid_usd") != 0 or
            manifest.get("maximum_generation_calls") != 0 or
            manifest.get("maximum_training_steps") != 2 or
            manifest.get("maximum_training_tokens") != 128):
        raise ValidationError("GPU compatibility run lacks exact owner authority and caps")
    if (not isinstance(manifest.get("run_id"), str) or
            not manifest["run_id"].startswith("nvarc-acceptance-gpu-a-") or
            not isinstance(manifest.get("owner_authorization"), str) or
            not manifest["owner_authorization"].strip() or
            manifest.get("maximum_visible_gpus") != 4 or
            manifest.get("maximum_wall_seconds") != 1500):
        raise ValidationError("GPU run identity or resource bounds differ")
    expected = manifest.get("dependencies")
    if not isinstance(expected, dict):
        raise ValidationError("GPU dependency profile missing")
    actual = {name: importlib.metadata.version(name) for name in
              ("torch", "transformers", "peft", "safetensors")}
    if actual != expected:
        raise ValidationError(f"GPU dependency profile differs: {actual}")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise ValidationError("GPU compatibility probe must be offline")
    import torch
    from peft import get_peft_model_state_dict
    from transformers import Qwen3_5Config, Qwen3_5ForConditionalGeneration

    count = torch.cuda.device_count()
    if not 1 <= count <= manifest["maximum_visible_gpus"]:
        raise ValidationError("actual GPU topology exceeds approved bound or is absent")
    started = time.monotonic()
    torch.manual_seed(7)
    config = Qwen3_5Config()
    text = config.text_config
    text.vocab_size, text.hidden_size, text.intermediate_size = 16, 64, 128
    text.num_hidden_layers, text.layer_types = 2, ["linear_attention", "full_attention"]
    text.num_attention_heads, text.num_key_value_heads, text.head_dim = 4, 2, 16
    text.linear_num_key_heads = text.linear_num_value_heads = 4
    text.linear_key_head_dim = text.linear_value_head_dim = 16
    text.max_position_embeddings = 128
    text.rope_parameters = {"rope_type": "default", "rope_theta": 10000.0,
                            "mrope_section": [1, 1, 0], "mrope_interleaved": True}
    config.vision_config.depth = 1
    config.vision_config.hidden_size = 64
    config.vision_config.intermediate_size = 128
    config.vision_config.num_heads = 4
    config.vision_config.out_hidden_size = 64
    config.vision_config.num_position_embeddings = 16
    config.vocab_size = 16
    model = Qwen3_5ForConditionalGeneration(config).to("cuda:0").train()
    tokens, labels = GridTokenizer().encode_pair([[1]], [[2]])
    if len(tokens) > manifest["maximum_training_tokens"]:
        raise ValidationError("tiny grid exceeds token cap")
    batch = {key: torch.tensor(value, device="cuda:0") for key, value in
             collate([{"input_ids": tokens, "labels": labels}], 128).items()}
    loss = model(**batch).loss
    if not torch.isfinite(loss):
        raise ValidationError("tiny Qwen loss nonfinite")
    loss.backward()
    gradient_groups = {"attention": False, "delta": False, "embedding": False,
                       "head": False}
    for name, parameter in model.named_parameters():
        if parameter.grad is None or not bool(torch.any(parameter.grad != 0)):
            continue
        if ".self_attn." in name:
            gradient_groups["attention"] = True
        if ".linear_attn." in name:
            gradient_groups["delta"] = True
        if "embed_tokens" in name:
            gradient_groups["embedding"] = True
        if "lm_head" in name:
            gradient_groups["head"] = True
    if not all(gradient_groups.values()):
        tied = (model.get_input_embeddings().weight.data_ptr() ==
                model.get_output_embeddings().weight.data_ptr())
        if tied and gradient_groups["embedding"]:
            gradient_groups["head"] = True
        if not all(gradient_groups.values()):
            raise ValidationError("tiny Qwen text gradient coverage incomplete")
    model.zero_grad(set_to_none=True)
    task = {"task_id": "synthetic", "train": [{"input": [[1]], "output": [[2]]}],
            "test": [{"input": [[3]]}]}
    adaptation = task_local_sequences(task, seed=7, augmentation_count=1)
    total_tokens = len(tokens) + 2 * sum(len(item["input_ids"]) for item in adaptation)
    if len(adaptation) != 1 or total_tokens > manifest["maximum_training_tokens"]:
        raise ValidationError("tiny GPU training token ceiling exceeded")
    adapter = TaskLocalAdapter(model, {"seed": 7, "rank": 2, "alpha": 4,
                                       "learning_rate": 0.001, "steps": 1,
                                       "max_sequence_length": 128,
                                       "augmentation_count": 1})
    adapter.adapt(task)
    updated = get_peft_model_state_dict(adapter.model)
    if not any(not torch.equal(value.cpu(), adapter.initial[name])
               for name, value in updated.items()):
        raise ValidationError("tiny PEFT training did not update adapter weights")
    adapter.reset()
    for name, value in get_peft_model_state_dict(adapter.model).items():
        if not torch.equal(value.cpu(), adapter.initial[name]):
            raise ValidationError("PEFT reset changed initial adapter state")
    original_step = torch.optim.AdamW.step

    def fail_after_step(optimizer, *args, **kwargs):
        original_step(optimizer, *args, **kwargs)
        raise RuntimeError("synthetic failure after LoRA optimizer step")

    try:
        with mock.patch.object(torch.optim.AdamW, "step", fail_after_step):
            adapter.adapt(task)
    except RuntimeError as exc:
        if str(exc) != "synthetic failure after LoRA optimizer step":
            raise
    else:
        raise ValidationError("synthetic PEFT post-step failure path did not fail")
    for name, value in get_peft_model_state_dict(adapter.model).items():
        if not torch.equal(value.cpu(), adapter.initial[name]):
            raise ValidationError("PEFT failure failed to reset adapter")
    elapsed = time.monotonic() - started
    if elapsed > manifest["maximum_wall_seconds"]:
        raise ValidationError("tiny GPU work exceeded session wall limit")
    result = {"format": "irisx/nvarc-tiny-gpu-compatibility", "run_id": manifest["run_id"],
              "manifest_digest": digest_value(manifest), "dependencies": actual,
              "gpu_count": count, "gpu_name": torch.cuda.get_device_name(0),
              "training_steps": 2, "training_tokens_upper_bound": total_tokens,
              "generation_calls": 0, "gradient_groups": gradient_groups,
              "base_backward": True,
              "peft_success_reset": True, "peft_failure_reset": True,
              "peak_memory_mib": torch.cuda.max_memory_allocated(0) // (1024 * 1024),
              "elapsed_seconds": elapsed, "truth_free": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(result, newline=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(json.loads(args.manifest.read_bytes()), args.output)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

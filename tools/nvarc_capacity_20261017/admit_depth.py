"""Local CPU admission of official 2B identity depth, without training or export."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import tempfile
import time

import torch
from transformers import AutoConfig, Qwen3ForCausalLM

from tools.nvarc_capacity_20261017.prototype import (
    count_parameters, expand_identity_depth, train_only_new_depth,
)
from tools.nvarc_posttrain_20261017.codec import encode_example
from tools.nvarc_posttrain_20261017.engine import load_compact_tokenizer, model_contract
from tools.nvarc_posttrain_20261017.materials import verify_model


def _require(condition, message):
    if not condition:
        raise ValueError(message)


@torch.no_grad()
def _probe(model, input_ids):
    logits = model(input_ids, use_cache=False).logits.detach().float()
    _require(bool(torch.isfinite(logits).all()), "nonfinite initial logits")
    current, cache, tokens, cached_logits = input_ids, None, [], []
    for _ in range(6):
        output = model(current, past_key_values=cache, use_cache=True)
        cache = output.past_key_values
        row = output.logits[:, -1].detach().float()
        _require(bool(torch.isfinite(row).all()), "nonfinite cached logits")
        cached_logits.append(row)
        current = row.argmax(dim=-1).unsqueeze(-1)
        tokens.append(current.item())
    return logits, torch.stack(cached_logits), tokens, len(cache.layers)


def run(model_root, output):
    started = time.monotonic()
    torch.set_num_threads(4)
    pin = verify_model(model_root, "2b")
    print("Official 2B file hashes admitted", flush=True)
    raw = json.loads((model_root / "config.json").read_bytes())
    config = AutoConfig.from_pretrained(model_root, local_files_only=True, trust_remote_code=False)
    _require(model_contract(raw, variant="2b") == model_contract(config, variant="2b"),
             "official config metadata not preserved")
    tokenizer = load_compact_tokenizer(model_root)
    row = encode_example([{"input": [[1, 0], [0, 1]], "output": [[2, 0], [0, 2]]}],
                         [[1, 1], [0, 1]], generation=6)
    ids = row["prompt_ids"]
    _require(tokenizer.encode(tokenizer.decode(ids), add_special_tokens=False) == ids,
             "compact input roundtrip differs")
    input_ids = torch.tensor([ids])
    model = Qwen3ForCausalLM.from_pretrained(model_root, config=config,
        local_files_only=True, trust_remote_code=False, dtype=torch.bfloat16,
        attn_implementation="sdpa", device_map={"": "cpu"}).eval()
    _require(count_parameters(model) == 1_409_475_584, "official parameter count differs")
    model.requires_grad_(False)
    before = _probe(model, input_ids)
    print("Original forward and six cached decoding steps completed", flush=True)
    receipt = expand_identity_depth(model, after_layers=(6, 13, 20, 27))
    _require(receipt["parameters"] == 1_610_819_584, "expanded parameter count differs")
    after = _probe(model, input_ids)
    _require(torch.equal(before[0], after[0]), "actual BF16/SDPA full logits not identical")
    _require(torch.equal(before[1], after[1]), "actual BF16/SDPA cached logits not identical")
    _require(before[2] == after[2], "cached greedy sequence differs")
    _require((before[3], after[3]) == (28, 32), "cache did not cover new layer layout")
    trainables = train_only_new_depth(model, receipt)
    _require(trainables == 201_409_536, "new-block/compact-head trainable count differs")
    receipt.update({"schema": "irisx-local-depth-admission/v1", "variant": "2b",
        "material_identity_sha256": pin["material_identity_sha256"],
        "base_weight_sha256": pin["files"]["model.safetensors"]["sha256"],
        "device": "cpu", "dtype": "bfloat16", "attention": "sdpa",
        "prompt_tokens": len(ids), "cached_decode_steps": 6,
        "full_logit_max_abs_difference": (before[0] - after[0]).abs().max().item(),
        "cached_logit_max_abs_difference": (before[1] - after[1]).abs().max().item(),
        "initial_greedy_sequence_equal": True, "original_cache_layers": before[3],
        "expanded_cache_layers": after[3], "planned_trainable_parameters": trainables,
        "trainable_dtype_promoted": False, "training_performed": False,
        "weights_exported": False, "benchmark_data_loaded": False,
        "gpu_admitted": False, "full_context_admitted": False,
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2,
        "torch": torch.__version__,
        "prototype_sha256": hashlib.sha256(Path(__file__).with_name("prototype.py").read_bytes()).hexdigest()})
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                prefix=".depth-admission-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(receipt, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)  # Atomic complete publication, never replace a prior receipt.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(json.dumps({k: receipt[k] for k in ("parameters", "planned_trainable_parameters",
        "full_logit_max_abs_difference", "cached_logit_max_abs_difference", "elapsed_seconds",
        "peak_rss_gib", "training_performed", "capability_gain_established")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.model_root.absolute(), args.output.absolute())

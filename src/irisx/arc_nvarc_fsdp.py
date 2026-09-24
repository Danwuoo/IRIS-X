"""Four-L4 full-parameter FSDP feasibility entry for the pinned 4B compact model.

This deliberately performs one unpacked optimizer step and emits only a small
truth-free observation. It is not a completed ARC-SFT checkpoint or result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from .arc_nvarc_training import collate, load_compact_model
from .arc_nvarc_representation import verify_model_material
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


def _hardware_gate() -> dict:
    import torch
    import torch.distributed as dist

    world = int(os.environ.get("WORLD_SIZE", "0"))
    rank = int(os.environ.get("RANK", "-1"))
    local_rank = int(os.environ.get("LOCAL_RANK", "-1"))
    if (world != 4 or rank not in range(4) or local_rank not in range(4) or
            not torch.cuda.is_available() or torch.cuda.device_count() != 4 or
            not torch.cuda.is_bf16_supported()):
        raise ValidationError("FSDP feasibility requires exactly four visible CUDA GPUs")
    torch.cuda.set_device(local_rank)
    name = torch.cuda.get_device_name(local_rank)
    if "L4" not in name:
        raise ValidationError("FSDP feasibility requires L4 devices")
    dist.init_process_group("nccl")
    device = torch.device("cuda", local_rank)
    properties = torch.cuda.get_device_properties(local_rank)
    observed = {"rank": rank, "local_rank": local_rank, "name": name,
                "device_uuid": str(getattr(properties, "uuid", "")),
                "total_memory_bytes": properties.total_memory}
    all_observed = [None] * 4
    dist.all_gather_object(all_observed, observed)
    if (len({item["local_rank"] for item in all_observed}) != 4 or
            len({item["device_uuid"] for item in all_observed}) != 4 or
            any(not item["device_uuid"] or item["total_memory_bytes"] < 22 * 10**9
                for item in all_observed)):
        raise ValidationError("FSDP ranks do not cover four distinct L4 UUIDs")
    return observed


def _weight_sum(model) -> float:
    import torch
    import torch.distributed as dist

    with torch.no_grad():
        local = sum((parameter.detach().float().sum() for parameter in model.parameters()),
                    torch.zeros((), device=torch.device("cuda", torch.cuda.current_device())))
    dist.all_reduce(local)
    return float(local.cpu())


def run(plan_path: Path, compact: Path, sequences_path: Path, output: Path) -> dict:
    import torch
    import torch.distributed as dist
    from torch.distributed.fsdp import FullyShardedDataParallel as FSDP, MixedPrecision
    from torch.distributed.fsdp.wrap import ModuleWrapPolicy

    plan = json.loads(plan_path.read_bytes())
    if (plan.get("format") != "irisx/nvarc-m2-fsdp-feasibility-v1" or
            plan.get("approved") is not True or plan.get("maximum_optimizer_steps") != 1 or
            plan.get("world_size") != 4 or plan.get("maximum_paid_usd") != 0 or
            plan.get("packing") is not False or plan.get("maximum_generations") != 0 or
            plan.get("maximum_teacher_calls") != 0):
        raise ValidationError("exact authorized FSDP feasibility plan required")
    if (hashlib.sha256(sequences_path.read_bytes()).hexdigest() != plan["sequences_sha256"] or
            not plan["compact_material_digest"].startswith("sha256:")):
        raise ValidationError("FSDP sequence or model binding differs")
    sequences = [json.loads(line) for line in sequences_path.read_text(encoding="utf-8").splitlines()]
    if (len(sequences) != 128 or digest_value(sequences) != plan["sequences_digest"] or
            any(len(sequence["input_ids"]) > plan["max_sequence_length"] or
                len(sequence["input_ids"]) != len(sequence["labels"])
                for sequence in sequences)):
        raise ValidationError("FSDP sequence count/digest differs")
    started = time.monotonic()
    observed = _hardware_gate()
    rank = observed["rank"]
    try:
        gate = [None]
        if rank == 0:
            try:
                verify_model_material(compact, plan["compact_material_digest"])
            except Exception as error:
                gate[0] = f"{type(error).__name__}: {error}"
        dist.broadcast_object_list(gate, src=0)
        if gate[0] is not None:
            raise ValidationError("FSDP compact material gate failed: " + gate[0])
        model = load_compact_model(compact, dtype="bfloat16")
        layer_type = type(model.model.language_model.layers[0])
        wrapped = FSDP(model, auto_wrap_policy=ModuleWrapPolicy({layer_type}),
                       device_id=torch.cuda.current_device(), use_orig_params=True,
                       limit_all_gathers=True,
                       mixed_precision=MixedPrecision(param_dtype=torch.bfloat16,
                                                      reduce_dtype=torch.bfloat16,
                                                      buffer_dtype=torch.bfloat16))
        optimizer = torch.optim.AdamW(wrapped.parameters(), lr=float(plan["learning_rate"]),
                                      weight_decay=float(plan["weight_decay"]))
        torch.cuda.reset_peak_memory_stats()
        before = _weight_sum(wrapped)
        sequence = sequences[(int(plan["seed"]) + rank) % len(sequences)]
        batch = {key: torch.tensor(value, dtype=torch.long,
                                   device=torch.device("cuda", observed["local_rank"]))
                 for key, value in collate([sequence], int(plan["max_sequence_length"])).items()}
        tokens = int(batch["attention_mask"].sum())
        if tokens > int(plan["maximum_tokens_per_rank"]):
            raise ValidationError("FSDP rank token ceiling exceeded")
        wrapped.train()
        step_started = time.monotonic()
        loss = wrapped(**batch).loss
        if not bool(torch.isfinite(loss)):
            raise ValidationError("FSDP SFT loss non-finite")
        loss.backward()
        nonzero = sum(int(parameter.grad is not None and bool(torch.any(parameter.grad != 0)))
                      for parameter in wrapped.parameters())
        if not nonzero or any(parameter.grad is not None and not bool(torch.isfinite(parameter.grad).all())
                              for parameter in wrapped.parameters()):
            raise ValidationError("FSDP SFT gradient missing or non-finite")
        wrapped.clip_grad_norm_(float(plan["clip_grad_norm"]))
        optimizer.step()
        if any(not bool(torch.isfinite(parameter).all()) for parameter in wrapped.parameters()):
            raise ValidationError("FSDP SFT updated weight non-finite")
        torch.cuda.synchronize()
        after = _weight_sum(wrapped)
        if before == after:
            raise ValidationError("FSDP SFT optimizer did not change weight sum")
        local = {**observed, "input_tokens": tokens, "loss": float(loss.detach().cpu()),
                 "nonzero_gradient_tensors": nonzero,
                 "weight_sum_before": before, "weight_sum_after": after,
                 "step_wall_seconds": time.monotonic() - step_started,
                 "peak_cuda_allocated_mib": torch.cuda.max_memory_allocated() / 1048576}
        all_local = [None] * 4
        dist.all_gather_object(all_local, local)
        if sum(item["input_tokens"] for item in all_local) > plan["maximum_total_input_tokens"]:
            raise ValidationError("FSDP global token ceiling exceeded")
        result = {"format": "irisx/nvarc-m2-fsdp-feasibility-result-v1",
                  "plan_digest": digest_value(plan),
                  "compact_material_digest": plan["compact_material_digest"],
                  "sequences_digest": plan["sequences_digest"],
                  "optimizer_steps": 1, "total_input_tokens": sum(item["input_tokens"] for item in all_local),
                  "ranks": all_local, "wall_seconds": time.monotonic() - started,
                  "contains_evaluator_truth": False,
                  "claim": "FSDP one-step compatibility only; no exported ARC-SFT checkpoint"}
        if rank == 0:
            output.mkdir(parents=True, exist_ok=False)
            (output / "result.json").write_bytes(canonical_bytes(result, newline=True))
        dist.barrier()
        return result
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.compact, args.sequences, args.output)


if __name__ == "__main__":
    main()

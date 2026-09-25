"""Four-L4 full-parameter FSDP feasibility entry for the pinned 4B compact model.

This deliberately performs one unpacked optimizer step and emits only a small
truth-free observation. It is not a completed ARC-SFT checkpoint or result.
"""

from __future__ import annotations

import argparse
from datetime import timedelta
import faulthandler
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
import traceback

from .arc_nvarc_training import collate, load_compact_model
from .arc_nvarc_representation import verify_model_material
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


class _RankTrace:
    """Small, truth-free, durable per-rank markers for a bounded provider run."""

    def __init__(self, root: Path, rank: int) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.rank = rank
        self.path = root / f"rank-{rank}.jsonl"
        self.stack = (root / f"rank-{rank}-stack.txt").open("w", encoding="utf-8")
        faulthandler.dump_traceback_later(240, repeat=True, file=self.stack)

    def mark(self, phase: str, **details: object) -> None:
        payload = {"rank": self.rank, "phase": phase, "monotonic_seconds": time.monotonic(),
                   **details}
        try:
            import torch
            if torch.cuda.is_available() and torch.cuda.is_initialized():
                payload["cuda_allocated_bytes"] = torch.cuda.memory_allocated()
                payload["cuda_peak_bytes"] = torch.cuda.max_memory_allocated()
        except Exception:
            pass
        with self.path.open("ab") as handle:
            handle.write(canonical_bytes(payload, newline=True))
            handle.flush()
            os.fsync(handle.fileno())

    def close(self) -> None:
        faulthandler.cancel_dump_traceback_later()
        self.stack.close()


def _tensor_health(tensors, device, *, require_nonzero: bool) -> tuple[bool, int]:
    """Aggregate CUDA predicates before the one host synchronization."""
    import torch

    finite = torch.ones((), dtype=torch.bool, device=device)
    nonzero = torch.zeros((), dtype=torch.int64, device=device)
    count = 0
    for tensor in tensors:
        if tensor is None:
            continue
        count += 1
        finite = finite & torch.isfinite(tensor).all()
        if require_nonzero:
            nonzero = nonzero + torch.any(tensor != 0).to(torch.int64)
    values = torch.stack((finite.to(torch.int64), nonzero)).cpu().tolist()
    return bool(values[0]) and count > 0, int(values[1])


def _json_fingerprint(value: tuple[float, float]) -> list[float]:
    """Convert a numerical fingerprint to the canonical JSON array type."""
    if len(value) != 2 or not all(math.isfinite(part) for part in value):
        raise ValidationError("FSDP weight fingerprint is invalid")
    return [float(value[0]), float(value[1])]


def _hardware_gate(*, collective_timeout_seconds: int = 600) -> dict:
    import torch
    import torch.distributed as dist

    world = int(os.environ.get("WORLD_SIZE", "0"))
    rank = int(os.environ.get("RANK", "-1"))
    local_rank = int(os.environ.get("LOCAL_RANK", "-1"))
    if (world != 4 or rank not in range(4) or local_rank not in range(4) or
            not torch.cuda.is_available() or torch.cuda.device_count() != 4 or
            not torch.cuda.is_bf16_supported()):
        raise ValidationError("FSDP feasibility requires exactly four visible CUDA GPUs")
    smi = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,uuid",
                          "--format=csv,noheader,nounits"], capture_output=True,
                         text=True, timeout=30, check=True)
    rows = [[part.strip() for part in line.split(",")] for line in smi.stdout.splitlines()]
    if (len(rows) != 4 or any(len(row) != 4 or row[0] != str(index) or
                              "L4" not in row[1] or int(row[2]) < 22000 or not row[3]
                              for index, row in enumerate(rows)) or
            len({row[3] for row in rows}) != 4):
        raise ValidationError("FSDP feasibility requires four distinct L4 UUIDs")
    torch.cuda.set_device(local_rank)
    name = torch.cuda.get_device_name(local_rank)
    if "L4" not in name:
        raise ValidationError("FSDP feasibility requires L4 devices")
    dist.init_process_group("nccl", timeout=timedelta(seconds=collective_timeout_seconds))
    device = torch.device("cuda", local_rank)
    properties = torch.cuda.get_device_properties(local_rank)
    observed = {"rank": rank, "local_rank": local_rank, "name": name,
                "device_uuid": rows[local_rank][3],
                "total_memory_bytes": properties.total_memory}
    all_observed = [None] * 4
    dist.all_gather_object(all_observed, observed)
    if (len({item["local_rank"] for item in all_observed}) != 4 or
            len({item["device_uuid"] for item in all_observed}) != 4 or
            any(not item["device_uuid"] or item["total_memory_bytes"] < 22 * 10**9
                for item in all_observed)):
        raise ValidationError("FSDP ranks do not cover four distinct L4 UUIDs")
    return observed


def _weight_fingerprint(model) -> tuple[float, float]:
    import torch
    import torch.distributed as dist

    local = torch.zeros(2, dtype=torch.float64,
                        device=torch.device("cuda", torch.cuda.current_device()))
    with torch.no_grad():
        for parameter in model.parameters():
            value = parameter.detach().double()
            local[0] += value.sum()
            local[1] += (value * value).sum()
    dist.all_reduce(local)
    return float(local[0].cpu()), float(local[1].cpu())


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
    if (plan.get("run_id") not in {"nvarc-m2-fsdp-feasibility-001",
                                    "nvarc-m2-fsdp-feasibility-002",
                                    "nvarc-m2-fsdp-feasibility-003"} or
            plan.get("kernel_id") != "danielwuu/" + plan["run_id"] or
            plan.get("collective_timeout_seconds", 600) not in {480, 600}):
        raise ValidationError("FSDP run identity or collective timeout differs")
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
    rank = int(os.environ.get("RANK", "-1"))
    trace = _RankTrace(output.parent / (plan["run_id"] + "-diagnostics"), rank)
    trace.mark("input_verified")
    try:
        observed = _hardware_gate(
            collective_timeout_seconds=int(plan.get("collective_timeout_seconds", 600)))
        trace.mark("hardware_gate_complete")
        gate = [None]
        if rank == 0:
            try:
                metadata = compact / "dataset-metadata.json"
                verify_model_material(compact, plan["compact_material_digest"],
                                      allowed_extra_files={"dataset-metadata.json"}
                                      if metadata.exists() else None)
            except Exception as error:
                gate[0] = f"{type(error).__name__}: {error}"
        dist.broadcast_object_list(gate, src=0)
        if gate[0] is not None:
            raise ValidationError("FSDP compact material gate failed: " + gate[0])
        trace.mark("compact_gate_complete")
        model = load_compact_model(compact, dtype="bfloat16")
        trace.mark("model_loaded")
        layer_type = type(model.model.language_model.layers[0])
        wrapped = FSDP(model, auto_wrap_policy=ModuleWrapPolicy({layer_type}),
                       device_id=torch.cuda.current_device(), use_orig_params=True,
                       limit_all_gathers=True,
                       mixed_precision=MixedPrecision(param_dtype=torch.bfloat16,
                                                      reduce_dtype=torch.bfloat16,
                                                       buffer_dtype=torch.bfloat16))
        trace.mark("fsdp_wrapped")
        optimizer = torch.optim.AdamW(wrapped.parameters(), lr=float(plan["learning_rate"]),
                                      weight_decay=float(plan["weight_decay"]))
        torch.cuda.reset_peak_memory_stats()
        trace.mark("fingerprint_before_start")
        before = _json_fingerprint(_weight_fingerprint(wrapped))
        trace.mark("fingerprint_before_complete")
        sequence = sequences[(int(plan["seed"]) + rank) % len(sequences)]
        batch = {key: torch.tensor(value, dtype=torch.long,
                                   device=torch.device("cuda", observed["local_rank"]))
                 for key, value in collate([sequence], int(plan["max_sequence_length"])).items()}
        tokens = int(batch["attention_mask"].sum())
        if tokens > int(plan["maximum_tokens_per_rank"]):
            raise ValidationError("FSDP rank token ceiling exceeded")
        wrapped.train()
        step_started = time.monotonic()
        trace.mark("forward_start", input_tokens=tokens)
        loss = wrapped(**batch).loss
        if not bool(torch.isfinite(loss)):
            raise ValidationError("FSDP SFT loss non-finite")
        trace.mark("forward_complete", loss=float(loss.detach().cpu()))
        trace.mark("backward_start")
        loss.backward()
        trace.mark("backward_complete")
        gradients_ok, nonzero = _tensor_health(
            (parameter.grad for parameter in wrapped.parameters()),
            torch.device("cuda", observed["local_rank"]), require_nonzero=True)
        if not gradients_ok or not nonzero:
            raise ValidationError("FSDP SFT gradient missing or non-finite")
        trace.mark("gradient_check_complete", nonzero_gradient_tensors=nonzero)
        trace.mark("clip_start")
        wrapped.clip_grad_norm_(float(plan["clip_grad_norm"]))
        trace.mark("clip_complete")
        trace.mark("optimizer_start")
        optimizer.step()
        trace.mark("optimizer_complete")
        weights_ok, _ = _tensor_health(
            (parameter for parameter in wrapped.parameters()),
            torch.device("cuda", observed["local_rank"]), require_nonzero=False)
        if not weights_ok:
            raise ValidationError("FSDP SFT updated weight non-finite")
        trace.mark("weight_check_complete")
        torch.cuda.synchronize()
        trace.mark("fingerprint_after_start")
        after = _json_fingerprint(_weight_fingerprint(wrapped))
        trace.mark("fingerprint_after_complete")
        if before == after:
            raise ValidationError("FSDP SFT optimizer did not change weight sum")
        local = {**observed, "input_tokens": tokens, "loss": float(loss.detach().cpu()),
                 "nonzero_gradient_tensors": nonzero,
                 "weight_fingerprint_before": before, "weight_fingerprint_after": after,
                 "step_wall_seconds": time.monotonic() - step_started,
                 "peak_cuda_allocated_mib": torch.cuda.max_memory_allocated() / 1048576}
        all_local = [None] * 4
        trace.mark("result_gather_start")
        dist.all_gather_object(all_local, local)
        trace.mark("result_gather_complete")
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
        trace.mark("completed")
        return result
    except BaseException as error:
        trace.mark("exception", error_type=type(error).__name__,
                   message=str(error)[:1000], stack=traceback.format_exc()[-4000:])
        raise
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()
        trace.close()


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

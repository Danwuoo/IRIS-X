"""Second immutable GPU probe: CPU FSDP state and bounded rank diagnostics."""

from __future__ import annotations

import argparse
from datetime import timedelta
from functools import partial
import gc
import json
import os
from pathlib import Path
import shutil
import time

from .arc_nvarc_fsdp_sft import (_broadcast_error, _load_checkpoint,
    _mark, _save_checkpoint, _verify_compact_base, verify_checkpoint)
from .arc_nvarc_training import load_compact_model, collate
from .arc_nvarc_source_recipe import source_sft_lr
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError

RUN = "nvarc-q35-gpu-preflight-002"
BASE = "sha256:1a8eebd70d811e58c35dc5b1ee27dc18bd73a1066c3ab33adf96ed8427d4c982"
CORPUS_SHA = "63277d77d2af04e2aba487e5a69f64df5113d2d12bc66a449232e1ac70fa6eff"
RECIPE = {"learning_rate": 1e-4, "minimum_learning_rate": 1e-7,
          "warmup_initial_learning_rate": 1e-6, "warmup_steps": 200,
          "schedule_steps": 12716, "betas": [0.9, 0.98], "epsilon": 1e-8,
          "weight_decay": 0.1, "clip_grad_norm": 0.5}
MEMORY_POLICY = {"fsdp_cpu_offload": True, "optimizer_foreach": False,
    "activation_checkpoint": "per-decoder-layer-nonreentrant", "backward_prefetch": None,
    "control_backend": "gloo", "model_backend": "nccl", "control_timeout_seconds": 600,
    "model_timeout_seconds": 180, "heartbeat_timeout_seconds": 120,
    "parameter_dtype": "float32", "optimizer_dtype": "float32", "compute_dtype": "bfloat16"}


def check_plan(plan: dict, rows: list[dict], world: int) -> str:
    fixture = plan.get("backend") == "cpu" and plan.get("synthetic_fixture") is True
    if (plan.get("format") != "irisx/nvarc-q35-gpu-preflight-v2" or
            plan.get("maximum_optimizer_steps") != 2 or plan.get("packing") is not False or
            plan.get("source_recipe") != RECIPE or plan.get("world_size") != world or
            world not in {2, 4} or len(rows) != world * 2 or
            plan.get("maximum_paid_usd") != 0 or plan.get("maximum_generations") != 0 or
            plan.get("maximum_teacher_calls") != 0 or
            plan.get("sample_digest") != digest_value(rows) or
            plan.get("checkpoint_steps") != [1, 2] or plan.get("memory_policy") != MEMORY_POLICY):
        raise ValidationError("GPU preflight plan/schedule differs")
    if not fixture and (world != 4 or plan.get("approved") is not True or
            plan.get("run_id") != RUN or plan.get("owner_decision") != "Decision 0052" or
            plan.get("backend") != "cuda-l4" or plan.get("base_material_digest") != BASE or
            plan.get("corpus_manifest_sha256") != CORPUS_SHA or
            plan.get("sample_digest") != "sha256:11f247f1714d5833db8a8e04c9c5be82dc29bc0407acb3d24530ad9112347e01" or
            plan.get("scheduled_input_tokens") != 47078 or plan.get("maximum_sequence_length") != 11196):
        raise ValidationError("exact Qwen3.5 Kaggle GPU authority required")
    total = 0
    for row in rows:
        ids, labels = row.get("input_ids"), row.get("labels")
        if (not isinstance(ids, list) or not ids or not isinstance(labels, list) or
                len(ids) != len(labels) or len(ids) > plan["maximum_sequence_length"] or
                any(type(x) is not int or not 0 <= x < 16 for x in ids) or
                any(type(y) is not int or y != -100 and y != x for x, y in zip(ids, labels)) or
                not any(y >= 0 for y in labels[1:]) or not row.get("parent_ids")):
            raise ValidationError("GPU preflight whole sequence/labels/lineage differs")
        total += len(ids)
    if total != plan.get("scheduled_input_tokens") or total > plan["maximum_training_tokens"]:
        raise ValidationError("GPU preflight token ceiling differs")
    return digest_value({"plan": plan, "sample_digest": plan["sample_digest"]})


def token_normalized_loss(logits, labels, *, world: int, global_supervised_tokens: int):
    """FSDP averages gradients; compensate to match one global masked-token mean."""
    import torch.nn.functional as F
    if world < 1 or global_supervised_tokens < 1:
        raise ValidationError("positive global supervised token count required")
    total = F.cross_entropy(logits[:, :-1].float().reshape(-1, logits.shape[-1]),
                           labels[:, 1:].reshape(-1), ignore_index=-100, reduction="sum")
    return total * world / global_supervised_tokens, total.detach()


def cpu_fingerprint(model) -> list[float]:
    """Sum CPU shards without temporarily allocating full FP64 shards on GPU."""
    import torch
    import torch.distributed as dist
    values = torch.zeros(2, dtype=torch.float64)
    with torch.no_grad():
        for parameter in model.parameters():
            if parameter.device.type != "cpu" or parameter.dtype != torch.float32:
                raise ValidationError("idle FP32 parameter shards must reside on CPU")
            tensor = parameter.detach().double()
            values[0] += tensor.sum()
            values[1] += tensor.square().sum()
    dist.all_reduce(values)  # Default group is deliberately CPU Gloo.
    if not torch.isfinite(values).all():
        raise ValidationError("CPU shard fingerprint is non-finite")
    return values.tolist()


def memory_snapshot(model, optimizer, device) -> dict:
    """Observe residency without synchronizing a possibly failed CUDA context."""
    import torch
    result = {"parameter_bytes": {}, "gradient_bytes": {}, "optimizer_bytes": {}}
    def account(table, tensor):
        key = tensor.device.type + "/" + str(tensor.dtype)
        table[key] = table.get(key, 0) + tensor.numel() * tensor.element_size()
    for parameter in model.parameters():
        account(result["parameter_bytes"], parameter)
        if parameter.grad is not None:
            account(result["gradient_bytes"], parameter.grad)
    for state in optimizer.state.values():
        for value in state.values():
            if torch.is_tensor(value):
                account(result["optimizer_bytes"], value)
    if device.type == "cuda":
        result.update(cuda_allocated_bytes=torch.cuda.memory_allocated(device),
            cuda_reserved_bytes=torch.cuda.memory_reserved(device),
            cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(device),
            cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved(device))
    status = Path("/proc/self/status")
    if status.is_file():
        result["host_rss_bytes"] = int(next(line.split()[1] for line in status.read_text().splitlines()
            if line.startswith("VmRSS:"))) * 1024
    return result


def require_cpu_residency(snapshot):
    for kind in ("parameter_bytes", "gradient_bytes", "optimizer_bytes"):
        if any(count > 0 and key != "cpu/torch.float32" for key,count in snapshot[kind].items()):
            raise ValidationError("FP32 CPU state residency differs: " + kind)


def record(output, rank, phase, *, model, optimizer, device, **extra):
    value = {"rank": rank, "phase": phase, "monotonic_seconds": time.monotonic(),
             "memory": memory_snapshot(model, optimizer, device), **extra}
    with (output / f"rank-{rank}-memory.jsonl").open("ab") as stream:
        stream.write(canonical_bytes(value, newline=True))
        stream.flush()
        os.fsync(stream.fileno())
    return value["memory"]


def initialize_groups(rank, local_rank, world, gpu):
    import torch
    import torch.distributed as dist
    if gpu:
        from .arc_nvarc_hardware import collect_hardware_inventory
        import subprocess
        if world != 4 or not torch.cuda.is_available() or torch.cuda.device_count() != 4:
            raise ValidationError("four CUDA devices required")
        torch.cuda.set_device(local_rank)
        smi = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,uuid",
            "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True, timeout=30)
        inventory = collect_hardware_inventory(torch, smi.stdout, lambda raw: None)
        if (len(inventory) != 4 or len({x["uuid"] for x in inventory}) != 4 or
                any(x["name"] != "NVIDIA L4" or not x["bf16"] or x["memory_bytes"] < 22 * 10**9 for x in inventory)):
            raise ValidationError("four distinct BF16 L4s required")
        item = inventory[local_rank]
        hardware = {"rank": rank, "local_rank": local_rank, "name": item["name"],
            "device_uuid": item["uuid"], "total_memory_bytes": item["memory_bytes"]}
        device = torch.device("cuda", local_rank)
    else:
        device, hardware = torch.device("cpu"), {"rank": rank, "name": "CPU fixture"}
    dist.init_process_group("gloo", timeout=timedelta(seconds=600))
    observations = [None] * world
    dist.all_gather_object(observations, hardware)
    if gpu and (len({x["device_uuid"] for x in observations}) != 4 or
                len({x["local_rank"] for x in observations}) != 4):
        raise ValidationError("rank UUID coverage differs")
    model_group = dist.new_group(list(range(world)), backend="nccl" if gpu else "gloo",
        timeout=timedelta(seconds=180))
    return device, hardware, model_group


def _retain_checkpoint(output: Path, scratch: Path, reference: dict, identity: str, world: int):
    directory = scratch / reference["path"]
    if directory.parent.resolve() != scratch.resolve() or not directory.name.startswith("checkpoint-step-"):
        raise ValidationError("unsafe GPU probe checkpoint path")
    manifest = verify_checkpoint(directory, identity, world)
    if digest_value(manifest) != reference["manifest_digest"]:
        raise ValidationError("GPU probe checkpoint binding differs")
    name = f"checkpoint-{reference['step']}-manifest.json"
    (output / name).write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


def run(plan_path: Path, model_root: Path, samples_path: Path, output: Path,
        scratch: Path, *, resume: bool = False, stop_after_step: int | None = None) -> dict:
    import torch
    import torch.distributed as dist
    from torch.distributed.fsdp import FullyShardedDataParallel as FSDP, MixedPrecision, CPUOffload
    from torch.distributed.fsdp.wrap import ModuleWrapPolicy
    from torch.distributed.algorithms._checkpoint.checkpoint_wrapper import (
        apply_activation_checkpointing, checkpoint_wrapper, CheckpointImpl, CheckpointWrapper)

    started = time.monotonic()
    plan = json.loads(plan_path.read_bytes())
    rows = json.loads(samples_path.read_bytes())
    rank, world, local_rank = (int(os.environ.get(k, "-1")) for k in ("RANK", "WORLD_SIZE", "LOCAL_RANK"))
    identity = check_plan(plan, rows, world)
    if rank not in range(world) or local_rank not in range(world):
        raise ValidationError("GPU preflight must run under bounded torchrun")
    gpu = plan["backend"] == "cuda-l4"
    device, hardware, model_group = initialize_groups(rank, local_rank, world, gpu)
    phase, model, optimizer = "material-inventory", None, None
    step, input_tokens, supervised_tokens, forwards = 0, 0, 0, 0
    optimizer_steps_returned_this_process = 0
    try:
        error = None
        if rank == 0:
            try:
                _verify_compact_base(model_root, plan["base_material_digest"])
                if not resume:
                    if output.exists() or scratch.exists():
                        raise ValidationError("new GPU preflight output/scratch required")
                    output.mkdir(parents=True)
                    scratch.mkdir(parents=True)
                elif not (scratch / "latest.json").is_file():
                    raise ValidationError("exact GPU preflight checkpoint required")
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        _broadcast_error(error, rank)
        dist.barrier()
        phase = "model-load"
        _mark(output, rank, "model-load-start")
        torch.manual_seed(plan["seed"])
        model = load_compact_model(model_root, dtype="float32")
        model.config.use_cache = False
        model.gradient_checkpointing_disable()
        layer_type = type(model.model.language_model.layers[0])
        expected_layers = len(model.model.language_model.layers)
        mixed = MixedPrecision(param_dtype=torch.bfloat16, reduce_dtype=torch.float32,
                               buffer_dtype=torch.bfloat16) if gpu else None
        wrapped = FSDP(model, auto_wrap_policy=ModuleWrapPolicy({layer_type}), device_id=device,
                       process_group=model_group, cpu_offload=CPUOffload(offload_params=gpu),
                       backward_prefetch=None, forward_prefetch=False,
                       mixed_precision=mixed, use_orig_params=True, limit_all_gathers=True)
        apply_activation_checkpointing(wrapped, checkpoint_wrapper_fn=partial(checkpoint_wrapper,
            checkpoint_impl=CheckpointImpl.NO_REENTRANT), check_fn=lambda m: isinstance(m, layer_type))
        checkpointed_layers = sum(isinstance(m, CheckpointWrapper) for m in wrapped.modules())
        if checkpointed_layers != expected_layers:
            raise ValidationError("all decoder layers must be activation checkpointed")
        _mark(output, rank, "model-wrap-complete")
        optimizer = torch.optim.AdamW(wrapped.parameters(), lr=RECIPE["learning_rate"],
            betas=tuple(RECIPE["betas"]), eps=RECIPE["epsilon"], weight_decay=RECIPE["weight_decay"], foreach=False)
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer,
            lambda step: source_sft_lr(RECIPE, step) / RECIPE["learning_rate"])
        before = cpu_fingerprint(wrapped)
        require_cpu_residency(record(output, rank, "model-ready", model=wrapped, optimizer=optimizer,
            device=device, checkpointed_layers=checkpointed_layers, memory_policy=MEMORY_POLICY,
            gpu_cpu_offload_enabled=gpu))
        restored = None
        if resume:
            phase = "checkpoint-restore"
            state, previous = _load_checkpoint(wrapped, optimizer, scheduler, scratch,
                                               identity, rank, world, device)
            step, input_tokens, forwards = state["step"], state["tokens_seen"], state["forwards"]
            supervised_tokens = state["supervised_tokens_seen"]
            restored = cpu_fingerprint(wrapped)
            if restored != state["weight_fingerprint_after"]:
                raise ValidationError("GPU probe resumed weights differ")
            error = None
            if rank == 0:
                try:
                    _retain_checkpoint(output, scratch, previous, identity, world)
                    directory = scratch / previous["path"]
                    shutil.rmtree(directory)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
            _broadcast_error(error, rank)
            dist.barrier()
            _mark(output, rank, "checkpoint-restored-and-evicted")
            require_cpu_residency(record(output, rank, "checkpoint-restored", model=wrapped,
                optimizer=optimizer, device=device, restored_fingerprint=restored,
                input_tokens_completed=input_tokens, optimizer_steps_completed=step))
        elif stop_after_step not in {None, 1}:
            raise ValidationError("GPU controlled interruption must be step one")
        histories = []
        while step < 2:
            row = rows[step * world + rank]
            batch = {key: torch.tensor(value, dtype=torch.long, device=device)
                     for key, value in collate([row], plan["maximum_sequence_length"]).items()}
            counts = torch.tensor([len(row["input_ids"]), sum(x >= 0 for x in row["labels"][1:])], dtype=torch.int64)
            dist.all_reduce(counts)
            global_input, global_supervised = (int(x) for x in counts.tolist())
            if input_tokens + global_input > plan["maximum_training_tokens"]:
                raise ValidationError("GPU probe cannot truncate its frozen schedule")
            optimizer.zero_grad(set_to_none=True)
            wrapped.train()
            if gpu:
                torch.cuda.reset_peak_memory_stats(device)
            tick = time.monotonic()
            rate = optimizer.param_groups[0]["lr"]
            phase = f"step-{step + 1}-forward"
            _mark(output, rank, f"step-{step + 1}-forward")
            require_cpu_residency(record(output, rank, phase + "-start", model=wrapped,
                optimizer=optimizer, device=device, input_tokens=len(row["input_ids"])))
            logits = wrapped(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"],
                             use_cache=False).logits
            record(output, rank, phase + "-complete", model=wrapped, optimizer=optimizer, device=device)
            loss, local_sum = token_normalized_loss(logits, batch["labels"], world=world,
                                                    global_supervised_tokens=global_supervised)
            if not bool(torch.isfinite(loss)):
                raise ValidationError("GPU preflight loss is non-finite")
            phase = f"step-{step + 1}-backward"
            loss.backward()
            _mark(output, rank, f"step-{step + 1}-backward-complete")
            require_cpu_residency(record(output, rank, phase + "-complete", model=wrapped,
                optimizer=optimizer, device=device))
            del logits, loss, batch
            gc.collect()
            finite, nonzero = torch.ones((), dtype=torch.int64), 0
            for parameter in wrapped.parameters():
                if parameter.grad is not None:
                    finite *= torch.isfinite(parameter.grad).all().to(torch.int64)
                    nonzero += int(torch.any(parameter.grad != 0).item())
            dist.all_reduce(finite, op=dist.ReduceOp.MIN)
            if not finite.item() or nonzero < 1:
                raise ValidationError("GPU preflight gradients missing or non-finite")
            norm = wrapped.clip_grad_norm_(RECIPE["clip_grad_norm"])
            phase = f"step-{step + 1}-optimizer"
            optimizer.step()
            optimizer_steps_returned_this_process += 1
            scheduler.step()
            if gpu:
                torch.cuda.synchronize(device)
            after = cpu_fingerprint(wrapped)
            if after == (restored if step == 1 and restored is not None else before):
                raise ValidationError("GPU preflight weights did not change")
            snapshot = record(output, rank, phase + "-complete", model=wrapped,
                optimizer=optimizer, device=device)
            require_cpu_residency(snapshot)
            global_loss = local_sum.cpu()
            dist.all_reduce(global_loss)
            local = {"rank": rank, "step": step + 1, "source_id": row["source_id"],
                "source_row": row["source_row"], "puzzle_name": row["puzzle_name"],
                "parent_ids": row["parent_ids"], "exposure_tags": row["exposure_tags"],
                "input_tokens": len(row["input_ids"]), "supervised_tokens": sum(x >= 0 for x in row["labels"][1:]),
                "learning_rate": rate, "global_token_mean_loss": float(global_loss.cpu()) / global_supervised,
                "gradient_norm_before_clip": float(norm.cpu()), "finite_gradient_tensors": nonzero,
                "wall_seconds": time.monotonic() - tick, "hardware": hardware,
                "state_residency": snapshot, "checkpointed_layers": checkpointed_layers,
                "fsdp_cpu_offload_enabled": gpu,
                "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device) if gpu else None,
                "peak_cuda_reserved_bytes": torch.cuda.max_memory_reserved(device) if gpu else None}
            observed = [None] * world
            dist.all_gather_object(observed, local)
            histories.append(observed)
            step, input_tokens, supervised_tokens, forwards = (step + 1, input_tokens + global_input,
                supervised_tokens + global_supervised, forwards + world)
            state = {"identity_digest": identity, "world_size": world, "step": step,
                "tokens_seen": input_tokens, "supervised_tokens_seen": supervised_tokens,
                "forwards": forwards, "weight_fingerprint_after": after, "last_rank_observations": observed,
                "contains_evaluator_truth": False}
            phase = f"step-{step}-checkpoint"
            optimizer.zero_grad(set_to_none=True)
            gc.collect()
            if gpu:
                torch.cuda.empty_cache()
            reference = _save_checkpoint(wrapped, optimizer, scheduler, scratch, state, rank, world, device)
            _mark(output, rank, f"step-{step}-checkpoint-saved")
            if rank == 0:
                _retain_checkpoint(output, scratch, reference, identity, world)
            dist.barrier()
            if stop_after_step == step:
                break
        result = {"format": "irisx/nvarc-q35-gpu-preflight-result-v2", "run_id": plan["run_id"],
            "identity_digest": identity, "plan_digest": digest_value(plan), "step": step,
            "input_tokens": input_tokens, "supervised_tokens": supervised_tokens, "forwards": forwards,
            "weight_fingerprint_before": before, "weight_fingerprint_after": after,
            "restored_fingerprint": restored, "checkpoint": reference, "observations": histories,
            "wall_seconds": time.monotonic() - started, "packing_verified": False,
            "full_sft_completed": False, "original_qwen3_nemo_parity": False,
            "contains_evaluator_truth": False, "generation_calls": 0, "teacher_calls": 0}
        result.update(memory_policy=MEMORY_POLICY, checkpointed_layers=checkpointed_layers,
            optimizer_steps_returned_this_process=optimizer_steps_returned_this_process)
        if rank == 0:
            (output / ("final-result.json" if step == 2 else "pause-result.json")).write_bytes(canonical_bytes(result, newline=True))
        dist.barrier()
        return result
    except BaseException as error:
        if output.is_dir():
            diagnostic = {"rank": rank, "run_id": plan["run_id"], "identity_digest": identity,
                "phase": phase, "optimizer_steps_verified": step, "input_tokens_completed": input_tokens,
                "optimizer_steps_returned_this_process": optimizer_steps_returned_this_process,
                "error_type": type(error).__name__, "error_message": str(error)[:1200],
                "contains_evaluator_truth": False}
            if model is not None and optimizer is not None:
                try:
                    diagnostic["memory"] = memory_snapshot(wrapped, optimizer, device)
                except Exception as capture_error:
                    diagnostic["memory_capture_error_type"] = type(capture_error).__name__
            (output / f"rank-{rank}-failure.json").write_bytes(canonical_bytes(diagnostic, newline=True))
        raise
    finally:
        if dist.is_initialized():
            dist.destroy_process_group(model_group)
            dist.destroy_process_group()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("plan", "model", "samples", "output", "scratch"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-step", type=int)
    args = parser.parse_args()
    run(args.plan, args.model, args.samples, args.output, args.scratch,
        resume=args.resume, stop_after_step=args.stop_after_step)

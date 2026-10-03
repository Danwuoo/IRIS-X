"""Unpacked full-parameter Qwen3.5 SFT with sharded optimizer checkpoints.

The same worker runs a two-rank CPU engineering check and an explicitly
approved four-L4 job. A successful CPU run is not evidence of a 4B export.
"""

from __future__ import annotations

import argparse
from datetime import timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time
from typing import Any

from .arc_nvarc_representation import (export_trained_model,
                                        verify_model_material)
from .arc_nvarc_training import collate, load_compact_model
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError

PINNED_COMPACT_4B = "sha256:1a8eebd70d811e58c35dc5b1ee27dc18bd73a1066c3ab33adf96ed8427d4c982"
PINNED_ARC_DATA = "sha256:2903887f4603cb76540c97a0162c2687199003ff92b502e040f0417579b015b4"


def _verify_compact_base(root: Path, digest: str) -> dict:
    """Accept only the known Kaggle Dataset metadata sidecar beside model bytes."""
    metadata = root / "dataset-metadata.json"
    return verify_model_material(root, digest,
                                 allowed_extra_files={"dataset-metadata.json"}
                                 if metadata.exists() else None)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mark(output: Path, rank: int, phase: str) -> None:
    path = output / f"rank-{rank}-trace.jsonl"
    with path.open("ab") as stream:
        stream.write(canonical_bytes({"rank": rank, "phase": phase,
                                      "monotonic_seconds": time.monotonic()}, newline=True))
        stream.flush()
        os.fsync(stream.fileno())


def _broadcast_error(error: str | None, rank: int) -> None:
    import torch.distributed as dist

    value = [error if rank == 0 else None]
    dist.broadcast_object_list(value, src=0)
    if value[0] is not None:
        raise ValidationError(value[0])


def _fingerprint(model: Any, device: Any) -> list[float]:
    import torch
    import torch.distributed as dist

    values = torch.zeros(2, dtype=torch.float64, device=device)
    with torch.no_grad():
        for parameter in model.parameters():
            tensor = parameter.detach().double()
            values[0] += tensor.sum()
            values[1] += (tensor * tensor).sum()
    dist.all_reduce(values)
    result = [float(number) for number in values.cpu().tolist()]
    if not all(math.isfinite(number) for number in result):
        raise ValidationError("FSDP fingerprint is non-finite")
    return result


def _check_plan(plan: dict, compact: Path, sequences_path: Path,
                world: int) -> tuple[list[dict], str]:
    if (plan.get("format") != "irisx/nvarc-m2-fsdp-sft-v1" or
            plan.get("mode") != "full-sft" or plan.get("packing") is not False or
            plan.get("world_size") != world or plan.get("maximum_paid_usd") != 0 or
            plan.get("maximum_teacher_calls") != 0 or
            plan.get("maximum_generations") != 0 or
            plan.get("maximum_optimizer_steps", 0) < 2 or
            plan.get("maximum_training_tokens", 0) < 1 or
            plan.get("max_sequence_length", 0) < 2 or
            plan.get("checkpoint_steps") != [1, plan.get("maximum_optimizer_steps")] or
            plan.get("gradient_accumulation") != 1):
        raise ValidationError("bounded unpacked FSDP SFT plan required")
    if plan.get("backend") == "cuda-l4":
        run_id = plan.get("run_id")
        storage_policy = plan.get("checkpoint_storage", "retained-working")
        identity_ok = (
            (run_id == "nvarc-m2-fsdp-sft-001" and
             plan.get("kernel_id") == "danielwuu/nvarc-m2-fsdp-sft-001" and
             storage_policy == "retained-working" and
             not plan.get("discard_resumed_checkpoint_after_load")) or
            (run_id == "nvarc-m2-fsdp-sft-002" and
             plan.get("kernel_id") == "danielwuu/nvarc-m2-fsdp-sft-002" and
             storage_policy == "ephemeral-scratch" and
             plan.get("discard_resumed_checkpoint_after_load") is True))
        if (plan.get("approved") is not True or world != 4 or
                not plan.get("owner_decision") or
                not identity_ok or
                plan.get("maximum_optimizer_steps") != 8 or
                plan.get("maximum_training_tokens") != 2578 or
                plan.get("scheduled_training_tokens") != 2578 or
                plan.get("sample_stride") != 17 or
                plan.get("max_sequence_length") != 128 or
                plan.get("sequence_count") != 128 or
                plan.get("seed") != 24 or
                plan.get("compact_material_digest") != PINNED_COMPACT_4B or
                plan.get("source_data_manifest_digest") != PINNED_ARC_DATA):
            raise ValidationError("exact owner-approved four-L4 SFT plan required")
    elif (plan.get("backend") != "cpu" or world != 2 or
          plan.get("local_cpu_validation") is not True):
        raise ValidationError("unknown FSDP SFT backend")
    if _sha(sequences_path) != plan.get("sequences_sha256"):
        raise ValidationError("FSDP SFT sequence bytes differ")
    sequences = [json.loads(line) for line in sequences_path.read_text(encoding="utf-8").splitlines()]
    if (len(sequences) != plan.get("sequence_count") or
            digest_value(sequences) != plan.get("sequences_digest") or
            any(len(item["input_ids"]) > plan["max_sequence_length"] or
                len(item["input_ids"]) != len(item["labels"]) or
                not any(label >= 0 for label in item["labels"])
                for item in sequences)):
        raise ValidationError("FSDP SFT frozen sequences differ")
    stride = int(plan.get("sample_stride", 1))
    if stride < 1 or math.gcd(stride, len(sequences)) != 1:
        raise ValidationError("FSDP SFT sample stride must permute the frozen rows")
    scheduled = [sequences[(int(plan["seed"]) + index * stride) % len(sequences)]
                 for index in range(plan["maximum_optimizer_steps"] * world)]
    scheduled_tokens = sum(len(item["input_ids"]) for item in scheduled)
    if (scheduled_tokens > plan["maximum_training_tokens"] or
            (plan.get("scheduled_training_tokens") is not None and
             scheduled_tokens != plan["scheduled_training_tokens"])):
        raise ValidationError("FSDP SFT frozen schedule exceeds or differs from token plan")
    identity = digest_value({"plan": plan, "model_material_digest": plan["compact_material_digest"],
                             "sequences_digest": plan["sequences_digest"]})
    return sequences, identity


def _checkpoint_inventory(directory: Path, state: dict) -> dict:
    (directory / "state.json").write_bytes(canonical_bytes(state, newline=True))
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files.append({"path": path.relative_to(directory).as_posix(),
                          "sha256": _sha(path), "bytes": path.stat().st_size})
    manifest = {"format": "irisx/nvarc-m2-fsdp-checkpoint-v1",
                "state": state, "files": files}
    (directory / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


def verify_checkpoint(directory: Path, identity: str, world: int) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("FSDP checkpoint directory is missing or unsafe")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if (manifest.get("format") != "irisx/nvarc-m2-fsdp-checkpoint-v1" or
            manifest.get("state", {}).get("identity_digest") != identity or
            manifest["state"].get("world_size") != world):
        raise ValidationError("FSDP checkpoint identity differs")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("FSDP checkpoint inventory is empty")
    names = set()
    for entry in entries:
        name = entry.get("path")
        if (not isinstance(name, str) or not name or name in names or
                any(part in {"", ".", ".."} for part in name.split("/")) or
                "\\" in name or ":" in name):
            raise ValidationError("unsafe FSDP checkpoint member")
        names.add(name)
        path = directory / name
        if (path.is_symlink() or not path.is_file() or path.stat().st_size != entry["bytes"] or
                _sha(path) != entry["sha256"]):
            raise ValidationError("FSDP checkpoint member differs")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*")
              if path.is_file() and path.name != "manifest.json"}
    if actual != names or (directory / "state.json").read_bytes() != canonical_bytes(manifest["state"], newline=True):
        raise ValidationError("FSDP checkpoint inventory or state differs")
    return manifest


def _save_checkpoint(wrapped: Any, optimizer: Any, scheduler: Any,
                     output: Path, state: dict, rank: int, world: int,
                     device: Any, *, directory_name: str | None = None, before_publish=None) -> dict:
    import torch
    import torch.distributed as dist
    import torch.distributed.checkpoint as dcp
    from torch.distributed.checkpoint.state_dict import StateDictOptions, get_state_dict

    step = state["step"]
    name = directory_name or f"checkpoint-step-{step:04d}"
    if not name.startswith('checkpoint-step-') or any(value in name for value in ('/', '\\', ':')):
        raise ValidationError('safe checkpoint transaction name required')
    directory = output / name
    error = None
    if rank == 0:
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except Exception as caught:
            error = f'{type(caught).__name__}: {caught}'
    _broadcast_error(error,rank)
    dist.barrier()
    model_state, optimizer_state = get_state_dict(
        wrapped, optimizer, options=StateDictOptions(full_state_dict=False, cpu_offload=True))
    dcp.save({"model": model_state, "optimizer": optimizer_state},
             checkpoint_id=directory / "dcp")
    sidecar = {"rank": rank, "cpu_rng": torch.get_rng_state(),
               "cuda_rng": torch.cuda.get_rng_state(device) if device.type == "cuda" else None,
               "scheduler": scheduler.state_dict()}
    torch.save(sidecar, directory / f"rank-{rank}.pt")
    dist.barrier()
    error = None
    if rank == 0:
        try:
            manifest = _checkpoint_inventory(directory, state)
            reference = {"path": directory.name, "manifest_digest": digest_value(manifest),
                         "step": step}
            if before_publish is not None:
                before_publish(directory)
            temporary = output / "latest.tmp"
            temporary.write_bytes(canonical_bytes(reference, newline=True))
            if before_publish is not None:
                with temporary.open('rb+') as stream:
                    os.fsync(stream.fileno())
            temporary.replace(output / "latest.json")
        except Exception as caught:
            error = f'{type(caught).__name__}: {caught}'
    _broadcast_error(error,rank)
    dist.barrier()
    reference = json.loads((output / "latest.json").read_bytes())
    return reference


def _load_checkpoint(wrapped: Any, optimizer: Any, scheduler: Any,
                     output: Path, identity: str, rank: int, world: int,
                     device: Any) -> tuple[dict, dict]:
    import torch
    import torch.distributed as dist
    import torch.distributed.checkpoint as dcp
    from torch.distributed.checkpoint.state_dict import (StateDictOptions, get_state_dict,
                                                         set_state_dict)

    error = None
    reference = None
    if rank == 0:
        try:
            reference = json.loads((output / "latest.json").read_bytes())
            if (not isinstance(reference.get("path"), str) or
                    not reference["path"].startswith("checkpoint-step-") or
                    "/" in reference["path"] or "\\" in reference["path"]):
                raise ValidationError("unsafe FSDP latest checkpoint path")
            manifest = verify_checkpoint(output / reference["path"], identity, world)
            if digest_value(manifest) != reference["manifest_digest"]:
                raise ValidationError("FSDP latest manifest digest differs")
        except Exception as caught:
            error = f"{type(caught).__name__}: {caught}"
    _mark(output, rank, "resume_manifest_checked")
    _broadcast_error(error, rank)
    values = [reference]
    dist.broadcast_object_list(values, src=0)
    reference = values[0]
    directory = output / reference["path"]
    options = StateDictOptions(full_state_dict=False, cpu_offload=True)
    _mark(output, rank, "resume_get_state_start")
    model_state, optimizer_state = get_state_dict(wrapped, optimizer, options=options)
    _mark(output, rank, "resume_get_state_complete")
    payload = {"model": model_state, "optimizer": optimizer_state}
    _mark(output, rank, "resume_dcp_load_start")
    dcp.load(payload, checkpoint_id=directory / "dcp")
    _mark(output, rank, "resume_dcp_load_complete")
    set_state_dict(wrapped, optimizer, model_state_dict=payload["model"],
                   optim_state_dict=payload["optimizer"], options=options)
    _mark(output, rank, "resume_set_state_complete")
    sidecar = torch.load(directory / f"rank-{rank}.pt", map_location="cpu", weights_only=True)
    if sidecar["rank"] != rank:
        raise ValidationError("FSDP RNG sidecar rank differs")
    scheduler.load_state_dict(sidecar["scheduler"])
    torch.set_rng_state(sidecar["cpu_rng"])
    if device.type == "cuda":
        torch.cuda.set_rng_state(sidecar["cuda_rng"], device)
    state = json.loads((directory / "state.json").read_bytes())
    return state, reference


def run(plan_path: Path, compact: Path, sequences_path: Path, output: Path,
        *, resume: bool = False, stop_after_steps: int | None = None) -> dict:
    import torch
    import torch.distributed as dist
    from torch.distributed.fsdp import FullyShardedDataParallel as FSDP, MixedPrecision
    from torch.distributed.fsdp.wrap import ModuleWrapPolicy

    started = time.monotonic()
    plan = json.loads(plan_path.read_bytes())
    rank = int(os.environ.get("RANK", "-1"))
    world = int(os.environ.get("WORLD_SIZE", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "-1"))
    if rank not in range(world) or world not in {2, 4}:
        raise ValidationError("FSDP SFT must run under bounded torchrun")
    sequences, identity = _check_plan(plan, compact, sequences_path, world)
    gpu = plan["backend"] == "cuda-l4"
    if gpu:
        from .arc_nvarc_fsdp import _hardware_gate
        observed = _hardware_gate(collective_timeout_seconds=int(plan.get("collective_timeout_seconds", 600)))
        device = torch.device("cuda", observed["local_rank"])
    else:
        dist.init_process_group("gloo", timeout=timedelta(seconds=180))
        device = torch.device("cpu")
    try:
        error = None
        if rank == 0:
            try:
                _verify_compact_base(compact, plan["compact_material_digest"])
                if (resume and not (output / "latest.json").is_file()) or (not resume and output.exists()):
                    raise ValidationError("new output or exact resume checkpoint required")
            except Exception as caught:
                error = f"{type(caught).__name__}: {caught}"
        _broadcast_error(error, rank)
        if rank == 0 and not resume:
            output.mkdir(parents=True)
        dist.barrier()
        _mark(output, rank, "model_load_start")
        torch.manual_seed(int(plan["seed"]) + rank)
        model = load_compact_model(compact, dtype="bfloat16" if gpu else "float32")
        layer_type = type(model.model.language_model.layers[0])
        mixed = (MixedPrecision(param_dtype=torch.bfloat16, reduce_dtype=torch.bfloat16,
                                buffer_dtype=torch.bfloat16) if gpu else None)
        wrapped = FSDP(model, auto_wrap_policy=ModuleWrapPolicy({layer_type}),
                       device_id=device, use_orig_params=True, limit_all_gathers=True,
                       mixed_precision=mixed)
        _mark(output, rank, "model_wrap_complete")
        optimizer = torch.optim.AdamW(wrapped.parameters(), lr=float(plan["learning_rate"]),
                                      weight_decay=float(plan.get("weight_decay", 0.0)))
        total_steps = int(plan["maximum_optimizer_steps"])
        scheduler = torch.optim.lr_scheduler.LambdaLR(
            optimizer, lambda step: max(0.0, (total_steps - step) / total_steps))
        step = tokens_seen = forwards = 0
        initial_fingerprint = _fingerprint(wrapped, device)
        _mark(output, rank, "initial_fingerprint_complete")
        previous = None
        if resume:
            state, previous = _load_checkpoint(wrapped, optimizer, scheduler, output,
                                               identity, rank, world, device)
            _mark(output, rank, "resume_load_complete")
            step, tokens_seen, forwards = (state["step"], state["tokens_seen"],
                                            state["forwards"])
            if step >= total_steps:
                raise ValidationError("terminal FSDP checkpoint cannot be resumed")
            restored = _fingerprint(wrapped, device)
            if any(abs(left - right) > 1e-5 for left, right in
                   zip(restored, state["weight_fingerprint_after"])):
                raise ValidationError("FSDP resumed weights differ from saved fingerprint")
            if plan.get("discard_resumed_checkpoint_after_load") is True:
                dist.barrier()
                cleanup_error = None
                if rank == 0:
                    try:
                        old_checkpoint = output / previous["path"]
                        if (old_checkpoint.parent.resolve() != output.resolve() or
                                state["step"] != 1 or previous["step"] != 1):
                            raise ValidationError("unsafe resumed FSDP checkpoint cleanup")
                        first_manifest = json.loads((old_checkpoint / "manifest.json").read_bytes())
                        if digest_value(first_manifest) != previous["manifest_digest"]:
                            raise ValidationError("resumed FSDP checkpoint manifest changed")
                        (output / "first-checkpoint-manifest.json").write_bytes(
                            canonical_bytes(first_manifest, newline=True))
                        shutil.rmtree(old_checkpoint)
                        (output / "resume-evicted.json").write_bytes(canonical_bytes(
                            {"format": "irisx/nvarc-m2-fsdp-resume-evicted-v1",
                             "identity_digest": identity,
                             "checkpoint_manifest_digest": previous["manifest_digest"],
                             "step": state["step"], "contains_evaluator_truth": False},
                            newline=True))
                    except Exception as caught:
                        cleanup_error = f"{type(caught).__name__}: {caught}"
                _broadcast_error(cleanup_error, rank)
                dist.barrier()
                _mark(output, rank, "resumed_checkpoint_evicted")
        elif stop_after_steps is not None and stop_after_steps not in plan["checkpoint_steps"]:
            raise ValidationError("controlled interruption must align with checkpoint")
        if gpu:
            torch.cuda.reset_peak_memory_stats(device)
        call_start = forwards
        histories = []
        stop_reason = "maximum_steps"
        while step < total_steps:
            item = sequences[(int(plan["seed"]) +
                              (step * world + rank) * int(plan.get("sample_stride", 1))) % len(sequences)]
            batch = {key: torch.tensor(value, dtype=torch.long, device=device)
                     for key, value in collate([item], plan["max_sequence_length"]).items()}
            local_tokens = int(batch["attention_mask"].sum().item())
            counts = torch.tensor([local_tokens], dtype=torch.int64, device=device)
            dist.all_reduce(counts)
            global_tokens = int(counts.item())
            if tokens_seen + global_tokens > plan["maximum_training_tokens"]:
                raise ValidationError("FSDP SFT token ceiling would truncate frozen schedule")
            step_started = time.monotonic()
            wrapped.train()
            optimizer.zero_grad(set_to_none=True)
            loss = wrapped(**batch).loss
            if not bool(torch.isfinite(loss)):
                raise ValidationError("non-finite FSDP SFT loss")
            loss.backward()
            finite = torch.ones((), dtype=torch.int64, device=device)
            nonzero = torch.zeros((), dtype=torch.int64, device=device)
            for parameter in wrapped.parameters():
                if parameter.grad is not None:
                    finite *= torch.isfinite(parameter.grad).all().to(torch.int64)
                    nonzero += torch.any(parameter.grad != 0).to(torch.int64)
            dist.all_reduce(finite, op=dist.ReduceOp.MIN)
            dist.all_reduce(nonzero)
            if not bool(finite.item()) or not int(nonzero.item()):
                raise ValidationError("FSDP gradient missing or non-finite")
            wrapped.clip_grad_norm_(float(plan.get("clip_grad_norm", 1.0)))
            optimizer.step()
            scheduler.step()
            for parameter in wrapped.parameters():
                finite *= torch.isfinite(parameter).all().to(torch.int64)
            dist.all_reduce(finite, op=dist.ReduceOp.MIN)
            if not bool(finite.item()):
                raise ValidationError("FSDP updated weight non-finite")
            step += 1
            forwards += world
            tokens_seen += global_tokens
            if gpu:
                torch.cuda.synchronize(device)
            after = _fingerprint(wrapped, device)
            if step == 1 and after == initial_fingerprint:
                raise ValidationError("FSDP SFT weights did not change")
            local = {"rank": rank, "step": step, "input_tokens": local_tokens,
                     "loss": float(loss.detach().cpu()), "nonzero_gradient_tensors": int(nonzero.item()),
                     "wall_seconds": time.monotonic() - step_started,
                     "peak_cuda_allocated_mib": (torch.cuda.max_memory_allocated(device) / 1048576
                                                  if gpu else None)}
            observed = [None] * world
            dist.all_gather_object(observed, local)
            histories.append(observed)
            if step in plan["checkpoint_steps"]:
                state = {"format": "irisx/nvarc-m2-fsdp-state-v1",
                         "identity_digest": identity, "world_size": world,
                         "step": step, "cursor": step * world, "forwards": forwards,
                         "tokens_seen": tokens_seen, "weight_fingerprint_after": after,
                         "last_rank_observations": observed, "contains_evaluator_truth": False}
                previous = _save_checkpoint(wrapped, optimizer, scheduler, output,
                                            state, rank, world, device)
                _mark(output, rank, "checkpoint_save_complete")
            if stop_after_steps == step:
                stop_reason = "controlled_interruption"
                break
        result = {"format": "irisx/nvarc-m2-fsdp-sft-result-v1",
                  "identity_digest": identity, "base_material_digest": plan["compact_material_digest"],
                  "sequences_digest": plan["sequences_digest"],
                  "step": step, "tokens_seen": tokens_seen, "forwards": forwards,
                  "invocation_forwards": forwards - call_start,
                  "checkpoint": previous, "export_material_digest": None,
                  "stop_reason": stop_reason, "observations": histories,
                  "wall_seconds": time.monotonic() - started,
                  "contains_evaluator_truth": False}
        if rank == 0:
            (output / ("final-result.json" if step == total_steps else "pause-result.json")).write_bytes(
                canonical_bytes(result, newline=True))
        dist.barrier()
        return result
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()


def export_from_checkpoint(plan_path: Path, compact: Path, sequences_path: Path,
                           output: Path) -> dict:
    """Consolidate DCP shards after workers exit; reload the inference export."""
    import gc
    import torch
    import torch.distributed.checkpoint as dcp

    started = time.monotonic()
    plan = json.loads(plan_path.read_bytes())
    sequences, identity = _check_plan(plan, compact, sequences_path, plan["world_size"])
    del sequences
    _verify_compact_base(compact, plan["compact_material_digest"])
    result = json.loads((output / "final-result.json").read_bytes())
    if (result.get("identity_digest") != identity or
            result.get("step") != plan["maximum_optimizer_steps"] or
            result.get("stop_reason") != "maximum_steps"):
        raise ValidationError("complete FSDP SFT result required for export")
    reference = json.loads((output / "latest.json").read_bytes())
    if reference != result["checkpoint"] or reference["step"] != result["step"]:
        raise ValidationError("FSDP result and latest checkpoint differ")
    checkpoint = output / reference["path"]
    manifest = verify_checkpoint(checkpoint, identity, plan["world_size"])
    if digest_value(manifest) != reference["manifest_digest"]:
        raise ValidationError("FSDP checkpoint manifest differs")
    if (output / "export").exists() or (output / "export-chain.json").exists():
        raise ValidationError("new FSDP inference export required")
    model = load_compact_model(compact, dtype="bfloat16" if plan["backend"] == "cuda-l4"
                               else "float32")
    model_state = model.state_dict()
    dcp.load({"model": model_state}, checkpoint_id=checkpoint / "dcp", no_dist=True)
    model.load_state_dict(model_state)
    source_fingerprint = [sum(float(parameter.double().sum()) for parameter in model.parameters()),
                          sum(float((parameter.double() ** 2).sum()) for parameter in model.parameters())]
    expected = manifest["state"]["weight_fingerprint_after"]
    if any(abs(left - right) > 1e-4 * max(1.0, abs(right))
           for left, right in zip(source_fingerprint, expected)):
        raise ValidationError("consolidated FSDP model differs from saved weights")
    export_digest = export_trained_model(model, compact, output / "export",
                                         training_identity_digest=identity)
    verify_model_material(output / "export", export_digest)
    del model_state, model
    gc.collect()
    reloaded = load_compact_model(output / "export", dtype="bfloat16" if
                                  plan["backend"] == "cuda-l4" else "float32")
    reloaded_fingerprint = [sum(float(parameter.double().sum()) for parameter in reloaded.parameters()),
                            sum(float((parameter.double() ** 2).sum()) for parameter in reloaded.parameters())]
    if any(abs(left - right) > 1e-4 * max(1.0, abs(left))
           for left, right in zip(source_fingerprint, reloaded_fingerprint)):
        raise ValidationError("FSDP inference export changed on reload")
    chain = {"format": "irisx/nvarc-m2-fsdp-export-chain-v1",
             "identity_digest": identity,
             "plan_sha256": _sha(plan_path), "sequences_sha256": _sha(sequences_path),
             "base_material_digest": plan["compact_material_digest"],
             "checkpoint_manifest_digest": reference["manifest_digest"],
             "checkpoint_step": reference["step"],
             "export_material_digest": export_digest,
             "saved_weight_fingerprint": expected,
             "consolidated_weight_fingerprint": source_fingerprint,
             "reloaded_weight_fingerprint": reloaded_fingerprint,
             "elapsed_seconds": time.monotonic() - started,
             "contains_evaluator_truth": False}
    (output / "export-chain.json").write_bytes(canonical_bytes(chain, newline=True))
    return chain


def package_checkpoint_transport(output: Path, *, maximum_member_bytes: int = 1_750_000_000) -> dict:
    """Split large DCP members for bounded terminal retrieval after export."""
    if maximum_member_bytes < 1024:
        raise ValidationError("checkpoint transport member bound is invalid")
    chain = json.loads((output / "export-chain.json").read_bytes())
    result = json.loads((output / "final-result.json").read_bytes())
    if (chain["identity_digest"] != result["identity_digest"] or
            chain["checkpoint_manifest_digest"] != result["checkpoint"]["manifest_digest"]):
        raise ValidationError("checkpoint transport lacks a matching inference export")
    checkpoint = output / result["checkpoint"]["path"]
    manifest = verify_checkpoint(checkpoint, chain["identity_digest"],
                                 json.loads((output.parent / "plan.json").read_bytes())["world_size"])
    if digest_value(manifest) != chain["checkpoint_manifest_digest"]:
        raise ValidationError("checkpoint transport source digest differs")
    transport = output / "checkpoint-transport"
    transport.mkdir(exist_ok=False)
    entries = []
    for member in manifest["files"]:
        path = checkpoint / member["path"]
        if member["bytes"] <= maximum_member_bytes:
            continue
        stem = member["path"].replace("/", "--")
        parts = []
        with path.open("rb") as source:
            index = 0
            while True:
                target = transport / f"{stem}.part-{index:04d}"
                digest = hashlib.sha256()
                written = 0
                with target.open("wb") as stream:
                    while written < maximum_member_bytes:
                        chunk = source.read(min(4 * 1024 * 1024,
                                                maximum_member_bytes - written))
                        if not chunk:
                            break
                        stream.write(chunk)
                        digest.update(chunk)
                        written += len(chunk)
                if written == 0:
                    target.unlink()
                    break
                parts.append({"path": target.name, "sha256": digest.hexdigest(),
                              "bytes": written})
                index += 1
        if sum(item["bytes"] for item in parts) != member["bytes"]:
            raise ValidationError("checkpoint transport split size differs")
        combined = hashlib.sha256()
        for part in parts:
            with (transport / part["path"]).open("rb") as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    combined.update(chunk)
        if combined.hexdigest() != member["sha256"]:
            raise ValidationError("checkpoint transport split hash differs")
        entries.append({"original": member, "parts": parts})
        path.unlink()
    report = {"format": "irisx/nvarc-m2-fsdp-checkpoint-transport-v1",
              "identity_digest": chain["identity_digest"],
              "checkpoint_manifest_digest": chain["checkpoint_manifest_digest"],
              "maximum_member_bytes": maximum_member_bytes,
              "split_members": entries, "contains_evaluator_truth": False}
    (transport / "manifest.json").write_bytes(canonical_bytes(report, newline=True))
    return report


def restore_checkpoint_transport(output: Path, destination: Path) -> dict:
    """Reconstruct and verify the retained DCP checkpoint after retrieval."""
    report = json.loads((output / "checkpoint-transport/manifest.json").read_bytes())
    if report.get("format") != "irisx/nvarc-m2-fsdp-checkpoint-transport-v1":
        raise ValidationError("checkpoint transport format differs")
    result = json.loads((output / "final-result.json").read_bytes())
    source = output / result["checkpoint"]["path"]
    if (destination.exists() or result["identity_digest"] != report["identity_digest"] or
            result["checkpoint"]["manifest_digest"] != report["checkpoint_manifest_digest"]):
        raise ValidationError("checkpoint transport destination or lineage differs")
    if (source.is_symlink() or not source.is_dir() or
            any(path.is_symlink() for path in source.rglob("*"))):
        raise ValidationError("unsafe checkpoint transport source tree")
    shutil.copytree(source, destination)
    for entry in report["split_members"]:
        original = entry["original"]
        relative = original["path"]
        if (not isinstance(relative, str) or not relative or
                any(part in {"", ".", ".."} for part in relative.split("/")) or
                "\\" in relative or ":" in relative):
            raise ValidationError("unsafe split checkpoint path")
        target = destination / relative
        if target.exists() or not target.parent.is_dir():
            raise ValidationError("split checkpoint target already exists")
        with target.open("wb") as stream:
            for part in entry["parts"]:
                name = part["path"]
                if (not isinstance(name, str) or not name or "/" in name or
                        "\\" in name or ":" in name or name in {".", ".."}):
                    raise ValidationError("unsafe split checkpoint member")
                path = output / "checkpoint-transport" / name
                if (not path.is_file() or path.is_symlink() or
                        path.stat().st_size != part["bytes"] or _sha(path) != part["sha256"]):
                    raise ValidationError("split checkpoint member differs")
                with path.open("rb") as input_stream:
                    shutil.copyfileobj(input_stream, stream, length=4 * 1024 * 1024)
        if target.stat().st_size != original["bytes"] or _sha(target) != original["sha256"]:
            raise ValidationError("reconstructed checkpoint member differs")
    manifest = verify_checkpoint(destination, report["identity_digest"],
                                 json.loads((output.parent / "plan.json").read_bytes())["world_size"])
    if digest_value(manifest) != report["checkpoint_manifest_digest"]:
        raise ValidationError("reconstructed checkpoint manifest digest differs")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-steps", type=int)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--package-transport", action="store_true")
    parser.add_argument("--maximum-member-bytes", type=int, default=1_750_000_000)
    args = parser.parse_args()
    if args.export and args.package_transport:
        parser.error("export and checkpoint transport are separate stages")
    if args.export:
        if args.resume or args.stop_after_steps is not None:
            parser.error("export does not accept resume or stop-after-steps")
        export_from_checkpoint(args.plan, args.compact, args.sequences, args.output)
    elif args.package_transport:
        if args.resume or args.stop_after_steps is not None:
            parser.error("checkpoint transport does not accept training flags")
        package_checkpoint_transport(args.output,
                                     maximum_member_bytes=args.maximum_member_bytes)
    else:
        run(args.plan, args.compact, args.sequences, args.output,
            resume=args.resume, stop_after_steps=args.stop_after_steps)


if __name__ == "__main__":
    main()

"""Token-normalized accumulation using reduced FP32 CPU gradient shards.

FSDP CPU offload replaces reduced gradients on each backward. Accumulate
explicit detached CPU shards, then copy into the final FSDP gradient views;
no full unsharded GPU gradients are retained through no_sync().
"""
from __future__ import annotations

import time
from typing import Any, Sequence

from .arc_nvarc_gpu_preflight_v2 import memory_snapshot, require_cpu_residency
from .arc_nvarc_packing import pack_sequences, iter_isolated_forwards
from .canonical import digest_value
from .errors import ValidationError


def source_optimizer(model: Any, recipe: dict) -> tuple[Any, Any]:
    import torch
    from .arc_nvarc_source_recipe import source_sft_lr
    optimizer = torch.optim.AdamW(model.parameters(), lr=recipe["learning_rate"],
        betas=tuple(recipe.get("betas", recipe.get("optimizer_betas", (.9, .98)))),
        eps=recipe.get("epsilon", recipe.get("optimizer_eps", 1e-8)),
        weight_decay=recipe["weight_decay"], foreach=False)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer,
        lambda step: source_sft_lr(recipe, step) / recipe["learning_rate"])
    return optimizer, scheduler


def train_source_step(model: Any, optimizer: Any, scheduler: Any, rows: Sequence[dict],
                      *, device: Any, recipe: dict, capacity: int = 256000,
                      length_multiple: int = 64, distributed: bool = True,
                      packed_backend: str | None = None,
                      maximum_packed_input_tokens: int | None = None) -> dict:
    """One full optimizer step; every rank runs equal forward/backward slots.

    The default process group must be CPU Gloo. Model/FSDP collectives may use
    a separate NCCL group. Empty-rank slots use a connected zero loss and are
    counted separately; they contribute no input/supervision to training totals.
    """
    import torch
    import torch.distributed as dist
    if distributed and (not dist.is_initialized() or dist.get_backend() != "gloo"):
        raise ValidationError("CPU Gloo control process group required")
    rank, world = (dist.get_rank(), dist.get_world_size()) if distributed else (0, 1)
    packs = pack_sequences(rows, capacity=capacity, length_multiple=length_multiple)
    totals = torch.tensor([sum(p["input_tokens"] for p in packs),
        sum(p["supervised_tokens"] for p in packs), len(rows)], dtype=torch.int64)
    if packed_backend not in {None, 'dense-sdpa-reference', 'torch-varlen-flash'}:
        raise ValidationError('unknown source packed-step backend')
    if maximum_packed_input_tokens is not None:
        if packed_backend is None:raise ValidationError('physical chunking requires explicit packed execution')
        from .arc_nvarc_qwen3_packing import execution_slices
        physical_packs=[piece for pack in packs for piece in execution_slices(pack,maximum_packed_input_tokens)]
    else:physical_packs=packs
    local_slots = len(rows) if packed_backend is None else len(physical_packs)
    slots = torch.tensor([local_slots], dtype=torch.int64)
    if distributed:
        dist.all_reduce(totals)
        dist.all_reduce(slots, op=dist.ReduceOp.MAX)
    if totals[1] < 1 or slots.item() < 1:
        raise ValidationError("global source step has no supervised samples")
    global_input, global_supervised, global_rows = totals.tolist()
    model.train()
    parameters = dict(model.named_parameters())
    summed = {}
    real = dummy = 0
    detached_loss = torch.zeros((), dtype=torch.float64)
    started, rate = time.monotonic(), optimizer.param_groups[0]["lr"]
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    def forwards():
        for pack in (packs if packed_backend is None else physical_packs):
            if packed_backend is None:
                yield from iter_isolated_forwards(model, pack, device)
            else:
                from .arc_nvarc_qwen3_packing import packed_forward
                yield packed_forward(model, pack, backend=packed_backend,device=device)
    iterator = forwards()
    try:
        for slot in range(int(slots.item())):
            optimizer.zero_grad(set_to_none=True)
            if slot < local_slots:
                item = next(iterator)
                loss = item["loss_sum"] * world / global_supervised
                detached_loss += item["loss_sum"].detach().double().cpu()
                real += 1
            else:
                ids = torch.tensor([[14, 15]], dtype=torch.long, device=device)
                if packed_backend is None:
                    value = model(input_ids=ids, attention_mask=torch.ones_like(ids),
                        use_cache=False, past_key_values=None).logits
                else:
                    from .arc_nvarc_qwen3_packing import packed_forward
                    dummy_pack=pack_sequences([{'input_ids':[14,15],'labels':[-100,15]}],
                        capacity=capacity,length_multiple=length_multiple)[0]
                    value=packed_forward(model,dummy_pack,backend=packed_backend,device=device)['logits']
                loss = value.float().sum() * 0
                dummy += 1
            if not bool(torch.isfinite(loss)):
                raise ValidationError("nonfinite source microstep loss")
            loss.backward()
            del loss
            if slot < local_slots:
                del item
            else:
                del value
            valid = torch.ones((), dtype=torch.int64)
            for name, parameter in parameters.items():
                gradient = parameter.grad
                if gradient is None or not gradient.numel():
                    continue
                if gradient.device.type != "cpu" or gradient.dtype != torch.float32:
                    raise ValidationError("source accumulation requires reduced FP32 CPU shards")
                valid *= torch.isfinite(gradient).all().to(torch.int64)
                if name not in summed:
                    summed[name] = gradient.detach().clone()
                else:
                    summed[name].add_(gradient.detach())
            if distributed:
                dist.all_reduce(valid, op=dist.ReduceOp.MIN)
            if not valid.item():
                raise ValidationError("nonfinite source microstep gradients")
        nonzero, accumulated_bytes = 0, 0
        for name, gradient in summed.items():
            parameter = parameters[name]
            if parameter.grad is None or parameter.grad.shape != gradient.shape:
                raise ValidationError("final FSDP gradient view does not cover an accumulated shard")
            # Preserve the FSDP flat shard/view relationship for clipping and AdamW.
            parameter.grad.copy_(gradient)
            nonzero += int(torch.any(gradient != 0).item())
            accumulated_bytes += gradient.numel() * gradient.element_size()
        active = torch.tensor([nonzero], dtype=torch.int64)
        if distributed:
            dist.all_reduce(active)
        if not active.item():
            raise ValidationError("source global step has no nonzero gradient")
        norm = (model.clip_grad_norm_(recipe["clip_grad_norm"])
                if distributed else torch.nn.utils.clip_grad_norm_(model.parameters(), recipe["clip_grad_norm"]))
        if not bool(torch.isfinite(norm)):
            raise ValidationError("source global gradient norm is nonfinite")
        optimizer.step()
        scheduler.step()
        if distributed:
            dist.all_reduce(detached_loss)
        snapshot = memory_snapshot(model, optimizer, device)
        require_cpu_residency(snapshot)
        return {"rank": rank, "world_size": world, "real_forward_calls": real,
            "dummy_forward_calls": dummy, "collective_slots": int(slots.item()),
            "global_input_tokens": global_input, "global_supervised_tokens": global_supervised,
            "global_sequence_count": global_rows, "global_token_mean_loss": float(detached_loss) / global_supervised,
            "learning_rate": rate, "gradient_norm_before_clip": float(norm.cpu()),
            "finite_nonzero_shards": nonzero, "cpu_accumulation_bytes": accumulated_bytes,
            "owned_parameter_shards":sum(bool(p.numel()) for p in parameters.values()),
            "accumulated_parameter_shards":len(summed),
            "missing_owned_gradient_shards":[name for name,p in parameters.items() if p.numel() and name not in summed],
            "state_residency": snapshot, "packing_layout_digests": [digest_value(p) for p in packs],
            "physical_packing_layout_digests": [digest_value(p) for p in physical_packs],
            "maximum_packed_input_tokens":maximum_packed_input_tokens,
            "wall_seconds": time.monotonic() - started,
            "packing_execution": packed_backend or "isolated-segments",
            "fused_packing_verified": packed_backend == 'torch-varlen-flash'}
    finally:
        iterator.close()
        summed.clear()

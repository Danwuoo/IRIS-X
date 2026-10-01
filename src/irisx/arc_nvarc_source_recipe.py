"""Pinned Qwen notebook context handling and complete task-local epoch.

This opt-in path keeps the historical short-step profiles unchanged. It is a
Qwen3.5 reference backend, not Unsloth numerical or performance parity.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .errors import ValidationError


class SourceTextTokenizer:
    """Map the notebook's literal grid chat format onto verified compact rows."""

    _pattern = re.compile(r"<\|im_start\|>|<\|im_end\|>|assistant|user|[0-9\n]")

    def encode(self, text: str) -> list[int]:
        special = {"<|im_start|>": 14, "<|im_end|>": 15,
                   "user": 11, "assistant": 12, "\n": 10}
        result, cursor = [], 0
        for match in self._pattern.finditer(text):
            if match.start() != cursor:
                raise ValidationError("non-grid source formatter text")
            value = match.group()
            result.append(special[value] if value in special else int(value))
            cursor = match.end()
        if cursor != len(text):
            raise ValidationError("non-grid source formatter suffix")
        return result


def cut_source_dataset(dataset: Any, *, name: str, max_length: int) -> Any:
    """Call the original cut_to_len after proving its final sample can fit.

    The original loop cannot handle an oversized irreducible query. With no
    reply, get() also formats a training challenge even when measuring input,
    so at least one demonstration must remain. Reject before entering it;
    retain complete examples and EOS without modifying the source cell.
    """
    from .arc_nvarc_upstream import qwen_cell

    if name not in {"text", "input"} or type(max_length) is not int or max_length < 2:
        raise ValidationError("source context bound differs")
    formatter = qwen_cell("arc_loader.py").QwenFormatter(SourceTextTokenizer())
    cls = type(dataset)
    for key in dataset.keys:
        query = dataset.queries[key]
        needs_demo = name == "text" or key not in dataset.replies
        if not query["train"] and needs_demo:
            raise ValidationError("source adaptation has no demonstration")
        mandatory = {**query, "train": query["train"][-1:] if needs_demo else []}
        smallest = cls(queries={key: mandatory}, replies={key: dataset.replies[key]}
                       if key in dataset.replies else {}, keys=[key])
        if smallest.get_length(key, formatter, name) > max_length:
            raise ValidationError("irreducible source example exceeds context bound")
    return dataset.cut_to_len(formatter=formatter, name=name, max_len=max_length)


def cpu_state_adamw(parameters,*,lr):
    """Keep AdamW mirrors/moments on CPU, copying clipped gradients and updates.

    This opt-in resource adapter uses the same PyTorch AdamW algorithm. CPU/GPU
    kernel parity is not inferred; the CPU differential oracle is bitwise.
    """
    import torch
    originals=list(parameters)
    class CPUStateAdamW(torch.optim.AdamW):
        def __init__(self):
            # PEFT's tied embedding/head adapters can be different Parameter
            # objects sharing transposed storage. Preserve that alias topology;
            # independent clones silently change AdamW's two updates.
            storages={};mirrors=[]
            for value in originals:
                storage=value.untyped_storage()
                key=(str(value.device),storage.data_ptr(),storage.nbytes(),str(value.dtype))
                if key not in storages:
                    storages[key]=value.detach().as_strided((storage.nbytes()//value.element_size(),),(1,),0).cpu().clone()
                mirrors.append(torch.nn.Parameter(storages[key].as_strided(value.shape,value.stride(),value.storage_offset())))
            super().__init__(mirrors,lr=lr,weight_decay=0.)
            self.mirrors=mirrors
        def step(self,closure=None):
            if closure is not None:raise ValidationError('CPU source optimizer closure unsupported')
            for original,mirror in zip(originals,self.mirrors):
                mirror.grad=None if original.grad is None else original.grad.detach().cpu().clone()
            result=super().step()
            with torch.no_grad():
                for original,mirror in zip(originals,self.mirrors):original.copy_(mirror)
            return result
        def zero_grad(self,set_to_none=True):
            super().zero_grad(set_to_none=set_to_none)
            for original in originals:original.grad=None
    return CPUStateAdamW()


def train_source_epoch(adapter: Any, task: dict) -> Any:
    """Consume every source augmentation exactly once with notebook scheduling."""
    import torch
    from transformers import get_cosine_schedule_with_warmup
    from .arc_nvarc_training import task_local_sequences, collate, _torch_batch

    config = adapter.config
    if config.get("source_qwen") is not True:
        raise ValidationError("source epoch requires source demonstrations and masks")
    examples = task_local_sequences(task, seed=int(config["seed"]),
        augmentation_count=int(config["augmentation_count"]), source_qwen=True,
        source_augmentation_seed=int(config.get("source_augmentation_seed", 1)),
        source_max_length=int(config["max_sequence_length"]))
    steps, tokens = len(examples), sum(len(item["input_ids"]) for item in examples)
    for key, actual in (("maximum_optimizer_steps", steps), ("maximum_training_tokens", tokens)):
        limit = config.get(key)
        if type(limit) is not int or limit < actual:
            raise ValidationError(f"complete source epoch exceeds {key}")
    ratio = config.get("warmup_ratio", 0.1)
    clip = config.get("clip_grad_norm", 1.0)
    if (type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 <= ratio < 1 or
            type(clip) not in (int, float) or not math.isfinite(clip) or clip <= 0):
        raise ValidationError("source epoch warmup or clipping differs")
    adapter.reset()
    torch.manual_seed(int(config["seed"]))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(config["seed"]))
    generator = torch.Generator().manual_seed(int(config["seed"]))
    order = torch.randperm(steps, generator=generator).tolist()
    state_device=config.get('optimizer_state_device','model')
    if state_device not in {'model','cpu'}:raise ValidationError('source optimizer state device differs')
    trainable=(p for p in adapter.model.parameters() if p.requires_grad)
    optimizer=(cpu_state_adamw(trainable,lr=float(config['learning_rate'])) if state_device=='cpu' else
        torch.optim.AdamW(trainable,lr=float(config['learning_rate']),weight_decay=0.))
    device = next(adapter.model.parameters()).device
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    scheduler = get_cosine_schedule_with_warmup(optimizer,
        num_warmup_steps=math.ceil(steps * ratio), num_training_steps=steps)
    losses, rates, groups, consumed = [], [], [], []
    tokens_seen = 0
    try:
        adapter.model.train()
        for index in order:
            batch = _torch_batch(collate([examples[index]], int(config["max_sequence_length"])),
                                 next(adapter.model.parameters()).device)
            optimizer.zero_grad(set_to_none=True)
            rates.append(float(optimizer.param_groups[0]["lr"]))
            loss = adapter.model(**batch, use_cache=False).loss
            if not bool(torch.isfinite(loss)):
                raise ValidationError("non-finite source epoch loss")
            loss.backward()
            groups.append(adapter._finite_step(len(losses) + 1))
            norm = torch.nn.utils.clip_grad_norm_(adapter.model.parameters(), float(clip))
            if not bool(torch.isfinite(norm)):
                raise ValidationError("non-finite source epoch gradient norm")
            optimizer.step()
            adapter._finite_adapter(len(losses) + 1)
            scheduler.step()
            losses.append(float(loss.detach().cpu()))
            consumed.append(index)
            tokens_seen += len(examples[index]["input_ids"])
            if adapter.step_observer is not None:
                adapter.step_observer({"completed_steps": len(losses), "source_view_index": index,
                    "training_tokens": tokens_seen, "loss": losses[-1], "learning_rate": rates[-1]})
    except BaseException as exc:
        adapter.reset(clear_observation=False)
        adapter.last_observation = {"task_id": task["task_id"], "status": "failed",
            "training_schedule": "source-one-epoch", "steps": len(losses),
            "training_tokens": tokens_seen, "failure_type": type(exc).__name__}
        raise
    finally:
        optimizer.zero_grad(set_to_none=True)
        del optimizer, scheduler
    adapter.model.eval()
    adapter.last_observation = {"task_id": task["task_id"], "status": "complete",
        "training_schedule": "source-one-epoch", "steps": len(losses),
        "training_tokens": tokens_seen, "last_loss": losses[-1],
        "source_view_count": steps, "consumed_view_indices": consumed,
        "source_sequence_keys": [item["source"] for item in examples],
        "losses_by_step": losses, "learning_rates_by_step": rates,
        "gradient_groups_by_step": groups, "targets": adapter.targets,
        "warmup_steps": math.ceil(steps * ratio), "complete_epoch": sorted(consumed) == list(range(steps)),
        "sample_order_policy": "seeded-torch-randperm-reference",
        "gradient_checkpointing": bool(adapter.model.is_gradient_checkpointing),
        "optimizer_state_device": state_device,
        "trainable_parameter_count": sum(p.numel() for p in adapter.model.parameters() if p.requires_grad),
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device) if device.type == "cuda" else None,
        "peak_cuda_reserved_bytes": torch.cuda.max_memory_reserved(device) if device.type == "cuda" else None}
    return adapter.model


def source_sft_lr(config: dict, step: int) -> float:
    """Megatron-style linear warmup/decay from the effective run_sft_4b recipe."""
    peak = float(config["learning_rate"])
    start = float(config["warmup_initial_learning_rate"])
    minimum = float(config["minimum_learning_rate"])
    horizon, warmup = config["schedule_steps"], config["warmup_steps"]
    if (type(horizon) is not int or type(warmup) is not int or not 0 <= warmup < horizon or
            not all(math.isfinite(x) for x in (peak, start, minimum)) or
            not 0 < minimum <= start <= peak):
        raise ValidationError("source SFT learning-rate schedule differs")
    if step < warmup:
        return start + (peak - start) * step / warmup
    progress = min(1.0, (step - warmup) / (horizon - warmup))
    return peak + (minimum - peak) * progress

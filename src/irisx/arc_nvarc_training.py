"""Explicit compact-grid SFT and task-local LoRA training paths.

Heavy ML libraries load only inside the real backend. The small transition
model is an offline engineering fixture, never an ARC solver measurement.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Iterable, Mapping, Sequence

from .arc_nvarc_representation import GridTokenizer, PAD, validate_compact_model
from .arc_nvarc_data import seeded_transform, transform_task
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


def supervised_sequences(tasks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    tokenizer = GridTokenizer()
    sequences = []
    for task in tasks:
        tokens: list[int] = []
        labels: list[int] = []
        for pair in task["train"] + task.get("labelled_test", []):
            pair_tokens, pair_labels = tokenizer.encode_pair(pair["input"], pair["output"])
            tokens.extend(pair_tokens)
            labels.extend(pair_labels)
        if not tokens:
            raise ValidationError("SFT record has no labelled grid pair")
        sequences.append({"source": task["task_id"], "input_ids": tokens, "labels": labels})
    return sequences


class FrozenSequenceStore:
    """Verified random-access view over deterministic JSONL shards."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest = json.loads((root / "manifest.json").read_bytes())
        if self.manifest.get("format") != "irisx/nvarc-data-freeze":
            raise ValidationError("not an NVARC frozen data manifest")
        self.data_digest = digest_value(self.manifest)
        self.index: list[tuple[Path, int]] = []
        for shard in self.manifest["shards"]:
            path = root / shard["path"]
            if path.parent != root or not path.is_file():
                raise ValidationError("frozen shard path differs")
            sha = hashlib.sha256()
            offset = 0
            local_count = 0
            with path.open("rb") as stream:
                for line in stream:
                    sha.update(line)
                    self.index.append((path, offset))
                    offset += len(line)
                    local_count += 1
            if sha.hexdigest() != shard["sha256"] or local_count != shard["records"]:
                raise ValidationError("frozen shard digest/count differs")
        if len(self.index) != self.manifest["record_count"] or not self.index:
            raise ValidationError("frozen dataset count differs or is empty")

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, index: int) -> dict[str, Any]:
        path, offset = self.index[index]
        with path.open("rb") as stream:
            stream.seek(offset)
            record = json.loads(stream.readline())
        return supervised_sequences([record])[0]


def task_local_sequences(task: Mapping[str, Any], *, seed: int,
                         augmentation_count: int = 16) -> list[dict[str, Any]]:
    """Leave-one-out demonstration targets across reversible task views.

    Test inputs and any test outputs are never supervised here.
    """
    tokenizer = GridTokenizer()
    sequences = []
    if augmentation_count < 1:
        raise ValidationError("task adaptation needs at least one view")
    for view_index in range(augmentation_count):
        spec = seeded_transform(task, seed, view_index)
        transformed = transform_task(task, spec)
        for heldout_index, pair in enumerate(transformed["train"]):
            context = {"task_id": task["task_id"],
                       "train": [item for index, item in enumerate(transformed["train"])
                                 if index != heldout_index],
                       "test": [{"input": pair["input"]}]}
            prefix = tokenizer.encode_query(context, 0)
            answer = tokenizer.encode_grid(pair["output"]) + [tokenizer.eos_token_id]
            sequences.append({"source": f"{task['task_id']}:view{view_index}:loo{heldout_index}",
                              "input_ids": prefix + answer,
                              "labels": [-100] * len(prefix) + answer})
    return sequences


def collate(sequences: list[Mapping[str, Any]], max_length: int) -> dict[str, list[list[int]]]:
    if not sequences or max_length < 2:
        raise ValidationError("empty or invalid SFT batch")
    length = max(len(item["input_ids"]) for item in sequences)
    if length > max_length:
        raise ValidationError("sample exceeds training sequence bound")
    data = {"input_ids": [], "labels": [], "attention_mask": []}
    for item in sequences:
        tokens, labels = item["input_ids"], item["labels"]
        if len(tokens) != len(labels) or not any(value >= 0 for value in labels):
            raise ValidationError("invalid label mask")
        padding = length - len(tokens)
        data["input_ids"].append(tokens + [PAD] * padding)
        data["labels"].append(labels + [-100] * padding)
        data["attention_mask"].append([1] * len(tokens) + [0] * padding)
    return data


class TinyTransitionModel:
    """Pure-Python causal transition model for gradient/checkpoint tests."""

    def __init__(self, seed: int = 0, vocab_size: int = 16) -> None:
        rng = random.Random(seed)
        self.rows = [[rng.uniform(-0.01, 0.01) for _ in range(vocab_size)]
                     for _ in range(vocab_size)]
        self.vocab_size = vocab_size

    def train_step(self, batch: Mapping[str, list[list[int]]], *, lr: float = 0.1,
                   trainable_rows: set[int] | None = None) -> float:
        gradient = [[0.0] * self.vocab_size for _ in range(self.vocab_size)]
        loss = 0.0
        count = 0
        for tokens, labels, mask in zip(batch["input_ids"], batch["labels"], batch["attention_mask"]):
            for position in range(1, len(tokens)):
                target = labels[position]
                if not mask[position] or target == -100:
                    continue
                source = tokens[position - 1]
                logits = self.rows[source]
                peak = max(logits)
                exponentials = [math.exp(value - peak) for value in logits]
                denominator = sum(exponentials)
                probabilities = [value / denominator for value in exponentials]
                loss -= math.log(probabilities[target])
                for index, probability in enumerate(probabilities):
                    gradient[source][index] += probability - (index == target)
                count += 1
        if count == 0:
            raise ValidationError("batch has no supervised next tokens")
        for row in range(self.vocab_size):
            if trainable_rows is None or row in trainable_rows:
                for col in range(self.vocab_size):
                    self.rows[row][col] -= lr * gradient[row][col] / count
        return loss / count

    def predict(self, prefix: list[int], max_tokens: int) -> list[int]:
        result = []
        last = prefix[-1]
        for _ in range(max_tokens):
            last = max(range(self.vocab_size), key=lambda index: (self.rows[last][index], -index))
            result.append(last)
            if last == GridTokenizer.eos_token_id:
                break
        return result


def tiny_train(sequences: list[Mapping[str, Any]], output: Path, *, seed: int,
               steps: int, max_length: int = 2048, resume: bool = False) -> dict[str, Any]:
    """Deterministic tiny training with cursor, RNG and optimizer-equivalent state."""
    if steps < 1 or not sequences:
        raise ValidationError("tiny training needs steps and examples")
    identity = digest_value(sequences)
    state_path = output / "tiny-training.json"
    if resume:
        state = json.loads(state_path.read_bytes())
        if state["data_digest"] != identity or state["seed"] != seed:
            raise ValidationError("tiny checkpoint identity differs")
        model = TinyTransitionModel(seed)
        model.rows = state["rows"]
        cursor = state["cursor"]
        completed = state["steps"]
    else:
        if state_path.exists():
            raise ValidationError("existing tiny checkpoint requires resume")
        model, cursor, completed = TinyTransitionModel(seed), 0, 0
    losses = []
    for _ in range(steps):
        batch = collate([sequences[cursor % len(sequences)]], max_length)
        losses.append(model.train_step(batch))
        cursor += 1
        completed += 1
    state = {"format": "irisx/nvarc-tiny-training", "seed": seed,
             "data_digest": identity, "rows": model.rows, "cursor": cursor,
             "steps": completed, "optimizer": {"kind": "sgd", "learning_rate": 0.1},
             "scheduler": {"kind": "constant"}, "rng": {"seed": seed, "cursor": cursor},
             "last_loss": losses[-1]}
    output.mkdir(parents=True, exist_ok=True)
    state_path.write_bytes(canonical_bytes(state, newline=True))
    return state


def _torch_batch(batch: Mapping[str, list[list[int]]], device: Any) -> dict[str, Any]:
    import torch
    return {key: torch.tensor(value, dtype=torch.long, device=device) for key, value in batch.items()}


def inspect_lora_targets(model: Any) -> list[str]:
    """Require projection coverage in both attention and DeltaNet layers."""
    import torch

    linear = [name for name, module in model.named_modules()
              if isinstance(module, torch.nn.Linear) and "model.language_model.layers." in name]
    attention = [name for name in linear if ".self_attn." in name and
                 name.endswith(("q_proj", "k_proj", "v_proj", "o_proj"))]
    delta = [name for name in linear if ".linear_attn." in name]
    mlp = [name for name in linear if ".mlp." in name and
           name.endswith(("gate_proj", "up_proj", "down_proj"))]
    embedding = [name for name, module in model.named_modules()
                 if isinstance(module, torch.nn.Embedding) and name == "model.language_model.embed_tokens"]
    head = [name for name, module in model.named_modules()
            if isinstance(module, torch.nn.Linear) and name == "lm_head"]
    if not all((attention, delta, mlp, embedding, head)):
        raise ValidationError("Qwen3.5 attention/DeltaNet/MLP/embedding/head LoRA coverage unverified")
    return sorted(set(attention + delta + mlp + embedding + head))


def load_compact_model(checkpoint: Path, *, dtype: str = "bfloat16") -> Any:
    import torch
    from transformers import AutoModelForMultimodalLM

    if not (checkpoint / "grid-vocab.json").is_file():
        raise ValidationError("compact checkpoint lacks grid vocabulary binding")
    torch_dtype = {"bfloat16": torch.bfloat16, "float32": torch.float32}[dtype]
    model = AutoModelForMultimodalLM.from_pretrained(
        checkpoint, local_files_only=True, dtype=torch_dtype, attn_implementation="sdpa")
    material_path = checkpoint / "material-manifest.json"
    tied = json.loads(material_path.read_bytes())["tied_embeddings"] if material_path.is_file() else None
    validate_compact_model(model, tied=tied)
    return model


def train_torch_sft(model: Any, sequences: Sequence[Mapping[str, Any]], output: Path,
                    config: Mapping[str, Any], *, model_identity_digest: str,
                    resume: bool = False) -> dict[str, Any]:
    """Real gradient path with exact optimizer/scheduler/RNG/data-cursor restore.

    Single-process full SFT is deliberate; distributed sharding requires a
    separately tested launcher. Packing is rejected until DeltaNet masking is
    verified on the pinned architecture.
    """
    import torch

    if config.get("packing", False) or config.get("mode") != "full-sft":
        raise ValidationError("only unpacked full-SFT is supported by this entry")
    if not sequences:
        raise ValidationError("SFT dataset is empty")
    if not model_identity_digest.startswith("sha256:"):
        raise ValidationError("immutable compact model identity required")
    data_digest = sequences.data_digest if isinstance(sequences, FrozenSequenceStore) else digest_value(sequences)
    identity = digest_value({"config": config, "data_digest": data_digest,
                             "model_identity_digest": model_identity_digest})
    device = torch.device(config.get("device", "cpu"))
    model.to(device).train()
    if config.get("gradient_checkpointing", False):
        model.gradient_checkpointing_enable()
        if hasattr(model.config, "use_cache"):
            model.config.use_cache = False
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(config["learning_rate"]),
                                  weight_decay=float(config.get("weight_decay", 0.0)))
    total_steps = int(config["max_steps"])
    token_limit = int(config["maximum_training_tokens"])
    if token_limit < 1:
        raise ValidationError("training token limit is required")
    warmup = int(config.get("warmup_steps", 0))
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda step: min(1.0, (step + 1) / max(1, warmup)) *
        max(0.0, (total_steps - step) / max(1, total_steps - warmup)))
    checkpoint = output / "training-state.pt"
    cursor = step = tokens_seen = 0
    if resume:
        state = torch.load(checkpoint, map_location="cpu", weights_only=False)
        if state["identity_digest"] != identity:
            raise ValidationError("training checkpoint identity differs")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        torch.set_rng_state(state["cpu_rng"])
        if torch.cuda.is_available() and state["cuda_rng"] is not None:
            torch.cuda.set_rng_state_all(state["cuda_rng"])
        cursor, step, tokens_seen = state["cursor"], state["step"], state["tokens_seen"]
        if step >= total_steps or tokens_seen >= token_limit:
            raise ValidationError("terminal training checkpoint cannot be resumed")
    elif checkpoint.exists():
        raise ValidationError("existing training state requires resume")
    else:
        torch.manual_seed(int(config["seed"]))
    accumulation = int(config.get("gradient_accumulation", 1))
    if accumulation < 1 or total_steps < 1:
        raise ValidationError("invalid training limits")
    optimizer.zero_grad(set_to_none=True)
    last_loss = None
    stop_reason = "maximum_steps"
    stride = max(1, int(config["seed"]) % len(sequences))
    while math.gcd(stride, len(sequences)) != 1:
        stride += 1
    while step < total_steps:
        microbatches = []
        for microstep in range(accumulation):
            # Coprime stride gives an O(1) deterministic permutation and
            # exact cursor restoration for large corpora.
            item = sequences[(int(config["seed"]) + (cursor + microstep) * stride) % len(sequences)]
            batch = _torch_batch(collate([item], int(config["max_sequence_length"])), device)
            sample_tokens = int(batch["attention_mask"].sum().item())
            microbatches.append((batch, sample_tokens))
        if tokens_seen + sum(count for _, count in microbatches) > token_limit:
            stop_reason = "maximum_training_tokens"
            optimizer.zero_grad(set_to_none=True)
            break
        for batch, sample_tokens in microbatches:
            output_value = model(**batch)
            loss = output_value.loss
            if not torch.isfinite(loss):
                raise ValidationError("non-finite SFT loss")
            (loss / accumulation).backward()
            last_loss = float(loss.detach().cpu())
            cursor += 1
            tokens_seen += sample_tokens
        if step == 0 and not any(parameter.grad is not None and
                                 bool(torch.any(parameter.grad != 0)) for parameter in model.parameters()
                                 if parameter.requires_grad):
            raise ValidationError("no trainable parameter received a nonzero gradient")
        torch.nn.utils.clip_grad_norm_(model.parameters(), float(config.get("clip_grad_norm", 1.0)))
        optimizer.step()
        scheduler.step()
        optimizer.zero_grad(set_to_none=True)
        step += 1
        if step % int(config.get("checkpoint_every", 1)) == 0 or step == total_steps:
            output.mkdir(parents=True, exist_ok=True)
            temporary = checkpoint.with_suffix(".tmp")
            torch.save({"identity_digest": identity, "model": model.state_dict(),
                        "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                        "cpu_rng": torch.get_rng_state(),
                        "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
                        "cursor": cursor, "step": step, "tokens_seen": tokens_seen,
                        "last_loss": last_loss}, temporary)
            temporary.replace(checkpoint)
    if stop_reason == "maximum_training_tokens":
        output.mkdir(parents=True, exist_ok=True)
        temporary = checkpoint.with_suffix(".tmp")
        torch.save({"identity_digest": identity, "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                    "cpu_rng": torch.get_rng_state(),
                    "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
                    "cursor": cursor, "step": step, "tokens_seen": tokens_seen,
                    "last_loss": last_loss}, temporary)
        temporary.replace(checkpoint)
    return {"artifact_kind": "training-state", "identity_digest": identity,
            "steps": step, "cursor": cursor, "tokens_seen": tokens_seen,
            "last_loss": last_loss, "stop_reason": stop_reason,
            "trainable_parameter_count": sum(parameter.numel() for parameter in model.parameters()
                                             if parameter.requires_grad)}


class TaskLocalAdapter:
    """Keep one loaded base model while restoring a fresh LoRA for every task."""

    def __init__(self, base_model: Any, config: Mapping[str, Any]) -> None:
        import torch
        from peft import LoraConfig, get_peft_model, get_peft_model_state_dict

        self.config = dict(config)
        self.targets = inspect_lora_targets(base_model)
        torch.manual_seed(int(config["seed"]))
        self.model = get_peft_model(base_model, LoraConfig(
            r=int(config["rank"]), lora_alpha=int(config["alpha"]),
            lora_dropout=float(config.get("dropout", 0.0)), target_modules=self.targets,
            bias="none", task_type="CAUSAL_LM", use_rslora=bool(config.get("use_rslora", True))))
        self.initial = {key: value.detach().cpu().clone() for key, value in
                        get_peft_model_state_dict(self.model).items()}
        self.last_observation: dict[str, Any] | None = None

    def reset(self, *, clear_observation: bool = True) -> None:
        """Discard task gradients and adapter deltas after success or failure."""
        from peft import set_peft_model_state_dict

        self.model.zero_grad(set_to_none=True)
        set_peft_model_state_dict(self.model, copy.deepcopy(self.initial))
        self.model.eval()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if clear_observation:
            self.last_observation = None

    def adapt(self, task: Mapping[str, Any]) -> Any:
        import torch
        config = self.config
        self.reset()
        torch.manual_seed(int(config["seed"]))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(config["seed"]))
            torch.cuda.empty_cache()
        optimizer = None
        last_loss = None
        tokens_seen = 0
        try:
            optimizer = torch.optim.AdamW((parameter for parameter in self.model.parameters() if parameter.requires_grad),
                                          lr=float(config["learning_rate"]))
            examples = task_local_sequences(task, seed=int(config["seed"]),
                                            augmentation_count=int(config.get("augmentation_count", 16)))
            self.model.train()
            for step in range(int(config["steps"])):
                batch = _torch_batch(collate([examples[step % len(examples)]], int(config["max_sequence_length"])),
                                     next(self.model.parameters()).device)
                optimizer.zero_grad(set_to_none=True)
                loss = self.model(**batch).loss
                if not torch.isfinite(loss):
                    raise ValidationError("non-finite task adaptation loss")
                loss.backward()
                optimizer.step()
                last_loss = float(loss.detach().cpu())
                tokens_seen += int(batch["attention_mask"].sum().item())
        except BaseException:
            self.reset()
            raise
        finally:
            del optimizer
        self.model.eval()
        self.last_observation = {"task_id": task["task_id"], "steps": int(config["steps"]),
                                 "training_tokens": tokens_seen,
                                 "last_loss": last_loss, "targets": self.targets}
        return self.model

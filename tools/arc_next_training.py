"""Default-inert, bounded manual G4 demonstration-only LoRA calibration.

This is a calibration backend, not a full SFT/RL launcher or an ARC score claim.
The ordinary import/data/preflight/test path is stdlib-only and offline. Explicit
manual enablement runs ONE chosen local model under a separate process watchdog.
No cloud provisioning, credential access, uploads, downloads, or retry loops exist.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import random
import resource
import signal
import shutil
import time
from typing import Any, Callable

from tools.arc_next_models import (ContractError, canonical, digest, file_sha256, get_spec,
                                   load_candidate, lora_target_modules, observe_g4_hardware,
                                   require, validate_material, write_json)

ARC_REVISION = "f3283f727488ad98fe575ea6a5ac981e4a188e49"
PROFILES = {"smoke2": 2, "pilot16": 16, "pilot128": 128}


@dataclass(frozen=True)
class RunBudget:
    max_optimizer_steps: int = 2
    max_input_tokens: int = 16384
    max_supervised_tokens: int = 8192
    max_sequence_tokens: int = 4096
    max_wall_seconds: float = 1800.0
    max_eval_input_tokens: int = 32768
    max_eval_rows: int = 4


@dataclass(frozen=True)
class CalibrationConfig:
    model_path: str = ""
    training_tasks_path: str = ""
    training_manifest_path: str = ""
    output_dir: str = ""
    environment_lock_path: str = ""
    model_key: str = "granite-4.2-8b"
    model_manifest_path: str | None = None
    enabled: bool = False
    profile: str = "smoke2"
    enable_pilot: bool = False
    allow_experimental_qwen: bool = False
    budget: RunBudget = field(default_factory=RunBudget)
    approved_max_cost_usd: float | None = None
    estimated_hourly_cost_usd: float | None = None
    seed: int = 0
    learning_rate: float = 0.0002
    lora_rank: int = 16
    lora_alpha: int = 32
    max_grad_norm: float = 1.0
    train_augmentations: tuple[str, ...] = ("identity",)


def _positive_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate_budget(budget: RunBudget) -> None:
    for name in ("max_optimizer_steps", "max_input_tokens", "max_supervised_tokens", "max_sequence_tokens", "max_eval_input_tokens", "max_eval_rows"):
        require(type(getattr(budget, name)) is int and getattr(budget, name) > 0,
                name + " must be a finite positive integer")
    require(_positive_number(budget.max_wall_seconds), "finite positive wall budget required")
    require(budget.max_supervised_tokens <= budget.max_input_tokens and
            budget.max_sequence_tokens <= budget.max_input_tokens, "inconsistent token budgets")


def preflight(config: CalibrationConfig, *, verify_material: bool = False) -> dict[str, Any]:
    """Show the bounded proposed operation without touching Torch/CUDA or running it."""
    require(all(type(value) is bool for value in (config.enabled, config.enable_pilot,
                                                  config.allow_experimental_qwen)),
            "enabled, enable_pilot, and allow_experimental_qwen must be exact booleans")
    spec = get_spec(config.model_key)
    validate_budget(config.budget)
    require(config.profile in PROFILES and config.budget.max_optimizer_steps == PROFILES[config.profile],
            "profile must match its exact 2, 16, or 128 optimizer-step ceiling")
    require(config.profile == "smoke2" or config.enable_pilot,
            "16/128-step pilot requires separate explicit enable_pilot=True")
    require(not spec.experimental or config.allow_experimental_qwen,
            "Qwen hybrid route requires explicit experimental opt-in")
    require(type(config.seed) is int and 0 <= config.seed < 2**32, "invalid deterministic seed")
    require(_positive_number(config.learning_rate) and config.learning_rate <= 0.01,
            "bounded positive learning rate required")
    require(type(config.lora_rank) is int and 1 <= config.lora_rank <= 64 and
            type(config.lora_alpha) is int and 1 <= config.lora_alpha <= 128 and
            _positive_number(config.max_grad_norm), "invalid LoRA/gradient configuration")
    require(bool(config.train_augmentations) and set(config.train_augmentations) <=
            {"identity", "rotate90", "rotate180", "rotate270"}, "unsupported augmentation")
    cost = None
    if config.estimated_hourly_cost_usd is not None:
        require(_positive_number(config.estimated_hourly_cost_usd), "explicit positive hourly cost estimate required")
        cost = config.estimated_hourly_cost_usd * config.budget.max_wall_seconds / 3600.0
    if config.enabled:
        require(all((config.model_path, config.training_tasks_path, config.training_manifest_path,
                     config.output_dir, config.environment_lock_path)), "explicit local input/output/lock paths required")
        require(_positive_number(config.approved_max_cost_usd) and cost is not None and
                cost <= config.approved_max_cost_usd, "explicit sufficient owner-approved calibration cost cap required")
        output = Path(config.output_dir).resolve()
        require(not output.exists(), "new immutable output directory required; never resume or overwrite a prior run")
        require(not output.is_relative_to(Path(config.model_path).resolve()), "output cannot be inside base material")
    result = {"format": "irisx/arc-next-calibration-preflight-v1", "enabled": config.enabled,
              "model_id": spec.repository + "@" + spec.revision, "selected_model_count": 1,
              "profile": config.profile, "budget": asdict(config.budget),
              "approved_max_cost_usd": config.approved_max_cost_usd,
              "estimated_hourly_cost_usd": config.estimated_hourly_cost_usd,
              "maximum_calibration_compute_estimate_usd": cost,
              "billing_caveat": "watchdog bounds this process only; an existing VM can keep billing until its owner stops it",
              "training_objective": "leave-one-demonstration-out supervised completion LoRA",
              "trajectory_sft_enabled": False, "rl_enabled": False,
              "dev_evaluation": "same held-out task-group demonstration rows before/after; NLL only, no ARC accuracy",
              "maximum_forward_input_tokens": config.budget.max_input_tokens + config.budget.max_eval_input_tokens,
              "native_vocabulary_policy": "retain all native input/output rows; never reuse compressed 16-token NVARC",
              "gpu_runtime_verified": False, "provisions_or_starts_compute": False,
              "network_access": False, "automatic_uploads": False}
    if verify_material:
        result["material"] = validate_material(config.model_path, config.model_key, config.model_manifest_path)
        result["training_material"] = load_training_material(config.training_tasks_path,
                                                            config.training_manifest_path)[1]
    return result


def _grid(value: Any) -> list[list[int]]:
    require(isinstance(value, list) and 1 <= len(value) <= 30, "grid height must be 1..30")
    width = len(value[0]) if isinstance(value[0], list) else 0
    require(1 <= width <= 30 and all(isinstance(row, list) and len(row) == width and
            all(type(cell) is int and 0 <= cell <= 9 for cell in row) for row in value),
            "rectangular ARC grids with integer colors 0..9 required")
    return value


def _validate_demo_tasks(tasks: Any) -> None:
    require(isinstance(tasks, dict) and bool(tasks), "nonempty demonstration-only training map required")
    for task_id, task in tasks.items():
        require(isinstance(task_id, str) and len(task_id) == 8 and
                all(c in "0123456789abcdef" for c in task_id), "official 8-hex training task IDs required")
        require(isinstance(task, dict) and set(task) == {"train"},
                "training material may contain demonstrations only: test/eval/solutions are forbidden")
        require(isinstance(task["train"], list) and 2 <= len(task["train"]) <= 100,
                "LODO requires at least two demonstration pairs")
        for pair in task["train"]:
            require(isinstance(pair, dict) and set(pair) == {"input", "output"}, "exact demonstration pair required")
            _grid(pair["input"])
            _grid(pair["output"])


def task_group_split(task_ids: list[str], *, seed: int = 0,
                     dev_fraction: float = 0.2) -> dict[str, list[str]]:
    """Assign whole task groups before any demonstration/augmentation expansion."""
    require(len(task_ids) == len(set(task_ids)) and len(task_ids) >= 2,
            "at least two unique task groups required for train/dev isolation")
    require(type(dev_fraction) in (float, int) and 0 < dev_fraction < 1, "dev fraction must be in (0,1)")
    ranked = sorted(task_ids, key=lambda task_id: (digest(["arc-next-task-split-v1", seed, task_id]), task_id))
    dev_count = min(len(ranked) - 1, max(1, round(len(ranked) * dev_fraction)))
    return {"train": sorted(ranked[dev_count:]), "dev": sorted(ranked[:dev_count])}


def write_training_manifest(training_tasks_path: str | Path, allowed_task_ids: list[str],
                            manifest_path: str | Path, *, source_revision: str = ARC_REVISION,
                            train_task_ids: list[str] | None = None,
                            dev_task_ids: list[str] | None = None, seed: int = 0) -> dict[str, Any]:
    """Bind an already sanitized, allowlisted official training-demonstration file.

    This helper does NOT sanitize raw challenge/solution files and does not read
    any second source. Source preparation must choose official training IDs first.
    """
    path = Path(training_tasks_path)
    require(source_revision == ARC_REVISION, "only the pinned official ARC training source is allowed")
    require(not any(word in path.name.lower() for word in ("solution", "evaluation", "test_challenge")),
            "answer/evaluation source paths are forbidden")
    tasks = json.loads(path.read_text())
    _validate_demo_tasks(tasks)
    require(len(allowed_task_ids) == len(set(allowed_task_ids)) and set(tasks) == set(allowed_task_ids),
            "material must exactly equal explicit official training allowlist")
    if train_task_ids is None and dev_task_ids is None:
        split = task_group_split(allowed_task_ids, seed=seed)
    else:
        require(train_task_ids is not None and dev_task_ids is not None, "both task partitions are required")
        split = {"train": sorted(train_task_ids), "dev": sorted(dev_task_ids)}
    require(split["train"] and split["dev"] and not set(split["train"]) & set(split["dev"]) and
            set(split["train"]) | set(split["dev"]) == set(tasks) and
            len(split["train"]) + len(split["dev"]) == len(tasks), "disjoint exact whole-task split required")
    result = {"format": "irisx/arc-next-training-material-v1", "source_repository": "arcprize/ARC-AGI-2",
              "source_revision": source_revision, "source_file_sha256": file_sha256(path),
              "task_sha256": {key: digest(tasks[key]) for key in sorted(tasks)},
              "task_partition": split, "split_seed": seed,
              "scope": "official-training-demonstrations-only", "test_outputs_present": False}
    write_json(Path(manifest_path), result)
    return result


def load_training_material(training_tasks_path: str | Path,
                           manifest_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(training_tasks_path)
    require(not any(word in path.name.lower() for word in ("solution", "evaluation", "test_challenge")),
            "answer/evaluation source paths are forbidden")
    manifest = json.loads(Path(manifest_path).read_text())
    require(manifest.get("format") == "irisx/arc-next-training-material-v1" and
            manifest.get("source_repository") == "arcprize/ARC-AGI-2" and
            manifest.get("source_revision") == ARC_REVISION and
            manifest.get("scope") == "official-training-demonstrations-only" and
            manifest.get("test_outputs_present") is False,
            "reviewed pinned demonstration-only training manifest required")
    require(file_sha256(path) == manifest.get("source_file_sha256"), "training file hash changed")
    tasks = json.loads(path.read_text())
    _validate_demo_tasks(tasks)
    require({key: digest(value) for key, value in tasks.items()} == manifest.get("task_sha256"),
            "exact allowlisted demonstration hashes required")
    split = manifest.get("task_partition", {})
    require(set(split) == {"train", "dev"} and split["train"] and split["dev"] and
            not set(split["train"]) & set(split["dev"]) and
            set(split["train"]) | set(split["dev"]) == set(tasks) and
            len(split["train"]) + len(split["dev"]) == len(tasks), "invalid grouped task split")
    return tasks, manifest


def _transform(grid: list[list[int]], transform: str) -> list[list[int]]:
    result = [row[:] for row in grid]
    turns = {"identity": 0, "rotate90": 1, "rotate180": 2, "rotate270": 3}[transform]
    for _ in range(turns):
        result = [list(row) for row in zip(*result[::-1])]
    return result


def build_training_rows(tasks: dict[str, Any], manifest: dict[str, Any], *,
                        train_augmentations: tuple[str, ...] = ("identity",)) -> dict[str, list[dict[str, Any]]]:
    """LODO on train demonstrations only, with split-before-augmentation identity."""
    _validate_demo_tasks(tasks)
    require(bool(train_augmentations) and set(train_augmentations) <=
            {"identity", "rotate90", "rotate180", "rotate270"}, "unsupported augmentation")
    split = manifest["task_partition"]
    require(not set(split["train"]) & set(split["dev"]) and
            set(split["train"]) | set(split["dev"]) == set(tasks), "task partitions must be exhaustive/disjoint")
    result = {"train": [], "dev": []}
    for partition in ("train", "dev"):
        for task_id in sorted(split[partition]):
            task = tasks[task_id]
            for transform in (train_augmentations if partition == "train" else ("identity",)):
                demos = [{key: _transform(pair[key], transform) for key in ("input", "output")}
                         for pair in task["train"]]
                for held_out in range(len(demos)):
                    visible = [pair for i, pair in enumerate(demos) if i != held_out]
                    query = demos[held_out]["input"]
                    target = demos[held_out]["output"]
                    # Seed's native template forbids a separate system message.
                    user = ("Infer the grid transformation from the demonstrations. Return only the complete "
                            "output grid as a JSON array of integer rows, without explanation.\n"
                            "Demonstrations:\n" + canonical(visible).decode() +
                            "\nQuery input:\n" + canonical(query).decode())
                    row = {"task_id": task_id, "partition": partition,
                           "held_out_demonstration": held_out, "augmentation": transform,
                           "messages": [{"role": "user", "content": user}],
                           "completion": canonical(target).decode(),
                           "visible_demonstration_indices": [i for i in range(len(demos)) if i != held_out]}
                    row["row_id"] = digest(row)
                    result[partition].append(row)
    return result


def tokenize_rows(rows: list[dict[str, Any]], tokenizer: Any,
                  max_sequence_tokens: int, *, model_key: str = "granite-4.2-8b") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Native-template prompt/completion masking; never truncate a grid or row."""
    accepted, excluded = [], []
    for row in rows:
        kwargs = {"tokenize": False, "enable_thinking": False}
        prompt_text = tokenizer.apply_chat_template(row["messages"], add_generation_prompt=True, **kwargs)
        completion, completion_policy = row["completion"], "native-template"
        full_text = tokenizer.apply_chat_template(
            row["messages"] + [{"role": "assistant", "content": completion}],
            add_generation_prompt=False, **kwargs)
        require(full_text.startswith(prompt_text), "native rendered completion does not extend generation prompt")
        prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
        ids = tokenizer.encode(full_text, add_special_tokens=False)
        require(ids[:len(prompt_ids)] == prompt_ids and len(ids) > len(prompt_ids) > 0,
                "template boundary token merge/empty completion; cannot safely mask assistant-only labels")
        require(all(type(i) is int and i >= 0 for i in ids), "invalid tokenizer output")
        if len(ids) > max_sequence_tokens:
            excluded.append({"row_id": row["row_id"], "reason": "whole-row-exceeds-sequence-budget",
                             "input_tokens": len(ids)})
            continue
        labels = [-100] * len(prompt_ids) + ids[len(prompt_ids):]
        item = {key: row[key] for key in ("row_id", "task_id", "partition", "held_out_demonstration", "augmentation")}
        item.update(input_ids=ids, labels=labels, input_tokens=len(ids),
                    supervised_tokens=len(ids) - len(prompt_ids), prompt_tokens=len(prompt_ids),
                    rendered_template_sha256=hashlib.sha256(full_text.encode()).hexdigest(),
                    completion_rendering_policy=completion_policy)
        accepted.append(item)
    return accepted, excluded


class BudgetStop(RuntimeError):
    pass


class BudgetLedger:
    """Reserve work before executing it; count returned updates separately."""
    def __init__(self, budget: RunBudget, *, clock: Callable[[], float] = time.monotonic,
                 start_time: float | None = None):
        validate_budget(budget)
        self.budget, self.clock = budget, clock
        self.start_time = clock() if start_time is None else start_time
        self.reserved_input_tokens = self.reserved_supervised_tokens = self.reserved_steps = 0
        self.actual_updates = 0

    def reserve(self, row: dict[str, Any]) -> None:
        if self.clock() - self.start_time >= self.budget.max_wall_seconds:
            raise BudgetStop("wall-clock-budget")
        if self.reserved_steps >= self.budget.max_optimizer_steps:
            raise BudgetStop("optimizer-step-budget")
        if self.reserved_input_tokens + row["input_tokens"] > self.budget.max_input_tokens:
            raise BudgetStop("input-token-budget")
        if self.reserved_supervised_tokens + row["supervised_tokens"] > self.budget.max_supervised_tokens:
            raise BudgetStop("supervised-token-budget")
        require(row["input_tokens"] <= self.budget.max_sequence_tokens, "whole row exceeds sequence budget")
        self.reserved_steps += 1
        self.reserved_input_tokens += row["input_tokens"]
        self.reserved_supervised_tokens += row["supervised_tokens"]

    def snapshot(self) -> dict[str, Any]:
        return {"reserved_optimizer_steps": self.reserved_steps, "actual_optimizer_updates": self.actual_updates,
                "reserved_input_tokens": self.reserved_input_tokens,
                "reserved_supervised_tokens": self.reserved_supervised_tokens,
                "elapsed_seconds": max(0.0, self.clock() - self.start_time), "limits": asdict(self.budget)}


def execute_training_steps(backend: Any, rows: list[dict[str, Any]], budget: RunBudget, *,
                           seed: int = 0, clock: Callable[[], float] = time.monotonic,
                           start_time: float | None = None,
                           on_event: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Backend-neutral bounded loop, CPU-tested with literal fake updates."""
    require(rows and all(row["partition"] == "train" for row in rows),
            "only training partition rows can enter an optimizer")
    ledger = BudgetLedger(budget, clock=clock, start_time=start_time)
    rng, steps = random.Random(seed), []
    order = list(range(len(rows)))
    rng.shuffle(order)
    stop_reason = "optimizer-step-budget"
    for step in range(budget.max_optimizer_steps):
        if step and step % len(order) == 0:
            rng.shuffle(order)
        row = rows[order[step % len(order)]]
        try:
            ledger.reserve(row)
        except BudgetStop as error:
            stop_reason = str(error)
            break
        event = {"event": "step-reserved", "step": step + 1, "row_id": row["row_id"],
                 "task_id": row["task_id"], "input_tokens": row["input_tokens"],
                 "supervised_tokens": row["supervised_tokens"], "budget": ledger.snapshot()}
        if on_event:
            on_event(event)
        observation = backend.step(row)
        require(_positive_number(observation.get("seconds")) or observation.get("seconds") == 0,
                "nonnegative finite observed step timing required")
        require(type(observation.get("loss")) in (int, float) and math.isfinite(observation["loss"]),
                "finite observed loss required")
        require(observation.get("finite_gradients") is True and
                type(observation.get("optimizer_updates")) is int and observation.get("optimizer_updates") == 1 and
                observation.get("adam_step") == ledger.actual_updates + 1 and
                observation.get("changed_adapter_tensors", 0) > 0, "actual finite changed adapter update required")
        ledger.actual_updates += 1
        completed = dict(event, event="step-completed", observation=observation, budget=ledger.snapshot())
        steps.append(completed)
        if on_event:
            on_event(completed)
    return {"stop_reason": stop_reason, "budget": ledger.snapshot(), "steps": steps,
            "completed_profile": ledger.actual_updates == budget.max_optimizer_steps}



def select_evaluation_rows(rows: list[dict[str, Any]], budget: RunBudget) -> list[dict[str, Any]]:
    """Fix whole dev rows once, budgeting BOTH pre/post forwards before either."""
    require(rows and all(row["partition"] == "dev" for row in rows), "held-out task-group dev rows required")
    selected, used = [], 0
    for row in sorted(rows, key=lambda item: item["row_id"]):
        if len(selected) >= budget.max_eval_rows:
            break
        if used + 2 * row["input_tokens"] <= budget.max_eval_input_tokens:
            selected.append(row)
            used += 2 * row["input_tokens"]
    require(selected, "no complete dev row fits both bounded evaluation passes")
    return selected


def evaluate_rows(backend: Any, rows: list[dict[str, Any]], budget: RunBudget, *,
                  phase: str, clock: Callable[[], float] = time.monotonic,
                  start_time: float, prior_input_tokens: int = 0,
                  on_event: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    require(phase in {"before", "after"} and rows and len(rows) <= budget.max_eval_rows and
            all(row["partition"] == "dev" for row in rows), "bounded held-out dev evaluation required")
    used, weighted_loss, labels, observations = prior_input_tokens, 0.0, 0, []
    for row in rows:
        require(clock() - start_time < budget.max_wall_seconds, "wall budget exhausted before dev evaluation")
        require(used + row["input_tokens"] <= budget.max_eval_input_tokens, "dev evaluation token budget exhausted")
        used += row["input_tokens"]
        if on_event:
            on_event({"event": "dev-forward-reserved", "phase": phase, "row_id": row["row_id"],
                      "reserved_eval_input_tokens": used})
        value = backend.evaluate(row)
        require(type(value.get("loss")) in (int, float) and math.isfinite(value["loss"]),
                "finite observed held-out dev NLL required")
        labels += row["supervised_tokens"]
        weighted_loss += value["loss"] * row["supervised_tokens"]
        observation = {"row_id": row["row_id"], "task_id": row["task_id"],
                       "input_tokens": row["input_tokens"], "supervised_tokens": row["supervised_tokens"],
                       "loss": value["loss"], "seconds": value["seconds"]}
        observations.append(observation)
        if on_event:
            on_event(dict(observation, event="dev-forward-completed", phase=phase))
    return {"phase": phase, "rows": observations, "supervised_token_weighted_nll": weighted_loss / labels,
            "supervised_tokens": labels, "cumulative_eval_input_tokens": used,
            "optimizer_updates": 0, "arc_accuracy_measured": False}

def _state_fingerprint(state: dict[str, Any], torch: Any) -> dict[str, Any]:
    tensors = {}
    for name, value in sorted(state.items()):
        value = value.detach().cpu().contiguous()
        require(bool(torch.isfinite(value).all()), "nonfinite adapter tensor")
        tensors[name] = {"shape": list(value.shape), "dtype": str(value.dtype), "elements": value.numel(),
                         "sha256": hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}
    return {"sha256": digest(tensors), "tensors": tensors}


class TorchLoRABackend:
    def __init__(self, session: Any, config: CalibrationConfig):
        from peft import LoraConfig, TaskType, get_peft_model, get_peft_model_state_dict
        self.session, self.config, self.torch = session, config, session.torch
        self.get_state = get_peft_model_state_dict
        targets = lora_target_modules(session.model, config.model_key, self.torch)
        session.model.config.use_cache = False
        if hasattr(session.model.config, "text_config"):
            session.model.config.text_config.use_cache = False
        session.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        if hasattr(session.model, "enable_input_require_grads"):
            session.model.enable_input_require_grads()
        self.model = get_peft_model(session.model, LoraConfig(
            task_type=TaskType.CAUSAL_LM, r=config.lora_rank, lora_alpha=config.lora_alpha,
            target_modules=targets, lora_dropout=0.0, bias="none"))
        self.parameters = {name: p for name, p in self.model.named_parameters() if p.requires_grad}
        require(self.parameters and all("lora_" in name for name in self.parameters),
                "only LoRA tensors may be trainable")
        self.baseline = {name: tensor.detach().cpu().clone() for name, tensor in self.get_state(self.model).items()}
        self.initial_fingerprint = _state_fingerprint(self.baseline, self.torch)
        self.optimizer = self.torch.optim.AdamW(list(self.parameters.values()), lr=config.learning_rate,
                                              weight_decay=0.0, foreach=False)
        self.metadata = {"target_modules": targets, "lora_rank": config.lora_rank,
                         "trainable_parameter_count": sum(p.numel() for p in self.parameters.values()),
                         "trainable_tensor_count": len(self.parameters), "gradient_checkpointing": True,
                         "batch_size": 1, "gradient_accumulation_steps": 1,
                         "attention_backend": session.identity["attention_backend_policy"],
                         "base_parameter_updates": False, "initial_adapter_fingerprint": self.initial_fingerprint}

    def step(self, row: dict[str, Any]) -> dict[str, Any]:
        torch = self.torch
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        before = _state_fingerprint(self.get_state(self.model), torch)
        ids = torch.tensor([row["input_ids"]], device="cuda:0", dtype=torch.long)
        labels = torch.tensor([row["labels"]], device="cuda:0", dtype=torch.long)
        attention = torch.ones_like(ids)
        torch.cuda.synchronize()
        started = time.monotonic()
        output = self.model(input_ids=ids, labels=labels, attention_mask=attention, use_cache=False)
        loss = output.loss
        require(bool(torch.isfinite(loss).all()), "nonfinite training loss")
        loss.backward()
        missing = [name for name, p in self.parameters.items() if p.grad is None]
        require(not missing, "missing LoRA gradient groups: " + ",".join(missing[:8]))
        require(all(bool(torch.isfinite(p.grad).all()) for p in self.parameters.values()), "nonfinite LoRA gradient")
        norm = torch.nn.utils.clip_grad_norm_(list(self.parameters.values()), self.config.max_grad_norm,
                                            error_if_nonfinite=True)
        require(math.isfinite(float(norm)), "nonfinite observed gradient norm")
        self.optimizer.step()
        torch.cuda.synchronize()
        after = _state_fingerprint(self.get_state(self.model), torch)
        changed = sum(before["tensors"][name]["sha256"] != entry["sha256"]
                      for name, entry in after["tensors"].items())
        optimizer_steps = {int(float(self.optimizer.state[p]["step"])) for p in self.parameters.values()}
        require(len(optimizer_steps) == 1, "inconsistent actual Adam step counters")
        for state in self.optimizer.state.values():
            require(all(bool(torch.isfinite(state[name]).all()) for name in ("exp_avg", "exp_avg_sq")),
                    "nonfinite Adam moments")
        return {"loss": float(loss.detach()), "seconds": time.monotonic() - started,
                "finite_gradients": True, "gradient_tensor_count": len(self.parameters),
                "gradient_norm_before_clip": float(norm), "optimizer_updates": 1,
                "adam_step": next(iter(optimizer_steps)), "changed_adapter_tensors": changed,
                "adapter_before_sha256": before["sha256"], "adapter_after_sha256": after["sha256"],
                "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved()}

    def evaluate(self, row: dict[str, Any]) -> dict[str, Any]:
        torch = self.torch
        self.model.eval()
        ids = torch.tensor([row["input_ids"]], device="cuda:0", dtype=torch.long)
        labels = torch.tensor([row["labels"]], device="cuda:0", dtype=torch.long)
        torch.cuda.synchronize()
        started = time.monotonic()
        with torch.no_grad():
            loss = self.model(input_ids=ids, labels=labels, attention_mask=torch.ones_like(ids),
                              use_cache=False).loss
        torch.cuda.synchronize()
        require(bool(torch.isfinite(loss).all()), "nonfinite held-out dev loss")
        return {"loss": float(loss.detach()), "seconds": time.monotonic() - started}

    def export_and_validate(self, root: Path) -> dict[str, Any]:
        """Save safe adapter/tokenizer, exact baseline restore, and disk reload check."""
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file
        torch = self.torch
        trained = _state_fingerprint(self.get_state(self.model), torch)
        require(trained["sha256"] != self.initial_fingerprint["sha256"], "adapter never changed")
        root.mkdir(parents=True, exist_ok=False)
        self.model.save_pretrained(str(root), safe_serialization=True)
        self.session.tokenizer.save_pretrained(str(root))
        adapter_config_path = root / "adapter_config.json"
        adapter_config = json.loads(adapter_config_path.read_text())
        repository, revision = self.session.identity["model_id"].rsplit("@", 1)
        adapter_config["base_model_name_or_path"] = repository
        adapter_config["revision"] = revision
        write_json(adapter_config_path, adapter_config)
        require((root / "adapter_model.safetensors").is_file() and
                (root / "adapter_config.json").is_file() and (root / "tokenizer.json").is_file(),
                "complete safetensors adapter/config/tokenizer export required")
        set_peft_model_state_dict(self.model, self.baseline)
        restored = _state_fingerprint(self.get_state(self.model), torch)
        require(restored == self.initial_fingerprint, "baseline adapter restore does not match exact bytes")
        state = load_file(str(root / "adapter_model.safetensors"), device="cpu")
        disk = _state_fingerprint(state, torch)
        require(disk == trained, "saved adapter differs from in-memory trained adapter")
        set_peft_model_state_dict(self.model, state)
        reloaded = _state_fingerprint(self.get_state(self.model), torch)
        require(reloaded == trained, "disk adapter reload does not match trained state")
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True, trust_remote_code=False)
        probe = [{"role": "user", "content": "Return [[0,1],[2,3]]."}]
        kwargs = {"tokenize": True, "add_generation_prompt": True, "enable_thinking": False}
        require(tokenizer.get_vocab() == self.session.tokenizer.get_vocab() and
                tokenizer.apply_chat_template(probe, **kwargs) ==
                self.session.tokenizer.apply_chat_template(probe, **kwargs), "exported tokenizer/template changed")
        material = Path(self.session.identity["local_material_path"])
        for source, target in (("README.md", "BASE_MODEL_CARD.md"), ("LICENSE", "LICENSE"),
                               ("config.json", "source-base-config.json")):
            if (material / source).is_file():
                shutil.copyfile(material / source, root / target)
        write_json(root / "source-model-identity.json", self.session.identity)
        files = {p.name: file_sha256(p) for p in root.iterdir() if p.is_file()}
        binding = {"format": "irisx/arc-next-adapter-binding-v1",
                   "model_id": self.session.identity["model_id"],
                   "material_manifest_sha256": self.session.identity["material_manifest_sha256"],
                   "native_embedding_rows": self.session.identity["native_embedding_rows"],
                   "adapter_state_sha256": trained["sha256"], "files": files}
        write_json(root / "adapter-binding.json", binding)
        return {"adapter_path": str(root), "binding_sha256": file_sha256(root / "adapter-binding.json"),
                "trained_fingerprint": trained, "baseline_restore_exact": True,
                "saved_state_exact": True, "reloaded_adapter_exact": True,
                "tokenizer_round_trip_exact": True,
                "fresh_base_process_reload_verified": False,
                "deployment_note": "offline pinned base plus LoRA; a separate 4-L4 inference probe is still required"}


def _resource_observation(torch: Any) -> dict[str, Any]:
    return {"host_max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved()}


def _worker_entry(config_data: dict[str, Any]) -> None:
    if hasattr(os, "setsid"):
        os.setsid()  # This worker owns its process group; the parent cleans descendants too.
    config_data["budget"] = RunBudget(**config_data["budget"])
    config_data["train_augmentations"] = tuple(config_data["train_augmentations"])
    config = CalibrationConfig(**config_data)
    root, start = Path(config.output_dir), time.monotonic()
    write_json(root / "worker-ownership.json", {"pid": os.getpid(), "process_group": os.getpgrp()})
    result = {"format": "irisx/arc-next-calibration-result-v1", "status": "failed",
              "gpu_runtime_verified": False, "arc_accuracy_measured": False,
              "official_test_answers_loaded": False, "trajectory_sft_enabled": False}
    def event(value: dict[str, Any]) -> None:
        with (root / "events.jsonl").open("a") as stream:
            stream.write(canonical(value).decode() + "\n")
            stream.flush()
    try:
        for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
            os.environ[name] = "1"
        os.environ["WANDB_DISABLED"] = "true"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        tasks, manifest = load_training_material(config.training_tasks_path, config.training_manifest_path)
        rows = build_training_rows(tasks, manifest, train_augmentations=config.train_augmentations)
        write_json(root / "data-manifest.json", manifest)
        write_json(root / "configuration.json", asdict(config))
        write_json(root / "source-manifest.json", {
            "files": {Path(__file__).name: file_sha256(Path(__file__)),
                      "arc_next_models.py": file_sha256(Path(__file__).with_name("arc_next_models.py"))}})
        import torch
        hardware = observe_g4_hardware(torch)
        random.seed(config.seed)
        torch.manual_seed(config.seed)
        torch.cuda.manual_seed_all(config.seed)
        torch.cuda.reset_peak_memory_stats()
        session = load_candidate(config.model_path, config.model_key, manifest_path=config.model_manifest_path,
                                 environment_lock_path=config.environment_lock_path,
                                 allow_experimental_qwen=config.allow_experimental_qwen)
        write_json(root / "model-manifest.json", session.identity)
        write_json(root / "environment-manifest.json", session.environment)
        write_json(root / "hardware.json", hardware)
        tokenized, excluded = tokenize_rows(rows["train"], session.tokenizer, config.budget.max_sequence_tokens, model_key=config.model_key)
        require(tokenized, "all whole training rows exceed the finite sequence budget")
        dev_tokens, dev_excluded = tokenize_rows(rows["dev"], session.tokenizer, config.budget.max_sequence_tokens, model_key=config.model_key)
        evaluation_rows = select_evaluation_rows(dev_tokens, config.budget)
        # Dev rows are recorded by IDs only and are never passed to this optimizer.
        data_receipt = {"train_row_count": len(rows["train"]), "tokenized_train_row_count": len(tokenized),
                        "excluded_whole_rows": excluded, "excluded_dev_whole_rows": dev_excluded,
                        "dev_row_ids": [r["row_id"] for r in rows["dev"]],
                        "selected_evaluation_row_ids": [r["row_id"] for r in evaluation_rows],
                        "train_task_ids": manifest["task_partition"]["train"],
                        "dev_task_ids": manifest["task_partition"]["dev"],
                        "split_before_augmentation": True, "supervision": "withheld training demonstration output",
                        "tokenized_rows_sha256": digest(tokenized)}
        write_json(root / "data-receipt.json", data_receipt)
        backend = TorchLoRABackend(session, config)
        write_json(root / "lora-manifest.json", backend.metadata)
        dev_before = evaluate_rows(backend, evaluation_rows, config.budget, phase="before",
                                   start_time=start, on_event=event)
        write_json(root / "dev-before.json", dev_before)
        training = execute_training_steps(backend, tokenized, config.budget, seed=config.seed,
                                          start_time=start, on_event=event)
        result["training"] = training
        require(training["completed_profile"], "finite budget stopped before the selected calibration profile completed")
        require(time.monotonic() - start < config.budget.max_wall_seconds,
                "wall budget exhausted before export validation")
        dev_after = evaluate_rows(backend, evaluation_rows, config.budget, phase="after",
                                  start_time=start, prior_input_tokens=dev_before["cumulative_eval_input_tokens"],
                                  on_event=event)
        write_json(root / "dev-after.json", dev_after)
        result["dev_evaluation"] = {"before": dev_before, "after": dev_after,
                                    "nll_delta_after_minus_before": dev_after["supervised_token_weighted_nll"] -
                                    dev_before["supervised_token_weighted_nll"]}
        result["export"] = backend.export_and_validate(root / "adapter")
        result.update(status="completed-calibration", gpu_runtime_verified=True,
                      model_id=session.identity["model_id"], hardware=hardware,
                      resources=_resource_observation(torch),
                      acceptance_scope="bounded LoRA/backend calibration only; no ARC score or method promotion")
    except BaseException as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)[:2000]}
        event({"event": "failed", "error": result["error"]})
    finally:
        result["elapsed_seconds"] = time.monotonic() - start
        write_json(root / "result.json", result)



def _stop_owned_worker(process: Any, root: Path) -> dict[str, Any]:
    """Clean our isolated process group on timeout, cancellation, and all exits."""
    pid = getattr(process, "pid", None)
    group = False
    owner = root / "worker-ownership.json"
    if pid is not None and owner.is_file():
        receipt = json.loads(owner.read_text())
        group = receipt.get("pid") == receipt.get("process_group") == pid
    def send_group(sig: int) -> None:
        if group:
            try:
                os.killpg(pid, sig)
            except ProcessLookupError:
                pass
    send_group(signal.SIGTERM)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
    send_group(signal.SIGKILL)
    if process.is_alive():
        process.kill()
        process.join(timeout=5)
    alive = process.is_alive()
    require(not alive, "owned worker still alive after TERM/KILL; stop the manual session immediately")
    group_alive = False
    if group:
        try:
            os.killpg(pid, 0)
            group_alive = True
        except ProcessLookupError:
            pass
    return {"worker_alive_after_cleanup": alive, "owned_process_group": pid if group else None,
            "group_still_observable_after_kill": group_alive,
            "group_note": "a killed descendant may remain observable briefly while awaiting OS reaping"}


def run_calibration(config: CalibrationConfig | None = None) -> dict[str, Any]:
    """Notebook-callable one-shot entry, False-by-default with a hard process timeout.

    Never schedules/resumes another run. Killing this worker does NOT stop a GCP VM;
    the owner must separately stop their existing paid instance when finished.
    """
    config = config or CalibrationConfig()
    proposed = preflight(config)
    if not config.enabled:
        return {"status": "inert", "reason": "manual enabled=True is required", "preflight": proposed,
                "model_imported": False, "gpu_execution_started": False}
    root = Path(config.output_dir)
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "preflight.json", proposed)
    process = multiprocessing.get_context("spawn").Process(target=_worker_entry, args=(asdict(config),))
    start = time.monotonic()
    started, result = False, None
    try:
        process.start()
        started = True
        process.join(timeout=config.budget.max_wall_seconds)
        if process.is_alive():
            result = {"format": "irisx/arc-next-calibration-result-v1", "status": "watchdog-timeout",
                      "elapsed_seconds": time.monotonic() - start,
                      "wall_budget_seconds": config.budget.max_wall_seconds,
                      "gpu_runtime_verified": False, "complete_artifact": False,
                      "evidence": "partial events.jsonl remains; no successful calibration claim"}
        elif not (root / "result.json").is_file():
            result = {"status": "worker-failed-without-result", "worker_exitcode": process.exitcode,
                      "gpu_runtime_verified": False, "complete_artifact": False}
        else:
            result = json.loads((root / "result.json").read_text())
            result["worker_exitcode"] = process.exitcode
            require(process.exitcode == 0 or result.get("status") != "completed-calibration",
                    "abnormal worker cannot claim success")
    except BaseException as error:
        result = {"status": "cancelled" if isinstance(error, KeyboardInterrupt) else "supervisor-failed",
                  "error": {"type": type(error).__name__, "message": str(error)[:1000]},
                  "gpu_runtime_verified": False, "complete_artifact": False}
        write_json(root / "watchdog-result.json", result)
        raise
    finally:
        if started or getattr(process, "pid", None) is not None:
            cleanup = _stop_owned_worker(process, root)
            if result is not None:
                result["cleanup"] = cleanup
        if result is not None:
            write_json(root / "watchdog-result.json", result)
    return result

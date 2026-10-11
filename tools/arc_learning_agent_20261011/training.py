"""Real native-vocabulary LoRA updates, exact restart, isolated demo-only TTT.

Imports are inert. Neural libraries are loaded only by explicit Trainer creation.
Checkpoints are complete update boundaries; never pretend adapter-only resume.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile
import time
import uuid

from tools.arc_next_models import canonical, digest, lora_target_modules, require
from tools.arc_next_training import _state_fingerprint
from .data import build_task_records, validate_records

DEFAULTS = {"tiny_cpu": False, "model_key": "granite-4.2-8b", "lora_rank": 32, "lora_alpha": 64,
            "learning_rate": 2e-4, "task_learning_rate": 5e-5, "weight_decay": 0.0,
            "betas": [0.9, 0.999], "eps": 1e-8, "max_grad_norm": 1.0,
            "max_sequence_tokens": 8192, "max_input_tokens": 100_000_000,
            "max_supervised_tokens": 50_000_000, "seed": 0, "task_augmentations": 8,
            "gradient_checkpointing": True, "checkpoint_every": 0,
            "schedule_steps": 0, "warmup_steps": 0, "min_lr_ratio": 0.1, "objective_cycle": None, "checkpoint_keep": 2, "checkpoint_disk_reserve_bytes": 4 * 1024**3}


def _fingerprint_tree(value, torch):
    """Stable names/shapes/dtypes/raw bytes, independent of pickle storage IDs."""
    def walk(item):
        if isinstance(item, torch.Tensor):
            v = item.detach().cpu().contiguous()
            return {"tensor": True, "dtype": str(v.dtype), "shape": list(v.shape),
                    "sha256": hashlib.sha256(v.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()}
        if isinstance(item, dict):
            return {str(k): walk(v) for k, v in sorted(item.items(), key=lambda pair: str(pair[0]))}
        if isinstance(item, (list, tuple)):
            return [walk(v) for v in item]
        return item
    return digest(walk(value))


class Trainer:
    def __init__(self, native_model, config=None):
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        self.torch, self.native = torch, native_model
        self.config = {**DEFAULTS, **dict(config or {})}
        self._validate_config()
        self.optimizer = self.scheduler = None
        self._snapshots = {}
        self._global = None
        self._task_id = None
        self._last_task_reset_receipt = None
        self._caller_rng = None
        self._run_state = None
        self._task_records_digest = None
        self._optimizer_serial = 0
        self._fingerprint_cache = None
        self.fingerprint_cache_hits = 0
        self.fingerprint_rehashes = 0
        self._schedule_records = []
        self._effective_cycle = None
        caller_rng = self._get_rng()
        try:
            self._seed(self.config["seed"])
            model = native_model.model
            if self.config["tiny_cpu"]:
                require(next(model.parameters()).device.type == "cpu", "tiny_cpu requires CPU model")
                require(sum(p.numel() for p in model.parameters()) <= 10_000_000, "tiny_cpu model exceeds 10M parameters")
            else:
                require(next(model.parameters()).device.type == "cuda", "production LoRA requires admitted GPU model")
                require(isinstance(getattr(native_model, "identity", None), dict) and native_model.identity.get("model_id"), "pinned production model identity required")
            require(model.get_input_embeddings().weight.shape[0] > 16, "compact16 vocabulary forbidden")
            require(model.get_output_embeddings().weight.shape[0] == model.get_input_embeddings().weight.shape[0], "full native embedding/head rows required")
            model.config.use_cache = False
            if self.config["gradient_checkpointing"]:
                model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
                if hasattr(model, "enable_input_require_grads"):
                    model.enable_input_require_grads()
            if not getattr(model, "peft_config", None):
                if self.config["tiny_cpu"]:
                    suffixes = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
                    targets = sorted(name for name, module in model.named_modules() if name.startswith("model.layers.") and
                                     name.rsplit(".", 1)[-1] in suffixes and isinstance(module, torch.nn.Linear))
                    require(len(targets) == 7 * model.config.num_hidden_layers, "tiny model needs same seven-projection topology")
                else:
                    targets = lora_target_modules(model, self.config["model_key"], torch)
                model = get_peft_model(model, LoraConfig(task_type=TaskType.CAUSAL_LM,
                    r=self.config["lora_rank"], lora_alpha=self.config["lora_alpha"], target_modules=targets,
                    lora_dropout=0.0, bias="none"))
            else:
                require(len(model.peft_config) == 1, "nested/multiple adapters forbidden")
                peft = next(iter(model.peft_config.values()))
                expected_targets = {f"model.layers.{i}.{group}.{name}" for i in range(model.config.num_hidden_layers)
                                    for group, names in (("self_attn", ("q_proj", "k_proj", "v_proj", "o_proj")),
                                                         ("mlp", ("gate_proj", "up_proj", "down_proj"))) for name in names}
                require(peft.r == self.config["lora_rank"] and peft.lora_alpha == self.config["lora_alpha"] and
                        peft.lora_dropout == 0.0 and not peft.modules_to_save and peft.bias == "none" and
                        not peft.use_rslora and not peft.use_dora and set(peft.target_modules) == expected_targets,
                        "existing adapter differs from frozen seven-projection LoRA recipe")
                for name, parameter in model.named_parameters():
                    parameter.requires_grad_("lora_" in name)
            self.model = model
            self.native.model = model
            self.parameters = {name: p for name, p in model.named_parameters() if p.requires_grad}
            require(self.parameters and all("lora_" in name for name in self.parameters), "only LoRA parameters trainable")
            self.parameter_names = list(self.parameters)
            self._base_identity = self._model_identity()
            self._initial = self.fingerprint()
            self._publish_fingerprint(self._initial)
        finally:
            self._set_rng(caller_rng)

    def _validate_config(self):
        c = self.config
        for key in ("lora_rank", "lora_alpha", "max_sequence_tokens", "max_input_tokens", "max_supervised_tokens", "task_augmentations"):
            require(type(c[key]) is int and c[key] > 0, "invalid " + key)
        for key in ("learning_rate", "task_learning_rate", "eps", "max_grad_norm"):
            require(type(c[key]) in (int, float) and math.isfinite(c[key]) and c[key] > 0, "invalid " + key)
        require(c["max_sequence_tokens"] <= 8192, "sequence cap cannot exceed 8192")
        require(type(c["seed"]) is int and 0 <= c["seed"] < 2**63, "invalid seed")
        require(type(c["tiny_cpu"]) is bool and type(c["gradient_checkpointing"]) is bool, "explicit bool mode required")
        require(len(c["betas"]) == 2 and all(0 <= b < 1 for b in c["betas"]), "invalid Adam betas")
        require(0 <= c["weight_decay"] and math.isfinite(c["weight_decay"]), "invalid weight decay")
        require(0 <= c["min_lr_ratio"] <= 1 and 0 <= c["warmup_steps"] <= c["schedule_steps"], "invalid LR schedule")
        require(c["objective_cycle"] is None or (type(c["objective_cycle"]) is list and 1 <= len(c["objective_cycle"]) <= 128 and all(k in ("grid", "program", "repair") for k in c["objective_cycle"])), "invalid objective cycle")
        require(type(c["checkpoint_keep"]) is int and 1 <= c["checkpoint_keep"] <= 10, "checkpoint_keep must be 1..10")
        require(type(c["checkpoint_disk_reserve_bytes"]) is int and c["checkpoint_disk_reserve_bytes"] >= (0 if c["tiny_cpu"] else 4 * 1024**3), "production checkpoint reserve must retain 4GiB")
        require(type(c["checkpoint_every"]) is int and c["checkpoint_every"] >= 0, "invalid checkpoint cadence")

    def _get_rng(self):
        import numpy as np
        torch = self.torch
        state = np.random.get_state()
        return {"python": random.getstate(), "numpy": {"name": state[0], "keys": state[1].tolist(),
                "position": state[2], "has_gauss": state[3], "cached_gaussian": state[4]},
                "torch": torch.get_rng_state().clone(),
                "cuda": [x.clone() for x in torch.cuda.get_rng_state_all()] if torch.cuda.is_initialized() else []}

    def _set_rng(self, state):
        import numpy as np
        random.setstate(state["python"])
        n = state["numpy"]
        np.random.set_state((n["name"], np.array(n["keys"], dtype=np.uint32), n["position"], n["has_gauss"], n["cached_gaussian"]))
        self.torch.set_rng_state(state["torch"].cpu())
        if state["cuda"]:
            require(self.torch.cuda.is_available() and len(state["cuda"]) == self.torch.cuda.device_count(), "CUDA RNG device count differs")
            self.torch.cuda.set_rng_state_all(state["cuda"])

    def _seed(self, seed):
        import numpy as np
        random.seed(seed)
        np.random.seed(seed % 2**32)
        self.torch.manual_seed(seed)
        if self.torch.cuda.is_initialized():
            self.torch.cuda.manual_seed_all(seed)

    def _state(self):
        return {k: v.detach().cpu().clone() for k, v in self.parameters.items()}

    def fingerprint(self):
        # Only tracked optimizer/load_state_dict/no_grad-copy_ writes are admitted.
        # .data writes and concurrent mutation are unsupported, as in NativeModel.
        signature = tuple((name, id(value), value.data_ptr(), value._version, tuple(value.shape),
                           str(value.dtype), str(value.device), value.requires_grad)
                          for name, value in sorted(self.parameters.items()))
        if self._fingerprint_cache is not None and self._fingerprint_cache[0] == signature:
            self.fingerprint_cache_hits += 1
            return deepcopy(self._fingerprint_cache[1])
        value = _state_fingerprint(self.parameters, self.torch)
        self._fingerprint_cache = (signature, deepcopy(value))
        self.fingerprint_rehashes += 1
        return value

    def _publish_fingerprint(self, fingerprint=None):
        self.native.adapter_state_sha256 = (fingerprint or self.fingerprint())["sha256"]

    def _model_identity(self):
        import transformers
        import peft
        import numpy
        torch = self.torch
        environment_path = getattr(self.native, "config", {}).get("environment_lock_path")
        environment_sha256 = None
        if environment_path:
            path = Path(environment_path)
            require(path.is_file(), "native environment lock path unavailable")
            environment_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        identity = {"native_identity": deepcopy(getattr(self.native, "identity", {})),
                    "model_config": self.model.config.to_dict(),
                    "tokenizer_vocab_sha256": digest(self.native.tokenizer.get_vocab()),
                    "chat_template_sha256": digest(getattr(self.native.tokenizer, "chat_template", None)),
                    "tiny_cpu": self.config["tiny_cpu"],
                    "runtime": {"python": sys.version, "torch": str(torch.__version__),
                                "transformers": transformers.__version__, "peft": peft.__version__,
                                "numpy": numpy.__version__, "torch_cuda_build": torch.version.cuda,
                                "environment_lock_sha256": environment_sha256},
                    "precision_and_kernels": {
                        "trainable_dtypes": sorted({str(p.dtype) for p in self.parameters.values()}),
                        "frozen_dtypes": sorted({str(p.dtype) for p in self.model.parameters() if not p.requires_grad}),
                        "device_types": sorted({p.device.type for p in self.model.parameters()}),
                        "float32_matmul_precision": torch.get_float32_matmul_precision(),
                        "cuda_matmul_allow_tf32": bool(torch.backends.cuda.matmul.allow_tf32),
                        "cudnn_allow_tf32": bool(torch.backends.cudnn.allow_tf32),
                        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
                        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
                        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
                        "deterministic_warn_only": bool(torch.is_deterministic_algorithms_warn_only_enabled())},
                    "resume_validation_scope": "CPU differential tested; CUDA bitwise restart not yet validated"}
        # Production identity comes from exact hash-bound loader, not an 8B rehash.
        if self.config["tiny_cpu"]:
            identity["frozen_base_sha256"] = _fingerprint_tree({k: p for k, p in self.model.named_parameters() if not p.requires_grad}, self.torch)
        return identity

    def _source_identity(self):
        files = [Path(__file__), Path(__file__).with_name("data.py"), Path(__file__).with_name("grid_codec.py"),
                 Path(__file__).with_name("native_model.py"), Path(__file__).parents[1] / "arc_next_training.py",
                 Path(__file__).parents[1] / "arc_next_models.py",
                 Path(__file__).parents[2] / "src" / "irisx" / "arc_nvarc_data.py"]
        return {str(p.relative_to(Path(__file__).parents[2])): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}

    def _identity(self, records):
        # All config including full lineage/protected set is part of exact restart.
        return {"model": self._base_identity, "source": self._source_identity(),
                "config_sha256": digest(self.config), "data_sha256": digest(records),
                "parameter_names": self.parameter_names, "objective": "native-full-vocab-completion-only-v1",
                "task_id": self._task_id, "effective_objective_cycle": self._effective_cycle}

    def _clear(self):
        self.model.zero_grad(set_to_none=True)
        self.optimizer = self.scheduler = None
        self._run_state = None
        self._task_records_digest = None

    def snapshot(self, label):
        require(type(label) is str and label, "snapshot label required")
        token = uuid.uuid4().hex
        state = self._state()
        fingerprint = _state_fingerprint(state, self.torch)
        self._snapshots[token] = {"state": state, "rng": self._get_rng(), "fingerprint": fingerprint,
                                  "label": label, "model_identity_sha256": digest(self._base_identity)}
        return {"snapshot_id": token, "label": label, "fingerprint": deepcopy(fingerprint),
                "model_identity_sha256": digest(self._base_identity)}

    def restore(self, snapshot):
        require(type(snapshot) is dict and snapshot.get("snapshot_id") in self._snapshots, "unknown snapshot handle")
        saved = self._snapshots[snapshot["snapshot_id"]]
        require(snapshot.get("fingerprint") == saved["fingerprint"] and snapshot.get("model_identity_sha256") == saved["model_identity_sha256"], "snapshot handle changed")
        require(_state_fingerprint(saved["state"], self.torch) == saved["fingerprint"], "snapshot tensors changed")
        with self.torch.no_grad():
            for name, parameter in self.parameters.items():
                parameter.copy_(saved["state"][name].to(parameter.device))
        self._clear()
        self._set_rng(saved["rng"])
        actual = self.fingerprint()
        require(actual == saved["fingerprint"], "exact adapter restore failed")
        self._publish_fingerprint(actual)
        return {"restored": True, "adapter_sha256": actual["sha256"], "optimizer_cleared": True,
                "scheduler_cleared": True, "gradients_cleared": all(p.grad is None for p in self.parameters.values()),
                "rng_sha256": _fingerprint_tree(self._get_rng(), self.torch)}

    def freeze_global(self):
        require(self._task_id is None, "cannot freeze task-adapted global")
        self._global = self.snapshot("global")
        self._clear()
        return deepcopy(self._global)

    @property
    def active_task_id(self):
        return self._task_id

    @property
    def last_task_reset_receipt(self):
        return deepcopy(self._last_task_reset_receipt)

    def begin_task(self, task_id):
        require(type(task_id) is str and bool(task_id), "task ID required")
        require(self._task_id is None, "previous task must end before another begins")
        require(self._global is not None, "freeze_global required before task adaptation")
        caller = self._get_rng()
        reset = self.restore(self._global)
        self._caller_rng = caller
        self._task_id = task_id
        self._last_task_reset_receipt = None
        seed = int(digest(["independent-task-rng", self.config["seed"], task_id])[:15], 16)
        self._seed(seed)
        self._task_seed = seed
        return {"task_id": task_id, "seed": seed, **reset, "task_rng_sha256": _fingerprint_tree(self._get_rng(), self.torch)}

    def end_task(self):
        if self._task_id is None:
            last = self._last_task_reset_receipt
            require(last is not None and last.get("restored") is True and
                    self.fingerprint()["sha256"] == last["adapter_sha256"] and self.optimizer is None and
                    self.scheduler is None and all(p.grad is None for p in self.parameters.values()), "no verified prior task reset")
            return {**deepcopy(last), "already_ended": True}
        require(self._task_id is not None, "no active task")
        task_id, caller = self._task_id, self._caller_rng
        result = self.restore(self._global)
        self._task_id = self._caller_rng = None
        self._set_rng(caller)
        result.update(task_id=task_id, caller_rng_restored=True)
        self._last_task_reset_receipt = deepcopy(result)
        return result

    def _make_optimizer(self):
        torch, c = self.torch, self.config
        lr = c["task_learning_rate"] if self._task_id is not None else c["learning_rate"]
        self.optimizer = torch.optim.AdamW(list(self.parameters.values()), lr=lr, betas=tuple(c["betas"]),
                                          eps=c["eps"], weight_decay=c["weight_decay"], foreach=False)
        self._optimizer_serial += 1
        def schedule(step):
            if c["schedule_steps"] == 0 or self._task_id is not None:
                return 1.0
            if c["warmup_steps"] and step < c["warmup_steps"]:
                return (step + 1) / c["warmup_steps"]
            progress = min(1.0, max(0.0, (step - c["warmup_steps"]) / max(1, c["schedule_steps"] - c["warmup_steps"])))
            return c["min_lr_ratio"] + (1 - c["min_lr_ratio"]) * 0.5 * (1 + math.cos(math.pi * progress))
        self.scheduler = torch.optim.lr_scheduler.LambdaLR(self.optimizer, schedule)

    def _order(self, records_count, epoch):
        seed = self._task_seed if self._task_id is not None else self.config["seed"]
        if self._effective_cycle is None:
            order = list(range(records_count))
            random.Random(digest(["training-data-order", seed, epoch])).shuffle(order)
            return order
        require(len(self._schedule_records) == records_count, "schedule record identities missing")
        # Engineering hypothesis: bounded objective cycle, then equal family turns.
        # Repeated minority rows remain explicit actual work and never new examples.
        grouped = {}
        for index, record in enumerate(self._schedule_records):
            grouped.setdefault(record["kind"], {}).setdefault(record["family_id"], []).append(index)
        cycles = math.ceil(records_count / len(self._effective_cycle))
        selected = {kind: 0 for kind in grouped}
        family_visits = {}
        permutations = {}
        order = []
        for _ in range(cycles):
            for kind in self._effective_cycle:
                families = sorted(grouped[kind])
                family = families[selected[kind] % len(families)]
                selected[kind] += 1
                rows = grouped[kind][family]
                key = (kind, family)
                visit = family_visits.get(key, 0)
                pass_index, row_index = divmod(visit, len(rows))
                permutation_key = (kind, family, pass_index)
                if permutation_key not in permutations:
                    values = sorted(rows, key=lambda i: self._schedule_records[i]["record_id"])
                    random.Random(digest(["objective-family-order-v1", seed, epoch, kind, family, pass_index])).shuffle(values)
                    permutations[permutation_key] = values
                order.append(permutations[permutation_key][row_index])
                family_visits[key] = visit + 1
        return order

    def _prepared(self, record):
        row = self.native.prepare_completion(record["messages"], record["completion"])
        ids, labels = row["input_ids"], row["labels"]
        require(type(ids) is list and type(labels) is list and len(ids) == len(labels), "invalid native completion tensors")
        require(all(type(i) is int and 0 <= i < self.model.get_output_embeddings().weight.shape[0] for i in ids), "token outside native vocabulary")
        prefix = row["prompt_tokens"]
        require(prefix > 0 and labels[:prefix] == [-100] * prefix and labels[prefix:] == ids[prefix:] and len(ids) > prefix, "completion-only loss mask differs")
        require(sum(x != -100 for x in labels) == row["completion_tokens"], "completion mask count differs")
        row["input_tokens"] = len(ids)
        row["supervised_tokens"] = len(ids) - prefix
        return row

    def _step(self, row):
        started = time.monotonic()
        torch = self.torch
        device = next(self.model.parameters()).device
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        before = self.fingerprint()
        ids = torch.tensor([row["input_ids"]], dtype=torch.long, device=device)
        labels = torch.tensor([row["labels"]], dtype=torch.long, device=device)
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        output = self.model(input_ids=ids, attention_mask=torch.ones_like(ids), labels=labels, use_cache=False)
        loss = output.loss
        require(loss is not None and bool(torch.isfinite(loss)), "nonfinite training loss")
        loss.backward()
        require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in self.parameters.values()), "missing/nonfinite LoRA gradients")
        norm = torch.nn.utils.clip_grad_norm_(list(self.parameters.values()), self.config["max_grad_norm"], error_if_nonfinite=True)
        self.optimizer.step()
        self.scheduler.step()
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        actual_steps = {int(float(self.optimizer.state[p]["step"])) for p in self.parameters.values()}
        require(len(actual_steps) == 1, "inconsistent Adam step identities")
        require(all(bool(torch.isfinite(state[key]).all()) for state in self.optimizer.state.values() for key in ("exp_avg", "exp_avg_sq")), "nonfinite Adam state")
        after = self.fingerprint()
        changed = sum(before["tensors"][name]["sha256"] != entry["sha256"] for name, entry in after["tensors"].items())
        require(changed > 0, "no actual LoRA tensor update")
        self._publish_fingerprint(after)
        receipt = {"loss": float(loss.detach()), "elapsed_seconds": time.monotonic() - started,
                   "gradient_norm": float(norm), "finite_gradients": True, "changed_adapter_tensors": changed,
                   "adam_step": next(iter(actual_steps)), "adapter_before_sha256": before["sha256"], "adapter_after_sha256": after["sha256"]}
        self.optimizer.zero_grad(set_to_none=True)
        receipt["elapsed_seconds"] = time.monotonic() - started
        return receipt

    def train(self, records, *, max_steps, deadline, checkpoint_dir=None, resume=None):
        require(type(max_steps) is int and max_steps >= 0, "finite nonnegative optimizer limit required")
        require(type(deadline) in (int, float) and math.isfinite(deadline), "absolute monotonic deadline required")
        started = time.monotonic()
        initial = self.fingerprint()["sha256"]
        if self._task_id is None:
            require(self.config.get("split_manifest") is not None, "global training requires explicit lineage admission")
            admission = validate_records(records, self.config["split_manifest"], self.config.get("protected_ids", ()))
        else:
            require(digest(records) == self._task_records_digest, "task training accepts only internally built demo-only records")
            admission = {"scope": "active-task-demonstrations-only", "records_sha256": digest(records)}
        train_records = [r for r in records if r["split"] == "train"]
        require(train_records, "no admitted train records")
        self._schedule_records = [{k: r[k] for k in ("kind", "family_id", "record_id")} for r in train_records]
        requested = self.config["objective_cycle"] if self._task_id is None else None
        available = {r["kind"] for r in train_records}
        self._effective_cycle = [kind for kind in requested if kind in available] if requested else None
        require(self._effective_cycle is None or bool(self._effective_cycle), "requested objective kinds absent")
        identity = self._identity(records)
        if resume is not None:
            require(self._task_id is None, "task-local checkpoint resume is not admitted")
            self.load_checkpoint(resume, identity=identity, records_count=len(train_records))
        elif self._run_state is None:
            if self._task_id is None:
                self._seed(self.config["seed"])
            self._make_optimizer()
            self._run_state = {"identity": identity, "epoch": 0, "cursor": 0, "order": self._order(len(train_records), 0),
                               "steps": 0, "input_tokens": 0, "supervised_tokens": 0, "attempted_steps": 0,
                               "attempted_input_tokens": 0, "attempted_supervised_tokens": 0, "excluded": {}, "seen_record_ids": [], "seen_families": [], "processed_by_kind": {}}
        else:
            require(self._run_state["identity"] == identity, "cannot change data/config/source mid-training; start a new state")
        state = self._run_state
        require(state["attempted_steps"] == state["steps"], "failed training state cannot continue without checkpoint restore")
        attempted_before = state["attempted_steps"]
        adam_before = max((int(float(v.get("step", 0))) for v in self.optimizer.state.values()), default=0)
        steps, input_tokens, supervised_tokens, updates, checkpoints = 0, 0, 0, [], []
        status, error = "complete", None
        processed_by_kind, seen_records, seen_families = {}, set(), set()
        while steps < max_steps:
            if time.monotonic() >= deadline:
                status = "deadline"
                break
            if len(state["excluded"]) == len(train_records):
                status = "no_context_eligible_records"
                break
            if state["cursor"] == len(state["order"]):
                state["epoch"] += 1
                state["cursor"] = 0
                state["order"] = self._order(len(train_records), state["epoch"])
            index = state["order"][state["cursor"]]
            record = train_records[index]
            if record["record_id"] in state["excluded"]:
                state["cursor"] += 1
                continue
            try:
                row = self._prepared(record)
            except ValueError as exc:
                # Only explicit context overflow is an exclusion; any masking/schema failure aborts.
                if "context" in str(exc).lower() and any(word in str(exc).lower() for word in ("limit", "exceed", "overflow", "budget", "excluded")):
                    state["excluded"][record["record_id"]] = {"reason": str(exc)}
                    state["cursor"] += 1
                    continue
                raise
            if row["input_tokens"] > self.config["max_sequence_tokens"]:
                state["excluded"][record["record_id"]] = {"reason": "whole-row-exceeds-sequence-budget", "input_tokens": row["input_tokens"]}
                state["cursor"] += 1
                continue
            if time.monotonic() >= deadline:
                status = "deadline"
                break
            if state["attempted_input_tokens"] + row["input_tokens"] > self.config["max_input_tokens"] or state["attempted_supervised_tokens"] + row["supervised_tokens"] > self.config["max_supervised_tokens"]:
                status = "token_budget"
                break
            # Reserve physical work before the real forward, including failed work.
            state["attempted_steps"] += 1
            state["attempted_input_tokens"] += row["input_tokens"]
            state["attempted_supervised_tokens"] += row["supervised_tokens"]
            input_tokens += row["input_tokens"]
            supervised_tokens += row["supervised_tokens"]
            for counts in (processed_by_kind, state["processed_by_kind"]):
                item = counts.setdefault(record["kind"], {"microbatches": 0, "input_tokens": 0, "supervised_tokens": 0})
                item["microbatches"] += 1
                item["input_tokens"] += row["input_tokens"]
                item["supervised_tokens"] += row["supervised_tokens"]
            seen_records.add(record["record_id"])
            seen_families.add(record["family_id"])
            if record["record_id"] not in state["seen_record_ids"]:
                state["seen_record_ids"].append(record["record_id"])
            if record["family_id"] not in state["seen_families"]:
                state["seen_families"].append(record["family_id"])
            try:
                update = self._step(row)
            except Exception as exc:
                status, error = "failed_update", type(exc).__name__ + ": " + str(exc)
                self.optimizer.zero_grad(set_to_none=True)
                break
            update.update(record_id=record["record_id"], input_tokens=row["input_tokens"], supervised_tokens=row["supervised_tokens"])
            updates.append(update)
            state["cursor"] += 1
            state["steps"] += 1
            state["input_tokens"] += row["input_tokens"]
            state["supervised_tokens"] += row["supervised_tokens"]
            steps += 1
            if checkpoint_dir and self.config["checkpoint_every"] and state["steps"] % self.config["checkpoint_every"] == 0 and time.monotonic() < deadline:
                checkpoints.append(self.save_checkpoint(checkpoint_dir))
        if checkpoint_dir and status != "failed_update" and time.monotonic() < deadline:
            if not checkpoints or checkpoints[-1]["steps"] != state["steps"]:
                checkpoints.append(self.save_checkpoint(checkpoint_dir))
        self.model.eval()
        elapsed = time.monotonic() - started
        lookup = {r["record_id"]: r for r in train_records}
        for counts, ids_seen in ((processed_by_kind, seen_records), (state["processed_by_kind"], state["seen_record_ids"])):
            for kind, item in counts.items():
                matching = [lookup[key] for key in ids_seen if lookup[key]["kind"] == kind]
                item["unique_record_count"] = len(matching)
                item["unique_family_count"] = len({r["family_id"] for r in matching})
        observed_adam = [int(float(v.get("step", 0))) for v in self.optimizer.state.values()]
        observed_updates = max(observed_adam, default=adam_before) - adam_before
        receipt = {"status": status, "steps": steps, "optimizer_steps": observed_updates, "optimizer_state_consistent": len(set(observed_adam)) <= 1, "attempted_microbatches": state["attempted_steps"] - attempted_before, "usage_known": True, "total_steps": state["steps"], "input_tokens": input_tokens,
                   "supervised_tokens": supervised_tokens, "elapsed_seconds": elapsed, "losses": [u["loss"] for u in updates],
                   "updates": updates, "admission": admission, "exclusions": deepcopy(state["excluded"]),
                   "sampling": {"policy": "objective-family-cycle-v1" if self._effective_cycle else "uniform-row-epochs",
                                "requested_cycle": self.config["objective_cycle"] if self._task_id is None else None,
                                "effective_cycle": self._effective_cycle, "missing_kinds_removed": sorted(set(self.config["objective_cycle"] or []) - available) if self._task_id is None else [],
                                "engineering_hypothesis": True},
                   "processed_by_kind": processed_by_kind, "cumulative_processed_by_kind": deepcopy(state["processed_by_kind"]),
                   "unique_record_ids": sorted(seen_records), "unique_record_count": len(seen_records), "unique_family_count": len(seen_families),
                   "cumulative_unique_record_count": len(state["seen_record_ids"]), "cumulative_unique_family_count": len(state["seen_families"]),
                   "adapter_before_sha256": initial, "adapter_after_sha256": self.fingerprint()["sha256"],
                   "optimizer_state_sha256": _fingerprint_tree(self.optimizer.state_dict(), self.torch),
                   "optimizer_serial": self._optimizer_serial, "rng_sha256": _fingerprint_tree(self._get_rng(), self.torch),
                   "cursor": {k: deepcopy(state[k]) for k in ("epoch", "cursor", "order")},
                   "checkpoints": checkpoints, "input_tokens_per_second": input_tokens / elapsed if elapsed else 0,
                   "tiny_cpu": self.config["tiny_cpu"], "full_native_vocabulary": self.model.get_output_embeddings().weight.shape[0],
                   "validation_claim": "training loss only; no fresh-fold generalization evidence"}
        if next(self.model.parameters()).device.type == "cuda":
            receipt.update(cuda_peak_allocated_bytes=self.torch.cuda.max_memory_allocated(), cuda_peak_reserved_bytes=self.torch.cuda.max_memory_reserved())
        if error:
            receipt["error"] = error
        return receipt

    def adapt_task(self, task_id, demos, *, max_steps, deadline):
        if self._task_id is None:
            self.begin_task(task_id)
        require(self._task_id == task_id, "another task is active")
        try:
            records = build_task_records(task_id, demos, augmentations=self.config["task_augmentations"], seed=self._task_seed)
            if not records:
                return {"task_id": task_id, "status": "skipped_single_demo", "steps": 0, "input_tokens": 0,
                        "supervised_tokens": 0, "elapsed_seconds": 0.0, "losses": [], "adapter_before_sha256": self.fingerprint()["sha256"],
                        "adapter_after_sha256": self.fingerprint()["sha256"], "optimizer_state_sha256": None}
            self._task_records_digest = digest(records)
            result = self.train(records, max_steps=max_steps, deadline=deadline)
            result["task_id"] = task_id
            return result
        except BaseException:
            # Exceptions may never leak an altered task adapter into the next task.
            self.end_task()
            raise

    def save_checkpoint(self, checkpoint_dir):
        require(self._run_state is not None and self.optimizer is not None, "no complete optimizer state to checkpoint")
        require(self._run_state["attempted_steps"] == self._run_state["steps"], "failed/incomplete update cannot be checkpointed")
        require(all(p.grad is None for p in self.parameters.values()), "checkpoint only at cleared-gradient update boundary")
        root = Path(checkpoint_dir)
        root.mkdir(parents=True, exist_ok=True)
        root = root.resolve()
        owner, history = self._checkpoint_owner(root)
        tensor_bytes = sum(p.numel() * p.element_size() for p in self.parameters.values())
        tensor_bytes += sum(v.numel() * v.element_size() for state in self.optimizer.state.values() for v in state.values() if isinstance(v, self.torch.Tensor))
        projected_bytes = int(tensor_bytes * 1.1) + 16 * 1024**2
        free_bytes = shutil.disk_usage(root).free
        require(free_bytes >= projected_bytes + self.config["checkpoint_disk_reserve_bytes"], "insufficient checkpoint disk reserve")
        target = root / ("step-%08d-%s" % (self._run_state["steps"], uuid.uuid4().hex[:8]))
        staging = Path(tempfile.mkdtemp(prefix=".checkpoint-", dir=root))
        try:
            payload = {"format": "irisx/learning-lora-checkpoint-v1", "identity": self._run_state["identity"],
                       "adapter": self._state(), "optimizer": self.optimizer.state_dict(), "scheduler": self.scheduler.state_dict(),
                       "rng": self._get_rng(), "run_state": deepcopy(self._run_state)}
            file = staging / "state.pt"
            self.torch.save(payload, file)
            with file.open("rb") as handle:
                os.fsync(handle.fileno())
            manifest = {"format": payload["format"], "owner_token": owner["owner_token"], "state_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                        "state_bytes": file.stat().st_size, "identity_sha256": digest(payload["identity"]),
                        "adapter_sha256": self.fingerprint()["sha256"], "optimizer_sha256": _fingerprint_tree(payload["optimizer"], self.torch),
                        "rng_sha256": _fingerprint_tree(payload["rng"], self.torch), "steps": self._run_state["steps"]}
            (staging / "manifest.json").write_bytes(canonical(manifest) + b"\n")
            with (staging / "manifest.json").open("rb") as handle:
                os.fsync(handle.fileno())
            staging_fd = os.open(staging, os.O_RDONLY)
            try:
                os.fsync(staging_fd)
            finally:
                os.close(staging_fd)
            os.replace(staging, target)
            pointer = root / (".latest-" + uuid.uuid4().hex)
            pointer.write_bytes(canonical({"directory": target.name, "manifest_sha256": hashlib.sha256((target / "manifest.json").read_bytes()).hexdigest()}) + b"\n")
            with pointer.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(pointer, root / "latest.json")
            directory = os.open(root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            history.append({"directory": target.name, "steps": manifest["steps"], "state_sha256": manifest["state_sha256"],
                            "manifest_sha256": hashlib.sha256((target / "manifest.json").read_bytes()).hexdigest(), "status": "retained"})
            self._atomic_json(root / "checkpoint-history.json", history)
            history = self._prune_checkpoints(root, owner, history, target.name)
            return {"path": str(target), **manifest, "atomic": True, "includes_optimizer_rng_cursor": True,
                    "disk_free_before_bytes": free_bytes, "projected_checkpoint_bytes": projected_bytes,
                    "disk_reserve_bytes": self.config["checkpoint_disk_reserve_bytes"], "retention": deepcopy(history)}
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def _atomic_json(self, path, value):
        temporary = path.with_name("." + path.name + "-" + uuid.uuid4().hex)
        temporary.write_bytes(canonical(value) + b"\n")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _checkpoint_owner(self, root):
        marker = root / "checkpoint-owner.json"
        identity_sha = digest(self._run_state["identity"])
        if not marker.exists():
            require(not list(root.iterdir()), "checkpoint root is not empty and has no ownership binding")
            owner = {"format": "irisx/learning-checkpoint-owner-v1", "owner_token": uuid.uuid4().hex,
                     "identity_sha256": identity_sha}
            self._atomic_json(marker, owner)
            history = []
        else:
            require(not marker.is_symlink(), "checkpoint ownership symlink forbidden")
            owner = json.loads(marker.read_text())
            require(owner.get("format") == "irisx/learning-checkpoint-owner-v1" and
                    owner.get("identity_sha256") == identity_sha, "checkpoint root belongs to another training identity")
            history_path = root / "checkpoint-history.json"
            require(not history_path.is_symlink(), "checkpoint history symlink forbidden")
            history = json.loads(history_path.read_text()) if history_path.exists() else []
        # Recover only the explicitly committed latest pointer if a crash preceded
        # its history write; do not discover or delete arbitrary directory globs.
        latest = root / "latest.json"
        if latest.exists():
            require(not latest.is_symlink(), "latest checkpoint symlink forbidden")
            pointer = json.loads(latest.read_text())
            name = pointer["directory"]
            require(type(name) is str and Path(name).name == name and name.startswith("step-"), "unsafe latest checkpoint path")
            directory = root / name
            require(not directory.is_symlink() and directory.is_dir(), "latest checkpoint directory missing")
            manifest_path = directory / "manifest.json"
            require(not manifest_path.is_symlink() and hashlib.sha256(manifest_path.read_bytes()).hexdigest() == pointer["manifest_sha256"], "latest checkpoint manifest changed")
            manifest = json.loads(manifest_path.read_text())
            require(manifest.get("owner_token") == owner["owner_token"] and manifest["identity_sha256"] == identity_sha, "latest checkpoint owner differs")
            if not any(row["directory"] == name for row in history):
                history.append({"directory": name, "steps": manifest["steps"], "state_sha256": manifest["state_sha256"],
                                "manifest_sha256": pointer["manifest_sha256"], "status": "retained"})
        return owner, history

    def _prune_checkpoints(self, root, owner, history, latest):
        retained = [row for row in history if row["status"] == "retained"]
        for row in retained[:-self.config["checkpoint_keep"]]:
            name = row["directory"]
            require(type(name) is str and Path(name).name == name and name.startswith("step-") and name != latest, "unsafe checkpoint pruning target")
            directory = root / name
            require(not directory.is_symlink(), "checkpoint pruning symlink forbidden")
            if not directory.exists():
                row["status"] = "previously_owned_directory_absent"
                continue
            require(directory.is_dir() and {p.name for p in directory.iterdir()} == {"manifest.json", "state.pt"} and
                    all(not p.is_symlink() for p in directory.iterdir()), "unexpected checkpoint contents; refusing cleanup")
            manifest_path = directory / "manifest.json"
            require(hashlib.sha256(manifest_path.read_bytes()).hexdigest() == row["manifest_sha256"], "pruning manifest binding differs")
            manifest = json.loads(manifest_path.read_text())
            require(manifest["owner_token"] == owner["owner_token"] and manifest["identity_sha256"] == owner["identity_sha256"] and
                    manifest["state_sha256"] == row["state_sha256"], "pruning ownership binding differs")
            require(hashlib.sha256((directory / "state.pt").read_bytes()).hexdigest() == row["state_sha256"], "pruning state bytes changed")
            shutil.rmtree(directory)
            row["status"] = "pruned_after_durable_latest"
        self._atomic_json(root / "checkpoint-history.json", history)
        return history

    def load_checkpoint(self, checkpoint, *, identity, records_count):
        root = Path(checkpoint)
        require(not root.is_symlink(), "checkpoint symlink forbidden")
        manifest = json.loads((root / "manifest.json").read_text())
        file = root / "state.pt"
        require(not file.is_symlink() and file.stat().st_size == manifest["state_bytes"] and
                hashlib.sha256(file.read_bytes()).hexdigest() == manifest["state_sha256"], "checkpoint bytes changed")
        require(manifest["identity_sha256"] == digest(identity), "checkpoint model/source/data/config identity differs")
        payload = self.torch.load(file, map_location="cpu", weights_only=True)
        require(payload["format"] == "irisx/learning-lora-checkpoint-v1" and payload["identity"] == identity, "checkpoint identity differs")
        state = payload["run_state"]
        require(state["identity"] == identity and all(type(i) is int and 0 <= i < records_count for i in state["order"]) and
                0 <= state["cursor"] <= len(state["order"]) and state["order"] == self._order(records_count, state["epoch"]), "checkpoint data cursor/order differs")
        require(state["steps"] == state["attempted_steps"] == manifest["steps"], "checkpoint is not complete update boundary")
        require(set(payload["adapter"]) == set(self.parameters), "checkpoint adapter names differ")
        require(_state_fingerprint(payload["adapter"], self.torch)["sha256"] == manifest["adapter_sha256"] and
                _fingerprint_tree(payload["optimizer"], self.torch) == manifest["optimizer_sha256"] and
                _fingerprint_tree(payload["rng"], self.torch) == manifest["rng_sha256"], "checkpoint state fingerprints differ")
        with self.torch.no_grad():
            for name, parameter in self.parameters.items():
                require(list(parameter.shape) == list(payload["adapter"][name].shape), "checkpoint adapter shape differs")
                parameter.copy_(payload["adapter"][name].to(parameter.device))
        self._make_optimizer()
        self.optimizer.load_state_dict(payload["optimizer"])
        self.scheduler.load_state_dict(payload["scheduler"])
        self._set_rng(payload["rng"])
        self._run_state = state
        require(self.fingerprint()["sha256"] == manifest["adapter_sha256"] and
                _fingerprint_tree(self.optimizer.state_dict(), self.torch) == manifest["optimizer_sha256"], "restored weights/optimizer differ")
        self._publish_fingerprint()
        return {"loaded": True, "steps": state["steps"], "adapter_sha256": manifest["adapter_sha256"]}

    def export_adapter(self, output_dir):
        """Inference artifact is separate from complete restart checkpoint."""
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=False)
        self.model.save_pretrained(str(root), safe_serialization=True)
        self.native.tokenizer.save_pretrained(str(root))
        from peft import get_peft_model_state_dict
        from safetensors.torch import load_file
        expected = _state_fingerprint(get_peft_model_state_dict(self.model), self.torch)
        saved = _state_fingerprint(load_file(str(root / "adapter_model.safetensors"), device="cpu"), self.torch)
        require(expected == saved, "exported safetensors adapter differs from actual trained state")
        report = {"format": "irisx/learning-agent-adapter-v1", "model_identity": self._base_identity,
                  "adapter_sha256": self.fingerprint()["sha256"], "training_config_sha256": digest(self.config),
                  "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()},
                  "resume_capable": False, "same_process_state_saved": True, "saved_state_exact": True, "saved_adapter_sha256": saved["sha256"], "fresh_base_reload_verified": False}
        (root / "adapter-binding.json").write_bytes(canonical(report) + b"\n")
        return {"path": str(root), **report}

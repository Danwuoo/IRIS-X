"""Single-device Qwen LoRA, raw-token sampling and actual AF3 streamed updates.

No answer files, evaluator, packed cross-example attention or external API exists
in this module. Sampling/replay use the same temperature-one full vocabulary.
"""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
import math
from pathlib import Path
import re
import time

import torch
import torch.nn.functional as F

from tools.arc2_goal_sprint_20261017.af3 import AF3Trajectory, compute_group_loss
from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.ddis_loss import DDISLoss


class PhaseDeadline(RuntimeError):
    pass


def check_deadline(deadline):
    if time.time() >= deadline:
        raise PhaseDeadline("phase deadline reached")


def adapter_state(model):
    return {name: value.detach().cpu().clone() for name, value in model.named_parameters() if value.requires_grad}


def state_digest(state):
    h = hashlib.sha256()
    for name, value in sorted(state.items()):
        h.update(name.encode())
        h.update(str(tuple(value.shape)).encode())
        h.update(value.contiguous().view(torch.uint8).numpy().tobytes())
    return h.hexdigest()


def restore_state(model, state):
    named = {n: p for n, p in model.named_parameters() if p.requires_grad}
    if set(named) != set(state):
        raise ValueError("adapter inventory differs")
    if any(named[n].shape != v.shape or named[n].dtype != v.dtype
           or not bool(torch.isfinite(v).all()) for n, v in state.items()):
        raise ValueError("adapter tensor shape/dtype/finiteness differs")
    with torch.no_grad():
        for name, value in state.items():
            named[name].copy_(value.to(named[name].device, dtype=named[name].dtype))


def make_optimizer(model, lr):
    return torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01)


def tensor_inventory(state):
    return {name: {"shape": list(value.shape), "dtype": str(value.dtype),
                   "sha256": hashlib.sha256(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
            for name, value in sorted(state.items())}


def build_resume_manifest(root, *, expected_state_sha256, base_identity, origin):
    """Seal downloaded LoRA files without loading a base model or executing it.

    The conventional default-adapter key mapping is deliberately narrow. The
    reconstructed digest MUST match the independently sealed selected state;
    arbitrary adapters or guessed key remappings cannot pass this check.
    """
    from safetensors.torch import load
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("regular adapter directory required")
    files, bodies = {}, {}
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        path = root / name
        limit = 1024**3 if name.endswith("safetensors") else 8 * 1024**2
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError("regular bounded adapter file required")
        body = path.read_bytes()
        bodies[name] = body
        files[name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    exported = load(bodies["adapter_model.safetensors"])
    current = {}
    for name, value in exported.items():
        match = re.fullmatch(r"(.+\.lora_[AB])\.weight", name)
        if not match:
            raise ValueError("only explicit default LoRA A/B weight mapping is supported")
        current[match[1] + ".default.weight"] = value
    if (not current or len(current) != len(exported)
            or any(not bool(torch.isfinite(v).all()) for v in current.values())
            or state_digest(current) != expected_state_sha256):
        raise ValueError("downloaded adapter does not match sealed selected state")
    return {"format": "irisx/pre-public-adapter-v1", "base_identity": base_identity, "origin": origin,
            "files": files, "exported_tensors": tensor_inventory(exported),
            "trainable_tensors": tensor_inventory(current), "state_sha256": state_digest(current)}


def load_adapter_resume(engine, spec, *, base_identity):
    """Load only externally pinned, exact, pre-PUBLIC PEFT tensors or fail closed.

    base_identity must be injected by the admitted bootstrap after independently
    verifying the actual base shards/config/tokenizer material contract; it must
    not originate from the adapter manifest or a user-overridable tuning map.
    No checkpoint optimizer/RNG state is resumed. A new phase optimizer is fresh.
    All file/key/config/shape/dtype checks precede mutation, and a failed copy is
    rolled back to the initial adapter with a verified state hash.
    """
    from safetensors.torch import load
    from peft import get_peft_model_state_dict, set_peft_model_state_dict
    if not isinstance(spec, dict) or set(spec) != {"root", "manifest_sha256"}:
        raise ValueError("strict adapter resume configuration required")
    if not isinstance(base_identity, dict) or not base_identity:
        raise ValueError("independently verified base identity required")
    root = Path(spec["root"])
    if root.is_symlink() or not root.is_dir():
        raise ValueError("regular adapter resume directory required")
    expected_files = {"manifest.json", "adapter_config.json", "adapter_model.safetensors"}
    if {p.name for p in root.iterdir()} != expected_files:
        raise ValueError("exact resume file inventory required")
    bodies = {}
    for name in expected_files:
        path = root / name
        limit = 1024**3 if name.endswith("safetensors") else 8 * 1024**2
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError("regular bounded resume file required")
        bodies[name] = path.read_bytes()
    if (not isinstance(spec["manifest_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", spec["manifest_sha256"])
            or hashlib.sha256(bodies["manifest.json"]).hexdigest() != spec["manifest_sha256"]):
        raise ValueError("adapter manifest SHA differs")
    manifest = json.loads(bodies["manifest.json"])
    canonical_manifest = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode() + b"\n"
    if bodies["manifest.json"] != canonical_manifest:
        raise ValueError("canonical adapter manifest required")
    if (set(manifest) != {"format", "base_identity", "origin", "files", "exported_tensors", "trainable_tensors", "state_sha256"}
            or manifest["format"] != "irisx/pre-public-adapter-v1"
            or manifest["base_identity"] != base_identity):
        raise ValueError("adapter schema or base identity differs")
    origin = manifest["origin"]
    if (not isinstance(origin, dict) or set(origin) != {"run_id", "source_sha256", "phase", "public_ttt_applied", "public_labels_used",
                                                     "run_summary_sha256", "provider_record_sha256"}
            or not isinstance(origin["run_id"], str) or not origin["run_id"]
            or any(not isinstance(origin[k], str) or not re.fullmatch(r"[a-f0-9]{64}", origin[k])
                   for k in ("source_sha256", "run_summary_sha256", "provider_record_sha256"))
            or origin["phase"] != "pre_public" or origin["public_ttt_applied"] is not False
            or origin["public_labels_used"] is not False):
        raise ValueError("pre-PUBLIC training-only origin required")
    expected = {name: {"bytes": len(bodies[name]), "sha256": hashlib.sha256(bodies[name]).hexdigest()}
                for name in expected_files - {"manifest.json"}}
    if manifest["files"] != expected:
        raise ValueError("adapter file SHA or byte inventory differs")
    config = json.loads(bodies["adapter_config.json"])
    actual_config = json.loads(json.dumps(engine.model.peft_config["default"].to_dict(), default=lambda v: sorted(v)))
    if set(config) != set(actual_config):
        raise ValueError("adapter LoRA configuration key inventory differs")
    # save_pretrained flips inference_mode and stores a relocatable base path.
    # The independent material identity above, not that path, binds the base.
    for field in ("base_model_name_or_path", "inference_mode"):
        config.pop(field, None)
        actual_config.pop(field, None)
    for fields in (config, actual_config):
        if isinstance(fields.get("target_modules"), list):
            fields["target_modules"] = sorted(fields["target_modules"])
    if config != actual_config:
        raise ValueError("adapter LoRA configuration differs")
    exported = load(bodies["adapter_model.safetensors"])
    current_export = get_peft_model_state_dict(engine.model)
    if (not exported or set(exported) != set(current_export)
            or any(v.shape != current_export[n].shape or v.dtype != current_export[n].dtype
                   or not bool(torch.isfinite(v).all()) for n, v in exported.items())
            or tensor_inventory(exported) != manifest["exported_tensors"]):
        raise ValueError("adapter exported tensor inventory differs")
    before = adapter_state(engine.model)
    if (set(manifest["trainable_tensors"]) != set(before)
            or any(row.get("shape") != list(before[n].shape) or row.get("dtype") != str(before[n].dtype)
                   for n, row in manifest["trainable_tensors"].items())):
        raise ValueError("adapter trainable tensor inventory differs")
    before_hash = state_digest(before)
    try:
        set_peft_model_state_dict(engine.model, exported)
        resumed = adapter_state(engine.model)
        if (state_digest(resumed) != manifest["state_sha256"]
                or tensor_inventory(resumed) != manifest["trainable_tensors"]):
            raise ValueError("resumed adapter state digest or tensor inventory differs")
    except BaseException:
        restore_state(engine.model, before)
        if state_digest(adapter_state(engine.model)) != before_hash:
            raise RuntimeError("failed resume did not restore initial adapter")
        raise
    return {"manifest_sha256": spec["manifest_sha256"], "state_sha256": manifest["state_sha256"],
            "base_identity": base_identity, "origin": origin, "tensor_count": len(exported),
            "optimizer_resumed": False, "rng_resumed": False}


class Engine:
    def __init__(self, model, tokenizer, *, device=None):
        self.model = model
        self.tokenizer = tokenizer
        self.device = torch.device(device or next(model.parameters()).device)
        self.parameters = [p for p in model.parameters() if p.requires_grad]
        self.forward_calls = 0
        self.sampled_tokens = 0
        self.optimizer_steps = 0
        self.optimizer_attempts = 0

    @classmethod
    def load(cls, path, *, rank=16, alpha=32, device="cuda"):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model
        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
        model = AutoModelForCausalLM.from_pretrained(path, local_files_only=True, trust_remote_code=False,
                    dtype=torch.bfloat16, attn_implementation="sdpa", device_map={"": device})
        model.config.use_cache = False
        model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=alpha, lora_dropout=0.0,
                    bias="none", task_type="CAUSAL_LM",
                    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
        for param in model.parameters():
            if param.requires_grad:
                param.data = param.data.float()
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        return cls(model, tokenizer, device=device)

    def sync(self):
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)

    def autocast(self):
        return torch.autocast("cuda", dtype=torch.bfloat16) if self.device.type == "cuda" else nullcontext()

    def completion_logps(self, ids, prompt_length):
        if not 0 < prompt_length < len(ids):
            raise ValueError("nonempty prompt and completion required")
        self.model.train()
        tokens = torch.tensor([ids], dtype=torch.long, device=self.device)
        positions = torch.arange(prompt_length - 1, len(ids) - 1, device=self.device)
        with self.autocast():
            out = self.model(input_ids=tokens, attention_mask=torch.ones_like(tokens),
                             use_cache=False, logits_to_keep=positions)
        self.forward_calls += 1
        logits = out.logits[0].float()
        targets = tokens[0, prompt_length:]
        selected = logits.gather(-1, targets[:, None]).squeeze(-1) - torch.logsumexp(logits, dim=-1)
        if not bool(torch.isfinite(selected).all()):
            raise FloatingPointError("nonfinite model log probabilities")
        return torch.cat((selected.new_zeros(prompt_length), selected))

    def masked_logps(self, ids, mask):
        if (len(mask) != len(ids) or not mask or mask[0] != 0
                or any(type(v) is not int or v not in (0, 1) for v in mask) or not any(mask)):
            raise ValueError("nonempty binary causal supervision mask required")
        selected = torch.tensor([i for i, value in enumerate(mask) if value], device=self.device)
        tokens = torch.tensor([ids], dtype=torch.long, device=self.device)
        self.model.train()
        with self.autocast():
            out = self.model(input_ids=tokens, attention_mask=torch.ones_like(tokens),
                             use_cache=False, logits_to_keep=selected - 1)
        self.forward_calls += 1
        logits = out.logits[0].float()
        values = logits.gather(-1, tokens[0, selected, None]).squeeze(-1) - torch.logsumexp(logits, -1)
        if not bool(torch.isfinite(values).all()):
            raise FloatingPointError("nonfinite masked log probabilities")
        return values

    def commit(self, optimizer):
        gradients = [p.grad for p in self.parameters if p.grad is not None]
        if not gradients or any(not bool(torch.isfinite(g).all()) for g in gradients):
            optimizer.zero_grad(set_to_none=True)
            raise FloatingPointError("missing or nonfinite adapter gradients")
        norm = torch.nn.utils.clip_grad_norm_(self.parameters, 1.0, error_if_nonfinite=True)
        if norm.item() == 0:
            optimizer.zero_grad(set_to_none=True)
            return {"updated": False, "gradient_norm": 0.0, "reason": "zero_gradient"}
        self.optimizer_attempts += 1
        optimizer.step()
        if any(not bool(torch.isfinite(p).all()) for p in self.parameters):
            raise FloatingPointError("nonfinite adapter after optimizer step")
        self.optimizer_steps += 1
        optimizer.zero_grad(set_to_none=True)
        return {"updated": True, "gradient_norm": norm.item()}

    def sft_step(self, example, optimizer, *, deadline=math.inf):
        check_deadline(deadline)
        ids = example["prompt_ids"] + example["completion_ids"]
        optimizer.zero_grad(set_to_none=True)
        if "loss_mask" in example:
            logps = self.masked_logps(ids, example["loss_mask"])
            loss = -logps.mean()
        else:
            logps = self.completion_logps(ids, len(example["prompt_ids"]))
            loss = -logps[len(example["prompt_ids"]):].mean()
        loss.backward()
        check_deadline(deadline)
        report = self.commit(optimizer)
        return {**report, "loss": loss.item(), "tokens": len(ids),
                "completion_tokens": len(example["completion_ids"]), "demos_dropped": example["demos_dropped"],
                "supervised_tokens": sum(example["loss_mask"]) if "loss_mask" in example else len(example["completion_ids"]),
                "loss_mode": example.get("loss_mode", "final")}

    @torch.no_grad()
    def nll(self, example):
        self.model.eval()
        # Disable checkpoint recomputation through no_grad; identical dropout-zero model.
        ids = example["prompt_ids"] + example["completion_ids"]
        value = self.completion_logps(ids, len(example["prompt_ids"]))
        return -value[len(example["prompt_ids"]):].mean().item()

    @torch.no_grad()
    def candidate_log_likelihood(self, example, *, normalization="sum", deadline=math.inf):
        if normalization not in {"sum", "token_mean"}:
            raise ValueError("invalid likelihood normalization")
        check_deadline(deadline)
        ids = example["prompt_ids"] + example["completion_ids"]
        values = self.completion_logps(ids, len(example["prompt_ids"]))[len(example["prompt_ids"]):]
        check_deadline(deadline)
        return (values.sum() if normalization == "sum" else values.mean()).item()

    @torch.no_grad()
    def generate(self, prompt_ids, *, count=1, max_new_tokens=2048, sample=False, deadline=math.inf):
        """Only retain sampled token log-probabilities, not vocabulary-sized scores.

        All sequences share one prompt. Finished trajectories keep their original
        raw tokens; batched filler is not retained or assigned a reward.
        """
        if not prompt_ids or count < 1 or max_new_tokens < 1:
            raise ValueError("nonempty prompt/count/token bound required")
        check_deadline(deadline)
        self.model.eval()
        tokens = torch.tensor([prompt_ids] * count, device=self.device, dtype=torch.long)
        attention = torch.ones_like(tokens)
        cache = None
        generated = [[] for _ in range(count)]
        logps = [[] for _ in range(count)]
        finished = [False] * count
        eos = self.tokenizer.eos_token_id
        # Qwen chat may expose several EOS IDs through generation_config.
        configured = getattr(self.model.generation_config, "eos_token_id", None)
        endings = {x for x in ([configured] if isinstance(configured, int) else configured or [])}
        if eos is not None:
            endings.add(eos)
        stop_ids = self.tokenizer.encode("</grid>", add_special_tokens=False)
        try:
            for step in range(max_new_tokens):
                check_deadline(deadline)
                with self.autocast():
                    out = self.model(input_ids=tokens, attention_mask=attention, past_key_values=cache,
                                     use_cache=True, logits_to_keep=1)
                self.forward_calls += 1
                cache = out.past_key_values
                logits = out.logits[:, -1, :].float()
                if not bool(torch.isfinite(logits).all()):
                    raise FloatingPointError("nonfinite rollout logits")
                probs = F.softmax(logits, dim=-1)
                selected = torch.multinomial(probs, 1) if sample else logits.argmax(-1, keepdim=True)
                chosen_logps = logits.gather(1, selected).squeeze(1) - torch.logsumexp(logits, -1)
                selected_list = selected[:, 0].tolist()
                for i, token in enumerate(selected_list):
                    if not finished[i]:
                        generated[i].append(token)
                        logps[i].append(chosen_logps[i].item())
                        self.sampled_tokens += 1
                        if token in endings or (stop_ids and generated[i][-len(stop_ids):] == stop_ids):
                            finished[i] = True
                if all(finished):
                    break
                tokens = selected
                attention = torch.cat((attention, attention.new_ones((count, 1))), dim=1)
            return [{"input_ids": prompt_ids + generated[i], "prompt_length": len(prompt_ids),
                     "behavior_log_probs": [0.0] * len(prompt_ids) + logps[i],
                     "text": self.tokenizer.decode(generated[i], skip_special_tokens=True),
                     "completion_tokens": len(generated[i]),
                     "stop": "completed" if finished[i] else "length"} for i in range(count)]
        finally:
            del cache

    @torch.no_grad()
    def generate_prompts(self, prompts, *, max_new_tokens=2048, deadline=math.inf):
        """Greedy heterogeneous prompt batch, only for opt-in PUBLIC views.

        Left padding is invisible to each row's attention and rotary positions.
        This does not replace the original RL sampler or its probability measure.
        A failed/late batch returns no candidates; the caller owns bounded retry
        and retains its physical work. No GPU speedup or bitwise CUDA parity is
        implied by this implementation.
        """
        vocab = self.model.config.vocab_size
        if (not isinstance(prompts, (list, tuple)) or not 1 <= len(prompts) <= 8
                or any(not isinstance(p, (list, tuple)) or not p
                       or any(type(t) is not int or not 0 <= t < vocab for t in p) for p in prompts)
                or type(max_new_tokens) is not int or max_new_tokens < 1):
            raise ValueError("bounded nonempty original prompt token lists required")
        prompts = [list(p) for p in prompts]
        check_deadline(deadline)
        self.model.eval()
        eos = self.tokenizer.eos_token_id
        pad = getattr(self.tokenizer, "pad_token_id", None)
        pad = pad if pad is not None else eos if eos is not None else 0
        if type(pad) is not int or not 0 <= pad < vocab:
            raise ValueError("valid in-vocabulary padding token required")
        count, width = len(prompts), max(map(len, prompts))
        lengths = [len(p) for p in prompts]
        tokens = torch.tensor([[pad] * (width - len(p)) + p for p in prompts], device=self.device)
        attention = torch.tensor([[0] * (width - len(p)) + [1] * len(p) for p in prompts], device=self.device)
        positions = (attention.cumsum(-1) - 1).clamp(min=0)
        cache = out = logits = selected = None
        generated, logps = [[] for _ in prompts], [[] for _ in prompts]
        finished = [False] * count
        configured = getattr(self.model.generation_config, "eos_token_id", None)
        endings = set([configured] if isinstance(configured, int) else configured or [])
        if eos is not None:
            endings.add(eos)
        stop_ids = self.tokenizer.encode("</grid>", add_special_tokens=False)
        try:
            for step in range(max_new_tokens):
                check_deadline(deadline)
                with self.autocast():
                    out = self.model(input_ids=tokens, attention_mask=attention, position_ids=positions,
                                     past_key_values=cache, use_cache=True, logits_to_keep=1)
                self.forward_calls += 1
                cache = out.past_key_values
                logits = out.logits[:, -1, :].float()
                if not bool(torch.isfinite(logits).all()):
                    raise FloatingPointError("nonfinite batched view logits")
                selected = logits.argmax(-1, keepdim=True)
                selected_list = selected[:, 0].tolist()
                chosen_logps = (logits.gather(1, selected).squeeze(1) - torch.logsumexp(logits, -1)).tolist()
                # Charge tokens before checking time: rejected late work was real.
                self.sampled_tokens += sum(not done for done in finished)
                check_deadline(deadline)
                for i, token in enumerate(selected_list):
                    if not finished[i]:
                        generated[i].append(token)
                        logps[i].append(chosen_logps[i])
                        if token in endings or (stop_ids and generated[i][-len(stop_ids):] == stop_ids):
                            finished[i] = True
                if all(finished):
                    break
                tokens = selected
                attention = torch.cat((attention, attention.new_ones((count, 1))), dim=1)
                positions = torch.tensor([[length + step] for length in lengths], device=self.device)
            result = [{"input_ids": prompts[i] + generated[i], "prompt_length": lengths[i],
                       "behavior_log_probs": [0.0] * lengths[i] + logps[i],
                       "text": self.tokenizer.decode(generated[i], skip_special_tokens=True),
                       "completion_tokens": len(generated[i]),
                       "stop": "completed" if finished[i] else "length"} for i in range(count)]
            check_deadline(deadline)
            return result
        finally:
            # Release GPU owners even while an OOM traceback is being audited.
            cache = out = logits = selected = tokens = attention = positions = None

    def af3_update(self, rows, optimizer, *, expected_groups, group_size, deadline=math.inf):
        """Plan complete groups then stream actual upstream DDIS graphs one at a time.

        No optimizer step until every nonzero-advantage trajectory has replayed
        and backpropagated. Zero-signal samples remain in physical diagnostics.
        """
        groups = {}
        for row in rows:
            groups.setdefault(row["group_id"], []).append(row)
        if set(groups) != set(expected_groups) or any(len(v) != group_size for v in groups.values()):
            raise ValueError("complete planned rollout batch required")
        ids = [row["sample_id"] for row in rows]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate physical trajectory")
        # This lightweight graph validates the shared adapter and obtains actual
        # upstream TrainingSamples/divisors; no model replay graphs are retained.
        small = []
        for row in rows:
            old = torch.tensor(row["behavior_log_probs"], device=self.device)
            mask = torch.tensor([0] * row["prompt_length"] + [1] * row["completion_tokens"], device=self.device)
            small.append(AF3Trajectory(row["sample_id"], row["group_id"], row["input_ids"],
                         old.clone().requires_grad_(), old, mask, row["reward"]))
        plan = compute_group_loss(small)
        samples, mixed = plan.samples, plan.mixed_groups
        del plan, small
        optimizer.zero_grad(set_to_none=True)
        if not mixed:
            return {"updated": False, "reason": "zero_reward_signal", "mixed_groups": 0,
                    "physical_trajectories": len(rows), "replayed": 0}
        loss_sum = 0.0
        max_gap = 0.0
        unclipped, tokens, replayed = 0, 0, 0
        loss_fn = DDISLoss(eps_low=.2, eps_high=.2, use_opsm=False, entropy_top_pct=None)
        try:
            for row, sample in zip(rows, samples):
                check_deadline(deadline)
                if not any(sample.advantages):
                    continue
                current = self.completion_logps(sample.input_ids, row["prompt_length"])
                mask = torch.tensor(sample.completion_mask, device=self.device, dtype=torch.float32)
                old = torch.tensor(sample.gen_logprobs, device=self.device)
                advantages = torch.tensor(sample.advantages, device=self.device)
                loss = loss_fn.compute_unpacked(log_probs=[current], completion_mask=[mask],
                         advantages=[advantages], divisors=torch.tensor([sample.divisor], device=self.device),
                         gen_log_probs=[old]).loss_unscaled
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("nonfinite AF3 loss")
                with torch.no_grad():
                    gap = (current - old)[mask.bool()]
                    max_gap = max(max_gap, gap.abs().max().item())
                    ratio = gap.clamp(-20, 20).exp()
                    unclipped += int(((ratio > .8) & (ratio < 1.2)).sum().item())
                    tokens += gap.numel()
                loss_sum += loss.item()
                loss.backward()
                replayed += 1
                del loss, current, mask, old, advantages
            check_deadline(deadline)
            report = self.commit(optimizer)
            return {**report, "mixed_groups": mixed, "physical_trajectories": len(rows),
                    "replayed": replayed, "loss": loss_sum, "max_replay_logp_gap": max_gap,
                    "unclipped_fraction": unclipped / tokens if tokens else None,
                    "probability_measure": "full-vocabulary-temperature-one"}
        except BaseException:
            optimizer.zero_grad(set_to_none=True)
            raise

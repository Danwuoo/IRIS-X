"""Single-device Qwen LoRA, raw-token sampling and actual AF3 streamed updates.

No answer files, evaluator, packed cross-example attention or external API exists
in this module. Sampling/replay use the same temperature-one full vocabulary.
"""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
import math
from pathlib import Path
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
    with torch.no_grad():
        for name, value in state.items():
            named[name].copy_(value.to(named[name].device, dtype=named[name].dtype))


def make_optimizer(model, lr):
    return torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01)


class Engine:
    def __init__(self, model, tokenizer, *, device=None):
        self.model = model
        self.tokenizer = tokenizer
        self.device = torch.device(device or next(model.parameters()).device)
        self.parameters = [p for p in model.parameters() if p.requires_grad]
        self.forward_calls = 0
        self.sampled_tokens = 0
        self.optimizer_steps = 0

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

    def commit(self, optimizer):
        gradients = [p.grad for p in self.parameters if p.grad is not None]
        if not gradients or any(not bool(torch.isfinite(g).all()) for g in gradients):
            optimizer.zero_grad(set_to_none=True)
            raise FloatingPointError("missing or nonfinite adapter gradients")
        norm = torch.nn.utils.clip_grad_norm_(self.parameters, 1.0, error_if_nonfinite=True)
        if norm.item() == 0:
            optimizer.zero_grad(set_to_none=True)
            return {"updated": False, "gradient_norm": 0.0, "reason": "zero_gradient"}
        optimizer.step()
        if any(not bool(torch.isfinite(p).all()) for p in self.parameters):
            raise FloatingPointError("nonfinite adapter after optimizer step")
        self.optimizer_steps += 1
        optimizer.zero_grad(set_to_none=True)
        return {"updated": True, "gradient_norm": norm.item()}

    def sft_step(self, example, optimizer):
        ids = example["prompt_ids"] + example["completion_ids"]
        optimizer.zero_grad(set_to_none=True)
        logps = self.completion_logps(ids, len(example["prompt_ids"]))
        loss = -logps[len(example["prompt_ids"]):].mean()
        loss.backward()
        report = self.commit(optimizer)
        return {**report, "loss": loss.item(), "tokens": len(ids),
                "completion_tokens": len(example["completion_ids"]), "demos_dropped": example["demos_dropped"]}

    @torch.no_grad()
    def nll(self, example):
        self.model.eval()
        # Disable checkpoint recomputation through no_grad; identical dropout-zero model.
        ids = example["prompt_ids"] + example["completion_ids"]
        value = self.completion_logps(ids, len(example["prompt_ids"]))
        return -value[len(example["prompt_ids"]):].mean().item()

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

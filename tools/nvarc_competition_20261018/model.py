"""Frozen v2 demo-only SFT engine primitives; no offline training or RL."""
from contextlib import nullcontext
import hashlib, math, time
import torch
import torch.nn.functional as F

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

"""CPU-testable RLVR mathematics, deliberately disconnected from any runtime.

No model, rollout, reward environment, checkpoint or provider integration lives
here. The caller must supply aligned original tokens and actual behavior log-mu.
The DDIS formula is independently expressed from agent-factory-3 at commit
a1836decb836cd52cf2b27f5022f6838cee75df3. No upstream source is executed.
"""
from __future__ import annotations

import math
import torch


def need(condition, message):
    if not condition:
        raise ValueError(message)


def masked_log_probs(logits, allowed, *, temperature=1.0):
    """The actual DFA-conditioned distribution, not full-vocabulary NLL.

    Top-p is intentionally absent: this initial mathematical contract admits
    only full-support sampling within the supplied legal-token mask.
    """
    need(type(temperature) in (int, float) and math.isfinite(temperature)
         and temperature > 0, "positive finite temperature required")
    need(math.isfinite(1.0 / temperature) and 1.0 / temperature <= torch.finfo(torch.float32).max,
         "inverse temperature exceeds float32 derivative range")
    need(torch.is_tensor(logits) and logits.ndim in (1, 2)
         and logits.is_floating_point(), "one or two dimensional logits required")
    need(torch.is_tensor(allowed) and allowed.dtype == torch.bool
         and allowed.shape == logits.shape and allowed.device == logits.device,
         "exact boolean legal-token mask required")
    need(bool(torch.isfinite(logits).all()), "nonfinite logits")
    need(bool(allowed.any(dim=-1).all()), "empty legal-token support")
    converted = logits.float()
    need(bool(torch.isfinite(converted).all()), "logits exceed float32 computation range")
    scaled = converted / temperature
    need(bool(torch.isfinite(scaled).all()), "scaled logits exceed float32 computation range")
    logp = torch.log_softmax(scaled.masked_fill(~allowed, -torch.inf), dim=-1)
    need(bool(torch.isfinite(logp[allowed]).all()), "legal log probabilities exceed computation range")
    return logp


def sample_masked(logits, allowed, *, generator, temperature=1.0):
    """Sample one action and retain its exact cached-actor log probability."""
    need(torch.is_tensor(logits) and logits.ndim == 1, "single sampling step required")
    logp = masked_log_probs(logits.detach(), allowed, temperature=temperature)
    token = int(torch.multinomial(logp.exp(), 1, generator=generator).item())
    return token, float(logp[token].item())


def selected_log_probs(logits, allowed, tokens, *, temperature=1.0):
    """Differentiable target-policy probabilities for exact supplied tokens.

    This checks masks and token IDs, not model-prefix alignment. That independent
    actor/teacher-forcing check remains required before any production update.
    """
    need(torch.is_tensor(logits) and logits.ndim == 2 and torch.is_tensor(tokens) and tokens.dtype == torch.long
         and tokens.shape == (logits.shape[0],) and tokens.device == logits.device,
         "exact token/position alignment required")
    need(bool(((tokens >= 0) & (tokens < logits.shape[1])).all()), "token outside vocabulary")
    logp = masked_log_probs(logits, allowed, temperature=temperature)
    need(bool(allowed.gather(1, tokens[:, None]).all()), "recorded token outside actor support")
    return logp.gather(1, tokens[:, None])[:, 0]


def reward_groups(rewards, groups, eligible, policy_versions):
    """Exact binary rewards, group-centered advantages, all groups reported.

    Infrastructure exclusions are supplied explicitly, never inferred from a
    zero reward. A zero-variance group stays in reporting but has no update.
    """
    need(torch.is_tensor(rewards) and rewards.ndim == 1 and rewards.is_floating_point(),
         "one-dimensional floating rewards required")
    n = rewards.numel()
    need(type(groups) in (list, tuple) and len(groups) == n
         and all(type(g) is str and g for g in groups), "explicit group IDs required")
    need(torch.is_tensor(eligible) and eligible.dtype == torch.bool and eligible.shape == rewards.shape
         and eligible.device == rewards.device, "explicit eligibility mask required")
    need(type(policy_versions) in (list, tuple) and len(policy_versions) == n
         and all(type(v) is str and v for v in policy_versions), "explicit actor versions required")
    need(bool(torch.isfinite(rewards).all()) and bool(((rewards == 0) | (rewards == 1)).all()),
         "finite binary exact rewards only")
    need(len({policy_versions[i] for i in range(n) if bool(eligible[i])}) <= 1,
         "initial synchronous batch cannot mix actor versions")
    advantage = torch.zeros(n, dtype=torch.float32, device=rewards.device)
    sizes = torch.ones(n, dtype=torch.int64, device=rewards.device)
    rows = []
    for group in dict.fromkeys(groups):
        members = [i for i, g in enumerate(groups) if g == group]
        used = [i for i in members if bool(eligible[i])]
        need(len({policy_versions[i] for i in used}) <= 1,
             "initial synchronous group cannot mix actor versions")
        total = int((rewards[used] == 1).sum(dtype=torch.int64).item()) if used else 0
        count = len(used)
        mixed = 0 < total < count
        if count:
            advantage[used] = rewards[used].detach().float() - total / count
            sizes[used] = count
        rows.append({"group": group, "total": len(members), "eligible": count,
                     "infrastructure_excluded": len(members)-count,
                     "successes": int(total), "mean_reward": total/count if count else None,
                     "mixed": mixed, "all_zero": count > 0 and total == 0,
                     "all_one": count > 0 and total == count})
    return advantage.detach(), sizes.detach(), rows


def ddis_loss(log_pi, log_mu, assistant_mask, rewards, groups, eligible, policy_versions,
              *, eps_low=.2, eps_high=.28):
    """Group-relative, equal-sequence-weighted DDIS with strict clipping bounds.

    Mixed groups alone determine the loss normalizer, matching zero-variance
    group filtering, while diagnostics keep all submitted groups. No advantage
    standardization, OPSM, entropy mask, critic or reference KL is implied.
    """
    need(type(eps_low) in (int, float) and math.isfinite(eps_low) and 0 <= eps_low < 1
         and type(eps_high) in (int, float) and math.isfinite(eps_high) and eps_high >= 0,
         "finite clipping bounds required")
    need(torch.is_tensor(log_pi) and log_pi.ndim == 2 and log_pi.is_floating_point(),
         "batch by token target log probabilities required")
    need(torch.is_tensor(log_mu) and log_mu.shape == log_pi.shape and log_mu.device == log_pi.device
         and log_mu.is_floating_point(), "aligned behavior log probabilities required")
    need(torch.is_tensor(assistant_mask) and assistant_mask.dtype == torch.bool
         and assistant_mask.shape == log_pi.shape and assistant_mask.device == log_pi.device,
         "exact generated-assistant mask required")
    need(torch.is_tensor(rewards) and rewards.shape == (log_pi.shape[0],) and rewards.device == log_pi.device,
         "reward batch differs")
    need(bool(torch.isfinite(log_pi).all()) and bool(torch.isfinite(log_mu).all())
         and bool((log_pi <= 1e-6).all()) and bool((log_mu <= 1e-6).all()),
         "finite nonpositive log probabilities required")
    advantage, group_sizes, rows = reward_groups(rewards, groups, eligible, policy_versions)
    count = assistant_mask.sum(dim=1)
    need(bool((count[eligible] > 0).all()), "eligible trajectory has no generated assistant tokens")
    mask = assistant_mask & eligible[:, None]
    target = log_pi.float()
    behavior = log_mu.detach().float()
    need(bool(torch.isfinite(target).all()) and bool(torch.isfinite(behavior).all()),
         "log probabilities exceed float32 computation range")
    ratio = torch.exp(torch.where(mask, (target-behavior).clamp(-20, 20), torch.zeros_like(target)))
    inside = (ratio > 1-eps_low) & (ratio < 1+eps_high)
    effective = mask & inside
    mixed = sum(row['mixed'] for row in rows)
    divisor = group_sizes.float() * count.clamp_min(1).float() * max(1, mixed)
    per_sequence = -(ratio.detach() * advantage[:, None].float() * target * effective).sum(dim=1)
    loss = (per_sequence / divisor).sum()
    need(bool(torch.isfinite(loss)), "nonfinite loss")
    total_tokens = int(mask.sum().item())
    diagnostics = {"groups": rows, "mixed_groups": mixed,
                   "assistant_tokens": total_tokens,
                   "clipped_tokens": int((mask & ~inside).sum().item()),
                   "effective_tokens": int(effective.sum().item()),
                   "effective_tokens_meaning": "unclipped eligible mask coverage, including zero-advantage groups",
                   "contributing_tokens": int((effective & (advantage[:, None] != 0)).sum().item()),
                   "objective": "group-centered-equal-sequence-ddis",
                   "ratio_min": float(ratio[mask].min().item()) if total_tokens else None,
                   "ratio_max": float(ratio[mask].max().item()) if total_tokens else None,
                   "normalizer": "mixed_groups*eligible_group_size*assistant_sequence_length",
                   "production_update_authorized": False}
    return loss, diagnostics

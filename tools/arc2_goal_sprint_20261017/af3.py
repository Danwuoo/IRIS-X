"""Device-preserving, synchronous adapter for the actual upstream AF3 DDIS loss.

The upstream implementation is unmodified at commit
``a1836decb836cd52cf2b27f5022f6838cee75df3``. Its Apache-2.0 license and NOTICE
remain in ``tools/arc2_agent_factory3_bridge_20261014/vendor``. This module is
new IRIS-X glue, not the upstream asynchronous training framework.

Contract: one raw-token, un-packed trajectory per item. All vectors align with
``input_ids``: element i is log P(input_ids[i] | input_ids[:i]), including a
masked placeholder at position zero. The mask is a prompt-zero/completion-one
suffix. Sampling and replay must both use full-vocabulary softmax, temperature
one, without top-k/top-p/DFA filtering. This adapter validates declared tensors,
not the model, tokenizer, sampling measure, reward provenance or policy version.

Gradients and loss stay on the supplied device; only detached metadata is
materialized as Python lists for upstream TrainingSample. The caller owns
backward, optimizer commit, numerical replay admission and batch completeness.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import torch

from tools.arc2_agent_factory3_bridge_20261014.vendor.types import TrainingSample
from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.ddis_loss import DDISLoss
from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.metric_state import MeanMetricState


UPSTREAM_COMMIT = "a1836decb836cd52cf2b27f5022f6838cee75df3"


@dataclass(frozen=True)
class AF3Trajectory:
    sample_id: str
    group_id: str
    input_ids: Sequence[int]
    train_log_probs: torch.Tensor
    behavior_log_probs: torch.Tensor
    completion_mask: torch.Tensor
    reward: float


@dataclass(frozen=True)
class AF3LossResult:
    loss: torch.Tensor | None
    should_update: bool
    reason: str
    samples: tuple[TrainingSample, ...]
    metric_states: dict[str, MeanMetricState]
    group_summaries: tuple[dict, ...]

    @property
    def mixed_groups(self) -> int:
        """Groups with nonzero relative reward signal, not only binary rewards."""
        return sum(group["has_signal"] for group in self.group_summaries)


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _epsilon(value: float, name: str, *, lower: bool = False) -> float:
    _need(type(value) in (int, float), f"{name} must be a finite number")
    value = float(value)
    _need(math.isfinite(value) and value >= 0, f"{name} must be finite and nonnegative")
    if lower:
        _need(value <= 1, "eps_low must not exceed one")
    _need(value <= torch.finfo(torch.float32).max - 1, f"{name} exceeds float32 range")
    return value


def compute_group_loss(
    trajectories: Sequence[AF3Trajectory],
    *,
    eps_low: float = 0.2,
    eps_high: float = 0.2,
) -> AF3LossResult:
    """Group-center rewards and call upstream DDIS with sequence-token means.

    The divisor is M * group_size * completion_length, where M is the number
    of signal-bearing groups. Equal-reward groups remain in the returned
    samples/diagnostics, but contribute zero. This matches AF3's group-filtered
    sequence-token-mean objective, without silently discarding missing samples.
    The caller must supply every planned valid trajectory; this function cannot
    infer a missing rollout from a partial list. Each group requires >=2 items.

    A completely zero-signal batch returns loss=None without invoking upstream
    loss or requiring autograd. Fully clipped signal returns the upstream zero
    loss and should_update=False. Behavior probabilities are always detached.
    No entropy masking, OPSM, reference KL, std-normalization or stale-policy
    filtering is applied. Epsilon defaults are DDISLoss's own .2/.2 defaults.
    """
    eps_low = _epsilon(eps_low, "eps_low", lower=True)
    eps_high = _epsilon(eps_high, "eps_high")
    _need(isinstance(trajectories, (list, tuple)) and len(trajectories) > 0,
          "provide a nonempty list or tuple of trajectories")
    groups: dict[str, list[int]] = {}
    ids: set[str] = set()
    device = None
    counts: list[int] = []
    rewards: list[float] = []
    masks: list[torch.Tensor] = []
    behavior: list[torch.Tensor] = []
    for index, item in enumerate(trajectories):
        _need(isinstance(item, AF3Trajectory), "expected AF3Trajectory")
        _need(isinstance(item.sample_id, str) and bool(item.sample_id) and item.sample_id not in ids,
              "sample IDs must be nonempty and unique")
        ids.add(item.sample_id)
        _need(isinstance(item.group_id, str) and bool(item.group_id), "group ID must be nonempty")
        _need(isinstance(item.input_ids, (list, tuple)) and len(item.input_ids) >= 2 and
              all(type(token) is int and 0 <= token < 2**63 for token in item.input_ids),
              "input_ids must contain original nonnegative integer tokens")
        vectors = (item.train_log_probs, item.behavior_log_probs, item.completion_mask)
        _need(all(isinstance(tensor, torch.Tensor) for tensor in vectors), "all aligned vectors must be tensors")
        _need(all(tensor.ndim == 1 and tensor.numel() == len(item.input_ids) for tensor in vectors),
              "one-dimensional vectors must match the complete original token sequence")
        if device is None:
            device = item.train_log_probs.device
        _need(all(tensor.device == device for tensor in vectors), "all trajectories and vectors must share a device")
        _need(all(tensor.layout == torch.strided for tensor in vectors), "dense strided vectors required")
        for label, tensor in (("train", item.train_log_probs), ("behavior", item.behavior_log_probs)):
            _need(tensor.is_floating_point(), f"{label} log probabilities must be floating point")
            _need(bool(torch.isfinite(tensor).all().item()), f"{label} log probabilities must be finite")
            _need(bool(torch.isfinite(tensor.float()).all().item()), f"{label} log probabilities exceed float32 range")
            _need(bool((tensor <= 1e-6).all().item()), f"{label} log probabilities must not be positive")
        mask = item.completion_mask
        _need(not mask.is_complex() and not mask.requires_grad, "completion mask must be real and detached")
        _need(bool(((mask == 0) | (mask == 1)).all().item()), "completion mask must be binary and finite")
        _need(mask[0].item() == 0, "position zero cannot be a predicted completion token")
        binary = mask.detach().to(dtype=torch.bool)
        _need(not bool((binary[:-1] & ~binary[1:]).any().item()), "mask must be prompt zeros followed by completion ones")
        count = int(binary.sum().item())
        _need(count > 0, "each trajectory needs at least one completion token")
        _need(type(item.reward) in (int, float), "reward must be a finite scalar, not an infrastructure status")
        try:
            reward = float(item.reward)
        except OverflowError as error:
            raise ValueError("reward exceeds scalar range") from error
        _need(math.isfinite(reward) and abs(reward) <= torch.finfo(torch.float32).max / 2,
              "reward must be finite and safely float32-representable")
        groups.setdefault(item.group_id, []).append(index)
        counts.append(count)
        rewards.append(reward)
        masks.append(binary.float())
        behavior.append(item.behavior_log_probs.detach())

    advantages = [0.0] * len(trajectories)
    reports = []
    for group_id, indices in groups.items():
        _need(len(indices) >= 2, "each reward group requires at least two complete trajectories")
        baseline = math.fsum(rewards[index] / len(indices) for index in indices)
        for index in indices:
            advantages[index] = rewards[index] - baseline
        reports.append({"group_id": group_id, "samples": len(indices),
                        "reward_mean": baseline,
                        "has_signal": any(advantages[index] != 0 for index in indices)})
    mixed = sum(report["has_signal"] for report in reports)

    samples = []
    advantage_vectors = []
    divisors = []
    for index, item in enumerate(trajectories):
        indices = groups[item.group_id]
        advantage_vector = masks[index] * advantages[index]
        divisor = float(max(1, mixed) * len(indices) * counts[index])
        _need(math.isfinite(divisor) and divisor <= torch.finfo(torch.float32).max,
              "loss divisor exceeds float32 range")
        sample = TrainingSample(
            sample_id=item.sample_id, input_ids=list(item.input_ids),
            completion_mask=masks[index].to(dtype=torch.int64).tolist(),
            gen_logprobs=behavior[index].float().tolist(),
            advantages=advantage_vector.tolist(),
            oldest_weight_version=0, weight_version_token_counts={0: counts[index]},
            seq_token_count=counts[index], prompt_token_count=sum(counts[j] for j in indices),
            prompt_sequence_count=len(indices), prompt_id=item.group_id, divisor=divisor,
        )
        samples.append(sample)
        advantage_vectors.append(advantage_vector)
        divisors.append(divisor)

    if mixed == 0:
        return AF3LossResult(None, False, "zero_reward_signal", tuple(samples), {}, tuple(reports))
    _need(torch.is_grad_enabled() and not torch.is_inference_mode_enabled(), "signal-bearing loss requires enabled autograd")
    for index, item in enumerate(trajectories):
        if advantages[index] != 0:
            _need(item.train_log_probs.requires_grad, "signal-bearing train log probabilities require gradients")

    output = DDISLoss(eps_low=eps_low, eps_high=eps_high, use_opsm=False,
                      entropy_top_pct=None).compute_unpacked(
        log_probs=[item.train_log_probs for item in trajectories],
        completion_mask=masks, advantages=advantage_vectors,
        divisors=torch.tensor(divisors, dtype=torch.float32, device=device),
        gen_log_probs=behavior,
    )
    _need(bool(torch.isfinite(output.loss_unscaled).item()), "upstream DDIS produced a nonfinite loss")
    effective = False
    with torch.no_grad():
        for index, item in enumerate(trajectories):
            if advantages[index] == 0:
                continue
            ratio = (item.train_log_probs.float() - behavior[index].float()).clamp(-20, 20).exp()
            inside = (ratio > 1 - eps_low) & (ratio < 1 + eps_high) & masks[index].bool()
            effective = effective or bool(inside.any().item())
    return AF3LossResult(output.loss_unscaled, effective,
                         "signal" if effective else "all_signal_tokens_clipped",
                         tuple(samples), output.metric_states, tuple(reports))

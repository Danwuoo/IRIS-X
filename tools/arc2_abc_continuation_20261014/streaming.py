"""Opt-in, CPU-only sequential reduction using the pinned upstream AF3 loss.

This is an offline shadow interface, not a model owner or an update protocol.
Validate the complete PreparedBatch before replay, then contribute all 64 rows
in their original order. Backward (if desired) belongs to the caller, which must
release each contribution before constructing the next replay graph. The session
never retains a replay tensor or differentiable loss. A micro-loss, or even a
successful finalize(), cannot authorize a parameter/optimizer update.

Derivatives here are through caller-supplied replay tensors. This does not prove
actual model/LoRA gradients, replay provenance, real rollback, or training.
"""
from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any

from tools.arc2_agent_factory3_bridge_20261014.bridge import (
    BatchContext, PreparedBatch, TrainingSample, _contract_digest,
    _finite_probability, _sample_digest, _sha, need,
)
from tools.arc2_agent_factory3_bridge_20261014.provenance import (
    UPSTREAM_COMMIT, verify_frozen_contract, verify_vendor,
)

DERIVATIVE_SCOPE = "caller-supplied-CPU-replay-tensors-only"


@dataclass(frozen=True)
class StreamingContribution:
    """One caller-owned graph; consume/release it before the next replay.

    Zero-advantage rows still undergo every replay gate and upstream metric
    calculation. has_training_signal=False preserves the native skip-backward
    choice for those rows. No backward or optimizer operation is called here.
    """
    sample_id: str
    index: int
    loss_unscaled: Any
    metric_states: dict
    has_training_signal: bool
    derivative_scope: str = DERIVATIVE_SCOPE
    production_update_authorized: bool = False


@dataclass(frozen=True)
class StreamingLossReport:
    """Detached completed shadow reduction, never an owner admission receipt."""
    status: str
    contributed_samples: int
    mixed_groups: int
    loss_unscaled: float | None
    metric_states: dict
    contract_digest: str
    sample_digest: str
    raw_receipt_digest: str
    evidence_kind: str
    batch_index: int
    derivative_scope: str = DERIVATIVE_SCOPE
    production_update_authorized: bool = False
    model_replay_verified: bool = False
    provenance_authenticated: bool = False

    def summary(self):
        """Compact JSON-compatible output; no raw tokens, rewards or replay arrays."""
        return {
            "format": "irisx/af3-streaming-shadow-v1", "status": self.status,
            "upstream_commit": UPSTREAM_COMMIT, "batch_index": self.batch_index,
            "declared_samples": 64, "contributed_samples": self.contributed_samples,
            "mixed_groups": self.mixed_groups, "loss_unscaled": self.loss_unscaled,
            "metrics": {name: {"sum": float(state.sum), "count": float(state.count),
                               "mean": float(state.mean()), "weighting": state.weighting}
                        for name, state in self.metric_states.items()},
            "contract_digest": self.contract_digest, "sample_digest": self.sample_digest,
            "raw_receipt_digest": self.raw_receipt_digest, "evidence_kind": self.evidence_kind,
            "derivative_scope": self.derivative_scope,
            "production_update_authorized": False, "model_replay_verified": False,
            "provenance_authenticated": False, "optimizer_executed": False,
        }


def _validated_snapshot(prepared):
    """Bind every declaration before admitting any graph; never regroup one row.

    The existing bridge has already checked the original producer receipt. Its
    digest checks are reused, and the complete prepared shape is checked too:
    PreparedBatch is a public dataclass, so a truncated/rebound instance must not
    accidentally become a one-sample batch. Hashes remain consistency checks,
    not evidence authentication. Copying prevents later caller mutation.
    """
    verify_vendor()
    verify_frozen_contract()
    need(type(prepared) is PreparedBatch, "prepared upstream batch")
    prepared = deepcopy(prepared)
    need(type(prepared.context) is BatchContext, "exact batch context")
    prepared.context.validate()
    need(type(prepared.samples) is tuple and len(prepared.samples) == 64 and
         all(type(s) is TrainingSample for s in prepared.samples), "complete 64-slot prepared batch")
    need(type(prepared.group_reports) is tuple and len(prepared.group_reports) == 8 and
         all(type(g) is dict for g in prepared.group_reports), "complete eight group reports")
    need(type(prepared.prompt_lengths) is tuple and len(prepared.prompt_lengths) == 64 and
         type(prepared.nonforced_masks) is tuple and len(prepared.nonforced_masks) == 64,
         "complete prepared alignment")
    need(_sample_digest(prepared.samples) == prepared.sample_digest, "mutated upstream samples")
    need(_contract_digest(prepared.samples, prepared.group_reports, prepared.nonforced_masks,
                          prepared.prompt_lengths, prepared.context, prepared.raw_receipt_digest)
         == prepared.contract_digest, "mutated bridge contract")
    need(_sha(prepared.raw_receipt_digest), "raw receipt digest")
    parents = prepared.context.train_parent_ids[prepared.context.batch_index * 8:][:8]
    for parent, group in zip(parents, prepared.group_reports):
        successes = group.get("successes")
        need(type(successes) is int and 0 <= successes <= 8, "fixed group success count")
        need(group == {"parent_id": parent, "planned": 8, "eligible": 8, "successes": successes,
                       "mixed": 0 < successes < 8, "all_zero": successes == 0,
                       "all_one": successes == 8}, "fixed full-batch group report")
    seen = set()
    for index, (sample, p, nonforced) in enumerate(zip(
            prepared.samples, prepared.prompt_lengths, prepared.nonforced_masks)):
        n = sample.seq_token_count
        need(type(p) is int and 0 < p <= 3072 and type(n) is int and 0 < n <= 1024,
             "original prepared token lengths")
        need(type(nonforced) is tuple and len(nonforced) == n and
             all(type(flag) is bool for flag in nonforced), "prepared nonforced alignment")
        need(type(sample.sample_id) is str and sample.sample_id and sample.sample_id not in seen,
             "unique prepared trajectory identity")
        seen.add(sample.sample_id)
        need(len(sample.input_ids) == p + n and
             all(type(t) is int and 0 <= t < 151936 for t in sample.input_ids), "original prepared token IDs")
        need(sample.completion_mask == [0] * p + [1] * n and
             len(sample.gen_logprobs) == p + n and len(sample.advantages) == p + n,
             "prepared causal alignment")
        need(sample.gen_logprobs[:p] == [0.] * p and sample.advantages[:p] == [0.] * p and
             all(_finite_probability(mu) for mu in sample.gen_logprobs[p:]) and
             all(flag or mu == 0. for flag, mu in zip(nonforced, sample.gen_logprobs[p:])),
             "prepared behavior probabilities")
        group = index // 8
        baseline = prepared.group_reports[group]["successes"] / 8
        advantage = sample.advantages[p]
        need(advantage in (-baseline, 1. - baseline) and
             sample.advantages[p:] == [advantage] * n, "fixed full-batch group advantage")
        need(sample.prompt_id == parents[group] and sample.prompt_sequence_count == 8 and
             sample.prompt_token_count == sum(s.seq_token_count for s in prepared.samples[group * 8:group * 8 + 8]) and
             sample.divisor == float(max(1, prepared.mixed_groups) * 8 * n), "fixed full-batch divisor and group")
        need(sample.oldest_weight_version == 0 and sample.weight_version_token_counts == {0: n} and
             sample.gen_entropy is None and sample.routing_indices is None, "fixed upstream replay configuration")
        first = prepared.samples[group * 8]
        first_p = prepared.prompt_lengths[group * 8]
        need(sample.input_ids[:p] == first.input_ids[:first_p], "fixed parent prompt token IDs")
    for group in range(8):
        samples = prepared.samples[group * 8:group * 8 + 8]
        baseline = prepared.group_reports[group]["successes"] / 8
        need(sum(s.advantages[p] + baseline for s, p in zip(
            samples, prepared.prompt_lengths[group * 8:group * 8 + 8])) == baseline * 8,
            "full group centered advantages")
    return prepared


class StreamingLossSession:
    """Fail-closed sequential CPU shadow reduction of a complete PreparedBatch.

    Use as a context manager when caller replay/backward can raise or time out.
    An exception, an incomplete finalize(), or leaving the context without
    finalize() aborts the session and discards its detached accumulators. Already
    returned graphs/accumulated caller gradients remain the caller's property;
    real owner rollback and commit gates are intentionally outside this API.
    This single-consumer session provides no thread/concurrent replay support.
    """
    __slots__ = ("_prepared", "_loss", "_metric_states", "_loss_total", "_index",
                 "_state", "_identity", "_mixed_groups", "_padded_length", "_torch")

    def __init__(self, prepared):
        snapshot = _validated_snapshot(prepared)
        self._identity = {"contract_digest": snapshot.contract_digest,
                          "sample_digest": snapshot.sample_digest,
                          "raw_receipt_digest": snapshot.raw_receipt_digest,
                          "evidence_kind": snapshot.context.evidence_kind,
                          "batch_index": snapshot.context.batch_index}
        self._mixed_groups = snapshot.mixed_groups
        self._padded_length = max(len(sample.input_ids) for sample in snapshot.samples)
        self._prepared = snapshot
        self._index = 0
        self._state = "open"
        self._metric_states = {}
        self._loss_total = 0.
        self._torch = None
        self._loss = None
        # Preserve the native complete zero-signal path: no torch/loss/replay
        # construction is necessary, even inside a no-grad/inference context.
        if self._mixed_groups:
            import torch
            from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.ddis_loss import DDISLoss
            self._torch = torch
            self._loss = DDISLoss(eps_low=.2, eps_high=.28, use_opsm=False, entropy_top_pct=None)

    @property
    def state(self):
        return self._state

    @property
    def contributed_samples(self):
        return self._index

    @property
    def next_sample_id(self):
        if self._state != "open" or not self._mixed_groups or self._index == 64:
            return None
        return self._prepared.samples[self._index].sample_id

    def _clear(self):
        self._prepared = None
        self._loss = None
        self._metric_states = {}
        self._loss_total = 0.
        self._torch = None

    def abort(self):
        """Discard this reduction; no caller gradients/parameters are modified."""
        if self._state != "finalized":
            self._state = "aborted"
            self._clear()

    def contribute(self, sample_id, replay_log_probs):
        """Return one real upstream contribution without retaining its graph."""
        try:
            need(self._state == "open", "streaming session is not open")
            need(self._mixed_groups > 0, "zero-signal batch: no replay or loss permitted")
            need(type(sample_id) is str and sample_id == self.next_sample_id,
                 "exact next trajectory identity; no duplicate, missing or reordered replay")
            torch = self._torch
            need(torch.is_grad_enabled() and not torch.is_inference_mode_enabled(), "replay needs active autograd")
            sample = self._prepared.samples[self._index]
            p = self._prepared.prompt_lengths[self._index]
            nonforced = self._prepared.nonforced_masks[self._index]
            pi = replay_log_probs
            need(torch.is_tensor(pi) and pi.device.type == "cpu" and pi.ndim == 1 and
                 pi.is_floating_point() and pi.shape[0] == sample.seq_token_count and pi.requires_grad,
                 "CPU differentiable original generated-token replay vector")
            need(not torch.is_inference(pi), "inference replay tensor is not differentiable")
            need(bool(torch.isfinite(pi).all()) and bool((pi <= 1e-6).all()) and
                 bool(torch.isfinite(pi.float()).all()), "finite replay log probabilities")
            mu = torch.tensor(sample.gen_logprobs[p:], dtype=torch.float32)
            need(bool(torch.isfinite(mu).all()), "behavior exceeds float32")
            select = torch.tensor(nonforced, dtype=torch.bool)
            need(bool((pi.detach()[~select] == 0.).all()), "forced-token replay probability")
            gap = (pi.detach().double() - mu.double())[select].abs()
            need(gap.numel() == 0 or (float(gap.max()) <= .20 and float(torch.quantile(gap, .95)) <= .05),
                 "frozen replay gap gate")
            ratio = (pi.detach().double() - mu.double()).clamp(-20, 20).exp()
            need(bool(((ratio > .8) & (ratio < 1.28)).all()), "frozen replay unclipped-fraction gate")
            # Reuse the exact upstream implementation. In particular, never
            # invoke prepare_batch on a single row, recenter, or change divisor.
            # Match the full upstream call's reduction width. Padding only
            # this row costs O(max original sequence length), not 64 graphs.
            # Without it, float32 E[ratio**2]-E[ratio]**2 can change the upstream
            # ratio_std metric solely due to a different sum kernel/width.
            padding = self._padded_length - len(sample.input_ids)
            def padded(tensor):
                return torch.nn.functional.pad(tensor, (0, padding))
            output = self._loss.compute_unpacked(
                log_probs=[padded(torch.cat((pi.new_zeros(p), pi)))],
                completion_mask=[padded(torch.tensor(sample.completion_mask, dtype=torch.float32))],
                advantages=[padded(torch.tensor(sample.advantages, dtype=torch.float32).detach())],
                divisors=torch.tensor([sample.divisor], dtype=torch.float32),
                gen_log_probs=[padded(torch.tensor(sample.gen_logprobs, dtype=torch.float32).detach())])
            need(bool(torch.isfinite(output.loss_unscaled)) and output.loss_unscaled.requires_grad,
                 "finite differentiable upstream micro-loss")
            from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.metric_state import MeanMetricState
            need(self._index == 0 or set(output.metric_states) == set(self._metric_states),
                 "stable upstream metric schema")
            for name, state in output.metric_states.items():
                need(type(state) is MeanMetricState and state.weighting == "sample" and
                     state.sum.ndim == state.count.ndim == 0 and
                     bool(torch.isfinite(state.sum)) and bool(torch.isfinite(state.count)) and
                     bool(state.count >= 0), "finite upstream sample-weighted metric state")
                detached = MeanMetricState(state.sum.detach().clone(), state.count.detach().clone(), state.weighting)
                if name not in self._metric_states:
                    self._metric_states[name] = detached
                else:
                    self._metric_states[name].merge_(detached)
                merged = self._metric_states[name]
                need(bool(torch.isfinite(merged.sum)) and bool(torch.isfinite(merged.count)),
                     "finite merged upstream metric state")
            self._loss_total += float(output.loss_unscaled.detach())
            need(math.isfinite(self._loss_total), "finite accumulated upstream loss")
            contribution = StreamingContribution(sample.sample_id, self._index, output.loss_unscaled,
                                                 output.metric_states, sample.advantages[p] != 0.)
            self._index += 1
            return contribution
        except BaseException:
            self.abort()
            raise

    def finalize(self):
        """Return detached results only after complete replay, or zero signal."""
        try:
            need(self._state == "open", "streaming session is not open")
            need(self._index == (64 if self._mixed_groups else 0), "incomplete streaming batch cannot finalize")
            need(math.isfinite(self._loss_total), "finite accumulated upstream loss")
            for metric in self._metric_states.values():
                need(bool(self._torch.isfinite(metric.sum)) and bool(self._torch.isfinite(metric.count)),
                     "finite merged upstream metric state")
            report = StreamingLossReport(
                status="complete-shadow-reduction" if self._mixed_groups else "zero-signal-no-replay-no-loss",
                contributed_samples=self._index, mixed_groups=self._mixed_groups,
                loss_unscaled=self._loss_total if self._mixed_groups else None,
                metric_states=self._metric_states, **self._identity)
            self._state = "finalized"
            self._clear()
            return report
        except BaseException:
            self.abort()
            raise

    def __enter__(self):
        need(self._state == "open", "streaming session is not open")
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None or self._state == "open":
            self.abort()
        return False

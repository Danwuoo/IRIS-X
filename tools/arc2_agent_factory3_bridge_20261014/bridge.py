"""Actual AF3 TrainingSample/DDISLoss reuse, isolated from production ownership.

This is an in-memory offline bridge. Caller declarations and hash consistency do
not authenticate reward origin, a running model, DFA semantics or replay. No
optimizer, model, data reader, server, persistence or external operation exists.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math

from .provenance import UPSTREAM_COMMIT, verify_frozen_contract, verify_vendor

verify_vendor()
from .vendor.types import TrainingSample


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("finite JSON-compatible declaration required") from exc
    return hashlib.sha256(encoded).hexdigest()


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _ids(value, name, maximum):
    # Frozen owned_runtime/factory.py:25-26 binds vocab and context capacities.
    need(type(value) is list and 0 < len(value) <= maximum and
         all(type(v) is int and 0 <= v < 151936 for v in value), name + " token IDs")


def _finite_probability(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and -3.4028234663852886e38 <= value <= 1e-6
    except OverflowError:
        return False


@dataclass(frozen=True)
class BatchContext:
    """Expected caller declarations, never a production admission credential."""
    train_parent_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    forbidden_parent_ids: tuple[str, ...]
    batch_index: int
    policy_version: str
    actor_identity: str
    generation_epoch: int
    panel_sha256: str
    sampling_policy_sha256: str
    evidence_kind: str = "synthetic"

    def validate(self):
        for values, size, label in ((self.train_parent_ids, 32, "train parents"),
                                    (self.record_ids, 32, "training records")):
            need(type(values) is tuple and len(values) == size and
                 all(type(v) is str and v for v in values) and len(set(values)) == size, label)
        need(type(self.forbidden_parent_ids) is tuple and len(self.forbidden_parent_ids) >= 120 and
             all(type(v) is str and v for v in self.forbidden_parent_ids) and
             len(set(self.forbidden_parent_ids)) == len(self.forbidden_parent_ids), "full forbidden parent declarations")
        need(not set(self.train_parent_ids).intersection(self.forbidden_parent_ids), "training/public lineage overlap")
        need(type(self.batch_index) is int and 0 <= self.batch_index < 4, "fixed batch index")
        need(type(self.generation_epoch) is int and self.generation_epoch >= 0, "generation epoch")
        need(type(self.policy_version) is str and self.policy_version, "explicit policy version")
        need(all(_sha(x) for x in (self.actor_identity, self.panel_sha256, self.sampling_policy_sha256)),
             "source-bound identity declarations")
        need(self.evidence_kind in ("synthetic", "declared-training-only"), "training-only evidence kind")


@dataclass(frozen=True)
class PreparedBatch:
    samples: tuple[TrainingSample, ...]
    sample_digest: str
    group_reports: tuple[dict, ...]
    nonforced_masks: tuple[tuple[bool, ...], ...]
    prompt_lengths: tuple[int, ...]
    context: BatchContext
    raw_receipt_digest: str
    contract_digest: str

    @property
    def mixed_groups(self):
        return sum(g["mixed"] for g in self.group_reports)

    def summary(self):
        return {"upstream_commit": UPSTREAM_COMMIT,
                "component": "actual-upstream-TrainingSample",
                "evidence_kind": self.context.evidence_kind,
                "samples": len(self.samples), "mixed_groups": self.mixed_groups,
                "group_reports": list(self.group_reports),
                "sample_digest": self.sample_digest,
                "contract_digest": self.contract_digest,
                "raw_receipt_digest": self.raw_receipt_digest,
                "upstream_weight_version_namespace": "batch-local-symbolic-only",
                "upstream_weight_version_mapping": {"0": self.context.policy_version},
                "provenance_authenticated": False, "model_replay_verified": False,
                "production_update_authorized": False}


def _sample_digest(samples):
    return digest([s.model_dump(mode="json") for s in samples])


def _contract_digest(samples, reports, nonforced, lengths, context, raw_receipt_digest):
    return digest({"samples": _sample_digest(samples), "groups": reports,
                   "nonforced": nonforced, "prompt_lengths": lengths, "context": asdict(context),
                   "raw_receipt_digest": raw_receipt_digest})


def prepare_batch(batch, context):
    """Map the frozen native 8-parent x 8-slot receipt to real upstream samples.

    Preserve all 64 samples including zero-signal groups. Their advantages are
    zero, while the divisor counts mixed groups only, exactly as frozen IRIS-X.
    No incomplete-row filtering, text retokenization or reward recomputation.
    """
    verify_vendor()
    verify_frozen_contract()
    need(type(context) is BatchContext, "exact batch context")
    context.validate()
    need(type(batch) is dict, "batch object")
    fatal = batch.get("fatal_native_state")
    need((fatal is None or fatal is False) and batch.get("stop_reason") is None and
         batch.get("error") is None, "fatal/stopped batch")
    parents = context.train_parent_ids[context.batch_index * 8:context.batch_index * 8 + 8]
    need(batch.get("closed") is True and batch.get("all_slots_reached") is True, "incomplete batch")
    for name, expected in (("planned_attempts", 64), ("group_size", 8), ("planned_parents", 32),
                           ("session_planned_attempts", 256), ("batch_index", context.batch_index),
                           ("generation_epoch", context.generation_epoch)):
        need(type(batch.get(name)) is int and batch[name] == expected, "fixed " + name)
    need(batch.get("parent_ids") == list(parents), "fixed parent order")
    for name in ("policy_version", "panel_sha256", "sampling_policy_sha256"):
        need(batch.get(name) == getattr(context, name), "batch " + name + " mismatch")
    rows = batch.get("rows")
    need(type(rows) is list and len(rows) == 64, "complete 64-slot batch")
    metadata, seen, cache_modes, group_prompts = [], set(), set(), {}
    for index, row in enumerate(rows):
        need(type(row) is dict, "row object")
        parent = parents[index // 8]
        record = context.record_ids[context.batch_index * 8 + index // 8]
        need(row.get("parent_id") == parent and type(row.get("slot")) is int and
             row["slot"] == index % 8, "fixed parent/slot order")
        need(row.get("eligible") is True and row.get("status") == "eligible", "infrastructure/missing row")
        need(type(row.get("reward")) is int and row["reward"] in (0, 1), "binary reward, not unknown")
        need(row.get("reason") == "exact-training-LOO-equality", "training reward declaration")
        t = row.get("trajectory")
        need(type(t) is dict, "original trajectory")
        fatal = t.get("fatal_native_state")
        need((fatal is None or fatal is False) and t.get("error") is None, "fatal/error trajectory")
        need(t.get("parent_id") == parent and t.get("record_id") == record, "training record mismatch")
        tid = t.get("trajectory_id")
        need(type(tid) is str and tid and tid not in seen, "unique trajectory identity")
        seen.add(tid)
        need(t.get("policy_version") == context.policy_version and
             t.get("identity") == context.actor_identity and
             type(t.get("generation_epoch")) is int and
             t["generation_epoch"] == context.generation_epoch, "stale/mixed actor identity")
        need(t.get("infrastructure_excluded") is False and
             t.get("finish_reason") in ("eos", "length"), "infrastructure trajectory")
        need(row["reward"] == 0 or t["finish_reason"] == "eos", "positive non-EOS reward")
        sampling = t.get("sampling", {})
        need(type(sampling) is dict and type(sampling.get("temperature")) in (int, float) and
             sampling["temperature"] == 1 and type(sampling.get("top_p")) in (int, float) and
             sampling["top_p"] == 1 and sampling.get("dfa") is True and
             sampling.get("cache_mode") in ("cached", "full_prefix"), "frozen sampling policy")
        cache_modes.add(sampling["cache_mode"])
        need(len(cache_modes) == 1, "single actor cannot mix cache modes")
        prompt, generated, original = t.get("prompt_ids"), t.get("generated_ids"), t.get("original_ids")
        _ids(prompt, "prompt", 3072); _ids(generated, "generated", 1024); _ids(original, "original", 4096)
        prompt_tuple = tuple(prompt)
        need(group_prompts.get(parent, prompt_tuple) == prompt_tuple, "fixed parent prompt token IDs")
        group_prompts[parent] = prompt_tuple
        attention = t.get("attention_mask")
        need(original == prompt + generated and type(attention) is list and
             all(type(v) is int for v in attention) and attention == [1] * len(original) and
             t.get("origins") == ["prompt"] * len(prompt) + ["assistant_generated"] * len(generated),
             "original causal token layout")
        steps = t.get("steps")
        need(type(steps) is list and len(steps) == len(generated), "original step alignment")
        mus, nonforced = [], []
        for position, (token, step) in enumerate(zip(generated, steps)):
            need(type(step) is dict and type(step.get("token")) is int and step["token"] == token and
                 type(step.get("position")) is int and step["position"] == len(prompt) + position - 1 and
                 step.get("prefix_sha256") == digest(prompt + generated[:position]), "causal prefix/position")
            support = step.get("support")
            _ids(support, "support", 27)
            need(len(set(support)) == len(support) and token in support,
                 "DFA support declaration")
            state = step.get("dfa_state")
            need(type(state) is list and len(state) == 3 and
                 all(type(v) is int and v >= 0 for v in state), "native DFA state declaration")
            mu = step.get("log_mu")
            need(_finite_probability(mu), "finite float32 behavior log-mu")
            need(len(support) != 1 or mu == 0., "forced-token behavior probability")
            mus.append(float(mu)); nonforced.append(len(support) > 1)
        metadata.append((t, mus, tuple(nonforced)))
    reports = []
    for index, parent in enumerate(parents):
        successes = sum(r["reward"] for r in rows[index * 8:index * 8 + 8])
        reports.append({"parent_id": parent, "planned": 8, "eligible": 8, "successes": successes,
                        "mixed": 0 < successes < 8, "all_zero": successes == 0, "all_one": successes == 8})
    mixed = sum(g["mixed"] for g in reports)
    samples = []
    for index, (row, (t, mus, _)) in enumerate(zip(rows, metadata)):
        p, n = len(t["prompt_ids"]), len(t["generated_ids"])
        group = index // 8
        advantage = row["reward"] - reports[group]["successes"] / 8
        sample = TrainingSample(
            sample_id=t["trajectory_id"], input_ids=list(t["original_ids"]),
            completion_mask=[0] * p + [1] * n, gen_logprobs=[0.] * p + mus,
            advantages=[0.] * p + [advantage] * n,
            # AF3 expects integer versions; use a batch-local symbol, never
            # confuse native batch index/generation epoch with weight history.
            oldest_weight_version=0, weight_version_token_counts={0: n},
            seq_token_count=n,
            prompt_token_count=sum(len(metadata[j][0]["generated_ids"]) for j in range(group * 8, group * 8 + 8)),
            prompt_sequence_count=8, prompt_id=row["parent_id"], divisor=float(max(1, mixed) * 8 * n))
        samples.append(sample)
    nonforced = tuple(m[2] for m in metadata)
    lengths = tuple(len(m[0]["prompt_ids"]) for m in metadata)
    raw_receipt_digest = digest(batch)
    return PreparedBatch(tuple(samples), _sample_digest(samples), tuple(reports), nonforced, lengths,
                         context, raw_receipt_digest,
                         _contract_digest(samples, reports, nonforced, lengths, context, raw_receipt_digest))


def compute_loss(prepared, replay_log_probs):
    """Run the actual pinned upstream DDISLoss on CPU replay tensors.

    Input values are already DFA-conditioned selected-token probabilities. This
    function cannot infer a model graph, revalidate DFA semantics, prove an
    unchanged model or authorize an optimizer step. It never calls backward.
    """
    verify_vendor()
    verify_frozen_contract()
    need(type(prepared) is PreparedBatch, "prepared upstream batch")
    prepared.context.validate()
    need(_sample_digest(prepared.samples) == prepared.sample_digest, "mutated upstream samples")
    need(_contract_digest(prepared.samples, prepared.group_reports, prepared.nonforced_masks,
                          prepared.prompt_lengths, prepared.context, prepared.raw_receipt_digest) == prepared.contract_digest,
         "mutated bridge contract")
    need(prepared.mixed_groups > 0, "zero-signal batch: preserve native no-replay/no-update")
    import torch
    from .vendor.losses.ddis_loss import DDISLoss
    need(torch.is_grad_enabled() and not torch.is_inference_mode_enabled(), "replay needs active autograd")
    need(type(replay_log_probs) is dict and set(replay_log_probs) == {s.sample_id for s in prepared.samples},
         "complete exact replay identity set")
    logps, masks, advantages, behavior, divisors = [], [], [], [], []
    for sample, p, nonforced in zip(prepared.samples, prepared.prompt_lengths, prepared.nonforced_masks):
        pi = replay_log_probs[sample.sample_id]
        need(torch.is_tensor(pi) and pi.device.type == "cpu" and pi.ndim == 1 and pi.is_floating_point()
             and pi.shape[0] == sample.seq_token_count and pi.requires_grad,
             "CPU differentiable original generated-token replay vector")
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
        logps.append(torch.cat((pi.new_zeros(p), pi)))
        masks.append(torch.tensor(sample.completion_mask, dtype=torch.float32))
        advantages.append(torch.tensor(sample.advantages, dtype=torch.float32).detach())
        behavior.append(torch.tensor(sample.gen_logprobs, dtype=torch.float32).detach())
        divisors.append(sample.divisor)
    result = DDISLoss(eps_low=.2, eps_high=.28, use_opsm=False, entropy_top_pct=None).compute_unpacked(
        log_probs=logps, completion_mask=masks, advantages=advantages,
        divisors=torch.tensor(divisors, dtype=torch.float32), gen_log_probs=behavior)
    need(bool(torch.isfinite(result.loss_unscaled)), "finite upstream loss")
    need(result.loss_unscaled.requires_grad, "differentiable upstream loss")
    return result

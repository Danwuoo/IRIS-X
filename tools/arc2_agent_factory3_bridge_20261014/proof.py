"""CPU synthetic execution proof for actual upstream loss and gradient reuse."""
import hashlib
import importlib.util
import json

from .bridge import compute_loss, prepare_batch
from .fixtures import synthetic_batch
from .provenance import BASELINE_MATH, BASELINE_MATH_SHA256, ROOT, UPSTREAM_COMMIT, verify_vendor


def baseline_math():
    path = ROOT.parents[1] / BASELINE_MATH
    if hashlib.sha256(path.read_bytes()).hexdigest() != BASELINE_MATH_SHA256:
        raise ValueError("frozen local math source drift")
    spec = importlib.util.spec_from_file_location("af3_proof_frozen_math", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_replay(batch, math_module):
    import torch
    max_length = max(len(row["trajectory"]["generated_ids"]) for row in batch["rows"])
    logits = (torch.arange(64 * max_length * 16, dtype=torch.float32).reshape(64, max_length, 16)
              .remainder(13).mul(.001)).requires_grad_()
    replay = {}
    for index, row in enumerate(batch["rows"]):
        t = row["trajectory"]; n = len(t["generated_ids"])
        allowed = torch.zeros((n, 16), dtype=torch.bool)
        for p, step in enumerate(t["steps"]):
            allowed[p, step["support"]] = True
        replay[t["trajectory_id"]] = math_module.selected_log_probs(
            logits[index, :n], allowed, torch.tensor(t["generated_ids"], dtype=torch.long))
    return logits, replay


def run_proof():
    import torch
    from torch.nn.utils.rnn import pad_sequence
    verify_vendor(); math_module = baseline_math()
    batch, context = synthetic_batch(); prepared = prepare_batch(batch, context)
    logits, replay = synthetic_replay(batch, math_module)
    upstream = compute_loss(prepared, replay)
    pi = pad_sequence(list(replay.values()), batch_first=True)
    mu = pad_sequence([torch.tensor([s["log_mu"] for s in r["trajectory"]["steps"]])
                       for r in batch["rows"]], batch_first=True)
    mask = pad_sequence([torch.ones(len(r["trajectory"]["generated_ids"]), dtype=torch.bool)
                         for r in batch["rows"]], batch_first=True)
    rewards = torch.tensor([r["reward"] for r in batch["rows"]], dtype=torch.float32)
    local_loss, local_diagnostics = math_module.ddis_loss(
        pi, mu, mask, rewards, [r["parent_id"] for r in batch["rows"]],
        torch.ones(64, dtype=torch.bool), [context.policy_version] * 64)
    upstream_gradient, = torch.autograd.grad(upstream.loss_unscaled, logits, retain_graph=True)
    local_gradient, = torch.autograd.grad(local_loss, logits, retain_graph=True)
    # The runtime's per-trajectory accumulation is a third independent reduction.
    micro = pi.new_zeros(())
    for i, sample in enumerate(prepared.samples):
        n, p = sample.seq_token_count, prepared.prompt_lengths[i]
        advantage = sample.advantages[p]
        target = replay[sample.sample_id]
        behavior = torch.tensor(sample.gen_logprobs[p:])
        ratio = (target.float() - behavior.detach()).clamp(-20, 20).exp()
        micro = micro - (ratio.detach() * advantage * target * ((ratio > .8) & (ratio < 1.28))).sum() / sample.divisor
    micro_gradient, = torch.autograd.grad(micro, logits)
    atol, rtol = 1e-7, 1e-6
    torch.testing.assert_close(upstream.loss_unscaled, local_loss, atol=atol, rtol=rtol)
    torch.testing.assert_close(upstream.loss_unscaled, micro, atol=atol, rtol=rtol)
    torch.testing.assert_close(upstream_gradient, local_gradient, atol=atol, rtol=rtol)
    torch.testing.assert_close(upstream_gradient, micro_gradient, atol=atol, rtol=rtol)
    if not bool(torch.isfinite(upstream_gradient).all()) or not bool(upstream_gradient.abs().sum() > 0):
        raise ValueError("synthetic gradient missing/nonfinite")
    return {
        "format": "irisx/agent-factory3-offline-proof-v1", "evidence": "fabricated-non-ARC-CPU-logits",
        "upstream_commit": UPSTREAM_COMMIT, "torch_version": torch.__version__, "device": "cpu",
        "actual_upstream_TrainingSample_count": 64, "actual_upstream_DDISLoss_executed": True,
        "actual_upstream_metric_state_count": len(upstream.metric_states),
        "mixed_groups": prepared.mixed_groups, "generated_tokens": int(mask.sum()),
        "upstream_loss": float(upstream.loss_unscaled.detach()), "frozen_local_loss": float(local_loss.detach()),
        "loss_absolute_gap": float((upstream.loss_unscaled - local_loss).detach().abs()),
        "logit_gradient_max_abs_gap": float((upstream_gradient - local_gradient).abs().max()),
        "micro_gradient_max_abs_gap": float((upstream_gradient - micro_gradient).abs().max()),
        "logit_gradient_norm": float(upstream_gradient.norm()), "atol": atol, "rtol": rtol,
        "sample_mask_rate": float(upstream.metric_states["algo/ddis_mask_rate"].mean()),
        "local_effective_tokens": local_diagnostics["effective_tokens"],
        "source_hashes": verify_vendor(), "frozen_math_sha256": BASELINE_MATH_SHA256,
        "production_runtime_rewired": False, "optimizer_executed": False,
        "model_replay_verified": False, "GPU_verified": False, "ARC_accuracy_claim": False,
        "provenance_authenticated": False, "production_update_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_proof(), indent=2, sort_keys=True, allow_nan=False))

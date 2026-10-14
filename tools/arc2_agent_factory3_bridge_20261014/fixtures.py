"""Fabricated non-ARC token receipts. No dataset, model or evaluator read."""
import math
from .bridge import BatchContext, digest


def synthetic_batch(successes=(1, 2, 4, 6, 0, 8, 3, 5), *, batch_index=0):
    context = BatchContext(
        train_parent_ids=tuple("fabricated-parent-%02d" % i for i in range(32)),
        record_ids=tuple("fabricated-record-%02d" % i for i in range(32)),
        forbidden_parent_ids=tuple("fabricated-excluded-%03d" % i for i in range(120)),
        batch_index=batch_index, policy_version="synthetic-policy-A", actor_identity="a" * 64,
        generation_epoch=0, panel_sha256="b" * 64, sampling_policy_sha256="c" * 64)
    parents = context.train_parent_ids[batch_index * 8:batch_index * 8 + 8]
    batch = {"id": "synthetic-batch", "closed": True, "all_slots_reached": True,
             "fatal_native_state": None, "stop_reason": None,
             "planned_attempts": 64, "group_size": 8, "planned_parents": 32,
             "session_planned_attempts": 256, "batch_index": batch_index, "generation_epoch": 0,
             "policy_version": context.policy_version, "panel_sha256": context.panel_sha256,
             "sampling_policy_sha256": context.sampling_policy_sha256, "parent_ids": list(parents), "rows": []}
    for index in range(64):
        parent = parents[index // 8]
        prompt = [20, 21, 22][:2 + (index // 8) % 2]
        generated = [1 + (p % 3) for p in range(2 + index % 4)]
        steps = []
        for p, token in enumerate(generated):
            support = [token] if p % 2 == 0 else [token, token + 8]
            steps.append({"token": token, "position": len(prompt) + p - 1, "support": support,
                          "prefix_sha256": digest(prompt + generated[:p]), "dfa_state": [0, 1, p],
                          "log_mu": -math.log(len(support))})
        t = {"trajectory_id": "synthetic-%02d" % index, "parent_id": parent,
             "record_id": context.record_ids[batch_index * 8 + index // 8],
             "policy_version": context.policy_version, "identity": context.actor_identity,
             "generation_epoch": 0, "infrastructure_excluded": False, "finish_reason": "eos",
             "sampling": {"temperature": 1., "top_p": 1., "dfa": True, "cache_mode": "cached"},
             "prompt_ids": prompt, "generated_ids": generated, "original_ids": prompt + generated,
             "attention_mask": [1] * (len(prompt) + len(generated)),
             "origins": ["prompt"] * len(prompt) + ["assistant_generated"] * len(generated), "steps": steps}
        batch["rows"].append({"parent_id": parent, "slot": index % 8, "trajectory": t,
                              "reward": int(index % 8 < successes[index // 8]),
                              "eligible": True, "status": "eligible", "reason": "exact-training-LOO-equality"})
    return batch, context

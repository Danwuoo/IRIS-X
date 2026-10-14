"""Fabricated non-ARC original producer-shaped audits, never historical data.

These synthesize serialized declarations only. No model/actor/training/evaluator
is run. Native token alphabet, DFA states and the actual producer's field names
are retained so tests exercise the real saved-audit boundary rather than invent
an adapter-shaped substitute. Rewards are fabricated labels, not grid scoring.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
import struct

from tools.arc2_agent_factory3_bridge_20261014.bridge import BatchContext, digest
from .audit import CONTEXT_FORMAT, POLICY_SHA256, _stats, _summary


def audit_bytes(audit):
    return (json.dumps(audit, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def bind_context_document(audit, document):
    result = deepcopy(document)
    result["audit_sha256"] = hashlib.sha256(audit_bytes(audit)).hexdigest()
    return result


def _f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def synthetic_audit(successes=(1, 2, 4, 6, 0, 8, 3, 5), *, batch_index=0, logp_gap=0.):
    """Return (full saved-audit declaration, independently hash-bound context)."""
    if type(successes) not in (tuple, list) or len(successes) != 8 or any(type(x) is not int or not 0 <= x <= 8 for x in successes):
        raise ValueError("synthetic success counts")
    if type(batch_index) is not int or not 0 <= batch_index < 4:
        raise ValueError("synthetic batch index")
    context = BatchContext(
        train_parent_ids=tuple("fabricated-parent-%02d" % i for i in range(32)),
        record_ids=tuple("fabricated-record-%02d" % i for i in range(32)),
        forbidden_parent_ids=tuple("fabricated-excluded-%03d" % i for i in range(120)),
        batch_index=batch_index, policy_version="rl:fabricated-before-%d" % batch_index,
        actor_identity=digest("fabricated actor identity"), generation_epoch=2 * batch_index,
        panel_sha256=digest("fabricated panel declaration"), sampling_policy_sha256=POLICY_SHA256,
        evidence_kind="synthetic")
    records = [{"parent_id": p, "record_id": r, "messages_sha256": digest(["fabricated prompt", i]),
                "target_sha256": digest(["fabricated target", i]), "exclusion": None}
               for i, (p, r) in enumerate(zip(context.train_parent_ids, context.record_ids))]
    training = {"source_sha256": digest("fabricated training source"),
                "manifest_sha256": digest("fabricated training manifest"),
                "plan_sha256": digest("fabricated training plan"),
                "exclusions_sha256": digest(list(context.forbidden_parent_ids)), "record_declarations": records}
    before = {"policy_version": context.policy_version, "adapter_sha256": digest("fabricated adapter before"),
              "source_sha256": digest("fabricated owned source identity"), "generation_epoch": context.generation_epoch}
    parents = list(context.train_parent_ids[batch_index * 8:batch_index * 8 + 8])
    batch_id = "fabricated-batch-%d" % batch_index
    batch = {"id": batch_id, "planned_attempts": 64, "rows": [], "policy_version": context.policy_version,
             "generation_epoch": context.generation_epoch, "sweep": batch_index, "batch_index": batch_index,
             "parent_ids": parents, "group_size": 8, "planned_parents": 32, "session_planned_attempts": 256,
             "sampling_policy_sha256": POLICY_SHA256, "panel_sha256": context.panel_sha256,
             "attempted_batches": batch_index + 1, "stop_reason": None, "fatal_native_state": None,
             "closed": True, "all_slots_reached": True}
    for index in range(64):
        record = records[batch_index * 8 + index // 8]
        prompt = [20, 21, 22][:2 + index // 8 % 2]
        generated = [15 + i % 10 for i in range(1 + index % 5)] + [151645]
        steps, state = [], (0, 1, 0)
        trajectory_id = "fabricated-trajectory-%d-%02d" % (batch_index, index)
        event_id = index
        for position, token in enumerate(generated):
            width, nrows, column = state
            support = list(range(15, 25)) if column < (width or 30) else []
            if column > 0 and nrows < 30 and (not width or column == width):
                support.append(198)
            if column > 0 and (not width or column == width):
                support += [151643, 151645]
            steps.append({"position": len(prompt) + position - 1, "token": token,
                          "support": sorted(support), "dfa_state": list(state),
                          "prefix_sha256": digest(prompt + generated[:position]),
                          "log_mu": _f32(-math.log(len(support))), "actor_event_id": event_id,
                          "actor_forward_index": position})
            if 15 <= token <= 24:
                state = width, nrows, column + 1
        t = {"trajectory_id": trajectory_id, "parent_id": record["parent_id"], "record_id": record["record_id"],
             "messages_sha256": record["messages_sha256"], "policy_version": context.policy_version,
             "identity": context.actor_identity, "generation_epoch": context.generation_epoch,
             "seed": int(digest(["rl-fixed-batch-sampling-v1", POLICY_SHA256, training["plan_sha256"],
                                  batch_index, record["parent_id"], index % 8])[:15], 16),
             "generated_ids": generated, "steps": steps, "finish_reason": "eos", "infrastructure_excluded": False,
             "format_text": "".join(str(t - 15) for t in generated[:-1]),
             "sampling": {"temperature": 1., "top_p": 1., "dfa": True, "cache_mode": "cached"},
             "prompt_ids": prompt, "original_ids": prompt + generated,
             "attention_mask": [1] * (len(prompt) + len(generated)),
             "origins": ["prompt"] * len(prompt) + ["assistant_generated"] * len(generated),
             "cache_discarded": True, "dispatched_forwards": len(generated), "physical_event_ids": [event_id],
             "physical_accounting": "one-durable-generation-with-dense-original-forward-indices"}
        batch["rows"].append({"parent_id": record["parent_id"], "slot": index % 8,
                              "trajectory": t, "reward": int(index % 8 < successes[index // 8]),
                              "eligible": True, "status": "eligible", "valid_grid": True,
                              "reason": "exact-training-LOO-equality", "target_sha256": record["target_sha256"],
                              "fixture_only": False})
    summary = _summary(batch, parents)
    mixed = summary["mixed_groups"]
    after = {**before, "generation_epoch": before["generation_epoch"] + (2 if mixed else 1)}
    update = None
    if mixed:
        after.update(policy_version="rl:fabricated-after-%d" % batch_index,
                     adapter_sha256=digest("fabricated adapter after"))
        groups = [{"group": g["parent_id"], "total": 8, "eligible": 8, "infrastructure_excluded": 0,
                   "successes": g["successes"], "mean_reward": g["successes"] / 8,
                   "mixed": g["mixed"], "all_zero": g["all_zero"], "all_one": g["all_one"],
                   "pass_at_8": g["pass_at_8"]} for g in summary["groups"]]
        replays = []
        for index, row in enumerate(batch["rows"]):
            t, group = row["trajectory"], groups[index // 8]
            mu = [s["log_mu"] for s in t["steps"]]
            pi = [_f32(v + logp_gap) for v in mu]
            gaps = [p - m for p, m in zip(pi, mu)]
            advantage, length = row["reward"] - group["mean_reward"], len(pi)
            denominator = mixed * 8 * length
            # Same float32 detached ratio formula as the producer. The actual
            # upstream loss and frozen control provide independent test oracles.
            terms = [_f32(_f32(_f32(math.exp(_f32(max(-20., min(20., p - m))))) * advantage) * p)
                     if .8 < _f32(math.exp(_f32(p - m))) < 1.28 else 0. for p, m in zip(pi, mu)]
            loss = _f32(-math.fsum(terms) / denominator) if advantage else 0.
            replay = {"all_tokens": _stats(gaps), "nonforced_tokens": _stats(gaps),
                      "parent_id": row["parent_id"], "trajectory_id": t["trajectory_id"],
                      "replay_event_id": 64 + 2 * index,
                      "backward_event_id": 65 + 2 * index if advantage else None,
                      "update_batch_id": batch_id, "log_pi": pi, "log_mu": mu,
                      "peak_memory_bytes": 1024, "peak_reserved_bytes": 2048,
                      "checkpointing_active": True, "training_mode": True,
                      "prompt_and_tool_loss_masked": True, "forced_tokens": 0,
                      "original_token_replay": True, "cache_mode": "cached", "seconds": .02 if advantage else .01,
                      "group_advantage": advantage, "eligible_group_size": 8, "mixed_group_count": mixed,
                      "original_generated_length": length, "gradient_weight": 1. / denominator if advantage else 0.,
                      "detached_DDIS_loss": loss}
            if advantage:
                replay["backward_seconds"] = .01
            replays.append(replay)
        numeric_gate = {"maximum_absolute_gap": .2, "minimum_unclipped_fraction": 1.,
                        "maximum_replay_seconds": 30., "maximum_peak_bytes": 72 * 1024**3,
                        "fixture_only": False, "maximum_p95_gap": .05,
                        "maximum_reserved_bytes": 80 * 1024**3, "maximum_batch_replay_backward_seconds": 600.}
        update = {"optimizer_committed": True, "optimizer_dispatched": True, "groups": groups,
                  "planned_attempts": 64, "batch_index": batch_index, "parent_ids": parents,
                  "session_planned_attempts": 256, "eligible_attempts": 64, "not_reached": 0,
                  "infrastructure_excluded": 0, "actually_dispatched": 64, "replays": replays,
                  "backward_calls": mixed * 8, "update_batch_id": batch_id,
                  "maximum_batch_replay_backward_seconds": 600., "batch_id": batch_id,
                  "batch_started_monotonic": 1000., "batch_deadline": 1600., "batch_replay_started": 1000.1,
                  "numerical_gate": {"admitted": True, "failures": [], "gate": numeric_gate,
                                     "per_trajectory": replays, "per_parent_ids": parents},
                  "whole_replay_backward_seconds": 2., "peak_allocated_bytes": 1024,
                  "peak_reserved_bytes": 2048, "optimizer_event_id": 192,
                  "gradient_norm": .5, "policy_version": after["policy_version"],
                  "batch_finished_monotonic": 1003., "status": "committed",
                  "gradient_divisor": "mixed-groups * eligible-group-size * original-generated-length"}
        update["batch_acknowledgment"] = {"batch_id": batch_id, "batch_index": batch_index,
            "parent_ids": parents, "status": "committed", "before_policy_version": before["policy_version"],
            "after_policy_version": after["policy_version"], "rl_updates": batch_index + 1,
            "physical_attempted_batches": batch_index + 1, "rl_stop_reason": None}
    audit = {"batch": batch, "summary": summary, "update": update,
             "status": "updated" if mixed else "zero-signal", "batch_index": batch_index,
             "parent_ids": parents, "policy_before": before, "policy_after": after,
             "admission": {"phase": "B", "sweep": batch_index, "batch_index": batch_index,
                           "parent_ids": parents, "admitted": True, "remaining_seconds": 20000.,
                           "projected_B_seconds": 300., "projected_C_growth_seconds": 315.,
                           "required_seconds": 17000., "protected_seconds": 16000.,
                           "forecast_sha256": digest("fabricated forecast"), "cost_forecast": {},
                           "phase_deadline": 7000., "whole_B_spent_seconds": 0.}}
    document = {"format": CONTEXT_FORMAT, "audit_sha256": "0" * 64,
                "batch_context": json.loads(json.dumps(asdict(context))), "training": training,
                "policy_before": before}
    return audit, bind_context_document(audit, document)

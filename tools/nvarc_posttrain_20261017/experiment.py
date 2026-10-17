"""Compact specialist continuation with generated dev selection, not dev NLL.

Only admitted training demonstrations provide gradients/rewards. Initial NVARC
weights have inherited benchmark exposure: this split does not erase that fact.
"""
from __future__ import annotations

import hashlib
import math
import random
import time

from tools.arc2_goal_sprint_20261017.data import canonical, digest, inference_views, loo_example, transform, view_inputs
from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, check_deadline, make_optimizer, restore_state, state_digest
from .codec import encode_example, parse_completion
from .curriculum import ExactCurriculum, PositiveReplay, exact_reward


def panel_ids(tasks, count):
    if type(count) is not int or not 1 <= count <= len(tasks):
        raise ValueError("complete frozen development panel required")
    return sorted(tasks, key=lambda key: hashlib.sha256(("nvarc-dev-v1:" + key).encode()).hexdigest())[:count]


def encoded_loo(task, rng, cfg, *, augment=True, held_index=None):
    demos, query, target = loo_example(task, rng, augment=augment, held_index=held_index)
    return encode_example(demos, query, target, context=cfg["context_tokens"],
                          generation=cfg["generation_tokens"], loss_mode="final"), target


def infer_query(engine, task, query, cfg, *, task_id, views, deadline):
    """Fixed target-free transformed views, inverse mapping, vote/likelihood tie."""
    candidates, receipts = [], []
    # Independent training seeds must not silently change the selection test.
    specs = inference_views(views, seed=cfg.get("evaluation_seed", 20261017), task_id=task_id, demo_count=len(task["train"]))
    for index, view in enumerate(specs):
        try:
            check_deadline(deadline)
            demos, transformed_query = view_inputs(task, query, view)
            example = encode_example(demos, transformed_query, context=cfg["context_tokens"], generation=cfg["generation_tokens"])
            rows = engine.generate(example["prompt_ids"], max_new_tokens=cfg["generation_tokens"], sample=False, deadline=deadline)
        except PhaseDeadline:
            break
        row = rows[0]
        grid = parse_completion(row["input_ids"][row["prompt_length"]:])
        record = {"view": index, "valid": grid is not None, "tokens": row["completion_tokens"],
                  "stop": row["stop"], "demos_dropped": example["demos_dropped"]}
        if grid is not None:
            original = transform(grid, **view["transform"], inverse=True)
            nll = -sum(row["behavior_log_probs"][row["prompt_length"]:]) / row["completion_tokens"]
            found = next((i for i, c in enumerate(candidates) if c["grid"] == original), None)
            if found is None:
                found = len(candidates)
                candidates.append({"grid": original, "votes": 0, "nll_sum": 0.0, "views": []})
            candidates[found]["votes"] += 1
            candidates[found]["nll_sum"] += nll
            candidates[found]["views"].append(index)
            record["candidate"] = found
        receipts.append(record)
    order = sorted(range(len(candidates)), key=lambda i: (-candidates[i]["votes"],
        candidates[i]["nll_sum"] / candidates[i]["votes"], i))
    return {"ranked_grids": [candidates[i]["grid"] for i in order[:2]], "candidates": candidates,
            "ranked_candidate_indices": order, "views": receipts,
            "ranking": "votes-descending-mean-own-view-nll-tie-v1", "complete": len(receipts) == views}


def adapt_task(engine, task, cfg, *, task_id, steps, deadline, audit):
    """Demo-only task adaptation; caller restores selected state for every task.

    Numerical/optimizer errors abort the worker. A deadline before commit leaves
    prior accepted steps intact; it is not presented as optimizer rollback.
    """
    rng = random.Random(hashlib.sha256(canonical([cfg.get("evaluation_seed", 20261017), task_id, "ttt"])).digest())
    optimizer = make_optimizer(engine.model, cfg["ttt_lr"])
    started, accepted, attempted = time.time(), 0, 0
    try:
        for step in range(steps):
            check_deadline(deadline)
            example, _ = encoded_loo(task, rng, cfg)
            attempted += 1
            report = engine.sft_step(example, optimizer, deadline=deadline)
            accepted += int(report["updated"])
            audit("ttt_step", task_id=task_id, attempt=attempted, **report)
    except PhaseDeadline:
        optimizer.zero_grad(set_to_none=True)
    finally:
        del optimizer
    return {"steps": accepted, "attempts": attempted, "wall_seconds": time.time() - started,
            "requested_steps": steps, "all_requested_complete": accepted == steps,
            "data": "demonstrations-only", "optimizer_resumed": False}


def evaluate_panel(engine, tasks, cfg, *, deadline, audit, ttt_steps=0, views=2, ids=None):
    """One frozen held-out demonstration per parent, free autoregressive output."""
    ids = panel_ids(tasks, cfg["dev_parents"]) if ids is None else list(ids)
    if not ids or len(set(ids)) != len(ids) or not set(ids) <= set(tasks):
        raise ValueError("explicit unique development-only panel required")
    started = time.time()
    before = adapter_state(engine.model) if ttt_steps else None
    before_sha = state_digest(before) if before is not None else None
    records, pass1, pass2, valid = [], 0, 0, 0
    try:
        for parent in ids:
            task_started = time.time()
            check_deadline(deadline)
            task = tasks[parent]
            demos, query, target = loo_example(task, random.Random(0), augment=False, held_index=0)
            adapted_task = {"train": demos}
            if ttt_steps:
                if not demos:
                    raise ValueError("TTT development pilot requires at least two original demonstrations")
                restore_state(engine.model, before)
                if state_digest(adapter_state(engine.model)) != before_sha:
                    raise RuntimeError("development task reset differs")
                ttt = adapt_task(engine, adapted_task, cfg, task_id=parent, steps=ttt_steps,
                                 deadline=deadline, audit=audit)
            else:
                ttt = None
            query_started = time.time()
            result = infer_query(engine, adapted_task, query, cfg, task_id=parent, views=views, deadline=deadline)
            ranked = result["ranked_grids"]
            first, second = int(bool(ranked) and ranked[0] == target), int(target in ranked)
            pass1 += first
            pass2 += second
            valid += int(bool(ranked))
            records.append({"parent_id": parent, "pass1": first, "pass2": second, "valid": bool(ranked),
                            "inference_seconds": time.time() - query_started, "ttt": ttt,
                            "query_complete": result["complete"],
                            "task_lifecycle_seconds": time.time() - task_started,
                            "completion_tokens": sum(v["tokens"] for v in result["views"])})
            audit("dev_query", **records[-1])
    except PhaseDeadline:
        pass
    finally:
        if before is not None:
            restore_state(engine.model, before)
            if state_digest(adapter_state(engine.model)) != before_sha:
                raise RuntimeError("development TTT did not restore selected adapter")
    wall = time.time() - started
    protocol = {"ids": ids, "evaluation_seed": cfg.get("evaluation_seed", 20261017), "views": views,
                "ttt_steps": ttt_steps, "context_tokens": cfg["context_tokens"],
                "generation_tokens": cfg["generation_tokens"], "held_demo_index": 0,
                "version": "compact-generated-dev-v1"}
    return {"panel_sha256": hashlib.sha256(canonical(protocol)).hexdigest(), "evaluation_protocol": protocol, "queries": len(ids),
            "completed_queries": sum(r["query_complete"] for r in records),
            "complete": len(records) == len(ids) and all(r["query_complete"] and
                (r["ttt"] is None or r["ttt"]["all_requested_complete"]) for r in records),
            "pass1": pass1, "pass2": pass2, "valid": valid, "records": records,
            "ttt_steps": ttt_steps, "views": views, "wall_seconds": wall,
            "unamortized_setup_restore_seconds": max(0.0, wall - sum(r["task_lifecycle_seconds"] for r in records)),
            "selection_uses_generated_exact": True, "unseen_initialization_claimed": False}


def train_arm(engine, tasks, cfg, *, deadline, audit):
    """Fixed requested work, actual physical costs; not wall/compute matched."""
    arm = cfg["arm"]
    if arm not in {"S", "H"}:
        raise ValueError("explicit continued-SFT or exact-hybrid arm required")
    rng = random.Random(cfg["seed"])
    chooser = ExactCurriculum(tasks, seed=cfg["seed"] + 1)
    replay = PositiveReplay(tasks, per_parent=4, seed=cfg["seed"] + 2)
    optimizer = make_optimizer(engine.model, cfg["learning_rate"])
    counts = {"sft_attempts": 0, "sft_updates": 0, "rl_groups_attempted": 0, "rl_groups_complete": 0,
              "rl_updates": 0, "rollouts": 0, "exact_rollouts": 0, "positive_replay_updates": 0,
              "rollout_microbatches_attempted": 0, "partial_group_rollouts_discarded": 0,
              "zero_signal_groups": 0, "context_rejected": 0, "completed_requested_work": False}
    start_forwards, start_tokens, start_updates = engine.forward_calls, engine.sampled_tokens, engine.optimizer_steps
    started = time.time()
    try:
        for step in range(cfg["sft_steps"] if arm == "S" else cfg["hybrid_warmup_steps"]):
            check_deadline(deadline)
            parent = rng.choice(sorted(tasks))
            counts["sft_attempts"] += 1
            try:
                example, _ = encoded_loo(tasks[parent], rng, cfg)
            except ValueError as exc:
                if "exceeds context" not in str(exc):
                    raise
                counts["context_rejected"] += 1
                continue
            report = engine.sft_step(example, optimizer, deadline=deadline)
            counts["sft_updates"] += int(report["updated"])
            audit("posttrain_sft", parent_id=parent, step=step, **report)
        if arm == "H":
            for group_number in range(cfg["rl_groups"]):
                check_deadline(deadline)
                counts["rl_groups_attempted"] += 1
                parent, allocation = chooser.choose()
                demos, query, target = loo_example(tasks[parent], rng)
                example = encode_example(demos, query, context=cfg["context_tokens"], generation=cfg["generation_tokens"])
                rows = []
                group_id = f"{cfg['job_id']}:{group_number}:{parent}"
                policy_id = hashlib.sha256(canonical([cfg["job_id"], engine.optimizer_steps, group_id])).hexdigest()
                # No updates between microbatches: all eight belong to one policy.
                for offset in range(0, cfg["group_size"], cfg["rollout_microbatch"]):
                    counts["rollout_microbatches_attempted"] += 1
                    batch = engine.generate(example["prompt_ids"], count=min(cfg["rollout_microbatch"], cfg["group_size"] - offset),
                                            max_new_tokens=cfg["generation_tokens"], sample=True, deadline=deadline)
                    counts["rollouts"] += len(batch)
                    for index, row in enumerate(batch):
                        predicted = parse_completion(row["input_ids"][row["prompt_length"]:])
                        row.update(group_id=group_id, sample_id=f"{group_id}:{offset+index}", reward=exact_reward(predicted, target))
                        counts["exact_rollouts"] += int(row["reward"])
                        rows.append(row)
                rewards = [row["reward"] for row in rows]
                counts["rl_groups_complete"] += 1
                chooser.observe(parent, rewards)
                report = engine.af3_update(rows, optimizer, expected_groups=[group_id], group_size=cfg["group_size"], deadline=deadline)
                counts["rl_updates"] += int(report["updated"])
                counts["zero_signal_groups"] += int(report.get("reason") == "zero_reward_signal")
                audit("exact_af3_group", parent_id=parent, allocation=allocation, exact=sum(rewards),
                      group_number=group_number, **report)
                for row in rows:
                    replay.add(parent, row, target=target, policy_digest=policy_id, model_identity=engine.base_identity)
                positive = replay.sample()
                if positive is not None:
                    report = engine.sft_step(positive, optimizer, deadline=deadline)
                    counts["positive_replay_updates"] += int(report["updated"])
                    audit("separate_exact_positive_ce", parent_id=positive["parent_id"], **report)
                else:
                    # All-wrong does not manufacture an RL update. Use the real
                    # train demonstration as a separately metered SFT fallback.
                    example, _ = encoded_loo(tasks[parent], rng, cfg)
                    counts["sft_attempts"] += 1
                    report = engine.sft_step(example, optimizer, deadline=deadline)
                    counts["sft_updates"] += int(report["updated"])
                    audit("zero_positive_supervised_support", parent_id=parent, **report)
        counts["completed_requested_work"] = True
    except PhaseDeadline:
        optimizer.zero_grad(set_to_none=True)
        counts["stop_reason"] = "platform_phase_deadline"
    finally:
        del optimizer
    counts["partial_group_rollouts_discarded"] = counts["rollouts"] - counts["rl_groups_complete"] * cfg["group_size"]
    counts.update(wall_seconds=time.time() - started, forward_calls=engine.forward_calls - start_forwards,
                  sampled_tokens=engine.sampled_tokens - start_tokens, committed_updates=engine.optimizer_steps - start_updates,
                  replay_size=len(replay), curriculum=chooser.report(),
                  reward="exact-only", shaping_rewards=False, equal_compute_claimed=False,
                  treatment="continued-sft" if arm == "S" else "warmup-sft+adaptive-exact-af3+separate-positive-ce")
    return counts


def select_checkpoint(reports):
    """Require complete identical generated panels; prefer lower cost on ties."""
    if not reports:
        raise ValueError("checkpoint reports required")
    panels = {r["dev"]["panel_sha256"] for r in reports}
    settings = {(r["dev"]["queries"], r["dev"]["views"], r["dev"]["ttt_steps"]) for r in reports}
    if len(panels) != 1 or len(settings) != 1 or any(not r["dev"]["complete"] for r in reports):
        raise ValueError("complete identical autoregressive development panels required")
    return sorted(reports, key=lambda r: (-r["dev"]["pass2"], -r["dev"]["pass1"],
        -r["dev"]["valid"], r["training_seconds"], r["checkpoint_id"]))[0]

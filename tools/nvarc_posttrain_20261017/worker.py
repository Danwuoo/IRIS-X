"""Fresh-process, single-adapter worker for one owned compact-model experiment.

The parent imports no CUDA runtime. Workers share a device, not mutable models,
optimizers, checkpoints or random streams. Evaluator inputs are never accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
import traceback

import torch

from tools.arc2_goal_sprint_20261017.data import canonical, digest, load_data
from tools.arc2_goal_sprint_20261017.launch import TRAINING_MANIFEST_SHA256, SOLVER_MANIFEST_SHA256, verify_inventory
from tools.arc2_goal_sprint_20261017.model import adapter_state, check_deadline, make_optimizer, restore_state, state_digest, PhaseDeadline
from tools.arc2_goal_sprint_20261017.run import Audit, atomic_json
from .codec import encode_example
from .engine import CompactEngine
from .experiment import adapt_task, evaluate_panel, infer_query, panel_ids, train_arm
from .materials import verify_model


def topology():
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise ValueError("this successor requires exactly one actual CUDA device")
    prop = torch.cuda.get_device_properties(0)
    free, total = torch.cuda.mem_get_info(0)
    identity = str(getattr(prop, "uuid", None) or f"{prop.name}:{total}:{prop.major}.{prop.minor}")
    return {"measured": True, "device_count": 1, "device_identity": identity,
            "name": prop.name, "total_bytes": total, "free_bytes": free,
            "compute_capability": [prop.major, prop.minor], "torch": torch.__version__,
            "cuda": torch.version.cuda, "hardware_partition_claimed": False}


def wait_release(cfg):
    while not Path(cfg["release_path"]).exists():
        check_deadline(cfg["deadline_epoch"])
        time.sleep(0.05)
    release = json.loads(Path(cfg["release_path"]).read_bytes())
    if release.get("job_id") != cfg["job_id"] or release.get("released") is not True:
        raise ValueError("worker release does not match owned experiment")


def settings(cfg):
    defaults = {"context_tokens": 8192, "generation_tokens": 931, "group_size": 8,
        "rollout_microbatch": 2, "sft_steps": 1024, "hybrid_warmup_steps": 256,
        "rl_groups": 64, "dev_parents": 24, "learning_rate": 2e-5,
        "ttt_lr": 5e-5, "ttt_steps": 32, "public_views": 8}
    override = cfg.get("parameters", {})
    if not isinstance(override, dict) or set(override) - set(defaults):
        raise ValueError("unknown or protected experiment parameter")
    result = {**defaults, **override, "job_id": cfg["job_id"], "arm": cfg["arm"], "seed": cfg["seed"]}
    for key in ("context_tokens", "generation_tokens", "group_size", "rollout_microbatch", "dev_parents", "public_views"):
        if type(result[key]) is not int or result[key] < 1:
            raise ValueError("positive integer experiment parameter required: " + key)
    if (result["context_tokens"] != 8192 or result["generation_tokens"] != 931
            or result["group_size"] != 8 or result["rollout_microbatch"] not in (1, 2, 4)
            or result["public_views"] not in (2, 8, 16) or result["dev_parents"] > 200):
        raise ValueError("frozen compact workload dimensions differ")
    for key in ("sft_steps", "hybrid_warmup_steps", "rl_groups", "ttt_steps"):
        if type(result[key]) is not int or not 0 <= result[key] <= 100000:
            raise ValueError("bounded physical work count required")
    if not 1 <= result["ttt_steps"] <= 128:
        raise ValueError("this timed TTT recipe requires 1..128 requested steps")
    for key in ("learning_rate", "ttt_lr"):
        if type(result[key]) not in (int, float) or not math.isfinite(result[key]) or not 0 < result[key] <= .001:
            raise ValueError("finite bounded learning rate required")
    return result


def resource_probe(engine, cfg, *, deadline):
    """Identical synthetic fixed work, discarded after each topology/repeat.

    Artificial binary rewards below exercise actual DDIS backward memory only.
    They are NOT ARC rewards, model successes, or post-training evidence.
    Cached decoding deliberately ignores EOS for a fixed worst-length allocation;
    the scientific generator always stops at EOS and never uses this routine.
    """
    # Include model loading/adapter creation peaks as well as the active probe.
    optimizer = make_optimizer(engine.model, cfg["learning_rate"])
    tokens, updates, started = 0, 0, time.time()
    for length in (2048, 4096, 8192):
        prompt = [14, 11, 10] + [i % 10 for i in range(length - 7)] + [15, 14, 12, 10]
        # Total sequence length includes the two supervised completion symbols.
        prompt = prompt[:-2]
        report = engine.sft_step({"prompt_ids": prompt, "completion_ids": [1, 15], "demos_dropped": 0}, optimizer, deadline=deadline)
        tokens += report["tokens"]
        updates += int(report["updated"])
    engine.model.eval()
    batch, decode_steps, context = cfg["rollout_microbatch"], 64, cfg["context_tokens"]
    prefix = [14, 11, 10] + [i % 10 for i in range(context - decode_steps - 3)]
    cache = out = current = attention = None
    try:
        with torch.no_grad():
            current = torch.tensor([prefix] * batch, device=engine.device)
            attention = torch.ones_like(current)
            for step in range(decode_steps):
                check_deadline(deadline)
                input_tokens = current.numel()
                with engine.autocast():
                    out = engine.model(input_ids=current, attention_mask=attention, past_key_values=cache,
                                       use_cache=True, logits_to_keep=1)
                engine.forward_calls += 1
                cache = out.past_key_values
                current = out.logits[:, -1].argmax(-1, keepdim=True)
                attention = torch.cat([attention, attention.new_ones((batch, 1))], dim=1)
                tokens += input_tokens
    finally:
        cache = out = current = attention = None
    rows = []
    for index in range(cfg["group_size"]):
        prompt = [14, 11, 10] + [i % 10 for i in range(57)] + [15, 14, 12, 10]
        completion = [(index + i) % 10 for i in range(7)] + [15]
        ids = prompt + completion
        with torch.no_grad():
            old = engine.completion_logps(ids, len(prompt)).cpu().tolist()
        rows.append({"input_ids": ids, "prompt_length": len(prompt), "completion_tokens": len(completion),
                     "behavior_log_probs": old, "group_id": "resource-only", "sample_id": str(index), "reward": float(index % 2)})
        tokens += len(ids)
    report = engine.af3_update(rows, optimizer, expected_groups=["resource-only"], group_size=cfg["group_size"], deadline=deadline)
    tokens += sum(len(row["input_ids"]) for row in rows)
    updates += int(report["updated"])
    del optimizer
    engine.sync()
    return {"tokens": tokens, "updates": updates, "active_seconds": time.time() - started,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(engine.device),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(engine.device),
            "synthetic_resource_work_only": True, "scientific_reward_or_effectiveness_claimed": False,
            "fixed_decode_steps": decode_steps, "full_context_tokens": context, "af3_replay": report}


def run_public(engine, public, cfg, *, deadline, audit, output):
    selected = adapter_state(engine.model)
    selected_sha = state_digest(selected)
    pools = {"format": "irisx/arc-offline-pools-v1", "run_id": cfg["job_id"],
        "method": "official NVARC specialist continuation plus demo-only TTT",
        "challenges_digest": digest(public), "records": [], "parent_wall_seconds": None}
    full = {"format": "irisx/private-full-candidates-v1", "run_id": cfg["job_id"], "records": []}
    # Initialize ALL queries before any model work; failed/missing results stay.
    for key in sorted(public):
        pools["records"].append({"task_id": key, "tests": [{"test_index": i, "input_digest": digest(q["input"]),
            "ranked_grids": [], "status": "not_attempted"} for i, q in enumerate(public[key]["test"])]})
    atomic_json(output / "pools.json", pools)
    started = time.time()
    completed = True
    adaptations = []
    try:
        for number, record in enumerate(pools["records"]):
            check_deadline(deadline)
            key, task = record["task_id"], public[record["task_id"]]
            task_start = time.time()
            task_deadline = min(deadline, task_start + (deadline - task_start) / (120 - number))
            restore_state(engine.model, selected)
            if state_digest(adapter_state(engine.model)) != selected_sha:
                raise RuntimeError("task-local adapter reset differs")
            adaptation = adapt_task(engine, {"train": task["train"]}, cfg, task_id=key, steps=cfg["ttt_steps"],
                                    deadline=task_start + (task_deadline - task_start) / 3, audit=audit)
            adaptations.append({"task_id": key, **adaptation})
            completed = completed and adaptation["all_requested_complete"]
            atomic_json(output / "task-adaptations.json", adaptations)
            for index, query in enumerate(task["test"]):
                remaining_queries = len(task["test"]) - index
                query_deadline = min(task_deadline, time.time() + max(0, task_deadline - time.time()) / remaining_queries)
                try:
                    result = infer_query(engine, task, query["input"], cfg, task_id=key,
                                         views=cfg["public_views"], deadline=query_deadline)
                    record["tests"][index].update(ranked_grids=result["ranked_grids"],
                                                   status="complete" if result["complete"] else "partial")
                    completed = completed and result["complete"]
                    full["records"].append({"task_id": key, "test_index": index, "input_digest": digest(query["input"]),
                        **{k: result[k] for k in ("candidates", "ranked_candidate_indices", "views", "ranking")}})
                except PhaseDeadline:
                    completed = False
                    record["tests"][index]["status"] = "deadline"
                atomic_json(output / "pools.json", pools)
                atomic_json(output / "full-candidate-pools.json", full)
    except PhaseDeadline:
        completed = False
    finally:
        restore_state(engine.model, selected)
        if state_digest(adapter_state(engine.model)) != selected_sha:
            raise RuntimeError("PUBLIC adaptation did not restore pre-public state")
        pools["parent_wall_seconds"] = time.time() - started
        atomic_json(output / "pools.json", pools)
        atomic_json(output / "full-candidate-pools.json", full)
    return {"complete": completed, "tasks": 120, "queries": 167,
        "queries_complete": all(t["status"] == "complete" for r in pools["records"] for t in r["tests"]),
        "requested_adaptation_complete": len(adaptations) == 120 and all(r["all_requested_complete"] for r in adaptations),
        "ttt_committed_updates": sum(r["steps"] for r in adaptations), "ttt_requested_per_task": cfg["ttt_steps"],
        "nonempty_queries": sum(bool(t["ranked_grids"]) for r in pools["records"] for t in r["tests"]),
        "wall_seconds": time.time() - started, "selected_state_sha256": selected_sha,
        "inherited_exposure_qualified": True, "clean_generalization_claimed": False}


def run(cfg):
    started = time.time()
    output = Path(cfg["output_dir"])
    params = settings(cfg)
    audit = Audit(output / "audit.jsonl")
    torch.set_num_threads(max(1, int(cfg.get("cpu_threads", 1))))
    device = topology()
    if cfg.get("device_identity") != device["device_identity"]:
        raise ValueError("actual GPU device differs from controller topology probe")
    fraction = cfg.get("allocator_fraction", 1.0)
    if type(fraction) not in (int, float) or not 0 < fraction <= 1:
        raise ValueError("allocator fraction must be explicit and bounded")
    torch.cuda.set_per_process_memory_fraction(fraction, 0)
    identity = verify_model(cfg["model_root"], cfg["variant"])
    train = dev = public = split = None
    if cfg["mode"] != "probe":
        verify_inventory(Path(cfg["public_path"]).parent, SOLVER_MANIFEST_SHA256)
        train, dev, public, split = load_data(cfg["training_root"], cfg["training_manifest_path"], cfg["public_path"],
                                            expected_manifest_sha256=TRAINING_MANIFEST_SHA256)
    engine = CompactEngine.load(cfg["model_root"], base_identity=identity, variant=cfg["variant"], seed=cfg["seed"],
                                adapter_seed=cfg.get("adapter_seed", 731 if cfg["variant"] == "2b" else 739))
    resumed = None
    if cfg.get("checkpoint") is not None:
        resumed = engine.load_checkpoint(cfg["checkpoint"])
    ready = {"job_id": cfg["job_id"], "ready": True, "device": device,
             "base_identity": identity, "trainables": engine.trainable_inventory,
             "allocator_fraction": fraction, "allocator_is_hardware_partition": False,
             "load_seconds": time.time() - started, "resumed": resumed}
    atomic_json(Path(cfg["ready_path"]), ready)
    wait_release(cfg)
    active = time.time()
    result = {"job_id": cfg["job_id"], "mode": cfg["mode"], "source_identity": cfg["source_identity"],
              "workload_identity": cfg["workload_identity"], "device_identity": device["device_identity"],
              "model_identity": identity, "completed": False, "measured": True, "seed": cfg["seed"]}
    deadline = cfg["deadline_epoch"]
    if cfg["mode"] == "probe":
        result.update(resource_probe(engine, params, deadline=deadline), completed=True)
    elif cfg["mode"] == "pilot":
        eligible = {k: t for k, t in dev.items() if len(t["train"]) >= 2}
        ids = panel_ids(eligible, 4)
        panel = evaluate_panel(engine, eligible, params, deadline=deadline, audit=audit,
                               ttt_steps=params["ttt_steps"], views=params["public_views"], ids=ids)
        result.update(pilot=panel, completed=panel["complete"])
    elif cfg["mode"] == "train":
        origin = {"phase": "pre_public", "public_ttt_applied": False, "public_labels_used": False,
                  "job_id": cfg["job_id"], "source_identity": cfg["source_identity"], "training_split": split}
        base_checkpoint = engine.save_checkpoint(output / "baseline", origin={**origin, "treatment": "untouched-specialist-adapter"})
        baseline = evaluate_panel(engine, dev, params, deadline=min(deadline, cfg["training_deadline_epoch"]), audit=audit)
        atomic_json(output / "baseline-evidence.json", {"job_id": cfg["job_id"], "source_identity": cfg["source_identity"],
                    "device_identity": device["device_identity"], "workload_identity": cfg["workload_identity"],
                    "model_identity": identity, "checkpoint": base_checkpoint, "dev": baseline,
                    "pre_training": True, "public_labels_used": False})
        training = train_arm(engine, train, params, deadline=min(deadline, cfg["training_deadline_epoch"]), audit=audit)
        checkpoint = engine.save_checkpoint(output / "posttrained", origin={**origin, "treatment": training["treatment"]})
        final = evaluate_panel(engine, dev, params, deadline=deadline, audit=audit)
        result.update(baseline=baseline, dev=final, training=training, baseline_checkpoint=base_checkpoint,
                      checkpoint=checkpoint, completed=baseline["complete"] and final["complete"])
    elif cfg["mode"] == "public":
        if resumed is None:
            raise ValueError("PUBLIC requires independently selected pre-public checkpoint")
        report = run_public(engine, public, params, deadline=deadline, audit=audit, output=output)
        result.update(public=report, completed=report["complete"])
    else:
        raise ValueError("unknown worker mode")
    engine.sync()
    result.update(active_seconds=time.time() - active, cold_startup_seconds=active - started,
                  wall_seconds=time.time() - started, forward_calls=engine.forward_calls,
                  sampled_tokens=engine.sampled_tokens, committed_updates=engine.optimizer_steps,
                  peak_allocated_bytes=torch.cuda.max_memory_allocated(engine.device),
                  peak_reserved_bytes=torch.cuda.max_memory_reserved(engine.device),
                  training_split=split, inherited_exposure_qualified=True,
                  clean_generalization_claimed=False, optimizer_shared=False, mutable_adapter_shared=False)
    atomic_json(output / "result.json", result)
    audit("worker_complete", job_id=cfg["job_id"], mode=cfg["mode"], completed=result["completed"],
          wall_seconds=result["wall_seconds"], committed_updates=engine.optimizer_steps)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--topology", action="store_true")
    args = parser.parse_args()
    if args.topology:
        print(json.dumps(topology(), sort_keys=True), flush=True)
        return
    cfg = json.loads(Path(args.config).read_bytes())
    try:
        run(cfg)
    except BaseException as error:
        atomic_json(Path(cfg["output_dir"]) / "failure.json", {"job_id": cfg["job_id"],
            "error_type": type(error).__name__, "completed": False, "epoch": time.time()})
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()

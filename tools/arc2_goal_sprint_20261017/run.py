"""Goal-driven SFT -> upstream AF3 RL -> control -> dev selection -> TTT.

This solver process never imports an evaluator or opens a PUBLIC answer file.
Its output is a truth-free candidate pool. The parent scores only after closure.
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

from tools.arc2_goal_sprint_20261017.data import (IDENTITY, SECOND_VIEW, canonical, digest,
    encode_example, load_data, loo_example, parse_grid, transform)
from tools.arc2_goal_sprint_20261017.model import (Engine, PhaseDeadline, adapter_state,
    check_deadline, make_optimizer, restore_state, state_digest)


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


class Audit:
    def __init__(self, path):
        self.path = Path(path)
        self.started = time.time()
        self.sequence = 0

    def __call__(self, event, **fields):
        self.sequence += 1
        row = {"event": event, "sequence": self.sequence, "epoch": time.time(),
               "elapsed_seconds": time.time() - self.started, **fields}
        with self.path.open("ab") as stream:
            stream.write(canonical(row) + b"\n")
            stream.flush()
        # Logs remain concise and contain no predicted/answer grids.
        if event not in {"sft_step", "ttt_step"} or self.sequence % 50 == 0:
            print(json.dumps(row, ensure_ascii=True), flush=True)

    def trajectory(self, row):
        with (self.path.parent / "training-rollouts.jsonl").open("ab") as stream:
            stream.write(canonical(row) + b"\n")


def reward_components(predicted, target):
    exact = float(predicted == target)
    pixel = 0.0
    if predicted and len(predicted) == len(target) and len(predicted[0]) == len(target[0]):
        pixel = sum(a == b for r, s in zip(predicted, target) for a, b in zip(r, s)) / sum(map(len, target))
    return {"exact": exact, "pixel": pixel, "reward": exact + .2 * pixel}


def encoded_loo(engine, task, rng, cfg, *, augment=True, held_index=None):
    demos, query, target = loo_example(task, rng, augment=augment, held_index=held_index)
    example = encode_example(engine.tokenizer, demos, query, target,
                             context=cfg["context_tokens"], generation=cfg["generation_tokens"])
    return example, target


def sft_phase(engine, tasks, cfg, audit, *, phase, rng, deadline, steps=None, lr=1e-4):
    started = time.time()
    optimizer = make_optimizer(engine.model, lr)
    keys = sorted(tasks)
    successes, attempts, failures = 0, 0, 0
    while time.time() < deadline and (steps is None or successes < steps):
        attempts += 1
        key = rng.choice(keys)
        step_before = None
        try:
            example, _ = encoded_loo(engine, tasks[key], rng, cfg)
            # Optimizer allocation/step can fail after partial parameter mutation.
            # Retain the small adapter, not the 14B base; reset optimizer on abort.
            step_before = adapter_state(engine.model)
            report = engine.sft_step(example, optimizer)
            successes += int(report["updated"])
            audit("sft_step", phase=phase, parent_id=key, attempt=attempts, step=successes, **report)
        except (torch.cuda.OutOfMemoryError, FloatingPointError) as error:
            if step_before is not None:
                restore_state(engine.model, step_before)
                if state_digest(adapter_state(engine.model)) != state_digest(step_before):
                    raise RuntimeError("failed SFT step did not restore adapter") from error
            optimizer.zero_grad(set_to_none=True)
            optimizer = make_optimizer(engine.model, lr)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            failures += 1
            # Change only execution length budget, never truncate a grid.
            previous = cfg["context_tokens"]
            if isinstance(error, torch.cuda.OutOfMemoryError):
                cfg["context_tokens"] = max(4096, previous - 1024)
            audit("sft_step_aborted", phase=phase, parent_id=key, failure=type(error).__name__,
                  previous_context=previous, new_context=cfg["context_tokens"], failed_attempts=failures,
                  adapter_restored=True, optimizer_reset=True, committed=False)
            if failures >= 5:
                raise RuntimeError("repeated SFT numerical/memory failures despite rollback")
        except ValueError as error:
            if "exceeds context" not in str(error):
                raise
            audit("sft_context_rejected", phase=phase, parent_id=key, attempt=attempts)
        finally:
            del step_before
    engine.sync()
    elapsed = time.time() - started
    del optimizer
    audit("sft_phase_complete", phase=phase, steps=successes, attempts=attempts,
          wall_seconds=elapsed, failures=failures, deadline_reached=time.time() >= deadline)
    return {"steps": successes, "attempts": attempts, "wall_seconds": elapsed, "failures": failures}


def rl_phase(engine, tasks, cfg, audit, *, rng, deadline):
    started = time.time()
    optimizer = make_optimizer(engine.model, 2e-5)
    keys = sorted(tasks)
    commits, attempted, completed, physical = 0, 0, 0, 0
    batches = []
    for index in range(cfg["rl_batches"]):
        if time.time() >= deadline:
            break
        attempted += 1
        before = adapter_state(engine.model)
        before_hash = state_digest(before)
        group_ids = rng.sample(keys, cfg["rl_parents_per_batch"])
        rows = []
        batch_started = time.time()
        try:
            for task_id in group_ids:
                demos, query, target = loo_example(tasks[task_id], rng)
                example = encode_example(engine.tokenizer, demos, query,
                             context=cfg["context_tokens"], generation=cfg["generation_tokens"])
                generated = engine.generate(example["prompt_ids"], count=cfg["rl_group_size"], sample=True,
                             max_new_tokens=cfg["generation_tokens"], deadline=deadline)
                for slot, row in enumerate(generated):
                    components = reward_components(parse_grid(row["text"]), target)
                    physical += 1
                    trajectory = {**row, **components, "sample_id": f"batch{index}:{task_id}:{slot}",
                                  "group_id": task_id}
                    rows.append(trajectory)
                    # Private train-only audit retains exact sampled IDs/logps and
                    # reward target, enabling independent replay after the run.
                    if isinstance(audit, Audit):
                        audit.trajectory({**trajectory, "training_target": target,
                            "policy_sha256": before_hash, "batch_index": index,
                            "demos_dropped": example["demos_dropped"], "public_data": False})
            report = engine.af3_update(rows, optimizer, expected_groups=group_ids,
                                      group_size=cfg["rl_group_size"], deadline=deadline)
            after_hash = state_digest(adapter_state(engine.model))
            if report["updated"] and after_hash == before_hash:
                raise RuntimeError("optimizer reported update but adapter bytes unchanged")
            if not report["updated"] and after_hash != before_hash:
                raise RuntimeError("zero-update batch changed adapter")
            commits += int(report["updated"])
            completed += 1
            record = {**report, "batch": index, "before_sha256": before_hash, "after_sha256": after_hash,
                      "exact_solved": sum(r["exact"] for r in rows), "mean_pixel": sum(r["pixel"] for r in rows) / len(rows),
                      "wall_seconds": time.time() - batch_started}
            batches.append(record)
            audit("af3_batch_complete", **record)
        except (PhaseDeadline, torch.cuda.OutOfMemoryError, FloatingPointError) as error:
            restore_state(engine.model, before)
            restored = state_digest(adapter_state(engine.model))
            if restored != before_hash:
                raise RuntimeError("failed AF3 batch did not restore adapter") from error
            optimizer.zero_grad(set_to_none=True)
            optimizer = make_optimizer(engine.model, 2e-5)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            audit("af3_batch_aborted", batch=index, failure=type(error).__name__, complete_trajectories=len(rows),
                  before_sha256=before_hash, restored_sha256=restored,
                  wall_seconds=time.time() - batch_started, committed=False)
            if isinstance(error, PhaseDeadline):
                break
        finally:
            del before, rows
    engine.sync()
    del optimizer
    result = {"attempted_batches": attempted, "complete_batches": completed, "commits": commits,
              "physical_complete_trajectories": physical, "wall_seconds": time.time() - started, "batches": batches}
    audit("af3_phase_complete", **{k: v for k, v in result.items() if k != "batches"})
    return result


def select_arm(engine, states, dev, cfg, audit, deadline):
    keys = sorted(dev, key=lambda key: hashlib.sha256(("dev-panel:" + key).encode()).hexdigest())[:cfg["dev_tasks"]]
    panel = []
    for key in keys:
        example, _ = encoded_loo(engine, dev[key], random.Random(cfg["seed"]), cfg, augment=False, held_index=0)
        panel.append((key, example))
    scores = {}
    try:
        for arm, state in states.items():
            restore_state(engine.model, state)
            values = []
            for key, example in panel:
                check_deadline(deadline)
                values.append(engine.nll(example))
            score = math.fsum(values) / len(values)
            if not math.isfinite(score):
                raise FloatingPointError("invalid dev score")
            scores[arm] = score
            audit("dev_arm", arm=arm, task_count=len(values), mean_nll=score, panel_digest=digest(keys))
        selected = min(scores, key=lambda arm: (scores[arm], list(states).index(arm)))
    except PhaseDeadline:
        # Predeclared fallback, never choose from unequal partial panels or PUBLIC.
        selected = "A"
        audit("dev_incomplete_fallback", selected="A", complete_arm_scores=scores,
              reason="inference_reserve", partial_panel_used_for_selection=False)
    restore_state(engine.model, states[selected])
    audit("selection_sealed", selected=selected, dev_scores=scores,
          selected_sha256=state_digest(states[selected]), public_label_access=False)
    return selected, scores


def solve_public(engine, public, selected_state, cfg, audit, output, *, deadline):
    pools = {"format": "irisx/arc-offline-pools-v1", "run_id": cfg["run_id"],
             "method": "Qwen3-14B LoRA SFT + upstream AF3 DDIS + dev selection + demonstration-only TTT",
             "challenges_digest": digest(public), "records": [], "parent_wall_seconds": None}
    started = time.time()
    selected_hash = state_digest(selected_state)
    atomic_json(output / "pools.json", pools)
    keys = sorted(public)
    for task_number, key in enumerate(keys):
        task = public[key]
        task_start = time.time()
        task_remaining = len(keys) - task_number
        # A per-task share prevents a single hard grid consuming later tasks' inference.
        task_deadline = min(deadline, task_start + max(0, deadline - task_start) / task_remaining)
        restore_state(engine.model, selected_state)
        reset_hash = state_digest(adapter_state(engine.model))
        if reset_hash != selected_hash:
            raise RuntimeError("PUBLIC task adapter reset differs")
        ttt_start = time.time()
        ttt_steps = 0
        optimizer = make_optimizer(engine.model, 5e-5)
        rng = random.Random(cfg["seed"] + task_number)
        # Protect at least two thirds of each task's remaining interval for queries.
        ttt_deadline = task_start + (task_deadline - task_start) / 3
        try:
            for step in range(cfg["ttt_steps"]):
                if time.time() >= ttt_deadline:
                    break
                example, _ = encoded_loo(engine, task, rng, cfg)
                report = engine.sft_step(example, optimizer)
                ttt_steps += int(report["updated"])
                audit("ttt_step", task_id=key, step=step, **report)
        except (torch.cuda.OutOfMemoryError, FloatingPointError, ValueError) as error:
            restore_state(engine.model, selected_state)
            audit("ttt_rollback", task_id=key, failure=type(error).__name__, steps=ttt_steps)
            ttt_steps = 0
        finally:
            del optimizer
        ttt_wall = time.time() - ttt_start
        tests = []
        generation_started = time.time()
        for query_index, query in enumerate(task["test"]):
            candidates = []
            attempted_views = 0
            for view_index, spec in enumerate((IDENTITY, SECOND_VIEW)):
                views_left = (len(task["test"]) - query_index) * 2 - view_index
                view_deadline = time.time() + max(0.0, task_deadline - time.time()) / views_left
                try:
                    check_deadline(view_deadline)
                    demos = [{k: transform(pair[k], **spec) for k in ("input", "output")} for pair in task["train"]]
                    example = encode_example(engine.tokenizer, demos, transform(query["input"], **spec),
                                    context=cfg["context_tokens"], generation=cfg["generation_tokens"])
                    generated = engine.generate(example["prompt_ids"], max_new_tokens=cfg["generation_tokens"],
                                                sample=False, deadline=view_deadline)[0]
                    attempted_views += 1
                    grid = parse_grid(generated["text"])
                    if grid is not None:
                        original = transform(grid, **spec, inverse=True)
                        if original not in candidates:
                            candidates.append(original)
                    audit("public_view", task_id=key, test_index=query_index, view=view_index,
                          valid=grid is not None, completion_tokens=generated["completion_tokens"], stop=generated["stop"],
                          demos_dropped=example["demos_dropped"])
                except (PhaseDeadline, torch.cuda.OutOfMemoryError, FloatingPointError, ValueError) as error:
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    audit("public_view_failed", task_id=key, test_index=query_index, view=view_index,
                          failure=type(error).__name__)
            status = "complete" if attempted_views == 2 else "partial" if candidates else "failed"
            tests.append({"test_index": query_index, "input_digest": digest(query["input"]),
                          "ranked_grids": candidates[:2], "status": status})
        record = {"task_id": key, "task_digest": digest(task), "tests": tests,
                  "timings": {"training_seconds": ttt_wall, "search_seconds": time.time() - generation_started,
                              "total_seconds": time.time() - task_start}}
        pools["records"].append(record)
        pools["parent_wall_seconds"] = time.time() - started
        atomic_json(output / "pools.json", pools)
        audit("public_task_complete", task_id=key, task_number=task_number + 1, ttt_steps=ttt_steps,
              queries=len(tests), nonempty_queries=sum(bool(t["ranked_grids"]) for t in tests),
              reset_sha256=reset_hash, elapsed_seconds=time.time() - task_start)
    return pools


def save_adapter(engine, destination, expected_state):
    """Persist and replay exact adapter bytes without exporting the 14B base."""
    engine.model.save_pretrained(destination, safe_serialization=True)
    engine.tokenizer.save_pretrained(destination)
    from safetensors.torch import load_file
    from peft import get_peft_model_state_dict, set_peft_model_state_dict
    exported = load_file(str(Path(destination) / "adapter_model.safetensors"))
    expected_export = get_peft_model_state_dict(engine.model)
    if (not exported or set(exported) != set(expected_export) or
            any(not bool(torch.isfinite(v).all()) for v in exported.values()) or
            any(not torch.equal(exported[k], expected_export[k].detach().cpu()) for k in exported)):
        raise RuntimeError("exported adapter differs from selected model")
    set_peft_model_state_dict(engine.model, exported)
    fingerprint = state_digest(expected_state)
    if state_digest(adapter_state(engine.model)) != fingerprint:
        raise RuntimeError("adapter save/reload differs")
    return {"adapter_sha256": fingerprint, "tensor_count": len(exported)}


def admit_resource():
    """Check actual allocated memory before attempting the 14B BF16 load.

    A requested accelerator is not evidence of the device the provider supplied.
    Fail explicitly on a small fallback device, rather than hiding allocation
    mismatch behind repeated model OOMs. This is not a remaining-quota gate.
    """
    if not torch.cuda.is_available():
        raise RuntimeError("GPU allocation missing; this solver requires the requested large-memory accelerator")
    actual = {"gpu": torch.cuda.get_device_name(),
              "gpu_bytes": torch.cuda.get_device_properties(0).total_memory}
    if actual["gpu_bytes"] < 80 * 1024**3:
        raise RuntimeError("GPU allocation mismatch for 14B BF16: " + json.dumps(actual))
    return actual


def execute(cfg):
    cfg = dict(cfg)
    defaults = {"seed": 20261017, "training_seconds": 24000, "sft_steps": 3072, "rl_batches": 12,
                "rl_group_size": 8, "rl_parents_per_batch": 8, "ttt_steps": 8,
                "context_tokens": 8192, "generation_tokens": 2048, "dev_tasks": 24}
    for key, value in defaults.items():
        cfg.setdefault(key, value)
    output = Path(cfg["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    if (output / "audit.jsonl").exists():
        raise ValueError("fresh run output required")
    audit = Audit(output / "audit.jsonl")
    started = time.time()
    final_deadline = float(cfg["session_deadline_epoch"]) - 300
    check_deadline(final_deadline)
    torch.manual_seed(cfg["seed"])
    random.seed(cfg["seed"])
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    training, dev, public, receipt = load_data(cfg["training_root"], cfg["training_manifest_path"], cfg["public_path"],
        expected_manifest_sha256=cfg.get("training_manifest_sha256"))
    audit("data_admitted", **receipt)
    atomic_json(output / "effective-config.json", cfg)
    # If a later model/training failure occurs, retain explicit empty predictions
    # with the complete input identity, not a shortened denominator or invented
    # model success. The parent reports solver returncode separately from score.
    atomic_json(output / "pools.json", {"format": "irisx/arc-offline-pools-v1", "run_id": cfg["run_id"],
        "method": "Qwen3-14B goal successor; solver progress incomplete",
        "challenges_digest": digest(public), "records": [], "parent_wall_seconds": None})
    resource = admit_resource()
    audit("gpu_allocation_admitted", **resource)
    engine = Engine.load(cfg["model_path"])
    audit("model_loaded", model_class=type(engine.model).__name__, torch_version=torch.__version__,
          cuda_version=torch.version.cuda, gpu=torch.cuda.get_device_name(),
          gpu_bytes=torch.cuda.get_device_properties(0).total_memory,
          trainable_parameters=sum(p.numel() for p in engine.parameters))
    # This is within-session phase scheduling, not a GPU-quota gate or task stop.
    public_reserve = 13000
    training_deadline = min(time.time() + cfg["training_seconds"], final_deadline - public_reserve)
    train_start = time.time()
    sft_deadline = train_start + max(0, training_deadline - train_start) * .55
    rng = random.Random(cfg["seed"])
    baseline = adapter_state(engine.model)
    a_report = sft_phase(engine, training, cfg, audit, phase="A", rng=rng, deadline=sft_deadline, steps=cfg["sft_steps"])
    if a_report["steps"] == 0:
        raise RuntimeError("no SFT update completed")
    states = {"A": adapter_state(engine.model)}
    if state_digest(states["A"]) == state_digest(baseline):
        raise RuntimeError("SFT did not change adapter")
    del baseline
    audit("anchor_reload_verified", **save_adapter(engine, output / "anchor-adapter", states["A"]))
    # AF3 and control share remaining training wall, measured rather than padded.
    rl_deadline = time.time() + max(0, training_deadline - time.time() - 300) / 2
    b_started = time.time()
    b_report = rl_phase(engine, training, cfg, audit, rng=rng, deadline=rl_deadline)
    states["B"] = adapter_state(engine.model)
    b_report["inner_wall_seconds"] = b_report["wall_seconds"]
    b_report["wall_seconds"] = time.time() - b_started
    c_started = time.time()
    restore_state(engine.model, states["A"])
    c_deadline = min(c_started + b_report["wall_seconds"], training_deadline)
    c_report = sft_phase(engine, training, cfg, audit, phase="C", rng=random.Random(cfg["seed"] + 1),
                         deadline=c_deadline, steps=None)
    states["C"] = adapter_state(engine.model)
    c_report["inner_wall_seconds"] = c_report["wall_seconds"]
    c_report["wall_seconds"] = time.time() - c_started
    matched = c_report["wall_seconds"] >= b_report["wall_seconds"]
    audit("control_cost", rl_full_wall_seconds=b_report["wall_seconds"], control_wall_seconds=c_report["wall_seconds"],
          matched_at_least_rl_wall=matched, idle_padding=False)
    selected, scores = select_arm(engine, states, dev, cfg, audit, final_deadline - 11000)
    selected_state = states[selected]
    selected_hash = state_digest(selected_state)
    audit("checkpoint_reload_verified", **save_adapter(engine, output / "selected-adapter", selected_state))
    del states
    selection = {"selected_arm": selected, "dev_scores": scores, "selected_state_sha256": selected_hash,
                 "A": a_report, "B": b_report, "C": c_report, "control_cost_matched": matched,
                 "data": receipt, "public_labels_used": False}
    atomic_json(output / "selection.json", selection)
    pools = solve_public(engine, public, selected_state, cfg, audit, output, deadline=final_deadline)
    engine.sync()
    summary = {"run_id": cfg["run_id"], "solver_status": "complete", **selection,
               "public_tasks": len(pools["records"]), "public_queries": sum(len(r["tests"]) for r in pools["records"]),
               "public_nonempty_queries": sum(bool(t["ranked_grids"]) for r in pools["records"] for t in r["tests"]),
               "forward_calls": engine.forward_calls, "sampled_tokens": engine.sampled_tokens,
               "optimizer_steps": engine.optimizer_steps, "wall_seconds": time.time() - started,
               "score": None, "score_reason": "parent-only evaluator after solver process closure"}
    atomic_json(output / "run-summary.json", summary)
    audit("solver_complete", public_tasks=summary["public_tasks"], public_queries=summary["public_queries"],
          wall_seconds=summary["wall_seconds"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    try:
        execute(cfg)
    except BaseException as error:
        output = Path(cfg["output_dir"])
        output.mkdir(parents=True, exist_ok=True)
        atomic_json(output / "solver-error.json", {"type": type(error).__name__, "message": str(error),
                    "traceback": traceback.format_exc(), "epoch": time.time()})
        raise


if __name__ == "__main__":
    main()

"""Truth-free, bounded comparison of compact base, eight-step SFT and SFT+TTT."""

from __future__ import annotations

import gc
import math
import random
import time
from pathlib import Path
from typing import Any

from .arc_nvarc_candidates import QwenCandidateBackend, rank_candidates
from .arc_nvarc_data import grid, source_qwen_transform_grid, source_qwen_views, visible_task
from .arc_nvarc_representation import END, GridTokenizer, verify_model_material
from .arc_nvarc_training import TaskLocalAdapter, load_compact_model
from .canonical import digest_value
from .errors import ValidationError

BASE = "sha256:1a8eebd70d811e58c35dc5b1ee27dc18bd73a1066c3ab33adf96ed8427d4c982"
SFT = "sha256:481d9f12d573b39b0703e47b5f8f6f518a7ccd7847824ffb3f0fb96b11f2c3e6"
TRAINING = "sha256:40804d408005b666cb377aab623bd6b0edcfbcdaa4743049d26e7e65500f5fc4"
VOCAB = "sha256:573199335acdb16205158d55457ea6e1c49fb64fb677e3817091b6f46e533422"
TASKS = ("00576224", "c9e6f938", "0d3d703e")
ARMS = ("A", "B", "C")


def check_materials(base: Path, sft: Path) -> dict[str, Any]:
    """Verify every retained byte and the shared row/role/EOS lineage."""
    from .arc_nvarc_combined import sha

    a = verify_model_material(base, BASE, allowed_extra_files={"dataset-metadata.json"})
    b = verify_model_material(sft, SFT, allowed_extra_files={"dataset-metadata.json"})
    if (b.get("kind") != "sft-inference-export" or b.get("base_material_digest") != BASE or
            b.get("training_identity_digest") != TRAINING or
            a["vocabulary_identity_digest"] != VOCAB or b["vocabulary_identity_digest"] != VOCAB or
            not a["tied_embeddings"] or not b["tied_embeddings"]):
        raise ValidationError("A/B/C compact weight ancestry or tying differs")
    for name in ("grid-vocab.json", "grid-tokenizer.json", "generation_config.json"):
        if sha(base / name) != sha(sft / name):
            raise ValidationError("A/B/C vocabulary, role or EOS bytes differ: " + name)
    tokenizer = GridTokenizer(source_chat_newlines=True)
    pair, labels = tokenizer.encode_pair([[1]], [[2]])
    if pair != [14, 11, 10, 1, 15, 14, 12, 10, 2, 15] or labels[-2:] != [2, 15]:
        raise ValidationError("source-role newline grammar differs")
    return {"base_material_digest": BASE, "sft_export_material_digest": SFT,
            "training_identity_digest": TRAINING, "vocabulary_identity_digest": VOCAB,
            "source_chat_newlines": True, "embedding_head_tied": True}


def public_grammar(task: dict) -> dict[str, Any]:
    """Use only unanimous demonstration facts; no test output is accessible."""
    pairs = task["train"]
    shapes = {(len(p["output"]), len(p["output"][0])) for p in pairs}
    if len(shapes) != 1:
        return {"status": "unsupported-shape"}
    shape = next(iter(shapes))
    if shape[0] * (shape[1] + 1) > 64 or shape[0] * shape[1] < 1:
        return {"status": "unsupported-token-bound", "shape": list(shape)}
    palette_rule = all({x for row in p["input"] for x in row} ==
                       {x for row in p["output"] for x in row} for p in pairs)
    test_colors = {x for row in task["test"][0]["input"] for x in row}
    colors = tuple(sorted(test_colors if palette_rule else range(10)))
    return {"status": "supported", "shape": list(shape), "palette_rule": palette_rule,
            "legal_colors": list(colors), "source": "public demonstrations and visible test input"}


def grammar_sequences(query: list[int], next_log_probs, grammar: dict, *,
                      maximum_tokens: int, maximum_expansions: int, sequences: int = 2) -> dict:
    rows, columns = grammar["shape"]
    colors = grammar["legal_colors"]
    length = rows * (columns + 1)
    if grammar["status"] != "supported" or length > maximum_tokens or sequences != 2 or \
            length * sequences > maximum_expansions or not colors:
        raise ValidationError("public grammar exceeds fixed search budget")
    results = []
    for variant in range(sequences):
        suffix, nll = [], 0.0
        for position in range(length):
            logits = next_log_probs(query + suffix)
            if len(logits) != 16 or not all(math.isfinite(float(x)) for x in logits):
                raise ValidationError("nonfinite or noncompact model logits")
            column = position % (columns + 1)
            if column == columns:
                token = END if position == length - 1 else 10
            else:
                remaining = rows * columns - (position - position // (columns + 1) + 1)
                used = {x for x in suffix if 0 <= x <= 9}
                allowed = [x for x in colors if not grammar["palette_rule"] or
                           len(set(colors) - (used | {x})) <= remaining]
                if not allowed:
                    raise ValidationError("public grammar has no legal color")
                allowed.sort(key=lambda x: (-float(logits[x]), x))
                token = allowed[1] if variant == 1 and position == 0 and len(allowed) > 1 else allowed[0]
            suffix.append(token)
            nll -= float(logits[token])
        results.append({"tokens": suffix, "eos": True, "beam_nll": nll})
    return {"sequences": results, "expansions": length * sequences,
            "stop_reason": "public-grammar-complete", "forced_structure": True}


def _seed(seed: int) -> None:
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.cuda.empty_cache()


def solve_one(task: dict, backend: QwenCandidateBackend, plan: dict, event) -> dict:
    """Persist raw completions separately from inverse grids and truth-free rank."""
    from .arc_nvarc_qwen35_adapter import full_prefix_log_probs

    tokenizer = GridTokenizer(source_chat_newlines=True)
    options = plan["limits"]
    views = source_qwen_views(task, 0, seed=options["view_seed"], color_repeats=1)
    raw, mapped, diagnostics = [], [], []
    verification = {}
    forwards = 0
    backend.begin_task(task)
    try:
        if backend.adapter is not None:
            observation = backend.adapter.last_observation
            if (observation is None or observation.get("steps") != 1 or
                    not 0 < observation.get("training_tokens", 0) <= 256):
                raise ValidationError("task-local TTT step or token bound differs")
            event({"kind": "ttt", "status": "complete", "task_id": task["task_id"],
                   "index": 1, "observation": observation})
        for view_index, view in enumerate(views[:options["calls_per_task"]]):
            grammar = public_grammar(view["task"])
            if grammar["status"] != "supported":
                diagnostics.append({"view": view_index, "stop_reason": grammar["status"], "grammar": grammar})
                continue
            query = tokenizer.encode_query(view["task"], 0)
            index = len(diagnostics) + 1
            event({"kind": "generation", "status": "reserved", "task_id": task["task_id"], "index": index,
                   "view": view_index, "query_digest": digest_value(query)})
            def next_probs(prefix):
                nonlocal forwards
                forwards += 1
                if forwards > options["expansions_per_task"]:
                    raise ValidationError("generation expansion ceiling")
                return full_prefix_log_probs(backend.model, prefix)
            generated = grammar_sequences(query, next_probs, grammar,
                maximum_tokens=options["new_tokens_per_sequence"],
                maximum_expansions=options["expansions_per_call"])
            observation = {"view": view_index, "grammar": grammar, "query_tokens": len(query),
                           "query_digest": digest_value(query), "expansions": generated["expansions"],
                           "stop_reason": generated["stop_reason"]}
            diagnostics.append(observation)
            event({"kind": "generation", "status": "complete", "task_id": task["task_id"],
                   "index": index, "view": view_index, "observation": observation,
                   "raw_sequences": generated["sequences"]})
            for seq_index, seq in enumerate(generated["sequences"]):
                record = {"view": view_index, "sequence": seq_index, **seq,
                          "view_spec": view["spec"]}
                raw.append(record)
                candidate = tokenizer.parse_completion(seq["tokens"], stopped_on_eos=seq["eos"])
                if candidate is None:
                    record["parse_stop_reason"] = "invalid-or-incomplete-grid"
                    continue
                inverse = source_qwen_transform_grid(candidate, view["spec"], inverse=True)
                key = digest_value(inverse)
                if key not in verification:
                    if len(verification) >= options["verifications_per_task"]:
                        record["parse_stop_reason"] = "verification-ceiling"
                        continue
                    event({"kind": "verification", "status": "reserved", "task_id": task["task_id"],
                           "index": len(verification) + 1, "candidate_digest": key})
                    verification[key] = backend.verify(task, 0, inverse)
                    event({"kind": "verification", "status": "complete", "task_id": task["task_id"],
                           "index": len(verification), "candidate_digest": key,
                           "inverse_grid": inverse, "verification_nll": verification[key]})
                mapped.append({"grid": inverse, "complete": True, "source": f"view{view_index}:seq{seq_index}",
                               "beam_nll": seq["beam_nll"], "verification_nll": verification[key],
                               "view_spec": view["spec"]})
        ranked = rank_candidates(mapped, policy="source-kgmon")
        return {"task_id": task["task_id"], "raw_sequences": raw, "inverse_candidates": mapped,
                "ranked": ranked, "attempts": [x["grid"] for x in ranked[:2]],
                "status": "complete" if len(ranked) >= 2 else "missing-candidate",
                "generation_observations": diagnostics, "generation_calls": sum(x.get("expansions", 0) > 0 for x in diagnostics),
                "returned_sequences": len(raw), "verification_calls": len(verification),
                "generation_forwards": forwards, "verification_forwards": backend.forward_calls,
                "ranking_policy": "source-kgmon", "contains_evaluator_truth": False}
    finally:
        backend.end_task()


def run_arm(arm: str, model_path: Path, visible: dict, plan: dict, output: Path, event) -> dict:
    import torch
    from .arc_nvarc_combined import atomic

    if arm not in ARMS:
        raise ValidationError("unknown comparison arm")
    start = time.monotonic()
    model = load_compact_model(model_path, dtype="bfloat16")
    model.to("cuda:0").eval()
    loaded = time.monotonic()
    adapter = TaskLocalAdapter(model, plan["adaptation"]) if arm == "C" else None
    backend = QwenCandidateBackend(model, task_adapter=adapter)
    backend.augmentation = "source-qwen"
    backend.representation = "source-qwen"
    rows = []
    try:
        for task_id in TASKS:
            task = visible_task(task_id, visible[task_id])
            _seed(plan["limits"]["model_seed"])
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
            task_start = time.monotonic()
            try:
                if arm == "C":
                    event({"kind": "ttt", "status": "reserved", "task_id": task_id,
                           "index": 1, "maximum_steps": 1, "maximum_training_tokens": 256})
                row = solve_one(task, backend, plan, event)
                row["ttt"] = adapter.last_observation if adapter is not None else None
            except Exception as exc:
                row = {"task_id": task_id, "status": "failed", "error_type": type(exc).__name__,
                       "error_message": str(exc)[:1000], "attempts": [], "contains_evaluator_truth": False}
            row.update(arm=arm, task_wall_seconds=time.monotonic() - task_start,
                       peak_cuda_allocated_mib=torch.cuda.max_memory_allocated() / 1048576)
            rows.append(row)
            atomic(output / (arm + "-" + task_id + ".json"), row)
        report = {"arm": arm, "model_material_digest": BASE if arm == "A" else SFT,
                  "load_seconds": loaded - start, "wall_seconds": time.monotonic() - start,
                  "ttt_enabled": arm == "C", "tasks": [x["task_id"] for x in rows],
                  "statuses": [x["status"] for x in rows], "contains_evaluator_truth": False}
        atomic(output / (arm + "-summary.json"), report)
        return report
    finally:
        del backend, adapter, model
        gc.collect()
        torch.cuda.empty_cache()


def run_worker(plan_path: Path, visible_path: Path, base: Path, sft: Path,
               bundle: Path, hardware_path: Path, output: Path, expected_digest: str) -> dict:
    import json
    import os
    import subprocess
    import torch
    from .arc_nvarc_combined import atomic, check_logical_device, read, sha
    from .arc_nvarc_hardware import collect_hardware_inventory
    from .arc_nvarc_source_bundle import verify_bundle
    from .arc_nvarc_upstream import source_bundle, qwen_cell

    plan, visible = read(plan_path), read(visible_path)
    if (digest_value(plan) != expected_digest or plan.get("approved") is not True or
            plan.get("owner_decision") != "Decision 0044" or
            plan.get("run_id") != "nvarc-compact-abc-editor-001" or
            sha(visible_path) != plan["visible_sha256"] or set(visible) != set(TASKS)):
        raise ValidationError("exact ABC plan or visible workload differs")
    if set(plan["sft_train_parent_ids"]) & set(TASKS):
        raise ValidationError("selected tasks overlap SFT train parent IDs")
    hardware = read(hardware_path)
    smi = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,uuid",
        "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True, timeout=30)
    logical = collect_hardware_inventory(torch, smi.stdout,
        lambda raw: atomic(output / "worker-hardware-raw.json", raw))
    check_logical_device("m2", hardware, hardware["assignments"]["m2"]["uuid"],
                         logical, os.environ.get("CUDA_VISIBLE_DEVICES"))
    material = check_materials(base, sft)
    atomic(output / "material-verification.json", material)
    verify_bundle(bundle, plan["source_bundle_digest"])
    ledger = {"format": "irisx/nvarc-abc-call-ledger-v1", "run_id": plan["run_id"],
              "plan_digest": expected_digest, "records": []}
    def event(record):
        entry = {**record, "arm": current_arm[0]}
        kind, status = entry.get("kind"), entry.get("status")
        limits = {"ttt": 1, "generation": plan["limits"]["calls_per_task"],
                  "verification": plan["limits"]["verifications_per_task"]}
        if (kind not in limits or status not in {"reserved", "complete"} or
                entry["arm"] not in ARMS or entry.get("task_id") not in TASKS or
                type(entry.get("index")) is not int or not 1 <= entry["index"] <= limits[kind] or
                (kind == "ttt" and entry["arm"] != "C")):
            raise ValidationError("ABC call reservation exceeds reviewed plan")
        previous = [x for x in ledger["records"] if all(x[key] == entry[key] for key in
                    ("arm", "task_id", "kind", "index"))]
        if (status == "reserved" and previous or
                status == "complete" and (len(previous) != 1 or previous[0]["status"] != "reserved")):
            raise ValidationError("ABC call must be reserved exactly once before completion")
        ledger["records"].append(entry)
        atomic(output / "call-ledger.json", ledger)
    current_arm = [None]
    summary = {"format": "irisx/nvarc-abc-worker-v1", "run_id": plan["run_id"],
               "plan_digest": expected_digest, "actual_arm_order": [], "arms": {},
               "contains_evaluator_truth": False}
    with source_bundle(bundle, plan["source_bundle_digest"]):
        for name in ("arc_loader.py", "arc_decoder.py", "arc_solver.py"):
            qwen_cell(name)
        for arm in ARMS:
            current_arm[0] = arm
            summary["actual_arm_order"].append(arm)
            atomic(output / "worker-summary.json", summary)
            try:
                summary["arms"][arm] = run_arm(arm, base if arm == "A" else sft,
                                                visible, plan, output, event)
                for task_id in TASKS:
                    row = read(output / (arm + "-" + task_id + ".json"))
                    if "generation_calls" in row:
                        limits = plan["limits"]
                        if (row["generation_calls"] > limits["calls_per_task"] or
                                row["returned_sequences"] > limits["calls_per_task"] *
                                limits["returned_sequences_per_call"] or
                                row["generation_forwards"] > limits["expansions_per_task"] or
                                row["verification_calls"] > limits["verifications_per_task"] or
                                row["verification_forwards"] !=
                                row["verification_calls"] * limits["verification_views_per_candidate"] or
                                (arm != "C" and row.get("ttt") is not None)):
                            raise ValidationError("ABC per-task fair budget differs")
            except Exception as exc:
                summary["arms"][arm] = {"status": "failed", "error_type": type(exc).__name__,
                                         "error_message": str(exc)[:1000]}
            atomic(output / "worker-summary.json", summary)
    return summary


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    for name in ("plan", "visible", "base", "sft", "bundle", "hardware", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--digest", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    run_worker(args.plan, args.visible, args.base, args.sft, args.bundle,
               args.hardware, args.output, args.digest)


if __name__ == "__main__":
    main()

"""Offline diagnostics for the retained prompt pilot; never runs a model."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from irisx.arc_prompt_pilot import score_result_package, score_search_result_package


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def shape(grid):
    return [len(grid), len(grid[0])] if grid else None


def classify(scored, record):
    if scored["correct"]:
        return "correct"
    capped = record["generation"]["stop_reason"] == "maximum_new_tokens"
    if scored["status"] != "valid":
        kind = "invalid"
    elif shape(scored["predicted_output"]) != shape(scored["expected_output"]):
        kind = "wrong_shape"
    else:
        kind = "wrong_cells"
    return kind + ("_at_cap" if capped else "_not_at_cap")


def analyze(root):
    search = root / "search"
    ledger = read(search / "ledger.json")
    trial = root / "repair-002/trial"
    visible = {c["task_id"]: c for c in read(trial / "solver-cases.json")["cases"]}
    baseline = read(search / "baseline-score.json")
    baseline_cases = {c["task_id"]: c for c in baseline["records"]}
    inputs = [("B1", ledger["baseline"]["instruction"], search / "baseline-score.json",
               root / "repair-002/recovered-v1/result.zip",
               root / "repair-002/outbound/prompt-pilot-baseline-002.zip")]
    for item in ledger["rounds"]:
        if not item.get("score_path"):
            continue
        directory = search / f"round-{item['round']:02d}"
        score_path = directory / "score.json"
        saved = read(score_path)
        files = {digest(p): p for p in directory.rglob("*.zip")}
        inputs.append((item["candidate"], item["candidate_instruction"], score_path,
                       files[saved["bindings"]["result_digest"]],
                       files[saved["bindings"]["outbound_digest"]]))

    report = {"format": "irisx/prompt-pilot-offline-diagnostics", "version": 1,
              "holdout_scored": False, "holdout_records_analyzed": 0,
              "new_model_calls": 0, "candidates": [],
              "ledger_digest": digest(search / "ledger.json"),
              "limitations": ["serialized grid characters are not tokenizer-certified token counts",
                              "observational comparisons do not establish a causal prompt-length effect",
                              "oracle unions use known answers and are not deployable solver scores"]}
    dev_union = set()
    for label, instruction, score_path, result_path, outbound_path in inputs:
        scorer = score_result_package if label == "B1" else score_search_result_package
        score = scorer(trial, result_path, outbound_path)
        if score != read(score_path):
            raise ValueError(f"Recomputed score differs: {label}")
        with zipfile.ZipFile(result_path) as archive:
            records = {c["task_id"]: c for c in json.loads(archive.read("predictions/predictions.json"))["records"]}
            observation = json.loads(archive.read("observations/execution.json"))
        candidate = {"candidate": label, "instruction_characters": len(instruction),
                     "score_digest": digest(score_path), "result_digest": digest(result_path),
                     "runner_seconds": observation["session_wall_seconds"], "groups": {}}
        for group in ("optimization-train", "selection-dev"):
            cases = [c for c in score["records"] if c["group"] == group]
            categories = Counter()
            eos_token_char_deltas = Counter()
            regressions = Counter()
            size_buckets = {}
            copied_wrong = 0
            cap_correct = 0
            above_char_proxy = 0
            cap_ids = []
            wrong_shape_not_cap_ids = []
            wins, losses = [], []
            for case in cases:
                task_id = case["task_id"]
                record = records[task_id]
                kind = classify(case, record)
                categories[kind] += 1
                target = case["expected_output"]
                serialized_chars = sum(len(row) for row in target) + len(target) - 1
                above_char_proxy += serialized_chars + 1 > 512
                capped = record["generation"]["stop_reason"] == "maximum_new_tokens"
                if capped:
                    cap_ids.append(task_id)
                    cap_correct += case["correct"]
                if kind == "wrong_shape_not_at_cap":
                    wrong_shape_not_cap_ids.append(task_id)
                if not case["correct"] and case["predicted_output"] == visible[task_id]["test"][0]["input"]:
                    copied_wrong += 1
                if record["generation"]["stop_reason"] == "eos_token" and case["status"] == "valid":
                    raw = record["generation"]["raw_completion"]
                    eos_token_char_deltas[record["tokens"]["generated"] - len(raw)] += 1
                cells = sum(len(row) for row in target)
                bucket = "<=64" if cells <= 64 else "65-256" if cells <= 256 else "257-480" if cells <= 480 else ">480"
                stats = size_buckets.setdefault(bucket, {"count": 0, "correct": 0, "cap": 0})
                stats["count"] += 1
                stats["correct"] += int(case["correct"])
                stats["cap"] += int(capped)
                if case["correct"] and not baseline_cases[task_id]["correct"]:
                    wins.append(task_id)
                if not case["correct"] and baseline_cases[task_id]["correct"]:
                    losses.append(task_id)
                    regressions[kind] += 1
                if group == "selection-dev" and case["correct"]:
                    dev_union.add(task_id)
            candidate["groups"][group] = {
                "denominator": len(cases), "correct": sum(c["correct"] for c in cases),
                "failure_categories": dict(categories), "capped": len(cap_ids), "capped_correct": cap_correct,
                "wrong_input_copies": copied_wrong, "expected_grid_characters_plus_eos_over_512": above_char_proxy,
                "eos_valid_generated_tokens_minus_raw_chars": dict(eos_token_char_deltas),
                "size_buckets": size_buckets, "wins_vs_B1": wins, "losses_vs_B1": losses,
                "regression_categories": dict(regressions), "cap_task_ids": cap_ids,
                "wrong_shape_not_at_cap_task_ids": wrong_shape_not_cap_ids,
                "median_generated_tokens": statistics.median(records[c["task_id"]]["tokens"]["generated"] for c in cases),
            }
        report["candidates"].append(candidate)
    report["dev_oracle_union_count"] = len(dev_union)
    report["parents"] = Counter(r["parent_candidate"] for r in ledger["rounds"])
    report["completed_reflection_seconds"] = sum(r["proposal_wall_seconds"] for r in ledger["rounds"] if r["proposal_status"] == "valid")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new analysis output")
    report = analyze(args.pilot_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in report["candidates"]:
        print(json.dumps({"candidate": item["candidate"], "instruction_chars": item["instruction_characters"],
                          "groups": {g: {k: v for k, v in s.items() if not k.endswith("task_ids") and k not in ("wins_vs_B1", "losses_vs_B1")}
                                     for g, s in item["groups"].items()}}))
    print("dev_oracle_union", report["dev_oracle_union_count"])


if __name__ == "__main__":
    main()

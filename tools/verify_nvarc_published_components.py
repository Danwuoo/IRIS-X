"""Independent offline readers for published SDG/TRM integration observations."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def require(condition, reason):
    if not condition:
        raise ValidationError(reason)


def read(folder, name):
    return json.loads((folder / name).read_bytes())


def verify_sdg(folder):
    plan, result = read(folder, "plan.json"), read(folder, "result.json")
    require(result["plan_digest"] == digest_value(plan), "published SDG plan binding differs")
    require(plan["source_filter"] == {"minimum_majority": 8, "minimum_pairs": 12,
                                      "minimum_correct_solutions": 4}, "published SDG filter changed")
    key = plan["join_key"]
    relative = Path(key["mix_name"]) / key["puzzle_name1"] / (key["puzzle_name1"] + "_" + key["puzzle_name2"] + ".json")
    inputs = read(folder, str(Path("input-grids") / relative))
    matrix = read(folder, str(Path("output-grids") / relative))
    require(len(inputs) == 30 and len(matrix["codes"]) == 20 and len(matrix["grids"]) == 600,
            "published SDG 30-by-20 matrix differs")
    require({(row["gid"], row["sid"]) for row in matrix["grids"]} ==
            {(gid, sid) for gid in range(30) for sid in range(20)}, "published SDG closed program/grid coverage differs")
    accepted, common, majorities = [], None, []
    for gid in range(30):
        rows = [row for row in matrix["grids"] if row["gid"] == gid]
        counts = Counter(digest_value(row["grid"]) for row in rows)
        winner, majority = counts.most_common(1)[0]
        winning = [row for row in rows if digest_value(row["grid"]) == winner]
        majorities.append(majority)
        if winning[0]["grid"] is None or majority < 8:
            continue
        accepted.append({"input": inputs[gid][1], "output": winning[0]["grid"]})
        sids = {row["sid"] for row in winning}
        common = sids if common is None else common & sids
        if not common:
            break
    diversity = all(len({digest_value(pair[side]) for pair in accepted}) > 1 and
                    len({color for pair in accepted for row in pair[side] for color in row}) > 1
                    for side in ("input", "output"))
    qualifies = len(accepted) >= 12 and len(common or ()) >= 4 and diversity
    expected_pairs = accepted if qualifies else []
    pair_path = folder / "accepted-pairs" / relative
    observed_pairs = read(folder, str(pair_path.relative_to(folder))) if pair_path.exists() else []
    require(expected_pairs == observed_pairs and result["accepted_pairs"] == len(expected_pairs),
            "independent published SDG majority/intersection/pair selection differs")
    events = [json.loads(line) for line in (folder / "invocations.jsonl").read_bytes().splitlines()]
    outcomes = [json.loads(line) for line in (folder / "program-results.jsonl").read_bytes().splitlines()]
    require([event["invocation"] for event in events] == list(range(1, len(events) + 1)) and
            len(events) == result["isolated_program_invocations"] <= 660,
            "published SDG program reservation ledger differs")
    require(len(events) == len(outcomes) and all(
        event["invocation"] == outcome["invocation"] and outcome["result_digest"] == digest_value(outcome["result"])
        for event, outcome in zip(events, outcomes)), "published SDG program outcome ledger differs")
    rejections = (folder / "rejections.jsonl").read_bytes().splitlines() if (folder / "rejections.jsonl").exists() else []
    require(sum(outcome["result"] is None for outcome in outcomes) == len(rejections) ==
            sum(result["program_rejections"].values()), "published SDG program rejection count differs")
    require(result["valid_nonidentity_outputs"] == sum(row["grid"] is not None for row in matrix["grids"]),
            "published SDG nonidentity output count differs")
    if "recovery" in plan:
        require(result["new_program_invocations"] == 0 and result["reused_program_invocations"] == len(events),
                "published SDG recovery claims new program calls")
        parent = folder.parent / plan["recovery"]["parent_run"]
        require({path.relative_to(parent).as_posix(): sha_file(path) for path in sorted(parent.rglob("*"))
                 if path.is_file()} == plan["recovery"]["parent_artifact_sha256"],
                "published SDG frozen parent artifacts differ")
    require(sum(event["entry"] == "generate_puzzle_output" for event in events) == 600,
            "published SDG output execution count differs")
    require(result["teacher_calls"] == 0 and not result["correctness_scored"] and
            not result["contains_evaluator_truth"] and not result["complete_dataset_verified"],
            "published SDG replay has an unearned claim")
    material = ROOT / ".irisx/nvarc-original/materials/sdg-first-shards-20261002-001"
    require(sha_file(material / "acquisition.json") == plan["acquisition_sha256"],
            "published SDG material ledger differs")
    for member in read(material, "acquisition.json")["members"]:
        require(sha_file(material / member["path"]) == member["sha256"], "published SDG source shard differs")
    return {"input_grids": 30, "output_programs": 20, "output_attempts": 600,
            "program_invocations": len(events), "majorities": majorities,
            "consistent_solution_count": len(common or ()), "independently_accepted_pairs": len(expected_pairs),
            "parent_ids": result["parent_ids"], "exposure_tags": result["exposure_tags"],
            "source_filter_8_12_4_verified": True, "complete_dataset_verified": False}


def verify_trm(folder):
    from irisx.arc_nvarc_trm import _decode_trm_tensor
    from irisx.arc_nvarc_trm_checkpoint import published_model_config
    plan, result, loaded = (read(folder, name) for name in ("plan.json", "result.json", "load-observation.json"))
    require(result["plan_digest"] == digest_value(plan) and result["model_config"] == plan["model_config"] ==
            published_model_config(), "published TRM full-width config/plan differs")
    material = ROOT / ".irisx/nvarc-original/materials/trm-published-031-20261002"
    require(sha_file(material / "step_220708") == plan["checkpoint_sha256"] == loaded["checkpoint_sha256"],
            "published TRM checkpoint bytes differ")
    require(loaded == result["checkpoint_load"] and loaded["checkpoint_bytes"] == 2159719349 and
            loaded["state_tensor_count"] == 15 and loaded["source_puzzle_embedding_shape"] == [1041208, 512] and
            loaded["target_puzzle_embedding_shape"] == [1, 512] and loaded["source_mean_reset_applied"] and
            loaded["dropped_state_keys"] == 0 and loaded["loaded_tensors_exact_after_explicit_dtype_cast"],
            "published TRM strict load/mean reset differs")
    require(result["ttt_optimizer_steps"] == 1 and result["changed_state_tensors"] > 0 and
            result["nonzero_gradient_parameters"] > 0 and 1 <= result["inference_forwards"] <= 10 and
            result["act_halted"] and result["reset_to_published_state_exact"], "published TRM observed workload differs")
    require(_decode_trm_tensor(result["raw_prediction"]) == result["candidate"],
            "published TRM candidate decoding differs")
    require(not result["original_scale_training_verified"] and not result["original_notebook_v18_verified"] and
            not result["original_bf16_numerical_parity"] and not result["correctness_scored"] and
            not result["contains_evaluator_truth"] and result["teacher_calls"] == 0,
            "published TRM observation has an unearned claim")
    return {"hidden_size": 512, "checkpoint_sha256": loaded["checkpoint_sha256"], "state_tensors": 15,
            "ttt_optimizer_steps": 1, "inference_forwards": result["inference_forwards"],
            "candidate_shape": [len(result["candidate"]), len(result["candidate"][0])],
            "reset_exact": True, "original_v18_and_bf16_parity_verified": False}


def verify(kind, run):
    pattern = r"nvarc-overnight-sdg-replay-\d{3}" if kind == "sdg" else r"nvarc-overnight-trm-cpu-\d{3}"
    require(re.fullmatch(pattern, run), "exact new component identity required")
    folder = ROOT / ".irisx/nvarc-original/runs" / run
    output = folder / "independent-terminal-verification.json"
    require(not output.exists() and not (folder / "failure.json").exists(), "new complete component record required")
    runtime = verify_sdg(folder) if kind == "sdg" else verify_trm(folder)
    report = {"format": "irisx/nvarc-published-component-independent-v1", "run_id": run, "runtime": runtime,
              "closed_artifact_sha256": {path.relative_to(folder).as_posix(): sha_file(path)
                                        for path in sorted(folder.rglob("*")) if path.is_file()},
              "external_calls": 0, "model_calls": 0, "program_executions": 0, "correctness_scored": False}
    output.write_bytes(canonical_bytes(report, newline=True))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", required=True, choices=("sdg", "trm"))
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.kind, args.run), indent=2))

"""Separately isolated workers behind the exact combined parent guard."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import time

from .arc_nvarc_combined import (atomic, check_logical_device, read, require,
                                require_live_authorization, sha)
from .arc_nvarc_source_continuation import EXPORT, TRAINING
from .arc_nvarc_teacher_profile import LIMITS, PROFILE, PROMPTS, TOTAL_TOKENS
from .canonical import digest_value


def inventory() -> list[dict]:
    import torch

    completed = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,uuid",
                                "--format=csv,noheader,nounits"], capture_output=True,
                               text=True, check=True, timeout=30)
    rows = [[item.strip() for item in line.split(",")] for line in completed.stdout.splitlines()]
    by_uuid = {row[3]: row for row in rows if len(row) == 4}
    require(len(by_uuid) == len(rows), "hardware UUID inventory malformed")
    devices = []
    for index in range(torch.cuda.device_count()):
        properties = torch.cuda.get_device_properties(index)
        uuid = str(properties.uuid)
        require(uuid in by_uuid, "Torch and nvidia-smi UUID records differ")
        row = by_uuid[uuid]
        with torch.cuda.device(index):
            bf16 = torch.cuda.is_bf16_supported()
        devices.append({"index": index, "uuid": uuid, "name": properties.name,
                        "memory_bytes": properties.total_memory,
                        "memory_mib": int(row[2]), "bf16": bf16})
    return devices


def _verify_m2(plan: dict, output: Path) -> dict:
    child = plan["branches"]["m2"]
    for name, key in (("visible.json", "visible_sha256"), ("source-config.json", "source_config_sha256"),
                      ("training-evidence.json", "training_evidence_sha256")):
        require(sha(output / name) == child[key], "combined M2 input binding differs")
    source_path = output / "work/source-result.json"
    chain = read(output / "work/continuation-chain.json")
    source = read(source_path)
    require(source.get("format") == "irisx/nvarc-source-stage-result-v1" and
            source.get("profile") == "4b" and source.get("material_digest") == EXPORT and
            source.get("training_identity_digest") == TRAINING and
            source.get("source_bundle_digest") == child["source_bundle_digest"] and
            source.get("config_sha256") == child["source_config_sha256"] and
            source.get("visible_sha256") == child["visible_sha256"] and
            source.get("contains_evaluator_truth") is False and source.get("task_count") == 1,
            "combined M2 result ancestry differs")
    visible = read(output / "visible.json")
    expected = len(visible["00576224"]["test"])
    rows = source.get("results", [])
    require(source.get("test_count") == expected and len(rows) == expected and
            [(r["task_id"], r["test_index"]) for r in rows] == [("00576224", i) for i in range(expected)],
            "combined M2 test coverage differs")
    calls = max(r["generation_calls_so_far"] for r in rows)
    verification = max(r["verification_calls_so_far"] for r in rows)
    require(type(calls) is int and 0 <= calls <= 4 and type(verification) is int and verification >= 0,
            "combined M2 counters differ")
    measurements = source.get("measurements", [])
    require(len(measurements) == 1, "combined M2 measurements missing")
    ttt = measurements[0].get("ttt", {})
    require(ttt.get("task_id") == "00576224" and ttt.get("status") == "complete" and
            ttt.get("steps") == 1 and ttt.get("training_tokens", 0) > 0 and
            isinstance(ttt.get("last_loss"), (int, float)) and math.isfinite(ttt["last_loss"]),
            "combined M2 finite completed TTT absent")
    require(chain == {"format": "irisx/nvarc-m2-source-continuation-result-v1",
        "run_id": child["run_id"], "plan_digest": digest_value(child),
        "export_material_digest": EXPORT, "training_identity_digest": TRAINING,
        "source_bundle_digest": child["source_bundle_digest"],
        "training_evidence_sha256": child["training_evidence_sha256"],
        "source_result_sha256": sha(source_path), "sft_steps": 0,
        "optimizer_checkpoint_retained": False, "generation_calls": calls,
        "verification_calls": verification, "nonempty_ranking_observed": verification > 0,
        "contains_evaluator_truth": False}, "combined M2 chain differs")
    return {"generation_calls": calls, "verification_calls": verification, "ttt_steps": 1,
            "ranked_candidates": sum(len(r["ranked"]) for r in rows), "sft_steps": 0}


def _verify_m3(plan: dict, output: Path) -> dict:
    from .arc_nvarc_sdg import BoundedLocalHFTeacher, validate_teacher_response

    child = plan["branches"]["m3"]
    result = read(output / "work/result.json")
    seed = read(output / "seed.json")
    require(sha(output / "seed.json") == child["seed_record_sha256"] and
            digest_value(read(output / "prompts.json")) == child["prompts_digest"] and
            read(output / "prompts.json") == PROMPTS, "combined teacher inputs differ")
    provider = BoundedLocalHFTeacher(None, None,
        model_material_digest=child["teacher_model_manifest_digest"],
        maximum_input_tokens=8192, maximum_output_tokens=3072, maximum_total_tokens=TOTAL_TOKENS,
        stage_limits=LIMITS, enable_thinking=False, require_complete=True)
    item = seed["record"]
    responses = []
    for index, stage in enumerate(PROMPTS):
        ledger = read(output / "work/stage-ledgers" / (stage + ".json"))
        require(ledger.get("format") == "irisx/nvarc-sdg-stage" and ledger.get("stage") == stage and
            ledger.get("binding") == digest_value({"stage": stage, "inputs": [item],
                "prompt": PROMPTS[stage], "provider": provider.identity, "seed": 24}) and
            ledger.get("maximum_calls") == 4 - index and ledger.get("reserved_calls") == 1 and
            set(ledger["records"]) == {item["record_id"]}, "combined teacher dependent ledger differs")
        record = ledger["records"][item["record_id"]]
        response = record["response"]
        require(record.get("status") == "complete" and record.get("provider_calls") == 1 and
                record.get("input_digest") == digest_value(item) and
                record.get("response_digest") == digest_value(response), "combined teacher response differs")
        checked = copy.deepcopy(response)
        validate_teacher_response(stage, checked)
        require(checked == response and 0 < response["input_tokens"] <= LIMITS[stage]["input"] and
                0 < response["output_tokens"] <= LIMITS[stage]["output"] and
                len(response.get("output_token_ids", [])) == response["output_tokens"] and
                response.get("enable_thinking") is False and
                response.get("model_material_digest") == child["teacher_model_manifest_digest"],
                "combined teacher actual tokens or direct mode differ")
        responses.append({"stage": stage, "usage": {k: response[k] for k in ("input_tokens", "output_tokens")},
                          "accepted": True, "rejection_reason": None,
                          "response_digest": record["response_digest"]})
        item = {**item, "stage_responses": {**item.get("stage_responses", {}), stage: response}}
    require(result.get("format") == "irisx/nvarc-m3-teacher-small-result-v1" and
        result.get("teacher_profile") == PROFILE and result.get("run_id") == child["run_id"] and
        result.get("plan_digest") == digest_value(child) and result.get("completed_calls") == 4 and
        result.get("accepted_stages") == 4 and result.get("reserved_calls") == 4 and
        result.get("reserved_tokens") == TOTAL_TOKENS and result.get("responses") == responses and
        result.get("seed_record_sha256") == child["seed_record_sha256"] and
        result.get("teacher_model_manifest_digest") == child["teacher_model_manifest_digest"] and
        result.get("contains_evaluator_truth") is False, "combined teacher result counters or binding differ")
    return {"teacher_calls": 4, "accepted_stages": 4, "reserved_tokens": TOTAL_TOKENS,
            "input_tokens": sum(r["usage"]["input_tokens"] for r in responses),
            "output_tokens": sum(r["usage"]["output_tokens"] for r in responses),
            "pair_acceptance": "pending separate authorized sandbox replay"}


def verify_branch(plan, branch, output):
    counts = (_verify_m2 if branch == "m2" else _verify_m3)(plan, output)
    if branch == "m2":
        partial = partial_m2_counts(plan, output)
        require(partial["reserved_counters"]["generation_calls"] == counts["generation_calls"] and
                partial["actual_counters"]["completed_generation_calls"] == counts["generation_calls"] and
                partial["reserved_counters"]["verification_calls"] == counts["verification_calls"] and
                partial["actual_counters"]["completed_verification_calls"] == counts["verification_calls"],
                "M2 source result/call ledger counters differ")
    return counts


def partial_m2_counts(plan, output):
    path = output / "call-ledger.json"
    if not path.exists():
        return {"counter_evidence": "M2 call ledger absent; counts unknown"}
    ledger = read(path)
    require(ledger.get("format") == "irisx/nvarc-combined-m2-call-ledger-v1" and
            ledger.get("parent_run_id") == plan["run_id"] and ledger.get("branch") == "m2" and
            ledger.get("run_id") == plan["branches"]["m2"]["run_id"] and
            ledger.get("child_plan_digest") == digest_value(plan["branches"]["m2"]) and
            ledger.get("plan_digest") == digest_value(plan) and
            all(k == r.get("kind", "") + ":" + str(r.get("index")) and
                r.get("kind") in {"generation", "verification"} and type(r.get("index")) is int
                for k, r in ledger["records"].items()), "M2 call ledger binding differs")
    counts = {}
    for kind in ("generation", "verification"):
        records = [r for r in ledger["records"].values() if r["kind"] == kind]
        require(sorted(r["index"] for r in records) == list(range(1, len(records) + 1)) and
                all(r["task_id"] == "00576224" and r["status"] in {"reserved", "complete"} for r in records) and
                (kind != "generation" or len(records) <= 4), "M2 call ledger coverage or bound differs")
        counts[kind] = {"reserved": len(records), "complete": sum(r["status"] == "complete" for r in records)}
    return {"reserved_counters": {k + "_calls": v["reserved"] for k, v in counts.items()},
            "actual_counters": {**{"completed_" + k + "_calls": v["complete"] for k, v in counts.items()},
                                **{"total_" + k + "_calls": v["complete"] if v["reserved"] == v["complete"] else None
                                   for k, v in counts.items()}},
            "counter_evidence": "persisted M2 reservations/completed returns; interrupted call actual work and TTT remain unknown"}


def partial_teacher_counts(plan, output):
    """Reconcile persisted reservations; never infer actual calls from pending work."""
    from .arc_nvarc_sdg import BoundedLocalHFTeacher

    child = plan["branches"]["m3"]
    if not (output / "seed.json").exists():
        return {"counter_evidence": "no persisted teacher seed/ledgers; counts unknown"}
    require(sha(output / "seed.json") == child["seed_record_sha256"], "partial teacher seed differs")
    item = read(output / "seed.json")["record"]
    provider = BoundedLocalHFTeacher(None, None,
        model_material_digest=child["teacher_model_manifest_digest"],
        maximum_input_tokens=8192, maximum_output_tokens=3072, maximum_total_tokens=TOTAL_TOKENS,
        stage_limits=LIMITS, enable_thinking=False, require_complete=True)
    reserved, responses, input_tokens, output_tokens = 0, 0, 0, 0
    uncertain = False
    for index, stage in enumerate(PROMPTS):
        path = output / "work/stage-ledgers" / (stage + ".json")
        if not path.exists():
            break
        ledger = read(path)
        require(ledger.get("binding") == digest_value({"stage": stage, "inputs": [item],
                "prompt": PROMPTS[stage], "provider": provider.identity, "seed": 24}) and
                ledger.get("maximum_calls") == 4 - reserved and
                ledger.get("reserved_calls") in (0, 1) and
                set(ledger["records"]) <= {item["record_id"]}, "partial teacher ledger differs")
        reserved += ledger["reserved_calls"]
        if not ledger["records"]:
            break
        record = ledger["records"][item["record_id"]]
        require(record.get("input_digest") == digest_value(item) and record.get("provider_calls") == 1,
                "partial teacher reservation differs")
        response = record.get("response")
        if response is None:
            uncertain = True
            break
        require(record.get("response_digest") == digest_value(response) and
                type(response.get("input_tokens")) is int and type(response.get("output_tokens")) is int and
                0 < response["input_tokens"] <= LIMITS[stage]["input"] and
                0 < response["output_tokens"] <= LIMITS[stage]["output"], "partial teacher usage differs")
        responses += 1
        input_tokens += response["input_tokens"]
        output_tokens += response["output_tokens"]
        if record.get("status") != "complete":
            break
        item = {**item, "stage_responses": {**item.get("stage_responses", {}), stage: response}}
    return {"reserved_counters": {"teacher_calls": reserved, "tokens": None},
            "actual_counters": {"completed_responses": responses, "input_tokens": input_tokens,
                                "output_tokens": output_tokens, "actual_model_calls": None if uncertain else responses},
            "counter_evidence": "digest-bound partial ledgers; pending/failed calls and reserved token count remain unknown"}


def _run_prepared(plan: dict, branch: str, paths: dict, hardware: dict, output: Path):
    """Internal work after the exact approved parent envelope is verified."""
    import shutil
    from .arc_nvarc_source_continuation import _run_bound as run_m2
    from .arc_nvarc_sdg_teacher import _run_bound as run_m3

    started = time.monotonic()
    child = plan["branches"][branch]
    digest = digest_value(plan)
    device = hardware["assignments"][branch]
    common = {"branch": branch, "parent_run_id": plan["run_id"], "run_id": child["run_id"],
              "plan_digest": digest, "child_plan_digest": digest_value(child), "device": device,
              "contains_evaluator_truth": False}
    state = {**common, "phase": "prerequisites", "reserved_counters": None, "actual_counters": None}
    atomic(output / "worker-state.json", state)
    try:
        check_logical_device(branch, hardware, device["uuid"], inventory(), os.environ.get("CUDA_VISIBLE_DEVICES"))

        def ready():
            state["phase"] = "work"
            atomic(output / "model-ready.json", common)
            atomic(output / "worker-state.json", state)

        state["phase"] = "loading"
        atomic(output / "worker-state.json", state)
        if branch == "m2":
            ledger = {**common, "format": "irisx/nvarc-combined-m2-call-ledger-v1", "records": {}}
            atomic(output / "call-ledger.json", ledger)
            def observe(call):
                key = call["kind"] + ":" + str(call["index"])
                if call["status"] == "reserved":
                    require(key not in ledger["records"] and
                            (call["kind"] != "generation" or call["index"] <= 4), "M2 call reused or exceeded bounds")
                else:
                    require(ledger["records"][key] == {**call, "status": "reserved"}, "M2 call reservation differs")
                ledger["records"][key] = call
                atomic(output / "call-ledger.json", ledger)
            for key, name in (("visible", "visible.json"), ("source_config", "source-config.json"),
                              ("training_evidence", "training-evidence.json")):
                shutil.copyfile(paths[key], output / name)
            run_m2(child, Path(paths["source_config"]), Path(paths["visible"]), Path(paths["bundle"]),
                   Path(paths["m2_model"]), Path(paths["training_evidence"]), output / "work", model_ready=ready,
                   call_observer=observe)
        else:
            for key in ("seed", "prompts"):
                shutil.copyfile(paths[key], output / (key + ".json"))
            run_m3(child, Path(paths["seed"]), Path(paths["prompts"]), Path(paths["m3_model"]),
                   Path(paths["model_manifest"]), output / "work", model_ready=ready)
        counts = verify_branch(plan, branch, output)
        state.update(phase="verified", actual_counters=counts,
                     reserved_counters=({"teacher_calls": 4, "tokens": TOTAL_TOKENS} if branch == "m3"
                                        else partial_m2_counts(plan, output)["reserved_counters"]))
        terminal = {**state, "status": "complete", "wall_seconds": time.monotonic() - started}
    except Exception as exception:
        terminal = {**state, "status": "failed", "wall_seconds": time.monotonic() - started,
                    "error": {"type": type(exception).__name__, "message": str(exception)[:2000]}}
        raise
    finally:
        # Keep partial stage reservation evidence. Unknown generation/token counts
        # remain null when a worker is interrupted before a persisted result.
        if branch == "m3" and terminal["status"] != "complete":
            try:
                terminal.update(partial_teacher_counts(plan, output))
            except Exception as exception:
                terminal["counter_evidence"] = "partial counters unreconciled: " + str(exception)[:2000]
        if branch == "m2" and terminal["status"] != "complete":
            try:
                terminal.update(partial_m2_counts(plan, output))
            except Exception as exception:
                terminal["counter_evidence"] = "partial M2 counters unreconciled: " + str(exception)[:2000]
        terminal["artifacts"] = {p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*")
                                 if p.is_file() and p.name not in {"stdout.log", "stderr.log", "worker-state.json",
                                                                 "model-ready.json", "worker-terminal.json"}}
        atomic(output / "worker-terminal.json", terminal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--branch", choices=("m2", "m3"), required=True)
    parser.add_argument("--paths", type=Path, required=True)
    parser.add_argument("--hardware", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = read(args.plan)
    require_live_authorization(plan)
    _run_prepared(plan, args.branch, read(args.paths), read(args.hardware), args.output)


if __name__ == "__main__":
    main()

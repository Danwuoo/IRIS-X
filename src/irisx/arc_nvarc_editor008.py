"""Decision 0042 owner-Editor repaired M2 and M3, with no transport API."""

import argparse
import copy
import json
import math
import os
from pathlib import Path
import shutil
import time
import zipfile

from .arc_nvarc_combined import atomic, read, require, sha, member, check_logical_device
from .canonical import digest_value

RUN = "nvarc-m2-m3-combined-008"
PLAN_DIGEST = "sha256:f8644274acac94f860839b1c93c2ddf54e82dd1ccdbc906027bcc5d36b873b49"


def require_editor_authorization(plan):
    require(digest_value(plan) == PLAN_DIGEST and plan.get("run_id") == RUN and
            plan.get("approved") is True and plan.get("owner_decision") == "Decision 0042" and
            plan.get("execution_control") == {"agent_start": False, "owner_editor_start": True,
                                               "save_type": "QUICK_SAVE"},
            "exact owner-Editor Decision 0042 combined package required")


def observe_call(plan, output):
    """Persist reservations before calls; interrupted actual work stays unknown."""
    child = plan["branches"]["m2"]
    ledger = {"format": "irisx/nvarc-editor008-m2-ledger-v1", "run_id": child["run_id"],
              "parent_run_id": RUN, "plan_digest": PLAN_DIGEST, "records": {}}
    atomic(output / "call-ledger.json", ledger)
    def observe(event):
        event = copy.deepcopy(event)
        kind, status = event["kind"], event["status"]
        require(kind in {"ttt", "generation", "verification"} and status in {"reserved", "complete"},
                "unknown paired call event")
        arm = event.get("arm_id", "shared")
        key = arm + ":" + kind + ":" + str(event.get("index", 1))
        limit = {"ttt": 1, "generation": 4, "verification": 8}[kind]
        require((kind == "ttt" and arm == "shared") or arm in {a["id"] for a in child["arms"]},
                "paired call arm differs")
        require(type(event.get("index", 1)) is int and 1 <= event.get("index", 1) <= limit,
                "paired call exceeds bound")
        if status == "reserved":
            require(key not in ledger["records"], "paired call reused")
        else:
            prior = ledger["records"].get(key)
            require(prior and prior["status"] == "reserved" and all(
                event.get(k) == v for k,v in prior.items() if k not in {"status", "steps"}), "paired reservation differs")
            if kind == "ttt":
                require(event.get("observation", {}).get("steps") == prior["steps"], "TTT step count differs")
        ledger["records"][key] = event
        atomic(output / "call-ledger.json", ledger)
    return observe


def partial_counts(plan, branch, output):
    if branch == "m2":
        path = output / "call-ledger.json"
        if not path.exists():
            return {"counter_evidence": "ledger absent; actual work unknown"}
        value = read(path)
        require(value["plan_digest"] == digest_value(plan) and value["parent_run_id"] == RUN,
                "partial M2 ledger binding differs")
        rows = list(value["records"].values())
        return {"reserved_counters": {kind: sum(r["kind"] == kind for r in rows)
                                        for kind in ("ttt", "generation", "verification")},
                "actual_counters": {"completed_" + kind: sum(r["kind"] == kind and r["status"] == "complete" for r in rows)
                                     for kind in ("ttt", "generation", "verification")},
                "counter_evidence": "reservations and completed returns; pending actual work unknown"}
    path = output / "work/result.json"
    if path.exists():
        report = read(path)
        require(report["plan_digest"] == digest_value(plan["branches"][branch]), "partial M3 binding differs")
        return {"reserved_counters": {"teacher_calls": report["reserved_calls"], "tokens": report["reserved_tokens"]},
                "actual_counters": {"completed_responses": report["completed_calls"],
                                    "accepted_stages": report["accepted_stages"],
                                    "accepted_pairs": report["accepted_pairs"]},
                "stage_outcomes": report["stage_outcomes"]}
    # The existing reconciler binds every stage against this v3 provider identity.
    from .arc_nvarc_combined_worker import partial_teacher_counts
    return partial_teacher_counts(plan, output)


def run_m2(plan, paths, output, ready):
    require_editor_authorization(plan)
    from .arc_nvarc_source_continuation import EXPORT, TRAINING
    from .arc_nvarc_representation import verify_model_material, validate_profile_material
    from .arc_nvarc_training import TaskLocalAdapter, load_compact_model
    from .arc_nvarc_candidates import QwenCandidateBackend
    from .arc_nvarc_shape_floor_trial import run_grammar_completion
    from .arc_nvarc_data import visible_task
    from .arc_nvarc_upstream import source_bundle, qwen_cell
    child = plan["branches"]["m2"]
    for key in ("source_config", "visible", "training_evidence"):
        require(sha(Path(paths[key])) == child[key + "_sha256"], "M2 input differs: " + key)
        shutil.copyfile(paths[key], output / (key.replace("_", "-") + ".json"))
    lineage = read(Path(paths["training_evidence"]))
    require(lineage["export_material_digest"] == EXPORT and lineage["training_identity_digest"] == TRAINING and
            lineage["optimizer_checkpoint_retained"] is False, "M2 training lineage differs")
    cfg = read(Path(paths["source_config"]))
    visible = read(Path(paths["visible"]))
    require(list(visible) == ["00576224"], "M2 task differs")
    material = verify_model_material(Path(paths["m2_model"]), EXPORT)
    validate_profile_material("4b", cfg["profiles"]["4b"]["material_digest"], EXPORT, material)
    require(material["training_identity_digest"] == TRAINING, "M2 material ancestry differs")
    with source_bundle(Path(paths["bundle"]), child["source_bundle_digest"]):
        for name in ("arc_loader.py", "arc_decoder.py", "arc_solver.py"):
            qwen_cell(name)
        model = load_compact_model(Path(paths["m2_model"]), dtype="bfloat16")
        model.to("cuda:0")
        backend = QwenCandidateBackend(model, task_adapter=TaskLocalAdapter(model, cfg["adaptation"]),
                                       decoding="grammar-completion", dfs_max_expansions=128)
        observer = observe_call(plan, output)
        ready()
        result = run_grammar_completion(visible_task("00576224", visible["00576224"]), backend,
                                 cfg["candidate"], call_observer=observer)
    require(0 < result["shared_adaptation"]["training_tokens"] <= 512, "M2 training token bound differs")
    result.update(run_id=child["run_id"], plan_digest=digest_value(child), parent_plan_digest=PLAN_DIGEST,
        export_material_digest=EXPORT, training_identity_digest=TRAINING,
        source_bundle_digest=child["source_bundle_digest"], contains_evaluator_truth=False)
    atomic(output / "work/result.json", result)


def run_m3(plan, paths, output, ready):
    require_editor_authorization(plan)
    from .arc_nvarc_4b_pilot import verify_model_material
    from .arc_nvarc_sdg import BoundedLocalHFTeacher, run_teacher_pipeline
    from .arc_nvarc_sdg_teacher import stage_outcomes
    from .arc_nvarc_semantics_v6 import PROFILE, PROMPTS, accept_semantic_record
    from .arc_nvarc_semantics import SemanticProgramExecutor, prepare_numpy
    from .arc_nvarc_upstream import sdg_source_bundle
    from .errors import ValidationError
    child = plan["branches"]["m3"]
    for key in ("seed", "prompts"):
        shutil.copyfile(paths[key], output / (key + ".json"))
    require(sha(output / "seed.json") == child["seed_record_sha256"] and
            read(output / "prompts.json") == PROMPTS and digest_value(PROMPTS) == child["prompts_digest"],
            "M3 seed/prompts differ")
    seed, manifest = read(output / "seed.json"), read(Path(paths["model_manifest"]))
    require(seed["parent_ids"] == child["seed_train_parent_ids"] and manifest["manifest_digest"] ==
            child["teacher_model_manifest_digest"], "M3 public parents/material differ")
    verify_model_material(Path(paths["m3_model"]), manifest)
    import torch
    from transformers import AutoModelForMultimodalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(paths["m3_model"], local_files_only=True)
    model = AutoModelForMultimodalLM.from_pretrained(paths["m3_model"], local_files_only=True,
        dtype=torch.bfloat16, attn_implementation="sdpa", device_map="cuda:0").eval()
    ready()
    provider = BoundedLocalHFTeacher(model, tokenizer, model_material_digest=manifest["manifest_digest"],
        maximum_input_tokens=8192, maximum_output_tokens=3072, maximum_total_tokens=28160,
        stage_limits=child["stage_limits"], enable_thinking=False, require_complete=True, validation_profile=PROFILE)
    ledgers = run_teacher_pipeline([seed["record"]], PROMPTS, provider, output / "work/stage-ledgers",
                                   seed=24, maximum_calls=4)
    outcomes = stage_outcomes(ledgers)
    responses = {stage: record["response"] for stage, ledger in ledgers["stages"].items()
                 for record in ledger["records"].values() if "response" in record}
    report = {"format": "irisx/nvarc-editor008-m3-result-v1", "run_id": child["run_id"],
        "plan_digest": digest_value(child), "parent_plan_digest": PLAN_DIGEST, "teacher_profile": PROFILE,
        "reserved_calls": ledgers["reserved_calls"], "reserved_tokens": provider.reserved_tokens,
        "completed_calls": len(responses), "accepted_stages": sum(o["status"] == "complete" for o in outcomes),
        "stage_outcomes": outcomes, "response_digests": {k:digest_value(v) for k,v in responses.items()},
        "accepted_pairs": 0, "semantic_disposition": "teacher-stage-rejected", "contains_evaluator_truth": False}
    atomic(output / "work/result.json", report)
    if report["accepted_stages"] == 4:
        # No fallback to host exec if the provider image lacks namespace support.
        try:
            deps = Path(paths["sandbox_dependencies"])  # outside retained worker artifacts
            prepare_numpy(Path(paths["numpy_wheel"]), deps)
            executor = SemanticProgramExecutor(deps, launcher=Path(paths["sandbox_launcher"]),
                                                launcher_sha256=child["sandbox_launcher_sha256"])
            with sdg_source_bundle(Path(paths["sdg_bundle"]), child["sdg_source_digest"]):
                accepted = accept_semantic_record(seed["record"], responses, executor)
            atomic(output / "work/accepted-pairs.json", accepted)
            report.update(accepted_pairs=len(accepted["pairs"]), semantic_disposition=accepted["status"],
                          pair_result_sha256=sha(output / "work/accepted-pairs.json"))
        except Exception as error:
            report.update(semantic_disposition="program-contract-rejected",
                          semantic_error={"type":type(error).__name__, "message":str(error)[:2000]})
        atomic(output / "work/result.json", report)
    # A completed negative observation is a valid trial result, not promotion.


def verify_branch(plan, branch, output):
    require_editor_authorization(plan)
    child, result = plan["branches"][branch], read(output / "work/result.json")
    require(result["run_id"] == child["run_id"] and result["plan_digest"] == digest_value(child) and
            result["parent_plan_digest"] == PLAN_DIGEST and result["contains_evaluator_truth"] is False,
            "worker result binding differs")
    if branch == "m2":
        visible = read(output / "visible.json")["00576224"]
        test_colors = {value for row in visible["test"][0]["input"] for value in row}
        require(result["generation_calls"] == 4 and result["shared_adaptation"]["steps"] == 1 and
                0 < result["shared_adaptation"]["training_tokens"] <= 512 and
                math.isfinite(result["shared_adaptation"]["last_loss"]) and
                result["public_output_shape"] == [6,6] and
                result["completion_profile"] == "model-ranked-legal-colors/forced-public-grammar" and
                result["public_palette_constraint"] is True and
                result["verification_calls"] <= 8 and
                result["explicit_forwards"] <= 4*128+8*8 and
                result["model_mutation_guard_passed"] is True and
                all(len(candidate["grid"]) == 6 and all(len(row) == 6 for row in candidate["grid"])
                    for row in result["results"] for candidate in row["ranked"]) and
                all({value for grid_row in candidate["grid"] for value in grid_row} == test_colors
                    for row in result["results"] for candidate in row["ranked"]),
                "M2 coverage or public palette differs")
        partial = partial_counts(plan, branch, output)
        require(partial["reserved_counters"] == {"ttt":1, "generation":4,
                "verification":result["verification_calls"]} and
                partial["actual_counters"] == {"completed_"+k:v for k,v in partial["reserved_counters"].items()},
                "M2 result/ledger reconciliation differs")
        return {"ttt_steps":1, "generation_calls":4,
                "verification_calls":result["verification_calls"],
                "ranked_candidates":result["ranked_candidates"]}
    from .arc_nvarc_combined_worker import partial_teacher_counts
    partial = partial_teacher_counts(plan, output)
    from .arc_nvarc_semantics_v6 import PROFILE, PROMPTS
    from .arc_nvarc_sdg import validate_teacher_response
    item = read(output / "seed.json")["record"]
    accepted_stages = 0
    response_digests = {}
    for stage in PROMPTS:
        path = output / "work/stage-ledgers" / (stage + ".json")
        if not path.exists():
            break
        record = read(path)["records"].get(item["record_id"], {})
        response = record.get("response")
        if response is None:
            break
        response_digests[stage] = digest_value(response)
        checked = copy.deepcopy(response)
        try:
            validate_teacher_response(stage, checked, profile=PROFILE, item=item)
        except Exception:
            require(record["status"] == "rejected", "M3 invalid response marked accepted")
            break
        require(record["status"] == "complete" and checked == response, "M3 stage disposition differs")
        accepted_stages += 1
        item = {**item,"stage_responses":{**item.get("stage_responses",{}),stage:response}}
    require(0 <= result["reserved_calls"] <= 4 and result["reserved_tokens"] <= 28160 and
            result["completed_calls"] == partial["actual_counters"]["completed_responses"] and
            result["reserved_calls"] == partial["reserved_counters"]["teacher_calls"] and
            result["accepted_stages"] == accepted_stages and result["response_digests"] == response_digests and
            result["accepted_pairs"] in (0,5), "M3 result/ledger reconciliation differs")
    if result["accepted_pairs"]:
        pairs = read(output / "work/accepted-pairs.json")
        require(sha(output / "work/accepted-pairs.json") == result["pair_result_sha256"] and
                len(pairs["pairs"]) == 5 and pairs["program_invocations"] == 44 and pairs["source_filter_passed"],
                "M3 pair evidence differs")
    return {"teacher_calls":result["completed_calls"], "accepted_stages":result["accepted_stages"],
            "accepted_pairs":result["accepted_pairs"], "semantic_disposition":result["semantic_disposition"],
            "input_tokens":partial["actual_counters"]["input_tokens"],
            "output_tokens":partial["actual_counters"]["output_tokens"]}


def package_results(work, target, run_id=RUN, plan_digest=PLAN_DIGEST):
    from .arc_nvarc_analysis_zip008 import write_analysis_zip
    return write_analysis_zip(work, target, run_id, plan_digest)


def run_worker(plan, branch, paths, hardware, output):
    require_editor_authorization(plan)
    from .arc_nvarc_combined_worker import inventory
    require(output.is_dir() and {p.name for p in output.iterdir()} <= {"stdout.log", "stderr.log"},
            "new empty worker directory required")
    started = time.monotonic()
    child, device = plan["branches"][branch], hardware["assignments"][branch]
    state = {"branch":branch,"parent_run_id":RUN,"run_id":child["run_id"], "plan_digest":PLAN_DIGEST,
        "child_plan_digest":digest_value(child), "device":device, "contains_evaluator_truth":False,
        "phase":"prerequisites", "reserved_counters":None, "actual_counters":None}
    atomic(output / "worker-state.json",state)
    try:
        check_logical_device(branch,hardware,device["uuid"],inventory(output),os.environ.get("CUDA_VISIBLE_DEVICES"))
        state["phase"] = "loading"
        atomic(output / "worker-state.json",state)
        def ready():
            state["phase"] = "work"
            atomic(output / "model-ready.json",state)
            atomic(output / "worker-state.json",state)
        (run_m2 if branch=="m2" else run_m3)(plan,paths,output,ready)
        counts = verify_branch(plan,branch,output)
        state.update(phase="verified",actual_counters=counts)
        terminal = {**state,"status":"complete"}
    except Exception as error:
        terminal = {**state,"status":"failed","error":{"type":type(error).__name__,"message":str(error)[:2000]}}
        raise
    finally:
        if terminal["status"] != "complete":
            try:
                terminal.update(partial_counts(plan,branch,output))
            except Exception as error:
                terminal["counter_evidence"] = "partial reconciliation failed: " + str(error)[:1000]
        terminal["wall_seconds"] = time.monotonic()-started
        terminal["artifacts"] = {p.relative_to(output).as_posix():sha(p) for p in output.rglob("*") if p.is_file()
            and p.name not in {"stdout.log","stderr.log","worker-state.json","model-ready.json","worker-terminal.json"}}
        atomic(output / "worker-terminal.json",terminal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan","paths","hardware","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--branch",choices=("m2","m3"),required=True)
    args = parser.parse_args()
    run_worker(read(args.plan),args.branch,read(args.paths),read(args.hardware),args.output)


if __name__ == "__main__":
    main()

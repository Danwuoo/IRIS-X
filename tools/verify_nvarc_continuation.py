"""Independently verify retrieved Decision 0033 artifacts without model calls."""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from irisx.arc_nvarc_source_continuation import EXPORT, TRAINING, RUN, validate_plan
from irisx.arc_nvarc_source_bundle import verify_bundle
from irisx.arc_nvarc_sdg import BoundedLocalHFTeacher, validate_teacher_response
from irisx.arc_nvarc_teacher_profile import LIMITS, PROMPTS, TOTAL_TOKENS
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def common(package, output, terminal_name):
    plan = read(package / "plan.json")
    require((output / "plan.json").read_bytes() == (package / "plan.json").read_bytes(),
            "retrieved approved plan differs")
    require(plan.get("approved") is True and plan.get("owner_decision") == "Decision 0033",
            "continuation owner binding differs")
    wheels = list((package / "wheel").glob("*.whl"))
    require(len(wheels) == 1 and sha(output / wheels[0].name) == sha(wheels[0]),
            "retrieved runtime wheel differs")
    hardware = read(output / "hardware-uuid-preflight.json")
    rows = hardware.get("rows", [])
    require(hardware.get("bf16") is True and len(rows) == 4 and
            all(len(row) == 4 and row[0] == str(i) and "L4" in row[1] and
                int(row[2]) >= 22000 and row[3] for i, row in enumerate(rows)) and
            len({row[3] for row in rows}) == 4, "four distinct BF16 L4 evidence differs")
    terminal = read(output / terminal_name)
    require(terminal.get("return_code") == 0 and terminal.get("plan_sha256") == sha(package / "plan.json") and
            0 < terminal.get("wall_seconds", 0) <= plan["maximum_kernel_wall_seconds"],
            "successful bounded terminal evidence differs")
    return plan, {"plan_sha256": sha(package / "plan.json"),
                  "hardware_sha256": sha(output / "hardware-uuid-preflight.json"),
                  "terminal_sha256": sha(output / terminal_name),
                  "wall_seconds": terminal["wall_seconds"]}


def verify_m2(package, output):
    plan, bindings = common(package, output, "source-continuation-terminal.json")
    validate_plan(plan, approved=True)
    verify_bundle(output / "source-bundle", plan["source_bundle_digest"])
    for name in ("source-config.json", "visible.json", "training-evidence.json"):
        require((output / name).read_bytes() == (package / name).read_bytes(),
                "retrieved M2 input differs: " + name)
    source_path = output / RUN / "source-result.json"
    chain_path = output / RUN / "continuation-chain.json"
    source, chain = read(source_path), read(chain_path)
    require(source.get("format") == "irisx/nvarc-source-stage-result-v1" and
            source.get("profile") == "4b" and source.get("material_digest") == EXPORT and
            source.get("training_identity_digest") == TRAINING and
            source.get("source_bundle_digest") == plan["source_bundle_digest"] and
            source.get("config_sha256") == plan["source_config_sha256"] and
            source.get("visible_sha256") == plan["visible_sha256"] and
            source.get("contains_evaluator_truth") is False and source.get("task_count") == 1,
            "source result ancestry differs")
    visible = read(package / "visible.json")
    expected_tests = len(visible["00576224"]["test"])
    results = source.get("results", [])
    require(source.get("test_count") == expected_tests and len(results) == expected_tests and
            [(row["task_id"], row["test_index"]) for row in results] ==
            [("00576224", i) for i in range(expected_tests)], "source result test coverage differs")
    calls = max(row["generation_calls_so_far"] for row in results)
    verification = max(row["verification_calls_so_far"] for row in results)
    require(0 <= calls <= 4 and verification >= 0, "source call bounds differ")
    observations = source.get("measurements", [])
    require(len(observations) == 1, "source measurement coverage differs")
    ttt = observations[0].get("ttt", {})
    require(ttt.get("task_id") == "00576224" and ttt.get("status") == "complete" and
            ttt.get("steps") == 1 and ttt.get("training_tokens", 0) > 0 and
            math.isfinite(ttt["last_loss"]), "source TTT update is not verified")
    require(chain.get("format") == "irisx/nvarc-m2-source-continuation-result-v1" and
            chain.get("run_id") == RUN and chain.get("plan_digest") == digest_value(plan) and
            chain.get("export_material_digest") == EXPORT and chain.get("training_identity_digest") == TRAINING and
            chain.get("source_bundle_digest") == plan["source_bundle_digest"] and
            chain.get("training_evidence_sha256") == plan["training_evidence_sha256"] and
            chain.get("source_result_sha256") == sha(source_path) and chain.get("sft_steps") == 0 and
            chain.get("optimizer_checkpoint_retained") is False and
            chain.get("generation_calls") == calls and chain.get("verification_calls") == verification and
            chain.get("nonempty_ranking_observed") is (verification > 0) and
            chain.get("contains_evaluator_truth") is False, "distinct continuation chain differs")
    return {"format": "irisx/nvarc-m2-source-continuation-verification-v1", "run_id": RUN,
            **bindings, "source_result_sha256": sha(source_path), "chain_sha256": sha(chain_path),
            "export_material_digest": EXPORT, "training_identity_digest": TRAINING,
            "sft_steps": 0, "ttt_steps": 1, "ttt_tokens": ttt["training_tokens"],
            "ttt_loss": ttt["last_loss"], "generation_calls": calls, "verification_calls": verification,
            "returned_sequences": sum(row["returned_sequences"] for row in results),
            "ranked_candidates": sum(len(row["ranked"]) for row in results),
            "contains_evaluator_truth": False}


def verify_m3(package, output):
    plan, bindings = common(package, output, "m3-teacher-terminal.json")
    require(plan["run_id"] == "nvarc-m3-teacher-small-004" and plan["stage_limits"] == LIMITS and
            read(package / "prompts.json") == PROMPTS, "teacher profile differs")
    for name in ("seed.json", "prompts.json"):
        require((output / name).read_bytes() == (package / name).read_bytes(), "teacher input differs")
    seed = read(package / "seed.json")
    provider = BoundedLocalHFTeacher(None, None, model_material_digest=plan["teacher_model_manifest_digest"],
        maximum_input_tokens=plan["maximum_input_tokens_per_call"],
        maximum_output_tokens=plan["maximum_output_tokens_per_call"], maximum_total_tokens=TOTAL_TOKENS,
        stage_limits=LIMITS, enable_thinking=False, require_complete=True)
    run = output / "m3-teacher-small-004"
    result = read(run / "result.json")
    item = seed["record"]
    usage = []
    ledgers = {}
    for index, stage in enumerate(PROMPTS):
        path = run / "stage-ledgers" / (stage + ".json")
        ledger = read(path)
        expected_binding = digest_value({"stage": stage, "inputs": [item], "prompt": PROMPTS[stage],
                                         "provider": provider.identity, "seed": 24})
        require(ledger.get("format") == "irisx/nvarc-sdg-stage" and ledger.get("stage") == stage and
                ledger.get("binding") == expected_binding and ledger.get("maximum_calls") == 4 - index and
                ledger.get("reserved_calls") == 1 and set(ledger["records"]) == {item["record_id"]},
                "teacher dependent stage binding differs: " + stage)
        record = ledger["records"][item["record_id"]]
        response = record["response"]
        require(record.get("status") == "complete" and record.get("provider_calls") == 1 and
                record.get("input_digest") == digest_value(item) and
                record.get("response_digest") == digest_value(response), "teacher accepted response binding differs")
        checked = copy.deepcopy(response)
        validate_teacher_response(stage, checked)
        require(checked == response, "teacher validated content differs")
        require(0 < response["input_tokens"] <= LIMITS[stage]["input"] and
                0 < response["output_tokens"] <= LIMITS[stage]["output"] and
                response.get("enable_thinking") is False and
                response.get("model_material_digest") == plan["teacher_model_manifest_digest"] and
                len(response.get("output_token_ids", [])) == response["output_tokens"], "teacher actual usage differs")
        usage.append({"stage": stage, "input_tokens": response["input_tokens"],
                      "output_tokens": response["output_tokens"], "response_digest": record["response_digest"]})
        ledgers[stage] = sha(path)
        item = {**item, "stage_responses": {**item.get("stage_responses", {}), stage: response}}
    require(result.get("format") == "irisx/nvarc-m3-teacher-small-result-v1" and
            result.get("teacher_profile") == "qwen-direct-complete-v1" and
            result.get("run_id") == plan["run_id"] and result.get("plan_digest") == digest_value(plan) and
            result.get("completed_calls") == 4 and result.get("accepted_stages") == 4 and
            result.get("reserved_calls") == 4 and result.get("reserved_tokens") == TOTAL_TOKENS and
            result.get("seed_record_sha256") == plan["seed_record_sha256"] and
            result.get("teacher_model_manifest_digest") == plan["teacher_model_manifest_digest"] and
            result.get("contains_evaluator_truth") is False, "teacher result counters or identity differ")
    require(result.get("responses") == [{"stage": row["stage"],
            "usage": {"input_tokens": row["input_tokens"], "output_tokens": row["output_tokens"]},
            "accepted": True, "rejection_reason": None, "response_digest": row["response_digest"]}
            for row in usage], "teacher result/ledger usage differs")
    return {"format": "irisx/nvarc-m3-direct-teacher-verification-v1", "run_id": plan["run_id"],
            **bindings, "result_sha256": sha(run / "result.json"), "ledger_sha256": ledgers,
            "completed_calls": 4, "accepted_stages": 4, "reserved_tokens": TOTAL_TOKENS,
            "input_tokens": sum(row["input_tokens"] for row in usage),
            "output_tokens": sum(row["output_tokens"] for row in usage), "usage": usage,
            "contains_evaluator_truth": False, "pair_acceptance": "requires separate sandbox replay"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("m2", "m3"))
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--retrieved", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    require(not args.report.exists(), "new verification report required")
    report = (verify_m2 if args.kind == "m2" else verify_m3)(args.package, args.retrieved)
    args.report.write_bytes(canonical_bytes(report, newline=True))
    print(json.dumps(report, indent=2))

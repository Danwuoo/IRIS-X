"""One bounded offline full-vocabulary teacher pass over public train demos."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from .arc_nvarc_4b_pilot import verify_model_material
from .arc_nvarc_sdg import BoundedLocalHFTeacher, run_teacher_pipeline
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError
from .arc_nvarc_teacher_profile import LIMITS, TOTAL_TOKENS, PROFILE, PROMPTS, profile_prompts
from .arc_nvarc_teacher_spec import PROFILE as SPEC_PROFILE


def stage_outcomes(ledgers: dict) -> list[dict]:
    """Keep failed stages visible even when no model response was returned."""
    outcomes = []
    for stage, ledger in ledgers["stages"].items():
        for record_id, record in ledger["records"].items():
            response = record.get("response", {})
            outcomes.append({"stage": stage, "record_id": record_id,
                             "status": record["status"],
                             "reason": record.get("rejection_reason") or record.get("error_message") or
                                       record.get("error_type"),
                             "error_type": record.get("error_type"),
                             "finish_reason": response.get("finish_reason"),
                             "input_tokens": response.get("input_tokens"),
                             "output_tokens": response.get("output_tokens")})
    return outcomes


def completion_error(report: dict, expected_calls: int) -> str | None:
    if report["completed_calls"] == expected_calls and report["accepted_stages"] == expected_calls:
        return None
    counts = (f"responses={report['completed_calls']}/{expected_calls}, "
              f"accepted_stages={report['accepted_stages']}/{expected_calls}")
    failures = [item for item in report["stage_outcomes"] if item["status"] != "complete"]
    if failures:
        first = failures[0]
        detail = f"{first['stage']} {first['status']}: {first['reason'] or 'no completed response'}"
    else:
        detail = "stage coverage incomplete; inspect result.json and stage-ledgers"
    return f"local SDG teacher batch incomplete ({counts}); {detail}"


def run(plan_path: Path, seed_path: Path, prompts_path: Path, model_root: Path,
        model_manifest_path: Path, output: Path) -> dict:
    plan = json.loads(plan_path.read_bytes())
    # New candidate prompts must never piggyback on a consumed standalone
    # Decision 0033/0034 identity. Only the internal combined workload knows v2;
    # its parent/worker still require a separately bound execution envelope.
    if plan.get("teacher_profile") in {SPEC_PROFILE, "qwen-rule-contract-v3"}:
        raise ValidationError("structured teacher profile is inert; separate exact combined approval required")
    validated = plan.get("teacher_profile") == PROFILE
    if (plan.get("format") != "irisx/nvarc-m3-teacher-small-v1" or
            plan.get("approved") is not True or not plan.get("owner_decision") or
            plan.get("maximum_teacher_calls") != 4 or
            plan.get("maximum_model_generations") != 4 or
            plan.get("maximum_paid_usd") != 0 or plan.get("retry") is not False or
            output.exists()):
        raise ValidationError("exact owner-approved small teacher run required")
    direct_decisions = {"nvarc-m3-teacher-small-004": "Decision 0033",
                        "nvarc-m3-teacher-small-005": "Decision 0034"}
    if validated and (plan.get("run_id") not in direct_decisions or
                      plan.get("owner_decision") != direct_decisions[plan["run_id"]] or
                      plan.get("stage_limits") != LIMITS or plan.get("enable_thinking") is not False or
                      plan.get("maximum_total_reserved_tokens") != TOTAL_TOKENS or
                      json.loads(prompts_path.read_bytes()) != profile_prompts(plan["teacher_profile"])):
        raise ValidationError("validated teacher profile or stage limits differ")
    import torch
    if (not torch.cuda.is_available() or torch.cuda.device_count() != 4 or
            "L4" not in torch.cuda.get_device_name(0)):
        raise ValidationError("private Kaggle four-L4 gate failed before teacher load")
    return _run_bound(plan, seed_path, prompts_path, model_root, model_manifest_path, output)


def _run_bound(plan: dict, seed_path: Path, prompts_path: Path, model_root: Path,
               model_manifest_path: Path, output: Path, *, model_ready=None) -> dict:
    """Internal workload after the standalone or combined execution gate."""
    if plan.get("teacher_profile") == "qwen-rule-contract-v3":
        raise ValidationError("semantic teacher profile is inert; new exact execution envelope required")
    import torch
    from transformers import AutoModelForMultimodalLM, AutoTokenizer

    validated = plan.get("teacher_profile") in {PROFILE, SPEC_PROFILE}
    seed_bytes, prompts_bytes = seed_path.read_bytes(), prompts_path.read_bytes()
    if validated and (json.loads(prompts_bytes) != profile_prompts(plan["teacher_profile"]) or
                      plan.get("stage_limits") != LIMITS or plan.get("enable_thinking") is not False or
                      plan.get("maximum_total_reserved_tokens") != TOTAL_TOKENS):
        raise ValidationError("internal direct teacher profile or complete-response bounds differ")
    if (hashlib.sha256(seed_bytes).hexdigest() != plan["seed_record_sha256"] or
            digest_value(json.loads(prompts_bytes)) != plan["prompts_digest"]):
        raise ValidationError("teacher public seed or source prompt binding differs")
    seed = json.loads(seed_bytes)
    if (seed.get("format") != "irisx/nvarc-m3-teacher-seed-v1" or
            seed.get("parent_ids") != plan["seed_train_parent_ids"] or
            len(seed.get("record", {}).get("train_demos", [])) < 2):
        raise ValidationError("teacher seed exposure differs")
    manifest = json.loads(model_manifest_path.read_bytes())
    if manifest.get("manifest_digest") != plan["teacher_model_manifest_digest"]:
        raise ValidationError("teacher model manifest identity differs")
    verify_model_material(model_root, manifest)
    started = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(model_root, local_files_only=True)
    model = AutoModelForMultimodalLM.from_pretrained(
        model_root, local_files_only=True, dtype=torch.bfloat16,
        attn_implementation="sdpa", device_map="cuda:0").eval()
    if model_ready is not None:
        model_ready()
    provider = BoundedLocalHFTeacher(
        model, tokenizer, model_material_digest=manifest["manifest_digest"],
        maximum_input_tokens=plan["maximum_input_tokens_per_call"],
        maximum_output_tokens=plan["maximum_output_tokens_per_call"],
        maximum_total_tokens=plan["maximum_total_reserved_tokens"],
        stage_limits=LIMITS if validated else None,
        enable_thinking=False if validated else None, require_complete=validated,
        validation_profile=plan["teacher_profile"] if validated else PROFILE)
    ledgers = run_teacher_pipeline([seed["record"]], json.loads(prompts_bytes), provider,
                                   output / "stage-ledgers", seed=24,
                                   maximum_calls=plan["maximum_teacher_calls"])
    responses = []
    for stage, ledger in ledgers["stages"].items():
        for record in ledger["records"].values():
            if "response" in record:
                responses.append({"stage": stage, "usage": {key: record["response"][key]
                                  for key in ("input_tokens", "output_tokens")},
                                  "accepted": record["status"] == "complete",
                                  "rejection_reason": record.get("rejection_reason"),
                                  "response_digest": record["response_digest"]})
    report = {"format": "irisx/nvarc-m3-teacher-small-result-v1",
              "run_id": plan["run_id"], "plan_digest": digest_value(plan),
              "seed_record_sha256": plan["seed_record_sha256"],
              "teacher_model_manifest_digest": manifest["manifest_digest"],
              "reserved_calls": ledgers["reserved_calls"],
              "reserved_tokens": provider.reserved_tokens,
              "completed_calls": len(responses), "responses": responses,
              "accepted_stages": sum(item["accepted"] for item in responses),
              "stage_outcomes": stage_outcomes(ledgers),
              "teacher_profile": plan.get("teacher_profile", "legacy-source-prompts"),
              "wall_seconds": time.monotonic() - started,
              "contains_evaluator_truth": False,
              "claim": "local Qwen3.5-4B teacher smoke; no NVARC teacher parity or generated data acceptance"}
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_bytes(canonical_bytes(report, newline=True))
    failure = completion_error(report, plan["maximum_teacher_calls"])
    if failure is not None:
        raise ValidationError(f"{failure}; evidence: {output / 'result.json'}")
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.seed, args.prompts, args.model, args.model_manifest, args.output)


if __name__ == "__main__":
    main()

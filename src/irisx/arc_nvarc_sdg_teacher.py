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


def run(plan_path: Path, seed_path: Path, prompts_path: Path, model_root: Path,
        model_manifest_path: Path, output: Path) -> dict:
    import torch
    from transformers import AutoModelForMultimodalLM, AutoTokenizer

    plan = json.loads(plan_path.read_bytes())
    if (plan.get("format") != "irisx/nvarc-m3-teacher-small-v1" or
            plan.get("approved") is not True or not plan.get("owner_decision") or
            plan.get("maximum_teacher_calls") != 4 or
            plan.get("maximum_model_generations") != 4 or
            plan.get("maximum_paid_usd") != 0 or plan.get("retry") is not False or
            output.exists()):
        raise ValidationError("exact owner-approved small teacher run required")
    if (not torch.cuda.is_available() or torch.cuda.device_count() != 4 or
            "L4" not in torch.cuda.get_device_name(0)):
        raise ValidationError("private Kaggle four-L4 gate failed before teacher load")
    seed_bytes, prompts_bytes = seed_path.read_bytes(), prompts_path.read_bytes()
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
    provider = BoundedLocalHFTeacher(
        model, tokenizer, model_material_digest=manifest["manifest_digest"],
        maximum_input_tokens=plan["maximum_input_tokens_per_call"],
        maximum_output_tokens=plan["maximum_output_tokens_per_call"],
        maximum_total_tokens=plan["maximum_total_reserved_tokens"])
    ledgers = run_teacher_pipeline([seed["record"]], json.loads(prompts_bytes), provider,
                                   output / "stage-ledgers", seed=24,
                                   maximum_calls=plan["maximum_teacher_calls"])
    responses = []
    for stage, ledger in ledgers["stages"].items():
        for record in ledger["records"].values():
            if record["status"] == "complete":
                responses.append({"stage": stage, "usage": {key: record["response"][key]
                                  for key in ("input_tokens", "output_tokens")},
                                  "response_digest": record["response_digest"]})
    report = {"format": "irisx/nvarc-m3-teacher-small-result-v1",
              "run_id": plan["run_id"], "plan_digest": digest_value(plan),
              "seed_record_sha256": plan["seed_record_sha256"],
              "teacher_model_manifest_digest": manifest["manifest_digest"],
              "reserved_calls": ledgers["reserved_calls"],
              "reserved_tokens": provider.reserved_tokens,
              "completed_calls": len(responses), "responses": responses,
              "wall_seconds": time.monotonic() - started,
              "contains_evaluator_truth": False,
              "claim": "local Qwen3.5-4B teacher smoke; no NVARC teacher parity or generated data acceptance"}
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_bytes(canonical_bytes(report, newline=True))
    if report["completed_calls"] != plan["maximum_teacher_calls"]:
        raise ValidationError("local SDG teacher batch ended before all four calls completed")
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

"""Bounded source solve from an existing SFT inference export, never SFT resume."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .arc_nvarc_representation import verify_model_material
from .arc_nvarc_source_runtime import run_source_profile
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


RUN = "nvarc-m2-source-cont-001"
RUN_DECISIONS = {RUN: "Decision 0033", "nvarc-m2-source-cont-002": "Decision 0034"}
EXPORT = "sha256:481d9f12d573b39b0703e47b5f8f6f518a7ccd7847824ffb3f0fb96b11f2c3e6"
TRAINING = "sha256:40804d408005b666cb377aab623bd6b0edcfbcdaa4743049d26e7e65500f5fc4"


def validate_plan(plan: dict, *, approved: bool) -> None:
    run_id = plan.get("run_id")
    original = run_id == RUN
    if (plan.get("format") != "irisx/nvarc-m2-source-continuation-v1" or
            run_id not in RUN_DECISIONS or plan.get("approved") is not approved or
            plan.get("export_material_digest") != EXPORT or
            plan.get("training_identity_digest") != TRAINING or
            plan.get("maximum_sft_steps") != 0 or plan.get("maximum_ttt_steps") != 1 or
            plan.get("maximum_source_generation_calls") != 4 or
            plan.get("maximum_new_tokens") != 64 or plan.get("maximum_dfs_expansions") != 128 or
            plan.get("maximum_paid_usd") != 0 or plan.get("retry") is not False or
            plan.get("maximum_kernel_wall_seconds") != 1800 or
            plan.get("maximum_output_retrievals") != (1 if original else 0) or
            plan.get("maximum_model_dataset_versions") != (1 if original else 0) or
            plan.get("maximum_accepted_kernel_versions") != 1):
        raise ValidationError("source continuation identity or bounds differ")
    if approved:
        if plan.get("owner_decision") != RUN_DECISIONS[run_id] or plan.get("kernel_id") != "danielwuu/" + run_id:
            raise ValidationError("exact new owner-approved source continuation required")
    elif plan.get("owner_decision") is not None or plan.get("kernel_id") != "DRAFT-DO-NOT-PUSH/" + run_id:
        raise ValidationError("source continuation draft must be inert")


def run(plan_path: Path, config: Path, visible: Path, bundle: Path,
        model: Path, evidence: Path, output: Path) -> dict:
    plan = json.loads(plan_path.read_bytes())
    validate_plan(plan, approved=True)
    return _run_bound(plan, config, visible, bundle, model, evidence, output)


def _run_bound(plan: dict, config: Path, visible: Path, bundle: Path,
               model: Path, evidence: Path, output: Path, *, model_ready=None, call_observer=None) -> dict:
    """Internal workload; caller must enforce its own exact execution profile."""
    if output.exists():
        raise ValidationError("new source continuation output required")
    for name, path in (("source_config", config), ("visible", visible), ("training_evidence", evidence)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != plan[name + "_sha256"]:
            raise ValidationError("source continuation input differs: " + name)
    lineage = json.loads(evidence.read_bytes())
    if (lineage.get("export_material_digest") != EXPORT or
            lineage.get("training_identity_digest") != TRAINING or
            lineage.get("optimizer_checkpoint_retained") is not False):
        raise ValidationError("source continuation training lineage differs")
    cfg = json.loads(config.read_bytes())
    if (cfg["candidate"]["maximum_calls_per_task"] != 4 or
            cfg["candidate"]["maximum_new_tokens"] != 64 or
            cfg["candidate"]["dfs_max_expansions"] != 128 or cfg["adaptation"]["steps"] != 1 or
            list(json.loads(visible.read_bytes())) != ["00576224"]):
        raise ValidationError("source continuation workload differs")
    material = verify_model_material(model, EXPORT)
    if material.get("training_identity_digest") != TRAINING:
        raise ValidationError("source continuation model ancestry differs")
    result_path = output / "source-result.json"
    result = run_source_profile(config, visible, result_path, profile="4b", checkpoint=model,
                                material_digest=EXPORT, bundle=bundle,
                                bundle_digest=plan["source_bundle_digest"], model_ready=model_ready,
                                call_observer=call_observer)
    calls = max(item["generation_calls_so_far"] for item in result["results"])
    verification_calls = max(item["verification_calls_so_far"] for item in result["results"])
    if calls > 4 or result["task_count"] != 1:
        raise ValidationError("source continuation work exceeded bounds")
    report = {"format": "irisx/nvarc-m2-source-continuation-result-v1", "run_id": plan["run_id"],
              "plan_digest": digest_value(plan), "export_material_digest": EXPORT,
              "training_identity_digest": TRAINING, "source_bundle_digest": plan["source_bundle_digest"],
              "training_evidence_sha256": plan["training_evidence_sha256"],
              "source_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
              "sft_steps": 0, "optimizer_checkpoint_retained": False,
              "generation_calls": calls, "verification_calls": verification_calls,
              "nonempty_ranking_observed": verification_calls > 0,
              "contains_evaluator_truth": False}
    (output / "continuation-chain.json").write_bytes(canonical_bytes(report, newline=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "config", "visible", "bundle", "model", "evidence", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.config, args.visible, args.bundle, args.model, args.evidence, args.output)


if __name__ == "__main__":
    main()

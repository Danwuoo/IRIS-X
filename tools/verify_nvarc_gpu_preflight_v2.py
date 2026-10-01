"""Verify bounded GPU diagnostics offline; checkpoint bytes remain ephemeral."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_gpu_preflight_v2 import RUN, MEMORY_POLICY, check_plan, require_cpu_residency
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def verify(archive_path: Path, package: Path) -> dict:
    plan = json.loads((package / "plan.json").read_bytes())
    rows = json.loads((package / "samples.json").read_bytes())
    summary = json.loads((package / "stage-summary.json").read_bytes())
    identity = check_plan(plan, rows, plan["world_size"])
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        require(len(names) == len(set(names)) and len(names) <= 60, "duplicate/excessive GPU result members")
        require(all(not name.startswith("/") and "\\" not in name and ":" not in name and
            all(p not in {"", ".", ".."} for p in name.split("/")) for name in names), "unsafe GPU result member")
        require(all(not x.is_dir() and not x.flag_bits & 1 and x.file_size <= 8 * 1024**2 and
            (x.external_attr >> 16) & 0o170000 != 0o120000 for x in infos), "unsupported GPU result member")
        require(sum(x.file_size for x in infos) <= 64 * 1024**2, "GPU result exceeds retained limit")
        require("manifest.json" in names, "GPU archive manifest missing")
        require(archive.testzip() is None, "GPU ZIP CRC differs")
        raw = {name: archive.read(name) for name in names}
    index = json.loads(raw.pop("manifest.json"))
    require(index.get("format") == "irisx/nvarc-gpu-preflight-archive-v1" and
        index.get("run_id") == RUN and index.get("plan_digest") == digest_value(plan), "GPU archive plan differs")
    entries = index["members"]
    require(len(entries) == len(raw) and {item["path"] for item in entries} == set(raw), "GPU closed archive inventory differs")
    allowed = {"plan.json", "payload-bindings.json", "hardware-raw.json", "hardware.json", "mount-policy.json",
        "resource-gate.json", "events.jsonl", "selected-lineage.json", "terminal.json", "pause-stdout.log",
        "pause-stderr.log", "resume-stdout.log", "resume-stderr.log", "worker/pause-result.json",
        "worker/final-result.json", "worker/checkpoint-1-manifest.json", "worker/checkpoint-2-manifest.json"}
    allowed |= {f"{prefix}rank-{rank}-trace.jsonl" for prefix in ("worker/", "resume-") for rank in range(4)}
    allowed |= {f"worker/rank-{rank}-{suffix}" for suffix in ("memory.jsonl", "failure.json") for rank in range(4)}
    require(set(raw) <= allowed, "unexpected retained GPU artifact")
    for item in entries:
        value = raw[item["path"]]
        require(len(value) == item["bytes"] and hashlib.sha256(value).hexdigest() == item["sha256"], "GPU member hash differs")
    require(json.loads(raw["plan.json"]) == plan, "returned GPU plan differs")
    require(json.loads(raw["payload-bindings.json"]) == summary["payload_sha256"], "GPU payload bindings differ")
    terminal = json.loads(raw["terminal.json"])
    require(terminal.get("run_id") == RUN and terminal.get("contains_evaluator_truth") is False and
        terminal.get("full_sft_completed") is False and terminal.get("packing_verified") is False,
        "GPU terminal scope differs")
    report = {"run_id": RUN, "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "plan_digest": digest_value(plan), "identity_digest": identity, "member_count": len(raw),
        "member_digests_verified": True, "outcome": terminal["outcome"], "terminal": terminal,
        "checkpoint_bytes_retained": False, "full_sft_completed": False, "packing_verified": False,
        "original_qwen3_nemo_parity": False, "generation_calls": 0, "teacher_calls": 0, "scoring_calls": 0}
    report["memory_policy"] = MEMORY_POLICY
    report["rank_failures"] = []
    for rank in range(4):
        name = f"worker/rank-{rank}-failure.json"
        if name in raw:
            failure = json.loads(raw[name])
            require(failure.get("rank") == rank and failure.get("run_id") == RUN and
                failure.get("identity_digest") == identity and failure.get("contains_evaluator_truth") is False,
                "rank failure identity differs")
            report["rank_failures"].append(failure)
    if terminal["outcome"] == "failed":
        require(terminal.get("phase") and terminal.get("error"), "GPU failure cause missing")
        report["runtime_verified"] = False
        report["worker_steps_verified"] = 0
        if "worker/pause-result.json" in raw:
            paused = json.loads(raw["worker/pause-result.json"])
            manifest = json.loads(raw["worker/checkpoint-1-manifest.json"])
            require(paused["identity_digest"] == identity and paused["step"] == 1 and
                paused["checkpoint"]["manifest_digest"] == digest_value(manifest),
                "partial GPU checkpoint binding differs")
            require(paused["forwards"] == 4 and paused["plan_digest"] == digest_value(plan) and
                paused["input_tokens"] == sum(len(row["input_ids"]) for row in rows[:4]) and
                paused["generation_calls"] == 0 and paused["teacher_calls"] == 0 and
                paused["weight_fingerprint_before"] != paused["weight_fingerprint_after"],
                "partial GPU optimizer/token evidence differs")
            state = manifest["state"]
            require(state["identity_digest"] == identity and state["world_size"] == 4 and
                state["step"] == 1 and state["tokens_seen"] == paused["input_tokens"] and
                state["weight_fingerprint_after"] == paused["weight_fingerprint_after"],
                "partial GPU checkpoint state differs")
            require(len(paused["observations"]) == 1 and len(paused["observations"][0]) == 4 and
                {x["rank"] for x in paused["observations"][0]} == set(range(4)) and
                paused["observations"][0] == state["last_rank_observations"],
                "partial GPU rank observations differ")
            inventory = json.loads(raw["hardware.json"])["inventory"]
            require(len(inventory) == 4 and len({x["uuid"] for x in inventory}) == 4 and
                all(x["name"] == "NVIDIA L4" and x["bf16"] for x in inventory), "partial GPU hardware differs")
            observed = paused["observations"][0]
            for obs in observed:
                require_cpu_residency(obs["state_residency"])
                require(obs["fsdp_cpu_offload_enabled"] is True and obs["checkpointed_layers"] > 0,
                    "partial second-probe CPU offload differs")
                row = rows[obs["rank"]]
                require(all(obs[k] == row[k] for k in ("source_id", "source_row", "puzzle_name", "parent_ids", "exposure_tags")) and
                    obs["input_tokens"] == len(row["input_ids"]) and obs["supervised_tokens"] == sum(x >= 0 for x in row["labels"][1:]) and
                    obs["hardware"]["device_uuid"] == inventory[obs["rank"]]["uuid"] and
                    obs["learning_rate"] == 1e-6 and obs["finite_gradient_tensors"] > 0 and
                    all(math.isfinite(obs[k]) for k in ("global_token_mean_loss", "gradient_norm_before_clip", "wall_seconds")),
                    "partial GPU source/loss/gradient evidence differs")
            restored = all(f"worker/rank-{rank}-trace.jsonl" in raw and
                any(json.loads(line).get("phase") == "checkpoint-restored-and-evicted" and
                    json.loads(line).get("rank") == rank for line in
                    raw[f"worker/rank-{rank}-trace.jsonl"].decode().splitlines()) for rank in range(4))
            report["worker_steps_verified"] = 1
            report.update(input_tokens=paused["input_tokens"], supervised_tokens=paused["supervised_tokens"],
                observations=observed, checkpoint_inventory_bytes=sum(x["bytes"] for x in manifest["files"]),
                checkpoint_restore_fingerprint_gate_reached=restored,
                second_optimizer_step_completed=False)
        for name in ("hardware.json", "resource-gate.json"):
            if name in raw:
                report[name.removesuffix(".json")] = json.loads(raw[name])
        return report
    require(terminal["outcome"] == "complete" and terminal.get("identity_digest") == identity and
        terminal.get("plan_digest") == digest_value(plan) and terminal.get("step") == 2 and
        terminal.get("resumed") is True and terminal.get("generation_calls") == 0 and
        terminal.get("teacher_calls") == 0 and terminal.get("maximum_paid_usd") == 0, "GPU completion envelope differs")
    hardware = json.loads(raw["hardware.json"])
    inventory = hardware["inventory"]
    require(len(inventory) == 4 and len({r["uuid"] for r in inventory}) == 4 and
        all(r["bf16"] is True and r["name"] == "NVIDIA L4" for r in inventory), "four BF16 L4s not verified")
    pause, final = [json.loads(raw[f"worker/{part}-result.json"]) for part in ("pause", "final")]
    all_observed = []
    for step, result in enumerate((pause, final), 1):
        require(result.get("memory_policy") == MEMORY_POLICY and result.get("checkpointed_layers", 0) > 0,
            "second-probe memory/checkpoint policy differs")
        require(result.get("optimizer_steps_returned_this_process") == 1,
            "exactly one optimizer step per controlled worker process required")
        require(result["identity_digest"] == identity and result["plan_digest"] == digest_value(plan) and
            result["step"] == step and result["forwards"] == 4 * step and result["generation_calls"] == 0 and
            result["teacher_calls"] == 0 and result["contains_evaluator_truth"] is False,
            "GPU worker result scope differs")
        manifest = json.loads(raw[f"worker/checkpoint-{step}-manifest.json"])
        require(manifest["format"] == "irisx/nvarc-m2-fsdp-checkpoint-v1" and
            digest_value(manifest) == result["checkpoint"]["manifest_digest"], "GPU checkpoint inventory binding differs")
        state = manifest["state"]
        require(state["identity_digest"] == identity and state["world_size"] == 4 and state["step"] == step and
            state["tokens_seen"] == result["input_tokens"] and state["forwards"] == result["forwards"] and
            state["weight_fingerprint_after"] == result["weight_fingerprint_after"], "GPU checkpoint state differs")
        require(len(result["observations"]) == 1 and len(result["observations"][0]) == 4, "GPU step observation count differs")
        observed = result["observations"][0]
        require(observed == state["last_rank_observations"] and {x["rank"] for x in observed} == set(range(4)), "GPU rank/state observations differ")
        for observation in observed:
            require_cpu_residency(observation["state_residency"])
            require(observation["fsdp_cpu_offload_enabled"] is True and observation["checkpointed_layers"] == result["checkpointed_layers"],
                "GPU CPU-offload/layer checkpoint evidence differs")
            row = rows[(step - 1) * 4 + observation["rank"]]
            require(all(observation[k] == row[k] for k in ("source_id", "source_row", "puzzle_name", "parent_ids", "exposure_tags")) and
                observation["step"] == step and observation["input_tokens"] == len(row["input_ids"]) and
                observation["supervised_tokens"] == sum(x >= 0 for x in row["labels"][1:]), "whole GPU sequence lineage/count differs")
            require(all(math.isfinite(observation[k]) for k in ("learning_rate", "global_token_mean_loss", "gradient_norm_before_clip", "wall_seconds")) and
                observation["finite_gradient_tensors"] > 0 and observation["peak_cuda_allocated_bytes"] > 0,
                "GPU loss/gradient/memory evidence differs")
            require(observation["learning_rate"] == (1e-6 if step == 1 else 1.495e-6), "source warmup learning rate differs")
            require(observation["hardware"]["device_uuid"] == inventory[observation["rank"]]["uuid"],
                "GPU rank UUID differs from parent inventory")
        require(result["weight_fingerprint_after"] != (result["weight_fingerprint_before"] if step == 1 else pause["weight_fingerprint_after"]),
            "GPU step did not change weights")
        all_observed.extend(observed)
    require(final["restored_fingerprint"] == pause["weight_fingerprint_after"] and
        final["input_tokens"] == terminal["input_tokens"] == plan["scheduled_input_tokens"] and
        final["supervised_tokens"] == sum(x["supervised_tokens"] for x in all_observed), "GPU checkpoint resume/whole token sum differs")
    for rank in range(4):
        memory_records = [json.loads(line) for line in raw[f"worker/rank-{rank}-memory.jsonl"].decode().splitlines()]
        require(all(item["rank"] == rank for item in memory_records), "GPU memory rank differs")
        for phase in ("model-ready", "step-1-forward-start", "step-1-backward-complete", "step-1-optimizer-complete",
                      "checkpoint-restored", "step-2-forward-start", "step-2-backward-complete", "step-2-optimizer-complete"):
            matches = [item for item in memory_records if item["phase"] == phase]
            require(len(matches) == (2 if phase == "model-ready" else 1), "GPU memory phase coverage differs")
            for item in matches:
                require_cpu_residency(item["memory"])
        restored = next(item for item in memory_records if item["phase"] == "checkpoint-restored")
        require(restored["restored_fingerprint"] == pause["weight_fingerprint_after"], "rank restore fingerprint differs")
    report.update(runtime_verified=True, worker_steps_verified=2, input_tokens=final["input_tokens"],
        supervised_tokens=final["supervised_tokens"], observations=all_observed, hardware=hardware,
        checkpoint_resume_verified=True, maximum_sequence_length=max(x["input_tokens"] for x in all_observed),
        resource_gate=json.loads(raw["resource-gate.json"]))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    require(not args.report.exists(), "new GPU verification report required")
    report = verify(args.archive, args.package)
    args.report.write_bytes(canonical_bytes(report, newline=True))
    print(json.dumps(report, indent=2))

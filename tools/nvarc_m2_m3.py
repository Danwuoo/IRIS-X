"""One local M2/M3 stage entry. External provider commands are deliberately absent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from irisx.arc_nvarc_m2 import (create_tiny_qwen_material, freeze_arc_sft_data,
                                 load_frozen_arc_sft_data)
from irisx.arc_nvarc_m3_trm import run_tiny_trm
from irisx.arc_nvarc_sdg import (WSLNamespaceProgramExecutor, replay_pinned_ten_stage_sdg,
                                 replay_teacher_program_ledgers)
from irisx.arc_nvarc_trm import integrate_with_qwen_verifier
from irisx.arc_nvarc_representation import export_trained_model, verify_model_material
from irisx.arc_nvarc_training import TaskLocalAdapter, load_compact_model, train_torch_sft
from irisx.arc_nvarc_candidates import QwenCandidateBackend, configure_candidate_backend
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools.nvarc_source_stage import run as run_source_stage

DEFAULT_CONFIG = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-small.json"
SOURCE_STAGE = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/source-integration-stage.json"
SOURCE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/source"


def checked_config(path: Path) -> dict:
    config = json.loads(path.read_bytes())
    if config.get("format") != "irisx/nvarc-m2-m3-small-v1":
        raise ValidationError("M2/M3 stage config differs")
    return config


def checked_source() -> None:
    subprocess.run([sys.executable, str(ROOT / "tools/nvarc_source.py"), "verify"],
                   check=True, stdout=subprocess.DEVNULL)


def tiny_sft(config: dict, data_root: Path, output: Path) -> dict:
    from irisx.arc_nvarc_representation import validate_compact_model
    import torch

    if output.exists():
        raise ValidationError("new tiny SFT output directory required")
    sequences = load_frozen_arc_sft_data(config, data_root)
    data_manifest = json.loads((data_root / "manifest.json").read_bytes())
    model, base_digest = create_tiny_qwen_material(output / "base")
    verify_model_material(output / "base", base_digest)
    # HF save/load normalizes runtime configuration; train the exact reloaded
    # bytes and config that the immutable base material digest identifies.
    del model
    model = load_compact_model(output / "base", dtype="float32")
    train_config = {**config["sft"], "max_steps": config["tiny_cpu_validation_steps"],
                    "maximum_training_tokens": config["tiny_cpu_validation_tokens"]}
    first = train_torch_sft(model, sequences, output / "training", train_config,
                            model_identity_digest=base_digest, stop_after_steps=1)
    if first["stop_reason"] != "controlled_interruption" or first["steps"] != 1:
        raise ValidationError("controlled SFT interruption failed")
    del model
    restored = load_compact_model(output / "base", dtype="float32")
    final = train_torch_sft(restored, sequences, output / "training", train_config,
                            model_identity_digest=base_digest, resume=True)
    if final["steps"] != config["tiny_cpu_validation_steps"] or not final["last_loss"]:
        raise ValidationError("tiny ARC-SFT did not finish")
    state_path = output / "training/training-state.pt"
    state_sha = hashlib.sha256(state_path.read_bytes()).hexdigest()
    export_digest = export_trained_model(restored, output / "base", output / "export",
                                         training_identity_digest=final["identity_digest"])
    verify_model_material(output / "export", export_digest)
    reloaded = load_compact_model(output / "export", dtype="float32")
    validate_compact_model(reloaded, tied=True)
    if any(not torch.equal(value.cpu(), reloaded.state_dict()[key].cpu())
           for key, value in restored.state_dict().items()):
        raise ValidationError("SFT inference export changed weights on reload")
    chain = {"format": "irisx/nvarc-m2-sft-chain-v1", "profile": "tiny-real-qwen3.5-cpu",
             "config_digest": digest_value(config), "data_manifest_digest": digest_value(data_manifest),
             "train_parent_ids": [item["id"] for item in config["train"]],
             "dev_parent_ids": [item["id"] for item in config["dev"]],
             "base_material_digest": base_digest, "training_state_sha256": state_sha,
             "training_identity_digest": final["identity_digest"],
             "sft_export_material_digest": export_digest, "interruption": first,
             "completion": final, "reload_equal": True,
             "contains_evaluator_truth": False, "claim": "full-parameter tiny real architecture path only"}
    (output / "chain.json").write_bytes(canonical_bytes(chain, newline=True))
    return chain


def tiny_solve(config: dict, data_root: Path, sft_root: Path, output: Path) -> dict:
    chain = json.loads((sft_root / "chain.json").read_bytes())
    if (chain.get("format") != "irisx/nvarc-m2-sft-chain-v1" or
            chain.get("config_digest") != digest_value(config) or
            chain.get("reload_equal") is not True):
        raise ValidationError("SFT chain or config differs")
    digest = chain["sft_export_material_digest"]
    verify_model_material(sft_root / "export", digest)
    visible = json.loads((data_root / "dev-visible.json").read_bytes())
    selected = dict(list(sorted(visible.items()))[:config["dev_visible_task_limit"]])
    if not selected or output.exists():
        raise ValidationError("fresh tiny solve output and visible dev task required")
    output.mkdir(parents=True)
    (output / "visible.json").write_bytes(canonical_bytes(selected, newline=True))
    result = run_source_stage(SOURCE_STAGE, output / "visible.json", output / "result.json",
                              profile="tiny", checkpoint=sft_root / "export",
                              material_digest=digest)
    observation = {"format": "irisx/nvarc-m2-solve-chain-v1",
                   "sft_export_material_digest": digest,
                   "source_result_sha256": hashlib.sha256((output / "result.json").read_bytes()).hexdigest(),
                   "task_count": result["task_count"], "test_count": result["test_count"],
                   "generation_calls": sum(x["generation_calls_so_far"] for x in result["results"]),
                   "verification_calls": sum(x["verification_calls_so_far"] for x in result["results"]),
                   "missing_attempts": sum(x["missing_attempts"] for x in result["results"]),
                   "contains_evaluator_truth": False}
    (output / "observation.json").write_bytes(canonical_bytes(observation, newline=True))
    return observation


def tiny_joint(config: dict, data_root: Path, sft_root: Path, qwen_root: Path,
               trm_root: Path, output: Path) -> dict:
    if output.exists():
        raise ValidationError("new joint output required")
    sft = json.loads((sft_root / "chain.json").read_bytes())
    qwen_observation = json.loads((qwen_root / "observation.json").read_bytes())
    qwen_result_path = qwen_root / "result.json"
    qwen_result_sha256 = hashlib.sha256(qwen_result_path.read_bytes()).hexdigest()
    qwen_result = json.loads(qwen_result_path.read_bytes())
    trm_chain = json.loads((trm_root / "chain.json").read_bytes())
    trm_inference_path = trm_root / "inference.json"
    trm_inference_sha256 = hashlib.sha256(trm_inference_path.read_bytes()).hexdigest()
    trm_inference = json.loads(trm_inference_path.read_bytes())
    data_manifest = json.loads((data_root / "manifest.json").read_bytes())
    dev_visible_path = data_root / "dev-visible.json"
    dev_visible_sha256 = hashlib.sha256(dev_visible_path.read_bytes()).hexdigest()
    source_stage_bytes = SOURCE_STAGE.read_bytes()
    source_stage = json.loads(source_stage_bytes)
    candidate_config = source_stage["candidate"]
    digest = sft["sft_export_material_digest"]
    if (sft.get("config_digest") != digest_value(config) or
            sft.get("data_manifest_digest") != digest_value(data_manifest) or
            data_manifest.get("dev_visible_sha256") != dev_visible_sha256 or
            qwen_observation.get("sft_export_material_digest") != digest or
            qwen_observation.get("source_result_sha256") != qwen_result_sha256 or
            qwen_result.get("format") != "irisx/nvarc-source-stage-result-v1" or
            qwen_result.get("material_digest") != digest or
            qwen_result.get("config_sha256") != hashlib.sha256(source_stage_bytes).hexdigest() or
            qwen_result.get("source_profile") != source_stage["source_profile"] or
            qwen_result.get("profile") != "tiny" or
            qwen_result.get("contains_evaluator_truth") is not False or
            trm_chain.get("format") != "irisx/nvarc-m3-trm-cpu-chain-v1" or
            trm_inference.get("format") != "irisx/nvarc-m3-trm-visible-inference-v1" or
            trm_chain["checkpoint_sha256"] != trm_inference["training_checkpoint_sha256"] or
            trm_chain.get("inference_sha256") != trm_inference_sha256 or
            trm_chain["train_parent_ids"] != trm_inference.get("training_exposure") or
            not set(trm_chain["train_parent_ids"]).isdisjoint(
                item["id"] for item in config["dev"]) or
            trm_inference.get("labels_in_inference") is not False or
            trm_inference.get("contains_evaluator_truth") is not False or
            hashlib.sha256((trm_root / "trm-trained.pt").read_bytes()).hexdigest() !=
            trm_chain["checkpoint_sha256"]):
        raise ValidationError("joint parent artifact digest differs")
    verify_model_material(sft_root / "export", digest)
    results = qwen_result["results"]
    visible = json.loads(dev_visible_path.read_bytes())
    selected = dict(list(sorted(visible.items()))[:config["dev_visible_task_limit"]])
    if (hashlib.sha256((qwen_root / "visible.json").read_bytes()).hexdigest() !=
            qwen_result.get("visible_sha256") or
            json.loads((qwen_root / "visible.json").read_bytes()) != selected):
        raise ValidationError("joint Qwen visible task binding differs")
    task_id = trm_inference["task_id"]
    if (len(results) != 1 or results[0]["task_id"] != task_id or
            results[0].get("test_index") != trm_inference.get("test_index") or
            task_id not in selected or trm_inference.get("ttt_visible_demo_parent") != task_id):
        raise ValidationError("joint task/test denominator differs")
    task = {"task_id": task_id, **visible[task_id]}
    model = load_compact_model(sft_root / "export", dtype="float32")
    adapter = TaskLocalAdapter(model, source_stage["adaptation"])
    verifier = QwenCandidateBackend(model, task_adapter=adapter)
    verifier_profile = configure_candidate_backend(verifier, candidate_config)
    qwen = [{"grid": item["grid"], "branch": "qwen", "source": item["sources"][0]
             if item.get("sources") else "qwen"} for item in results[0]["ranked"]]
    trm = ([{"grid": trm_inference["candidate"], "branch": "trm", "source": "trained-ttt"}]
           if trm_inference["status"] == "candidate" else [])
    verifier.begin_task(task)
    try:
        joint = integrate_with_qwen_verifier(task, 0, qwen, trm, verifier,
                                             policy=verifier_profile["ranking"])
        ttt = adapter.last_observation
        forwards = verifier.forward_calls
    finally:
        verifier.end_task()
    output.mkdir(parents=True)
    report = {"format": "irisx/nvarc-m3-joint-v1", "task_id": task_id, "test_index": 0,
              "sft_export_material_digest": digest,
              "data_manifest_digest": digest_value(data_manifest),
              "dev_visible_sha256": dev_visible_sha256,
              "source_candidate_config_digest": digest_value(candidate_config),
              "verifier_profile": {**verifier_profile,
                                   "source_profile": source_stage["source_profile"]},
              "qwen_result_sha256": qwen_result_sha256,
              "trm_checkpoint_sha256": trm_chain["checkpoint_sha256"],
              "trm_inference_sha256": trm_inference_sha256,
              "qwen_candidates": len(qwen), "trm_candidates": len(trm),
              "joint": joint, "qwen_verifier_explicit_forwards": forwards,
              "qwen_task_local_ttt": ttt, "contains_evaluator_truth": False,
              "claim": "tiny trained Qwen and tiny trained TRM CPU branch integration"}
    (output / "result.json").write_bytes(canonical_bytes(report, newline=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze", "tiny-sft", "tiny-solve", "tiny-trm",
                                          "tiny-joint", "sdg-replay", "sdg-teacher-replay"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--sft", type=Path)
    parser.add_argument("--qwen", type=Path)
    parser.add_argument("--trm", type=Path)
    parser.add_argument("--teacher-ledgers", type=Path)
    parser.add_argument("--teacher-seed", type=Path)
    parser.add_argument("--saved-responses", type=Path,
                        default=ROOT / "tests/fixtures/nvarc_sdg_saved_replay.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = checked_config(args.config)
    checked_source()
    if args.stage == "freeze":
        report = freeze_arc_sft_data(config, args.source, args.output or args.data)
    elif args.stage == "tiny-sft":
        if args.output is None:
            parser.error("tiny-sft requires --output")
        report = tiny_sft(config, args.data, args.output)
    elif args.stage == "tiny-solve":
        if args.output is None or args.sft is None:
            parser.error("tiny-solve requires --sft and --output")
        report = tiny_solve(config, args.data, args.sft, args.output)
    elif args.stage == "tiny-trm":
        if args.output is None:
            parser.error("tiny-trm requires --output")
        report = run_tiny_trm(config, args.source / "NVARC/external/TinyRecursiveModels",
                              args.source, args.data, args.output)
    elif args.stage == "tiny-joint":
        if args.output is None or args.sft is None or args.qwen is None or args.trm is None:
            parser.error("tiny-joint requires --sft, --qwen, --trm and --output")
        report = tiny_joint(config, args.data, args.sft, args.qwen, args.trm, args.output)
    elif args.stage == "sdg-replay":
        if args.output is None:
            parser.error("sdg-replay requires --output")
        report = replay_pinned_ten_stage_sdg(args.saved_responses, args.source, args.output,
                                              WSLNamespaceProgramExecutor())
    else:
        if args.output is None or args.teacher_ledgers is None or args.teacher_seed is None:
            parser.error("sdg-teacher-replay requires --teacher-ledgers, --teacher-seed and --output")
        report = replay_teacher_program_ledgers(args.teacher_ledgers, args.teacher_seed,
                                                 args.output, WSLNamespaceProgramExecutor())
    display = report
    if args.stage == "tiny-joint":
        display = {key: value for key, value in report.items() if key not in
                   {"joint", "qwen_task_local_ttt"}}
        display["branch_counts"] = report["joint"]["branch_counts"]
        display["attempt_count"] = len(report["joint"]["attempts"])
    print(json.dumps(display, sort_keys=True))


if __name__ == "__main__":
    main()

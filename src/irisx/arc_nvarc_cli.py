"""Offline NVARC engineering commands; no provider or Kaggle API calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .arc_nvarc_candidates import FixtureCandidateBackend, solve_task
from .arc_nvarc_data import (freeze_shards, freeze_streaming, import_jsonl,
                             stream_import_jsonl, visible_task)
from .arc_nvarc_runtime import (build_outbound, build_result, finalize_interrupted,
                                finish_task, make_binding, make_workload,
                                new_checkpoint, reserve_task, score_sealed,
                                verify_outbound, verify_result)
from .arc_nvarc_training import supervised_sequences, tiny_train
from .arc_nvarc_training import FrozenSequenceStore, load_compact_model, train_torch_sft
from .arc_nvarc_representation import (convert_qwen35_checkpoint, export_trained_model,
                                       verify_model_material)
from .arc_nvarc_transport import stage_runtime_dataset
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError
from .transport import digest_path


def fixture_e2e(output: Path) -> dict[str, Any]:
    """Synthetic data -> tiny gradient -> candidates -> result -> sealed score."""
    if output.exists() and any(output.iterdir()):
        raise ValidationError("fixture output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    a = {"task_id": "fixture-a", "parent_id": "parent-a", "source_id": "synthetic",
         "train": [{"input": [[1]], "output": [[2]]}],
         "test": [{"input": [[3]], "output": [[4]]},
                  {"input": [[5, 0]], "output": [[6, 0]]}]}
    b = {"task_id": "fixture-b", "parent_id": "parent-b", "source_id": "synthetic",
         "train": [{"input": [[7]], "output": [[8]]}],
         "test": [{"input": [[9]], "output": [[2]]}]}
    input_path = output / "synthetic-labelled.jsonl"
    input_path.write_bytes(canonical_bytes(a, newline=True) + canonical_bytes(b, newline=True))
    records = import_jsonl(input_path, split="sft-train", forbidden_parent_ids={"locked"})
    data_manifest = freeze_shards(records, output / "frozen-data", policy="clean-research",
                                  forbidden_parent_ids={"locked"})
    sequences = supervised_sequences(records)
    tiny = tiny_train(sequences, output / "tiny-model", seed=24, steps=2)
    tiny = tiny_train(sequences, output / "tiny-model", seed=24, steps=2, resume=True)
    truth = {raw["task_id"]: raw for raw in (a, b)}
    visible = {task_id: visible_task(task_id, raw) for task_id, raw in truth.items()}
    workload = make_workload(visible, source_digest=digest_value(visible))
    config = {"worker_count": 4, "task_deadline_seconds": 300,
              "session_budget_seconds": 3600, "finalization_reserve_seconds": 300,
              "maximum_calls_per_task": 32, "beams_per_call": 1,
              "maximum_new_tokens": 128, "seed": 24, "color_repeats": 2,
              "ranking": "votes-minus-mean-nll"}
    binding = make_binding(workload, run_id="nvarc-fixture-e2e-001",
                           model_digest=digest_value(tiny),
                           data_digest=digest_value(data_manifest),
                           tokenizer_digest=digest_value({"symbols": 16}),
                           runtime_digest=digest_value({"backend": "fixture-predictions"}),
                           config=config)
    outbound = output / "outbound.zip"
    outbound_digest = build_outbound(outbound, binding, workload)
    verify_outbound(outbound)
    backend = FixtureCandidateBackend({"fixture-a:0": [[[4]]],
                                       "fixture-a:1": [[[9, 0]]],
                                       "fixture-b:0": [[[1]], [[2]]]})
    checkpoint = new_checkpoint(binding, workload)
    for case in workload["cases"]:
        task_id = case["task_id"]
        reserve_task(checkpoint, binding, task_id, rank=0, at_utc="synthetic")
        tests = solve_task(case, backend, config)
        finish_task(checkpoint, task_id, {"task_id": task_id, "tests": tests,
                                          "status": "fixture-complete",
                                          "timing": {"load_seconds": None, "ttt_seconds": None,
                                                     "generate_seconds": None, "rank_seconds": None},
                                          "peak_memory_mib": None})
    finalize_interrupted(checkpoint, workload, reason="not_executed")
    observations = {"format": "irisx/nvarc-fixture-observation", "backend": backend.kind,
                    "new_external_model_calls": 0, "new_gpu_calls": 0,
                    "generation_calls": sum(record["tests"][-1]["generation_calls_so_far"] for record in
                                            checkpoint["completed"].values()),
                    "gpu_busy_time_seconds": None}
    result_path = output / "result.zip"
    result_digest = build_result(result_path, binding, workload, checkpoint, observations)
    verify_result(result_path, binding, workload)
    score = score_sealed(truth, [checkpoint["completed"][key] for key in checkpoint["expected_tasks"]])
    (output / "sealed-fixture-score.json").write_bytes(canonical_bytes(score, newline=True))
    report = {"format": "irisx/nvarc-offline-e2e", "backend": backend.kind,
              "tiny_training_steps": tiny["steps"], "tiny_last_loss": tiny["last_loss"],
              "outbound_digest": outbound_digest, "result_digest": result_digest,
              "score": score, "external_model_calls": 0,
              "claim": "synthetic engineering validation only"}
    (output / "report.json").write_bytes(canonical_bytes(report, newline=True))
    return report


def draft_outbound(challenges: Path, task_ids: list[str], output: Path,
                   binding_fields: dict[str, Any]) -> dict[str, str]:
    """Package a static full-task workload after explicit source selection."""
    source = json.loads(challenges.read_bytes())
    if len(set(task_ids)) != len(task_ids) or not task_ids:
        raise ValidationError("task ids must be nonempty and unique")
    workload = make_workload({task_id: source[task_id] for task_id in task_ids},
                             source_digest=digest_path(challenges))
    binding = make_binding(workload, **binding_fields)
    digest = build_outbound(output, binding, workload)
    return {"outbound_digest": digest, "run_identity_digest": binding["identity_digest"]}


def _authorized(path: Path, *, operation: str, identity_digest: str) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if (value.get("approved") is not True or value.get("operation") != operation or
            value.get("identity_digest") != identity_digest or
            not value.get("owner_decision") or value.get("maximum_paid_usd") is None):
        raise ValidationError("exact owner authorization with nonempty limits is required")
    return value


def load_frozen_sequences(root: Path) -> tuple[FrozenSequenceStore, dict[str, Any]]:
    store = FrozenSequenceStore(root)
    return store, store.manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Qwen3.5 NVARC development")
    commands = parser.add_subparsers(dest="command", required=True)
    fixture = commands.add_parser("fixture-e2e")
    fixture.add_argument("--output", type=Path, required=True)
    freeze = commands.add_parser("freeze-data")
    freeze.add_argument("--input", type=Path, required=True)
    freeze.add_argument("--split", required=True)
    freeze.add_argument("--policy", choices=["clean-research", "competition-reproduction"], required=True)
    freeze.add_argument("--excluded-parents", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--shard-size", type=int, default=8192)
    draft = commands.add_parser("draft-outbound")
    draft.add_argument("--challenges", type=Path, required=True)
    draft.add_argument("--task-ids", type=Path, required=True)
    draft.add_argument("--binding-fields", type=Path, required=True)
    draft.add_argument("--output", type=Path, required=True)
    stage = commands.add_parser("stage-runtime")
    stage.add_argument("--outbound", type=Path, required=True)
    stage.add_argument("--wheel", type=Path, required=True)
    stage.add_argument("--dependency-wheel", type=Path, action="append", default=[])
    stage.add_argument("--output", type=Path, required=True)
    convert = commands.add_parser("convert-compact")
    convert.add_argument("--base", type=Path, required=True)
    convert.add_argument("--output", type=Path, required=True)
    convert.add_argument("--model-revision", required=True)
    convert.add_argument("--model-manifest-digest", required=True)
    convert.add_argument("--authorization", type=Path, required=True)
    train = commands.add_parser("train-sft")
    train.add_argument("--compact-base", type=Path, required=True)
    train.add_argument("--frozen-data", type=Path, required=True)
    train.add_argument("--config", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--authorization", type=Path, required=True)
    train.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "fixture-e2e":
        print(json.dumps(fixture_e2e(args.output), ensure_ascii=False, indent=2))
    elif args.command == "freeze-data":
        excluded = json.loads(args.excluded_parents.read_bytes())
        if not isinstance(excluded, list) or any(not isinstance(value, str) for value in excluded):
            raise ValidationError("excluded parents must be a JSON string list")
        records = stream_import_jsonl(args.input, split=args.split,
                                      forbidden_parent_ids=excluded)
        print(json.dumps(freeze_streaming(records, args.output, policy=args.policy,
                                          forbidden_parent_ids=excluded,
                                          shard_size=args.shard_size), indent=2))
    elif args.command == "draft-outbound":
        fields = json.loads(args.binding_fields.read_bytes())
        task_ids = json.loads(args.task_ids.read_bytes())
        print(json.dumps(draft_outbound(args.challenges, task_ids, args.output, fields), indent=2))
    elif args.command == "stage-runtime":
        print(json.dumps(stage_runtime_dataset(args.outbound, args.wheel, args.output,
                                               args.dependency_wheel), indent=2))
    elif args.command == "convert-compact":
        identity = digest_value({"base_revision": args.model_revision,
                                 "model_manifest_digest": args.model_manifest_digest})
        _authorized(args.authorization, operation="convert-compact", identity_digest=identity)
        print(json.dumps(convert_qwen35_checkpoint(args.base, args.output,
                                                    model_revision=args.model_revision,
                                                    model_manifest_digest=args.model_manifest_digest), indent=2))
    else:
        sequences, data_manifest = load_frozen_sequences(args.frozen_data)
        config = json.loads(args.config.read_bytes())
        model_digest = digest_value(json.loads((args.compact_base / "material-manifest.json").read_bytes()))
        verify_model_material(args.compact_base, model_digest)
        identity = digest_value({"model_digest": model_digest,
                                 "data_digest": digest_value(data_manifest), "config": config})
        authorization = _authorized(args.authorization, operation="train-sft", identity_digest=identity)
        if (authorization.get("maximum_steps") != config.get("max_steps") or
                authorization.get("maximum_training_tokens") != config.get("maximum_training_tokens")):
            raise ValidationError("training authorization limits differ from configuration")
        model = load_compact_model(args.compact_base)
        state = train_torch_sft(model, sequences, args.output, config, resume=args.resume)
        inference_digest = (export_trained_model(model, args.compact_base,
                            args.output / "inference-model",
                            training_identity_digest=state["identity_digest"])
                            if state["stop_reason"] == "maximum_steps" else None)
        print(json.dumps({**state, "inference_model_digest": inference_digest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

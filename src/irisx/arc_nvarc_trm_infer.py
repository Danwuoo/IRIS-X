"""Inference-only entry for the pinned NVARC TRM evaluation functions.

This imports the pinned source's model, test dataloader and evaluate function,
but never calls its train loop or train_batch. The upstream ARC evaluator is
disabled; only raw prediction tensors are saved for truth-free normalization.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys
from typing import Any

from .errors import ValidationError


EXPECTED_EVAL_SHA256 = "62ec1e2f179cd80c58a7f0067ab51c76e2e7eb213959566b015c107c5d98b36f"
RAW_KEYS = {"inputs", "puzzle_identifiers", "q_halt_logits", "preds"}


def _sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def run_inference_core(source: Any, config: Any, *, output: Path,
                       rank: int, world_size: int, cpu_group: Any,
                       max_batches: int) -> dict[str, Any]:
    """Small seam for a CPU harness; production source functions run on CUDA."""
    if (max_batches < 1 or config.evaluators or set(config.eval_save_outputs) != RAW_KEYS or
            not config.load_checkpoint or Path(config.checkpoint_path).resolve() != output.resolve()):
        raise ValidationError("TRM inference must save only raw truth-free outputs")
    loader, metadata = source.create_dataloader(
        config, "test", test_set_mode=True, epochs_per_iter=1,
        global_batch_size=config.global_batch_size, rank=rank, world_size=world_size)
    model, _, _ = source.create_model(config, metadata, rank=rank, world_size=world_size)
    model.eval()
    state = source.TrainState(model=model, optimizers=[], optimizer_lrs=[],
                              carry=None, step=0, total_steps=0)
    output.mkdir(parents=True, exist_ok=True)
    source.evaluate(config, state, itertools.islice(loader, max_batches), metadata,
                    [], rank=rank, world_size=world_size, cpu_group=cpu_group)
    saved = output / f"step_0_all_preds.{rank}"
    if not saved.is_file():
        raise ValidationError("TRM inference did not produce a rank tensor")
    return {"format": "irisx/nvarc-trm-inference-rank", "rank": rank,
            "tensor_path": str(saved), "max_batches": max_batches,
            "training_steps": 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pinned TRM inference only")
    for name in ("source-script", "upstream-root", "data-root", "checkpoint", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--max-batches", type=int, required=True)
    args = parser.parse_args(argv)
    if (_sha256(args.source_script) != EXPECTED_EVAL_SHA256 or
            _sha256(args.checkpoint) != args.checkpoint_sha256 or
            _sha256(args.data_root / "test" / "dataset.json") != args.dataset_sha256 or
            args.max_batches < 1 or not (args.data_root / "identifiers.json").is_file()):
        raise ValidationError("TRM inference source, checkpoint, dataset or limit differs")
    sys.path.insert(0, str(args.upstream_root))
    spec = importlib.util.spec_from_file_location("pinned_nvarc_trm_eval", args.source_script)
    if spec is None or spec.loader is None:
        raise ValidationError("pinned TRM source cannot load")
    source = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = source
    spec.loader.exec_module(source)
    import hydra
    import torch
    import torch.distributed as dist

    rank = int(os.environ.get("RANK", "0"))
    world = int(os.environ.get("WORLD_SIZE", "1"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    if not torch.cuda.is_available() or torch.cuda.device_count() < world:
        raise ValidationError("TRM inference needs its exact CUDA rank count")
    torch.cuda.set_device(local_rank)
    cpu_group = None
    if world > 1:
        dist.init_process_group("nccl")
        cpu_group = dist.new_group(backend="gloo")
    try:
        with hydra.initialize_config_dir(config_dir=str(args.upstream_root / "config"), version_base=None):
            hydra_config = hydra.compose(config_name="cfg_pretrain", overrides=[
                "arch=trm", f"data_paths=[{args.data_root.as_posix()}]",
                f"data_paths_test=[{args.data_root.as_posix()}]",
                "evaluators=[]", "arch.L_layers=2", "arch.H_cycles=4", "arch.L_cycles=4",
                "arch.halt_max_steps=10", "global_batch_size=128",
                f"+load_checkpoint={args.checkpoint.as_posix()}",
                f"+checkpoint_path={args.output.as_posix()}",
                "eval_save_outputs=[inputs,puzzle_identifiers,q_halt_logits,preds]"])
        config = source.PretrainConfig(**hydra_config)
        report = run_inference_core(source, config, output=args.output, rank=rank,
                                    world_size=world, cpu_group=cpu_group,
                                    max_batches=args.max_batches)
        print(json.dumps(report))
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Small CPU execution of the pinned TRM model/loss with isolated labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

from .arc_nvarc_trm import (_decode_trm_tensor, preprocess_source_training_fixture,
                            stage_trm_training, trm_grid)
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


def _source_classes(source_root: Path) -> tuple[Any, Any, Any, Any]:
    from .arc_nvarc_upstream import SOURCE
    from .arc_nvarc_trm import TRM_SOURCE_HASHES, _pinned_file

    if source_root.resolve() != (SOURCE / "NVARC/external/TinyRecursiveModels").resolve():
        raise ValidationError("TRM source is not the verified pinned tree")
    _pinned_file(source_root / "dataset/build_arc_dataset.py", TRM_SOURCE_HASHES["builder"])
    # The pinned source verifier rejects generated Python files in the clone.
    sys.dont_write_bytecode = True
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    from models.recursive_reasoning.trm import TinyRecursiveReasoningModel_ACTV1
    from models.losses import ACTLossHead
    from models.sparse_embedding import CastedSparseEmbeddingSignSGD_Distributed
    from adam_atan2_pytorch import AdamAtan2
    return TinyRecursiveReasoningModel_ACTV1, ACTLossHead, CastedSparseEmbeddingSignSGD_Distributed, AdamAtan2


def _model_config(metadata: Mapping[str, Any]) -> dict[str, Any]:
    # NVARC's H=3, L=4, two layers and original loss/optimizer are kept.
    # Width and ACT horizon are reduced solely for an actual CPU path check.
    return {"batch_size": 1, "seq_len": 900, "puzzle_emb_ndim": 32,
            "num_puzzle_identifiers": int(metadata["num_puzzle_identifiers"]),
            "vocab_size": 12, "H_cycles": 3, "L_cycles": 4, "H_layers": 0,
            "L_layers": 2, "hidden_size": 32, "expansion": 4, "num_heads": 4,
            "pos_encodings": "rope", "halt_max_steps": 2,
            "halt_exploration_prob": 0.0, "forward_dtype": "float32",
            "puzzle_emb_len": 16, "no_ACT_continue": True}


def _batch(input_grid: Any, output_grid: Any | None, *, identifier: int) -> dict[str, Any]:
    import torch

    inputs = trm_grid(input_grid)
    labels = trm_grid(output_grid) if output_grid is not None else [0] * 900
    return {"inputs": torch.tensor([inputs], dtype=torch.int64),
            "labels": torch.tensor([[value if value else -100 for value in labels]], dtype=torch.int64),
            "puzzle_identifiers": torch.tensor([identifier], dtype=torch.int64)}


def _initial_carry_on_device(model: Any, batch: Mapping[str, Any]):
    import torch
    # Upstream pretrain initializes carry inside its device context; the source
    # factories for hidden states/steps/halted otherwise use the CPU default.
    with torch.device(batch['inputs'].device):
        return model.initial_carry(batch)


def _step(model: Any, batch: Mapping[str, Any], optimizers: list[Any]) -> tuple[float, int]:
    import torch

    model.train()
    carry = _initial_carry_on_device(model, batch)
    carry, loss, _, _, _ = model(carry=carry, batch=batch, return_keys=[])
    if not bool(torch.isfinite(loss)):
        raise ValidationError("TRM training loss is non-finite")
    loss.backward()
    nonzero = sum(int(parameter.grad is not None and bool(torch.any(parameter.grad != 0)))
                  for parameter in model.parameters())
    if not nonzero or any(parameter.grad is not None and not bool(torch.isfinite(parameter.grad).all())
                          for parameter in model.parameters()):
        raise ValidationError("TRM gradient missing or non-finite")
    for optimizer in optimizers:
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
    if any(not bool(torch.isfinite(parameter).all()) for parameter in model.parameters()):
        raise ValidationError("TRM weight became non-finite")
    return float(loss.detach()), nonzero


def run_tiny_trm(config: Mapping[str, Any], source_root: Path, source_cache: Path,
                 frozen_data_root: Path, output: Path) -> dict[str, Any]:
    """Train/reload one source TRM step, one demo-only TTT step, infer one test."""
    import numpy as np
    import torch

    if output.exists():
        raise ValidationError("TRM output must be new")
    started = time.monotonic()
    model_class, loss_class, sparse_optimizer_class, adam_class = _source_classes(source_root)
    train_parent = config["train"][0]
    source_file = source_cache / "NVARC/external/ARC-AGI-2/data/training" / f"{train_parent['id']}.json"
    if hashlib.sha256(source_file.read_bytes()).hexdigest() != train_parent["sha256"]:
        raise ValidationError("TRM training parent source differs")
    raw_train = json.loads(source_file.read_bytes())
    if len(raw_train["train"]) < 2:
        raise ValidationError("TRM training parent needs two demonstrations")
    staged = {train_parent["id"]: {"train": raw_train["train"][:1],
                                  "labelled_test": [raw_train["train"][1]]}}
    stage_trm_training(staged, output / "labelled-train", source_digest=digest_value(train_parent),
                       augmentation_count=0)
    processed = preprocess_source_training_fixture(output / "labelled-train",
                                                    output / "processed", augmentation_count=0)
    metadata = processed["dataset_metadata"]
    model_config = _model_config(metadata)
    torch.manual_seed(44)

    def new_model():
        core = model_class(model_config)
        return loss_class(core, loss_type="stablemax_cross_entropy")

    model = new_model()
    sparse = sparse_optimizer_class(model.model.puzzle_emb.buffers(), world_size=1,
                                    lr=0.01, weight_decay=0.1)
    adam = adam_class(model.parameters(), lr=0.0003, weight_decay=0.1,
                      betas=(0.9, 0.95))
    input_array = np.load(output / "processed/train/all__inputs.npy", allow_pickle=False)
    label_array = np.load(output / "processed/train/all__labels.npy", allow_pickle=False)
    if input_array.shape[0] != 2 or label_array.shape != input_array.shape:
        raise ValidationError("TRM source builder arrays differ")
    train_batch = {"inputs": torch.tensor(input_array[:1].copy(), dtype=torch.int64),
                   "labels": torch.tensor(np.where(label_array[:1] == 0, -100,
                                                   label_array[:1].astype(np.int64)).copy(),
                                          dtype=torch.int64),
                   "puzzle_identifiers": torch.tensor([1], dtype=torch.int64)}
    train_started = time.monotonic()
    train_loss, train_gradient_groups = _step(model, train_batch, [sparse, adam])
    train_wall = time.monotonic() - train_started
    checkpoint = output / "trm-trained.pt"
    torch.save({"model": model.state_dict(), "config": model_config,
                "train_parent_ids": [train_parent["id"]], "train_steps": 1,
                "source_builder_digest": processed["stage_digest"]}, checkpoint)
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    reloaded = new_model()
    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if saved["config"] != model_config or saved["train_parent_ids"] != [train_parent["id"]]:
        raise ValidationError("TRM checkpoint exposure/config differs")
    reloaded.load_state_dict(saved["model"])
    if any(not torch.equal(value, reloaded.state_dict()[key]) for key, value in model.state_dict().items()):
        raise ValidationError("TRM trained checkpoint changed on reload")
    dev_id = sorted(item["id"] for item in config["dev"])[0]
    # Read only the truth-free M2 visible artifact, never the dev source file.
    dev_visible = json.loads((frozen_data_root / "dev-visible.json").read_bytes())
    task = dev_visible[dev_id]
    demo = task["train"][0]
    ttt_batch = _batch(demo["input"], demo["output"], identifier=0)
    ttt_sparse = sparse_optimizer_class(reloaded.model.puzzle_emb.buffers(), world_size=1,
                                        lr=0.01, weight_decay=0.1)
    ttt_adam = adam_class(reloaded.parameters(), lr=0.0001, weight_decay=0.0,
                          betas=(0.9, 0.95))
    ttt_started = time.monotonic()
    ttt_loss, ttt_gradient_groups = _step(reloaded, ttt_batch, [ttt_sparse, ttt_adam])
    ttt_wall = time.monotonic() - ttt_started
    reloaded.eval()
    infer_batch = _batch(task["test"][0]["input"], None, identifier=0)
    infer_started = time.monotonic()
    with torch.inference_mode():
        carry = reloaded.model.initial_carry(infer_batch)
        for _ in range(model_config["halt_max_steps"]):
            carry, outputs = reloaded.model(carry=carry, batch=infer_batch)
        predicted = torch.argmax(outputs["logits"], dim=-1)[0].tolist()
    infer_wall = time.monotonic() - infer_started
    try:
        candidate = _decode_trm_tensor(predicted)
        status = "candidate"
    except ValidationError:
        candidate, status = None, "missing-candidate"
    inference = {"format": "irisx/nvarc-m3-trm-visible-inference-v1",
                 "task_id": dev_id, "test_index": 0, "candidate": candidate,
                 "status": status, "model_kind": "pinned-upstream-TRM-tiny-width-CPU",
                 "training_checkpoint_sha256": checkpoint_sha,
                 "training_exposure": [train_parent["id"]],
                 "ttt_visible_demo_parent": dev_id,
                 "labels_in_inference": False, "contains_evaluator_truth": False}
    (output / "inference.json").write_bytes(canonical_bytes(inference, newline=True))
    inference_sha256 = hashlib.sha256((output / "inference.json").read_bytes()).hexdigest()
    report = {"format": "irisx/nvarc-m3-trm-cpu-chain-v1",
              "upstream_revision": "e7b68717f0a6c4cbb4ce6fbef787b14f42083bd9",
              "nvarc_revision": "846d0198efa752534594e321fc3289fc0a06c657",
              "source_builder_stage_digest": processed["stage_digest"],
              "model_config": model_config, "train_parent_ids": [train_parent["id"]],
              "train_steps": 1, "train_loss": train_loss,
              "train_input_tokens": int(train_batch["inputs"].numel()),
              "train_supervised_tokens": int((train_batch["labels"] != -100).sum()),
              "train_model_forwards": 1,
              "train_gradient_groups": train_gradient_groups, "train_wall_seconds": train_wall,
              "checkpoint_sha256": checkpoint_sha, "reload_equal": True,
              "inference_sha256": inference_sha256,
              "ttt_steps": 1, "ttt_loss": ttt_loss,
              "ttt_input_tokens": int(ttt_batch["inputs"].numel()),
              "ttt_supervised_tokens": int((ttt_batch["labels"] != -100).sum()),
              "ttt_model_forwards": 1,
              "ttt_gradient_groups": ttt_gradient_groups, "ttt_wall_seconds": ttt_wall,
              "inference_forwards": model_config["halt_max_steps"],
              "inference_wall_seconds": infer_wall, "candidate_status": status,
              "inference_input_tokens": int(infer_batch["inputs"].numel()),
              "total_wall_seconds": time.monotonic() - started,
              "contains_evaluator_truth": False,
              "claim": "tiny-width CPU architecture and source-loss path; not NVARC scale"}
    try:
        import psutil
        memory = psutil.Process().memory_info()
        report["process_peak_rss_mib"] = getattr(memory, "peak_wset", memory.rss) / 1048576
    except ImportError:
        report["process_peak_rss_mib"] = None
    (output / "chain.json").write_bytes(canonical_bytes(report, newline=True))
    return report

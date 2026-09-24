"""Bounded, source-bound ARC-SFT data and checkpoint chain.

This module never reads evaluation data or scores answers. The tiny profile
exercises the same full-parameter trainer used by a later 4B run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .arc_nvarc_data import source_sdg_messages, visible_task
from .arc_nvarc_representation import GridTokenizer
from .arc_nvarc_training import source_sft_sequences
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


def freeze_arc_sft_data(config: Mapping[str, Any], source_root: Path, output: Path) -> dict[str, Any]:
    """Use only pinned public training parents; augment only the train side."""
    from datasets import Dataset

    if config.get("format") != "irisx/nvarc-m2-m3-small-v1" or output.exists():
        raise ValidationError("M2 config or new output directory required")
    if (config.get("teacher_calls_authorized") != 0 or config.get("paid_usd_authorized") != 0 or
            config.get("augmentation", {}).get("dev_views_per_parent") != 0):
        raise ValidationError("M2 source or execution boundary differs")
    train, dev = config["train"], config["dev"]
    if len(train) != 8 or len(dev) != 8:
        raise ValidationError("M2 parent count differs")
    ids = [item["id"] for item in train + dev]
    if len(set(ids)) != 16 or any(not isinstance(item["sha256"], str) or
                                len(item["sha256"]) != 64 for item in train + dev):
        raise ValidationError("M2 parent or hash repeats")
    # Resolve only exact members of the pinned official training directory.
    source = source_root / "NVARC/external/ARC-AGI-2/data/training"
    if not source.is_dir():
        raise ValidationError("pinned official ARC training source missing")
    records: list[dict[str, Any]] = []
    visible: dict[str, Any] = {}
    lengths: list[int] = []
    for split, selected in (("train", train), ("dev", dev)):
        for item in selected:
            task_id = item["id"]
            if not isinstance(task_id, str) or len(task_id) != 8 or any(c not in "0123456789abcdef" for c in task_id):
                raise ValidationError("ARC task identifier differs")
            path = source / f"{task_id}.json"
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise ValidationError(f"ARC training source digest differs: {task_id}")
            raw = json.loads(payload)
            task = visible_task(task_id, raw)
            if split == "dev":
                visible[task_id] = {"train": task["train"], "test": task["test"]}
                continue
            for view in range(int(config["augmentation"]["train_views_per_parent"])):
                seed = int(config["augmentation"]["seed_start"]) + view
                source_view = source_sdg_messages(task["train"], seed=seed, augment=True)
                records.append({"puzzle_name": f"{task_id}:source-aug-{view:02d}",
                                "messages": source_view["messages"]})
    if len(records) != 128:
        raise ValidationError("M2 augmented episode count differs")
    output.mkdir(parents=True)
    dataset_path = output / "source-sft-dataset"
    Dataset.from_list(records).save_to_disk(dataset_path)
    sequences = source_sft_sequences(str(dataset_path), maximum_records=len(records))
    if len(sequences) != len(records):
        raise ValidationError("source SFT loader did not return all episodes")
    for sequence in sequences:
        length = len(sequence["input_ids"])
        if length > int(config["sft"]["max_sequence_length"]):
            raise ValidationError("source augmentation exceeds unpacked sequence bound")
        lengths.append(length)
    (output / "dev-visible.json").write_bytes(canonical_bytes(visible, newline=True))
    # No labelled dev record or original task bytes enter this output.
    manifest = {"format": "irisx/nvarc-m2-arc-data-v1", "source_revision": config["source_revision"],
                "source_role": "official-ARC-AGI-2-public-training-only",
                "train_parents": train, "dev_parents": dev,
                "excluded_sources": ["arc2_evaluation6", "evaluation", "holdout"],
                "train_episodes": len(records), "dev_augmentation_count": 0,
                "train_sequence_digest": digest_value(sequences),
                "train_sequence_tokens_total": sum(lengths),
                "train_sequence_tokens_max": max(lengths),
                "supervised_tokens_total": sum(sum(token >= 0 for token in s["labels"]) for s in sequences),
                "dev_visible_sha256": hashlib.sha256((output / "dev-visible.json").read_bytes()).hexdigest(),
                "dataset_kind": "labels-in-train-only", "dev_truth_retained": False,
                "selection": config["selection"]}
    (output / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


def load_frozen_arc_sft_data(config: Mapping[str, Any], data_root: Path) -> list[dict[str, Any]]:
    manifest = json.loads((data_root / "manifest.json").read_bytes())
    if (manifest.get("format") != "irisx/nvarc-m2-arc-data-v1" or
            manifest.get("train_parents") != config["train"] or
            manifest.get("dev_parents") != config["dev"] or
            hashlib.sha256((data_root / "dev-visible.json").read_bytes()).hexdigest() !=
            manifest["dev_visible_sha256"]):
        raise ValidationError("ARC-SFT frozen data binding differs")
    sequences = source_sft_sequences(str(data_root / "source-sft-dataset"),
                                     maximum_records=manifest["train_episodes"])
    if digest_value(sequences) != manifest["train_sequence_digest"]:
        raise ValidationError("ARC-SFT source loader output differs")
    return sequences


def create_tiny_qwen_material(output: Path, *, seed: int = 24) -> tuple[Any, str]:
    """Actual tiny Qwen3.5 hybrid architecture for CPU path validation."""
    import torch
    from transformers import Qwen3_5Config, Qwen3_5ForConditionalGeneration
    from .arc_nvarc_representation import BEGIN, END, PAD, SYMBOLS, validate_compact_model

    if output.exists():
        raise ValidationError("tiny compact base output must be new")
    torch.manual_seed(seed)
    config = Qwen3_5Config()
    text = config.text_config
    config.tie_word_embeddings = text.tie_word_embeddings = True
    text.vocab_size = config.vocab_size = 32
    text.hidden_size = 64
    text.intermediate_size = 128
    text.num_hidden_layers = 2
    text.layer_types = ["linear_attention", "full_attention"]
    text.num_attention_heads = 4
    text.num_key_value_heads = 2
    text.head_dim = 16
    text.linear_num_key_heads = text.linear_num_value_heads = 4
    text.linear_key_head_dim = text.linear_value_head_dim = 16
    text.max_position_embeddings = 512
    text.rope_parameters = {"rope_type": "default", "rope_theta": 10000.0,
                            "mrope_section": [1, 1, 0], "mrope_interleaved": True}
    config.vision_config.depth = 1
    config.vision_config.hidden_size = 64
    config.vision_config.intermediate_size = 128
    config.vision_config.num_heads = 4
    config.vision_config.out_hidden_size = 64
    config.vision_config.num_position_embeddings = 16
    model = Qwen3_5ForConditionalGeneration(config)
    model.resize_token_embeddings(16)
    for obj in (model.config, model.config.text_config, model.generation_config):
        obj.pad_token_id, obj.eos_token_id, obj.bos_token_id = PAD, END, BEGIN
    model.config.vocab_size = model.config.text_config.vocab_size = 16
    validate_compact_model(model, tied=True)
    output.mkdir(parents=True)
    model.save_pretrained(output, safe_serialization=True)
    vocabulary = {"format": "irisx/nvarc-compact-vocab", "vocab_size": 16,
                  "symbols": [{"compact_id": i, "symbol": symbol, "source_token_ids": [i]}
                              for i, symbol in enumerate(SYMBOLS)]}
    vocabulary["identity_digest"] = digest_value(vocabulary)
    (output / "grid-vocab.json").write_bytes(canonical_bytes(vocabulary, newline=True))
    (output / "grid-tokenizer.json").write_bytes(canonical_bytes(
        {"format": "irisx/nvarc-grid-tokenizer", "symbols": list(SYMBOLS),
         "pad_token_id": PAD, "eos_token_id": END}, newline=True))
    files = [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "bytes": path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file()]
    material = {"format": "irisx/nvarc-compact-model-material", "tied_embeddings": True,
                "base_model_revision": "tiny-real-qwen3.5-random-seed-24",
                "source_model_manifest_digest": digest_value("tiny-real-qwen3.5-seed-24"),
                "vocabulary_identity_digest": vocabulary["identity_digest"],
                "vision_modules_retained": True, "files": files}
    (output / "material-manifest.json").write_bytes(canonical_bytes(material, newline=True))
    return model, digest_value(material)

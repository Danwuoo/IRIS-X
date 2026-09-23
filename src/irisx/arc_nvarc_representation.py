"""Sixteen-symbol grid grammar and immutable Qwen3.5 embedding conversion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

from .arc_nvarc_data import grid
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


SYMBOLS = tuple("0123456789") + ("\n", "<user>", "<assistant>", "<pad>", "<begin>", "<end>")
USER, ASSISTANT, PAD, BEGIN, END = 11, 12, 13, 14, 15
MODEL_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
TOKENIZER_SHA256 = "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"
PINNED_SOURCE_IDS = tuple(range(15, 25)) + (198, 846, 74455, 248044, 248045, 248046)


class GridTokenizer:
    """Fixed grammar: one digit per cell, newline per row, explicit roles/end.

    Its IDs are deliberately not Qwen3 IDs. A converted checkpoint is required.
    """

    vocab_size = len(SYMBOLS)
    pad_token_id = PAD
    eos_token_id = END

    def encode_grid(self, value: Any) -> list[int]:
        rows = grid(value)
        result: list[int] = []
        for index, row in enumerate(rows):
            if index:
                result.append(10)
            result.extend(row)
        return result

    def decode_grid(self, tokens: list[int]) -> list[list[int]]:
        if not tokens or any(type(token) is not int or token < 0 or token > 10 for token in tokens):
            raise ValidationError("grid token stream contains non-grid symbols")
        rows: list[list[int]] = [[]]
        for token in tokens:
            if token == 10:
                rows.append([])
            else:
                rows[-1].append(token)
        return grid(rows)

    def encode_pair(self, input_grid: Any, output_grid: Any) -> tuple[list[int], list[int]]:
        prefix = [BEGIN, USER] + self.encode_grid(input_grid) + [END, BEGIN, ASSISTANT]
        answer = self.encode_grid(output_grid) + [END]
        tokens = prefix + answer
        labels = [-100] * len(prefix) + answer
        return tokens, labels

    def encode_query(self, task: Mapping[str, Any], test_index: int) -> list[int]:
        if type(test_index) is not int or not 0 <= test_index < len(task["test"]):
            raise ValidationError("invalid test index")
        result: list[int] = []
        for item in task["train"]:
            pair, _ = self.encode_pair(item["input"], item["output"])
            result.extend(pair)
        result.extend([BEGIN, USER] + self.encode_grid(task["test"][test_index]["input"]) +
                      [END, BEGIN, ASSISTANT])
        return result

    def parse_completion(self, tokens: list[int], *, stopped_on_eos: bool) -> list[list[int]] | None:
        if not stopped_on_eos or not tokens or tokens[-1] != END:
            return None
        try:
            return self.decode_grid(tokens[:-1])
        except ValidationError:
            return None


def vocabulary_manifest(source_tokenizer: Any, *, model_revision: str,
                        model_manifest_digest: str) -> dict[str, Any]:
    """Bind each compact row to one or more pinned native tokenizer rows."""
    if not model_revision or not model_manifest_digest.startswith("sha256:"):
        raise ValidationError("immutable model identity required")
    if model_revision != MODEL_REVISION:
        raise ValidationError("compact row map is pinned to one Qwen3.5 revision")
    native = [str(i) for i in range(10)] + ["\n", "user", "assistant", "<|endoftext|>",
                                          "<|im_start|>", "<|im_end|>"]
    rows = []
    for compact_id, text in enumerate(native):
        ids = source_tokenizer.encode(text, add_special_tokens=False)
        if not ids or any(type(value) is not int or value < 0 for value in ids):
            raise ValidationError(f"native tokenizer cannot represent symbol {compact_id}")
        rows.append({"compact_id": compact_id, "symbol": SYMBOLS[compact_id],
                     "native_text": text, "source_token_ids": ids,
                     "initialization": "exact-row" if len(ids) == 1 else "mean-of-native-rows"})
    if tuple(row["source_token_ids"][0] for row in rows if len(row["source_token_ids"]) == 1) != PINNED_SOURCE_IDS or any(len(row["source_token_ids"]) != 1 for row in rows):
        raise ValidationError("pinned Qwen3.5 tokenizer no longer has the verified 16 exact rows")
    manifest = {"format": "irisx/nvarc-compact-vocab", "version": 1,
                "model_revision": model_revision, "model_manifest_digest": model_manifest_digest,
                "symbols": rows, "vocab_size": 16,
                "tokenizer_sha256": TOKENIZER_SHA256,
                "source_difference": "Qwen3.5 tokenizer rows and text-only grammar; source NVARC ids cannot be reused"}
    manifest["identity_digest"] = digest_value(manifest)
    return manifest


def select_rows(weight: Any, manifest: Mapping[str, Any]) -> Any:
    """Torch tensor row selection, also usable with a tiny tensor in unit tests."""
    import torch

    rows = []
    for symbol in manifest["symbols"]:
        indices = symbol["source_token_ids"]
        if max(indices) >= weight.shape[0]:
            raise ValidationError("source row is outside embedding matrix")
        rows.append(weight[torch.tensor(indices, dtype=torch.long, device=weight.device)].mean(dim=0))
    return torch.stack(rows)


def validate_compact_model(model: Any, *, tied: bool | None = None) -> None:
    """Check every token ID that inference and generation use after reload."""
    input_module = model.get_input_embeddings()
    output_module = model.get_output_embeddings()
    if input_module is None or output_module is None:
        raise ValidationError("compact input or output embedding is missing")
    embeddings = input_module.weight
    head = output_module.weight
    if embeddings.shape[0] != 16 or head.shape[0] != 16:
        raise ValidationError("checkpoint is not a compact-grid model")
    configs = [model.config]
    if hasattr(model.config, "text_config"):
        configs.append(model.config.text_config)
    generation = getattr(model, "generation_config", None)
    if generation is None:
        raise ValidationError("compact generation configuration is missing")
    configs.append(generation)
    for config in configs:
        for name, expected in (("pad_token_id", PAD), ("eos_token_id", END),
                               ("bos_token_id", BEGIN)):
            if getattr(config, name, None) != expected:
                raise ValidationError(f"compact {name} differs after reload")
    if tied is not None and (embeddings.data_ptr() == head.data_ptr()) != tied:
        raise ValidationError("compact output-head tying differs after reload")


def convert_qwen35_checkpoint(base_dir: Path, output_dir: Path, *, model_revision: str,
                              model_manifest_digest: str) -> dict[str, Any]:
    """Save a distinct compact checkpoint; never change the base directory.

    The vision module remains in the saved HF model but is never given image
    inputs. Actual Qwen3.5 gradient/load compatibility requires a GPU pilot.
    """
    import torch
    from transformers import AutoModelForMultimodalLM, AutoTokenizer

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValidationError("converted output directory must be empty")
    if base_dir.resolve() == output_dir.resolve() or not base_dir.is_dir():
        raise ValidationError("base checkpoint must be immutable and separate")
    if hashlib.sha256((base_dir / "tokenizer.json").read_bytes()).hexdigest() != TOKENIZER_SHA256:
        raise ValidationError("pinned Qwen3.5 tokenizer digest differs")
    tokenizer = AutoTokenizer.from_pretrained(base_dir, local_files_only=True)
    manifest = vocabulary_manifest(tokenizer, model_revision=model_revision,
                                   model_manifest_digest=model_manifest_digest)
    model = AutoModelForMultimodalLM.from_pretrained(base_dir, local_files_only=True,
                                                      dtype=torch.bfloat16, attn_implementation="sdpa")
    input_weight = model.get_input_embeddings().weight
    source_output_module = model.get_output_embeddings()
    if source_output_module is None:
        raise ValidationError("Qwen output head is not exposed")
    tied = input_weight.data_ptr() == source_output_module.weight.data_ptr()
    source_input = input_weight.detach().clone()
    source_output = source_output_module.weight.detach().clone()
    selected_input = select_rows(source_input, manifest)
    selected_output = select_rows(source_output, manifest)
    model.resize_token_embeddings(16)
    with torch.no_grad():
        model.get_input_embeddings().weight.copy_(selected_input)
        if not tied:
            model.get_output_embeddings().weight.copy_(selected_output)
    if tied:
        model.tie_weights()
    model.config.pad_token_id = PAD
    model.config.eos_token_id = END
    model.config.bos_token_id = BEGIN
    if hasattr(model.config, "vocab_size"):
        model.config.vocab_size = 16
    if hasattr(model.config, "text_config"):
        model.config.text_config.vocab_size = 16
        model.config.text_config.pad_token_id = PAD
        model.config.text_config.eos_token_id = END
        model.config.text_config.bos_token_id = BEGIN
    if getattr(model, "generation_config", None) is not None:
        model.generation_config.pad_token_id = PAD
        model.generation_config.eos_token_id = END
        model.generation_config.bos_token_id = BEGIN
    validate_compact_model(model, tied=tied)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir, safe_serialization=True)
    (output_dir / "grid-vocab.json").write_bytes(canonical_bytes(manifest, newline=True))
    (output_dir / "grid-tokenizer.json").write_bytes(canonical_bytes(
        {"format": "irisx/nvarc-grid-tokenizer", "symbols": SYMBOLS,
         "pad_token_id": PAD, "eos_token_id": END}, newline=True))
    del model
    reloaded = AutoModelForMultimodalLM.from_pretrained(output_dir, local_files_only=True,
                                                        dtype=torch.bfloat16, attn_implementation="sdpa")
    validate_compact_model(reloaded, tied=tied)
    if not torch.equal(reloaded.get_input_embeddings().weight.cpu(), selected_input.cpu()):
        raise ValidationError("converted embedding rows changed on reload")
    if not tied and not torch.equal(reloaded.get_output_embeddings().weight.cpu(), selected_output.cpu()):
        raise ValidationError("converted output rows changed on reload")
    files = []
    for file in sorted(output_dir.iterdir()):
        if file.is_file():
            sha = hashlib.sha256()
            with file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    sha.update(chunk)
            files.append({"path": file.name, "sha256": sha.hexdigest(), "bytes": file.stat().st_size})
    material = {"format": "irisx/nvarc-compact-model-material", "base_model_revision": model_revision,
                "source_model_manifest_digest": model_manifest_digest,
                "vocabulary_identity_digest": manifest["identity_digest"],
                "tied_embeddings": tied, "vision_modules_retained": True, "files": files}
    (output_dir / "material-manifest.json").write_bytes(canonical_bytes(material, newline=True))
    return {"material_digest": digest_value(material), "vocabulary_manifest": manifest,
            "tied_embeddings": tied}


def verify_model_material(root: Path, expected_digest: str) -> dict[str, Any]:
    import hashlib

    material = json.loads((root / "material-manifest.json").read_bytes())
    if digest_value(material) != expected_digest or material.get("format") != "irisx/nvarc-compact-model-material":
        raise ValidationError("compact model material identity differs")
    for item in material["files"]:
        path = root / item["path"]
        if path.parent != root or not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValidationError("compact model member missing or outside root")
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(chunk)
        if sha.hexdigest() != item["sha256"]:
            raise ValidationError("compact model member digest differs")
    return material


def export_trained_model(model: Any, compact_base: Path, output: Path,
                         *, training_identity_digest: str) -> str:
    """Export inference weights separately from optimizer/RNG training state."""
    if output.exists() and any(output.iterdir()):
        raise ValidationError("trained model output directory must be empty")
    if not training_identity_digest.startswith("sha256:"):
        raise ValidationError("training identity is required")
    base_material = json.loads((compact_base / "material-manifest.json").read_bytes())
    tied = bool(base_material["tied_embeddings"])
    validate_compact_model(model, tied=tied)
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output, safe_serialization=True)
    for name in ("grid-vocab.json", "grid-tokenizer.json"):
        shutil.copyfile(compact_base / name, output / name)
    files = []
    for file in sorted(output.iterdir()):
        if file.is_file():
            sha = hashlib.sha256()
            with file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    sha.update(chunk)
            files.append({"path": file.name, "sha256": sha.hexdigest(), "bytes": file.stat().st_size})
    material = {"format": "irisx/nvarc-compact-model-material",
                "kind": "sft-inference-export", "training_identity_digest": training_identity_digest,
                "vocabulary_identity_digest": json.loads((output / "grid-vocab.json").read_bytes())["identity_digest"],
                "vision_modules_retained": True, "tied_embeddings": tied, "files": files}
    (output / "material-manifest.json").write_bytes(canonical_bytes(material, newline=True))
    return digest_value(material)

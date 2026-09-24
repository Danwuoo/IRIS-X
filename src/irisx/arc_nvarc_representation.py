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
BASE_CONFIG_SHA256 = "ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670"
BASE_INDEX_SHA256 = "cf3f798ee02ba45f9622aa8892a47369ab667d0afbf154ee7c2212de42e6302d"
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


def compact_loaded_model(model: Any, manifest: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    """Apply the same 16-row conversion to a loaded source or tiny test model."""
    import torch

    input_weight = model.get_input_embeddings().weight
    source_output_module = model.get_output_embeddings()
    if source_output_module is None:
        raise ValidationError("Qwen output head is not exposed")
    tied = input_weight.data_ptr() == source_output_module.weight.data_ptr()
    selected_input = select_rows(input_weight.detach(), manifest).cpu()
    selected_output = (selected_input if tied else
                       select_rows(source_output_module.weight.detach(), manifest).cpu())
    del input_weight, source_output_module
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
    return tied, selected_input, selected_output


def convert_qwen35_checkpoint(base_dir: Path, output_dir: Path, *, model_revision: str,
                              model_manifest_digest: str,
                              base_manifest_path: Path | None = None,
                              allowed_extra_source_files: set[str] | None = None,
                              allowed_extra_source_directories: Mapping[str, set[str]] | None = None) -> dict[str, Any]:
    """Save a distinct compact checkpoint; never change the base directory.

    The vision module remains in the saved HF model but is never given image
    inputs. Actual Qwen3.5 gradient/load compatibility requires a GPU pilot.
    """
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValidationError("converted output directory must be empty")
    if base_dir.resolve() == output_dir.resolve() or not base_dir.is_dir():
        raise ValidationError("base checkpoint must be immutable and separate")
    verify_source_model_material(base_dir, model_manifest_digest, model_revision,
                                 manifest_path=base_manifest_path,
                                 allowed_extra_files=allowed_extra_source_files,
                                 allowed_extra_directories=allowed_extra_source_directories)
    import torch
    from transformers import AutoModelForMultimodalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_dir, local_files_only=True)
    manifest = vocabulary_manifest(tokenizer, model_revision=model_revision,
                                   model_manifest_digest=model_manifest_digest)
    model = AutoModelForMultimodalLM.from_pretrained(base_dir, local_files_only=True,
                                                      dtype=torch.bfloat16, attn_implementation="sdpa")
    tied, selected_input, selected_output = compact_loaded_model(model, manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir, safe_serialization=True)
    (output_dir / "grid-vocab.json").write_bytes(canonical_bytes(manifest, newline=True))
    (output_dir / "grid-tokenizer.json").write_bytes(canonical_bytes(
        {"format": "irisx/nvarc-grid-tokenizer", "symbols": SYMBOLS,
         "pad_token_id": PAD, "eos_token_id": END}, newline=True))
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
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
    manifest_path = root / "material-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValidationError("compact material manifest is missing or unsafe")
    material = json.loads(manifest_path.read_bytes())
    if (digest_value(material) != expected_digest or
            material.get("format") != "irisx/nvarc-compact-model-material" or
            type(material.get("tied_embeddings")) is not bool):
        raise ValidationError("compact model material identity differs")
    files = _verify_file_inventory(root, material.get("files"), "material-manifest.json")
    _verify_weight_layout(root, files)
    required = {"config.json", "generation_config.json", "grid-vocab.json", "grid-tokenizer.json"}
    if not required.issubset(files):
        raise ValidationError("compact model config or grid tokenizer is missing")
    config = json.loads((root / "config.json").read_bytes())
    generation = json.loads((root / "generation_config.json").read_bytes())
    vocabulary = json.loads((root / "grid-vocab.json").read_bytes())
    tokenizer = json.loads((root / "grid-tokenizer.json").read_bytes())
    if (config.get("text_config", config).get("vocab_size") != 16 or
            vocabulary.get("vocab_size") != 16 or
            vocabulary.get("identity_digest") != digest_value({k: v for k, v in vocabulary.items()
                                                               if k != "identity_digest"}) or
            material.get("vocabulary_identity_digest") != vocabulary["identity_digest"] or
            tokenizer.get("format") != "irisx/nvarc-grid-tokenizer" or
            tokenizer.get("symbols") != list(SYMBOLS) or
            tokenizer.get("pad_token_id") != PAD or tokenizer.get("eos_token_id") != END):
        raise ValidationError("compact vocabulary binding differs")
    for member in (config, config.get("text_config", {}), generation):
        for name, expected in (("pad_token_id", PAD), ("eos_token_id", END),
                               ("bos_token_id", BEGIN)):
            if member.get(name) != expected:
                raise ValidationError("compact model special-token config differs")
    return material


def _verify_file_inventory(root: Path, entries: Any, manifest_name: str | None,
                           allowed_extra_files: set[str] | None = None,
                           allowed_extra_directories: Mapping[str, set[str]] | None = None) -> set[str]:
    if not isinstance(entries, list) or not entries:
        raise ValidationError("model material file inventory is empty")
    names: set[str] = set()
    for item in entries:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"} or
                not isinstance(item["path"], str) or not item["path"] or
                item["path"] in {".", "..", manifest_name} or
                "/" in item["path"] or "\\" in item["path"] or ":" in item["path"] or
                item["path"] in names or type(item["bytes"]) is not int or item["bytes"] < 1 or
                not isinstance(item["sha256"], str) or len(item["sha256"]) != 64 or
                any(char not in "0123456789abcdef" for char in item["sha256"])):
            raise ValidationError("model material member identity is unsafe")
        names.add(item["path"])
        path = root / item["path"]
        if (path.is_symlink() or not path.is_file() or path.stat().st_size != item["bytes"] or
                _file_sha256(path) != item["sha256"]):
            raise ValidationError("model material member digest differs")
    extra_files = allowed_extra_files or set()
    extra_directories = allowed_extra_directories or {}
    actual = {path.name for path in root.iterdir() if path.name != manifest_name}
    if (actual != names | extra_files | set(extra_directories) or
            (names | extra_files) & set(extra_directories) or
            any(path.is_symlink() or
                (not path.is_dir() if path.name in extra_directories else not path.is_file())
                for path in root.iterdir() if path.name != manifest_name)):
        raise ValidationError("model material has an unlisted or unsafe member")
    for dirname, expected_files in extra_directories.items():
        if (not dirname or "/" in dirname or "\\" in dirname or dirname in {".", ".."} or
                not expected_files or any(not member or "\\" in member or
                Path(member).is_absolute() or any(part in {".", ".."} for part in member.split("/"))
                for member in expected_files)):
            raise ValidationError("model material extra directory identity is unsafe")
        directory = root / dirname
        expected_nodes = set(expected_files)
        for member in expected_files:
            expected_nodes.update(parent.as_posix() for parent in Path(member).parents
                                  if parent != Path("."))
        nodes = list(directory.rglob("*"))
        actual_nodes = {path.relative_to(directory).as_posix() for path in nodes}
        if (actual_nodes != expected_nodes or
                any(path.is_symlink() or
                    (not path.is_file() if path.relative_to(directory).as_posix() in expected_files
                     else not path.is_dir()) for path in nodes)):
            raise ValidationError("model material extra directory differs")
    return names


def _file_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _verify_weight_layout(root: Path, names: set[str]) -> None:
    index = "model.safetensors.index.json"
    weights = {name for name in names if name.endswith(".safetensors")}
    if index in names:
        mapping = json.loads((root / index).read_bytes()).get("weight_map")
        if (not isinstance(mapping, dict) or not mapping or
                any(not isinstance(key, str) or not isinstance(value, str) for key, value in mapping.items()) or
                set(mapping.values()) != weights):
            raise ValidationError("model shard index and files differ")
    elif weights != {"model.safetensors"}:
        raise ValidationError("model needs an indexed shard set or one safe tensor")


def verify_source_model_material(root: Path, expected_digest: str,
                                 model_revision: str, *,
                                 manifest_path: Path | None = None,
                                 allowed_extra_files: set[str] | None = None,
                                 allowed_extra_directories: Mapping[str, set[str]] | None = None) -> dict[str, Any]:
    """Verify the approved base inventory before any HF loader sees its files."""
    path = manifest_path if manifest_path is not None else root / "source-model-manifest.json"
    if not path.is_file() or path.is_symlink():
        raise ValidationError("base model inventory is missing")
    manifest = json.loads(path.read_bytes())
    if (digest_value(manifest) != expected_digest or
            manifest.get("format") != "irisx/nvarc-base-model-material" or
            manifest.get("revision") != MODEL_REVISION or model_revision != MODEL_REVISION):
        raise ValidationError("base model identity differs")
    local_name = path.name if path.parent.resolve() == root.resolve() else None
    names = _verify_file_inventory(root, manifest.get("files"), local_name,
                                   allowed_extra_files=allowed_extra_files,
                                   allowed_extra_directories=allowed_extra_directories)
    _verify_weight_layout(root, names)
    if not {"config.json", "tokenizer.json", "model.safetensors.index.json"}.issubset(names):
        raise ValidationError("pinned base config, tokenizer or weight index missing")
    for name, expected in (("config.json", BASE_CONFIG_SHA256),
                           ("tokenizer.json", TOKENIZER_SHA256),
                           ("model.safetensors.index.json", BASE_INDEX_SHA256)):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValidationError(f"pinned base {name} digest differs")
    return manifest


def snapshot_source_model_material(root: Path, output: Path) -> str:
    """Hash an already present pinned base into a separate, immutable inventory."""
    if (not root.is_dir() or output.exists() or output.resolve().is_relative_to(root.resolve()) or
            any(path.is_symlink() or not path.is_file() for path in root.iterdir())):
        raise ValidationError("base snapshot needs a regular directory and new external manifest")
    files = []
    for path in sorted(root.iterdir()):
        files.append({"path": path.name, "sha256": _file_sha256(path),
                      "bytes": path.stat().st_size})
    manifest = {"format": "irisx/nvarc-base-model-material", "revision": MODEL_REVISION,
                "files": files}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(manifest, newline=True))
    digest = digest_value(manifest)
    verify_source_model_material(root, digest, MODEL_REVISION, manifest_path=output)
    return digest


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

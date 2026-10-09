"""Pinned, offline, full-vocabulary small-model material and lazy HF loader.

Importing this module performs no model imports, network access, or GPU calls.
Model bytes are never downloaded here. Material manifests describe manually staged
bytes; upstream SHA-256 anchors below independently bind all load-bearing files.
The Qwen route is deliberately experimental and never falls back to a causal LM.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any


class ContractError(ValueError):
    """A fail-closed material, budget, or execution contract violation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(canonical(value) + b"\n")
    temp.replace(path)


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repository: str
    revision: str
    architecture: str
    model_type: str
    vocab_size: int
    parameters: int
    storage_dtypes: dict[str, int]
    config_fields: dict[str, Any]
    loader_class: str = "AutoModelForCausalLM"
    experimental: bool = False


MODELS = {
    "granite-4.2-8b": ModelSpec(
        "granite-4.2-8b", "ibm-granite/granite-4.2-8b",
        "f8de16cdcdbc6c779ca517604e050d82cc119e44", "GraniteForCausalLM", "granite",
        100352, 8791592960, {"BF16": 8791592960},
        {"num_hidden_layers": 40, "hidden_size": 4096, "intermediate_size": 12800,
         "num_attention_heads": 32, "num_key_value_heads": 8}),
    "qwen3.5-9b": ModelSpec(
        "qwen3.5-9b", "Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
        "Qwen3_5ForConditionalGeneration", "qwen3_5", 248320, 9653104368,
        {"BF16": 9653100528, "F32": 3840},
        {"num_hidden_layers": 32, "hidden_size": 4096, "intermediate_size": 12288,
         "num_attention_heads": 16, "num_key_value_heads": 4, "full_attention_interval": 4},
        "AutoModelForImageTextToText", True),
    "seed-coder-8b-reasoning": ModelSpec(
        "seed-coder-8b-reasoning", "ByteDance-Seed/Seed-Coder-8B-Reasoning",
        "9927b7724deb1f8189da1cc6a50328dfb885d60d", "LlamaForCausalLM", "llama",
        155136, 8250462208, {"F32": 8250462208},
        {"num_hidden_layers": 32, "hidden_size": 4096, "intermediate_size": 14336,
         "num_attention_heads": 32, "num_key_value_heads": 8}),
}

# Filled from revision-pinned official config/tokenizer files and HF LFS metadata.
# These are source SHA-256 values, not measurements from an executed GPU run.
PINNED_FILES: dict[str, dict[str, str]] = {'granite-4.2-8b': {'README.md': '01396b1a8596586986fea22cfaa86d0255d19113d71fe09e0b69cc2bfa4307da',
                    'chat_template.jinja': 'f0ba43f79b3cabca5e5a7584c77aec92f49feae45cdf7779c87d9fc54cd90258',
                    'config.json': '85611f4e34633d4e148e6a5f64bc2d3a23ebbc2b014bc87fbda764eecf261cd9',
                    'generation_config.json': '1b9baf0a7959d31d7fb58ff6b506c27d09a73d395cadccc7e6dd1d4b7e43fd9d',
                    'merges.txt': 'b6fe424e334903f7fb84d3a106d9730455f4744b9fe3c21ee136d97a00e72502',
                    'model-00001-of-00004.safetensors': 'baed4f3128d1f2e3792ad896ac5621124929bb4f658722f132e614108751e96c',
                    'model-00002-of-00004.safetensors': '69e7a59b810f4c029339b7a208b4dac0c1eee6b88a66e830e74882cbd191803c',
                    'model-00003-of-00004.safetensors': 'c2c52fd2baa6ec5003d3ac9842bfd782c0a5a80fc9a1b406a007cae6af008a89',
                    'model-00004-of-00004.safetensors': '0dfcc074193c1cb81270fd6e99cace27d4b0461e8739691c2a347b657c030ffc',
                    'model.safetensors.index.json': 'd37ecbd9468d7925034dc40e9633509ef746f54d52ac6050e2ffc3e365e31504',
                    'special_tokens_map.json': 'e9435fefd6d838fd9fcbbc44b97a8e3ff322be7f6dfb7e4fd2468586574bb52b',
                    'tokenizer.json': '883975314d58743726347caaf2c32ac89afd5ad57222cffbc4f052f2ab27b2d7',
                    'tokenizer_config.json': '2007f26df166ed10a2d6fa881c1c8f3cdd151e451469f59b274897f14449835f',
                    'vocab.json': 'a1be0c1e0a89b5bacda6af6f8b63df09668cb8d1f656229ee9123140c9507810'},
 'qwen3.5-9b': {'LICENSE': 'bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a',
                'README.md': 'c5f5a8c2dddab69cfbf05279235aa5fddb137939a06539c4c7637aa900fef6d0',
                'chat_template.jinja': 'a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715',
                'config.json': 'd0883072e01861ed0b2d47be3c16c36a8e81c224c7ffaa310c6558fb3f932b05',
                'merges.txt': 'a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d',
                'model.safetensors-00001-of-00004.safetensors': 'db6f444b43d318c92f360a13a25561a6a65b10c0631b8ed305a426dbaa6c380e',
                'model.safetensors-00002-of-00004.safetensors': '31c7d7e2dd5d207840b31cc59083c8f4c4718959149e0358c0364052bb9a0330',
                'model.safetensors-00003-of-00004.safetensors': '7ec36ba3a4176a44c3c0876ad80c56a2f70c84bf008d82e9501df642f17dadec',
                'model.safetensors-00004-of-00004.safetensors': 'b62b0c4cd7e44edee103ee8f4fe225f246d5e768e07bfd5f25b63a8aa1fdd0c6',
                'model.safetensors.index.json': '26d3539b516be613f39563617cb9d33b3f83d401298125be392c80cefb8f7fe5',
                'preprocessor_config.json': '27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516',
                'tokenizer.json': '5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42',
                'tokenizer_config.json': '316230d6a809701f4db5ea8f8fc862bc3a6f3229c937c174e674ff3ca0a64ac8',
                'video_preprocessor_config.json': '7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13',
                'vocab.json': 'ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003'},
 'seed-coder-8b-reasoning': {'README.md': 'b2eede6f1209da511098bb301046259847c9604bdf7956f280f404f0ba380f3a',
                             'config.json': '931841a74b39cc356a44ee1f7199f3ac2b3a390f793e0db96fee165113423faf',
                             'generation_config.json': '84627c1cf87427a3daea68979e45536913c393c4e8faac927ba6a03fcf50fa5e',
                             'model-00001-of-00007.safetensors': '67b86d0d342342fd2e8e87f8264745443e1374302124895f290a4d7d44b6d4e3',
                             'model-00002-of-00007.safetensors': '8be6c0335d4a5f5ff56a62eefbfd0db98b4f8166f252e6a9de8a5610f790d18f',
                             'model-00003-of-00007.safetensors': '69d6d63c361ad588a202c33cdfb796c3f094ef42ef9bd04a049b0ced289d3690',
                             'model-00004-of-00007.safetensors': '43190f0e6f3b2c983868d8dd378373e81c73384c04e9bfc0d47df86bd6416bd8',
                             'model-00005-of-00007.safetensors': '3b5bc57ee10925dafd62e31723a8836f6a779fed2d397334cf014ccb30bb7684',
                             'model-00006-of-00007.safetensors': '6eba89c9dc6d939aafbb1920c1b5c9feeddb22150397d3a5697ac51f2d1113b3',
                             'model-00007-of-00007.safetensors': 'b7099e7c65dde6a7fbab68f4b2f577b27736a635fdad27cd4afeaf2bcadbffe7',
                             'model.safetensors.index.json': 'a3d436c7e189ebed2fcb8e5d13b59ccec9251336498393e6d723743530ef537e',
                             'special_tokens_map.json': 'dc0c22e96ab28d40c0a808d5bb4d479d22776fd059bddbcc424f25b493a1120d',
                             'tokenizer.json': 'db6520146c388c495a98bbea62ff6d00c0a8935bed33622e33bb33ec71aaafed',
                             'tokenizer_config.json': 'bfc80b9873151e6ffd20247aab73da83ed88f44d39dd25dae834486c4a34048a'}}

SUPPLEMENTAL_FILES = {'granite-4.2-8b': {'LICENSE': {'sha256': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4',
                                'size_bytes': 11357,
                                'source_url': 'https://raw.githubusercontent.com/ibm-granite/granite-4.2-language-models/75355e6ef8c17d72a7b3736654ab525352f5e0b8/LICENSE'}},
 'qwen3.5-9b': {},
 'seed-coder-8b-reasoning': {'LICENSE': {'sha256': '32e6feeb26ff1769664186fc3b9f34e1d36ffe38cac71d8a9fbc64dd506a7fa4',
                                         'size_bytes': 1066,
                                         'source_url': 'https://raw.githubusercontent.com/ByteDance-Seed/Seed-Coder/0a7e8026d77d9d9aebac6fdb55e6eb3a160446c0/LICENSE'}}}

MODEL_CANDIDATES = {key: {"repository": spec.repository, "revision": spec.revision,
                           "vocab_size": spec.vocab_size, "parameters": spec.parameters}
                    for key, spec in MODELS.items()}

CORE_PACKAGES = ("torch", "transformers", "peft", "accelerate", "tokenizers",
                 "huggingface-hub", "safetensors", "jinja2")
GRANITE_BACKEND = {"torch": "2.8.0", "transformers": "5.8.1", "peft": "0.21.0",
                   "accelerate": "1.10.1", "tokenizers": "0.22.2", "huggingface-hub": "1.32.0",
                   "safetensors": "0.8.0", "jinja2": "3.1.6"}


APPROVED_CORE_WHEELS = {'accelerate': {'accelerate-1.10.1-py3-none-any.whl': '3621cff60b9a27ce798857ece05e2b9f56fcc71631cfb31ccf71f0359c311f11'},
 'huggingface-hub': {'huggingface_hub-1.32.0-py3-none-any.whl': 'b0c7c80561969d9cdacdd55fce67ba9584cca0b9d4ea80957a3a5c1445fac5c8'},
 'jinja2': {'jinja2-3.1.6-py3-none-any.whl': '85ece4451f492d0c13c5dd7c13a64681a86afae63a5f347908daf103ce6d2f67'},
 'peft': {'peft-0.21.0-py3-none-any.whl': 'b64eb75fd9dece7401c70e675b8d9de024993b70483691b41c62876f0c7809b7'},
 'safetensors': {'safetensors-0.8.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl': 'fd6f3f93c9a0a7cc2788ee63fb763353d4bd2e89b0751bc78fcf7dda00bea774'},
 'tokenizers': {'tokenizers-0.22.2-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl': '369cc9fc8cc10cb24143873a0d95438bb8ee257bb80c71989e3ee290e8d72c67'},
 'torch': {'torch-2.8.0+cu128-cp311-cp311-manylinux_2_28_x86_64.whl': '039b9dcdd6bdbaa10a8a5cd6be22c4cb3e3589a341e5f904cbb571ca28f55bed',
           'torch-2.8.0+cu128-cp312-cp312-manylinux_2_28_x86_64.whl': '4354fc05bb79b208d6995a04ca1ceef6a9547b1c4334435574353d381c55087c'},
 'transformers': {'transformers-5.8.1-py3-none-any.whl': '5340fb95962162cdfdae5cc91d7f8fedd92ed75216c1154c5e1f590fcf56dd0e'}}

def get_spec(model_key: str) -> ModelSpec:
    require(model_key in MODELS, "exactly one known model_key is required")
    return MODELS[model_key]


def _safe_member(root: Path, name: str) -> Path:
    path = Path(name)
    require(not path.is_absolute() and name and ".." not in path.parts,
            "material member must be a safe relative path")
    candidate = root / path
    # HF snapshot symlinks into an explicitly staged cache are legitimate. Bytes
    # still have to match independently pinned hashes; path discovery is bounded.
    require(candidate.is_file(), "missing local model member: " + name)
    return candidate


def write_material_manifest(model_path: str | Path, model_key: str,
                            manifest_path: str | Path | None = None) -> dict[str, Any]:
    """Hash the exact registry allowlist only; never materialize/download a file."""
    spec = get_spec(model_key)
    root = Path(model_path)
    expected = PINNED_FILES[model_key]
    require(bool(expected), "upstream load-bearing file anchors are unavailable")
    files = []
    for name, expected_hash in sorted(expected.items()):
        path = _safe_member(root, name)
        observed = file_sha256(path)
        require(observed == expected_hash, "upstream hash mismatch: " + name)
        files.append({"path": name, "sha256": observed, "size_bytes": path.stat().st_size})
    supplemental = []
    for name, expected in sorted(SUPPLEMENTAL_FILES.get(model_key, {}).items()):
        member = _safe_member(root, name)
        require(member.stat().st_size == expected["size_bytes"] and file_sha256(member) == expected["sha256"],
                "official supplemental license bytes mismatch: " + name)
        supplemental.append(dict(expected, path=name))
    result = {"format": "irisx/arc-next-model-material-v1", "model_key": model_key,
              "repository": spec.repository, "revision": spec.revision, "files": files,
              "supplemental_files": supplemental,
              "provenance": "exact official revision-pinned load-bearing SHA-256 anchors"}
    write_json(Path(manifest_path or root / "irisx-model-material.json"), result)
    return result


def _safetensor_inventory(path: Path) -> dict[str, dict[str, Any]]:
    """Read only the bounded safe header, validating its payload offsets."""
    with path.open("rb") as stream:
        raw = stream.read(8)
        require(len(raw) == 8, "incomplete safetensors header")
        length = struct.unpack("<Q", raw)[0]
        require(0 < length <= 64 * 1024 * 1024, "unreasonable safetensors header size")
        header = json.loads(stream.read(length))
    payload_size = path.stat().st_size - 8 - length
    require(isinstance(header, dict) and payload_size >= 0, "invalid safetensors file")
    dtypes = {"BF16": 2, "F32": 4, "F16": 2, "F64": 8, "I64": 8,
              "I32": 4, "I16": 2, "I8": 1, "U8": 1, "BOOL": 1}
    inventory = {}
    intervals = []
    for name, entry in header.items():
        if name == "__metadata__":
            continue
        require(isinstance(entry, dict), "invalid tensor entry")
        shape, dtype, offsets = entry.get("shape"), entry.get("dtype"), entry.get("data_offsets")
        require(isinstance(shape, list) and all(type(v) is int and v >= 0 for v in shape),
                "invalid tensor shape")
        require(dtype in dtypes and isinstance(offsets, list) and len(offsets) == 2 and
                all(type(v) is int for v in offsets), "invalid tensor dtype/offsets")
        count = math.prod(shape)
        require(0 <= offsets[0] <= offsets[1] <= payload_size and
                offsets[1] - offsets[0] == count * dtypes[dtype], "tensor payload size mismatch")
        intervals.append(tuple(offsets))
        inventory[name] = {"shape": shape, "dtype": dtype, "elements": count}
    cursor = 0
    for start, end in sorted(intervals):
        require(start == cursor, "tensor payload has gaps or overlaps")
        cursor = end
    require(cursor == payload_size and bool(inventory), "incomplete safetensors payload")
    return inventory


def validate_material(model_path: str | Path, model_key: str = "granite-4.2-8b",
                      manifest_path: str | Path | None = None) -> dict[str, Any]:
    """Verify exact bytes, complete shard map, config, full native vocabulary."""
    root, spec = Path(model_path), get_spec(model_key)
    path = Path(manifest_path or root / "irisx-model-material.json")
    manifest = json.loads(path.read_text())
    expected_files = PINNED_FILES[model_key]
    repair_identity = {}
    if manifest.get("format") == "irisx/arc-next-model-material-v2":
        from tools.arc_next_index_repair import validate_derived_manifest
        expected_files = validate_derived_manifest(root, model_key, manifest)
        repair_identity = {"index_repair_applied": True, "index_repair": manifest["index_repair"],
                           "full_model_load_verified": False}
    else:
        require(manifest.get("format") == "irisx/arc-next-model-material-v1" and
                manifest.get("model_key") == model_key and
                manifest.get("repository") == spec.repository and
                manifest.get("revision") == spec.revision, "pinned model identity mismatch")
    entries = manifest.get("files", [])
    require(isinstance(entries, list), "material files must be a list")
    by_name = {entry["path"]: entry for entry in entries}
    require(len(by_name) == len(entries) and set(by_name) == set(PINNED_FILES[model_key]),
            "exact complete pinned load-bearing inventory required")
    for name, entry in by_name.items():
        member = _safe_member(root, name)
        expected = expected_files[name]
        require(entry.get("sha256") == expected and member.stat().st_size == entry.get("size_bytes")
                and file_sha256(member) == expected, "material bytes mismatch: " + name)
    expected_supplemental = [dict(expected, path=name) for name, expected in
                             sorted(SUPPLEMENTAL_FILES.get(model_key, {}).items())]
    require(manifest.get("supplemental_files", []) == expected_supplemental,
            "exact official supplemental license inventory required")
    for entry in expected_supplemental:
        member = _safe_member(root, entry["path"])
        require(member.stat().st_size == entry["size_bytes"] and file_sha256(member) == entry["sha256"],
                "official supplemental license bytes mismatch")
    # Unlisted recognized model/tokenizer files could silently change HF loading.
    relevant = {p.name for p in root.iterdir() if p.is_file() and
                (p.suffix in {".safetensors", ".bin", ".pt", ".pth", ".jinja"} or
                 p.name in {"config.json", "tokenizer.json", "tokenizer_config.json",
                            "special_tokens_map.json", "generation_config.json", "vocab.json",
                            "merges.txt", "tokenizer.model", "added_tokens.json",
                            "model.safetensors.index.json", "pytorch_model.bin.index.json"})}
    require(not relevant - set(by_name), "unlisted alternative load-bearing model files forbidden")
    config = json.loads((root / "config.json").read_text())
    require(config.get("model_type") == spec.model_type and
            config.get("architectures") == [spec.architecture] and not config.get("auto_map"),
            "native architecture without remote code required")
    text_config = config.get("text_config", config)
    require(text_config.get("vocab_size") == spec.vocab_size and
            all(text_config.get(k) == v for k, v in spec.config_fields.items()),
            "full native model config required; compressed NVARC checkpoints are forbidden")
    index = json.loads((root / "model.safetensors.index.json").read_text())
    weight_map = index.get("weight_map", {})
    require(weight_map and set(weight_map.values()) == {n for n in by_name if n.endswith(".safetensors")},
            "complete exact shard inventory required")
    tensors, counts = {}, {}
    for shard in sorted(set(weight_map.values())):
        inventory = _safetensor_inventory(root / shard)
        require(not set(tensors).intersection(inventory), "duplicate tensor across shards")
        require(all(weight_map.get(name) == shard for name in inventory), "weight index/header mismatch")
        tensors.update(inventory)
        for tensor in inventory.values():
            counts[tensor["dtype"]] = counts.get(tensor["dtype"], 0) + tensor["elements"]
    require(set(tensors) == set(weight_map), "missing indexed model tensors")
    require(counts == spec.storage_dtypes and sum(counts.values()) == spec.parameters,
            "full source parameter/dtype inventory mismatch")
    tokenizer_config = json.loads((root / "tokenizer_config.json").read_text())
    require(not tokenizer_config.get("auto_map"), "remote tokenizer code forbidden")
    template = ((root / "chat_template.jinja").read_text() if "chat_template.jinja" in by_name
                else tokenizer_config.get("chat_template"))
    require(isinstance(template, str) and bool(template.strip()), "native chat template is mandatory")
    tokenizer = json.loads((root / "tokenizer.json").read_text())
    vocabulary = tokenizer.get("model", {}).get("vocab", {})
    require(isinstance(vocabulary, dict) and vocabulary, "complete native tokenizer vocabulary required")
    vocabulary = dict(vocabulary)
    vocabulary.update({token["content"]: token["id"] for token in tokenizer.get("added_tokens", [])})
    token_ids = list(vocabulary.values())
    special_ids = {}
    for key in ("bos_token", "eos_token", "pad_token", "unk_token"):
        value = tokenizer_config.get(key)
        content = value.get("content") if isinstance(value, dict) else value
        special_ids[key + "_id"] = vocabulary.get(content) if content is not None else None
    require(all(type(i) is int and 0 <= i < spec.vocab_size for i in token_ids),
            "tokenizer IDs must fit full native embeddings")
    return {"model_key": model_key, "repository": spec.repository, "revision": spec.revision,
            "model_id": spec.repository + "@" + spec.revision,
            "material_manifest_sha256": file_sha256(path), "files": entries,
            "supplemental_files": expected_supplemental,
            "config_sha256": by_name["config.json"]["sha256"],
            "tokenizer_sha256": by_name["tokenizer.json"]["sha256"],
            "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
            "source_parameter_count": spec.parameters, "source_storage_dtypes": counts,
            "native_embedding_rows": spec.vocab_size, "tokenizer_max_id": max(token_ids),
            "vocabulary_mapping_sha256": digest(vocabulary), "tokenizer_special_ids": special_ids,
            "tensor_inventory_sha256": digest(tensors), "tensor_count": len(tensors),
            "tensor_inventory": tensors,
            "load_dtype": "bfloat16", "source_dtype_conversion": model_key == "seed-coder-8b-reasoning",
            "full_native_vocabulary": True, "gpu_runtime_verified": False,
            "local_material_path": str(root.resolve()), **repair_identity}



def validate_wheel_platform(filename: str) -> None:
    from packaging.tags import sys_tags
    from packaging.utils import parse_wheel_filename
    _, _, _, wheel_tags = parse_wheel_filename(filename)
    require(bool(wheel_tags.intersection(set(sys_tags()))),
            "staged wheel ABI/platform does not match the actual runtime: " + filename)


def validate_environment(lock_path: str | Path, model_key: str) -> dict[str, Any]:
    """Exact operator-staged dependency lock; never install or resolve packages."""
    lock = json.loads(Path(lock_path).read_text())
    versions = lock.get("versions", {})
    require(lock.get("format") == "irisx/arc-next-environment-lock-v1" and
            all(isinstance(versions.get(p), str) and versions[p] for p in CORE_PACKAGES),
            "explicit exact installed dependency lock required")
    require(lock.get("complete_transitive_lock") is True, "complete transitive offline wheel lock required")
    lock_root = Path(lock_path).parent
    wheel_path = lock_root / "wheel-lock.json"
    require(wheel_path.is_file() and file_sha256(wheel_path) == lock.get("wheel_lock_sha256"),
            "environment must bind the complete neighboring wheel lock")
    wheels = json.loads(wheel_path.read_text())
    require(wheels.get("format") == "irisx/arc-next-offline-wheel-lock-v1" and
            wheels.get("all_transitive_wheels_materialized") is True and wheels.get("versions") == versions,
            "complete wheel/installed dependency version closure required")
    require(file_sha256(lock_root / "requirements.lock") == wheels.get("requirements_sha256"),
            "offline requirements lock changed")
    require(wheels.get("files") and {entry["name"]: entry["version"] for entry in wheels["files"].values()} == versions,
            "wheel inventory does not cover every locked distribution")
    for name, entry in wheels["files"].items():
        validate_wheel_platform(name)
        path = _safe_member(lock_root / "wheels", name)
        if entry["name"] in APPROVED_CORE_WHEELS:
            require(APPROVED_CORE_WHEELS[entry["name"]].get(name) == entry["sha256"],
                    "core wheel differs from revision-reviewed official source hash: " + name)
        require(path.stat().st_size == entry["bytes"] and file_sha256(path) == entry["sha256"],
                "staged offline wheel hash changed: " + name)
    require(platform.system() == "Linux" and platform.machine() == "x86_64" and
            sys.version_info[:2] in {(3, 11), (3, 12)} and
            lock.get("python") == wheels.get("python") == platform.python_version(),
            "exact staged Linux x86_64 Python 3.11/3.12 runtime required")
    actual = {name: importlib.metadata.version(name) for name in versions}
    require(actual == versions, "installed package versions differ from reviewed environment lock")
    require(all(actual[name].split("+")[0] == value for name, value in GRANITE_BACKEND.items()),
            "first pilot requires the reviewed HF/PEFT/PyTorch backend tuple")
    require("+cu128" in actual["torch"], "explicit official CUDA 12.8 PyTorch build required")
    optional_modules = ("torchao", "bitsandbytes", "flash_attn", "fla", "causal_conv1d", "vllm", "unsloth")
    require(all(importlib.util.find_spec(name) is None for name in optional_modules),
            "clean BF16 reference environment must omit optional quantization/attention/serving extensions")
    return {"versions": actual, "lock_sha256": file_sha256(Path(lock_path)),
            "wheel_lock_sha256": file_sha256(wheel_path), "complete_transitive_lock_verified": True,
            "optional_backend_modules_absent": list(optional_modules),
            "compatibility_status": "proposed-until-authorized-runtime-success"}


def observe_g4_hardware(torch: Any) -> dict[str, Any]:
    """Explicit one-GPU manual execution gate; never called by CPU preflight."""
    require(torch.cuda.is_available() and torch.cuda.device_count() == 1,
            "manual training requires exactly one visible G4 RTX PRO 6000 GPU")
    props = torch.cuda.get_device_properties(0)
    name = props.name.upper()
    require("RTX PRO 6000" in name and "BLACKWELL" in name and props.total_memory >= 90_000_000_000,
            "expected one 96 GB-class RTX PRO 6000 Blackwell, not deployment L4 hardware")
    require(torch.cuda.is_bf16_supported(), "native BF16 support required")
    capability = tuple(torch.cuda.get_device_capability(0))
    cuda = tuple(int(v) for v in (torch.version.cuda or "0.0").split(".")[:2])
    require(capability == (12, 0) and cuda >= (12, 8) and "sm_120" in torch.cuda.get_arch_list(),
            "Blackwell sm_120 compiled kernels and CUDA >=12.8 required")
    driver = subprocess.run(["nvidia-smi", "--query-gpu=driver_version,uuid",
                             "--format=csv,noheader,nounits", "--id=0"],
                            capture_output=True, text=True, timeout=15, check=True).stdout.strip()
    fields = [part.strip() for part in driver.split(",")]
    require(len(fields) == 2 and all(piece.isdigit() for piece in fields[0].split(".")),
            "exact local NVIDIA driver/UUID observation required")
    driver_version = tuple(int(piece) for piece in fields[0].split("."))
    require(driver_version >= (580, 95, 5), "G4 requires the source-reviewed Linux driver 580.95.05 or newer")
    host_memory = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    require(os.cpu_count() == 48 and host_memory >= 170 * 1024**3,
            "expected g4-standard-48 class 48 vCPU and approximately 180 GiB host memory")
    return {"gpu_count": 1, "gpu_name": props.name, "gpu_total_memory_bytes": props.total_memory,
            "driver_version": fields[0], "gpu_uuid": fields[1], "host_memory_bytes": host_memory,
            "compute_capability": list(capability), "torch_cuda": torch.version.cuda,
            "cpu_count": os.cpu_count(), "bf16_supported": True,
            "target_machine_type": "g4-standard-48", "machine_type_verified": False}


@dataclass
class ModelSession:
    model: Any
    tokenizer: Any
    identity: dict[str, Any]
    torch: Any
    environment: dict[str, Any]


def _loading_info_receipt(loading: dict[str, Any]) -> dict[str, Any]:
    """Bind HF's set-valued loading diagnostics as deterministic JSON arrays.

    Transformers 5.8.1 returns sets even for an exact load. Keep the loader's
    original diagnostics for validation and normalize only its known key fields;
    canonical JSON must still reject unsupported values elsewhere.
    """
    receipt = dict(loading)
    for name in ("missing_keys", "unexpected_keys", "mismatched_keys"):
        value = receipt.get(name)
        if isinstance(value, (set, frozenset)):
            receipt[name] = sorted(value)
    return receipt


def load_candidate(model_path: str | Path, model_key: str = "granite-4.2-8b", *,
                   manifest_path: str | Path | None = None, environment_lock_path: str | Path,
                   device: str = "cuda:0", adapter_path: str | Path | None = None,
                   allow_experimental_qwen: bool = False) -> ModelSession:
    """Load a single pinned local model, never a remote name or a second model.

    This is a real GPU operation for explicitly enabled manual callers. Parent
    workflows must apply their budget/watchdog before calling. Qwen keeps the full
    multimodal container; text-only calls never pass pixels or vision inputs.
    """
    spec = get_spec(model_key)
    require(type(allow_experimental_qwen) is bool, "allow_experimental_qwen must be an exact boolean")
    require(not spec.experimental or allow_experimental_qwen,
            "Qwen needs a separate reviewed modern environment and explicit experimental opt-in")
    require(Path(model_path).is_dir(), "a local model directory is required")
    identity = validate_material(model_path, model_key, manifest_path)
    environment = validate_environment(environment_lock_path, model_key)
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ[name] = "1"
    os.environ["WANDB_DISABLED"] = "true"
    import torch
    import transformers
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        str(model_path), local_files_only=True, trust_remote_code=False, use_fast=True)
    require(tokenizer.chat_template, "loaded native tokenizer template missing")
    resolved_template = tokenizer.get_chat_template()
    require(hashlib.sha256(resolved_template.encode()).hexdigest() == identity["template_sha256"],
            "loaded tokenizer chat template differs from exact source")
    vocab = tokenizer.get_vocab()
    require(vocab and max(vocab.values()) < spec.vocab_size and
            max(vocab.values()) == identity["tokenizer_max_id"] and
            digest(vocab) == identity["vocabulary_mapping_sha256"] and
            all(getattr(tokenizer, name, None) == expected for name, expected in identity["tokenizer_special_ids"].items()),
            "loaded native token mapping or special-token IDs changed")
    loader = getattr(transformers, spec.loader_class, None)
    require(loader is not None, "required native HF model loader is unavailable")
    model, loading = loader.from_pretrained(
        str(model_path), local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.bfloat16, attn_implementation="sdpa", use_safetensors=True,
        low_cpu_mem_usage=True, output_loading_info=True)
    require(type(model).__name__ == spec.architecture, "unexpected loaded architecture")
    missing = loading.get("missing_keys", [])
    unexpected = loading.get("unexpected_keys", [])
    allowed_unexpected = model_key == "qwen3.5-9b" and all(n.startswith("mtp.") for n in unexpected)
    require(not missing and not loading.get("mismatched_keys") and not loading.get("error_msgs") and
            (not unexpected or allowed_unexpected), "unexplained model loading keys or errors")
    input_rows = model.get_input_embeddings().weight.shape[0]
    output_rows = model.get_output_embeddings().weight.shape[0]
    require(input_rows == output_rows == spec.vocab_size, "full native input/output embeddings required")
    loaded_state = model.state_dict()
    source_tensors = identity["tensor_inventory"]
    expected_names = {name for name in source_tensors if not (model_key == "qwen3.5-9b" and name.startswith("mtp."))}
    require(set(loaded_state) == expected_names and
            all(list(loaded_state[name].shape) == source_tensors[name]["shape"] for name in expected_names),
            "every native model tensor must have exact source-key/shape coverage")
    identity["full_loaded_source_tensor_coverage"] = True
    identity["loading_info"] = _loading_info_receipt(loading)
    identity["loaded_parameter_count"] = sum(p.numel() for p in model.parameters())
    expected_count = sum(source_tensors[name]["elements"] for name in expected_names)
    require(identity["loaded_parameter_count"] == expected_count, "loaded native parameter count mismatch")
    dtype_counts = {}
    for parameter in model.parameters():
        dtype = str(parameter.dtype)
        dtype_counts[dtype] = dtype_counts.get(dtype, 0) + parameter.numel()
    require(set(dtype_counts) <= {str(torch.bfloat16), str(torch.float32)},
            "unexpected loaded model dtype; explicit BF16 with native FP32 exceptions only")
    if model_key != "qwen3.5-9b":
        require(set(dtype_counts) == {str(torch.bfloat16)}, "all Granite/Seed base parameters must load as explicit BF16")
    else:
        require(dtype_counts.get(str(torch.float32), 0) <= spec.storage_dtypes["F32"],
                "only the small source-declared Qwen FP32 tensor inventory may remain FP32")
    identity["loaded_dtype_parameter_counts"] = dtype_counts
    identity["attention_backend_policy"] = ("SDPA for full attention; pure PyTorch reference DeltaNet; no FLA/causal-conv1d"
                                             if model_key == "qwen3.5-9b" else "native SDPA")
    identity["qwen_container_policy"] = "full conditional container, text-only calls, retained frozen vision memory" if model_key == "qwen3.5-9b" else None
    identity["unused_source_keys"] = sorted(set(source_tensors) - expected_names)
    model.to(device)
    if adapter_path is not None:
        from peft import PeftModel
        adapter_root = Path(adapter_path)
        binding = json.loads((adapter_root / "adapter-binding.json").read_text())
        require(binding.get("model_id") == identity["model_id"] and
                binding.get("material_manifest_sha256") == identity["material_manifest_sha256"],
                "adapter is not bound to this exact base material")
        for name, expected_hash in binding.get("files", {}).items():
            require(file_sha256(_safe_member(adapter_root, name)) == expected_hash,
                    "exported adapter bytes differ from verified binding")
        require("adapter_model.safetensors" in binding.get("files", {}) and
                "adapter_config.json" in binding.get("files", {}), "incomplete adapter binding")
        adapter_config = json.loads((adapter_root / "adapter_config.json").read_text())
        require(adapter_config.get("base_model_name_or_path") == spec.repository and
                adapter_config.get("revision") == spec.revision, "adapter config exact base identity mismatch")
        model = PeftModel.from_pretrained(model, str(adapter_root), local_files_only=True,
                                         is_trainable=False)
        identity["adapter_binding_sha256"] = file_sha256(adapter_root / "adapter-binding.json")
    return ModelSession(model, tokenizer, identity, torch, environment)


def lora_target_modules(model: Any, model_key: str, torch: Any) -> list[str]:
    """Exact native text-linears only; no vision/MTP/embedding/head adaptation."""
    ordinary = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
    delta = {"in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "out_proj"}
    prefix = "model.language_model.layers." if model_key == "qwen3.5-9b" else "model.layers."
    suffixes = ordinary | (delta if model_key == "qwen3.5-9b" else set())
    modules = [name for name, module in model.named_modules()
               if name.startswith(prefix) and name.rsplit(".", 1)[-1] in suffixes and
               isinstance(module, torch.nn.Linear)]
    require(bool(modules), "no supported native text LoRA targets found")
    spec = get_spec(model_key)
    expected = set()
    for layer in range(spec.config_fields["num_hidden_layers"]):
        stem = prefix + str(layer) + "."
        expected.update(stem + "mlp." + suffix for suffix in ("gate_proj", "up_proj", "down_proj"))
        if model_key == "qwen3.5-9b" and (layer + 1) % 4:
            expected.update(stem + "linear_attn." + suffix for suffix in delta)
        else:
            expected.update(stem + "self_attn." + suffix for suffix in ("q_proj", "k_proj", "v_proj", "o_proj"))
    require(set(modules) == expected,
            "exact per-layer text LoRA coverage required, including every Qwen DeltaNet projection")
    return sorted(modules)

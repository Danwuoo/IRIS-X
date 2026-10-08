"""Explicit, offline, provenance-preserving repair of one official Granite index.

The source's v1 material is deliberately still invalid for loading. This module
does not change upstream pins or weights: it creates a separate v2 material with
a header-derived index and retains the original index and manifest byte-for-byte.
No downloads, model imports, inference, GPU calls, or provider IO occur here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
from typing import Any

from tools import arc_next_models as m


MODEL_KEY = "granite-4.2-8b"
REPOSITORY = "ibm-granite/granite-4.2-8b"
REVISION = "f8de16cdcdbc6c779ca517604e050d82cc119e44"
FORMAT = "irisx/arc-next-model-material-v2"
REPAIR_FORMAT = "irisx/granite-4.2-8b-index-repair-v1"
INDEX_NAME = "model.safetensors.index.json"
MANIFEST_NAME = "irisx-model-material.json"
SOURCE_INDEX_PATH = "provenance/" + INDEX_NAME
SOURCE_MANIFEST_PATH = "provenance/" + MANIFEST_NAME
NOTICE_PATH = "provenance/INDEX_REPAIR_NOTICE.txt"
SOURCE_INDEX_SHA256 = "d37ecbd9468d7925034dc40e9633509ef746f54d52ac6050e2ffc3e365e31504"
SOURCE_MANIFEST_SHA256 = "8a6716cc1a1dfa11c3656024e902f4509ad48ad11d1485d1da401aac17f536e8"
DERIVED_INDEX_SHA256 = "2a8a723176e2f695b1d7cfa8a704dd41ad8149731dda261b3d9fc50f2a1bd375"
DERIVED_INDEX_BYTES = 27695
TENSOR_COUNT = 363
PARAMETER_COUNT = 8791592960
PAYLOAD_BYTES = 17583185920
SOURCE_DECLARED_BYTES = 16761102336
ASSIGNMENT_MISMATCH_COUNT = 241
SOURCE_PROVENANCE = "exact official revision-pinned load-bearing SHA-256 anchors"
DERIVED_PROVENANCE = "official weights unchanged; explicitly derived Granite index with retained source bytes"
NOTICE_BYTES = (
    "IRIS-X MODIFICATION NOTICE: Granite 4.2 8B derived model material\n"
    "\n"
    "This is a locally derived artifact, not an unmodified official model export.\n"
    "Source: ibm-granite/granite-4.2-8b\n"
    "Revision: f8de16cdcdbc6c779ca517604e050d82cc119e44\n"
    "\n"
    "IRIS-X modified model.safetensors.index.json: its weight_map is rebuilt from\n"
    "the verified official safetensors headers and metadata.total_size is corrected\n"
    "to the complete tensor payload size. No tensor values, weights, configuration,\n"
    "tokenizer, chat template, original README, or license bytes were changed.\n"
    "\n"
    "IRIS-X created irisx-model-material.json in explicit derived v2 format, binding\n"
    "the corrected index, all unchanged official files, and this notice. The exact\n"
    "original index and v1 material manifest are retained beside this notice as\n"
    "model.safetensors.index.json and irisx-model-material.json, respectively.\n"
    "The source license remains available at ../LICENSE.\n"
).encode("utf-8")


def _json(body: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            m.require(key not in result, "duplicate JSON key in repair material")
            result[key] = value
        return result
    try:
        return json.loads(body, object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise m.ContractError("invalid JSON in repair material") from exc


def _identity(model_key: str) -> m.ModelSpec:
    spec = m.get_spec(model_key)
    m.require(model_key == MODEL_KEY and spec.key == MODEL_KEY and
              spec.repository == REPOSITORY and spec.revision == REVISION and
              spec.parameters == PARAMETER_COUNT and
              spec.storage_dtypes == {"BF16": PARAMETER_COUNT},
              "index repair is restricted to the exact reviewed Granite revision")
    m.require(m.PINNED_FILES[model_key].get(INDEX_NAME) == SOURCE_INDEX_SHA256,
              "original official index anchor must remain unchanged")
    return spec


def _member(root: Path, name: str) -> Path:
    member = m._safe_member(root, name)
    m.require(not root.is_symlink() and
              not any(p.is_symlink() for p in [member, *member.parents]
                      if p == root or root in p.parents),
              "derived material must contain regular files, not symlinks")
    return member


def _entry(path: Path, name: str, sha256: str | None = None) -> dict[str, Any]:
    return {"path": name, "sha256": sha256 or m.file_sha256(path),
            "size_bytes": path.stat().st_size}


def _verify_source(root: Path, manifest_path: Path, index_path: Path, *,
                   hash_all_files: bool) -> dict[str, Any]:
    """Bind original v1 bytes, including the known-bad index, without loading it.

    In v2 validation the caller's ordinary material loop hashes all root files;
    this function additionally hashes the two retained provenance files. During
    derivation all original files are fully hashed before any destination exists.
    """
    spec = _identity(MODEL_KEY)
    m.require(m.file_sha256(manifest_path) == SOURCE_MANIFEST_SHA256,
              "original material manifest provenance hash mismatch")
    m.require(m.file_sha256(index_path) == SOURCE_INDEX_SHA256,
              "original index provenance hash mismatch")
    source = _json(manifest_path.read_bytes())
    entries = []
    for name, expected in sorted(m.PINNED_FILES[MODEL_KEY].items()):
        path = index_path if name == INDEX_NAME else m._safe_member(root, name)
        if hash_all_files:
            m.require(m.file_sha256(path) == expected, "upstream hash mismatch: " + name)
        entries.append(_entry(path, name, expected))
    supplemental = []
    for name, expected in sorted(m.SUPPLEMENTAL_FILES[MODEL_KEY].items()):
        path = m._safe_member(root, name)
        m.require(path.stat().st_size == expected["size_bytes"],
                  "official supplemental license size mismatch")
        if hash_all_files:
            m.require(m.file_sha256(path) == expected["sha256"],
                      "official supplemental license bytes mismatch")
        supplemental.append(dict(expected, path=name))
    m.require(source == {"format": "irisx/arc-next-model-material-v1",
                         "model_key": MODEL_KEY, "repository": spec.repository,
                         "revision": spec.revision, "files": entries,
                         "supplemental_files": supplemental, "provenance": SOURCE_PROVENANCE},
              "exact original v1 material manifest required")
    return source


def _derive_index(root: Path, source_index_path: Path) -> bytes:
    """Read every actual shard header and reproduce the reviewed repair bytes."""
    spec = _identity(MODEL_KEY)
    original = _json(source_index_path.read_bytes())
    original_map = original.get("weight_map")
    shards = {name for name in m.PINNED_FILES[MODEL_KEY] if name.endswith(".safetensors")}
    m.require(isinstance(original_map, dict) and original_map and
              set(original_map.values()) == shards and
              original.get("metadata", {}).get("total_size") == SOURCE_DECLARED_BYTES,
              "known original shard inventory and declared size required")
    actual_map: dict[str, str] = {}
    counts: dict[str, int] = {}
    payload_bytes = 0
    for name in sorted(shards):
        path = m._safe_member(root, name)
        # Detect duplicate JSON names before the existing strict payload parser.
        with path.open("rb") as stream:
            raw = stream.read(8)
            m.require(len(raw) == 8, "incomplete safetensors header")
            length = struct.unpack("<Q", raw)[0]
            m.require(0 < length <= 64 * 1024 * 1024, "unreasonable safetensors header size")
            _json(stream.read(length))
        inventory = m._safetensor_inventory(path)
        m.require(not set(actual_map).intersection(inventory), "duplicate tensor across shards")
        actual_map.update({tensor: name for tensor in inventory})
        payload_bytes += path.stat().st_size - 8 - length
        for tensor in inventory.values():
            counts[tensor["dtype"]] = counts.get(tensor["dtype"], 0) + tensor["elements"]
    m.require(set(actual_map) == set(original_map), "source index and actual tensor names differ")
    m.require(len(actual_map) == TENSOR_COUNT and counts == spec.storage_dtypes and
              sum(counts.values()) == PARAMETER_COUNT and payload_bytes == PAYLOAD_BYTES,
              "full reviewed tensor count, parameters, dtypes and payload required")
    m.require(sum(original_map[name] != shard for name, shard in actual_map.items()) ==
              ASSIGNMENT_MISMATCH_COUNT, "unexpected original index assignment discrepancy")
    body = m.canonical({"metadata": {"total_size": payload_bytes}, "weight_map": actual_map}) + b"\n"
    m.require(len(body) == DERIVED_INDEX_BYTES and
              hashlib.sha256(body).hexdigest() == DERIVED_INDEX_SHA256,
              "header-derived index differs from the independently reviewed repair")
    return body


def _repair_record(root: Path) -> dict[str, Any]:
    return {"format": REPAIR_FORMAT,
            "method": "rebuild-weight-map-and-total-size-from-verified-safetensors-headers",
            "source_repository": REPOSITORY, "source_revision": REVISION,
            "source_index": _entry(root / SOURCE_INDEX_PATH, SOURCE_INDEX_PATH, SOURCE_INDEX_SHA256),
            "source_material_manifest": _entry(root / SOURCE_MANIFEST_PATH, SOURCE_MANIFEST_PATH,
                                                SOURCE_MANIFEST_SHA256),
            "derived_index": {"path": INDEX_NAME, "sha256": DERIVED_INDEX_SHA256,
                              "size_bytes": DERIVED_INDEX_BYTES},
            "modification_notice": {"path": NOTICE_PATH,
                                    "sha256": hashlib.sha256(NOTICE_BYTES).hexdigest(),
                                    "size_bytes": len(NOTICE_BYTES)},
            "tensor_count": TENSOR_COUNT, "parameters": PARAMETER_COUNT,
            "storage_dtypes": {"BF16": PARAMETER_COUNT}, "tensor_payload_bytes": PAYLOAD_BYTES,
            "source_declared_total_size": SOURCE_DECLARED_BYTES,
            "assignment_mismatch_count": ASSIGNMENT_MISMATCH_COUNT,
            "official_weights_unchanged": True}


def validate_derived_manifest(root: Path, model_key: str,
                              manifest: dict[str, Any]) -> dict[str, str]:
    """Validate the narrow v2 exception; ordinary material checks still follow.

    Returns a separate expected-hash map. The global official pins stay intact.
    This helper alone is not full material validation: use validate_material.
    """
    spec = _identity(model_key)
    m.require(isinstance(manifest, dict) and set(manifest) == {
        "format", "model_key", "repository", "revision", "files", "supplemental_files",
        "provenance", "index_repair"} and manifest.get("format") == FORMAT and
        manifest.get("model_key") == model_key and manifest.get("repository") == spec.repository and
        manifest.get("revision") == spec.revision and manifest.get("provenance") == DERIVED_PROVENANCE,
        "exact derived material identity and schema required")
    for name in [*m.PINNED_FILES[model_key], *m.SUPPLEMENTAL_FILES[model_key],
                 SOURCE_INDEX_PATH, SOURCE_MANIFEST_PATH, NOTICE_PATH, MANIFEST_NAME]:
        _member(root, name)
    provenance = root / "provenance"
    m.require({p.name for p in provenance.iterdir()} == {INDEX_NAME, MANIFEST_NAME, Path(NOTICE_PATH).name},
              "exact retained provenance inventory required")
    m.require((root / NOTICE_PATH).read_bytes() == NOTICE_BYTES,
              "exact prominent modification notice required")
    m.require((root / MANIFEST_NAME).read_bytes() == m.canonical(manifest) + b"\n",
              "canonical root derived material manifest required")
    source = _verify_source(root, root / SOURCE_MANIFEST_PATH, root / SOURCE_INDEX_PATH,
                            hash_all_files=False)
    body = _derive_index(root, root / SOURCE_INDEX_PATH)
    m.require((root / INDEX_NAME).read_bytes() == body, "derived index bytes mismatch")
    m.require(m.canonical(manifest.get("index_repair")) == m.canonical(_repair_record(root)),
              "exact index repair provenance contract required")
    expected_entries = [dict(entry) if entry["path"] != INDEX_NAME else
                        {"path": INDEX_NAME, "sha256": DERIVED_INDEX_SHA256,
                         "size_bytes": DERIVED_INDEX_BYTES} for entry in source["files"]]
    m.require(m.canonical(manifest.get("files")) == m.canonical(expected_entries) and
              m.canonical(manifest.get("supplemental_files")) == m.canonical(source["supplemental_files"]),
              "derived inventory must preserve all original files except the index")
    return dict(m.PINNED_FILES[model_key], **{INDEX_NAME: DERIVED_INDEX_SHA256})


def repair_material(source_path: str | Path, destination_path: str | Path, *,
                    enabled: bool = False, copy_mode: str = "hardlink") -> dict[str, Any]:
    """Create and fully validate fresh derived material; never edit the source.

    Hardlink mode only links unchanged weights, saving disk. Both roots must stay
    immutable after preparation; changing a linked weight invalidates both. Small
    original files and provenance are independent copies. Copy mode isolates all
    inodes. Failures retain a partial destination for diagnosis; never reuse it.
    """
    m.require(type(enabled) is bool, "enabled must be an exact boolean")
    if not enabled:
        return {"status": "disabled"}
    m.require(copy_mode in {"hardlink", "copy"}, "copy_mode must be hardlink or copy")
    source, destination = Path(source_path), Path(destination_path)
    m.require(source.is_dir() and not destination.exists() and not destination.is_symlink(),
              "existing source and fresh destination required")
    source_resolved, destination_resolved = source.resolve(), destination.resolve()
    m.require(source_resolved != destination_resolved and source_resolved not in destination_resolved.parents,
              "destination must not mutate or be nested in the original source")
    source_manifest = _verify_source(source, source / MANIFEST_NAME, source / INDEX_NAME,
                                     hash_all_files=True)
    body = _derive_index(source, source / INDEX_NAME)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "provenance").mkdir()
    for name in sorted(set(m.PINNED_FILES[MODEL_KEY]) | set(m.SUPPLEMENTAL_FILES[MODEL_KEY])):
        if name == INDEX_NAME:
            continue
        original, target = source / name, destination / name
        if copy_mode == "hardlink" and name.endswith(".safetensors"):
            # Resolve a legitimate staged HF cache link, never reproduce a symlink.
            os.link(original.resolve(strict=True), target)
        else:
            shutil.copyfile(original, target)
    shutil.copyfile(source / INDEX_NAME, destination / SOURCE_INDEX_PATH)
    shutil.copyfile(source / MANIFEST_NAME, destination / SOURCE_MANIFEST_PATH)
    (destination / NOTICE_PATH).write_bytes(NOTICE_BYTES)
    (destination / INDEX_NAME).write_bytes(body)
    manifest = dict(source_manifest, format=FORMAT, provenance=DERIVED_PROVENANCE,
                    files=[dict(entry) if entry["path"] != INDEX_NAME else
                           {"path": INDEX_NAME, "sha256": DERIVED_INDEX_SHA256,
                            "size_bytes": DERIVED_INDEX_BYTES} for entry in source_manifest["files"]],
                    index_repair=_repair_record(destination))
    m.write_json(destination / MANIFEST_NAME, manifest)
    identity = m.validate_material(destination, MODEL_KEY)
    return {"status": "verified", "model_key": MODEL_KEY, "copy_mode": copy_mode,
            "source_material_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "derived_material_manifest_sha256": identity["material_manifest_sha256"],
            "derived_index_sha256": DERIVED_INDEX_SHA256,
            "index_repair_applied": True, "tensor_count": identity["tensor_count"],
            "source_parameter_count": identity["source_parameter_count"],
            "destination": str(destination.resolve()), "full_model_load_verified": False,
            "gpu_runtime_verified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--enable-repair", action="store_true")
    parser.add_argument("--copy-mode", choices=("hardlink", "copy"), default="hardlink")
    args = parser.parse_args()
    result = repair_material(args.source, args.destination, enabled=args.enable_repair,
                             copy_mode=args.copy_mode)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

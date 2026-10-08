"""Offline synthetic contracts; fixture anchors are explicitly patched, never real weights."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import arc_next_index_repair as r
from tools import arc_next_models as m


class IndexRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.destination = self.root / "original", self.root / "derived"
        self.source.mkdir()
        self.key = r.MODEL_KEY
        self.shards = ["model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"]
        self.names = ["model.embed_tokens.weight", "lm_head.weight"]
        self.actual_map = dict(zip(self.names, self.shards))
        self.spec = m.ModelSpec(self.key, r.REPOSITORY, r.REVISION, "GraniteForCausalLM",
                               "granite", 2, 8, {"BF16": 8}, {"hidden_size": 2})
        docs = {
            "config.json": {"architectures": ["GraniteForCausalLM"], "model_type": "granite",
                            "vocab_size": 2, "hidden_size": 2},
            "tokenizer.json": {"model": {"vocab": {"zero": 0, "one": 1}}},
            "tokenizer_config.json": {"chat_template": "{{ messages }}"},
            "generation_config.json": {"bos_token_id": 0},
            r.INDEX_NAME: {"metadata": {"total_size": 8},
                           "weight_map": dict(zip(self.names, reversed(self.shards)))},
        }
        for name, value in docs.items():
            m.write_json(self.source / name, value)
        (self.source / "README.md").write_bytes(b"Explicit synthetic fixture, not model evidence.\n")
        for name, shard in self.actual_map.items():
            self.write_shard(shard, {name: {"dtype": "BF16", "shape": [2, 2],
                                           "data_offsets": [0, 8]}}, payload=bytes(8))
        license_body = b"synthetic official license"
        (self.source / "LICENSE").write_bytes(license_body)
        self.supplemental = {"LICENSE": {"sha256": hashlib.sha256(license_body).hexdigest(),
                                         "size_bytes": len(license_body),
                                         "source_url": "https://example.invalid/pinned/LICENSE"}}
        self.anchors = {path.name: m.file_sha256(path) for path in self.source.iterdir()
                        if path.name != "LICENSE"}
        self.patch(patch.dict(m.MODELS, {self.key: self.spec}))
        self.patch(patch.dict(m.PINNED_FILES, {self.key: self.anchors}))
        self.patch(patch.dict(m.SUPPLEMENTAL_FILES, {self.key: self.supplemental}))
        self.corrected = m.canonical({"metadata": {"total_size": 16}, "weight_map": self.actual_map}) + b"\n"
        for name, value in {
            "SOURCE_INDEX_SHA256": self.anchors[r.INDEX_NAME], "PARAMETER_COUNT": 8,
            "PAYLOAD_BYTES": 16, "SOURCE_DECLARED_BYTES": 8, "TENSOR_COUNT": 2,
            "ASSIGNMENT_MISMATCH_COUNT": 2, "DERIVED_INDEX_BYTES": len(self.corrected),
            "DERIVED_INDEX_SHA256": hashlib.sha256(self.corrected).hexdigest(),
        }.items():
            self.patch(patch.object(r, name, value))
        self.reseal_synthetic_source()

    def patch(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    def reseal_synthetic_source(self):
        """Explicitly re-anchor malformed synthetic headers to test structural gates."""
        for name in self.anchors:
            self.anchors[name] = m.file_sha256(self.source / name)
        m.write_material_manifest(self.source, self.key)
        self.patch(patch.object(r, "SOURCE_INDEX_SHA256", self.anchors[r.INDEX_NAME]))
        self.patch(patch.object(r, "SOURCE_MANIFEST_SHA256", m.file_sha256(self.source / r.MANIFEST_NAME)))

    def write_shard(self, shard, header, payload):
        header = m.canonical(header)
        (self.source / shard).write_bytes(struct.pack("<Q", len(header)) + header + payload)

    def repair(self, **kwargs):
        return r.repair_material(self.source, self.destination, enabled=True, **kwargs)

    def rewrite_manifest(self, change):
        path = self.destination / r.MANIFEST_NAME
        manifest = json.loads(path.read_bytes())
        change(manifest)
        m.write_json(path, manifest)

    def test_default_is_inert_and_boolean_gate_is_exact(self):
        with patch.object(r, "_verify_source", side_effect=AssertionError("must be inert")):
            self.assertEqual(r.repair_material("missing", self.destination), {"status": "disabled"})
        self.assertFalse(self.destination.exists())
        with self.assertRaises(m.ContractError):
            r.repair_material(self.source, self.destination, enabled=1)

    def test_derived_copy_preserves_original_pins_and_bytes_and_exposes_provenance(self):
        original = {p.name: p.read_bytes() for p in self.source.iterdir()}
        anchors = dict(self.anchors)
        result = self.repair(copy_mode="copy")
        self.assertEqual(result["status"], "verified")
        self.assertFalse(result["full_model_load_verified"])
        self.assertFalse(result["gpu_runtime_verified"])
        self.assertEqual(self.anchors, anchors)
        self.assertEqual({p.name: p.read_bytes() for p in self.source.iterdir()}, original)
        self.assertEqual((self.destination / r.INDEX_NAME).read_bytes(), self.corrected)
        self.assertEqual((self.destination / r.SOURCE_INDEX_PATH).read_bytes(), original[r.INDEX_NAME])
        self.assertEqual((self.destination / r.SOURCE_MANIFEST_PATH).read_bytes(), original[r.MANIFEST_NAME])
        self.assertEqual((self.destination / r.NOTICE_PATH).read_bytes(), r.NOTICE_BYTES)
        self.assertFalse(any(p.is_symlink() for p in self.destination.rglob("*")))
        self.assertNotEqual((self.source / self.shards[0]).stat().st_ino,
                            (self.destination / self.shards[0]).stat().st_ino)
        identity = m.validate_material(self.destination, self.key)
        self.assertTrue(identity["index_repair_applied"])
        self.assertFalse(identity["full_model_load_verified"])
        self.assertTrue(identity["full_native_vocabulary"])
        self.assertEqual(identity["tensor_count"], 2)
        self.assertEqual(identity["source_parameter_count"], 8)
        self.assertEqual(identity["index_repair"]["source_material_manifest"]["sha256"],
                         r.SOURCE_MANIFEST_SHA256)

    def test_hardlinks_only_unchanged_weights_and_never_original_index(self):
        self.repair()
        for shard in self.shards:
            self.assertEqual((self.source / shard).stat().st_ino, (self.destination / shard).stat().st_ino)
        for name in [r.INDEX_NAME, r.MANIFEST_NAME, "config.json", "LICENSE"]:
            self.assertNotEqual((self.source / name).stat().st_ino, (self.destination / name).stat().st_ino)

    def test_original_v1_still_rejects_the_known_bad_index_after_repair(self):
        self.repair()
        with self.assertRaisesRegex(m.ContractError, "index/header mismatch"):
            m.validate_material(self.source, self.key)

    def test_corrected_index_cannot_be_silently_substituted_into_v1(self):
        (self.source / r.INDEX_NAME).write_bytes(self.corrected)
        with self.assertRaisesRegex(m.ContractError, "material bytes mismatch"):
            m.validate_material(self.source, self.key)

    def test_destination_must_be_fresh_and_outside_original(self):
        self.destination.mkdir()
        with self.assertRaisesRegex(m.ContractError, "fresh destination"):
            self.repair()
        with self.assertRaisesRegex(m.ContractError, "nested"):
            r.repair_material(self.source, self.source / "derived", enabled=True)
        with self.assertRaisesRegex(m.ContractError, "fresh destination"):
            r.repair_material(self.source, self.source, enabled=True)

    def test_source_full_weight_hash_is_required_before_destination_creation(self):
        path = self.source / self.shards[0]
        path.write_bytes(path.read_bytes()[:-1] + b"x")
        with self.assertRaisesRegex(m.ContractError, "upstream hash mismatch"):
            self.repair()
        self.assertFalse(self.destination.exists())

    def test_supplemental_license_hash_is_required_before_derivation(self):
        path = self.source / "LICENSE"
        path.write_bytes(b"x" * path.stat().st_size)
        with self.assertRaisesRegex(m.ContractError, "license bytes mismatch"):
            self.repair()
        self.assertFalse(self.destination.exists())

    def test_original_source_manifest_hash_cannot_be_self_declared(self):
        path = self.source / r.MANIFEST_NAME
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(m.ContractError, "manifest provenance hash mismatch"):
            self.repair()
        self.assertFalse(self.destination.exists())

    def test_tampered_derived_index_rejected_even_if_manifest_rebound(self):
        self.repair()
        path = self.destination / r.INDEX_NAME
        wrong = json.loads(path.read_bytes())
        wrong["metadata"]["total_size"] -= 8
        m.write_json(path, wrong)
        self.rewrite_manifest(lambda value: value["files"].__setitem__(
            next(i for i, e in enumerate(value["files"]) if e["path"] == r.INDEX_NAME),
            r._entry(path, r.INDEX_NAME)))
        with self.assertRaisesRegex(m.ContractError, "derived index bytes mismatch"):
            m.validate_material(self.destination, self.key)

    def test_tampered_weight_payload_rejected(self):
        self.repair(copy_mode="copy")
        path = self.destination / self.shards[0]
        path.write_bytes(path.read_bytes()[:-1] + b"x")
        with self.assertRaisesRegex(m.ContractError, "material bytes mismatch"):
            m.validate_material(self.destination, self.key)

    def test_tampered_original_index_provenance_rejected(self):
        self.repair()
        path = self.destination / r.SOURCE_INDEX_PATH
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(m.ContractError, "index provenance hash mismatch"):
            m.validate_material(self.destination, self.key)

    def test_tampered_original_manifest_provenance_rejected(self):
        self.repair()
        path = self.destination / r.SOURCE_MANIFEST_PATH
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(m.ContractError, "manifest provenance hash mismatch"):
            m.validate_material(self.destination, self.key)

    def test_missing_or_changed_modification_notice_rejected(self):
        self.repair()
        path = self.destination / r.NOTICE_PATH
        path.write_bytes(b"unmodified official export")
        with self.assertRaisesRegex(m.ContractError, "modification notice"):
            m.validate_material(self.destination, self.key)
        path.unlink()
        with self.assertRaisesRegex(m.ContractError, "missing local"):
            m.validate_material(self.destination, self.key)

    def test_wrong_model_and_revision_and_repair_record_rejected(self):
        self.repair()
        with self.assertRaisesRegex(m.ContractError, "exact reviewed Granite revision"):
            m.validate_material(self.destination, "qwen3.5-9b")
        self.rewrite_manifest(lambda value: value.update(revision="main"))
        with self.assertRaisesRegex(m.ContractError, "identity and schema"):
            m.validate_material(self.destination, self.key)
        self.rewrite_manifest(lambda value: value.update(revision=r.REVISION))
        self.rewrite_manifest(lambda value: value["index_repair"].update(official_weights_unchanged=False))
        with self.assertRaisesRegex(m.ContractError, "provenance contract"):
            m.validate_material(self.destination, self.key)

    def test_source_wrong_revision_rejected_even_with_reanchored_manifest(self):
        self.patch(patch.dict(m.MODELS, {self.key: replace(self.spec, revision="b" * 40)}))
        with self.assertRaisesRegex(m.ContractError, "exact reviewed Granite revision"):
            self.repair()
        self.assertFalse(self.destination.exists())

    def test_exact_manifest_types_cannot_alias_boolean_or_integer(self):
        self.repair()
        self.rewrite_manifest(lambda value: value["index_repair"].update(official_weights_unchanged=1))
        with self.assertRaisesRegex(m.ContractError, "provenance contract"):
            m.validate_material(self.destination, self.key)
        self.rewrite_manifest(lambda value: value["index_repair"].update(official_weights_unchanged=True))
        self.rewrite_manifest(lambda value: value["files"][0].update(
            size_bytes=float(value["files"][0]["size_bytes"])))
        with self.assertRaisesRegex(m.ContractError, "preserve all original"):
            m.validate_material(self.destination, self.key)

    def test_missing_or_extra_tensor_names_rejected_after_synthetic_hash_verification(self):
        self.write_shard(self.shards[1], {"unexpected.weight": {"dtype": "BF16", "shape": [2, 2],
                                                              "data_offsets": [0, 8]}}, bytes(8))
        self.reseal_synthetic_source()
        with self.assertRaisesRegex(m.ContractError, "tensor names differ"):
            self.repair()
        self.assertFalse(self.destination.exists())

    def test_duplicate_tensor_across_shards_rejected_after_synthetic_hash_verification(self):
        self.write_shard(self.shards[1], {self.names[0]: {"dtype": "BF16", "shape": [2, 2],
                                                       "data_offsets": [0, 8]}}, bytes(8))
        self.reseal_synthetic_source()
        with self.assertRaisesRegex(m.ContractError, "duplicate tensor across shards"):
            self.repair()

    def test_payload_overlaps_rejected_after_synthetic_hash_verification(self):
        entry = {"dtype": "BF16", "shape": [2, 2], "data_offsets": [0, 8]}
        self.write_shard(self.shards[0], {self.names[0]: entry, "overlap": entry}, bytes(8))
        self.reseal_synthetic_source()
        with self.assertRaisesRegex(m.ContractError, "gaps or overlaps"):
            self.repair()

    def test_full_parameter_count_and_dtype_still_required(self):
        self.write_shard(self.shards[1], {self.names[1]: {"dtype": "F32", "shape": [2],
                                                       "data_offsets": [0, 8]}}, bytes(8))
        self.reseal_synthetic_source()
        with self.assertRaisesRegex(m.ContractError, "full reviewed tensor count"):
            self.repair()

    def test_duplicate_header_json_keys_rejected(self):
        tensor = b'{"dtype":"BF16","shape":[2,2],"data_offsets":[0,8]}'
        key = json.dumps(self.names[0]).encode()
        header = b"{" + key + b":" + tensor + b"," + key + b":" + tensor + b"}"
        (self.source / self.shards[0]).write_bytes(struct.pack("<Q", len(header)) + header + bytes(8))
        self.reseal_synthetic_source()
        with self.assertRaisesRegex(m.ContractError, "duplicate JSON key"):
            self.repair()

    def test_independently_reviewed_corrected_hash_still_required(self):
        with patch.object(r, "DERIVED_INDEX_SHA256", "0" * 64):
            with self.assertRaisesRegex(m.ContractError, "independently reviewed repair"):
                self.repair()
        self.assertFalse(self.destination.exists())

    def test_derived_files_cannot_be_symlinks(self):
        self.repair(copy_mode="copy")
        path = self.destination / self.shards[0]
        path.unlink()
        path.symlink_to(self.source / self.shards[0])
        with self.assertRaisesRegex(m.ContractError, "not symlinks"):
            m.validate_material(self.destination, self.key)

    def test_unlisted_alternative_weights_still_rejected(self):
        self.repair()
        (self.destination / "pytorch_model.bin").write_bytes(b"forbidden")
        with self.assertRaisesRegex(m.ContractError, "unlisted alternative"):
            m.validate_material(self.destination, self.key)

    def test_normal_architecture_and_tokenizer_checks_remain_active(self):
        path = self.source / "config.json"
        config = json.loads(path.read_bytes())
        config["auto_map"] = {"AutoModel": "remote.code"}
        m.write_json(path, config)
        self.reseal_synthetic_source()
        with self.assertRaisesRegex(m.ContractError, "native architecture without remote code"):
            self.repair()

    def test_normal_native_vocabulary_check_remains_active(self):
        path = self.source / "tokenizer.json"
        tokenizer = json.loads(path.read_bytes())
        tokenizer["model"]["vocab"]["one"] = 2
        m.write_json(path, tokenizer)
        self.reseal_synthetic_source()
        with self.assertRaisesRegex(m.ContractError, "tokenizer IDs must fit"):
            self.repair()


if __name__ == "__main__":
    unittest.main()

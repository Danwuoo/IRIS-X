"""Adversarial, correctly rehashed NVARC package and material checks."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from irisx.arc_nvarc_cli import fixture_e2e
from irisx.arc_nvarc_representation import (MODEL_REVISION, SYMBOLS,
    convert_qwen35_checkpoint, verify_model_material, verify_source_model_material)
from irisx.arc_nvarc_runtime import (OUTBOUND_KIND, RESULT_KIND,
    verify_outbound, verify_result)
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from irisx.transport import RESULT_LIMITS, TRIAL_LIMITS, verify_zip, write_zip


def inventory(root: Path, *, excluded: str) -> list[dict[str, object]]:
    return [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
             "bytes": path.stat().st_size}
            for path in sorted(root.iterdir()) if path.name != excluded]


class NvarcBoundaryTests(unittest.TestCase):
    def test_rehashed_outbound_rejects_test_truth_and_extra_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture_e2e(root / "fixture")
            binding, workload, _ = verify_outbound(root / "fixture" / "outbound.zip")
            for field, value in (("output", [[9]]), ("truth_digest", "sha256:secret")):
                bad_workload = deepcopy(workload)
                bad_workload["cases"][0]["test"][0][field] = value
                bad_binding = deepcopy(binding)
                bad_binding["workload_digest"] = digest_value(bad_workload)
                bad_binding["identity_digest"] = digest_value({key: item for key, item in
                                                               bad_binding.items() if key != "identity_digest"})
                path = root / f"bad-{field}.zip"
                write_zip(path, OUTBOUND_KIND, bad_binding["run_id"], {
                    "bindings/run.json": canonical_bytes(bad_binding, newline=True),
                    "cases/visible-tasks.json": canonical_bytes(bad_workload, newline=True)},
                    {"trial_id": bad_binding["trial_id"],
                     "identity_digest": bad_binding["identity_digest"], "truth_free": True},
                    limits=TRIAL_LIMITS)
                with self.assertRaises(ValidationError):
                    verify_outbound(path)

    def test_rehashed_result_requires_terminal_checkpoint_and_exact_counters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture_e2e(root / "fixture")
            binding, workload, _ = verify_outbound(root / "fixture" / "outbound.zip")
            _, original, _ = verify_zip(root / "fixture" / "result.zip", limits=RESULT_LIMITS,
                                        package_kind=RESULT_KIND)
            for label, mutation in (("incomplete", lambda c: c.update(complete=False)),
                                    ("counter", lambda c: c["counters"].update(generation_calls_observed=0)),
                                    ("missing", lambda c: c["completed"].pop(c["expected_tasks"][0]))):
                contents = dict(original)
                checkpoint = json.loads(contents["checkpoint/checkpoint.json"])
                mutation(checkpoint)
                contents["checkpoint/checkpoint.json"] = canonical_bytes(checkpoint, newline=True)
                path = root / f"bad-{label}.zip"
                write_zip(path, RESULT_KIND, binding["run_id"], contents,
                          {"trial_id": binding["trial_id"],
                           "identity_digest": binding["identity_digest"], "truth_free": True},
                          limits=RESULT_LIMITS)
                with self.assertRaises(ValidationError):
                    verify_result(path, binding, workload)

    def test_compact_material_requires_complete_closed_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = {"text_config": {"vocab_size": 16, "pad_token_id": 13,
                                      "eos_token_id": 15, "bos_token_id": 14},
                      "pad_token_id": 13, "eos_token_id": 15, "bos_token_id": 14}
            generation = {"pad_token_id": 13, "eos_token_id": 15, "bos_token_id": 14}
            vocabulary = {"format": "irisx/nvarc-compact-vocab", "vocab_size": 16,
                          "symbols": list(SYMBOLS)}
            vocabulary["identity_digest"] = digest_value(vocabulary)
            tokenizer = {"format": "irisx/nvarc-grid-tokenizer", "symbols": list(SYMBOLS),
                         "pad_token_id": 13, "eos_token_id": 15}
            for name, value in (("config.json", config), ("generation_config.json", generation),
                                ("grid-vocab.json", vocabulary), ("grid-tokenizer.json", tokenizer)):
                (root / name).write_bytes(canonical_bytes(value, newline=True))
            (root / "model.safetensors").write_bytes(b"synthetic tensor fixture")
            material = {"format": "irisx/nvarc-compact-model-material",
                        "tied_embeddings": True,
                        "vocabulary_identity_digest": vocabulary["identity_digest"],
                        "files": inventory(root, excluded="material-manifest.json")}
            manifest = root / "material-manifest.json"
            manifest.write_bytes(canonical_bytes(material, newline=True))
            verify_model_material(root, digest_value(material))
            for changed in (dict(material, files=[]),
                            dict(material, files=material["files"] + material["files"][:1])):
                manifest.write_bytes(canonical_bytes(changed, newline=True))
                with self.assertRaises(ValidationError):
                    verify_model_material(root, digest_value(changed))
            manifest.write_bytes(canonical_bytes(material, newline=True))
            (root / "unbound-config.json").write_text("{}")
            with self.assertRaises(ValidationError):
                verify_model_material(root, digest_value(material))

    def test_base_manifest_digest_is_verified_before_converter_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config.json").write_bytes(b"{\"model_type\":\"fixture\"}")
            (root / "tokenizer.json").write_bytes(b"{\"tokenizer\":\"fixture\"}")
            (root / "model.safetensors.index.json").write_bytes(canonical_bytes(
                {"weight_map": {"embedding": "model-00001.safetensors"}}, newline=True))
            (root / "model-00001.safetensors").write_bytes(b"synthetic shard")
            material = {"format": "irisx/nvarc-base-model-material", "revision": MODEL_REVISION,
                        "files": inventory(root, excluded="source-model-manifest.json")}
            (root / "source-model-manifest.json").write_bytes(canonical_bytes(material, newline=True))
            import irisx.arc_nvarc_representation as representation
            with mock.patch.object(representation, "BASE_CONFIG_SHA256",
                                   hashlib.sha256((root / "config.json").read_bytes()).hexdigest()), \
                 mock.patch.object(representation, "TOKENIZER_SHA256",
                                   hashlib.sha256((root / "tokenizer.json").read_bytes()).hexdigest()), \
                 mock.patch.object(representation, "BASE_INDEX_SHA256",
                                   hashlib.sha256((root / "model.safetensors.index.json").read_bytes()).hexdigest()):
                verify_source_model_material(root, digest_value(material), MODEL_REVISION)
                with self.assertRaises(ValidationError):
                    convert_qwen35_checkpoint(root, root / "derived",
                                              model_revision=MODEL_REVISION,
                                              model_manifest_digest=digest_value("caller claim"))
                (root / "model-00001.safetensors").write_bytes(b"changed shard")
                with self.assertRaises(ValidationError):
                    verify_source_model_material(root, digest_value(material), MODEL_REVISION)


if __name__ == "__main__":
    unittest.main()

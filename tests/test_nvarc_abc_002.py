"""Focused checks for the distinct compact ABC Editor material repair."""

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from irisx.arc_nvarc_abc_002 import BASE, SFT, TRAINING, VOCAB, check_materials
from irisx.arc_nvarc_representation import _verify_file_inventory
from irisx.errors import ValidationError
from tools.stage_nvarc_abc_002 import PLAN, make_plan, metadata, preflight, save_fields
from irisx.arc_nvarc_combined import read

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-002-submission"


class ABCRepairTests(unittest.TestCase):
    def test_publishing_sidecar_is_optional_but_unknown_members_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            body = b"signed model member\n"
            (root / "weight.bin").write_bytes(body)
            entry = {"path": "weight.bin", "bytes": len(body),
                     "sha256": hashlib.sha256(body).hexdigest()}
            for sidecar in (False, True):
                if sidecar:
                    (root / "dataset-metadata.json").write_text("{}", encoding="utf-8")
                self.assertEqual({"weight.bin"}, _verify_file_inventory(
                    root, [entry], None, allowed_extra_files={"dataset-metadata.json"}
                    if sidecar else None))
            (root / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                _verify_file_inventory(root, [entry], None,
                                       allowed_extra_files={"dataset-metadata.json"})

    def test_worker_sidecar_detection_and_exact_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base, sft = root / "base", root / "sft"
            base.mkdir()
            sft.mkdir()
            for name in ("grid-vocab.json", "grid-tokenizer.json", "generation_config.json"):
                (base / name).write_text(name, encoding="utf-8")
                (sft / name).write_text(name, encoding="utf-8")
            a = {"vocabulary_identity_digest": VOCAB, "tied_embeddings": True}
            b = {**a, "kind": "sft-inference-export", "base_material_digest": BASE,
                 "training_identity_digest": TRAINING}
            with patch("irisx.arc_nvarc_abc_002.verify_model_material", side_effect=[a, b]) as verify:
                check_materials(base, sft)
                self.assertEqual(None, verify.call_args_list[0].kwargs["allowed_extra_files"])
                self.assertEqual(None, verify.call_args_list[1].kwargs["allowed_extra_files"])
            (base / "dataset-metadata.json").write_text("{}", encoding="utf-8")
            with patch("irisx.arc_nvarc_abc_002.verify_model_material", side_effect=[a, b]) as verify:
                check_materials(base, sft)
                self.assertEqual({"dataset-metadata.json"},
                                 verify.call_args_list[0].kwargs["allowed_extra_files"])
                self.assertEqual(None, verify.call_args_list[1].kwargs["allowed_extra_files"])

        plan = read(PLAN)
        self.assertEqual(make_plan(), plan)
        self.assertEqual("nvarc-compact-abc-editor-002", plan["run_id"])
        self.assertEqual("four-distinct-bf16-l4-verified/one-active-worker-v1",
                         plan["hardware_profile"])
        self.assertEqual(["arc-prize-2026-arc-agi-2"], metadata(plan)["competition_sources"])
        self.assertEqual("QUICK_SAVE", save_fields(PACKAGE)["kernel_execution_type"])
        self.assertTrue(preflight(PACKAGE)["wheel_matches_source"])


if __name__ == "__main__":
    unittest.main()

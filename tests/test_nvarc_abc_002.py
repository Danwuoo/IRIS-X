"""Focused checks for the distinct compact ABC Editor material repair."""

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from irisx.arc_nvarc_abc_002 import BASE, SFT, TRAINING, VOCAB, check_materials
from irisx.arc_nvarc_analysis_zip_abc import write_abc_zip
from irisx.arc_nvarc_representation import _verify_file_inventory
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.analyze_nvarc_abc import inspect
from tools.stage_nvarc_abc_002 import PLAN, RUN, make_plan, metadata, preflight, save_fields
from irisx.arc_nvarc_combined import read

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-002-submission"


class ABCRepairTests(unittest.TestCase):
    def test_002_analysis_uses_explicit_bound_plan_without_truth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / RUN
            work.mkdir()
            (work / "aggregate-terminal.json").write_text('{"outcome":"complete"}', encoding="utf-8")
            result = root / "result.zip"
            write_abc_zip(work, result, RUN, digest_value(read(PLAN)))
            report = inspect(result, plan_path=PLAN)
            self.assertEqual(RUN, report["run_id"])
            self.assertEqual("unknown-no-isolated-truth", report["scoring"])

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

    def test_worker_sidecar_detection(self):
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

    def test_tracked_plan_contract(self):
        plan = read(PLAN)
        self.assertEqual("nvarc-compact-abc-editor-002", plan["run_id"])
        self.assertEqual("four-distinct-bf16-l4-verified/one-active-worker-v1",
                         plan["hardware_profile"])
        self.assertEqual(["arc-prize-2026-arc-agi-2"], metadata(plan)["competition_sources"])

    def test_retained_plan_and_save_projection(self):
        self.assertEqual(make_plan(), read(PLAN))
        self.assertEqual("QUICK_SAVE", save_fields(PACKAGE, retained_review=True)["kernel_execution_type"])
        self.assertTrue(preflight(PACKAGE, retained_review=True)["retained_wheel_verified"])


if __name__ == "__main__":
    unittest.main()

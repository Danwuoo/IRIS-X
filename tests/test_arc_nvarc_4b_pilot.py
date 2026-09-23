"""The 4B pilot package stays private and fails closed until authorized."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

from irisx.arc_nvarc_4b_pilot import validate_plan
from irisx.errors import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_nvarc_4b_pilot import PLAN, stage  # noqa: E402


class FourBPilotTests(unittest.TestCase):
    def test_draft_cannot_enter_model_work(self) -> None:
        old = os.environ.get("HF_HUB_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            with self.assertRaisesRegex(ValidationError, "authority"):
                validate_plan(json.loads(PLAN.read_bytes()))
        finally:
            if old is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = old

    def test_local_stage_has_exact_private_offline_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            summary = stage(Path(temp) / "stage")
            kernel = Path(summary["local_kernel_path"])
            metadata = json.loads((kernel / "kernel-metadata.json").read_bytes())
            code = "".join(json.loads((kernel / "kaggle-notebook.ipynb").read_bytes())
                           ["cells"][0]["source"])
            self.assertFalse(summary["approved"])
            self.assertTrue(metadata["is_private"])
            self.assertFalse(metadata["enable_internet"])
            self.assertEqual(metadata["competition_sources"], [])
            self.assertEqual(metadata["dataset_sources"],
                             ["danielwuu/irisx-arc-agi-2-trial-002-smoke-001"])
            self.assertTrue(metadata["id"].startswith("DRAFT-DO-NOT-PUSH/"))
            self.assertIn('plan.get("approved") is not True', code)
            self.assertIn('"--no-index"', code)
            self.assertIn('timeout=1500', code)

    def test_fake_authorization_cannot_change_plan_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth = root / "authorization.json"
            auth.write_text(json.dumps({"approved": True, "draft_plan_sha256": "wrong",
                                        "run_id": "nvarc-4b-compat-pilot-001",
                                        "kernel_id": "danielwuu/irisx-nvarc-4b-compat-pilot-001",
                                        "owner_decision": "fixture"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "authorization"):
                stage(root / "stage", authorization_path=auth)

    def test_bound_local_package_builder_uses_final_private_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth = root / "fixture-authorization.json"
            auth.write_text(json.dumps({
                "approved": True,
                "draft_plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
                "run_id": "nvarc-4b-compat-pilot-001",
                "kernel_id": "danielwuu/irisx-nvarc-4b-compat-pilot-001",
                "owner_decision": "fixture-only; no provider work"
            }), encoding="utf-8")
            summary = stage(root / "stage", authorization_path=auth)
            metadata = json.loads((Path(summary["local_kernel_path"]) /
                                   "kernel-metadata.json").read_bytes())
            self.assertTrue(summary["approved"])
            self.assertEqual(metadata["id"],
                             "danielwuu/irisx-nvarc-4b-compat-pilot-001")
            self.assertTrue(metadata["is_private"])
            self.assertFalse(metadata["enable_internet"])


if __name__ == "__main__":
    unittest.main()

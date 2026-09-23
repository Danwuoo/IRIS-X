"""The optional GPU package must remain a local, unapproved draft."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from irisx.arc_nvarc_gpu_smoke import run
from irisx.errors import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_nvarc_gpu_compat import CONFIG, stage  # noqa: E402


class GpuDraftTests(unittest.TestCase):
    def test_draft_refuses_execution_before_importing_gpu_packages(self) -> None:
        manifest = json.loads(CONFIG.read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            with self.assertRaisesRegex(ValidationError, "authority"):
                run(manifest, output)
            self.assertFalse(output.exists())

    def test_local_stage_is_private_offline_truth_free_and_digest_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            summary = stage(root)
            kernel = root / "kernel"
            metadata = json.loads((kernel / "kernel-metadata.json").read_bytes())
            notebook = json.loads((kernel / "kaggle-notebook.ipynb").read_bytes())
            code = "".join(notebook["cells"][0]["source"])
            self.assertFalse(summary["approved"])
            self.assertTrue(metadata["is_private"])
            self.assertFalse(metadata["enable_internet"])
            self.assertEqual(metadata["competition_sources"], [])
            self.assertEqual(metadata["dataset_sources"], [])
            self.assertIn('manifest.get("approved") is not True', code)
            self.assertIn('"--no-index"', code)
            self.assertIn('timeout=1500', code)
            self.assertEqual(
                summary["wheel_sha256"],
                hashlib.sha256((root / "wheel/irisx-0.2.0-py3-none-any.whl").read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()

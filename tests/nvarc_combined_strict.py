"""Cached material/package checks; missing prerequisites fail explicitly."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from irisx.arc_nvarc_combined import atomic, read, sha
from irisx.errors import ValidationError
from tools.stage_nvarc_combined import DRAFT, stage, verify_inputs
from tools.preflight_nvarc_combined import preflight

ROOT = Path(__file__).resolve().parents[1]


class CombinedPackageStrictLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / ".irisx", prefix="combined-package-")
        cls.package = Path(cls.temp.name) / "package"
        cls.summary = stage(cls.package)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_exact_package_guard_and_deterministic_rebuild(self):
        report = preflight(self.package)
        self.assertTrue(report["draft_guard_verified"])
        other = Path(self.temp.name) / "second"
        self.assertEqual(self.summary, stage(other))
        self.assertEqual(0, report["external_calls"])
        self.assertFalse((self.package / "model-dataset").exists())

    def test_rehashed_extra_file_is_not_an_accepted_inventory(self):
        package = Path(self.temp.name) / "extra"
        shutil.copytree(self.package, package)
        (package / "unexpected.json").write_text("{}")
        summary = read(package / "stage-summary.json")
        summary["inventory"]["unexpected.json"] = sha(package / "unexpected.json")
        atomic(package / "stage-summary.json", summary)
        with self.assertRaisesRegex(ValidationError, "expected review inventory"):
            preflight(package)

    def test_changed_manifest_file_inventory_cannot_keep_old_digest(self):
        payloads = {key: (self.package / filename).read_bytes() for key, filename in
                    (("source_config", "source-config.json"), ("visible", "visible.json"),
                     ("training_evidence", "training-evidence.json"), ("seed", "seed.json"),
                     ("prompts", "prompts.json"), ("model_manifest", "model-manifest.json"),
                     ("wheel_manifest", "wheel-manifest.json"))}
        manifest = json.loads(payloads["model_manifest"])
        manifest["files"][0]["content_digest"] = "sha256:" + "0" * 64
        payloads["model_manifest"] = json.dumps(manifest).encode()
        with self.assertRaisesRegex(ValidationError, "manifest content"):
            verify_inputs(read(DRAFT), payloads)

"""Cached material/package checks; missing prerequisites fail explicitly."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
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
        cls.approved = Path(cls.temp.name) / "approved"
        cls.approved_summary = stage(cls.approved, approved=True)

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

    def test_exact_approved_package_preserves_draft_and_changes_only_envelope(self):
        report = preflight(self.approved, approved=True)
        self.assertTrue(report["approved_guard_verified"])
        self.assertEqual(read(self.package / "plan.json")["branches"],
                         read(self.approved / "plan.json")["branches"])
        for name, digest in self.summary["inventory"].items():
            if name not in {"plan.json", "kernel/kaggle-notebook.ipynb", "kernel/kernel-metadata.json"}:
                self.assertEqual(digest, self.approved_summary["inventory"][name])
        with self.assertRaises(ValidationError):
            preflight(self.approved)
        with self.assertRaises(ValidationError):
            preflight(self.package, approved=True)

    def test_actual_wheel_parent_and_worker_guards_accept_only_exact_envelope(self):
        wheel = next((self.approved / "wheel").glob("*.whl"))
        probe = Path(self.temp.name) / "installed-guards.py"
        probe.write_text('''import sys, json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from irisx import arc_nvarc_combined as parent, arc_nvarc_combined_worker as worker
plan = Path(sys.argv[2])
parent.require_live_authorization(parent.read(plan))
with patch.object(sys, "argv", ["parent", "--plan", str(plan)]):
    parent.main()
inputs = plan.parent / "paths-fixture.json"
inputs.write_text("{}")
with patch.object(worker, "_run_prepared") as workload, patch.object(sys, "argv",
    ["worker", "--plan", str(plan), "--branch", "m2", "--paths", str(inputs),
     "--hardware", str(inputs), "--output", str(plan.parent / "output-fixture")]):
    worker.main()
    assert workload.call_count == 1
for decision in ("Decision 0033", "Decision 0034"):
    altered = parent.read(plan); altered["owner_decision"] = decision
    try: parent.require_live_authorization(altered)
    except Exception: pass
    else: raise AssertionError("old decision activated installed runtime")
print("installed parent/worker exact guards verified; zero workload calls")
''', encoding="utf-8")
        # Keep fixture inputs outside the immutable review package.
        fixture = Path(self.temp.name) / "approved-plan-fixture.json"
        shutil.copyfile(self.approved / "plan.json", fixture)
        result = subprocess.run([sys.executable, "-I", str(probe), str(wheel), str(fixture)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("zero workload calls", result.stdout)

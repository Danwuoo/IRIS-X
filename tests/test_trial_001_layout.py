from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "irisx_trial_001_layout", ROOT / "tools/trial_001_layout.py"
)
assert SPEC is not None and SPEC.loader is not None
LAYOUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAYOUT)


def digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class Trial001LayoutAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name)
        self.trial_root = self.repository / ".irisx/arc-agi-2/trial-001"
        self.outbound = self.trial_root / "kaggle/outbound/run-001/trial-input.zip"
        self.outbound.parent.mkdir(parents=True)
        notebook = b'{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}\n'
        notebook_path = self.repository / "trials/first-real-domain/kaggle-notebook.ipynb"
        notebook_path.parent.mkdir(parents=True)
        notebook_path.write_bytes(notebook)
        self.notebook_digest = digest(notebook)
        self.runner_digest = digest(b"runner")
        self.revision = "a" * 40
        manifest = {
            "format": "irisx/closed-world-zip",
            "format_version": "1.0",
            "package_kind": "irisx/arc-agi-2-trial-input",
            "package_id": "run-001",
            "files": [{"path": "payload.txt", "byte_size": 1, "content_digest": digest(b"x")}],
            "metadata": {
                "repository": {"revision": self.revision},
                "notebook_digest": self.notebook_digest,
                "runner_digest": self.runner_digest,
            },
        }
        self.manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with zipfile.ZipFile(self.outbound, "w") as archive:
            archive.writestr("manifest.json", self.manifest_bytes)
            archive.writestr("payload.txt", b"x")
        self.expected = {
            "trial_zip_digest": LAYOUT._digest_path(self.outbound),
            "trial_manifest_digest": digest(self.manifest_bytes),
            "notebook_digest": self.notebook_digest,
            "runner_digest": self.runner_digest,
            "repository_revision": self.revision,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_audit_freezes_layout_until_result_closure(self) -> None:
        with mock.patch.dict(LAYOUT.EXPECTED, self.expected, clear=True):
            report = LAYOUT.audit_layout(self.repository, self.trial_root)
        self.assertEqual(report["status"], "frozen-awaiting-result-closure")
        self.assertFalse(report["normalization_ready"])
        self.assertTrue(any("quarantine" in item for item in report["blockers"]))

    def test_audit_allows_normalization_only_after_import_and_evaluation(self) -> None:
        result = self.trial_root / "kaggle/inbound/quarantine/run-001/result-package.zip"
        result.parent.mkdir(parents=True)
        result.write_bytes(b"returned")
        run = self.trial_root / "runs/run-001"
        run.mkdir(parents=True)
        (run / "import-evidence.json").write_text("{}\n", encoding="utf-8")
        evaluation = run / "local-evaluation"
        evaluation.mkdir()
        for name in (
            "baseline-result.json",
            "candidate-result.json",
            "selection.json",
            "p2-acceptance.json",
        ):
            (evaluation / name).write_text("{}\n", encoding="utf-8")
        with mock.patch.dict(LAYOUT.EXPECTED, self.expected, clear=True):
            report = LAYOUT.audit_layout(self.repository, self.trial_root)
        self.assertEqual(report["status"], "ready-to-normalize")
        self.assertTrue(report["normalization_ready"])
        self.assertEqual(report["blockers"], [])


if __name__ == "__main__":
    unittest.main()

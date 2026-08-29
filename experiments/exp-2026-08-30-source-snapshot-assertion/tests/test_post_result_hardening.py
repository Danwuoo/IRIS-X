"""Targeted checks for the supported H-M1a startup hardening."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_snapshot_assertion import SourceSnapshotAssertionError  # noqa: E402
from tools.source_snapshot_assertion import assert_registered_source_snapshot  # noqa: E402


REGISTRY = ROOT / "corpus" / "sources.yaml"
BASELINE_RUNNER = ROOT / "experiments" / "exp-2026-08-28-docops-readonly-baseline" / "scripts" / "run_baseline.py"
BASELINE_MANIFEST = ROOT / "experiments" / "exp-2026-08-28-docops-readonly-baseline" / "inputs" / "task-manifest.json"
BASELINE_CONFIGS = ROOT / "experiments" / "exp-2026-08-28-docops-readonly-baseline" / "inputs" / "configurations.json"


class SourceSnapshotAssertionTests(unittest.TestCase):
    def test_valid_registered_vanta_identity_passes(self) -> None:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
        ).stdout.strip()
        identity = assert_registered_source_snapshot(
            ROOT, REGISTRY, "src.vanta", "snap.src.vanta.initial-import", commit
        )
        self.assertEqual(identity.registered_tree_oid, identity.observed_tree_oid)
        self.assertEqual(identity.source_path, "sources/predecessors/vanta")

    def test_unknown_snapshot_fails_closed(self) -> None:
        with self.assertRaisesRegex(SourceSnapshotAssertionError, "not registered") as caught:
            assert_registered_source_snapshot(ROOT, REGISTRY, "src.vanta", "snap.src.vanta.unknown", "HEAD")
        self.assertEqual(caught.exception.code, "unknown_snapshot_id")

    def test_tree_mismatch_fails_closed(self) -> None:
        with patch("tools.source_snapshot_assertion.git_tree_oid", return_value="f" * 40):
            with self.assertRaises(SourceSnapshotAssertionError) as caught:
                assert_registered_source_snapshot(
                    ROOT, REGISTRY, "src.vanta", "snap.src.vanta.initial-import", "HEAD"
                )
        self.assertEqual(caught.exception.code, "tree_oid_mismatch")

    def test_baseline_validate_only_rejects_mismatched_manifest_snapshot(self) -> None:
        manifest = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
        manifest["source_snapshot_id"] = "snap.src.vanta.not-registered"
        temp_parent = ROOT / "experiments" / "exp-2026-08-30-source-snapshot-assertion" / "tests"
        with tempfile.TemporaryDirectory(dir=temp_parent) as directory:
            manifest_path = Path(directory) / "mismatched-manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(BASELINE_RUNNER),
                    "--manifest",
                    manifest_path.relative_to(ROOT).as_posix(),
                    "--configurations",
                    BASELINE_CONFIGS.relative_to(ROOT).as_posix(),
                    "--validate-only",
                ],
                cwd=ROOT,
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("source snapshot assertion failed [unknown_snapshot_id]", completed.stderr)


if __name__ == "__main__":
    unittest.main()

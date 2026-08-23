"""Regression tests for the Stage 0 ARC-AGI-1 substrate contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from arc_a1_substrate import build_manifest, validate_manifest, write_manifest  # noqa: E402


class ArcA1SubstrateTests(unittest.TestCase):
    def create_fixture(self, temporary_directory: Path) -> tuple[Path, Path, Path, Path]:
        project_root = temporary_directory / "project"
        dataset_root = project_root / "data" / "arc-datasets" / "ARC-AGI-1"
        training = dataset_root / "data" / "training"
        evaluation = dataset_root / "data" / "evaluation"
        training.mkdir(parents=True)
        evaluation.mkdir(parents=True)
        (training / "task-a.json").write_text(json.dumps({"train": [], "test": []}), encoding="utf-8")
        (evaluation / "task-b.json").write_text(json.dumps({"train": [], "test": []}), encoding="utf-8")

        rules_path = project_root / "artifacts" / "arc-agi-1" / "rules.json"
        rules_path.parent.mkdir(parents=True)
        rules_path.write_text(json.dumps({"snapshot": "test"}), encoding="utf-8")

        self.git(dataset_root, "init")
        self.git(dataset_root, "add", ".")
        self.git(dataset_root, "-c", "user.email=test@example.invalid", "-c", "user.name=Stage 0 Test", "commit", "-m", "fixture")
        self.git(dataset_root, "remote", "add", "origin", "https://example.invalid/ARC-AGI.git")

        manifest_path = project_root / "artifacts" / "arc-agi-1" / "manifest.json"
        write_manifest(manifest_path, build_manifest(dataset_root, project_root, rules_path))
        return project_root, dataset_root, rules_path, manifest_path

    def git(self, directory: Path, *arguments: str) -> None:
        subprocess.run(["git", *arguments], cwd=directory, check=True, capture_output=True, text=True)

    def test_regeneration_is_deterministic_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project_root, dataset_root, rules_path, manifest_path = self.create_fixture(Path(temporary))
            first = build_manifest(dataset_root, project_root, rules_path)
            second = build_manifest(dataset_root, project_root, rules_path)

            self.assertEqual(first, second)
            self.assertTrue(validate_manifest(manifest_path, dataset_root, project_root)["valid"])

    def test_changed_task_files_fail_validation(self) -> None:
        cases = {
            "modified": lambda root: (root / "data" / "training" / "task-a.json").write_text("{}", encoding="utf-8"),
            "extra": lambda root: (root / "data" / "evaluation" / "task-extra.json").write_text("{}", encoding="utf-8"),
            "missing": lambda root: (root / "data" / "training" / "task-a.json").unlink(),
            "renamed": lambda root: (root / "data" / "evaluation" / "task-b.json").rename(root / "data" / "evaluation" / "task-renamed.json"),
        }
        expected_codes = {
            "modified": {"modified_task_file"},
            "extra": {"unexpected_task_file"},
            "missing": {"missing_task_file"},
            "renamed": {"missing_task_file", "unexpected_task_file"},
        }

        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                project_root, dataset_root, _rules_path, manifest_path = self.create_fixture(Path(temporary))
                mutate(dataset_root)
                result = validate_manifest(manifest_path, dataset_root, project_root)
                failure_codes = {failure["code"] for failure in result["failures"]}

                self.assertFalse(result["valid"])
                self.assertTrue(expected_codes[name].issubset(failure_codes))

    def test_rules_and_nested_task_files_fail_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project_root, dataset_root, rules_path, manifest_path = self.create_fixture(Path(temporary))
            rules_path.write_text(json.dumps({"snapshot": "changed"}), encoding="utf-8")
            nested = dataset_root / "data" / "training" / "unexpected" / "nested.json"
            nested.parent.mkdir()
            nested.write_text("{}", encoding="utf-8")

            result = validate_manifest(manifest_path, dataset_root, project_root)
            failure_codes = {failure["code"] for failure in result["failures"]}

            self.assertFalse(result["valid"])
            self.assertIn("rules_snapshot_mismatch", failure_codes)
            self.assertIn("unexpected_nested_task_file", failure_codes)


if __name__ == "__main__":
    unittest.main()

"""Constant-only synthetic Git sources; no model/training/legacy test bodies."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "tools/suite_runner.py").is_file() and (p / "pyproject.toml").is_file())
sys.path.insert(0, str(ROOT))
from tools import source_identity as identity
from tools import suite_runner as runner


class SourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="irisx-constant-source-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repository"
        self.root.mkdir()
        self.attempt = 0
        (self.root / "tests").mkdir()
        (self.root / "src").mkdir()
        (self.root / "tools").mkdir()
        for name in ("suite_runner.py", "source_identity.py", "workstream_management.py"):
            shutil.copyfile(ROOT / "tools" / name, self.root / "tools" / name)
        self.write(".gitignore", ".irisx/\n__pycache__/\n")
        self.write("tests/test_constant.py", "import unittest\nclass Constant(unittest.TestCase):\n    def test_value(self): self.assertEqual(4, 4)\n")
        entry = {"path": "tests/test_constant.py", "workstream": "core", "dependency_class": "stdlib", "suite": "core", "role": "test", "dependencies": [], "collector": "unittest", "reason": "constant-only fixture", "expected_skips": []}
        self.write("tests/inventory.json", json.dumps({"format": "irisx.tests.v1", "suites": {"core": {"public": True}}, "entries": [entry]}))
        self.git("init")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.commit()

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8", newline="\n")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE).decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-m", "constant-only fixture")
        self.commit_sha = self.git("rev-parse", "HEAD")

    def run_fixture(self, *, require_committed=False):
        self.attempt += 1
        return runner.run_suite(self.root, "core", self.root / f".irisx/output-{self.attempt}", require_committed=require_committed)

    def test_clean_committed_snapshot_binds_source_inventory_and_runner(self):
        report = self.run_fixture(require_committed=True)
        self.assertEqual(report["status"], "passed", report)
        self.assertTrue(report["attestable"])
        self.assertEqual(report["evidence_kind"], "commit")
        self.assertEqual(report["target_commit"], self.commit_sha)
        self.assertEqual(report["head_commit"], self.commit_sha)
        self.assertEqual(report["inventory_blob"], self.git("rev-parse", "HEAD:tests/inventory.json"))
        self.assertEqual(report["runner_blob"], self.git("rev-parse", "HEAD:tools/suite_runner.py"))
        self.assertEqual(report["source_identity"]["tree"], self.git("rev-parse", "HEAD^{tree}"))
        self.assertEqual(report["source_identity"]["manifest_sha256"], identity.manifest_digest(identity.git_manifest(self.root, self.commit_sha)))
        self.assertNotEqual(report["execution_root"], str(self.root))
        for child in report["modules"]:
            for field in ("attestable", "evidence_kind", "target_commit", "inventory_blob", "runner_blob", "source_identity"):
                self.assertEqual(child[field], report[field])

    def test_unstaged_pass_never_attests_the_committed_failing_test(self):
        self.write("tests/test_constant.py", "import unittest\nclass Constant(unittest.TestCase):\n    def test_value(self): self.assertEqual(4, 5)\n")
        self.commit()
        original = self.run_fixture(require_committed=True)
        self.assertEqual(original["status"], "failed")
        self.assertEqual(original["failures"], 1)
        self.write("tests/test_constant.py", "import unittest\nclass Constant(unittest.TestCase):\n    def test_value(self): self.assertEqual(4, 4)\n")
        changed = self.run_fixture()
        self.assertEqual(changed["status"], "passed", changed)
        self.assertFalse(changed["attestable"])
        self.assertEqual(changed["evidence_kind"], "development")
        self.assertIsNone(changed["target_commit"])
        self.assertEqual(changed["head_commit"], self.commit_sha)

    def test_staged_change_is_development_and_strict_mode_imports_nothing(self):
        self.write("tests/test_constant.py", "import unittest\nclass Constant(unittest.TestCase):\n    def test_value(self): self.assertEqual(7, 7)\n")
        self.git("add", "tests/test_constant.py")
        report = self.run_fixture()
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["attestable"])
        self.assertIsNone(report["target_commit"])
        strict = self.run_fixture(require_committed=True)
        self.assertEqual(strict["status"], "failed")
        self.assertEqual(strict["tests"], 0)
        self.assertIn("clean Git checkout", strict["reason"])

    def test_untracked_source_input_is_isolated_but_non_attestable(self):
        self.write("tests/test_constant.py", "import unittest\nimport sample_input\nclass Constant(unittest.TestCase):\n    def test_value(self): self.assertEqual(sample_input.VALUE, 9)\n")
        self.commit()
        self.write("src/sample_input.py", "VALUE = 9\n")
        report = self.run_fixture()
        self.assertEqual(report["status"], "passed", report)
        self.assertFalse(report["attestable"])
        self.assertIsNone(report["target_commit"])

    def test_ignored_output_does_not_invalidate_clean_source(self):
        self.write(".irisx/previous-output.json", '{"synthetic": true}')
        report = self.run_fixture(require_committed=True)
        self.assertEqual(report["status"], "passed", report)
        self.assertTrue(report["attestable"])
        self.assertFalse((Path(report["execution_root"]) / ".irisx/previous-output.json").exists())

    def test_caller_change_during_child_is_detected(self):
        original_run = subprocess.run
        def mutate(command, *args, **kwargs):
            result = original_run(command, *args, **kwargs)
            if "--child" in command:
                self.write("src/changed_input.py", "VALUE = 'new constant'\n")
            return result
        with mock.patch.object(runner.subprocess, "run", side_effect=mutate):
            report = self.run_fixture(require_committed=True)
        self.assertEqual(report["status"], "failed", report)
        self.assertFalse(report["attestable"])
        self.assertIsNone(report["target_commit"])
        self.assertTrue(report["source_changes"])

    def test_change_and_revert_in_caller_cannot_change_executed_snapshot(self):
        original_run = subprocess.run
        target = self.root / "tests/test_constant.py"
        original = target.read_bytes()
        def mutate(command, *args, **kwargs):
            if "--child" not in command:
                return original_run(command, *args, **kwargs)
            target.write_bytes(b"raise AssertionError('CALLER BYTES MUST NOT EXECUTE')\n")
            try:
                return original_run(command, *args, **kwargs)
            finally:
                target.write_bytes(original)
        with mock.patch.object(runner.subprocess, "run", side_effect=mutate):
            report = self.run_fixture(require_committed=True)
        self.assertEqual(report["status"], "passed", report)
        self.assertTrue(report["attestable"])
        self.assertEqual(report["target_commit"], self.commit_sha)

    def test_snapshot_change_after_child_invalidates_evidence(self):
        original_run = subprocess.run
        def mutate(command, *args, **kwargs):
            result = original_run(command, *args, **kwargs)
            if "--child" in command:
                snapshot = Path(command[command.index("--root") + 1])
                (snapshot / "tests/test_constant.py").write_bytes(b"# changed snapshot source\n")
            return result
        with mock.patch.object(runner.subprocess, "run", side_effect=mutate):
            report = self.run_fixture(require_committed=True)
        self.assertEqual(report["status"], "failed", report)
        self.assertFalse(report["attestable"])
        self.assertIn("executed source snapshot changed", report["source_changes"])

    def test_independent_manifest_algorithm_uses_only_git_metadata(self):
        entries = identity.git_manifest(self.root, self.commit_sha)
        canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.assertEqual(identity.manifest_digest(entries), hashlib.sha256(canonical).hexdigest())

    def test_unsafe_case_colliding_and_link_modes_are_denied(self):
        ordinary = {"path": "src/a.py", "mode": "100644", "blob": "1" * 40}
        for entry in ({**ordinary, "path": "../escape.py"}, {**ordinary, "mode": "120000"}, {**ordinary, "mode": "160000"}):
            with self.subTest(entry=entry), self.assertRaises(identity.SourceIdentityError):
                identity.validate_manifest([entry])
        for path in (".git", ".GIT", ".git/config", ".GiT/config", ".irisx", ".IRISX", ".irisx/report.json", ".IrIsX/report.json"):
            with self.subTest(reserved_path=path), self.assertRaisesRegex(identity.SourceIdentityError, "Git/output directories"):
                identity.validate_manifest([{**ordinary, "path": path}])
        with self.assertRaisesRegex(identity.SourceIdentityError, "collision"):
            identity.validate_manifest([ordinary, {**ordinary, "path": "src/A.py"}])
        with self.assertRaisesRegex(identity.SourceIdentityError, "parent path/case collision"):
            identity.validate_manifest([{**ordinary, "path": "src/Package/a.py"}, {**ordinary, "path": "src/package/b.py"}])

    def test_working_source_junction_is_rejected_before_copy(self):
        with mock.patch.object(Path, "is_junction", lambda p: p.name == "test_constant.py", create=True):
            with self.assertRaisesRegex(identity.SourceIdentityError, "linked"):
                identity.create_snapshot(self.root, self.root / ".irisx/denied-source")


if __name__ == "__main__":
    unittest.main()

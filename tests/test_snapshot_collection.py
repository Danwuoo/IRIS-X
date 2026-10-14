"""Constant packages reproduce tool-root and package-name collection behavior."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file() and (p / "tools").is_dir())
sys.path.insert(0, str(ROOT))
from tools import suite_runner as runner
from tools import no_training


class SnapshotCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="irisx-constant-package-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repository"
        self.root.mkdir()
        (self.root / "tests").mkdir()
        self.entries = []
        self.attempt = 0

    def package(self, snapshot, value, metadata=True):
        source = f"tools/{snapshot}/source"
        for path, text in (("experiment_flow/__init__.py", ""), ("experiment_flow/_constants.py", f"VALUE = {value!r}\n"),
                           ("experiment_flow/tests/__init__.py", ""),
                           ("experiment_flow/tests/test_constant.py", "import unittest\nfrom .._constants import VALUE\nclass Constant(unittest.TestCase):\n    def test_value(self): self.assertEqual(VALUE, " + repr(value) + ")\n")):
            target = self.root / source / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        entry = {"path": f"{source}/experiment_flow/tests/test_constant.py", "workstream": "arc-agi-2", "dependency_class": "stdlib",
                 "suite": "constants", "role": "test", "dependencies": [], "collector": "unittest", "reason": "constant-only synthetic snapshot", "expected_skips": []}
        if metadata:
            entry.update(import_roots=[source], module_name="experiment_flow.tests.test_constant")
        self.entries.append(entry)
        return entry

    def data(self):
        return {"format": "irisx.tests.v1", "suites": {"constants": {"public": False}}, "entries": self.entries}

    def run_fixture(self):
        (self.root / "tests/inventory.json").write_text(json.dumps(self.data()), encoding="utf-8")
        self.attempt += 1
        return runner.run_suite(self.root, "constants", self.root / f".irisx/output-{self.attempt}")

    def test_missing_owner_root_reproduces_collection_failure_then_metadata_passes(self):
        entry = self.package("first", "FIRST", metadata=False)
        missing = self.run_fixture()
        self.assertEqual(missing["status"], "failed")
        self.assertEqual(missing["modules"][0]["collection_errors"], 1)
        entry.update(import_roots=["tools/first/source"], module_name="experiment_flow.tests.test_constant")
        fixed = self.run_fixture()
        self.assertEqual(fixed["status"], "passed", fixed)
        self.assertEqual(fixed["tests"], 1)
        self.assertFalse(fixed["attestable"])
        self.assertIsNone(fixed["target_commit"])

    def test_identical_package_names_in_distinct_snapshots_use_fresh_processes(self):
        self.package("first", "FIRST")
        self.package("second", "SECOND")
        report = self.run_fixture()
        self.assertEqual(report["status"], "passed", report)
        self.assertEqual(report["tests"], 2)
        self.assertEqual(len(report["commands"]), 2)
        self.assertTrue(all(all(flag in command for flag in ("-P", "-s", "-B"))
                            and "-I" not in command and "-E" not in command
                            for command in report["commands"]))
        self.assertNotEqual(report["modules"][0]["path"], report["modules"][1]["path"])

    def test_global_pythonpath_does_not_replace_owner_constants(self):
        self.package("first", "FIRST")
        poison = Path(self.temp.name) / "poison/experiment_flow"
        poison.mkdir(parents=True)
        (poison / "__init__.py").write_text("raise AssertionError('GLOBAL PACKAGE MUST NOT IMPORT')", encoding="utf-8")
        with mock.patch.dict(os.environ, {"PYTHONPATH": str(poison.parent)}):
            report = self.run_fixture()
        self.assertEqual(report["status"], "passed", report)

    def test_escaping_foreign_global_and_duplicate_roots_are_rejected(self):
        entry = self.package("first", "FIRST")
        self.package("second", "SECOND")
        for roots in (["../outside"], ["tools/second/source"], ["tools"], ["tools/first/source", "tools/first/source"]):
            changed = copy.deepcopy(entry)
            changed["import_roots"] = roots
            with self.subTest(roots=roots), self.assertRaises(ValueError):
                runner.validate_entry_imports(self.root, changed)

    def test_wrong_module_name_is_rejected_before_import(self):
        entry = self.package("first", "FIRST")
        for name in ("experiment_flow.bad", "../evil", "experiment_flow.tests.test_constant;bad", "experiment_flow.class"):
            changed = dict(entry, module_name=name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                runner.validate_entry_imports(self.root, changed)

    def test_existing_external_package_collision_is_rejected_before_test_body(self):
        entry = self.package("first", "FIRST")
        source = self.root / "tools/first/source"
        (source / "experiment_flow").rename(source / "unittest")
        entry["path"] = entry["path"].replace("/experiment_flow/", "/unittest/")
        entry["module_name"] = "unittest.tests.test_constant"
        report = self.run_fixture()
        self.assertEqual(report["status"], "failed", report)
        self.assertIn("package collision", report["modules"][0]["collection_messages"][0])

    def test_namespace_package_parents_remain_confined_to_the_owner(self):
        self.package("first", "FIRST")
        source = self.root / "tools/first/source/experiment_flow"
        (source / "__init__.py").unlink()
        (source / "tests/__init__.py").unlink()
        report = self.run_fixture()
        self.assertEqual(report["status"], "passed", report)

    def test_authored_parent_cannot_expand_namespace_to_another_root(self):
        self.package("first", "FIRST")
        init = self.root / "tools/first/source/experiment_flow/__init__.py"
        init.write_text("__path__ = ['/outside-owning-snapshot']\n", encoding="utf-8")
        report = self.run_fixture()
        self.assertEqual(report["status"], "failed", report)
        self.assertIn("namespace escapes", report["modules"][0]["collection_messages"][0])

    def test_junction_and_symlink_roots_are_denied_without_loading(self):
        entry = self.package("first", "FIRST")
        with mock.patch.object(Path, "is_junction", lambda path: path.name == "source", create=True):
            with self.assertRaisesRegex(ValueError, "linked"):
                runner.validate_entry_imports(self.root, entry)
        with mock.patch.object(Path, "is_symlink", lambda path: path.name == "source"):
            with self.assertRaisesRegex(ValueError, "linked"):
                runner.validate_entry_imports(self.root, entry)

    def test_aggregate_parser_accepts_valid_optional_fields_but_keeps_training_class(self):
        entry = self.package("first", "FIRST")
        entry["dependency_class"] = "training"
        classified = no_training._classifications(self.root, self.data())
        self.assertEqual(classified[entry["path"].casefold()]["dependency_class"], "training")
        entry["import_roots"] = ["../outside"]
        with self.assertRaises(no_training.InventoryClassificationError):
            no_training._classifications(self.root, self.data())


if __name__ == "__main__":
    unittest.main()

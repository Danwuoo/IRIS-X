"""Synthetic offline inventory, process-isolation and gate regression tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / "pyproject.toml").is_file() and (path / "tools").is_dir())
sys.path.insert(0, str(ROOT))

from tools import suite_runner as runner


CORE_TEST = """import unittest
class TestCore(unittest.TestCase):
    def test_public_case(self):
        self.assertEqual(2 + 2, 4)
"""

TOOL_TEST = """import unittest
class TestTool(unittest.TestCase):
    def test_tool_case(self):
        self.assertEqual('synthetic'.upper(), 'SYNTHETIC')
"""

PRIVATE_TEST = """from pathlib import Path
Path(__file__).with_name('PRIVATE_IMPORTED').write_text('unexpected import', encoding='utf-8')
raise RuntimeError('UNSELECTED_PRIVATE_IMPORTED')
"""


class SuiteRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="irisx-suite-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repository"
        self.root.mkdir()
        self.attempt = 0
        self.data = {
            "format": "irisx.tests.v1",
            "suites": {"core": {"public": True}, "operational": {"public": False}},
            "entries": [
                self.entry("tests/test_core.py", "core"),
                self.entry("tools/probe/test_tool.py", "core"),
                self.entry("tests/test_private.py", "operational", "operational"),
            ],
        }
        self.write_text("tests/test_core.py", CORE_TEST)
        self.write_text("tools/probe/test_tool.py", TOOL_TEST)
        self.write_text("tests/test_private.py", PRIVATE_TEST)
        self.flush()

    @staticmethod
    def entry(path: str, suite: str, dependency_class: str = "stdlib") -> dict:
        return {"path": path, "workstream": "core" if suite == "core" else "arc-agi-2",
                "dependency_class": dependency_class, "suite": suite, "role": "test",
                "dependencies": [], "collector": "unittest",
                "reason": "New synthetic test fixture; no authentic provider or evaluator inputs",
                "expected_skips": []}

    def write_text(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def flush(self) -> None:
        self.write_text("tests/inventory.json", json.dumps(self.data, indent=2) + "\n")

    def assert_invalid(self, *fragments: str) -> None:
        issues = runner.validate_inventory(self.root, self.data)
        self.assertTrue(issues, "invalid synthetic inventory was accepted")
        text = "\n".join(issues).lower()
        self.assertTrue(any(fragment.lower() in text for fragment in fragments), text)

    def run_suite(self, suite: str = "core") -> dict:
        self.flush()
        self.attempt += 1
        output = self.root / ".irisx/core/suite-test" / f"attempt-{self.attempt:03d}"
        report = runner.run_suite(self.root, suite, output)
        self.assertEqual(json.loads((output / "report.json").read_text(encoding="utf-8")), report)
        return report

    def assert_failed(self, report: dict) -> None:
        self.assertEqual(report["status"], "failed", report)
        self.assertNotEqual(report["exit_code"], 0, report)

    def test_valid_inventory_covers_tests_and_tool_tests(self) -> None:
        self.assertEqual(runner.validate_inventory(self.root, self.data), [])
        self.assertEqual(runner.validate_inventory(self.root), [])
        selected = runner.select_suite(self.root, "core", self.data)
        self.assertEqual({entry["path"] for entry in selected},
                         {"tests/test_core.py", "tools/probe/test_tool.py"})

    def test_validation_and_selection_are_read_only_and_never_import_private_files(self) -> None:
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(runner.validate_inventory(self.root, self.data), [])
        runner.select_suite(self.root, "core", self.data)
        after = {path.relative_to(self.root): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / "tests/PRIVATE_IMPORTED").exists())

    def test_new_unregistered_test_file_is_not_silently_omitted(self) -> None:
        self.write_text("tests/test_new.py", CORE_TEST)
        self.assert_invalid("coverage", "unregistered", "unclassified", "missing")

    def test_new_unregistered_tool_test_file_is_not_silently_omitted(self) -> None:
        self.write_text("tools/new_probe/test_new.py", TOOL_TEST)
        self.assert_invalid("coverage", "unregistered", "unclassified", "missing")

    def test_duplicate_classification_rejected(self) -> None:
        self.data["entries"].append(copy.deepcopy(self.data["entries"][0]))
        self.assert_invalid("duplicate", "classification")

    def test_missing_indexed_test_file_rejected(self) -> None:
        (self.root / "tests/test_core.py").unlink()
        self.assert_invalid("missing", "file", "path")

    def test_inventory_paths_cannot_escape_or_use_unbounded_globs(self) -> None:
        for path in ("../outside.py", "/tmp/test.py", "C:\\test.py", "tests/../test.py", "tests/**"):
            with self.subTest(path=path):
                self.data["entries"][0]["path"] = path
                self.assert_invalid("path", "escape", "glob", "coverage")

    def test_unknown_executable_fields_rejected_without_execution(self) -> None:
        self.data["entries"][0]["command"] = "create MUST-NOT-EXIST"
        self.assert_invalid("unknown", "field", "command")
        self.assertFalse((self.root / "MUST-NOT-EXIST").exists())
        del self.data["entries"][0]["command"]
        self.data["run_command"] = "create MUST-NOT-EXIST"
        self.assert_invalid("unknown", "field", "command")
        self.assertFalse((self.root / "MUST-NOT-EXIST").exists())

    def test_entry_cannot_expand_collection_to_product_source(self) -> None:
        self.write_text("src/foreign.py", CORE_TEST)
        self.data["entries"].append(self.entry("src/foreign.py", "core"))
        self.assert_invalid("managed", "test root", "path", "scope")

    def test_expected_skip_policy_rejects_blank_reason_or_non_string_platform(self) -> None:
        allowed = {"test_id": "test_core.TestCore.test_skip", "reason_contains": "Synthetic platform limitation",
                   "platforms": [sys.platform]}
        for change in ({"reason_contains": " "}, {"platforms": [True]}, {"platforms": [None]},
                       {"platforms": [""]}):
            with self.subTest(change=change):
                self.data["entries"][0]["expected_skips"] = [dict(allowed, **change)]
                self.assert_invalid("skip", "reason", "platform")

    def test_undeclared_suite_and_invalid_dependency_class_rejected(self) -> None:
        self.data["entries"][0]["suite"] = "missing"
        self.assert_invalid("suite")
        self.data["entries"][0]["suite"] = "core"
        self.data["entries"][0]["dependency_class"] = "secret-magic"
        self.assert_invalid("dependency", "class")

    def test_empty_suite_is_rejected_before_execution(self) -> None:
        self.data["entries"] = [entry for entry in self.data["entries"] if entry["suite"] != "core"]
        (self.root / "tests/test_core.py").unlink()
        (self.root / "tools/probe/test_tool.py").unlink()
        with self.assertRaises(ValueError):
            runner.select_suite(self.root, "core", self.data)

    def test_helper_only_suite_is_not_a_successful_test_selection(self) -> None:
        for entry in self.data["entries"]:
            if entry["suite"] == "core":
                entry.update(role="helper", collector="helper")
        with self.assertRaises(ValueError):
            runner.select_suite(self.root, "core", self.data)

    def test_invalid_or_unknown_selection_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            runner.select_suite(self.root, "missing", self.data)
        self.data["entries"].append(copy.deepcopy(self.data["entries"][0]))
        with self.assertRaises(ValueError):
            runner.select_suite(self.root, "core", self.data)

    def test_core_runs_in_children_without_importing_unselected_private_test(self) -> None:
        report = self.run_suite()
        self.assertEqual(report["status"], "passed", report)
        self.assertEqual(report["exit_code"], 0, report)
        self.assertEqual(report["tests"], 2, report)
        self.assertEqual(report["failures"], 0, report)
        self.assertEqual(report["errors"], 0, report)
        self.assertEqual(report["blocked"], 0, report)
        self.assertEqual({row["path"] for row in report["modules"]},
                         {"tests/test_core.py", "tools/probe/test_tool.py"})
        self.assertFalse((self.root / "tests/PRIVATE_IMPORTED").exists())

    def test_collection_error_is_reported_as_failure_with_nonzero_counts(self) -> None:
        self.write_text("tests/test_core.py", "raise RuntimeError('SYNTHETIC_COLLECTION_ERROR')\n")
        report = self.run_suite()
        self.assert_failed(report)
        self.assertGreater(report["errors"], 0, report)
        self.assertGreater(sum(row["collection_errors"] for row in report["modules"]), 0, report)

    def test_zero_collected_tests_is_failure(self) -> None:
        self.write_text("tests/test_core.py", "def helper_only():\n    return 1\n")
        self.write_text("tools/probe/test_tool.py", "VALUE = 'no tests'\n")
        report = self.run_suite()
        self.assert_failed(report)
        self.assertEqual(report["tests"], 0, report)

    def test_assertion_failure_retains_the_real_failure_count(self) -> None:
        self.write_text("tests/test_core.py", "import unittest\nclass TestCore(unittest.TestCase):\n"
                        "    def test_failure(self):\n        self.fail('synthetic deliberate failure')\n")
        report = self.run_suite()
        self.assert_failed(report)
        self.assertEqual(report["failures"], 1, report)
        self.assertEqual(report["tests"], 2, report)

    def write_skip_test(self) -> None:
        self.write_text("tests/test_core.py", "import unittest\nclass TestCore(unittest.TestCase):\n"
                        "    @unittest.skip('Synthetic platform limitation')\n"
                        "    def test_skip(self):\n        pass\n")

    def test_unexpected_skip_is_failure(self) -> None:
        self.write_skip_test()
        report = self.run_suite()
        self.assert_failed(report)
        self.assertEqual(report["skips"], 1, report)
        self.assertEqual(report["unexpected_skips"], 1, report)

    def test_exact_platform_and_reason_bound_skip_is_visible(self) -> None:
        self.write_skip_test()
        self.data["entries"][0]["expected_skips"] = [{
            "test_id": "test_core.TestCore.test_skip", "reason_contains": "Synthetic platform limitation",
            "platforms": [sys.platform],
        }]
        report = self.run_suite()
        self.assertEqual(report["status"], "passed", report)
        self.assertEqual(report["skips"], 1, report)
        self.assertEqual(report["expected_skips"], 1, report)
        self.assertEqual(report["unexpected_skips"], 0, report)

    def test_skip_whitelist_does_not_cover_another_reason(self) -> None:
        self.write_skip_test()
        self.data["entries"][0]["expected_skips"] = [{
            "test_id": "test_core.TestCore.test_skip", "reason_contains": "Different reason",
            "platforms": [sys.platform],
        }]
        report = self.run_suite()
        self.assert_failed(report)
        self.assertEqual(report["unexpected_skips"], 1, report)

    def test_protected_classes_are_blocked_before_import(self) -> None:
        for dependency_class in ("historical", "operational", "native", "training"):
            with self.subTest(dependency_class=dependency_class):
                self.data["entries"][2]["dependency_class"] = dependency_class
                report = self.run_suite("operational")
                self.assertEqual(report["status"], "blocked", report)
                self.assertNotEqual(report["exit_code"], 0, report)
                self.assertEqual(report["tests"], 0, report)
                self.assertGreater(report["blocked"], 0, report)
                self.assertFalse((self.root / "tests/PRIVATE_IMPORTED").exists())

    def test_unclassified_public_failure_is_executed_and_not_hidden_as_private(self) -> None:
        self.data["suites"]["audit"] = {"public": False}
        self.data["entries"][0].update(suite="audit", dependency_class="unclassified-public")
        self.write_text("tests/test_core.py", "import unittest\nclass TestCore(unittest.TestCase):\n"
                        "    def test_failure(self):\n        self.fail('visible audit failure')\n")
        report = self.run_suite("audit")
        self.assert_failed(report)
        self.assertEqual(report["blocked"], 0, report)
        self.assertEqual(report["failures"], 1, report)


class GateTests(unittest.TestCase):
    @staticmethod
    def report() -> dict:
        return {"status": "passed", "tests": 1, "failures": 0, "errors": 0, "skips": 0,
                "blocked": 0, "exit_code": 0, "expected_skips": 0, "unexpected_skips": 0}

    def test_gate_accepts_only_complete_successful_expected_reports(self) -> None:
        reports = {"core": self.report(), "line-b": self.report()}
        self.assertEqual(runner.validate_gate(reports, ["core", "line-b"]), [])

    def test_gate_rejects_missing_reports(self) -> None:
        self.assertTrue(runner.validate_gate({"core": self.report()}, ["core", "line-b"]))

    def test_gate_rejects_cancellation_blocking_zero_tests_and_report_failures(self) -> None:
        changes = [{"status": "cancelled", "exit_code": -1},
                   {"status": "blocked", "blocked": 1, "exit_code": 2},
                   {"tests": 0}, {"unexpected_skips": 1, "skips": 1},
                   {"failures": 1}, {"errors": 1}, {"exit_code": 1}]
        for change in changes:
            with self.subTest(change=change):
                report = dict(self.report(), **change)
                self.assertTrue(runner.validate_gate({"core": report}, ["core"]))

    def test_gate_rejects_empty_selection_or_unexpected_skip_as_pass(self) -> None:
        self.assertTrue(runner.validate_gate({}, []))
        report = dict(self.report(), skips=1, unexpected_skips=1)
        self.assertTrue(runner.validate_gate({"core": report}, ["core"]))

    def test_gate_rejects_boolean_float_negative_or_missing_counts(self) -> None:
        changes = [{"failures": False}, {"errors": 0.0}, {"exit_code": False},
                   {"blocked": None}, {"unexpected_skips": False},
                   {"skips": -1, "expected_skips": -1}]
        for change in changes:
            with self.subTest(change=change):
                self.assertTrue(runner.validate_gate({"core": dict(self.report(), **change)}, ["core"]))


if __name__ == "__main__":
    unittest.main()

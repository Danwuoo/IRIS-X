"""Synthetic runtime-denial tests; no real trainer body is executed."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / "pyproject.toml").is_file() and (path / "tools").is_dir())
sys.path.insert(0, str(ROOT))
from tools import no_training as guard


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


class NoTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="irisx-no-training-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tests").mkdir()
        self.events = []
        self.data = {"format": "irisx.tests.v1", "suites": {"core": {"public": True}}, "entries": []}

    def entry(self, path, dependency_class):
        return {"path": path, "workstream": "core", "dependency_class": dependency_class,
                "suite": "core", "role": "test", "dependencies": [], "collector": "unittest",
                "reason": "Authored counter fixture only; no training implementation", "expected_skips": []}

    def case(self, name, dependency_class="stdlib"):
        path = self.root / "tests" / (name + ".py")
        path.write_text("# Authored source identity only; never imported.\n", encoding="utf-8")
        self.data["entries"].append(self.entry(path.relative_to(self.root).as_posix(), dependency_class))
        module_name = "_irisx_no_training_fixture_" + name
        module = types.ModuleType(module_name)
        module.__file__ = str(path)
        events = self.events
        module.setUpModule = lambda: events.append(name + ":module")
        previous = sys.modules.get(module_name)
        sys.modules[module_name] = module

        def restore():
            if previous is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous
        self.addCleanup(restore)

        def body(_case):
            events.append(name + ":body")
        case_type = type("Fixture_" + name, (unittest.TestCase,),
                         {"__module__": module_name, "test_counter": body,
                          "setUpClass": classmethod(lambda _cls: events.append(name + ":class")),
                          "setUp": lambda _case: events.append(name + ":setup"),
                          "tearDown": lambda _case: events.append(name + ":teardown")})
        return case_type("test_counter")

    def run_cases(self, suite):
        return unittest.TextTestRunner(stream=io.StringIO()).run(suite)

    def flush(self, data=None):
        (self.root / "tests/inventory.json").write_text(json.dumps(data or self.data), encoding="utf-8")

    def test_nested_suite_retains_every_id_count_order_and_public_object(self):
        first = self.case("ordinary_first")
        protected = self.case("prohibited_body", "training")
        last = self.case("ordinary_last")
        original = unittest.TestSuite([first, unittest.TestSuite([protected, unittest.TestSuite([last])])])
        ids = [case.id() for case in flatten(original)]
        changed = guard.constrain_suite(original, self.root, self.data)
        self.assertEqual(changed.countTestCases(), original.countTestCases())
        self.assertEqual([case.id() for case in flatten(changed)], ids)
        self.assertIs(list(flatten(changed))[0], first)
        self.assertIs(list(flatten(changed))[-1], last)
        result = self.run_cases(changed)
        self.assertEqual((result.testsRun, len(result.errors), len(result.failures), len(result.skipped)), (3, 1, 0, 0))
        self.assertEqual(changed.blocked_test_ids, (protected.id(),))
        self.assertIn("TrainingBlockedError", result.errors[0][1])
        self.assertIn(protected.id(), result.errors[0][1])
        self.assertFalse(any(event.startswith("prohibited_body:") for event in self.events))
        self.assertIn("ordinary_first:body", self.events)
        self.assertIn("ordinary_last:body", self.events)

    def test_only_training_class_is_blocked_by_case_proxy(self):
        cases = [self.case("classification_" + name, name)
                 for name in ("stdlib", "native", "historical", "operational")]
        # These four bodies only append counters; they are not real protected operations.
        changed = guard.constrain_suite(unittest.TestSuite(cases), self.root, self.data)
        self.assertEqual(changed.blocked_test_ids, ())
        result = self.run_cases(changed)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 4)

    def test_function_case_is_denied_without_body_or_changed_id(self):
        source_case = self.case("function_source", "training")
        def fictional_body():
            self.events.append("function:body")
        fictional_body.__module__ = type(source_case).__module__
        original = unittest.FunctionTestCase(fictional_body)
        changed = guard.constrain_suite(unittest.TestSuite([original]), self.root, self.data)
        self.assertEqual(list(flatten(changed))[0].id(), original.id())
        result = self.run_cases(changed)
        self.assertEqual((result.testsRun, len(result.errors), len(result.skipped)), (1, 1, 0))
        self.assertEqual(self.events, [])

    def test_original_collection_error_keeps_object_id_and_error(self):
        original = unittest.loader._FailedTest("synthetic_missing", ImportError("synthetic unavailable module"))
        changed = guard.constrain_suite(unittest.TestSuite([original]), self.root, self.data)
        self.assertIs(list(flatten(changed))[0], original)
        result = self.run_cases(changed)
        self.assertEqual((result.testsRun, len(result.errors)), (1, 1))
        self.assertIn("synthetic unavailable module", result.errors[0][1])

    def test_repeated_constraining_remains_denied(self):
        original = self.case("repeated", "training")
        changed = guard.constrain_suite(unittest.TestSuite([original]), self.root, self.data)
        changed = guard.constrain_suite(changed, self.root, self.data)
        self.assertEqual(changed.blocked_test_ids, (original.id(),))
        self.assertEqual(len(self.run_cases(changed).errors), 1)
        self.assertEqual(self.events, [])

    def test_missing_classification_fails_before_any_case_body(self):
        case = self.case("unclassified")
        self.data["entries"].clear()
        with self.assertRaisesRegex(guard.InventoryClassificationError, "unclassified"):
            guard.constrain_suite(unittest.TestSuite([case]), self.root, self.data)
        self.assertEqual(self.events, [])

    def test_duplicate_unsafe_unknown_metadata_fail_closed(self):
        case = self.case("safe")
        for mutation, expected in (("duplicate", "duplicate"), ("unsafe", "unsafe"),
                                   ("unknown", "fields"), ("class", "dependency")):
            data = copy.deepcopy(self.data)
            if mutation == "duplicate":
                data["entries"].append(copy.deepcopy(data["entries"][0]))
            elif mutation == "unsafe":
                data["entries"][0]["path"] = "../escaped.py"
            elif mutation == "unknown":
                data["entries"][0]["command"] = "never executed"
            else:
                data["entries"][0]["dependency_class"] = "unknown"
            with self.subTest(mutation=mutation), self.assertRaisesRegex(guard.InventoryClassificationError, expected):
                guard.constrain_suite(unittest.TestSuite([case]), self.root, data)
        self.assertEqual(self.events, [])

    def test_exact_inventory_file_and_duplicate_json_key(self):
        case = self.case("file")
        self.flush()
        changed = guard.constrain_suite(unittest.TestSuite([case]), self.root, self.root / "tests/inventory.json")
        self.assertEqual(changed.countTestCases(), 1)
        elsewhere = self.root / "other.json"
        elsewhere.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaisesRegex(guard.InventoryClassificationError, "exact tests/inventory.json"):
            guard.constrain_suite(unittest.TestSuite([case]), self.root, elsewhere)
        (self.root / "tests/inventory.json").write_text('{"format":"a","format":"b"}', encoding="utf-8")
        with self.assertRaisesRegex(guard.InventoryClassificationError, "duplicate inventory JSON key"):
            guard.constrain_suite(unittest.TestSuite([case]), self.root)

    def test_junction_path_is_denied_without_case_execution(self):
        case = self.case("junction")
        with mock.patch.object(Path, "is_junction", lambda path: path.name == "junction.py", create=True):
            with self.assertRaisesRegex(guard.InventoryClassificationError, "linked inventory path"):
                guard.constrain_suite(unittest.TestSuite([case]), self.root, self.data)
        self.assertEqual(self.events, [])

    def test_runtime_guard_replaces_fake_calls_and_already_loaded_alias(self):
        events = self.events
        def fictional_call(*_args, **_kwargs):
            events.append("fake:body")
        class FictionalModel:
            train_step = fictional_call
        training = types.SimpleNamespace(tiny_train=fictional_call, TinyTransitionModel=FictionalModel)
        cli = types.SimpleNamespace(tiny_train=fictional_call)
        counters = guard.install_runtime_guard({"irisx.arc_nvarc_training": training, "irisx.arc_nvarc_cli": cli})
        later_alias = training.tiny_train
        for call in (training.tiny_train, FictionalModel().train_step, cli.tiny_train, later_alias):
            for _ in range(2):
                with self.assertRaisesRegex(guard.TrainingBlockedError, "BLOCKED training call"):
                    call("fictional input")
        self.assertEqual(counters["blocked_calls"], 8)
        self.assertEqual(events, [])

    def test_runtime_guard_rejects_missing_known_callsites(self):
        with self.assertRaisesRegex(guard.InventoryClassificationError, "callsites"):
            guard.install_runtime_guard({"irisx.arc_nvarc_training": types.SimpleNamespace()})

    def aggregate_sources(self, *, complete=True):
        public = """import unittest
class Ordinary(unittest.TestCase):
    def test_ordinary(self): self.assertEqual(2 + 2, 4)
"""
        blocked = """import unittest
from irisx.arc_nvarc_training import tiny_train
class Original(unittest.TestCase):
    def test_protected(self): tiny_train()
"""
        for name, text, dependency in (("test_a.py", public, "stdlib"), ("test_b.py", blocked, "training")):
            (self.root / "tests" / name).write_text(text, encoding="utf-8")
            if complete or dependency == "stdlib":
                self.data["entries"].append(self.entry("tests/" + name, dependency))
        source = self.root / "src/irisx"
        source.mkdir(parents=True)
        (source / "__init__.py").write_text("# Fictional package only.\n", encoding="utf-8")
        (source / "arc_nvarc_training.py").write_text("""def tiny_train(*args, **kwargs):
    raise AssertionError('FICTIONAL BODY MUST NOT RUN')
class TinyTransitionModel:
    def train_step(self, *args, **kwargs):
        raise AssertionError('FICTIONAL BODY MUST NOT RUN')
""", encoding="utf-8")
        self.flush()

    def test_aggregate_cli_retains_default_discovery_count_and_errors(self):
        self.aggregate_sources()
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/no_training.py"),
                                 "--aggregate", "--root", str(self.root)],
                                cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Ran 2 tests", result.stderr)
        self.assertIn("TrainingBlockedError", result.stderr)
        self.assertIn("test_b.Original.test_protected", result.stderr)
        self.assertIn("blocked_training=1", result.stderr)
        self.assertNotIn("FICTIONAL BODY MUST NOT RUN", result.stderr)
        self.assertLess(result.stderr.index("test_ordinary ("), result.stderr.index("test_protected ("))

    def test_incomplete_aggregate_inventory_fails_before_collection(self):
        self.aggregate_sources(complete=False)
        marker = self.root / "IMPORTED_UNCLASSIFIED"
        source = self.root / "tests/test_b.py"
        source.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n", encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/no_training.py"),
                                 "--aggregate", "--root", str(self.root)],
                                cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn("BLOCKED inventory classification", result.stderr)
        self.assertFalse(marker.exists())
        self.assertNotIn("Ran ", result.stderr)

    def test_aggregate_runtime_guard_denies_missed_classification_alias(self):
        self.aggregate_sources()
        self.data["entries"][1]["dependency_class"] = "stdlib"
        self.flush()
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/no_training.py"),
                                 "--aggregate", "--root", str(self.root)],
                                cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Ran 2 tests", result.stderr)
        self.assertIn("TrainingBlockedError", result.stderr)
        self.assertIn("blocked_training=0", result.stderr)
        self.assertIn("runtime_training_calls_blocked=1", result.stderr)
        self.assertNotIn("FICTIONAL BODY MUST NOT RUN", result.stderr)


if __name__ == "__main__":
    unittest.main()

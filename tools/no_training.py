"""Retain original aggregate cases while denying inventory-classified training.

The aggregate validates its exact inventory before collecting tests. Collection
still imports the original modules: this runtime guard cannot stop import-time
training, custom TestCase constructors or load_tests side effects. A caller must
separately review those surfaces or use the static pre-import suite runner. An
import-blocking loader cannot preserve unknown dynamically collected cases and
their original counts/IDs merely from this file-level inventory.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path, PurePosixPath
import sys
import unittest


class TrainingBlockedError(RuntimeError):
    """An original test is retained as an error because training is unauthorized."""


class InventoryClassificationError(ValueError):
    """The aggregate cannot safely classify the original tests."""


_ENTRY_FIELDS = {
    "path", "workstream", "dependency_class", "suite", "role", "dependencies",
    "collector", "reason", "expected_skips",
}
_OPTIONAL_ENTRY_FIELDS = {"import_roots", "module_name"}
_DEPENDENCY_CLASSES = {
    "stdlib", "small-python", "historical", "operational", "native",
    "training", "unclassified-public",
}


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise InventoryClassificationError(f"duplicate inventory JSON key: {key}")
        value[key] = item
    return value


def _safe_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise InventoryClassificationError("invalid inventory path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts) or PurePosixPath(value).is_absolute():
        raise InventoryClassificationError(f"unsafe inventory path: {value}")
    path = root
    for part in parts:
        path /= part
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise InventoryClassificationError(f"linked inventory path: {value}")
    if not path.resolve().is_relative_to(root):
        raise InventoryClassificationError(f"inventory path escapes root: {value}")
    return path


def _classifications(root: Path, inventory) -> dict[str, dict]:
    """Read only the exact inventory or a supplied in-memory synthetic record."""
    if not isinstance(inventory, dict):
        expected = _safe_path(root, "tests/inventory.json")
        supplied = expected if inventory is None else Path(inventory)
        if supplied.resolve() != expected.resolve() or supplied.is_symlink():
            raise InventoryClassificationError("aggregate requires exact tests/inventory.json")
        try:
            inventory = json.loads(expected.read_text(encoding="utf-8"),
                                   object_pairs_hook=_unique_object)
        except (OSError, json.JSONDecodeError) as exc:
            raise InventoryClassificationError(f"cannot read inventory: {exc}") from exc
    if set(inventory) != {"format", "suites", "entries"} or inventory["format"] != "irisx.tests.v1":
        raise InventoryClassificationError("invalid inventory schema")
    suites, entries = inventory["suites"], inventory["entries"]
    if not isinstance(suites, dict) or not suites or not isinstance(entries, list):
        raise InventoryClassificationError("invalid suite/entry catalog")
    for name, options in suites.items():
        if (not isinstance(name, str) or not name or not isinstance(options, dict)
                or set(options) != {"public"} or type(options["public"]) is not bool):
            raise InventoryClassificationError("invalid suite definition")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or not _ENTRY_FIELDS <= set(entry) or set(entry) - _ENTRY_FIELDS - _OPTIONAL_ENTRY_FIELDS:
            raise InventoryClassificationError("unknown or missing inventory entry fields")
        path = _safe_path(root, entry["path"])
        if entry["path"].split("/")[0] not in {"tests", "tools"} or path.suffix != ".py" or not path.is_file():
            raise InventoryClassificationError(f"missing/unmanaged Python path: {entry['path']}")
        if set(entry) & _OPTIONAL_ENTRY_FIELDS:
            try:
                from .suite_runner import validate_entry_imports
            except ImportError:
                from suite_runner import validate_entry_imports
            try:
                validate_entry_imports(root, entry)
            except ValueError as exc:
                raise InventoryClassificationError(f"invalid snapshot import metadata: {exc}") from exc
        key = entry["path"].casefold()
        if key in result:
            raise InventoryClassificationError(f"duplicate classification: {entry['path']}")
        if (not isinstance(entry["dependency_class"], str)
                or entry["dependency_class"] not in _DEPENDENCY_CLASSES
                or not isinstance(entry["suite"], str) or entry["suite"] not in suites):
            raise InventoryClassificationError(f"invalid dependency/suite: {entry['path']}")
        if (not isinstance(entry["workstream"], str)
                or entry["workstream"] not in {"core", "arc-agi-2", "line-b"}
                or not isinstance(entry["role"], str)
                or entry["role"] not in {"test", "helper", "script"}):
            raise InventoryClassificationError(f"invalid workstream/role: {entry['path']}")
        if (not isinstance(entry["collector"], str)
                or entry["collector"] not in {"unittest", "helper", "blocked-script"}
                or ((entry["role"] == "test") != (entry["collector"] == "unittest"))
                or not isinstance(entry["reason"], str) or not entry["reason"].strip()
                or not isinstance(entry["dependencies"], list)
                or not all(isinstance(item, str) for item in entry["dependencies"])
                or not isinstance(entry["expected_skips"], list)):
            raise InventoryClassificationError(f"invalid collection/dependency metadata: {entry['path']}")
        for skip in entry["expected_skips"]:
            if (not isinstance(skip, dict) or set(skip) != {"test_id", "reason_contains", "platforms"}
                    or not isinstance(skip["test_id"], str) or not skip["test_id"].strip()
                    or not isinstance(skip["reason_contains"], str) or not skip["reason_contains"].strip()
                    or not isinstance(skip["platforms"], list) or not skip["platforms"]
                    or any(not isinstance(item, str) or item not in {"win32", "linux", "darwin"}
                           for item in skip["platforms"])):
                raise InventoryClassificationError(f"invalid expected skip metadata: {entry['path']}")
        result[key] = entry
    required = {path.relative_to(root).as_posix().casefold()
                for path in (root / "tests").rglob("*.py")}
    required.update(path.relative_to(root).as_posix().casefold()
                    for path in (root / "tools").rglob("test_*.py"))
    missing = required - result.keys()
    if missing:
        raise InventoryClassificationError("unclassified test paths: " + ", ".join(sorted(missing)))
    return result


class _BlockedTrainingCase(unittest.TestCase):
    def __init__(self, original: unittest.TestCase, path: str):
        super().__init__("runTest")
        self._original_id = original.id()
        self._original_description = str(original)
        self._blocked_path = path

    def id(self):
        return self._original_id

    def __str__(self):
        return self._original_description

    def runTest(self):
        raise TrainingBlockedError(
            f"BLOCKED training test {self.id()}: {self._blocked_path}; "
            "owner scope excludes training; original case retained as ERROR"
        )


def _case_path(test: unittest.TestCase, root: Path) -> str | None:
    # Loader errors already preserve import exceptions; do not replace their IDs.
    if type(test).__module__ == "unittest.loader" and type(test).__name__ == "_FailedTest":
        return None
    if isinstance(test, _BlockedTrainingCase):
        return test._blocked_path
    subject = test._testFunc if isinstance(test, unittest.FunctionTestCase) else type(test)
    module = sys.modules.get(subject.__module__)
    filename = getattr(module, "__file__", None)
    if not isinstance(filename, str):
        raise InventoryClassificationError(f"test has no source module path: {test.id()}")
    path = Path(filename).resolve()
    if not path.is_relative_to(root):
        raise InventoryClassificationError(f"test source outside classified root: {test.id()}")
    return path.relative_to(root).as_posix()


def constrain_suite(suite: unittest.TestSuite, root: Path, inventory=None) -> unittest.TestSuite:
    """Preserve original case order/count/IDs; only training becomes explicit ERROR.

    Nonprotected cases remain the original objects. Protected proxies have no
    original class/module/setup/teardown fixtures, so those cannot start training.
    No test module is imported by this function.
    """
    root = Path(root).resolve()
    classified = _classifications(root, inventory)
    blocked = []

    def walk(item):
        if isinstance(item, unittest.TestSuite):
            return unittest.TestSuite(walk(child) for child in item)
        if not isinstance(item, unittest.TestCase) or item.countTestCases() != 1:
            raise InventoryClassificationError("unsupported aggregate test leaf")
        path = _case_path(item, root)
        if path is None:
            return item
        entry = classified.get(path.casefold())
        if entry is None:
            raise InventoryClassificationError(f"unclassified collected test: {item.id()} ({path})")
        if entry["dependency_class"] != "training":
            return item
        blocked.append(item.id())
        return item if isinstance(item, _BlockedTrainingCase) else _BlockedTrainingCase(item, path)

    if not isinstance(suite, unittest.TestSuite):
        raise InventoryClassificationError("aggregate must be a unittest.TestSuite")
    result = walk(suite)
    if result.countTestCases() != suite.countTestCases():
        raise InventoryClassificationError("aggregate case count changed")
    result.blocked_test_ids = tuple(blocked)
    return result


def install_runtime_guard(modules=None) -> dict[str, int]:
    """Deny the two known pure-Python fitting callsites before test discovery.

    Production imports only the reviewed dependency-free training module. Tests
    supply fake modules, so guard verification never calls an actual trainer.
    Already-loaded CLI aliases are patched; later imports receive guarded names.
    This is an in-process callsite safeguard, not a general Python sandbox.
    """
    module_name = "irisx.arc_nvarc_training"
    if modules is None:
        training = importlib.import_module(module_name)
        cli = sys.modules.get("irisx.arc_nvarc_cli")
    else:
        training = modules.get(module_name)
        cli = modules.get("irisx.arc_nvarc_cli")
    model = getattr(training, "TinyTransitionModel", None)
    if (not callable(getattr(training, "tiny_train", None))
            or model is None or not callable(getattr(model, "train_step", None))):
        raise InventoryClassificationError("known no-training callsites are missing")
    counters = {"blocked_calls": 0}

    def deny(name):
        def blocked(*_args, **_kwargs):
            counters["blocked_calls"] += 1
            raise TrainingBlockedError(f"BLOCKED training call {module_name}.{name}; owner scope excludes training")
        return blocked

    training.tiny_train = deny("tiny_train")
    model.train_step = deny("TinyTransitionModel.train_step")
    if cli is not None and hasattr(cli, "tiny_train"):
        cli.tiny_train = training.tiny_train
    return counters


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", action="store_true", required=True,
                        help="collect the original unittest aggregate with a runtime no-training guard")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository root; defaults to this checkout")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        # Fail before discovery when the static classification is incomplete.
        _classifications(root, None)
        data = json.loads((root / "tests/inventory.json").read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_object)
        sys.path[:0] = [str(root), str(root / "src")]
        guard_counters = install_runtime_guard()
        loader = unittest.TestLoader()
        original = loader.discover(str(root / "tests"), pattern="test*.py")
        guarded = constrain_suite(original, root, data)
    except (InventoryClassificationError, OSError, TypeError, KeyError, ImportError,
            json.JSONDecodeError) as exc:
        print(f"IRIS-X aggregate: BLOCKED inventory classification: {exc}", file=sys.stderr)
        return 1
    print(f"IRIS-X aggregate no-training guard: BLOCKED {len(guarded.blocked_test_ids)} "
          "training cases; original IDs/count/order retained", file=sys.stderr)
    result = unittest.TextTestRunner(verbosity=2).run(guarded)
    print(f"IRIS-X aggregate counts: ran={result.testsRun} failures={len(result.failures)} "
          f"errors={len(result.errors)} skips={len(result.skipped)} "
          f"blocked_training={len(guarded.blocked_test_ids)} "
          f"runtime_training_calls_blocked={guard_counters['blocked_calls']}", file=sys.stderr)
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

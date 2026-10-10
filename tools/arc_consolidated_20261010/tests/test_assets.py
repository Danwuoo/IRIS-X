"""Source-only admission checks; never construct a model backend."""
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.arc_consolidated_20261010 import assets, build_notebook
from tools.arc_consolidated_20261010.model_provider import G4Backend
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory


class ExecutableIdentityTests(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        for name, source in build_notebook.collect_sources().items():
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.encode("utf-8"))
        self.root = self.base / "tools" / "arc_consolidated_20261010"

    def test_exact_builder_overlay_and_canonical_helper_pins(self):
        self.assertEqual(G4Backend.SOURCE_PINS, build_notebook.BACKEND_PINS)
        expected = {name: hashlib.sha256(source.encode("utf-8")).hexdigest()
                    for name, source in build_notebook.collect_sources().items()}
        actual = assets.executable_identity()
        self.assertEqual(expected, actual)
        self.assertEqual(actual, assets.executable_identity(self.root))
        self.assertEqual(list(actual), sorted(actual))
        self.assertIn("tools/__init__.py", actual)
        self.assertEqual({name: value for name, value in actual.items()
                          if not name.startswith(build_notebook.PREFIX)},
                         {"tools/__init__.py": actual["tools/__init__.py"],
                          **{"tools/" + name: value
                             for name, value in G4Backend.SOURCE_PINS.items()}})
        self.assertEqual({name.removeprefix(build_notebook.PREFIX): value
                          for name, value in actual.items()
                          if name.startswith(build_notebook.PREFIX)},
                         assets.source_identity())

    def test_tests_docs_builder_and_output_are_excluded(self):
        before = assets.executable_identity(self.root)
        for name in ("tests/test_extra.py", "docs/review.md", "README.md",
                     "build_notebook.py", "output/result.json", "run.ipynb"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("non-runtime material", encoding="utf-8")
        self.assertEqual(before, assets.executable_identity(self.root))

    def test_initializer_and_new_runtime_source_are_bound(self):
        before = assets.executable_identity(self.root)
        (self.root.parent / "__init__.py").write_bytes(b"# changed initializer\n")
        (self.root / "extra.py").write_bytes(b"# extra runtime source\n")
        after = assets.executable_identity(self.root)
        self.assertNotEqual(before["tools/__init__.py"], after["tools/__init__.py"])
        self.assertEqual(after[build_notebook.PREFIX + "extra.py"],
                         hashlib.sha256(b"# extra runtime source\n").hexdigest())

    def test_each_immutable_helper_rejects_drift(self):
        for name in G4Backend.SOURCE_PINS:
            with self.subTest(name=name):
                path = self.root.parent / name
                raw = path.read_bytes()
                path.write_bytes(raw + b"\n# drift\n")
                with self.assertRaisesRegex(ValueError, "immutable asset hash mismatch"):
                    assets.executable_identity(self.root)
                path.write_bytes(raw)

    def test_each_legacy_interpreter_rejects_drift(self):
        for name in assets.PINS:
            with self.subTest(name=name):
                path = self.root / "legacy" / (name + ".py")
                raw = path.read_bytes()
                path.write_bytes(raw + b"\n# drift\n")
                with self.assertRaisesRegex(ValueError, "immutable asset hash mismatch"):
                    assets.executable_identity(self.root)
                path.write_bytes(raw)

    def test_missing_or_directory_helper_rejected(self):
        path = self.root.parent / "arc_next_models.py"
        path.unlink()
        with self.assertRaisesRegex(ValueError, "missing regular asset"):
            assets.executable_identity(self.root)
        path.mkdir()
        with self.assertRaisesRegex(ValueError, "missing regular asset"):
            assets.executable_identity(self.root)

    def test_missing_initializer_or_entrypoint_rejected(self):
        path = self.root.parent / "__init__.py"
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "missing regular asset"):
            assets.executable_identity(self.root)
        path.write_bytes(raw)
        (self.root / "runner.py").unlink()
        with self.assertRaisesRegex(ValueError, "entrypoints"):
            assets.executable_identity(self.root)

    def test_missing_inventory_directory_is_not_silently_omitted(self):
        directory = self.root / "data"
        for path in directory.iterdir():
            path.unlink()
        directory.rmdir()
        with self.assertRaisesRegex(ValueError, "missing source directory"):
            assets.executable_identity(self.root)

    def test_symlink_and_junction_files_and_ancestors_rejected(self):
        # Mock metadata probes so this runs without Windows link privileges.
        for method in ("is_symlink", "is_junction"):
            original = getattr(Path, method, lambda path: False)
            for target in (self.root.parent / "arc_next_models.py", self.root,
                           self.root / "data", self.base):
                with self.subTest(method=method, target=target):
                    def probe(path, target=target, original=original):
                        return path == target or original(path)
                    with patch.object(Path, method, probe, create=True):
                        with self.assertRaisesRegex(ValueError, "symlink/junction"):
                            assets.executable_identity(self.root)

    def test_parent_traversal_is_rejected_before_read(self):
        with self.assertRaisesRegex(ValueError, "parent traversal"):
            assets.executable_identity(self.root / ".." / self.root.name)

    def test_unexpected_helper_inventory_is_rejected(self):
        with patch.object(G4Backend, "SOURCE_PINS", {**G4Backend.SOURCE_PINS,
                                                    "extra.py": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "helper source inventory differs"):
                assets.executable_identity(self.root)


if __name__ == "__main__":
    unittest.main()

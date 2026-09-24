"""Offline regressions for the pinned NVARC source verifier and local bundle."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import nvarc_source


def git(directory: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=directory, check=True,
                            text=True, capture_output=True, encoding="utf-8")
    return result.stdout.strip()


def new_repo(directory: Path, files: dict[str, str]) -> None:
    directory.mkdir(parents=True)
    git(directory, "init", "-q")
    git(directory, "config", "user.name", "Fixture")
    git(directory, "config", "user.email", "fixture@example.test")
    for name, content in files.items():
        file = directory / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    git(directory, "add", ".")
    git(directory, "commit", "-qm", "fixture")


def source_fixture(root: Path) -> tuple[Path, dict]:
    upstream = root / "upstream"
    nested = upstream / "nested"
    child = upstream / "child"
    source = root / "source"
    main = source / "NVARC"
    new_repo(nested, {"nested.py": "VALUE = 3\n"})
    new_repo(child, {"child.py": "VALUE = 2\n", "other.py": "OTHER = 2\n"})
    git(child, "-c", "protocol.file.allow=always", "submodule", "add", "-q",
        str(nested), "editor")
    git(child, "commit", "-qam", "add nested")
    new_repo(main, {"bound.py": "VALUE = 1\n", "other.py": "OTHER = 1\n",
                    ".gitignore": "ignored_shadow.py\n"})
    git(main, "-c", "protocol.file.allow=always", "submodule", "add", "-q",
        str(child), "external/child")
    git(main, "commit", "-qam", "add child")
    git(main, "-c", "protocol.file.allow=always", "submodule", "update",
        "--init", "--recursive")
    child_checkout = main / "external/child"
    nested_checkout = child_checkout / "editor"
    notebooks = {
        "qwen": {"path": "kaggle-qwen/source.ipynb", "ref": "fixture/qwen",
                 "version_number": 10},
        "trm": {"path": "kaggle-trm/source.ipynb", "ref": "fixture/trm",
                "version_number": 21},
    }
    for name, info in notebooks.items():
        file = source / info["path"]
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps({"cells": [{"source": [name]}]}), encoding="utf-8")
        info["sha256"] = nvarc_source.sha256(file)
    manifest = {"git": {
        "NVARC": {"path": "", "url": str(main), "commit": git(main, "rev-parse", "HEAD")},
        "child": {"path": "external/child", "url": str(child),
                  "commit": git(child_checkout, "rev-parse", "HEAD")},
        "nested": {"path": "external/child/editor", "url": str(nested),
                   "commit": git(nested_checkout, "rev-parse", "HEAD")},
    }, "notebooks": notebooks,
        "code_files": {"bound.py": {"sha256": nvarc_source.sha256(main / "bound.py")}}}
    return source, manifest


class SourceMaterializationTests(unittest.TestCase):
    def test_unlisted_tracked_staged_missing_and_recursive_submodule_dirt_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            source, manifest = source_fixture(Path(temp))
            main = source / "NVARC"
            child = main / "external/child"
            nested = child / "editor"
            self.assertTrue(nvarc_source.verify(source, manifest)["source_ready"])
            other = main / "other.py"  # Deliberately absent from code_files.
            other.write_text("OTHER = 9\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NVARC index/worktree is dirty"):
                nvarc_source.verify(source, manifest)
            git(main, "restore", "other.py")
            other.unlink()
            with self.assertRaisesRegex(ValueError, "NVARC index/worktree is dirty"):
                nvarc_source.verify(source, manifest)
            git(main, "restore", "other.py")
            other.write_text("OTHER = 8\n", encoding="utf-8")
            git(main, "add", "other.py")
            with self.assertRaisesRegex(ValueError, "NVARC index/worktree is dirty"):
                nvarc_source.verify(source, manifest)
            git(main, "restore", "--staged", "--worktree", "other.py")
            git(main, "update-index", "--assume-unchanged", "other.py")
            other.write_text("OTHER = 6\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tracked file bypass flag"):
                nvarc_source.verify(source, manifest)
            git(main, "update-index", "--no-assume-unchanged", "other.py")
            git(main, "restore", "other.py")
            git(main, "update-index", "--skip-worktree", "other.py")
            other.write_text("OTHER = 5\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tracked file bypass flag"):
                nvarc_source.verify(source, manifest)
            git(main, "update-index", "--no-skip-worktree", "other.py")
            git(main, "restore", "other.py")
            (main / "shadow.py").write_text("VALUE = 0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NVARC index/worktree is dirty"):
                nvarc_source.verify(source, manifest)
            (main / "shadow.py").unlink()
            (main / "ignored_shadow.py").write_text("VALUE = 0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NVARC index/worktree is dirty"):
                nvarc_source.verify(source, manifest)
            (main / "ignored_shadow.py").unlink()
            (child / "other.py").write_text("OTHER = 7\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "child index/worktree is dirty"):
                nvarc_source.verify(source, manifest)
            git(child, "restore", "other.py")
            (nested / "nested.py").write_text("VALUE = 7\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nested index/worktree is dirty"):
                nvarc_source.verify(source, manifest)
            git(nested, "restore", "nested.py")
            cache = main / "SDG/scripts/__pycache__"
            cache.mkdir(parents=True)
            (cache / "build_datasets.cpython-312.pyc").write_bytes(b"ignored by direct loader")
            self.assertTrue(nvarc_source.verify(source, manifest)["source_ready"])
            (cache / "shadow.cpython-312.pyc").write_bytes(b"unapproved cache")
            with self.assertRaisesRegex(ValueError, "NVARC index/worktree is dirty"):
                nvarc_source.verify(source, manifest)

    def test_bundle_rebuilds_recursive_source_offline_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, manifest = source_fixture(root)
            bundle = root / "bundle"
            bundle_argument = Path(os.path.relpath(bundle, Path.cwd()))
            nvarc_source.export_bundle(source, manifest, bundle_argument)
            rebuilt = root / "rebuilt"
            nvarc_source.import_bundle(rebuilt, manifest, bundle_argument)
            self.assertTrue(nvarc_source.verify(rebuilt, manifest)["source_ready"])
            self.assertEqual(manifest["git"]["nested"]["commit"],
                             git(rebuilt / "NVARC/external/child/editor", "rev-parse", "HEAD"))
            notebook = bundle / "notebooks/notebook-000.ipynb"
            correct_notebook = notebook.read_bytes()
            notebook.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "source bundle member differs"):
                nvarc_source.import_bundle(root / "rejected", manifest, bundle)
            self.assertFalse((root / "rejected").exists())
            notebook.write_bytes(correct_notebook)
            (bundle / "NVARC/other.py").write_text("OTHER = 99\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source bundle member differs"):
                nvarc_source.import_bundle(root / "rejected-source", manifest, bundle)
            self.assertFalse((root / "rejected-source").exists())

    def test_valid_cache_avoids_current_api_and_changed_current_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            source, manifest = source_fixture(Path(temp))
            with mock.patch.object(nvarc_source, "fetch_current_notebook",
                                   side_effect=AssertionError("network used")):
                nvarc_source.materialize(source, manifest)
            missing = source / manifest["notebooks"]["qwen"]["path"]
            missing.unlink()
            with mock.patch.object(nvarc_source, "fetch_current_notebook",
                                   return_value=(11, b"new version")) as fetch:
                with self.assertRaisesRegex(ValueError, "current version 11 differs"):
                    nvarc_source.materialize(source, manifest)
            self.assertEqual(1, fetch.call_count)
            self.assertFalse(missing.exists())

    def test_interrupted_and_hash_mismatched_download_never_promote(self):
        with tempfile.TemporaryDirectory() as temp:
            source, manifest = source_fixture(Path(temp))
            info = manifest["notebooks"]["qwen"]
            destination = source / info["path"]
            correct = destination.read_bytes()
            destination.unlink()
            pending = destination.with_suffix(destination.suffix + ".pending")
            pending.write_bytes(correct[:5])
            with mock.patch.object(nvarc_source, "fetch_current_notebook",
                                   side_effect=ConnectionError("interrupted")):
                with self.assertRaisesRegex(ConnectionError, "interrupted"):
                    nvarc_source.materialize(source, manifest)
            self.assertFalse(pending.exists())
            self.assertFalse(destination.exists())
            with mock.patch.object(nvarc_source, "fetch_current_notebook",
                                   return_value=(10, b"wrong")):
                with self.assertRaisesRegex(ValueError, "pulled bytes differ"):
                    nvarc_source.materialize(source, manifest)
            self.assertFalse(pending.exists())
            self.assertFalse(destination.exists())
            write_bytes = Path.write_bytes

            def interrupted_write(path: Path, content: bytes) -> int:
                if path == pending:
                    write_bytes(path, content[:5])
                    raise OSError("partial write")
                return write_bytes(path, content)

            with mock.patch.object(nvarc_source, "fetch_current_notebook",
                                   return_value=(10, correct)):
                with mock.patch.object(Path, "write_bytes", new=interrupted_write):
                    with self.assertRaisesRegex(OSError, "partial write"):
                        nvarc_source.materialize(source, manifest)
            self.assertFalse(pending.exists())
            self.assertFalse(destination.exists())
            with mock.patch.object(nvarc_source, "fetch_current_notebook",
                                   return_value=(10, correct)):
                nvarc_source.materialize(source, manifest)
            self.assertEqual(hashlib.sha256(correct).hexdigest(), nvarc_source.sha256(destination))


if __name__ == "__main__":
    unittest.main()

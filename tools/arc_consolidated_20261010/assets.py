"""Verify immutable trusted compiler/interpreter bytes before importing them."""
from __future__ import annotations

import hashlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parent
PINS = {
    "arc_bounded_v2": "9f210e97ddea7f98358ce8d3551310fe1411d57db27c21d7d80f705ce5d41ab7",
    "arc_typed_ir": "8802c4d8e36f2a43acac1abec5a7c2a5b913461cf9f51f7bc7a3eb274ef72ff9",
}
ENGINEERING_IDS = ("68bc2e87", "fafffa47", "33067df9", "996ec1f3",
                   "66e6c45b", "c444b776", "7ec998c9", "b25e450b")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _asset_path(path):
    path = Path(path)
    if ".." in path.parts:
        raise ValueError("parent traversal in asset path")
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
           for p in (path, *path.parents)):
        raise ValueError("symlink/junction asset path")
    return path


def _regular_bytes(path):
    path = _asset_path(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("missing regular asset: " + str(path))
    return path.read_bytes()


def checked_bytes(path, expected):
    path = Path(path)
    raw = _regular_bytes(path)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("immutable asset hash mismatch: " + path.name)
    return raw


class _VerifiedLoader(importlib.abc.Loader):
    def __init__(self, raw, path):
        self.raw, self.path = raw, path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        # Only pinned trusted repository modules reach this loader. Generated
        # model programs are AST data and never reach Python compile/exec.
        exec(compile(self.raw, str(self.path), "exec"), module.__dict__)


def load_legacy(name):
    if name not in PINS:
        raise ValueError("unsupported legacy asset")
    path = ROOT / "legacy" / (name + ".py")
    raw = checked_bytes(path, PINS[name])
    key = "_irisx_consolidated_pinned_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_loader(key, _VerifiedLoader(raw, path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(key, None)
            raise
    return sys.modules[key]


def load_demos():
    from .model_provider import validate_demos_task
    manifest = json.loads((ROOT / "data" / "provenance.json").read_bytes())
    raw = checked_bytes(ROOT / "data" / "engineering-demos.json", manifest["demos_sha256"])
    tasks = json.loads(raw)
    if type(tasks) is not list or tuple(t.get("task_id") for t in tasks) != ENGINEERING_IDS:
        raise ValueError("fixed exposed task denominator differs")
    return [validate_demos_task(task) for task in tasks]


def _source_identity(root):
    root = _asset_path(root)
    for directory in (root, root / "legacy", root / "data"):
        if not _asset_path(directory).is_dir():
            raise ValueError("missing source directory: " + str(directory))
    for name, expected in PINS.items():
        checked_bytes(root / "legacy" / (name + ".py"), expected)
    paths = sorted(root.glob("*.py")) + sorted((root / "legacy").glob("*.py"))
    paths += sorted((root / "data").glob("*.json"))
    return {p.relative_to(root).as_posix(): hashlib.sha256(_regular_bytes(p)).hexdigest()
            for p in paths if p.name != "build_notebook.py"}


def source_identity():
    """Bind executable package, frozen data, vendor bytes; exclude output/tests."""
    return _source_identity(ROOT)


def executable_identity(package_root=None):
    """Hash the complete portable overlay with checkout-relative POSIX keys.

    This inventory matches build_notebook.collect_sources without importing the
    builder, which is absent from the portable runtime. Both frozen interpreter
    files and the two G4 helper copies must retain their approved exact bytes.
    No model/backend is constructed or loaded by this source-only inspection.
    """
    from .model_provider import G4Backend

    root = ROOT if package_root is None else Path(package_root)
    package = _source_identity(root)
    if not {"__init__.py", "runner.py"}.issubset(package):
        raise ValueError("executable package entrypoints are missing")
    pins = dict(G4Backend.SOURCE_PINS)
    if set(pins) != {"arc_next_models.py", "arc_next_index_repair.py"}:
        raise ValueError("G4 helper source inventory differs")
    files = {"tools/arc_consolidated_20261010/" + name: value
             for name, value in package.items()}
    for name, expected in pins.items():
        raw = checked_bytes(root.parent / name, expected)
        files["tools/" + name] = hashlib.sha256(raw).hexdigest()
    files["tools/__init__.py"] = hashlib.sha256(
        _regular_bytes(root.parent / "__init__.py")).hexdigest()
    return dict(sorted(files.items()))

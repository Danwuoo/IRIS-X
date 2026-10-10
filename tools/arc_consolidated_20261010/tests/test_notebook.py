"""Notebook bootstrap tests; active paths use an explicitly synthetic runner.

No runtime8 acceptance, model/backend, training or GPU execution occurs here.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from tools.arc_consolidated_20261010 import assets
from tools.arc_consolidated_20261010 import build_notebook as b
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory


MOCK_RUNNER = '''"""Synthetic notebook boot test only; no verifier/model acceptance."""
def run(output_root, **kwargs):
    import json
    from pathlib import Path
    path = Path(output_root)
    path.mkdir(parents=True, exist_ok=True)
    result = {'synthetic_test_only': True, 'arguments': kwargs,
              'source_origin': __file__, 'archive': 'MOCK-NO-REAL-ARCHIVE'}
    (path / 'mock-runner.json').write_text(json.dumps(result), encoding='utf-8')
    return result
'''

SUBPROCESS = r'''
import importlib.abc
import json
from pathlib import Path
import sys

class RejectModelImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'transformers', 'tokenizers'} or fullname in {
                'tools.arc_next_models', 'tools.arc_next_index_repair'}:
            raise AssertionError('model/backend import forbidden in notebook CPU test: ' + fullname)

sys.meta_path.insert(0, RejectModelImports())
spec = json.loads(sys.stdin.read())
exec(spec.get('prelude', ''), globals())
namespace = {'__name__': '__main__'}
error = None
try:
    for _ in range(spec.get('repeat', 1)):
        for cell in spec['notebook']['cells']:
            if cell['cell_type'] == 'code':
                exec(compile(''.join(cell['source']), '<trusted-notebook-test>', 'exec'), namespace)
                if cell['id'] == 'consolidated-config':
                    namespace.update(spec.get('overrides', {}))
                if cell['id'] == 'consolidated-payload':
                    exec(spec.get('after_payload', ''), namespace)
except Exception as exc:
    error = type(exc).__name__ + ': ' + str(exc)
state = {'error': error, 'result': namespace.get('RESULT'),
         'files': sorted(str(p.relative_to(Path.cwd())) for p in Path.cwd().rglob('*')),
         'tools_loaded': sorted(x for x in sys.modules if x == 'tools' or x.startswith('tools.')),
         'torch_loaded': 'torch' in sys.modules,
         'bytecode_setting': sys.dont_write_bytecode}
print('TEST_STATE=' + json.dumps(state, ensure_ascii=True, sort_keys=True))
'''


class NotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = b.collect_sources(require_runner=False)
        cls.mock_files = {**cls.files, b.PREFIX + "runner.py": MOCK_RUNNER}
        cls.notebook = b.make_notebook(cls.mock_files)

    def execute(self, root, *, notebook=None, overrides=None, prelude="", after_payload="", repeat=1):
        spec = {"notebook": self.notebook if notebook is None else notebook,
                "overrides": overrides or {}, "prelude": prelude,
                "after_payload": after_payload, "repeat": repeat}
        completed = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", SUBPROCESS],
                                   input=json.dumps(spec), text=True, encoding="utf-8",
                                   cwd=root, capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        states = [line[len("TEST_STATE="):] for line in completed.stdout.splitlines()
                  if line.startswith("TEST_STATE=")]
        self.assertEqual(len(states), 1, completed.stdout + completed.stderr)
        return json.loads(states[0])

    def test_default_all_cells_inert_no_writes_or_backend_imports(self):
        with TemporaryDirectory() as root:
            state = self.execute(root)
            self.assertIsNone(state["error"])
            self.assertEqual(state["files"], [])
            self.assertEqual(state["tools_loaded"], [])
            self.assertFalse(state["torch_loaded"])
            self.assertIsNone(state["result"])

    def test_active_mock_installs_exact_bytes_and_passes_bounded_config(self):
        with TemporaryDirectory() as root:
            state = self.execute(root, overrides={"MANUAL_START": True})
            self.assertIsNone(state["error"])
            self.assertTrue(state["result"]["synthetic_test_only"])
            args = state["result"]["arguments"]
            self.assertFalse(args["enable_model"])
            self.assertEqual(args["profile"], "SMOKE")
            self.assertGreaterEqual(args["bootstrap_seconds"], 0)
            self.assertEqual(args["model_config"], {"input_root":"/kaggle/input", "explicit_roots":{}})
            self.assertFalse(state["torch_loaded"])
            self.assertFalse(any("__pycache__" in name for name in state["files"]))
            source = Path(root) / ".irisx-consolidated-source" / self.notebook["metadata"]["irisx_bundle_sha256"]
            for name, text in self.mock_files.items():
                self.assertEqual((source / name).read_bytes(), text.encode("utf-8"))

    def test_same_source_rerun_uses_existing_bytes_without_pyc(self):
        with TemporaryDirectory() as root:
            state = self.execute(root, overrides={"MANUAL_START": True}, repeat=2)
            self.assertIsNone(state["error"])
            self.assertTrue(state["result"]["synthetic_test_only"])
            self.assertFalse(any("__pycache__" in name for name in state["files"]))

    def test_auto_dataset_config_forwarded_without_mount_access(self):
        # A real bootstrap must occur behind the runner's FULL/model gate.
        # This synthetic notebook check only attests that configuration and
        # source installation do not touch any model Dataset root.
        prelude = """\
_original_stat = Path.stat
_original_scandir = __import__('os').scandir
def _mount_guard(value):
    if str(value).startswith(('/kaggle/input', '/explicit/no-scan')):
        raise AssertionError('Dataset inspection before model gate')
def _guarded_stat(self, *args, **kwargs):
    _mount_guard(self)
    return _original_stat(self, *args, **kwargs)
def _guarded_scandir(value):
    _mount_guard(value)
    return _original_scandir(value)
Path.stat = _guarded_stat
__import__('os').scandir = _guarded_scandir
"""
        config = {"input_root":"/kaggle/input", "explicit_roots":{"model":"/explicit/no-scan/model", "runtime":None}}
        with TemporaryDirectory() as root:
            state = self.execute(root, overrides={"MANUAL_START":True, "MODEL_CONFIG":config}, prelude=prelude)
            self.assertIsNone(state["error"])
            self.assertEqual(state["result"]["arguments"]["model_config"],config)
            self.assertFalse(state["torch_loaded"])
            self.assertFalse(any("offline_bootstrap" in name or "arc_next_offline" in name
                                 for name in state["tools_loaded"]))

    def test_invalid_dataset_role_and_legacy_path_config_rejected_before_writes(self):
        invalid = [
            {"input_root":"/kaggle/input", "explicit_roots":{"unknown":"/assets"}},
            {"input_root":"/kaggle/input", "explicit_roots":[]},
            {"input_root":"relative/input", "explicit_roots":{}},
            {"input_root":"/kaggle/../input", "explicit_roots":{}},
            {"input_root":"/kaggle\\input", "explicit_roots":{}},
            {"input_root":True, "explicit_roots":{}},
            {"input_root":"/kaggle/input", "explicit_roots":{"model":True}},
            {"input_root":"/kaggle/input", "explicit_roots":{"model":"relative/model"}},
            {"model_path":None, "manifest_path":None, "environment_lock_path":None,
             "environment_sha256":None, "runtime_manifest_path":None},
        ]
        for config in invalid:
            with self.subTest(config=config), TemporaryDirectory() as root:
                state = self.execute(root, overrides={"MANUAL_START":True, "MODEL_CONFIG":config})
                self.assertIsNotNone(state["error"])
                self.assertEqual(state["files"],[])

    def test_corrupt_payload_rejected_before_any_source_write(self):
        with TemporaryDirectory() as root:
            state = self.execute(root, overrides={"MANUAL_START": True},
                                 after_payload="PACKED_SOURCE_SHA256 = '0' * 64")
            self.assertIn("compressed source hash differs", state["error"])
            self.assertEqual(state["files"], [])

    def test_invalid_switch_profile_and_synthetic_backend_config_rejected(self):
        settings = ({"MANUAL_START": 1}, {"MANUAL_START": True, "ENABLE_MODEL": 1},
                    {"MANUAL_START": True, "PROFILE": "UNLIMITED"},
                    {"MANUAL_START": True, "MODEL_CONFIG": {"synthetic_backend": True}},
                    {"MANUAL_START": True, "SESSION_SECONDS": float("inf")})
        for override in settings:
            with self.subTest(settings=override), TemporaryDirectory() as root:
                state = self.execute(root, overrides=override)
                self.assertIsNotNone(state["error"])
                self.assertEqual(state["files"], [])

    def test_session_allowance_separate_from_coverage_and_allows_full_7200(self):
        # The mock checks argument transfer only, not elapsed work or remaining
        # durable ledger budget. Explicit values above profile defaults are
        # permitted by the real runner, subject to the fixed total wall budget.
        for profile, seconds in (("SMOKE", 600), ("FULL", 7200), ("FULL", 8000), ("FULL", 14400)):
            with self.subTest(profile=profile, seconds=seconds), TemporaryDirectory() as root:
                state = self.execute(root, overrides={"MANUAL_START": True, "PROFILE": profile,
                                                      "SESSION_SECONDS": seconds})
                self.assertIsNone(state["error"])
                self.assertEqual(state["result"]["arguments"]["session_seconds"], seconds)
                self.assertEqual(state["result"]["arguments"]["profile"], profile)
                self.assertFalse(state["result"]["arguments"]["enable_model"])

    def test_out_of_bound_session_allowance_rejected_before_writes(self):
        for seconds in (True, 0, 65, -1, 14401, float("inf"), float("nan")):
            with self.subTest(seconds=seconds), TemporaryDirectory() as root:
                state = self.execute(root, overrides={"MANUAL_START": True, "PROFILE": "FULL",
                                                      "SESSION_SECONDS": seconds})
                self.assertIn("Session allowance", state["error"])
                self.assertEqual(state["files"], [])

    def test_conflicting_imported_tools_refused_without_writes(self):
        prelude = "import types\nsys.modules['tools'] = types.ModuleType('tools')\nsys.modules['tools'].__file__ = '/other/tools/__init__.py'"
        with TemporaryDirectory() as root:
            state = self.execute(root, overrides={"MANUAL_START": True}, prelude=prelude)
            self.assertIn("Conflicting imported tools path", state["error"])
            self.assertEqual(state["files"], [])

    def test_existing_different_source_never_overwritten(self):
        with TemporaryDirectory() as root:
            source = Path(root) / ".irisx-consolidated-source" / self.notebook["metadata"]["irisx_bundle_sha256"]
            target = source / "tools/__init__.py"
            target.parent.mkdir(parents=True)
            target.write_text("owner change\n", encoding="utf-8")
            state = self.execute(root, overrides={"MANUAL_START": True})
            self.assertIn("Existing source differs", state["error"])
            self.assertEqual(target.read_text(encoding="utf-8"), "owner change\n")
            self.assertFalse((Path(root) / "irisx-consolidated-20261010-run001").exists())

    def test_extra_file_in_closed_source_tree_refused(self):
        with TemporaryDirectory() as root:
            source = Path(root) / ".irisx-consolidated-source" / self.notebook["metadata"]["irisx_bundle_sha256"]
            source.mkdir(parents=True)
            (source / "unbound.py").write_text("pass\n", encoding="utf-8")
            state = self.execute(root, overrides={"MANUAL_START": True})
            self.assertIn("Existing source differs", state["error"])
            self.assertFalse((source / "tools").exists())

    def test_output_cannot_be_inside_source_cache_identity(self):
        source = ".irisx-consolidated-source/" + self.notebook["metadata"]["irisx_bundle_sha256"]
        with TemporaryDirectory() as root:
            state = self.execute(root, overrides={"MANUAL_START": True, "OUTPUT_ROOT": source + "/run"})
            self.assertIn("trees must be separate", state["error"])
            self.assertEqual(state["files"], [])

    def test_real_symlink_source_parent_refused_where_supported(self):
        with TemporaryDirectory() as root:
            target = Path(root) / "existing-target"
            target.mkdir()
            link = Path(root) / "linked-source"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest("host does not permit test symlinks: " + str(exc))
            state = self.execute(root, overrides={"MANUAL_START": True, "SOURCE_PARENT": "linked-source"})
            self.assertIn("symlink or junction forbidden", state["error"])
            self.assertEqual(list(target.iterdir()), [])

    def test_unsafe_payload_names_rejected(self):
        for name in ("../escape.py", "/absolute.py", "tools/../escape.py", "tools\\escape.py",
                     "tools/C:escape.py", "tools//bad.py", "tools/./bad.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                b.make_notebook({name: "pass\n"})

    def test_source_collection_matches_runtime_identity_and_backend_pins(self):
        files = b.collect_sources(require_runner=False)
        package_hashes = {name[len(b.PREFIX):]: b.sha(value.encode("utf-8"))
                          for name, value in files.items() if name.startswith(b.PREFIX)}
        self.assertEqual(package_hashes, assets.source_identity())
        self.assertFalse(any("/tests/" in name or "build_notebook.py" in name for name in files))
        for name, expected in b.BACKEND_PINS.items():
            self.assertEqual(b.sha(files["tools/" + name].encode("utf-8")), expected)

    def test_builder_deterministic_and_notebook_flags_inert(self):
        first = b.make_notebook(self.files)
        second = b.make_notebook(dict(reversed(list(self.files.items()))))
        self.assertEqual(first, second)
        self.assertFalse(first["metadata"]["irisx_manual_start"])
        self.assertFalse(first["metadata"]["irisx_enable_model"])
        self.assertFalse(first["metadata"]["irisx_gpu_executed"])
        self.assertFalse(first["metadata"]["irisx_publication_performed"])
        self.assertEqual(first["metadata"]["irisx_default_profile"], "SMOKE")
        for cell in first["cells"]:
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])

    def test_guide_is_readable_and_describes_v2_without_acceptance_claims(self):
        self.assertNotIn("???",b.GUIDE)
        self.assertNotIn("\ufffd",b.GUIDE)
        for phrase in ("5,965", "47,848", "52,536", "10,507,200,000",
                       "persistent model-owner", "CP312", "legal wrong-program",
                       "original positive demo targets unchanged", "four", "not GPU-accepted"):
            self.assertIn(phrase,b.GUIDE)
        for stale in ("6,225", "49,928", "54,616", "runtime_manifest_path", "environment_lock_path"):
            self.assertNotIn(stale,b.GUIDE + b.CONFIG)


if __name__ == "__main__":
    unittest.main()

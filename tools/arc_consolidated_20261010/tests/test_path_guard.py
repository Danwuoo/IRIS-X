"""Pre-write isolation regressions; synthetic paths only, no model assets."""
import builtins
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.arc_consolidated_20261010 import path_guard as guard, runner
from tools.arc_consolidated_20261010.tests import test_notebook as notebook_tests


class PathGuardTests(unittest.TestCase):
    def test_all_roots_reject_equal_descendant_and_ancestor_without_stat(self):
        for name in ("source cache parent", "source", "output", "environment"):
            for path in ("/immutable/input", "/immutable/input/child", "/immutable"):
                for role in (None, *sorted(guard.ROLES)):
                    config = ({"input_root": "/immutable/input"} if role is None else
                              {"explicit_roots": {role: "/immutable/input"}})
                    with self.subTest(name=name, path=path, role=role), \
                         patch.object(Path, "stat", side_effect=AssertionError("stat before lexical rejection")), \
                         patch.object(os, "scandir", side_effect=AssertionError("scan")), \
                         self.assertRaisesRegex(ValueError, "overlaps declared immutable input"):
                        guard.guard_paths(config, {name: path})

    @unittest.skipUnless(os.name == "posix", "POSIX double-slash alias semantics")
    def test_normalized_aliases_overlap_but_prefix_siblings_do_not(self):
        for inputs, output in (("/immutable//input/./", "/immutable/input/child"),
                               ("//immutable/input", "/immutable/input"),
                               ("/immutable/input", "//immutable/input/./child")):
            with self.subTest(inputs=inputs, output=output), self.assertRaisesRegex(ValueError, "overlaps"):
                guard.guard_paths({"input_root": inputs}, {"output": output}, check_links=False)
        with patch.object(Path, "stat", side_effect=AssertionError("pure planning stat")), \
             patch.object(Path, "open", side_effect=AssertionError("pure planning open")):
            paths = guard.guard_paths({"input_root": "/immutable/input"},
                                      {"output": "/immutable/input-other"}, check_links=False)
        self.assertEqual(paths["output"], guard.normalized_path("/immutable/input-other"))

    def test_relative_output_alias_uses_cwd_without_resolving_inputs(self):
        declared = str(Path.cwd()).replace("\\", "/") + "/immutable"
        if os.name == "nt":
            self.skipTest("Dataset declarations are Linux absolute paths")
        with patch.object(Path, "resolve", side_effect=AssertionError("realpath forbidden")), \
             patch.object(Path, "stat", side_effect=AssertionError("stat forbidden")), \
             self.assertRaisesRegex(ValueError, "overlaps"):
            guard.guard_paths({"input_root": declared}, {"output": "./immutable//child"})

    def test_traversal_and_invalid_paths_rejected_before_inspection(self):
        for path in ("safe/../input", "safe/..\\input", "", True, "bad\x00path", "/" + "a" * 4096):
            with self.subTest(path=path), \
                 patch.object(Path, "stat", side_effect=AssertionError("stat")), self.assertRaises(ValueError):
                guard.guard_paths({}, {"source": path})

    @unittest.skipUnless(os.name == "posix", "synthetic Dataset roots use Linux paths")
    def test_root_first_link_checks_reject_alias_without_reading_its_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "immutable"
            target.mkdir()
            link = root / "alias"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest("host does not permit symlinks: " + str(exc))
            original = Path.stat
            def guarded_stat(path, *args, **kwargs):
                if str(path).startswith(str(link) + os.sep) or path == target:
                    raise AssertionError("stat traversed a link or inspected an input")
                return original(path, *args, **kwargs)
            with patch.object(Path, "stat", guarded_stat), self.assertRaisesRegex(ValueError, "symlink"):
                guard.guard_paths({"input_root": str(target)}, {"environment": link / "new"})
            self.assertEqual(list(target.iterdir()), [])


class DirectRunnerInputGuardTests(unittest.TestCase):
    def reject_before_demos_or_filesystem(self, output, config):
        with patch.object(runner.assets, "load_demos", side_effect=AssertionError("demos loaded")), \
             patch.object(runner.evidence, "safe_root", side_effect=AssertionError("write")), \
             patch.object(Path, "stat", side_effect=AssertionError("stat before rejection")), \
             self.assertRaisesRegex(ValueError, "overlaps declared immutable input"):
            runner.run(output, manual_start=True, model_config=config)

    def test_direct_output_equal_descendant_ancestor_and_all_explicit_roles(self):
        for output in ("/immutable/input", "/immutable/input/run", "/immutable"):
            self.reject_before_demos_or_filesystem(output, {"input_root": "/immutable/input"})
            for role in guard.ROLES:
                self.reject_before_demos_or_filesystem(output, {"explicit_roots": {role: "/immutable/input"}})

    def test_direct_source_equal_descendant_ancestor_rejected(self):
        if os.name == "nt":
            self.skipTest("Dataset declarations are Linux absolute paths")
        source = Path(runner.__file__).absolute().parents[2]
        for inputs in (source, source / "declared-input", source.parent):
            self.reject_before_demos_or_filesystem("/separate-output/run", {"input_root": str(inputs)})

    def test_derived_environment_guard_runs_even_when_model_disabled(self):
        for immutable in ("/scratch/run-environment", "/scratch/run-environment/input"):
            for role in (None, *sorted(guard.ROLES)):
                config = ({"input_root": immutable} if role is None else {"explicit_roots": {role: immutable}})
                self.reject_before_demos_or_filesystem("/scratch/run", config)

    def test_default_and_safe_cpu_configuration_never_inspect_inputs(self):
        original_stat, original_scandir, original_open = Path.stat, os.scandir, builtins.open
        def deny_input(value):
            if str(value).replace("\\", "/").startswith(("/kaggle/input", "/explicit/no-scan")):
                raise AssertionError("Dataset inspected in CPU mode")
        def stat(path, *args, **kwargs):
            deny_input(path)
            return original_stat(path, *args, **kwargs)
        def scandir(path):
            deny_input(path)
            return original_scandir(path)
        def opened(path, *args, **kwargs):
            deny_input(path)
            return original_open(path, *args, **kwargs)
        class ReachedDemos(Exception):
            pass
        for config in (None, {"input_root": "/kaggle/input", "explicit_roots": {"model": "/explicit/no-scan/model"}}):
            with tempfile.TemporaryDirectory() as temporary, \
                 patch.object(Path, "stat", stat), patch.object(os, "scandir", scandir), \
                 patch.object(builtins, "open", opened), \
                 patch.object(runner.offline_bootstrap, "plan_config", side_effect=AssertionError("model planning in CPU mode")), \
                 patch.object(runner.assets, "load_demos", side_effect=ReachedDemos), \
                 self.assertRaises(ReachedDemos):
                runner.run(Path(temporary) / "run", manual_start=True, model_config=config)

    def test_disabled_is_inert_even_with_unsafe_paths(self):
        with patch.object(runner, "guard_paths", side_effect=AssertionError("inactive path inspection")), \
             patch.object(Path, "stat", side_effect=AssertionError("inactive stat")), \
             patch.object(runner.assets, "load_demos", side_effect=AssertionError("inactive demos")):
            result = runner.run("/kaggle/input/../input", model_config={"input_root": "/"})
        self.assertEqual(result["status"], "INACTIVE")

    @unittest.skipUnless(os.name == "posix", "synthetic Dataset roots use Linux paths")
    def test_direct_output_and_environment_links_rejected_before_any_write(self):
        for target_name in ("run", "run-environment"):
            with self.subTest(target_name=target_name), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                immutable = base / "immutable"
                immutable.mkdir()
                link = base / target_name
                try:
                    link.symlink_to(immutable, target_is_directory=True)
                except OSError as exc:
                    self.skipTest("host does not permit symlinks: " + str(exc))
                with patch.object(runner.assets, "load_demos", side_effect=AssertionError("demos")), \
                     patch.object(runner.evidence, "safe_root", side_effect=AssertionError("write")), \
                     self.assertRaisesRegex(ValueError, "symlink"):
                    runner.run(base / "run", manual_start=True, model_config={"input_root": str(immutable)})
                self.assertEqual(list(immutable.iterdir()), [])
                self.assertFalse((base / ".irisx-consolidated-source").exists())

    def test_direct_output_traversal_rejected_before_demos_or_writes(self):
        with patch.object(runner.assets, "load_demos", side_effect=AssertionError("demos")), \
             patch.object(Path, "stat", side_effect=AssertionError("stat")), \
             self.assertRaisesRegex(ValueError, "traversal"):
            runner.run("safe/../run", manual_start=True)


@unittest.skipUnless(os.name == "posix", "synthetic Dataset roots use Linux paths")
class NotebookInputGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        notebook_tests.NotebookTests.setUpClass()
        cls.helper = notebook_tests.NotebookTests()

    def test_source_parent_output_and_environment_rejected_without_any_write(self):
        for role in (None, *sorted(guard.ROLES)):
            for target in ("SOURCE_PARENT", "OUTPUT_ROOT", "environment"):
                for relation in ("equal", "descendant", "ancestor"):
                    with self.subTest(role=role, target=target, relation=relation), tempfile.TemporaryDirectory() as temporary:
                        base = Path(temporary)
                        candidate = base / "candidate"
                        immutable = candidate
                        if relation == "descendant":
                            immutable = base
                        elif relation == "ancestor":
                            immutable = candidate / "input"
                        settings = {"MANUAL_START": True}
                        if target == "environment":
                            # Environment is derived from OUTPUT_ROOT, even for CPU mode.
                            candidate = base / "run-environment"
                            immutable = candidate if relation == "equal" else (
                                base if relation == "descendant" else candidate / "input")
                            settings["OUTPUT_ROOT"] = str(base / "run")
                        else:
                            settings[target] = str(candidate)
                        config = {"input_root": str(immutable), "explicit_roots": {}} if role is None else {
                            "input_root": "/kaggle/input", "explicit_roots": {role: str(immutable)}}
                        settings["MODEL_CONFIG"] = config
                        # For every failure, forbid all stat calls; lexical rejection
                        # must precede existing source/output link checks as well.
                        prelude = """\
_original_stat = Path.stat
def _no_notebook_stat(path, *args, **kwargs):
    frame = sys._getframe()
    while frame is not None:
        if frame.f_code.co_filename in {'<trusted-notebook-test>', '<trusted-path-guard>'}:
            raise AssertionError('stat before rejection')
        frame = frame.f_back
    return _original_stat(path, *args, **kwargs)
Path.stat = _no_notebook_stat
"""
                        state = self.helper.execute(temporary, overrides=settings, prelude=prelude)
                        self.assertIn("overlaps declared immutable input", state["error"])
                        self.assertEqual(state["files"], [])
                        self.assertEqual(state["tools_loaded"], [])
                        self.assertFalse(state["torch_loaded"])

    def test_source_identity_itself_is_declared_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / ".irisx-consolidated-source" / self.helper.notebook["metadata"]["irisx_bundle_sha256"]
            state = self.helper.execute(temporary, overrides={"MANUAL_START": True,
                "MODEL_CONFIG": {"input_root": str(source), "explicit_roots": {}}})
            self.assertIn("overlaps declared immutable input", state["error"])
            self.assertEqual(state["files"], [])

    def test_traversal_and_lexical_aliases_rejected_before_writes(self):
        for setting in ("SOURCE_PARENT", "OUTPUT_ROOT"):
            for value in ("safe/../unsafe", "//kaggle/input/./run", "/kaggle//input/run"):
                with self.subTest(setting=setting, value=value), tempfile.TemporaryDirectory() as temporary:
                    state = self.helper.execute(temporary, overrides={"MANUAL_START": True, setting: value})
                    self.assertIsNotNone(state["error"])
                    self.assertEqual(state["files"], [])

    def test_environment_symlink_to_input_is_rejected_before_source_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable = root / "immutable"
            immutable.mkdir()
            link = root / "run-environment"
            try:
                link.symlink_to(immutable, target_is_directory=True)
            except OSError as exc:
                self.skipTest("host does not permit symlinks: " + str(exc))
            state = self.helper.execute(temporary, overrides={"MANUAL_START": True, "OUTPUT_ROOT": str(root / "run"),
                "MODEL_CONFIG": {"input_root": str(immutable), "explicit_roots": {}}})
            self.assertIn("symlink or junction forbidden", state["error"])
            self.assertEqual(list(immutable.iterdir()), [])
            self.assertFalse((root / ".irisx-consolidated-source").exists())
            self.assertFalse((root / "run").exists())

    def test_disabled_unsafe_configuration_performs_zero_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = self.helper.execute(temporary, overrides={"SOURCE_PARENT": "/kaggle/input/source",
                "OUTPUT_ROOT": "/kaggle/input/output", "MODEL_CONFIG": {"input_root": "/", "explicit_roots": {}}})
            self.assertIsNone(state["error"])
            self.assertEqual(state["files"], [])
            self.assertEqual(state["tools_loaded"], [])

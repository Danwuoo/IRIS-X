"""Fresh constant-only subprocesses prove fixed-seed interpreter initialization."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / "pyproject.toml").is_file() and (path / "tools").is_dir())
sys.path.insert(0, str(ROOT))
from tools import suite_runner as runner


# Values are compared with a fresh reference from this exact executable. No
# Python-version-dependent hash value is baked into the fixtures or assertions.
VALUES = ("IRIS-X seed regression", "constant-only", "hash startup", "", "0", "測試", "repeatable", "source snapshot")
PROBE = """import json, os, site, sys
values = %r
print(json.dumps({
    'hashes': [hash(value) for value in values],
    'flags': {name: getattr(sys.flags, name) for name in (
        'optimize', 'safe_path', 'no_user_site', 'dont_write_bytecode',
        'ignore_environment', 'isolated', 'hash_randomization')},
    'python_environment': {name: value for name, value in os.environ.items()
                           if name.upper().startswith('PYTHON')},
    'path': sys.path,
    'user_site_enabled': site.ENABLE_USER_SITE,
    'executable': sys.executable,
}, ensure_ascii=True))
""" % (VALUES,)


class InterpreterStartupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="irisx-seed-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def launch(self, command, environment, *, cwd=None):
        completed = subprocess.run(command, env=environment, cwd=cwd or self.root,
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="strict", timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def reference(self, optimize):
        # Construct the reference independently of either production helper.
        environment = {key: value for key, value in os.environ.items()
                       if not key.upper().startswith("PYTHON")}
        environment.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, "-P", "-s", "-B"]
        if optimize:
            command.append("-" + "O" * optimize)
        return self.launch([*command, "-c", PROBE], environment)

    def controlled_probe(self, optimize, inherited=None, *, cwd=None, script=None):
        arguments = (str(script),) if script else ("-c", PROBE)
        return self.launch(runner.controlled_python_command(sys.executable, *arguments,
                                                           optimize=optimize),
                           runner.controlled_python_environment(inherited), cwd=cwd)

    def assert_effective(self, data, optimize):
        self.assertEqual(data["flags"], {
            "optimize": optimize, "safe_path": True, "no_user_site": 1,
            "dont_write_bytecode": 1, "ignore_environment": 0, "isolated": 0,
            "hash_randomization": 0,
        })
        self.assertEqual(data["python_environment"], runner.PYTHON_ENVIRONMENT)
        self.assertFalse(data["user_site_enabled"])
        self.assertEqual(Path(data["executable"]).resolve(), Path(sys.executable).resolve())

    def assert_repeatable(self, optimize):
        reference = self.reference(optimize)
        self.assert_effective(reference, optimize)
        children = [self.controlled_probe(optimize) for _ in range(3)]
        for child in children:
            self.assert_effective(child, optimize)
            self.assertEqual(child["hashes"], reference["hashes"])
        self.assertEqual(len({tuple(child["hashes"]) for child in children}), 1)

    def test_environment_removes_all_case_variants_and_only_restores_allowlist(self):
        inherited = {"PYTHONPATH": "poison", "pythonhome": "poison", "PythonHashSeed": "random",
                     "PYTHONUSERBASE": "poison", "PYTHONWARNINGS": "error",
                     "PYTHONSAFEPATH": "", "PYTHONOPTIMIZE": "2", "PYTHONSTARTUP": "poison",
                     "PYTHON_FUTURE_UNKNOWN": "poison", "HF_HUB_OFFLINE": "1", "PLAIN_SETTING": "keep"}
        saved = dict(inherited)
        self.assertEqual(runner.controlled_python_environment(inherited),
                         dict(runner.PYTHON_ENVIRONMENT, HF_HUB_OFFLINE="1", PLAIN_SETTING="keep"))
        self.assertEqual(inherited, saved)

    def test_command_has_effective_isolation_and_requested_optimization(self):
        for optimize in (0, 1, 2):
            with self.subTest(optimize=optimize):
                command = runner.controlled_python_command(sys.executable, "-c", "pass", optimize=optimize)
                self.assertEqual(command[1:4], ["-P", "-s", "-B"])
                self.assertNotIn("-I", command)
                self.assertNotIn("-E", command)
                self.assertEqual(command[4:], (["-" + "O" * optimize] if optimize else []) + ["-c", "pass"])

    def test_default_command_inherits_current_optimization(self):
        self.assertEqual(runner.controlled_python_command(sys.executable, "-c", "pass"),
                         runner.controlled_python_command(sys.executable, "-c", "pass", optimize=sys.flags.optimize))

    def test_invalid_optimization_is_rejected(self):
        for value in (-1, 3, False, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runner.controlled_python_command(sys.executable, "-c", "pass", optimize=value)

    def test_ignore_environment_flags_cannot_disable_seed_in_helper(self):
        for flag in ("-I", "-E"):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "fixed seed"):
                runner.controlled_python_command(sys.executable, flag, "-c", "pass")

    def test_normal_children_match_fresh_same_interpreter_seed_zero_reference(self):
        self.assert_repeatable(0)

    def test_optimized_children_match_fresh_same_interpreter_seed_zero_reference(self):
        self.assert_repeatable(1)

    def test_double_optimized_children_match_fresh_same_interpreter_seed_zero_reference(self):
        self.assert_repeatable(2)

    def test_polluted_python_environment_is_absent_at_fresh_interpreter_startup(self):
        poison = self.root / "poison"
        poison.mkdir()
        marker = poison / "IMPORTED"
        (poison / "sitecustomize.py").write_text(
            "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('poison')\nraise RuntimeError('POISON IMPORT')\n",
            encoding="utf-8")
        inherited = dict(os.environ, PYTHONPATH=str(poison), PYTHONHOME=str(poison / "missing-home"),
                         PYTHONUSERBASE=str(poison), PYTHONHASHSEED="random", PYTHONWARNINGS="error",
                         PYTHONOPTIMIZE="2", PYTHONSAFEPATH="", PYTHONPYCACHEPREFIX=str(poison))
        for optimize in (0, 1):
            with self.subTest(optimize=optimize):
                child = self.controlled_probe(optimize, inherited, cwd=poison)
                self.assert_effective(child, optimize)
                self.assertEqual(child["hashes"], self.reference(optimize)["hashes"])
                self.assertNotIn(str(poison), child["path"])
        self.assertFalse(marker.exists())

    def test_safe_path_omits_current_directory_and_script_directory(self):
        script_directory = self.root / "script-root"
        script_directory.mkdir()
        cwd = self.root / "caller-root"
        cwd.mkdir()
        script = script_directory / "probe.py"
        script.write_text(PROBE, encoding="utf-8")
        for optimize in (0, 1):
            with self.subTest(optimize=optimize):
                child = self.controlled_probe(optimize, cwd=cwd, script=script)
                self.assert_effective(child, optimize)
                self.assertNotIn(str(script_directory), child["path"])
                self.assertNotIn(str(cwd), child["path"])
                self.assertNotIn("", child["path"])
                self.assertFalse((script_directory / "__pycache__").exists())

    def test_report_validation_rejects_claimed_seed_when_effective_flags_disagree(self):
        valid = self.reference(0)
        startup = {key: valid[key] for key in ("flags", "python_environment")}
        self.assertEqual(runner.validate_child_startup(startup, optimize=0), [])
        for flag, value in (("hash_randomization", 1), ("ignore_environment", 1),
                            ("safe_path", False), ("no_user_site", 0), ("dont_write_bytecode", 0)):
            invalid = copy.deepcopy(startup)
            invalid["flags"][flag] = value
            with self.subTest(flag=flag):
                self.assertTrue(runner.validate_child_startup(invalid, optimize=0))
        self.assertTrue(runner.validate_child_startup(startup, optimize=1))
        self.assertTrue(runner.validate_child_startup({"python_environment": runner.PYTHON_ENVIRONMENT}, optimize=0))

    def test_runner_constant_module_uses_same_interpreter_reference_despite_pollution(self):
        repository = self.root / "repository"
        tests = repository / "tests"
        tests.mkdir(parents=True)
        expected = self.reference(sys.flags.optimize)["hashes"]
        source = "import sys, unittest\nclass ConstantSeed(unittest.TestCase):\n    def test_seed(self):\n"
        source += "        self.assertEqual([hash(value) for value in " + repr(VALUES) + "], " + repr(expected) + ")\n"
        source += "        self.assertEqual(sys.flags.hash_randomization, 0)\n"
        (tests / "test_constant.py").write_text(source, encoding="utf-8")
        entry = {"path": "tests/test_constant.py", "workstream": "core", "dependency_class": "stdlib",
                 "suite": "constant", "role": "test", "dependencies": [], "collector": "unittest",
                 "reason": "constant-only startup fixture", "expected_skips": []}
        (tests / "inventory.json").write_text(json.dumps({"format": "irisx.tests.v1",
            "suites": {"constant": {"public": True}}, "entries": [entry]}), encoding="utf-8")
        poison = self.root / "unavailable-python-home"
        with mock.patch.dict(os.environ, {"PYTHONHOME": str(poison), "PYTHONPATH": str(poison),
                                          "PYTHONHASHSEED": "random", "PYTHONOPTIMIZE": "2"}):
            reports = [runner.run_suite(repository, "constant", repository / f".irisx/run-{number}")
                       for number in range(3)]
        for report in reports:
            self.assertEqual(report["status"], "passed", report)
            self.assertEqual(report["tests"], 1)
            self.assertFalse(report["attestable"])
            self.assertIsNone(report["target_commit"])
            self.assertEqual(report["child_python_environment"], runner.PYTHON_ENVIRONMENT)
            self.assertEqual(runner.validate_child_startup(report["modules"][0]["interpreter_startup"]), [])


if __name__ == "__main__":
    unittest.main()

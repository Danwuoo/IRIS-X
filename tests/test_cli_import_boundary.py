"""Fresh-process CLI boundary checks using only synthetic engineering inputs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from distribution_check import ADMISSION_INPUTS, copy_declared  # noqa: E402


SCRIPT = r'''
import contextlib, importlib.abc, io, json, pathlib, sys
source, arguments, block_arc = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3] == "yes"
sys.path.insert(0, source)
def forbidden(name):
    return name == "tools" or name.startswith("tools.") or name.split(".")[0] in {"torch", "transformers", "numpy", "IPython", "huggingface_hub", "kaggle", "peft", "tensorflow"} or (block_arc and (name.startswith("irisx.arc") or name.startswith("irisx.kaggle")))
class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if forbidden(fullname):
            raise AssertionError("forbidden implementation import: " + fullname)
sys.meta_path.insert(0, Blocker())
from irisx import cli
results = []
for argv, expected in arguments:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            actual = cli.main(argv)
        except SystemExit as error:
            actual = error.code
    if actual != expected:
        raise AssertionError((argv, actual, expected, out.getvalue(), err.getvalue()))
    results.append({"args": argv, "exit_code": actual, "stdout": out.getvalue(), "stderr": err.getvalue()})
loaded = sorted(name for name in sys.modules if name.startswith("irisx.arc") or name.startswith("irisx.kaggle"))
if block_arc and loaded:
    raise AssertionError("domain implementations loaded: " + repr(loaded))
print(json.dumps({"results": results, "domain_modules": loaded}))
'''


class CliImportBoundaryTests(unittest.TestCase):
    def run_process(self, arguments: list, optimized: bool, block_arc: bool = True) -> dict:
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["PYTHONHASHSEED"] = "0"
        result = subprocess.run(
            [sys.executable, *( ["-O"] if optimized else []), "-I", "-B", "-c", SCRIPT,
             str(ROOT / "src"), json.dumps(arguments), "yes" if block_arc else "no"],
            cwd=ROOT.parent, env=environment, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_generic_help_and_complete_reference_flow_without_domain_imports(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                copy_declared(ROOT, root / "admission", ADMISSION_INPUTS)
                arguments = [
                    [["--help"], 0], [["arc-agi-2", "--help"], 0],
                    [["fixture", "prepare", "--output", str(root / "fixture")], 0],
                    [["spec", "validate", str(root / "fixture/specification.json")], 0],
                    [["trial", "validate", str(root / "fixture/trial.json")], 0],
                    [["trial", "run", "--trial", str(root / "fixture/trial.json"), "--output", str(root / "run")], 0],
                    [["package", "build", "--run", str(root / "run"), "--output", str(root / "package")], 0],
                    [["package", "verify", str(root / "package")], 0],
                    [["admission", "validate", str(root / "admission/trials/p2-admission/admission.json")], 0],
                    [["package", "verify", str(root / "missing")], 2],
                ]
                report = self.run_process(arguments, optimized)
                self.assertEqual(report["domain_modules"], [])
                self.assertIn("arc-agi-2", report["results"][0]["stdout"])
                self.assertIn("admission_blocked", report["results"][-2]["stdout"])
                self.assertIn("irisx: error:", report["results"][-1]["stderr"])

    def test_selected_arc_command_loads_legacy_and_retains_missing_path_error(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized), tempfile.TemporaryDirectory() as temporary:
                report = self.run_process([[["arc-agi-2", "source", "validate", str(Path(temporary) / "missing")], 2]], optimized, block_arc=False)
                self.assertIn("irisx.arc_agi2", report["domain_modules"])
                self.assertIn("irisx: error:", report["results"][0]["stderr"])

    def test_legacy_parser_options_and_argument_errors_do_not_load_domain(self):
        arguments = [
            [["arc-agi-2", "result", "benchmark-verify", "--help"], 0],
            [["arc-agi-2", "baseline", "kernel-stage", "--help"], 0],
            [["fixture", "prepare"], 2], [["unknown-command"], 2],
        ]
        for optimized in (False, True):
            report = self.run_process(arguments, optimized)
            self.assertIn("--trial-package", report["results"][0]["stdout"])
            self.assertIn("--dataset-ref", report["results"][1]["stdout"])
            self.assertEqual(report["domain_modules"], [])


if __name__ == "__main__":
    unittest.main()

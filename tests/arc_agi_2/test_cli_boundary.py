"""Compare mutable routing to fixed PR3 source without real domain/provider inputs."""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
PREDECESSOR = "756cd560f8d61256ed35e12c3c3637ec456c6141"
sys.path.insert(0, str(ROOT / "src"))

from irisx import cli  # noqa: E402
from irisx.domains.arc_agi_2 import cli as arc_cli  # noqa: E402


def parser_snapshot(parser: argparse.ArgumentParser) -> dict:
    actions = []
    children = {}
    for action in parser._actions:
        snapshot = {name: getattr(action, name) for name in ("dest", "option_strings", "nargs", "required", "default", "const", "metavar", "help")}
        snapshot["class"] = type(action).__name__
        snapshot["type"] = None if action.type is None else action.type.__name__
        snapshot["choices"] = None if action.choices is None else list(action.choices)
        actions.append(snapshot)
        if isinstance(action, argparse._SubParsersAction):
            children = {name: parser_snapshot(child) for name, child in action.choices.items()}
    return {"prog": parser.prog, "help": parser.format_help(), "usage": parser.format_usage(), "actions": actions, "children": children}


def captured_main(module, argv: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = module.main(argv)
        except SystemExit as error:
            code = error.code
    return code, stdout.getvalue(), stderr.getvalue()


def fake_legacy_modules() -> dict[str, types.ModuleType]:
    contract = lambda digest: types.SimpleNamespace(content_digest=digest)
    definitions = {
        "irisx.arc_agi2": {
            "materialize_source": {"content_digest": "synthetic-source"}, "validate_source": {"content_digest": "synthetic-source"},
            "prepare_trial": contract("synthetic-trial"), "validate_trial_bundle": contract("synthetic-trial"),
        },
        "irisx.arc_package": {"build_arc_package": contract("synthetic-package"), "verify_arc_package": contract("synthetic-package")},
        "irisx.arc_trial_002": {
            "build_outbound_package": "synthetic-outbound2", "import_quarantine": "synthetic-quarantine2",
            "prepare_trial": {"run_identity_digest": "synthetic-run2"}, "validate_trial": {"run_identity_digest": "synthetic-run2"},
            "score_quarantined": {"passed_test_outputs": 1, "total_test_outputs": 2, "score": 0.5},
            "stage_kaggle_kernel": {"id": "synthetic-only-kernel"}, "technical_preflight": {"technical_ready": False},
            "verify_outbound_package": ({}, {}, "synthetic-outbound2"), "verify_result_package": ({}, {}, "synthetic-result2"),
        },
        "irisx.kaggle": {
            "build_outbound_package": "synthetic-outbound", "evaluate_imported_run": {"selection_outcome": "no_promotion", "p2_accepted": False},
            "import_quarantine": "synthetic-quarantine", "materialize_model": {"content_digest": "synthetic-model"},
            "preflight": {"payload": {"technical_ready": False}, "content_digest": "synthetic-preflight"},
            "validate_model_source": {"content_digest": "synthetic-model"},
            "verify_benchmark_result_package": ({}, {}, "synthetic-benchmark"), "verify_outbound_package": ({}, "synthetic-outbound"),
            "verify_result_package": ({}, {}, "synthetic-result"),
        },
    }
    modules = {}
    for name, functions in definitions.items():
        module = types.ModuleType(name)
        module.__synthetic_only__ = True
        for function, value in functions.items():
            setattr(module, function, mock.Mock(name=f"{name}.{function}", return_value=value))
        modules[name] = module
    return modules


def dispatch_cases(root: Path) -> list[tuple[list[str], str, str]]:
    path = lambda name: str(root / name)
    option = lambda name: ["--" + name, path(name)]
    return [
        (["source", "materialize", *option("output")], "irisx.arc_agi2", "materialize_source"),
        (["source", "validate", path("source")], "irisx.arc_agi2", "validate_source"),
        (["model", "materialize", *option("output")], "irisx.kaggle", "materialize_model"),
        (["model", "validate", path("model")], "irisx.kaggle", "validate_model_source"),
        (["trial", "prepare", *option("source"), *option("output")], "irisx.arc_agi2", "prepare_trial"),
        (["trial", "validate", path("trial")], "irisx.arc_agi2", "validate_trial_bundle"),
        (["trial", "outbound-build", *sum((option(name) for name in ("trial", "model-source", "binding", "runtime-wheels", "output")), [])], "irisx.kaggle", "build_outbound_package"),
        (["trial", "outbound-verify", path("outbound")], "irisx.kaggle", "verify_outbound_package"),
        (["trial", "preflight", *sum((option(name) for name in ("trial", "model-source", "trial-package", "binding", "output")), [])], "irisx.kaggle", "preflight"),
        (["result", "verify", *sum((option(name) for name in ("package", "trial-package", "trial")), [])], "irisx.kaggle", "verify_result_package"),
        (["result", "benchmark-verify", *option("package"), *option("trial-package")], "irisx.kaggle", "verify_benchmark_result_package"),
        (["result", "import", *sum((option(name) for name in ("package", "trial-package", "trial", "run-root")), [])], "irisx.kaggle", "import_quarantine"),
        (["result", "evaluate", *option("trial"), *option("run")], "irisx.kaggle", "evaluate_imported_run"),
        (["package", "build", *sum((option(name) for name in ("trial", "source", "run", "model-source", "trial-package", "result-package", "output")), [])], "irisx.arc_package", "build_arc_package"),
        (["package", "verify", path("package")], "irisx.arc_package", "verify_arc_package"),
        (["baseline", "prepare", *option("source"), *option("competition-challenges"), *option("output")], "irisx.arc_trial_002", "prepare_trial"),
        (["baseline", "validate", path("trial")], "irisx.arc_trial_002", "validate_trial"),
        (["baseline", "outbound-build", *sum((option(name) for name in ("trial", "model", "nvarc", "wheels", "output")), [])], "irisx.arc_trial_002", "build_outbound_package"),
        (["baseline", "outbound-verify", path("outbound")], "irisx.arc_trial_002", "verify_outbound_package"),
        (["baseline", "kernel-stage", *option("template"), *option("output"), "--dataset-ref", "synthetic-only/ref", "--outbound-digest", "synthetic-digest"], "irisx.arc_trial_002", "stage_kaggle_kernel"),
        (["baseline", "preflight", *sum((option(name) for name in ("trial", "outbound", "model", "nvarc", "wheels", "competition-challenges", "dataset", "kernel", "output")), []), "--dataset-ref", "synthetic-only/ref"], "irisx.arc_trial_002", "technical_preflight"),
        (["baseline", "result-verify", *option("package"), *option("outbound")], "irisx.arc_trial_002", "verify_result_package"),
        (["baseline", "result-import", *option("package"), *option("outbound"), *option("quarantine")], "irisx.arc_trial_002", "import_quarantine"),
        (["baseline", "result-score", *option("trial"), *option("quarantined"), *option("output")], "irisx.arc_trial_002", "score_quarantined"),
    ]


FRESH_PROCESS = r'''
import contextlib, importlib.abc, io, json, pathlib, sys
sys.path.insert(0, sys.argv[1])
selected, missing = sys.argv[2] == "selected", sys.argv[3]
class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "tools" or fullname.startswith("tools.") or fullname.split(".")[0] in {"torch","transformers","numpy","peft","kaggle","huggingface_hub","tensorflow"} or (not selected and (fullname.startswith("irisx.arc") or fullname.startswith("irisx.kaggle"))):
            raise AssertionError("unexpected runtime import: " + fullname)
sys.meta_path.insert(0, Blocker())
from irisx import cli
commands = [["arc-agi-2","source","validate",missing]] if selected else [["--help"],["arc-agi-2","--help"],["arc-agi-2","trial","outbound-build","--help"],["fixture","--help"],["package","--help"],["admission","--help"]]
results = []
for args in commands:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(args)
        except SystemExit as error:
            code = error.code
    if code != (2 if selected else 0):
        raise AssertionError((args, code, err.getvalue()))
    results.append({"exit_code": code, "stdout": out.getvalue(), "stderr": err.getvalue()})
runtime = sorted(name for name in sys.modules if name.startswith("irisx.arc") or name.startswith("irisx.kaggle"))
if not selected and runtime:
    raise AssertionError(runtime)
print(json.dumps({"results":results,"runtime_modules":runtime,"parser_module_loaded":"irisx.domains.arc_agi_2.cli" in sys.modules}))
'''


class ArcCliBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="irisx-pr3-cli-source-")
        source = subprocess.check_output(["git", "show", f"{PREDECESSOR}:src/irisx/cli.py"], cwd=ROOT)
        target = Path(cls.temporary.name) / "predecessor_cli.py"
        target.write_bytes(source)
        spec = importlib.util.spec_from_file_location("irisx._pr3_predecessor_cli", target)
        cls.predecessor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.predecessor)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_entire_parser_tree_help_options_and_path_conversion_match_pr3(self):
        self.assertEqual(parser_snapshot(cli.build_parser()), parser_snapshot(self.predecessor.build_parser()))
        for text in ("relative/synthetic.json", ".", str(ROOT / "missing-synthetic")):
            self.assertEqual(cli._path(text), self.predecessor._path(text))
        self.assertTrue(all(callable(getattr(cli, name)) for name in ("main", "execute", "build_parser", "_path")))

    def test_argument_failures_and_help_match_pr3_exactly(self):
        arguments = [[], ["not-a-command"], ["arc-agi-2"], ["arc-agi-2", "source"], ["arc-agi-2", "trial", "outbound-build"],
                     ["arc-agi-2", "baseline", "kernel-stage", "--unknown"], ["--help"], ["arc-agi-2", "--help"]]
        for argv in arguments:
            with self.subTest(argv=argv):
                self.assertEqual(captured_main(cli, argv), captured_main(self.predecessor, argv))

    def test_every_arc_dispatch_route_matches_pr3_using_synthetic_module_mocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.predecessor.__file__ = str(ROOT / "src/irisx/cli.py")
            for arguments, module_name, function_name in dispatch_cases(Path(temporary)):
                with self.subTest(arguments=arguments):
                    modules = fake_legacy_modules()
                    namespace = cli.build_parser().parse_args(["arc-agi-2", *arguments])
                    with mock.patch.dict(sys.modules, modules), mock.patch.object(arc_cli, "write_artifact"), mock.patch.object(arc_cli, "write_json"):
                        actual = cli.execute(namespace)
                    actual_calls = {name: {function: method.mock_calls[:] for function, method in vars(module).items() if isinstance(method, mock.Mock)}
                                    for name, module in modules.items()}
                    self.assertEqual(len(getattr(modules[module_name], function_name).mock_calls), 1)
                    if arguments[:2] in (["trial", "outbound-build"], ["baseline", "outbound-build"]):
                        self.assertEqual(getattr(modules[module_name], function_name).call_args.kwargs["repository_root"], ROOT)
                    for module in modules.values():
                        for method in vars(module).values():
                            if isinstance(method, mock.Mock):
                                method.reset_mock()
                    with mock.patch.dict(sys.modules, modules), mock.patch.object(self.predecessor, "write_artifact"), mock.patch.object(self.predecessor, "write_json"):
                        expected = self.predecessor.execute(namespace)
                    expected_calls = {name: {function: method.mock_calls[:] for function, method in vars(module).items() if isinstance(method, mock.Mock)}
                                      for name, module in modules.items()}
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual_calls, expected_calls)

    def test_router_passes_original_repository_root_to_domain_facade(self):
        args = cli.build_parser().parse_args(["arc-agi-2", "source", "validate", "synthetic-missing"])
        with mock.patch.object(arc_cli, "execute", return_value="synthetic-only") as dispatch:
            self.assertEqual(cli.execute(args), "synthetic-only")
        dispatch.assert_called_once_with(args, repository_root=ROOT)

    def test_facade_uses_supplied_root_for_both_outbound_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            supplied = Path(temporary) / "synthetic-root"
            for arguments, name, function in dispatch_cases(Path(temporary)):
                if arguments[:2] not in (["trial", "outbound-build"], ["baseline", "outbound-build"]):
                    continue
                with self.subTest(arguments=arguments):
                    modules = fake_legacy_modules()
                    with mock.patch.dict(sys.modules, modules):
                        arc_cli.execute(cli.build_parser().parse_args(["arc-agi-2", *arguments]), repository_root=supplied)
                    self.assertEqual(getattr(modules[name], function).call_args.kwargs["repository_root"], supplied)

    def test_generic_help_is_parser_only_and_selected_missing_path_retains_exit2(self):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        for optimized in (False, True):
            for selected in (False, True):
                with self.subTest(optimized=optimized, selected=selected), tempfile.TemporaryDirectory() as temporary:
                    result = subprocess.run([sys.executable, *( ["-O"] if optimized else []), "-I", "-B", "-c", FRESH_PROCESS,
                                             str(ROOT / "src"), "selected" if selected else "generic", str(Path(temporary) / "missing")],
                                            cwd=temporary, env=environment, text=True, encoding="utf-8", capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertTrue(report["parser_module_loaded"])
                    if selected:
                        self.assertIn("irisx.arc_agi2", report["runtime_modules"])
                        self.assertIn("irisx: error:", report["results"][0]["stderr"])
                    else:
                        self.assertEqual(report["runtime_modules"], [])


if __name__ == "__main__":
    unittest.main()

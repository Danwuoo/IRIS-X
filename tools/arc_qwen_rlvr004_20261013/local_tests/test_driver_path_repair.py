"""CPU tests for the narrow driver-path overlay; no GPU/provider/evaluator I/O.

POSIX path tests use real synthetic files and links. Native preflight outcomes
are explicit mocks, never observations of the pinned Kaggle BYOD resource.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import ctypes
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY = PACKAGE.parents[1]
OVERLAY = PACKAGE / "driver_path_repair/parent_scoring.py"
RESULTS = REPOSITORY / ".irisx/code17-local-20261013/test-results"
SCRATCH = RUNTIME = PARENT = WORKER = EVIDENCE = OLD_PATH = None


def authenticated_bytes(name):
    row = json.loads((PACKAGE / "runtime-path-map.json").read_bytes())["files"][name]
    path = REPOSITORY / row["repository_path"]
    raw = path.read_bytes()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("linked repository source")
    if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("frozen source differs: " + name)
    return raw


def setUpModule():
    global SCRATCH, RUNTIME, PARENT, WORKER, EVIDENCE, OLD_PATH
    sys.dont_write_bytecode = True
    RESULTS.mkdir(parents=True, exist_ok=True)
    SCRATCH = tempfile.TemporaryDirectory(prefix="driver-path-repair-", dir=RESULTS)
    output = Path(SCRATCH.name) / "reconstructed"
    result = subprocess.run(
        [sys.executable, "-B", str(PACKAGE / "runtime_assembly.py"),
         "--repository-root", str(REPOSITORY), "--output-root", str(output)],
        capture_output=True, text=True, timeout=45, check=True,
    )
    report = json.loads(result.stdout)
    freeze = json.loads((PACKAGE / "release/SOURCE-FREEZE.json").read_bytes())
    if report["members"] != 259 or report["source_archive_sha256"] != freeze["source_archive_sha256"]:
        raise ValueError("frozen reconstruction differs")
    RUNTIME = output / "producer-source"
    OLD_PATH = list(sys.path)
    sys.path[:0] = [str(RUNTIME), str(RUNTIME / "baseline"), str(RUNTIME / "baseline/src")]
    original = importlib.import_module("owned_runtime.parent_scoring")
    if Path(original.__file__).read_bytes() != authenticated_bytes("owned_runtime/parent_scoring.py"):
        raise ValueError("loaded frozen parent module differs")
    PARENT = ModuleType("owned_runtime.driver_path_repair_cpu_fixture")
    PARENT.__file__ = str(OVERLAY)
    PARENT.__package__ = "owned_runtime"
    exec(compile(OVERLAY.read_bytes(), str(OVERLAY), "exec", dont_inherit=True,
                 optimize=sys.flags.optimize), PARENT.__dict__)
    WORKER = importlib.import_module("owned_runtime.worker")
    EVIDENCE = importlib.import_module("owned_runtime.evidence")
    if Path(WORKER.__file__).read_bytes() != authenticated_bytes("owned_runtime/worker.py"):
        raise ValueError("loaded frozen worker differs")


def tearDownModule():
    if OLD_PATH is not None:
        sys.path[:] = OLD_PATH
    if SCRATCH is not None:
        SCRATCH.cleanup()


def node_dump(node):
    return ast.dump(node, include_attributes=False)


class FrozenDeltaTests(unittest.TestCase):
    def test_exact_ast_delta_preserves_all_other_source(self):
        old = ast.parse(authenticated_bytes("owned_runtime/parent_scoring.py"))
        new = ast.parse(OVERLAY.read_bytes())
        added = [n for n in new.body if isinstance(n, ast.FunctionDef)
                 and n.name in {"_driver_candidate_observations", "_trusted_driver_roots"}]
        self.assertEqual({n.name for n in added}, {"_driver_candidate_observations", "_trusted_driver_roots"})
        for node in added:
            new.body.remove(node)
        for node in new.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                    t.id == "TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES" for t in node.targets):
                self.assertEqual(ast.literal_eval(node.value),
                    ("/usr/local/nvidia/bin", "/bin", "/usr/bin", "/opt/bin"))
                self.assertIsInstance(node.value, ast.Tuple)
                node.value.elts.pop()
            elif isinstance(node, ast.FunctionDef) and node.name == "_driver_executable":
                self.assertEqual(node_dump(node.args), node_dump(ast.parse(
                    "def f(receipt=None): pass").body[0].args))
                node.args = deepcopy(next(n for n in old.body if isinstance(n, ast.FunctionDef)
                    and n.name == node.name).args)
                blocks = [n for n in node.body if isinstance(n, ast.If)]
                self.assertEqual(len(blocks), 1)
                self.assertEqual(node_dump(blocks[0]), node_dump(ast.parse(
                    "if receipt is not None:\n    receipt['nvidia_cli_candidates'] = _driver_candidate_observations()"
                    ).body[0]))
                node.body.remove(blocks[0])
                root_calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                              and isinstance(n.func, ast.Name) and n.func.id == "_trusted_driver_roots"]
                self.assertEqual(len(root_calls), 1)
                for parent in ast.walk(node):
                    for field, value in ast.iter_fields(parent):
                        if value is root_calls[0]:
                            setattr(parent, field, ast.parse(
                                "{Path(p).resolve() for p in TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES}",
                                mode="eval").body)
                        elif isinstance(value, list):
                            for index, child in enumerate(value):
                                if child is root_calls[0]:
                                    value[index] = ast.parse(
                                        "{Path(p).resolve() for p in TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES}",
                                        mode="eval").body
            elif isinstance(node, ast.FunctionDef) and node.name == "_preflight_child_driver":
                calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                         and isinstance(n.func, ast.Name) and n.func.id == "_driver_executable"]
                self.assertEqual(len(calls), 1)
                self.assertEqual([node_dump(n) for n in calls[0].args], ["Name(id='receipt', ctx=Load())"])
                self.assertEqual(calls[0].keywords, [])
                calls[0].args = []
        self.assertEqual(node_dump(new), node_dump(old))

    def test_library_tuple_and_environment_remain_fixed(self):
        expected = ("/usr/local/cuda/lib64", "/usr/local/nvidia/lib", "/usr/local/nvidia/lib64",
                    "/usr/lib/x86_64-linux-gnu", "/usr/lib64")
        self.assertEqual(PARENT.TRUSTED_DRIVER_LIBRARY_DIRECTORIES, expected)
        with patch.dict(os.environ, {"PATH": "/synthetic/ambient", "LD_LIBRARY_PATH": "/synthetic/ambient",
              "LD_PRELOAD": "/synthetic/injection", "KAGGLE_API_TOKEN": "SYNTHETIC_SECRET",
              "PYTHONPATH": "/synthetic/ambient", "CUDA_VISIBLE_DEVICES": "0"}, clear=True):
            production = PARENT.worker_environment(fixture=False)
            fixture = PARENT.worker_environment(fixture=True)
        self.assertEqual(production["PATH"], "/usr/local/nvidia/bin:/bin:/usr/bin:/opt/bin")
        self.assertEqual(production["LD_LIBRARY_PATH"], ":".join(expected))
        self.assertNotIn("LD_PRELOAD", production)
        self.assertNotIn("KAGGLE_API_TOKEN", production)
        self.assertNotIn("PYTHONPATH", production)
        self.assertNotIn("SYNTHETIC_SECRET", json.dumps(production))
        self.assertEqual(fixture["PATH"], os.defpath)
        self.assertNotIn("LD_LIBRARY_PATH", fixture)

    def test_ambient_path_rejected_before_any_leaf_observation(self):
        with patch.dict(os.environ, {"PATH": "/synthetic/ambient"}, clear=True), \
                patch.object(PARENT, "_driver_candidate_observations") as observe, patch("shutil.which") as which:
            with self.assertRaisesRegex(ValueError, "fixed source policy"):
                PARENT._driver_executable({})
            observe.assert_not_called()
            which.assert_not_called()


@unittest.skipUnless(os.name == "posix", "real executable/link semantics require POSIX")
class PosixFixedLeafTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=RESULTS)
        self.root = Path(self.tmp.name)
        self.dirs = tuple(str(self.root / name) for name in ("nvidia-bin", "bin", "usr-bin", "opt-bin"))
        for directory in self.dirs:
            Path(directory).mkdir()
        self.patches = ExitStack()
        self.patches.enter_context(patch.object(PARENT, "TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES", self.dirs))
        self.patches.enter_context(patch.dict(os.environ, {"PATH": ":".join(self.dirs)}, clear=True))

    def tearDown(self):
        self.patches.close()
        self.tmp.cleanup()

    def executable(self, index, body=b"#!/bin/sh\nexit 0\n"):
        leaf = Path(self.dirs[index]) / "nvidia-smi"
        leaf.write_bytes(body)
        leaf.chmod(0o755)
        return leaf

    def test_fourth_fixed_leaf_is_resolved_and_hashed_without_execution(self):
        expected = self.executable(3)
        with patch("subprocess.run") as run:
            receipt = {}
            executable, resolved = PARENT._driver_executable(receipt)
            run.assert_not_called()
        self.assertEqual(executable, expected)
        self.assertEqual(resolved, expected.resolve())
        self.assertEqual([r["state"] for r in receipt["nvidia_cli_candidates"]],
                         ["missing", "missing", "missing", "executable"])
        self.assertEqual(len(receipt["nvidia_cli_candidates"]), 4)

    def test_original_priority_is_retained(self):
        first, fourth = self.executable(0), self.executable(3)
        executable, _ = PARENT._driver_executable({})
        self.assertEqual(executable, first)
        self.assertNotEqual(executable, fourth)

    def test_new_root_directory_link_cannot_admit_an_untrusted_target(self):
        Path(self.dirs[3]).rmdir()
        outside = self.root / "untrusted-root"
        outside.mkdir()
        target = outside / "nvidia-smi"
        target.write_bytes(b"synthetic untrusted CLI; never executed")
        target.chmod(0o755)
        Path(self.dirs[3]).symlink_to(outside, target_is_directory=True)
        receipt = {}
        with self.assertRaisesRegex(ValueError, "fixed trusted directories"):
            PARENT._driver_executable(receipt)
        row = receipt["nvidia_cli_candidates"][3]
        self.assertEqual(row["state"], "rejected-link-target")
        self.assertEqual(row["resolved_path"], str(target.resolve()))
        self.assertNotIn(outside.resolve(), PARENT._trusted_driver_roots())

    def test_original_root_directory_links_keep_original_canonical_behavior(self):
        Path(self.dirs[1]).rmdir()
        target = self.executable(2)
        Path(self.dirs[1]).symlink_to(Path(self.dirs[2]), target_is_directory=True)
        executable, resolved = PARENT._driver_executable({})
        self.assertEqual(executable, Path(self.dirs[1]) / "nvidia-smi")
        self.assertEqual(resolved, target.resolve())

    def test_absence_has_exactly_four_missing_rows_and_fails(self):
        receipt = {}
        with self.assertRaisesRegex(ValueError, "cannot resolve nvidia-smi"):
            PARENT._driver_executable(receipt)
        self.assertEqual([r["path"] for r in receipt["nvidia_cli_candidates"]],
                         [str(Path(p) / "nvidia-smi") for p in self.dirs])
        self.assertTrue(all(r["state"] == "missing" and r["resolved_path"] is None
                            for r in receipt["nvidia_cli_candidates"]))

    def test_nonexecutables_and_nonregular_leaves_are_not_admitted(self):
        self.executable(0).chmod(0o644)
        (Path(self.dirs[1]) / "nvidia-smi").mkdir()
        receipt = {}
        with self.assertRaisesRegex(ValueError, "cannot resolve nvidia-smi"):
            PARENT._driver_executable(receipt)
        self.assertEqual([r["state"] for r in receipt["nvidia_cli_candidates"]],
                         ["non-executable", "nonregular", "missing", "missing"])

    def test_rejected_symlink_target_is_reported_without_body_read_or_admission(self):
        outside = self.root / "outside-executable"
        outside.write_bytes(b"SYNTHETIC_EXTERNAL_BODY_MUST_NOT_BE_READ")
        outside.chmod(0o755)
        (Path(self.dirs[3]) / "nvidia-smi").symlink_to(outside)
        receipt = {}
        with patch.object(Path, "read_bytes", side_effect=AssertionError("no file-body read")), \
                self.assertRaisesRegex(ValueError, "fixed trusted directories"):
            PARENT._driver_executable(receipt)
        row = receipt["nvidia_cli_candidates"][3]
        self.assertEqual(row["state"], "rejected-link-target")
        self.assertEqual(row["resolved_path"], str(outside.resolve()))
        self.assertFalse(row["resolved_path_truncated"])
        self.assertNotIn("SYNTHETIC_EXTERNAL_BODY", json.dumps(receipt))

    def test_trusted_root_symlink_is_accepted_by_original_canonical_gate(self):
        target = self.executable(2)
        leaf = Path(self.dirs[3]) / "nvidia-smi"
        leaf.symlink_to(target)
        # Remove the earlier exact leaf from resolver search using the original
        # returned-selection fixture, while preserving its canonical-root check.
        with patch("shutil.which", return_value=str(leaf)):
            executable, resolved = PARENT._driver_executable({})
        self.assertEqual(executable, leaf)
        self.assertEqual(resolved, target.resolve())

    def test_dangling_and_looping_links_preserve_bounded_failed_diagnostics(self):
        (Path(self.dirs[0]) / "nvidia-smi").symlink_to(self.root / "absent")
        loop = Path(self.dirs[1]) / "nvidia-smi"
        loop.symlink_to(loop)
        receipt = {}
        with self.assertRaisesRegex(ValueError, "cannot resolve nvidia-smi"):
            PARENT._driver_executable(receipt)
        self.assertEqual(receipt["nvidia_cli_candidates"][0]["state"], "missing")
        self.assertEqual(receipt["nvidia_cli_candidates"][1]["state"], "resolution-error")
        self.assertIn(receipt["nvidia_cli_candidates"][1]["error_type"], ("RuntimeError", "OSError"))
        self.assertLess(len(json.dumps(receipt)), 4096)

    def test_long_rejected_canonical_target_is_truncated_to_512_characters(self):
        parent = self.root / ("a" * 180) / ("b" * 180) / ("c" * 180)
        parent.mkdir(parents=True)
        target = parent / "nvidia-smi"
        target.write_bytes(b"synthetic never executed")
        target.chmod(0o755)
        (Path(self.dirs[3]) / "nvidia-smi").symlink_to(target)
        receipt = {}
        with self.assertRaisesRegex(ValueError, "fixed trusted directories"):
            PARENT._driver_executable(receipt)
        row = receipt["nvidia_cli_candidates"][3]
        self.assertEqual(row["resolved_path"], str(target.resolve())[:512])
        self.assertTrue(row["resolved_path_truncated"])
        self.assertEqual(len(row["resolved_path"]), 512)


@contextmanager
def synthetic_native_preflight(*, loader=None, responses=None):
    """Mock only native observations and interpreter prerequisites, not gates."""
    flags = SimpleNamespace(**{name: getattr(sys.flags, name) for name in dir(sys.flags)
                              if not name.startswith("_")})
    flags.isolated = flags.ignore_environment = flags.no_user_site = 1
    with tempfile.TemporaryDirectory(dir=RESULTS) as td, ExitStack() as stack:
        path = Path(td) / "nvidia-smi"
        path.write_bytes(b"synthetic native CLI; subprocess mocked, never executed")
        stack.enter_context(patch.object(sys, "flags", flags))
        stack.enter_context(patch.object(sys, "dont_write_bytecode", True))
        stack.enter_context(patch.object(Path, "cwd", return_value=RUNTIME))
        stack.enter_context(patch.dict(os.environ, PARENT.worker_environment(fixture=False), clear=True))
        resolve = stack.enter_context(patch.object(PARENT, "_driver_executable", return_value=(path, path)))
        load = stack.enter_context(patch("ctypes.CDLL", **(loader or {"return_value": SimpleNamespace(cuInit=object())})))
        run = stack.enter_context(patch("subprocess.run", side_effect=responses or [
            subprocess.CompletedProcess([], 0, "580.178.04\n", ""),
            subprocess.CompletedProcess([], 0, '{"cuda_available":true,"device_count":1}', "")]))
        yield resolve, load, run


class NativeGatePreservationTests(unittest.TestCase):
    def test_synthetic_positive_retains_queries_deadlines_and_no_model_claim(self):
        with synthetic_native_preflight() as (resolve, load, run):
            result = PARENT.preflight_child_driver(deadline=time.monotonic() + 90)
        resolve.assert_called_once()
        self.assertIsInstance(resolve.call_args.args[0], dict)
        load.assert_called_once_with("libcuda.so.1")
        self.assertEqual(run.call_count, 2)
        first, second = run.call_args_list
        self.assertEqual(first.args[0][1:], ["--query-gpu=driver_version", "--format=csv,noheader"])
        self.assertEqual(first.kwargs["timeout"], 10.)
        self.assertTrue(first.kwargs["check"])
        self.assertEqual(second.args[0][1:4], ["-I", "-B", "-c"])
        self.assertIn("torch.cuda.is_available()", second.args[0][4])
        self.assertEqual(second.kwargs["timeout"], 60.)
        self.assertEqual(result["driver_version"], "580.178.04")
        self.assertEqual(result["status"], "complete")
        self.assertFalse(result["native_model_loaded"])
        self.assertFalse(result["GPU_fit_or_throughput_claim"])
        self.assertTrue(result["full_native_admission_still_required"])

    def test_missing_library_and_missing_cuinit_fail_before_query(self):
        for loader, message in (({"side_effect": OSError("synthetic missing library")}, "cannot resolve libcuda"),
                                ({"return_value": SimpleNamespace()}, "lacks cuInit")):
            with self.subTest(message=message), synthetic_native_preflight(loader=loader) as (_, _, run):
                with self.assertRaisesRegex(ValueError, message) as caught:
                    PARENT.preflight_child_driver(deadline=time.monotonic() + 90)
                run.assert_not_called()
                receipt = caught.exception.child_driver_resolution
                self.assertEqual(receipt["stage"], "resolve-cuda-library")
                self.assertFalse(receipt["driver_resolved_before_weights"])
                self.assertFalse(receipt["native_model_loaded"])

    def test_query_error_or_timeout_preserves_failure_and_does_not_probe_cuda(self):
        for exc in (subprocess.CalledProcessError(9, "synthetic-cli"),
                    subprocess.TimeoutExpired("synthetic-cli", 10)):
            with self.subTest(kind=type(exc).__name__), synthetic_native_preflight(responses=[exc]) as (_, _, run):
                with self.assertRaises(type(exc)) as caught:
                    PARENT.preflight_child_driver(deadline=time.monotonic() + 90)
                self.assertEqual(run.call_count, 1)
                receipt = caught.exception.child_driver_resolution
                self.assertEqual(receipt["stage"], "query-nvidia-driver")
                self.assertEqual(receipt["status"], "failed")
                self.assertFalse(receipt["nvidia_smi_query_complete"])
                self.assertFalse(receipt["native_model_loaded"])
                if isinstance(exc, subprocess.CalledProcessError):
                    self.assertEqual(receipt["subprocess_returncode"], 9)

    def test_cuda_zero_malformed_and_wrong_driver_remain_rejected(self):
        scenarios = [("580.178.04", '{"cuda_available":false,"device_count":0}', "CUDA unavailable"),
                     ("580.178.04", '{"cuda_available":true,"device_count":true}', "visibility response"),
                     ("580.178.04", '{"cuda_available":true,"device_count":1,"extra":0}', "visibility response"),
                     ("580.000.00", '{"cuda_available":true,"device_count":1}', "unchanged hardware contract")]
        for driver, visibility, message in scenarios:
            responses = [subprocess.CompletedProcess([], 0, driver + "\n", ""),
                         subprocess.CompletedProcess([], 0, visibility, "")]
            with self.subTest(message=message), synthetic_native_preflight(responses=responses):
                with self.assertRaisesRegex(ValueError, message) as caught:
                    PARENT.preflight_child_driver(deadline=time.monotonic() + 90)
                self.assertFalse(caught.exception.child_driver_resolution["native_model_loaded"])
                self.assertEqual(caught.exception.child_driver_resolution["status"], "failed")

    def test_oversized_query_rejected_before_cuda_probe(self):
        with synthetic_native_preflight(responses=[subprocess.CompletedProcess([], 0, "x" * 16385, "")]) as (_, _, run):
            with self.assertRaisesRegex(ValueError, "bounded NVIDIA CLI"):
                PARENT.preflight_child_driver(deadline=time.monotonic() + 90)
            self.assertEqual(run.call_count, 1)

    def test_invalid_or_expired_deadline_cannot_observe_or_admit_hardware(self):
        for value in (True, float("inf"), float("nan"), -1.):
            with self.subTest(value=repr(value)), patch.object(PARENT, "_driver_executable") as resolve:
                with self.assertRaisesRegex(ValueError, "original inner deadline") as caught:
                    PARENT.preflight_child_driver(deadline=value)
                resolve.assert_not_called()
                self.assertEqual(caught.exception.child_driver_resolution["stage"], "child-policy")

    def test_real_isolated_child_persists_bounded_failed_receipt_without_model_imports(self):
        # The unavailable CLI is synthetic. The process, isolation, unchanged
        # preflight failure handling and durable original writer are real CPU I/O.
        with tempfile.TemporaryDirectory(dir=RESULTS) as td:
            output = Path(td)
            script = output / "probe.py"
            script.write_text("""from pathlib import Path
import json,sys,time,types
from unittest.mock import patch
root,overlay,output=map(Path,sys.argv[1:])
sys.path[:0]=[str(root),str(root/'baseline'),str(root/'baseline/src')]
module=types.ModuleType('owned_runtime.driver_overlay_fixture');module.__package__='owned_runtime'
exec(compile(overlay.read_bytes(),str(overlay),'exec',dont_inherit=True,optimize=sys.flags.optimize),module.__dict__)
from owned_runtime.evidence import register_output
from experiment_flow.contracts import write_json
register_output(output)
with patch('shutil.which',return_value=None):
    try:module.preflight_child_driver(deadline=time.monotonic()+15.)
    except ValueError as exc:
        ref=write_json(output/'child-driver-resolution.json',exc.child_driver_resolution)
        print(json.dumps({'receipt':ref,'optimized':sys.flags.optimize,
            'model_imports':any(n in sys.modules for n in ('torch','transformers','peft'))}))
    else:raise RuntimeError('synthetic CLI absence admitted')
""", encoding="utf-8")
            env = PARENT.worker_environment(fixture=False)
            if os.name == "nt":
                for key in ("SystemRoot", "WINDIR"):
                    if key in os.environ:
                        env[key] = os.environ[key]
            flags = ["-O"] if sys.flags.optimize else []
            proc = subprocess.run([sys.executable, "-I", "-B", *flags, str(script), str(RUNTIME), str(OVERLAY), str(output)],
                cwd=RUNTIME, env=env, capture_output=True, text=True, timeout=25)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            observation = json.loads(proc.stdout)
            raw = (output / "child-driver-resolution.json").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), observation["receipt"]["file_sha256"])
            self.assertEqual(observation["optimized"], sys.flags.optimize)
            self.assertFalse(observation["model_imports"])
            receipt = json.loads(raw)
            self.assertEqual(len(receipt["nvidia_cli_candidates"]), 4)
            self.assertEqual(receipt["stage"], "resolve-nvidia-cli")
            self.assertEqual(receipt["status"], "failed")
            self.assertFalse(receipt["driver_resolved_before_weights"])
            self.assertFalse(receipt["nvidia_smi_query_complete"])
            self.assertFalse(receipt["native_model_loaded"])
            self.assertTrue(receipt["full_native_admission_still_required"])

    def test_diagnostic_failure_preserves_unknown_physical_totals_and_unclosed_owner(self):
        with tempfile.TemporaryDirectory(dir=RESULTS) as td:
            output = Path(td)
            EVIDENCE.register_output(output)
            events = [{"event_id": 0, "op_id": "synthetic-unsettled", "phase": "native-model-load",
                       "status": "unknown", "dispatched": True,
                       "reserved_cost": {"model_loads": 1}, "charged_cost": {"model_loads": 1}}]
            closure = {"closed": False, "model_stopped": False, "ledger_settled": False,
                       "fatal_native_state": "synthetic diagnostic failure", "physical_events": deepcopy(events),
                       "physical_totals": {"seconds": None, "tokens": None, "calls": None}}
            journal = SimpleNamespace(events=deepcopy(events), summary=lambda: {"closed": True, "integrity_ok": True,
                                                       "physical_events": deepcopy(events)},
                                      seal_artifact=lambda path, label: None)
            try:
                actual = WORKER._finalize_physical_events(journal, closure, output)
                self.assertEqual(json.loads((output / "physical-events.json").read_bytes()), events)
                self.assertEqual(actual["physical_totals"], {"seconds": None, "tokens": None, "calls": None})
                self.assertFalse(actual["closed"])
                self.assertFalse(actual["model_stopped"])
                self.assertFalse(actual["ledger_settled"])
                self.assertEqual(closure["physical_events"], events)
            finally:
                EVIDENCE._OWNED_OUTPUTS.discard(output.resolve())


if __name__ == "__main__":
    unittest.main()

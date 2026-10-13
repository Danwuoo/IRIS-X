"""CPU adversaries for exact code17 bytes; no GPU, model, provider or evaluator.

The worker projection uses a synthetic journal observation and actual bounded,
fsynced files. Closure guards are compiled unchanged from authenticated source
AST nodes because their complete module imports Linux-only fcntl on Windows.
These checks do not prove Linux process ownership or production admission.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import weakref


PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY = PACKAGE.parents[1]
RESULTS = REPOSITORY / ".irisx/code17-local-20261013/test-results"
SCRATCH = None
RUNTIME = None
PARENT = None
WORKER = None
EVIDENCE = None
GUARDS = None
OLD_PATH = None


def authenticated_bytes(name):
    mapping = json.loads((PACKAGE / "runtime-path-map.json").read_bytes())
    row = mapping["files"][name]
    path = REPOSITORY / row["repository_path"]
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("linked repository source")
    raw = path.read_bytes()
    if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("source differs: " + name)
    return raw


def setUpModule():
    global SCRATCH, RUNTIME, PARENT, WORKER, EVIDENCE, GUARDS, OLD_PATH
    sys.dont_write_bytecode = True
    RESULTS.mkdir(parents=True, exist_ok=True)
    SCRATCH = tempfile.TemporaryDirectory(prefix="startup-contract-", dir=RESULTS)
    output = Path(SCRATCH.name) / "reconstructed"
    proc = subprocess.run(
        [sys.executable, "-B", str(PACKAGE / "runtime_assembly.py"),
         "--repository-root", str(REPOSITORY), "--output-root", str(output)],
        capture_output=True, text=True, timeout=45, check=True,
    )
    report = json.loads(proc.stdout)
    freeze = json.loads((PACKAGE / "release/SOURCE-FREEZE.json").read_bytes())
    if (report["members"] != 259 or report["source_archive_sha256"] != freeze["source_archive_sha256"]
            or freeze["source_members"] != 259):
        raise ValueError("reconstructed freeze differs")
    RUNTIME = output / "producer-source"
    OLD_PATH = list(sys.path)
    sys.path[:0] = [str(RUNTIME), str(RUNTIME / "baseline"), str(RUNTIME / "baseline/src")]
    PARENT = importlib.import_module("owned_runtime.parent_scoring")
    WORKER = importlib.import_module("owned_runtime.worker")
    EVIDENCE = importlib.import_module("owned_runtime.evidence")
    sys.path[:] = [str(RUNTIME), str(RUNTIME / "baseline"), str(RUNTIME / "baseline/src"), *OLD_PATH]
    for name, module in (("owned_runtime/parent_scoring.py", PARENT),
                         ("owned_runtime/worker.py", WORKER)):
        if Path(module.__file__).read_bytes() != authenticated_bytes(name):
            raise ValueError("loaded module differs")
    # Preserve complete AST definitions; replace no guard or runtime body.
    tree = ast.parse(authenticated_bytes("owned_runtime/supervisor.py"))
    names = {"ClosedCapability", "_inner_is_closed", "verify_closed_capability"}
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
             and node.name in names]
    if {node.name for node in nodes} != names:
        raise ValueError("source closure guards absent")
    GUARDS = {"__name__": "authenticated_closure_guard_fixture",
              "_REGISTRY": weakref.WeakKeyDictionary()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<authenticated-supervisor-guards>",
                 "exec", dont_inherit=True, optimize=sys.flags.optimize), GUARDS)


def tearDownModule():
    if OLD_PATH is not None:
        sys.path[:] = OLD_PATH
    if SCRATCH is not None:
        SCRATCH.cleanup()


class DriverPolicyTests(unittest.TestCase):
    def test_production_environment_uses_fixed_source_paths_only(self):
        ambient = {"PATH": "/synthetic/untrusted", "LD_LIBRARY_PATH": "/synthetic/injected",
                   "KAGGLE_API_TOKEN": "SYNTHETIC_TOKEN", "PYTHONPATH": "/synthetic/injected",
                   "LD_PRELOAD": "/synthetic/injected", "CUDA_VISIBLE_DEVICES": "0",
                   "CUDA_DEVICE_ORDER": "PCI_BUS_ID"}
        with patch.dict(os.environ, ambient, clear=True):
            result = PARENT.worker_environment(fixture=False)
        self.assertEqual(result["PATH"], ":".join(PARENT.TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES))
        self.assertEqual(result["LD_LIBRARY_PATH"], ":".join(PARENT.TRUSTED_DRIVER_LIBRARY_DIRECTORIES))
        self.assertEqual(result["CUDA_VISIBLE_DEVICES"], "0")
        self.assertEqual(result["PYTHONHASHSEED"], "0")
        self.assertFalse(set(ambient) & set(result) - {"PATH", "LD_LIBRARY_PATH", "CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER"})
        self.assertNotIn("SYNTHETIC_TOKEN", json.dumps(result))

    def test_fixture_never_requests_cuda_driver_paths(self):
        with patch.dict(os.environ, {"PATH": "/untrusted", "CUDA_VISIBLE_DEVICES": "0"}, clear=True):
            result = PARENT.worker_environment(fixture=True)
        self.assertEqual(result["CUDA_VISIBLE_DEVICES"], "")
        self.assertEqual(result["PATH"], os.defpath)
        self.assertNotIn("LD_LIBRARY_PATH", result)

    def test_ambient_executable_search_rejected_before_resolution(self):
        with patch.dict(os.environ, {"PATH": "/synthetic/untrusted"}, clear=True), patch("shutil.which") as which:
            with self.assertRaisesRegex(ValueError, "fixed source policy"):
                PARENT._driver_executable()
            which.assert_not_called()

    def test_missing_cli_uses_exact_trusted_search(self):
        fixed = ":".join(PARENT.TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES)
        with patch.dict(os.environ, {"PATH": fixed}, clear=True), patch("shutil.which", return_value=None) as which:
            with self.assertRaisesRegex(ValueError, "cannot resolve nvidia-smi"):
                PARENT._driver_executable()
            which.assert_called_once_with("nvidia-smi", path=fixed)

    def test_foreign_resolved_executable_rejected(self):
        with tempfile.TemporaryDirectory(dir=RESULTS) as td:
            foreign = Path(td) / "nvidia-smi"
            foreign.write_bytes(b"synthetic executable, never invoked")
            fixed = ":".join(PARENT.TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES)
            with patch.dict(os.environ, {"PATH": fixed}, clear=True), patch("shutil.which", return_value=str(foreign)):
                with self.assertRaisesRegex(ValueError, "fixed trusted directories"):
                    PARENT._driver_executable()

    def test_invalid_or_expired_deadline_has_failed_receipt(self):
        for value in (True, False, float("inf"), float("-inf"), float("nan"), -1.0):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError) as caught:
                PARENT.preflight_child_driver(deadline=value)
            receipt = caught.exception.child_driver_resolution
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["stage"], "child-policy")
            self.assertFalse(receipt["native_model_loaded"])
            self.assertTrue(receipt["full_native_admission_still_required"])

    def test_real_isolated_cpu_child_preserves_absent_cli_failure(self):
        # CLI absence is synthetic; isolated interpreter/cwd/environment and
        # the actual failure receipt/write are exercised in a real CPU child.
        with tempfile.TemporaryDirectory(dir=RESULTS) as td:
            output = Path(td)
            script = output / "probe.py"
            script.write_text("""from pathlib import Path
import json,sys,time
from unittest.mock import patch
root=Path(sys.argv[1]);output=Path(sys.argv[2])
sys.path[:0]=[str(root),str(root/'baseline'),str(root/'baseline/src')]
from owned_runtime.parent_scoring import preflight_child_driver
from owned_runtime.evidence import register_output
from experiment_flow.contracts import write_json
register_output(output)
with patch('shutil.which',return_value=None):
    try:preflight_child_driver(deadline=time.monotonic()+15.)
    except ValueError as exc:
        ref=write_json(output/'child-driver-resolution.json',exc.child_driver_resolution)
        print(json.dumps({'receipt':ref,'model_libraries_imported':any(x in sys.modules for x in ('torch','transformers','peft'))}))
    else:raise RuntimeError('synthetic unavailable CLI accepted')
""", encoding="utf-8")
            env = PARENT.worker_environment(fixture=False)
            # Windows DLL/Winsock initialization needs its host directory;
            # this CPU fixture is not the Linux production child environment.
            if os.name == "nt":
                for key in ("SystemRoot", "WINDIR"):
                    if key in os.environ:
                        env[key] = os.environ[key]
            flags = ["-O"] if sys.flags.optimize else []
            proc = subprocess.run([sys.executable, "-I", "-B", *flags, str(script), str(RUNTIME), str(output)],
                                  cwd=RUNTIME, env=env, capture_output=True, text=True, timeout=25)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            observation = json.loads(proc.stdout)
            self.assertFalse(observation["model_libraries_imported"])
            raw = (output / "child-driver-resolution.json").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), observation["receipt"]["file_sha256"])
            receipt = json.loads(raw)
            self.assertEqual(receipt["stage"], "resolve-nvidia-cli")
            self.assertEqual(receipt["status"], "failed")
            self.assertFalse(receipt["nvidia_smi_query_complete"])
            self.assertFalse(receipt["driver_resolved_before_weights"])
            self.assertFalse(receipt["native_model_loaded"])
            self.assertFalse(receipt["GPU_fit_or_throughput_claim"])


class SyntheticClosedJournal:
    """Explicit test observation; never an authenticated production journal."""
    def __init__(self, events, *, closed=True, integrity=True):
        self.events = deepcopy(events)
        self.closed = closed
        self.integrity = integrity
        self.sealed = []

    def summary(self):
        return {"closed": self.closed, "integrity_ok": self.integrity,
                "physical_events": deepcopy(self.events)}

    def seal_artifact(self, path, *, label):
        self.sealed.append((str(path), label))


class FailedPhysicalProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=RESULTS)
        self.root = Path(self.tmp.name)
        EVIDENCE.register_output(self.root)
        self.events = [{"event_id": 0, "op_id": "synthetic-native-load", "phase": "native-model-load",
                        "status": "failed", "dispatched": True, "seconds": 1.25,
                        "reserved_cost": {"model_loads": 1}, "charged_cost": {"model_loads": 1}},
                       {"event_id": 1, "op_id": "synthetic-unsettled", "phase": "calibration-generation",
                        "status": "unknown", "dispatched": True, "reserved_cost": {"calls": 1},
                        "charged_cost": {"calls": 1}}]
        self.closure = {"closed": False, "model_stopped": False, "ledger_settled": False,
                        "fatal_native_state": "synthetic admission failure",
                        "physical_events": deepcopy(self.events),
                        "nested": {"physical_events": deepcopy(self.events)}}

    def tearDown(self):
        EVIDENCE._OWNED_OUTPUTS.discard(self.root.resolve())
        self.tmp.cleanup()

    def test_failed_admission_emits_complete_fsynchronized_event_union(self):
        original = deepcopy(self.closure)
        journal = SyntheticClosedJournal(self.events)
        result = WORKER._finalize_physical_events(journal, self.closure, self.root)
        path = self.root / "physical-events.json"
        self.assertEqual(json.loads(path.read_bytes()), self.events)
        ref = result["physical_events_ref"]
        self.assertEqual(ref["file_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result["nested"]["physical_events_ref"], ref)
        self.assertEqual(journal.sealed, [(str(path.resolve()), "physical-events")])
        for field in ("closed", "model_stopped", "ledger_settled", "fatal_native_state"):
            self.assertEqual(result[field], original[field])
        self.assertEqual(self.closure, original)
        self.assertFalse(GUARDS["_inner_is_closed"]({"model_closure": result}))

    def test_unclosed_or_damaged_journal_cannot_emit_projection(self):
        for closed, integrity in ((False, True), (True, False)):
            journal = SyntheticClosedJournal(self.events, closed=closed, integrity=integrity)
            with self.subTest(closed=closed, integrity=integrity), self.assertRaisesRegex(ValueError, "authenticated closed journal"):
                WORKER._finalize_physical_events(journal, self.closure, self.root)
            self.assertFalse((self.root / "physical-events.json").exists())
            self.assertEqual(journal.sealed, [])

    def test_closure_event_omission_preserves_failure_without_output(self):
        closure = deepcopy(self.closure)
        closure["physical_events"] = closure["physical_events"][:1]
        with self.assertRaisesRegex(ValueError, "event union differs"):
            WORKER._finalize_physical_events(SyntheticClosedJournal(self.events), closure, self.root)
        self.assertFalse((self.root / "physical-events.json").exists())

    def test_reused_byte_bound_projection_is_checked_and_not_rewritten(self):
        journal = SyntheticClosedJournal(self.events)
        result = WORKER._finalize_physical_events(journal, self.closure, self.root)
        path = self.root / "physical-events.json"
        raw = path.read_bytes()
        again = WORKER._finalize_physical_events(journal, result, self.root)
        self.assertEqual(again, result)
        self.assertEqual(path.read_bytes(), raw)
        path.write_bytes(raw + b" ")
        with self.assertRaisesRegex(ValueError, "stream differs"):
            WORKER._finalize_physical_events(journal, result, self.root)
        self.assertEqual(path.read_bytes(), raw + b" ")

    def test_escaped_projection_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=RESULTS) as external:
            path = Path(external) / "physical-events.json"
            path.write_text(json.dumps(self.events), encoding="utf-8")
            closure = deepcopy(self.closure)
            closure["physical_events_ref"] = {"path": str(path), "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            with self.assertRaisesRegex(ValueError, "stream differs"):
                WORKER._finalize_physical_events(SyntheticClosedJournal(self.events), closure, self.root)

    def test_failure_receipt_and_unregistered_object_cannot_authorize_scoring(self):
        cap = GUARDS["ClosedCapability"]
        with self.assertRaises(TypeError):
            cap()
        for forged in ({"safe_closure": True, "model_stopped": True}, object.__new__(cap)):
            with self.subTest(kind=type(forged).__name__), self.assertRaisesRegex(ValueError, "live owned parent closure"):
                GUARDS["verify_closed_capability"](forged)


if __name__ == "__main__":
    unittest.main()

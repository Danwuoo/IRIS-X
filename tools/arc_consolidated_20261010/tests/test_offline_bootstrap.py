"""Synthetic controller tests; no real Dataset acceptance, install or GPU run.

Real Linux process tests only launch ordinary sleeping Python children. Windows
skips those tests and cannot provide Linux stop-proof acceptance evidence.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from tools.arc_consolidated_20261010 import offline_bootstrap as b
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory


GATE = {"passed": True, "profile": "FULL", "gate": "research_testability_only"}
STOPPED = {"dispatched": True, "owned_group_stopped": True, "leader_reaped": True,
           "live_group_members": 0, "scope": "synthetic mock; not Linux evidence"}


def synthetic_material():
    return {"roots": {role: "/synthetic/" + role for role in b.PINS},
            "interpreter": {"python_executable": "/synthetic/python"},
            "asset_receipts": {"synthetic": True}}


def synthetic_installed():
    return {"python_command": ["/synthetic/python", "-I", "-B", "-S", "/synthetic/guard.py"],
            "environment_lock_path": "/synthetic/environment-lock.json",
            "actual_environment_lock_sha256": "a" * 64,
            "reused_environment": False, "installed_offline": True}


class PurePlanningTests(unittest.TestCase):
    def test_plan_is_pure_deterministic_and_defaults_have_no_reads(self):
        with mock.patch.object(Path, "stat", side_effect=AssertionError("filesystem read")), \
             mock.patch.object(Path, "open", side_effect=AssertionError("filesystem read")), \
             mock.patch.object(b, "_helpers", side_effect=AssertionError("backend import")):
            first = b.plan_config(None, "/scratch/environment-assets")
            second = b.plan_config({}, "/scratch/environment-assets")
        self.assertEqual(first, second)
        self.assertEqual(first["plan_sha256"], b.digest(first["config"]))
        self.assertEqual(first["config"]["input_root"], "/kaggle/input")
        self.assertEqual(first["config"]["explicit_roots"], dict.fromkeys(b.PINS))
        self.assertNotIn("torch", b.__dict__)

    def test_bad_configuration_rejected(self):
        for config in ({"model_path": "/somewhere"}, {"input_root": "relative"},
                       {"input_root": "/safe/../unsafe"}, {"input_root": True},
                       {"explicit_roots": {"competition": "/ignored"}},
                       {"explicit_roots": {"runtime": "C:\\host"}},
                       {"explicit_roots": []}, []):
            with self.subTest(config=config), self.assertRaises(b.BootstrapError):
                b.plan_config(config, "/scratch")

    def test_plan_binds_paths_and_frozen_pins(self):
        first = b.plan_config({}, "/scratch/a")
        self.assertNotEqual(first["plan_sha256"], b.plan_config({}, "/scratch/b")["plan_sha256"])
        changed = copy.deepcopy(first)
        changed["config"]["pins"]["runtime"]["manifest_sha256"] = "0" * 64
        changed["plan_sha256"] = b.digest(changed["config"])
        with self.assertRaises(b.BootstrapError):
            b._validate_plan(changed)

    def test_disabled_and_failed_gate_do_not_touch_files(self):
        with mock.patch.object(b, "_safe", side_effect=AssertionError("filesystem read")), \
             mock.patch.object(b, "_dispatch", side_effect=AssertionError("child launch")), \
             mock.patch.object(b, "_helpers", side_effect=AssertionError("backend import")):
            self.assertEqual(b.prepare_model_environment(None)["files_written"], 0)
            for gate in (None, {}, {**GATE, "passed": 1}, {**GATE, "profile": "SMOKE"}):
                with self.assertRaises(b.BootstrapError) as caught:
                    b.prepare_model_environment(None, enable_model=True, gate_receipt=gate)
                self.assertTrue(caught.exception.owned_descendants_stopped)

    def test_switch_and_deadline_are_strict(self):
        plan = b.plan_config({}, "/scratch")
        for value in (1, "true", None):
            with self.assertRaises(b.BootstrapError):
                b.prepare_model_environment(plan, enable_model=value)
        for seconds in (True, 0, -1, 14401, float("nan"), float("inf"), "1800"):
            with self.assertRaises(b.BootstrapError):
                b.prepare_model_environment(plan, enable_model=True, gate_receipt=GATE,
                                            deadline_seconds=seconds)

    def test_unsupported_platform_stops_before_creating_work_root(self):
        with mock.patch.object(b.sys, "platform", "win32"), \
             mock.patch.object(b, "_safe", side_effect=AssertionError("filesystem read")):
            with self.assertRaisesRegex(b.BootstrapError, "requires Linux"):
                b.prepare_model_environment(b.plan_config({}, "/scratch"),
                                            enable_model=True, gate_receipt=GATE)

    def test_exact_vendored_helpers_match_frozen_pins(self):
        package = Path(b.__file__).parent
        for filename, expected in b.HELPER_PINS.items():
            with self.subTest(filename=filename):
                self.assertEqual(b._sha(package / "legacy" / filename), expected)


class FilesystemBindingTests(unittest.TestCase):
    def test_mounts_use_only_two_exact_layouts_and_reject_ambiguity(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs, work = root / "inputs", root / "work"
            work.mkdir()
            for index, pin in enumerate(b.PINS.values()):
                owner, slug, _ = pin["reference"].split("/")
                target = inputs / "datasets" / owner / slug if index % 2 else inputs / slug
                target.mkdir(parents=True)
            # Deliberately internal synthetic config; real public plans require Linux paths.
            config = {"input_root": str(inputs), "work_root": str(work),
                      "explicit_roots": dict.fromkeys(b.PINS)}
            self.assertEqual(set(b.resolve_mounts(config)), set(b.PINS))
            owner, slug, _ = b.PINS["runtime"]["reference"].split("/")
            (inputs / "datasets" / owner / slug).mkdir(parents=True)
            with self.assertRaisesRegex(b.BootstrapError, "exactly one"):
                b.resolve_mounts(config)

    def test_missing_mount_has_no_recursive_fallback(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pin = b.PINS["runtime"]
            slug = pin["reference"].split("/")[1]
            (root / "arbitrary" / slug).mkdir(parents=True)
            with self.assertRaisesRegex(b.BootstrapError, "runtime"):
                b.resolve_mounts({"input_root": str(root), "work_root": str(root),
                                  "explicit_roots": dict.fromkeys(b.PINS)})

    def test_corrupt_helper_cannot_execute(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "untrusted.py"
            path.write_text("raise AssertionError('must not execute')\n")
            with self.assertRaisesRegex(b.BootstrapError, "hash differs"):
                b._load_verified("synthetic_untrusted_helper", path, "0" * 64)
            self.assertNotIn("synthetic_untrusted_helper", sys.modules)

    def test_json_duplicates_and_existing_receipts_rejected(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "receipt.json"
            path.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(b.BootstrapError, "duplicate"):
                b._read_json(path)
            with self.assertRaises(FileExistsError):
                b._write_new(path, {"replace": True})

    def test_synthetic_adapter_subtree_and_pin_checks(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "adapter"
            folder.mkdir()
            (root / "adapter-manifest.json").write_text('{"fixture":"synthetic"}')
            config = {"base_model_name_or_path": b.MODEL_ID.split("@")[0],
                      "revision": b.MODEL_ID.split("@")[1]}
            (folder / "adapter_config.json").write_bytes(b.canonical(config))
            (folder / "adapter_model.safetensors").write_bytes(b"synthetic opaque bytes, not weights")
            binding = {"model_id": b.MODEL_ID,
                       "material_manifest_sha256": b.PINS["model"]["manifest_sha256"],
                       "files": {name: b._sha(folder / name) for name in
                                 ("adapter_config.json", "adapter_model.safetensors")}}
            (folder / "adapter-binding.json").write_bytes(b.canonical(binding))
            pins = copy.deepcopy(b.PINS)
            pins["adapter"]["manifest_sha256"] = b._sha(root / "adapter-manifest.json")
            with mock.patch.object(b, "PINS", pins), \
                 mock.patch.object(b, "ADAPTER_BINDING_SHA256", b._sha(folder / "adapter-binding.json")):
                receipt = b._adapter(root)
                self.assertFalse(receipt["loaded"])
                self.assertEqual(receipt["bound_file_count"], 2)
                self.assertEqual(receipt["scope"], "pinned outer manifest and complete adapter binding subtree")
                (folder / "extra.bin").write_bytes(b"unlisted")
                with self.assertRaisesRegex(b.BootstrapError, "closed inventory"):
                    b._adapter(root)


class SyntheticControllerTests(unittest.TestCase):
    def test_material_checks_opaque_runtime_without_scientific_parsers(self):
        runtime = mock.Mock()
        runtime.verify_runtime.return_value = {"files": {
            "evaluator/secret.json": {"bytes": 30, "sha256": "do-not-forward"},
            "training/private.json": {"bytes": 20, "sha256": "do-not-forward"}}}
        runtime.verify_inputs.side_effect = AssertionError("scientific parser forbidden")
        runtime.verify_runtime_training.side_effect = AssertionError("training parser forbidden")
        environment = mock.Mock()
        environment.validate_wheelhouse.return_value = {
            "status": "synthetic-static-check", "wheel_count": 2,
            "wheel_lock_sha256": "b" * 64, "source_lock_sha256": "c" * 64}
        model = mock.Mock()
        model.validate_material.return_value = {"material_manifest_sha256": b.PINS["model"]["manifest_sha256"]}
        interpreter = mock.Mock()
        interpreter.prepare_interpreter.return_value = {
            "manifest_sha256": "d" * 64, "archive_sha256": "e" * 64,
            "executable_sha256": "f" * 64, "verified_member_count": 2,
            "python_executable": "/synthetic/python"}
        helpers = {"arc_next_offline_bundle.py": runtime,
                   "arc_next_offline_environment.py": environment,
                   "arc_next_models.py": model,
                   "arc_next_offline_interpreter.py": interpreter}
        def synthetic_hash(path):
            for pin in b.PINS.values():
                if Path(path).name == pin["manifest"]:
                    return pin["manifest_sha256"]
            return b.SOURCE_LOCK_SHA256
        with mock.patch.object(b, "_helpers", return_value=helpers), \
             mock.patch.object(b, "resolve_mounts", return_value=synthetic_material()["roots"]), \
             mock.patch.object(b, "_safe", side_effect=lambda path, **_: Path(path)), \
             mock.patch.object(b, "_sha", side_effect=synthetic_hash), \
             mock.patch.object(b, "_adapter", return_value={"synthetic": True}):
            result = b._material_child(b.plan_config({}, "/synthetic/work"))
        runtime.verify_runtime.assert_called_once()
        runtime.verify_inputs.assert_not_called()
        runtime.verify_runtime_training.assert_not_called()
        environment.validate_wheelhouse.assert_called_once()
        self.assertFalse(environment.validate_wheelhouse.call_args.kwargs["check_runtime"])
        self.assertEqual(result["asset_receipts"]["runtime"]["file_count"], 2)
        self.assertEqual(result["asset_receipts"]["runtime"]["total_bytes"], 50)
        serialized = json.dumps(result)
        for forbidden in ("evaluator/", "secret.json", "training/private", "do-not-forward"):
            self.assertNotIn(forbidden, serialized)

    def test_success_dispatches_in_order_and_returns_actual_prepared_contract(self):
        with TemporaryDirectory() as temporary:
            plan = b.plan_config({}, str(Path(temporary) / "work"))
            with mock.patch.object(b.sys, "platform", "linux"), \
                 mock.patch.object(b.os, "killpg", create=True), \
                 mock.patch.object(b, "_dispatch", side_effect=[
                     (synthetic_material(), STOPPED.copy()),
                     (synthetic_installed(), STOPPED.copy())]) as dispatch:
                result = b.prepare_model_environment(plan, enable_model=True,
                                                     gate_receipt=GATE, deadline_seconds=100)
            self.assertEqual([call.args[0] for call in dispatch.call_args_list], ["material", "install"])
            self.assertEqual(dispatch.call_args_list[0].args[3], dispatch.call_args_list[1].args[3])
            self.assertEqual(result["python_command"], synthetic_installed()["python_command"])
            self.assertEqual(result["environment_plan_sha256"], plan["plan_sha256"])
            self.assertEqual(result["actual_environment_lock_sha256"], "a" * 64)
            self.assertEqual(result["child_stop_proof"], {"material": STOPPED, "install": STOPPED})
            self.assertEqual(result["gpu_calls"], 0)
            self.assertGreaterEqual(result["bootstrap_wall_seconds"], 0)

    def test_failure_retains_elapsed_stop_proofs_and_never_retries(self):
        for confirmed in (True, False):
            with self.subTest(confirmed=confirmed), TemporaryDirectory() as temporary:
                plan = b.plan_config({}, str(Path(temporary) / "work"))
                failed = b.BootstrapError("synthetic child failed")
                failed.child_stop_proof = {**STOPPED, "owned_group_stopped": confirmed}
                with mock.patch.object(b.sys, "platform", "linux"), \
                     mock.patch.object(b.os, "killpg", create=True), \
                     mock.patch.object(b, "_dispatch", side_effect=[
                         (synthetic_material(), STOPPED.copy()), failed]) as dispatch:
                    with self.assertRaises(b.BootstrapError) as caught:
                        b.prepare_model_environment(plan, enable_model=True, gate_receipt=GATE)
                self.assertEqual(dispatch.call_count, 2)
                self.assertEqual(caught.exception.owned_descendants_stopped, confirmed)
                self.assertEqual(caught.exception.child_stop_proof["material"], STOPPED)
                self.assertEqual(caught.exception.child_stop_proof["install"], failed.child_stop_proof)
                self.assertGreaterEqual(caught.exception.bootstrap_wall_seconds, 0)

    def test_pre_dispatch_failure_marks_both_phases_not_dispatched(self):
        plan = b.plan_config({}, "/synthetic/work")
        with mock.patch.object(b.sys, "platform", "linux"), \
             mock.patch.object(b.os, "killpg", create=True), \
             mock.patch.object(b, "_safe", side_effect=OSError("synthetic directory failure")):
            with self.assertRaises(b.BootstrapError) as caught:
                b.prepare_model_environment(plan, enable_model=True, gate_receipt=GATE)
        self.assertTrue(caught.exception.owned_descendants_stopped)
        self.assertTrue(all(not proof["dispatched"] for proof in caught.exception.child_stop_proof.values()))

    def test_invalid_completed_response_retains_stop_proof(self):
        with TemporaryDirectory() as temporary:
            work = Path(temporary)
            plan = b.plan_config({}, str(work))
            with mock.patch.object(b, "_supervise", return_value=STOPPED.copy()), \
                 mock.patch.object(b, "_controller_identity", return_value={"pid": 1, "birth": "1"}), \
                 mock.patch.object(b, "_read_json", side_effect=ValueError("synthetic malformed response")):
                with self.assertRaises(b.BootstrapError) as caught:
                    b._dispatch("material", plan, work, time.monotonic() + 10)
            self.assertEqual(caught.exception.child_stop_proof, STOPPED)
            self.assertEqual(len(list(work.glob("*.request.json"))), 1)

    def test_partial_environment_is_revalidated_not_reinstalled(self):
        with TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / "environment-cp312-cu128").mkdir()
            source_lock = work / "runtime/research/arc-next-line/model-source-lock.json"
            source_lock.parent.mkdir(parents=True)
            source_lock.write_text('{"synthetic":true}')
            roots = {**synthetic_material()["roots"], "runtime": str(work)}
            interpreter = mock.Mock()
            interpreter.validate_interpreter.return_value = {"python_executable": sys.executable}
            environment = mock.Mock()
            runtime = mock.Mock()
            runtime._runtime_environment.side_effect = ValueError("synthetic partial environment rejected")
            helpers = {"arc_next_offline_interpreter.py": interpreter,
                       "arc_next_offline_environment.py": environment,
                       "arc_next_offline_runtime.py": runtime}
            with mock.patch.object(b, "_helpers", return_value=helpers), \
                 mock.patch.object(b, "SOURCE_LOCK_SHA256", b._sha(source_lock)):
                with self.assertRaisesRegex(ValueError, "partial environment"):
                    b._install_child(b.plan_config({}, str(work)), {"roots": roots})
            interpreter.validate_interpreter.assert_called_once()
            environment.install_offline.assert_not_called()
            runtime._runtime_environment.assert_called_once()

    def test_mock_nonzero_child_still_proves_stop_and_isolation(self):
        with TemporaryDirectory() as temporary:
            process = mock.Mock(pid=1234, returncode=1)
            process.poll.return_value = 1
            with mock.patch.object(b.sys, "platform", "linux"), \
                 mock.patch.object(b.os, "killpg", create=True), \
                 mock.patch.dict(b.os.environ, {"PYTHONPATH": "untrusted", "PIP_INDEX_URL": "untrusted"}), \
                 mock.patch.object(b.subprocess, "Popen", return_value=process) as popen, \
                 mock.patch.object(b, "_process_identity", return_value={"birth": "1000"}), \
                 mock.patch.object(b, "_stop_group", return_value=STOPPED.copy()) as stop:
                with self.assertRaises(b.BootstrapError) as caught:
                    b._supervise(["synthetic-command"], Path(temporary) / "child.log", time.monotonic() + 10)
            self.assertTrue(caught.exception.child_stop_proof["owned_group_stopped"])
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertTrue(popen.call_args.kwargs["close_fds"])
            self.assertNotIn("PYTHONPATH", popen.call_args.kwargs["env"])
            self.assertNotIn("PIP_INDEX_URL", popen.call_args.kwargs["env"])
            stop.assert_called_once_with(process, "1000")

    def test_mock_unconfirmed_child_stop_is_never_reported_safe(self):
        with TemporaryDirectory() as temporary:
            process = mock.Mock(pid=1234, returncode=1)
            process.poll.return_value = 1
            with mock.patch.object(b.sys, "platform", "linux"), \
                 mock.patch.object(b.os, "killpg", create=True), \
                 mock.patch.object(b.subprocess, "Popen", return_value=process), \
                 mock.patch.object(b, "_process_identity", return_value={"birth": "1000"}), \
                 mock.patch.object(b, "_stop_group", side_effect=b.BootstrapError("synthetic stop failure")):
                with self.assertRaises(b.BootstrapError) as caught:
                    b._supervise(["synthetic-command"], Path(temporary) / "child.log", time.monotonic() + 10)
            self.assertFalse(caught.exception.owned_descendants_stopped)
            self.assertFalse(caught.exception.child_stop_proof["owned_group_stopped"])

    def test_changed_child_request_fails_before_helpers(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "request.json"
            path.write_text('{"synthetic":true}')
            with mock.patch.object(b, "_helpers", side_effect=AssertionError("backend import")):
                with self.assertRaisesRegex(b.BootstrapError, "request bytes"):
                    b._child(path, "0" * 64)

    def test_parent_birth_reuse_and_zombie_are_not_alive(self):
        identity = {"pid": 123, "birth": "1000"}
        for current in ({"pid": 123, "birth": "1001", "state": "S"},
                        {"pid": 123, "birth": "1000", "state": "Z"}):
            with mock.patch.object(b, "_process_identity", return_value=current):
                self.assertFalse(b._same_process(identity))
        with mock.patch.object(b, "_process_identity", side_effect=FileNotFoundError):
            self.assertFalse(b._same_process(identity))

    def test_group_pid_reuse_refuses_signal(self):
        with mock.patch.object(b, "_process_identity", return_value={"birth": "2000"}):
            with self.assertRaisesRegex(b.BootstrapError, "PID was reused"):
                b._assert_leader_birth(123, "1000")

    def test_watchdog_must_acknowledge_before_any_material_work(self):
        with TemporaryDirectory() as temporary:
            plan = b.plan_config({}, temporary)
            request = {"plan": plan, "result_path": str(Path(temporary) / "result.json"),
                       "phase": "material", "material": None}
            with mock.patch.object(b, "_bound_request", return_value=request), \
                 mock.patch.object(b, "_start_watchdog", side_effect=b.BootstrapError("synthetic no readiness")), \
                 mock.patch.object(b, "_material_child", side_effect=AssertionError("must remain unstarted")) as material:
                with self.assertRaisesRegex(b.BootstrapError, "no readiness"):
                    b._child("synthetic request", "synthetic hash")
                material.assert_not_called()


# The following programs exercise the real supervisor only. They cannot call
# material/install functions and use no Dataset paths, model code or GPU.
SYNTHETIC_WORKER = r'''
import importlib.util, json, pathlib, sys, time
spec = importlib.util.spec_from_file_location("synthetic_bootstrap", sys.argv[1])
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
request = b._bound_request(sys.argv[2], sys.argv[3])
receipt = b._start_watchdog(sys.argv[2], sys.argv[3], request)
pathlib.Path(sys.argv[4]).write_text(json.dumps(receipt))
time.sleep(30)
'''

SYNTHETIC_CONTROLLER = r'''
import importlib.util, json, pathlib, subprocess, sys, time
spec = importlib.util.spec_from_file_location("synthetic_bootstrap", sys.argv[1])
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
work = pathlib.Path(sys.argv[2])
request = {"format": b.FORMAT, "phase": "material", "plan": b.plan_config({}, str(work)),
    "material": None, "module_sha256": b._sha(sys.argv[1]),
    "controller": b._controller_identity(), "deadline_monotonic": time.monotonic() + float(sys.argv[3]),
    "result_path": str(work / "result.json")}
path = work / "synthetic-watchdog-request.json"
sha = b._write_new(path, request)
worker = subprocess.Popen([sys.executable, "-I", "-B", "-S", "-c", sys.argv[4],
    sys.argv[1], str(path), sha, str(work / "synthetic-worker-ready.json")], start_new_session=True)
print(json.dumps(b._process_identity(worker.pid)), flush=True)
time.sleep(30)
'''


@unittest.skipUnless(sys.platform.startswith("linux") and hasattr(os, "killpg"),
                     "real Linux session/group supervision unavailable on this host")
class LinuxSyntheticProcessTests(unittest.TestCase):
    def _watchdog_case(self, *, kill_controller):
        with TemporaryDirectory() as temporary:
            work = Path(temporary)
            command = [sys.executable, "-I", "-B", "-S", "-c", SYNTHETIC_CONTROLLER,
                       str(Path(b.__file__).absolute()), temporary,
                       "20" if kill_controller else "1.5", SYNTHETIC_WORKER]
            controller, identity = None, None
            try:
                with (work / "synthetic-process.log").open("wb") as log:
                    controller = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log,
                                                  start_new_session=True, close_fds=True)
                    readable, _, _ = select.select([controller.stdout], [], [], 5)
                    self.assertTrue(readable, "synthetic controller startup did not complete")
                    identity = json.loads(controller.stdout.readline())
                    controller.stdout.close()
                    end = time.monotonic() + 5
                    while not (work / "synthetic-worker-ready.json").is_file() and time.monotonic() < end:
                        time.sleep(0.02)
                    self.assertTrue((work / "synthetic-worker-ready.json").is_file())
                    if kill_controller:
                        controller.terminate()
                        controller.wait(timeout=3)
                    end = time.monotonic() + 5
                    while b._same_process(identity) and time.monotonic() < end:
                        time.sleep(0.02)
                    self.assertFalse(b._same_process(identity), "watchdog failed to stop its worker")
                    if not kill_controller:
                        self.assertIsNone(controller.poll(), "independent deadline test lost its controller")
                    end = time.monotonic() + 2
                    while any(row["state"] != "Z" for row in b._group_members(identity["pid"])) and time.monotonic() < end:
                        time.sleep(0.02)
                    self.assertFalse(any(row["state"] != "Z" for row in b._group_members(identity["pid"])))
            finally:
                if controller is not None:
                    if controller.poll() is None:
                        controller.kill()
                    controller.wait(timeout=3)
                if identity is not None and any(row["state"] != "Z" for row in b._group_members(identity["pid"])):
                    try:
                        os.killpg(identity["pid"], signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_independent_watchdog_stops_worker_after_controller_death(self):
        self._watchdog_case(kill_controller=True)

    def test_independent_watchdog_enforces_deadline_with_live_controller(self):
        self._watchdog_case(kill_controller=False)

    def test_normal_child_exit_reaps_leader_and_stops_spawned_group_member(self):
        with TemporaryDirectory() as temporary:
            command = [sys.executable, "-I", "-B", "-S", "-c",
                       "import subprocess,sys; subprocess.Popen([sys.executable,'-I','-B','-S','-c','import time; time.sleep(30)'])"]
            proof = b._supervise(command, Path(temporary) / "child.log", time.monotonic() + 5)
            self.assertTrue(proof["owned_group_stopped"])
            self.assertTrue(proof["leader_reaped"])
            self.assertEqual(proof["live_group_members"], 0)

    def test_deadline_kills_and_reaps_synthetic_child(self):
        with TemporaryDirectory() as temporary:
            command = [sys.executable, "-I", "-B", "-S", "-c", "import time; time.sleep(30)"]
            with self.assertRaises(b.BootstrapError) as caught:
                b._supervise(command, Path(temporary) / "child.log", time.monotonic() + 0.2)
            self.assertTrue(caught.exception.child_stop_proof["owned_group_stopped"])
            self.assertTrue(caught.exception.child_stop_proof["leader_reaped"])


if __name__ == "__main__":
    unittest.main()

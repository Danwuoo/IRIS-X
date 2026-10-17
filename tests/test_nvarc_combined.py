"""Offline process, hardware and inert-package regressions, without ML mocks."""

import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from irisx.arc_nvarc_combined import (LOG_LIMIT, RUN, atomic, check_logical_device, member,
                                    read, require_live_authorization, select_devices,
                                    sha, supervise, validate_plan)
from irisx.errors import ValidationError
from irisx.arc_nvarc_combined_worker import _run_prepared, partial_m2_counts
from irisx.canonical import digest_value
from irisx.arc_nvarc_candidates import FixtureCandidateBackend, solve_task
from tools.stage_nvarc_combined import DRAFT, stage, verify_inputs
from tools.preflight_nvarc_combined import preflight

ROOT = Path(__file__).resolve().parents[1]
CHILD = ROOT / "tests/nvarc_combined_fixture_child.py"


def devices(count=2):
    return [{"index": i, "uuid": "GPU-fixture-" + str(i), "name": "NVIDIA L4", "bf16": True,
             "memory_bytes": 24 * 10**9, "memory_mib": 23034} for i in range(count)]


def fixture_validator(root):
    value = read(root / "fixture-result.json")
    if value.get("kind") != "synthetic-process-fixture" or value.get("counters") != {"fixture_calls": 1}:
        raise ValidationError("synthetic fixture result differs")
    return value["counters"]


class RetirementFixtureClock:
    """Exclude only bounded fixture admission, never retirement or callbacks.

    These tests exercise retirement, not interpreter startup throughput. Keep
    real monotonic time running everywhere except an actual, bounded child-exit
    handshake. Replacing only runtime.time also leaves subprocess wait timeouts
    and the other tests' deadline/readiness clocks real.
    """

    def __init__(self):
        self._real_monotonic = time.monotonic
        self.sleep = time.sleep
        self._lock = threading.Lock()
        self._paused_at = None
        self.excluded_seconds = 0
        self.processes = []

    def monotonic(self):
        with self._lock:
            now = self._real_monotonic() if self._paused_at is None else self._paused_at
            return now - self.excluded_seconds

    def wait_for_exit(self, process, timeout):
        with self._lock:
            if self._paused_at is not None:
                raise RuntimeError("nested retirement fixture admission")
            self._paused_at = self._real_monotonic()
        try:
            # This is the original Popen, not a fabricated successful poll.
            process.wait(timeout=timeout)
        finally:
            with self._lock:
                self.excluded_seconds += self._real_monotonic() - self._paused_at
                self._paused_at = None


class AtomicLedgerTests(unittest.TestCase):
    def test_child_json_rejects_ambiguous_fields_and_nonfinite_values(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx") as temp:
            path = Path(temp) / "child.json"
            for raw in ('{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '{"x":1,"x":2}'):
                with self.subTest(raw=raw):
                    path.write_text(raw)
                    with self.assertRaises(ValidationError):
                        read(path)
            path.write_text('{"x":1.25}')
            self.assertEqual({"x": 1.25}, read(path))

    def test_transient_windows_lock_keeps_old_complete_ledger_until_replace(self):
        import irisx.arc_nvarc_combined as runtime
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.json"
            atomic(path, {"reserved": 1})
            original = runtime.os.replace
            observed = []

            def locked_twice(source, target):
                observed.append(read(path))
                if len(observed) <= 2:
                    error = PermissionError("injected Windows sharing lock")
                    error.winerror = 32
                    raise error
                return original(source, target)

            with patch.object(runtime.os, "replace", side_effect=locked_twice), patch.object(runtime.time, "sleep"):
                atomic(path, {"reserved": 2})
            self.assertEqual([{"reserved": 1}] * 3, observed)
            self.assertEqual({"reserved": 2}, read(path))
            persistent = PermissionError("persistent Windows access denial")
            persistent.winerror = 5
            with patch.object(runtime.os, "replace", side_effect=persistent) as replace, patch.object(runtime.time, "sleep"):
                with self.assertRaises(PermissionError):
                    atomic(path, {"reserved": 3})
            self.assertEqual(5, replace.call_count)
            self.assertEqual({"reserved": 2}, read(path))
            with patch.object(runtime.os, "replace", side_effect=PermissionError("ordinary permission denial")) as replace:
                with self.assertRaises(PermissionError):
                    atomic(path, {"reserved": 4})
            self.assertEqual(1, replace.call_count)


class CombinedProcessTests(unittest.TestCase):
    @contextmanager
    def retirement_fixture(self, *, admission_seconds=5):
        import irisx.arc_nvarc_combined as runtime
        clock = RetirementFixtureClock()
        original = runtime._launch_worker

        def admit(command, **kwargs):
            mode = command[command.index("--mode") + 1]
            if mode not in {"success", "pre-ready-fail"}:
                raise RuntimeError("retirement admission requires a tiny no-descendant fixture")
            # Launcher setup/error cleanup retains a running clock. Only the
            # returned child's bounded wait excludes cold startup and teardown.
            process, job = original(command, **kwargs)
            clock.processes.append(process)
            try:
                clock.wait_for_exit(process, admission_seconds)
            except BaseException as primary:
                # wait_for_exit resumed time before any cleanup deadline loop.
                try:
                    runtime._reap(process, job, .3, .3)
                except BaseException as cleanup:
                    primary.add_note("fixture admission cleanup failed: " + str(cleanup))
                    for note in runtime._force_reap(process, job, .3):
                        primary.add_note("fixture admission fallback failed: " + note)
                finally:
                    for pipe in (process.stdout, process.stderr):
                        pipe.close()
                if isinstance(primary, subprocess.TimeoutExpired):
                    raise RuntimeError("retirement fixture exit admission exceeded real timeout") from primary
                raise
            return process, job

        with patch.object(runtime, "time", clock), \
                patch.object(runtime, "_launch_worker", side_effect=admit):
            yield clock

    def launch(self, modes, *, work_seconds=3, readiness=0.6, setup=None,
               startup_delays=(0, 0), work_delays=(0.1, 0.1), admit_faults=False, terminal_reserve=2,
               diagnostics=None, fixture_clock=None):
        root = Path(self.temp.name) / ("out-" + str(self.serial))
        self.serial += 1
        hardware = select_devices(devices(4))
        children = {b: {"device": hardware["assignments"][b], "command": [sys.executable, str(CHILD),
            "--output", str(root / b), "--branch", b, "--mode", modes[i],
            "--startup-delay", str(startup_delays[i]), "--work-delay", str(work_delays[i]),
            "--device", json.dumps(hardware["assignments"][b])]} for i, b in enumerate(("m2", "m3"))}
        for branch, callback in (diagnostics or {}).items():
            children[branch]["diagnostics"] = callback
        monotonic = time.monotonic if fixture_clock is None else fixture_clock.monotonic
        now = monotonic()
        def run():
            return supervise(children, root, run_id="fixture-combined", plan_digest="fixture-plan",
                deadline=now + work_seconds, terminal_deadline=now + work_seconds + terminal_reserve,
                readiness_seconds=readiness, validators={b: fixture_validator for b in children},
                setup=setup, term_seconds=0.3, kill_seconds=0.3)

        if admit_faults:
            import irisx.arc_nvarc_combined as runtime
            original = runtime._launch_worker

            def admit(command, **kwargs):
                process, job = original(command, **kwargs)
                branch = command[command.index("--branch") + 1]
                # Fault classification requires the fixture to reach its fault
                # protocol, independently of interpreter/bootstrap scheduling.
                # Startup still consumes the unchanged overall work deadline;
                # timeout tests use the real, unmodified launch path below.
                while not (root / branch / "model-ready.json").is_file() and process.poll() is None:
                    if time.monotonic() >= now + work_seconds:
                        runtime._reap(process, job, .3, .3)
                        raise RuntimeError("fixture fault admission exceeded overall work budget")
                    time.sleep(.005)
                return process, job

            with patch.object(runtime, "_launch_worker", side_effect=admit):
                report = run()
        else:
            report = run()
        self.assertEqual(report, read(root / "aggregate-terminal.json"))
        self.assertLess(monotonic() - now, work_seconds + 2)
        self.assertEqual(0, report["retries"])
        self.assertTrue(all(r["launch_count"] <= 1 for r in report["branches"].values()))
        return root, report

    def test_retirement_fixture_excludes_only_bounded_real_child_admission(self):
        real_started = time.monotonic()
        with self.retirement_fixture() as clock:
            started = clock.monotonic()
            _, report = self.launch(["success", "success"], work_seconds=.35,
                                    terminal_reserve=.2, startup_delays=(.6, .6),
                                    fixture_clock=clock)
            self.assertLess(clock.monotonic() - started, .7)
            self.assertGreaterEqual(clock.excluded_seconds, 1.2)
            self.assertEqual("complete", report["outcome"])
            for result in report["branches"].values():
                self.assertEqual(0, result["exit_code_before_stop"])
                self.assertLess(result["disposition_observed_seconds"], .35)
                self.assertTrue(result["process_exit_confirmed"])
                self.assertTrue(result["log_drain_confirmed"])
            self.assertTrue(all(p.poll() is not None and p.stdout.closed and p.stderr.closed
                                for p in clock.processes))
        self.assertGreaterEqual(time.monotonic() - real_started, 1.2)

    def test_retirement_fixture_admission_timeout_keeps_real_cleanup_bounded(self):
        import irisx.arc_nvarc_combined as runtime
        original_reap = runtime._reap
        cleanups = []

        def observe_cleanup(process, *args):
            observation = original_reap(process, *args)
            cleanups.append((process, observation))
            return observation

        with patch.object(runtime, "_reap", side_effect=observe_cleanup), \
                self.retirement_fixture(admission_seconds=.05) as clock:
            _, report = self.launch(["success", "success"], startup_delays=(60, 0),
                                    fixture_clock=clock)
            self.assertEqual("failed", report["branches"]["m2"]["outcome"])
            self.assertIn("retirement fixture exit admission exceeded real timeout",
                          report["branches"]["m2"]["error"])
            self.assertIsNone(clock._paused_at)
            self.assertEqual(2, len(clock.processes))
            self.assertTrue(all(p.poll() is not None and p.stdout.closed and p.stderr.closed
                                for p in clock.processes))
            owned_cleanup = [value for process, value in cleanups if process is clock.processes[0]]
            self.assertEqual(1, len(owned_cleanup))
            if os.name == "nt" or sys.platform.startswith("linux"):
                self.assertEqual(0, owned_cleanup[0]["active_processes_after_termination"])

    def setUp(self):
        self.temp = SimpleNamespace(name=tempfile.mkdtemp(dir=ROOT / ".irisx", prefix="combined-cpu-"))
        self.serial = 0

    def tearDown(self):
        result = self._outcome.result
        failed = any(test is self or getattr(test, "test_case", None) is self
                     for test, _ in [*result.failures, *result.errors])
        if failed:
            atomic(Path(self.temp.name) / "failed-test.json", {
                "test_id": self.id(), "synthetic_cpu_fixture": True,
                "contains_evaluator_truth": False,
                "evidence": "original process outputs retained after failed assertion/error"})
        else:
            shutil.rmtree(self.temp.name)

    def test_two_successes_use_distinct_device_environments_and_stagger(self):
        root, report = self.launch(["success", "success"])
        self.assertEqual("complete", report["outcome"])
        for i, b in enumerate(("m2", "m3")):
            self.assertEqual("GPU-fixture-" + str(i), read(root / b / "fixture-result.json")["visible_devices"])
        events = [json.loads(line) for line in (root / "startup-events.jsonl").read_text().splitlines()]
        positions = {(e["branch"], e["phase"]): i for i, e in enumerate(events)}
        self.assertLess(positions["m2", "model-ready"], positions["m3", "launch"])

    def test_failure_before_ready_during_work_and_artifact_failures_keep_sibling(self):
        for mode in ("pre-ready-fail", "work-fail", "tampered", "no-result", "forged-counters"):
            with self.subTest(mode=mode):
                root, report = self.launch([mode, "success"], admit_faults=True)
                self.assertEqual("partial", report["outcome"], report)
                self.assertEqual("failed", report["branches"]["m2"]["outcome"])
                self.assertEqual("complete", report["branches"]["m3"]["outcome"])
                self.assertIsNotNone(report["branches"]["m2"]["exit_code_before_stop"])
                if mode not in {"pre-ready-fail", "work-fail"}:
                    self.assertTrue((root / "m2/worker-terminal.json").is_file())

    def test_slow_interpreter_startup_is_timeout_before_tamper_and_keeps_sibling(self):
        root, report = self.launch(["tampered", "success"], startup_delays=(.8, 0))
        self.assertEqual("partial", report["outcome"])
        self.assertEqual("timed-out", report["branches"]["m2"]["outcome"])
        self.assertFalse((root / "m2/model-ready.json").exists())
        self.assertFalse((root / "m2/worker-terminal.json").exists())
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_late_ready_published_during_parent_poll_stall_cannot_pass_readiness(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._launch_worker

        def stalled_poll(command, **kwargs):
            process, job = original(command, **kwargs)
            if command[command.index("--branch") + 1] == "m2":
                poll = process.poll
                first = True

                def delayed_poll():
                    nonlocal first
                    if first:
                        first = False
                        time.sleep(.4)
                    return poll()
                process.poll = delayed_poll
            return process, job

        with patch.object(runtime, "_launch_worker", side_effect=stalled_poll):
            root, report = self.launch(["success", "success"], startup_delays=(.25, 0), readiness=.15)
        self.assertTrue((root / "m2/model-ready.json").exists())
        self.assertEqual("timed-out", report["branches"]["m2"]["outcome"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_fault_admission_is_independent_of_slow_bootstrap_without_extending_ready_bound(self):
        root, report = self.launch(["tampered", "success"], startup_delays=(.8, 0), admit_faults=True)
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertIn("child artifact differs", report["branches"]["m2"]["error"])
        self.assertEqual({}, read(root / "m2/fixture-result.json"))
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_malformed_or_foreign_child_json_fails_closed_without_poisoning_aggregate(self):
        for mode in ("foreign-ready", "duplicate-ready", "nonfinite-diagnostics"):
            with self.subTest(mode=mode):
                _, report = self.launch([mode, "success"], admit_faults=True)
                self.assertEqual("failed", report["branches"]["m2"]["outcome"])
                self.assertEqual("complete", report["branches"]["m3"]["outcome"])
                self.assertEqual("partial", report["outcome"])

    def test_counter_and_device_bindings_preserve_json_types(self):
        for mode in ("boolean-counters", "float-counters", "boolean-ready-device", "boolean-terminal-device"):
            with self.subTest(mode=mode):
                _, report = self.launch([mode, "success"], admit_faults=True)
                self.assertEqual("failed", report["branches"]["m2"]["outcome"])
                self.assertEqual("complete", report["branches"]["m3"]["outcome"])
                self.assertEqual("partial", report["outcome"])

    def test_launch_cleanup_notes_preserve_primary_and_keep_sibling(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._launch_worker
        attempted = []

        def failed_launch(command, **kwargs):
            branch = command[command.index("--branch") + 1]
            attempted.append(branch)
            if branch == "m2":
                error = RuntimeError("injected primary launch failure")
                error.add_note("injected secondary tree cleanup failure")
                raise error
            return original(command, **kwargs)

        with patch.object(runtime, "_launch_worker", side_effect=failed_launch):
            _, report = self.launch(["success", "success"])
        self.assertEqual(["m2", "m3"], attempted)
        self.assertEqual("injected primary launch failure", report["branches"]["m2"]["error"])
        self.assertEqual(["injected secondary tree cleanup failure"],
                         report["branches"]["m2"]["launch_cleanup_errors"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_invalid_deadline_contract_rejects_before_output_or_launch(self):
        now = time.monotonic()
        defaults = dict(deadline=now + 3, terminal_deadline=now + 5, readiness_seconds=.6,
                        term_seconds=.3, kill_seconds=.3)
        children = {b: {"command": [sys.executable, "-c", "raise RuntimeError('must not launch')"]}
                    for b in ("m2", "m3")}
        for change in ({"deadline": float("nan")}, {"terminal_deadline": now + 2},
                       {"readiness_seconds": 0}, {"readiness_seconds": True}, {"kill_seconds": -1}):
            with self.subTest(change=change):
                root = Path(self.temp.name) / "invalid-contract"
                with self.assertRaisesRegex(ValidationError, "finite ordered"):
                    supervise(children, root, run_id="fixture-combined", plan_digest="fixture-plan",
                              validators={b: fixture_validator for b in children}, **{**defaults, **change})
                self.assertFalse(root.exists())

    def test_delayed_job_assignment_cannot_race_fast_worker_exit(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._windows_job

        def delayed(process):
            time.sleep(0.35)
            return original(process)

        with patch.object(runtime, "_windows_job", side_effect=delayed):
            _, report = self.launch(["pre-ready-fail", "success"], work_seconds=5, readiness=2)
        self.assertEqual("partial", report["outcome"], report)
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assertTrue(all(row["launch_count"] == 1 for row in report["branches"].values()))

    def test_pre_ready_hang_is_bounded_and_sibling_launches(self):
        _, report = self.launch(["pre-ready-hang", "success"])
        self.assertEqual("partial", report["outcome"])
        self.assertEqual("timed-out", report["branches"]["m2"]["outcome"])
        self.assertIn("model-ready", report["branches"]["m2"]["error"])
        self.assertIsNone(report["branches"]["m2"]["actual_counters"])

    def test_global_timeout_reaps_both_and_retains_unknown_counts(self):
        _, report = self.launch(["work-hang", "work-hang"], work_seconds=0.8)
        self.assertEqual("timed-out", report["outcome"])
        self.assertTrue(all(r["return_code"] is not None and r["actual_counters"] is None
                            for r in report["branches"].values()))

    def test_worker_diagnostic_cannot_overwrite_parent_timeout_cause(self):
        _, report = self.launch(["work-hang-with-diagnostic-error", "success"], work_seconds=.8)
        m2 = report["branches"]["m2"]
        self.assertEqual("timed-out", m2["outcome"])
        self.assertEqual("global monotonic work deadline exceeded", m2["supervisor_error"])
        self.assertEqual(m2["supervisor_error"], m2["error"])
        self.assertEqual("earlier worker note", m2["worker_error"]["message"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_ready_io_crossing_work_deadline_cannot_verify_or_admit_sibling(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.read

        def delayed_ready(path):
            if path.parent.name == "m2" and path.name == "model-ready.json":
                time.sleep(.4)
            return original(path)

        with patch.object(runtime, "read", side_effect=delayed_ready):
            root, report = self.launch(["success", "success"], work_seconds=.3)
        self.assertEqual("timed-out", report["outcome"])
        self.assertEqual("timed-out", report["branches"]["m2"]["outcome"])
        self.assertNotIn("verification", report["branches"]["m2"])
        self.assertEqual(0, report["branches"]["m3"]["launch_count"])
        self.assertFalse((root / "m3").exists())

    def test_admission_io_crossing_work_deadline_never_calls_launcher(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.Path.mkdir
        root = Path(self.temp.name) / ("out-" + str(self.serial))

        def delayed_directory(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == root / "m2":
                time.sleep(.4)
            return result

        with patch.object(runtime.Path, "mkdir", new=delayed_directory), \
                patch.object(runtime, "_launch_worker", side_effect=AssertionError("must not launch")) as launch:
            _, report = self.launch(["success", "success"], work_seconds=.3)
        self.assertEqual(0, launch.call_count)
        self.assertEqual("timed-out", report["outcome"])
        self.assertTrue(all(r["launch_count"] == 0 for r in report["branches"].values()))

    def test_shared_failure_launches_neither(self):
        def fail():
            raise ValidationError("fixture shared setup failed")
        _, report = self.launch(["success", "success"], setup=fail)
        self.assertEqual("failed", report["outcome"])
        self.assertEqual("ValidationError", report["shared_error"]["type"])
        self.assertTrue(all(r["launch_count"] == 0 for r in report["branches"].values()))

    def test_sibling_directory_acquisition_error_does_not_cancel_ready_worker(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.Path.mkdir
        root = Path(self.temp.name) / ("out-" + str(self.serial))

        def denied_directory(path, *args, **kwargs):
            if path == root / "m3":
                raise PermissionError("injected M3-only output directory denial")
            return original(path, *args, **kwargs)

        with patch.object(runtime.Path, "mkdir", new=denied_directory):
            _, report = self.launch(["success", "success"], work_delays=(.25, .1))
        self.assertEqual("complete", report["branches"]["m2"]["outcome"])
        self.assertEqual("failed", report["branches"]["m3"]["outcome"])
        self.assertEqual(0, report["branches"]["m3"]["launch_count"])
        self.assertIsNone(report["shared_error"])

    def test_cleanup_errors_still_reap_all_and_write_aggregate(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._reap
        calls = []
        def fail_after_reap(*args):
            original(*args)
            calls.append(args[0].pid)
            raise OSError("injected cleanup report failure after actual reap")
        with patch.object(runtime, "_reap", side_effect=fail_after_reap):
            _, report = self.launch(["work-hang", "work-hang"], work_seconds=0.8)
        self.assertEqual(2, len(calls))
        self.assertTrue(all(r["cleanup_errors"] for r in report["branches"].values()))
        self.assertEqual("failed", report["outcome"])

    def test_large_logs_drain_without_deadlock_and_have_bounded_retention(self):
        root, report = self.launch(["log-flood", "success"])
        self.assertEqual("complete", report["outcome"])
        self.assertEqual(LOG_LIMIT, (root / "m2/stdout.log").stat().st_size)
        self.assertEqual(LOG_LIMIT, (root / "m2/stderr.log").stat().st_size)

    def test_descendant_is_cleaned_after_primary_worker_exits(self):
        root, report = self.launch(["descendant", "success"])
        self.assertEqual("complete", report["outcome"])
        self.assert_descendant_gone(root, report)

    def assert_descendant_gone(self, root, report):
        pid = read(root / "m2/descendant.json")["pid"]
        if os.name == "nt":
            cleanup = report["branches"]["m2"]["process_tree_cleanup"]
            self.assertEqual("owned-windows-job", cleanup["kind"])
            self.assertIn(pid, cleanup["initial_process_ids"])
            self.assertEqual(0, cleanup["active_processes_after_termination"])
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, pid)
            if handle:
                status = wintypes.DWORD()
                kernel.GetExitCodeProcess(handle, ctypes.byref(status))
                kernel.CloseHandle(handle)
                self.assertNotEqual(259, status.value)
        else:
            status_path = Path("/proc") / str(pid) / "stat"
            if status_path.exists():
                self.assertEqual("Z", status_path.read_text().split()[2])

    def test_delayed_job_assignment_contains_redirector_and_descendant(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._windows_job

        def delayed(process):
            # An unsuspended venv redirector can spawn its interpreter while
            # this delay elapses, even though Python code waits on the pipe gate.
            time.sleep(0.35)
            return original(process)

        with patch.object(runtime, "_windows_job", side_effect=delayed):
            root, report = self.launch(["descendant", "success"], work_seconds=5, readiness=2)
        self.assertEqual("complete", report["outcome"])
        self.assert_descendant_gone(root, report)
        self.assertTrue(all(row["launch_count"] == 1 for row in report["branches"].values()))

    def test_log_drain_uses_terminal_reserve_and_closes_files_before_completion(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._drain

        def delayed_close(pipe, path):
            original(pipe, path)
            # Retain the log lock for a finite delay after real EOF. The caller
            # still has its original 3s work + 2s terminal deadline and 0.3s
            # kill grace; complete requires both readers and locks to be gone.
            with path.open("ab"):
                time.sleep(0.45)

        with patch.object(runtime, "_drain", side_effect=delayed_close):
            root, report = self.launch(["descendant", "success"])
        self.assertEqual("complete", report["outcome"])
        self.assert_descendant_gone(root, report)
        for branch in ("m2", "m3"):
            for name in ("stdout.log", "stderr.log"):
                path = root / branch / name
                renamed = path.with_suffix(".closed")
                path.rename(renamed)
                renamed.rename(path)

    def test_failed_branch_log_retirement_cannot_spend_siblings_work_budget(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._drain

        def slow_retirement(pipe, path):
            original(pipe, path)
            if path.parent.name == "m2":
                time.sleep(.9)

        with patch.object(runtime, "_drain", side_effect=slow_retirement):
            _, report = self.launch(["pre-ready-fail", "success"], work_seconds=.6, admit_faults=True)
        self.assertEqual("partial", report["outcome"])
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assertTrue(all(r["retirement_completed"] for r in report["branches"].values()))

    def test_verification_in_terminal_reserve_keeps_ontime_sibling_and_calls_once(self):
        original = fixture_validator
        calls = []

        def slow_validator(root):
            calls.append(root.name)
            if root.name == "m2":
                time.sleep(.7)
            return original(root)

        with patch.dict(globals(), fixture_validator=slow_validator):
            _, report = self.launch(["success", "success"], work_seconds=.6, admit_faults=True)
        self.assertEqual("complete", report["outcome"])
        self.assertCountEqual(["m2", "m3"], calls)
        for result in report["branches"].values():
            self.assertEqual(0, result["exit_code_before_stop"])
            self.assertLess(result["disposition_observed_seconds"], .6)

    def test_validator_return_is_frozen_before_other_callback_mutates_it(self):
        import irisx.arc_nvarc_combined as runtime
        original_sha = runtime.sha
        original_validator = fixture_validator
        shared = {"fixture_calls": 1}
        checked = threading.Event()

        def held_retention(path, **kwargs):
            if path.parent.name == "m2" and path.name == "stdout.log":
                checked.set()
                time.sleep(.2)
            return original_sha(path, **kwargs)

        def mutable_validator(root):
            value = original_validator(root)
            if root.name == "m2":
                return shared
            if not checked.wait(1):
                raise RuntimeError("M2 did not reach reconciled retention")
            shared["fixture_calls"] = 999
            return value

        with patch.object(runtime, "sha", side_effect=held_retention), \
                patch.dict(globals(), fixture_validator=mutable_validator):
            _, report = self.launch(["success", "success"])
        self.assertEqual("complete", report["outcome"])
        self.assertEqual({"fixture_calls": 1}, report["branches"]["m2"]["verification"])
        self.assertEqual({"fixture_calls": 1}, report["branches"]["m2"]["actual_counters"])

    def test_validator_systemexit_is_explicit_failed_evidence_after_owned_cleanup(self):
        original_validator = fixture_validator

        def aborted_validator(root):
            if root.name == "m2":
                raise SystemExit("injected validator abort")
            return original_validator(root)

        with patch.dict(globals(), fixture_validator=aborted_validator):
            _, report = self.launch(["success", "success"])
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertEqual(0, report["branches"]["m2"]["return_code"])
        self.assertIn("injected validator abort", report["branches"]["m2"]["error"])
        self.assertTrue(report["branches"]["m2"]["artifacts"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_expired_retirement_cannot_later_mutate_published_manifest_or_become_complete(self):
        original = fixture_validator
        entered = threading.Event()
        release = threading.Event()
        returned = threading.Event()
        retirement_threads = []

        def blocked_validator(root):
            if root.name == "m2":
                retirement_threads.append(threading.current_thread())
                entered.set()
                # Publication, not elapsed fixture startup time, releases this
                # callback. A real watchdog longer than admission also catches
                # a regression invoking finalization synchronously in parent.
                if not release.wait(10):
                    raise AssertionError("overdue validator was not released after publication")
                try:
                    return original(root)
                finally:
                    returned.set()
            return original(root)

        with self.retirement_fixture() as clock, \
                patch.dict(globals(), fixture_validator=blocked_validator):
            try:
                root, report = self.launch(["success", "success"], work_seconds=.4,
                                           terminal_reserve=.3, fixture_clock=clock)
                frozen = copy.deepcopy(report)
                self.assertTrue(entered.is_set())
                self.assertFalse(returned.is_set())
                self.assertEqual("failed", report["branches"]["m2"]["outcome"])
                self.assertFalse(report["branches"]["m2"]["retirement_completed"])
                self.assertEqual("worker retirement did not terminate",
                                 report["branches"]["m2"]["finalization_error"])
                self.assertEqual("complete", report["branches"]["m3"]["outcome"])
                for result in report["branches"].values():
                    self.assertEqual(0, result["exit_code_before_stop"])
                    self.assertLess(result["disposition_observed_seconds"], .4)
            finally:
                release.set()
                # Validator return is not retirement completion: join its actual
                # thread before restoring the clock or removing its artifacts.
                for thread in retirement_threads:
                    thread.join(timeout=5)
            self.assertTrue(returned.is_set())
            self.assertTrue(all(not thread.is_alive() for thread in retirement_threads))
        self.assertEqual(frozen, report)
        self.assertEqual(frozen, read(root / "aggregate-terminal.json"))

    def test_artifacts_are_verified_after_descendant_termination(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._reap
        root = Path(self.temp.name) / ("out-" + str(self.serial))
        mutated = False

        def final_descendant_write(process, *args):
            nonlocal mutated
            if (root / "m2/descendant.json").exists() and not mutated:
                # A last descendant write after primary exit must be included
                # in verification, rather than trusting a pre-cleanup snapshot.
                (root / "m2/fixture-result.json").write_text("{}")
                mutated = True
            return original(process, *args)

        with patch.object(runtime, "_reap", side_effect=final_descendant_write):
            root, report = self.launch(["descendant", "success"])
        self.assertTrue(mutated)
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertIn("child artifact differs", report["branches"]["m2"]["error"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assert_descendant_gone(root, report)

    def test_log_open_failure_is_observed_and_does_not_hide_tree_or_sibling(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime._drain

        def failed_log(pipe, path):
            if path.parent.name == "m2" and path.name == "stdout.log":
                pipe.close()
                raise PermissionError("injected log-open denial")
            return original(pipe, path)

        with patch.object(runtime, "_drain", side_effect=failed_log):
            root, report = self.launch(["descendant", "success"])
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertIn("injected log-open denial", str(report["branches"]["m2"]["cleanup_errors"]))
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assert_descendant_gone(root, report)

    def test_post_verification_retention_failure_cannot_become_complete(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.sha

        def failed_retention(path, **kwargs):
            if path.parent.name == "m2" and path.name == "stdout.log":
                raise OSError("injected artifact retention failure")
            return original(path, **kwargs)

        with patch.object(runtime, "sha", side_effect=failed_retention):
            _, report = self.launch(["success", "success"])
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertIn("injected artifact retention failure", report["branches"]["m2"]["artifact_error"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_terminal_event_failure_cannot_become_complete(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.event

        def failed_event(output, **kwargs):
            if kwargs["branch"] == "m2" and kwargs["phase"] == "terminal":
                raise OSError("injected terminal event failure")
            return original(output, **kwargs)

        with patch.object(runtime, "event", side_effect=failed_event):
            _, report = self.launch(["success", "success"])
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertIn("injected terminal event failure", report["branches"]["m2"]["event_error"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_prior_event_error_is_reconciled_before_final_branch_terminal_record(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.event

        def failed_ready_event(output, **kwargs):
            if kwargs["branch"] == "m2" and kwargs["phase"] == "model-ready":
                raise OSError("injected earlier ready-event failure")
            return original(output, **kwargs)

        with patch.object(runtime, "event", side_effect=failed_ready_event):
            root, report = self.launch(["success", "success"])
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        events = [json.loads(line) for line in (root / "startup-events.jsonl").read_text().splitlines()]
        terminals = [e for e in events if e["branch"] == "m2" and e["phase"] == "terminal"]
        self.assertTrue(terminals)
        self.assertEqual(report["branches"]["m2"]["outcome"], terminals[-1]["outcome"])
        self.assertEqual("aggregate-terminal.json", terminals[-1]["authoritative_source"])

    def test_slow_terminal_event_cannot_block_siblings_work_watchdog(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.event

        def slow_terminal(output, **kwargs):
            if kwargs["branch"] == "m2" and kwargs["phase"] == "terminal":
                time.sleep(.8)
            return original(output, **kwargs)

        with patch.object(runtime, "event", side_effect=slow_terminal):
            _, report = self.launch(["pre-ready-fail", "success"], work_seconds=.6)
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assertTrue(report["event_drain_confirmed"])

    def test_overdue_terminal_event_cannot_append_complete_after_frozen_failure(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.event

        def late_terminal(output, **kwargs):
            if kwargs["branch"] == "m2" and kwargs["phase"] == "terminal":
                time.sleep(.7)
            return original(output, **kwargs)

        with patch.object(runtime, "event", side_effect=late_terminal):
            root, report = self.launch(["success", "success"], work_seconds=.35, terminal_reserve=.2)
            self.assertEqual("failed", report["branches"]["m2"]["outcome"])
            frozen = copy.deepcopy(report)
            time.sleep(.5)
        self.assertEqual(frozen, report)
        self.assertEqual(frozen, read(root / "aggregate-terminal.json"))
        events = [json.loads(line) for line in (root / "startup-events.jsonl").read_text().splitlines()]
        self.assertFalse(any(e["branch"] == "m2" and e["phase"] == "terminal" and
                             e.get("outcome") == "complete" for e in events))

    def test_partial_log_thread_start_failure_keeps_ownership_and_stops_tree(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.threading.Thread.start
        attempts = 0
        processes = []
        launch = runtime._launch_worker

        def capture(*args, **kwargs):
            process, job = launch(*args, **kwargs)
            processes.append(process)
            return process, job

        def fail_second(thread):
            nonlocal attempts
            if thread._target.__name__ == "drain":
                attempts += 1
                if attempts == 2:
                    raise RuntimeError("injected second reader startup failure")
            return original(thread)

        with patch.object(runtime, "_launch_worker", side_effect=capture), \
                patch.object(runtime.threading.Thread, "start", new=fail_second):
            _, report = self.launch(["pre-ready-hang", "success"])
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assertTrue(all(p.poll() is not None for p in processes))
        self.assertTrue(all(p.stdout.closed and p.stderr.closed for p in processes))

    def test_retirement_thread_start_failure_still_closes_owned_tree_and_is_failed(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.threading.Thread.start
        failed = False

        def fail_retirement(thread):
            nonlocal failed
            if not failed and thread._target.__name__ == "complete_retirement":
                failed = True
                raise RuntimeError("injected retirement startup failure")
            return original(thread)

        with patch.object(runtime.threading.Thread, "start", new=fail_retirement):
            root, report = self.launch(["descendant", "success"])
        self.assertTrue(failed)
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertIn("injected retirement startup failure", str(report["branches"]["m2"]["cleanup_errors"]))
        self.assertTrue(report["branches"]["m2"]["process_exit_confirmed"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assert_descendant_gone(root, report)

    def test_retirement_thread_refusal_defers_log_io_and_keeps_sibling_budget(self):
        import irisx.arc_nvarc_combined as runtime
        original_start = runtime.threading.Thread.start
        original_drain = runtime._drain
        refused = False

        def refuse_once(thread):
            nonlocal refused
            if not refused and thread._target.__name__ == "complete_retirement":
                refused = True
                raise RuntimeError("injected retirement refusal")
            return original_start(thread)

        def delayed_drain(pipe, path):
            original_drain(pipe, path)
            if path.parent.name == "m2":
                time.sleep(.9)

        with patch.object(runtime.threading.Thread, "start", new=refuse_once), \
                patch.object(runtime, "_drain", side_effect=delayed_drain):
            _, report = self.launch(["pre-ready-fail", "success"], work_seconds=.6)
        self.assertTrue(refused)
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])

    def test_retirement_thread_refusal_skips_unbounded_partial_callback_in_parent(self):
        import irisx.arc_nvarc_combined as runtime
        original = runtime.threading.Thread.start
        refused = False
        callback_threads = []

        def refuse_once(thread):
            nonlocal refused
            if not refused and thread._target.__name__ == "complete_retirement":
                refused = True
                raise RuntimeError("injected retirement refusal")
            return original(thread)

        def slow_partial(root):
            callback_threads.append(threading.current_thread().name)
            time.sleep(1)
            return {"counter_evidence": "synthetic slow diagnostic"}

        with self.retirement_fixture() as clock, \
                patch.object(runtime.threading.Thread, "start", new=refuse_once):
            started = clock.monotonic()
            _, report = self.launch(["pre-ready-fail", "success"], work_seconds=.35,
                                    terminal_reserve=.2, diagnostics={"m2": slow_partial},
                                    fixture_clock=clock)
            # Cold fixture admission is excluded, but an erroneously invoked
            # one-second parent callback still consumes this unchanged bound.
            self.assertLess(clock.monotonic() - started, .7)
            self.assertTrue(all(p.poll() is not None and p.stdout.closed and p.stderr.closed
                                for p in clock.processes))
        self.assertTrue(refused)
        self.assertEqual([], callback_threads)
        self.assertEqual("failed", report["branches"]["m2"]["outcome"])
        self.assertTrue(report["branches"]["m2"]["partial_diagnostics_skipped"])
        self.assertIsNone(report["branches"]["m2"]["actual_counters"])
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assertEqual(0, report["branches"]["m3"]["exit_code_before_stop"])
        self.assertLess(report["branches"]["m3"]["disposition_observed_seconds"], .35)

    def test_second_exit_poll_error_cannot_drop_ownership_or_cancel_sibling(self):
        import irisx.arc_nvarc_combined as runtime
        original_launch = runtime._launch_worker
        captured = []

        def faulty_poll(command, **kwargs):
            process, job = original_launch(command, **kwargs)
            captured.append((process, job))
            if command[command.index("--branch") + 1] == "m2":
                process.wait(timeout=2)
                poll = process.poll
                calls = 0

                def second_poll_error():
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        raise OSError("injected second poll handle failure")
                    return poll()
                process.poll = second_poll_error
            return process, job

        try:
            with patch.object(runtime, "_launch_worker", side_effect=faulty_poll):
                root, report = self.launch(["descendant", "success"])
            self.assertTrue(report["branches"]["m2"].get("process_exit_confirmed"), report)
            self.assertEqual("failed", report["branches"]["m2"]["outcome"])
            self.assertIn("injected second poll handle failure", report["branches"]["m2"]["poll_error"])
            self.assertEqual("complete", report["branches"]["m3"]["outcome"])
            self.assert_descendant_gone(root, report)
        finally:
            # The pre-repair negative must not leave its demonstrated orphan.
            for process, job in captured:
                runtime._force_reap(process, job, .3)
            time.sleep(.05)

    def test_launch_assignment_and_cleanup_failures_still_force_stop_before_return(self):
        import irisx.arc_nvarc_combined as runtime
        original_job = runtime._windows_job
        original_reap = runtime._reap
        original_popen = runtime.subprocess.Popen
        processes = []
        job_calls = 0
        reap_calls = 0

        def capture(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process

        def failed_assignment(process):
            nonlocal job_calls
            job_calls += 1
            if job_calls == 1:
                raise RuntimeError("injected assignment failure")
            return original_job(process)

        def failed_cleanup(*args):
            nonlocal reap_calls
            reap_calls += 1
            if reap_calls == 1:
                raise RuntimeError("injected cleanup failure before stop")
            return original_reap(*args)

        with patch.object(runtime.subprocess, "Popen", side_effect=capture), \
                patch.object(runtime, "_windows_job", side_effect=failed_assignment), \
                patch.object(runtime, "_reap", side_effect=failed_cleanup):
            _, report = self.launch(["pre-ready-hang", "success"])
        self.assertEqual("injected assignment failure", report["branches"]["m2"]["error"])
        self.assertIn("injected cleanup failure before stop", str(report["branches"]["m2"]["launch_cleanup_errors"]))
        self.assertEqual("complete", report["branches"]["m3"]["outcome"])
        self.assertTrue(all(p.poll() is not None and p.stdout.closed and p.stderr.closed for p in processes))

    @unittest.skipUnless(os.name == "posix", "POSIX-specific ignored TERM signal fixture")
    def test_grandchildren_ignoring_term_are_killed_after_primary_exit(self):
        root, report = self.launch(["grandchild", "success"])
        self.assertEqual("complete", report["outcome"])
        self.assert_descendant_gone(root, report)
        pid = read(root / "m2/grandchild.json")["pid"]
        status = Path("/proc") / str(pid) / "stat"
        if status.exists():
            self.assertEqual("Z", status.read_text().rsplit(")", 1)[1].split()[0])
        cleanup = report["branches"]["m2"]["process_tree_cleanup"]
        if sys.platform.startswith("linux"):
            self.assertEqual(0, cleanup["active_processes_after_termination"])
            self.assertIn(pid, cleanup["initial_process_ids"])


class CombinedHardwareAndPlanTests(unittest.TestCase):
    def test_logical_device_binding_rejects_boolean_and_float_integer_aliases(self):
        inventory = [{**d, "physical_index": d["index"]} for d in devices(2)]
        hardware = select_devices(inventory)
        logical = hardware["assignments"]["m2"]
        for field, alias in (("index", False), ("physical_index", False), ("bf16", 1),
                             ("memory_bytes", float(logical["memory_bytes"])),
                             ("memory_mib", float(logical["memory_mib"]))):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    check_logical_device("m2", hardware, logical["uuid"], [{**logical, field: alias}], logical["uuid"])

    def test_two_selected_from_four_and_logical_mapping(self):
        inventory = devices(4)
        hardware = select_devices(inventory, [1, 3])
        logical = {**inventory[3], "index": 0}
        check_logical_device("m3", hardware, inventory[3]["uuid"], [logical], inventory[3]["uuid"])
        for wrong in ([logical, logical], [{**logical, "index": 3}], [{**logical, "uuid": inventory[1]["uuid"]}]):
            with self.assertRaises(ValidationError):
                check_logical_device("m3", hardware, inventory[3]["uuid"], wrong, inventory[3]["uuid"])

    def test_reject_missing_duplicate_type_precision_and_memory(self):
        for inventory, indices in ((devices(1), [0, 1]), (devices(2), [0, 0]),
            ([devices()[0], {**devices()[1], "uuid": devices()[0]["uuid"]}], [0, 1]),
            ([devices()[0], {**devices()[1], "name": "Tesla T4"}], [0, 1]),
            ([devices()[0], {**devices()[1], "bf16": False}], [0, 1]),
            ([devices()[0], {**devices()[1], "memory_bytes": 16 * 10**9}], [0, 1])):
            with self.assertRaises(ValidationError):
                select_devices(inventory, indices)

    def test_stale_approvals_identity_material_budget_and_live_draft_are_rejected(self):
        plan = read(DRAFT)
        validate_plan(plan)
        with self.assertRaisesRegex(ValidationError, "inert"):
            require_live_authorization(plan)
        mutations = [("owner_decision", "Decision 0034"), ("approved", True),
                     ("run_id", "nvarc-m2-source-cont-002"), ("maximum_notebook_wall_seconds", 1801)]
        for key, value in mutations:
            changed = copy.deepcopy(plan)
            changed[key] = value
            with self.assertRaises(ValidationError):
                validate_plan(changed)
        for key, value in (("maximum_source_generation_calls", 5), ("export_material_digest", "sha256:" + "0" * 64)):
            changed = copy.deepcopy(plan)
            changed["branches"]["m2"][key] = value
            with self.assertRaises(ValidationError):
                validate_plan(changed)

    def test_unsafe_artifact_members_fail_before_reading(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ("C:foo", "C:/foo", "../foo", "/foo", "a\\b", ""):
                with self.assertRaises(ValidationError):
                    member(Path(temp), name)

    def test_m2_interrupted_reservation_has_known_lower_bound_and_unknown_actual_total(self):
        plan = read(DRAFT)
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx") as temp:
            root = Path(temp)
            atomic(root / "call-ledger.json", {"format": "irisx/nvarc-combined-m2-call-ledger-v1",
                "parent_run_id": plan["run_id"], "run_id": plan["branches"]["m2"]["run_id"], "branch": "m2",
                "plan_digest": digest_value(plan), "child_plan_digest": digest_value(plan["branches"]["m2"]),
                "records": {"generation:1": {"kind": "generation", "index": 1, "task_id": "00576224",
                                             "status": "reserved", "test_index": 0, "view_index": 0}}})
            observed = partial_m2_counts(plan, root)
            self.assertEqual(1, observed["reserved_counters"]["generation_calls"])
            self.assertEqual(0, observed["actual_counters"]["completed_generation_calls"])
            self.assertIsNone(observed["actual_counters"]["total_generation_calls"])

    def test_generation_failure_keeps_reservation_and_does_not_retry(self):
        class FailingFixture(FixtureCandidateBackend):
            def generate(self, query, **kwargs):
                self.calls += 1
                raise ValidationError("synthetic generation failure")
        backend = FailingFixture({})
        events = []
        task = {"task_id": "fixture", "train": [{"input": [[1]], "output": [[2]]}],
                "test": [{"input": [[3]]}]}
        config = {"seed": 24, "maximum_calls_per_task": 4, "beams_per_call": 1, "maximum_new_tokens": 64}
        with self.assertRaisesRegex(ValidationError, "synthetic generation failure"):
            solve_task(task, backend, config, call_observer=events.append)
        self.assertEqual(1, backend.calls)
        self.assertEqual(1, len(events))
        self.assertEqual(("generation", 1, "reserved"),
                         (events[0]["kind"], events[0]["index"], events[0]["status"]))

    def test_complete_worker_terminal_retains_known_reservations(self):
        # Synthetic workload substitution isolates terminal accounting. Actual
        # tiny-model evidence remains in the separate installed-wheel probe.
        plan = read(DRAFT)
        hardware = select_devices(devices())
        counts = {"generation_calls": 4, "verification_calls": 2, "ttt_steps": 1, "sft_steps": 0,
                  "ranked_candidates": 0}
        def fixture_workload(*args, model_ready, call_observer):
            model_ready()
            for kind, count in (("generation", 4), ("verification", 2)):
                for index in range(1, count + 1):
                    for status in ("reserved", "complete"):
                        call_observer({"kind": kind, "index": index, "status": status,
                                       "task_id": "00576224", "test_index": 0, "view_index": 0})
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx") as temp:
            root = Path(temp)
            inputs = root / "fixture-input.json"
            inputs.write_text("{}")
            paths = {key: str(inputs) for key in ("source_config", "visible", "training_evidence", "bundle", "m2_model")}
            with patch("irisx.arc_nvarc_source_continuation._run_bound", side_effect=fixture_workload), \
                 patch("irisx.arc_nvarc_combined_worker.inventory", return_value=[devices()[0]]), \
                 patch("irisx.arc_nvarc_combined_worker.verify_branch", return_value=counts), \
                 patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": devices()[0]["uuid"]}):
                _run_prepared(plan, "m2", paths, hardware, root / "worker")
            terminal = read(root / "worker/worker-terminal.json")
            self.assertEqual("complete", terminal["status"])
            self.assertEqual({"generation_calls": 4, "verification_calls": 2}, terminal["reserved_counters"])
            self.assertEqual(counts, terminal["actual_counters"])




if __name__ == "__main__":
    unittest.main()

"""Offline process, hardware and inert-package regressions, without ML mocks."""

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
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


class CombinedProcessTests(unittest.TestCase):
    def launch(self, modes, *, work_seconds=3, readiness=0.6, setup=None):
        root = Path(self.temp.name) / ("out-" + str(self.serial))
        self.serial += 1
        hardware = select_devices(devices(4))
        children = {b: {"device": hardware["assignments"][b], "command": [sys.executable, str(CHILD),
            "--output", str(root / b), "--branch", b, "--mode", modes[i],
            "--device", json.dumps(hardware["assignments"][b])]} for i, b in enumerate(("m2", "m3"))}
        now = time.monotonic()
        report = supervise(children, root, run_id="fixture-combined", plan_digest="fixture-plan",
            deadline=now + work_seconds, terminal_deadline=now + work_seconds + 2,
            readiness_seconds=readiness, validators={b: fixture_validator for b in children},
            setup=setup, term_seconds=0.3, kill_seconds=0.3)
        self.assertEqual(report, read(root / "aggregate-terminal.json"))
        self.assertLess(time.monotonic() - now, work_seconds + 2)
        self.assertEqual(0, report["retries"])
        self.assertTrue(all(r["launch_count"] <= 1 for r in report["branches"].values()))
        return root, report

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".irisx", prefix="combined-cpu-")
        self.serial = 0

    def tearDown(self):
        self.temp.cleanup()

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
                _, report = self.launch([mode, "success"])
                self.assertEqual("partial", report["outcome"])
                self.assertEqual("failed", report["branches"]["m2"]["outcome"])
                self.assertEqual("complete", report["branches"]["m3"]["outcome"])

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

    def test_shared_failure_launches_neither(self):
        def fail():
            raise ValidationError("fixture shared setup failed")
        _, report = self.launch(["success", "success"], setup=fail)
        self.assertEqual("failed", report["outcome"])
        self.assertEqual("ValidationError", report["shared_error"]["type"])
        self.assertTrue(all(r["launch_count"] == 0 for r in report["branches"].values()))

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
        pid = read(root / "m2/descendant.json")["pid"]
        if os.name == "nt":
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


class CombinedHardwareAndPlanTests(unittest.TestCase):
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

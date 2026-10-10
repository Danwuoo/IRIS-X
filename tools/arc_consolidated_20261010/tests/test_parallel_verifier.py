"""Controller concurrency/accounting tests; synthetic callbacks, no VM or GPU."""
from concurrent.futures import Future
from contextlib import ExitStack
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from tools.arc_consolidated_20261010 import runner, stages
from tools.arc_consolidated_20261010.ledger import Ledger, digest
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory


PLAN = {"steps": [{"op": "identity"}]}


def task(index):
    return {"task_id": str(index), "demos": [{"input": [[1]], "output": [[1]]}]}


def receipt(index, *, stopped=True):
    return {"status": "fit", "known": True, "all_demos_fit": True, "gas": 7,
            "wall_seconds": .001, "dispatched": True, "owned_descendants_stopped": stopped,
            "synthetic_index": index, "test_evidence": "synthetic-test-only"}


class ParallelVerifierTests(unittest.TestCase):
    def ledger(self, path, cap=1152):
        limits = runner.limits_for("SMOKE")
        limits["coverage_checks"] = cap
        bindings = {key: digest(key) for key in ("source", "task", "model", "prompt", "sampling")}
        bindings.update(budget=digest(limits), mode=digest("synthetic-test-only"))
        return Ledger(path, bindings, limits)

    def checked(self, ledger, verify, resume=False):
        return runner.AccountedVerifier(ledger, cpu_deadline=time.monotonic() + 30,
            capability={"available": True}, resume=resume, verify_fn=verify)

    @staticmethod
    def jobs(count=8):
        return ((task(i), PLAN) for i in range(count))

    def test_four_workers_reserve_before_dispatch_and_finalize_in_input_order(self):
        controller = threading.get_ident()
        barrier, lock = threading.Barrier(4), threading.Lock()
        active, peak, finish_order, thread_ids = 0, 0, [], set()
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            def verify(source, item, **kwargs):
                nonlocal active, peak
                index = int(item["task_id"])
                ident = "cpu/coverage/" + runner.assets.digest({"task": item, "plan": PLAN})
                # Read committed bytes, without calling any ledger API in the worker.
                events = [json.loads(line) for line in ledger.journal_path.read_bytes().splitlines()]
                self.assertTrue(any(e["event"] == "reserve" and e["data"]["id"] == ident for e in events))
                self.assertLessEqual(kwargs["timeout"], 3)
                self.assertEqual(kwargs["max_steps"], 200000)
                with lock:
                    active += 1
                    peak = max(peak, active)
                    thread_ids.add(threading.get_ident())
                barrier.wait(timeout=3)
                time.sleep((3 - index % 4) * .015)
                with lock:
                    finish_order.append(index)
                    active -= 1
                return receipt(index)
            checked = self.checked(ledger, verify)
            def on_controller(original):
                def wrapped(*args, **kwargs):
                    self.assertEqual(threading.get_ident(), controller)
                    return original(*args, **kwargs)
                return wrapped
            with ExitStack() as stack:
                for name in ("reserve", "record_response", "finish", "operation", "get_response", "summary"):
                    stack.enter_context(patch.object(ledger, name, side_effect=on_controller(getattr(ledger, name))))
                result = checked.batch(self.jobs())
            self.assertEqual(peak, 4)
            self.assertEqual(len(thread_ids), 4)
            self.assertNotIn(controller, thread_ids)
            self.assertNotEqual(finish_order, list(range(8)))
            self.assertEqual([row["synthetic_index"] for row in result["results"]], list(range(8)))
            self.assertEqual((result["workers_used"], result["workers_cap"]), (4, 4))
            self.assertTrue(checked.all_stopped)
            self.assertEqual(ledger.summary()["charged"]["coverage_checks"], 8)
            response_ids = [json.loads(line)["data"]["id"] for line in ledger.journal_path.read_bytes().splitlines()
                            if json.loads(line)["event"] == "response"]
            self.assertEqual(response_ids, ["cpu/coverage/" + runner.assets.digest({"task": task(i), "plan": PLAN})
                                            for i in range(8)])

    def test_budget_stop_drains_reserved_jobs_and_preserves_unvisited(self):
        calls = []
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger", cap=2).session(session_seconds=1000) as ledger:
            def verify(source, item, **kwargs):
                calls.append(item["task_id"])
                return receipt(int(item["task_id"]))
            checked = self.checked(ledger, verify)
            result = checked.batch(self.jobs())
            self.assertEqual(sorted(calls), ["0", "1"])
            self.assertEqual([row["status"] for row in result["results"]], ["fit"] * 2 + ["missing"] * 6)
            self.assertIn("BudgetExceeded", result["stop_reason"])
            self.assertTrue(checked.all_stopped)
            self.assertEqual(ledger.summary()["charged"]["coverage_checks"], 2)
            self.assertEqual(ledger.summary()["operation_states"]["reserved"], 0)

    def test_successful_batch_is_cached_across_explicit_resume_without_duplicates(self):
        calls = []
        with TemporaryDirectory() as td:
            for iteration in range(2):
                with self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
                    def verify(source, item, **kwargs):
                        calls.append(item["task_id"])
                        return receipt(int(item["task_id"]))
                    checked = self.checked(ledger, verify, resume=bool(iteration))
                    result = checked.batch(self.jobs())
                    self.assertEqual(len(result["results"]), 8)
                    self.assertTrue(checked.all_stopped)
                    self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 8)
                    self.assertEqual(checked.physical_this_session, 0 if iteration else 8)
            self.assertEqual(len(calls), 8)

    def test_one_unconfirmed_worker_drains_peers_stops_future_dispatch_and_never_retries(self):
        calls = []
        with TemporaryDirectory() as td:
            for iteration in range(2):
                with self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
                    def verify(source, item, **kwargs):
                        calls.append(item["task_id"])
                        if item["task_id"] == "0":
                            raise RuntimeError("synthetic unconfirmed child")
                        return receipt(int(item["task_id"]))
                    checked = self.checked(ledger, verify, resume=bool(iteration))
                    result = checked.batch(self.jobs())
                    self.assertEqual([r["status"] for r in result["results"]],
                                     ["unknown"] + ["fit"] * 3 + ["missing"] * 4)
                    self.assertFalse(checked.all_stopped)
                    self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 4)
                    self.assertEqual(ledger.summary()["charged"]["unknown_verifications"], 1)
            self.assertEqual(len(calls), 4)

    def test_controller_interrupt_drains_four_jobs_and_returns_full_partial_denominator(self):
        interrupted = False
        original = Future.result
        def interrupt_once(future, *args, **kwargs):
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt()
            return original(future, *args, **kwargs)
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            checked = self.checked(ledger, lambda source, item, **kwargs: receipt(int(item["task_id"])))
            with patch.object(Future, "result", interrupt_once):
                result = checked.batch(self.jobs())
            self.assertIn("interrupted", result["stop_reason"])
            self.assertEqual([r["status"] for r in result["results"]], ["fit"] * 4 + ["missing"] * 4)
            self.assertTrue(checked.all_stopped)
            self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 4)
            self.assertEqual(ledger.summary()["operation_states"]["reserved"], 0)

    def test_deadline_stops_next_window_without_losing_completed_results(self):
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            checked = self.checked(ledger, lambda source, item, **kwargs: receipt(int(item["task_id"])))
            original = checked._prepare
            def prepare(item, plan):
                if item["task_id"] == "4":
                    checked.cpu_deadline = 0
                return original(item, plan)
            with patch.object(checked, "_prepare", side_effect=prepare):
                result = checked.batch(self.jobs())
            self.assertEqual([r["status"] for r in result["results"]], ["fit"] * 4 + ["missing"] * 4)
            self.assertIn("wall cap", result["stop_reason"])
            self.assertTrue(checked.all_stopped)

    def test_malformed_worker_receipt_withholds_stop_and_stops_new_admission(self):
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            checked = self.checked(ledger, lambda source, item, **kwargs:
                                   None if item["task_id"] == "0" else receipt(int(item["task_id"])))
            result = checked.batch(self.jobs())
            self.assertEqual([r["status"] for r in result["results"]],
                             ["unknown"] + ["fit"] * 3 + ["missing"] * 4)
            self.assertFalse(checked.all_stopped)
            self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 4)

    def test_observed_overrun_stops_dispatch_but_drains_and_retains_peer_receipts(self):
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            def verify(source, item, **kwargs):
                value = receipt(int(item["task_id"]))
                if item["task_id"] == "0":
                    value["wall_seconds"] = 4
                return value
            checked = self.checked(ledger, verify)
            result = checked.batch(self.jobs())
            self.assertEqual([r["status"] for r in result["results"]], ["fit"] * 4 + ["missing"] * 4)
            self.assertIn("BudgetExceeded", result["stop_reason"])
            self.assertTrue(checked.all_stopped)
            self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 4)
            self.assertGreaterEqual(ledger.summary()["charged"]["verifier_seconds"], 4)
            self.assertEqual(ledger.summary()["operation_states"]["reserved"], 0)

    def test_worker_base_exception_is_unknown_not_a_false_controller_stop_ack(self):
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            def verify(source, item, **kwargs):
                if item["task_id"] == "0":
                    raise KeyboardInterrupt()
                return receipt(int(item["task_id"]))
            checked = self.checked(ledger, verify)
            result = checked.batch(self.jobs())
            self.assertEqual([r["status"] for r in result["results"]],
                             ["unknown"] + ["fit"] * 3 + ["missing"] * 4)
            self.assertFalse(checked.all_stopped)
            self.assertEqual(ledger.summary()["charged"]["unknown_verifications"], 1)

    def test_stage_helpers_use_batch_and_preserve_fixed_order(self):
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            checked = self.checked(ledger, lambda source, item, **kwargs: receipt(int(item["task_id"])))
            controls = [{"control_id": "c" + str(i), "task": task(i), "plan": PLAN, "expected_status": "fit"}
                        for i in range(8)]
            report = stages.run_controls(controls, checked)
            self.assertEqual([r["control_id"] for r in report["controls"]], ["c" + str(i) for i in range(8)])
            self.assertTrue(report["complete"])
            report = stages.run_coverage([task(i) for i in range(8)], [PLAN], checked, expected_task_ids=None)
            self.assertEqual([t["task_id"] for t in report["tasks"]], [str(i) for i in range(8)])
            self.assertEqual(report["planned"], 8)
            self.assertTrue(report["complete"])
            self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 8)

    def test_accounting_api_rejects_non_controller_thread(self):
        failures = []
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            checked = self.checked(ledger, lambda *a, **k: receipt(0))
            def attempt():
                try:
                    checked(task(0), PLAN)
                except RuntimeError as exc:
                    failures.append(str(exc))
            thread = threading.Thread(target=attempt)
            thread.start()
            thread.join()
            self.assertEqual(len(failures), 1)
            self.assertIn("controller thread", failures[0])
            self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 0)


if __name__ == "__main__":
    unittest.main()

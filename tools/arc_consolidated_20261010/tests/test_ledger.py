"""CPU-only failure injection for the successor's persistent accounting."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

from tools.arc_consolidated_20261010.ledger import (
    BindingMismatch, BudgetExceeded, ControllerBusy, IntegrityError, Ledger,
    LedgerError, canonical, digest,
)


def limits(**changes):
    return {"physical_calls": 80, "cpu_checks": 30, "prompt_tokens": 8000,
            "output_tokens": 800, "gas": 1000, "model_seconds": 100,
            "wall_seconds": 1000, "unknown_calls": 3, **changes}


def bindings(bounds):
    return {**{name: hashlib.sha256(name.encode()).hexdigest()
               for name in ("source", "task", "model", "prompt", "sampling", "mode")},
            "budget": digest(bounds)}


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


@contextmanager
def scratch_directory():
    # Windows sandbox identities cannot traverse Python's mode-0700 tempfile
    # ACLs. Inherit the approved workspace ACL on a unique, owned test directory.
    parent = Path(__file__).resolve().parents[3] / ".irisx" / "consolidated-ledger-tests"
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        if path.resolve().parent != parent.resolve() or len(path.name) != 32:
            raise RuntimeError("refusing cleanup outside the exact test scratch parent")
        shutil.rmtree(path)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = scratch_directory()
        self.root = self.temp.__enter__() / "ledger"
        self.addCleanup(self.temp.__exit__, None, None, None)
        self.bounds = limits()

    def ledger(self, bounds=None, identity=None):
        bounds = self.bounds if bounds is None else bounds
        return Ledger(self.root, bindings(bounds) if identity is None else identity, bounds)

    def crash_child(self, action, bounds=None):
        bounds = self.bounds if bounds is None else bounds
        code = "\n".join([
            "import json, os, sys",
            "from tools.arc_consolidated_20261010.ledger import Ledger",
            "root, identity, bounds, action = json.loads(sys.argv[1])",
            "with Ledger(root, identity, bounds).session(session_seconds=10) as ledger:",
            "    ledger.reserve('model', 'root/1', {'prompt_tokens': 10, 'output_tokens': 20})",
            "    if action == 'response': ledger.record_response('root/1', {'text': 'durable'})",
            "    ledger.checkpoint_wall()",
            "    os._exit(73)",
        ])
        result = subprocess.run([sys.executable, "-c", code,
                                 json.dumps([str(self.root), bindings(bounds), bounds, action])],
                                capture_output=True, text=True, timeout=20,
                                cwd=Path(__file__).resolve().parents[3])
        self.assertEqual(result.returncode, 73, result.stdout + result.stderr)

    def test_budget_binding_is_exact_and_required(self):
        identity = bindings(self.bounds)
        identity["budget"] = "f" * 64
        with self.assertRaises(BindingMismatch):
            self.ledger(identity=identity)
        for name in ("source", "task", "model", "prompt", "sampling", "budget", "mode"):
            identity = bindings(self.bounds)
            del identity[name]
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.ledger(identity=identity)

    def test_fsync_precedes_dispatch_and_response_is_durable(self):
        fsync = os.fsync
        calls = []
        def observed(fd):
            fsync(fd)
            calls.append(fd)
        with self.ledger().session(session_seconds=10) as ledger:
            with patch("tools.arc_consolidated_20261010.ledger.os.fsync", side_effect=observed):
                ledger.reserve("model", "shared-root", {"prompt_tokens": 20, "output_tokens": 10},
                               metadata={"arms": ["true", "redacted"]})
                self.assertTrue(calls, "dispatch must only occur after this fsync")
                self.assertIn(b'"event":"reserve"', ledger.journal_path.read_bytes())
                ledger.record_response("shared-root", {"text": "{}", "truncated": False})
                ledger.finish("shared-root", {"prompt_tokens": 20, "output_tokens": 2})
            self.assertEqual(ledger.get_response("shared-root")["text"], "{}")
            summary = ledger.summary()
            self.assertEqual(summary["charged"]["physical_calls"], 1)
            self.assertEqual(summary["charged"]["output_tokens"], 2)
            self.assertFalse(summary["vm_billing_stopped"])
        with self.ledger().session(session_seconds=10) as ledger:
            self.assertEqual(ledger.summary()["charged"]["physical_calls"], 1)
            with self.assertRaises(LedgerError):
                ledger.reserve("model", "shared-root", {})

    def test_physical_call_ceiling_parameterized_including_eighty(self):
        for maximum in (1, 2, 80):
            with self.subTest(maximum=maximum), scratch_directory() as root:
                bounds = limits(physical_calls=maximum)
                with Ledger(root, bindings(bounds), bounds).session(session_seconds=10) as ledger:
                    for number in range(maximum):
                        call_id = f"call-{number}"
                        ledger.reserve("model", call_id, {})
                        ledger.record_response(call_id, {"text": ""})
                        ledger.finish(call_id)
                    with self.assertRaises(BudgetExceeded):
                        ledger.reserve("model", "over-limit", {})
                    self.assertEqual(ledger.summary()["charged"]["physical_calls"], maximum)

    def test_unknown_after_real_process_crash_is_full_charge_and_never_retry(self):
        self.crash_child("no-response")
        with self.ledger().session(session_seconds=10) as ledger:
            summary = ledger.summary()
            self.assertEqual(summary["operation_states"]["unknown"], 1)
            self.assertEqual(summary["charged"]["physical_calls"], 1)
            self.assertEqual(summary["charged"]["output_tokens"], 20)
            self.assertEqual(summary["consumed_wall_seconds"], 10)
            with self.assertRaises(LedgerError):
                ledger.reserve("model", "root/1", {"output_tokens": 20})
            with self.assertRaises(LedgerError):
                ledger.finish("root/1", {"output_tokens": 0})
            with self.assertRaises(LedgerError):
                ledger.record_response("root/1", {"text": "late result"})

    def test_recorded_response_can_resume_with_new_accounted_cpu_verification(self):
        self.crash_child("response")
        with self.ledger().session(session_seconds=10) as ledger:
            self.assertEqual(ledger.operation("root/1")["status"], "responded")
            self.assertEqual(ledger.get_response("root/1"), {"text": "durable"})
            self.assertEqual(ledger.summary()["charged"]["output_tokens"], 20)
            ledger.reserve("cpu", "verify-root-1-resume-1", {"cpu_checks": 1, "gas": 200})
            ledger.finish("verify-root-1-resume-1", {"gas": 150})
            ledger.finish("root/1", {"output_tokens": 1})
            self.assertEqual(ledger.summary()["charged"]["physical_calls"], 1)
            self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 1)
            with self.assertRaises(LedgerError):
                ledger.reserve("cpu", "verify-root-1-resume-1", {"cpu_checks": 1})

    def test_unknown_ceiling_blocks_new_work_and_preserves_summary(self):
        self.bounds = limits(unknown_calls=1)
        self.crash_child("no-response")
        with self.ledger().session(session_seconds=10) as ledger:
            self.assertEqual(ledger.summary()["operation_states"]["unknown"], 1)
            with self.assertRaises(BudgetExceeded):
                ledger.reserve("cpu", "new-verification", {"cpu_checks": 1})

    def test_unfinished_cpu_is_unknown_and_full_charge(self):
        with self.ledger().session(session_seconds=10) as ledger:
            ledger.reserve("cpu", "verify-once", {"cpu_checks": 4, "gas": 300})
        with self.ledger().session(session_seconds=10) as ledger:
            self.assertEqual(ledger.operation("verify-once")["status"], "unknown")
            self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 4)
            self.assertEqual(ledger.summary()["charged"]["gas"], 300)

    def test_limits_and_all_identity_dimensions_are_immutable_on_resume(self):
        with self.ledger().session(session_seconds=10):
            pass
        for name in bindings(self.bounds):
            identity = bindings(self.bounds)
            if name == "budget":
                changed = limits(physical_calls=81)
                other = self.ledger(bounds=changed)
            else:
                identity[name] = "a" * 64
                other = self.ledger(identity=identity)
            before = self.root.joinpath("journal.jsonl").read_bytes()
            with self.subTest(name=name), self.assertRaises(BindingMismatch), other.session():
                pass
            self.assertEqual(self.root.joinpath("journal.jsonl").read_bytes(), before)

    def test_second_controller_is_rejected_and_lock_released_normally(self):
        with self.ledger().session(session_seconds=10):
            with self.assertRaises(ControllerBusy), self.ledger().session(session_seconds=10):
                pass
        with self.ledger().session(session_seconds=10) as ledger:
            self.assertEqual(ledger.summary()["charged"]["physical_calls"], 0)

    def test_truncated_journal_is_rejected_and_exact_bytes_preserved(self):
        with self.ledger().session(session_seconds=10):
            pass
        path = self.root / "journal.jsonl"
        with path.open("ab") as handle:
            handle.write(b'{"seq":')
        before = path.read_bytes()
        with self.assertRaises(IntegrityError), self.ledger().session(session_seconds=10):
            pass
        self.assertEqual(path.read_bytes(), before)

    def test_edited_chain_and_missing_response_fail_closed(self):
        with self.ledger().session(session_seconds=10) as ledger:
            ledger.reserve("model", "call", {})
            receipt = ledger.record_response("call", {"text": "data"})
            ledger.finish("call")
        response = self.root / "responses" / receipt["file"]
        original = response.read_bytes()
        response.write_bytes(b"changed")
        with self.assertRaises(IntegrityError), self.ledger().session(session_seconds=10):
            pass
        response.write_bytes(original)
        response.unlink()
        with self.assertRaises(IntegrityError), self.ledger().session(session_seconds=10):
            pass
        response.write_bytes(original)
        path = self.root / "journal.jsonl"
        path.write_bytes(path.read_bytes().replace(b'"call"', b'"xall"', 1))
        with self.assertRaises(IntegrityError), self.ledger().session(session_seconds=10):
            pass

    def test_orphan_response_is_rejected_without_deletion_or_adoption(self):
        with self.ledger().session(session_seconds=10) as ledger:
            ledger.reserve("model", "call", {})
            real_append = ledger._append
            def fail_response(event, data, **kwargs):
                if event == "response":
                    raise OSError("injected death after response fsync before journal append")
                return real_append(event, data, **kwargs)
            with patch.object(ledger, "_append", side_effect=fail_response), self.assertRaises(OSError):
                ledger.record_response("call", {"text": "retained orphan"})
        response = next((self.root / "responses").iterdir())
        before = response.read_bytes()
        journal = (self.root / "journal.jsonl").read_bytes()
        with self.assertRaises(IntegrityError), self.ledger().session(session_seconds=10):
            pass
        self.assertEqual(response.read_bytes(), before)
        self.assertEqual((self.root / "journal.jsonl").read_bytes(), journal)

    def test_failed_reservation_fsync_never_returns_dispatch_permission(self):
        dispatched = []
        with self.ledger().session(session_seconds=10) as ledger:
            with patch("tools.arc_consolidated_20261010.ledger.os.fsync", side_effect=OSError("disk fault")):
                with self.assertRaises(OSError):
                    ledger.reserve("model", "uncertain", {})
                    dispatched.append("must-not-run")
            with self.assertRaises(LedgerError):
                ledger.reserve("model", "second", {})
        self.assertEqual(dispatched, [])
        with self.ledger().session(session_seconds=10) as ledger:
            self.assertEqual(ledger.operation("uncertain")["status"], "unknown")

    def test_new_monotonic_origin_does_not_reset_consumed_wall(self):
        clock = Clock()
        with patch("tools.arc_consolidated_20261010.ledger.time.monotonic", side_effect=clock):
            with self.ledger().session(session_seconds=20) as ledger:
                clock.value += 7
                self.assertEqual(ledger.checkpoint_wall(), 7)
                self.assertEqual(ledger.remaining_wall_seconds, 13)
            clock.value = 1  # simulate a reboot with a different monotonic origin
            with self.ledger().session(session_seconds=20) as ledger:
                self.assertEqual(ledger.summary()["consumed_wall_seconds"], 7)
                self.assertEqual(ledger.remaining_wall_seconds, 20)
                clock.value += 20
                with self.assertRaises(BudgetExceeded):
                    ledger.reserve("model", "too-late", {})
            with self.ledger().session(session_seconds=10) as ledger:
                self.assertEqual(ledger.summary()["consumed_wall_seconds"], 27)

    def test_wall_overrun_is_recorded_and_deadline_does_not_claim_preemption(self):
        clock = Clock()
        with patch("tools.arc_consolidated_20261010.ledger.time.monotonic", side_effect=clock):
            with self.ledger().session(session_seconds=2) as ledger:
                clock.value += 3
                ledger.checkpoint_wall()
            with self.ledger().session(session_seconds=2) as ledger:
                self.assertEqual(ledger.summary()["consumed_wall_seconds"], 3)
                self.assertEqual(ledger.summary()["state"], "fail")

    def test_trusted_bootstrap_debits_deadline_and_settled_wall(self):
        clock = Clock()
        with patch("tools.arc_consolidated_20261010.ledger.time.monotonic", side_effect=clock):
            with self.ledger().session(session_seconds=20, prior_elapsed_seconds=10) as ledger:
                self.assertEqual(ledger.remaining_wall_seconds, 10)
                self.assertEqual(ledger.summary()["session_prior_elapsed_seconds"], 10)
                self.assertEqual(ledger.summary()["directory_fsync_supported"], os.name != "nt")
                clock.value += 3
                self.assertEqual(ledger.checkpoint_wall(), 13)
            with self.ledger().session(session_seconds=20) as ledger:
                self.assertEqual(ledger.summary()["consumed_wall_seconds"], 13)
                self.assertEqual(ledger.remaining_wall_seconds, 20)

    def test_invalid_bootstrap_time_is_rejected_before_dispatch(self):
        for prior in (True, float("nan"), float("inf"), -1):
            with self.subTest(prior=prior), self.assertRaises(ValueError), self.ledger().session(prior_elapsed_seconds=prior):
                self.fail("invalid prior elapsed time admitted a session")
        with self.assertRaises(BudgetExceeded), self.ledger().session(session_seconds=10, prior_elapsed_seconds=11):
            self.fail("overallowance bootstrap admitted a session")
        self.assertFalse(self.root.exists())
        with self.assertRaises(BudgetExceeded), self.ledger().session(prior_elapsed_seconds=self.bounds["wall_seconds"] + 1):
            self.fail("bootstrap above remaining wall admitted a session")

    def test_run_states_and_model_error_receipts(self):
        with self.ledger().session(session_seconds=10) as ledger:
            ledger.reserve("model", "errored", {})
            with self.assertRaises(LedgerError):
                ledger.finish("errored", outcome="fail")
            with self.assertRaises(LedgerError):
                ledger.set_state("complete")
            ledger.record_response("errored", {"error": "mock backend failure"})
            ledger.finish("errored", outcome="fail")
            ledger.set_state("partial", "model arm failed; CPU diagnostics retained")
            ledger.set_state("complete")
            with self.assertRaises(LedgerError):
                ledger.reserve("model", "new-after-complete", {})

    def test_invalid_counts_nan_unbounded_dimension_and_refunds_rejected(self):
        for changes in ({"physical_calls": True}, {"gas": float("nan")}, {"gas": float("inf")}, {"cpu_checks": 1.5}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.ledger(bounds=limits(**changes))
        with self.ledger().session(session_seconds=10) as ledger:
            for budget in ({"physical_calls": 0}, {"physical_calls": True}, {"unbounded": 2}, {"wall_seconds": 2}):
                with self.subTest(budget=budget), self.assertRaises(ValueError):
                    ledger.reserve("model", "invalid", budget)
            ledger.reserve("model", "valid", {"output_tokens": 2})
            ledger.record_response("valid", {"text": "x"})
            with self.assertRaises(ValueError):
                ledger.finish("valid", {"physical_calls": 0})
            with self.assertRaises(BudgetExceeded):
                ledger.finish("valid", {"output_tokens": 3})
            self.assertEqual(ledger.summary()["charged"]["physical_calls"], 1)
            self.assertEqual(ledger.summary()["charged"]["output_tokens"], 3)
            self.assertEqual(ledger.operation("valid")["status"], "fail")
            with self.assertRaises(BudgetExceeded):
                ledger.reserve("cpu", "after-overrun", {"cpu_checks": 1})
        with self.ledger().session(session_seconds=10) as ledger:
            self.assertTrue(ledger.summary()["reservation_overrun"])
            with self.assertRaises(LedgerError):
                ledger.set_state("complete")

    def test_json_rejects_nonfinite_tuple_and_integer_keys(self):
        for value in (float("nan"), (1, 2), {1: "key"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical(value)


if __name__ == "__main__":
    unittest.main()

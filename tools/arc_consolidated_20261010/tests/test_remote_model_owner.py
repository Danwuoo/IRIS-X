"""Synthetic-only persistent child protocol tests; no model or GPU imports."""
from dataclasses import asdict, replace
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import time
import unittest
from unittest.mock import patch

from tools.arc_consolidated_20261010 import model_provider as mp, remote_model_owner as remote
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory


PLAN_HASH = "e" * 64
SOURCE_ROOT = Path(__file__).resolve().parents[3]
GRAMMAR = {"version": "synthetic-test-only", "max_steps": 3, "operations": {"identity": {}}}


def study():
    return mp.build_study_plan([
        {"task_id": "synthetic_" + str(i), "demos": [{"input": [[i]], "output": [[i]]}]}
        for i in range(8)], grammar=GRAMMAR, environment_sha256=PLAN_HASH)


def fixtures(directory):
    directory = Path(directory)
    source = {name: hashlib.sha256((SOURCE_ROOT / name).read_bytes()).hexdigest() for name in (
        "tools/__init__.py", "tools/arc_consolidated_20261010/__init__.py",
        "tools/arc_consolidated_20261010/model_provider.py", remote.ENTRY)}
    lock = directory / "synthetic-environment.json"
    lock.write_bytes(remote._canonical({"evidence_mode": "synthetic-test-only"}))
    prepared = {"python_command": [sys.executable, "-I", "-B", "-S"], "source_root": str(SOURCE_ROOT),
        "model_path": str(directory / "no-model"), "manifest_path": str(directory / "no-manifest"),
        "environment_lock_path": str(lock), "actual_environment_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest()}
    admission = {"format": "irisx/consolidated-runtime-admission-v2", "environment_plan_sha256": PLAN_HASH,
        "source_identity_sha256": remote._digest(source), "prepared": prepared, "asset_receipts_sha256": "a" * 64}
    path = directory / "admission.json"
    path.write_bytes(remote._canonical(admission))
    return {**prepared, "admission_path": str(path), "admission_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, source


class RemoteModelOwnerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.bootstrap, self.source = fixtures(self.scratch.name)
        self.plan = study()
        self.roots = [mp.materialize_request(self.plan, spec) for spec in self.plan.calls if spec.stage == "root"]

    def owner(self, **kwargs):
        owner = remote.RemoteModelOwner._synthetic_for_tests(self.bootstrap,
            environment_plan_sha256=PLAN_HASH, source_identity=self.source,
            deadline_monotonic=time.monotonic() + 30, **kwargs)
        self.addCleanup(owner.close)
        return owner

    def ready(self, **kwargs):
        owner = self.owner(**kwargs)
        item = owner.prepare(self.roots[0])
        owner.ensure_model_loaded()
        return owner, item

    def test_constructor_and_never_started_close_are_inert(self):
        with patch.object(remote.subprocess, "Popen", side_effect=AssertionError("spawn")), \
             patch.object(remote, "_read_bound", side_effect=AssertionError("filesystem")):
            owner = remote.RemoteModelOwner(self.bootstrap, environment_plan_sha256=PLAN_HASH,
                source_identity=self.source, deadline_monotonic=time.monotonic() + 30)
            self.assertFalse(owner.enabled)
            self.assertTrue(owner.close()["model_owner_stopped"])
            self.assertEqual(owner.accounting()["load_count"], 0)

    def test_admission_matches_v2_and_rejects_mutation_before_spawn(self):
        self.assertIn(remote.ENTRY, remote._admission(self.bootstrap, PLAN_HASH, self.source, synthetic=True))
        owner = self.owner()
        Path(self.bootstrap["admission_path"]).write_bytes(b"{}")
        with patch.object(remote.subprocess, "Popen", side_effect=AssertionError("spawn")), \
             self.assertRaisesRegex(remote.RemoteOwnerError, "bound file changed"):
            owner.initialize_tokenizer()
        self.assertIsNone(owner._process)

    def test_all_root_audit_precedes_one_load_and_one_persistent_process(self):
        owner = self.owner()
        owner.set_initialization_deadline(time.monotonic() + 20)
        owner.initialize_tokenizer()
        pid = owner._process.pid
        for request in self.roots:
            owner.prepare(request, register=False)
        self.assertEqual(owner.accounting()["load_count"], 0)
        first, second = owner.prepare_group(self.roots[:2])[0]
        with self.assertRaisesRegex(remote.RemoteOwnerError, "model load"):
            owner.dispatch(first, deadline_monotonic=time.monotonic() + 5)
        owner.ensure_model_loaded()
        owner.ensure_model_loaded()
        one = owner.dispatch(first, deadline_monotonic=time.monotonic() + 5)
        two = owner.dispatch(second, deadline_monotonic=time.monotonic() + 5)
        self.assertEqual(owner._process.pid, pid)
        self.assertEqual(owner.accounting()["load_count"], 1)
        self.assertEqual(owner.accounting()["physical_calls_attempted"], 2)
        for request, result in ((first, one), (second, two)):
            self.assertEqual(result["environment_sha256"], PLAN_HASH)
            self.assertEqual(result["environment_plan_sha256"], PLAN_HASH)
            self.assertEqual(result["actual_environment_lock_sha256"], self.bootstrap["actual_environment_lock_sha256"])
            self.assertNotEqual(result["environment_sha256"], result["actual_environment_lock_sha256"])
            self.assertEqual(result["request_sha256"], request.sha256)
            self.assertEqual(result["cache_sha256"], request.cache_sha256)
            self.assertNotEqual(result["actual_request_sha256"], request.sha256)
            self.assertGreaterEqual(result["model_seconds"], result["worker_model_seconds"])
        marker = json.loads((owner._request_path.parent / "worker-start.json").read_text())
        self.assertEqual(marker["worker_pid"], pid)
        self.assertEqual(marker["evidence_mode"], "synthetic-test-only")
        with self.assertRaisesRegex(remote.RemoteOwnerError, "previously attempted"):
            owner.dispatch(first, deadline_monotonic=time.monotonic() + 5)
        closed = owner.close()
        self.assertTrue(closed["model_owner_stopped"])
        self.assertTrue(closed["process_evidence"]["owned_io_threads_stopped"])
        self.assertIsNotNone(owner._process.returncode)
        self.assertFalse(closed["vm_billing_stopped"])

    def test_initialization_uses_one_narrowed_allowance(self):
        owner = self.owner(faults={"delay_load_seconds": 1})
        owner.set_initialization_deadline(time.monotonic() + 0.7)
        owner.prepare(self.roots[0], register=False)
        with self.assertRaises(TimeoutError):
            owner.ensure_model_loaded()
        self.assertLess(owner.load_seconds, 1.5)
        self.assertGreater(owner.load_seconds, 0)
        self.assertTrue(owner.close()["process_evidence"]["forced"])
        with self.assertRaises(remote.RemoteOwnerError):
            owner.set_initialization_deadline(time.monotonic() + 10)

    def test_paired_token_overflow_excludes_both(self):
        owner = self.owner()
        tiny = replace(self.roots[1], sampling=replace(self.roots[1].sampling, max_prompt_tokens=1))
        prepared, receipt = owner.prepare_group([self.roots[0], tiny])
        self.assertEqual(prepared, ())
        self.assertEqual(receipt["denominator"], 2)
        self.assertEqual(receipt["admitted"], 0)
        self.assertEqual(owner.accounting()["load_count"], 0)

    def test_audit_only_cannot_dispatch_and_changed_cache_cannot_dispatch(self):
        owner = self.owner()
        audit = owner.prepare(self.roots[0], register=False)
        owner.ensure_model_loaded()
        with self.assertRaisesRegex(remote.RemoteOwnerError, "unprepared"):
            owner.dispatch(audit, deadline_monotonic=time.monotonic() + 5)
        item = owner.prepare(self.roots[0])
        changed = replace(item, input_token_ids=(42,))
        with self.assertRaisesRegex(remote.RemoteOwnerError, "unprepared"):
            owner.dispatch(changed, deadline_monotonic=time.monotonic() + 5)

    def test_timeout_stops_child_and_charges_observed_dispatch(self):
        owner, item = self.ready(faults={"delay_generate_seconds": 2})
        with self.assertRaises(TimeoutError):
            owner.dispatch(item, deadline_monotonic=time.monotonic() + 0.15)
        self.assertGreaterEqual(owner.model_seconds, 0.15)
        self.assertEqual(owner.accounting()["physical_calls_attempted"], 1)
        receipt = owner.close()
        self.assertTrue(receipt["process_evidence"]["forced"])
        self.assertTrue(receipt["process_evidence"]["owned_io_threads_stopped"])
        self.assertIsNotNone(owner._process.returncode)

    def test_worker_crash_cannot_restart_or_retry(self):
        owner, item = self.ready(faults={"crash_generate": True})
        pid = owner._process.pid
        with self.assertRaises(EOFError):
            owner.dispatch(item, deadline_monotonic=time.monotonic() + 5)
        self.assertGreater(owner.model_seconds, 0)
        with self.assertRaises(remote.RemoteOwnerError):
            owner.dispatch(item, deadline_monotonic=time.monotonic() + 5)
        self.assertEqual(owner._process.pid, pid)
        self.assertTrue(owner.close()["process_evidence"]["forced"])

    def test_unknown_partial_load_is_proven_stopped_by_process_cleanup(self):
        owner = self.owner(faults={"fail_load": True})
        owner.initialize_tokenizer()
        with self.assertRaises(mp.ModelContractError):
            owner.ensure_model_loaded()
        closed = owner.close()
        self.assertTrue(closed["process_evidence"]["forced"])
        self.assertIsNone(closed["child_acknowledgement"])
        self.assertIsNotNone(owner._process.returncode)

    def test_bad_counter_rejected_without_success_receipt(self):
        owner, item = self.ready(faults={"bad_counter": True})
        with self.assertRaises(mp.ModelContractError):
            owner.dispatch(item, deadline_monotonic=time.monotonic() + 5)
        self.assertGreater(owner.model_seconds, 0)

    def test_failed_dispatch_elapsed_survives_coarse_monotonic_clock(self):
        owner, item = self.ready()
        coarse_now = time.monotonic()
        with patch.object(remote.time, "monotonic", return_value=coarse_now), \
             patch.object(remote.time, "perf_counter", side_effect=[10.0, 10.125]), \
             patch.object(owner, "_rpc", side_effect=mp.ModelContractError("synthetic failure")):
            with self.assertRaises(mp.ModelContractError):
                owner.dispatch(item, deadline_monotonic=coarse_now + 1)
        self.assertEqual(owner.model_seconds, 0.125)
        self.assertEqual(owner.accounting()["physical_calls_attempted"], 1)

    @unittest.skipUnless(os.name == "posix", "Linux /proc ownership requires Linux; Windows synthetic child only")
    def test_fault_grandchild_is_killed_by_parent_owned_tree(self):
        owner, item = self.ready(faults={"grandchild": True, "delay_generate_seconds": 2})
        with self.assertRaises(TimeoutError):
            owner.dispatch(item, deadline_monotonic=time.monotonic() + 0.5)
        evidence = owner.close()["process_evidence"]
        self.assertGreaterEqual(len(evidence["observed_process_identities"]), 2)
        self.assertFalse(owner._live())

    def test_unknown_protocol_action_is_rejected_as_data(self):
        owner = self.owner()
        owner.initialize_tokenizer()
        with self.assertRaisesRegex(mp.ModelContractError, "unknown IPC action"):
            owner._rpc("EXEC", {"source": "raise RuntimeError()"}, time.monotonic() + 5)
        self.assertEqual(owner.accounting()["load_count"], 0)


class RemoteProtocolPureTests(unittest.TestCase):
    def test_parent_state_may_change_but_birth_and_pid_may_not(self):
        initial = {"pid": 123, "birth": 987, "state": "R", "ppid": 7}
        self.assertTrue(remote._same_process({**initial, "state": "S"}, initial))
        self.assertFalse(remote._same_process({**initial, "birth": 988}, initial))
        self.assertFalse(remote._same_process({**initial, "pid": 124}, initial))
        self.assertFalse(remote._same_process(None, initial))

    def test_partial_writes_are_completed_and_oversize_reads_rejected(self):
        class ShortWriter(io.BytesIO):
            def write(self, raw):
                return super().write(raw[:3])
        stream = ShortWriter()
        remote._write_frame(stream, {"bounded": "value"})
        stream.seek(0)
        self.assertEqual(remote._read_frame(stream), {"bounded": "value"})
        with self.assertRaises(remote.RemoteOwnerError):
            remote._read_frame(io.BytesIO(struct.pack("!I", remote.MAX_FRAME_BYTES + 1)))

    def test_reconstruct_rejects_extra_fields_bool_tokens_and_forbidden_payload(self):
        planned = study()
        request = mp.materialize_request(planned, planned.calls[0])
        value = json.loads(remote._canonical(asdict(request)))
        self.assertEqual(remote._request(value), request)
        with self.assertRaises(remote.RemoteOwnerError):
            remote._request({**value, "code": "print(1)"})
        with self.assertRaises(remote.RemoteOwnerError):
            remote._prepared({"request": value, "input_token_ids": [True]})
        messages = json.loads(value["messages_json"])
        payload = json.loads(messages[1]["content"])
        payload["memory"] = {"query": [[1]]}
        messages[1]["content"] = mp.canonical(payload)
        with self.assertRaises(mp.ModelContractError):
            remote._request({**value, "messages_json": mp.canonical(messages)})


if __name__ == "__main__":
    unittest.main()

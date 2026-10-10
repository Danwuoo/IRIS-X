"""Real isolated-process IPC with a fixed fake backend; no model or CUDA."""
from dataclasses import asdict, replace
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.arc_public_research_20261010 import model_provider as mp, remote_model_owner as remote
from tools.arc_public_research_20261010.tests.test_generation_trie import requests
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory

PLAN_HASH = "e" * 64
SOURCE_ROOT = Path(__file__).resolve().parents[3]


def fixtures(directory):
    directory = Path(directory)
    names = ["tools/__init__.py", "tools/arc_consolidated_20261010/__init__.py",
             "tools/arc_consolidated_20261010/model_provider.py", remote.ENTRY,
             "tools/arc_public_research_20261010/model_provider.py",
             "tools/arc_public_research_20261010/finite_trie.py"]
    new_init = "tools/arc_public_research_20261010/__init__.py"
    if (SOURCE_ROOT / new_init).exists():
        names.append(new_init)
    source = {name: hashlib.sha256((SOURCE_ROOT / name).read_bytes()).hexdigest() for name in names}
    lock = directory / "synthetic-environment.json"
    lock.write_bytes(remote._canonical({"evidence_mode": "synthetic-test-only"}))
    prepared = {"python_command": [str(Path(sys.executable).resolve()), "-I", "-B", "-S"], "source_root": str(SOURCE_ROOT),
                "model_path": str(directory / "no-model"), "manifest_path": str(directory / "no-manifest"),
                "environment_lock_path": str(lock), "actual_environment_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest()}
    admission = {"format": "irisx/consolidated-runtime-admission-v2", "environment_plan_sha256": PLAN_HASH,
                 "source_identity_sha256": remote._digest(source), "prepared": prepared, "asset_receipts_sha256": "a" * 64}
    path = directory / "admission.json"; path.write_bytes(remote._canonical(admission))
    return {**prepared, "admission_path": str(path), "admission_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, source


class RemoteOwnerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory(); self.addCleanup(self.scratch.cleanup)
        self.bootstrap, self.source = fixtures(self.scratch.name)
        self.requests = requests()

    def owner(self, **kwargs):
        owner = remote.RemoteModelOwner._synthetic_for_tests(self.bootstrap,
            environment_plan_sha256=PLAN_HASH, source_identity=self.source,
            deadline_monotonic=time.monotonic() + 30, **kwargs)
        self.addCleanup(owner.close)
        return owner

    def ready(self, **kwargs):
        owner = self.owner(**kwargs)
        items, receipt = owner.prepare_group(list(self.requests[:2]))
        self.assertEqual(receipt["admitted"], 2)
        owner.ensure_model_loaded()
        return owner, items

    def test_inert_constructor_and_exact_production_backend(self):
        with patch.object(remote.subprocess, "Popen", side_effect=AssertionError("spawn")), \
             patch.object(remote, "_read_bound", side_effect=AssertionError("read")):
            owner = remote.RemoteModelOwner(self.bootstrap, environment_plan_sha256=PLAN_HASH,
                source_identity=self.source, deadline_monotonic=time.monotonic() + 10)
            self.assertFalse(owner.enabled); self.assertTrue(owner.close()["model_owner_stopped"])
        owner = mp.SingleModelOwner(lambda: object(), enabled=True, environment_sha256=PLAN_HASH)
        with self.assertRaisesRegex(mp.ModelContractError, "exact gated"):
            owner.initialize_tokenizer()
        with self.assertRaises(mp.ModelContractError):
            owner.initialize_tokenizer()

    def test_hardware_is_explicit_not_run_for_synthetic_and_unloaded(self):
        owner = self.owner()
        before = owner.accounting()["hardware_receipt"]
        self.assertEqual(before["status"], "not_run")
        self.assertEqual(before["reason"], "synthetic-test-only")
        self.assertIsNone(before["hardware"])
        first = owner.ensure_model_loaded()["hardware_receipt"]
        second = owner.ensure_model_loaded()["hardware_receipt"]
        self.assertEqual(first, before); self.assertEqual(second, first)
        self.assertEqual(owner.accounting()["hardware_receipt"], first)
        self.assertEqual(first["environment_sha256"], self.bootstrap["actual_environment_lock_sha256"])
        self.assertEqual(first["model_sha256"], mp.MODEL_MANIFEST_SHA256)
        self.assertEqual(first["sha256"], mp.digest({k: v for k, v in first.items() if k != "sha256"}))
        unloaded = mp.SingleModelOwner(lambda: None, environment_sha256=PLAN_HASH)
        receipt = unloaded.accounting()["hardware_receipt"]
        self.assertEqual(receipt["reason"], "model-not-loaded")
        self.assertIsNone(receipt["hardware"])

    def test_hardware_receipt_binding_unit_fixture_never_observes_gpu(self):
        # This is a serialization fixture, not an observed hardware claim.
        fixture = {"gpu_count": 1, "gpu_name": "SYNTHETIC UNIT FIXTURE",
                   "gpu_uuid": "NOT-A-REAL-GPU", "gpu_total_memory_bytes": 96000000000,
                   "driver_version": "fixture", "host_memory_bytes": 192000000000,
                   "compute_capability": [12, 0], "torch_cuda": "fixture",
                   "cpu_count": 48, "bf16_supported": True,
                   "target_machine_type": "g4-standard-48", "machine_type_verified": False}
        a = mp.hardware_receipt(fixture, execution_mode="g4",
            model_sha256=mp.MODEL_MANIFEST_SHA256, environment_sha256=PLAN_HASH)
        b = mp.hardware_receipt(fixture, execution_mode="g4",
            model_sha256=mp.MODEL_MANIFEST_SHA256, environment_sha256="a" * 64)
        self.assertNotEqual(a["sha256"], b["sha256"])
        self.assertEqual(a["hardware"], fixture)
        fixture["gpu_name"] = "changed fixture"
        self.assertNotEqual(a["hardware"], fixture)
        with self.assertRaises(mp.ModelContractError):
            mp.hardware_receipt(fixture, execution_mode="synthetic-test",
                model_sha256=mp.MODEL_MANIFEST_SHA256, environment_sha256=PLAN_HASH)
        with self.assertRaises(mp.ModelContractError):
            mp.hardware_receipt({**fixture, "machine_type_verified": True}, execution_mode="g4",
                model_sha256=mp.MODEL_MANIFEST_SHA256, environment_sha256=PLAN_HASH)

    def test_load_receipt_and_accounting_keep_observation_without_hardware_calls(self):
        fixture = {"gpu_count": 1, "gpu_name": "SYNTHETIC UNIT FIXTURE",
                   "gpu_uuid": "NOT-A-REAL-GPU", "gpu_total_memory_bytes": 96000000000,
                   "driver_version": "fixture", "host_memory_bytes": 192000000000,
                   "compute_capability": [12, 0], "torch_cuda": "fixture",
                   "cpu_count": 48, "bf16_supported": True,
                   "target_machine_type": "g4-standard-48", "machine_type_verified": False}
        owner = mp.SingleModelOwner(lambda: None, environment_sha256=PLAN_HASH)
        owner._backend = SimpleNamespace(hardware=fixture)
        with patch.object(mp.legacy.SingleModelOwner, "ensure_model_loaded",
                          return_value={"model_loaded": True}):
            receipt = owner.ensure_model_loaded()["hardware_receipt"]
        self.assertEqual(receipt["hardware"], fixture)
        self.assertEqual(owner.accounting()["hardware_receipt"], receipt)
        fixture["gpu_name"] = "mutation"
        self.assertNotEqual(owner.accounting()["hardware_receipt"]["hardware"], fixture)
        missing = mp.SingleModelOwner(lambda: None, environment_sha256=PLAN_HASH)
        missing._backend = SimpleNamespace()
        with patch.object(mp.legacy.SingleModelOwner, "ensure_model_loaded",
                          return_value={"model_loaded": True}):
            with self.assertRaises(mp.ModelContractError):
                missing.ensure_model_loaded()
        self.assertFalse(missing._model_ready)

    def test_new_source_admission_cannot_omit_any_executable(self):
        self.assertIn(remote.ENTRY, remote._admission(self.bootstrap, PLAN_HASH, self.source, synthetic=True))
        for name in (remote.ENTRY, "tools/arc_public_research_20261010/model_provider.py",
                     "tools/arc_public_research_20261010/finite_trie.py"):
            source = {k: v for k, v in self.source.items() if k != name}
            with self.assertRaises(remote.RemoteOwnerError):
                remote._verify_source(str(SOURCE_ROOT), source)

    def test_mutated_admission_never_spawns(self):
        owner = self.owner(); Path(self.bootstrap["admission_path"]).write_bytes(b"{}")
        with patch.object(remote.subprocess, "Popen", side_effect=AssertionError("spawn")), \
             self.assertRaises(remote.RemoteOwnerError):
            owner.initialize_tokenizer()
        self.assertIsNone(owner._process)

    def test_paired_admission_one_process_one_load_and_independent_caches(self):
        owner, items = self.ready(); pid = owner._process.pid
        self.assertEqual(items[0].input_token_ids, items[1].input_token_ids)
        self.assertNotEqual(items[0].cache_sha256, items[1].cache_sha256)
        owner.ensure_model_loaded()
        for item in items:
            result = owner.dispatch(item, deadline_monotonic=time.monotonic() + 5)
            self.assertEqual(result["request_sha256"], item.sha256)
            self.assertEqual(result["environment_sha256"], PLAN_HASH)
            self.assertNotEqual(result["actual_request_sha256"], item.sha256)
            self.assertTrue(result["native_eos_complete"])
            self.assertEqual(result["evidence_mode"], "synthetic-test-only")
        self.assertEqual(owner.accounting()["physical_calls_attempted"], 2)
        self.assertEqual(owner.accounting()["load_count"], 1)
        self.assertEqual(owner._process.pid, pid)
        with self.assertRaises(remote.RemoteOwnerError):
            owner.dispatch(items[0], deadline_monotonic=time.monotonic() + 5)
        closed = owner.close()
        self.assertTrue(closed["process_evidence"]["owned_io_threads_stopped"])
        self.assertIsNotNone(owner._process.returncode)

    def test_whole_pair_token_overflow_and_no_model_load(self):
        rows = list(self.requests[:2])
        data = json.loads(rows[0].messages_json)
        payload = json.loads(data[1]["content"])
        payload["grammar"] = {"synthetic_long": "x" * 7000}
        data[1]["content"] = mp.canonical(payload)
        rows = [replace(r, messages_json=mp.canonical(data)) for r in rows]
        owner = self.owner(); items, receipt = owner.prepare_group(rows)
        self.assertEqual(items, ()); self.assertEqual(receipt["denominator"], 2)
        self.assertEqual(receipt["admitted"], 0); self.assertEqual(owner.load_count, 0)

    def test_wrong_pair_and_audit_only_not_dispatchable(self):
        owner = self.owner()
        with self.assertRaises(mp.ModelContractError):
            owner.prepare_group([self.requests[0], self.requests[2]])
        item = owner.prepare(self.requests[0], register=False)
        owner.ensure_model_loaded()
        with self.assertRaises(remote.RemoteOwnerError):
            owner.dispatch(item, deadline_monotonic=time.monotonic() + 5)

    def test_timeout_consumes_attempt_and_proves_process_stop(self):
        owner, items = self.ready(faults={"delay_generate_seconds": 2})
        with self.assertRaises(TimeoutError):
            owner.dispatch(items[0], deadline_monotonic=time.monotonic() + .15)
        self.assertEqual(owner.accounting()["physical_calls_attempted"], 1)
        self.assertGreaterEqual(owner.model_seconds, .15)
        closed = owner.close(); self.assertTrue(closed["process_evidence"]["forced"])
        self.assertIsNotNone(owner._process.returncode)

    def test_crash_eof_no_retry_or_implicit_restart(self):
        owner, items = self.ready(faults={"crash_generate": True}); pid = owner._process.pid
        with self.assertRaises(EOFError):
            owner.dispatch(items[0], deadline_monotonic=time.monotonic() + 5)
        with self.assertRaises(remote.RemoteOwnerError):
            owner.dispatch(items[0], deadline_monotonic=time.monotonic() + 5)
        self.assertEqual(owner._process.pid, pid)
        self.assertEqual(owner.accounting()["physical_calls_attempted"], 1)

    def test_unknown_partial_load_forces_cleanup(self):
        owner = self.owner(faults={"fail_load": True}); owner.initialize_tokenizer()
        with self.assertRaises(mp.ModelContractError):
            owner.ensure_model_loaded()
        closed = owner.close()
        self.assertTrue(closed["process_evidence"]["forced"])
        self.assertIsNone(closed["child_acknowledgement"])

    def test_owned_grandchild_is_reaped_even_after_false_backend_ack(self):
        owner, items = self.ready(faults={"grandchild": True})
        owner.dispatch(items[0], deadline_monotonic=time.monotonic() + 5)
        time.sleep(.08)
        self.assertTrue(owner._live())
        closed = owner.close()
        self.assertEqual(closed["process_evidence"]["owned_descendants"], [])
        self.assertGreaterEqual(len(closed["process_evidence"]["observed_process_identities"]), 2)

    def test_bad_counter_and_bound_frame_reject(self):
        owner, items = self.ready(faults={"bad_counter": True})
        with self.assertRaises(mp.ModelContractError):
            owner.dispatch(items[0], deadline_monotonic=time.monotonic() + 5)
        with self.assertRaises(remote.RemoteOwnerError):
            remote._read_frame(io.BytesIO(struct.pack("!I", remote.MAX_FRAME_BYTES + 1)))
        with self.assertRaises(EOFError):
            remote._read_frame(io.BytesIO(struct.pack("!I", 100) + b"{}"))

    def test_session_and_call_caps_and_physical_240(self):
        with self.assertRaises(remote.RemoteOwnerError):
            remote.RemoteModelOwner(self.bootstrap, environment_plan_sha256=PLAN_HASH,
                source_identity=self.source, deadline_monotonic=time.monotonic() + 7201)
        owner, items = self.ready()
        with self.assertRaises(remote.RemoteOwnerError):
            owner.dispatch(items[0], deadline_monotonic=time.monotonic() + 121)
        owner._attempted = {"synthetic_" + str(i) for i in range(240)}
        with self.assertRaises(remote.RemoteOwnerError):
            owner.dispatch(items[0], deadline_monotonic=time.monotonic() + 5)
        self.assertEqual(mp.MAX_CALLS, 240)


if __name__ == "__main__":
    unittest.main()

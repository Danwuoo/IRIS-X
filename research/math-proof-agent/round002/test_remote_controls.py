"""Offline constant-only publisher/monitor controls; never a Kaggle run."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
TEST_SOURCE_HASHES = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                      for name in ("test_remote_controls.py", "kaggle_run.py", "common.py", "sdk_readback.py")}
sys.path.insert(0, str(HERE))
import kaggle_run as monitor
import sdk_readback as sdk
from common import atomic_json, file_digest

OFFLINE_GUARD_ACTIVE = False


def setUpModule():
    global OFFLINE_GUARD_ACTIVE
    OFFLINE_GUARD_ACTIVE = True


def tearDownModule():
    global OFFLINE_GUARD_ACTIVE
    if any(hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected
           for name, expected in TEST_SOURCE_HASHES.items()):
        raise RuntimeError("Tested sources changed during remote controls")
    OFFLINE_GUARD_ACTIVE = False


def deny_external_operations(event, args):
    """Process-wide guard: forgotten mocks cannot use a provider or real state."""
    if not OFFLINE_GUARD_ACTIVE:
        return
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.posix_spawnp",
                 "socket.__new__", "socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
        raise RuntimeError("R3 offline controls deny network and subprocess operations")
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
        protected = os.path.normcase(str(monitor.STATE_ROOT / "state.json"))
        if path == protected:
            raise RuntimeError("R3 controls must not read or write real task state")


sys.addaudithook(deny_external_operations)


def notebook():
    return {"cells": [{"cell_type": "code", "source": ["print(1)\n"],
                       "outputs": [], "execution_count": None, "metadata": {}}],
            "metadata": {}, "nbformat": 4, "nbformat_minor": 5}


def manifest(run_id="synthetic-run-1", timeout=1800):
    return {"task": "MATH-002", "kind": "smoke", "run_id": run_id,
            "notebook_id": "synthetic-owner/math-only-controls-" + run_id, "timeout_seconds": timeout,
            "code_sha": "1" * 40, "source_sha256": "2" * 64,
            "protocol_sha256": "3" * 64, "panel_sha256": "4" * 64,
            "model_sha256": "5" * 64, "source_files": {"fixture.py": "6" * 64},
            "notebook_sha256": sdk.notebook_source_identity(notebook())}


class SourceIdentityControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="math002-remote-constants-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = manifest() | {"version": 1, "state": "submitted"}

    def test_plain_and_versioned_reference(self):
        self.assertEqual(sdk.parse_reference("owner/task-slug"), ("owner", "task-slug", None))
        self.assertEqual(sdk.parse_reference("owner/task-slug/17"), ("owner", "task-slug", 17))

    def test_invalid_reference_rejected(self):
        for value in ("owner", "owner/slug/0", "owner/slug/-1", "owner/slug/01",
                      "owner/slug/1/extra", "../slug", "owner/slug\n", "owner/slug?x=1"):
            with self.subTest(reference=value), self.assertRaises(ValueError):
                sdk.parse_reference(value)

    def test_source_list_and_string_normalize_equally(self):
        first, second = notebook(), notebook()
        second["cells"][0]["source"] = "print(1)\n"
        self.assertEqual(sdk.notebook_source_identity(first), sdk.notebook_source_identity(second))

    def test_outputs_and_metadata_do_not_change_source_identity(self):
        first, second = notebook(), notebook()
        second["metadata"] = {"kaggle": {"execution": True}}
        second["cells"][0]["outputs"] = [{"text": "synthetic output"}]
        second["cells"][0]["execution_count"] = 15
        self.assertEqual(sdk.notebook_source_identity(first), sdk.notebook_source_identity(second))

    def test_source_and_cell_type_changes_are_bound(self):
        for key, value in (("source", "print(2)\n"), ("cell_type", "markdown")):
            changed = notebook()
            changed["cells"][0][key] = value
            self.assertNotEqual(sdk.notebook_source_identity(notebook()), sdk.notebook_source_identity(changed))

    def test_independent_digest_and_monitor_agree(self):
        expected = hashlib.sha256(json.dumps([{"cell_type": "code", "source": "print(1)\n"}],
            sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        path = self.root / "synthetic.ipynb"
        atomic_json(path, notebook())
        self.assertEqual(sdk.notebook_source_identity(notebook()), expected)
        self.assertEqual(monitor.notebook_identity(path), expected)

    def fake_source_receipt(self, version=1, overrides=None, source=None, code_file="synthetic.ipynb"):
        def receipt(_root, command, timeout=120):
            if command[:3] == ["kaggle", "kernels", "pull"]:
                destination = Path(command[command.index("-p") + 1])
                atomic_json(destination / "kernel-metadata.json", {
                    "id": self.run["notebook_id"], "is_private": True, "code_file": code_file})
                atomic_json(destination / "synthetic.ipynb", source or notebook())
                return {"exit_code": 0, "stdout": ""}
            self.assertIn("sdk_readback.py", command[-2])
            value = {"ref": self.run["notebook_id"], "current_version_number": version,
                     "is_private": True, "notebook_sha256": self.run["notebook_sha256"]}
            value.update(overrides or {})
            return {"exit_code": 0, "stdout": json.dumps(value)}
        return receipt

    def test_matching_current_version_and_source_pass(self):
        with mock.patch.object(monitor, "receipt", side_effect=self.fake_source_receipt()):
            for versioned in (False, True):
                result = monitor.source_readback(self.root, self.run, versioned)
                self.assertEqual(result["current_version_number"], 1)

    def test_same_source_newer_version_fails(self):
        with mock.patch.object(monitor, "receipt", side_effect=self.fake_source_receipt(version=2)):
            for versioned in (False, True):
                with self.subTest(versioned=versioned), self.assertRaisesRegex(RuntimeError, "exact version"):
                    monitor.source_readback(self.root, self.run, versioned)

    def test_wrong_sdk_owner_source_or_privacy_fails(self):
        for override in ({"ref": "other/other"}, {"is_private": False}, {"notebook_sha256": "0" * 64}):
            with self.subTest(override=override), mock.patch.object(monitor, "receipt", side_effect=self.fake_source_receipt(overrides=override)):
                with self.assertRaisesRegex(RuntimeError, "exact version"):
                    monitor.source_readback(self.root, self.run, False)

    def test_ambiguous_sdk_version_type_fails(self):
        for value in (True, False, None, 0, "1", 1.0):
            with self.subTest(version=value), mock.patch.object(monitor, "receipt", side_effect=self.fake_source_receipt(version=value)):
                with self.assertRaisesRegex(RuntimeError, "exact version"):
                    monitor.source_readback(self.root, self.run, False)

    def test_changed_pulled_source_fails_before_sdk(self):
        changed = notebook()
        changed["cells"][0]["source"] = "print(2)"
        with mock.patch.object(monitor, "receipt", side_effect=self.fake_source_receipt(source=changed)) as receipt:
            with self.assertRaisesRegex(RuntimeError, "source identity"):
                monitor.source_readback(self.root, self.run, False)
            self.assertEqual(receipt.call_count, 1)

    def test_unsafe_remote_code_path_fails(self):
        with mock.patch.object(monitor, "receipt", side_effect=self.fake_source_receipt(code_file="../outside.ipynb")):
            with self.assertRaisesRegex(RuntimeError, "code path"):
                monitor.source_readback(self.root, self.run, False)

    def test_import_does_not_initialize_kaggle(self):
        self.assertNotIn("kaggle", sys.modules)


class ReservationControls(unittest.TestCase):
    def test_reused_slug_is_rejected(self):
        old = manifest("first") | {"state": "error", "root_cause": "setup"}
        new = manifest("second") | {"notebook_id": old["notebook_id"]}
        with self.assertRaisesRegex(ValueError, "fresh task slug"):
            monitor.reserve({"runs": [old]}, new)

    def test_complete_status_needs_bound_artifacts(self):
        state = {"runs": [manifest("first") | {"state": "complete"}]}
        with self.assertRaisesRegex(ValueError, "retrieved run-bound"):
            monitor.reserve(state, manifest("second"))
        state["runs"][0]["retrieval"] = {"verified": True}
        monitor.reserve(state, manifest("second"))

    def test_first_run_must_be_bounded_smoke(self):
        for entry in (manifest(timeout=1801), manifest() | {"kind": "panel"}):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                monitor.reserve({"runs": []}, entry)

    def test_valid_reservation_is_unknown_before_submission(self):
        state = {"runs": []}
        result = monitor.reserve(state, manifest())
        self.assertEqual(result["state"], "submission_unknown")
        self.assertIsNone(result["version"])
        self.assertEqual(len(state["runs"]), 1)

    def test_unknown_or_active_run_blocks_second_submission(self):
        for status in ("submission_unknown", "submitted", "running", "queued"):
            state = {"runs": [manifest() | {"state": status}]}
            before = copy.deepcopy(state)
            with self.subTest(status=status), self.assertRaises(ValueError):
                monitor.reserve(state, manifest("synthetic-run-2"))
            self.assertEqual(state, before)

    def test_terminal_failure_requires_root_cause(self):
        for status in ("error", "canceled", "cancelacknowledged", "confirmed_not_started"):
            state = {"runs": [manifest() | {"state": status}]}
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "diagnose"):
                monitor.reserve(state, manifest("synthetic-run-2"))

    def test_two_same_root_causes_block_retry(self):
        state = {"runs": [manifest("first") | {"state": "error", "root_cause": "synthetic_platform"},
                           manifest("second") | {"state": "error", "root_cause": "synthetic_platform"}]}
        with self.assertRaisesRegex(ValueError, "same root cause"):
            monitor.reserve(state, manifest("third"))

    def test_diagnosed_single_failure_keeps_its_budget_charge(self):
        state = {"runs": [manifest("first") | {"state": "error", "root_cause": "synthetic_platform"}]}
        monitor.reserve(state, manifest("second"))
        self.assertEqual(sum(run["timeout_seconds"] for run in state["runs"]), 3600)

    def test_count_and_total_timeout_caps(self):
        capped = {"runs": [manifest(str(i)) | {"state": "complete"} for i in range(4)]}
        total = {"runs": [manifest("first", 10800) | {"state": "complete"},
                            manifest("second", 10800) | {"state": "complete"}]}
        for state in (capped, total):
            with self.assertRaisesRegex(ValueError, "budget exhausted"):
                monitor.reserve(state, manifest("extra"))
        for timeout in (True, 0, -1, 10801):
            with self.assertRaisesRegex(ValueError, "timeout"):
                monitor.reserve({"runs": []}, manifest(timeout=timeout))


class RetrievalControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="math002-output-constants-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = manifest() | {"version": 1, "state": "complete"}
        atomic_json(self.root / "state.json", {"task": "MATH-002", "runs": [self.run]})

    def retrieve_fixture(self, *, manifest_overrides=None, artifact_overrides=None, tamper=False, extra_manifest=False):
        def output_receipt(_root, command, timeout=120):
            self.assertEqual(command[:3], ["kaggle", "kernels", "output"])
            destination = Path(command[command.index("-p") + 1])
            saved = {**self.run, **(manifest_overrides or {})}
            atomic_json(destination / "run-manifest.json", saved)
            atomic_json(destination / "result.json", {"scope": "synthetic constant only"})
            files = {name: file_digest(destination / name) for name in ("run-manifest.json", "result.json")}
            artifact = {"run_id": self.run["run_id"], "code_sha": self.run["code_sha"],
                        "source_sha256": self.run["source_sha256"], "files": files,
                        **(artifact_overrides or {})}
            atomic_json(destination / "artifact-manifest.json", artifact)
            if tamper:
                atomic_json(destination / "result.json", {"scope": "changed bytes"})
            if extra_manifest:
                atomic_json(destination / "nested/artifact-manifest.json", artifact)
            return {"exit_code": 0, "stdout": "synthetic output only"}
        with mock.patch.object(monitor, "source_readback", return_value={}), mock.patch.object(monitor, "receipt", side_effect=output_receipt):
            return monitor.retrieve(self.root)

    def test_complete_matching_artifacts_verify(self):
        self.assertTrue(self.retrieve_fixture()["verified"])

    def test_artifact_source_fingerprint_mismatch_fails(self):
        self.assertFalse(self.retrieve_fixture(artifact_overrides={"source_sha256": "0" * 64})["verified"])

    def test_saved_manifest_fingerprint_and_budget_mismatch_fail(self):
        for key in ("run_id", "code_sha", "source_sha256", "protocol_sha256", "panel_sha256", "model_sha256", "timeout_seconds", "source_files"):
            with self.subTest(field=key):
                self.assertFalse(self.retrieve_fixture(manifest_overrides={key: "synthetic-mismatch"})["verified"])

    def test_changed_output_bytes_fail(self):
        self.assertFalse(self.retrieve_fixture(tamper=True)["verified"])

    def test_unsafe_output_path_fails(self):
        self.assertFalse(self.retrieve_fixture(artifact_overrides={"files": {"../outside": "0" * 64}})["verified"])

    def test_missing_file_list_or_ambiguous_manifests_fail(self):
        self.assertFalse(self.retrieve_fixture(artifact_overrides={"files": {}})["verified"])
        self.assertFalse(self.retrieve_fixture(extra_manifest=True)["verified"])

    def test_unresolved_run_cannot_be_retrieved(self):
        for status in ("submitted", "running", "submission_unknown"):
            atomic_json(self.root / "state.json", {"task": "MATH-002", "runs": [self.run | {"state": status}]})
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "terminal"):
                monitor.retrieve(self.root)

    def test_retrieval_source_failure_revokes_old_verified_dispatch(self):
        self.run["retrieval"] = {"verified": True, "path": "historical-synthetic-output"}
        for failed_index in range(3):
            atomic_json(self.root / "state.json", {"task": "MATH-002", "runs": [self.run]})
            calls = []
            def readback(*_):
                calls.append(None)
                if len(calls) - 1 == failed_index:
                    raise RuntimeError("retrieval source drift")
                return {}
            with self.subTest(failed_index=failed_index), mock.patch.object(monitor, "source_readback", side_effect=readback), \
                    mock.patch.object(monitor, "receipt", return_value={"exit_code": 1, "stdout": "synthetic output failure"}):
                with self.assertRaisesRegex(RuntimeError, "source drift"):
                    monitor.retrieve(self.root)
            state = monitor.read_state(self.root)
            self.assertEqual(state["runs"][0]["state"], "complete")
            self.assertEqual(state["runs"][0]["retrieval"], self.run["retrieval"])
            self.assertEqual(state["runs"][0]["dispatch_state"], "needs_reconcile")
            with self.assertRaisesRegex(ValueError, "reconciliation"):
                monitor.reserve(state, manifest("next"))

    def test_successful_output_retrieval_cannot_clear_sticky_observation_failure(self):
        self.run.update(dispatch_state="needs_reconcile", identity_status="identity_unknown",
                        last_event="observation_error: prior source drift")
        atomic_json(self.root / "state.json", {"task": "MATH-002", "runs": [self.run]})
        self.assertTrue(self.retrieve_fixture()["verified"])
        state = monitor.read_state(self.root)
        self.assertEqual(state["runs"][0]["dispatch_state"], "needs_reconcile")
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            monitor.reserve(state, manifest("next"))


class ObservationReconciliationControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="math002-r3-mocked-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = manifest() | {"version": 1, "state": "complete",
                                 "retrieval": {"verified": True, "path": "historical-synthetic-output"},
                                 "latest_readback": {"historical": True}}
        self.save()

    def save(self):
        atomic_json(self.root / "state.json", {"task": "MATH-002", "runs": [self.run]})

    def state(self):
        return monitor.read_state(self.root)

    def readback(self, root, run, versioned):
        self.assertEqual(root, self.root)
        self.assertEqual(run["notebook_id"], self.run["notebook_id"])
        self.assertIs(type(run["version"]), int)
        self.assertEqual(run["version"], 1)
        return {"ref": run["notebook_id"] + ("/1" if versioned else ""),
                "current_version_number": 1, "notebook_sha256": run["notebook_sha256"], "private": True}

    def status_receipt(self, status="complete", *, exit_code=0, stdout=None):
        def fake(root, command, timeout=120):
            self.assertEqual(root, self.root)
            self.assertEqual(command, ["kaggle", "kernels", "status", self.run["notebook_id"] + "/1"])
            return {"exit_code": exit_code, "stdout": stdout if stdout is not None else
                    self.run["notebook_id"] + ' has status "KernelWorkerStatus.' + status.upper() + '"'}
        return fake

    def observe(self, *, readback=None, status="complete", exit_code=0, stdout=None):
        with mock.patch.object(monitor, "source_readback", side_effect=readback or self.readback), \
                mock.patch.object(monitor, "receipt", side_effect=self.status_receipt(status, exit_code=exit_code, stdout=stdout)):
            return monitor.observe_once(self.root)

    def assert_blocked_preserving_history(self, expected_state="complete"):
        state = self.state()
        run = state["runs"][0]
        self.assertEqual(run["state"], expected_state)
        self.assertEqual(run["retrieval"], self.run["retrieval"])
        self.assertEqual(run["dispatch_state"], "needs_reconcile")
        self.assertEqual(run["identity_status"], "identity_unknown")
        self.assertEqual(len(state["runs"]), 1)
        self.assertEqual(sum(r["timeout_seconds"] for r in state["runs"]), 1800)
        before = copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            monitor.reserve(state, manifest("next"))
        self.assertEqual(state, before)

    def test_completed_verified_run_loses_dispatch_on_source_failure(self):
        self.observe()
        def mismatch(*_):
            raise RuntimeError("remote source identity mismatch")
        result = self.observe(readback=mismatch)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["dispatch_state"], "needs_reconcile")
        self.assert_blocked_preserving_history()

    def test_each_exact_and_latest_guard_failure_is_sticky(self):
        for failed_index in range(3):
            with self.subTest(failed_index=failed_index):
                self.save()
                calls = []
                def fail_at(root, run, versioned):
                    calls.append(versioned)
                    if len(calls) - 1 == failed_index:
                        raise RuntimeError("source/version/privacy readback mismatch")
                    return self.readback(root, run, versioned)
                self.observe(readback=fail_at)
                self.assert_blocked_preserving_history()
                self.assertEqual(calls, [True, False, False][:failed_index + 1])

    def test_unavailable_unknown_or_ambiguous_status_cannot_release(self):
        cases = [(1, None), (None, None), (0, ""), (0, 'has status "UNKNOWN"'),
                 (0, 'has status "COMPLETE"\nhas status "RUNNING"'),
                 (0, 'has status "COMPLETE"\nhas status "unknown.value"')]
        for code, output in cases:
            with self.subTest(exit_code=code, stdout=output):
                self.save()
                self.observe(exit_code=code, stdout=output)
                self.assert_blocked_preserving_history()

    def test_historical_terminal_never_overwritten_by_changed_status(self):
        for status in ("running", "queued", "error", "canceled", "cancelacknowledged"):
            with self.subTest(status=status):
                self.save()
                self.observe(status=status)
                self.assert_blocked_preserving_history()
                self.assertEqual(self.state()["runs"][0]["observation_history"][-1]["observed_status"], status)

    def test_failed_terminal_keeps_diagnosis_and_budget_but_revokes_dispatch(self):
        self.run.update(state="error", root_cause="authored-platform-failure")
        self.save()
        self.observe(status="complete")
        self.assert_blocked_preserving_history(expected_state="error")
        self.assertEqual(self.state()["runs"][0]["root_cause"], "authored-platform-failure")

    def test_matched_readonly_reconciliation_releases_only_current_guard(self):
        self.observe(stdout="ambiguous")
        with mock.patch.object(monitor, "source_readback", side_effect=self.readback) as readback, \
                mock.patch.object(monitor, "receipt", side_effect=self.status_receipt()) as receipt:
            result = monitor.reconcile(self.root)
        self.assertEqual([call.args[2] for call in readback.call_args_list], [True, False, False])
        self.assertEqual(receipt.call_count, 1)  # status only; no push/output/download
        self.assertEqual(result["dispatch_state"], "matched")
        state = self.state()
        self.assertEqual([e["event"] for e in state["runs"][0]["observation_history"]],
                         ["observation_error", "matched_observation"])
        self.assertEqual(state["runs"][0]["retrieval"], self.run["retrieval"])
        monitor.reserve(state, manifest("next"))
        self.assertEqual(len(state["runs"]), 2)
        self.assertEqual(sum(r["timeout_seconds"] for r in state["runs"]), 3600)
        self.assertEqual(state["runs"][1]["state"], "submission_unknown")

    def test_failed_reconcile_remains_blocked(self):
        self.observe(stdout="ambiguous")
        with mock.patch.object(monitor, "source_readback", side_effect=self.readback), \
                mock.patch.object(monitor, "receipt", side_effect=self.status_receipt("running")):
            monitor.reconcile(self.root)
        self.assert_blocked_preserving_history()
        self.assertEqual(len(self.state()["runs"][0]["observation_history"]), 2)

    def test_matched_active_run_still_cannot_dispatch(self):
        self.run["state"] = "submitted"
        self.save()
        self.observe(status="running")
        state = self.state()
        self.assertEqual(state["runs"][0]["dispatch_state"], "matched")
        with self.assertRaisesRegex(ValueError, "active"):
            monitor.reserve(state, manifest("next"))

    def test_legacy_error_or_identity_marker_cannot_reuse_verified_output(self):
        for marker in ({"last_event": "observation_error: legacy failed readback"},
                       {"dispatch_state": "needs_reconcile"}, {"dispatch_state": "identity_unknown"},
                       {"identity_status": "identity_unknown"}, {"needs_reconcile": True}):
            state = {"runs": [self.run | marker]}
            before = copy.deepcopy(state)
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, "reconciliation"):
                monitor.reserve(state, manifest("next"))
            self.assertEqual(state, before)

    def test_legacy_observation_error_can_be_reconciled_without_erasing_complete(self):
        self.run["last_event"] = "observation_error: legacy mismatch"
        self.save()
        with mock.patch.object(monitor, "source_readback", side_effect=self.readback), \
                mock.patch.object(monitor, "receipt", side_effect=self.status_receipt()):
            monitor.reconcile(self.root)
        state = self.state()
        self.assertEqual(state["runs"][0]["state"], "complete")
        self.assertEqual(state["runs"][0]["observation_history"][0]["event"], "legacy_observation_error")
        monitor.reserve(state, manifest("next"))

    def test_matched_marker_with_wrong_identity_or_observed_status_cannot_dispatch(self):
        self.observe()
        for field, value in (("dispatch_identity", {}), ("observed_status", "running")):
            state = self.state()
            state["runs"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "identity"):
                monitor.reserve(state, manifest("next"))

    def test_missing_or_ambiguous_terminal_version_cannot_be_replaced(self):
        for version in (None, True, 0, "1", 1.0):
            with self.subTest(version=version):
                self.run.update(version=version, dispatch_state="needs_reconcile")
                self.save()
                with mock.patch.object(monitor, "receipt", side_effect=AssertionError("no version guessing")) as receipt, \
                        mock.patch.object(monitor, "source_readback", side_effect=AssertionError("invalid version")) as readback:
                    monitor.reconcile(self.root)
                self.assertEqual(receipt.call_count, 0)
                self.assertEqual(readback.call_count, 0)
                self.assert_blocked_preserving_history()

    def test_unknown_push_matching_readback_can_bind_without_refund_or_push(self):
        self.run.update(state="submission_unknown", version=None)
        self.save()
        calls = []
        def fake(root, command, timeout=120):
            calls.append(command)
            if command[:3] == ["kaggle", "kernels", "status"]:
                return self.status_receipt("running")(root, command, timeout)
            self.assertIn("sdk_readback.py", command[-2])
            return {"exit_code": 0, "stdout": json.dumps({"ref": self.run["notebook_id"],
                    "is_private": True, "notebook_sha256": self.run["notebook_sha256"], "current_version_number": 1})}
        with mock.patch.object(monitor, "source_readback", side_effect=self.readback), \
                mock.patch.object(monitor, "receipt", side_effect=fake):
            result = monitor.reconcile(self.root)
        self.assertEqual((result["state"], result["version"], result["dispatch_state"]), ("running", 1, "matched"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(sum(r["timeout_seconds"] for r in self.state()["runs"]), 1800)

    def test_unknown_push_mismatched_readback_stays_unknown_and_charged(self):
        for identity in ({}, {"ref": "other/slug"}, {"current_version_number": True}):
            self.run.update(state="submission_unknown", version=None)
            self.save()
            with self.subTest(identity=identity), mock.patch.object(monitor, "receipt", return_value={"exit_code": 0, "stdout": json.dumps(identity)}), \
                    mock.patch.object(monitor, "source_readback", side_effect=AssertionError("unmatched version")) as readback:
                result = monitor.reconcile(self.root)
            self.assertEqual((result["state"], result["version"], result["dispatch_state"]),
                             ("submission_unknown", None, "needs_reconcile"))
            self.assertEqual(readback.call_count, 0)
            self.assertEqual(sum(r["timeout_seconds"] for r in self.state()["runs"]), 1800)

    def test_offline_guard_denies_process_network_and_real_state(self):
        with self.assertRaisesRegex(RuntimeError, "deny network and subprocess"):
            subprocess.run(["R3-FORBIDDEN-PROCESS"])
        with self.assertRaisesRegex(RuntimeError, "deny network and subprocess"):
            socket.socket()
        with self.assertRaisesRegex(RuntimeError, "must not read or write"):
            deny_external_operations("open", (str(monitor.STATE_ROOT / "state.json"), "rb"))

    def test_effective_controlled_startup(self):
        self.assertEqual(os.environ.get("PYTHONHASHSEED"), "0")
        self.assertEqual(sys.flags.hash_randomization, 0)
        self.assertTrue(sys.flags.safe_path)
        self.assertTrue(sys.flags.no_user_site)
        self.assertTrue(sys.dont_write_bytecode)


if __name__ == "__main__":
    print(json.dumps({"python": platform.python_version(), "platform": platform.platform(),
                      "optimize": sys.flags.optimize, "hash_randomization": sys.flags.hash_randomization,
                      "safe_path": sys.flags.safe_path, "no_user_site": sys.flags.no_user_site,
                      "dont_write_bytecode": sys.dont_write_bytecode,
                      "source_files": TEST_SOURCE_HASHES,
                      "mode": "mocked; process/network audit denial; temp states only"}), flush=True)
    unittest.main(verbosity=2)

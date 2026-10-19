"""Offline constant-only publisher/monitor controls; never a Kaggle run."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kaggle_run as monitor
import sdk_readback as sdk
from common import atomic_json, file_digest


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


if __name__ == "__main__":
    unittest.main(verbosity=2)

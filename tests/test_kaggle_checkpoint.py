from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import support  # noqa: F401

from irisx.kaggle_runner_v4 import (
    CHECKPOINT_FORMAT,
    CHECKPOINT_POLICY,
    SMOKE_INVOCATION_LIMIT,
    _load_checkpoint,
    _new_state,
    _persist_checkpoint,
    _recover_pending,
    _tasks,
    _validate_state,
)


def identity() -> dict:
    ref = {
        "kind": "irisx/candidate-configuration",
        "artifact_id": "configuration",
        "version": "1.0.0",
        "content_digest": "sha256:" + "a" * 64,
    }
    return {
        "bundle_id": "run-002",
        "trial_manifest_digest": "sha256:" + "b" * 64,
        "model_source_provenance_digest": "sha256:" + "c" * 64,
        "repository_revision": "d" * 40,
        "notebook_digest": "sha256:" + "e" * 64,
        "runner_digest": "sha256:" + "f" * 64,
        "runner_core_digest": "sha256:" + "1" * 64,
        "baseline_configuration_ref": ref,
        "candidate_configuration_ref": {**ref, "artifact_id": "candidate"},
        "execution_envelope_ref": {**ref, "kind": "irisx/execution-envelope", "artifact_id": "envelope"},
        "checkpoint_policy": CHECKPOINT_POLICY,
    }


def keys() -> list[dict]:
    return [
        {
            "configuration": "baseline",
            "case_id": "case-001",
            "test_index": 0,
            "attempt_index": attempt_index,
        }
        for attempt_index in range(2)
    ]


def attempt(index: int) -> dict:
    return {
        "attempt_index": index,
        "status": "ok",
        "grid": [[index]],
        "raw_output_digest": "sha256:" + str(index) * 64,
    }


def record_session(state: dict) -> None:
    state["session_count"] = 1
    state["sessions"] = [
        {
            "session_index": 0,
            "hardware": {"gpu_model": "NVIDIA RTX PRO 6000"},
            "software": {
                "python": "3.12.13",
                "torch": "2.10.0+cu128",
                "transformers": "5.8.1",
            },
        }
    ]


class KaggleCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.package = self.root / "checkpoint-package.zip"
        self.progress = self.root / "progress.jsonl"
        self.progress.write_bytes(b"")
        self.identity = identity()
        self.keys = keys()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_smoke_limit_covers_both_configurations_in_four_invocations(self) -> None:
        tasks = _tasks(
            {"payload": {"cases": [{"case_id": "case-001", "test": [{"input": [[0]]}]}]}},
            {"artifact_id": "baseline"},
            {"artifact_id": "candidate"},
            {"payload": {"system": "baseline"}},
            {"payload": {"system": "candidate"}},
        )
        self.assertEqual(SMOKE_INVOCATION_LIMIT, 4)
        self.assertEqual(
            [task["key"]["configuration"] for task in tasks[:4]],
            ["baseline", "baseline", "candidate", "candidate"],
        )
        self.assertEqual(
            [task["key"]["attempt_index"] for task in tasks[:4]],
            [0, 1, 0, 1],
        )

    def test_checkpoint_round_trip_is_atomic_and_identity_bound(self) -> None:
        state = _new_state(self.identity)
        record_session(state)
        state["completed"].append(
            {"key": self.keys[0], "attempt": attempt(0), "elapsed_seconds": 1.25}
        )
        state["consumed_wall_clock_seconds"] = 1.25
        _persist_checkpoint(self.package, self.progress, state)
        loaded_progress = self.root / "loaded-progress.jsonl"
        loaded = _load_checkpoint(
            self.package,
            self.identity,
            self.keys,
            43200,
            loaded_progress,
        )
        self.assertEqual(loaded, state)
        self.assertEqual(loaded_progress.read_bytes(), b"")
        self.assertFalse(self.package.with_name(".checkpoint-package.zip.tmp").exists())

        changed_identity = copy.deepcopy(self.identity)
        changed_identity["runner_digest"] = "sha256:" + "9" * 64
        with self.assertRaisesRegex(RuntimeError, "identity"):
            _load_checkpoint(
                self.package,
                changed_identity,
                self.keys,
                43200,
                self.root / "rejected-progress.jsonl",
            )

    def test_checkpoint_rejects_noncontiguous_or_over_budget_state(self) -> None:
        state = _new_state(self.identity)
        state["completed"].append(
            {"key": self.keys[1], "attempt": attempt(1), "elapsed_seconds": 1.0}
        )
        with self.assertRaisesRegex(RuntimeError, "contiguous"):
            _validate_state(state, self.identity, self.keys, 43200)

        state = _new_state(self.identity)
        state["consumed_wall_clock_seconds"] = 43201
        with self.assertRaisesRegex(RuntimeError, "wall-clock"):
            _validate_state(state, self.identity, self.keys, 43200)

        state = _new_state(self.identity)
        state["completed"].append(
            {"key": self.keys[0], "attempt": attempt(0), "elapsed_seconds": 1.0}
        )
        state["consumed_wall_clock_seconds"] = 1.0
        with self.assertRaisesRegex(RuntimeError, "recorded session"):
            _validate_state(state, self.identity, self.keys, 43200)

    def test_checkpoint_rejects_tampered_member_digest(self) -> None:
        state = _new_state(self.identity)
        _persist_checkpoint(self.package, self.progress, state)
        with zipfile.ZipFile(self.package) as archive:
            contents = {name: archive.read(name) for name in archive.namelist()}
        contents["checkpoint.json"] = json.dumps(state).encode("utf-8") + b"\n"
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(tampered, "w") as archive:
            for name, data in contents.items():
                archive.writestr(name, data)
        with self.assertRaisesRegex(RuntimeError, "canonical|binding"):
            _load_checkpoint(
                tampered,
                self.identity,
                self.keys,
                43200,
                self.root / "tampered-progress.jsonl",
            )

    def test_interrupted_pending_attempt_is_charged_once_and_not_rerun(self) -> None:
        state = _new_state(self.identity)
        record_session(state)
        state["pending"] = {"key": self.keys[0], "reserved_seconds": 600.0}
        recovered = _recover_pending(state, self.progress, self.package)
        self.assertTrue(recovered)
        self.assertIsNone(state["pending"])
        self.assertEqual(state["consumed_wall_clock_seconds"], 600.0)
        self.assertEqual(state["interrupted_attempts"], 1)
        self.assertEqual(state["completed"][0]["key"], self.keys[0])
        self.assertEqual(state["completed"][0]["attempt"]["status"], "timeout")

        self.assertFalse(_recover_pending(state, self.progress, self.package))
        self.assertEqual(len(state["completed"]), 1)
        self.assertEqual(state["consumed_wall_clock_seconds"], 600.0)


if __name__ == "__main__":
    unittest.main()

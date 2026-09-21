from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import support  # noqa: F401
from arc_support import make_arc_source, make_model_source, make_runtime_wheels, write_outbound_binding

from irisx.arc_agi2 import prepare_trial
from irisx.kaggle import (
    build_outbound_package,
    outbound_manifest_digest,
    verify_benchmark_result_package,
    verify_outbound_package,
)
from irisx.kaggle_runner_v5 import (
    BENCHMARK_INVOCATION_LIMIT,
    BENCHMARK_RESULT_KIND,
    CHECKPOINT_POLICY,
    _load_checkpoint,
    _new_state,
    _persist_checkpoint,
    _recover_pending,
    _identity,
    _tasks,
    _validate_state,
    _write_result,
)
from irisx.transport import TRIAL_LIMITS, verify_zip


ROOT = Path(__file__).resolve().parents[1]


def identity() -> dict:
    ref = {
        "kind": "irisx/candidate-configuration",
        "artifact_id": "configuration",
        "version": "1.0.0",
        "content_digest": "sha256:" + "a" * 64,
    }
    return {
        "bundle_id": "run-003",
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
            "configuration": "baseline" if sequence < 2 else "candidate",
            "case_id": "case-001",
            "test_index": 0,
            "attempt_index": sequence % 2,
        }
        for sequence in range(BENCHMARK_INVOCATION_LIMIT)
    ]


def attempt(index: int) -> dict:
    raw = json.dumps([[index]])
    import hashlib

    return {
        "attempt_index": index % 2,
        "status": "ok",
        "grid": [[index]],
        "raw_output": raw,
        "raw_output_digest": "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "raw_output_truncated": False,
        "seed": index,
        "input_token_count": 10,
        "generated_token_count": 4,
        "eos_token_observed": True,
        "error": None,
    }


def session() -> dict:
    return {
        "session_index": 0,
        "hardware": {"gpu_count": 1, "gpu_model": "NVIDIA RTX PRO 6000", "gpu_memory_mib": 98304},
        "software": {
            "python": "3.12.13",
            "torch": "2.10.0+cu128",
            "transformers": "5.8.1",
            "cuda": "12.8",
            "cudnn": "91002",
        },
        "model_load_seconds": 3.0,
        "model": {"class": "Qwen3_5ForConditionalGeneration", "dtype": "torch.bfloat16", "parameter_count": 27_000_000_000},
    }


class KaggleBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.checkpoint = self.root / "checkpoint-package.zip"
        self.progress = self.root / "progress.jsonl"
        self.progress.write_bytes(b"")
        self.identity = identity()
        self.keys = keys()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def complete_state(self) -> dict:
        state = _new_state(self.identity)
        state["session_count"] = 1
        state["sessions"] = [session()]
        for sequence, key in enumerate(self.keys):
            state["completed"].append(
                {
                    "key": key,
                    "attempt": attempt(sequence),
                    "elapsed_seconds": 1000.0 + sequence,
                    "started_at_utc": f"2026-09-22T00:0{sequence}:00Z",
                    "finished_at_utc": f"2026-09-22T00:0{sequence}:01Z",
                }
            )
        state["consumed_wall_clock_seconds"] = 4010.0
        return state

    def test_policy_has_no_runner_time_limit_but_keeps_four_invocations(self) -> None:
        self.assertEqual(CHECKPOINT_POLICY["invocation_limit"], 4)
        self.assertIsNone(CHECKPOINT_POLICY["invocation_time_limit_seconds"])
        self.assertIsNone(CHECKPOINT_POLICY["cumulative_time_limit_seconds"])
        self.assertFalse(CHECKPOINT_POLICY["provider_session_limit_controlled"])

    def test_checkpoint_round_trip_preserves_raw_generation_and_runtime_details(self) -> None:
        state = self.complete_state()
        _persist_checkpoint(self.checkpoint, self.progress, state)
        loaded = _load_checkpoint(
            self.checkpoint,
            self.identity,
            self.keys,
            self.root / "loaded-progress.jsonl",
        )
        self.assertEqual(loaded, state)
        self.assertEqual(loaded["completed"][3]["attempt"]["raw_output"], "[[3]]")

        changed = copy.deepcopy(state)
        changed["completed"][0]["attempt"]["raw_output"] = "substituted"
        with self.assertRaisesRegex(RuntimeError, "digest"):
            _validate_state(changed, self.identity, self.keys)

    def test_interrupted_invocation_is_retried_instead_of_converted_to_timeout(self) -> None:
        state = _new_state(self.identity)
        state["session_count"] = 1
        state["sessions"] = [session()]
        state["pending"] = {"key": self.keys[0], "started_at_utc": "2026-09-22T00:00:00Z"}
        self.assertTrue(_recover_pending(state, self.progress, self.checkpoint))
        self.assertIsNone(state["pending"])
        self.assertEqual(state["completed"], [])
        self.assertEqual(state["interrupted_attempts"], 1)
        self.assertIn(b'"event":"invocation_interrupted"', self.progress.read_bytes())

    def test_result_zip_contains_four_raw_outputs_and_bound_evidence(self) -> None:
        state = self.complete_state()
        progress_events = []
        for sequence, record in enumerate(state["completed"]):
            progress_events.append(
                {
                    "event": "invocation_complete",
                    "sequence": sequence,
                    "key": record["key"],
                    "status": record["attempt"]["status"],
                    "elapsed_seconds": record["elapsed_seconds"],
                    "consumed_wall_clock_seconds": state["consumed_wall_clock_seconds"],
                }
            )
        progress_events.append(
            {
                "event": "benchmark_complete",
                "completed_invocations": 4,
                "required_invocations": 4,
                "consumed_wall_clock_seconds": state["consumed_wall_clock_seconds"],
            }
        )
        self.progress.write_bytes(
            b"".join(
                (json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
                for event in progress_events
            )
        )
        output = self.root / "result.zip"
        binding = {
            **self.identity,
            "run_id": "run-003",
            "model_dataset": {"owner": "owner", "slug": "model", "version": 1, "private": True, "immutable": True},
        }
        observations = {
            "format": "irisx/arc-agi-2-four-invocation-benchmark-observations",
            "format_version": "1.0",
        }
        _write_result(output, binding, self.identity, state, observations, self.progress)
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            result = json.loads(archive.read("benchmark/result.json"))
        self.assertEqual(manifest["package_kind"], BENCHMARK_RESULT_KIND)
        self.assertEqual(len([name for name in names if name.startswith("outputs/")]), 4)
        self.assertEqual(result["completed_invocations"], 4)
        self.assertNotIn("timeout", output.read_bytes().decode("latin-1"))


class KaggleBenchmarkPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source = self.root / "source"
        profile = make_arc_source(source)
        self.trial = self.root / "trial"
        prepare_trial(source, self.trial, profile=profile)
        model_source = make_model_source(self.root)
        runtime_wheels = make_runtime_wheels(self.root)
        binding = write_outbound_binding(self.root / "v5", bundle_id="run-003")
        self.outbound = self.root / "outbound/run-003/trial-input.zip"
        build_outbound_package(
            self.trial,
            model_source,
            binding,
            runtime_wheels,
            self.outbound,
            repository_root=ROOT,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_offline_verifier_binds_result_to_run_003_and_four_raw_outputs(self) -> None:
        outbound_manifest, _ = verify_outbound_package(self.outbound)
        _, outbound, _ = verify_zip(self.outbound, limits=TRIAL_LIMITS)
        run = json.loads(outbound["bindings/run.json"])
        benchmark_identity = _identity(run, outbound_manifest_digest(outbound_manifest))
        tasks = _tasks(
            json.loads(outbound["cases/solver-cases.json"]),
            json.loads(outbound["configurations/baseline.json"]),
            json.loads(outbound["configurations/candidate.json"]),
            json.loads(outbound["components/baseline-prompts.json"]),
            json.loads(outbound["components/candidate-prompts.json"]),
        )[:BENCHMARK_INVOCATION_LIMIT]
        state = _new_state(benchmark_identity)
        runtime_session = session()
        runtime_session["software"].update(
            {
                "python": "3.11.9",
                "torch": "2.8.0",
                "transformers": "5.8.1",
            }
        )
        state["session_count"] = 1
        state["sessions"] = [runtime_session]
        events = [
            {
                "event": "session_started",
                "session_index": 0,
                "resume": False,
                "completed_invocations": 0,
                "consumed_wall_clock_seconds": 0.0,
            }
        ]
        for sequence, task in enumerate(tasks):
            key = task["key"]
            item = attempt(sequence)
            item["attempt_index"] = key["attempt_index"]
            record = {
                "key": key,
                "attempt": item,
                "elapsed_seconds": 100.0 + sequence,
                "started_at_utc": f"2026-09-22T00:0{sequence}:00Z",
                "finished_at_utc": f"2026-09-22T00:0{sequence}:01Z",
            }
            state["completed"].append(record)
            events.extend(
                [
                    {
                        "event": "invocation_started",
                        "sequence": sequence,
                        "key": key,
                        "time_limit_seconds": None,
                        "max_new_tokens": 32768,
                        "started_at_utc": record["started_at_utc"],
                    },
                    {
                        "event": "invocation_complete",
                        "sequence": sequence,
                        "key": key,
                        "status": item["status"],
                        "elapsed_seconds": record["elapsed_seconds"],
                        "consumed_wall_clock_seconds": 406.0,
                    },
                ]
            )
        state["consumed_wall_clock_seconds"] = 406.0
        events.append(
            {
                "event": "benchmark_complete",
                "completed_invocations": 4,
                "required_invocations": 4,
                "consumed_wall_clock_seconds": 406.0,
            }
        )
        progress = self.root / "progress.jsonl"
        progress.write_bytes(
            b"".join(
                (json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
                for event in events
            )
        )
        observations = {
            "format": "irisx/arc-agi-2-four-invocation-benchmark-observations",
            "format_version": "1.0",
            "hardware": runtime_session["hardware"],
            "software": runtime_session["software"],
            "model": runtime_session["model"],
            "internet_disabled": True,
            "credentials_present": False,
            "network_calls": 0,
            "provider_calls": 0,
            "external_paid_cost_usd": 0,
            "evaluation_leaks": 0,
            "identity_binding_failures": 0,
            "recorded_wall_clock_seconds": 406.0,
            "wall_clock_coverage": "completed-session-time; interrupted session tails are not recoverable",
            "gpu_seconds_state": "unknown",
            "gpu_seconds": None,
            "time_limit_policy": {
                "invocation_time_limit_seconds": None,
                "cumulative_time_limit_seconds": None,
                "provider_session_limit_controlled": False,
            },
            "generation": {
                "decoding": {"do_sample": True, "temperature": 0.2, "top_p": 0.95},
                "max_new_tokens": 32768,
                "max_response_bytes_recorded": 262144,
            },
            "seed_policy": "sha256(configuration-ref,case-id,test-index,attempt-index) reduced to uint32",
            "attempts_per_test_input": 2,
            "stop_conditions_triggered": [],
            "checkpoint": {
                "format": "irisx/arc-agi-2-checkpoint",
                "format_version": "2.0",
                "resume_count": 0,
                "session_count": 1,
                "interrupted_attempts": 0,
                "completed_invocations": 4,
                "required_invocations": 4,
                "cumulative_wall_clock_seconds": 406.0,
                "sessions": [runtime_session],
            },
        }
        result = self.root / "result.zip"
        _write_result(result, run, benchmark_identity, state, observations, progress)
        manifest, contents, digest = verify_benchmark_result_package(result, self.outbound)
        self.assertEqual(manifest["package_id"], "run-003")
        self.assertEqual(len([path for path in contents if path.startswith("outputs/")]), 4)
        self.assertTrue(digest.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import support  # noqa: F401

from irisx import arc_trial_002 as trial002
from irisx.errors import ValidationError
from irisx.kaggle_runner_trial002 import invert_grid, transform_grid, validate_runtime_hardware


ROOT = Path(__file__).resolve().parents[1]


def grid(value: int) -> list[list[int]]:
    return [[value]]


def generation(ordinal: int | None = None, raw: str | None = None) -> dict:
    return {
        "invocation_ordinal": ordinal,
        "raw_completion": raw,
        "raw_completion_bytes": len(raw.encode("utf-8")) if raw is not None else None,
        "raw_completion_truncated": False,
        "parse_state": "valid_grid" if raw is not None else "not_available",
        "stop_reason": "eos_token" if raw is not None else "not_available",
    }


def prediction(task_id: str, status: str, attempts=None, *, ordinal: int | None = None) -> dict:
    attempts = [] if attempts is None else attempts
    return {
        "job_key": f"{task_id}:0",
        "task_id": task_id,
        "test_index": 0,
        "status": status,
        "attempts": attempts,
        "valid_model_output": bool(attempts),
        "generated_candidate_count": len(attempts),
        "failure": None if attempts else status,
        "timing": {"ttft_seconds": "unknown"},
        "tokens": {"input": 1, "generated": len(attempts)},
        "generation": generation(ordinal, "1" if attempts else None),
        "gpu_peak_memory_mib": None,
    }


def run_and_solver(count: int = 4) -> tuple[dict, dict]:
    cases = [
        {
            "task_id": chr(ord("a") + index),
            "train": [{"input": grid(index), "output": grid(index + 1)}],
            "test": [{"input": grid(index + 2)}],
        }
        for index in range(count)
    ]
    solver = {
        "format": "irisx/arc-agi-2-trial-002-solver-cases",
        "format_version": "1.0",
        "trial_id": trial002.TRIAL_ID,
        "split": "training",
        "cases": cases,
    }
    configuration = trial002._run_configuration()
    identity = {
        "trial_id": trial002.TRIAL_ID,
        "run_id": trial002.RUN_ID,
        "configuration": configuration,
        "configuration_digest": trial002.digest_value(configuration),
    }
    run = {**identity, "run_identity_digest": trial002.digest_value(identity)}
    return run, solver


class Trial002SelectionAndScoringTests(unittest.TestCase):
    def test_smoke_selection_is_answer_blind(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(8):
                task = {
                    "train": [{"input": [[index % 10]], "output": [[(index + 1) % 10]]}],
                    "test": [{"input": [[(index + 2) % 10]], "output": [[(index + 3) % 10]]}],
                }
                (root / f"{index:08x}.json").write_text(json.dumps(task), encoding="utf-8")
            before = trial002.select_smoke_tasks(root)
            for path in root.glob("*.json"):
                task = json.loads(path.read_text(encoding="utf-8"))
                task["train"][0]["output"] = [[9, 9], [9, 9]]
                task["test"][0]["output"] = [[8, 8], [8, 8]]
                path.write_text(json.dumps(task), encoding="utf-8")
            self.assertEqual(before, trial002.select_smoke_tasks(root))

    def test_grid_parser_and_retained_nvarc_transform_round_trip(self) -> None:
        original = [[0, 1, 2], [3, 4, 5]]
        permutation = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
        for view in ("identity", "rot90", "rot180", "rot270", "transpose"):
            self.assertEqual(original, invert_grid(transform_grid(original, view, permutation), view, permutation))
        self.assertEqual([[1, 2], [3, 4]], trial002.parse_grid_text("answer:\n12\n34\n\nextra"))
        self.assertIsNone(trial002.parse_grid_text("not a grid"))

    def test_pass_at_two_metric_still_accepts_one_or_two_predictions(self) -> None:
        truth = {"cases": [{"task_id": "a", "test": [{"output": grid(1)}, {"output": grid(2)}]}]}
        predictions = {"records": [{"job_key": "a:0", "attempts": [grid(9), grid(1)]}, {"job_key": "a:1", "attempts": [grid(8)]}]}
        score = trial002.score_predictions(truth, predictions)
        self.assertEqual(1, score["passed_test_outputs"])
        self.assertEqual(2, score["total_test_outputs"])


class Trial002CompetitionMountTests(unittest.TestCase):
    def test_real_challenge_projection_is_bound_and_solution_free(self) -> None:
        run, solver = run_and_solver()
        challenge = {
            case["task_id"]: {"train": case["train"], "test": [*case["test"], {"input": grid(9)}]}
            for case in solver["cases"]
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / trial002.COMPETITION_CHALLENGE_FILENAME
            path.write_text(json.dumps(challenge), encoding="utf-8")
            run["source"] = {"competition_challenge_digest": trial002.digest_path(path)}
            evidence = trial002.validate_competition_mount(path, run, solver)
            self.assertEqual(4, len(evidence["selected_task_ids"]))
            self.assertFalse(evidence["solutions_opened"])
            challenge.pop("d")
            path.write_text(json.dumps(challenge), encoding="utf-8")
            run["source"]["competition_challenge_digest"] = trial002.digest_path(path)
            with self.assertRaisesRegex(ValidationError, "absent"):
                trial002.validate_competition_mount(path, run, solver)

    def test_competition_digest_substitution_is_rejected(self) -> None:
        run, solver = run_and_solver()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / trial002.COMPETITION_CHALLENGE_FILENAME
            path.write_text("{}", encoding="utf-8")
            run["source"] = {"competition_challenge_digest": "sha256:" + "0" * 64}
            with self.assertRaisesRegex(ValidationError, "substituted"):
                trial002.validate_competition_mount(path, run, solver)


class Trial002InvocationCheckpointTests(unittest.TestCase):
    def test_exactly_four_global_invocations_and_no_fifth_on_resume(self) -> None:
        run, solver = run_and_solver(count=5)
        checkpoint = trial002.new_checkpoint(run, solver)
        for rank, task_id in enumerate(("a", "b", "c", "d")):
            ordinal = trial002.start_generation_invocation(checkpoint, f"{task_id}:0", rank, run, solver)
            self.assertEqual(rank + 1, ordinal)
        with self.assertRaisesRegex(ValidationError, "quota exhausted"):
            trial002.start_generation_invocation(checkpoint, "e:0", 0, run, solver)
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            trial002.start_generation_invocation(checkpoint, "a:0", 0, run, solver)

    def test_invocation_terminal_record_binding_and_duplicate_rejection(self) -> None:
        run, solver = run_and_solver()
        checkpoint = trial002.new_checkpoint(run, solver)
        ordinal = trial002.start_generation_invocation(checkpoint, "a:0", 0, run, solver)
        trial002.finish_generation_invocation(checkpoint, "a:0", "completed", run, solver)
        record = prediction("a", "valid", [grid(1)], ordinal=ordinal)
        trial002.record_terminal(checkpoint, record, run, solver)
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            trial002.record_terminal(checkpoint, record, run, solver)
        wrong = copy.deepcopy(checkpoint)
        wrong["completed"]["a:0"]["generation"]["invocation_ordinal"] = 2
        with self.assertRaisesRegex(ValidationError, "disagrees"):
            trial002.validate_checkpoint(wrong, run, solver)

    def test_failure_without_generate_does_not_invent_invocation(self) -> None:
        run, solver = run_and_solver()
        checkpoint = trial002.new_checkpoint(run, solver)
        trial002.record_terminal(checkpoint, prediction("a", "worker_crash"), run, solver)
        self.assertEqual({}, checkpoint["generation_invocations"])

    def test_resume_preserves_cumulative_budget_and_canonical_bytes(self) -> None:
        run, solver = run_and_solver()
        checkpoint = trial002.new_checkpoint(run, solver)
        checkpoint["sessions"].append({"session_index": 0, "started_utc": "2026-09-22T00:00:00Z", "hardware": {"gpus": []}, "charged_seconds": 125.0})
        checkpoint["cumulative_charged_seconds"] = 125.0
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint.json"
            trial002.atomically_write_json(path, checkpoint)
            loaded = trial002.load_checkpoint(path, run, solver)
        self.assertEqual(125.0, loaded["cumulative_charged_seconds"])
        reset = copy.deepcopy(loaded)
        reset["cumulative_charged_seconds"] = 0.0
        with self.assertRaisesRegex(ValidationError, "cumulative charge"):
            trial002.validate_checkpoint(reset, run, solver)


class Trial002KaggleStagingTests(unittest.TestCase):
    def test_kernel_staging_binds_competition_gpu_dataset_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "kernel"
            metadata = trial002.stage_kaggle_kernel(
                ROOT / "trials" / "arc-agi-2-baseline",
                output,
                expected_dataset_ref="danielwuu/irisx-arc-agi-2-trial-002-smoke-001",
                outbound_digest="sha256:" + "a" * 64,
            )
            self.assertEqual([trial002.COMPETITION_SLUG], metadata["competition_sources"])
            self.assertEqual(trial002.KAGGLE_MACHINE_SHAPE, metadata["machine_shape"])
            notebook = (output / metadata["code_file"]).read_text(encoding="utf-8")
            self.assertIn("a" * 64, notebook)
            self.assertNotIn("__IRISX_", notebook)

    def test_kernel_staging_rejects_missing_competition_and_ignored_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "kernel"
            trial002.stage_kaggle_kernel(
                ROOT / "trials" / "arc-agi-2-baseline",
                output,
                expected_dataset_ref="danielwuu/irisx-arc-agi-2-trial-002-smoke-001",
                outbound_digest="b" * 64,
            )
            metadata_path = output / "kernel-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["competition_sources"] = []
            metadata["accelerator"] = "L4 x4"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "ignored fields"):
                trial002.validate_kernel_staging(output, expected_dataset_ref="danielwuu/irisx-arc-agi-2-trial-002-smoke-001")

    def test_bad_outbound_digest_and_stale_runtime_wheel_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValidationError, "digest binding"):
                trial002.stage_kaggle_kernel(
                    ROOT / "trials" / "arc-agi-2-baseline",
                    root / "kernel",
                    expected_dataset_ref="danielwuu/irisx-arc-agi-2-trial-002-smoke-001",
                    outbound_digest="not-a-digest",
                )
            wheel_root = root / "wheels"
            wheel_root.mkdir()
            wheel = wheel_root / "irisx-0.2.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("irisx/kaggle_runner_trial002.py", b"stale")
                archive.writestr("irisx/arc_trial_002.py", b"stale")
            with self.assertRaisesRegex(ValidationError, "source differ"):
                trial002.validate_runtime_wheel_sources(wheel_root, runner=b"new", core=b"new")

    def test_runner_source_has_one_generate_site_and_no_adaptation(self) -> None:
        source = (ROOT / "src" / "irisx" / "kaggle_runner_trial002.py").read_text(encoding="utf-8")
        self.assertEqual(1, source.count("model.generate("))
        self.assertNotIn("_adapt_model", source)
        self.assertIn("num_return_sequences=1", source)
        self.assertIn("generation_invocation_started", source)


class Trial002HardwareAndImportTests(unittest.TestCase):
    def test_progress_log_accepts_bound_worker_stage_records_only(self) -> None:
        trial002.validate_progress_log(
            b'{"event":"worker_started"}\n'
            b'{"type":"stage","rank":0,"task_id":"2dd70a9a","stage":"model_load"}\n'
            b'{"type":"stage","rank":3,"task_id":"d968ffd4","stage":"single_generate"}\n',
            {"2dd70a9a", "d968ffd4"},
        )
        for malformed in (
            b'{"type":"stage","rank":4,"task_id":"2dd70a9a","stage":"model_load"}\n',
            b'{"type":"stage","rank":0,"task_id":"unknown","stage":"model_load"}\n',
            b'{"type":"stage","rank":0,"task_id":"2dd70a9a","stage":"training"}\n',
            b'{"type":"unknown"}\n',
        ):
            with self.assertRaisesRegex(ValidationError, "malformed"):
                trial002.validate_progress_log(malformed, {"2dd70a9a", "d968ffd4"})

    def test_gpu_count_model_and_smi_mismatch_fail_fast(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "exactly four"):
            validate_runtime_hardware({"torch_cuda_device_count": 2, "gpus": [], "nvidia_smi_exit_code": 0, "nvidia_smi_rows": []})
        wrong = {
            "torch_cuda_device_count": 4,
            "gpus": [{"name": "Tesla T4", "memory_mib": 23000}] * 4,
            "nvidia_smi_exit_code": 0,
            "nvidia_smi_rows": ["gpu"] * 4,
        }
        with self.assertRaisesRegex(RuntimeError, "four L4"):
            validate_runtime_hardware(wrong)

    def test_runner_import_does_not_load_gpu_or_model_libraries(self) -> None:
        script = (
            "import sys; import irisx.kaggle_runner_trial002; "
            "assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules; assert 'peft' not in sys.modules"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False, env=environment)
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from irisx import arc_prompt_pilot as pilot
from irisx.errors import ValidationError
from irisx.canonical import canonical_bytes, digest_value, write_json
from irisx.kaggle_runner_prompt_pilot import canonical_ready_evidence, validate_runtime_hardware
from irisx.transport import TRIAL_LIMITS, write_zip


def _task(index: int) -> dict:
    # Leading 0,1 fixes the color-normalization mapping; remaining ten bits
    # provide enough distinct visible projections for a 512-task split test.
    bits = [0, 1] + [int(value) for value in f"{index:010b}"]
    grid = [bits[:4], bits[4:8], bits[8:12]]
    output = [row[::-1] for row in grid]
    return {"train": [{"input": grid, "output": output}], "test": [{"input": output, "output": grid}]}


class PromptPilotTests(unittest.TestCase):
    def test_search_kernel_title_resolves_to_its_fixed_slug(self) -> None:
        self.assertEqual(
            pilot.KAGGLE_SEARCH_KERNEL_REF.split("/", 1)[1],
            pilot.KAGGLE_SEARCH_KERNEL_TITLE.lower().replace(" ", "-"),
        )

    def test_split_is_deterministic_balanced_and_excludes_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            training = Path(temporary)
            for index in range(540):
                task_id = f"{index:08x}"
                (training / f"{task_id}.json").write_text(json.dumps(_task(index)), encoding="utf-8")
            for offset, task_id in enumerate(pilot.SMOKE_TASK_IDS, start=600):
                (training / f"{task_id}.json").write_text(json.dumps(_task(offset)), encoding="utf-8")
            first = pilot.freeze_split(training)
            second = pilot.freeze_split(training)
            self.assertEqual(first, second)
            self.assertEqual({"optimization-train": 256, "selection-dev": 128, "locked-holdout": 128}, first["counts"])
            selected = {item["task_id"] for item in first["records"]}
            self.assertFalse(selected.intersection(pilot.SMOKE_TASK_IDS))
            self.assertEqual(512, len(selected))

    def test_b0_b1_render_and_token_ids_are_identical(self) -> None:
        case = {"task_id": "00000001", "train": _task(1)["train"], "test": [{"input": _task(1)["test"][0]["input"]}]}

        class FakeTokenizer:
            def apply_chat_template(self, messages, **kwargs):
                return messages[0]["content"] + "<assistant>"

            def __call__(self, text, **kwargs):
                return {"input_ids": list(text.encode("utf-8"))}

        evidence = pilot.assert_render_parity([case], FakeTokenizer())
        self.assertTrue(evidence["messages_equal"])
        self.assertTrue(evidence["token_ids_equal"])

    def test_dynamic_scheduler_initially_uses_all_four_and_reuses_free_worker(self) -> None:
        state = pilot.DispatchState.from_jobs(f"job-{index}" for index in range(8))
        first = [state.dispatch(rank, 100.0) for rank in range(4)]
        self.assertEqual(["job-0", "job-1", "job-2", "job-3"], first)
        state.finish(2, "job-2", "valid")
        self.assertEqual("job-4", state.dispatch(2, 120.0))
        self.assertEqual({0, 1, 2, 3}, set(state.active))

    def test_scheduler_rejects_duplicate_terminal_and_reports_timeout(self) -> None:
        state = pilot.DispatchState.from_jobs(["a", "b"])
        self.assertEqual("a", state.dispatch(0, 10.0))
        self.assertEqual([(0, "a")], state.expired(10.0))
        state.finish(0, "a", "timeout")
        with self.assertRaises(ValidationError):
            state.finish(0, "a", "timeout")

    def test_checkpoint_preserves_full_denominator_and_invocation_quota(self) -> None:
        cases = [{"task_id": f"{index:08x}", "group": "optimization-train", "train": [], "test": [{"input": [[0]]}]} for index in range(pilot.BASELINE_JOB_COUNT)]
        solver = {"cases": cases}
        run = {"run_identity_digest": "sha256:" + "0" * 64}
        checkpoint = pilot.new_checkpoint(run, solver)
        pilot.validate_checkpoint(checkpoint, run, solver)
        self.assertEqual(384, len(checkpoint["expected_jobs"]))
        checkpoint["generation_invocations"] = {f"x{index}": {} for index in range(385)}
        with self.assertRaises(ValidationError):
            pilot.validate_checkpoint(checkpoint, run, solver)

    def test_hardware_gate_requires_four_distinct_l4s(self) -> None:
        hardware = {
            "torch_cuda_device_count": 4,
            "gpus": [{"name": "NVIDIA L4", "memory_mib": 22563, "uuid": f"GPU-{index}"} for index in range(4)],
            "nvidia_smi_exit_code": 0,
            "nvidia_smi_rows": [f"{index}, NVIDIA L4, 23034, GPU-{index}, bus" for index in range(4)],
        }
        validate_runtime_hardware(hardware)
        hardware["gpus"][3]["uuid"] = "GPU-2"
        with self.assertRaises(RuntimeError):
            validate_runtime_hardware(hardware)

    def test_runtime_observations_stringify_worker_rank_keys(self) -> None:
        ready = {
            rank: {"event": "model_ready", "rank": rank, "gpu_uuid": f"GPU-{rank}"}
            for rank in range(4)
        }
        evidence = canonical_ready_evidence(ready)
        self.assertEqual(["0", "1", "2", "3"], list(evidence))
        self.assertEqual(0, evidence["0"]["rank"])
        canonical_bytes({"model_ready": evidence}, newline=True)

    def test_result_zip_accepts_canonical_worker_evidence(self) -> None:
        cases = [
            {"task_id": f"{index:08x}", "group": "optimization-train", "train": [], "test": [{"input": [[0]]}]}
            for index in range(pilot.BASELINE_JOB_COUNT)
        ]
        solver = {"cases": cases}
        run = {"run_identity_digest": "sha256:" + "0" * 64}
        checkpoint = pilot.new_checkpoint(run, solver)
        checkpoint["completed"] = {
            job_key: {"job_key": job_key, "status": "valid"}
            for job_key in checkpoint["expected_jobs"]
        }
        checkpoint["complete"] = True
        ready = {
            rank: {"event": "model_ready", "rank": rank, "gpu_uuid": f"GPU-{rank}"}
            for rank in range(4)
        }
        observations = {"model_ready": canonical_ready_evidence(ready)}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.zip"
            digest = pilot.build_result_package(output, run, solver, checkpoint, observations, b"")
            self.assertTrue(digest.startswith("sha256:"))
            with zipfile.ZipFile(output) as archive:
                returned = json.loads(archive.read("observations/execution.json"))
            self.assertEqual(["0", "1", "2", "3"], list(returned["model_ready"]))

    def test_scorer_keeps_invalid_outputs_in_the_denominator(self) -> None:
        truth = [
            {"task_id": "a", "group": "optimization-train", "test_index": 0, "output": [[1]]},
            {"task_id": "b", "group": "optimization-train", "test_index": 0, "output": [[2]]},
            {"task_id": "c", "group": "selection-dev", "test_index": 0, "output": [[3]]},
        ]
        records = [
            {"job_key": "a:0", "task_id": "a", "group": "optimization-train", "test_index": 0, "status": "valid", "attempts": [[[1]]]},
            {"job_key": "b:0", "task_id": "b", "group": "optimization-train", "test_index": 0, "status": "invalid", "attempts": []},
            {"job_key": "c:0", "task_id": "c", "group": "selection-dev", "test_index": 0, "status": "valid", "attempts": [[[0]]]},
        ]

        score = pilot.score_prediction_records(records, truth)

        self.assertEqual({"correct": 1, "denominator": 2, "accuracy": 0.5, "terminal_status_counts": {"invalid": 1, "valid": 1}}, score["groups"]["optimization-train"])
        self.assertEqual(0, score["groups"]["selection-dev"]["correct"])
        self.assertEqual(3, score["overall"]["denominator"])

    def test_scorer_rejects_a_changed_denominator(self) -> None:
        truth = [{"task_id": "a", "group": "optimization-train", "test_index": 0, "output": [[1]]}]
        with self.assertRaises(ValidationError):
            pilot.score_prediction_records([], truth)

    def test_complete_checkpoint_can_be_recovered_without_new_generation(self) -> None:
        cases = [
            {"task_id": f"{index:08x}", "group": "optimization-train" if index < pilot.TRAIN_COUNT else "selection-dev", "train": [], "test": [{"input": [[0]]}]}
            for index in range(pilot.BASELINE_JOB_COUNT)
        ]
        solver = {
            "format": "irisx/arc-agi-2-prompt-pilot-solver-cases",
            "format_version": "1.0",
            "trial_id": pilot.TRIAL_ID,
            "run_id": pilot.RUN_ID,
            "instruction": pilot.BASE_INSTRUCTION,
            "cases": cases,
        }
        configuration = pilot._configuration()
        run = {
            "trial_id": pilot.TRIAL_ID,
            "run_id": pilot.RUN_ID,
            "source": {"competition_slug": pilot.COMPETITION_SLUG, "competition_challenge_digest": f"sha256:{pilot.COMPETITION_CHALLENGE_SHA256}", "solutions_opened_in_runtime": False},
            "model": {"repository": pilot.MODEL_REPOSITORY, "revision": pilot.MODEL_REVISION, "license": pilot.MODEL_LICENSE},
            "prompt": {"candidate": "B1", "instruction": pilot.BASE_INSTRUCTION, "instruction_digest": digest_value(pilot.BASE_INSTRUCTION)},
            "split_digest": pilot.BASELINE_SPLIT_DIGEST,
            "solver_cases_digest": digest_value(solver),
            "configuration": configuration,
            "configuration_digest": digest_value(configuration),
        }
        run["run_identity_digest"] = digest_value(run)
        checkpoint = pilot.new_checkpoint(run, solver)
        hardware = {
            "python": "3.12.13",
            "torch": "2.10.0+cu128",
            "cuda": "12.8",
            "cudnn": "91002",
            "torch_cuda_device_count": 4,
            "gpus": [{"index": rank, "name": "NVIDIA L4", "memory_mib": 22563, "uuid": f"GPU-{rank}"} for rank in range(4)],
            "nvidia_smi_exit_code": 0,
            "nvidia_smi_rows": [f"{rank}, NVIDIA L4, 23034, GPU-{rank}, bus" for rank in range(4)],
        }
        checkpoint["sessions"] = [{"session_index": 0, "started_utc": "2026-09-22T00:00:00Z", "ended_utc": "2026-09-22T00:10:00Z", "wall_seconds": 600.0, "hardware": hardware}]
        events = [
            {"event": "runtime_preflight_started", "run_id": pilot.RUN_ID},
            {"event": "runtime_hardware_observed", "hardware": hardware},
            {"event": "competition_mount_validated", "competition_slug": pilot.COMPETITION_SLUG, "challenge_digest": f"sha256:{pilot.COMPETITION_CHALLENGE_SHA256}", "available_task_count": 1000, "selected_job_count": 384, "selected_test_index": 0, "solutions_opened": False},
        ]
        for rank in range(4):
            ready = {"event": "model_ready", "rank": rank, "gpu_uuid": f"GPU-{rank}", "model_revision": pilot.MODEL_REVISION}
            checkpoint["model_ready"][str(rank)] = ready
            events.extend((
                {"event": "worker_process_started", "rank": rank},
                {"event": "model_load_started", "rank": rank, "gpu_uuid": f"GPU-{rank}"},
                {**ready, "elapsed_seconds": 10.0},
            ))
        events.append({"event": "all_workers_ready", "ready_ranks": [0, 1, 2, 3]})
        for index, job_key in enumerate(checkpoint["expected_jobs"], start=1):
            rank = (index - 1) % 4
            status = "valid" if index <= 380 else "invalid"
            checkpoint["generation_invocations"][job_key] = {"ordinal": index, "worker_rank": rank, "status": "completed"}
            checkpoint["completed"][job_key] = {"job_key": job_key, "status": status, "worker_rank": rank, "gpu_uuid": f"GPU-{rank}", "invocation_ordinal": index, "timing": {"generation_seconds": 1.0}}
            events.extend((
                {"event": "generation_invocation_dispatched", "job_key": job_key, "invocation_ordinal": index, "rank": rank, "gpu_uuid": f"GPU-{rank}"},
                {"event": "job_started", "job_key": job_key},
                {"event": "job_terminal", "job_key": job_key, "invocation_ordinal": index, "rank": rank, "gpu_uuid": f"GPU-{rank}", "status": status},
            ))
        checkpoint["complete"] = True
        events.append({"event": "session_complete", "completed_jobs": 384, "terminal_status_counts": {"invalid": 4, "valid": 380}})
        outbound_files = {
            "bindings/run.json": canonical_bytes(run, newline=True),
            "cases/solver-cases.json": canonical_bytes(solver, newline=True),
            "runtime/dependencies.json": canonical_bytes({"transformers": "5.8.1"}, newline=True),
            "runtime/runner.py": b"runner\n",
            "runtime/core.py": b"core\n",
            "sources/model-manifest.json": canonical_bytes({}, newline=True),
            "sources/base-wheel-manifest.json": canonical_bytes({}, newline=True),
            "sources/runtime-wheel-manifest.json": canonical_bytes({}, newline=True),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outbound = root / f"{pilot.RUN_ID}.zip"
            write_zip(outbound, pilot.OUTBOUND_KIND, pilot.RUN_ID, outbound_files, {}, limits=TRIAL_LIMITS)
            write_json(root / "checkpoint.json", checkpoint)
            (root / "progress.jsonl").write_bytes(b"".join(canonical_bytes(event, newline=True) for event in events))
            report = pilot.recover_result_package(outbound, root / "checkpoint.json", root / "progress.jsonl", root / "result.zip")
            self.assertTrue(report["verified"])
            self.assertFalse(report["scored"])
            self.assertEqual(0, report["new_generation_invocations"])

    def test_import_does_not_load_torch_or_transformers(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "src/irisx/kaggle_runner_prompt_pilot.py").read_text(encoding="utf-8")
        self.assertNotIn("\nimport torch\n", source)
        self.assertNotIn("\nfrom transformers", source)

    def test_repair_uses_new_identity_and_exact_mount_candidates(self) -> None:
        self.assertEqual("prompt-pilot-baseline-002", pilot.RUN_ID)
        self.assertEqual(2, pilot.RUNTIME_DATASET_VERSION)
        self.assertTrue(pilot.KAGGLE_KERNEL_REF.endswith("prompt-pilot-baseline-002"))
        notebook_path = Path(__file__).resolve().parents[1] / "trials/arc-agi-2-prompt-pilot/repair-002/kaggle-notebook.ipynb"
        notebook = json.loads(notebook_path.read_bytes())
        source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"] if cell.get("cell_type") == "code")
        self.assertIn("/kaggle/input/datasets/danielwuu/irisx-arc-agi-2-prompt-pilot-baseline-001", source)
        self.assertIn("/kaggle/input/competitions/arc-prize-2026-arc-agi-2", source)
        self.assertIn("mount_paths_resolved", source)
        self.assertNotIn(".rglob(", source)


if __name__ == "__main__":
    unittest.main()

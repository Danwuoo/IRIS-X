from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from irisx import arc_prompt_pilot as pilot
from irisx.errors import ValidationError
from irisx.kaggle_runner_prompt_pilot import validate_runtime_hardware


def _task(index: int) -> dict:
    # Leading 0,1 fixes the color-normalization mapping; remaining ten bits
    # provide enough distinct visible projections for a 512-task split test.
    bits = [0, 1] + [int(value) for value in f"{index:010b}"]
    grid = [bits[:4], bits[4:8], bits[8:12]]
    output = [row[::-1] for row in grid]
    return {"train": [{"input": grid, "output": output}], "test": [{"input": output, "output": grid}]}


class PromptPilotTests(unittest.TestCase):
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

    def test_import_does_not_load_torch_or_transformers(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "src/irisx/kaggle_runner_prompt_pilot.py").read_text(encoding="utf-8")
        self.assertNotIn("\nimport torch\n", source)
        self.assertNotIn("\nfrom transformers", source)


if __name__ == "__main__":
    unittest.main()

"""Offline compact pilot plan, package and truth-boundary checks."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from irisx.arc_nvarc_compact_pilot import prepare, validate_plan, visible_workload
from irisx.arc_nvarc_kaggle import run as run_kaggle
from irisx.arc_nvarc_runtime import (build_outbound, build_result, finalize_interrupted,
                                     finish_task, make_binding, new_checkpoint,
                                     reserve_task, verify_result)
from irisx.canonical import digest_value
from irisx.errors import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_nvarc_compact_complete import stage  # noqa: E402


def single_worker(rank, commands, outputs, model_root, config, gpu_uuid):
    outputs.put({"type": "ready", "rank": rank, "gpu_uuid": gpu_uuid,
                 "model_load_seconds": 0.0, "model_load_peak_mib": 0})
    while True:
        command = commands.get()
        if command["type"] == "stop":
            return
        task = command["task"]
        tests = [{"test_index": index, "attempts": [], "missing_attempts": 2,
                  "status": "missing-candidate", "generation_calls_so_far": 0,
                  "verification_calls_so_far": 0, "returned_sequences": 0}
                 for index in range(len(task["test"]))]
        outputs.put({"type": "record", "rank": rank, "task_id": task["task_id"],
                     "record": {"task_id": task["task_id"], "tests": tests,
                                "status": "missing-candidate", "adaptation": {},
                                "explicit_forward_calls": 0, "peak_memory_mib": None,
                                "timing": {"task_wall_seconds": 0.0}}})


class CompactPilotTests(unittest.TestCase):
    def test_one_worker_supervisor_uses_mount_presence_without_reading_challenges(self) -> None:
        config_dir = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
        config = json.loads((config_dir / "compact-complete-001.json").read_bytes())["config"]
        workload = visible_workload(json.loads((config_dir / "compact-complete-visible.json").read_bytes()))
        digest = digest_value("synthetic-material")
        binding = make_binding(workload, run_id="synthetic-one-worker", model_digest=digest,
                               data_digest=digest, tokenizer_digest=digest,
                               runtime_digest=digest, config=config)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outbound = root / "outbound.zip"
            build_outbound(outbound, binding, workload)
            source = root / "arc-agi_training_challenges.json"
            source.write_text("mounted but deliberately not parsed")
            compact = root / "compact"
            compact.mkdir()
            (compact / "grid-vocab.json").write_text("{}")
            hardware = {"gpus": [{"uuid": "one-L4"}]}
            with mock.patch("irisx.arc_nvarc_kaggle.validate_hardware", return_value=hardware), \
                 mock.patch("irisx.arc_nvarc_kaggle.verify_model_material", return_value={}):
                run_kaggle(outbound, compact, source, root / "result.zip",
                           root / "checkpoint.json", worker_target=single_worker,
                           source_policy="mount-presence-only")
            verify_result(root / "result.zip", binding, workload)
            checkpoint = json.loads((root / "checkpoint.json").read_bytes())
            self.assertEqual(["0"], list(checkpoint["model_ready"]))
            self.assertEqual(2, len(checkpoint["completed"]))

    def test_failed_adaptation_observation_survives_truth_free_ledger(self) -> None:
        config_dir = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
        config = json.loads((config_dir / "compact-complete-001.json").read_bytes())["config"]
        workload = visible_workload(json.loads((config_dir / "compact-complete-visible.json").read_bytes()))
        digest = digest_value("synthetic-material")
        binding = make_binding(workload, run_id="synthetic-finite-failure", model_digest=digest,
                               data_digest=digest, tokenizer_digest=digest,
                               runtime_digest=digest, config=config)
        checkpoint = new_checkpoint(binding, workload)
        task_id = workload["cases"][0]["task_id"]
        reserve_task(checkpoint, binding, task_id, rank=0, at_utc="synthetic")
        tests = [{"test_index": index, "attempts": [], "missing_attempts": 2,
                  "status": "worker_crash"} for index in range(2)]
        finish_task(checkpoint, task_id, {"task_id": task_id, "tests": tests,
                                          "status": "worker_crash",
                                          "adaptation": {"status": "failed", "steps": 0,
                                                         "training_tokens": 0,
                                                         "failure_type": "ValidationError",
                                                         "gradient_groups_by_step": []},
                                          "explicit_forward_calls": 0,
                                          "peak_memory_mib": None})
        finalize_interrupted(checkpoint, workload, reason="not_executed")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_outbound(root / "outbound.zip", binding, workload)
            result = root / "result.zip"
            build_result(result, binding, workload, checkpoint,
                         {"format": "irisx/nvarc-execution", "run_id": binding["run_id"]})
            verify_result(result, binding, workload)
            self.assertEqual("failed", checkpoint["completed"][task_id]["adaptation"]["status"])

    def test_plan_and_checked_in_materials_are_bound(self) -> None:
        config = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
        summary = prepare(config / "compact-complete-001.json",
                          config / "compact-complete-visible.json",
                          config / "base-model-manifest.json",
                          config / "base-wheel-manifest.json")
        self.assertEqual((2, 4, False),
                         (summary["tasks"], summary["tests"], summary["approved"]))
        plan = json.loads((config / "compact-complete-001.json").read_bytes())
        with self.assertRaises(ValidationError):
            validate_plan({**plan, "maximum_generation_calls": 5}, approved=False)
        with self.assertRaises(ValidationError):
            validate_plan({**plan, "approved": True}, approved=True)
        visible = json.loads((config / "compact-complete-visible.json").read_bytes())
        visible["synthetic-rect-a"]["test"][0]["output"] = [[9]]
        with self.assertRaises(ValidationError):
            visible_workload(visible)

    def test_draft_kaggle_package_is_private_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            summary = stage(Path(temp) / "stage")
            kernel = Path(summary["kernel_path"])
            metadata = json.loads((kernel / "kernel-metadata.json").read_bytes())
            notebook = json.loads((kernel / "kaggle-notebook.ipynb").read_bytes())
            code = "".join(notebook["cells"][0]["source"])
            self.assertFalse(summary["approved"])
            self.assertTrue(metadata["is_private"])
            self.assertFalse(metadata["enable_internet"])
            self.assertEqual(["arc-prize-2026-arc-agi-2"], metadata["competition_sources"])
            self.assertIn("lacks exact owner authorization", code)
            self.assertIn("competition_challenges_read", code)
            self.assertIn("remove_optional_torchao_if_present", code)
            self.assertIn("finalize-timeout", code)


if __name__ == "__main__":
    unittest.main()

"""Tiny real Qwen replay of the bounded two-path ABC beam."""

import importlib.util
import unittest
from pathlib import Path

from irisx.arc_nvarc_abc_004 import ObservedTaskLocalAdapter, solve_one
from irisx.arc_nvarc_candidates import QwenCandidateBackend
from irisx.arc_nvarc_combined import read
from irisx.arc_nvarc_representation import compact_loaded_model
from irisx.arc_nvarc_upstream import source_bundle
from tools.stage_nvarc_abc_004 import PLAN

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-004-submission"


class ABCBeamStrict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [name for name in ("torch", "transformers", "peft", "safetensors", "numpy")
                   if importlib.util.find_spec(name) is None]
        if missing:
            raise unittest.SkipTest("optional ML dependencies missing: " + ", ".join(missing))

    def test_beam_and_one_step_ttt_flow_through_truth_free_generation(self):
        import torch
        from tests.test_arc_nvarc_ml import NvarcMLTests

        torch.set_num_threads(2)
        torch.manual_seed(43)
        model = NvarcMLTests()._tiny_qwen().eval()
        compact_loaded_model(model, {"symbols": [{"source_token_ids": [i]} for i in range(16)]})
        plan = read(PLAN)
        plan["limits"].update(calls_per_task=1, expansions_per_task=128,
                              verifications_per_task=2)
        adapter = ObservedTaskLocalAdapter(model, plan["adaptation"])
        backend = QwenCandidateBackend(model, task_adapter=adapter)
        backend.augmentation = backend.representation = "source-qwen"
        task = {"task_id": "tiny-public-beam", "train": [
            {"input": [[1, 2], [2, 1]], "output": [[1, 2], [2, 1]]},
            {"input": [[3, 4], [4, 3]], "output": [[3, 4], [4, 3]]}],
            "test": [{"input": [[5, 6], [6, 5]]}]}
        events = []
        with source_bundle(PACKAGE / "source-bundle", read(PLAN)["source_bundle_digest"]):
            row = solve_one(task, backend, plan, events.append)
        self.assertEqual("complete", row["status"])
        self.assertEqual(1, row["generation_calls"])
        self.assertEqual(2, row["returned_sequences"])
        self.assertLessEqual(row["generation_forwards"], 128)
        self.assertEqual(1, adapter.last_observation["steps"])
        self.assertTrue(adapter.last_observation["reset_verified"])
        self.assertEqual("public-grammar-beam-complete",
                         row["generation_observations"][0]["stop_reason"])
        self.assertFalse(row["contains_evaluator_truth"])


if __name__ == "__main__":
    unittest.main()

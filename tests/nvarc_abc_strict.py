"""Tiny real Qwen CPU replay of the ABC comparison path; never 4B inference."""

import copy
import importlib.util
from pathlib import Path
import unittest

from irisx.arc_nvarc_abc import solve_one
from irisx.arc_nvarc_candidates import QwenCandidateBackend
from irisx.arc_nvarc_representation import compact_loaded_model
from irisx.arc_nvarc_training import TaskLocalAdapter
from irisx.arc_nvarc_upstream import source_bundle
from tools.stage_nvarc_abc import PLAN
from irisx.arc_nvarc_combined import read

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-001-submission"


class ABCStrictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [name for name in ("torch", "transformers", "peft", "safetensors", "numpy")
                   if importlib.util.find_spec(name) is None]
        if missing:
            raise unittest.SkipTest("optional ML dependencies missing: " + ", ".join(missing))

    def test_tiny_real_model_three_arms_and_reset(self):
        import torch
        from peft import get_peft_model_state_dict
        from tests.test_arc_nvarc_ml import NvarcMLTests

        torch.set_num_threads(2)
        torch.manual_seed(31)
        base = NvarcMLTests()._tiny_qwen().eval()
        compact_loaded_model(base, {"symbols": [{"source_token_ids": [i]} for i in range(16)]})
        sft = copy.deepcopy(base).eval()
        with torch.no_grad():
            sft.get_input_embeddings().weight[0].add_(0.02)
        plan = read(PLAN)
        plan["limits"].update(calls_per_task=1, expansions_per_task=128,
                              verifications_per_task=2)
        task = {"task_id": "tiny-public-1", "train": [
            {"input": [[1, 2], [2, 1]], "output": [[1, 2], [2, 1]]},
            {"input": [[3, 4], [4, 3]], "output": [[3, 4], [4, 3]]}],
            "test": [{"input": [[5, 6], [6, 5]]}]}
        events = []
        with source_bundle(PACKAGE / "source-bundle", read(PLAN)["source_bundle_digest"]):
            a = QwenCandidateBackend(base)
            a.augmentation = a.representation = "source-qwen"
            row_a = solve_one(task, a, plan, events.append)
            b = QwenCandidateBackend(sft)
            b.augmentation = b.representation = "source-qwen"
            row_b = solve_one(task, b, plan, events.append)
            adapter = TaskLocalAdapter(sft, plan["adaptation"])
            initial = {key: value.detach().clone() for key, value in
                       get_peft_model_state_dict(adapter.model).items()}
            c = QwenCandidateBackend(sft, task_adapter=adapter)
            c.augmentation = c.representation = "source-qwen"
            row_c = solve_one(task, c, plan, events.append)
            self.assertEqual(1, adapter.last_observation["steps"])
            self.assertTrue(all(torch.equal(initial[key], value) for key, value in
                                get_peft_model_state_dict(adapter.model).items()))
            second = copy.deepcopy(task)
            second["task_id"] = "tiny-public-2"
            row_c2 = solve_one(second, c, plan, events.append)
            self.assertTrue(all(torch.equal(initial[key], value) for key, value in
                                get_peft_model_state_dict(adapter.model).items()))
        for row in (row_a, row_b, row_c, row_c2):
            self.assertEqual(1, row["generation_calls"])
            self.assertEqual(2, row["returned_sequences"])
            self.assertEqual(12, row["generation_forwards"])
            self.assertLessEqual(row["verification_calls"], 2)
            self.assertEqual(8 * row["verification_calls"], row["verification_forwards"])
            self.assertEqual(2, len(row["raw_sequences"]))
            self.assertEqual([x["grid"] for x in row["ranked"][:2]], row["attempts"])
            self.assertFalse(row["contains_evaluator_truth"])
        self.assertIsNone(a.adapter)
        self.assertIsNone(b.adapter)
        self.assertEqual(8, sum(e["kind"] == "generation" for e in events))


if __name__ == "__main__":
    unittest.main()

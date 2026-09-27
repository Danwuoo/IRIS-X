"""Real tiny Qwen/PEFT paired arms, one TTT, failure reset; missing deps FAIL."""

import unittest

from irisx.arc_nvarc_candidates import QwenCandidateBackend
from irisx.arc_nvarc_representation import compact_loaded_model
from irisx.arc_nvarc_training import TaskLocalAdapter
from irisx.arc_nvarc_threshold_trial import compare_thresholds


class ThresholdStrictTests(unittest.TestCase):
    def test_paired_actual_tiny_model_adapts_once_preserves_weights_queries_and_costs(self):
        import torch
        from tests.test_arc_nvarc_ml import NvarcMLTests
        torch.set_num_threads(2); torch.manual_seed(19)
        model = NvarcMLTests()._tiny_qwen().eval()
        compact_loaded_model(model, {"symbols": [{"source_token_ids": [i]} for i in range(16)]})
        class CountedAdapter(TaskLocalAdapter):
            invocations = 0
            def adapt(self, task):
                self.invocations += 1
                return super().adapt(task)
        adapter = CountedAdapter(model, {"seed":42,"rank":2,"alpha":4,"learning_rate":.00005,
            "steps":1,"max_sequence_length":128,"augmentation_count":1,"source_augmentation_seed":1,"source_qwen":True})
        original = {name: value.detach().clone() for name, value in model.named_parameters()}
        backend = QwenCandidateBackend(model, task_adapter=adapter, dfs_max_expansions=128)
        config = {"seed":2,"source_generation_seed":2,"color_repeats":2,"maximum_calls_per_task":4,
            "beams_per_call":2,"maximum_new_tokens":64,"augmentation":"source-qwen",
            "representation":"source-qwen","ranking":"source-kgmon"}
        arms = [{"id": name, "cumulative_probability_threshold": p} for name,p in
                (("control",.2),("candidate1",.1),("candidate2",.02))]
        task = {"task_id":"synthetic-root", "train":[{"input":[[1]],"output":[[2]]},
            {"input":[[3]],"output":[[4]]}],"test":[{"input":[[5]]}]}
        events = []
        result = compare_thresholds(task, backend, config, arms, call_observer=events.append)
        self.assertEqual(1, adapter.invocations)
        self.assertEqual(1, result["shared_adaptation"]["steps"])
        self.assertEqual(12, result["generation_calls"])
        root_sets = [[o["diagnostics"]["root"]["log_probs"] for o in arm["results"][0]["generation_observations"]]
                     for arm in result["arms"]]
        self.assertEqual(root_sets[0], root_sets[1]); self.assertEqual(root_sets[0], root_sets[2])
        self.assertEqual(1, len({arm["shared_adapter_digest"] for arm in result["arms"]}))
        self.assertTrue(all(arm["query_digests"] == result["arms"][0]["query_digests"] for arm in result["arms"]))
        self.assertEqual(12, sum(e["kind"] == "generation" and e["status"] == "reserved" for e in events))
        for arm in result["arms"]:
            self.assertLessEqual(arm["explicit_forwards"], 4*128+8*8)
            self.assertEqual(4, arm["generation_calls"])
        self.assertIs(backend.model, model); self.assertIs(backend.adapter, adapter)
        for name,value in model.named_parameters():
            self.assertTrue(torch.equal(original[name], value))
        # A reservation/observer failure must clean up the adapted model too.
        def fail(event):
            if event["kind"] == "generation": raise RuntimeError("injected ledger failure")
        with self.assertRaisesRegex(RuntimeError, "injected ledger failure"):
            compare_thresholds(task, backend, config, arms, call_observer=fail)
        self.assertIs(backend.model, model)
        for name,value in model.named_parameters():
            self.assertTrue(torch.equal(original[name], value))


if __name__ == "__main__":
    unittest.main()

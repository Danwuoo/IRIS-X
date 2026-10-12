"""TTT policy fixtures plus explicitly opted-in real tiny CPU neural work."""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from tools.arc_next_models import digest
from tools.arc_learning_agent_20261011.budget import DEFAULT_CAPS, WorkLedger
from tools.arc_learning_agent_20261011.data import create_split_manifest
from tools.arc_learning_agent_20261011.grid_codec import encode_grid, grid_messages
from tools.arc_learning_agent_20261011.ttt_effectiveness import select_ttt, _rank_ids
from tools.arc_learning_agent_20261011.tests.test_data import fixture_tasks
from tools.arc_learning_agent_20261011.tests.test_effectiveness import generation


def sources():
    tasks = fixture_tasks()
    tasks["c"]["train"].append({"input": [[7, 8], [2, 3]], "output": [[7, 2], [8, 3]]})
    tasks["d"]["train"].append({"input": [[9, 9, 9, 9]], "output": [[9]]})
    return tasks, create_split_manifest(tasks, fixed_splits={"train": ["a", "b"], "dev": ["c", "d"]})


class FixtureModel:
    def __init__(self, tasks):
        self.config = {"do_sample": True, "temperature": .7, "top_p": .9, "keep": True}
        self.targets = {digest(grid_messages(task["train"][:-1], task["train"][-1]["input"])):
                        (key, encode_grid(task["train"][-1]["output"]))
                        for key, task in tasks.items()}
        self.outputs, self.losses, self.log = {}, {}, []
        self.steps, self.target_exposed, self.trainer = 0, False, None
        self.score_failure, self.generate_failure = None, None

    def generate(self, messages, **kwargs):
        assert not self.target_exposed, "target scored before last generation"
        assert self.config["do_sample"] is False
        key, target = self.targets[digest(messages)]
        self.log.append(("generate", key, self.steps, copy.deepcopy(messages), kwargs))
        if self.generate_failure:
            return self.generate_failure(self, key)
        output = self.outputs.get((key, self.steps), self.outputs.get(self.steps, "exact"))
        if output == "exact":
            output = target
        elif output == "content":
            output = "".join(str((int(c) + 1) % 10) if c != "\n" else c for c in target)
        elif output == "shape":
            output = "000000"
        elif output == "invalid":
            output = "not a grid"
        return generation(output)

    def score_completion(self, messages, completion, **kwargs):
        assert self.trainer.active_task_id is None
        key, target = self.targets[digest(messages)]
        assert completion == target
        self.log.append(("score", key, self.steps))
        self.target_exposed = True
        if self.score_failure:
            return self.score_failure(self, key)
        loss = self.losses.get((key, self.steps), self.losses.get(self.steps, 1.0))
        return {"valid": True, "dispatched": True, "model_forward_started": True,
                "input_tokens": 17, "output_tokens": 0, "forward_calls": 1, "forward_input_tokens": 17,
                "nll_sum": 5 * loss, "token_count": 5, "mean_nll": loss}


class FixtureTrainer:
    def __init__(self, model):
        self.model, model.trainer = model, self
        self._global = {"snapshot_id": "global", "label": "global"}
        self.active_task_id = None
        self.optimizer = {"saved": [1, 2]}
        self.snapshots, self.training_snapshots = {}, {}
        self.serial, self.adaptations, self.resets, self.peak = 0, [], [], 0
        self.adapt_failure = None

    def snapshot_training_state(self, label):
        self.training_snapshots[label] = copy.deepcopy((self.model.steps, self._global, self.active_task_id, self.optimizer))
        return {"snapshot_id": label, "complete_training_state": True}

    def restore_training_state(self, handle):
        self.model.steps, self._global, self.active_task_id, self.optimizer = copy.deepcopy(self.training_snapshots[handle["snapshot_id"]])
        return {"restored": True, "complete_training_state": True, "physical_ledger_untouched": True}

    def release_training_state(self, handle):
        del self.training_snapshots[handle["snapshot_id"]]
        return {"released": True}

    def begin_task(self, key):
        assert self.active_task_id is None
        self.model.steps, self.optimizer, self.active_task_id = 0, None, key
        return {"restored": True, "task_id": key}

    def end_task(self):
        self.resets.append(self.active_task_id)
        self.model.steps, self.optimizer, self.active_task_id = 0, None, None
        return {"restored": True, "optimizer_cleared": True, "gradients_cleared": True}

    def adapt_task(self, key, demos, *, max_steps, deadline):
        assert self.active_task_id == key
        self.adaptations.append((key, copy.deepcopy(demos), max_steps))
        self.model.steps = max_steps
        if self.adapt_failure:
            return self.adapt_failure(self, max_steps)
        updates = (max_steps + 1) // 2
        return {"status": "complete", "usage_known": True, "steps": updates,
                "optimizer_steps": updates, "optimizer_state_consistent": True,
                "attempted_microbatches": max_steps, "completed_microbatches": max_steps,
                "physical_microbatch_ceiling": max_steps, "input_tokens": 20 * max_steps,
                "supervised_tokens": 5 * max_steps}

    def snapshot(self, label):
        self.serial += 1
        handle = {"snapshot_id": str(self.serial), "label": label, "fingerprint": {"sha256": str(self.model.steps)}}
        self.snapshots[str(self.serial)] = self.model.steps
        self.peak = max(self.peak, len(self.snapshots))
        return handle

    def restore(self, handle):
        assert self.active_task_id is None
        self.model.steps = self.snapshots[handle["snapshot_id"]]
        self.optimizer = None
        return {"restored": True}

    def release_snapshot(self, handle):
        del self.snapshots[handle["snapshot_id"]]
        return {"released": True}


class TttEffectivenessTests(unittest.TestCase):
    def setUp(self):
        self.tasks, self.manifest = sources()
        self.model = FixtureModel(self.tasks)
        self.trainer = FixtureTrainer(self.model)

    def run_selection(self, **kwargs):
        config = {"seed": 7, "dev_tasks": 2, "max_new_tokens": 64, "evidence_mode": "mock_fixture"}
        config.update(kwargs.pop("config", {}))
        with tempfile.TemporaryDirectory() as output:
            report = select_ttt(kwargs.pop("tasks", self.tasks), kwargs.pop("manifest", self.manifest),
                self.model, self.trainer, kwargs.pop("deadline", time.monotonic() + 30), output, config, **kwargs)
            self.assertEqual(report, json.loads((Path(output) / "dev-selection.json").read_text()))
        return report

    def test_exact_beats_low_nll_with_fixed_order_and_accumulation_units(self):
        self.model.outputs = {0: "content", 8: "exact", 16: "shape"}
        self.model.losses = {0: .00001, 8: 20, 16: .000001}
        original = copy.deepcopy((self.trainer._global, self.trainer.optimizer, self.model.config))
        report = self.run_selection()
        self.assertTrue(report["comparison_complete"], report)
        self.assertEqual(report["selected_ttt_steps"], 8)
        self.assertEqual(report["predeclared_tasks"], _rank_ids(["c", "d"], 7))
        from tools.arc_learning_agent_20261011.worker import _rank_ids as worker_rank
        self.assertEqual(report["predeclared_tasks"], worker_rank(["c", "d"], 7))
        self.assertEqual(report["complete_matched_options"], [0, 8, 16])
        self.assertEqual(report["usage"]["attempted_microbatches"], 48)
        self.assertEqual(report["usage"]["optimizer_updates"], 24)
        self.assertEqual(report["usage"]["generation_calls"], 6)
        self.assertEqual(report["usage"]["scoring_calls"], 6)
        self.assertEqual((self.trainer._global, self.trainer.optimizer, self.model.config), original)
        self.assertIsNone(self.trainer.active_task_id)
        self.assertFalse(self.trainer.snapshots or self.trainer.training_snapshots)
        self.assertEqual(report["peak_option_snapshot_handles"], 6)
        self.assertFalse(report["public_answers_used"])
        self.assertEqual(report["evidence"], "mock_fixture_not_neural_proof")

    def test_all_generation_before_targets_visible_only_adaptation(self):
        report = self.run_selection()
        self.assertTrue(report["comparison_complete"])
        self.assertEqual([row[0] for row in self.model.log], ["generate"] * 6 + ["score"] * 6)
        for key, demos, steps in self.trainer.adaptations:
            self.assertEqual(demos, self.tasks[key[4:]]["train"][:-1])
            self.assertNotIn(self.tasks[key[4:]]["train"][-1], demos)
        for _, key, steps, messages, kwargs in self.model.log[:6]:
            task = self.tasks[key]
            self.assertEqual(messages, grid_messages(task["train"][:-1], task["train"][-1]["input"]))
            self.assertEqual(kwargs["max_new_tokens"], 64)
            self.assertNotIn("completion", kwargs)
        self.assertEqual(len(self.trainer.resets), 6)
        self.assertEqual([row[2] for row in self.model.log[:6]], [row[2] for row in self.model.log[6:]])

    def test_nll_alone_never_activates_even_when_all_generated_exact(self):
        self.model.losses = {0: 10, 8: 1, 16: .01}
        report = self.run_selection()
        self.assertEqual(report["selected_ttt_steps"], 0)
        self.assertEqual(report["selection_reason"], "no-generated-improvement")
        self.assertFalse(report["eligible_nonzero_options"])

    def test_dimension_and_validity_improve_then_nll_and_lower_ceiling_ties(self):
        for outputs, losses, expected in (({0: "shape", 8: "content", 16: "content"}, {8: 2, 16: 1}, 16),
                                         ({0: "shape", 8: "content", 16: "content"}, {8: 1, 16: 1}, 8),
                                         ({0: "invalid", 8: "shape", 16: "invalid"}, {8: 9, 16: .01}, 8)):
            with self.subTest(outputs=outputs, losses=losses):
                self.model = FixtureModel(self.tasks)
                self.trainer = FixtureTrainer(self.model)
                self.model.outputs, self.model.losses = outputs, losses
                report = self.run_selection()
                self.assertTrue(report["comparison_complete"])
                self.assertEqual(report["selected_ttt_steps"], expected)

    def test_exact_gain_cannot_hide_dimension_regression(self):
        self.model.outputs = {0: "content", ("c", 8): "exact", ("d", 8): "shape", 16: "content"}
        report = self.run_selection()
        self.assertEqual(report["option_metrics"]["8"]["exact"], 1)
        self.assertEqual(report["option_metrics"]["8"]["dimension_correct"], 1)
        self.assertEqual(report["selected_ttt_steps"], 0)

    def test_missing_generation_score_and_partial_microbatches_default_zero(self):
        def partial(trainer, steps):
            return {"status": "complete", "usage_known": True, "steps": steps, "optimizer_steps": steps,
                    "optimizer_state_consistent": True, "attempted_microbatches": steps - 1,
                    "completed_microbatches": steps - 1, "physical_microbatch_ceiling": steps,
                    "input_tokens": 5, "supervised_tokens": 1}
        for failure in ("generation", "score", "adaptation"):
            with self.subTest(failure=failure):
                self.model = FixtureModel(self.tasks)
                self.trainer = FixtureTrainer(self.model)
                self.model.outputs = {0: "shape", 8: "exact", 16: "content"}
                if failure == "generation":
                    self.model.generate_failure = lambda model, key: None
                elif failure == "score":
                    self.model.score_failure = lambda model, key: None
                else:
                    self.trainer.adapt_failure = partial
                report = self.run_selection()
                self.assertFalse(report["comparison_complete"])
                self.assertEqual(report["selected_ttt_steps"], 0)
                self.assertEqual(len(report["rows"]), 6)
                self.assertEqual(report["option_metrics"]["8"]["denominator"], 2)
                self.assertFalse(self.trainer.snapshots or self.trainer.training_snapshots)

    def test_exceptions_restore_active_caller_and_release_snapshots(self):
        self.trainer.active_task_id, self.model.steps = "caller-task", 99
        before = copy.deepcopy((self.trainer._global, self.trainer.optimizer, self.model.config))
        def fail(model, key):
            raise RuntimeError("injected generation failure")
        self.model.generate_failure = fail
        report = self.run_selection()
        self.assertFalse(report["comparison_complete"])
        self.assertEqual(self.trainer.active_task_id, "caller-task")
        self.assertEqual(self.model.steps, 99)
        self.assertEqual((self.trainer._global, self.trainer.optimizer, self.model.config), before)
        self.assertFalse(self.trainer.snapshots or self.trainer.training_snapshots)

    def test_deadline_and_missing_source_do_not_reduce_fixed_denominator(self):
        report = self.run_selection(deadline=time.monotonic() - 1)
        self.assertFalse(report["comparison_complete"])
        self.assertEqual(report["usage"]["attempted_calls"], {"generation_calls": 0, "scoring_calls": 0, "adaptation_calls": 0})
        self.assertEqual(len(report["rows"]), 6)
        self.model.target_exposed = False
        tasks = copy.deepcopy(self.tasks)
        del tasks["d"]
        report = self.run_selection(tasks=tasks)
        self.assertEqual(report["predeclared_tasks"], _rank_ids(["c", "d"], 7))
        self.assertFalse(report["comparison_complete"])
        self.assertEqual(report["selected_ttt_steps"], 0)

    def test_manifest_source_and_protected_ancestry_rejected_before_work(self):
        tasks = copy.deepcopy(self.tasks)
        tasks["c"]["train"][-1]["output"] = [[0]]
        with self.assertRaisesRegex(ValueError, "source hash"):
            self.run_selection(tasks=tasks)
        with self.assertRaisesRegex(ValueError, "protected"):
            self.run_selection(protected_ids=["c"])
        tasks = copy.deepcopy(self.tasks)
        tasks["c"]["test"] = [{"input": [[1]], "output": [[2]]}]
        with self.assertRaisesRegex(ValueError, "demonstration-only"):
            self.run_selection(tasks=tasks)
        self.assertFalse(self.model.log)

    def test_tiny_options_and_token_mismatch_fail_closed(self):
        report = self.run_selection(config={"tiny_cpu": True, "dev_tasks": 1})
        self.assertEqual(report["predeclared_options"], [0, 1])
        self.assertEqual(report["usage"]["attempted_microbatches"], 1)
        self.model.target_exposed = False
        original = self.model.score_completion
        def changed(messages, completion, **kwargs):
            result = original(messages, completion, **kwargs)
            result["token_count"] += self.model.steps
            result["nll_sum"] = result["token_count"] * result["mean_nll"]
            return result
        self.model.score_completion = changed
        report = self.run_selection()
        self.assertFalse(report["comparison_complete"])
        self.assertEqual(report["selected_ttt_steps"], 0)

    def test_metered_budget_exhaustion_keeps_charges_and_defaults_zero(self):
        from tools.arc_learning_agent_20261011.metering import MeteredModel, MeteredTrainer
        with tempfile.TemporaryDirectory() as output:
            ledger = WorkLedger(Path(output) / "physical.jsonl", caps={**DEFAULT_CAPS, "training_steps": 1})
            result = select_ttt(self.tasks, self.manifest, MeteredModel(self.model, ledger),
                MeteredTrainer(self.trainer, ledger, max_sequence_tokens=128), time.monotonic() + 30,
                output, {"evidence_mode": "mock_fixture", "max_new_tokens": 64, "dev_tasks": 2})
            self.assertFalse(result["comparison_complete"])
            self.assertEqual(result["selected_ttt_steps"], 0)
            self.assertEqual(result["usage"]["attempted_microbatches"], 1)
            self.assertEqual(ledger.used["training_steps"], 1)
            self.assertEqual(len(result["usage"]["ledgers"]), 1)
            self.assertEqual(result["usage"]["ledgers"][0]["charged_delta"], ledger.used)
            self.assertFalse(ledger.pending)

    def test_insufficient_eligible_tasks_keeps_requested_denominator(self):
        report = self.run_selection(config={"dev_tasks": 4})
        self.assertFalse(report["comparison_complete"])
        self.assertEqual(report["selected_ttt_steps"], 0)
        self.assertEqual(report["option_metrics"]["8"]["denominator"], 4)
        self.assertEqual(report["complete_matched_options"], [])
        self.assertIsNone(report["mean_nll"]["8"])
        self.assertEqual(report["budgets"]["max_generation_calls"], 12)
        self.assertTrue(any("insufficient fixed dev tasks" in error for error in report["errors"]))

    def test_failed_optimizer_boundary_stops_all_further_neural_work_and_restores(self):
        from tools.arc_learning_agent_20261011.metering import MeteredModel, MeteredTrainer
        original = copy.deepcopy((self.trainer._global, self.trainer.optimizer))
        def failed(trainer, steps):
            return {"status": "failed_update", "usage_known": True, "steps": 0,
                    "optimizer_steps": 0, "attempted_microbatches": 1,
                    "completed_microbatches": 0, "physical_microbatch_ceiling": steps,
                    "input_tokens": 20, "supervised_tokens": 5}
        self.trainer.adapt_failure = failed
        for metered in (False, True):
            with self.subTest(metered=metered), tempfile.TemporaryDirectory() as output:
                self.model.log.clear()
                ledger = WorkLedger(Path(output) / "physical.jsonl")
                report = select_ttt(self.tasks, self.manifest,
                    MeteredModel(self.model, ledger) if metered else self.model,
                    MeteredTrainer(self.trainer, ledger, max_sequence_tokens=128) if metered else self.trainer,
                    time.monotonic() + 30, output,
                    {"evidence_mode": "mock_fixture", "dev_tasks": 2, "max_new_tokens": 64})
                self.assertTrue(report["stop_all_new_neural_work"])
                self.assertFalse(report["comparison_complete"])
                self.assertEqual(report["selected_ttt_steps"], 0)
                self.assertEqual([row[0] for row in self.model.log], ["generate"])
                self.assertEqual(report["usage"]["attempted_microbatches"], 1)
                self.assertEqual(report["usage"]["optimizer_updates"], 0)
                self.assertFalse(self.trainer.snapshots or self.trainer.training_snapshots)
                self.assertEqual((self.trainer._global, self.trainer.optimizer), original)
                self.assertIsNone(self.trainer.active_task_id)
                if metered:
                    self.assertEqual(ledger.used["training_steps"], 1)
                    self.assertFalse(ledger.pending)

    def test_one_missing_option_cannot_select_easier_subset(self):
        self.model.outputs = {0: "shape", 8: "exact", 16: "content"}
        original = self.model.generate
        def missing(messages, **kwargs):
            if self.model.targets[digest(messages)][0] == "d" and self.model.steps == 16:
                return None
            return original(messages, **kwargs)
        self.model.generate = missing
        report = self.run_selection()
        self.assertEqual(report["complete_matched_tasks"], ["c"])
        self.assertEqual(report["option_metrics"]["8"]["exact"], 2)
        self.assertEqual(report["selected_ttt_steps"], 0)
        self.assertFalse(report["comparison_complete"])

    def test_nonfinite_nll_remains_serializable_and_never_selects(self):
        self.model.losses = {8: float("nan")}
        self.model.outputs = {0: "shape", 8: "exact", 16: "content"}
        report = self.run_selection()
        self.assertFalse(report["comparison_complete"])
        self.assertEqual(report["selected_ttt_steps"], 0)
        self.assertTrue(any(row["score"]["mean_nll"] == "nonfinite:nan" for row in report["rows"]))

    def test_unmetered_adaptation_exception_is_unknown_and_stops_new_work(self):
        def failed(trainer, steps):
            trainer.end_task()
            raise RuntimeError("unknown attempted optimizer work")
        self.trainer.adapt_failure = failed
        report = self.run_selection()
        self.assertTrue(report["stop_all_new_neural_work"])
        self.assertFalse(report["usage"]["usage_known"])
        self.assertEqual([row[0] for row in self.model.log], ["generate"])
        self.assertEqual(report["selected_ttt_steps"], 0)
        self.assertFalse(self.trainer.snapshots or self.trainer.training_snapshots)


@unittest.skipUnless(os.environ.get("ARC_LEARNING_NEURAL_TESTS") == "1", "explicit tiny CPU neural tests only")
class TttEffectivenessNeuralTests(unittest.TestCase):
    def test_real_tiny_native_cpu_matched_options_metering_and_complete_state_restore(self):
        self.assertEqual(os.environ.get("CUDA_VISIBLE_DEVICES"), "")
        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")
        import torch
        torch.set_num_threads(1)
        from transformers import LlamaConfig, LlamaForCausalLM
        from tools.arc_learning_agent_20261011.native_model import NativeModel, TinyByteTokenizer
        from tools.arc_learning_agent_20261011.training import Trainer
        from tools.arc_learning_agent_20261011.metering import MeteredModel, MeteredTrainer
        from tools.arc_learning_agent_20261011.data import build_records
        tasks, manifest = sources()
        torch.manual_seed(41)
        native = NativeModel(LlamaForCausalLM(LlamaConfig(vocab_size=130, hidden_size=16,
            intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2,
            max_position_embeddings=2048, bos_token_id=129, eos_token_id=128, pad_token_id=128)),
            TinyByteTokenizer(), {"tiny_cpu": True, "context_limit": 1024, "prompt_cap": 768,
                                  "output_cap": 64, "do_sample": True, "temperature": .7, "top_p": .8})
        trainer = Trainer(native, {"tiny_cpu": True, "lora_rank": 2, "lora_alpha": 4,
            "gradient_checkpointing": False, "max_sequence_tokens": 1024, "task_augmentations": 1,
            "seed": 7, "stability_mode": True, "schedule_steps": 12, "warmup_steps": 2,
            "accumulation_target_tokens": 1000, "accumulation_max_microbatches": 2,
            "split_manifest": manifest, "protected_ids": []})
        trainer.freeze_global()
        # Preserve real Adam/scheduler/cursor state as well as an existing frozen
        # global. This is logical restoration, never a physical-work refund.
        trainer.train(build_records(tasks, manifest, augmentations=1), max_steps=2, deadline=time.monotonic() + 30)
        before = trainer.snapshot_training_state("before-proof")
        before_config, before_global = copy.deepcopy(native.config), copy.deepcopy(trainer._global)
        with tempfile.TemporaryDirectory() as output:
            ledger = WorkLedger(Path(output) / "physical.jsonl")
            metered = MeteredTrainer(trainer, ledger, max_sequence_tokens=1024)
            report = select_ttt(tasks, manifest, MeteredModel(native, ledger), metered,
                time.monotonic() + 60, output, {"tiny_cpu": True, "dev_tasks": 1, "max_new_tokens": 12})
            self.assertTrue(report["comparison_complete"], report)
            self.assertEqual(report["evidence"], "tiny_cpu_neural_not_pretrained")
            self.assertEqual(report["predeclared_options"], [0, 1])
            self.assertEqual(report["usage"]["attempted_microbatches"], 1)
            self.assertEqual(report["usage"]["optimizer_updates"], 1)
            self.assertEqual(ledger.used["training_steps"], 1)
            self.assertEqual(ledger.used["generation_calls"], 2)
            self.assertEqual(ledger.used["scoring_forwards"], 2)
            self.assertFalse(ledger.pending)
            self.assertEqual(metered.completed_optimizer_steps, 1)
        after = trainer.snapshot_training_state("after-proof")
        self.assertEqual(before["state_sha256"], after["state_sha256"])
        self.assertEqual(before["fingerprint"], after["fingerprint"])
        self.assertEqual(trainer._global, before_global)
        self.assertEqual(native.config, before_config)
        self.assertIsNone(trainer.active_task_id)
        self.assertEqual(set(trainer._snapshots), {before_global["snapshot_id"]})
        trainer.release_training_state(before)
        trainer.release_training_state(after)
        self.assertFalse(trainer._training_snapshots)
        native.close()


if __name__ == "__main__":
    unittest.main()

"""Actual CPU neural tests; opt in explicitly, no model downloads or GPU work."""
import copy
import json
import os
from pathlib import Path
import random
import tempfile
import time
import unittest

from tools.arc_learning_agent_20261011.data import build_records, create_split_manifest
from tools.arc_learning_agent_20261011.tests.test_data import fixture_tasks


@unittest.skipUnless(os.environ.get("ARC_LEARNING_NEURAL_TESTS") == "1", "explicit tiny CPU neural tests only")
class TrainingNeuralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(2)
        cls.torch = torch
        cls.tasks = fixture_tasks()
        cls.manifest = create_split_manifest(cls.tasks)
        cls.records = build_records(cls.tasks, cls.manifest, augmentations=1)

    def make_trainer(self, **overrides):
        from transformers import LlamaConfig, LlamaForCausalLM
        from tools.arc_learning_agent_20261011.native_model import NativeModel, TinyByteTokenizer
        from tools.arc_learning_agent_20261011.training import Trainer
        limits = overrides.pop("native_limits", {})
        native_overrides = overrides.pop("native_overrides", {})
        self.torch.manual_seed(41)
        model = LlamaForCausalLM(LlamaConfig(vocab_size=130, hidden_size=16, intermediate_size=32,
            num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2,
            max_position_embeddings=2048, attention_dropout=0.1, bos_token_id=129, eos_token_id=128, pad_token_id=128))
        native = NativeModel(model, TinyByteTokenizer(), {"tiny_cpu": True, "context_limit": 1024, "prompt_cap": 768, "output_cap": 256, **limits, **native_overrides})
        return Trainer(native, {"tiny_cpu": True, "lora_rank": 2, "lora_alpha": 4, "learning_rate": 0.002,
            "task_learning_rate": 0.002, "gradient_checkpointing": False, "max_sequence_tokens": 1024,
            "task_augmentations": 1, "seed": 123, "split_manifest": self.manifest, "protected_ids": [], **overrides})

    def run_steps(self, trainer, steps, **kwargs):
        return trainer.train(self.records, max_steps=steps, deadline=time.monotonic() + 120, **kwargs)

    def test_real_full_vocab_forward_backward_changes_only_lora(self):
        trainer = self.make_trainer(gradient_checkpointing=True)
        frozen = {k: p.detach().clone() for k, p in trainer.model.named_parameters() if not p.requires_grad}
        before = trainer.fingerprint()
        receipt = self.run_steps(trainer, 2)
        self.assertEqual(receipt["steps"], 2, receipt)
        self.assertEqual(receipt["full_native_vocabulary"], 130)
        self.assertNotEqual(before["sha256"], receipt["adapter_after_sha256"])
        self.assertTrue(all(u["finite_gradients"] and u["changed_adapter_tensors"] > 0 for u in receipt["updates"]))
        self.assertGreater(receipt["input_tokens"], receipt["supervised_tokens"])
        self.assertEqual(receipt["attempted_microbatches"], 2)
        for k, p in trainer.model.named_parameters():
            if k in frozen:
                self.assertTrue(self.torch.equal(p, frozen[k]), k)
        self.assertEqual({int(float(s["step"])) for s in trainer.optimizer.state.values()}, {2})

    def test_exact_native_completion_mask_and_full_head_loss(self):
        trainer = self.make_trainer()
        record = self.records[0]
        row = trainer._prepared(record)
        self.assertEqual(row["labels"][:row["prompt_tokens"]], [-100] * row["prompt_tokens"])
        self.assertEqual(row["input_ids"][-1], 128)
        self.assertEqual(row["labels"][-1], 128)
        ids = self.torch.tensor([row["input_ids"]])
        labels = self.torch.tensor([row["labels"]])
        trainer.model.eval()
        with self.torch.no_grad():
            output = trainer.model(input_ids=ids, labels=labels, use_cache=False)
        expected = self.torch.nn.functional.cross_entropy(output.logits[:, :-1, :].float().reshape(-1, 130), labels[:, 1:].reshape(-1))
        self.assertTrue(self.torch.allclose(expected, output.loss, atol=1e-6))
        scored = trainer.native.score_completion(record["messages"], record["completion"], deadline=time.monotonic() + 30)
        self.assertTrue(scored["valid"], scored)
        self.assertAlmostEqual(scored["mean_nll"], float(expected), places=5)

    def test_real_native_granite_tokenizer_100352_head_lora_update(self):
        from transformers import AutoTokenizer, GraniteConfig, GraniteForCausalLM
        from tools.arc_learning_agent_20261011.native_model import NativeModel
        from tools.arc_learning_agent_20261011.training import Trainer
        tokenizer_root = Path(__file__).resolve().parents[4] / "tokenizer-assets"
        if not (tokenizer_root / "tokenizer.json").is_file():
            self.skipTest("actual pinned tokenizer assets absent")
        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_root), local_files_only=True, trust_remote_code=False)
        self.torch.manual_seed(19)
        model = GraniteForCausalLM(GraniteConfig(vocab_size=100352, hidden_size=16, intermediate_size=32,
            num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2,
            max_position_embeddings=2048, bos_token_id=tokenizer.bos_token_id, eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id))
        native = NativeModel(model, tokenizer, {"tiny_cpu": True, "context_limit": 1024, "prompt_cap": 768, "output_cap": 256})
        trainer = Trainer(native, {"tiny_cpu": True, "lora_rank": 2, "lora_alpha": 4, "learning_rate": .002,
            "gradient_checkpointing": False, "split_manifest": self.manifest, "protected_ids": []})
        result = self.run_steps(trainer, 1)
        self.assertEqual(result["steps"], 1, result)
        self.assertEqual(result["full_native_vocabulary"], 100352)
        self.assertGreater(result["updates"][0]["changed_adapter_tensors"], 0)
        row = trainer._prepared(self.records[0])
        self.assertEqual(row["labels"][-1], tokenizer.eos_token_id)
        self.assertGreater(row["labels"][-1], 16)

    def test_global_checkpoint_resume_matches_uninterrupted_every_state(self):
        from tools.arc_learning_agent_20261011.training import _fingerprint_tree
        uninterrupted = self.make_trainer(schedule_steps=6, warmup_steps=1)
        full = self.run_steps(uninterrupted, 5)
        self.assertEqual(full["steps"], 5, full)
        with tempfile.TemporaryDirectory() as tmp:
            first = self.make_trainer(schedule_steps=6, warmup_steps=1)
            partial = self.run_steps(first, 2, checkpoint_dir=tmp)
            path = partial["checkpoints"][-1]["path"]
            # Constructor creates another base/adapter/optimizer identity; restart loads real tensors/states.
            restarted = self.make_trainer(schedule_steps=6, warmup_steps=1)
            result = self.run_steps(restarted, 3, resume=path)
            self.assertEqual(result["steps"], 3, result)
            self.assertEqual(result["total_steps"], 5)
            self.assertEqual(result["adapter_after_sha256"], full["adapter_after_sha256"])
            self.assertEqual(result["optimizer_state_sha256"], full["optimizer_state_sha256"])
            self.assertEqual(result["rng_sha256"], full["rng_sha256"])
            self.assertEqual(result["cursor"], full["cursor"])
            self.assertEqual(_fingerprint_tree(restarted.scheduler.state_dict(), self.torch), _fingerprint_tree(uninterrupted.scheduler.state_dict(), self.torch))
            self.assertEqual([u["record_id"] for u in result["updates"]], [u["record_id"] for u in full["updates"]][2:])
            self.assertEqual(result["losses"], full["losses"][2:])

    def test_weighted_objective_family_resume_and_missing_kind_receipts(self):
        from tools.arc_learning_agent_20261011.data import build_authored_curriculum
        with tempfile.TemporaryDirectory() as tmp:
            rows, manifest, _ = build_authored_curriculum(per_family=1, deadline=time.monotonic() + 60, output_dir=Path(tmp) / "authored")
            config = {"split_manifest": manifest, "max_sequence_tokens": 4096,
                      "native_limits": {"context_limit": 4096, "prompt_cap": 3584, "output_cap": 1024},
                      "objective_cycle": ["grid", "program", "repair"]}
            full = self.make_trainer(**copy.deepcopy(config))
            all_result = full.train(rows, max_steps=6, deadline=time.monotonic() + 120)
            self.assertEqual(all_result["steps"], 6, all_result)
            self.assertEqual({k: v["microbatches"] for k, v in all_result["processed_by_kind"].items()}, {"grid": 2, "program": 2, "repair": 2})
            first = self.make_trainer(**copy.deepcopy(config))
            partial = first.train(rows, max_steps=2, deadline=time.monotonic() + 120, checkpoint_dir=Path(tmp) / "checkpoints")
            second = self.make_trainer(**copy.deepcopy(config))
            resumed = second.train(rows, max_steps=4, deadline=time.monotonic() + 120, resume=partial["checkpoints"][-1]["path"])
            self.assertEqual(resumed["adapter_after_sha256"], all_result["adapter_after_sha256"])
            self.assertEqual(resumed["optimizer_state_sha256"], all_result["optimizer_state_sha256"])
            self.assertEqual(resumed["rng_sha256"], all_result["rng_sha256"])
            self.assertEqual(resumed["cursor"], all_result["cursor"])
            self.assertEqual(resumed["cumulative_processed_by_kind"], all_result["cumulative_processed_by_kind"])
            self.assertEqual(resumed["cumulative_unique_record_count"], all_result["cumulative_unique_record_count"])
        grid_only = self.make_trainer(objective_cycle=["grid"] * 6 + ["program", "repair"])
        result = self.run_steps(grid_only, 2)
        self.assertEqual(result["sampling"]["effective_cycle"], ["grid"] * 6)
        self.assertEqual(result["sampling"]["missing_kinds_removed"], ["program", "repair"])

    def test_owned_checkpoint_retention_two_and_disk_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            trainer = self.make_trainer(checkpoint_every=1, checkpoint_keep=2, checkpoint_disk_reserve_bytes=16 * 1024**2)
            result = self.run_steps(trainer, 3, checkpoint_dir=tmp)
            history = json.loads((Path(tmp) / "checkpoint-history.json").read_text())
            self.assertEqual([r["status"] for r in history], ["pruned_after_durable_latest", "retained", "retained"])
            self.assertFalse(Path(result["checkpoints"][0]["path"]).exists())
            self.assertTrue(Path(result["checkpoints"][-1]["path"]).is_dir())
            self.assertEqual(len(list(Path(tmp).glob("step-*"))), 2)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "unowned.txt").write_text("must not delete")
            trainer = self.make_trainer()
            self.run_steps(trainer, 1)
            with self.assertRaisesRegex(ValueError, "no ownership binding"):
                trainer.save_checkpoint(tmp)
            self.assertEqual((Path(tmp) / "unowned.txt").read_text(), "must not delete")
        with tempfile.TemporaryDirectory() as tmp:
            trainer = self.make_trainer(checkpoint_disk_reserve_bytes=10**18)
            self.run_steps(trainer, 1)
            with self.assertRaisesRegex(ValueError, "disk reserve"):
                trainer.save_checkpoint(tmp)
            self.assertFalse(list(Path(tmp).glob("step-*")))

    def test_adapt_exception_reset_and_idempotent_finally(self):
        trainer = self.make_trainer()
        baseline = trainer.freeze_global()["fingerprint"]["sha256"]
        with self.assertRaises(ValueError):
            trainer.adapt_task("bad", [{"input": [[True]], "output": [[1]]}], max_steps=1, deadline=time.monotonic()+30)
        self.assertIsNone(trainer.active_task_id)
        self.assertTrue(trainer.last_task_reset_receipt["restored"])
        final = trainer.end_task()
        self.assertTrue(final["already_ended"])
        self.assertEqual(final["adapter_sha256"], baseline)

    def test_checkpoint_rejects_config_data_source_and_byte_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            trainer = self.make_trainer()
            result = self.run_steps(trainer, 1, checkpoint_dir=tmp)
            path = Path(result["checkpoints"][-1]["path"])
            changed = self.make_trainer(learning_rate=0.003)
            with self.assertRaisesRegex(ValueError, "identity differs"):
                self.run_steps(changed, 1, resume=path)
            fresh = self.make_trainer()
            identity = fresh._identity(self.records)
            identity["source"]["modified-source"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "identity differs"):
                fresh.load_checkpoint(path, identity=identity, records_count=sum(r["split"] == "train" for r in self.records))
            data_changed = list(reversed(self.records))
            with self.assertRaisesRegex(ValueError, "identity differs"):
                fresh.train(data_changed, max_steps=1, deadline=time.monotonic() + 30, resume=path)
            state = path / "state.pt"
            body = state.read_bytes()
            state.write_bytes(body[:-1] + bytes([body[-1] ^ 1]))
            with self.assertRaisesRegex(ValueError, "bytes changed"):
                self.run_steps(fresh, 1, resume=path)

    def test_fingerprint_cache_invalidates_tracked_updates_and_restores(self):
        trainer = self.make_trainer()
        baseline = trainer.snapshot("cache-baseline")
        first = trainer.fingerprint()
        rehashes = trainer.fingerprint_rehashes
        self.assertEqual(first, trainer.fingerprint())
        self.assertEqual(trainer.fingerprint_rehashes, rehashes)
        with self.torch.no_grad():
            next(iter(trainer.parameters.values())).add_(0.001)
        changed = trainer.fingerprint()
        self.assertNotEqual(first["sha256"], changed["sha256"])
        self.assertEqual(trainer.fingerprint_rehashes, rehashes + 1)
        trainer.restore(baseline)
        self.assertEqual(trainer.fingerprint(), first)
        # Returned dictionaries do not permit corrupting the retained cache.
        fingerprint = trainer.fingerprint()
        fingerprint["sha256"] = "mutated-by-caller"
        self.assertEqual(trainer.fingerprint(), first)
        result = self.run_steps(trainer, 1)
        self.assertEqual(result["steps"], 1, result)
        self.assertNotEqual(result["adapter_after_sha256"], first["sha256"])
        self.assertGreater(result["updates"][0]["elapsed_seconds"], 0)

    def test_checkpoint_binds_runtime_precision_and_environment_lock(self):
        old_precision = self.torch.get_float32_matmul_precision()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                lock = Path(tmp) / "fixture-environment.json"
                lock.write_text('{"synthetic_fixture_version":1}')
                trainer = self.make_trainer(native_overrides={"environment_lock_path": str(lock)})
                result = self.run_steps(trainer, 1, checkpoint_dir=Path(tmp) / "checkpoint")
                path = result["checkpoints"][-1]["path"]
                runtime = trainer._base_identity["runtime"]
                self.assertEqual(runtime["torch"], str(self.torch.__version__))
                self.assertTrue(runtime["environment_lock_sha256"])
                self.torch.set_float32_matmul_precision("medium" if old_precision != "medium" else "highest")
                changed = self.make_trainer(native_overrides={"environment_lock_path": str(lock)})
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    self.run_steps(changed, 1, resume=path)
                self.torch.set_float32_matmul_precision(old_precision)
                lock.write_text('{"synthetic_fixture_version":2}')
                changed_lock = self.make_trainer(native_overrides={"environment_lock_path": str(lock)})
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    self.run_steps(changed_lock, 1, resume=path)
        finally:
            self.torch.set_float32_matmul_precision(old_precision)

    def test_task_a_then_b_equals_fresh_b_and_global_reset(self):
        from tools.arc_learning_agent_20261011.training import _fingerprint_tree
        first = self.make_trainer()
        self.run_steps(first, 2)
        global_state = first.freeze_global()
        caller = _fingerprint_tree(first._get_rng(), self.torch)
        first.begin_task("A")
        a = first.adapt_task("A", self.tasks["a"]["train"], max_steps=2, deadline=time.monotonic() + 30)
        self.assertEqual(a["steps"], 2, a)
        reset = first.end_task()
        self.assertEqual(reset["adapter_sha256"], global_state["fingerprint"]["sha256"])
        self.assertEqual(_fingerprint_tree(first._get_rng(), self.torch), caller)
        self.assertIsNone(first.optimizer)
        self.assertIsNone(first.scheduler)
        self.assertTrue(all(p.grad is None for p in first.parameters.values()))
        b = first.adapt_task("B", self.tasks["b"]["train"], max_steps=2, deadline=time.monotonic() + 30)
        self.assertEqual(b["updates"][0]["adam_step"], 1)
        first.end_task()
        fresh = self.make_trainer()
        self.run_steps(fresh, 2)
        fresh.freeze_global()
        only_b = fresh.adapt_task("B", self.tasks["b"]["train"], max_steps=2, deadline=time.monotonic() + 30)
        self.assertEqual(b["adapter_after_sha256"], only_b["adapter_after_sha256"])
        self.assertEqual(b["optimizer_state_sha256"], only_b["optimizer_state_sha256"])
        self.assertEqual(b["losses"], only_b["losses"])
        self.assertEqual(b["rng_sha256"], only_b["rng_sha256"])
        fresh.end_task()

    def test_actual_peft_export_and_fresh_tiny_base_reload(self):
        from transformers import LlamaConfig, LlamaForCausalLM
        from peft import PeftModel
        from tools.arc_learning_agent_20261011.native_model import NativeModel, TinyByteTokenizer
        trainer = self.make_trainer()
        self.run_steps(trainer, 2)
        record = self.records[0]
        before = trainer.native.score_completion(record["messages"], record["completion"], deadline=time.monotonic() + 30)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "export"
            exported = trainer.export_adapter(root)
            self.assertTrue(exported["saved_state_exact"])
            self.assertFalse(exported["resume_capable"])
            marker = json.loads((root / "tiny-byte-tokenizer.json").read_text())
            self.assertTrue(marker["synthetic_only"])
            self.assertFalse(marker["production_compatible"])
            self.torch.manual_seed(41)
            base = LlamaForCausalLM(LlamaConfig(vocab_size=130, hidden_size=16, intermediate_size=32,
                num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2,
                max_position_embeddings=2048, attention_dropout=0.1, bos_token_id=129, eos_token_id=128, pad_token_id=128))
            reloaded = PeftModel.from_pretrained(base, str(root), is_trainable=False, local_files_only=True)
            native = NativeModel(reloaded, TinyByteTokenizer.from_pretrained(root), {"tiny_cpu": True, "context_limit": 1024, "prompt_cap": 768, "output_cap": 256})
            after = native.score_completion(record["messages"], record["completion"], deadline=time.monotonic() + 30)
            self.assertTrue(after["valid"], after)
            self.assertEqual(before["nll_sum"], after["nll_sum"])
            self.assertEqual(before["token_count"], after["token_count"])

    def test_snapshot_immutable_and_single_demo_skip(self):
        trainer = self.make_trainer()
        snap = trainer.freeze_global()
        changed = copy.deepcopy(snap)
        changed["fingerprint"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            trainer.restore(changed)
        trainer.adapt_task("single", [{"input": [[1]], "output": [[2]]}], max_steps=10, deadline=time.monotonic() + 30)
        self.assertIsNone(trainer.optimizer)
        trainer.end_task()
        self.assertEqual(trainer.fingerprint(), snap["fingerprint"])

    def test_context_deadline_token_budget_fail_closed(self):
        trainer = self.make_trainer(max_sequence_tokens=10)
        receipt = self.run_steps(trainer, 1)
        self.assertEqual(receipt["status"], "no_context_eligible_records")
        self.assertEqual(receipt["steps"], 0)
        self.assertEqual(receipt["input_tokens"], 0)
        trainer = self.make_trainer(max_input_tokens=1)
        receipt = self.run_steps(trainer, 1)
        self.assertEqual(receipt["status"], "token_budget")
        self.assertEqual(receipt["steps"], 0)
        trainer = self.make_trainer()
        receipt = trainer.train(self.records, max_steps=2, deadline=time.monotonic() - 1)
        self.assertEqual(receipt["status"], "deadline")
        self.assertEqual(receipt["steps"], 0)

    def test_failed_forward_is_charged_and_cannot_checkpoint(self):
        trainer = self.make_trainer()
        def fail(_):
            raise RuntimeError("deliberate forward failure")
        trainer._step = fail
        result = self.run_steps(trainer, 1)
        self.assertEqual(result["status"], "failed_update")
        self.assertEqual(result["steps"], 0)
        self.assertEqual(result["attempted_microbatches"], 1)
        self.assertGreater(result["input_tokens"], 0)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            trainer.save_checkpoint(tmp)
        with self.assertRaises(ValueError):
            self.run_steps(trainer, 1)

    def test_global_train_rejects_protected_and_unmanifested_rows(self):
        trainer = self.make_trainer(protected_ids=[self.records[0]["task_id"]])
        with self.assertRaises(ValueError):
            self.run_steps(trainer, 1)
        trainer = self.make_trainer(split_manifest=None)
        with self.assertRaises(ValueError):
            self.run_steps(trainer, 1)


if __name__ == "__main__":
    unittest.main()

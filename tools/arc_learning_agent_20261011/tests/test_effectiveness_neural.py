"""Actual random native-head CPU proof, separate from mocked policy fixtures.

Explicit opt-in; staged native tokenizer; no downloads/GPU/pretrained claims.
Two independently reset 20-update rectangle memorization controls reproduce the
historical native audit. They establish learnability, not ARC generalization.
"""
import json
import os
from pathlib import Path
import resource
import tempfile
import time
import unittest

from tools.arc_learning_agent_20261011.effectiveness import (
    build_panel, evaluate_panel, greedy_scope, _receipt_ok)
from tools.arc_learning_agent_20261011.grid_codec import decode_grid
from tools.arc_learning_agent_20261011.tests.test_effectiveness import sources


@unittest.skipUnless(os.environ.get("ARC_LEARNING_NEURAL_TESTS") == "1", "explicit native CPU proof only")
class EffectivenessNeuralTests(unittest.TestCase):
    def test_real_native_random_negative_and_independent_twenty_step_rectangles(self):
        self.assertEqual(os.environ.get("CUDA_VISIBLE_DEVICES"), "", "GPU must be explicitly disabled")
        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")
        import torch
        torch.set_num_threads(1)
        from tools.arc_learning_agent_20261011.native_model import NativeModel
        from tools.arc_learning_agent_20261011.training import Trainer
        workspace = Path(__file__).resolve().parents[5]
        tokenizer = Path(os.environ.get("ARC_NATIVE_TOKENIZER_PATH", str(workspace / "learning-agent-repair3-20261011/tokenizer-assets")))
        self.assertTrue((tokenizer / "tokenizer.json").is_file(), "real staged native tokenizer is required")
        started = time.monotonic()
        native = NativeModel.from_config({"tiny_cpu": True, "tokenizer_path": str(tokenizer),
            "tiny_hidden_size": 32, "seed": 123, "do_sample": True, "temperature": .7, "top_p": .8})
        trainer = Trainer(native, {"tiny_cpu": True, "lora_rank": 16, "lora_alpha": 32,
            "learning_rate": .003, "gradient_checkpointing": True, "seed": 7})
        initial = trainer.snapshot("independent-rectangle-initial")
        old_config = dict(native.config)
        tasks, manifest = sources()
        panel = build_panel(tasks, manifest, dev_tasks=2, seed=0)
        from tools.arc_learning_agent_20261011.budget import WorkLedger
        from tools.arc_learning_agent_20261011.metering import MeteredModel
        with tempfile.TemporaryDirectory() as temporary:
            ledger = WorkLedger(Path(temporary) / "physical.jsonl")
            negative = evaluate_panel(MeteredModel(native, ledger), panel, time.monotonic() + 30,
                                      manifest=manifest, max_new_tokens=12)
            self.assertEqual(ledger.used["generation_calls"], negative["physical"]["generation_calls"])
            self.assertEqual(ledger.used["scoring_forwards"], negative["physical"]["scoring_calls"])
            self.assertFalse(ledger.pending)
            self.assertEqual(negative["physical"]["ledger_charged_delta"]["generation_calls"], 4)
            self.assertEqual(negative["physical"]["ledger_charged_delta"]["scoring_forwards"], 4)
            self.assertFalse(negative["physical"]["ledger_pending"])
            self.assertTrue(all(row["generation"]["physical_event_id"] and row["score"]["physical_event_id"]
                                for row in negative["rows"]))
        self.assertFalse(negative["gate_pass"])
        self.assertFalse(negative["eligible_for_public_run"])
        self.assertEqual(negative["evidence"], "tiny_cpu_neural_not_pretrained")
        self.assertEqual(negative["exact"], 0)
        self.assertEqual(native.config, old_config)
        messages = [{"role": "user", "content": "Rectangle A"}]
        proof = {"scope": "independent explicitly memorized synthetic rectangles; not held-out generalization",
                 "native_vocabulary_rows": native.vocab_size,
                 "tokenizer_sha256": native.constraint.tokenizer_sha256,
                 "random_panel": {key: negative[key] for key in ("exact", "denominator", "gate_pass", "physical")},
                 "controls": []}
        self.assertEqual(native.vocab_size, 100352)
        for target in ("12\n34", "567\n890"):
            trainer.restore(initial)
            trainer._make_optimizer()
            prepared = trainer._prepared({"messages": messages, "completion": target})
            first = None
            for _ in range(20):
                step = trainer._step(prepared)
                first = step["loss"] if first is None else first
            with greedy_scope(native):
                result = native.generate(messages, kind="grid", seed=0, max_new_tokens=12, deadline=time.monotonic() + 15)
                score = native.score_completion(messages, target, deadline=time.monotonic() + 15)
            self.assertTrue(_receipt_ok(result, generation=True, cap=12), result)
            self.assertTrue(result["valid"], result)
            self.assertEqual(result["text"], target, result)
            self.assertEqual(decode_grid(result["text"]), decode_grid(target))
            self.assertTrue(_receipt_ok(score, generation=False), score)
            self.assertEqual(result["full_vocabulary_rows"], 100352)
            self.assertGreater(result["forward_calls"], 0)
            self.assertEqual(native.config, old_config)
            proof["controls"].append({"target": target, "steps": 20, "initial_loss": first,
                "last_loss": step["loss"], "exact": True, "generation": result, "score": score,
                "target_exposure": "explicitly trained on this exact prompt/completion; memorization learnability only"})
        proof.update(elapsed_seconds=time.monotonic() - started,
                     max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        self.assertLess(proof["elapsed_seconds"], 300)
        self.assertLess(proof["max_rss_kib"], 2 * 1024 * 1024)
        native.close()
        print("NATIVE_EFFECTIVENESS_PROOF=" + json.dumps(proof, sort_keys=True), flush=True)


if __name__ == "__main__":
    unittest.main()

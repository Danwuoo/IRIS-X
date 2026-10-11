"""Real tiny neural tests. No production weight load, network, or CUDA calls."""
import importlib.util
import math
import os
from pathlib import Path
import time
import tempfile
import unittest
from unittest import mock

from tools.arc_learning_agent_20261011.native_model import NativeModel, audit_tokenizer_assets

NEURAL_AVAILABLE = importlib.util.find_spec("torch") is not None and importlib.util.find_spec("transformers") is not None
TOKENIZER_PATH = Path(os.environ.get("ARC_NATIVE_TOKENIZER_PATH", str(Path(__file__).resolve().parents[4] / "tokenizer-assets")))


@unittest.skipUnless(NEURAL_AVAILABLE, "explicit CPU neural environment required")
class NativeNeuralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(1)
        cls.torch = torch

    def setUp(self):
        self.native = NativeModel.from_config({"tiny_cpu": True, "do_sample": False, "seed": 123})
        self.messages = [{"role": "user", "content": "0"}]

    def tearDown(self):
        self.native.close()

    def test_exact_full_head_nll_matches_manually_shifted_ce(self):
        import torch.nn.functional as F
        torch = self.torch
        row = self.native.prepare_completion(self.messages, "12\n34")
        ids = torch.tensor([row["input_ids"]])
        self.native.model.eval()
        with torch.no_grad():
            logits = self.native.model(ids[:, :-1], use_cache=False).logits[0]
            target = ids[0, row["prompt_tokens"]:]
            expected = float(F.cross_entropy(logits[row["prompt_tokens"] - 1:].float(), target, reduction="sum"))
        self.native.model.train()
        receipt = self.native.score_completion(self.messages, "12\n34", deadline=time.monotonic() + 20)
        self.assertTrue(receipt["valid"], receipt)
        self.assertAlmostEqual(receipt["nll_sum"], expected, places=5)
        self.assertEqual(receipt["token_count"], 6)
        self.assertEqual(receipt["completion_token_ids"][-1], 128)
        self.assertEqual(receipt["forward_input_tokens"], len(row["input_ids"]) - 1)
        self.assertEqual(receipt["input_tokens"], receipt["forward_input_tokens"])
        self.assertTrue(self.native.model.training)

    def test_actual_gradient_training_lowers_loss_and_invalidates_fingerprint(self):
        torch = self.torch
        row = self.native.prepare_completion(self.messages, "1")
        before = self.native.score_completion(self.messages, "1", deadline=time.monotonic() + 20)
        optimizer = torch.optim.AdamW(self.native.model.parameters(), lr=0.01)
        self.native.model.train()
        for _ in range(12):
            optimizer.zero_grad()
            loss = self.native.model(input_ids=torch.tensor([row["input_ids"]]),
                                     labels=torch.tensor([row["labels"]]), use_cache=False).loss
            loss.backward()
            optimizer.step()
        after = self.native.score_completion(self.messages, "1", deadline=time.monotonic() + 20)
        self.assertTrue(after["valid"], after)
        self.assertLess(after["nll_sum"], before["nll_sum"])
        self.assertNotEqual(after["adapter_fingerprint"], before["adapter_fingerprint"])
        self.assertFalse(after["adapter_fingerprint_cache_hit"])

    def test_fingerprint_cache_hit_copy_restore_and_wrap_invalidation(self):
        torch = self.torch
        first = self.native.adapter_fingerprint()
        self.assertEqual(first, self.native.adapter_fingerprint())
        self.assertTrue(self.native._last_fingerprint_cache_hit)
        parameter = next(self.native.model.parameters())
        saved = parameter.detach().clone()
        with torch.no_grad():
            parameter.add_(0.1)
        changed = self.native.adapter_fingerprint()
        self.assertNotEqual(changed, first)
        with torch.no_grad():
            parameter.copy_(saved)
        restored = self.native.adapter_fingerprint()
        self.assertEqual(restored, first)
        self.assertFalse(self.native._last_fingerprint_cache_hit)
        self.assertEqual(self.native.fingerprint_rehashes, 3)
        # Replacement tensor with identical bytes must revalidate its identity.
        self.native.model.lm_head.weight = torch.nn.Parameter(self.native.model.lm_head.weight.detach().clone())
        self.native.adapter_fingerprint()
        self.assertFalse(self.native._last_fingerprint_cache_hit)
        self.assertEqual(self.native.fingerprint_rehashes, 4)

    def test_real_neural_generation_strict_eos_and_seeded_receipts(self):
        torch = self.torch
        with torch.no_grad():
            for parameter in self.native.model.parameters():
                parameter.zero_()
        # Uniform logits + greedy chooses digit0, newline, ...; row30 forces EOS.
        receipt = self.native.generate(self.messages, kind="grid", seed=8, max_new_tokens=60,
                                       deadline=time.monotonic() + 20)
        self.assertTrue(receipt["valid"], receipt)
        self.assertEqual(receipt["text"], "\n".join(["0"] * 30))
        self.assertEqual(receipt["output_token_ids"][-1], 128)
        self.assertEqual(receipt["output_tokens"], 60)
        self.assertEqual(receipt["forward_calls"], 60)
        self.assertEqual(receipt["forward_input_tokens"], receipt["input_tokens"] + 59)
        truncated = self.native.generate(self.messages, kind="grid", seed=8, max_new_tokens=3,
                                         deadline=time.monotonic() + 20)
        self.assertFalse(truncated["valid"])
        self.assertEqual(truncated["finish_reason"], "length")
        self.assertEqual(truncated["output_tokens"], 3)
        self.assertNotEqual(truncated["output_token_ids"][-1], 128)

    def test_deadline_context_and_forward_failure_accounting(self):
        expired = self.native.generate(self.messages, kind="grid", seed=0, max_new_tokens=2, deadline=time.monotonic() - 1)
        self.assertFalse(expired["dispatched"])
        self.assertEqual(expired["output_tokens"], 0)
        self.assertIn("adapter_fingerprint", expired)
        self.native.prompt_cap = 2
        excluded = self.native.generate(self.messages, kind="grid", seed=0, max_new_tokens=2, deadline=time.monotonic() + 20)
        self.assertEqual(excluded["finish_reason"], "context_excluded")
        self.assertFalse(excluded["model_forward_started"])
        self.native.prompt_cap = 6144
        with mock.patch.object(self.native.model, "forward", side_effect=RuntimeError("out of memory test")):
            failed = self.native.score_completion(self.messages, "1", deadline=time.monotonic() + 20)
        self.assertFalse(failed["valid"])
        self.assertTrue(failed["dispatched"])
        self.assertEqual(failed["forward_calls"], 1)
        self.assertGreater(failed["forward_input_tokens"], 0)
        self.assertIn("out of memory", failed["error"])
        original = self.native.model.forward
        def slow(*args, **kwargs):
            time.sleep(0.15)
            return original(*args, **kwargs)
        with mock.patch.object(self.native.model, "forward", side_effect=slow):
            timed = self.native.generate(self.messages, kind="grid", seed=0, max_new_tokens=2, deadline=time.monotonic() + 0.10)
        self.assertFalse(timed["valid"])
        self.assertEqual(timed["finish_reason"], "deadline")
        self.assertTrue(timed["dispatched"])
        self.assertEqual(timed["output_tokens"], 0)

    def test_seeded_sampling_does_not_change_global_rng(self):
        torch = self.torch
        self.native.config["do_sample"] = True
        state = torch.get_rng_state().clone()
        first = self.native.generate(self.messages, kind="grid", seed=17, max_new_tokens=8,
                                     deadline=time.monotonic() + 20)
        second = self.native.generate(self.messages, kind="grid", seed=17, max_new_tokens=8,
                                      deadline=time.monotonic() + 20)
        self.assertEqual(first["output_token_ids"], second["output_token_ids"])
        self.assertTrue(torch.equal(state, torch.get_rng_state()))
        self.assertEqual(first["adapter_fingerprint"], second["adapter_fingerprint"])

    def test_post_admission_native_eos_change_is_rejected(self):
        self.native.model.generation_config.eos_token_id = 129
        receipt = self.native.generate(self.messages, kind="grid", seed=0, max_new_tokens=2,
                                       deadline=time.monotonic() + 20)
        self.assertFalse(receipt["valid"])
        self.assertFalse(receipt["dispatched"])
        self.assertIn("EOS", receipt["error"])

    def test_exported_synthetic_tokenizer_reloads_without_native_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            self.native.tokenizer.save_pretrained(directory)
            with mock.patch("transformers.AutoTokenizer.from_pretrained") as production_loader:
                restored = NativeModel.from_config({"tiny_cpu": True, "tokenizer_path": directory,
                                                    "seed": 123, "do_sample": False})
                production_loader.assert_not_called()
            try:
                self.assertEqual(restored.tokenizer.get_vocab(), self.native.tokenizer.get_vocab())
                self.assertEqual(restored.prepare_completion(self.messages, "1"),
                                 self.native.prepare_completion(self.messages, "1"))
                original = self.native.score_completion(self.messages, "1", deadline=time.monotonic() + 20)
                reloaded = restored.score_completion(self.messages, "1", deadline=time.monotonic() + 20)
                self.assertTrue(reloaded["valid"], reloaded)
                self.assertEqual(original["nll_sum"], reloaded["nll_sum"])
                self.assertEqual(original["adapter_fingerprint"], reloaded["adapter_fingerprint"])
                self.assertEqual(reloaded["full_vocabulary_rows"], 130)
                self.assertTrue(reloaded["tiny_cpu"])
            finally:
                restored.close()

    def test_production_hardware_gate_precedes_loader(self):
        with mock.patch("tools.arc_next_models.observe_g4_hardware", side_effect=ValueError("G4 gate denied")), \
             mock.patch("tools.arc_next_models.load_candidate") as loader:
            with self.assertRaisesRegex(ValueError, "G4 gate denied"):
                NativeModel.from_config({"enabled": True, "model_path": "/unused", "environment_lock_path": "/unused"})
            loader.assert_not_called()


@unittest.skipUnless(NEURAL_AVAILABLE and TOKENIZER_PATH.is_dir(), "authenticated local native tokenizer required")
class AuthenticatedNativeTokenizerTests(unittest.TestCase):
    def test_actual_tokenizer_byte_context_audit(self):
        receipt = audit_tokenizer_assets(TOKENIZER_PATH)
        self.assertEqual(receipt["native_vocabulary_rows"], 100352)
        self.assertEqual(receipt["native_eos_ids"], [100257])
        self.assertEqual(receipt["piece_count"], 1125)
        self.assertEqual(receipt["contextual_checks"], 6750)
        self.assertFalse(receipt["model_weights_loaded"])
        self.assertFalse(receipt["finite_solution_inventory"])

    def test_actual_native_tokenizer_and_full_100352_neural_head(self):
        import torch
        torch.set_num_threads(1)
        native = NativeModel.from_config({"tiny_cpu": True, "tokenizer_path": str(TOKENIZER_PATH),
                                          "tiny_hidden_size": 8, "seed": 3})
        messages = [{"role": "user", "content": "0"}]
        rendered, prompt = native._prompt(messages)
        self.assertTrue(rendered.endswith("<think></think>"))
        self.assertFalse(rendered.endswith("<think>\n"))
        row = native.prepare_completion(messages, "01\n23")
        self.assertEqual(row["input_ids"][-1], 100257)
        self.assertEqual(native.constraint.validate_completion(row["input_ids"][len(prompt):]), "01\n23")
        receipt = native.score_completion(messages, "01\n23", deadline=time.monotonic() + 30)
        self.assertTrue(receipt["valid"], receipt)
        self.assertEqual(receipt["full_vocabulary_rows"], 100352)
        self.assertEqual(native.model.get_output_embeddings().weight.shape[0], 100352)
        self.assertGreater(receipt["mean_nll"], 10.0)  # Random full head; compact16 would be about2.8.
        self.assertEqual(receipt["token_count"], 4)  # 01, newline, 23, authenticated nativeEOS.
        native.close()


if __name__ == "__main__":
    unittest.main()

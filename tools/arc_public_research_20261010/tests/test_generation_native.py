"""Opt-in exact native tokenizer and pinned Transformers CPU-logit gates.

Set IRISX_NATIVE_TOKENIZER_DIR to authenticated Dataset-v2 small files. Without
that explicit local path these integration gates are NOT RUN (reported skips).
No weights/model construction or CUDA calls are permitted by these tests.
"""
from contextlib import ExitStack
import builtins
import io
import importlib.util
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from tools.arc_public_research_20261010 import model_provider as mp, finite_trie as ft

ASSETS = os.environ.get("IRISX_NATIVE_TOKENIZER_DIR")


def forbid(*args, **kwargs):
    raise AssertionError("model/weight/CUDA operation forbidden in CPU-only gate")


@unittest.skipUnless(ASSETS, "NOT RUN: explicit pinned native tokenizer materials not configured")
class NativeTokenizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec("transformers") is None:
            raise unittest.SkipTest("NOT RUN: pinned Transformers 5.8.1 unavailable")
        import transformers
        from transformers.models.auto.auto_factory import _BaseAutoModelClass
        with ExitStack() as stack:
            stack.enter_context(patch.object(_BaseAutoModelClass, "from_pretrained", side_effect=forbid))
            if importlib.util.find_spec("torch") is not None:
                import torch
                from transformers.modeling_utils import PreTrainedModel
                stack.enter_context(patch.object(PreTrainedModel, "from_pretrained", side_effect=forbid))
                stack.enter_context(patch.object(torch, "load", side_effect=forbid))
                for name in ("_lazy_init", "is_available", "device_count", "manual_seed", "manual_seed_all", "synchronize"):
                    stack.enter_context(patch.object(torch.cuda, name, side_effect=forbid))
            original_open, original_io_open = builtins.open, io.open
            def guarded(original):
                def call(file, *args, **kwargs):
                    if isinstance(file, (str, bytes, os.PathLike)):
                        value = os.fsdecode(file)
                        if value.endswith((".safetensors", ".bin", ".pt", ".pth")):
                            forbid()
                    return original(file, *args, **kwargs)
                return call
            stack.enter_context(patch.object(builtins, "open", guarded(original_open)))
            stack.enter_context(patch.object(io, "open", guarded(original_io_open)))
            cls.tokenizer, cls.trie, cls.receipt = mp.audit_native_tokenizer_only(
                str(Path(ASSETS).resolve()), str((Path(ASSETS) / "irisx-model-material.json").resolve()))
        receipt_path = os.environ.get("IRISX_NATIVE_QA_RECEIPT")
        if receipt_path:
            target = Path(receipt_path)
            with target.open("x") as stream:
                json.dump(cls.receipt, stream, sort_keys=True, indent=2)
                stream.write("\n")

    def test_native_5965_complete_roundtrip_walk_and_fingerprint(self):
        self.assertEqual(self.receipt["all_inventory_walk_count"], 5965)
        self.assertEqual(self.trie.inventory_sha256, ft.INVENTORY_SHA256)
        self.assertFalse(self.receipt["model_loaded"])
        self.assertFalse(self.receipt["gpu_runtime_verified"])
        self.assertLessEqual(self.receipt["metrics"]["setup_seconds"], 60)
        self.assertLessEqual(self.receipt["metrics"]["nodes"], 1_000_000)
        self.assertLessEqual(self.receipt["metrics"]["rss_delta_bytes"], 512 * 1024 * 1024)
        self.assertLessEqual(self.receipt["metrics"]["max_content_tokens"] + 1, 2048)
        self.assertEqual(self.receipt["native_policy"]["native_eos_ids"], [100257])
        for tokens in self.trie.token_sequences:
            with self.assertRaises(mp.ModelContractError):
                self.trie.validate_completion([*tokens[:-1], 100257])
            with self.assertRaises(mp.ModelContractError):
                self.trie.validate_completion([*tokens, 100257, 100257])

    def test_actual_pinned_cpu_logits_mask_and_sampler(self):
        if importlib.util.find_spec("torch") is None:
            self.skipTest("NOT RUN: CPU torch unavailable for actual Transformers logit integration")
        import torch
        from transformers.generation.logits_process import (
            PrefixConstrainedLogitsProcessor, TemperatureLogitsWarper, TopPLogitsWarper, TopKLogitsWarper)
        trie = self.trie
        for prefix in ((), trie.token_sequences[0][:-1], trie.token_sequences[0]):
            callback = ft.make_prefix_callback(trie, 2, time.monotonic() + 30, ft.OverheadLedger(), prompt_ids=(1, 2))
            processor = PrefixConstrainedLogitsProcessor(callback, num_beams=1)
            input_ids = torch.tensor([[1, 2, *prefix]], dtype=torch.long, device="cpu")
            scores = torch.zeros((1, 100352), device="cpu")
            allowed = trie.allowed_suffix_tokens(prefix)
            output = processor(input_ids, scores)
            finite = torch.isfinite(output[0]).nonzero().flatten().tolist()
            self.assertEqual(finite, allowed)
            for warper in (TemperatureLogitsWarper(.7), TopKLogitsWarper(50), TopPLogitsWarper(.95)):
                output = warper(input_ids, output)
            remaining = torch.isfinite(output[0]).nonzero().flatten().tolist()
            self.assertTrue(remaining); self.assertTrue(set(remaining) <= set(allowed))
        callback = ft.make_prefix_callback(trie, 1, time.monotonic() + 5, ft.OverheadLedger())
        processor = PrefixConstrainedLogitsProcessor(callback, num_beams=1)
        with self.assertRaises(mp.ModelContractError):
            processor(torch.tensor([[1, 100257]]), torch.zeros((1, 100352)))


if __name__ == "__main__":
    unittest.main()

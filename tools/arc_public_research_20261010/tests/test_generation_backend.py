"""No torch installed: a data-only fake session exercises generation wiring."""
from dataclasses import replace
from contextlib import nullcontext
import json
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.arc_public_research_20261010 import model_provider as mp
from tools.arc_public_research_20261010.tests.test_generation_trie import ByteTokenizer, requests, small


class Tensor:
    def __init__(self, rows):
        self.rows = rows
        self.ndim = 2 if rows and type(rows[0]) in (list, tuple) else 1
        self.shape = (len(rows), len(rows[0])) if self.ndim == 2 else (len(rows),)
    def __getitem__(self, key):
        if type(key) is tuple:
            return Tensor(self.rows[key[0]][key[1]])
        return Tensor(self.rows[key])
    def tolist(self):
        return list(self.rows)


class FakeTorch:
    long = "fake-int64"
    def __init__(self):
        self.cuda = SimpleNamespace(manual_seed_all=lambda *a: None, synchronize=lambda: None)
    def tensor(self, rows, **kwargs):
        return Tensor(rows)
    def manual_seed(self, seed):
        pass
    def ones_like(self, ids):
        return "fake-attention"
    def inference_mode(self):
        return nullcontext()


class FakeTokenizer(ByteTokenizer):
    def decode(self, ids, *, skip_special_tokens, clean_up_tokenization_spaces):
        if skip_special_tokens or clean_up_tokenization_spaces:
            raise AssertionError("unexpected decoder normalization")
        return "".join(chr(v) if v < 256 else "<EOS>" for v in ids)


class FakeModel:
    device = "synthetic-cpu-only"
    def __init__(self, suffix):
        self.suffix, self.kwargs, self.error = suffix, None, False
    def generate(self, **kwargs):
        self.kwargs = kwargs
        prefix = list(kwargs["input_ids"].rows[0])
        callback = kwargs.get("prefix_allowed_tokens_fn")
        for token in self.suffix:
            if callback:
                allowed = callback(0, Tensor(prefix))
                if token not in allowed:
                    raise ValueError("synthetic forbidden token")
            if self.error:
                raise ValueError("synthetic zero finite scores")
            prefix.append(token)
        return Tensor([prefix])


class BackendTests(unittest.TestCase):
    def backend(self, suffix=None):
        trie = replace(small(), inventory_sha256=mp.INVENTORY_SHA256)
        backend = mp.G4Backend.__new__(mp.G4Backend)
        backend.trie, backend.overhead = trie, mp.OverheadLedger()
        backend.native_policy = {"pad_token_id": 256}
        backend.generation_config = "synthetic-effective-config"
        backend.environment_sha256 = "e" * 64
        backend._inventory_hashes = frozenset(trie.plan_hashes)
        model = FakeModel([*trie.token_sequences[0], 256] if suffix is None else suffix)
        backend.session = SimpleNamespace(torch=FakeTorch(), tokenizer=FakeTokenizer(), model=model)
        return backend

    def generate(self, backend, request):
        prepared = mp.PreparedCall(request, (11, 12), mp.canonical(backend.decoding_binding(request.decoding_mode)))
        transformers = SimpleNamespace(StoppingCriteria=object, StoppingCriteriaList=list)
        with patch.dict(sys.modules, {"transformers": transformers}):
            return backend.generate(prepared, deadline_monotonic=time.monotonic() + 5)

    def test_effective_defaults_fill_only_missing_fields(self):
        class Config:
            num_beams = None
            forced_eos_token_id = 256
            def _get_default_generation_params(self):
                return {"num_beams": 1, "forced_eos_token_id": None}
            def update(self, *, defaults_only, **values):
                if defaults_only is not True:
                    raise AssertionError("unexpected override")
                for key, value in values.items():
                    if getattr(self, key) is None:
                        setattr(self, key, value)
        original = Config()
        effective = mp._effective_generation_config(original)
        self.assertEqual(effective.num_beams, 1)
        self.assertEqual(effective.forced_eos_token_id, 256)
        self.assertIsNone(original.num_beams)
        with self.assertRaises(mp.ModelContractError):
            mp.validate_generation_config({"num_beams": effective.num_beams,
                                           "forced_eos_token_id": effective.forced_eos_token_id})

    def test_same_generation_kwargs_except_strict_callback(self):
        backend = self.backend(); raw, strict = requests()[:2]
        a = self.generate(backend, raw); kwargs_a = backend.session.model.kwargs
        b = self.generate(backend, strict); kwargs_b = backend.session.model.kwargs
        self.assertNotIn("prefix_allowed_tokens_fn", kwargs_a)
        self.assertIn("prefix_allowed_tokens_fn", kwargs_b)
        for key in set(kwargs_a) - {"input_ids", "stopping_criteria"}:
            self.assertEqual(kwargs_a[key], kwargs_b[key], key)
        self.assertEqual(kwargs_a["input_ids"].rows, kwargs_b["input_ids"].rows)
        self.assertTrue(a["native_eos_complete"]); self.assertTrue(b["native_eos_complete"])
        self.assertEqual(a["text"], b["text"]); self.assertTrue(b["eligibility"]["eligible"])
        self.assertEqual(b["original_decoded_text"], b["text"] + "<EOS>")
        self.assertGreater(b["callback_calls"], 0)
        first = b["callback_calls"]
        c = self.generate(backend, strict)
        self.assertEqual(c["callback_calls"], first)
        self.assertEqual(backend.overhead.calls, first * 2)

    def test_no_eos_means_incomplete_even_if_json_is_parseable(self):
        backend = self.backend()
        backend.session.model.suffix = list(backend.trie.token_sequences[0])
        result = self.generate(backend, requests()[0])
        self.assertEqual(result["finish_reason"], "incomplete")
        self.assertFalse(result["native_eos_complete"])
        self.assertFalse(result["eligibility"]["eligible"])
        self.assertEqual(result["text"], backend.trie.canonical_texts[0])

    def test_forbidden_extra_brace_is_failure_with_partial_ids(self):
        backend = self.backend()
        backend.session.model.suffix = [*backend.trie.token_sequences[0], 125, 256]
        result = self.generate(backend, requests()[1])
        self.assertEqual(result["finish_reason"], "incomplete")
        self.assertIsNotNone(result["failure"])
        self.assertEqual(result["output_token_ids"], list(backend.trie.token_sequences[0]))
        self.assertFalse(result["eligibility"]["eligible"])

    def test_zero_finite_scores_has_no_fallback(self):
        backend = self.backend(); backend.session.model.error = True
        result = self.generate(backend, requests()[1])
        self.assertIn("zero finite", result["failure"]["message"])
        self.assertFalse(result["native_eos_complete"])
        self.assertFalse(result["eligibility"]["eligible"])
        self.assertEqual(result["output_token_ids"], [])

    def test_outside_pool_raw_plan_is_preserved(self):
        text = mp.canonical({"steps": [{"op": "identity"}] * 3})
        backend = self.backend([*text.encode(), 256])
        result = self.generate(backend, requests()[0])
        self.assertTrue(result["native_eos_complete"])
        self.assertEqual(result["text"], text)
        self.assertEqual(result["eligibility"]["status"], "legal_outside_inventory")
        self.assertFalse(result["eligibility"]["eligible"])


if __name__ == "__main__":
    unittest.main()

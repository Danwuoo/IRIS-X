"""Optional CPU engineering controls, never target-model or TPU evidence.

Run with the pinned CPU test dependencies and, optionally,
XLA_FLAGS=--xla_force_host_platform_device_count=8 to exercise the same layout
on eight CPU devices. No pretrained weights, datasets, or network are used.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_adapter import JaxQwen3Adapter, PreflightError, sample_token, validate_config


class ModelAdapterControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import jax
        import jax.numpy as jnp
        import ml_dtypes
        import numpy as np
        import torch
        from jax.sharding import Mesh, NamedSharding, PartitionSpec as P
        from transformers import Qwen3Config, Qwen3ForCausalLM

        if jax.default_backend() != "cpu":
            raise RuntimeError("These engineering controls are CPU-only")
        torch.set_num_threads(2)
        cls.np = np
        cls.results = []
        for tied in (False, True):
            torch.manual_seed(0)
            config = Qwen3Config(hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                                num_attention_heads=16, num_key_value_heads=8, head_dim=8,
                                vocab_size=64, rope_theta=1000000, tie_word_embeddings=tied,
                                attention_bias=False, attention_dropout=0.0,
                                max_position_embeddings=32, sliding_window=None)
            config._attn_implementation = "eager"
            model = Qwen3ForCausalLM(config).to(torch.bfloat16).eval()
            state = model.state_dict()
            # Construct the numerical kernel only; production adapter's TPU gate
            # remains intact and is tested separately below.
            adapter = object.__new__(JaxQwen3Adapter)
            adapter.jax, adapter.jnp, adapter.np = jax, jnp, np
            adapter.context_length, adapter.config = 32, config.to_dict()
            adapter.config["architectures"] = ["Qwen3ForCausalLM"]
            validate_config(adapter.config)
            adapter.mesh = Mesh(np.array(jax.devices()), ("mp",))
            adapter.replicated = NamedSharding(adapter.mesh, P())
            adapter.cache_sharding = NamedSharding(adapter.mesh, P(None, None, "mp", None))

            def array(name):
                return state[name].view(torch.uint16).numpy().view(ml_dtypes.bfloat16)

            specs = {
                "q": ("self_attn.q_proj.weight", lambda a: a.T.reshape(32, 16, 8), P(None, None, "mp", None)),
                "k": ("self_attn.k_proj.weight", lambda a: a.T.reshape(32, 8, 8), P(None, None, "mp", None)),
                "v": ("self_attn.v_proj.weight", lambda a: a.T.reshape(32, 8, 8), P(None, None, "mp", None)),
                "o": ("self_attn.o_proj.weight", lambda a: a.T.reshape(16, 8, 32), P(None, "mp", None, None)),
                "gate": ("mlp.gate_proj.weight", lambda a: a.T, P(None, None, "mp")),
                "up": ("mlp.up_proj.weight", lambda a: a.T, P(None, None, "mp")),
                "down": ("mlp.down_proj.weight", lambda a: a.T, P(None, "mp", None)),
                "input_norm": ("input_layernorm.weight", lambda a: a, P()),
                "post_norm": ("post_attention_layernorm.weight", lambda a: a, P()),
                "q_norm": ("self_attn.q_norm.weight", lambda a: a, P()),
                "k_norm": ("self_attn.k_norm.weight", lambda a: a, P()),
            }
            adapter.weights = {
                key: jax.device_put(np.stack([transform(array(f"model.layers.{i}.{suffix}"))
                                              for i in range(2)]), NamedSharding(adapter.mesh, spec))
                for key, (suffix, transform, spec) in specs.items()}
            adapter.embedding = jax.device_put(array("model.embed_tokens.weight"), NamedSharding(adapter.mesh, P("mp", None)))
            adapter.final_norm = jax.device_put(array("model.norm.weight"), adapter.replicated)
            adapter.lm_head = (adapter.embedding.T if tied else jax.device_put(
                array("lm_head.weight").T, NamedSharding(adapter.mesh, P(None, "mp"))))
            adapter._step = jax.jit(adapter._forward, donate_argnums=(5, 6))
            adapter.first_compile_seconds = None
            compile_seconds = adapter.compile()
            keys, values = adapter.empty_cache()
            prompt, output, traces = [1, 2, 3, 4], [], []

            def step(token, position, k, v):
                returned = adapter._compiled(
                    adapter.weights, adapter.embedding, adapter.final_norm, adapter.lm_head,
                    jnp.asarray(token, dtype=jnp.int32), k, v, jnp.asarray(position, dtype=jnp.int32))
                returned[0].block_until_ready()
                return returned

            for i, token in enumerate(prompt):
                logits, keys, values = step(token, i, keys, values)
            for i in range(8):
                traces.append(np.asarray(logits))
                token = int(np.argmax(logits))
                output.append(token)
                if i < 7:
                    logits, keys, values = step(token, len(prompt) + i, keys, values)
            reference, reference_tokens, past = [], [], None
            ids = torch.tensor([prompt])
            with torch.inference_mode():
                for _ in range(8):
                    returned = model(input_ids=ids, past_key_values=past, use_cache=True)
                    values = returned.logits[0, -1].float().numpy()
                    reference.append(values)
                    token = int(np.argmax(values))
                    reference_tokens.append(token)
                    past, ids = returned.past_key_values, torch.tensor([[token]])
            a, b = np.asarray(traces), np.asarray(reference)
            cls.results.append({
                "tied_embeddings": tied, "backend": jax.default_backend(),
                "cpu_device_count": len(jax.devices()), "greedy_token_ids": output,
                "reference_token_ids": reference_tokens,
                "max_absolute_logit_error": float(np.max(np.abs(a - b))),
                "relative_l2_logit_error": float(np.linalg.norm(a - b) / np.linalg.norm(b)),
                "cold_compile_seconds": compile_seconds,
            })
        cls.config = adapter.config
        cls.adapter = adapter
        report_path = os.environ.get("IRISX_ADAPTER_CONTROL_REPORT")
        if report_path:
            Path(report_path).write_text(json.dumps(cls.results, indent=2) + "\n")

    def test_tiny_greedy_parity_tied_and_untied(self):
        for item in self.results:
            self.assertEqual(item["greedy_token_ids"], item["reference_token_ids"])

    def test_tiny_full_logit_bounds_tied_and_untied(self):
        for item in self.results:
            self.assertLessEqual(item["max_absolute_logit_error"], 0.5)
            self.assertLessEqual(item["relative_l2_logit_error"], 0.03)

    def test_unsupported_rope_rejected(self):
        bad = dict(self.config, rope_scaling={"rope_type": "linear", "factor": 2})
        with self.assertRaises(PreflightError):
            validate_config(bad)

    def test_sampling_greedy(self):
        rng = self.np.random.Generator(self.np.random.PCG64(0))
        self.assertEqual(sample_token(self.np.array([0., 100., 0.]), rng, 0, 1), 1)

    def test_sampling_nucleus(self):
        rng = self.np.random.Generator(self.np.random.PCG64(0))
        self.assertEqual(sample_token(self.np.array([0., 100., 0.]), rng, 1, .1), 1)

    def test_sampling_seed_reproducible(self):
        a = self.np.random.Generator(self.np.random.PCG64(0))
        b = self.np.random.Generator(self.np.random.PCG64(0))
        logits = self.np.arange(30) / 20
        self.assertEqual([sample_token(logits, a, .6, .95) for _ in range(10)],
                         [sample_token(logits, b, .6, .95) for _ in range(10)])

    def test_nonfinite_logits_rejected(self):
        rng = self.np.random.Generator(self.np.random.PCG64(0))
        with self.assertRaises(PreflightError):
            sample_token(self.np.array([0., float("nan")]), rng, 1, 1)

    def test_completion_limit(self):
        with self.assertRaises(ValueError):
            self.adapter.generate([], seed=0, max_new_tokens=4097, qualification_mode=True)

    def test_production_adapter_rejects_cpu(self):
        with self.assertRaises(PreflightError):
            JaxQwen3Adapter("unused-model-directory", {})


if __name__ == "__main__":
    unittest.main(verbosity=2)

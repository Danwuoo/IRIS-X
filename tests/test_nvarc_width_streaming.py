"""Bounded streaming mechanics. Synthetic tests are not official gain evidence."""
from __future__ import annotations
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MISSING = [name for name in ('torch', 'transformers', 'peft', 'tokenizers', 'safetensors')
           if importlib.util.find_spec(name) is None]
if not MISSING:
    import torch
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from tests.test_nvarc_posttrain_engine import tokenizer_fixture
    from tools.nvarc_posttrain_20261017.engine import CompactEngine, OFFICIAL_SHAPES
    from tools.nvarc_width_20261018 import model as reference
    from tools.nvarc_width_streaming_20261019 import bridge


def fixture():
    with torch.random.fork_rng():
        torch.manual_seed(123)
        config = Qwen3Config(vocab_size=16, hidden_size=32, intermediate_size=64,
            num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
            head_dim=16, attention_dropout=0.0, tie_word_embeddings=False,
            bos_token_id=13, eos_token_id=15)
        config._attn_implementation = 'sdpa'
        raw = Qwen3ForCausalLM(config).bfloat16()
    source = bridge.MappingSource({name: p.detach().clone() for name, p in raw.named_parameters()})
    return config, raw, source


def pair(*, chunk_rows=3):
    config, raw, source = fixture()
    config = copy.deepcopy(config)
    dense = CompactEngine.from_base(raw, tokenizer_fixture(), base_identity={'fixture': 'streaming-tiny'},
        device='cpu', test_fixture=True, rank=4, alpha=16, seed=7, adapter_seed=731,
        base_dtype=torch.bfloat16, probability_policy='fp32-backbone-math-v1')
    expected = reference.from_dense(dense, 'width8192')
    result = bridge.build_bounded_model(config, source, target_width=85, rank=4,
        alpha=16, adapter_seed=731, chunk_rows=chunk_rows)
    return expected, result


@unittest.skipIf(bool(MISSING), 'optional ML dependencies missing')
class WidthStreamingCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_every_native_adapter_buffer_and_receipt_hash_matches_reference(self):
        before = torch.random.get_rng_state().clone()
        expected, result = pair()
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        actual = dict(result.model.named_parameters())
        for name, p in expected.model.named_parameters():
            self.assertTrue(torch.equal(p, actual[name]), name)
            self.assertEqual(p.requires_grad, actual[name].requires_grad, name)
        self.assertEqual(len(actual), len(list(expected.model.named_parameters())))
        ab = dict(result.model.named_buffers())
        for name, b in expected.model.named_buffers():
            self.assertTrue(torch.equal(b, ab[name]), name)
        for index, row in enumerate(expected.contract['width_v1']['expansions']):
            self.assertEqual(result.receipt['adapter_mapping'][index]['new_down_A_sha256'], row['new_down_A_sha256'])
            for projection in ('gate_proj', 'up_proj', 'down_proj'):
                self.assertEqual(result.receipt['source_promoted_sha256'][f'model.layers.{index}.mlp.{projection}.weight'],
                                 row['source_parameter_sha256'][projection + '.base_layer.weight'])
        self.assertFalse(result.receipt['full_model_admitted'])

    def test_forward_cached_logits_and_all_trainable_gradients_equal(self):
        expected, result = pair()
        models = (expected.model, result.model)
        ids = torch.tensor([[14, 11, 10, 1, 2, 15, 10, 14, 12, 10]])
        logits, grads, cached = [], [], []
        for model in models:
            model.eval()
            out = model(ids, use_cache=True)
            logits.append(out.logits.detach())
            cached.append(model(torch.tensor([[3]]), past_key_values=out.past_key_values, use_cache=True).logits.detach())
            loss = out.logits.float().square().mean()
            loss.backward()
            grads.append({name: p.grad.clone() for name, p in model.named_parameters() if p.requires_grad})
            self.assertTrue(all(p.grad is None for p in model.parameters() if not p.requires_grad))
        self.assertTrue(torch.equal(*logits))
        self.assertTrue(torch.equal(*cached))
        for name in grads[0]:
            self.assertTrue(torch.equal(grads[0][name], grads[1][name]), name)

    def test_nonzero_B_training_and_checkpoint_recompute_gradients_match(self):
        from tools.nvarc_posttrain_20261017.precision import full_precision_compute
        expected, result = pair()
        models = (expected.model, result.model)
        optimizers = [torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                     lr=2e-5, foreach=False) for model in models]
        ids = torch.tensor([[14, 11, 10, 1, 2, 15, 10, 14, 12, 10]])
        for step in range(2):
            snapshots = []
            for model, optimizer in zip(models, optimizers):
                model.train()
                self.assertTrue(model.is_gradient_checkpointing)
                calls = []
                handle = model.get_base_model().model.layers[0].mlp.register_forward_pre_hook(
                    lambda *_: calls.append('called'))
                optimizer.zero_grad(set_to_none=True)
                with full_precision_compute('cpu'):
                    logits = model(ids, use_cache=False).logits
                    loss = torch.nn.functional.cross_entropy(logits[:, :-1].reshape(-1, 16),
                                                            ids[:, 1:].reshape(-1))
                    loss.backward()
                handle.remove()
                self.assertGreaterEqual(len(calls), 2, 'checkpoint backward did not recompute the MLP')
                grads = {n: p.grad.detach().clone() for n, p in model.named_parameters() if p.requires_grad}
                if step == 1:
                    for name, gradient in grads.items():
                        if '.lora_A.' in name:
                            self.assertTrue(bool(gradient.count_nonzero()), name)
                snapshots.append((logits.detach(), grads))
                optimizer.step()
            self.assertTrue(torch.equal(snapshots[0][0], snapshots[1][0]))
            for name, gradient in snapshots[0][1].items():
                self.assertTrue(torch.equal(gradient, snapshots[1][1][name]), name)
            for (name, p), (other, q) in zip(models[0].named_parameters(), models[1].named_parameters()):
                self.assertEqual(name, other)
                self.assertTrue(torch.equal(p, q), name)

    def test_source_file_stream_and_fresh_adapter_reload_equal(self):
        from safetensors.torch import save_file, load_file
        config, raw, source = fixture()
        del raw
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_file(source.values, root / 'source.safetensors')
            reader = bridge.SafetensorSource(root / 'source.safetensors')
            one = bridge.build_bounded_model(config, reader, target_width=85, rank=4, adapter_seed=731)
            ids = torch.tensor([[14, 11, 10, 1, 15, 10, 14, 12, 10]])
            one.model.train()
            opt = torch.optim.AdamW([p for p in one.model.parameters() if p.requires_grad], lr=2e-5)
            one.model(ids).logits.square().mean().backward()
            opt.step(); opt.zero_grad(set_to_none=True)
            save_file({n: p.detach().clone() for n, p in one.model.named_parameters() if p.requires_grad}, root / 'trainable.safetensors')
            two = bridge.build_bounded_model(config, reader, target_width=85, rank=4, adapter_seed=731)
            state = load_file(root / 'trainable.safetensors')
            with torch.no_grad():
                for name, p in two.model.named_parameters():
                    if p.requires_grad:
                        p.copy_(state[name])
                one.model.eval(); two.model.eval()
                self.assertTrue(torch.equal(one.model(ids).logits, two.model(ids).logits))

    def test_chunk_size_does_not_change_exact_native_or_adapter_bytes(self):
        a, b = pair(chunk_rows=1)[1], pair(chunk_rows=128)[1]
        for (name, p), (other, q) in zip(a.model.named_parameters(), b.model.named_parameters()):
            self.assertEqual(name, other)
            self.assertTrue(torch.equal(p, q), name)

    def test_full_model_cap_fails_before_constructing_or_reading_weights(self):
        config = Qwen3Config(vocab_size=16, **OFFICIAL_SHAPES['2b'], tie_word_embeddings=False)
        with patch('transformers.Qwen3ForCausalLM', side_effect=AssertionError('must not allocate')):
            with self.assertRaisesRegex(ValueError, 'full 2B forbidden'):
                bridge.build_bounded_model(config, object(), target_width=8192)
        plan = bridge.memory_plan(OFFICIAL_SHAPES['2b'], 8192)
        self.assertEqual(plan['final_parameter_bytes'], 7_370_412_032)
        self.assertEqual(plan['whole_dense_source_copy_bytes'], 0)
        self.assertFalse(plan['measured_peak'])

    def test_stale_manifest_same_numel_wrong_shape_rejected(self):
        config, raw, source = fixture()
        del raw
        name = 'model.layers.0.self_attn.q_proj.weight'
        source.values[name] = source.values[name].reshape(16, 64)
        with self.assertRaisesRegex(ValueError, 'actual source shape'):
            bridge.build_bounded_model(config, source, target_width=85, rank=4)

    def test_finite_source_that_overflows_expansion_is_rejected(self):
        value = torch.full((4, 2), torch.finfo(torch.bfloat16).max, dtype=torch.bfloat16)
        with self.assertRaisesRegex(ValueError, 'finite exact paired'):
            bridge._native_destination(value, projection='up_proj', target_width=6, chunk_rows=1)

    def test_direct_placeholder_submodules_and_saved_head_copies_cannot_execute(self):
        import peft
        config, raw, source = fixture()
        del raw
        original = peft.get_peft_model
        blocked = []
        def inspect_placeholder(raw, *args, **kwargs):
            with self.assertRaisesRegex(RuntimeError, 'unmaterialized streaming'):
                raw.model.layers[0].mlp(torch.zeros((1, 1, 32), dtype=torch.bfloat16))
            blocked.append('native_mlp')
            wrapped = original(raw, *args, **kwargs)
            head = wrapped.get_output_embeddings().modules_to_save['default']
            with self.assertRaisesRegex(RuntimeError, 'unmaterialized streaming'):
                head(torch.zeros((1, 1, 32), dtype=head.weight.dtype))
            blocked.append('saved_head_copy')
            return wrapped
        with patch('peft.get_peft_model', side_effect=inspect_placeholder):
            result = bridge.build_bounded_model(config, source, target_width=85, rank=4)
        self.assertEqual(blocked, ['native_mlp', 'saved_head_copy'])
        with torch.no_grad():
            self.assertEqual(tuple(result.model(torch.tensor([[14, 11, 10]])).logits.shape), (1, 3, 16))

    def test_wide_geometry_scratch_accounts_for_down_and_hash_operations(self):
        geometry = dict(hidden_size=32, intermediate_size=100_000, num_hidden_layers=1,
                        num_attention_heads=2, num_key_value_heads=1, head_dim=16)
        plan = bridge.memory_plan(geometry, 200_000, rank=1)
        self.assertGreaterEqual(plan['arithmetic_scratch_allowance_bytes'], 3 * 32 * 100_000 * 4)
        self.assertEqual(plan['arithmetic_scratch_allowance_bytes'],
                         max(plan['per_operation_scratch_bytes'].values()))
        self.assertFalse(plan['runtime_allocator_and_activation_overhead_included'])

    def test_adapter_heavy_geometry_rejected_before_model_or_source_access(self):
        config = Qwen3Config(vocab_size=16, hidden_size=64, intermediate_size=500_000,
            num_hidden_layers=1, num_attention_heads=1, num_key_value_heads=1,
            head_dim=64, tie_word_embeddings=False)
        with patch('transformers.Qwen3ForCausalLM', side_effect=AssertionError('must not allocate')):
            with self.assertRaisesRegex(ValueError, 'final/peak tensor allocation cap'):
                bridge.build_bounded_model(config, object(), target_width=500_001, rank=64)

    def test_excessive_module_count_and_invalid_geometry_rejected_before_build(self):
        config = Qwen3Config(vocab_size=16, hidden_size=2, intermediate_size=4,
            num_hidden_layers=5, num_attention_heads=1, num_key_value_heads=1,
            head_dim=2, tie_word_embeddings=False)
        with patch('transformers.Qwen3ForCausalLM', side_effect=AssertionError('must not allocate')):
            with self.assertRaisesRegex(ValueError, 'bounded prototype layer count'):
                bridge.build_bounded_model(config, object(), target_width=6, rank=1)
        config.num_hidden_layers = 100_000_000
        with patch.object(bridge, '_geometry', side_effect=AssertionError('must not enumerate shapes')), \
             patch.object(bridge.copy, 'deepcopy', side_effect=AssertionError('must not deepcopy')):
            with self.assertRaisesRegex(ValueError, 'bounded prototype layer count'):
                bridge.build_bounded_model(config, object(), target_width=6, rank=1)
        geometry = dict(hidden_size=32, intermediate_size=64, num_hidden_layers=1,
                        num_attention_heads=2, num_key_value_heads=0, head_dim=16)
        with self.assertRaisesRegex(ValueError, 'positive integer Qwen3 geometry'):
            bridge.memory_plan(geometry, 85, rank=4)

    def test_wrong_source_and_nonfinite_fail_closed_preserving_rng(self):
        config, raw, source = fixture()
        del raw
        source.manifest.pop('model.norm.weight')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            bridge.build_bounded_model(config, source, target_width=85, rank=4)
        config, raw, source = fixture()
        del raw
        source.values['model.norm.weight'][0] = float('nan')
        before = torch.random.get_rng_state().clone()
        with self.assertRaisesRegex(ValueError, 'finite BF16'):
            bridge.build_bounded_model(config, source, target_width=85, rank=4)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))


if __name__ == '__main__':
    unittest.main()

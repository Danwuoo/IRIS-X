"""Synthetic CPU controls for untrained capacity, not model-quality evidence."""
from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

_MISSING = [name for name in ("torch", "transformers")
            if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from tools.nvarc_capacity_20261017.prototype import (
        ParallelFFNUnits, TwoExpertRoutingControl, count_parameters,
        expand_ffn_width, expand_identity_depth, fold_width_to_native,
        train_only_new_depth, train_only_new_width,
    )


def model():
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(17)
        config = Qwen3Config(vocab_size=16, hidden_size=32, intermediate_size=64,
            num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
            head_dim=16, attention_dropout=0.0, tie_word_embeddings=False,
            bos_token_id=13, eos_token_id=15)
        config._attn_implementation = "eager"
        return Qwen3ForCausalLM(config).double().eval()


def ids():
    return torch.tensor([[14, 11, 10, 2, 4, 15, 14, 12, 10, 3, 5, 15]])


def loss(m):
    return m(input_ids=ids(), labels=ids(), use_cache=False).loss


@unittest.skipIf(bool(_MISSING), "Optional capacity CPU dependencies missing: " + ", ".join(_MISSING))
class CapacityControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def assert_logits(self, left, right, *, exact=False):
        torch.testing.assert_close(left, right, rtol=0 if exact else 1e-11,
                                   atol=0 if exact else 1e-11)

    def test_depth_initial_function_and_cache_indices(self):
        m = model()
        old_blocks = list(m.model.layers)
        old_state = {k: v.clone() for k, v in m.state_dict().items()}
        with torch.no_grad():
            baseline = m(ids(), use_cache=False).logits
        base_parameters = count_parameters(m)
        receipt = expand_identity_depth(m, after_layers=(0, 1))
        self.assertEqual(receipt["added_layers"], [1, 3])
        self.assertEqual(m.config.num_hidden_layers, 4)
        self.assertEqual(m.config.layer_types, ["full_attention"] * 4)
        self.assertFalse(receipt["cache_and_optimizer_reuse_allowed"])
        self.assertFalse(receipt["capability_gain_established"])
        self.assertEqual(count_parameters(m), base_parameters + sum(
            p.numel() for b in old_blocks for p in b.parameters()))
        for i, block in enumerate(m.model.layers):
            self.assertEqual(block.self_attn.layer_idx, i)
            self.assertIs(block.self_attn.config, m.config)
            self.assertIs(block.mlp.config, m.config)
        for old_index, new_index in ((0, 0), (1, 2)):
            self.assertIs(m.model.layers[new_index], old_blocks[old_index])
            for name, value in old_blocks[old_index].state_dict().items():
                self.assertTrue(torch.equal(value, old_state[f"model.layers.{old_index}.{name}"]))
        with torch.no_grad():
            expanded = m(ids(), use_cache=False).logits
            first = m(ids()[:, :6], use_cache=True)
            second = m(ids()[:, 6:], past_key_values=first.past_key_values, use_cache=True)
        self.assert_logits(baseline, expanded, exact=True)
        self.assertEqual(len(first.past_key_values.layers), 4)
        self.assert_logits(expanded[:, 6:], second.logits)

    def test_depth_gradient_wakeup_and_frozen_originals(self):
        m = model()
        receipt = expand_identity_depth(m, after_layers=(0,))
        expected = count_parameters(m.model.layers[1])
        self.assertEqual(train_only_new_depth(m, receipt, include_compact_heads=False), expected)
        frozen = {k: p.detach().clone() for k, p in m.named_parameters() if not p.requires_grad}
        new = m.model.layers[1]
        optimizer = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],
                                      lr=0.01, weight_decay=0.1)
        loss(m).backward()
        for projection in (new.self_attn.o_proj, new.mlp.down_proj):
            self.assertGreater(projection.weight.grad.abs().sum().item(), 0)
        for projection in (new.self_attn.q_proj, new.self_attn.k_proj,
                           new.self_attn.v_proj, new.mlp.gate_proj, new.mlp.up_proj):
            self.assertEqual(projection.weight.grad.abs().sum().item(), 0)
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        loss(m).backward()
        for projection in (new.self_attn.q_proj, new.self_attn.k_proj,
                           new.self_attn.v_proj, new.mlp.gate_proj, new.mlp.up_proj):
            self.assertGreater(projection.weight.grad.abs().sum().item(), 0)
        for name, value in frozen.items():
            self.assertTrue(torch.equal(dict(m.named_parameters())[name], value), name)

    def test_depth_native_checkpoint_roundtrip(self):
        m = model()
        expand_identity_depth(m, after_layers=(0, 1))
        with tempfile.TemporaryDirectory() as tmp:
            m.save_pretrained(tmp)
            restored = Qwen3ForCausalLM.from_pretrained(tmp, local_files_only=True,
                dtype=torch.float64, attn_implementation="eager").eval()
        with torch.no_grad():
            self.assert_logits(m(ids()).logits, restored(ids()).logits, exact=True)
        self.assertEqual(restored.config.num_hidden_layers, 4)
        self.assertEqual([b.self_attn.layer_idx for b in restored.model.layers], list(range(4)))

    def test_depth_invalid_requests_do_not_mutate(self):
        for after in ((), (True,), (-1,), (2,), (1, 0), (0, 0)):
            with self.subTest(after=after):
                m = model()
                original = copy.deepcopy(m.state_dict())
                with self.assertRaises(ValueError):
                    expand_identity_depth(m, after_layers=after)
                self.assertEqual(m.config.num_hidden_layers, 2)
                for name, tensor in original.items():
                    self.assertTrue(torch.equal(m.state_dict()[name], tensor))

    def test_depth_scope_rejects_wrong_model_receipt_and_invalid_metadata_atomically(self):
        a, b = model(), model()
        ra = expand_identity_depth(a, after_layers=(0,))
        rb = expand_identity_depth(b, after_layers=(1,))
        before = [p.requires_grad for p in b.parameters()]
        for receipt in (ra, {**rb, "added_layers": [1, 999]},
                        {**rb, "layout": list(reversed(rb["layout"]))}):
            with self.assertRaises(ValueError):
                train_only_new_depth(b, receipt)
            self.assertEqual([p.requires_grad for p in b.parameters()], before)
        self.assertGreater(train_only_new_depth(b, rb), 0)
        self.assertFalse(any(p.requires_grad for p in b.model.layers[1].parameters()))
        self.assertTrue(all(p.requires_grad for p in b.model.layers[2].parameters()))

    def test_scope_rejects_pending_gradients_before_mutating_flags(self):
        for kind in ("depth", "width"):
            with self.subTest(kind=kind):
                m = model()
                if kind == "depth":
                    receipt = expand_identity_depth(m, after_layers=(0,))
                    scope = lambda: train_only_new_depth(m, receipt, include_compact_heads=False)
                else:
                    expand_ffn_width(m, intermediate_size=80)
                    scope = lambda: train_only_new_width(m, include_compact_heads=False)
                loss(m).backward()
                flags = [p.requires_grad for p in m.parameters()]
                with self.assertRaises(ValueError):
                    scope()
                self.assertEqual([p.requires_grad for p in m.parameters()], flags)
                m.zero_grad(set_to_none=True)
                scope()
                frozen = {k: p.detach().clone() for k, p in m.named_parameters() if not p.requires_grad}
                optimizer = torch.optim.AdamW(m.parameters(), lr=0.01, weight_decay=0.1)
                loss(m).backward()
                optimizer.step()
                for name, value in frozen.items():
                    self.assertTrue(torch.equal(dict(m.named_parameters())[name], value), name)

    def test_composed_transforms_and_oversized_allocation_rejected(self):
        m = model()
        expand_identity_depth(m, after_layers=(0,))
        with self.assertRaises(ValueError):
            expand_identity_depth(m, after_layers=(0,))
        with self.assertRaises(ValueError):
            expand_ffn_width(m, intermediate_size=80)
        with patch("tools.nvarc_capacity_20261017.prototype.ParallelFFNUnits") as allocation:
            with self.assertRaises(ValueError):
                expand_ffn_width(model(), intermediate_size=10_000_000)
            allocation.assert_not_called()

    def test_fresh_cpu_eval_model_is_required(self):
        m = model().train()
        with self.assertRaises(ValueError):
            expand_identity_depth(m, after_layers=(0,))
        m.eval()
        next(m.parameters()).grad = torch.zeros_like(next(m.parameters()))
        with self.assertRaises(ValueError):
            expand_ffn_width(m, intermediate_size=80)

    def test_nonfinite_inherited_weights_fail_before_layout_change(self):
        m = model()
        with torch.no_grad():
            m.model.layers[0].mlp.gate_proj.weight[0, 0] = float("nan")
        old_blocks = list(m.model.layers)
        with self.assertRaises(ValueError):
            expand_identity_depth(m, after_layers=(0,))
        self.assertEqual(list(m.model.layers), old_blocks)
        self.assertEqual(m.config.num_hidden_layers, 2)

    def test_width_initial_function_and_rng_preservation(self):
        m = model()
        old = [b.mlp for b in m.model.layers]
        with torch.no_grad():
            baseline = m(ids(), use_cache=False).logits
        state = torch.random.get_rng_state().clone()
        receipt = expand_ffn_width(m, intermediate_size=80, seed=41)
        self.assertTrue(torch.equal(state, torch.random.get_rng_state()))
        self.assertEqual(receipt["parameters"] - receipt["base_parameters"], 2 * 3 * 32 * 16)
        self.assertFalse(receipt["native_checkpoint_ready"])
        self.assertFalse(receipt["capability_gain_established"])
        for i, layer in enumerate(m.model.layers):
            self.assertIs(layer.mlp.original, old[i])
        with torch.no_grad():
            self.assert_logits(baseline, m(ids(), use_cache=False).logits, exact=True)

    def test_width_gradients_wake_without_weight_decay_on_old_units(self):
        m = model()
        expand_ffn_width(m, intermediate_size=80)
        self.assertEqual(train_only_new_width(m, include_compact_heads=False), 2 * 3 * 32 * 16)
        frozen = {k: p.detach().clone() for k, p in m.named_parameters() if not p.requires_grad}
        optimizer = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],
                                      lr=0.01, weight_decay=0.1)
        loss(m).backward()
        for layer in m.model.layers:
            self.assertGreater(layer.mlp.down_proj.weight.grad.abs().sum().item(), 0)
            self.assertEqual(layer.mlp.gate_proj.weight.grad.abs().sum().item(), 0)
            self.assertEqual(layer.mlp.up_proj.weight.grad.abs().sum().item(), 0)
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        loss(m).backward()
        for layer in m.model.layers:
            self.assertGreater(layer.mlp.gate_proj.weight.grad.abs().sum().item(), 0)
            self.assertGreater(layer.mlp.up_proj.weight.grad.abs().sum().item(), 0)
        for name, value in frozen.items():
            self.assertTrue(torch.equal(dict(m.named_parameters())[name], value), name)

    def test_width_fold_and_native_roundtrip_after_nonzero_update(self):
        m = model()
        expand_ffn_width(m, intermediate_size=80)
        train_only_new_width(m)
        optimizer = torch.optim.SGD([p for p in m.parameters() if p.requires_grad], lr=0.05)
        loss(m).backward()
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        with torch.no_grad():
            before = m(ids(), use_cache=False).logits
        receipt = fold_width_to_native(m)
        self.assertTrue(receipt["numerical_parity_must_be_checked"])
        self.assertTrue(receipt["training_scope_must_be_reconfigured"])
        self.assertTrue(all(not isinstance(b.mlp, ParallelFFNUnits) for b in m.model.layers))
        with torch.no_grad():
            after = m(ids(), use_cache=False).logits
        self.assert_logits(before, after)
        with tempfile.TemporaryDirectory() as tmp:
            m.save_pretrained(tmp)
            restored = Qwen3ForCausalLM.from_pretrained(tmp, local_files_only=True,
                dtype=torch.float64, attn_implementation="eager").eval()
        self.assertEqual(restored.config.intermediate_size, 80)
        with torch.no_grad():
            self.assert_logits(after, restored(ids(), use_cache=False).logits, exact=True)

    def test_invalid_width_and_double_expansion_rejected(self):
        for width in (True, 64, 63, 80.0):
            m = model()
            with self.assertRaises(ValueError):
                expand_ffn_width(m, intermediate_size=width)
            self.assertEqual(m.config.intermediate_size, 64)
        expand_ffn_width(m, intermediate_size=80)
        with self.assertRaises(ValueError):
            expand_identity_depth(m, after_layers=(0,))
        with self.assertRaises(ValueError):
            expand_ffn_width(m, intermediate_size=96)

    def test_normalized_top1_preserves_but_router_has_zero_task_gradient(self):
        original = model().model.layers[0].mlp
        moe = TwoExpertRoutingControl(original, routing="normalized-top1")
        x = torch.randn(2, 6, 32, dtype=torch.float64)
        y = moe(x)
        self.assert_logits(original(x), y, exact=True)
        y.square().sum().backward()
        self.assertEqual(moe.router.weight.grad.abs().sum().item(), 0)
        self.assertGreater(moe.experts[0].down_proj.weight.grad.abs().sum().item(), 0)
        self.assertIsNone(moe.experts[1].down_proj.weight.grad)
        self.assertEqual(count_parameters(moe), 2 * count_parameters(original) + 32 * 2)

    def test_unnormalized_top1_has_router_gradient_but_changes_function(self):
        original = model().model.layers[0].mlp
        moe = TwoExpertRoutingControl(original, routing="unnormalized-top1")
        x = torch.randn(2, 6, 32, dtype=torch.float64)
        y = moe(x)
        self.assert_logits(original(x) * 0.5, y, exact=True)
        self.assertFalse(torch.equal(original(x), y))
        y.square().sum().backward()
        self.assertGreater(moe.router.weight.grad.abs().sum().item(), 0)

    def test_identical_top2_symmetry_then_distinct_expert_gradient(self):
        original = model().model.layers[0].mlp
        moe = TwoExpertRoutingControl(original, routing="soft-top2")
        x = torch.randn(2, 6, 32, dtype=torch.float64)
        y = moe(x)
        self.assert_logits(original(x), y, exact=True)
        y.square().sum().backward()
        self.assertEqual(moe.router.weight.grad.abs().sum().item(), 0)
        torch.testing.assert_close(moe.experts[0].down_proj.weight.grad,
                                   moe.experts[1].down_proj.weight.grad, rtol=0, atol=0)
        moe.zero_grad(set_to_none=True)
        with torch.no_grad():
            moe.experts[1].down_proj.weight.mul_(1.1)
        moe(x).square().sum().backward()
        self.assertGreater(moe.router.weight.grad.abs().sum().item(), 0)

    def test_routing_control_is_bounded(self):
        original = model().model.layers[0].mlp
        with self.assertRaises(ValueError):
            TwoExpertRoutingControl(original, routing="guess")
        moe = TwoExpertRoutingControl(original, routing="soft-top2")
        with self.assertRaises(ValueError):
            moe(torch.zeros(513, 32, dtype=torch.float64))
        with self.assertRaises(ValueError):
            TwoExpertRoutingControl(torch.nn.Linear(512, 2048), routing="soft-top2")


if __name__ == "__main__":
    unittest.main()

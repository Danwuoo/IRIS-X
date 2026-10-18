"""Real tiny-Qwen architecture/gradient/checkpoint tests, not official GPU scores."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

_MISSING = [name for name in ('torch', 'transformers', 'peft', 'pydantic', 'tokenizers', 'safetensors')
            if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from tools.nvarc_capacity_20261018 import model as c
    from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY, full_precision_execution_contract
    from tools.nvarc_posttrain_20261017.engine import FatalUpdateError
    from tools.arc2_goal_sprint_20261017.model import adapter_state, state_digest, make_optimizer
    from tests.test_nvarc_posttrain_engine import tiny_engine, example, origin, pin


def dense():
    return tiny_engine(dtype=torch.bfloat16, probability_policy=FP32_BACKBONE_POLICY)


def engine(treatment='baseline'):
    return c.from_dense(dense(), treatment, fixture_layers=(0,))


@unittest.skipIf(bool(_MISSING), 'optional CPU capacity dependencies missing: ' + ', '.join(_MISSING))
class CapacityV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_official_geometry_counts_no_model_allocation(self):
        expected = {
            'baseline': (1409475584, 69795840, 1479271424, 1479205888),
            'depth32': (1610819584, 79757312, 1690576896, 1690511360),
            'moe4_top2': (1862460416, 88702976, 1951163392, 1636525056),
        }
        for treatment, counts in expected.items():
            a = c.official_accounting(treatment)
            self.assertEqual(tuple(a[k] for k in ('frozen_parameters', 'trainable_parameters',
                'total_resident_parameters', 'potentially_active_parameters_per_token')), counts)
            self.assertEqual(a['resident_parameter_bytes_fp32'], 4 * counts[2])
            self.assertIsNone(a['actual_wall_seconds'])
            self.assertIsNone(a['actual_peak_memory_bytes'])
            self.assertFalse(a['equal_compute_claimed'])
        self.assertEqual(c.official_accounting('moe4_top2')['router_parameters'], 32768)
        self.assertLess(c.official_accounting('moe4_top2')['linear_forward_flops_per_token'],
                        c.official_accounting('depth32')['linear_forward_flops_per_token'])

    def test_source_value_mapping_geometry_precision_and_initial_function(self):
        for treatment in c.TREATMENTS:
            d = dense()
            before = c._digest(dict(d.model.named_parameters()))
            e = c.from_dense(d, treatment, fixture_layers=(0,))
            receipt = e.contract['capacity_v2']
            self.assertEqual(receipt['inherited_source_and_adapter_sha256'], before)
            self.assertEqual(c._digest(c._source_values(e.model, receipt['layout'], treatment, (0,))), before)
            self.assertEqual(sum(p.numel() for p in e.model.parameters()), receipt['accounting']['total_resident_parameters'])
            self.assertEqual(sum(p.numel() for p in e.parameters), receipt['accounting']['trainable_parameters'])
            self.assertEqual(e.probability_execution_receipt(), full_precision_execution_contract())
            self.assertIsNone(e.capacity_receipt)  # Never silently changes depth-v1 admission.
            self.assertTrue(e.initial_function_receipt['greedy_tokens_equal'])
            self.assertLessEqual(e.initial_function_receipt['full_and_cached_max_absolute_logit_gap'],
                                 e.initial_function_receipt['predeclared_max_absolute_logit_gap'])
            if treatment != 'moe4_top2':
                self.assertTrue(e.initial_function_receipt['exact_bitwise_preservation'])
            self.assertFalse(receipt['capability_gain_established'])
            e._checkpoint_admission()

    def test_cpu_global_rng_preserved_and_source_adapter_seed_shared(self):
        d = dense()
        state = torch.random.get_rng_state().clone()
        e = c.from_dense(d, 'moe4_top2', fixture_layers=(0,))
        self.assertTrue(torch.equal(state, torch.random.get_rng_state()))
        self.assertEqual(state_digest(adapter_state(e.model)), state_digest(adapter_state(engine('moe4_top2').model)))
        a = e.model.get_base_model().model.layers[0].mlp
        self.assertFalse(torch.equal(a.experts[0].down_proj.lora_A['default'].weight,
                                     a.experts[1].down_proj.lora_A['default'].weight))
        for expert in a.experts:
            for projection in ('gate_proj', 'up_proj', 'down_proj'):
                module = getattr(expert, projection)
                self.assertEqual(module.lora_B['default'].weight.count_nonzero().item(), 0)
                self.assertFalse(module.base_layer.weight.requires_grad)
                self.assertTrue(module.lora_A['default'].weight.requires_grad)

    def test_sparse_dispatch_never_executes_unselected_experts_and_gradients(self):
        e = engine('moe4_top2')
        moe = e.model.get_base_model().model.layers[0].mlp
        # All positive inputs select exactly experts 0 and 1. No task labels or
        # manufactured rewards are used: this is a forward/backward mechanism.
        with torch.no_grad():
            for index, weight in enumerate((.02, .01, -.01, -.02)):
                moe.router.weight[index].fill_(weight)
        calls = [[] for _ in range(4)]
        hooks = [expert.register_forward_pre_hook(lambda _m, args, i=i: calls[i].append(args[0].shape[0]))
                 for i, expert in enumerate(moe.experts)]
        x = torch.ones(2, 5, 32, requires_grad=True)
        result = moe(x)
        result.square().mean().backward()
        self.assertEqual(calls, [[10], [10], [], []])
        self.assertEqual(moe.last_dispatch['selected_token_expert_pairs'], 20)
        self.assertLess(moe.router.weight.grad.abs().max().item(), 1e-7)
        for i, expert in enumerate(moe.experts):
            b = expert.down_proj.lora_B['default'].weight
            if i < 2:
                self.assertIsNotNone(b.grad)
                self.assertGreater(b.grad.abs().sum().item(), 0)
            else:
                self.assertIsNone(b.grad)
                self.assertIsNone(expert.down_proj.lora_A['default'].weight.grad)
        for hook in hooks:
            hook.remove()
        # Independently reconstruct normalized selected-only mixing.
        with torch.no_grad():
            scores, indices = moe.router(x.reshape(-1, 32)).topk(2, dim=-1)
            weights = scores.softmax(-1)
            self.assertTrue(torch.allclose(weights.sum(-1), torch.ones(10)))
            reference = sum(moe.experts[i](x.reshape(-1, 32)) * weights[:, i:i+1] for i in (0, 1))
        self.assertTrue(torch.equal(result.reshape(-1, 32), reference))

    def test_real_sft_specializes_experts_and_wakes_router(self):
        e = engine('moe4_top2')
        frozen = c._digest({n: p for n, p in e.model.named_parameters() if not p.requires_grad})
        optimizer = make_optimizer(e.model, 1e-3)
        first = e.sft_step(example(), optimizer)
        self.assertTrue(first['updated'])
        first_gradient = next(iter(e.last_router_gradient_norms.values()))
        self.assertLess(first_gradient, 1e-7)
        moe = e.model.get_base_model().model.layers[0].mlp
        self.assertFalse(torch.equal(moe.experts[0].down_proj.lora_B['default'].weight,
                                     moe.experts[1].down_proj.lora_B['default'].weight))
        second = e.sft_step(example(), optimizer)
        self.assertTrue(second['updated'])
        self.assertGreater(next(iter(e.last_router_gradient_norms.values())), 1e-5)
        self.assertEqual(c._digest({n: p for n, p in e.model.named_parameters() if not p.requires_grad}), frozen)
        telemetry = next(iter(e.dispatch_receipt().values()))
        self.assertEqual(telemetry['routing_tokens_including_recompute'], 64)
        self.assertEqual(sum(telemetry['expert_token_attempts']), 128)
        self.assertEqual(telemetry['dead_experts_in_observed_calls'], [])
        self.assertGreater(telemetry['mean_full_router_entropy_nats'], 0)
        self.assertLessEqual(telemetry['mean_full_router_entropy_nats'], 1.386295)
        self.assertFalse(telemetry['balance_loss_added'])
        e._checkpoint_admission()

    def test_depth_new_zero_outputs_wake_second_step_with_original_gqa_rope(self):
        e = engine('depth32')
        added = e.model.get_base_model().model.layers[1]
        original = e.contract['capacity_v2']['base_model_contract']
        self.assertEqual((e.model.config.num_attention_heads, e.model.config.num_key_value_heads), (2, 1))
        self.assertEqual(e.contract['rope_parameters'], original['rope_parameters'])
        self.assertEqual(added.self_attn.layer_idx, 1)
        self.assertEqual(added.self_attn.o_proj.base_layer.weight.count_nonzero().item(), 0)
        self.assertEqual(added.mlp.down_proj.base_layer.weight.count_nonzero().item(), 0)
        optimizer = make_optimizer(e.model, 1e-3)
        row = example()
        logps = e.completion_logps(row['prompt_ids'] + row['completion_ids'], len(row['prompt_ids']))
        (-logps[len(row['prompt_ids']):].mean()).backward()
        self.assertGreater(added.self_attn.o_proj.lora_B['default'].weight.grad.abs().sum().item(), 0)
        self.assertEqual(added.self_attn.q_proj.lora_B['default'].weight.grad.abs().sum().item(), 0)
        e.commit(optimizer)
        logps = e.completion_logps(row['prompt_ids'] + row['completion_ids'], len(row['prompt_ids']))
        (-logps[len(row['prompt_ids']):].mean()).backward()
        self.assertGreater(added.self_attn.q_proj.lora_B['default'].weight.grad.abs().sum().item(), 0)

    def test_real_training_checkpoint_reconstruction_generation_and_size(self):
        for treatment in c.TREATMENTS:
            e = engine(treatment)
            e.sft_step(example(), make_optimizer(e.model, 1e-3))
            with tempfile.TemporaryDirectory() as directory:
                saved = e.save_checkpoint(Path(directory) / treatment, origin=origin())
                restored = engine(treatment)
                restored.load_checkpoint(pin(saved))
                self.assertEqual(state_digest(adapter_state(e.model)), state_digest(adapter_state(restored.model)))
                left = e.generate(example()['prompt_ids'], count=2, max_new_tokens=8, sample=False)
                right = restored.generate(example()['prompt_ids'], count=2, max_new_tokens=8, sample=False)
                self.assertEqual(left, right)
                manifest = json.loads((Path(saved['root']) / 'manifest.json').read_bytes())
                self.assertEqual(manifest['model_contract'], e.contract)
                self.assertEqual(manifest['trainable_contract']['parameter_count'], sum(p.numel() for p in e.parameters))
                size = (Path(saved['root']) / 'trainable_state.safetensors').stat().st_size
                payload = sum(p.numel() * p.element_size() for p in e.parameters)
                self.assertGreaterEqual(size, payload)
                self.assertLess(size, payload + 100000)
                self.assertFalse(manifest['optimizer_resumed'])
                with self.assertRaises(ValueError):
                    engine('depth32' if treatment != 'depth32' else 'baseline').load_checkpoint(pin(saved))

    def test_actual_fresh_sampled_probability_replay_gate(self):
        for treatment in c.TREATMENTS:
            e = engine(treatment)
            report = c.probability_admission(e, example()['prompt_ids'], max_new_tokens=12,
                           deadline=time.time() + 30)
            self.assertTrue(report['passed'], report['error'])
            self.assertFalse(report['cached_replay_performed'])
            for stage in report['replays'].values():
                self.assertLessEqual(stage['metrics']['max_abs_logp_gap'], 1e-5)
            self.assertEqual(e.optimizer_attempts, 0)

    def test_historical_policy_and_reuse_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unused'):
            c.from_dense(tiny_engine(dtype=torch.bfloat16), 'baseline', fixture_layers=(0,))
        d = dense()
        d.sft_step(example(), make_optimizer(d.model, 1e-3))
        with self.assertRaisesRegex(ValueError, 'unused'):
            c.from_dense(d, 'depth32', fixture_layers=(0,))
        with self.assertRaisesRegex(ValueError, 'fresh ordinary'):
            c.from_dense(engine(), 'depth32', fixture_layers=(0,))

    def test_native_bytes_trainable_flags_routing_and_scaling_fail_closed(self):
        changes = (
            lambda e: next(p for p in e.model.parameters() if not p.requires_grad).data.add_(1),
            lambda e: next(p for p in e.model.parameters() if not p.requires_grad).requires_grad_(True),
            lambda e: setattr(e.model.get_base_model().model.layers[0].mlp, 'top_k', 1),
            lambda e: e.model.get_base_model().model.layers[0].self_attn.q_proj.scaling.update(default=1),
            lambda e: setattr(e.model.get_base_model().model.layers[0].input_layernorm, 'variance_epsilon', .1),
            lambda e: e.contract['capacity_v2']['accounting'].update(trainable_parameters=1),
            lambda e: setattr(e.model.get_base_model().model.rotary_emb, 'attention_scaling', 2.0),
            lambda e: e.trainable_inventory.update(rank=16, alpha=32),
        )
        for change in changes:
            e = engine('moe4_top2')
            change(e)
            with self.assertRaises(ValueError):
                e._checkpoint_admission()

    def test_mutated_routing_is_rejected_before_any_inference_or_training_forward(self):
        for action in ('generate', 'logps', 'sft'):
            e = engine('moe4_top2')
            moe = e.model.get_base_model().model.layers[0].mlp
            moe.top_k = 4
            before = e.forward_calls
            row = example()
            with self.assertRaises(ValueError):
                if action == 'generate':
                    e.generate(row['prompt_ids'], max_new_tokens=1)
                elif action == 'logps':
                    e.completion_logps(row['prompt_ids'] + row['completion_ids'], len(row['prompt_ids']))
                else:
                    e.sft_step(row, make_optimizer(e.model, 1e-3))
            self.assertEqual(e.forward_calls, before)
            self.assertEqual(moe.dispatch_calls, 0)

    def test_rope_buffer_mutation_rejected_before_generation(self):
        e = engine('moe4_top2')
        rotary = e.model.get_base_model().model.rotary_emb
        rotary.inv_freq.add_(.1)
        before = e.forward_calls
        with self.assertRaisesRegex(ValueError, 'buffer identity or version'):
            e.generate(example()['prompt_ids'], max_new_tokens=1)
        self.assertEqual(e.forward_calls, before)

    def test_initial_probe_failure_rolls_back_layout_and_values(self):
        for treatment in ('depth32', 'moe4_top2'):
            e = dense()
            before = c._digest(dict(e.model.named_parameters()))
            layers = list(e.model.get_base_model().model.layers)
            real_probe, calls = c._probe, 0
            def broken(model):
                nonlocal calls
                calls += 1
                result = real_probe(model)
                return (result[0] + 1, *result[1:]) if calls == 2 else result
            with patch.object(c, '_probe', side_effect=broken), self.assertRaisesRegex(ValueError, 'preservation'):
                c.from_dense(e, treatment, fixture_layers=(0,))
            self.assertEqual(c._digest(dict(e.model.named_parameters())), before)
            self.assertEqual(list(e.model.get_base_model().model.layers), layers)
            self.assertEqual(e.model.config.num_hidden_layers, 2)
            e._checkpoint_admission()

    def test_official_material_verification_precedes_any_model_load(self):
        with patch.object(c, 'verify_model', side_effect=ValueError('official pin mismatch')) as verify, \
             patch.object(c.CompactEngine, 'load') as load:
            with self.assertRaisesRegex(ValueError, 'pin mismatch'):
                c.load_engine('/no-official-model', 'moe4_top2', device='cpu')
            verify.assert_called_once_with('/no-official-model', '2b')
            load.assert_not_called()

    def test_nonfinite_update_preserves_existing_fatal_abort_policy(self):
        e = engine('moe4_top2')
        optimizer = make_optimizer(e.model, 1e-3)
        e.parameters[0].grad = torch.full_like(e.parameters[0], float('nan'))
        with self.assertRaises(FatalUpdateError):
            e.commit(optimizer)
        with self.assertRaises(FatalUpdateError):
            e.generate(example()['prompt_ids'], max_new_tokens=1)


if __name__ == '__main__':
    unittest.main()

"""Actual tiny-Qwen CPU tests; never evidence of official-weight GPU feasibility."""
from __future__ import annotations

import copy
import hashlib
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
    from tools.nvarc_capacity_20261017 import factory as f
    from tools.nvarc_posttrain_20261017.engine import CompactEngine, adapter_state, make_optimizer, state_digest
    from tools.nvarc_posttrain_20261017.matched_controller import _official_model_contract
    from tests.test_nvarc_capacity_training import base
    from tests.test_nvarc_posttrain_engine import tokenizer_fixture, example, origin, pin


def engine(dtype=None, after=(0,), sample_seed=17):
    return f.from_base_depth(base(dtype), tokenizer_fixture(), base_identity={'fixture': 'tiny-17'},
        after_layers=after, device='cpu', seed=sample_seed, adapter_seed=7, rank=4, alpha=16,
        base_dtype=dtype or torch.float32, test_fixture=True)


@unittest.skipIf(bool(_MISSING), 'Optional capacity dependencies missing: ' + ', '.join(_MISSING))
class CapacityFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_official_accounting_without_allocating_or_claiming_weights(self):
        plan = f._core(_official_model_contract(), f.OFFICIAL_AFTER, 64, 16, 'torch.bfloat16')
        self.assertEqual(plan['base_parameters'], 1409475584)
        self.assertEqual(plan['expanded_parameters'], 1610819584)
        self.assertEqual(plan['added_parameters'], 201344000)
        self.assertEqual(plan['trainable_parameters'], 79757312)
        self.assertEqual(plan['trainable_tensor_count'], 450)
        self.assertEqual(plan['peft_total_parameters'], 1690576896)
        self.assertEqual(plan['expanded_native_tensor_count'], 355)
        self.assertEqual([row['index'] for row in plan['layout'] if row['new']], [7, 15, 23, 31])
        self.assertFalse(plan['scope']['native_added_blocks_trainable'])
        self.assertFalse(plan['scope']['gpu_admitted'])

    def test_actual_fp32_bf16_native_function_cache_and_determinism(self):
        for dtype in (torch.float32, torch.bfloat16):
            with self.subTest(dtype=dtype):
                original = base(dtype)
                before = f._probe(original)
                blocks = list(original.model.layers)
                receipt = f.expand_depth(original, after_layers=(0,), rank=4, test_fixture=True)
                after = f._probe(original)
                self.assertTrue(torch.equal(before[0], after[0]))
                self.assertTrue(torch.equal(before[1], after[1]))
                self.assertEqual((before[3], after[3]), (2, 3))
                self.assertIs(original.model.layers[0], blocks[0])
                self.assertIs(original.model.layers[2], blocks[1])
                self.assertEqual(receipt, f.expand_depth(base(dtype), after_layers=(0,), rank=4, test_fixture=True))
                self.assertEqual(receipt['expanded_parameters'], sum(p.numel() for p in original.parameters()))
                with self.assertRaises(ValueError):
                    f.expand_depth(original, after_layers=(0,), rank=4, test_fixture=True)

    def test_actual_compact_engine_training_frozen_native_and_gradient_wakeup(self):
        e = engine()
        self.assertIs(type(e), CompactEngine)
        frozen = {name: p.detach().clone() for name, p in f._native_named(e.model, peft=True).items()}
        native = e.model.get_base_model().model.layers[1]
        row = example()
        optimizer = make_optimizer(e.model, 0.01)
        logps = e.completion_logps(row['prompt_ids'] + row['completion_ids'], len(row['prompt_ids']))
        (-logps[len(row['prompt_ids']):].mean()).backward()
        self.assertGreater(native.self_attn.o_proj.lora_B['default'].weight.grad.abs().sum().item(), 0)
        self.assertGreater(native.mlp.down_proj.lora_B['default'].weight.grad.abs().sum().item(), 0)
        self.assertEqual(native.self_attn.q_proj.lora_B['default'].weight.grad.abs().sum().item(), 0)
        report = e.commit(optimizer)
        self.assertTrue(report['updated'])
        optimizer.zero_grad(set_to_none=True)
        logps = e.completion_logps(row['prompt_ids'] + row['completion_ids'], len(row['prompt_ids']))
        (-logps[len(row['prompt_ids']):].mean()).backward()
        self.assertGreater(native.self_attn.q_proj.lora_B['default'].weight.grad.abs().sum().item(), 0)
        optimizer.zero_grad(set_to_none=True)
        self.assertTrue(all(torch.equal(p, frozen[n]) for n, p in f._native_named(e.model, peft=True).items()))
        f.validate_capacity_engine(e)

    def test_bf16_same_initial_function_as_dtype_matched_unexpanded_peft(self):
        expanded = engine(torch.bfloat16)
        control = CompactEngine.from_base(base(torch.bfloat16), tokenizer_fixture(),
            base_identity={'fixture': 'tiny-17'}, device='cpu', test_fixture=True, rank=4, alpha=16,
            seed=17, adapter_seed=7, base_dtype=torch.bfloat16, probability_policy='fp32-compact-head-v1')
        ids = torch.tensor([example()['prompt_ids']])
        with torch.no_grad(), expanded.autocast():
            self.assertTrue(torch.equal(control.model(ids, use_cache=False).logits,
                                        expanded.model(ids, use_cache=False).logits))

    def test_real_update_export_restore_and_exact_generation(self):
        e = engine(torch.bfloat16)
        e.sft_step(example(), make_optimizer(e.model, 1e-3))
        with tempfile.TemporaryDirectory() as tmp:
            saved = e.save_checkpoint(Path(tmp) / 'depth', origin=origin())
            manifest = json.loads((Path(saved['root']) / 'manifest.json').read_bytes())
            self.assertEqual(manifest['model_contract']['capacity_receipt'], e.capacity_receipt)
            self.assertEqual(manifest['base_identity'], {'fixture': 'tiny-17'})
            restored = engine(torch.bfloat16)
            restored.load_checkpoint(pin(saved))
            self.assertEqual(state_digest(adapter_state(e.model)), state_digest(adapter_state(restored.model)))
            left = e.generate(example()['prompt_ids'], count=2, max_new_tokens=5, sample=False)
            right = restored.generate(example()['prompt_ids'], count=2, max_new_tokens=5, sample=False)
            self.assertEqual([r['input_ids'] for r in left], [r['input_ids'] for r in right])
            with self.assertRaises(ValueError):
                engine(torch.bfloat16, after=(1,)).load_checkpoint(pin(saved))

    def test_actual_capacity_stable_policy_sampling_and_replay_preflight(self):
        from tools.nvarc_posttrain_20261017.probability_probe import probe
        e = engine(torch.bfloat16)
        before = state_digest(adapter_state(e.model))
        result = probe(e, example()['prompt_ids'], count=2, max_new_tokens=12,
                       deadline=time.time() + 30, seed=31)
        self.assertEqual(result['status'], 'completed')
        self.assertLessEqual(result['cached_max_abs_logp_gap'], .05)
        self.assertLessEqual(result['full_max_abs_logp_gap'], .05)
        self.assertFalse(result['training_authorized'])
        self.assertEqual(state_digest(adapter_state(e.model)), before)
        self.assertEqual(e.optimizer_attempts, 0)
        f.validate_capacity_engine(e)

    def test_receipt_tamper_and_native_mutation_fail_closed(self):
        m = base()
        receipt = f.expand_depth(m, after_layers=(0,), rank=4, test_fixture=True)
        for key, value in (('expanded_parameters', 1), ('trainable_parameters', 1), ('after_layers', [1]),
                           ('scope', {**receipt['scope'], 'native_added_blocks_trainable': True})):
            bad = copy.deepcopy(receipt)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                f.capacity_model_contract(m.config, bad)
        with torch.no_grad():
            m.model.layers[1].mlp.down_proj.weight[0, 0] = 1
        with self.assertRaisesRegex(ValueError, 'digest'):
            f.validate_capacity_base(m, receipt)
        e = engine()
        native = f._native_named(e.model, peft=True)
        native['model.layers.1.mlp.down_proj.weight'].data[0, 0] = 1
        with self.assertRaisesRegex(ValueError, 'content'):
            f.validate_capacity_engine(e)

    def test_reject_extra_trainable_full_new_blocks_and_live_replacement(self):
        e = engine()
        p = f._native_named(e.model, peft=True)['model.layers.1.mlp.down_proj.weight']
        p.requires_grad_(True)
        with self.assertRaisesRegex(ValueError, 'frozen'):
            f.validate_capacity_engine(e)
        e = engine()
        e.model.get_base_model().model.layers[1].mlp.down_proj.base_layer.weight = torch.nn.Parameter(
            e.model.get_base_model().model.layers[1].mlp.down_proj.base_layer.weight.clone(), requires_grad=False)
        with self.assertRaisesRegex(ValueError, 'identity/version'):
            f.validate_capacity_engine(e, check_values=False)

    def test_invalid_geometry_and_recipe_leave_base_unexpanded(self):
        for after in ((), (True,), (2,), (0, 0), (1, 0)):
            m = base()
            before = f._digest(dict(m.named_parameters()))
            with self.subTest(after=after), self.assertRaises(ValueError):
                f.expand_depth(m, after_layers=after, rank=4, test_fixture=True)
            self.assertEqual(m.config.num_hidden_layers, 2)
            self.assertEqual(f._digest(dict(m.named_parameters())), before)
        m = base()
        m.model.layers[0].mlp.down_proj.weight = torch.nn.Parameter(torch.zeros(31, 64))
        with self.assertRaisesRegex(ValueError, 'geometry'):
            f.expand_depth(m, after_layers=(0,), rank=4, test_fixture=True)

    def test_failed_initial_probe_rolls_back_exact_layout(self):
        m = base()
        original = list(m.model.layers)
        before = f._digest(dict(m.named_parameters()))
        real = f._probe
        calls = 0
        def altered(model):
            nonlocal calls
            calls += 1
            result = real(model)
            return (result[0] + 1, *result[1:]) if calls == 2 else result
        with patch.object(f, '_probe', side_effect=altered), self.assertRaisesRegex(ValueError, 'parity'):
            f.expand_depth(m, after_layers=(0,), rank=4, test_fixture=True)
        self.assertEqual(list(m.model.layers), original)
        self.assertEqual([b.self_attn.layer_idx for b in m.model.layers], [0, 1])
        self.assertEqual(m.config.num_hidden_layers, 2)
        self.assertEqual(f._digest(dict(m.named_parameters())), before)
        self.assertFalse(hasattr(m, '_nvarc_capacity_receipt'))

    def test_official_file_verification_precedes_hf_loading(self):
        with patch.object(f, 'verify_model', side_effect=ValueError('official pin mismatch')) as verify, \
                patch('transformers.AutoConfig.from_pretrained') as load, self.assertRaisesRegex(ValueError, 'pin mismatch'):
            f.load_depth_engine('/not-official', device='cpu')
        verify.assert_called_once_with(Path('/not-official'), '2b')
        load.assert_not_called()

    def test_comparison_uses_actual_reported_wall_not_budget_or_gpu_claim(self):
        from tools.nvarc_posttrain_20261017.matched_controls import COUNTERS
        from tools.nvarc_posttrain_20261017.materials import model_pin
        declaration = {'format': 'irisx/depth-gpu-wall-declaration-v1', 'declared_at_epoch': 1.,
            'maximum_relative_wall_gap': .05, 'shared_protocol_sha256': 'a' * 64,
            'data_admission_sha256': 'b' * 64, 'source_sha256': 'c' * 64,
            'adapter_seed': 731, 'probability_policy': 'fp32-compact-head-v1'}
        pin = model_pin('2b')
        identity = {**pin, 'material_identity_sha256': hashlib.sha256(f._canonical(pin)).hexdigest(),
            'verified_parameters': pin['parameters'], 'verified_tensors': 311, 'remote_code_executed': False}
        physical = {key: 0 for key in (*COUNTERS, 'model_forward_attempts', 'model_input_tokens')}
        physical.update(optimizer_attempts=4, optimizer_steps=4, model_forward_attempts=10, forward_calls=10)
        # These are synthetic contract inputs, NOT observations of a GPU run.
        one = {'format': 'irisx/depth-gpu-wall-run-v1', 'treatment': 'baseline-depth28-rslora64',
            'complete': True, 'base_identity': identity,
            'declaration_sha256': hashlib.sha256(f._canonical(declaration)).hexdigest(),
            **{k: declaration[k] for k in ('shared_protocol_sha256', 'data_admission_sha256', 'source_sha256',
                                         'adapter_seed', 'probability_policy')},
            'hardware_identity': 'synthetic fixture', 'started_at_epoch': 2., 'physical': physical,
            'timing': {'scope': 'training-only-exclusive-gpu-wall', 'clock': 'time.monotonic',
                'elapsed_seconds': 100., 'started_monotonic': 1., 'finished_monotonic': 101.,
                'exclusive_device': True, 'synchronized_before': True, 'synchronized_after': True,
                'failed_and_no_signal_work_included': True, 'idle_padding_seconds': 0.},
            'evidence_kind': 'synthetic-contract-test', 'closed_evidence_sha256': 'd' * 64}
        two = {**copy.deepcopy(one), 'treatment': 'identity-depth32-rslora64'}
        result = f.assess_compute_match(one, two, declaration=declaration)
        self.assertFalse(result['compute_matched'])
        self.assertFalse(result['measurement_authenticity_independently_verified'])
        self.assertTrue(all('synthetic' in reason for reason in result['reasons']))
        one['evidence_kind'] = two['evidence_kind'] = 'owned-gpu-measurement'
        result = f.assess_compute_match(one, two, declaration=declaration)
        self.assertTrue(result['compute_matched'])  # Receipt arithmetic only.
        self.assertFalse(result['measurement_authenticity_independently_verified'])
        two['timing'].update(elapsed_seconds=120., finished_monotonic=121.)
        self.assertFalse(f.assess_compute_match(one, two, declaration=declaration)['compute_matched'])
        two['timing'].update(elapsed_seconds=100., finished_monotonic=101., idle_padding_seconds=1.)
        self.assertFalse(f.assess_compute_match(one, two, declaration=declaration)['eligible'])
        two['adapter_seed'] += 1
        with self.assertRaisesRegex(ValueError, 'declaration differs'):
            f.assess_compute_match(one, two, declaration=declaration)


if __name__ == '__main__':
    unittest.main()

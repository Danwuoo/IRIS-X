import json
from dataclasses import replace
import unittest

from tools.arc_next_models import MODELS
from tools.arc_learning_agent_20261011.deployment_profiles import (
    GiB, PROFILES, ModelProfile, get_profile, plan_deployment,
    require_measured_deployment, weight_floor_bytes,
)


def tiny(**kwargs):
    return replace(ModelProfile('tiny', 'synthetic/tiny', None, 1024, 1024,
                                'synthetic', 'UNADMITTED', 2, 8, 4, 16), **kwargs)


class DeploymentProfilesTests(unittest.TestCase):
    def test_existing_identities_reuse_exact_registry(self):
        for key, spec in MODELS.items():
            profile = get_profile(key)
            self.assertEqual((profile.repository, profile.revision, profile.parameters_total),
                             (spec.repository, spec.revision, spec.parameters))
        self.assertTrue(get_profile('qwen3.5-9b').experimental)
        self.assertEqual(get_profile('qwen3.5-9b').attention_layers, 8)

    def test_larger_models_are_not_admitted_or_pinned(self):
        for key in ('qwen3.5-27b', 'qwen3-14b', 'qwen3-32b', 'qwen3-coder-30b-a3b-instruct'):
            p = get_profile(key)
            self.assertEqual(p.admission, 'UNADMITTED')
            self.assertIsNone(p.revision)
            self.assertEqual(p.parameter_evidence, 'rounded_card_estimate')

    def test_payload_floors_use_total_not_active_or_source_dtype(self):
        profile = get_profile('qwen3-coder-30b-a3b-instruct')
        self.assertEqual(profile.parameters_active, 3_300_000_000)
        plan = plan_deployment(profile, precision='w8a8_fp8')
        self.assertEqual(plan['weight_floor_bytes_per_model'], 30_500_000_000)
        self.assertEqual(plan['status'], 'BLOCKED')
        seed = get_profile('seed-coder-8b-reasoning')
        self.assertEqual(weight_floor_bytes(seed.parameters_total, 16), 16_500_924_416)
        self.assertEqual(weight_floor_bytes(3, 4), 2)

    def test_granite_kv_formula(self):
        p = plan_deployment('granite-4.2-8b', batch_size=1, context_tokens=8192)
        self.assertEqual(p['per_gpu_bytes']['attention_kv'], 2 * 40 * 8 * 128 * 8192 * 2)
        self.assertEqual(p['per_gpu_bytes']['attention_kv'], 1.25 * GiB)
        four = plan_deployment('granite-4.2-8b', batch_size=4, context_tokens=8192)
        self.assertEqual(four['per_gpu_bytes']['attention_kv'], 5 * GiB)
        self.assertFalse(p['execution_admitted'])
        self.assertEqual(p['fit_claim'], 'NOT_MEASURED')

    def test_exception_scale_and_replication_arithmetic(self):
        p = plan_deployment(tiny(), precision='w4a16', tensor_parallel=2,
                            high_precision_parameters=128, replicated_parameters=128,
                            scale_group_size=128, scale_bytes_per_group=4,
                            batch_size=1, context_tokens=1,
                            workspace_bytes_per_gpu=0, reserve_bytes_per_gpu=0)
        self.assertEqual(p['per_gpu_bytes']['weights'], 128 * 2 + 448 // 2)
        self.assertEqual(p['per_gpu_bytes']['weight_scales'], 4 * 4)
        self.assertEqual(p['per_gpu_bytes']['attention_kv'], 2 * 2 * 2 * 16 * 2)
        self.assertFalse(p['exception_count_is_assumed'])

    def test_default_quant_exception_is_labeled_assumption(self):
        p = plan_deployment(tiny(), precision='w8a8_fp8')
        self.assertEqual(p['high_precision_parameters'], 154)
        self.assertTrue(p['exception_count_is_assumed'])
        self.assertGreater(p['per_gpu_bytes']['weights'], 1024)

    def test_four_24gib_devices_never_pooled(self):
        single = plan_deployment('qwen3-14b', precision='bf16', tensor_parallel=1)
        sharded = plan_deployment('qwen3-14b', precision='bf16', tensor_parallel=2)
        self.assertEqual(single['status'], 'BLOCKED')
        self.assertEqual(single['per_gpu_capacity_bytes'], 24 * GiB)
        self.assertFalse(single['pooled_memory'])
        self.assertEqual((single['independent_workers'], sharded['independent_workers']), (4, 2))
        self.assertEqual(sharded['per_gpu_bytes']['weights'] * 2, single['per_gpu_bytes']['weights'])
        self.assertEqual(sharded['status'], 'ESTIMATE_ONLY')
        self.assertIn('no NVLink', sharded['interconnect_assumption'])
        self.assertTrue(any('NCCL' in x for x in sharded['measurement_obligations']))

    def test_exact_24gib_edge_blocked(self):
        p = plan_deployment(tiny(), workspace_bytes_per_gpu=0, reserve_bytes_per_gpu=0)
        budget = p['known_bytes_per_gpu']
        edge = plan_deployment(tiny(), workspace_bytes_per_gpu=0, reserve_bytes_per_gpu=24 * GiB-budget)
        self.assertEqual(edge['known_bytes_per_gpu'], 24 * GiB)
        self.assertEqual(edge['status'], 'BLOCKED')
        below = plan_deployment(tiny(), workspace_bytes_per_gpu=0, reserve_bytes_per_gpu=24 * GiB-budget-1)
        self.assertEqual(below['status'], 'ESTIMATE_ONLY')
        self.assertFalse(below['execution_admitted'])

    def test_invalid_tp_and_head_divisibility(self):
        with self.assertRaises(ValueError):
            plan_deployment(tiny(), tensor_parallel=3)
        with self.assertRaises(ValueError):
            plan_deployment(tiny(), tensor_parallel=4, device_count=2)
        p = plan_deployment(tiny(kv_heads=3), tensor_parallel=2)
        self.assertEqual(p['status'], 'BLOCKED')
        self.assertIsNone(p['per_gpu_bytes']['attention_kv'])
        self.assertTrue(any('no implicit KV replication' in b for b in p['blockers']))

    def test_unknown_batch_and_hybrid_state_require_probe(self):
        p = plan_deployment('qwen3.5-9b', batch_size=None)
        self.assertIsNone(p['estimated_bytes_per_gpu'])
        self.assertIsNone(p['per_gpu_bytes']['hybrid_state'])
        self.assertFalse(p['estimate_complete'])
        p = plan_deployment('qwen3.5-9b', hybrid_state_bytes_per_gpu=100)
        self.assertTrue(p['estimate_complete'])
        self.assertEqual(p['per_gpu_bytes']['hybrid_state'], 100)
        with self.assertRaisesRegex(ValueError, 'unadmitted'):
            require_measured_deployment(p)

    def test_fp8_kv_is_separate_from_weight_precision(self):
        bf16 = plan_deployment(tiny(), kv_precision='bf16')
        kv8 = plan_deployment(tiny(), kv_precision='fp8')
        self.assertEqual(bf16['per_gpu_bytes']['weights'], kv8['per_gpu_bytes']['weights'])
        self.assertEqual(bf16['per_gpu_bytes']['attention_kv'], 2 * kv8['per_gpu_bytes']['attention_kv'])
        self.assertIsNone(kv8['per_gpu_bytes']['kv_scales'])
        self.assertFalse(kv8['estimate_complete'])

    def test_precision_contracts_and_unsupported_recipes(self):
        for sm in ((8, 9), (12, 0)):
            p = plan_deployment(tiny(), precision='w8a8_fp8', fp8_recipe='mxfp8', target_sm=sm)
            self.assertEqual(p['status'], 'BLOCKED')
        p = plan_deployment(tiny(), precision='mixed_fp8_training')
        self.assertEqual(p['status'], 'BLOCKED')
        self.assertEqual(p['precision']['weight_bits'], 16)
        self.assertFalse(p['estimate_complete'])
        self.assertIsNone(p['estimated_bytes_per_gpu'])
        for field in ('fp8_weight_copies', 'fp8_scale_and_amax_history', 'trainable_gradients',
                      'master_parameters', 'optimizer_state', 'saved_training_activations'):
            self.assertIsNone(p['per_gpu_bytes'][field])
        p = plan_deployment(tiny(), precision='w8a16')
        self.assertIn('not_w8a8', p['precision']['compute'])

    def test_invalid_numeric_values_rejected(self):
        for kwargs in ({'batch_size': 0}, {'context_tokens': True}, {'high_precision_parameters': False},
                       {'reserve_bytes_per_gpu': -1}, {'replicated_parameters': 1025},
                       {'high_precision_parameters': 1025}, {'device_memory_bytes': float('inf')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                plan_deployment(tiny(), **kwargs)
        json.dumps(plan_deployment(tiny()), allow_nan=False)


if __name__ == '__main__':
    unittest.main()

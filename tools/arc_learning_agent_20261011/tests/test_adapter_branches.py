"""Real tiny PEFT branch isolation; no production weights or CUDA execution."""
import importlib.util
import time
import unittest

from tools.arc_learning_agent_20261011.native_model import NativeModel, NativeModelError


@unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('peft'),
                     'explicit CPU neural environment required')
class AdapterBranchTests(unittest.TestCase):
    def setUp(self):
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        torch.set_num_threads(1)
        self.torch = torch
        self.native = NativeModel.from_config({'tiny_cpu': True, 'do_sample': False, 'seed': 12})
        self.messages = [{'role': 'user', 'content': '0'}]
        self.base_score = self.native.score_completion(self.messages, '12', deadline=time.monotonic() + 20)
        self.native.model = get_peft_model(self.native.model,
            LoraConfig(task_type=TaskType.CAUSAL_LM, r=2, lora_alpha=4, target_modules=['q_proj', 'v_proj']))
        with torch.no_grad():
            for name, value in self.native.model.named_parameters():
                if 'lora_B' in name:
                    value.fill_(0.2)

    def tearDown(self):
        self.native.close()

    def test_frozen_base_equals_original_and_state_survives(self):
        before = {name: value.detach().clone() for name, value in self.native.model.named_parameters()}
        trained = self.native.score_completion(self.messages, '12', deadline=time.monotonic() + 20)
        with self.native.adapter_branch('base'):
            base = self.native.score_completion(self.messages, '12', deadline=time.monotonic() + 20)
            self.assertEqual(base['adapter_execution_mode'], 'base')
            self.assertEqual(base['adapter_fingerprint_tensor_elements'], 0)
            self.assertNotEqual(base['adapter_fingerprint'], trained['adapter_fingerprint'])
            self.assertAlmostEqual(base['nll_sum'], self.base_score['nll_sum'], places=6)
        restored = self.native.score_completion(self.messages, '12', deadline=time.monotonic() + 20)
        self.assertEqual(restored['adapter_execution_mode'], 'trained')
        self.assertEqual(restored['adapter_fingerprint'], trained['adapter_fingerprint'])
        self.assertEqual(restored['nll_sum'], trained['nll_sum'])
        for name, value in self.native.model.named_parameters():
            self.assertTrue(self.torch.equal(value, before[name]))

    def test_failure_and_nested_context_never_leave_base_enabled(self):
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            with self.native.adapter_branch('base'):
                with self.assertRaisesRegex(NativeModelError, 'nested'):
                    with self.native.adapter_branch('trained'):
                        pass
                raise RuntimeError('injected')
        self.assertEqual(self.native._adapter_execution_mode, 'trained')
        self.assertFalse(self.native._branch_context_active)
        self.assertFalse(any(getattr(module, 'disable_adapters', False)
                             for module in self.native.model.modules()
                             if hasattr(module, 'lora_A')))

    def test_missing_peft_and_unknown_mode_fail_closed(self):
        with self.assertRaises(NativeModelError):
            with self.native.adapter_branch('unknown'):
                pass
        bare = NativeModel.from_config({'tiny_cpu': True})
        try:
            with self.assertRaisesRegex(NativeModelError, 'PEFT'):
                with bare.adapter_branch('base'):
                    pass
            self.assertFalse(bare._branch_context_active)
        finally:
            bare.close()


if __name__ == '__main__':
    unittest.main()

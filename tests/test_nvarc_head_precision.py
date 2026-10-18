"""Real tiny-model precision tests; not official-weight GPU validation."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from tools.nvarc_posttrain_20261017.precision_contract import LEGACY_POLICY, FP32_HEAD_POLICY

MISSING = [n for n in ("torch", "transformers", "peft", "tokenizers", "safetensors", "pydantic")
           if importlib.util.find_spec(n) is None]
if not MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine, example, origin, pin
    from tools.nvarc_posttrain_20261017.precision import FP32CompactHead, active_head, install_policy, validate_policy
    from tools.arc2_goal_sprint_20261017.model import adapter_state, state_digest, make_optimizer


@unittest.skipIf(bool(MISSING), "Optional real-model dependencies unavailable: " + ", ".join(MISSING))
class CompactHeadPrecision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def engine(self, policy=FP32_HEAD_POLICY):
        return tiny_engine(dtype=torch.bfloat16, probability_policy=policy)

    def test_installation_preserves_every_parameter_name_identity_value_and_rng(self):
        engine = self.engine(LEGACY_POLICY)
        before = {n: (id(p), p.detach().clone()) for n, p in engine.model.named_parameters()}
        rng = torch.random.get_rng_state().clone()
        install_policy(engine.model, FP32_HEAD_POLICY)
        self.assertTrue(torch.equal(rng, torch.random.get_rng_state()))
        after = dict(engine.model.named_parameters())
        self.assertEqual(set(before), set(after))
        for name, (identity, value) in before.items():
            self.assertEqual(id(after[name]), identity)
            self.assertTrue(torch.equal(after[name], value))
        # A changed module alone cannot masquerade as the original engine policy.
        with self.assertRaisesRegex(ValueError, "computation policy"):
            engine._checkpoint_admission()

    def test_both_generation_and_differentiable_replay_use_fp32_head(self):
        engine = self.engine(); observed = []; backbone = []
        h = active_head(engine.model).register_forward_hook(
            lambda m, a, out: observed.append((out.dtype, torch.is_grad_enabled())))
        projection = engine.model.get_base_model().model.layers[0].self_attn.q_proj
        b = projection.register_forward_hook(lambda m, a, out: backbone.append(out.dtype))
        try:
            rows = engine.generate(example()['prompt_ids'], count=2, max_new_tokens=8,
                                   sample=True, deadline=time.time()+30)
            current = engine.completion_logps(rows[0]['input_ids'], rows[0]['prompt_length'])
            self.assertTrue(current.requires_grad)
            current.sum().backward()
        finally:
            h.remove(); b.remove()
        self.assertTrue(observed and all(dtype == torch.float32 for dtype, _ in observed))
        self.assertTrue(any(not enabled for _, enabled in observed))
        self.assertTrue(any(enabled for _, enabled in observed))
        self.assertTrue(backbone and all(dtype == torch.bfloat16 for dtype in backbone))
        head = active_head(engine.model)
        self.assertTrue(bool(torch.isfinite(head.weight.grad).all()))
        self.assertGreater(head.weight.grad.abs().sum().item(), 0)
        self.assertTrue(all(p.dtype == torch.bfloat16 for p in engine.model.parameters() if not p.requires_grad))

    def test_late_output_cast_cannot_recover_bf16_projection_rounding(self):
        # Exact same weights and input. A common large logit offset is softmax
        # invariant mathematically, but BF16 rounds its sub-unit differences.
        head = torch.nn.Linear(2, 16, bias=False, dtype=torch.float32)
        with torch.no_grad():
            head.weight[:, 0] = 100
            head.weight[:, 1] = torch.arange(16) * .03
        stable = FP32CompactHead(2, 16, bias=False, device='meta')
        stable.weight = head.weight
        x = torch.tensor([[1., 1.]])
        with torch.autocast('cpu', dtype=torch.bfloat16):
            rounded = head(x).float(); actual = stable(x)
        reference = torch.nn.functional.linear(x, head.weight)
        self.assertTrue(torch.equal(actual, reference))
        self.assertGreater((rounded-actual).abs().max().item(), .1)
        self.assertGreater((torch.log_softmax(rounded,-1)-torch.log_softmax(actual,-1)).abs().max().item(), .05)
        self.assertEqual(actual.dtype, torch.float32)

    def test_real_update_export_reload_binds_precision_policy(self):
        engine = self.engine(); before = state_digest(adapter_state(engine.model))
        report = engine.sft_step(example(), make_optimizer(engine.model, 1e-3), deadline=time.time()+30)
        self.assertTrue(report['updated'])
        self.assertNotEqual(before, state_digest(adapter_state(engine.model)))
        with tempfile.TemporaryDirectory() as directory:
            saved = engine.save_checkpoint(Path(directory)/'new', origin=origin())
            manifest = json.loads((Path(saved['root'])/'manifest.json').read_bytes())
            self.assertEqual(manifest['trainable_contract']['probability_policy'], FP32_HEAD_POLICY)
            fresh = self.engine(); restored = fresh.load_checkpoint(pin(saved))
            self.assertEqual(restored['state_sha256'], saved['state_sha256'])
            legacy = self.engine(LEGACY_POLICY); original = state_digest(adapter_state(legacy.model))
            with self.assertRaisesRegex(ValueError, "contract differs"):
                legacy.load_checkpoint(pin(saved))
            self.assertEqual(state_digest(adapter_state(legacy.model)), original)

    def test_legacy_checkpoint_schema_stays_unchanged_and_cannot_load_into_new_policy(self):
        legacy = self.engine(LEGACY_POLICY)
        self.assertNotIn('probability_policy', legacy.trainable_inventory)
        with tempfile.TemporaryDirectory() as directory:
            saved = legacy.save_checkpoint(Path(directory)/'old', origin=origin())
            with self.assertRaisesRegex(ValueError, "contract differs"):
                self.engine().load_checkpoint(pin(saved))

    def test_policy_attribute_is_readonly_and_monkeypatched_forward_is_rejected(self):
        engine = self.engine()
        with self.assertRaises(AttributeError): engine.probability_policy = LEGACY_POLICY
        head = active_head(engine.model)
        head.forward = lambda value: torch.nn.functional.linear(value, head.weight)
        with self.assertRaisesRegex(ValueError, "computation policy"):
            engine._checkpoint_admission()

    def test_unknown_policy_is_rejected_before_adapter_installation(self):
        with self.assertRaisesRegex(ValueError, "probability policy"):
            self.engine('unreviewed')

    def test_real_bf16_probe_binds_all_logits_and_actual_grad_forward(self):
        from tools.nvarc_posttrain_20261017.probability_probe import probe
        from tools.nvarc_posttrain_20261017.precision_contract import stable_probe_admission
        engine = self.engine()
        before = state_digest(adapter_state(engine.model))
        rng = engine.generator.get_state().clone()
        modes = [m.training for m in engine.model.modules()]
        result = probe(engine, example()['prompt_ids'], count=2, max_new_tokens=12, seed=7, deadline=time.time()+30)
        self.assertEqual(result['status'], 'completed', result['error'])
        summary, passed = stable_probe_admission(result, tolerance=.05, count=2)
        self.assertTrue(passed, summary)
        self.assertEqual(set(summary), {'eval_nograd','train_grad'})
        self.assertGreater(result['extra_projection_calls'], 0)
        self.assertEqual(result['work']['total']['forward_successes'], result['engine_counter_deltas']['forward_calls'])
        self.assertEqual(before, state_digest(adapter_state(engine.model)))
        self.assertTrue(torch.equal(rng, engine.generator.get_state()))
        self.assertEqual(modes, [m.training for m in engine.model.modules()])
        self.assertTrue(all(p.grad is None for p in engine.parameters))
        self.assertFalse(result['additional_replays']['train_grad']['backward_validated'])
        json.dumps(result, allow_nan=False)

    def test_strict_extra_path_gate_and_logit_tamper_rejected(self):
        import copy
        from tools.nvarc_posttrain_20261017.probability_probe import probe, _metrics
        from tools.nvarc_posttrain_20261017.precision_contract import stable_probe_admission
        result = probe(self.engine(), example()['prompt_ids'], count=2, max_new_tokens=5, seed=7, deadline=time.time()+30)
        bad = copy.deepcopy(result)
        # A correctly retained but genuinely divergent grad-enabled path is not
        # admitted, even if no-grad and cached paths match. Partial evidence can
        # carry this strict failure without pretending a complete head trace.
        bad['status'] = 'failed'
        stage = bad['additional_replays']['train_grad']
        stage['rows'][0]['full_log_probs'][0] += .1
        a = [v for r in stage['rows'] for v in r['behavior_log_probs']]
        b = [v for r in stage['rows'] for v in r['full_log_probs']]
        stage['metrics'] = _metrics(a,b)
        summary, passed = stable_probe_admission(bad, tolerance=.05, count=2)
        self.assertFalse(passed)
        self.assertGreater(summary['train_grad']['max_abs_logp_gap'], .05)
        bad = copy.deepcopy(result)
        bad['additional_replays']['train_grad']['rows'][0]['behavior_log_probs'][0] += .01
        with self.assertRaisesRegex(ValueError, 'behavior denominator'):
            stable_probe_admission(bad, tolerance=.05, count=2)
        bad = copy.deepcopy(result)
        bad['logit_evidence'][0]['actual_logits'][0][0][0] += 1
        with self.assertRaisesRegex(ValueError, 'same-hidden'):
            stable_probe_admission(bad, tolerance=.05, count=2)

    def test_partial_projection_failure_retains_actual_logits_and_charged_attempts(self):
        from unittest.mock import patch
        from tools.nvarc_posttrain_20261017 import probability_probe as pp
        original = torch.nn.functional.linear
        engine = self.engine()
        head_pointer = active_head(engine.model).weight.data_ptr()
        control_calls = [0]
        def linear(inputs, weight, bias=None):
            # The actual head has its trainable Parameter, controls detach it.
            if weight.data_ptr() == head_pointer and not weight.requires_grad:
                control_calls[0] += 1
                if control_calls[0] == 2:
                    raise RuntimeError('injected legacy projection failure')
            return original(inputs, weight, bias)
        with patch('torch.nn.functional.linear', side_effect=linear):
            result = pp.probe(engine, example()['prompt_ids'], count=2, max_new_tokens=5,
                              seed=7, deadline=time.time()+30)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['extra_projection_attempts'], 2)
        self.assertEqual(result['extra_projection_successes'], 1)
        self.assertEqual(result['extra_projection_calls'], 1)
        self.assertEqual(len(result['logit_evidence']), 1)
        record = result['logit_evidence'][0]
        self.assertIsNotNone(record['actual_logits'])
        self.assertIsNotNone(record['fp32_same_hidden_logits'])
        self.assertIsNone(record['legacy_same_hidden_logits'])
        self.assertEqual(record['error']['type'], 'RuntimeError')
        self.assertEqual(result['work']['generation']['forward_attempts'], 1)
        self.assertEqual(result['engine_counter_deltas']['optimizer_attempts'], 0)

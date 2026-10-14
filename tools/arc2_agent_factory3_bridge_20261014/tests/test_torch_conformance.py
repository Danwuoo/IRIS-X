from dataclasses import replace
import importlib.util
import math
import unittest

from tools.arc2_agent_factory3_bridge_20261014.bridge import compute_loss, prepare_batch
from tools.arc2_agent_factory3_bridge_20261014.fixtures import synthetic_batch

HAS_TORCH = importlib.util.find_spec("torch") is not None


@unittest.skipUnless(HAS_TORCH, "real CPU torch is required; tensor integration NOT RUN")
class TorchConformanceTests(unittest.TestCase):
    def setUp(self):
        import torch
        torch.set_num_threads(1)
        self.torch = torch
        from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.ddis_loss import DDISLoss
        self.DDISLoss = DDISLoss

    def _prepared_replay(self):
        from tools.arc2_agent_factory3_bridge_20261014.proof import baseline_math, synthetic_replay
        batch, context = synthetic_batch()
        prepared = prepare_batch(batch, context)
        logits, replay = synthetic_replay(batch, baseline_math())
        return prepared, logits, replay

    def test_actual_upstream_forward_and_logit_gradient_match_frozen_math(self):
        from tools.arc2_agent_factory3_bridge_20261014.proof import run_proof
        result = run_proof()
        self.assertTrue(result["actual_upstream_DDISLoss_executed"])
        self.assertLessEqual(result["logit_gradient_max_abs_gap"], 1e-7)
        self.assertGreater(result["logit_gradient_norm"], 0)
        self.assertFalse(result["optimizer_executed"])

    def test_forced_support_has_zero_underlying_logit_gradient(self):
        prepared, logits, replay = self._prepared_replay()
        output = compute_loss(prepared, replay)
        grad, = self.torch.autograd.grad(output.loss_unscaled, logits)
        for i, flags in enumerate(prepared.nonforced_masks):
            for j, flag in enumerate(flags):
                if not flag:
                    self.assertEqual(float(grad[i, j].abs().sum()), 0.)

    def test_missing_replay_and_detached_graph_rejected(self):
        prepared, _, replay = self._prepared_replay()
        first = next(iter(replay))
        missing = dict(replay); missing.pop(first)
        with self.assertRaisesRegex(ValueError, "identity set"):
            compute_loss(prepared, missing)
        detached = dict(replay); detached[first] = detached[first].detach()
        with self.assertRaisesRegex(ValueError, "differentiable"):
            compute_loss(prepared, detached)

    def test_disabled_autograd_contexts_fail_closed(self):
        prepared, _, replay = self._prepared_replay()
        for mode in (self.torch.no_grad, self.torch.inference_mode):
            with self.subTest(mode=mode), mode(), self.assertRaisesRegex(ValueError, "active autograd"):
                compute_loss(prepared, replay)

    def test_mutated_sample_and_nonforced_contract_rejected(self):
        prepared, _, replay = self._prepared_replay()
        changed = replace(prepared, nonforced_masks=tuple(tuple(False for _ in m) for m in prepared.nonforced_masks))
        with self.assertRaisesRegex(ValueError, "bridge contract"):
            compute_loss(changed, replay)
        prepared.samples[0].divisor *= 2
        with self.assertRaisesRegex(ValueError, "upstream samples"):
            compute_loss(prepared, replay)

    def test_replay_gap_and_nan_fail_closed(self):
        prepared, _, replay = self._prepared_replay()
        first = next(iter(replay))
        for value in (-1., float("nan"), .1):
            changed = dict(replay)
            changed[first] = changed[first].detach().clone()
            changed[first][1] = value
            changed[first].requires_grad_()
            with self.subTest(value=value), self.assertRaises(ValueError):
                compute_loss(prepared, changed)

    def test_zero_signal_never_executes_upstream_loss(self):
        batch, context = synthetic_batch((0,) * 8)
        prepared = prepare_batch(batch, context)
        with self.assertRaisesRegex(ValueError, "zero-signal"):
            compute_loss(prepared, {})

    def test_direct_upstream_strict_boundaries_and_detached_ratio(self):
        torch = self.torch
        # Choose epsilon from the actual float32 exp result so equality is exact.
        pi = torch.tensor([-1.5, -.5, -1.], requires_grad=True)
        mu = torch.tensor([-1., -1., -1.], requires_grad=True)
        ratios = (pi.detach() - mu.detach()).exp()
        low, high = 1. - float(ratios[0]), float(ratios[1]) - 1.
        advantage = torch.tensor([1., -1., 1.])
        output = self.DDISLoss(eps_low=low, eps_high=high).compute_unpacked(
            log_probs=[pi], completion_mask=[torch.ones(3)], advantages=[advantage],
            divisors=torch.tensor([3.]), gen_log_probs=[mu])
        pi_grad, mu_grad = torch.autograd.grad(output.loss_unscaled, (pi, mu), allow_unused=True)
        torch.testing.assert_close(pi_grad, torch.tensor([0., 0., -1 / 3]))
        self.assertIsNone(mu_grad)
        self.assertAlmostEqual(float(output.metric_states["algo/ddis_mask_rate"].mean()), 2 / 3, places=6)

    def test_direct_upstream_positive_negative_and_prompt_masks(self):
        torch = self.torch
        pi = torch.tensor([-2., -1., -1., -1.], requires_grad=True)
        mu = torch.tensor([-2., -1., -1., -1.], requires_grad=True)
        output = self.DDISLoss(eps_high=.28).compute_unpacked(
            log_probs=[pi], completion_mask=[torch.tensor([0., 1., 1., 1.])],
            advantages=[torch.tensor([9., 1., -1., 0.])], divisors=torch.tensor([3.]), gen_log_probs=[mu])
        gradient, = torch.autograd.grad(output.loss_unscaled, pi)
        torch.testing.assert_close(gradient, torch.tensor([0., -1 / 3, 1 / 3, 0.]))

    def test_actual_upstream_metric_states_merge_without_mean_of_means(self):
        torch = self.torch
        from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.metric_state import MeanMetricState
        def compute(rows):
            return self.DDISLoss(eps_high=.28).compute_unpacked(
                log_probs=[torch.tensor(x, requires_grad=True) for x in rows],
                completion_mask=[torch.ones(len(x)) for x in rows],
                advantages=[torch.ones(len(x)) for x in rows], divisors=torch.ones(len(rows)),
                gen_log_probs=[torch.full((len(x),), -1.) for x in rows])
        rows = [[-1.], [-.9, -1.1], [-1., -1., -1.], [-1.2, -1.1, -.8, -.9]]
        whole, left, right = compute(rows), compute(rows[:1]), compute(rows[1:])
        for name, expected in whole.metric_states.items():
            self.assertIs(type(left.metric_states[name]), MeanMetricState)
            left.metric_states[name].merge_(right.metric_states[name])
            torch.testing.assert_close(left.metric_states[name].mean(), expected.mean())
        bad = MeanMetricState(torch.tensor(1.), torch.tensor(1.), "token")
        with self.assertRaises(ValueError):
            left.metric_states["algo/ratio_mean"].merge_(bad)


if __name__ == "__main__":
    unittest.main()

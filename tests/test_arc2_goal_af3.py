"""CPU contract tests for the live, actual-upstream AF3 adapter (no model load)."""

from dataclasses import replace
import unittest
from unittest.mock import patch

try:
    import torch
    from tools.arc2_goal_sprint_20261017.af3 import AF3Trajectory, compute_group_loss
    from tools.arc2_agent_factory3_bridge_20261014.vendor.types import TrainingSample
    from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.metric_state import MeanMetricState
    OPTIONAL_AVAILABLE = True
except ModuleNotFoundError as error:
    if error.name not in {"torch", "numpy", "pydantic"}:
        raise
    torch = None
    OPTIONAL_AVAILABLE = False


def trajectory(name, reward, *, group="g", length=3, value=-1.0, behavior=-1.0):
    train = torch.full((length,), value, dtype=torch.float32, requires_grad=True)
    old = torch.full((length,), behavior, dtype=torch.float32, requires_grad=True)
    mask = torch.tensor([0] + [1] * (length - 1))
    return AF3Trajectory(name, group, list(range(length)), train, old, mask, reward)


@unittest.skipUnless(OPTIONAL_AVAILABLE, "optional torch/numpy/pydantic absent; not AF3 acceptance")
class AF3LiveAdapterTests(unittest.TestCase):
    def test_real_upstream_autograd_and_original_ids(self):
        raw = torch.tensor([[0.1, -0.2, 0.3], [0.4, 0.2, -0.5]], requires_grad=True)
        selected = raw.log_softmax(-1)[:, 1]
        rows = [AF3Trajectory(str(i), "g", [9, 7],
                              torch.cat((selected[i:i+1] * 0, selected[i:i+1])),
                              torch.cat((selected[i:i+1] * 0, selected[i:i+1])).detach(),
                              torch.tensor([0, 1]), 1 - i) for i in range(2)]
        original = [list(row.input_ids) for row in rows]
        result = compute_group_loss(rows)
        self.assertTrue(result.should_update)
        self.assertEqual(result.loss.device, raw.device)
        self.assertTrue(all(type(sample) is TrainingSample for sample in result.samples))
        self.assertTrue(all(type(metric) is MeanMetricState for metric in result.metric_states.values()))
        self.assertEqual([sample.input_ids for sample in result.samples], original)
        self.assertEqual([row.input_ids for row in rows], original)
        result.loss.backward()
        self.assertTrue(torch.isfinite(raw.grad).all())
        self.assertGreater(raw.grad.norm().item(), 0)

    def test_centered_gradients_token_mean_and_behavior_detached(self):
        rows = [trajectory("win", 1), trajectory("lose", 0)]
        result = compute_group_loss(rows)
        result.loss.backward()
        torch.testing.assert_close(rows[0].train_log_probs.grad, torch.tensor([0., -.125, -.125]))
        torch.testing.assert_close(rows[1].train_log_probs.grad, torch.tensor([0., .125, .125]))
        self.assertIsNone(rows[0].behavior_log_probs.grad)
        self.assertIsNone(rows[1].behavior_log_probs.grad)
        self.assertEqual(result.group_summaries[0]["reward_mean"], .5)

    def test_unequal_lengths_and_signal_group_weighting(self):
        rows = [trajectory("a", 1, length=2), trajectory("b", 0, length=4),
                trajectory("c", 1, group="zero"), trajectory("d", 1, group="zero")]
        result = compute_group_loss(rows)
        result.loss.backward()
        self.assertEqual(result.mixed_groups, 1)
        self.assertEqual([sample.divisor for sample in result.samples], [2., 6., 4., 4.])
        torch.testing.assert_close(rows[0].train_log_probs.grad, torch.tensor([0., -.25]))
        torch.testing.assert_close(rows[1].train_log_probs.grad, torch.tensor([0., 1/12, 1/12, 1/12]))
        self.assertEqual(rows[2].train_log_probs.grad.abs().sum().item(), 0)

    def test_two_signal_groups_average_equally(self):
        rows = [trajectory("a", 1), trajectory("b", 0),
                trajectory("c", 1, group="h"), trajectory("d", 0, group="h")]
        result = compute_group_loss(rows)
        result.loss.backward()
        self.assertEqual(result.mixed_groups, 2)
        torch.testing.assert_close(rows[0].train_log_probs.grad, torch.tensor([0., -.0625, -.0625]))

    def test_zero_signal_never_calls_upstream(self):
        for reward in (0, 1, .25):
            with self.subTest(reward=reward):
                rows = [trajectory("a", reward), trajectory("b", reward)]
                with patch("tools.arc2_goal_sprint_20261017.af3.DDISLoss", side_effect=AssertionError("called")):
                    with torch.no_grad():
                        result = compute_group_loss(rows)
                self.assertFalse(result.should_update)
                self.assertIsNone(result.loss)
                self.assertEqual(result.reason, "zero_reward_signal")

    def test_policy_lag_clips_both_advantage_signs(self):
        rows = [trajectory("a", 1, value=-.1, behavior=-2.),
                trajectory("b", 0, value=-3., behavior=-1.)]
        result = compute_group_loss(rows)
        self.assertFalse(result.should_update)
        self.assertEqual(result.reason, "all_signal_tokens_clipped")
        result.loss.backward()
        for row in rows:
            self.assertEqual(row.train_log_probs.grad.abs().sum().item(), 0)
        self.assertEqual(result.metric_states["algo/ddis_mask_rate"].mean().item(), 1.)

    def test_valid_some_tokens_clipped(self):
        a, b = trajectory("a", 1), trajectory("b", 0)
        a = replace(a, train_log_probs=torch.tensor([0., -1., -.1], requires_grad=True))
        result = compute_group_loss([a, b])
        self.assertTrue(result.should_update)
        result.loss.backward()
        self.assertLess(a.train_log_probs.grad[1].item(), 0)
        self.assertEqual(a.train_log_probs.grad[2].item(), 0)

    def test_malformed_shapes_and_masks_rejected(self):
        a, b = trajectory("a", 1), trajectory("b", 0)
        changes = [
            {"train_log_probs": torch.zeros(2, requires_grad=True)},
            {"behavior_log_probs": torch.zeros(1, 3)},
            {"completion_mask": torch.tensor([0, 1, 2])},
            {"completion_mask": torch.tensor([1, 1, 1])},
            {"completion_mask": torch.tensor([0, 0, 0])},
            {"completion_mask": torch.tensor([0, 1, 0])},
            {"completion_mask": torch.tensor([0., 1., float("nan")])},
            {"input_ids": [0, True, 2]},
            {"input_ids": [0, -1, 2]},
            {"sample_id": "b"},
            {"reward": None},
            {"reward": True},
        ]
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    compute_group_loss([replace(a, **change), b])

    def test_nonfinite_and_nonprobability_rejected(self):
        a, b = trajectory("a", 1), trajectory("b", 0)
        for field in ("train_log_probs", "behavior_log_probs"):
            for invalid in (float("nan"), float("inf"), -float("inf"), .1, -1e100):
                with self.subTest(field=field, invalid=invalid):
                    bad = torch.tensor([0., invalid, -1.], dtype=torch.float64, requires_grad=True)
                    with self.assertRaises(ValueError):
                        compute_group_loss([replace(a, **{field: bad}), b])
        for reward in (float("nan"), float("inf"), 10**400):
            with self.assertRaises(ValueError):
                compute_group_loss([replace(a, reward=reward), b])

    def test_missing_groups_autograd_and_epsilon_rejected(self):
        a, b = trajectory("a", 1), trajectory("b", 0)
        for rows in ([], [a], [a, replace(b, group_id="other")]):
            with self.assertRaises(ValueError):
                compute_group_loss(rows)
        with self.assertRaises(ValueError):
            compute_group_loss([replace(a, train_log_probs=a.train_log_probs.detach()), b])
        with torch.no_grad():
            with self.assertRaises(ValueError):
                compute_group_loss([a, b])
        for args in ({"eps_low": -1}, {"eps_low": 2}, {"eps_high": float("nan")}, {"eps_high": True}):
            with self.assertRaises(ValueError):
                compute_group_loss([a, b], **args)

    @unittest.skipUnless(torch is not None and torch.cuda.is_available(), "CPU environment; CUDA behavior requires GPU validation")
    def test_cuda_preserves_device(self):
        rows = [trajectory("a", 1), trajectory("b", 0)]
        rows = [replace(row, train_log_probs=row.train_log_probs.detach().cuda().requires_grad_(),
                        behavior_log_probs=row.behavior_log_probs.detach().cuda(),
                        completion_mask=row.completion_mask.cuda()) for row in rows]
        result = compute_group_loss(rows)
        self.assertEqual(result.loss.device.type, "cuda")
        result.loss.backward()
        self.assertEqual(rows[0].train_log_probs.grad.device.type, "cuda")


if __name__ == "__main__":
    unittest.main()

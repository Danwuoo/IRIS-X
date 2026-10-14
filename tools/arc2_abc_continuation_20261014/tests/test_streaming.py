"""Synthetic CPU conformance; no model/owner/training or network is exercised."""
from copy import deepcopy
from dataclasses import replace
import gc
import importlib.util
import json
import math
import unittest
from unittest.mock import patch
import weakref

from tools.arc2_agent_factory3_bridge_20261014.bridge import (
    _contract_digest, _sample_digest, compute_loss, digest, prepare_batch,
)
from tools.arc2_agent_factory3_bridge_20261014.fixtures import synthetic_batch
from tools.arc2_abc_continuation_20261014.streaming import StreamingLossSession

HAS_TORCH = importlib.util.find_spec("torch") is not None


def rebound(prepared, **changes):
    """Adversarial self-consistent hashes are not an authentication credential."""
    changed = replace(prepared, **changes)
    return replace(changed, sample_digest=_sample_digest(changed.samples), contract_digest=_contract_digest(
        changed.samples, changed.group_reports, changed.nonforced_masks, changed.prompt_lengths,
        changed.context, changed.raw_receipt_digest))


def set_length(batch, row_index, length, *, all_nonforced=False, log_mu=None):
    t = batch["rows"][row_index]["trajectory"]
    p = t["prompt_ids"]
    generated = [1 + i % 3 for i in range(length)]
    steps = []
    for i, token in enumerate(generated):
        support = [token, token + 8] if all_nonforced or i % 2 else [token]
        steps.append({"token": token, "position": len(p) + i - 1, "support": support,
                      "prefix_sha256": digest(p + generated[:i]), "dfa_state": [0, 1, i],
                      "log_mu": (log_mu if log_mu is not None else -math.log(len(support)))})
    t.update(generated_ids=generated, original_ids=p + generated, steps=steps,
             attention_mask=[1] * (len(p) + length),
             origins=["prompt"] * len(p) + ["assistant_generated"] * length)


class StreamingContractTests(unittest.TestCase):
    def test_complete_zero_signal_has_no_loss_or_replay_construction(self):
        batch, context = synthetic_batch((0, 8) * 4)
        prepared = prepare_batch(batch, context)
        # Importing the module / creating this path must not require torch.
        import builtins
        original = builtins.__import__
        def guard(name, *args, **kwargs):
            if name == "torch" or ".vendor.losses" in name:
                raise AssertionError("zero-signal attempted torch/loss import")
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=guard):
            with StreamingLossSession(prepared) as session:
                self.assertIsNone(session.next_sample_id)
                report = session.finalize()
        self.assertEqual(report.status, "zero-signal-no-replay-no-loss")
        self.assertIsNone(report.loss_unscaled)
        self.assertEqual(report.contributed_samples, 0)
        self.assertEqual(report.metric_states, {})
        self.assertFalse(report.production_update_authorized)
        self.assertFalse(report.model_replay_verified)
        self.assertFalse(report.provenance_authenticated)
        json.dumps(report.summary(), allow_nan=False)
        self.assertEqual(session.state, "finalized")
        self.assertIsNone(session._prepared)

    def test_zero_signal_contribute_is_rejected_and_aborted(self):
        batch, context = synthetic_batch((0,) * 8)
        session = StreamingLossSession(prepare_batch(batch, context))
        with self.assertRaisesRegex(ValueError, "zero-signal"):
            session.contribute("synthetic-00", None)
        self.assertEqual(session.state, "aborted")
        with self.assertRaisesRegex(ValueError, "not open"):
            session.finalize()

    def test_truncated_or_rehashed_prepared_contract_cannot_be_admitted(self):
        batch, context = synthetic_batch()
        prepared = prepare_batch(batch, context)
        for changed in (
            rebound(prepared, samples=prepared.samples[:1]),
            rebound(prepared, group_reports=prepared.group_reports[:1]),
            rebound(prepared, prompt_lengths=prepared.prompt_lengths[:-1]),
            rebound(prepared, nonforced_masks=prepared.nonforced_masks[:-1]),
        ):
            with self.subTest(kind=len(changed.samples)), self.assertRaises(ValueError):
                StreamingLossSession(changed)

    def test_rehashed_bad_divisor_advantage_identity_and_alignment_rejected(self):
        batch, context = synthetic_batch()
        prepared = prepare_batch(batch, context)
        mutations = (
            lambda p: setattr(p.samples[0], "divisor", 8.),
            lambda p: setattr(p.samples[0], "advantages", [0.] * len(p.samples[0].input_ids)),
            lambda p: setattr(p.samples[1], "sample_id", p.samples[0].sample_id),
            lambda p: setattr(p.samples[0], "seq_token_count", 1),
            lambda p: setattr(p.samples[0], "prompt_sequence_count", 1),
            lambda p: setattr(p.samples[0], "oldest_weight_version", 1),
            lambda p: setattr(p.samples[1], "input_ids", [23] + p.samples[1].input_ids[1:]),
        )
        for mutate in mutations:
            changed = deepcopy(prepared)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                StreamingLossSession(rebound(changed))

    def test_mutation_and_source_drift_rejected_before_replay(self):
        from tools.arc2_agent_factory3_bridge_20261014 import provenance
        batch, context = synthetic_batch()
        prepared = prepare_batch(batch, context)
        with patch.dict(provenance.VENDOR_SHA256, {"vendor/types.py": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "source drift"):
                StreamingLossSession(prepared)
        with patch.dict(provenance.FROZEN_CONTRACT_SHA256, {provenance.BASELINE_MATH: "0" * 64}):
            with self.assertRaisesRegex(ValueError, "source drift"):
                StreamingLossSession(prepared)
        changed = replace(prepared, nonforced_masks=tuple(tuple(False for _ in m) for m in prepared.nonforced_masks))
        with self.assertRaisesRegex(ValueError, "bridge contract"):
            StreamingLossSession(changed)
        prepared.samples[0].divisor *= 2
        with self.assertRaisesRegex(ValueError, "upstream samples"):
            StreamingLossSession(prepared)


@unittest.skipUnless(HAS_TORCH, "real CPU torch required; streaming tensor integration NOT RUN")
class StreamingTorchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(1)
        cls.torch = torch
        from tools.arc2_agent_factory3_bridge_20261014.proof import baseline_math
        cls.math_module = baseline_math()

    def fixture(self, successes=(1, 2, 4, 6, 0, 8, 3, 5), batch_index=0):
        batch, context = synthetic_batch(successes, batch_index=batch_index)
        return batch, context, prepare_batch(batch, context)

    def replay_leaf(self, prepared, index=0, *, dtype=None):
        return self.torch.tensor(prepared.samples[index].gen_logprobs[prepared.prompt_lengths[index]:],
                                 dtype=dtype or self.torch.float32, requires_grad=True)

    def selected(self, logits, row):
        t = row["trajectory"]
        n = len(t["generated_ids"])
        allowed = self.torch.zeros((n, 16), dtype=self.torch.bool)
        for i, step in enumerate(t["steps"]):
            allowed[i, step["support"]] = True
        return self.math_module.selected_log_probs(logits[:n], allowed,
                                                   self.torch.tensor(t["generated_ids"], dtype=self.torch.long))

    def compare_three_reductions(self, batch, context):
        torch = self.torch
        from tools.arc2_agent_factory3_bridge_20261014.proof import synthetic_replay
        from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.ddis_loss import DDISLoss
        from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.metric_state import MeanMetricState
        from torch.nn.utils.rnn import pad_sequence
        prepared = prepare_batch(batch, context)
        logits, replay = synthetic_replay(batch, self.math_module)
        whole = compute_loss(prepared, replay)
        pi = pad_sequence(list(replay.values()), batch_first=True)
        mu = pad_sequence([torch.tensor([step["log_mu"] for step in row["trajectory"]["steps"]])
                           for row in batch["rows"]], batch_first=True)
        mask = pad_sequence([torch.ones(len(row["trajectory"]["generated_ids"]), dtype=torch.bool)
                             for row in batch["rows"]], batch_first=True)
        frozen, _ = self.math_module.ddis_loss(
            pi, mu, mask, torch.tensor([row["reward"] for row in batch["rows"]], dtype=torch.float32),
            [row["parent_id"] for row in batch["rows"]], torch.ones(64, dtype=torch.bool),
            [context.policy_version] * 64)
        upstream_gradient, = torch.autograd.grad(whole.loss_unscaled, logits, retain_graph=True)
        frozen_gradient, = torch.autograd.grad(frozen, logits)
        streamed_logits = logits.detach().clone().requires_grad_()
        session = StreamingLossSession(prepared)
        self.assertIs(type(session._loss), DDISLoss)
        # No full replay dictionary / graph list is constructed on this path.
        backward_calls = 0
        with session:
            for index, row in enumerate(batch["rows"]):
                selected = self.selected(streamed_logits[index], row)
                contribution = session.contribute(row["trajectory"]["trajectory_id"], selected)
                self.assertEqual(contribution.index, index)
                self.assertFalse(contribution.production_update_authorized)
                self.assertEqual(contribution.derivative_scope, "caller-supplied-CPU-replay-tensors-only")
                if contribution.has_training_signal:
                    contribution.loss_unscaled.backward()
                    backward_calls += 1
                else:
                    self.assertEqual(float(contribution.loss_unscaled.detach()), 0.)
                del contribution, selected
            report = session.finalize()
        torch.testing.assert_close(torch.tensor(report.loss_unscaled), whole.loss_unscaled.detach(), atol=1e-7, rtol=1e-6)
        torch.testing.assert_close(whole.loss_unscaled, frozen, atol=1e-7, rtol=1e-6)
        torch.testing.assert_close(streamed_logits.grad, upstream_gradient, atol=1e-7, rtol=1e-6)
        torch.testing.assert_close(streamed_logits.grad, frozen_gradient, atol=1e-7, rtol=1e-6)
        self.assertGreater(float(streamed_logits.grad.abs().sum()), 0.)
        for name, expected in whole.metric_states.items():
            actual = report.metric_states[name]
            self.assertIs(type(actual), MeanMetricState)
            self.assertEqual(actual.weighting, expected.weighting)
            self.assertFalse(actual.sum.requires_grad)
            self.assertIsNone(actual.sum.grad_fn)
            torch.testing.assert_close(actual.count, expected.count, atol=0., rtol=0.)
            # Float32 per-row sums may round differently from padded reduction.
            torch.testing.assert_close(actual.sum, expected.sum, atol=1e-5, rtol=1e-5)
            torch.testing.assert_close(actual.mean(), expected.mean(), atol=3e-7, rtol=1e-5)
        self.assertEqual(report.contributed_samples, 64)
        self.assertEqual(backward_calls, prepared.mixed_groups * 8)
        self.assertEqual(float(report.metric_states["algo/ratio_mean"].count), 64.)
        self.assertEqual(report.mixed_groups, prepared.mixed_groups)
        self.assertFalse(report.summary()["production_update_authorized"])
        self.assertEqual(report.contract_digest, prepared.contract_digest)
        self.assertEqual(session._metric_states, {})
        self.assertIsNone(session._prepared)
        json.dumps(report.summary(), allow_nan=False)
        return report

    def test_all_four_batches_mixed_counts_lengths_scalar_gradients_and_metrics(self):
        patterns = ((1, 0, 8, 0, 8, 0, 8, 0), (1, 2, 0, 8, 0, 8, 0, 8),
                    (1, 2, 4, 6, 0, 8, 3, 5), (1, 2, 3, 4, 5, 6, 7, 1))
        for batch_index, successes in enumerate(patterns):
            with self.subTest(batch_index=batch_index):
                batch, context, _ = self.fixture(successes, batch_index)
                set_length(batch, 0, 1)
                set_length(batch, 1, 31)
                set_length(batch, 7, 9)
                self.compare_three_reductions(batch, context)

    def test_remaining_mixed_group_counts_preserve_complete_batch_weighting(self):
        for mixed in (3, 4, 5, 7):
            with self.subTest(mixed_groups=mixed):
                batch, context, _ = self.fixture(tuple(range(1, mixed + 1)) + (0,) * (8 - mixed))
                self.compare_three_reductions(batch, context)

    def test_maximum_generated_length_keeps_full_batch_divisor(self):
        batch, context, _ = self.fixture()
        set_length(batch, 0, 1024)
        self.compare_three_reductions(batch, context)

    def test_snapshot_not_mutated_by_caller_after_session_start(self):
        _, _, prepared = self.fixture()
        pi = self.replay_leaf(prepared)
        expected = prepared.samples[0].divisor
        session = StreamingLossSession(prepared)
        prepared.samples[0].divisor *= 99
        prepared.samples[0].sample_id = "mutated"
        prepared.group_reports[0]["mixed"] = False
        self.assertEqual(session.next_sample_id, "synthetic-00")
        self.assertEqual(session._prepared.samples[0].divisor, expected)
        contribution = session.contribute("synthetic-00", pi)
        self.assertTrue(contribution.loss_unscaled.requires_grad)
        session.abort()

    def test_wrong_order_duplicate_unknown_extra_and_incomplete_poison_session(self):
        _, _, prepared = self.fixture()
        for identity in ("synthetic-01", "unknown", None):
            session = StreamingLossSession(prepared)
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, "next trajectory identity"):
                session.contribute(identity, self.replay_leaf(prepared))
            self.assertEqual(session.state, "aborted")
            self.assertIsNone(session._prepared)
            with self.assertRaisesRegex(ValueError, "not open"):
                session.finalize()
        session = StreamingLossSession(prepared)
        session.contribute("synthetic-00", self.replay_leaf(prepared))
        with self.assertRaisesRegex(ValueError, "next trajectory identity"):
            session.contribute("synthetic-00", self.replay_leaf(prepared))
        self.assertEqual(session.state, "aborted")
        for count in (0, 1, 63):
            session = StreamingLossSession(prepared)
            for index in range(count):
                session.contribute(prepared.samples[index].sample_id, self.replay_leaf(prepared, index))
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "incomplete"):
                session.finalize()
            self.assertEqual(session.state, "aborted")
            self.assertEqual(session._metric_states, {})
            self.assertEqual(session._loss_total, 0.)
        session = StreamingLossSession(prepared)
        for index in range(64):
            session.contribute(prepared.samples[index].sample_id, self.replay_leaf(prepared, index))
        with self.assertRaisesRegex(ValueError, "next trajectory identity"):
            session.contribute("synthetic-00", self.replay_leaf(prepared))
        self.assertEqual(session.state, "aborted")

    def test_successful_finalize_is_single_use(self):
        _, _, prepared = self.fixture()
        session = StreamingLossSession(prepared)
        for index in range(64):
            session.contribute(prepared.samples[index].sample_id, self.replay_leaf(prepared, index))
        report = session.finalize()
        for action in (session.finalize, lambda: session.contribute("synthetic-00", None)):
            with self.assertRaisesRegex(ValueError, "not open"):
                action()
        session.abort()
        self.assertEqual(session.state, "finalized")
        self.assertEqual(report.contributed_samples, 64)

    def test_mixed_batch_zero_advantage_rows_still_require_replay_diagnostics(self):
        _, _, prepared = self.fixture((0, 1, 8, 0, 8, 0, 8, 0))
        session = StreamingLossSession(prepared)
        good = session.contribute("synthetic-00", self.replay_leaf(prepared))
        self.assertFalse(good.has_training_signal)
        self.assertEqual(float(good.loss_unscaled.detach()), 0.)
        bad = self.replay_leaf(prepared, 1).detach()
        bad[1] = -1.
        bad.requires_grad_()
        with self.assertRaisesRegex(ValueError, "replay gap"):
            session.contribute("synthetic-01", bad)
        self.assertEqual(session.state, "aborted")
        self.assertEqual(session._metric_states, {})

    def test_disabled_autograd_and_inference_tensors_fail_closed(self):
        torch = self.torch
        _, _, prepared = self.fixture()
        for mode in (torch.no_grad, torch.inference_mode):
            session = StreamingLossSession(prepared)
            pi = self.replay_leaf(prepared)
            with self.subTest(mode=mode), mode(), self.assertRaisesRegex(ValueError, "active autograd"):
                session.contribute("synthetic-00", pi)
            self.assertEqual(session.state, "aborted")
        with torch.inference_mode():
            pi = self.replay_leaf(prepared)
        with self.assertRaisesRegex(ValueError, "inference replay tensor"):
            StreamingLossSession(prepared).contribute("synthetic-00", pi)
        zero_batch, zero_context = synthetic_batch((0,) * 8)
        with torch.no_grad():
            report = StreamingLossSession(prepare_batch(zero_batch, zero_context)).finalize()
        self.assertIsNone(report.loss_unscaled)

    def test_invalid_tensor_shapes_devices_detached_and_values_rejected(self):
        torch = self.torch
        _, _, prepared = self.fixture()
        pi = self.replay_leaf(prepared)
        bad_values = [None, list(pi.detach()), pi.detach(), pi.reshape(1, -1), pi[:1],
                      pi.to(dtype=torch.int64), torch.empty(pi.shape, device="meta", requires_grad=True)]
        for index, value in enumerate((float("nan"), float("inf"), -float("inf"), .1, -1e300)):
            bad = pi.detach().double().clone()
            bad[1] = value
            bad_values.append(bad.requires_grad_())
        forced_bad = pi.detach().clone()
        forced_bad[0] = -.001
        bad_values.append(forced_bad.requires_grad_())
        for bad in bad_values:
            session = StreamingLossSession(prepared)
            with self.subTest(value=repr(bad)), self.assertRaises(ValueError):
                session.contribute("synthetic-00", bad)
            self.assertEqual(session.state, "aborted")

    def test_replay_max_and_p95_gates_and_ratio_boundaries(self):
        torch = self.torch
        batch, context, _ = self.fixture()
        set_length(batch, 0, 101, all_nonforced=True, log_mu=-1.)
        prepared = prepare_batch(batch, context)
        for delta, allowed in ((0., True), (.20, True), (.200001, False), (.05, True), (.050001, False),
                               (math.log(.8), False), (math.log(1.28), False)):
            pi = self.replay_leaf(prepared, dtype=torch.float64).detach()
            # Max gate gets one outlier; p95 gate gets a whole-vector shift.
            if abs(delta) > .1:
                pi[0] += delta
            else:
                pi += delta
                if delta == .05:
                    pi = torch.nextafter(pi, torch.full_like(pi, -1.))
            pi.requires_grad_()
            session = StreamingLossSession(prepared)
            with self.subTest(delta=delta):
                if allowed:
                    contribution = session.contribute("synthetic-00", pi)
                    self.assertTrue(contribution.loss_unscaled.requires_grad)
                    session.abort()
                else:
                    with self.assertRaisesRegex(ValueError, "replay gap|unclipped"):
                        session.contribute("synthetic-00", pi)
                    self.assertEqual(session.state, "aborted")

    def test_actual_upstream_strict_ratio_equality_and_detached_ratio_derivative(self):
        torch = self.torch
        from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.ddis_loss import DDISLoss
        pi = torch.tensor([-1.5, -.5, -1.], requires_grad=True)
        mu = torch.tensor([-1., -1., -1.], requires_grad=True)
        ratios = (pi.detach() - mu.detach()).exp()
        upstream = DDISLoss(eps_low=1. - float(ratios[0]), eps_high=float(ratios[1]) - 1.)
        result = upstream.compute_unpacked(log_probs=[pi], gen_log_probs=[mu],
            completion_mask=[torch.ones(3)], advantages=[torch.tensor([1., -1., 1.])],
            divisors=torch.tensor([3.]))
        pi_grad, mu_grad = torch.autograd.grad(result.loss_unscaled, (pi, mu), allow_unused=True)
        torch.testing.assert_close(pi_grad, torch.tensor([0., 0., -1. / 3]))
        self.assertIsNone(mu_grad)
        # Runtime replay gates reject these .5 gaps before loss. This direct
        # upstream differential checks the actual hard strict mask separately.

    def test_session_retains_no_replay_graph_before_or_after_caller_backward(self):
        torch = self.torch
        _, _, prepared = self.fixture()
        for backward in (False, True):
            session = StreamingLossSession(prepared)
            for index in range(64):
                leaf = self.replay_leaf(prepared, index)
                pi = leaf * 1.
                result = session.contribute(prepared.samples[index].sample_id, pi)
                references = [weakref.ref(obj) for obj in (leaf, pi, result.loss_unscaled, result)]
                if backward:
                    result.loss_unscaled.backward()
                del leaf, pi, result
                gc.collect()
                self.assertTrue(all(reference() is None for reference in references),
                                "session retained a caller replay graph")
                self.assertIsInstance(session._loss_total, float)
                for state in session._metric_states.values():
                    self.assertIsNone(state.sum.grad_fn)
                    self.assertIsNone(state.count.grad_fn)
                    self.assertFalse(state.sum.requires_grad)
                    self.assertFalse(state.count.requires_grad)
            session.finalize()

    def test_caller_metric_mutation_does_not_corrupt_session_accumulator(self):
        _, _, prepared = self.fixture()
        session = StreamingLossSession(prepared)
        result = session.contribute("synthetic-00", self.replay_leaf(prepared))
        result.metric_states["algo/ratio_mean"].sum.fill_(99.)
        self.assertEqual(float(session._metric_states["algo/ratio_mean"].sum), 1.)
        session.abort()

    def test_exception_timeout_keyboard_interrupt_and_unfinalized_context_cleanup(self):
        _, _, prepared = self.fixture()
        for error in (RuntimeError("caller replay failed"), TimeoutError("caller budget expired"), KeyboardInterrupt()):
            session = StreamingLossSession(prepared)
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                with session:
                    session.contribute("synthetic-00", self.replay_leaf(prepared))
                    raise error
            self.assertEqual(session.state, "aborted")
            self.assertIsNone(session._prepared)
            self.assertIsNone(session._loss)
            self.assertEqual(session._metric_states, {})
            self.assertEqual(session._loss_total, 0.)
        with StreamingLossSession(prepared) as session:
            session.contribute("synthetic-00", self.replay_leaf(prepared))
        self.assertEqual(session.state, "aborted")
        session.abort()
        with self.assertRaisesRegex(ValueError, "not open"):
            session.contribute("synthetic-01", self.replay_leaf(prepared, 1))

    def test_finite_per_row_metrics_cannot_overflow_merged_report(self):
        batch, context, _ = self.fixture()
        # These are legal declarations, not a claim of real model logp. Each
        # upstream metric is finite; merging two float32 -3e38 sums overflows.
        for index in (0, 1):
            set_length(batch, index, 1, all_nonforced=True, log_mu=-3e38)
        prepared = prepare_batch(batch, context)
        session = StreamingLossSession(prepared)
        first = session.contribute("synthetic-00", self.replay_leaf(prepared))
        self.assertTrue(bool(self.torch.isfinite(first.metric_states["algo/logprobs_mean"].sum)))
        with self.assertRaisesRegex(ValueError, "finite merged upstream metric"):
            session.contribute("synthetic-01", self.replay_leaf(prepared, 1))
        self.assertEqual(session.state, "aborted")
        self.assertEqual(session._metric_states, {})
        with self.assertRaisesRegex(ValueError, "not open"):
            session.finalize()

    def test_upstream_failure_aborts_without_claiming_owner_rollback(self):
        _, _, prepared = self.fixture()
        session = StreamingLossSession(prepared)
        with patch.object(session._loss, "compute_unpacked", side_effect=RuntimeError("upstream failure")):
            with self.assertRaisesRegex(RuntimeError, "upstream failure"):
                session.contribute("synthetic-00", self.replay_leaf(prepared))
        self.assertEqual(session.state, "aborted")
        self.assertEqual(session.contributed_samples, 0)
        self.assertEqual(session._metric_states, {})


if __name__ == "__main__":
    unittest.main()

"""Real tiny Qwen3 CPU probability diagnostics, not official-weight/GPU proof."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import time
import unittest
from unittest.mock import patch

_OPTIONAL = ("torch", "transformers", "peft", "pydantic", "tokenizers", "safetensors")
_MISSING = [name for name in _OPTIONAL if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline
    from tools.nvarc_posttrain_20261017 import probability_probe as pp


def engine_fixture(dtype=None):
    engine = tiny_engine(dtype=dtype)
    # Exercise actual adapter contributions, not zero-initialized LoRA B only.
    generator = torch.Generator(device="cpu").manual_seed(20261018)
    with torch.no_grad():
        for name, parameter in engine.model.named_parameters():
            if ".lora_B." in name:
                parameter.normal_(mean=0.0, std=0.02, generator=generator)
    return engine


@unittest.skipIf(bool(_MISSING), "Optional model dependencies missing: " + ", ".join(_MISSING))
class ProbabilityProbeCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        self.engine = engine_fixture()
        self.prompt = [14, 11, 10, 1, 2, 15, 14, 12, 10]

    def run_probe(self, engine=None, **kwargs):
        return pp.probe(engine or self.engine, self.prompt, deadline=time.time() + 60,
                        **{"max_new_tokens": 40, "seed": 7, **kwargs})

    def make_trace(self, **kwargs):
        trace = {}
        rows = self.engine.generate(self.prompt, trace=trace, sample=True, count=2,
                                    max_new_tokens=40, **kwargs)
        return trace, rows

    def replay(self, trace, seal=None):
        return pp.replay_trace(self.engine, trace, expected_trace_sha256=seal or trace["sha256"],
                               deadline=time.time() + 60)

    def test_genuine_sampled_fp32_and_bf16_nonzero_lora(self):
        for dtype in (torch.float32, torch.bfloat16):
            with self.subTest(dtype=dtype):
                engine = engine_fixture(dtype)
                original = torch.multinomial
                draws = []
                def sample(probabilities, count, **kwargs):
                    self.assertEqual(tuple(probabilities.shape), (2, 16))
                    self.assertTrue(bool((probabilities > 0).all()))
                    draws.append(1)
                    return original(probabilities, count, **kwargs)
                with patch("torch.multinomial", side_effect=sample):
                    result = self.run_probe(engine)
                self.assertEqual(result["status"], "completed", result["error"])
                self.assertEqual(len(draws), len(result["trace"]["steps"]))
                self.assertTrue(result["trace"]["sample"])
                self.assertEqual(result["cached_max_abs_logp_gap"], 0.0)
                self.assertLess(result["full_max_abs_logp_gap"], 0.05 if dtype == torch.bfloat16 else 1e-5)
                self.assertEqual(len(result["full_replay"]), 2)
                self.assertFalse(result["training_authorized"])
                self.assertGreater(result["full_metrics"]["importance_ratio_min"], 0)
                self.assertEqual(result["context"]["base_dtype"], str(dtype))
                self.assertEqual(result["context"]["autocast"], "cpu_bfloat16" if dtype == torch.bfloat16 else "none")
                self.assertEqual(result["engine_counter_deltas"]["optimizer_attempts"], 0)
                self.assertEqual(result["engine_counter_deltas"]["optimizer_steps"], 0)
                for detail, row in zip(result["full_replay"], result["rows"]):
                    self.assertEqual(detail["behavior_log_probs"], row["behavior_log_probs"][row["prompt_length"]:])
                    self.assertEqual(len(detail["full_log_probs"]), row["completion_tokens"])
                json.dumps(result, allow_nan=False)

    def test_trace_hook_preserves_rows_and_random_stream_exactly(self):
        state = self.engine.generator.get_state().clone()
        expected = self.engine.generate(self.prompt, count=2, max_new_tokens=40, sample=True)
        expected_rng = self.engine.generator.get_state().clone()
        self.engine.generator.set_state(state)
        trace, rows = self.make_trace()
        self.assertEqual(rows, expected)
        self.assertTrue(torch.equal(expected_rng, self.engine.generator.get_state()))
        self.assertEqual(trace["completion_ids"], [r["completion_ids"] for r in rows])
        pp.validate_trace(trace, expected_trace_sha256=trace["sha256"])

    def test_genuine_heterogeneous_eos_retains_all_discarded_filler(self):
        trace, rows = self.make_trace()
        self.assertNotEqual(rows[0]["completion_tokens"], rows[1]["completion_tokens"])
        self.assertGreater(trace["work"]["generation_finished_row_token_slots"], 0)
        self.assertTrue(any(not all(step["retained"]) for step in trace["steps"]))
        for i, row in enumerate(rows):
            retained = [step["selected_ids"][i] for step in trace["steps"] if step["retained"][i]]
            self.assertEqual(retained, row["completion_ids"])
            if row["stop"] == "completed":
                self.assertEqual(retained[-1], 15)
                self.assertNotIn(15, retained[:-1])
        result = self.replay(trace)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["metrics"]["max_abs_logp_gap"], 0.0)
        self.assertEqual(result["metrics"]["tokens"], len(trace["steps"]) * 2)
        self.assertGreater(result["metrics"]["tokens"], sum(r["completion_tokens"] for r in rows))

    def test_heterogeneous_left_padding_replays_exact_greedy_trace(self):
        trace = {}
        prompts = [[14, 12, 10], self.prompt]
        self.engine.generate_prompts(prompts, max_new_tokens=8, trace=trace)
        self.assertFalse(trace["sample"])
        self.assertEqual(trace["padding_width"], len(self.prompt))
        self.assertEqual(trace["work"]["generation_padding_tokens"], len(self.prompt) - 3)
        result = self.replay(trace)
        self.assertEqual(result["status"], "completed", result["error"])
        self.assertEqual(result["metrics"]["max_abs_logp_gap"], 0.0)
        self.assertEqual(result["work"]["input_tokens"], trace["work"]["generation_input_tokens"])

    def test_independent_all_logits_causal_alignment_and_future_invariance(self):
        result = self.run_probe(max_new_tokens=12)
        self.assertEqual(result["status"], "completed")
        with torch.no_grad():
            for row, detail in zip(result["rows"], result["full_replay"]):
                tokens = torch.tensor([row["input_ids"]])
                prompt = row["prompt_length"]
                self.engine.model.train()
                logits = self.engine.model(input_ids=tokens, attention_mask=torch.ones_like(tokens),
                                           use_cache=False, logits_to_keep=0).logits[0].float()
                # Independent explicit p-1 -> p, ..., n-2 -> n-1 alignment.
                selected = torch.log_softmax(logits, -1)[torch.arange(prompt - 1, len(row["input_ids"]) - 1),
                                                        tokens[0, prompt:]]
                torch.testing.assert_close(selected, torch.tensor(detail["full_log_probs"]), atol=1e-6, rtol=1e-6)
                wrong = torch.log_softmax(logits, -1)[torch.arange(prompt, len(row["input_ids"])), tokens[0, prompt:]]
                self.assertGreater((wrong - selected).abs().max().item(), 1e-3)
                changed = tokens.clone(); changed[0, -1] = (changed[0, -1] + 1) % 16
                other = self.engine.model(input_ids=changed, attention_mask=torch.ones_like(tokens),
                                          use_cache=False, logits_to_keep=0).logits[0].float()
                torch.testing.assert_close(logits[:-1], other[:-1], atol=0, rtol=0)

    def test_preserves_all_parameters_buffers_gradients_modes_and_rng(self):
        self.engine.model.train()
        list(self.engine.model.modules())[3].eval()
        modes = [m.training for m in self.engine.model.modules()]
        for p in self.engine.parameters[::2]:
            p.grad = torch.full_like(p, 0.125)
        params = {n: p.detach().clone() for n, p in self.engine.model.named_parameters()}
        buffers = {n: p.detach().clone() for n, p in self.engine.model.named_buffers()}
        gradients = {n: p.grad.clone() if p.grad is not None else None for n, p in self.engine.model.named_parameters()}
        private = self.engine.generator.get_state().clone()
        global_rng = torch.random.get_rng_state().clone()
        result = self.run_probe()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(modes, [m.training for m in self.engine.model.modules()])
        self.assertTrue(torch.equal(private, self.engine.generator.get_state()))
        self.assertTrue(torch.equal(global_rng, torch.random.get_rng_state()))
        for n, p in self.engine.model.named_parameters():
            self.assertTrue(torch.equal(params[n], p), n)
            if gradients[n] is None:
                self.assertIsNone(p.grad)
            else:
                self.assertTrue(torch.equal(gradients[n], p.grad), n)
        for n, p in self.engine.model.named_buffers():
            self.assertTrue(torch.equal(buffers[n], p), n)

    def test_actual_path_modes_cache_positions_and_no_grad(self):
        calls = []
        original = self.engine.model.forward
        def forward(*args, **kwargs):
            calls.append((self.engine.model.training, torch.is_grad_enabled(), copy.deepcopy(kwargs.get("position_ids")),
                          kwargs["use_cache"], kwargs["input_ids"].shape))
            return original(*args, **kwargs)
        with patch.object(self.engine.model, "forward", side_effect=forward):
            result = self.run_probe(max_new_tokens=5)
        self.assertEqual(result["status"], "completed")
        steps = len(result["trace"]["steps"])
        self.assertEqual(len(calls), 2 * steps + 2)
        for i, (train, grad, positions, cache, shape) in enumerate(calls):
            self.assertFalse(grad)
            self.assertEqual(train, i >= 2 * steps)
            self.assertEqual(cache, i < 2 * steps)
            if i < 2 * steps:
                step = i % steps
                expected = torch.arange(len(self.prompt))[None, :].repeat(2, 1) if step == 0 else torch.full((2, 1), len(self.prompt) + step - 1)
                self.assertTrue(torch.equal(positions, expected))
            else:
                self.assertIsNone(positions)
                self.assertEqual(shape[0], 1)

    def test_rejects_mutations_even_with_resealed_semantically_invalid_trace(self):
        trace, _ = self.make_trace()
        original = copy.deepcopy(trace)
        mutated = copy.deepcopy(trace)
        mutated["steps"][0]["selected_ids"][0] = (mutated["steps"][0]["selected_ids"][0] + 1) % 16
        self.assertEqual(self.replay(mutated, original["sha256"])["status"], "failed")
        mutations = [lambda t: t["steps"][0]["retained"].__setitem__(0, False),
                     lambda t: t["steps"][0]["selected_ids"].pop(),
                     lambda t: t["work"].__setitem__("generation_forward_attempts", 0),
                     lambda t: t["conventions"].__setitem__("temperature", True),
                     lambda t: t["completion_log_probs"][0].__setitem__(0, -100.0),
                     lambda t: t["steps"].__setitem__(0, {**t["steps"][0], "extra": 1}),
                     lambda t: t.__setitem__("padding_width", 8193)]
        for mutate in mutations:
            damaged = copy.deepcopy(trace); mutate(damaged); damaged["sha256"] = pp._sha(damaged)
            replay = self.replay(damaged)
            self.assertEqual(replay["status"], "failed")
            self.assertEqual(replay["work"]["forward_attempts"], 0)
        self.assertEqual(trace, original)

    def test_expired_deadline_and_invalid_bounds_never_claim_measured_zero(self):
        result = pp.probe(self.engine, self.prompt, deadline=time.time() - 1)
        self.assertEqual(result["status"], "deadline")
        self.assertIsNone(result["cached_max_abs_logp_gap"])
        self.assertIsNone(result["full_max_abs_logp_gap"])
        self.assertEqual(result["work"]["total"]["forward_attempts"], 0)
        for kwargs in ({"count": 9}, {"count": True}, {"max_new_tokens": 932}, {"seed": -1}, {"deadline": math.inf}):
            result = pp.probe(self.engine, self.prompt, **{"deadline": time.time() + 60, **kwargs})
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["work"]["total"]["forward_attempts"], 0)
            json.dumps(result, allow_nan=False)

    def test_generation_deadline_after_selection_retains_partial_trace_and_charges(self):
        calls = 0
        def deadline(_):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise PhaseDeadline("selected but not committed")
        with patch("tools.nvarc_posttrain_20261017.engine.check_deadline", side_effect=deadline):
            result = self.run_probe()
        self.assertEqual(result["status"], "deadline")
        self.assertEqual(result["stage"], "generation")
        self.assertEqual(result["work"]["generation"]["forward_attempts"], 1)
        self.assertEqual(result["work"]["generation"]["forward_successes"], 1)
        self.assertEqual(result["work"]["generation"]["input_tokens"], 2 * len(self.prompt))
        self.assertEqual(len(result["trace"]["steps"]), 1)
        self.assertFalse(result["trace"]["steps"][0]["committed"])
        self.assertEqual(result["trace"]["completion_ids"], [[], []])
        self.assertEqual(result["rows"], [])
        self.assertIsNone(result["full_max_abs_logp_gap"])

    def test_generation_forward_failure_retains_attempted_charge(self):
        original = self.engine.model.forward
        calls = 0
        def forward(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("synthetic second forward failure")
            return original(*args, **kwargs)
        with patch.object(self.engine.model, "forward", side_effect=forward):
            result = self.run_probe()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["work"]["total"]["forward_attempts"], 2)
        self.assertEqual(result["work"]["total"]["forward_successes"], 1)
        self.assertEqual(result["work"]["total"]["input_tokens"], 2 * (len(self.prompt) + 1))
        self.assertEqual(len(result["trace"]["steps"]), 1)
        self.assertEqual(result["trace"]["status"], "failed")
        json.dumps(result, allow_nan=False)

    def test_cached_failure_preserves_first_measured_gap_and_charges(self):
        original = self.engine.model.forward
        calls = 0
        def forward(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 5:  # generation 3 forwards, then second cached replay
                raise RuntimeError("synthetic cached failure")
            return original(*args, **kwargs)
        with patch.object(self.engine.model, "forward", side_effect=forward):
            result = self.run_probe(max_new_tokens=3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "cached_replay")
        self.assertEqual(result["work"]["cached_replay"]["forward_attempts"], 2)
        self.assertEqual(result["work"]["cached_replay"]["forward_successes"], 1)
        self.assertEqual(result["cached_max_abs_logp_gap"], 0.0)
        self.assertIsNone(result["full_max_abs_logp_gap"])
        self.assertEqual(result["work"]["total"]["forward_attempts"], 5)

    def test_full_failure_preserves_prior_rows_and_charges_failed_forward(self):
        original = self.engine.model.forward
        train_calls = 0
        def forward(*args, **kwargs):
            nonlocal train_calls
            if not kwargs["use_cache"]:
                train_calls += 1
                if train_calls == 2:
                    raise RuntimeError("synthetic full replay failure")
            return original(*args, **kwargs)
        with patch.object(self.engine.model, "forward", side_effect=forward):
            result = self.run_probe(max_new_tokens=3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "full_replay")
        self.assertEqual(len(result["full_replay"]), 1)
        self.assertIsNotNone(result["full_max_abs_logp_gap"])
        self.assertEqual(result["work"]["full_replay"]["forward_attempts"], 2)
        self.assertEqual(result["work"]["full_replay"]["forward_successes"], 1)
        self.assertEqual(result["work"]["full_replay"]["input_tokens"], 2 * (len(self.prompt) + 3))
        self.assertEqual(result["engine_counter_deltas"]["forward_calls"], 7)
        self.assertEqual(result["work"]["total"]["forward_attempts"], 8)

    def test_interrupts_propagate_with_receipt_and_restore_rng_modes(self):
        self.engine.model.train()
        modes = [m.training for m in self.engine.model.modules()]
        private = self.engine.generator.get_state().clone()
        for error in (KeyboardInterrupt("stop"), SystemExit("stop")):
            with patch.object(self.engine.model, "forward", side_effect=error):
                with self.assertRaises(type(error)) as raised:
                    self.run_probe()
            result = raised.exception.probability_probe_result
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["work"]["total"]["forward_attempts"], 1)
            self.assertEqual(result["work"]["total"]["forward_successes"], 0)
            self.assertEqual(modes, [m.training for m in self.engine.model.modules()])
            self.assertTrue(torch.equal(private, self.engine.generator.get_state()))

    def test_cached_deadline_keeps_measured_probabilities_and_status(self):
        real_deadline = pp.check_deadline
        calls = 0
        def deadline(value):
            nonlocal calls
            calls += 1
            if calls == 4:  # admission, cached entry, preforward, postforward
                raise PhaseDeadline("cached postforward deadline")
            return real_deadline(value)
        with patch.object(pp, "check_deadline", side_effect=deadline):
            result = self.run_probe(max_new_tokens=3)
        self.assertEqual(result["status"], "deadline")
        self.assertEqual(result["stage"], "cached_replay")
        self.assertEqual(result["error"]["type"], "PhaseDeadline")
        self.assertEqual(len(result["cached_replay"]["steps"]), 1)
        self.assertEqual(result["cached_max_abs_logp_gap"], 0.0)
        self.assertEqual(result["work"]["total"]["forward_attempts"], 4)
        self.assertIsNone(result["full_max_abs_logp_gap"])

    def test_full_deadline_keeps_measured_row_and_exact_charges(self):
        real_deadline = pp.check_deadline
        def deadline(value):
            if self.engine.model.training:
                raise PhaseDeadline("full postforward deadline")
            return real_deadline(value)
        self.engine.model.eval()
        with patch.object(pp, "check_deadline", side_effect=deadline):
            result = self.run_probe(max_new_tokens=3)
        self.assertEqual(result["status"], "deadline")
        self.assertEqual(result["stage"], "full_replay")
        self.assertEqual(len(result["full_replay"]), 1)
        self.assertIsNotNone(result["full_max_abs_logp_gap"])
        self.assertEqual(result["work"]["full_replay"]["forward_attempts"], 1)
        self.assertEqual(result["work"]["total"]["forward_attempts"], 7)
        self.assertFalse(self.engine.model.training)

    def test_ratio_overflow_retains_raw_vectors_and_measured_gap_json_safely(self):
        original = self.engine.completion_logps
        def shifted(*args, **kwargs):
            result = original(*args, **kwargs)
            result[args[1]:] += 1000.0
            return result
        with patch.object(self.engine, "completion_logps", side_effect=shifted):
            result = self.run_probe(max_new_tokens=3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "full_replay")
        self.assertGreater(result["full_max_abs_logp_gap"], 999)
        self.assertFalse(result["full_metrics"]["ratios_finite"])
        self.assertIsNone(result["full_metrics"]["importance_ratio_max"])
        self.assertEqual(len(result["full_replay"][0]["full_log_probs"]), 3)
        self.assertEqual(result["work"]["full_replay"]["forward_attempts"], 1)
        self.assertEqual(result["work"]["full_replay"]["forward_successes"], 1)
        json.dumps(result, allow_nan=False)

    def test_cached_interrupt_propagates_partial_nested_receipt(self):
        original = self.engine.model.forward
        calls = 0
        def forward(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 5:
                raise KeyboardInterrupt("stop cached replay")
            return original(*args, **kwargs)
        with patch.object(self.engine.model, "forward", side_effect=forward):
            with self.assertRaises(KeyboardInterrupt) as raised:
                self.run_probe(max_new_tokens=3)
        result = raised.exception.probability_probe_result
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "cached_replay")
        self.assertEqual(len(result["cached_replay"]["steps"]), 1)
        self.assertEqual(result["cached_max_abs_logp_gap"], 0.0)
        self.assertEqual(result["work"]["total"]["forward_attempts"], 5)
        self.assertEqual(result["work"]["total"]["forward_successes"], 4)

    def test_no_tolerance_relaxation_or_behavior_probability_replacement(self):
        original = self.engine.completion_logps
        def shifted(*args, **kwargs):
            result = original(*args, **kwargs)
            result[args[1]:] -= 0.1  # instrument diagnostic, never production repair
            return result
        with patch.object(self.engine, "completion_logps", side_effect=shifted):
            result = self.run_probe(max_new_tokens=4)
        self.assertEqual(result["status"], "completed")
        self.assertGreater(result["full_max_abs_logp_gap"], 0.05)
        self.assertEqual(result["cached_max_abs_logp_gap"], 0.0)
        self.assertFalse(result["training_authorized"])
        for index, row in enumerate(result["rows"]):
            self.assertEqual(row["behavior_log_probs"][row["prompt_length"]:], result["trace"]["completion_log_probs"][index])


if __name__ == "__main__":
    unittest.main()

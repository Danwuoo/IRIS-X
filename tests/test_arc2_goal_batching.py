"""Opt-in view batching: real Qwen cache semantics, deadlines and full accounting.

CPU numerical checks are not full-model CUDA throughput or ARC effectiveness.
"""
from __future__ import annotations

import copy
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.arc2_goal_sprint_20261017 import data, materials

MISSING = [name for name in ("torch", "transformers", "peft", "pydantic")
           if importlib.util.find_spec(name) is None]
if not MISSING:
    import torch
    from tools.arc2_goal_sprint_20261017 import model, run
    from tests.test_arc2_goal_model import tiny_engine


class BatchConfigurationTests(unittest.TestCase):
    def test_opt_in_strict_request_validation(self):
        self.assertEqual(materials.validate_solver_parameters(), {})
        for size in (1, 2, 4, 8):
            self.assertEqual(materials.validate_solver_parameters({"candidate_batch_size": size}),
                             {"candidate_batch_size": size})
        for size in (True, False, 0, -1, 3, 9, 16, 2.0, "2", None):
            with self.subTest(size=size), self.assertRaises(ValueError):
                materials.validate_solver_parameters({"candidate_batch_size": size})


@unittest.skipIf(bool(MISSING), "Optional ML dependencies missing: " + ", ".join(MISSING))
class BatchedQwenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_unequal_prompts_real_cached_fp32_replay_and_forward_reduction(self):
        engine = tiny_engine()
        prompts = [[1], [2, 3, 4], [5, 6, 7, 8, 9]]
        before = copy.deepcopy(prompts)
        rng = torch.get_rng_state().clone()
        state = model.state_digest(model.adapter_state(engine.model))
        batched = engine.generate_prompts(prompts, max_new_tokens=6)
        batch_calls = engine.forward_calls
        single = [engine.generate(p, max_new_tokens=6)[0] for p in prompts]
        self.assertEqual(prompts, before)
        self.assertEqual(state, model.state_digest(model.adapter_state(engine.model)))
        torch.testing.assert_close(rng, torch.get_rng_state(), atol=0, rtol=0)
        self.assertLess(batch_calls, engine.forward_calls - batch_calls)
        for prompt, left, right in zip(prompts, batched, single):
            self.assertEqual(left["input_ids"], right["input_ids"])
            self.assertEqual(left["prompt_length"], len(prompt))
            self.assertEqual(left["input_ids"][:len(prompt)], prompt)
            replay = engine.completion_logps(left["input_ids"], len(prompt)).detach()
            torch.testing.assert_close(replay, torch.tensor(left["behavior_log_probs"]), atol=1e-6, rtol=1e-6)

    def test_left_padding_positions_masks_and_aliases_are_explicit(self):
        engine = tiny_engine()
        shared = [1, 2]
        prompts = [shared, [3, 4, 5, 6], shared]
        original = engine.model.forward
        observed = []
        def forward(*args, **kwargs):
            observed.append({k: kwargs[k].detach().clone() for k in ("input_ids", "attention_mask", "position_ids")})
            return original(*args, **kwargs)
        with patch.object(engine.model, "forward", side_effect=forward):
            result = engine.generate_prompts(prompts, max_new_tokens=3)
        self.assertEqual(shared, [1, 2])
        self.assertEqual(observed[0]["attention_mask"].tolist(), [[0, 0, 1, 1], [1, 1, 1, 1], [0, 0, 1, 1]])
        self.assertEqual(observed[0]["position_ids"].tolist(), [[0, 0, 0, 1], [0, 1, 2, 3], [0, 0, 0, 1]])
        self.assertEqual(observed[1]["position_ids"].tolist(), [[2], [4], [2]])
        self.assertEqual(observed[2]["position_ids"].tolist(), [[3], [5], [3]])
        self.assertEqual(result[0]["input_ids"], result[2]["input_ids"])
        self.assertIsNot(result[0]["input_ids"], result[2]["input_ids"])

    def test_finished_rows_retain_neither_padding_nor_filler(self):
        engine = tiny_engine()
        engine.tokenizer.eos_token_id = 0
        engine.tokenizer.encode = lambda text, **kwargs: [30, 31]
        engine.model.generation_config.eos_token_id = [0, 29]
        forced = [[0, 30, 4], [6, 31, 5], [6, 7, 29]]
        original = engine.model.forward
        def forward(*args, **kwargs):
            out = original(*args, **kwargs)
            out.logits.fill_(-100)
            for row, token in enumerate(forced.pop(0)):
                out.logits[row, -1, token] = 0
            return out
        prompts = [[1], [2, 3], [4, 5, 6]]
        with patch.object(engine.model, "forward", side_effect=forward):
            rows = engine.generate_prompts(prompts, max_new_tokens=8)
        self.assertEqual([r["completion_tokens"] for r in rows], [1, 2, 3])
        self.assertEqual([r["input_ids"][len(p):] for p, r in zip(prompts, rows)], [[0], [30, 31], [4, 5, 29]])
        self.assertEqual(engine.sampled_tokens, 6)
        self.assertTrue(all(r["stop"] == "completed" for r in rows))

    def test_late_forward_is_charged_but_returns_no_candidates(self):
        engine = tiny_engine()
        now = [100.]
        original = engine.model.forward
        def forward(*args, **kwargs):
            result = original(*args, **kwargs)
            now[0] = 102.
            return result
        with patch.object(model, "time", SimpleNamespace(time=lambda: now[0])), \
             patch.object(engine.model, "forward", side_effect=forward), self.assertRaises(model.PhaseDeadline):
            engine.generate_prompts([[1], [2, 3]], max_new_tokens=1, deadline=101.)
        self.assertEqual(engine.forward_calls, 1)
        self.assertEqual(engine.sampled_tokens, 2)

    def test_late_tokenizer_decode_is_rejected(self):
        engine = tiny_engine()
        now = [100.]
        original = engine.tokenizer.decode
        def decode(*args, **kwargs):
            result = original(*args, **kwargs)
            now[0] = 102.
            return result
        with patch.object(model, "time", SimpleNamespace(time=lambda: now[0])), \
             patch.object(engine.tokenizer, "decode", side_effect=decode), self.assertRaises(model.PhaseDeadline):
            engine.generate_prompts([[1], [2, 3]], max_new_tokens=1, deadline=101.)

    def test_nonfinite_logits_and_invalid_token_inputs_fail_closed(self):
        engine = tiny_engine()
        original = engine.model.forward
        def forward(*args, **kwargs):
            out = original(*args, **kwargs)
            out.logits[0, -1, 0] = float("nan")
            return out
        with patch.object(engine.model, "forward", side_effect=forward), self.assertRaises(FloatingPointError):
            engine.generate_prompts([[1], [2]])
        for prompts in ([], [[]], [[True]], [[1.0]], [[-1]], [[32]], [[1]] * 9):
            with self.subTest(prompts=prompts), self.assertRaises(ValueError):
                engine.generate_prompts(prompts)

    def test_bfloat16_cached_probabilities_replay_own_tokens_not_singleton_claim(self):
        engine = tiny_engine(seed=13)
        for parameter in engine.model.parameters():
            if not parameter.requires_grad:
                parameter.data = parameter.data.to(torch.bfloat16)
        prompts = [[(i + offset) % 31 + 1 for i in range(length)]
                   for offset, length in enumerate((1, 2, 5, 8, 16, 24, 31, 40))]
        rows = engine.generate_prompts(prompts, max_new_tokens=12)
        for prompt, row in zip(prompts, rows):
            replay = engine.completion_logps(row["input_ids"], len(prompt)).detach()
            actual = torch.tensor(row["behavior_log_probs"])
            self.assertTrue(torch.isfinite(replay).all())
            self.assertLess((replay - actual).abs().max().item(), .05)
        # BF16 batching can change near-tie greedy choices: deliberately do not
        # assert equal candidates to singleton inference or any score benefit.


@unittest.skipIf(bool(MISSING), "Optional ML dependencies missing: " + ", ".join(MISSING))
class BatchedViewAccountingTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.engine = tiny_engine()
        self.task = {"train": [{"input": [[1]], "output": [[2]]}], "test": [{"input": [[3]]}]}
        self.cfg = {"run_id": "synthetic", "seed": 1, "ttt_steps": 0, "context_tokens": 128,
                    "generation_tokens": 32, "candidate_views": 8, "candidate_ranker": "vote", "candidate_batch_size": 4}
        self.views = data.inference_views(8, seed=1, task_id="synthetic", demo_count=1)
        self.grids = [[[1, 2]], [[2, 3]], [[3, 4]]]
        self.choices = [0, 1, 1, 2, 2, 2, 2, 0]
        self.outputs = [{"text": data.answer_text(data.transform(self.grids[i], **v["transform"])),
                         "completion_tokens": 9, "stop": "completed"} for i, v in zip(self.choices, self.views)]

    def solve(self, function, **kwargs):
        with patch.object(self.engine, "generate_prompts", side_effect=function):
            return run.solve_query_views(self.engine, self.task, [[3]], self.cfg, lambda *a, **k: None,
                    task_id="synthetic", query_index=0, deadline=kwargs.get("deadline", math.inf))

    def test_fixed_order_inverse_dedup_top_two_and_batch_counts(self):
        outputs = list(self.outputs)
        sizes = []
        def generate(prompts, **kwargs):
            sizes.append(len(prompts))
            result, outputs[:] = outputs[:len(prompts)], outputs[len(prompts):]
            return result
        result, full = self.solve(generate)
        self.assertEqual(sizes, [4, 4])
        self.assertEqual(result["ranked_grids"], [self.grids[2], self.grids[0]])
        self.assertEqual([r["votes"] for r in full["candidates"]], [2, 2, 4])
        self.assertEqual([r["view"] for r in full["views"]], list(range(8)))
        self.assertEqual(len(full["generation_attempts"]), 2)
        self.assertEqual(result["status"], "complete")

    def test_oom_fallback_once_per_view_no_duplicate_votes_or_deadline_reset(self):
        outputs = list(self.outputs)
        calls = []
        def generate(prompts, **kwargs):
            calls.append((len(prompts), kwargs["deadline"]))
            self.engine.forward_calls += 1
            self.engine.sampled_tokens += len(prompts)
            if len(calls) == 1:
                raise torch.cuda.OutOfMemoryError("synthetic batch OOM")
            return [outputs.pop(0)]
        with patch.object(run, "time", SimpleNamespace(time=lambda: 100.)), \
             patch.object(model, "time", SimpleNamespace(time=lambda: 100.)):
            result, full = self.solve(generate, deadline=200.)
        self.assertEqual([n for n, _ in calls], [4] + [1] * 8)
        self.assertTrue(all(d <= 150. for _, d in calls[:5]))
        self.assertEqual(sum(r["votes"] for r in full["candidates"]), 8)
        self.assertEqual(full["generation_attempts"][0]["failure"], "OutOfMemoryError")
        self.assertEqual(full["generation_attempts"][0]["generated_token_work"], 4)
        self.assertEqual(full["views"][0]["attempts"], [0, 1])
        self.assertTrue(full["oom_demoted_to_singletons"])
        self.assertEqual(result["status"], "complete")

    def test_malformed_whole_batch_has_no_partial_votes_and_no_retry(self):
        calls = []
        def generate(prompts, **kwargs):
            calls.append(len(prompts))
            return self.outputs[:len(prompts) - 1]
        result, full = self.solve(generate)
        self.assertEqual(calls, [4, 4])
        self.assertEqual(result["ranked_grids"], [])
        self.assertEqual(result["status"], "failed")
        self.assertTrue(all(r["failure"] == "ValueError" for r in full["generation_attempts"]))
        self.assertEqual(len(full["views"]), 8)

    def test_unhashable_stop_and_nonfinite_failure_remain_audited_no_retry(self):
        for mode in ("bad_stop", "nonfinite"):
            calls = []
            def generate(prompts, **kwargs):
                calls.append(len(prompts))
                if mode == "nonfinite":
                    raise FloatingPointError("synthetic nonfinite")
                return [{**self.outputs[0], "stop": []} for _ in prompts]
            result, full = self.solve(generate)
            self.assertEqual(calls, [4, 4])
            self.assertEqual(result["ranked_grids"], [])
            self.assertTrue(all(r["status"] == "failed" for r in full["generation_attempts"]))

    def test_sixteen_views_in_two_eight_row_batches(self):
        self.cfg.update(candidate_views=16, candidate_batch_size=8)
        calls = []
        def generate(prompts, **kwargs):
            calls.append(len(prompts))
            return [{"text": "invalid", "completion_tokens": 1, "stop": "length"} for _ in prompts]
        result, full = self.solve(generate)
        self.assertEqual(calls, [8, 8])
        self.assertEqual(len(full["views"]), 16)
        self.assertEqual(result["ranked_grids"], [])
        self.assertEqual(result["status"], "complete")

    def test_one_context_rejection_does_not_drop_other_ordered_views(self):
        original = run.encode_example
        encodes, sizes = [], []
        def encode(*args, **kwargs):
            encodes.append(1)
            if len(encodes) == 2:
                raise ValueError("synthetic complete query cannot fit")
            return original(*args, **kwargs)
        def generate(prompts, **kwargs):
            sizes.append(len(prompts))
            return [{"text": "invalid", "completion_tokens": 1, "stop": "length"} for _ in prompts]
        with patch.object(run, "encode_example", side_effect=encode):
            _, full = self.solve(generate)
        self.assertEqual(sizes, [3, 4])
        self.assertEqual(full["views"][1]["failure"], "ValueError")
        self.assertEqual(full["views"][1]["attempts"], [])
        self.assertEqual([r["view"] for r in full["views"]], list(range(8)))
        self.assertEqual(sum(r["status"] == "complete" for r in full["views"]), 7)

    def test_oom_exhausted_group_does_not_dispatch_late_singletons(self):
        now, calls = [100.], []
        def generate(prompts, **kwargs):
            calls.append((len(prompts), kwargs["deadline"]))
            if len(calls) == 1:
                now[0] = 150.
                raise torch.cuda.OutOfMemoryError("synthetic full budget OOM")
            return [{"text": "invalid", "completion_tokens": 1, "stop": "length"}]
        with patch.object(run, "time", SimpleNamespace(time=lambda: now[0])), \
             patch.object(model, "time", SimpleNamespace(time=lambda: now[0])):
            _, full = self.solve(generate, deadline=200.)
        self.assertEqual([n for n, _ in calls], [4, 1, 1, 1, 1])
        self.assertTrue(all(not r["generation_invoked"] for r in full["generation_attempts"][1:5]))
        self.assertTrue(all(r["failure"] == "PhaseDeadline" for r in full["views"][:4]))

    def test_rerank_reserve_covers_batch_and_oom_fallback(self):
        self.cfg.update(candidate_ranker="cross_view_likelihood")
        calls = []
        def generate(prompts, **kwargs):
            calls.append(kwargs["deadline"])
            if len(calls) == 1:
                raise torch.cuda.OutOfMemoryError("synthetic OOM")
            return [{"text": "invalid", "completion_tokens": 1, "stop": "length"}]
        with patch.object(run, "time", SimpleNamespace(time=lambda: 100.)), \
             patch.object(model, "time", SimpleNamespace(time=lambda: 100.)):
            _, full = self.solve(generate, deadline=200.)
        self.assertEqual(full["rerank_budget_fraction"], .25)
        self.assertTrue(all(d <= 175. for d in calls))
        self.assertTrue(all(d <= 137.5 for d in calls[:5]))

    def test_expired_batched_public_keeps_full_120_167_denominator(self):
        public = {f"synthetic-{i:03}": {"train": self.task["train"],
                  "test": [{"input": [[3]]}] * (2 if i < 47 else 1)} for i in range(120)}
        self.cfg.update(candidate_views=16, candidate_batch_size=8)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(self.engine, "generate_prompts", side_effect=AssertionError("expired batch dispatched")):
            pools = run.solve_public(self.engine, public, model.adapter_state(self.engine.model), self.cfg,
                        lambda *a, **k: None, Path(directory), deadline=0.)
            from tools.arc2_goal_sprint_20261017.launch import candidate_audit
            audit = candidate_audit(Path(directory) / "full-candidate-pools.json", pools)
        self.assertEqual(len(pools["records"]), 120)
        self.assertEqual(sum(len(r["tests"]) for r in pools["records"]), 167)
        self.assertEqual(audit["queries"], 167)
        self.assertTrue(audit["complete_coverage"])
        self.assertTrue(all(t["ranked_grids"] == [] for r in pools["records"] for t in r["tests"]))

    def test_expiry_preserves_all_view_receipts_without_dispatch(self):
        result, full = self.solve(AssertionError("expired generation dispatched"), deadline=0.)
        self.assertEqual(result["ranked_grids"], [])
        self.assertEqual(len(full["views"]), 8)
        self.assertEqual(full["generation_attempts"], [])
        self.assertTrue(all(r["failure"] == "PhaseDeadline" for r in full["views"]))

    def test_late_batch_return_is_rejected_before_votes(self):
        now = [100.]
        def generate(prompts, **kwargs):
            now[0] = 201.
            return self.outputs[:len(prompts)]
        with patch.object(run, "time", SimpleNamespace(time=lambda: now[0])), \
             patch.object(model, "time", SimpleNamespace(time=lambda: now[0])):
            result, full = self.solve(generate, deadline=200.)
        self.assertEqual(result["ranked_grids"], [])
        self.assertEqual(len(full["generation_attempts"]), 1)
        self.assertEqual(full["generation_attempts"][0]["failure"], "PhaseDeadline")

    def test_default_stays_serial_and_two_view_batch_is_explicitly_audited(self):
        self.assertEqual(run.continuation_options({})["candidate_batch_size"], 1)
        for invalid in (True, 0, 3, 2.0):
            with self.assertRaises(ValueError):
                run.continuation_options({"candidate_batch_size": invalid})
        cfg = {**self.cfg, "candidate_views": 2, "candidate_ranker": "first", "candidate_batch_size": 2}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(self.engine, "generate_prompts", return_value=self.outputs[:2]), \
             patch.object(self.engine, "generate", side_effect=AssertionError("legacy sampler used")):
            pools = run.solve_public(self.engine, {"synthetic": self.task}, model.adapter_state(self.engine.model),
                        cfg, lambda *a, **k: None, Path(directory), deadline=math.inf)
            self.assertTrue((Path(directory) / "full-candidate-pools.json").is_file())
        self.assertEqual(len(pools["records"][0]["tests"][0]["ranked_grids"]), 2)


if __name__ == "__main__":
    unittest.main()

"""Compact view batching CPU contracts, not official-weight/GPU validation."""
from __future__ import annotations

import copy
import gc
import importlib.util
import math
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from tools.arc2_goal_sprint_20261017.data import inference_views, transform, view_inputs
from tools.nvarc_posttrain_20261017 import batched_inference as batching
from tools.nvarc_posttrain_20261017.codec import encode_example, grid_tokens


class PhaseDeadline(RuntimeError):
    pass


class OutOfMemoryError(RuntimeError):
    pass


class FakeEngine:
    """Exercise the production dispatcher without importing optional ML code."""
    def __init__(self, script=None):
        for name in batching.WORK_COUNTERS:
            setattr(self, name, 0)
        self.calls, self.script = [], script

    def dispatch(self, prompts, *, step=0, finished=0, completed=True):
        count, width = len(prompts), max(map(len, prompts))
        self.generation_forward_attempts += 1
        self.generation_input_tokens += count * (width if step == 0 else 1)
        self.generation_row_token_slots += count
        self.generation_finished_row_token_slots += finished
        self.generation_padding_tokens += count * width - sum(map(len, prompts)) if step == 0 else 0
        if completed:
            self.forward_calls += 1
            self.sampled_tokens += count - finished

    def rows(self, prompts, completions=None, nlls=None):
        completions = [[13, 15] for _ in prompts] if completions is None else completions
        nlls = [0.5] * len(prompts) if nlls is None else nlls
        for step in range(max(map(len, completions))):
            self.dispatch(prompts, step=step, finished=sum(len(row) <= step for row in completions))
        return [{"input_ids": list(prompt) + list(completion), "prompt_length": len(prompt),
                 "completion_ids": list(completion), "completion_tokens": len(completion),
                 "behavior_log_probs": [0.0] * len(prompt) + [-nll] * len(completion),
                 "stop": "completed" if completion[-1] == 15 else "length"}
                for prompt, completion, nll in zip(prompts, completions, nlls)]

    def generate_prompts(self, prompts, **kwargs):
        self.calls.append((copy.deepcopy(prompts), dict(kwargs)))
        return self.script(self, prompts, kwargs) if self.script else self.rows(prompts)


class BatchedCompactFakeTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.task = {"train": [{"input": [[1, 2]], "output": [[2, 1]]},
                               {"input": [[3]], "output": [[4]]}]}
        self.query = [[3, 4, 5]]
        self.cfg = {"context_tokens": 128, "generation_tokens": 8,
                    "inference_batch_size": 2, "seed": 1}
        self.engine = FakeEngine()
        self.release = []

        def check(deadline):
            if self.now >= deadline:
                raise PhaseDeadline("synthetic deadline")

        def release():
            self.assertIsNone(sys.exc_info()[1])
            gc.collect()
            self.release.append(True)

        self.enterContext(patch.object(batching, "_runtime", return_value=(
            PhaseDeadline, OutOfMemoryError, check, release)))
        self.enterContext(patch.object(batching, "time", SimpleNamespace(time=lambda: self.now)))

    def solve(self, *, views=8, deadline=200.0):
        return batching.infer_query_batched(self.engine, self.task, self.query, self.cfg,
                                           task_id="synthetic", views=views, deadline=deadline)

    def test_strict_batch_sizes_and_distinct_protocol_identity(self):
        self.assertEqual(batching.protocol_identity({})["inference_batch_size"], 1)
        self.assertNotEqual(batching.protocol_identity({}), batching.protocol_identity(self.cfg))
        self.assertFalse(batching.protocol_identity(self.cfg)["batch_numerical_parity_claimed"])
        for value in (True, False, 0, -1, 3, 4, 8, 2.0, "2", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                batching.protocol_identity({"inference_batch_size": value})

    def test_invalid_deadlines_bounds_and_counters_rejected_before_dispatch(self):
        for deadline in (True, float("nan"), -math.inf, "200"):
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                self.solve(deadline=deadline)
        for key, value in (("generation_tokens", True), ("generation_tokens", 932),
                           ("context_tokens", 8193), ("context_tokens", 0)):
            with self.subTest(key=key, value=value), patch.dict(self.cfg, {key: value}), self.assertRaises(ValueError):
                self.solve()
        for value in (None, -1, True, 0.0):
            self.engine.generation_row_token_slots = value
            with self.assertRaisesRegex(ValueError, "counter required"):
                self.solve()
        self.assertEqual(self.engine.calls, [])

    def test_fixed_compact_prompts_inverse_dedup_nll_tie_and_top_two(self):
        specs = inference_views(8, seed=20261017, task_id="synthetic", demo_count=2)
        grids = [[[1, 2]], [[2, 3]], [[3, 4]]]
        choices, nlls = [0, 1, 1, 2, 2, 2, 2, 0], [0.8, 0.2, 0.2, 0.9, 0.9, 0.9, 0.9, 0.8]
        remaining = list(range(8))

        def generate(engine, prompts, kwargs):
            indices = [remaining.pop(0) for _ in prompts]
            completion = [grid_tokens(transform(grids[choices[i]], **specs[i]["transform"])) + [15] for i in indices]
            return engine.rows(prompts, completion, [nlls[i] for i in indices])

        self.engine.script = generate
        original_task, original_query = copy.deepcopy(self.task), copy.deepcopy(self.query)
        result = self.solve()
        self.assertEqual([len(prompts) for prompts, _ in self.engine.calls], [2] * 4)
        expected = [encode_example(*view_inputs(self.task, self.query, spec), context=128, generation=8)["prompt_ids"] for spec in specs]
        self.assertEqual([prompt for prompts, _ in self.engine.calls for prompt in prompts], expected)
        self.assertTrue(all(set(kwargs) == {"max_new_tokens", "deadline"} for _, kwargs in self.engine.calls))
        self.assertEqual(result["ranked_grids"], [grids[2], grids[1]])
        self.assertEqual(result["ranked_candidate_indices"], [2, 1, 0])
        self.assertEqual([row["votes"] for row in result["candidates"]], [2, 2, 4])
        self.assertEqual([row["view"] for row in result["views"]], list(range(8)))
        self.assertTrue(result["complete"])
        self.assertEqual(self.task, original_task)
        self.assertEqual(self.query, original_query)
        self.assertEqual(result["ranking"], batching.RANKING)

    def test_exact_equal_votes_and_nll_keep_first_view_tie_order(self):
        specs = inference_views(2, seed=20261017, task_id="synthetic", demo_count=2)
        grids = [[[5]], [[6]]]
        self.engine.script = lambda engine, prompts, kwargs: engine.rows(prompts,
            [grid_tokens(transform(grid, **spec["transform"])) + [15] for grid, spec in zip(grids, specs)])
        self.assertEqual(self.solve(views=2)["ranked_grids"], grids)

    def test_training_seed_does_not_change_view_protocol_or_prompts(self):
        first = self.solve()
        prompts = copy.deepcopy(self.engine.calls)
        self.cfg["seed"] = 987654
        self.engine = FakeEngine()
        second = self.solve()
        self.assertEqual(first["view_specs_sha256"], second["view_specs_sha256"])
        self.assertEqual(prompts, self.engine.calls)
        self.cfg["evaluation_seed"] = 987654
        self.engine = FakeEngine()
        self.assertNotEqual(first["view_specs_sha256"], self.solve()["view_specs_sha256"])

    def test_invalid_grid_completes_view_without_candidate_or_legacy_text_parse(self):
        self.engine.script = lambda engine, prompts, kwargs: [dict(row, text="[[9]]") for row in engine.rows(prompts)]
        result = self.solve(views=2)
        self.assertTrue(result["complete"])
        self.assertEqual(result["ranked_grids"], [])
        self.assertTrue(all(not row["valid"] for row in result["views"]))

    def test_failed_work_padding_and_finished_rows_counted_not_only_committed_tokens(self):
        def generate(engine, prompts, kwargs):
            if len(engine.calls) == 1:
                engine.dispatch(prompts, completed=False)
                raise OutOfMemoryError("failed before completed forward")
            return engine.rows(prompts)

        self.engine.script = generate
        result = self.solve(views=2)
        work, first = result["generation_work"], result["generation_attempts"][0]
        self.assertEqual(first["generation_forward_attempts"], 1)
        self.assertEqual(first["forward_calls"], 0)
        self.assertEqual(first["generation_row_token_slots"], 2)
        self.assertEqual(first["committed_completion_tokens"], 0)
        self.assertEqual(work["generation_row_token_slots"], 6)
        self.assertEqual(work["sampled_tokens"], work["committed_completion_tokens"])
        self.assertGreater(first["generation_padding_tokens"], 0)
        self.engine = FakeEngine(lambda engine, prompts, kwargs: engine.rows(prompts, [[15], [1, 2, 15]]))
        result = self.solve(views=2)
        self.assertEqual(result["generation_work"]["generation_finished_row_token_slots"], 2)
        self.assertEqual(result["generation_work"]["generation_row_token_slots"], 6)
        self.assertEqual(result["generation_work"]["committed_completion_tokens"], 4)

    def test_oom_retries_each_member_once_without_duplicate_votes_or_deadline_reset(self):
        def generate(engine, prompts, kwargs):
            if len(engine.calls) == 1:
                engine.dispatch(prompts)
                raise OutOfMemoryError("synthetic batch failure")
            return engine.rows(prompts, [[2, 15]])

        self.engine.script = generate
        result = self.solve()
        self.assertEqual([len(prompts) for prompts, _ in self.engine.calls], [2] + [1] * 8)
        self.assertTrue(result["complete"])
        self.assertTrue(result["oom_demoted_to_singletons"])
        self.assertEqual(sum(row["votes"] for row in result["candidates"]), 8)
        self.assertEqual(result["views"][0]["attempts"], [0, 1])
        self.assertEqual(result["views"][1]["attempts"], [0, 2])
        original_until = self.engine.calls[0][1]["deadline"]
        self.assertTrue(all(kwargs["deadline"] <= original_until for _, kwargs in self.engine.calls[1:3]))
        self.assertEqual(result["generation_work"]["sampled_tokens"], 18)
        self.assertEqual(result["generation_work"]["committed_completion_tokens"], 16)
        self.assertEqual(len(self.release), 1)

    def test_oom_exception_frames_released_before_singleton_fallback(self):
        refs = []

        class Payload:
            pass

        def generate(engine, prompts, kwargs):
            if len(engine.calls) == 1:
                payload = Payload()
                refs.append(weakref.ref(payload))
                raise OutOfMemoryError("do not retain this frame")
            self.assertIsNone(refs[0]())
            self.assertIsNone(sys.exc_info()[1])
            return engine.rows(prompts)

        self.engine.script = generate
        self.assertTrue(self.solve(views=2)["complete"])
        self.assertIsNone(refs[0]())

    def test_repeated_singleton_ooms_never_retry_singleton(self):
        def generate(engine, prompts, kwargs):
            engine.dispatch(prompts, completed=False)
            raise OutOfMemoryError("all allocations fail")

        self.engine.script = generate
        result = self.solve()
        self.assertEqual([len(prompts) for prompts, _ in self.engine.calls], [2] + [1] * 8)
        self.assertFalse(result["complete"])
        self.assertEqual(result["generation_work"]["generation_row_token_slots"], 10)
        self.engine = FakeEngine(generate)
        self.cfg["inference_batch_size"] = 1
        result = self.solve()
        self.assertEqual(len(self.engine.calls), 8)
        self.assertTrue(all(len(row["attempts"]) == 1 for row in result["views"]))

    def test_other_known_failures_are_counted_without_resampling(self):
        for error in (ValueError, FloatingPointError):
            def generate(engine, prompts, kwargs):
                engine.dispatch(prompts)
                raise error("failed numerical result")
            with self.subTest(error=error):
                self.engine = FakeEngine(generate)
                result = self.solve()
                self.assertEqual(len(self.engine.calls), 4)
                self.assertEqual(result["ranked_grids"], [])
                self.assertFalse(result["oom_demoted_to_singletons"])
                self.assertEqual(result["generation_work"]["sampled_tokens"], 8)
                self.assertEqual(result["generation_work"]["committed_completion_tokens"], 0)
                self.assertTrue(all(row["failure"] == error.__name__ for row in result["generation_attempts"]))

    def test_unexpected_failure_propagates_and_never_resamples(self):
        def generate(engine, prompts, kwargs):
            engine.dispatch(prompts, completed=False)
            raise RuntimeError("unexpected programming failure")

        self.engine.script = generate
        with self.assertRaisesRegex(RuntimeError, "unexpected programming"):
            self.solve()
        self.assertEqual(len(self.engine.calls), 1)
        self.assertEqual(self.engine.generation_forward_attempts, 1)

    def test_malformed_whole_batch_is_atomic_and_never_retried(self):
        def prefix(rows):
            rows[-1]["input_ids"][0] = 9
        mutations = {
            "missing_row": lambda rows: rows.pop(), "prefix": prefix,
            "bool_count": lambda rows: rows[-1].update(completion_tokens=True),
            "bool_prompt_length": lambda rows: rows[-1].update(prompt_length=True),
            "bad_token": lambda rows: rows[-1]["input_ids"].__setitem__(-1, 16),
            "nan_logp": lambda rows: rows[-1]["behavior_log_probs"].__setitem__(-1, math.nan),
            "infinite_logp": lambda rows: rows[-1]["behavior_log_probs"].__setitem__(-1, math.inf),
            "bad_stop": lambda rows: rows[-1].update(stop=[]),
            "incomplete_length": lambda rows: rows[-1].update(stop="length"),
            "completion_mismatch": lambda rows: rows[-1].update(completion_ids=[3, 15]),
        }
        for name, mutate in mutations.items():
            def generate(engine, prompts, kwargs):
                rows = engine.rows(prompts, [[2, 15]] * len(prompts))
                mutate(rows)
                return rows
            with self.subTest(name=name):
                self.engine = FakeEngine(generate)
                result = self.solve()
                self.assertEqual(len(self.engine.calls), 4)
                self.assertEqual(result["ranked_grids"], [])
                self.assertFalse(result["complete"])
                self.assertTrue(all(row["failure"] == "ValueError" for row in result["generation_attempts"]))

    def test_context_rejection_preserves_other_ordered_views_without_retry(self):
        original, encodes = batching.encode_example, []

        def encode(*args, **kwargs):
            encodes.append(True)
            if len(encodes) == 2:
                raise ValueError("whole query cannot fit")
            return original(*args, **kwargs)

        with patch.object(batching, "encode_example", side_effect=encode):
            result = self.solve()
        self.assertEqual([len(prompts) for prompts, _ in self.engine.calls], [1, 2, 2, 2])
        self.assertEqual(result["views"][1]["attempts"], [])
        self.assertEqual(result["views"][1]["failure"], "ValueError")
        self.assertEqual(result["generation_work"]["completed_views"], 7)
        self.assertFalse(result["complete"])

    def test_expiry_before_dispatch_keeps_all_view_receipts_and_zero_work(self):
        result = self.solve(deadline=100.0)
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(result["generation_attempts"], [])
        self.assertEqual(len(result["views"]), 8)
        self.assertTrue(all(row["failure"] == "PhaseDeadline" for row in result["views"]))
        self.assertTrue(all(result["generation_work"][name] == 0 for name in batching.WORK_COUNTERS))

    def test_late_batch_rejected_before_votes_but_physical_work_not_erased(self):
        def generate(engine, prompts, kwargs):
            result = engine.rows(prompts, [[2, 15]] * len(prompts))
            self.now = 201.0
            return result

        self.engine.script = generate
        result = self.solve()
        self.assertEqual(len(self.engine.calls), 1)
        self.assertEqual(result["ranked_grids"], [])
        self.assertEqual(result["generation_work"]["sampled_tokens"], 4)
        self.assertEqual(result["generation_work"]["committed_completion_tokens"], 0)

    def test_expired_oom_group_has_no_late_retry_and_does_not_reset_phase_budget(self):
        def generate(engine, prompts, kwargs):
            if len(engine.calls) == 1:
                self.now = kwargs["deadline"]
                engine.dispatch(prompts, completed=False)
                raise OutOfMemoryError("OOM consumed group budget")
            return engine.rows(prompts)

        self.engine.script = generate
        result = self.solve()
        self.assertEqual([len(prompts) for prompts, _ in self.engine.calls], [2] + [1] * 6)
        self.assertTrue(all(not row["generation_invoked"] for row in result["generation_attempts"][1:3]))
        self.assertTrue(all(row["failure"] == "PhaseDeadline" for row in result["views"][:2]))
        self.assertTrue(all(kwargs["deadline"] <= 200.0 for _, kwargs in self.engine.calls))

    def test_batch_one_two_and_sixteen_views_are_bounded_and_json_serializable(self):
        import json
        for size in (1, 2):
            self.cfg["inference_batch_size"] = size
            self.engine = FakeEngine()
            result = self.solve(views=16, deadline=math.inf)
            self.assertEqual(len(self.engine.calls), 16 // size)
            self.assertEqual(len(result["views"]), 16)
            self.assertTrue(result["complete"])
            json.dumps(result, allow_nan=False)


_MISSING = [name for name in ("torch", "transformers", "peft", "pydantic", "tokenizers", "safetensors")
            if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine


@unittest.skipIf(bool(_MISSING), "Optional compact model dependencies missing: " + ", ".join(_MISSING))
class BatchedCompactActualCPUTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_real_compact_fp32_left_padding_cached_positions_and_singleton_parity(self):
        engine = tiny_engine()
        prompts = [[14, 12, 10], [14, 11, 10, 1, 2, 15, 10, 14, 12, 10]]
        captured = []

        def observe(module, args, kwargs):
            captured.append({key: kwargs[key].detach().clone() for key in ("input_ids", "attention_mask", "position_ids")})

        handle = engine.model.register_forward_pre_hook(observe, with_kwargs=True)
        try:
            rows = engine.generate_prompts(prompts, max_new_tokens=7)
        finally:
            handle.remove()
        expected_mask = torch.tensor([[0] * 7 + [1] * 3, [1] * 10])
        torch.testing.assert_close(captured[0]["attention_mask"], expected_mask)
        torch.testing.assert_close(captured[0]["position_ids"], (expected_mask.cumsum(-1) - 1).clamp(min=0))
        torch.testing.assert_close(captured[0]["input_ids"][0, :7], torch.full((7,), 13))
        if len(captured) > 1:
            torch.testing.assert_close(captured[1]["position_ids"], torch.tensor([[3], [10]]))
        steps = max(row["completion_tokens"] for row in rows)
        self.assertEqual(engine.generation_forward_attempts, steps)
        self.assertEqual(engine.generation_padding_tokens, 7)
        self.assertEqual(engine.generation_row_token_slots, 2 * steps)
        self.assertEqual(engine.generation_input_tokens, 20 + 2 * (steps - 1))
        self.assertEqual(engine.generation_finished_row_token_slots,
                         2 * steps - sum(row["completion_tokens"] for row in rows))
        for prompt, row in zip(prompts, rows):
            singleton = engine.generate(prompt, max_new_tokens=7)[0]
            self.assertEqual(row["input_ids"], singleton["input_ids"])
            torch.testing.assert_close(torch.tensor(row["behavior_log_probs"]),
                                       torch.tensor(singleton["behavior_log_probs"]), atol=1e-6, rtol=1e-6)

    def test_production_helper_uses_real_compact_engine_for_both_batch_sizes(self):
        engine = tiny_engine()
        task = {"train": [{"input": [[1, 2]], "output": [[2, 1]]}]}
        reports = []
        for size in (1, 2):
            reports.append(batching.infer_query_batched(engine, task, [[3, 4, 5]],
                {"context_tokens": 128, "generation_tokens": 7, "inference_batch_size": size},
                task_id="synthetic-real-cpu", views=8, deadline=math.inf))
        self.assertTrue(all(report["complete"] for report in reports))
        self.assertEqual([len(report["generation_attempts"]) for report in reports], [8, 4])
        self.assertEqual(reports[0]["view_specs_sha256"], reports[1]["view_specs_sha256"])
        self.assertEqual(reports[0]["ranked_grids"], reports[1]["ranked_grids"])
        self.assertLess(reports[1]["generation_work"]["forward_calls"], reports[0]["generation_work"]["forward_calls"])

    def test_actual_engine_finished_row_slots_and_failed_forward_submission(self):
        engine = tiny_engine()
        choices = iter([[15, 3], [1, 4], [2, 15]])

        def forward(**kwargs):
            logits = torch.full((2, 1, 16), -20.0)
            for index, token in enumerate(next(choices)):
                logits[index, 0, token] = 20.0
            return SimpleNamespace(logits=logits, past_key_values=None)

        with patch.object(engine.model, "forward", side_effect=forward):
            rows = engine.generate_prompts([[14, 12, 10], [14, 11, 10, 1, 15, 14, 12, 10]], max_new_tokens=7)
        self.assertEqual([row["completion_tokens"] for row in rows], [1, 3])
        self.assertEqual(engine.generation_finished_row_token_slots, 2)
        self.assertEqual(engine.generation_row_token_slots, 6)
        self.assertEqual(engine.sampled_tokens, 4)
        before = batching._snapshot(engine)
        with patch.object(engine.model, "forward", side_effect=torch.cuda.OutOfMemoryError("synthetic CPU failure")):
            with self.assertRaises(torch.cuda.OutOfMemoryError):
                engine.generate_prompts([[14, 12, 10]], max_new_tokens=1)
        work = batching._delta(engine, before)
        self.assertEqual(work["generation_forward_attempts"], 1)
        self.assertEqual(work["generation_input_tokens"], 3)
        self.assertEqual(work["generation_row_token_slots"], 1)
        self.assertEqual(work["forward_calls"], 0)
        self.assertEqual(work["sampled_tokens"], 0)


if __name__ == "__main__":
    unittest.main()

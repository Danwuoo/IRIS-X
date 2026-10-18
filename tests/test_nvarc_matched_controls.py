"""Synthetic tiny CPU numerical tests, NOT real-weight/GPU validation."""
from __future__ import annotations

import copy
import importlib.util
import math
import time
import unittest
from unittest.mock import patch

_OPTIONAL = ("torch", "transformers", "peft", "pydantic", "tokenizers", "safetensors")
_MISSING = [name for name in _OPTIONAL if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tools.nvarc_posttrain_20261017 import matched_controls as mc
    from tools.arc2_goal_sprint_20261017.af3 import AF3Trajectory, compute_group_loss
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, make_optimizer, restore_state, state_digest
    from tools.nvarc_posttrain_20261017.codec import encode_example, grid_tokens
    from tools.nvarc_posttrain_20261017.engine import FatalUpdateError
    from src.irisx.arc_nvarc_data import known_variant_group


def fixture():
    training = {"train-a": {"train": [{"input": [[1]], "output": [[2]]},
                                      {"input": [[3, 4]], "output": [[5]]}]}}
    admission = {"format": mc.ADMISSION_FORMAT, "source_sha256": "a" * 64,
                 "split_sha256": "b" * 64, "family_lineage_sha256": "c" * 64,
                 "parents": [{"parent_id": key, "task_sha256": mc._sha(task),
                              "variant_group": known_variant_group({**task, "test": []}),
                              "family_id": "family-a", "held_index": 0} for key, task in training.items()],
                 "excluded": {"parent_ids": ["excluded-a"], "variant_groups": ["e" * 64],
                              "family_ids": ["excluded-family"]}}
    return training, admission


def config(**changes):
    return {**mc.DEFAULT_CONFIG, "context_tokens": 96, "generation_tokens": 2,
            "max_groups": 1, "target_mixed_groups": 1, "microbatch": 8,
            "learning_rate": 1e-3, **changes}


def scripted_groups(patterns):
    """Test-only token draws through actual full-vocab forwards/logp capture.

    Production always uses real torch.multinomial. Scripted draws are synthetic
    failure/mixed-signal fixtures, not reported stochastic model performance.
    """
    calls = iter(token for pattern in patterns for token in ([2 if positive else 3 for positive in pattern], [15] * 8))
    def draw(probabilities, count, **kwargs):
        tokens = next(calls)
        if tuple(probabilities.shape) != (8, 16) or not bool((probabilities > 0).all()):
            raise AssertionError("fixture must see real complete-vocabulary probabilities")
        return torch.tensor(tokens, dtype=torch.long, device=probabilities.device)[:, None]
    return draw


@unittest.skipIf(bool(_MISSING), "Optional compact model dependencies missing: " + ", ".join(_MISSING))
class MatchedControlsCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        self.engine = tiny_engine()
        self.training, self.admission = fixture()
        self.pin = mc._sha(self.admission)

    def run_screen(self, cfg=None, engine=None):
        return mc.run_matched_controls(engine or self.engine, self.training, self.admission,
                    expected_admission_sha256=self.pin, deadline=time.time() + 90, config=cfg or config())

    def mixed_result(self):
        with patch("torch.multinomial", side_effect=scripted_groups([[1, 0] * 4])):
            return self.run_screen()

    def test_actual_stochastic_collection_full_vocab_and_restoration(self):
        before = mc.full_policy_sha256(self.engine)
        rng = self.engine.generator.get_state().clone()
        result = self.run_screen()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["capture"]["status"], "budget_exhausted")
        self.assertEqual(result["collection"]["trajectories_retained"], 8)
        self.assertEqual(result["verification"]["rows"], 8)
        self.assertLess(result["verification"]["max_logp_gap"], 1e-5)
        self.assertEqual(before, mc.full_policy_sha256(self.engine))
        self.assertTrue(torch.equal(rng, self.engine.generator.get_state()))
        self.assertTrue(result["anchor_restored"])
        self.assertFalse(result["engine_poisoned"])
        self.assertFalse(result["efficacy_claim"])
        self.assertFalse(result["equal_compute_claim"])
        self.assertTrue(all(p.grad is None for p in self.engine.parameters))
        self.assertEqual(result["collection"]["physical"]["optimizer_steps"], 0)
        self.assertEqual(result["collection"]["physical"]["optimizer_attempts"], 0)
        for arm in mc.ARMS:
            self.assertEqual(result["arms"][arm]["before_policy_sha256"], before)
            self.assertEqual(result["arms"][arm]["optimizer_initial_state_entries"], 0)
            self.assertEqual(result["arms"][arm]["pool_sha256"], result["capture"]["seal_sha256"])
        for key in mc.COUNTERS:
            self.assertEqual(result["physical"][key], result["collection"]["physical"][key]
                             + result["verification"]["physical"][key]
                             + sum(a["physical"][key] for a in result["arms"].values()))
        self.assertEqual(result["physical"]["model_forward_attempts"], result["physical"]["forward_calls"])

    def test_mixed_real_sft_af3_gradients_and_fresh_optimizer_identity(self):
        made, original = [], mc.make_optimizer
        def factory(model, lr):
            optimizer = original(model, lr)
            made.append(optimizer)
            return optimizer
        with patch.object(mc, "make_optimizer", side_effect=factory):
            result = self.mixed_result()
        self.assertEqual(len({id(o) for o in made}), 4)
        self.assertEqual(result["capture"]["status"], "target_reached")
        anchor_sha = state_digest(result["states"]["anchor"])
        for arm in mc.ARMS[1:]:
            report = result["arms"][arm]
            self.assertTrue(report["updated"])
            self.assertGreater(report["gradient_norm"], 0)
            self.assertNotEqual(state_digest(result["states"][arm]), anchor_sha)
            self.assertEqual(report["physical"]["optimizer_steps"], 1)
            self.assertEqual(report["physical"]["optimizer_attempts"], 1)
        self.assertEqual(result["arms"]["exact_centered_ddis"]["replayed"], 8)
        self.assertEqual(result["arms"]["known_target_ce"]["physical"]["forward_calls"], 1)
        self.assertEqual(result["arms"]["exact_positive_ce"]["physical"]["forward_calls"], 1)
        self.assertEqual(state_digest(result["states"]["known_target_ce"]), state_digest(result["states"]["exact_positive_ce"]))
        # An independent REAL engine.sft_step is exactly the single-group CE.
        group = result["capture"]["groups"][0]
        independent = tiny_engine()
        item = {"prompt_ids": group["prompt_ids"], "completion_ids": [2, 15], "demos_dropped": 0}
        report = independent.sft_step(item, make_optimizer(independent.model, 1e-3))
        self.assertTrue(report["updated"])
        self.assertEqual(state_digest(adapter_state(independent.model)), state_digest(result["states"]["known_target_ce"]))

    def test_failed_first_replay_records_actual_gap_before_denial(self):
        real = self.engine.completion_logps
        before = mc.full_policy_sha256(self.engine)
        def mismatch(ids, prompt_length):
            values = real(ids, prompt_length).clone()
            values[prompt_length] += 0.25
            return values
        with patch.object(self.engine, "completion_logps", side_effect=mismatch):
            with self.assertRaisesRegex(ValueError, "captured behavior logps") as caught:
                self.run_screen()
        result = caught.exception.matched_controls_result
        verify = result["verification"]
        self.assertEqual(verify["rows"], 0)
        self.assertEqual(verify["observed_rows"], 1)
        self.assertAlmostEqual(verify["max_logp_gap"], 0.25, places=5)
        detail = verify["failed_row"]
        row = result["capture"]["groups"][0]["rows"][0]
        self.assertEqual(detail["sample_id"], row["sample_id"])
        self.assertEqual(detail["max_gap_token_index"], row["prompt_length"])
        self.assertEqual(len(detail["replay_log_probs"]), len(row["input_ids"]))
        self.assertFalse(detail["numerical_cause_established"])
        self.assertEqual(result["physical"]["optimizer_attempts"], 0)
        self.assertTrue(all(arm["status"] == "not_run" for arm in result["arms"].values()))
        self.assertEqual(before, mc.full_policy_sha256(self.engine))

    def test_failed_replay_forward_has_unknown_not_zero_gap(self):
        with patch.object(self.engine, "completion_logps", side_effect=RuntimeError("replay forward failed")):
            with self.assertRaisesRegex(RuntimeError, "replay forward failed") as caught:
                self.run_screen()
        verify = caught.exception.matched_controls_result["verification"]
        self.assertEqual(verify["rows"], 0)
        self.assertEqual(verify["observed_rows"], 0)
        self.assertIsNone(verify["max_logp_gap"])
        self.assertIsNone(verify["failed_row"])

    def test_prompt_weighting_saturation_and_conservation(self):
        patterns = [[0] * 8, [1] * 8, [1, 0] * 4]
        with patch("torch.multinomial", side_effect=scripted_groups(patterns)):
            result = self.run_screen(config(max_groups=3))
        self.assertEqual(result["collection"]["categories"], {"all_wrong": 1, "all_correct": 1, "mixed": 1})
        weights = result["arms"]["known_target_ce"]["prompt_weights"]
        self.assertEqual([w["weight"] for w in weights], [1 / 3] * 3)
        weights = result["arms"]["exact_positive_ce"]["prompt_weights"]
        self.assertEqual([w["group_id"] for w in weights], ["g1", "g2"])
        self.assertEqual([w["weight"] for w in weights], [2 / 3, 1 / 3])
        self.assertEqual(result["arms"]["exact_centered_ddis"]["prompt_weights"],
                         [{"group_id": "g2", "parent_id": "train-a", "weight": 1.0}])
        self.assertEqual(result["collection"]["trajectories_requested"], 24)
        self.assertEqual(result["collection"]["parent_stats"]["train-a"]["positive"], 12)
        self.assertEqual(result["collection"]["family_stats"]["family-a"]["complete"], 3)
        self.assertEqual(result["collection"]["physical"]["sampled_tokens"], 48)

    def test_zero_and_one_reward_pools_have_no_manufactured_rl(self):
        for reward in (0, 1):
            engine = tiny_engine()
            with patch("torch.multinomial", side_effect=scripted_groups([[reward] * 8])):
                result = self.run_screen(engine=engine)
            self.assertEqual(result["capture"]["status"], "budget_exhausted")
            self.assertFalse(result["arms"]["exact_centered_ddis"]["updated"])
            self.assertEqual(result["arms"]["exact_centered_ddis"]["physical"]["forward_calls"], 0)
            self.assertEqual(result["arms"]["exact_positive_ce"]["updated"], bool(reward))
            # Exercise actual AF3 zero-signal handling, not a fake optimizer.
            rows = result["capture"]["groups"][0]["rows"]
            counters = (engine.forward_calls, engine.optimizer_steps)
            report = engine.af3_update(rows, make_optimizer(engine.model, 1e-3), expected_groups=["g0"], group_size=8)
            self.assertFalse(report["updated"])
            self.assertEqual(report["reason"], "zero_reward_signal")
            self.assertEqual(counters, (engine.forward_calls, engine.optimizer_steps))

    def test_admission_hash_task_variant_family_and_strict_bounds(self):
        mc.admit_panel(self.training, self.admission, expected_admission_sha256=self.pin)
        for mutate in (
            lambda t, a: t["train-a"].update(test=[]),
            lambda t, a: a["excluded"]["parent_ids"].append("train-a"),
            lambda t, a: a["excluded"]["variant_groups"].append(a["parents"][0]["variant_group"]),
            lambda t, a: a["excluded"]["family_ids"].append("family-a"),
            lambda t, a: a["parents"][0].update(variant_group="f" * 64),
            lambda t, a: a.update(public_data=False),
            lambda t, a: a["parents"][0].update(held_index=True),
        ):
            training, admission = copy.deepcopy((self.training, self.admission))
            mutate(training, admission)
            with self.assertRaises(ValueError):
                mc.admit_panel(training, admission, expected_admission_sha256=mc._sha(admission))
        with self.assertRaisesRegex(ValueError, "pinned"):
            mc.admit_panel(self.training, self.admission, expected_admission_sha256="f" * 64)
        for cfg in (config(max_groups=65), config(target_mixed_groups=9), config(microbatch=True), config(seed=-1), config(public_data=False)):
            with self.assertRaises(ValueError):
                self.run_screen(cfg)

    def test_capture_rejects_resealed_forged_rows_and_partial_groups(self):
        result = self.mixed_result()
        mutations = [lambda c: c["groups"][0]["rows"][0].update(reward=0),
                     lambda c: c["groups"][0]["rows"][0]["input_ids"].__setitem__(0, 9),
                     lambda c: c["groups"][0]["rows"][0].update(policy_sha256="f" * 64),
                     lambda c: c["groups"][0]["rows"][0].update(behavior_log_probs=[float("nan")]),
                     lambda c: c["groups"][0]["rows"][0].update(sample_id="g0:s1"),
                     lambda c: c["groups"][0]["rows"].pop(),
                     lambda c: c["groups"][0].update(training_target=[[7]]),
                     lambda c: c["groups"][0]["rows"][0].update(public_data=False)]
        for mutate in mutations:
            capture = copy.deepcopy(result["capture"])
            mutate(capture)
            if not any(math.isnan(v) for r in capture["groups"][0]["rows"] for v in r["behavior_log_probs"]):
                capture["seal_sha256"] = mc._sha({k: v for k, v in capture.items() if k != "seal_sha256"})
            with self.assertRaises(ValueError):
                mc.validate_capture(capture, self.training, self.admission, expected_admission_sha256=self.pin, engine=self.engine)

    def test_expired_entry_and_partial_deadline_retained_without_updates(self):
        before = mc.full_policy_sha256(self.engine)
        expired = mc.run_matched_controls(self.engine, self.training, self.admission,
            expected_admission_sha256=self.pin, deadline=time.time() - 1, config=config())
        self.assertEqual(expired["status"], "deadline")
        self.assertEqual(expired["collection"]["groups_attempted"], 1)
        self.assertEqual(expired["collection"]["trajectories_requested"], 0)
        self.assertEqual(expired["physical"]["forward_calls"], 0)
        self.assertTrue(all(a["status"] == "not_run" for a in expired["arms"].values()))
        original, calls = self.engine.generate, 0
        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PhaseDeadline("synthetic second microbatch deadline")
            return original(*args, **kwargs)
        with patch.object(self.engine, "generate", side_effect=interrupted):
            result = self.run_screen(config(microbatch=2))
        self.assertEqual(result["status"], "deadline")
        self.assertEqual(result["collection"]["categories"], {"partial": 1})
        self.assertEqual(result["collection"]["trajectories_requested"], 4)
        self.assertEqual(result["collection"]["trajectories_retained"], 2)
        self.assertEqual(result["physical"]["optimizer_steps"], 0)
        mc.validate_capture(result["capture"], self.training, self.admission, expected_admission_sha256=self.pin, engine=self.engine)
        self.assertEqual(before, mc.full_policy_sha256(self.engine))

    def test_invalid_generator_partial_return_charged_and_error_not_hidden(self):
        original = self.engine.generate
        def partial(*args, **kwargs):
            return original(*args, **kwargs)[:3]
        with patch.object(self.engine, "generate", side_effect=partial):
            with self.assertRaisesRegex(ValueError, "partial generator") as caught:
                self.run_screen()
        result = caught.exception.matched_controls_result
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["collection"]["trajectories_requested"], 8)
        self.assertEqual(result["collection"]["trajectories_retained"], 3)
        self.assertGreaterEqual(result["collection"]["physical"]["sampled_tokens"], 8)
        self.assertTrue(result["anchor_restored"])
        mc.validate_capture(result["capture"], self.training, self.admission, expected_admission_sha256=self.pin, engine=self.engine)

    def test_optimizer_failure_restores_anchor_and_preserves_poison(self):
        original, count = mc.make_optimizer, 0
        before = mc.full_policy_sha256(self.engine)
        def factory(model, lr):
            nonlocal count
            count += 1
            opt = original(model, lr)
            if count == 2:
                def bad_step(*args, **kwargs):
                    with torch.no_grad():
                        next(p for p in model.parameters() if p.requires_grad).add_(3)
                    raise RuntimeError("synthetic partial optimizer mutation")
                opt.step = bad_step
            return opt
        with patch.object(mc, "make_optimizer", side_effect=factory):
            with self.assertRaises(FatalUpdateError) as caught:
                self.mixed_result()
        result = caught.exception.matched_controls_result
        self.assertTrue(result["engine_poisoned"])
        self.assertTrue(result["anchor_restored"])
        self.assertEqual(result["physical"]["optimizer_attempts"], 1)
        self.assertEqual(result["physical"]["optimizer_steps"], 0)
        self.assertEqual(result["arms"]["exact_positive_ce"]["status"], "not_run")
        self.assertEqual(before, mc.full_policy_sha256(self.engine))
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        with self.assertRaises(FatalUpdateError):
            self.engine.generate([14, 11, 10, 1], max_new_tokens=2)

    def test_full_hash_detects_frozen_parameter_and_config_mutation(self):
        before = mc.full_policy_sha256(self.engine)
        frozen = next(p for p in self.engine.model.parameters() if not p.requires_grad)
        old = frozen.detach().clone()
        with torch.no_grad():
            frozen.add_(0.1)
        self.assertNotEqual(before, mc.full_policy_sha256(self.engine))
        with torch.no_grad():
            frozen.copy_(old)
        self.assertEqual(before, mc.full_policy_sha256(self.engine))
        self.engine.model.config.rms_norm_eps *= 2
        self.assertNotEqual(before, mc.full_policy_sha256(self.engine))

    def test_default_eight_mixed_target_and_hard_64_group_cap(self):
        with patch("torch.multinomial", side_effect=scripted_groups([[1, 0] * 4] * 8)):
            mixed = self.run_screen(config(max_groups=64, target_mixed_groups=8))
        self.assertEqual(mixed["collection"]["groups_attempted"], 8)
        self.assertTrue(mixed["collection"]["mixed_target_met"])
        self.assertEqual(mixed["collection"]["trajectories_requested"], 64)
        with patch("torch.multinomial", side_effect=scripted_groups([[0] * 8] * 64)):
            capped = self.run_screen(config(max_groups=64, target_mixed_groups=8))
        self.assertEqual(capped["collection"]["groups_attempted"], 64)
        self.assertFalse(capped["collection"]["mixed_target_met"])
        self.assertEqual(capped["collection"]["trajectories_requested"], 512)
        self.assertEqual(capped["capture"]["status"], "budget_exhausted")
        self.assertEqual(capped["collection"]["categories"], {"all_wrong": 64})

    def test_resealed_impossible_terminal_evidence_is_rejected(self):
        with patch("torch.multinomial", side_effect=scripted_groups([[0] * 8])):
            result = self.run_screen()
        for mutate in (lambda c: c.update(status="target_reached"),
                       lambda c: c["groups"][0]["batches"][0].update(status="failed"),
                       lambda c: c.update(status="deadline"),
                       lambda c: c["lineage"].update(policy_sha256="f" * 64)):
            capture = copy.deepcopy(result["capture"])
            mutate(capture)
            capture["seal_sha256"] = mc._sha({k: v for k, v in capture.items() if k != "seal_sha256"})
            with self.assertRaises(ValueError):
                mc.validate_capture(capture, self.training, self.admission, expected_admission_sha256=self.pin, engine=self.engine)

    def test_live_adapter_mutation_cannot_claim_successful_restoration(self):
        original = self.engine.generate
        module = next(m for m in self.engine.model.modules() if hasattr(m, "lora_A"))
        def mutate_after_generation(*args, **kwargs):
            output = original(*args, **kwargs)
            module.scaling["default"] *= 2
            return output
        with patch.object(self.engine, "generate", side_effect=mutate_after_generation):
            with self.assertRaises(FatalUpdateError) as caught:
                self.run_screen()
        result = caught.exception.matched_controls_result
        self.assertFalse(result["anchor_restored"])
        self.assertTrue(result["engine_poisoned"])
        self.assertEqual(result["error"], "ValueError")
        self.assertEqual(result["restoration_error"], "FatalUpdateError")
        self.assertEqual(result["physical"]["optimizer_steps"], 0)
        self.assertEqual(len(self.engine.model._forward_pre_hooks), 0)

    def test_sync_failure_does_not_erase_primary_or_charged_work(self):
        original = self.engine.generate
        def failed_after_forward(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("primary generation failure")
        with patch.object(self.engine, "generate", side_effect=failed_after_forward), patch.object(
                self.engine, "sync", side_effect=RuntimeError("cleanup sync failure")):
            with self.assertRaisesRegex(ValueError, "primary generation") as caught:
                self.run_screen()
        result = caught.exception.matched_controls_result
        self.assertEqual(result["error"], "ValueError")
        self.assertEqual(result["cleanup_errors"][0]["error"], "RuntimeError")
        self.assertEqual(result["cleanup_errors"][0]["primary_error"], "ValueError")
        self.assertGreater(result["collection"]["physical"]["forward_calls"], 0)
        self.assertEqual(result["collection"]["trajectories_requested"], 8)
        self.assertEqual(len(self.engine.model._forward_pre_hooks), 0)
        with patch.object(self.engine, "sync", side_effect=RuntimeError("primary sync failure")):
            with self.assertRaisesRegex(RuntimeError, "primary sync") as caught:
                self.run_screen()
        self.assertGreater(caught.exception.matched_controls_result["collection"]["physical"]["sampled_tokens"], 0)
        self.assertTrue(caught.exception.matched_controls_result["anchor_restored"])

    def test_sync_failure_inside_unrelated_caller_except_is_not_suppressed(self):
        try:
            raise ValueError("unrelated handled caller exception")
        except ValueError:
            with patch.object(self.engine, "sync", side_effect=RuntimeError("local sync failure")):
                with self.assertRaisesRegex(RuntimeError, "local sync") as caught:
                    self.run_screen()
        result = caught.exception.matched_controls_result
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["cleanup_errors"][0]["primary_error"])
        self.assertGreater(result["collection"]["physical"]["sampled_tokens"], 0)
        self.assertEqual(len(self.engine.model._forward_pre_hooks), 0)
        calls = 0
        def fail_arm_sync():
            nonlocal calls
            calls += 1
            if calls == 3:  # Collection, verification, then anchor-arm closure.
                raise RuntimeError("arm closure sync failure")
        with patch.object(self.engine, "sync", side_effect=fail_arm_sync):
            with self.assertRaisesRegex(RuntimeError, "arm closure") as caught:
                self.mixed_result()
        result = caught.exception.matched_controls_result
        self.assertEqual(result["arms"]["anchor"]["status"], "failed")
        self.assertEqual(result["arms"]["known_target_ce"]["status"], "not_run")
        self.assertTrue(result["anchor_restored"])

    def test_arm_order_cannot_change_anchor_or_control_states(self):
        first = self.mixed_result()
        other = tiny_engine()
        with patch.object(mc, "ARMS", tuple(reversed(mc.ARMS))), patch(
                "torch.multinomial", side_effect=scripted_groups([[1, 0] * 4])):
            second = self.run_screen(engine=other)
        self.assertEqual(first["capture"]["seal_sha256"], second["capture"]["seal_sha256"])
        for arm in mc.ARMS:
            self.assertEqual(state_digest(first["states"][arm]), state_digest(second["states"][arm]))
        self.assertEqual(mc.full_policy_sha256(self.engine), mc.full_policy_sha256(other))

    def test_distinct_parent_ids_do_not_bypass_variant_exclusion(self):
        training, admission = copy.deepcopy((self.training, self.admission))
        # Different raw task bytes/ID, but a known color-renaming variant.
        task = copy.deepcopy(training["train-a"])
        for pair in task["train"]:
            for key, grid in pair.items():
                pair[key] = [[(v + 1) % 10 for v in row] for row in grid]
        training["train-b"] = task
        admission["parents"].append({"parent_id": "train-b", "task_sha256": mc._sha(task),
            "variant_group": known_variant_group({**task, "test": []}), "family_id": "family-b", "held_index": 0})
        self.assertNotEqual(admission["parents"][0]["task_sha256"], admission["parents"][1]["task_sha256"])
        with self.assertRaisesRegex(ValueError, "distinct training variant"):
            mc.admit_panel(training, admission, expected_admission_sha256=mc._sha(admission))

    def test_forward_failure_charged_and_backward_failure_cleared(self):
        original = self.engine.model.forward
        def failed_forward(*args, **kwargs):
            raise RuntimeError("synthetic forward failure")
        with patch.object(self.engine.model, "forward", side_effect=failed_forward):
            with self.assertRaisesRegex(RuntimeError, "forward failure") as caught:
                self.run_screen()
        physical = caught.exception.matched_controls_result["physical"]
        self.assertEqual(physical["model_forward_attempts"], 1)
        self.assertEqual(physical["forward_calls"], 0)
        self.assertEqual(physical["generation_forward_attempts"], 1)
        self.assertEqual(physical["optimizer_attempts"], 0)
        real_logps = self.engine.completion_logps
        def fail_backward(*args, **kwargs):
            result = real_logps(*args, **kwargs)
            if result.requires_grad:
                def bad_gradient(grad):
                    raise RuntimeError("synthetic backward failure")
                result.register_hook(bad_gradient)
            return result
        with patch.object(self.engine, "completion_logps", side_effect=fail_backward):
            with self.assertRaisesRegex(RuntimeError, "backward failure") as caught:
                self.mixed_result()
        result = caught.exception.matched_controls_result
        self.assertEqual(result["arms"]["known_target_ce"]["physical"]["forward_calls"], 1)
        self.assertTrue(result["arms"]["known_target_ce"]["backward_cost"]["partial_work_unknown"])
        self.assertEqual(result["physical"]["optimizer_steps"], 0)
        self.assertTrue(result["anchor_restored"])
        self.assertTrue(all(p.grad is None for p in self.engine.parameters))

    def test_two_parent_positive_reduction_matches_expanded_real_sft(self):
        groups = []
        for i, (target, positives) in enumerate((([[2]], 2), ([[5, 6]], 6))):
            prompt = encode_example([], [[i + 1]], context=96, generation=3)["prompt_ids"]
            completion = grid_tokens(target) + [15]
            groups.append({"group_id": f"g{i}", "parent_id": f"parent-{i}", "status": "complete",
                           "prompt_ids": prompt, "training_target": target,
                           "rows": [{"reward": int(j < positives), "completion_ids": completion if j < positives else [9, 15]}
                                    for j in range(8)]})
        weighted = mc._weights(groups, "exact_positive_ce")
        self.assertEqual([w for _, w in weighted], [.25, .75])
        collapsed, expanded = tiny_engine(), tiny_engine()
        report = mc._ce_update(collapsed, weighted, make_optimizer(collapsed.model, 1e-3), time.time() + 90, positive=True)
        opt = make_optimizer(expanded.model, 1e-3)
        total = 0.0
        for group in groups:
            for row in group["rows"]:
                if row["reward"]:
                    prompt = group["prompt_ids"]
                    values = expanded.completion_logps(prompt + row["completion_ids"], len(prompt))
                    loss = -values[len(prompt):].mean() / 8
                    total += loss.item()
                    loss.backward()
        expanded.commit(opt)
        self.assertAlmostEqual(report["loss"], total, places=6)
        for name, value in adapter_state(collapsed.model).items():
            torch.testing.assert_close(value, adapter_state(expanded.model)[name], atol=1e-6, rtol=1e-5)

    def test_streamed_real_af3_matches_direct_upstream_on_unequal_lengths(self):
        streamed, direct = tiny_engine(), tiny_engine()
        prompt = encode_example([], [[1]], context=96, generation=4)["prompt_ids"]
        rows, trajectories = [], []
        for group_index in range(2):
            for slot in range(8):
                completion = [2, 15] if slot % 2 == 0 else [3, 4, 15]
                ids = prompt + completion
                with torch.no_grad():
                    old = streamed.completion_logps(ids, len(prompt)).detach()
                row = {"sample_id": f"g{group_index}:s{slot}", "group_id": f"g{group_index}",
                       "input_ids": ids, "prompt_length": len(prompt), "completion_tokens": len(completion),
                       "behavior_log_probs": old.tolist(),
                       "reward": float(slot % 2 == 0 if group_index == 0 else slot < 3)}
                rows.append(row)
                current = direct.completion_logps(ids, len(prompt))
                trajectories.append(AF3Trajectory(row["sample_id"], row["group_id"], ids, current, old,
                    torch.tensor([0] * len(prompt) + [1] * len(completion)), row["reward"]))
        reference = compute_group_loss(trajectories)
        reference.loss.backward()
        direct_report = direct.commit(make_optimizer(direct.model, 1e-3))
        report = streamed.af3_update(rows, make_optimizer(streamed.model, 1e-3),
                                    expected_groups=["g0", "g1"], group_size=8)
        self.assertTrue(report["updated"] and direct_report["updated"])
        self.assertEqual(report["replayed"], 16)
        self.assertAlmostEqual(report["loss"], reference.loss.item(), places=6)
        self.assertAlmostEqual(report["gradient_norm"], direct_report["gradient_norm"], places=6)
        direct_state = adapter_state(direct.model)
        for name, value in adapter_state(streamed.model).items():
            torch.testing.assert_close(value, direct_state[name], atol=1e-6, rtol=1e-5)

    def test_target_only_mask_and_actual_af3_centered_gradient_conservation(self):
        group = self.mixed_result()["capture"]["groups"][0]
        # Real compact SFT: prompt positions have no direct supervised logp gradient.
        values = self.engine.completion_logps(group["prompt_ids"] + [2, 15], len(group["prompt_ids"]))
        values.retain_grad()
        (-values[len(group["prompt_ids"]):].mean()).backward()
        self.assertTrue(torch.equal(values.grad[:len(group["prompt_ids"])], torch.zeros(len(group["prompt_ids"]))))
        self.assertTrue(torch.equal(values.grad[-2:], torch.full((2,), -0.5)))
        for p in self.engine.parameters:
            p.grad = None
        items, logits = [], []
        # Unequal completion lengths, exact binary rewards, complete 8-row groups.
        for gi, rewards in enumerate(([0] * 8, [1] * 8, [1, 0] * 4)):
            for si, reward in enumerate(rewards):
                length = 2 + si % 2
                current = torch.full((3 + length,), -2.0, requires_grad=True)
                logits.append(current)
                items.append(AF3Trajectory(f"g{gi}:s{si}", f"g{gi}", [1] * (3 + length), current,
                    current.detach().clone(), torch.tensor([0] * 3 + [1] * length), reward))
        plan = compute_group_loss(items)
        self.assertEqual(plan.mixed_groups, 1)
        plan.loss.backward()
        for index, (sample, values) in enumerate(zip(plan.samples, logits)):
            length = 2 + index % 2
            self.assertEqual(sample.divisor, 8 * length)
            self.assertEqual(sample.advantages[:3], [0.0] * 3)
            self.assertTrue(torch.equal(values.grad[:3], torch.zeros(3)))
            if index < 16:
                self.assertTrue(torch.equal(values.grad, torch.zeros_like(values)))
            else:
                expected = -0.5 / (8 * length) if index % 2 == 0 else 0.5 / (8 * length)
                torch.testing.assert_close(values.grad[3:], torch.full((length,), expected))
        self.assertAlmostEqual(sum(sum(sample.advantages[3:]) / sample.seq_token_count for sample in plan.samples), 0)


if __name__ == "__main__":
    unittest.main()

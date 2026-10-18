"""Local-only diagnostic contract tests, not model effectiveness evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.arc2_goal_sprint_20261017 import diagnostic as d
from tools.arc2_goal_sprint_20261017.data import SECOND_VIEW, answer_text, transform


def panel(dev=2, train=1, remaining=2):
    parents = []
    for partition, count, prefix in (("dev", dev, "dev-panel:"), ("train", train, "train-diagnostic:")):
        names = sorted([partition + str(i) for i in range(count)], key=lambda name: hashlib.sha256((prefix + name).encode()).hexdigest())
        for name in names:
            parents.append({"parent_id": name, "partition": partition, "sft_exposure": partition == "train",
                "solver": {"demos": [{"pair_index": i + 1, "input": [[i]], "output": [[i + 1]]}
                                      for i in range(remaining)], "query": [[8]]},
                "held_out": {"pair_index": 0, "target": [[9]]}})
    return {"format": d.PANEL_FORMAT,
        "provenance": {"training_manifest_sha256": "1" * 64, "train_ids_digest": "sha256:" + "2" * 64,
            "dev_ids_digest": "sha256:" + "3" * 64, "source_run_id": "synthetic-source",
            "source_seal_sha256": "4" * 64, "public_benchmark_data_included": False,
            "original_test_fields_used": False},
        "selection": {"dev_count": dev, "train_count": train, "heldout_pair_index": 0,
            "dev_order": "sha256:dev-panel:", "train_order": "sha256:train-diagnostic:", "seed": 20261017},
        "parents": parents}


def profile():
    return d.default_profile(session_epoch=1, session_deadline=10000)


CHECKPOINTS = {"A": {"root": "A", "manifest_sha256": "a" * 64},
               "C": {"root": "C", "manifest_sha256": "c" * 64}}


class CharacterTokenizer:
    eos_token_id = 0
    is_fast = True

    def encode(self, text, **kwargs):
        return [ord(c) for c in text]

    def decode(self, ids, **kwargs):
        return "".join(chr(i) for i in ids if i)

    def apply_chat_template(self, messages, **kwargs):
        return "USER\n" + messages[0]["content"] + "\nASSISTANT\n"

    def __call__(self, text, **kwargs):
        return {"input_ids": self.encode(text), "offset_mapping": [(i, i + 1) for i in range(len(text))]}


class FakeOptimizer:
    def __init__(self):
        self.zeroed = 0

    def zero_grad(self, **kwargs):
        self.zeroed += 1


class FakeEngine:
    def __init__(self):
        self.w = 0.0
        self.tokenizer = CharacterTokenizer()
        self.forward_calls = self.sampled_tokens = self.optimizer_steps = self.optimizer_attempts = 0
        self.steps, self.generations, self.start_weights = [], [], []
        self.step_hook, self.generate_hook = None, None

    def sync(self):
        pass

    def sft_step(self, example, optimizer, **kwargs):
        self.start_weights.append(self.w)
        self.steps.append(copy.deepcopy(example))
        self.optimizer_attempts += 1
        self.optimizer_steps += 1
        self.forward_calls += 1
        self.w += 1
        if self.step_hook:
            self.step_hook(self)
        return {"updated": True, "loss": 0.5, "demos_dropped": example["demos_dropped"]}

    def generate(self, prompt_ids, **kwargs):
        self.generations.append((list(prompt_ids), dict(kwargs), self.w))
        self.forward_calls += 1
        self.sampled_tokens += 3
        text = self.generate_hook(self) if self.generate_hook else "<grid>9</grid>"
        return [{"text": text, "completion_tokens": 3, "stop": "completed"}]


class FakeBackend:
    recoverable = (d.DiagnosticDeadline, FloatingPointError, ValueError)

    def __init__(self):
        self.optimizers, self.restores, self.loads = [], [], []
        self.corrupt_restore = False

    def state(self, engine):
        return {"w": engine.w}

    def state_digest(self, state):
        return d.sha(state)

    def restore(self, engine, state):
        self.restores.append(dict(state))
        engine.w = state["w"] + (1 if self.corrupt_restore else 0)

    def verify(self, engine, state):
        if self.state(engine) != state:
            raise d.FatalDiagnostic("synthetic wrong restore")

    def optimizer(self, engine, lr):
        optimizer = FakeOptimizer()
        self.optimizers.append(optimizer)
        return optimizer

    def load(self, engine, spec, base_identity):
        self.loads.append((copy.deepcopy(spec), copy.deepcopy(base_identity)))
        engine.w = 10.0 if spec["root"] == "A" else 20.0
        return {"state_sha256": self.state_digest(self.state(engine)), "manifest_sha256": spec["manifest_sha256"]}

    def cleanup(self):
        pass

    def token_nll(self, engine, example):
        engine.forward_calls += 1
        return [0.5] * len(example["completion_ids"])


class PanelTests(unittest.TestCase):
    def test_pinned_canonical_bytes_and_complete_denominators(self):
        p = panel()
        self.assertEqual(d.validate_panel(p), p)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "panel.json"
            body = d.canonical(p) + b"\n"
            path.write_bytes(body)
            self.assertEqual(d.load_panel(path, hashlib.sha256(body).hexdigest()), p)
            with self.assertRaisesRegex(ValueError, "SHA differs"):
                d.load_panel(path, "0" * 64)
            path.write_bytes(body + b" ")
            with self.assertRaisesRegex(ValueError, "canonical"):
                d.load_panel(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_leakage_ambiguous_partitions_and_unpinned_fields_rejected(self):
        mutations = [
            lambda p: p["parents"][0]["solver"]["demos"][0].update(pair_index=0),
            lambda p: p["parents"][0]["solver"].update(target=[[9]]),
            lambda p: p["parents"][0].update(sft_exposure=True),
            lambda p: p["parents"][0]["solver"].update(demos=[]),
            lambda p: p["parents"][0]["held_out"].update(pair_index=True),
            lambda p: p["provenance"].update(public_benchmark_data_included=True),
            lambda p: p["provenance"].update(original_test_fields_used=True),
            lambda p: p["parents"].append(copy.deepcopy(p["parents"][0])),
            lambda p: p["parents"].reverse(),
            lambda p: p.update(evaluator_path="not-allowed"),
        ]
        for mutation in mutations:
            p = panel()
            mutation(p)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                d.validate_panel(p)

    def test_duplicate_json_key_fails(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            d.strict_json('{"a":1,"a":2}')

    def test_malformed_profiles_and_causal_ineligible_panel_fail(self):
        for key, value in (("context_tokens", 4096), ("generation_tokens", 4096), ("seed", True),
                           ("session_deadline", float("inf")), ("session_epoch", 20000),
                           ("closure_reserve_seconds", 1), ("closure_reserve_seconds", 59),
                           ("arm_seconds", 0), ("ttt_lr", True), ("inference_views", "adaptive"),
                           ("arms", ["A0", "C0"]), ("base_identity", {})):
            config = profile()
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate_profile(config, panel())
        config = profile()
        config["arms"] += ["C32final", "C32causal_outputs"]
        d.validate_profile(config, panel())
        with self.assertRaisesRegex(ValueError, "two remaining demos"):
            d.validate_profile(config, panel(remaining=1))

    def test_heldout_is_never_passed_to_adaptation_loo(self):
        p, seen = panel(), []
        original = d.loo_example
        def spy(task, *args, **kwargs):
            seen.append(copy.deepcopy(task))
            return original(task, *args, **kwargs)
        with patch.object(d, "loo_example", side_effect=spy):
            d.adaptation_example(CharacterTokenizer(), d.solver_demos(p["parents"][0]),
                parent_id="dev0", seed=1, step=0, context=8192, generation=2048, loss_mode="final")
        self.assertEqual(seen, [{"train": [{"input": [[0]], "output": [[1]]}, {"input": [[1]], "output": [[2]]}]}])
        self.assertNotIn("query", seen[0])
        self.assertNotIn("held_out", seen[0])

    def test_augmentation_is_deterministic_paired_prefix(self):
        demos = d.solver_demos(panel()["parents"][0])
        def sequence():
            return [d.adaptation_example(CharacterTokenizer(), demos, parent_id="x", seed=17,
                step=i, context=8192, generation=2048, loss_mode="final") for i in range(32)]
        first = sequence()
        import random
        random.seed(999)
        self.assertEqual(first, sequence())
        self.assertNotEqual(first[0], first[1])
        short_engine, long_engine = FakeEngine(), FakeEngine()
        d.adapt_demos(short_engine, demos, parent_id="x", profile=profile(), arm="A8final", deadline=9999, backend=FakeBackend(), now=lambda: 100)
        d.adapt_demos(long_engine, demos, parent_id="x", profile=profile(), arm="C32final", deadline=9999, backend=FakeBackend(), now=lambda: 100)
        self.assertEqual(short_engine.steps, long_engine.steps[:8])

    def test_token_loss_categories_exact_or_explicitly_unavailable(self):
        tokenizer = CharacterTokenizer()
        target = [[1, 2]]
        ids = tokenizer.encode(answer_text(target)) + [0]
        categories = d.loss_categories(tokenizer, ids, target)
        self.assertEqual(categories.count("digit_content"), 2)
        self.assertGreater(categories.count("whitespace"), 0)
        self.assertGreater(categories.count("structure"), 0)
        self.assertIsNone(d.loss_categories(tokenizer, ids + [1], target))


class HarnessTests(unittest.TestCase):
    def run_fake(self, root, *, p=None, cfg=None, engine=None, backend=None, now=lambda: 100):
        engine, backend = engine or FakeEngine(), backend or FakeBackend()
        result = d.run_diagnostic(engine, p or panel(), cfg or profile(), CHECKPOINTS,
            verified_base_identity={"independently_verified": True}, output=Path(root) / "result", backend=backend, now=now)
        private = json.loads((Path(root) / "result/diagnostic.private.json").read_text())
        return result, private, engine, backend

    def test_factorial_resets_fresh_optimizers_full_paired_denominators(self):
        with tempfile.TemporaryDirectory() as root:
            summary, private, engine, backend = self.run_fake(root)
            self.assertEqual(summary["status"], "complete")
            self.assertTrue(summary["full_panel_complete"])
            self.assertEqual(len(private["rows"]), 10)
            self.assertEqual(len(engine.generations), 20)
            self.assertEqual(len(backend.optimizers), 4)
            self.assertEqual(len(backend.loads), 2)
            self.assertEqual(engine.w, 0.0)
            for row in private["rows"]:
                self.assertTrue(row["reset_verified"])
                self.assertEqual(row["ttt"]["actual_ttt_steps"], d.ARMS[row["arm"]][1])
                self.assertEqual(row["initial_state_sha256"], d.sha({"w": 10.0 if row["checkpoint"] == "A" else 20.0}))
            self.assertFalse(summary["selection_permitted"])
            self.assertIsNone(summary["winner_selected"])
            self.assertEqual(summary["partitions"]["dev"]["fully_paired_complete_parents"], 2)
            self.assertEqual(summary["partitions"]["train"]["arms"]["A0"]["expected"], 1)
            self.assertNotIn("dev0", json.dumps(summary))
            self.assertNotIn("prediction", json.dumps(summary))
            self.assertEqual((Path(root) / "result/diagnostic.private.json").stat().st_mode & 0o777, 0o600)

    def test_exact_second_view_inverse_and_target_free_ranking(self):
        engine = FakeEngine()
        engine.generate_hook = lambda e: answer_text([[0]]) if len(e.generations) % 2 else answer_text(transform([[9]], **SECOND_VIEW))
        with tempfile.TemporaryDirectory() as root:
            _, private, _, _ = self.run_fake(root, engine=engine)
            for row in private["rows"]:
                self.assertEqual(row["ranked_predictions"], [[[0]], [[9]]])
                self.assertFalse(row["metrics"]["pass_at_1"])
                self.assertTrue(row["metrics"]["pass_at_2"])
                self.assertEqual(row["ranking"], "fixed_view_order_valid_dedup_no_target_access")

    def test_identity_only_is_explicit_and_never_mixed(self):
        config = profile()
        config["inference_views"] = "identity_only"
        with tempfile.TemporaryDirectory() as root:
            result, private, engine, _ = self.run_fake(root, cfg=config)
            self.assertEqual(result["inference_views"], "identity_only")
            self.assertEqual(len(engine.generations), 10)
            self.assertTrue(all(len(row["views"]) == 1 for row in private["rows"]))

    def test_optional_causal_arm_uses_remaining_demos_only(self):
        p, config = panel(dev=1, train=0, remaining=3), profile()
        config["arms"] += ["C32final", "C32causal_outputs"]
        with tempfile.TemporaryDirectory() as root:
            result, private, engine, _ = self.run_fake(root, p=p, cfg=config)
            self.assertTrue(result["full_panel_complete"])
            causal = next(row for row in private["rows"] if row["arm"] == "C32causal_outputs")
            self.assertEqual(causal["ttt"]["actual_ttt_steps"], 32)
            masked = [e for e in engine.steps if "loss_mask" in e]
            self.assertEqual(len(masked), 32)
            self.assertTrue(all(sum(e["loss_mask"]) > len(e["completion_ids"]) for e in masked))

    def test_changing_heldout_target_does_not_change_training_or_generation(self):
        p1, p2 = panel(dev=1, train=0), panel(dev=1, train=0)
        p2["parents"][0]["held_out"]["target"] = [[7, 8]]
        with tempfile.TemporaryDirectory() as r1, tempfile.TemporaryDirectory() as r2:
            _, _, e1, _ = self.run_fake(r1, p=p1)
            _, _, e2, _ = self.run_fake(r2, p=p2)
            self.assertEqual(e1.steps, e2.steps)
            self.assertEqual(e1.generations, e2.generations)

    def test_partial_mutating_step_rolls_back_only_failed_step(self):
        engine, backend = FakeEngine(), FakeBackend()
        def fail_second(e):
            if len(e.steps) == 2:
                raise FloatingPointError("synthetic mutation")
        engine.step_hook = fail_second
        result = d.adapt_demos(engine, d.solver_demos(panel()["parents"][0]), parent_id="x",
            profile=profile(), arm="C8final", deadline=9999, backend=backend, now=lambda: 100)
        self.assertEqual(engine.w, 1.0)
        self.assertEqual(result["actual_ttt_steps"], 1)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["physical"]["optimizer_steps"], 2)
        self.assertEqual(result["physical"]["optimizer_attempts"], 2)
        self.assertFalse(result["complete"])
        self.assertFalse(result["steps"][-1]["retried"])

    def test_late_step_charged_not_retained(self):
        engine, backend, now = FakeEngine(), FakeBackend(), [100]
        engine.step_hook = lambda e: now.__setitem__(0, 200)
        result = d.adapt_demos(engine, d.solver_demos(panel()["parents"][0]), parent_id="x",
            profile=profile(), arm="C8final", deadline=200, backend=backend, now=lambda: now[0])
        self.assertEqual(engine.w, 0)
        self.assertEqual(result["actual_ttt_steps"], 0)
        self.assertEqual(result["physical"]["optimizer_steps"], 1)
        self.assertEqual(result["stop_reason"], "DiagnosticDeadline")

    def test_unknown_failure_stops_and_checkpoints_without_followon_generation(self):
        engine = FakeEngine()
        engine.step_hook = lambda e: (_ for _ in ()).throw(RuntimeError("unknown synthetic"))
        cfg = profile()
        # Fix order so the first arm encounters the injected failure.
        with tempfile.TemporaryDirectory() as root, patch.object(d, "arm_order", return_value=["A8final", "A0", "C0", "C8final"]):
            with self.assertRaises(d.FatalDiagnostic):
                self.run_fake(root, engine=engine, cfg=cfg)
            self.assertEqual(engine.generations, [])
            self.assertEqual(engine.w, 0.0)
            saved = json.loads((Path(root) / "result/diagnostic.private.json").read_text())
            self.assertEqual(saved["status"], "failed_closed")
            self.assertEqual(saved["summary"]["partitions"]["dev"]["fully_paired_complete_parents"], 0)
            self.assertEqual(saved["summary"]["physical"]["optimizer_steps"], 1)
            accounting = saved["summary"]["partitions"]["dev"]["arms"]["A8final"]
            self.assertIsNone(accounting["actual_ttt_steps"])
            self.assertEqual(accounting["ttt_reports_missing"], 1)

    def test_wrong_reset_is_fatal(self):
        backend, engine = FakeBackend(), FakeEngine()
        backend.corrupt_restore = True
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(d.FatalDiagnostic):
                self.run_fake(root, backend=backend, engine=engine)
            self.assertEqual(engine.generations, [])
            saved = json.loads((Path(root) / "result/aggregate.safe.json").read_text())
            self.assertEqual(saved["status"], "failed_closed")

    def test_expired_session_does_not_load_checkpoints(self):
        backend = FakeBackend()
        with tempfile.TemporaryDirectory() as root:
            result, private, engine, _ = self.run_fake(root, backend=backend, now=lambda: 10000)
            self.assertEqual(result["status"], "incomplete_deadline")
            self.assertEqual(backend.loads, [])
            self.assertEqual(private["rows"], [])
            self.assertEqual(result["partitions"]["dev"]["arms"]["A0"]["incomplete"], 2)

    def test_unequal_partial_panel_no_paired_selection(self):
        p, config = panel(), profile()
        metrics = {"exact": True, "pass_at_1": True, "pass_at_2": True, "valid": True,
                   "shape": True, "pixel": 1.0, "copies_query": False}
        rows = [{"parent_id": p["parents"][0]["parent_id"], "arm": "A0", "status": "complete", "metrics": metrics,
                 "nll_before": {"tokens": 2, "mean_nll": 10}, "nll_after": {"tokens": 2, "mean_nll": 9}},
                {"parent_id": p["parents"][1]["parent_id"], "arm": "C0", "status": "complete", "metrics": metrics,
                 "nll_before": {"tokens": 2, "mean_nll": 1}, "nll_after": {"tokens": 2, "mean_nll": .5}}]
        summary = d.summarize(p, config, rows, "incomplete", {key: 0 for key in d.COUNTERS})
        arm = summary["partitions"]["dev"]["arms"]["A0"]
        self.assertEqual(arm["descriptive_observed"]["denominator"], 1)
        self.assertEqual(arm["paired_complete_only"]["denominator"], 0)
        self.assertIsNone(arm["paired_complete_only"]["exact"])
        self.assertEqual(arm["descriptive_observed_nll"]["before"]["parent_mean"], 10)
        self.assertEqual(arm["paired_complete_only_nll"]["before"]["parents"], 0)
        self.assertIsNone(arm["paired_complete_only_nll"]["before"]["parent_mean"])
        self.assertEqual(summary["partitions"]["dev"]["arms"]["C0"]["descriptive_observed_nll"]["before"]["parent_mean"], 1)
        self.assertFalse(summary["selection_permitted"])

    def test_output_reuse_and_identical_manifest_refused(self):
        with tempfile.TemporaryDirectory() as root:
            self.run_fake(root)
            with self.assertRaisesRegex(ValueError, "fresh"):
                self.run_fake(root)
        specs = copy.deepcopy(CHECKPOINTS)
        specs["C"]["manifest_sha256"] = specs["A"]["manifest_sha256"]
        with tempfile.TemporaryDirectory() as root, self.assertRaisesRegex(ValueError, "distinct"):
            d.run_diagnostic(FakeEngine(), panel(), profile(), specs, verified_base_identity={"verified": True},
                             output=Path(root) / "result", backend=FakeBackend(), now=lambda: 100)


_MISSING = [name for name in ("torch", "transformers", "peft", "pydantic") if importlib.util.find_spec(name) is None]


@unittest.skipIf(bool(_MISSING), "Optional ML dependencies missing: " + ", ".join(_MISSING))
class TinyQwenTests(unittest.TestCase):
    def test_admitted_wrapper_loads_once_and_rejects_bad_identity_first(self):
        import time
        from tools.arc2_goal_sprint_20261017 import model, materials
        config = d.default_profile(session_epoch=time.time() - 10, session_deadline=time.time() + 1000)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "panel.json"
            body = d.canonical(panel()) + b"\n"
            path.write_bytes(body)
            args = dict(model_path="already-verified-local-base", verified_base_identity=materials.base_identity(),
                panel_path=path, panel_sha256=hashlib.sha256(body).hexdigest(), profile=config,
                checkpoints=CHECKPOINTS, output=Path(root) / "result", device="cpu")
            with patch.object(model.Engine, "load", return_value="loaded-once") as load, \
                 patch.object(d, "run_diagnostic", return_value={"status": "synthetic"}) as run:
                self.assertEqual(d.execute_from_bootstrap(**args), {"status": "synthetic"})
                load.assert_called_once_with("already-verified-local-base", device="cpu")
                self.assertEqual(run.call_args.args[0], "loaded-once")
            args["verified_base_identity"] = {"manifest_claim": "not-independent"}
            with patch.object(model.Engine, "load") as load, self.assertRaisesRegex(ValueError, "identity differs"):
                d.execute_from_bootstrap(**args)
            load.assert_not_called()

    def test_real_tiny_qwen_nll_ttt_reset_and_raw_generation(self):
        import torch
        from tests.test_arc2_goal_model import tiny_engine
        torch.set_num_threads(1)
        engine, backend = tiny_engine(), d.TorchBackend()
        original = backend.state(engine)
        config, parent = profile(), panel(dev=1, train=0)["parents"][0]
        before = d.target_nll(engine, parent["solver"], parent["held_out"]["target"], config, backend, float("inf"), lambda: 100)
        result = d.adapt_demos(engine, d.solver_demos(parent), parent_id=parent["parent_id"],
            profile=config, arm="A8final", deadline=float("inf"), backend=backend, now=lambda: 100)
        self.assertEqual(result["actual_ttt_steps"], 8)
        self.assertEqual(result["physical"]["optimizer_attempts"], 8)
        self.assertNotEqual(backend.state_digest(original), backend.state_digest(backend.state(engine)))
        after = d.target_nll(engine, parent["solver"], parent["held_out"]["target"], config, backend, float("inf"), lambda: 100)
        self.assertGreater(before["mean_nll"], after["mean_nll"])
        self.assertEqual(after["categories_status"], "unavailable_token_offsets")
        generated = engine.generate([2, 3, 4], max_new_tokens=3, sample=False)[0]
        self.assertGreater(generated["completion_tokens"], 0)
        d.reset_verified(engine, original, backend)
        self.assertEqual(backend.state_digest(original), backend.state_digest(backend.state(engine)))
        self.assertTrue(all(p.grad is None for p in engine.parameters))


if __name__ == "__main__":
    unittest.main()

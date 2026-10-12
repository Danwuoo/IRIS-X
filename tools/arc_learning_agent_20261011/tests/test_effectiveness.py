"""Policy/receipt fixtures. These mocked outputs are never neural evidence."""
import copy
import random
import tempfile
import time
import unittest

from tools.arc_next_models import digest
from tools.arc_learning_agent_20261011.budget import digest as declared_order_digest
from tools.arc_learning_agent_20261011.data import create_split_manifest
from tools.arc_learning_agent_20261011.effectiveness import (
    build_panel, validate_panel, evaluate_panel, compare_checkpoints, greedy_scope,
    DEFAULT_GATE_POLICY)
from tools.arc_learning_agent_20261011.grid_codec import grid_messages, encode_grid
from tools.arc_learning_agent_20261011.tests.test_data import fixture_tasks


def sources():
    tasks = fixture_tasks()
    for task in tasks.values():
        task["train"].append(copy.deepcopy(task["train"][-1]))
    manifest = create_split_manifest(tasks, fixed_splits={"train": ["a", "b"], "dev": ["c", "d"]})
    return tasks, manifest


def generation(text, *, valid=True, finish_reason="eos"):
    n = len(text) + 1
    return {"text": text, "valid": valid, "finish_reason": finish_reason,
            "input_tokens": 12, "output_tokens": n, "forward_calls": n,
            "forward_input_tokens": 12 + n - 1, "dispatched": True, "model_forward_started": True,
            "sampling": {"do_sample": False, "temperature": 1.0, "top_p": 1.0}}


class FixtureModel:
    def __init__(self, panel, *, wrong=None, loss=1.0):
        self.config = {"do_sample": True, "temperature": .5, "top_p": .4, "unrelated": "keep"}
        self.targets = {digest(grid_messages(c["demos"], c["query_input"])): encode_grid(c["target"]) for c in panel["cases"]}
        self.log, self.wrong, self.loss, self.checkpoint = [], wrong, loss, "base"
        self.overrides = {}

    def generate(self, messages, **kwargs):
        self.log.append(("generate", copy.deepcopy(messages), dict(kwargs)))
        assert self.config["do_sample"] is False
        text = self.targets[digest(messages)]
        wrong = self.overrides.get(self.checkpoint, self.wrong)
        if wrong == "missing":
            return None
        if wrong == "exception":
            raise RuntimeError("fixture exception")
        if wrong == "shape":
            text = "0"
        if wrong == "empty":
            text = ""
        if wrong == "content":
            text = "".join(str((int(c) + 1) % 10) if c != "\n" else c for c in text)
        if wrong == "random":
            rng = random.Random(913)
            text = "".join(str(rng.randrange(10)) if c != "\n" else c for c in text)
        result = generation(text)
        if wrong == "receipt":
            del result["forward_calls"]
        if wrong == "deadline":
            result.update(valid=False, finish_reason="deadline")
        return result

    def score_completion(self, messages, completion, **kwargs):
        self.log.append(("score", copy.deepcopy(messages), completion))
        loss = self.loss[self.checkpoint] if type(self.loss) is dict else self.loss
        return {"valid": True, "dispatched": True, "model_forward_started": True,
                "input_tokens": 17, "output_tokens": 0, "forward_calls": 1, "forward_input_tokens": 17,
                "nll_sum": 5 * loss, "token_count": 5, "mean_nll": loss}


class FixtureTrainer:
    def __init__(self, model):
        self.model, self.restores = model, []
    def restore(self, name):
        self.model.checkpoint = name
        self.restores.append(name)
        return {"restored": True}


class EffectivenessTests(unittest.TestCase):
    def setUp(self):
        self.tasks, self.manifest = sources()
        self.panel = build_panel(self.tasks, self.manifest, dev_tasks=2, seed=7)

    def evaluate(self, model, **kwargs):
        return evaluate_panel(model, self.panel, time.monotonic() + 30,
            manifest=self.manifest, evidence_mode="mock_fixture", **kwargs)

    def test_frozen_order_source_and_heldout_last_demo(self):
        self.assertEqual(self.panel, build_panel(dict(reversed(list(self.tasks.items()))), self.manifest, dev_tasks=2, seed=7))
        order = sorted(["c", "d"], key=lambda key: (declared_order_digest(["declared-task-order", 7, key]), key))
        self.assertEqual(self.panel["predeclared_dev_ids"], order)
        self.assertTrue(validate_panel(self.panel, manifest=self.manifest))
        for case in self.panel["cases"][:2]:
            self.assertEqual(case["source"]["held_out_demo_index"], 2)
            self.assertEqual(case["source"]["visible_demo_indices"], [0, 1])
        for case in self.panel["cases"][2:]:
            self.assertFalse(case["source"]["generalization_evidence"])
            self.assertEqual(case["source"]["training_exposure"], "not-established-by-this-panel")
        with self.assertRaises(TypeError):
            DEFAULT_GATE_POLICY["minimum_held_out_dev_exact"] = 0

    def test_source_mismatch_public_id_and_missing_dev_rejected(self):
        tasks = copy.deepcopy(self.tasks)
        tasks["c"]["train"][-1]["output"] = [[9]]
        with self.assertRaisesRegex(ValueError, "source hash"):
            build_panel(tasks, self.manifest, dev_tasks=2)
        with self.assertRaisesRegex(ValueError, "protected"):
            build_panel(self.tasks, self.manifest, dev_tasks=2, protected_ids=["c"])
        with self.assertRaisesRegex(ValueError, "insufficient"):
            build_panel(self.tasks, self.manifest, dev_tasks=3)
        with self.assertRaisesRegex(ValueError, "manifest required"):
            validate_panel(self.panel, manifest=None)

    def test_rehash_cannot_replace_target_prompt_lineage_or_order(self):
        for change in ("target", "demos", "query_input", "source", "order", "label_prompt"):
            panel = copy.deepcopy(self.panel)
            if change in ("target", "query_input"):
                panel["cases"][0][change] = [[9, 9, 9]]
            elif change == "demos":
                panel["cases"][0]["demos"].append({"input": [[0]], "output": [[9]]})
            elif change == "source":
                panel["cases"][0]["source"]["held_out_demo_index"] = 1
            elif change == "order":
                panel["cases"].reverse()
            else:
                panel["cases"][0]["messages"] = [{"role": "user", "content": "answer 999"}]
            panel["panel_sha256"] = digest({k: v for k, v in panel.items() if k != "panel_sha256"})
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "exact source"):
                validate_panel(panel, manifest=self.manifest)

    def test_correct_fixtures_measure_exact_but_not_neural_proof(self):
        model = FixtureModel(self.panel)
        before = copy.deepcopy(model.config)
        result = self.evaluate(model)
        self.assertTrue(result["complete"])
        self.assertTrue(result["gate_pass"])
        self.assertFalse(result["eligible_for_public_run"])
        self.assertEqual(result["evidence"], "mock_fixture_not_neural_proof")
        self.assertEqual(result["exact"], 4)
        self.assertEqual(result["dev"]["denominator"], 2)
        self.assertEqual(result["learnability_controls"]["denominator"], 2)
        self.assertEqual(result["attempted"], {"generation_calls": 4, "scoring_calls": 4})
        self.assertEqual(result["physical"]["generation_calls"], 4)
        self.assertEqual(result["physical"]["scoring_calls"], 4)
        self.assertEqual(model.config, before)
        with self.assertRaisesRegex(ValueError, "real NativeModel"):
            evaluate_panel(model, self.panel, time.monotonic() + 10, manifest=self.manifest)

    def test_random_wrongshape_empty_and_missing_fail_closed(self):
        for wrong in ("random", "shape", "content", "empty", "missing", "receipt", "deadline", "exception"):
            with self.subTest(wrong=wrong):
                model = FixtureModel(self.panel, wrong=wrong, loss=0.000001)
                before = copy.deepcopy(model.config)
                result = self.evaluate(model)
                self.assertFalse(result["gate_pass"])
                self.assertEqual(result["exact"], 0)
                self.assertEqual(result["denominator"], 4)
                self.assertEqual(model.config, before)
                if wrong in ("missing", "receipt", "deadline", "exception"):
                    self.assertFalse(result["complete"])

    def test_all_generation_precedes_scoring_and_prompt_never_gets_label(self):
        model = FixtureModel(self.panel)
        result = self.evaluate(model)
        self.assertTrue(result["complete"])
        self.assertEqual([entry[0] for entry in model.log], ["generate"] * 4 + ["score"] * 4)
        for index, case in enumerate(self.panel["cases"]):
            self.assertEqual(model.log[index][1], grid_messages(case["demos"], case["query_input"]))
            self.assertNotIn("target", model.log[index][2])
            self.assertNotIn("completion", model.log[index][2])
            self.assertEqual(model.log[index + 4][2], encode_grid(case["target"]))

    def test_budget_and_deadline_missing_rows_do_not_shrink_denominator(self):
        for kwargs in ({"max_generation_calls": 1}, {"max_scoring_calls": 0}):
            result = self.evaluate(FixtureModel(self.panel), **kwargs)
            self.assertFalse(result["complete"])
            self.assertFalse(result["gate_pass"])
            self.assertEqual(len(result["rows"]), 4)
        result = evaluate_panel(FixtureModel(self.panel), self.panel, time.monotonic() - 1,
            manifest=self.manifest, evidence_mode="mock_fixture")
        self.assertEqual(result["attempted"], {"generation_calls": 0, "scoring_calls": 0})
        self.assertFalse(result["complete"])

    def test_optional_programs_use_actual_bounded_vm_demo_proof(self):
        from tools.arc_learning_agent_20261011 import program_tools
        if not program_tools.legacy.capability()["available"]:
            self.skipTest("Linux bounded VM unavailable")
        model = FixtureModel(self.panel)
        original = model.generate
        def generated(messages, **kwargs):
            if kwargs["kind"] == "program":
                # This general transpose is fitted to the authored transpose
                # and dev transpose demonstrations by the actual bounded VM.
                return generation("def transform(grid):\n    return transpose(grid)\n")
            return original(messages, **kwargs)
        model.generate = generated
        with tempfile.TemporaryDirectory() as output:
            result = self.evaluate(model, include_program=True, program_output_dir=output)
        self.assertEqual(result["attempted"]["generation_calls"], 8)
        self.assertTrue(result["complete"], result)
        self.assertGreaterEqual(result["program_demo_fit"], 1)
        proof = next(row["program"]["proof"] for row in result["rows"] if row["program"]["demo_fit"])
        self.assertTrue(proof["receipt"]["owned_descendants_stopped"])
        self.assertGreater(proof["gas_charged"], 0)

    def test_sampling_keys_restored_when_exception_escapes(self):
        model = FixtureModel(self.panel)
        model.config = {"unrelated": 13}
        with self.assertRaises(RuntimeError):
            with greedy_scope(model):
                raise RuntimeError("test")
        self.assertEqual(model.config, {"unrelated": 13})

    def test_strict_predeclared_policy_and_absent_controls(self):
        with self.assertRaisesRegex(ValueError, "gate policy"):
            build_panel(self.tasks, self.manifest, dev_tasks=2,
                gate_policy={"require_all_authored_controls_exact": False, "minimum_held_out_dev_exact": 0})
        panel = build_panel(self.tasks, self.manifest, dev_tasks=2, include_controls=False)
        report = evaluate_panel(FixtureModel(panel), panel, time.monotonic() + 30,
            manifest=self.manifest, evidence_mode="mock_fixture")
        self.assertTrue(report["complete"])
        self.assertFalse(report["gate_pass"])

    def compare(self, model, snapshots=None):
        trainer = FixtureTrainer(model)
        snapshots = snapshots if snapshots is not None else {name: name for name in ("base", "early", "best", "final")}
        report = compare_checkpoints(model, trainer, snapshots, self.panel, deadline=time.monotonic() + 30,
                                    manifest=self.manifest, evidence_mode="mock_fixture")
        return report, trainer

    def test_exact_beats_nll_and_all_same_panel_budget(self):
        model = FixtureModel(self.panel, loss={"base": .00001, "early": .001, "best": 4.0, "final": .000001})
        model.overrides = {"base": "shape", "early": "content", "final": "shape"}
        report, trainer = self.compare(model)
        self.assertEqual(report["selected"], "best")
        self.assertEqual(trainer.restores[-1], "best")
        self.assertTrue(report["gate_pass"])
        self.assertEqual(len({digest(r["budgets"]) for r in report["reports"].values()}), 1)
        self.assertEqual(len({r["panel_sha256"] for r in report["reports"].values()}), 1)

    def test_incomplete_or_no_qualifying_checkpoint_restores_base(self):
        for model, snapshots in ((FixtureModel(self.panel, wrong="shape"), None),
                                 (FixtureModel(self.panel), {"base": "base", "best": "best", "final": "final"})):
            report, trainer = self.compare(model, snapshots)
            self.assertEqual(report["selected"], "base")
            self.assertEqual(report["status"], "gate_blocked_base_fallback")
            self.assertEqual(trainer.restores[-1], "base")
            self.assertFalse(report["gate_pass"])


if __name__ == "__main__":
    unittest.main()

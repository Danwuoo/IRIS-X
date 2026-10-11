"""Scripted-model controller tests with actual CPU bounded program execution.

ScriptedModel/ScriptedTrainer below are control fixtures, not neural training or
model-quality evidence. Their program outputs are checked by the real pinned VM.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from tools.arc_learning_agent_20261011 import controller as c
from tools.arc_learning_agent_20261011.grid_codec import decode_grid, encode_grid
from tools.arc_learning_agent_20261011.budget import WorkLedger, DEFAULT_CAPS, BudgetExceeded

IDENTITY = "def transform(grid):\n    return copy_grid(grid)\n"
RECOLOR = """def transform(grid):
    out = copy_grid(grid)
    for r in range(len(out)):
        for col in range(len(out[r])):
            if out[r][col] == 1:
                out[r][col] = 2
    return out
"""


class ScriptedTrainer:
    """MOCKED task adaptation fixture; never reports itself as actual training."""
    def __init__(self):
        self.state = "global"
        self.active = None
        self.adapted_demos = []
        self.reset_count = 0

    def fingerprint(self):
        return {"sha256": hashlib.sha256(("scripted-" + self.state).encode()).hexdigest()}

    def begin_task(self, task_id):
        if self.active is not None:
            raise ValueError("task state leaked")
        self.active = task_id
        self.state = "global"
        return {"adapter_sha256": self.fingerprint()["sha256"], "test_fixture": "mocked trainer"}

    def adapt_task(self, task_id, demos, *, max_steps, deadline):
        assert task_id == self.active
        self.adapted_demos.append(copy.deepcopy(demos))
        self.state = "task"
        return {"status": "scripted_only", "steps": 1, "input_tokens": 10, "supervised_tokens": 2,
                "adapter_after_sha256": self.fingerprint()["sha256"]}

    def end_task(self):
        self.state, self.active = "global", None
        self.reset_count += 1
        return {"adapter_sha256": self.fingerprint()["sha256"]}


class ScriptedModel:
    """MOCKED native generation/scoring fixture. Program verifier remains real."""
    def __init__(self, trainer, grids=None, programs=None, score_fn=None):
        self.trainer = trainer
        self.grids = {key: list(values) for key, values in (grids or {}).items()}
        self.programs = list(programs or [])
        self.generations, self.scores = [], []
        self.score_fn = score_fn

    def generate(self, messages, *, kind, seed, max_new_tokens, deadline):
        self.generations.append({"kind": kind, "messages": copy.deepcopy(messages), "state": self.trainer.state})
        if kind == "program":
            text = self.programs.pop(0) if self.programs else "def transform(:"
        elif self.grids.get(self.trainer.state):
            value = self.grids[self.trainer.state].pop(0)
            if isinstance(value, Exception):
                raise value
            text = encode_grid(value) if isinstance(value, list) else value
        else:
            text = messages[-1]["content"].split("\n\nQuery\nInput:\n")[-1].removesuffix("\nOutput:")
        return {"text": text, "input_tokens": 10, "output_tokens": 3, "elapsed_seconds": .001,
                "finish_reason": "scripted", "valid": True, "forward_calls": 1, "forward_input_tokens": 10}

    def score_completion(self, messages, completion, *, deadline):
        self.scores.append({"messages": copy.deepcopy(messages), "completion": completion, "state": self.trainer.state})
        receipt = {"nll_sum": 2., "token_count": 2, "mean_nll": 1., "input_tokens": 12, "elapsed_seconds": .001,
                   "valid": True, "forward_calls": 1, "forward_input_tokens": 12}
        if self.score_fn:
            receipt.update(self.score_fn(self.scores[-1], len(self.scores)))
        return receipt


def identity_task():
    return {"train": [{"input": [[1, 2]], "output": [[1, 2]]}, {"input": [[3], [0]], "output": [[3], [0]]}],
            "test": [{"input": [[4, 0], [2, 3]]}]}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def solve(self, task=None, config=None, model=None, trainer=None, name="task", deadline=None, ledger=None):
        trainer = trainer or (model.trainer if model else ScriptedTrainer())
        model = model or ScriptedModel(trainer)
        result = c.solve_task(name, task or identity_task(), model=model, trainer=trainer,
                             config=config or {}, deadline=deadline or time.monotonic() + 20,
                             output_dir=self.root / name, work_ledger=ledger)
        return result, model, trainer

    def test_all_eight_augmentation_views_are_reversible(self):
        for grid in ([[0]], [[1, 2, 3], [4, 5, 6]], [[0, 9], [2, 3], [4, 1]]):
            for view in c.VIEWS:
                self.assertEqual(view.inverse(view.forward(grid)), grid)
        self.assertEqual(len({_hash for _hash in [c._hash(v.forward([[1, 2, 3], [4, 5, 6]])) for v in c.VIEWS]}), 8)

    def test_shared_physical_work_three_policies_and_demo_only_adaptation(self):
        task = identity_task()
        result, model, trainer = self.solve(task)
        self.assertEqual(result["status"], "complete", result["evidence"])
        for policy in result["policies"].values():
            self.assertEqual(policy[0]["candidates"], [task["test"][0]["input"]])
        usage = result["physical_usage"]
        self.assertEqual(usage["generation_calls"], 4)
        self.assertEqual(usage["scoring_forwards"], 16)
        self.assertEqual(usage["cpu_checks"], 0)
        self.assertEqual(usage["input_tokens"], 4 * 10 + 16 * 12 + 10)
        self.assertEqual(usage["model_forward_calls"], 20)
        self.assertEqual(trainer.adapted_demos, [task["train"]])
        self.assertEqual(trainer.state, "global")
        self.assertEqual(trainer.reset_count, 1)
        self.assertTrue(all(row["state"] == "global" for row in model.scores[:8]))
        self.assertTrue(all(row["state"] == "task" for row in model.scores[8:]))
        json.dumps(result, allow_nan=False)

    @unittest.skipUnless(c.legacy.capability()["available"], "real CPU verifier requires Linux")
    def test_real_feedback_repair_and_full_agent_uses_program_without_gating_direct(self):
        task = {"train": [{"input": [[1]], "output": [[2]]}, {"input": [[3]], "output": [[3]]}],
                "test": [{"input": [[1, 3]]}]}
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, grids={"global": [[[7, 7]]], "task": [[[6, 6]]]}, programs=[IDENTITY, RECOLOR])
        result, model, trainer = self.solve(task, {"global_views": 1, "adapted_views": 1}, model=model)
        self.assertEqual(result["status"], "complete", result["evidence"])
        self.assertEqual(result["policies"]["global_grid"][0]["candidates"], [[[7, 7]]])
        self.assertEqual(result["policies"]["task_ttt"][0]["candidates"], [[[6, 6]]])
        self.assertEqual(result["policies"]["full_agent"][0]["candidates"][0], [[2, 3]])
        self.assertEqual(result["physical_usage"]["generation_calls"], 4)
        self.assertEqual(result["physical_usage"]["cpu_checks"], 3)
        programs = [row for row in model.generations if row["kind"] == "program"]
        self.assertTrue(all(row["state"] == "global" for row in programs))
        self.assertIn('"partial_score":0.5', programs[1]["messages"][-1]["content"])
        queries = [row for row in result["evidence"] if row["kind"] == "query_execution"]
        self.assertEqual(len(queries), 1)
        self.assertTrue(queries[0]["payload"]["receipt"]["owned_descendants_stopped"])
        self.assertEqual(trainer.reset_count, 1)

    def test_disagreement_escalates_but_two_view_agreement_skips_programs(self):
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, grids={"global": [[[1]], c.VIEWS[1].forward([[2]])]}, programs=["broken"])
        result, _, _ = self.solve(config={"repair_attempts": 0, "adapted_views": 0}, model=model)
        decisions = [r["payload"] for r in result["evidence"] if r["kind"] == "decision"]
        self.assertIn("global reversible views disagree", [r["reason"] for r in decisions])
        self.assertTrue(result["policies"]["full_agent"][0]["candidates"])

    def test_complete_common_views_outrank_missing_not_low_partial_average(self):
        trainer = ScriptedTrainer()
        # Any completion containing zero gets invalid likelihood, with a tempting
        # zero value that must not count. Other grid has a complete finite score.
        def score(row, index):
            valid = index % 2 == 0
            return {"valid": valid, "mean_nll": 1 if valid else 0, "nll_sum": 2 if valid else 0}
        model = ScriptedModel(trainer, grids={"global": [[[1]], c.VIEWS[1].forward([[2]])]}, score_fn=score)
        result, _, _ = self.solve(config={"program_policy": "never", "adapted_views": 0, "ttt_steps": 0}, model=model)
        selection = next(row["payload"] for row in result["evidence"] if row["kind"] == "selection" and row["payload"]["policy"] == "global_grid")
        scores = {row["grid_sha256"]: row["common_view_mean_nll"] for row in selection["likelihood"]}
        self.assertIsNotNone(scores[selection["selected_grid_sha256"][0]])
        self.assertIsNone(scores[selection["selected_grid_sha256"][1]])

    def test_global_score_and_task_score_each_use_identical_ordered_views(self):
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, grids={"global": [[[1]], c.VIEWS[1].forward([[2]])]})
        result, model, _ = self.solve(config={"program_policy": "never", "adapted_views": 0}, model=model)
        for phase in ("global", "task"):
            rows = [r["payload"] for r in result["evidence"] if r["kind"] == "likelihood" and r["payload"]["phase"] == phase]
            by_grid = {}
            for row in rows:
                by_grid.setdefault(row["grid_sha256"], []).append(row)
            self.assertEqual(len(by_grid), 2)
            self.assertTrue(all([r["view"] for r in values] == list(range(8)) for values in by_grid.values()))
            self.assertEqual(len({r["adapter_sha256"] for r in rows}), 1)

    def test_expired_deadline_preserves_all_policy_denominators(self):
        result, model, trainer = self.solve(deadline=time.monotonic() - 1)
        self.assertEqual(result["status"], "budget_stopped")
        self.assertEqual(result["physical_usage"]["generation_calls"], 0)
        self.assertEqual(len(model.generations), 0)
        for policy in result["policies"].values():
            self.assertEqual(len(policy), 1)
            self.assertEqual(policy[0]["status"], "missing")

    def test_generation_floor_round_robin_before_second_view(self):
        task = identity_task()
        task["test"].append({"input": [[8]]})
        result, model, _ = self.solve(task, {"max_generation_calls": 2, "program_policy": "never"})
        self.assertTrue(all(row["candidates"] for row in result["policies"]["global_grid"]))
        self.assertEqual(result["physical_usage"]["generation_calls"], 2)

    def test_failed_generation_charged_once_with_conservative_unknown_tokens(self):
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, grids={"global": [RuntimeError("fixture failure")]})
        result, _, _ = self.solve(config={"global_views": 1, "adapted_views": 0, "program_policy": "never", "ttt_steps": 0}, model=model)
        self.assertEqual(result["physical_usage"]["generation_calls"], 1)
        self.assertEqual(result["physical_usage"]["input_tokens"], 6144)
        self.assertEqual(result["physical_usage"]["output_tokens"], 2048)
        self.assertEqual(result["physical_usage"]["unknown_usage_events"], 1)

    def test_budget_refusal_is_not_a_physical_model_call(self):
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, grids={"global": [BudgetExceeded("fixture cap")]})
        result, _, _ = self.solve(config={"global_views": 1, "adapted_views": 0, "program_policy": "never", "ttt_steps": 0}, model=model)
        self.assertEqual(result["status"], "budget_stopped")
        self.assertEqual(result["physical_usage"]["generation_calls"], 0)
        self.assertEqual(result["physical_usage"]["unknown_usage_events"], 0)

    def test_task_memory_isolation_and_actual_reset_finally(self):
        trainer = ScriptedTrainer()
        first, _, _ = self.solve(trainer=trainer, name="first")
        second, _, _ = self.solve(trainer=trainer, name="second")
        self.assertTrue(all(r["task_id"] == "first" for r in first["evidence"]))
        self.assertTrue(all(r["task_id"] == "second" for r in second["evidence"]))
        self.assertEqual(first["evidence"][0]["id"], second["evidence"][0]["id"])
        self.assertEqual(trainer.reset_count, 2)
        with mock.patch.object(trainer, "adapt_task", side_effect=RuntimeError("training fixture failure")):
            failed, _, _ = self.solve(trainer=trainer, name="failed")
        self.assertEqual(failed["status"], "error")
        self.assertEqual(trainer.state, "global")
        self.assertIsNone(trainer.active)
        self.assertTrue(failed["policies"]["global_grid"][0]["candidates"])

    def test_same_input_deterministic_ranking_and_exact_cap(self):
        a, _, _ = self.solve(config={"max_scoring_forwards": 1}, name="a")
        b, _, _ = self.solve(config={"max_scoring_forwards": 1}, name="b")
        self.assertEqual(a["policies"]["full_agent"][0]["candidates"], b["policies"]["full_agent"][0]["candidates"])
        self.assertEqual(a["physical_usage"]["scoring_forwards"], 1)
        self.assertIn("scoring_forwards_cap", a["stop_reasons"])

    def test_query_answer_and_extra_metadata_rejected(self):
        task = identity_task()
        task["test"][0]["output"] = [[5]]
        with self.assertRaises(ValueError):
            self.solve(task)

    def test_typed_memory_rejects_foreign_parents_and_nonfinite(self):
        memory = c.EvidenceMemory("fixture", max_records=1)
        with self.assertRaises(ValueError):
            memory.add(c.EvidenceKind.ERROR, {}, ["foreign"])
        with self.assertRaises(ValueError):
            memory.add(c.EvidenceKind.ERROR, {"x": float("nan")})
        memory.add(c.EvidenceKind.TASK, {})
        with self.assertRaises(ValueError):
            memory.add(c.EvidenceKind.ERROR, {})

    def test_configuration_cannot_raise_hard_limits_or_shrink_common_views(self):
        for cfg in ({"initial_programs": 3}, {"global_views": 3}, {"scoring_views": 4}, {"max_candidates": 33}):
            with self.assertRaises(ValueError):
                self.solve(config=cfg)

    @unittest.skipUnless(c.legacy.capability()["available"], "real CPU verifier requires Linux")
    def test_cpu_session_ledger_reserves_real_checks_once(self):
        ledger = WorkLedger(self.root / "ledger.jsonl")
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, programs=[IDENTITY])
        result, _, _ = self.solve(config={"program_policy": "always"}, model=model, ledger=ledger)
        self.assertEqual(result["physical_usage"]["cpu_checks"], 2)
        self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 2)
        self.assertEqual(ledger.summary()["charged"]["gas"], result["physical_usage"]["program_gas"])
        self.assertFalse(ledger.summary()["pending"])

    @unittest.skipUnless(c.legacy.capability()["available"], "real CPU verifier requires Linux")
    def test_conflicting_fitted_programs_preserve_direct_grid_floor(self):
        task = {"train": [{"input": [[1]], "output": [[1]]}, {"input": [[3]], "output": [[3]]}],
                "test": [{"input": [[1, 2]]}]}
        flip = "def transform(grid):\n    return [row[::-1] for row in grid]\n"
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, grids={"global": [[[7, 7]]], "task": [[[6, 6]]]}, programs=[IDENTITY, flip])
        result, _, _ = self.solve(task, {"global_views": 1, "adapted_views": 1, "initial_programs": 2}, model=model)
        selected = result["policies"]["full_agent"][0]["candidates"]
        self.assertEqual(len(selected), 2)
        self.assertIn(selected[0], ([[1, 2]], [[2, 1]]))
        self.assertIn(selected[1], ([[7, 7]], [[6, 6]]))
        self.assertEqual(result["physical_usage"]["cpu_checks"], 4)

    def test_model_admission_exclusion_is_attempt_not_physical_forward(self):
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer)
        with mock.patch.object(model, "generate", return_value={"text": "", "valid": False, "dispatched": False,
                "input_tokens": 7000, "output_tokens": 0, "error": "context excluded"}):
            result, _, _ = self.solve(config={"global_views": 1, "adapted_views": 0, "program_policy": "never", "ttt_steps": 0}, model=model)
        self.assertEqual(result["physical_usage"]["generation_attempts"], 1)
        self.assertEqual(result["physical_usage"]["generation_calls"], 0)
        self.assertEqual(result["physical_usage"]["input_tokens"], 0)

    def test_consumed_output_identity_rejected_before_any_model_work(self):
        result, _, _ = self.solve()
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer)
        with self.assertRaisesRegex(ValueError, "consumed"):
            self.solve(model=model)
        self.assertEqual(model.generations, [])

    def test_cpu_zero_budget_never_dispatches_real_verifier(self):
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, programs=[IDENTITY])
        with mock.patch.object(c.program_tools, "verify_program") as verify:
            result, _, _ = self.solve(config={"program_policy": "always", "max_cpu_checks": 0}, model=model)
        verify.assert_not_called()
        self.assertTrue(result["policies"]["full_agent"][0]["candidates"])
        self.assertEqual(result["physical_usage"]["cpu_checks"], 0)

    def test_cpu_session_cap_refusal_preserves_direct_candidates(self):
        ledger = WorkLedger(self.root / "ledger-cpu-zero.jsonl", caps={**DEFAULT_CAPS, "cpu_checks": 0})
        trainer = ScriptedTrainer()
        model = ScriptedModel(trainer, programs=[IDENTITY])
        result, _, _ = self.solve(config={"program_policy": "always"}, model=model, ledger=ledger)
        self.assertEqual(result["status"], "budget_stopped")
        self.assertTrue(result["policies"]["full_agent"][0]["candidates"])
        self.assertEqual(result["physical_usage"]["cpu_checks"], 0)

    def test_unknown_adaptation_charged_and_global_state_restored(self):
        trainer = ScriptedTrainer()
        with mock.patch.object(trainer, "adapt_task", side_effect=RuntimeError("unknown optimizer failure")):
            result, _, _ = self.solve(trainer=trainer, config={"ttt_steps": 3})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["physical_usage"]["optimizer_steps"], 3)
        self.assertEqual(result["physical_usage"]["unknown_usage_events"], 1)
        self.assertEqual(trainer.state, "global")


@unittest.skipUnless(__import__('os').environ.get("ARC_LEARNING_NEURAL_TESTS") == "1",
                     "explicit actual tiny CPU neural integration only")
class ActualTinyNeuralControllerTests(unittest.TestCase):
    def test_global_sft_then_demo_ttt_and_three_policy_controller(self):
        """ACTUAL tiny neural updates/generation/scoring; no production-quality claim."""
        from tools.arc_learning_agent_20261011.tests.test_training_neural import TrainingNeuralTests
        TrainingNeuralTests.setUpClass()
        fixture = TrainingNeuralTests()
        trainer = fixture.make_trainer()
        self.addCleanup(trainer.native.close)
        trained = fixture.run_steps(trainer, 1)
        self.assertEqual(trained["steps"], 1)
        frozen = trainer.freeze_global()
        task = {"train": [{"input": [[1]], "output": [[2]]}, {"input": [[3]], "output": [[3]]}],
                "test": [{"input": [[1, 3]]}]}
        with tempfile.TemporaryDirectory() as root:
            result = c.solve_task("actual-tiny-controller", task, model=trainer.native, trainer=trainer,
                                  config={"global_views": 1, "adapted_views": 1, "program_policy": "never",
                                          "ttt_steps": 1, "max_new_tokens": 64},
                                  deadline=time.monotonic() + 60, output_dir=root)
        self.assertEqual(result["status"], "complete", [r for r in result["evidence"] if r["kind"] == "error"])
        self.assertEqual(result["physical_usage"]["generation_calls"], 2)
        self.assertEqual(result["physical_usage"]["optimizer_steps"], 1)
        self.assertGreaterEqual(result["physical_usage"]["scoring_forwards"], 16)
        adaptation = next(r["payload"]["receipt"] for r in result["evidence"] if r["kind"] == "adaptation")
        self.assertNotEqual(adaptation["adapter_before_sha256"], adaptation["adapter_after_sha256"])
        self.assertEqual(trainer.fingerprint(), frozen["fingerprint"])
        self.assertIsNone(trainer.optimizer)
        self.assertTrue(all(p.grad is None for p in trainer.parameters.values()))
        self.assertTrue(all(rows[0]["candidates"] for rows in result["policies"].values()))

    def test_actual_trainer_exception_reset_is_not_false_reset_failure(self):
        from tools.arc_learning_agent_20261011.tests.test_training_neural import TrainingNeuralTests
        TrainingNeuralTests.setUpClass()
        trainer = TrainingNeuralTests().make_trainer()
        self.addCleanup(trainer.native.close)
        frozen = trainer.freeze_global()
        with tempfile.TemporaryDirectory() as root, mock.patch.object(trainer, "train", side_effect=RuntimeError("injected failure")):
            result = c.solve_task("actual-reset-failure", identity_task(), model=trainer.native, trainer=trainer,
                                  config={"global_views": 1, "adapted_views": 1, "program_policy": "never",
                                          "ttt_steps": 1, "max_new_tokens": 64},
                                  deadline=time.monotonic() + 60, output_dir=root)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(trainer.active_task_id)
        self.assertTrue(trainer.last_task_reset_receipt["restored"])
        self.assertEqual(trainer.fingerprint(), frozen["fingerprint"])
        self.assertFalse(any(row["kind"] == "error" and row["payload"].get("action") == "end_task" for row in result["evidence"]))

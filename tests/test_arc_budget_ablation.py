from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from irisx import arc_budget_ablation as budget
from irisx import kaggle_runner_budget_ablation as runner
from irisx.errors import ValidationError
from irisx.transport import digest_path


class BudgetAblationTests(unittest.TestCase):
    def test_thinking_final_boundary_and_cap_are_enforced(self) -> None:
        final, state = runner.split_final_completion("reasoning 123\n</think>\n012\n345", enable_thinking=True)
        self.assertEqual(("012\n345", "final_present"), (final, state))
        self.assertEqual([[0, 1, 2], [3, 4, 5]], budget.parse_grid_text(final))
        self.assertEqual((None, "missing_final_separator"), runner.split_final_completion("123\n456", enable_thinking=True))
        self.assertEqual((None, "empty_final"), runner.split_final_completion("123</think>  ", enable_thinking=True))
        self.assertFalse(runner.final_is_complete("maximum_new_tokens", False, final))
        self.assertFalse(runner.final_is_complete("eos_token", True, final))
        self.assertTrue(runner.final_is_complete("eos_token", False, final))
        self.assertEqual(("012\n345", "thinking_off"), runner.split_final_completion("012\n345", enable_thinking=False))

    def test_512_case_source_audit_separates_full_visible_and_index_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            training = root / "training"
            training.mkdir()
            competition = {}
            split = []
            baseline = []
            holdout = []
            for index in range(512):
                task_id = "f3e62deb" if index == 511 else f"{index:08x}"
                group = "optimization-train" if index < 256 else ("selection-dev" if index < 384 else "locked-holdout")
                visible = {"train": [{"input": [[index % 10]], "output": [[(index + 1) % 10]]}],
                           "test": [{"input": [[0]]}, {"input": [[1]]}]}
                competition[task_id] = visible
                split.append({"task_id": task_id, "group": group})
                if group == "locked-holdout":
                    holdout.append({"task_id": task_id, "group": group, **visible})
                else:
                    baseline.append({"task_id": task_id, "group": group, "train": visible["train"], "test": visible["test"][:1]})
                    (training / f"{task_id}.json").write_text(json.dumps({"train": visible["train"],
                                                                            "test": [{**pair, "output": [[2]]} for pair in visible["test"]]}))
            paths = {"competition": root / "competition.json", "split": root / "split.json", "baseline": root / "baseline.json", "holdout": root / "holdout.zip"}
            paths["competition"].write_text(json.dumps(competition))
            paths["split"].write_text(json.dumps({"records": split}))
            paths["baseline"].write_text(json.dumps({"cases": baseline}))
            with zipfile.ZipFile(paths["holdout"], "w") as archive:
                archive.writestr("cases/solver-cases.json", json.dumps({"cases": holdout}))
            with mock.patch.object(budget, "COMPETITION_SHA256", digest_path(paths["competition"]).removeprefix("sha256:")):
                report = budget.audit_visible_source(paths["competition"], paths["baseline"], paths["holdout"], paths["split"], training)
                self.assertTrue(report["executable_parity"])
                self.assertEqual(0, len(report["mismatches"]))
                self.assertEqual(2, report["f3e62deb_old_gate"]["pinned_test_input_count"])
                competition["00000000"]["train"][0]["output"] = [[9]]
                paths["competition"].write_text(json.dumps(competition))
                with mock.patch.object(budget, "COMPETITION_SHA256", digest_path(paths["competition"]).removeprefix("sha256:")):
                    report = budget.audit_visible_source(paths["competition"], paths["baseline"], paths["holdout"], paths["split"], training)
                    self.assertFalse(report["executable_parity"])
                    self.assertEqual(["00000000"], report["executable_mismatches"])

    def test_atomic_ledger_rejects_over_budget_and_preserves_prior_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.json"
            ledger = {"trial_id": budget.TRIAL_ID, "generation_ceiling": 576,
                      "development": budget.ACTIVE_REFLECTION_PROFILE,
                      "reflection": {**budget.ACTIVE_REFLECTION_PROFILE, "proposer_calls": 0},
                      "diagnostic": {"reserved_generations": 192, "consumed_generations": 0},
                      "validation": {"reserved_generations": 384, "consumed_generations": 0}}
            budget.atomic_json(path, ledger)
            budget.update_ledger(path, "diagnostic", consumed_generations=192)
            self.assertEqual(192, json.loads(path.read_bytes())["diagnostic"]["consumed_generations"])
            with self.assertRaises(ValidationError):
                budget.update_ledger(path, "validation", consumed_generations=385)
            self.assertEqual(0, json.loads(path.read_bytes())["validation"]["consumed_generations"])

    def test_qualification_gate_and_tie_break(self) -> None:
        score = {"run_id": budget.DIAGNOSTIC_RUN, "arms": {
            "A1": {"net_additional_correct": 4, "baseline_correct_retained": 16, "correct": 22, "elapsed_p95_seconds": 20},
            "A2": {"net_additional_correct": 4, "baseline_correct_retained": 16, "correct": 22, "elapsed_p95_seconds": 20},
            "A3": {"net_additional_correct": 3, "baseline_correct_retained": 18, "correct": 22, "elapsed_p95_seconds": 10}}}
        self.assertEqual("A1", budget.choose_validation_arm(score)["selected_arm"])
        score["arms"]["A1"]["net_additional_correct"] = 3
        self.assertEqual("A2", budget.choose_validation_arm(score)["selected_arm"])

    def test_dynamic_dispatch_exposes_parent_deadline_without_retry(self) -> None:
        queue = budget.DispatchState.from_jobs(["one:A1", "two:A2"])
        self.assertEqual("one:A1", queue.dispatch(0, 300.0))
        self.assertEqual([], queue.expired(299.99))
        self.assertEqual([(0, "one:A1")], queue.expired(300.0))
        queue.finish(0, "one:A1", "timeout")
        self.assertEqual("two:A2", queue.dispatch(1, 600.0))
        self.assertEqual(["one:A1"], list(queue.terminal))


if __name__ == "__main__":
    unittest.main()

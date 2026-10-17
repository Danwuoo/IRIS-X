"""Train-only synthetic control/deadline tests; no benchmark answers or GPU."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

_MISSING = [name for name in ("torch", "transformers", "peft", "pydantic")
            if importlib.util.find_spec(name) is None]
if not _MISSING:
    from tools.nvarc_posttrain_20261017 import experiment as ex, worker
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline


def cfg():
    return dict(job_id="2b-H", arm="H", seed=7, context_tokens=8192,
                generation_tokens=931, group_size=8, rollout_microbatch=2,
                learning_rate=2e-5, ttt_lr=5e-5, ttt_steps=32, public_views=2,
                dev_parents=1, sft_steps=0, hybrid_warmup_steps=0, rl_groups=1)


def task():
    return {"train": [{"input": [[1]], "output": [[2]]},
                      {"input": [[3]], "output": [[4]]}], "test": [{"input": [[5]]}]}


def public_fixture():
    result = {f"task{i:03}": task() for i in range(120)}
    for i in range(47):
        result[f"task{i:03}"]["test"].append({"input": [[6]]})
    return result


def row(value=2):
    return dict(input_ids=[14, 11, 10, 1, 15, 14, 12, 10, value, 15],
                prompt_length=8, completion_tokens=2, stop="eos",
                behavior_log_probs=[0.] * 8 + [-.3, -.2])


@unittest.skipIf(bool(_MISSING), "Optional model dependencies missing: " + ", ".join(_MISSING))
class ExperimentControlTests(unittest.TestCase):
    def test_independent_training_seeds_share_exact_evaluation_protocol(self):
        result = dict(ranked_grids=[[[2]]], views=[{"tokens": 2}], complete=True)
        panels = []
        for seed in (1, 999):
            with patch.object(ex, "infer_query", return_value=result):
                panels.append(ex.evaluate_panel(SimpleNamespace(), {"dev": task()}, {**cfg(), "seed": seed},
                    deadline=10**12, audit=Mock(), ids=["dev"]))
        self.assertEqual(panels[0]["panel_sha256"], panels[1]["panel_sha256"])
        engine = SimpleNamespace(generate=Mock(return_value=[row()]))
        with patch.object(ex, "inference_views", return_value=[{"transform": {}}]) as views, \
                patch.object(ex, "view_inputs", return_value=(task()["train"], [[1]])), \
                patch.object(ex, "transform", side_effect=lambda grid, **kw: grid):
            ex.infer_query(engine, task(), [[1]], {**cfg(), "seed": 999}, task_id="dev", views=1, deadline=10**12)
        self.assertEqual(views.call_args.kwargs["seed"], 20261017)

    def test_partial_view_preserves_completed_candidates(self):
        engine = SimpleNamespace(generate=Mock(side_effect=[[row()], PhaseDeadline("later view")]))
        with patch.object(ex, "inference_views", return_value=[{"transform": {}}] * 2), \
                patch.object(ex, "view_inputs", return_value=(task()["train"], [[1]])), \
                patch.object(ex, "transform", side_effect=lambda grid, **kw: grid):
            result = ex.infer_query(engine, task(), [[1]], cfg(), task_id="train", views=2, deadline=10**12)
        self.assertEqual(result["ranked_grids"], [[[2]]])
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["views"]), 1)

    def test_partial_group_counts_exact_and_discards_uncommitted_group(self):
        engine = SimpleNamespace(model=object(), forward_calls=0, sampled_tokens=0,
            optimizer_steps=0, base_identity={"fixture": True},
            generate=Mock(side_effect=[[row(), row()], PhaseDeadline("second microbatch")]),
            af3_update=Mock())
        optimizer = Mock()
        with patch.object(ex, "make_optimizer", return_value=optimizer), \
                patch.object(ex, "loo_example", return_value=(task()["train"], [[1]], [[2]])):
            report = ex.train_arm(engine, {"train": task()}, cfg(), deadline=10**12, audit=Mock())
        self.assertEqual(report["rollouts"], 2)
        self.assertEqual(report["exact_rollouts"], 2)
        self.assertEqual(report["rollout_microbatches_attempted"], 2)
        self.assertEqual(report["partial_group_rollouts_discarded"], 2)
        self.assertEqual(report["rl_updates"], 0)
        self.assertFalse(report["completed_requested_work"])
        engine.af3_update.assert_not_called()
        optimizer.zero_grad.assert_called_once_with(set_to_none=True)

    def test_incomplete_ttt_cannot_claim_complete_public(self):
        engine = SimpleNamespace(model=object())
        prediction = dict(ranked_grids=[[[2]]], candidates=[{"grid": [[2]]}],
                          ranked_candidate_indices=[0], views=[], ranking="fixture", complete=True)
        adaptation = dict(steps=0, attempts=0, requested_steps=32, all_requested_complete=False)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(worker, "adapter_state", return_value={"fixture": 1}), \
                patch.object(worker, "state_digest", return_value="state"), \
                patch.object(worker, "restore_state") as restore, \
                patch.object(worker, "adapt_task", return_value=adaptation), \
                patch.object(worker, "infer_query", return_value=prediction):
            report = worker.run_public(engine, public_fixture(), cfg(), deadline=10**12,
                                       audit=Mock(), output=Path(directory))
            pools = json.loads((Path(directory) / "pools.json").read_bytes())
            adaptations = json.loads((Path(directory) / "task-adaptations.json").read_bytes())
        self.assertFalse(report["complete"])
        self.assertTrue(report["queries_complete"])
        self.assertFalse(report["requested_adaptation_complete"])
        self.assertEqual(report["ttt_committed_updates"], 0)
        self.assertEqual(len(adaptations), 120)
        self.assertEqual(sum(len(r["tests"]) for r in pools["records"]), 167)
        self.assertEqual(restore.call_count, 121)

    def test_production_settings_reject_zero_ttt(self):
        with self.assertRaisesRegex(ValueError, "1..128"):
            worker.settings({"job_id": "2b-S", "arm": "S", "seed": 1, "parameters": {"ttt_steps": 0}})

    def test_dev_partial_generation_is_not_selection_eligible(self):
        result = dict(ranked_grids=[[[2]]], views=[{"tokens": 2}], complete=False)
        with patch.object(ex, "infer_query", return_value=result):
            report = ex.evaluate_panel(SimpleNamespace(), {"dev": task()}, cfg(),
                                       deadline=10**12, audit=Mock(), ids=["dev"])
        self.assertEqual(report["pass2"], 1)
        self.assertFalse(report["complete"])
        self.assertEqual(report["completed_queries"], 0)
        with self.assertRaisesRegex(ValueError, "complete identical"):
            ex.select_checkpoint([dict(dev=report, training_seconds=1., checkpoint_id="partial")])

    def test_dev_ttt_reset_and_lifecycle_includes_non_inference_work(self):
        result = dict(ranked_grids=[[[2]]], views=[{"tokens": 2}], complete=True)
        adaptation = dict(steps=1, all_requested_complete=True)
        with patch.object(ex, "adapter_state", return_value={"fixture": 1}), \
                patch.object(ex, "state_digest", return_value="state"), \
                patch.object(ex, "restore_state") as restore, \
                patch.object(ex, "adapt_task", return_value=adaptation), \
                patch.object(ex, "infer_query", return_value=result), \
                patch.object(ex, "check_deadline"), \
                patch.object(ex.time, "time", side_effect=[0., 1., 5., 7., 9., 12.]):
            report = ex.evaluate_panel(SimpleNamespace(model=object()), {"dev": task()}, cfg(),
                                       deadline=10**12, audit=Mock(), ids=["dev"], ttt_steps=1)
        self.assertTrue(report["complete"])
        self.assertEqual(report["records"][0]["inference_seconds"], 2.)
        self.assertEqual(report["records"][0]["task_lifecycle_seconds"], 8.)
        self.assertEqual(report["unamortized_setup_restore_seconds"], 4.)
        self.assertEqual(restore.call_count, 2)


if __name__ == "__main__":
    unittest.main()

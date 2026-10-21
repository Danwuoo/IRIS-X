"""CPU tensor and real subprocess faults, never public model capability evidence."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.public_full_calibrated_solver import core, controller, worker
from tools.public_full_calibrated_solver.supervisor import supervised_run
from tools.public_sft141_diagnostic import contract as codec
from tools.public_sft141_submission import contract as wire, files
from tools.public_demo_calibration import core as calibration
from tests.platform_requirements import requires_linux


def fixture(n=2):
    return {f"task-{n-i}": {"train": [
        {"input": [[1, 2], [3, 4]], "output": [[2], [3]]},
        {"input": [[4, 5], [6, 7]], "output": [[5, 6]]}],
        "test": [{"input": [[1, 2, 3], [4, 5, 6]]}] + ([{"input": [[7], [8]]}] if i == 0 else [])}
        for i in range(n)}


class FixtureBackend:
    def __init__(self, plan, deadline, mode="normal"):
        self.max_context = plan["configuration"]["context_cap"]
        self.metadata = {"backend": "synthetic-no-public-model-evidence"}
        self.deadline, self.mode, self.state = deadline, mode, 0
        self.loo = core.loo_cases(plan)
        self.generation = core.generation_cases(plan)
        self.scores = self.generated = 0
        if mode == "load-fail":
            raise RuntimeError("synthetic load failure")
        if mode in ("descendant", "escaped-descendant"):
            p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=mode == "escaped-descendant")
            self.metadata["child_pid"] = p.pid
            if mode == "escaped-descendant":
                time.sleep(.2)

    def score(self, prompt, answer, deadline):
        if deadline is not self.deadline:
            raise ValueError("clock replaced")
        self.scores += 1
        if self.mode == "loo-fail" and self.scores == 3:
            raise RuntimeError("LOO failure")
        if self.mode == "loo-hang" and self.scores == 3:
            time.sleep(60)
        if self.mode == "nll-fail" and self.scores == len(self.loo) + 3:
            raise RuntimeError("NLL failure")
        if self.mode == "nll-hang" and self.scores == len(self.loo) + 3:
            time.sleep(60)
        if self.mode == "mutate" and self.scores == 3:
            self.state += 1
        begin = time.monotonic()
        if self.scores <= len(self.loo):
            view = self.loo[self.scores - 1][0]["view"]
            strength = 3. if view >= 6 else .2
        else:
            strength = 3. if answer[0] == 3 else .2
        if self.mode == "tensor":
            import torch
            from tools.public_sft141_diagnostic.model_worker import full_answer_nll
            torch.set_num_threads(1)
            logits = torch.zeros((1, len(prompt) + len(answer) - 1, 16), dtype=torch.float32)
            for j, token in enumerate(answer):
                logits[0, len(prompt) - 1 + j, token] = strength
            nll = full_answer_nll(logits, len(prompt), answer)
        else:
            nll = len(answer) * math.log1p(15 * math.exp(-strength))
        return {"nll": nll, "seconds": time.monotonic() - begin, "memory": None,
                "input_tokens": len(prompt) + len(answer) - 1, "answer_tokens": len(answer),
                "batch_size": 1, "use_cache": False}

    def generate(self, prompt, max_new_tokens, deadline):
        if max_new_tokens != 931 or deadline is not self.deadline:
            raise ValueError("generation contract changed")
        spec, expected = self.generation[self.generated]
        if prompt != expected:
            raise ValueError("not full original support or not view-major")
        self.generated += 1
        if self.mode == "generation-fail" and self.generated == 3:
            raise RuntimeError("generation failure")
        if self.mode == "generation-hang" and self.generated == 3:
            time.sleep(60)
        v = spec["view"]
        grid = [[1 if v < 4 else 2 if v < 6 else 3]]
        tokens = codec.answer_ids(codec.transform(grid, v))
        if self.mode == "invalid" or (self.mode == "one-invalid-view" and v == 0):
            tokens = [codec.EOS_ID]
        return {"token_ids": tokens, "seconds": .00001, "memory": None, "termination": "eos"}


def prefix(mode):
    return [sys.executable, str(Path(__file__).resolve()), "--synthetic-worker", mode]


class FullCalibratedTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".irisx").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="full-calibrated-test-", dir=ROOT / ".irisx")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def execute(self, mode="normal", challenge=None, budget=20., context=10240, strategy="vote", outer=False):
        challenge = fixture() if challenge is None else challenge
        p = self.base / "challenge.json"
        p.write_text(json.dumps(challenge))
        fn = supervised_run if outer else controller.run
        result = fn(p, self.base / "never-read-model", self.base / "run", self.base / "output",
                    budget_seconds=budget, context_cap=context, strategy=strategy, fallback="copy-input", _test_worker_prefix=prefix(mode))
        return result, files.load_json(self.base / "run/analysis.json")[0]

    def execute_hung_generation(self):
        # Killing the worker must retain auditable unknown cost. The real 2s
        # clock need not also fit export/fsync into its 0.25s closure reserve.
        # An expired closure is a failure, never a completed-run substitute.
        root = self.base / "run"
        failure = None
        try:
            result, _ = self.execute("generation-hang", budget=2.)
        except TimeoutError as exc:
            self.assertEqual(str(exc), "original whole clock expired during closure; no completed-run claim")
            failure = files.load_json(root / "deadline_failure.json")[0]
            self.assertGreaterEqual(failure["budget"]["elapsed_seconds"], 2.)
            self.assertEqual(failure["budget"]["remaining_seconds"], 0.)
            with self.assertRaises((OSError, ValueError)):
                controller.verify(root, self.base / "output")
        else:
            self.assertTrue(result["whole_budget_met"])
            controller.verify(root, self.base / "output")
        dispatch = files.load_json(root / "dispatch.json")[0]
        exited = files.load_json(root / "controller_exit.json")[0]
        self.assertEqual(dispatch["budget_seconds"], 2.)
        self.assertEqual(exited["stop_reason"], "global-work-deadline")
        self.assertTrue(exited["worker_exited"])
        self.assertIn(exited["returncode"], (-signal.SIGTERM, -signal.SIGKILL))
        self.assertTrue(exited["cleanup"]["complete"])
        self.assertEqual(exited["cleanup"]["remaining_owned_members"], {})
        controller.validate_budget(exited["budget"], dispatch)
        if failure is not None:
            controller.validate_budget(failure["budget"], dispatch)
        records = {p.name: files.load_json(p)[0] for p in (root / "worker/receipts").glob("*.json")}
        analysis, _ = core.reconstruct(files.load_json(root / "plan.json")[0], records,
            freeze=files.load_json(root / "worker/calibration_freeze.json")[0],
            timing_bounds=(dispatch["start_monotonic"], dispatch["work_end_monotonic"],
                           dispatch["start_monotonic"] + exited["budget"]["elapsed_seconds"]))
        self.assertEqual(analysis["counts"]["generation"]["started"], 3)
        self.assertEqual(analysis["counts"]["generation"]["returned"], 2)
        self.assertEqual(analysis["fixed_query_denominator"], 3)
        self.assertFalse(analysis["scientific_complete"])
        return analysis

    def test_dynamic_plan_preserves_full_inventory(self):
        for n in (1, 2, 120):
            challenge = fixture(n)
            plan = core.make_plan(challenge, "a" * 64)
            core.validate_plan(plan, challenge, "a" * 64)
            info = core.prepare(plan)
            self.assertEqual((info["task_count"], info["query_count"], info["loo_calls"], info["generation_calls"]), (n, n+1, 16*n, 8*(n+1)))
            cases = core.generation_cases(plan)
            self.assertEqual([s["view"] for s, _ in cases[:n+1]], [0] * (n+1))
            self.assertEqual([s["query_index"] for s, _ in cases[:n+1]], list(range(n+1)))
            self.assertTrue(all(s["support_indices"] == [0, 1] for s, _ in cases))
            self.assertEqual(info["calibration_probe_calls"], 0)
            self.assertFalse(info["measured_fit"])

    def test_config_validation_and_unmodified_legacy_limits(self):
        from tools.public_sft141_solver import core as old
        self.assertEqual(old.CONTEXT_CAP, 8192)
        self.assertEqual(calibration.CONTEXT_CAP, 8192)
        for budget in (0, -1, float("nan"), float("inf"), 39601, True):
            with self.assertRaises(ValueError): core.config(budget_seconds=budget)
        for cap in (True, 0, 262145, float("inf")):
            with self.assertRaises(ValueError): core.config(context_cap=cap)
        core.config(context_cap=10240, budget_seconds=39600)
        with self.assertRaises(ValueError): old.SharedDeadline(time.monotonic(), 14400)

    def test_gold_and_plan_mutations_rejected(self):
        dirty = fixture()
        dirty[next(iter(dirty))]["test"][0]["output"] = [[0]]
        with self.assertRaises(ValueError): core.make_plan(dirty, "a" * 64)
        plan = core.make_plan(fixture(), "a" * 64)
        for change in (lambda p: p["parents"][0]["test"][0].update(test_index=True),
                       lambda p: p.update(gold={}), lambda p: p["scheduler"].update(retry=True)):
            modified = deepcopy(plan); change(modified)
            with self.assertRaises(ValueError): core.validate_plan(modified)

    def test_loo_spec_full_eos_and_weight_math(self):
        plan = core.make_plan(fixture(), "a" * 64)
        for spec, prompt, answer in core.loo_cases(plan):
            self.assertEqual(spec["conditioned_support_indices"], [1-spec["held_support_index"]])
            self.assertEqual(spec["input_tokens"], len(prompt)+len(answer)-1)
            self.assertEqual(answer[-1], codec.EOS_ID)
            self.assertFalse(spec["loss_mask"]["prompt_targets_included"])
        uniform = calibration.weights_from_means([0]*8)
        self.assertEqual(uniform["weights"], [1/8]*8)
        self.assertEqual(calibration.weights_from_means([0]+[10000]*7)["weights"], [1/8]*8)

    @requires_linux("real process supervision")
    def test_complete_pipeline_shared_pool_three_rankers(self):
        result, analysis = self.execute()
        self.assertTrue(result["whole_budget_met"])
        self.assertTrue(analysis["protocol_complete"])
        self.assertEqual(analysis["fixed_query_denominator"], 3)
        self.assertEqual(analysis["counts"]["loo"]["returned"], 32)
        self.assertEqual(analysis["counts"]["generation"]["returned"], 24)
        self.assertEqual(analysis["counts"]["nll"]["returned"], 72)
        for row in analysis["queries"]:
            self.assertEqual(row["vote"], [[[1]], [[2]]])
            self.assertEqual(row["demo_weighted"][0], [[3]])
            self.assertEqual(row["rescored"][0], [[3]])
            self.assertEqual([c["count"] for c in row["candidates"]], [4, 2, 2])
        controller.verify(self.base / "run", self.base / "output")
        self.assertFalse(analysis["generation_protocol_complete"])

    @requires_linux("real process supervision")
    def test_single_demo_no_empty_loo_or_adaptation(self):
        challenge = fixture(1)
        challenge[next(iter(challenge))]["train"] = challenge[next(iter(challenge))]["train"][:1]
        _, analysis = self.execute(challenge=challenge)
        self.assertEqual(analysis["counts"]["loo"]["started"], 0)
        self.assertTrue(analysis["calibration_complete"])
        for row in analysis["queries"]:
            self.assertFalse(row["weighted_adaptation_applied"])
            self.assertEqual(row["demo_weighted"], row["vote"])

    @requires_linux("real process supervision")
    def test_overflow_rejects_whole_panel_before_load(self):
        _, analysis = self.execute(context=10)
        self.assertFalse(analysis["protocol_complete"])
        self.assertEqual(analysis["counts"]["loo"]["started"], 0)
        self.assertEqual(analysis["fixed_query_denominator"], 3)
        self.assertFalse((self.base / "run/worker/load_start.json").exists())
        submission = files.load_json(self.base / "output/submission.json")[0]
        self.assertEqual(sum(map(len, submission.values())), 3)

    @requires_linux("real process supervision")
    def test_loo_failure_blocks_every_query_generation(self):
        _, analysis = self.execute("loo-fail")
        self.assertEqual(analysis["counts"]["loo"]["failed"], 1)
        self.assertTrue(analysis["counts"]["loo"]["unknown_cost"])
        self.assertEqual(analysis["counts"]["generation"]["started"], 0)
        self.assertFalse((self.base / "run/worker/calibration_freeze.json").exists())

    @requires_linux("real process supervision")
    def test_generation_failure_keeps_full_denominator_and_no_nll(self):
        _, analysis = self.execute("generation-fail")
        self.assertTrue(analysis["calibration_complete"])
        self.assertEqual(analysis["counts"]["generation"]["failed"], 1)
        self.assertEqual(analysis["counts"]["nll"]["started"], 0)
        self.assertEqual(len(analysis["queries"]), 3)
        self.assertTrue(all(not q["weighted_adaptation_applied"] for q in analysis["queries"]))

    @requires_linux("real process supervision")
    def test_nll_failure_never_selects_partial_common8_scores(self):
        _, analysis = self.execute("nll-fail")
        self.assertTrue(analysis["generation_complete"])
        self.assertFalse(analysis["nll_complete"])
        self.assertEqual(analysis["counts"]["nll"]["failed"], 1)
        self.assertTrue(all(not q["rescored"] for q in analysis["queries"]))
        self.assertTrue(all(q["demo_weighted"] for q in analysis["queries"]))

    @requires_linux("real process supervision")
    def test_hung_generation_killed_and_unknown_cost_retained(self):
        analysis = self.execute_hung_generation()
        self.assertEqual(analysis["counts"]["generation"]["unknown"], 1)
        self.assertTrue(analysis["counts"]["generation"]["unknown_cost"])

    @requires_linux("real process deadline and late closure")
    def test_hung_generation_late_closure_cannot_claim_completion(self):
        original = core.publish
        delayed = []
        def late(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if Path(path).name == "controller_exit.json":
                delayed.append(True)
                dispatch = files.load_json(Path(path).parent / "dispatch.json")[0]
                time.sleep(max(0., dispatch["end_monotonic"] - time.monotonic()) + .05)
            return result
        with patch.object(core, "publish", side_effect=late):
            analysis = self.execute_hung_generation()
        self.assertEqual(delayed, [True])
        self.assertTrue((self.base / "run/deadline_failure.json").exists())
        self.assertFalse((self.base / "run/completion.json").exists())
        self.assertEqual(analysis["counts"]["generation"]["unknown"], 1)

    @requires_linux("real process supervision")
    def test_mutation_blocks_candidates(self):
        _, analysis = self.execute("mutate")
        self.assertEqual(analysis["model_state_guard"], "changed")
        self.assertFalse(analysis["protocol_complete"])
        self.assertTrue(all(not q["demo_weighted"] for q in analysis["queries"]))

    @requires_linux("real process supervision")
    def test_invalid_answers_retained_without_repair(self):
        _, analysis = self.execute("invalid")
        self.assertTrue(analysis["generation_complete"])
        self.assertEqual(analysis["counts"]["nll"]["started"], 0)
        self.assertFalse(analysis["candidate_coverage_complete"])
        self.assertTrue(analysis["all_planned_calls_returned"])
        self.assertTrue(all(not q["candidates"] for q in analysis["queries"]))
        self.assertTrue(all(v["status"] == "invalid" for q in analysis["queries"] for v in q["views"]))

    @requires_linux("real process supervision")
    def test_invalid_but_returned_view_does_not_change_protocol(self):
        _, analysis = self.execute("one-invalid-view")
        self.assertTrue(analysis["protocol_complete"])
        self.assertTrue(analysis["all_planned_calls_returned"])
        self.assertTrue(analysis["candidate_coverage_complete"])
        self.assertFalse(analysis["all_generated_answers_valid"])
        self.assertEqual(analysis["counts"]["nll"]["returned"], 72)
        self.assertTrue(all(q["views"][0]["status"] == "invalid" for q in analysis["queries"]))
        self.assertTrue(all(q["candidates"][0]["count"] == 3 for q in analysis["queries"]))

    @requires_linux("real process supervision")
    def test_descendants_cleanup_and_unrelated_child_survives(self):
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            _, analysis = self.execute("escaped-descendant")
            self.assertIsNone(unrelated.poll())
            receipt = files.load_json(self.base / "run/controller_exit.json")[0]
            self.assertTrue(receipt["cleanup"]["complete"])
            self.assertGreaterEqual(len(receipt["cleanup"]["observed_pids"]), 2)
        finally:
            unrelated.terminate(); unrelated.wait(timeout=5)

    @requires_linux("independent hard outer watchdog")
    def test_outer_supervisor_and_original_clock_readback(self):
        _, analysis = self.execute(outer=True)
        controller.verify(self.base / "run", self.base / "output")
        dispatch = files.load_json(self.base / "run/dispatch.json")[0]
        outer = files.load_json(self.base / "run/outer_completion.json")[0]
        self.assertEqual(outer["original_start_monotonic"], dispatch["start_monotonic"])
        self.assertTrue(outer["readback_verified"])

    @requires_linux("independent hard outer watchdog")
    def test_outer_watchdog_kills_stuck_inner_controller(self):
        p = self.base / "challenge.json"; p.write_text(json.dumps(fixture()))
        with self.assertRaises(TimeoutError):
            supervised_run(p, self.base, self.base / "run", self.base / "output", budget_seconds=.4,
                           _test_controller_prefix=[sys.executable, "-c", "import time;time.sleep(60)"])
        self.assertFalse((self.base / "run/outer_completion.json").exists())

    @requires_linux("real process supervision")
    def test_sealed_raw_tamper_and_no_resume(self):
        self.execute()
        raw = self.base / "run/worker/receipts/00000000-end.json"
        value = files.load_json(raw)[0]; value["raw"]["nll"] += 1
        raw.write_bytes(wire.canonical(value))
        with self.assertRaises(ValueError): controller.verify(self.base / "run", self.base / "output")
        with self.assertRaises(FileExistsError):
            controller.run(self.base / "challenge.json", self.base, self.base / "run", self.base / "other",
                           _test_worker_prefix=prefix("normal"))

    @requires_linux("real process supervision")
    def test_evaluator_boundary_and_full_denominator(self):
        self.execute("generation-fail")
        from tools.public_full_calibrated_solver.evaluation import evaluate
        gold = self.base / "gold.json"
        gold.write_text(json.dumps({p: [[[1]]] * len(t["test"]) for p, t in fixture().items()}))
        result = evaluate(self.base / "run", self.base / "output", gold)
        self.assertEqual(result["same_pool_scores"]["vote"]["denominator"], 3)
        self.assertFalse(result["protocol_complete"])
        # A bad export must fail before the evaluator ever tries to read gold.
        (self.base / "output/submission.json").write_text("{}")
        with patch("tools.public_full_calibrated_solver.evaluation.files.load_json", wraps=files.load_json) as read:
            with self.assertRaises(ValueError): evaluate(self.base / "run", self.base / "output", self.base / "nonexistent-gold")
            self.assertFalse(any(str(c.args[0]).endswith("nonexistent-gold") for c in read.call_args_list))

    @requires_linux("separate owned evaluator within original clock")
    def test_integrated_evaluator_and_earlier_original_clock(self):
        challenge = fixture()
        p = self.base / "challenge.json"; p.write_text(json.dumps(challenge))
        gold = self.base / "gold.json"
        gold.write_text(json.dumps({k: [[[1]]] * len(v["test"]) for k, v in challenge.items()}))
        original_start, original_epoch = time.monotonic() - 1, time.time() - 1
        supervised_run(p, self.base / "never-read-model", self.base / "run", self.base / "output",
            budget_seconds=20., _test_worker_prefix=prefix("normal"), evaluation_gold_path=gold,
            original_start_monotonic=original_start, original_start_epoch=original_epoch)
        analysis = controller.verify(self.base / "run", self.base / "output")
        receipt = files.load_json(self.base / "run/evaluation.json")[0]
        dispatch = files.load_json(self.base / "run/dispatch.json")[0]
        completion = files.load_json(self.base / "run/completion.json")[0]
        self.assertNotIn(str(gold), json.dumps(dispatch))
        self.assertEqual(dispatch["start_monotonic"], original_start)
        self.assertEqual(receipt["original_start_monotonic"], original_start)
        self.assertEqual(receipt["report"]["same_pool_scores"]["vote"]["denominator"], 3)
        self.assertEqual(dispatch["configuration"]["strategy"], "vote")
        self.assertTrue(receipt["cleanup"]["complete"])
        self.assertIsNotNone(completion["evaluation_sha256"])
        self.assertGreater(completion["budget"]["elapsed_seconds"], 1.)
        self.assertTrue(analysis["protocol_complete"])

    @requires_linux("real process supervision")
    def test_per_query_unknown_cost_and_status(self):
        analysis = self.execute_hung_generation()
        row = analysis["queries"][2]
        self.assertEqual(row["views"][0]["status"], "unknown-interrupted")
        self.assertTrue(row["physical_cost"]["generation"]["unknown_cost"])
        self.assertIsNone(row["physical_cost"]["generation"]["total_generated_tokens"])
        self.assertEqual(len(row["views"]), 8)

    def test_task_macro_differs_from_micro_and_paired_counts(self):
        from tools.public_full_calibrated_solver.evaluation import comparison_metrics
        challenge = {"a": {"test": [{}, {}, {}]}, "b": {"test": [{}]}}
        gold = {"a": [[[1]], [[1]], [[1]]], "b": [[[1]]]}
        vote = {("a", 0): [[[1]]], ("a", 1): [[[1]]], ("a", 2): [[[1]]], ("b", 0): [[[0]]]}
        weighted = {**vote, ("a", 2): [[[0]]], ("b", 0): [[[1]]]}
        scores, rows, paired = comparison_metrics(challenge, gold,
            {"vote": vote, "rescored": vote, "demo_weighted": weighted}, [])
        self.assertEqual(scores["vote"]["query_micro_pass_at_2"], .75)
        self.assertEqual(scores["vote"]["equal_task_macro_pass_at_2"], .5)
        self.assertAlmostEqual(scores["demo_weighted"]["equal_task_macro_pass_at_2"], 5/6)
        self.assertEqual(paired["demo_weighted"]["pass_at_2"], {"wins": 1, "losses": 1, "ties": 2})
        self.assertEqual(paired["demo_weighted"]["first_selection_changes"], 2)
        self.assertEqual(paired["demo_weighted"]["second_selection_changes"], 0)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["strategies"]["vote"]["missing_second"] for r in rows))

    def test_exact_tensor_causal_eos_loss(self):
        try: import torch
        except ImportError: self.skipTest("optional CPU torch unavailable")
        from tools.public_sft141_diagnostic.model_worker import full_answer_nll
        logits = torch.zeros((1, 8, 16), dtype=torch.float64)
        answer = codec.answer_ids([[1]])
        loss = full_answer_nll(logits, 3, answer)
        self.assertAlmostEqual(loss, len(answer) * math.log(16), places=5)
        logits[:, :2, :] = 123.  # prompt targets do not enter the loss.
        logits[:, 3+len(answer)-1:, :] = -123.  # padding does not enter.
        self.assertEqual(loss, full_answer_nll(logits, 3, answer))
        logits[0, 3-1+len(answer)-1, codec.EOS_ID] = 5.
        self.assertLess(full_answer_nll(logits, 3, answer), loss)

    @requires_linux("CPU tensor worker subprocess")
    def test_tensor_end_to_end(self):
        try: import torch
        except ImportError: self.skipTest("optional CPU torch unavailable")
        _, analysis = self.execute("tensor", budget=30.)
        self.assertTrue(analysis["protocol_complete"])
        self.assertEqual(analysis["counts"]["nll"]["returned"], 72)
        self.assertFalse(analysis["scientific_complete"])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--synthetic-worker":
        mode = sys.argv[2]
        raise SystemExit(worker.main(sys.argv[3:], factory=lambda plan, deadline: FixtureBackend(plan, deadline, mode)))
    unittest.main()

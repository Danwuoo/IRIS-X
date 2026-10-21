"""Fresh public-only mechanics and CPU tensors, not 2B/GPU success evidence."""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.public_sft141_diagnostic import contract
from tools.public_sft141_diagnostic.model_worker import Deadline
from tools.public_demo_calibration import core, runtime
from tools.public_demo_calibration.__main__ import main, read_frozen


def plan_fixture(supports=2):
    train = [{"input": [[0, 1]], "output": [[1, 0]]},
             {"input": [[2], [3]], "output": [[3], [2]]},
             {"input": [[4, 5, 6]], "output": [[6, 5, 4]]}][:supports]
    return {"schema": "iris-public-sft141-plan-v1", "provenance": {}, "protocol": {},
        "parents": [{"task_id": f"parent{i:02d}", "train": copy.deepcopy(train),
            "test": [{"input": [[i % 10]], "query_id": f"parent{i:02d}:0", "test_index": 0}],
            "selection": {}} for i in range(12)]}


def fixtures(plan=None, means=None, grids=None):
    plan = plan or plan_fixture()
    means = means or [1.] * 8
    rows = [core.complete_row(spec, means[spec["view"]] * spec["answer_tokens"], .01, i)
            for i, (spec, _, _) in enumerate(core.cases(plan))]
    calibration = core.calibration_bundle(plan, rows, completed_event=len(rows))
    grids = grids or ([[[1]]] * 4 + [[[2]]] * 3 + [[[3]]])
    pool = core.pool_bundle(plan, calibration, [core.pool_row(spec,
        contract.answer_ids(contract.transform(grids[spec["view"]], spec["view"])), .1, len(rows) + 1 + i)
        for i, spec in enumerate(core.generation_specs(plan))])
    return plan, calibration, pool


class Clock:
    value = 0.
    def __call__(self):
        return self.value


class Backend:
    max_context = 8192
    def __init__(self, clock):
        self.clock, self.calls, self.fail_at = clock, [], None
    def score(self, prompt, answer, deadline):
        self.calls.append((prompt, answer))
        self.clock.value += .01
        if len(self.calls) == self.fail_at:
            raise RuntimeError("bounded synthetic failure")
        return {"nll": len(answer) * 1.2, "seconds": .01,
            "input_tokens": len(prompt) + len(answer) - 1,
            "answer_tokens": len(answer), "batch_size": 1, "use_cache": False}


class PlanAndReceiptTests(unittest.TestCase):
    def test_all_other_supports_original_order_and_full_eos_mask(self):
        plan = plan_fixture(3)
        pairs = core.cases(plan)
        self.assertEqual(len(pairs), 12 * 3 * 8)
        for spec, prompt, answer in pairs:
            held, view = spec["held_support_index"], spec["view"]
            train = plan["parents"][0]["train"]
            indices = [i for i in range(3) if i != held]
            self.assertEqual(spec["conditioned_support_indices"], indices)
            self.assertEqual(prompt, contract.prompt_ids([train[i] for i in indices], train[held]["input"], view))
            self.assertEqual(answer, contract.answer_ids(contract.transform(train[held]["output"], view)))
            self.assertEqual(spec["model_input_sha256"], core.digest(prompt + answer[:-1]))
            self.assertEqual(spec["loss_mask"]["logit_start_inclusive"], len(prompt) - 1)
            self.assertEqual(spec["loss_mask"]["logit_end_exclusive"], len(prompt) + len(answer) - 1)
            self.assertFalse(spec["loss_mask"]["held_support_pair_in_conditioning"])

    def test_test_output_and_label_metadata_are_rejected_not_dropped(self):
        for mutation in ("test", "metadata", "top", "support"):
            p = plan_fixture()
            if mutation == "test": p["parents"][0]["test"][0]["output"] = [[9]]
            if mutation == "metadata": p["provenance"]["gold"] = [[9]]
            if mutation == "top": p["answers"] = []
            if mutation == "support": p["parents"][0]["train"][0]["extra"] = 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                core.prepare(p)

    def test_label_metadata_aliases_and_capitalization_rejected(self):
        for field in ("Gold", "targets", "expected_output", "Test-Labels", "ground_truth"):
            p = plan_fixture()
            p["parents"][0]["selection"]["nested"] = [{field: [[1]]}]
            with self.subTest(field=field), self.assertRaises(ValueError): core.prepare(p)

    def test_changed_support_output_or_binding_is_rejected(self):
        p, c, pool = fixtures()
        for mutate in ("output", "mask", "held", "order", "duplicate"):
            c2 = copy.deepcopy(c)
            if mutate == "output": c2["rows"][0]["spec"]["answer_sha256"] = "0" * 64
            if mutate == "mask": c2["rows"][0]["spec"]["loss_mask"]["prompt_targets_included"] = True
            if mutate == "held": c2["rows"][0]["spec"]["held_support_index"] = 1
            if mutate == "order": c2["rows"][0]["spec"]["conditioned_support_indices"] = [0]
            if mutate == "duplicate": c2["rows"].append(c2["rows"][0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                core.calibrate(p, c2)
        p["parents"][0]["train"][0]["output"] = [[5]]
        with self.assertRaises(ValueError): core.rank(p, c, pool)

    def test_single_demo_falls_back_and_never_forwards(self):
        p, c, pool = fixtures(plan_fixture(1))
        self.assertEqual(core.cases(p), [])
        r = core.rank(p, c, pool)
        self.assertTrue(all(s["status"] == "single_demo_fallback" for s in r["calibration"].values()))
        self.assertTrue(all(q["uniform_top2"] == q["weighted_top2"] and not q["adaptation_applied"] for q in r["queries"]))
        self.assertEqual(r["cost"]["calibration_completed_forward_calls"], 0)

    def test_context_admission_checks_every_full_prompt_and_every_loo(self):
        p = plan_fixture()
        schedule = core.prepare(p)
        self.assertTrue(schedule["context_admitted"])
        self.assertEqual(len(schedule["generation_cases"]), 96)
        self.assertEqual(schedule["candidate_rescore_forward_upper_bound"], 12 * 64)
        denied = core.prepare(p, max_context=25)
        self.assertFalse(denied["context_admitted"])
        self.assertTrue(any("case_id" in row for row in denied["context_failures"]))
        self.assertTrue(any("query_id" in row for row in denied["context_failures"]))
        self.assertIsNone(schedule["gpu_seconds"])
        self.assertFalse(schedule["model_executed"])

    def test_true_multi_query_inputs_and_fixed_denominator_retained(self):
        p = plan_fixture()
        p["parents"][0]["test"].append({"input": [[9, 8]], "test_index": 1, "query_id": "parent00:1"})
        p, c, pool = fixtures(p)
        r = core.rank(p, c, pool)
        self.assertEqual(r["fixed_query_denominator"], 13)
        self.assertEqual([q["query_id"] for q in r["queries"][:2]], ["parent00:0", "parent00:1"])
        self.assertEqual(r["cost"]["generation_recorded_calls"], 104)

    def test_calibration_before_generation_and_same_frozen_pool(self):
        p, c, pool = fixtures()
        for mutate in ("early", "different_calibration", "partial_support", "duplicate"):
            pp = copy.deepcopy(pool)
            if mutate == "early": pp["rows"][0]["event"] = c["completed_event"]
            if mutate == "different_calibration": pp["calibration_sha256"] = "0" * 64
            if mutate == "partial_support": pp["rows"][0]["spec"]["support_indices"] = [0]
            if mutate == "duplicate": pp["rows"].append(pp["rows"][0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): core.rank(p, c, pp)

    def test_partial_calibration_cannot_promote_even_completed_tasks(self):
        p, c, pool = fixtures(means=[10.] * 4 + [2.] * 3 + [0.])
        c["rows"].pop()
        with self.assertRaises(ValueError): core.calibrate(p, c)
        c["status"] = "partial"
        pool["calibration_sha256"] = core.digest(c)
        r = core.rank(p, c, pool)
        self.assertTrue(all(not q["adaptation_applied"] and q["weighted_ranking"] == q["uniform_ranking"] for q in r["queries"]))
        self.assertFalse(r["all_eligible_calibrations_complete"])
        self.assertIsNone(r["cost"]["calibration_token_difference_vs_rescore"])

    def test_receipt_counters_nonfinite_and_unknown_fields_fail_closed(self):
        p, c, _ = fixtures()
        for key, value in (("nll_sum", float("nan")), ("seconds", -1), ("forward_calls", True),
                           ("actual_input_tokens", 1), ("test_output", [[9]])):
            bad = copy.deepcopy(c)
            bad["rows"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): core.calibrate(p, bad)


class RankingAndNumericalTests(unittest.TestCase):
    def test_uniform_anchor_exact_ties_and_canonical_inverse(self):
        g = [[1, 2, 3], [4, 5, 6]]
        p, c, pool = fixtures(grids=[g] * 8)
        r = core.rank(p, c, pool)
        for q in r["queries"]:
            self.assertEqual(q["uniform_top2"], [g])
            self.assertEqual(q["weighted_top2"], [g])
            self.assertEqual(q["candidates"][0]["count"], 8)
        p, c, pool = fixtures(grids=[[[2]]] * 4 + [[[1]]] * 4)
        q = core.rank(p, c, pool)["queries"][0]
        self.assertEqual(q["uniform_top2"], [[[1]], [[2]]])
        self.assertEqual(q["uniform_top2"], q["weighted_top2"])

    def test_valid_counterexample_weighting_hurts_top2(self):
        p, c, pool = fixtures(means=[10.] * 4 + [2.] * 3 + [0.])
        q = core.rank(p, c, pool)["queries"][0]
        self.assertEqual(q["uniform_top2"], [[[1]], [[2]]])
        self.assertEqual(q["weighted_top2"], [[[3]], [[2]]])
        # Hypothetical synthetic truth is used here only, never fed to ranking.
        correct = [[1]]
        self.assertIn(correct, q["uniform_top2"])
        self.assertNotIn(correct, q["weighted_top2"])

    def test_weights_equal_support_not_total_token_pool(self):
        p, c, _ = fixtures()
        for row in c["rows"]:
            # Two held supports have 3 or 4 target tokens depending on view.
            mean = 1. if row["spec"]["held_support_index"] == 0 else 3.
            row["nll_sum"] = mean * row["spec"]["answer_tokens"]
        s = core.calibrate(p, c)["parent00"]
        self.assertEqual(s["means"], [2.] * 8)
        self.assertEqual(s["support_view_coverage"], [8, 8])
        self.assertEqual(s["weights"], [1 / 8] * 8)

    def test_softmax_stability_shift_invariance_ess_and_underflow(self):
        means = [1., 2., 3., 4., 5., 6., 7., 8.]
        a = core.weights_from_means(means)
        b = core.weights_from_means([m + 1e10 for m in means])
        self.assertEqual(a["weights"], b["weights"])
        self.assertAlmostEqual(math.fsum(a["weights"]), 1.)
        self.assertTrue(1 <= a["effective_view_count"] <= 8)
        self.assertTrue(all(w > 0 for w in a["weights"]))
        huge = core.weights_from_means([1e308] * 8)
        self.assertEqual(huge["weights"], [1 / 8] * 8)
        underflow = core.weights_from_means([0.] + [1e4] * 7)
        self.assertEqual(underflow["underflow_views"], 7)
        self.assertEqual(underflow["weights"], [1 / 8] * 8)
        for bad in ([1.] * 7, [math.inf] * 8, [-1.] * 8):
            with self.assertRaises(ValueError): core.weights_from_means(bad)

    def test_invalid_views_not_repaired_renormalized_or_silently_removed(self):
        p, c, pool = fixtures()
        pool["rows"][0]["token_ids"] = [1]  # No EOS.
        q = core.rank(p, c, pool)["queries"][0]
        self.assertEqual(q["invalid_views"], [0])
        self.assertAlmostEqual(q["invalid_view_weight_not_redistributed"], 1 / 8)
        self.assertAlmostEqual(q["valid_view_weight"], 7 / 8)
        pool["rows"].pop(1)
        q = core.rank(p, c, pool)["queries"][0]
        self.assertFalse(q["pool_complete"])
        self.assertFalse(q["adaptation_applied"])
        self.assertEqual(q["weighted_top2"], q["uniform_top2"])

    def test_actual_token_cost_counterfactual_and_weighting_can_cost_more(self):
        p, c, pool = fixtures(grids=[[[1]]] * 8)
        r = core.rank(p, c, pool)
        cost = r["cost"]
        self.assertEqual(cost["calibration_completed_forward_calls"], 192)
        self.assertEqual(cost["calibration_completed_input_tokens"], sum(r["spec"]["input_tokens"] for r in c["rows"]))
        self.assertEqual(cost["same_pool_original_rescore_forward_calls_counterfactual"], 96)
        self.assertGreater(cost["calibration_token_difference_vs_rescore"], 0)
        self.assertIsNone(cost["gpu_time_saving"])
        self.assertEqual(cost["uniform_vote_extra_forward_calls"], 0)
        self.assertFalse(r["scientific_effectiveness_established"])


class RuntimeAndCLITests(unittest.TestCase):
    def test_sequential_collect_saves_receipts_without_training(self):
        p = plan_fixture()
        clock, temp = Clock(), tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        backend = Backend(clock)
        c = runtime.collect(p, backend, Path(temp.name) / "fresh", Deadline(600, clock))
        self.assertEqual(len(backend.calls), 192)
        self.assertEqual(c["status"], "complete")
        self.assertEqual(len(list((Path(temp.name) / "fresh" / "receipts").glob("*.json"))), 192)
        self.assertTrue(all(s["adaptation_eligible"] for s in core.calibrate(p, c).values()))
        with self.assertRaises(FileExistsError):
            runtime.collect(p, backend, Path(temp.name) / "fresh", Deadline(600, clock))

    def test_context_time_and_failed_forward_never_promote(self):
        for failure in ("context", "expired", "forward", "late_last"):
            clock, temp = Clock(), tempfile.TemporaryDirectory()
            self.addCleanup(temp.cleanup)
            backend = Backend(clock)
            deadline = Deadline(600, clock)
            if failure == "context": backend.max_context = 25
            if failure == "expired": clock.value = deadline.work_end
            if failure == "forward": backend.fail_at = 3
            if failure == "late_last":
                original = backend.score
                def score(*args):
                    result = original(*args)
                    if len(backend.calls) == 192: clock.value = deadline.work_end + 1
                    return result
                backend.score = score
            c = runtime.collect(plan_fixture(), backend, Path(temp.name) / "fresh", deadline)
            self.assertEqual(c["status"], "partial")
            self.assertTrue(all(not s["adaptation_eligible"] for s in core.calibrate(plan_fixture(), c).values()))
            if failure == "context": self.assertEqual(backend.calls, [])
            if failure == "forward": self.assertIsNone(c["rows"][-1]["actual_input_tokens"])

    def test_real_model_path_requires_verified_public_files(self):
        with tempfile.TemporaryDirectory() as td, self.assertRaises(ValueError):
            runtime.collect(plan_fixture(), Backend(Clock()), Path(td) / "no-run", Deadline(600), execution_kind="public_model")

    def test_controller_timeout_preserves_partial_raw_receipt_and_kills_only_leaf(self):
        from tools.public_demo_calibration import execution
        p = plan_fixture()
        owned = []
        class FakeLeaf:
            def __init__(self, command, **kwargs):
                self.returncode, self.killed, self.waits = None, False, 0
                owned.append(self)
                root = Path(command[command.index("--output") + 1])
                (root / "receipts").mkdir(parents=True)
                spec = core.cases(p)[0][0]
                (root / "receipts" / "loo-00000.json").write_text(json.dumps(core.complete_row(spec, 1., .1, 0)))
            def wait(self, timeout):
                self.waits += 1
                if self.waits == 1:
                    raise subprocess.TimeoutExpired("owned-leaf", timeout)
                self.returncode = -9
                return self.returncode
            def kill(self):
                self.killed = True
            def poll(self):
                return self.returncode
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.json"
            path.write_text(json.dumps(p))
            output = Path(td) / "run"
            with patch.object(execution.subprocess, "Popen", FakeLeaf), patch.object(execution, "PUBLIC_PLAN_SHA256", core.digest(p)):
                rc = execution.run(p, path, hashlib.sha256(path.read_bytes()).hexdigest(), "unused-model", output, 600)
            self.assertEqual(rc, 2)
            self.assertEqual(len(owned), 1)
            self.assertTrue(owned[0].killed)
            bundle = json.loads((output / "calibration.json").read_text())
            self.assertEqual(bundle["status"], "partial")
            self.assertEqual(len(bundle["rows"]), 1)
            self.assertTrue(json.loads((output / "closure.json").read_text())["worker_timed_out"])
            self.assertTrue(all(not s["adaptation_eligible"] for s in core.calibrate(p, bundle).values()))

    def test_real_controller_rejects_changed_support_or_query_before_model_load(self):
        from tools.public_demo_calibration import execution
        import time
        original = plan_fixture()
        for changed in ("support", "query"):
            p = copy.deepcopy(original)
            if changed == "support": p["parents"][0]["train"][0]["output"] = [[9]]
            else: p["parents"][0]["test"][0]["input"] = [[9]]
            with tempfile.TemporaryDirectory() as td, patch.object(execution, "PUBLIC_PLAN_SHA256", core.digest(original)), patch.object(execution, "TransformersBackend") as model:
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    execution.worker(p, "unused-model", Path(td) / "worker", 600, time.monotonic(), "test")
                with self.assertRaises(ValueError):
                    execution.run(p, "unused-plan", "0" * 64, "unused-model", Path(td) / "parent", 600)
                model.assert_not_called()
                self.assertFalse((Path(td) / "worker").exists())
                self.assertFalse((Path(td) / "parent").exists())

    @unittest.skipUnless(os.environ.get("PUBLIC_DEMO_PLAN_PATH"), "gold-free frozen public plan not supplied; actual-panel admission untested here")
    def test_actual_public_plan_admission_only_without_model_load(self):
        from tools.public_demo_calibration import execution
        path = Path(os.environ["PUBLIC_DEMO_PLAN_PATH"])
        plan = read_frozen(path, "bafeabeae62625171147645d166b524e3f008fdbf5e44164c0ed8c41498e9c1c")
        with patch.object(execution, "TransformersBackend") as model:
            self.assertEqual(execution.admit_public_plan(plan), execution.PUBLIC_PLAN_SHA256)
            result = core.prepare(plan)
            self.assertEqual((result["task_count"], result["query_count"], result["calibration_forward_calls"]), (12, 15, 256))
            self.assertEqual(result["calibration_input_tokens"], 479832)
            self.assertTrue(result["context_admitted"])
            model.assert_not_called()

    def test_aggregate_omission_preserves_raw_cost_and_cannot_promote(self):
        from tools.public_demo_calibration.execution import reconcile_receipts
        p = plan_fixture()
        spec = core.cases(p)[0][0]
        raw = [core.complete_row(spec, 1., .1, 0)]
        omitted = core.calibration_bundle(p, [], kind="public_model", session_id="owned", status="partial")
        recovered, consistent = reconcile_receipts(p, "owned", raw, omitted)
        self.assertFalse(consistent)
        self.assertEqual(recovered["rows"], raw)
        summary = core.calibrate(p, recovered)["parent00"]
        self.assertEqual(summary["completed_input_tokens"], spec["input_tokens"])
        self.assertFalse(summary["adaptation_eligible"])
        with self.assertRaises(ValueError): reconcile_receipts(p, "different-owner", raw, omitted)

    def test_worker_missing_public_model_fails_before_backend_load(self):
        from tools.public_demo_calibration import execution
        import time
        with tempfile.TemporaryDirectory() as td, patch.object(execution, "TransformersBackend") as model, patch.object(execution, "PUBLIC_PLAN_SHA256", core.digest(plan_fixture())):
            output = Path(td) / "worker"
            rc = execution.worker(plan_fixture(), Path(td) / "absent-public-model", output, 600, time.monotonic(), "test")
            self.assertEqual(rc, 2)
            model.assert_not_called()
            bundle = json.loads((output / "calibration.json").read_text())
            self.assertEqual(bundle["status"], "partial")
            self.assertEqual(bundle["rows"], [])

    def test_frozen_cli_and_duplicate_keys_no_evaluator_import(self):
        p, c, pool = fixtures()
        with tempfile.TemporaryDirectory() as td:
            args = ["rank"]
            for name, value in (("plan", p), ("calibration", c), ("pool", pool)):
                path = Path(td) / (name + ".json")
                data = json.dumps(value).encode()
                path.write_bytes(data)
                args += ["--" + name, str(path), "--" + name + "-sha256", hashlib.sha256(data).hexdigest()]
            output = Path(td) / "rank.json"
            self.assertEqual(main(args + ["--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())["fixed_task_denominator"], 12)
            with self.assertRaises(FileExistsError): main(args + ["--output", str(output)])
            with self.assertRaises(ValueError): read_frozen(Path(td) / "plan.json", "0" * 64)
            dup = Path(td) / "duplicate.json"
            dup.write_bytes(b'{"x":1,"x":2}')
            with self.assertRaises(ValueError): read_frozen(dup, hashlib.sha256(dup.read_bytes()).hexdigest())
        script = "import sys; import tools.public_demo_calibration.__main__; assert not any(n.endswith('.evaluate') for n in sys.modules)"
        subprocess.run([sys.executable, "-c", script], check=True)


@unittest.skipUnless(importlib.util.find_spec("torch"), "real CPU Torch unavailable")
class RealTensorTests(unittest.TestCase):
    def test_causal_tensor_alignment_prompt_exclusion_eos_and_mean(self):
        import torch
        logits = torch.zeros((1, 7, 16), dtype=torch.bfloat16)
        logits[0, 0, 8] = 90  # Prompt-only positions must not enter loss.
        logits[0, 1, 9] = 90
        answer = [2, 10, 3, 15]
        for j, token in enumerate(answer): logits[0, 2 + j, token] = j + 1
        logits[0, 6, 7] = 90  # Beyond final target also excluded.
        actual = runtime.masked_token_mean_nll(logits, 3, answer)
        oracle = torch.nn.functional.cross_entropy(logits[0, 2:6].float(), torch.tensor(answer), reduction="mean").item()
        self.assertAlmostEqual(actual, oracle, places=6)
        self.assertNotAlmostEqual(actual, runtime.masked_token_mean_nll(logits, 2, answer), places=4)
        with self.assertRaises(ValueError): runtime.masked_token_mean_nll(logits, 3, answer[:-1])

    def test_stable_weights_match_real_torch_softmax(self):
        import torch
        means = torch.tensor([1., 1.5, 2., 3., 5., 8., 13., 21.], dtype=torch.float64)
        oracle = torch.softmax(-(means - means.mean()), dim=0)
        actual = torch.tensor(core.weights_from_means(means.tolist())["weights"], dtype=torch.float64)
        self.assertTrue(torch.allclose(actual, oracle, rtol=1e-13, atol=1e-15))

    def test_tiny_cpu_model_forward_immutable_and_mutation_guard(self):
        import torch
        torch.manual_seed(7)
        previous_threads = torch.get_num_threads()
        self.addCleanup(lambda: torch.set_num_threads(previous_threads))
        torch.set_num_threads(1)
        class TinyBackend(Backend):
            def __init__(self, clock):
                super().__init__(clock)
                self.model = torch.nn.Sequential(torch.nn.Embedding(16, 8), torch.nn.Linear(8, 16)).eval()
            def score(self, prompt, answer, deadline):
                result = super().score(prompt, answer, deadline)
                with torch.inference_mode():
                    logits = self.model(torch.tensor([prompt + answer[:-1]]))
                    result["nll"] = runtime.masked_token_mean_nll(logits, len(prompt), answer) * len(answer)
                return result
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            backend = TinyBackend(clock)
            before = {k: v.clone() for k, v in backend.model.state_dict().items()}
            c = runtime.collect(plan_fixture(), backend, Path(td) / "fresh", Deadline(600, clock))
            self.assertEqual(c["status"], "complete")
            self.assertTrue(all(torch.equal(before[k], v) for k, v in backend.model.state_dict().items()))
            original = backend.score
            def mutating(*args):
                result = original(*args)
                with torch.no_grad(): next(backend.model.parameters()).add_(1)
                return result
            backend.score = mutating
            broken = runtime.collect(plan_fixture(), backend, Path(td) / "mutation", Deadline(600, clock))
            self.assertEqual(broken["status"], "partial")
            self.assertEqual(broken["rows"][0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()

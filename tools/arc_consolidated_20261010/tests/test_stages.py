"""Pure bookkeeping tests with labelled mock verifier outcomes.

These are not runtime8 mount, real ARC coverage, or Linux worker acceptance.
"""
import copy
import json
import unittest

from tools.arc_consolidated_20261010 import arc_object_ir as ir
from tools.arc_consolidated_20261010 import stages as s


IDENTITY = {"steps": [{"op": "identity"}]}
FLIP = {"steps": [{"op": "flip_horizontal"}]}
ROTATE = {"steps": [{"op": "rotate", "turns": 1}]}
THREE_STEP = {"steps": [{"op": "identity"}, {"op": "flip_horizontal"}, {"op": "identity"}]}


def task(tid="mock-task"):
    return {"task_id": tid, "demos": [{"input": [[1, 2]], "output": [[1, 2]]}]}


def mock_receipt(status="mismatch", **extra):
    return {"status": status, "all_demos_fit": status == "fit",
            "known": status in s.KNOWN_STATUSES, "gas": 7, "wall_seconds": 0.001,
            "test_evidence": "mock_outcome_not_real_verification", **extra}


def controls():
    return [{"control_id": "mock-control-" + str(i), "task": task("mock-control-" + str(i)),
             "plan": copy.deepcopy(IDENTITY), "expected_status": "fit" if i < 64 else "mismatch"}
            for i in range(128)]


class SchemaTests(unittest.TestCase):
    def test_fixed_exposed_task_order_and_fresh_copy(self):
        rows = [task(tid) for tid in s.ENGINEERING_TASK_IDS]
        actual = s.validate_tasks(rows)
        actual[0]["demos"][0]["input"][0][0] = 9
        self.assertEqual(rows[0]["demos"][0]["input"][0][0], 1)
        for malformed in (rows[::-1], rows[:-1], rows + [rows[0]]):
            with self.assertRaises(s.StageError):
                s.validate_tasks(malformed)

    def test_forbidden_truth_query_test_and_extra_fields(self):
        for key in ("test", "query", "gold", "solutions", "metadata"):
            bad = task()
            bad[key] = []
            with self.assertRaises(s.StageError):
                s.validate_task(bad)
            bad = task()
            bad["demos"][0][key] = []
            with self.assertRaises(s.StageError):
                s.validate_task(bad)

    def test_grid_boundaries_and_bool_as_int(self):
        valid = task()
        valid["demos"] = [{"input": [[9] * 30 for _ in range(30)], "output": [[0]]}]
        s.validate_task(valid)
        for grid in ([[True]], [[1.0]], [[]], [[1], [1, 2]], [[10]], [[0] * 31], [[0]] * 31):
            bad = task()
            bad["demos"][0]["input"] = grid
            with self.assertRaises(s.StageError):
                s.validate_task(bad)

    def test_duplicate_json_nonfinite_and_nesting_rejected(self):
        bad = ('[{"task_id":"x","task_id":"y","demos":[]}]',
               '[{"task_id":"x","demos":[{"input":[[NaN]],"output":[[0]]}]}]',
               '[{"task_id":"x","demos":[{"input":[[1.0]],"output":[[0]]}]}]',
               '[' * 2000 + '0' + ']' * 2000)
        for text in bad:
            with self.assertRaises(s.StageError):
                s.parse_tasks(text, None)
        self.assertEqual(s.parse_tasks(json.dumps([task()]), None), [task()])


class PoolTests(unittest.TestCase):
    def test_legal_three_step_duplicate_overflow_and_invalid_all_receipted(self):
        proposals = [IDENTITY, THREE_STEP, ROTATE, FLIP, {"steps": [{"op": "unknown"}]}]
        pool = s.build_common_pool([IDENTITY], proposals, ir.compile_plan)
        self.assertEqual([r["status"] for r in pool["receipts"]],
                         ["duplicate", "added", "added", "overflow", "out_of_domain"])
        self.assertEqual(len(pool["candidates"]), 3)
        self.assertTrue(pool["receipts"][3]["legal"])
        self.assertEqual(pool["candidates"][1]["plan"], THREE_STEP)
        self.assertEqual(pool["base_inventory_sha256"], s.digest([IDENTITY]))

    def test_precompiled_base_not_compiled_again_and_input_immutable(self):
        base = s.freeze_base_inventory([IDENTITY, FLIP], ir.compile_plan)
        original = copy.deepcopy(base)
        def no_compilation(_):
            raise AssertionError("frozen base must not be compiled again")
        self.assertEqual(s.build_common_pool(base, [], no_compilation)["pool_kind"], "base")
        self.assertEqual(base, original)

    def test_base_invalid_duplicate_or_mutated_hash_rejected(self):
        with self.assertRaises(s.StageError):
            s.freeze_base_inventory([IDENTITY, IDENTITY], ir.compile_plan)
        pool = s.freeze_base_inventory([IDENTITY], ir.compile_plan)
        pool["candidates"][0]["plan"] = FLIP
        with self.assertRaises(s.StageError):
            s.build_common_pool(pool, [], ir.compile_plan)
        with self.assertRaises(ValueError):
            s.freeze_base_inventory([{"steps": [{"op": "unknown"}]}], ir.compile_plan)
        for limit in (True, 3, -1, 1.5):
            with self.assertRaises(s.StageError):
                s.build_common_pool([IDENTITY], [], ir.compile_plan, max_additions=limit)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [task(tid) for tid in s.ENGINEERING_TASK_IDS]

    def test_failed_check_retained_and_other_tasks_continue(self):
        calls = []
        def mock_verify(t, plan):
            calls.append(t["task_id"])
            if len(calls) == 1:
                raise RuntimeError("mock verifier interrupted")
            return mock_receipt("fit" if t["task_id"] == self.tasks[1]["task_id"] else "mismatch")
        report = s.run_coverage(self.tasks, [IDENTITY], mock_verify)
        self.assertEqual(len(calls), 8)
        self.assertEqual((report["executed"], report["unknown"], report["missing"]), (7, 1, 0))
        self.assertEqual(report["tasks"][0]["conclusion"], "inconclusive")
        self.assertEqual(report["tasks"][1]["conclusion"], "demo_fit")
        self.assertEqual(report["tasks"][2]["conclusion"], "no_witness_in_inventory")
        self.assertEqual(report["task_denominator"], 8)
        self.assertFalse(report["complete"])

    def test_budget_stop_preserves_all_unvisited_denominators(self):
        for current in ("missing", "unknown"):
            calls = []
            def mock_verify(t, plan):
                calls.append((t["task_id"], plan))
                if len(calls) == 3:
                    raise s.StopCoverage("mock budget exhausted", current_status=current)
                return mock_receipt()
            report = s.run_coverage(self.tasks, [IDENTITY, FLIP], mock_verify, profile="FULL")
            self.assertEqual(len(calls), 3)
            self.assertEqual(report["planned"], 16)
            self.assertEqual(report["executed"], 2)
            self.assertEqual(report["unknown"], int(current == "unknown"))
            self.assertEqual(report["missing"], 14 - int(current == "unknown"))
            self.assertTrue(all(t["conclusion"] == "inconclusive" for t in report["tasks"][1:]))

    def test_platform_unavailable_is_missing_without_fake_witness(self):
        report = s.run_coverage(self.tasks, [IDENTITY], lambda *_: mock_receipt("unavailable"))
        self.assertEqual(report["missing"], 8)
        self.assertEqual(report["demo_fit_tasks"], 0)
        self.assertTrue(all(t["conclusion"] == "inconclusive" for t in report["tasks"]))

    def test_malformed_verifier_counters_flags_and_binding_are_unknown(self):
        invalid = [mock_receipt("fit", all_demos_fit=1), mock_receipt("fit", gas=True),
                   mock_receipt("fit", gas_charged=-1), mock_receipt("fit", wall_seconds=float("nan")),
                   mock_receipt("fit", known=False), mock_receipt("fit", candidate_id="wrong")]
        for receipt in invalid:
            report = s.run_coverage(self.tasks, [IDENTITY], lambda *_: receipt)
            self.assertEqual(report["unknown"], 8)
            self.assertEqual(report["demo_fit_tasks"], 0)

    def test_callback_mutation_cannot_change_frozen_inputs(self):
        def mock_verify(t, plan):
            t["demos"][0]["input"][0][0] = 9
            plan["steps"][0]["op"] = "bad"
            return mock_receipt()
        s.run_coverage(self.tasks, [IDENTITY], mock_verify)
        self.assertEqual(self.tasks[0]["demos"][0]["input"], [[1, 2]])
        self.assertEqual(IDENTITY["steps"][0]["op"], "identity")


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        defs = controls()
        by_id = {c["task"]["task_id"]: c["expected_status"] for c in defs}
        cls.controls = s.run_controls(defs, lambda t, p: mock_receipt(by_id[t["task_id"]]))
        cls.inventory = ir.base_inventory()
        cls.coverage = s.run_coverage([task(tid) for tid in s.ENGINEERING_TASK_IDS], cls.inventory,
                                      lambda *_: mock_receipt("fit"), profile="FULL")

    def gate(self, control=None, coverage=None, ledger=True, **kwargs):
        return s.testability_gate(control or self.controls, coverage or self.coverage, ledger,
                                  expected_base_inventory_sha256=s.digest(self.inventory),
                                  expected_candidate_count=5965, **kwargs)

    def test_full_complete_mock_gate_is_testability_only(self):
        gate = self.gate()
        self.assertTrue(gate["passed"])
        self.assertFalse(gate["n14_promotion"])
        self.assertFalse(gate["generalization_claim"])
        self.assertTrue(gate["diagnostic_archive_required"])

    def test_smoke_partial_proposals_ledger_and_missing_binding_cannot_pass(self):
        for field, value in (("profile", "SMOKE"), ("complete", False), ("missing", 1),
                             ("unknown", 1), ("pool_kind", "base_plus_roots"),
                             ("demo_fit_tasks", 1), ("task_denominator", 7), ("candidate_count", 1)):
            changed = copy.deepcopy(self.coverage)
            changed[field] = value
            self.assertFalse(self.gate(coverage=changed)["passed"], field)
        self.assertFalse(self.gate(ledger=False)["passed"])
        self.assertFalse(s.testability_gate(self.controls, self.coverage, True)["passed"])
        with self.assertRaises(s.StageError):
            self.gate(ledger=1)

    def test_control_wrong_negative_vacuity_partial_and_count(self):
        for field, value in (("all_expected", False), ("complete", False),
                             ("positive_count", 1), ("negative_count", 0), ("positive_count", True)):
            changed = copy.deepcopy(self.controls)
            changed[field] = value
            self.assertFalse(self.gate(control=changed)["passed"])
        only_positive = s.run_controls(controls()[:1], lambda *_: mock_receipt("fit"))
        self.assertFalse(only_positive["all_expected"])
        stopped = s.run_controls(controls(), lambda *_: (_ for _ in ()).throw(s.StopCoverage("mock")))
        self.assertEqual(stopped["missing"], 128)
        self.assertFalse(stopped["all_expected"])


class OrderingTests(unittest.TestCase):
    def setUp(self):
        self.pool = s.build_common_pool([IDENTITY, FLIP], [THREE_STEP], ir.compile_plan)
        self.results = {row["candidate_id"]: mock_receipt("fit" if row["plan"] == THREE_STEP else "mismatch")
                        for row in self.pool["candidates"]}

    def order(self, support=None, results=None, seed=7, budget=3):
        return s.order_diagnostics(self.pool, self.results if results is None else results,
                                   {} if support is None else support, seed, budget,
                                   production_ids_callback=ir.production_ids)

    def test_same_pool_deterministic_ties_and_hard_exclusions_retained(self):
        first = self.order()
        self.assertEqual(first, self.order())
        expected_ids = set(self.results)
        for arm in first["arms"].values():
            self.assertEqual(arm["pool_sha256"], self.pool["pool_sha256"])
            self.assertEqual(set(arm["ordering"]), expected_ids)
        hard = first["arms"]["hard_pruned"]
        self.assertEqual(hard["excluded_count"], 3)
        self.assertEqual(hard["logical_expansions"], 0)
        self.assertFalse(hard["success"])
        self.assertEqual(first["physical_verifier_calls"], 0)
        self.assertTrue(first["reexecution_required"])

    def test_first_witness_success_curve_and_full_eight_task_denominator(self):
        support = {x: 1 for row in self.pool["candidates"] for x in ir.production_ids(row["plan"])}
        result = self.order(support)
        for arm in result["arms"].values():
            witness = arm["first_witness_expansion"]
            self.assertIsNotNone(witness)
            self.assertEqual(arm["success_at_expansions"], [i >= witness for i in range(1, 4)])
        summary = s.summarize_ordering({s.ENGINEERING_TASK_IDS[0]: result})
        self.assertEqual(summary["arms"]["uniform"]["success_rate"], 1 / 8)
        self.assertEqual(summary["arms"]["uniform"]["task_denominator"], 8)
        self.assertEqual(summary["arms"]["uniform"]["inconclusive_tasks"], 7)

    def test_missing_unknown_and_foreign_results_not_inferred_failed(self):
        report = self.order(results={})
        self.assertEqual(report["arms"]["uniform"]["missing"], 3)
        self.assertFalse(report["arms"]["uniform"]["conclusive"])
        with self.assertRaises(s.StageError):
            self.order(results={"foreign": mock_receipt()})

    def test_budget_seed_support_strict_numeric_validation(self):
        for bad in (True, -1, 1.5):
            with self.assertRaises(s.StageError):
                self.order(budget=bad)
            with self.assertRaises(s.StageError):
                self.order(seed=bad)
        for bad in (True, -1, float("nan"), float("inf")):
            with self.assertRaises(s.StageError):
                self.order(support={"op:identity": bad})


if __name__ == "__main__":
    unittest.main()

"""Bounds, truth isolation and neutral interoperability on invented fixtures."""
from tests.platform_requirements import requires_linux
import copy
from dataclasses import asdict
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from irisx.arc_symbolic_dsl import (GRAMMAR, GRAMMAR_SPEC, Limits, Macro, apply_macro,
    execute_program, search, validate_task)
from irisx.arc_symbolic_runner import solve_isolated
from irisx.arc_candidates_neutral import (combine_pools, from_dsl_worker, submission_records,
    to_offline_pools, validate_pools, validate_record)
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools.arc_kaggle_submission import build_submission
from tools.arc_offline_evaluation import evaluate
from tools.evaluate_arc_symbolic import exact_union_metrics


def task():
    # Expectations are hand-written CCW rotations, not candidate output.
    return {"train": [{"input": [[1, 2], [3, 4]], "output": [[2, 4], [1, 3]]},
                       {"input": [[5, 6], [7, 8]], "output": [[6, 8], [5, 7]]}],
            "test": [{"input": [[9, 1], [2, 3]]}, {"input": [[4, 5], [6, 7]]}]}


def synthetic_record():
    raw = task()
    result = search(raw, Limits(max_depth=1, max_ast_nodes=4))
    worker = {"format": "irisx/arc-dsl-worker-v1", "status": "complete",
              "solver_id": result["solver_id"], "task_digest": result["task_digest"],
              "config_digest": result["config_digest"], "result": result,
              "limits": result["limits"],
              "parent_wall_seconds": 0.5, "peak_rss_bytes": None,
              "memory_enforcement": "synthetic-cooperative-reference", "correctness_scored": False}
    return from_dsl_worker("invented", raw, worker, "sha256:" + "0" * 64)


class SymbolicBoundTests(unittest.TestCase):
    def test_fixed_grammar_and_ast_cost(self):
        self.assertEqual(len(GRAMMAR), 1120)
        self.assertEqual(GRAMMAR_SPEC["macro_ast_nodes"], 4)
        self.assertEqual(GRAMMAR_SPEC["selector_nesting"], 1)
        self.assertEqual(len(set(GRAMMAR)), len(GRAMMAR))
        for depth in (1, 2, 3):
            Limits(max_depth=depth, max_ast_nodes=4 * depth).validate()

    def test_invalid_limits_never_start_search(self):
        for name, value in (("max_depth", 4), ("max_states", 50001), ("max_states", True),
                            ("wall_seconds", float("nan")), ("wall_seconds", 10.01),
                            ("max_ast_nodes", 3), ("cache_bytes", 0),
                            ("address_space_bytes", 1024**3 + 1), ("loo", 1)):
            values = asdict(Limits()); values[name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValidationError):
                search(task(), Limits(**values))

    def test_no_test_truth_or_extra_metadata_silently_stripped(self):
        for boundary, key in (("test", "output"), ("test", "expected_output"),
                              ("train", "correctness_scored")):
            raw = task(); raw[boundary][0][key] = [[0]]
            with self.subTest(boundary=boundary, key=key), self.assertRaises(ValidationError):
                validate_task(raw)
        raw = task(); raw["solutions"] = {}
        with self.assertRaises(ValidationError):
            search(raw)

    def test_no_python_ast_or_unbounded_parameters(self):
        for node in ({"extract": "grid", "select": "all", "transform": "eval:1+1", "render": "canvas"},
                     {"extract": "grid", "select": "all", "transform": "scale:10", "render": "crop"},
                     {"extract": "grid", "select": "all", "transform": "identity", "render": "canvas", "code": "x"}):
            with self.subTest(node=node), self.assertRaises(ValidationError):
                execute_program([[1]], [node])

    def test_cap_counts_all_attempts_including_invalid_and_dedup(self):
        first = search(task(), Limits(max_states=7, max_candidates=2))
        second = search(task(), Limits(max_states=7, max_candidates=2))
        self.assertEqual(first["states"], 7)
        self.assertEqual(first["stop_reason"], "state_limit")
        self.assertEqual(first["candidates"], second["candidates"])
        self.assertLessEqual(first["unique_states"], 8)
        self.assertTrue(all(c["ast_nodes"] <= 12 for c in first["candidates"]))

    def test_cache_cap_has_deterministic_explicit_stop(self):
        result = search(task(), Limits(cache_bytes=1))
        self.assertEqual(result["stop_reason"], "cache_limit")
        self.assertEqual(result["states"], 0)
        self.assertEqual(result["candidates"], [])
        self.assertLessEqual(result["cache_bytes"], 1)

    def test_deadline_returns_fixed_empty_pool(self):
        times = iter((0.0, 0.0, 11.0, 11.0))
        result = search(task(), now=lambda: next(times))
        self.assertEqual(result["stop_reason"], "wall_limit")
        self.assertEqual(result["candidates"], [])
        self.assertLessEqual(result["states"], 1)

    def test_all_inputs_and_caller_rng_are_unchanged(self):
        import random
        raw = task(); original = copy.deepcopy(raw)
        state = random.getstate()
        search(raw, Limits(max_depth=1, max_ast_nodes=4))
        self.assertEqual(raw, original)
        self.assertEqual(state, random.getstate())

    def test_loo_excludes_demo_and_shares_single_budget(self):
        raw = {"train": [{"input": [[c, 0], [0, 0]], "output": [[c, 0], [0, 0]]}
                         for c in (1, 2, 3)], "test": [{"input": [[4, 0], [0, 0]]}]}
        result = search(raw, Limits(max_depth=1, max_ast_nodes=4, loo=True))
        self.assertEqual(result["states"], 4 * len(GRAMMAR))
        self.assertEqual(result["loo_support"], {"kind": "leave-one-demonstration-out-top-one",
            "folds": 3, "supported": 3, "shared_task_budget": True})
        truncated = search(raw, Limits(max_depth=1, max_ast_nodes=4, max_states=1200, loo=True))
        self.assertEqual(truncated["states"], 1200)
        self.assertIsNone(truncated["loo_support"])
        self.assertIsNone(search(task(), Limits(max_depth=1, max_ast_nodes=4, loo=True))["loo_support"])

    def test_loo_cache_cap_includes_retained_main_candidates(self):
        raw = {"train": [{"input": [[0, c, 0]], "output": [[0, c, 0]]} for c in (1, 2, 3)],
               "test": [{"input": [[0, 4, 0]]}]}
        identity = Macro("grid", "all", "identity", "canvas")
        with patch("irisx.arc_symbolic_dsl.GRAMMAR", (identity,)):
            result = search(raw, Limits(max_depth=1, max_ast_nodes=4, cache_bytes=300, loo=True))
        self.assertTrue(result["candidates"])
        self.assertIsNone(result["loo_support"])
        self.assertLessEqual(result["cache_bytes"], 300)

    @unittest.skipUnless(sys.platform.startswith("linux"), "hard address-space enforcement is Linux-only")
    def test_isolated_worker_success_and_hard_wall(self):
        result = solve_isolated(task(), Limits(max_depth=1, max_ast_nodes=4))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["memory_enforcement"], "linux-RLIMIT_AS")
        self.assertLess(result["peak_rss_bytes"], 1024**3)
        for _ in range(2):
            timed = solve_isolated(task(), Limits(wall_seconds=0.000001))
            self.assertEqual(timed["status"], "wall_limit")
            self.assertIsNone(timed["result"])

    @requires_linux('Spawn-failure case requires supported POSIX resource memory enforcement before launch')
    def test_spawn_failure_is_fixed_fault_without_candidates(self):
        with patch("irisx.arc_symbolic_runner.subprocess.Popen", side_effect=OSError("injected")):
            result = solve_isolated(task())
        self.assertEqual(result["status"], "worker_fault")
        self.assertIsNone(result["result"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux bootstrap mapping precheck")
    def test_tiny_address_cap_fails_before_search_and_never_certifies_complete(self):
        result = solve_isolated(task(), Limits(max_states=1, address_space_bytes=1))
        self.assertEqual(result["status"], "memory_limit")
        self.assertIsNone(result["result"])


class NeutralCandidateTests(unittest.TestCase):
    def test_dsl_record_pool_submission_and_evaluator_interoperate(self):
        record = synthetic_record()
        self.assertTrue(record["candidates"])
        self.assertTrue(all(c["evidence"]["native_verification"] is None for c in record["candidates"]))
        challenges = {"invented": task()}
        pools = to_offline_pools(challenges, [record], "invented-run", 0.5)
        validate_pools(challenges, pools)
        submission, audit = build_submission(challenges, submission_records(challenges, pools))
        self.assertEqual(len(submission["invented"]), 2)
        # Two fixed, independent hand-written held-out rotations.
        expected = {"invented": [[[1, 3], [9, 2]], [[5, 7], [4, 6]]]}
        report = evaluate(challenges, expected, pools)
        self.assertEqual(report["development_metrics"]["metrics"]["pass_at_2"]["numerator"], 2)
        self.assertFalse(audit["correctness_scored"])

    def test_tampered_outputs_program_fit_or_native_views_fail_closed(self):
        record = synthetic_record()
        mutations = []
        bad = copy.deepcopy(record); bad["candidates"][0]["candidate_outputs"][0] = [[0]]; mutations.append(bad)
        bad = copy.deepcopy(record); bad["candidates"][0]["evidence"]["native_verification"] = {"views": 8}; mutations.append(bad)
        bad = copy.deepcopy(record); bad["candidates"][0]["record_kind"] = "nvarc-native-model"; mutations.append(bad)
        bad = copy.deepcopy(record); bad["expected_outputs"] = [[[0]]]; mutations.append(bad)
        bad = copy.deepcopy(record); bad["test_input_digests"].reverse(); mutations.append(bad)
        for bad in mutations:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_record(task(), bad)

    def test_full_multitest_identity_cannot_be_projected_implicitly(self):
        record = synthetic_record(); smaller = task(); smaller["test"].pop()
        with self.assertRaises(ValidationError):
            validate_record(smaller, record)

    def test_forged_cap_overruns_are_rejected_at_neutral_boundary(self):
        original = synthetic_record()
        mutations = []
        for field, value in (("parent_wall_seconds", 11.5), ("search_wall_seconds", 11.0),
                             ("cpu_seconds", 11.0), ("states", 50001),
                             ("serialized_cache_bytes", 256 * 1024 * 1024 + 1),
                             ("peak_rss_bytes", 1024**3 + 1)):
            bad = copy.deepcopy(original); bad["cost"][field] = value; mutations.append(bad)
        bad = copy.deepcopy(original)
        bad["limits"]["max_depth"] = 1; bad["limits"]["max_ast_nodes"] = 4
        candidate = bad["candidates"][0]
        identity = {"extract": "grid", "select": "all", "transform": "identity", "render": "canvas"}
        candidate["program"] += [identity, identity]
        candidate["program_digest"] = digest_value(candidate["program"])
        candidate["ast_nodes"] = 12
        mutations.append(bad)
        for bad in mutations:
            with self.subTest(cost=bad["cost"]), self.assertRaises(ValidationError):
                validate_record(task(), bad)

    def test_slot_policy_uses_only_branch_order_and_deduplicates(self):
        challenges = {"invented": task()}
        symbolic = to_offline_pools(challenges, [synthetic_record()], "sym", 0.5)
        baseline = copy.deepcopy(symbolic); baseline.update(run_id="base", method="synthetic-baseline")
        for record in baseline["records"]:
            for row in record["tests"]:
                row["ranked_grids"] = [[[0]], [[8]]]; row["status"] = "complete"
        combined, provenance = combine_pools(challenges, baseline, symbolic, policy="one-each", run_id="mix")
        self.assertEqual(combined["records"][0]["tests"][0]["ranked_grids"][0], [[0]])
        self.assertEqual(combined["records"][0]["tests"][0]["ranked_grids"][1], [[1, 3], [9, 2]])
        self.assertFalse(provenance["correctness_scored"])
        preserved, _ = combine_pools(challenges, baseline, symbolic, policy="baseline-first", run_id="keep")
        self.assertEqual(preserved["records"][0]["tests"][0]["ranked_grids"][:2], [[[0]], [[8]]])
        expected = {"invented": [[[1, 3], [9, 2]], [[5, 7], [4, 6]]]}
        union = exact_union_metrics(evaluate(challenges, expected, baseline), evaluate(challenges, expected, symbolic))
        self.assertEqual(union["symbolic_new_correct_tests"], 2)
        self.assertEqual(union["tasks_with_new_correct_tests"], 1)
        self.assertEqual(union["candidate_union_oracle"]["numerator"], 2)

    def test_pool_rejects_truth_even_in_nested_unrecognized_fields(self):
        challenges = {"invented": task()}
        pools = to_offline_pools(challenges, [synthetic_record()], "sym", 0.5)
        pools["records"][0]["tests"][0]["exact_match"] = True
        with self.assertRaises(ValidationError):
            validate_pools(challenges, pools)

    def test_one_each_v2_skips_a_shared_head_to_retain_distinct_symbolic_slot(self):
        challenges = {"invented": task()}
        symbolic = to_offline_pools(challenges, [synthetic_record()], "sym", 0.5)
        baseline = copy.deepcopy(symbolic); baseline.update(run_id="base", method="synthetic-baseline")
        for record in baseline["records"]:
            for row in record["tests"]:
                row["ranked_grids"] = [[[0]], [[1]]]; row["status"] = "complete"
        for record in symbolic["records"]:
            for row in record["tests"]:
                row["ranked_grids"] = [[[0]], [[2]]]; row["status"] = "complete"
        merged, provenance = combine_pools(challenges, baseline, symbolic, policy="one-each", run_id="duplicate-head")
        self.assertEqual(merged["records"][0]["tests"][0]["ranked_grids"][:2], [[[0]], [[2]]])
        self.assertEqual(merged["method"], "fixed-one-each-v2")
        self.assertEqual(provenance["policy_version"], 2)

    def test_tasks_with_new_correct_tests_does_not_claim_whole_task_gain(self):
        challenges = {"invented": task()}
        symbolic = to_offline_pools(challenges, [synthetic_record()], "sym", 0.5)
        baseline = copy.deepcopy(symbolic); baseline.update(run_id="base", method="synthetic-baseline")
        for record in baseline["records"]:
            for row in record["tests"]:
                row["ranked_grids"] = [[[0]]]; row["status"] = "partial"
        expected = {"invented": [[[1, 3], [9, 2]], [[9]]]}
        union = exact_union_metrics(evaluate(challenges, expected, baseline), evaluate(challenges, expected, symbolic))
        self.assertEqual(union["tasks_with_new_correct_tests"], 1)
        self.assertEqual(union["symbolic_newly_all_tests_correct_tasks"], 0)
        self.assertEqual(union["newly_all_tests_correct_union_tasks"], 0)
        self.assertEqual(union["tasks_all_tests_union_oracle"]["numerator"], 0)

    def test_full_union_oracle_does_not_disappear_at_merged_pool_cap(self):
        challenges = {"invented": task()}
        symbolic = to_offline_pools(challenges, [synthetic_record()], "sym", 0.5)
        baseline = copy.deepcopy(symbolic); baseline.update(run_id="base", method="invented-baseline")
        # The independent expected answer is fixed first. Baseline candidates
        # enumerate only 00..63; the answer 99 is absent by construction.
        expected = {"invented": [[[9, 9]], [[9, 9]]]}
        for record in baseline["records"]:
            for row in record["tests"]:
                row["ranked_grids"] = [[[i // 10, i % 10]] for i in range(64)]
                row["status"] = "complete"
        for record in symbolic["records"]:
            for row in record["tests"]:
                row["ranked_grids"] = [[[9, 9]]]; row["status"] = "partial"
        merged, _ = combine_pools(challenges, baseline, symbolic, policy="baseline-first", run_id="cap")
        self.assertEqual(len(merged["records"][0]["tests"][0]["ranked_grids"]), 64)
        self.assertNotIn([[9, 9]], merged["records"][0]["tests"][0]["ranked_grids"])
        union = exact_union_metrics(evaluate(challenges, expected, baseline), evaluate(challenges, expected, symbolic))
        self.assertEqual(union["candidate_union_oracle"]["numerator"], 2)
        self.assertEqual(evaluate(challenges, expected, merged)["development_metrics"]["metrics"]["candidate_oracle"]["numerator"], 0)

    def test_final_confirmation_lock_is_single_use_and_consumed_before_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            challenges = {"invented": task()}
            pools = to_offline_pools(challenges, [synthetic_record()], "confirm-synthetic", 0.5)
            expected = {"invented": [[[1, 3], [9, 2]], [[5, 7], [4, 6]]]}
            for name, value in (("challenges.json", challenges), ("pools.json", pools), ("solutions.json", expected)):
                (root / name).write_bytes(canonical_bytes(value))
            pool_sha = hashlib.sha256((root / "pools.json").read_bytes()).hexdigest()
            solutions_sha = hashlib.sha256((root / "solutions.json").read_bytes()).hexdigest()
            command = [sys.executable, "tools/evaluate_arc_symbolic.py", "--challenges", str(root / "challenges.json"),
                "--expected-challenges-digest", digest_value(challenges), "--solutions", str(root / "solutions.json"),
                "--expected-solutions-sha256", solutions_sha, "--symbolic-pools", str(root / "pools.json"),
                "--expected-symbolic-sha256", pool_sha, "--purpose", "final-public-confirmation",
                "--confirmation-lock", str(root / "global-lock.json"), "--output", str(root / "evaluate")]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            lock_bytes = (root / "global-lock.json").read_bytes()
            brief = json.loads((root / "evaluate/aggregate-brief.json").read_bytes())
            self.assertEqual(brief["purpose"], "final-public-confirmation")
            self.assertEqual(brief["policy_version"], 1)
            self.assertEqual(json.loads(lock_bytes)["policy_version"], 1)
            self.assertNotIn("rows", brief)
            # If an existing lock is reused, missing truth must never be opened.
            (root / "solutions.json").unlink()
            command[-1] = str(root / "again")
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("single-use final confirmation lock", second.stderr)
            self.assertNotIn("FileNotFoundError", second.stderr)
            self.assertEqual(lock_bytes, (root / "global-lock.json").read_bytes())

    def test_truth_free_cli_complete_output_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); challenge = root / "challenge.json"; limits = root / "limits.json"
            challenges = {"invented": task()}
            challenge.write_bytes(canonical_bytes(challenges))
            limits.write_bytes(canonical_bytes(asdict(Limits(max_depth=1, max_ast_nodes=4))))
            command = [sys.executable, "tools/run_arc_symbolic.py", "--challenges", str(challenge),
                "--expected-challenges-digest", digest_value(challenges), "--run-id", "cli-invented",
                "--limits", str(limits), "--output", str(root / "run")]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            pools = json.loads((root / "run/pools.json").read_bytes())
            validate_pools(challenges, pools)
            manifest = json.loads((root / "run/manifest.json").read_bytes())
            self.assertIn("submission.json", manifest["files"])
            self.assertFalse(manifest["correctness_scored"])
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)


if __name__ == "__main__":
    unittest.main()

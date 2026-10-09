"""Run: PYTHONPATH=<this directory>:<suite src> python -m unittest -v test_typed_ir"""
from __future__ import annotations

import ast
import collections
import copy
import hashlib
import json
import importlib.util
import marshal
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'src'
sys.path.insert(0,str(SRC))

import arc_curriculum
import arc_typed_ir
from arc_curriculum import (CurriculumError, FAMILY_SPLIT, FAMILIES, build_episode,
                            fresh_verifier, make_curriculum)
from arc_ir_coverage import reference_plan
from arc_typed_ir import (PlanError, compile_plan, digest, grammar_candidates,
                          grammar_manifest, order_candidates, parse_plan,
                          production_ids, validate_plan)

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"


class StrictPlanTests(unittest.TestCase):
    def test_round_trip(self):
        p = {"steps": [{"op": "rotate", "turns": 1}, {"op": "recolor", "source": 1, "target": 2}]}
        self.assertEqual(parse_plan(json.dumps(p)), p)
        self.assertEqual(parse_plan(json.dumps(p)), validate_plan(p))

    def test_duplicate_keys(self):
        for text in ('{"steps":[],"steps":[]}', '{"steps":[{"op":"rotate","turns":1,"turns":2}]}'):
            with self.subTest(text=text), self.assertRaises(PlanError):
                parse_plan(text)

    def test_malformed_and_host_payloads(self):
        cases = ('[]', '{}', 'null', 'true', '"identity"',
                 '{"steps":[{"op":"import"}]}',
                 '{"steps":[{"op":"identity","source":"__import__"}]}',
                 '```json\n{"steps":[{"op":"identity"}]}\n```',
                 '{"steps":[{"op":"rotate","turns":NaN}]}',
                 '{"steps":[{"op":"rotate","turns":Infinity}]}',
                 '{"steps":[{"op":"rotate","turns":1.0}]}',
                 '{"steps":[{"op":"rotate","turns":true}]}',
                 '[' * 2000 + ']' * 2000, '\ud800', ' ' * 4097)
        for text in cases:
            with self.subTest(text=text[:80]), self.assertRaises(PlanError):
                parse_plan(text)

    def test_exact_arity_bounds_and_types(self):
        invalid = [None, [], {"steps": []}, {"steps": [{"op": "identity"}] * 4},
                   {"steps": [{"op": "identity"}], "extra": 1}]
        for step in ({"op": "rotate"}, {"op": "rotate", "turns": 4},
                     {"op": "scale", "factor": 1}, {"op": "scale", "factor": True},
                     {"op": "recolor", "source": 1, "target": 1},
                     {"op": "recolor", "source": 10, "target": 0},
                     {"op": "tile", "rows": 1, "columns": 1},
                     {"op": "largest_component_crop", "background": 0, "connectivity": 6}):
            invalid.append({"steps": [step]})
        for plan in invalid:
            with self.subTest(plan=plan), self.assertRaises(PlanError):
                compile_plan(plan)

    def test_no_alias_to_input(self):
        p = {"steps": [{"op": "identity"}]}
        q = validate_plan(p)
        q["steps"][0]["op"] = "transpose"
        self.assertEqual(p["steps"][0]["op"], "identity")


class GrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates = grammar_candidates()

    def test_frozen_inventory(self):
        self.assertEqual(len(self.candidates), 1277)
        self.assertEqual(len({c["id"] for c in self.candidates}), 1277)
        self.assertEqual(sum(len(c["plan"]["steps"]) == 1 for c in self.candidates), 137)
        self.assertEqual(self.candidates, grammar_candidates())
        self.assertEqual(len({c["plan"]["steps"][0]["op"] for c in self.candidates[:10]}), 10)

    def test_bounds_and_stable_productions(self):
        for c in self.candidates:
            self.assertEqual(c["id"], "ir-" + digest(c["plan"]))
            self.assertEqual(c["production_ids"], production_ids(c["plan"]))
            self.assertEqual(c["program"], compile_plan(c["plan"]))
            self.assertLessEqual(len(c["program"].encode()), 32768)
            self.assertLessEqual(len(list(ast.walk(ast.parse(c["program"])))), 2048)

    def test_uniform_positive_support(self):
        values = order_candidates(mode="uniform")
        self.assertEqual([v["id"] for v in values], [c["id"] for c in self.candidates])
        self.assertEqual(len({v["prior_weight"] for v in values}), 1)
        self.assertAlmostEqual(sum(v["prior_weight"] for v in values), 1.0)

    def test_smoothed_positive_support(self):
        p = {"steps": [{"op": "rotate", "turns": 1}]}
        values = order_candidates([p], mode="smoothed")
        self.assertEqual(len(values), len(self.candidates))
        self.assertTrue(all(v["prior_weight"] > 0 for v in values))
        self.assertAlmostEqual(sum(v["prior_weight"] for v in values), 1.0)
        self.assertEqual(values, order_candidates([p], mode="smoothed"))

    def test_empty_smoothed_exactly_recovers_uniform(self):
        self.assertEqual(order_candidates([], mode="smoothed"), order_candidates([], mode="uniform"))
        for alpha in (1e-6, 1000):
            values = order_candidates([{"steps": [{"op": "rotate", "turns": 1}]}], mode="smoothed", alpha=alpha)
            self.assertTrue(all(v["prior_weight"] > 0 for v in values))
            self.assertAlmostEqual(sum(v["prior_weight"] for v in values), 1.0)

    def test_hard_pruning_zero_support(self):
        self.assertEqual(order_candidates([], mode="hard_pruned"), [])
        values = order_candidates([{"steps": [{"op": "rotate", "turns": 1}]}], mode="hard_pruned")
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["plan"]["steps"][0], {"op": "rotate", "turns": 1})

    def test_prior_bounds(self):
        for kwargs in ({"alpha": True}, {"alpha": 0}, {"alpha": 1e-100}, {"alpha": float("nan")}, {"mode": "unknown"}):
            with self.assertRaises(ValueError):
                order_candidates(**kwargs)
        with self.assertRaises(ValueError):
            order_candidates([{"steps": [{"op": "identity"}]}] * 5)

    def test_known_witness_receipt(self):
        path = HERE / "evidence/known-witness-coverage-reviewed.json"
        self.assertTrue(path.is_file(), "Run known_witness_coverage first")
        report = json.loads(path.read_text())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["fresh_verifier_calls"], 171)
        self.assertEqual(report["atomic_parameterizations_verified"], 137)
        self.assertEqual(report["composition_operation_classes_verified"], 34)
        self.assertEqual(report["grammar"], grammar_manifest())
        self.assertTrue(report["verifier"]["fresh_os_limited_child_per_call"])


class FreshWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verify = staticmethod(fresh_verifier(SRC / "arc_bounded_v2.py"))

    def assert_verified(self, plan, grid):
        target = reference_plan(grid, plan)
        task = {"train": [{"input": grid, "output": target}], "test": [{"input": grid}]}
        result = self.verify(compile_plan(plan), task)
        self.assertTrue(result["all_demonstrations_exact"], result)
        self.assertTrue(result["query_execution_success"], result)
        self.assertEqual(result["candidate"], target)

    def test_empty_foreground_crops(self):
        for op in ({"op": "crop_nonbackground", "background": 3},
                   {"op": "largest_component_crop", "background": 3, "connectivity": 4}):
            self.assert_verified({"steps": [op]}, [[3, 3], [3, 3]])

    def test_largest_tie_and_connectivity(self):
        grid = [[1, 0, 2, 2], [0, 1, 0, 0], [3, 3, 0, 0]]
        for connectivity in (4, 8):
            self.assert_verified({"steps": [{"op": "largest_component_crop", "background": 0,
                                            "connectivity": connectivity}]}, grid)

    def test_three_operation_interface(self):
        self.assert_verified({"steps": [{"op": "rotate", "turns": 1},
                                        {"op": "recolor", "source": 1, "target": 9},
                                        {"op": "flip_horizontal"}]}, [[1, 2, 3], [4, 5, 6]])

    def test_growth_domain_is_bounded_failure(self):
        grid = [[0] * 16]
        task = {"train": [{"input": grid, "output": grid}], "test": [{"input": grid}]}
        r = self.verify(compile_plan({"steps": [{"op": "scale", "factor": 2}]}), task)
        self.assertTrue(r["ast_admitted"])
        self.assertEqual(r["error_category"], "demo_runtime")
        self.assertIn("new_grid bounds", r["feedback"]["error"])

    def test_every_family_witness_and_mutation(self):
        for index in range(0, 512, 64):
            episode = build_episode(index)
            for mutation in (False, True):
                source = episode["mutation_program" if mutation else "witness_program"]
                result = self.verify(source, episode["task"])
                arc_curriculum._check_receipt(result, episode, mutation=mutation)

    def test_verifier_rejects_unpinned_source(self):
        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory) / "arc_program_v2.py"
            wrapper.write_text("raise RuntimeError('must never load')\n")
            with self.assertRaisesRegex(CurriculumError, "verifier source binding mismatch"):
                fresh_verifier(SRC / "arc_bounded_v2.py", wrapper)

    def test_verifier_bypasses_matching_timestamp_pyc(self):
        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory) / "arc_program_v2.py"
            wrapper.write_bytes((SRC / "arc_program_v2.py").read_bytes())
            marker = Path(directory) / "cache-was-executed"
            payload = "from pathlib import Path\nPath(%r).write_text('unsafe-cache')\n" % str(marker)
            code = compile(payload, str(wrapper), "exec")  # Trusted test fixture, never a candidate.
            stat = wrapper.stat()
            header = importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, int(stat.st_mtime), stat.st_size)
            cached = Path(importlib.util.cache_from_source(str(wrapper)))
            cached.parent.mkdir(parents=True)
            cached.write_bytes(header + marshal.dumps(code))
            verify = fresh_verifier(SRC / "arc_bounded_v2.py", wrapper)
            self.assertFalse(marker.exists())
            self.assertTrue(verify.provenance["captured_source_cache_bypass"])
            episode = build_episode(0)
            result = verify(episode["witness_program"], episode["task"])
            self.assertTrue(result["query_execution_success"], result)
            self.assertFalse(marker.exists())


class CurriculumTests(unittest.TestCase):
    def test_deterministic_family_split_and_independent_queries(self):
        counts = collections.Counter()
        for i in range(512):
            episode = build_episode(i)
            self.assertEqual(episode, build_episode(i))
            counts[episode["split"]] += 1
            self.assertEqual(len(set(episode["sample_seeds"].values())), 3)
            grids = [p["input"] for p in episode["task"]["train"]] + [episode["task"]["test"][0]["input"]]
            self.assertEqual(len({digest(g) for g in grids}), 3)
            self.assertNotIn("output", episode["task"]["test"][0])
        self.assertEqual(counts, {"train": 384, "validation": 128})

    def test_split_overlap_and_changes_fail(self):
        for split in ({}, {**FAMILY_SPLIT, "new": "train"}, {f: "train" for f in FAMILIES}):
            with self.assertRaises(CurriculumError):
                build_episode(0, family_split=split)
        changed = dict(FAMILY_SPLIT)
        changed[FAMILIES[0]], changed[FAMILIES[-1]] = "validation", "train"
        with self.assertRaises(CurriculumError):
            build_episode(0, family_split=changed)

    def test_invalid_mutation_is_not_semantic_evidence(self):
        episode = build_episode(0)
        result = {"format_admitted": True, "python_parse_admitted": True, "ast_admitted": True,
                  "demo_execution_success": False, "error_category": "demo_runtime"}
        with self.assertRaises(CurriculumError):
            arc_curriculum._check_receipt(result, episode, mutation=True)

    def test_fixed_budget_and_no_overwrite(self):
        verify = fresh_verifier(SRC / "arc_bounded_v2.py")
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory)
            with self.assertRaises(CurriculumError):
                make_curriculum(existing, verify)
            for kwargs in ({"episodes": 8}, {"max_verifications": 1025}, {"wall_seconds": 1201}):
                with self.assertRaises(CurriculumError):
                    make_curriculum(existing / "out", verify, **kwargs)
            with self.assertRaises(CurriculumError):
                make_curriculum(existing / "out", verify, wall_seconds=0.000001)
            self.assertFalse((existing / "out").exists())

    def test_frozen_full_export(self):
        directory = HERE / "evidence/curriculum-512-reviewed"
        if not (directory / 'manifest.json').exists():
            temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
            directory=Path(temporary.name)/'curriculum'
            make_curriculum(directory,fresh_verifier(SRC/'arc_bounded_v2.py'))
        manifest = json.loads((directory / "manifest.json").read_text())
        payload = (directory / "episodes.jsonl").read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest["payload_sha256"])
        self.assertEqual(manifest["grammar"], grammar_manifest())
        self.assertEqual(manifest["accounting"]["fresh_verifier_calls"], 1024)
        self.assertEqual(manifest["accounting"]["unknown_usage_calls"], 0)
        ledger_bytes = (directory / "verification-ledger.jsonl").read_bytes()
        self.assertEqual(hashlib.sha256(ledger_bytes).hexdigest(), manifest["accounting"]["ledger_sha256"])
        ledger = [json.loads(line) for line in ledger_bytes.splitlines()]
        self.assertEqual(len(ledger), 1024)
        self.assertEqual(sum(row["charged_program_steps"] for row in ledger), manifest["accounting"]["program_steps"])
        self.assertTrue(all(row["status"] == "validated" and row["usage_known"] for row in ledger))
        self.assertEqual(manifest["compiler_sha256"], hashlib.sha256(Path(arc_typed_ir.__file__).read_bytes()).hexdigest())
        self.assertEqual(manifest["generator_sha256"], hashlib.sha256(Path(arc_curriculum.__file__).read_bytes()).hexdigest())
        rows = [json.loads(line) for line in payload.splitlines()]
        self.assertEqual(len(rows), 512)
        self.assertEqual(collections.Counter(row["family"] for row in rows), {f: 64 for f in FAMILIES})
        for row in rows:
            self.assertEqual(row["P"]["target"], row["R"]["target"])
            self.assertTrue(row["verification"]["witness_and_identical_repair"]["query_execution_success"])
            self.assertEqual(row["verification"]["mutation"]["error_category"], "demo_mismatch")
            self.assertTrue(row["verification"]["mutation"]["demo_execution_success"])
            self.assertEqual(row["F"]["target"], row["F"]["input"]["supplied_program"])
            self.assertEqual(row["F"]["target"], row["P"]["target"])
            self.assertEqual(row["F"]["target_format"], row["P"]["target_format"])


class FailureLedgerTests(unittest.TestCase):
    @staticmethod
    def attach_provenance(verify):
        verify.provenance = {"fresh_os_limited_child_per_call": True,
                             "interpreter_sha256": "injected-test-adapter",
                             "verifier_sha256": "injected-test-adapter"}
        return verify

    def fail_export(self, verify, expected_exception=BaseException, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "output"
            with self.assertRaises(expected_exception):
                make_curriculum(destination, self.attach_provenance(verify), **kwargs)
            self.assertFalse(destination.exists())
            failures = list(Path(directory).glob(".curriculum-*/FAILED.json"))
            self.assertEqual(len(failures), 1)
            failed = json.loads(failures[0].read_text())
            ledger_bytes = (failures[0].parent / failed["ledger_file"]).read_bytes()
            self.assertEqual(hashlib.sha256(ledger_bytes).hexdigest(), failed["ledger_sha256"])
            self.assertFalse((failures[0].parent / "manifest.json").exists())
            return failed, [json.loads(line) for line in ledger_bytes.splitlines()]

    def test_failed_returned_witness_is_charged(self):
        def verify(source, task, *, timeout_seconds):
            return {"program_steps": 123, "format_admitted": False}
        failed, ledger = self.fail_export(verify, CurriculumError)
        self.assertEqual(failed["program_steps"], 123)
        self.assertEqual(failed["attempted_calls"], 1)
        self.assertEqual(failed["returned_calls"], 1)
        self.assertEqual(failed["unknown_usage_calls"], 0)
        self.assertEqual(ledger[0]["charged_program_steps"], 123)

    def test_verifier_raise_reserves_unknown_usage(self):
        def verify(source, task, *, timeout_seconds):
            raise RuntimeError("injected verifier exception")
        failed, ledger = self.fail_export(verify, RuntimeError)
        self.assertEqual(failed["program_steps"], 200000)
        self.assertEqual(failed["conservative_reserved_steps"], 200000)
        self.assertEqual(failed["attempted_calls"], 1)
        self.assertEqual(failed["returned_calls"], 0)
        self.assertEqual(failed["unknown_usage_calls"], 1)
        self.assertEqual(ledger[0]["status"], "verifier_raised")

    def test_untrusted_receipt_usage_reserves_full_cost(self):
        for value in (True, -1, 200001, None):
            def verify(source, task, *, timeout_seconds):
                return {"program_steps": value}
            failed, ledger = self.fail_export(verify, CurriculumError)
            self.assertEqual(failed["program_steps"], 200000)
            self.assertEqual(failed["returned_calls"], 1)
            self.assertEqual(failed["unknown_usage_calls"], 1)

    def test_failed_mutation_cost_preserves_prior_witness(self):
        episode = build_episode(0)
        witness = fresh_verifier(SRC / "arc_bounded_v2.py")(episode["witness_program"], episode["task"])
        count = 0
        def verify(source, task, *, timeout_seconds):
            nonlocal count
            count += 1
            return witness if count == 1 else {"program_steps": 456, "format_admitted": False}
        failed, ledger = self.fail_export(verify, CurriculumError)
        self.assertEqual(failed["program_steps"], witness["program_steps"] + 456)
        self.assertEqual(failed["attempted_calls"], 2)
        self.assertEqual(failed["returned_calls"], 2)
        self.assertEqual([row["role"] for row in ledger], ["witness_and_identical_repair", "mutation"])

    def test_late_return_is_charged_before_deadline_rejection(self):
        clock = [0.0]
        def verify(source, task, *, timeout_seconds):
            clock[0] = 4.0
            return {"program_steps": 789}
        with mock.patch.object(arc_curriculum.time, "monotonic", side_effect=lambda: clock[0]):
            failed, ledger = self.fail_export(verify, CurriculumError, wall_seconds=2)
        self.assertEqual(failed["program_steps"], 789)
        self.assertEqual(failed["returned_calls"], 1)
        self.assertEqual(failed["unknown_usage_calls"], 0)

    def test_interrupt_preserves_attempted_reservation(self):
        def verify(source, task, *, timeout_seconds):
            raise KeyboardInterrupt()
        failed, ledger = self.fail_export(verify, KeyboardInterrupt)
        self.assertEqual(failed["program_steps"], 200000)
        self.assertEqual(failed["unknown_usage_calls"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Synthetic, CPU-only subprocess and filesystem checks; no evaluator or model."""

import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.public_sft141_submission.contract import (FROZEN_SCHEMA, build_submission,
    canonical, grid_key, validate_challenge, validate_submission)
from tools.public_sft141_submission.files import decode_json, publish_bundle

ROOT = Path(__file__).resolve().parents[1]
MODULE = "tools.public_sft141_submission"


def challenge_fixture():
    return {"Z-original": {"train": [{"input": [[1]], "output": [[2, 3]]}],
                           "test": [{"input": [[3, 4]]}, {"input": [[5], [6]]}]},
            "A-original": {"train": [{"input": [[4]], "output": [[5]]}],
                           "test": [{"input": [[6]]}]}}


class SubmissionCLI(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".irisx"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="submission-test-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.challenge = challenge_fixture()
        self.challenge_path = self.base / "challenge.json"
        self.candidates_path = self.base / "candidates.json"
        self.output = self.base / "export"
        self.write(self.challenge_path, self.challenge)
        self.candidates = {"schema": FROZEN_SCHEMA,
            "challenge_sha256": self.sha(self.challenge_path), "strategy": "frozen",
            "strategy_chosen_before_gold": True,
            "queries": {"A-original": {"0": [[[9]]]},
                        "Z-original": {"1": [[[2]], [[3]]], "0": [[[8, 8]]]}}}
        self.write(self.candidates_path, self.candidates)

    def write(self, path, value):
        path.write_bytes(canonical(value))

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def command(self, command="export", *extra):
        return [sys.executable, "-m", MODULE, command, "--challenge", str(self.challenge_path),
                "--candidates", str(self.candidates_path), "--strategy", "frozen",
                "--strategy-chosen-before-gold", "--output-dir", str(self.output), *extra]

    def run_cli(self, command="export", *extra, ok=True):
        result = subprocess.run(self.command(command, *extra), cwd=ROOT, text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0 if ok else 2, result.stdout + result.stderr)
        return result

    def save_candidates(self):
        self.write(self.candidates_path, self.candidates)

    def test_real_cli_preserves_multiquery_order_ids_and_bindings(self):
        result = self.run_cli()
        submission = json.loads((self.output / "submission.json").read_text())
        closure = json.loads((self.output / "closure.json").read_text())
        self.assertEqual(set(submission), set(self.challenge))
        self.assertEqual(submission["Z-original"][0], {"attempt_1": [[8, 8]], "attempt_2": [[8, 8]]})
        self.assertEqual(submission["Z-original"][1], {"attempt_1": [[2]], "attempt_2": [[3]]})
        self.assertEqual(closure["counts"], {"tasks": 2, "queries": 3,
            "two_distinct_selected_queries": 1, "singleton_duplicated_queries": 2,
            "fallback_queries": 0, "selected_attempts": 4,
            "duplicate_padding_attempts": 2, "fallback_attempts": 0})
        self.assertTrue(closure["format_complete"])
        self.assertTrue(closure["candidate_coverage_complete"])
        self.assertFalse(closure["scientific_complete"])
        self.assertFalse(closure["accuracy_evaluated"])
        self.assertFalse(closure["official_submission_performed"])
        self.assertEqual(closure["source_hashes"]["challenge_sha256"], self.sha(self.challenge_path))
        self.assertEqual(closure["source_hashes"]["candidate_source_sha256"], self.sha(self.candidates_path))
        self.assertEqual(closure["submission_sha256"], self.sha(self.output / "submission.json"))
        self.assertNotIn("attempt_1", result.stdout)
        self.run_cli("verify")

    def test_missing_candidate_is_fail_closed_then_explicit_fallback(self):
        self.candidates["queries"]["Z-original"]["1"] = []
        self.save_candidates()
        self.run_cli(ok=False)
        self.assertFalse(self.output.exists())
        self.run_cli("export", "--fallback", "copy-input")
        output = json.loads((self.output / "submission.json").read_text())
        closure = json.loads((self.output / "closure.json").read_text())
        self.assertEqual(output["Z-original"][1], {"attempt_1": [[5], [6]], "attempt_2": [[5], [6]]})
        self.assertEqual(closure["counts"]["fallback_queries"], 1)
        self.assertEqual(closure["counts"]["fallback_attempts"], 2)
        self.assertFalse(closure["candidate_coverage_complete"])
        self.assertTrue(closure["format_complete"])
        self.run_cli("verify", "--fallback", "copy-input")

    def test_all_empty_candidates_can_only_be_format_fallback(self):
        for indexed in self.candidates["queries"].values():
            for index in indexed:
                indexed[index] = []
        self.save_candidates()
        self.run_cli(ok=False)
        self.run_cli("export", "--fallback", "copy-input")
        counts = json.loads((self.output / "closure.json").read_text())["counts"]
        self.assertEqual(counts["fallback_queries"], 3)
        self.assertEqual(counts["selected_attempts"], 0)
        self.assertEqual(counts["duplicate_padding_attempts"], 0)

    def test_missing_unknown_or_gapped_query_inventory_never_gets_repaired(self):
        original = deepcopy(self.candidates)
        mutations = [lambda q: q.pop("A-original"),
                     lambda q: q.update(extra={"0": []}),
                     lambda q: q["Z-original"].pop("0"),
                     lambda q: q["Z-original"].update({"2": []}),
                     lambda q: q["Z-original"].update({"01": []}),
                     lambda q: q["Z-original"].update({"-1": []})]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.candidates = deepcopy(original)
                mutate(self.candidates["queries"])
                self.save_candidates()
                self.run_cli("export", "--fallback", "copy-input", ok=False)
                self.assertFalse(self.output.exists())

    def test_duplicate_json_keys_rejected_at_all_levels(self):
        for raw in (b'{"x":1,"x":2}', b'{"queries":{"task":{"0":[],"0":[]}}}'):
            with self.subTest(raw=raw):
                self.candidates_path.write_bytes(raw)
                self.run_cli(ok=False)
                self.assertFalse(self.output.exists())
        for raw in (b'{"task":{"train":[],"train":[],"test":[]}}', b'{"task":{},"task":{}}'):
            self.challenge_path.write_bytes(raw)
            self.run_cli(ok=False)

    def test_duplicate_candidate_grids_not_two_pieces_of_evidence(self):
        self.candidates["queries"]["A-original"]["0"] = [[[1]], [[1]]]
        self.save_candidates()
        self.run_cli(ok=False)
        self.assertFalse(self.output.exists())

    def test_bad_grids_fail_whole_inventory_without_output(self):
        invalid = [[], [[]], [[1], [2, 3]], [[True]], [[1.0]], [[-1]], [[10]],
                   [["1"]], [[0] * 31], [[0]] * 31, None, {"gold": [[1]]}]
        for grid in invalid:
            with self.subTest(grid=grid):
                self.candidates["queries"]["A-original"]["0"] = [grid]
                self.save_candidates()
                self.run_cli(ok=False)
                self.assertFalse(self.output.exists())
        self.candidates["queries"]["A-original"]["0"] = [[[1]], [[2]], [[3]]]
        self.save_candidates()
        self.run_cli(ok=False)

    def test_max_size_and_changed_output_dimensions_are_legal(self):
        self.candidates["queries"]["A-original"]["0"] = [[[9] * 30 for _ in range(30)]]
        self.save_candidates()
        self.run_cli()
        self.run_cli("verify")

    def test_challenge_gold_and_unexpected_fields_rejected(self):
        for field in ("output", "gold", "answers", "solutions", "test_index"):
            for location in ("test", "task"):
                with self.subTest(field=field, location=location):
                    challenge = deepcopy(self.challenge)
                    target = challenge["A-original"]["test"][0] if location == "test" else challenge["A-original"]
                    target[field] = [[1]]
                    self.write(self.challenge_path, challenge)
                    self.candidates["challenge_sha256"] = self.sha(self.challenge_path)
                    self.save_candidates()
                    self.run_cli(ok=False)
                    self.assertFalse(self.output.exists())

    def test_strategy_declarations_required_and_consistent(self):
        command = self.command()
        command.remove("--strategy-chosen-before-gold")
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.run_cli("export", "--strategy", "vote", ok=False)
        self.candidates["strategy_chosen_before_gold"] = False
        self.save_candidates()
        self.run_cli(ok=False)

    def test_challenge_mutation_breaks_frozen_candidate_binding(self):
        self.challenge["A-original"]["test"][0]["input"] = [[7]]
        self.write(self.challenge_path, self.challenge)
        self.run_cli(ok=False)
        self.assertFalse(self.output.exists())

    def test_verify_detects_candidate_byte_mutation_even_if_grids_same(self):
        self.run_cli()
        self.candidates_path.write_bytes(self.candidates_path.read_bytes() + b" ")
        self.run_cli("verify", ok=False)

    def test_verify_detects_output_and_closure_mutation(self):
        self.run_cli()
        for name in ("submission.json", "closure.json"):
            with self.subTest(name=name):
                path = self.output / name
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                self.run_cli("verify", ok=False)
                path.write_bytes(original)
        self.run_cli("verify")

    def test_nonfinite_json_rejected(self):
        for bad in (b'NaN', b'Infinity', b'-Infinity', b'1e10000', b'-1e10000'):
            with self.subTest(bad=bad):
                self.candidates_path.write_bytes(b'{"x":' + bad + b'}')
                self.run_cli(ok=False)

    def test_existing_directory_and_outputs_never_overwritten(self):
        self.output.mkdir()
        self.run_cli(ok=False)
        self.assertEqual(list(self.output.iterdir()), [])
        self.output.rmdir()
        self.run_cli()
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.run_cli(ok=False)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_parent_traversal_rejected_before_output(self):
        self.run_cli("export", "--output-dir", str(self.base / "x" / ".." / "escape"), ok=False)
        self.run_cli("export", "--challenge", str(self.base / ".." / self.base.name / "challenge.json"), ok=False)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unsupported")
    def test_symlink_sources_output_and_ancestors_rejected(self):
        link = self.base / "candidate-link.json"
        link.symlink_to(self.candidates_path)
        self.run_cli("export", "--candidates", str(link), ok=False)
        linked_dir = self.base / "linked-dir"
        linked_dir.symlink_to(self.base, target_is_directory=True)
        self.run_cli("export", "--challenge", str(linked_dir / "challenge.json"), ok=False)
        self.run_cli("export", "--output-dir", str(linked_dir / "new-output"), ok=False)
        self.output.symlink_to(self.base / "absent", target_is_directory=True)
        self.run_cli(ok=False)
        self.assertFalse((self.base / "absent").exists())

    def test_concurrent_export_is_exclusive(self):
        first = subprocess.Popen(self.command(), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        second = subprocess.Popen(self.command(), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        first.communicate(timeout=15)
        second.communicate(timeout=15)
        self.assertEqual(sorted([first.returncode, second.returncode]), [0, 2])
        self.run_cli("verify")

    def test_hardlink_failure_never_publishes_partial_submission(self):
        with patch("tools.public_sft141_submission.files.os.link", side_effect=OSError("unsupported")):
            with self.assertRaises(OSError):
                publish_bundle(self.output, b"{}\n", b"{}\n")
        self.assertFalse((self.output / "submission.json").exists())
        self.assertFalse(any(self.output.iterdir()))

    def test_dynamic_inventory_not_fixed_panel_or_public120(self):
        self.challenge = {f"task-{n}": {"train": [{"input": [[0]], "output": [[1]]}],
                                      "test": [{"input": [[n % 10]]}] * (1 + n % 3)}
                          for n in range(137)}
        self.write(self.challenge_path, self.challenge)
        self.candidates["challenge_sha256"] = self.sha(self.challenge_path)
        self.candidates["queries"] = {task: {str(i): [[[1]]] for i in range(len(value["test"]))}
                                      for task, value in self.challenge.items()}
        self.save_candidates()
        result = json.loads(self.run_cli().stdout)
        self.assertEqual(result["counts"]["tasks"], 137)
        self.assertEqual(result["counts"]["queries"], 273)
        self.run_cli("verify")

    def test_ids_are_preserved_not_used_as_paths(self):
        task = self.challenge.pop("A-original")
        grids = self.candidates["queries"].pop("A-original")
        self.challenge["a/b:original"] = task
        self.candidates["queries"]["a/b:original"] = grids
        self.write(self.challenge_path, self.challenge)
        self.candidates["challenge_sha256"] = self.sha(self.challenge_path)
        self.save_candidates()
        self.run_cli()
        self.assertIn("a/b:original", json.loads((self.output / "submission.json").read_text()))
        self.assertFalse((self.base / "a").exists())

    def diagnostic(self):
        plan = {"schema": "iris-public-sft141-plan-v1", "parents": [
            {"task_id": task, "train": value["train"], "test": [
                {"input": q["input"], "test_index": i, "query_id": f"{task}:{i}"}
                for i, q in enumerate(value["test"])]}
            for task, value in self.challenge.items()]}
        rows = []
        for task, value in self.challenge.items():
            for i in range(len(value["test"])):
                candidates = [{"canonical_key": grid_key([[n]]), "grid": [[n]], "count": count,
                               "view_nll": [], "mean_nll": None, "combined_score": score}
                              for n, count, score in ((1, 2, -4), (2, 1, -2))]
                rows.append({"task_id": task, "test_index": i, "query_id": f"{task}:{i}",
                             "candidates": candidates, "vote": [[[1]], [[2]]],
                             "rescored": [[[2]], [[1]]], "vote_complete": False,
                             "rescoring_complete": False, "views": [], "status": "partial"})
        result = {"schema": "iris-public-sft141-worker-v1", "status": "complete", "queries": rows}
        self.write(self.base / "plan.json", plan)
        self.write(self.candidates_path, result)
        self.reseal()
        return result, plan

    def reseal(self):
        self.write(self.base / "seal.json", {"result_sha256": self.sha(self.candidates_path), "worker_exited": True})

    def diag_cli(self, strategy="vote", *extra, ok=True):
        return self.run_cli("export", "--source-format", "diagnostic", "--strategy", strategy,
                            "--plan", str(self.base / "plan.json"), "--seal", str(self.base / "seal.json"), *extra, ok=ok)

    def test_diagnostic_strategy_explicit_no_complete_flag_or_science_claim(self):
        self.diagnostic()
        self.diag_cli("rescored")
        submission = json.loads((self.output / "submission.json").read_text())
        self.assertEqual(submission["Z-original"][0]["attempt_1"], [[2]])
        closure = json.loads((self.output / "closure.json").read_text())
        self.assertFalse(closure["source_verification"]["complete_flags_trusted"])
        self.assertFalse(closure["source_verification"]["scientific_audit_verified"])
        self.assertFalse(closure["source_verification"]["nll_and_raw_token_audit_performed"])
        self.assertFalse(closure["scientific_complete"])
        self.assertTrue(closure["format_complete"])

    def test_diagnostic_empty_selection_complete_flag_cannot_create_candidate(self):
        result, _ = self.diagnostic()
        result["queries"][1]["rescored"] = []
        result["queries"][1]["rescoring_complete"] = True
        self.write(self.candidates_path, result)
        self.reseal()
        self.diag_cli("rescored", ok=False)
        self.assertFalse(self.output.exists())
        self.diag_cli("rescored", "--fallback", "copy-input")
        closure = json.loads((self.output / "closure.json").read_text())
        self.assertEqual(closure["counts"]["fallback_queries"], 1)
        self.assertFalse(closure["candidate_coverage_complete"])

    def test_diagnostic_seal_and_plan_mutations_rejected(self):
        result, plan = self.diagnostic()
        self.write(self.candidates_path, dict(result, status="changed"))
        self.diag_cli(ok=False)
        self.reseal()
        plan["parents"][0]["test"][0]["input"] = [[8]]
        self.write(self.base / "plan.json", plan)
        self.diag_cli(ok=False)
        self.assertFalse(self.output.exists())

    def test_diagnostic_identity_and_inventory_mutations_rejected(self):
        original, _ = self.diagnostic()
        mutations = [lambda r: r["queries"].append(deepcopy(r["queries"][0])),
            lambda r: r["queries"].pop(),
            lambda r: r["queries"][0].update(test_index=True),
            lambda r: r["queries"][0].update(query_id="wrong:0"),
            lambda r: r["queries"][0].update(task_id="unknown"),
            lambda r: r["queries"][0].update(gold=[[1]]),
            lambda r: r["queries"][0].update(extra={}),
            lambda r: r["queries"][0].update(vote=[[[9]]]),
            lambda r: r["queries"][0].update(rescored=[[[2]], [[2]]]),
            lambda r: r["queries"][0]["candidates"][0].update(canonical_key="other"),
            lambda r: r["queries"][0]["candidates"][0].update(count=True),
            lambda r: r["queries"][0]["candidates"][0].update(combined_score=None),
            lambda r: r.update(backend={"nested": {"answers": [[1]]}})]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                result = deepcopy(original)
                mutate(result)
                self.write(self.candidates_path, result)
                self.reseal()
                self.diag_cli(ok=False)
                self.assertFalse(self.output.exists())

    def test_diagnostic_does_not_read_or_require_evaluation_file(self):
        self.diagnostic()
        (self.base / "evaluation.json").write_text("not JSON and not read")
        self.diag_cli()

    def test_nested_label_aliases_rejected_in_result_and_plan_metadata(self):
        for alias in ("ground_truth", "answer", "target", "Test-Labels", "EXPECTED OUTPUT"):
            for location in ("result", "plan"):
                with self.subTest(alias=alias, location=location):
                    result, plan = self.diagnostic()
                    if location == "result":
                        result["backend"] = {"nested": {alias: [[1]]}}
                        self.write(self.candidates_path, result)
                        self.reseal()
                    else:
                        plan["provenance"] = {"nested": {alias: [[1]]}}
                        self.write(self.base / "plan.json", plan)
                    self.diag_cli(ok=False)
                    self.assertFalse(self.output.exists())

    def test_diagnostic_unexpected_top_level_result_and_seal_rejected(self):
        result, _ = self.diagnostic()
        result["unrecognized"] = "ignored?"
        self.write(self.candidates_path, result)
        self.reseal()
        self.diag_cli(ok=False)
        result.pop("unrecognized")
        self.write(self.candidates_path, result)
        self.reseal()
        seal_path = self.base / "seal.json"
        seal = json.loads(seal_path.read_text())
        seal["unrecognized"] = "ignored?"
        self.write(seal_path, seal)
        self.diag_cli(ok=False)
        self.assertFalse(self.output.exists())

    def test_diagnostic_numeric_overflow_rejected_without_traceback(self):
        result, _ = self.diagnostic()
        result["queries"][0]["candidates"][0]["combined_score"] = 10 ** 400
        self.write(self.candidates_path, result)
        self.reseal()
        response = self.diag_cli(ok=False)
        self.assertNotIn("Traceback", response.stderr)
        for literal in ("1e10000", "-1e10000"):
            result, _ = self.diagnostic()
            raw = self.candidates_path.read_text().replace('"status":"complete"', '"status":"complete","timings":{"seconds":' + literal + '}')
            self.candidates_path.write_text(raw)
            self.reseal()
            response = self.diag_cli(ok=False)
            self.assertNotIn("Traceback", response.stderr)
        self.assertFalse(self.output.exists())


class SubmissionPureContract(unittest.TestCase):
    def test_submission_schema_and_full_denominator(self):
        challenge = challenge_fixture()
        rows = {key: [[[1]]] for key in validate_challenge(challenge)}
        submission, _, _ = build_submission(challenge, rows)
        validate_submission(challenge, submission)
        for mutate in (lambda v: v.pop("A-original"),
                       lambda v: v["Z-original"].pop(),
                       lambda v: v["A-original"][0].update(extra=[[1]]),
                       lambda v: v["A-original"][0].update(attempt_1=[[False]])):
            changed = deepcopy(submission)
            mutate(changed)
            with self.assertRaises(ValueError):
                validate_submission(challenge, changed)

    def test_input_duplicate_keys_and_nonfinite_are_strict(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                decode_json(raw)

    def test_package_imports_only_stdlib_and_itself(self):
        for path in (ROOT / "tools/public_sft141_submission").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    modules = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    modules = [(node.module or "").split(".")[0]]
                else:
                    continue
                for module in modules:
                    self.assertIn(module, sys.stdlib_module_names, (path, module))


if __name__ == "__main__":
    unittest.main()

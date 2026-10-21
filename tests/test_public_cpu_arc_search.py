"""Hand-constructible inference and operational tests. No public evaluation data."""

import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.public_cpu_arc_search.search import (BASES, TEMPLATES, Deadline, Inapplicable,
    Work, complexity, fit, geometry, key, loo, predict, rank_key, solve_task)
from tools.public_cpu_arc_search.runtime import (ROOT, SOURCE_PATHS, collect, load_bound_plan,
    make_plan, run, source_manifest, verify, worker, write_new)
from tools.public_sft141_submission.contract import canonical, digest, read_frozen, validate_challenge
from tools.public_sft141_submission.files import load_json

MODULE = "tools.public_cpu_arc_search"


def geo(base="identity", parameter=None, view=0):
    return {"family": "geometry", "base": base, "parameter": parameter, "view": view}


def pair(source, target):
    return {"input": source, "output": target}


def task(train, *queries):
    return {"train": train, "test": [{"input": q} for q in queries]}


def synthetic():
    return {"Z/multi": task([pair([[1, 0], [0, 1]], [[2, 0], [0, 2]]),
                             pair([[0, 1, 1]], [[0, 2, 2]])], [[1, 0]], [[0], [1]]),
            "A-missing": task([pair([[1, 1]], [[2, 3]]), pair([[1, 1]], [[3, 2]])], [[1, 1]])}


class SearchTests(unittest.TestCase):
    def test_grammar_is_precisely_136_plus_constant(self):
        self.assertEqual(len(BASES), 17)
        self.assertEqual(len(TEMPLATES), 137)
        self.assertEqual(len({key(t) for t in TEMPLATES}), 137)
        self.assertEqual([t["parameter"] for t in TEMPLATES if t.get("base") == "crop" and t["view"] == 0], list(range(10)))

    def test_rectangular_d4_and_joint_palette(self):
        # Public view 1 is CCW. The color table is jointly learned, never guessed.
        train = [pair([[1, 2, 1], [2, 1, 2]], [[7, 8], [8, 7], [7, 8]]),
                 pair([[2, 1]], [[7], [8]])]
        p = fit(geo(view=1), train, Work())
        self.assertEqual(p["observed_mapping"], [[1, 7], [2, 8]])
        self.assertEqual(predict(p, [[1, 1, 2]], Work()), [[8], [7], [7]])
        self.assertEqual(complexity(p), 4)
        self.assertEqual(loo(geo(view=1), train, Work())["exact_count"], 2)

    def test_each_fixed_spatial_base(self):
        work = Work()
        self.assertEqual(geometry([[0, 0, 0], [0, 2, 0]], geo("crop", 0), work), [[2]])
        self.assertEqual(geometry([[1, 1, 2, 2], [1, 1, 2, 2]], geo("downsample", 2), work), [[1, 2]])
        self.assertEqual(geometry([[2] * 3] * 3, geo("downsample", 3), work), [[2]])
        self.assertEqual(geometry([[1, 2]], geo("upscale", 2), work), [[1, 1, 2, 2]] * 2)
        self.assertEqual(geometry([[1]], geo("upscale", 3), work), [[1] * 3] * 3)
        self.assertEqual(geometry([[1, 2]], geo("tile", 2), work), [[1, 2, 1, 2]] * 2)
        self.assertEqual(geometry([[1]], geo("tile", 3), work), [[1] * 3] * 3)
        for grid, template, reason in [([[0]], geo("crop", 0), "empty_crop"),
                                      ([[1, 1, 1]], geo("downsample", 2), "indivisible"),
                                      ([[1, 1], [1, 2]], geo("downsample", 2), "nonuniform"),
                                      ([[1] * 16], geo("upscale", 2), "illegal")]:
            with self.subTest(reason=reason), self.assertRaisesRegex(Inapplicable, reason):
                geometry(grid, template, work)

    def test_fit_and_predict_real_crop_downsample_upscale_tile(self):
        cases = [(geo("crop", 0), [[0, 0, 0], [0, 1, 0]], [[2]], [[0, 1, 1, 0]], [[2, 2]]),
                 (geo("downsample", 2), [[1, 1], [1, 1]], [[2]], [[1, 1, 1, 1]] * 2, [[2, 2]]),
                 (geo("upscale", 2), [[1]], [[2, 2], [2, 2]], [[1, 1]], [[2] * 4] * 2),
                 (geo("tile", 2), [[1, 0]], [[2, 0, 2, 0]] * 2, [[0, 1]], [[0, 2, 0, 2]] * 2)]
        for template, x, y, q, expected in cases:
            with self.subTest(template=template):
                p = fit(template, [pair(x, y)], Work())
                self.assertEqual(predict(p, q, Work()), expected)

    def test_nonidentity_unseen_color_rejected_identity_passes(self):
        learned = fit(geo(), [pair([[1]], [[2]])], Work())
        self.assertEqual(learned["palette_mode"], "learned")
        with self.assertRaisesRegex(Inapplicable, "unseen_color"):
            predict(learned, [[3]], Work())
        identity = fit(geo(), [pair([[1]], [[1]])], Work())
        self.assertEqual(identity["observed_mapping"], [[1, 1]])
        self.assertEqual(identity["palette_mode"], "identity")
        self.assertEqual(predict(identity, [[9, 0]], Work()), [[9, 0]])
        self.assertEqual(complexity(identity), 0)

    def test_false_support_consistent_program_is_rejected(self):
        with self.assertRaisesRegex(Inapplicable, "inconsistent_palette"):
            fit(geo(), [pair([[1, 1]], [[2, 3]])], Work())
        with self.assertRaisesRegex(Inapplicable, "inconsistent_palette"):
            fit(geo(), [pair([[1]], [[2]]), pair([[1]], [[3]])], Work())
        with self.assertRaisesRegex(Inapplicable, "shape"):
            fit(geo(), [pair([[1]], [[2, 2]])], Work())
        receipt = solve_task("impossible", synthetic()["A-missing"])
        self.assertEqual(receipt["programs"], [])
        self.assertEqual(receipt["queries"][0]["status"], "missing")
        self.assertEqual(receipt["counts"]["templates_attempted"], 137)
        self.assertEqual(sum(receipt["failure_counts"].values()), 137)

    def test_constant_shortcut_is_verified_and_ranked_by_real_loo(self):
        data = task([pair([[1]], [[9]]), pair([[2]], [[9]])], [[3]], [[4, 5]])
        receipt = solve_task("constant", data)
        best = receipt["programs"][0]
        self.assertEqual(best["spec"], {"family": "constant", "grid": [[9]]})
        self.assertEqual(best["loo"]["exact_count"], 2)
        self.assertEqual(best["complexity"], 2)
        self.assertTrue(all(q["candidates"][0]["grid"] == [[9]] for q in receipt["queries"]))
        with self.assertRaisesRegex(Inapplicable, "nonconstant"):
            fit({"family": "constant"}, [pair([[1]], [[2]]), pair([[1]], [[3]])], Work())

    def test_loo_can_be_defined_but_wrong_and_unavailable_is_not_success(self):
        train = [pair([[1]], [[1]]), pair([[2]], [[3]])]
        full = fit(geo(), train, Work())
        self.assertTrue(all(predict(full, p["input"], Work()) == p["output"] for p in train))
        reliability = loo(geo(), train, Work())
        self.assertEqual((reliability["exact_count"], reliability["defined_count"]), (0, 1))
        self.assertEqual(reliability["folds"][0]["failure"], "unseen_color")
        self.assertEqual(reliability["folds"][1]["failure"], "held_output_mismatch")
        self.assertEqual(loo(geo(), train[:1], Work()),
                         {"available": False, "exact_count": 0, "defined_count": 0, "folds": []})

    def test_crop_background_ambiguity_remains_in_program_inventory(self):
        data = task([pair([[0, 1]], [[0, 1]]), pair([[1, 0]], [[1, 0]])], [[2, 0, 1, 2]])
        receipt = solve_task("ambiguous", data)
        identity = next(p for p in receipt["programs"] if p["spec"].get("base") == "identity" and p["spec"]["view"] == 0)
        crop = next(p for p in receipt["programs"] if p["spec"].get("base") == "crop" and p["spec"]["parameter"] == 2 and p["spec"]["view"] == 0)
        self.assertEqual(identity["loo"]["exact_count"], 2)
        self.assertEqual(crop["loo"]["exact_count"], 2)
        self.assertNotEqual(predict(identity["spec"], data["test"][0]["input"], Work()),
                            predict(crop["spec"], data["test"][0]["input"], Work()))
        self.assertLess(rank_key(identity), rank_key(crop))

    def test_multiquery_shared_rank_distinct_predictions_and_replay(self):
        data = synthetic()["Z/multi"]
        original = deepcopy(data)
        receipt = solve_task("Z/multi", data)
        self.assertEqual(data, original)
        self.assertEqual([q["test_index"] for q in receipt["queries"]], [0, 1])
        self.assertEqual(receipt["programs"], sorted(receipt["programs"], key=rank_key))
        for program in receipt["programs"]:
            self.assertTrue(all(predict(program["spec"], p["input"], Work()) == p["output"] for p in data["train"]))
        for query, expected in zip(receipt["queries"], [[[2, 0]], [[0], [2]]]):
            grids = [c["grid"] for c in query["candidates"]]
            self.assertEqual(grids[0], expected)
            self.assertEqual(len(grids), len({key(g) for g in grids}))
            self.assertLessEqual(len(grids), 2)
        all_duplicate = solve_task("duplicate", task([pair([[1]], [[1]]), pair([[1]], [[1]])], [[1]]))
        self.assertEqual(len(all_duplicate["queries"][0]["candidates"]), 1)
        self.assertGreater(all_duplicate["counts"]["candidate_grid_duplicates"], 0)

    def test_support_consistency_does_not_establish_unseen_query_truth(self):
        # Genuine counterexample: transpose is a valid rule for both symmetric demos.
        data = task([pair([[1, 0], [0, 2]], [[1, 0], [0, 2]]),
                     pair([[2, 1], [1, 0]], [[2, 1], [1, 0]])], [[1, 2], [0, 1]])
        receipt = solve_task("counterexample", data)
        best = receipt["programs"][0]
        self.assertEqual(best["full_support_exact_count"], 2)
        self.assertEqual(best["loo"]["exact_count"], 2)
        prediction = receipt["queries"][0]["candidates"][0]["grid"]
        synthetic_true_transpose = [[1, 0], [2, 1]]
        self.assertNotEqual(prediction, synthetic_true_transpose)
        self.assertEqual(prediction, data["test"][0]["input"])

    def test_cooperative_deadline_never_calls_prefix_full_search(self):
        receipt = solve_task("expired", synthetic()["Z/multi"], Work(time.monotonic() - 1))
        self.assertEqual(receipt["status"], "partial")
        self.assertEqual(receipt["attempts"], [])
        self.assertTrue(all(q["candidates"] == [] and q["status"] == "not_completed" for q in receipt["queries"]))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".irisx").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="public-cpu-test-", dir=ROOT / ".irisx")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.challenge = self.base / "challenge.json"
        self.plan = self.base / "plan.json"
        self.output = self.base / "run"
        self.challenge.write_bytes(canonical(synthetic()))

    def prepare(self, seconds=20):
        plan = make_plan(self.challenge, seconds)
        write_new(self.plan, plan)
        return plan

    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-m", MODULE, *args], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_cli_full_inventory_frozen_export_and_after_exit_verification(self):
        self.cli("plan", "--challenge", str(self.challenge), "--seconds", "20", "--output-plan", str(self.plan))
        result = self.cli("run", "--plan", str(self.plan), "--output-dir", str(self.output),
                          "--started-epoch", str(time.time()))
        closure = verify(self.output)
        self.assertTrue(closure["worker_exited"])
        self.assertTrue(closure["search_complete"])
        self.assertFalse(closure["accuracy_evaluated"])
        self.assertEqual((closure["task_count"], closure["query_count"]), (2, 3))
        self.assertEqual(closure["counts"]["templates_attempted"], 274)
        self.assertEqual(closure["predicted_query_count"], 2)
        frozen, _ = load_json(self.output / "frozen_candidates.json")
        challenge, raw = load_json(self.challenge)
        rows, _ = read_frozen(frozen, challenge, digest(raw), "frozen")
        self.assertEqual(rows[("A-missing", 0)], [])
        self.assertEqual(rows[("Z/multi", 0)][0], [[2, 0]])
        self.assertEqual(rows[("Z/multi", 1)][0], [[0], [2]])
        self.cli("verify", "--output-dir", str(self.output))
        # Existing output is never reused, including a fully successful directory.
        self.cli("run", "--plan", str(self.plan), "--output-dir", str(self.output),
                 "--started-epoch", str(time.time()), expected=2)

    def test_gold_metadata_duplicate_json_rejected_before_run(self):
        for field in ("output", "answer", "metadata"):
            challenge = synthetic()
            challenge["Z/multi"]["test"][0][field] = [[2]] if field != "metadata" else {"label": 2}
            self.challenge.write_bytes(canonical(challenge))
            with self.subTest(field=field), self.assertRaises(ValueError):
                make_plan(self.challenge, 20)
        self.challenge.write_text('{"x":{},"x":{}}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            make_plan(self.challenge, 20)

    def test_challenge_mutation_breaks_plan_before_worker(self):
        self.prepare()
        value = synthetic()
        value["Z/multi"]["test"][0]["input"] = [[0]]
        self.challenge.write_bytes(canonical(value))
        self.cli("run", "--plan", str(self.plan), "--output-dir", str(self.output),
                 "--started-epoch", str(time.time()), expected=2)
        self.assertFalse(self.output.exists())

    def test_source_mutation_breaks_plan_without_mutating_repo(self):
        self.prepare()
        files, _ = source_manifest()
        files[SOURCE_PATHS[0]] = "0" * 64
        with patch("tools.public_cpu_arc_search.runtime.source_manifest", return_value=(files, digest(canonical(files)))):
            with self.assertRaisesRegex(ValueError, "binding"):
                load_bound_plan(self.plan)

    def test_sealed_candidate_mutation_is_detected(self):
        self.prepare()
        run(self.plan, self.output, time.time())
        value, _ = load_json(self.output / "frozen_candidates.json")
        value["queries"]["Z/multi"]["0"] = [[[9]]]
        (self.output / "frozen_candidates.json").write_bytes(canonical(value))
        with self.assertRaisesRegex(ValueError, "changed"):
            verify(self.output)

    def test_real_deadline_has_all_missing_queries_and_no_success(self):
        # Large synthetic inventory ensures the fixed search cannot finish this budget.
        data = {f"T{i:04d}": synthetic()["Z/multi"] for i in range(300)}
        self.challenge.write_bytes(canonical(data))
        self.prepare(seconds=0.8)
        start = time.time()
        result = self.cli("run", "--plan", str(self.plan), "--output-dir", str(self.output),
                          "--started-epoch", str(start), expected=3)
        closure = verify(self.output)
        self.assertFalse(closure["search_complete"])
        self.assertFalse(closure["sealed_for_scoring"])
        self.assertTrue(closure["worker_exited"])
        self.assertEqual((closure["task_count"], closure["query_count"]), (300, 600))
        self.assertTrue(any(t["status"] != "complete" for t in closure["tasks"]))
        self.assertLess(time.time() - start, 2.0)
        frozen, _ = load_json(self.output / "frozen_candidates.json")
        self.assertEqual(sum(len(v) for v in frozen["queries"].values()), 600)
        for row in closure["tasks"]:
            if row["status"] != "complete":
                self.assertTrue(all(v == [] for v in frozen["queries"][row["task_id"]].values()))

    def test_missing_worker_summary_cannot_retain_complete_seal(self):
        self.prepare()
        run(self.plan, self.output, time.time())
        closure, _ = load_json(self.output / "closure.json")
        del closure["files"]["worker.json"]
        (self.output / "worker.json").unlink()
        (self.output / "closure.json").write_bytes(canonical(closure))
        with self.assertRaisesRegex(ValueError, "required artifact"):
            verify(self.output)

    def test_admission_clock_tamper_is_rejected_even_with_new_file_hash(self):
        self.prepare()
        run(self.plan, self.output, time.time())
        admission, _ = load_json(self.output / "admission.json")
        admission["deadline_epoch"] += 100
        raw = canonical(admission)
        (self.output / "admission.json").write_bytes(raw)
        closure, _ = load_json(self.output / "closure.json")
        closure["files"]["admission.json"] = digest(raw)
        (self.output / "closure.json").write_bytes(canonical(closure))
        with self.assertRaisesRegex(ValueError, "deadline"):
            verify(self.output)

    def test_exact_loaded_worker_bytes_are_hash_checked(self):
        plan = self.prepare()
        changed = synthetic()
        changed["Z/multi"]["test"][0]["input"] = [[9]]
        with patch("tools.public_cpu_arc_search.runtime.load_bound_plan", return_value=(plan, canonical(plan))):
            with patch("tools.public_cpu_arc_search.runtime.load_json", return_value=(changed, canonical(changed))):
                with self.assertRaisesRegex(ValueError, "loaded challenge bytes"):
                    worker(self.plan, self.output, time.time() + 5)

    def test_noncanonical_plan_rejected_before_dispatch(self):
        plan = self.prepare()
        self.plan.write_text(json.dumps(plan, indent=2))
        with self.assertRaisesRegex(ValueError, "canonical"):
            run(self.plan, self.output, time.time())
        self.assertFalse(self.output.exists())

    def test_challenge_change_during_worker_produces_no_complete_seal(self):
        # Exercise the real owned subprocess; mutate only synthetic challenge bytes.
        self.challenge.write_bytes(canonical({f"T{i:03d}": synthetic()["Z/multi"] for i in range(80)}))
        self.prepare()
        process = subprocess.Popen([sys.executable, "-m", MODULE, "run", "--plan", str(self.plan),
            "--output-dir", str(self.output), "--started-epoch", str(time.time())], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            wait_until = time.monotonic() + 5
            while not (self.output / "task-000000.json").exists() and process.poll() is None and time.monotonic() < wait_until:
                time.sleep(0.005)
            self.assertTrue((self.output / "task-000000.json").exists())
            with self.challenge.open("ab") as stream:
                stream.write(b" ")
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 3, stdout + stderr)
            closure, _ = load_json(self.output / "closure.json")
            self.assertEqual(closure["integrity_error"], "challenge bytes changed")
            self.assertFalse(closure["sealed_for_scoring"])
            frozen, _ = load_json(self.output / "frozen_candidates.json")
            self.assertTrue(all(not grids for rows in frozen["queries"].values() for grids in rows.values()))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_original_expired_deadline_is_not_reset(self):
        self.prepare(seconds=1)
        with self.assertRaisesRegex(ValueError, "expired"):
            run(self.plan, self.output, time.time() - 2)
        self.assertFalse(self.output.exists())

    def test_linux_required_and_package_has_no_evaluator_model_private_import(self):
        self.prepare()
        with patch("tools.public_cpu_arc_search.runtime.sys.platform", "win32"):
            with self.assertRaisesRegex(ValueError, "Linux"):
                run(self.plan, self.output, time.time())
        for path in (ROOT / "tools/public_cpu_arc_search").glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(any(x in (node.module or "") for x in ("evaluat", "nvarc", "torch", "transformers")))
                elif isinstance(node, ast.Import):
                    self.assertFalse(any(any(x in name.name for x in ("evaluat", "nvarc", "torch", "transformers")) for name in node.names))


if __name__ == "__main__":
    unittest.main()

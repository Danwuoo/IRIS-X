"""CPU-only full-denominator candidate mapping and generated-dev selection."""
import copy
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.nvarc_posttrain_20261017 import controller as ctl
def public_fixture():
    result = {f"task{i:03}": {"train": [{"input": [[1]], "output": [[2]]}],
                             "test": [{"input": [[5]]}]} for i in range(120)}
    for i in range(47):
        result[f"task{i:03}"]["test"].append({"input": [[6]]})
    return result


def pools(public, grids):
    return {"challenges_digest": ctl.digest(public), "records": [
        {"task_id": key, "tests": [{"test_index": i, "input_digest": ctl.digest(q["input"]),
          "ranked_grids": copy.deepcopy(grids), "status": "complete"} for i, q in enumerate(task["test"])]}
        for key, task in public.items()]}


def model_identity(variant):
    pin = ctl.model_pin(variant)
    return {**pin, "material_identity_sha256": ctl.hashlib.sha256(ctl.canonical(pin)).hexdigest(),
            "verified_parameters": pin["parameters"], "remote_code_executed": False}


class CoordinatorContractTests(unittest.TestCase):
    def test_foreign_superior_science_result_and_its_baseline_are_not_consumed(self):
        panel = dict(panel_sha256="fixed", complete=True, queries=24, views=2, ttt_steps=0,
                     pass1=24, pass2=24, valid=24)
        result = dict(job_id="2b-H", mode="train", source_identity="FOREIGN", device_identity="device",
            workload_identity="compact-four-arm-continuation-v1", model_identity=model_identity("2b"),
            baseline=panel, dev=panel, training={"wall_seconds": 1.},
            baseline_checkpoint={"root": "baseline", "manifest_sha256": "b" * 64},
            checkpoint={"root": "posttrained", "manifest_sha256": "c" * 64})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "science-0/2b-H"
            baseline.mkdir(parents=True)
            (baseline / "baseline-evidence.json").write_text(json.dumps(dict(job_id="2b-H", source_identity="source",
                device_identity="device", workload_identity="compact-four-arm-continuation-v1",
                pre_training=True, public_labels_used=False, model_identity=model_identity("2b"),
                checkpoint=result["baseline_checkpoint"], dev=panel)))
            for status in ("invalid_result", "completed"):
                row = dict(job_id="2b-H", closure_verified=True, status=status, result=result)
                self.assertEqual(ctl.science_options([row], "2b", root, source_identity="source", device_identity="device"), [])
            row.update(status="worker_failed", result=None)
            options = ctl.science_options([row], "2b", root, source_identity="source", device_identity="device")
            self.assertEqual([o["checkpoint_id"] for o in options], ["2b-H:baseline"])
            row["status"] = "invalid_result"
            self.assertEqual(ctl.science_options([row], "2b", root, source_identity="source", device_identity="device"), [])

    def test_public_identity_rejection_overrides_existing_predictions(self):
        ready = dict(job_id="2b-S", ready=True, device={"device_identity": "device"}, base_identity=model_identity("2b"))
        row = dict(job_id="2b-S", closure_verified=True, status="invalid_result", result=None, ready_receipt=ready)
        self.assertFalse(ctl.public_record_admitted(row, source_identity="source", device_identity="device"))
        row["status"] = "deadline_during_work"
        self.assertTrue(ctl.public_record_admitted(row, source_identity="source", device_identity="device"))
        ready["device"]["device_identity"] = "FOREIGN"
        self.assertFalse(ctl.public_record_admitted(row, source_identity="source", device_identity="device"))

    def test_full_mocked_coordinator_runs_four_arms_and_two_selected_models(self):
        # Orchestration control flow only; synthetic receipts are not GPU proof.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Path(__file__).resolve().parents[1]
            input_root = root / "input"
            solver = input_root / "solver"
            solver.mkdir(parents=True)
            public = public_fixture()
            (solver / "public.json").write_text(json.dumps(public))
            start = time.time() - 1
            config = dict(source_root=str(source), output_root=str(root / "output"), run_id="synthetic",
                started_epoch=start, deadline_epoch=start + 43200, runtime_env={}, python="synthetic-python",
                input_root=str(input_root), allowed_input_roots=[str(solver)], source_identity="a" * 64,
                model_roots={"2b": "synthetic-2b", "4b": "synthetic-4b"}, training_root="synthetic-train",
                training_manifest_path="synthetic-manifest", public_path=str(solver / "public.json"))
            topology = dict(measured=True, device_count=1, device_identity="synthetic-device",
                total_bytes=96 * 1024**3, free_bytes=95 * 1024**3)
            modes = []
            def wave(jobs, **kwargs):
                modes.extend(j["mode"] for j in jobs)
                records = []
                for job in jobs:
                    path = Path(kwargs["output_root"]) / job["job_id"]
                    path.mkdir(parents=True)
                    result = {key: job[key] for key in ("job_id", "source_identity", "workload_identity", "device_identity")}
                    result.update(mode=job["mode"], model_identity=model_identity(job["variant"]), completed=True)
                    result.update(tokens=100, updates=4, peak_allocated_bytes=1024**3,
                                  peak_reserved_bytes=1024**3, cold_startup_seconds=.1)
                    if job["mode"] == "pilot":
                        result["pilot"] = dict(records=[dict(task_lifecycle_seconds=.15, inference_seconds=.1)] * 4,
                                               unamortized_setup_restore_seconds=.01)
                    if job["mode"] == "train":
                        panel = dict(panel_sha256="fixed-protocol", queries=24, views=2, ttt_steps=0,
                                     complete=True, pass1=1, pass2=1, valid=24)
                        result.update(baseline=panel, dev={**panel, "pass1": 2, "pass2": 2 if job["arm"] == "S" else 3},
                            training={"wall_seconds": 10.}, baseline_checkpoint={"root": str(path / "baseline"), "manifest_sha256": "b" * 64},
                            checkpoint={"root": str(path / "posttrained"), "manifest_sha256": "c" * 64})
                    if job["mode"] == "public":
                        body = pools(public, [[[1 if job["variant"] == "4b" else 2]]])
                        (path / "pools.json").write_text(json.dumps(body))
                    records.append(dict(job_id=job["job_id"], status="completed", result=result,
                                        closure_verified=True, closure_wall_seconds=.01))
                return dict(jobs=records, completed=True, wall_seconds=1., cold_startup_seconds=.1, active_seconds=.8)
            with patch.object(ctl.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(topology))), \
                    patch.object(ctl, "run_wave", side_effect=wave), \
                    patch.object(ctl, "measure_full_export", return_value={"wall_seconds": .1}), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = ctl.run(config)
            self.assertEqual(modes.count("probe"), 24)
            self.assertEqual(modes.count("train"), 4)
            self.assertEqual(modes.count("pilot"), 2)
            self.assertEqual(modes.count("public"), 2)
            self.assertEqual(result["concurrency"]["concurrency"], 4)
            self.assertEqual(result["selected"]["2b"]["checkpoint_id"], "2b-H:posttrained")
            self.assertEqual(result["selected"]["4b"]["checkpoint_id"], "4b-H:posttrained")
            self.assertEqual(result["public_queries"], 167)
            self.assertFalse(result["clean_generalization_claimed"])
            merged = json.loads((root / "output/pools.json").read_bytes())
            self.assertTrue(all(t["ranked_grids"] == [[[1]], [[2]]] for r in merged["records"] for t in r["tests"]))

    def test_two_specialists_are_two_total_guesses_not_four(self):
        public = public_fixture()
        result = ctl.ensemble_pools(public, {"2b": pools(public, [[[2]], [[3]]]),
                    "4b": pools(public, [[[1]], [[4]]])}, run_id="fixture")
        self.assertEqual(len(result["records"]), 120)
        self.assertEqual(sum(len(r["tests"]) for r in result["records"]), 167)
        self.assertTrue(all(t["ranked_grids"] == [[[1]], [[2]]]
                            for r in result["records"] for t in r["tests"]))

    def test_duplicate_top_one_fills_from_fixed_four_b_priority(self):
        public = public_fixture()
        result = ctl.ensemble_pools(public, {"2b": pools(public, [[[1]], [[3]]]),
                    "4b": pools(public, [[[1]], [[4]]])}, run_id="fixture")
        self.assertEqual(result["records"][0]["tests"][0]["ranked_grids"], [[[1]], [[4]]])

    def test_export_is_accepted_by_unchanged_scorer_without_metadata_recovery(self):
        from tools.arc_offline_evaluation import evaluate, validate_pools
        public = public_fixture()
        result = ctl.ensemble_pools(public, {"2b": pools(public, [[[2]], [[3]]]),
                                   "4b": pools(public, [[[1]], [[4]]])}, run_id="fixture")
        validate_pools(public, result)
        self.assertIsNone(result["parent_wall_seconds"])
        self.assertTrue(all(r["task_digest"] == ctl.digest(public[r["task_id"]])
                            and r["timings"] == {} for r in result["records"]))
        # Synthetic targets only: the actual evaluator is unchanged and no
        # external benchmark material is used by this integration regression.
        targets = {key: [[[2]]] * len(task["test"]) for key, task in public.items()}
        metrics = evaluate(public, targets, result)["development_metrics"]
        self.assertEqual(metrics["metrics"]["pass_at_2"]["numerator"], 167)
        self.assertEqual(metrics["metrics"]["pass_at_1"]["numerator"], 0)
        self.assertEqual(metrics["tests"], 167)

    def test_empty_specialists_remain_full_denominator_scorer_inputs(self):
        from tools.arc_offline_evaluation import evaluate
        public = public_fixture()
        result = ctl.ensemble_pools(public, {"2b": pools(public, []), "4b": pools(public, [])}, run_id="fixture")
        targets = {key: [[[2]]] * len(task["test"]) for key, task in public.items()}
        metric = evaluate(public, targets, result)["development_metrics"]["metrics"]["pass_at_2"]
        self.assertEqual((metric["numerator"], metric["denominator"]), (0, 167))

    def test_reject_duplicate_missing_extra_or_wrong_input_queries(self):
        public = public_fixture()
        originals = {"2b": pools(public, []), "4b": pools(public, [])}
        def duplicate(body): body["records"][0]["tests"].append(body["records"][0]["tests"][0])
        def wrong_id(body): body["records"][0]["task_id"] = "wrong"
        def wrong_input(body): body["records"][0]["tests"][0]["input_digest"] = "wrong"
        def bool_grid(body): body["records"][0]["tests"][0]["ranked_grids"] = [[[True]]]
        for mutate in (duplicate, wrong_id, wrong_input, bool_grid):
            with self.subTest(mutation=mutate.__name__):
                values = copy.deepcopy(originals)
                mutate(values["2b"])
                with self.assertRaises(ValueError): ctl.ensemble_pools(public, values, run_id="fixture")

    def test_selection_exact_generation_not_nll_and_ties_choose_lower_cost(self):
        def report(key, exact, seconds, nll):
            return dict(checkpoint_id=key, training_seconds=seconds, dev=dict(panel_sha256="fixed",
                queries=24, views=2, ttt_steps=0, complete=True, pass1=exact, pass2=exact, valid=24, nll=nll))
        reports = [report("low-nll", 2, 10., .01), report("exact", 3, 20., 10.), report("cheaper", 3, 0., 20.)]
        self.assertEqual(ctl.pick_checkpoint(reports)["checkpoint_id"], "cheaper")
        reports[0]["dev"]["complete"] = False
        with self.assertRaises(ValueError): ctl.pick_checkpoint(reports)

    def test_full_export_measurement_covers_every_query_without_scoring_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ctl.measure_full_export(public_fixture(), directory, candidate_views=2)
            files = sorted(p.name for p in Path(directory).iterdir())
            data = json.loads((Path(directory) / "synthetic-export-full.json").read_bytes())
        self.assertEqual(result["queries"], 167)
        self.assertTrue(result["synthetic_byte_load_only"])
        self.assertGreater(result["wall_seconds"], 0)
        self.assertEqual(len(data), 167)
        self.assertEqual(files, ["synthetic-export-full.json", "synthetic-export-selected.json"])


if __name__ == "__main__": unittest.main()

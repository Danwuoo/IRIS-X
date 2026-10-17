"""CPU fixtures only: no GPU feasibility, speedup or model-quality claim."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tools.nvarc_posttrain_20261017.concurrency import (
    GIB, JOB_IDS, assess_memory, choose_concurrency, deadline_admission,
    run_wave, schedule_waves,
)


IDENTITY = {"source_identity": "source-fixture", "workload_identity": "work-fixture",
            "device_identity": "device-fixture"}


def memory_fixture(peak_gib=5):
    return [{**IDENTITY, "job_id": job_id, "measured": True, "completed": True,
             "tokens": 2048, "updates": 8, "peak_allocated_bytes": peak_gib * GIB,
             "peak_reserved_bytes": (peak_gib + 1) * GIB} for job_id in JOB_IDS]


def topology_fixture(total_gib=95, free_gib=93):
    return {"measured": True, "device_count": 1, "device_identity": IDENTITY["device_identity"],
            "total_bytes": total_gib * GIB, "free_bytes": free_gib * GIB}


def benchmark(concurrency, repeat_id, wall, **changes):
    return {**IDENTITY, "concurrency": concurrency, "repeat_id": repeat_id,
            "measured": True, "completed": True, "failures": [],
            "wall_seconds": wall, "cold_startup_seconds": 5, "active_seconds": wall - 5,
            "jobs": [{"job_id": job_id, "completed": True, "tokens": 2048, "updates": 8}
                     for job_id in JOB_IDS], **changes}


def receipts(serial=100, two=70, four=50):
    return [benchmark(c, repeat, wall) for c, wall in ((1, serial), (2, two), (4, four))
            for repeat in ("a", "b")]


class AdmissionTests(unittest.TestCase):
    def test_deterministic_mixed_model_waves(self):
        self.assertEqual(schedule_waves(reversed(JOB_IDS), 2),
                         [["2b-S", "4b-S"], ["2b-H", "4b-H"]])
        jobs = [{"job_id": job_id, "seed": i} for i, job_id in enumerate(JOB_IDS)]
        self.assertIs(schedule_waves(jobs, 4)[0][0], jobs[0])
        for count in (0, 3, True, 2.0):
            with self.assertRaises(ValueError):
                schedule_waves(JOB_IDS, count)
        for jobs in (JOB_IDS[:3], [JOB_IDS[0]] * 4, [*JOB_IDS[:3], "ReArc"]):
            with self.assertRaises(ValueError):
                schedule_waves(jobs, 2)

    def test_exact_integer_memory_gate(self):
        result = assess_memory(memory_fixture(), topology_fixture(), 4)
        expected = 2 * GIB + 4 * ((6 * 6 * GIB + 4) // 5 + 2 * GIB)
        self.assertEqual(result["waves"][0]["required_bytes"], expected)
        self.assertEqual(result["budget_bytes"], 95 * GIB * 4 // 5)
        self.assertTrue(result["admitted"])
        self.assertFalse(assess_memory(memory_fixture(15), topology_fixture(), 4)["admitted"])
        self.assertTrue(assess_memory(memory_fixture(15), topology_fixture(), 2)["admitted"])
        self.assertFalse(assess_memory(memory_fixture(), topology_fixture(free_gib=2), 1)["admitted"])

    def test_estimates_incomplete_or_foreign_memory_are_not_actual(self):
        for key, value in (("measured", False), ("completed", False),
                           ("source_identity", "foreign"), ("workload_identity", "foreign"),
                           ("device_identity", "foreign"), ("tokens", True),
                           ("updates", 0), ("peak_allocated_bytes", float("nan")),
                           ("peak_reserved_bytes", 1)):
            memory = memory_fixture()
            memory[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                assess_memory(memory, topology_fixture(), 1)
        for key, value in (("measured", False), ("device_count", 2), ("device_count", True),
                           ("free_bytes", 100 * GIB), ("total_bytes", 0)):
            topology = topology_fixture()
            topology[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                assess_memory(memory_fixture(), topology, 1)

    def test_four_way_only_with_repeated_actual_improvement(self):
        result = choose_concurrency(memory_fixture(), topology_fixture(), receipts())
        self.assertTrue(result["admitted"])
        self.assertEqual(result["concurrency"], 4)
        self.assertTrue(result["comparisons"]["4_vs_2"]["admitted"])
        self.assertEqual(result["physical_cost"]["observed_wall_seconds"], 440)
        self.assertEqual(result["physical_cost"]["unknown_wall_receipts"], 0)

    def test_memory_failure_falls_back_without_quotas(self):
        result = choose_concurrency(memory_fixture(15), topology_fixture(), receipts())
        self.assertEqual(result["concurrency"], 2)
        result = choose_concurrency(memory_fixture(35), topology_fixture(), receipts())
        self.assertEqual(result["concurrency"], 1)
        result = choose_concurrency(memory_fixture(70), topology_fixture(), receipts())
        self.assertIsNone(result["concurrency"])
        self.assertFalse(result["admitted"])

    def test_full_cold_wall_not_active_time_drives_selection(self):
        data = receipts(two=101, four=102)
        for row in data:
            if row["concurrency"] != 1:
                row["cold_startup_seconds"], row["active_seconds"] = 95, row["wall_seconds"] - 95
        self.assertEqual(choose_concurrency(memory_fixture(), topology_fixture(), data)["concurrency"], 1)

    def test_small_or_inconsistent_gains_are_not_speedups(self):
        self.assertEqual(choose_concurrency(memory_fixture(), topology_fixture(),
                                            receipts(two=96, four=96))["concurrency"], 1)
        data = receipts()
        data[-1]["wall_seconds"], data[-1]["active_seconds"] = 90, 85
        self.assertEqual(choose_concurrency(memory_fixture(), topology_fixture(), data)["concurrency"], 2)
        data = receipts()
        data[3]["wall_seconds"], data[3]["active_seconds"] = 110, 105
        # Four-way still has direct repeated wins over both serial and two-way.
        self.assertEqual(choose_concurrency(memory_fixture(), topology_fixture(), data)["concurrency"], 4)

    def test_pairing_and_all_fixed_jobs_are_required(self):
        for mutate in (
                lambda rows: rows[-1].update(repeat_id="unpaired"),
                lambda rows: rows[-1]["jobs"].pop(),
                lambda rows: rows[-1]["jobs"][0].update(tokens=2047),
                lambda rows: rows[-1]["jobs"][0].update(updates=7),
                lambda rows: rows[-1]["jobs"][0].update(completed=False),
                lambda rows: rows[-1].update(source_identity="foreign"),
                lambda rows: rows[-1].update(workload_identity="foreign"),
                lambda rows: rows[-1].update(device_identity="foreign"),
                lambda rows: rows[-1].update(measured=False),
                lambda rows: rows[-1].update(failures=["oom"]),
                lambda rows: rows[-1].update(completed=False),
                lambda rows: rows.append(copy.deepcopy(rows[-1]))):
            data = receipts()
            mutate(data)
            with self.subTest(data=data[-1]):
                self.assertEqual(choose_concurrency(memory_fixture(), topology_fixture(), data)["concurrency"], 2)
        data = [benchmark(c, "a", w) for c, w in ((1, 100), (2, 70), (4, 50))]
        self.assertEqual(choose_concurrency(memory_fixture(), topology_fixture(), data)["concurrency"], 1)
        self.assertEqual(choose_concurrency(memory_fixture(), topology_fixture(), receipts()[:4])["concurrency"], 2)
        self.assertIsNone(choose_concurrency(memory_fixture(), topology_fixture(), receipts()[2:])["concurrency"])

    def test_failures_costs_remain_and_bad_costs_fail_closed(self):
        data = receipts()
        data[-1].update(completed=False, failures=["oom"])
        result = choose_concurrency(memory_fixture(), topology_fixture(), data)
        self.assertEqual(result["physical_cost"]["observed_wall_seconds"], 440)
        self.assertEqual(result["concurrency"], 2)
        for bad in (0, -1, True, float("nan"), float("inf"), "50"):
            data = receipts()
            data[-1]["wall_seconds"] = bad
            result = choose_concurrency(memory_fixture(), topology_fixture(), data)
            self.assertEqual(result["concurrency"], 2)
            self.assertEqual(result["physical_cost"]["unknown_wall_receipts"], 1)
            self.assertEqual(result["physical_cost"]["observed_wall_seconds"], 390)
        data = receipts()
        data[-1].update(cold_startup_seconds=50, active_seconds=1)
        self.assertEqual(choose_concurrency(memory_fixture(), topology_fixture(), data)["concurrency"], 2)
        with self.assertRaises(ValueError):
            choose_concurrency(memory_fixture(), topology_fixture(), receipts(), min_improvement=0.01)
        with self.assertRaises(ValueError):
            choose_concurrency(memory_fixture(), topology_fixture(), receipts(), min_repeats=1)

    def test_deadline_physics_not_minimum_hours(self):
        pilot = {**IDENTITY, "measured": True, "completed": True,
                 "ttt_tasks": 12, "inference_queries": 10, "ttt_wall_seconds": 6,
                 "inference_wall_seconds": 2, "cold_startup_seconds": 1,
                 "export_seconds": 1, "closure_seconds": 1}
        result = deadline_admission(now_epoch=1000, deadline_epoch=2000,
                                    planned_training_seconds=500, pilot=pilot)
        self.assertTrue(result["admitted"])
        self.assertAlmostEqual(result["reserve_seconds"], 482)
        self.assertEqual(result["public_tasks"], 120)
        self.assertEqual(result["public_queries"], 167)
        self.assertFalse(result["external_scoring_in_provider_reserve"])
        self.assertFalse(deadline_admission(now_epoch=1000, deadline_epoch=1500,
                                            planned_training_seconds=19, pilot=pilot)["admitted"])
        self.assertTrue(deadline_admission(now_epoch=1000, deadline_epoch=1500,
                                           planned_training_seconds=18, pilot=pilot)["admitted"])
        self.assertFalse(deadline_admission(now_epoch=2000, deadline_epoch=1500,
                                            planned_training_seconds=0, pilot=pilot)["admitted"])
        for key, value in (("measured", False), ("completed", False), ("ttt_tasks", 121),
                           ("inference_queries", 168), ("ttt_wall_seconds", 0),
                           ("inference_wall_seconds", float("nan")), ("closure_seconds", 0)):
            bad = {**pilot, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                deadline_admission(now_epoch=1000, deadline_epoch=2000,
                                   planned_training_seconds=500, pilot=bad)

    def test_import_is_cpu_only_and_has_no_execution_side_effect(self):
        code = "import sys; import tools.nvarc_posttrain_20261017.concurrency; assert 'torch' not in sys.modules"
        result = subprocess.run([sys.executable, "-B", "-c", code], check=False,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


WORKER = r'''
import argparse, json, os, pathlib, subprocess, sys, time
p = argparse.ArgumentParser(); p.add_argument('--config'); a = p.parse_args()
c = json.loads(pathlib.Path(a.config).read_text())
r = pathlib.Path(c['output_dir'])
def write(name, value):
    t = r / (name + '.tmp'); t.write_text(json.dumps(value)); t.replace(r / name)
if c.get('mode') == 'exit_before_ready':
    raise SystemExit(3)
if c.get('mode') == 'hang_load':
    time.sleep(20)
if c.get('mode') == 'slow_load':
    time.sleep(.2)
if c.get('mode') == 'foreign_ready':
    write('ready.json', {'job_id': 'foreign', 'ready': True})
else:
    write('ready.json', {'job_id': c['job_id'], 'ready': True, 'epoch': time.time()})
if c.get('mode') == 'premature_success':
    write('result.json', {'job_id': c['job_id'], 'completed': True})
    raise SystemExit(0)
while not pathlib.Path(c['release_path']).exists():
    time.sleep(.005)
release = json.loads(pathlib.Path(c['release_path']).read_text())
assert release['released'] and release['job_id'] == c['job_id']
if c.get('mode') == 'fail':
    write('result.json', {'job_id': c['job_id'], 'completed': False, 'updates': 2})
    raise SystemExit(3)
if c.get('mode') == 'hang_child':
    subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    time.sleep(30)
if c.get('mode') == 'graceful_deadline':
    while time.time() < c['deadline_epoch']:
        time.sleep(.005)
    # Simulate the final receipt/checkpoint write AFTER the worker stops work.
    time.sleep(.1)
result = {'job_id': c['job_id'], 'completed': True, 'seed': c['seed'],
          'cache_dir': c['cache_dir'], 'release_epoch': release['release_epoch'],
          'hf_home': os.environ['HF_HOME'], 'updates': 8, 'tokens': 2048}
result.update({k: c[k] for k in ('source_identity', 'workload_identity', 'device_identity') if k in c})
if c.get('mode') == 'foreign_result':
    result['job_id'] = 'foreign'
if c.get('mode') != 'missing_result':
    write('result.json', result)
'''


@unittest.skipUnless(sys.platform == "linux" and hasattr(os, "pidfd_open"), "Linux owned-process proof required")
class OwnedWaveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nvarc-wave-")
        self.root = Path(self.temporary.name)
        (self.root / "fixture_worker.py").write_text(WORKER)

    def tearDown(self):
        self.temporary.cleanup()

    def run_jobs(self, jobs, **kwargs):
        return run_wave(jobs, python=sys.executable, source_root=self.root,
                        output_root=self.root / "wave", deadline_epoch=time.time() + kwargs.pop("deadline", 25),
                        worker_module="fixture_worker", stop_timeout_seconds=2,
                        finalization_reserve_seconds=kwargs.pop("finalization_reserve_seconds", 0.1),
                        load_timeout_seconds=kwargs.pop("load_timeout_seconds", 5),
                        poll_seconds=0.01, **kwargs)

    def test_success_private_isolation_and_staggered_barrier(self):
        result = self.run_jobs([{"job_id": "2b-S", **IDENTITY}, {"job_id": "4b-S", **IDENTITY}])
        self.assertTrue(result["completed"])
        self.assertEqual(result["failures"], [])
        self.assertAlmostEqual(result["cold_startup_seconds"] + result["active_seconds"], result["wall_seconds"])
        first, second = result["jobs"]
        self.assertLessEqual(first["ready_receipt"]["epoch"], second["started_epoch"])
        self.assertEqual(first["result"]["release_epoch"], second["result"]["release_epoch"])
        self.assertNotEqual(first["result"]["seed"], second["result"]["seed"])
        self.assertNotEqual(first["result"]["cache_dir"], second["result"]["cache_dir"])
        for row in result["jobs"]:
            self.assertTrue(row["closure_verified"])
            self.assertGreater(row["closure_wall_seconds"], 0)
            self.assertLessEqual(row["closure_wall_seconds"], result["wall_seconds"])
            self.assertEqual(row["closure_attempts"], 1)
            self.assertEqual(row["closure"]["remaining"], [])
            self.assertEqual(row["closure"]["worker_returncode"], 0)
            self.assertFalse(row["closure"]["forced"])
            job_root = self.root / "wave" / row["job_id"]
            self.assertEqual(stat.S_IMODE((job_root / "worker.log").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((job_root / "config.json").stat().st_mode), 0o600)
            self.assertEqual(row["result"]["hf_home"], str(job_root / "cache" / "hf"))

    def test_failed_job_does_not_cancel_independent_sibling(self):
        result = self.run_jobs([{"job_id": "2b-S", "mode": "fail"}, {"job_id": "4b-S"}])
        self.assertFalse(result["completed"])
        self.assertEqual(result["failures"], ["2b-S"])
        self.assertEqual([row["status"] for row in result["jobs"]], ["worker_failed", "completed"])
        self.assertEqual(result["jobs"][0]["result"]["updates"], 2)
        self.assertTrue(all(row["closure_verified"] for row in result["jobs"]))
        self.assertGreater(result["wall_seconds"], 0)

    def test_four_distinct_workers_are_independently_closed(self):
        result = self.run_jobs([{"job_id": job_id} for job_id in JOB_IDS])
        self.assertTrue(result["completed"])
        self.assertEqual(len({row["result"]["seed"] for row in result["jobs"]}), 4)
        self.assertEqual(len({row["closure"]["root_identity"]["pid"] for row in result["jobs"]}), 4)
        self.assertTrue(all(row["closure_verified"] for row in result["jobs"]))

    def test_exit_before_barrier_cannot_fabricate_success(self):
        result = self.run_jobs([{"job_id": "2b-S", "mode": "premature_success"},
                                {"job_id": "4b-S", "mode": "slow_load"}])
        # The child may exit before ready.json is observed or after observation
        # while its sibling loads. Both are pre-barrier rejection, never success.
        self.assertIn(result["jobs"][0]["status"], {"exited_before_ready", "exited_before_release"})
        self.assertEqual(result["jobs"][1]["status"], "completed")
        self.assertFalse(result["completed"])

    def test_invalid_closure_never_allows_success(self):
        with mock.patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof",
                        side_effect=ValueError("fixture closure rejection")):
            result = self.run_jobs([{"job_id": "2b-S"}])
        self.assertFalse(result["completed"])
        self.assertEqual(result["jobs"][0]["status"], "closure_failed")
        self.assertFalse(result["jobs"][0]["closure_verified"])
        # Underlying real process was closed despite validation rejection.
        self.assertEqual(result["jobs"][0]["closure"]["remaining"], [])

    def test_uncertain_closure_blocks_new_launches(self):
        with mock.patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof",
                        side_effect=ValueError("fixture closure rejection")):
            result = self.run_jobs([{"job_id": "2b-S", "mode": "hang_load"},
                                    {"job_id": "4b-S"}], load_timeout_seconds=0.2)
        self.assertTrue(result["ownership_uncertain"])
        self.assertEqual(result["jobs"][1]["status"], "ownership_blocked")
        self.assertIsNone(result["jobs"][1]["closure"])
        self.assertFalse((self.root / "wave" / "4b-S").exists())

    def test_uncertain_closure_blocks_release_of_already_loaded_sibling(self):
        with mock.patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof",
                        side_effect=ValueError("fixture closure rejection")):
            result = self.run_jobs([{"job_id": "2b-S"},
                                    {"job_id": "4b-S", "mode": "hang_load"}],
                                   load_timeout_seconds=0.2)
        self.assertTrue(result["ownership_uncertain"])
        self.assertFalse(result["completed"])
        self.assertFalse((self.root / "wave" / "2b-S" / "release.json").exists())
        self.assertTrue(all(row["closure"]["remaining"] == [] for row in result["jobs"]))

    def test_worker_deadline_preserves_outer_bound_and_finalization(self):
        result = self.run_jobs([{"job_id": "2b-S", "training_deadline_epoch": time.time() + 1000}],
                               finalization_reserve_seconds=0.5)
        config = json.loads((self.root / "wave" / "2b-S" / "config.json").read_bytes())
        self.assertEqual(config["outer_deadline_epoch"], result["deadline_epoch"])
        self.assertEqual(config["deadline_epoch"], result["worker_deadline_epoch"])
        self.assertEqual(config["training_deadline_epoch"], config["deadline_epoch"])
        self.assertEqual(config["supervisor_work_deadline_epoch"], config["deadline_epoch"] + 0.5)
        self.assertEqual(config["outer_deadline_epoch"], config["supervisor_work_deadline_epoch"] + 2)
        self.assertLess(config["deadline_epoch"], config["outer_deadline_epoch"])

    def test_worker_can_finalize_after_its_work_deadline_without_being_killed(self):
        result = self.run_jobs([{"job_id": "2b-S", "mode": "graceful_deadline"}],
                               deadline=3, finalization_reserve_seconds=0.4)
        self.assertTrue(result["completed"])
        self.assertFalse(result["jobs"][0]["closure"]["forced"])
        self.assertLessEqual(result["started_epoch"] + result["wall_seconds"], result["deadline_epoch"])

    def test_load_timeout_closes_before_independent_sibling(self):
        result = self.run_jobs([{"job_id": "2b-S", "mode": "hang_load"}, {"job_id": "4b-S"}],
                               load_timeout_seconds=0.2)
        self.assertEqual([row["status"] for row in result["jobs"]], ["load_timeout", "completed"])
        self.assertTrue(all(row["closure_verified"] for row in result["jobs"]))
        self.assertTrue(result["jobs"][0]["closure"]["forced"])
        # The later finally pass must not remeasure/count an already closed
        # job. This row passes through close_job twice but closes once.
        self.assertEqual(result["jobs"][0]["closure_attempts"], 1)
        self.assertGreater(result["jobs"][0]["closure_wall_seconds"], 0)

    def test_deadline_closes_detached_descendant(self):
        result = self.run_jobs([{"job_id": "2b-S", "mode": "hang_child"}], deadline=3)
        self.assertFalse(result["completed"])
        self.assertTrue(result["deadline_reached"])
        row = result["jobs"][0]
        self.assertEqual(row["status"], "deadline_during_work")
        self.assertTrue(row["closure_verified"])
        self.assertTrue(row["closure"]["forced"])
        self.assertGreaterEqual(len(row["closure"]["owned_identities"]), 3)
        self.assertEqual(row["closure"]["remaining"], [])

    def test_deadline_before_launch_never_claims_completed(self):
        result = self.run_jobs([{"job_id": "2b-S"}], deadline=1)
        self.assertFalse(result["completed"])
        self.assertEqual(result["jobs"][0]["status"], "deadline_before_launch")
        self.assertIsNone(result["jobs"][0]["closure"])
        self.assertIsNone(result["jobs"][0]["closure_wall_seconds"])
        self.assertEqual(result["jobs"][0]["closure_attempts"], 0)
        self.assertEqual(result["active_seconds"], 0)

    def test_untrusted_receipts_do_not_become_success(self):
        for mode, expected in (("foreign_ready", "invalid_ready"),
                               ("foreign_result", "invalid_result"),
                               ("missing_result", "missing_result"),
                               ("exit_before_ready", "exited_before_ready")):
            with self.subTest(mode=mode):
                output = self.root / mode
                result = run_wave([{"job_id": "2b-S", "mode": mode}], python=sys.executable,
                                  source_root=self.root, output_root=output,
                                  deadline_epoch=time.time() + 20, worker_module="fixture_worker",
                                  stop_timeout_seconds=2, load_timeout_seconds=2,
                                  finalization_reserve_seconds=0.1, poll_seconds=0.01)
                self.assertFalse(result["completed"])
                self.assertEqual(result["jobs"][0]["status"], expected)
                self.assertTrue(result["jobs"][0]["closure_verified"])

    def test_duplicate_rng_or_consumed_output_refused(self):
        with self.assertRaises(ValueError):
            self.run_jobs([{"job_id": "2b-S", "seed": 1}, {"job_id": "4b-S", "seed": 1}])
        with self.assertRaises(ValueError):
            self.run_jobs([{"job_id": "2b-S", "variant": "4b", "arm": "S"}])
        self.run_jobs([{"job_id": "2b-S"}])
        with self.assertRaises(FileExistsError):
            self.run_jobs([{"job_id": "2b-S"}])


if __name__ == "__main__":
    unittest.main()

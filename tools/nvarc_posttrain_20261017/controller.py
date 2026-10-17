"""CPU coordinator: measured concurrency, four arms, two selected specialists.

This module never imports torch or initializes a CUDA context. Every physical
GPU workload runs through a fresh owned worker tree. No provider APIs exist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from tools.arc2_goal_sprint_20261017.data import canonical, digest
from tools.arc2_goal_sprint_20261017.launch import check_dataset_separation, sha, write_new
from .concurrency import JOB_IDS, assess_memory, choose_concurrency, deadline_admission, run_wave, schedule_waves
from .materials import model_pin


def progress(event, **fields):
    # Aggregate operational telemetry only: no challenge/answer grids, tokens,
    # model probabilities, private credentials or per-case evaluation feedback.
    print(json.dumps({"event": event, "epoch": time.time(), **fields}, sort_keys=True, allow_nan=False), flush=True)


def checkpoint_spec(receipt):
    return {key: receipt[key] for key in ("root", "manifest_sha256")}


CONSUMABLE_STATUSES = {"completed", "worker_failed", "missing_result", "deadline_during_work"}


def model_bound(identity, variant):
    pin = model_pin(variant)
    return (isinstance(identity, dict) and identity.get("model_source") == pin["model_source"]
        and identity.get("material_identity_sha256") == hashlib.sha256(canonical(pin)).hexdigest()
        and identity.get("verified_parameters") == pin["parameters"] and identity.get("remote_code_executed") is False)


def result_bound(result, *, job_id, mode, source_identity, device_identity):
    workload = {"train": "compact-four-arm-continuation-v1", "public": "compact-selected-full-public-v1"}[mode]
    return (isinstance(result, dict) and result.get("job_id") == job_id and result.get("mode") == mode
        and result.get("source_identity") == source_identity and result.get("device_identity") == device_identity
        and result.get("workload_identity") == workload and model_bound(result.get("model_identity"), job_id.split("-")[0]))


def public_record_admitted(row, *, source_identity, device_identity):
    if (row.get("job_id") not in {"2b-S", "4b-S"} or row.get("closure_verified") is not True
            or row.get("status") not in CONSUMABLE_STATUSES):
        return False
    if row.get("result") is not None:
        return result_bound(row["result"], job_id=row["job_id"], mode="public",
                            source_identity=source_identity, device_identity=device_identity)
    # Partial worker output is admissible only after matched model/device ready
    # evidence and verified closure. Identity-invalid receipts never reach here.
    ready = row.get("ready_receipt", {})
    return (ready.get("job_id") == row["job_id"] and ready.get("ready") is True
        and ready.get("device", {}).get("device_identity") == device_identity
        and model_bound(ready.get("base_identity"), row["job_id"].split("-")[0]))


def science_options(science, variant, output, *, source_identity, device_identity):
    options = []
    for row in science:
        if (not row["job_id"].startswith(variant) or not row["closure_verified"]
                or row["status"] not in CONSUMABLE_STATUSES):
            continue
        result = row.get("result")
        if result is not None:
            if not result_bound(result, job_id=row["job_id"], mode="train",
                                source_identity=source_identity, device_identity=device_identity):
                continue
            for phase in ("baseline", "posttrained"):
                dev = result["baseline"] if phase == "baseline" else result["dev"]
                if dev["complete"]:
                    options.append({"checkpoint_id": row["job_id"] + ":" + phase,
                        "checkpoint": checkpoint_spec(result["baseline_checkpoint"] if phase == "baseline" else result["checkpoint"]),
                        "dev": dev, "training_seconds": 0 if phase == "baseline" else result["training"]["wall_seconds"]})
            continue
        candidates = list(Path(output).glob("science-*/" + row["job_id"] + "/baseline-evidence.json"))
        if len(candidates) != 1:
            continue
        baseline = json.loads(candidates[0].read_bytes())
        if (baseline.get("job_id") == row["job_id"] and baseline.get("source_identity") == source_identity
                and baseline.get("device_identity") == device_identity
                and baseline.get("workload_identity") == "compact-four-arm-continuation-v1"
                and baseline.get("pre_training") is True and baseline.get("public_labels_used") is False
                and model_bound(baseline.get("model_identity"), variant)
                and baseline.get("dev", {}).get("complete") is True):
            options.append({"checkpoint_id": row["job_id"] + ":baseline",
                "checkpoint": checkpoint_spec(baseline["checkpoint"]), "dev": baseline["dev"], "training_seconds": 0})
    return options


def pick_checkpoint(reports):
    """Pure CPU counterpart of the generated-panel selection contract."""
    if (not reports or len({r["dev"]["panel_sha256"] for r in reports}) != 1
            or len({(r["dev"]["queries"], r["dev"]["views"], r["dev"]["ttt_steps"]) for r in reports}) != 1
            or any(not r["dev"]["complete"] for r in reports)):
        raise ValueError("complete identical generated development panels required")
    return sorted(reports, key=lambda r: (-r["dev"]["pass2"], -r["dev"]["pass1"],
        -r["dev"]["valid"], r["training_seconds"], r["checkpoint_id"]))[0]


def aggregate_benchmark(waves, concurrency, repeat, identities):
    jobs = [job for wave in waves for job in wave["jobs"]]
    return {**identities, "concurrency": concurrency, "repeat_id": str(repeat), "measured": True,
        "completed": len(jobs) == 4 and all(w["completed"] for w in waves),
        "failures": [j["job_id"] for j in jobs if j["status"] != "completed"],
        "wall_seconds": sum(w["wall_seconds"] for w in waves),
        "cold_startup_seconds": sum(w["cold_startup_seconds"] for w in waves),
        "active_seconds": sum(w["active_seconds"] for w in waves),
        "jobs": [{"job_id": j["job_id"], "completed": j["status"] == "completed",
                  "tokens": (j.get("result") or {}).get("tokens", 0),
                  "updates": (j.get("result") or {}).get("updates", 0)} for j in jobs]}


def measure_full_export(public, output, *, candidate_views):
    """Measure all growing answer-free worst-shape query exports, not one stub.

    Zero grids below are synthetic byte-load fixtures, never model candidates.
    No answer source is opened and no fixture is placed at the scoring paths.
    """
    selected, full = [], []
    grid = [[0] * 30 for _ in range(30)]
    started = time.monotonic()
    for task_id in sorted(public):
        row = {"task_id": task_id, "tests": []}
        selected.append(row)
        for index, query in enumerate(public[task_id]["test"]):
            row["tests"].append({"test_index": index, "input_digest": digest(query["input"]), "ranked_grids": [grid, grid]})
            full.append({"task_id": task_id, "test_index": index, "candidates": [{"grid": grid, "votes": 1,
                "nll_sum": 1., "views": [v]} for v in range(candidate_views)],
                "ranked_candidate_indices": list(range(candidate_views))})
            for name, body in (("synthetic-export-selected.json", selected), ("synthetic-export-full.json", full)):
                path = Path(output) / name
                with path.open("wb") as stream:
                    stream.write(canonical(body))
                    stream.flush()
                    os.fsync(stream.fileno())
    sha(Path(output) / "synthetic-export-selected.json")
    sha(Path(output) / "synthetic-export-full.json")
    return {"measured": True, "synthetic_byte_load_only": True, "queries": len(full),
            "wall_seconds": time.monotonic() - started, "candidate_views": candidate_views}


def ensemble_pools(public, pools_by_variant, *, run_id):
    """One best answer from each specialist, then fill a duplicate gap to TWO."""
    expected = {(key, i) for key, task in public.items() for i in range(len(task["test"]))}
    if len(public) != 120 or len(expected) != 167:
        raise ValueError("full PUBLIC120 task/query inventory required")
    indexes = {}
    for variant, pools in pools_by_variant.items():
        if variant not in {"2b", "4b"} or pools["challenges_digest"] != digest(public):
            raise ValueError("selected model challenge identity differs")
        flat = [(row["task_id"], t) for row in pools["records"] for t in row["tests"]]
        rows = {(key, t["test_index"]): t for key, t in flat}
        if len(flat) != 167 or set(rows) != expected or len(pools["records"]) != 120:
            raise ValueError("complete model query inventory required")
        for row in rows.values():
            grids = row["ranked_grids"]
            if not isinstance(grids, list) or len(grids) > 2:
                raise ValueError("at most two strict model grids required")
            for grid in grids:
                if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
                        or any(not isinstance(line, list) or not 1 <= len(line) <= 30 for line in grid)
                        or len({len(line) for line in grid}) != 1
                        or any(type(value) is not int or not 0 <= value <= 9 for line in grid for value in line)):
                    raise ValueError("at most two strict model grids required")
        indexes[variant] = rows
    if set(indexes) != {"2b", "4b"}:
        raise ValueError("both selected specialists required, including explicit missing results")
    result = {"format": "irisx/arc-offline-pools-v1", "run_id": run_id,
        "method": "one top candidate per official NVARC specialist, duplicate-fill, total pass@2",
        "challenges_digest": digest(public), "records": []}
    for task_id in sorted(public):
        tests = []
        for i, query in enumerate(public[task_id]["test"]):
            rows = [indexes[v][task_id, i] for v in ("4b", "2b")]
            if any(r["input_digest"] != digest(query["input"]) for r in rows):
                raise ValueError("selected model query mapping differs")
            options = [r["ranked_grids"] for r in rows]
            grids = []
            for rank in range(2):
                for candidates in options:
                    if rank < len(candidates) and candidates[rank] not in grids:
                        grids.append(candidates[rank])
                    if len(grids) == 2:
                        break
                if len(grids) == 2:
                    break
            tests.append({"test_index": i, "input_digest": digest(query["input"]), "ranked_grids": grids,
                          "status": "complete" if all(r["status"] == "complete" for r in rows) else "partial"})
        result["records"].append({"task_id": task_id, "tests": tests})
    return result


def run(config):
    source, output = Path(config["source_root"]), Path(config["output_root"])
    output.mkdir(parents=True, exist_ok=False)
    if config["deadline_epoch"] != config["started_epoch"] + 43200 or not 0 < config["started_epoch"] <= time.time() < config["deadline_epoch"]:
        raise ValueError("original pre-dispatch 12-hour deadline required")
    check_dataset_separation(config["input_root"], config["allowed_input_roots"])
    write_new(output / "isolation.json", {"mechanism": "dataset-separated-provider-execution",
        "evaluator_dataset_absent": True, "os_sandbox_claimed": False,
        "allowed_input_roots": config["allowed_input_roots"], "answer_reads_permitted": False,
        "scoring": "external CPU only after complete owned-tree closure and exact provider terminal verification"})
    env = {**os.environ, **config["runtime_env"], "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    # Dedicated subprocess exits before any worker starts; coordinator stays CPU-only.
    probe = subprocess.run([config["python"], "-B", "-m", "tools.nvarc_posttrain_20261017.worker", "--topology"],
                           cwd=source, env=env, check=True, capture_output=True, text=True, timeout=120)
    topology = json.loads(probe.stdout.splitlines()[-1])
    write_new(output / "topology.json", topology)
    progress("actual_topology", **topology)
    identities = {"source_identity": config["source_identity"], "workload_identity": "compact-r64-2k4k8k-kv64-af3-8-v1",
                  "device_identity": topology["device_identity"]}
    jobs = []
    for index, job_id in enumerate(JOB_IDS):
        variant, arm = job_id.split("-")
        jobs.append({**identities, "job_id": job_id, "variant": variant, "arm": arm, "mode": "probe",
            "model_root": config["model_roots"][variant], "seed": 7321 + index,
            "adapter_seed": 731 if variant == "2b" else 739, "cpu_threads": 1,
            "parameters": config.get("parameters", {}), "allocator_fraction": .8,
            **{key: config[key] for key in ("training_root", "training_manifest_path", "public_path")}})
    benchmark_deadline = min(config["deadline_epoch"] - 300, time.time() + 3600)
    benchmarks, measurements = [], {}
    def allocated(wave):
        if len(measurements) != 4:
            return [{**job, "allocator_fraction": .8} for job in wave]
        policy = assess_memory(list(measurements.values()), topology, len(wave))
        if not policy["admitted"]:
            raise RuntimeError("actual wave no longer passes measured memory admission")
        reservations = {key: value for part in policy["waves"] for key, value in part["per_job_reserved_bytes"].items()}
        return [{**job, "allocator_fraction": reservations[job["job_id"]] / topology["total_bytes"]} for job in wave]
    def execute(wave, path, deadline):
        progress("wave_start", phase=path.name, jobs=[j["job_id"] for j in wave], mode=wave[0]["mode"], deadline_epoch=deadline)
        receipt = run_wave(wave, python=config["python"], source_root=str(source), output_root=str(path),
                        deadline_epoch=deadline, common_env=env, load_timeout_seconds=600, stop_timeout_seconds=15)
        if any(not row["closure_verified"] and row["status"] not in {"deadline_before_launch", "ownership_blocked"}
               for row in receipt["jobs"]):
            raise RuntimeError("owned worker closure unverified; no further dispatch or prediction export")
        progress("wave_closed", phase=path.name, wall_seconds=receipt["wall_seconds"],
                 jobs=[{"job_id": row["job_id"], "status": row["status"], "closure_verified": row["closure_verified"]}
                       for row in receipt["jobs"]])
        return receipt
    for concurrency in (1, 2, 4):
        if concurrency != 1:
            if len(measurements) != 4 or not assess_memory(list(measurements.values()), topology, concurrency)["admitted"]:
                continue
        for repeat in range(2):
            if time.time() >= benchmark_deadline:
                break
            waves = []
            for wave_index, wave in enumerate(schedule_waves(jobs, concurrency)):
                if time.time() >= benchmark_deadline:
                    break
                configured = allocated(wave)
                receipt = execute(configured, output / f"benchmark-c{concurrency}-r{repeat}-w{wave_index}", benchmark_deadline)
                waves.append(receipt)
                for row in receipt["jobs"]:
                    if row["status"] == "completed":
                        measured = {**identities, **{key: row["result"][key] for key in
                            ("job_id", "tokens", "updates", "peak_allocated_bytes", "peak_reserved_bytes")},
                            "completed": True, "measured": True}
                        old = measurements.get(row["job_id"])
                        if old:
                            for key in ("peak_allocated_bytes", "peak_reserved_bytes"):
                                measured[key] = max(old[key], measured[key])
                        measurements[row["job_id"]] = measured
            if waves:
                benchmarks.append(aggregate_benchmark(waves, concurrency, repeat, identities))
                write_new(output / f"benchmark-c{concurrency}-r{repeat}.json", benchmarks[-1])
    if len(measurements) != 4:
        raise RuntimeError("serial resource admission incomplete; no unmeasured scientific execution")
    admission = choose_concurrency(list(measurements.values()), topology, benchmarks)
    write_new(output / "concurrency-admission.json", admission)
    if not admission["admitted"]:
        raise RuntimeError("no measured safe concurrency admitted")
    concurrency = admission["concurrency"]
    progress("concurrency_selected", processes=concurrency, hardware_partition_claimed=False)
    # Pilot both models using train-derived dev only, before allocating training.
    pilot_jobs = [{**job, "mode": "pilot",
                   "workload_identity": "compact-demo-ttt-and-view-pilot-v1"} for job in jobs if job["arm"] == "S"]
    pilots = []
    pilot_concurrency = min(concurrency, 2)
    for index in range(0, len(pilot_jobs), pilot_concurrency):
        receipt = execute(allocated(pilot_jobs[index:index+pilot_concurrency]), output / f"pilot-{index}",
                          min(config["deadline_epoch"] - 300, time.time() + 2400))
        if not receipt["completed"]:
            raise RuntimeError("complete actual TTT/inference cost pilot required")
        pilots.extend(receipt["jobs"])
    # Output export benchmark uses challenge IDs only, never reference answers.
    public = json.loads(Path(config["public_path"]).read_bytes())
    empty = {"format": "irisx/arc-offline-pools-v1", "run_id": config["run_id"], "challenges_digest": digest(public),
        "records": [{"task_id": k, "tests": [{"test_index": i, "input_digest": digest(q["input"]),
            "ranked_grids": [], "status": "not_attempted"} for i, q in enumerate(public[k]["test"])]} for k in sorted(public)]}
    write_new(output / "empty-complete-inventory.json", empty)
    export = measure_full_export(public, output, candidate_views=config.get("parameters", {}).get("public_views", 8))
    write_new(output / "export-cost.json", export)
    reserves = []
    for pilot in pilots:
        r, rows = pilot["result"], pilot["result"]["pilot"]["records"]
        p = {**{key: r[key] for key in identities}, "measured": True, "completed": True,
             "ttt_tasks": len(rows), "inference_queries": len(rows),
             "ttt_wall_seconds": sum(x["task_lifecycle_seconds"] - x["inference_seconds"] for x in rows),
             "inference_wall_seconds": sum(x["inference_seconds"] for x in rows),
             "cold_startup_seconds": r["cold_startup_seconds"] + r["pilot"]["unamortized_setup_restore_seconds"],
             "export_seconds": export["wall_seconds"],
             "closure_seconds": pilot["closure_wall_seconds"]}
        reserves.append(deadline_admission(now_epoch=time.time(), deadline_epoch=config["deadline_epoch"] - 180,
                                           planned_training_seconds=0, pilot=p, candidates=1, safety_factor=1.5))
    evaluation_reserve = sum(r["reserve_seconds"] for r in reserves)
    write_new(output / "evaluation-cost-admission.json", {"models": reserves, "reserve_seconds": evaluation_reserve,
               "two_full_models_serially_budgeted": True, "external_scoring_not_in_provider_session": True})
    training_end = config["deadline_epoch"] - 180 - evaluation_reserve
    progress("phase_budget", evaluation_reserve_seconds=evaluation_reserve, training_end_epoch=training_end,
             original_session_deadline_epoch=config["deadline_epoch"])
    if training_end <= time.time():
        raise RuntimeError("measured full evaluation cannot fit this recipe; preserve pilot and redesign, not truncate denominator")
    science = []
    training_waves = schedule_waves(jobs, concurrency)
    for index, wave in enumerate(training_waves):
        now = time.time()
        wave_end = now + max(0, training_end - now) / (len(training_waves) - index)
        # A fifth of each phase is reserved for the same generated dev panel.
        train_deadline = now + .8 * max(0, wave_end - now)
        configured = [{**job, "mode": "train",
                       "training_deadline_epoch": train_deadline,
                       "workload_identity": "compact-four-arm-continuation-v1"} for job in wave]
        receipt = execute(allocated(configured), output / f"science-{index}", wave_end)
        science.extend(receipt["jobs"])
    write_new(output / "science-results.json", science)
    selected = {}
    for variant in ("2b", "4b"):
        options = science_options(science, variant, output, source_identity=config["source_identity"],
                                  device_identity=topology["device_identity"])
        selected[variant] = pick_checkpoint(options)
    write_new(output / "selected-checkpoints.json", selected)
    progress("pre_public_selection", checkpoints={key: value["checkpoint_id"] for key, value in selected.items()},
             inherited_exposure_qualified=True)
    public_jobs = []
    for job in jobs:
        if job["arm"] != "S":
            continue
        public_jobs.append({**job, "mode": "public",
            "checkpoint": selected[job["variant"]]["checkpoint"], "workload_identity": "compact-selected-full-public-v1"})
    results, pool_paths, public_admission = [], {}, {}
    reserve_by_variant = {row["job_id"].split("-")[0]: reserve["reserve_seconds"] for row, reserve in zip(pilots, reserves)}
    for index in range(0, len(public_jobs), min(concurrency, 2)):
        wave = public_jobs[index:index+min(concurrency, 2)]
        remaining = public_jobs[index:]
        share = sum(reserve_by_variant[j["variant"]] for j in wave) / sum(reserve_by_variant[j["variant"]] for j in remaining)
        wave_deadline = time.time() + max(0, config["deadline_epoch"] - 90 - time.time()) * share
        receipt = execute(allocated(wave), output / f"public-{index}", wave_deadline)
        results.extend(receipt["jobs"])
        for row in receipt["jobs"]:
            path = output / f"public-{index}" / row["job_id"] / "pools.json"
            # A failed worker still contributes its initialized complete missing
            # inventory. It is scored as failure, never silently removed.
            admitted = public_record_admitted(row, source_identity=config["source_identity"], device_identity=topology["device_identity"])
            variant = row["job_id"].split("-")[0]
            pool_paths[variant] = str(path) if admitted and path.is_file() else None
            public_admission[variant] = {"admitted": bool(pool_paths[variant]), "status": row["status"],
                "path": path.relative_to(output).as_posix() if pool_paths[variant] else None}
    write_new(output / "public-evidence-admission.json", {"source_identity": config["source_identity"], "models": public_admission})
    pools = {variant: json.loads(Path(path).read_bytes()) if path is not None else empty
             for variant, path in pool_paths.items()}
    merged = ensemble_pools(public, pools, run_id=config["run_id"])
    write_new(output / "pools.json", merged)
    summary = {"run_id": config["run_id"], "source_identity": config["source_identity"],
        "solver_status": "complete" if len(results) == 2 and all(r["status"] == "completed"
            and (r.get("result") or {}).get("completed") is True for r in results)
            and set(public_admission) == {"2b", "4b"} and all(r["admitted"] for r in public_admission.values()) else "partial",
        "selected": selected, "concurrency": admission, "models": results,
        "inherited_exposure_qualified": True, "clean_generalization_claimed": False,
        "external_scoring_required": True, "public_tasks": 120, "public_queries": 167,
        "combined_max_guesses_per_query": 2, "model_pool_paths": pool_paths}
    write_new(output / "run-summary.json", summary)
    progress("full_prediction_inventory_written", tasks=120, queries=167, solver_status=summary["solver_status"],
             external_scoring_required=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.config).read_bytes()))


if __name__ == "__main__":
    main()

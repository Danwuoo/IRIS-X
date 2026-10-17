"""CPU-only admission and owned-process orchestration for four NVARC arms.

These policies consume *measured* receipts, not parameter-count estimates.
Their numeric fixtures and passing CPU tests do not attest GPU feasibility or
quality. No CUDA library, device context, MIG/MPS/DDP or host security setting is
initialized here. Device observations must come from a separate worker/process.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import time

GIB = 1024 ** 3
JOB_IDS = ("2b-S", "4b-S", "2b-H", "4b-H")
IDENTITIES = ("source_identity", "workload_identity", "device_identity")
PUBLIC_TASKS = 120
PUBLIC_QUERIES = 167
MAX_RECEIPT_BYTES = 4 * 1024 ** 2


def _number(value, name, *, positive=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0 or (positive and value == 0)):
        raise ValueError(name + " must be finite and " + ("positive" if positive else "nonnegative"))
    return value


def _integer(value, name, *, positive=False):
    if type(value) is not int or value < 0 or (positive and value == 0):
        raise ValueError(name + " must be a " + ("positive" if positive else "nonnegative") + " integer")
    return value


def _identity(row):
    if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip() for k in IDENTITIES):
        raise ValueError("source, workload and device identities required")
    return tuple(row[k] for k in IDENTITIES)


def _job_id(job):
    return job if isinstance(job, str) else job.get("job_id") if isinstance(job, dict) else None


def _jobs(jobs, *, complete=True):
    jobs = list(jobs)
    ids = [_job_id(job) for job in jobs]
    if (any(x not in JOB_IDS for x in ids) or len(set(ids)) != len(ids)
            or (complete and set(ids) != set(JOB_IDS))
            or (not complete and len(ids) not in (1, 2, 4))):
        raise ValueError("unique fixed NVARC jobs required: " + ", ".join(JOB_IDS))
    return {job_id: job for job_id, job in zip(ids, jobs)}


def schedule_waves(jobs, concurrency):
    """Schedule every fixed job once; two-way waves each mix 2B and 4B.

    The return value contains the original job objects, ordered independently
    of input iteration order. Concurrency means independent processes sharing
    one device, never a claim of hardware partitioning.
    """
    if type(concurrency) is not int or concurrency not in (1, 2, 4):
        raise ValueError("concurrency must be 1, 2 or 4")
    by_id = _jobs(jobs)
    ordered = [by_id[job_id] for job_id in JOB_IDS]
    return [ordered[start:start + concurrency] for start in range(0, 4, concurrency)]


def _measurements(measurements, topology):
    by_id = _jobs(measurements)
    if (not isinstance(topology, dict) or topology.get("measured") is not True
            or type(topology.get("device_count")) is not int or topology["device_count"] != 1
            or not isinstance(topology.get("device_identity"), str) or not topology["device_identity"].strip()):
        raise ValueError("actual one-device topology receipt required")
    total = _integer(topology.get("total_bytes"), "total_bytes", positive=True)
    free = _integer(topology.get("free_bytes"), "free_bytes")
    if free > total:
        raise ValueError("free bytes exceed measured total")
    identities = set()
    for row in by_id.values():
        if row.get("measured") is not True or row.get("completed") is not True:
            raise ValueError("completed actual per-job memory measurement required")
        identities.add(_identity(row))
        if row["device_identity"] != topology["device_identity"]:
            raise ValueError("memory and topology device identities differ")
        allocated = _integer(row.get("peak_allocated_bytes"), "peak_allocated_bytes", positive=True)
        reserved = _integer(row.get("peak_reserved_bytes"), "peak_reserved_bytes", positive=True)
        if reserved < allocated or reserved > total:
            raise ValueError("inconsistent measured allocator peaks")
        _integer(row.get("tokens"), "tokens", positive=True)
        _integer(row.get("updates"), "updates", positive=True)
    if len(identities) != 1:
        raise ValueError("memory source/workload/device identity mismatch")
    return by_id, total, free


def assess_memory(measurements, topology, concurrency):
    """Apply baseline + sum(ceil(1.2 * peak) + 2 GiB) <= 0.8 * total.

    ``free_bytes`` must be observed before these jobs are loaded; total minus
    free is the baseline resident usage. This is a conservative admission
    calculation, not a measurement of the concurrent runtime's peak memory.
    """
    by_id, total, free = _measurements(measurements, topology)
    waves = schedule_waves(by_id.values(), concurrency)
    budget = total * 4 // 5
    baseline = total - free
    records = []
    for wave in waves:
        reservations = {
            row["job_id"]: (6 * max(row["peak_allocated_bytes"], row["peak_reserved_bytes"]) + 4) // 5 + 2 * GIB
            for row in wave
        }
        required = baseline + sum(reservations.values())
        records.append({"job_ids": [row["job_id"] for row in wave],
                        "per_job_reserved_bytes": reservations,
                        "required_bytes": required, "admitted": required <= budget})
    return {"admitted": all(row["admitted"] for row in records),
            "concurrency": concurrency, "total_bytes": total, "baseline_bytes": baseline,
            "budget_bytes": budget, "waves": records,
            "basis": "measured individual peaks with conservative margin; not concurrent peak measurement"}


def _validate_benchmark(row, measurements):
    if not isinstance(row, dict):
        raise ValueError("benchmark object required")
    if (type(row.get("concurrency")) is not int or row["concurrency"] not in (1, 2, 4)
            or not isinstance(row.get("repeat_id"), str) or not row["repeat_id"].strip()):
        raise ValueError("benchmark concurrency and repeat identity required")
    if row.get("measured") is not True or row.get("completed") is not True or row.get("failures") != []:
        raise ValueError("completed measured failure-free benchmark required")
    if _identity(row) != _identity(next(iter(measurements.values()))):
        raise ValueError("benchmark source/workload/device identity differs")
    wall = _number(row.get("wall_seconds"), "wall_seconds", positive=True)
    cold = _number(row.get("cold_startup_seconds"), "cold_startup_seconds")
    active = _number(row.get("active_seconds"), "active_seconds", positive=True)
    if cold + active > wall + 1e-6 * max(1, wall):
        raise ValueError("full wall time must include startup and active work")
    by_id = _jobs(row.get("jobs", []))
    for job_id, job in by_id.items():
        if job.get("completed") is not True:
            raise ValueError("every exact benchmark job must complete")
        for key in ("tokens", "updates"):
            if _integer(job.get(key), key, positive=True) != measurements[job_id][key]:
                raise ValueError("benchmark fixed token/update work differs")
    return row


def choose_concurrency(measurements, topology, benchmarks, *, min_improvement=0.05, min_repeats=2):
    """Choose 1/2/4 only from identity-matched complete fixed-work receipts.

    Every paired repeat must clear the gain, not merely their average. Two-way
    may win without four-way evidence. Four-way must beat both serial and the
    measured two-way schedule. Malformed or failed candidate receipts invalidate
    that candidate rather than disappearing from its repeat set. All observed
    wall costs, including failures/rejected identities, remain in physical_cost.
    """
    _number(min_improvement, "min_improvement", positive=True)
    if min_improvement < 0.05:
        raise ValueError("at least five percent measured throughput gain required")
    if type(min_repeats) is not int or min_repeats < 2:
        raise ValueError("at least two paired repeats required")
    measurements, _, _ = _measurements(measurements, topology)
    memory = {str(c): assess_memory(measurements.values(), topology, c) for c in (1, 2, 4)}
    groups = {1: {}, 2: {}, 4: {}}
    invalid = {1: [], 2: [], 4: []}
    reasons, unknown, observed = [], 0, 0.0
    for index, row in enumerate(benchmarks):
        try:
            observed += _number(row.get("wall_seconds"), "wall_seconds", positive=True)
        except (ValueError, AttributeError):
            unknown += 1
        try:
            valid = _validate_benchmark(row, measurements)
            c, repeat = valid["concurrency"], valid["repeat_id"]
            if repeat in groups[c]:
                raise ValueError("duplicate repeat identity")
            groups[c][repeat] = valid
        except (ValueError, TypeError, AttributeError) as exc:
            message = "receipt " + str(index) + ": " + str(exc)
            c = row.get("concurrency") if isinstance(row, dict) else None
            if type(c) is int and c in invalid:
                invalid[c].append(message)
            else:
                # Unattributable receipts cannot be silently excluded.
                for errors in invalid.values():
                    errors.append(message)
            reasons.append(message)
    usable = {c: bool(groups[c]) and not invalid[c] and memory[str(c)]["admitted"] for c in groups}
    comparisons = {}

    def improves(candidate, baseline):
        key = str(candidate) + "_vs_" + str(baseline)
        record = {"admitted": False, "gains": {}}
        comparisons[key] = record
        if not usable[candidate] or not usable[baseline]:
            record["reason"] = "valid completed benchmarks and memory admission required"
            return False
        if set(groups[candidate]) != set(groups[baseline]) or len(groups[candidate]) < min_repeats:
            record["reason"] = "identical paired repeat sets with at least two repeats required"
            return False
        for repeat in sorted(groups[candidate]):
            # Identical total tokens/updates makes throughput ratio equal to
            # the inverse full-wall makespan ratio, including cold startup.
            record["gains"][repeat] = groups[baseline][repeat]["wall_seconds"] / groups[candidate][repeat]["wall_seconds"] - 1
        record["admitted"] = all(gain + 1e-12 >= min_improvement for gain in record["gains"].values())
        record["reason"] = "every repeat must improve full-wall throughput by at least " + str(min_improvement)
        return record["admitted"]

    selected = 1 if usable[1] else None
    two = improves(2, 1)
    four_serial = improves(4, 1)
    four_two = improves(4, 2)
    if two:
        selected = 2
    if four_serial and four_two:
        selected = 4
    if selected is None:
        reasons.append("no completed serial reference with actual memory admission")
    return {"admitted": selected is not None, "concurrency": selected,
            "reasons": reasons, "memory": memory, "comparisons": comparisons,
            "physical_cost": {"observed_wall_seconds": observed, "unknown_wall_receipts": unknown},
            "selection_basis": "fixed-work repeated full-wall throughput; no quota-hour gate"}


def deadline_admission(*, now_epoch, deadline_epoch, planned_training_seconds, pilot,
                       candidates=4, safety_factor=1.25):
    """Reserve complete PUBLIC120 (120 tasks/167 queries) work from a pilot.

    The pilot's TTT and inference costs are independently extrapolated by their
    measured task/query counts. Startup, export and closure are measured
    *per-candidate* costs. Evaluation is conservatively budgeted serially; no
    unmeasured concurrency discount or minimum available-hours rule is applied.
    Answer scoring is external after provider termination, outside this reserve.
    A pilot is a cost observation, never a quality/effectiveness claim.
    """
    _number(now_epoch, "now_epoch", positive=True)
    _number(deadline_epoch, "deadline_epoch", positive=True)
    _number(planned_training_seconds, "planned_training_seconds")
    _integer(candidates, "candidates", positive=True)
    _number(safety_factor, "safety_factor", positive=True)
    if safety_factor < 1:
        raise ValueError("reserve safety factor cannot reduce measured cost")
    if not isinstance(pilot, dict) or pilot.get("measured") is not True or pilot.get("completed") is not True:
        raise ValueError("completed actual cost pilot required")
    _identity(pilot)
    tasks = _integer(pilot.get("ttt_tasks"), "ttt_tasks", positive=True)
    queries = _integer(pilot.get("inference_queries"), "inference_queries", positive=True)
    if tasks > PUBLIC_TASKS or queries > PUBLIC_QUERIES:
        raise ValueError("pilot counts exceed complete PUBLIC120 denominator")
    ttt = _number(pilot.get("ttt_wall_seconds"), "ttt_wall_seconds", positive=True)
    inference = _number(pilot.get("inference_wall_seconds"), "inference_wall_seconds", positive=True)
    extras = sum(_number(pilot.get(key), key, positive=True) for key in
                 ("cold_startup_seconds", "export_seconds", "closure_seconds"))
    per_candidate = ttt * PUBLIC_TASKS / tasks + inference * PUBLIC_QUERIES / queries + extras
    reserve = candidates * per_candidate * safety_factor
    remaining = max(0, deadline_epoch - now_epoch)
    available = max(0, remaining - reserve)
    return {"admitted": remaining >= reserve + planned_training_seconds,
            "remaining_seconds": remaining, "reserve_seconds": reserve,
            "available_training_seconds": available, "planned_training_seconds": planned_training_seconds,
            "candidates": candidates, "public_tasks": PUBLIC_TASKS, "public_queries": PUBLIC_QUERIES,
            "external_scoring_in_provider_reserve": False,
            "basis": "measured pilot extrapolation with answer-free export/closure; external scoring not charged to provider session"}


def _read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ValueError("regular bounded worker receipt required")
    with path.open("rb") as stream:
        raw = stream.read(MAX_RECEIPT_BYTES + 1)
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ValueError("worker receipt exceeds bound")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("worker receipt object required")
    return result


def _write_json(path, value):
    raw = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ValueError("metadata exceeds bound")
    temporary = path.with_name(path.name + ".pending")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if path.exists():
        raise ValueError("worker metadata identity already consumed")
    os.replace(temporary, path)


def run_wave(jobs, *, python, source_root, output_root, deadline_epoch,
             worker_module="tools.nvarc_posttrain_20261017.worker", common_env=None,
             load_timeout_seconds=300, stop_timeout_seconds=10,
             finalization_reserve_seconds=30, poll_seconds=0.05):
    """Launch an already-admitted 1/2/4-process wave through owned guards.

    This mechanism does NOT grant admission; call the measured policies first.
    Jobs are dictionaries containing a fixed job_id and optional worker config.
    Each gets private output/cache/RNG paths and a different deterministic seed.
    Loads are staggered by ready.json; all surviving loaded workers receive a
    release.json barrier. Failures never become successful results and do not
    cancel independent siblings except at the physical platform deadline.

    The worker writes {job_id, ready: true}, waits for its release_path, then
    writes {job_id, completed: true, ...} to result.json. Result identity fields
    supplied in config must match. Logs are private files and never emitted.
    Every launched tree is closed and independently checked before return.
    Worker deadline_epoch precedes the coordinator's kill deadline by an
    explicit finalization reserve; outer_deadline_epoch retains the unchanged
    supplied bound. No new clock is granted to a worker or a later wave.
    """
    from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof

    by_id = _jobs(jobs, complete=False)
    if any(not isinstance(job, dict) for job in by_id.values()):
        raise ValueError("worker config dictionaries required")
    _number(deadline_epoch, "deadline_epoch", positive=True)
    for name, value in (("load_timeout_seconds", load_timeout_seconds),
                        ("stop_timeout_seconds", stop_timeout_seconds),
                        ("finalization_reserve_seconds", finalization_reserve_seconds),
                        ("poll_seconds", poll_seconds)):
        _number(value, name, positive=True)
    if finalization_reserve_seconds > 300:
        raise ValueError("finalization reserve must be bounded to at most 300 seconds")
    if not isinstance(python, str) or not python or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", worker_module):
        raise ValueError("explicit Python and module required")
    source = Path(source_root).resolve(strict=True)
    output = Path(output_root).absolute()
    if not source.is_dir() or any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError("regular source/output directories required")
    env_additions = dict(common_env or {})
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in env_additions.items()):
        raise ValueError("environment keys and values must be strings")
    configs, seeds = {}, set()
    for job_id in JOB_IDS:
        if job_id not in by_id:
            continue
        config = dict(by_id[job_id])
        variant, arm = job_id.split("-")
        if ("variant" in config and config["variant"] != variant
                or "arm" in config and config["arm"] != arm):
            raise ValueError("job identity and model/arm configuration differ")
        seed = config.get("seed", 1729 + JOB_IDS.index(job_id))
        _integer(seed, "seed")
        if seed >= 2 ** 32 or seed in seeds:
            raise ValueError("distinct uint32 RNG seeds required for independent jobs")
        seeds.add(seed)
        config["seed"] = seed
        if "training_deadline_epoch" in config:
            _number(config["training_deadline_epoch"], "training_deadline_epoch", positive=True)
        configs[job_id] = config
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    started, epoch_started = time.monotonic(), time.time()
    # Reserve enough time for bounded, independent closure of every owned tree.
    closure_reserve = stop_timeout_seconds * len(configs)
    work_deadline_epoch = deadline_epoch - closure_reserve
    worker_deadline_epoch = work_deadline_epoch - finalization_reserve_seconds
    work_deadline = started + work_deadline_epoch - epoch_started
    records, guards, streams, ready = {}, {}, {}, []
    released_at, timed_out, ownership_uncertain = None, False, False

    def remaining():
        return min(work_deadline - time.monotonic(),
                   deadline_epoch - time.time() - stop_timeout_seconds * len(configs))

    def close_job(job_id, force=False):
        nonlocal ownership_uncertain
        record = records[job_id]
        # Once complete closure has been freshly verified, a later finally
        # pass is a no-op. A stopped incarnation cannot become alive again.
        if record["closure_verified"]:
            return record["closure"]
        guard = guards[job_id]
        closure_started = time.monotonic()
        try:
            proof = guard.stop(timeout=stop_timeout_seconds) if force or guard.poll() is None else guard.closed_proof()
            record["closure"] = proof
            try:
                verify_closed_proof(proof)
                record["closure_verified"] = True
            except (ValueError, OSError):
                record["closure_verified"] = False
                record["status"] = "closure_failed"
                ownership_uncertain = True
            return proof
        finally:
            # Include every actual close/verification call, including failure;
            # do not substitute a guessed minimum for a missing measurement.
            record["closure_wall_seconds"] = (record["closure_wall_seconds"] or 0.0) + time.monotonic() - closure_started
            record["closure_attempts"] += 1

    try:
        for job_id, config in configs.items():
            record = {"job_id": job_id, "status": "not_started", "result": None,
                      "closure": None, "closure_verified": False,
                      "closure_wall_seconds": None, "closure_attempts": 0}
            records[job_id] = record
            if ownership_uncertain:
                record["status"] = "ownership_blocked"
                continue
            if remaining() <= finalization_reserve_seconds:
                timed_out = True
                record["status"] = "deadline_before_launch"
                continue
            root = output / job_id
            root.mkdir(mode=0o700)
            cache = root / "cache"
            cache.mkdir(mode=0o700)
            temp = root / "tmp"
            temp.mkdir(mode=0o700)
            config.update({"output_dir": str(root), "cache_dir": str(cache),
                           "ready_path": str(root / "ready.json"), "release_path": str(root / "release.json"),
                           "rng_state_path": str(root / "rng-state.pt"),
                           "outer_deadline_epoch": deadline_epoch,
                           "supervisor_work_deadline_epoch": work_deadline_epoch,
                           "deadline_epoch": worker_deadline_epoch})
            if "training_deadline_epoch" in config:
                config["training_deadline_epoch"] = min(config["training_deadline_epoch"], worker_deadline_epoch)
            _write_json(root / "config.json", config)
            env = os.environ.copy()
            env.update(env_additions)
            env.update({"PYTHONHASHSEED": str(config["seed"]), "HF_HOME": str(cache / "hf"),
                        "HF_DATASETS_CACHE": str(cache / "datasets"), "TRANSFORMERS_CACHE": str(cache / "transformers"),
                        "TORCH_HOME": str(cache / "torch"), "TRITON_CACHE_DIR": str(cache / "triton"),
                        "XDG_CACHE_HOME": str(cache / "xdg"), "TMPDIR": str(temp)})
            fd = os.open(root / "worker.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            streams[job_id] = os.fdopen(fd, "wb")
            launch = time.monotonic()
            record["started_epoch"] = time.time()
            try:
                guards[job_id] = OwnedProcessGuard.spawn(
                    [python, "-B", "-m", worker_module, "--config", str(root / "config.json")],
                    evidence_dir=root / "ownership", cwd=str(source), env=env,
                    stdout=streams[job_id], stderr=streams[job_id])
            except Exception as exc:
                record.update(status="launch_failed", error_type=type(exc).__name__)
                # spawn attempts its own cleanup, but returned no closure proof.
                # Never assume that an uncertain launch is safe for siblings.
                ownership_uncertain = True
                continue
            record["status"] = "loading"
            while remaining() > 0 and time.monotonic() - launch < load_timeout_seconds:
                if guards[job_id].poll() is not None:
                    record["status"] = "exited_before_ready"
                    break
                if (root / "ready.json").exists():
                    try:
                        receipt = _read_json(root / "ready.json")
                        if receipt.get("job_id") != job_id or receipt.get("ready") is not True:
                            raise ValueError("ready receipt not bound to this job")
                        record["ready_receipt"] = receipt
                        record["load_wall_seconds"] = time.monotonic() - launch
                        record["status"] = "ready"
                        ready.append(job_id)
                    except (ValueError, OSError) as exc:
                        record.update(status="invalid_ready", error_type=type(exc).__name__)
                    break
                time.sleep(min(poll_seconds, max(0, remaining())))
            if record["status"] == "loading":
                record["status"] = "deadline_during_load" if remaining() <= 0 else "load_timeout"
                timed_out = timed_out or remaining() <= 0
            if record["status"] != "ready":
                try:
                    close_job(job_id, force=True)
                except Exception as exc:
                    ownership_uncertain = True
                    record.update(status="closure_failed", closure_verified=False,
                                  closure_error_type=type(exc).__name__)
        # A worker that exits before release cannot count as completed, even
        # if it left a plausible success receipt. The barrier is mandatory.
        for job_id in list(ready):
            if guards[job_id].poll() is not None:
                ready.remove(job_id)
                records[job_id]["status"] = "exited_before_release"
        if ownership_uncertain:
            for job_id in ready:
                records[job_id]["status"] = "ownership_blocked"
        elif remaining() > finalization_reserve_seconds and ready:
            released_at = time.monotonic()
            release_epoch = time.time()
            for job_id in ready:
                _write_json(output / job_id / "release.json",
                            {"job_id": job_id, "released": True, "release_epoch": release_epoch})
                records[job_id]["status"] = "running"
            active = set(ready)
            while active and remaining() > 0:
                for job_id in tuple(active):
                    if guards[job_id].poll() is not None:
                        active.remove(job_id)
                        records[job_id]["status"] = "exited"
                if active:
                    time.sleep(min(poll_seconds, max(0, remaining())))
            if active:
                timed_out = True
                for job_id in active:
                    records[job_id]["status"] = "deadline_during_work"
        elif ready:
            timed_out = True
            for job_id in ready:
                records[job_id]["status"] = "deadline_before_release"
    finally:
        # Catch interrupts and ordinary exceptions too: no owned live process
        # is intentionally left behind for an evaluator or a later wave.
        for job_id, guard in guards.items():
            try:
                close_job(job_id)
            except Exception as exc:
                ownership_uncertain = True
                records[job_id].update(status="closure_failed", closure_verified=False,
                                       closure_error_type=type(exc).__name__)
        for stream in streams.values():
            stream.close()
    for job_id, record in records.items():
        result_path = output / job_id / "result.json"
        if result_path.exists():
            try:
                result = _read_json(result_path)
                record["result"] = result
                if result.get("job_id") != job_id or any(
                        key in configs[job_id] and result.get(key) != configs[job_id][key] for key in IDENTITIES):
                    raise ValueError("result identity differs")
                proof = record["closure"]
                if (record["status"] == "exited" and result.get("completed") is True
                        and record["closure_verified"] and proof["worker_returncode"] == 0
                        and proof["returncode"] == 0 and not proof["forced"]):
                    record["status"] = "completed"
                elif record["status"] == "exited":
                    record["status"] = "worker_failed"
            except (ValueError, OSError) as exc:
                # Retain raw result.json for diagnosis, never expose a rejected
                # object as consumable scientific evidence to the coordinator.
                record.update(status="invalid_result", result=None, result_error_type=type(exc).__name__)
        elif record["status"] == "exited":
            record["status"] = "missing_result"
    finished = time.monotonic()
    wall = finished - started
    receipt = {"measured": True, "completed": len(records) == len(configs) and all(
                    row["status"] == "completed" for row in records.values()),
               "concurrency": len(configs), "started_epoch": epoch_started,
               "deadline_epoch": deadline_epoch, "deadline_reached": timed_out,
               "supervisor_work_deadline_epoch": work_deadline_epoch,
               "worker_deadline_epoch": worker_deadline_epoch,
               "closure_reserve_seconds": closure_reserve,
               "finalization_reserve_seconds": finalization_reserve_seconds,
               "ownership_uncertain": ownership_uncertain,
               "wall_seconds": wall,
               "cold_startup_seconds": wall if released_at is None else released_at - started,
               "active_seconds": 0 if released_at is None else finished - released_at,
               "jobs": list(records.values()),
               "failures": [job_id for job_id, row in records.items() if row["status"] != "completed"]}
    _write_json(output / "wave.json", receipt)
    return receipt

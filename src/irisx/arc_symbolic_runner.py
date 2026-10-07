"""Hard-wall, hard-address-space Linux worker for the closed CPU DSL.

The evaluator has no IO operators. Bootstrap reads code, then the only worker
IO is one truth-free task/config on stdin and one result on stdout. No arbitrary
source, plugin, model, solution library or program code is loaded.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from .arc_symbolic_dsl import Limits, SOLVER_ID, search, validate_task
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


def _failure(task: dict, limits: Limits, status: str, elapsed: float) -> dict:
    return {"format": "irisx/arc-dsl-worker-v1", "status": status,
            "solver_id": SOLVER_ID, "task_digest": digest_value(task),
            "config_digest": digest_value(asdict(limits)), "limits": asdict(limits), "result": None,
            "parent_wall_seconds": elapsed, "peak_rss_bytes": None,
            "memory_enforcement": "linux-RLIMIT_AS", "correctness_scored": False}


def solve_isolated(task: object, limits: Limits = Limits()) -> dict:
    """One process per task; no partial candidates survive timeout or fault.

    RLIMIT_AS bounds virtual address space and therefore resident memory. It
    is not an RSS measurement. Parent wall includes startup and output transfer;
    forced termination adds measured cleanup overhead after the solve cutoff.
    Non-Linux platforms fail closed rather than promise an unenforced cap.
    """
    start = time.monotonic()
    limits.validate()
    task = validate_task(task)
    if not sys.platform.startswith("linux"):
        return _failure(task, limits, "unsupported_memory_enforcement", time.monotonic() - start)
    body = canonical_bytes({"task": task, "limits": asdict(limits)})
    environment = os.environ.copy()
    # Always this reviewed package, independent of the caller's cwd/import path.
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    environment.update(PYTHONHASHSEED="0", CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1",
                       TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1")
    try:
        process = subprocess.Popen([sys.executable, "-m", "irisx.arc_symbolic_runner", "--worker"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env=environment)
    except OSError:
        return _failure(task, limits, "worker_fault", time.monotonic() - start)
    try:
        remaining = max(0.000001, limits.wall_seconds - (time.monotonic() - start))
        output, _ = process.communicate(body, timeout=remaining)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=1)
        return _failure(task, limits, "wall_limit", time.monotonic() - start)
    finally:
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
    elapsed = time.monotonic() - start
    if elapsed >= limits.wall_seconds:
        return _failure(task, limits, "wall_limit", elapsed)
    if process.returncode:
        return _failure(task, limits, "worker_fault", elapsed)
    try:
        result = json.loads(output)
        if (set(result) != {"result", "peak_rss_bytes", "status"} or
                result["status"] not in {"complete", "memory_limit", "worker_fault"}):
            raise ValueError("invalid worker envelope")
        if result["status"] != "complete":
            return _failure(task, limits, result["status"], elapsed)
        value = result["result"]
        if (value["task_digest"] != digest_value(task) or
                value["config_digest"] != digest_value(asdict(limits)) or
                value["states"] > limits.max_states or value["correctness_scored"] is not False):
            raise ValueError("worker identity differs")
        if value["stop_reason"] == "wall_limit":
            return _failure(task, limits, "wall_limit", elapsed)
        return {"format": "irisx/arc-dsl-worker-v1", "status": "complete",
                "solver_id": SOLVER_ID, "task_digest": value["task_digest"],
                "config_digest": value["config_digest"], "limits": asdict(limits), "result": value,
                "parent_wall_seconds": elapsed, "peak_rss_bytes": result["peak_rss_bytes"],
                "memory_enforcement": "linux-RLIMIT_AS", "correctness_scored": False}
    except (ValueError, TypeError, KeyError):
        return _failure(task, limits, "worker_fault", elapsed)


def _worker() -> None:
    import resource

    try:
        value = json.load(sys.stdin)
        if set(value) != {"task", "limits"}:
            raise ValidationError("worker input schema differs")
        limits = Limits(**value["limits"])
        limits.validate()
        # Lowering RLIMIT_AS does not reclaim existing bootstrap mappings.
        # Fail before search if they (or historical bootstrap RSS) already
        # exceed the requested cap, rather than certify an unenforced tiny cap.
        mapped = int(Path("/proc/self/statm").read_text().split()[0]) * os.sysconf("SC_PAGE_SIZE")
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        if max(mapped, peak) > limits.address_space_bytes:
            raise MemoryError("bootstrap exceeds configured address-space cap")
        resource.setrlimit(resource.RLIMIT_AS, (limits.address_space_bytes, limits.address_space_bytes))
        cpu_limit = max(1, math.ceil(limits.wall_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        result = search(value["task"], limits)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        response = {"result": result, "peak_rss_bytes": peak, "status": "complete"}
    except MemoryError:
        response = {"result": None, "peak_rss_bytes": None, "status": "memory_limit"}
    except Exception:
        response = {"result": None, "peak_rss_bytes": None, "status": "worker_fault"}
    sys.stdout.buffer.write(canonical_bytes(response))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("only --worker is supported; use tools/run_arc_symbolic.py")
    _worker()

"""Independent hard watchdog for preprocessing, model ownership, and closure.

The inner controller owns detailed records. This small outer process never reads
challenge/model bytes. Its original clock is passed unchanged to the controller.
An expired/stuck inner controller cannot issue a valid outer completion receipt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from tools.public_sft141_submission import contract as wire
from tools.public_sft141_submission import files
from . import core
from .controller import Ownership, safe_cleanup, process_table, subreaper


def _drain(stream, buffer):
    for _ in range(16):
        try:
            chunk = os.read(stream.fileno(), 65536)
        except BlockingIOError:
            return
        if not chunk:
            return
        if len(buffer) < 1024 * 1024:
            buffer.extend(chunk[:1024 * 1024 - len(buffer)])


def supervised_run(challenge_path, model_dir, run_dir, output_dir, *, budget_seconds=7200.,
                   fallback="fail", _test_worker_prefix=None, _test_controller_prefix=None):
    start, epoch = time.monotonic(), time.time()
    deadline = core.SharedDeadline(start, budget_seconds)
    if sys.platform != "linux":
        raise ValueError("hard watchdog requires Linux process ownership")
    request = {"challenge_path": os.fspath(challenge_path), "model_dir": os.fspath(model_dir),
               "run_dir": os.fspath(run_dir), "output_dir": os.fspath(output_dir),
               "budget_seconds": budget_seconds, "fallback": fallback,
               "_original_clock": [start, epoch], "_test_worker_prefix": _test_worker_prefix}
    # No production CLI exposes either injection seam or an original-clock override.
    command = list(_test_controller_prefix or [sys.executable, "-m", "tools.public_sft141_solver.controller"])
    command += ["--request-json", json.dumps(request, allow_nan=False)]
    proc = ownership = cleanup = None
    signals, old_handlers, buffer = [], {}, bytearray()
    previous_subreaper = None
    reason = "inner-controller-exited"
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, lambda signum, frame: signals.append(signum))
        previous_subreaper = subreaper(True)
        baseline = {(pid, row["start_ticks"]) for pid, row in process_table().items() if row["ppid"] == os.getpid()}
        proc = subprocess.Popen(command, cwd=core.ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        os.set_blocking(proc.stdout.fileno(), False)
        ownership = Ownership(proc.pid, baseline)
        while proc.poll() is None:
            ownership.update()
            _drain(proc.stdout, buffer)
            if signals:
                reason = "outer-controller-interrupted"
                break
            if deadline.remaining() <= 0:
                reason = "original-whole-deadline"
                break
            time.sleep(min(.02, deadline.remaining()))
    finally:
        if proc is not None:
            # At most the bounded TERM/KILL cleanup tail after a hard failure;
            # it is not a restarted clock and cannot yield a completed run.
            cleanup = safe_cleanup(proc, deadline, ownership, baseline)
            _drain(proc.stdout, buffer)
            proc.stdout.close()
        if previous_subreaper is not None:
            subreaper(previous_subreaper)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    if reason != "inner-controller-exited" or deadline.remaining() <= 0:
        raise TimeoutError(f"{reason}: original whole clock/interrupt stopped inner controller; no outer completion. Cleanup complete={bool(cleanup and cleanup['complete'])}")
    if not cleanup["complete"]:
        raise RuntimeError("owned/unattributed descendants remain; no outer completion receipt")
    if proc.returncode != 0:
        diagnostic = buffer.decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"inner controller exited {proc.returncode}; {diagnostic.strip()}")
    try:
        result = files.decode_json(bytes(buffer).strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise RuntimeError("inner controller did not return a valid completion result") from exc
    if result.get("whole_budget_met") is not True or result.get("format_complete") is not True:
        raise RuntimeError("inner controller did not establish an in-budget format-complete bundle")
    receipt = {"schema": core.SCHEMA, "original_start_monotonic": start, "budget_seconds": budget_seconds,
               "elapsed_seconds": time.monotonic() - start, "cleanup": cleanup,
               "submission_sha256": result["submission_sha256"], "closure_sha256": result["closure_sha256"],
               "source_sha256": result["source_sha256"], "original_whole_clock_met": True,
               "hard_watchdog": "independent-process-controller-watchdog-v1", "readback_verified": False}
    # The outer process has only one small final publication/readback; a real
    # interval timer also interrupts that operation instead of merely measuring it.
    old_alarm = signal.getsignal(signal.SIGALRM)
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    def expired(signum, frame):
        raise TimeoutError("original whole deadline during final watchdog receipt")
    try:
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, max(.000001, deadline.remaining()))
        root = files.safe_path(run_dir)
        target = root / "outer_precommit.json"
        core.publish(target, receipt)
        if files.read_bytes(target) != wire.canonical(receipt):
            raise ValueError("outer precommit readback mismatch")
        if deadline.remaining() <= 0:
            raise TimeoutError("original whole deadline after watchdog precommit readback")
        committed = {**receipt, "readback_verified": True,
                     "precommit_sha256": wire.digest(wire.canonical(receipt)),
                     "elapsed_seconds": time.monotonic() - start}
        # Final marker comes only AFTER actual precommit readback. Its byte
        # identity is independently checked by verify; no self-certifying read.
        core.publish(root / "outer_completion.json", committed)
        if deadline.remaining() <= 0:
            raise TimeoutError("original whole deadline after watchdog commit")
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, .1)
        try:
            core.publish(files.safe_path(run_dir) / "outer_failure.json", {
                "error": type(exc).__name__, "original_start_monotonic": start,
                "budget_seconds": budget_seconds, "elapsed_seconds": time.monotonic() - start,
                "completed_run": False})
        except BaseException:
            pass  # No completion marker is created before precommit readback.
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, old_alarm)
    result.update(hard_watchdog_complete=True, elapsed_seconds=time.monotonic() - start)
    return result

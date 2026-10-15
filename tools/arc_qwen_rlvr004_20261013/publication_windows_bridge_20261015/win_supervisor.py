"""Independent native Job owner. Binary stdio relay; no payload interpretation.

The worker is disposable and cannot inherit the Job handle. The supervisor keeps
its own deadline and parent/EOF watch, outside the SDK process and its GIL. A
successful exit requires a queried empty Job. Only fixed safe diagnostics leave
this module; arbitrary worker stderr is discarded, bounded, and never logged.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

# -I can be used without enabling arbitrary current-directory imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from win_runtime import (ExclusiveMutex, JobProcess, ParentWatch, WindowsGuardError,
                         bounded_seconds, need)

MAX_STREAM_BYTES = 64 * 1024 * 1024
MAX_STDERR_BYTES = 1024 * 1024


@dataclass(frozen=True)
class SupervisionResult:
    code: int
    reason: str
    closure: dict


def remaining_timeout(timeout, deadline_unix, now=None):
    timeout = bounded_seconds(timeout)
    need(type(deadline_unix) in (int, float) and math.isfinite(deadline_unix), 'windows_invalid_deadline')
    remaining = float(deadline_unix) - (time.time() if now is None else now)
    need(0 < remaining <= 43200, 'windows_deadline_expired_or_outside_bound')
    return min(timeout, remaining)


def supervise(argv, *, timeout_seconds, deadline_unix, parent_pid=None,
              scope='publication-worker-v1', input_fd=0, output_fd=1, env=None):
    """Return only after job-empty proof; stdin must stay open for worker lifetime.

    Deadline-unix is the original reviewed session deadline, not now+fresh budget.
    This API does not approve the worker arguments; the caller binds their source
    and bootstrap configuration. Native CLI takes only its caller's explicit argv.
    """
    duration = remaining_timeout(timeout_seconds, deadline_unix)
    deadline = time.monotonic() + duration
    stop = threading.Event(); output_done = threading.Event(); stderr_done = threading.Event()
    cause = []; cause_lock = threading.Lock()
    def fail(reason):
        with cause_lock:
            if not cause:
                cause.append(reason)
        stop.set()

    with ExclusiveMutex(scope), ParentWatch(parent_pid) as parent:
        job = JobProcess(argv, env=env)
        def input_relay():
            total = 0
            try:
                while not stop.is_set():
                    data = os.read(input_fd, 65536)
                    if not data:
                        fail('caller_pipe_eof'); return
                    total += len(data)
                    if total > MAX_STREAM_BYTES:
                        fail('input_limit'); return
                    job.stdin.write(data)
            except (OSError, WindowsGuardError):
                fail('caller_pipe_error')

        def output_relay():
            total = 0
            try:
                while True:
                    data = job.stdout.read()
                    if not data:
                        return
                    total += len(data)
                    if total > MAX_STREAM_BYTES:
                        fail('output_limit'); return
                    offset = 0
                    while offset < len(data):
                        written = os.write(output_fd, data[offset:])
                        if written <= 0:
                            fail('output_pipe_error'); return
                        offset += written
            except (OSError, WindowsGuardError):
                fail('output_pipe_error')
            finally:
                output_done.set()

        def stderr_sink():
            total = 0
            try:
                while True:
                    data = job.stderr.read()
                    if not data:
                        return
                    total += len(data)
                    if total > MAX_STDERR_BYTES:
                        fail('worker_stderr_limit'); return
            except (OSError, WindowsGuardError):
                fail('worker_stderr_pipe_error')
            finally:
                stderr_done.set()

        for fn in (input_relay, output_relay, stderr_sink):
            threading.Thread(target=fn, daemon=True).start()
        worker_code = None
        reason = 'supervisor_error'
        try:
            while True:
                if stop.is_set():
                    reason = cause[0]; break
                if time.monotonic() >= deadline:
                    reason = 'deadline'; break
                if parent.dead():
                    reason = 'parent_death'; break
                worker_code = job.poll()
                if worker_code is not None:
                    reason = 'worker_exit'; break
                stop.wait(min(0.02, max(0.0, deadline - time.monotonic())))
            stop.set()
            closure = job.terminate_and_prove_empty(close_pipes=False)
            # Drain bytes already written by the worker only within this same
            # deadline. Blocked consumer output cannot prolong the supervisor.
            drain_end = min(deadline, time.monotonic() + 2.0)
            while not (output_done.is_set() and stderr_done.is_set()):
                if time.monotonic() >= drain_end:
                    if reason == 'worker_exit':
                        reason = 'relay_drain_timeout'
                    break
                time.sleep(0.005)
            if cause and reason == 'worker_exit':
                reason = cause[0]
            code = 0 if reason == 'worker_exit' and worker_code == 0 else 124
            return SupervisionResult(code, reason, closure)
        finally:
            stop.set()
            if job.job:
                job.terminate_and_prove_empty()
            job._close_handles()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bounded Windows bridge Job owner')
    parser.add_argument('--timeout-seconds', type=float, required=True)
    parser.add_argument('--deadline-unix', type=float, required=True)
    parser.add_argument('worker', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.worker[1:] if args.worker[:1] == ['--'] else args.worker
    try:
        need(os.name == 'nt', 'native_windows_required')
        import msvcrt
        msvcrt.setmode(0, os.O_BINARY); msvcrt.setmode(1, os.O_BINARY); msvcrt.setmode(2, os.O_BINARY)
        need(bool(command), 'windows_worker_missing')
        result = supervise(command, timeout_seconds=args.timeout_seconds, deadline_unix=args.deadline_unix)
        receipt = {'format': 'irisx/windows-supervisor-result-v1', 'reason': result.reason,
                   'closure': result.closure, 'ok': result.code == 0}
        os.write(2, (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
        return result.code
    except WindowsGuardError as exc:
        # Exception codes originate only in this module/runtime, never SDK text.
        os.write(2, (json.dumps({'format': 'irisx/windows-supervisor-result-v1',
            'ok': False, 'reason': str(exc)}, separators=(',', ':')) + '\n').encode('ascii'))
        return 125
    except BaseException:
        os.write(2, b'{"format":"irisx/windows-supervisor-result-v1","ok":false,"reason":"supervisor_internal_error"}\n')
        return 125


if __name__ == '__main__':
    # Daemon relay threads may still block on a dead caller's inherited handles;
    # avoid Python buffered-stdio shutdown and never wait beyond the deadline.
    os._exit(main())

"""Deadline-authoritative outer supervision of one owned process group.

The child owns model workers with parent-death guards. No blocking stdout read
or unbounded wait is used. A hard kill is requested before the absolute cap;
unconfirmed exit remains failure, never a claim of physical GPU preemption.
"""
import os
import signal
import subprocess
import time


def supervise(command, *, env, cwd, started, total_seconds, cleanup_seconds,
              now=time.monotonic, pause=time.sleep, launch=subprocess.Popen,
              capture_path=None, maximum_capture_bytes=64*1024):
    if capture_path is not None and (type(maximum_capture_bytes) is not int or not 0 < maximum_capture_bytes <= 1024*1024):
        raise ValueError('bounded coordinator output capture required')
    hard = started+total_seconds
    soft = hard-cleanup_seconds
    if now() >= soft:
        return {'returncode': None, 'timed_out': True, 'launched': False,
                'confirmed_stopped': True, 'reason': 'startup exhausted whole-session work allowance'}
    # Default callers retain the original no-pipe behavior. Probe capture drains
    # a nonblocking byte pipe with a finite per-poll quantum and retains a tail;
    # it never reads lines or writes to a potentially blocked notebook console.
    process = launch(command, env=env, cwd=cwd, stdout=subprocess.DEVNULL if capture_path is None else subprocess.PIPE,
                     stderr=subprocess.STDOUT, start_new_session=True)
    tail = bytearray(); received = 0; result = None
    def drain():
        nonlocal received
        if capture_path is None:
            return
        for _ in range(4):
            try:
                block = os.read(process.stdout.fileno(), 65536)
            except BlockingIOError:
                break
            if not block:
                break
            received += len(block); tail.extend(block)
            if len(tail) > maximum_capture_bytes:
                del tail[:-maximum_capture_bytes]
    timed_out = False; terminated = False; killed = False
    try:
        if capture_path is not None:
            os.set_blocking(process.stdout.fileno(), False)
        while process.poll() is None:
            stamp = now()
            if stamp >= soft and not terminated:
                timed_out = terminated = True
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            # Reserve a final poll interval rather than waiting past the cap.
            if stamp >= hard-.2 and not killed:
                timed_out = killed = True
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            if stamp >= hard: break
            drain()
            pause(min(.05, max(0, hard-stamp)))
        code = process.poll()
        drain()
        result = {'returncode': code, 'timed_out': timed_out, 'launched': True,
                  'confirmed_stopped': code is not None, 'hard_deadline_monotonic': hard}
        return result
    finally:
        if process.poll() is None and not killed:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        if capture_path is not None:
            process.stdout.close()
            capture = {'bytes_received': received, 'bytes_retained': len(tail),
                       'truncated': received > len(tail), 'written': False}
            try:
                with open(capture_path, 'xb') as stream:
                    stream.write(tail); stream.flush(); os.fsync(stream.fileno())
                capture['written'] = True
            except BaseException as error:
                capture['error'] = type(error).__name__ + ': ' + str(error)[:500]
            if result is not None:
                result['output_capture'] = capture

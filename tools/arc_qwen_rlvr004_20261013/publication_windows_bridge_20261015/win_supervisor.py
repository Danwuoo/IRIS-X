"""Independent native Job owner. Binary stdio relay; no payload interpretation.

The worker is disposable and cannot inherit the Job handle. The supervisor keeps
its own deadline and parent/EOF watch, outside the SDK process and its GIL. A
successful exit requires a queried empty Job. Only fixed safe diagnostics leave
this module; arbitrary worker stderr is discarded, bounded, and never logged.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import re
import stat
import types
import math
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

# These two pins are updated only by the reviewed source integration. No sibling
# module is imported or executed before its bytes match its bootstrap pin.
WIN_RUNTIME_SHA256 = 'ae56db730ab84a8fa83c6439d5b6d0c537e0c348d0e93ea3b5618362e7e6f41e'
NATIVE_CONFIG_SHA256 = 'fe2ec44a37e8895077162a3369d859967001e5a50f4294d2d8e0fb954fa35282'
MAX_STREAM_BYTES = 32 * 1024 * 1024 * 1024
MAX_STDERR_BYTES = 1024 * 1024


def _install_runtime(module):
    for name in ('ExclusiveMutex', 'JobProcess', 'ParentWatch', 'WindowsGuardError',
                 'bounded_seconds', 'need'):
        globals()[name] = getattr(module, name)


# Test-only import callers load the runtime explicitly first. Production runs
# this file as __main__ under -I -B and reaches only the pinned bootstrap below.
if __name__ != '__main__' and 'win_runtime' in sys.modules:
    _install_runtime(sys.modules['win_runtime'])


def _pinned_module(name, path, digest):
    if not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None:
        raise RuntimeError('supervisor_bootstrap_unbound')
    path = Path(path).absolute()
    for component in reversed((path, *path.parents)):
        info = component.lstat()
        if getattr(info, 'st_file_attributes', 0) & 0x400 or stat.S_ISLNK(info.st_mode):
            raise RuntimeError('supervisor_bootstrap_reparse')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= 1024 * 1024:
        raise RuntimeError('supervisor_bootstrap_file')
    with path.open('rb') as source:
        raw = source.read(1024 * 1024 + 1)
    if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError('supervisor_bootstrap_hash')
    module = types.ModuleType(name); module.__file__ = str(path); module.__package__ = ''
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


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


class CommandWatch:
    """Supervisor-owned lease, operation and official-RPC clocks.

    Only strict non-secret control DTOs are observed. Opaque content is bounded
    by FrameObserver and discarded from its inspection state, never logged.
    """
    def __init__(self, protocol, nonce, *, lease_epoch, lease_monotonic,
                 monotonic=time.monotonic, wall=time.time):
        self.protocol = protocol
        self.request = protocol.FrameObserver(nonce, direction='request')
        self.response = protocol.FrameObserver(nonce, direction='response')
        self.sequence = protocol.SequenceGuard()
        self.lease_epoch = lease_epoch; self.lease_deadline = lease_monotonic
        self.monotonic = monotonic; self.wall = wall
        self.command_deadline = self.phase_deadline = None
        self.phase_id = None; self.last_phase = 0; self.operation = None
        self.lock = threading.Lock()

    def _expired(self):
        now = self.monotonic()
        if now >= self.lease_deadline:
            return 'deadline'
        if self.command_deadline is not None and now >= self.command_deadline:
            return 'operation_deadline'
        if self.phase_deadline is not None and now >= self.phase_deadline:
            return 'official_rpc_deadline'
        return None

    def expired(self):
        with self.lock:
            return self._expired()

    def observe(self, direction, data):
        observer = self.request if direction == 'request' else self.response
        # One dedicated relay thread per direction owns each frame parser.
        controls = observer.feed(data)
        with self.lock:
            need(self._expired() is None, 'windows_observed_deadline_expired')
            for envelope in controls:
                kind = envelope['kind']; payload = envelope['payload']
                binding = (envelope['sequence'], envelope['request_sha256'])
                if direction == 'request' and kind == 'request':
                    payload = self.sequence.accept(envelope)
                    operation = payload['operation']
                    need((envelope['sequence'] == 1) == (operation == 'open'), 'windows_open_sequence')
                    need(payload['deadline_epoch'] <= self.lease_epoch
                         and 0 < payload['max_seconds'] <= self.protocol.OPERATION_TIMEOUTS[operation],
                         'windows_operation_bound')
                    seconds = min(payload['max_seconds'], payload['deadline_epoch'] - self.wall())
                    need(seconds > 0, 'windows_operation_expired')
                    self.command_deadline = min(self.lease_deadline, self.monotonic() + seconds)
                    self.operation = operation
                    continue
                need(self.sequence.active == binding, 'windows_control_binding')
                if kind == 'phase_start':
                    need(self.phase_id is None and payload['phase_id'] > self.last_phase,
                         'windows_rpc_phase_replay')
                    seconds = min(payload['max_seconds'], payload['deadline_epoch'] - self.wall())
                    need(seconds > 0 and self.command_deadline is not None, 'windows_rpc_phase_expired')
                    self.phase_deadline = min(self.command_deadline, self.monotonic() + seconds)
                    self.phase_id = self.last_phase = payload['phase_id']
                elif kind == 'phase_end':
                    need(payload['phase_id'] == self.phase_id, 'windows_rpc_phase_mismatch')
                    self.phase_deadline = self.phase_id = None
                elif direction == 'response' and kind in ('response', 'error'):
                    need(self.phase_id is None, 'windows_rpc_phase_unfinished')
                    if kind == 'response':
                        need(payload['operation'] == self.operation, 'windows_response_operation')
                    self.sequence.complete(*binding)
                    self.command_deadline = self.operation = None

    def finish(self, direction):
        (self.request if direction == 'request' else self.response).finish()

    def complete(self):
        with self.lock:
            need(self.sequence.active is None and self.phase_id is None, 'windows_worker_incomplete_command')


def supervise(argv, *, timeout_seconds, deadline_unix, parent_pid=None,
              scope='publication-worker-v1', input_fd=0, output_fd=1, env=None,
              protocol=None, nonce=None):
    """Return only after job-empty proof; stdin must stay open for worker lifetime.

    Deadline-unix is the original worker lease deadline, distinct from immutable
    experiment clocks. The production CLI binds worker source/arguments/config.
    Generic argv is an internal primitive used only by the offline native probe.
    """
    duration = remaining_timeout(timeout_seconds, deadline_unix)
    deadline = time.monotonic() + duration
    stop = threading.Event(); output_done = threading.Event(); stderr_done = threading.Event()
    watch = None if protocol is None else CommandWatch(protocol, nonce, lease_epoch=deadline_unix, lease_monotonic=deadline)
    cause = []; cause_lock = threading.Lock()
    def fail(reason):
        with cause_lock:
            if not cause:
                cause.append(reason)
        stop.set()

    with ExclusiveMutex(scope), ParentWatch(parent_pid) as parent:
        job = JobProcess(argv, env=env, job_nonce=nonce if protocol is not None else None)
        def input_relay():
            total = 0
            try:
                while not stop.is_set():
                    data = os.read(input_fd, 65536)
                    if not data:
                        if watch is not None:
                            watch.finish('request')
                        fail('caller_pipe_eof'); return
                    total += len(data)
                    if total > MAX_STREAM_BYTES:
                        fail('input_limit'); return
                    if watch is not None:
                        watch.observe('request', data)
                    job.stdin.write(data)
            except BaseException:
                fail('caller_pipe_or_protocol_error')

        def output_relay():
            total = 0
            try:
                while True:
                    data = job.stdout.read()
                    if not data:
                        if watch is not None:
                            watch.finish('response')
                        return
                    total += len(data)
                    if total > MAX_STREAM_BYTES:
                        fail('output_limit'); return
                    if watch is not None:
                        watch.observe('response', data)
                    offset = 0
                    while offset < len(data):
                        written = os.write(output_fd, data[offset:])
                        if written <= 0:
                            fail('output_pipe_error'); return
                        offset += written
            except BaseException:
                fail('output_pipe_or_protocol_error')
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
                if watch is not None and watch.expired() is not None:
                    reason = watch.expired(); break
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
            if watch is not None and reason == 'worker_exit':
                watch.complete()
            code = 0 if reason == 'worker_exit' and worker_code == 0 else 124
            return SupervisionResult(code, reason, closure)
        finally:
            stop.set()
            if job.job:
                job.terminate_and_prove_empty()
            job._close_handles()


def main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha', required=True)
    parser.add_argument('--nonce', required=True)
    parser.add_argument('--deadline-epoch', type=float, required=True)
    parser.add_argument('--max-seconds', type=float, required=True)
    args = parser.parse_args(argv)
    receipt = {'format': 'irisx/windows-supervisor-result-v1', 'nonce': args.nonce,
               'ok': False, 'reason': 'supervisor_bootstrap_failed', 'closure': None}
    try:
        if (os.name != 'nt' or sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1
                or sys.flags.ignore_environment != 1):
            raise RuntimeError('native_isolated_windows_required')
        if re.fullmatch('[0-9a-f]{64}', args.nonce) is None or re.fullmatch('[0-9a-f]{64}', args.config_sha) is None:
            raise RuntimeError('supervisor_binding_invalid')
        import msvcrt
        for fd in (0, 1, 2):
            msvcrt.setmode(fd, os.O_BINARY)
        directory = Path(__file__).absolute().parent
        win = _pinned_module('win_runtime', directory / 'win_runtime.py', WIN_RUNTIME_SHA256)
        _install_runtime(win)
        # Capture the absolute monotonic lease before any expensive verification.
        budget = remaining_timeout(args.max_seconds, args.deadline_epoch)
        lease_deadline = started + budget
        config = _pinned_module('native_config', directory / 'native_config.py', NATIVE_CONFIG_SHA256)
        runtime = config.load_runtime(args.config, args.config_sha, supervisor=True)
        need(config.same_path(str(directory), runtime.source_root), 'windows_supervisor_source_identity')
        descriptor = runtime.document['sources']['protocol.py']
        protocol = _pinned_module('protocol', directory / 'protocol.py', descriptor['sha256'])
        command = [runtime.executable, '-I', '-B', str(runtime.worker_path),
                   '--config', args.config, '--config-sha', args.config_sha, '--nonce', args.nonce,
                   '--deadline-epoch', str(args.deadline_epoch), '--max-seconds', str(args.max_seconds)]
        remaining = lease_deadline - time.monotonic()
        need(remaining > 0, 'windows_bootstrap_deadline')
        result = supervise(command, timeout_seconds=remaining, deadline_unix=args.deadline_epoch,
                           protocol=protocol, nonce=args.nonce)
        receipt.update(reason=result.reason, closure=result.closure, ok=result.code == 0)
        code = result.code
    except BaseException:
        # Never echo native config, worker/SDK exception text, paths, or payloads.
        code = 125
    os.write(2, (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii'))
    return code


if __name__ == '__main__':
    # Daemon relay threads may still block on a dead caller's inherited handles;
    # avoid Python buffered-stdio shutdown and never wait beyond the deadline.
    os._exit(main())

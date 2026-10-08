"""Bounded CPU/file resource observations; never GPU or quality qualification."""
from __future__ import annotations
from contextlib import contextmanager
import os
from pathlib import Path
import resource
import select
import signal
import subprocess
import sys
import threading
import time

from tools.nvarc_native_multitask import require


def rss_bytes(usage):
    return usage.ru_maxrss if sys.platform == 'darwin' else usage.ru_maxrss*1024


class ResourceObserver:
    """Sample process-visible file sizes; report limits and missed observations."""
    def __init__(self, root, *, sample_seconds=1.0, maximum_files=30000, now=time.monotonic):
        require(type(sample_seconds) in (int, float) and sample_seconds >= .1 and
                type(maximum_files) is int and maximum_files > 0, 'bounded resource sampling required')
        self.root, self.sample_seconds, self.maximum_files, self.now = Path(root), sample_seconds, maximum_files, now
        self.phases, self.errors, self.samples = {}, [], 0
        self.logical_peak, self.allocated_peak = None, None
        self.stop = threading.Event(); self.thread = None

    def sample(self):
        try:
            logical, allocated, count = 0, 0, 0
            for entries, path in enumerate(self.root.rglob('*'), 1):
                if entries > self.maximum_files*2: raise RuntimeError('resource sample entry cap exceeded')
                if path.is_symlink(): raise RuntimeError('resource sample does not follow symlinks')
                try: stat = path.stat()
                except FileNotFoundError: continue  # transient atomic projection temp
                if path.is_file():
                    count += 1
                    if count > self.maximum_files: raise RuntimeError('resource sample file cap exceeded')
                    logical += stat.st_size
                    allocated += getattr(stat, 'st_blocks', 0)*512
            self.logical_peak = max(self.logical_peak or 0, logical)
            self.allocated_peak = max(self.allocated_peak or 0, allocated)
            self.samples += 1
        except BaseException as error:
            if len(self.errors) < 10: self.errors.append({'type': type(error).__name__, 'message': str(error)[:500]})

    def start(self):
        self.sample()
        def monitor():
            while not self.stop.wait(self.sample_seconds): self.sample()
        self.thread = threading.Thread(target=monitor, daemon=True); self.thread.start()
        return self

    @contextmanager
    def phase(self, name):
        begin = self.now()
        try: yield
        finally:
            self.phases[name] = {'wall_seconds': self.now()-begin, 'process_peak_rss_bytes': rss_bytes(resource.getrusage(resource.RUSAGE_SELF))}
            self.sample()

    def close(self):
        self.stop.set()
        if self.thread is not None: self.thread.join(timeout=2)
        self.sample()
        return self.report()

    def report(self):
        return {'format': 'irisx/stage4-resource-observations-v1', 'phases': dict(self.phases),
            'sampled_file_logical_peak_bytes': self.logical_peak,
            'sampled_file_allocated_peak_bytes': self.allocated_peak,
            'disk_scope': str(self.root), 'disk_samples': self.samples, 'disk_sample_interval_seconds': self.sample_seconds,
            'disk_errors': list(self.errors), 'disk_sampler_stopped': self.thread is None or not self.thread.is_alive(),
            'disk_peak_is_sampled': True, 'unsampled_disk_peak_attested': False,
            'disk_maximum_files_per_sample': self.maximum_files, 'disk_maximum_entries_per_sample': self.maximum_files*2,
            'disk_symlink_policy': 'never follow; sample error if encountered',
            'disk_sampling_limits': 'transient files/IO blocking may be missed; scan errors are retained',
            'gpu_timing_attestation': False, 'recovery_measurement': 'not run in this successful-execution path',
            'resource_qualification': False}


def run_observed(command, *, env, cwd, stdout, stderr, timeout, launch=subprocess.Popen,
                 now=time.monotonic, pause=time.sleep, wait4=getattr(os, 'wait4', None), cleanup_seconds=5):
    """One owned child, exact wait4 RSS when available, finite execution/stop clock.

    No model/device call, synchronization, stdout pipe or unrelated child wait.
    A missing or unconfirmed observation remains null; it is never numeric zero.
    """
    require(type(timeout) in (int, float) and timeout > cleanup_seconds and cleanup_seconds > 0,
            'export work/cleanup must fit a finite process clock')
    started = now(); hard = started+timeout; soft = hard-cleanup_seconds
    timed_out = False; code, usage, process, pidfd = None, None, None, None
    confirmed_stop = False; stop_attempted = False; owner_verified = False
    errors = []; observation_lost = False
    def failure(error, phase):
        errors.append({'phase': phase, 'type': type(error).__name__, 'message': str(error)[:500]})
    try:
        try:
            process = launch(command, env=env, cwd=cwd, stdout=stdout, stderr=stderr, start_new_session=False)
        except BaseException as error:
            failure(error, 'child-launch')
        if process is not None:
            try:
                owner = next(line for line in Path('/proc/'+str(process.pid)+'/status').read_text().splitlines() if line.startswith('PPid:'))
                require(int(owner.split()[1]) == os.getpid(), 'resource observer child ownership differs')
                owner_verified = True
                if hasattr(os, 'pidfd_open'): pidfd = os.pidfd_open(process.pid)
            except BaseException as error: failure(error, 'owned-child-pidfd')
            while now() < hard:
                if wait4 is not None:
                    try: pid, status, measured = wait4(process.pid, os.WNOHANG)
                    except ChildProcessError as error:
                        # poll() treats ECHILD as zero on some platforms. Never
                        # manufacture success after losing the owned exit receipt.
                        failure(error, 'owned-child-wait4'); observation_lost = True; break
                    except BaseException as error:
                        failure(error, 'owned-child-wait4'); wait4 = None; continue
                    if pid:
                        code = os.waitstatus_to_exitcode(status); usage = measured; process.returncode = code; confirmed_stop = True
                        break
                else:
                    try: pid, status = os.waitpid(process.pid, os.WNOHANG)
                    except ChildProcessError as error:
                        failure(error, 'owned-child-waitpid'); observation_lost = True; break
                    if pid:
                        code = os.waitstatus_to_exitcode(status); process.returncode = code; confirmed_stop = True
                        break
                if now() >= soft and not timed_out:
                    timed_out = True
                    stop_attempted = True
                    try:
                        if pidfd is not None and hasattr(signal, 'pidfd_send_signal'): signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        else:
                            require(owner_verified, 'owned child required before timeout signal')
                            os.kill(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    except BaseException as error: failure(error, 'child-timeout-stop')
                pause(min(.05, max(0, hard-now())))
    except BaseException as error:
        failure(error, 'child-observer')
    finally:
        if process is not None and code is None:
            timed_out = timed_out or now() >= soft; stop_attempted = True
            try:
                if pidfd is not None and hasattr(signal, 'pidfd_send_signal'):
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                else:
                    # On an exit-receipt loss, require current ownership before
                    # using a numeric PID. Never signal an unrelated/reused PID.
                    owner = next(line for line in Path('/proc/'+str(process.pid)+'/status').read_text().splitlines() if line.startswith('PPid:'))
                    require(int(owner.split()[1]) == os.getpid(), 'lost-receipt child ownership cannot be confirmed')
                    os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            except BaseException as error: failure(error, 'child-final-stop')
            while now() < hard and not confirmed_stop:
                if observation_lost and pidfd is None: break
                if pidfd is not None and select.select([pidfd], [], [], 0)[0]:
                    confirmed_stop = True; break
                if not observation_lost:
                    try:
                        found, status = os.waitpid(process.pid, os.WNOHANG)
                        if found: code = os.waitstatus_to_exitcode(status); process.returncode = code; confirmed_stop = True; break
                    except ChildProcessError: break
                pause(min(.02, max(0, hard-now())))
            if confirmed_stop and code is None:
                # Optional actual waitpid status may reap a live-child injected
                # wait4 fault; a real ECHILD still leaves returncode unknown.
                try:
                    found, status = os.waitpid(process.pid, os.WNOHANG)
                    if found: code = os.waitstatus_to_exitcode(status); process.returncode = code
                except ChildProcessError as error:
                    if not observation_lost: failure(error, 'owned-child-final-waitpid')
                    observation_lost = True
        if pidfd is not None: os.close(pidfd)
    return {'returncode': code, 'timed_out': timed_out, 'launched': process is not None,
        'confirmed_stopped': process is None or confirmed_stop, 'stop_attempted': stop_attempted,
        'child_session': 'inherits Stage4 parent process group; production CPU wrapper also has owner-death guard',
        'exit_observation_lost': observation_lost,
        'wall_seconds': now()-started, 'maximum_seconds': timeout, 'errors': errors,
        'child_peak_rss_bytes': None if usage is None else rss_bytes(usage),
        'child_peak_rss_method': 'owned-child wait4 RUSAGE' if usage is not None else 'unavailable',
        'cpu_user_seconds': None if usage is None else usage.ru_utime,
        'cpu_system_seconds': None if usage is None else usage.ru_stime,
        'gpu_calls_added': 0, 'device_synchronizations_added': 0}

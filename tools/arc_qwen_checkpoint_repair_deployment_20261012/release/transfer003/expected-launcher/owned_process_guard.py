"""Linux lifecycle proof for one trusted, exclusively owned subprocess tree.

Use ``OwnedProcessGuard.spawn(..., evidence_dir=...)`` for complete ownership.
A dedicated, model-free supervisor is a subreaper: double forks and setsid do
not leave its tree. The coordinator is also a process-local subreaper so that a
forced supervisor shutdown can reap *identified* adopted descendants. Neither
role changes a host setting or signals/reaps unrelated processes. All signals
and descendant waits use pidfds; /proc start times bind recorded incarnations.

This is lifecycle/dataflow isolation for trusted code, not an adversarial OS
sandbox. In particular it does not claim to survive arbitrary external SIGKILL
of every supervisor. Missing evidence fails closed. Import has no side effects.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

FORMAT = 'irisx/owned-process-closure-v1'
IDENTITY_KEYS = {'pid', 'birth', 'session', 'state'}
MAX_RECORD_BYTES = 4 * 1024 * 1024


def _read_process(pid):
    try:
        raw = (Path('/proc') / str(pid) / 'stat').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    fields = raw[raw.rfind(')') + 2:].split()
    return {'pid': pid, 'birth': int(fields[19]), 'session': int(fields[3]),
            'state': fields[0], 'parent': int(fields[1])}


def _identity(row):
    return {key: row[key] for key in ('pid', 'birth', 'session', 'state')}


def _key(row):
    return row['pid'], row['birth']


def _same(row, identity):
    return row is not None and _key(row) == _key(identity)


def _require_linux():
    if (sys.platform != 'linux' or not hasattr(os, 'pidfd_open')
            or not hasattr(signal, 'pidfd_send_signal') or not hasattr(os, 'P_PIDFD')):
        raise RuntimeError('Linux pidfd signaling and waiting required; no PID-only fallback')


def _prctl(option, value):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(ctypes.c_int(option), ctypes.c_ulong(value), 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def enable_subreaper():
    """Affects only this calling process; never reaps any child by itself."""
    _require_linux()
    _prctl(36, 1)  # PR_SET_CHILD_SUBREAPER


def arm_parent_death(expected_parent, death_signal=signal.SIGKILL):
    """Arm in the newly launched process, then close the parent-exit race."""
    _require_linux()
    _prctl(1, int(death_signal))  # PR_SET_PDEATHSIG
    if os.getppid() != expected_parent:
        os.kill(os.getpid(), death_signal)  # Only the current process.
        return False
    return True


def _write_record(path, value):
    path = Path(path)
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError('owned-process record exceeds bound')
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if path.exists():
        raise ValueError('owned-process evidence identity consumed')
    os.replace(temporary, path)


def _read_record(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError('owned-process record exceeds bound')
    return json.loads(raw)


def _child_pids(pid):
    """Parent edges from /proc stat; never inspect another process environment.

    Some Linux containers omit task/*/children, so stat PPIDs are the portable
    Linux source here. A discovered edge is rechecked before claiming ownership.
    """
    children = set()
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        row = _read_process(int(path.name))
        if row is not None and row['parent'] == pid:
            children.add(row['pid'])
    return children


class OwnedProcessGuard:
    """Track one Popen child; use spawn for a complete dedicated-tree proof.

    A guard around an arbitrary preexisting Popen can stop identified processes,
    but correctly reports ownership_complete=False: a preexisting orphan cannot
    be attributed safely from a later process-table snapshot.
    """
    def __init__(self, child, *, _scope=None, _evidence_dir=None):
        _require_linux()
        self.child = child
        row = _read_process(child.pid)
        if row is None or row['parent'] != os.getpid():
            raise RuntimeError('guard requires an unreaped direct child')
        self.identity = _identity(row)
        self._scope = _scope
        self._evidence_dir = None if _evidence_dir is None else Path(_evidence_dir)
        self._known = {}
        self._pidfds = {}
        self._reaped = set()
        self._errors = []
        self._forced = False
        self._persisted = False
        self._remember(row)
        self.poll()

    @classmethod
    def spawn(cls, argv, *, evidence_dir, **kwargs):
        """Launch the worker through a dedicated subreaper; preserve its argv/env.

        stdout/stderr/cwd/env pass through to the worker. The supervisor itself
        uses the caller's existing Python and only the standard library.
        """
        _require_linux()
        if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(x, str) for x in argv):
            raise ValueError('an explicit string argv is required')
        if kwargs.get('shell') or kwargs.get('preexec_fn') is not None or kwargs.get('pass_fds'):
            raise ValueError('shell, preexec_fn and inherited application fds are not supported')
        if kwargs.get('start_new_session', True) is not True or kwargs.get('close_fds', True) is not True:
            raise ValueError('dedicated session and closed file descriptors required')
        evidence = Path(evidence_dir).absolute()
        if any(p.is_symlink() for p in (evidence, *evidence.parents)):
            raise ValueError('symlink process evidence path forbidden')
        evidence.mkdir(parents=True, exist_ok=False)
        enable_subreaper()
        kwargs['start_new_session'] = True
        kwargs['close_fds'] = True
        command = [sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve()),
                   '--supervise', str(os.getpid()), str(evidence), '--', *argv]
        child = subprocess.Popen(command, **kwargs)
        guard = cls(child, _evidence_dir=evidence)
        try:
            _write_record(evidence / 'launch.json', {
                'format': 'irisx/owned-process-launch-v1', 'supervisor_identity': guard.identity,
                'coordinator_identity': _identity(_read_process(os.getpid())),
                'worker_argv': list(argv), 'scope': 'dedicated-subreaper-tree'})
            # Do not expose stop() until the supervisor's handlers and subreaper
            # are armed. Otherwise an immediate TERM could bypass its cleanup.
            deadline = time.monotonic() + 5
            while not (evidence / 'worker-launch.json').exists():
                if guard.poll() is not None:
                    raise RuntimeError('owned supervisor failed before launch handshake')
                if time.monotonic() >= deadline:
                    raise TimeoutError('owned supervisor launch handshake timed out')
                time.sleep(0.005)
        except BaseException:
            guard.stop(timeout=5)
            raise
        return guard

    def _remember(self, row):
        key = _key(row)
        if key in self._known:
            return
        self._known[key] = _identity(row)
        try:
            fd = os.pidfd_open(row['pid'], 0)
        except ProcessLookupError:
            return
        if not _same(_read_process(row['pid']), row):
            os.close(fd)
            return
        self._pidfds[key] = fd

    def _discover(self):
        roots = [self._known[key] for key in self._pidfds]
        if self._scope is not None:
            roots.append(self._scope)
        visited = set()
        while roots:
            parent = roots.pop()
            key = _key(parent)
            if key in visited or not _same(_read_process(parent['pid']), parent):
                continue
            visited.add(key)
            for pid in _child_pids(parent['pid']):
                row = _read_process(pid)
                # Confirm the parent edge while both incarnations still exist.
                if (row is None or row['parent'] != parent['pid'] or row['birth'] < parent['birth']
                        or not _same(_read_process(parent['pid']), parent)):
                    continue
                self._remember(row)
                roots.append(_identity(row))

    def _reap(self):
        self.child.poll()  # Popen alone owns its direct-child status.
        for key in list(self._pidfds):
            identity = self._known[key]
            if identity['pid'] == self.child.pid:
                continue
            row = _read_process(identity['pid'])
            fd = self._pidfds.get(key)
            if (fd is None or not _same(row, identity) or row['parent'] != os.getpid()
                    or row['state'] != 'Z'):
                continue
            try:
                result = os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG)
                if result is not None:
                    self._reaped.add(key)
            except ChildProcessError:
                pass  # Another owned ancestor, never wait for an arbitrary PID.
        for key, fd in list(self._pidfds.items()):
            if not _same(_read_process(key[0]), self._known[key]):
                os.close(fd)
                del self._pidfds[key]

    def poll(self):
        """Discover before and after reaping; return the supervisor/child status."""
        self._discover()
        self._reap()
        self._discover()
        return self.child.returncode

    def _remaining(self):
        return [_identity(row) for ident in self._known.values()
                if _same((row := _read_process(ident['pid'])), ident)]

    def _scope_has_children(self):
        if self._scope is None:
            return False
        # Only the exclusive supervisor makes this non-reaping presence probe.
        # ECHILD, unlike a racing /proc snapshot, proves it has no children left.
        try:
            os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            return False
        return True

    def _signal(self, identity, signum):
        key = _key(identity)
        row = _read_process(identity['pid'])
        fd = self._pidfds.get(key)
        if fd is None or not _same(row, identity) or row['state'] == 'Z':
            return False
        try:
            signal.pidfd_send_signal(fd, signum, None, 0)
            return True
        except ProcessLookupError:
            return False

    def _stop_tree(self, deadline):
        # Freeze known ancestors first. The exclusive subreaper retains any
        # just-orphaned child, including new-session/double-fork descendants.
        stable = None
        while time.monotonic() < deadline:
            self.poll()
            remaining = self._remaining()
            for identity in remaining:
                self._signal(identity, signal.SIGSTOP)
            self.poll()
            after = self._remaining()
            keys = frozenset(_key(row) for row in after)
            if keys == stable and all(row['state'] in ('T', 't', 'Z') for row in after):
                break
            stable = keys
            time.sleep(0.005)
        # The root is killed last; pidfds prevent targeting a recycled PID.
        self.poll()
        rows = self._remaining()
        rows.sort(key=lambda row: row['pid'] == self.child.pid)
        for identity in rows:
            self._signal(identity, signal.SIGKILL)
        while time.monotonic() < deadline:
            self.poll()
            # Adopted children may become discoverable/waitable just after their
            # parent exits. Kill newly discovered owned incarnations as well.
            remaining = self._remaining()
            for identity in remaining:
                self._signal(identity, signal.SIGKILL)
            if self.child.returncode is not None and not remaining and not self._scope_has_children():
                return
            time.sleep(0.01)

    def stop(self, timeout=10):
        """Stop and reap this tree within timeout, returning a fail-closed proof."""
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('positive finite stop timeout required')
        deadline = time.monotonic() + timeout
        self._forced = True
        self.poll()
        if self._evidence_dir is not None and self.child.returncode is None:
            # Let the dedicated supervisor retain/reap descendants itself.
            self._signal(self.identity, signal.SIGTERM)
            self._signal(self.identity, signal.SIGCONT)
            grace = min(deadline, time.monotonic() + min(3.0, timeout / 2))
            while time.monotonic() < grace and self.poll() is None:
                time.sleep(0.01)
        if self.child.returncode is None or self._remaining():
            self._stop_tree(deadline)
        return self.closed_proof()

    def closed_proof(self):
        """Snapshot proof; true closure requires all recorded incarnations gone."""
        self.poll()
        supervisor = None
        errors = list(self._errors)
        if self._evidence_dir is not None and self.child.returncode is not None:
            try:
                supervisor = _read_record(self._evidence_dir / 'supervisor-result.json')
                if (supervisor.get('format') != 'irisx/owned-supervisor-result-v1'
                        or _key(supervisor['supervisor_identity']) != _key(self.identity)):
                    raise ValueError('foreign supervisor receipt')
                for identity in supervisor['owned_identities']:
                    if set(identity) != IDENTITY_KEYS:
                        raise ValueError('invalid supervisor incarnation')
                    self._known.setdefault(_key(identity), identity)
                errors.extend(supervisor['errors'])
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append('supervisor receipt unavailable or invalid: ' + type(exc).__name__)
        complete = (self._scope is not None or (supervisor is not None
                    and supervisor.get('ownership_complete') is True
                    and supervisor.get('closed') is True))
        remaining = self._remaining()
        proof = {'format': FORMAT, 'root_identity': self.identity,
                 'scope': 'dedicated-subreaper-tree' if complete else 'observed-descendants-only',
                 'ownership_complete': complete,
                 'closed': complete and self.child.returncode is not None and not remaining and not errors
                           and not self._scope_has_children(),
                 'owned_identities': sorted(self._known.values(), key=lambda row: (row['birth'], row['pid'])),
                 'remaining': remaining, 'returncode': self.child.returncode,
                 'worker_returncode': (supervisor['worker_returncode'] if supervisor is not None
                                       else self.child.returncode if self._scope is not None else None),
                 'forced': self._forced or bool(supervisor and supervisor['forced']),
                 'reaped_identities': [self._known[key] for key in sorted(self._reaped)],
                 'errors': errors}
        if self._evidence_dir is not None and proof['closed'] and not self._persisted:
            _write_record(self._evidence_dir / 'closure.json', proof)
            self._persisted = True
        return proof


def verify_closed_proof(proof):
    """Fresh incarnation checks for the seal/evaluator; raises on any ambiguity."""
    required = {'format', 'root_identity', 'scope', 'ownership_complete', 'closed',
                'owned_identities', 'remaining', 'returncode', 'worker_returncode',
                'forced', 'reaped_identities', 'errors'}
    if (not isinstance(proof, dict) or set(proof) != required or proof['format'] != FORMAT
            or proof['scope'] != 'dedicated-subreaper-tree' or proof['closed'] is not True
            or proof['ownership_complete'] is not True or proof['remaining'] or proof['errors']
            or type(proof['returncode']) is not int or type(proof['worker_returncode']) is not int
            or type(proof['forced']) is not bool):
        raise ValueError('complete owned-process closure proof required')
    root = proof['root_identity']
    identities = proof['owned_identities']
    if (not isinstance(root, dict) or set(root) != IDENTITY_KEYS
            or not isinstance(identities, list) or not identities
            or not any(row == root for row in identities)):
        raise ValueError('bound owner incarnation required')
    keys = set()
    for identity in identities:
        if (not isinstance(identity, dict) or set(identity) != IDENTITY_KEYS
                or type(identity['pid']) is not int or identity['pid'] <= 0
                or type(identity['birth']) is not int or identity['birth'] < 0
                or type(identity['session']) is not int or type(identity['state']) is not str
                or _key(identity) in keys):
            raise ValueError('invalid or duplicate owned incarnation')
        keys.add(_key(identity))
        if _same(_read_process(identity['pid']), identity):
            raise ValueError('an owned process incarnation is still present')
    return True


def _supervise(expected_parent, evidence, argv):
    stopped = [False]
    def request_stop(_signum, _frame):
        stopped[0] = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    enable_subreaper()
    if not arm_parent_death(expected_parent, signal.SIGTERM) or stopped[0]:
        return 125
    supervisor_identity = _identity(_read_process(os.getpid()))
    command = [sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve()),
               '--exec-worker', str(os.getpid()), '--', *argv]
    child = subprocess.Popen(command, close_fds=True)
    guard = OwnedProcessGuard(child, _scope=supervisor_identity)
    try:
        _write_record(Path(evidence) / 'worker-launch.json', {
            'format': 'irisx/owned-worker-launch-v1', 'worker_identity': guard.identity,
            'supervisor_identity': supervisor_identity, 'parent_death_signal': int(signal.SIGKILL)})
        while guard.poll() is None and not stopped[0]:
            time.sleep(0.02)
        proof = guard.closed_proof()
        if stopped[0] or not proof['closed']:
            proof = guard.stop(timeout=5)
    except BaseException:
        proof = guard.stop(timeout=5)
        proof['errors'].append('supervisor exception')
        proof['closed'] = False
    result = {**proof, 'format': 'irisx/owned-supervisor-result-v1',
              'supervisor_identity': supervisor_identity,
              'worker_returncode': child.returncode}
    _write_record(Path(evidence) / 'supervisor-result.json', result)
    if not proof['closed'] or proof['errors']:
        return 125
    if stopped[0] or proof['forced']:
        return 125 if child.returncode == 0 else (128 - child.returncode if child.returncode < 0 else child.returncode)
    return 128 - child.returncode if child.returncode < 0 else child.returncode


def _main(argv):
    if len(argv) >= 5 and argv[0] == '--supervise' and argv[3] == '--':
        return _supervise(int(argv[1]), argv[2], argv[4:])
    if len(argv) >= 4 and argv[0] == '--exec-worker' and argv[2] == '--':
        if not arm_parent_death(int(argv[1])):
            return 125
        os.execvp(argv[3], argv[3:])
    raise ValueError('invalid owned-process entrypoint')


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))

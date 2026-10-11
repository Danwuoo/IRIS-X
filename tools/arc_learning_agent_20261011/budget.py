"""Persisted session clocks, bounded physical work, and deterministic calibration."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time

STAGE_SECONDS = {
    'bootstrap_and_load': 1800, 'calibrate': 900, 'data_admission': 900,
    'global_sft': 10800, 'train_only_program_rollouts': 2700,
    'verified_trajectory_sft': 2700, 'dev_and_freeze': 3600,
    'public_solve': 16200, 'seal_score_export': 1800, 'reserve': 1800,
}
SESSION_SECONDS = sum(STAGE_SECONDS.values())
if SESSION_SECONDS != 43200:
    raise RuntimeError('session budget arithmetic differs')
DEFAULT_CAPS = {'generation_calls': 1600, 'scoring_forwards': 12000,
                'input_tokens': 50_000_000, 'output_tokens': 3_200_000,
                'training_steps': 8192, 'cpu_checks': 12000, 'gas': 2_400_000_000}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8') + b'\n'


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def finite(value, name, *, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError('invalid ' + name)
    return float(value)


def atomic_json(path, value, *, exclusive=False):
    path = Path(path)
    if path.is_symlink() or (exclusive and path.exists()):
        raise ValueError('output identity already consumed or symlink')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.new-' + str(os.getpid()))
    with temporary.open('xb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    if exclusive:
        try:
            os.link(temporary, path)
        finally:
            temporary.unlink()
    else:
        os.replace(temporary, path)
    if os.name == 'posix':
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


class BudgetExceeded(RuntimeError):
    """No new work may be admitted; existing work still needs closure."""


class SessionClock:
    """Wall identity survives restarts; monotonic deadlines protect this process.

    The caller should persist a pre-dispatch epoch when it controls dispatch.
    Without it, provider provisioning time is unobserved and is not claimed.
    """
    def __init__(self, record, *, wall=time.time, monotonic=time.monotonic):
        if set(record) != {'format', 'started_epoch', 'deadline_epoch', 'maximum_seconds',
                           'origin', 'session_id'} or record['format'] != 'irisx/learning-clock-v1':
            raise ValueError('invalid session clock')
        duration = finite(record['maximum_seconds'], 'duration', minimum=1)
        start = finite(record['started_epoch'], 'start')
        end = finite(record['deadline_epoch'], 'end')
        if duration > SESSION_SECONDS or end != start + duration:
            raise ValueError('session deadline differs')
        if record['origin'] not in ('first-active-cell', 'pre-dispatch'):
            raise ValueError('invalid clock origin')
        if not isinstance(record['session_id'], str) or not record['session_id']:
            raise ValueError('session identity required')
        now = wall()
        if start > now + 2:
            raise ValueError('future session start')
        self.record = dict(record); self._wall = wall; self._mono = monotonic
        self._deadline = monotonic() + max(0, end - now)
        self.events = []
        self.stage_marker = None

    @classmethod
    def create(cls, path, session_id, *, maximum_seconds=SESSION_SECONDS,
               started_epoch=None, origin='first-active-cell', wall=time.time, monotonic=time.monotonic):
        start = wall() if started_epoch is None else finite(started_epoch, 'start')
        record = {'format': 'irisx/learning-clock-v1', 'session_id': session_id,
                  'started_epoch': start, 'deadline_epoch': start + maximum_seconds,
                  'maximum_seconds': maximum_seconds, 'origin': origin}
        clock = cls(record, wall=wall, monotonic=monotonic)
        atomic_json(path, record, exclusive=True)
        return clock

    @classmethod
    def resume(cls, path, *, expected_sha256, wall=time.time, monotonic=time.monotonic):
        path = Path(path)
        if path.is_symlink(): raise ValueError('clock symlink')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('clock identity differs')
        return cls(json.loads(raw), wall=wall, monotonic=monotonic)

    def remaining(self, *, reserve=0):
        reserve = finite(reserve, 'reserve')
        # Backwards wall adjustments cannot increase this process's time budget.
        return max(0.0, min(self._deadline - self._mono(),
                            self.record['deadline_epoch'] - self._wall()) - reserve)

    def deadline(self, *, reserve=0, maximum=None):
        seconds = self.remaining(reserve=reserve)
        if maximum is not None: seconds = min(seconds, finite(maximum, 'maximum'))
        return self._mono() + seconds

    def stage_deadline(self, name):
        if name not in STAGE_SECONDS or name == 'reserve': raise ValueError('unknown stage')
        reserve = STAGE_SECONDS['reserve']
        if name != 'seal_score_export': reserve += STAGE_SECONDS['seal_score_export']
        return self.deadline(reserve=reserve, maximum=STAGE_SECONDS[name])

    @contextmanager
    def stage(self, name):
        start = self._mono(); end = self.stage_deadline(name)
        # Reserve cleanup inside this stage, never by extending its hard cap.
        work_end = end - min(120.0, max(0.0, end - start) * 0.1)
        event = {'stage': name, 'started_epoch': self._wall(), 'maximum_seconds': STAGE_SECONDS[name],
                 'work_deadline_monotonic': work_end, 'hard_deadline_monotonic': end}
        self.events.append(event)
        if self.stage_marker is not None:
            atomic_json(self.stage_marker, {'stage': name, 'status': 'active', 'started_monotonic': start,
                'deadline_monotonic': end, 'work_deadline_monotonic': work_end,
                'session_id': self.record['session_id'],
                'maximum_seconds': STAGE_SECONDS[name]})
        if end <= start:
            event.update(status='not_admitted', elapsed_seconds=0)
            raise BudgetExceeded('session closure reserve reached')
        try:
            yield work_end
        except BaseException as exc:
            event.update(status='failed', error_type=type(exc).__name__)
            raise
        else:
            if self._mono() > end:
                event['status'] = 'overrun'
                raise BudgetExceeded('stage deadline overrun: ' + name)
            event['status'] = 'complete'
        finally:
            event['elapsed_seconds'] = self._mono() - start
            event['within_cap'] = self._mono() <= end
            if self.stage_marker is not None:
                atomic_json(self.stage_marker, {'stage': name, 'status': event['status'],
                    'deadline_monotonic': end, 'session_id': self.record['session_id'],
                    'elapsed_seconds': event['elapsed_seconds']})


class WorkLedger:
    """Reserve before dispatch. Unknown work retains its entire reservation."""
    def __init__(self, path, *, caps=None):
        self.path = Path(path)
        if self.path.exists(): raise ValueError('work ledger identity consumed')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.caps = dict(DEFAULT_CAPS if caps is None else caps)
        if set(self.caps) != set(DEFAULT_CAPS) or any(type(v) is not int or v < 0 or
                v > DEFAULT_CAPS[k] for k, v in self.caps.items()):
            raise ValueError('work caps may only narrow defaults')
        self.used = dict.fromkeys(self.caps, 0); self.pending = {}; self.events = []
        self._previous = '0' * 64
        self._append({'event': 'opened', 'caps': self.caps})

    def _append(self, event):
        row = {'index': len(self.events), 'previous': self._previous, **event}
        row['sha256'] = digest(row)
        with self.path.open('ab') as out:
            out.write(canonical(row)); out.flush(); os.fsync(out.fileno())
        self.events.append(row); self._previous = row['sha256']

    def reserve(self, event_id, estimates):
        if not isinstance(event_id, str) or not event_id or any(
            r.get('event_id') == event_id for r in self.events):
            raise ValueError('duplicate work identity')
        if self.pending:
            raise BudgetExceeded('unresolved physical work blocks new dispatch')
        if not estimates or not set(estimates) <= set(self.caps) or any(
                type(v) is not int or v < 0 for v in estimates.values()):
            raise ValueError('invalid work reservation')
        if any(self.used[k] + v > self.caps[k] for k, v in estimates.items()):
            raise BudgetExceeded('physical work cap reached')
        for k, v in estimates.items(): self.used[k] += v
        self.pending[event_id] = dict(estimates)
        self._append({'event': 'reserved', 'event_id': event_id, 'amounts': estimates})

    def complete(self, event_id, actual, *, status='complete'):
        if event_id not in self.pending or status not in ('complete', 'failed', 'excluded'):
            raise ValueError('unknown reservation or status')
        reservation = self.pending[event_id]
        if set(actual) != set(reservation) or any(type(v) is not int or v < 0 or
                v > reservation[k] for k, v in actual.items()):
            raise ValueError('work exceeded reservation; stop and preserve unknown')
        for k, v in actual.items(): self.used[k] -= reservation[k] - v
        del self.pending[event_id]
        self._append({'event': status, 'event_id': event_id, 'amounts': actual})

    def unknown(self, event_id, reason):
        if event_id not in self.pending: raise ValueError('unknown reservation')
        self._append({'event': 'unknown', 'event_id': event_id, 'reason': str(reason)[:160],
                      'charged': self.pending[event_id]})
        # Deliberately keep pending. Unknown dispatch is neither free nor retryable.

    def summary(self):
        return {'caps': dict(self.caps), 'charged': dict(self.used),
                'pending': dict(self.pending), 'events': len(self.events), 'last_sha256': self._previous}


def calibrated_steps(seconds, measurements, *, maximum_steps, safety=0.8):
    """Use observed upper per-update time, never extrapolate from fake throughput."""
    seconds = finite(seconds, 'seconds')
    if type(maximum_steps) is not int or maximum_steps < 0 or not 0 < safety <= 1:
        raise ValueError('invalid calibrated step ceiling')
    samples = [finite(x, 'measurement', minimum=1e-9) for x in measurements]
    if not samples: return 0
    return min(maximum_steps, int(seconds * safety / max(samples)))

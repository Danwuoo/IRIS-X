"""Fsync-before-dispatch physical journal. Logical snapshots never own this state.

The HMAC key belongs to the launching parent, not a caller's JSON receipt.  The
append-only chain and durable high-water anchor detect changed/replayed prefixes.
A damaged tail is retained as evidence and makes the ledger permanently unsafe;
recovery never converts uncertain dispatched work into excluded/refunded work.
"""
from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import contextvars
import fcntl
import hashlib
import hmac
import json
import math
import os
import threading
import time
import uuid

SCHEMA = 'owned-physical-journal-v1'
_ZERO = '0' * 64
_FINAL = frozenset(('complete', 'failed', 'excluded', 'excluded-recovered',
                    'unknown', 'unclosed-device-error'))
_IMMUTABLE = frozenset(('event_id', 'op_id', 'parent_op_id', 'phase', 'started',
                        'deadline', 'soft_deadline', 'hard_deadline', 'kind',
                        'clock', 'device_time_measured'))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _bounded_event(event):
    from .evidence import MAX_EVENT_BYTES
    for key in ('reserved_cost','actual_cost'):
        if key in event:
            value=event[key]
            if type(value) is not dict or not value or any(type(k) is not str or not 0<len(k)<=80 or
                type(v) not in (int,float) or not math.isfinite(v) or v<0 for k,v in value.items()):
                raise ValueError('finite nonnegative physical cost mapping required')
    if 'actual_cost' in event and ('reserved_cost' not in event or set(event['actual_cost'])!=set(event['reserved_cost']) or
        any(v>event['reserved_cost'][k] for k,v in event['actual_cost'].items())):
        raise ValueError('actual physical cost exceeds or differs from reservation')
    if len(canonical(event)) > MAX_EVENT_BYTES:
        raise ValueError('merged physical event exceeds source byte cap')


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


class JournalIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    generation_soft: float = 175.
    generation_hard: float = 180.
    operation_soft: float = 115.
    operation_hard: float = 120.
    load_soft: float = 1795.
    load_hard: float = 1800.

    def validate(self, fixture=False):
        if not fixture and self != Limits():
            raise ValueError('production watchdog limits are source-fixed')
        for soft, hard in ((self.generation_soft, self.generation_hard),
                           (self.operation_soft, self.operation_hard),
                           (self.load_soft, self.load_hard)):
            if not (_finite(soft) and _finite(hard) and 0 < soft <= hard):
                raise ValueError('positive ordered watchdog limits required')
        return self

    def for_kind(self, kind):
        if kind == 'native-load':
            return self.load_soft, self.load_hard
        if kind == 'generation':
            return self.generation_soft, self.generation_hard
        return self.operation_soft, self.operation_hard


def phase_kind(phase):
    if phase in ('native-load', 'native-model-load', 'model-load'):
        return 'native-load'
    if phase in ('generation', 'sample', 'sample-forward', 'prediction', 'public-generation', 'rollout-generation', 'evaluation-generation', 'calibration-generation'):
        return 'generation'
    return 'operation'


def _sign(key, value):
    return hmac.new(key, canonical(value), hashlib.sha256).hexdigest()


def _check_key(key):
    if type(key) is not bytes or len(key) < 32:
        raise ValueError('parent-owned authentication key of at least 32 bytes required')


def _fsync_directory(path):
    fd = os.open(str(Path(path)), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_authenticated_file(path, value, key):
    """A small parent control/high-water record; never a release authority."""
    _check_key(key)
    path = Path(path)
    envelope = {'payload': value, 'mac': _sign(key, value)}
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        data = canonical(envelope) + b'\n'
        while data:
            n = os.write(fd, data)
            if n <= 0:
                raise OSError('short control write')
            data = data[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def read_authenticated_file(path, key):
    value = json.loads(Path(path).read_bytes())
    if set(value) != {'payload', 'mac'} or not hmac.compare_digest(value['mac'], _sign(key, value['payload'])):
        raise JournalIntegrityError('authenticated local record differs')
    return value['payload']


class JournalReader:
    """Incremental authenticated reader; observes partial final lines without trust."""
    def __init__(self, path, key):
        _check_key(key)
        self.path, self.key = Path(path), key
        self.offset = 0
        self.head = _ZERO
        self.records = []
        self.events = []
        self.journal_id = None
        self.closed = False
        self.inode = None
        self.torn = False
        self.error = None
        self.anchor_seen = -1
        self.artifacts = {}
        self._op_ids = set()
        self.active = {}

    def refresh(self, *, final=False, _anchor_retry=False):
        if self.error:
            raise JournalIntegrityError(self.error)
        if not self.path.exists():
            return self
        stat = self.path.stat()
        from .evidence import MAX_JOURNAL_BYTES,MAX_EVENT_BYTES,MAX_JOURNAL_RECORDS
        if stat.st_size>MAX_JOURNAL_BYTES:
            return self._fail('journal complete byte cap exceeded')
        identity = (stat.st_dev, stat.st_ino)
        if self.inode is not None and identity != self.inode:
            return self._fail('journal replaced while observed')
        self.inode = identity
        if stat.st_size < self.offset:
            return self._fail('journal rolled back/truncated')
        with self.path.open('rb') as source:
            source.seek(self.offset)
            while True:
                line = source.readline(MAX_EVENT_BYTES+1)
                if len(line)>MAX_EVENT_BYTES or len(self.records)>=MAX_JOURNAL_RECORDS and line:
                    return self._fail('journal line/count expansion cap exceeded')
                if not line:
                    self.torn = False
                    break
                if not line.endswith(b'\n'):
                    self.torn = True
                    break
                try:
                    record = json.loads(line)
                    if set(record) != {'payload', 'mac'}:
                        raise ValueError('record envelope')
                    payload = record['payload']
                    if not hmac.compare_digest(record['mac'], _sign(self.key, payload)):
                        raise ValueError('authentication')
                    if payload['seq'] != len(self.records) or payload['previous'] != self.head:
                        raise ValueError('sequence/chain')
                    if payload['schema'] != SCHEMA:
                        raise ValueError('schema')
                    self._apply(payload)
                except (ValueError, TypeError, KeyError) as exc:
                    return self._fail('invalid journal record: ' + str(exc))
                self.head = hashlib.sha256(canonical(record)).hexdigest()
                self.records.append(payload)
                self.offset += len(line)
        # The anchor is written after journal fsync. A lagging anchor is legal
        # only while a writer is active or immediately after a crash.
        anchor_path = Path(str(self.path) + '.anchor')
        if anchor_path.exists():
            try:
                anchor = read_authenticated_file(anchor_path, self.key)
                seq = anchor['seq']
                if seq < self.anchor_seen or seq >= len(self.records):
                    # Concurrent append can advance the anchor after our EOF;
                    # final recovery has no writer and can reject immediately.
                    if not final and not _anchor_retry and seq >= len(self.records):
                        return self.refresh(final=final, _anchor_retry=True)
                    return self._fail('durable journal high-water mismatch')
                observed = self.records[seq]
                envelope = {'payload': observed, 'mac': _sign(self.key, observed)}
                if anchor['head'] != hashlib.sha256(canonical(envelope)).hexdigest() or anchor['journal_id'] != self.journal_id:
                    return self._fail('durable journal anchor differs')
                self.anchor_seen = seq
            except (ValueError, TypeError, KeyError) as exc:
                return self._fail('invalid durable anchor: ' + str(exc))
        elif final and self.records:
            return self._fail('durable journal anchor missing')
        return self

    def _fail(self, message):
        self.error = message
        raise JournalIntegrityError(message)

    def _apply(self, row):
        action = row['action']
        if not self.records:
            if action != 'open' or type(row.get('journal_id')) is not str:
                raise ValueError('initial open record')
            self.journal_id = row['journal_id']
            return
        if row.get('journal_id') != self.journal_id:
            raise ValueError('journal identity')
        if action == 'reserve':
            if self.closed:
                raise ValueError('reservation after closure')
            e = row['event']
            if e['event_id'] != len(self.events) or e['op_id'] in self._op_ids:
                raise ValueError('operation identity reused')
            if e['dispatched'] is not False or e['status'] != 'reserved':
                raise ValueError('initial operation state')
            if e['parent_op_id'] is not None and e['parent_op_id'] not in self.active:
                raise ValueError('unknown/closed parent operation')
            _bounded_event(e)
            self.events.append(deepcopy(e))
            self._op_ids.add(e['op_id'])
            self.active[e['op_id']] = self.events[-1]
        elif action in ('patch', 'dispatch', 'finish', 'recover'):
            e = self.events[row['event_id']]
            if e['op_id'] != row['op_id'] or 'ended' in e:
                raise ValueError('immutable/terminal operation changed')
            changes = row['changes']
            if _IMMUTABLE.intersection(changes) or any(k in e and k in changes and e[k]!=changes[k] for k in ('trajectory_id','update_batch_id','actual_cost')):
                raise ValueError('immutable operation metadata changed')
            if e['dispatched'] and changes.get('dispatched') is False:
                raise ValueError('dispatched work refunded')
            if changes.get('dispatched') is True and not e['dispatched'] and action != 'dispatch':
                raise ValueError('dispatch transition missing')
            if e['dispatched'] and changes.get('status', '').startswith('excluded'):
                raise ValueError('dispatched work excluded')
            _bounded_event({**e, **changes})
            e.update(deepcopy(changes))
            if 'ended' in changes:
                self.active.pop(e['op_id'], None)
        elif action == 'artifact':
            if not self.closed or row['label'] in self.artifacts:
                raise ValueError('artifact must follow closure exactly once')
            self.artifacts[row['label']] = {'path': row['path'], 'sha256': row['sha256']}
        elif action == 'close':
            if self.closed:
                raise ValueError('duplicate closure')
            self.closed = True
        else:
            raise ValueError('unknown journal action')

    def summary(self, *, final=False):
        events = deepcopy(self.events)
        for e in events:
            if 'ended' not in e and final:
                e['status'] = 'unknown' if e['dispatched'] or self.torn or self.error else 'excluded-recovered'
                e['recovery_observation_only'] = True
        charges = []
        for e in events:
            row = {'op_id': e['op_id'], 'status': e['status']}
            if 'reserved_cost' in e:
                row['charged_cost'] = deepcopy(e.get('actual_cost', e['reserved_cost']) if e['status'] == 'complete' else e['reserved_cost'])
            if 'reserved_input_tokens' in e:
                row['charged_input_tokens'] = e.get('forward_input_tokens', e['reserved_input_tokens']) if e['status'] == 'complete' else e['reserved_input_tokens']
                row['charged_forward_calls'] = e.get('forward_calls', e['reserved_forward_calls']) if e['status'] == 'complete' else e['reserved_forward_calls']
            if len(row) > 2:
                charges.append(row)
        unknown = [e['op_id'] for e in events if e['status'] in ('unknown', 'unclosed-device-error') or
                   (final and e['dispatched'] and 'ended' not in e)]
        settled = all('ended' in e and e['status'] in ('complete', 'failed', 'excluded', 'excluded-recovered') for e in events)
        return {'schema': SCHEMA, 'journal_id': self.journal_id, 'journal_path': str(self.path.resolve()),
                'head_sha256': self.head, 'record_count': len(self.records), 'event_count': len(events),
                'closed': self.closed, 'settled': settled and not self.torn and not self.error,
                'integrity_ok': not self.torn and not self.error, 'torn_tail': self.torn,
                'integrity_error': self.error, 'unknown_operation_ids': unknown,
                'dispatched_operations': sum(e['dispatched'] for e in events),
                'refunded_dispatched_operations': 0, 'cost_charges': charges, 'artifacts': deepcopy(self.artifacts), 'physical_events': events}


class DurableEvent(dict):
    """dict-compatible event whose assignment/update commits before returning."""
    def __init__(self, owner, data):
        dict.__init__(self, deepcopy(data))
        self._owner = owner

    def __setitem__(self, key, value):
        self._owner._patch(self, {key: value})

    def update(self, *args, **kwargs):
        changes = dict(*args, **kwargs)
        self._owner._patch(self, changes)

    def __delitem__(self, key):
        raise TypeError('physical journal events are append-only')

    def clear(self):
        raise TypeError('physical journal events are append-only')

    pop = popitem = clear

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def __ior__(self, other):
        self.update(other)
        return self

    def __deepcopy__(self, memo):
        return deepcopy(dict(self), memo)


class _ForwardEvent(dict):
    def __init__(self, parent, stats, started):
        super().__init__(event_id=parent['event_id'], op_id=parent['op_id'],
                         parent_op_id=parent['op_id'], phase='sample-forward',
                         started=started, dispatched=False, status='reserved',
                         compact_under_generation=True, forward_index=stats['forward_calls'])
        self.parent, self.stats = parent, stats

    def update(self, *args, **kwargs):
        changes = dict(*args, **kwargs)
        if changes.get('dispatched') is True and not self['dispatched']:
            count = changes.get('input_tokens', self.get('input_tokens'))
            if type(count) is not int or count <= 0:
                raise ValueError('positive input-token count before forward dispatch')
            if self.stats['forward_calls'] + 1 > self.parent['reserved_forward_calls'] or self.stats['forward_input_tokens'] + count > self.parent['reserved_input_tokens']:
                raise ValueError('whole-generation physical reservation exceeded')
            self.stats['forward_calls'] += 1
            self.stats['forward_input_tokens'] += count
        if self['dispatched'] and changes.get('dispatched') is False:
            raise ValueError('forward dispatch cannot be refunded')
        dict.update(self, changes)

    def __setitem__(self, key, value):
        if key in ('dispatched', 'input_tokens'):
            self.update({key: value})
        else:
            dict.__setitem__(self, key, value)


class EventView(Sequence):
    def __init__(self, owner):
        self._owner = owner

    def __len__(self):
        return len(self._owner._events)

    def __getitem__(self, index):
        return self._owner._events[index]

    def __deepcopy__(self, memo):
        return [deepcopy(e, memo) for e in self._owner._events]


class DurablePhysicalLedger:
    def __init__(self, device, global_deadline, on_fatal, journal_path, *,
                 auth_key, clock=time.monotonic, limits=None, fixture=False, recover=True,
                 stop_path=None):
        _check_key(auth_key)
        if not _finite(global_deadline):
            raise ValueError('finite original global deadline required')
        self.device, self.global_deadline, self.on_fatal = device, global_deadline, on_fatal
        self.clock, self.key = clock, auth_key
        self.limits = (limits or Limits()).validate(fixture)
        self.path = Path(journal_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stop_path = Path(stop_path or (str(self.path) + '.stop'))
        self._lock = threading.RLock()
        self._stack = contextvars.ContextVar('physical-stack-' + uuid.uuid4().hex, default=())
        self._closed = False
        self._io_failed = False
        self._events = []
        self._by_op = {}
        self._forward_stats = {}
        self.events = EventView(self)
        self._fd = os.open(self.path, os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.reader = JournalReader(self.path, self.key)
            try:
                self.reader.refresh(final=True)
            except JournalIntegrityError:
                self._io_failed = self._closed = True
            self._events = [DurableEvent(self, e) for e in self.reader.events]
            self._by_op = {e['op_id']: e for e in self._events}
            self._seq, self._head = len(self.reader.records), self.reader.head
            self.journal_id = self.reader.journal_id or uuid.uuid4().hex
            if self.reader.torn:
                self._io_failed = self._closed = True
            if self._io_failed:
                for event in self._events:
                    if 'ended' not in event:
                        dict.update(event, status='unknown', recovery_observation_only=True)
                return
            if not self._seq:
                self._append('open', created=self.clock(), pid=os.getpid())
                _fsync_directory(self.path.parent)
            elif not recover:
                raise ValueError('new physical journal required')
            elif self.reader.closed:
                self._closed = True
            else:
                for event in self._events:
                    if 'ended' not in event:
                        now = self.clock()
                        changes = {'status': 'unknown' if event['dispatched'] else 'excluded-recovered',
                                   'ended': now, 'seconds': max(0., now - event['started']),
                                   'recovered': True, 'duration_is_lower_bound': bool(event['dispatched'])}
                        _bounded_event({**event, **changes})
                        self._append('recover', event_id=event['event_id'], op_id=event['op_id'], changes=changes)
                        dict.update(event, changes)
                # Unknown model/device state cannot resume even under a fresh
                # logical snapshot. A new admitted worker is required.
                if any(e['status'] == 'unknown' for e in self._events):
                    self.closed = True
        except BaseException:
            os.close(self._fd)
            self._fd = None
            raise

    def _append(self, action, **data):
        if self._io_failed:
            raise JournalIntegrityError('physical journal is permanently unsafe')
        row = {'schema': SCHEMA, 'seq': self._seq, 'previous': self._head,
               'journal_id': self.journal_id, 'action': action, **data}
        record = {'payload': row, 'mac': _sign(self.key, row)}
        body = canonical(record)
        try:
            from .evidence import admit_journal_append
            admit_journal_append(self.path, len(body) + 1, self._seq)
            remaining = body + b'\n'
            while remaining:
                written = os.write(self._fd, remaining)
                if written <= 0:
                    raise OSError('short physical journal write')
                remaining = remaining[written:]
            os.fsync(self._fd)
            head = hashlib.sha256(body).hexdigest()
            atomic_authenticated_file(str(self.path) + '.anchor',
                                      {'seq': self._seq, 'head': head, 'journal_id': self.journal_id}, self.key)
            self._seq += 1
            self._head = head
        except BaseException as exc:
            self._io_failed = self._closed = True
            self.on_fatal(exc)
            raise

    @property
    def closed(self):
        return self._closed

    @closed.setter
    def closed(self, value):
        if value is not True:
            raise ValueError('physical ledger cannot be reopened')
        with self._lock:
            if not self._closed:
                self._append('close', ended=self.clock())
                self._closed = True

    def sync(self):
        if getattr(self.device, 'type', self.device) == 'cuda':
            import torch
            torch.cuda.synchronize(self.device)

    def _stop_requested(self):
        if self.stop_path.exists():
            value = read_authenticated_file(self.stop_path, self.key)
            if value.get('journal_path') != str(self.path.resolve()):
                raise JournalIntegrityError('stop command journal identity differs')
            return value
        return None

    def _patch(self, event, changes, *, internal=False):
        if not changes:
            return
        with self._lock:
            if self.closed or self._io_failed or 'ended' in event:
                raise ValueError('terminal physical operation cannot change')
            if _IMMUTABLE.intersection(changes) or any(k in event and k in changes and event[k]!=changes[k] for k in ('trajectory_id','update_batch_id','actual_cost')):
                raise ValueError('immutable physical operation identity/deadline/association')
            if event['dispatched'] and any(k.startswith('reserved_') for k in changes):
                raise ValueError('dispatched reservation cannot be changed/refunded')
            if event['dispatched'] and changes.get('dispatched') is False:
                raise ValueError('dispatched work cannot be refunded')
            if 'dispatched' in changes and type(changes['dispatched']) is not bool:
                raise ValueError('boolean dispatch transition required')
            dispatch = changes.get('dispatched') is True and not event['dispatched']
            if dispatch:
                if event['phase'] != 'session-cleanup' and (self.clock() >= event['soft_deadline'] or self._stop_requested()):
                    raise TimeoutError('stop/deadline before physical dispatch')
                changes = {**changes, 'status': 'dispatched', 'dispatched_at': self.clock()}
            if not internal and ('status' in changes or 'ended' in changes or 'seconds' in changes) and not dispatch:
                # Session.close owns the sole cleanup event and supplies its
                # final synchronized result; arbitrary operation state is private.
                if event['phase'] != 'session-cleanup':
                    raise ValueError('operation completion is ledger-owned')
            if event['dispatched'] and changes.get('status', '').startswith('excluded'):
                raise ValueError('dispatched work cannot be excluded')
            _bounded_event({**event, **changes})
            action = 'dispatch' if dispatch else ('finish' if 'ended' in changes else 'patch')
            self._append(action, event_id=event['event_id'], op_id=event['op_id'], changes=changes)
            dict.update(event, deepcopy(changes))

    def _reserve(self, phase, deadline, *, cleanup=False):
        with self._lock:
            if self.closed:
                raise ValueError('session physical ledger permanently closed')
            from .evidence import MAX_EVENT_COUNT
            if len(self._events) >= MAX_EVENT_COUNT:
                raise ValueError('physical event-count expansion cap reached')
            if type(phase) is not str or not phase or not _finite(deadline) or deadline > self.global_deadline:
                raise ValueError('finite operation deadline within original global limit required')
            if not cleanup and self._stop_requested():
                raise TimeoutError('parent requested stop')
            now = self.clock()
            kind = phase_kind(phase)
            soft, hard = self.limits.for_kind(kind)
            stack = self._stack.get()
            event = {'event_id': len(self._events), 'op_id': uuid.uuid4().hex,
                     'parent_op_id': stack[-1] if stack else None, 'phase': phase,
                     'kind': kind, 'started': now, 'deadline': deadline,
                     'soft_deadline': min(deadline, now + soft),
                     'hard_deadline': min(self.global_deadline, now + hard),
                     'dispatched': False, 'status': 'reserved',
                     'clock': 'synchronized-wall-time', 'device_time_measured': False}
            _bounded_event(event)
            self._append('reserve', event=event)
            proxy = DurableEvent(self, event)
            self._events.append(proxy)
            self._by_op[proxy['op_id']] = proxy
            return proxy

    def current_event(self):
        stack = self._stack.get()
        return self._by_op[stack[-1]] if stack else None

    def current_forward_counts(self):
        parent = self.current_event()
        return deepcopy(self._forward_stats.get(parent['op_id'],
                {'forward_calls': 0, 'forward_input_tokens': 0, 'forward_failed_calls': 0})) if parent else None

    @contextmanager
    def forward_work(self, phase, deadline):
        """Compact token forwards under a pre-dispatched whole-generation WAL.

        The full forward/input-token budget remains irrevocably reserved if the
        parent dies. Per-token receipt details stay local to the trajectory;
        only final aggregate observed counters are added to the parent journal.
        """
        parent = self.current_event()
        if parent is None or parent['kind'] != 'generation':
            with self.work(phase, deadline) as event:
                yield event
            return
        if not parent['dispatched']:
            raise ValueError('generation parent must be durably dispatched first')
        for key in ('reserved_forward_calls', 'reserved_input_tokens'):
            if type(parent.get(key)) is not int or parent[key] <= 0:
                raise ValueError('whole-generation bounded token reservation required')
        if not _finite(deadline) or deadline > parent['deadline']:
            raise ValueError('forward deadline cannot extend generation')
        if self.clock() >= parent['soft_deadline'] or self._stop_requested():
            raise TimeoutError('generation stop before token forward')
        stats = self._forward_stats.setdefault(parent['op_id'],
                {'forward_calls': 0, 'forward_input_tokens': 0, 'forward_failed_calls': 0})
        local = _ForwardEvent(parent, stats, self.clock())
        failure = None
        try:
            yield local
        except BaseException as exc:
            failure = exc
            raise
        finally:
            local['ended'] = self.clock()
            local['seconds'] = max(0., local['ended'] - local['started'])
            local['status'] = 'complete' if failure is None else ('failed' if local['dispatched'] else 'excluded')
            if failure is not None and local['dispatched']:
                stats['forward_failed_calls'] += 1

    def begin_event(self, phase, deadline):
        """Reserve for legacy adapters; caller marks dispatch BEFORE invocation."""
        return self._reserve(phase, deadline)

    def finish_event(self, event, *, status='complete', error=None, **details):
        if self._by_op.get(event.get('op_id')) is not event or status not in _FINAL:
            raise ValueError('owned event and terminal status required')
        now = self.clock()
        changes = {**details, 'status': status, 'ended': now,
                   'seconds': max(0., now - event['started'])}
        if error is not None:
            changes['error'] = str(error)[:256]
        self._patch(event, changes, internal=True)
        return deepcopy(dict(event))

    def seal_artifact(self, path, label='inner-closure'):
        """Bind the finalized worker closure to the authenticated journal."""
        if not self.closed or self._io_failed:
            raise ValueError('durable closure required before sealing artifact')
        path = Path(path).resolve(strict=True)
        with self._lock:
            self.reader.refresh(final=True)
            if label in self.reader.artifacts:
                raise ValueError('immutable artifact label already sealed')
            self._append('artifact', label=label, path=str(path),
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return self.reader.refresh(final=True).artifacts[label].copy()

    def start_cleanup(self, deadline=None):
        e = self._reserve('session-cleanup', self.global_deadline if deadline is None else deadline, cleanup=True)
        # Cleanup is mandatory even after a soft stop; reserve its irreversible
        # attempt before reference/device release. It cannot reset parent timers.
        self._patch(e, {'dispatched': True}, internal=True)
        return e

    @contextmanager
    def work(self, phase, deadline):
        event = self._reserve(phase, deadline)
        token = self._stack.set(self._stack.get() + (event['op_id'],))
        failure = None
        synchronized = False
        try:
            if self.clock() >= event['soft_deadline']:
                raise TimeoutError('deadline before ' + phase)
            self.sync()
            yield event
            self.sync()
            if self.clock() >= event['soft_deadline'] or self._stop_requested():
                raise TimeoutError('deadline after ' + phase)
        except BaseException as exc:
            failure = exc
            if isinstance(exc, RuntimeError):
                self.on_fatal(exc)
            raise
        finally:
            try:
                self.sync()
                synchronized = True
            except BaseException as exc:
                failure = exc
                self.on_fatal(exc)
                raise
            finally:
                self._stack.reset(token)
                now = self.clock()
                status = ('complete' if failure is None else ('failed' if event['dispatched'] else 'excluded')) if synchronized else 'unclosed-device-error'
                changes = {'status': status, 'ended': now, 'seconds': max(0., now - event['started'])}
                changes.update(self._forward_stats.pop(event['op_id'], {}))
                if failure is not None:
                    changes['error'] = type(failure).__name__ + ': ' + str(failure)[:256]
                self._patch(event, changes, internal=True)

    def summary(self):
        with self._lock:
            try:
                self.reader.refresh(final=True)
            except JournalIntegrityError:
                self._io_failed = True
            result = self.reader.summary(final=True)
            result['settled'] = result['settled'] and not self._io_failed
            result['integrity_ok'] = result['integrity_ok'] and not self._io_failed
            return result

    def release(self):
        """Release only the OS handle; it does not claim model/device closure."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __del__(self):
        try:
            self.release()
        except Exception:
            pass

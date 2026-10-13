"""Real parent-process watchdog and non-serializable closure capability.

The worker is a separate OS process. A parent-held HMAC key authenticates its
fsynced operation journal; its deadlines are intersected with the parent's
original, verified epoch mapping. No child/user Boolean can mint authority.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import hashlib
import types
import json
import os
import signal
import subprocess
import sys
import time
import weakref

from .ledger import (JournalIntegrityError, JournalReader, Limits,
                     atomic_authenticated_file, phase_kind)

_REGISTRY = weakref.WeakKeyDictionary()
_TERMINATIONS = weakref.WeakKeyDictionary()
_LAUNCHES = weakref.WeakKeyDictionary()
_OWNED_ROOT = Path(__file__).resolve().parents[1]
_WORKER = _OWNED_ROOT / 'owned_runtime' / 'worker.py'
_TEST_WORKER = _OWNED_ROOT / 'owned_tests' / 'test_ledger_supervisor.py'


class LaunchGrant:
    __slots__ = ('__weakref__',)

    def __new__(cls, *args, **kwargs):
        raise TypeError('launch grants require the source-owned parent runner')

    def __reduce__(self):
        raise TypeError('launch authority cannot be serialized')


def _environment(env, fixture):
    result = dict(os.environ if env is None else env)
    if any(result.get(name) for name in ('LD_PRELOAD', 'LD_AUDIT', 'PYTHONINSPECT', 'PYTHONSTARTUP')):
        raise ValueError('interpreter injection environment is forbidden')
    if any(type(k) is not str or type(v) is not str for k, v in result.items()):
        raise ValueError('exact string environment required')
    if fixture:
        result.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                      HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    return result


def _launch_binding(argv, cwd, output, journal_path, auth_key, clock, fixture, env, pass_fds):
    from .ledger import canonical
    return {'argv': list(argv), 'cwd': str(Path(cwd).resolve()),
            'output_root': str(Path(output).resolve()),
            'journal_path': str(Path(journal_path).resolve()),
            'key_sha256': hashlib.sha256(auth_key).hexdigest(),
            'clock': clock.receipt(), 'fixture': fixture,
            'environment_sha256': hashlib.sha256(canonical(_environment(env, fixture))).hexdigest(),
            'pass_fds': list(pass_fds)}


def register_launch(argv, *, cwd, output, journal_path, auth_key, clock,
                    request_path, request_sha256, sources, fixture, env=None, pass_fds=(), _external_release=None):
    """Only the canonical imported runner function can issue a one-use grant.

    This is in-process source ownership, not a sandbox against arbitrary Python
    reflection/memory mutation. No public JSON, key, cwd or Boolean grants it.
    """
    import owned_runtime.runner as runner
    from .clock import OriginalClock
    from .release import verify_inventory, require_production_release, canonical
    caller = sys._getframe(1)
    source_path = _OWNED_ROOT / 'owned_runtime' / 'runner.py'
    compiled = compile(source_path.read_bytes(), str(source_path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    expected = next(value for value in compiled.co_consts
                    if isinstance(value, types.CodeType) and value.co_name == 'run_owned')
    function = runner.run_owned
    if (caller.f_code is not function.__code__ or caller.f_globals is not vars(runner) or
            function.__code__ != expected or Path(runner.__file__).resolve() != source_path):
        raise ValueError('only canonical source-owned runner.run_owned may register a launch')
    if type(fixture) is not bool or type(clock) is not OriginalClock or clock.fixture is not fixture:
        raise ValueError('owned launch clock/fixture identity differs')
    clock.check_mapping()
    _validate_argv(argv, cwd, fixture)
    if list(argv[:4]) != [sys.executable, '-I', '-B', str(_WORKER)] or len(argv) != 7:
        raise ValueError('exact isolated owned worker invocation required')
    request_path = Path(request_path).resolve(strict=True)
    if Path(argv[4]).resolve() != request_path or argv[5] != request_sha256:
        raise ValueError('launch request argument differs')
    if tuple(pass_fds) != (int(argv[6]),):
        raise ValueError('one private key descriptor required')
    if request_path.is_symlink() or _sha(request_path) != request_sha256:
        raise ValueError('launch request byte identity differs')
    request = json.loads(request_path.read_bytes())
    if (request.get('format') != 'owned-rl-worker-request-v1' or
            request.get('clock') != clock.receipt() or request.get('sources') != sources or
            request.get('config', {}).get('fixture') is not fixture or
            request.get('output_root') != str(Path(output).resolve()) or
            request.get('config') != caller.f_locals.get('config') or
            caller.f_locals.get('sources') is not sources):
        raise ValueError('source-owned request/clock/config binding differs')
    source_sha = verify_inventory(sources)
    if request.get('worker_environment_sha256') != hashlib.sha256(canonical(_environment(env, fixture))).hexdigest():
        raise ValueError('owner request/actual child environment differs')
    if not fixture:
        config = request['config']
        require_production_release(sources, policy_path=config['policy_path'],
                                   environment_path=config['environment_path'],external_release=_external_release)
        from .bootstrap import consume_external_release
        consume_external_release(_external_release,sources=sources,phase='launch',request_sha256=request_sha256,plan_sha256=request['plan_sha256'],clock=clock)
    binding = _launch_binding(argv, cwd, output, journal_path, auth_key, clock, fixture, env, pass_fds)
    grant = object.__new__(LaunchGrant)
    _LAUNCHES[grant] = {'binding': binding, 'clock': clock, 'request_path': str(request_path),
                       'request_sha256': request_sha256, 'sources': dict(sources),
                       'source_sha256': source_sha}
    return grant


def _consume_launch(grant, argv, cwd, output, journal_path, auth_key, clock, fixture, env, pass_fds):
    from .release import verify_inventory
    if type(grant) is not LaunchGrant or grant not in _LAUNCHES:
        raise ValueError('fresh source-owned parent launch grant required')
    # Consume even on mismatch, before any directory creation or child spawn.
    owned = _LAUNCHES.pop(grant)
    binding = _launch_binding(argv, cwd, output, journal_path, auth_key, clock, fixture, env, pass_fds)
    if owned['clock'] is not clock or binding != owned['binding']:
        raise ValueError('launch grant arguments/request/clock/environment differ')
    if _sha(owned['request_path']) != owned['request_sha256']:
        raise ValueError('launch request changed after registration')
    verify_inventory(owned['sources'])
    return owned



class ClosedCapability:
    __slots__ = ('__weakref__',)

    def __new__(cls, *args, **kwargs):
        raise TypeError('closure capabilities are minted only by the live owned supervisor')

    def __reduce__(self):
        raise TypeError('closure authority cannot be serialized')

    def __copy__(self):
        raise TypeError('closure authority cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('closure authority cannot be copied')


class TerminatedCapability:
    """Export-only proof of observed process termination, never model closure."""
    __slots__ = ('__weakref__',)

    def __new__(cls, *args, **kwargs):
        raise TypeError('termination authority requires the live owned supervisor')

    def __reduce__(self):
        raise TypeError('termination authority cannot be serialized')

    def __copy__(self):
        raise TypeError('termination authority cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('termination authority cannot be copied')


@dataclass(frozen=True)
class SupervisionResult:
    receipt: dict
    capability: ClosedCapability | None
    termination_capability: TerminatedCapability | None = None


def _sha(path):
    from .release import file_sha
    return file_sha(path)


def verify_terminated_capability(capability):
    """Diagnostics only. Unknown model/device/journal state remains unknown."""
    if type(capability) is not TerminatedCapability or capability not in _TERMINATIONS:
        raise ValueError('live owned parent termination capability required')
    entry = _TERMINATIONS[capability]
    process = entry['process']
    if entry['pid'] != os.getpid() or process.poll() is None or _session_members(process.pid):
        raise ValueError('worker process/session termination is not verified')
    if entry['launch'] is None or entry['receipt']['worker_entrypoint'] != str(_WORKER):
        raise ValueError('only actual source-owned worker termination permits diagnostic export')
    launch = entry['launch']
    if _sha(launch['request_path']) != launch['request_sha256']:
        raise ValueError('owned termination request changed')
    entry['clock'].check_mapping()
    return deepcopy(entry['receipt'])


def _inner_is_closed(inner):
    value = inner.get('model_closure', {})
    return (type(value) is dict and all(value.get(k) is True for k in
            ('closed', 'future_operations_blocked', 'model_references_released',
             'device_synchronized', 'model_stopped', 'ledger_settled')) and
            value.get('fatal_native_state') is None)


def _journal_is_closed(journal):
    return (journal['closed'] and journal['settled'] and journal['integrity_ok'] and
            not journal['unknown_operation_ids'] and journal['event_count'] > 0 and
            any(e['phase'] == 'session-cleanup' and e['status'] == 'complete' and e['dispatched']
                for e in journal['physical_events']))


def _session_members(session_id):
    """Linux kernel-observed members of the separately created worker session."""
    result = []
    proc = Path('/proc')
    if not proc.is_dir():
        raise RuntimeError('kernel process-session closure inspection unavailable')
    for path in proc.iterdir():
        if not path.name.isdecimal():
            continue
        try:
            fields = (path / 'stat').read_text().rsplit(') ', 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if int(fields[3]) == session_id:
            result.append({'pid': int(path.name), 'state': fields[0],
                           'process_group': int(fields[2]), 'session_id': int(fields[3]),
                           'start_ticks': int(fields[19])})
    return result


def verify_closed_capability(capability, *, purpose='public'):
    """Return verified parent evidence or reject; never accepts a JSON receipt."""
    if type(capability) is not ClosedCapability or capability not in _REGISTRY:
        raise ValueError('live owned parent closure capability required')
    entry = _REGISTRY[capability]
    if purpose not in ('public', 'test'):
        raise ValueError('known closure verification purpose required')
    if purpose == 'public' and (entry.get('launch') is None or entry['receipt'].get('worker_entrypoint') != str(_WORKER)):
        raise ValueError('test worker closure cannot authorize PUBLIC; actual source-owned worker required')
    if purpose == 'public':
        from .release import verify_inventory
        verify_inventory(entry['launch']['sources'])
    receipt, process, key = entry['receipt'], entry['process'], entry['key']
    if process.poll() != 0 or not receipt['safe_closure'] or _session_members(process.pid):
        raise ValueError('worker closure is not safe')
    if _sha(receipt['inner_closure_path']) != receipt['inner_closure_sha256']:
        raise ValueError('authenticated inner closure changed')
    reader = JournalReader(receipt['journal']['journal_path'], key).refresh(final=True)
    current = reader.summary(final=True)
    if current['head_sha256'] != receipt['journal']['head_sha256'] or not _journal_is_closed(current):
        raise ValueError('durable physical closure changed')
    event_ref=receipt['journal']['physical_events_ref']
    if _sha(event_ref['path'])!=event_ref['file_sha256'] or json.loads(Path(event_ref['path']).read_bytes())!=current['physical_events']:
        raise ValueError('final physical event stream changed')
    # The source/clock authority remains parent-owned. The existing original
    # mapping must not have been reset during or after worker exit.
    entry['clock'].check_mapping()
    return deepcopy(receipt)


def _clock_deadlines(clock, fixture):
    if not fixture:
        from .clock import OriginalClock
        if type(clock) is not OriginalClock:
            raise ValueError('verified original clock object required')
    clock.check_mapping()
    values = {name: float(clock.deadline(name)) for name in ('inner', 'outer', 'provider', 'absolute')}
    if not all(values[a] < values[b] for a, b in (('inner', 'outer'), ('outer', 'provider'), ('provider', 'absolute'))):
        raise ValueError('ordered original epoch deadline chain required')
    return values


def _validate_argv(argv, cwd, fixture):
    if type(argv) not in (list, tuple) or not argv or any(type(v) is not str for v in argv):
        raise ValueError('explicit Python worker argv required')
    root = Path(cwd).resolve(strict=True)
    if root != _OWNED_ROOT:
        raise ValueError('canonical owned source root required; caller cwd is not authority')
    if Path(argv[0]).resolve() != Path(sys.executable).resolve():
        raise ValueError('current owned Python interpreter required')
    args = list(argv[1:])
    while args and args[0] in ('-I', '-B', '-u'):
        args.pop(0)
    if not args:
        raise ValueError('owned worker entrypoint required')
    entry = Path(args[0])
    entry = (root / entry).resolve() if not entry.is_absolute() else entry.resolve()
    approved = root / 'owned_runtime' / 'worker.py'
    test_entry = root / 'owned_tests' / 'test_ledger_supervisor.py'
    if entry != approved.resolve() and not (fixture and entry == test_entry.resolve()):
        raise ValueError('only the closed owned worker entrypoint may be supervised')
    if not entry.is_file():
        raise ValueError('owned worker entrypoint missing')
    return root


def _terminate(process, *, grace, absolute):
    actions = []
    def send(sig, label):
        groups = {row['process_group'] for row in _session_members(process.pid)}
        if process.poll() is None:
            groups.add(process.pid)
        for group in groups:
            try:
                os.killpg(group, sig)
                if label not in actions:
                    actions.append(label)
            except ProcessLookupError:
                pass
    send(signal.SIGTERM, 'SIGTERM-process-group')
    until = min(time.monotonic() + grace, absolute)
    while (process.poll() is None or any(row['state'] != 'Z' for row in _session_members(process.pid))) and time.monotonic() < until:
        time.sleep(min(.01, max(0., until - time.monotonic())))
    if process.poll() is None or any(row['state'] != 'Z' for row in _session_members(process.pid)):
        send(signal.SIGKILL, 'SIGKILL-process-group')
        settle = min(time.monotonic() + .2, absolute)
        while any(row['state'] != 'Z' for row in _session_members(process.pid)) and time.monotonic() < settle:
            time.sleep(.002)
    try:
        process.wait(timeout=max(.001, min(.25, absolute - time.monotonic())))
    except subprocess.TimeoutExpired:
        actions.append('worker-still-unreaped')
    return actions


def run_supervised(argv, *, cwd, output, journal_path, auth_key, clock,
                   pass_fds=(), fixture=False, limits=None, poll_seconds=.05,
                   terminate_grace=.2, env=None, _launch=None):
    """Launch one known child and enforce every outstanding nested operation.

    Tiny caps are admitted ONLY by the explicitly local CPU fixture API. The
    production limits and original deadline chain remain source-fixed.
    """
    if type(fixture) is not bool:
        raise ValueError('explicit fixture scope required')
    limits = (limits or Limits()).validate(fixture)
    deadlines = _clock_deadlines(clock, fixture)
    root = _validate_argv(argv, cwd, fixture)
    args = list(argv[1:])
    while args and args[0] in ('-I', '-B', '-u'):
        args.pop(0)
    entrypoint = (root / args[0]).resolve()
    child_env = _environment(env, fixture)
    launch = None
    if entrypoint == _WORKER:
        launch = _consume_launch(_launch, argv, cwd, output, journal_path, auth_key,
                                 clock, fixture, child_env, pass_fds)
    elif not fixture or entrypoint != _TEST_WORKER or _launch is not None:
        raise ValueError('only explicitly scoped canonical CPU test entry may omit launch grant')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    journal_path = Path(journal_path).resolve()
    if journal_path.exists() or Path(str(journal_path) + '.stop').exists():
        raise ValueError('fresh owned worker journal/control paths required')
    if time.monotonic() >= deadlines['inner']:
        raise TimeoutError('original inner deadline already expired before spawn')
    if not (0 < poll_seconds <= .25 and 0 <= terminate_grace <= 1.):
        raise ValueError('bounded parent poll and termination intervals required')
    reader = JournalReader(journal_path, auth_key)
    started = time.monotonic()
    stdout = output / 'worker.stdout.log'
    stderr = output / 'worker.stderr.log'
    stop_path = Path(str(journal_path) + '.stop')
    soft = []
    hard = None
    actions = []
    seen_soft = set()
    process = None
    integrity_error = None
    worker_incarnation = None
    try:
        with stdout.open('xb') as out, stderr.open('xb') as err:
            process = subprocess.Popen(list(argv), cwd=root, env=child_env,
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       pass_fds=tuple(pass_fds), start_new_session=True)
            worker_incarnation = next((row for row in _session_members(process.pid) if row['pid'] == process.pid), None)
            while process.poll() is None:
                now = time.monotonic()
                if stdout.stat().st_size>16*1024**2 or stderr.stat().st_size>16*1024**2:
                    hard={'reason':'owned-log-expansion-cap','observed':now};break
                try:
                    clock.check_mapping()
                    reader.refresh()
                except Exception as exc:
                    integrity_error = type(exc).__name__ + ': ' + str(exc)
                    hard = {'reason': 'clock-or-journal-integrity', 'observed': now}
                    break
                # The original chain dominates all operation-specific bounds.
                for name in ('absolute', 'provider', 'outer'):
                    if now >= deadlines[name]:
                        hard = {'reason': 'original-' + name + '-deadline', 'observed': now,
                                'deadline': deadlines[name]}
                        break
                if hard:
                    break
                pending_soft = []
                # Imports/owned admission before the first operation also have
                # the native-load ceiling; no unmetered startup can wait 12h.
                if not reader.events:
                    if now >= min(started + limits.load_hard, deadlines['outer']):
                        hard = {'reason': 'worker-startup-hard-deadline', 'observed': now,
                                'deadline': min(started + limits.load_hard, deadlines['outer'])}
                        break
                    if now >= started + limits.load_soft and 'startup' not in seen_soft:
                        pending_soft.append(('startup', {'reason': 'worker-startup-soft-deadline',
                                             'observed': now, 'deadline': started + limits.load_soft}))
                if now >= deadlines['inner'] and 'original-inner' not in seen_soft:
                    pending_soft.append(('original-inner', {'reason': 'original-inner-deadline',
                                         'observed': now, 'deadline': deadlines['inner']}))
                for e in tuple(reader.active.values()):
                    if 'ended' in e:
                        continue
                    kind = phase_kind(e['phase'])
                    soft_cap, hard_cap = limits.for_kind(kind)
                    # Worker-written values can shorten but never lengthen the
                    # independent parent policy. Validate its clock discipline.
                    if not (type(e['started']) in (int, float) and started - .01 <= e['started'] <= now + .01):
                        hard = {'reason': 'invalid-operation-start-clock', 'op_id': e['op_id'], 'observed': now}
                        break
                    op_soft = min(e['started'] + soft_cap, e['soft_deadline'], deadlines['inner'])
                    op_hard = min(e['started'] + hard_cap, e['hard_deadline'], deadlines['outer'])
                    if now >= op_hard:
                        hard = {'reason': 'operation-hard-deadline', 'op_id': e['op_id'],
                                'phase': e['phase'], 'observed': now, 'deadline': op_hard}
                        break
                    if now >= op_soft and e['op_id'] not in seen_soft:
                        pending_soft.append((e['op_id'], {'reason': 'operation-soft-deadline',
                                              'op_id': e['op_id'], 'phase': e['phase'],
                                              'observed': now, 'deadline': op_soft}))
                if hard:
                    break
                for identifier, record in pending_soft:
                    seen_soft.add(identifier)
                    soft.append(record)
                    atomic_authenticated_file(stop_path,
                                              {'journal_path': str(journal_path), 'stop_requested': True,
                                               'reason': record, 'parent_pid': os.getpid()}, auth_key)
                next_bound = min(deadlines['outer'], deadlines['provider'], deadlines['absolute'])
                time.sleep(min(poll_seconds, max(.001, next_bound - time.monotonic())))
            if hard:
                actions = _terminate(process, grace=terminate_grace, absolute=deadlines['absolute'])
            else:
                process.wait()
    except BaseException as exc:
        if process is None:
            raise
        hard = {'reason': 'parent-supervision-interrupted', 'observed': time.monotonic(),
                'exception_type': type(exc).__name__, 'exception': str(exc)[:4096]}
        if process.poll() is None:
            actions.extend(_terminate(process, grace=terminate_grace, absolute=deadlines['absolute']))
        # Continue the same real exit/session and journal inspection. Termination
        # is diagnostic evidence only; it cannot manufacture a ClosedCapability.
    exited = time.monotonic()
    surviving = _session_members(process.pid)
    if surviving and hard is None:
        hard = {'reason': 'surviving-worker-session-descendants', 'observed': exited,
                'members': surviving}
        actions.extend(_terminate(process, grace=terminate_grace, absolute=deadlines['absolute']))
    final_members = _session_members(process.pid)
    try:
        reader.refresh(final=True)
    except JournalIntegrityError as exc:
        integrity_error = str(exc)
    # Completion just after the last poll cannot erase a hard overrun.
    # Recheck every terminal operation against independently recomputed caps.
    for event in reader.events:
        if 'ended' not in event:
            continue
        _, hard_cap = limits.for_kind(phase_kind(event['phase']))
        maximum = min(event['started'] + hard_cap, event['hard_deadline'], deadlines['outer'])
        if event['ended'] > maximum and hard is None:
            hard = {'reason': 'completed-operation-hard-overrun', 'op_id': event['op_id'],
                    'phase': event['phase'], 'observed': exited, 'deadline': maximum,
                    'ended': event['ended']}
    journal = reader.summary(final=True)
    # Never rewrite unsettled worker data to pretend that killing the process
    # synchronized a GPU or refunded a dispatched operation.
    if hard or process.poll() is None:
        journal['settled'] = False
    inner_path = output / 'inner-closure.json'
    inner = None
    inner_sha = None
    closure_error = None
    try:
        inner_sha = _sha(inner_path)
        binding = reader.artifacts.get('inner-closure')
        if binding != {'path': str(inner_path), 'sha256': inner_sha}:
            raise ValueError('inner closure not sealed in authenticated durable journal')
        inner = json.loads(inner_path.read_bytes())
        if not _inner_is_closed(inner):
            raise ValueError('inner model/device closure is not verified')
    except (OSError, ValueError, TypeError) as exc:
        closure_error = type(exc).__name__ + ': ' + str(exc)
    if launch is not None and inner is not None and (inner.get('request_sha256') != launch['request_sha256'] or inner.get('clock') != clock.receipt()):
        closure_error = 'inner closure request/original clock differs from owned launch'
    # Bind one full event union instead of duplicating it in every projection.
    event_ref=(inner or {}).get('model_closure',{}).get('physical_events_ref') if type((inner or {}).get('model_closure')) is dict else None
    try:
        if event_ref is None:raise ValueError('actual worker lacks final physical event stream')
        event_path=Path(event_ref['path']).resolve()
        if not event_path.is_relative_to(output) or event_path.is_symlink() or _sha(event_path)!=event_ref['file_sha256']:
            raise ValueError('final physical stream byte binding differs')
        if json.loads(event_path.read_bytes())!=journal['physical_events']:
            raise ValueError('final physical stream differs from independently replayed journal')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        if launch is not None:
            closure_error=closure_error or ('physical-stream: '+str(exc))
        from experiment_flow.contracts import write_json
        event_ref=write_json(output/'physical-events-recovered.json',journal['physical_events'])
    journal.pop('physical_events',None)
    journal['physical_events_ref']=event_ref
    # Safety is checked against a fresh internal replay, not the compact receipt.
    journal_live=reader.summary(final=True)
    safe = (hard is None and integrity_error is None and closure_error is None and
            process.poll() == 0 and not final_members and exited < deadlines['outer'] and _journal_is_closed(journal_live))
    receipt = {'schema': 'owned-parent-supervision-v1', 'fixture': fixture,
               'output_root': str(output), 'worker_argv': list(argv), 'cwd': str(root),
               'worker_entrypoint': str(entrypoint), 'source_owned_launch': launch is not None,
               'launch_source_sha256': launch['source_sha256'] if launch else None,
               'worker_pid': process.pid, 'worker_returncode': process.poll(),
               'worker_incarnation': worker_incarnation, 'worker_session_members': final_members,
               'worker_session_empty': not final_members,
               'worker_exited': process.poll() is not None, 'started_monotonic': started,
               'exit_observed_monotonic': exited, 'original_deadlines': deadlines,
               'original_clock': clock.receipt(), 'soft_stops': soft, 'hard_stop': hard,
               'termination_actions': actions, 'safe_closure': bool(safe),
               'model_stopped': bool(safe), 'journal': journal,
               'integrity_error': integrity_error, 'closure_error': closure_error,
               'inner_closure_path': str(inner_path), 'inner_closure_sha256': inner_sha,
               'request_sha256': inner.get('request_sha256') if inner else None,
               'launch_request_sha256': launch['request_sha256'] if launch else None,
               'inner_closure': inner}
    capability = None
    if safe:
        capability = object.__new__(ClosedCapability)
        _REGISTRY[capability] = {'receipt': deepcopy(receipt), 'process': process,
                                 'key': auth_key, 'clock': clock, 'launch': launch}
    termination_capability = None
    if process.poll() is not None and not final_members and launch is not None:
        termination_capability = object.__new__(TerminatedCapability)
        _TERMINATIONS[termination_capability] = {'receipt': deepcopy(receipt), 'process': process,
            'clock': clock, 'launch': launch, 'pid': os.getpid()}
    return SupervisionResult(receipt, capability, termination_capability)

"""Opt-in E13 host shutdown policy; no model/provider imports or execution.

Signals and process-group observations concern owned host processes only. They
are not GPU preemption or provider billing attestations. The historical E10
supervisor is deliberately unchanged.
"""
from __future__ import annotations

import math
import os
import signal
import subprocess
import time

TERM_SECONDS = 3290
KILL_SECONDS = 3299.8
STOP_SECONDS = 3300
FINAL_SECONDS = 3600
MAX_WORKERS = 4


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def group_exists(pgid):
    """Probe one previously owned process group; unknown errors remain errors."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def _error(error, phase):
    return {'phase': phase, 'type': type(error).__name__, 'message': str(error)[:500]}


def cleanup_workers(resources, stop=None, *, primary=None, drains=(),
                    deadline_monotonic, now=time.monotonic, pause=time.sleep,
                    signal_group=os.killpg, group_exists=group_exists):
    """Signal all owned worker groups, then observe them under one deadline.

    ``stop`` is accepted for the shared lifecycle's calling convention, but its
    sequential per-worker wait is intentionally not invoked. Caller resources
    must be the coordinator's actual launch records, with one fresh session per
    worker. Leader exit alone does not prove group exit. Escaped/new-session
    descendants are outside this observation and must not be claimed stopped.
    """
    if not _finite(deadline_monotonic):
        raise ValueError('finite absolute E13 cleanup deadline required')
    resources = list(resources)
    if len(resources) > MAX_WORKERS:
        raise ValueError('at most four owned E13 worker groups required')
    identities = set(); pids = set(); forbidden_pids = {1, os.getpid(), os.getpgrp()}
    for item in resources:
        raw_identity = item['identity']
        if not (type(raw_identity) is int and 0 <= raw_identity < MAX_WORKERS or
                type(raw_identity) is str and raw_identity in ('0', '1', '2', '3')):
            raise ValueError('canonical declared E13 worker rank required')
        identity = str(raw_identity)
        process = item.get('process')
        if identity in identities:
            raise ValueError('unique owned worker identities required')
        identities.add(identity)
        if process is not None:
            if (type(process.pid) is not int or process.pid <= 1 or
                    process.pid in forbidden_pids or process.pid in pids):
                raise ValueError('unique positive owned worker group IDs excluding PID1/self required')
            pids.add(process.pid)
    report = {'format': 'irisx/e13-collective-cleanup-v1',
              'started_monotonic': now(), 'deadline_monotonic': deadline_monotonic,
              'finished_monotonic': None, 'workers': [], 'secondary_errors': [],
              'all_producers_stopped': False, 'complete_before_deadline': False,
              'timed_out': False, 'drain_status': 'not-requested',
              'scope': 'owned worker process groups and leaders; no escaped-descendant or GPU attestation'}
    errors = []; seen_errors = set()
    def failed(error, phase):
        if phase not in seen_errors:
            seen_errors.add(phase); errors.append(error)
            report['secondary_errors'].append(_error(error, phase))
    # Do not poll or wait between signal requests. An exited leader may leave
    # descendants in its owned group, so signal that group as well.
    for item in resources:
        process = item.get('process'); identity = str(item['identity'])
        row = {'identity': identity, 'pid': None if process is None else process.pid,
               'stop_attempted': process is not None, 'kill_requested_monotonic': None,
               'group_already_absent_at_signal': False, 'returncode': None,
               'group_absent': None, 'stop_confirmed': None,
               'stop_confirmed_monotonic': None, 'streams': {}}
        report['workers'].append(row)
        if process is not None:
            row['kill_requested_monotonic'] = now()
            try:
                signal_group(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                row['group_already_absent_at_signal'] = True
            except BaseException as error:
                failed(error, 'signal:' + identity)
    pending = [i for i, item in enumerate(resources) if item.get('process') is not None]
    while pending:
        for index in tuple(pending):
            item = resources[index]; process = item['process']; row = report['workers'][index]
            try:
                row['returncode'] = process.poll()
            except BaseException as error:
                failed(error, 'poll:' + row['identity'])
            try:
                exists = group_exists(process.pid)
                if type(exists) is not bool:
                    raise RuntimeError('literal process-group observation required')
                row['group_absent'] = not exists
            except BaseException as error:
                row['group_absent'] = None
                failed(error, 'group:' + row['identity'])
            row['stop_confirmed'] = row['returncode'] is not None and row['group_absent'] is True
            if row['stop_confirmed']:
                row['stop_confirmed_monotonic'] = now(); pending.remove(index)
        if not pending or now() >= deadline_monotonic:
            break
        delay = min(.05, max(0., deadline_monotonic - now()))
        if delay > 0:
            pause(delay)
    report['all_producers_stopped'] = not pending
    for index in pending:
        failed(RuntimeError('owned worker group or leader exit unconfirmed'),
               'stop:' + report['workers'][index]['identity'])
    for item, row in zip(resources, report['workers']):
        for name, stream in item.get('streams', {}).items():
            if stream is None:
                continue
            state = {'close_attempted': True, 'closed': None}; row['streams'][name] = state
            try:
                stream.close(); state['closed'] = stream.closed
                if state['closed'] is not True:
                    raise RuntimeError('worker stream close unconfirmed')
            except BaseException as error:
                failed(error, 'stream:' + row['identity'] + ':' + name)
    drains = list(drains)
    if drains:
        report['drain_status'] = 'skipped-unconfirmed-producers'
        if report['all_producers_stopped']:
            report['drain_status'] = 'attempted'
            for identity, action in drains:
                if now() >= deadline_monotonic:
                    report['drain_status'] = 'skipped-deadline'; break
                try:
                    action()
                except BaseException as error:
                    failed(error, 'drain:' + str(identity))
    report['finished_monotonic'] = now()
    report['timed_out'] = bool(pending) or report['finished_monotonic'] > deadline_monotonic
    report['complete_before_deadline'] = (report['all_producers_stopped'] and
                                         not report['timed_out'] and not errors)
    if report['timed_out']:
        failed(RuntimeError('E13 collective cleanup deadline exhausted'), 'cleanup-deadline')
    target = primary if primary is not None else errors[0] if errors else None
    if target is not None:
        target.cleanup_report = report
        for error in report['secondary_errors']:
            target.add_note('E13 cleanup secondary ' + error['phase'] + ': ' + error['message'])
    if primary is None and errors:
        raise target
    return report


def supervise(command, *, env, cwd, started, total_seconds, cleanup_seconds,
              now=time.monotonic, pause=time.sleep, launch=subprocess.Popen,
              capture_path=None, maximum_capture_bytes=64*1024,
              signal_group=os.killpg, group_exists=group_exists):
    """Return failed observations as well as success, so finalization can run.

    Exact cleanup_seconds=310 covers 10 seconds of shutdown and a planned
    300-second finalizer reserve. Confirmed stop covers only the coordinator's
    owned group; full export separately requires actual worker cleanup proof.
    Standard Popen construction errors have no returned process and are marked
    launch_failed. Interrupts/unknown launch outcomes cannot prove no process.
    Read/poll errors trigger an immediate owned-group kill and at most 10 seconds
    of recovery observation, still clipped to the absolute 3300-second cutoff.
    """
    if (not _finite(started) or type(total_seconds) is not int or total_seconds != FINAL_SECONDS or
            type(cleanup_seconds) is not int or cleanup_seconds != 310):
        raise ValueError('exact E13 3600/310 second supervisor profile required')
    if type(maximum_capture_bytes) is not int or not 0 < maximum_capture_bytes <= 1024*1024:
        raise ValueError('bounded coordinator output capture required')
    term_at = started + TERM_SECONDS; kill_at = started + KILL_SECONDS
    stop_at = started + STOP_SECONDS; hard = started + FINAL_SECONDS
    forbidden_pids = {1, os.getpid(), os.getpgrp()}
    receipt = {'format': 'irisx/e13-supervision-v1', 'started_monotonic': started,
               'term_deadline_monotonic': term_at, 'kill_deadline_monotonic': kill_at,
               'stop_deadline_monotonic': stop_at, 'finalizer_deadline_monotonic': hard,
               'term_requested_monotonic': None, 'kill_requested_monotonic': None,
               'coordinator_stopped_monotonic': None, 'capture_finished_monotonic': None,
               'finished_monotonic': None, 'finalization_remaining_seconds': None,
               'reserve_preserved': False, 'coordinator_group_absent': None,
               'orphaned_group_observed': False, 'supervisor_error_cleanup': False,
               'failure_cleanup_started_monotonic': None,
               'failure_cleanup_deadline_monotonic': None, 'errors': []}
    result = {'returncode': None, 'timed_out': False, 'launched': False,
              'launch_failed': False, 'launch_uncertain': False, 'launch_attempted': False, 'prelaunch_failed': False,
              'supervision_failed': False, 'confirmed_stopped': False,
              'coordinator_pid': None, 'coordinator_process_group_id': None, 'coordinator_start_new_session': None,
              'hard_deadline_monotonic': hard, 'reserve_preserved': False,
              'e13_supervision': receipt}
    process = None; owned_pid = None; tail = bytearray(); received = 0
    seen_errors = set()
    def failed(error, phase):
        result['supervision_failed'] = True
        if phase not in seen_errors:
            seen_errors.add(phase); receipt['errors'].append(_error(error, phase))
    def send(which):
        if owned_pid is None:
            return  # An invalid/unknown process identity is never a signal target.
        key = 'term_requested_monotonic' if which == signal.SIGTERM else 'kill_requested_monotonic'
        if receipt[key] is not None:
            return
        receipt[key] = now()
        try:
            signal_group(owned_pid, which)
        except ProcessLookupError:
            pass
        except BaseException as error:
            failed(error, 'term' if which == signal.SIGTERM else 'kill')
    def observe_stop():
        """Only successful poll plus literal group absence establishes exit."""
        observation_ok = True
        try:
            code = process.poll()
            if code is not None and type(code) is not int:
                raise RuntimeError('literal process return code required')
            result['returncode'] = code
        except BaseException as error:
            result['returncode'] = None; observation_ok = False; failed(error, 'poll')
        try:
            exists = group_exists(owned_pid)
            if type(exists) is not bool:
                raise RuntimeError('literal coordinator process-group observation required')
            receipt['coordinator_group_absent'] = not exists
        except BaseException as error:
            receipt['coordinator_group_absent'] = None
            observation_ok = False; failed(error, 'group')
        if result['returncode'] is not None and receipt['coordinator_group_absent'] is True:
            result['confirmed_stopped'] = True
            receipt['coordinator_stopped_monotonic'] = now()
        return observation_ok
    def recover_stop():
        if owned_pid is None or result['confirmed_stopped']:
            return
        if receipt['errors']:
            receipt['supervisor_error_cleanup'] = True
            if receipt['failure_cleanup_started_monotonic'] is None:
                stamp = now(); receipt['failure_cleanup_started_monotonic'] = stamp
                receipt['failure_cleanup_deadline_monotonic'] = min(stop_at, stamp + 10.)
            cutoff = receipt['failure_cleanup_deadline_monotonic']
        else:
            cutoff = stop_at
        send(signal.SIGKILL)
        while True:
            observe_stop()
            if result['confirmed_stopped'] or now() >= cutoff:
                break
            delay = min(.05, max(0., cutoff-now()))
            if delay > 0:
                pause(delay)
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
    try:
        if now() >= term_at:
            result.update(timed_out=True, confirmed_stopped=True, prelaunch_failed=True,
                          reason='startup exhausted E13 coordinator work allowance')
            failed(RuntimeError(result['reason']), 'startup-deadline')
            return result
        try:
            result['launch_attempted']=True
            process = launch(command, env=env, cwd=cwd,
                             stdout=subprocess.DEVNULL if capture_path is None else subprocess.PIPE,
                             stderr=subprocess.STDOUT, start_new_session=True)
        except BaseException as error:
            # These are ordinary constructor rejection/exec failures from the
            # trusted subprocess.Popen contract. A KeyboardInterrupt or other
            # unknown launcher failure may have interrupted process creation.
            proven_no_process = isinstance(error, (OSError, ValueError, TypeError, subprocess.SubprocessError))
            result.update(launch_failed=proven_no_process, launch_uncertain=not proven_no_process,
                          confirmed_stopped=proven_no_process)
            failed(error, 'launch')
            return result
        result['launched'] = True
        if (type(process.pid) is not int or process.pid <= 1 or process.pid in forbidden_pids):
            failed(ValueError('owned coordinator PID must exclude PID1 and caller PID/group'), 'ownership')
            return result
        owned_pid = process.pid
        result.update(coordinator_pid=owned_pid,coordinator_process_group_id=owned_pid,coordinator_start_new_session=True)
        if capture_path is not None:
            try:
                os.set_blocking(process.stdout.fileno(), False)
            except BaseException as error:
                failed(error, 'capture-setup')
                return result
        while True:
            if not observe_stop():
                break
            stamp = now()
            if result['confirmed_stopped']:
                break
            if result['returncode'] is not None:
                receipt['orphaned_group_observed'] = True
                result['timed_out'] = True; send(signal.SIGKILL)
            if stamp >= term_at:
                result['timed_out'] = True; send(signal.SIGTERM)
            if stamp >= kill_at:
                result['timed_out'] = True; send(signal.SIGKILL)
            if stamp >= stop_at:
                break
            try:
                drain()
            except BaseException as error:
                failed(error, 'capture-read'); break
            next_boundary = term_at if stamp < term_at else kill_at if stamp < kill_at else stop_at
            delay = min(.05, max(0., next_boundary - now()))
            if delay > 0:
                pause(delay)
        if not receipt['errors']:
            try:
                drain()
            except BaseException as error:
                failed(error, 'capture-read')
    except BaseException as error:
        failed(error, 'supervision')
    finally:
        # Best-effort bounded recovery never replaces the primary observation
        # error and cannot fabricate a return code or group-absence receipt.
        try:
            recover_stop()
        except BaseException as error:
            failed(error, 'recovery')
            send(signal.SIGKILL)
        if process is not None and owned_pid is not None and capture_path is not None:
            try:
                process.stdout.close()
            except BaseException as error:
                failed(error, 'capture-close')
        if capture_path is not None:
            capture = {'bytes_received': received, 'bytes_retained': len(tail),
                       'truncated': received > len(tail), 'written': False}
            result['output_capture'] = capture
            try:
                if now() > stop_at:
                    raise RuntimeError('capture write skipped after E13 stop cutoff')
                with open(capture_path, 'xb') as stream:
                    stream.write(tail); stream.flush(); os.fsync(stream.fileno())
                capture['written'] = True
                receipt['capture_finished_monotonic'] = now()
            except BaseException as error:
                capture['error'] = type(error).__name__ + ': ' + str(error)[:500]
                failed(error, 'capture')
        finished = now(); receipt['finished_monotonic'] = finished
        receipt['finalization_remaining_seconds'] = max(0., hard - finished)
        receipt['reserve_preserved'] = (result['confirmed_stopped'] and finished <= stop_at and
            (capture_path is None or result.get('output_capture', {}).get('written') is True) and
            not receipt['errors'])
        result['reserve_preserved'] = receipt['reserve_preserved']
        if finished > stop_at or not result['confirmed_stopped']:
            result['timed_out'] = True
    return result


def prelaunch_failure(capture_path, *, started, error, phase='dependency-discovery', now=time.monotonic):
    """Retain a real notebook setup error when no launch was attempted.

    Only the notebook's except branch may call this. It creates no process and
    makes no claim about a nonexistent PID, GPU work, or preserved success.
    """
    import traceback
    if not _finite(started) or started<0 or not isinstance(error,BaseException):
        raise ValueError('actual prelaunch exception and notebook start required')
    stamp=now()
    if not started<=stamp<=started+STOP_SECONDS:
        raise RuntimeError('prelaunch diagnostic must finish before absolute stop cutoff')
    body=(''.join(traceback.format_exception(error))).encode('utf-8',errors='replace')[-65536:]
    with open(capture_path,'xb') as stream:
        stream.write(body);stream.flush();os.fsync(stream.fileno())
    captured=now()
    if captured>started+STOP_SECONDS:raise RuntimeError('prelaunch capture exceeded absolute stop cutoff')
    receipt=dict(format='irisx/e13-supervision-v1',started_monotonic=started,
        term_deadline_monotonic=started+TERM_SECONDS,kill_deadline_monotonic=started+KILL_SECONDS,
        stop_deadline_monotonic=started+STOP_SECONDS,finalizer_deadline_monotonic=started+FINAL_SECONDS,
        term_requested_monotonic=None,kill_requested_monotonic=None,coordinator_stopped_monotonic=None,
        capture_finished_monotonic=captured,finished_monotonic=captured,
        finalization_remaining_seconds=started+FINAL_SECONDS-captured,reserve_preserved=False,
        coordinator_group_absent=None,orphaned_group_observed=False,supervisor_error_cleanup=False,
        failure_cleanup_started_monotonic=None,failure_cleanup_deadline_monotonic=None,
        errors=[_error(error,phase)])
    return dict(returncode=None,timed_out=False,launched=False,launch_failed=False,launch_uncertain=False,
        launch_attempted=False,prelaunch_failed=True,supervision_failed=True,confirmed_stopped=True,
        coordinator_pid=None,coordinator_process_group_id=None,coordinator_start_new_session=None,
        hard_deadline_monotonic=started+FINAL_SECONDS,reserve_preserved=False,e13_supervision=receipt,
        output_capture=dict(bytes_received=len(body),bytes_retained=len(body),truncated=False,written=True))

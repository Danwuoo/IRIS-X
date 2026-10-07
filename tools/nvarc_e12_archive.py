"""Bounded E12 archive finalization after observed producer shutdown.

No native imports or execution. Runtime qualification and archive closure are
separate: a failed native run may still have complete, truth-free evidence.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import time
import zipfile

from tools import nvarc_e12_delivery_envelope as delivery

MAX_FILE_BYTES = 8 * 1024**2
MAX_TREE_ENTRIES = 50000
MAX_TREE_BYTES = 512 * 1024**2
MAX_TREE_DEPTH = 32


def _read(directory_fd, name, limit, deadline, *, expected=None):
    delivery.safe_name(name); delivery.check_time(deadline)
    parts = name.split('/'); owned = []
    try:
        current = directory_fd
        for part in parts[:-1]:
            current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            owned.append(current)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            delivery.require(expected is None or delivery.file_identity(before) == delivery.file_identity(expected),
                             'evidence inode changed after inventory: ' + name)
            delivery.require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= limit,
                             'bounded regular evidence required: ' + name)
            body = bytearray()
            while True:
                delivery.check_time(deadline)
                block = stream.read(delivery.BLOCK)
                delivery.check_time(deadline)
                if not block: break
                body.extend(block)
                delivery.require(len(body) <= limit, 'growing evidence exceeded bound')
            delivery.require(len(body) == before.st_size and
                delivery.file_identity(before) == delivery.file_identity(os.fstat(stream.fileno())),
                'evidence changed while reading: ' + name)
            return bytes(body)
    finally:
        for fd in reversed(owned): os.close(fd)


def _cache(name, plan):
    parts = name.split('/')
    if len(parts) >= 4 and parts[0] == 'workers' and parts[1] in ('0', '1', '2', '3') and parts[2] in ('triton-cache', 'unsloth_compiled_cache'):
        delivery.require(name not in plan['payload_sha256'], 'compiler cache cannot replace pinned payload')
        return True
    if len(parts) >= 2 and parts[-2] == '__pycache__':
        match = re.fullmatch(r'(.+)\.cpython-[0-9]+(?:\.opt-[0-9]+)?\.pyc', parts[-1])
        source = '/'.join(parts[:-2] + [match[1] + '.py']) if match else None
        if source in plan['payload_sha256']: return True
    return False


def _inventory(directory_fd, plan, deadline):
    """Bound every entry and size, including excluded generated caches."""
    counts = [0, 0]; files = {}; folded = set(); total = 0
    cap = plan.get('maximum_archive_uncompressed_bytes')
    delivery.require(type(cap) is int and 0 < cap <= 8*1024**3, 'bounded E12 archive cap required')
    cap = min(cap, delivery.MAX_EXPANDED_BYTES)
    def walk(fd, prefix):
        nonlocal total
        delivery.check_time(deadline)
        names = []
        with os.scandir(fd) as stream:
            for entry in stream:
                counts[0] += 1
                delivery.require(counts[0] <= MAX_TREE_ENTRIES, 'bounded runtime tree entry cap exceeded')
                name = prefix + entry.name
                delivery.safe_name(name)
                delivery.require(len(name.split('/')) <= MAX_TREE_DEPTH, 'bounded runtime tree depth required')
                value = entry.stat(follow_symlinks=False)
                delivery.require(stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode),
                                 'runtime tree cannot contain symlinks or special files')
                delivery.require(name.casefold() not in folded, 'case-duplicate runtime path')
                folded.add(name.casefold()); names.append((entry.name, value))
        for leaf, value in sorted(names):
            delivery.check_time(deadline); name = prefix + leaf
            if stat.S_ISDIR(value.st_mode):
                child = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    opened = os.fstat(child)
                    delivery.require((value.st_dev, value.st_ino) == (opened.st_dev, opened.st_ino),
                                     'runtime directory inode changed after inventory')
                    walk(child, name + '/')
                finally: os.close(child)
            else:
                counts[1] += value.st_size
                delivery.require(value.st_size <= 64*1024**2 and counts[1] <= MAX_TREE_BYTES,
                                 'bounded runtime tree byte cap exceeded including caches')
                if _cache(name, plan): continue
                delivery.member_kind(name, plan)
                delivery.require(value.st_size <= MAX_FILE_BYTES, 'bounded individual evidence required')
                total += value.st_size
                delivery.require(total <= cap, 'archive uncompressed byte cap exceeded')
                body = _read(directory_fd, name, MAX_FILE_BYTES, deadline, expected=value)
                files[name] = body
    walk(directory_fd, '')
    delivery.require(set(plan['payload_sha256']) <= set(files), 'complete pinned payload inventory required')
    delivery.validate_runtime_artifacts(files, plan)
    return files


def validate_members(root, *, interrupted=None, read_bytes=None):
    """Offline inventory validation; no producer or runtime is started.

    read_bytes is intentionally unsupported: safe descriptor reads are mandatory.
    """
    delivery.require(read_bytes is None, 'descriptor-verified reads cannot be replaced')
    fd = delivery.open_directory(os.fspath(root)); deadline = time.monotonic() + delivery.MAX_SECONDS
    try:
        plan = delivery.parse(_read(fd, 'screen.json', delivery.MAX_JSON_BYTES, deadline))
        delivery.validate_plan(plan, plan.get('run_id'))
        files = _inventory(fd, plan, deadline)
        if interrupted is not None:
            interrupted.extend({'path': n, 'qualified': False} for n in files if n.endswith('.tmp'))
        return [Path(root) / name for name in sorted(files)]
    finally: os.close(fd)


def _publish(directory_fd, destination, writer, deadline, *, published_callback=None):
    """Exclusive publication of the exact verified anonymous inode."""
    delivery.require(hasattr(os, 'O_TMPFILE'), 'Linux anonymous temporary support required')
    delivery.check_time(deadline)
    fd = os.open('.', os.O_RDWR | os.O_TMPFILE | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
    with os.fdopen(fd, 'w+b') as stream:
        value = writer(stream)
        stream.flush(); os.fsync(stream.fileno()); delivery.check_time(deadline)
        os.fchmod(stream.fileno(), 0o400)
        os.link('/proc/self/fd/' + str(stream.fileno()), destination,
                dst_dir_fd=directory_fd, follow_symlinks=True)
        published = os.stat(destination, dir_fd=directory_fd, follow_symlinks=False)
        written = os.fstat(stream.fileno())
        delivery.require(stat.S_ISREG(published.st_mode) and
            (published.st_dev, published.st_ino) == (written.st_dev, written.st_ino), 'published archive inode differs')
        if published_callback is not None: published_callback(value)
        os.fsync(directory_fd); delivery.check_time(deadline)
        return value


def _new_json(fd, name, value, deadline):
    body = delivery.canonical(value)
    def write(stream):
        stream.write(body); return body
    return _publish(fd, name, write, deadline)


def _outer_gate(observation):
    """Validate in-memory coordinator stop before even opening the runtime root."""
    delivery.require(type(observation) is dict, 'outer observation object required')
    receipt = observation.get('e12_supervision', {}); start = receipt.get('started_monotonic')
    delivery.require(delivery.finite(start) and start >= 0 and observation.get('confirmed_stopped') is True and
        observation.get('hard_deadline_monotonic') == start + 3600 and
        receipt.get('format') == 'irisx/e12-supervision-v1' and
        all(delivery.finite(receipt.get(k)) and receipt[k] == start + v for k, v in (
            ('term_deadline_monotonic', 3290), ('kill_deadline_monotonic', 3299.8),
            ('stop_deadline_monotonic', 3300), ('finalizer_deadline_monotonic', 3600))) and
        type(observation.get('output_capture')) is dict and observation['output_capture'].get('written') is True and
        delivery.finite(receipt.get('capture_finished_monotonic')) and delivery.finite(receipt.get('finished_monotonic')) and
        start <= receipt['capture_finished_monotonic'] <= receipt['finished_monotonic'] <= start + 3300 and
        receipt['finished_monotonic'] <= time.monotonic(), 'bounded observed outer stop/capture required')
    delivery.reject_truth(observation)
    return observation['hard_deadline_monotonic']


def _registered_workers(root_fd):
    """Empty worker directories still need a matching cleanup observation."""
    try: fd = os.open('workers', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
    except FileNotFoundError: return set()
    try:
        ranks = set()
        with os.scandir(fd) as stream:
            for entry in stream:
                delivery.require(entry.name in ('0', '1', '2', '3') and
                    stat.S_ISDIR(entry.stat(follow_symlinks=False).st_mode), 'closed regular worker directories required')
                ranks.add(entry.name)
        return ranks
    finally: os.close(fd)


def finalize(root, observation, expected_plan_sha256):
    """Publish raw runtime ZIP, exact after-write evidence, then one delivery ZIP.

    The historical result keys describe raw evidence closure. delivery_bundle_*
    separately describes the envelope; neither an archive nor a receipt claims
    its own hash or knowledge of the outer Python function's future return.
    """
    root = Path(root)
    result = dict(final_archive_created=False, diagnostic_only_archive_created=False,
        existing_archive_preserved=False, finalization_qualified=False, diagnostic_errors=[],
        coordinator_diagnostic_excerpt='', supervision_observation_retained=False)
    receipt = dict(format='irisx/e12-finalization-timing-v1', plan_sha256=expected_plan_sha256,
        stages={}, hard_deadline_monotonic=observation.get('hard_deadline_monotonic') if type(observation) is dict else None,
        finalization_qualified=False, receipt_written=False, correctness_scored=False, promotion=False,
        archive_exists=False, archive_size=None, archive_sha256=None)
    result['finalization_timing'] = receipt
    root_fd = parent_fd = None; proof = None; sidecar = None
    def error(exc): result['diagnostic_errors'].append(type(exc).__name__ + ': ' + str(exc)[:1000])
    def observe(stage):
        stamp = time.monotonic()
        receipt['stages'][stage] = dict(monotonic=stamp, remaining_seconds=hard-stamp)
    try:
        hard = _outer_gate(observation); delivery.check_time(hard)
        delivery.identity(root.name, expected_plan_sha256)
        root_fd = delivery.open_directory(os.fspath(root)); parent_fd = delivery.open_directory(os.fspath(root.parent))
        try: os.stat(root.name+'.zip', dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError: pass
        else:
            result['existing_archive_preserved'] = True
            raise ValueError('immutable runtime archive already exists')
        raw = _read(root_fd, 'screen.json', delivery.MAX_JSON_BYTES, hard); plan = delivery.parse(raw)
        delivery.require(raw == delivery.canonical(plan) and hashlib.sha256(raw).hexdigest() == expected_plan_sha256 and
            _read(root_fd, 'plan.json', delivery.MAX_JSON_BYTES, hard) == raw, 'exact canonical finalization plan required')
        delivery.validate_plan(plan, root.name)
        terminal = None; launches = {}
        if observation.get('launched') is True:
            try: terminal = delivery.parse(_read(root_fd, 'terminal.json', delivery.MAX_JSON_BYTES, hard))
            except FileNotFoundError:
                try: terminal = delivery.parse(_read(root_fd, 'terminal-fallback.json', delivery.MAX_JSON_BYTES, hard))
                except FileNotFoundError: pass
            for row in (terminal or {}).get('cleanup', {}).get('workers', []):
                rank = row.get('identity')
                delivery.require(type(rank) is str and rank in ('0','1','2','3') and rank not in launches,
                                 'closed unique cleanup worker rank required')
                launches[rank] = None if row.get('pid') is None else delivery.parse(
                    _read(root_fd, 'workers/'+rank+'/process-launch.json', delivery.MAX_JSON_BYTES, hard))
        proof = dict(format=delivery.STOP_FORMAT, run_id=root.name, plan_sha256=expected_plan_sha256,
                     observation=observation, terminal=terminal, launches=launches)
        delivery.validate_stop(delivery.canonical(proof), root.name, expected_plan_sha256)
        delivery.require(_registered_workers(root_fd) == set(launches), 'registered worker directories differ from cleanup proof')
        if terminal is None:
            for name in ('workers', 'coordinator-admitted.json'):
                try: os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                except FileNotFoundError: continue
                raise ValueError('prelaunch failure cannot hide admitted coordinator/workers')
        capture = _read(root_fd, 'coordinator-output.log', 64*1024, hard)
        delivery.require(type(observation['output_capture'].get('bytes_retained')) is int and
            observation['output_capture']['bytes_retained'] == len(capture), 'capture byte observation differs')
        result['coordinator_diagnostic_excerpt'] = capture[-12000:].decode('utf-8', errors='replace')
        _new_json(root_fd, 'outer-supervision.json', observation, hard)
        result['supervision_observation_retained'] = True; observe('finalizer_entry')
        diagnostic = terminal is None or bool(observation['e12_supervision']['errors'])
        try:
            files = _inventory(root_fd, plan, hard)
            delivery.validate_completed_workers(files, lambda name: delivery.parse(files[name]), proof)
            partials = delivery.validate_runtime_artifacts(files, plan)
            if partials and 'interrupted-retention.json' not in files:
                files['interrupted-retention.json'] = delivery.canonical(delivery.interrupted_index(partials))
            if diagnostic: raise ValueError('supervision failure requires diagnostic-only evidence')
        except BaseException as exc:
            error(exc); diagnostic = True
            files = {'screen.json': raw, 'plan.json': raw, 'outer-supervision.json': delivery.canonical(observation),
                     'coordinator-output.log': capture}
            for name in ('bootstrap-failure.json', 'terminal.json', 'terminal-fallback.json'):
                try: body = _read(root_fd, name, delivery.MAX_JSON_BYTES, hard)
                except FileNotFoundError: continue
                delivery.validate_artifact(name, body, plan); files[name] = body
            if terminal is None and observation.get('launched') is True:
                files['e12-pre-admission-observation.json'] = delivery.canonical(dict(format='irisx/e12-pre-admission-failure-v1',
                    run_id=root.name, plan_sha256=expected_plan_sha256, coordinator_admitted=False,
                    worker_directory_exists=False, message='coordinator exited unsuccessfully before admission; retained capture gives actual failure',
                    correctness_scored=False, promotion=False))
            if terminal is None and 'bootstrap-failure.json' not in files:
                files['bootstrap-failure.json'] = delivery.canonical(dict(format='irisx/ttt-probe-entry-failure-v1',
                    run_id=root.name, message='observed coordinator startup failure; see exact captured output', correctness_scored=False, promotion=False))
            files['diagnostic-only.json'] = delivery.canonical(dict(format='irisx/ttt-probe-diagnostic-only-v1',
                complete_runtime_evidence=False, correctness_scored=False, promotion=False, errors=result['diagnostic_errors']))
        observe('validation_complete')
        def write_archive(stream):
            observe('archive_write_started')
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=False) as archive:
                for name, body in sorted(files.items()):
                    delivery.check_time(hard)
                    with archive.open(name, 'w') as member:
                        for offset in range(0, len(body), delivery.BLOCK):
                            delivery.check_time(hard); member.write(body[offset:offset+delivery.BLOCK])
            observe('archive_closed'); stream.flush(); stream.seek(0)
            binding, _ = delivery.inspect_runtime(stream, proof, root.name, expected_plan_sha256, hard)
            return binding
        def published(binding):
            result['diagnostic_only_archive_created' if diagnostic else 'final_archive_created'] = True
            receipt.update(archive_exists=True, archive_size=binding['size'], archive_sha256=binding['sha256'])
            observe('archive_published')
        _publish(parent_fd, root.name+'.zip', write_archive, hard, published_callback=published)
        observe('finalizer_returned')
        sidecar = _new_json(parent_fd, root.name+'-finalization-receipt.json', receipt, hard)
        receipt['receipt_written'] = True; receipt['receipt_write_finished_monotonic'] = time.monotonic()
        receipt['finalization_qualified'] = bool(not diagnostic and not result['diagnostic_errors'] and time.monotonic() < hard)
        result['finalization_qualified'] = receipt['finalization_qualified']
    except BaseException as exc:
        error(exc); receipt['finalization_qualified'] = result['finalization_qualified'] = False
    finally:
        for fd in (root_fd, parent_fd):
            if fd is not None: os.close(fd)
    # Serialize precisely the legacy result shape before adding transport facts.
    raw_result = delivery.canonical(result)
    result.update(delivery_bundle_created=False, delivery_bundle_path=None, delivery_bundle_sha256=None, delivery_error=None)
    if proof is not None and receipt['archive_exists']:
        try:
            envelope = delivery.create_envelope(root.parent, run_id=root.name, plan_sha256=expected_plan_sha256,
                stop_evidence=delivery.canonical(proof), sidecar=sidecar, finalizer_result=raw_result)
            result.update(delivery_bundle_created=True, delivery_bundle_path=envelope['path'],
                          delivery_bundle_sha256=envelope['sha256'])
        except BaseException as exc:
            result['delivery_error'] = type(exc).__name__ + ': ' + str(exc)[:1000]
    return result

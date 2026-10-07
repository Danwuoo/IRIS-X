"""INERT, future-integration-only E11 manual delivery; standard library only.

Never imports/extracts returned code, discovers producer files, or starts work.
Callers supply already observed stop evidence and exact expected identity.
"""

if __name__ == '__main__':
    raise RuntimeError('INERT E11 delivery: future manual-stage integration only')

import hashlib
import json
import math
import os
from pathlib import PurePosixPath
import re
import stat
import struct
import time
import zipfile

FORMAT = 'irisx/e11-manual-delivery-envelope-v1'
STOP_FORMAT = 'irisx/e11-delivery-stop-evidence-v1'
MAX_ARCHIVE_BYTES = 256 * 1024**2
MAX_EXPANDED_BYTES = 512 * 1024**2
MAX_JSON_BYTES = 1024**2
MAX_MEMBERS = 4096
MAX_DIRECTORY_BYTES = 4 * 1024**2
MAX_SECONDS = 30
BLOCK = 64 * 1024
STAGES = ('finalizer_entry', 'validation_complete', 'archive_write_started',
          'archive_closed', 'archive_published', 'finalizer_returned')
MEMBERS = {'runtime.zip', 'stop-evidence.json', 'sidecar.json',
           'finalizer-result.json', 'manifest.json'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def parse(body):
    require(type(body) is bytes and len(body) <= MAX_JSON_BYTES, 'bounded JSON bytes required')

    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'duplicate JSON key')
            value[key] = item
        return value

    def constant(_):
        raise ValueError('finite JSON required')

    value = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    require(type(value) is dict, 'JSON object required')
    # Also rejects numeric overflow such as 1e999, including nested values.
    canonical(value)
    return value


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def check_time(deadline):
    require(time.monotonic() < deadline, 'delivery time budget exhausted')


def identity(run_id, plan_sha256):
    require(type(run_id) is str and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,127}', run_id),
            'closed safe run ID required')
    require(type(plan_sha256) is str and re.fullmatch(r'[0-9a-f]{64}', plan_sha256),
            'exact expected plan SHA-256 required')


def validate_stop(body, run_id, plan_sha256):
    """Validate in-memory observations BEFORE any archive/directory is opened."""
    proof = parse(body)
    require(set(proof) == {'format', 'run_id', 'plan_sha256', 'observation', 'terminal', 'launches'} and
            proof['format'] == STOP_FORMAT and proof['run_id'] == run_id and
            proof['plan_sha256'] == plan_sha256, 'exact run/plan stop evidence required')
    observation = proof['observation']; launches = proof['launches']; terminal = proof['terminal']
    require(type(observation) is dict and type(launches) is dict, 'stop observation/launch objects required')
    receipt = observation.get('e11_supervision', {})
    require(type(receipt) is dict, 'supervision object required')
    start = receipt.get('started_monotonic')
    require(finite(start) and start >= 0 and receipt.get('format') == 'irisx/e11-supervision-v1' and
            all(finite(receipt.get(key)) and receipt[key] == start + offset for key, offset in (
                ('term_deadline_monotonic', 2390), ('kill_deadline_monotonic', 2399.8),
                ('stop_deadline_monotonic', 2400), ('finalizer_deadline_monotonic', 2700))) and
            observation.get('hard_deadline_monotonic') == start + 2700 and
            observation.get('confirmed_stopped') is True and
            type(observation.get('output_capture')) is dict and observation['output_capture'].get('written') is True and
            type(receipt.get('errors')) is list and
            all(finite(receipt.get(key)) for key in ('capture_finished_monotonic', 'finished_monotonic')) and
            start <= receipt['capture_finished_monotonic'] <= receipt['finished_monotonic'] <= start + 2400,
            'bounded confirmed outer stop/capture required')
    require(set(launches) <= {'0', '1', '2', '3'}, 'closed worker identities required')
    if observation.get('launched') is False:
        require(observation.get('launch_failed') is True and observation.get('returncode') is None and
                terminal is None and launches == {} and bool(receipt['errors']),
                'unambiguous prelaunch failure required')
        return proof
    require(observation.get('launched') is True and type(observation.get('returncode')) is int and
            receipt.get('coordinator_group_absent') is True and
            finite(receipt.get('coordinator_stopped_monotonic')) and
            start <= receipt['coordinator_stopped_monotonic'] <= receipt['capture_finished_monotonic'] and
            type(terminal) is dict and terminal.get('plan_digest') == 'sha256:' + plan_sha256,
            'coordinator and exact-plan terminal stop observations required')
    cleanup = terminal.get('cleanup', {})
    require(type(cleanup) is dict and cleanup.get('format') == 'irisx/e11-collective-cleanup-v1' and
            cleanup.get('deadline_monotonic') == start + 2399.8 and
            cleanup.get('all_producers_stopped') is cleanup.get('complete_before_deadline') is True and
            cleanup.get('timed_out') is False and cleanup.get('secondary_errors') == [] and
            finite(cleanup.get('started_monotonic')) and finite(cleanup.get('finished_monotonic')) and
            start <= cleanup['started_monotonic'] <= cleanup['finished_monotonic'] <= start + 2399.8 and
            cleanup['finished_monotonic'] <= receipt['coordinator_stopped_monotonic'] and
            type(cleanup.get('workers')) is list and len(cleanup['workers']) == len(launches),
            'all registered producers must be confirmed stopped')
    seen = set(); pids = set()
    for row in cleanup['workers']:
        require(type(row) is dict and type(row.get('identity')) is str and
                row['identity'] in launches and row['identity'] not in seen, 'unique cleanup worker required')
        seen.add(row['identity']); launch = launches[row['identity']]
        if row.get('pid') is None:
            require(launch is None and row.get('stop_attempted') is False, 'unlaunched worker receipt differs')
            continue
        require(type(launch) is dict and launch.get('format') == 'irisx/e11-owned-worker-launch-v1' and
                type(launch.get('binding')) is dict and launch['binding'].get('probe_id') == run_id and
                launch['binding'].get('plan_digest') == terminal['plan_digest'] and
                type(launch['binding'].get('rank')) is int and launch['binding']['rank'] == int(row['identity']) and
                type(row['pid']) is int and row['pid'] > 1 and row['pid'] not in pids and
                type(launch.get('pid')) is type(launch.get('process_group_id')) is int and
                launch['pid'] == launch['process_group_id'] == row['pid'] and launch.get('start_new_session') is True and
                finite(launch.get('started_monotonic')) and
                start <= launch['started_monotonic'] <= cleanup['started_monotonic'] and
                row.get('stop_attempted') is row.get('group_absent') is row.get('stop_confirmed') is True and
                type(row.get('returncode')) is int and
                finite(row.get('kill_requested_monotonic')) and finite(row.get('stop_confirmed_monotonic')) and
                cleanup['started_monotonic'] <= row['kill_requested_monotonic'] <=
                row['stop_confirmed_monotonic'] <= cleanup['finished_monotonic'],
                'matching owned launch and ordered worker stop required')
        pids.add(row['pid'])
    return proof


def open_directory(directory):
    """Reject symlinks in every path component, including ancestor directories."""
    path = os.fspath(directory)
    require(type(path) is str and len(path) <= 4096 and path.startswith('/') and '\\' not in path and
            all(part not in ('.', '..') for part in path.split('/')), 'absolute safe directory required')
    require(hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY'), 'POSIX no-follow support required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.split('/')[1:]:
            if part:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd); fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_regular(directory_fd, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    try:
        value = os.fstat(fd)
        require(stat.S_ISREG(value.st_mode) and 0 < value.st_size <= limit, 'bounded regular file required')
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


def file_identity(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def inventory(archive, *, envelope=False):
    rows = archive.infolist()
    require(len(rows) <= (len(MEMBERS) if envelope else MAX_MEMBERS), 'archive member count exceeded')
    names = set(); folded_names = set(); total = 0
    for row in rows:
        name = row.filename; parts = name.split('/')
        require(name == row.orig_filename and not name.startswith('/') and '\\' not in name and
                all(part not in ('', '.', '..') for part in parts) and ':' not in name and
                not any(ord(char) < 32 for char in name) and len(name) <= 240 and
                name.casefold() not in folded_names and not row.is_dir() and
                stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG) and
                not row.flag_bits & 1 and row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                'unsafe, duplicate or unsupported archive member')
        names.add(name); folded_names.add(name.casefold()); total += row.file_size
        require(0 <= row.file_size <= (MAX_ARCHIVE_BYTES if envelope else MAX_EXPANDED_BYTES) and
                total <= (MAX_ARCHIVE_BYTES + 4 * MAX_JSON_BYTES if envelope else MAX_EXPANDED_BYTES),
                'archive expanded size exceeded')
    require(all('/'.join(parts[:index]) not in folded_names for name in folded_names
                for parts in [name.split('/')] for index in range(1, len(parts))),
            'archive file/directory prefix collision')
    if envelope:
        require({'runtime.zip', 'stop-evidence.json', 'manifest.json'} <= names <= MEMBERS and
                all(row.compress_type == zipfile.ZIP_STORED for row in rows), 'closed stored envelope members required')
    return names


def check_directory_bounds(stream, deadline, *, envelope=False):
    """Bound central-directory parsing before zipfile allocates ZipInfo objects.

    Small bounded delivery archives never need ZIP64 or multi-disk records.
    Reject these, prefixes, suffixes and ambiguous comments conservatively.
    """
    check_time(deadline)
    stream.seek(0, 2); size = stream.tell()
    require(22 <= size <= MAX_ARCHIVE_BYTES + (5 * MAX_JSON_BYTES if envelope else 0),
            'bounded ZIP size required')
    stream.seek(size - min(size, 65557)); tail = stream.read(min(size, 65557))
    index = tail.rfind(b'PK\x05\x06')
    require(index >= 0 and len(tail) - index >= 22, 'ZIP end record missing')
    _, disk, central_disk, count_disk, count, central_size, offset, comment = struct.unpack(
        '<4s4H2IH', tail[index:index + 22])
    require(disk == central_disk == 0 and count_disk == count and
            0 < count <= (len(MEMBERS) if envelope else MAX_MEMBERS) and
            central_size <= MAX_DIRECTORY_BYTES and offset + central_size == size - len(tail) + index and
            len(tail) - index == 22 + comment, 'bounded single-disk ZIP directory required')
    stream.seek(0)
    require(stream.read(4) == b'PK\x03\x04', 'ZIP prefixes forbidden')
    check_time(deadline); stream.seek(0)


def stream_digest(stream, deadline, limit, target=None):
    hasher = hashlib.sha256(); count = 0
    while True:
        check_time(deadline)
        block = stream.read(BLOCK)
        check_time(deadline)
        if not block:
            break
        count += len(block)
        require(count <= limit, 'stream size exceeded')
        hasher.update(block)
        if target is not None:
            target.write(block)
            check_time(deadline)
    return {'size': count, 'sha256': hasher.hexdigest()}


def json_member(archive, name, deadline):
    require(archive.getinfo(name).file_size <= MAX_JSON_BYTES, 'bounded JSON member required')
    check_time(deadline)
    body = archive.read(name)
    check_time(deadline)
    return body, parse(body)


def inspect_runtime(stream, proof, run_id, plan_sha256, deadline):
    check_directory_bounds(stream, deadline)
    with zipfile.ZipFile(stream) as archive:
        names = inventory(archive)
        require('screen.json' in names and 'outer-supervision.json' in names, 'runtime plan/observation missing')
        raw, plan = json_member(archive, 'screen.json', deadline)
        require(hashlib.sha256(raw).hexdigest() == plan_sha256 and
                raw == canonical(plan) and
                plan.get('run_id') == plan.get('screen_id') == run_id and
                plan.get('maximum_notebook_wall_seconds') == 2700, 'runtime exact run/plan differs')
        if 'plan.json' in names:
            plan_raw, _ = json_member(archive, 'plan.json', deadline)
            require(hashlib.sha256(plan_raw).hexdigest() == plan_sha256, 'runtime plan copies differ')
        for name in ('outer-supervision.json', 'e11-supervision-observation.json'):
            if name in names:
                require(canonical(json_member(archive, name, deadline)[1]) == canonical(proof['observation']),
                        'archived stop observation differs')
        worker_paths = [PurePosixPath(name).parts for name in names if name == 'workers' or name.startswith('workers/')]
        require(all(len(parts) >= 3 and parts[1] in ('0', '1', '2', '3') for parts in worker_paths),
                'closed worker file paths required')
        worker_ids = {parts[1] for parts in worker_paths}
        fallback = False
        if 'diagnostic-only.json' in names:
            diagnostic = json_member(archive, 'diagnostic-only.json', deadline)[1]
            require(diagnostic.get('complete_runtime_evidence') is False and diagnostic.get('promotion') is False,
                    'diagnostic marker must remain unqualified')
            fallback = diagnostic.get('format') == 'irisx/ttt-probe-diagnostic-only-v1' and diagnostic.get('complete_runtime_evidence') is False
        require(worker_ids <= set(proof['launches']) and
                (fallback or worker_ids == set(proof['launches'])), 'archived worker inventory differs from stop proof')
        if proof['terminal'] is None:
            require('bootstrap-failure.json' in names and 'coordinator-admitted.json' not in names and
                    not any(name.startswith('workers/') for name in names) and
                    not {'terminal.json', 'terminal-fallback.json'} & names, 'prelaunch archive differs')
        else:
            terminal_name = 'terminal.json' if 'terminal.json' in names else 'terminal-fallback.json'
            require(terminal_name in names and canonical(json_member(archive, terminal_name, deadline)[1]) == canonical(proof['terminal']) and
                    proof['terminal'].get('plan_digest') == 'sha256:' + hashlib.sha256(canonical(plan)).hexdigest(),
                    'archived terminal/plan binding differs')
            for rank, launch in proof['launches'].items():
                name = 'workers/' + rank + '/process-launch.json'
                if launch is not None:
                    require(canonical(launch.get('binding')) == canonical(dict(probe_id=run_id, plan_digest=proof['terminal']['plan_digest'],
                                rank=int(rank), task_id=plan['task_order'][int(rank)],
                                model_material_digest=plan['model_material_digest'])), 'worker launch plan binding differs')
                if launch is None:
                    require(name not in names, 'unlaunched worker has launch record')
                elif fallback and name not in names:
                    # Ancestor finalization retains only bounded diagnostic files.
                    # In-memory stop evidence remains required; absence is no success.
                    continue
                else:
                    require(name in names and canonical(json_member(archive, name, deadline)[1]) == canonical(launch),
                            'archived worker launch binding differs')
        # Stream every member to EOF for CRC; nothing is extracted or executed.
        for row in archive.infolist():
            with archive.open(row) as member:
                info = stream_digest(member, deadline, row.file_size)
                require(info['size'] == row.file_size, 'runtime member size differs')
    stream.seek(0)
    return stream_digest(stream, deadline, MAX_ARCHIVE_BYTES), 'diagnostic-only.json' in names


def completion(sidecar_body, result_body, runtime, proof, plan_sha256, diagnostic, *, observed_now=None):
    """Preserve failed/partial receipts. Never infer after-write success."""
    sidecar = parse(sidecar_body) if sidecar_body is not None else None
    result = parse(result_body) if result_body is not None else None
    receipt = None
    if sidecar is not None:
        require(sidecar.get('receipt_written') is False and sidecar.get('finalization_qualified') is False and
                'receipt_write_finished_monotonic' not in sidecar, 'sidecar cannot claim post-write success')
    if result is not None:
        require(set(result) == {'final_archive_created', 'diagnostic_only_archive_created', 'existing_archive_preserved',
                    'finalization_qualified', 'supervision_observation_retained', 'diagnostic_errors',
                    'coordinator_diagnostic_excerpt', 'finalization_timing'} and
                all(type(result.get(key)) is bool for key in ('final_archive_created', 'diagnostic_only_archive_created',
                    'existing_archive_preserved', 'finalization_qualified', 'supervision_observation_retained')) and
                type(result.get('diagnostic_errors')) is list and type(result.get('finalization_timing')) is dict and
                all(type(error) is str for error in result['diagnostic_errors']) and
                type(result.get('coordinator_diagnostic_excerpt')) is str and
                len(result['coordinator_diagnostic_excerpt']) <= 12000 and
                not (result['final_archive_created'] and result['diagnostic_only_archive_created']) and
                (not diagnostic or not result['final_archive_created']), 'full finalizer result required')
        receipt = result['finalization_timing']
        require(result['finalization_qualified'] is receipt.get('finalization_qualified'), 'result/receipt qualification differs')
    for item in (sidecar, receipt):
        if item is None:
            continue
        require(set(item) == {'format', 'plan_sha256', 'stages', 'hard_deadline_monotonic',
                    'finalization_qualified', 'receipt_written', 'correctness_scored', 'promotion',
                    'archive_exists', 'archive_size', 'archive_sha256'} |
                    ({'receipt_write_finished_monotonic'} if item.get('receipt_written') is True else set()) and
                item.get('format') == 'irisx/e11-finalization-timing-v1' and item.get('plan_sha256') == plan_sha256 and
                item.get('hard_deadline_monotonic') == proof['observation']['hard_deadline_monotonic'] and
                item.get('correctness_scored') is item.get('promotion') is False and
                type(item.get('receipt_written')) is type(item.get('finalization_qualified')) is bool and
                item.get('archive_exists') is True and type(item.get('archive_size')) is int and
                item['archive_size'] == runtime['size'] and
                (item.get('archive_sha256') is None or item['archive_sha256'] == runtime['sha256']) and
                type(item.get('stages')) is dict and set(item['stages']) <= set(STAGES), 'receipt plan/archive binding differs')
        previous = proof['observation']['e11_supervision']['finished_monotonic']
        for stage in STAGES:
            if stage not in item['stages']:
                continue
            row = item['stages'][stage]
            require(type(row) is dict and set(row) == {'monotonic', 'remaining_seconds'} and
                    finite(row.get('monotonic')) and finite(row.get('remaining_seconds')) and
                    row['monotonic'] >= previous and
                    (observed_now is None or row['monotonic'] <= observed_now) and
                    row['remaining_seconds'] == item['hard_deadline_monotonic'] - row['monotonic'], 'receipt stage timing differs')
            previous = row['monotonic']
        if item['receipt_written']:
            require(finite(item.get('receipt_write_finished_monotonic')) and
                    item['receipt_write_finished_monotonic'] >= previous and
                    (observed_now is None or item['receipt_write_finished_monotonic'] <= observed_now),
                    'post-write observation missing, future or unordered')
        else:
            require('receipt_write_finished_monotonic' not in item and item['finalization_qualified'] is False,
                    'unwritten receipt cannot qualify')
    if sidecar is not None and receipt is not None:
        projection = dict(receipt, finalization_qualified=False, receipt_written=False)
        projection.pop('receipt_write_finished_monotonic', None)
        require(canonical(projection) == canonical(sidecar), 'sidecar and observed result disagree')
    if receipt is not None and receipt['finalization_qualified']:
        require(receipt['receipt_written'] and receipt['archive_sha256'] == runtime['sha256'] and
                set(receipt['stages']) == set(STAGES) and
                receipt['receipt_write_finished_monotonic'] < receipt['hard_deadline_monotonic'] and
                result['final_archive_created'] and not result['diagnostic_only_archive_created'] and
                not result['existing_archive_preserved'] and result['diagnostic_errors'] == [] and
                result['supervision_observation_retained'] and proof['observation'].get('launched') is True and
                proof['observation']['e11_supervision']['errors'] == [],
                'qualified completion lacks full observed closure')
    item = receipt if receipt is not None else sidecar
    return dict(evidence_kind=('post_write_result' if receipt and receipt['receipt_written'] else
                               'incomplete_result' if receipt else 'sidecar_only' if sidecar else 'unknown'),
                archive_binding=('verified' if item and item['archive_sha256'] is not None else 'unknown'),
                observed_finalization_qualified=receipt['finalization_qualified'] if receipt else None,
                runtime_qualification='diagnostic_only' if diagnostic else 'not_assessed',
                correctness_scored=False, promotion=False)


def verify_stream(stream, run_id, plan_sha256, deadline):
    check_directory_bounds(stream, deadline, envelope=True)
    with zipfile.ZipFile(stream) as archive:
        names = inventory(archive, envelope=True)
        _, manifest = json_member(archive, 'manifest.json', deadline)
        require(set(manifest) == {'format', 'run_id', 'plan_sha256', 'members', 'completion'} and
                manifest['format'] == FORMAT and manifest['run_id'] == run_id and manifest['plan_sha256'] == plan_sha256 and
                type(manifest['members']) is dict and set(manifest['members']) == names - {'manifest.json'},
                'envelope manifest identity/members differ')
        data = {}
        for name in sorted(names - {'manifest.json'}):
            with archive.open(name) as member:
                actual = stream_digest(member, deadline, MAX_ARCHIVE_BYTES if name == 'runtime.zip' else MAX_JSON_BYTES)
            require(canonical(actual) == canonical(manifest['members'][name]), 'envelope member hash/size differs')
            if name != 'runtime.zip':
                data[name] = json_member(archive, name, deadline)[0]
        proof = validate_stop(data['stop-evidence.json'], run_id, plan_sha256)
        with archive.open('runtime.zip') as runtime:
            actual, diagnostic = inspect_runtime(runtime, proof, run_id, plan_sha256, deadline)
        require(actual == manifest['members']['runtime.zip'], 'nested runtime bytes differ')
        expected = completion(data.get('sidecar.json'), data.get('finalizer-result.json'), actual, proof, plan_sha256, diagnostic)
        require(canonical(manifest['completion']) == canonical(expected), 'manifest cannot promote completion evidence')
    return manifest


def create_envelope(directory, *, run_id, plan_sha256, stop_evidence, sidecar=None, finalizer_result=None):
    """Create run_id-delivery.zip once, within the original hard deadline.

    Stop/evidence inputs are bytes from the future execution caller's observations;
    no producer directory or sidecar path is read. Linux O_TMPFILE/procfs only.
    """
    identity(run_id, plan_sha256)
    proof = validate_stop(stop_evidence, run_id, plan_sha256)
    started = time.monotonic()
    require(proof['observation']['e11_supervision']['finished_monotonic'] <= started,
            'producer stop must already have been observed')
    deadline = min(started + MAX_SECONDS, proof['observation']['hard_deadline_monotonic'])
    check_time(deadline)
    require(hasattr(os, 'O_TMPFILE'), 'Linux anonymous temporary support required')
    data = {'stop-evidence.json': stop_evidence}
    for name, body in (('sidecar.json', sidecar), ('finalizer-result.json', finalizer_result)):
        if body is not None:
            parse(body); data[name] = body
    directory_fd = open_directory(directory)
    try:
        destination = run_id + '-delivery.zip'
        try:
            os.stat(destination, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError('immutable delivery already exists')
        with open_regular(directory_fd, run_id + '.zip', MAX_ARCHIVE_BYTES) as source:
            before = os.fstat(source.fileno())
            runtime, diagnostic = inspect_runtime(source, proof, run_id, plan_sha256, deadline)
            manifest = dict(format=FORMAT, run_id=run_id, plan_sha256=plan_sha256,
                            members={'runtime.zip': runtime},
                            completion=completion(sidecar, finalizer_result, runtime, proof, plan_sha256, diagnostic,
                                                  observed_now=started))
            for name, body in data.items():
                manifest['members'][name] = dict(size=len(body), sha256=hashlib.sha256(body).hexdigest())
            # An anonymous inode has no temporary pathname for a racing writer
            # to substitute between verification and publication.
            fd = os.open('.', os.O_RDWR | os.O_TMPFILE | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
            with os.fdopen(fd, 'w+b') as output:
                with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
                    source.seek(0)
                    with archive.open('runtime.zip', 'w') as target:
                        require(stream_digest(source, deadline, MAX_ARCHIVE_BYTES, target) == runtime,
                                'runtime changed while copying')
                    for name, body in sorted(data.items()):
                        check_time(deadline); archive.writestr(name, body)
                    archive.writestr('manifest.json', canonical(manifest))
                output.flush(); os.fsync(output.fileno()); check_time(deadline)
                verify_stream(output, run_id, plan_sha256, deadline)
                output.seek(0)
                envelope = stream_digest(output, deadline, MAX_ARCHIVE_BYTES + 5 * MAX_JSON_BYTES)
                after = os.fstat(source.fileno())
                require(file_identity(before) == file_identity(after), 'runtime source changed')
                os.fchmod(output.fileno(), 0o400)
                check_time(deadline)
                # The sole intentional symlink follow is this process's own
                # open descriptor, never a caller-controlled path. linkat is
                # exclusive and links exactly the inode just verified.
                os.link('/proc/self/fd/' + str(output.fileno()), destination,
                        dst_dir_fd=directory_fd, follow_symlinks=True)
                published = os.stat(destination, dir_fd=directory_fd, follow_symlinks=False)
                written = os.fstat(output.fileno())
                require(stat.S_ISREG(published.st_mode) and
                        (published.st_dev, published.st_ino) == (written.st_dev, written.st_ino),
                        'published delivery inode differs')
                os.fsync(directory_fd)
                # A slow syscall may publish but cannot return a false in-budget claim.
                check_time(deadline)
        return dict(path=os.path.join(os.fspath(directory), destination), **envelope, manifest=manifest)
    finally:
        os.close(directory_fd)


def verify_envelope(directory, *, run_id, plan_sha256):
    """Read-only offline verification; historical monotonic clocks are not replayed."""
    identity(run_id, plan_sha256)
    deadline = time.monotonic() + MAX_SECONDS
    directory_fd = open_directory(directory)
    try:
        with open_regular(directory_fd, run_id + '-delivery.zip', MAX_ARCHIVE_BYTES + 5 * MAX_JSON_BYTES) as stream:
            before = os.fstat(stream.fileno())
            manifest = verify_stream(stream, run_id, plan_sha256, deadline)
            require(file_identity(before) == file_identity(os.fstat(stream.fileno())), 'delivery changed during verification')
            return manifest
    finally:
        os.close(directory_fd)

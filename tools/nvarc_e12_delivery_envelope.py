"""E12 bounded execution-time delivery and read-only verification; standard library only.

Never imports/extracts returned code, discovers producer files, or starts work.
Callers supply already observed stop evidence and exact expected identity.
"""

if __name__ == '__main__':
    raise RuntimeError('INERT E12 delivery: explicit caller integration required')

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

FORMAT = 'irisx/e12-delivery-envelope-v1'
STOP_FORMAT = 'irisx/e12-delivery-stop-evidence-v1'
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
RUN_ID = 'stage4-e12-probe-prefix-20261007-001'
ARMS = ('ttt64', 'ttt128')
TASKS = {'195c6913': 2, 'aa4ec2a5': 1, 'a47bf94d': 1, 'a25697e4': 2}
ROOT_FILES = {'screen.json', 'plan.json', 'material-contract.json', 'terminal.json',
    'execution-ledger.jsonl', 'caller-receipt-bindings.json', 'hardware.json', 'hardware-raw.json',
    'source-verification.json', 'model-verification.json', 'dependency-setup.log',
    'source-verification-prepare.json', 'interrupted-retention.json', 'mount-policy.json',
    'terminal-fallback.json', 'dependency-readproof-receipt.json', 'bootstrap-failure.json',
    'outer-supervision.json', 'coordinator-output.log', 'coordinator-admitted.json',
    'training-release.json', 'output-commit.json', 'output-projection.json', '.output-writer.lock',
    'diagnostic-only.json', 'e12-supervision-observation.json', 'e12-owner-confirmation.json',
    'e12-pre-admission-observation.json'}
OUTPUT_FILES = {'paired-summary.json', 'paired-task-timings.json'} | {
    arm + '-' + suffix + '.json' for arm in ARMS for suffix in ('answers', 'audit', 'candidate-pools')}
WORKER_FILES = {'stdout.log', 'stderr.log', 'ready.json', 'launch-reservation.json', 'result.json',
    'events.jsonl', 'process-launch.json', 'baseline-inventory.json', 'cache-control.json',
    'baseline-model-metadata.json', 'texts.json', 'expected-rows.json', 'training-ready.json',
    'training-window.json', 'final-reset-inventory.json', 'post-reset-control.json'}
ARM_FILES = {'native-schedule.json', 'arm-receipt.json', 'baseline-inventory.json',
    'preparation.json', 'prepared-rows.json',
    'training-before-metadata.json', 'training-after-metadata.json', 'training-ledger.json',
    'prefix-contract.json', 'prefix-trace.json', 'sampler.json', 'native-hook-status.json',
    'optimizer-state.json', 'trained-inventory.json', 'trained-inference-transition.json',
    'model-before-metadata.json', 'trained-before-inventory.json', 'inference-events.jsonl',
    'answer-checkpoint.json', 'inference-forward-diagnostics.json', 'test-allocations.json',
    'adapter-entry.json', 'model-after-metadata.json', 'trained-after-inventory.json',
    'reset-inference-transition.json', 'reset-inventory.json'}
TRUTH_FIELDS = {'expected_output', 'expected_outputs', 'evaluator_truth', 'solutions',
    'correct_output', 'correct_outputs', 'exact_match', 'official_score'}


def safe_name(name):
    require(type(name) is str and 0 < len(name) <= 240 and not name.startswith('/') and
            '\\' not in name and ':' not in name and
            all(part not in ('', '.', '..') for part in name.split('/')) and
            not any(ord(c) < 32 or ord(c) == 127 for c in name), 'safe relative member name required')


def validate_plan(plan, run_id):
    require(plan.get('format') == 'irisx/stage4-e12-prefix-probe-v1' and
            plan.get('run_id') == plan.get('screen_id') == run_id == RUN_ID and
            plan.get('resource_budget_profile') == 'conservative-60min-inert' and
            plan.get('generation_budget_profile') == 'native-prefix-stop-v10' and
            plan.get('task_order') == list(TASKS) and canonical(plan.get('test_counts')) == canonical(TASKS) and
            all(type(plan.get(k)) is int and plan[k] == v for k, v in {
                'maximum_notebook_wall_seconds': 3600, 'optimizer_steps': 768,
                'test_executions': 12, 'cleanup_reserve_seconds': 310}.items()) and
            canonical(plan.get('e12_process_policy')) == canonical(dict(term_seconds=3290,
                kill_seconds=3299.8, stop_seconds=3300, final_seconds=3600,
                worker_cleanup_deadline_seconds=3299.8, requires_owned_group_absence=True)),
            'closed E12 task/update/test/process profile required')
    payload = plan.get('payload_sha256'); sources = plan.get('source_files_sha256')
    require(type(payload) is dict and type(sources) is dict and set(sources) <= set(payload) and
            0 < len(payload) <= MAX_MEMBERS and not {'screen.json', 'plan.json'} & set(payload),
            'closed noncircular plan payload inventory required')
    for name, sha in payload.items():
        safe_name(name)
        require(type(sha) is str and re.fullmatch('[0-9a-f]{64}', sha), 'payload SHA-256 required')
    require(len({n.casefold() for n in payload}) == len(payload) and
            all(sources[n] == payload[n] for n in sources), 'source/payload inventory differs')


def member_kind(name, plan):
    """Exact payload or declared runtime evidence; never an extension allowlist."""
    safe_name(name)
    if name in plan['payload_sha256']:
        return 'static'
    normalized = re.sub(r'\.[0-9a-f]{32}\.tmp$', '', name)
    if normalized == name and name.endswith('.tmp'):
        normalized = name[:-4]
    parts = normalized.split('/')
    allowed = normalized in ROOT_FILES | OUTPUT_FILES
    if len(parts) == 3 and parts[0] == 'workers' and parts[1] in ('0', '1', '2', '3'):
        allowed |= parts[2] in WORKER_FILES
    if len(parts) == 5 and parts[0] == 'workers' and parts[1] in ('0', '1', '2', '3') and parts[2] == 'arms' and parts[3] in ARMS:
        allowed |= parts[4] in ARM_FILES
    if len(parts) == 3 and parts[0] == '.output-generations' and re.fullmatch('[0-9a-f]{32}', parts[1]):
        allowed |= parts[2] in OUTPUT_FILES | {'manifest.json'}
    require(allowed, 'unrecognized E12 runtime archive member: ' + name)
    return 'temporary' if normalized != name else 'runtime'


def reject_truth(value):
    if type(value) is dict:
        require(not TRUTH_FIELDS.intersection(value) and
                value.get('contains_evaluator_truth', False) is False and
                value.get('correctness_scored', False) is False, 'evaluator truth forbidden')
        for child in value.values(): reject_truth(child)
    elif type(value) is list:
        for child in value: reject_truth(child)


def data_json(body):
    """Typed JSON values, including inventory arrays; duplicate keys still fail."""
    return parse(b'{"value":' + body + b'}', limit=8*1024**2+32)['value']


def validate_artifact(name, body, plan, *, uncommitted_generation=False):
    kind = member_kind(name, plan)
    if kind == 'static':
        require(hashlib.sha256(body).hexdigest() == plan['payload_sha256'][name], 'static payload hash differs: ' + name)
        return
    normalized = re.sub(r'(?:\.[0-9a-f]{32})?\.tmp$', '', name)
    if not normalized.endswith(('.json', '.jsonl')): return
    require(not normalized.endswith('.json') or bool(body.strip()) or kind == 'temporary' or uncommitted_generation,
            'empty committed JSON evidence forbidden')
    partial = False
    lines = body.splitlines(keepends=True) if normalized.endswith('.jsonl') else [body]
    for index, line in enumerate(lines):
        if not line.strip(): continue
        try:
            reject_truth(data_json(line))
        except (json.JSONDecodeError, UnicodeDecodeError):
            require(kind == 'temporary' or uncommitted_generation or normalized.endswith('.jsonl') and index == len(lines)-1 and not line.endswith(b'\n'),
                    'corrupt committed JSON cannot be relabeled partial')
            partial = True
            for match in re.finditer(r'"((?:[^"\\]|\\.)*)"\s*:', line.decode('utf-8', errors='replace')):
                key = json.loads('"' + match[1] + '"')
                require(key not in TRUTH_FIELDS, 'evaluator marker forbidden in partial evidence')
                if key in ('contains_evaluator_truth', 'correctness_scored'):
                    suffix = line.decode('utf-8', errors='replace')[match.end():].lstrip()
                    require(suffix.startswith('false') or 'false'.startswith(suffix), 'evaluated partial evidence forbidden')
    return partial or normalized.endswith('.json') and not body.strip()


def validate_runtime_artifacts(bodies, plan):
    selected = data_json(bodies['output-commit.json']).get('generation') if 'output-commit.json' in bodies else None
    partials = []
    for name, body in sorted(bodies.items()):
        parts = name.split('/')
        uncommitted = (len(parts) == 3 and parts[0] == '.output-generations' and selected != parts[1] and
                       ('/'.join(parts[:2])+'/manifest.json' not in bodies or parts[2] == 'manifest.json'))
        if validate_artifact(name, body, plan, uncommitted_generation=uncommitted):
            partials.append(dict(path=name, kind='uncommitted generation member' if uncommitted else
                                'uncommitted temporary JSON' if name.endswith('.tmp') else 'uncommitted final ledger tail', qualified=False))
    if 'interrupted-retention.json' in bodies:
        require(canonical(data_json(bodies['interrupted-retention.json'])) == canonical(interrupted_index(partials)),
                'recomputed interrupted-artifact index differs')
    return partials


def interrupted_index(partials):
    return dict(format='irisx/unqualified-interrupted-artifacts-v1', artifacts=partials,
                promotion=False, candidate_qualification=False)


def validate_completed_workers(names, read_json, proof):
    """Inventory completeness only; never claims native numerical validation."""
    names = set(names)
    if proof['terminal'] is not None and proof['terminal'].get('outcome') == 'complete':
        require(set(proof['launches']) == {'0', '1', '2', '3'} and
                all(proof['launches'][rank] is not None and 'workers/'+rank+'/result.json' in names
                    for rank in proof['launches']), 'complete coordinator requires all four worker evidence records')
    for rank, launch in proof['launches'].items():
        name = 'workers/' + rank + '/result.json'
        if name in names:
            result = read_json(name)
            if result.get('outcome') == 'complete':
                require(launch is not None and canonical(result.get('binding')) == canonical(launch['binding']),
                        'complete worker result launch binding differs')
                require(all('workers/' + rank + '/arms/' + arm + '/' + leaf in names
                            for arm in ARMS for leaf in ARM_FILES),
                        'complete worker requires both explicit E12 arm evidence inventories')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def parse(body, *, limit=MAX_JSON_BYTES):
    require(type(body) is bytes and len(body) <= limit, 'bounded JSON bytes required')

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
    receipt = observation.get('e12_supervision', {})
    require(type(receipt) is dict, 'supervision object required')
    start = receipt.get('started_monotonic')
    require(finite(start) and start >= 0 and receipt.get('format') == 'irisx/e12-supervision-v1' and
            all(finite(receipt.get(key)) and receipt[key] == start + offset for key, offset in (
                ('term_deadline_monotonic', 3290), ('kill_deadline_monotonic', 3299.8),
                ('stop_deadline_monotonic', 3300), ('finalizer_deadline_monotonic', 3600))) and
            observation.get('hard_deadline_monotonic') == start + 3600 and
            observation.get('confirmed_stopped') is True and
            type(observation.get('output_capture')) is dict and observation['output_capture'].get('written') is True and
            type(receipt.get('errors')) is list and
            all(finite(receipt.get(key)) for key in ('capture_finished_monotonic', 'finished_monotonic')) and
            start <= receipt['capture_finished_monotonic'] <= receipt['finished_monotonic'] <= start + 3300,
            'bounded confirmed outer stop/capture required')
    require(observation.get('reserve_preserved') is receipt.get('reserve_preserved') is (not bool(receipt['errors'])) and
            receipt.get('finalization_remaining_seconds') == start + 3600 - receipt['finished_monotonic'],
            'literal reserve observation and remaining clock budget required')
    error_cleanup = False
    failure_start = receipt.get('failure_cleanup_started_monotonic')
    if failure_start is not None:
        error_cleanup = (receipt.get('supervisor_error_cleanup') is True and bool(receipt['errors']) and
            finite(failure_start) and finite(receipt.get('coordinator_stopped_monotonic')) and
            start <= failure_start <= receipt['coordinator_stopped_monotonic'] and
            receipt.get('failure_cleanup_deadline_monotonic') == min(failure_start + 10, start + 3300) and
            receipt['coordinator_stopped_monotonic'] <= receipt['failure_cleanup_deadline_monotonic'])
        require(error_cleanup, 'bounded supervision-error cleanup receipt required')
    for key, offset in (('term_requested_monotonic', 3290), ('kill_requested_monotonic', 3299.8)):
        stamp = receipt.get(key)
        require(stamp is None or finite(stamp) and start <= stamp <= receipt['finished_monotonic'] and
                (stamp >= start + offset or key == 'kill_requested_monotonic' and
                    (receipt.get('orphaned_group_observed') is True or error_cleanup and failure_start <= stamp)),
                'signal request monotonic ordering differs')
    require(set(launches) <= {'0', '1', '2', '3'}, 'closed worker identities required')
    if observation.get('launched') is False:
        proven_rejection = observation.get('launch_failed') is True
        unattempted_preflight = (observation.get('prelaunch_failed') is True and
            observation.get('launch_attempted') is False and observation.get('launch_failed') is False)
        require((proven_rejection or unattempted_preflight) and observation.get('launch_uncertain', False) is False and
                observation.get('returncode') is None and
                observation.get('coordinator_pid') is None and observation.get('coordinator_process_group_id') is None and
                observation.get('coordinator_start_new_session') is None and
                terminal is None and launches == {} and bool(receipt['errors']),
                'unambiguous prelaunch failure required')
        return proof
    require(observation.get('launched') is True and type(observation.get('returncode')) is int and
            type(observation.get('coordinator_pid')) is type(observation.get('coordinator_process_group_id')) is int and
            observation['coordinator_pid'] == observation['coordinator_process_group_id'] > 1 and
            observation.get('coordinator_start_new_session') is True and
            receipt.get('coordinator_group_absent') is True and
            finite(receipt.get('coordinator_stopped_monotonic')) and
            start <= receipt['coordinator_stopped_monotonic'] <= receipt['capture_finished_monotonic'],
            'coordinator stop observations required')
    if terminal is None:
        require(launches == {} and observation['returncode'] != 0,
                'failed pre-admission coordinator and zero worker launches required')
        return proof
    require(type(terminal) is dict and terminal.get('plan_digest') == 'sha256:' + plan_sha256,
            'exact-plan terminal stop observation required')
    cleanup = terminal.get('cleanup', {})
    require(type(cleanup) is dict and cleanup.get('format') == 'irisx/e12-collective-cleanup-v1' and
            cleanup.get('deadline_monotonic') == start + 3299.8 and
            cleanup.get('all_producers_stopped') is cleanup.get('complete_before_deadline') is True and
            cleanup.get('timed_out') is False and cleanup.get('secondary_errors') == [] and
            finite(cleanup.get('started_monotonic')) and finite(cleanup.get('finished_monotonic')) and
            start <= cleanup['started_monotonic'] <= cleanup['finished_monotonic'] <= start + 3299.8 and
            cleanup['finished_monotonic'] <= receipt['coordinator_stopped_monotonic'] and
            type(cleanup.get('workers')) is list and len(cleanup['workers']) == len(launches),
            'all registered producers must be confirmed stopped')
    seen = set(); pids = {observation['coordinator_pid']}
    for row in cleanup['workers']:
        require(type(row) is dict and type(row.get('identity')) is str and
                row['identity'] in launches and row['identity'] not in seen, 'unique cleanup worker required')
        seen.add(row['identity']); launch = launches[row['identity']]
        if row.get('pid') is None:
            require(launch is None and row.get('stop_attempted') is False, 'unlaunched worker receipt differs')
            continue
        require(type(launch) is dict and launch.get('format') == 'irisx/e12-owned-worker-launch-v1' and
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
                plan.get('maximum_notebook_wall_seconds') == 3600, 'runtime exact run/plan differs')
        validate_plan(plan, run_id)
        if 'plan.json' in names:
            plan_raw, _ = json_member(archive, 'plan.json', deadline)
            require(hashlib.sha256(plan_raw).hexdigest() == plan_sha256, 'runtime plan copies differ')
        for name in ('outer-supervision.json', 'e12-supervision-observation.json'):
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
            require(fallback, 'closed E12 diagnostic marker required')
        require(fallback or set(plan['payload_sha256']) <= names, 'complete pinned payload inventory required')
        if not fallback:
            validate_completed_workers(names, lambda name: json_member(archive, name, deadline)[1], proof)
        require(worker_ids <= set(proof['launches']) and
                (fallback or worker_ids == set(proof['launches'])), 'archived worker inventory differs from stop proof')
        if proof['terminal'] is None:
            require('bootstrap-failure.json' in names and 'coordinator-admitted.json' not in names and
                    not any(name.startswith('workers/') for name in names) and
                    not {'terminal.json', 'terminal-fallback.json'} & names and fallback, 'prelaunch archive differs')
            if proof['observation'].get('launched') is True:
                require('e12-pre-admission-observation.json' in names, 'pre-admission observation missing')
                bootstrap = json_member(archive, 'e12-pre-admission-observation.json', deadline)[1]
                require(bootstrap.get('format') == 'irisx/e12-pre-admission-failure-v1' and
                        bootstrap.get('run_id') == run_id and bootstrap.get('plan_sha256') == plan_sha256 and
                        bootstrap.get('coordinator_admitted') is False and bootstrap.get('worker_directory_exists') is False,
                        'explicit observed pre-admission failure required')
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
        bodies = {}
        for row in archive.infolist():
            member_kind(row.filename, plan)
            with archive.open(row) as member:
                info = stream_digest(member, deadline, row.file_size)
                require(info['size'] == row.file_size, 'runtime member size differs')
            require(row.file_size <= 8*1024**2, 'bounded individual runtime evidence required')
            check_time(deadline)
            bodies[row.filename] = archive.read(row)
            check_time(deadline)
        validate_runtime_artifacts(bodies, plan)
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
                item.get('format') == 'irisx/e12-finalization-timing-v1' and item.get('plan_sha256') == plan_sha256 and
                item.get('hard_deadline_monotonic') == proof['observation']['hard_deadline_monotonic'] and
                item.get('correctness_scored') is item.get('promotion') is False and
                type(item.get('receipt_written')) is type(item.get('finalization_qualified')) is bool and
                item.get('archive_exists') is True and type(item.get('archive_size')) is int and
                item['archive_size'] == runtime['size'] and
                (item.get('archive_sha256') is None or item['archive_sha256'] == runtime['sha256']) and
                type(item.get('stages')) is dict and set(item['stages']) <= set(STAGES), 'receipt plan/archive binding differs')
        previous = proof['observation']['e12_supervision']['finished_monotonic']
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
                proof['observation']['e12_supervision']['errors'] == [],
                'qualified completion lacks full observed closure')
    item = receipt if receipt is not None else sidecar
    return dict(evidence_kind=('post_write_result' if receipt and receipt['receipt_written'] else
                               'incomplete_result' if receipt else 'sidecar_only' if sidecar else 'unknown'),
                archive_binding=('verified' if item and item['archive_sha256'] is not None else 'unknown'),
                observed_finalization_qualified=receipt['finalization_qualified'] if receipt else None,
                runtime_qualification='diagnostic_only' if diagnostic else 'not_assessed',
                runtime_outcome=(proof['terminal'].get('outcome') if proof['terminal'] is not None else
                    'pre_admission_failure' if proof['observation'].get('launched') is True else 'prelaunch_failure'),
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
    require(proof['observation']['e12_supervision']['finished_monotonic'] <= started,
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

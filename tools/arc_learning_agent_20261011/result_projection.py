"""Truth-free, lossless prediction projection before the owned worker exits.

Only task-local ``evidence`` is omitted from the seal-facing aggregation. Full
owner bytes and every unchanged task result remain separately hash-bound. The
pure projection also supports explicit historical recovery; it never invents a
new process-closure proof or changes an original source/request identity.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from tools.arc_kaggle_submission import challenge_counts, grid, parse_json
from tools.arc_learning_agent_20261011.budget import atomic_json, canonical, digest, finite, DEFAULT_CAPS
from tools.arc_learning_agent_20261011.evaluation import POLICIES
from tools.arc_public_research_20261010.public_data import MAX_FILE_BYTES, hash_string, read_regular, safe_path

FULL_OWNER_MAX_BYTES = 64 * 1024**2
PROJECTION_FORMAT = 'irisx/learning-owner-projection-v1'
OWNER_FIELDS = {'format', 'run_id', 'status', 'source_identity_sha256', 'request_sha256',
    'solver_manifest_sha256', 'prediction_origin', 'production_model', 'model_stopped',
    'results', 'stages', 'stage_clock', 'training_steps', 'charged_training_microbatches',
    'physical_usage', 'pending_work', 'elapsed_seconds'}
TASK_FIELDS = {'task_id', 'policies', 'evidence', 'physical_usage', 'status', 'stop_reasons'}
TASK_COUNTERS = {'generation_calls', 'scoring_forwards', 'input_tokens', 'output_tokens',
    'optimizer_steps', 'supervised_tokens', 'cpu_checks', 'program_gas', 'unknown_usage_events',
    'model_forward_calls', 'forward_input_tokens', 'generation_attempts', 'scoring_attempts', 'cpu_attempts'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value):
    return type(value) is int and value >= 0


def _document(raw, limit, name):
    _require(type(raw) is bytes and 0 < len(raw) <= limit, 'bounded ' + name + ' bytes required')
    value = parse_json(raw)
    # Also rejects nonfinite overflow (e.g. 1e999) and preserves JSON types.
    canonical(value)
    _require(type(value) is dict, name + ' object required')
    return value


def _binding(path, raw):
    return {'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _validate_owner(owner, request, challenges):
    _require(set(owner) == OWNER_FIELDS and owner['format'] == 'irisx/learning-owner-result-v1',
             'full owner schema differs')
    _require(type(request) is dict and request.get('format') == 'irisx/learning-owner-request-v1',
             'owner request schema differs')
    source = request.get('source_identity')
    _require(type(source) is dict and bool(source), 'source identity required')
    for value in source.values():
        hash_string(value)
    _require(owner['source_identity_sha256'] == digest(source) and owner['request_sha256'] == digest(request),
             'foreign owner source/request binding')
    _require(type(owner['run_id']) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', owner['run_id']) and
             owner['run_id'] == request.get('run_id'), 'foreign owner run binding')
    hash_string(owner['solver_manifest_sha256'])
    _require(owner['solver_manifest_sha256'] == request.get('solver_manifest_sha256'), 'foreign solver result')
    _require(owner['status'] in ('complete', 'partial') and owner['model_stopped'] is True,
             'stopped terminal owner required')
    _require(type(owner['pending_work']) is dict and not owner['pending_work'], 'unknown work blocks projection')
    config = request.get('config')
    _require(type(config) is dict and type(config.get('tiny_cpu', False)) is bool, 'owner configuration differs')
    expected_origin = 'synthetic_cpu' if config.get('tiny_cpu') else 'trained_model_research'
    _require(owner['prediction_origin'] in (expected_origin, 'model_disabled') and
             owner['production_model'] is (owner['prediction_origin'] == 'trained_model_research'),
             'prediction origin/production attribution differs')
    _require(type(owner['stages']) is dict and type(owner['stage_clock']) is list, 'stage diagnostics required')
    finite(owner['elapsed_seconds'], 'owner elapsed seconds')
    _require(_integer(owner['training_steps']) and _integer(owner['charged_training_microbatches']),
             'training counters differ')
    usage = owner['physical_usage']
    _require(type(usage) is dict and set(usage) == {'caps', 'charged', 'pending', 'events', 'last_sha256'},
             'owner physical usage schema differs')
    _require(type(usage['caps']) is dict and type(usage['charged']) is dict and
             set(usage['caps']) == set(DEFAULT_CAPS) == set(usage['charged']), 'physical counter schema differs')
    for name, cap in usage['caps'].items():
        _require(_integer(cap) and cap <= DEFAULT_CAPS[name] and _integer(usage['charged'][name]) and
                 usage['charged'][name] <= cap, 'invalid physical counter or cap')
    _require(type(usage['pending']) is dict and not usage['pending'] and _integer(usage['events']),
             'unknown physical work blocks projection')
    hash_string(usage['last_sha256'])
    _require(owner['charged_training_microbatches'] == usage['charged']['training_steps'] and
             owner['training_steps'] <= owner['charged_training_microbatches'], 'training cost counters differ')
    counts = challenge_counts(challenges)
    _require(len(counts) == 120 and sum(counts.values()) == 167, 'PUBLIC120 task/query cardinality differs')
    _require(all(re.fullmatch(r'[0-9a-f]{8}', key) for key in counts), 'unsafe PUBLIC120 task ID')
    scheduled = sorted(counts, key=lambda key: (digest(['declared-task-order', config.get('seed', 0), key]), key))
    if config.get('tiny_cpu'):
        size = config.get('fixture_tasks', 2)
        _require(_integer(size) and size <= 120, 'fixture task cardinality differs')
        scheduled = scheduled[:size]
    results = owner['results']
    _require(type(results) is dict and set(results) <= set(scheduled), 'foreign or unscheduled task results')
    _require(owner['status'] != 'complete' or set(results) == set(scheduled), 'complete task cardinality differs')
    _require(owner['prediction_origin'] != 'model_disabled' or
             (not results and owner['training_steps'] == 0), 'disabled model cannot claim predictions/training')
    return counts


def _validate_task(task_id, row, count):
    _require(type(row) is dict and set(row) == TASK_FIELDS and row['task_id'] == task_id,
             'task result schema/identity differs')
    _require(row['status'] in ('complete', 'budget_stopped', 'error'), 'task lifecycle not closed')
    _require(type(row['stop_reasons']) is list and all(type(x) is str for x in row['stop_reasons']) and
             type(row['evidence']) is list, 'task diagnostics differ')
    usage = row['physical_usage']
    _require(type(usage) is dict and set(usage) == TASK_COUNTERS | {'events', 'logical_policies_share_physical_work'} and
             type(usage['events']) is list and usage['logical_policies_share_physical_work'] is True and
             all(_integer(usage[k]) for k in TASK_COUNTERS), 'task physical usage schema differs')
    policies = row['policies']
    _require(type(policies) is dict and set(policies) == set(POLICIES), 'exact policy set required')
    for items in policies.values():
        _require(type(items) is list and len(items) == count, 'multi-test policy cardinality differs')
        for item in items:
            _require(type(item) is dict and set(item) == {'candidates', 'status', 'evidence_ids'},
                     'policy item schema differs')
            candidates = item['candidates']
            _require(type(candidates) is list and len(candidates) <= 2, 'top-two candidates required')
            for candidate in candidates:
                grid(candidate)
            _require(len({digest(candidate) for candidate in candidates}) == len(candidates), 'duplicate candidates')
            expected_status = 'complete' if len(candidates) == 2 else 'partial' if candidates else 'missing'
            _require(item['status'] == expected_status and type(item['evidence_ids']) is list and
                     all(type(x) is str for x in item['evidence_ids']), 'policy status/evidence differs')


def project_owner_result(full_raw, *, request, challenges, task_details):
    """Return the deterministic <=16MiB projection, without I/O or scoring.

    ``full_raw`` is the exact full owner JSON bytes (<=64MiB); ``task_details``
    maps exactly the reported task IDs to their unchanged full result bytes.
    Neither supplied request/source identities nor any prediction is rewritten.
    """
    owner = _document(full_raw, FULL_OWNER_MAX_BYTES, 'full owner')
    counts = _validate_owner(owner, request, challenges)
    _require(type(task_details) is dict and set(task_details) == set(owner['results']),
             'missing or extra task detail')
    bindings = {}
    policies = {}
    for task_id, row in owner['results'].items():
        _validate_task(task_id, row, counts[task_id])
        detail_raw = task_details[task_id]
        detail = _document(detail_raw, MAX_FILE_BYTES, 'task detail')
        _require(canonical(detail) == canonical(row), 'task detail differs from full owner')
        bindings[task_id] = _binding('tasks/' + task_id + '/result.json', detail_raw)
        policies[task_id] = row['policies']
        # This is the sole omission. Physical events, status and counters remain.
        del row['evidence']
    owner['result_projection'] = {'format': PROJECTION_FORMAT, 'omitted_task_fields': ['evidence'],
        'full_owner': _binding('owner-evidence.json', full_raw), 'task_details': bindings,
        'policies_sha256': digest(policies)}
    _require(len(canonical(owner)) <= MAX_FILE_BYTES, 'projected owner exceeds16MiB cap')
    return owner


def verify_owner_projection(projected, *, full_raw, request, challenges, task_details):
    """Verify all projection fields and exact full-file byte bindings."""
    expected = project_owner_result(full_raw, request=request, challenges=challenges, task_details=task_details)
    _require(canonical(projected) == canonical(expected), 'owner projection or evidence binding differs')
    return True


def verify_written_owner_result(root, *, request, challenges):
    """Read bounded files at fixed, symlink-rejecting paths and verify bindings."""
    root = safe_path(Path(root).absolute())
    projected = _document(read_regular(root / 'result.json'), MAX_FILE_BYTES, 'projected owner')
    full_raw = read_regular(root / 'owner-evidence.json', limit=FULL_OWNER_MAX_BYTES)
    owner = _document(full_raw, FULL_OWNER_MAX_BYTES, 'full owner')
    _validate_owner(owner, request, challenges)  # Validate IDs before resolving paths.
    details = {key: read_regular(root / 'tasks' / key / 'result.json') for key in owner['results']}
    verify_owner_projection(projected, full_raw=full_raw, request=request, challenges=challenges, task_details=details)
    return projected


def write_owner_result(result, *, request, challenges):
    """Publish fresh full evidence, then verified compact bytes before owner exit.

    A failed projection retains full diagnostics and never creates result.json.
    Full evidence cannot be replaced by another invocation of this writer.
    """
    root = safe_path(Path(request['output_root']).absolute())
    _require(not (root / 'result.json').exists(), 'result identity consumed')
    full_raw = canonical(result)
    _require(len(full_raw) <= FULL_OWNER_MAX_BYTES, 'full owner exceeds64MiB cap')
    atomic_json(root / 'owner-evidence.json', result, exclusive=True)
    (root / 'owner-evidence.json').chmod(0o444)
    full_raw = read_regular(root / 'owner-evidence.json', hashlib.sha256(full_raw).hexdigest(),
                            limit=FULL_OWNER_MAX_BYTES)
    owner = _document(full_raw, FULL_OWNER_MAX_BYTES, 'full owner')
    _validate_owner(owner, request, challenges)
    details = {key: read_regular(root / 'tasks' / key / 'result.json') for key in owner['results']}
    projected = project_owner_result(full_raw, request=request, challenges=challenges, task_details=details)
    atomic_json(root / 'result.json', projected, exclusive=True)
    return verify_written_owner_result(root, request=request, challenges=challenges)

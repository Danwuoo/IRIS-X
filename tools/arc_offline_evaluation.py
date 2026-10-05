"""Solver-neutral, evaluator-only ARC reports. No solver or provider execution.

Uses the existing challenge/grid validators and canonical digest convention.
Answers and diagnostic rows stay in this module's local evaluator boundary.
"""
from __future__ import annotations

from collections import Counter
import math
from pathlib import Path
import re

from tools.arc_kaggle_submission import challenge_counts, grid, parse_json, require
from tools.nvarc_native_multitask import digest

POOL_FORMAT = 'irisx/arc-offline-pools-v1'
REPORT_FORMAT = 'irisx/arc-offline-evaluation-v1'
OFFICIAL_FORMAT = 'irisx/arc-official-observation-v1'
REFERENCE_REPOSITORY = 'https://github.com/arcprize/ARC-AGI-2.git'
REFERENCE_COMMIT = 'f3283f727488ad98fe575ea6a5ac981e4a188e49'
RUNTIME_FIELDS = {'training_seconds', 'search_seconds', 'verification_seconds',
                  'other_seconds', 'solve_seconds', 'reset_seconds', 'total_seconds'}


def load_pinned_reference(root, provenance_path):
    """Check all 120 preserved files against the existing digest-bound artifact.

    Full public source answers are stripped here and returned separately, only
    to the evaluator. No task ID or input hash alone establishes source parity.
    """
    from irisx.artifacts import load_artifact
    from irisx.arc_agi2 import validate_task
    import hashlib

    provenance = load_artifact(Path(provenance_path), kind='irisx/arc-source-provenance')['payload']
    require(provenance['repository'] == REFERENCE_REPOSITORY and
            provenance['commit'] == REFERENCE_COMMIT, 'pinned reference provenance required')
    rows = [r for r in provenance['files'] if r['path'].startswith('data/evaluation/')]
    paths = {r['path'] for r in rows}
    root = Path(root)
    actual = {p.relative_to(root).as_posix() for p in (root/'data/evaluation').glob('*.json')}
    require(len(rows) == len(paths) == 120 and actual == paths, 'complete reference file inventory required')
    challenges, solutions, hashes = {}, {}, {}
    for row in sorted(rows, key=lambda r: r['path']):
        path = root/row['path']
        require(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(), 'regular reference file required')
        body = path.read_bytes(); sha = hashlib.sha256(body).hexdigest()
        require(len(body) == row['byte_size'] and 'sha256:'+sha == row['content_digest'],
                'reference file digest differs: '+row['path'])
        task = validate_task(parse_json(body), row['path'], require_test_outputs=True)
        key = path.stem
        challenges[key] = {'train': task['train'], 'test': [{'input': t['input']} for t in task['test']]}
        solutions[key] = [t['output'] for t in task['test']]
        hashes[row['path']] = sha
    require(sum(challenge_counts(challenges).values()) == 167, 'pinned 120-task/167-test reference required')
    return challenges, solutions, {'repository': REFERENCE_REPOSITORY, 'commit': REFERENCE_COMMIT,
        'file_inventory_digest': digest(hashes),
        'provenance_sha256': hashlib.sha256(Path(provenance_path).read_bytes()).hexdigest(),
        'challenges_digest': digest(challenges), 'tasks': 120, 'tests': 167}


def content_identity(challenges):
    counts = challenge_counts(challenges)
    return {'challenges_digest': digest(challenges), 'tasks': len(counts), 'tests': sum(counts.values()),
        'task_identities': {k: {'task_digest': digest(t), 'demonstrations_digest': digest(t['train']),
                              'test_input_digests': [digest(v['input']) for v in t['test']]}
                            for k, t in sorted(challenges.items())}}


def compare_sources(challenges, reference):
    """Unique content join; reordered/extra tests never imply an exact execution.

    Ambiguous duplicate inputs are rejected rather than choosing an answer or
    silently dropping tests. All projection labels are retrospective.
    """
    executed = content_identity(challenges); pinned = content_identity(reference)
    matches, differences = [], []
    common = sorted(set(challenges) & set(reference))
    for key in common:
        task, original = challenges[key], reference[key]
        same_demo = task['train'] == original['train']
        used = set()
        for j, pair in enumerate(original['test']):
            indexes = [i for i, value in enumerate(task['test']) if value['input'] == pair['input']]
            require(len(indexes) <= 1, 'ambiguous multi-test input identity: '+key)
            if indexes:
                index = indexes[0]
                require(index not in used, 'ambiguous reference multi-test identity: '+key)
                used.add(index)
                matches.append({'task_id': key, 'test_index': index, 'reference_test_index': j,
                    'input_digest': digest(pair['input']), 'same_demonstrations': same_demo})
        if task != original:
            differences.append({'task_id': key, 'same_demonstrations': same_demo,
                'executed_tests': len(task['test']), 'reference_tests': len(original['test']),
                'unmatched_executed_tests': sorted(set(range(len(task['test'])))-used)})
    return {'executed': executed, 'reference': pinned,
        'exact_reference_input_content': challenges == reference,
        'exact_pinned_input_content': None,  # requires separate verified pinned-source provenance
        'common_task_ids': len(common),
        'exact_task_content_matches': sum(challenges[k] == reference[k] for k in common),
        'changed_demonstration_tasks': sum(challenges[k]['train'] != reference[k]['train'] for k in common),
        'unmatched_task_ids': sorted(set(challenges)-set(reference)),
        'missing_reference_task_ids': sorted(set(reference)-set(challenges)),
        'matched_test_inputs': len(matches),
        'matched_test_inputs_and_demonstrations': sum(r['same_demonstrations'] for r in matches),
        'differences': differences, 'matches': matches,
        'projection_qualification': 'filtered retrospective projection of existing execution; not a new canonical benchmark run'}


def validate_pools(challenges, pools):
    """Strict truth-free interchange, sparse tasks/tests allowed, denominator fixed."""
    counts = challenge_counts(challenges)
    require(set(pools) == {'format', 'run_id', 'method', 'challenges_digest', 'records', 'parent_wall_seconds'} and
            pools['format'] == POOL_FORMAT, 'offline pool envelope schema differs')
    require(isinstance(pools['run_id'], str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', pools['run_id']) and
            isinstance(pools['method'], str) and 0 < len(pools['method']) <= 200, 'run/method labels required')
    require(pools['challenges_digest'] == digest(challenges), 'pool source content identity differs')
    _seconds(pools['parent_wall_seconds'])
    require(isinstance(pools['records'], list), 'pool records array required')
    records = {}
    for record in pools['records']:
        require(set(record) == {'task_id', 'task_digest', 'tests', 'timings'}, 'truth-free task record schema differs')
        key = record['task_id']
        require(key in counts and key not in records and record['task_digest'] == digest(challenges[key]),
                'unique full multi-test task identity required')
        require(isinstance(record['timings'], dict) and set(record['timings']) <= RUNTIME_FIELDS,
                'observed timing fields only')
        for value in record['timings'].values(): _seconds(value)
        require(isinstance(record['tests'], list), 'test records array required')
        seen = set()
        for test in record['tests']:
            require(set(test) == {'test_index', 'input_digest', 'ranked_grids', 'status'},
                    'truth-free test record schema differs')
            i = test['test_index']
            require(type(i) is int and 0 <= i < counts[key] and i not in seen and
                    test['input_digest'] == digest(challenges[key]['test'][i]['input']),
                    'unique test index/input content identity required')
            require(test['status'] in {'complete', 'partial', 'failed', 'not_executed'}, 'test status differs')
            pool = test['ranked_grids']
            require(isinstance(pool, list) and len(pool) <= 64, 'bounded candidate array required')
            for value in pool: grid(value)
            require(len({digest(g) for g in pool}) == len(pool), 'unique candidate grids required')
            require(not pool or test['status'] in {'complete', 'partial'}, 'failed/unexecuted test cannot retain candidates')
            seen.add(i)
        records[key] = record
    return records


def _seconds(value):
    require(value is None or type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'nonnegative finite observed seconds or null required')


def metric(numerator, denominator, unit='test'):
    return {'numerator': numerator, 'denominator': denominator,
            'value': numerator/denominator if denominator else None, 'unit': unit}


def aggregate(rows):
    counts = Counter(r['task_id'] for r in rows)
    solved = Counter(r['task_id'] for r in rows if r['pass2'])
    n = len(rows)
    metrics = {name: metric(sum(bool(r[field]) for r in rows), n) for name, field in
               [('pass_at_1', 'pass1'), ('pass_at_2', 'pass2'), ('candidate_oracle', 'oracle'),
                ('candidate_coverage', 'coverage'), ('empty_pool', 'empty_pool'),
                ('pool_miss', 'pool_miss'), ('ranking_miss', 'ranking_miss')]}
    metrics['partial_pool'] = metric(sum(r['pool_size'] == 1 for r in rows), n)
    metrics['unobserved_test_record'] = metric(sum(not r['record_observed'] for r in rows), n)
    metrics['task_average_pass_at_2'] = metric(sum(solved[k]/v for k, v in counts.items()), len(counts), 'task')
    metrics['tasks_all_tests_pass_at_2'] = metric(sum(solved[k] == v for k, v in counts.items()), len(counts), 'task')
    require(sum(metrics[name]['numerator'] for name in ('pass_at_2', 'empty_pool', 'pool_miss', 'ranking_miss')) == n,
            'exclusive candidate-loss accounting differs')
    return {'tasks': len(counts), 'tests': n, 'aggregation': 'test-micro, task-macro and whole-task success reported separately',
            'metrics': metrics, 'candidate_total': sum(r['pool_size'] for r in rows)}


def runtime_summary(challenges, records, parent_wall_seconds):
    def phase(field):
        values = [records.get(k, {}).get('timings', {}).get(field) for k in challenges]
        known = [v for v in values if v is not None]
        return {'state': 'observed' if len(known) == len(values) else 'partial' if known else 'unknown',
                'seconds': sum(known) if len(known) == len(values) else None,
                'observed_seconds': sum(known) if known else None,
                'observed_tasks': len(known), 'task_denominator': len(values), 'scope': 'sum of worker task intervals'}
    return {'parent_wall': {'state': 'unknown' if parent_wall_seconds is None else 'observed',
                            'seconds': parent_wall_seconds, 'scope': 'elapsed parent interval, not sum of parallel workers'},
        'training': phase('training_seconds'), 'search': phase('search_seconds'),
        'verification': phase('verification_seconds'), 'other': phase('other_seconds'),
        'combined_test_solve': phase('solve_seconds'), 'reset_subinterval_of_other': phase('reset_seconds'),
        'worker_task_wall': phase('total_seconds'),
        'limitations': ['Unknown phases are not inferred from allowance, forward counts or wall-time residuals.',
                       'Combined solve intervals include preparation, search, verification and local bookkeeping.',
                       'Worker sums overlap in parallel; phases with different scopes must not be stacked.']}


def evaluate(challenges, solutions, pools):
    records = validate_pools(challenges, pools); counts = challenge_counts(challenges)
    require(isinstance(solutions, dict) and set(solutions) == set(counts), 'exact evaluator task denominator required')
    rows = []
    for key, count in sorted(counts.items()):
        require(isinstance(solutions[key], list) and len(solutions[key]) == count, 'exact evaluator multi-test denominator required')
        for answer in solutions[key]: grid(answer)
        tests = {t['test_index']: t for t in records.get(key, {}).get('tests', [])}
        for i in range(count):
            test = tests.get(i); pool = [] if test is None else test['ranked_grids']
            answer = solutions[key][i]
            one = bool(pool and pool[0] == answer); two = any(g == answer for g in pool[:2])
            oracle = any(g == answer for g in pool)
            rows.append({'task_id': key, 'test_index': i, 'task_digest': digest(challenges[key]),
                'demonstrations_digest': digest(challenges[key]['train']),
                'input_digest': digest(challenges[key]['test'][i]['input']),
                'pass1': one, 'pass2': two, 'oracle': oracle, 'coverage': bool(pool),
                'empty_pool': not pool, 'pool_miss': bool(pool) and not oracle,
                'ranking_miss': oracle and not two, 'pool_size': len(pool),
                'record_observed': test is not None, 'status': 'unobserved' if test is None else test['status']})
    return {'run_id': pools['run_id'], 'method': pools['method'], 'source_digest': digest(challenges),
        'development_metrics': aggregate(rows), 'rows': rows,
        'runtime': runtime_summary(challenges, records, pools['parent_wall_seconds']),
        'qualification': 'public development; exposure unresolved; no official or hidden score'}


def projections(evaluation, comparison):
    rows = {(r['task_id'], r['test_index']): r for r in evaluation['rows']}
    return {label: {'qualification': comparison['projection_qualification'],
                    'development_metrics': aggregate([rows[(m['task_id'], m['test_index'])] for m in comparison['matches']
                        if label == 'input_content_match' or m['same_demonstrations']])}
            for label in ('input_content_match', 'input_and_demonstration_match')}


def paired(left, right):
    require(left['source_digest'] == right['source_digest'], 'paired source content differs')
    identities = lambda report: [(r['task_id'], r['test_index'], r['task_digest'], r['input_digest'],
                                 r['demonstrations_digest']) for r in report['rows']]
    require(identities(left) == identities(right), 'paired full task/test identity differs')
    result = {'left': left['run_id'], 'right': right['run_id'], 'tests': len(left['rows'])}
    for label, field in [('pass_at_1', 'pass1'), ('pass_at_2', 'pass2'), ('candidate_oracle', 'oracle'),
                         ('candidate_coverage', 'coverage')]:
        counter = Counter(('both' if a[field] and b[field] else 'gain' if b[field] else
                           'loss' if a[field] else 'neither') for a, b in zip(left['rows'], right['rows']))
        result[label] = {k: counter[k] for k in ('both', 'gain', 'loss', 'neither')}
        result[label]['denominator'] = len(left['rows'])
    return result


def official_observation(value):
    """Offline recording only. COMPLETE + exception + null is never score zero."""
    fields = {'format', 'provider', 'competition', 'reference', 'kernel', 'kernel_version',
              'status', 'outcome', 'error', 'public_score', 'private_score', 'score_units',
              'observed_at', 'receipt_sha256'}
    require(isinstance(value, dict) and set(value) == fields and value['format'] == OFFICIAL_FORMAT,
            'official observation schema differs')
    for k in ('provider', 'competition', 'status', 'score_units', 'observed_at'):
        require(isinstance(value[k], str) and value[k], 'official observation label required: '+k)
    for k in ('reference', 'kernel', 'outcome', 'error'):
        require(value[k] is None or isinstance(value[k], str), 'official nullable text required: '+k)
    require(value['kernel_version'] is None or type(value['kernel_version']) is int and value['kernel_version'] > 0,
            'official version differs')
    require(value['receipt_sha256'] is None or re.fullmatch(r'[0-9a-f]{64}', value['receipt_sha256']), 'receipt hash differs')
    for k in ('public_score', 'private_score'):
        require(value[k] is None or type(value[k]) in (int, float) and math.isfinite(value[k]),
                'official score must be numeric or null; empty strings need explicit normalization')
    numeric = any(value[k] is not None for k in ('public_score', 'private_score'))
    return {**value, 'score_state': 'scored' if numeric else 'failed_without_score' if value['error'] else 'unavailable',
            'provider_requeried': False, 'development_metrics_are_official_score': False}

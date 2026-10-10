"""Frozen demo-fit selections and truth-free queries in bounded fresh processes.

The original demos-only verifier is unchanged. Generated source is never run as
host Python. Each input is interpreted by the pinned VM in its own Linux process.
"""
from __future__ import annotations

from pathlib import Path
import os
import re
import signal
import subprocess
import sys
import time

if __package__ in (None, ''):
    _root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(_root), str(_root / 'src')]

from tools.arc_consolidated_20261010 import arc_object_ir as ir, verifier
from tools.arc_kaggle_submission import grid, parse_json, require
from tools.arc_offline_evaluation import POOL_FORMAT, validate_pools
from tools.nvarc_native_multitask import digest
from tools.arc_public_research_20261010.public_data import (
    canonical, sha256, hash_value, hash_string, safe_path, read_regular, write_new, POLICIES)

PROTOCOL = 'irisx/public120-query-v1'
SELECTION_FORMAT = 'irisx/public120-frozen-selection-v1'
MAX_INPUTS = 167
MAX_RECEIPT_BYTES = verifier.MAX_RESPONSE_BYTES


def _name(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', value), 'safe call/run identity required')
    return value


def _validate_fit(row, task, run_id):
    require(type(row) is dict and set(row) in ({'candidate_id', 'run_id', 'plan', 'verification'},
            {'candidate_id', 'run_id', 'plan', 'verification', 'fit_call_id', 'fit_receipt_sha256'}),
            'candidate receipt schema differs')
    require(row['run_id'] == run_id, 'foreign candidate run')
    _name(row['candidate_id'])
    plan = ir.validate_plan(row['plan'])
    source = ir.compile_plan(plan)
    request = verifier._validate_request(source, task, verifier.MAX_WALL_SECONDS, verifier.MAX_STEPS)
    receipt = row['verification']
    extras = {'dispatched', 'gas_reserved', 'owned_descendants_stopped', 'gas_charged',
              'wall_reserved_seconds', 'wall_seconds'}
    require(type(receipt) is dict and extras <= set(receipt), 'fresh verifier transport receipt required')
    verifier._validate_receipt({k: v for k, v in receipt.items() if k not in extras}, request)
    require(receipt['dispatched'] is True and receipt['owned_descendants_stopped'] is True and
            type(receipt['gas_reserved']) is int and receipt['gas_reserved'] == verifier.MAX_STEPS and
            receipt['gas_charged'] == receipt['gas'] and
            receipt['wall_reserved_seconds'] == verifier.MAX_WALL_SECONDS and
            verifier._number(receipt['wall_seconds']), 'fresh bounded verification required')
    if 'fit_call_id' in row:
        _name(row['fit_call_id']); hash_string(row['fit_receipt_sha256'])
        require(row['fit_receipt_sha256'] == sha256(canonical(receipt) + b'\n'), 'fit receipt byte binding differs')
    return plan, receipt['known'] is True and receipt['all_demos_fit'] is True and receipt['status'] == 'fit'


def freeze_selections(challenges, ranked_candidates, *, run_id, policy, output_root):
    """Freeze full order and choose at most two distinct fitted plans before queries.

    Input rows are fresh verifier receipts obtained by the coordinator from its
    completed current-run ledger operations. No predicted grid/answer affects rank.
    """
    _name(run_id); require(policy in POLICIES, 'unknown policy')
    require(type(ranked_candidates) is dict and set(ranked_candidates) <= set(challenges), 'candidate task identities differ')
    selected, order = {}, {}
    for key, task in sorted(challenges.items()):
        rows = ranked_candidates.get(key, [])
        require(type(rows) is list and len(rows) <= 64, 'bounded candidate order required')
        identities, plans, chosen = set(), set(), []
        for row in rows:
            plan, fit = _validate_fit(row, {'task_id': key, 'demos': task['train']}, run_id)
            require(row['candidate_id'] not in identities, 'duplicate candidate identity')
            identities.add(row['candidate_id'])
            plan_hash = hash_value(plan)
            if fit and plan_hash not in plans and len(chosen) < (1 if policy in ('raw', 'strict') else 2):
                chosen.append({'candidate_id': row['candidate_id'], 'plan': plan, 'plan_sha256': plan_hash,
                               'verification_sha256': sha256(canonical(row['verification']) + b'\n')})
                plans.add(plan_hash)
        order[key] = rows
        selected[key] = chosen
    payload = {'format': SELECTION_FORMAT, 'run_id': run_id, 'policy': policy,
               'challenges_digest': digest(challenges), 'ordered_candidates': order,
               'selected': selected, 'sealed_at_ns': time.time_ns()}
    path = safe_path(output_root) / ('selection-' + policy + '.json')
    binding = write_new(path, payload)
    return {'selection': payload, 'selection_sha256': binding['sha256'], 'path': str(path)}


def _request(plan, value, selection_sha256):
    plan = ir.validate_plan(plan)
    if selection_sha256 is not None:
        hash_string(selection_sha256)
    return {'protocol': PROTOCOL, 'plan': plan, 'input': grid(value),
            'selection_sha256': selection_sha256, 'max_steps': verifier.MAX_STEPS}


def _worker():
    import resource
    if not verifier.capability()['available']:
        return 3
    for key, value in ((resource.RLIMIT_AS, verifier.MEMORY_BYTES),
                       (resource.RLIMIT_CPU, verifier.CPU_SECONDS),
                       (resource.RLIMIT_FSIZE, MAX_RECEIPT_BYTES), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(key, (value, value))
    try:
        raw = sys.stdin.buffer.read(verifier.MAX_REQUEST_BYTES + 1)
        require(len(raw) <= verifier.MAX_REQUEST_BYTES, 'query request limit')
        request = parse_json(raw)
        require(type(request) is dict and set(request) == {'protocol', 'plan', 'input', 'selection_sha256', 'max_steps'},
                'query request schema differs')
        require(request == _request(request['plan'], request['input'], request['selection_sha256']), 'query limits differ')
        source = ir.compile_plan(request['plan'])
        vm = verifier._load_interpreter(verifier._check_assets())
        result = {'request_sha256': hash_value(request), 'input_digest': digest(request['input']),
                  'status': 'invalid', 'output': None, 'gas': 0, 'reason': 'bounded program failed'}
        try:
            outcome = vm.execute_program(source, request['input'], vm.Limits(max_program_steps=verifier.MAX_STEPS))
            result.update(status='valid', output=grid(outcome['output']), gas=outcome['steps'], reason='valid grid')
        except vm.ProgramError as exc:
            result.update(gas=getattr(exc, 'steps', 0), reason=str(exc)[:160])
        sys.stdout.buffer.write(canonical(result)); sys.stdout.buffer.flush()
        return 0
    except (ValueError, OSError, MemoryError, RecursionError):
        return 4


def _query_one(request, root):
    require(verifier.capability()['available'], 'Linux query controls required; no fallback')
    root.mkdir()
    write_new(root / 'request.json', request)
    began = time.monotonic()
    status = {'request_sha256': hash_value(request), 'input_digest': digest(request['input']),
              'status': 'missing', 'output': None, 'gas': None, 'reason': 'worker receipt unavailable'}
    process = None
    with (root / 'request.json').open('rb') as incoming, (root / 'response.json').open('xb') as outgoing, \
            (root / 'stderr.txt').open('xb') as errors:
        try:
            process = subprocess.Popen([sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve()), '--worker'],
                stdin=incoming, stdout=outgoing, stderr=errors, cwd=root, close_fds=True, start_new_session=True,
                env={**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'CUDA_VISIBLE_DEVICES': ''})
            try:
                process.wait(timeout=max(.001, verifier.MAX_WALL_SECONDS - (time.monotonic() - began)))
            except subprocess.TimeoutExpired:
                verifier._terminate(process); status['reason'] = 'query wall timeout; killed and reaped'
            except BaseException:
                verifier._terminate(process); raise
        except OSError:
            status['reason'] = 'query process launch failed'
    if process is not None and process.returncode == 0:
        try:
            result = parse_json(read_regular(root / 'response.json', limit=MAX_RECEIPT_BYTES))
            require(type(result) is dict and set(result) == set(status), 'query response schema')
            require(result['request_sha256'] == status['request_sha256'] and result['input_digest'] == status['input_digest'],
                    'query receipt binding differs')
            require(result['status'] in ('valid', 'invalid') and type(result['gas']) is int and
                    0 <= result['gas'] <= verifier.MAX_STEPS and type(result['reason']) is str and
                    len(result['reason']) <= 160, 'query result accounting differs')
            if result['status'] == 'valid':
                grid(result['output'])
            else:
                require(result['output'] is None, 'invalid query has output')
            status = result
        except (ValueError, OSError):
            status['reason'] = 'query receipt invalid'
    status.update(dispatched=process is not None,
                  gas_charged=(verifier.MAX_STEPS if status['gas'] is None else status['gas']) if process else 0,
                  gas_reserved=verifier.MAX_STEPS if process else 0,
                  wall_seconds=time.monotonic() - began,
                  process_returncode=None if process is None else process.returncode,
                  owned_descendants_stopped=process is None or process.poll() is not None)
    return status


def query_execute(plan, inputs, output_root, call_id, *, selection_sha256=None):
    """Execute inputs only. Coordinator must reserve each input before dispatch."""
    _name(call_id)
    require(type(inputs) is list and 1 <= len(inputs) <= MAX_INPUTS, 'bounded nonempty query inputs required')
    plan = ir.validate_plan(plan)
    requests = [_request(plan, value, selection_sha256) for value in inputs]
    root = safe_path(output_root) / call_id
    require(not root.exists(), 'query call identity consumed')
    root.mkdir(parents=True)
    verifier._check_assets()
    started = time.time_ns()
    results = [_query_one(request, root / ('query-%03d' % i)) for i, request in enumerate(requests)]
    receipt = {'format': PROTOCOL, 'call_id': call_id, 'plan_sha256': hash_value(plan),
               'source_sha256': sha256(ir.compile_plan(plan).encode()), 'selection_sha256': selection_sha256,
               'started_at_ns': started, 'finished_at_ns': time.time_ns(), 'limits': verifier.known_limits(),
               'results': results, 'query_count': len(results), 'gas_charged': sum(r['gas_charged'] for r in results),
               'owned_descendants_stopped': all(r['owned_descendants_stopped'] for r in results)}
    write_new(root / 'receipt.json', receipt)
    return receipt


def build_policy_pool(challenges, selections, query_receipts, *, run_id, policy, parent_wall_seconds=None):
    """query_receipts is task_id -> [{candidate_id,test_index,receipt}, ...]."""
    frozen = selections['selection']; selection_hash = selections['selection_sha256']
    require(sha256(canonical(frozen) + b'\n') == selection_hash, 'selection seal differs')
    require(read_regular(selections['path'], selection_hash) == canonical(frozen) + b'\n', 'selection file differs')
    require(frozen['format'] == SELECTION_FORMAT and frozen['run_id'] == run_id and frozen['policy'] == policy and
            frozen['challenges_digest'] == digest(challenges), 'foreign selection')
    require(type(query_receipts) is dict and set(query_receipts) <= set(challenges), 'foreign query task')
    require(set(frozen) == {'format', 'run_id', 'policy', 'challenges_digest', 'ordered_candidates', 'selected', 'sealed_at_ns'}
            and type(frozen['sealed_at_ns']) is int and frozen['sealed_at_ns'] > 0
            and set(frozen['ordered_candidates']) == set(challenges) and set(frozen['selected']) == set(challenges),
            'complete frozen order required')
    for key, task in challenges.items():
        expected, seen, ids = [], set(), set()
        rows = frozen['ordered_candidates'][key]
        require(type(rows) is list and len(rows) <= 64, 'bounded frozen order required')
        for candidate in rows:
            plan, fit = _validate_fit(candidate, {'task_id': key, 'demos': task['train']}, run_id)
            require(candidate['candidate_id'] not in ids, 'duplicate frozen candidate')
            ids.add(candidate['candidate_id'])
            ph = hash_value(plan)
            if fit and ph not in seen and len(expected) < (1 if policy in ('raw', 'strict') else 2):
                expected.append({'candidate_id': candidate['candidate_id'], 'plan': plan, 'plan_sha256': ph,
                                 'verification_sha256': sha256(canonical(candidate['verification']) + b'\n')})
                seen.add(ph)
        require(frozen['selected'][key] == expected, 'selected plans differ from sealed demo-only order')
    records, global_calls = [], set()
    for key, task in sorted(challenges.items()):
        chosen = frozen['selected'][key]
        lookup, seen_calls = {}, set()
        for wrapper in query_receipts.get(key, []):
            require(type(wrapper) is dict and set(wrapper) == {'candidate_id', 'test_index', 'receipt'}, 'query association schema')
            index = wrapper['test_index']; cid = wrapper['candidate_id']; receipt = wrapper['receipt']
            require(type(index) is int and 0 <= index < len(task['test']), 'query test identity')
            choice = next((r for r in chosen if r['candidate_id'] == cid), None)
            require(choice is not None and (cid, index) not in lookup, 'foreign/duplicate selected query')
            require(receipt['format'] == PROTOCOL and receipt['selection_sha256'] == selection_hash and
                    receipt['plan_sha256'] == choice['plan_sha256'] and
                    receipt['source_sha256'] == sha256(ir.compile_plan(choice['plan']).encode()) and
                    receipt['started_at_ns'] >= frozen['sealed_at_ns'] and receipt['query_count'] == 1 and
                    receipt['limits'] == verifier.known_limits() and receipt['owned_descendants_stopped'] is True,
                    'query is unsealed, foreign, or unclosed')
            require(type(receipt) is dict and set(receipt) == {'format', 'call_id', 'plan_sha256', 'source_sha256',
                    'selection_sha256', 'started_at_ns', 'finished_at_ns', 'limits', 'results', 'query_count',
                    'gas_charged', 'owned_descendants_stopped'} and type(receipt['query_count']) is int and
                    type(receipt['started_at_ns']) is int and type(receipt['finished_at_ns']) is int and
                    receipt['finished_at_ns'] >= receipt['started_at_ns'], 'query receipt schema/time differs')
            require(receipt['call_id'] not in global_calls and len(receipt['results']) == 1, 'query call reused')
            _name(receipt['call_id']); global_calls.add(receipt['call_id'])
            row = receipt['results'][0]
            request = _request(choice['plan'], task['test'][index]['input'], selection_hash)
            require(row['request_sha256'] == hash_value(request) and row['input_digest'] == digest(task['test'][index]['input']),
                    'query input binding differs')
            require(type(row) is dict and set(row) == {'request_sha256', 'input_digest', 'status', 'output', 'gas',
                    'reason', 'dispatched', 'gas_charged', 'gas_reserved', 'wall_seconds', 'process_returncode',
                    'owned_descendants_stopped'}, 'query result schema differs')
            require(row['status'] in ('valid', 'invalid', 'missing') and type(row['dispatched']) is bool and
                    row['owned_descendants_stopped'] is True and verifier._number(row['wall_seconds']) and
                    type(row['gas_charged']) is int and type(row['gas_reserved']) is int and
                    row['gas_reserved'] == (verifier.MAX_STEPS if row['dispatched'] else 0) and
                    type(row['reason']) is str and len(row['reason']) <= 160, 'query status/accounting differs')
            if row['status'] == 'missing':
                require(row['gas'] is None and row['gas_charged'] == row['gas_reserved'], 'unknown query accounting differs')
            else:
                require(row['dispatched'] is True and type(row['process_returncode']) is int and
                        row['process_returncode'] == 0 and type(row['gas']) is int and
                        0 <= row['gas'] <= verifier.MAX_STEPS and row['gas_charged'] == row['gas'],
                        'known query worker/gas evidence differs')
            require(receipt['gas_charged'] == row['gas_charged'], 'query charged total differs')
            if row['status'] == 'valid':
                grid(row['output'])
            else:
                require(row['output'] is None, 'invalid query output retained')
            lookup[(cid, index)] = row
        tests = []
        for index, pair in enumerate(task['test']):
            outputs = []
            attempted = False
            for choice in chosen:
                row = lookup.get((choice['candidate_id'], index))
                if row is not None:
                    attempted = True
                    if row['status'] == 'valid' and row['output'] not in outputs:
                        outputs.append(row['output'])
            status = 'complete' if len(outputs) == 2 else 'partial' if outputs else 'failed' if attempted else 'not_executed'
            tests.append({'test_index': index, 'input_digest': digest(pair['input']), 'ranked_grids': outputs, 'status': status})
        records.append({'task_id': key, 'task_digest': digest(task), 'timings': {}, 'tests': tests})
    pool = {'format': POOL_FORMAT, 'run_id': run_id, 'method': policy,
            'challenges_digest': digest(challenges), 'records': records, 'parent_wall_seconds': parent_wall_seconds}
    validate_pools(challenges, pool)
    return pool


if __name__ == '__main__':
    require(sys.argv[1:] == ['--worker'], 'private query worker entry only')
    raise SystemExit(_worker())

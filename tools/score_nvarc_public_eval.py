"""Independent returned-public-ZIP scoring. Never included in GPU payloads."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.nvarc_public_eval import read_archive, validate_plan, validate_record, sha, INPUT_SHA
from tools.nvarc_native_multitask import digest, require, write
from tools.arc_kaggle_submission import parse_json, grid
from tools.stage_nvarc_public_eval import FILES


def score(plan, challenges, records, solutions, *, allow_fixture=False):
    counts = validate_plan(plan, challenges, allow_fixture=allow_fixture)
    require(set(solutions) == set(counts) and all(len(solutions[k]) == n for k, n in counts.items()),
            'complete exact public solution denominator required')
    for values in solutions.values():
        for value in values: grid(value)
    for key, record in records.items():
        require(validate_record(plan, challenges, record) == key, 'foreign returned prediction record')
    rows = []; task_scores = []
    for key, count in sorted(counts.items()):
        solved = 0
        for index in range(count):
            test = None if key not in records else records[key]['tests'][index]
            attempts = [] if test is None else test['attempts']; pool = [] if test is None else test['ranked_grids']
            answer = solutions[key][index]
            one = bool(attempts and attempts[0] == answer); two = any(g == answer for g in attempts)
            raw_one = (attempts[0] if attempts else [[0]]) == answer
            raw_two = two or not attempts and [[0]] == answer
            solved += two
            rows.append({'task_id': key, 'test_index': index, 'model_pass1': one, 'model_pass2': two,
                'raw_submission_pass1': raw_one, 'raw_submission_pass2': raw_two,
                'verified_pool_oracle': any(g == answer for g in pool), 'retained_pool_size': len(pool),
                'model_coverage': bool(attempts), 'status': 'not_executed' if test is None else test['status']})
        task_scores.append({'task_id': key, 'solved_tests': solved, 'tests': count,
                            'test_fraction': solved/count, 'all_tests_pass2': solved == count})
    n = len(rows)
    return {'format': 'irisx/nvarc-public-score-v1', 'run_id': plan['run_id'], 'profile': plan['profile'],
        'plan_digest': digest(plan), 'tasks': len(counts), 'tests': n,
        'test_pass1': sum(r['model_pass1'] for r in rows)/n, 'test_pass2': sum(r['model_pass2'] for r in rows)/n,
        'raw_submission_test_pass2': sum(r['raw_submission_pass2'] for r in rows)/n,
        'task_average_pass2': sum(r['test_fraction'] for r in task_scores)/len(counts),
        'tasks_all_tests_pass2': sum(r['all_tests_pass2'] for r in task_scores),
        'verified_pool_oracle': sum(r['verified_pool_oracle'] for r in rows)/n,
        'model_test_coverage': sum(r['model_coverage'] for r in rows)/n,
        'rows': rows, 'task_rows': task_scores, 'official_score': None,
        'qualification': 'public development measurement; model exposure unresolved; not a fresh or hidden score'}


def bind_returned_archive(manifest, payloads, package):
    """Bind returned bytes to the saved package, independent of today's source."""
    package = Path(package)
    summary = parse_json((package/'stage-summary.json').read_bytes())
    require(not package.is_symlink() and not any(p.is_symlink() for p in package.rglob('*')),
            'regular saved package required')
    actual = {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*')
              if p.is_file() and p.name != 'stage-summary.json'}
    require(actual == summary['inventory'], 'saved package inventory differs')
    plan = parse_json(payloads['plan.json'])
    require(payloads['plan.json'] == (package/'plan.json').read_bytes() and
        manifest['run_id'] == summary['run_id'] == plan['run_id'] and
        manifest['plan_digest'] == summary['plan_digest'] == digest(plan), 'returned/saved plan differs')
    bindings = parse_json(payloads['payload-bindings.json'])
    require(bindings == summary['payload_sha256'] and
        all(hashlib.sha256(payloads[name]).hexdigest() == bindings[key]
            for name, key in FILES.items()), 'returned source/input payload binding differs')
    require(hashlib.sha256(payloads['challenges.json']).hexdigest() == INPUT_SHA,
            'returned exact public challenge bytes differ')
    terminal = parse_json(payloads['terminal.json'])
    require(terminal['run_id'] == plan['run_id'] and terminal['plan_digest'] == digest(plan),
            'returned terminal identity differs')
    return plan, parse_json(payloads['challenges.json']), terminal


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--solutions', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); manifest, payloads = read_archive(args.archive)
    plan, challenges, terminal = bind_returned_archive(manifest, payloads, args.package)
    records = parse_json(payloads['candidate-pools.json'])
    require(records['plan_digest'] == digest(plan) and records['run_id'] == plan['run_id'], 'returned pool identity differs')
    data = score(plan, challenges, records['records'], parse_json(args.solutions.read_bytes()))
    data['provenance'] = {'archive_sha256': sha(args.archive), 'solutions_sha256': sha(args.solutions),
        'saved_package_summary_sha256': sha(args.package/'stage-summary.json'),
        'terminal_outcome': terminal['outcome'], 'wall_seconds': terminal.get('wall_seconds')}
    require(not args.output.exists(), 'new independent score output required')
    write(args.output, data); print(json.dumps({k: v for k, v in data.items() if k not in ('rows', 'task_rows')}))


if __name__ == '__main__': main()

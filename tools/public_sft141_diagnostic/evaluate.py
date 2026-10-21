"""Post-exit scoring. Never imported by the inference worker."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from .contract import validate_grid, parse_answer, inverse, transform, prompt_ids, answer_ids


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()


def _tokens_hash(tokens):
    return hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()


def _audit_query(parent, index, row):
    """Independently rebuild the pool, conditioning identities and both ranks."""
    views = row.get('views', [])
    if not isinstance(views, list) or any(type(v.get('view')) is not int or not 0 <= v['view'] < 8 for v in views):
        raise ValueError('Invalid view inventory')
    if len({v['view'] for v in views}) != len(views):
        raise ValueError('Duplicate generation view')
    counts, grids = Counter(), {}
    complete_views = len(views) == 8
    for view in views:
        complete_views = complete_views and view.get('status') == 'complete'
        if view.get('status') != 'complete':
            continue
        number = view['view']
        prompt = prompt_ids(parent['train'], parent['test'][index]['input'], number)
        if view.get('prompt_sha256') != _tokens_hash(prompt):
            raise ValueError('Generation prompt binding mismatch')
        try:
            parsed = parse_answer(view.get('token_ids'))
        except ValueError:
            parsed = None
        if bool(view.get('valid')) != (parsed is not None):
            raise ValueError('Raw token validity differs from reported validity')
        if parsed is None:
            continue
        grid = inverse(parsed, number)
        if view.get('canonical_grid') != grid:
            raise ValueError('Inverse-transformed candidate mismatch')
        key = json.dumps(grid, separators=(',', ':'))
        counts[key] += 1
        grids[key] = grid
    pool = row.get('candidates', [])
    if not isinstance(pool, list) or len(pool) != len(counts):
        raise ValueError('Candidate pool size differs from raw views')
    seen, scored = set(), {}
    scores_complete = complete_views
    for candidate in pool:
        grid = validate_grid(candidate['grid'])
        key = json.dumps(grid, separators=(',', ':'))
        if key not in counts or key in seen or type(candidate.get('count')) is not int or candidate['count'] != counts[key]:
            raise ValueError('Candidate occurrence count mismatch')
        seen.add(key)
        entries = candidate.get('view_nll', [])
        if not isinstance(entries, list) or len(entries) > 8 or any(type(v.get('view')) is not int or not 0 <= v['view'] < 8 for v in entries):
            raise ValueError('Invalid NLL view inventory')
        if len({v['view'] for v in entries}) != len(entries):
            raise ValueError('Duplicate NLL condition')
        all_scores = len(entries) == 8 and all(v.get('status') == 'complete' for v in entries)
        scores_complete = scores_complete and all_scores
        for entry in entries:
            if entry.get('status') != 'complete':
                continue
            value = entry.get('nll')
            if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                raise ValueError('Nonfinite or invalid NLL')
            view = entry['view']
            prompt = prompt_ids(parent['train'], parent['test'][index]['input'], view)
            answer = answer_ids(transform(grid, view))
            if (entry.get('prompt_sha256') != _tokens_hash(prompt)
                    or entry.get('answer_sha256') != _tokens_hash(answer)
                    or entry.get('answer_tokens') != len(answer)
                    or entry.get('includes_eos') is not True
                    or entry.get('normalization') != 'sum-not-token-mean'):
                raise ValueError('NLL full-answer conditioning mismatch')
        if all_scores:
            mean = sum(entry['nll'] for entry in entries) / 8.0
            if row.get('rescoring_complete') and (candidate.get('mean_nll') is None or candidate.get('combined_score') is None):
                raise ValueError('Completed ranking lacks derived NLL aggregates')
            if (candidate.get('mean_nll') is not None or row.get('rescoring_complete')) and not math.isclose(candidate.get('mean_nll', float('nan')), mean, rel_tol=1e-10, abs_tol=1e-10):
                raise ValueError('Mean NLL differs from per-view evidence')
            score = counts[key] - mean
            if (candidate.get('combined_score') is not None or row.get('rescoring_complete')) and not math.isclose(candidate.get('combined_score', float('nan')), score, rel_tol=1e-10, abs_tol=1e-10):
                raise ValueError('Combined ranking score mismatch')
            scored[key] = score
    vote = [grids[key] for key in sorted(counts, key=lambda key: (-counts[key], key))[:2]]
    if row.get('vote', []) != vote:
        raise ValueError('Vote ranking differs from raw pool')
    if row.get('rescoring_complete'):
        if not scores_complete:
            raise ValueError('Claimed completed ranking has missing NLL evidence')
        ranked = [grids[key] for key in sorted(scored, key=lambda key: (-scored[key], key))[:2]]
        if row.get('rescored', []) != ranked:
            raise ValueError('Rescored ranking differs from full NLL evidence')
    elif row.get('rescored', []):
        raise ValueError('Incomplete ranking cannot expose selected partial candidates')
    return complete_views and scores_complete and bool(row.get('rescoring_complete'))


def evaluate(plan, gold, result):
    """Keep full fixed denominators and report missing separately from observed errors."""
    expected = {}
    parent_queries = {}
    for parent in plan['parents']:
        task = parent['task_id']
        if task in parent_queries:
            raise ValueError('Duplicate parent')
        parent_queries[task] = []
        targets = gold['answers'][task]
        if len(targets) != len(parent['test']):
            raise ValueError('Gold/query count mismatch')
        for index, test in enumerate(parent['test']):
            key = f'{task}:{index}'
            if test.get('query_id', key) != key or test.get('test_index', index) != index:
                raise ValueError('Query ordering mismatch')
            validate_grid(targets[index])
            expected[key] = targets[index]
            parent_queries[task].append(key)
    if set(gold['answers']) != set(parent_queries):
        raise ValueError('Unexpected gold parents')
    rows = {}
    parents_by_id = {p['task_id']: p for p in plan['parents']}
    audited_complete = {}
    for row in result.get('queries', []):
        key = f"{row['task_id']}:{row['test_index']}"
        if key not in expected or row.get('query_id', key) != key or key in rows:
            raise ValueError('Unexpected or duplicated prediction query')
        rows[key] = row
        audited_complete[key] = _audit_query(parents_by_id[row['task_id']], row['test_index'], row)
    metrics, paired = {}, []
    for name in ('vote', 'rescored'):
        outcomes, observed, valid_views = {}, 0, 0
        for key, target in expected.items():
            row = rows.get(key, {})
            candidates = row.get(name, [])
            if not isinstance(candidates, list) or len(candidates) > 2:
                raise ValueError('Invalid attempt inventory')
            for grid in candidates:
                validate_grid(grid)
            if len(candidates) == 2 and candidates[0] == candidates[1]:
                raise ValueError('Candidate attempts must be distinct')
            if candidates:
                observed += 1
            outcomes[key] = [bool(candidates and candidates[0] == target), target in candidates]
            views = row.get('views', [])
            valid_views += sum(v.get('status') == 'valid' for v in views)
        n = len(expected)
        metrics[name] = {
            'query_denominator': n,
            'queries_with_candidates': observed,
            'queries_without_candidates': n - observed,
            'pass1_count': sum(v[0] for v in outcomes.values()),
            'pass2_count': sum(v[1] for v in outcomes.values()),
            'pass1': sum(v[0] for v in outcomes.values()) / n,
            'pass2': sum(v[1] for v in outcomes.values()) / n,
            'task_macro_pass2': sum(sum(outcomes[k][1] for k in keys) / len(keys) for keys in parent_queries.values()) / len(parent_queries),
            'all_queries_task_pass2_count': sum(all(outcomes[k][1] for k in keys) for keys in parent_queries.values()),
            'parent_denominator': len(parent_queries),
            'per_query': outcomes,
        }
    for key in expected:
        a, b = (metrics[x]['per_query'][key][1] for x in ('vote', 'rescored'))
        paired.append({'query_id': key, 'vote_pass2': a, 'rescored_pass2': b})
    oracle = 0
    for key, target in expected.items():
        pool = rows.get(key, {}).get('candidates', [])
        grids = [candidate['grid'] for candidate in pool]
        for grid in grids:
            validate_grid(grid)
        oracle += target in grids
    return {
        'schema': 'iris-public-sft141-evaluation-v1',
        'worker_status': result.get('status', 'missing'),
        'scientific_complete': result.get('status') == 'complete' and set(rows) == set(expected) and all(audited_complete.values()),
        'audited_complete_queries': sum(audited_complete.values()),
        'expected_views': 8 * len(expected),
        'recorded_complete_views': sum(v.get('status') == 'complete' for row in rows.values() for v in row.get('views', [])),
        'coverage_inclusive_metrics': metrics,
        'pool_oracle_pass2_count': oracle,
        'paired': {'rescored_only': sum(not r['vote_pass2'] and r['rescored_pass2'] for r in paired),
                   'vote_only': sum(r['vote_pass2'] and not r['rescored_pass2'] for r in paired), 'rows': paired},
        'qualification': 'Public evaluation, possible pretraining exposure. Not hidden generalization or private IRIS checkpoint reproduction. Missing predictions remain explicit; partial is not a completed comparison.',
    }


def score_sealed(plan_path, gold_path, result_path, seal_path):
    raw = Path(result_path).read_bytes()
    seal = json.loads(Path(seal_path).read_text())
    if hashlib.sha256(raw).hexdigest() != seal['result_sha256'] or not seal['worker_exited']:
        raise ValueError('Unsealed or changed worker predictions')
    return evaluate(json.loads(Path(plan_path).read_text()), json.loads(Path(gold_path).read_text()), json.loads(raw))

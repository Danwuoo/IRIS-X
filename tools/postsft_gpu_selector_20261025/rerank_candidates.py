"""Pure CPU selection from a sealed GPU candidate pool. No gold/scorer/model/provider.

These selectors diagnose selection loss on a FIXED pool; they do not create
answers, certify semantic correctness, or justify training a reward model.
"""
from collections import Counter
import hashlib
import json
import math

POOL_KEYS = {'schema', 'pool_id', 'policy_sha256', 'decoder_contract_sha256', 'candidates'}
CANDIDATE_KEYS = {'draw_id', 'view_id', 'grid', 'finished_eos', 'truncated', 'sampled_logps'}


def select(pool, method='vote', slots=2, max_grid_side=30):
    if set(pool) != POOL_KEYS or pool['schema'] != 'iris-fixed-candidate-pool/v1':
        raise ValueError('closed pool schema; query gold and evaluator feedback are not accepted')
    if method not in {'first', 'vote', 'mean_logp'} or type(slots) is not int or slots not in {1, 2}:
        raise ValueError('unregistered selector')
    if not isinstance(max_grid_side, int) or isinstance(max_grid_side, bool) or not 1 <= max_grid_side <= 64:
        raise ValueError('explicit grid resource bound required')
    for key in ('policy_sha256', 'decoder_contract_sha256'):
        if len(pool[key]) != 64 or any(c not in '0123456789abcdef' for c in pool[key]):
            raise ValueError('exact policy/decoder pins required')
    draws = pool['candidates']
    if not isinstance(draws, list) or not 1 <= len(draws) <= 256:
        raise ValueError('finite existing pool required')
    grouped = {}; seen = set(); invalid = 0
    for ordinal, candidate in enumerate(draws):
        if set(candidate) != CANDIDATE_KEYS:
            raise ValueError('closed candidate schema; no labels/rewards/support hints')
        draw_id = candidate['draw_id']
        if not isinstance(draw_id, str) or not draw_id or draw_id in seen:
            raise ValueError('draw IDs must be unique')
        seen.add(draw_id)
        if not isinstance(candidate['view_id'], str):
            raise ValueError('view provenance required')
        if type(candidate['finished_eos']) is not bool or type(candidate['truncated']) is not bool:
            raise ValueError('exact termination booleans required')
        logps = candidate['sampled_logps']
        if not isinstance(logps, list) or len(logps) > 8192:
            raise ValueError('finite per-generated-token logps required')
        if any(type(x) not in {int, float} or not math.isfinite(x) or x > 1e-6 for x in logps):
            raise ValueError('invalid logprob')
        grid = candidate['grid']
        valid = candidate['finished_eos'] and not candidate['truncated'] and bool(logps)
        valid = valid and isinstance(grid, list) and 1 <= len(grid) <= max_grid_side
        if valid:
            valid = all(isinstance(row, list) and 1 <= len(row) <= max_grid_side for row in grid)
        if valid:
            valid = len({len(row) for row in grid}) == 1
        if valid:
            valid = all(type(v) is int and 0 <= v <= 9 for row in grid for v in row)
        if not valid:
            invalid += 1
            continue
        # grid must already be inverse-transformed into the original task frame.
        raw = json.dumps(grid, separators=(',', ':')).encode()
        grid_sha = hashlib.sha256(raw).hexdigest()
        record = grouped.setdefault(grid_sha, {'grid': grid, 'grid_sha256': grid_sha,
                  'first_ordinal': ordinal, 'draw_ids': [], 'view_ids': [], 'scores': []})
        record['draw_ids'].append(draw_id); record['view_ids'].append(candidate['view_id'])
        record['scores'].append(sum(logps) / len(logps))
    values = list(grouped.values())
    if method == 'first':
        values.sort(key=lambda x: x['first_ordinal'])
    elif method == 'vote':
        values.sort(key=lambda x: (-len(x['draw_ids']), x['first_ordinal']))
    else:
        # Duplicate output confidence is max observed mean logp; fixed pre-score.
        values.sort(key=lambda x: (-max(x['scores']), x['first_ordinal']))
    return {'schema': 'iris-fixed-pool-selection/v1', 'pool_id': pool['pool_id'],
            'policy_sha256': pool['policy_sha256'],
            'decoder_contract_sha256': pool['decoder_contract_sha256'], 'method': method,
            'selected': [{k: v for k, v in x.items() if k != 'scores'} for x in values[:slots]],
            'draws': len(draws), 'invalid_or_truncated_draws': invalid,
            'unique_valid_grids': len(values), 'duplicate_valid_draws': len(draws)-invalid-len(values),
            'oracle_score': None, 'semantic_correctness_verified': False,
            'new_model_calls': 0, 'query_gold_access': False}

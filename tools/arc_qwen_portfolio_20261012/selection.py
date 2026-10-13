"""Closed, target-free checkpoint portfolio selection and canary-only ranking.

This module is pure stdlib: no model, filesystem, source execution, target loader,
NLL scorer, or GPU calls. Runtime adapters must project *trusted bounded-VM*
receipts into these schemas. Digests bind the projection; they are not signatures
and cannot prove that a dishonest producer actually ran the verifier.

Per-task selection always uses base, program8, program16 in that order. Canary
rankings are branch-aligned diagnostics and never remove or reorder that pool.
Persist the returned seal exclusively, and commit its digest to the run's phase
ledger, BEFORE opening noncanary target escrow or invoking any holdout scorer.
The integration layer owns that chronological boundary.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Literal

Grid = tuple[tuple[int, ...], ...]
CandidateId = Literal['base', 'program8', 'program16']
Branch = Literal['grid', 'program']
CANDIDATE_ORDER = ('base', 'program8', 'program16')
CHECKPOINT_UPDATES = (0, 8, 16)
MINIMUM_CANARIES = 3
VERIFIER_SHA256 = '072c4133b63e05c09509fa9f5734a4dae4f7065f8bdb2cc5483b6468e189368b'
QUERY_VERIFIER_SHA256 = '52bc22ffdf32198ceee209b68f68840869086af7d4372e54ec7d7b0297fe760d'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    """Canonical JSON bytes; distinct from legacy proof hashes without newline."""
    try:
        return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                           allow_nan=False, ensure_ascii=True) + '\n').encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError('finite JSON value required') from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def source_digest(text):
    _require(type(text) is str, 'source text required')
    return hashlib.sha256(text.encode('utf-8', 'strict')).hexdigest()


SELECTION_POLICY = {
    'format': 'irisx/qwen-program-portfolio-policy-v1',
    'candidate_order': list(CANDIDATE_ORDER), 'maximum_distinct_predictions': 2,
    'eligibility': 'known complete all-demo-fit proof and valid replayed query',
    'order': 'fixed checkpoint order; first candidate for each distinct grid',
    'no_eligible_candidate': 'abstain; no grid fallback',
    'conflict': 'retain first two distinct predictions; expose full conflict count',
    'query_gold_allowed': False, 'query_score_allowed': False,
    'query_nll_allowed': False, 'cross_branch_pooling_allowed': False,
    'verifier_sha256': VERIFIER_SHA256, 'query_verifier_sha256': QUERY_VERIFIER_SHA256,
}
RANKING_POLICY = {
    'format': 'irisx/qwen-canary-checkpoint-ranking-policy-v1',
    'scope': 'canary', 'checkpoint_updates': list(CHECKPOINT_UPDATES),
    'minimum_canaries': MINIMUM_CANARIES,
    'coverage': 'every approved case at every checkpoint; no other scopes',
    'grid_rank': ['grid_exact', 'grid_shape_correct', 'grid_valid',
                  'lower_fully_matched_grid_nll', 'earlier_update'],
    'program_rank': ['program_exact', 'program_all_demos_fit',
                     'program_valid_query', 'earlier_update'],
    'retain_all_checkpoints': True, 'affects_portfolio_order': False,
}
SELECTION_POLICY_SHA256 = digest(SELECTION_POLICY)
RANKING_POLICY_SHA256 = digest(RANKING_POLICY)


def _closed(value, keys, name):
    _require(type(value) is dict, name + ': plain object required')
    _require(set(value) == set(keys), name + ': unknown or missing fields')
    return value


def _string(value, name):
    _require(type(value) is str and 0 < len(value) <= 256
             and value.isprintable(), name + ': bounded nonempty string required')
    return value


def _sha(value, name):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
             name + ': lowercase SHA256 required')
    return value


def _bool(value, name):
    _require(type(value) is bool, name + ': exact Boolean required')
    return value


def _int(value, lo, hi, name):
    _require(type(value) is int and lo <= value <= hi, name + ': bounded integer required')
    return value


def _grid(value, name):
    _require(type(value) is list and 1 <= len(value) <= 30,
             name + ': grid must have 1..30 rows')
    width = None
    rows = []
    for row in value:
        _require(type(row) is list and 1 <= len(row) <= 30,
                 name + ': grid must have 1..30 columns')
        if width is None:
            width = len(row)
        _require(len(row) == width, name + ': rectangular grid required')
        _require(all(type(c) is int and 0 <= c <= 9 for c in row),
                 name + ': exact integer colors 0..9 required')
        rows.append(tuple(row))
    return tuple(rows)


def _grid_json(value):
    return [list(row) for row in value]


def _task(value):
    _closed(value, ('task_id', 'demos', 'query_input'), 'target-free task')
    _string(value['task_id'], 'task_id')
    demos = value['demos']
    _require(type(demos) is list and 1 <= len(demos) <= 10, '1..10 demonstrations required')
    for demo in demos:
        _closed(demo, ('input', 'output'), 'demonstration')
        _grid(demo['input'], 'demo input')
        _grid(demo['output'], 'demo output')
    _grid(value['query_input'], 'query input')
    return deepcopy(value)


@dataclass(frozen=True)
class DemoProof:
    source_sha256: str
    demos_sha256: str
    verifier_sha256: str
    proof_sha256: str
    known: bool
    all_demos_fit: bool
    demo_count: int
    matched_demo_indices: tuple[int, ...]
    owned_descendants_stopped: bool

    @classmethod
    def from_dict(cls, value):
        _closed(value, cls.__dataclass_fields__, 'demo proof')
        for key in ('source_sha256', 'demos_sha256', 'verifier_sha256', 'proof_sha256'):
            _sha(value[key], key)
        for key in ('known', 'all_demos_fit', 'owned_descendants_stopped'):
            _bool(value[key], key)
        count = _int(value['demo_count'], 1, 10, 'demo_count')
        indices = value['matched_demo_indices']
        _require(type(indices) is list, 'matched demonstration indices list required')
        for index in indices:
            _int(index, 0, count - 1, 'matched demonstration index')
        _require(indices == sorted(set(indices)), 'unique ordered demonstration indices required')
        _require(value['verifier_sha256'] == VERIFIER_SHA256, 'demo verifier pin differs')
        _require(value['owned_descendants_stopped'], 'demo verifier descendants not stopped')
        complete = value['known'] and indices == list(range(count))
        _require(value['all_demos_fit'] == complete, 'all-demo-fit claim contradicts known full coverage')
        return cls(**{**value, 'matched_demo_indices': tuple(indices)})


@dataclass(frozen=True)
class QueryProof:
    source_sha256: str
    demos_sha256: str
    query_input_sha256: str
    demo_proof_sha256: str
    verifier_sha256: str
    status: Literal['valid', 'invalid', 'unavailable']
    output: Grid | None
    demo_replay_verified: bool
    owned_descendants_stopped: bool

    @classmethod
    def from_dict(cls, value):
        _closed(value, cls.__dataclass_fields__, 'query proof')
        for key in ('source_sha256', 'demos_sha256', 'query_input_sha256',
                    'demo_proof_sha256', 'verifier_sha256'):
            _sha(value[key], key)
        for key in ('demo_replay_verified', 'owned_descendants_stopped'):
            _bool(value[key], key)
        _require(type(value['status']) is str and value['status'] in ('valid', 'invalid', 'unavailable'),
                 'closed query status required')
        _require(value['verifier_sha256'] == QUERY_VERIFIER_SHA256, 'query verifier pin differs')
        _require(value['owned_descendants_stopped'], 'query verifier descendants not stopped')
        if value['status'] == 'valid':
            output = _grid(value['output'], 'query output')
            _require(value['demo_replay_verified'], 'valid query requires verified demo replay')
        else:
            _require(value['output'] is None, 'nonvalid query cannot contain a prediction')
            output = None
        return cls(**{**value, 'output': output})


@dataclass(frozen=True)
class ProgramCandidate:
    candidate_id: CandidateId
    checkpoint_sha256: str
    generation_status: Literal['valid', 'invalid', 'unavailable']
    source_sha256: str | None
    proof: DemoProof | None
    query: QueryProof | None

    @classmethod
    def from_dict(cls, value, task):
        _closed(value, cls.__dataclass_fields__, 'program candidate')
        _require(type(value['candidate_id']) is str and value['candidate_id'] in CANDIDATE_ORDER,
                 'candidate outside fixed program pool')
        _sha(value['checkpoint_sha256'], 'checkpoint_sha256')
        _require(type(value['generation_status']) is str
                 and value['generation_status'] in ('valid', 'invalid', 'unavailable'),
                 'closed generation status required')
        if value['generation_status'] != 'valid':
            _require(value['source_sha256'] is None and value['proof'] is None and value['query'] is None,
                     'failed generation must have no source/proof/query')
            return cls(**value)
        source = _sha(value['source_sha256'], 'source_sha256')
        proof = DemoProof.from_dict(value['proof']) if value['proof'] is not None else None
        query = QueryProof.from_dict(value['query']) if value['query'] is not None else None
        if proof is not None:
            _require(proof.source_sha256 == source, 'proof source binding differs')
            _require(proof.demos_sha256 == digest(task['demos']), 'proof demonstration binding differs')
            _require(proof.demo_count == len(task['demos']), 'proof does not cover every demonstration')
        if query is not None:
            _require(proof is not None and proof.all_demos_fit, 'query forbidden before full demo fit')
            _require(query.source_sha256 == source and query.demos_sha256 == proof.demos_sha256
                     and query.demo_proof_sha256 == proof.proof_sha256,
                     'query source/demo/proof binding differs')
            _require(query.query_input_sha256 == digest(task['query_input']), 'query input binding differs')
        return cls(value['candidate_id'], value['checkpoint_sha256'], value['generation_status'],
                   source, proof, query)

    def exclusion(self):
        if self.generation_status != 'valid':
            return 'generation-' + self.generation_status
        if self.proof is None or not self.proof.known:
            return 'demo-proof-unavailable'
        if not self.proof.all_demos_fit:
            return 'not-all-demonstrations-fit'
        if self.query is None:
            return 'query-not-run'
        if self.query.status != 'valid':
            return 'query-' + self.query.status
        return None


def select_program_portfolio(task, candidates):
    """Select at most two distinct grids using demonstrations and fixed order only.

    Every fixed candidate must be present exactly once, even when generation or
    verification failed. Input list order is immaterial. Malformed or poisoned
    evidence raises ValueError; valid but ineligible evidence yields abstention.
    """
    task = _task(task)
    _require(type(candidates) is list and len(candidates) == len(CANDIDATE_ORDER),
             'all three fixed candidates required, including explicit failures')
    parsed = [ProgramCandidate.from_dict(c, task) for c in candidates]
    by_id = {c.candidate_id: (c, deepcopy(raw)) for c, raw in zip(parsed, candidates)}
    _require(set(by_id) == set(CANDIDATE_ORDER), 'duplicate or missing fixed candidate')
    ordered = [by_id[c][1] for c in CANDIDATE_ORDER]
    eligible, exclusions, selected, predictions = [], [], [], set()
    for name in CANDIDATE_ORDER:
        candidate = by_id[name][0]
        reason = candidate.exclusion()
        if reason is not None:
            exclusions.append({'candidate_id': name, 'reason': reason})
            continue
        eligible.append(name)
        prediction = candidate.query.output
        if prediction in predictions:
            continue
        predictions.add(prediction)
        if len(selected) < 2:
            grid = _grid_json(prediction)
            selected.append({'candidate_id': name, 'prediction': grid,
                             'prediction_sha256': digest(grid)})
    top2 = [deepcopy(s['prediction']) for s in selected]
    result = {
        'format': 'irisx/qwen-program-portfolio-decision-v1',
        'policy_sha256': SELECTION_POLICY_SHA256,
        'task_id': task['task_id'], 'task_sha256': digest(task),
        'candidate_set_sha256': digest(ordered),
        'inputs': {'task': task, 'candidates': ordered},
        'candidate_order': list(CANDIDATE_ORDER), 'eligible_candidate_ids': eligible,
        'exclusions': exclusions, 'selected': selected,
        'top1': deepcopy(top2[0]) if top2 else None, 'top2': top2,
        'distinct_prediction_count': len(predictions), 'conflict': len(predictions) > 1,
        'abstained': not selected,
        'abstention_reason': 'no-eligible-program-candidate' if not selected else None,
    }
    result['decision_sha256'] = digest(result)
    return result


def _canary_ids(approved_canary_ids, minimum_canaries):
    _int(minimum_canaries, MINIMUM_CANARIES, 10000, 'minimum_canaries')
    _require(type(approved_canary_ids) in (list, tuple), 'approved canary ID list required')
    ids = [_string(x, 'approved canary ID') for x in approved_canary_ids]
    _require(all(x.startswith('canary:') for x in ids), 'explicit canary namespace required')
    _require(len(ids) == len(set(ids)) and len(ids) >= minimum_canaries,
             'minimum distinct approved canary coverage required')
    return sorted(ids)


def _canary_row(value, branch, approved):
    metrics = ('grid_exact', 'grid_shape_correct', 'grid_valid', 'grid_nll') if branch == 'grid' else (
        'program_exact', 'program_all_demos_fit', 'program_valid_query')
    _closed(value, ('branch', 'scope', 'case_id', 'checkpoint_update', *metrics), 'canary rank row')
    _require(type(value['branch']) is str and value['branch'] == branch, 'rank branch mismatch')
    _require(type(value['scope']) is str and value['scope'] == 'canary',
             'only approved canary scope may enter ranking; no holdout/public/seen scopes')
    _string(value['case_id'], 'canary case_id')
    _require(value['case_id'] in approved, 'unapproved canary case')
    _int(value['checkpoint_update'], 0, 16, 'checkpoint_update')
    _require(value['checkpoint_update'] in CHECKPOINT_UPDATES, 'unregistered checkpoint update')
    for key in metrics:
        if key != 'grid_nll':
            _bool(value[key], key)
    if branch == 'program':
        _require(not value['program_valid_query'] or value['program_all_demos_fit'],
                 'valid program query requires all demonstrations fit')
        _require(not value['program_exact'] or value['program_valid_query'],
                 'program exact requires valid query')
    else:
        _require(not value['grid_exact'] or value['grid_shape_correct'],
                 'grid exact requires correct shape')
        _require(not value['grid_shape_correct'] or value['grid_valid'],
                 'correct shape requires valid grid')
        nll = value['grid_nll']
        if nll is not None:
            _closed(nll, ('nll_sum', 'token_count', 'example_sha256'), 'grid canary NLL')
            _require(type(nll['nll_sum']) in (int, float) and math.isfinite(nll['nll_sum'])
                     and 0 <= nll['nll_sum'] <= 1e100, 'finite nonnegative grid NLL required')
            _int(nll['token_count'], 1, 1000000, 'NLL token_count')
            _sha(nll['example_sha256'], 'matched NLL example_sha256')
    return deepcopy(value)


def rank_checkpoints(branch, canary_rows, approved_canary_ids, *, minimum_canaries=MINIMUM_CANARIES):
    """Rank all 0/8/16 checkpoints on approved canaries; never filter candidates.

    Missing cases/checkpoints are errors. Missing NLL disables the NLL tie-break
    globally, rather than comparing unmatched subsets. Conflicting example or
    token-count bindings are errors. Program rankings have no NLL field at all.
    The panel contract must independently establish family/parent independence.
    """
    _require(type(branch) is str and branch in ('grid', 'program'), 'grid or program branch required')
    approved = _canary_ids(approved_canary_ids, minimum_canaries)
    _require(type(canary_rows) is list, 'canary row list required')
    rows = [_canary_row(r, branch, approved) for r in canary_rows]
    indexed = {(r['checkpoint_update'], r['case_id']): r for r in rows}
    expected = {(u, case) for u in CHECKPOINT_UPDATES for case in approved}
    _require(len(rows) == len(indexed) and set(indexed) == expected,
             'complete unique checkpoint x approved-canary coverage required')
    ordered = [indexed[(u, case)] for u in CHECKPOINT_UPDATES for case in approved]
    nll_enabled = False
    if branch == 'grid':
        nll_enabled = all(r['grid_nll'] is not None for r in ordered)
        for case in approved:
            available = [indexed[(u, case)]['grid_nll'] for u in CHECKPOINT_UPDATES
                         if indexed[(u, case)]['grid_nll'] is not None]
            bindings = {(n['example_sha256'], n['token_count']) for n in available}
            _require(len(bindings) <= 1, 'grid NLL examples/token masks differ across checkpoints')
    summaries, keys = [], {}
    for update in CHECKPOINT_UPDATES:
        subset = [indexed[(update, case)] for case in approved]
        if branch == 'grid':
            exact = sum(r['grid_exact'] for r in subset)
            shape = sum(r['grid_shape_correct'] for r in subset)
            valid = sum(r['grid_valid'] for r in subset)
            mean_nll = (math.fsum(r['grid_nll']['nll_sum'] for r in subset)
                        / sum(r['grid_nll']['token_count'] for r in subset)) if nll_enabled else None
            metrics = {'grid_exact': exact, 'grid_shape_correct': shape,
                       'grid_valid': valid, 'grid_mean_nll': mean_nll}
            keys[update] = (-exact, -shape, -valid, mean_nll if nll_enabled else 0, update)
        else:
            exact = sum(r['program_exact'] for r in subset)
            fit = sum(r['program_all_demos_fit'] for r in subset)
            valid = sum(r['program_valid_query'] for r in subset)
            metrics = {'program_exact': exact, 'program_all_demos_fit': fit,
                       'program_valid_query': valid}
            keys[update] = (-exact, -fit, -valid, update)
        summaries.append({'checkpoint_update': update, 'denominator': len(approved), **metrics})
    ranking = sorted(CHECKPOINT_UPDATES, key=keys.__getitem__)
    result = {
        'format': 'irisx/qwen-canary-checkpoint-ranking-v1',
        'policy_sha256': RANKING_POLICY_SHA256, 'branch': branch,
        'approved_canary_ids': approved, 'minimum_canaries': minimum_canaries,
        'input_rows': ordered, 'rows_sha256': digest(ordered),
        'ranked_checkpoint_updates': ranking, 'best_checkpoint_update': ranking[0],
        'retained_checkpoint_updates': list(CHECKPOINT_UPDATES),
        'affects_portfolio_order': False, 'summaries': summaries,
        'nll_tiebreak_used': nll_enabled,
        'nll_tiebreak_status': ('fully-matched' if nll_enabled else 'incomplete-disabled')
        if branch == 'grid' else 'not-applicable-program-branch',
    }
    result['ranking_sha256'] = digest(result)
    return result


def _validate_decision(decision):
    _require(type(decision) is dict and type(decision.get('inputs')) is dict,
             'portfolio decision object required')
    inputs = _closed(decision['inputs'], ('task', 'candidates'), 'decision inputs')
    recomputed = select_program_portfolio(inputs['task'], inputs['candidates'])
    _require(canonical(decision) == canonical(recomputed), 'portfolio decision differs from deterministic replay')
    return recomputed


def _validate_ranking(ranking):
    _require(type(ranking) is dict, 'canary ranking object required')
    required = ('branch', 'input_rows', 'approved_canary_ids', 'minimum_canaries')
    _require(all(k in ranking for k in required), 'canary ranking inputs missing')
    recomputed = rank_checkpoints(ranking['branch'], ranking['input_rows'],
                                 ranking['approved_canary_ids'], minimum_canaries=ranking['minimum_canaries'])
    _require(canonical(ranking) == canonical(recomputed), 'canary ranking differs from deterministic replay')
    return recomputed


def seal_selection(decisions, rankings, protocol_sha256):
    """Return deterministic target-free seal to persist BEFORE holdout scoring.

    Requires both branch rankings and at least one task decision. The seal is a
    content commitment, not proof of wall-clock ordering; enforce phase ordering
    in the caller and preserve the externally recorded seal digest.
    """
    _sha(protocol_sha256, 'protocol_sha256')
    _require(type(decisions) is list and decisions, 'nonempty decision list required')
    _require(type(rankings) is list and len(rankings) == 2, 'both branch rankings required')
    checked_decisions = [_validate_decision(d) for d in decisions]
    checked_rankings = [_validate_ranking(r) for r in rankings]
    _require(len({d['task_id'] for d in checked_decisions}) == len(checked_decisions), 'duplicate task decision')
    for candidate_id in CANDIDATE_ORDER:
        identities = {c['checkpoint_sha256'] for d in checked_decisions
                      for c in d['inputs']['candidates'] if c['candidate_id'] == candidate_id}
        _require(len(identities) == 1, 'checkpoint identity differs between tasks')
    _require({r['branch'] for r in checked_rankings} == {'grid', 'program'}, 'exactly both branch rankings required')
    _require(checked_rankings[0]['approved_canary_ids'] == checked_rankings[1]['approved_canary_ids'],
             'branch canary panels differ')
    _require(checked_rankings[0]['minimum_canaries'] == checked_rankings[1]['minimum_canaries'],
             'branch canary coverage policies differ')
    payload = {
        'format': 'irisx/qwen-portfolio-selection-seal-v1',
        'phase': 'selected-before-noncanary-target-scoring',
        'protocol_sha256': protocol_sha256,
        'selection_policy_sha256': SELECTION_POLICY_SHA256,
        'ranking_policy_sha256': RANKING_POLICY_SHA256,
        'decisions': sorted(checked_decisions, key=lambda d: d['task_id']),
        'rankings': sorted(checked_rankings, key=lambda r: r['branch']),
    }
    return {'payload': payload, 'selection_sha256': digest(payload)}


def verify_selection_seal(seal, expected_sha256, protocol_sha256):
    """Verify against the pre-score externally committed digest; return a copy."""
    _closed(seal, ('payload', 'selection_sha256'), 'selection seal')
    _sha(expected_sha256, 'externally committed selection SHA256')
    _sha(protocol_sha256, 'protocol_sha256')
    payload = _closed(seal['payload'], ('format', 'phase', 'protocol_sha256',
        'selection_policy_sha256', 'ranking_policy_sha256', 'decisions', 'rankings'), 'seal payload')
    _require(seal['selection_sha256'] == expected_sha256 == digest(payload), 'selection seal digest differs')
    replayed = seal_selection(payload['decisions'], payload['rankings'], protocol_sha256)
    _require(canonical(replayed) == canonical(seal), 'selection seal deterministic replay differs')
    return deepcopy(payload)

"""Independent stdlib-only selector tests, including seen-v18 retrospective replay.

Run from worktree with python [-O] -m unittest discover -s
 tools/arc_qwen_portfolio_20261012/tests -p test_selection.py -v
No generation, inference, model import, external provider call, or source execution.
"""
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import unittest

from tools.arc_qwen_portfolio_20261012 import selection as s


def task(task_id='seen-fixture:a'):
    return {'task_id': task_id, 'demos': [
        {'input': [[1, 2]], 'output': [[2, 1]]},
        {'input': [[3], [4]], 'output': [[4], [3]]},
    ], 'query_input': [[5, 6]]}


def candidate(name, value=None, *, fitted=True, prediction=((6, 5),), generation='valid'):
    value = task() if value is None else value
    source_sha = s.source_digest('fixture source ' + name)
    row = {'candidate_id': name, 'checkpoint_sha256': s.digest('checkpoint ' + name),
           'generation_status': generation, 'source_sha256': source_sha, 'proof': None, 'query': None}
    if generation != 'valid':
        row['source_sha256'] = None
        return row
    count = len(value['demos'])
    row['proof'] = {
        'source_sha256': source_sha, 'demos_sha256': s.digest(value['demos']),
        'verifier_sha256': s.VERIFIER_SHA256, 'proof_sha256': s.digest('proof ' + name),
        'known': True, 'all_demos_fit': fitted, 'demo_count': count,
        'matched_demo_indices': list(range(count)) if fitted else list(range(count - 1)),
        'owned_descendants_stopped': True,
    }
    if fitted:
        row['query'] = {
            'source_sha256': source_sha, 'demos_sha256': s.digest(value['demos']),
            'query_input_sha256': s.digest(value['query_input']),
            'demo_proof_sha256': row['proof']['proof_sha256'],
            'verifier_sha256': s.QUERY_VERIFIER_SHA256, 'status': 'valid',
            'output': [list(r) for r in prediction], 'demo_replay_verified': True,
            'owned_descendants_stopped': True,
        }
    return row


def pool(value=None):
    return [candidate(name, value) for name in s.CANDIDATE_ORDER]


def canary_rows(branch='program'):
    rows = []
    for update in s.CHECKPOINT_UPDATES:
        for case in ('canary:a', 'canary:b', 'canary:c'):
            row = {'branch': branch, 'scope': 'canary', 'case_id': case, 'checkpoint_update': update}
            if branch == 'program':
                row.update(program_exact=False, program_all_demos_fit=True, program_valid_query=True)
            else:
                row.update(grid_exact=False, grid_shape_correct=True, grid_valid=True,
                           grid_nll={'nll_sum': 6.0, 'token_count': 3, 'example_sha256': s.digest(case)})
            rows.append(row)
    return rows


IDS = ['canary:a', 'canary:b', 'canary:c']


class Poison:
    def __bool__(self):
        raise AssertionError('poisoned gold was read')

    def __eq__(self, other):
        raise AssertionError('poisoned gold was compared')

    def __repr__(self):
        raise AssertionError('poisoned gold was serialized')


class PortfolioTests(unittest.TestCase):
    def test_fixed_order_ignores_input_order_and_collapses_duplicates(self):
        expected = s.select_program_portfolio(task(), pool())
        self.assertEqual(expected['selected'][0]['candidate_id'], 'base')
        self.assertEqual(expected['top2'], [[[6, 5]]])
        self.assertFalse(expected['conflict'])
        self.assertFalse(expected['abstained'])
        for permutation in itertools.permutations(pool()):
            self.assertEqual(s.select_program_portfolio(task(), list(permutation)), expected)

    def test_top2_distinct_retains_first_representative_and_records_third_conflict(self):
        rows = [candidate(n, prediction=((v,),)) for n, v in zip(s.CANDIDATE_ORDER, (1, 2, 3))]
        actual = s.select_program_portfolio(task(), rows)
        self.assertEqual(actual['top1'], [[1]])
        self.assertEqual(actual['top2'], [[[1]], [[2]]])
        self.assertEqual(actual['distinct_prediction_count'], 3)
        self.assertTrue(actual['conflict'])
        self.assertEqual([x['candidate_id'] for x in actual['selected']], ['base', 'program8'])

    def test_duplicate_first_two_does_not_hide_distinct_third(self):
        rows = pool()
        rows[2]['query']['output'] = [[9]]
        result = s.select_program_portfolio(task(), rows)
        self.assertEqual([x['candidate_id'] for x in result['selected']], ['base', 'program16'])
        self.assertEqual(result['distinct_prediction_count'], 2)

    def test_full_demo_fit_is_eligibility_gate_without_fallback(self):
        rows = [candidate(n, fitted=False) for n in s.CANDIDATE_ORDER]
        actual = s.select_program_portfolio(task(), rows)
        self.assertTrue(actual['abstained'])
        self.assertIsNone(actual['top1'])
        self.assertEqual(actual['top2'], [])
        self.assertEqual(actual['abstention_reason'], 'no-eligible-program-candidate')
        self.assertEqual(len(actual['exclusions']), 3)
        rows[2] = candidate('program16')
        self.assertEqual(s.select_program_portfolio(task(), rows)['selected'][0]['candidate_id'], 'program16')

    def test_missing_duplicate_extra_or_cross_branch_candidate_rejected(self):
        for rows in (pool()[:-1], pool() + [candidate('base')], [candidate('base')] * 3):
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                s.select_program_portfolio(task(), rows)
        rows = pool()
        rows[1]['candidate_id'] = 'grid8'
        with self.assertRaises(ValueError):
            s.select_program_portfolio(task(), rows)

    def test_failed_generations_are_explicit_fixed_denominator_entries(self):
        rows = [candidate('base', generation='unavailable'), candidate('program8', generation='invalid'),
                candidate('program16')]
        result = s.select_program_portfolio(task(), rows)
        self.assertEqual(result['eligible_candidate_ids'], ['program16'])
        self.assertEqual(len(result['inputs']['candidates']), 3)
        rows[0]['source_sha256'] = s.digest('source')
        with self.assertRaises(ValueError):
            s.select_program_portfolio(task(), rows)

    def test_absent_unknown_and_failed_query_abstain(self):
        rows = pool()
        rows[0]['proof'] = None
        rows[0]['query'] = None
        rows[1]['proof']['known'] = False
        rows[1]['proof']['all_demos_fit'] = False
        rows[1]['query'] = None
        rows[2]['query']['status'] = 'unavailable'
        rows[2]['query']['output'] = None
        rows[2]['query']['demo_replay_verified'] = False
        self.assertTrue(s.select_program_portfolio(task(), rows)['abstained'])

    def test_no_query_after_partial_fit(self):
        rows = pool()
        rows[0]['proof']['matched_demo_indices'] = [0]
        rows[0]['proof']['all_demos_fit'] = False
        with self.assertRaisesRegex(ValueError, 'before full demo fit'):
            s.select_program_portfolio(task(), rows)

    def test_untruthful_fit_claims_count_and_duplicate_indices_rejected(self):
        for change in ({'matched_demo_indices': [0]}, {'demo_count': 1, 'matched_demo_indices': [0]},
                       {'known': False}, {'matched_demo_indices': [0, 0]},
                       {'matched_demo_indices': [1, 0]}, {'matched_demo_indices': [0, True]},
                       {'matched_demo_indices': [0, 1, 2]}):
            rows = pool()
            rows[0]['proof'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                s.select_program_portfolio(task(), rows)

    def test_bindings_pin_every_input_and_proof(self):
        mutations = [(['source_sha256'], 'f' * 64), (['proof', 'demos_sha256'], 'f' * 64),
                     (['proof', 'verifier_sha256'], 'f' * 64),
                     (['query', 'source_sha256'], 'f' * 64), (['query', 'demos_sha256'], 'f' * 64),
                     (['query', 'query_input_sha256'], 'f' * 64),
                     (['query', 'demo_proof_sha256'], 'f' * 64),
                     (['query', 'verifier_sha256'], 'f' * 64)]
        for path, value in mutations:
            rows = pool()
            target = rows[0]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                s.select_program_portfolio(task(), rows)

    def test_strict_boolean_integer_and_status_types(self):
        mutations = [(['proof', 'known'], 1), (['proof', 'all_demos_fit'], 1),
                     (['proof', 'demo_count'], True), (['query', 'demo_replay_verified'], 1),
                     (['query', 'owned_descendants_stopped'], 1),
                     (['generation_status'], True), (['query', 'status'], 'fit')]
        for path, value in mutations:
            rows = pool()
            target = rows[0]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                s.select_program_portfolio(task(), rows)

    def test_unstopped_processes_and_unverified_query_replay_rejected(self):
        for section, key in [('proof', 'owned_descendants_stopped'), ('query', 'owned_descendants_stopped'),
                             ('query', 'demo_replay_verified')]:
            rows = pool()
            rows[0][section][key] = False
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                s.select_program_portfolio(task(), rows)

    def test_grid_validity_only_not_expected_shape(self):
        rows = pool()
        rows[0]['query']['output'] = [[1], [2], [3]]
        self.assertEqual(s.select_program_portfolio(task(), rows)['top1'], [[1], [2], [3]])
        for bad in ([], [[]], [[1], [2, 3]], [[True]], [[1.0]], [[10]], [[-1]], [[0] * 31], [[0]] * 31):
            rows = pool()
            rows[0]['query']['output'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                s.select_program_portfolio(task(), rows)

    def test_nonvalid_query_cannot_smuggle_output(self):
        rows = pool()
        rows[0]['query']['status'] = 'invalid'
        with self.assertRaises(ValueError):
            s.select_program_portfolio(task(), rows)

    def test_gold_score_nll_and_unknown_fields_rejected_at_every_boundary(self):
        for forbidden in ('target', 'gold', 'query_output', 'score', 'grid_nll', 'expected_shape', 'surprise'):
            value = task()
            value[forbidden] = Poison()
            with self.subTest(layer='task', key=forbidden), self.assertRaises(ValueError):
                s.select_program_portfolio(value, pool())
            for layer in ('candidate', 'proof', 'query'):
                rows = pool()
                selected = rows[0] if layer == 'candidate' else rows[0][layer]
                selected[forbidden] = Poison()
                with self.subTest(layer=layer, key=forbidden), self.assertRaises(ValueError):
                    s.select_program_portfolio(task(), rows)
        value = task()
        value['demos'][0]['gold'] = Poison()
        with self.assertRaises(ValueError):
            s.select_program_portfolio(value, pool())

    def test_selector_does_not_mutate_inputs_or_share_output_aliases(self):
        value, rows = task(), pool()
        before = deepcopy((value, rows))
        result = s.select_program_portfolio(value, rows)
        self.assertEqual((value, rows), before)
        result['top1'][0][0] = 0
        result['inputs']['task']['demos'][0]['input'][0][0] = 0
        self.assertEqual((value, rows), before)


class CanaryRankingTests(unittest.TestCase):
    def test_program_rank_uses_program_metrics_keeps_every_checkpoint(self):
        rows = canary_rows()
        for row in rows:
            row['program_exact'] = row['checkpoint_update'] == 16
        actual = s.rank_checkpoints('program', rows, IDS)
        self.assertEqual(actual['ranked_checkpoint_updates'], [16, 0, 8])
        self.assertEqual(actual['retained_checkpoint_updates'], [0, 8, 16])
        self.assertFalse(actual['affects_portfolio_order'])
        self.assertFalse(actual['nll_tiebreak_used'])
        self.assertEqual(actual['nll_tiebreak_status'], 'not-applicable-program-branch')
        self.assertEqual(actual, s.rank_checkpoints('program', list(reversed(rows)), list(reversed(IDS))))

    def test_program_secondary_fit_then_query_validity_then_earlier(self):
        rows = canary_rows()
        for row in rows:
            if row['checkpoint_update'] == 0:
                row.update(program_all_demos_fit=False, program_valid_query=False)
            elif row['checkpoint_update'] == 8:
                row['program_valid_query'] = False
        self.assertEqual(s.rank_checkpoints('program', rows, IDS)['ranked_checkpoint_updates'], [16, 8, 0])
        self.assertEqual(s.rank_checkpoints('program', canary_rows(), IDS)['best_checkpoint_update'], 0)

    def test_program_rows_reject_grid_nll_and_other_branch_metrics(self):
        for key in ('grid_nll', 'grid_exact', 'score', 'target'):
            rows = canary_rows()
            rows[0][key] = Poison()
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.rank_checkpoints('program', rows, IDS)

    def test_grid_priority_exact_before_shape_before_valid_before_nll(self):
        rows = canary_rows('grid')
        for row in rows:
            u = row['checkpoint_update']
            row['grid_exact'] = u == 16
            row['grid_nll']['nll_sum'] = {0: 0.01, 8: 0.001, 16: 100}[u]
        self.assertEqual(s.rank_checkpoints('grid', rows, IDS)['ranked_checkpoint_updates'], [16, 8, 0])
        for row in rows:
            row['grid_exact'] = False
            row['grid_shape_correct'] = row['checkpoint_update'] != 8
        self.assertEqual(s.rank_checkpoints('grid', rows, IDS)['ranked_checkpoint_updates'], [0, 16, 8])
        for row in rows:
            row['grid_shape_correct'] = False
            row['grid_valid'] = row['checkpoint_update'] != 8
        self.assertEqual(s.rank_checkpoints('grid', rows, IDS)['ranked_checkpoint_updates'], [0, 16, 8])

    def test_grid_nll_matched_tie_is_token_weighted(self):
        rows = canary_rows('grid')
        for row in rows:
            if row['case_id'] == 'canary:a':
                row['grid_nll']['token_count'] = 100
                row['grid_nll']['nll_sum'] = {0: 100, 8: 50, 16: 75}[row['checkpoint_update']]
        actual = s.rank_checkpoints('grid', rows, IDS)
        self.assertEqual(actual['ranked_checkpoint_updates'], [8, 16, 0])
        self.assertTrue(actual['nll_tiebreak_used'])
        self.assertAlmostEqual(actual['summaries'][0]['grid_mean_nll'], 112 / 106)

    def test_any_missing_nll_disables_tie_for_all_checkpoints(self):
        rows = canary_rows('grid')
        rows[0]['grid_nll'] = None
        for row in rows[1:]:
            row['grid_nll']['nll_sum'] = 0.0 if row['checkpoint_update'] == 16 else 100
        actual = s.rank_checkpoints('grid', rows, IDS)
        self.assertFalse(actual['nll_tiebreak_used'])
        self.assertEqual(actual['ranked_checkpoint_updates'], [0, 8, 16])
        self.assertTrue(all(r['grid_mean_nll'] is None for r in actual['summaries']))

    def test_nll_mismatched_examples_or_token_masks_are_rejected(self):
        for key, value in [('example_sha256', 'f' * 64), ('token_count', 4)]:
            rows = canary_rows('grid')
            rows[0]['grid_nll'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.rank_checkpoints('grid', rows, IDS)

    def test_nll_nonfinite_negative_boolean_tokens_and_gold_rejected(self):
        for key, value in [('nll_sum', float('nan')), ('nll_sum', float('inf')), ('nll_sum', -1),
                           ('nll_sum', True), ('token_count', 0), ('token_count', True), ('gold', Poison())]:
            rows = canary_rows('grid')
            rows[0]['grid_nll'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.rank_checkpoints('grid', rows, IDS)

    def test_missing_duplicate_unapproved_and_extra_checkpoint_rows_rejected(self):
        base = canary_rows()
        for rows in (base[:-1], base + [base[0]], base[3:]):
            with self.subTest(length=len(rows)), self.assertRaises(ValueError):
                s.rank_checkpoints('program', rows, IDS)
        for key, value in [('checkpoint_update', 4), ('checkpoint_update', True),
                           ('case_id', 'canary:unapproved'), ('branch', 'grid')]:
            rows = canary_rows()
            rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.rank_checkpoints('program', rows, IDS)

    def test_scope_poison_and_seen_old13_not_approved_canaries(self):
        for scope in ('holdout', 'public', 'PUBLIC120', 'seen_regression13', 'exposed_development',
                      'same_family_query12', 'heldout_family6', 'real_arc_holdout24'):
            rows = canary_rows()
            rows[0]['scope'] = scope
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                s.rank_checkpoints('program', rows, IDS)
        with self.assertRaises(ValueError):
            s.rank_checkpoints('program', [], ['public:a', 'public:b', 'public:c'])

    def test_at_least_three_canaries_and_configured_full_panel_required(self):
        for ids, minimum in [(IDS[:1], 3), (IDS[:2], 3), (IDS, 2), (IDS, 8), (IDS + [IDS[0]], 3)]:
            with self.subTest(ids=ids, minimum=minimum), self.assertRaises(ValueError):
                s.rank_checkpoints('program', canary_rows(), ids, minimum_canaries=minimum)
        ids = ['canary:' + str(n) for n in range(8)]
        rows = []
        for row in canary_rows():
            if row['case_id'] == 'canary:a':
                rows.extend([{**row, 'case_id': case} for case in ids])
        self.assertEqual(s.rank_checkpoints('program', rows, ids, minimum_canaries=8)['summaries'][0]['denominator'], 8)

    def test_inconsistent_metric_claims_rejected(self):
        for branch, changes in [('program', {'program_exact': True, 'program_valid_query': False}),
                                ('program', {'program_all_demos_fit': False}),
                                ('grid', {'grid_exact': True, 'grid_shape_correct': False}),
                                ('grid', {'grid_valid': False}), ('program', {'program_exact': 1})]:
            rows = canary_rows(branch)
            rows[0].update(changes)
            with self.subTest(branch=branch, changes=changes), self.assertRaises(ValueError):
                s.rank_checkpoints(branch, rows, IDS)


class SealTests(unittest.TestCase):
    def setUp(self):
        self.protocol_sha = s.digest('fixed preregistered protocol')
        self.decision = s.select_program_portfolio(task(), pool())
        self.rankings = [s.rank_checkpoints(branch, canary_rows(branch), IDS) for branch in ('grid', 'program')]
        self.seal = s.seal_selection([self.decision], self.rankings, self.protocol_sha)

    def test_seal_replays_deterministically_and_returns_detached_copy(self):
        result = s.verify_selection_seal(self.seal, self.seal['selection_sha256'], self.protocol_sha)
        self.assertEqual(result, self.seal['payload'])
        result['phase'] = 'mutated'
        self.assertNotEqual(result, self.seal['payload'])
        self.assertEqual(self.seal, s.seal_selection([self.decision], list(reversed(self.rankings)), self.protocol_sha))

    def test_mutation_external_hash_protocol_and_phase_rejected(self):
        for mutation in ('prediction', 'phase', 'unknown'):
            seal = deepcopy(self.seal)
            if mutation == 'prediction':
                seal['payload']['decisions'][0]['top1'][0][0] = 0
            elif mutation == 'phase':
                seal['payload']['phase'] = 'scored-already'
            else:
                seal['payload']['gold'] = [[0]]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                s.verify_selection_seal(seal, self.seal['selection_sha256'], self.protocol_sha)
        for external, protocol in [('0' * 64, self.protocol_sha), (self.seal['selection_sha256'], '0' * 64)]:
            with self.assertRaises(ValueError):
                s.verify_selection_seal(self.seal, external, protocol)

    def test_self_rehashed_tampering_still_fails_replay(self):
        seal = deepcopy(self.seal)
        seal['payload']['decisions'][0]['top1'][0][0] = 0
        decision = seal['payload']['decisions'][0]
        decision['decision_sha256'] = s.digest({k: v for k, v in decision.items() if k != 'decision_sha256'})
        seal['selection_sha256'] = s.digest(seal['payload'])
        with self.assertRaises(ValueError):
            s.verify_selection_seal(seal, seal['selection_sha256'], self.protocol_sha)

    def test_missing_rank_branch_duplicate_task_unknown_fields_rejected(self):
        for decisions, rankings in [([], self.rankings), ([self.decision] * 2, self.rankings),
                                    ([self.decision], self.rankings[:1]), ([self.decision], [self.rankings[0]] * 2)]:
            with self.assertRaises(ValueError):
                s.seal_selection(decisions, rankings, self.protocol_sha)
        changed = deepcopy(self.decision)
        changed['gold'] = [[0]]
        with self.assertRaises(ValueError):
            s.seal_selection([changed], self.rankings, self.protocol_sha)

    def test_checkpoint_identity_must_be_constant_across_tasks(self):
        other = task('seen-fixture:b')
        rows = pool(other)
        rows[0]['checkpoint_sha256'] = '0' * 64
        decision = s.select_program_portfolio(other, rows)
        with self.assertRaises(ValueError):
            s.seal_selection([self.decision, decision], self.rankings, self.protocol_sha)

    def test_numerical_program_rank_never_changes_portfolio_order(self):
        rows = canary_rows()
        for row in rows:
            row['program_exact'] = row['checkpoint_update'] == 16
        self.rankings[1] = s.rank_checkpoints('program', rows, IDS)
        seal = s.seal_selection([self.decision], self.rankings, self.protocol_sha)
        self.assertEqual(seal['payload']['rankings'][1]['best_checkpoint_update'], 16)
        self.assertEqual(seal['payload']['decisions'][0]['selected'][0]['candidate_id'], 'base')


class SeenV18RetrospectiveRegression(unittest.TestCase):
    """Seen historical evidence only. Not a new run or held-out effectiveness test."""
    def test_seen_v18_old13_complementarity_without_oracle_selection(self):
        path = Path(__file__).resolve().parents[5] / 'learning-agent-qwen-manual-20261012/analysis/manual-v18-final/per-case.json'
        if not path.is_file():
            self.skipTest('seen-v18 retrospective source artifact is not bundled')
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'c8c5e3cfab79238c1869b822819f457a6f062a5bc289310bd12c0466b1fb6ef6')
        rows = json.loads(raw)
        observations = {'base': 'frozen-base', 'program8': 'program_lora/update-8',
                        'program16': 'program_lora/update-16'}
        observed = {name: {r['case_id']: r for r in rows if r['observation'] == label}
                    for name, label in observations.items()}
        self.assertEqual([sum(r['program_exact'] for r in observed[name].values()) for name in s.CANDIDATE_ORDER], [5, 9, 11])
        decisions = []
        for case_id in sorted(observed['base']):
            # Synthetic closed task/proof bindings around actual recorded demo-fit
            # and output facts. This tests selection only, not live VM validation.
            value = task('seen-v18:' + case_id)
            candidates = []
            for name in s.CANDIDATE_ORDER:
                record = observed[name][case_id]
                cand = candidate(name, value, fitted=record['program_all_demo_fit'],
                                 prediction=record['program_prediction'] or ((0,),))
                candidates.append(cand)
            decisions.append((case_id, s.select_program_portfolio(value, candidates)))
        # Selection finishes before this retrospective harness touches target.
        exact = sum(d['top1'] == observed['base'][case]['target'] for case, d in decisions)
        disjoint = [(case, d) for case, d in decisions if case.startswith('authored-disjoint:')]
        self.assertEqual(len(decisions), 13)
        self.assertEqual(exact, 12)
        self.assertEqual(sum(d['top1'] == observed['base'][case]['target'] for case, d in disjoint), 6)
        self.assertEqual(sum(d['abstained'] for _, d in decisions), 1)
        self.assertTrue(all(not d['conflict'] for _, d in decisions))
        with self.assertRaises(ValueError):
            s.rank_checkpoints('program', rows, IDS)


if __name__ == '__main__':
    unittest.main()

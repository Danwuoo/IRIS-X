"""Synthetic-only full-denominator scoring and fail-closed gold-open tests."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.arc_public_research_20261010 import public_data as data, public_evaluator as ev, query_executor as query
from tools.arc_public_research_20261010.tests.test_public_data import make_assets
from tools.arc_public_research_20261010.tests.test_query_executor import candidate, IDENTITY


def bindings():
    return {'run_id': 'synthetic-run', 'source_identity': ev.source_identity(),
            'environment_plan_sha256': 'e' * 64, 'actual_environment_lock_sha256': 'f' * 64,
            'prediction_origin': 'synthetic_cpu', 'model_sha256': '0' * 64}


def disabled():
    return {'mode': 'model-disabled', 'model_disabled': True, 'physical_calls': 0, 'pending_reservations': 0}


def predictions(root, assets, *, with_predictions=False):
    root = Path(root); root.mkdir()
    solver = data.load_solver_tasks(assets['solver_root'], assets['solver_manifest_sha256'])
    challenges = solver['challenges']
    candidates = {'00000000': [candidate(task_id='00000000')]} if with_predictions else {}
    for policy in data.POLICIES:
        selection = query.freeze_selections(challenges, candidates, run_id='synthetic-run', policy=policy, output_root=root)
        receipts = {}
        if with_predictions:
            receipts['00000000'] = []
            for index, pair in enumerate(challenges['00000000']['test']):
                receipt = query.query_execute(IDENTITY, [pair['input']], root / 'query-evidence', policy + str(index),
                                              selection_sha256=selection['selection_sha256'])
                receipts['00000000'].append({'candidate_id': 'candidate-one', 'test_index': index, 'receipt': receipt})
        pool = query.build_policy_pool(challenges, selection, receipts, run_id='synthetic-run', policy=policy)
        data.write_new(root / ('pools-' + policy + '.json'), pool)
        data.write_new(root / ('prediction-proof-' + policy + '.json'), {'selections': selection, 'query_receipts': receipts})
    return root


class EvaluatorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.assets = make_assets(self.root)

    def seal(self, root, **kwargs):
        return ev.seal_predictions(root, solver_root=self.assets['solver_root'],
            solver_manifest_sha256=self.assets['solver_manifest_sha256'],
            evaluator_manifest_sha256=self.assets['evaluator_manifest_sha256'],
            owner_proof=kwargs.get('owner_proof', disabled()), bindings=kwargs.get('binding', bindings()))

    def score(self, root, seal):
        return ev.evaluate_sealed(root, seal['seal_sha256'], solver_root=self.assets['solver_root'],
            evaluator_root=self.assets['evaluator_root'], output_root=self.root / 'evaluator-output')

    def test_full_synthetic_multiquery_score_has_fixed_micro_and_distinct_task_metrics(self):
        root = predictions(self.root / 'predictions', self.assets, with_predictions=True)
        seal = self.seal(root); result = self.score(root, seal)
        self.assertEqual(result['status'], 'SCORED')
        self.assertEqual(result['measurement'], 'research-public-development')
        self.assertEqual(result['policy_prediction_origins'], {policy: 'synthetic_cpu' for policy in data.POLICIES})
        self.assertFalse(result['competition_gpu_equivalent'])
        self.assertFalse(result['gpu_hardware_verified'])
        self.assertFalse(result['training_used']); self.assertFalse(result['adapter_used'])
        self.assertIsNone(result['official_score'])
        self.assertEqual(result['evidence_mode'], 'synthetic-test-only')
        self.assertEqual(result['prediction_origin'], 'synthetic_cpu')
        self.assertFalse(result['generation_may_resume'])
        self.assertNotIn('reports', result)
        for policy in data.POLICIES:
            metrics = result['policies'][policy]['metrics']
            self.assertEqual(metrics['pass_at_1']['numerator'], 1)
            self.assertEqual(metrics['pass_at_1']['denominator'], 167)
            self.assertEqual(metrics['pass_at_2']['numerator'], 1)
            self.assertEqual(metrics['empty_pool']['numerator'], 165)
            self.assertEqual(metrics['task_average_pass_at_2']['denominator'], 120)
            self.assertEqual(metrics['task_average_pass_at_2']['numerator'], .5)
            self.assertEqual(metrics['tasks_all_tests_pass_at_2']['numerator'], 0)

    def test_policy_origin_labels_require_actual_model_calls(self):
        cpu = {'owner_proof': disabled()}
        expected_cpu = {'raw': 'not_executed', 'strict': 'not_executed',
                        'uniform': 'research_cpu', 'shape': 'research_cpu'}
        self.assertEqual(ev._policy_prediction_origins(cpu, 'public-development'), expected_cpu)
        remote = {'owner_proof': {'mode': 'remote-owner', 'physical_calls': 0}}
        self.assertEqual(ev._policy_prediction_origins(remote, 'public-development'), expected_cpu)
        remote['owner_proof']['physical_calls'] = 1
        self.assertEqual(ev._policy_prediction_origins(remote, 'public-development'),
                         {**expected_cpu, 'raw': 'research_gpu', 'strict': 'research_gpu'})
        self.assertEqual(ev._policy_prediction_origins(remote, 'synthetic-test-only'),
                         {policy: 'synthetic_cpu' for policy in data.POLICIES})

    def test_complete_missing_excluded_empty_predictions_retain167(self):
        root = predictions(self.root / 'predictions', self.assets)
        result = self.score(root, self.seal(root))
        self.assertEqual(result['status'], 'SCORED')
        for policy in result['policies'].values():
            self.assertEqual(policy['metrics']['pass_at_2']['denominator'], 167)
            self.assertEqual(policy['metrics']['empty_pool']['numerator'], 167)
            self.assertEqual(policy['metrics']['unobserved_test_record']['numerator'], 0)

    def test_pending_owner_and_fake_boolean_stop_block_before_gold(self):
        root = predictions(self.root / 'predictions', self.assets)
        proof = disabled(); proof['pending_reservations'] = 1
        with patch('tools.arc_offline_evaluation.load_pinned_reference', side_effect=AssertionError('GOLD OPENED')) as gold:
            with self.assertRaises(ValueError):
                self.seal(root, owner_proof=proof)
            with self.assertRaises(ValueError):
                self.seal(root, owner_proof={'model_owner_stopped': True})
            gold.assert_not_called()

    def test_prediction_mutation_extra_partial_and_symlink_rejected_before_gold(self):
        root = predictions(self.root / 'predictions', self.assets); seal = self.seal(root)
        for name, body in (('extra.json', b'{}'), ('interrupted.partial', b'{}')):
            (root / name).write_bytes(body)
            with patch('tools.arc_offline_evaluation.load_pinned_reference', side_effect=AssertionError('GOLD OPENED')) as gold:
                with self.assertRaises(ValueError): self.score(root, seal)
                gold.assert_not_called()
            (root / name).unlink()
        (root / 'alias').symlink_to(root / 'pools-raw.json')
        with self.assertRaisesRegex(ValueError, 'symlink'): self.score(root, seal)
        (root / 'alias').unlink()
        (root / 'pools-raw.json').write_text('{"truncated":')
        with self.assertRaises(ValueError): self.score(root, seal)

    def test_foreign_pool_and_unfitted_filler_cannot_seal(self):
        root = predictions(self.root / 'predictions', self.assets)
        path = root / 'pools-raw.json'; pool = data.parse_json(path.read_bytes())
        pool['records'][0]['tests'][0].update(ranked_grids=[[[0]]], status='partial')
        path.write_bytes(data.canonical(pool))
        with self.assertRaisesRegex(ValueError, 'pools differ'):
            self.seal(root)

    def test_wrong_origin_and_overlap_rejected(self):
        root = predictions(self.root / 'predictions', self.assets)
        value = bindings(); value['prediction_origin'] = 'research_gpu'
        with self.assertRaises(ValueError): self.seal(root, binding=value)
        seal = self.seal(root)
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            ev.evaluate_sealed(root, seal['seal_sha256'], solver_root=self.assets['solver_root'],
                evaluator_root=self.assets['evaluator_root'], output_root=root / 'output')

    def test_bad_evaluator_source_is_blocked_not_zero_score(self):
        root = predictions(self.root / 'predictions', self.assets); seal = self.seal(root)
        target = Path(self.assets['evaluator_root']) / 'upstream/data/evaluation/00000000.json'
        target.write_bytes(b'{}')
        result = self.score(root, seal)
        self.assertEqual(result['status'], 'SCORING_BLOCKED')
        self.assertNotIn('policies', result)
        self.assertIsNone(result['official_score'])


if __name__ == '__main__':
    unittest.main()

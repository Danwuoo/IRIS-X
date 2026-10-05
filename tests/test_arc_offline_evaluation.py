"""Behavioral regressions for shared offline evidence; all grids are synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import arc_offline_evaluation as evaluation
from tools import report_arc_offline as report
from tools.nvarc_native_multitask import digest


def fixture():
    challenges = {'a': {'train': [{'input': [[1]], 'output': [[2]]}],
        'test': [{'input': [[v]]} for v in (3, 4, 5, 6)]},
        'b': {'train': [{'input': [[6]], 'output': [[7]]}], 'test': [{'input': [[8]]}]}}
    truth = {'a': [[[0]], [[2]], [[3]], [[4]]], 'b': [[[5]]]}
    pools = {'format': evaluation.POOL_FORMAT, 'run_id': 'synthetic-left', 'method': 'synthetic fixture',
        'challenges_digest': digest(challenges), 'parent_wall_seconds': 10, 'records': []}
    for key, grids in [('a', [[], [[[9]]], [[[1]], [[2]], [[3]]], [[[4]]]]), ('b', [[[[5]]]])]:
        pools['records'].append({'task_id': key, 'task_digest': digest(challenges[key]),
            'timings': {'training_seconds': 0, 'solve_seconds': 12, 'reset_seconds': 2, 'total_seconds': 20},
            'tests': [{'test_index': i, 'input_digest': digest(challenges[key]['test'][i]['input']),
                       'ranked_grids': pool, 'status': 'partial'} for i, pool in enumerate(grids)]})
    return challenges, truth, pools


def official(public_score=None, error='Notebook Threw Exception'):
    return {'format': evaluation.OFFICIAL_FORMAT, 'provider': 'Kaggle', 'competition': 'synthetic',
        'reference': 'fixture-receipt', 'kernel': 'fixture/kernel', 'kernel_version': 1,
        'status': 'COMPLETE', 'outcome': 'Notebook Threw Exception' if error else 'scored', 'error': error,
        'public_score': public_score, 'private_score': None, 'score_units': 'provider units',
        'observed_at': '2026-10-05T12:00:00+08:00', 'receipt_sha256': 'a'*64}


class OfflineEvaluationTests(unittest.TestCase):
    def test_same_ids_do_not_establish_demonstration_or_test_identity(self):
        challenges, _, pools = fixture(); variant = copy.deepcopy(challenges)
        variant['a']['train'][0]['output'] = [[9]]
        source = evaluation.compare_sources(variant, challenges)
        self.assertFalse(source['exact_reference_input_content'])
        self.assertEqual(source['common_task_ids'], 2)
        self.assertEqual(source['matched_test_inputs'], 5)
        self.assertEqual(source['matched_test_inputs_and_demonstrations'], 1)
        with self.assertRaisesRegex(ValueError, 'source content'):
            evaluation.validate_pools(variant, pools)
        # Updating the outer hash still cannot rebind an old full-task record.
        pools['challenges_digest'] = digest(variant)
        with self.assertRaisesRegex(ValueError, 'multi-test task'):
            evaluation.validate_pools(variant, pools)

    def test_multitest_join_uses_input_content_and_preserves_order_identity(self):
        challenges, _, _ = fixture(); variant = copy.deepcopy(challenges)
        variant['a']['test'] = [{'input': [[9]]}] + list(reversed(variant['a']['test']))
        comparison = evaluation.compare_sources(variant, challenges)
        mapping = [(m['reference_test_index'], m['test_index']) for m in comparison['matches'] if m['task_id'] == 'a']
        self.assertEqual(mapping, [(0, 4), (1, 3), (2, 2), (3, 1)])
        self.assertEqual(comparison['executed']['tests'], 6)
        self.assertEqual(comparison['reference']['tests'], 5)
        self.assertFalse(comparison['exact_reference_input_content'])
        variant['a']['test'].append(copy.deepcopy(variant['a']['test'][1]))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            evaluation.compare_sources(variant, challenges)

    def test_loss_partition_and_micro_macro_denominators(self):
        challenges, truth, pools = fixture(); result = evaluation.evaluate(challenges, truth, pools)
        m = result['development_metrics']['metrics']
        self.assertEqual(m['pass_at_1']['value'], 2/5)
        self.assertEqual(m['pass_at_2']['numerator'], 2)
        self.assertEqual(m['candidate_oracle']['numerator'], 3)
        self.assertEqual(m['candidate_coverage']['numerator'], 4)
        self.assertEqual(m['empty_pool']['numerator'], 1)
        self.assertEqual(m['pool_miss']['numerator'], 1)
        self.assertEqual(m['ranking_miss']['numerator'], 1)
        self.assertEqual(m['partial_pool']['numerator'], 3)
        self.assertEqual(m['task_average_pass_at_2']['value'], .625)
        self.assertEqual(m['task_average_pass_at_2']['denominator'], 2)
        self.assertEqual(m['tasks_all_tests_pass_at_2']['numerator'], 1)
        self.assertTrue(all(m[k]['denominator'] == 5 for k in ('pass_at_1','candidate_oracle','empty_pool')))

    def test_missing_partial_records_keep_the_full_denominator_and_no_filler_credit(self):
        challenges, truth, pools = fixture()
        pools['records'].pop(); pools['records'][0]['tests'] = pools['records'][0]['tests'][:1]
        m = evaluation.evaluate(challenges, truth, pools)['development_metrics']['metrics']
        self.assertEqual(m['pass_at_2']['numerator'], 0)  # [[0]] answer, empty pool
        self.assertEqual(m['empty_pool']['numerator'], 5)
        self.assertEqual(m['unobserved_test_record']['numerator'], 4)
        self.assertEqual(m['pass_at_2']['denominator'], 5)
        with self.assertRaisesRegex(ValueError, 'multi-test denominator'):
            evaluation.evaluate(challenges, {**truth, 'a': truth['a'][:1]}, pools)

    def test_runtime_gaps_do_not_become_clock_observations(self):
        challenges, truth, pools = fixture(); r = evaluation.evaluate(challenges, truth, pools)['runtime']
        self.assertEqual(r['training']['seconds'], 0)
        self.assertEqual(r['combined_test_solve']['seconds'], 24)
        self.assertEqual(r['parent_wall']['seconds'], 10)
        for k in ('search', 'verification', 'other'):
            self.assertEqual(r[k]['state'], 'unknown'); self.assertIsNone(r[k]['seconds'])
        pools['records'].pop()
        r = evaluation.evaluate(challenges, truth, pools)['runtime']
        self.assertEqual(r['training']['state'], 'partial'); self.assertIsNone(r['training']['seconds'])
        self.assertEqual(r['combined_test_solve']['observed_seconds'], 12)

    def test_pairing_requires_full_source_then_reports_gains_and_losses(self):
        challenges, truth, pools = fixture(); left = evaluation.evaluate(challenges, truth, pools)
        right_pools = copy.deepcopy(pools); right_pools['run_id'] = 'synthetic-right'
        right_pools['records'][0]['tests'][0]['ranked_grids'] = [[[0]]]
        right_pools['records'][1]['tests'][0]['ranked_grids'] = []
        right = evaluation.evaluate(challenges, truth, right_pools)
        self.assertEqual(evaluation.paired(left, right)['pass_at_2'],
                         {'both': 1, 'gain': 1, 'loss': 1, 'neither': 2, 'denominator': 5})
        right['rows'][0]['demonstrations_digest'] = 'foreign'
        with self.assertRaisesRegex(ValueError, 'task/test identity'): evaluation.paired(left, right)

    def test_truth_and_answer_derived_metadata_rejected_at_pool_boundary(self):
        challenges, truth, pools = fixture(); before = copy.deepcopy(pools)
        evaluation.evaluate(challenges, truth, pools)
        self.assertEqual(pools, before)
        for key, value in [('solutions', truth), ('expected_output', [[0]]), ('diagnostic_label', 'ranking_miss'),
                           ('answer_rank', 3), ('stratum', 'correct')]:
            leaked = copy.deepcopy(pools); leaked['records'][0]['tests'][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'truth-free'):
                evaluation.validate_pools(challenges, leaked)
        leaked = copy.deepcopy(challenges); leaked['a']['test'][0]['output'] = [[0]]
        with self.assertRaisesRegex(ValueError, 'truth'): evaluation.content_identity(leaked)

    def test_official_exception_null_and_real_zero_remain_distinct(self):
        observed = evaluation.official_observation(official())
        self.assertEqual(observed['status'], 'COMPLETE')
        self.assertEqual(observed['score_state'], 'failed_without_score')
        self.assertIsNone(observed['public_score']); self.assertIsNone(observed['private_score'])
        zero = evaluation.official_observation(official(0, error=None))
        self.assertEqual(zero['score_state'], 'scored'); self.assertEqual(zero['public_score'], 0)
        for value in ('', '0', False, float('nan')):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'numeric or null'):
                evaluation.official_observation(official(value))

    def test_research_handoff_is_closed_aggregate_inventory(self):
        challenges, truth, pools = fixture(); scored = evaluation.evaluate(challenges, truth, pools)
        comparison = evaluation.compare_sources(challenges, challenges)
        scored['retrospective_projections'] = evaluation.projections(scored, comparison)
        data = {'format': evaluation.REPORT_FORMAT, 'source': {'repository': 'fixture', 'commit': 'fixture'},
            'reference': {'repository': 'fixture', 'commit': 'fixture', 'tasks': 2, 'tests': 5}, 'source_comparison': comparison,
            'evaluations': [scored], 'paired': [], 'official_submission': evaluation.official_observation(official()),
            'provenance': {'runs': []}}
        brief = report.research_brief(data)
        forbidden = {'rows', 'task_identities', 'ranked_grids', 'tests', 'solutions', 'matches', 'differences', 'answer_rank'}
        def inspect(value):
            if isinstance(value, dict):
                # aggregate denominator 'tests' is permitted; no list of tests.
                self.assertFalse((forbidden-{'tests'}) & value.keys())
                for key, child in value.items():
                    if key == 'tests': self.assertIsInstance(child, int)
                    inspect(child)
            elif isinstance(value, list):
                for child in value: inspect(child)
        inspect(brief)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'report'; report.write_report(output, data)
            manifest = json.loads((output/'manifest.json').read_bytes())
            self.assertEqual({r['path'] for r in manifest['members']}, {'evidence-brief.json', 'evidence-brief.md'})
            self.assertNotIn('local/evaluation.json', {r['path'] for r in manifest['members']})
            for item in manifest['members']:
                self.assertEqual(hashlib.sha256((output/item['path']).read_bytes()).hexdigest(), item['sha256'])
            with self.assertRaisesRegex(ValueError, 'new immutable'): report.write_report(output, data)

    def test_bound_file_rejects_modified_input_before_reading_evaluator_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fixture.json'; path.write_text('{}')
            bound = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(report.bound_file(bound, Path(directory)), path)
            path.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'SHA-256'): report.bound_file(bound, Path(directory))

    def test_cli_help_is_offline_without_optional_ml_packages(self):
        command = [sys.executable, str(Path(__file__).resolve().parents[1]/'tools/report_arc_offline.py'), '--help']
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--config', result.stdout)

    def test_replayable_synthetic_cli_retains_empty_and_ranking_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'fixture-report'
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'tools/report_arc_offline.py'),
                '--synthetic-fixture', '--output', str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((output/'local/evaluation.json').read_bytes())
            self.assertFalse(data['source_comparison']['exact_pinned_input_content'])
            self.assertIsNone(data['official_submission'])
            self.assertEqual(data['new_model_calls'], 0)
            m = data['evaluations'][0]['development_metrics']['metrics']
            self.assertEqual(m['pass_at_2']['numerator'], 1)
            self.assertEqual(m['candidate_oracle']['numerator'], 2)
            self.assertEqual(m['ranking_miss']['numerator'], 1)
            self.assertEqual(m['empty_pool']['numerator'], 1)

    def test_pinned_reference_loader_checks_file_digests_before_identity_claim(self):
        from irisx.artifacts import make_artifact, write_artifact
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); files = []; data = root/'data/evaluation'; data.mkdir(parents=True)
            for i in range(120):
                task = {'train': [{'input': [[1]], 'output': [[2]]}],
                    'test': [{'input': [[j+3]], 'output': [[j+5]]} for j in range(2 if i < 47 else 1)]}
                path = data/f'{i:08x}.json'; body = json.dumps(task).encode(); path.write_bytes(body)
                files.append({'path': path.relative_to(root).as_posix(), 'byte_size': len(body),
                              'content_digest': 'sha256:'+hashlib.sha256(body).hexdigest()})
            artifact = make_artifact('irisx/arc-source-provenance', 'synthetic-test-source', '1.0.0',
                {'repository': evaluation.REFERENCE_REPOSITORY, 'commit': evaluation.REFERENCE_COMMIT, 'files': files})
            provenance = root/'provenance.json'; write_artifact(provenance, artifact)
            challenges, truth, identity = evaluation.load_pinned_reference(root, provenance)
            self.assertEqual(identity['tests'], 167)
            self.assertEqual(len(challenges), 120)
            self.assertEqual(len(truth['00000000']), 2)
            self.assertNotIn('output', challenges['00000000']['test'][0])
            path.write_bytes(path.read_bytes().replace(b'5', b'9'))
            with self.assertRaisesRegex(ValueError, 'reference file digest'):
                evaluation.load_pinned_reference(root, provenance)


if __name__ == '__main__': unittest.main()

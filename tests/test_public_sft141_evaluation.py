"""Synthetic release contracts, not real-model capability claims."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools.public_sft141_diagnostic.contract import prompt_ids, answer_ids, transform
from tools.public_sft141_diagnostic.evaluate import evaluate, score_sealed
from tools.public_sft141_diagnostic.__main__ import leaf


def digest(tokens):
    return hashlib.sha256(json.dumps(tokens, separators=(',', ':')).encode()).hexdigest()


def fixture():
    plan = {'parents': []}
    gold = {'answers': {}}
    result = {'status': 'complete', 'queries': []}
    for parent_index in range(12):
        task = f'{parent_index:08x}'
        train = [{'input': [[1, 2]], 'output': [[2, 1]]}]
        tests = [{'input': [[1, 2]], 'test_index': i, 'query_id': f'{task}:{i}'} for i in range(2 if parent_index == 0 else 1)]
        parent = {'task_id': task, 'train': train, 'test': tests}
        plan['parents'].append(parent)
        gold['answers'][task] = [[[2, 1]] for _ in tests]
        for index, query in enumerate(tests):
            grid = [[2, 1]]
            views, scores = [], []
            for view in range(8):
                tokens = answer_ids(transform(grid, view))
                prompt = prompt_ids(train, query['input'], view)
                views.append({'view': view, 'status': 'complete', 'valid': True,
                              'token_ids': tokens, 'canonical_grid': grid, 'prompt_sha256': digest(prompt)})
                scores.append({'view': view, 'status': 'complete', 'nll': 1.0,
                               'prompt_sha256': digest(prompt), 'answer_sha256': digest(tokens),
                               'answer_tokens': len(tokens), 'includes_eos': True, 'normalization': 'sum-not-token-mean'})
            result['queries'].append({'task_id': task, 'test_index': index, 'query_id': query['query_id'],
                'views': views, 'candidates': [{'grid': grid, 'count': 8, 'view_nll': scores,
                    'mean_nll': 1.0, 'combined_score': 7.0}], 'vote': [grid], 'rescored': [grid],
                    'rescoring_complete': True})
    return plan, gold, result


class EvaluationTests(unittest.TestCase):
    def test_complete_multiquery_denominators(self):
        report = evaluate(*fixture())
        self.assertTrue(report['scientific_complete'])
        self.assertEqual(report['expected_views'], 104)
        self.assertEqual(report['coverage_inclusive_metrics']['vote']['pass2_count'], 13)
        self.assertEqual(report['coverage_inclusive_metrics']['vote']['all_queries_task_pass2_count'], 12)

    def test_empty_complete_claim_is_not_completion(self):
        plan, gold, result = fixture()
        result['queries'] = []
        report = evaluate(plan, gold, result)
        self.assertFalse(report['scientific_complete'])
        self.assertEqual(report['coverage_inclusive_metrics']['vote']['queries_without_candidates'], 13)

    def test_missing_query_not_removed_from_denominator(self):
        plan, gold, result = fixture()
        result['queries'].pop()
        report = evaluate(plan, gold, result)
        self.assertFalse(report['scientific_complete'])
        self.assertEqual(report['coverage_inclusive_metrics']['vote']['query_denominator'], 13)

    def test_query_macro_and_task_macro_are_distinct(self):
        plan, gold, result = fixture()
        gold['answers']['00000000'][0] = [[9]]
        metrics = evaluate(plan, gold, result)['coverage_inclusive_metrics']['vote']
        self.assertEqual(metrics['pass2_count'], 12)
        self.assertAlmostEqual(metrics['task_macro_pass2'], 11.5 / 12)
        self.assertEqual(metrics['all_queries_task_pass2_count'], 11)

    def test_pool_count_and_raw_inverse_are_checked(self):
        for alteration in ('count', 'grid', 'prompt'):
            plan, gold, result = fixture()
            row = result['queries'][0]
            if alteration == 'count':
                row['candidates'][0]['count'] = 7
            elif alteration == 'grid':
                row['views'][0]['canonical_grid'] = [[9]]
            else:
                row['views'][0]['prompt_sha256'] = 'wrong'
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                evaluate(plan, gold, result)

    def test_missing_nll_cannot_claim_complete(self):
        plan, gold, result = fixture()
        result['queries'][0]['candidates'][0]['view_nll'][0]['status'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'missing NLL'):
            evaluate(plan, gold, result)

    def test_deadline_after_eighth_nll_preserves_partial_vote(self):
        plan, gold, result = fixture()
        row = result['queries'][0]
        row['candidates'][0].update(mean_nll=None, combined_score=None)
        row.update(rescoring_complete=False, rescored=[])
        result['status'] = 'partial'
        report = evaluate(plan, gold, result)
        self.assertFalse(report['scientific_complete'])
        self.assertEqual(report['coverage_inclusive_metrics']['vote']['pass2_count'], 13)
        self.assertEqual(report['coverage_inclusive_metrics']['rescored']['queries_without_candidates'], 1)

    def test_nll_scope_eos_and_finiteness_checked(self):
        for key, value in [('includes_eos', False), ('normalization', 'mean'), ('nll', float('nan')),
                           ('answer_sha256', 'wrong'), ('prompt_sha256', 'wrong')]:
            plan, gold, result = fixture()
            result['queries'][0]['candidates'][0]['view_nll'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluate(plan, gold, result)

    def test_duplicate_query_and_condition_rejected(self):
        plan, gold, result = fixture()
        result['queries'].append(copy.deepcopy(result['queries'][0]))
        with self.assertRaises(ValueError):
            evaluate(plan, gold, result)
        plan, gold, result = fixture()
        result['queries'][0]['candidates'][0]['view_nll'][1]['view'] = 0
        with self.assertRaises(ValueError):
            evaluate(plan, gold, result)

    def test_seal_requires_exit_and_unchanged_predictions(self):
        plan, gold, result = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, value in [('plan', plan), ('gold', gold), ('result', result)]:
                (root / name).write_text(json.dumps(value))
            seal = {'worker_exited': True, 'result_sha256': hashlib.sha256((root / 'result').read_bytes()).hexdigest()}
            (root / 'seal').write_text(json.dumps(seal))
            self.assertTrue(score_sealed(root / 'plan', root / 'gold', root / 'result', root / 'seal')['scientific_complete'])
            (root / 'result').write_text('{}')
            with self.assertRaises(ValueError):
                score_sealed(root / 'plan', root / 'gold', root / 'result', root / 'seal')

    def test_worker_to_sealed_evaluator_complete_and_partial(self):
        from tools.public_sft141_diagnostic.model_worker import run
        plan, gold, _ = fixture()
        plan['schema'] = 'iris-public-sft141-plan-v1'
        for task, answers in gold['answers'].items():
            gold['answers'][task] = [[[1]] for _ in answers]

        class Backend:
            max_context = 8192
            metadata = {'backend': 'synthetic-test-only'}
            def generate(self, prompt, max_new_tokens, deadline):
                return {'token_ids': [1, 15], 'seconds': 0.001, 'termination': 'eos'}
            def score(self, prompt, answer, deadline):
                return {'nll': 1.0, 'seconds': 0.001}

        with tempfile.TemporaryDirectory() as tmp:
            result = run(plan, Backend(), Path(tmp) / 'worker', 60)
            report = evaluate(plan, gold, result)
            self.assertTrue(report['scientific_complete'])
            self.assertEqual(report['coverage_inclusive_metrics']['vote']['pass2_count'], 13)
        class FailScore(Backend):
            calls = 0
            def score(self, prompt, answer, deadline):
                self.calls += 1
                if self.calls == 4:
                    raise RuntimeError('deliberate first panel scoring failure')
                return super().score(prompt, answer, deadline)
        with tempfile.TemporaryDirectory() as tmp:
            result = run(plan, FailScore(), Path(tmp) / 'worker', 60)
            report = evaluate(plan, gold, result)
            self.assertFalse(report['scientific_complete'])
            self.assertEqual(report['coverage_inclusive_metrics']['vote']['pass2_count'], 13)
            self.assertEqual(report['coverage_inclusive_metrics']['rescored']['queries_without_candidates'], 13)

    def test_actual_owned_leaf_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, timed_out = leaf([sys.executable, '-c', 'import time; time.sleep(30)'], Path(tmp) / 'log', 0.2)
            self.assertTrue(timed_out)
            self.assertNotEqual(code, 0)

    def test_interrupt_reaps_owned_process(self):
        with tempfile.TemporaryDirectory() as tmp, patch('subprocess.Popen') as constructor:
            process = constructor.return_value
            process.wait.side_effect = [KeyboardInterrupt(), 1]
            process.poll.return_value = None
            with self.assertRaises(KeyboardInterrupt):
                leaf(['unused'], Path(tmp) / 'log', 1)
            process.kill.assert_called_once()
            self.assertEqual(process.wait.call_count, 2)


if __name__ == '__main__':
    unittest.main()

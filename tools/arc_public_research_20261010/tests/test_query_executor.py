"""Bounded synthetic query calls; no model execution or public predictions."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.arc_consolidated_20261010 import arc_object_ir as ir, verifier
from tools.arc_public_research_20261010 import query_executor as query

IDENTITY = {'steps': [{'op': 'identity'}]}
DOUBLE = {'steps': [{'op': 'identity'}, {'op': 'identity'}]}
CHALLENGES = {'tiny': {'train': [{'input': [[1]], 'output': [[1]]}],
                        'test': [{'input': [[2]]}, {'input': [[3]]}]}}


def candidate(plan=IDENTITY, cid='candidate-one', task_id='tiny'):
    task = {'task_id': task_id, 'demos': CHALLENGES['tiny']['train']}
    receipt = verifier.verify(ir.compile_plan(plan), task)
    return {'candidate_id': cid, 'run_id': 'synthetic-run', 'plan': copy.deepcopy(plan), 'verification': receipt}


class QueryExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_real_fresh_process_query_and_no_filler(self):
        row = candidate()
        self.assertTrue(row['verification']['all_demos_fit'])
        frozen = query.freeze_selections(CHALLENGES, {'tiny': [row]}, run_id='synthetic-run', policy='raw', output_root=self.root)
        receipt = query.query_execute(IDENTITY, [[[2]]], self.root / 'calls', 'query-one', selection_sha256=frozen['selection_sha256'])
        self.assertEqual(receipt['results'][0]['output'], [[2]])
        self.assertTrue(receipt['owned_descendants_stopped'])
        self.assertEqual(receipt['results'][0]['process_returncode'], 0)
        pool = query.build_policy_pool(CHALLENGES, frozen,
            {'tiny': [{'candidate_id': row['candidate_id'], 'test_index': 0, 'receipt': receipt}]},
            run_id='synthetic-run', policy='raw')
        self.assertEqual(pool['records'][0]['tests'][0]['ranked_grids'], [[[2]]])
        self.assertEqual(pool['records'][0]['tests'][1]['ranked_grids'], [])
        self.assertEqual(pool['records'][0]['tests'][1]['status'], 'not_executed')
        self.assertEqual(pool['records'][0]['tests'][0]['status'], 'partial')

    def test_top_two_distinct_plans_and_deduplicated_grids(self):
        first = candidate(); duplicate = copy.deepcopy(first); duplicate['candidate_id'] = 'duplicate'
        second = candidate(DOUBLE, 'second')
        frozen = query.freeze_selections(CHALLENGES, {'tiny': [first, duplicate, second]},
            run_id='synthetic-run', policy='uniform', output_root=self.root)
        self.assertEqual([r['candidate_id'] for r in frozen['selection']['selected']['tiny']], ['candidate-one', 'second'])
        rows = []
        for i, item in enumerate((first, second)):
            receipt = query.query_execute(item['plan'], [[[2]]], self.root / 'calls', 'query-' + str(i),
                                          selection_sha256=frozen['selection_sha256'])
            rows.append({'candidate_id': item['candidate_id'], 'test_index': 0, 'receipt': receipt})
        pool = query.build_policy_pool(CHALLENGES, frozen, {'tiny': rows}, run_id='synthetic-run', policy='uniform')
        self.assertEqual(pool['records'][0]['tests'][0]['ranked_grids'], [[[2]]])

    def test_forged_foreign_and_nonfresh_receipts_fail(self):
        original = candidate()
        alterations = [lambda r: r.update(run_id='foreign'),
            lambda r: r['verification'].update(source_sha256='0' * 64),
            lambda r: r['verification'].update(dispatched=False),
            lambda r: r['verification']['demos'][0].update(match=False),
            lambda r: r['verification'].update(known=False)]
        for i, change in enumerate(alterations):
            row = copy.deepcopy(original); change(row)
            with self.assertRaises(ValueError):
                query.freeze_selections(CHALLENGES, {'tiny': [row]}, run_id='synthetic-run', policy='raw',
                                        output_root=self.root / str(i))

    def test_original_demo_guard_unchanged_and_host_source_forbidden(self):
        with self.assertRaises(verifier.AdmissionError):
            verifier.validate_task({'task_id': 'tiny', 'demos': [], 'test': []})
        with self.assertRaises(ValueError):
            query.query_execute({'source': 'import os'}, [[[1]]], self.root, 'bad')
        with self.assertRaises(ValueError):
            query.query_execute(IDENTITY, [[[True]]], self.root, 'bad-bool')

    def test_missing_worker_output_stays_missing(self):
        with patch.object(query.subprocess, 'Popen', side_effect=OSError('synthetic launch failure')):
            receipt = query.query_execute(IDENTITY, [[[1]]], self.root, 'unavailable')
        self.assertEqual(receipt['results'][0]['status'], 'missing')
        self.assertIsNone(receipt['results'][0]['output'])
        self.assertEqual(receipt['gas_charged'], 0)
        with self.assertRaises(ValueError):
            query.query_execute(IDENTITY, [[[1]]], self.root, 'unavailable')


if __name__ == '__main__':
    unittest.main()

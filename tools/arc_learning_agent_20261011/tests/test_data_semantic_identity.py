"""Semantic sampling must never depend on measured proof runtime."""
import copy
from pathlib import Path
import tempfile
import time
import unittest

from tools.arc_learning_agent_20261011 import data
from tools.arc_learning_agent_20261011.training import DEFAULTS, Trainer
from tools.arc_learning_agent_20261011.tests.test_data import fixture_tasks
from tools.arc_next_models import digest


class SemanticIdentityTests(unittest.TestCase):
    def setUp(self):
        self.manifest = data.create_split_manifest(fixture_tasks())
        self.rows = data.build_records(fixture_tasks(), self.manifest, augmentations=1)

    def reseal(self, row):
        row['record_id'] = digest({k: v for k, v in row.items() if k != 'record_id'})
        return row

    def test_runtime_changes_full_evidence_but_not_semantic_id(self):
        original = copy.deepcopy(self.rows[0])
        original['provenance']['verification'] = {'receipt_sha256': 'a' * 64, 'verification_seconds': 1.0}
        original['provenance']['verification_proof'] = {'proof_path': '/original/proof', 'proof_sha256': 'b' * 64,
                                                     'candidate_path': '/original/candidate', 'elapsed_seconds': 2.0}
        self.reseal(original)
        changed = copy.deepcopy(original)
        changed['provenance']['verification'].update(receipt_sha256='c' * 64, verification_seconds=999.0)
        changed['provenance']['verification_proof'].update(proof_path='/new/proof', proof_sha256='d' * 64,
                                                          candidate_path='/new/candidate', elapsed_seconds=0.5)
        self.reseal(changed)
        self.assertNotEqual(original['record_id'], changed['record_id'])
        self.assertEqual(data.semantic_sample_id(original), data.semantic_sample_id(changed))
        # The original whole-record digest gate remains mandatory.
        changed['provenance']['verification']['verification_seconds'] += 1
        with self.assertRaisesRegex(ValueError, 'record digest changed'):
            data.validate_records([changed], self.manifest, ())

    def test_actual_persisted_proofs_keep_semantics_and_strict_admission(self):
        from tools.arc_learning_agent_20261011.program_tools import verify_program
        tasks = fixture_tasks()
        manifest = data.create_split_manifest(tasks, fixed_splits={'train': ['a', 'b', 'c'], 'dev': ['d']})
        source = 'def transform(grid):\n return [row[::-1] for row in grid]\n'
        with tempfile.TemporaryDirectory() as tmp:
            rows = []
            for name in ('first-runtime', 'second-runtime'):
                proof = verify_program(source, tasks['a']['train'], Path(tmp), name, deadline=time.monotonic() + 30)
                rows.append(data.verified_program_record('a', tasks['a'], source, proof, manifest))
            self.assertNotEqual(rows[0]['record_id'], rows[1]['record_id'])
            self.assertNotEqual(rows[0]['provenance']['verification_proof']['proof_sha256'],
                                rows[1]['provenance']['verification_proof']['proof_sha256'])
            self.assertEqual(data.semantic_sample_id(rows[0]), data.semantic_sample_id(rows[1]))
            data.validate_records(rows, manifest, ())
            changed = copy.deepcopy(rows[0])
            changed['provenance']['verification_proof']['elapsed_seconds'] += 1
            self.reseal(changed)
            self.assertEqual(data.semantic_sample_id(changed), data.semantic_sample_id(rows[0]))
            with self.assertRaisesRegex(ValueError, 'proof binding differs'):
                data.validate_records([changed], manifest, ())

    def test_actual_target_source_and_prompt_changes_semantic_id(self):
        row = self.rows[0]
        for field, value in (('completion', '999'), ('messages', [{'role': 'user', 'content': 'changed source'}]),
                             ('parent_ids', ['changed-source'])):
            changed = {**copy.deepcopy(row), field: value}
            self.assertNotEqual(data.semantic_sample_id(row), data.semantic_sample_id(changed), field)
        changed = copy.deepcopy(row)
        changed['provenance']['source_task_sha256'] = 'e' * 64
        self.assertNotEqual(data.semantic_sample_id(row), data.semantic_sample_id(changed))
        bad = self.reseal({**copy.deepcopy(row), 'completion': '999'})
        with self.assertRaises(ValueError):
            data.validate_records([bad], self.manifest, ())

    def order(self, rows, cycle):
        trainer = Trainer.__new__(Trainer)
        trainer.config = {**DEFAULTS, 'stability_mode': True}
        trainer._task_id = None
        trainer._effective_cycle = cycle
        trainer._schedule_records = [{**{k: row[k] for k in ('kind', 'family_id', 'record_id')},
                                      'semantic_id': data.semantic_sample_id(row)} for row in rows]
        return [data.semantic_sample_id(rows[index]) for index in trainer._order(len(rows), 3)]

    def test_both_sampling_modes_ignore_runtime_identity_and_source_order(self):
        changed = copy.deepcopy(list(reversed(self.rows)))
        for i, row in enumerate(changed):
            row['provenance']['verification'] = {'receipt_sha256': digest(['runtime', i]), 'verification_seconds': i / 10}
            self.reseal(row)
        for cycle in (None, ['grid', 'grid']):
            self.assertEqual(self.order(self.rows, cycle), self.order(changed, cycle))

    def test_duplicate_semantics_use_occurrence_order_never_receipt_hash(self):
        a, b = copy.deepcopy(self.rows[0]), copy.deepcopy(self.rows[0])
        a['record_id'], b['record_id'] = 'z' * 64, 'a' * 64
        trainer = Trainer.__new__(Trainer)
        trainer.config = {**DEFAULTS, 'stability_mode': True}
        trainer._task_id = None
        trainer._effective_cycle = ['grid']
        trainer._schedule_records = [{**{k: r[k] for k in ('kind', 'family_id', 'record_id')},
                                      'semantic_id': data.semantic_sample_id(r)} for r in (a, b)]
        first = trainer._order(2, 0)
        trainer._schedule_records[0]['record_id'], trainer._schedule_records[1]['record_id'] = 'a' * 64, 'z' * 64
        self.assertEqual(first, trainer._order(2, 0))


if __name__ == '__main__':
    unittest.main()

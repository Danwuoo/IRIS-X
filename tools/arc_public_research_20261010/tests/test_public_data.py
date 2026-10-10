"""Synthetic 120-task/167-query fixtures only. No real benchmark answers."""
import copy
from pathlib import Path
import tempfile
import unittest

from irisx.artifacts import make_artifact
from tools.arc_offline_evaluation import load_pinned_reference
from tools.arc_public_research_20261010 import public_data as data
from tools.arc_public_research_20261010.prepare_public_assets import _write_assets


def make_assets(root):
    root = Path(root)
    source = root / 'synthetic-source'; source.mkdir()
    (source / 'LICENSE').write_bytes(b'Synthetic fixture license, no public source content.\n')
    files = []
    for i in range(120):
        name = 'data/evaluation/%08x.json' % i
        tests = [{'input': [[2]], 'output': [[2]]}]
        if i < 47:
            tests.append({'input': [[2]], 'output': [[3]]})
        task = {'train': [{'input': [[1]], 'output': [[1]]}], 'test': tests}
        body = data.canonical(task) + b'\n'
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        files.append({'path': name, 'byte_size': len(body), 'content_digest': 'sha256:' + data.sha256(body)})
    provenance = make_artifact('irisx/arc-source-provenance', 'synthetic-public-shape', '1.0.0', {
        'repository': data.REPOSITORY, 'commit': data.COMMIT, 'files': files,
        'evaluation_task_count': 120, 'training_task_count': 0, 'preserved_bytes': True})
    path = root / 'synthetic-provenance.json'; path.write_bytes(data.canonical(provenance))
    challenges, answers, reference = load_pinned_reference(source, path)
    del answers
    result = _write_assets(source, path, root / 'assets', challenges, reference, evidence_mode='synthetic-test-only')
    return result


class PublicDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.assets = make_assets(self.root)
        self.solver = Path(self.assets['solver_root'])

    def load(self):
        return data.load_solver_tasks(self.solver, self.assets['solver_manifest_sha256'])

    def test_complete_denominator_and_only_inputs_on_query_path(self):
        loaded = self.load()
        self.assertEqual(loaded['identity']['tasks'], 120)
        self.assertEqual(loaded['identity']['tests'], 167)
        self.assertEqual(len(loaded['demos_tasks']), 120)
        self.assertFalse(loaded['manifest']['complete_official_pinned_set'])
        for key, task in loaded['challenges'].items():
            self.assertEqual(set(task), {'train', 'test'})
            self.assertTrue(all(set(pair) == {'input'} for pair in task['test']))
            self.assertEqual(set(loaded['demos_tasks'][key]), {'task_id', 'demos'})
        loaded['demos_tasks']['00000000']['demos'][0]['input'][0][0] = 9
        self.assertEqual(loaded['challenges']['00000000']['train'][0]['input'], [[1]])

    def test_wrong_manifest_mutation_and_extra_file_fail(self):
        with self.assertRaises(ValueError):
            data.load_solver_tasks(self.solver, '0' * 64)
        (self.solver / 'unexpected.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.load()
        (self.solver / 'unexpected.json').unlink()
        (self.solver / 'public-challenges.json').write_text('{}')
        with self.assertRaises(ValueError):
            self.load()

    def test_link_and_partial_artifact_fail(self):
        (self.solver / 'extra-link').symlink_to(self.root / 'synthetic-provenance.json')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.load()
        (self.solver / 'extra-link').unlink()
        (self.solver / 'pending.partial').write_text('')
        with self.assertRaisesRegex(ValueError, 'interrupted'):
            self.load()

    def test_duplicate_keys_and_bad_grids_fail(self):
        with self.assertRaises(ValueError):
            data.parse_json(b'{"x":1,"x":2}')
        from tools.arc_kaggle_submission import challenge_counts
        good = self.load()['challenges']
        for grid in ([[True]], [[1], [1, 2]], [[1] * 31], [], [[10]]):
            value = copy.deepcopy(good)
            value['00000000']['test'][0]['input'] = grid
            with self.assertRaises(ValueError):
                challenge_counts(value)
        value = copy.deepcopy(good); value['00000000']['test'][0]['output'] = [[2]]
        with self.assertRaises(ValueError):
            challenge_counts(value)

    def test_source_pin_and_authoritative_inventory_cannot_be_fabricated(self):
        manifest = self.load()['manifest']
        manifest['evidence_mode'] = 'public-development'
        manifest['complete_official_pinned_set'] = True
        with self.assertRaisesRegex(ValueError, 'source pin'):
            data.validate_manifest(manifest, role='solver')
        with self.assertRaises(ValueError):
            data.verify_upstream_inventory({'format': 'irisx/pinned-public-evaluation-git-inventory-v1',
                'commit': data.COMMIT, 'objects': {'commit': '', 'root': '', 'data': '', 'evaluation': ''}, 'files': {}})

    def test_dev8_172_and_false_completeness_rejected(self):
        manifest = self.load()['manifest']
        for tasks, tests in ((8, 8), (120, 172)):
            value = copy.deepcopy(manifest); value['identity'].update(tasks=tasks, tests=tests)
            with self.assertRaises(ValueError):
                data.validate_manifest(value, role='solver')
        manifest['complete_official_pinned_set'] = True
        with self.assertRaises(ValueError):
            data.validate_manifest(manifest, role='solver')


if __name__ == '__main__':
    unittest.main()

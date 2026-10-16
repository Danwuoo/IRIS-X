"""CPU-only audit projection checks; no archive, model, or evaluator access."""
import ast
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import types
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
TOOL = PACKAGE.parent
REPOSITORY = TOOL.parents[1]
FIXTURE_PACKAGE = '_numeric_panel_counts_fixture'


class DiagnosticPanelCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load only unchanged public audit/contracts in an isolated namespace.
        # Other runtime tests reconstruct their own source-frozen packages.
        mapping = json.loads((TOOL / 'runtime-path-map.json').read_bytes())['files']
        for name in ('experiment_flow/audit.py', 'experiment_flow/contracts.py'):
            row = mapping[name]
            raw = (REPOSITORY / row['repository_path']).read_bytes()
            if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise RuntimeError('unchanged public audit dependency differs: ' + name)
        package = types.ModuleType(FIXTURE_PACKAGE)
        package.__path__ = [str(TOOL / 'source/experiment_flow')]
        sys.modules[FIXTURE_PACKAGE] = package
        cls.audit = importlib.import_module(FIXTURE_PACKAGE + '.audit')
        tree = ast.parse((PACKAGE / 'runtime/experiment_flow/flow.py').read_bytes())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'run_training_numeric_diagnostic')
        finalizer = next(node for node in function.body if isinstance(node, ast.Try)).finalbody
        projection = next(node for node in finalizer if isinstance(node, ast.If)
                          and any(isinstance(child, ast.ImportFrom) and child.module == 'audit'
                                  for child in node.body))
        cls.projection = compile(ast.Module(body=[projection], type_ignores=[]),
                                 '<actual-diagnostic-audit-projection>', 'exec')
        cls.parents = tuple('synthetic-parent-' + str(index) for index in range(32))

    @classmethod
    def tearDownClass(cls):
        for name in tuple(sys.modules):
            if name == FIXTURE_PACKAGE or name.startswith(FIXTURE_PACKAGE + '.'):
                del sys.modules[name]

    def entries(self, reached=None):
        entries = []
        for index in range(4):
            parents = self.parents[index * 8:(index + 1) * 8]
            batch = self.audit.empty_batch(parents, 8, index,
                'diagnostic-first-batch-not-entered' if index == 0 else 'not-requested-by-diagnostic')
            status = 'not-reached' if index == 0 else 'not-requested-by-diagnostic'
            if index == 0 and reached is not None:
                status = 'intentionally-no-update' if reached == 64 else 'incomplete-audit'
                for row in batch['rows'][:reached]:
                    row.update(eligible=True, reward=0, status='eligible',
                               trajectory={'dispatched': True, 'steps': [{'token': 0}]})
                batch['all_slots_reached'] = reached == 64
            entries.append({'batch_index': index, 'parent_ids': list(parents), 'batch': batch,
                            'status': status, 'update': None})
        return entries

    def project(self, entries):
        original = deepcopy(entries)
        writes = []
        namespace = {'__package__': FIXTURE_PACKAGE,
            'plan': types.SimpleNamespace(shape=types.SimpleNamespace(batch_parents=8, group_size=8)),
            'result': {}, 'sweeps': entries,
            'reward_panel': types.SimpleNamespace(parent_ids=self.parents),
            'root': Path('unused-synthetic-audit-output'),
            'write_json': lambda path, value: writes.append((path, deepcopy(value)))}
        exec(self.projection, namespace)
        result = namespace['result']['full_panel_audit']
        self.assertEqual(entries, original)
        self.assertEqual(writes, [(namespace['root'] / 'full-panel-audit.json', result)])
        inherited = self.audit.full_panel_summary(entries, self.parents, 8)
        self.assertEqual({key: value for key, value in result.items() if key != 'physical_attempted_batches'},
                         {key: value for key, value in inherited.items() if key != 'physical_attempted_batches'})
        self.assertEqual(result['planned_attempts'], 256)
        self.assertEqual(result['planned_batches'], 4)
        self.assertEqual(result['summary']['planned_attempts'], 256)
        self.assertEqual(result['batch_statuses'][1:], ['not-requested-by-diagnostic'] * 3)
        self.assertFalse(result['summary']['complete'])
        self.assertFalse(result['all32_coverage_complete'])
        self.assertFalse(result['all_zero_panel'])
        self.assertEqual(result['optimizer_updates'], 0)
        self.assertEqual(result['physical_optimizer_commit_attempts'], 0)
        return result

    def test_no_entered_batch_has_zero_physical_attempts(self):
        result = self.project(self.entries())
        self.assertEqual(result['physical_attempted_batches'], 0)
        self.assertEqual(result['summary']['not_reached'], 256)
        self.assertEqual(result['summary']['actual_dispatched_attempts'], 0)
        self.assertIsNone(result['summary']['eligible_mean_reward'])

    def test_complete_first_batch_counts_once_with_full_denominator(self):
        result = self.project(self.entries(64))
        self.assertEqual(result['physical_attempted_batches'], 1)
        self.assertEqual(result['summary']['not_reached'], 192)
        self.assertEqual(result['summary']['actual_dispatched_attempts'], 64)

    def test_partial_first_batch_counts_once_even_without_dispatched_slots(self):
        for reached in (0, 5, 63):
            with self.subTest(reached=reached):
                result = self.project(self.entries(reached))
                self.assertEqual(result['physical_attempted_batches'], 1)
                self.assertEqual(result['summary']['not_reached'], 256 - reached)
                self.assertEqual(result['summary']['actual_dispatched_attempts'], reached)

    def test_original_abc_and_shared_audit_are_unchanged(self):
        original = (TOOL / 'source/experiment_flow/flow.py').read_bytes()
        self.assertTrue((PACKAGE / 'runtime/experiment_flow/flow.py').read_bytes().startswith(original))
        self.assertFalse((PACKAGE / 'runtime/experiment_flow/audit.py').exists())
        entries = self.entries(64)
        for entry in entries[1:]:
            entry['status'] = 'not-reached'
        legacy = self.audit.full_panel_summary(entries, self.parents, 8)
        self.assertEqual(legacy['physical_attempted_batches'], 1)
        self.assertEqual(legacy['summary']['not_reached'], 192)
        self.assertEqual(legacy['planned_attempts'], 256)
        for entry in entries:
            entry['status'] = 'zero-signal'
            for row in entry['batch']['rows']:
                row.update(eligible=True, reward=0, status='eligible',
                           trajectory={'dispatched': True, 'steps': [{'token': 0}]})
        legacy = self.audit.full_panel_summary(entries, self.parents, 8)
        self.assertEqual(legacy['physical_attempted_batches'], 4)
        self.assertTrue(legacy['all32_coverage_complete'])
        self.assertTrue(legacy['all_zero_panel'])


if __name__ == '__main__':
    unittest.main()

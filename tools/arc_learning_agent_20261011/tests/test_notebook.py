import builtins
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.arc_learning_agent_20261011.build_notebook import build, build_stable


def fake_pins():
    return {'code': {'reference': 'owner/code/1', 'manifest_sha256': 'a'*64, 'archive_sha256':'b'*64},
            'data': {'reference': 'owner/data/1', 'manifest_sha256':'c'*64,
                     'role_manifests': {'solver':'d'*64, 'evaluator':'e'*64}},
            'training': {'reference': 'owner/training/1', 'manifest_sha256':'f'*64}}


class NotebookTests(unittest.TestCase):
    def test_default_notebook_inert_no_reads_writes_or_project_import(self):
        notebook = build(fake_pins())
        scope = {}
        with patch.object(builtins, 'open', side_effect=AssertionError('unexpected file read/write')), \
             patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected input read')), \
             patch.object(Path, 'write_bytes', side_effect=AssertionError('unexpected output write')):
            for cell in notebook['cells']:
                if cell['cell_type'] == 'code': exec(compile(''.join(cell['source']), '<inert-notebook>', 'exec'), scope)
        self.assertFalse(scope['MANUAL_START']); self.assertFalse(scope['ENABLE_MODEL'])
        self.assertIsNone(scope['_LEARNING_READY'])
        self.assertEqual(scope['SESSION_SECONDS'], 43200)
        self.assertNotIn('_learning_run', scope)

    def test_only_three_exact_new_asset_roles(self):
        with self.assertRaises(ValueError): build({'code': fake_pins()['code']})

    def test_stable_candidate_inert_and_embeds_actual_deadline_supervisor(self):
        notebook = build_stable(fake_pins()); scope = {}
        with patch.object(builtins, 'open', side_effect=AssertionError('unexpected file access')), \
             patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected input read')), \
             patch.object(Path, 'write_bytes', side_effect=AssertionError('unexpected output write')):
            for cell in notebook['cells']:
                if cell['cell_type'] == 'code': exec(compile(''.join(cell['source']), '<stable-inert>', 'exec'), scope)
        self.assertFalse(scope['MANUAL_START']); self.assertFalse(scope['ENABLE_MODEL'])
        self.assertEqual(scope['PROFILE'], 'LEARNING_AGENT_STABLE12H')
        self.assertEqual(scope['SESSION_SECONDS'], 43200)
        self.assertIsNone(scope['PREDISPATCH_EPOCH'])
        self.assertIn('OwnedProcessGuard.spawn', ''.join(notebook['cells'][2]['source']))
        self.assertIn('EFFECTIVENESS_BLOCKED', ''.join(notebook['cells'][2]['source']))


if __name__ == '__main__': unittest.main()

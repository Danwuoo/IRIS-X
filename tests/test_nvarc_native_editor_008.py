"""Approved 008 Editor guard, archive routing and QUICK_SAVE boundary; offline."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from irisx.canonical import canonical_bytes, digest_value
from tools import stage_nvarc_native_editor_008 as stage
from tools import save_nvarc_native_editor_008 as transport
from tools import verify_nvarc_native_long_ttt as reader


class NativeEditor008Tests(unittest.TestCase):
    def test_approved_parent_passes_approval_guard_and_reader_routes_exact_008_archive(self):
        plan = {'run_id': stage.RUN, 'approved': True, 'owner_decision': stage.AUTHORITY,
            'owner_editor_only': True, 'maximum_notebook_wall_seconds': 3600,
            'maximum_child_wall_seconds': 3000, 'source_learning_rates': [0.] * 129}
        raw = {'plan': canonical_bytes(plan), 'source_inventory': b'{}', 'model_inventory': b'{}',
            'editor_archive': stage.proposal.predecessor.ARCHIVE.read_bytes(), 'expected_rows': b'[]'}
        source = ''.join(stage.proposal.notebook(plan, raw)['cells'][0]['source'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = source.replace("Path('/kaggle/working')", 'Path(' + repr(str(root)) + ')')
            with patch('sys.stdout', new_callable=io.StringIO), patch('sys.version_info', (3, 12, 0)), \
                    self.assertRaisesRegex(RuntimeError, 'original Python version required'):
                exec(compile(source, 'approved-008-parent', 'exec'), {})
            package = root / 'package'; package.mkdir()
            (package / 'plan.json').write_bytes(raw['plan'])
            with patch.object(stage, 'preflight', return_value={'plan_digest': digest_value(plan)}), \
                    patch.object(stage, 'raw_payloads', return_value=raw):
                proof = reader.verify(root / '結果.zip', package)
            self.assertEqual(proof['run_id'], stage.RUN)
            self.assertEqual(proof['model_forwards_reserved'], 0)
            self.assertFalse(proof['full_native_long_ttt_completed'])
            self.assertEqual(proof['error_message'], 'original Python version required')

    def test_save_fields_reject_inert_plan_changed_limits_and_run_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp); (package / 'kernel').mkdir()
            plan = {'run_id': stage.RUN, 'approved': True, 'owner_decision': stage.AUTHORITY,
                'owner_editor_only': True, 'maximum_notebook_wall_seconds': 3600,
                'maximum_child_wall_seconds': 3000, 'kernel_execution_type': 'QUICK_SAVE'}
            meta = {'id': 'danielwuu/' + stage.RUN, 'title': stage.RUN, 'is_private': True,
                'enable_gpu': True, 'enable_internet': False, 'dataset_sources': [],
                'competition_sources': ['arc-prize-2026-arc-agi-2'], 'kernel_sources': ['pinned'],
                'model_sources': ['pinned'], 'docker_image': 'pinned'}
            notebook = {'cells': [{'cell_type': 'code', 'execution_count': None, 'outputs': [], 'source': ['pass\n']}]}
            (package / 'kernel/kernel-metadata.json').write_bytes(canonical_bytes(meta))
            (package / 'kernel/notebook.ipynb').write_bytes(canonical_bytes(notebook))
            (package / 'plan.json').write_bytes(canonical_bytes(plan))
            fields = transport.request_fields(package)
            self.assertEqual(fields['kernel_execution_type'], 'QUICK_SAVE')
            self.assertEqual(fields['session_timeout_seconds'], 3600)
            for mutation in ({'approved': False}, {'owner_decision': 'Decision 0055'},
                    {'maximum_notebook_wall_seconds': 1500}, {'maximum_child_wall_seconds': 1200},
                    {'kernel_execution_type': 'SAVE_AND_RUN_ALL'}):
                (package / 'plan.json').write_bytes(canonical_bytes({**plan, **mutation}))
                with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                    transport.request_fields(package)


if __name__ == '__main__':
    unittest.main()

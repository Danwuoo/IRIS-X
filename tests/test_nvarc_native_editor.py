"""Offline Editor failure/download and save-mode boundary tests; no model work."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from irisx.canonical import canonical_bytes, digest_value
from tools import nvarc_native_editor_archive as archive_tools
from tools import save_nvarc_native_editor as transport
from tools import stage_nvarc_native_editor as stage
from tools import verify_nvarc_native_long_ttt as reader


class NativeEditorTests(unittest.TestCase):
    def test_parent_failure_still_packages_exact_inputs_and_download_cell_only_relinks(self):
        # Artificial inputs fail the Python gate before dependency/model access.
        plan = {'run_id': stage.RUN, 'owner_editor_only': True,
            'maximum_notebook_wall_seconds': 1500, 'source_learning_rates': [0.] * 129}
        raw = {'plan': canonical_bytes(plan), 'source_inventory': b'{}', 'model_inventory': b'{}',
            'editor_archive': stage.ARCHIVE.read_bytes(), 'expected_rows': b'[]'}
        source = stage.render(plan, raw)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = source.replace("Path('/kaggle/working')", 'Path(' + repr(str(root)) + ')')
            namespace = {}
            with patch('sys.stdout', new_callable=io.StringIO), patch('sys.version_info', (3, 12, 0)), \
                    self.assertRaisesRegex(RuntimeError, 'original Python version'):
                exec(compile(source, 'emitted-editor-parent', 'exec'), namespace)
            destination = root / '結果.zip'
            self.assertTrue(destination.is_file())
            with zipfile.ZipFile(destination) as stream:
                manifest = json.loads(stream.read('manifest.json'))
                self.assertEqual(manifest['plan_digest'], digest_value(plan))
                self.assertEqual(set(stream.namelist()),
                    {'manifest.json', 'plan.json', 'payload-bindings.json', 'terminal.json', 'editor-archive.py'})
                terminal = json.loads(stream.read('terminal.json'))
                self.assertEqual(terminal['outcome'], 'failed')
                self.assertEqual(terminal['model_forwards_reserved'], 0)
                self.assertEqual(terminal['optimizer_steps_reserved'], 0)
                for row in manifest['members']:
                    body = stream.read(row['path'])
                    self.assertEqual(len(body), row['bytes'])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), row['sha256'])
            package = root / 'package'; package.mkdir()
            (package / 'plan.json').write_bytes(raw['plan'])
            with patch.object(stage, 'preflight', return_value={'plan_digest': digest_value(plan)}), \
                    patch.object(stage, 'raw_payloads', return_value=raw):
                proof = reader.verify(destination, package)
            self.assertEqual(proof['model_forwards'], 0)
            self.assertFalse(proof['full_native_long_ttt_completed'])
            before = destination.read_bytes()
            download = stage.download_cell(plan).replace(
                "Path('/kaggle/working/結果.zip')", 'Path(' + repr(str(destination)) + ')')
            for _ in range(2):
                with patch('sys.stdout', new_callable=io.StringIO):
                    exec(compile(download, 'emitted-editor-download', 'exec'), {})
            self.assertEqual(before, destination.read_bytes())
            self.assertNotIn('subprocess', download)

    def test_archive_bounds_identity_and_existing_output_are_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); work = root / 'run'; work.mkdir(); destination = root / '結果.zip'
            (work / 'log.txt').write_text('bounded diagnostic', encoding='utf-8')
            plan = {'run_id': 'fixture'}
            archive_tools.write_editor_archive(work, destination, 'fixture', plan)
            with self.assertRaisesRegex(RuntimeError, 'identity differs'):
                archive_tools.show_editor_archive(destination, 'different', digest_value(plan))
            with self.assertRaisesRegex(RuntimeError, 'already exists'):
                archive_tools.write_editor_archive(work, destination, 'fixture', plan)
            (work / 'oversized.log').write_bytes(b'x' * (16 * 1024**2 + 1))
            with self.assertRaisesRegex(RuntimeError, 'bounded native diagnostic member'):
                archive_tools.write_editor_archive(work, root / 'other.zip', 'fixture', plan)
            self.assertFalse((root / 'other.zip').exists())

    def test_save_fields_require_owner_editor_quick_save_and_empty_notebook(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp); (package / 'kernel').mkdir()
            plan = {'run_id': stage.RUN, 'owner_decision': 'Decision 0055',
                'owner_editor_only': True, 'kernel_execution_type': 'QUICK_SAVE'}
            meta = {'id': 'danielwuu/' + stage.RUN, 'title': stage.RUN, 'is_private': True,
                'enable_internet': False, 'enable_gpu': True, 'dataset_sources': [],
                'competition_sources': ['arc-prize-2026-arc-agi-2'], 'kernel_sources': ['original'],
                'model_sources': ['pinned'], 'docker_image': 'pinned'}
            notebook = {'cells': [{'cell_type': 'code', 'execution_count': None, 'outputs': [], 'source': ['pass\n']}]}
            (package / 'kernel/kernel-metadata.json').write_bytes(canonical_bytes(meta))
            (package / 'kernel/notebook.ipynb').write_bytes(canonical_bytes(notebook))
            for execution in ('QUICK_SAVE', 'SAVE_AND_RUN_ALL'):
                plan['kernel_execution_type'] = execution
                (package / 'plan.json').write_bytes(canonical_bytes(plan))
                if execution == 'QUICK_SAVE':
                    fields = transport.request_fields(package)
                    self.assertEqual(fields['kernel_execution_type'], 'QUICK_SAVE')
                    self.assertEqual(fields['session_timeout_seconds'], 1500)
                    self.assertFalse(fields['enable_internet'])
                else:
                    with self.assertRaises(AssertionError): transport.request_fields(package)
            plan['kernel_execution_type'] = 'QUICK_SAVE'
            (package / 'plan.json').write_bytes(canonical_bytes(plan))
            notebook['cells'][0]['execution_count'] = 1
            (package / 'kernel/notebook.ipynb').write_bytes(canonical_bytes(notebook))
            with self.assertRaises(AssertionError): transport.request_fields(package)


if __name__ == '__main__':
    unittest.main()

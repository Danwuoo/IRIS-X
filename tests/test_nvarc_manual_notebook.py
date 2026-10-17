import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools.nvarc_posttrain_20261017 import manual, package
from tools.arc2_goal_sprint_20261017.package import notebook


class ManualNotebookTests(unittest.TestCase):
    def request(self):
        return {'run_id': 'frozen-source-001', 'started_epoch': 100., 'session_deadline_epoch': 43300.,
            'working_root': '/kaggle/working/frozen-source-001', 'runtime_root': '/kaggle/temp/frozen-source-001',
            'source_dataset': 'danielwuu/source/1', 'source_manifest_sha256': 'a'*64,
            'source_payload_sha256': 'b'*64, 'parameters': {'x': [1]}}

    def claim(self, original, root):
        with patch.object(manual, 'kernel_birth_epoch', return_value=(200., 250.)), redirect_stdout(io.StringIO()):
            return manual.claim_manual_request(original, 'manual-session-001', working_parent=str(root), runtime_parent=str(root/'runtime'))

    @unittest.skipUnless(hasattr(__import__('os'), 'O_NOFOLLOW'), 'POSIX exclusive no-follow file creation required')
    def test_claim_preserves_old_clock_and_never_resets(self):
        original = self.request(); before = copy.deepcopy(original)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); result = self.claim(original, root)
            receipt_path = root/'manual-session-001-start.json'; raw = receipt_path.read_bytes()
            self.assertEqual(original, before)
            self.assertEqual(result['predecessor_clock'], {'started_epoch':100., 'session_deadline_epoch':43300.})
            self.assertEqual(result['started_epoch'], 200.)
            self.assertEqual(result['session_deadline_epoch'], 43400.)
            self.assertEqual(result['run_id'], original['run_id'])
            self.assertEqual(json.loads(raw)['first_execution_epoch'],250.)
            with self.assertRaises(FileExistsError): self.claim(original,root)
            self.assertEqual(receipt_path.read_bytes(),raw)

    def test_existing_runtime_or_output_is_never_overwritten(self):
        for suffix in ('', '-source'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); (root/('manual-session-001'+suffix)).mkdir()
                with self.assertRaises(FileExistsError): self.claim(self.request(),root)
                self.assertFalse((root/'manual-session-001-start.json').exists())

    def test_invalid_historical_clock_or_identity_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for value in (None,float('nan'),True):
                request=self.request();request['started_epoch']=value
                with self.assertRaises(ValueError): self.claim(request,root)
            with self.assertRaises(ValueError):
                manual.claim_manual_request(self.request(),'frozen-source-001',working_parent=str(root))

    def test_build_does_not_claim_clock_or_change_capsule(self):
        request=self.request(); original=notebook([package.loader(request)],request['run_id']);before=copy.deepcopy(original)
        with patch.object(manual.time,'time',side_effect=AssertionError('save must not start clock')):
            result=manual.build_manual_notebook(original,'manual-session-001')
        self.assertEqual(original,before)
        self.assertEqual(len(result['cells']),2)
        self.assertIn('claim_manual_request',result['cells'][1]['source'])
        self.assertIn(repr(request),result['cells'][1]['source'])
        self.assertEqual(result['cells'][1]['execution_count'],None)
        self.assertEqual(result['cells'][1]['outputs'],[])
        compile(result['cells'][1]['source'],'<manual>','exec')

    def test_changed_loader_or_executed_source_is_not_overwritten(self):
        request=self.request();original=notebook([package.loader(request)],request['run_id'])
        for modify in (lambda n:n['cells'][0].update(execution_count=1),lambda n:n['cells'][0].update(source=n['cells'][0]['source']+'\nprint(1)')):
            value=copy.deepcopy(original);modify(value)
            with self.assertRaises(ValueError): manual.build_manual_notebook(value,'manual-session-001')

    @unittest.skipUnless(hasattr(manual.os, 'sysconf') and hasattr(manual.time, 'clock_gettime')
                         and hasattr(manual.time, 'CLOCK_BOOTTIME'), 'Linux process-birth clock required')
    def test_kernel_birth_includes_idle_and_rejects_expired(self):
        # /proc stat fields after the command begin at field3; starttime is22.
        stat='123 (python worker) '+' '.join(['S']+['0']*18+['1000']+['0']*5)
        with patch.object(Path,'read_text',return_value=stat), patch.object(manual.os,'sysconf',return_value=100), \
             patch.object(manual.time,'clock_gettime',return_value=70.),patch.object(manual.time,'time',return_value=1000.):
            self.assertEqual(manual.kernel_birth_epoch(),(940.,1000.))
        with patch.object(Path,'read_text',return_value=stat), patch.object(manual.os,'sysconf',return_value=100), \
             patch.object(manual.time,'clock_gettime',return_value=50000.):
            with self.assertRaises(ValueError): manual.kernel_birth_epoch()

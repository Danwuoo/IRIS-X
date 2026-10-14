"""Offline control-flow tests; no provider, credentials, model or answer input."""
import hashlib, importlib.util, os
from pathlib import Path
import sys, tempfile, unittest
from unittest.mock import patch

HERE=Path(__file__).absolute().parent
SPEC=importlib.util.spec_from_file_location('run008_engineering_transfer',HERE/'rebuild_engineering.py')
b=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(b)

class RebuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='run008-transfer-test-');self.root=Path(self.tmp.name)
        self.repo=self.root/'repo';self.repo.mkdir();(self.repo/'.git').mkdir()
        self.inputs=self.root/'inputs';(self.inputs/'run007').mkdir(parents=True)
        self.argv=['rebuild_engineering.py','--repository-root',str(self.repo),'--authentic-inputs-root',str(self.inputs)]
    def tearDown(self):self.tmp.cleanup()
    def invoke(self):
        with patch.object(sys,'argv',self.argv):b.main()
    def test_regular_digest(self):
        p=self.root/'source';p.write_bytes(b'ordinary source\n');self.assertEqual(b.digest(p),hashlib.sha256(p.read_bytes()).hexdigest())
    def test_relative_and_dotdot_paths_rejected(self):
        for p in ('relative',str(self.root/'a/../b')):
            with self.assertRaisesRegex(ValueError,'absolute normal'):b.regular(p)
    def test_symlink_root_rejected(self):
        p=self.root/'linked';p.symlink_to(self.repo,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'linked'):b.regular(p/'anything')
    def test_hardlink_input_rejected(self):
        p=self.root/'one';p.write_bytes(b'source');os.link(p,self.root/'two')
        with self.assertRaisesRegex(ValueError,'single-link'):b.digest(p)
    def test_missing_authentic_input_fails_before_git_or_scripts(self):
        (self.inputs/'run007').rmdir()
        with patch.object(b.subprocess,'check_output') as git,patch.object(b.subprocess,'run') as execute:
            with self.assertRaisesRegex(ValueError,'Git checkout and authentic'):self.invoke()
            git.assert_not_called();execute.assert_not_called()
    def test_wrong_historical_tree_fails_before_scripts(self):
        with patch.object(b.subprocess,'check_output',return_value=b'0'*40+b'\n'),patch.object(b.subprocess,'run') as execute:
            with self.assertRaisesRegex(ValueError,'snapshot tree'):self.invoke()
            execute.assert_not_called()
    def test_existing_outputs_or_report_never_overwritten(self):
        for relative in ('.irisx/transfer-verification-20261013/rebuild-offline-2','.irisx/run008-packaging/independent-reviewed-proposal','.irisx/RUN008-ENGINEERING-REBUILD-REPORT.json'):
            with self.subTest(relative=relative):
                p=self.repo/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'keep')
                with patch.object(b.subprocess,'check_output',return_value=(b.TREE+'\n').encode()),patch.object(b.subprocess,'run') as execute:
                    with self.assertRaisesRegex(ValueError,'preserve prior'):self.invoke()
                    execute.assert_not_called();self.assertEqual(p.read_bytes(),b'keep')
                p.unlink()
    def test_changed_overlay_rejected_before_any_builder(self):
        p=self.repo/'tools/arc_qwen_rlvr004_20261013/loader_repair_run008/OVERLAY-MANIFEST.json';p.parent.mkdir(parents=True);p.write_bytes(b'changed')
        with patch.object(b.subprocess,'check_output',return_value=(b.TREE+'\n').encode()),patch.object(b.subprocess,'run') as execute:
            with self.assertRaisesRegex(ValueError,'overlay/review'):self.invoke()
            execute.assert_not_called()
    def test_git_lazy_fetch_disabled_before_first_object_read(self):
        p=self.repo/'.irisx/RUN008-ENGINEERING-REBUILD-REPORT.json';p.parent.mkdir();p.write_bytes(b'keep')
        with patch.object(b.subprocess,'check_output',return_value=(b.TREE+'\n').encode()) as git,patch.object(b.subprocess,'run') as execute:
            with self.assertRaisesRegex(ValueError,'preserve prior'):self.invoke()
            self.assertEqual(git.call_args.kwargs['env']['GIT_NO_LAZY_FETCH'],'1')
            for key in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_DATASETS_OFFLINE'):
                self.assertEqual(git.call_args.kwargs['env'][key],'1')
            execute.assert_not_called()
    def test_no_native_operator_or_shell_entry(self):
        s=(HERE/'rebuild_engineering.py').read_text()
        self.assertNotIn('shell=True',s);self.assertNotIn('publication_run008/launch.py',s)
        self.assertNotIn('import kaggle',s);self.assertNotIn('time.time(',s)
        self.assertIn("need(digest(proposal/'ASSEMBLY-INVENTORY.json')==PROPOSAL_INVENTORY",s)

if __name__=='__main__':unittest.main(verbosity=2)

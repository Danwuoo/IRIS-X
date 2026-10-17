"""Offline license payload integrity; no legal/GPU/model readiness attestation."""
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import stage_nvarc_e10_screen as stage
from tools import stage_nvarc_e10_probe as probe_stage
from tests.test_nvarc_e10_probe import probe_fixture


ROOT=Path(__file__).resolve().parents[1]


def contract_v1():
    return {'format':'irisx/native-code-material-contract-v1','files_sha256':{name:'0'*64 for name in stage.EXTERNAL_FILES},
        'template_sha256':'0'*64,'tokenizer_sha256':'0'*64,'source_provenance':'synthetic contract API fixture'}


class NoticeTests(unittest.TestCase):
    def setUp(self):
        self.contract={**contract_v1(),'format':'irisx/native-code-material-contract-v2',
            'notices_sha256':dict(stage.NOTICE_FILES_SHA256)}
        self.external={'notices/'+name:(ROOT/'research/stage4-e10/native-notices'/name).read_bytes()
            for name in stage.NOTICE_FILES_SHA256}
    def test_exact_retained_notice_license_provenance_hashes_and_slots(self):
        self.assertTrue(stage.native_notice_closure(self.contract,self.external))
        self.assertEqual(set(stage.material_files(self.contract)),set(stage.EXTERNAL_FILES)|set(self.external))
        for name,body in self.external.items():
            self.assertEqual(hashlib.sha256(body).hexdigest(),stage.NOTICE_FILES_SHA256[name.removeprefix('notices/')])

    def test_windows_autocrlf_checkout_preserves_exact_notice_bytes(self):
        # Exercise Git's real checkout filter, not newline-normalized reads or
        # weakened digest assertions. No repository history or remotes change.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '--quiet', str(root)], check=True, capture_output=True)
            (root / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            notices = root / 'research/stage4-e10/native-notices'
            notices.mkdir(parents=True)
            for name in stage.NOTICE_FILES_SHA256:
                (notices / name).write_bytes(self.external['notices/' + name])
            subprocess.run(['git', '-c', 'core.autocrlf=false', 'add', '.'],
                cwd=root, check=True, capture_output=True)
            for name in stage.NOTICE_FILES_SHA256:
                (notices / name).unlink()
            subprocess.run(['git', '-c', 'core.autocrlf=true', 'checkout-index', '-a', '-f'],
                cwd=root, check=True, capture_output=True)
            for name, expected in stage.NOTICE_FILES_SHA256.items():
                self.assertEqual(hashlib.sha256((notices / name).read_bytes()).hexdigest(), expected, name)
    def test_missing_tampered_or_unbound_notice_members_reject(self):
        for name in self.external:
            absent=dict(self.external);absent.pop(name)
            with self.assertRaisesRegex(RuntimeError,'license/notice/provenance'):
                stage.native_notice_closure(self.contract,absent)
            with self.assertRaisesRegex(RuntimeError,'license/notice/provenance'):
                stage.native_notice_closure(self.contract,{**self.external,name:self.external[name]+b' altered'})
        bad=copy.deepcopy(self.contract);bad['notices_sha256']['unexpected.txt']='0'*64
        with self.assertRaisesRegex(RuntimeError,'closed reviewed'):
            stage.material_files(bad)
    def test_historical_v1_schema_preserved_without_notice_readiness_claim(self):
        self.assertEqual(stage.material_files(contract_v1()),stage.EXTERNAL_FILES)
        self.assertFalse(stage.native_notice_closure(contract_v1(),{}))
    def test_source_cells_stay_frozen_and_generated_modified_prefix_has_attribution(self):
        from tools.nvarc_native_solve_runtime import SOURCE_HASHES
        self.assertEqual(SOURCE_HASHES,{'solver.py':'1387c5b0b188dcc8570659dd5905ec2e824e5e0dfd7b20d8be9c2e13d0f12962',
            'arc_loader.py':'d01cd56167e534ae156706ef62ab11662fc7b403964614a7a55131940bde970c',
            'arc_decoder.py':'965cfd910777d9bbec9681c6c15c5e2ea3924569734248046f5e58f16cb28222'})
        source=stage.rendered_worker().decode()
        self.assertTrue(source.startswith(stage.NATIVE_ATTRIBUTION));self.assertIn('does not relicense the entire file',source)
    def test_probe_cannot_receive_runtime_admission_with_historical_unlicensed_contract(self):
        plan,_=probe_fixture()
        config={key:plan[key] for key in stage.CONFIG_FIELDS};config['native_source_learning_rates']=plan['native_source_learning_rates']
        with patch.object(probe_stage,'validate_baseline'),self.assertRaisesRegex(RuntimeError,'license/notice closure'):
            probe_stage.construct('stage4-e10-probe-denied-license','0'*40,{},config,contract_v1(),resource_admission={})


if __name__=='__main__':unittest.main()

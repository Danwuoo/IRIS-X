"""No-model packaging mode tests; source-only default must not claim full evidence."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import reproduce_release as r
import runtime_assembly as a
class ReconstructionModes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='checkpoint-owner-modes-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=HERE.parents[1]
    def test_default_source_only_without_raw_archive(self):
        result=r.reproduce(self.repo,self.root/'source-only')
        self.assertEqual(result['status'],'SOURCE_ONLY_RECONSTRUCTION_PASS')
        self.assertFalse(result['complete_historical_release']);self.assertEqual(result['runtime_members'],200)
        self.assertEqual(result['release_files'],39);self.assertEqual(result['expected_full_release_files'],40)
        self.assertFalse((Path(result['release'])/r.EXTERNAL_MEMBER).exists())
        self.assertEqual([x['path'] for x in result['omitted_external_evidence']],[r.EXTERNAL_MEMBER])
    def test_explicit_full_without_external_fails_before_output(self):
        with self.assertRaisesRegex(a.AssemblyError,'external_predecessor_evidence_required'):
            r.reproduce(self.repo,self.root/'missing',full_release=True)
        self.assertFalse((self.root/'missing').exists())
    def test_wrong_external_fails_closed_before_output(self):
        p=self.root/'fixture';p.write_bytes(b'not predecessor evidence')
        with self.assertRaisesRegex(a.AssemblyError,'external_predecessor_evidence_mismatch'):
            r.reproduce(self.repo,self.root/'wrong',full_release=True,predecessor_evidence=p)
        self.assertFalse((self.root/'wrong').exists())
    def test_external_requires_explicit_full_switch(self):
        with self.assertRaisesRegex(a.AssemblyError,'external_input_requires_explicit_full_release'):
            r.reproduce(self.repo,self.root/'wrong',predecessor_evidence=self.root/'unused')
        self.assertFalse((self.root/'wrong').exists())
    def test_external_symlink_denied(self):
        p=self.root/'fixture';p.write_bytes(b'fixture');link=self.root/'link';link.symlink_to(p)
        with self.assertRaises(a.AssemblyError):r.reproduce(self.repo,self.root/'linked',full_release=True,predecessor_evidence=link)
        self.assertFalse((self.root/'linked').exists())
if __name__=='__main__':unittest.main()

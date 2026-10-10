import json,tempfile,unittest,zipfile
from pathlib import Path
from unittest import mock
from tools.arc_public_research_20261010 import source_pack as p

class SourcePackTests(unittest.TestCase):
    def test_closed_deterministic_source_archive(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=Path(t)/'a',Path(t)/'b';x=p.build_code(a);y=p.build_code(b)
            self.assertEqual(x,y);self.assertEqual((a/'source.zip').read_bytes(),(b/'source.zip').read_bytes())
            m=json.loads((a/'manifest.json').read_bytes())
            self.assertFalse(m['contains_public_test_answers']);self.assertFalse(m['contains_model_weights'])
            with zipfile.ZipFile(a/'source.zip') as z:
                self.assertEqual(set(z.namelist()),set(m['source_identity']))
                self.assertIn('tools/arc_public_research_20261010/runner.py',z.namelist())
                self.assertNotIn('tools/arc_public_research_20261010/source_pack.py',z.namelist())
                for name in z.namelist():self.assertEqual(p.sha(z.read(name)),m['source_identity'][name])
    def test_empty_pinned_scorer_rejected(self):
        original=p.regular
        with mock.patch.object(p,'regular',side_effect=lambda path:b'' if path.name=='arc_offline_evaluation.py' else original(path)):
            with self.assertRaisesRegex(ValueError,'historical scorer'):p.collect_sources()
    def test_data_manifest_opaque_file_hashing(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for role in ('solver','evaluator'):
                (root/role).mkdir();(root/role/'manifest.json').write_bytes(b'{}\n')
                (root/role/'opaque').write_bytes(b'synthetic bytes')
            r=p.build_data_manifest(root);self.assertEqual(r['files'],4)
            self.assertEqual(json.loads((root/'public-data-material.json').read_bytes())['tests'],167)
            with self.assertRaises(ValueError):p.build_data_manifest(root)

if __name__=='__main__':unittest.main()

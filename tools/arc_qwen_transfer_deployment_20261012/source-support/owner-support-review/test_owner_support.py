import hashlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'owner-handoff/complete-source'
DEP=PACKAGE/'repository/tools/arc_qwen_transfer_deployment_20261012'
sys.path.insert(0,str(DEP))
import runtime_assembly as a
import reproduce_release as rr
class Support(unittest.TestCase):
 def test_pinned_sources_and_mapping(self):
  r=DEP/'release/transfer-v1'
  entries,inner=a.load_contract(source_freeze=r/'SOURCE-FREEZE.json',publication_manifest=r/'publication-manifest.json',path_map=DEP/'runtime-path-map.json')
  self.assertEqual(len(entries),197);self.assertEqual(len(inner),192)
  self.assertEqual(entries['panel-freeze/public120-exclusions.json']['repository_path'],'research/qwen-transfer-20261012/panel-freeze/public120-exclusions.json')
  self.assertEqual(sum(n.startswith('materials/') for n in entries),28)
 def test_real_reproduction(self):
  with tempfile.TemporaryDirectory() as d:
   result=rr.reproduce(PACKAGE/'repository',Path(d)/'out')
   self.assertEqual(result['status'],'PASS');self.assertEqual(result['runtime_members'],197)
   actual=Path(d)/'out/release'
   expected=ROOT/'release-candidate-001'
   for f in expected.rglob('*'):
    if f.is_file():self.assertEqual(f.read_bytes(),(actual/f.relative_to(expected)).read_bytes())
   self.assertEqual(a.verify_runtime(Path(d)/'out/runtime',PACKAGE/'repository')['runtime_member_count'],197)
 def test_existing_destination_unchanged(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'out';out.mkdir();(out/'keep').write_text('user data')
   with self.assertRaises(a.AssemblyError):rr.reproduce(PACKAGE/'repository',out)
   self.assertEqual((out/'keep').read_text(),'user data');self.assertEqual(list(out.iterdir()),[out/'keep'])
 def test_overlap_denied(self):
  with self.assertRaises(a.AssemblyError):rr.reproduce(PACKAGE/'repository',PACKAGE/'repository'/'should-not-exist')
 def test_linked_output_parent_denied(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'real').mkdir();(root/'link').symlink_to(root/'real',target_is_directory=True)
   with self.assertRaises(a.AssemblyError):rr.reproduce(PACKAGE/'repository',root/'link/out')
   self.assertFalse((root/'real/out').exists())
 def test_changed_metadata_denied(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'map';p.write_bytes((DEP/'runtime-path-map.json').read_bytes()+b' ')
   r=DEP/'release/transfer-v1'
   with self.assertRaises(a.AssemblyError):a.load_contract(source_freeze=r/'SOURCE-FREEZE.json',publication_manifest=r/'publication-manifest.json',path_map=p)
 def test_path_traversal_denied(self):
  for name in ('../x','/tmp/x','a/../x','a//x','a\\x','a:x'):
   with self.subTest(name=name),self.assertRaises(a.AssemblyError):a.safe_name(name)
 def test_support_no_network_or_model_import(self):
  import ast
  for name in ('runtime_assembly.py','reproduce_release.py'):
   tree=ast.parse((DEP/name).read_text())
   roots={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}|{n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module}
   self.assertFalse(roots&{'torch','transformers','peft','requests','urllib','socket','subprocess','kaggle'})
if __name__=='__main__':unittest.main(verbosity=2)

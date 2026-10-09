import ast,base64,contextlib,hashlib,io,json,os,tempfile,unittest,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class NotebookTests(unittest.TestCase):
 def test_exact10_closed_inert_and_hashes(self):
  files=sorted((ROOT/'notebooks').glob('*.ipynb'));self.assertEqual(len(files),10)
  manifest=json.loads((ROOT/'publication-manifest.json').read_text());byid={r['run_id']:r for r in manifest['notebooks']}
  self.assertEqual(set(byid),{'N'+str(i) for i in range(5,15)})
  for file in files:
   nb=json.loads(file.read_text());run=nb['metadata']['irisx_run_id'];self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),byid[run]['sha256'])
   self.assertFalse(byid[run]['enable_gpu']);self.assertFalse(byid[run]['enable_tpu']);self.assertFalse(byid[run]['enable_internet']);self.assertFalse(byid[run]['manual_start'])
   ns={}
   with tempfile.TemporaryDirectory() as td:
    old=os.getcwd();os.chdir(td)
    try:
     with contextlib.redirect_stdout(io.StringIO()) as stdout:
      for c in nb['cells']:
       if c['cell_type']=='code':
        self.assertIsNone(c['execution_count']);self.assertEqual(c['outputs'],[]);source=''.join(c['source']);ast.parse(source);exec(compile(source,'trusted-notebook','exec'),ns)
     self.assertIn('INACTIVE',stdout.getvalue());self.assertEqual(list(Path(td).iterdir()),[])
    finally:os.chdir(old)
   packed=base64.b64decode(ns['PACKED_SOURCE_BASE64'],validate=True);self.assertEqual(hashlib.sha256(packed).hexdigest(),ns['PACKED_SOURCE_SHA256'])
   contents=json.loads(zlib.decompress(packed));self.assertEqual(set(contents),set(ns['FILE_HASHES']))
   for name,value in contents.items():self.assertEqual(hashlib.sha256(value.encode()).hexdigest(),ns['FILE_HASHES'][name]);self.assertEqual(value,(ROOT/'src'/name).read_text())
   self.assertEqual(contents['source-lock.json'],(ROOT/'src/source-lock.json').read_text())
 def _namespace(self,run):
  file=next(p for p in (ROOT/'notebooks').glob('*.ipynb') if json.loads(p.read_text())['metadata']['irisx_run_id']==run)
  cells=json.loads(file.read_text())['cells'];ns={}
  for cell in cells[1:3]:exec(compile(''.join(cell['source']),'trusted-notebook-setup','exec'),ns)
  return ns,''.join(cells[3]['source'])
 def test_active_source_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td)/'base';base.mkdir();outside=Path(td)/'outside';outside.mkdir();(base/'source').symlink_to(outside,target_is_directory=True)
   ns,source=self._namespace('N13');ns.update(BASE=base,MANUAL_START=True)
   with self.assertRaisesRegex(ValueError,'Symlink source directory'):exec(compile(source,'trusted-notebook-run','exec'),ns)
   self.assertEqual(list(outside.iterdir()),[])
 def test_active_missing_gate_blocks_before_input_scan_or_model(self):
  with tempfile.TemporaryDirectory() as td:
   ns,source=self._namespace('N9');ns.update(BASE=Path(td)/'base',MANUAL_START=True)
   for role in ns['PINS']:
    path=Path(td)/'inputs'/role;path.mkdir(parents=True);ns[role.upper()+'_ROOT']=str(path)
   with contextlib.redirect_stdout(io.StringIO()):exec(compile(source,'trusted-notebook-run','exec'),ns)
   self.assertEqual(ns['result']['status'],'blocked');self.assertEqual(ns['result']['generate_calls'],0)
   self.assertFalse((ns['BASE']/'environment-cp312-cu128').exists());self.assertFalse((ns['BASE']/'cpython312').exists())
 def test_active_malformed_prior_gets_blocked_receipt(self):
  with tempfile.TemporaryDirectory() as td:
   ns,source=self._namespace('N9');ns.update(BASE=Path(td)/'base',MANUAL_START=True)
   for role in ns['PINS']:
    path=Path(td)/'inputs'/role;path.mkdir(parents=True);ns[role.upper()+'_ROOT']=str(path)
   bad=Path(td)/'bad-prior';bad.mkdir();ns['PRIOR_RESULTS']={'N6':str(bad)}
   with contextlib.redirect_stdout(io.StringIO()):exec(compile(source,'trusted-notebook-run','exec'),ns)
   self.assertEqual(ns['result']['status'],'blocked');self.assertEqual(ns['result']['reason'],'invalid-prerequisite')
   self.assertEqual(ns['result']['generate_calls'],0);self.assertTrue(Path(ns['result']['output'],'blocked.json').exists())
if __name__=='__main__':unittest.main(verbosity=2)

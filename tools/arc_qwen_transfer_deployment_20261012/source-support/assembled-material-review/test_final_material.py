import ast,contextlib,hashlib,io,json,pathlib,socket,unittest,zipfile
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]; RELEASE=ROOT/'release-candidate-001'
EXPECTED='689e587ce8d7c0c7c606176dac5c010e7a9a1fb817d65ace1c59773f55f96d9a'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def cells(nb):return [''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code']
class FinalMaterial(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  raw=(RELEASE/'publication-manifest.json').read_bytes();assert sha(raw)==EXPECTED
  cls.m=json.loads(raw);cls.nbs=[json.loads((RELEASE/r['path']).read_bytes()) for r in cls.m['notebooks']]
 def test_payload197_closed_and175_preserved(self):
  z=zipfile.ZipFile(RELEASE/'code-payload/source.zip'); old=zipfile.ZipFile(ROOT.parent/'portfolio63-source-recovery-20261012/exact-delivered/support/code-payload/source.zip')
  self.assertEqual(len(z.namelist()),197);self.assertEqual(len(set(z.namelist())),197);self.assertIsNone(z.testzip())
  for n in old.namelist():self.assertEqual(z.read(n),old.read(n))
  allowed={n for n in z.namelist() if n not in old.namelist()}
  self.assertTrue(all(n.startswith(('tools/arc_qwen_transfer_20261012/','tools/arc_qwen_transfer_deployment_20261012/','panel-freeze/')) for n in allowed))
  self.assertTrue(all(not n.endswith(('.safetensors','.pt','.bin','.zip','.ipynb')) for n in allowed))
 def test_notebook_artifact_binding(self):
  for row,nb in zip(self.m['notebooks'],self.nbs):
   raw=(RELEASE/row['path']).read_bytes();self.assertEqual(sha(raw),row['sha256']);self.assertEqual(len(raw),row['bytes'])
   for c in nb['cells']:
    if c['cell_type']=='code':self.assertEqual(c['outputs'],[]);self.assertIsNone(c['execution_count'])
 def test_exact_activation_delta(self):
  a,b=map(cells,self.nbs);self.assertEqual(a[1:],b[1:]);
  self.assertEqual(a[0].replace('MANUAL_START = False','MANUAL_START = True').replace('ENABLE_MODEL = False','ENABLE_MODEL = True'),b[0])
 def test_inert_notebook_performs_no_io(self):
  env={'__name__':'__notebook__'}
  def denied(*a,**k):raise AssertionError('inert notebook touched filesystem/network')
  with patch('builtins.open',side_effect=denied),patch.object(pathlib.Path,'exists',side_effect=denied),patch.object(pathlib.Path,'is_file',side_effect=denied),patch.object(pathlib.Path,'mkdir',side_effect=denied),patch.object(socket,'socket',side_effect=denied),contextlib.redirect_stdout(io.StringIO()):
   for code in cells(self.nbs[0]):exec(compile(code,'reviewed-final-inert','exec'),env)
  self.assertEqual(env['RESULT']['status'],'DISABLED')
 def test_active_none_epoch_denies_before_io(self):
  env={'__name__':'__notebook__'};a=cells(self.nbs[1]);exec(compile(a[0],'config','exec'),env);exec(compile(a[1],'loader','exec'),env)
  with patch.object(pathlib.Path,'is_symlink',side_effect=AssertionError('filesystem reached')),self.assertRaisesRegex(ValueError,'predispatch epoch'):
   exec(compile(a[2],'entry','exec'),env)
 def test_clocks_pins_and_inactive_wire(self):
  inactive,active=self.m['notebooks']
  self.assertEqual((inactive['save_version_value'],inactive['enable_gpu'],inactive['machine_shape']),(3,False,None))
  self.assertEqual((active['save_version_value'],active['session_timeout_seconds']),(1,42300))
  for r in (inactive,active):
   self.assertEqual([r[k] for k in ('execution_cutoff_seconds','outer_cutoff_seconds','provider_runtime_seconds','global_seconds')],[42000,42180,42300,43200])
   self.assertEqual(r['dispatch_epoch_patch']['maximum_patch_age_seconds'],60);self.assertEqual(len(r['dataset_sources']),8)
   self.assertEqual(r['model_sources'],['qwen-lm/qwen-3/transformers/14b/1'])
 def test_evaluator_never_in_child_request_comprehension(self):
  z=zipfile.ZipFile(RELEASE/'code-payload/source.zip');s=z.read('tools/arc_qwen_transfer_20261012/runner.py').decode()
  self.assertIn("if k not in ('public_evaluator_root','public_evaluator_manifest_sha256')",s)
  s=z.read('tools/arc_qwen_transfer_deployment_20261012/source_loader.py').decode()
  self.assertNotIn("read(data/'evaluator",s)
 def test_clock_future_and_zero_denial_without_fs(self):
  env={'__name__':'__notebook__'};a=cells(self.nbs[1]);exec(compile(a[0],'config','exec'),env);exec(compile(a[1],'loader','exec'),env)
  for epoch in (float('nan'),True,0,10**20):
   env['PREDISPATCH_EPOCH']=epoch
   with self.subTest(epoch=str(epoch)),patch.object(pathlib.Path,'is_symlink',side_effect=AssertionError('filesystem reached')),self.assertRaises(ValueError):
    exec(compile(a[2],'entry','exec'),env)
if __name__=='__main__':unittest.main(verbosity=2)

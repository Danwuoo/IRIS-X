import ast,contextlib,hashlib,io,json,pathlib,socket,unittest,zipfile
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]; RELEASE=ROOT/'release-candidate-001'
EXPECTED='1db39d38fca5bb58c7f73035a2b555566f2a44c23c496488a0f55ba1f5da0331'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def cells(nb):return [''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code']
class FinalMaterial(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  raw=(RELEASE/'publication-manifest.json').read_bytes()
  if sha(raw)!=EXPECTED:raise ValueError('final manifest differs')
  cls.m=json.loads(raw);cls.nbs=[json.loads((RELEASE/r['path']).read_bytes()) for r in cls.m['notebooks']]
 def test_payload200_closed_and174_preserved(self):
  z=zipfile.ZipFile(RELEASE/'code-payload/source.zip'); old=zipfile.ZipFile(ROOT.parent/'portfolio63-source-recovery-20261012/exact-delivered/support/code-payload/source.zip')
  self.assertEqual(len(z.namelist()),200);self.assertEqual(len(set(z.namelist())),200);self.assertIsNone(z.testzip())
  changed={n for n in old.namelist() if z.read(n)!=old.read(n)}
  self.assertEqual(changed,{'tools/arc_qwen_portfolio_20261012/checkpoints.py'})
  self.assertEqual(len(old.namelist())-len(changed),174)
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
 def test_review_descriptor_resolves_and_exact_final_approval(self):
  d=self.m['runtime_source_approval'];raw=(RELEASE/d['path']).read_bytes()
  self.assertEqual(d['path'],'RUNTIME-SOURCE-APPROVAL.json');self.assertEqual(len(raw),d['bytes']);self.assertEqual(sha(raw),d['sha256'])
  self.assertEqual(sha(raw),'7053c1897ee799645a474e3be54677dfb3bc38d33e31dc0f8eecd8fb0ea513fa')
  a=json.loads(raw);self.assertTrue(a['approved']);self.assertEqual(a['known_blockers'],[])
  with zipfile.ZipFile(RELEASE/'code-payload/source.zip') as z:
   for n,h in a['runtime_source_identity'].items():self.assertEqual(sha(z.read(n)),h)
 def test_exact_narrow_runtime_delta(self):
  with zipfile.ZipFile(RELEASE/'code-payload/source.zip') as z,zipfile.ZipFile(ROOT.parent/'portfolio63-transfer-repair-20261012/release-candidate-002/code-payload/source.zip') as old:
   self.assertEqual(set(old.namelist())-set(z.namelist()),set())
   self.assertEqual(set(z.namelist())-set(old.namelist()),{'tools/arc_qwen_transfer_20261012/checkpoint_policy.py'})
   self.assertEqual({n.rsplit('/',1)[-1] for n in old.namelist() if z.read(n)!=old.read(n)}, {'checkpoints.py','backend.py','experiment.py','public_evaluation.py'})
 def test_explicit_final_capacity_and_fixed_identity(self):
  self.assertEqual(self.m['format'],'irisx/qwen14b-transfer-checkpoint-repair-publication-contract-v1')
  self.assertEqual(self.m['datasets'][0]['expected_version'],13)
  self.assertEqual([n['expected_version'] for n in self.m['notebooks']],[24,25]);self.assertEqual(self.m['notebooks'][1]['role'],'transfer003')
  a=self.m['terminal_contract']['archive_caps'];self.assertEqual(a['evidence_expanded_bytes'],512*1024**2);self.assertEqual(a['evidence_archive_bytes'],544*1024**2)
  self.assertEqual(a['evidence_members'],12000);self.assertEqual(a['checkpoint_expanded_bytes'],2*1024**3)
  d=self.m['generation_call_policy'];raw=(RELEASE/d['path']).read_bytes();self.assertEqual(sha(raw),d['sha256']);self.assertEqual(len(raw),d['bytes'])
  with zipfile.ZipFile(RELEASE/'code-payload/source.zip') as z:self.assertEqual(sha(z.read(d['source_member'])),d['source_sha256'])
 def test_exact_checkpoint_policy_source_and_schedules(self):
  d=self.m['checkpoint_policy']; raw=(RELEASE/d['path']).read_bytes(); self.assertEqual(len(raw),d['bytes']);self.assertEqual(sha(raw),d['sha256'])
  p=json.loads(raw)
  with zipfile.ZipFile(RELEASE/'code-payload/source.zip') as z:
   for n,h in p['source_sha256'].items():self.assertEqual(sha(z.read(n)),h)
  self.assertEqual(set(p['contracts']),{'global','ttt','fixture'})
  for name,scope,steps,fixture in [('global','global',[0,64,256],False),('ttt','task',[0,8,16],False),('fixture','global',[0,1,2],True)]:
   c=p['contracts'][name];self.assertEqual(c['scope'],scope);self.assertEqual(c['allowed_updates'],steps);self.assertIs(c['fixture_only'],fixture)
   self.assertTrue(all(type(i) is int for i in c['allowed_updates']))
   for n,h in c['source_sha256'].items():self.assertEqual(p['source_sha256']['tools/arc_qwen_transfer_20261012/'+n],h)
 def test_frozen_science_protocol_unchanged(self):
  names=['protocol.py','data.py','science_profiles.py','call_policy.py','timing_refresh.py','runner.py']
  with zipfile.ZipFile(RELEASE/'code-payload/source.zip') as z,zipfile.ZipFile(ROOT.parent/'portfolio63-transfer-repair-20261012/release-candidate-002/code-payload/source.zip') as old:
   for n in names:
    key='tools/arc_qwen_transfer_20261012/'+n;self.assertEqual(z.read(key),old.read(key))
if __name__=='__main__':unittest.main(verbosity=2)

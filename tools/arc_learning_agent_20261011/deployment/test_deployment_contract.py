import ast,hashlib,importlib.util,json,os,pathlib,sys,tempfile,time,unittest
D=pathlib.Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('deployment_preloader',D/'preloader.py');P=importlib.util.module_from_spec(s);s.loader.exec_module(P)
M=json.loads((D/'publication-manifest.json').read_bytes())
def notebook_path(row):
 name=pathlib.Path(row['path']).name
 candidates=[D/name,D.parent/'notebooks'/name]
 matches=[p for p in candidates if p.is_file()]
 if len(matches)!=1:raise RuntimeError('Exactly one local reviewed notebook required')
 return matches[0]
def runtime_root():
 if D.name=='deployment' and D.parent.name=='arc_learning_agent_20261011':return D.parents[2]
 return D.parent/'public120-next-20261011/worktree'
class DeploymentContractTests(unittest.TestCase):
 def test_all_template_hashes_and_default_inert(self):
  for row in M['notebooks']:
   raw=notebook_path(row).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256']);self.assertEqual(len(raw),row['bytes'])
   doc=json.loads(raw);self.assertTrue(all(c.get('outputs',[])==[] and c.get('execution_count') is None for c in doc['cells']))
   if row['role']=='inactive':
    scope={}
    for c in doc['cells']:
     if c['cell_type']=='code':exec(compile(''.join(c['source']),'<inert-reviewed-cell>','exec'),scope)
    self.assertFalse(scope['MANUAL_START']);self.assertFalse(scope['ENABLE_MODEL']);self.assertNotIn('_learning_result',scope)
 def test_activation_only_three_config_fields(self):
  docs=[json.loads(notebook_path(r).read_bytes()) for r in M['notebooks']]
  for i in (0,2,3):self.assertEqual(docs[0]['cells'][i],docs[1]['cells'][i])
  def assignments(d):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(''.join(d['cells'][1]['source'])).body if isinstance(n,ast.Assign)}
  a,b=map(assignments,docs);self.assertEqual({k for k in a if a[k]!=b[k]},{'MANUAL_START','ENABLE_MODEL','OUTPUT_ROOT'});self.assertIsNone(b['PREDISPATCH_EPOCH'])
 def test_embedded_bindings(self):
  doc=json.loads(notebook_path(M['notebooks'][0]).read_bytes());scope={};exec(''.join(doc['cells'][2]['source']),scope)
  for role in ('loader','guard'):
   self.assertEqual(hashlib.sha256(scope[role.upper()+'_SOURCE'].encode()).hexdigest(),M['notebook_launcher'][role+'_sha256'])
  self.assertEqual(hashlib.sha256((D/'preloader.py').read_bytes()).hexdigest(),M['notebook_launcher']['preloader_sha256'])
 def test_runtime97_unchanged(self):
  root=runtime_root()
  self.assertEqual(len(M['source_identity']),97)
  for n,h in M['source_identity'].items():self.assertEqual(hashlib.sha256((root/n).read_bytes()).hexdigest(),h,n)
 def test_budget_exact(self):
  self.assertEqual(M['notebooks'][1]['provider_session_timeout_seconds'],42300);self.assertEqual(M['notebook_launcher']['deadline_seconds'],43200);self.assertEqual(M['notebook_launcher']['cleanup_reserve_seconds'],30)
 def test_input_overlap_blocks_before_writes(self):
  with tempfile.TemporaryDirectory(dir=D) as td:
   root=pathlib.Path(td);output=root/'input/output'; c={'manual_start':True,'enable_model':False,'profile':'LEARNING_AGENT12H','session_seconds':43200,'predispatch_epoch':None,'output_root':str(output),'source_parent':str(root/'source'),'input_root':str(root/'input'),'code_root':None,'data_root':None,'training_root':None,'model_config':None,'seed':0}
   with self.assertRaisesRegex(ValueError,'overlaps'):P.launch_reviewed_notebook(pins={},config=c,loader_source='',guard_source='',expected_loader_sha256=hashlib.sha256(b'').hexdigest(),expected_guard_sha256=hashlib.sha256(b'').hexdigest())
   self.assertEqual(list(root.iterdir()),[])
 def test_outer_environment_overlap_blocks_before_writes(self):
  with tempfile.TemporaryDirectory(dir=D) as td:
   root=pathlib.Path(td);output=root/'output'; c={'manual_start':True,'enable_model':False,'profile':'LEARNING_AGENT12H','session_seconds':43200,'predispatch_epoch':None,'output_root':str(output),'source_parent':str(root/'source'),'input_root':str(root/'input'),'code_root':None,'data_root':None,'training_root':None,'model_config':{'explicit_roots':{'model':str(root/'output-environment/assets')}},'seed':0}
   with self.assertRaisesRegex(ValueError,'overlaps'):P.launch_reviewed_notebook(pins={},config=c,loader_source='',guard_source='',expected_loader_sha256=hashlib.sha256(b'').hexdigest(),expected_guard_sha256=hashlib.sha256(b'').hexdigest())
   self.assertEqual(list(root.iterdir()),[])
if __name__=='__main__':unittest.main(verbosity=2)

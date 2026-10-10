"""CPU-only notebook I/O regression. Scientific runner/source lock stays frozen."""
import contextlib,copy,io,json,os,shutil,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'notebook_support'))
import arc_suite as s
import arc_evidence_inputs as h
from test_suite import Fixture

class InputTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.fx=Fixture(cls.temp.name)
  with patch.object(s,'read',side_effect=cls.fx.read):
   cls.priors={};cls.archives={}
   for run in ('N6','N7'):
    out,m,r,_=cls.fx.run(run);s.write(out/'report.json',r);s.write(out/'summary.json',{'status':'complete','processes_ok':True})
    cls.priors[run]=out;cls.archives[run]=Path(s.finalize(out)['path'])
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def setUp(self):
  self.temp2=tempfile.TemporaryDirectory();self.work=Path(self.temp2.name)
  self.p=patch.object(s,'read',side_effect=self.fx.read);self.p.start()
 def tearDown(self):self.p.stop();self.temp2.cleanup()
 def copy(self,run='N6',name='evidence'):
  path=self.work/name;shutil.copytree(self.priors[run],path);return path
 def discover(self,run='N9',**kwargs):return h.discover_priors(s,run,search_roots=[self.work],**kwargs)
 def test_zip_and_multilevel_autoextraction_deduplicate(self):
  d=self.work/'datasets/owner/arbitrary/payload/N6';d.parent.mkdir(parents=True);shutil.copytree(self.priors['N6'],d)
  shutil.copy2(self.archives['N6'],self.work/'uploaded.zip')
  (self.work/'manifest.json').write_text('{"kind":"unrelated-wrapper"}')
  paths,report=self.discover();self.assertEqual(Path(paths['N6']),d)
  self.assertEqual(len(report['selected']['N6']['identical_copies']),2)
  self.assertEqual(s.resolve_gate('N9',paths)['status'],'passed')
 def test_wrong_run_ignored_and_missing_report_only_diagnosed(self):
  self.copy('N7');(self.work/'report.json').write_text('{}')
  paths,report=self.discover();self.assertEqual(paths,{});self.assertEqual(report['missing'],['N6'])
  self.assertTrue(report['rejected'])
 def test_two_valid_identities_block_no_latest_choice(self):
  a=self.copy(name='a');b=self.copy(name='b');report=s.read(b/'report.json');report['interpretation']='distinct verified fixture'
  (b/'report.json').write_bytes(s.canonical(report));inv=s.read(b/'final-inventory.json');inv['files']['report.json']=s.file_sha(b/'report.json');(b/'final-inventory.json').write_bytes(s.canonical(inv))
  s.verified_prior(b,'N6')
  with self.assertRaises(h.InputError) as error:self.discover()
  self.assertEqual(error.exception.reason,'ambiguous-prerequisite')
  paths,report=h.discover_priors(s,'N9',{'N6':str(b)},[self.work]);self.assertEqual(Path(paths['N6']),b)
  self.assertEqual(report['selected']['N6']['method'],'explicit-override')
 def test_auto_evidence_pin_enforced_after_ambiguity(self):
  self.copy();pin={'N6':{'final_inventory_sha256':'0'*64}}
  with self.assertRaises(h.InputError) as error:self.discover(expected_evidence=pin)
  self.assertEqual(error.exception.reason,'prerequisite-evidence-pin-mismatch')
 def test_tamper_partial_old_lock_and_unexpected_file_rejected(self):
  for kind in ('tamper','partial','old-lock','extra'):
   with self.subTest(kind=kind):
    d=self.copy(name=kind)
    if kind=='extra':(d/'unexpected.txt').write_text('x')
    elif kind=='old-lock':
     m=s.read(d/'manifest.json');m['core']['source_lock_sha256']='0'*64;m['core_sha256']=s.digest(m['core']);m['records']=s.identities(m['core']);(d/'manifest.json').write_bytes(s.canonical(m))
    elif kind=='partial':
     value=s.read(d/'summary.json');value['status']='partial-or-failed';(d/'summary.json').write_bytes(s.canonical(value))
     inv=s.read(d/'final-inventory.json');inv['files']['summary.json']=s.file_sha(d/'summary.json');(d/'final-inventory.json').write_bytes(s.canonical(inv))
    else:(d/'report.json').write_text('{}')
    with self.assertRaises(Exception):h.verify_candidate(s,d,'N6')
 def test_nonstopped_and_search_incomplete_rejected(self):
  for field in ('processes_ok','search_ledger_complete'):
   d=self.copy(name=field);name='summary.json' if field=='processes_ok' else 'report.json';value=s.read(d/name);value[field]=False;(d/name).write_bytes(s.canonical(value))
   inv=s.read(d/'final-inventory.json');inv['files'][name]=s.file_sha(d/name);(d/'final-inventory.json').write_bytes(s.canonical(inv))
   with self.assertRaises(ValueError):h.verify_candidate(s,d,'N6')
 def test_symlink_root_parent_and_member_rejected(self):
  d=self.copy();link=self.work/'link';link.symlink_to(d,target_is_directory=True)
  with self.assertRaises(ValueError):h.verify_candidate(s,link,'N6')
  (d/'alias').symlink_to(d/'report.json')
  with self.assertRaises(ValueError):h.verify_candidate(s,d,'N6')
 def test_traversal_duplicate_and_oversize_zip_rejected(self):
  for name in ('../escape','a/../escape','/absolute','bad\\name','a//b'):
   p=self.work/'unsafe.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr(name,'x')
   with self.assertRaises(ValueError):h.materialize(s,p)
  with zipfile.ZipFile(p,'w') as z:
   z.writestr('final-inventory.json','{}');z.writestr('final-inventory.json','{}')
  with self.assertRaises(ValueError):h.materialize(s,p)
  with patch.object(h,'MAX_BYTES',1):
   with self.assertRaises(ValueError):h.materialize(s,self.archives['N6'])
 def test_model_asset_trees_are_not_scanned(self):
  slug=s.EXPECTED_PINS['model']['reference'].split('/')[1];d=self.work/slug;d.mkdir();(d/'do-not-follow').symlink_to('/nonexistent')
  self.copy();paths,report=self.discover();self.assertIn('N6',paths);self.assertEqual(report['scan']['directories'],2)
 def test_known_asset_alias_pruned_unknown_symlink_still_blocks(self):
  slug=s.EXPECTED_PINS['model']['reference'].split('/')[1]
  (self.work/slug).symlink_to('/nonexistent/never-follow')
  self.copy();paths,_=self.discover();self.assertIn('N6',paths)
  (self.work/'unknown-evidence-alias').symlink_to(self.priors['N6'])
  with self.assertRaises(h.InputError) as error:self.discover()
  self.assertEqual(error.exception.reason,'unsafe-prior-discovery-path')
 def test_typed_competition_tree_excluded_before_scandir(self):
  blocked=self.work/'competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents/.git/logs/refs/remotes/origin'
  blocked.mkdir(parents=True);self.copy()
  original=h.os.scandir;visited=[]
  def observe(path):
   visited.append(Path(path));self.assertFalse(Path(path).is_relative_to(self.work/'competitions'))
   return original(path)
  with patch.object(h,'KAGGLE_INPUT_ROOT',self.work),patch.object(h.os,'scandir',side_effect=observe):paths,report=self.discover()
  self.assertIn('N6',paths);self.assertIn(str(self.work/'competitions'),report['scan']['excluded_paths'])
 def test_explicit_competition_descendant_search_root_not_read(self):
  d=self.work/'competitions/arc-prize-2026-arc-agi-3/repo';d.mkdir(parents=True)
  with patch.object(h,'KAGGLE_INPUT_ROOT',self.work),patch.object(h.os,'scandir',side_effect=AssertionError('competition scan forbidden')):
   candidates,report=h.scan_candidates([d])
  self.assertEqual(candidates,[]);self.assertEqual(report['directories'],0)
 def test_legacy_competition_and_vcs_metadata_pruned(self):
  (self.work/'arc-prize-2026-arc-agi-3').symlink_to('/never-read-competition')
  for name in ('.git','.hg','.svn'):
   (self.work/'repo'/name/'deep/a/b/c/d/e/f/g/h').mkdir(parents=True)
  self.copy()
  with patch.object(h,'KAGGLE_INPUT_ROOT',self.work):paths,report=self.discover()
  self.assertIn('N6',paths);self.assertEqual(len(report['scan']['excluded_paths']),4)
 def test_dataset_wrapper_named_competitions_is_not_excluded(self):
  d=self.work/'datasets/owner/dataset/competitions/N6';d.parent.mkdir(parents=True);shutil.copytree(self.priors['N6'],d)
  with patch.object(h,'KAGGLE_INPUT_ROOT',self.work):paths,_=self.discover()
  self.assertEqual(Path(paths['N6']),d)
 def test_competition_exclusion_does_not_hide_ordinary_dataset_ambiguity(self):
  (self.work/'competitions/deep/a/b/c/d/e/f/g/h').mkdir(parents=True)
  self.copy(name='legacy-dataset');b=self.copy(name='datasets/owner/ordinary-repo/results/N6')
  (self.work/'datasets/owner/ordinary-repo/.git/refs/deep/a/b/c/d/e/f/g').mkdir(parents=True)
  report=s.read(b/'report.json');report['interpretation']='different valid ordinary Dataset';(b/'report.json').write_bytes(s.canonical(report))
  inv=s.read(b/'final-inventory.json');inv['files']['report.json']=s.file_sha(b/'report.json');(b/'final-inventory.json').write_bytes(s.canonical(inv))
  with patch.object(h,'KAGGLE_INPUT_ROOT',self.work):
   with self.assertRaises(h.InputError) as error:self.discover()
  self.assertEqual(error.exception.reason,'ambiguous-prerequisite')
 def test_unrelated_ordinary_dataset_depth_limit_still_blocks(self):
  (self.work/'ordinary-dataset/a/b/c/d/e/f/g/h/i').mkdir(parents=True)
  self.copy()
  with patch.object(h,'KAGGLE_INPUT_ROOT',self.work):
   with self.assertRaises(h.InputError) as error:self.discover()
  self.assertEqual(error.exception.reason,'prior-discovery-limit')
 def test_vcs_metadata_inside_evidence_is_not_ignored_by_integrity(self):
  d=self.copy();(d/'.git').write_text('unexpected')
  with self.assertRaises(ValueError):h.verify_candidate(s,d,'N6')
 def test_reported_depth_block_retries_without_changing_old_evidence(self):
  base=self.work/'base';old_error=h.InputError('prior-discovery-limit',{'limit':'depth','path':'/kaggle/input/competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents/.git/logs/refs/remotes/origin'})
  with patch.object(h,'discover_priors',side_effect=old_error),contextlib.redirect_stdout(io.StringIO()):first=h.launch_notebook(s,base,'N9',prior_search_roots=[self.work/'input'])
  before={str(p):s.file_sha(p) for p in base.rglob('*') if p.is_file()}
  d=self.copy();assets={}
  for role in s.EXPECTED_PINS:
   path=self.work/'assets'/role;path.mkdir(parents=True);assets[role]=str(path)
  with patch.object(s,'launch',return_value={'status':'CPU-backend-boundary'}) as launch,contextlib.redirect_stdout(io.StringIO()):
   result=h.launch_notebook(s,base,'N9',prior_results={'N6':str(d)},prior_search_roots=[self.work/'input'],explicit_roots=assets)
  self.assertEqual(result['status'],'CPU-backend-boundary');self.assertIn('attempt-0002',launch.call_args.args[0]['output_root'])
  for path,digest in before.items():self.assertEqual(s.file_sha(path),digest)
 def test_scan_limits_fail_closed(self):
  for i in range(3):(self.work/str(i)).mkdir()
  with patch.object(h,'MAX_DIRECTORIES',2):
   with self.assertRaises(h.InputError):self.discover()
 def blocked(self,base=None):
  base=base or self.work/'base'
  with contextlib.redirect_stdout(io.StringIO()):return h.launch_notebook(s,base,'N9',prior_search_roots=[self.work/'empty-input'])
 def test_missing_blocks_before_asset_scan_install_or_model(self):
  with patch.object(h,'asset_roots',side_effect=AssertionError),patch.object(s,'launch',side_effect=AssertionError):result=self.blocked()
  self.assertEqual(result['status'],'blocked');self.assertEqual(result['generate_calls'],0);self.assertEqual(result['expected_runs'],['N6'])
  self.assertEqual(result['reason'],'missing-prerequisite');s.verify_final_inventory(result['output'])
 def test_repeated_blocks_preserve_every_attempt_and_archive(self):
  first=self.blocked();before={str(p):s.file_sha(p) for p in self.work.rglob('*') if p.is_file()}
  second=self.blocked();third=self.blocked()
  self.assertIn('attempt-0002',second['output']);self.assertIn('attempt-0003',third['output'])
  for p,sha in before.items():self.assertEqual(s.file_sha(p),sha)
  receipt=s.read(Path(third['input_receipt']));self.assertEqual(len(receipt['preserved_blocked_attempts']),2)
 def test_complete_partial_or_ambiguous_attempt_never_retried(self):
  base=self.work/'base';out=base/'runs'/s.experiment_identity('N9');out.mkdir(parents=True);(out/'gate.json').write_text('{}')
  with self.assertRaises(Exception):h.allocate_output_root(s,base,'N9')
 def test_blocked_counter_bool_wrong_source_extra_data_reject_retry(self):
  for key,value in [('generate_calls',False),('generate_calls',1),('source_lock_sha256','0'*64)]:
   base=self.work/(key+str(value));result=self.blocked(base);out=Path(result['output']);r=s.read(out/'blocked.json');r[key]=value;(out/'blocked.json').write_bytes(s.canonical(r));inv=s.read(out/'final-inventory.json');inv['files']['blocked.json']=s.file_sha(out/'blocked.json');(out/'final-inventory.json').write_bytes(s.canonical(inv))
   with self.assertRaises(ValueError):h.allocate_output_root(s,base,'N9')
 def test_missing_assets_is_retryable_zero_call_block(self):
  d=self.copy();base=self.work/'base'
  with contextlib.redirect_stdout(io.StringIO()):
   result=h.launch_notebook(s,base,'N9',prior_results={'N6':str(d)},prior_search_roots=[],explicit_roots={'runtime':self.work/'missing'})
   second=h.launch_notebook(s,base,'N9',prior_results={'N6':str(d)},prior_search_roots=[],explicit_roots={'runtime':self.work/'missing'})
  self.assertEqual(result['reason'],'missing-or-invalid-asset-mount');self.assertIn('attempt-0002',second['output'])
 def test_N13_does_not_scan_priors_or_model_assets(self):
  with patch.object(h,'scan_candidates',side_effect=AssertionError),patch.object(s,'launch',return_value={'status':'CPU-boundary'}) as launch,contextlib.redirect_stdout(io.StringIO()):
   result=h.launch_notebook(s,self.work/'base','N13',prior_search_roots=[self.work/'absent'])
  self.assertEqual(result['status'],'CPU-boundary');self.assertEqual(set(launch.call_args.args[0]),{'output_root'})
 def test_N14_missing_source_BLOCKED_does_not_waive_results(self):
  b=self.blocked()
  with self.assertRaises(ValueError):h.verify_candidate(s,b['output'],'N9',True)

class ActualOwnerEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  value=os.environ.get('IRISX_ACTUAL_PRIOR_ROOT')
  if not value:raise unittest.SkipTest('Set IRISX_ACTUAL_PRIOR_ROOT for actual returned N6/N7 mounted-input acceptance')
  cls.root=Path(value);cls.pin=json.loads((ROOT/'docs/PREREQUISITE-DATASET-PIN.json').read_text())
 def test_actual_extracted_all_four_admission_gates(self):
  for run in ('N9','N10','N11','N12'):
   paths,report=h.discover_priors(s,run,search_roots=[self.root],expected_evidence=self.pin['sources'])
   self.assertEqual(s.resolve_gate(run,paths)['status'],'passed');self.assertTrue(all(x['evidence_pin_verified'] for x in report['selected'].values()))
 def test_actual_notebook_decoding_nested_inputs_to_cpu_backend_boundary(self):
  for run in ('N9','N10','N11','N12'):
   with self.subTest(run=run),tempfile.TemporaryDirectory() as td:
    td=Path(td);nb=next(json.loads(p.read_text()) for p in (ROOT/'notebooks').glob('*.ipynb') if json.loads(p.read_text())['metadata']['irisx_run_id']==run)
    ns={}
    for cell in nb['cells'][1:3]:exec(compile(''.join(cell['source']),'notebook-setup','exec'),ns)
    ns.update(MANUAL_START=True,BASE=td/'base',PRIOR_SEARCH_ROOTS=[self.root])
    for role in ns['PINS']:
     path=td/'assets'/role;path.mkdir(parents=True);ns[role.upper()+'_ROOT']=str(path)
    entry=''.join(nb['cells'][3]['source']);entry=entry.replace('    result=helper.launch_notebook','    suite.launch=lambda cfg,run_id,**kw: {"status":"verified-CPU-backend-boundary","run_id":run_id,"priors":sorted(kw["prior_paths"])}\n    result=helper.launch_notebook')
    with contextlib.redirect_stdout(io.StringIO()):exec(compile(entry,'notebook-run-CPU-boundary','exec'),ns)
    self.assertEqual(ns['result']['status'],'verified-CPU-backend-boundary');self.assertEqual(ns['result']['priors'],list(h.REQUIRED[run]))
 def test_all_six_notebooks_with_reported_competition_tree(self):
  with tempfile.TemporaryDirectory() as td:
   td=Path(td);input_root=td/'input';shutil.copytree(self.root,input_root/'datasets/danielwuu/prerequisites')
   (input_root/'competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents/.git/logs/refs/remotes/origin').mkdir(parents=True)
   for run in ('N9','N10','N11','N12','N13','N14'):
    with self.subTest(run=run):
     nb=next(json.loads(p.read_text()) for p in (ROOT/'notebooks').glob('*.ipynb') if json.loads(p.read_text())['metadata']['irisx_run_id']==run);ns={}
     for cell in nb['cells'][1:3]:exec(compile(''.join(cell['source']),'notebook-setup','exec'),ns)
     ns.update(MANUAL_START=True,BASE=td/run,PRIOR_SEARCH_ROOTS=[input_root])
     for role in ns['PINS']:
      path=td/'assets'/role;path.mkdir(parents=True,exist_ok=True);ns[role.upper()+'_ROOT']=str(path)
     entry=''.join(nb['cells'][3]['source']);entry=entry.replace('    result=helper.launch_notebook','    helper.KAGGLE_INPUT_ROOT=PRIOR_SEARCH_ROOTS[0]\n    suite.launch=lambda cfg,run_id,**kw: {"status":"verified-CPU-backend-boundary","run_id":run_id,"config_keys":sorted(cfg),"priors":sorted(kw["prior_paths"])}\n    result=helper.launch_notebook')
     with contextlib.redirect_stdout(io.StringIO()):exec(compile(entry,'notebook-run-CPU-boundary','exec'),ns)
     if run=='N14':self.assertEqual(ns['result']['reason'],'missing-consolidation-source');self.assertEqual(ns['result']['required'],'N9')
     else:self.assertEqual(ns['result']['status'],'verified-CPU-backend-boundary')
     receipt=s.read(ns['result']['input_receipt']);scan=receipt['discovery']['scan']
     if run=='N13':self.assertEqual(scan['directories'],0);self.assertEqual(ns['result']['config_keys'],['output_root'])
     else:self.assertIn(str(input_root/'competitions'),scan['excluded_paths'])
 def test_actual_N14_still_needs_three_future_results(self):
  paths,report=h.discover_priors(s,'N14',search_roots=[self.root],expected_evidence=self.pin['sources'])
  self.assertEqual(report['missing'],['N9','N10','N11']);self.assertEqual(s.resolve_gate('N14',paths)['status'],'blocked')

if __name__=='__main__':unittest.main(verbosity=2)

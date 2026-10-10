"""Real runtime8 provenance regression; no installers, model loads or GPU calls.

The two manifest fixtures are independent captured asset/historical bytes.
Full mounted-Dataset route checks run when IRISX_RUNTIME8_TEST_ROOT is supplied;
release acceptance requires these checks (an absent mount is an explicit skip).
"""
import contextlib,copy,hashlib,io,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'src';sys.path.insert(0,str(SRC))
import arc_suite as s
FIXTURE=Path(__file__).parent/'evidence/runtime8-manifest-hotfix'
OLD_LOCK='5483b47b573960c4dba64e2af95efdb1a92e19c2f9bdf652a8b45d9db45e290d'
OLD_REFERENCE='d4f6fbb693d35313f2b9be4eac50e5ac3c8340c61e6b4e77ba71de7a44ea54f8'
RUNTIME=os.environ.get('IRISX_RUNTIME8_TEST_ROOT')
RUNTIME_RUNS=('N5','N6','N7','N8','N9','N10','N11','N12','N14')

class ManifestFixtureTests(unittest.TestCase):
 def test_reference_matches_captured_pinned_asset_not_derived_fix1(self):
  bundle=FIXTURE/'runtime8-bundle-manifest.json'
  canonical=FIXTURE/'canonical-runtime8-n1-manifest.json'
  historical=FIXTURE/'historical-fix1-manifest.json'
  self.assertEqual(s.file_sha(bundle),s.RUNTIME_MANIFEST_SHA)
  entry=s.read(bundle)['files']['n1/manifest.json']
  self.assertEqual(canonical.stat().st_size,entry['bytes'])
  self.assertEqual(s.file_sha(canonical),entry['sha256'])
  self.assertEqual((SRC/'solver-manifest-reference.json').read_bytes(),canonical.read_bytes())
  self.assertEqual(s.file_sha(historical),OLD_REFERENCE)
  self.assertNotEqual(s.read(historical),s.read(canonical))
 def test_all_scientific_bindings_unchanged(self):
  old=s.read(FIXTURE/'historical-fix1-manifest.json');new=s.read(FIXTURE/'canonical-runtime8-n1-manifest.json')
  for field in ('tuning_ids','confirmation_ids','development_ids','base_manifest_sha256','adapter_binding_sha256','solutions_sha256'):
   self.assertEqual(new['core'][field],old['core'][field],field)
  self.assertEqual(new['challenge_sha256'],old['challenge_sha256'])
  self.assertEqual(len(new['challenge_sha256']),64)
  self.assertEqual(len(new['core']['confirmation_ids']),136)
  self.assertEqual(s.digest(new['core']['confirmation_ids']),s.CONFIRMATION_SHA)
  challenges=s.read(SRC/'solver-challenges-reference.json')
  self.assertEqual(set(challenges),set(new['challenge_sha256']))
  for tid,value in challenges.items():
   self.assertEqual(s.digest(s.task(value)),new['challenge_sha256'][tid],tid)
 def test_all_runtime_manifests_bind_new_revision_and_original_asset(self):
  original=s.read(FIXTURE/'canonical-runtime8-n1-manifest.json');ch=s.read(SRC/'solver-challenges-reference.json')
  for run in RUNTIME_RUNS:
   ids=original['core']['tuning_ids'][8:40] if run=='N14' else s.ENGINEERING_TASKS
   visible={tid:ch[tid] for tid in ids}
   m=s.make_manifest(run,original,visible,selected_policy='typed_ir' if run=='N14' else None)
   self.assertEqual(s.verify_manifest(m,visible),m['core'])
   self.assertEqual(m['core']['source_n1_core_sha256'],original['core_sha256'])
   self.assertEqual(m['core']['suite_revision'],s.SUITE_REVISION)
   self.assertNotEqual(m['core']['experiment_id'],'iris-x-'+run.lower()+'-20261009')
 def test_pre_revision_evidence_rejected_even_if_rehashed(self):
  original=s.read(FIXTURE/'canonical-runtime8-n1-manifest.json');ch=s.read(SRC/'solver-challenges-reference.json');visible={t:ch[t] for t in s.ENGINEERING_TASKS}
  m=s.make_manifest('N6',original,visible);m['core']['source_lock_sha256']=OLD_LOCK
  m['core_sha256']=s.digest(m['core']);m['records']=s.identities(m['core'])
  with self.assertRaisesRegex(ValueError,'source/design'):s.verify_manifest(m,visible)
 def test_all_notebook_base_directories_have_new_revision(self):
  for path in (ROOT/'notebooks').glob('*.ipynb'):
   nb=json.loads(path.read_text());self.assertEqual(nb['metadata']['irisx_suite_revision'],s.SUITE_REVISION)
   config=''.join(nb['cells'][1]['source'])
   self.assertIn('iris-nextphase-'+nb['metadata']['irisx_run_id'].lower()+'-'+s.SUITE_REVISION,config)
   self.assertIn('MANUAL_START = False',config)

@unittest.skipUnless(RUNTIME,'Requires actual pinned runtime8 mount; required at repair release')
class MountedRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.runtime=Path(RUNTIME).resolve();cls.original,cls.challenges=s.load_runtime_inputs(cls.runtime)
  if (cls.runtime/'n1/manifest.json').read_bytes()!=(FIXTURE/'canonical-runtime8-n1-manifest.json').read_bytes():
   raise AssertionError('External runtime mount does not match captured fixture')
 def test_real_runtime_boundary_verifies_complete_closed_inventory(self):
  original,challenges=s.load_runtime_inputs(self.runtime)
  self.assertEqual(original,s.read(SRC/'solver-manifest-reference.json'))
  self.assertEqual(challenges,s.read(SRC/'solver-challenges-reference.json'))
 def test_derived_reference_reproduces_identity_failure_without_install(self):
  old=s.read(FIXTURE/'historical-fix1-manifest.json');read=s.read
  def historical_reference(path):
   return copy.deepcopy(old) if Path(path)==SRC/'solver-manifest-reference.json' else read(path)
  with patch.object(s,'read',side_effect=historical_reference),patch.object(s,'_validate_config',side_effect=AssertionError('must not prepare model')):
   with self.assertRaisesRegex(ValueError,'Source N1 manifest identity differs'):s.load_runtime_inputs(self.runtime)
 def test_rehashed_reference_mutation_is_not_accepted(self):
  bad=copy.deepcopy(self.original);bad['core']['experiment_id']+='-tampered';read=s.read
  def altered_reference(path):return bad if Path(path)==SRC/'solver-manifest-reference.json' else read(path)
  with patch.object(s,'read',side_effect=altered_reference):
   with self.assertRaisesRegex(ValueError,'Source N1 manifest identity differs'):s.load_runtime_inputs(self.runtime)
 def test_all_nine_launch_paths_cross_real_boundary_before_install(self):
  class BoundaryReached(Exception):pass
  actual=s.load_runtime_inputs;calls=[]
  def stop_after_verified_boundary(path):
   result=actual(path);calls.append(result[0]['core_sha256']);raise BoundaryReached
  for run in RUNTIME_RUNS:
   with self.subTest(run=run),tempfile.TemporaryDirectory() as td:
    gate={'status':'passed','receipts':[],'selected_policy':'typed_ir'}
    with patch.object(s,'resolve_gate',return_value=gate),patch.object(s,'load_runtime_inputs',side_effect=stop_after_verified_boundary),patch.object(s,'_validate_config',side_effect=AssertionError('no installer/model permitted')):
     with self.assertRaises(BoundaryReached):s.launch({'runtime_root':str(self.runtime),'output_root':td},run,enabled=True)
    self.assertTrue((Path(td)/s.experiment_identity(run)/'gate.json').is_file())
    self.assertFalse((Path(td)/('iris-x-'+run.lower()+'-20261009')).exists())
  self.assertEqual(len(calls),9)
 def test_n13_bypasses_runtime_boundary(self):
  # Test discovery imports the compiler ordinarily in another module. The
  # notebook correctly rejects such an unverified module object; use a fresh
  # process, just like its source-verified notebook bootstrap, for this check.
  code="""
import contextlib,io,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1]);import arc_suite as s
curriculum=s.component('arc_curriculum')
with tempfile.TemporaryDirectory() as td,patch.object(s,'load_runtime_inputs',side_effect=AssertionError('N13 must not read runtime')),patch.object(curriculum,'make_curriculum',return_value={'test_fixture_only':True}),contextlib.redirect_stdout(io.StringIO()):
 result=s.launch({'output_root':td},'N13',enabled=True)
 assert result['model_calls']==0 and result['training_performed'] is False
 assert s.read(Path(result['output'])/'run-identity.json')['suite_revision']==s.SUITE_REVISION
"""
  result=subprocess.run([sys.executable,'-I','-B','-c',code,str(SRC)],capture_output=True,text=True,timeout=20)
  self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main(verbosity=2)

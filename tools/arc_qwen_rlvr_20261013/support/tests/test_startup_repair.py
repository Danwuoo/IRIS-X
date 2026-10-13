"""Focused synthetic CPU proofs; no provider, model, driver or installer execution."""
from pathlib import Path
import contextlib, hashlib, json, os, shutil, sys, tempfile, time, types, unittest, zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT.parent/'portfolio63-rl-environment-repair-20261013'
sys.dont_write_bytecode=True

def source_module(name,path):
    m=types.ModuleType(name);m.__file__=str(path);m.__package__='';sys.modules[name]=m
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(m));return m

launch=source_module('startup_test_launch',ROOT/'deployment/launch_notebook.py')
guard=source_module('startup_test_guard',RUNTIME/'baseline/tools/arc_learning_agent_20261011/process_guard.py')

class StopBeforeWork(RuntimeError):pass

class OwnedSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.stage=self.root/'stage'
    def tearDown(self):self.tmp.cleanup()
    def run_child(self,code='print("fixture-ok")',**kw):
        return launch.run_bounded([sys.executable,'-I','-B','-c',code],guard_module=guard,directory=self.stage,
            deadline_epoch=time.time()+60,env={'PATH':os.defpath,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'},scope='synthetic-CPU-startup-repair',
            failure_context={'original_epoch':1234567890,'source_sha256':'a'*64,'request_sha256':'b'*64},**kw)
    def diag(self):return json.loads((self.stage/'startup-failure.json').read_bytes())
    def check_real_closed(self):
        proof=json.loads((self.stage/'owned-tree/closure.json').read_bytes());guard.verify_closed_proof(proof)
        self.assertTrue(proof['closed']);self.assertFalse(proof['remaining']);return proof
    def test_actual_success(self):
        d=self.run_child();self.assertEqual(d['proof'],self.check_real_closed());self.assertEqual(d['proof']['worker_returncode'],0)
        self.assertFalse((self.stage/'startup-failure.json').exists())
    def test_actual_clean_nonzero_is_not_operational_success(self):
        with self.assertRaises(RuntimeError):self.run_child('raise SystemExit(7)')
        p=self.check_real_closed();self.assertEqual(p['worker_returncode'],7);d=self.diag();self.assertEqual(d['stage'],'owned-result')
        self.assertTrue(d['clean_owned_closure_verified']);self.assertFalse(d['operational_success'])
    def test_selector_constructor_failure_closes_real_child(self):
        with patch.object(launch.selectors,'DefaultSelector',side_effect=OSError('synthetic private detail')):
            with self.assertRaises(OSError):self.run_child('import time; time.sleep(45)')
        self.check_real_closed();d=self.diag();self.assertEqual(d['stage'],'selector-setup');self.assertTrue(d['proof_verified'])
        self.assertFalse(d['clean_owned_closure_verified']);self.assertNotIn('private detail',json.dumps(d))
    def test_selector_registration_failure_closes_real_child(self):
        original=launch.selectors.DefaultSelector
        class Broken:
            def __init__(self):self.inner=original()
            def register(self,*a,**kw):raise OSError('synthetic register failure')
            def close(self):self.inner.close()
        with patch.object(launch.selectors,'DefaultSelector',Broken):
            with self.assertRaises(OSError):self.run_child('import time; time.sleep(45)')
        self.check_real_closed();self.assertEqual(self.diag()['stage'],'selector-setup')
    def test_set_blocking_failure_closes_real_child(self):
        with patch.object(launch.os,'set_blocking',side_effect=OSError('synthetic nonblock failure')):
            with self.assertRaises(OSError):self.run_child('import time; time.sleep(45)')
        self.check_real_closed();self.assertEqual(self.diag()['stage'],'selector-setup')
    def test_cleanup_retry_closes_acquired_child_after_first_stop_fault(self):
        original=guard.OwnedProcessGuard.stop;calls=[]
        def stop(instance,*a,**kw):
            calls.append(True)
            if len(calls)==1:raise OSError('synthetic first cleanup failure')
            return original(instance,*a,**kw)
        with patch.object(launch.selectors,'DefaultSelector',side_effect=OSError('synthetic setup fault')),patch.object(guard.OwnedProcessGuard,'stop',stop):
            with self.assertRaisesRegex(OSError,'setup fault'):self.run_child('import time; time.sleep(45)')
        self.assertEqual(len(calls),2);self.check_real_closed();self.assertTrue(self.diag()['proof_verified'])

    def test_pre_return_spawn_failure_stays_unknown(self):
        with patch.object(guard.OwnedProcessGuard,'spawn',side_effect=OSError('synthetic spawn failure; no process created by fixture')):
            with self.assertRaises(OSError):self.run_child()
        d=self.diag();self.assertEqual(d['dispatch_state'],'unknown-spawn-may-not-have-returned')
        self.assertFalse(d['proof_available']);self.assertFalse(d['clean_owned_closure_verified']);self.assertFalse((self.stage/'closure.json').exists())
    def test_expired_budget_records_not_dispatched(self):
        with self.assertRaisesRegex(ValueError,'reserve'):
            launch.run_bounded([sys.executable],guard_module=guard,directory=self.stage,deadline_epoch=time.time()-1,env={},scope='fixture')
        self.assertEqual(self.diag()['dispatch_state'],'not-dispatched');self.assertFalse((self.stage/'owned-tree').exists())
    def test_log_open_failure_records_not_dispatched(self):
        original=Path.open
        def opening(path,*args,**kwargs):
            if path==self.stage/'stderr.txt':raise OSError('synthetic log failure')
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',opening):
            with self.assertRaises(OSError):self.run_child()
        self.assertEqual(self.diag()['stage'],'log-open');self.assertEqual(self.diag()['dispatch_state'],'not-dispatched')
    def test_proof_verification_failure_never_claims_clean(self):
        with patch.object(guard,'verify_closed_proof',side_effect=ValueError('synthetic proof rejection')):
            with self.assertRaises(ValueError):self.run_child()
        self.check_real_closed();d=self.diag();self.assertFalse(d['proof_verified']);self.assertFalse(d['clean_owned_closure_verified'])
    def test_diagnostic_is_bounded_redacted_and_one_use(self):
        self.stage.mkdir();error=ValueError('SYNTHETIC_SECRET='+('x'*200000))
        self.assertTrue(launch.persist_failure(self.stage,stage='fixture',error=error,context={},dispatch_state='not-dispatched'))
        raw=(self.stage/'startup-failure.json').read_bytes();self.assertLess(len(raw),launch.FAILURE_BYTES);self.assertNotIn(b'SYNTHETIC_SECRET',raw)
        self.assertFalse(launch.persist_failure(self.stage,stage='replacement',error=error,context={},dispatch_state='not-dispatched'))
        self.assertEqual(raw,(self.stage/'startup-failure.json').read_bytes())
    def test_diagnostic_symlink_rejected(self):
        real=self.root/'real';real.mkdir();self.stage.symlink_to(real,target_is_directory=True)
        self.assertFalse(launch.persist_failure(self.stage,stage='fixture',error=ValueError(),context={},dispatch_state='not-dispatched'))
        self.assertFalse(list(real.iterdir()))

class ActualPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.base=Path(cls.tmp.name);cls.source=cls.base/'source/runtime'
        cls.source.mkdir(parents=True)
        with zipfile.ZipFile(RUNTIME/'RELEASE-SOURCE.zip') as archive:
            for name in archive.namelist():
                path=cls.source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(name))
        # Use only the complete producer inventory directories and policy files.
        source_module('prefix_loader',ROOT/'deployment/source_loader.py').source_import_paths(cls.source)
        import owned_runtime.release as release
        cls.runtime_release=release;cls.source_sha=release.source_digest(release.inventory())
        (cls.source.parent/'release').mkdir();shutil.copyfile(ROOT/'environment-candidate/REVIEWED-ENVIRONMENT-CANDIDATE.json',cls.source.parent/'release/REVIEWED-ENVIRONMENT.json')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.tmp2=tempfile.TemporaryDirectory(dir=self.base);self.work=Path(self.tmp2.name);self.output=self.work/'run'
        self.ready={'source_root':str(self.source),'source_sha256':self.source_sha}
        old=ROOT.parent/'portfolio63-rl-release-20261012/release-candidate-001/notebook-release.json'
        self.release=json.loads(old.read_bytes());self.release.update(release_role='rlvr002',source_sha256=self.source_sha,environment_sha256=hashlib.sha256((ROOT/'environment-candidate/REVIEWED-ENVIRONMENT-CANDIDATE.json').read_bytes()).hexdigest())
        self.epoch=int(time.time());self.finalized={'owner_request':{'original_epoch':self.epoch},'operator':{}}
        original=launch.load_file
        def load(name,path):
            module=original(name,path)
            if name=='rlvr_checked_builder':module.OUTPUT=str(self.output);module.SOURCE=str(self.source.parent)
            return module
        self.load=load
    def tearDown(self):self.tmp2.cleanup()
    def invoke(self):return launch.launch(ready=self.ready,release=self.release,finalized=self.finalized,loader_source=(ROOT/'deployment/source_loader.py').read_text(),output_root=str(self.output),input_root=str(self.work/'inputs'),epoch=self.epoch)
    def diagnostic(self):return json.loads(Path(str(self.output)+'-launcher/startup-failure.json').read_bytes())
    def test_real_prefix_ignores_unsupported_ambient_loader(self):
        seen={}
        def stop(argv,**kwargs):seen.update(kwargs);raise StopBeforeWork('synthetic stop before any preparation process')
        with patch.object(launch,'load_file',self.load),patch.object(launch,'run_bounded',stop),patch.dict(os.environ,{'LD_LIBRARY_PATH':'/synthetic/untrusted::/synthetic/untrusted','CUDA_VISIBLE_DEVICES':'0'},clear=True):
            with self.assertRaises(StopBeforeWork):self.invoke()
        from owned_runtime.parent_scoring import TRUSTED_DRIVER_LIBRARY_DIRECTORIES
        self.assertEqual(seen['env']['LD_LIBRARY_PATH'],':'.join(TRUSTED_DRIVER_LIBRARY_DIRECTORIES))
        self.assertEqual(seen['failure_context']['source_sha256'],self.source_sha)
        self.assertEqual(self.diagnostic()['stage'],'owned-preparation')
        self.assertFalse(any(x in sys.modules for x in ('torch','transformers','peft')))
    def test_actual_device_policy_failure_persists_prefix_evidence(self):
        with patch.object(launch,'load_file',self.load),patch.dict(os.environ,{'CUDA_DEVICE_ORDER':'SYNTHETIC_PRIVATE_VALUE'},clear=True):
            with self.assertRaisesRegex(ValueError,'device ordering'):self.invoke()
        d=self.diagnostic();self.assertEqual(d['stage'],'parent-environment-policy');self.assertEqual(d['dispatch_state'],'not-dispatched')
        self.assertEqual(d['source_sha256'],self.source_sha);self.assertEqual(len(d['request_sha256']),64)
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE',json.dumps(d));self.assertFalse(d['clean_owned_closure_verified'])
    def test_guard_import_failure_has_durable_evidence(self):
        def fail(name,path):
            if name=='rlvr_outer_guard':raise ImportError('synthetic private import detail')
            return self.load(name,path)
        with patch.object(launch,'load_file',fail):
            with self.assertRaises(ImportError):self.invoke()
        self.assertEqual(self.diagnostic()['stage'],'source-guard-import')
    def test_cache_failure_has_durable_evidence(self):
        cache=self.source/'__pycache__';cache.mkdir()
        try:
            with patch.object(launch,'load_file',self.load):
                with self.assertRaisesRegex(ValueError,'bytecode cache'):self.invoke()
        finally:cache.rmdir()
        self.assertEqual(self.diagnostic()['stage'],'source-import-policy')
    def preparation_authentication_negative(self,relative,missing=False):
        prepare=source_module('negative_prepare',ROOT/'deployment/prepare_entry.py')
        path=self.source/relative;raw=path.read_bytes()
        try:
            if missing:path.unlink()
            else:path.write_bytes(raw+b'\n')
            with self.assertRaises((ValueError,FileNotFoundError)):prepare.authenticate_preinstall_source(self.ready,self.release)
        finally:path.write_bytes(raw)
    def test_changed_source_rejected_preinstall(self):self.preparation_authentication_negative('owned_runtime/parent_scoring.py')
    def test_missing_source_rejected_preinstall(self):self.preparation_authentication_negative('owned_runtime/parent_scoring.py',True)
    def test_changed_policy_rejected_preinstall(self):self.preparation_authentication_negative('design/MEASURED-POLICY.json')
    def test_missing_policy_rejected_preinstall(self):self.preparation_authentication_negative('design/MEASURED-POLICY.json',True)
    def test_changed_environment_rejected_preinstall(self):self.preparation_authentication_negative('../release/REVIEWED-ENVIRONMENT.json')
    def test_missing_environment_rejected_preinstall(self):self.preparation_authentication_negative('../release/REVIEWED-ENVIRONMENT.json',True)
    def test_normalized_pin_rejected_preinstall(self):
        prepare=source_module('negative_pin_prepare',ROOT/'deployment/prepare_entry.py')
        with patch.object(self.runtime_release,'NORMALIZED_SOURCE_CONTRACT_SHA256','0'*64):
            with self.assertRaisesRegex(ValueError,'normalized'):prepare.authenticate_preinstall_source(self.ready,self.release)

    def test_actual_preparation_prefix_verifies_final_pins_before_materials(self):
        prepare=source_module('prefix_prepare',ROOT/'deployment/prepare_entry.py')
        import tools.arc_qwen_transfer_deployment_20261012.bootstrap as bootstrap
        request={'format':'irisx/rlvr-parent-preparation-request-v1','ready':self.ready,'release':self.release,'epoch':self.epoch,
                 'finalized':self.finalized,'input_root':str(self.work/'inputs')}
        with patch.object(bootstrap,'resolve_datasets',side_effect=StopBeforeWork('synthetic stop at material resolution')):
            with self.assertRaises(StopBeforeWork):prepare.prepare(request)
        self.assertFalse(any(x in sys.modules for x in ('torch','transformers','peft')))

if __name__=='__main__':unittest.main()

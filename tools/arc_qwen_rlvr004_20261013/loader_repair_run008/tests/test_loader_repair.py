"""Real Linux ELF/subprocess proof of loader policy; no model, GPU or evaluator use."""
from contextlib import ExitStack
from pathlib import Path
import ast, hashlib, importlib, importlib.util, json, os, shutil, subprocess, sys, tempfile, time, unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent
REPO=PACKAGE.parents[2]
BASE=Path(os.environ.get('IRISX_RUN007_SOURCE_ROOT',str(REPO/'.irisx/transfer-verification-20261013/rebuild-offline-2/source-rebuild/producer-source'))).resolve()
OVERLAYS=PACKAGE/'overlays'
SCRATCH=RUNTIME=E=P=FIXTURE=None


def setUpModule():
    global SCRATCH,RUNTIME,E,P,FIXTURE
    sys.dont_write_bytecode=True
    manifest=json.loads((PACKAGE/'OVERLAY-MANIFEST.json').read_text())
    for target,row in manifest['files'].items():
        if hashlib.sha256((BASE/target).read_bytes()).hexdigest()!=row['original_sha256']:
            raise ValueError('authenticated base overlay target differs: '+target)
        raw=(PACKAGE/row['path']).read_bytes()
        if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('exact overlay manifest differs: '+target)
    SCRATCH=tempfile.TemporaryDirectory(prefix='run008-loader-')
    RUNTIME=Path(SCRATCH.name)/'runtime';shutil.copytree(BASE,RUNTIME)
    shutil.copytree(OVERLAYS,RUNTIME,dirs_exist_ok=True)
    sys.path.insert(0,str(RUNTIME))
    E=importlib.import_module('owned_runtime.environment_v2')
    P=importlib.import_module('owned_runtime.parent_scoring')
    spec=importlib.util.spec_from_file_location('run008_elf_fixture',HERE/'elf_fixture.py')
    FIXTURE=importlib.util.module_from_spec(spec);spec.loader.exec_module(FIXTURE)


def tearDownModule():
    if SCRATCH:SCRATCH.cleanup()


@unittest.skipUnless(sys.platform=='linux' and shutil.which('gcc'),'real ELF tests require Linux and gcc')
class ELFTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='elf-',dir=SCRATCH.name)
        self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def run_case(self,case,*,needed=False,mutate=None):
        config,data=FIXTURE.build(self.root,RUNTIME,needed=needed)
        with FIXTURE.settings(data):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
            env=P.worker_environment(fixture=False)
        if mutate:mutate(data)
        if case in ('historical','late_env'):env['LD_LIBRARY_PATH']=data['system']
        if case=='system_first':env['LD_LIBRARY_PATH']=data['system']+':'+data['lib']
        if case=='child_path_changed':env['LD_LIBRARY_PATH']=data['system']
        if case=='child_env_injection':env['PYTHONPATH']='/synthetic/foreign'
        args=[sys.executable,'-I','-B']+(['-O'] if sys.flags.optimize else [])+[str(HERE/'elf_fixture.py'),str(config),case]
        result=subprocess.run(args,env=env,cwd=RUNTIME,capture_output=True,text=True,timeout=25,check=True)
        row=json.loads(result.stdout);self.assertTrue(row['fixture_only']);return row
    def test_historical_owned_shim_system_backend_mismatch(self):
        row=self.run_case('historical');self.assertFalse(row['accepted']);self.assertEqual(row['api'],90800)
        self.assertIn('exact pinned wheel',row['error']['message'])
    def test_system_first_even_with_vendor_root_reproduces_mismatch(self):
        row=self.run_case('system_first');self.assertFalse(row['accepted']);self.assertEqual(row['api'],90800)
    def test_inprocess_environment_update_is_too_late(self):
        row=self.run_case('late_env');self.assertFalse(row['accepted']);self.assertEqual(row['api'],90800)
    def test_owned_first_before_exec_selects_owned_deferred_backend(self):
        row=self.run_case('repaired');self.assertTrue(row['accepted']);self.assertEqual(row['api'],91002)
        self.assertTrue(all(r['location']=='owned-installed' for r in row['observation']['verified_mappings']))
        self.assertEqual(len(row['observation']['verified_libraries']),3)
    def test_owned_first_before_exec_selects_owned_dt_needed_backend(self):
        row=self.run_case('repaired',needed=True);self.assertTrue(row['accepted']);self.assertEqual(row['api'],91002)
    def test_system_dt_needed_backend_reproduces_mismatch(self):
        row=self.run_case('historical',needed=True);self.assertFalse(row['accepted']);self.assertEqual(row['api'],90800)
    def test_already_loaded_foreign_soname_is_reused_then_rejected(self):
        row=self.run_case('preloaded_foreign');self.assertFalse(row['accepted']);self.assertEqual(row['api'],90800)
        self.assertIn('exact pinned wheel',row['error']['message'])
    def test_parent_preloaded_backend_does_not_survive_exec(self):
        row=self.run_case('parent_preloaded');self.assertTrue(row['accepted']);self.assertEqual(row['api'],91002)
    def test_child_tamper_rejected_before_native_load(self):
        def tamper(data):
            with (Path(data['lib'])/'libcudnn_ops.so.9').open('ab') as stream:stream.write(b'tampered')
        row=self.run_case('child_tampered',mutate=tamper)
        self.assertFalse(row['accepted']);self.assertEqual(row['stage'],'child-startup');self.assertIsNone(row['api'])
    def test_child_path_replacement_rejected_before_native_load(self):
        row=self.run_case('child_path_changed');self.assertFalse(row['accepted']);self.assertEqual(row['stage'],'child-startup')
        self.assertIn('authenticated loader policy',row['error']['message'])
    def test_child_environment_injection_rejected_before_native_load(self):
        row=self.run_case('child_env_injection');self.assertFalse(row['accepted']);self.assertEqual(row['stage'],'child-startup')
        self.assertEqual(row['native_modules_imported'],[])
    def test_parent_environment_injections_are_not_forwarded(self):
        _,data=FIXTURE.build(self.root,RUNTIME)
        with FIXTURE.settings(data),patch.dict(os.environ,{'LD_LIBRARY_PATH':'/foreign','LD_PRELOAD':'/foreign.so',
                'LD_AUDIT':'/foreign.so','PYTHONPATH':'/foreign','KAGGLE_TOKEN':'SYNTHETIC','CUDA_VISIBLE_DEVICES':'0'},clear=True):
            env=P.worker_environment(fixture=False)
        self.assertEqual(env['LD_LIBRARY_PATH'],data['lib']+':'+data['system'])
        self.assertFalse(set(env)&{'LD_PRELOAD','LD_AUDIT','PYTHONPATH','KAGGLE_TOKEN'})
    def test_expired_and_invalid_deadlines_fail_before_installation_io(self):
        _,data=FIXTURE.build(self.root,RUNTIME)
        for deadline in (True,float('nan'),float('inf'),time.monotonic()-1):
            with self.subTest(deadline=deadline),FIXTURE.settings(data),patch.object(E,'_regular') as read:
                with self.assertRaises(ValueError):E.verify_cudnn_installation(data['model'],deadline=deadline,diagnostic={})
                read.assert_not_called()
    def test_wrong_distribution_version_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME)
        with FIXTURE.settings(data):
            E.importlib.metadata.distribution(data['policy']['distribution']).version='9.8.0'
            with self.assertRaisesRegex(ValueError,'exact installed'):
                E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_installed_library_outside_owned_prefix_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME)
        with FIXTURE.settings(data),patch.object(E.sys,'prefix',str(self.root/'other-prefix')):
            with self.assertRaisesRegex(ValueError,'actual owned interpreter prefix'):
                E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_nonlibrary_vendor_member_tamper_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME);(Path(data['lib'])/'__init__.py').write_text('tampered')
        with FIXTURE.settings(data),self.assertRaises(ValueError):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_missing_vendor_root_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME);shutil.rmtree(data['lib'])
        with FIXTURE.settings(data),self.assertRaises(FileNotFoundError):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_extra_vendor_member_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME);(Path(data['lib'])/'libcudnn_unknown.so.9').write_bytes(b'unknown')
        with FIXTURE.settings(data),self.assertRaisesRegex(ValueError,'inventory differs'):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_missing_vendor_member_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME);(Path(data['lib'])/'libcudnn_ops.so.9').unlink()
        with FIXTURE.settings(data),self.assertRaisesRegex(ValueError,'inventory differs'):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_symlink_vendor_root_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME);lib=Path(data['lib']);moved=lib.with_name('actual');lib.rename(moved);lib.symlink_to(moved)
        with FIXTURE.settings(data),self.assertRaisesRegex(ValueError,'no-link'):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_unpinned_shadow_library_fails_before_root_is_used(self):
        _,data=FIXTURE.build(self.root,RUNTIME);(Path(data['lib'])/'libcuda.so.1').write_bytes(b'shadow')
        with FIXTURE.settings(data),self.assertRaisesRegex(ValueError,'unpinned search entries'):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_hardware_capability_subdirectory_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME);(Path(data['lib'])/'glibc-hwcaps').mkdir()
        with FIXTURE.settings(data),self.assertRaisesRegex(ValueError,'unpinned search entries'):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_ordinary_python_cache_directory_is_allowed(self):
        _,data=FIXTURE.build(self.root,RUNTIME);(Path(data['lib'])/'__pycache__').mkdir()
        with FIXTURE.settings(data):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_wheel_tamper_fails_closed(self):
        _,data=FIXTURE.build(self.root,RUNTIME);wheel=Path(data['model']['wheel_root_path'])/'wheels'/data['policy']['wheel_name']
        with wheel.open('ab') as stream:stream.write(b'x')
        with FIXTURE.settings(data),self.assertRaises(ValueError):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})
    def test_path_separator_vendor_root_fails_closed(self):
        bad=self.root/'bad:root';bad.mkdir();_,data=FIXTURE.build(bad,RUNTIME)
        with FIXTURE.settings(data),self.assertRaisesRegex(ValueError,'unambiguous'):
            E.verify_cudnn_installation(data['model'],deadline=time.monotonic()+15,diagnostic={})


class SourceDeltaTests(unittest.TestCase):
    def test_source_policy_pin_and_mapping_abi_verifier_unchanged(self):
        old=ast.parse((BASE/'owned_runtime/environment_v2.py').read_bytes())
        new=ast.parse((OVERLAYS/'owned_runtime/environment_v2.py').read_bytes())
        ignored={'_observe_cudnn','verify_cudnn_installation','installed_cudnn_library'}
        extract=lambda tree:{node.name:ast.dump(node,include_attributes=False) for node in tree.body
                             if isinstance(node,ast.FunctionDef) and node.name not in ignored}
        self.assertEqual(extract(old),extract(new))
        constants=lambda tree:[ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.Assign)]
        self.assertEqual(constants(old),constants(new))
    def test_post_import_api_and_mapping_admission_suffix_is_byte_identical(self):
        marker="    diagnostic['stage']='observe-current-api';import torch"
        old=(BASE/'owned_runtime/environment_v2.py').read_text().split(marker,1)[1]
        new=(OVERLAYS/'owned_runtime/environment_v2.py').read_text().split(marker,1)[1]
        self.assertEqual(old,new)
    def test_four_runtime_files_only(self):
        self.assertEqual({p.relative_to(OVERLAYS).as_posix() for p in OVERLAYS.rglob('*.py')},
            {'owned_runtime/'+name+'.py' for name in ('environment_v2','parent_scoring','runner','worker')})
    def test_child_verifies_before_native_imports(self):
        source=(OVERLAYS/'owned_runtime/worker.py').read_text()
        self.assertLess(source.index('verify_child_loader_environment(request'),source.index('from owned_runtime.factory'))
        self.assertLess(source.index('verify_child_loader_environment(request'),source.index('    import torch'))
    def test_parent_verifies_before_launch(self):
        source=(OVERLAYS/'owned_runtime/runner.py').read_text()
        self.assertLess(source.index('verify_cudnn_installation(config'),source.index('worker_env=worker_environment'))
        self.assertLess(source.index('worker_env=worker_environment'),source.index('launch=register_launch'))
    def test_fixture_environment_unchanged(self):
        original=BASE/'owned_runtime/parent_scoring.py'
        spec=importlib.util.spec_from_file_location('owned_runtime.original_parent',original)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.worker_environment(fixture=True),P.worker_environment(fixture=True))
    def test_driver_roots_unchanged(self):
        self.assertEqual(E.ALIAS_DIRECTORIES,P.TRUSTED_DRIVER_LIBRARY_DIRECTORIES)
        self.assertEqual(P.TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES,('/usr/local/nvidia/bin','/bin','/usr/bin','/opt/bin'))


class SupervisorTests(unittest.TestCase):
    def run_supervisor(self,*,expired=False):
        from owned_runtime.clock import OriginalClock
        from owned_runtime.ledger import Limits
        from owned_runtime.supervisor import run_supervised
        worker=RUNTIME/'owned_tests/test_ledger_supervisor.py';worker.parent.mkdir(exist_ok=True)
        worker.write_text('import time\ntime.sleep(20)\n')
        clock=OriginalClock.create(time.time()-42000+(-1 if expired else 30),'loader-cpu-timeout',fixture=True)
        root=Path(SCRATCH.name)/('deadline' if expired else 'timeout');root.mkdir()
        return run_supervised([sys.executable,'-I','-B',str(worker)],cwd=RUNTIME,output=root,
            journal_path=root/'journal.jsonl',auth_key=b'c'*32,clock=clock,fixture=True,
            limits=Limits(load_soft=.1,load_hard=.2),poll_seconds=.01,env=P.worker_environment(fixture=True))
    def test_expired_original_deadline_prevents_child_spawn(self):
        with patch('subprocess.Popen') as spawn,self.assertRaisesRegex(TimeoutError,'before spawn'):
            self.run_supervisor(expired=True)
        spawn.assert_not_called()
    def test_real_stalled_child_is_killed_reaped_and_never_mints_closure(self):
        result=self.run_supervisor();row=result.receipt
        self.assertEqual(row['hard_stop']['reason'],'worker-startup-hard-deadline')
        self.assertTrue(row['worker_exited']);self.assertTrue(row['worker_session_empty'])
        self.assertFalse(row['safe_closure']);self.assertFalse(row['model_stopped']);self.assertIsNone(result.capability)
        self.assertIn('SIGTERM-process-group',row['termination_actions'])
        self.assertLess(row['exit_observed_monotonic']-row['started_monotonic'],3)


if __name__=='__main__':unittest.main()

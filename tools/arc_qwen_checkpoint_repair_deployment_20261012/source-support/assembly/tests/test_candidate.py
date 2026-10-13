"""Actual candidate notebook/source admission tests. No model imports or real task bytes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent
CANDIDATE = Path(os.environ.get('QWEN_CANDIDATE', HERE.parents[1]/'release-candidate-001'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def notebook_scope():
    notebook = json.loads((CANDIDATE/'iris-x-qwen14b-transfer-inactive.ipynb').read_bytes())
    scope = {}
    for cell in notebook['cells'][1:3]:
        exec(compile(''.join(cell['source']), '<actual-candidate-notebook>', 'exec'), scope)
    return notebook, scope


class ActualNotebookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='portfolio-notebook-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.notebook, self.scope = notebook_scope()
        self.scope['PINS'] = copy.deepcopy(self.scope['PINS'])
        self.scope['PINS']['release']['runtime_reviewed'] = True  # Explicit no-model launch fixture only.

    def config(self, **changes):
        value = {'manual_start': True, 'enable_model': True, 'profile': 'QWEN14B_TRANSFER12H',
                 'session_seconds': 43200, 'probe_seconds': 43200, 'predispatch_epoch': self.scope['time'].time(),
                 'execution_cutoff_seconds':42000,'outer_cutoff_seconds':42180,'provider_runtime_seconds':42300,
                 'output_root': str(self.root/'output'), 'source_parent': str(self.root/'source'),
                 'input_root': str(self.root/'inputs'), 'code_root': None, 'data_root': None, 'training_root': None}
        value.update(changes)
        return value

    def launch(self, config):
        return self.scope['launch_reviewed_qwen_notebook'](pins=self.scope['PINS'], config=config,
            loader_source=self.scope['LOADER_SOURCE'], guard_source=self.scope['GUARD_SOURCE'],
            expected_loader_sha256=self.scope['EXPECTED_LOADER_SHA256'], expected_guard_sha256=self.scope['EXPECTED_GUARD_SHA256'])

    def fake_run(self, *args, **kwargs):
        (kwargs['launcher_root']/'result.json').write_text(json.dumps({'status': 'TRANSFER_COMPLETE'}))
        return {'closed': True, 'fixture_only': True}

    def test_actual_default_notebook_is_inert(self):
        scope = {}
        with patch('builtins.open', side_effect=AssertionError('inert open')), patch.object(Path, 'read_bytes', side_effect=AssertionError('inert read')), patch.object(Path, 'mkdir', side_effect=AssertionError('inert mkdir')):
            for cell in self.notebook['cells']:
                if cell['cell_type'] == 'code':
                    exec(compile(''.join(cell['source']), '<actual-inert-notebook>', 'exec'), scope)
        self.assertEqual(scope['RESULT']['status'], 'DISABLED')
        self.assertFalse(scope['RESULT']['gpu_executed'])

    def test_actual_embedded_sources_match_closed_payload(self):
        with zipfile.ZipFile(CANDIDATE/'code-payload/source.zip') as archive:
            for name, key in [('tools/arc_qwen_transfer_deployment_20261012/source_loader.py', 'LOADER_SOURCE'),
                              ('tools/arc_qwen_transfer_deployment_20261012/preloader.py', 'PRELOADER_SOURCE'),
                              ('tools/arc_learning_agent_20261011/process_guard.py', 'GUARD_SOURCE')]:
                self.assertEqual(archive.read(name), self.scope[key].encode())

    def test_missing_epoch_denied_without_writes(self):
        with self.assertRaisesRegex(ValueError, 'finite predispatch epoch'):
            self.launch(self.config(predispatch_epoch=None))
        self.assertFalse((self.root/'output-launcher').exists())

    def test_source_review_only_pin_denies_even_finite_epoch(self):
        self.scope['PINS']['release']['runtime_reviewed'] = False
        with self.assertRaisesRegex(ValueError, 'preview cannot dispatch'):
            self.launch(self.config())
        self.assertFalse((self.root/'output-launcher').exists())

    def test_active_template_has_one_epoch_placeholder_and_no_fallback(self):
        notebook = json.loads((CANDIDATE/'iris-x-qwen14b-transfer-active-template.ipynb').read_bytes())
        code = ''.join(notebook['cells'][1]['source'])
        self.assertEqual(code.count('PREDISPATCH_EPOCH = None'), 1)
        self.assertIn('MANUAL_START = True', code)
        self.assertIn('ENABLE_MODEL = True', code)
        self.assertNotIn('\n        epoch=time.time()', self.scope['PRELOADER_SOURCE'])

    def test_explicit_epoch_is_not_refreshed(self):
        with patch.dict(self.scope, {'_load_guard': lambda *a: object(), '_run_owned': self.fake_run}), patch.object(self.scope['time'], 'time', return_value=2000000100):
            self.launch(self.config(predispatch_epoch=2000000000))
        request = json.loads((self.root/'output-launcher/request.json').read_bytes())
        self.assertEqual(request['started_epoch'], 2000000000)
        self.assertEqual(request['clock_origin'], 'explicit-predispatch-epoch')
        self.assertEqual(request['hard_deadline_epoch'], 2000042180)
        self.assertEqual(request['global_deadline_epoch'], 2000043200)
        self.assertEqual(request['execution_deadline_epoch'], 2000042000)
        self.assertEqual(request['provider_deadline_epoch'], 2000042300)

    def test_invalid_expired_future_epochs_fail_before_write(self):
        with patch.object(self.scope['time'], 'time', return_value=2000000000):
            for epoch in (None, True, float('nan'), float('inf'), -1, 1, 2000000003):
                with self.subTest(epoch=epoch), self.assertRaises(ValueError):
                    self.launch(self.config(predispatch_epoch=epoch))
        self.assertFalse((self.root/'output-launcher').exists())

    def test_all_four_collisions_preserve_existing_bytes(self):
        for name in ('output', 'source', 'output-launcher', 'output-environment'):
            root = self.root/name
            root.mkdir()
            marker = root/'preserve'
            marker.write_bytes(b'unchanged')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'fresh launcher'):
                self.launch(self.config())
            self.assertEqual(marker.read_bytes(), b'unchanged')
            shutil.rmtree(root)

    def test_rerun_rejects_original_launcher_without_clock_overwrite(self):
        with patch.dict(self.scope, {'_load_guard': lambda *a: object(), '_run_owned': self.fake_run}):
            self.launch(self.config())
            request = (self.root/'output-launcher/request.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'fresh launcher'):
                self.launch(self.config())
            self.assertEqual((self.root/'output-launcher/request.json').read_bytes(), request)

    def test_failure_keeps_original_clock_and_rejects_retry(self):
        def fail(*args, **kwargs):
            raise RuntimeError('authored no-model failure')
        with patch.dict(self.scope, {'_load_guard': lambda *a: object(), '_run_owned': fail}):
            with self.assertRaises(RuntimeError):
                self.launch(self.config())
        raw = (self.root/'output-launcher/request.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'fresh launcher'):
            self.launch(self.config())
        self.assertEqual(raw, (self.root/'output-launcher/request.json').read_bytes())

    def test_late_start_preserves_original_cutoffs_and_exact_reserve(self):
        epoch=2000000000
        with patch.dict(self.scope, {'_load_guard':lambda *a: object(),'_run_owned':self.fake_run}), patch.object(self.scope['time'],'time',return_value=epoch+41879):
            self.launch(self.config(predispatch_epoch=epoch))
        request=json.loads((self.root/'output-launcher/request.json').read_bytes())
        self.assertEqual(request['hard_deadline_epoch'],epoch+42180)
        self.assertEqual(request['execution_deadline_epoch'],epoch+42000)
        shutil.rmtree(self.root/'output-launcher')
        with patch.object(self.scope['time'],'time',return_value=epoch+41880):
            with self.assertRaisesRegex(ValueError,'clock expired'):self.launch(self.config(predispatch_epoch=epoch))
        self.assertFalse((self.root/'output-launcher').exists())

    def test_outer_work_overrun_forces_close_and_records_distinct_deadlines(self):
        import types
        launcher=self.root/'guard-fixture';launcher.mkdir()
        clock={'wall':1000,'mono':100}
        proof={'closed':True,'remaining':[],'returncode':0,'worker_returncode':0,'forced':False}
        stopped=[]
        class Guard:
            def poll(self):return None
            def stop(self,timeout):stopped.append(timeout);return proof
            def closed_proof(self):return proof
        def spawn(*args,**kwargs):
            clock.update(wall=1071,mono=171)
            return Guard()
        module=types.SimpleNamespace(OwnedProcessGuard=types.SimpleNamespace(spawn=spawn),verify_closed_proof=lambda p:None)
        with patch.object(self.scope['time'],'time',side_effect=lambda:clock['wall']),patch.object(self.scope['time'],'monotonic',side_effect=lambda:clock['mono']):
            with self.assertRaisesRegex(RuntimeError,'stopped or failed'):
                self.scope['_run_owned'](['fixture'],guard_module=module,launcher_root=launcher,output_root=self.root/'output',started_epoch=1000,hard_deadline_epoch=1100,cleanup_reserve=30)
        receipt=json.loads((launcher/'launcher-closure.json').read_bytes())
        self.assertEqual(len(stopped),1)
        self.assertTrue(receipt['forced']);self.assertEqual(receipt['reason'],'absolute-session-deadline')
        self.assertEqual(receipt['global_deadline_epoch'],44200)
        self.assertEqual(receipt['execution_deadline_epoch'],43000)
        self.assertEqual(receipt['provider_deadline_epoch'],43300)

    def test_missing_result_cannot_claim_success(self):
        with patch.dict(self.scope, {'_load_guard': lambda *a: object(), '_run_owned': lambda *a, **k: {'closed': True}}):
            with self.assertRaisesRegex(ValueError, 'bounded child result'):
                self.launch(self.config())

    def test_switches_caps_overlap_and_link_fail_closed(self):
        for values in ({'enable_model': False}, {'manual_start': 1}, {'session_seconds': 43201},
                       {'probe_seconds': 21600}, {'execution_cutoff_seconds':42001}, {'outer_cutoff_seconds':42300},
                       {'provider_runtime_seconds':43200}, {'execution_cutoff_seconds':True}, {'source_parent': str(self.root/'output')},
                       {'output_root': str(self.root/'inputs/run')}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.launch(self.config(**values))
        (self.root/'output').symlink_to(self.root/'missing')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.launch(self.config())


class ActualMountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='portfolio-mount-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        _, scope = notebook_scope()
        self.loader = {}
        exec(compile(scope['LOADER_SOURCE'], '<actual-embedded-loader>', 'exec'), self.loader)
        self.pins = copy.deepcopy(scope['PINS'])
        self.old_path = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), self.old_path))
        for name in ('code', 'data', 'training'):
            (self.root/name).mkdir()
        roles = {'solver': '1'*64, 'evaluator': '2'*64}
        raw = json.dumps({'reference': self.pins['data']['reference'], 'format': 'irisx/public120-data-material-v1', 'role_manifests': roles}).encode()
        (self.root/'data/public-data-material.json').write_bytes(raw)
        self.pins['data'].update(manifest_sha256=sha(raw), role_manifests=roles)
        raw = json.dumps({'format': 'irisx/learning-training-material-v1', 'reference': self.pins['training']['reference'],
                          'tasks': 1000, 'public_evaluation_files': 0, 'files': {}}).encode()
        (self.root/'training/manifest.json').write_bytes(raw)
        self.pins['training']['manifest_sha256'] = sha(raw)
        # Synthetic metadata only. No ARC task/answer is copied or accessed.
        for name in ('manifest.json', 'NOTICE.txt'):
            shutil.copyfile(CANDIDATE/'code-payload'/name, self.root/'code'/name)

    def layout(self, kind):
        if kind == 'archive':
            shutil.copyfile(CANDIDATE/'code-payload/source.zip', self.root/'code/source.zip')
        else:
            with zipfile.ZipFile(CANDIDATE/'code-payload/source.zip') as archive:
                archive.extractall(self.root/'code'/('source' if kind == 'directory' else ''))

    def load(self):
        return self.loader['load_reviewed_qwen_source'](pins=self.pins, input_root=str(self.root/'inputs'),
            code_root=str(self.root/'code'), data_root=str(self.root/'data'), training_root=str(self.root/'training'),
            source_parent=str(self.root/'source'), output_root=str(self.root/'output'), model_config={}, resume=False)

    def test_archive(self):
        self.layout('archive')
        self.assertEqual(self.load()['source_transport_mode'], 'verified-archive')

    def test_extracted_root(self):
        self.layout('root')
        self.assertEqual(self.load()['source_transport_mode'], 'verified-extracted-source-root')

    def test_extracted_directory(self):
        self.layout('directory')
        self.assertEqual(self.load()['source_transport_mode'], 'verified-extracted-source-directory')

    def test_mutated_member_rejected(self):
        self.layout('root')
        (self.root/'code/tools/__init__.py').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.load()

    def test_missing_member_rejected(self):
        self.layout('root')
        (self.root/'code/tools/__init__.py').unlink()
        with self.assertRaisesRegex(ValueError, 'closed extracted'):
            self.load()

    def test_symlink_member_rejected(self):
        self.layout('root')
        member = self.root/'code/tools/__init__.py'
        member.unlink()
        member.symlink_to(self.root/'code/NOTICE.txt')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.load()

    def test_wrong_pin_rejected(self):
        self.layout('archive')
        self.pins['code']['manifest_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'manifest hash'):
            self.load()

    def test_unknown_extra_member_rejected(self):
        self.layout('archive')
        (self.root/'code/unlisted').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'ambiguous archive'):
            self.load()




class ActualBootstrapTests(unittest.TestCase):
    def test_exact_driver_and_new_runtime_config_without_model_import(self):
        import types
        with tempfile.TemporaryDirectory(prefix='transfer-bootstrap-') as td:
            root = Path(td)
            with zipfile.ZipFile(CANDIDATE/'code-payload/source.zip') as archive:
                source = archive.read('tools/arc_qwen_transfer_deployment_20261012/bootstrap.py').decode()
                contract = root/'source/materials/qwen14b/material-contract.json'
                contract.parent.mkdir(parents=True)
                contract.write_bytes(archive.read('materials/qwen14b/material-contract.json'))
            scope = {'__name__':'_fixture_bootstrap','__file__':str(root/'fixture_bootstrap.py')}
            exec(compile(source,'<actual-bootstrap>','exec'),scope)
            launcher = root/'launcher'; launcher.mkdir()
            request = {'config':{'input_root':str(root/'input')},'started_epoch':scope['time'].time(),
                       'hard_deadline_epoch':scope['time'].time()+42180,'global_deadline_epoch':scope['time'].time()+43200,
                       'execution_deadline_epoch':scope['time'].time()+42000,'provider_deadline_epoch':scope['time'].time()+42300,'launcher_root':str(launcher),
                       'pins':json.loads((CANDIDATE/'pins.json').read_bytes())}
            ready = {'source_root':str(root/'source'),'training_root':str(root/'training'),
                     'solver_root':str(root/'solver'),'solver_manifest_sha256':'1'*64,
                     'evaluator_root':str(root/'evaluator'),'evaluator_manifest_sha256':'2'*64,
                     'output_root':str(root/'output'),'entry_provenance':{'fixture':True}}
            captured = {}
            def run(config, output, python_command):
                captured.update(config=config,output=output,python_command=python_command)
                return {'status':'TRANSFER_NOT_ADMITTED','operational_success':False}
            runner=types.ModuleType('tools.arc_qwen_transfer_20261012.runner');runner.run_owned_transfer=run
            profile=types.ModuleType('tools.arc_qwen_transfer_20261012.model_profile')
            profile.PROFILE_ID='qwen3-14b-native-bf16-r8-c4096-transfer-v1'
            profile.DEPLOYMENT_ID='qwen3-14b-kaggle-v1-hf40c069-bf16-r8-c4096-transfer-20261012'
            profile.MATERIAL_ADDENDUM_SHA256='ec8354dda582077a67a4df48fbd46dbca0edd1b85fd3461626e040eda5596804'
            offline=types.ModuleType('tools.arc_consolidated_20261010.offline_bootstrap')
            offline.PINS={str(i):{'reference':f'owner/asset{i}/1'} for i in range(5)}
            modules={m.__name__:m for m in (runner,profile,offline)}
            before=set(sys.modules)
            with patch.dict(sys.modules,modules),patch.dict(scope,{
                'resolve_datasets':lambda _: {'runtime':'r','wheels':'w','interpreter':'i'},
                'discover_model':lambda *a,**kw: str(root/'model'),
                'prepare_environment':lambda *a: {'python_command':['verified-python','-I']}}):
                result=scope['bootstrap_probe'](request,ready)
            self.assertEqual(result['status'],'TRANSFER_NOT_ADMITTED')
            self.assertNotIn('torch',set(sys.modules)-before)
            c=captured['config'];self.assertEqual(c['maximum_seconds'],43200)
            self.assertEqual(c['started_epoch'],request['started_epoch'])
            self.assertEqual(c['public_exclusions_sha256'],'ef1d0f2812f42b221a24b6938ed1ee2b64b6165a3d071a5d2d55bb951976be9e')
            self.assertEqual(c['public_evaluator_root'],ready['evaluator_root'])
            self.assertEqual(c['public_solver_root'],ready['solver_root'])
            self.assertEqual(c['model']['context_limit'],4096)
            self.assertEqual(c['model']['prompt_cap'],3072)
            self.assertEqual(c['model']['output_cap'],1024)
            self.assertEqual(c['model']['material_addendum_sha256'],profile.MATERIAL_ADDENDUM_SHA256)
            self.assertEqual(captured['python_command'],['verified-python','-I'])
            saved=json.loads((launcher/'result.json').read_bytes());self.assertEqual(saved,result)
            driver=(CANDIDATE/'expected-launcher/bootstrap.py').read_text()
            self.assertIn('tools.arc_qwen_transfer_deployment_20261012.bootstrap',driver)
            self.assertNotIn("'PORTFOLIO_COMPLETE'",driver)
            compile(driver,'<expected-driver>','exec')


class ExactArtifactTests(unittest.TestCase):
    def test_explicit_baseline_delta_and_payload_closed(self):
        baseline = CANDIDATE.parent.parent/'portfolio63-source-recovery-20261012/exact-delivered/support/code-payload/manifest.json'
        inherited = json.loads(baseline.read_bytes())['source_identity']
        manifest = json.loads((CANDIDATE/'code-payload/manifest.json').read_bytes())
        freeze = json.loads((CANDIDATE/'SOURCE-FREEZE.json').read_bytes())
        self.assertEqual(len(inherited),175)
        with zipfile.ZipFile(CANDIDATE/'code-payload/source.zip') as archive:
            self.assertEqual(set(archive.namelist()),set(manifest['files']))
            self.assertEqual(len(archive.namelist()),len(set(archive.namelist())))
            for name, row in manifest['files'].items():
                raw=archive.read(name)
                self.assertEqual(len(raw),row['bytes'])
                self.assertEqual(sha(raw),row['sha256'])
                self.assertEqual(manifest['source_identity'][name],row['sha256'])
                self.assertEqual(freeze['source_identity'][name],row['sha256'])
            for name,digest in inherited.items():
                if name not in freeze['baseline_changed']:self.assertEqual(sha(archive.read(name)),digest)
            extras=set(archive.namelist())-set(inherited)
            self.assertTrue(all(n.startswith(('tools/arc_qwen_transfer_20261012/','tools/arc_qwen_transfer_deployment_20261012/')) or n=='panel-freeze/public120-exclusions.json' for n in extras))
            self.assertFalse(any(n.startswith('tests/') for n in extras))
        self.assertEqual(set(freeze['baseline_changed']),{'tools/arc_qwen_portfolio_20261012/checkpoints.py'})

    def test_exact_provider_contract_and_unique_roots(self):
        m=json.loads((CANDIDATE/'publication-manifest.json').read_bytes())
        d=m['datasets'][0];self.assertEqual((d['id'],d['expected_predecessor_version'],d['expected_version']),(12504696,12,13))
        self.assertFalse(m['dispatch_ready']);self.assertFalse(m['provider_publication_completed'])
        inactive,active=m['notebooks']
        self.assertEqual((inactive['expected_version'],active['expected_version']),(24,25))
        self.assertEqual(inactive['existing_notebook_id'],138123872)
        self.assertEqual(inactive['dataset_sources'],active['dataset_sources'])
        self.assertEqual(len(inactive['dataset_sources']),8)
        self.assertEqual(active['model_sources'],['qwen-lm/qwen-3/transformers/14b/1'])
        self.assertEqual(active['competition_sources'],['arc-prize-2026-arc-agi-3'])
        self.assertEqual(active['machine_shape'],'NvidiaRtxPro6000')
        for k,v in [('program_session_seconds',43200),('global_seconds',43200),('execution_cutoff_seconds',42000),('outer_cutoff_seconds',42180),('provider_runtime_seconds',42300)]:
            self.assertEqual(active[k],v)
        self.assertFalse(inactive['enable_gpu']);self.assertTrue(active['enable_gpu'])
        self.assertIsNone(active['predispatch_epoch'])
        self.assertEqual(active['dispatch_epoch_patch']['maximum_patch_age_seconds'],60)
        self.assertIsNone(inactive['machine_shape'])
        self.assertIsNone(inactive['timeout_seconds'])
        self.assertFalse(d['delete_old_versions'])
        self.assertEqual(active['role'],'transfer003')
        notebook,scope=notebook_scope()
        self.assertTrue(scope['OUTPUT_ROOT'].endswith('transfer-20261012-run003'))
        self.assertTrue(scope['SOURCE_PARENT'].endswith('transfer-20261012-source003'))

    def test_actual_driver_hash_gate_entrypoint_and_terminal_exits(self):
        import ast,types
        driver=(CANDIDATE/'expected-launcher/bootstrap.py').read_text()
        tree=ast.parse(driver);tail=tree.body[-1]
        self.assertIsInstance(tail,ast.If)
        executable=compile(ast.Module(body=[tail],type_ignores=[]),'<actual-assembled-driver>','exec')
        with tempfile.TemporaryDirectory(prefix='driver-') as td:
            request=Path(td)/'request.json'
            raw=json.dumps({'pins':{'fixture':True},'config':{'input_root':'input','code_root':None,'data_root':None,
                  'training_root':None,'source_parent':'source','output_root':'output'}}).encode()
            request.write_bytes(raw)
            fake=types.ModuleType('tools.arc_qwen_transfer_deployment_20261012.bootstrap')
            called=[]
            def load(**kw):called.append(kw);return {'fixture_ready':True}
            for status,code in [('TRANSFER_COMPLETE',0),('TRANSFER_PARTIAL',0),('TRANSFER_NOT_ADMITTED',0),('TRANSFER_FAILED',2),('PORTFOLIO_COMPLETE',2)]:
                fake.bootstrap_probe=lambda request,ready:{'status':status}
                scope={'__name__':'__main__','load_reviewed_qwen_source':load}
                with patch.object(sys,'argv',['driver',str(request),sha(raw)]),patch.dict(sys.modules,{fake.__name__:fake}):
                    with self.assertRaises(SystemExit) as caught:exec(executable,scope)
                self.assertEqual(caught.exception.code,code)
            self.assertEqual(len(called),5)
            self.assertEqual(called[0]['model_config'],{})
            with patch.object(sys,'argv',['driver',str(request),'0'*64]),patch.dict(sys.modules,{fake.__name__:fake}):
                with self.assertRaisesRegex(ValueError,'request changed'):exec(executable,{'__name__':'__main__','load_reviewed_qwen_source':load})
            self.assertEqual(len(called),5)


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Offline tests for new local run008 transport, never provider admission.

SDK responses and receipts in this suite are explicitly synthetic. Real source
modules, configuration checks, durable claims, journals and readback logic run;
no real credential value, provider endpoint, model, answer or scorer is used.
"""
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parents[1]

def sha(value):
    return hashlib.sha256(Path(value).read_bytes()).hexdigest()

def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()

def load(name,path):
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize),vars(module))
    return module

class NativeTransportTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.repo=self.root/'repository';self.repo.mkdir();(self.repo/'.git').mkdir()
        self.candidate=self.repo/'candidate';self.candidate.mkdir();self.scratch=self.repo/'.irisx/run008-test'
        self.t=load('run008_'+self._testMethodName,HERE/'rl_transport.py')
        t=self.t
        versions={'code_predecessor':20,'code':21,'inactive_predecessor':39,'inactive':40,'active':41}
        self.manifest={'datasets':[{'id':12504696,'reference':t.DREF,'expected_predecessor_version':20,'expected_version':21}],
            'notebooks':[{'role':'inactive','existing_notebook_id':138123872,'existing_notebook_reference':t.REF,'expected_predecessor_version':39,'expected_version':40,'predecessor_source_sha256':'a3076380789de383c1df7c710023d8ca9e9a64a37405547bcebf0e066405d4b9','dataset_sources':[t.DREF+'/21',*t.NON_CODE_PINS]},
                {'role':'rlvr004','existing_notebook_id':138123872,'existing_notebook_reference':t.REF,'expected_predecessor_version':40,'expected_version':41,'dataset_sources':[t.DREF+'/21',*t.NON_CODE_PINS]}]}
        self.manifest_path=self.candidate/'publication-manifest.json';self.manifest_path.write_bytes(encoded(self.manifest))
        self.config={'format':'irisx/run008-native-operator-config-v1','repository_root':str(self.repo),'candidate_root':str(self.candidate),'scratch_root':str(self.scratch),'state_root':str(self.scratch/'state-run008'),'evidence_root':str(self.scratch/'evidence-run008'),'gpu_stop_path':str(self.scratch/'STOP.json'),
            'native_wrapper':{'path':str(self.root/'kaggle_setup/kaggle.sh'),'sha256':'46134808e2705d45d70bdc9aadd26a1e1863628d3d045a32a507efa56616b4bc'},'username':'danielwuu','publication_manifest_sha256':sha(self.manifest_path),'versions':versions,
            'remote_predecessor':{'code_version':20,'notebook_version':39,'notebook_source_sha256':'a3076380789de383c1df7c710023d8ca9e9a64a37405547bcebf0e066405d4b9','provider_status':'ERROR','snapshot_sha256':'b'*64}}
        wrapper=self.root/'kaggle_setup/kaggle.sh';wrapper.parent.mkdir();wrapper.write_bytes((HERE.parents[3]/'kaggle_setup/kaggle.sh').read_bytes())
        self.config_path=self.root/'config.json';self.config_path.write_bytes(encoded(self.config))
        self.review_path=self.root/'SYNTHETIC-REVIEW.json'
        self.review={'status':'PASS','publication_manifest_sha256':sha(self.manifest_path),'material_approval_sha256':'1'*64,'local_config_sha256':sha(self.config_path),'operator_files':{name:sha(HERE/name) for name in ('rl_transport.py','operator_common.py','config.py','native_auth.py','sdk-lock.json','launch.py')},'provider_execution_admitted':False,'synthetic_test_only':True,'allowed_actions':[]}
        self.review_path.write_bytes(encoded(self.review))
        self.args=types.SimpleNamespace(action='validate',manifest=str(self.manifest_path),manifest_sha=sha(self.manifest_path),local_config=str(self.config_path),local_config_sha=sha(self.config_path),review=str(self.review_path),review_sha=sha(self.review_path),material_sha='1'*64,mount=None,mount_sha=None,audit=None,audit_sha=None,monitor_review=None,monitor_sha=None,consumer_root=None,active_review=None,active_review_sha=None)
    def bind(self):
        self.t.configure_local(self.args)
    def rewrite_config(self,document):
        self.config_path.write_bytes(encoded(document));self.args.local_config_sha=sha(self.config_path)
    def code_receipt(self,version=None):
        t=self.t;t.write_new(t.code_state('-receipt.json'),{'dataset_id':12504696,'version':t.CODE_VERSION if version is None else version,'is_private':True,'manifest_sha256':self.args.manifest_sha,'exact_byte_roundtrip':True})
    def active_fixture(self):
        self.bind();t=self.t;self.code_receipt()
        template=encoded({'cells':[{'cell_type':'code','source':['MANUAL_START = False\n']}],'metadata':{}})
        template_path=self.candidate/'template.ipynb';template_path.write_bytes(template)
        row=copy.deepcopy(self.manifest['notebooks'][1]);row.update(path=template_path.name,sha256=sha(template_path),bytes=len(template),title='IRIS-X Learning Agent 20261011',language='python',kernel_type='notebook',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,save_version_value=1,session_timeout_seconds=42300,machine_shape='NvidiaRtxPro6000',docker_image=t.DOCKER,competition_sources=['arc-prize-2026-arc-agi-3'],model_sources=[t.MODEL])
        manifest=copy.deepcopy(self.manifest);manifest['notebooks'][1]=row;manifest['jit']={'entry':{'sha256':'2'*64}}
        submitted=encoded({'cells':[{'cell_type':'code','source':['MANUAL_START = True\n','ENABLE_MODEL = True\n']}],'metadata':{}})
        saved_document=json.loads(submitted);saved_document['cells'][0]['source']=''.join(saved_document['cells'][0]['source']);saved=encoded(saved_document)
        documents={'active-finalized.ipynb':submitted,**{name:encoded({'synthetic_only':True,'role':name}) for name in ('original-request.json','operator.json','parent-private-scorer.json')}}
        raw_meta={'id':138123872,'ref':t.REF,'currentVersionNumber':t.ACTIVE_VERSION,'isPrivate':True,'title':row['title'],'language':'python','kernelType':'notebook','kernelDataSources':[],'enableGpu':True,'enableTpu':False,'enableInternet':False,'modelDataSources':[t.MODEL],'datasetDataSources':['/'.join(p.split('/')[:2]) for p in t.PINS],'competitionDataSources':['arc-prize-2026-arc-agi-3'],'dockerImage':t.DOCKER,'machineShape':'NvidiaRtxPro6000'}
        meta=types.SimpleNamespace(id=138123872,ref=t.REF,current_version_number=t.ACTIVE_VERSION,is_private=True,title=row['title'],language='python',kernel_type='notebook',kernel_data_sources=[],enable_gpu=True,enable_tpu=False,enable_internet=False,model_data_sources=[t.MODEL],dataset_data_sources=raw_meta['datasetDataSources'],competition_data_sources=raw_meta['competitionDataSources'],docker_image=t.DOCKER,machine_shape='NvidiaRtxPro6000',to_dict=lambda:copy.deepcopy(raw_meta))
        source=types.SimpleNamespace(metadata=meta,blob=types.SimpleNamespace(source=saved.decode()))
        response=types.SimpleNamespace(error=None,kernel_id=138123872,ref=t.REF,version_number=t.ACTIVE_VERSION,invalid_dataset_sources=[],invalid_model_sources=[],invalid_competition_sources=[],invalid_kernel_sources=[],to_dict=lambda:{'synthetic_test_only':True,'version_number':t.ACTIVE_VERSION})
        provider=types.SimpleNamespace(save=mock.Mock(return_value=response),kernel=mock.Mock(return_value=source),status=mock.Mock(return_value=types.SimpleNamespace(status=types.SimpleNamespace(name='QUEUED'),failure_message='')))
        return manifest,documents,provider
    def save_patches(self,documents):
        return mock.patch.multiple(self.t,dataset_check=mock.DEFAULT,run_prerequisites=mock.DEFAULT,predecessor=mock.DEFAULT,finalized_documents=mock.DEFAULT,git_publication_gate=mock.Mock(return_value='a'*40))
    def test_live_versions_are_allocated_from_bound_configuration(self):
        document=copy.deepcopy(self.config);manifest=copy.deepcopy(self.manifest)
        document['versions']={'code_predecessor':24,'code':25,'inactive_predecessor':42,'inactive':43,'active':44}
        manifest['datasets'][0].update(expected_predecessor_version=24,expected_version=25)
        for row in manifest['notebooks']:
            row['dataset_sources']=[self.t.DREF+'/25',*self.t.NON_CODE_PINS]
            row['expected_predecessor_version']=42 if row['role']=='inactive' else 43;row['expected_version']=43 if row['role']=='inactive' else 44
        manifest['notebooks'][0]['predecessor_source_sha256']='9'*64
        document['remote_predecessor'].update(code_version=24,notebook_version=42,notebook_source_sha256='9'*64)
        self.manifest_path.write_bytes(encoded(manifest));self.args.manifest_sha=sha(self.manifest_path);document['publication_manifest_sha256']=self.args.manifest_sha
        self.rewrite_config(document);self.bind()
        self.assertEqual(self.t.ACTIVE_VERSION,44);self.assertEqual(self.t.CODE_VERSION,25);self.assertEqual(self.t.OLD_SOURCE,'9'*64)
    def test_old_state_namespace_and_manifest_mismatch_reject_before_state(self):
        changed=copy.deepcopy(self.config);changed['state_root']=str(self.scratch/'state-run005');self.rewrite_config(changed)
        with self.assertRaisesRegex(ValueError,'fresh_state_namespace'):self.bind()
        self.assertFalse(self.scratch.exists())
    def test_stale_review_or_synthetic_review_cannot_admit_execution(self):
        self.bind()
        self.args.action='activate'
        with self.assertRaisesRegex(ValueError,'provider_execution_not_reviewed'):self.t.execution_gate(self.args)
        bad=copy.deepcopy(self.review);bad['local_config_sha256']='0'*64;self.review_path.write_bytes(encoded(bad));self.args.review_sha=sha(self.review_path)
        with self.assertRaisesRegex(ValueError,'config_binding'):self.t.execution_gate(self.args)
    def test_current_and_original_identity_validator_are_separate(self):
        self.bind();t=self.t
        historical=load('run008_historical_fixture',HERE.parent/'publication_run005/rl_transport.py')
        self.assertEqual(t.FROZEN_TRANSPORT_SHA256,sha(HERE.parent/'publication_run005/rl_transport.py'))
        self.assertNotEqual('a3076380789de383c1df7c710023d8ca9e9a64a37405547bcebf0e066405d4b9',historical.OLD_SOURCE)
        self.assertEqual(t.V35_LINEAGE_HELPER_SHA,sha(HERE.parent/'preparation_successor/v35_lineage.py'))
    def test_json_rejects_duplicate_keys_and_nonfinite_values(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}'):
            with self.assertRaises(ValueError):self.t.strict_object(raw)
    def test_git_publication_gate_rejects_missing_remote_proof_before_any_git_command(self):
        self.bind()
        for flag,commit in ((False,None),(True,None),(1,'a'*40),(True,'NOT-COMMITTED')):
            with self.subTest(flag=flag,commit=commit),mock.patch.object(self.t.subprocess,'run') as runner:
                review={'candidate_git_remote_verified':flag,'candidate_git_commit':commit}
                with self.assertRaisesRegex(ValueError,'git_publication_required'):
                    self.t.git_publication_gate(self.args,review)
                runner.assert_not_called()
    def test_git_publication_gate_binds_real_committed_operator_blobs(self):
        import subprocess
        self.bind();t=self.t
        local=self.repo/'publication_run008';local.mkdir()
        names=('config.py','operator_common.py','rl_transport.py','rl_collect.py','native_auth.py','sdk-lock.json','launch.py')
        for name in names:(local/name).write_bytes((HERE/name).read_bytes())
        subprocess.run(['git','-C',str(self.repo),'init','--quiet'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        subprocess.run(['git','-C',str(self.repo),'add','publication_run008'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Offline Test','-c','user.email=offline-test@example.invalid','commit','--quiet','-m','Synthetic offline fixture'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        commit=subprocess.run(['git','-C',str(self.repo),'rev-parse','HEAD'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode().strip()
        review={'candidate_git_remote_verified':True,'candidate_git_commit':commit,'synthetic_test_only':True}
        with mock.patch.object(t,'SCRIPT',local/'rl_transport.py'):
            self.assertEqual(t.git_publication_gate(self.args,review),commit)
            (local/'rl_collect.py').write_bytes(b'# Synthetic uncommitted mutation\n')
            with self.assertRaisesRegex(ValueError,'git_operator_bytes_not_committed'):
                t.git_publication_gate(self.args,review)
    def test_git_gate_precedes_provider_for_write_actions(self):
        self.bind();t=self.t
        review=copy.deepcopy(self.review);review.update(provider_execution_admitted=True,synthetic_test_only=False,allowed_actions=['update-code','save-inactive','activate'])
        self.review_path.write_bytes(encoded(review));self.args.review_sha=sha(self.review_path)
        for action in review['allowed_actions']:
            self.args.action=action
            with self.assertRaisesRegex(ValueError,'git_publication_required'):
                t.execution_gate(self.args)
        self.assertFalse(t.STATE.exists())

    def prepared(self):
        manifest,documents,provider=self.active_fixture();t=self.t
        with self.save_patches(documents) as patched,mock.patch.object(t.time,'time',return_value=2000):
            patched['run_prerequisites'].return_value={};patched['predecessor'].return_value={'version':40,'status':'COMPLETE'};patched['finalized_documents'].return_value=documents
            result=t.save(provider,manifest,self.args,'rlvr004')
        self.assertEqual(result['status'],'ACTIVE_PREPARED_REVIEW_REQUIRED');provider.save.assert_not_called()
        review={'format':'irisx/run008-active-wire-review-v1','status':'PASS','synthetic_test_only':False,'publication_manifest_sha256':self.args.manifest_sha,'material_approval_sha256':self.args.material_sha,'transport_review_sha256':self.args.review_sha,'local_config_sha256':self.args.local_config_sha,'wire_sha256':sha(t.STATE/'notebook-rlvr004-wire.json'),'finalization_sha256':sha(t.STATE/'finalization.json'),'finalized_source_sha256':sha(t.STATE/'active-finalized.ipynb'),'prepared_journal_sha256':sha(t.STATE/'notebook-rlvr004-journal.json'),'predispatch_epoch':2000,'numeric_notebook_version':41}
        path=self.root/'SYNTHETIC-ACTIVE-REVIEW.json';path.write_bytes(encoded(review));self.args.active_review=str(path);self.args.active_review_sha=sha(path)
        return manifest,documents,provider

    @contextlib.contextmanager
    def dispatch_patches(self,documents):
        with mock.patch.multiple(self.t,dataset_check=mock.Mock(),run_prerequisites=mock.Mock(return_value={}),predecessor=mock.Mock(),git_publication_gate=mock.Mock(return_value='a'*40),finalized_documents=mock.Mock(return_value=documents)),mock.patch.object(self.t.time,'time',return_value=2010):yield

    def test_stage_requires_new_review_and_sends_once(self):
        manifest,documents,provider=self.prepared();t=self.t
        with self.dispatch_patches(documents):
            result=t.activate(provider,manifest,self.args)
            self.assertEqual(result['status'],'QUEUED');self.assertEqual(result['version'],41)
            with self.assertRaises(ValueError):t.activate(provider,manifest,self.args)
            intent=sha(t.STATE/'active-readback.claim.json')
            result=t.verify_notebook(provider,manifest,self.args,'rlvr004')
            self.assertEqual(sha(t.STATE/'active-readback.claim.json'),intent)
        self.assertEqual(provider.save.call_count,1)
        j=t.obj(t.STATE/'notebook-rlvr004-journal.json')
        self.assertEqual(j['predispatch_epoch'],2000);self.assertEqual(j['deadline_epoch'],45200)
        self.assertFalse(j['stop_after_submit_readback']);self.assertTrue(j['provider_monitoring_authorized'])

    def test_uncertain_send_can_reconcile_without_resend(self):
        manifest,documents,provider=self.prepared();t=self.t
        provider.save.side_effect=TimeoutError('synthetic uncertain write')
        with self.dispatch_patches(documents):
            with self.assertRaises(TimeoutError):t.activate(provider,manifest,self.args)
            result=t.verify_notebook(provider,manifest,self.args,'rlvr004')
            self.assertTrue(result['provider_acceptance_reconciled'])
            with self.assertRaises(ValueError):t.activate(provider,manifest,self.args)
        self.assertEqual(provider.save.call_count,1)

    def test_interrupted_initial_read_is_reconciled(self):
        manifest,documents,provider=self.prepared();t=self.t
        provider.kernel.side_effect=TimeoutError('synthetic metadata interruption')
        with self.dispatch_patches(documents):
            with self.assertRaises(TimeoutError):t.activate(provider,manifest,self.args)
            claim=sha(t.STATE/'active-readback.claim.json');provider.kernel.side_effect=None
            t.verify_notebook(provider,manifest,self.args,'rlvr004')
            self.assertEqual(sha(t.STATE/'active-readback.claim.json'),claim)
        self.assertEqual(provider.save.call_count,1)

    def test_stale_wire_never_resamples_clock(self):
        manifest,documents,provider=self.prepared();t=self.t
        with mock.patch.object(t,'finalized_documents',return_value=documents),mock.patch.object(t.time,'time',return_value=2061):
            with self.assertRaisesRegex(ValueError,'stale_epoch_no_send'):t.active_review_gate(manifest,self.args)
        provider.save.assert_not_called();self.assertEqual(t.obj(t.STATE/'notebook-rlvr004-journal.json')['predispatch_epoch'],2000)
        with self.save_patches(documents) as patched:
            patched['run_prerequisites'].return_value={};patched['predecessor'].return_value={}
            with self.assertRaises(FileExistsError):t.save(provider,manifest,self.args,'rlvr004')

    def test_synthetic_missing_or_changed_actual_wire_review_rejects(self):
        manifest,documents,provider=self.prepared();t=self.t
        p=Path(self.args.active_review);review=json.loads(p.read_bytes())
        with mock.patch.object(t,'finalized_documents',return_value=documents),mock.patch.object(t.time,'time',return_value=2010):
            for key,value in [('synthetic_test_only',True),('numeric_notebook_version',40),('wire_sha256','0'*64),('predispatch_epoch',1999)]:
                changed={**review,key:value};p.write_bytes(encoded(changed));self.args.active_review_sha=sha(p)
                with self.assertRaises(ValueError):t.active_review_gate(manifest,self.args)
        provider.save.assert_not_called()

    def test_source_and_settings_edits_fail_readback(self):
        manifest,documents,provider=self.prepared();t=self.t
        provider.kernel.return_value.blob.source=encoded({'cells':[{'cell_type':'code','source':'MANUAL_START = False\n'}],'metadata':{}}).decode()
        with self.dispatch_patches(documents):
            with self.assertRaisesRegex(ValueError,'provider_source_normalization'):t.activate(provider,manifest,self.args)
        self.assertFalse((t.STATE/'notebook-rlvr004-receipt.json').exists())

    def test_gpu_unavailable_latches_plain_error_does_not(self):
        self.bind();t=self.t
        t.failure(RuntimeError('plain ERROR without failure message'),'poll');self.assertFalse(t.STOP.exists())
        t.failure(RuntimeError('GPU is unavailable'),'poll');self.assertTrue(t.STOP.is_file())
        with self.assertRaisesRegex(ValueError,'sprint_gpu_stop'):t.no_gpu_stop()

    def test_monitor_actions_are_reviewed_and_separate_from_mutation(self):
        self.bind();t=self.t
        review={**self.review,'provider_execution_admitted':True,'synthetic_test_only':False,'allowed_actions':['poll','collect','watch']}
        self.review_path.write_bytes(encoded(review));self.args.review_sha=sha(self.review_path)
        for action in review['allowed_actions']:
            self.args.action=action;t.execution_gate(self.args,monitor=True)
            with self.assertRaisesRegex(ValueError,'wrong_execution_role'):t.execution_gate(self.args)
        self.args.action='activate'
        with self.assertRaises(ValueError):t.execution_gate(self.args,monitor=True)

    def test_routes_origins_bounds_and_mutation_retries(self):
        import requests
        c=self.t._common
        session=requests.Session();response=mock.Mock(headers={'Content-Type':'application/json'},status_code=200)
        response.iter_content.return_value=iter([b'{}']);session.send=mock.Mock(return_value=response)
        original=session.send;client=types.SimpleNamespace(http_client=lambda:types.SimpleNamespace(_session=session));counts={}
        c.bound_sdk_client(client,counts)
        for url in ['http://api.kaggle.com/v1/kernels.KernelsApiService/GetKernel','https://evil.example/v1/kernels.KernelsApiService/GetKernel','https://api.kaggle.com/v1/kernels.KernelsApiService/CancelKernelSession','https://api.kaggle.com/v1/wrong/GetKernel','https://api.kaggle.com/v1/kernels.KernelsApiService/GetKernel?x=1']:
            with self.assertRaises(ValueError):session.send(requests.Request('POST',url).prepare())
        original.assert_not_called()
        request=requests.Request('POST','https://api.kaggle.com/v1/kernels.KernelsApiService/SaveKernel').prepare()
        session.send(request)
        self.assertEqual(original.call_args.kwargs['timeout'],(15,90));self.assertFalse(original.call_args.kwargs['allow_redirects'])
        with self.assertRaisesRegex(ValueError,'rpc_mutation_resend'):session.send(request)
        self.assertEqual(original.call_count,1)

    def test_wall_timeout_restores_handler(self):
        import signal,time
        c=self.t._common;handler=signal.getsignal(signal.SIGALRM)
        with self.assertRaises(c.WallTimeout):
            with c.wall_bound(.02):time.sleep(.1)
        self.assertEqual(signal.getsignal(signal.SIGALRM),handler);self.assertEqual(signal.getitimer(signal.ITIMER_REAL)[0],0)

    def test_download_failure_closes_and_never_publishes_partial(self):
        self.bind();c=self.t._common
        response=mock.Mock(headers={'Content-Type':'application/octet-stream'},status_code=200)
        response.iter_content.return_value=iter([b'oversized'])
        dest=self.root/'download.bin'
        with self.assertRaisesRegex(ValueError,'download_stream_cap'):
            c.binary_get(response,dest,2)
        self.assertFalse(dest.exists());self.assertTrue(response.close.called)

    def test_no_auth_token_or_historical_guard_bypass_code(self):
        text=(HERE/'native_auth.py').read_text();tree=ast.parse(text)
        names={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        self.assertFalse({'_access_token','_refresh_token','get_access_token'} & names)
        self.assertNotIn('windows_acl_check',text)
        self.assertEqual(self.t._common.NATIVE_AUTH_SHA256,sha(HERE/'native_auth.py'))

    def test_native_boundary_rejects_arbitrary_wrapper(self):
        document=copy.deepcopy(self.config);document['native_wrapper']['path']=str(self.root/'other/kaggle.sh');self.rewrite_config(document)
        with self.assertRaisesRegex(ValueError,'native_wrapper_identity'):self.bind()

    def test_sdk_source_only_ignores_forged_bytecode(self):
        auth=load('native_source_loader_test',HERE/'native_auth.py');c=self.t._common
        package=self.root/'kagglesdk';package.mkdir();source=package/'__init__.py';source.write_text('VALUE = "reviewed"\n')
        finder=auth.ReviewedSdkFinder(self.root,{'kagglesdk/__init__.py':sha(source)},vars(c))
        spec=types.SimpleNamespace(origin=str(source),loader=None)
        with mock.patch.object(auth.importlib.machinery.PathFinder,'find_spec',return_value=spec):
            checked=finder.find_spec('kagglesdk');namespace={};exec(checked.loader.get_code('kagglesdk'),namespace)
            self.assertEqual(namespace['VALUE'],'reviewed')
            source.write_text('VALUE = "changed"\n')
            with self.assertRaises(ValueError):finder.find_spec('kagglesdk')

    def test_launcher_plan_is_fixed_and_isolated(self):
        launcher=load('native_launcher_test',HERE/'launch.py')
        alternate_names=('KAGGLE_API_TOKEN','KAGGLE_USERNAME','KAGGLE_KEY','KAGGLE_TOKEN','KAGGLE_IAP_TOKEN','KAGGLE_API_ENVIRONMENT','KAGGLE_KERNEL_RUN_TYPE','KAGGLE_DATA_PROXY_URL','KAGGLE_API_V1_TOKEN','VERBOSE','VERBOSE_OUTPUT','XDG_CONFIG_HOME','PYTHONPATH','PYTHONHOME')
        injected={key:'SYNTHETIC_NOT_A_CREDENTIAL' for key in alternate_names}
        injected['KAGGLE_CONFIG_DIR']='SYNTHETIC_OTHER_STORE';injected['HOME']='SYNTHETIC_OTHER_HOME'
        with mock.patch.dict(os.environ,injected):
            executable,argv,environment=launcher.plan(['publish','--help'])
        self.assertEqual(argv[1:3],['-I','-B']);self.assertEqual(Path(executable).parent,launcher.WRAPPER.parent/'venv/bin')
        self.assertTrue(all(key not in environment for key in alternate_names))
        self.assertEqual(environment['HOME'],str(launcher.WRAPPER.parent/'home'))
        self.assertEqual(environment['KAGGLE_CONFIG_DIR'],str(launcher.WRAPPER.parent/'home/.kaggle'))
        with self.assertRaises(ValueError):launcher.plan(['arbitrary','file.py'])

    def test_pending_indexing_is_not_stopped_after_elapsed_window(self):
        collector=load('run008_collector_pending_test',HERE/'rl_collect.py')
        snapshot={'status':'ERROR','gpu_stop':False}
        collector.OUT=self.root/'out';collector.OUT.mkdir()
        with mock.patch.object(collector,'poll',return_value=snapshot),mock.patch.object(collector,'collect',side_effect=[collector.IndexingPending('pending'),collector.IndexingPending('pending'),{'status':'TERMINAL_EVIDENCE_VERIFIED'}]) as collect,mock.patch.object(collector.time,'sleep') as sleep,mock.patch.object(collector.time,'monotonic',side_effect=[0,999999,1999999]),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(collector.watch(None,{},None,{}, {'deadline_epoch':1},self.args),0)
        self.assertEqual(collect.call_count,3);self.assertEqual(sleep.call_count,2)
        self.assertTrue(all(call.kwargs['final_incomplete'] is False for call in collect.call_args_list))
        self.assertFalse((collector.OUT/'TERMINAL-BLOCKER.json').exists())

    def test_shared_publisher_lock_released_on_exception(self):
        self.bind();c=self.t._common
        with self.assertRaisesRegex(RuntimeError,'synthetic'):
            with c.lock('publisher'):
                with self.assertRaisesRegex(ValueError,'operator_already_running'):
                    with c.lock('collector'):pass
                raise RuntimeError('synthetic')
        with c.lock('collector'):pass

    def test_numeric_output_requests_never_default_to_latest(self):
        self.bind();c=self.t._common;provider=c.Provider.__new__(c.Provider)
        provider.ensure_read_auth=mock.Mock()
        download=mock.Mock(return_value='SYNTHETIC')
        provider.client=types.SimpleNamespace(kernels=types.SimpleNamespace(kernels_api_client=types.SimpleNamespace(download_kernel_output=download)))
        for version in (None,True,0,'41',40.0,42):
            with self.assertRaises(ValueError):provider.output('selected.json',version=version)
        download.assert_not_called()
        class Request:pass
        with mock.patch.dict(sys.modules,{'kagglesdk.kernels.types.kernels_api_service':types.SimpleNamespace(ApiDownloadKernelOutputRequest=Request)}):
            self.assertEqual(provider.output('selected.json',version=41),'SYNTHETIC')
        request=download.call_args.args[0]
        self.assertEqual(request.version_number,41);self.assertEqual(request.file_path,'selected.json')
        self.assertEqual(request.owner_slug,'danielwuu')

if __name__=='__main__':unittest.main(verbosity=2)

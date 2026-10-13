"""Offline tests for new local run006 transport, never provider admission.

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

@unittest.skipUnless(os.name=='posix','official local transport requires WSL/POSIX')
class LocalReconstructionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.repo=self.root/'repository';self.repo.mkdir();(self.repo/'.git').mkdir()
        self.candidate=self.repo/'candidate';self.candidate.mkdir();self.scratch=self.repo/'.irisx/run006-test'
        self.t=load('run006_'+self._testMethodName,HERE/'rl_transport.py')
        t=self.t
        versions={'code_predecessor':18,'code':19,'inactive_predecessor':35,'inactive':36,'active':37}
        self.manifest={'datasets':[{'id':12504696,'reference':t.DREF,'expected_predecessor_version':18,'expected_version':19}],
            'notebooks':[{'role':'inactive','existing_notebook_id':138123872,'existing_notebook_reference':t.REF,'expected_predecessor_version':35,'expected_version':36,'predecessor_source_sha256':t.V35_SAVED_SOURCE,'dataset_sources':[t.DREF+'/19',*t.NON_CODE_PINS]},
                {'role':'rlvr004','existing_notebook_id':138123872,'existing_notebook_reference':t.REF,'expected_predecessor_version':36,'expected_version':37,'dataset_sources':[t.DREF+'/19',*t.NON_CODE_PINS]}]}
        self.manifest_path=self.candidate/'publication-manifest.json';self.manifest_path.write_bytes(encoded(self.manifest))
        self.config={'format':'irisx/rlvr-local-operator-config-v1','repository_root':str(self.repo),'candidate_root':str(self.candidate),'scratch_root':str(self.scratch),'state_root':str(self.scratch/'state-run006'),'evidence_root':str(self.scratch/'evidence-run006'),'gpu_stop_path':str(self.scratch/'STOP.json'),
            'credential':{'kind':'windows-local','path':'/mnt/c/Users/wurre/.kaggle/credentials.json'},'username':'danielwuu','publication_manifest_sha256':sha(self.manifest_path),'versions':versions,
            'remote_predecessor':{'code_version':18,'notebook_version':35,'notebook_source_sha256':t.V35_SAVED_SOURCE,'provider_status':'CANCEL_ACKNOWLEDGED','snapshot_sha256':'b'*64}}
        self.config_path=self.root/'config.json';self.config_path.write_bytes(encoded(self.config))
        self.review_path=self.root/'SYNTHETIC-REVIEW.json'
        self.review={'status':'PASS','publication_manifest_sha256':sha(self.manifest_path),'material_approval_sha256':'1'*64,'local_config_sha256':sha(self.config_path),'operator_files':{'rl_transport.py':sha(HERE/'rl_transport.py'),'operator_common.py':sha(HERE/'operator_common.py')},'provider_execution_admitted':False,'synthetic_test_only':True,'allowed_actions':[]}
        self.review_path.write_bytes(encoded(self.review))
        self.args=types.SimpleNamespace(action='validate',manifest=str(self.manifest_path),manifest_sha=sha(self.manifest_path),local_config=str(self.config_path),local_config_sha=sha(self.config_path),review=str(self.review_path),review_sha=sha(self.review_path),material_sha='1'*64,mount=None,mount_sha=None,audit=None,audit_sha=None,monitor_review=None,monitor_sha=None,consumer_root=None)

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
        return mock.patch.multiple(self.t,dataset_check=mock.DEFAULT,run_prerequisites=mock.DEFAULT,predecessor=mock.DEFAULT,finalized_documents=mock.DEFAULT)

    def test_fresh_local_profile_and_safety_paths(self):
        self.bind();t=self.t
        self.assertEqual(t.profile_versions(),self.config['versions']);self.assertEqual(t.PINS,[t.DREF+'/19',*t.NON_CODE_PINS])
        self.assertEqual(t.code_state('-receipt.json'),self.scratch/'state-run006/dataset-code-v19-receipt.json')
        self.assertEqual(t.OLD_SOURCE,t.V35_SAVED_SOURCE);self.assertFalse(t.STATE.exists())

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

    def test_task_cloud_credentials_are_rejected_without_reading_values(self):
        document=copy.deepcopy(self.config);document['credential']={'kind':'task-local','path':'/workspace/shared/private-auth/credentials.json'};self.rewrite_config(document)
        with self.assertRaisesRegex(ValueError,'credential_kind'):self.bind()
        self.assertFalse(self.scratch.exists())

    def test_home_spoof_rejected_before_config_or_authentication(self):
        with mock.patch.dict(os.environ,{'HOME':str(self.root/'spoofed')}):
            with self.assertRaisesRegex(ValueError,'real_home_required'):self.bind()
        self.assertFalse(self.scratch.exists())

    def test_stale_review_or_synthetic_review_cannot_admit_execution(self):
        self.bind()
        self.args.action='activate'
        with self.assertRaisesRegex(ValueError,'provider_execution_not_reviewed'):self.t.execution_gate(self.args)
        bad=copy.deepcopy(self.review);bad['local_config_sha256']='0'*64;self.review_path.write_bytes(encoded(bad));self.args.review_sha=sha(self.review_path)
        with self.assertRaisesRegex(ValueError,'config_binding'):self.t.execution_gate(self.args)

    def test_poll_watch_and_continuous_monitor_are_unavailable(self):
        self.bind()
        for action in ('poll','watch','collect'):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):self.t.parser().parse_args([action])
        with self.assertRaisesRegex(ValueError,'monitoring_not_authorized'):self.t.execution_gate(self.args,monitor=True)
        self.assertFalse(hasattr(self.t,'poll'));self.assertFalse(hasattr(self.t,'watch'))

    def test_queued_dispatch_has_one_readback_and_second_send_is_impossible(self):
        manifest,documents,provider=self.active_fixture();t=self.t
        with self.save_patches(documents) as patched,mock.patch.object(t.time,'time',return_value=2000):
            patched['run_prerequisites'].return_value={};patched['predecessor'].return_value={'version':36,'status':'COMPLETE'};patched['finalized_documents'].return_value=documents
            receipt=t.save(provider,manifest,self.args,'rlvr004')
            self.assertEqual(receipt['status'],'QUEUED');self.assertEqual(receipt['version'],37);self.assertTrue(receipt['normalized_source_exact'])
            self.assertEqual(provider.status.call_count,1);self.assertEqual(provider.kernel.call_count,2)
            with self.assertRaises(FileExistsError):t.save(provider,manifest,self.args,'rlvr004')
            with self.assertRaises(FileExistsError):t.verify_notebook(provider,manifest,self.args,'rlvr004')
        self.assertEqual(provider.save.call_count,1);self.assertEqual(provider.status.call_count,1)
        journal=t.obj(t.STATE/'notebook-rlvr004-journal.json');self.assertEqual(journal['predispatch_epoch'],2000);self.assertEqual(journal['deadline_epoch'],45200)
        self.assertTrue(journal['stop_after_submit_readback']);self.assertFalse(journal['provider_monitoring_authorized'])

    def test_uncertain_send_is_reconciled_readonly_without_resend(self):
        manifest,documents,provider=self.active_fixture();t=self.t
        provider.save.side_effect=TimeoutError('SYNTHETIC transport uncertainty')
        with self.save_patches(documents) as patched,mock.patch.object(t.time,'time',return_value=2000):
            patched['run_prerequisites'].return_value={};patched['predecessor'].return_value={'version':36,'status':'COMPLETE'};patched['finalized_documents'].return_value=documents
            with self.assertRaises(TimeoutError):t.save(provider,manifest,self.args,'rlvr004')
            self.assertEqual(provider.kernel.call_count,0)
            receipt=t.verify_notebook(provider,manifest,self.args,'rlvr004')
            self.assertTrue(receipt['provider_acceptance_reconciled']);self.assertEqual(receipt['status'],'QUEUED')
            with self.assertRaises(FileExistsError):t.save(provider,manifest,self.args,'rlvr004')
        self.assertEqual(provider.save.call_count,1);self.assertEqual(provider.status.call_count,1)

    def test_stale_epoch_consumes_claim_and_does_not_send_or_extend_clock(self):
        manifest,documents,provider=self.active_fixture();t=self.t
        with self.save_patches(documents) as patched,mock.patch.object(t.time,'time',side_effect=[2000,2061,2061]):
            patched['run_prerequisites'].return_value={};patched['predecessor'].return_value={'version':36,'status':'COMPLETE'};patched['finalized_documents'].return_value=documents
            with self.assertRaisesRegex(ValueError,'stale_epoch_no_send'):t.save(provider,manifest,self.args,'rlvr004')
        provider.save.assert_not_called();provider.status.assert_not_called()
        journal=t.obj(t.STATE/'notebook-rlvr004-journal.json');self.assertEqual(journal['predispatch_epoch'],2000);self.assertEqual(journal['deadline_epoch'],45200);self.assertEqual(journal['save_calls'],1)

    def test_source_normalization_does_not_allow_source_edits(self):
        manifest,documents,provider=self.active_fixture();t=self.t
        provider.kernel.return_value.blob.source=encoded({'cells':[{'cell_type':'code','source':'MANUAL_START = False\n'}],'metadata':{}}).decode()
        with self.save_patches(documents) as patched,mock.patch.object(t.time,'time',return_value=2000):
            patched['run_prerequisites'].return_value={};patched['predecessor'].return_value={'version':36,'status':'COMPLETE'};patched['finalized_documents'].return_value=documents
            with self.assertRaisesRegex(ValueError,'provider_source_normalization'):t.save(provider,manifest,self.args,'rlvr004')
        self.assertFalse((t.STATE/'notebook-rlvr004-receipt.json').exists());self.assertEqual(provider.status.call_count,1)

    def test_gpu_unavailable_sets_stop_and_cannot_claim_another_send(self):
        manifest,documents,provider=self.active_fixture();t=self.t
        provider.status.return_value.failure_message='GPU is unavailable'
        with self.save_patches(documents) as patched,mock.patch.object(t.time,'time',return_value=2000):
            patched['run_prerequisites'].return_value={};patched['predecessor'].return_value={'version':36,'status':'COMPLETE'};patched['finalized_documents'].return_value=documents
            receipt=t.save(provider,manifest,self.args,'rlvr004');self.assertTrue(receipt['snapshot']['gpu_stop'])
            with self.assertRaisesRegex(ValueError,'sprint_gpu_stop'):t.save(provider,manifest,self.args,'rlvr004')
        self.assertTrue(t.STOP.is_file());self.assertEqual(provider.save.call_count,1)

    def test_old_or_incomplete_receipts_do_not_admit_active_run(self):
        self.bind();t=self.t;self.code_receipt(version=18)
        t.write_new(t.STATE/'notebook-inactive-receipt.json',{'kernel_id':138123872,'version':36,'manifest_sha256':self.args.manifest_sha,'status':'COMPLETE'})
        with self.assertRaisesRegex(ValueError,'prerequisite_versions'):t.run_prerequisites(self.manifest,self.args)

    def test_current_and_original_identity_validator_are_separate(self):
        self.bind();t=self.t
        historical=load('run006_historical_fixture',HERE.parent/'publication_run005/rl_transport.py')
        self.assertEqual(t.FROZEN_TRANSPORT_SHA256,sha(HERE.parent/'publication_run005/rl_transport.py'))
        self.assertNotEqual(t.V35_SAVED_SOURCE,historical.OLD_SOURCE)
        self.assertEqual(t.V35_LINEAGE_HELPER_SHA,sha(HERE.parent/'preparation_successor/v35_lineage.py'))

    def test_common_official_auth_and_request_safety_preserved(self):
        self.assertEqual(self.t.COMMON_SOURCE_SHA256,sha(HERE/'operator_common.py'))
        common_functions={node.name:ast.dump(node,include_attributes=False) for node in ast.parse((HERE/'operator_common.py').read_bytes()).body if isinstance(node,ast.FunctionDef)}
        frozen_functions={node.name:ast.dump(node,include_attributes=False) for node in ast.parse((HERE.parent/'publication_local/operator_common.py').read_bytes()).body if isinstance(node,ast.FunctionDef)}
        for name in ('bound_sdk_client','no_retry_session','safe_url','existing_token','wall_bound','claim','lock','redacted_message'):
            self.assertEqual(common_functions[name],frozen_functions[name],name)
        self.assertEqual(self.t._common.CONFIG_SOURCE_SHA256,sha(HERE/'config.py'))

    def test_json_rejects_duplicate_keys_and_nonfinite_values(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}'):
            with self.assertRaises(ValueError):self.t.strict_object(raw)

    def test_rebound_collector_checks_complete_saved_launch_git_linkage(self):
        manifest,documents,provider=self.active_fixture();t=self.t
        with self.save_patches(documents) as patched,mock.patch.object(t.time,'time',return_value=2000):
            patched['run_prerequisites'].return_value={'monitor_review_sha256':None};patched['predecessor'].return_value={'version':36,'status':'COMPLETE'};patched['finalized_documents'].return_value=documents
            t.save(provider,manifest,self.args,'rlvr004')
        collector=load('run006_collector_git_tests',HERE/'rl_collect.py')
        collector.transport.configure_local(self.args)
        receipt_path=t.STATE/'notebook-rlvr004-receipt.json';journal_path=t.STATE/'notebook-rlvr004-journal.json'
        original_receipt=t.obj(receipt_path);original_journal=t.obj(journal_path)
        cases=[(False,None,False,None,True),(True,'a'*40,True,'a'*40,True),
               (True,'a'*40,True,'b'*40,False),(True,'NOT-A-COMMIT',True,'NOT-A-COMMIT',False),
               (False,'a'*40,False,'a'*40,False),(True,'a'*40,1,'a'*40,False)]
        with mock.patch.object(collector.transport,'load_contract',return_value=manifest),mock.patch.object(collector.transport,'monitor_gate',return_value={}),mock.patch.object(collector.transport,'finalized_documents',return_value=documents):
            for receipt_flag,receipt_commit,journal_flag,journal_commit,accepted in cases:
                with self.subTest(receipt_flag=receipt_flag,journal_flag=journal_flag,accepted=accepted):
                    journal=copy.deepcopy(original_journal);journal.update(git_publication_completed=journal_flag,git_commit=journal_commit);t.journal('notebook-rlvr004',journal)
                    receipt=copy.deepcopy(original_receipt);receipt.update(git_publication_completed=receipt_flag,git_commit=receipt_commit,launch_journal_sha256=sha(journal_path));receipt_path.write_bytes(encoded(receipt))
                    if accepted:
                        _,launch,_,_=collector.bindings(self.args);self.assertEqual(launch['git_commit'],receipt_commit)
                    else:
                        with self.assertRaisesRegex(ValueError,'honest_git'):collector.bindings(self.args)

    def test_rebound_collector_cannot_create_provider_for_poll_collect_or_watch(self):
        collector=load('run006_collector_stop_tests',HERE/'rl_collect.py')
        parser=types.SimpleNamespace(_actions=[None,types.SimpleNamespace(choices=[])],parse_args=lambda:self.args)
        for action in ('poll','collect','watch'):
            self.args.action=action
            with mock.patch.object(collector.transport,'parser',return_value=parser),mock.patch.object(collector,'bindings',return_value=({},None,None,None)),mock.patch.object(collector,'Provider') as provider,contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(collector.main(),2);provider.assert_not_called()
                self.assertIn('provider_monitoring_not_authorized',output.getvalue())

if __name__=='__main__':
    unittest.main(verbosity=2)

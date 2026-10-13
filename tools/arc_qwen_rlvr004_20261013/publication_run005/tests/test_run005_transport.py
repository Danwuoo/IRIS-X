"""No-provider run005 identity, one-send, clock and unchanged safety tests."""
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parents[1]
PRIOR=HERE.parent/'publication_local'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def encoded(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def load(name,path):
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize),vars(module));return module
def functions(path):
    return {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(path.read_bytes()).body if isinstance(node,ast.FunctionDef)}

@unittest.skipUnless(os.name=='posix','operator requires local WSL/POSIX')
class Run005TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.repo=self.root/'repository';self.repo.mkdir();(self.repo/'.git').mkdir()
        self.candidate=self.repo/'candidate';self.candidate.mkdir();self.scratch=self.repo/'.irisx/run005-fixture'
        self.transport=load('run005_transport_'+self._testMethodName,HERE/'rl_transport.py')
        t=self.transport
        self.manifest={'datasets':[{'id':12504696,'reference':t.DREF,'expected_predecessor_version':17,'expected_version':18}],
                       'notebooks':[{'role':'inactive','existing_notebook_id':138123872,'existing_notebook_reference':t.REF,'expected_predecessor_version':33,'expected_version':34,'predecessor_source_sha256':t.OLD_SOURCE,'dataset_sources':t.PINS,'sha256':'c'*64},
                                    {'role':'rlvr004','existing_notebook_id':138123872,'existing_notebook_reference':t.REF,'expected_predecessor_version':34,'expected_version':35,'dataset_sources':t.PINS,'sha256':'d'*64}]}
        self.manifest_path=self.candidate/'publication-manifest.json';self.manifest_path.write_bytes(encoded(self.manifest))
        self.config={'format':'irisx/rlvr-local-operator-config-v1','repository_root':str(self.repo),'candidate_root':str(self.candidate),'scratch_root':str(self.scratch),'state_root':str(self.scratch/'state-run005'),'evidence_root':str(self.scratch/'evidence-run005'),'gpu_stop_path':str(self.scratch/'STOP.json'),
                     'credential':{'kind':'windows-local','path':'/mnt/c/Users/wurre/.kaggle/credentials.json'},'username':'danielwuu','publication_manifest_sha256':sha(self.manifest_path),'versions':t.profile_versions(),
                     'remote_predecessor':{'code_version':17,'notebook_version':33,'notebook_source_sha256':t.OLD_SOURCE,'provider_status':'ERROR','snapshot_sha256':'b'*64}}
        self.config_path=self.root/'config.json';self.config_path.write_bytes(encoded(self.config))
        self.review_path=self.root/'synthetic-review.json'
        self.review={'status':'PASS','publication_manifest_sha256':sha(self.manifest_path),'material_approval_sha256':'1'*64,'local_config_sha256':sha(self.config_path),'operator_files':{'rl_transport.py':sha(HERE/'rl_transport.py'),'operator_common.py':sha(HERE/'operator_common.py')},'provider_execution_admitted':False,'synthetic_test_only':True,'allowed_actions':[]}
        self.review_path.write_bytes(encoded(self.review))
        self.args=types.SimpleNamespace(action='validate',manifest=str(self.manifest_path),manifest_sha=sha(self.manifest_path),local_config=str(self.config_path),local_config_sha=sha(self.config_path),review=str(self.review_path),review_sha=sha(self.review_path),material_sha='1'*64)
    def bind(self):self.transport.configure_local(self.args)
    def change_config(self,changes):
        document=copy.deepcopy(self.config);document.update(changes);self.config_path.write_bytes(encoded(document));self.args.local_config_sha=sha(self.config_path)
    def fake_code_receipt(self,version=18):
        self.transport.write_new(self.transport.code_state('-receipt.json'),{'dataset_id':12504696,'version':version,'is_private':True,'manifest_sha256':self.args.manifest_sha,'exact_byte_roundtrip':True})
    def active_fixture(self):
        self.bind();self.fake_code_receipt()
        raw=b'synthetic inert template only\n';path=self.candidate/'inert-template.ipynb';path.write_bytes(raw)
        row=copy.deepcopy(self.manifest['notebooks'][1]);row.update(path=path.name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),title='IRIS-X Learning Agent 20261011',enable_gpu=True,save_version_value=1,session_timeout_seconds=42300,machine_shape='NvidiaRtxPro6000')
        manifest=copy.deepcopy(self.manifest);manifest['notebooks'][1]=row;manifest['jit']={'entry':{'sha256':'2'*64}}
        documents={name:b'synthetic '+name.encode()+b'\n' for name in ('active-finalized.ipynb','original-request.json','operator.json','parent-private-scorer.json')}
        return manifest,documents

    def test_exact_profile_and_distinct_namespace(self):
        self.bind();t=self.transport
        self.assertEqual(t.profile_versions(),{'code_predecessor':17,'code':18,'inactive_predecessor':33,'inactive':34,'active':35})
        self.assertEqual(t.code_state('-receipt.json'),self.scratch/'state-run005/dataset-code-v18-receipt.json')
        self.assertTrue(t.RUN_PATH.endswith('run005'));self.assertTrue(t.SOURCE_PATH.endswith('source005'));self.assertTrue(t.ENVIRONMENT_PATH.endswith('environment005'))
        self.assertEqual(t.PINS[0],t.DREF+'/18');self.assertEqual(t.PINS[1:],load('prior_pins_fixture',PRIOR/'rl_transport.py').PINS[1:])
        self.assertFalse(t.STATE.exists())

    def test_old_attempt_state_namespace_is_rejected(self):
        self.change_config({'state_root':str(self.scratch/'state-run004')})
        with self.assertRaisesRegex(ValueError,'fresh_state_namespace'):self.bind()
        self.assertFalse(self.scratch.exists())

    def test_other_numeric_profile_even_with_matching_manifest_is_rejected(self):
        document=copy.deepcopy(self.config);manifest=copy.deepcopy(self.manifest)
        document['versions']={'code_predecessor':18,'code':19,'inactive_predecessor':35,'inactive':36,'active':37}
        manifest['datasets'][0].update(expected_predecessor_version=18,expected_version=19)
        for row in manifest['notebooks']:
            row['dataset_sources']=[self.transport.DREF+'/19',*self.transport.PINS[1:]]
            row['expected_predecessor_version']=35 if row['role']=='inactive' else 36;row['expected_version']=36 if row['role']=='inactive' else 37
        document['remote_predecessor'].update(code_version=18,notebook_version=35)
        self.manifest_path.write_bytes(encoded(manifest));self.args.manifest_sha=sha(self.manifest_path);document['publication_manifest_sha256']=self.args.manifest_sha
        self.config_path.write_bytes(encoded(document));self.args.local_config_sha=sha(self.config_path)
        with self.assertRaisesRegex(ValueError,'config_versions'):self.bind()

    def test_stale_review_config_or_operator_hash_is_rejected(self):
        self.bind()
        for field in ('local_config_sha256','operator_files'):
            review=copy.deepcopy(self.review)
            if field=='local_config_sha256':review[field]='0'*64
            else:review[field]['rl_transport.py']='0'*64
            self.review_path.write_bytes(encoded(review))
            with self.assertRaises(ValueError):self.transport.review_gate(self.review_path,sha(self.review_path),self.args.manifest_sha,self.args.material_sha,[HERE/'rl_transport.py',HERE/'operator_common.py'])

    def test_old_code_receipt_cannot_admit_save(self):
        self.bind();self.fake_code_receipt(version=17);provider=types.SimpleNamespace(save=mock.Mock())
        with self.assertRaisesRegex(ValueError,'verified_code_required'):
            self.transport.save(provider,self.manifest,self.args,'inactive')
        provider.save.assert_not_called()

    def test_old_code_journal_cannot_start_numeric_readback(self):
        self.bind();self.transport.write_new(self.transport.code_state('-journal.json'),{'manifest_sha256':self.args.manifest_sha,'version_calls':1,'expected_version':17,'expected_predecessor_version':16})
        provider=types.SimpleNamespace(dataset_download=mock.Mock())
        with self.assertRaisesRegex(ValueError,'code_journal_versions'):self.transport.verify_code(provider,self.manifest,self.args)
        provider.dataset_download.assert_not_called()

    def test_duplicate_active_dispatch_cannot_send_twice(self):
        manifest,documents=self.active_fixture();t=self.transport
        response=types.SimpleNamespace(error=None,kernel_id=138123872,ref=t.REF,version_number=35,invalid_dataset_sources=[],invalid_model_sources=[],invalid_competition_sources=[],invalid_kernel_sources=[]);response.to_dict=lambda:{'fixture':True,'version_number':35}
        provider=types.SimpleNamespace(save=mock.Mock(return_value=response))
        with mock.patch.object(t,'dataset_check'),mock.patch.object(t,'run_prerequisites',return_value={}),mock.patch.object(t,'predecessor',return_value={'version':34,'status':'COMPLETE'}),mock.patch.object(t,'finalized_documents',return_value=documents),mock.patch.object(t.time,'time',return_value=2000):
            result=t.save(provider,manifest,self.args,'rlvr004');self.assertEqual(result['version'],35)
            with self.assertRaises(FileExistsError):t.save(provider,manifest,self.args,'rlvr004')
        self.assertEqual(provider.save.call_count,1)
        journal=t.obj(t.STATE/'notebook-rlvr004-journal.json');self.assertEqual(journal['predispatch_epoch'],2000);self.assertEqual(journal['deadline_epoch'],45200)
        wire=provider.save.call_args.args[0];self.assertEqual(wire['dataset_data_sources'][0],t.DREF+'/18');self.assertEqual(wire['session_timeout_seconds'],42300)

    def test_stale_epoch_consumes_claim_without_provider_send_or_clock_reset(self):
        manifest,documents=self.active_fixture();t=self.transport;provider=types.SimpleNamespace(save=mock.Mock())
        with mock.patch.object(t,'dataset_check'),mock.patch.object(t,'run_prerequisites',return_value={}),mock.patch.object(t,'predecessor',return_value={'version':34,'status':'COMPLETE'}),mock.patch.object(t,'finalized_documents',return_value=documents),mock.patch.object(t.time,'time',side_effect=[2000,2061,2061]):
            with self.assertRaisesRegex(ValueError,'stale_epoch_no_send'):t.save(provider,manifest,self.args,'rlvr004')
        provider.save.assert_not_called();journal=t.obj(t.STATE/'notebook-rlvr004-journal.json')
        self.assertEqual(journal['predispatch_epoch'],2000);self.assertEqual(journal['deadline_epoch'],45200);self.assertEqual(journal['save_calls'],1)

    def test_successor_dependency_pins_and_unchanged_common_config(self):
        collector=load('run005_collector_pins',HERE/'rl_collect.py')
        self.assertEqual(collector.TRANSPORT_SOURCE_SHA256,sha(HERE/'rl_transport.py'));self.assertEqual(collector.COMMON_SOURCE_SHA256,sha(HERE/'operator_common.py'))
        self.assertEqual((HERE/'operator_common.py').read_bytes(),(PRIOR/'operator_common.py').read_bytes());self.assertEqual((HERE/'config.py').read_bytes(),(PRIOR/'config.py').read_bytes())
        self.assertIsNone(collector.OUT);self.assertIsNone(collector.CONFIG)

    def test_collector_old_cache_version_is_rejected(self):
        collector=load('run005_collector_cache',HERE/'rl_collect.py');collector.transport.configure_local(self.args)
        collector.__dict__.update({k:v for k,v in collector._common.__dict__.items() if not k.startswith('_')})
        collector.OUT=collector.CONFIG.evidence_root;collector.DOWNLOADS=collector.OUT/'downloads'
        name='synthetic/result.json';digest=collector.sha(name.encode());receipt=collector.OUT/'download-receipts'/(digest+'.json')
        collector.write_new(receipt,{'provider_path':name,'version':33,'numeric_version':33,'http_status':200,'source_kind':'provider_download','bytes':1,'sha256':'0'*64})
        provider=types.SimpleNamespace(output=mock.Mock())
        with self.assertRaisesRegex(ValueError,'selected_cache_binding'):collector.fetch_selected(provider,name,10,100)
        provider.output.assert_not_called()

    def test_pred_submission_and_saved_hashes_are_not_conflated(self):
        t=self.transport;self.assertNotEqual(t.OLD_SOURCE,t.PREDECESSOR_SUBMITTED_SOURCE)
        self.assertEqual(t.OLD_SOURCE,'e7747c8013a9149cf7331954fd583fd8770adb416b2881074c9875f94c3f7761')
        self.assertEqual(t.PREDECESSOR_EPOCH,1791866719)

    def test_predecessor_mixed_saved_submitted_or_version_is_rejected(self):
        t=self.transport
        proof={'format':'irisx/rlvr005-predecessor-evidence-v1','notebook_id':138123872,'numeric_notebook_version':33,'code_dataset_id':12504696,'code_dataset_version':17,'provider_status':'ERROR','saved_source_sha256':t.OLD_SOURCE,'submitted_source_sha256':t.PREDECESSOR_SUBMITTED_SOURCE,'evidence':{},'selected_outputs':{},'historical_v31':{}}
        for field,value,expected in (('saved_source_sha256',t.PREDECESSOR_SUBMITTED_SOURCE,'distinct_saved_submitted'),('numeric_notebook_version',31,'verified_error_predecessor_required'),('code_dataset_version',16,'verified_error_predecessor_required')):
            changed=copy.deepcopy(proof);changed[field]=value;path=self.candidate/'synthetic-predecessor.json';path.write_bytes(encoded(changed))
            manifest={'predecessor_readiness':{'path':path.name,'bytes':path.stat().st_size,'sha256':sha(path),'notebook_version':33,'notebook_source_sha256':t.OLD_SOURCE,'provider_status':'ERROR'}}
            with self.assertRaisesRegex(ValueError,expected):t.predecessor_proof(manifest,self.candidate)

    def test_protected_scientific_functions_and_clock_remain_exact(self):
        old=functions(PRIOR/'rl_transport.py');new=functions(HERE/'rl_transport.py')
        protected=('clock','descriptor_at','finalized_documents','check_finalization','review_gate','load_contract','settings','saved_settings','bracket','expected_layout','monitor_gate','execution_gate','kernel_wire','parser')
        for name in protected:self.assertEqual(old[name],new[name],name)
        old=functions(PRIOR/'rl_collect.py');new=functions(HERE/'rl_collect.py')
        for name in ('output_paths','failure_paths','downloaded_bytes','checkpoint_observation','wrapper_gate','assemble_consumer_envelope','validate_received','validation_gate','strict_json','diagnostic_archive_helpers','explicit_cuda_unavailable','retry_delay','watch','main'):
            self.assertEqual(old[name],new[name],name)

    def test_consumed_local_operator_hashes_remain_unchanged(self):
        expected={'config.py':'71efb0de2c10c506a53072e5c8372e0aa4af6e0dac840c0f07239663995e9f72','operator_common.py':'9c1385696c4edd3fe381d7c1d657aa805b9dcca2def6700148a40aa255db977a','rl_transport.py':'4cecb2bb2e9e254f7410c2ffe9f8d30c93735db87fdcb8f23b62ee11c07e4a1e','rl_collect.py':'67856b6ce78fb004b0efaea56346fb8266988f9a2384c34e0c0cecc76c401c73'}
        for name,digest in expected.items():self.assertEqual(sha(PRIOR/name),digest,name)

if __name__=='__main__':unittest.main(verbosity=2)

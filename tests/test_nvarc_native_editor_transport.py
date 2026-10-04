"""Offline synthetic save lifecycle; fake provider sends never leave this process."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import save_nvarc_native_multitask as save
from tools import stage_nvarc_native_multitask as stage
from tools.nvarc_native_multitask import canonical,digest


class NativeEditorTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan,cls.raw,cls.notebook,cls.metadata=stage.construct('nvarc-original-qwen3-native-multitask-995')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='iris-synthetic-save-')
        self.root=Path(self.temp.name);self.patch_root=patch.object(save,'ROOT',self.root);self.patch_root.start()
        self.run=self.plan['run_id'];_,self.package,self.journal=save.paths(self.run)
        (self.package/'kernel').mkdir(parents=True)
        self.put('plan.json',self.plan);self.put('kernel/kernel-metadata.json',self.metadata)
        self.put('kernel/notebook.ipynb',self.notebook)
        self.put('stage-summary.json',{'inventory':{p.relative_to(self.package).as_posix():save.sha(p)
            for p in self.package.rglob('*') if p.is_file()},'plan_digest':digest(self.plan)})
        self.admission={'reviewed_plan_digest':'sha256:'+'a'*64}

    def tearDown(self):self.patch_root.stop();self.temp.cleanup()
    def put(self,name,value):(self.package/name).write_bytes(canonical(value))
    def get(self,name):return json.loads((self.package/name).read_bytes())

    def admitted(self):
        self.put('controller-admission.json',self.admission)
        plan=self.get('plan.json');plan.update(approved=True,controller_admission=self.admission,
            controller_admission_sha256=save.sha(self.package/'controller-admission.json'),
            approved_proposal_plan_digest=self.admission['reviewed_plan_digest'])
        self.put('plan.json',plan)
        self.put('stage-summary.json',{'inventory':{p.relative_to(self.package).as_posix():save.sha(p)
            for p in self.package.rglob('*') if p.is_file() and p.name!='stage-summary.json'},'plan_digest':digest(plan)})

    def initialize(self):
        self.admitted()
        with patch.object(save,'validate_admission',return_value=self.admission),patch.object(stage,'preflight',return_value={'external_calls':0}):
            return save.execute('init',self.package)

    def fake_client(self,kind):
        wire=json.loads((self.journal/'save-request.json').read_bytes());sends=[]
        session=SimpleNamespace(send=lambda prepared,**kw:sends.append(prepared.url))
        def provider(req):
            self.assertEqual(json.loads((self.journal/'save-ledger.json').read_bytes())['push_reserved'],1)
            self.assertTrue((self.package.parent/'quick-save-reservation.json').is_file())
            prepared=SimpleNamespace(method='POST',url=save.SAVE_URL,body=json.dumps(req.to_dict()))
            if kind=='wrong-api':prepared.url=save.SAVE_URL.replace('SaveKernel','GetKernel')
            session.send(prepared)
            if kind=='double-send':session.send(prepared)
            if kind=='timeout':raise TimeoutError('synthetic unknown outcome')
            if kind=='interrupt':raise KeyboardInterrupt()
            receipt={'url':'https://www.kaggle.com/code/danielwuu/'+self.run,'versionNumber':1}
            if kind=='different-slug':receipt['url']+='-different'
            if kind=='version-two':receipt['versionNumber']=2
            if kind=='invalid-source':receipt['invalidModelSources']=['synthetic-invalid']
            error='synthetic rejection' if kind=='rejected' else None
            return SimpleNamespace(to_dict=lambda:dict(receipt),url=receipt['url'],version_number=receipt['versionNumber'],error=error)
        class Client:
            def __enter__(inner):return inner
            def __exit__(inner,*_args):pass
            def http_client(inner):return SimpleNamespace(_init_session=lambda:None,_session=session)
            kernels=SimpleNamespace(kernels_api_client=SimpleNamespace(save_kernel=provider))
        return Client(),sends,wire

    def do_save(self,kind):
        client,sends,_=self.fake_client(kind)
        with patch.object(stage,'preflight',return_value={'external_calls':0}),\
             patch.object(save,'validate_admission',return_value=self.admission),\
             patch.object(save,'token',return_value='synthetic-not-a-credential'),\
             patch.object(save,'client_for',return_value=client):
            result=save.execute('save',self.package)
        return result,sends

    def test_inert_review_builds_real_sdk_wire_without_credentials(self):
        with patch.object(stage,'preflight',return_value={'external_calls':0}),patch.object(save,'token',side_effect=AssertionError('credentials forbidden')):
            proof=save.execute('review',self.package)
        self.assertTrue(proof['review_only']);wire=json.loads((self.journal/'save-request.json').read_bytes())
        self.assertEqual(wire['kernelExecutionType'],'QUICK_SAVE');self.assertTrue(wire['isPrivate'])
        self.assertFalse(wire.get('enableInternet',False));self.assertEqual(wire['machineShape'],'NvidiaL4')
        self.assertEqual(wire['modelDataSources'],self.metadata['model_sources'])
        with patch.object(stage,'preflight',return_value={}):
            with self.assertRaisesRegex(RuntimeError,'unused admitted'):save.execute('save',self.package)

    def test_acceptance_is_one_save_receipt_and_runtime_unobserved(self):
        self.initialize();result,sends=self.do_save('accepted')
        self.assertTrue(result['accepted']);self.assertFalse(result['agent_execution_started'])
        self.assertEqual(result['runtime'],'unobserved');self.assertEqual(sends,[save.SAVE_URL])
        ledger=json.loads((self.journal/'save-ledger.json').read_bytes())
        self.assertEqual(ledger['events'][0]['receipt_sha256'],save.sha(self.journal/'save-receipt.json'))
        with self.assertRaisesRegex(RuntimeError,'unused admitted'):self.do_save('accepted')

    def test_all_failures_unknowns_and_interrupts_consume_identity(self):
        for kind in ('rejected','timeout','interrupt','different-slug','version-two','invalid-source','double-send','wrong-api'):
            with self.subTest(kind=kind):
                # Independent synthetic identity directory per simulated outcome.
                with tempfile.TemporaryDirectory(prefix='iris-synthetic-outcome-') as temp,patch.object(save,'ROOT',Path(temp)):
                    _,package,journal=save.paths(self.run)
                    import shutil
                    shutil.copytree(self.package,package)
                    old=self.package,self.journal;self.package,self.journal=package,journal
                    try:
                        self.initialize()
                        with self.assertRaisesRegex(RuntimeError,'frozen; no retry'):self.do_save(kind)
                        ledger=json.loads((journal/'save-ledger.json').read_bytes())
                        self.assertEqual(ledger['push_reserved'],1);self.assertLessEqual(ledger['events'][0]['sends'],1)
                        with self.assertRaisesRegex(RuntimeError,'unused admitted'):self.do_save('accepted')
                    finally:self.package,self.journal=old

    def test_crash_claim_blocks_reinitialization_even_without_receipt(self):
        self.initialize();claim=self.package.parent/'quick-save-reservation.json';claim.write_text('synthetic crash window')
        with patch.object(stage,'preflight',return_value={}):
            with self.assertRaisesRegex(RuntimeError,'reserved identity'):save.execute('init',self.package)
        with self.assertRaises(FileExistsError):self.do_save('accepted')

    def test_tampered_package_or_wire_is_rejected_before_credentials(self):
        self.initialize();path=self.journal/'save-request.json';wire=json.loads(path.read_bytes());wire['kernelExecutionType']='SAVE_AND_RUN_ALL';path.write_bytes(canonical(wire))
        with patch.object(stage,'preflight',return_value={}),patch.object(save,'token',side_effect=AssertionError('must not enter credentials')):
            with self.assertRaisesRegex(RuntimeError,'unused admitted'):save.execute('save',self.package)

    def test_mounts_privacy_and_execution_fields_fail_closed(self):
        for key,value in [('model_sources',['wrong/model']),('competition_sources',[]),('dataset_sources',['extra']),
                ('enable_internet',True),('is_private',False),('id','danielwuu/other'),('unknown',True)]:
            with self.subTest(key=key):
                meta=copy.deepcopy(self.metadata);meta[key]=value;self.put('kernel/kernel-metadata.json',meta)
                with self.assertRaises(RuntimeError):save.request_fields(self.package,admitted=False)

    def test_fixed_path_and_single_init_are_enforced(self):
        self.initialize()
        with patch.object(stage,'preflight',return_value={}):
            with self.assertRaisesRegex(RuntimeError,'already prepared'):save.execute('init',self.package)
        (self.root/'plan.json').write_bytes(canonical(self.plan))
        with self.assertRaisesRegex(RuntimeError,'fixed package'):save.execute('init',self.root)

    def test_v2_admission_binds_review_and_real_resource_fields(self):
        review='nvarc-original-qwen3-native-multitask-994';_,package,_=save.paths(review)
        (package/'kernel').mkdir(parents=True);(package/'kernel/notebook.ipynb').write_bytes(b'synthetic inert review')
        value={'format':save.ADMISSION_FORMAT,'run_id':self.run,'reviewed_run_id':review,
            'reviewed_plan_digest':'sha256:'+'a'*64,'reviewed_notebook_sha256':save.sha(package/'kernel/notebook.ipynb'),
            'source_commit':save.REVIEW_COMMIT,'control_review_sha256':save.REVIEW_SHA,'maximum_paid_usd':0,
            'prior_sessions_reconciled':True,'quota_reservation_id':'SYNTHETIC TEST ONLY','reserved_quota_hours':2.5,
            'quota_observed_at':'2026-10-04T22:00:00+08:00','local_resource_admission':True,'ui_operator':'user',
            'private':True,'internet':False,'owner_editor_sessions_closed':True,'owner_clearance_ref':'SYNTHETIC TEST ONLY',
            'l4_quota_multiplier':2,'quick_save_authorized':True,'maximum_quick_saves':1,'agent_execution_authorized':False}
        path=self.root/'synthetic-admission.json'
        with patch.object(save,'sha',side_effect=lambda p:save.REVIEW_SHA if p==save.REVIEW_FILE else __import__('hashlib').sha256(p.read_bytes()).hexdigest()),\
                patch.object(stage,'preflight',return_value={'approved_for_runtime':False,'plan_digest':value['reviewed_plan_digest']}):
            path.write_bytes(canonical(value));self.assertEqual(save.validate_admission(path,self.run),value)
            for key,bad in [('owner_editor_sessions_closed',None),('reserved_quota_hours',2.49),('reserved_quota_hours',float('inf')),
                    ('l4_quota_multiplier',4),('quota_observed_at','2026-10-04T22:00:00'),('owner_clearance_ref',''),
                    ('quick_save_authorized',False),('maximum_quick_saves',2),('agent_execution_authorized',True),
                    ('reviewed_run_id',self.run),('reviewed_notebook_sha256','wrong'),('source_commit','old')]:
                with self.subTest(key=key,bad=bad):
                    changed=dict(value);changed[key]=bad;path.write_text(json.dumps(changed))
                    with self.assertRaises((RuntimeError,ValueError)):save.validate_admission(path,self.run)

    def test_admission_derivation_changes_only_plan_payload(self):
        value={'format':save.ADMISSION_FORMAT,'source_commit':save.REVIEW_COMMIT,'owner_clearance_ref':'SYNTHETIC TEST ONLY',
            'reviewed_plan_digest':digest(self.plan),'reviewed_run_id':self.run,'quota_observed_at':'2026-10-04T22:00:00+08:00'}
        path=self.root/'synthetic-not-an-authority.json';path.write_bytes(canonical(value))
        with patch.object(stage,'admission_for',return_value=value):
            plan,raw,_,_=stage.construct('nvarc-original-qwen3-native-multitask-993',path)
        self.assertEqual({k:v for k,v in raw.items() if k!='plan'},{k:v for k,v in self.raw.items() if k!='plan'})
        self.assertEqual(plan['task_specs'],self.plan['task_specs']);self.assertEqual(plan['producer_files'],self.plan['producer_files'])

    def test_acceptance_command_diagnostics_never_imply_gpu_gate(self):
        from tools import verify_nvarc_native_multitask as verifier
        for gate in (False,True):
            output=self.root/('synthetic-proof-'+str(gate)+'.json')
            with patch.object(verifier,'verify',return_value={'gpu_validation_gate':gate,'parent_outcome':'failed'}),patch('builtins.print'):
                code=verifier.main(['--archive','synthetic.zip','--package',str(self.package),
                    '--output',str(output),'--require-gpu-gate'])
            self.assertEqual(code,0 if gate else 2);self.assertEqual(json.loads(output.read_bytes())['gpu_validation_gate'],gate)

    def test_retained_identity_cannot_be_staged_in_another_directory(self):
        existing=self.root/'.irisx/native-solve-stage0/proposal/plan.json';existing.parent.mkdir(parents=True)
        existing.write_bytes(canonical({'run_id':self.run}))
        with patch.object(stage,'ROOT',self.root),patch.object(stage,'construct',side_effect=AssertionError('must reject before constructing')):
            with self.assertRaisesRegex(RuntimeError,'cannot be reused'):stage.stage(self.root/'other-package',self.run)

    def test_actual_offline_admitted_stage_preflight_init_roundtrip(self):
        review='nvarc-original-qwen3-native-multitask-994';run='nvarc-original-qwen3-native-multitask-993'
        _,reviewed,_=save.paths(review);_,package,journal=save.paths(run)
        checked=stage.stage(reviewed,review)
        value={'format':save.ADMISSION_FORMAT,'run_id':run,'reviewed_run_id':review,
            'reviewed_plan_digest':checked['plan_digest'],'reviewed_notebook_sha256':save.sha(reviewed/'kernel/notebook.ipynb'),
            'source_commit':save.REVIEW_COMMIT,'control_review_sha256':save.REVIEW_SHA,'maximum_paid_usd':0,
            'prior_sessions_reconciled':True,'quota_reservation_id':'SYNTHETIC TEST ONLY','reserved_quota_hours':2.5,
            'quota_observed_at':'2026-10-04T22:00:00+08:00','local_resource_admission':True,'ui_operator':'user',
            'private':True,'internet':False,'owner_editor_sessions_closed':True,'owner_clearance_ref':'SYNTHETIC TEST ONLY',
            'l4_quota_multiplier':2,'quick_save_authorized':True,'maximum_quick_saves':1,'agent_execution_authorized':False}
        path=self.root/'synthetic-fixture-only-admission.json';path.write_bytes(canonical(value))
        with patch.object(save,'token',side_effect=AssertionError('offline roundtrip must not access credentials')):
            admitted=save.prepare_admitted(reviewed,package,path)
            self.assertTrue(admitted['approved_for_runtime']);self.assertTrue(stage.preflight(package)['approved_for_runtime'])
            result=save.execute('init',package);self.assertFalse(result['review_only'])
        before=json.loads((reviewed/'stage-summary.json').read_bytes())['payload_sha256']
        after=json.loads((package/'stage-summary.json').read_bytes())['payload_sha256']
        self.assertEqual({k:v for k,v in before.items() if k!='plan'},{k:v for k,v in after.items() if k!='plan'})
        self.assertEqual(json.loads((journal/'save-ledger.json').read_bytes())['push_reserved'],0)

    def test_credential_failure_is_reserved_without_provider_send_or_retry(self):
        self.initialize()
        with patch.object(stage,'preflight',return_value={}),patch.object(save,'validate_admission',return_value=self.admission),\
                patch.object(save,'token',side_effect=RuntimeError('synthetic credential failure')),\
                patch.object(save,'client_for',side_effect=AssertionError('provider forbidden')):
            with self.assertRaisesRegex(RuntimeError,'frozen; no retry'):save.execute('save',self.package)
        ledger=json.loads((self.journal/'save-ledger.json').read_bytes())
        self.assertEqual(ledger['push_reserved'],1);self.assertEqual(ledger['events'][0]['sends'],0)


if __name__=='__main__':unittest.main()

"""Offline controller tests: deterministic provider doubles, never credentials."""
from tests.platform_requirements import requires_linux
from datetime import datetime, timedelta, timezone
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools import publish_nvarc_e12_run as p


class Request:
    def __init__(self, value): self.value = value
    def to_dict(self): return self.value


class Response:
    def __init__(self, body, status=200, headers=None):
        self.body, self.status_code = body, status
        self.headers = headers or {}; self.closed = False
    def iter_content(self, _): yield self.body
    def close(self): self.closed = True
    def __enter__(self): return self
    def __exit__(self, *_): self.close()


@requires_linux('Fixture and transport require directory fsync/O_DIRECTORY and POSIX locking')
class E12RunTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.package = self.root / 'package'; (self.package / 'runtime').mkdir(parents=True)
        self.journal = self.root / 'journal'
        self.plan = dict(run_id=p.RUN_ID, kernel_execution_type='RUN', agent_execution_authorized=True,
            publication_authorized=True, expected_notebook_version=11, expected_previous_version=10,
            notebook_numeric_id=p.KERNEL_ID, maximum_notebook_wall_seconds=3600,
            resource_admission={'quota_policy': 'owner-positive-free-quota-waiver-v1'})
        self.meta = dict(id=p.REF, title=p.SLUG, is_private=True, enable_gpu=True, enable_internet=False,
            machine_shape='NvidiaL4', dataset_sources=[], competition_sources=['arc-prize-2026-arc-agi-2'],
            kernel_sources=['sorokin/pip-install-unsloth-flash-patch/2'],
            model_sources=['sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'],
            docker_image='gcr.io/kaggle-private-byod/python@sha256:'+'1'*64, docker_image_pinning_type='original')
        self.notebook = {'nbformat':4, 'nbformat_minor':5, 'metadata':{}, 'cells':[
            {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':['print("synthetic")\n']}]}
        self.body = p.canonical(self.notebook)
        self.bindings = dict(package_manifest_sha256='a'*64, plan_sha256=p.sha(p.canonical(self.plan)),
            notebook_sha256=p.sha(self.body), source_digest=p.execution_source_digest(self.notebook),
            offline_package_verified=True)
        p.write(self.package / 'runtime/plan.json', self.plan)
        self.previous = self.root/'previous.ipynb'; self.previous.write_bytes(self.body)
        self.patchers = [patch.object(p,'ROOT',self.root),
            patch.object(p,'package_info', side_effect=lambda *a,**k:(self.plan,copy.deepcopy(self.meta),self.body,self.bindings)),
            patch.object(p,'request',side_effect=self.request),
            patch.object(p,'capture_prepared',side_effect=lambda req,wire:json.dumps(wire).encode()),
            patch.object(p,'sdk_request',side_effect=lambda name,**kw:Request(self.api_wire(kw))),
            patch('tools.nvarc_e12_admission.validate_resource_snapshot',create=True)]
        for mock in self.patchers: mock.start()
        self.review = self.root/'review.json'

    def tearDown(self):
        for mock in reversed(self.patchers): mock.stop()
        self.temp.cleanup()

    @staticmethod
    def api_wire(fields):
        return {key.split('_')[0]+''.join(s.title() for s in key.split('_')[1:]):value for key,value in fields.items()}

    def request(self,*args,**kwargs):
        _,wire,bindings=p.request_fields(self.package,current=False)
        return Request(wire),wire,bindings

    def initialize(self):
        binding=p.prepare(self.package,self.journal,self.previous)
        p.write(self.review,dict(binding,verdict='PASS',reviewer='independent synthetic reviewer',reviewed_at=p.utc()))

    def client(self,kind='accepted'):
        sends=[]
        raw=dict(ref=p.REF,url=p.PUBLIC_URL,versionNumber=p.VERSION,kernelId=p.KERNEL_ID)
        if kind=='wrong-version': raw['versionNumber']=p.VERSION+1
        if kind=='wrong-id': raw['kernelId']=1
        if kind=='wrong-slug': raw['ref']='danielwuu/other'
        if kind=='invalid-model': raw['invalidModelSources']=['wrong']
        if kind=='error': raw['error']='synthetic'
        def network(prepared,**kwargs):
            sends.append(prepared.url)
            self.assertFalse(kwargs['allow_redirects']); self.assertEqual(kwargs['timeout'],(15,120))
            if kind=='timeout': raise TimeoutError('do not retain this text')
            if kind=='interrupt': raise KeyboardInterrupt()
            if kind=='oversize': return Response(b'x'*(p.MAX_JSON+1))
            return Response(p.canonical(raw),400 if kind=='http400' else 200)
        session=NS(send=network,adapters={'https':NS(max_retries=NS(total=0))})
        def save(req):
            ledger=p.read(self.journal/'ledger.json')
            self.assertEqual(ledger['publication_reserved'],1); self.assertTrue(p.claim_path().exists())
            body=json.dumps(req.to_dict()).encode()
            prepared=NS(method='POST',url=p.SAVE_URL,body=body)
            if kind=='wrong-api': prepared.url=p.API+'GetKernel'
            if kind=='changed-body': prepared.body=body.replace(b'SAVE_AND_RUN_ALL',b'QUICK_SAVE')
            if kind=='duplicate-json': prepared.body=body[:-1]+b',"id":137327571}'
            response=session.send(prepared)
            if kind=='double-send': session.send(prepared)
            raw_result=p.parse(response._content)
            return NS(ref=raw_result.get('ref'),url=raw_result.get('url'),
                version_number=raw_result.get('versionNumber'),kernel_id=raw_result.get('kernelId'),
                error=raw_result.get('error'),to_dict=lambda:raw_result)
        class Client:
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def http_client(self): return NS(_init_session=lambda:None,_session=session)
            kernels=NS(kernels_api_client=NS(save_kernel=save))
        return Client(),sends

    def do_publish(self,kind='accepted',source_fail=False):
        client,sends=self.client(kind)
        fresh=dict(remaining_free_seconds=120, reserved_seconds=0,pay_to_scale_enabled=False)
        with patch.object(p,'official_client',return_value=client),\
             patch.object(p,'current_source',side_effect=RuntimeError('changed') if source_fail else None,
                          return_value={'version':p.PREVIOUS_VERSION,'observed_at':p.utc()}),\
             patch.object(p,'quota_snapshot',return_value=fresh):
            result=p.publish(self.package,self.journal,self.review)
        return result,sends

    def test_independent_request_dictionary_has_fixed_native_run_bounds(self):
        fields,wire,_=p.request_fields(self.package)
        self.assertEqual(wire['id'],137327571); self.assertEqual(wire['slug'],p.REF)
        self.assertEqual(wire['sessionTimeoutSeconds'],3600)
        self.assertEqual(wire['kernelExecutionType'],'SAVE_AND_RUN_ALL')
        self.assertEqual(wire['text'].encode(),self.body)
        self.assertEqual(wire['kernelDataSources'],['sorokin/pip-install-unsloth-flash-patch/2'])
        self.assertFalse(wire['enableInternet']); self.assertFalse(wire['enableTpu'])
        self.assertTrue(wire['isPrivate']); self.assertEqual(wire['machineShape'],'NvidiaL4')
        self.assertEqual(fields['id'],137327571)

    def test_rejects_nonexact_destination_mounts_privacy_and_shape(self):
        for key,value in [('id','danielwuu/other'),('title','renamed'),('is_private',False),
                ('enable_internet',True),('machine_shape','NvidiaTeslaT4'),('dataset_sources',['extra']),
                ('competition_sources',[]),('kernel_sources',['sorokin/pip-install-unsloth-flash-patch']),
                ('model_sources',['sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/2'])]:
            with self.subTest(key=key):
                original=self.meta[key]; self.meta[key]=value
                try:
                    with self.assertRaises(RuntimeError): p.request_fields(self.package)
                finally: self.meta[key]=original

    def test_acceptance_is_exact_and_second_send_is_impossible(self):
        self.initialize(); result,sends=self.do_publish()
        self.assertTrue(result['accepted']); self.assertEqual(sends,[p.SAVE_URL])
        ledger=p.read(self.journal/'ledger.json')
        self.assertEqual(ledger['events'][-1]['sends'],1)
        self.assertEqual(ledger['events'][-1]['raw_receipt_sha256'],p.sha(p.read_bytes(self.journal/'save-receipt.raw.json')))
        with self.assertRaisesRegex(RuntimeError,'already reserved'): self.do_publish()

    def test_failed_unknown_and_interrupted_sends_freeze_without_duplicate(self):
        for kind in ('wrong-version','wrong-id','wrong-slug','invalid-model','error','timeout','interrupt',
                     'http400','oversize','double-send','wrong-api','changed-body','duplicate-json'):
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory() as folder,patch.object(p,'ROOT',Path(folder)):
                    old=self.journal; self.journal=Path(folder)/'journal'
                    try:
                        self.initialize()
                        with self.assertRaisesRegex(RuntimeError,'identity frozen'): self.do_publish(kind)
                        ledger=p.read(self.journal/'ledger.json')
                        self.assertEqual(ledger['publication_reserved'],1)
                        self.assertLessEqual(ledger['events'][-1]['sends'],1)
                        self.assertNotIn('do not retain this text',json.dumps(ledger))
                        with self.assertRaisesRegex(RuntimeError,'already reserved'): self.do_publish()
                    finally: self.journal=old

    def test_preflight_failure_does_not_consume_run_mutation(self):
        self.initialize()
        with self.assertRaisesRegex(RuntimeError,'changed'): self.do_publish(source_fail=True)
        self.assertFalse(p.claim_path().exists())
        self.assertEqual(p.read(self.journal/'ledger.json')['publication_reserved'],0)

    def test_unknown_review_field_and_changed_wire_fail_before_auth(self):
        self.initialize(); review=p.read(self.review); review['unreviewed']=True; p.write(self.review,review)
        with patch.object(p,'official_client',side_effect=AssertionError('auth forbidden')):
            with self.assertRaisesRegex(RuntimeError,'independent PASS'): p.publish(self.package,self.journal,self.review)
        del review['unreviewed']; p.write(self.review,review)
        path=self.journal/'prepared-request.body'; path.write_bytes(path.read_bytes()+b' ')
        with patch.object(p,'official_client',side_effect=AssertionError('auth forbidden')):
            with self.assertRaisesRegex(RuntimeError,'binding changed'): p.publish(self.package,self.journal,self.review)

    def test_global_claim_blocks_another_journal_and_crash_without_receipt(self):
        self.initialize(); p.write(p.claim_path(),{'reserved':'synthetic'})
        with self.assertRaisesRegex(RuntimeError,'already reserved'): p.prepare(self.package,self.root/'new',self.previous)
        with self.assertRaisesRegex(RuntimeError,'already reserved'): self.do_publish()

    def test_duplicate_prepared_json_and_unknown_keys_fail_closed(self):
        _,wire,_=p.request_fields(self.package)
        for body in (p.canonical(dict(wire,extra=True)),p.canonical(wire)[:-1]+b',"id":137327571}'):
            with self.assertRaises(RuntimeError): p.wire_body(NS(method='POST',url=p.SAVE_URL,body=body),wire)

    def test_primary_call_retains_raw_and_bounds_requests(self):
        raw=b'{"actual": 1}'
        session=NS(send=lambda *a,**k:Response(raw),adapters={'https':NS(max_retries=NS(total=0))})
        def method(req):
            response=session.send(NS(method='POST',url=p.API+'GetKernel',body=p.canonical(req.to_dict())))
            return p.parse(response._content)
        client=NS(http_client=lambda:NS(_init_session=lambda:None,_session=session),
                  kernels=NS(kernels_api_client=NS(get_kernel=method)))
        result=p.primary_call(client,'get_kernel',Request({'userName':p.OWNER,'kernelSlug':p.SLUG}),self.root/'raw.json')
        self.assertEqual(result,{'actual':1}); self.assertEqual((self.root/'raw.json').read_bytes(),raw)

    def test_raw_receipt_needs_numeric_id_version_and_source_success(self):
        good=dict(ref=p.REF,url=p.PUBLIC_URL,versionNumber=p.VERSION,kernelId=p.KERNEL_ID)
        typed=NS(ref=p.REF,url=p.PUBLIC_URL,version_number=p.VERSION,kernel_id=p.KERNEL_ID,error='')
        self.assertTrue(p.receipt_is_accepted(good,typed))
        for key,value in [('versionNumber',True),('kernelId',str(p.KERNEL_ID)),('url',p.PUBLIC_URL+'/10'),
                          ('ref','wrong'),('unknown',True),('invalidKernelSources',['wrong'])]:
            with self.subTest(key=key):
                with self.assertRaises(RuntimeError): p.receipt_is_accepted(dict(good,**{key:value}),typed)

    def test_documented_historical_receipt_ref_is_accepted_without_general_rewriting(self):
        historical={'kernelId':137327571,'ref':'/code/danielwuu/stage4-e10-probe-20261006-001',
                    'url':'https://www.kaggle.com/code/danielwuu/stage4-e10-probe-20261006-001','versionNumber':p.VERSION}
        typed=NS(kernel_id=137327571,ref=historical['ref'],url=historical['url'],version_number=p.VERSION,error='')
        self.assertTrue(p.receipt_is_accepted(historical,typed))
        for value in ('/code/'+p.REF+'/', '/notebooks/'+p.REF, 'https://www.kaggle.com/code/'+p.REF):
            with self.assertRaises(RuntimeError): p.receipt_is_accepted(dict(historical,ref=value),typed)
        typed.ref=p.REF
        with self.assertRaisesRegex(RuntimeError,'disagree'): p.receipt_is_accepted(historical,typed)

    def accepted_ledger(self):
        self.initialize()
        ledger=p.read(self.journal/'ledger.json')
        ledger.update(accepted=True,publication_reserved=1,provider_version=p.VERSION)
        p.write(self.journal/'ledger.json',ledger)

    def test_status_is_bracketed_exact_version_and_queued_is_not_terminal(self):
        self.accepted_ledger(); client,_=self.client()
        observation=dict(version=p.VERSION,source_digest=self.bindings['source_digest'],settings_sha256='b'*64)
        for state in ('QUEUED','COMPLETE'):
            ledger=p.read(self.journal/'ledger.json'); ledger.pop('last_status_at',None)
            p.write(self.journal/'ledger.json',ledger)
            with patch.object(p,'official_client',return_value=client),\
                 patch.object(p,'current_source',return_value=observation) as sources,\
                 patch.object(p,'primary_call',return_value=NS(status=NS(name=state))):
                result=p.status(self.package,self.journal)
            self.assertEqual(sources.call_count,2)
            self.assertEqual(result['terminal'],state=='COMPLETE')
            self.assertEqual(result['version'],p.VERSION)
        with self.assertRaisesRegex(RuntimeError,'60 seconds'): p.status(self.package,self.journal)

    def test_status_version_drift_never_authorizes_output(self):
        self.accepted_ledger(); client,_=self.client()
        before=dict(version=p.VERSION,source_digest='a'*64,settings_sha256='b'*64)
        after=dict(before,version=p.VERSION+1)
        with patch.object(p,'official_client',return_value=client),\
             patch.object(p,'current_source',side_effect=[before,after]),\
             patch.object(p,'primary_call',return_value=NS(status=NS(name='COMPLETE'))):
            with self.assertRaisesRegex(RuntimeError,'status read failed'): p.status(self.package,self.journal)
        self.assertFalse(p.read(self.journal/'ledger.json').get('terminal_observed',False))

    def test_current_read_accepts_only_literal_historical_normalizations(self):
        actual=dict(id=p.KERNEL_ID,ref=p.REF,title=p.SLUG,current_version_number=9,
            is_private=True,enable_internet=False,enable_gpu=True,enable_tpu=False,
            language='python',kernel_type='notebook',machine_shape='NvidiaL4',
            docker_image=self.meta['docker_image'],dataset_data_sources=[],
            competition_data_sources=self.meta['competition_sources'],
            kernel_data_sources=['sorokin/pip-install-unsloth-flash-patch'],
            model_data_sources=['sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1'])
        raw=self.root/'source.json'; raw.write_bytes(b'{}')
        result=NS(metadata=NS(**actual),blob=NS(source=self.body.decode()))
        with patch.object(p,'primary_call',return_value=result):
            observed=p.current_source(None,self.package,raw,9,self.bindings['source_digest'])
            self.assertEqual(len(observed['provider_read_normalizations']),2)
            self.assertFalse(observed['dependency_version_echo_verified'])
            for key,value in [('kernel_data_sources',['sorokin/pip-install-unsloth-flash-patch/3']),
                              ('model_data_sources',['sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/2']),
                              ('is_private',False),('current_version_number',10)]:
                original=getattr(result.metadata,key); setattr(result.metadata,key,value)
                try:
                    with self.assertRaises(RuntimeError):
                        p.current_source(None,self.package,raw,9,self.bindings['source_digest'])
                finally: setattr(result.metadata,key,original)

    def test_quota_evidence_uses_primary_and_full_timedelta_days(self):
        raw={'gpuQuota':{'timeUsed':'96496.8659s','timeReserved':'0s','totalTimeAllowed':'108000s'},
             'tpuQuota':{},'quotaRefreshTime':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()}
        result=NS(gpu_quota=NS(time_used=timedelta(seconds=96496.8659),time_reserved=timedelta(0),
                             total_time_allowed=timedelta(seconds=108000),is_pay_to_scale_enabled=False))
        path=self.root/'quota.raw.json'
        def primary(*args,**kwargs):
            path.write_bytes(p.canonical(raw)); return result
        with patch.object(p,'primary_call',side_effect=primary):
            observed=p.quota_snapshot(None,path)
        self.assertAlmostEqual(observed['remaining_free_seconds'],11503.1341)
        self.assertEqual(observed['typed_projection_sha256'],p.sha(p.read_bytes(path.with_suffix('.typed.json'))))
        self.assertEqual(observed['primary_sha256'],p.sha(path.read_bytes()))

    def test_retrieval_reserves_exact_version_and_one_anonymous_bounded_file(self):
        self.accepted_ledger(); ledger=p.read(self.journal/'ledger.json')
        ledger['terminal_observed']=True; p.write(self.journal/'ledger.json',ledger)
        sent=[]; downloaded=[]; target='https://www.kaggleusercontent.com/kf/12345/'+p.RUN_ID+'-delivery.zip?secret=DO-NOT-RETAIN'
        def network(prepared,**kwargs):
            sent.append(p.parse(prepared.body)); self.assertFalse(kwargs['allow_redirects'])
            return Response(b'',302,{'Location':target})
        session=NS(send=network,adapters={'https':NS(max_retries=NS(total=0))})
        def output(req):
            return session.send(NS(method='POST',url=p.API+'DownloadKernelOutput',body=p.canonical(req.to_dict())))
        class Client:
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def http_client(self): return NS(_init_session=lambda:None,_session=session)
            kernels=NS(kernels_api_client=NS(download_kernel_output=output))
        class Downloads:
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def get(self,url,**kwargs):
                downloaded.append(url)
                self_auth=kwargs['auth'](NS(headers={}))
                self_outer.assertEqual(self_auth.headers,{})
                self_outer.assertFalse(kwargs['allow_redirects'])
                return Response(b'synthetic envelope',200)
        self_outer=self
        with patch.object(p,'official_client',return_value=Client()),\
             patch.object(p,'current_source',return_value={}),\
             patch.dict('sys.modules',{'requests':NS(Session=Downloads)}),\
             patch('tools.nvarc_e12_delivery_envelope.verify_envelope',return_value={'verified':'synthetic'}) as verifier:
            result=p.retrieve(self.package,self.journal)
        self.assertTrue(result['delivery_envelope_verified'])
        self.assertEqual(len(sent),1); self.assertEqual(sent[0]['versionNumber'],p.VERSION)
        self.assertEqual(sent[0]['filePath'],p.RUN_ID+'-delivery.zip')
        self.assertEqual(downloaded,[target]); self.assertEqual(verifier.call_count,1)
        self.assertNotIn('DO-NOT-RETAIN',(self.journal/'ledger.json').read_text())
        with self.assertRaisesRegex(RuntimeError,'one terminal retrieval'): p.retrieve(self.package,self.journal)

    def test_retrieval_failure_is_consumed_without_repeat(self):
        self.accepted_ledger(); ledger=p.read(self.journal/'ledger.json')
        ledger['terminal_observed']=True; p.write(self.journal/'ledger.json',ledger)
        with patch.object(p,'official_client',side_effect=RuntimeError('synthetic auth failure')):
            with self.assertRaisesRegex(RuntimeError,'no repeat'): p.retrieve(self.package,self.journal)
        ledger=p.read(self.journal/'ledger.json')
        self.assertEqual(ledger['retrieval_reserved'],1)
        self.assertEqual(ledger['events'][-1]['state'],'failed-or-partial-no-repeat')

    def test_terminal_log_fallback_preserves_log_without_signed_urls_or_download(self):
        self.accepted_ledger(); ledger=p.read(self.journal/'ledger.json')
        ledger.update(terminal_observed=True,retrieval_reserved=1); p.write(self.journal/'ledger.json',ledger)
        raw={'log':'synthetic quota-killed log\n','files':[{'fileName':'partial.txt','url':'https://secret.invalid/DO-NOT-SAVE'}]}
        session=NS(send=lambda *a,**k:Response(p.canonical(raw)),adapters={'https':NS(max_retries=NS(total=0))})
        def logs(req):
            self.assertEqual(req.to_dict()['pageSize'],1)
            response=session.send(NS(method='POST',url=p.API+'ListKernelSessionOutput',body=p.canonical(req.to_dict())))
            return NS(log=p.parse(response._content)['log'])
        class Client:
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def http_client(self): return NS(_init_session=lambda:None,_session=session)
            kernels=NS(kernels_api_client=NS(list_kernel_session_output=logs))
        observation=dict(version=p.VERSION,source_digest='a'*64,settings_sha256='b'*64)
        with patch.object(p,'official_client',return_value=Client()),\
             patch.object(p,'current_source',return_value=observation):
            result=p.terminal_logs(self.package,self.journal)
        self.assertTrue(result['log_retained']); self.assertFalse(result['delivery_envelope_verified'])
        self.assertEqual((self.journal/'provider.log').read_text(),raw['log'])
        self.assertNotIn('DO-NOT-SAVE',(self.journal/'ledger.json').read_text())
        with self.assertRaisesRegex(RuntimeError,'one terminal log'): p.terminal_logs(self.package,self.journal)

    def test_genuine_sdk_empty_redirect_capture_precedes_json_parser(self):
        if importlib.util.find_spec('kagglesdk') is None: self.skipTest('optional official SDK not installed')
        from kagglesdk import KaggleClient
        from kagglesdk.kaggle_env import KaggleEnv
        from kagglesdk.kernels.types.kernels_api_service import ApiDownloadKernelOutputRequest
        import requests
        request = ApiDownloadKernelOutputRequest()
        request.owner_slug=p.OWNER; request.kernel_slug=p.SLUG
        request.version_number=p.VERSION; request.file_path=p.RUN_ID+'-delivery.zip'
        sent=[]; checkpoints=[]
        def simulated(prepared, **kwargs):
            sent.append(prepared.url)
            response=requests.Response(); response.status_code=302
            response.headers['Content-Type']='application/json'
            response.headers['Location']='https://www.kaggleusercontent.com/kf/12345/synthetic.zip'
            response._content=b''; response._content_consumed=True
            return response
        with KaggleClient(env=KaggleEnv.PROD,verbose=False,api_token='OFFLINE-NOT-A-CREDENTIAL') as client:
            session=p.bounded_session(client); session.send=simulated
            with self.assertRaises(requests.exceptions.JSONDecodeError):
                client.kernels.kernels_api_client.download_kernel_output(request)
            response=p.capture_output_response(client,request,lambda:checkpoints.append('reserved'))
            self.assertEqual(response.status_code,302); response.close()
            self.assertEqual(checkpoints,['reserved']); self.assertEqual(len(sent),2)
            self.assertIs(session.send,simulated)

    def test_genuine_official_sdk_prepared_request_is_offline_and_exact(self):
        if importlib.util.find_spec('kagglesdk') is None: self.skipTest('optional official SDK not installed')
        # Undo only the request/capture doubles for this actual serialization test.
        self.patchers[2].stop(); self.patchers[3].stop()
        try:
            with patch('requests.sessions.Session.send',side_effect=AssertionError('network forbidden')):
                request,wire,_=p.request(self.package,current=False)
                body=p.capture_prepared(request,wire)
            self.assertEqual(p.parse(body),wire)
            self.assertEqual(p.parse(body)['text'].encode(),self.body)
        finally:
            self.patchers[2].start(); self.patchers[3].start()


if __name__ == '__main__':
    unittest.main()

"""Offline new-notebook QUICK_SAVE transport and exact official SDK wire tests."""
from tests.platform_requirements import requires_linux
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools import publish_nvarc_uncapped_quicksave as p

HAS_SDK = importlib.util.find_spec('kagglesdk') is not None


class Request:
    def __init__(self, value): self.value = value
    def to_dict(self): return self.value


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code, self.closed = body, status, False
    def iter_content(self, _): yield self.body
    def close(self): self.closed = True


class NewQuickSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package, self.journal = self.root/'package', self.root/'journal'
        self.review = self.root/'review.json'
        self.plan = dict(run_id=p.RUN_ID, kernel_execution_type='QUICK_SAVE', owner_editor_only=True,
            agent_execution_authorized=False, approved_for_runtime=False, resource_admission=None,
            publication_authorized=True, paid_usd_ceiling=0)
        self.meta = dict(id=p.REF, title=p.SLUG, code_file='notebook.ipynb', is_private=True,
            enable_gpu=True, enable_internet=False, machine_shape='NvidiaL4', dataset_sources=[],
            competition_sources=['arc-prize-2026-arc-agi-2'],
            kernel_sources=['sorokin/pip-install-unsloth-flash-patch/2'],
            model_sources=['sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'],
            docker_image='gcr.io/kaggle-private-byod/python@sha256:'+'1'*64,
            docker_image_pinning_type='original')
        self.notebook = {'nbformat':4, 'nbformat_minor':5, 'metadata':{}, 'cells':[
            {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':['CONFIRM_UNCAPPED_OWNER_RUN = False\nprint("synthetic")\n']}]}
        self.body = p.canonical(self.notebook)
        self.bindings = dict(package_manifest_sha256='a'*64, plan_sha256=p.sha(p.canonical(self.plan)),
            metadata_sha256=p.sha(p.canonical(self.meta)), notebook_sha256=p.sha(self.body),
            source_digest=p.execution_source_digest(self.notebook), offline_package_verified=True)
        self.patchers = [patch.object(p,'ROOT', self.root/'worktree'),
            patch.object(p,'package_info',side_effect=lambda *_: (self.plan, copy.deepcopy(self.meta), self.body, self.bindings))]
        if not HAS_SDK:
            self.patchers.extend([patch.object(p,'request',side_effect=self.request),
                patch.object(p,'capture_prepared',side_effect=lambda req,wire:json.dumps(wire).encode()),
                patch.object(p,'source_request',side_effect=lambda ref=p.REF:Request({'userName':ref.split('/')[0],'kernelSlug':ref.split('/')[1]}))])
        for patcher in self.patchers: patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers): patcher.stop()
        self.temp.cleanup()

    def request(self, package):
        _, wire, bindings = p.request_fields(package)
        return Request(wire), wire, bindings

    def initialize(self,newness_proof='source-404'):
        value = p.prepare(self.package,self.journal,newness_proof=newness_proof)
        p.write(self.review,dict(value,verdict='PASS',reviewer='independent offline test',reviewed_at=p.utc()))

    def raw_source(self, kernel_id=400000001):
        notebook = copy.deepcopy(self.notebook)
        notebook['metadata']['kaggle'] = {'SaveType':'QUICK_SAVE'}
        meta = dict(id=kernel_id,ref=p.REF,title=p.SLUG,currentVersionNumber=1,isPrivate=True,
            enableInternet=False,enableGpu=True,enableTpu=False,language='python',kernelType='notebook',
            machineShape='NvidiaL4',dockerImage=self.meta['docker_image'],
            kernelDataSources=['sorokin/pip-install-unsloth-flash-patch'],
            competitionDataSources=self.meta['competition_sources'],
            modelDataSources=['sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1'])
        return dict(metadata=meta,blob=dict(source=p.canonical(notebook).decode()))

    def client(self, kind='accepted', absent_status=404):
        calls=[]
        raw = dict(ref=p.REF,url=p.PUBLIC_URL,versionNumber=1,kernelId=400000001)
        if kind=='old-id': raw['kernelId']=137327571
        if kind=='wrong-version': raw['versionNumber']=2
        if kind=='wrong-slug': raw['ref']='danielwuu/other'
        if kind=='wrong-url': raw['url']=p.PUBLIC_URL+'/1'
        if kind=='invalid-mount': raw['invalidModelSources']=['wrong']
        if kind=='error': raw['error']='synthetic-error'
        def network(prepared,**kwargs):
            calls.append(prepared.url)
            self.assertFalse(kwargs['allow_redirects'])
            self.assertEqual(kwargs['timeout'],(15,120))
            if prepared.url==p.LIST_URL:
                rows=[dict(ref=p.PRIVATE_ANCHOR_REF,title=p.PRIVATE_ANCHOR_REF.split('/')[1],
                    author='Daniel Wu',lastRunTime='2026-10-08T00:53:49.567Z')]
                if kind=='existing-returned-id':rows.append(dict(id=400000001,ref=p.OWNER+'/another-existing',isPrivate=True))
                return Response(p.canonical(dict(kernels=rows)))
            if prepared.url==p.SOURCE_URL:
                if p.parse(prepared.body).get('kernelSlug')==p.PRIVATE_ANCHOR_REF.split('/')[1]:
                    return Response(p.canonical(dict(metadata=dict(id=137327571,ref=p.PRIVATE_ANCHOR_REF,isPrivate=True))))
                before = not p.claim_path().exists()
                if before: return Response(b'{"message":"synthetic exact absence"}',absent_status)
                source = self.raw_source()
                if kind=='readback-wrong-version':source['metadata']['currentVersionNumber']=2
                if kind=='readback-http403':return Response(b'{}',403)
                return Response(p.canonical(source))
            self.assertEqual(prepared.url,p.SAVE_URL)
            if kind=='timeout':raise TimeoutError('secret-like exception text must not be retained')
            if kind=='interrupt':raise KeyboardInterrupt()
            if kind=='oversize':return Response(b'x'*(p.MAX_JSON+1))
            return Response(p.canonical(raw),400 if kind=='http400' else 200)
        session=NS(send=network,adapters={'https':NS(max_retries=NS(total=0))})
        def get_kernel(req):
            return session.send(NS(method='POST',url=p.SOURCE_URL,body=p.canonical(req.to_dict())))
        def list_kernels(req):
            return session.send(NS(method='POST',url=p.LIST_URL,body=p.canonical(req.to_dict())))
        def save_kernel(req):
            self.assertTrue(p.claim_path().exists())
            self.assertEqual(p.read(self.journal/'ledger.json')['publication_reserved'],1)
            # The exact real-SDK capture is the reviewed serialization fixture.
            body=p.read_bytes(self.journal/'prepared-request.body')
            prepared=NS(method='POST',url=p.SAVE_URL,body=body)
            if kind=='changed-wire':prepared.body=body.replace(b'QUICK_SAVE',b'SAVE_AND_RUN_ALL')
            if kind=='wrong-endpoint':prepared.url=p.SOURCE_URL
            if kind=='added-id':prepared.body=body[:-1]+b',"id":137327571}'
            if kind=='added-timeout':prepared.body=body[:-1]+b',"sessionTimeoutSeconds":3600}'
            if kind=='duplicate-key':prepared.body=body[:-1]+b',"slug":"'+p.REF.encode()+b'"}'
            response=session.send(prepared)
            if kind=='double-send':session.send(prepared)
            value=p.parse(response._content)
            return NS(ref=value.get('ref'),url=value.get('url'),version_number=value.get('versionNumber'),
                kernel_id=value.get('kernelId'),error=value.get('error'),to_dict=lambda:value)
        class Client:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def http_client(self):return NS(_init_session=lambda:None,_session=session)
            kernels=NS(kernels_api_client=NS(get_kernel=get_kernel,save_kernel=save_kernel,list_kernels=list_kernels))
        return Client(),calls

    def publish(self,kind='accepted',absent_status=404):
        client,calls=self.client(kind,absent_status)
        with patch.object(p,'official_client',return_value=client):
            result=p.publish(self.package,self.journal,self.review)
        return result,calls

    def test_closed_new_request_has_no_id_or_timeout(self):
        fields,wire,_=p.request_fields(self.package)
        self.assertNotIn('id',fields);self.assertNotIn('id',wire)
        self.assertNotIn('session_timeout_seconds',fields);self.assertNotIn('sessionTimeoutSeconds',wire)
        self.assertEqual(wire['slug'],p.REF);self.assertEqual(wire['newTitle'],p.SLUG)
        self.assertEqual(wire['kernelExecutionType'],'QUICK_SAVE')
        self.assertTrue(wire['isPrivate']);self.assertFalse(wire['enableInternet'])
        self.assertEqual(wire['machineShape'],'NvidiaL4')
        self.assertEqual(wire['text'].encode(),self.body)

    @unittest.skipUnless(HAS_SDK,'requires installed official SDK; run with iris-kaggle-cli/bin/python')
    def test_official_sdk_actual_session_send_capture_is_offline_and_exact(self):
        import requests
        with patch.object(requests.Session,'send',side_effect=AssertionError('network forbidden')):
            req,wire,_=p.request(self.package)
            body=p.capture_prepared(req,wire)
        self.assertEqual(p.parse(body),wire)
        self.assertNotIn('id',req.to_dict())
        self.assertNotIn('sessionTimeoutSeconds',req.to_dict())
        self.assertEqual(req.kernel_execution_type.name,'QUICK_SAVE')
        self.assertNotIn(b'OFFLINE-NOT-A-CREDENTIAL',body)

    def test_identity_privacy_mount_mutations_fail_closed(self):
        for key,value in [('id','danielwuu/other'),('title','other'),('is_private',False),
            ('enable_internet',True),('enable_gpu',False),('machine_shape','NvidiaTeslaT4'),
            ('dataset_sources',['extra']),('competition_sources',[]),('kernel_sources',[]),
            ('model_sources',[]),('docker_image_pinning_type','latest'),('id_no',137327571),
            ('session_timeout_seconds',3600)]:
            with self.subTest(key=key):
                old=copy.deepcopy(self.meta)
                self.meta[key]=value
                try:
                    with self.assertRaises(RuntimeError):p.request_fields(self.package)
                finally:self.meta=old

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_success_one_save_and_source_only_readback(self):
        self.initialize();result,calls=self.publish()
        self.assertEqual(calls,[p.SOURCE_URL,p.SAVE_URL,p.SOURCE_URL])
        self.assertEqual(result['kernel_id'],400000001)
        self.assertTrue(result['source_only_verified'])
        self.assertFalse(result['auto_run_requested']);self.assertFalse(result['runtime_state_queried'])
        self.assertEqual(result['provider_save_type'],'QUICK_SAVE')
        ledger=p.read(self.journal/'ledger.json')
        self.assertTrue(ledger['accepted']);self.assertTrue(ledger['source_verified'])
        self.assertEqual(ledger['events'][0]['sends'],1)
        with self.assertRaisesRegex(RuntimeError,'already reserved'):self.publish()

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_403_is_not_404_and_existing_slug_never_updates(self):
        for status,reason in [(403,'403 forbidden'),(200,'already exists'),(401,'not return 404'),(500,'not return 404')]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                old=self.journal;self.journal=Path(folder)/'journal'
                try:
                    self.initialize()
                    with self.assertRaisesRegex(RuntimeError,reason):self.publish(absent_status=status)
                    self.assertFalse(p.claim_path().exists())
                    self.assertEqual(p.read(self.journal/'ledger.json')['publication_reserved'],0)
                    self.assertEqual(p.read(self.journal/'pre-send-source.http.json')['http_status'],status)
                finally:self.journal=old

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_ambiguous_rejected_malformed_and_mutated_save_freezes_identity(self):
        kinds=('old-id','wrong-version','wrong-slug','wrong-url','invalid-mount','error','timeout','interrupt',
            'oversize','http400','changed-wire','wrong-endpoint','added-id','added-timeout','duplicate-key','double-send')
        for kind in kinds:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder,patch.object(p,'ROOT',Path(folder)/'worktree'):
                old=self.journal;self.journal=Path(folder)/'journal'
                try:
                    self.initialize()
                    with self.assertRaisesRegex(RuntimeError,'identity frozen'):self.publish(kind)
                    ledger=p.read(self.journal/'ledger.json')
                    self.assertEqual(ledger['publication_reserved'],1)
                    self.assertLessEqual(ledger['events'][0]['sends'],1)
                    self.assertEqual(ledger['state'],'frozen-uncertain-no-retry')
                    self.assertNotIn('secret-like',json.dumps(ledger))
                    with self.assertRaisesRegex(RuntimeError,'already reserved'):self.publish()
                finally:self.journal=old

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_readback_failure_preserves_acceptance_and_forbids_resave(self):
        self.initialize()
        with self.assertRaisesRegex(RuntimeError,'SOURCE verification read failed'):self.publish('readback-http403')
        ledger=p.read(self.journal/'ledger.json')
        self.assertTrue(ledger['accepted']);self.assertEqual(ledger['kernel_id'],400000001)
        with self.assertRaisesRegex(RuntimeError,'already reserved'):self.publish()
        client,calls=self.client()
        with patch.object(p,'official_client',return_value=client):result=p.verify_source(self.package,self.journal)
        self.assertEqual(calls,[p.SOURCE_URL]);self.assertTrue(result['source_only_verified'])

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_actual_wire_review_and_package_hashes_rechecked_before_auth(self):
        self.initialize();review=p.read(self.review);review['unreviewed']=True;p.write(self.review,review)
        with patch.object(p,'official_client',side_effect=AssertionError('auth forbidden')):
            with self.assertRaisesRegex(RuntimeError,'independent PASS'):p.publish(self.package,self.journal,self.review)
        del review['unreviewed'];p.write(self.review,review)
        self.bindings['plan_sha256']='f'*64
        with patch.object(p,'official_client',side_effect=AssertionError('auth forbidden')):
            with self.assertRaisesRegex(RuntimeError,'binding changed'):p.publish(self.package,self.journal,self.review)

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_prepared_bytes_binding_is_exact_not_merely_json_equivalent(self):
        self.initialize();path=self.journal/'prepared-request.body';path.write_bytes(path.read_bytes()+b' ')
        with patch.object(p,'official_client',side_effect=AssertionError('auth forbidden')):
            with self.assertRaisesRegex(RuntimeError,'binding changed'):p.publish(self.package,self.journal,self.review)

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_global_claim_blocks_new_journal_and_is_write_once(self):
        self.initialize();p.write(p.claim_path(),{'frozen':True},exclusive=True)
        with self.assertRaises(FileExistsError):p.write(p.claim_path(),{'frozen':False},exclusive=True)
        self.assertTrue(p.read(p.claim_path())['frozen'])
        with self.assertRaisesRegex(RuntimeError,'already reserved'):p.prepare(self.package,self.root/'other')
        with self.assertRaisesRegex(RuntimeError,'already reserved'):self.publish()

    def test_source_rejects_wrong_identity_execution_and_save_type(self):
        raw=self.raw_source()
        result=p.verify_source_value(raw,self.package,400000001,self.bindings['source_digest'])
        self.assertEqual(result['provider_save_type'],'QUICK_SAVE')
        for key,value in [('id',137327571),('currentVersionNumber',2),('isPrivate',False),('ref','danielwuu/other')]:
            mutated=copy.deepcopy(raw);mutated['metadata'][key]=value
            with self.assertRaisesRegex(RuntimeError,'SOURCE new notebook'):p.verify_source_value(mutated,self.package,400000001,self.bindings['source_digest'])
        missing=copy.deepcopy(raw);notebook=p.parse(missing['blob']['source']);notebook['metadata']={}
        missing['blob']['source']=p.canonical(notebook).decode()
        result=p.verify_source_value(missing,self.package,400000001,self.bindings['source_digest'])
        self.assertFalse(result['provider_save_type_attested']);self.assertIsNone(result['provider_save_type'])
        self.assertFalse(result['runtime_state_attested'])
        for mode in ('run-save-type','executed','changed-code'):
            mutated=copy.deepcopy(raw);notebook=p.parse(mutated['blob']['source'])
            if mode=='missing-save-type':notebook['metadata']={}
            if mode=='run-save-type':notebook['metadata']['kaggle']['SaveType']='SAVE_AND_RUN_ALL'
            if mode=='executed':notebook['cells'][0]['execution_count']=1
            if mode=='changed-code':notebook['cells'][0]['source']=['print("changed")']
            mutated['blob']['source']=p.canonical(notebook).decode()
            with self.assertRaises(RuntimeError):p.verify_source_value(mutated,self.package,400000001,self.bindings['source_digest'])

    def test_raw_receipt_requires_new_numeric_id_and_version_one(self):
        raw=dict(ref=p.REF,url=p.PUBLIC_URL,versionNumber=1,kernelId=400000001)
        typed=NS(ref=p.REF,url=p.PUBLIC_URL,version_number=1,kernel_id=400000001,error='')
        self.assertEqual(p.receipt_is_accepted(raw,typed),400000001)
        for key,value in [('kernelId',True),('kernelId','400000001'),('kernelId',0),('kernelId',137327571),
            ('versionNumber',True),('versionNumber',2),('unknown',True)]:
            with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):p.receipt_is_accepted(dict(raw,**{key:value}),typed)

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_accepted_receipt_cannot_be_replaced_before_source_read(self):
        self.initialize();self.publish()
        receipt=self.journal/'save-receipt.raw.json'
        raw=p.read(receipt);raw['kernelId']=400000002;p.write(receipt,raw)
        with patch.object(p,'official_client',side_effect=AssertionError('auth forbidden')):
            with self.assertRaises(RuntimeError):p.verify_source(self.package,self.journal)

    def test_source_normalizes_provider_cell_strings_without_changing_code(self):
        raw=self.raw_source();notebook=p.parse(raw['blob']['source'])
        for cell in notebook['cells']:
            cell['source']=''.join(cell['source']);cell['id']='provider-added-cell-id'
        raw['blob']['source']=json.dumps(notebook,indent=2)
        result=p.verify_source_value(raw,self.package,400000001,self.bindings['source_digest'])
        self.assertTrue(result['owner_start_default_false_verified'])

    def listing_client(self,pages,statuses=None,anchor_status=200,anchor_metadata=None):
        calls=[]
        def network(prepared,**kwargs):
            if prepared.url==p.SOURCE_URL:
                self.assertEqual(p.parse(prepared.body)['kernelSlug'],p.PRIVATE_ANCHOR_REF.split('/')[1])
                meta=anchor_metadata if anchor_metadata is not None else dict(id=137327571,ref=p.PRIVATE_ANCHOR_REF,isPrivate=True)
                return Response(p.canonical(dict(metadata=meta)),anchor_status)
            self.assertEqual(prepared.url,p.LIST_URL)
            self.assertFalse(kwargs['allow_redirects'])
            wire=p.parse(prepared.body);calls.append(wire)
            index=len(calls)-1
            return Response(p.canonical(pages[index]),statuses[index] if statuses else 200)
        session=NS(send=network,adapters={'https':NS(max_retries=NS(total=0))})
        def list_kernels(req):
            return session.send(NS(method='POST',url=p.LIST_URL,body=p.canonical(req.to_dict())))
        def get_kernel(req):
            return session.send(NS(method='POST',url=p.SOURCE_URL,body=p.canonical(req.to_dict())))
        return NS(http_client=lambda:NS(_init_session=lambda:None,_session=session),
            kernels=NS(kernels_api_client=NS(list_kernels=list_kernels,get_kernel=get_kernel))),calls

    def list_request(self,token=''):
        wire=dict(group='PROFILE',sortBy='DATE_CREATED',pageSize=100,pageToken=token,user='',
            language='all',kernelType='all',outputType='all',dataset='',competition='',parentKernel='',search='')
        if not token:wire['page']=1
        return Request(wire)

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_complete_own_list_tracks_every_cursor_and_private_identity(self):
        anchor=dict(id=137327571,ref=p.OWNER+'/stage4-e10-probe-20261006-001',isPrivate=True)
        pages=[dict(kernels=[anchor],nextPageToken='opaque-2'),dict(kernels=[dict(id=2,ref=p.OWNER+'/another',isPrivate=False)])]
        client,calls=self.listing_client(pages)
        with patch.object(p,'own_list_request',side_effect=self.list_request):
            proof=p.confirm_absent_from_own_list(client,self.root/'inventory')
        self.assertEqual(len(calls),2);self.assertEqual(calls[1]['pageToken'],'opaque-2')
        self.assertNotIn('page',calls[1]);self.assertEqual(proof['notebook_count'],2)
        self.assertTrue(proof['pagination_complete']);self.assertFalse(proof['target_source_read'])
        self.assertFalse(proof['source_403_used_as_absence'])
        self.assertTrue(proof['operational_newness_verified']);self.assertTrue(proof['absent'])
        self.assertFalse(proof['atomic_namespace_absence_guaranteed'])
        self.assertFalse(proof['quicksave_draft_coverage_attested'])
        self.assertFalse(proof['create_only_semantics_verified'])

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_own_list_refuses_denials_incompleteness_and_foreign_or_existing_identity(self):
        anchor=dict(id=137327571,ref=p.OWNER+'/stage4-e10-probe-20261006-001',isPrivate=True)
        cases=[([dict(kernels=[anchor])],[403]),([dict(kernels=[anchor])],[401]),
            ([dict(kernels=[])],None),([dict(kernels=[dict(anchor,isPrivate=False)])],None),
            ([dict(kernels=[dict(anchor,ref='other/name')])],None),
            ([dict(kernels=[anchor,dict(id=2,ref=p.REF,isPrivate=True)])],None),
            ([dict(kernels=[anchor],nextPageToken='x'),dict(kernels=[anchor])],None),
            ([dict(kernels=[anchor],nextPageToken='x'),dict(kernels=[],nextPageToken='x')],None),
            ([dict(kernels=[anchor],nextPageToken=7)],None),
            ([dict(kernels=[anchor],error='denied')],None)]
        for index,(pages,statuses) in enumerate(cases):
            with self.subTest(index=index),patch.object(p,'own_list_request',side_effect=self.list_request):
                client,_=self.listing_client(pages,statuses)
                with self.assertRaises(RuntimeError):p.confirm_absent_from_own_list(client,self.root/f'inventory-{index}')

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_real_sparse_profile_projection_with_91_refs_verifies_separate_private_anchor(self):
        rows=[dict(ref=p.OWNER+f'/synthetic-{index:03d}',title=f'Synthetic {index}',
            author='Owner',lastRunTime='2026-10-08T00:53:49.567Z') for index in range(90)]
        rows.append(dict(ref=p.PRIVATE_ANCHOR_REF,title=p.PRIVATE_ANCHOR_REF.split('/')[1],
            author='Daniel Wu',lastRunTime='2026-10-08T00:53:49.567Z'))
        client,calls=self.listing_client([dict(kernels=rows)])
        with patch.object(p,'own_list_request',side_effect=self.list_request):
            proof=p.confirm_absent_from_own_list(client,self.root/'sparse-inventory')
        self.assertEqual(len(calls),1);self.assertEqual(proof['notebook_count'],91)
        self.assertTrue(proof['pagination_complete']);self.assertTrue(proof['private_anchor_source_verified'])
        self.assertEqual(proof['private_anchor_source']['ref'],p.PRIVATE_ANCHOR_REF)
        self.assertFalse(proof['numeric_id_inventory_complete']);self.assertEqual(proof['enumerated_kernel_ids'],[])
        self.assertEqual(proof['private_namespace_anchor_ids'],[137327571])

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_exact_provider_redactions_are_counted_with_incomplete_reference_coverage(self):
        rows=[dict(ref=p.OWNER+f'/synthetic-{index:03d}',title=f'Synthetic {index}',
            author='Owner',lastRunTime='2026-10-08T00:53:49.567Z') for index in range(91)]
        rows[0]['ref']=p.PRIVATE_ANCHOR_REF
        rows[34]=dict(p.REDACTED_OWN_LIST_ROW);rows[90]=dict(p.REDACTED_OWN_LIST_ROW)
        client,calls=self.listing_client([dict(kernels=rows)])
        with patch.object(p,'own_list_request',side_effect=self.list_request):
            proof=p.confirm_absent_from_own_list(client,self.root/'redacted-inventory')
        self.assertEqual(len(calls),1)
        self.assertEqual(proof['redacted_count'],2);self.assertEqual(proof['visible_reference_count'],89)
        self.assertEqual(proof['inventory_row_count'],91);self.assertFalse(proof['reference_coverage_complete'])
        self.assertEqual(proof['redacted_positions'],[dict(page=0,row=34),dict(page=0,row=90)])
        self.assertTrue(proof['pagination_complete']);self.assertTrue(proof['private_anchor_source_verified'])
        self.assertTrue(proof['visible_reference_noncollision']);self.assertFalse(proof['numeric_id_inventory_complete'])
        self.assertFalse(proof['atomic_namespace_absence_guaranteed'])

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_nonexact_redacted_or_other_ref_less_rows_are_rejected(self):
        bad_rows=[dict(title='[Private Notebook]'),dict(p.REDACTED_OWN_LIST_ROW,extra=True),
            dict(p.REDACTED_OWN_LIST_ROW,lastRunTime='2010-04-01T00:00:01Z'),
            dict(p.REDACTED_OWN_LIST_ROW,title='[Private notebook]'),{},None,
            dict(p.REDACTED_OWN_LIST_ROW,ref=None)]
        for index,row in enumerate(bad_rows):
            client,_=self.listing_client([dict(kernels=[dict(ref=p.PRIVATE_ANCHOR_REF),row])])
            with self.subTest(index=index),patch.object(p,'own_list_request',side_effect=self.list_request):
                with self.assertRaisesRegex(RuntimeError,'exact owned notebook ref'):
                    p.confirm_absent_from_own_list(client,self.root/f'bad-redaction-{index}')

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_sparse_inventory_needs_successful_exact_private_anchor_source(self):
        rows=[dict(ref=p.PRIVATE_ANCHOR_REF,title='Anchor',author='Owner',lastRunTime='2026-10-08T00:53:49.567Z')]
        cases=[(403,None),(401,None),(200,dict(id=1,ref=p.PRIVATE_ANCHOR_REF,isPrivate=True)),
            (200,dict(id=137327571,ref=p.OWNER+'/wrong',isPrivate=True)),
            (200,dict(id=137327571,ref=p.PRIVATE_ANCHOR_REF,isPrivate=False)),
            (200,dict(id='137327571',ref=p.PRIVATE_ANCHOR_REF,isPrivate=True))]
        for index,(status,meta) in enumerate(cases):
            client,_=self.listing_client([dict(kernels=rows)],anchor_status=status,anchor_metadata=meta)
            with self.subTest(index=index),patch.object(p,'own_list_request',side_effect=self.list_request):
                with self.assertRaisesRegex(RuntimeError,'private anchor SOURCE'):
                    p.confirm_absent_from_own_list(client,self.root/f'bad-anchor-{index}')

    def test_source_reader_rejects_nonallowlisted_anchor_before_provider_call(self):
        with self.assertRaisesRegex(RuntimeError,'predefined exact SOURCE'):
            p.source_response(None,self.root/'forbidden-source.json',ref=p.OWNER+'/unrelated')

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_own_list_page_ceiling_is_incomplete_and_never_absence(self):
        anchor=dict(id=137327571,ref=p.OWNER+'/stage4-e10-probe-20261006-001',isPrivate=True)
        client,_=self.listing_client([dict(kernels=[anchor],nextPageToken='still-more')])
        with patch.object(p,'own_list_request',side_effect=self.list_request),patch.object(p,'MAX_OWN_LIST_PAGES',1):
            with self.assertRaisesRegex(RuntimeError,'enumeration incomplete'):p.confirm_absent_from_own_list(client,self.root/'inventory')
        self.assertFalse((self.root/'inventory'/'inventory-census.json').exists())

    @unittest.skipUnless(HAS_SDK,'requires official SDK')
    def test_official_own_list_sdk_wire_matches_cli_mine_profile_semantics(self):
        from kagglesdk import KaggleClient
        from kagglesdk.kaggle_env import KaggleEnv
        for token in ('','opaque-cursor'):
            with KaggleClient(env=KaggleEnv.PROD,verbose=False,api_token='OFFLINE-NOT-A-CREDENTIAL') as client:
                captured=[]
                def stop(prepared,**kwargs):
                    self.assertEqual(prepared.url,p.LIST_URL)
                    captured.append(p.parse(prepared.body));raise p.CapturedRequest()
                client.http_client()._session.send=stop
                with self.assertRaises(p.CapturedRequest):client.kernels.kernels_api_client.list_kernels(p.own_list_request(token))
                self.assertEqual(captured,[self.list_request(token).to_dict()])

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_explicit_complete_own_list_mode_never_reads_denied_source_before_save(self):
        self.initialize('complete-own-list')
        with patch.object(p,'own_list_request',side_effect=self.list_request):
            result,calls=self.publish()
        self.assertEqual(calls,[p.LIST_URL,p.SOURCE_URL,p.SAVE_URL,p.SOURCE_URL])
        self.assertTrue(result['source_only_verified'])
        self.assertFalse((self.journal/'pre-send-source.json').exists())
        proof=p.read(self.journal/'pre-send-own-list/inventory-census.json')
        self.assertTrue(proof['operational_newness_verified'])
        self.assertFalse(proof['create_only_semantics_verified'])
        self.assertFalse(proof['quicksave_draft_coverage_attested'])

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_returned_id_must_be_absent_from_complete_own_inventory(self):
        self.initialize('complete-own-list')
        with patch.object(p,'own_list_request',side_effect=self.list_request):
            with self.assertRaisesRegex(RuntimeError,'identity frozen'):self.publish('existing-returned-id')
        ledger=p.read(self.journal/'ledger.json')
        self.assertFalse(ledger['accepted']);self.assertEqual(ledger['events'][0]['sends'],1)
        self.assertIn(400000001,ledger['events'][0]['absence']['enumerated_kernel_ids'])
        with self.assertRaisesRegex(RuntimeError,'already reserved'):self.publish()

    @requires_linux('Durable transport evidence requires O_DIRECTORY, directory fsync and fcntl locking')
    def test_newness_mode_requires_exact_independent_review(self):
        self.initialize('complete-own-list')
        ledger=p.read(self.journal/'ledger.json')
        self.assertEqual(p.review_binding(ledger)['newness_proof'],'complete-own-list')
        ledger['newness_proof']='source-404';p.write(self.journal/'ledger.json',ledger)
        with patch.object(p,'official_client',side_effect=AssertionError('auth forbidden')):
            with self.assertRaisesRegex(RuntimeError,'independent PASS'):p.publish(self.package,self.journal,self.review)

    def test_no_provider_runtime_status_quota_or_output_api_surface(self):
        import ast
        tree=ast.parse(Path(p.__file__).read_text())
        calls={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)
            and isinstance(node.value,ast.Attribute) and node.value.attr=='kernels_api_client'}
        self.assertEqual(calls,{'save_kernel','get_kernel','list_kernels'})
        self.assertFalse(any(hasattr(p,name) for name in ('status','observe_quota','retrieve','terminal_logs')))


if __name__=='__main__':unittest.main()

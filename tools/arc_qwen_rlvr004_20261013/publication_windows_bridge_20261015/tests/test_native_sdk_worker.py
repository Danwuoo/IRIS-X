"""Offline doubles only. No real SDK import, authentication or network calls."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


auth = load('test_windows_native_auth', 'native_auth.py')
worker = load('test_windows_sdk_worker', 'sdk_worker.py')
protocol = load('test_windows_sdk_protocol', 'protocol.py')


class Runtime:
    def __init__(self):
        self.guards = []
        self.events = []
    @contextmanager
    def credential_guard(self, allow_write=False):
        self.guards.append(allow_write)
        self.events.append(('guard', allow_write))
        yield


class Exchange:
    def __init__(self, events):
        self.events = events
        self.fail_intent = self.fail_accepted = False
    def check_ready(self):
        pass
    def intent(self, metadata):
        self.events.append('intent_ack')
        self.intent_metadata = metadata
        if self.fail_intent:
            raise BrokenPipeError('https://secret.example?token=do-not-print')
    def accepted(self, metadata):
        self.events.append('accepted_ack')
        self.accepted_metadata = metadata
        if self.fail_accepted:
            raise BrokenPipeError('secret')


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        events = self.events
        class Client:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        class Credentials:
            fail_save = False
            def __init__(self):
                self._access_token_expiration = datetime.now(timezone.utc) - timedelta(seconds=1)
                self.username = 'danielwuu'
            @classmethod
            def load(cls, client=None):
                return cls()
            def get_username(self):
                return self.username
            def access_token_has_expired(self):
                return False
            def save(self):
                events.append('official_save')
                if self.fail_save:
                    raise OSError('password=secret')
            def refresh_access_token(self):
                events.append('GenerateAccessToken')
                self._access_token_expiration = datetime.now(timezone.utc) + timedelta(hours=12)
                self.save()
            def delete(self):
                events.append('delete')
            def revoke_token(self):
                events.append('revoke')
        self.Client, self.Credentials = Client, Credentials
        self.runtime = Runtime()
        self.exchange = Exchange(self.events)
        self.session = auth.OfficialSession(self.runtime, self.exchange, lambda *args: None)
        self.session._install(Client, Credentials)
    def tearDown(self):
        self.session.close()
    def test_refresh_order_and_metadata_only(self):
        self.Credentials().refresh_access_token()
        self.assertEqual(self.events, ['intent_ack', 'GenerateAccessToken', 'official_save', 'accepted_ack'])
        self.assertEqual(len(self.exchange.intent_metadata['refresh_id']), 64)
        self.assertEqual(set(self.exchange.intent_metadata), {'account', 'old_expiration_epoch', 'refresh_id'})
        self.assertTrue(self.exchange.accepted_metadata['official_save_completed'])
        self.assertIn(True, self.runtime.guards)
        self.assertFalse(self.session.uncertain)
    def test_intent_pipe_failure_prevents_generate(self):
        self.exchange.fail_intent = True
        creds = self.Credentials()
        with self.assertRaises(auth.AuthRefreshUnknown):
            creds.refresh_access_token()
        with self.assertRaises(auth.AuthRefreshUnknown):
            creds.refresh_access_token()
        self.assertEqual(self.events, ['intent_ack'])
    def test_save_failure_latches_no_retry_or_delete(self):
        creds = self.Credentials()
        creds.fail_save = True
        with self.assertRaises(auth.AuthRefreshUnknown):
            creds.refresh_access_token()
        with self.assertRaises(auth.AuthRefreshUnknown):
            creds.refresh_access_token()
        with self.assertRaises(auth.AuthGuardError):
            creds.delete()
        self.assertEqual(self.events, ['intent_ack', 'GenerateAccessToken', 'official_save'])
    def test_accepted_pipe_failure_latches(self):
        self.exchange.fail_accepted = True
        creds = self.Credentials()
        with self.assertRaises(auth.AuthRefreshUnknown):
            creds.refresh_access_token()
        with self.assertRaises(auth.AuthRefreshUnknown):
            self.session.check()
        with self.assertRaises(auth.AuthRefreshUnknown):
            creds.refresh_access_token()
        self.assertEqual(self.events.count('GenerateAccessToken'), 1)
    def test_unclaimed_save_and_revoke_blocked(self):
        creds = self.Credentials()
        with self.assertRaises(auth.AuthGuardError):
            creds.save()
        with self.assertRaises(auth.AuthGuardError):
            creds.revoke_token()
        self.assertEqual(self.events, [])
    def test_early_expiry_and_account(self):
        creds = self.Credentials()
        creds._access_token_expiration = datetime.now(timezone.utc) + timedelta(seconds=240)
        self.assertTrue(creds.access_token_has_expired())
        creds._access_token_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertFalse(creds.access_token_has_expired())
        creds.username = 'other-account'
        with self.assertRaises(auth.AuthGuardError):
            creds.refresh_access_token()
        self.assertEqual(self.events, [])
    def test_auth_requires_prepared_ready(self):
        with self.assertRaises(auth.AuthGuardError):
            self.session.open()
        self.session.prepared = True
        with self.assertRaises(auth.AuthGuardError):
            self.session.open()
    def test_credentials_load_cannot_redirect(self):
        with self.assertRaises(auth.AuthGuardError):
            self.Credentials.load(client=None, file_path='elsewhere.json')


class SourceClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        sources = {}
        for package in ('kaggle', 'kagglesdk'):
            (self.root / package).mkdir()
            for index in range(85):
                name = package + '/' + ('__init__.py' if index == 0 else f'item{index}.py')
                raw = b'REVIEWED_SOURCE = True\n'
                (self.root / name).write_bytes(raw)
                sources[name] = hashlib.sha256(raw).hexdigest()
        self.lock = self.root / 'sdk-lock.json'
        self.lock.write_bytes(json.dumps({'format': 'irisx/run008-native-sdk-source-lock-v1',
            'distributions': {'kaggle': '2.2.4', 'kagglesdk': '0.1.37'}, 'sources': sources}).encode())
        self.runtime = SimpleNamespace(sdk_root=self.root, verify_runtime=lambda: None,
            read_source=lambda path, cap: path.read_bytes())
        self.patches = [patch.object(auth, 'LOCK_SHA256', hashlib.sha256(self.lock.read_bytes()).hexdigest()),
            patch.object(auth.sysconfig, 'get_path', lambda name: str(self.root)),
            patch.object(auth.importlib.metadata, 'distribution', lambda name: SimpleNamespace(
                version={'kaggle': '2.2.4', 'kagglesdk': '0.1.37'}[name], locate_file=lambda name: self.root))]
        for item in self.patches:
            item.start()
    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()
    def test_all_170_required_before_import(self):
        root, sources = auth.verify_sdk(self.runtime, self.lock)
        self.assertEqual(root, self.root)
        self.assertEqual(len(sources), 170)
        self.assertNotIn('kaggle', sys.modules)
    def test_extra_source_fails(self):
        (self.root / 'kaggle/rogue.py').write_text('raise RuntimeError()')
        with self.assertRaises(auth.AuthGuardError):
            auth.verify_sdk(self.runtime, self.lock)
    def test_missing_or_changed_source_fails(self):
        path = self.root / 'kaggle/item1.py'
        path.write_text('UNREVIEWED = True')
        with self.assertRaises(auth.AuthGuardError):
            auth.verify_sdk(self.runtime, self.lock)
        path.unlink()
        with self.assertRaises(auth.AuthGuardError):
            auth.verify_sdk(self.runtime, self.lock)
    def test_preimported_sdk_rejected(self):
        with patch.dict(sys.modules, {'kaggle.fake': ModuleType('kaggle.fake')}):
            with self.assertRaises(auth.AuthGuardError):
                auth.verify_sdk(self.runtime, self.lock)
    def test_source_only_loader_ignores_bytecode(self):
        root, sources = auth.verify_sdk(self.runtime, self.lock)
        source = root / 'kaggle/item1.py'
        cache = source.parent / '__pycache__'
        cache.mkdir()
        (cache / 'item1.cpython-312.pyc').write_bytes(b'UNTRUSTED BYTECODE')
        spec = importlib.util.spec_from_file_location('kaggle.item1', source)
        finder = auth.ReviewedSdkFinder(root, sources, self.runtime)
        with patch.object(auth.importlib.machinery.PathFinder, 'find_spec', return_value=spec):
            found = finder.find_spec('kaggle.item1')
        scope = {}
        exec(found.loader.get_code('kaggle.item1'), scope)
        self.assertTrue(scope['REVIEWED_SOURCE'])


class Response:
    def __init__(self, chunks=(), headers=None, status=200, data=None):
        self.chunks, self.headers, self.status_code = chunks, headers or {}, status
        self.content = b''
        self.data = data
        self.closed = False
    def iter_content(self, unused):
        yield from self.chunks
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError('https://secret.invalid?token=secret')
    def json(self):
        return self.data
    def close(self):
        self.closed = True


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.response = Response([b'{}'], {'Content-Type': 'application/json', 'Content-Length': '2'})
        def send(request, **kwargs):
            self.sent.append((request, kwargs))
            return self.response
        self.session = SimpleNamespace(send=send)
        self.client = SimpleNamespace(http_client=lambda: SimpleNamespace(_session=self.session))
        self.auth = SimpleNamespace(check=lambda: None, refreshing=False, refresh_credential=None)
        with patch.object(worker, 'no_retry_session', lambda value: value):
            worker.HttpBoundary().bind(self.client, self.auth)
    def request(self, operation='GetDataset', service='datasets.DatasetApiService'):
        return SimpleNamespace(method='POST', url='https://api.kaggle.com/v1/' + service + '/' + operation)
    def test_tls_proxy_preserved_and_metadata_bounded(self):
        response = self.session.send(self.request(), verify='C:/approved-ca.pem', proxies={'https': 'existing-proxy'})
        self.assertEqual(response._content, b'{}')
        self.assertTrue(response.closed)
        settings = self.sent[0][1]
        self.assertEqual(settings['verify'], 'C:/approved-ca.pem')
        self.assertEqual(settings['proxies'], {'https': 'existing-proxy'})
        self.assertEqual(settings['timeout'], (15, 90))
        self.assertFalse(settings['allow_redirects'])
    def test_mutation_never_resent(self):
        request = self.request('CreateDatasetVersionById')
        self.session.send(request)
        with self.assertRaises(worker.WorkerGuardError):
            self.session.send(request)
        self.assertEqual(len(self.sent), 1)
    def test_alternate_route_refresh_and_insecure_tls_rejected(self):
        with self.assertRaises(worker.WorkerGuardError):
            self.session.send(self.request('ListCompetitions', 'competitions.CompetitionApiService'))
        with self.assertRaises(worker.WorkerGuardError):
            self.session.send(self.request('GenerateAccessToken', 'users.AccountService'))
        with self.assertRaises(worker.WorkerGuardError):
            self.session.send(self.request(), verify=False)
        self.assertEqual(self.sent, [])
    def test_one_generate_per_refresh_object(self):
        self.auth.refreshing, self.auth.refresh_credential = True, object()
        request = self.request('GenerateAccessToken', 'users.AccountService')
        self.session.send(request)
        with self.assertRaises(worker.WorkerGuardError):
            self.session.send(request)
        self.assertEqual(len(self.sent), 1)
    def test_metadata_declared_cap(self):
        self.response.headers['Content-Length'] = str(worker.METADATA_CAP + 1)
        with self.assertRaises(worker.WorkerGuardError):
            self.session.send(self.request())
        self.assertTrue(self.response.closed)


class RecoveryHttpTests(unittest.TestCase):
    def setUp(self):
        self.sent,self.frames=[],[]
        def send(request,**kwargs):
            self.sent.append(request)
            return Response([b'{}'],{'Content-Type':'application/json'})
        self.session=SimpleNamespace(send=send)
        channel=SimpleNamespace(send=lambda *args,**kwargs:self.frames.append(args),
            receive=lambda **kwargs:{'payload':{'refresh_id':'a'*64,'phase':'intent',
                'claim_sha256':'b'*64,'journal_sha256':'c'*64}})
        self.exchange=worker.RefreshExchange(channel)
        self.exchange.ready=True;self.exchange.bind_request(1,'d'*64)
        self.auth=SimpleNamespace(check=lambda:None,refreshing=False,refresh_credential=None,exchange=self.exchange)
        self.expired=False
        def guard():
            worker.need(not self.expired,'worker_recovery_expired')
        client=SimpleNamespace(http_client=lambda:SimpleNamespace(_session=self.session))
        with patch.object(worker,'no_retry_session',lambda value:value):
            self.boundary=worker.HttpBoundary(self.exchange.official_rpc,recovery=True,
                refresh_exchange=self.exchange,lease_guard=guard)
            self.boundary.bind(client,self.auth)
    def request(self,service,operation):
        return SimpleNamespace(method='POST',url='https://api.kaggle.com/v1/'+service+'/'+operation)
    def test_only_three_read_routes_allowed(self):
        for service,operations in worker.ROUTES.items():
            for operation in operations:
                request=self.request(service,operation)
                if operation in ('GetDataset','GetKernel','GetKernelSessionStatus'):
                    self.session.send(request)
                else:
                    with self.subTest(operation=operation),self.assertRaises(worker.WorkerGuardError):
                        self.session.send(request)
        self.assertEqual(len(self.sent),3)
        self.assertEqual(self.boundary.mutations,{})
    def test_refresh_needs_durable_intent_and_exact_exchange(self):
        self.auth.refreshing=True;self.auth.refresh_credential=object()
        request=self.request('users.AccountService','GenerateAccessToken')
        with self.assertRaisesRegex(worker.WorkerGuardError,'recovery_durable_refresh_required'):
            self.session.send(request)
        self.exchange.intent({'refresh_id':'a'*64,'account':'danielwuu','old_expiration_epoch':1})
        self.auth.exchange=None
        with self.assertRaises(worker.WorkerGuardError):self.session.send(request)
        self.auth.exchange=self.exchange
        self.session.send(request)
        with self.assertRaisesRegex(worker.WorkerGuardError,'auth_rpc_resend_forbidden'):
            self.session.send(request)
        self.assertEqual(len(self.sent),1)
    def test_lost_intent_ack_blocks_refresh_rpc(self):
        self.auth.refreshing=True;self.auth.refresh_credential=object()
        self.exchange.channel.receive=lambda **kwargs:(_ for _ in ()).throw(EOFError())
        with self.assertRaises(EOFError):self.exchange.intent({'refresh_id':'a'*64})
        with self.assertRaises(worker.WorkerGuardError):
            self.session.send(self.request('users.AccountService','GenerateAccessToken'))
        self.assertEqual(self.sent,[])
    def test_expired_recovery_cannot_send_even_read_or_refresh(self):
        self.expired=True
        with self.assertRaisesRegex(worker.WorkerGuardError,'worker_recovery_expired'):
            self.session.send(self.request('datasets.DatasetApiService','GetDataset'))
        self.assertEqual(self.sent,[])
    def test_direct_storage_helpers_all_fail_before_http(self):
        storage=worker.StorageHttp(recovery=True)
        with self.assertRaises(worker.WorkerGuardError):storage.requests
        with self.assertRaises(worker.WorkerGuardError):
            with storage.download(Response(),1):pass
        with self.assertRaises(worker.WorkerGuardError):list(storage.chunks(Response(),1))
        with self.assertRaises(worker.WorkerGuardError):storage.metadata(Response(),1,1)
        with self.assertRaises(worker.WorkerGuardError):storage.put('https://storage.googleapis.com/a',io.BytesIO(b'x'),1)
    def test_direct_provider_helpers_all_fail_before_sdk_or_storage(self):
        provider=worker.WorkerProvider(SimpleNamespace(),VERSIONS,recovery=True)
        cases=(('list_files',(20,)),('output',('x',39)),('dataset_download',('x',20)),
            ('start_upload',('x.zip',1,'a'*64)),('upload_once',('a'*64,io.BytesIO(b'x'),1,'b'*64)),
            ('version',('a'*64,'notes',20)),('save',({},)))
        for method,args in cases:
            with self.subTest(method=method),self.assertRaisesRegex(worker.WorkerGuardError,'recovery_operation_forbidden'):
                getattr(provider,method)(*args)
        with self.assertRaises(worker.WorkerGuardError):
            worker.WorkerProvider(SimpleNamespace(),VERSIONS,SimpleNamespace(),recovery=True)
    def test_unrecognized_internal_mode_is_rejected(self):
        for mode in ('recovery','legacy',1,None,{}):
            with self.subTest(mode=mode):
                with self.assertRaises(worker.WorkerGuardError):worker.HttpBoundary(recovery=mode)
                with self.assertRaises(worker.WorkerGuardError):worker.StorageHttp(recovery=mode)
                with self.assertRaises(worker.WorkerGuardError):worker.WorkerProvider(SimpleNamespace(),VERSIONS,recovery=mode)


VERSIONS = {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39, 'inactive': 40, 'active': 41}


class WorkerTests(unittest.TestCase):
    def test_sanitized_errors_do_not_contain_arbitrary_data(self):
        result = worker.error_dto(RuntimeError('Bearer SECRET https://storage.googleapis.com/a?token=SECRET'))
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('https:', json.dumps(result))
        self.assertEqual(result['code'], 'PROVIDER_FAILURE')
        self.assertEqual(worker.safe_semantic('GPU unavailable token=SECRET'), 'GPU unavailable')
        proxy = type('ProxyError', (RuntimeError,), {})('Tunnel connection failed: 403 Forbidden SECRET')
        self.assertEqual(worker.error_dto(proxy)['classification'], 'ACCESS_BLOCKED')
    def test_raw_stdout_stderr_are_sunk_without_leaking_to_ipc(self):
        script = '''import importlib.util, os, sys
spec = importlib.util.spec_from_file_location('synthetic_auth', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with module.isolate_sdk_output() as (reader, writer):
    print('PYTHON-SECRET', flush=True)
    print('ERROR-SECRET', file=sys.stderr, flush=True)
    os.write(1, b'RAW-SECRET')
    os.write(2, b'RAW-ERROR-SECRET')
    writer.write(b'FRAME')
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(ROOT / 'native_auth.py')],
            input=b'', capture_output=True, timeout=5, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'FRAME')
        self.assertEqual(result.stderr, b'')
    def test_download_stream_is_bounded_and_closes(self):
        storage = worker.StorageHttp()
        response = Response([b'ab', b'cd'], {'Content-Length': '4'})
        with storage.download(response, 4) as current:
            self.assertEqual(b''.join(storage.chunks(current, 4)), b'abcd')
        self.assertTrue(response.closed)
        response = Response([b'abcde'])
        with self.assertRaises(worker.WorkerGuardError):
            with storage.download(response, 4) as current:
                list(storage.chunks(current, 4))
        self.assertTrue(response.closed)
    def test_storage_url_allowlist(self):
        for value in ('http://storage.googleapis.com/a', 'https://evil.invalid/a',
                      'https://user:password@storage.googleapis.com/a', 'https://storage.googleapis.com/a#x'):
            with self.assertRaises(worker.WorkerGuardError):
                worker.safe_url(value)
        self.assertEqual(worker.safe_url('https://storage.googleapis.com/a?sig=SECRET').hostname,
                         'storage.googleapis.com')
    def test_metadata_is_presence_only_not_download_claim(self):
        response = Response([b'never-consumed'], {'Content-Length': '17'})
        result = worker.StorageHttp().metadata(response, 17, 100)
        self.assertFalse(result['archive_bytes_verified'])
        self.assertEqual(result['body_consumed_bytes'], 0)
        self.assertTrue(response.closed)
    def test_upload_handle_ram_only_and_verify_before_put(self):
        module = ModuleType('kagglesdk.blobs.types.blob_api_service')
        module.ApiStartBlobUploadRequest = type('Request', (), {})
        module.ApiBlobType = SimpleNamespace(DATASET=1)
        token, url = 'STAGING-SECRET', 'https://storage.googleapis.com/upload?signature=URL-SECRET'
        client = SimpleNamespace(blobs=SimpleNamespace(blob_api_client=SimpleNamespace(
            start_blob_upload=lambda request: SimpleNamespace(token=token, create_url=url))))
        auth_double = SimpleNamespace(renew_if_due=lambda: client, close=lambda: None)
        puts = []
        storage = SimpleNamespace(put=lambda url, source, size: puts.append((url, source.read(), size)) or 200)
        provider = worker.WorkerProvider(auth_double, VERSIONS, storage)
        content, digest = b'zipbytes', hashlib.sha256(b'zipbytes').hexdigest()
        with patch.dict(sys.modules, {module.__name__: module}):
            result = provider.start_upload('source.zip', len(content), digest)
            self.assertEqual(len(result['handle']), 64)
            self.assertNotIn(token, json.dumps(result))
            self.assertNotIn('URL-SECRET', json.dumps(result))
            with self.assertRaises(worker.WorkerGuardError):
                provider.start_upload('source.zip', len(content), digest)
        with self.assertRaises(worker.WorkerGuardError):
            provider.upload_once(result['handle'], io.BytesIO(b'badbytes'), len(content), digest)
        self.assertEqual(puts, [])
        response = provider.upload_once(result['handle'], io.BytesIO(content), len(content), digest)
        self.assertEqual(response, {'bytes': len(content), 'sha256': digest, 'http_status': 200})
        with self.assertRaises(worker.WorkerGuardError):
            provider.upload_once(result['handle'], io.BytesIO(content), len(content), digest)
        self.assertEqual(len(puts), 1)
        provider.close()
        self.assertEqual(provider.uploads, {})
    def test_version_requires_separate_verified_put_and_predecessor(self):
        module = ModuleType('kagglesdk.datasets.types.dataset_api_service')
        for name in ('ApiCreateDatasetVersionByIdRequest', 'ApiCreateDatasetVersionRequestBody', 'ApiDatasetNewFile'):
            setattr(module, name, type(name, (), {}))
        calls = []
        client = SimpleNamespace(datasets=SimpleNamespace(dataset_api_client=SimpleNamespace(
            create_dataset_version_by_id=lambda request: calls.append(request) or SimpleNamespace(ref=worker.DREF, error=''))))
        provider = worker.WorkerProvider(SimpleNamespace(renew_if_due=lambda: client, close=lambda: None), VERSIONS)
        handle = 'a' * 64
        provider.uploads[handle] = {'stage': 'begin', 'token': 'RAM-SECRET'}
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaises(worker.WorkerGuardError):
                provider.version(handle, 'notes', 20)
            provider.uploads[handle]['stage'] = 'put_accepted'
            provider.dataset = lambda: {'id': worker.DATASET_ID, 'ref': worker.DREF,
                'isPrivate': True, 'currentVersionNumber': 21}
            with self.assertRaises(worker.WorkerGuardError):
                provider.version(handle, 'notes', 20)
            self.assertEqual(calls, [])
            provider.dataset = lambda: {'id': worker.DATASET_ID, 'ref': worker.DREF,
                'isPrivate': True, 'currentVersionNumber': 20}
            self.assertEqual(provider.version(handle, 'notes', 20), {'ref': worker.DREF, 'error': ''})
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0].body.delete_old_versions)
        self.assertNotIn(handle, provider.uploads)


class NativeLeaseTests(unittest.TestCase):
    def test_native_deadline_never_renews_supervisor_budget(self):
        with patch.object(worker, 'time', SimpleNamespace(monotonic=lambda: 103)):
            self.assertEqual(worker.native_lease_deadline(5, 105), 105)
            self.assertEqual(worker.native_lease_deadline(5, 1000), 108)
            self.assertEqual(worker.native_lease_deadline(5), 108)

    def test_expired_and_invalid_native_leases_fail_closed(self):
        for seconds, deadline in ((0, 105), (True, 105), (43200.1, 105),
                                  (math.inf, 105), (5, math.nan), (5, True),
                                  (5, 99), (5, 100)):
            with self.subTest(seconds=seconds, deadline=deadline), \
                 self.assertRaises(worker.WorkerGuardError):
                worker.native_lease_deadline(seconds, deadline, started=100)


class FullFramingTests(unittest.TestCase):
    """Actual FramedIO/SequenceGuard over local pipes with fully fake SDK/auth."""
    @contextmanager
    def running(self, *, refresh=False, provider_error=False, recovery=False, boot_failure=0,
                native_wall_offset=0):
        read_worker, write_client = os.pipe()
        read_client, write_worker = os.pipe()
        handles = [os.fdopen(fd, mode, buffering=0) for fd, mode in (
            (read_worker, 'rb'), (write_client, 'wb'), (read_client, 'rb'), (write_worker, 'wb'))]
        nonce = '1' * 64
        self.lease = time.time() + 600
        self.client = protocol.FramedIO(handles[2], handles[1], nonce=nonce, deadline=time.monotonic() + 10)
        server = protocol.FramedIO(handles[0], handles[3], nonce=nonce, deadline=time.monotonic() + 10)
        events, result = [], []
        class FakeAuth:
            def __init__(inner, runtime, exchange, boundary):
                inner.exchange, inner.uncertain = exchange, False
            def prepare(inner):
                events.append('verified_all_sources')
                return {'sdk_lock_sha256': auth.LOCK_SHA256, 'sdk_source_count': 170,
                        'account': 'danielwuu', 'existing_official_store': True}
            def protocol_ready(inner):
                inner.exchange.check_ready()
                events.append('ready_ack')
            def open(inner):
                events.append('open')
                if refresh:
                    try:
                        inner.exchange.intent({'refresh_id': '2' * 64, 'account': 'danielwuu',
                            'old_expiration_epoch': 1})
                        with inner.exchange.official_rpc():
                            events.append('GenerateAccessToken_double')
                        events.append('official_save_double')
                        inner.exchange.accepted({'refresh_id': '2' * 64,
                            'new_expiration_epoch': time.time() + 3600,
                            'official_save_completed': True, 'credential_acl_verified': True})
                    except BaseException:
                        inner.uncertain = True
                        raise auth.AuthRefreshUnknown('fixed') from None
            def close(inner):
                events.append('closed')
        class FakeProvider:
            def __init__(inner, authentication, versions, *, recovery=False):
                inner.authentication = authentication
            def status(inner):
                if provider_error:
                    error = RuntimeError('SECRET provider body')
                    error.response = Response(headers={'Retry-After': '3'},
                        status=503 if provider_error is True else provider_error)
                    raise error
                return {'status': 'COMPLETE', 'failureMessage': ''}
            def close(inner):
                inner.authentication.close()
        self.recovery={'capability_sha256':'a'*64,'reservation_sha256':'b'*64,
            'challenge':'c'*64,'host_install_sha256':'d'*64,'last_boot_utc':'2026-10-15T08:00:00.000000Z',
            'expires_epoch':self.lease+10,'allowed_operations':['open','dataset','kernel','status','close']}
        def verify_recovery_boot(**kwargs):
            events.append('fresh_boot')
            if boot_failure and events.count('fresh_boot')==boot_failure:
                raise worker.WorkerGuardError('synthetic_boot_mismatch')
        runtime = SimpleNamespace(config_sha256='3' * 64,
            recovery=self.recovery if recovery else None,verify_recovery_boot=verify_recovery_boot)
        def serve():
            try:
                result.append(worker.run_worker(runtime, VERSIONS, server, protocol,
                    SimpleNamespace(OfficialSession=FakeAuth), deadline_epoch=self.lease, max_seconds=600))
            finally:
                handles[0].close()
                handles[3].close()
        with patch.object(worker, 'WorkerProvider', FakeProvider), \
             patch.object(worker, 'time', SimpleNamespace(monotonic=time.monotonic,
                 time=lambda: time.time() + native_wall_offset)):
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            try:
                yield events, result
            finally:
                handles[1].close()
                handles[2].close()
                thread.join(2)
                self.assertFalse(thread.is_alive(), 'synthetic worker did not close')
    def command(self, sequence, operation, arguments):
        deadline = min(self.lease, time.time() + 120)
        digest = protocol.request_hash(operation, arguments, deadline_epoch=deadline, max_seconds=120)
        self.client.send('request', {'operation': operation, 'arguments': arguments,
            'deadline_epoch': deadline, 'max_seconds': 120}, sequence=sequence, request_sha256=digest)
        return digest
    def open_request(self, recovery=None):
        args={'account': 'danielwuu', 'versions': VERSIONS,
            'configuration_sha256': '4' * 64, 'bridge_configuration_sha256': '3' * 64,
            'publication_manifest_sha256': '5' * 64, 'deadline_epoch': self.lease, 'max_seconds': 600}
        if recovery is not None:args['recovery']=recovery
        return self.command(1,'open',args)
    def recovery_binding(self):
        return {key:self.recovery[key] for key in ('capability_sha256','reservation_sha256')}
    def ready(self, digest):
        frame = self.client.receive(kinds={'ready'}, sequence=1, request_sha256=digest)
        self.assertEqual(frame['payload']['sdk_source_count'], 170)
        self.client.send('ready_ack', {'ready': True}, sequence=1, request_sha256=digest)
    def test_full_open_refresh_phase_status_close(self):
        with self.running(refresh=True) as (events, result):
            digest = self.open_request()
            self.ready(digest)
            frame = self.client.receive(kinds={'refresh_request'}, sequence=1, request_sha256=digest)
            refresh_id = frame['payload']['refresh_id']
            self.client.send('refresh_ack', {'refresh_id': refresh_id, 'phase': 'intent',
                'claim_sha256': '6' * 64, 'journal_sha256': '7' * 64}, sequence=1, request_sha256=digest)
            self.client.receive(kinds={'phase_start'}, sequence=1, request_sha256=digest)
            self.client.receive(kinds={'phase_end'}, sequence=1, request_sha256=digest)
            self.client.receive(kinds={'refresh_result'}, sequence=1, request_sha256=digest)
            self.client.send('refresh_ack', {'refresh_id': refresh_id, 'phase': 'accepted',
                'claim_sha256': '6' * 64, 'journal_sha256': '8' * 64}, sequence=1, request_sha256=digest)
            opened = self.client.receive(kinds={'response'}, sequence=1, request_sha256=digest)
            self.assertEqual(opened['payload']['result'], {'authenticated': True})
            status = self.command(2, 'status', {})
            self.assertEqual(self.client.receive(kinds={'response'}, sequence=2,
                request_sha256=status)['payload']['result']['status'], 'COMPLETE')
            closing = self.command(3, 'close', {})
            self.client.receive(kinds={'response'}, sequence=3, request_sha256=closing)
        self.assertEqual(result, [0])
        self.assertEqual(events, ['verified_all_sources', 'ready_ack', 'open',
            'GenerateAccessToken_double', 'official_save_double', 'closed'])

    def test_cross_os_wall_skew_preserves_open_operation_and_close(self):
        for offset in (-172800, 172800):
            for provider_error in (False, True):
                with self.subTest(offset=offset, provider_error=provider_error):
                    with self.running(native_wall_offset=offset,
                                      provider_error=provider_error) as (events, result):
                        digest = self.open_request()
                        self.ready(digest)
                        self.client.receive(kinds={'response'}, sequence=1, request_sha256=digest)
                        status = self.command(2, 'status', {})
                        self.client.receive(kinds={'error' if provider_error else 'response'},
                                            sequence=2, request_sha256=status)
                        closing = self.command(3, 'close', {})
                        self.client.receive(kinds={'response'}, sequence=3, request_sha256=closing)
                    self.assertEqual(result, [0])
                    self.assertEqual(events, ['verified_all_sources', 'ready_ack', 'open', 'closed'])
    def test_bad_refresh_ack_stops_before_generate(self):
        with self.running(refresh=True) as (events, result):
            digest = self.open_request()
            self.ready(digest)
            self.client.receive(kinds={'refresh_request'}, sequence=1, request_sha256=digest)
            self.client.send('refresh_ack', {'refresh_id': '9' * 64, 'phase': 'intent',
                'claim_sha256': '6' * 64, 'journal_sha256': '7' * 64}, sequence=1, request_sha256=digest)
            response = self.client.receive(kinds={'error'}, sequence=1, request_sha256=digest)
            self.assertEqual(response['payload']['code'], 'AUTH_REFRESH_UNKNOWN')
        self.assertEqual(result, [2])
        self.assertNotIn('GenerateAccessToken_double', events)
    def test_readonly_503_allows_close_only_and_clean_exit(self):
        with self.running(provider_error=True) as (events, result):
            digest = self.open_request()
            self.ready(digest)
            self.client.receive(kinds={'response'}, sequence=1, request_sha256=digest)
            status = self.command(2, 'status', {})
            response = self.client.receive(kinds={'error'}, sequence=2, request_sha256=status)
            self.assertEqual(response['payload']['http_status'], 503)
            self.assertEqual(response['payload']['retry_after_seconds'], 3)
            self.assertFalse(response['payload']['mutation_uncertain'])
            closing = self.command(3, 'close', {})
            self.client.receive(kinds={'response'}, sequence=3, request_sha256=closing)
        self.assertEqual(result, [0])
    def test_readonly_404_can_close_cleanly(self):
        with self.running(provider_error=404) as (events, result):
            digest = self.open_request()
            self.ready(digest)
            self.client.receive(kinds={'response'}, sequence=1, request_sha256=digest)
            status = self.command(2, 'status', {})
            response = self.client.receive(kinds={'error'}, sequence=2, request_sha256=status)
            self.assertEqual(response['payload']['http_status'], 404)
            self.assertEqual(response['payload']['classification'], 'PROVIDER_ERROR')
            closing = self.command(3, 'close', {})
            self.client.receive(kinds={'response'}, sequence=3, request_sha256=closing)
        self.assertEqual(result, [0])
    def test_recovery_fresh_boot_before_prepare_and_open_then_status_close(self):
        with self.running(recovery=True) as (events,result):
            digest=self.open_request(self.recovery_binding());self.ready(digest)
            self.client.receive(kinds={'response'},sequence=1,request_sha256=digest)
            status=self.command(2,'status',{})
            self.client.receive(kinds={'response'},sequence=2,request_sha256=status)
            closing=self.command(3,'close',{})
            self.client.receive(kinds={'response'},sequence=3,request_sha256=closing)
        self.assertEqual(result,[0])
        self.assertEqual(events,['fresh_boot','verified_all_sources','ready_ack','fresh_boot','open','closed'])
    def test_recovery_missing_ready_ack_stops_before_second_boot_or_auth(self):
        with self.running(recovery=True) as (events,result):
            digest=self.open_request(self.recovery_binding())
            self.client.receive(kinds={'ready'},sequence=1,request_sha256=digest)
            self.client.writer.close()
            with self.assertRaises((protocol.ProtocolError,EOFError)):
                self.client.receive(kinds={'response'},sequence=1,request_sha256=digest)
        self.assertEqual(result,[2])
        self.assertEqual(events,['fresh_boot','verified_all_sources','closed'])
    def test_recovery_refresh_keeps_durable_two_ack_exchange(self):
        for accept in (True,False):
            with self.subTest(accept=accept):
                with self.running(recovery=True,refresh=True) as (events,result):
                    digest=self.open_request(self.recovery_binding());self.ready(digest)
                    request=self.client.receive(kinds={'refresh_request'},sequence=1,request_sha256=digest)
                    refresh_id=request['payload']['refresh_id']
                    self.client.send('refresh_ack',{'refresh_id':refresh_id if accept else 'f'*64,
                        'phase':'intent','claim_sha256':'6'*64,'journal_sha256':'7'*64},
                        sequence=1,request_sha256=digest)
                    if not accept:
                        self.client.receive(kinds={'error'},sequence=1,request_sha256=digest)
                    else:
                        self.client.receive(kinds={'phase_start'},sequence=1,request_sha256=digest)
                        self.client.receive(kinds={'phase_end'},sequence=1,request_sha256=digest)
                        self.client.receive(kinds={'refresh_result'},sequence=1,request_sha256=digest)
                        self.client.send('refresh_ack',{'refresh_id':refresh_id,'phase':'accepted',
                            'claim_sha256':'6'*64,'journal_sha256':'8'*64},sequence=1,request_sha256=digest)
                        self.client.receive(kinds={'response'},sequence=1,request_sha256=digest)
                        closing=self.command(2,'close',{})
                        self.client.receive(kinds={'response'},sequence=2,request_sha256=closing)
                self.assertEqual(result,[0 if accept else 2])
                self.assertEqual(events.count('GenerateAccessToken_double'),1 if accept else 0)
    def test_open_mode_and_capability_parity_fail_before_boot_or_auth(self):
        for recovery,binding in ((True,None),(False,{'capability_sha256':'a'*64,'reservation_sha256':'b'*64}),
             (True,{'capability_sha256':'e'*64,'reservation_sha256':'b'*64}),
             (True,{'capability_sha256':'a'*64,'reservation_sha256':'e'*64})):
            with self.subTest(recovery=recovery,binding=binding):
                with self.running(recovery=recovery) as (events,result):
                    digest=self.open_request(binding)
                    frame=self.client.receive(kinds={'error'},sequence=1,request_sha256=digest)
                    self.assertEqual(frame['payload']['code'],'VERIFICATION_FAILED')
                self.assertEqual(result,[2]);self.assertEqual(events,['closed'])
    def test_fresh_boot_failure_never_authenticates(self):
        for failed in (1,2):
            with self.subTest(failed=failed),self.running(recovery=True,boot_failure=failed) as (events,result):
                digest=self.open_request(self.recovery_binding())
                if failed==2:self.ready(digest)
                self.client.receive(kinds={'error'},sequence=1,request_sha256=digest)
            self.assertNotIn('open',events)
            if failed==1:self.assertNotIn('verified_all_sources',events)
            self.assertEqual(result,[2])
    def test_recovery_rejects_all_excluded_frames_before_provider_dispatch(self):
        save={'id':138123872,'slug':worker.REF,'new_title':'synthetic','text':'{}','language':'python',
            'kernel_type':'notebook','dataset_data_sources':[],'model_data_sources':[],
            'competition_data_sources':[],'kernel_data_sources':[],'is_private':True,'enable_gpu':True,
            'enable_tpu':False,'enable_internet':False,'docker_image':'synthetic',
            'kernel_execution_type':3,'session_timeout_seconds':1,'machine_shape':None}
        cases={'list_files':{'dataset':True,'version':20},
            'output':{'name':'x','version':39,'cap':1,'expected_bytes':None,'expected_sha256':None},
            'dataset_download':{'name':None,'version':20,'cap':1,'expected_bytes':None,'expected_sha256':None},
            'binary_metadata':{'name':'x','version':39,'expected_size':1,'cap':1},
            'start_upload':{'name':'x.zip','bytes':1,'sha256':'a'*64},
            'upload_once':{'handle':'a'*64,'bytes':1,'sha256':'b'*64},
            'version':{'handle':'a'*64,'notes':'notes','expected_predecessor_version':20},'save':{'wire':save}}
        self.assertEqual(set(cases),protocol.OPERATIONS-protocol.RECOVERY_OPERATIONS)
        for operation,args in cases.items():
            with self.subTest(operation=operation):
                with self.running(recovery=True) as (events,result):
                    digest=self.open_request(self.recovery_binding());self.ready(digest)
                    self.client.receive(kinds={'response'},sequence=1,request_sha256=digest)
                    digest=self.command(2,operation,args)
                    frame=self.client.receive(kinds={'error'},sequence=2,request_sha256=digest)
                    self.assertEqual(frame['payload']['code'],'VERIFICATION_FAILED')
                self.assertEqual(result,[2])
    def test_recovery_expiry_blocks_next_request(self):
        with self.running(recovery=True) as (events,result):
            digest=self.open_request(self.recovery_binding());self.ready(digest)
            self.client.receive(kinds={'response'},sequence=1,request_sha256=digest)
            self.recovery['expires_epoch']=time.time()-1
            digest=self.command(2,'status',{})
            frame=self.client.receive(kinds={'error'},sequence=2,request_sha256=digest)
            self.assertEqual(frame['payload']['code'],'VERIFICATION_FAILED')
        self.assertEqual(result,[2])


if __name__ == '__main__':
    unittest.main()

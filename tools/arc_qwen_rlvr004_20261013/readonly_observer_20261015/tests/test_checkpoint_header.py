"""Offline-only header capability tests; fake HTTP/native Job, real pinned SDK.

Synthetic chains substitute their own pins explicitly. They never assert that
synthetic bytes are the preserved terminal or create collector admission.
"""
import copy
from contextlib import contextmanager, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
import sys
from unittest.mock import Mock, patch

import test_retrieve as old

retrieve, observer, sdk = old.retrieve, old.observer, old.sdk
CAP = 4 * 1024**3
SIZE = retrieve.CHECKPOINT_SOURCE['bytes']
URL = 'https://api.kaggle.com/v1/kernels.KernelsApiService/DownloadKernelOutput'


class HTTPError(ValueError):
    def __init__(self, message, *, response):
        super().__init__(message)
        self.response = response


class Request:
    def __init__(self, method, url, headers):
        self.method, self.url, self.headers = method, url, headers

    def prepare(self):
        return self


def fake_requests_modules():
    # No requests installation or network is needed: the real SDK transport
    # receives an inert HTTP library whose responses trap every body method.
    module = ModuleType('requests')
    adapters = ModuleType('requests.adapters')
    adapters.HTTPAdapter = lambda **kwargs: SimpleNamespace(**kwargs)
    module.adapters = adapters
    return {'requests': module, 'requests.adapters': adapters}



def manifest():
    value = old.manifest()
    value['terminal_contract']['archive_caps']['checkpoint_archive_bytes'] = CAP
    return value


def argv():
    return old.argv(retrieve.CHECKPOINT_PATH) + ['--checkpoint-header',
        '--terminal-receipt', '/cpu/terminal/retrieval-result.json',
        '--terminal-receipt-sha', retrieve.HEADER_TERMINAL_RECEIPT_SHA256]


class TensorResponse(old.FakeResponse):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.headers['Content-Length'] = str(SIZE)

    @property
    def content(self):
        raise AssertionError('checkpoint content read')

    def json(self):
        raise AssertionError('checkpoint JSON read')

    def iter_content(self, *args, **kwargs):
        raise AssertionError('checkpoint iter_content read')

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPError('synthetic private URL', response=self)


class HeaderTransportTests(old.ClockedTests):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(sys.modules, fake_requests_modules()))
        self.enterContext(patch.object(observer, 'SOURCE_SHA256', old.FAKE_SOURCE_SHA))
        self.base = SimpleNamespace(**vars(observer))
        self.base.METADATA_SHA256 = observer.sha(observer.canonical(old.metadata()))
        self.base.observe = lambda provider, expected: observer.observe(provider, expected, wall=lambda: old.NOW)
        self.session = SimpleNamespace(send=Mock(), close=Mock(), mount=Mock(),
            merge_environment_settings=Mock(return_value={}))
        self.storage = retrieve.DownloadOnly(sdk.StorageHttp(requests_module=SimpleNamespace(
            Session=lambda: self.session, Request=Request)))
        self.storage.chunks = Mock(side_effect=AssertionError('checkpoint chunks read'))

    def run_header(self, provider=None):
        return retrieve.observe_checkpoint_header(self.base,
            provider or old.FakeProvider(TensorResponse()), self.storage,
            old.metadata(), CAP, retrieve.CHECKPOINT_SOURCE, old.DEADLINE)

    def test_direct_response_is_header_only_and_source_bracketed(self):
        response = TensorResponse()
        provider = old.FakeProvider(response)
        with patch.object(Path, 'open', side_effect=AssertionError('checkpoint filesystem write')):
            result = self.run_header(provider)
        self.assertEqual(result['checkpoint'], retrieve.header_observation(SIZE))
        self.assertEqual(provider.calls, ['kernel', 'status', 'kernel',
            ('output', retrieve.CHECKPOINT_PATH, 43), 'kernel', 'status', 'kernel'])
        self.assertTrue(response.closed)
        self.storage.chunks.assert_not_called()
        self.session.send.assert_not_called()

    def test_every_missing_invalid_or_mismatched_length_rejected_and_closed(self):
        for value in (None, '', '-1', '+1', ' 1546535710', '1546535710 ', 'NaN', '1.5',
                      str(SIZE-1), str(SIZE+1), str(CAP+1), True, SIZE, float(SIZE)):
            response = TensorResponse()
            if value is None:
                del response.headers['Content-Length']
            else:
                response.headers['Content-Length'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_header(old.FakeProvider(response))
            self.assertTrue(response.closed)

    def test_wrong_encoding_and_http_status_never_read_body(self):
        for encoding in ('gzip', 'br', 'Identity', 'identity,gzip'):
            response = TensorResponse(headers={'Content-Encoding': encoding})
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                self.run_header(old.FakeProvider(response))
            self.assertTrue(response.closed)
        for status in (201, 204, 206, 301, 302, 304, 400, 401, 403, 404, 500):
            response = TensorResponse(status=status)
            with self.subTest(status=status), self.assertRaises((ValueError, HTTPError)):
                self.run_header(old.FakeProvider(response))
            self.assertTrue(response.closed)

    def test_json_direct_response_is_refused_before_content_or_json_access(self):
        for status in (200, 404):
            response = TensorResponse(status=status, headers={'Content-Type': 'application/json'})
            with self.assertRaisesRegex(ValueError, 'checkpoint_json_body_forbidden'):
                self.run_header(old.FakeProvider(response))
            self.assertTrue(response.closed)

    def test_storage_location_redirect_uses_original_metadata_transport(self):
        initial = TensorResponse(status=302, headers={'Location': 'https://storage.googleapis.com/a?sig=PRIVATE',
                                                      'Content-Type': 'application/json'})
        redirect = TensorResponse(status=307, headers={'Location': '/b?sig=PRIVATE'})
        response = TensorResponse()
        self.session.send.side_effect = [redirect, response]
        result = self.run_header(old.FakeProvider(initial))
        self.assertEqual(result['checkpoint'], retrieve.header_observation(SIZE))
        for call in self.session.send.call_args_list:
            request = call.args[0]
            self.assertEqual(request.method, 'GET')
            self.assertEqual(request.headers, {'Accept-Encoding': 'identity'})
            self.assertIs(call.kwargs['stream'], True)
            self.assertIs(call.kwargs['allow_redirects'], False)
            self.assertEqual(call.kwargs['timeout'], (15, 90))
        self.assertTrue(all(row.closed for row in (initial, redirect, response)))
        self.session.close.assert_called_once()
        self.assertNotIn('PRIVATE', observer.canonical(result).decode())

    def test_storage_json_label_does_not_consume_tensor_response(self):
        initial = TensorResponse(status=302, headers={'Location': 'https://storage.googleapis.com/a'})
        response = TensorResponse(headers={'Content-Type': 'application/json'})
        self.session.send.return_value = response
        self.assertEqual(self.run_header(old.FakeProvider(initial))['checkpoint'], retrieve.header_observation(SIZE))
        self.assertTrue(response.closed)

    def test_unsafe_redirect_and_redirect_limit_fail_closed(self):
        for url in ('http://storage.googleapis.com/a', 'https://evil.example/a',
                    'https://user@storage.googleapis.com/a'):
            response = TensorResponse(status=302, headers={'Location': url})
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.run_header(old.FakeProvider(response))
            self.assertTrue(response.closed)
        self.session.send.side_effect = [TensorResponse(status=302,
            headers={'Location': 'https://storage.googleapis.com/a'}) for _ in range(5)]
        response = TensorResponse(status=302, headers={'Location': 'https://storage.googleapis.com/a'})
        with self.assertRaisesRegex(ValueError, 'redirect_limit'):
            self.run_header(old.FakeProvider(response))
        self.assertEqual(self.session.send.call_count, 5)

    def test_source_or_settings_drift_at_all_four_reads_fails(self):
        for index in range(4):
            for field in ('source', 'metadata'):
                values = [old.kernel() for _ in range(4)]
                if field == 'source':
                    values[index]['blob']['source'] += 'changed'
                else:
                    values[index]['metadata']['currentVersionNumber'] = 44
                provider = old.FakeProvider(TensorResponse(), kernels=values)
                with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                    self.run_header(provider)
                if index < 2:
                    self.assertFalse(any(isinstance(call, tuple) for call in provider.calls))

    def test_running_before_or_changed_terminal_after_fails(self):
        for statuses in (('RUNNING',), ('ERROR', 'COMPLETE'), ('ERROR', 'RUNNING')):
            provider = old.FakeProvider(TensorResponse(), statuses=statuses)
            with self.subTest(statuses=statuses), self.assertRaises(ValueError):
                self.run_header(provider)
            if statuses[0] == 'RUNNING':
                self.assertFalse(any(isinstance(call, tuple) for call in provider.calls))

    def test_stale_deadlines_fail_before_output(self):
        for monotonic, wall in ((old.DEADLINE, old.NOW), (100, observer.CLOCK['global_deadline'])):
            self.monotonic.return_value, self.wall.return_value = monotonic, wall
            provider = old.FakeProvider(TensorResponse())
            with self.subTest(monotonic=monotonic, wall=wall), self.assertRaisesRegex(ValueError, 'deadline'):
                self.run_header(provider)
            self.assertEqual(provider.calls, [])

    def test_deadline_expiring_on_response_closes_and_does_not_observe_after(self):
        response = TensorResponse()
        provider = old.FakeProvider(response)
        original = provider.output
        def output(*args):
            value = original(*args)
            self.monotonic.return_value = old.DEADLINE
            return value
        provider.output = output
        with self.assertRaisesRegex(ValueError, 'deadline'):
            self.run_header(provider)
        self.assertTrue(response.closed)
        self.assertEqual(len(provider.calls), 4)


class HeaderBoundaryTests(old.ClockedTests):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(sys.modules, fake_requests_modules()))

    def bind(self, response):
        raw_send = Mock(return_value=response)
        session = SimpleNamespace(send=raw_send, mount=Mock())
        client = SimpleNamespace(http_client=lambda: SimpleNamespace(_session=session))
        auth = SimpleNamespace(check=Mock())
        retrieve.bind_readonly(observer, sdk, client, auth, old.DEADLINE, checkpoint_header=True)
        return session, raw_send, auth

    def test_real_sdk_boundary_forces_stream_before_was_stream_for_both_inputs(self):
        for stream in (False, True):
            response = TensorResponse()
            session, raw_send, auth = self.bind(response)
            self.assertIs(session.send(SimpleNamespace(method='POST', url=URL), stream=stream), response)
            self.assertIs(raw_send.call_args.kwargs['stream'], True)
            self.assertFalse(response.closed)
            auth.check.assert_called_once()

    def test_real_boundary_json_body_is_rejected_before_eager_iteration(self):
        for content_type in ('application/json', 'APPLICATION/JSON'):
            for stream in (False, True):
                response = TensorResponse(headers={'Content-Type': content_type})
                session, raw_send, auth = self.bind(response)
                with self.subTest(stream=stream), self.assertRaisesRegex(ValueError, 'checkpoint_json_body_forbidden'):
                    session.send(SimpleNamespace(method='POST', url=URL), stream=stream)
                self.assertTrue(response.closed)

    def test_real_boundary_accepts_json_location_redirect_without_read(self):
        response = TensorResponse(status=302, headers={'Content-Type': 'application/json',
            'Location': 'https://storage.googleapis.com/a'})
        session, raw_send, auth = self.bind(response)
        self.assertIs(session.send(SimpleNamespace(method='POST', url=URL)), response)

    def test_auth_deadline_mutation_and_refresh_fail_before_transport(self):
        for url in (URL.replace('DownloadKernelOutput', 'SaveKernel'),
                    'https://api.kaggle.com/v1/users.AccountService/GenerateAccessToken'):
            session, raw_send, auth = self.bind(TensorResponse())
            with self.assertRaises(ValueError):
                session.send(SimpleNamespace(method='POST', url=url))
            raw_send.assert_not_called()
        session, raw_send, auth = self.bind(TensorResponse())
        auth.check.side_effect = ValueError('stale_auth')
        with self.assertRaisesRegex(ValueError, 'stale_auth'):
            session.send(SimpleNamespace(method='POST', url=URL))
        raw_send.assert_not_called()
        auth.check.side_effect = None
        self.monotonic.return_value = old.DEADLINE
        with self.assertRaisesRegex(ValueError, 'deadline'):
            session.send(SimpleNamespace(method='POST', url=URL))
        raw_send.assert_not_called()


class HeaderPriorTests(unittest.TestCase):
    def setUp(self):
        self.chain = old.PriorTerminalTests('test_complete_real_file_launch_worker_receipt_chain_passes')
        self.chain.setUp()
        self.addCleanup(self.chain.doCleanups)
        f = self.chain
        previous = next(iter(retrieve.HEADER_PREDECESSORS))
        f.launch['helper_sha256'] = f.receipt['helper_sha256'] = previous
        f.terminal['checkpoint_archive_observation'] = {
            **retrieve.header_observation(SIZE), 'transport_observation': 'DECLARED_LOCAL_ARCHIVE_PRESENT'}
        for key in ('http_status', 'body_consumed_bytes'):
            del f.terminal['checkpoint_archive_observation'][key]
        f.terminal['external_bodies'] = {'checkpoints.zip': {
            'reason': 'separate-checkpoint-archive-body', 'descriptor': 'checkpoint-zip-descriptor.json',
            'original_bytes': SIZE, 'local_observed_bytes': SIZE, 'local_presence_observed': True,
            'original_sha256': retrieve.CHECKPOINT_SOURCE['source_sha256'],
            'local_observed_sha256': retrieve.CHECKPOINT_SOURCE['source_sha256'],
            'local_sha256_verified': True, 'archive_body_included': False,
            'external_body_materialized': False, 'external_sha256_independently_verified': False,
            'external_observed_sha256': None}}
        f.save()

    def prior(self, *, bind_synthetic=True):
        f = self.chain
        with patch.object(retrieve, 'HEADER_TERMINAL_RECEIPT_SHA256',
                          f.args.terminal_receipt_sha if bind_synthetic else retrieve.HEADER_TERMINAL_RECEIPT_SHA256), \
             patch.object(retrieve, 'HEADER_TERMINAL_FILE', f.receipt['file'] if bind_synthetic else retrieve.HEADER_TERMINAL_FILE):
            return retrieve.prior_terminal(observer, f.args, old.ARCHIVE_CAP, old.DEADLINE, checkpoint_cap=CAP)

    def test_fixed_predecessor_complete_chain_passes_without_body_reads(self):
        self.assertEqual(self.prior(), retrieve.CHECKPOINT_SOURCE)

    def test_production_pins_reject_synthetic_chain(self):
        with self.assertRaisesRegex(ValueError, 'reviewed_header_predecessor_required'):
            self.prior(bind_synthetic=False)

    def test_old_helper_remains_forbidden_to_body_archive_mode(self):
        with self.assertRaisesRegex(ValueError, 'prior_terminal_receipt_binding'):
            self.chain.prior()

    def test_unreviewed_old_helper_and_mismatched_launch_helper_rejected(self):
        f = self.chain
        for target in ('receipt', 'launch'):
            original = copy.deepcopy(getattr(f, target))
            getattr(f, target)['helper_sha256'] = '0' * 64
            f.save()
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.prior()
            setattr(f, target, original)
        f.save()

    def test_each_hash_chain_file_and_pin_required(self):
        f = self.chain
        for filename in ('launch.json', 'worker-result.json', 'payload.bin', 'retrieval-result.json'):
            path = f.directory / filename
            raw = path.read_bytes()
            path.write_bytes(raw + b' ')
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                self.prior()
            path.write_bytes(raw)

    def test_nonzero_or_incomplete_job_closure_rejects(self):
        f = self.chain
        for value in ({**old.closure(), 'active_processes': 1},
                      {**old.closure(), 'active_processes': False}, None):
            f.receipt['closure'] = value
            f.save()
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prior()

    def test_terminal_status_source_and_lease_are_revalidated(self):
        f = self.chain
        original = copy.deepcopy(f.receipt)
        worker = copy.deepcopy(f.worker)
        for field, value in (('status', 'RUNNING'), ('numeric_version', 44),
                             ('saved_source_sha256', '0'*64), ('observed_epoch', old.NOW+301)):
            f.receipt, f.worker = copy.deepcopy(original), copy.deepcopy(worker)
            f.receipt['after'][field] = f.worker['download']['after'][field] = value
            f.save()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.prior()

    def test_local_declaration_cannot_claim_remote_hash_or_wrong_size(self):
        f = self.chain
        original = copy.deepcopy(f.terminal)
        for field, value in (('present', 1), ('byte_length', True), ('byte_length', SIZE+1),
                             ('body_materialized', True), ('independently_sha256_verified', True),
                             ('observed_sha256', '0'*64),
                             ('transport_observation', 'HTTP200_CONTENT_LENGTH_VERIFIED')):
            f.terminal = copy.deepcopy(original)
            f.terminal['checkpoint_archive_observation'][field] = value
            f.save()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.prior()
        f.terminal = copy.deepcopy(original)
        f.terminal['external_bodies']['checkpoints.zip']['original_sha256'] = '0'*64
        f.save()
        with self.assertRaises(ValueError):
            self.prior()


class HeaderSupervisorTests(old.ClockedTests):
    def setUp(self):
        super().setUp()
        self.base = SimpleNamespace(**vars(observer))
        self.native_result = SimpleNamespace(code=0, reason='worker_exit', closure=old.closure())
        self.supervisor = SimpleNamespace(_install_runtime=Mock(), supervise=Mock(side_effect=self.closed_worker))
        self.base.pinned_module = Mock(return_value=self.supervisor)
        self.base.observation_output = Mock(return_value=self.directory)
        self.cli = argv()
        self.args = retrieve.arguments(self.cli)
        self.enterContext(patch.object(retrieve, 'bootstrap', return_value=(self.base, old.BRIDGE, object(),
            SimpleNamespace(executable='cpu-python'), old.metadata(), manifest(), retrieve.selected_caps(manifest()))))
        self.real_prior = retrieve.prior_terminal
        self.prior = self.enterContext(patch.object(retrieve, 'prior_terminal', return_value=retrieve.CHECKPOINT_SOURCE))
        self.mutate = lambda value: None
        self.payload = None
        self.worker = None

    def closed_worker(self, child, **kwargs):
        raw = (self.directory / 'launch.json').read_bytes()
        launch = observer.strict_json(raw)
        self.assertIn('--checkpoint-header', child)
        self.assertEqual(kwargs['timeout_seconds'], 300)
        self.assertEqual(kwargs['deadline_unix'], old.NOW+300)
        self.worker = {'format': 'irisx/v43-checkpoint-header-worker-v1', 'nonce': launch['nonce'],
            'request_sha256': observer.sha(raw), 'ok': True, 'header': {
                'before': old.snapshot(), 'after': old.snapshot(),
                'checkpoint': retrieve.header_observation(SIZE)}}
        self.mutate(self.worker)
        if self.payload:
            (self.directory / self.payload).write_bytes(b'preserve unexpected partial')
        os.write(kwargs['output_fd'], observer.canonical(self.worker))
        return self.native_result

    def run_supervisor(self):
        stdout = io.StringIO()
        with patch.object(retrieve, 'digest_file', side_effect=AssertionError('checkpoint digest')), \
             patch.object(retrieve.os, 'rename', side_effect=AssertionError('checkpoint rename')), redirect_stdout(stdout):
            code = retrieve.supervise(self.args, self.cli)
        raw = (self.directory / 'checkpoint-header-result.json').read_bytes()
        receipt = observer.strict_json(raw)
        self.assertEqual(json.loads(stdout.getvalue()), receipt)
        self.assertNotIn('download_finalized', receipt)
        self.assertNotIn('file', receipt)
        self.assertFalse((self.directory / 'retrieval-result.json').exists())
        self.assertIs(receipt['consumer_admitted'], False)
        self.assertIs(receipt['scientific_success_verified'], False)
        self.assertIs(receipt['body_materialized'], False)
        self.assertIs(receipt['independently_sha256_verified'], False)
        self.assertIsNone(receipt['observed_sha256'])
        return code, receipt

    def test_success_is_separate_header_receipt_without_payload_or_collector_admission(self):
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 0)
        self.assertIs(receipt['header_observation_finalized'], True)
        self.assertEqual(receipt['format'], 'irisx/v43-checkpoint-header-v1')
        self.assertEqual(receipt['source_checkpoint_descriptor'], retrieve.CHECKPOINT_SOURCE)
        self.assertEqual(receipt['checkpoint'], retrieve.header_observation(SIZE))
        launch = observer.strict_json((self.directory/'launch.json').read_bytes())
        self.assertEqual(launch['expected_checkpoint_source'], retrieve.CHECKPOINT_SOURCE)
        self.assertNotIn('expected_file', launch)
        self.assertFalse(any((self.directory/name).exists() for name in ('payload.part', 'payload.bin')))
        receipt_path = self.directory/'checkpoint-header-result.json'
        args = SimpleNamespace(helper_sha=self.args.helper_sha, terminal_receipt=receipt_path,
            terminal_receipt_sha=observer.sha(receipt_path.read_bytes()))
        # Invoke the real function despite this supervisor fixture's prior patch.
        with self.assertRaises(ValueError):
            self.real_prior(observer, args, old.ARCHIVE_CAP, old.DEADLINE)

    def test_new_job_nonzero_closure_cannot_finalize(self):
        self.native_result.closure['active_processes'] = 1
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 2)
        self.assertFalse(receipt['header_observation_finalized'])
        self.assertEqual(receipt['error_code'], 'new_job_closure_required')

    def test_header_schema_wrong_types_or_promoted_claims_are_rejected(self):
        for field, value in (('byte_length', float(SIZE)), ('http_status', 200.0),
                             ('body_consumed_bytes', False), ('present', 1),
                             ('observed_sha256', '0'*64), ('body_materialized', True)):
            with self.subTest(field=field):
                self.mutate = lambda result, field=field, value=value: result['header']['checkpoint'].__setitem__(field, value)
                code, receipt = self.run_supervisor()
                self.assertEqual(code, 2)
                self.assertFalse(receipt['header_observation_finalized'])
                for name in ('launch.json', 'worker-result.json', 'checkpoint-header-result.json'):
                    (self.directory/name).unlink()

    def test_worker_nonce_or_hash_mismatch_is_rejected(self):
        for field in ('nonce', 'request_sha256', 'format'):
            self.mutate = lambda result, field=field: result.__setitem__(field, 'wrong')
            code, receipt = self.run_supervisor()
            self.assertEqual(code, 2)
            self.assertFalse(receipt['header_observation_finalized'])
            for name in ('launch.json', 'worker-result.json', 'checkpoint-header-result.json'):
                (self.directory/name).unlink()

    def test_unexpected_payload_preserved_and_not_promoted(self):
        self.payload = 'payload.part'
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 2)
        self.assertEqual(receipt['error_code'], 'checkpoint_body_forbidden')
        self.assertEqual((self.directory/self.payload).read_bytes(), b'preserve unexpected partial')

    def test_stale_or_nonterminal_or_changed_source_worker_observation_rejected(self):
        for field, value in (('started_epoch', old.NOW-1), ('observed_epoch', old.NOW+301),
                             ('status', 'COMPLETE'), ('numeric_version', 44),
                             ('saved_source_sha256', '0'*64)):
            self.mutate = lambda result, field=field, value=value: result['header']['after'].__setitem__(field, value)
            code, receipt = self.run_supervisor()
            self.assertEqual(code, 2)
            self.assertFalse(receipt['header_observation_finalized'])
            for name in ('launch.json', 'worker-result.json', 'checkpoint-header-result.json'):
                (self.directory/name).unlink()

    def test_mutex_failure_is_preserved_without_takeover(self):
        self.supervisor.supervise.side_effect = ValueError('windows_duplicate_worker')
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 2)
        self.assertFalse(receipt['header_observation_finalized'])
        self.assertEqual(receipt['reason'], 'original_mutex_exists_no_takeover')

    def test_worker_failure_is_not_header_success(self):
        self.native_result.code = 2
        self.mutate = lambda result: result.update(ok=False, header=None, error='AUTH_REFRESH_UNKNOWN',
            failure_stage='auth_open', error_code='auth_refresh_unknown')
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 2)
        self.assertFalse(receipt['header_observation_finalized'])
        self.assertEqual(receipt['worker_error'], 'AUTH_REFRESH_UNKNOWN')
        self.assertEqual(receipt['worker_failure_stage'], 'auth_open')
        self.assertEqual(receipt['worker_error_code'], 'auth_refresh_unknown')

    def test_failed_header_diagnostics_survive_parent_without_success_claims(self):
        self.native_result.code = 2
        self.mutate = lambda result: result.update(ok=False, header=None,
            error='selected_retrieval_failed', failure_stage='checkpoint_rpc_headers',
            error_code='checkpoint_json_body_forbidden')
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 2)
        self.assertIs(receipt['ok'], False)
        self.assertEqual(receipt['reason'], 'worker_exit')
        self.assertEqual(receipt['worker_error'], 'selected_retrieval_failed')
        self.assertEqual(receipt['worker_failure_stage'], 'checkpoint_rpc_headers')
        self.assertEqual(receipt['worker_error_code'], 'checkpoint_json_body_forbidden')
        self.assertEqual(receipt['closure'], old.closure())
        self.assertEqual(receipt['body_consumed_bytes'], 0)
        for key in ('checkpoint', 'before', 'after', 'http_status', 'byte_length'):
            self.assertNotIn(key, receipt)

    def test_actual_worker_failure_bytes_reach_parent_classification(self):
        def closed_worker(child, **kwargs):
            fixture = HeaderWorkerTests('test_json_body_rejection_keeps_guard_code_without_body_read')
            fixture.setUp()
            try:
                fixture.args = retrieve.arguments(child[4:])
                fixture.args.output = str(fixture.directory)
                fixture.launch = observer.strict_json((self.directory / 'launch.json').read_bytes())
                fixture.save_launch()
                fixture.provider.response.headers['Content-Type'] = 'application/json'
                self.native_result.code = retrieve.worker(fixture.args)
                raw = fixture.writer.getvalue()
                self.assertIsNone(observer.strict_json(raw)['header'])
                os.write(kwargs['output_fd'], raw)
            finally:
                fixture.doCleanups()
            return self.native_result
        self.supervisor.supervise.side_effect = closed_worker
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 2)
        self.assertIs(receipt['ok'], False)
        self.assertIs(receipt['header_observation_finalized'], False)
        self.assertEqual(receipt['worker_error'], 'selected_retrieval_failed')
        self.assertEqual(receipt['worker_failure_stage'], 'checkpoint_rpc_headers')
        self.assertEqual(receipt['worker_error_code'], 'checkpoint_json_body_forbidden')
        self.assertNotIn('checkpoint', receipt)
        self.assertEqual(receipt['body_consumed_bytes'], 0)

    def test_unknown_worker_diagnostic_is_not_interpolated_or_promoted(self):
        self.native_result.code = 2
        secret = 'https://private.invalid/?token=SECRET /private/config.json'
        for field in ('error', 'failure_stage', 'error_code', 'header', 'ok'):
            for bad in (secret, [secret], {'secret': secret}, None, True):
                def mutate(result):
                    result.update(ok=False, header=None, error='selected_retrieval_failed',
                        failure_stage='checkpoint_output', error_code='unexpected_error')
                    result[field] = bad
                # None is the required failed header value, so it is not a malformed case.
                if field == 'header' and bad is None:
                    continue
                self.mutate = mutate
                with self.subTest(field=field, bad=bad):
                    code, receipt = self.run_supervisor()
                    self.assertEqual(code, 2)
                    self.assertIs(receipt['ok'], False)
                    self.assertIs(receipt['header_observation_finalized'], False)
                    self.assertEqual(receipt['failure_stage'], 'checkpoint_header_worker')
                    self.assertEqual(receipt['error_code'], 'checkpoint_header_worker_result')
                    self.assertNotIn('worker_error', receipt)
                    self.assertNotIn(secret, json.dumps(receipt))
                    self.assertNotIn('checkpoint', receipt)
                for name in ('launch.json', 'worker-result.json', 'checkpoint-header-result.json'):
                    (self.directory/name).unlink()

    def test_failed_worker_binding_is_checked_before_diagnostics(self):
        self.native_result.code = 2
        self.mutate = lambda result: result.update(ok=False, header=None, nonce='wrong',
            error='selected_retrieval_failed', failure_stage='checkpoint_output', error_code='unexpected_error')
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 2)
        self.assertEqual(receipt['error_code'], 'worker_result_binding')
        self.assertNotIn('worker_error', receipt)

    def test_unexpected_parent_exception_remains_sanitized(self):
        self.supervisor.supervise.side_effect = RuntimeError({'token': 'SECRET', 'url': 'https://private.invalid'})
        code, receipt = self.run_supervisor()
        self.assertEqual(code, 2)
        self.assertEqual(receipt['reason'], 'retrieval_supervision_failed')
        self.assertEqual(receipt['failure_stage'], 'supervise')
        self.assertEqual(receipt['error_code'], 'unexpected_error')
        self.assertNotIn('SECRET', json.dumps(receipt))
        self.assertNotIn('private.invalid', json.dumps(receipt))
        self.assertNotIn('checkpoint', receipt)


class HeaderWorkerTests(old.ClockedTests):
    def setUp(self):
        super().setUp()
        self.args = retrieve.arguments(argv() + ['--worker', '--nonce', 'a'*64,
            '--request-sha', 'b'*64, '--deadline-epoch', str(old.NOW+300)])
        self.args.output = str(self.directory)
        self.launch = {'format': 'irisx/v43-checkpoint-header-launch-v1', 'nonce': self.args.nonce,
            'provider_path': retrieve.CHECKPOINT_PATH, 'helper_sha256': self.args.helper_sha,
            'observer_sha256': retrieve.OBSERVER_SHA256, 'manifest_sha256': retrieve.MANIFEST_SHA256,
            'native_config_sha256': observer.CONFIG_SHA256, 'accepted_metadata_sha256': observer.METADATA_SHA256,
            'numeric_version': 43, 'clock': observer.CLOCK,
            'terminal_receipt_sha256': self.args.terminal_receipt_sha,
            'expected_checkpoint_source': retrieve.CHECKPOINT_SOURCE, 'cap': CAP,
            'deadline_epoch': self.args.deadline_epoch, 'max_seconds': 300,
            'scope': 'checkpoint-header-only-no-refresh-no-admission'}
        self.save_launch()
        self.writer = io.BytesIO()
        self.auth = SimpleNamespace(prepare=Mock(), protocol_ready=Mock(), open=Mock(), close=Mock())
        class AuthRefreshUnknown(Exception):
            pass
        @contextmanager
        def isolated():
            yield None, self.writer
        self.auth_module = SimpleNamespace(OfficialSession=Mock(return_value=self.auth),
            AuthRefreshUnknown=AuthRefreshUnknown, isolate_sdk_output=isolated)
        self.provider = old.FakeProvider(TensorResponse())
        self.fake_sdk = SimpleNamespace(StorageHttp=sdk.StorageHttp, WorkerProvider=Mock(return_value=self.provider))
        self.base = SimpleNamespace(**vars(observer))
        self.base.observe = Mock(side_effect=[old.snapshot(), old.snapshot()])
        self.base.pinned_module = Mock(side_effect=lambda name, *args:
            self.fake_sdk if name == 'retrieval_sdk_worker' else self.auth_module)
        self.win = SimpleNamespace(require_worker_job=Mock())
        self.enterContext(patch.object(retrieve, 'bootstrap', return_value=(self.base, old.BRIDGE,
            self.win, SimpleNamespace(versions={'active':43}), old.metadata(), manifest(),
            retrieve.selected_caps(manifest()))))
        self.prior = self.enterContext(patch.object(retrieve, 'prior_terminal', return_value=retrieve.CHECKPOINT_SOURCE))

    def save_launch(self):
        raw = observer.canonical(self.launch)
        (self.directory/'launch.json').write_bytes(raw)
        self.args.request_sha = observer.sha(raw)

    def test_real_header_worker_seals_only_header_result_with_no_refresh_facade(self):
        self.assertEqual(retrieve.worker(self.args), 0)
        value = observer.strict_json(self.writer.getvalue())
        self.assertEqual(value['format'], 'irisx/v43-checkpoint-header-worker-v1')
        self.assertEqual(set(value), {'format', 'nonce', 'request_sha256', 'ok', 'header'})
        self.assertEqual(value['header']['checkpoint'], retrieve.header_observation(SIZE))
        self.assertNotIn('download', value)
        self.win.require_worker_job.assert_called_once_with(self.args.nonce)
        facade, no_refresh = self.auth_module.OfficialSession.call_args.args[:2]
        self.assertIsInstance(facade, observer.ReadonlyRuntime)
        self.assertIsInstance(no_refresh, observer.NoRefresh)
        with self.assertRaises(ValueError):
            no_refresh.intent(None)
        with self.assertRaises(ValueError):
            with facade.credential_guard(allow_write=True):
                self.fail('refresh write guard entered')
        self.auth.close.assert_called_once()
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), ['launch.json'])

    def test_auth_refresh_failure_stops_before_output_and_remains_sanitized(self):
        self.auth.open.side_effect = self.auth_module.AuthRefreshUnknown('private refresh detail')
        self.assertEqual(retrieve.worker(self.args), 2)
        value = observer.strict_json(self.writer.getvalue())
        self.assertIs(value['ok'], False)
        self.assertIsNone(value['header'])
        self.assertEqual(value['error'], 'AUTH_REFRESH_UNKNOWN')
        self.assertEqual(value['failure_stage'], 'auth_open')
        self.assertEqual(value['error_code'], 'auth_refresh_unknown')
        self.assertEqual(self.provider.calls, [])
        self.auth.close.assert_called_once()
        self.assertNotIn(b'private refresh detail', self.writer.getvalue())

    def test_http404_missing_is_failure_without_materialization_or_secret_url(self):
        self.provider.response.status_code = 404
        self.assertEqual(retrieve.worker(self.args), 2)
        value = observer.strict_json(self.writer.getvalue())
        self.assertEqual(value['error'], 'SELECTED_OUTPUT_PENDING_OR_MISSING')
        self.assertEqual(value['failure_stage'], 'checkpoint_storage_headers')
        self.assertEqual(value['error_code'], 'http_error')
        self.assertIsNone(value['header'])
        self.assertTrue(self.provider.response.closed)
        self.assertNotIn(b'private URL', self.writer.getvalue())

    def failed_worker(self, stage, error_code, *, reason='selected_retrieval_failed'):
        self.assertEqual(retrieve.worker(self.args), 2)
        raw = self.writer.getvalue()
        value = observer.strict_json(raw)
        self.assertIs(value['ok'], False)
        self.assertIsNone(value['header'])
        self.assertEqual(value['error'], reason)
        self.assertEqual(value['failure_stage'], stage)
        self.assertEqual(value['error_code'], error_code)
        self.assertIn(value['failure_stage'], retrieve.HEADER_WORKER_STAGES)
        self.assertIn(value['error_code'], retrieve.HEADER_WORKER_ERROR_CODES)
        for key in ('checkpoint', 'http_status', 'byte_length', 'body_materialized', 'download'):
            self.assertNotIn(key, value)
        self.assertNotIn(b'SECRET', raw)
        self.assertNotIn(b'private.invalid', raw)
        self.assertFalse(any((self.directory/name).exists() for name in ('payload.part', 'payload.bin')))
        return value

    def test_each_auth_stage_preserves_only_safe_classification(self):
        for method, stage in (('prepare', 'auth_prepare'), ('protocol_ready', 'auth_protocol_ready'),
                              ('open', 'auth_open')):
            self.writer.seek(0)
            self.writer.truncate()
            with self.subTest(stage=stage), patch.object(self.auth, method,
                    Mock(side_effect=RuntimeError('https://private.invalid/?token=SECRET'))):
                self.failed_worker(stage, 'unexpected_error')
            self.assertEqual(self.provider.calls, [])

    def test_known_auth_guard_code_is_preserved(self):
        self.auth.prepare.side_effect = observer.ObserverError('official_sdk_source_closure')
        self.failed_worker('auth_prepare', 'official_sdk_source_closure')
        self.assertEqual(self.provider.calls, [])

    def test_unknown_exception_does_not_call_str_or_echo_nonstring_arguments(self):
        class PrivateException(Exception):
            def __str__(self):
                raise AssertionError('must not render SECRET exception')
        for error in (PrivateException('SECRET'), ValueError(['SECRET']),
                      RuntimeError({'url': 'https://private.invalid/?token=SECRET'}),
                      ValueError('checkpoint_header_length', 'SECRET')):
            self.writer.seek(0)
            self.writer.truncate()
            self.auth.open.side_effect = error
            with self.subTest(error_type=type(error).__name__):
                self.failed_worker('auth_open', 'unexpected_error')
        self.assertEqual(self.provider.calls, [])

    def test_provider_setup_exception_is_sanitized(self):
        self.fake_sdk.WorkerProvider.side_effect = TypeError('SECRET constructor config')
        self.failed_worker('provider_setup', 'unexpected_error')
        self.assertEqual(self.provider.calls, [])

    def test_before_guard_is_classified_without_output(self):
        self.base.observe.side_effect = observer.ObserverError('v43_source_changed')
        self.failed_worker('checkpoint_before', 'v43_source_changed')
        self.assertEqual(self.provider.calls, [])

    def test_nonterminal_classification_survives_without_output(self):
        self.base.observe.side_effect = [old.snapshot('RUNNING')]
        self.failed_worker('checkpoint_before', 'provider_not_terminal', reason='PROVIDER_NOT_TERMINAL')
        self.assertEqual(self.provider.calls, [])

    def test_output_exception_does_not_leak_response_or_signed_url(self):
        self.provider.output = Mock(side_effect=HTTPError('https://private.invalid/?token=SECRET',
            response=SimpleNamespace(status_code=403, headers={'Authorization': 'SECRET'})))
        self.failed_worker('checkpoint_output', 'http_error')
        self.provider.output.assert_called_once_with(retrieve.CHECKPOINT_PATH, 43)
        self.base.observe.assert_called_once()

    def test_json_body_rejection_keeps_guard_code_without_body_read(self):
        self.provider.response.headers['Content-Type'] = 'application/json'
        self.failed_worker('checkpoint_rpc_headers', 'checkpoint_json_body_forbidden')
        self.assertTrue(self.provider.response.closed)
        self.assertEqual(self.provider.calls, [('output', retrieve.CHECKPOINT_PATH, 43)])
        self.base.observe.assert_called_once()

    def test_header_length_rejection_has_no_partial_header_success(self):
        self.provider.response.headers['Content-Length'] = str(SIZE-1)
        self.failed_worker('checkpoint_validate_headers', 'checkpoint_header_length')
        self.assertTrue(self.provider.response.closed)
        self.base.observe.assert_called_once()

    def test_after_guard_failure_discards_provisional_header_success(self):
        self.base.observe.side_effect = [old.snapshot(), observer.ObserverError('v43_metadata_changed')]
        self.failed_worker('checkpoint_after', 'v43_metadata_changed')
        self.assertTrue(self.provider.response.closed)
        self.assertEqual(self.base.observe.call_count, 2)

    def test_bracket_failure_discards_provisional_header_success(self):
        self.base.observe.side_effect = [old.snapshot(), old.snapshot('COMPLETE')]
        self.failed_worker('checkpoint_terminal_brackets', 'terminal_bracket_changed')
        self.assertTrue(self.provider.response.closed)

    def test_job_membership_and_expired_worker_lease_stop_before_auth(self):
        self.win.require_worker_job.side_effect = ValueError('worker_job_missing')
        with self.assertRaisesRegex(ValueError, 'worker_job_missing'):
            retrieve.worker(self.args)
        self.auth_module.OfficialSession.assert_not_called()
        self.win.require_worker_job.side_effect = None
        self.args.deadline_epoch = float(old.NOW)
        with self.assertRaisesRegex(ValueError, 'worker_lease'):
            retrieve.worker(self.args)
        self.auth_module.OfficialSession.assert_not_called()

    def test_mismatched_launch_bindings_rejected_before_auth(self):
        original = copy.deepcopy(self.launch)
        for key, value in (('format', 'irisx/v43-selected-launch-v1'), ('helper_sha256', '0'*64),
                           ('numeric_version', 43.0), ('cap', float(CAP)), ('deadline_epoch', old.NOW+299),
                           ('terminal_receipt_sha256', '0'*64), ('expected_checkpoint_source', None),
                           ('scope', 'single-selected-output-no-refresh-no-admission')):
            self.launch = copy.deepcopy(original)
            self.launch[key] = value
            self.save_launch()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'checkpoint_launch_binding'):
                retrieve.worker(self.args)
            self.auth_module.OfficialSession.assert_not_called()

    def test_invalid_actual_prior_chain_stops_before_sdk_and_auth(self):
        self.prior.side_effect = ValueError('prior_terminal_worker_binding')
        with self.assertRaisesRegex(ValueError, 'prior_terminal_worker_binding'):
            retrieve.worker(self.args)
        self.base.pinned_module.assert_not_called()
        self.auth_module.OfficialSession.assert_not_called()


class HeaderArgumentsTests(unittest.TestCase):
    def test_header_requires_explicit_mode_fixed_path_and_prior_pair(self):
        args = retrieve.arguments(argv())
        self.assertTrue(args.checkpoint_header)
        self.assertEqual(args.name, retrieve.CHECKPOINT_PATH)
        for values in (old.argv()+['--checkpoint-header'],
                       old.argv(retrieve.CHECKPOINT_PATH)+['--checkpoint-header'],
                       argv()+['--checkpoint-header']):
            with self.subTest(values=values), self.assertRaises(ValueError):
                retrieve.arguments(values)
        self.assertNotIn(retrieve.CHECKPOINT_PATH, retrieve.selected_caps(manifest()))

    def test_exact_manifest_checkpoint_cap_true_integer(self):
        self.assertEqual(retrieve.checkpoint_cap(manifest()), CAP)
        for value in (True, float(CAP), CAP-1, CAP+1, str(CAP), None):
            m = manifest()
            m['terminal_contract']['archive_caps']['checkpoint_archive_bytes'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                retrieve.checkpoint_cap(m)

    def test_published_pins_remain_exact(self):
        self.assertEqual(retrieve.HEADER_PREDECESSORS, {'1bdadfd56c68f53528babf64390295bb53965884bb9eacaff5f20a207e53d615'})
        self.assertEqual(retrieve.HEADER_TERMINAL_RECEIPT_SHA256, 'c7aed6c2ea053b4dde32fdb280b36e6694f9da282b9db872abde53185082c697')
        self.assertEqual(retrieve.HEADER_TERMINAL_FILE, {'bytes':119652,
            'sha256':'a95c964a8e29d5b27e067ac1a6ee66af7efe345cd55684f88ab11a0cf32092a7'})
        self.assertEqual(hashlib.sha256((old.HERE/'observe.py').read_bytes()).hexdigest(), retrieve.OBSERVER_SHA256)
        for name, digest in observer.PINS.items():
            self.assertEqual(hashlib.sha256((old.BRIDGE/name).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()

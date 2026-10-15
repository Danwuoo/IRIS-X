"""Offline CPU contract tests for one separately supervised v43 output retrieval.

The real observer and storage parsers are exercised with local fake responses.
No credentials, network requests, native jobs, or collector imports are used.
"""
import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / 'retrieve.py'
BRIDGE = HERE.parent / 'publication_windows_bridge_20261015'
ORIGINAL = HERE.parent / 'publication_run008' / 'rl_collect.py'
ARCHIVE_CAP = 5 * 1024**3 + 16 * 1024**2
TERMINAL_CAP = 16 * 1024**2
DEADLINE = 1000.0


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


retrieve = load('selected_retrieval_under_test', SOURCE)
observer = load('selected_retrieval_observer_fixture', HERE / 'observe.py')
sdk = load('selected_retrieval_storage_fixture', BRIDGE / 'sdk_worker.py')
NOW = observer.CLOCK['original_epoch'] + 100
FAKE_SOURCE = 'Synthetic source for CPU-only retrieval tests.\n'
FAKE_SOURCE_SHA = hashlib.sha256(FAKE_SOURCE.encode()).hexdigest()


def descriptor(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def manifest():
    return {'terminal_contract': {
        'terminal_path': retrieve.TERMINAL_PATH,
        'evidence_path': retrieve.EVIDENCE_PATH,
        'checkpoint_path': retrieve.PREFIX + '/checkpoints.zip',
        'archive_caps': {'evidence_archive_bytes': ARCHIVE_CAP}}}


def metadata():
    return {'id': observer.KERNEL_ID, 'ref': observer.REFERENCE,
            'currentVersionNumber': 43, 'isPrivate': True, 'enableGpu': True,
            'enableTpu': False, 'enableInternet': False,
            'machineShape': 'NvidiaRtxPro6000', 'title': 'Synthetic CPU fixture'}


def kernel():
    return {'metadata': metadata(), 'blob': {'source': FAKE_SOURCE}}


def snapshot(status='ERROR'):
    return {'reference': observer.REFERENCE, 'kernel_id': observer.KERNEL_ID,
            'numeric_version': 43, 'code_version': 22,
            'saved_source_sha256': observer.SOURCE_SHA256,
            'metadata_sha256': observer.METADATA_SHA256, 'status': status,
            'failure_message': 'Provider error' if status == 'ERROR' else '',
            'terminal': status in observer.TERMINAL, 'started_epoch': NOW,
            'observed_epoch': NOW, 'clock': copy.deepcopy(observer.CLOCK),
            'source_and_metadata_bracket_verified': True,
            'remote_process_closure_verified': False, 'billing_verified': False,
            'scientific_success_verified': False, 'old_native_session_closure_verified': False}


def closure():
    return {'format': 'irisx/windows-job-closure-v1', 'active_processes': 0,
            'kill_on_close': True, 'breakaway_permitted': False,
            'atomic_job_assignment': True}


def argv(name=None):
    return ['--helper-sha', hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            '--bridge-root', '/cpu/bridge', '--config', '/cpu/config.json',
            '--config-sha', observer.CONFIG_SHA256,
            '--accepted-metadata', '/cpu/accepted.json',
            '--accepted-metadata-sha', observer.METADATA_SHA256,
            '--manifest', '/cpu/manifest.json', '--manifest-sha', retrieve.MANIFEST_SHA256,
            '--name', retrieve.TERMINAL_PATH if name is None else name,
            '--output', '/cpu/output']


class FakeResponse:
    def __init__(self, body=b'cpu evidence', headers=None, chunks=None, status=200):
        self.body, self.status_code = body, status
        self.headers = {'Content-Length': str(len(body)), 'Content-Encoding': 'identity',
                        'Content-Type': 'application/octet-stream'}
        if headers is not None:
            self.headers.update(headers)
        self.blocks = [body] if chunks is None else chunks
        self.closed = False

    def iter_content(self, unused_size):
        yield from self.blocks

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError('synthetic_http_status')

    def close(self):
        self.closed = True


class FakeProvider:
    def __init__(self, response=None, statuses=('ERROR', 'ERROR'), kernels=None):
        self.response = FakeResponse() if response is None else response
        self.statuses = iter(statuses)
        self.kernels = iter([kernel() for _ in range(4)] if kernels is None else kernels)
        self.calls = []

    def kernel(self):
        self.calls.append('kernel')
        return next(self.kernels)

    def status(self):
        self.calls.append('status')
        status = next(self.statuses)
        return {'status': status, 'failureMessage': 'Provider error' if status == 'ERROR' else ''}

    def output(self, name, version):
        self.calls.append(('output', name, version))
        return self.response


class ClockedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.monotonic = self.enterContext(patch.object(retrieve.time, 'monotonic', return_value=100.0))
        self.wall = self.enterContext(patch.object(retrieve.time, 'time', return_value=NOW))


class SelectedContractTests(unittest.TestCase):
    def test_caps_equal_original_collector_function_without_importing_it(self):
        parsed = ast.parse(ORIGINAL.read_text(encoding='utf-8'), filename=str(ORIGINAL))
        function = next(node for node in parsed.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'output_paths')
        isolated = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        ns = {'Path': Path, 'transport': SimpleNamespace(
            row=lambda unused_manifest, role: {'output_root': '/kaggle/working/' + retrieve.PREFIX})}
        exec(compile(isolated, str(ORIGINAL), 'exec'), ns)
        prefix, unused_outer, original_caps, required = ns['output_paths'](manifest())
        self.assertEqual(prefix, retrieve.PREFIX)
        self.assertEqual(retrieve.selected_caps(manifest()), original_caps)
        self.assertTrue(required <= original_caps.keys())
        self.assertEqual(original_caps[retrieve.EVIDENCE_PATH], ARCHIVE_CAP)
        self.assertEqual(original_caps[retrieve.TERMINAL_PATH], TERMINAL_CAP)
        self.assertEqual(retrieve.RESERVE, 4 * 1024**3)
        self.assertEqual(retrieve.MAX_SECONDS, 300)

    def test_archive_cap_is_exact_original_cap_and_true_integer(self):
        for bad in (True, False, 1, 0, -1, ARCHIVE_CAP - 1, ARCHIVE_CAP + 1,
                    8 * 1024**3, float(ARCHIVE_CAP), str(ARCHIVE_CAP), None):
            value = manifest()
            value['terminal_contract']['archive_caps']['evidence_archive_bytes'] = bad
            with self.subTest(cap=bad), self.assertRaises(ValueError):
                retrieve.selected_caps(value)

    def test_contract_cannot_redirect_fixed_paths(self):
        for key in ('terminal_path', 'evidence_path', 'checkpoint_path'):
            value = manifest()
            value['terminal_contract'][key] = 'other/path'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'fixed_output_contract'):
                retrieve.selected_caps(value)

    def test_no_arbitrary_paths_checkpoint_bodies_or_expanded_failure_paths(self):
        caps = retrieve.selected_caps(manifest())
        denied = ('anything.json', '../payload.bin', '/absolute/file', 'a\\b',
                  retrieve.PREFIX + '/checkpoints.zip', retrieve.PREFIX + '/experiment/result.json',
                  retrieve.PREFIX + '/physical-journal.jsonl', retrieve.PREFIX + '/worker.stdout.log')
        for name in denied:
            with self.subTest(name=name):
                self.assertNotIn(name, caps)
        for name, cap in caps.items():
            self.assertIs(type(cap), int)
            self.assertGreater(cap, 0)
            self.assertFalse(name.startswith('/'))
            self.assertNotIn('..', name.split('/'))

    def test_bootstrap_denies_unknown_paths_before_sdk_or_provider_loading(self):
        raw = observer.canonical(manifest())
        raw += b' ' * (134508 - len(raw))
        helper_raw = SOURCE.read_bytes()
        helper_sha = hashlib.sha256(helper_raw).hexdigest()
        runtime = SimpleNamespace(versions={'active': 43})
        win = SimpleNamespace(read_source=Mock(side_effect=lambda path, cap:
            raw if str(path) == '/cpu/manifest.json' else helper_raw))
        base = SimpleNamespace(**vars(observer))
        base.read_pinned = Mock(return_value=helper_raw)
        base.bootstrap = Mock(return_value=(BRIDGE, win, runtime, metadata()))
        # Only immutable-input transport is substituted; the selected-path gate is real.
        base.sha = lambda value: retrieve.MANIFEST_SHA256 if value == raw else observer.sha(value)
        with patch.object(retrieve, 'load_observer', return_value=base):
            for name in ('arbitrary.txt', retrieve.PREFIX + '/checkpoints.zip', '../payload.bin',
                         retrieve.PREFIX + '/experiment/result.json'):
                args = retrieve.arguments(argv(name))
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unreviewed_output_path'):
                    retrieve.bootstrap(args)
            args = retrieve.arguments(argv())
            result = retrieve.bootstrap(args)
            self.assertEqual(result[-1], retrieve.selected_caps(manifest()))
            self.assertEqual(args.helper_sha, helper_sha)
            passed = base.bootstrap.call_args.args[0]
            self.assertEqual(passed.helper_sha, retrieve.OBSERVER_SHA256)

    def test_published_observer_hash_is_unchanged(self):
        expected = '696cbfc6336fa208526352c4479bf3a32eb5a835d8fa75aca01a87ffa7346655'
        self.assertEqual(retrieve.OBSERVER_SHA256, expected)
        self.assertEqual(hashlib.sha256((HERE / 'observe.py').read_bytes()).hexdigest(), expected)
        self.assertEqual(retrieve.load_observer().SOURCE_SHA256, observer.SOURCE_SHA256)

    def test_download_only_facade_delegates_reads_and_never_uploads(self):
        inner = Mock()
        facade = retrieve.DownloadOnly(inner)
        response = object()
        self.assertIs(facade.download(response, 7), inner.download.return_value)
        self.assertIs(facade.chunks(response, 7), inner.chunks.return_value)
        inner.download.assert_called_once_with(response, 7)
        inner.chunks.assert_called_once_with(response, 7)
        with self.assertRaisesRegex(ValueError, 'upload_forbidden'):
            facade.put('https://example.invalid', b'private', size=7)
        inner.put.assert_not_called()


class ReadonlyBoundaryTests(unittest.TestCase):
    def bind(self):
        downstream = Mock(return_value='bounded response')
        session = SimpleNamespace(send=Mock(side_effect=AssertionError('unbound transport')))
        client = SimpleNamespace(http_client=lambda: SimpleNamespace(_session=session))
        boundary = Mock()
        boundary.bind.side_effect = lambda unused_client, unused_auth: setattr(session, 'send', downstream)
        fake_sdk = SimpleNamespace(HttpBoundary=Mock(return_value=boundary))
        auth = object()
        retrieve.bind_readonly(observer, fake_sdk, client, auth, 100.0)
        boundary.bind.assert_called_once_with(client, auth)
        return session, downstream

    def test_exact_three_post_rpcs_on_exact_two_authorities(self):
        for authority in ('https://api.kaggle.com', 'https://api.kaggle.com:443'):
            for operation in ('GetKernel', 'GetKernelSessionStatus', 'DownloadKernelOutput'):
                session, downstream = self.bind()
                request = SimpleNamespace(method='POST', url=authority + '/v1/kernels.KernelsApiService/' + operation)
                with self.subTest(url=request.url), patch.object(retrieve.time, 'monotonic', return_value=99):
                    self.assertEqual(session.send(request, timeout=3), 'bounded response')
                downstream.assert_called_once_with(request, timeout=3)

    def test_mutation_refresh_other_reads_and_url_variants_cannot_reach_transport(self):
        good = 'https://api.kaggle.com/v1/kernels.KernelsApiService/GetKernel'
        urls = [good.replace('GetKernel', operation) for operation in (
            'SaveKernel', 'CancelKernelSession', 'ListKernelSessionFiles', 'GetKernelSessionOutput',
            'RefreshToken', 'GenerateAccessToken', 'GetDataset')]
        urls += [good + suffix for suffix in ('/', '?x=1', '#f', ';x')]
        urls += [good.replace('api.kaggle.com', host) for host in (
            'api.kaggle.com.evil.example', 'api.kaggle.com:444', 'user@api.kaggle.com', 'API.KAGGLE.COM')]
        urls += [good.replace('https:', 'http:'), good.replace('/v1/', '//v1/'),
                 good.replace('/GetKernel', '/%47etKernel'), good.replace('/GetKernel', '/../GetKernel'),
                 'https://api.kaggle.com/v1/users.AccountService/GenerateAccessToken',
                 'https://storage.googleapis.com/fake.bin']
        for url in urls:
            session, downstream = self.bind()
            with self.subTest(url=url), patch.object(retrieve.time, 'monotonic', return_value=99):
                with self.assertRaisesRegex(ValueError, 'readonly_retrieval_rpc_required'):
                    session.send(SimpleNamespace(method='POST', url=url))
            downstream.assert_not_called()
        for method in ('GET', 'PUT', 'PATCH', 'DELETE', 'post', None):
            session, downstream = self.bind()
            with self.subTest(method=method), patch.object(retrieve.time, 'monotonic', return_value=99):
                with self.assertRaises(ValueError):
                    session.send(SimpleNamespace(method=method, url=good))
            downstream.assert_not_called()

    def test_expired_deadline_stops_before_transport(self):
        for now in (100, 101):
            session, downstream = self.bind()
            with self.subTest(now=now), patch.object(retrieve.time, 'monotonic', return_value=now):
                with self.assertRaisesRegex(ValueError, 'retrieval_deadline'):
                    session.send(SimpleNamespace(method='POST', url='https://api.kaggle.com/v1/kernels.KernelsApiService/GetKernel'))
            downstream.assert_not_called()


class RetrieveOneTests(ClockedTests):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(observer, 'SOURCE_SHA256', FAKE_SOURCE_SHA))
        self.base = SimpleNamespace(**vars(observer))
        self.base.METADATA_SHA256 = observer.sha(observer.canonical(metadata()))
        self.base.observe = lambda provider, expected: observer.observe(provider, expected, wall=lambda: NOW)
        self.disk = self.enterContext(patch.object(retrieve.shutil, 'disk_usage',
            return_value=SimpleNamespace(free=retrieve.RESERVE + ARCHIVE_CAP + 1)))
        self.storage = retrieve.DownloadOnly(sdk.StorageHttp(requests_module=Mock(
            side_effect=AssertionError('network is forbidden'))))

    def run_retrieval(self, provider=None, expected_file=None, cap=1024):
        return retrieve.retrieve_one(self.base, provider or FakeProvider(), self.storage,
            metadata(), retrieve.TERMINAL_PATH, cap, self.directory, DEADLINE, expected_file)

    def test_running_never_requests_output_or_creates_payload(self):
        provider = FakeProvider(statuses=('RUNNING',))
        with self.assertRaisesRegex(ValueError, 'provider_not_terminal'):
            self.run_retrieval(provider)
        self.assertEqual(provider.calls, ['kernel', 'status', 'kernel'])
        self.assertFalse((self.directory / 'payload.part').exists())
        self.disk.assert_not_called()

    def test_success_requires_exact_v43_and_source_terminal_brackets(self):
        provider = FakeProvider()
        result = self.run_retrieval(provider, descriptor(provider.response.body))
        self.assertEqual(provider.calls, ['kernel', 'status', 'kernel',
            ('output', retrieve.TERMINAL_PATH, 43), 'kernel', 'status', 'kernel'])
        self.assertIs(type(provider.calls[3][2]), int)
        self.assertEqual(result['file'], descriptor(provider.response.body))
        for position in ('before', 'after'):
            self.assertIs(result[position]['terminal'], True)
            self.assertIs(result[position]['source_and_metadata_bracket_verified'], True)
            self.assertEqual(result[position]['numeric_version'], 43)
        self.assertEqual((self.directory / 'payload.part').read_bytes(), provider.response.body)
        self.assertFalse((self.directory / 'payload.bin').exists())
        self.assertTrue(provider.response.closed)

    def test_changed_source_at_each_of_four_bracket_reads_fails(self):
        for index in range(4):
            with self.subTest(index=index), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                values = [kernel() for _ in range(4)]
                values[index]['blob']['source'] += 'tampered'
                provider = FakeProvider(kernels=values)
                with self.assertRaisesRegex(ValueError, 'v43_source_changed'):
                    retrieve.retrieve_one(self.base, provider, self.storage, metadata(),
                        retrieve.TERMINAL_PATH, 1024, tmp, DEADLINE)
                if index < 2:
                    self.assertFalse(any(isinstance(call, tuple) for call in provider.calls))
                self.assertFalse((Path(tmp) / 'payload.bin').exists())

    def test_changed_version_or_metadata_at_each_bracket_read_fails(self):
        for index in range(4):
            with self.subTest(index=index), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                values = [kernel() for _ in range(4)]
                values[index]['metadata']['currentVersionNumber'] = 44
                provider = FakeProvider(kernels=values)
                with self.assertRaisesRegex(ValueError, 'v43_metadata_changed'):
                    retrieve.retrieve_one(self.base, provider, self.storage, metadata(),
                        retrieve.TERMINAL_PATH, 1024, tmp, DEADLINE)

    def test_status_drift_or_return_to_running_rejects(self):
        for after in ('COMPLETE', 'RUNNING', 'CANCELLED'):
            with self.subTest(after=after), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                provider = FakeProvider(statuses=('ERROR', after))
                with self.assertRaisesRegex(ValueError, 'terminal_(bracket_changed|source_bracket_required)'):
                    retrieve.retrieve_one(self.base, provider, self.storage, metadata(),
                        retrieve.TERMINAL_PATH, 1024, tmp, DEADLINE)

    def test_expected_sha_mismatch_and_expected_length_mismatch_reject(self):
        for expected in ({'bytes': 12, 'sha256': '0' * 64},
                         {'bytes': 13, 'sha256': descriptor(b'cpu evidence')['sha256']}):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                with self.assertRaises(ValueError):
                    retrieve.retrieve_one(self.base, FakeProvider(), self.storage, metadata(),
                        retrieve.TERMINAL_PATH, 1024, tmp, DEADLINE, expected)

    def test_declared_length_malformed_or_truncated_rejects(self):
        for declared in ('', '-1', 'NaN', '1.5', '999999', '13', '10', ' 12', '+12', True, 12):
            with self.subTest(declared=declared), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                response = FakeResponse()
                if declared is None:
                    del response.headers['Content-Length']
                else:
                    response.headers['Content-Length'] = declared
                with self.assertRaises(ValueError):
                    retrieve.retrieve_one(self.base, FakeProvider(response), self.storage, metadata(),
                        retrieve.TERMINAL_PATH, 1024, tmp, DEADLINE)

    def test_missing_content_length_can_use_exact_expected_bytes_and_hash(self):
        response = FakeResponse()
        del response.headers['Content-Length']
        self.assertEqual(self.run_retrieval(FakeProvider(response), descriptor(response.body))['file'],
                         descriptor(response.body))

    def test_expected_length_uses_archive_size_for_initial_reserve(self):
        response = FakeResponse()
        self.disk.return_value = SimpleNamespace(free=retrieve.RESERVE + len(response.body))
        self.assertEqual(self.run_retrieval(FakeProvider(response), descriptor(response.body))['file'],
                         descriptor(response.body))

    def test_final_disk_reserve_is_rechecked_after_stream_closes(self):
        self.disk.side_effect = [SimpleNamespace(free=retrieve.RESERVE + 1024),
                                 SimpleNamespace(free=retrieve.RESERVE + 12),
                                 SimpleNamespace(free=retrieve.RESERVE - 1)]
        with self.assertRaisesRegex(ValueError, 'reserve'):
            self.run_retrieval()
        self.assertEqual(self.disk.call_count, 3)

    def test_encoded_body_rejects_without_finalization(self):
        for encoding in ('gzip', 'br', 'deflate', 'Identity', 'identity,gzip'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                response = FakeResponse(headers={'Content-Encoding': encoding})
                with self.assertRaises(ValueError):
                    retrieve.retrieve_one(self.base, FakeProvider(response), self.storage, metadata(),
                        retrieve.TERMINAL_PATH, 1024, tmp, DEADLINE)
                self.assertFalse((Path(tmp) / 'payload.bin').exists())

    def test_stream_cannot_exceed_selected_budget_even_with_false_header(self):
        response = FakeResponse(headers={'Content-Length': '5'}, chunks=[b'12345', b'6'])
        with self.assertRaises(ValueError):
            self.run_retrieval(FakeProvider(response), cap=5)
        self.assertFalse((self.directory / 'payload.bin').exists())

    def test_low_initial_disk_reserve_rejects_before_output(self):
        self.disk.return_value = SimpleNamespace(free=retrieve.RESERVE + 1023)
        provider = FakeProvider()
        with self.assertRaisesRegex(ValueError, 'download_disk_reserve'):
            self.run_retrieval(provider, cap=1024)
        self.assertFalse(any(isinstance(call, tuple) for call in provider.calls))

    def test_exact_initial_reserve_boundary_is_admitted(self):
        self.disk.return_value = SimpleNamespace(free=retrieve.RESERVE + 1024)
        self.assertEqual(self.run_retrieval(cap=1024)['file'], descriptor(b'cpu evidence'))

    def test_disk_reserve_is_checked_during_streaming(self):
        self.disk.side_effect = [SimpleNamespace(free=retrieve.RESERVE + 1024),
                                 SimpleNamespace(free=retrieve.RESERVE - 1)]
        response = FakeResponse(body=b'ab', chunks=[b'a', b'b'])
        with self.assertRaisesRegex(ValueError, 'reserve'):
            self.run_retrieval(FakeProvider(response))
        self.assertGreaterEqual(self.disk.call_count, 2)
        self.assertFalse((self.directory / 'payload.bin').exists())

    def test_monotonic_or_original_global_deadline_rejects(self):
        for monotonic, wall in ((DEADLINE, NOW), (DEADLINE - 1, observer.CLOCK['global_deadline'])):
            with self.subTest(monotonic=monotonic, wall=wall), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                self.monotonic.return_value = monotonic
                self.wall.return_value = wall
                with self.assertRaisesRegex(ValueError, 'deadline'):
                    retrieve.retrieve_one(self.base, FakeProvider(), self.storage, metadata(),
                        retrieve.TERMINAL_PATH, 1024, tmp, DEADLINE)

    def test_deadline_expiring_midstream_rejects(self):
        def chunks():
            yield b'a'
            self.monotonic.return_value = DEADLINE
            yield b'b'
        response = FakeResponse(body=b'ab', chunks=chunks())
        with self.assertRaisesRegex(ValueError, 'deadline'):
            self.run_retrieval(FakeProvider(response))
        self.assertFalse((self.directory / 'payload.bin').exists())

    def test_existing_partial_or_final_payload_is_never_overwritten(self):
        for filename in ('payload.part', 'payload.bin'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                path = Path(tmp) / filename
                path.write_bytes(b'preserve')
                provider = FakeProvider()
                with self.assertRaises(ValueError):
                    retrieve.retrieve_one(self.base, provider, self.storage, metadata(),
                        retrieve.TERMINAL_PATH, 1024, tmp, DEADLINE)
                self.assertEqual(path.read_bytes(), b'preserve')
                self.assertFalse(any(isinstance(call, tuple) for call in provider.calls))

    def test_boolean_cap_and_expected_length_are_not_numeric_sizes(self):
        for cap, expected in ((True, None), (False, None),
                              (1024, {'bytes': True, 'sha256': descriptor(b'x')['sha256']})):
            with self.subTest(cap=cap, expected=expected), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                with self.assertRaises(ValueError):
                    retrieve.retrieve_one(self.base, FakeProvider(FakeResponse(b'x')), self.storage,
                        metadata(), retrieve.TERMINAL_PATH, cap, tmp, DEADLINE, expected)


class DigestFileTests(ClockedTests):
    def test_regular_file_digest_and_exact_cap(self):
        path = self.directory / 'file.bin'
        path.write_bytes(b'abc')
        self.assertEqual(retrieve.digest_file(observer, path, 3, DEADLINE), descriptor(b'abc'))

    def test_zero_byte_file_is_valid(self):
        path = self.directory / 'empty.bin'
        path.write_bytes(b'')
        self.assertEqual(retrieve.digest_file(observer, path, 0, DEADLINE), descriptor(b''))

    def test_file_and_parent_symlinks_rejected(self):
        real = self.directory / 'real'
        real.mkdir()
        path = real / 'file.bin'
        path.write_bytes(b'abc')
        linked_file = self.directory / 'file-link'
        linked_file.symlink_to(path)
        linked_parent = self.directory / 'parent-link'
        linked_parent.symlink_to(real, target_is_directory=True)
        for bad in (linked_file, linked_parent / 'file.bin'):
            with self.subTest(path=bad), self.assertRaisesRegex(ValueError, 'linked_path_forbidden'):
                retrieve.digest_file(observer, bad, 3, DEADLINE)

    def test_hardlink_directory_and_oversize_file_rejected(self):
        path = self.directory / 'file.bin'
        path.write_bytes(b'abc')
        with self.assertRaisesRegex(ValueError, 'bounded_download_file'):
            retrieve.digest_file(observer, path, 2, DEADLINE)
        os.link(path, self.directory / 'hardlink')
        for bad in (path, self.directory):
            with self.subTest(path=bad), self.assertRaisesRegex(ValueError, 'bounded_download_file'):
                retrieve.digest_file(observer, bad, 100, DEADLINE)

    def test_digest_cap_requires_integer_not_bool_or_float(self):
        path = self.directory / 'file.bin'
        path.write_bytes(b'a')
        for cap in (True, 1.0):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                retrieve.digest_file(observer, path, cap, DEADLINE)

    def test_replacement_after_read_is_rejected(self):
        path = self.directory / 'file.bin'
        replacement = self.directory / 'other.bin'
        path.write_bytes(b'abc')
        replacement.write_bytes(b'abc')
        base = SimpleNamespace(**vars(observer))
        base.no_links = Mock(side_effect=[path, replacement])
        with self.assertRaisesRegex(ValueError, 'download_file_changed'):
            retrieve.digest_file(base, path, 3, DEADLINE)

    def test_both_deadlines_apply_to_digest(self):
        path = self.directory / 'file.bin'
        path.write_bytes(b'abc')
        for monotonic, wall in ((DEADLINE, NOW), (100, observer.CLOCK['global_deadline'])):
            self.monotonic.return_value, self.wall.return_value = monotonic, wall
            with self.subTest(monotonic=monotonic, wall=wall), self.assertRaisesRegex(ValueError, 'deadline'):
                retrieve.digest_file(observer, path, 3, DEADLINE)

    def test_identity_change_between_stat_and_open_rejected(self):
        path = self.directory / 'file.bin'
        path.write_bytes(b'abc')
        original = os.fstat
        def changed(fd):
            value = original(fd)
            fields = {key: getattr(value, key) for key in
                      ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')}
            fields['st_ino'] += 1
            return SimpleNamespace(**fields)
        with patch.object(retrieve.os, 'fstat', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'download_file_changed'):
                retrieve.digest_file(observer, path, 3, DEADLINE)


class PriorTerminalTests(ClockedTests):
    def setUp(self):
        super().setUp()
        self.helper_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        self.terminal = {'format': 'owned-rl-evidence-terminal-v1',
            'output_root': '/kaggle/working/' + retrieve.PREFIX, 'archive_complete': True,
            'status': 'diagnostic', 'mode': 'runtime-reload-bound',
            'archive': {'path': '/kaggle/working/' + retrieve.EVIDENCE_PATH,
                        'bytes': 7, 'sha256': hashlib.sha256(b'archive').hexdigest()}}
        self.launch = {'format': 'irisx/v43-selected-launch-v1', 'nonce': 'a' * 64,
            'helper_sha256': self.helper_sha, 'observer_sha256': retrieve.OBSERVER_SHA256,
            'native_config_sha256': observer.CONFIG_SHA256,
            'accepted_metadata_sha256': observer.METADATA_SHA256,
            'manifest_sha256': retrieve.MANIFEST_SHA256, 'provider_path': retrieve.TERMINAL_PATH,
            'numeric_version': 43, 'clock': copy.deepcopy(observer.CLOCK),
            'deadline_epoch': NOW + 300, 'max_seconds': 300, 'terminal_receipt_sha256': None,
            'expected_file': None, 'cap': TERMINAL_CAP,
            'scope': 'single-selected-output-no-refresh-no-admission'}
        self.worker = {'format': 'irisx/v43-selected-worker-v1', 'nonce': self.launch['nonce'],
            'request_sha256': None, 'ok': True, 'download': {
                'before': snapshot(), 'after': snapshot(), 'file': None}}
        self.receipt = {'format': 'irisx/v43-selected-retrieval-v1', 'nonce': self.launch['nonce'],
            'request_sha256': None, 'ok': True, 'closure': closure(), 'reason': 'worker_exit',
            'numeric_version': 43, 'provider_path': retrieve.TERMINAL_PATH,
            'manifest_sha256': retrieve.MANIFEST_SHA256,
            'native_config_sha256': observer.CONFIG_SHA256,
            'observer_sha256': retrieve.OBSERVER_SHA256, 'helper_sha256': self.helper_sha,
            'saved_source_sha256': observer.SOURCE_SHA256, 'clock': copy.deepcopy(observer.CLOCK),
            'download_finalized': True, 'inventory_scope': 'selected_outputs_only',
            'whole_provider_inventory_verified': False, 'collection_aggregate_verified': False,
            'consumer_admitted': False, 'scientific_success_verified': False,
            'old_native_session_closure_verified': False, 'before': snapshot(), 'after': snapshot()}
        self.args = SimpleNamespace(terminal_receipt=str(self.directory / 'retrieval-result.json'),
            terminal_receipt_sha=None, helper_sha=self.helper_sha, config_sha=observer.CONFIG_SHA256,
            accepted_metadata_sha=observer.METADATA_SHA256, manifest_sha=retrieve.MANIFEST_SHA256)
        self.save()

    def write(self, filename, value):
        raw = observer.canonical(value)
        (self.directory / filename).write_bytes(raw)
        return descriptor(raw)

    def save(self, *, relink_payload=True, relink_launch=True, relink_worker=True):
        payload = self.write('payload.bin', self.terminal)
        if relink_payload:
            self.receipt['file'] = copy.deepcopy(payload)
            self.worker['download']['file'] = copy.deepcopy(payload)
        launch = self.write('launch.json', self.launch)
        if relink_launch:
            self.receipt['request_sha256'] = launch['sha256']
            self.worker['request_sha256'] = launch['sha256']
        worker = self.write('worker-result.json', self.worker)
        if relink_worker:
            self.receipt['worker_result_sha256'] = worker['sha256']
        self.args.terminal_receipt_sha = self.write('retrieval-result.json', self.receipt)['sha256']

    def prior(self):
        return retrieve.prior_terminal(observer, self.args, ARCHIVE_CAP, DEADLINE)

    def test_complete_real_file_launch_worker_receipt_chain_passes(self):
        self.assertEqual(self.prior(), {'bytes': 7, 'sha256': hashlib.sha256(b'archive').hexdigest()})

    def test_missing_receipt_or_pair_rejects(self):
        for key in ('terminal_receipt', 'terminal_receipt_sha'):
            original = getattr(self.args, key)
            setattr(self.args, key, None)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.prior()
            setattr(self.args, key, original)

    def test_receipt_pin_and_each_chain_file_hash_are_required(self):
        for filename in ('payload.bin', 'launch.json', 'worker-result.json', 'retrieval-result.json'):
            path = self.directory / filename
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                self.prior()
            path.write_bytes(original)

    def test_missing_launch_or_worker_file_rejects(self):
        for filename in ('launch.json', 'worker-result.json'):
            path = self.directory / filename
            original = path.read_bytes()
            path.unlink()
            with self.subTest(filename=filename), self.assertRaises((ValueError, OSError)):
                self.prior()
            path.write_bytes(original)

    def test_rehashed_launch_wrong_nonce_version_path_or_helper_rejects(self):
        changes = [('nonce', 'b' * 64), ('numeric_version', 44), ('numeric_version', 43.0),
                   ('provider_path', retrieve.EVIDENCE_PATH), ('helper_sha256', '0' * 64),
                   ('observer_sha256', '0' * 64), ('native_config_sha256', '0' * 64),
                   ('accepted_metadata_sha256', '0' * 64), ('manifest_sha256', '0' * 64),
                   ('cap', True), ('cap', float(TERMINAL_CAP)), ('max_seconds', True), ('format', 'wrong')]
        original = copy.deepcopy(self.launch)
        for key, bad in changes:
            self.launch = copy.deepcopy(original)
            self.launch[key] = bad
            self.save()
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                self.prior()
        self.launch = original

    def test_rehashed_worker_wrong_nonce_request_or_success_type_rejects(self):
        changes = [('nonce', 'b' * 64), ('request_sha256', '0' * 64),
                   ('ok', False), ('ok', 1), ('format', 'wrong')]
        original = copy.deepcopy(self.worker)
        for key, bad in changes:
            self.worker = copy.deepcopy(original)
            self.worker[key] = bad
            self.save(relink_launch=False)
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                self.prior()
        self.worker = original

    def test_receipt_identity_hash_nonce_version_and_boolean_traps_reject(self):
        changes = [('nonce', 'b' * 64), ('request_sha256', '0' * 64),
                   ('worker_result_sha256', '0' * 64), ('numeric_version', 44),
                   ('numeric_version', 43.0), ('ok', 1), ('download_finalized', 1),
                   ('provider_path', retrieve.EVIDENCE_PATH), ('helper_sha256', '0' * 64),
                   ('manifest_sha256', '0' * 64), ('saved_source_sha256', '0' * 64)]
        original = copy.deepcopy(self.receipt)
        for key, bad in changes:
            self.receipt = copy.deepcopy(original)
            self.receipt[key] = bad
            self.args.terminal_receipt_sha = self.write('retrieval-result.json', self.receipt)['sha256']
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                self.prior()
        self.receipt = original

    def test_new_job_closure_must_be_complete_and_exact_typed(self):
        changes = [('active_processes', 1), ('active_processes', False),
                   ('kill_on_close', False), ('kill_on_close', 1),
                   ('breakaway_permitted', True), ('breakaway_permitted', 0),
                   ('atomic_job_assignment', False), ('atomic_job_assignment', 1)]
        for key, bad in changes:
            self.receipt['closure'] = closure()
            self.receipt['closure'][key] = bad
            self.save()
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                self.prior()
        self.receipt['closure'] = None
        self.save()
        with self.assertRaises(ValueError):
            self.prior()

    def test_both_observations_must_be_terminal_and_same_status(self):
        original_receipt, original_worker = copy.deepcopy(self.receipt), copy.deepcopy(self.worker)
        for side in ('before', 'after'):
            for target in ('receipt', 'worker', 'both'):
                self.receipt, self.worker = copy.deepcopy(original_receipt), copy.deepcopy(original_worker)
                if target in ('receipt', 'both'):
                    self.receipt[side] = snapshot('RUNNING')
                if target in ('worker', 'both'):
                    self.worker['download'][side] = snapshot('RUNNING')
                self.save()
                with self.subTest(side=side, target=target), self.assertRaises(ValueError):
                    self.prior()
        self.receipt, self.worker = copy.deepcopy(original_receipt), copy.deepcopy(original_worker)
        self.receipt['after'] = snapshot('COMPLETE')
        self.worker['download']['after'] = snapshot('COMPLETE')
        self.save()
        with self.assertRaises(ValueError):
            self.prior()

    def test_observation_source_metadata_clock_and_types_are_bound(self):
        changes = [('terminal', 1), ('numeric_version', 43.0), ('saved_source_sha256', '0' * 64),
                   ('metadata_sha256', '0' * 64), ('source_and_metadata_bracket_verified', 1),
                   ('clock', {**observer.CLOCK, 'original_epoch': NOW})]
        original_receipt, original_worker = copy.deepcopy(self.receipt), copy.deepcopy(self.worker)
        for key, bad in changes:
            self.receipt, self.worker = copy.deepcopy(original_receipt), copy.deepcopy(original_worker)
            self.receipt['before'][key] = bad
            self.worker['download']['before'][key] = bad
            self.save()
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                self.prior()

    def test_receipt_file_bytes_must_be_integer_and_match_actual_payload(self):
        original = copy.deepcopy(self.receipt['file'])
        for value in (True, float(original['bytes']), original['bytes'] + 1, 0):
            self.receipt['file'] = {**original, 'bytes': value}
            self.worker['download']['file'] = copy.deepcopy(self.receipt['file'])
            self.save(relink_payload=False)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prior()

    def test_launch_and_observation_deadlines_are_bounded(self):
        original = self.launch['deadline_epoch']
        for value in (True, float('inf'), float('nan'), observer.CLOCK['global_deadline'] + 1,
                      observer.CLOCK['original_epoch'], NOW - 1, NOW + 301):
            self.launch['deadline_epoch'] = value
            if isinstance(value, float) and (value != value or value == float('inf')):
                raw = (json.dumps(self.launch, allow_nan=True) + '\n').encode()
                (self.directory / 'launch.json').write_bytes(raw)
                self.receipt['request_sha256'] = descriptor(raw)['sha256']
                self.worker['request_sha256'] = descriptor(raw)['sha256']
                self.receipt['worker_result_sha256'] = self.write('worker-result.json', self.worker)['sha256']
                self.args.terminal_receipt_sha = self.write('retrieval-result.json', self.receipt)['sha256']
            else:
                self.save()
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prior()
        self.launch['deadline_epoch'] = original

    def test_observation_order_and_finite_nonboolean_timestamps_required(self):
        original_receipt, original_worker = copy.deepcopy(self.receipt), copy.deepcopy(self.worker)
        changes = [('started_epoch', True), ('observed_epoch', NOW - 1),
                   ('started_epoch', observer.CLOCK['original_epoch'] - 1),
                   ('observed_epoch', observer.CLOCK['global_deadline'])]
        for key, value in changes:
            self.receipt, self.worker = copy.deepcopy(original_receipt), copy.deepcopy(original_worker)
            self.receipt['before'][key] = value
            self.worker['download']['before'][key] = value
            self.save()
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.prior()
        self.receipt, self.worker = copy.deepcopy(original_receipt), copy.deepcopy(original_worker)
        for side in (self.receipt['before'], self.worker['download']['before']):
            side['observed_epoch'] = NOW + 1
        self.save()
        with self.assertRaisesRegex(ValueError, 'terminal_bracket_changed'):
            self.prior()

    def test_terminal_archive_descriptor_and_boolean_traps_reject(self):
        original = copy.deepcopy(self.terminal)
        changes = [('path', '/kaggle/working/other.zip'), ('bytes', True), ('bytes', 0),
                   ('bytes', -1), ('bytes', ARCHIVE_CAP + 1), ('bytes', 7.0),
                   ('sha256', 'A' * 64), ('sha256', '0' * 63), ('sha256', None)]
        for key, bad in changes:
            self.terminal = copy.deepcopy(original)
            self.terminal['archive'][key] = bad
            self.save()
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                self.prior()
        for key, bad in (('archive_complete', False), ('archive_complete', 1),
                         ('format', 'wrong'), ('mode', 'other'), ('status', 'running'),
                         ('output_root', '/kaggle/working/other')):
            self.terminal = copy.deepcopy(original)
            self.terminal[key] = bad
            self.save()
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                self.prior()


class ArgumentsAndImportTests(unittest.TestCase):
    def test_supervisor_arguments_parse_with_no_side_effect(self):
        args = retrieve.arguments(argv())
        self.assertEqual(args.name, retrieve.TERMINAL_PATH)
        self.assertFalse(args.worker)

    def test_duplicate_flags_including_equals_form_are_rejected(self):
        for tail in (['--name', retrieve.TERMINAL_PATH], ['--name=' + retrieve.TERMINAL_PATH],
                     ['--worker', '--worker']):
            with self.subTest(tail=tail), self.assertRaisesRegex(ValueError, 'unambiguous_arguments'):
                retrieve.arguments(argv() + tail)

    def test_archive_requires_paired_prior_receipt_only_archive_accepts_it(self):
        with self.assertRaises(ValueError):
            retrieve.arguments(argv(retrieve.EVIDENCE_PATH))
        pair = ['--terminal-receipt', '/cpu/prior/retrieval-result.json', '--terminal-receipt-sha', 'd' * 64]
        self.assertEqual(retrieve.arguments(argv(retrieve.EVIDENCE_PATH) + pair).terminal_receipt_sha, 'd' * 64)
        for tail in (pair, pair[:2], pair[2:]):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                retrieve.arguments(argv() + tail)

    def test_worker_requires_exact_nonce_hash_and_finite_deadline(self):
        good = ['--worker', '--nonce', 'e' * 64, '--request-sha', 'f' * 64,
                '--deadline-epoch', str(NOW + 100)]
        self.assertTrue(retrieve.arguments(argv() + good).worker)
        for index, bad in ((2, 'bad'), (4, 'F' * 64), (6, 'nan'), (6, 'inf'), (6, '-inf')):
            changed = list(good)
            changed[index] = bad
            with self.subTest(index=index, bad=bad), redirect_stderr(io.StringIO()), self.assertRaises((ValueError, SystemExit)):
                retrieve.arguments(argv() + changed)
        with self.assertRaises(ValueError):
            retrieve.arguments(argv() + good[1:])

    def test_invalid_cli_main_is_sanitized_and_never_bootstraps(self):
        stdout = io.StringIO()
        with patch.object(retrieve, 'bootstrap') as bootstrap, redirect_stdout(stdout):
            code = retrieve.main(argv() + ['--name', 'duplicate'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue()), {'ok': False, 'reason': 'retrieval_bootstrap_failed'})
        bootstrap.assert_not_called()

    def test_import_is_inert_without_provider_process_files_or_output(self):
        raw = SOURCE.read_bytes()
        module = ModuleType('cpu_import_only_selected_retrieval')
        module.__file__ = str(SOURCE)
        stdout = io.StringIO()
        with patch.object(socket, 'socket', side_effect=AssertionError('socket on import')), \
                patch.object(socket, 'create_connection', side_effect=AssertionError('network on import')), \
                patch.object(subprocess, 'Popen', side_effect=AssertionError('process on import')), \
                patch.object(Path, 'open', side_effect=AssertionError('file on import')), \
                patch.object(os, '_exit', side_effect=AssertionError('exit on import')), redirect_stdout(stdout):
            exec(compile(raw, str(SOURCE), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
        self.assertEqual(stdout.getvalue(), '')
        self.assertTrue(callable(module.main))
        self.assertNotIn('provider', vars(module))


if __name__ == '__main__':
    unittest.main()

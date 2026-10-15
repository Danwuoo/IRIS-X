"""Bounded offline integration of the WSL owner and real binary worker protocol.

These are synthetic Linux pipe tests, never Windows/OAuth/provider acceptance.
Production Provider, BridgeClient, WorkerProvider, run_worker, DTO validation,
journals and file publication run unchanged. Only the external SDK/auth/native
process boundary is fake. Payloads are at most 64 KiB; no SDK is imported and
no network, credentials, provider, subprocess, or Windows runtime is accessed.
"""
import ast
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import stat
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[2]
PORTABLE = ROOT.with_name('publication_portable_20261015')
VERSIONS = {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39,
            'inactive': 40, 'active': 41}
CONTENT = bytes(range(256)) * 256
STAGING_TOKEN = 'SYNTHETIC-NATIVE-ONLY-STAGING-TOKEN'
SIGNED_URL = 'https://storage.googleapis.com/synthetic/upload?signature=SYNTHETIC-PRIVATE-SIGNATURE'
PROVIDER_TEXT = 'Bearer SYNTHETIC-PRIVATE-CREDENTIAL ' + SIGNED_URL
OPERATOR_SOURCES = frozenset(('config.py', 'operator_common.py', 'bridge_client.py',
    'rl_transport.py', 'rl_collect.py', 'launch.py', 'verify_active_wire.py',
    'native_config.py', 'native_auth.py', 'sdk_worker.py', 'sdk-lock.json',
    'protocol.py', 'win_runtime.py', 'win_supervisor.py', 'native_probe.py'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_source(name, path):
    """Compile current source, never stale .pyc; production dependency pins stay on."""
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    try:
        exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                     optimize=sys.flags.optimize), vars(module))
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


worker = load_source('owner_integration_worker', ROOT / 'sdk_worker.py')


def synthetic_binding():
    value = {}
    for key, name in [('executable', 'python.exe'), ('supervisor', 'win_supervisor.py'),
                      ('configuration', 'configuration.json')]:
        value[key] = {'native_path': 'C:\\Synthetic\\' + name,
                      'wsl_path': '/mnt/c/Synthetic/' + name, 'sha256': 'a' * 64}
    value['native_acceptance'] = {'path': '/synthetic-only/never-opened.json', 'sha256': 'b' * 64}
    return value


def request_modules():
    """Official-shaped request fields, with slots rejecting invented field names."""
    fields = {
        'kagglesdk.datasets.types.dataset_api_service': {
            'ApiGetDatasetRequest': ('owner_slug', 'dataset_slug'),
            'ApiListDatasetFilesRequest': ('owner_slug', 'dataset_slug', 'dataset_version_number',
                                           'page_size', 'page_token'),
            'ApiDownloadDatasetRequest': ('owner_slug', 'dataset_slug', 'dataset_version_number',
                                         'file_name', 'raw'),
            'ApiCreateDatasetVersionByIdRequest': ('id', 'body'),
            'ApiCreateDatasetVersionRequestBody': ('files', 'delete_old_versions', 'version_notes'),
            'ApiDatasetNewFile': ('token',),
        },
        'kagglesdk.kernels.types.kernels_api_service': {
            'ApiGetKernelRequest': ('user_name', 'kernel_slug'),
            'ApiGetKernelSessionStatusRequest': ('user_name', 'kernel_slug'),
            'ApiDownloadKernelOutputRequest': ('owner_slug', 'kernel_slug', 'version_number', 'file_path'),
        },
        'kagglesdk.blobs.types.blob_api_service': {
            'ApiStartBlobUploadRequest': ('type', 'name', 'content_type', 'content_length'),
        },
    }
    result = {}
    for module_name, definitions in fields.items():
        module = ModuleType(module_name)
        for name, slots in definitions.items():
            setattr(module, name, type(name, (), {'__slots__': slots}))
        if '.blobs.' in module_name:
            module.ApiBlobType = SimpleNamespace(DATASET=1)
        result[module_name] = module
    return result


class NoExternalImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('kaggle', 'kagglesdk', 'requests'):
            raise AssertionError('offline_real_sdk_or_http_import_forbidden')
        return None


class Response:
    def __init__(self, content=CONTENT, *, status=200):
        self.payload, self.status_code = content, status
        self.headers = {'Content-Length': str(len(content)), 'Content-Type': 'application/octet-stream'}
        self.content, self.closed, self.body_reads = b'', False, 0

    def raise_for_status(self):
        if self.status_code >= 400:
            error = RuntimeError(PROVIDER_TEXT)
            error.response = self
            raise error

    def iter_content(self, chunk_size):
        self.body_reads += 1
        for start in range(0, len(self.payload), min(chunk_size, 8192)):
            yield self.payload[start:start + min(chunk_size, 8192)]

    def close(self):
        self.closed = True


class BoundedPipe:
    """A hard three-second I/O bound prevents broken fake workers hanging tests."""
    def __init__(self, stream, *, capture=False):
        self.stream, self.data = stream, bytearray() if capture else None

    def read(self, count):
        if not select.select([self.stream], [], [], 3)[0]:
            raise TimeoutError('synthetic_pipe_read_bound')
        return self.stream.read(count)

    def write(self, raw):
        if not select.select([], [self.stream], [], 3)[1]:
            raise TimeoutError('synthetic_pipe_write_bound')
        count = self.stream.write(raw[:4096])
        if self.data is not None:
            if len(self.data) + count > 1024 * 1024:
                raise ValueError('synthetic_wire_capture_cap')
            self.data.extend(raw[:count])
        return count

    def flush(self):
        self.stream.flush()

    def close(self):
        self.stream.close()


class PipeWorker:
    """Real run_worker over OS pipes; only the Job-zero receipt is synthetic."""
    def __init__(self, harness, protocol, nonce, deadline, argv):
        self.harness, self.protocol, self.nonce, self.argv = harness, protocol, nonce, argv
        read_worker, write_client = os.pipe()
        read_client, write_worker = os.pipe()
        self.handles = [os.fdopen(fd, mode, buffering=0) for fd, mode in
                        ((read_worker, 'rb'), (write_client, 'wb'),
                         (read_client, 'rb'), (write_worker, 'wb'))]
        self.reader = BoundedPipe(self.handles[2])
        self.writer = BoundedPipe(self.handles[1], capture=True)
        self.native_writer = BoundedPipe(self.handles[3], capture=True)
        channel = protocol.FramedIO(BoundedPipe(self.handles[0]), self.native_writer, nonce=nonce)
        self.result, self.errors, self.released = [], [], False
        lease = float(argv[argv.index('--deadline-epoch') + 1])
        seconds = float(argv[argv.index('--max-seconds') + 1])
        runtime = SimpleNamespace(config_sha256=harness.binding['configuration']['sha256'])
        self.sdk = FakeSDK(harness, self)
        sdk = self.sdk

        class FakeAuth:
            def __init__(inner, unused_runtime, exchange, unused_boundary):
                inner.exchange, inner.uncertain = exchange, False

            def prepare(inner):
                return {'sdk_lock_sha256': sha((ROOT / 'sdk-lock.json').read_bytes()),
                        'sdk_source_count': 170, 'account': 'danielwuu', 'existing_official_store': True}

            def protocol_ready(inner):
                inner.exchange.check_ready()

            def open(inner):
                harness.auth_opens += 1

            def renew_if_due(inner):
                return sdk.client

            def close(inner):
                harness.auth_closes += 1

        def serve():
            try:
                self.result.append(worker.run_worker(runtime, VERSIONS, channel, protocol,
                    SimpleNamespace(OfficialSession=FakeAuth), deadline_epoch=lease, max_seconds=seconds))
            except BaseException as error:
                self.errors.append(type(error).__name__)
            finally:
                self.handles[0].close()
                self.handles[3].close()

        self.thread = threading.Thread(target=serve, name='offline-owner-pipe-worker', daemon=True)
        self.thread.start()

    def finish(self, timeout):
        self.thread.join(min(timeout, 3))
        if self.thread.is_alive() or self.errors or not self.result:
            raise ValueError('synthetic_worker_not_closed')
        code = self.result[0]
        receipt = {'format': 'irisx/windows-supervisor-result-v1',
                   'nonce': '0' * 64 if self.harness.bad_closure else self.nonce,
                   'ok': code == 0, 'reason': 'worker_exit',
                   'closure': {'format': 'irisx/windows-job-closure-v1', 'active_processes': 0,
                               'kill_on_close': True, 'breakaway_permitted': False,
                               'atomic_job_assignment': True}}
        return code, self.protocol.canonical(receipt) + b'\n'

    def release(self):
        self.released = True
        self.writer.close()
        self.reader.close()
        self.thread.join(3)
        if self.thread.is_alive():
            raise ValueError('synthetic_worker_survived_cleanup')


class FakeSDK:
    """Input DTOs are SDK-style attributes; production creates every IPC DTO."""
    def __init__(self, harness, process):
        self.h, self.process = harness, process
        self.client = SimpleNamespace(
            datasets=SimpleNamespace(dataset_api_client=SimpleNamespace(
                get_dataset=self.dataset, list_dataset_files=self.list_files,
                download_dataset=self.dataset_download, create_dataset_version_by_id=self.version)),
            kernels=SimpleNamespace(kernels_api_client=SimpleNamespace(
                get_kernel=self.kernel, get_kernel_session_status=self.status,
                download_kernel_output=self.output)),
            blobs=SimpleNamespace(blob_api_client=SimpleNamespace(start_blob_upload=self.start_upload)))

    def record(self, name, request):
        self.h.calls.append((name, request))

    def dataset(self, request):
        self.record('dataset', request)
        return SimpleNamespace(id=12504696, ref=worker.DREF, is_private=True,
            current_version_number=True if self.h.malformed_dataset else self.h.version,
            title='IRIS-X Learning Agent Code 20261011', license_name='Other (specified in description)',
            owner_ref='danielwuu', versions=[SimpleNamespace(version_number=n)
                                           for n in range(self.h.version, self.h.version - 10, -1)],
            private_unused_field=PROVIDER_TEXT)

    def kernel(self, request):
        self.record('kernel', request)
        meta = SimpleNamespace(id=138123872, ref=worker.REF, is_private=True, current_version_number=39,
            title='Synthetic owner integration', language='python', kernel_type='notebook',
            kernel_data_sources=[], enable_gpu=False, enable_tpu=False, enable_internet=False,
            model_data_sources=[self.h.common.MODEL], dataset_data_sources=[worker.DREF,
                *['/'.join(pin.split('/')[:2]) for pin in self.h.transport.NON_CODE_PINS]],
            competition_data_sources=['arc-agi-3'], docker_image=self.h.transport.DOCKER,
            machine_shape='None')
        return SimpleNamespace(metadata=meta, blob=SimpleNamespace(source=self.h.source))

    def status(self, request):
        self.record('status', request)
        if self.h.status_failures:
            failure = self.h.status_failures.pop(0)
            if failure == '503':
                response = Response(status=503)
                response.headers['Retry-After'] = '41'
                response.raise_for_status()
            raise TimeoutError(PROVIDER_TEXT)
        return SimpleNamespace(status=SimpleNamespace(name='ERROR'), failure_message='')

    def list_files(self, request):
        self.record('list_files', request)
        token = getattr(request, 'page_token', '')
        rows = [SimpleNamespace(name='source/a.py', total_bytes=17)] if not token else [
            SimpleNamespace(name='source/b.py', total_bytes=31)]
        if token not in ('', 'page-2'):
            raise ValueError('synthetic_page_token')
        return SimpleNamespace(error_message='', dataset_files=rows,
                               next_page_token='page-2' if not token else '')

    def response(self):
        response = Response()
        self.h.responses.append(response)
        return response

    def output(self, request):
        self.record('output', request)
        response = self.response()
        if self.h.output_failures:
            response.status_code = self.h.output_failures.pop(0)
        return response

    def dataset_download(self, request):
        self.record('dataset_download', request)
        return self.response()

    def start_upload(self, request):
        self.record('start_upload', request)
        self.h.check_stage('init_intent')
        return SimpleNamespace(token=STAGING_TOKEN, create_url=SIGNED_URL)

    def version(self, request):
        self.record('version', request)
        self.h.check_stage('version_intent')
        if request.id != 12504696 or request.body.delete_old_versions is not False:
            raise ValueError('synthetic_version_identity_or_retention')
        if len(request.body.files) != 1 or request.body.files[0].token != STAGING_TOKEN:
            raise ValueError('synthetic_opaque_handle_not_resolved')
        self.h.version += 1
        return SimpleNamespace(ref=worker.DREF, error='')


class Harness:
    def __init__(self, testcase, *, status_failures=(), output_failures=(), bad_closure=False, fail_put=False,
                 malformed_dataset=False):
        self.testcase, self.stack = testcase, ExitStack()
        testcase.addCleanup(self.stack.close)
        scratch = REPOSITORY / '.irisx'
        scratch.mkdir(exist_ok=True)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='owner-integration-', dir=scratch)))
        self.collector = load_source('owner_integration_collect_' + self.root.name, ROOT / 'rl_collect.py')
        self.transport, self.common = self.collector.transport, self.collector._common
        self.binding = synthetic_binding()
        self.version, self.offset = VERSIONS['code_predecessor'], 0
        self.calls, self.responses, self.processes, self.puts = [], [], [], []
        self.status_failures, self.bad_closure = list(status_failures), bad_closure
        self.output_failures = list(output_failures)
        self.fail_put, self.malformed_dataset = fail_put, malformed_dataset
        self.auth_opens = self.auth_closes = 0
        self.require_mutation_journal = False
        self.source = json.dumps({'cells': [{'cell_type': 'code', 'source': ['PASSIVE = True\n']}],
                                  'nbformat': 4, 'nbformat_minor': 5, 'metadata': {}})
        self.config = SimpleNamespace(versions=VERSIONS, document_sha256='c' * 64,
            publication_manifest_sha256='d' * 64, windows_bridge=self.binding,
            repository_root=REPOSITORY, candidate_root=self.root, scratch_root=self.root,
            state_root=self.root / 'state-run008', evidence_root=self.root / 'evidence-run008',
            gpu_stop_path=self.root / 'gpu-stop.json')
        self.config.state_root.mkdir()
        for module in (self.common, self.transport, self.collector):
            module.CONFIG = self.config
            module.BASE, module.WORK, module.STATE, module.STOP = (REPOSITORY, self.root,
                self.config.state_root, self.config.gpu_stop_path)
        t = self.transport
        t.CODE_PREDECESSOR, t.CODE_VERSION = 20, 21
        t.NOTEBOOK_PREDECESSOR, t.INACTIVE_VERSION, t.ACTIVE_VERSION = 39, 40, 41
        t.PINS = [worker.DREF + '/21', *t.NON_CODE_PINS]
        t.OLD_SOURCE = sha(self.source.encode())
        t.REMOTE_PREDECESSOR = {'provider_status': 'ERROR'}
        self.stack.enter_context(patch.dict(sys.modules, request_modules()))
        self.stack.enter_context(patch.object(sys, 'meta_path', [NoExternalImports(), *sys.meta_path]))
        self.stack.enter_context(patch.object(socket, 'socket', side_effect=AssertionError('offline_socket_forbidden')))
        self.stack.enter_context(patch.object(socket, 'create_connection', side_effect=AssertionError('offline_network_forbidden')))
        self.stack.enter_context(patch.object(self.common, 'credential_guard', return_value={'synthetic_test_only': True}))
        original_load = self.common.load_source_module

        def source_loader(name, path, expected_sha, cap=16 * 1024**2):
            module = original_load(name, path, expected_sha, cap)
            if Path(path).name == 'bridge_client.py':
                actual = module.BridgeClient
                self.client_module = module
                module.BridgeClient = lambda c, binding: actual.for_testing(c, binding, self.factory,
                    clock=lambda: time.monotonic() + self.offset)
            return module

        self.stack.enter_context(patch.object(self.common, 'load_source_module', side_effect=source_loader))
        # The 4-GiB production reserve is not loosened; only the disposable
        # filesystem's reported free-space capability is synthetic here.
        self.stack.enter_context(patch.object(self.common.shutil, 'disk_usage',
            return_value=SimpleNamespace(free=self.common.RESERVE + 1024**2)))
        actual_storage = worker.StorageHttp
        harness = self

        class NativeStorage(actual_storage):
            def put(inner, url, source, size):
                harness.check_stage('put_intent')
                raw = source.read(len(CONTENT) + 1)
                if url != SIGNED_URL or len(raw) != size or size > len(CONTENT):
                    raise ValueError('synthetic_put_binding')
                harness.puts.append((url, raw, size))
                if harness.fail_put:
                    raise TimeoutError(PROVIDER_TEXT)
                return 200

        self.stack.enter_context(patch.object(worker, 'StorageHttp', NativeStorage))
        self.provider = self.common.Provider()
        testcase.addCleanup(self.cleanup)

    def check_stage(self, stage):
        if self.require_mutation_journal:
            actual = self.common.obj(self.config.state_root / 'dataset-code-v21-journal.json')
            if actual['stage'] != stage:
                raise ValueError('synthetic_external_mutation_precedes_journal')

    def factory(self, protocol, nonce, deadline, argv):
        process = PipeWorker(self, protocol, nonce, deadline, argv)
        self.processes.append(process)
        return process

    def cleanup(self):
        if not self.provider.bridge.closed and not self.provider.bridge.unknown:
            self.provider.close()
        for process in self.processes:
            process.release()
            self.testcase.assertFalse(process.thread.is_alive())
            self.testcase.assertEqual(process.errors, [])

    def assert_no_secrets(self):
        parts = [bytes(p.writer.data) + bytes(p.native_writer.data) for p in self.processes]
        parts.extend(p.read_bytes() for p in self.config.state_root.rglob('*.json'))
        for raw in parts:
            for forbidden in (STAGING_TOKEN, SIGNED_URL, 'SYNTHETIC-PRIVATE-SIGNATURE',
                              'SYNTHETIC-PRIVATE-CREDENTIAL', 'Bearer ', 'https://'):
                self.testcase.assertNotIn(forbidden.encode(), raw)
        for path in self.config.state_root.glob('native-bridge-*.claim.json'):
            self.testcase.assertIs(self.common.obj(path)['synthetic_test_only'], True)

    def operations(self, process):
        observer = process.protocol.FrameObserver(process.nonce, direction='request')
        controls = observer.feed(bytes(process.writer.data))
        observer.finish()
        return [frame['payload']['operation'] for frame in controls if frame['kind'] == 'request']

    def inactive_row(self):
        return {'role': 'inactive', 'expected_predecessor_version': 39,
                'predecessor_source_sha256': sha(self.source.encode()),
                'title': 'Synthetic owner integration', 'language': 'python',
                'kernel_type': 'notebook', 'enable_gpu': False, 'competition_sources': ['arc-agi-3']}


class OwnerIntegrationTests(unittest.TestCase):
    def test_actual_sdk_to_wire_to_dto_and_frozen_metadata_consumers(self):
        h = Harness(self)
        dataset = h.provider.dataset()
        self.assertEqual(dataset.current_version_number, 20)
        self.assertIs(dataset.is_private, True)
        self.assertEqual(dataset.versions[0].version_number, 20)
        self.assertEqual(dataset.to_dict()['licenseName'], 'Other (specified in description)')
        copy = dataset.to_dict()
        copy['versions'][0]['versionNumber'] = 999
        self.assertEqual(dataset.versions[0].version_number, 20)
        with self.assertRaises(AttributeError):
            dataset.current_version_number = 99
        history = h.transport.dataset_check(h.provider, 20, metadata_only=True)
        self.assertEqual(history['versions'], list(range(20, 10, -1)))
        snapshot, raw, metadata = h.transport.bracket(h.provider, 39, sha(h.source.encode()), h.inactive_row())
        self.assertEqual(snapshot['status'], 'ERROR')
        self.assertEqual(raw, h.source.encode())
        h.transport.saved_settings(metadata.to_dict(), h.inactive_row(), 39)
        self.assertEqual(h.provider.list_files(dataset=True, version=7), {'source/a.py': 17, 'source/b.py': 31})
        requests = [request for name, request in h.calls if name == 'list_files']
        self.assertEqual([getattr(request, 'page_token', '') for request in requests], ['', 'page-2'])
        self.assertTrue(all(request.dataset_version_number == 7 and request.page_size == 200 for request in requests))
        h.provider.close()
        self.assertEqual(h.processes[0].result, [0])
        h.assert_no_secrets()

    def test_inert_descriptors_binary_hash_fsync_and_atomic_publish(self):
        h = Harness(self)
        request = h.provider.output('run/result.zip', version=39)
        self.assertFalse(any(name == 'output' for name, unused in h.calls))
        self.assertFalse(hasattr(request, 'url'))
        destination = h.root / 'downloads' / 'result.zip'
        events, original_fsync, original_rename = [], os.fsync, Path.rename

        def fsync(fd):
            events.append('dir-fsync' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file-fsync')
            return original_fsync(fd)

        def rename(path, target):
            if path == destination.with_name(destination.name + '.partial'):
                self.assertFalse(destination.exists())
                self.assertEqual(path.read_bytes(), CONTENT)
                events.append('publish')
            return original_rename(path, target)

        with patch.object(os, 'fsync', side_effect=fsync), patch.object(Path, 'rename', rename):
            result = h.common.binary_get(request, destination, len(CONTENT), sha(CONTENT), len(CONTENT))
        self.assertEqual(result, {'path': str(destination), 'bytes': len(CONTENT), 'sha256': sha(CONTENT)})
        published = events.index('publish')
        self.assertEqual(events[published - 1], 'file-fsync')
        self.assertEqual(events[published + 1], 'dir-fsync')
        self.assertFalse(destination.with_name(destination.name + '.partial').exists())
        self.assertTrue(request.used)
        with self.assertRaises(h.common.GuardError):
            h.common.binary_get(request, h.root / 'reused.zip', len(CONTENT))
        whole = h.provider.dataset_download(version=20)
        h.common.binary_get(whole, h.root / 'dataset.zip', len(CONTENT), sha(CONTENT), len(CONTENT))
        selected = h.provider.dataset_download('source/a.py', version=21)
        h.common.binary_get(selected, h.root / 'selected.bin', len(CONTENT), sha(CONTENT), len(CONTENT))
        downloads = [r for name, r in h.calls if name == 'dataset_download']
        self.assertFalse(hasattr(downloads[0], 'file_name'))
        self.assertEqual((downloads[1].file_name, downloads[1].raw), ('source/a.py', True))
        self.assertTrue(all(response.closed and response.body_reads == 1 for response in h.responses))
        h.assert_no_secrets()

    def test_binary_hash_failure_never_publishes_or_rotates(self):
        h = Harness(self)
        destination = h.root / 'bad.zip'
        with self.assertRaises(h.provider.bridge.protocol.ProtocolError):
            h.common.binary_get(h.provider.output('run/result.zip', version=39), destination,
                                len(CONTENT), '0' * 64, len(CONTENT))
        self.assertFalse(destination.exists())
        self.assertTrue(h.provider.bridge.unknown)
        with self.assertRaises(h.common.GuardError):
            h.provider.ensure_read_auth()
        self.assertEqual(len(h.processes), 1)
        h.assert_no_secrets()

    def test_metadata_does_not_consume_body_or_claim_archive_verification(self):
        h = Harness(self)
        request = h.provider.output('run/checkpoint.zip', version=41)
        self.assertEqual(h.responses, [])
        result = h.common.binary_metadata(request, len(CONTENT), len(CONTENT))
        self.assertEqual(result['bytes'], len(CONTENT))
        self.assertIs(result['archive_bytes_verified'], False)
        self.assertEqual(result['body_consumed_bytes'], 0)
        self.assertTrue(h.responses[0].closed)
        self.assertEqual(h.responses[0].body_reads, 0)
        self.assertFalse(any(p.suffix == '.partial' for p in h.root.rglob('*')))
        with self.assertRaises(h.common.GuardError):
            h.common.binary_metadata(request, len(CONTENT), len(CONTENT))
        h.assert_no_secrets()

    def test_update_code_opaque_begin_put_version_and_real_durable_journal(self):
        h = Harness(self)
        payload = h.root / 'source.zip'
        payload.write_bytes(CONTENT)
        manifest = {'datasets': [{'transport_archive': {'path': payload.name,
            'bytes': len(CONTENT), 'sha256': sha(CONTENT)}, 'version_notes': 'Offline synthetic integration'}],
            'notebooks': [h.inactive_row()]}
        args = SimpleNamespace(manifest=str(h.root / 'manifest.json'), manifest_sha='d' * 64)
        h.require_mutation_journal = True
        check = h.transport.dataset_check
        modes, synced_stages = [], []
        original_fsync = os.fsync

        def observed_fsync(fd):
            original_fsync(fd)
            if stat.S_ISREG(os.fstat(fd).st_mode):
                path = Path(os.readlink('/proc/self/fd/' + str(fd)))
                if path.name.startswith('dataset-code-v21-journal.json.'):
                    synced_stages.append(json.loads(path.read_bytes())['stage'])

        def synthetic_history(provider, version, **kwargs):
            # Published v1-v7 file hashes cannot be manufactured in a 64-KiB
            # test. Keep the actual metadata checker; do not claim historical
            # retention acceptance or admission from this isolated lifecycle.
            modes.append(kwargs)
            return check(provider, version, metadata_only=True)

        with patch.object(h.transport, 'dataset_check', side_effect=synthetic_history), \
                patch.object(os, 'fsync', side_effect=observed_fsync):
            result = h.transport.update_code(h.provider, manifest, args)
        self.assertEqual(result, {'status': 'VERSION_ACCEPTED_READBACK_REQUIRED', 'version': 21})
        self.assertEqual(modes, [{'capture_prewrite': True}, {}])
        self.assertEqual([name for name, unused in h.calls if name in ('start_upload', 'version')],
                         ['start_upload', 'version'])
        self.assertEqual(h.puts, [(SIGNED_URL, CONTENT, len(CONTENT))])
        journal = h.common.obj(h.config.state_root / 'dataset-code-v21-journal.json')
        self.assertEqual([journal[name] for name in ('init_calls', 'put_calls', 'version_calls')], [1, 1, 1])
        self.assertEqual(journal['stage'], 'version_accepted')
        self.assertEqual(journal['claim_sha256'], h.common.file_sha(h.config.state_root / 'dataset-code-v21.claim.json'))
        self.assertEqual(journal['response'], {'ref': worker.DREF, 'error': ''})
        self.assertEqual(synced_stages, ['claimed', 'init_intent', 'init_accepted_ram_only',
                                        'put_intent', 'put_accepted', 'version_intent', 'version_accepted'])
        self.assertEqual([operation for operation in h.operations(h.processes[0])
                          if operation in ('start_upload', 'upload_once', 'version')],
                         ['start_upload', 'upload_once', 'version'])
        self.assertEqual(h.provider.dataset().current_version_number, 21)
        self.assertFalse(h.provider.bridge.can_rotate_read_only())
        with self.assertRaises(ValueError):
            h.provider.start_upload(payload)
        self.assertEqual(sum(name == 'start_upload' for name, unused in h.calls), 1)
        h.provider.close()
        h.assert_no_secrets()

    def test_frozen_checkpoint_consumer_preserves_pending_404_then_header_only(self):
        h = Harness(self, output_failures=[404])
        manifest = {'terminal_contract': {'checkpoint_path': 'run/checkpoints.zip',
                    'archive_caps': {'checkpoint_archive_bytes': len(CONTENT)}}}
        terminal = {'checkpoint_archive_observation': {'filename': 'checkpoints.zip', 'present': True,
                    'byte_length': len(CONTENT), 'body_materialized': False,
                    'independently_sha256_verified': False, 'observed_sha256': None}}
        old = h.provider.bridge
        pending = h.collector.checkpoint_observation(h.provider, manifest, terminal)
        self.assertEqual(pending['transport_observation'], 'PENDING_HTTP404')
        self.assertEqual(pending['http_status'], 404)
        self.assertIsNone(pending['present'])
        self.assertTrue(old.closed and old.closure_verified)
        self.assertFalse(old.unknown)
        self.assertEqual(h.operations(h.processes[0]), ['open', 'binary_metadata', 'close'])
        present = h.collector.checkpoint_observation(h.provider, manifest, terminal)
        self.assertEqual(present['transport_observation'], 'HTTP200_CONTENT_LENGTH_VERIFIED')
        self.assertIs(present['independently_sha256_verified'], False)
        self.assertIsNone(present['observed_sha256'])
        self.assertTrue(all(response.closed and response.body_reads == 0 for response in h.responses))
        self.assertEqual(len(h.processes), 2)
        h.assert_no_secrets()

    def test_uncertain_put_is_not_replayed_or_rotated(self):
        h = Harness(self, fail_put=True)
        payload = h.root / 'source.zip'
        payload.write_bytes(CONTENT)
        started = h.provider.start_upload(payload)
        self.assertRegex(started.handle, '^[0-9a-f]{64}$')
        self.assertFalse(hasattr(started, 'token'))
        self.assertFalse(hasattr(started, 'create_url'))
        with self.assertRaises(h.client_module.BridgeProviderError) as caught:
            h.provider.upload_once(started.handle, payload)
        self.assertTrue(caught.exception.bridge_failure['mutation_uncertain'])
        self.assertTrue(h.provider.bridge.unknown)
        with self.assertRaises(ValueError):
            h.provider.upload_once(started.handle, payload)
        with self.assertRaises(h.common.GuardError):
            h.provider.ensure_read_auth()
        self.assertEqual(len(h.puts), 1)
        self.assertEqual(len(h.processes), 1)
        self.assertFalse(any(name == 'version' for name, unused in h.calls))
        h.common.failure(caught.exception, 'upload')
        h.assert_no_secrets()

    def test_known_readonly_503_preserves_backoff_and_clean_rotation(self):
        h = Harness(self, status_failures=['503'])
        original = h.provider.bridge
        with self.assertRaises(h.client_module.BridgeProviderError) as caught:
            h.provider.status()
        failure = h.common.failure(caught.exception, 'poll')
        self.assertEqual((failure['classification'], failure['http_status'], failure['retry_after_seconds']),
                         ('TRANSIENT', 503, 41))
        self.assertEqual(h.collector.retry_delay(failure, 1), 41)
        self.assertEqual(h.collector.retry_delay(failure, 2), 60)
        self.assertTrue(original.closed and original.closure_verified)
        self.assertFalse(original.unknown)
        self.assertEqual(h.processes[0].result, [0])
        self.assertEqual(h.operations(h.processes[0]), ['open', 'status', 'close'])
        self.assertEqual(h.provider.status().status.name, 'ERROR')
        self.assertIsNot(h.provider.bridge, original)
        self.assertEqual(len(h.processes), 2)
        self.assertEqual(h.auth_opens, 2)
        self.assertEqual(h.operations(h.processes[1]), ['open', 'status'])
        self.assertEqual(original.mutations, set())
        h.assert_no_secrets()

    def test_unknown_transport_error_cannot_be_treated_as_readonly_retry(self):
        h = Harness(self, status_failures=['timeout'])
        with self.assertRaises(h.client_module.BridgeProviderError) as caught:
            h.provider.status()
        self.assertTrue(h.provider.bridge.unknown)
        self.assertIsNone(caught.exception.http_status)
        with self.assertRaises(h.common.GuardError):
            h.provider.status()
        self.assertEqual(len(h.processes), 1)
        self.assertEqual(sum(name == 'status' for name, unused in h.calls), 1)
        h.common.failure(caught.exception, 'poll')
        h.assert_no_secrets()

    def test_known_503_without_matching_closure_stays_unknown(self):
        h = Harness(self, status_failures=['503'], bad_closure=True)
        with self.assertRaises(h.client_module.BridgeUnknown):
            h.provider.status()
        self.assertTrue(h.provider.bridge.unknown)
        self.assertFalse(h.provider.bridge.closure_verified)
        with self.assertRaises(h.common.GuardError):
            h.provider.ensure_read_auth()
        self.assertEqual(len(h.processes), 1)
        h.assert_no_secrets()

    def test_early_readonly_rotation_reserves_longest_command_and_close(self):
        h = Harness(self)
        old = h.provider.bridge
        # Remaining lease is below the owner's 1,030-second reserve, but well
        # above zero. The inert descriptor must rotate only when consumed.
        h.offset = 43200 - 1029
        request = h.provider.output('run/result.zip', version=39)
        h.common.binary_get(request, h.root / 'rotated.zip', len(CONTENT), sha(CONTENT), len(CONTENT))
        self.assertTrue(old.closed and old.closure_verified)
        self.assertFalse(old.unknown)
        self.assertIsNot(h.provider.bridge, old)
        self.assertEqual(len(h.processes), 2)
        self.assertEqual(h.operations(h.processes[0]), ['open', 'close'])
        self.assertEqual(h.operations(h.processes[1]), ['open', 'output'])
        self.assertGreater(h.provider.bridge.lease_deadline - h.provider.bridge.clock(), 42000)
        self.assertEqual(h.transport.clock(1791908053)['deadline_epoch'], 1791951253)
        h.assert_no_secrets()

    def test_short_lease_after_mutation_cannot_rotate_or_send_again(self):
        h = Harness(self)
        payload = h.root / 'source.zip'
        payload.write_bytes(CONTENT)
        h.provider.start_upload(payload)
        h.offset = 43200 - 1029
        with self.assertRaises(h.common.GuardError):
            h.provider.ensure_read_auth()
        self.assertEqual(len(h.processes), 1)
        self.assertEqual(h.operations(h.processes[0]), ['open', 'start_upload'])
        self.assertEqual(h.puts, [])
        h.assert_no_secrets()

    def test_wrong_official_dto_type_fails_closed_before_consumer(self):
        h = Harness(self, malformed_dataset=True)
        with self.assertRaises(h.client_module.BridgeProviderError) as caught:
            h.provider.dataset()
        self.assertEqual(caught.exception.bridge_failure['code'], 'VERIFICATION_FAILED')
        self.assertTrue(h.provider.bridge.unknown)
        self.assertEqual(len(h.processes), 1)
        h.assert_no_secrets()


class AdmissionSourceClosureTests(unittest.TestCase):
    """Real admission gates with local synthetic review and read-only Git double."""
    def setUp(self):
        scratch = REPOSITORY / '.irisx'
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='owner-source-closure-', dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.transport = load_source('owner_closure_' + self.directory.name, ROOT / 'rl_transport.py')
        self.transport.CONFIG = SimpleNamespace(document_sha256='c' * 64, repository_root=REPOSITORY)
        self.review = {'status': 'PASS', 'local_config_sha256': 'c' * 64,
                      'publication_manifest_sha256': 'd' * 64, 'material_approval_sha256': 'e' * 64,
                      'candidate_git_commit': 'f' * 40, 'candidate_git_remote_verified': True,
                      'operator_files': {name: sha((ROOT / name).read_bytes()) for name in OPERATOR_SOURCES}}

    def review_args(self, review):
        path = self.directory / 'synthetic-review.json'
        path.write_bytes(self.transport.canonical(review))
        return SimpleNamespace(review=str(path), review_sha=sha(path.read_bytes()),
                               manifest_sha='d' * 64, material_sha='e' * 64)

    def check_review(self, review):
        args = self.review_args(review)
        return self.transport.review_gate(args.review, args.review_sha, args.manifest_sha,
                                         args.material_sha, [ROOT / 'rl_transport.py', ROOT / 'operator_common.py'])

    def test_complete_review_requires_all_15_native_and_wsl_operator_sources(self):
        self.assertEqual(len(self.transport.OPERATOR_SOURCE_NAMES), 15)
        self.assertEqual(set(self.transport.OPERATOR_SOURCE_NAMES), OPERATOR_SOURCES)
        self.assertEqual(self.check_review(self.review), self.review)
        for omitted in sorted(OPERATOR_SOURCES):
            review = {**self.review, 'operator_files': dict(self.review['operator_files'])}
            del review['operator_files'][omitted]
            with self.subTest(omitted=omitted), self.assertRaisesRegex(ValueError, 'complete_bridge_operator_review_required'):
                self.check_review(review)

    def test_stale_bridge_hash_cannot_reuse_otherwise_current_review(self):
        for changed in sorted(OPERATOR_SOURCES):
            review = {**self.review, 'operator_files': {**self.review['operator_files'], changed: '0' * 64}}
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'operator_bytes_not_reviewed'):
                self.check_review(review)

    def test_review_still_binds_pass_manifest_material_and_local_configuration(self):
        for key, value in [('status', 'FAIL'), ('local_config_sha256', '0' * 64),
                           ('publication_manifest_sha256', '0' * 64), ('material_approval_sha256', '0' * 64)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check_review({**self.review, key: value})

    def test_git_publication_requires_exact_bytes_for_every_bridge_source(self):
        args = self.review_args(self.review)
        seen = []
        fault = {'name': None, 'mode': None}

        def git_show(argv, **kwargs):
            self.assertEqual(argv[:4], ['git', '-C', str(REPOSITORY), 'show'])
            commit, relative = argv[4].split(':', 1)
            self.assertEqual(commit, 'f' * 40)
            self.assertEqual(kwargs['timeout'], 30)
            self.assertIs(kwargs['check'], False)
            path = REPOSITORY / relative
            self.assertEqual(path.parent, ROOT)
            seen.append(path.name)
            raw = path.read_bytes()
            if path.name == fault['name']:
                if fault['mode'] == 'missing':
                    return SimpleNamespace(returncode=1, stdout=b'', stderr=b'synthetic missing Git blob')
                raw += b'\n# synthetic stale remote bytes\n'
            return SimpleNamespace(returncode=0, stdout=raw, stderr=b'')

        with patch.object(self.transport.subprocess, 'run', side_effect=git_show):
            self.assertEqual(self.transport.git_publication_gate(args), 'f' * 40)
            self.assertEqual(len(seen), 15)
            self.assertEqual(set(seen), OPERATOR_SOURCES)
            for mode in ('missing', 'stale'):
                for name in sorted(OPERATOR_SOURCES):
                    fault.update(name=name, mode=mode)
                    with self.subTest(name=name, mode=mode), self.assertRaisesRegex(ValueError, 'git_operator_bytes_not_committed'):
                        self.transport.git_publication_gate(args)

    def test_git_gate_keeps_remote_verification_and_commit_identity_requirement(self):
        with patch.object(self.transport.subprocess, 'run') as run:
            for key, value in [('candidate_git_remote_verified', False), ('candidate_git_commit', None),
                               ('candidate_git_commit', 'bad-commit')]:
                args = self.review_args({**self.review, key: value})
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'review_git_publication_required'):
                    self.transport.git_publication_gate(args)
            run.assert_not_called()


class SourceSeparationTests(unittest.TestCase):
    def test_all_59_scientific_source_members_still_match_frozen_manifest(self):
        source_root = ROOT.parent / 'source'
        frozen = (ROOT.parent / 'release/SOURCE-FREEZE.json').read_bytes()
        self.assertEqual(sha(frozen), '3c39398e27a29c0f4a8fe7a1ee668dd0d24c67c6e8de225ae2a23944e95bf459')
        roots = {'design', 'experiment_flow', 'independent-protocol-review', 'owned_runtime',
                 'reviewed', 'rl_session', 'validation'}
        rows = {name: row for name, row in json.loads(frozen)['files'].items()
                if name.split('/')[0] in roots}
        self.assertEqual(len(rows), 59)
        for name, row in rows.items():
            raw = (source_root / name).read_bytes()
            self.assertEqual((len(raw), sha(raw)), (row['bytes'], row['sha256']), name)

    def test_scientific_consumers_unchanged_outside_upload_boundary(self):
        def definitions(path):
            return {node.name: ast.dump(node, include_attributes=False)
                    for node in ast.parse(path.read_bytes()).body
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        old, new = definitions(PORTABLE / 'rl_transport.py'), definitions(ROOT / 'rl_transport.py')
        self.assertEqual(set(old), set(new))
        # Uploads now use opaque handles; review/Git admission must also cover
        # the complete bridge closure (exercised above for every missing/stale
        # member). All other publication and scientific consumer functions stay
        # byte-equivalent at the AST level.
        for name in old.keys() - {'update_code', 'review_gate', 'git_publication_gate'}:
            self.assertEqual(old[name], new[name], name)
        self.assertEqual(definitions(PORTABLE / 'rl_collect.py'), definitions(ROOT / 'rl_collect.py'))
        self.assertEqual((PORTABLE / 'sdk-lock.json').read_bytes(), (ROOT / 'sdk-lock.json').read_bytes())
        # Recheck the original consumed transport's full immutable provenance.
        provenance = json.loads((PORTABLE / 'FROZEN-SOURCE-PROVENANCE.json').read_bytes())
        for name, row in provenance['files'].items():
            raw = (REPOSITORY / row['path']).read_bytes()
            self.assertEqual((len(raw), sha(raw)), (row['bytes'], row['sha256']), name)

    def test_wsl_owner_has_no_sdk_imports_and_gates_survive_optimization(self):
        for name in ('operator_common.py', 'bridge_client.py'):
            tree = ast.parse((ROOT / name).read_bytes())
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or '')
            self.assertFalse(any(value.split('.')[0] in ('kaggle', 'kagglesdk') for value in imports), name)
        # No Python assert-based security gate disappears in optimized mode.
        for name in ('operator_common.py', 'bridge_client.py', 'protocol.py', 'sdk_worker.py'):
            self.assertFalse(any(isinstance(node, ast.Assert)
                                 for node in ast.walk(ast.parse((ROOT / name).read_bytes()))), name)


if __name__ == '__main__':
    unittest.main(verbosity=2)

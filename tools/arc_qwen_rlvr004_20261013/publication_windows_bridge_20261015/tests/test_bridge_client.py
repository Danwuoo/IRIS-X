"""Offline WSL client tests. Synthetic receipts never prove native acceptance."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_CANARY = 'synthetic-private-canary://C:/Synthetic/credential?token=never-persist'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


client_module = load('test_windows_bridge_client_module', ROOT / 'bridge_client.py')


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def binding():
    rows = {}
    for key, native in [('executable', r'C:\Synthetic\python.exe'),
                        ('supervisor', r'C:\Synthetic\win_supervisor.py'),
                        ('configuration', r'C:\Synthetic\binding.json')]:
        rows[key] = {'native_path': native, 'wsl_path': '/mnt/c/' + native[3:].replace('\\', '/'),
                     'sha256': 'a' * 64}
    rows['native_acceptance'] = {'path': '/synthetic/acceptance.json', 'sha256': 'b' * 64}
    return rows


class Common:
    def __init__(self, root):
        self.root, self.writes = root, []
        self.config = types.SimpleNamespace(versions={'code_predecessor': 20, 'code': 21,
            'inactive_predecessor': 39, 'inactive': 40, 'active': 41},
            document_sha256='c' * 64, publication_manifest_sha256='d' * 64)
        self.protocol = None
        self.wall_limit = None
        self.mapping = {'STATE': root, 'configured': lambda: self.config, 'canonical': canonical,
            'claim': self.claim, 'journal': self.journal, 'file_sha': lambda p: digest(Path(p).read_bytes()),
            'secure_path': lambda p: Path(p), 'obj': lambda p: json.loads(Path(p).read_bytes()),
            'load_source_module': self.module, 'verified': self.verified, 'wall_bound': self.wall_bound}

    def module(self, name, path, expected):
        # Test harness authenticates the actual current source, including before
        # the integration lead updates the immutable production source pin.
        self.protocol = load(name + str(id(self)), path)
        return self.protocol

    def verified(self, path, sha, cap):
        raw = Path(path).read_bytes()
        if len(raw) > cap or digest(raw) != sha:
            raise ValueError('test_source_hash')
        return raw

    def _write(self, path, value, exclusive=False):
        raw = canonical(value)
        with path.open('xb' if exclusive else 'wb') as file:
            file.write(raw); file.flush(); os.fsync(file.fileno())
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.writes.append((path.name, value.copy()))
        return {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)}

    def claim(self, name, value):
        return self._write(self.root / (name + '.claim.json'), value, True)

    def journal(self, name, value):
        target = self.root / (name + '-journal.json')
        temporary = target.with_suffix('.tmp')
        self._write(temporary, value)
        os.replace(temporary, target)
        fd = os.open(target.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return target

    @contextlib.contextmanager
    def wall_bound(self, seconds):
        if self.wall_limit is None:
            yield
            return
        old = signal.getsignal(signal.SIGALRM)
        def expired(*unused):
            raise TimeoutError('synthetic_wall_timeout')
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, min(seconds, self.wall_limit))
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)


class QueueReader:
    def __init__(self):
        self.data = bytearray()
    def read(self, count):
        result = bytes(self.data[:count]); del self.data[:count]
        return result


class ServerWriter:
    def __init__(self, server):
        self.server, self.data, self.closed = server, bytearray(), False
    def write(self, raw):
        if self.closed:
            raise BrokenPipeError('synthetic')
        self.data.extend(raw)
        return len(raw)
    def flush(self):
        protocol = self.server.protocol
        while len(self.data) >= protocol.HEADER.size:
            magic, kind, count = protocol.HEADER.unpack(self.data[:protocol.HEADER.size])
            if len(self.data) < protocol.HEADER.size + count:
                return
            raw = bytes(self.data[protocol.HEADER.size:protocol.HEADER.size + count])
            del self.data[:protocol.HEADER.size + count]
            if kind == protocol.CONTROL:
                self.server.control(protocol.strict_json(raw))
            else:
                self.server.upload.extend(raw[protocol.CONTENT_HEADER.size:])
    def close(self):
        self.closed = True


class SyntheticServer:
    def __init__(self, common, protocol, nonce, deadline, argv, *, refresh=False,
                 fault=None, content=b'archive-content'):
        self.common, self.protocol, self.nonce = common, protocol, nonce
        self.reader = QueueReader(); self.writer = ServerWriter(self)
        self.argv, self.requests, self.acks, self.upload = argv, [], [], bytearray()
        self.refresh, self.fault, self.content = refresh, fault, content
        self.released = False
        self.current = None
        self.refresh_id = digest(canonical({'account': 'danielwuu', 'old_expiration_epoch': 0}))

    def emit(self, kind, payload):
        request = self.current
        envelope = {'protocol': self.protocol.PROTOCOL, 'kind': kind, 'nonce': self.nonce,
            'sequence': request['sequence'], 'request_sha256': request['request_sha256'], 'payload': payload}
        if self.fault == 'wrong_nonce' and kind == 'response' and payload['operation'] == 'status':
            envelope['nonce'] = '0' * 64
        if self.fault == 'wrong_sequence' and kind == 'response' and payload['operation'] == 'status':
            envelope['sequence'] += 1
        raw = self.protocol.canonical(envelope)
        self.reader.data.extend(self.protocol.HEADER.pack(self.protocol.MAGIC, self.protocol.CONTROL, len(raw)) + raw)

    def respond(self, result):
        self.emit('response', {'operation': self.current['payload']['operation'], 'result': result})

    def control(self, envelope):
        kind, payload = envelope['kind'], envelope['payload']
        if kind == 'request':
            self.protocol.validate_envelope(envelope)
            self.current = envelope; self.requests.append(envelope)
            op = payload['operation']
            if op in ('status', 'output', 'binary_metadata') and self.fault in ('explicit_404', 'unknown_404_like'):
                self.emit('error', {'code': 'PROVIDER_FAILURE', 'classification': 'PROVIDER_ERROR',
                    'http_status': 404 if self.fault == 'explicit_404' else None,
                    'retry_after_seconds': 0.5, 'mutation_uncertain': False})
                return
            if op == 'open':
                if self.fault == 'open_eof':
                    return
                self.emit('ready', {'sdk_lock_sha256': client_module.SDK_LOCK_SHA256,
                    'sdk_source_count': 170, 'account': 'danielwuu', 'existing_official_store': True})
            elif op == 'close':
                self.respond({'closed': True})
            elif op == 'status':
                if self.fault in ('phases', 'nested_phase', 'unfinished_phase'):
                    phase = {'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 120,
                             'deadline_epoch': time.time() + 120}
                    self.emit('phase_start', phase)
                    if self.fault == 'nested_phase':
                        self.emit('phase_start', phase)
                    if self.fault != 'unfinished_phase':
                        self.emit('phase_end', {'phase_id': 1})
                if self.fault == 'eof':
                    return
                if self.fault == 'provider_error':
                    self.emit('error', {'code': 'PROVIDER_FAILURE', 'classification': 'TRANSIENT',
                        'http_status': 503, 'retry_after_seconds': 1, 'mutation_uncertain': False})
                else:
                    self.respond({'status': 'COMPLETE', 'failureMessage': ''})
            elif op in ('output', 'dataset_download'):
                descriptor = {key: payload['arguments'][key] for key in ('cap', 'expected_bytes', 'expected_sha256')}
                target = io.BytesIO()
                framed = self.protocol.FramedIO(io.BytesIO(), target, nonce=self.nonce)
                result = framed.send_content(io.BytesIO(self.content), descriptor,
                    sequence=envelope['sequence'], request_sha256=envelope['request_sha256'])
                self.reader.data.extend(target.getvalue())
                if self.fault == '404_after_content':
                    self.emit('error', {'code': 'PROVIDER_FAILURE', 'classification': 'PROVIDER_ERROR',
                        'http_status': 404, 'retry_after_seconds': None, 'mutation_uncertain': False})
                    return
                if self.fault == 'download_result':
                    result['sha256'] = '0' * 64
                self.respond({**result, 'http_status': 200})
            elif op == 'start_upload':
                self.respond({'handle': 'f' * 64, 'origin': {'scheme': 'https',
                    'hostname': 'storage.googleapis.com', 'port': 443, 'path_class': 'absolute',
                    'path_segments': 2, 'query_present': True, 'token_or_signed_url_persisted': False,
                    'official_init_response': True, 'payload_sha256': payload['arguments']['sha256']}})
            elif op == 'upload_once':
                pass
            elif op == 'binary_metadata':
                self.respond({'http_status': 200, 'bytes': payload['arguments']['expected_size'],
                    'body_consumed_bytes': 0, 'archive_bytes_verified': False,
                    'scope': 'numeric output request; Content-Length and successful response only'})
            else:
                raise ValueError('synthetic_operation_unimplemented')
        elif kind == 'ready_ack':
            if self.fault == 'open_ready_eof':
                return
            if self.fault == 'open_phase_eof':
                self.emit('phase_start', {'phase_id': 1, 'kind': 'official_rpc',
                    'max_seconds': 120, 'deadline_epoch': time.time() + 120})
                return
            if self.refresh:
                self.emit('refresh_request', {'refresh_id': self.refresh_id,
                    'account': 'danielwuu', 'old_expiration_epoch': 0})
            else:
                self.respond({'authenticated': True})
        elif kind == 'refresh_ack':
            self.acks.append(payload)
            name = 'native-auth-refresh-' + self.refresh_id[:24]
            claim = self.common.root / (name + '.claim.json')
            journal = self.common.root / (name + '-journal.json')
            if payload['claim_sha256'] != digest(claim.read_bytes()) or payload['journal_sha256'] != digest(journal.read_bytes()):
                raise ValueError('ack_before_durable_record')
            proof = json.loads(journal.read_bytes())
            if proof['stage'] != 'refresh_' + ('intent' if payload['phase'] == 'intent' else 'accepted'):
                raise ValueError('ack_before_durable_stage')
            if payload['phase'] == 'intent':
                if self.fault == 'refresh_eof':
                    return
                self.emit('refresh_result', {'refresh_id': self.refresh_id,
                    'new_expiration_epoch': time.time() + 3600, 'official_save_completed': True,
                    'credential_acl_verified': self.fault != 'bad_acl'})
            elif self.fault != 'accepted_ack_lost':
                self.respond({'authenticated': True})
        elif kind == 'content_start':
            self.upload.clear()
        elif kind == 'content_end':
            if payload['bytes'] != len(self.upload) or payload['sha256'] != digest(self.upload):
                raise ValueError('synthetic_upload_corrupt')
            self.respond({'bytes': len(self.upload), 'sha256': digest(self.upload), 'http_status': 200})

    def finish(self, timeout):
        if self.fault == 'finish_timeout':
            raise subprocess.TimeoutExpired('synthetic', timeout)
        closure = {'format': 'irisx/windows-job-closure-v1', 'active_processes': 0,
            'kill_on_close': True, 'breakaway_permitted': False, 'atomic_job_assignment': True}
        result = {'format': 'irisx/windows-supervisor-result-v1', 'nonce': self.nonce,
            'ok': True, 'reason': 'worker_exit', 'closure': closure}
        if self.fault == 'job_nonzero':
            closure['active_processes'] = 1
        if self.fault == 'receipt_nonce':
            result['nonce'] = '0' * 64
        if self.fault == 'missing_receipt':
            return 0, b''
        if self.fault == 'extra_stderr':
            return 0, canonical(result) + b'untrusted stderr\n'
        return 0, canonical(result)

    def release(self):
        self.released = True


class BridgeClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.common = Common(Path(self.temporary.name))
        self.servers = []

    def tearDown(self):
        self.temporary.cleanup()

    def create(self, **options):
        def factory(*args):
            server = SyntheticServer(self.common, *args, **options)
            self.servers.append(server)
            return server
        return client_module.BridgeClient.for_testing(self.common.mapping, binding(), factory)

    def session(self):
        files = list(self.common.root.glob('native-bridge-*-journal.json'))
        return json.loads(files[-1].read_bytes())

    def fail_open(self, configure, *, fault='open_eof'):
        client = client_module.BridgeClient.__new__(client_module.BridgeClient)
        def factory(*args):
            server = SyntheticServer(self.common, *args, fault=fault)
            self.servers.append(server)
            configure(server, client)
            return server
        with self.assertRaisesRegex(ValueError, '^bridge_eof_or_invalid_read$'):
            client._initialize(self.common.mapping, binding(), factory, time.monotonic, time.time)
        return client

    def assert_closed_failure_diagnostics(self, client):
        proof = self.session()
        self.assertEqual(proof['stage'], 'UNKNOWN')
        self.assertTrue(client.unknown)
        self.assertFalse(client.can_rotate_read_only())
        self.assertEqual(proof['native_process_closure_verified'], client.closure_verified)
        diagnostics = proof['failure_diagnostics']
        self.assertEqual(set(diagnostics), {'format', 'ready_observed', 'authenticated_observed',
            'rpc_phase_observed', 'cleanup', 'writer_close', 'finish', 'release',
            'proxy_exit_status', 'receipt_validation', 'receipt_bytes_capped', 'receipt_sha256',
            'supervisor_reason'})
        self.assertEqual(diagnostics['format'], 'irisx/windows-bridge-failure-diagnostics-v1')
        self.assertLess(len(canonical(diagnostics)), 1024)
        self.assertNotIn(DIAGNOSTIC_CANARY, canonical(proof).decode())
        before = len(self.servers)
        with self.assertRaisesRegex(ValueError, 'previous_session_unknown'):
            self.create()
        self.assertEqual(len(self.servers), before)
        return diagnostics

    def test_open_failure_preserves_bounded_receipt_rejection_diagnostics(self):
        cases = ('absent', 'malformed', 'oversized', 'duplicate_key', 'duplicate_receipt',
                 'wrong_nonce', 'extra_stderr', 'job_nonzero', 'not_bytes')
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                observed = []
                def configure(server, client):
                    _, raw = server.finish(1)
                    result = json.loads(raw)
                    result.update(ok=False, reason=DIAGNOSTIC_CANARY)
                    if case == 'wrong_nonce':
                        result['nonce'] = '0' * 64
                    if case == 'job_nonzero':
                        result['closure']['active_processes'] = 1
                    raw = canonical(result)
                    if case == 'absent':
                        raw = b''
                    elif case == 'malformed':
                        raw = b'{' + DIAGNOSTIC_CANARY.encode() + b'\n'
                    elif case == 'oversized':
                        raw = DIAGNOSTIC_CANARY.encode() * client_module.RECEIPT_CAP
                    elif case == 'duplicate_key':
                        raw = raw[:-2] + b',"ok":false}\n'
                    elif case == 'duplicate_receipt':
                        raw += raw
                    elif case == 'extra_stderr':
                        raw += DIAGNOSTIC_CANARY.encode() + b'\n'
                    elif case == 'not_bytes':
                        raw = DIAGNOSTIC_CANARY
                    observed.append(raw)
                    server.finish = lambda timeout: (124, raw)
                client = self.fail_open(configure)
                diagnostics = self.assert_closed_failure_diagnostics(client)
                self.assertFalse(client.closure_verified)
                self.assertFalse(diagnostics['ready_observed'])
                self.assertFalse(diagnostics['authenticated_observed'])
                self.assertEqual(diagnostics['rpc_phase_observed'], 'not_started')
                self.assertEqual(diagnostics['cleanup'], 'complete')
                self.assertEqual(diagnostics['finish'], 'complete')
                self.assertEqual(diagnostics['proxy_exit_status'], 124)
                self.assertEqual(diagnostics['receipt_validation'],
                    case if case in ('absent', 'oversized') else 'rejected')
                self.assertEqual(diagnostics['supervisor_reason'],
                                 'unrecognized' if case == 'job_nonzero' else 'unavailable')
                raw = observed[0]
                self.assertEqual(diagnostics['receipt_bytes_capped'],
                    min(len(raw), client_module.RECEIPT_CAP + 1) if type(raw) is bytes else None)
                self.assertEqual(diagnostics['receipt_sha256'], digest(raw)
                    if type(raw) is bytes and 0 < len(raw) <= client_module.RECEIPT_CAP else None)

    def test_valid_failed_jobzero_receipt_never_clears_unknown(self):
        for fault, ready, phase in [('open_eof', False, 'not_started'),
                                   ('open_ready_eof', True, 'not_started'),
                                   ('open_phase_eof', True, 'active')]:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                def configure(server, client):
                    _, raw = server.finish(1)
                    result = json.loads(raw)
                    result.update(ok=False, reason=DIAGNOSTIC_CANARY)
                    server.finish = lambda timeout: (124, canonical(result))
                client = self.fail_open(configure, fault=fault)
                diagnostics = self.assert_closed_failure_diagnostics(client)
                self.assertTrue(client.closure_verified)
                self.assertEqual(diagnostics['receipt_validation'], 'valid_job_zero')
                self.assertEqual(diagnostics['supervisor_reason'], 'unrecognized')
                self.assertEqual(diagnostics['ready_observed'], ready)
                self.assertFalse(diagnostics['authenticated_observed'])
                self.assertEqual(diagnostics['rpc_phase_observed'], phase)
                with self.assertRaisesRegex(client_module.BridgeUnknown, 'unknown_reconcile'):
                    client.close()

    def test_allowlisted_supervisor_reason_is_diagnostic_only(self):
        for reason in sorted(client_module.SUPERVISOR_REASONS):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                def configure(server, client):
                    _, raw = server.finish(1)
                    result = json.loads(raw)
                    result.update(ok=False, reason=reason, closure=None)
                    server.finish = lambda timeout: (124, canonical(result))
                client = self.fail_open(configure)
                diagnostics = self.assert_closed_failure_diagnostics(client)
                self.assertEqual(diagnostics['supervisor_reason'], reason)
                self.assertEqual(diagnostics['receipt_validation'], 'rejected')
                self.assertFalse(client.closure_verified)

    def test_supervisor_reason_requires_closed_nonce_bound_receipt_envelope(self):
        cases = ('extra_key', 'wrong_format', 'wrong_nonce', 'wrong_ok_type', 'wrong_reason_type')
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                def configure(server, client):
                    _, raw = server.finish(1)
                    result = json.loads(raw)
                    result.update(ok=False, reason='supervisor_binding_failed')
                    if case == 'extra_key':
                        result['arbitrary'] = DIAGNOSTIC_CANARY
                    elif case == 'wrong_format':
                        result['format'] = DIAGNOSTIC_CANARY
                    elif case == 'wrong_nonce':
                        result['nonce'] = '0' * 64
                    elif case == 'wrong_ok_type':
                        result['ok'] = 0
                    elif case == 'wrong_reason_type':
                        result['reason'] = [DIAGNOSTIC_CANARY]
                    server.finish = lambda timeout: (124, canonical(result))
                client = self.fail_open(configure)
                diagnostics = self.assert_closed_failure_diagnostics(client)
                self.assertEqual(diagnostics['supervisor_reason'], 'unavailable')
                self.assertEqual(diagnostics['receipt_validation'], 'rejected')
                self.assertFalse(client.closure_verified)

    def test_writer_close_failure_still_preserves_bounded_receipt(self):
        budgets = []
        def configure(server, client):
            original = server.finish
            def finish(timeout):
                budgets.append(timeout)
                return original(timeout)
            def broken_close():
                raise OSError(DIAGNOSTIC_CANARY)
            server.finish, server.writer.close = finish, broken_close
        client = self.fail_open(configure)
        diagnostics = self.assert_closed_failure_diagnostics(client)
        self.assertTrue(client.closure_verified)
        self.assertEqual(diagnostics['writer_close'], 'failed')
        self.assertEqual(diagnostics['finish'], 'complete')
        self.assertEqual(diagnostics['release'], 'complete')
        self.assertEqual(diagnostics['cleanup'], 'incomplete')
        self.assertEqual(len(budgets), 1)
        self.assertGreater(budgets[0], 0)
        self.assertLessEqual(budgets[0], client_module.CLOSURE_WAIT_SECONDS)

    def test_authenticated_phase_observation_survives_following_eof(self):
        client = self.create(fault='phases')
        client.call('status', {})
        self.servers[-1].fault = 'eof'
        with self.assertRaisesRegex(ValueError, '^bridge_eof_or_invalid_read$'):
            client.call('status', {})
        diagnostics = self.assert_closed_failure_diagnostics(client)
        self.assertTrue(diagnostics['ready_observed'])
        self.assertTrue(diagnostics['authenticated_observed'])
        self.assertEqual(diagnostics['rpc_phase_observed'], 'completed')

    def test_cleanup_timeout_failure_and_expired_budget_keep_primary_eof(self):
        for fault in ('timeout', 'finish_failed', 'release_failed', 'budget_expired'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                finishes = []
                def configure(server, client):
                    original = server.finish
                    def finish(timeout):
                        finishes.append(timeout)
                        if fault == 'timeout':
                            raise subprocess.TimeoutExpired(DIAGNOSTIC_CANARY, timeout,
                                output=DIAGNOSTIC_CANARY, stderr=DIAGNOSTIC_CANARY)
                        if fault == 'finish_failed':
                            raise RuntimeError(DIAGNOSTIC_CANARY)
                        return original(timeout)
                    server.finish = finish
                    if fault == 'release_failed':
                        def broken_release():
                            raise OSError(DIAGNOSTIC_CANARY)
                        server.release = broken_release
                    if fault == 'budget_expired':
                        control = server.control
                        def expire(envelope):
                            client.lease_deadline = client.clock() - 1
                            return control(envelope)
                        server.control = expire
                client = self.fail_open(configure)
                diagnostics = self.assert_closed_failure_diagnostics(client)
                self.assertEqual(diagnostics['cleanup'], 'incomplete')
                self.assertEqual(diagnostics['finish'], {'timeout': 'timeout',
                    'finish_failed': 'failed', 'release_failed': 'complete',
                    'budget_expired': 'budget_expired'}[fault])
                self.assertEqual(len(finishes), 0 if fault == 'budget_expired' else 1)
                self.assertEqual(client.closure_verified, fault == 'release_failed')
                if fault in ('timeout', 'finish_failed'):
                    self.assertEqual(diagnostics['receipt_validation'], 'unavailable')
                    self.assertIsNone(diagnostics['receipt_sha256'])
                if fault == 'release_failed':
                    self.assertEqual(diagnostics['release'], 'failed')

    def test_receipt_validator_failure_never_replaces_primary_eof(self):
        def configure(server, client):
            def broken_receipt(*args, **kwargs):
                raise RuntimeError(DIAGNOSTIC_CANARY)
            client._receipt = broken_receipt
        client = self.fail_open(configure)
        diagnostics = self.assert_closed_failure_diagnostics(client)
        self.assertFalse(client.closure_verified)
        self.assertEqual(diagnostics['receipt_validation'], 'rejected')
        self.assertIsNotNone(diagnostics['receipt_sha256'])

    def test_unknown_journal_failure_never_replaces_primary_eof(self):
        for permanent in (False, True):
            with self.subTest(permanent=permanent), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                attempts = []
                original = self.common.journal
                def journal(name, value):
                    if value['stage'] == 'UNKNOWN':
                        attempts.append(name)
                        if permanent or len(attempts) == 1:
                            raise OSError(DIAGNOSTIC_CANARY)
                    return original(name, value)
                self.common.mapping['journal'] = journal
                client = self.fail_open(lambda server, client: None)
                self.assertEqual(len(attempts), 2)
                self.assertTrue(client.unknown and client.closure_verified)
                self.assertEqual(client.session_proof['stage'], 'UNKNOWN')
                self.assertEqual(client.session_proof['failure_diagnostics']['receipt_validation'],
                                 'valid_job_zero')
                if not permanent:
                    self.assert_closed_failure_diagnostics(client)
                else:
                    self.assertEqual(self.session()['stage'], 'operation_intent')
                    with self.assertRaisesRegex(ValueError, 'previous_session_unknown'):
                        self.create()

    def test_close_release_failure_preserves_primary_receipt_error(self):
        client = self.create(fault='missing_receipt')
        releases = []
        def broken_release():
            releases.append(True)
            raise RuntimeError(DIAGNOSTIC_CANARY)
        self.servers[-1].release = broken_release
        with self.assertRaisesRegex(ValueError, '^bridge_supervisor_receipt_bytes$'):
            client.close()
        self.assertEqual(len(releases), 1)
        diagnostics = self.assert_closed_failure_diagnostics(client)
        self.assertEqual(diagnostics['release'], 'failed')
        self.assertEqual(diagnostics['receipt_validation'], 'absent')

    def test_real_proxy_oversized_stderr_keeps_exit_and_capped_count(self):
        processes = []
        def factory(*args):
            pipes = client_module._Pipes([sys.executable, '-I', '-B', '-c',
                'import sys; sys.stderr.write(' + repr(DIAGNOSTIC_CANARY) + ' * 200)'])
            processes.append(pipes)
            return pipes
        client = client_module.BridgeClient.__new__(client_module.BridgeClient)
        with self.assertRaises((ValueError, BrokenPipeError)):
            client._initialize(self.common.mapping, binding(), factory, time.monotonic, time.time)
        diagnostics = self.assert_closed_failure_diagnostics(client)
        self.assertEqual(diagnostics['proxy_exit_status'], 0)
        self.assertEqual(diagnostics['receipt_validation'], 'oversized')
        self.assertEqual(diagnostics['receipt_bytes_capped'], client_module.RECEIPT_CAP + 1)
        self.assertIsNone(diagnostics['receipt_sha256'])
        self.assertFalse(client.closure_verified)
        self.assertFalse(processes[0].thread.is_alive())
        self.assertLessEqual(len(processes[0].receipt), client_module.RECEIPT_CAP)

    def test_real_proxy_timeout_records_cleanup_exit_without_native_closure(self):
        processes = []
        def factory(*args):
            pipes = client_module._Pipes([sys.executable, '-I', '-B', '-c',
                'import os,time; os.close(1); time.sleep(60)'])
            processes.append(pipes)
            return pipes
        client = client_module.BridgeClient.__new__(client_module.BridgeClient)
        with mock.patch.object(client_module, 'CLOSURE_WAIT_SECONDS', 0.02):
            with self.assertRaisesRegex(ValueError, '^bridge_eof_or_invalid_read$'):
                client._initialize(self.common.mapping, binding(), factory, time.monotonic, time.time)
        diagnostics = self.assert_closed_failure_diagnostics(client)
        self.assertEqual(diagnostics['finish'], 'timeout')
        self.assertEqual(diagnostics['proxy_exit_status'], -signal.SIGKILL)
        self.assertEqual(diagnostics['receipt_validation'], 'unavailable')
        self.assertEqual(diagnostics['receipt_bytes_capped'], 0)
        self.assertIsNone(diagnostics['receipt_sha256'])
        self.assertFalse(client.closure_verified)
        self.assertFalse(processes[0].thread.is_alive())

    def test_source_bound_fixed_argv_and_open_binding(self):
        client = self.create()
        server = self.servers[-1]
        self.assertEqual(server.argv[:4], ['/mnt/c/Synthetic/python.exe', '-I', '-B', r'C:\Synthetic\win_supervisor.py'])
        self.assertNotIn('bash', server.argv)
        self.assertNotIn('powershell', server.argv)
        args = server.requests[0]['payload']['arguments']
        self.assertEqual(args['versions'], self.common.config.versions)
        self.assertEqual(args['publication_manifest_sha256'], 'd' * 64)
        self.assertEqual(args['bridge_configuration_sha256'], 'a' * 64)
        self.assertEqual(float(server.argv[-1]), args['max_seconds'])
        self.assertEqual(server.requests[0]['payload']['max_seconds'], 120)
        self.assertTrue(self.session()['synthetic_test_only'])
        client.close()
        self.assertTrue(client.closure_verified)
        self.assertEqual(self.session()['stage'], 'closed')

    def test_refresh_records_are_durable_before_each_ack(self):
        client = self.create(refresh=True)
        server = self.servers[-1]
        self.assertEqual([row['phase'] for row in server.acks], ['intent', 'accepted'])
        self.assertEqual(server.acks[0]['claim_sha256'], server.acks[1]['claim_sha256'])
        self.assertIsNone(client.refresh)
        records = list(self.common.root.glob('native-auth-refresh-*-journal.json'))
        self.assertEqual(json.loads(records[0].read_bytes())['stage'], 'refresh_accepted')
        client.close()

    def test_refresh_pipe_loss_and_acl_failure_are_permanently_unknown(self):
        for fault in ('refresh_eof', 'accepted_ack_lost', 'bad_acl'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                with self.assertRaises((ValueError, RuntimeError)):
                    self.create(refresh=True, fault=fault)
                record = next(self.common.root.glob('native-auth-refresh-*-journal.json'))
                self.assertEqual(json.loads(record.read_bytes())['stage'], 'refresh_unknown')
                self.assertEqual(self.session()['stage'], 'UNKNOWN')
                with self.assertRaisesRegex(ValueError, 'auth_refresh_unknown'):
                    self.create()

    def test_pending_claim_without_journal_blocks_before_spawn(self):
        self.common.claim('native-auth-refresh-' + '1' * 24, {'account': 'danielwuu'})
        with self.assertRaisesRegex(ValueError, 'auth_refresh_unknown'):
            self.create()
        self.assertEqual(len(self.servers), 0)

    def test_binary_download_is_streamed_and_final_result_bound(self):
        content = b'x' * (128 * 1024 + 17)
        client = self.create(content=content)
        sink = io.BytesIO()
        result = client.download('output', {'name': 'proof.zip', 'version': 41}, sink,
            cap=len(content), expected=digest(content), expected_size=len(content))
        self.assertEqual(sink.getvalue(), content)
        self.assertEqual(result, {'bytes': len(content), 'sha256': digest(content), 'http_status': 200})
        self.assertEqual(self.servers[-1].requests[-1]['payload']['max_seconds'], 900)
        client.close()

    def test_download_result_mismatch_is_unknown(self):
        client = self.create(fault='download_result')
        with self.assertRaisesRegex(ValueError, 'download_result_binding'):
            client.download('output', {'name': 'proof.zip', 'version': 41}, io.BytesIO(), cap=100)
        self.assertTrue(client.unknown)
        self.assertEqual(self.session()['stage'], 'UNKNOWN')

    def test_upload_transmits_only_content_and_opaque_handle(self):
        client = self.create()
        path = self.common.root / 'payload.zip'; path.write_bytes(b'local-content')
        result = client.upload_once('f' * 64, path)
        self.assertEqual(bytes(self.servers[-1].upload), path.read_bytes())
        self.assertEqual(result['sha256'], digest(path.read_bytes()))
        request = self.servers[-1].requests[-1]
        self.assertNotIn(str(path), json.dumps(request))
        self.assertEqual(request['payload']['max_seconds'], 600)
        with self.assertRaisesRegex(ValueError, 'mutation_replay'):
            client.upload_once('f' * 64, path)
        self.assertFalse(client.can_rotate_read_only())
        client.close()

    def test_wrong_binding_and_eof_poison_and_block_reopen(self):
        for fault in ('wrong_nonce', 'wrong_sequence', 'eof'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                client = self.create(fault=fault)
                with self.assertRaises(ValueError):
                    client.call('status', {})
                self.assertTrue(client.unknown)
                self.assertTrue(self.servers[-1].released)
                self.assertEqual(self.session()['stage'], 'UNKNOWN')
                with self.assertRaisesRegex(ValueError, 'previous_session_unknown'):
                    self.create()

    def test_process_exit_is_not_native_closure(self):
        for fault in ('missing_receipt', 'job_nonzero', 'receipt_nonce', 'extra_stderr', 'finish_timeout'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                client = self.create(fault=fault)
                with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    client.close()
                self.assertTrue(client.unknown)
                self.assertFalse(client.closure_verified)
                self.assertEqual(self.session()['stage'], 'UNKNOWN')

    def test_no_arbitrary_operation_path_or_version(self):
        client = self.create()
        count = len(self.servers[-1].requests)
        for operation, arguments in [('shell', {'argv': ['anything']}),
            ('status', {'url': 'https://example.invalid'}),
            ('list_files', {'dataset': True, 'version': 22}),
            ('binary_metadata', {'name': '../bad', 'version': 41, 'expected_size': 1, 'cap': 1})]:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                client.call(operation, arguments)
        self.assertEqual(len(self.servers[-1].requests), count)
        self.assertFalse(client.unknown)
        client.close()

    def test_safe_dto_and_readonly_rotation_require_closed_old_job(self):
        client = self.create()
        response = client.dto(client.call('status', {}), 'status')
        self.assertEqual(response.status.name, 'COMPLETE')
        copy = response.to_dict(); copy['status'] = 'ERROR'
        self.assertEqual(response.status.name, 'COMPLETE')
        replacement = client.rotate_read_only()
        self.assertTrue(client.closed and client.closure_verified)
        self.assertNotEqual(client.nonce, replacement.nonce)
        replacement.close()

    def test_mutation_prevents_rotation_even_after_success(self):
        client = self.create()
        client.call('start_upload', {'name': 'payload.zip', 'bytes': 1, 'sha256': 'e' * 64})
        with self.assertRaisesRegex(ValueError, 'rotation_forbidden'):
            client.rotate_read_only()
        client.close()

    def test_explicit_readonly_failure_closes_and_can_retry_after_rotation(self):
        client = self.create(fault='provider_error')
        with self.assertRaises(client_module.BridgeProviderError) as caught:
            client.call('status', {})
        self.assertEqual(caught.exception.classification, 'TRANSIENT')
        self.assertEqual(caught.exception.retry_after_seconds, 1)
        self.assertFalse(client.unknown)
        self.assertTrue(client.closed and client.closure_verified)
        self.assertEqual([r['payload']['operation'] for r in self.servers[-1].requests],
                         ['open', 'status', 'close'])
        self.assertEqual(self.session()['stage'], 'closed')
        replacement = self.create()
        self.assertEqual(replacement.call('status', {})['status'], 'COMPLETE')
        replacement.close()

    def test_explicit_readonly_error_without_jobzero_stays_unknown(self):
        client = self.create(fault='provider_error')
        server = self.servers[-1]
        server.finish = lambda timeout: (0, b'')
        with self.assertRaises(client_module.BridgeUnknown):
            client.call('status', {})
        self.assertTrue(client.unknown)
        self.assertFalse(client.can_rotate_read_only())

    def test_official_rpc_phase_sequence_and_unfinished_phase_fail_closed(self):
        client = self.create(fault='phases')
        self.assertEqual(client.call('status', {})['status'], 'COMPLETE')
        self.assertEqual(client.last_phase_id, 1)
        self.assertIsNone(client.active_phase)
        client.close()
        for fault in ('nested_phase', 'unfinished_phase'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                client = self.create(fault=fault)
                with self.assertRaises(ValueError):
                    client.call('status', {})
                self.assertTrue(client.unknown)

    def test_refresh_journal_failure_never_sends_ack_for_failed_stage(self):
        for stage, expected_acks in [('refresh_intent', 0), ('refresh_accepted', 1)]:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as root:
                self.common = Common(Path(root))
                original = self.common.journal
                def broken(name, proof):
                    if proof['stage'] == stage:
                        raise OSError('synthetic_disk_failure')
                    return original(name, proof)
                self.common.mapping['journal'] = broken
                with self.assertRaises(OSError):
                    self.create(refresh=True)
                self.assertEqual(len(self.servers[-1].acks), expected_acks)
                record = next(self.common.root.glob('native-auth-refresh-*-journal.json'))
                self.assertEqual(json.loads(record.read_bytes())['stage'], 'refresh_unknown')

    def test_explicit_transient_error_after_mutation_cannot_rotate(self):
        client = self.create()
        client.call('start_upload', {'name': 'payload.zip', 'bytes': 1, 'sha256': 'e' * 64})
        self.servers[-1].fault = 'provider_error'
        with self.assertRaises(client_module.BridgeProviderError):
            client.call('status', {})
        self.assertTrue(client.unknown)
        self.assertFalse(client.can_rotate_read_only())
        self.assertEqual(self.session()['stage'], 'UNKNOWN')

    def test_explicit_readonly_404_exposes_inert_metadata_and_cleanly_reopens(self):
        client = self.create(fault='explicit_404')
        with self.assertRaises(client_module.BridgeProviderError) as caught:
            client.call('binary_metadata', {'name': 'pending.zip', 'version': 41,
                        'expected_size': 1, 'cap': 1})
        error = caught.exception
        self.assertEqual(error.classification, 'PROVIDER_ERROR')
        self.assertEqual(error.response.status_code, 404)
        self.assertEqual(dict(error.response.headers), {'Retry-After': '1'})
        self.assertEqual(error.response.content, b'')
        self.assertFalse(hasattr(error.response, 'url'))
        self.assertFalse(hasattr(error.response, 'request'))
        with self.assertRaises(AttributeError):
            error.response.status_code = 200
        with self.assertRaises(TypeError):
            error.response.headers['URL'] = 'anything'
        self.assertTrue(client.closed and client.closure_verified)
        self.assertFalse(client.unknown)
        replacement = self.create()
        metadata = replacement.call('binary_metadata', {'name': 'indexed.zip', 'version': 41,
                                    'expected_size': 1, 'cap': 1})
        self.assertEqual(metadata['http_status'], 200)
        self.assertFalse(metadata['archive_bytes_verified'])
        replacement.close()

    def test_404_like_without_explicit_http_status_cannot_safely_rotate(self):
        client = self.create(fault='unknown_404_like')
        with self.assertRaises(client_module.BridgeProviderError) as caught:
            client.call('status', {})
        self.assertIsNone(caught.exception.response)
        self.assertTrue(client.unknown)
        self.assertFalse(client.can_rotate_read_only())
        self.assertEqual(self.session()['stage'], 'UNKNOWN')

    def test_404_after_content_is_unknown_not_clean_readonly_retry(self):
        client = self.create(fault='404_after_content')
        with self.assertRaises(client_module.BridgeProviderError):
            client.download('output', {'name': 'proof.zip', 'version': 41}, io.BytesIO(), cap=100)
        self.assertTrue(client.command_content_started)
        self.assertTrue(client.unknown)
        self.assertFalse(client.can_rotate_read_only())

    def test_operation_budget_is_not_reset_by_refresh_frames(self):
        client = self.create(refresh=True)
        first = self.servers[-1].requests[0]
        self.assertEqual(client.sequence, 1)
        self.assertEqual(first['payload']['max_seconds'], 120)
        self.assertLess(first['payload']['deadline_epoch'], client.lease_epoch)
        self.assertEqual(len(self.servers[-1].requests), 1)
        client.close()

    def test_production_path_requires_actual_source_bytes(self):
        with self.assertRaises(FileNotFoundError):
            client_module.BridgeClient(self.common.mapping, binding())
        self.assertEqual(len(list(self.common.root.glob('*.claim.json'))), 0)

    def test_windows_path_translation_and_closed_binding(self):
        for change in ({'native_path': r'C:\Synthetic\..\python.exe'},
                       {'wsl_path': '/tmp/python.exe'},
                       {'native_path': r'\\server\share\python.exe'},
                       {'native_path': r'C:\Synthetic\python.exe:evil'},
                       {'native_path': r'C:\Synthetic\python.exe\n'}):
            value = dict(binding()['executable']); value.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                client_module._mapped_path(value)

    def test_child_eof_reaped_without_inventing_windows_closure(self):
        class Child:
            def __init__(self, protocol, nonce, deadline, argv):
                self.p = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'pass'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
                self.reader, self.writer = self.p.stdout, self.p.stdin
            def finish(self, timeout):
                self.p.wait(timeout=timeout)
                return self.p.returncode, b''
            def release(self):
                for stream in (self.p.stdin, self.p.stdout, self.p.stderr):
                    stream.close()
                if self.p.poll() is None:
                    self.p.kill(); self.p.wait(timeout=1)
        children = []
        def factory(*args):
            child = Child(*args); children.append(child); return child
        with self.assertRaises((ValueError, BrokenPipeError)):
            client_module.BridgeClient.for_testing(self.common.mapping, binding(), factory)
        self.assertIsNotNone(children[0].p.poll())
        self.assertEqual(self.session()['stage'], 'UNKNOWN')
        self.assertFalse(self.session()['native_process_closure_verified'])

    def test_stalled_child_wall_timeout_has_durable_unknown_and_cleanup(self):
        class Stalled:
            def __init__(self, protocol, nonce, deadline, argv):
                self.p = subprocess.Popen([sys.executable, '-I', '-B', '-c',
                    'import time; time.sleep(60)'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, bufsize=0)
                self.reader, self.writer = self.p.stdout, self.p.stdin
            def finish(self, timeout):
                self.p.kill(); self.p.wait(timeout=1)
                return self.p.returncode, b''
            def release(self):
                for stream in (self.p.stdin, self.p.stdout, self.p.stderr):
                    stream.close()
        self.common.wall_limit = 0.05
        start = time.monotonic()
        with self.assertRaisesRegex(ValueError, 'bridge_io_failure'):
            client_module.BridgeClient.for_testing(self.common.mapping, binding(), Stalled)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(self.session()['stage'], 'UNKNOWN')
        self.assertFalse(self.session()['native_process_closure_verified'])


if __name__ == '__main__':
    unittest.main()

"""WSL-only journal owner for the reviewed native Windows publication bridge.

No SDK, authentication store, URL, or network client is imported here. Production
launch uses a fixed native Python executable and supervisor argv over binary
pipes. Only the native supervisor's nonce-bound Job-zero receipt can establish
Windows process closure. A WSL proxy exit/kill alone is never closure evidence.

The 12-hour worker lease is separate from an experiment's immutable clock. Each
command gets one smaller deadline, shared by all refresh/content frames. Only a
fully closed read-only worker may rotate; no mutation is replayed or migrated.
"""
from __future__ import annotations

import hashlib
import math
import ntpath
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import threading
import time
from types import MappingProxyType

PROTOCOL_SOURCE_SHA256 = '086c70bc50d942c753ac19b8b6f994a54bef1e6a3b0819cacd496d4d09c57b3d'
SDK_LOCK_SHA256 = '3d447ab7fad280fcc378fd18b57c3792c5b39798127f583679646027ab73288d'
LEASE_SECONDS = 43200.0
CLOSURE_WAIT_SECONDS = 5.0
RECEIPT_CAP = 4096
ACCOUNT = 'danielwuu'
READ_ONLY_OPERATIONS = frozenset(('dataset', 'kernel', 'status', 'list_files', 'output',
    'dataset_download', 'binary_metadata'))
VERSION_KEYS = frozenset(('code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'))


class BridgeUnknown(RuntimeError):
    """A durable uncertain bridge state requires explicit reconciliation."""


class _SafeResponse:
    """Inert compatibility metadata; no URL, session, body, or SDK reference."""
    __slots__ = ('status_code', 'headers', 'content')

    def __init__(self, status, retry_after):
        object.__setattr__(self, 'status_code', status)
        headers = {} if retry_after is None else {'Retry-After': str(math.ceil(retry_after))}
        object.__setattr__(self, 'headers', MappingProxyType(headers))
        object.__setattr__(self, 'content', b'')

    def __setattr__(self, name, value):
        raise AttributeError('bridge_response_metadata_immutable')


class BridgeProviderError(RuntimeError):
    """Only protocol-enumerated diagnostics, never SDK exception text."""
    def __init__(self, payload):
        self.bridge_failure = dict(payload)
        self.classification = payload['classification']
        self.http_status = payload['http_status']
        self.retry_after_seconds = payload['retry_after_seconds']
        self.response = None if self.http_status is None else _SafeResponse(
            self.http_status, self.retry_after_seconds)
        super().__init__(payload['code'])


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _mapped_path(row):
    """Closed drive mapping; no WSL shell, wslpath, UNC, device, or alternate ADS."""
    _need(type(row) is dict and set(row) == {'wsl_path', 'native_path', 'sha256'},
          'bridge_launch_binding_schema')
    _need(_sha(row['sha256']), 'bridge_launch_source_hash')
    native, wsl = row['native_path'], row['wsl_path']
    _need(type(native) is str and type(wsl) is str and 0 < len(native) <= 4096
          and 0 < len(wsl) <= 4096, 'bridge_launch_path_type')
    _need(not any(ord(ch) < 32 for ch in native + wsl), 'bridge_launch_path_control')
    path = PureWindowsPath(native)
    _need(re.fullmatch('[A-Za-z]:', path.drive) is not None and path.is_absolute()
          and native == str(path) and ntpath.normpath(native) == native,
          'bridge_native_absolute_path')
    _need(all(part not in ('', '.', '..') and ':' not in part and not part.endswith((' ', '.'))
              for part in path.parts[1:]), 'bridge_native_path_component')
    translated = '/mnt/' + path.drive[0].lower() + '/' + '/'.join(path.parts[1:])
    _need(wsl == translated and '..' not in Path(wsl).parts, 'bridge_reviewed_drive_mapping')
    return row


class _Pipes:
    """Own only the WSL interop proxy. Native lifetime proof is separate."""
    def __init__(self, argv):
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False, close_fds=True, bufsize=0)
        self.reader, self.writer = self.process.stdout, self.process.stdin
        self.receipt = bytearray()
        self.receipt_failed = False
        def drain():
            try:
                while True:
                    block = self.process.stderr.read(4096)
                    if not block:
                        break
                    if len(self.receipt) + len(block) > RECEIPT_CAP:
                        self.receipt_failed = True
                    elif not self.receipt_failed:
                        self.receipt.extend(block)
            except (OSError, ValueError):
                self.receipt_failed = True
        self.thread = threading.Thread(target=drain, daemon=True, name='bridge-safe-supervisor-receipt')
        self.thread.start()

    def finish(self, timeout):
        start = time.monotonic()
        code = self.process.wait(timeout=timeout)
        self.thread.join(max(0, timeout - (time.monotonic() - start)))
        _need(not self.thread.is_alive() and not self.receipt_failed,
              'bridge_supervisor_receipt_unavailable')
        return code, bytes(self.receipt)

    def release(self):
        for stream in (self.writer, self.reader, self.process.stderr):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
        # This only reaps the interop proxy, never establishes Windows closure.
        if self.process.poll() is None:
            try:
                self.process.kill()
                self.process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.thread.join(0.1)


class BridgeClient:
    """One source-bound connection with WSL-durable refresh and session claims."""
    def __init__(self, c, binding):
        self._initialize(c, binding, None, time.monotonic, time.time)

    @classmethod
    def for_testing(cls, c, binding, transport_factory, *, clock=time.monotonic,
                    wall_clock=time.time):
        """Explicit offline injection; never reachable through runtime config/CLI.

        The factory receives (protocol, nonce, monotonic_deadline, argv) and
        returns a reader/writer/finish/release transport. Claims are permanently
        labelled synthetic; such records cannot admit production execution.
        """
        _need(callable(transport_factory), 'bridge_test_transport_required')
        value = cls.__new__(cls)
        value._initialize(c, binding, transport_factory, clock, wall_clock)
        return value

    def _initialize(self, c, binding, factory, clock, wall_clock):
        self.c, self.binding = c, binding
        self.clock, self.wall_clock = clock, wall_clock
        self._factory = factory
        self.synthetic = factory is not None
        self.transport = self.io = None
        self.closed = self.unknown = self.authenticated = False
        self.closure_verified = self.ready = False
        self.sequence = 0
        self.last_phase_id = 0
        self.active_phase = None
        self.failure_handled = False
        self.active = None
        self.command_content_started = False
        self.mutations = set()
        self.refresh = None
        self.session_name = None
        self.session_proof = None
        self._validate_binding()
        source = Path(__file__).with_name('protocol.py')
        self.protocol = c['load_source_module']('reviewed_windows_bridge_protocol_' +
            PROTOCOL_SOURCE_SHA256, source, PROTOCOL_SOURCE_SHA256)
        self._pending_refresh()
        self._pending_sessions()
        config = c['configured']()
        versions = dict(config.versions)
        _need(set(versions) == VERSION_KEYS and all(type(v) is int and 1 <= v <= 1000000
              for v in versions.values()), 'bridge_reviewed_numeric_versions')
        _need(_sha(config.document_sha256) and _sha(config.publication_manifest_sha256),
              'bridge_configuration_manifest_hash')
        self.nonce = self.protocol.new_nonce()
        self.lease_deadline = clock() + LEASE_SECONDS
        self.lease_epoch = wall_clock() + LEASE_SECONDS
        self.open_binding = {'account': ACCOUNT, 'versions': versions,
            'configuration_sha256': config.document_sha256,
            'bridge_configuration_sha256': binding['configuration']['sha256'],
            'publication_manifest_sha256': config.publication_manifest_sha256,
            'deadline_epoch': self.lease_epoch, 'max_seconds': LEASE_SECONDS}
        self.session_name = 'native-bridge-' + self.nonce
        claim = c['claim'](self.session_name, {'format': 'irisx/windows-bridge-session-claim-v1',
            'nonce': self.nonce, **self.open_binding, 'synthetic_test_only': self.synthetic})
        self.session_proof = {'format': 'irisx/windows-bridge-session-journal-v1',
            'nonce': self.nonce, 'claim_sha256': claim['sha256'],
            'stage': 'launch_intent', 'synthetic_test_only': self.synthetic,
            'native_process_closure_verified': False, 'mutation_attempted': False}
        self._journal_session()
        argv = self._launch_argv()
        try:
            self.transport = factory(self.protocol, self.nonce, self.lease_deadline, argv) \
                if factory is not None else _Pipes(argv)
            self.io = self.protocol.FramedIO(self.transport.reader, self.transport.writer,
                nonce=self.nonce, clock=self.clock, deadline=self.lease_deadline)
            self._command('open', self.open_binding)
            self.authenticated = True
            self.session_proof['stage'] = 'authenticated'
            self._journal_session()
        except BaseException:
            self._failed('BRIDGE_OPEN_UNKNOWN')
            raise

    def _validate_binding(self):
        _need(type(self.binding) is dict and set(self.binding) ==
              {'executable', 'supervisor', 'configuration', 'native_acceptance'},
              'bridge_runtime_binding_schema')
        for name in ('executable', 'supervisor', 'configuration'):
            row = _mapped_path(self.binding[name])
            if not self.synthetic:
                self.c['verified'](row['wsl_path'], row['sha256'], cap=128 * 1024**2)
        _need(self.binding['executable']['native_path'].lower().endswith('\\python.exe'),
              'bridge_fixed_native_python')
        _need(PureWindowsPath(self.binding['supervisor']['native_path']).name == 'win_supervisor.py',
              'bridge_fixed_native_supervisor')
        receipt = self.binding['native_acceptance']
        _need(type(receipt) is dict and set(receipt) == {'path', 'sha256'}
              and _sha(receipt['sha256']) and type(receipt['path']) is str,
              'bridge_native_acceptance_binding')
        if not self.synthetic:
            # Detailed acceptance schema and independent review are config gates.
            self.c['verified'](receipt['path'], receipt['sha256'], cap=4 * 1024**2)

    def _launch_argv(self):
        return [self.binding['executable']['wsl_path'], '-I', '-B',
            self.binding['supervisor']['native_path'], '--config',
            self.binding['configuration']['native_path'], '--config-sha',
            self.binding['configuration']['sha256'], '--nonce', self.nonce,
            '--deadline-epoch', repr(self.lease_epoch), '--max-seconds',
            repr(self.open_binding['max_seconds'])]

    def _journal_session(self):
        self.c['journal'](self.session_name, dict(self.session_proof))

    def _pending_refresh(self):
        for path in self.c['STATE'].glob('native-auth-refresh-*.claim.json'):
            self.c['secure_path'](path)
            journal = path.with_name(path.name[:-len('.claim.json')] + '-journal.json')
            _need(journal.is_file(), 'auth_refresh_unknown_reconcile_only')
            proof = self.c['obj'](journal)
            _need(proof.get('stage') == 'refresh_accepted'
                  and proof.get('claim_sha256') == self.c['file_sha'](path),
                  'auth_refresh_unknown_reconcile_only')

    def _pending_sessions(self):
        for path in self.c['STATE'].glob('native-bridge-*.claim.json'):
            self.c['secure_path'](path)
            journal = path.with_name(path.name[:-len('.claim.json')] + '-journal.json')
            _need(journal.is_file(), 'bridge_previous_session_unknown_reconcile_only')
            proof = self.c['obj'](journal)
            _need(proof.get('stage') == 'closed'
                  and proof.get('native_process_closure_verified') is True
                  and proof.get('claim_sha256') == self.c['file_sha'](path),
                  'bridge_previous_session_unknown_reconcile_only')

    def _refresh_intent(self, payload, sequence, request_hash):
        _need(self.ready and self.refresh is None, 'bridge_refresh_state')
        self._pending_refresh()
        metadata = {'account': ACCOUNT, 'old_expiration_epoch': payload['old_expiration_epoch']}
        expected = hashlib.sha256(self.c['canonical'](metadata)).hexdigest()
        _need(payload['account'] == ACCOUNT and payload['refresh_id'] == expected,
              'bridge_refresh_identity')
        name = 'native-auth-refresh-' + expected[:24]
        claim = self.c['claim'](name, {**metadata, 'existing_grant_only': True,
            'time_epoch': self.wall_clock(), 'bridge_nonce': self.nonce,
            'refresh_id': expected, 'synthetic_test_only': self.synthetic})
        proof = {'stage': 'refresh_intent', 'claim_sha256': claim['sha256'],
            'old_expiration_epoch': payload['old_expiration_epoch'], 'attempts': 1,
            'refresh_id': expected, 'bridge_nonce': self.nonce,
            'sequence': sequence, 'request_sha256': request_hash}
        # Set in-memory uncertainty before the first durable write can fail.
        self.refresh = {'name': name, 'proof': proof, 'accepted': False}
        journal = self.c['journal'](name, proof)
        self.io.send('refresh_ack', {'refresh_id': expected, 'phase': 'intent',
            'claim_sha256': claim['sha256'], 'journal_sha256': self.c['file_sha'](journal)},
            sequence=sequence, request_sha256=request_hash)

    def _refresh_accepted(self, payload, sequence, request_hash):
        state = self.refresh
        _need(state is not None and not state['accepted']
              and payload['refresh_id'] == state['proof']['refresh_id'],
              'bridge_refresh_acceptance_state')
        _need(payload['official_save_completed'] is True and payload['credential_acl_verified'] is True
              and _finite(payload['new_expiration_epoch'])
              and payload['new_expiration_epoch'] > self.wall_clock() + 300,
              'bridge_refresh_save_acl_expiry')
        proof = {**state['proof'], 'stage': 'refresh_accepted',
            'new_expiration_epoch': payload['new_expiration_epoch'],
            'official_save_completed': True, 'credential_acl_verified': True,
            'new_grant_created': False, 'time_epoch': self.wall_clock()}
        journal = self.c['journal'](state['name'], proof)
        state['proof'], state['accepted'] = proof, True
        self.io.send('refresh_ack', {'refresh_id': payload['refresh_id'], 'phase': 'accepted',
            'claim_sha256': proof['claim_sha256'], 'journal_sha256': self.c['file_sha'](journal)},
            sequence=sequence, request_sha256=request_hash)
        # Keep the refresh pending until a final operation response proves the
        # worker consumed the ACK. Lost acknowledgement is durably UNKNOWN.

    def _receive(self, operation, sequence, request_hash, sink=None, descriptor=None):
        content = None
        while True:
            envelope = self.io.receive(kinds={'ready', 'refresh_request', 'refresh_result',
                'response', 'error', 'content_start', 'phase_start', 'phase_end'},
                sequence=sequence, request_sha256=request_hash)
            kind, payload = envelope['kind'], envelope['payload']
            if kind == 'phase_start':
                _need(self.active_phase is None and payload['phase_id'] == self.last_phase_id + 1
                      and payload['kind'] == 'official_rpc' and payload['max_seconds'] == 120,
                      'bridge_rpc_phase_start')
                self.last_phase_id = self.active_phase = payload['phase_id']
            elif kind == 'phase_end':
                _need(self.active_phase is not None and payload['phase_id'] == self.active_phase,
                      'bridge_rpc_phase_end')
                self.active_phase = None
            elif kind == 'ready':
                _need(operation == 'open' and not self.ready
                      and payload['sdk_lock_sha256'] == SDK_LOCK_SHA256
                      and payload['sdk_source_count'] == 170 and payload['account'] == ACCOUNT
                      and payload['existing_official_store'] is True, 'bridge_ready_source_account')
                self.ready = True
                self.io.send('ready_ack', {'ready': True}, sequence=sequence, request_sha256=request_hash)
            elif kind == 'refresh_request':
                self._refresh_intent(payload, sequence, request_hash)
            elif kind == 'refresh_result':
                self._refresh_accepted(payload, sequence, request_hash)
            elif kind == 'content_start':
                _need(sink is not None and descriptor is not None and content is None,
                      'bridge_unrequested_content')
                self.command_content_started = True
                content = self.io.receive_content(sink, descriptor, sequence=sequence,
                    request_sha256=request_hash, first=envelope)
            elif kind == 'error':
                raise BridgeProviderError(payload)
            else:
                _need(self.active_phase is None, 'bridge_rpc_phase_unfinished')
                _need(payload['operation'] == operation, 'bridge_response_operation')
                result = self.protocol.validate_result(operation, payload['result'])
                _need(operation != 'open' or self.ready, 'bridge_auth_before_ready')
                _need(self.refresh is None or self.refresh['accepted'], 'bridge_refresh_unfinished')
                if sink is not None:
                    _need(content is not None and content == {key: result[key] for key in ('bytes', 'sha256')},
                          'bridge_download_result_binding')
                self.refresh = None
                return result

    def _command(self, operation, arguments, *, sink=None, descriptor=None, source=None):
        _need(not self.closed and not self.unknown and self.active is None, 'bridge_client_unavailable')
        _need(operation == 'open' or self.authenticated, 'bridge_client_unauthenticated')
        self.protocol.validate_request(operation, arguments)
        self._check_versions(operation, arguments)
        _need(operation not in self.mutations, 'bridge_mutation_replay_forbidden')
        started = self.clock()
        seconds = min(self.protocol.OPERATION_TIMEOUTS[operation], self.lease_deadline - started)
        _need(seconds > 0, 'bridge_lease_expired')
        monotonic_deadline = started + seconds
        deadline_epoch = min(self.lease_epoch, self.wall_clock() + seconds)
        self.sequence += 1
        sequence = self.sequence
        digest = self.protocol.request_hash(operation, arguments,
            deadline_epoch=deadline_epoch, max_seconds=seconds)
        self.active = (operation, sequence, digest)
        self.command_content_started = False
        if operation in self.protocol.MUTATIONS:
            self.mutations.add(operation)
        self.session_proof.update(stage='operation_intent', operation=operation,
            sequence=sequence, request_sha256=digest, deadline_epoch=deadline_epoch,
            mutation_attempted=bool(self.mutations))
        try:
            self.io.deadline = monotonic_deadline
            remaining = monotonic_deadline - self.clock()
            _need(remaining > 0, 'bridge_command_deadline')
            with self.c['wall_bound'](remaining):
                self._journal_session()
                self.io.send('request', {'operation': operation, 'arguments': arguments,
                    'deadline_epoch': deadline_epoch, 'max_seconds': seconds},
                    sequence=sequence, request_sha256=digest)
                if source is not None:
                    self.io.send_content(source, descriptor, sequence=sequence, request_sha256=digest)
                result = self._receive(operation, sequence, digest, sink, descriptor)
            self.session_proof.update(stage='operation_accepted')
            self._journal_session()
            self.active = None
            return result
        except BridgeProviderError as error:
            if (operation in READ_ONLY_OPERATIONS and not self.mutations and self.refresh is None
                    and self.active_phase is None and not self.command_content_started
                    and error.bridge_failure['mutation_uncertain'] is False
                    and error.bridge_failure['code'] == 'PROVIDER_FAILURE'
                    and type(error.http_status) is int
                    and ((error.classification == 'TRANSIENT'
                          and (error.http_status == 429 or 500 <= error.http_status <= 599))
                         or (error.classification == 'PROVIDER_ERROR' and error.http_status == 404))):
                # A final, explicit read-only rejection is distinguishable from
                # transport uncertainty, but only after an acknowledged close
                # AND independent native Job-zero proof. Never reuse that worker.
                self.active = None
                self.session_proof.update(stage='read_only_operation_rejected')
                try:
                    self._journal_session()
                    self.close()
                except BaseException:
                    self._failed('BRIDGE_ERROR_CLOSE_UNKNOWN')
                    raise BridgeUnknown('bridge_error_close_unknown_reconcile_only') from None
                raise
            self._failed('BRIDGE_OPERATION_UNKNOWN')
            raise
        except BaseException:
            self._failed('BRIDGE_OPERATION_UNKNOWN')
            raise
        finally:
            if self.io is not None:
                self.io.deadline = self.lease_deadline

    def _check_versions(self, operation, arguments):
        versions = self.open_binding['versions']
        if operation in ('output', 'binary_metadata'):
            _need(arguments['version'] in {versions[key] for key in ('inactive_predecessor', 'inactive', 'active')},
                  'bridge_reviewed_output_version')
        elif operation == 'dataset_download':
            _need(arguments['version'] in {versions['code_predecessor'], versions['code']},
                  'bridge_reviewed_dataset_download_version')
        elif operation == 'list_files':
            _need(1 <= arguments['version'] <= versions['code'], 'bridge_reviewed_dataset_list_version')
        elif operation == 'version':
            _need(arguments['expected_predecessor_version'] == versions['code_predecessor'],
                  'bridge_reviewed_dataset_predecessor')

    def call(self, operation, arguments):
        _need(operation not in ('open', 'close', 'output', 'dataset_download', 'upload_once'),
              'bridge_specialized_operation_required')
        return self._command(operation, arguments)

    def dto(self, result, kind=None):
        return self.protocol.dto(result, kind=kind)

    def download(self, operation, arguments, sink, *, cap, expected=None, expected_size=None):
        _need(operation in ('output', 'dataset_download') and callable(getattr(sink, 'write', None)),
              'bridge_download_operation_sink')
        _need(type(arguments) is dict and set(arguments) == {'name', 'version'},
              'bridge_download_arguments')
        descriptor = {'cap': cap, 'expected_bytes': expected_size, 'expected_sha256': expected}
        self.protocol.validate_content_descriptor(descriptor)
        return self._command(operation, {**arguments, **descriptor}, sink=sink, descriptor=descriptor)

    def upload_once(self, handle, path):
        path = self.c['secure_path'](path)
        _need(path.is_file() and 0 < path.stat().st_size <= self.protocol.MAX_UPLOAD_BYTES,
              'bridge_upload_regular_file')
        # Pin content before transmission; FramedIO verifies this same digest
        # again. Native worker finishes verification BEFORE its only network PUT.
        before = path.stat()
        size, digest = before.st_size, self.c['file_sha'](path)
        descriptor = {'cap': size, 'expected_bytes': size, 'expected_sha256': digest}
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            opened = os.fstat(source.fileno())
            _need((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                  (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns),
                  'bridge_upload_identity_changed')
            return self._command('upload_once', {'handle': handle, 'bytes': size, 'sha256': digest},
                                 source=source, descriptor=descriptor)

    def _receipt(self, code, raw, *, clean):
        _need(type(raw) is bytes and 0 < len(raw) <= RECEIPT_CAP and raw.endswith(b'\n')
              and raw.count(b'\n') == 1, 'bridge_supervisor_receipt_bytes')
        result = self.protocol.strict_json(raw)
        _need(set(result) == {'format', 'nonce', 'ok', 'reason', 'closure'}
              and result['format'] == 'irisx/windows-supervisor-result-v1'
              and result['nonce'] == self.nonce and type(result['ok']) is bool
              and type(result['reason']) is str, 'bridge_supervisor_receipt_identity')
        closure = result['closure']
        _need(type(closure) is dict and set(closure) == {'format', 'active_processes', 'kill_on_close',
              'breakaway_permitted', 'atomic_job_assignment'}
              and closure['format'] == 'irisx/windows-job-closure-v1'
              and type(closure['active_processes']) is int and closure['active_processes'] == 0
              and closure['kill_on_close'] is True and closure['breakaway_permitted'] is False
              and closure['atomic_job_assignment'] is True, 'bridge_native_job_closure_required')
        if clean:
            _need(code == 0 and result['ok'] is True and result['reason'] == 'worker_exit',
                  'bridge_clean_native_exit_required')
        self.closure_verified = True
        return result

    def _mark_unknown(self, code):
        self.unknown = True
        if self.refresh is not None:
            state = self.refresh
            state['proof'] = {**state['proof'], 'stage': 'refresh_unknown',
                'unknown_reason': code, 'time_epoch': self.wall_clock()}
            self.c['journal'](state['name'], state['proof'])
        if self.session_proof is not None:
            self.session_proof.update(stage='UNKNOWN', unknown_reason=code,
                native_process_closure_verified=self.closure_verified)
            self._journal_session()

    def _failed(self, code):
        # Fail first, before cleanup or receipt handling can itself raise.
        if self.failure_handled:
            return
        self.failure_handled = True
        try:
            self._mark_unknown(code)
        finally:
            if self.transport is not None:
                try:
                    self.transport.writer.close()  # Native parent-EOF watchdog.
                    remaining = min(CLOSURE_WAIT_SECONDS, self.lease_deadline - self.clock())
                    if remaining > 0:
                        status, raw = self.transport.finish(remaining)
                        self._receipt(status, raw, clean=False)
                except BaseException:
                    pass
                finally:
                    self.transport.release()
            if self.session_proof is not None:
                self.session_proof['native_process_closure_verified'] = self.closure_verified
                self._journal_session()

    def close(self):
        if self.closed:
            return
        if self.unknown:
            raise BridgeUnknown('bridge_unknown_reconcile_only')
        try:
            self._command('close', {})
            # Keep stdin open until native worker exit; closing it earlier would
            # race the supervisor's success with its parent-EOF failure signal.
            remaining = min(CLOSURE_WAIT_SECONDS, self.lease_deadline - self.clock())
            _need(remaining > 0, 'bridge_closure_deadline')
            status, raw = self.transport.finish(remaining)
            self._receipt(status, raw, clean=True)
            self.session_proof.update(stage='closed', native_process_closure_verified=True)
            self._journal_session()
            self.closed = True
        except BaseException:
            self._failed('BRIDGE_CLOSE_UNKNOWN')
            raise
        finally:
            if self.transport is not None:
                self.transport.release()

    def can_rotate_read_only(self):
        return not self.unknown and not self.mutations and self.refresh is None and self.active is None

    def rotate_read_only(self):
        _need(self.can_rotate_read_only(), 'bridge_read_only_rotation_forbidden')
        self.close()
        _need(self.closure_verified, 'bridge_rotation_requires_native_closure')
        if self.synthetic:
            return type(self).for_testing(self.c, self.binding, self._factory,
                clock=self.clock, wall_clock=self.wall_clock)
        return type(self)(self.c, self.binding)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

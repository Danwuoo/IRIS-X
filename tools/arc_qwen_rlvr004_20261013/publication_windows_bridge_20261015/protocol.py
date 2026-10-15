"""Offline, fail-closed Windows/WSL publication bridge wire contract.

Only binary pipes, strict JSON DTOs and bounded content frames cross this boundary.
No SDK objects, Python object serialization, credentials, signed URLs, paths on
either host, or arbitrary exception strings are accepted. The caller owns the
WSL durable mutation/refresh journal and the native process watchdog. Checking
an injected clock cannot interrupt a blocking pipe syscall: the watchdog MUST
close the job/pipes at the absolute deadline, including on parent EOF.

A content receiver's successful return proves the complete digest and length.
An upload caller MUST finish receive_content before allowing any network PUT.
Failure poisons this connection: reconnect/reconciliation must never resend an
uncertain mutation. SequenceGuard is in-memory defence, not a durable journal.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import secrets
import struct
import time
from types import SimpleNamespace

PROTOCOL = 'irisx/windows-wsl-bridge-v1'
MAGIC = b'IXB1'
CONTROL = 1
CONTENT = 2
HEADER = struct.Struct('!4sBI')
CONTENT_HEADER = struct.Struct('!32sQ32sI')
MAX_CONTROL_BYTES = 16 * 1024**2
MAX_CHUNK_BYTES = 64 * 1024
MAX_CONTENT_BYTES = 8 * 1024**3
MAX_UPLOAD_BYTES = 64 * 1024**2
MAX_CONTENT_FRAMES = 1024 * 1024
MAX_DEPTH = 16
MAX_NODES = 100000
MAX_STRING_BYTES = 2 * 1024**2
MAX_SEQUENCE = 2**63 - 1
REF = 'danielwuu/iris-x-learning-agent-20261011'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
OPERATIONS = frozenset(('open', 'dataset', 'kernel', 'status', 'list_files', 'output',
    'dataset_download', 'binary_metadata', 'start_upload', 'upload_once',
    'version', 'save', 'close'))
OPERATION_TIMEOUTS = {operation: (900 if operation in ('output', 'dataset_download') else
    600 if operation == 'upload_once' else 120) for operation in OPERATIONS}
MUTATIONS = frozenset(('start_upload', 'upload_once', 'version', 'save'))
ERROR_CODES = frozenset(('PROVIDER_FAILURE', 'AUTH_REFRESH_UNKNOWN',
    'PROTOCOL_FAILURE', 'VERIFICATION_FAILED', 'DEADLINE_EXCEEDED'))
CLASSIFICATIONS = frozenset(('ACCESS_BLOCKED', 'GPU_UNAVAILABLE_STOP', 'TRANSIENT',
    'PROVIDER_ERROR', 'VERIFICATION_BLOCKED', 'AUTH_REFRESH_BLOCKED',
    'DIAGNOSTIC_TRUNCATED_BLOCKED'))
SAFE_MESSAGES = frozenset(('', 'GPU unavailable', 'Access blocked', 'Provider error',
    'Transient provider error', 'Diagnostic unavailable'))
STATUS_NAMES = frozenset(('UNKNOWN', 'QUEUED', 'RUNNING', 'COMPLETE', 'ERROR',
    'CANCEL_REQUESTED', 'CANCEL_ACKNOWLEDGED', 'CANCELLED', 'CANCELED', 'NEW_SCRIPT'))
_HEX = re.compile(r'[0-9a-f]{64}\Z')


class ProtocolError(ValueError):
    """The code is fixed by this module; never an external exception message."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(ok, code='bridge_schema'):
    if not ok:
        raise ProtocolError(code)


def _keys(value, fields):
    _need(type(value) is dict and set(value) == set(fields))


def _int(value, minimum=0, maximum=MAX_SEQUENCE):
    _need(type(value) is int and minimum <= value <= maximum)


def _bool(value):
    _need(type(value) is bool)


def _text(value, maximum=4096, *, empty=True):
    _need(type(value) is str)
    try:
        size = len(value.encode('utf-8'))
    except UnicodeError:
        raise ProtocolError('bridge_unicode') from None
    _need(size <= maximum and (empty or size > 0) and '\x00' not in value)


def _sha(value):
    _need(type(value) is str and _HEX.fullmatch(value) is not None)


def _epoch(value):
    _need(type(value) in (int, float) and 0 <= value <= 1e11 and math.isfinite(value))


def _strings(value, maximum=20000):
    _need(type(value) is list and len(value) <= maximum)
    for item in value:
        _text(item, 1024, empty=False)


def _relative(value, *, basename=False):
    _text(value, 512, empty=False)
    _need(not value.startswith('/') and '\\' not in value and ':' not in value
          and all(p not in ('', '.', '..') for p in value.split('/'))
          and not any(ord(c) < 32 or ord(c) == 127 for c in value)
          and (not basename or '/' not in value), 'bridge_relative_name')


def _handle(value):
    _sha(value)


def new_nonce():
    return secrets.token_hex(32)


def _walk(value):
    count = 0
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        count += 1
        _need(count <= MAX_NODES and depth <= MAX_DEPTH, 'bridge_json_bounds')
        if type(item) is dict:
            for key, child in item.items():
                _text(key, 512)
                stack.append((child, depth + 1))
        elif type(item) is list:
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            _text(item, MAX_STRING_BYTES)
        elif type(item) is int:
            _need(-MAX_SEQUENCE <= item <= MAX_SEQUENCE, 'bridge_json_integer')
        elif type(item) is float:
            _need(math.isfinite(item), 'bridge_json_nonfinite')
        else:
            _need(item is None or type(item) is bool, 'bridge_json_type')


def canonical(value):
    _walk(value)
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ProtocolError('bridge_json_invalid') from None
    _need(len(raw) <= MAX_CONTROL_BYTES, 'bridge_control_cap')
    return raw


def strict_json(raw):
    _need(type(raw) is bytes and 0 < len(raw) <= MAX_CONTROL_BYTES, 'bridge_control_cap')
    # Bound parser nesting BEFORE json.loads, including malicious opening braces.
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            _need(depth <= MAX_DEPTH + 1, 'bridge_json_bounds')
        elif byte in (93, 125):
            depth -= 1
            _need(depth >= 0, 'bridge_json_invalid')
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, 'bridge_duplicate_key')
            result[key] = value
        return result
    def integer(text):
        _need(len(text.lstrip('-')) <= 19, 'bridge_json_integer')
        value = int(text)
        _need(-MAX_SEQUENCE <= value <= MAX_SEQUENCE, 'bridge_json_integer')
        return value
    def floating(text):
        value = float(text)
        _need(math.isfinite(value), 'bridge_json_nonfinite')
        return value
    def constant(_):
        raise ProtocolError('bridge_json_nonfinite')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                            parse_int=integer, parse_float=floating, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ProtocolError('bridge_json_invalid') from None
    _walk(result)
    _need(type(result) is dict, 'bridge_json_object')
    return result


def validate_content_descriptor(value):
    _keys(value, ('cap', 'expected_bytes', 'expected_sha256'))
    _int(value['cap'], 0, MAX_CONTENT_BYTES)
    if value['expected_bytes'] is not None:
        _int(value['expected_bytes'], 0, value['cap'])
    if value['expected_sha256'] is not None:
        _sha(value['expected_sha256'])
    return value


def _content_result(value, *, http=False):
    _keys(value, ('bytes', 'sha256', 'http_status') if http else ('bytes', 'sha256'))
    _int(value['bytes'], 0, MAX_CONTENT_BYTES)
    _sha(value['sha256'])
    if http:
        _need(type(value['http_status']) is int and value['http_status'] in (200, 201))


def _wire(value):
    _keys(value, ('id', 'slug', 'new_title', 'text', 'language', 'kernel_type',
        'dataset_data_sources', 'model_data_sources', 'competition_data_sources',
        'kernel_data_sources', 'is_private', 'enable_gpu', 'enable_tpu',
        'enable_internet', 'docker_image', 'kernel_execution_type',
        'session_timeout_seconds', 'machine_shape'))
    _need(type(value['id']) is int and value['id'] == 138123872 and value['slug'] == REF)
    _text(value['new_title'], 256, empty=False)
    _text(value['text'], 1024**2, empty=False)
    _need(value['language'] == 'python' and value['kernel_type'] == 'notebook')
    for key in ('dataset_data_sources', 'model_data_sources', 'competition_data_sources', 'kernel_data_sources'):
        _strings(value[key], 64)
    _need(value['is_private'] is True and value['enable_tpu'] is False and value['enable_internet'] is False)
    _bool(value['enable_gpu'])
    _text(value['docker_image'], 256, empty=False)
    _need(type(value['kernel_execution_type']) is int and value['kernel_execution_type'] in (1, 3))
    if value['session_timeout_seconds'] is not None:
        _int(value['session_timeout_seconds'], 1, 43200)
    if value['machine_shape'] is not None:
        _text(value['machine_shape'], 128, empty=False)


def validate_request(operation, arguments):
    _need(type(operation) is str and operation in OPERATIONS, 'bridge_operation')
    _need(type(arguments) is dict)
    if operation == 'open':
        _keys(arguments, ('account', 'versions', 'configuration_sha256', 'bridge_configuration_sha256',
            'publication_manifest_sha256', 'deadline_epoch', 'max_seconds'))
        _need(arguments['account'] == 'danielwuu')
        _keys(arguments['versions'], ('code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'))
        for version in arguments['versions'].values():
            _int(version, 1, 1000000)
        for key in ('configuration_sha256', 'bridge_configuration_sha256', 'publication_manifest_sha256'):
            _sha(arguments[key])
        _epoch(arguments['deadline_epoch'])
        _need(type(arguments['max_seconds']) in (int, float) and 0 < arguments['max_seconds'] <= 43200)
    elif operation in ('dataset', 'kernel', 'status', 'close'):
        _keys(arguments, ())
    elif operation == 'list_files':
        _keys(arguments, ('dataset', 'version'))
        _need(arguments['dataset'] is True)
        _int(arguments['version'], 1, 1000000)
    elif operation in ('output', 'dataset_download'):
        _keys(arguments, ('name', 'version', 'cap', 'expected_sha256', 'expected_bytes'))
        if operation == 'output' or arguments['name'] is not None:
            _relative(arguments['name'])
        _int(arguments['version'], 1, 1000000)
        validate_content_descriptor({k: arguments[k] for k in ('cap', 'expected_bytes', 'expected_sha256')})
    elif operation == 'binary_metadata':
        _keys(arguments, ('name', 'version', 'expected_size', 'cap'))
        _relative(arguments['name'])
        _int(arguments['version'], 1, 1000000)
        _int(arguments['cap'], 0, MAX_CONTENT_BYTES)
        _int(arguments['expected_size'], 0, arguments['cap'])
    elif operation == 'start_upload':
        _keys(arguments, ('name', 'bytes', 'sha256'))
        _relative(arguments['name'], basename=True)
        _need(arguments['name'].endswith('.zip'), 'bridge_upload_name')
        _int(arguments['bytes'], 1, MAX_UPLOAD_BYTES)
        _sha(arguments['sha256'])
    elif operation == 'upload_once':
        _keys(arguments, ('handle', 'bytes', 'sha256'))
        _handle(arguments['handle'])
        _int(arguments['bytes'], 1, MAX_UPLOAD_BYTES)
        _sha(arguments['sha256'])
    elif operation == 'version':
        _keys(arguments, ('handle', 'notes', 'expected_predecessor_version'))
        _handle(arguments['handle'])
        _text(arguments['notes'], 4096, empty=False)
        _int(arguments['expected_predecessor_version'], 1, 1000000)
    elif operation == 'save':
        _keys(arguments, ('wire',))
        _wire(arguments['wire'])
    _walk(arguments)
    return arguments


def request_hash(operation, arguments, *, deadline_epoch, max_seconds):
    validate_request(operation, arguments)
    _epoch(deadline_epoch)
    _need(type(max_seconds) in (int, float) and 0 < max_seconds <= OPERATION_TIMEOUTS[operation],
          'bridge_operation_timeout')
    return hashlib.sha256(canonical({'operation': operation, 'arguments': arguments,
        'deadline_epoch': deadline_epoch, 'max_seconds': max_seconds})).hexdigest()


def _metadata(value):
    _keys(value, ('id', 'ref', 'isPrivate', 'currentVersionNumber', 'title', 'language',
        'kernelType', 'kernelDataSources', 'enableGpu', 'enableTpu', 'enableInternet',
        'modelDataSources', 'datasetDataSources', 'competitionDataSources',
        'dockerImage', 'machineShape'))
    _int(value['id'], 1)
    _text(value['ref'], 512, empty=False)
    _int(value['currentVersionNumber'], 1, 1000000)
    for key in ('isPrivate', 'enableGpu', 'enableTpu', 'enableInternet'):
        _bool(value[key])
    for key in ('title', 'language', 'kernelType', 'dockerImage', 'machineShape'):
        _text(value[key], 1024)
    for key in ('kernelDataSources', 'modelDataSources', 'datasetDataSources', 'competitionDataSources'):
        if key != 'kernelDataSources' or value[key] is not None:
            _strings(value[key], 64)


def validate_result(operation, result):
    _need(type(operation) is str and operation in OPERATIONS, 'bridge_operation')
    if operation == 'open':
        _keys(result, ('authenticated',))
        _need(result['authenticated'] is True)
    elif operation == 'dataset':
        _keys(result, ('id', 'ref', 'isPrivate', 'currentVersionNumber', 'title', 'licenseName', 'ownerRef', 'versions'))
        _int(result['id'], 1)
        _int(result['currentVersionNumber'], 1, 1000000)
        _bool(result['isPrivate'])
        for key in ('ref', 'title', 'licenseName', 'ownerRef'):
            _text(result[key], 1024, empty=False)
        _need(type(result['versions']) is list and len(result['versions']) <= 10000)
        for row in result['versions']:
            _keys(row, ('versionNumber',))
            _int(row['versionNumber'], 1, 1000000)
    elif operation == 'kernel':
        _keys(result, ('metadata', 'blob'))
        _metadata(result['metadata'])
        _keys(result['blob'], ('source',))
        _text(result['blob']['source'], 1024**2, empty=False)
    elif operation == 'status':
        _keys(result, ('status', 'failureMessage'))
        _need(type(result['status']) is str and result['status'] in STATUS_NAMES)
        _need(type(result['failureMessage']) is str and result['failureMessage'] in SAFE_MESSAGES)
    elif operation == 'list_files':
        _need(type(result) is dict and len(result) <= 20000)
        for name, size in result.items():
            _relative(name)
            _int(size)
    elif operation in ('output', 'dataset_download', 'upload_once'):
        _content_result(result, http=True)
        if operation != 'upload_once':
            _need(result['http_status'] == 200)
    elif operation == 'binary_metadata':
        _keys(result, ('http_status', 'bytes', 'body_consumed_bytes', 'archive_bytes_verified', 'scope'))
        _need(type(result['http_status']) is int and result['http_status'] == 200)
        _int(result['bytes'], 0, MAX_CONTENT_BYTES)
        _need(type(result['body_consumed_bytes']) is int and result['body_consumed_bytes'] == 0
              and result['archive_bytes_verified'] is False
              and result['scope'] == 'numeric output request; Content-Length and successful response only')
    elif operation == 'start_upload':
        _keys(result, ('handle', 'origin'))
        _handle(result['handle'])
        origin = result['origin']
        _keys(origin, ('scheme', 'hostname', 'port', 'path_class', 'path_segments',
            'query_present', 'token_or_signed_url_persisted', 'official_init_response', 'payload_sha256'))
        _need(origin['scheme'] == 'https' and origin['path_class'] == 'absolute'
              and type(origin['port']) is int and origin['port'] == 443)
        _text(origin['hostname'], 253, empty=False)
        _need(re.fullmatch(r'[a-z0-9.-]+', origin['hostname']) is not None)
        _int(origin['path_segments'], 0, 1000)
        _bool(origin['query_present'])
        _need(origin['token_or_signed_url_persisted'] is False and origin['official_init_response'] is True)
        _sha(origin['payload_sha256'])
    elif operation == 'version':
        _keys(result, ('error', 'ref'))
        _need(type(result['error']) is str and result['error'] in SAFE_MESSAGES)
        if result['ref'] is not None:
            _text(result['ref'], 512)
    elif operation == 'save':
        _keys(result, ('error', 'ref', 'kernelId', 'versionNumber', 'invalidDatasetSources',
            'invalidModelSources', 'invalidCompetitionSources', 'invalidKernelSources'))
        _need(type(result['error']) is str and result['error'] in SAFE_MESSAGES)
        if result['ref'] is not None:
            _text(result['ref'], 512)
        for key in ('kernelId', 'versionNumber'):
            if result[key] is not None:
                _int(result[key], 0)
        for key in ('invalidDatasetSources', 'invalidModelSources', 'invalidCompetitionSources', 'invalidKernelSources'):
            if result[key] is not None:
                _strings(result[key], 64)
    elif operation == 'close':
        _keys(result, ('closed',))
        _need(result['closed'] is True)
    _walk(result)
    return result


def _payload(kind, payload):
    if kind == 'request':
        _keys(payload, ('operation', 'arguments', 'deadline_epoch', 'max_seconds'))
        request_hash(payload['operation'], payload['arguments'],
            deadline_epoch=payload['deadline_epoch'], max_seconds=payload['max_seconds'])
    elif kind == 'response':
        _keys(payload, ('operation', 'result'))
        validate_result(payload['operation'], payload['result'])
    elif kind == 'phase_start':
        _keys(payload, ('phase_id', 'kind', 'max_seconds', 'deadline_epoch'))
        _int(payload['phase_id'], 1)
        _epoch(payload['deadline_epoch'])
        _need(payload['kind'] == 'official_rpc' and type(payload['max_seconds']) is int
              and payload['max_seconds'] == 120)
    elif kind == 'phase_end':
        _keys(payload, ('phase_id',))
        _int(payload['phase_id'], 1)
    elif kind == 'ready':
        _keys(payload, ('sdk_lock_sha256', 'sdk_source_count', 'account', 'existing_official_store'))
        _sha(payload['sdk_lock_sha256'])
        _need(type(payload['sdk_source_count']) is int and payload['sdk_source_count'] == 170
              and payload['account'] == 'danielwuu' and payload['existing_official_store'] is True)
    elif kind == 'ready_ack':
        _keys(payload, ('ready',))
        _need(payload['ready'] is True)
    elif kind == 'error':
        _keys(payload, ('code', 'classification', 'http_status', 'retry_after_seconds', 'mutation_uncertain'))
        _need(type(payload['code']) is str and payload['code'] in ERROR_CODES)
        _need(type(payload['classification']) is str and payload['classification'] in CLASSIFICATIONS)
        if payload['http_status'] is not None:
            _int(payload['http_status'], 100, 599)
        if payload['retry_after_seconds'] is not None:
            _need(type(payload['retry_after_seconds']) in (int, float)
                  and math.isfinite(payload['retry_after_seconds'])
                  and 0 <= payload['retry_after_seconds'] <= 600)
        _bool(payload['mutation_uncertain'])
    elif kind == 'refresh_request':
        _keys(payload, ('refresh_id', 'account', 'old_expiration_epoch'))
        _sha(payload['refresh_id'])
        _need(payload['account'] == 'danielwuu')
        _epoch(payload['old_expiration_epoch'])
    elif kind == 'refresh_ack':
        _keys(payload, ('refresh_id', 'phase', 'claim_sha256', 'journal_sha256'))
        _sha(payload['refresh_id'])
        _need(payload['phase'] in ('intent', 'accepted'))
        _sha(payload['claim_sha256'])
        _sha(payload['journal_sha256'])
    elif kind == 'refresh_result':
        _keys(payload, ('refresh_id', 'new_expiration_epoch', 'official_save_completed', 'credential_acl_verified'))
        _sha(payload['refresh_id'])
        _epoch(payload['new_expiration_epoch'])
        _need(payload['official_save_completed'] is True and payload['credential_acl_verified'] is True)
    elif kind == 'content_start':
        validate_content_descriptor(payload)
    elif kind == 'content_end':
        _keys(payload, ('bytes', 'sha256', 'frames'))
        _content_result({k: payload[k] for k in ('bytes', 'sha256')})
        _int(payload['frames'], 0, MAX_CONTENT_FRAMES)
    else:
        raise ProtocolError('bridge_message_kind')


def validate_envelope(value):
    _keys(value, ('protocol', 'kind', 'nonce', 'sequence', 'request_sha256', 'payload'))
    _need(value['protocol'] == PROTOCOL, 'bridge_protocol_version')
    _sha(value['nonce'])
    _int(value['sequence'], 1)
    _sha(value['request_sha256'])
    _need(type(value['kind']) is str, 'bridge_message_kind')
    _payload(value['kind'], value['payload'])
    if value['kind'] == 'request':
        payload = value['payload']
        _need(value['request_sha256'] == request_hash(payload['operation'], payload['arguments'],
            deadline_epoch=payload['deadline_epoch'], max_seconds=payload['max_seconds']), 'bridge_request_hash')
    return value


class SequenceGuard:
    """One in-flight command and one attempt per mutation operation per worker."""
    def __init__(self):
        self.next_sequence = 1
        self.active = None
        self.mutations = set()
        self.failed = False

    def accept(self, envelope):
        try:
            _need(not self.failed and self.active is None, 'bridge_sequence_state')
            validate_envelope(envelope)
            _need(envelope['kind'] == 'request' and envelope['sequence'] == self.next_sequence, 'bridge_sequence')
            operation = envelope['payload']['operation']
            if operation in MUTATIONS:
                _need(operation not in self.mutations, 'bridge_mutation_replay')
                self.mutations.add(operation)
            self.active = (envelope['sequence'], envelope['request_sha256'])
            self.next_sequence += 1
            return envelope['payload']
        except Exception:
            self.failed = True
            raise

    def complete(self, sequence, request_sha256):
        try:
            _need(not self.failed and type(sequence) is int and self.active == (sequence, request_sha256), 'bridge_sequence_state')
            self.active = None
        except Exception:
            self.failed = True
            raise

    def fail(self):
        self.failed = True


class FrameObserver:
    """Bounded incremental parser for the native supervisor's two relay pipes.

    Content bytes are counted and skipped, never decoded or retained. Control
    messages use exactly the endpoint validator. The caller must enforce active
    sequence/hash, arm the request deadline BEFORE forwarding the request, and
    never reset it for ready/refresh/content messages. Do not log returned DTOs.
    """
    def __init__(self, nonce, *, direction):
        _sha(nonce)
        _need(direction in ('request', 'response'), 'bridge_observer_direction')
        self.nonce, self.direction = nonce, direction
        self.header = bytearray()
        self.body = bytearray()
        self.remaining = 0
        self.frame_type = None
        self.failed = False

    def feed(self, raw):
        try:
            _need(not self.failed and type(raw) is bytes, 'bridge_observer_state')
            controls = []
            offset = 0
            while offset < len(raw):
                if self.frame_type is None:
                    length = min(HEADER.size - len(self.header), len(raw) - offset)
                    self.header.extend(raw[offset:offset + length])
                    offset += length
                    if len(self.header) < HEADER.size:
                        continue
                    magic, kind, size = HEADER.unpack(self.header)
                    self.header.clear()
                    _need(magic == MAGIC and kind in (CONTROL, CONTENT), 'bridge_frame_header')
                    _need(0 < size <= MAX_CONTROL_BYTES if kind == CONTROL else
                          CONTENT_HEADER.size < size <= CONTENT_HEADER.size + MAX_CHUNK_BYTES,
                          'bridge_frame_cap')
                    self.frame_type, self.remaining = kind, size
                length = min(self.remaining, len(raw) - offset)
                if self.frame_type == CONTROL:
                    self.body.extend(raw[offset:offset + length])
                offset += length
                self.remaining -= length
                if self.remaining:
                    continue
                if self.frame_type == CONTROL:
                    message = validate_envelope(strict_json(bytes(self.body)))
                    self.body.clear()
                    _need(message['nonce'] == self.nonce, 'bridge_nonce')
                    kinds = {'request', 'ready_ack', 'refresh_ack', 'content_start', 'content_end'} if self.direction == 'request' else {
                        'response', 'error', 'ready', 'refresh_request', 'refresh_result', 'content_start', 'content_end', 'phase_start', 'phase_end'}
                    _need(message['kind'] in kinds, 'bridge_observer_direction')
                    controls.append(message)
                self.frame_type = None
            return controls
        except BaseException:
            self.failed = True
            raise

    def finish(self):
        try:
            _need(not self.failed and not self.header and self.frame_type is None, 'bridge_truncated_frame')
        except Exception:
            self.failed = True
            raise


class FramedIO:
    """Synchronous binary I/O; failures permanently poison this instance.

    receive accepts expected sequence/request_sha256=None only for the worker's
    next command. The worker MUST pass that command through SequenceGuard.
    All other receives require the command's exact binding. No retry is made.
    """
    def __init__(self, reader, writer, *, nonce, clock=time.monotonic, deadline=None):
        _sha(nonce)
        if deadline is not None:
            _need(type(deadline) in (int, float) and math.isfinite(deadline), 'bridge_deadline')
        self.reader, self.writer, self.nonce = reader, writer, nonce
        self.clock, self.deadline = clock, deadline
        self.poisoned = False

    def _check(self):
        _need(not self.poisoned, 'bridge_connection_poisoned')
        if self.deadline is not None:
            now = self.clock()
            _need(type(now) in (int, float) and math.isfinite(now) and now < self.deadline, 'bridge_deadline_exceeded')

    def _read_exact(self, size):
        chunks = bytearray()
        remaining = size
        while remaining:
            self._check()
            try:
                part = self.reader.read(remaining)
            except (TimeoutError, OSError):
                raise ProtocolError('bridge_io_failure') from None
            self._check()
            _need(type(part) is bytes and 0 < len(part) <= remaining, 'bridge_eof_or_invalid_read')
            chunks.extend(part)
            remaining -= len(part)
        return bytes(chunks)

    def _write_all(self, raw):
        offset = 0
        while offset < len(raw):
            self._check()
            try:
                count = self.writer.write(raw[offset:])
            except (TimeoutError, OSError):
                raise ProtocolError('bridge_io_failure') from None
            self._check()
            _need(type(count) is int and 0 < count <= len(raw) - offset, 'bridge_short_write')
            offset += count

    def _frame(self, frame_type, raw):
        self._write_all(HEADER.pack(MAGIC, frame_type, len(raw)))
        self._write_all(raw)
        try:
            self.writer.flush()
        except (TimeoutError, OSError):
            raise ProtocolError('bridge_io_failure') from None
        self._check()

    def _read_frame(self):
        self._check()
        magic, frame_type, size = HEADER.unpack(self._read_exact(HEADER.size))
        _need(magic == MAGIC and frame_type in (CONTROL, CONTENT), 'bridge_frame_header')
        if frame_type == CONTROL:
            _need(0 < size <= MAX_CONTROL_BYTES, 'bridge_control_cap')
        else:
            _need(CONTENT_HEADER.size < size <= CONTENT_HEADER.size + MAX_CHUNK_BYTES, 'bridge_chunk_cap')
        return frame_type, self._read_exact(size)

    def send(self, kind, payload, *, sequence, request_sha256):
        try:
            self._check()
            envelope = {'protocol': PROTOCOL, 'kind': kind, 'nonce': self.nonce,
                'sequence': sequence, 'request_sha256': request_sha256, 'payload': payload}
            validate_envelope(envelope)
            self._frame(CONTROL, canonical(envelope))
            return envelope
        except BaseException:
            self.poisoned = True
            raise

    def _decode(self, raw, *, kinds, sequence, request_sha256):
        envelope = validate_envelope(strict_json(raw))
        _need(envelope['nonce'] == self.nonce, 'bridge_nonce')
        _need(envelope['kind'] in kinds, 'bridge_unexpected_kind')
        if sequence is not None:
            _need(type(sequence) is int and envelope['sequence'] == sequence, 'bridge_sequence')
        if request_sha256 is not None:
            _need(envelope['request_sha256'] == request_sha256, 'bridge_request_hash')
        return envelope

    def receive(self, *, kinds, sequence=None, request_sha256=None):
        try:
            _need(type(kinds) in (set, frozenset, tuple, list) and bool(kinds), 'bridge_expected_kinds')
            _need((sequence is not None and request_sha256 is not None)
                  or set(kinds) == {'request'} and sequence is None and request_sha256 is None,
                  'bridge_expected_binding')
            frame_type, raw = self._read_frame()
            _need(frame_type == CONTROL, 'bridge_unexpected_content')
            return self._decode(raw, kinds=kinds, sequence=sequence, request_sha256=request_sha256)
        except BaseException:
            self.poisoned = True
            raise

    @staticmethod
    def _chunks(source):
        if callable(getattr(source, 'read', None)):
            while True:
                chunk = source.read(MAX_CHUNK_BYTES)
                _need(type(chunk) is bytes and len(chunk) <= MAX_CHUNK_BYTES, 'bridge_source_chunk')
                if not chunk:
                    return
                yield chunk
        else:
            for chunk in source:
                _need(type(chunk) is bytes and 0 < len(chunk) <= MAX_CHUNK_BYTES, 'bridge_source_chunk')
                yield chunk

    def send_content(self, source, descriptor, *, sequence, request_sha256):
        try:
            validate_content_descriptor(descriptor)
            self.send('content_start', descriptor, sequence=sequence, request_sha256=request_sha256)
            total = count = 0
            digest = hashlib.sha256()
            for chunk in self._chunks(source):
                self._check()
                _need(count < MAX_CONTENT_FRAMES, 'bridge_content_frame_cap')
                total += len(chunk)
                _need(total <= descriptor['cap'], 'bridge_content_cap')
                if descriptor['expected_bytes'] is not None:
                    _need(total <= descriptor['expected_bytes'], 'bridge_content_size')
                digest.update(chunk)
                prefix = CONTENT_HEADER.pack(bytes.fromhex(self.nonce), sequence,
                    bytes.fromhex(request_sha256), count)
                self._frame(CONTENT, prefix + chunk)
                count += 1
            result = {'bytes': total, 'sha256': digest.hexdigest()}
            self._verify_content(result, descriptor)
            self.send('content_end', {**result, 'frames': count}, sequence=sequence, request_sha256=request_sha256)
            return result
        except BaseException:
            self.poisoned = True
            raise

    @staticmethod
    def _verify_content(result, descriptor):
        _need(result['bytes'] <= descriptor['cap'], 'bridge_content_cap')
        if descriptor['expected_bytes'] is not None:
            _need(result['bytes'] == descriptor['expected_bytes'], 'bridge_content_size')
        if descriptor['expected_sha256'] is not None:
            _need(result['sha256'] == descriptor['expected_sha256'], 'bridge_content_hash')

    def receive_content(self, sink, descriptor, *, sequence, request_sha256, first=None):
        """Only return after final hash/count verified; sink remains untrusted until then.

        The caller must discard/close the partial sink on failure. No provider
        callback is invoked here and no path can be supplied through this API.
        """
        try:
            _int(sequence, 1)
            _sha(request_sha256)
            validate_content_descriptor(descriptor)
            if first is None:
                first = self.receive(kinds={'content_start'}, sequence=sequence, request_sha256=request_sha256)
            else:
                validate_envelope(first)
                _need(first['kind'] == 'content_start' and first['nonce'] == self.nonce
                      and first['sequence'] == sequence and first['request_sha256'] == request_sha256,
                      'bridge_content_binding')
            _need(first['payload'] == descriptor, 'bridge_content_descriptor')
            total = count = 0
            digest = hashlib.sha256()
            while True:
                frame_type, raw = self._read_frame()
                if frame_type == CONTROL:
                    end = self._decode(raw, kinds={'content_end'}, sequence=sequence, request_sha256=request_sha256)['payload']
                    result = {'bytes': total, 'sha256': digest.hexdigest()}
                    _need(end == {**result, 'frames': count}, 'bridge_content_trailer')
                    self._verify_content(result, descriptor)
                    return result
                nonce, seq, request, index = CONTENT_HEADER.unpack(raw[:CONTENT_HEADER.size])
                _need(nonce.hex() == self.nonce and seq == sequence and request.hex() == request_sha256
                      and index == count, 'bridge_content_binding')
                chunk = raw[CONTENT_HEADER.size:]
                _need(count < MAX_CONTENT_FRAMES, 'bridge_content_frame_cap')
                total += len(chunk)
                _need(total <= descriptor['cap'], 'bridge_content_cap')
                if descriptor['expected_bytes'] is not None:
                    _need(total <= descriptor['expected_bytes'], 'bridge_content_size')
                digest.update(chunk)
                offset = 0
                while offset < len(chunk):
                    self._check()
                    written = sink.write(chunk[offset:])
                    _need(type(written) is int and 0 < written <= len(chunk) - offset, 'bridge_sink_write')
                    offset += written
                count += 1
        except BaseException:
            self.poisoned = True
            raise


class DTO:
    """SDK-free immutable snapshot adapter for the frozen consumer field names."""
    __slots__ = ('_value',)

    def __init__(self, value):
        _need(type(value) is dict, 'bridge_dto_object')
        _walk(value)
        object.__setattr__(self, '_value', copy.deepcopy(value))

    def __setattr__(self, name, value):
        raise AttributeError('bridge_dto_immutable')

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        parts = name.split('_')
        key = parts[0] + ''.join(part[:1].upper() + part[1:] for part in parts[1:])
        try:
            value = self._value[key]
        except KeyError:
            raise AttributeError(name) from None
        if key == 'status' and type(value) is str:
            return SimpleNamespace(name=value)
        return _adapt(value)

    def to_dict(self):
        return copy.deepcopy(self._value)


def _adapt(value):
    if type(value) is dict:
        return DTO(value)
    if type(value) is list:
        return [_adapt(item) for item in value]
    return value


def dto(value, kind=None):
    if kind is not None:
        validate_result(kind, value)
    return DTO(value)

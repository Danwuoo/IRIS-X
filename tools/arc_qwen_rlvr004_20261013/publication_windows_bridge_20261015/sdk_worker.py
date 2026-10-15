"""Bounded Windows provider process: the only bridge component doing HTTP.

No response objects, signed storage URLs, OAuth values or staging tokens enter
IPC. The supervisor must establish its fail-closed Job Object and watchdog before
calling this entry. This file has no provider work at import time.
"""
from contextlib import contextmanager, nullcontext
import hashlib
import email.utils
import io
import math
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time
import types
from urllib.parse import urljoin, urlparse


ACCOUNT = 'danielwuu'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
REF = 'danielwuu/iris-x-learning-agent-20261011'
DATASET_ID = 12504696
KERNEL_ID = 138123872
CHUNK = 65536
METADATA_CAP = 16 * 1024 * 1024
UPLOAD_CAP = 64 * 1024 * 1024
DOWNLOAD_CAP = 8 * 1024 * 1024 * 1024
HEX = re.compile(r'[0-9a-f]{64}\Z')
HANDLE = re.compile(r'[0-9a-f]{64}\Z')
MUTATIONS = frozenset(('StartBlobUpload', 'CreateDatasetVersionById', 'SaveKernel'))
RECOVERY_OPERATIONS = frozenset(('open', 'dataset', 'kernel', 'status', 'close'))
RECOVERY_ROUTES = frozenset(('GetDataset', 'GetKernel', 'GetKernelSessionStatus', 'GenerateAccessToken'))
ROUTES = {
    'datasets.DatasetApiService': {'GetDataset', 'ListDatasetFiles', 'DownloadDataset', 'CreateDatasetVersionById'},
    'kernels.KernelsApiService': {'GetKernel', 'GetKernelSessionStatus', 'DownloadKernelOutput', 'SaveKernel'},
    'blobs.BlobApiService': {'StartBlobUpload'},
    'users.AccountService': {'GenerateAccessToken'},
}

# Filled only after the corresponding reviewed sources settle. An unbound
# checkout cannot start an authenticated Windows worker.
WIN_RUNTIME_SHA256 = '7280b755d3155fb3d5d4f9989c0ea592d7a0d8be8750d635360f06fe766db69d'
NATIVE_CONFIG_SHA256 = '5008d989004f2c99948a157f9fda09f6ce751ee93c07ce39f1659f3789fb9fe8'


class WorkerGuardError(ValueError):
    pass


def need(value, code):
    if not value:
        raise WorkerGuardError(code)


def relative(name):
    need(type(name) is str and 0 < len(name) <= 1024 and '\\' not in name
         and ':' not in name and not name.startswith('/')
         and all(part not in ('', '.', '..') for part in name.split('/'))
         and all(ord(c) >= 32 and ord(c) != 127 for c in name), 'unsafe_relative_path')
    return name


def safe_url(url, upload=False):
    need(type(url) is str and len(url) <= 65536, 'storage_url_type')
    parsed = urlparse(url)
    need(parsed.scheme == 'https' and parsed.port in (None, 443)
         and not parsed.username and not parsed.password and not parsed.fragment,
         'unsafe_storage_url')
    hosts = {'storage.googleapis.com', 'www.googleapis.com'} if upload else {
        'storage.googleapis.com', 'www.kaggleusercontent.com'}
    need(parsed.hostname in hosts and parsed.path.startswith('/'), 'storage_host_not_allowed')
    return parsed


def no_retry_session(session):
    from requests.adapters import HTTPAdapter
    session.mount('https://', HTTPAdapter(max_retries=0))
    session.mount('http://', HTTPAdapter(max_retries=0))
    return session


def safe_semantic(message):
    """Only a fixed semantic label may leave this process, never original text."""
    value = str(message or '')[:8192]
    gpu = re.search(r'(?i)\bGPU(?:\s+accelerators?)?\s+(?:(?:is|are|currently)\s+)*(?:unavailable|not available)\b', value)
    gpu = gpu or re.search(r'(?i)\b(?:no|zero)\s+GPU\s+hours\b', value)
    gpu = gpu or re.search(r'(?i)\bGPU\s+hours\s+(?:remaining|available|left)\s*[:=]?\s*0(?:\.0+)?(?![\d.])', value)
    gpu = gpu or re.search(r'(?i)(?<![\d.])0(?:\.0+)?(?![\d.])\s+GPU\s+hours\s+(?:remaining|available|left)', value)
    gpu = gpu or re.search(r'(?i)\bGPU\s+(?:quota|time limit|weekly limit)\s+(?:has been\s+|is\s+)?(?:exhausted|exceeded|reached)', value)
    if gpu:
        return 'GPU unavailable'
    return 'Provider error' if value else ''


def _string(value, cap=4096, nullable=False):
    if value is None and nullable:
        return None
    need(type(value) is str and len(value.encode('utf-8')) <= cap, 'dto_string')
    return value


def _integer(value, low=0, high=2**63-1):
    need(type(value) is int and low <= value <= high, 'dto_integer')
    return value


def _boolean(value):
    need(type(value) is bool, 'dto_boolean')
    return value


def _strings(value, nullable=False):
    if value is None and nullable:
        return None
    need(type(value) in (list, tuple) and len(value) <= 256, 'dto_list')
    return [_string(item, 4096) for item in value]


def dataset_dto(response):
    need(type(response.versions) in (list, tuple) and len(response.versions) <= 1000, 'dto_versions')
    return {'id': _integer(response.id, 1), 'ref': _string(response.ref),
        'isPrivate': _boolean(response.is_private),
        'currentVersionNumber': _integer(response.current_version_number, 1),
        'title': _string(response.title), 'licenseName': _string(response.license_name),
        'ownerRef': _string(getattr(response, 'owner_ref', ACCOUNT)),
        'versions': [{'versionNumber': _integer(v.version_number, 1)} for v in response.versions]}


def kernel_dto(response):
    meta = response.metadata
    out = {'id': _integer(meta.id, 1), 'ref': _string(meta.ref), 'isPrivate': _boolean(meta.is_private),
        'currentVersionNumber': _integer(meta.current_version_number, 1),
        'title': _string(meta.title), 'language': _string(meta.language, 64),
        'kernelType': _string(meta.kernel_type, 64),
        'kernelDataSources': _strings(meta.kernel_data_sources, True),
        'enableGpu': _boolean(meta.enable_gpu), 'enableTpu': _boolean(meta.enable_tpu),
        'enableInternet': _boolean(meta.enable_internet),
        'modelDataSources': _strings(meta.model_data_sources),
        'datasetDataSources': _strings(meta.dataset_data_sources),
        'competitionDataSources': _strings(meta.competition_data_sources),
        'dockerImage': _string(meta.docker_image, 4096), 'machineShape': _string(meta.machine_shape, 256)}
    return {'metadata': out, 'blob': {'source': _string(response.blob.source, 1024 * 1024)}}


def status_dto(response):
    status = response.status.name
    need(status in {'UNKNOWN', 'QUEUED', 'RUNNING', 'COMPLETE', 'ERROR', 'CANCEL_REQUESTED',
                    'CANCEL_ACKNOWLEDGED', 'CANCELLED', 'CANCELED', 'NEW_SCRIPT'}, 'dto_status')
    return {'status': status, 'failureMessage': safe_semantic(response.failure_message)}


def version_dto(response):
    need(response.ref in (None, '', DREF), 'version_response_identity')
    return {'ref': _string(response.ref, nullable=True), 'error': safe_semantic(response.error)}


def save_dto(response, wire=None):
    need(response.ref in (None, '', REF, '/code/' + REF), 'save_response_identity')
    if wire is not None:
        for field in ('dataset', 'model', 'competition', 'kernel'):
            invalid = getattr(response, 'invalid_' + field + '_sources')
            need(invalid is None or type(invalid) in (list, tuple) and all(
                value in wire[field + '_data_sources'] for value in invalid), 'save_invalid_source_identity')
    return {'error': safe_semantic(response.error), 'ref': _string(response.ref, nullable=True),
        'kernelId': None if response.kernel_id is None else _integer(response.kernel_id),
        'versionNumber': None if response.version_number is None else _integer(response.version_number),
        'invalidDatasetSources': _strings(response.invalid_dataset_sources, True),
        'invalidModelSources': _strings(response.invalid_model_sources, True),
        'invalidCompetitionSources': _strings(response.invalid_competition_sources, True),
        'invalidKernelSources': _strings(response.invalid_kernel_sources, True)}


class HttpBoundary:
    """Same reviewed routes, timeouts and TLS/proxy settings as POSIX transport.

    Wall timeout is enforced externally by the Job Object supervisor. A worker
    failure is terminal. HTTP adapters have zero retry; mutation counters never
    reset (except one fresh GenerateAccessToken identity after durable claim).
    """
    def __init__(self, phase=None, *, recovery=False, refresh_exchange=None, lease_guard=None):
        need(type(recovery) is bool, 'worker_recovery_mode')
        self.mutations = {}
        self.refresh_objects = set()
        self.phase = phase or nullcontext
        self.recovery = recovery
        self.refresh_exchange = refresh_exchange
        self.lease_guard = lease_guard

    def bind(self, client, auth):
        session = no_retry_session(client.http_client()._session)
        send = session.send
        def bounded(request, **kw):
            if self.recovery:
                need(callable(self.lease_guard), 'recovery_http_lease_required')
                self.lease_guard()
            auth.check()
            parsed = urlparse(request.url)
            need(parsed.scheme == 'https' and parsed.hostname == 'api.kaggle.com'
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and not parsed.fragment and not parsed.query, 'official_rpc_route_required')
            operation = parsed.path.rsplit('/', 1)[-1]
            need(request.method == 'POST' and any(parsed.path == '/v1/' + service + '/' + operation
                 and operation in allowed for service, allowed in ROUTES.items()), 'unreviewed_rpc_operation')
            need(not self.recovery or operation in RECOVERY_ROUTES, 'recovery_rpc_forbidden')
            if operation in MUTATIONS:
                need(operation not in self.mutations, 'rpc_mutation_resend_forbidden')
                self.mutations[operation] = True
            if operation == 'GenerateAccessToken':
                need(auth.refreshing and auth.refresh_credential is not None, 'unclaimed_auth_refresh')
                if self.recovery:
                    exchange = self.refresh_exchange
                    need(isinstance(exchange, RefreshExchange) and getattr(auth, 'exchange', None) is exchange
                         and exchange.ready and exchange.refresh_pending
                         and exchange.refresh_claimed_id in exchange.claims
                         and getattr(self.phase, '__self__', None) is exchange
                         and getattr(self.phase, '__func__', None) is RefreshExchange.official_rpc,
                         'recovery_durable_refresh_required')
                # A credential object is unique for each official load; do not use
                # id(), which may be reused after collection during a long watch.
                marker = auth.refresh_credential
                need(marker not in self.refresh_objects, 'auth_rpc_resend_forbidden')
                self.refresh_objects.add(marker)
            was_stream = bool(kw.get('stream'))
            need(kw.get('verify', True) is not False, 'tls_verification_required')
            kw.update(timeout=(15, 90), allow_redirects=False, stream=True)
            with self.phase():
                response = send(request, **kw)
                is_json = 'json' in response.headers.get('Content-Type', '')
                if not was_stream or is_json and not (300 <= response.status_code < 400 and response.headers.get('Location')):
                    try:
                        declared = response.headers.get('Content-Length')
                        need(declared is None or 0 <= int(declared) <= METADATA_CAP, 'metadata_declared_cap')
                        parts, total = [], 0
                        for block in response.iter_content(CHUNK):
                            total += len(block)
                            need(total <= METADATA_CAP, 'metadata_stream_cap')
                            parts.append(block)
                        response._content = b''.join(parts)
                        response._content_consumed = True
                    finally:
                        response.close()
                return response
        session.send = bounded


class StorageHttp:
    def __init__(self, requests_module=None, *, recovery=False):
        need(type(recovery) is bool, 'worker_recovery_mode')
        self._requests_module = requests_module
        self.recovery = recovery

    @property
    def requests(self):
        need(not self.recovery, 'recovery_storage_forbidden')
        if self._requests_module is None:
            import requests
            self._requests_module = requests
        return self._requests_module

    @contextmanager
    def download(self, response, cap, *, metadata=False):
        need(not self.recovery, 'recovery_storage_forbidden')
        _integer(cap, 0, DOWNLOAD_CAP)
        session = None
        try:
            url = response.headers.get('Location')
            if url is None and 'json' in response.headers.get('Content-Type', ''):
                need(int(response.headers.get('Content-Length', '0')) <= 1024 * 1024,
                     'redirect_response_cap')
                need(len(response.content) <= 1024 * 1024, 'redirect_response_body_cap')
                data = response.json()
                url = data.get('url') if type(data) is dict else None
            if url:
                response.close()
                session = no_retry_session(self.requests.Session())
                for unused in range(5):
                    safe_url(url)
                    request = self.requests.Request('GET', url, headers={'Accept-Encoding': 'identity'}).prepare()
                    need('Authorization' not in request.headers and 'Cookie' not in request.headers,
                         'credential_forwarding')
                    settings = session.merge_environment_settings(url, {}, None, None, None)
                    need(settings.get('verify', True) is not False, 'tls_verification_required')
                    settings.update(stream=True, timeout=(15, 90 if metadata else 120), allow_redirects=False)
                    response = session.send(request, **settings)
                    redirect = (300 <= response.status_code < 400 and response.headers.get('Location')) if metadata else (
                        response.status_code in (301, 302, 303, 307, 308))
                    if redirect:
                        next_url = response.headers.get('Location')
                        need(bool(next_url), 'redirect_location_missing')
                        url = urljoin(url, next_url)
                        response.close()
                        continue
                    break
                else:
                    raise WorkerGuardError('redirect_limit')
            response.raise_for_status()
            need(response.status_code == 200, 'download_status')
            declared = response.headers.get('Content-Length')
            need(declared is None or 0 <= int(declared) <= cap, 'download_declared_cap')
            yield response
        finally:
            response.close()
            if session is not None:
                session.close()

    def chunks(self, response, cap):
        need(not self.recovery, 'recovery_storage_forbidden')
        total = 0
        for block in response.iter_content(CHUNK):
            need(type(block) is bytes and len(block) <= CHUNK, 'download_chunk_bound')
            total += len(block)
            need(total <= cap, 'download_stream_cap')
            if block:
                yield block

    def metadata(self, response, expected_size, cap):
        need(not self.recovery, 'recovery_storage_forbidden')
        _integer(expected_size, 0, cap)
        with self.download(response, cap, metadata=True) as download:
            length = download.headers.get('Content-Length')
            need(length is not None and int(length) == expected_size, 'checkpoint_metadata_length')
            need(download.headers.get('Content-Encoding', 'identity') in ('', 'identity'), 'checkpoint_metadata_encoding')
            return {'http_status': 200, 'bytes': expected_size, 'body_consumed_bytes': 0,
                'archive_bytes_verified': False,
                'scope': 'numeric output request; Content-Length and successful response only'}

    def put(self, url, source, size):
        need(not self.recovery, 'recovery_storage_forbidden')
        safe_url(url, upload=True)
        with no_retry_session(self.requests.Session()) as session:
            request = self.requests.Request('PUT', url, data=source,
                headers={'Content-Type': 'application/zip', 'Content-Length': str(size)}).prepare()
            need('Authorization' not in request.headers and 'Cookie' not in request.headers,
                 'upload_credential_forwarding')
            settings = session.merge_environment_settings(url, {}, None, None, None)
            need(settings.get('verify', True) is not False, 'tls_verification_required')
            settings.update(timeout=(15, 180), allow_redirects=False, stream=True)
            response = session.send(request, **settings)
            try:
                response.raise_for_status()
                need(response.status_code in (200, 201), 'upload_incomplete_no_retry')
                total = 0
                for block in response.iter_content(CHUNK):
                    total += len(block)
                    need(total <= 1024 * 1024, 'upload_response_cap')
                return response.status_code
            finally:
                response.close()


class WorkerProvider:
    """Explicit official requests; all resource identities remain fixed."""
    def __init__(self, authentication, versions, storage=None, *, recovery=False):
        need(type(recovery) is bool, 'worker_recovery_mode')
        self.recovery = recovery
        self.authentication, self.versions = authentication, dict(versions)
        need(set(self.versions) == {'code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'},
             'reviewed_version_schema')
        for number in self.versions.values():
            _integer(number, 1, 1000000)
        need(self.versions['code'] == self.versions['code_predecessor'] + 1
             and self.versions['inactive'] == self.versions['inactive_predecessor'] + 1
             and self.versions['active'] == self.versions['inactive'] + 1, 'reviewed_version_sequence')
        need(not recovery or storage is None, 'recovery_custom_storage_forbidden')
        self.storage = storage or StorageHttp(recovery=recovery)
        self.uploads = {}
        self.started = self.put_attempted = self.version_attempted = self.save_attempted = False
        self.failed = False

    @property
    def client(self):
        need(not self.failed, 'worker_latched')
        return self.authentication.renew_if_due()

    def dataset(self):
        from kagglesdk.datasets.types.dataset_api_service import ApiGetDatasetRequest
        request = ApiGetDatasetRequest()
        request.owner_slug, request.dataset_slug = ACCOUNT, DREF.split('/')[1]
        return dataset_dto(self.client.datasets.dataset_api_client.get_dataset(request))

    def kernel(self):
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
        request = ApiGetKernelRequest()
        request.user_name, request.kernel_slug = ACCOUNT, REF.split('/')[1]
        return kernel_dto(self.client.kernels.kernels_api_client.get_kernel(request))

    def status(self):
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelSessionStatusRequest
        request = ApiGetKernelSessionStatusRequest()
        request.user_name, request.kernel_slug = ACCOUNT, REF.split('/')[1]
        return status_dto(self.client.kernels.kernels_api_client.get_kernel_session_status(request))

    def list_files(self, version):
        need(not self.recovery, 'recovery_operation_forbidden')
        from kagglesdk.datasets.types.dataset_api_service import ApiListDatasetFilesRequest
        _integer(version, 1, self.versions['code'])
        token, tokens, rows = '', set(), {}
        for unused in range(100):
            request = ApiListDatasetFilesRequest()
            request.owner_slug, request.dataset_slug = ACCOUNT, DREF.split('/')[1]
            request.dataset_version_number, request.page_size = version, 200
            if token:
                request.page_token = token
            out = self.client.datasets.dataset_api_client.list_dataset_files(request)
            need(not out.error_message, 'provider_file_listing_error')
            for entry in out.dataset_files:
                name = relative(entry.name)
                need(name not in rows and len(rows) < 20000, 'provider_inventory_cap_or_duplicate')
                rows[name] = _integer(entry.total_bytes)
            token = out.next_page_token
            if not token:
                return rows
            _string(token, 65536)
            need(token not in tokens, 'provider_pagination_loop')
            tokens.add(token)
        raise WorkerGuardError('provider_pagination_cap')

    def output(self, name, version):
        need(not self.recovery, 'recovery_operation_forbidden')
        from kagglesdk.kernels.types.kernels_api_service import ApiDownloadKernelOutputRequest
        need(type(version) is int and version in {self.versions[key] for key in
            ('inactive_predecessor', 'inactive', 'active')}, 'reviewed_numeric_output_version_required')
        request = ApiDownloadKernelOutputRequest()
        request.owner_slug, request.kernel_slug = ACCOUNT, REF.split('/')[1]
        request.version_number, request.file_path = version, relative(name)
        return self.client.kernels.kernels_api_client.download_kernel_output(request)

    def dataset_download(self, name, version):
        need(not self.recovery, 'recovery_operation_forbidden')
        from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest
        need(type(version) is int and version in {self.versions['code_predecessor'], self.versions['code']},
             'reviewed_numeric_dataset_download_version_required')
        request = ApiDownloadDatasetRequest()
        request.owner_slug, request.dataset_slug = ACCOUNT, DREF.split('/')[1]
        request.dataset_version_number = version
        if name is not None:
            request.file_name, request.raw = relative(name), True
        return self.client.datasets.dataset_api_client.download_dataset(request)

    def start_upload(self, name, size, digest):
        need(not self.recovery, 'recovery_operation_forbidden')
        from kagglesdk.blobs.types.blob_api_service import ApiStartBlobUploadRequest, ApiBlobType
        need(not self.started and not self.failed, 'upload_init_resend_forbidden')
        relative(name)
        need('/' not in name and name.endswith('.zip'), 'upload_archive_name')
        _integer(size, 1, UPLOAD_CAP)
        need(type(digest) is str and HEX.fullmatch(digest), 'upload_digest')
        request = ApiStartBlobUploadRequest()
        request.type, request.name = ApiBlobType.DATASET, name
        request.content_type, request.content_length = 'application/zip', size
        self.started = True
        try:
            response = self.client.blobs.blob_api_client.start_blob_upload(request)
            need(type(response.token) is str and 0 < len(response.token) <= 65536, 'upload_init_token')
            origin = safe_url(response.create_url, upload=True)
            handle = secrets.token_hex(32)
            self.uploads[handle] = {'url': response.create_url, 'token': response.token,
                'bytes': size, 'sha256': digest, 'stage': 'begin'}
            return {'handle': handle, 'origin': {'scheme': origin.scheme, 'hostname': origin.hostname,
                'port': origin.port or 443, 'path_class': 'absolute',
                'path_segments': len([part for part in origin.path.split('/') if part]),
                'query_present': bool(origin.query), 'token_or_signed_url_persisted': False,
                'official_init_response': True, 'payload_sha256': digest}}
        except BaseException:
            self.failed = True
            raise

    def upload_once(self, handle, source, size, digest):
        need(not self.recovery, 'recovery_operation_forbidden')
        need(type(handle) is str and HANDLE.fullmatch(handle) and handle in self.uploads, 'unknown_upload_handle')
        upload = self.uploads[handle]
        need(not self.put_attempted and not self.failed and upload['stage'] == 'begin', 'upload_put_resend_forbidden')
        need(size == upload['bytes'] and digest == upload['sha256'], 'upload_handle_content_binding')
        # FramedIO has verified the entire content before this method is called.
        # Rehash the bounded seekable source so the boundary is independently
        # correct even when exercised without the protocol in offline tests.
        start = source.tell()
        total, h = 0, hashlib.sha256()
        while True:
            block = source.read(CHUNK)
            if not block:
                break
            total += len(block)
            need(total <= size, 'upload_stream_cap')
            h.update(block)
        need(total == size and h.hexdigest() == digest, 'upload_content_hash')
        source.seek(start)
        self.put_attempted = True
        upload['stage'] = 'put_intent'
        try:
            status = self.storage.put(upload['url'], source, size)
            upload['stage'] = 'put_accepted'
            return {'bytes': size, 'sha256': digest, 'http_status': status}
        except BaseException:
            self.failed = True
            raise

    def version(self, handle, notes, expected_predecessor_version):
        need(not self.recovery, 'recovery_operation_forbidden')
        from kagglesdk.datasets.types.dataset_api_service import (
            ApiCreateDatasetVersionByIdRequest, ApiCreateDatasetVersionRequestBody, ApiDatasetNewFile)
        need(type(handle) is str and HANDLE.fullmatch(handle) and handle in self.uploads, 'unknown_upload_handle')
        upload = self.uploads[handle]
        need(not self.version_attempted and not self.failed and upload['stage'] == 'put_accepted',
             'version_predecessor_stage')
        need(expected_predecessor_version == self.versions['code_predecessor'], 'version_expected_predecessor')
        _string(notes, 8192)
        predecessor = self.dataset()
        need(predecessor['id'] == DATASET_ID and predecessor['ref'] == DREF
             and predecessor['isPrivate'] is True
             and predecessor['currentVersionNumber'] == expected_predecessor_version,
             'version_actual_predecessor')
        file = ApiDatasetNewFile()
        file.token = upload['token']
        body = ApiCreateDatasetVersionRequestBody()
        body.files, body.delete_old_versions, body.version_notes = [file], False, notes
        request = ApiCreateDatasetVersionByIdRequest()
        request.id, request.body = DATASET_ID, body
        self.version_attempted = True
        upload['stage'] = 'version_intent'
        try:
            result = version_dto(self.client.datasets.dataset_api_client.create_dataset_version_by_id(request))
            upload['stage'] = 'version_accepted'
            return result
        except BaseException:
            self.failed = True
            raise
        finally:
            self.uploads.pop(handle, None)

    def save(self, wire):
        need(not self.recovery, 'recovery_operation_forbidden')
        from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
        from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
        need(not self.save_attempted and not self.failed, 'save_resend_forbidden')
        need(type(wire) is dict and wire.get('id') == KERNEL_ID and wire.get('slug') == REF
             and wire.get('is_private') is True, 'save_fixed_private_identity')
        request = ApiSaveKernelRequest()
        for key, value in wire.items():
            if key == 'kernel_execution_type':
                value = KernelExecutionType(value)
            if value is not None:
                setattr(request, key, value)
        self.save_attempted = True
        try:
            return save_dto(self.client.kernels.kernels_api_client.save_kernel(request), wire)
        except BaseException:
            self.failed = True
            raise

    def close(self):
        self.uploads.clear()
        self.authentication.close()


class RefreshExchange:
    def __init__(self, channel):
        self.channel = channel
        self.sequence = self.request_sha256 = None
        self.ready = False
        self.claims = {}
        self.phase_id = 0
        self.refresh_pending = self.phase_active = False
        self.refresh_claimed_id = None

    def bind_request(self, sequence, request_sha256):
        self.sequence, self.request_sha256 = sequence, request_sha256

    def check_ready(self):
        need(self.ready and self.sequence is not None, 'refresh_ipc_not_ready')

    def _ack(self, refresh_id, phase):
        envelope = self.channel.receive(kinds={'refresh_ack'}, sequence=self.sequence,
                                        request_sha256=self.request_sha256)
        value = envelope['payload']
        need(set(value) == {'refresh_id', 'phase', 'claim_sha256', 'journal_sha256'}
             and value['refresh_id'] == refresh_id and value['phase'] == phase,
             'refresh_durable_ack_binding')
        need(all(type(value[key]) is str and HEX.fullmatch(value[key])
                 for key in ('claim_sha256', 'journal_sha256')), 'refresh_durable_ack_hash')
        if phase == 'intent':
            need(refresh_id not in self.claims, 'refresh_attempt_replay')
            self.claims[refresh_id] = value['claim_sha256']
        else:
            need(self.claims.get(refresh_id) == value['claim_sha256'], 'refresh_accepted_claim_binding')

    def intent(self, metadata):
        self.check_ready()
        self.refresh_pending = True
        self.refresh_claimed_id = None
        self.channel.send('refresh_request', metadata, sequence=self.sequence,
                          request_sha256=self.request_sha256)
        self._ack(metadata['refresh_id'], 'intent')
        self.refresh_claimed_id = metadata['refresh_id']

    def accepted(self, metadata):
        self.channel.send('refresh_result', metadata, sequence=self.sequence,
                          request_sha256=self.request_sha256)
        self._ack(metadata['refresh_id'], 'accepted')
        self.refresh_pending = False
        self.refresh_claimed_id = None

    @contextmanager
    def official_rpc(self):
        self.check_ready()
        self.phase_id += 1
        phase_id = self.phase_id
        need(not self.phase_active, 'nested_official_rpc_phase')
        self.channel.send('phase_start', {'phase_id': phase_id, 'kind': 'official_rpc',
            'max_seconds': 120, 'deadline_epoch': time.time() + 120},
            sequence=self.sequence, request_sha256=self.request_sha256)
        self.phase_active = True
        try:
            yield
        finally:
            self.channel.send('phase_end', {'phase_id': phase_id}, sequence=self.sequence,
                              request_sha256=self.request_sha256)
            self.phase_active = False


def error_dto(error, mutation=False):
    """Never serialize repr/str of a provider, HTTP or protocol exception."""
    name = type(error).__name__
    status = getattr(getattr(error, 'response', None), 'status_code', None)
    response = getattr(error, 'response', None)
    if response is not None and 'json' in getattr(response, 'headers', {}).get('Content-Type', ''):
        try:
            if len(response.content) <= 65536:
                rpc_code = response.json().get('code')
                if type(rpc_code) is int and 400 <= rpc_code <= 599:
                    status = rpc_code
        except Exception:
            pass
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    semantic = safe_semantic(error)
    diagnostic = str(error)
    proxy_denial = re.search(r'(?i)\bTunnel connection failed:\s*(?:401|403)(?![\d.])\b', diagnostic[:8192])
    if name in ('AuthRefreshUnknown', 'AuthRefreshUncertain'):
        code, classification, mutation = 'AUTH_REFRESH_UNKNOWN', 'AUTH_REFRESH_BLOCKED', True
    elif semantic == 'GPU unavailable':
        code, classification = 'PROVIDER_FAILURE', 'GPU_UNAVAILABLE_STOP'
    elif status in (401, 403) or proxy_denial:
        code, classification = 'PROVIDER_FAILURE', 'ACCESS_BLOCKED'
    elif len(diagnostic) > 8192:
        code, classification = 'PROVIDER_FAILURE', 'DIAGNOSTIC_TRUNCATED_BLOCKED'
    elif status == 429 or status is not None and status >= 500:
        code, classification = 'PROVIDER_FAILURE', 'TRANSIENT'
    elif name in ('WorkerGuardError', 'AuthGuardError', 'RuntimeGuardError', 'WindowsGuardError', 'ProbeError'):
        code, classification = 'VERIFICATION_FAILED', 'VERIFICATION_BLOCKED'
    elif name in ('ProtocolError', 'EOFError', 'BrokenPipeError'):
        code, classification = 'PROTOCOL_FAILURE', 'VERIFICATION_BLOCKED'
    elif name in ('TimeoutError', 'WallTimeout'):
        code, classification = 'DEADLINE_EXCEEDED', 'TRANSIENT'
    elif name in ('Timeout', 'ReadTimeout', 'ConnectTimeout', 'ConnectionError', 'ProxyError'):
        code, classification = 'PROVIDER_FAILURE', 'TRANSIENT'
    else:
        code, classification = 'PROVIDER_FAILURE', 'PROVIDER_ERROR'
    retry = None
    if response is not None:
        value = getattr(response, 'headers', {}).get('Retry-After')
        try:
            retry = max(0, min(600, int(value)))
        except (TypeError, ValueError):
            try:
                retry = max(0, min(600, email.utils.parsedate_to_datetime(value).timestamp() - time.time()))
            except Exception:
                pass
    return {'code': code, 'classification': classification, 'http_status': status,
            'retry_after_seconds': retry, 'mutation_uncertain': bool(mutation)}


def run_worker(runtime, versions, channel, protocol, auth_module, *,
               deadline_epoch, max_seconds, monotonic_deadline=None):
    """Serve one sequential stream; any error closes it, with no implicit retry.

    The caller supplies source-verified local modules, a runtime already bound to
    the supervisor Job, and a FramedIO on duplicate stdout/stdin handles.
    """
    recovery = getattr(runtime, 'recovery', None)
    recovery_enabled = recovery is not None
    exchange = RefreshExchange(channel)
    def recovery_lease():
        need(time.time() < min(deadline_epoch, recovery['expires_epoch'])
             and time.monotonic() < lease_end, 'worker_recovery_expired')
    boundary = HttpBoundary(exchange.official_rpc, recovery=recovery_enabled,
        refresh_exchange=exchange, lease_guard=recovery_lease if recovery_enabled else None)
    auth = auth_module.OfficialSession(runtime, exchange, boundary.bind)
    provider = None
    sequence, active_hash, operation = 1, None, 'open'
    content_started = False
    sequence_guard = protocol.SequenceGuard()
    need(type(deadline_epoch) in (int, float) and math.isfinite(deadline_epoch)
         and type(max_seconds) in (int, float) and math.isfinite(max_seconds) and 0 < max_seconds <= 43200
         and (monotonic_deadline is None or type(monotonic_deadline) in (int, float)
              and math.isfinite(monotonic_deadline)),
         'worker_lease_invalid')
    lease_end = monotonic_deadline if monotonic_deadline is not None else time.monotonic() + min(
        max_seconds, max(0, deadline_epoch - time.time()))
    channel.deadline = lease_end
    try:
        if recovery_enabled:
            need(type(recovery) is dict and set(recovery) == {'capability_sha256', 'reservation_sha256',
                 'challenge', 'host_install_sha256', 'last_boot_utc', 'expires_epoch', 'allowed_operations'}
                 and recovery['allowed_operations'] == ['open', 'dataset', 'kernel', 'status', 'close']
                 and all(type(recovery[key]) is str and HEX.fullmatch(recovery[key]) for key in
                         ('capability_sha256', 'reservation_sha256', 'challenge', 'host_install_sha256')),
                 'worker_recovery_binding')
            need(type(recovery['expires_epoch']) in (int, float) and math.isfinite(recovery['expires_epoch'])
                 and deadline_epoch <= recovery['expires_epoch'], 'worker_recovery_lease')
            lease_end = min(lease_end, time.monotonic() + min(max_seconds,
                deadline_epoch - time.time(), recovery['expires_epoch'] - time.time()))
            channel.deadline = lease_end
            recovery_lease()
        while True:
            envelope = channel.receive(kinds={'request'})
            payload = sequence_guard.accept(envelope)
            sequence = envelope['sequence']
            active_hash = envelope['request_sha256']
            operation, arguments = payload['operation'], payload['arguments']
            content_started = False
            if recovery_enabled:
                recovery_lease()
                need(operation in RECOVERY_OPERATIONS, 'recovery_operation_forbidden')
            protocol.validate_request(operation, arguments)
            need(protocol.request_hash(operation, arguments, deadline_epoch=payload['deadline_epoch'],
                 max_seconds=payload['max_seconds']) == active_hash, 'request_content_binding')
            need(time.time() < payload['deadline_epoch'] <= deadline_epoch
                 and 0 < payload['max_seconds'] <= protocol.OPERATION_TIMEOUTS[operation], 'request_deadline')
            channel.deadline = min(lease_end, time.monotonic() + min(payload['max_seconds'],
                payload['deadline_epoch'] - time.time()))
            exchange.bind_request(sequence, active_hash)
            if sequence == 1:
                need(operation == 'open', 'initial_open_required')
                need(arguments['account'] == ACCOUNT and arguments['versions'] == dict(versions)
                     and arguments['bridge_configuration_sha256'] == runtime.config_sha256
                     and arguments['deadline_epoch'] == deadline_epoch
                     and arguments['max_seconds'] == max_seconds, 'native_open_binding')
                need(('recovery' in arguments) == recovery_enabled, 'native_open_mode_binding')
                if recovery_enabled:
                    need(arguments['recovery'] == {key: recovery[key]
                         for key in ('capability_sha256', 'reservation_sha256')}, 'native_open_recovery_binding')
                    runtime.verify_recovery_boot(deadline_epoch=deadline_epoch, max_seconds=max_seconds,
                        monotonic_deadline=min(lease_end, channel.deadline))
                ready = auth.prepare()
                channel.send('ready', ready, sequence=sequence, request_sha256=active_hash)
                ack = channel.receive(kinds={'ready_ack'}, sequence=sequence, request_sha256=active_hash)
                need(ack['payload'] == {'ready': True}, 'ready_ack_required')
                exchange.ready = True
                auth.protocol_ready()
                if recovery_enabled:
                    runtime.verify_recovery_boot(deadline_epoch=deadline_epoch, max_seconds=max_seconds,
                        monotonic_deadline=min(lease_end, channel.deadline))
                    recovery_lease()
                auth.open()
                provider = WorkerProvider(auth, versions, recovery=recovery_enabled) if recovery_enabled else WorkerProvider(auth, versions)
                result = {'authenticated': True}
            else:
                need(provider is not None and operation != 'open', 'worker_not_authenticated')
                if operation == 'close':
                    result = {'closed': True}
                elif operation in ('dataset', 'kernel', 'status'):
                    result = getattr(provider, operation)()
                elif operation == 'list_files':
                    result = provider.list_files(arguments['version'])
                elif operation in ('output', 'dataset_download'):
                    descriptor = {key: arguments[key] for key in ('cap', 'expected_bytes', 'expected_sha256')}
                    response = getattr(provider, operation)(arguments['name'], arguments['version'])
                    with provider.storage.download(response, arguments['cap']) as download:
                        content_started = True
                        result = channel.send_content(provider.storage.chunks(download, arguments['cap']),
                            descriptor, sequence=sequence, request_sha256=active_hash)
                    result = {**result, 'http_status': 200}
                elif operation == 'binary_metadata':
                    response = provider.output(arguments['name'], arguments['version'])
                    result = provider.storage.metadata(response, arguments['expected_size'], arguments['cap'])
                elif operation == 'start_upload':
                    result = provider.start_upload(arguments['name'], arguments['bytes'], arguments['sha256'])
                elif operation == 'upload_once':
                    _integer(arguments['bytes'], 1, UPLOAD_CAP)
                    upload = provider.uploads.get(arguments['handle'])
                    need(upload is not None and upload['bytes'] == arguments['bytes']
                         and upload['sha256'] == arguments['sha256'] and upload['stage'] == 'begin',
                         'upload_precontent_binding')
                    descriptor = {'cap': arguments['bytes'], 'expected_bytes': arguments['bytes'],
                                  'expected_sha256': arguments['sha256']}
                    with io.BytesIO() as source:
                        channel.receive_content(source, descriptor, sequence=sequence, request_sha256=active_hash)
                        source.seek(0)
                        result = provider.upload_once(arguments['handle'], source, arguments['bytes'], arguments['sha256'])
                elif operation == 'version':
                    result = provider.version(arguments['handle'], arguments['notes'], arguments['expected_predecessor_version'])
                elif operation == 'save':
                    result = provider.save(arguments['wire'])
                else:
                    raise WorkerGuardError('unsupported_operation')
            channel.send('response', {'operation': operation, 'result': result},
                         sequence=sequence, request_sha256=active_hash)
            sequence_guard.complete(sequence, active_hash)
            channel.deadline = lease_end
            if operation == 'close':
                return 0
            sequence += 1
    except BaseException as error:
        result = error_dto(error, operation in {'start_upload', 'upload_once', 'version', 'save'})
        if active_hash is not None:
            try:
                channel.send('error', result,
                             sequence=sequence, request_sha256=active_hash)
                # A fully received, explicit transient read-only response may
                # close cleanly so the WSL watcher preserves existing backoff.
                # No business request or auth renewal follows the failure.
                safe_close = (provider is not None and operation in {'dataset', 'kernel', 'status',
                    'list_files', 'output', 'dataset_download', 'binary_metadata'}
                    and not content_started and result['code'] == 'PROVIDER_FAILURE'
                    and (result['classification'] == 'TRANSIENT' and result['http_status'] is not None
                         or result['classification'] == 'PROVIDER_ERROR' and result['http_status'] == 404)
                    and not result['mutation_uncertain'] and not boundary.mutations
                    and not exchange.refresh_pending and not exchange.phase_active and not auth.uncertain)
                if safe_close:
                    if recovery_enabled:
                        recovery_lease()
                    sequence_guard.complete(sequence, active_hash)
                    channel.deadline = lease_end
                    closing = channel.receive(kinds={'request'})
                    close_payload = sequence_guard.accept(closing)
                    if recovery_enabled:
                        recovery_lease()
                    need(close_payload['operation'] == 'close' and close_payload['arguments'] == {},
                         'readonly_failure_close_only')
                    need(time.time() < close_payload['deadline_epoch'] <= deadline_epoch,
                         'readonly_failure_close_deadline')
                    channel.deadline = min(lease_end, time.monotonic() + min(close_payload['max_seconds'],
                        close_payload['deadline_epoch'] - time.time()))
                    channel.send('response', {'operation': 'close', 'result': {'closed': True}},
                        sequence=closing['sequence'], request_sha256=closing['request_sha256'])
                    sequence_guard.complete(closing['sequence'], closing['request_sha256'])
                    return 0
            except BaseException:
                pass
        sequence_guard.fail()
        return 2
    finally:
        if provider is not None:
            provider.close()
        else:
            auth.close()


def _pinned_module(name, path, digest):
    need(type(digest) is str and HEX.fullmatch(digest), 'worker_bootstrap_pin_unbound')
    path = Path(path).absolute()
    for component in reversed((path, *path.parents)):
        info = component.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'worker_bootstrap_reparse')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= 1024 * 1024,
         'worker_bootstrap_source_file')
    with path.open('rb') as source:
        raw = source.read(1024 * 1024 + 1)
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == digest,
         'worker_bootstrap_source_hash')
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def main(argv=None):
    """Only the native supervisor invokes this source-verified worker CLI."""
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha', required=True)
    parser.add_argument('--nonce', required=True)
    parser.add_argument('--deadline-epoch', type=float, required=True)
    parser.add_argument('--max-seconds', type=float, required=True)
    args = parser.parse_args(argv)
    # Capture the original lease before bootstrap, never renew it after imports.
    started = time.monotonic()
    reader = writer = None
    try:
        need(os.name == 'nt', 'native_windows_required')
        import msvcrt
        for fd in (0, 1, 2):
            msvcrt.setmode(fd, os.O_BINARY)
        need(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1
             and sys.flags.ignore_environment == 1, 'native_isolated_source_execution_required')
        need(math.isfinite(args.deadline_epoch) and math.isfinite(args.max_seconds)
             and 0 < args.max_seconds <= 43200 and args.deadline_epoch > time.time(),
             'native_worker_lease')
        need(HEX.fullmatch(args.nonce) and HEX.fullmatch(args.config_sha), 'native_worker_binding')
        deadline = started + min(args.max_seconds, args.deadline_epoch - time.time())
        directory = Path(__file__).absolute().parent
        win = _pinned_module('win_runtime', directory / 'win_runtime.py', WIN_RUNTIME_SHA256)
        win.require_worker_job(args.nonce)
        config = _pinned_module('native_config', directory / 'native_config.py', NATIVE_CONFIG_SHA256)
        runtime = config.load_runtime(args.config, args.config_sha)
        runtime.verify_runtime()
        need(Path(runtime.worker_path) == Path(__file__).absolute(), 'native_worker_source_identity')
        # Native config checked the complete legacy or recovery source closure.
        # Compile these two leaf modules from those same reviewed descriptors.
        def leaf(name):
            descriptor = runtime.document['sources'][name + '.py']
            return _pinned_module(name, directory / (name + '.py'), descriptor['sha256'])
        protocol, auth = leaf('protocol'), leaf('native_auth')
        with auth.isolate_sdk_output() as (reader, writer):
            channel = protocol.FramedIO(reader, writer, nonce=args.nonce, deadline=deadline)
            return run_worker(runtime, runtime.versions, channel, protocol, auth,
                deadline_epoch=args.deadline_epoch, max_seconds=args.max_seconds,
                monotonic_deadline=deadline)
    except BaseException:
        # Bootstrap failures have no authenticated protocol. Do not expose paths,
        # exceptions or the inherited environment via stderr/stdout diagnostics.
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

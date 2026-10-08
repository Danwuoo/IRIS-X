"""One exact private E12 RUN, with offline wire review and durable reservations.

Importing this module never authenticates or contacts Kaggle. `prepare` uses an
explicit dummy token and intercepts the genuine SDK HTTP request before send.
Only explicit observe/publish/status/retrieve commands use official stored auth.
No credential values, headers, signed URLs, or provider error text are retained.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from tools.nvarc_e12_admission import canonical, parse, require
from tools.stage4_provider_evidence import execution_source_digest, normalize_quota
from tools.stage4_execution_ledger import canonical as evidence_canonical

RUN_ID = 'stage4-e12-probe-prefix-20261008-003'
REF = 'danielwuu/stage4-e10-probe-20261006-001'
OWNER, SLUG = REF.split('/')
KERNEL_ID, PREVIOUS_VERSION, VERSION = 137327571, 10, 11
API = 'https://api.kaggle.com/v1/kernels.KernelsApiService/'
SAVE_URL = API + 'SaveKernel'
PUBLIC_URL = 'https://www.kaggle.com/code/' + REF
AUTH_REF = 'Sentinel_f5427e757f54819193ef59565b8c7b23'
MAX_JSON = 1024 * 1024
MAX_NOTEBOOK = 64 * 1024 * 1024
MAX_OUTPUT = 261 * 1024 * 1024
TERMINAL = {'COMPLETE', 'ERROR', 'CANCEL_ACKNOWLEDGED'}
FORMAT = 'irisx/e12-single-run-transport-v1'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'regular non-symlink path required')
    return path


def read_bytes(path, limit=MAX_NOTEBOOK):
    path = safe_path(path)
    require(path.is_file() and path.stat().st_size <= limit, 'bounded regular file required')
    with path.open('rb') as stream:
        body = stream.read(limit + 1)
    require(len(body) <= limit, 'file byte ceiling exceeded')
    return body


def read(path, limit=MAX_NOTEBOOK):
    return parse(read_bytes(path, limit))


def atomic_bytes(path, body, *, exclusive=False):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
        if exclusive:
            # Publish complete bytes atomically without replacing any prior
            # claim/receipt. A crash before publication leaves no partial file.
            os.link(temporary, path, follow_symlinks=False)
            os.unlink(temporary)
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(path, value, *, exclusive=False):
    atomic_bytes(path, canonical(value), exclusive=exclusive)


@contextmanager
def locked(journal):
    import fcntl
    path = safe_path(Path(journal) / 'controller.lock')
    with path.open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def package_info(package, *, current=True):
    from tools.stage_nvarc_e12_prefix_probe import preflight
    package = safe_path(package)
    checked = preflight(package, current_resource=current)
    plan = read(package / 'runtime/plan.json')
    require(plan['run_id'] == RUN_ID and plan['kernel_execution_type'] == 'RUN'
            and plan['agent_execution_authorized'] is True and plan['publication_authorized'] is True
            and plan['expected_notebook_version'] == VERSION
            and plan['expected_previous_version'] == PREVIOUS_VERSION
            and plan['notebook_numeric_id'] == KERNEL_ID
            and plan['maximum_notebook_wall_seconds'] == 3600,
            'exact admitted E12 run003 plan required')
    notebook = read_bytes(package / 'kernel/notebook.ipynb')
    parse(notebook)
    return plan, read(package / 'kernel/kernel-metadata.json'), notebook, {
        'package_manifest_sha256': sha(read_bytes(package / 'package-manifest.json')),
        'plan_sha256': sha(read_bytes(package / 'runtime/plan.json')),
        'notebook_sha256': sha(notebook),
        'source_digest': execution_source_digest(parse(notebook)),
        'offline_package_verified': checked['offline_package_verified']}


def request_fields(package, *, current=True):
    plan, meta, notebook, bindings = package_info(package, current=current)
    require(meta['id'] == REF and meta['title'] == SLUG and meta['is_private'] is True
            and meta['enable_internet'] is False and meta['enable_gpu'] is True
            and meta['machine_shape'] == 'NvidiaL4' and meta['dataset_sources'] == []
            and meta['competition_sources'] == ['arc-prize-2026-arc-agi-2']
            and meta['kernel_sources'] == ['sorokin/pip-install-unsloth-flash-patch/2']
            and meta['model_sources'] == ['sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'],
            'exact retained private E12 source mounts required')
    fields = dict(id=KERNEL_ID, slug=REF, new_title=SLUG, text=notebook.decode('utf-8'),
        language='python', kernel_type='notebook', is_private=True, enable_gpu=True,
        enable_tpu=False, enable_internet=False, session_timeout_seconds=3600,
        dataset_data_sources=[], competition_data_sources=meta['competition_sources'],
        kernel_data_sources=meta['kernel_sources'], model_data_sources=meta['model_sources'],
        machine_shape='NvidiaL4', docker_image=meta['docker_image'],
        docker_image_pinning_type=meta['docker_image_pinning_type'])
    # This independently spelled wire expectation must match SDK serialization.
    wire = dict(id=KERNEL_ID, slug=REF, newTitle=SLUG, text=notebook.decode('utf-8'),
        language='python', kernelType='notebook', isPrivate=True, enableGpu=True,
        enableTpu=False, enableInternet=False, sessionTimeoutSeconds=3600,
        competitionDataSources=meta['competition_sources'], kernelDataSources=meta['kernel_sources'],
        modelDataSources=meta['model_sources'], machineShape='NvidiaL4',
        dockerImage=meta['docker_image'], dockerImagePinningType=meta['docker_image_pinning_type'],
        kernelExecutionType='SAVE_AND_RUN_ALL')
    return fields, wire, bindings


def request(package, *, current=True):
    from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
    from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
    fields, wire, bindings = request_fields(package, current=current)
    req = ApiSaveKernelRequest()
    for key, value in fields.items():
        setattr(req, key, value)
    req.kernel_execution_type = KernelExecutionType.SAVE_AND_RUN_ALL
    require(canonical(req.to_dict()) == canonical(wire), 'genuine SDK wire differs from closed independent expectation')
    return req, wire, bindings


def wire_body(prepared, expected):
    require(prepared.method == 'POST' and prepared.url == SAVE_URL, 'one exact SaveKernel endpoint required')
    body = prepared.body
    body = body.encode('utf-8') if type(body) is str else body
    require(type(body) is bytes and len(body) <= MAX_NOTEBOOK * 2, 'bounded prepared request body required')
    require(canonical(parse(body)) == canonical(expected), 'actual prepared request differs from reviewed closed wire')
    require(sha(parse(body)['text'].encode()) == sha(expected['text'].encode()), 'inner notebook bytes differ')
    return body


class CapturedRequest(BaseException):
    pass


def capture_prepared(req, wire):
    from kagglesdk import KaggleClient
    from kagglesdk.kaggle_env import KaggleEnv
    captured = []
    # Explicit sentinel avoids stored-credential discovery. Production endpoint
    # plus an intercepted Session.send establishes actual SDK serialization.
    with KaggleClient(env=KaggleEnv.PROD, verbose=False, api_token='OFFLINE-NOT-A-CREDENTIAL') as client:
        session = client.http_client()._session
        def stop(prepared, **kwargs):
            require(not captured, 'exactly one prepared offline request required')
            captured.append(wire_body(prepared, wire))
            raise CapturedRequest()
        session.send = stop
        try:
            client.kernels.kernels_api_client.save_kernel(req)
        except CapturedRequest:
            pass
    require(len(captured) == 1, 'SDK did not reach actual HTTP interception')
    return captured[0]


def prepare(package, journal, previous_notebook):
    journal = safe_path(journal)
    require(not journal.exists(), 'new immutable transport journal required')
    require(not claim_path().exists(), 'E12 publication identity already reserved')
    req, wire, bindings = request(package)
    previous = read_bytes(previous_notebook)
    previous_digest = execution_source_digest(parse(previous))
    body = capture_prepared(req, wire)
    journal.mkdir(parents=True)
    atomic_bytes(journal / 'previous-notebook.ipynb', previous, exclusive=True)
    atomic_bytes(journal / 'prepared-request.body', body, exclusive=True)
    write(journal / 'save-request.json', wire, exclusive=True)
    value = dict(format=FORMAT, run_id=RUN_ID, ref=REF, kernel_id=KERNEL_ID,
        previous_version=PREVIOUS_VERSION, expected_version=VERSION,
        bindings=bindings, previous_source_digest=previous_digest,
        previous_notebook_sha256=sha(previous), request_sha256=sha(canonical(wire)),
        prepared_body_sha256=sha(body), transport_sha256=sha(read_bytes(Path(__file__))),
        prepared_at=utc(), publication_reserved=0, status_checks_reserved=0,
        retrieval_reserved=0, state='prepared-not-sent', events=[])
    write(journal / 'ledger.json', value, exclusive=True)
    return review_binding(value)


def review_binding(ledger):
    return dict(format='irisx/e12-run-transport-review-v1', run_id=RUN_ID,
        ref=REF, kernel_id=KERNEL_ID, expected_version=VERSION,
        **ledger['bindings'], previous_source_digest=ledger['previous_source_digest'],
        previous_notebook_sha256=ledger['previous_notebook_sha256'],
        request_sha256=ledger['request_sha256'], prepared_body_sha256=ledger['prepared_body_sha256'],
        transport_sha256=ledger['transport_sha256'])


def verify_review(ledger, path):
    value = read(path, MAX_JSON)
    expected = review_binding(ledger)
    require(set(value) == set(expected) | {'verdict', 'reviewer', 'reviewed_at'}
            and all(value.get(k) == v and type(value.get(k)) is type(v) for k, v in expected.items())
            and value['verdict'] == 'PASS' and type(value['reviewer']) is str and value['reviewer'].strip()
            and type(value['reviewed_at']) is str and value['reviewed_at'],
            'independent PASS review must bind exact package and actual prepared SDK wire')
    return sha(read_bytes(path))


def load_bound(package, journal, *, current=False):
    journal = safe_path(journal)
    ledger = read(journal / 'ledger.json', MAX_JSON)
    req, wire, bindings = request(package, current=current)
    require(ledger['format'] == FORMAT and ledger['run_id'] == RUN_ID and ledger['ref'] == REF
            and ledger['kernel_id'] == KERNEL_ID and ledger['expected_version'] == VERSION
            and ledger['previous_version'] == PREVIOUS_VERSION and ledger['bindings'] == bindings
            and ledger['transport_sha256'] == sha(read_bytes(Path(__file__)))
            and ledger['request_sha256'] == sha(canonical(wire))
            and canonical(read(journal / 'save-request.json')) == canonical(wire)
            and ledger['prepared_body_sha256'] == sha(read_bytes(journal / 'prepared-request.body', MAX_NOTEBOOK * 2))
            and ledger['previous_notebook_sha256'] == sha(read_bytes(journal / 'previous-notebook.ipynb')),
            'immutable package, implementation or journal binding changed')
    require(canonical(parse(read_bytes(journal / 'prepared-request.body', MAX_NOTEBOOK * 2))) == canonical(wire),
            'retained prepared request changed')
    return ledger, req, wire


def claim_path():
    return ROOT / '.irisx/e12-run-publication' / (RUN_ID + '-reservation.json')


def official_client():
    # The official CLI owns stored credential loading and refresh. Do not read,
    # copy, print, serialize or extract any credential through this controller.
    import kaggle
    api = kaggle.api
    require(api.config_values.get(api.CONFIG_NAME_USER) == OWNER and api._authenticated is True,
            'official CLI must authenticate the exact owner first')
    return api.build_kaggle_client()


def bounded_session(client):
    http = client.http_client(); http._init_session()
    session = http._session
    require(all(adapter.max_retries.total == 0 for adapter in session.adapters.values()),
            'HTTP retries must be disabled')
    return session


def sdk_request(name, **fields):
    from kagglesdk.kernels.types import kernels_api_service
    req = getattr(kernels_api_service, name)()
    for key, value in fields.items():
        setattr(req, key, value)
    return req


def primary_call(client, method, req, destination, *, limit=MAX_JSON):
    """Capture original bounded response bytes with one exact no-redirect send."""
    session = bounded_session(client); original = session.send; count = 0
    endpoint = API + ''.join(part.capitalize() for part in method.split('_'))
    expected = canonical(req.to_dict())
    def send(prepared, **kwargs):
        nonlocal count
        require(count == 0 and prepared.method == 'POST' and prepared.url == endpoint
                and canonical(parse(prepared.body)) == expected, 'one exact provider read required')
        count += 1
        kwargs.update(timeout=(15, 120), allow_redirects=False, stream=True)
        response = original(prepared, **kwargs)
        body = bytearray()
        try:
            for chunk in response.iter_content(65536):
                body.extend(chunk); require(len(body) <= limit, 'provider JSON response byte ceiling exceeded')
            atomic_bytes(destination, bytes(body), exclusive=True)
            response._content = bytes(body); response._content_consumed = True
            require(response.status_code == 200, 'provider read failed; retained response, no alternate endpoint')
            parse(bytes(body))
            return response
        finally:
            response.close()
    session.send = send
    try:
        result = getattr(client.kernels.kernels_api_client, method)(req)
        require(count == 1, 'one provider response required')
        return result
    finally:
        session.send = original


def current_source(client, package, destination, expected_version, expected_digest):
    req = sdk_request('ApiGetKernelRequest', user_name=OWNER, kernel_slug=SLUG)
    result = primary_call(client, 'get_kernel', req, destination, limit=MAX_NOTEBOOK * 2)
    meta = result.metadata
    _, expected, _, _ = package_info(package, current=False)
    checks = dict(id=KERNEL_ID, ref=REF, title=SLUG, current_version_number=expected_version,
        is_private=True, enable_internet=False, enable_gpu=True, enable_tpu=False,
        language='python', kernel_type='notebook', machine_shape='NvidiaL4',
        docker_image=expected['docker_image'], dataset_data_sources=expected['dataset_sources'],
        kernel_data_sources=expected['kernel_sources'], model_data_sources=expected['model_sources'],
        competition_data_sources=expected['competition_sources'])
    actual = {key: getattr(meta, key) for key in checks}
    normalized = dict(actual)
    normalizations = []
    # Exact surviving v9 evidence records these two provider read projections.
    # Only this literal allowlist is admitted; outbound requests keep all pins.
    if actual['kernel_data_sources'] == ['sorokin/pip-install-unsloth-flash-patch']:
        normalized['kernel_data_sources'] = ['sorokin/pip-install-unsloth-flash-patch/2']
        normalizations.append('known provider dependency version suffix omitted')
    if actual['model_data_sources'] == ['sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1']:
        normalized['model_data_sources'] = ['sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1']
        normalizations.append('known provider Transformers framework capitalization')
    require(all(type(normalized[k]) is type(v) and normalized[k] == v for k, v in checks.items()),
            'fresh current notebook identity/version/settings/source pins differ')
    notebook = parse(result.blob.source)
    require(execution_source_digest(notebook) == expected_digest, 'fresh provider executable source differs')
    return dict(version=expected_version, source_digest=expected_digest, observed_at=utc(),
                provider_read_normalizations=normalizations, dependency_version_echo_verified=False,
                dependency_selected_bytes_verified=False, settings_sha256=sha(canonical(checks)), primary_sha256=sha(read_bytes(destination, MAX_NOTEBOOK * 2)))


def quota_snapshot(client, destination):
    req = sdk_request('ApiGetAcceleratorQuotaStatisticsRequest')
    result = primary_call(client, 'get_accelerator_quota_statistics', req, destination)
    typed = dict(gpu_used_seconds=result.gpu_quota.time_used.total_seconds(),
        gpu_reserved_seconds=result.gpu_quota.time_reserved.total_seconds(),
        gpu_total_seconds=result.gpu_quota.total_time_allowed.total_seconds(),
        gpu_pay_to_scale_enabled=result.gpu_quota.is_pay_to_scale_enabled)
    body = read_bytes(destination, MAX_JSON)
    value = normalize_quota(body, typed, account=OWNER, observed_at=utc())
    require(value['remaining_free_seconds'] > 0 and value['reserved_seconds'] == 0,
            'actual positive free quota and no conflicting reservation required')
    atomic_bytes(destination.with_suffix('.typed.json'), evidence_canonical(typed), exclusive=True)
    write(destination.with_suffix('.normalized.json'), value, exclusive=True)
    return value


def observe_quota(destination):
    destination = safe_path(destination)
    require(not destination.exists(), 'fresh quota evidence path required')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with official_client() as client:
        return quota_snapshot(client, destination)


def receipt_is_accepted(raw, typed):
    allowed = {'ref', 'url', 'versionNumber', 'kernelId', 'error', 'invalidTags',
        'invalidDatasetSources', 'invalidKernelSources', 'invalidCompetitionSources', 'invalidModelSources'}
    require(type(raw) is dict and set(raw) <= allowed, 'closed SaveKernel receipt required')
    required = dict(url=PUBLIC_URL, versionNumber=VERSION, kernelId=KERNEL_ID)
    require(type(raw.get('ref')) is str and raw['ref'] in {REF, '/code/' + REF},
            'one exact documented provider receipt reference required')
    require(all(type(raw.get(k)) is type(v) and raw[k] == v for k, v in required.items()),
            'strong accepted receipt must match exact destination and new version')
    require(not raw.get('error') and not any(raw.get(k) for k in allowed if k.startswith('invalid')),
            'provider rejected a source or save')
    require(typed.ref == raw['ref'] and typed.url == PUBLIC_URL and type(typed.version_number) is int
            and typed.version_number == VERSION and typed.kernel_id == KERNEL_ID and not typed.error,
            'raw and typed SaveKernel receipt disagree')
    return True


def publish(package, journal, review):
    journal = safe_path(journal)
    with locked(journal):
        ledger, req, wire = load_bound(package, journal, current=True)
        require(ledger['publication_reserved'] == 0 and ledger['state'] == 'prepared-not-sent'
                and not claim_path().exists(), 'single E12 publication already reserved; no retry')
        review_sha = verify_review(ledger, review)
        with official_client() as client:
            # Read-only failures do not consume the sole mutation. Each failed
            # precheck remains retained; a later retry needs a fresh journal.
            before = current_source(client, package, journal / 'pre-send-current.json', PREVIOUS_VERSION,
                                    ledger['previous_source_digest'])
            fresh = quota_snapshot(client, journal / 'pre-send-quota.json')
            plan = read(Path(package) / 'runtime/plan.json')
            admission = plan['resource_admission']
            # Fresh evidence is independent of the reviewed snapshot; it may
            # decrease, but never bypass free-only or the selected quota policy.
            from tools.nvarc_e12_admission import validate_resource_snapshot
            validate_resource_snapshot(fresh, current=True)
            require(admission['quota_policy'] == 'owner-positive-free-quota-waiver-v1'
                    or fresh['remaining_free_seconds'] >= 14400, 'fresh conservative quota is insufficient')
            event = dict(action='SaveKernel', reserved_at=utc(), sends=0, review_sha256=review_sha,
                current_source=before, fresh_quota_sha256=sha(canonical(fresh)), outcome='reserved-unsent')
            write(claim_path(), dict(run_id=RUN_ID, ref=REF, expected_version=VERSION,
                package_manifest_sha256=ledger['bindings']['package_manifest_sha256'],
                prepared_body_sha256=ledger['prepared_body_sha256'], reserved_at=event['reserved_at']), exclusive=True)
            ledger['publication_reserved'] = 1; ledger['state'] = 'reserved-unknown'; ledger['events'].append(event)
            write(journal / 'ledger.json', ledger)
            session = bounded_session(client); original = session.send
            def send(prepared, **kwargs):
                body = wire_body(prepared, wire)
                validate_resource_snapshot(fresh, current=True)
                require((datetime.now(timezone.utc) - datetime.fromisoformat(before['observed_at'])).total_seconds() <= 300,
                        'current notebook observation expired before send')
                require(sha(body) == ledger['prepared_body_sha256'] and event['sends'] == 0,
                        'actual wire changed or duplicate send attempted')
                event['sends'] = 1; event['outcome'] = 'send-started-unknown'
                write(journal / 'ledger.json', ledger)
                kwargs.update(timeout=(15, 120), allow_redirects=False, stream=True)
                response = original(prepared, **kwargs)
                retained = bytearray()
                try:
                    for chunk in response.iter_content(65536):
                        retained.extend(chunk); require(len(retained) <= MAX_JSON, 'bounded SaveKernel raw receipt required')
                    atomic_bytes(journal / 'save-receipt.raw.json', bytes(retained), exclusive=True)
                    event['raw_receipt_sha256'] = sha(bytes(retained)); event['http_status'] = response.status_code
                    write(journal / 'ledger.json', ledger)
                    response._content = bytes(retained); response._content_consumed = True
                    require(response.status_code == 200, 'SaveKernel failed; identity frozen')
                    parse(bytes(retained))
                    return response
                finally:
                    response.close()
            session.send = send
            try:
                response = client.kernels.kernels_api_client.save_kernel(req)
                raw = read(journal / 'save-receipt.raw.json', MAX_JSON)
                receipt_is_accepted(raw, response)
                require(event['sends'] == 1, 'one completed SaveKernel send required')
                write(journal / 'save-receipt.typed.json', response.to_dict(), exclusive=True)
                write(journal / 'save-receipt.identity.json', dict(ref=REF, provider_ref=raw['ref'],
                    url=PUBLIC_URL, version=VERSION, kernel_id=KERNEL_ID,
                    raw_receipt_sha256=event['raw_receipt_sha256']), exclusive=True)
                ledger.update(state='accepted-runtime-unobserved', accepted=True, provider_version=VERSION)
                event.update(outcome='accepted', completed_at=utc())
                write(journal / 'ledger.json', ledger)
                return dict(accepted=True, ref=REF, version=VERSION, execution_type='SAVE_AND_RUN_ALL',
                    gpu_execution_verified=False, session_timeout_seconds_requested=3600)
            except BaseException as error:
                ledger['state'] = 'frozen-uncertain-no-retry'; ledger['accepted'] = False
                event.update(outcome='failed-or-uncertain-no-retry', error_type=type(error).__name__, completed_at=utc())
                write(journal / 'ledger.json', ledger)
                raise RuntimeError('E12 publication failed or is uncertain; identity frozen; no duplicate send') from None
            finally:
                session.send = original


def status(package, journal):
    journal = safe_path(journal)
    with locked(journal):
        ledger, _, _ = load_bound(package, journal)
        require(ledger.get('accepted') is True and ledger['retrieval_reserved'] == 0,
                'accepted unretrieved E12 version required')
        if ledger.get('last_status_at'):
            require((datetime.now(timezone.utc) - datetime.fromisoformat(ledger['last_status_at'])).total_seconds() >= 60,
                    'status observations must be at least 60 seconds apart')
        require(ledger['status_checks_reserved'] < 180, 'status observation budget exhausted; continue only after review')
        index = ledger['status_checks_reserved']; ledger['status_checks_reserved'] += 1
        ledger['last_status_at'] = utc()
        event = dict(action='status', index=index, reserved_at=utc(), state='reserved')
        ledger['events'].append(event); write(journal / 'ledger.json', ledger)
        try:
            with official_client() as client:
                before = current_source(client, package, journal / f'status-{index:03d}-before.json', VERSION,
                                        ledger['bindings']['source_digest'])
                req = sdk_request('ApiGetKernelSessionStatusRequest', user_name=OWNER, kernel_slug=SLUG)
                response = primary_call(client, 'get_kernel_session_status', req, journal / f'status-{index:03d}.json')
                after = current_source(client, package, journal / f'status-{index:03d}-after.json', VERSION,
                                       ledger['bindings']['source_digest'])
            require(all(before[k] == after[k] for k in ('version', 'source_digest', 'settings_sha256')),
                    'current source changed around status observation')
            state = response.status.name
            require(state in TERMINAL | {'QUEUED', 'RUNNING', 'CANCEL_REQUESTED', 'NEW_SCRIPT'}, 'unknown provider state')
            ledger.update(last_status=state, terminal_observed=state in TERMINAL)
            event.update(state='observed', provider_status=state, completed_at=utc())
            write(journal / 'ledger.json', ledger)
            return dict(ref=REF, version=VERSION, status=state, terminal=state in TERMINAL,
                        runtime_output_verified=False)
        except BaseException as error:
            event.update(state='failed-read', error_type=type(error).__name__)
            write(journal / 'ledger.json', ledger)
            raise RuntimeError('E12 status read failed; no alternate endpoint attempted') from None


class RawOutputResponseCaptured(BaseException):
    """Stop the official SDK before its JSON parser sees an empty redirect."""


def capture_output_response(client, req, checkpoint):
    session = bounded_session(client); original = session.send; captured = []
    def send(prepared, **kwargs):
        require(not captured and prepared.method == 'POST'
                and prepared.url == API + 'DownloadKernelOutput'
                and canonical(parse(prepared.body)) == canonical(req.to_dict()),
                'one exact-version file request required')
        checkpoint()
        kwargs.update(timeout=(15, 120), allow_redirects=False, stream=True)
        captured.append(original(prepared, **kwargs))
        raise RawOutputResponseCaptured()
    session.send = send
    try:
        try:
            client.kernels.kernels_api_client.download_kernel_output(req)
        except RawOutputResponseCaptured:
            pass
    finally:
        session.send = original
    require(len(captured) == 1, 'one actual raw output response required')
    return captured[0]


def retrieve(package, journal):
    """One exact-version delivery file, streamed once; no listing or blind retry."""
    journal = safe_path(journal)
    with locked(journal):
        ledger, _, _ = load_bound(package, journal)
        require(ledger.get('accepted') is True and ledger.get('terminal_observed') is True
                and ledger['retrieval_reserved'] == 0, 'one terminal retrieval requires accepted exact-version status')
        event = dict(action='terminal-delivery', reserved_at=utc(), sends=0, downloads=0, state='reserved')
        ledger['retrieval_reserved'] = 1; ledger['events'].append(event); write(journal / 'ledger.json', ledger)
        destination = journal / 'retrieved'; destination.mkdir()
        filename = RUN_ID + '-delivery.zip'; started = time.monotonic()
        try:
            with official_client() as client:
                current_source(client, package, journal / 'retrieve-before.json', VERSION,
                               ledger['bindings']['source_digest'])
                req = sdk_request('ApiDownloadKernelOutputRequest', owner_slug=OWNER, kernel_slug=SLUG,
                                  version_number=VERSION, file_path=filename)
                def checkpoint():
                    require(event['sends'] == 0, 'one exact-version delivery request only')
                    event['sends'] = 1; write(journal / 'ledger.json', ledger)
                response = capture_output_response(client, req, checkpoint)
                with response:
                    event['http_status'] = response.status_code
                    write(journal / 'ledger.json', ledger)
                    require(response.status_code in (301, 302, 303, 307, 308), 'one supported output redirect required')
                    target = response.headers.get('Location', '')
                    parts = urlsplit(target)
                    ids = re.findall(r'/(?:kf|kernels)/([0-9]+)/', parts.path)
                    require(parts.scheme == 'https' and parts.hostname == 'www.kaggleusercontent.com'
                            and parts.port in (None, 443) and parts.username is None and parts.password is None
                            and len(ids) == 1, 'official output host and script-version path required')
                # A new anonymous HTTP session does not forward API credentials.
                import requests
                event['downloads'] = 1; event['download_script_version_id'] = int(ids[0])
                write(journal / 'ledger.json', ledger)
                with requests.Session() as download_session:
                    download_session.auth = None
                    # Explicit no-op auth suppresses ~/.netrc credential discovery.
                    with download_session.get(target, auth=lambda prepared: prepared, stream=True, timeout=(15, 120),
                                              allow_redirects=False) as download:
                        require(download.status_code == 200, 'output download failed; no redirect chain or retry')
                        size = 0; digest = hashlib.sha256(); path = destination / filename
                        with path.open('xb') as stream:
                            for chunk in download.iter_content(1024 * 1024):
                                size += len(chunk)
                                require(size <= MAX_OUTPUT and time.monotonic() - started <= 900,
                                        'output byte or wall ceiling exceeded')
                                stream.write(chunk); digest.update(chunk)
                            stream.flush(); os.fsync(stream.fileno())
                current_source(client, package, journal / 'retrieve-after.json', VERSION,
                               ledger['bindings']['source_digest'])
            from tools.nvarc_e12_delivery_envelope import verify_envelope
            proof = verify_envelope(destination, run_id=RUN_ID, plan_sha256=ledger['bindings']['plan_sha256'])
            write(journal / 'delivery-verification.json', proof, exclusive=True)
            event.update(state='verified', bytes=size, sha256=digest.hexdigest(), completed_at=utc())
            ledger['state'] = 'terminal-delivery-verified'; write(journal / 'ledger.json', ledger)
            return dict(ref=REF, version=VERSION, filename=filename, bytes=size, sha256=digest.hexdigest(),
                        delivery_envelope_verified=True, model_quality_claim=False)
        except BaseException as error:
            event.update(state='failed-or-partial-no-repeat', error_type=type(error).__name__, completed_at=utc())
            write(journal / 'ledger.json', ledger)
            raise RuntimeError('terminal output retrieval failed or is partial; retained evidence; no repeat') from None



def terminal_logs(package, journal):
    """One bounded terminal log read, including when a killed run has no ZIP.

    The supported current-output response is bracketed by exact version/source
    reads. File URLs are transient only; no file downloads or pagination follow.
    """
    journal = safe_path(journal)
    with locked(journal):
        ledger, _, _ = load_bound(package, journal)
        require(ledger.get('accepted') is True and ledger.get('terminal_observed') is True
                and ledger.get('log_retrieval_reserved', 0) == 0,
                'one terminal log retrieval requires accepted exact-version status')
        event = dict(action='terminal-log', reserved_at=utc(), sends=0, state='reserved')
        ledger['log_retrieval_reserved'] = 1; ledger['events'].append(event)
        write(journal / 'ledger.json', ledger)
        try:
            with official_client() as client:
                before = current_source(client, package, journal / 'logs-before.json', VERSION,
                                        ledger['bindings']['source_digest'])
                req = sdk_request('ApiListKernelSessionOutputRequest', user_name=OWNER,
                                  kernel_slug=SLUG, page_size=1)
                session = bounded_session(client); original = session.send
                captured = []
                def send(prepared, **kwargs):
                    require(event['sends'] == 0 and prepared.method == 'POST'
                            and prepared.url == API + 'ListKernelSessionOutput'
                            and canonical(parse(prepared.body)) == canonical(req.to_dict()),
                            'one exact bounded terminal log request required')
                    event['sends'] = 1; write(journal / 'ledger.json', ledger)
                    kwargs.update(timeout=(15, 120), allow_redirects=False, stream=True)
                    response = original(prepared, **kwargs)
                    body = bytearray()
                    try:
                        for chunk in response.iter_content(65536):
                            body.extend(chunk); require(len(body) <= 9 * MAX_JSON, 'terminal log response ceiling exceeded')
                        require(response.status_code == 200, 'terminal log read failed')
                        raw = parse(bytes(body)); log = raw.get('log', '')
                        require(type(log) is str and len(log.encode()) <= 8 * MAX_JSON,
                                'bounded primary provider log string required')
                        captured.append(log)
                        atomic_bytes(journal / 'provider.log', log.encode(), exclusive=True)
                        event.update(primary_response_sha256=sha(bytes(body)), log_sha256=sha(log.encode()),
                                     log_bytes=len(log.encode()), file_urls_retained=False)
                        write(journal / 'ledger.json', ledger)
                        response._content = bytes(body); response._content_consumed = True
                        return response
                    finally:
                        response.close()
                session.send = send
                try:
                    result = client.kernels.kernels_api_client.list_kernel_session_output(req)
                finally:
                    session.send = original
                require(len(captured) == 1 and result.log == captured[0], 'primary and typed terminal logs differ')
                after = current_source(client, package, journal / 'logs-after.json', VERSION,
                                       ledger['bindings']['source_digest'])
                require(all(before[k] == after[k] for k in ('version', 'source_digest', 'settings_sha256')),
                        'source changed around terminal log observation')
            event.update(state='retained', completed_at=utc()); write(journal / 'ledger.json', ledger)
            return dict(ref=REF, version=VERSION, log_retained=True, log_bytes=event['log_bytes'],
                        log_sha256=event['log_sha256'], delivery_envelope_verified=ledger['state']=='terminal-delivery-verified')
        except BaseException as error:
            event.update(state='failed-no-repeat', error_type=type(error).__name__, completed_at=utc())
            write(journal / 'ledger.json', ledger)
            raise RuntimeError('terminal log retrieval failed; retained evidence; no repeat') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'observe-quota', 'publish', 'status', 'retrieve', 'terminal-logs'))
    parser.add_argument('--package', type=Path)
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--previous-notebook', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'observe-quota':
        require(args.output is not None, 'new output evidence path required')
        result = observe_quota(args.output)
    else:
        require(args.package is not None and args.journal is not None, 'package and journal required')
        if args.action == 'prepare':
            require(args.previous_notebook is not None, 'independently retained previous v10 notebook required')
            result = prepare(args.package, args.journal, args.previous_notebook)
        elif args.action == 'publish':
            require(args.review is not None, 'independent actual-wire review required')
            result = publish(args.package, args.journal, args.review)
        else:
            result = globals()[args.action.replace('-', '_')](args.package, args.journal)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()

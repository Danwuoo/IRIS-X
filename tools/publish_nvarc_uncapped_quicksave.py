"""One new private uncapped notebook QUICK_SAVE, never a runtime operation.

`prepare` is offline: the installed official SDK uses an explicit dummy token,
and its actual Session.send request is intercepted before any network I/O.
Only explicit `publish` and `verify-source` use existing official stored auth.
HTTP/file safety bounds here do not impose notebook runtime or artifact caps.
No API credentials, header values, error text, or signed URLs are printed.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from tools.stage4_provider_evidence import execution_source_digest

RUN_ID = 'stage4-uncapped-20261008-001'
REF = 'danielwuu/stage4-uncapped-ttt128-20261008-3baff209a1'
OWNER, SLUG = REF.split('/')
VERSION = 1
# Exclusion only: this ID is never used as a request target.
PRESERVED_KERNEL_IDS = frozenset({137327571})
PRIVATE_ANCHOR_REF = 'danielwuu/stage4-e10-probe-20261006-001'
API = 'https://api.kaggle.com/v1/kernels.KernelsApiService/'
SAVE_URL, SOURCE_URL = API + 'SaveKernel', API + 'GetKernel'
LIST_URL = API + 'ListKernels'
NEWNESS_PROOFS = ('source-404', 'complete-own-list')
OWN_LIST_PAGE_SIZE, MAX_OWN_LIST_PAGES = 100, 100
REDACTED_OWN_LIST_ROW = {'title': '[Private Notebook]', 'lastRunTime': '2010-04-01T00:00:00Z'}
PUBLIC_URL = 'https://www.kaggle.com/code/' + REF
FORMAT = 'irisx/new-uncapped-quicksave-transport-v1'
MAX_JSON, MAX_NOTEBOOK = 1024 * 1024, 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def parse(body):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    value = json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('finite JSON required')))
    canonical(value)
    return value


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
    require(path.is_file() and path.stat().st_size <= limit, 'bounded regular transport file required')
    with path.open('rb') as stream:
        body = stream.read(limit + 1)
    require(len(body) <= limit, 'transport file byte ceiling exceeded')
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


def package_info(package):
    from tools.stage_nvarc_uncapped_notebook import preflight
    package = safe_path(package)
    checked = preflight(package, publication=True)
    plan = read(package / 'runtime/plan.json')
    require(plan.get('run_id') == RUN_ID and plan.get('kernel_execution_type') == 'QUICK_SAVE'
        and plan.get('owner_editor_only') is True and plan.get('agent_execution_authorized') is False
        and plan.get('publication_authorized') is True
        and plan.get('approved_for_runtime') is False and plan.get('resource_admission') is None
        and plan.get('paid_usd_ceiling') == 0,
        'exact no-run manual-owner-only uncapped plan required')
    require(plan.get('notebook_numeric_id') is None and plan.get('expected_previous_version') in (None, 0)
        and plan.get('expected_notebook_version', VERSION) == VERSION,
        'new notebook plan cannot target an existing numeric ID or version')
    meta = read(package / 'kernel/kernel-metadata.json')
    require(meta.get('code_file') == 'notebook.ipynb', 'exact notebook filename required')
    notebook = read_bytes(package / 'kernel/notebook.ipynb')
    parsed = parse(notebook)
    require(type(parsed) is dict and parsed.get('nbformat') == 4, 'native notebook required')
    require(all(c.get('outputs', []) == [] and c.get('execution_count') is None
        for c in parsed['cells'] if c.get('cell_type') == 'code'), 'unexecuted source-only notebook required')
    require(checked.get('offline_package_verified') is True, 'offline package preflight must pass')
    return plan, meta, notebook, dict(
        package_manifest_sha256=sha(read_bytes(package / 'package-manifest.json')),
        plan_sha256=sha(read_bytes(package / 'runtime/plan.json')),
        metadata_sha256=sha(read_bytes(package / 'kernel/kernel-metadata.json')),
        notebook_sha256=sha(notebook), source_digest=execution_source_digest(parsed),
        offline_package_verified=True)


def request_fields(package):
    _, meta, notebook, bindings = package_info(package)
    require(meta.get('id') == REF and meta.get('title') == SLUG and meta.get('is_private') is True
        and meta.get('enable_internet') is False and meta.get('enable_gpu') is True
        and meta.get('machine_shape') == 'NvidiaL4' and meta.get('dataset_sources') == []
        and meta.get('competition_sources') == ['arc-prize-2026-arc-agi-2']
        and meta.get('kernel_sources') == ['sorokin/pip-install-unsloth-flash-patch/2']
        and meta.get('model_sources') == ['sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1']
        and type(meta.get('docker_image')) is str and '@sha256:' in meta['docker_image']
        and meta.get('docker_image_pinning_type') == 'original',
        'exact new private notebook identity and retained source pins required')
    require(not any(k in meta for k in ('id_no', 'kernel_id', 'session_timeout_seconds', 'sessionTimeoutSeconds')),
        'metadata cannot supply existing numeric ID or session timeout')
    # Supported official CLI new-slug workflow: kaggle_api_extended.py:6356-
    # 6363 accepts metadata slug without id_no, and :6430-6432 assigns id=None,
    # slug and new_title. ApiSaveKernelRequest docs in kernels_api_service.py:
    # 1968-1978 require id OR slug and prioritize a supplied numeric ID. This
    # request therefore omits ID entirely; it is not an atomic create-only API.
    fields = dict(slug=REF, new_title=SLUG, text=notebook.decode('utf-8'),
        language='python', kernel_type='notebook', is_private=True, enable_gpu=True,
        enable_tpu=False, enable_internet=False, dataset_data_sources=[],
        competition_data_sources=meta['competition_sources'], kernel_data_sources=meta['kernel_sources'],
        model_data_sources=meta['model_sources'], machine_shape='NvidiaL4',
        docker_image=meta['docker_image'], docker_image_pinning_type=meta['docker_image_pinning_type'])
    wire = dict(slug=REF, newTitle=SLUG, text=notebook.decode('utf-8'),
        language='python', kernelType='notebook', isPrivate=True, enableGpu=True,
        enableTpu=False, enableInternet=False, competitionDataSources=meta['competition_sources'],
        kernelDataSources=meta['kernel_sources'], modelDataSources=meta['model_sources'],
        machineShape='NvidiaL4', dockerImage=meta['docker_image'],
        dockerImagePinningType=meta['docker_image_pinning_type'], kernelExecutionType='QUICK_SAVE')
    return fields, wire, bindings


def request(package):
    from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
    from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
    fields, wire, bindings = request_fields(package)
    req = ApiSaveKernelRequest()
    for key, value in fields.items():
        setattr(req, key, value)
    req.kernel_execution_type = KernelExecutionType.QUICK_SAVE
    require(canonical(req.to_dict()) == canonical(wire), 'genuine SDK serialization differs from closed expectation')
    return req, wire, bindings


def wire_body(prepared, expected):
    require(prepared.method == 'POST' and prepared.url == SAVE_URL, 'only exact SaveKernel endpoint permitted')
    body = prepared.body.encode('utf-8') if type(prepared.body) is str else prepared.body
    require(type(body) is bytes and len(body) <= MAX_NOTEBOOK * 2, 'bounded prepared transport body required')
    actual = parse(body)
    require(canonical(actual) == canonical(expected), 'actual prepared request differs from reviewed closed wire')
    require('id' not in actual and 'sessionTimeoutSeconds' not in actual
        and actual['kernelExecutionType'] == 'QUICK_SAVE' and actual['slug'] == REF
        and actual['newTitle'] == SLUG, 'new QUICK_SAVE with no numeric ID or session timeout required')
    return body


class CapturedRequest(BaseException):
    pass


def capture_prepared(req, wire):
    from kagglesdk import KaggleClient
    from kagglesdk.kaggle_env import KaggleEnv
    captured = []
    with KaggleClient(env=KaggleEnv.PROD, verbose=False, api_token='OFFLINE-NOT-A-CREDENTIAL') as client:
        session = client.http_client()._session
        def stop(prepared, **kwargs):
            require(not captured, 'exactly one offline prepared request required')
            captured.append(wire_body(prepared, wire))
            raise CapturedRequest()
        session.send = stop
        try:
            client.kernels.kernels_api_client.save_kernel(req)
        except CapturedRequest:
            pass
    require(len(captured) == 1, 'SDK did not reach HTTP interception')
    return captured[0]


def claim_path():
    # Shared by sibling recovery worktrees; an alternate journal cannot resend.
    return ROOT.parent / '.uncapped-quicksave-publication' / (RUN_ID + '-reservation.json')


def prepare(package, journal, *, newness_proof='source-404'):
    journal = safe_path(journal)
    require(newness_proof in NEWNESS_PROOFS, 'explicit supported newness proof required')
    require(not journal.exists(), 'new immutable transport journal required')
    require(not claim_path().exists(), 'new notebook publication identity already reserved')
    req, wire, bindings = request(package)
    body = capture_prepared(req, wire)
    journal.mkdir(parents=True)
    atomic_bytes(journal / 'prepared-request.body', body, exclusive=True)
    write(journal / 'save-request.json', wire, exclusive=True)
    value = dict(format=FORMAT, run_id=RUN_ID, ref=REF, expected_version=VERSION,
        execution_type='QUICK_SAVE', newness_proof=newness_proof, bindings=bindings, request_sha256=sha(canonical(wire)),
        prepared_body_sha256=sha(body), transport_sha256=sha(read_bytes(Path(__file__))),
        prepared_at=utc(), publication_reserved=0, state='prepared-not-sent', events=[])
    write(journal / 'ledger.json', value, exclusive=True)
    return review_binding(value)


def review_binding(ledger):
    return dict(format='irisx/new-uncapped-quicksave-review-v1', run_id=RUN_ID, ref=REF,
        expected_version=VERSION, execution_type='QUICK_SAVE', newness_proof=ledger['newness_proof'], **ledger['bindings'],
        request_sha256=ledger['request_sha256'], prepared_body_sha256=ledger['prepared_body_sha256'],
        transport_sha256=ledger['transport_sha256'])


def verify_review(ledger, path):
    value = read(path, MAX_JSON)
    expected = review_binding(ledger)
    require(set(value) == set(expected) | {'verdict', 'reviewer', 'reviewed_at'}
        and all(type(value.get(k)) is type(v) and value[k] == v for k, v in expected.items())
        and value['verdict'] == 'PASS' and type(value['reviewer']) is str and value['reviewer'].strip()
        and type(value['reviewed_at']) is str and value['reviewed_at'],
        'independent PASS review must bind exact package and actual prepared SDK wire')
    return sha(read_bytes(path))


def load_bound(package, journal):
    journal = safe_path(journal)
    ledger = read(journal / 'ledger.json', MAX_JSON)
    req, wire, bindings = request(package)
    require(ledger['format'] == FORMAT and ledger['run_id'] == RUN_ID and ledger['ref'] == REF
        and ledger['expected_version'] == VERSION and ledger['execution_type'] == 'QUICK_SAVE'
        and ledger.get('newness_proof') in NEWNESS_PROOFS
        and ledger['bindings'] == bindings and ledger['transport_sha256'] == sha(read_bytes(Path(__file__)))
        and ledger['request_sha256'] == sha(canonical(wire))
        and canonical(read(journal / 'save-request.json')) == canonical(wire)
        and ledger['prepared_body_sha256'] == sha(read_bytes(journal / 'prepared-request.body', MAX_NOTEBOOK * 2)),
        'immutable package, implementation or journal binding changed')
    require(canonical(parse(read_bytes(journal / 'prepared-request.body', MAX_NOTEBOOK * 2))) == canonical(wire),
        'retained actual prepared wire changed')
    return ledger, req, wire


def official_client():
    # Only official CLI credential loading/refresh; no secret files read here.
    import kaggle
    api = kaggle.api
    require(api.config_values.get(api.CONFIG_NAME_USER) == OWNER and api._authenticated is True,
        'official existing auth must authenticate exact owner')
    client = api.build_kaggle_client()
    client.http_client()._verbose = False
    return client


def bounded_session(client):
    http = client.http_client(); http._init_session()
    session = http._session
    require(all(adapter.max_retries.total == 0 for adapter in session.adapters.values()),
        'HTTP retries must be disabled')
    return session


def source_request(ref=REF):
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
    require(ref in (REF, PRIVATE_ANCHOR_REF), 'only new notebook or predefined private anchor SOURCE permitted')
    req = ApiGetKernelRequest()
    req.user_name, req.kernel_slug = ref.split('/')
    return req


class CapturedSourceResponse(BaseException):
    pass


def source_response(client, destination, *, ref=REF):
    """One official exact-slug SOURCE read; preserve HTTP status and raw bytes."""
    require(ref in (REF, PRIVATE_ANCHOR_REF), 'only predefined exact SOURCE references permitted')
    req = source_request(ref)
    session = bounded_session(client); original = session.send
    captured = []
    def send(prepared, **kwargs):
        require(not captured and prepared.method == 'POST' and prepared.url == SOURCE_URL
            and canonical(parse(prepared.body)) == canonical(req.to_dict()), 'one exact-slug SOURCE read required')
        # Reserve the call before I/O, including when I/O raises ambiguously.
        captured.append(None)
        kwargs.update(timeout=(15, 120), allow_redirects=False, stream=True)
        response = original(prepared, **kwargs)
        try:
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                require(len(body) <= MAX_NOTEBOOK * 2, 'SOURCE transport response byte ceiling exceeded')
            atomic_bytes(destination, bytes(body), exclusive=True)
            evidence = dict(http_status=response.status_code, ref=ref, observed_at=utc(),
                body_sha256=sha(bytes(body)), endpoint=SOURCE_URL)
            write(Path(destination).with_suffix('.http.json'), evidence, exclusive=True)
            captured[0] = evidence
        finally:
            response.close()
        # Bypass SDK parsing/retries for both 404 and 403 while retaining status.
        raise CapturedSourceResponse()
    session.send = send
    try:
        try:
            client.kernels.kernels_api_client.get_kernel(req)
        except CapturedSourceResponse:
            pass
    finally:
        session.send = original
    require(len(captured) == 1 and captured[0] is not None, 'one captured SOURCE response required')
    return captured[0]


def confirm_absent(client, destination):
    evidence = source_response(client, destination)
    status = evidence['http_status']
    if status == 403:
        raise RuntimeError('exact-slug SOURCE returned 403 forbidden; absence is not established; no save')
    if status == 200:
        raise RuntimeError('exact new slug already exists; no version update permitted')
    require(status == 404, 'exact-slug SOURCE did not return 404; absence is not established; no save')
    return dict(evidence, absent=True)



def own_list_request(page_token=''):
    """Exact official kernels_list(mine=True, sort_by='dateCreated') semantics.

    Installed official kaggle/api/kaggle_api_extended.py:6078-6095 maps mine
    to PROFILE and sets the unfiltered fields below; :1146-1166 maps cursor
    paging. kagglesdk/kernels/types/kernels_api_service.py:1920-1962 defines
    kernels plus nextPageToken. No runtime or target SOURCE call is involved.
    """
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelsRequest
    from kagglesdk.kernels.types.kernels_enums import KernelsListViewType, KernelsListSortType
    require(type(page_token) is str and len(page_token) <= 4096, 'bounded opaque own-list cursor required')
    req = ApiListKernelsRequest()
    req.group = KernelsListViewType.PROFILE
    req.sort_by = KernelsListSortType.DATE_CREATED
    req.page_size = OWN_LIST_PAGE_SIZE
    req.page_token = page_token
    if not page_token:
        req.page = 1
    req.user = ''  # PROFILE identifies the authenticated owner, not a public user search.
    req.language = req.kernel_type = req.output_type = 'all'
    req.dataset = req.competition = req.parent_kernel = req.search = ''
    return req


def own_list_response(client, destination, page_token=''):
    """One authorized own-inventory page. No target SOURCE, status or runtime IO."""
    req = own_list_request(page_token)
    session = bounded_session(client); original = session.send
    captured = []
    def send(prepared, **kwargs):
        require(not captured and prepared.method == 'POST' and prepared.url == LIST_URL
            and canonical(parse(prepared.body)) == canonical(req.to_dict()), 'one exact official own-list page required')
        captured.append(None)
        kwargs.update(timeout=(15, 120), allow_redirects=False, stream=True)
        response = original(prepared, **kwargs)
        try:
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                require(len(body) <= 16 * MAX_JSON, 'own-list response byte ceiling exceeded; enumeration incomplete')
            atomic_bytes(destination, bytes(body), exclusive=True)
            evidence = dict(http_status=response.status_code, owner=OWNER, observed_at=utc(),
                body_sha256=sha(bytes(body)), request_sha256=sha(canonical(req.to_dict())), endpoint=LIST_URL)
            write(Path(destination).with_suffix('.http.json'), evidence, exclusive=True)
            captured[0] = evidence
        finally:
            response.close()
        raise CapturedSourceResponse()
    session.send = send
    try:
        try:
            client.kernels.kernels_api_client.list_kernels(req)
        except CapturedSourceResponse:
            pass
    finally:
        session.send = original
    require(len(captured) == 1 and captured[0] is not None, 'one captured own-list response required')
    return captured[0]


def confirm_absent_from_own_list(client, destination):
    """Operational newness proof from a complete authorized own-kernel census.

    Official PROFILE listing is the same route used by CLI mine=True. Require
    the known notebook ref in that census and a separate authorized SOURCE
    read proving its private numeric identity as evidence of the owner's
    private inventory. Complete PROFILE enumeration, a fresh unique slug and
    that private anchor are the reviewed operational proof, not a provider
    guarantee about every draft or atomic create-only behavior. Any denial,
    missing private anchor, incomplete pagination, duplicate, foreign owner
    or unknown response shape blocks publication. Exact recognized private
    redactions are counted explicitly without inspecting their identities;
    their presence makes reference coverage incomplete, not pagination.
    """
    destination = safe_path(destination)
    require(not destination.exists(), 'fresh own-list evidence directory required')
    destination.mkdir(parents=True)
    started_at = utc()
    token = ''
    seen_tokens, seen_ids, seen_refs, pages = set(), set(), set(), []
    numeric_inventory_complete = True
    redacted_positions = []
    inventory_row_count = 0
    for index in range(MAX_OWN_LIST_PAGES):
        require(token not in seen_tokens, 'own-list pagination loop; enumeration incomplete')
        seen_tokens.add(token)
        path = destination / f'page-{index:03d}.json'
        evidence = own_list_response(client, path, token)
        require(evidence['http_status'] == 200,
            'own-list request denied or failed; namespace absence unestablished; no save')
        raw = read(path, 16 * MAX_JSON)
        require(type(raw) is dict and set(raw) <= {'kernels', 'nextPageToken'},
            'unknown own-list response shape; enumeration incomplete')
        rows, next_token = raw.get('kernels', []), raw.get('nextPageToken', '')
        require(type(rows) is list and len(rows) <= OWN_LIST_PAGE_SIZE
            and type(next_token) is str and len(next_token) <= 4096,
            'malformed own-list page; enumeration incomplete')
        require(rows or not next_token, 'empty own-list continuation page; enumeration incomplete')
        inventory_row_count += len(rows)
        page_redacted_count = 0
        for row_index, row in enumerate(rows):
            if type(row) is dict and row == REDACTED_OWN_LIST_ROW:
                # Exact observed provider marker only. Retain its count and
                # position, do not infer its identity or attempt to access it.
                redacted_positions.append(dict(page=index, row=row_index))
                page_redacted_count += 1
                numeric_inventory_complete = False
                continue
            # Live official PROFILE pages can project only ref/title/author/
            # lastRunTime. Do not invent numeric IDs or privacy flags.
            require(type(row) is dict and type(row.get('ref')) is str
                and row['ref'].startswith(OWNER + '/') and len(row['ref'].split('/')) == 2
                and row['ref'].split('/')[1], 'own-list row must identify an exact owned notebook ref')
            require(row['ref'] not in seen_refs, 'duplicate own-list ref; stable complete enumeration unestablished')
            require(row['ref'] != REF, 'exact new slug already exists in own list; no version update permitted')
            seen_refs.add(row['ref'])
            if 'id' in row:
                require(type(row['id']) is int and row['id'] > 0 and row['id'] not in seen_ids,
                    'invalid or duplicate provided own-list numeric ID')
                seen_ids.add(row['id'])
            else:
                numeric_inventory_complete = False
            if 'isPrivate' in row:
                require(type(row['isPrivate']) is bool, 'invalid provided own-list privacy flag')
            if row['ref'] == PRIVATE_ANCHOR_REF:
                require(row.get('id', 137327571) == 137327571 and row.get('isPrivate', True) is True,
                    'provided private-anchor identity or privacy contradicts known anchor')
        pages.append(dict(evidence, rows=len(rows), redacted_count=page_redacted_count,
            has_next_page=bool(next_token)))
        if not next_token:
            break
        token = next_token
    else:
        raise RuntimeError('own-list page bound reached; enumeration incomplete; no save')
    require(PRIVATE_ANCHOR_REF in seen_refs,
        'known own notebook ref absent from list; authenticated private namespace unverified')
    # This explicitly authorized, known-private SOURCE is not the denied new
    # target. It verifies the account/private anchor without a runtime query.
    anchor_path = destination / 'private-anchor-source.json'
    anchor_evidence = source_response(client, anchor_path, ref=PRIVATE_ANCHOR_REF)
    require(anchor_evidence['http_status'] == 200,
        'private anchor SOURCE denied or failed; private namespace unverified; no save')
    anchor_raw = read(anchor_path, MAX_NOTEBOOK * 2)
    anchor_meta = anchor_raw.get('metadata') if type(anchor_raw) is dict else None
    require(type(anchor_meta) is dict and type(anchor_meta.get('id')) is int
        and anchor_meta['id'] == 137327571 and anchor_meta.get('ref') == PRIVATE_ANCHOR_REF
        and anchor_meta.get('isPrivate') is True,
        'private anchor SOURCE must verify exact owned ref, ID and privacy')
    private_anchors = set(PRESERVED_KERNEL_IDS)
    proof = dict(owner=OWNER, ref=REF, absent=True, absence_scope='visible PROFILE references only',
        target_not_listed=True, visible_reference_noncollision=True,
        operational_newness_verified=True, atomic_namespace_absence_guaranteed=False,
        quicksave_draft_coverage_attested=False,
        create_only_semantics_verified=False, observed_at=started_at, completed_at=utc(),
        proof_kind='complete-official-own-profile-list', pagination_complete=True,
        inventory_scope='cursor-complete authenticated PROFILE, visible refs checked and exact redactions counted',
        guarantee_limitations='Redacted identities are not inspected and inaccessible-name absence is not inferred. No guarantee for every unsaved/QuickSave-only draft or atomic create-if-absent.',
        target_source_read=False, source_403_used_as_absence=False,
        private_namespace_anchor_ids=sorted(private_anchors), private_anchor_source_verified=True,
        private_anchor_source=anchor_evidence,
        enumerated_kernel_ids=sorted(seen_ids), numeric_id_inventory_complete=numeric_inventory_complete,
        notebook_count=len(seen_refs), notebook_count_scope='visible references only',
        visible_reference_count=len(seen_refs), inventory_row_count=inventory_row_count,
        redacted_count=len(redacted_positions), redacted_positions=redacted_positions,
        reference_coverage_complete=not redacted_positions,
        page_count=len(pages), pages=pages, identity_set_sha256=sha(canonical(sorted(seen_refs))))
    write(destination / 'inventory-census.json', proof, exclusive=True)
    return proof

def receipt_is_accepted(raw, typed, *, prior_kernel_ids=()):
    allowed = {'ref', 'url', 'versionNumber', 'kernelId', 'error', 'invalidTags',
        'invalidDatasetSources', 'invalidKernelSources', 'invalidCompetitionSources', 'invalidModelSources'}
    require(type(raw) is dict and set(raw) <= allowed, 'closed SaveKernel receipt required')
    require(type(raw.get('ref')) is str and raw['ref'] in {REF, '/code/' + REF}
        and raw.get('url') == PUBLIC_URL and type(raw.get('versionNumber')) is int and raw['versionNumber'] == VERSION
        and type(raw.get('kernelId')) is int and raw['kernelId'] > 0
        and raw['kernelId'] not in PRESERVED_KERNEL_IDS and raw['kernelId'] not in prior_kernel_ids,
        'accepted receipt must identify a distinct new notebook, exact slug and version 1')
    require(not raw.get('error') and not any(raw.get(k) for k in allowed if k.startswith('invalid')),
        'provider rejected a source or save')
    require(typed.ref == raw['ref'] and typed.url == PUBLIC_URL
        and type(typed.version_number) is int and typed.version_number == VERSION
        and type(typed.kernel_id) is int and typed.kernel_id == raw['kernelId'] and not typed.error,
        'raw and typed SaveKernel receipt disagree')
    return raw['kernelId']


def verify_source_value(raw, package, kernel_id, expected_digest):
    """Verify SOURCE identity/settings/cells; distinguish request from attestation."""
    require(type(raw) is dict and type(raw.get('metadata')) is dict and type(raw.get('blob')) is dict,
        'complete SOURCE response required')
    meta, blob = raw['metadata'], raw['blob']
    _, expected, _, _ = package_info(package)
    checks = dict(id=kernel_id, ref=REF, title=SLUG, currentVersionNumber=VERSION,
        isPrivate=True, enableInternet=False, enableGpu=True, enableTpu=False,
        language='python', kernelType='notebook', machineShape='NvidiaL4',
        dockerImage=expected['docker_image'], datasetDataSources=expected['dataset_sources'],
        kernelDataSources=expected['kernel_sources'], modelDataSources=expected['model_sources'],
        competitionDataSources=expected['competition_sources'])
    actual = {key: meta.get(key, [] if key == 'datasetDataSources' else None) for key in checks}
    normalizations = []
    if actual['kernelDataSources'] == ['sorokin/pip-install-unsloth-flash-patch']:
        actual['kernelDataSources'] = expected['kernel_sources']
        normalizations.append('known provider dependency version suffix omitted')
    if actual['modelDataSources'] == ['sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1']:
        actual['modelDataSources'] = expected['model_sources']
        normalizations.append('known provider Transformers framework capitalization')
    require(type(kernel_id) is int and kernel_id > 0 and kernel_id not in PRESERVED_KERNEL_IDS
        and all(type(actual[k]) is type(v) and actual[k] == v for k, v in checks.items()),
        'SOURCE new notebook identity/version/settings/source pins differ')
    require(type(blob.get('source')) is str, 'SOURCE notebook string required')
    notebook = parse(blob['source'])
    require(execution_source_digest(notebook) == expected_digest, 'SOURCE executable cells differ')
    require(all(c.get('outputs', []) == [] and c.get('execution_count') is None
        for c in notebook['cells'] if c.get('cell_type') == 'code'), 'SOURCE contains executed cells')
    defaults = []
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        code = cell['source'] if type(cell['source']) is str else ''.join(cell['source'])
        for node in ast.parse(code).body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == 'CONFIRM_UNCAPPED_OWNER_RUN' for target in node.targets):
                defaults.append(isinstance(node.value, ast.Constant) and node.value.value is False)
    require(defaults == [True], 'SOURCE must retain exactly one explicit owner-start default False')
    # Official GetKernel historically returns no SaveType. Never fabricate an
    # attestation from our own notebook metadata or from absence of output.
    kaggle_meta = notebook.get('metadata', {}).get('kaggle', {})
    save_type = kaggle_meta.get('SaveType')
    require(save_type in (None, 'QUICK_SAVE'), 'SOURCE SaveType contradicts reviewed QUICK_SAVE')
    return dict(ref=REF, url=PUBLIC_URL, kernel_id=kernel_id, version=VERSION,
        source_digest=expected_digest, source_only_verified=True,
        provider_save_type=save_type, provider_save_type_attested=save_type is not None,
        source_outputs_empty=True, owner_start_default_false_verified=True,
        runtime_state_attested=False, runtime_state_queried=False, gpu_allocation_queried=False,
        provider_read_normalizations=normalizations,
        dependency_version_echo_verified='known provider dependency version suffix omitted' not in normalizations,
        dependency_selected_bytes_verified=False)



def verify_accepted_receipt(journal, ledger):
    require(ledger.get('accepted') is True and ledger.get('publication_reserved') == 1
        and len(ledger.get('events', [])) == 1, 'accepted single-save ledger required')
    event = ledger['events'][0]
    raw_body = read_bytes(journal / 'save-receipt.raw.json', MAX_JSON)
    raw = parse(raw_body)
    typed = read(journal / 'save-receipt.typed.json', MAX_JSON)
    identity = SimpleNamespace(ref=typed.get('ref'), url=typed.get('url'),
        version_number=typed.get('versionNumber'), kernel_id=typed.get('kernelId'), error=typed.get('error'))
    kernel_id = receipt_is_accepted(raw, identity,
        prior_kernel_ids=event.get('absence', {}).get('enumerated_kernel_ids', ()))
    claim = read(claim_path(), MAX_JSON)
    require(event.get('action') == 'SaveKernel' and event.get('execution_type') == 'QUICK_SAVE'
        and event.get('sends') == 1 and event.get('outcome') == 'accepted'
        and event.get('raw_receipt_sha256') == sha(raw_body) and event.get('http_status') == 200
        and kernel_id == ledger.get('kernel_id') and ledger.get('provider_version') == VERSION
        and claim.get('run_id') == RUN_ID and claim.get('ref') == REF
        and claim.get('expected_version') == VERSION
        and claim.get('package_manifest_sha256') == ledger['bindings']['package_manifest_sha256']
        and claim.get('prepared_body_sha256') == ledger['prepared_body_sha256']
        and claim.get('review_sha256') == event.get('review_sha256'),
        'accepted receipt, durable claim and exact package must remain bound')
    return kernel_id

def verify_source(package, journal):
    """Read SOURCE only, including recovery after an accepted save/readback failure."""
    journal = safe_path(journal)
    with locked(journal):
        ledger, _, _ = load_bound(package, journal)
        verify_accepted_receipt(journal, ledger)
        index = ledger.get('source_reads_reserved', 0)
        ledger['source_reads_reserved'] = index + 1
        write(journal / 'ledger.json', ledger)
        destination = journal / f'post-save-source-{index:03d}.json'
        with official_client() as client:
            evidence = source_response(client, destination)
        require(evidence['http_status'] == 200, 'SOURCE verification read failed; never resend SaveKernel')
        result = verify_source_value(read(destination, MAX_NOTEBOOK * 2), package,
            ledger['kernel_id'], ledger['bindings']['source_digest'])
        result.update(primary_sha256=evidence['body_sha256'], observed_at=evidence['observed_at'],
            request_execution_type='QUICK_SAVE', actual_wire_quicksave_verified=True,
            prepared_body_sha256=ledger['prepared_body_sha256'], auto_run_requested=False)
        write(journal / f'source-verification-{index:03d}.json', result, exclusive=True)
        ledger.update(state='new-private-quicksave-source-verified', source_verified=True)
        write(journal / 'ledger.json', ledger)
        return result


def publish(package, journal, review):
    journal = safe_path(journal)
    with locked(journal):
        ledger, req, wire = load_bound(package, journal)
        require(ledger['publication_reserved'] == 0 and ledger['state'] == 'prepared-not-sent'
            and not claim_path().exists(), 'new notebook publication already reserved; no retry')
        review_sha = verify_review(ledger, review)
        with official_client() as client:
            if ledger['newness_proof'] == 'source-404':
                before = confirm_absent(client, journal / 'pre-send-source.json')
            else:
                before = confirm_absent_from_own_list(client, journal / 'pre-send-own-list')
                require(before.get('operational_newness_verified') is True
                    and before.get('pagination_complete') is True
                    and before.get('target_not_listed') is True
                    and before.get('private_namespace_anchor_ids') == sorted(PRESERVED_KERNEL_IDS),
                    'complete private own-inventory operational newness proof required; no save')
            # Recheck all actual package and reviewed wire bindings after I/O.
            fresh, _, fresh_wire = load_bound(package, journal)
            require(fresh == ledger and fresh_wire == wire and verify_review(fresh, review) == review_sha,
                'package, journal or review changed during newness check')
            event = dict(action='SaveKernel', execution_type='QUICK_SAVE', reserved_at=utc(), sends=0,
                review_sha256=review_sha, absence=before, outcome='reserved-unsent')
            write(claim_path(), dict(run_id=RUN_ID, ref=REF, expected_version=VERSION,
                package_manifest_sha256=ledger['bindings']['package_manifest_sha256'],
                prepared_body_sha256=ledger['prepared_body_sha256'], review_sha256=review_sha,
                reserved_at=event['reserved_at']), exclusive=True)
            ledger['publication_reserved'] = 1; ledger['state'] = 'reserved-unknown'; ledger['events'].append(event)
            write(journal / 'ledger.json', ledger)
            session = bounded_session(client); original = session.send
            def send(prepared, **kwargs):
                body = wire_body(prepared, wire)
                fresh_ledger, _, _ = load_bound(package, journal)
                require(fresh_ledger == ledger and verify_review(fresh_ledger, review) == review_sha,
                    'package or reviewed transport changed immediately before send')
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(before['observed_at'])).total_seconds()
                require(0 <= age <= 300, 'exact-slug absence observation expired before send')
                require(sha(body) == ledger['prepared_body_sha256'] and event['sends'] == 0,
                    'actual wire changed or duplicate send attempted')
                event.update(sends=1, outcome='send-started-unknown')
                write(journal / 'ledger.json', ledger)
                kwargs.update(timeout=(15, 120), allow_redirects=False, stream=True)
                response = original(prepared, **kwargs)
                try:
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk); require(len(body) <= MAX_JSON, 'bounded SaveKernel receipt required')
                    atomic_bytes(journal / 'save-receipt.raw.json', bytes(body), exclusive=True)
                    event.update(raw_receipt_sha256=sha(bytes(body)), http_status=response.status_code)
                    write(journal / 'ledger.json', ledger)
                    response._content = bytes(body); response._content_consumed = True
                    require(response.status_code == 200, 'SaveKernel failed; identity frozen')
                    parse(bytes(body))
                    return response
                finally:
                    response.close()
            session.send = send
            try:
                response = client.kernels.kernels_api_client.save_kernel(req)
                raw = read(journal / 'save-receipt.raw.json', MAX_JSON)
                kernel_id = receipt_is_accepted(raw, response,
                    prior_kernel_ids=before.get('enumerated_kernel_ids', ()))
                require(event['sends'] == 1, 'one completed SaveKernel send required')
                write(journal / 'save-receipt.typed.json', response.to_dict(), exclusive=True)
                ledger.update(state='accepted-source-unverified', accepted=True, kernel_id=kernel_id, provider_version=VERSION)
                event.update(outcome='accepted', completed_at=utc())
                write(journal / 'ledger.json', ledger)
            except BaseException as error:
                ledger.update(state='frozen-uncertain-no-retry', accepted=False)
                event.update(outcome='failed-or-uncertain-no-retry', error_type=type(error).__name__, completed_at=utc())
                write(journal / 'ledger.json', ledger)
                raise RuntimeError('new QUICK_SAVE failed or is uncertain; identity frozen; no duplicate send') from None
            finally:
                session.send = original
    # Readback failure preserves accepted identity. SOURCE-only retries are safe;
    # SaveKernel cannot be retried after any reservation, even an uncertain one.
    return verify_source(package, journal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'publish', 'verify-source'))
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--newness-proof', choices=NEWNESS_PROOFS,
        help='prepare only; explicit reviewed choice, never an automatic denial fallback')
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.package, args.journal, newness_proof=args.newness_proof or 'source-404')
    elif args.action == 'publish':
        require(args.newness_proof is None, 'newness proof is fixed by prepare and independent review')
        require(args.review is not None, 'independent actual-wire review required')
        result = publish(args.package, args.journal, args.review)
    else:
        require(args.newness_proof is None, 'newness proof applies only to prepare')
        result = verify_source(args.package, args.journal)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()

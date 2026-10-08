"""Fresh private offline pilot v2 source-only QUICK_SAVE transport.

``inspect`` and ``prepare`` are offline. Preparation uses the installed official
SDK with a dummy token and intercepts its actual HTTP request before network IO.
``publish`` alone may save once, after a separate PASS review and exact v1
SOURCE check. No runtime/status/list calls, RUN, GPU allocation, session timeout,
or Dataset publication are implemented here. Only the exact owner-confirmed
existing ARC3 attachment is preserved; no competition content is read or used.
An uncertain save is frozen.

Assets evidence is a separately reviewed attestation, never manufactured by
this transport. Its three records must bind exact numerical Dataset references,
manifest hashes, ready/private/file-verification flags and nonempty retained
receipt files. Receipt provenance/meaning must be reviewed before setting PASS;
a hash alone cannot establish that an arbitrary file is a provider receipt.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
# Only shared low-level/pure helpers and exact-ref SOURCE/auth plumbing. Never
# call the consumed v1 package/prepare/publish/receipt/claim functions.
from tools.publish_arc_next_quicksave import (
    MAX_JSON, MAX_NOTEBOOK, SAVE_URL, SOURCE_URL, atomic_bytes, bounded_session,
    canonical, execution_source_digest, locked, official_client, parse,
    read, read_bytes, require, safe_path as _safe_path, sha, source_response as _source_response, utc, write,
)

RUN_ID = 'arc-next-g4-offline-20261008-002'
REF = 'danielwuu/iris-arc2-g4-agent-pilot-20261008-6deaf904'
OWNER, SLUG = REF.split('/')
KERNEL_ID = 137630087
EXPECTED_PREVIOUS_VERSION = 1
EXPECTED_NEXT_VERSION = 2
PUBLIC_URL = 'https://www.kaggle.com/code/' + REF
FORMAT = 'irisx/arc-next-offline-quicksave-transport-v1'
ASSETS_FORMAT = 'irisx/arc-next-offline-assets-evidence-v1'
REVIEW_FORMAT = 'irisx/arc-next-offline-quicksave-review-v1'
ROLES = ('runtime', 'model', 'wheels')
PRESERVED_COMPETITION_SOURCES = ('arc-prize-2026-arc-agi-3',)
SAFE_REQUEST_HEADERS = frozenset({'content-type', 'host', 'content-length'})
IMPLEMENTATION_FILES = (
    'tools/publish_arc_next_offline_quicksave.py',
    'tools/publish_arc_next_quicksave.py',
    'tools/stage_arc_next_offline.py',
    'tools/stage_arc_next_notebook.py',
    'tools/arc_next_offline_bundle.py',
    'tools/stage4_provider_evidence.py',
)


def safe_path(path):
    # Inspect the supplied path's ancestors for symlinks before collapsing "..".
    # Then perform all containment checks on a normalized absolute path.
    return _safe_path(Path(os.path.normpath(str(_safe_path(path)))))


def source_implementation():
    files = {name: sha(read_bytes(Path(__file__).resolve().parents[1] / name))
             for name in IMPLEMENTATION_FILES}
    return dict(source_implementation_files=files,
                source_implementation_sha256=sha(canonical(files)))


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def verified_pins(pins):
    from tools.arc_next_offline_bundle import validate_reference
    require(type(pins) is dict and set(pins) == set(ROLES), 'exactly three Dataset roles required')
    for role in ROLES:
        pin = pins[role]
        require(type(pin) is dict and set(pin) == {'reference', 'manifest_sha256', 'private'},
                'closed Dataset reference, manifest and privacy pin required')
        validate_reference(pin['reference'])
        require(pin['private'] is True and digest(pin['manifest_sha256']),
                'private Dataset with actual manifest SHA256 required')
    require(len({pins[k]['reference'].rsplit('/', 1)[0] for k in ROLES}) == 3,
            'runtime, model and wheels must be independently versioned Datasets')
    return pins


def assert_inert(nb, flags):
    require(type(nb) is dict and type(nb.get('cells')) is list and nb['cells'],
            'complete notebook cells required')
    defaults = {name: [] for name in flags}
    for cell in nb['cells']:
        require(type(cell) is dict and cell.get('cell_type') in ('code', 'markdown'),
                'only code and markdown notebook cells permitted')
        source = cell.get('source')
        require(type(source) is str or (type(source) is list and all(type(s) is str for s in source)),
                'notebook source text required')
        if cell['cell_type'] != 'code':
            continue
        require(cell.get('outputs', []) == [] and cell.get('execution_count') is None,
                'saved source must have no executed outputs')
        for node in ast.parse(source if type(source) is str else ''.join(source)).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in defaults:
                        defaults[target.id].append(isinstance(node.value, ast.Constant)
                                                   and node.value.value is False)
    require(all(v == [True] for v in defaults.values()), 'each manual flag must appear once and default False')
    meta = nb.get('metadata', {})
    require(meta.get('irisx_execution_mode') == 'QUICK_SAVE'
            and meta.get('irisx_agent_execution_authorized') is False,
            'default-inert source-only execution declaration required')
    require(meta.get('kaggle', {}).get('SaveType') in (None, 'QUICK_SAVE'),
            'source contradicts QUICK_SAVE request')


def package_info(package):
    from tools.stage_arc_next_offline import FLAGS, notebook, PRESERVED_COMPETITION_SOURCES as BUILDER_COMPETITIONS
    require(BUILDER_COMPETITIONS == PRESERVED_COMPETITION_SOURCES,
            'builder must preserve only the exact owner-confirmed existing ARC3 attachment')
    package = safe_path(package)
    nb_bytes = read_bytes(package / 'notebook.ipynb')
    meta_bytes = read_bytes(package / 'kernel-metadata.json', MAX_JSON)
    nb, meta = parse(nb_bytes), parse(meta_bytes)
    pins = verified_pins(nb.get('metadata', {}).get('irisx_offline_dataset_pins'))
    require(nb.get('metadata', {}).get('irisx_preserved_competition_sources') == list(PRESERVED_COMPETITION_SOURCES),
            'notebook must explicitly declare the exact preserved competition attachment')
    # This prevents a syntactically inert but changed/unreviewed runtime loader.
    require(canonical(nb) == canonical(notebook(pins)), 'staged source differs from current offline notebook builder')
    assert_inert(nb, FLAGS)
    refs = [pins[k]['reference'] for k in ROLES]
    expected = dict(id=REF, title=SLUG, code_file='notebook.ipynb', language='python', kernel_type='notebook',
                    is_private=True, enable_gpu=False, enable_internet=False, dataset_sources=refs,
                    competition_sources=list(PRESERVED_COMPETITION_SOURCES), kernel_sources=[], model_sources=[])
    require(canonical(meta) == canonical(expected), 'exact private offline numerical Dataset metadata required')
    bindings = dict(notebook_sha256=sha(nb_bytes), metadata_sha256=sha(meta_bytes),
                    all_cells_sha256=sha(canonical(nb['cells'])), source_digest=execution_source_digest(nb),
                    dataset_pins=pins, all_defaults_inert=True,
                    expected_live_predecessor_competition_sources=list(PRESERVED_COMPETITION_SOURCES),
                    expected_successor_competition_sources=list(PRESERVED_COMPETITION_SOURCES),
                    preserved_competition_attachment_only=True, competition_data_use_authorized=False,
                    **source_implementation())
    return nb, meta, nb_bytes, bindings


def inspect(package):
    _, _, _, bindings = package_info(package)
    return dict(run_id=RUN_ID, ref=REF, kernel_id=KERNEL_ID,
                expected_previous_version=EXPECTED_PREVIOUS_VERSION, expected_next_version=EXPECTED_NEXT_VERSION,
                execution_type='QUICK_SAVE', publication_ready=False, assets_verification_required=True,
                pending_gates=['three-private-ready-file-verified-Dataset-receipts',
                               'preserved-v1-source-binding', 'independent-actual-wire-PASS-review',
                               'exact-live-v1-source-precheck', 'explicit-publication-decision'], **bindings)


def assets_info(path, pins, *, journal):
    path, journal = safe_path(path), safe_path(journal)
    require(not path.is_relative_to(journal), 'asset evidence must be retained outside mutable transport journal')
    body = read_bytes(path, MAX_JSON)
    value = parse(body)
    require(type(value) is dict and set(value) == {'format', 'assets'} and value['format'] == ASSETS_FORMAT
            and type(value['assets']) is dict and set(value['assets']) == set(ROLES),
            'closed exact three-role assets evidence required')
    receipts = []
    for role in ROLES:
        asset = value['assets'][role]
        require(type(asset) is dict and set(asset) == {'reference', 'manifest_sha256', 'private',
                'dataset_ready', 'files_verified', 'receipts'}, 'closed Dataset readiness evidence required')
        require(asset['reference'] == pins[role]['reference']
                and asset['manifest_sha256'] == pins[role]['manifest_sha256']
                and asset['private'] is True and asset['dataset_ready'] is True
                and asset['files_verified'] is True, 'pending, public, unverified or different Dataset blocks preparation')
        require(type(asset['receipts']) is list and 0 < len(asset['receipts']) <= 30,
                'actual nonempty Dataset publication/readiness/file-verification receipt references required')
        seen = set()
        for receipt in asset['receipts']:
            require(type(receipt) is dict and set(receipt) == {'path', 'sha256'}
                    and type(receipt['path']) is str and receipt['path'] and digest(receipt['sha256']),
                    'closed retained receipt path and SHA256 required')
            location = Path(receipt['path'])
            if not location.is_absolute():
                location = path.parent / location
            location = safe_path(location)
            require('..' not in location.parts and not location.is_relative_to(journal)
                    and location != path and location not in seen,
                    'distinct receipt outside mutable journal and evidence required')
            seen.add(location)
            receipt_body = read_bytes(location, MAX_NOTEBOOK)
            require(receipt_body and sha(receipt_body) == receipt['sha256'], 'retained asset receipt bytes changed or empty')
            receipts.append(dict(role=role, path=str(location), sha256=receipt['sha256']))
    return dict(assets_evidence_path=str(path), assets_evidence_sha256=sha(body),
                assets_receipts=receipts, assets_receipts_sha256=sha(canonical(receipts)),
                assets_evidence_verified=True)


def source_identity(raw, version, references, *, competition_sources):
    require(type(raw) is dict and type(raw.get('metadata')) is dict and type(raw.get('blob')) is dict,
            'complete exact notebook SOURCE readback required')
    meta, blob = raw['metadata'], raw['blob']
    checks = dict(id=KERNEL_ID, ref=REF, title=SLUG, currentVersionNumber=version,
                  isPrivate=True, enableGpu=False, enableTpu=False, enableInternet=False,
                  language='python', kernelType='notebook')
    require(all(type(meta.get(k)) is type(v) and meta[k] == v for k, v in checks.items()),
            'exact notebook ID, version, private and all accelerator/Internet OFF flags required')
    require(meta.get('datasetDataSources', []) == references, 'exact numerical Dataset versions must survive SOURCE readback')
    require(type(competition_sources) is list and competition_sources in ([], list(PRESERVED_COMPETITION_SOURCES)),
            'only frozen empty or exact owner-confirmed existing competition attachment expected')
    require(meta.get('competitionDataSources', []) == competition_sources,
            'exact historical/preserved competition attachment must survive SOURCE readback')
    for key in ('kernelDataSources', 'modelDataSources'):
        require(meta.get(key, []) == [], 'unapproved external SOURCE inputs')
    require(type(blob.get('source')) is str, 'SOURCE notebook string required')
    return parse(blob['source'])


def previous_info(path, *, journal):
    from tools.stage_arc_next_notebook import FLAGS
    path = safe_path(path)
    require(not path.is_relative_to(safe_path(journal)), 'preserved v1 source must remain outside new journal')
    body = read_bytes(path, MAX_NOTEBOOK * 2)
    raw = parse(body)
    nb = source_identity(raw, EXPECTED_PREVIOUS_VERSION, [], competition_sources=[])
    assert_inert(nb, FLAGS)
    return dict(previous_source_path=str(path), previous_source_sha256=sha(body),
                previous_all_cells_sha256=sha(canonical(nb['cells'])),
                previous_notebook_sha256=sha(canonical(nb)),
                previous_source_text_sha256=sha(raw['blob']['source'].encode('utf-8')),
                historical_previous_competition_sources=[])


def request_fields(package):
    _, meta, notebook, bindings = package_info(package)
    fields = dict(slug=REF, new_title=SLUG, text=notebook.decode('utf-8'), language='python',
                  kernel_type='notebook', is_private=True, enable_gpu=False, enable_tpu=False,
                  enable_internet=False, dataset_data_sources=meta['dataset_sources'],
                  competition_data_sources=meta['competition_sources'], kernel_data_sources=[], model_data_sources=[])
    wire = dict(slug=REF, newTitle=SLUG, text=notebook.decode('utf-8'), language='python',
                kernelType='notebook', isPrivate=True, enableGpu=False, enableTpu=False,
                enableInternet=False, datasetDataSources=meta['dataset_sources'],
                competitionDataSources=meta['competition_sources'], kernelExecutionType='QUICK_SAVE')
    return fields, wire, bindings


def request(package):
    from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
    from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
    fields, wire, bindings = request_fields(package)
    req = ApiSaveKernelRequest()
    for key, value in fields.items():
        setattr(req, key, value)
    req.kernel_execution_type = KernelExecutionType.QUICK_SAVE
    require(canonical(req.to_dict()) == canonical(wire), 'official SDK serialization differs from closed v2 expectation')
    return req, wire, bindings


def representation_headers(prepared, body):
    """Validate and retain only non-sensitive representation/routing headers."""
    names = list(prepared.headers)
    require(all(type(name) is str for name in names), 'HTTP header names must be strings')
    lowered = [name.lower() for name in names]
    require(len(lowered) == len(set(lowered)), 'duplicate case-insensitive HTTP headers forbidden')
    require('transfer-encoding' not in lowered and 'content-encoding' not in lowered,
            'unexpected transfer/content encoding forbidden')
    # Never copy or serialize authorization, cookies or other unreviewed values.
    headers = {name.lower(): prepared.headers[name] for name in names if name.lower() in SAFE_REQUEST_HEADERS}
    require(headers.get('content-type') == 'application/json', 'actual JSON Content-Type required')
    require('host' not in headers or headers['host'] == 'api.kaggle.com', 'official API Host required when provided')
    require('content-length' not in headers or headers['content-length'] == str(len(body)),
            'actual Content-Length must equal exact prepared body bytes')
    return headers


def wire_body(prepared, expected, expected_headers=None):
    require(prepared.method == 'POST' and prepared.url == SAVE_URL, 'only exact SaveKernel endpoint permitted')
    body = prepared.body.encode('utf-8') if type(prepared.body) is str else prepared.body
    require(type(body) is bytes and len(body) <= MAX_NOTEBOOK * 2, 'bounded prepared request body required')
    headers = representation_headers(prepared, body)
    require(expected_headers is None or headers == expected_headers,
            'actual representation/routing headers differ from reviewed SDK wire')
    actual = parse(body)
    require(canonical(actual) == canonical(expected), 'actual SDK HTTP body differs from reviewed closed request')
    require(actual['slug'] == REF and actual['newTitle'] == SLUG and actual['kernelExecutionType'] == 'QUICK_SAVE'
            and actual.get('competitionDataSources') == list(PRESERVED_COMPETITION_SOURCES)
            and actual['isPrivate'] is True and all(actual[k] is False for k in ('enableGpu', 'enableTpu', 'enableInternet'))
            and not any(k in actual for k in ('id', 'sessionTimeoutSeconds', 'machineShape', 'accelerator')),
            'source-only exact-slug QUICK_SAVE without hardware allocation or timeout required')
    return body


class CapturedRequest(BaseException):
    pass


def capture_prepared(req, wire, *, with_headers=False):
    from kagglesdk import KaggleClient
    from kagglesdk.kaggle_env import KaggleEnv
    captured = []
    with KaggleClient(env=KaggleEnv.PROD, verbose=False, api_token='OFFLINE-NOT-A-CREDENTIAL') as client:
        session = client.http_client()._session
        def stop(prepared, **kwargs):
            require(not captured, 'one offline prepared request required')
            body = wire_body(prepared, wire)
            captured.append((body, representation_headers(prepared, body)))
            raise CapturedRequest()
        session.send = stop
        try:
            client.kernels.kernels_api_client.save_kernel(req)
        except CapturedRequest:
            pass
    require(len(captured) == 1, 'SDK did not reach offline HTTP interception')
    return captured[0] if with_headers else captured[0][0]


def claim_path():
    # Fresh identity and directory; the old v1 claim is never read or changed.
    return ROOT.parent / '.arc-next-offline-quicksave-publication' / (RUN_ID + '-reservation.json')


def prepare(package, journal, assets_evidence, previous_source):
    journal = safe_path(journal)
    require(not journal.exists() and not claim_path().exists(), 'fresh unconsumed offlinev2 journal and identity required')
    req, wire, bindings = request(package)
    bindings.update(assets_info(assets_evidence, bindings['dataset_pins'], journal=journal),
                    **previous_info(previous_source, journal=journal))
    body, headers = capture_prepared(req, wire, with_headers=True)
    journal.mkdir(parents=True)
    atomic_bytes(journal / 'prepared-request.body', body, exclusive=True)
    write(journal / 'save-request.json', wire, exclusive=True)
    write(journal / 'prepared-request.headers.json', headers, exclusive=True)
    ledger = dict(format=FORMAT, run_id=RUN_ID, ref=REF, kernel_id=KERNEL_ID,
                  expected_previous_version=EXPECTED_PREVIOUS_VERSION, expected_next_version=EXPECTED_NEXT_VERSION,
                  execution_type='QUICK_SAVE', bindings=bindings, request_sha256=sha(canonical(wire)),
                  prepared_body_sha256=sha(body), prepared_headers=headers,
                  prepared_headers_sha256=sha(canonical(headers)), prepared_at=utc(), publication_reserved=0,
                  state='prepared-not-sent', events=[])
    write(journal / 'ledger.json', ledger, exclusive=True)
    return review_binding(ledger)


def review_binding(ledger):
    return dict(format=REVIEW_FORMAT, run_id=RUN_ID, ref=REF, kernel_id=KERNEL_ID,
                expected_previous_version=EXPECTED_PREVIOUS_VERSION, expected_next_version=EXPECTED_NEXT_VERSION,
                execution_type='QUICK_SAVE', **ledger['bindings'], request_sha256=ledger['request_sha256'],
                prepared_body_sha256=ledger['prepared_body_sha256'],
                prepared_headers=ledger['prepared_headers'], prepared_headers_sha256=ledger['prepared_headers_sha256'])


def verify_review(ledger, path):
    body = read_bytes(path, MAX_JSON)
    value, expected = parse(body), review_binding(ledger)
    require(type(value) is dict and set(value) == set(expected) | {'verdict', 'reviewer', 'reviewed_at'}
            and all(type(value.get(k)) is type(v) and value[k] == v for k, v in expected.items())
            and value['verdict'] == 'PASS' and type(value['reviewer']) is str and value['reviewer'].strip()
            and type(value['reviewed_at']) is str and value['reviewed_at'].strip(),
            'independent PASS must bind actual SDK wire, source implementation, assets evidence and v1 source')
    return sha(body)


def load_bound(package, journal):
    journal = safe_path(journal)
    ledger = read(journal / 'ledger.json', MAX_JSON)
    req, wire, bindings = request(package)
    original = ledger['bindings']
    bindings.update(assets_info(original['assets_evidence_path'], bindings['dataset_pins'], journal=journal),
                    **previous_info(original['previous_source_path'], journal=journal))
    require(ledger['format'] == FORMAT and ledger['run_id'] == RUN_ID and ledger['ref'] == REF
            and ledger['kernel_id'] == KERNEL_ID and type(ledger['kernel_id']) is int
            and ledger['expected_previous_version'] == EXPECTED_PREVIOUS_VERSION
            and type(ledger['expected_previous_version']) is int
            and ledger['expected_next_version'] == EXPECTED_NEXT_VERSION
            and type(ledger['expected_next_version']) is int and ledger['execution_type'] == 'QUICK_SAVE'
            and ledger['bindings'] == bindings and ledger['request_sha256'] == sha(canonical(wire))
            and canonical(read(journal / 'save-request.json')) == canonical(wire)
            and ledger['prepared_headers'] == read(journal / 'prepared-request.headers.json', MAX_JSON)
            and ledger['prepared_headers_sha256'] == sha(canonical(ledger['prepared_headers']))
            and ledger['prepared_body_sha256'] == sha(read_bytes(journal / 'prepared-request.body', MAX_NOTEBOOK * 2))
            and canonical(parse(read_bytes(journal / 'prepared-request.body', MAX_NOTEBOOK * 2))) == canonical(wire),
            'immutable package, source implementation, assets, v1 evidence or actual prepared request changed')
    return ledger, req, wire


def source_response(client, destination, *, ref=REF):
    """Exact-ref SOURCE with v2-local header guards; old v1 code is untouched."""
    require(ref == REF, 'only the exact pilot SOURCE is permitted')
    session = bounded_session(client)
    original = session.send
    def checked_send(prepared, **kwargs):
        require(prepared.method == 'POST' and prepared.url == SOURCE_URL, 'only exact SOURCE endpoint permitted')
        body = prepared.body.encode('utf-8') if type(prepared.body) is str else prepared.body
        require(type(body) is bytes and len(body) <= MAX_JSON, 'bounded SOURCE request body required')
        representation_headers(prepared, body)
        return original(prepared, **kwargs)
    session.send = checked_send
    try:
        return _source_response(client, destination, ref=ref)
    finally:
        session.send = original


def confirm_previous(client, destination, bindings):
    evidence = source_response(client, destination, ref=REF)
    require(evidence['http_status'] == 200, 'exact v1 SOURCE denied or failed; no save')
    raw = read(destination, MAX_NOTEBOOK * 2)
    nb = source_identity(raw, EXPECTED_PREVIOUS_VERSION, [],
                         competition_sources=list(PRESERVED_COMPETITION_SOURCES))
    require(bindings['expected_live_predecessor_competition_sources'] == list(PRESERVED_COMPETITION_SOURCES)
            and bindings['historical_previous_competition_sources'] == []
            and sha(raw['blob']['source'].encode('utf-8')) == bindings['previous_source_text_sha256']
            and sha(canonical(nb)) == bindings['previous_notebook_sha256']
            and sha(canonical(nb['cells'])) == bindings['previous_all_cells_sha256'],
            'live v1 source differs from preserved exact v1 evidence; no save')
    return dict(evidence, previous_version=EXPECTED_PREVIOUS_VERSION, kernel_id=KERNEL_ID,
                previous_source_verified=True, all_cells_sha256=sha(canonical(nb['cells'])),
                source_text_sha256=sha(raw['blob']['source'].encode('utf-8')),
                preserved_competition_sources=list(PRESERVED_COMPETITION_SOURCES))


def receipt_is_accepted(raw, typed):
    allowed = {'ref', 'url', 'versionNumber', 'kernelId', 'error', 'invalidTags',
               'invalidDatasetSources', 'invalidKernelSources', 'invalidCompetitionSources', 'invalidModelSources'}
    require(type(raw) is dict and set(raw) <= allowed, 'closed SaveKernel receipt required')
    require(raw.get('ref') in (REF, '/code/' + REF) and raw.get('url') == PUBLIC_URL
            and type(raw.get('versionNumber')) is int and raw['versionNumber'] == EXPECTED_NEXT_VERSION
            and type(raw.get('kernelId')) is int and raw['kernelId'] == KERNEL_ID,
            'receipt must identify exact same pilot ID137630087/version2')
    require(not raw.get('error') and not any(raw.get(k) for k in allowed if k.startswith('invalid')),
            'provider rejected save or a version-pinned Dataset source')
    require(typed.ref == raw['ref'] and typed.url == PUBLIC_URL
            and type(typed.version_number) is int and typed.version_number == EXPECTED_NEXT_VERSION
            and type(typed.kernel_id) is int and typed.kernel_id == KERNEL_ID and not typed.error,
            'raw and official typed receipt identity disagree')
    return KERNEL_ID


def verify_source_value(raw, package):
    from tools.stage_arc_next_offline import FLAGS
    expected, meta, _, bindings = package_info(package)
    nb = source_identity(raw, EXPECTED_NEXT_VERSION, meta['dataset_sources'],
                         competition_sources=list(PRESERVED_COMPETITION_SOURCES))
    assert_inert(nb, FLAGS)
    require(canonical(nb['cells']) == canonical(expected['cells']), 'SOURCE all cells differ from prepared notebook')
    require(nb.get('nbformat') == expected['nbformat'] and nb.get('nbformat_minor') == expected['nbformat_minor']
            and all(nb.get('metadata', {}).get(k) == v for k, v in expected['metadata'].items()),
            'SOURCE notebook structure or bound Dataset pins differ')
    save_type = nb.get('metadata', {}).get('kaggle', {}).get('SaveType')
    return dict(ref=REF, url=PUBLIC_URL, kernel_id=KERNEL_ID, version=EXPECTED_NEXT_VERSION,
                source_digest=bindings['source_digest'], all_cells_sha256=bindings['all_cells_sha256'],
                source_only_verified=True, private_verified=True, dataset_versions_verified=True,
                preserved_competition_sources=list(PRESERVED_COMPETITION_SOURCES),
                preserved_competition_attachment_verified=True, competition_data_use_authorized=False,
                dataset_pins=bindings['dataset_pins'], source_outputs_empty=True,
                owner_start_default_false_verified=True, provider_save_type=save_type,
                provider_save_type_attested=save_type is not None, runtime_state_attested=False,
                runtime_state_queried=False, gpu_allocation_queried=False, automatic_run_requested=False)


def claim_value(ledger, review_sha, reserved_at):
    return dict(run_id=RUN_ID, ref=REF, kernel_id=KERNEL_ID,
                expected_previous_version=EXPECTED_PREVIOUS_VERSION, expected_next_version=EXPECTED_NEXT_VERSION,
                prepared_body_sha256=ledger['prepared_body_sha256'],
                prepared_headers_sha256=ledger['prepared_headers_sha256'], bindings_sha256=sha(canonical(ledger['bindings'])),
                review_sha256=review_sha, reserved_at=reserved_at)


def verify_accepted_receipt(journal, ledger):
    require(ledger.get('accepted') is True and ledger.get('publication_reserved') == 1
            and len(ledger.get('events', [])) == 1, 'accepted single-save ledger required')
    event = ledger['events'][0]
    raw_body = read_bytes(journal / 'save-receipt.raw.json', MAX_JSON)
    typed = read(journal / 'save-receipt.typed.json', MAX_JSON)
    identity = SimpleNamespace(ref=typed.get('ref'), url=typed.get('url'),
        version_number=typed.get('versionNumber'), kernel_id=typed.get('kernelId'), error=typed.get('error'))
    receipt_is_accepted(parse(raw_body), identity)
    require(event.get('action') == 'SaveKernel' and event.get('execution_type') == 'QUICK_SAVE'
            and event.get('sends') == 1 and event.get('outcome') == 'accepted'
            and event.get('raw_receipt_sha256') == sha(raw_body) and event.get('http_status') == 200
            and ledger.get('provider_version') == EXPECTED_NEXT_VERSION
            and read(claim_path(), MAX_JSON) == claim_value(ledger, event['review_sha256'], event['reserved_at']),
            'accepted v2 receipt, durable new claim and exact bindings must remain unchanged')


def verify_source(package, journal):
    """SOURCE-only readback may be repeated after accepted v2; never resend."""
    journal = safe_path(journal)
    with locked(journal):
        ledger, _, _ = load_bound(package, journal)
        verify_accepted_receipt(journal, ledger)
        index = ledger.get('source_reads_reserved', 0)
        ledger['source_reads_reserved'] = index + 1
        write(journal / 'ledger.json', ledger)
        destination = journal / f'post-save-source-{index:03d}.json'
        with official_client() as client:
            evidence = source_response(client, destination, ref=REF)
        require(evidence['http_status'] == 200, 'v2 SOURCE verification failed; never resend SaveKernel')
        result = verify_source_value(read(destination, MAX_NOTEBOOK * 2), package)
        result.update(primary_sha256=evidence['body_sha256'], observed_at=evidence['observed_at'],
                      request_execution_type='QUICK_SAVE', actual_wire_quicksave_verified=True,
                      prepared_body_sha256=ledger['prepared_body_sha256'],
                prepared_headers=ledger['prepared_headers'], prepared_headers_sha256=ledger['prepared_headers_sha256'])
        write(journal / f'source-verification-{index:03d}.json', result, exclusive=True)
        ledger.update(state='offline-v2-private-quicksave-source-verified', source_verified=True)
        write(journal / 'ledger.json', ledger)
        return result


def publish(package, journal, review):
    journal = safe_path(journal)
    with locked(journal):
        ledger, req, wire = load_bound(package, journal)
        require(ledger['publication_reserved'] == 0 and ledger['state'] == 'prepared-not-sent'
                and ledger['events'] == [] and not claim_path().exists(),
                'offlinev2 publication already reserved or journal is not pristine; no retry')
        review_sha = verify_review(ledger, review)
        with official_client() as client:
            before = confirm_previous(client, journal / 'pre-send-source.json', ledger['bindings'])
            fresh, _, fresh_wire = load_bound(package, journal)
            require(fresh == ledger and fresh_wire == wire and verify_review(fresh, review) == review_sha,
                    'package, assets, source or review changed during exact v1 source check')
            event = dict(action='SaveKernel', execution_type='QUICK_SAVE', reserved_at=utc(), sends=0,
                         review_sha256=review_sha, previous_source=before, outcome='reserved-unsent')
            write(claim_path(), claim_value(ledger, review_sha, event['reserved_at']), exclusive=True)
            ledger.update(publication_reserved=1, state='reserved-unknown')
            ledger['events'].append(event)
            write(journal / 'ledger.json', ledger)
            session = bounded_session(client)
            original = session.send
            def send(prepared, **kwargs):
                body = wire_body(prepared, wire, ledger['prepared_headers'])
                fresh_ledger, _, _ = load_bound(package, journal)
                require(fresh_ledger == ledger and verify_review(fresh_ledger, review) == review_sha,
                        'immutable package/assets/review changed immediately before save')
                require(read(claim_path(), MAX_JSON) == claim_value(ledger, review_sha, event['reserved_at']),
                        'durable one-send reservation changed')
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(before['observed_at'])).total_seconds()
                require(0 <= age <= 300, 'exact v1 SOURCE observation expired before save')
                require(sha(body) == ledger['prepared_body_sha256'] and event['sends'] == 0,
                        'actual prepared SDK wire changed or duplicate save attempted')
                event.update(sends=1, outcome='send-started-unknown')
                write(journal / 'ledger.json', ledger)
                kwargs.update(timeout=(15, 120), allow_redirects=False, stream=True)
                response = original(prepared, **kwargs)
                try:
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        require(len(body) <= MAX_JSON, 'bounded SaveKernel receipt required')
                    atomic_bytes(journal / 'save-receipt.raw.json', bytes(body), exclusive=True)
                    event.update(raw_receipt_sha256=sha(bytes(body)), http_status=response.status_code)
                    write(journal / 'ledger.json', ledger)
                    response._content = bytes(body)
                    response._content_consumed = True
                    require(response.status_code == 200, 'v2 save failed; fresh identity frozen')
                    parse(bytes(body))
                    return response
                finally:
                    response.close()
            session.send = send
            try:
                response = client.kernels.kernels_api_client.save_kernel(req)
                receipt_is_accepted(read(journal / 'save-receipt.raw.json', MAX_JSON), response)
                require(event['sends'] == 1, 'exactly one completed offlinev2 save required')
                write(journal / 'save-receipt.typed.json', response.to_dict(), exclusive=True)
                ledger.update(state='accepted-source-unverified', accepted=True, provider_version=EXPECTED_NEXT_VERSION)
                event.update(outcome='accepted', completed_at=utc())
                write(journal / 'ledger.json', ledger)
            except BaseException as error:
                ledger.update(state='frozen-uncertain-no-retry', accepted=False)
                event.update(outcome='failed-or-uncertain-no-retry', error_type=type(error).__name__, completed_at=utc())
                write(journal / 'ledger.json', ledger)
                raise RuntimeError('offlinev2 QUICK_SAVE failed or uncertain; identity frozen; no duplicate send') from None
            finally:
                session.send = original
    return verify_source(package, journal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'prepare', 'publish', 'verify-source'))
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--assets-evidence', type=Path)
    parser.add_argument('--previous-source', type=Path)
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    if args.action == 'inspect':
        result = inspect(args.package)
    else:
        require(args.journal is not None, 'fresh offlinev2 transport journal required')
        if args.action == 'prepare':
            require(args.assets_evidence is not None and args.previous_source is not None,
                    'actual three-Dataset evidence and preserved exact v1 SOURCE required')
            result = prepare(args.package, args.journal, args.assets_evidence, args.previous_source)
        elif args.action == 'publish':
            require(args.review is not None, 'independent PASS actual-wire review required')
            result = publish(args.package, args.journal, args.review)
        else:
            result = verify_source(args.package, args.journal)
    print(canonical(result).decode('utf-8'))


if __name__ == '__main__':
    main()

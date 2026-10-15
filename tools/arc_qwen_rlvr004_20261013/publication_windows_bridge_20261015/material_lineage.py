"""Read-only collector-only succession of one completed run008 recovery context.

The caller must obtain receipt_descriptor from its actual authenticated action
review. A receipt, a PASS label, and this validator never grant publication
permission. Fresh independent runtime/material reviews are assembler inputs;
every other changed candidate byte is reconstructed below, without importing or
executing candidate Python, notebooks, finalizers, or the assembler. Historical
f5 eligibility and current publication-state extensions remain separate gates.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

FORMAT = 'irisx/run008-collector-material-lineage-v1'
COMPARISON_FORMAT = 'irisx/run008-collector-rebuild-comparison-v1'
ASSEMBLER_SHA256 = 'ba1b94cfcf4ff55d52a85e9508490039accb66f67f8d323085fd7df64b9d489e'
SOURCE_SHA256 = 'c61025e67354272099e40941cadcd77202964846d9a4c42c51a1817f77bb661b'
ARCHIVE_SHA256 = '4d8b414bd35ca79a2eaaec7042880966879ed13bdeaf96762eaee7932ee1de4c'
FILE_CAP = 128 * 1024**2
TREE_CAP = 512 * 1024**2
COUNT_CAP = 12000
CHANGED_FILES = frozenset(('ADMISSION-PROPOSAL.json',
    'code-payload/release/RUNTIME-REVIEW.json', 'code-payload/release/MATERIAL-REVIEW.json',
    'code-payload/manifest.json', 'code-upload.zip', 'notebook-release.json',
    'run008-inactive.ipynb', 'run008-active-template.ipynb',
    'consumer-release/material_review.json', 'consumer-release/release.json',
    'terminal-consumer/CONSUMER-OPERATOR.json', 'terminal-consumer/reviewed_entry.py',
    'publication-manifest.json', 'ASSEMBLY-INVENTORY.json'))
BINDING_KEYS = ('source_sha256', 'source_archive_sha256', 'environment_sha256',
    'normalized_source_contract_sha256', 'phase_policy_sha256', 'scorer_pins_sha256',
    'dataset_file_sha256', 'dataset_escrow_sha256', 'deployment_inventory',
    'collector_sha256', 'consumer_helper_inventory_sha256',
    'current_predecessor_observation_sha256', 'owner_direction_sha256', 'versions',
    'loader_overlay_manifest_sha256', 'loader_overlay_review_sha256',
    'assembler_source_sha256', 'source_proposal_inventory_sha256',
    'historical_candidate_inventory_sha256')


class LineageError(ValueError):
    """Fixed non-secret diagnostic; never include local artifact bodies."""


def _need(value, code):
    if not value:
        raise LineageError(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _desc(raw):
    return {'bytes': len(raw), 'sha256': _sha(raw)}


def _row(raw, name):
    return {'path': _relative(name), **_desc(raw)}


def _keys(value, names, code):
    _need(type(value) is dict and set(value) == set(names), code)


def _relative(name):
    _need(type(name) is str and 0 < len(name) <= 4096 and '\\' not in name
          and ':' not in name and not any(ord(c) < 32 for c in name), 'lineage_relative_path')
    path = PurePosixPath(name)
    _need(not path.is_absolute() and str(path) == name
          and all(part not in ('.', '..') for part in path.parts)
          and len(path.parts) <= 32, 'lineage_relative_path')
    return name


def _size_row(row):
    _keys(row, ('bytes', 'sha256'), 'lineage_size_descriptor_schema')
    _need(type(row['bytes']) is int and 0 <= row['bytes'] <= FILE_CAP
          and _is_sha(row['sha256']), 'lineage_size_descriptor_bounds')
    return row


def _primitive(p, name):
    return p[name] if type(p) is dict else getattr(p, name)


def _scan(p, root, *, count_cap=COUNT_CAP, tree_cap=TREE_CAP):
    """Bounded descriptor-relative walk; all files and directories stay ordinary."""
    root = _primitive(p, '_path')(root)
    identity = _primitive(p, '_identity')
    files, directories, total = {}, set(), 0
    with _primitive(p, '_directory')(root) as fd:
        def walk(directory, prefix):
            nonlocal total
            before = os.fstat(directory)
            names = sorted(os.listdir(directory))
            _need(len(names) <= count_cap, 'lineage_tree_entry_bound')
            for name in names:
                relative = _relative(prefix + name)
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    directories.add(relative)
                    _need(len(directories) <= count_cap, 'lineage_tree_directory_bound')
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                                    | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
                    try:
                        _need(identity(info) == identity(os.fstat(child)), 'lineage_directory_race')
                        walk(child, relative + '/')
                        _need(identity(info) == identity(os.stat(name, dir_fd=directory,
                              follow_symlinks=False)), 'lineage_directory_race')
                    finally:
                        os.close(child)
                else:
                    _need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                          and 0 <= info.st_size <= FILE_CAP, 'lineage_bounded_single_link_file')
                    _need(total + info.st_size <= tree_cap and len(files) < count_cap,
                          'lineage_tree_bound')
                    leaf = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                                   | os.O_NONBLOCK, dir_fd=directory)
                    with os.fdopen(leaf, 'rb') as stream:
                        _need(identity(info) == identity(os.fstat(leaf)), 'lineage_file_open_race')
                        raw = stream.read(info.st_size + 1)
                        after = os.stat(name, dir_fd=directory, follow_symlinks=False)
                        _need(len(raw) == info.st_size and identity(info) == identity(after)
                              == identity(os.fstat(leaf)), 'lineage_file_read_race')
                    files[relative] = raw
                    total += len(raw)
            _need(names == sorted(os.listdir(directory))
                  and identity(before) == identity(os.fstat(directory)), 'lineage_tree_race')
        walk(fd, '')
    expected_dirs = {parent.as_posix() for name in files for parent in PurePosixPath(name).parents
                     if parent.as_posix() != '.'}
    _need(directories == expected_dirs, 'lineage_empty_or_uninventoried_directory')
    return files


def _closed(p, candidate):
    _keys(candidate, ('root', 'inventory', 'manifest'), 'lineage_candidate_schema')
    root = _primitive(p, '_path')(candidate['root'])
    for key, name in (('inventory', 'ASSEMBLY-INVENTORY.json'),
                      ('manifest', 'publication-manifest.json')):
        _need(candidate[key].get('path') == str(root / name), 'lineage_candidate_descriptor_path')
        _primitive(p, '_verified')(candidate[key])
    files = _scan(p, root)
    obj = _primitive(p, '_json')
    inventory = obj(files['ASSEMBLY-INVENTORY.json'])
    _need(0 < len(inventory) < COUNT_CAP and set(files) == set(inventory) | {'ASSEMBLY-INVENTORY.json'},
          'lineage_candidate_closed_paths')
    for name, row in inventory.items():
        _relative(name)
        _need(_size_row(row) == _desc(files[name]), 'lineage_candidate_inventory_bytes')
    for key, name in (('inventory', 'ASSEMBLY-INVENTORY.json'),
                      ('manifest', 'publication-manifest.json')):
        _need(candidate[key] == {'path': str(root / name), **_desc(files[name])},
              'lineage_candidate_descriptor_changed')
    return files


def _zip(files):
    """Byte-identical metadata and compression to original assembler.zip_blobs."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(_relative(name), (2026, 10, 12, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw, compress_type=info.compress_type, compresslevel=9)
    return stream.getvalue()


def _review_links(obj, files, proposal):
    runtime_raw = files['code-payload/release/RUNTIME-REVIEW.json']
    material_raw = files['code-payload/release/MATERIAL-REVIEW.json']
    runtime, material = obj(runtime_raw), obj(material_raw)
    _need(runtime.get('format') == 'irisx/run008-runtime-review-v1' and runtime.get('status') == 'PASS',
          'lineage_runtime_review_schema')
    _need(material.get('format') == 'owned-rl-reviewed-material-v1'
          and material.get('status') == 'APPROVED'
          and material.get('runtime_review_sha256') == _sha(runtime_raw)
          and material.get('dataset_content_sha256') is None, 'lineage_material_review_schema')
    for review in (runtime, material):
        _need(review.get('proposal_sha256') == _sha(files['ADMISSION-PROPOSAL.json'])
              and all(review.get(key) == proposal[key] for key in BINDING_KEYS)
              and review.get('dataset_namespace_review_sha256') == _sha(files['review/SOLVER-NAMESPACE-REVIEW.json'])
              and type(review.get('baseline_unchanged_members')) is int
              and review['baseline_unchanged_members'] == 199
              and review.get('production_GPU_validation_passed') is False,
              'lineage_independent_review_binding')
    _need(files['consumer-release/material_review.json'] == material_raw,
          'lineage_material_review_copy')


def _notebook(obj, old_raw, old_release, new_release, loader):
    old = obj(old_raw)
    _need(old_raw == _encoded(old), 'lineage_notebook_not_canonical')
    def embedded(release):
        text = 'import json\nRELEASE = json.loads(' + repr(json.dumps(release, sort_keys=True, separators=(',', ':'))) + ')\n'
        text += "FINALIZED = json.loads('null')\nLOADER_SOURCE = " + repr(loader.decode('utf-8')) + '\n'
        return text.splitlines(keepends=True)
    cells = old.get('cells')
    _need(type(cells) is list and len(cells) == 4, 'lineage_notebook_cells')
    matches = [i for i, cell in enumerate(cells) if type(cell) is dict
               and cell.get('source') == embedded(old_release)]
    _need(matches == [2], 'lineage_notebook_unique_release_cell')
    _need(cells[2] == {'cell_type': 'code', 'metadata': {}, 'source': embedded(old_release),
                       'execution_count': None, 'outputs': []}, 'lineage_notebook_release_cell_schema')
    result = copy.deepcopy(old)
    result['cells'][2]['source'] = embedded(new_release)
    return _encoded(result)


def _reconstruct(p, old, new, collector_sha, *, _identity_pass=False):
    """Reproduce original assembler's collector-dependent closure in memory."""
    obj = _primitive(p, '_json')
    proposal = obj(old['ADMISSION-PROPOSAL.json'])
    if not _identity_pass:
        # Prove the old manifest's full descriptor graph too. Its frozen hash
        # must not hide stale links to an otherwise self-consistent inventory.
        _reconstruct(p, old, old, proposal['collector_sha256'], _identity_pass=True)
    _need(proposal.get('format') == 'irisx/run008-admission-proposal-v1'
          and _is_sha(proposal.get('collector_sha256')) and _is_sha(collector_sha)
          and (_identity_pass or proposal['collector_sha256'] != collector_sha),
          'lineage_distinct_collector_required')
    expected_proposal = copy.deepcopy(proposal)
    expected_proposal['collector_sha256'] = collector_sha
    _need(new['ADMISSION-PROPOSAL.json'] == _encoded(expected_proposal), 'lineage_only_collector_proposal_delta')
    _review_links(obj, old, proposal)
    _review_links(obj, new, expected_proposal)
    source = {n.removeprefix('producer-source/'): raw for n, raw in old.items() if n.startswith('producer-source/')}
    _need(len(source) == 259 and _sha(_canonical(sorted((n, _sha(b)) for n, b in source.items())))
          == proposal['source_sha256'] == SOURCE_SHA256, 'lineage_frozen_runtime259')
    _need(_sha(old['code-payload/source.zip']) == proposal['source_archive_sha256'] == ARCHIVE_SHA256,
          'lineage_frozen_source_archive')
    helpers = obj(old['terminal-consumer/CONSUMER-INVENTORY.json'])
    _keys(helpers, ('format', 'files'), 'lineage_helper_inventory_schema')
    _need(helpers['format'] == 'owned-rl-batched-consumer-helpers-v1' and type(helpers['files']) is dict
          and len(helpers['files']) == 21
          and _sha(old['terminal-consumer/CONSUMER-INVENTORY.json']) == proposal['consumer_helper_inventory_sha256'],
          'lineage_frozen_helpers21')
    for name, digest in helpers['files'].items():
        _relative(name)
        _need(_is_sha(digest) and _sha(old['terminal-consumer/' + name]) == digest,
              'lineage_helper_bytes')
    _need(set(name.removeprefix('terminal-consumer/') for name in old if name.startswith('terminal-consumer/'))
          == set(helpers['files']) | {'CONSUMER-INVENTORY.json', 'CONSUMER-OPERATOR.json', 'reviewed_entry.py'},
          'lineage_closed_consumer_helpers')
    expected = dict(old)
    expected['ADMISSION-PROPOSAL.json'] = new['ADMISSION-PROPOSAL.json']
    for name in ('code-payload/release/RUNTIME-REVIEW.json', 'code-payload/release/MATERIAL-REVIEW.json'):
        expected[name] = new[name]
    expected['consumer-release/material_review.json'] = new['code-payload/release/MATERIAL-REVIEW.json']
    manifest = obj(old['code-payload/manifest.json'])
    _need(manifest['source']['files'] == {n: _desc(b) for n, b in source.items()}
          and manifest['source']['source_sha256'] == SOURCE_SHA256
          and manifest['source']['archive'] == {'name': 'source.zip', **_desc(old['code-payload/source.zip'])},
          'lineage_code_source_binding')
    auxiliary = {n.removeprefix('code-payload/'): raw for n, raw in expected.items()
                 if n.startswith('code-payload/') and n not in ('code-payload/manifest.json', 'code-payload/source.zip')}
    old_auxiliary = {n.removeprefix('code-payload/'): _desc(raw) for n, raw in old.items()
                    if n.startswith('code-payload/') and n not in ('code-payload/manifest.json', 'code-payload/source.zip')}
    _need(manifest['auxiliary_files'] == old_auxiliary, 'lineage_code_auxiliary_binding')
    manifest['auxiliary_files'] = {n: _desc(b) for n, b in sorted(auxiliary.items())}
    expected['code-payload/manifest.json'] = _encoded(manifest)
    payload = {n.removeprefix('code-payload/'): raw for n, raw in expected.items() if n.startswith('code-payload/')}
    _need(_zip({n.removeprefix('code-payload/'): raw for n, raw in old.items()
                if n.startswith('code-payload/')}) == old['code-upload.zip'], 'lineage_original_zip_not_canonical')
    expected['code-upload.zip'] = _zip(payload)
    old_release = obj(old['notebook-release.json'])
    release = copy.deepcopy(old_release)
    _need(release['production_admitted'] is True and release['source_sha256'] == SOURCE_SHA256
          and release['source_archive_sha256'] == ARCHIVE_SHA256
          and release['deployment'] == proposal['deployment_inventory'], 'lineage_frozen_release_bindings')
    release.update(code_manifest_sha256=_sha(expected['code-payload/manifest.json']),
                   material_review_sha256=_sha(expected['consumer-release/material_review.json']))
    release['storage']['observed_assembled_source_copy_bytes'] = (sum(map(len, source.values()))
        + len(payload['source.zip']) + sum(map(len, auxiliary.values())))
    expected['notebook-release.json'] = _encoded(release)
    independent = obj(old['consumer-release/release.json'])
    _need(independent.get('source_sha256') == SOURCE_SHA256, 'lineage_independent_source_binding')
    for key in ('material_review', 'environment', 'phase_policy', 'owner_protocol'):
        _need(independent[key + '_sha256'] == _sha(old['consumer-release/' + key + '.json']),
              'lineage_original_independent_release_binding')
        independent[key + '_sha256'] = _sha(expected['consumer-release/' + key + '.json'])
    expected['consumer-release/release.json'] = _encoded(independent)
    operator = obj(old['terminal-consumer/CONSUMER-OPERATOR.json'])
    _need(operator['collector_entry_sha256'] == proposal['collector_sha256']
          and operator['release_sha256'] == _sha(old['consumer-release/release.json'])
          and operator['helper_inventory_sha256'] == proposal['consumer_helper_inventory_sha256'],
          'lineage_original_consumer_binding')
    operator.update(release_sha256=_sha(expected['consumer-release/release.json']), collector_entry_sha256=collector_sha)
    expected['terminal-consumer/CONSUMER-OPERATOR.json'] = _encoded(operator)
    before = ('REVIEWED_OPERATOR_PINS_SHA256 = ' + repr(_sha(old['terminal-consumer/CONSUMER-OPERATOR.json']))).encode()
    after = ('REVIEWED_OPERATOR_PINS_SHA256 = ' + repr(_sha(expected['terminal-consumer/CONSUMER-OPERATOR.json']))).encode()
    entry = old['terminal-consumer/reviewed_entry.py']
    _need(entry.count(before) == 1, 'lineage_original_entry_pin')
    expected['terminal-consumer/reviewed_entry.py'] = entry.replace(before, after, 1)
    for kind in ('inactive', 'active-template'):
        name = 'run008-' + kind + '.ipynb'
        expected[name] = _notebook(obj, old[name], old_release, release, payload['deployment/source_loader.py'])
    publication = obj(old['publication-manifest.json'])
    _need(publication.get('format') == 'irisx/qwen14b-rlvr-run008-publication-contract-v1'
          and publication['admission_proposal_sha256'] == _sha(old['ADMISSION-PROPOSAL.json'])
          and publication['runtime_source_sha256'] == SOURCE_SHA256
          and publication['source_review_only'] is False and publication['run_authorized'] is True
          and publication['release_runtime_finalized'] is True and publication['dispatch_ready'] is False
          and publication['provider_publication_completed'] is False, 'lineage_original_publication_binding')
    _need(len(publication['datasets']) == 1, 'lineage_single_dataset')
    dataset = publication['datasets'][0]
    upload = [_row(raw, name) for name, raw in sorted(payload.items())]
    material_rows = [row for row in upload if row['path'] != 'source.zip']
    dataset.update(root_manifest={'path': 'manifest.json', 'sha256': _sha(payload['manifest.json'])},
        upload_inventory=upload, upload_inventory_sha256=_sha(_canonical(upload) + b'\n'),
        transport_archive=_row(expected['code-upload.zip'], 'code-upload.zip'),
        expected_readback_layouts={'original-upload': upload,
            'extracted-root': sorted(material_rows + [_row(b, n) for n, b in source.items()], key=lambda row: row['path']),
            'extracted-source-directory': sorted(material_rows + [_row(b, 'source/' + n) for n, b in source.items()], key=lambda row: row['path'])})
    _need(len(publication['notebooks']) == 2
          and {r['path'] for r in publication['notebooks']} == {'run008-inactive.ipynb', 'run008-active-template.ipynb'},
          'lineage_notebook_scope')
    for row in publication['notebooks']:
        row.update(_desc(expected[row['path']]))
    publication.update(admission_proposal_sha256=_sha(expected['ADMISSION-PROPOSAL.json']),
        runtime_source_approval=_row(expected['code-payload/release/RUNTIME-REVIEW.json'], 'code-payload/release/RUNTIME-REVIEW.json'))
    publication['jit']['dependencies'] = [_row(expected[name], name) for name in ('notebook-release.json',
        'code-payload/deployment/notebook_builder.py', 'code-payload/deployment/source_loader.py')]
    for key in ('release', 'material_review', 'environment', 'phase_policy', 'owner_protocol'):
        name = 'consumer-release/' + key + '.json'
        publication['consumer_contract'][key] = _row(expected[name], name)
    publication['terminal_contract']['storage'] = release['storage']
    expected['publication-manifest.json'] = _encoded(publication)
    expected['ASSEMBLY-INVENTORY.json'] = _encoded({n: _desc(b) for n, b in sorted(expected.items())
                                                  if n != 'ASSEMBLY-INVENTORY.json'})
    _need(expected == new, 'lineage_noncanonical_successor_bytes')


def _frontier(p, frontier, eligibility, seal):
    _keys(frontier, ('root', 'files'), 'lineage_frontier_schema')
    root = _primitive(p, '_path')(frontier['root'])
    rows = frontier['files']
    _need(type(rows) is dict and len(rows) == 83, 'lineage_frozen_frontier83')
    roots = [name for name in rows if '/' not in name]
    events = [name for name in rows if re.fullmatch(r'events/[^/]+\.json', name)]
    _need(len(roots) == 17 and len(events) == 66 and len(roots) + len(events) == len(rows),
          'lineage_frozen_frontier_layout')
    _need(all(re.fullmatch(r'(?:native-bridge-[0-9a-f]{64}|recovery-epoch-[0-9a-f]{64}(?:-(?:capability|launch|eligibility|sealed))?)(?:\.claim|-journal)\.json', name)
              for name in roots), 'lineage_prepublication_frontier_required')
    _need(all(re.fullmatch(r'events/[0-9]+-[A-Za-z0-9_.-]+-[0-9a-f]{8}\.json', name)
              for name in events), 'lineage_prepublication_event_scope')
    # The publication-state gate owns the evolving namespace. Read only this
    # immutable subset here; future readback directories need not be closed yet.
    current = {}
    for name, row in rows.items():
        _relative(name)
        _size_row(row)
        current[name] = _primitive(p, '_verified')({'path': str(root / name), **row})
        value = _primitive(p, '_json')(current[name])
        _need(value.get('mutation_attempted', False) is False
              and value.get('operation') not in ('start_upload', 'upload_once', 'version', 'save'),
              'lineage_prepublication_commitment')
    for descriptor in (eligibility, seal):
        path = _primitive(p, '_path')(descriptor['path'])
        _need(path.parent == root and path.name in rows
              and descriptor == {'path': str(path), **rows[path.name]}, 'lineage_history_frontier_binding')
    seal_value = _primitive(p, '_json')(_primitive(p, '_verified')(seal))
    _need(seal_value.get('format') == 'irisx/recovery-completion-seal-v1'
          and seal_value.get('eligibility') == eligibility, 'lineage_historical_seal_binding')
    return {name: current[name] for name in rows}


def validate_lineage(p, c, configured, *, actual_descriptor, actual, original_descriptor,
                     original, eligibility_descriptor, receipt_descriptor, source_names):
    """Validate externally authenticated exact receipt; return no execution authority.

    p is the already-reviewed context module or its globals. No c callback is
    executed. The caller separately verifies original f5 eligibility and passes
    this result to its reviewed publication-state extension gate.
    """
    try:
        verified, obj, path = (_primitive(p, name) for name in ('_verified', '_json', '_path'))
        chain = []
        def document(row):
            raw = verified(row)
            chain.append((row, raw))
            return obj(raw)
        receipt = document(receipt_descriptor)
        _keys(receipt, ('format', 'original_configuration', 'successor_configuration',
            'historical_eligibility', 'historical_seal', 'original_candidate', 'successor_candidate',
            'state_frontier', 'operator_sources', 'canonical_rebuild'), 'lineage_receipt_schema')
        _need(receipt['format'] == FORMAT, 'lineage_receipt_format')
        _need(receipt['original_configuration'] == original_descriptor
              and receipt['successor_configuration'] == actual_descriptor
              and receipt['historical_eligibility'] == eligibility_descriptor,
              'lineage_receipt_context_binding')
        _need(document(actual_descriptor) == actual and document(original_descriptor) == original,
              'lineage_configuration_bytes')
        _need(actual_descriptor['sha256'] == configured.document_sha256
              and actual['repository_root'] == str(configured.repository_root)
              and actual['candidate_root'] == str(configured.candidate_root)
              and actual['publication_manifest_sha256'] == configured.publication_manifest_sha256
              and actual['state_root'] == str(configured.state_root) == str(c['STATE']),
              'lineage_actual_configuration_binding')
        normalized = copy.deepcopy(actual)
        for key in ('repository_root', 'candidate_root', 'publication_manifest_sha256'):
            normalized[key] = original[key]
        normalized['runtime']['interop_environment_sha256']['WSL_INTEROP'] = original['runtime']['interop_environment_sha256']['WSL_INTEROP']
        _need(_canonical(normalized) == _canonical(original), 'lineage_configuration_scope')
        for document_ in (original, actual):
            _keys(document_['runtime']['interop_environment_sha256'], ('WSL_INTEROP',), 'lineage_interop_scope')
            _need(_is_sha(document_['runtime']['interop_environment_sha256']['WSL_INTEROP']), 'lineage_interop_hash')
        old_binding, new_binding = receipt['original_candidate'], receipt['successor_candidate']
        for binding, config in ((old_binding, original), (new_binding, actual)):
            _need(binding['root'] == config['candidate_root']
                  and binding['manifest']['sha256'] == config['publication_manifest_sha256'],
                  'lineage_candidate_configuration_binding')
        old_root, new_root = path(old_binding['root']), path(new_binding['root'])
        _need(old_root != new_root and not old_root.is_relative_to(new_root)
              and not new_root.is_relative_to(old_root), 'lineage_distinct_candidate_roots')
        operational = [path(actual[key]) for key in ('state_root', 'scratch_root', 'evidence_root')]
        _need(all(not root.is_relative_to(item) and not item.is_relative_to(root)
                  for root in (old_root, new_root) for item in operational), 'lineage_candidate_operational_overlap')
        for binding in (old_binding, new_binding):
            _need(not path(receipt_descriptor['path']).is_relative_to(path(binding['root'])),
                  'lineage_receipt_must_be_external')
        _need(receipt['state_frontier']['root'] == actual['state_root'], 'lineage_state_root_binding')
        frozen = _frontier(p, receipt['state_frontier'], eligibility_descriptor, receipt['historical_seal'])
        old, new = _closed(p, old_binding), _closed(p, new_binding)
        _need(set(old) == set(new) and {n for n in old if old[n] != new[n]} == CHANGED_FILES,
              'lineage_exact_fourteen_changed_files')
        sources = receipt['operator_sources']
        names = set(source_names)
        _need(names and len(names) == len(source_names) and type(sources) is dict and set(sources) == names
              and {'material_lineage.py', 'rl_collect.py'} <= names, 'lineage_complete_operator_sources')
        source_root = path(actual['repository_root']) / 'tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015'
        for name, row in sources.items():
            _need(_relative(name) == name and '/' not in name and row['path'] == str(source_root / name),
                  'lineage_operator_source_path')
            document_raw = verified(row)
            chain.append((row, document_raw))
        collector_sha = sources['rl_collect.py']['sha256']
        comparison = document(receipt['canonical_rebuild'])
        _keys(comparison, ('format', 'assembler', 'original_inventory_sha256', 'successor_inventory_sha256',
            'independent_rebuild_inventory_sha256', 'unchanged_proposal_sha256', 'changed_files',
            'all_files_byte_identical', 'verifier'), 'lineage_rebuild_comparison_schema')
        _need(comparison['format'] == COMPARISON_FORMAT
              and comparison['assembler']['sha256'] == ASSEMBLER_SHA256
              and comparison['original_inventory_sha256'] == old_binding['inventory']['sha256']
              and comparison['successor_inventory_sha256'] == comparison['independent_rebuild_inventory_sha256']
                  == new_binding['inventory']['sha256']
              and comparison['all_files_byte_identical'] is True
              and comparison['changed_files'] == sorted(CHANGED_FILES), 'lineage_independent_rebuild_binding')
        assembler_raw = verified(comparison['assembler'])
        verifier_raw = verified(comparison['verifier'])
        chain.extend(((comparison['assembler'], assembler_raw), (comparison['verifier'], verifier_raw)))
        unchanged = obj(old['ADMISSION-PROPOSAL.json'])
        _need(unchanged['assembler_source_sha256'] == ASSEMBLER_SHA256, 'lineage_original_assembler_binding')
        unchanged.pop('collector_sha256')
        _need(comparison['unchanged_proposal_sha256'] == _sha(_canonical(unchanged)),
              'lineage_rebuild_unchanged_inputs')
        _reconstruct(p, old, new, collector_sha)
        # Recheck all dynamic trust inputs and closed trees after the complete
        # comparison, including concurrent replacements of self-consistent sets.
        for row, raw in chain:
            _need(verified(row) == raw, 'lineage_input_changed')
        _need(_closed(p, old_binding) == old and _closed(p, new_binding) == new,
              'lineage_candidate_changed')
        _need(_frontier(p, receipt['state_frontier'], eligibility_descriptor, receipt['historical_seal']) == frozen,
              'lineage_frontier_changed')
        return {'receipt_descriptor': copy.deepcopy(receipt_descriptor), 'candidate_root': str(new_root),
            'publication_manifest_sha256': new_binding['manifest']['sha256'],
            'state_frontier': copy.deepcopy(receipt['state_frontier'])}
    except (KeyError, TypeError, AttributeError, UnicodeError, RecursionError, OSError):
        raise LineageError('lineage_invalid_or_unavailable_input') from None

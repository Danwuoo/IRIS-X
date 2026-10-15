"""Synthetic offline closure fixtures, NOT real candidate or review acceptance.

Real local acceptance must independently rebuild the genuine candidate using the
original assembler, authenticate reviews and preserve the actual83-file frontier.
No fixture receipt is suitable for publication, native recovery or model work.
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import types
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


m = load('synthetic_material_lineage', ROOT / 'material_lineage.py')
p = load('synthetic_lineage_context_primitives', ROOT / 'context_continuation.py')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def desc(raw):
    return {'bytes': len(raw), 'sha256': sha(raw)}


def row(name, raw):
    return {'path': name, **desc(raw)}


def zip_bytes(files, stored=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', allowZip64=True) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 12, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            kind = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            archive.writestr(info, raw, compress_type=kind, compresslevel=None if stored else 9)
    return stream.getvalue()


def write(path, value):
    raw = value if type(value) is bytes else encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {'path': str(path), **desc(raw)}


def fixture_candidate(collector, source, helpers, *, assembler_sha, reviewer):
    """Independent tiny fixture encoder for the original assembler data graph."""
    source_sha = sha(m._canonical(sorted((name, sha(raw)) for name, raw in source.items())))
    archive = zip_bytes(source, stored=True)
    deployment = {name: b'# synthetic immutable deployment\n' for name in
                  ('source_loader.py', 'notebook_builder.py', 'launch_notebook.py', 'prepare_entry.py', 'parent_entry.py')}
    helper_raw = encoded({'format': 'owned-rl-batched-consumer-helpers-v1',
                          'files': {name: sha(raw) for name, raw in helpers.items()}})
    proposal = {key: sha(key.encode()) for key in m.BINDING_KEYS}
    proposal.update(format='irisx/run008-admission-proposal-v1', collector_sha256=collector,
        source_sha256=source_sha, source_archive_sha256=sha(archive),
        deployment_inventory={name: desc(raw) for name, raw in deployment.items()},
        consumer_helper_inventory_sha256=sha(helper_raw), assembler_source_sha256=assembler_sha,
        versions={'code_predecessor': 20, 'code': 21, 'notebook_predecessor': 39, 'inactive': 40, 'active': 41},
        dataset_escrow_sha256={'dev': 'd' * 64, 'holdout': 'e' * 64},
        scientific_policy={'A': 'SFT256', 'B': 'disjoint64', 'C': 'wall-matched-SFT', 'public_denominator': 167},
        historical_run007_clock={'epoch': 1791908053, 'deadline': 1791951253})
    proposal_raw = encoded(proposal)
    namespace = encoded({'format': 'irisx/run008-solver-namespace-review-v1', 'status': 'PASS',
        'path_substitutions': 2, 'reverse_byte_equality': True, 'escrow_bodies_read': False,
        'original_solver': desc(b'synthetic old solver'), 'projected_solver': desc(b'synthetic new solver'),
        'dataset_escrow_sha256': proposal['dataset_escrow_sha256'],
        'source_proposal_inventory_sha256': proposal['source_proposal_inventory_sha256'], 'synthetic_test_only': True})
    bindings = {key: proposal[key] for key in m.BINDING_KEYS}
    bindings.update(proposal_sha256=sha(proposal_raw), dataset_namespace_review_sha256=sha(namespace),
                    baseline_unchanged_members=199, production_GPU_validation_passed=False,
                    reviewer=reviewer, synthetic_test_only=True)
    runtime = encoded({'format': 'irisx/run008-runtime-review-v1', 'status': 'PASS', **bindings})
    material = encoded({'format': 'owned-rl-reviewed-material-v1', 'status': 'APPROVED', **bindings,
                        'runtime_review_sha256': sha(runtime), 'dataset_content_sha256': None})
    auxiliary = {'NOTICE.txt': b'SYNTHETIC ONLY\n', 'release/RUNTIME-REVIEW.json': runtime,
                 'release/MATERIAL-REVIEW.json': material,
                 **{'deployment/' + name: raw for name, raw in deployment.items()}}
    manifest = encoded({'source': {'source_sha256': source_sha, 'archive': {'name': 'source.zip', **desc(archive)},
                                  'files': {name: desc(raw) for name, raw in source.items()}},
                        'auxiliary_files': {name: desc(raw) for name, raw in auxiliary.items()}})
    payload = {**auxiliary, 'manifest.json': manifest, 'source.zip': archive}
    release = {'production_admitted': True, 'source_sha256': source_sha, 'source_archive_sha256': sha(archive),
               'deployment': proposal['deployment_inventory'], 'code_manifest_sha256': sha(manifest),
               'material_review_sha256': sha(material), 'storage': {
                   'observed_assembled_source_copy_bytes': sum(map(len, source.values())) + len(archive) + sum(map(len, auxiliary.values())),
                   'session_limit': 43200}, 'science': proposal['scientific_policy']}
    files = {'code-payload/' + name: raw for name, raw in payload.items()}
    files.update({'producer-source/' + name: raw for name, raw in source.items()})
    files.update({'terminal-consumer/' + name: raw for name, raw in helpers.items()})
    files.update({'ADMISSION-PROPOSAL.json': proposal_raw, 'notebook-release.json': encoded(release),
                  'review/SOLVER-NAMESPACE-REVIEW.json': namespace,
                  'terminal-consumer/CONSUMER-INVENTORY.json': helper_raw,
                  'consumer-release/material_review.json': material,
                  'historical-v31/preserved.json': encoded({'failure': 'preserved', 'clock': 123}),
                  'SOURCE-FREEZE.json': encoded({'source_sha256': source_sha}),
                  'OWNER-DIRECTION.json': encoded({'synthetic_test_only': True})})
    for key in ('environment', 'phase_policy', 'owner_protocol'):
        files['consumer-release/' + key + '.json'] = encoded({'synthetic_immutable': key})
    independent = {'format': 'owned-rl-independent-release-v1', 'source_sha256': source_sha,
                   **{key + '_sha256': sha(files['consumer-release/' + key + '.json'])
                      for key in ('material_review', 'environment', 'phase_policy', 'owner_protocol')}}
    files['consumer-release/release.json'] = encoded(independent)
    operator = {'collector_entry_sha256': collector, 'release_sha256': sha(files['consumer-release/release.json']),
                'helper_inventory_sha256': sha(helper_raw), 'source_sha256': source_sha,
                'source_archive_sha256': sha(archive)}
    files['terminal-consumer/CONSUMER-OPERATOR.json'] = encoded(operator)
    files['terminal-consumer/reviewed_entry.py'] = ('# synthetic immutable entry\nREVIEWED_OPERATOR_PINS_SHA256 = '
        + repr(sha(encoded(operator))) + '\n').encode()
    for kind in ('inactive', 'active-template'):
        embedded = 'import json\nRELEASE = json.loads(' + repr(json.dumps(release, sort_keys=True, separators=(',', ':'))) + ')\n'
        embedded += "FINALIZED = json.loads('null')\nLOADER_SOURCE = " + repr(deployment['source_loader.py'].decode()) + '\n'
        notebook = {'cells': [{'cell_type': 'markdown', 'source': ['Synthetic only'], 'metadata': {}},
            {'cell_type': 'code', 'source': ['MANUAL_START = False\n', 'PREDISPATCH_EPOCH = None\n'], 'metadata': {}, 'outputs': [], 'execution_count': None},
            {'cell_type': 'code', 'source': embedded.splitlines(keepends=True), 'metadata': {}, 'outputs': [], 'execution_count': None},
            {'cell_type': 'code', 'source': ['# unchanged inert fixture\n'], 'metadata': {}, 'outputs': [], 'execution_count': None}],
            'metadata': {'kind': kind}, 'nbformat': 4, 'nbformat_minor': 5}
        files['run008-' + kind + '.ipynb'] = encoded(notebook)
    upload = [row(name, raw) for name, raw in sorted(payload.items())]
    material_rows = [item for item in upload if item['path'] != 'source.zip']
    files['code-upload.zip'] = zip_bytes(payload)
    publication = {'format': 'irisx/qwen14b-rlvr-run008-publication-contract-v1',
        'admission_proposal_sha256': sha(proposal_raw), 'runtime_source_sha256': source_sha,
        'source_review_only': False, 'run_authorized': True, 'release_runtime_finalized': True,
        'dispatch_ready': False, 'provider_publication_completed': False,
        'runtime_source_approval': row('code-payload/release/RUNTIME-REVIEW.json', runtime),
        'datasets': [{'payload_root': 'code-payload', 'root_manifest': {'path': 'manifest.json', 'sha256': sha(manifest)},
            'upload_inventory': upload, 'upload_inventory_sha256': sha(m._canonical(upload) + b'\n'),
            'transport_archive': row('code-upload.zip', files['code-upload.zip']),
            'expected_readback_layouts': {'original-upload': upload,
                'extracted-root': sorted(material_rows + [row(n, b) for n, b in source.items()], key=lambda x: x['path']),
                'extracted-source-directory': sorted(material_rows + [row('source/' + n, b) for n, b in source.items()], key=lambda x: x['path'])}}],
        'notebooks': [row('run008-' + kind + '.ipynb', files['run008-' + kind + '.ipynb']) for kind in ('inactive', 'active-template')],
        'jit': {'dependencies': [row(name, files[name]) for name in ('notebook-release.json',
            'code-payload/deployment/notebook_builder.py', 'code-payload/deployment/source_loader.py')]},
        'consumer_contract': {key: row('consumer-release/' + key + '.json', files['consumer-release/' + key + '.json'])
                              for key in ('release', 'material_review', 'environment', 'phase_policy', 'owner_protocol')},
        'terminal_contract': {'storage': release['storage']}, 'science': proposal['scientific_policy']}
    files['publication-manifest.json'] = encoded(publication)
    files['ASSEMBLY-INVENTORY.json'] = encoded({name: desc(raw) for name, raw in files.items()})
    return files


class MaterialLineageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-material-lineage-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repository'
        self.source_root = self.repo / 'tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015'
        self.source_names = ('material_lineage.py', 'rl_collect.py', 'publication_state.py')
        self.sources = {name: write(self.source_root / name, ('# SYNTHETIC SOURCE ' + name + '\n').encode())
                        for name in self.source_names}
        source = {'runtime/file%03d.py' % i: ('# synthetic runtime %d\n' % i).encode() for i in range(259)}
        helpers = {'helper%02d.py' % i: ('# synthetic helper %d\n' % i).encode() for i in range(21)}
        assembler = ROOT.parent / 'admission_run008/assemble.py'
        self.assembler = {'path': str(assembler), **desc(assembler.read_bytes())}
        self.old = fixture_candidate('1' * 64, source, helpers, assembler_sha=self.assembler['sha256'], reviewer='old synthetic')
        self.new = fixture_candidate(self.sources['rl_collect.py']['sha256'], source, helpers,
                                     assembler_sha=self.assembler['sha256'], reviewer='new independent synthetic')
        proposal = json.loads(self.old['ADMISSION-PROPOSAL.json'])
        self.enterContext(mock.patch.object(m, 'SOURCE_SHA256', proposal['source_sha256']))
        self.enterContext(mock.patch.object(m, 'ARCHIVE_SHA256', proposal['source_archive_sha256']))
        self.old_root, self.new_root = self.root / 'old-candidate', self.root / 'new-candidate'
        self.persist(self.old_root, self.old)
        self.persist(self.new_root, self.new)
        self.state = self.root / 'state'
        for i in range(4):
            stem = 'native-bridge-' + str(i) * 64
            for suffix in ('.claim.json', '-journal.json'):
                write(self.state / (stem + suffix), {'synthetic_test_only': True, 'mutation_attempted': False})
        prefix = 'recovery-epoch-' + 'a' * 64
        for tail in ('', '-capability', '-launch', '-eligibility'):
            for suffix in ('.claim.json', '-journal.json'):
                write(self.state / (prefix + tail + suffix), {'synthetic_test_only': True})
        self.eligibility = self.descriptor(self.state / (prefix + '-eligibility.claim.json'))
        self.seal = write(self.state / (prefix + '-sealed.claim.json'),
                          {'format': 'irisx/recovery-completion-seal-v1', 'eligibility': self.eligibility, 'files': []})
        for i in range(66):
            write(self.state / ('events/%d-native-bridge-%s-%08x.json' % (1000 + i, '0' * 64, i)),
                  {'synthetic_test_only': True, 'mutation_attempted': False, 'sequence': i})
        self.frontier = {'root': str(self.state), 'files': {path.relative_to(self.state).as_posix(): desc(path.read_bytes())
                                                        for path in self.state.rglob('*') if path.is_file()}}
        self.original = {'repository_root': str(self.root / 'old-repository'), 'candidate_root': str(self.old_root),
            'publication_manifest_sha256': sha(self.old['publication-manifest.json']), 'state_root': str(self.state),
            'scratch_root': str(self.root / 'scratch'), 'evidence_root': str(self.root / 'evidence'),
            'runtime': {'interop_environment_sha256': {'WSL_INTEROP': '1' * 64}, 'identity': 'unchanged'},
            'science': {'public_denominator': 167}}
        self.actual = copy.deepcopy(self.original)
        self.actual.update(repository_root=str(self.repo), candidate_root=str(self.new_root),
                           publication_manifest_sha256=sha(self.new['publication-manifest.json']))
        self.actual['runtime']['interop_environment_sha256']['WSL_INTEROP'] = '2' * 64
        self.original_row = write(self.root / 'original.json', self.original)
        self.actual_row = write(self.root / 'actual.json', self.actual)
        self.config = types.SimpleNamespace(document_sha256=self.actual_row['sha256'], candidate_root=self.new_root,
            publication_manifest_sha256=self.actual['publication_manifest_sha256'], state_root=self.state,
            repository_root=self.repo)
        self.comparison = {'format': m.COMPARISON_FORMAT, 'assembler': self.assembler,
            'original_inventory_sha256': sha(self.old['ASSEMBLY-INVENTORY.json']),
            'successor_inventory_sha256': sha(self.new['ASSEMBLY-INVENTORY.json']),
            'independent_rebuild_inventory_sha256': sha(self.new['ASSEMBLY-INVENTORY.json']),
            'unchanged_proposal_sha256': sha(m._canonical({key: value for key, value in proposal.items() if key != 'collector_sha256'})),
            'changed_files': sorted(m.CHANGED_FILES), 'all_files_byte_identical': True,
            'verifier': write(self.root / 'independent-synthetic-verifier.py', b'# SYNTHETIC TEST ONLY\n')}
        comparison_row = write(self.root / 'comparison.json', self.comparison)
        self.receipt = {'format': m.FORMAT, 'original_configuration': self.original_row,
            'successor_configuration': self.actual_row, 'historical_eligibility': self.eligibility,
            'historical_seal': self.seal, 'original_candidate': self.binding(self.old_root),
            'successor_candidate': self.binding(self.new_root), 'state_frontier': self.frontier,
            'operator_sources': self.sources, 'canonical_rebuild': comparison_row}
        self.receipt_row = write(self.root / 'receipt.json', self.receipt)
        self.callbacks = {'STATE': self.state}
        for name in ('claim', 'journal', 'event', 'provider', 'configured', 'auth', 'load_runtime'):
            self.callbacks[name] = mock.Mock(side_effect=AssertionError('no side effects permitted'))

    def descriptor(self, path):
        return {'path': str(path), **desc(path.read_bytes())}

    def binding(self, root):
        return {'root': str(root), 'inventory': self.descriptor(root / 'ASSEMBLY-INVENTORY.json'),
                'manifest': self.descriptor(root / 'publication-manifest.json')}

    def persist(self, root, files):
        for name, raw in files.items():
            write(root / name, raw)

    def refresh_receipt(self):
        self.receipt_row = write(self.root / 'receipt.json', self.receipt)

    def validate(self):
        return m.validate_lineage(p, self.callbacks, self.config, actual_descriptor=self.actual_row,
            actual=self.actual, original_descriptor=self.original_row, original=self.original,
            eligibility_descriptor=self.eligibility, receipt_descriptor=self.receipt_row, source_names=self.source_names)

    def bind_changed_new(self):
        self.new['ASSEMBLY-INVENTORY.json'] = encoded({n: desc(b) for n, b in self.new.items() if n != 'ASSEMBLY-INVENTORY.json'})
        self.persist(self.new_root, self.new)
        self.actual['publication_manifest_sha256'] = sha(self.new['publication-manifest.json'])
        self.actual_row = write(self.root / 'actual.json', self.actual)
        self.config.document_sha256 = self.actual_row['sha256']
        self.config.publication_manifest_sha256 = self.actual['publication_manifest_sha256']
        self.receipt['successor_configuration'] = self.actual_row
        self.receipt['successor_candidate'] = self.binding(self.new_root)
        self.comparison['successor_inventory_sha256'] = self.comparison['independent_rebuild_inventory_sha256'] = sha(self.new['ASSEMBLY-INVENTORY.json'])
        self.receipt['canonical_rebuild'] = write(self.root / 'comparison.json', self.comparison)
        self.refresh_receipt()

    def test_exact_synthetic_collector_successor_without_effects(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('no process')), \
             mock.patch.object(socket, 'socket', side_effect=AssertionError('no network')), \
             mock.patch('builtins.exec', side_effect=AssertionError('no candidate Python')):
            result = self.validate()
        self.assertEqual(result['publication_manifest_sha256'], self.actual['publication_manifest_sha256'])
        self.assertEqual(result['state_frontier'], self.frontier)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        for value in self.callbacks.values():
            if isinstance(value, mock.Mock): value.assert_not_called()

    def test_frozen_frontier_can_coexist_with_postpublication_paths(self):
        (self.state / 'code-v21-readback/payload').mkdir(parents=True)
        write(self.state / 'active-finalized.ipynb', b'opaque publication-state gate owns this')
        write(self.state / 'native-bridge-later-journal.json', {'stage': 'closed'})
        self.validate()  # Dynamic-state admissibility is a separate mandatory gate.

    def test_authentic_native_manifest_identity_and_readiness_bracket_are_not_mutations(self):
        native = next(n for n in self.frontier['files'] if n.startswith('native-bridge-') and n.endswith('.claim.json'))
        write(self.state / native, {'format': 'irisx/windows-bridge-session-claim-v1',
                                   'publication_manifest_sha256': self.original['publication_manifest_sha256']})
        self.frontier['files'][native] = desc((self.state / native).read_bytes())
        event = next(n for n in self.frontier['files'] if n.startswith('events/'))
        replacement = 'events/9999-bracket-v39-before-12345678.json'
        (self.state / event).rename(self.state / replacement)
        self.frontier['files'][replacement] = self.frontier['files'].pop(event)
        self.refresh_receipt()
        self.validate()

    def test_namespace_review_bytes_cannot_change_with_passing_labels(self):
        self.new['review/SOLVER-NAMESPACE-REVIEW.json'] = encoded({'status': 'PASS', 'synthetic_test_only': True})
        self.bind_changed_new()
        with self.assertRaisesRegex(ValueError, 'fourteen_changed_files'): self.validate()

    def test_candidate_root_parent_symlink_rejected(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.new_root, target_is_directory=True)
        binding = self.binding(self.new_root)
        binding['root'] = str(alias)
        for key, name in (('manifest', 'publication-manifest.json'), ('inventory', 'ASSEMBLY-INVENTORY.json')):
            binding[key]['path'] = str(alias / name)
        with self.assertRaisesRegex(ValueError, 'directory_type'):
            m._closed(p, binding)

    def test_source_inventory_file_count_and_bytes_caps_rejected(self):
        with mock.patch.object(m, 'COUNT_CAP', 10), self.assertRaisesRegex(ValueError, 'closed_paths'):
            self.validate()
        with mock.patch.object(m, 'FILE_CAP', 10), self.assertRaisesRegex(ValueError, 'bounded_single_link_file'):
            m._scan(p, self.new_root)

    def test_json_schema_duplicate_and_nonfinite_rejected(self):
        for raw in (b'{"format":1,"format":2}', b'{"value":NaN}', b'{"value":1e999}'):
            self.receipt_row = write(self.root / 'receipt.json', raw)
            with self.assertRaises(ValueError): self.validate()

    def test_unknown_receipt_field_rejected(self):
        self.receipt['self_approved'] = True
        self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'receipt_schema'): self.validate()

    def test_missing_current_source_rejected(self):
        del self.receipt['operator_sources']['publication_state.py']
        self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'complete_operator_sources'): self.validate()

    def test_source_replaced_after_receipt_rejected(self):
        (self.source_root / 'rl_collect.py').write_bytes(b'# not reviewed\n')
        with self.assertRaisesRegex(ValueError, 'descriptor_changed'): self.validate()

    def test_old_collector_pin_cannot_migrate(self):
        proposal = json.loads(self.new['ADMISSION-PROPOSAL.json'])
        proposal['collector_sha256'] = '1' * 64
        self.new['ADMISSION-PROPOSAL.json'] = encoded(proposal)
        self.bind_changed_new()
        with self.assertRaisesRegex(ValueError, 'fourteen_changed_files|only_collector_proposal_delta'): self.validate()

    def test_science_change_in_proposal_rejected_despite_rebound_inventory(self):
        proposal = json.loads(self.new['ADMISSION-PROPOSAL.json'])
        proposal['scientific_policy']['public_denominator'] = 120
        self.new['ADMISSION-PROPOSAL.json'] = encoded(proposal)
        self.bind_changed_new()
        with self.assertRaisesRegex(ValueError, 'only_collector_proposal_delta'): self.validate()

    def test_notebook_code_metadata_and_extra_release_cells_rejected(self):
        original = self.new['run008-inactive.ipynb']
        for change in ('code', 'metadata', 'second_release'):
            notebook = json.loads(original)
            if change == 'code': notebook['cells'][1]['source'] = ['MANUAL_START = True\n']
            elif change == 'metadata': notebook['metadata']['unreviewed'] = True
            else: notebook['cells'][3] = copy.deepcopy(notebook['cells'][2])
            self.new['run008-inactive.ipynb'] = encoded(notebook)
            self.bind_changed_new()
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'noncanonical_successor_bytes'): self.validate()

    def test_runtime_review_proposal_binding_rejected(self):
        review = json.loads(self.new['code-payload/release/RUNTIME-REVIEW.json'])
        review['proposal_sha256'] = '0' * 64
        self.new['code-payload/release/RUNTIME-REVIEW.json'] = encoded(review)
        self.bind_changed_new()
        with self.assertRaisesRegex(ValueError, 'material_review_schema|independent_review_binding'): self.validate()

    def test_changed_unchanged_science_or_history_files_rejected(self):
        for name in ('producer-source/runtime/file000.py', 'terminal-consumer/helper00.py',
                     'historical-v31/preserved.json', 'review/SOLVER-NAMESPACE-REVIEW.json'):
            original = self.new[name]
            self.new[name] += b' '
            self.bind_changed_new()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'fourteen_changed_files'): self.validate()
            self.new[name] = original

    def test_zip_byte_change_with_same_members_rejected(self):
        self.new['code-upload.zip'] += b'extraneous trailing ZIP bytes'
        self.bind_changed_new()
        with self.assertRaisesRegex(ValueError, 'noncanonical_successor_bytes'): self.validate()

    def test_original_manifest_cannot_hide_stale_dependency_links(self):
        old = dict(self.old)
        manifest = json.loads(old['publication-manifest.json'])
        manifest['runtime_source_approval']['sha256'] = '0' * 64
        old['publication-manifest.json'] = encoded(manifest)
        old['ASSEMBLY-INVENTORY.json'] = encoded({name: desc(raw) for name, raw in old.items() if name != 'ASSEMBLY-INVENTORY.json'})
        with self.assertRaisesRegex(ValueError, 'noncanonical_successor_bytes'):
            m._reconstruct(p, old, self.new, self.sources['rl_collect.py']['sha256'])

    def test_original_zip_must_be_canonical(self):
        old = dict(self.old)
        old['code-upload.zip'] += b'comment'
        with self.assertRaisesRegex(ValueError, 'original_zip_not_canonical'):
            m._reconstruct(p, old, self.new, self.sources['rl_collect.py']['sha256'])

    def test_wrong_config_runtime_or_science_not_normalized(self):
        self.actual['runtime']['identity'] = 'changed-runtime'
        self.actual_row = write(self.root / 'actual.json', self.actual)
        self.config.document_sha256 = self.actual_row['sha256']
        self.receipt['successor_configuration'] = self.actual_row
        self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'configuration_scope'): self.validate()

    def test_frozen_state_edit_rejected(self):
        name = next(iter(self.frontier['files']))
        (self.state / name).write_bytes(b'{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'descriptor_changed'): self.validate()

    def test_frontier_publication_record_and_mutation_rejected(self):
        name = next(n for n in self.frontier['files'] if n.startswith('events/'))
        write(self.state / name, {'mutation_attempted': True, 'operation': 'save'})
        self.frontier['files'][name] = desc((self.state / name).read_bytes())
        self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'prepublication_commitment'): self.validate()

    def test_inventoried_path_traversal_rejected(self):
        inventory = json.loads(self.new['ASSEMBLY-INVENTORY.json'])
        inventory['../escape'] = desc(b'bad')
        self.new['ASSEMBLY-INVENTORY.json'] = encoded(inventory)
        self.persist(self.new_root, self.new)
        self.receipt['successor_candidate'] = self.binding(self.new_root)
        self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'closed_paths|relative_path'): self.validate()

    def test_symlink_hardlink_special_and_extra_files_rejected(self):
        path = self.new_root / 'unreviewed'
        for kind in ('symlink', 'hardlink', 'fifo', 'extra'):
            if kind == 'symlink': path.symlink_to(self.new_root / 'ADMISSION-PROPOSAL.json')
            elif kind == 'hardlink': os.link(self.new_root / 'ADMISSION-PROPOSAL.json', path)
            elif kind == 'fifo': os.mkfifo(path)
            else: path.write_bytes(b'not in closed inventory')
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.validate()
            path.unlink()

    def test_empty_uninventoried_candidate_directory_rejected(self):
        (self.new_root / 'empty').mkdir()
        with self.assertRaisesRegex(ValueError, 'empty_or_uninventoried'): self.validate()

    def test_self_consistent_receipt_replacement_mid_validation_rejected(self):
        original_scan = m._closed
        count = 0
        def racing(*args, **kwargs):
            nonlocal count
            result = original_scan(*args, **kwargs)
            count += 1
            if count == 2:
                raw = (self.root / 'receipt.json').read_bytes()
                (self.root / 'receipt.json').write_bytes(raw + b' ')
            return result
        with mock.patch.object(m, '_closed', side_effect=racing), self.assertRaisesRegex(ValueError, 'descriptor_changed'):
            self.validate()

    def test_candidate_changed_after_first_complete_scan_rejected(self):
        original = m._reconstruct
        def racing(*args, **kwargs):
            result = original(*args, **kwargs)
            (self.new_root / 'producer-source/runtime/file000.py').write_bytes(b'replaced')
            return result
        with mock.patch.object(m, '_reconstruct', side_effect=racing), self.assertRaisesRegex(ValueError, 'candidate_inventory_bytes'):
            self.validate()

    def test_independent_comparison_and_assembler_bindings_required(self):
        for key, value in (('all_files_byte_identical', False), ('independent_rebuild_inventory_sha256', '0' * 64),
                           ('unchanged_proposal_sha256', '0' * 64)):
            before = self.comparison[key]
            self.comparison[key] = value
            self.receipt['canonical_rebuild'] = write(self.root / 'comparison.json', self.comparison)
            self.refresh_receipt()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'independent_rebuild_binding|rebuild_unchanged_inputs'):
                self.validate()
            self.comparison[key] = before

    def test_numeric_bool_descriptor_rejected(self):
        self.receipt['operator_sources']['rl_collect.py']['bytes'] = True
        self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'descriptor_bounds'): self.validate()


if __name__ == '__main__':
    unittest.main()

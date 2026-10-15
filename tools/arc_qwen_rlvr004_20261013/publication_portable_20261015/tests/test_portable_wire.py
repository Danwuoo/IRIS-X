"""Self-contained synthetic portable review tests; no provider or emitted approval.

The old review tests depend on a missing ignored draft. These fixtures exercise
its source/JIT/clock/claim/wire boundaries without synthesizing historical facts.
A deterministic fixture finalizer only emits synthetic documents in temporary
scratch directories. Successful verifier results remain in memory.
"""
from contextlib import ExitStack, redirect_stdout
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).absolute().parents[4]
PACKAGE = ROOT / 'tools/arc_qwen_rlvr004_20261013/publication_portable_20261015'
VERIFIER = PACKAGE / 'verify_active_wire.py'
FROZEN_VERIFIER = ROOT / 'tools/arc_qwen_rlvr004_20261013/review_run008/verify_active_wire.py'
FROZEN_TRANSPORT = ROOT / 'tools/arc_qwen_rlvr004_20261013/publication_run008/rl_transport.py'
FROZEN_SHA = '955f6adec5f9608d96754e18ecc9958d1b9edd0998e226621dba18f14af75e00'
EPOCH = 1790000000
BASELINE = {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39, 'inactive': 40, 'active': 41}
ALTERNATE = {'code_predecessor': 24, 'code': 25, 'inactive_predecessor': 42, 'inactive': 43, 'active': 44}
SCRATCH = ROOT / '.irisx/portable-publication-tests'
SCRATCH.mkdir(parents=True, exist_ok=True)
v = types.ModuleType('portable_wire_test_verifier')
v.__file__ = str(VERIFIER)
exec(compile(VERIFIER.read_bytes(), str(VERIFIER), 'exec', dont_inherit=True,
             optimize=sys.flags.optimize), vars(v))

# Deliberately no production finalizer, provider, runtime, or model imports.
FINALIZER_SOURCE = b'''"""Synthetic fixture only; not production-reviewed bytes."""
import json

def finalize(root, epoch):
    settings = {
        'MANUAL_START': True, 'ENABLE_MODEL': True, 'PREDISPATCH_EPOCH': epoch,
        'NOTEBOOK_KIND': 'active-finalized', 'SESSION_SECONDS': 43200,
        'PROBE_SECONDS': 43200, 'EXECUTION_CUTOFF_SECONDS': 42000,
        'OUTER_CUTOFF_SECONDS': 42180, 'PROVIDER_RUNTIME_SECONDS': 42300,
        'OUTPUT_ROOT': '/kaggle/working/irisx-qwen14b-rlvr-20261013-run008',
        'SOURCE_PARENT': '/kaggle/working/irisx-qwen14b-rlvr-20261013-source008',
        'PROFILE': 'QWEN14B_RLVR12H',
    }
    source = ''.join(key + ' = ' + repr(value) + '\\n' for key, value in settings.items())
    notebook = {'cells': [{'cell_type': 'code', 'source': source}]}
    docs = {'active-finalized.ipynb': json.dumps(notebook).encode()}
    for name in ('original-request.json', 'operator.json', 'parent-private-scorer.json'):
        docs[name] = json.dumps({'synthetic_test_only': True, 'name': name, 'epoch': epoch}).encode()
    return docs
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def put(path, value):
    raw = value if isinstance(value, bytes) else v.encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}


def canonical_wire(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def producer_inactive_receipt(fixture, returned_sources):
    """Run the frozen receipt producer with offline metadata/readback doubles.

    Extract only this function so importing provider/auth/bootstrap code is
    impossible. The receipt dictionary is produced by frozen production code,
    not reconstructed by the test. Its numeric pins still come from the fixture.
    """
    tree = ast.parse(FROZEN_TRANSPORT.read_bytes())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'verify_notebook')
    module_ast = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    state = fixture.root / 'synthetic-producer-state'
    state.mkdir()
    source_path = fixture.candidate / 'synthetic-inactive.ipynb'
    raw = b'{"synthetic_test_only": true, "kind": "inactive"}\n'
    put(source_path, raw)
    notebook = {**fixture.manifest['notebooks'][0], 'path': source_path.name}
    claim = put(state / 'notebook-inactive.claim.json', {'synthetic_test_only': True})
    journal = {'expected_version': fixture.versions['inactive'],
               'manifest_sha256': fixture.pins['publication_manifest_sha256'],
               'save_calls': 1, 'claim_sha256': claim['sha256'], 'source_sha256': sha(raw),
               'predecessor': {'version': fixture.versions['inactive_predecessor']},
               'git_publication_completed': False, 'git_commit': None}
    put(state / 'notebook-inactive-journal.json', journal)
    snapshot = {'version': fixture.versions['inactive'], 'status': 'COMPLETE', 'source_sha256': sha(raw)}
    metadata = types.SimpleNamespace(model_data_sources=['qwen-lm/qwen-3/transformers/14b/1'],
                                     dataset_data_sources=returned_sources, to_dict=lambda: {'synthetic_test_only': True})
    namespace = {
        'STATE': state, 'REF': v.REF, 'Path': Path, 'need': v.need, 'sha': sha,
        'row': lambda manifest, role: notebook,
        'obj': lambda path: json.loads(path.read_bytes()), 'read': lambda path: path.read_bytes(),
        'file_sha': lambda path: sha(path.read_bytes()),
        'descriptor': lambda path: {'path': str(path), 'sha256': sha(path.read_bytes()), 'bytes': len(path.read_bytes())},
        'write_new': put, 'source_normalize': lambda source: source,
        'bracket': lambda provider, version, n: (snapshot, raw, metadata),
    }
    exec(compile(module_ast, str(FROZEN_TRANSPORT), 'exec', dont_inherit=True,
                 optimize=sys.flags.optimize), namespace)
    args = types.SimpleNamespace(manifest=str(fixture.candidate / 'publication-manifest.json'),
                                 manifest_sha=fixture.pins['publication_manifest_sha256'])
    return namespace['verify_notebook'](None, fixture.manifest, args, 'inactive')


class Fixture:
    def __init__(self, root, allocation=BASELINE):
        self.root = root
        self.candidate = root / 'candidate'
        self.state = root / 'state'
        self.state.mkdir(parents=True)
        self.versions = dict(allocation)
        entry = put(self.candidate / 'assembly/finalize.py', FINALIZER_SOURCE)
        entry['path'] = 'assembly/finalize.py'
        dependency = put(self.candidate / 'synthetic-dependency.json', {'synthetic_test_only': True})
        dependency['path'] = 'synthetic-dependency.json'
        sources = [v.DREF + '/' + str(allocation['code']), *v.NON_CODE_PINS]
        self.manifest = {
            'format': 'irisx/qwen14b-rlvr-run008-publication-contract-v1',
            'run_authorized': True, 'runtime_source_sha256': v.SOURCE,
            'consumer_contract': {'source_archive': {'sha256': v.ARCHIVE}},
            'datasets': [{'id': 12504696, 'reference': v.DREF, 'is_private': True,
                          'expected_predecessor_version': allocation['code_predecessor'],
                          'expected_version': allocation['code']}],
            'notebooks': [],
            'jit': {'maximum_dispatch_age_seconds': 60, 'output_documents': sorted(v.DOCS),
                    'entry': entry, 'dependencies': [dependency]},
        }
        for role, predecessor, successor in (('inactive', 'inactive_predecessor', 'inactive'),
                                             ('rlvr004', 'inactive', 'active')):
            self.manifest['notebooks'].append({
                'role': role, 'existing_notebook_id': 138123872, 'existing_notebook_reference': v.REF,
                'expected_predecessor_version': allocation[predecessor], 'expected_version': allocation[successor],
                'run_authorized': role == 'rlvr004', 'dataset_sources': list(sources),
                'sha256': 'b' * 64, 'docker_image': 'synthetic-reviewed-container',
            })
        md = put(self.candidate / 'publication-manifest.json', self.manifest)
        self.cfg = {'format': v.CONFIG_FORMAT, 'candidate_root': str(self.candidate),
                    'state_root': str(self.state), 'publication_manifest_sha256': md['sha256'],
                    'versions': dict(allocation)}
        cd = put(root / 'config.json', self.cfg)
        self.code_claim = {'expected_predecessor_version': allocation['code_predecessor'],
                           'expected_version': allocation['code'], 'manifest_sha256': md['sha256']}
        code_stem = 'dataset-code-v' + str(allocation['code'])
        code_claim_descriptor = put(self.state / (code_stem + '.claim.json'), self.code_claim)
        self.code_journal = {**self.code_claim, 'claim_sha256': code_claim_descriptor['sha256']}
        code_journal_descriptor = put(self.state / (code_stem + '-journal.json'), self.code_journal)
        bracket = {'id': 12504696, 'ref': v.DREF, 'version': allocation['code'], 'private': True}
        self.code = {'dataset_id': 12504696, 'version': allocation['code'], 'is_private': True,
                     'exact_byte_roundtrip': True, 'manifest_sha256': md['sha256'],
                     'before': dict(bracket), 'after': dict(bracket),
                     'claim_sha256': code_claim_descriptor['sha256'],
                     'journal_sha256': code_journal_descriptor['sha256']}
        self.inactive = {'kernel_id': 138123872, 'reference': v.REF, 'role': 'inactive',
                         'version': allocation['inactive'], 'status': 'COMPLETE',
                         'normalized_source_exact': True, 'manifest_sha256': md['sha256'],
                         'predecessor': {'version': allocation['inactive_predecessor']},
                         'snapshot': {'version': allocation['inactive'], 'status': 'COMPLETE'},
                         'dataset_sources_returned': ['/'.join(source.split('/')[:2]) for source in sources]}
        cod = put(self.code_path, self.code)
        ind = put(self.state / 'notebook-inactive-receipt.json', self.inactive)
        self.pins = {
            'format': v.FORMAT, 'status': 'SOURCE_AND_PRELAUNCH_READBACKS_REVIEWED',
            # Mimics admission only inside this synthetic fixture. Never persisted as approval.
            'synthetic_test_only': False, 'verifier_sha256': sha(VERIFIER.read_bytes()),
            'candidate_root': str(self.candidate), 'state_root': str(self.state),
            'versions': dict(allocation), 'publication_manifest_sha256': md['sha256'],
            'local_config_sha256': cd['sha256'], 'prelaunch_files': {'local_config': cd},
            'code_receipt_sha256': cod['sha256'], 'inactive_receipt_sha256': ind['sha256'],
        }
        for key in ('material_approval_sha256', 'transport_review_sha256', 'monitor_review_sha256',
                    'mount_receipt_sha256', 'persisted_audit_sha256'):
            self.pins[key] = 'a' * 64
        finalizer = types.ModuleType('synthetic_fixture_finalizer')
        exec(compile(FINALIZER_SOURCE, '<synthetic-fixture-finalizer>', 'exec'), vars(finalizer))
        self.docs = finalizer.finalize(self.candidate, EPOCH)
        descriptors = {name: put(self.state / name, raw) for name, raw in self.docs.items()}
        self.clock = {'dispatch_epoch': EPOCH, 'predispatch_epoch': EPOCH, 'deadline_epoch': EPOCH + 43200,
                      'global_deadline_epoch': EPOCH + 43200, 'execution_deadline_epoch': EPOCH + 42000,
                      'outer_deadline_epoch': EPOCH + 42180, 'provider_timeout_seconds': 42300}
        self.final = {'format': 'irisx/rlvr-finalization-v1', 'manifest_sha256': md['sha256'],
                      'template_sha256': 'b' * 64, 'finalized_sha256': sha(self.docs['active-finalized.ipynb']),
                      'documents': descriptors, 'finalizer_sha256': entry['sha256'], **self.clock}
        fd = put(self.state / 'finalization.json', self.final)
        self.wire = {
            'id': 138123872, 'slug': v.REF, 'new_title': 'IRIS-X Learning Agent 20261011',
            'text': self.docs['active-finalized.ipynb'].decode(), 'language': 'python', 'kernel_type': 'notebook',
            'dataset_data_sources': sources, 'model_data_sources': ['qwen-lm/qwen-3/transformers/14b/1'],
            'competition_data_sources': ['arc-prize-2026-arc-agi-3'], 'kernel_data_sources': [],
            'is_private': True, 'enable_gpu': True, 'enable_tpu': False, 'enable_internet': False,
            'docker_image': 'synthetic-reviewed-container', 'kernel_execution_type': 1,
            'session_timeout_seconds': 42300, 'machine_shape': 'NvidiaRtxPro6000',
        }
        wd = put(self.state / 'notebook-rlvr004-wire.json', canonical_wire(self.wire))
        self.claim = {'stage': 'claimed', 'save_calls': 0, 'expected_version': allocation['active'],
                      'kernel_id': 138123872, 'reference': v.REF, 'role': 'rlvr004',
                      'predecessor': {'version': allocation['inactive'], 'status': 'COMPLETE'},
                      'manifest_sha256': md['sha256'], 'stop_after_submit_readback': False,
                      'provider_monitoring_authorized': True}
        for key in ('material_approval_sha256', 'transport_review_sha256', 'monitor_review_sha256',
                    'mount_receipt_sha256', 'persisted_audit_sha256', 'code_receipt_sha256', 'inactive_receipt_sha256'):
            self.claim[key] = self.pins[key]
        cld = put(self.state / 'notebook-rlvr004.claim.json', self.claim)
        self.journal = {**copy.deepcopy(self.claim), **self.clock, 'stage': 'wire_prepared',
                        'claim_sha256': cld['sha256'], 'source_sha256': sha(self.docs['active-finalized.ipynb']),
                        'wire_sha256': wd['sha256'], 'finalization_sha256': fd['sha256']}
        self.save_journal()

    @property
    def code_path(self):
        return self.state / ('dataset-code-v' + str(self.versions['code']) + '-receipt.json')

    def save_config(self):
        descriptor = put(self.root / 'config.json', self.cfg)
        self.pins['local_config_sha256'] = descriptor['sha256']
        self.pins['prelaunch_files']['local_config'] = descriptor

    def save_manifest(self):
        descriptor = put(self.candidate / 'publication-manifest.json', self.manifest)
        self.pins['publication_manifest_sha256'] = descriptor['sha256']

    def save_journal(self):
        put(self.state / 'notebook-rlvr004-journal.json', self.journal)

    def save_claim(self):
        descriptor = put(self.state / 'notebook-rlvr004.claim.json', self.claim)
        self.journal['claim_sha256'] = descriptor['sha256']
        self.save_journal()

    def verify(self, now=EPOCH + 2):
        descriptor = put(self.root / 'synthetic-pins.json', self.pins)
        with patch.object(v.time, 'time', return_value=now):
            return v.verify(descriptor['path'], descriptor['sha256'])


class PortableWireTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.tmp.name)
        self.counter = 0
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(self.tmp.cleanup)
        self.stack.enter_context(patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')))
        self.stack.enter_context(patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')))
        self.stack.enter_context(patch.object(subprocess, 'Popen', side_effect=AssertionError('subprocess forbidden')))
        self.f = self.fixture()

    def fixture(self, allocation=BASELINE):
        self.counter += 1
        return Fixture(self.root / str(self.counter), allocation)

    def test_frozen_source_provenance_and_distinct_schema(self):
        self.assertEqual(sha(FROZEN_VERIFIER.read_bytes()), FROZEN_SHA)
        self.assertIn(FROZEN_SHA, VERIFIER.read_text())
        self.assertNotEqual(v.FORMAT, 'irisx/run008-active-review-static-pins-v1')

    def test_baseline_and_alternate_exact_allocations(self):
        for allocation in (BASELINE, ALTERNATE):
            with self.subTest(allocation=allocation):
                f = self.fixture(allocation)
                result = f.verify()
                self.assertEqual(result['status'], 'PASS')
                self.assertEqual(result['format'], 'irisx/run008-active-wire-review-v1')
                self.assertEqual(result['versions'], allocation)
                self.assertEqual(result['numeric_notebook_version'], allocation['active'])
                self.assertEqual(result['static_review_pins_sha256'], sha((f.root / 'synthetic-pins.json').read_bytes()))
                self.assertEqual(result['prepared_journal_sha256'], sha((f.state / 'notebook-rlvr004-journal.json').read_bytes()))
                self.assertTrue(result['exact_four_document_reconstruction'])
                self.assertEqual(result['provider_calls'], 0)
                self.assertEqual(result['model_or_GPU_calls'], 0)
                self.assertFalse(result['production_GPU_validation_passed'])
                self.assertIsNone(result['scientific_result'])
                self.assertFalse((f.state / 'active-review.json').exists())

    def test_pins_require_all_five_exact_integer_versions(self):
        for field in BASELINE:
            for value in (True, False, float(BASELINE[field]), str(BASELINE[field]), 0, -1, None):
                with self.subTest(field=field, value=value):
                    f = self.fixture()
                    f.pins['versions'][field] = value
                    with self.assertRaisesRegex(ValueError, 'strict positive integer'):
                        f.verify()
        for change in ('missing', 'extra'):
            f = self.fixture()
            if change == 'missing':
                del f.pins['versions']['code_predecessor']
            else:
                f.pins['versions']['free_version'] = 999
            with self.assertRaisesRegex(ValueError, 'version schema'):
                f.verify()

    def test_nonconsecutive_or_unbound_allocation_rejected(self):
        for field in BASELINE:
            f = self.fixture()
            f.pins['versions'][field] += 1
            with self.assertRaisesRegex(ValueError, 'successor versions'):
                f.verify()
        self.f.pins['versions'] = dict(ALTERNATE)
        with self.assertRaisesRegex(ValueError, 'manifest code versions'):
            self.f.verify()

    def test_old_synthetic_and_changed_verifier_pins_rejected(self):
        for field, value, error in (
            ('format', 'irisx/run008-active-review-static-pins-v1', 'actual independently'),
            ('synthetic_test_only', True, 'actual independently'),
            ('verifier_sha256', FROZEN_SHA, 'verifier bytes changed'),
        ):
            f = self.fixture()
            f.pins[field] = value
            with self.assertRaisesRegex(ValueError, error):
                f.verify()

    def test_config_allocation_type_format_and_root_binding(self):
        for field in BASELINE:
            f = self.fixture()
            f.cfg['versions'][field] = float(BASELINE[field])
            f.save_config()
            with self.assertRaisesRegex(ValueError, 'strict positive integer'):
                f.verify()
        for key, value, error in (
            ('versions', ALTERNATE, 'local version allocation'),
            ('format', 'irisx/run008-native-operator-config-v1', 'portable local config'),
            ('candidate_root', str(self.root), 'local state binding'),
            ('state_root', str(self.root), 'local state binding'),
            ('publication_manifest_sha256', '0' * 64, 'local state binding'),
        ):
            f = self.fixture()
            f.cfg[key] = value
            f.save_config()
            with self.assertRaisesRegex(ValueError, error):
                f.verify()

    def test_manifest_versions_strict_in_every_role(self):
        for group, index in (('datasets', 0), ('notebooks', 0), ('notebooks', 1)):
            for field in ('expected_predecessor_version', 'expected_version'):
                for replacement in ('float', 'bool', 'other'):
                    f = self.fixture()
                    row = f.manifest[group][index]
                    old = row[field]
                    row[field] = float(old) if replacement == 'float' else True if replacement == 'bool' else old + 1
                    f.save_manifest()
                    with self.assertRaisesRegex(ValueError, 'manifest .* versions'):
                        f.verify()

    def test_manifest_exact_roles_identity_privacy_and_dataset_pins(self):
        mutations = [
            (lambda m: m['datasets'].append(copy.deepcopy(m['datasets'][0])), 'dataset role'),
            (lambda m: m['datasets'][0].update(id=12504696.0), 'dataset identity'),
            (lambda m: m['datasets'][0].update(reference='other/code'), 'dataset identity'),
            (lambda m: m['datasets'][0].update(is_private=False), 'dataset identity'),
            (lambda m: m['notebooks'].append(copy.deepcopy(m['notebooks'][0])), 'notebook roles'),
            (lambda m: m['notebooks'][1].update(role='inactive'), 'notebook roles'),
            (lambda m: m['notebooks'][0].update(existing_notebook_id=138123872.0), 'notebook identity'),
            (lambda m: m['notebooks'][1].update(existing_notebook_reference='other/notebook'), 'notebook identity'),
            (lambda m: m['notebooks'][0]['dataset_sources'].__setitem__(0, v.DREF + '/25'), 'dataset pins'),
            (lambda m: m['notebooks'][1]['dataset_sources'].__setitem__(1, v.NON_CODE_PINS[0] + '0'), 'dataset pins'),
        ]
        for mutation, error in mutations:
            f = self.fixture()
            mutation(f.manifest)
            f.save_manifest()
            with self.assertRaisesRegex(ValueError, error):
                f.verify()

    def test_actual_readback_versions_identities_and_privacy(self):
        for role, updates, error in (
            ('code', {'version': 25}, 'numeric code'), ('code', {'version': 21.0}, 'numeric code'),
            ('code', {'version': True}, 'numeric code'), ('code', {'dataset_id': 12504696.0}, 'numeric code'),
            ('code', {'is_private': False}, 'numeric code'), ('code', {'exact_byte_roundtrip': False}, 'numeric code'),
            ('inactive', {'version': 43}, 'inactive readback'), ('inactive', {'version': 40.0}, 'inactive readback'),
            ('inactive', {'version': True}, 'inactive readback'), ('inactive', {'kernel_id': 138123872.0}, 'inactive readback'),
            ('inactive', {'reference': 'other/notebook'}, 'inactive readback'), ('inactive', {'role': 'rlvr004'}, 'inactive readback'),
            ('inactive', {'status': 'RUNNING'}, 'inactive readback'), ('inactive', {'normalized_source_exact': False}, 'inactive readback'),
        ):
            with self.subTest(role=role, updates=updates):
                f = self.fixture()
                receipt = getattr(f, role)
                receipt.update(updates)
                path = f.code_path if role == 'code' else f.state / 'notebook-inactive-receipt.json'
                f.pins[role + '_receipt_sha256'] = put(path, receipt)['sha256']
                with self.assertRaisesRegex(ValueError, error):
                    f.verify()

    def test_frozen_producer_unversioned_identity_projection_and_permutations(self):
        for allocation in (BASELINE, ALTERNATE):
            expected = ['/'.join(value.split('/')[:2]) for value in
                        [v.DREF + '/' + str(allocation['code']), *v.NON_CODE_PINS]]
            for sources in (expected, list(reversed(expected))):
                f = self.fixture(allocation)
                receipt = producer_inactive_receipt(f, sources)
                self.assertEqual(receipt['dataset_sources_returned'], sources)
                digest = put(f.state / 'notebook-inactive-receipt.json', receipt)['sha256']
                f.pins['inactive_receipt_sha256'] = digest
                f.claim['inactive_receipt_sha256'] = digest
                f.journal['inactive_receipt_sha256'] = digest
                f.save_claim()
                self.assertEqual(f.verify()['numeric_notebook_version'], allocation['active'])

    def test_frozen_producer_changed_duplicate_missing_or_versioned_identity_rejected(self):
        expected = ['/'.join(value.split('/')[:2]) for value in [v.DREF + '/21', *v.NON_CODE_PINS]]
        for sources in ([*expected[:-1], 'other/identity'], [*expected[:-1], expected[0]], expected[:-1],
                        [v.DREF + '/21', *expected[1:]]):
            f = self.fixture()
            receipt = producer_inactive_receipt(f, sources)
            f.pins['inactive_receipt_sha256'] = put(f.state / 'notebook-inactive-receipt.json', receipt)['sha256']
            with self.assertRaisesRegex(ValueError, 'inactive predecessor snapshot and pins'):
                f.verify()

    def test_readback_brackets_predecessors_and_dataset_pins(self):
        for location in ('before', 'after'):
            for key, value in (('id', 12504696.0), ('ref', 'other/code'), ('version', 21.0),
                               ('version', 25), ('private', False)):
                f = self.fixture()
                f.code[location][key] = value
                f.pins['code_receipt_sha256'] = put(f.code_path, f.code)['sha256']
                with self.assertRaisesRegex(ValueError, 'code readback bracket'):
                    f.verify()
        for key, value in (
            ('predecessor', {'version': 42}), ('predecessor', {'version': 39.0}),
            ('snapshot', {'version': 43, 'status': 'COMPLETE'}),
            ('snapshot', {'version': 40.0, 'status': 'COMPLETE'}),
            ('snapshot', {'version': 40, 'status': 'RUNNING'}),
            ('dataset_sources_returned', [v.DREF + '/25', *v.NON_CODE_PINS]),
        ):
            f = self.fixture()
            f.inactive[key] = value
            f.pins['inactive_receipt_sha256'] = put(f.state / 'notebook-inactive-receipt.json', f.inactive)['sha256']
            with self.assertRaisesRegex(ValueError, 'inactive predecessor snapshot and pins'):
                f.verify()

    def test_code_claim_and_journal_allocation_are_hash_bound(self):
        for role in ('code_claim', 'code_journal'):
            for key in ('expected_predecessor_version', 'expected_version'):
                for replacement in ('changed', 'float', 'bool'):
                    f = self.fixture()
                    document = getattr(f, role)
                    old = document[key]
                    document[key] = old + 1 if replacement == 'changed' else float(old) if replacement == 'float' else True
                    claim = put(f.state / 'dataset-code-v21.claim.json', f.code_claim)
                    f.code_journal['claim_sha256'] = claim['sha256']
                    journal = put(f.state / 'dataset-code-v21-journal.json', f.code_journal)
                    f.code.update(claim_sha256=claim['sha256'], journal_sha256=journal['sha256'])
                    f.pins['code_receipt_sha256'] = put(f.code_path, f.code)['sha256']
                    with self.assertRaisesRegex(ValueError, 'code claim and journal allocation'):
                        f.verify()
        for name in ('dataset-code-v21.claim.json', 'dataset-code-v21-journal.json'):
            f = self.fixture()
            p = f.state / name
            p.write_bytes(p.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash or size'):
                f.verify()
        f = self.fixture()
        f.code_journal['claim_sha256'] = '0' * 64
        f.code['journal_sha256'] = put(f.state / 'dataset-code-v21-journal.json', f.code_journal)['sha256']
        f.pins['code_receipt_sha256'] = put(f.code_path, f.code)['sha256']
        with self.assertRaisesRegex(ValueError, 'actual code claim chain'):
            f.verify()

    def test_actual_readbacks_are_hash_bound_and_numeric_path_is_exact(self):
        for filename in ('dataset-code-v21-receipt.json', 'notebook-inactive-receipt.json'):
            f = self.fixture()
            p = f.state / filename
            p.write_bytes(p.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash or size'):
                f.verify()
        self.f.code_path.rename(self.f.state / 'dataset-code-v25-receipt.json')
        with self.assertRaises(FileNotFoundError):
            self.f.verify()

    def test_claim_and_journal_versions_identity_and_predecessor(self):
        for role in ('claim', 'journal'):
            for updates, error in (
                ({'expected_version': 44}, 'claim target'), ({'expected_version': 41.0}, 'claim target'),
                ({'expected_version': True}, 'claim target'), ({'kernel_id': 138123872.0}, 'claim target'),
                ({'reference': 'other/notebook'}, 'claim target'), ({'role': 'inactive'}, 'claim target'),
                ({'predecessor': {'version': 43, 'status': 'COMPLETE'}}, 'inactive predecessor'),
                ({'predecessor': {'version': 40.0, 'status': 'COMPLETE'}}, 'inactive predecessor'),
                ({'predecessor': {'version': True, 'status': 'COMPLETE'}}, 'inactive predecessor'),
                ({'predecessor': {'version': 40, 'status': 'RUNNING'}}, 'inactive predecessor'),
            ):
                f = self.fixture()
                getattr(f, role).update(updates)
                getattr(f, 'save_' + role)()
                with self.assertRaisesRegex(ValueError, error):
                    f.verify()

    def test_unsent_claim_and_journal_replay_rejected(self):
        for role in ('claim', 'journal'):
            for value in (1, False, 0.0):
                f = self.fixture()
                getattr(f, role)['save_calls'] = value
                getattr(f, 'save_' + role)()
                with self.assertRaisesRegex(ValueError, 'unsent one-attempt'):
                    f.verify()
            f = self.fixture()
            getattr(f, role)['stage'] = 'save_intent'
            getattr(f, 'save_' + role)()
            with self.assertRaisesRegex(ValueError, 'unsent one-attempt'):
                f.verify()
        self.f.journal['claim_sha256'] = '0' * 64
        self.f.save_journal()
        with self.assertRaisesRegex(ValueError, 'hash or size'):
            self.f.verify()

    def test_claim_prelaunch_receipts_and_monitoring_scope_cannot_change(self):
        for role in ('claim', 'journal'):
            for key in ('material_approval_sha256', 'transport_review_sha256', 'monitor_review_sha256',
                        'mount_receipt_sha256', 'persisted_audit_sha256', 'code_receipt_sha256', 'inactive_receipt_sha256'):
                f = self.fixture()
                getattr(f, role)[key] = '0' * 64
                getattr(f, 'save_' + role)()
                with self.assertRaisesRegex(ValueError, 'claim exact prelaunch receipts'):
                    f.verify()
            for key, value in (('stop_after_submit_readback', True), ('provider_monitoring_authorized', False)):
                f = self.fixture()
                getattr(f, role)[key] = value
                getattr(f, 'save_' + role)()
                with self.assertRaisesRegex(ValueError, 'monitoring scope'):
                    f.verify()

    def test_fresh_60_second_boundary_and_expiry_during_review(self):
        for now in (EPOCH, EPOCH + 60):
            self.assertEqual(self.f.verify(now)['status'], 'PASS')
        for now in (EPOCH - 1, EPOCH + 60.001, EPOCH + 61):
            with self.assertRaisesRegex(ValueError, 'fresh immutable'):
                self.f.verify(now)
        desc = put(self.f.root / 'synthetic-pins.json', self.f.pins)
        with patch.object(v.time, 'time', side_effect=[EPOCH + 59, EPOCH + 61]):
            with self.assertRaisesRegex(ValueError, 'expired during review'):
                v.verify(desc['path'], desc['sha256'])

    def test_all_original_clocks_are_strict_and_unchanged(self):
        for role in ('final', 'journal'):
            for field in self.f.clock:
                for replacement in ('float', 'bool', 'changed'):
                    f = self.fixture()
                    doc = getattr(f, role)
                    old = doc[field]
                    doc[field] = float(old) if replacement == 'float' else True if replacement == 'bool' else old + 1
                    filename = 'finalization.json' if role == 'final' else 'notebook-rlvr004-journal.json'
                    put(f.state / filename, doc)
                    with self.assertRaises(ValueError):
                        f.verify()

    def test_jit_document_paths_bytes_and_four_document_set(self):
        for name in v.DOCS:
            f = self.fixture()
            p = f.state / name
            p.write_bytes(p.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash or size'):
                f.verify()
            f = self.fixture()
            f.final['documents'][name]['path'] = str(f.root / name)
            put(f.state / 'finalization.json', f.final)
            with self.assertRaisesRegex(ValueError, 'original JIT path'):
                f.verify()
        self.f.final['documents']['unexpected.json'] = self.f.final['documents']['operator.json']
        put(self.f.state / 'finalization.json', self.f.final)
        with self.assertRaisesRegex(ValueError, 'closed actual JIT'):
            self.f.verify()

    def test_rehashed_jit_mutation_still_fails_reconstruction(self):
        p = self.f.state / 'operator.json'
        self.f.final['documents']['operator.json'] = put(p, b'{"synthetic_test_only": true, "changed": true}\n')
        put(self.f.state / 'finalization.json', self.f.final)
        with self.assertRaisesRegex(ValueError, 'reviewed reconstruction'):
            self.f.verify()

    def test_finalizer_dependency_hash_and_source_archive_gates(self):
        for name in ('assembly/finalize.py', 'synthetic-dependency.json'):
            f = self.fixture()
            p = f.candidate / name
            p.write_bytes(p.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash or size'):
                f.verify()
        for key in ('runtime_source_sha256', 'archive'):
            f = self.fixture()
            if key == 'archive':
                f.manifest['consumer_contract']['source_archive']['sha256'] = '0' * 64
            else:
                f.manifest[key] = '0' * 64
            f.save_manifest()
            with self.assertRaisesRegex(ValueError, 'manifest|archive identity'):
                f.verify()

    def test_active_wire_privacy_model_resources_and_serialized_booleans(self):
        for key, value in (
            ('enable_gpu', 1), ('enable_tpu', True), ('enable_internet', True), ('is_private', False),
            ('model_data_sources', ['other/model/1']), ('machine_shape', 'other-machine'),
            ('session_timeout_seconds', 43200), ('kernel_execution_type', 3),
            ('dataset_data_sources', [v.DREF + '/25', *v.NON_CODE_PINS]),
        ):
            f = self.fixture()
            f.wire[key] = value
            put(f.state / 'notebook-rlvr004-wire.json', canonical_wire(f.wire))
            with self.assertRaisesRegex(ValueError, 'serialized bytes'):
                f.verify()
        put(self.f.state / 'notebook-rlvr004-wire.json', v.encoded(self.f.wire))
        with self.assertRaisesRegex(ValueError, 'serialized bytes'):
            self.f.verify()

    def test_journal_hash_chain_cannot_be_replayed(self):
        for key in ('source_sha256', 'wire_sha256', 'finalization_sha256'):
            f = self.fixture()
            f.journal[key] = '0' * 64
            f.save_journal()
            with self.assertRaisesRegex(ValueError, 'prepared exact byte chain'):
                f.verify()

    def test_paths_reject_links_and_hardlinks(self):
        f = self.fixture()
        p = f.state / 'operator.json'
        target = f.root / 'linked-operator.json'
        p.rename(target)
        p.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'linked review path'):
            f.verify()
        f = self.fixture()
        (f.root / 'hardlinked-operator.json').hardlink_to(f.state / 'operator.json')
        with self.assertRaisesRegex(ValueError, 'ordinary review file'):
            f.verify()

    def test_duplicate_json_and_nonfinite_numbers_rejected(self):
        for raw in (b'{"versions": {}, "versions": {}}', b'{"version": NaN}', b'{"version": 1e999}'):
            with self.assertRaises(ValueError):
                v.obj(raw)

    def test_main_keeps_write_once_output_and_reports_actual_returned_version(self):
        output = self.root / 'synthetic-output.json'
        synthetic_result = {'synthetic_test_only': True, 'predispatch_epoch': EPOCH, 'numeric_notebook_version': 44}
        argv = ['verify_active_wire.py', '--pins', '/synthetic', '--pins-sha', '0' * 64, '--output', str(output)]
        stdout = io.StringIO()
        with patch.object(v, 'verify', return_value=synthetic_result), patch.object(sys, 'argv', argv), redirect_stdout(stdout):
            v.main()
        self.assertTrue(json.loads(output.read_bytes())['synthetic_test_only'])
        self.assertEqual(json.loads(stdout.getvalue())['numeric_notebook_version'], 44)
        before = output.read_bytes()
        with patch.object(v, 'verify', return_value=synthetic_result), patch.object(sys, 'argv', argv):
            with self.assertRaises(FileExistsError):
                v.main()
        self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Synthetic offline round isolation; never private candidate/provider admission.

The sequential test keeps real publication writers, reconstruction/review gates,
readback receipt consumers and selected-output caching. Only source finalization,
Git approval, remote bytes and the separately tested retention RPC are doubled.
All generated approvals and epochs are disposable synthetic test data.
"""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import tempfile
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

from test_owner_integration import load_source

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def put(path, value):
    raw = value if isinstance(value, bytes) else encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)}


def allocation(code):
    return {'code_predecessor': code - 1, 'code': code,
            'inactive_predecessor': 2 * code - 3, 'inactive': 2 * code - 2, 'active': 2 * code - 1}


class MemoryProvider:
    """In-memory bytes only. No credentials, sockets, native process or SDK."""
    def __init__(self, transport, code):
        self.t, self.notebook_version, self.saved = transport, allocation(code)['inactive_predecessor'], b'{"cells":[]}\n'
        self.dataset_version = code - 1
        self.wire = None
        self.downloads = []

    def stage(self, expected):
        if self.t.obj(self.t.code_state('-journal.json'))['stage'] != expected:
            raise ValueError('synthetic mutation preceded durable intent')

    def start_upload(self, payload):
        self.stage('init_intent')
        return SimpleNamespace(handle='synthetic-handle', origin={'payload_sha256': digest(payload.read_bytes()),
            'official_init_response': True, 'token_or_signed_url_persisted': False})

    def upload_once(self, handle, payload):
        self.stage('put_intent')
        if handle != 'synthetic-handle' or payload.read_bytes() != self.payload:
            raise ValueError('synthetic upload changed')

    def version(self, handle, notes):
        self.stage('version_intent')
        if handle != 'synthetic-handle': raise ValueError('synthetic handle changed')
        self.dataset_version += 1
        return SimpleNamespace(error='', ref=self.t.DREF,
            to_dict=lambda: {'synthetic_test_only': True, 'version': self.dataset_version})

    def save(self, wire):
        self.notebook_version += 1
        self.wire, self.saved = dict(wire), wire['text'].encode()
        result = SimpleNamespace(error='', kernel_id=138123872, ref=self.t.REF,
            version_number=self.notebook_version, invalid_dataset_sources=[], invalid_model_sources=[],
            invalid_competition_sources=[], invalid_kernel_sources=[])
        result.to_dict = lambda: {'synthetic_test_only': True, 'version': self.notebook_version}
        return result

    def kernel(self):
        t, w = self.t, self.wire
        values = {'id': 138123872, 'ref': t.REF, 'is_private': True,
                  'current_version_number': self.notebook_version}
        if w is not None:
            values.update(title=w['new_title'], language='python', kernel_type='notebook',
                kernel_data_sources=[], enable_gpu=w['enable_gpu'], enable_tpu=False,
                enable_internet=False, model_data_sources=[t.MODEL],
                dataset_data_sources=['/'.join(s.split('/')[:2]) for s in w['dataset_data_sources']],
                competition_data_sources=w['competition_data_sources'], docker_image=t.DOCKER,
                machine_shape='NvidiaRtxPro6000' if w['enable_gpu'] else 'None')
        metadata = SimpleNamespace(**values)
        fields = {'id': 'id', 'ref': 'ref', 'is_private': 'isPrivate',
            'current_version_number': 'currentVersionNumber', 'title': 'title', 'language': 'language',
            'kernel_type': 'kernelType', 'kernel_data_sources': 'kernelDataSources',
            'enable_gpu': 'enableGpu', 'enable_tpu': 'enableTpu', 'enable_internet': 'enableInternet',
            'model_data_sources': 'modelDataSources', 'dataset_data_sources': 'datasetDataSources',
            'competition_data_sources': 'competitionDataSources', 'docker_image': 'dockerImage',
            'machine_shape': 'machineShape'}
        metadata.to_dict = lambda: {fields[key]: value for key, value in values.items()}
        return SimpleNamespace(metadata=metadata, blob=SimpleNamespace(source=self.saved.decode()))

    def status(self):
        value = 'ERROR' if self.wire is None else ('RUNNING' if self.wire['enable_gpu'] else 'COMPLETE')
        return SimpleNamespace(status=SimpleNamespace(name=value), failure_message='')

    def dataset_download(self, name, *, version):
        self.downloads.append(('code', version, name))
        return ('code', version, name)

    def list_files(self, dataset=False, *, version):
        return {'NOTICE.txt': len(self.payload)}

    def output(self, name, *, version):
        self.downloads.append(('output', version, name))
        return ('output', version, name)


class MultiRoundTransportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-multiround-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.state, self.evidence = self.base / 'state-run008', self.base / 'evidence-run008'
        self.state.mkdir(); self.evidence.mkdir()
        self.t = load_source('multiround_transport_' + self.base.name, ROOT / 'rl_transport.py')
        self.c = self.t._common
        self.collector = load_source('multiround_collector_' + self.base.name, ROOT / 'rl_collect.py')
        self.v = load_source('multiround_wire_' + self.base.name, ROOT / 'verify_active_wire.py')
        self.enterContext(patch.object(socket, 'socket', side_effect=AssertionError('offline only')))
        self.enterContext(patch.object(socket, 'create_connection', side_effect=AssertionError('offline only')))

    def select(self, code, *, modern=True, history=()):
        versions = allocation(code)
        selected = self.state / 'publications' / ('code-v' + str(code)) if modern else self.state
        output = self.evidence / ('code-v' + str(code)) if modern else self.evidence
        config = SimpleNamespace(versions=versions, state_root=self.state, evidence_root=self.evidence,
            scratch_root=self.base, gpu_stop_path=self.base / 'gpu-stop.json',
            publication_state_root=selected, publication_evidence_root=output,
            publication_history=tuple(history), document_sha256='c' * 64)
        self.c.CONFIG, self.c.STATE, self.c.STOP = config, self.state, config.gpu_stop_path
        self.c.PUBLICATION_STATE, self.c.PUBLICATION_EVIDENCE = selected, output
        self.t.__dict__.update({k: v for k, v in vars(self.c).items() if not k.startswith('_')})
        t = self.t
        t.CODE_PREDECESSOR, t.CODE_VERSION = code - 1, code
        t.NOTEBOOK_PREDECESSOR, t.INACTIVE_VERSION, t.ACTIVE_VERSION = (
            versions['inactive_predecessor'], versions['inactive'], versions['active'])
        t.PINS = [t.DREF + '/' + str(code), *t.NON_CODE_PINS]
        t.REMOTE_PREDECESSOR = {'provider_status': 'ERROR'}
        return selected, output

    def synthetic_round(self, code, *, modern):
        t, c = self.t, self.c
        selected, output = self.select(code, modern=modern)
        candidate = self.base / ('candidate' + str(code)); candidate.mkdir()
        provider = MemoryProvider(t, code); provider.payload = ('synthetic code ' + str(code)).encode()
        notebooks = []
        for role, before, after in (('inactive', t.NOTEBOOK_PREDECESSOR, t.INACTIVE_VERSION),
                                   ('rlvr004', t.INACTIVE_VERSION, t.ACTIVE_VERSION)):
            descriptor = put(candidate / (role + '.ipynb'), {'cells': [], 'synthetic': code, 'role': role})
            descriptor['path'] = role + '.ipynb'
            notebooks.append(dict(descriptor, role=role, expected_predecessor_version=before,
                expected_version=after, predecessor_source_sha256=digest(provider.saved),
                title='Synthetic round ' + str(code), language='python', kernel_type='notebook',
                enable_gpu=role == 'rlvr004', competition_sources=['arc-prize-2026-arc-agi-3'],
                save_version_value=2 if role == 'rlvr004' else 0, session_timeout_seconds=42300,
                machine_shape='NvidiaRtxPro6000' if role == 'rlvr004' else 'None'))
        upload = put(candidate / 'synthetic-upload.bin', provider.payload)
        upload['path'] = 'synthetic-upload.bin'
        manifest = {'notebooks': notebooks, 'jit': {'entry': {'sha256': 'e' * 64}},
            'datasets': [{'transport_archive': upload, 'version_notes': 'Synthetic test only',
                'expected_readback_layouts': {'extracted-root': [
                {'path': 'NOTICE.txt', 'bytes': len(provider.payload), 'sha256': digest(provider.payload)}]}}]}
        manifest_row = put(candidate / 'publication-manifest.json', manifest)
        review = put(candidate / 'review.json', {'synthetic_test_only': True})
        args = SimpleNamespace(manifest=manifest_row['path'], manifest_sha=manifest_row['sha256'],
            review=review['path'], review_sha=review['sha256'], material_sha='a' * 64,
            monitor_sha='b' * 64, local_config_sha='c' * 64, active_review=None, active_review_sha=None)
        def dataset_check(unused, version, **options):
            self.assertIn(version, (code - 1, code))
            self.assertEqual(provider.dataset_version, version)
            return {'id': 12504696, 'ref': t.DREF, 'version': version, 'private': True}
        def binary_get(request, destination, cap, expected_sha=None, expected_bytes=None):
            raw = provider.payload if request[0] == 'code' else ('output ' + str(request[1])).encode()
            self.assertLessEqual(len(raw), cap)
            if expected_sha is not None: self.assertEqual(digest(raw), expected_sha)
            if expected_bytes is not None: self.assertEqual(len(raw), expected_bytes)
            return c.write_new(destination, raw)
        def finalized(unused_manifest, unused_path, epoch):
            return {name: encoded({'cells': [], 'synthetic_test_only': True, 'code': code,
                                  'name': name, 'epoch': epoch}) for name in
                    ('active-finalized.ipynb', 'operator.json', 'original-request.json', 'parent-private-scorer.json')}
        with ExitStack() as stack:
            stack.enter_context(patch.object(t, 'dataset_check', side_effect=dataset_check))
            stack.enter_context(patch.object(t, 'binary_get', side_effect=binary_get))
            stack.enter_context(patch.object(t, 'git_publication_gate', return_value='d' * 40))
            stack.enter_context(patch.object(t, 'finalized_documents', side_effect=finalized))
            stack.enter_context(patch.object(t, 'monitor_gate', return_value={}))
            self.assertEqual(t.update_code(provider, manifest, args)['status'], 'VERSION_ACCEPTED_READBACK_REQUIRED')
            receipt = t.verify_code(provider, manifest, args, per_file=True)
            self.assertEqual(receipt['payload_root'], str(selected / ('code-v' + str(code) + '-readback') / 'payload'))
            self.assertEqual(t.save(provider, manifest, args, 'inactive')['status'], 'SAVE_ACCEPTED')
            t.verify_notebook(provider, manifest, args, 'inactive')
            mount = put(candidate / 'mount.json', {'status': 'PASS', 'publication_manifest_sha256': args.manifest_sha,
                'code_dataset_version': code, 'model_calls': 0, 'owned_tree_closed': True,
                'code_receipt_sha256': c.file_sha(t.code_state('-receipt.json'))})
            audit = put(candidate / 'audit.json', {'status': 'PASS', 'publication_manifest_sha256': args.manifest_sha,
                'code_receipt_sha256': c.file_sha(t.code_state('-receipt.json')),
                'inactive_receipt_sha256': c.file_sha(selected / 'notebook-inactive-receipt.json'),
                'mount_receipt_sha256': mount['sha256']})
            args.mount, args.mount_sha, args.audit, args.audit_sha = mount['path'], mount['sha256'], audit['path'], audit['sha256']
            self.assertEqual(t.save(provider, manifest, args, 'rlvr004')['status'], 'ACTIVE_PREPARED_REVIEW_REQUIRED')
            final = c.obj(selected / 'finalization.json')
            actual_review = {'format': 'irisx/run008-active-wire-review-v1', 'status': 'PASS',
                'synthetic_test_only': False, 'publication_manifest_sha256': args.manifest_sha,
                'material_approval_sha256': args.material_sha, 'transport_review_sha256': args.review_sha,
                'local_config_sha256': args.local_config_sha, 'predispatch_epoch': final['predispatch_epoch'],
                'numeric_notebook_version': t.ACTIVE_VERSION}
            for key, name in (('wire_sha256', 'notebook-rlvr004-wire.json'), ('finalization_sha256', 'finalization.json'),
                              ('finalized_source_sha256', 'active-finalized.ipynb'), ('prepared_journal_sha256', 'notebook-rlvr004-journal.json')):
                actual_review[key] = c.file_sha(selected / name)
            review_row = put(candidate / 'synthetic-active-review.json', actual_review)
            args.active_review, args.active_review_sha = review_row['path'], review_row['sha256']
            self.assertEqual(t.activate(provider, manifest, args)['version'], t.ACTIVE_VERSION)
            with self.assertRaisesRegex(ValueError, 'active_review_exact_bindings|prepared_run_claim'):
                t.activate(provider, manifest, args)
            collector = self.collector
            collector.transport, collector._common = t, c
            stack.enter_context(patch.object(t, 'load_contract', return_value=manifest))
            collector.bindings(args)
            self.assertEqual(collector.OUT, output)
            stack.enter_context(patch.object(collector, 'binary_get', side_effect=binary_get))
            selected_row = collector.fetch_selected(provider, 'same/output.json', 100, 1000)
            again = collector.fetch_selected(provider, 'same/output.json', 100, 1000)
            self.assertEqual(selected_row, again)
            self.assertEqual(provider.downloads.count(('output', t.ACTIVE_VERSION, 'same/output.json')), 1)
            c.write_new(output / 'TERMINAL-CHECKPOINT.json', {'synthetic_test_only': True, 'code': code})
        return selected, output

    def test_sequential_transport_rounds_preserve_old_claims_jit_receipts_and_cache(self):
        put(self.state / 'native-bridge-preserved.claim.json', {'synthetic': 'native'})
        put(self.evidence / 'recovery-boot-preserved.json', {'synthetic': 'boot'})
        first, first_output = self.synthetic_round(21, modern=False)
        preserved = {p: p.read_bytes() for root in (first, first_output) for p in root.rglob('*')
                     if p.is_file() and 'events' not in p.parts}
        second, second_output = self.synthetic_round(22, modern=True)
        self.assertEqual(second, self.state / 'publications/code-v22')
        self.assertEqual(second_output, self.evidence / 'code-v22')
        for path, raw in preserved.items(): self.assertEqual(path.read_bytes(), raw)
        self.assertNotEqual((first_output / 'downloads/same/output.json').read_bytes(),
                            (second_output / 'downloads/same/output.json').read_bytes())
        self.assertEqual(self.c.STATE, self.state)
        self.assertEqual(self.c.publication_paths()['publication_state_root'], str(second))
        with self.assertRaises(FileExistsError):
            self.c.publication_claim('notebook-inactive', {'different_manifest': True})

    def test_native_claim_journal_and_global_lock_remain_shared(self):
        selected, unused = self.select(22)
        self.c.claim('native-bridge-test', {'synthetic': True})
        self.c.journal('native-bridge-test', {'stage': 'UNKNOWN'})
        self.assertTrue((self.state / 'native-bridge-test.claim.json').is_file())
        self.assertFalse((selected / 'native-bridge-test.claim.json').exists())
        with self.c.lock():
            with self.assertRaisesRegex(ValueError, 'operator_already_running'):
                with self.c.lock('collector'): pass
        self.assertTrue((self.base / 'publisher.lock').is_file())

    def test_wire_independently_selects_round_without_rebinding_native_pins(self):
        native = self.state; versions = allocation(22)
        cfg = {'state_root': str(native), 'publication': {'history': []}}
        self.assertEqual(self.v.publication_root(cfg, native, versions), native / 'publications/code-v22')
        self.assertEqual(self.v.publication_root({'state_root': str(native)}, native, versions), native)
        with self.assertRaisesRegex(ValueError, 'local state binding'):
            self.v.publication_root(cfg, self.base, versions)
        with self.assertRaisesRegex(ValueError, 'publication namespace'):
            self.v.publication_root(dict(cfg, publication={'root': str(self.base)}), native, versions)

    def test_publication_write_rejects_linked_round_directory(self):
        self.select(22)
        (self.state / 'publications').mkdir()
        (self.state / 'publications/code-v22').symlink_to(self.evidence, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink_path'):
            self.c.publication_claim('notebook-inactive', {'synthetic': True})

    def test_full_wire_verifier_uses_selected_receipts_and_jit(self):
        fixture_path = ROOT.with_name('publication_portable_20261015') / 'tests/test_portable_wire.py'
        fixture = load_source('multiround_wire_fixture_' + self.base.name, fixture_path)
        with patch.object(fixture, 'v', self.v), patch.object(fixture, 'VERIFIER', ROOT / 'verify_active_wire.py'):
            f = fixture.Fixture(self.base / 'wire-fixture', allocation(22))
            native = f.state
            original = list(native.iterdir())
            selected = native / 'publications/code-v22'; selected.mkdir(parents=True)
            for item in original: item.rename(selected / item.name)
            f.state = selected
            f.cfg['publication'] = {'history': []}
            f.save_config()
            for name, row in f.final['documents'].items(): row['path'] = str(selected / name)
            row = put(selected / 'finalization.json', f.final)
            f.journal['finalization_sha256'] = row['sha256']; f.save_journal()
            # Old flat paths remain populated with deliberately incompatible bytes.
            for name in ('dataset-code-v22-receipt.json', 'notebook-inactive-receipt.json', 'finalization.json'):
                put(native / name, {'old_round_decoy': True})
            self.assertEqual(f.verify()['numeric_notebook_version'], allocation(22)['active'])
            f.code_path.rename(f.candidate / 'moved-receipt.json')
            with self.assertRaises(FileNotFoundError): f.verify()

    def history(self, code, root):
        fixture = load_source('multiround_state_fixture_' + str(code), ROOT / 'tests/test_publication_state.py')
        manifest = fixture.manifest(configured_versions=allocation(code))
        descriptor = put(self.base / ('history' + str(code)) / 'manifest.json', manifest)
        for old in range(8, max(7, code - 10) + 1):
            files = self.inventory(old)
            put(root / ('historical-code-v' + str(old) + '-inventory.json'), {
                'dataset_id': 12504696, 'numeric_version': old,
                'captured_while_current_version': code - 1,
                'inventory_sha256': digest(encoded(files)), 'files_inventory': files,
                'payload_bytes_rehashed': False})
        return MappingProxyType({'root': str(root), 'manifest': MappingProxyType(descriptor)})

    @staticmethod
    def inventory(old):
        return {'synthetic/source' + str(old) + '.py': old}

    def retention_check(self, code=22, *, changed=None, capture=True):
        # Frozen provider v1-v7 digests are unrelated to this synthetic fixture.
        # Replace only those seven test hashes; later inventories use real SHA256.
        pinned = ('9a8b5f698c942407b74cc5b16e0ad1d77dd2ac4a6800f991c8bd9f9584353a1b',
            '402aebb539a8163ed516d2e2915c75f5b7a16c56e1d244ac99088f62a2f2e6b9',
            '8c1b22bd9b676ad2a10f31ee820ed4d1732f04dca9d0a81835fdc456c6bd318d',
            'dc87ea2368b0ce1b750b3572327d57adc670474a8c511a485c43704b62c3e01f',
            '54fbc4f2d6543cc82255fdd71113ffce44ca88aab83442f1ac9d80abbe52e255',
            '8db523abc333759e431e396146e991564523aa2d2daac30374a384f86023dcac',
            '55ee43dcab68f291aa517ad823c58993c8ec813a520173e09676598ae9dcda79')
        test_hashes = {encoded(self.inventory(old)): value for old, value in enumerate(pinned, 1)}
        metadata = SimpleNamespace(id=12504696, ref=self.t.DREF, is_private=True,
            current_version_number=code - 1, title='IRIS-X Learning Agent Code 20261011',
            license_name='Other (specified in description)', owner_ref='danielwuu',
            versions=[SimpleNamespace(version_number=n) for n in range(code - 1, code - 11, -1)])
        def files(dataset=False, *, version):
            return {'changed.py': 999} if version == changed else self.inventory(version)
        provider = SimpleNamespace(dataset=lambda: metadata, list_files=files)
        with patch.object(self.t, 'sha', side_effect=lambda raw: test_hashes.get(raw, digest(raw))):
            return self.t.dataset_check(provider, code - 1, capture_prewrite=capture)

    def test_retention_compares_old_capture_and_writes_distinct_current_capture(self):
        history = self.history(21, self.state)
        old = self.state / 'historical-code-v8-inventory.json'; original = old.read_bytes()
        selected, unused = self.select(22, history=(history,))
        result = self.retention_check()
        self.assertTrue(result['retention_check_complete'])
        self.assertEqual(old.read_bytes(), original)
        self.assertEqual(self.c.obj(old)['captured_while_current_version'], 20)
        self.assertEqual(self.c.obj(selected / old.name)['captured_while_current_version'], 21)
        self.assertTrue((selected / 'historical-code-v12-inventory.json').is_file())
        self.assertFalse((self.state / 'historical-code-v12-inventory.json').exists())
        self.retention_check(capture=False)

    def test_retention_drift_and_missing_prior_capture_reject_before_new_record(self):
        history = self.history(21, self.state)
        selected, unused = self.select(22, history=(history,))
        with self.assertRaisesRegex(ValueError, 'prior_historical_baseline_changed'):
            self.retention_check(changed=8)
        self.assertFalse((selected / 'historical-code-v8-inventory.json').exists())
        (self.state / 'historical-code-v8-inventory.json').unlink()
        with self.assertRaisesRegex(ValueError, 'prior_historical_baseline_missing'):
            self.retention_check()

    def test_retention_checks_every_prior_round_and_original_manifest_hash(self):
        first = self.history(21, self.state)
        second = self.history(22, self.state / 'publications/code-v22')
        self.select(23, history=(first, second))
        prior = self.state / 'historical-code-v8-inventory.json'
        value = self.c.obj(prior); value['files_inventory'] = {'bad': 1}; put(prior, value)
        with self.assertRaisesRegex(ValueError, 'prior_historical_baseline_changed'):
            self.retention_check(23)
        Path(first['manifest']['path']).write_bytes(b'{}\n')
        with self.assertRaisesRegex(ValueError, 'artifact_hash_or_size'):
            self.retention_check(23)

    def test_new_retention_capture_cannot_follow_a_claim(self):
        history = self.history(21, self.state)
        self.select(22, history=(history,))
        self.c.publication_claim(self.t.code_claim_name(), {'synthetic_test_only': True})
        with self.assertRaisesRegex(ValueError, 'history_capture_only_before_claim'):
            self.retention_check()
        with self.assertRaisesRegex(ValueError, 'historical_baseline_missing_prewrite_required'):
            self.retention_check(capture=False)

    def test_foreign_prior_round_blocks_before_credentials_when_native_history_is_empty(self):
        history = self.history(21, self.state)
        self.select(22, history=(history,))
        fixture = load_source('multiround_guard_fixture', ROOT / 'tests/test_publication_state.py')
        current = put(self.base / 'current' / 'manifest.json', fixture.manifest(configured_versions=allocation(22)))
        self.c.MANIFEST_PATH = Path(current['path'])
        self.c.CONFIG.candidate_root = self.c.MANIFEST_PATH.parent
        self.c.CONFIG.publication_manifest_sha256 = current['sha256']
        put(self.state / 'dataset-code-v21.claim.json', {'manifest_sha256': '0' * 64,
            'expected_version': 21, 'expected_predecessor_version': 20})
        self.assertEqual(list(self.state.glob('native-*')), [])
        with patch.object(self.c, 'credential_guard', side_effect=AssertionError('must not reach native')) as credential:
            with self.assertRaisesRegex(ValueError, 'publication_state_foreign_manifest'):
                self.c.Provider()
            credential.assert_not_called()


if __name__ == '__main__':
    unittest.main()

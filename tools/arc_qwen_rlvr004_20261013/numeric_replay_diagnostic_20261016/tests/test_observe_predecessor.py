"""Mocked read-only API tests; synthetic reviews never authorize a real call."""
import copy
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'assembly/observe_predecessor.py'
spec = importlib.util.spec_from_file_location('fixed_predecessor_capture_tests', PATH)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def descriptor(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': observer.sha(raw)}


def write(path, value):
    path.write_bytes(observer.encoded(value))
    return descriptor(path)


class OfflineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for module, name in ((socket, 'socket'), (socket, 'create_connection'), (subprocess, 'Popen')):
            replacement = patch.object(module, name, side_effect=AssertionError('external calls forbidden'))
            replacement.start()
            self.addCleanup(replacement.stop)


class PreparationTests(OfflineTests):
    def setUp(self):
        super().setUp()
        self.manifest = {'notebooks': [{'role': 'inactive', 'sha256': 'a' * 64},
                                       {'role': 'rlvr004', 'sha256': 'b' * 64}]}
        manifest = write(self.root / 'manifest.json', self.manifest)
        material = write(self.root / 'material.json', {'status': 'APPROVED',
            'scope': {'publication_manifest': {'sha256': manifest['sha256']}},
            'approved_notebooks': self.manifest['notebooks']})
        config = write(self.root / 'config.json', {'publication_manifest_sha256': manifest['sha256']})
        self.review = {'status': 'PASS', 'synthetic_test_only': False,
            'provider_execution_admitted': True, 'allowed_actions': ['reconcile-read-only'],
            'observer': {'purpose': observer.PURPOSE, 'script': descriptor(PATH),
                'output_root': str(self.root / 'new-output'), 'manifest': manifest,
                'material': material, 'local_config': config}}
        self.review_path = self.root / 'synthetic-review.json'
        self.events = []
        self.configured = types.SimpleNamespace(scratch_root=self.root,
            candidate_root=self.root / 'candidate')
        self.common = types.SimpleNamespace(STATE=self.root / 'state',
            configured=lambda: self.configured,
            bind_action_review=lambda *args: self.events.append('bind_action_review'),
            publication_guard=lambda: self.events.append('publication_guard'))
        self.transport = types.SimpleNamespace(CONFIG=types.SimpleNamespace(versions=dict(observer.VERSIONS)),
            SCRIPT=observer.OPERATOR / 'rl_transport.py', _common=self.common,
            configure_local=lambda args: self.events.append('configure_local'),
            review_gate=lambda *args: self.events.append('review_gate'),
            execution_gate=lambda *args, **kwargs: self.events.append('execution_gate'),
            load_contract=lambda *args: self.fail('numeric load_contract must never be used'))
        self.collector = types.SimpleNamespace(bootstrap=self.bootstrap)

    def bootstrap(self, args):
        self.events.append('bootstrap')
        self.assertEqual(args.action, 'reconcile-read-only')
        self.assertEqual(args.manifest_sha, self.review['observer']['manifest']['sha256'])
        return self.transport

    def prepare(self):
        row = write(self.review_path, self.review)
        # Only the missing private manifest is substituted, in memory, to test
        # orchestration. Production literals are independently asserted below.
        manifest = self.review['observer']['manifest']
        with patch.object(observer, 'MANIFEST_SHA256', manifest['sha256']), \
             patch.object(observer, 'MANIFEST_BYTES', manifest['bytes']), \
             patch.object(observer, 'load_collector', return_value=self.collector):
            return observer.prepare(self.review_path, row['sha256'])

    def test_fixed_published_literals_and_collector_bootstrap_load(self):
        self.assertEqual(observer.MANIFEST_BYTES, 135137)
        self.assertEqual(observer.SAVED_SOURCE_BYTES, 22913)
        self.assertEqual(observer.PURPOSE, 'fixed-code23-v45-predecessor-capture-v1')
        self.assertEqual(observer.MANIFEST_SHA256,
            '15f340149a8eff74e6c1d56f3cd34b8836d349dfa6818ef14bd142dcb600161a')
        self.assertEqual(observer.SAVED_SOURCE_SHA256,
            '5f884856484087033f6569335f5c65f752c4868c823276efaffed3c3e96eaeff')
        self.assertEqual(observer.VERSIONS, {'code_predecessor': 22, 'code': 23,
            'inactive_predecessor': 43, 'inactive': 44, 'active': 45})
        self.assertTrue(callable(observer.load_collector().bootstrap))
        self.assertIsNone(observer.load_collector().transport)

    def test_explicit_gate_order_without_numeric_contract(self):
        result = self.prepare()
        self.assertEqual(self.events, ['bootstrap', 'configure_local', 'review_gate',
                                      'execution_gate', 'bind_action_review', 'publication_guard'])
        self.assertEqual(result, (self.transport, self.common, self.manifest, self.root / 'new-output'))
        self.assertFalse((self.root / 'new-output').exists())

    def test_source_review_and_scope_mutations_reject_before_bootstrap(self):
        original = copy.deepcopy(self.review)
        variants = [dict(original, status='FAIL'), dict(original, synthetic_test_only=True),
            dict(original, provider_execution_admitted=False),
            dict(original, allowed_actions=['reconcile-read-only', 'activate']),
            dict(original, allowed_actions=['reconcile-read-only', 'reconcile-read-only'])]
        for key, value in (('purpose', 'generic'), ('extra', True),
                           ('script', {**original['observer']['script'], 'sha256': '0' * 64})):
            variants.append({**original, 'observer': {**original['observer'], key: value}})
        for review in variants:
            with self.subTest(review=review):
                self.review = review
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertEqual(self.events, [])
        self.review = original

    def test_material_approved_notebooks_and_exact_manifest_binding(self):
        path = self.root / 'material.json'
        for value in ({'status': 'APPROVED', 'scope': {'publication_manifest': {'sha256': '0' * 64}},
                       'approved_notebooks': self.manifest['notebooks']},
                      {'status': 'APPROVED', 'scope': {'publication_manifest': {
                          'sha256': self.review['observer']['manifest']['sha256']}},
                       'approved_notebooks': []}):
            self.review['observer']['material'] = write(path, value)
            with self.assertRaises(ValueError):
                self.prepare()
            self.assertEqual(self.events, [])

    def test_stale_versions_output_overwrite_and_retained_overlap_reject(self):
        self.transport.CONFIG.versions['active'] = 44
        with self.assertRaisesRegex(ValueError, 'fixed_accepted_versions'):
            self.prepare()
        self.transport.CONFIG.versions = dict(observer.VERSIONS)
        output = self.root / 'new-output'
        output.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh_output_required'):
            self.prepare()
        self.review['observer']['output_root'] = str(self.root / 'state' / 'new-output')
        with self.assertRaisesRegex(ValueError, 'output_overlaps_retained_inputs'):
            self.prepare()

    def test_exact_collector_source_is_required_before_compile(self):
        (self.root / 'rl_collect.py').write_bytes(b'raise AssertionError("must not compile")\n')
        with patch.object(observer, 'OPERATOR', self.root):
            with self.assertRaisesRegex(ValueError, 'source_hash_changed'):
                observer.load_collector()


class DTO(types.SimpleNamespace):
    def to_dict(self):
        return dict(vars(self))


class CaptureTests(OfflineTests):
    def setUp(self):
        super().setUp()
        self.events, self.locked = [], False
        self.raw = b'{"synthetic_only":true}'
        self.dataset = DTO(id=12504696, ref='danielwuu/iris-x-learning-agent-code-20261011',
            owner_ref='danielwuu', is_private=True, current_version_number=23)
        metadata = DTO(id=138123872, ref='danielwuu/iris-x-learning-agent-20261011',
            current_version_number=45, is_private=True, enable_gpu=True, enable_tpu=False,
            enable_internet=False, title='Synthetic expected title')
        self.kernels = [DTO(metadata=metadata, blob=DTO(source=self.raw.decode())),
                        DTO(metadata=copy.deepcopy(metadata), blob=DTO(source=self.raw.decode()))]
        self.status = types.SimpleNamespace(status=types.SimpleNamespace(name='COMPLETE'), failure_message='',
            to_dict=lambda: {'status': self.status.status.name, 'failureMessage': self.status.failure_message})
        self.bridge = types.SimpleNamespace(closed=False, closure_verified=False)
        self.fail_call = None
        self.fail_close = False
        self.false_closure = False
        self.kernel_count = 0
        self.provider = types.SimpleNamespace(dataset=lambda: self.call('dataset', self.dataset),
            kernel=self.kernel, status=lambda: self.call('status', self.status), close=self.close,
            bridge=self.bridge)
        self.common = types.SimpleNamespace(lock=self.lock, publisher_lock_owner=self.require_lock,
            no_gpu_stop=lambda: self.require_lock(), Provider=lambda: self.call('construct', self.provider),
            classify=lambda *args: ('OTHER', ''), STOP=self.root / 'GPU_STOP', write_new=self.write_new)
        self.settings_calls = 0
        self.transport = types.SimpleNamespace(DREF=self.dataset.ref, settings=self.settings,
            row=lambda manifest, role: {'title': 'Synthetic expected title'})
        self.output = self.root / 'output'

    @contextmanager
    def lock(self, name):
        self.assertEqual(name, 'reconcile-read-only')
        self.assertFalse(self.locked)
        self.locked = True
        self.events.append('lock')
        try:
            yield
        finally:
            self.events.append('unlock')
            self.locked = False

    def require_lock(self):
        self.assertTrue(self.locked)

    def call(self, name, value):
        self.require_lock()
        self.events.append(name)
        if self.fail_call == name:
            raise ValueError('synthetic_call_failure')
        return value

    def kernel(self):
        result = self.call('kernel', self.kernels[self.kernel_count])
        self.kernel_count += 1
        return result

    def close(self):
        self.require_lock()
        self.events.append('close')
        if self.fail_close:
            raise ValueError('synthetic_close_failure')
        self.bridge.closed = True
        self.bridge.closure_verified = not self.false_closure

    def write_new(self, path, raw):
        self.require_lock()
        if path.name == 'OBSERVATION.json':
            self.assertTrue(self.bridge.closed and self.bridge.closure_verified)
        with path.open('xb') as stream:
            stream.write(raw if type(raw) is bytes else observer.encoded(raw))

    def settings(self, metadata, row):
        self.settings_calls += 1
        observer.need(metadata.title == row['title'], 'full_settings')

    def capture(self):
        with patch.object(observer, 'SAVED_SOURCE_SHA256', observer.sha(self.raw)), \
             patch.object(observer, 'SAVED_SOURCE_BYTES', len(self.raw)):
            return observer.capture(self.transport, self.common, {}, self.output)

    def test_five_reads_six_raw_files_close_then_observation_under_lock(self):
        result = self.capture()
        self.assertEqual(self.events, ['lock', 'construct', 'dataset', 'kernel', 'status',
                                      'kernel', 'dataset', 'close', 'unlock'])
        self.assertEqual(self.settings_calls, 2)
        self.assertEqual({p.name for p in self.output.iterdir()}, {'dataset.json', 'metadata-before.json',
            'status.json', 'metadata-after.json', 'saved_source.ipynb', 'dataset-after.json', 'OBSERVATION.json'})
        observation = json.loads((self.output / 'OBSERVATION.json').read_bytes())
        for name, key in (('dataset.json', 'dataset_metadata_sha256'), ('metadata-before.json', 'metadata_before_sha256'),
            ('status.json', 'status_sha256'), ('metadata-after.json', 'metadata_after_sha256'),
            ('saved_source.ipynb', 'saved_source_sha256'), ('dataset-after.json', 'dataset_after_sha256')):
            self.assertEqual(observer.sha((self.output / name).read_bytes()), observation[key])
        self.assertEqual((result['code_version'], result['notebook_version']), (23, 45))
        self.assertEqual((observation['code_version'], observation['notebook_version']), (23, 45))
        self.assertFalse(result['numeric_publication_contract_admitted'])
        self.assertFalse(observation['runtime_closure_verified'])
        self.assertFalse(observation['scientific_result_verified'])
        with self.assertRaisesRegex(ValueError, 'fresh_output_required'):
            self.capture()

    def test_fixed_saved_source_length_is_required_even_with_matching_digest(self):
        with patch.object(observer, 'SAVED_SOURCE_SHA256', observer.sha(self.raw)), \
             patch.object(observer, 'SAVED_SOURCE_BYTES', len(self.raw) + 1):
            with self.assertRaisesRegex(ValueError, 'fixed_v45_source_bracket'):
                observer.capture(self.transport, self.common, {}, self.output)
        self.assertFalse((self.output / 'OBSERVATION.json').exists())
        self.assertEqual(self.events[-2:], ['close', 'unlock'])

    def test_failed_call_closes_inside_lock_and_never_emits_observation(self):
        self.fail_call = 'status'
        with self.assertRaisesRegex(ValueError, 'synthetic_call_failure'):
            self.capture()
        self.assertEqual(self.events[-2:], ['close', 'unlock'])
        self.assertFalse((self.output / 'OBSERVATION.json').exists())

    def test_failed_close_preserves_six_raw_files_without_authoritative_observation(self):
        self.fail_close = True
        with self.assertRaisesRegex(ValueError, 'synthetic_close_failure'):
            self.capture()
        self.assertEqual(len(list(self.output.iterdir())), 6)
        self.assertFalse((self.output / 'OBSERVATION.json').exists())

    def test_missing_closure_blocks_observation(self):
        self.false_closure = True
        with self.assertRaisesRegex(ValueError, 'native_clean_close_required'):
            self.capture()
        self.assertFalse((self.output / 'OBSERVATION.json').exists())

    def test_fixed_versions_source_types_settings_and_status_fail_closed(self):
        variants = ('dataset_float', 'dataset_version', 'dataset_predecessor', 'dataset_owner',
                    'notebook_version', 'notebook_predecessor', 'notebook_future',
                    'gpu_int', 'settings', 'metadata', 'source', 'status')
        for name in variants:
            with self.subTest(name=name):
                # Each temporary fixture keeps failed work separate.
                fixture = CaptureTests('test_fixed_versions_source_types_settings_and_status_fail_closed')
                fixture.setUp()
                try:
                    if name == 'dataset_float': fixture.dataset.current_version_number = 23.0
                    elif name == 'dataset_version': fixture.dataset.current_version_number = 24
                    elif name == 'dataset_predecessor': fixture.dataset.current_version_number = 22
                    elif name == 'notebook_predecessor': fixture.kernels[1].metadata.current_version_number = 43
                    elif name == 'notebook_future': fixture.kernels[1].metadata.current_version_number = 46
                    elif name == 'dataset_owner': fixture.dataset.owner_ref = 'other'
                    elif name == 'notebook_version': fixture.kernels[1].metadata.current_version_number = 44
                    elif name == 'gpu_int': fixture.kernels[0].metadata.enable_gpu = 1
                    elif name == 'settings': fixture.kernels[1].metadata.title = 'changed'
                    elif name == 'metadata': fixture.kernels[1].metadata.extra_field = True
                    elif name == 'source': fixture.kernels[1].blob.source = 'different'
                    else: fixture.status.status.name = 'RUNNING'
                    with self.assertRaises(ValueError): fixture.capture()
                    self.assertFalse((fixture.output / 'OBSERVATION.json').exists())
                    self.assertEqual(fixture.events[-2:], ['close', 'unlock'])
                finally:
                    fixture.doCleanups()


if __name__ == '__main__':
    unittest.main()

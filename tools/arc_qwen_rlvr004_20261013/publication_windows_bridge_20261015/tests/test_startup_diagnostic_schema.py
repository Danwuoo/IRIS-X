"""Offline, synthetic v41-shaped pre-owned diagnostic collection regressions.

Five invented outputs exercise the current collector and real numeric download,
cache, hash, closed-schema, JIT/source/clock and non-admission checks. Only the
external bridge, finalized-document trust root and provider snapshot are fake.
These fixtures are not the actual v41 raw bytes or terminal-validation evidence.
No SDK, authentication, provider, model, evaluator or subprocess is used.
"""
import copy
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[2] / '.irisx/startup-diagnostic-schema-tests'
EPOCH = 1792079687
VERSION = 41


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(document):
    return (json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def load(name, path):
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                 optimize=sys.flags.optimize), vars(module))
    return module


bootstrap_fixture = load('startup_schema_bootstrap_fixture', ROOT / 'tests/test_collector_bootstrap.py')
producer = load('startup_schema_real_producer', ROOT.with_name('preparation_diagnostics_repair') / 'launch_notebook.py')


class NoExternalImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('kaggle', 'kagglesdk', 'requests', 'torch', 'transformers'):
            raise AssertionError('external_import_forbidden_in_synthetic_test')
        return None


class SyntheticBridge:
    """Only the bounded binary transport boundary is synthetic."""
    def __init__(self, files):
        self.files, self.calls = files, []

    def download(self, operation, arguments, sink, *, cap, expected, expected_size):
        if operation != 'output' or set(arguments) != {'name', 'version'} or arguments['version'] != VERSION:
            raise AssertionError('exact_numeric_output_request_required')
        self.calls.append(dict(arguments))
        raw = self.files[arguments['name']]
        if len(raw) > cap or expected not in (None, sha(raw)) or expected_size not in (None, len(raw)):
            raise AssertionError('unexpected_fixture_download_binding')
        sink.write(raw)
        return {'bytes': len(raw), 'sha256': sha(raw)}


class StartupDiagnosticSchemaTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(prefix='synthetic-', dir=SCRATCH)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target in ('socket.create_connection', 'socket.socket.connect', 'subprocess.Popen', 'os.system'):
            self.stack.enter_context(patch(target, side_effect=AssertionError('external_effect_forbidden')))
        self.stack.enter_context(patch.object(sys, 'meta_path', [NoExternalImports(), *sys.meta_path]))
        self.c = bootstrap_fixture.load_collector(ROOT / 'rl_collect.py')
        self.c.bootstrap(bootstrap_fixture.synthetic_bootstrap_arguments(self.root / 'bootstrap'))
        self.common, self.transport = self.c._common, self.c.transport
        self.c.OUT, self.c.DOWNLOADS = self.root / 'evidence', self.root / 'evidence/downloads'
        config = SimpleNamespace(versions={'inactive_predecessor': 39, 'inactive': 40, 'active': VERSION})
        self.state = self.root / 'state'
        self.state.mkdir()
        (self.state / 'notebook-rlvr004-receipt.json').write_bytes(encoded({'synthetic_test_only': True}))
        for module in (self.common, self.transport, self.c):
            module.CONFIG, module.STATE = config, self.state
        self.transport.ACTIVE_VERSION = VERSION
        self.prefix = 'synthetic-run008'
        self.outer = self.prefix + '-launcher'
        output = '/kaggle/working/' + self.prefix
        source_parent = '/kaggle/working/synthetic-source008'
        self.release = {'format': 'irisx/rlvr-notebook-release-v1', 'release_role': 'rlvr004',
                        'source_sha256': sha(b'synthetic runtime'),
                        'source_archive_sha256': sha(b'synthetic source archive'),
                        'code_manifest_sha256': sha(b'synthetic code inventory')}
        self.owner = {'format': 'owned-rl-original-owner-request-v1',
                      'instruction': 'Synthetic test only. No provider execution authority.',
                      'original_epoch': EPOCH, 'owner_id': 'synthetic-owner',
                      'request_id': 'synthetic-request', 'role': 'rl-abc', 'scope': 'production-rl-abc'}
        self.operator = {'format': 'owned-rl-reviewed-operator-v2',
                         'material_review_sha256': sha(b'synthetic material review'),
                         'original_epoch': EPOCH, 'original_request_id': self.owner['request_id'],
                         'original_request_sha256': sha(encoded(self.owner)),
                         'owner_id': self.owner['owner_id'], 'parent_scorer_sha256': sha(b'synthetic scorer'),
                         'raw_source_sha256': self.release['source_sha256'], 'role': 'rl-abc',
                         'scope': 'production-rl-abc',
                         'source_archive_sha256': self.release['source_archive_sha256']}
        self.notebook = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {}, 'cells': [
            {'cell_type': 'markdown', 'metadata': {}, 'source': ['Synthetic input notebook, not execution logs.']},
            *[{'cell_type': 'code', 'metadata': {}, 'source': ['# Synthetic test only\n'],
               'execution_count': None, 'outputs': []} for _ in range(3)]]}
        self.docs = {'active-finalized.ipynb': encoded(self.notebook),
                     'original-request.json': encoded(self.owner), 'operator.json': encoded(self.operator)}
        environment = '/tmp/synthetic-environment008'
        self.prep = {'format': 'irisx/rlvr-parent-preparation-request-v1',
                     'epoch': EPOCH, 'notebook_python_executable': '/usr/bin/python3',
                     'input_root': '/kaggle/input', 'output_root': output,
                     'launcher_root': output + '-launcher', 'environment_root': environment,
                     'finalized': {'operator': self.operator, 'owner_request': self.owner},
                     'release': self.release,
                     'ready': {'format': 'irisx/rlvr-no-model-source-acceptance-v1',
                         'source_root': source_parent + '/runtime',
                         'deployment_root': source_parent + '/deployment',
                         'material_root': source_parent + '/release',
                         'source_archive_path': source_parent + '/source.zip',
                         'source_sha256': self.release['source_sha256'],
                         'source_archive_sha256': self.release['source_archive_sha256'],
                         'manifest_sha256': self.release['code_manifest_sha256'],
                         'source_transport_mode': 'verified-extracted-source-directory',
                         'original_archive_transport': False, 'exact_archive_bytes_available': True,
                         'source_members': 259, 'auxiliary_members': 9, 'model_imported': False,
                         'weights_read': False, 'evaluator_body_read': False, 'provider_mount_verified': False}}
        release_raw = encoded(self.release)
        (self.root / 'notebook-release.json').write_bytes(release_raw)
        self.m = {'runtime_source_sha256': self.release['source_sha256'],
                  'notebooks': [{'role': 'rlvr004', 'output_root': output, 'source_parent': source_parent}],
                  'jit': {'dependencies': [{'path': 'notebook-release.json',
                          'bytes': len(release_raw), 'sha256': sha(release_raw)}]},
                  'terminal_contract': {'terminal_path': self.prefix + '/terminal.json',
                      'evidence_path': self.prefix + '/evidence.zip',
                      'checkpoint_path': self.prefix + '/checkpoints.zip',
                      'archive_caps': {'evidence_archive_bytes': 64 * 1024**2},
                      'storage': {'environment_root': environment}}}
        self.args = SimpleNamespace(manifest=str(self.root / 'manifest.json'), manifest_sha=sha(encoded(self.m)))
        self.f = {'predispatch_epoch': EPOCH, 'outer_deadline_epoch': EPOCH + 42180}
        self.l = {'saved_source': {'sha256': sha(b'synthetic provider-saved notebook')}}
        self.before = {'status': 'ERROR', 'version': VERSION, 'gpu_stop': False,
                       'source_sha256': self.l['saved_source']['sha256'], 'observed_epoch': EPOCH + 224,
                       'metadata_before_sha256': sha(b'synthetic metadata before'),
                       'metadata_sha256': sha(b'synthetic metadata after')}
        self.after = {**self.before, 'observed_epoch': EPOCH + 225}
        self.diagnostic = {'format': 'irisx/rlvr-parent-startup-failure-v1', 'status': 'FAILED',
            'stage': 'parent-environment-policy', 'exception_type': 'ValueError',
            'safe_message': 'Exception text omitted; consult the bounded official execution log.',
            'frames': [{'file': file, 'function': function, 'line': line} for file, function, line in (
                ('launch_notebook.py', 'launch', 322), ('parent_scoring.py', 'worker_environment', 103),
                ('parent_scoring.py', '_worker_library_path', 109),
                ('environment_v2.py', 'installed_cudnn_library', 204), ('release.py', 'need', 19))],
            'observed_epoch': EPOCH + 152.2677517, 'observed_monotonic': 2074.968237037,
            'original_epoch': EPOCH, 'deadline_epoch': EPOCH + 42180,
            'source_sha256': self.release['source_sha256'], 'request_sha256': sha(encoded(self.prep)),
            'dispatch_state': 'not-dispatched', 'preparation_failure': None,
            **{key: False for key in ('proof_available', 'proof_verified', 'clean_owned_closure_verified',
                'closure_authority', 'model_or_GPU_execution_claim', 'environment_values_recorded',
                'operational_success', 'VM_teardown_or_billing_claim')}}
        self.files = {self.outer + '/' + name: raw for name, raw in (
            ('startup-failure.json', encoded(self.diagnostic)), ('preparation-request.json', encoded(self.prep)),
            ('original-request.json', self.docs['original-request.json']),
            ('operator.json', self.docs['operator.json']), ('outer.ipynb', self.docs['active-finalized.ipynb']))}
        self.bridge = SyntheticBridge(self.files)
        # Real provider.output -> DownloadRequest -> binary_get -> bounded sink.
        self.provider = self.common.Provider.__new__(self.common.Provider)
        self.provider.bridge = self.bridge
        self.provider.ensure_read_auth = lambda: None
        self.finalization = self.stack.enter_context(patch.object(self.transport, 'check_finalization',
                                                                 return_value=self.docs))
        self.bracket = self.stack.enter_context(patch.object(self.transport, 'bracket',
                                                           side_effect=lambda *_: (self.after, None, None)))
        self.stack.enter_context(redirect_stdout(io.StringIO()))

    def download_five(self):
        _, _, caps, _ = self.c.output_paths(self.m)
        return [self.c.fetch_selected(self.provider, name, caps[name], 128 * 1024**2) for name in self.files]

    def binding(self, diagnostic=None):
        self.download_five()
        return self.c.preowned_failure_binding(self.m, self.args, self.f, self.before,
            self.diagnostic if diagnostic is None else diagnostic, self.outer)

    def collect(self):
        return self.c.collect(self.provider, self.m, self.l, {}, self.f, self.args, self.before)

    def test_real_shaped_null_five_file_collection_is_non_authoritative(self):
        result = self.collect()
        self.assertEqual(result['status'], 'INCOMPLETE_DIAGNOSTIC_EVIDENCE')
        self.assertEqual(result['reason'], 'SOURCE_BOUND_PRE_OWNED_STARTUP_FAILURE')
        self.assertEqual(result['provider_status'], 'ERROR')
        for key in ('terminal_validated', 'consumer_admitted', 'production_admitted',
                    'scientific_evidence_eligible', 'science_complete', 'operational_complete',
                    'comparison_complete', 'comparison_eligible', 'compute_matched',
                    'public_benchmark_evidence_eligible', 'verified_public_threshold_reached',
                    'provider_operational_success', 'owned_closure_verified', 'physical_costs_known',
                    'billing_verified', 'operational_success', 'public_goal_met', 'scientific_goal_met',
                    'goal_met', 'automatic_retry', 'whole_provider_inventory_verified'):
            self.assertIs(result[key], False, key)
        self.assertIsNone(result['public_score'])
        self.assertEqual(result['separate_checkpoint_presence'], 'UNKNOWN')
        self.assertEqual(result['missing'], [])
        self.assertEqual({call['name'] for call in self.bridge.calls}, set(self.files))
        self.assertEqual(len(self.bridge.calls), 5)
        receipt = self.c.obj(result['retrieval_receipt']['path'])
        self.assertEqual(receipt['numeric_output_version'], VERSION)
        self.assertEqual(receipt['inventory_scope'], 'selected_outputs_only')
        self.assertIs(receipt['whole_provider_inventory_verified'], False)
        self.assertEqual(receipt['before'], self.before)
        self.assertEqual(receipt['after'], self.after)
        self.assertEqual(receipt['manifest_sha256'], self.args.manifest_sha)
        self.assertEqual(receipt['launch_receipt_sha256'], sha((self.state / 'notebook-rlvr004-receipt.json').read_bytes()))
        for row in receipt['files']:
            self.assertEqual((row['version'], row['numeric_version'], row['http_status'], row['source_kind']),
                             (VERSION, VERSION, 200, 'provider_download'))
            raw = self.files[row['provider_path']]
            self.assertEqual((row['bytes'], row['sha256']), (len(raw), sha(raw)))
            self.assertEqual((self.c.DOWNLOADS / row['provider_path']).read_bytes(), raw)
        for name in (self.outer + '/preparation/stderr.txt', self.outer + '/preparation/stdout.txt',
                     self.prefix + '/artifact-inventory.json', self.prefix + '/terminal.json'):
            self.assertIn(name, result['unattempted_paths'])
        self.assertFalse((self.c.OUT / 'TERMINAL-VALIDATION.json').exists())
        self.assertFalse((self.c.OUT / 'TERMINAL-CHECKPOINT.json').exists())
        self.assertTrue((self.c.OUT / 'TERMINAL-BLOCKER.json').exists())
        self.finalization.assert_called_once()
        self.bracket.assert_called_once()

    def test_legacy_exact_schema_remains_supported(self):
        document = copy.deepcopy(self.diagnostic)
        del document['preparation_failure']
        self.assertIs(self.binding(document)['owned_closure_verified'], False)

    def test_actual_producer_default_null_matches_collector(self):
        directory = self.root / 'synthetic-producer'
        directory.mkdir()
        context = {key: self.diagnostic[key] for key in ('source_sha256', 'request_sha256', 'original_epoch', 'deadline_epoch')}
        with patch.object(producer.time, 'time', return_value=self.diagnostic['observed_epoch']), \
                patch.object(producer.time, 'monotonic', return_value=self.diagnostic['observed_monotonic']):
            self.assertTrue(producer.persist_failure(directory, stage='parent-environment-policy',
                error=ValueError('synthetic'), context=context, dispatch_state='not-dispatched'))
        document = self.c.strict_json((directory / 'startup-failure.json').read_bytes())
        self.assertEqual(set(document), set(self.diagnostic))
        self.assertIs(document['preparation_failure'], None)
        self.assertIs(self.binding(document)['diagnostic_source_bound'], True)

    def test_unknown_top_level_keys_and_missing_required_keys_rejected(self):
        for key in ('arbitrary', 'scoring_authority', 'preparation_failures'):
            with self.subTest(extra=key), self.assertRaisesRegex(self.c.GuardError, 'closed_startup_diagnostic'):
                self.binding({**self.diagnostic, key: None})
        for key in set(self.diagnostic) - {'preparation_failure'}:
            document = copy.deepcopy(self.diagnostic)
            del document[key]
            with self.subTest(missing=key), self.assertRaisesRegex(self.c.GuardError, 'closed_startup_diagnostic'):
                self.binding(document)

    def test_every_non_null_preparation_failure_rejected(self):
        projection = {'format': 'irisx/rlvr-preparation-failure-projection-v1',
            'stage': 'offline-installation', 'exception_type': 'ValueError',
            'source_authenticated': True, 'report_sha256': sha(b'synthetic child report'),
            'diagnostic_only': True, 'closure_authority': False, 'model_or_GPU_execution_claim': False,
            'scoring_authority': False, 'operational_success': False}
        values = (False, True, 0, 1, '', 'null', [], [None], {}, projection,
                  {'preparation_failure': None}, {**projection, 'unknown': None},
                  {**projection, 'report_sha256': {'nested': []}}, {**projection, 'closure_authority': True})
        for value in values:
            with self.subTest(value=value), self.assertRaisesRegex(self.c.GuardError, 'preowned_preparation_failure_must_be_null'):
                self.binding({**self.diagnostic, 'preparation_failure': value})

    def test_malformed_nested_frames_remain_rejected(self):
        values = ({}, [None], [{'file': 'x', 'function': 'f', 'line': True}],
                  [{'file': 'x', 'function': 'f', 'line': 0}],
                  [{'file': 'x', 'function': 'f', 'line': 1, 'unknown': None}],
                  [{'file': {'nested': 'x'}, 'function': 'f', 'line': 1}],
                  [{'file': 'x', 'function': 'f', 'line': 1}] * 33)
        for value in values:
            with self.subTest(value=value), self.assertRaisesRegex(self.c.GuardError, 'bounded_diagnostic_frames|diagnostic_frame_schema'):
                self.binding({**self.diagnostic, 'frames': value})

    def test_all_authority_flags_must_be_literal_false(self):
        for key in ('proof_available', 'proof_verified', 'clean_owned_closure_verified', 'closure_authority',
                    'model_or_GPU_execution_claim', 'environment_values_recorded', 'operational_success',
                    'VM_teardown_or_billing_claim'):
            for value in (True, 0, None, 'false'):
                with self.subTest(key=key, value=value), self.assertRaisesRegex(self.c.GuardError, 'diagnostic_cannot_assert_proof'):
                    self.binding({**self.diagnostic, key: value})

    def test_source_request_epoch_stage_and_dispatch_bindings_preserved(self):
        cases = [('source_sha256', sha(b'wrong'), 'startup_source_identity'),
                 ('request_sha256', sha(b'wrong'), 'diagnostic_request_bytes'),
                 ('original_epoch', EPOCH + 1, 'startup_original_clock'),
                 ('deadline_epoch', EPOCH + 43200, 'startup_original_clock'),
                 ('observed_epoch', EPOCH - 1, 'startup_original_clock'),
                 ('observed_epoch', self.before['observed_epoch'] + 1, 'startup_original_clock'),
                 ('observed_monotonic', -1, 'startup_original_clock'),
                 ('observed_epoch', float('nan'), 'finite_startup_time'),
                 ('original_epoch', True, 'finite_startup_time'),
                 ('stage', 'owned-preparation', 'preowned_stage_only'),
                 ('dispatch_state', 'dispatched', 'preowned_stage_only')]
        for key, value, error in cases:
            with self.subTest(key=key, value=value), self.assertRaisesRegex(self.c.GuardError, error):
                self.binding({**self.diagnostic, key: value})

    def test_prepared_release_or_jit_mutation_still_rejected(self):
        self.download_five()
        for name in ('outer.ipynb', 'original-request.json', 'operator.json'):
            path = self.c.DOWNLOADS / self.outer / name
            original = path.read_bytes()
            path.write_bytes(original + b'\n')
            with self.subTest(name=name), self.assertRaisesRegex(self.c.GuardError, 'preowned_exact_jit_documents'):
                self.c.preowned_failure_binding(self.m, self.args, self.f, self.before, self.diagnostic, self.outer)
            path.write_bytes(original)
        prep = copy.deepcopy(self.prep)
        prep['release']['source_archive_sha256'] = sha(b'wrong archive')
        raw = encoded(prep)
        (self.c.DOWNLOADS / self.outer / 'preparation-request.json').write_bytes(raw)
        with self.assertRaisesRegex(self.c.GuardError, 'preowned_reviewed_release_jit'):
            self.c.preowned_failure_binding(self.m, self.args, self.f, self.before,
                {**self.diagnostic, 'request_sha256': sha(raw)}, self.outer)

    def test_cache_numeric_http_provenance_and_bytes_are_still_checked(self):
        rows = self.download_five()
        row = rows[0]
        name = row['provider_path']
        path = self.c.OUT / 'download-receipts' / (sha(name.encode()) + '.json')
        for key, value in (('version', 40), ('numeric_version', 40), ('http_status', 404),
                           ('source_kind', 'local_copy'), ('provider_path', 'wrong')):
            path.write_bytes(encoded({**row, key: value}))
            with self.subTest(key=key), self.assertRaisesRegex(self.c.GuardError, 'selected_cache_binding'):
                self.collect()
        for key, value in (('bytes', row['bytes'] + 1), ('sha256', sha(b'wrong bytes'))):
            path.write_bytes(encoded({**row, key: value}))
            with self.subTest(key=key), self.assertRaisesRegex(self.c.GuardError, 'selected_cache_hash'):
                self.collect()
        path.write_bytes(encoded(row))
        (self.c.DOWNLOADS / name).write_bytes(b'{}')
        with self.assertRaisesRegex(self.c.GuardError, 'selected_cache_hash'):
            self.collect()

    def test_after_snapshot_must_retain_version_source_status_and_order(self):
        for key, value in (('version', 40), ('source_sha256', sha(b'wrong saved notebook')),
                           ('status', 'COMPLETE'), ('gpu_stop', True), ('observed_epoch', EPOCH)):
            prior = self.after[key]
            self.after[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(self.c.GuardError,
                    'preowned_terminal_source_bracket|ordered_preowned_collection_bracket'):
                self.collect()
            self.after[key] = prior
        self.assertFalse((self.c.OUT / 'TERMINAL-BLOCKER.json').exists())

    def test_invalid_non_null_collection_writes_no_terminal_receipt(self):
        self.files[self.outer + '/startup-failure.json'] = encoded({**self.diagnostic, 'preparation_failure': {}})
        with self.assertRaisesRegex(self.c.GuardError, 'preowned_preparation_failure_must_be_null'):
            self.collect()
        self.assertEqual(len(self.bridge.calls), 5)
        self.bracket.assert_not_called()
        self.assertFalse(list(self.c.OUT.glob('TERMINAL-*.json')))
        self.assertFalse(list(self.c.OUT.glob('retrieval-*.json')))

    def test_duplicate_null_key_and_nonfinite_json_rejected(self):
        raw = encoded(self.diagnostic)
        duplicate = raw[:-2] + b',"preparation_failure":null}\n'
        for malformed in (duplicate, b'{"preparation_failure":NaN}', b'{"preparation_failure":{"x":0,"x":1}}'):
            with self.subTest(raw=malformed[-60:]), self.assertRaises(self.c.GuardError):
                self.c.strict_json(malformed)


if __name__ == '__main__':
    unittest.main()

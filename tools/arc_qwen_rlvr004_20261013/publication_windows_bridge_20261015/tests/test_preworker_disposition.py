"""Synthetic offline source-bound evidence; NEVER genuine native admission."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
PREFIX = ROOT.relative_to(REPO).as_posix() + '/'
spec = importlib.util.spec_from_file_location('tested_preworker_disposition', ROOT / 'preworker_disposition.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def versions():
    return {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39,
            'inactive': 40, 'active': 41}


def synthetic_native_configuration(pins, configured_versions):
    """Full normal f5 document for offline integration fixtures only."""
    return {
        'format': 'irisx/run008-windows-sdk-runtime-v1', 'account': 'danielwuu',
        'identity': {'sid': 'S-1-5-21-1-2-3-4', 'profile': r'C:\Users\synthetic'},
        'source_root': r'C:\synthetic\frozen-f5',
        'runtime': {'executable': {'path': r'C:\synthetic\venv\Scripts\python.exe', 'sha256': '1' * 64},
            'base_executable': {'path': r'C:\synthetic\Python312\python.exe', 'sha256': '2' * 64},
            'pyvenv_cfg_sha256': '3' * 64, 'venv_prefix': r'C:\synthetic\venv',
            'sdk_root': r'C:\synthetic\venv\Lib\site-packages', 'python_version': [3, 12, 8]},
        'sources': {name: copy.deepcopy(pins[name]) for name in p.NATIVE_SOURCES},
        'versions': dict(configured_versions), 'network_environment_sha256': {}, 'requests_ca_bundle': None}


class PreworkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest_raw = (ROOT / 'context-source-pins.json').read_bytes()
        cls.pins = json.loads(cls.manifest_raw)['sources']
        cls.sources = {name: subprocess.check_output(['git', 'show',
            p.HISTORICAL_COMMIT + ':' + PREFIX + name], cwd=REPO)
            for name in p.DIAGNOSTIC_SOURCES}

    def setUp(self):
        self.storage = {}
        self.reads = []
        self.source_rows = {name: self.store('/synthetic/frozen-f5/' + name, raw)
                            for name, raw in self.sources.items()}
        self.native = synthetic_native_configuration(self.pins, versions())
        self.native_row = self.store('/synthetic/normal-native.json', canonical(self.native))
        self.nonce = sha(b'OFFLINE synthetic lease failure, not actual native evidence')
        self.session = 'native-bridge-' + self.nonce
        self.claim_name = self.session + '.claim.json'
        self.journal_name = self.session + '-journal.json'
        self.claim = {'format': 'irisx/windows-bridge-session-claim-v1', 'nonce': self.nonce,
            'account': 'danielwuu', 'versions': versions(), 'configuration_sha256': '4' * 64,
            'bridge_configuration_sha256': self.native_row['sha256'],
            'publication_manifest_sha256': '5' * 64, 'deadline_epoch': 1800043200.0,
            'max_seconds': 43200.0, 'synthetic_test_only': False}
        self.initial_diagnostics = {'format': 'irisx/windows-bridge-failure-diagnostics-v1',
            'ready_observed': False, 'authenticated_observed': False, 'rpc_phase_observed': 'not_started',
            'cleanup': 'not_started', 'writer_close': 'not_attempted', 'finish': 'not_attempted',
            'release': 'not_attempted', 'proxy_exit_status': None, 'receipt_validation': 'not_attempted',
            'receipt_bytes_capped': None, 'receipt_sha256': None, 'supervisor_reason': 'unavailable'}
        self.diagnostics = {**self.initial_diagnostics, 'cleanup': 'complete', 'writer_close': 'closed',
            'finish': 'complete', 'release': 'complete', 'proxy_exit_status': 125,
            'receipt_validation': 'rejected', 'receipt_bytes_capped': 184,
            # A digest is retained, but raw receipt bytes are deliberately absent.
            'receipt_sha256': sha(b'synthetic retained diagnostic digest'),
            'supervisor_reason': 'supervisor_lease_failed'}
        self.files = {}
        self.build()

    def store(self, path, raw):
        self.storage[path] = raw
        return {'path': path, 'bytes': len(raw), 'sha256': sha(raw)}

    def verified(self, row):
        self.reads.append(row['path'])
        return self.storage[row['path']]

    def build(self):
        self.files[self.claim_name] = canonical(self.claim)
        base = {'format': 'irisx/windows-bridge-session-journal-v1', 'nonce': self.nonce,
            'claim_sha256': sha(self.files[self.claim_name]), 'stage': 'launch_intent',
            'synthetic_test_only': False, 'native_process_closure_verified': False,
            'mutation_attempted': False}
        arguments = {key: self.claim[key] for key in p.OPEN_KEYS}
        request = {'operation': 'open', 'arguments': arguments, 'deadline_epoch': 1800000120.0,
                   'max_seconds': 120}
        operation = {**base, 'stage': 'operation_intent', 'operation': 'open', 'sequence': 1,
            'request_sha256': sha(canonical(request)[:-1]), 'deadline_epoch': request['deadline_epoch']}
        initial = {**operation, 'stage': 'UNKNOWN', 'unknown_reason': 'BRIDGE_OPERATION_UNKNOWN',
                   'failure_diagnostics': self.initial_diagnostics}
        final = {**initial, 'failure_diagnostics': self.diagnostics}
        self.event_names = ['events/' + str(1800000000000000000 + index) + '-' + self.session
                            + '-' + format(index, '08x') + '.json' for index in range(4)]
        for name, value in zip(self.event_names, (base, operation, initial, final)):
            self.files[name] = canonical(value)
        self.files[self.journal_name] = self.files[self.event_names[-1]]

    def classify(self, **kwargs):
        options = {'state_root': '/synthetic/STATE', 'native_configuration': self.native_row,
                   'diagnostic_sources': self.source_rows, 'source_manifest': self.manifest_raw,
                   'verified': self.verified}
        options.update(kwargs)
        return p.classify(self.files, **options)

    def change_event(self, index, change, *, journal=True):
        value = json.loads(self.files[self.event_names[index]])
        change(value)
        self.files[self.event_names[index]] = canonical(value)
        if index == 3 and journal:
            self.files[self.journal_name] = self.files[self.event_names[index]]

    def test_exact_lease_disposition_is_immutable_read_only_and_not_closure(self):
        before = copy.deepcopy((self.files, self.storage, self.native_row, self.source_rows))
        with (mock.patch('builtins.open', side_effect=AssertionError('no filesystem writes or reads')),
              mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('no process'))):
            result = self.classify()
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['disposition'], 'process_not_started')
        self.assertIs(row['process_started'], False)
        self.assertIs(row['native_process_closure_verified'], False)
        self.assertEqual(row['excluded_root_names'], (self.claim_name, self.journal_name))
        self.assertEqual(row['claim_sha256'], sha(self.files[self.claim_name]))
        self.assertEqual(row['journal_sha256'], sha(self.files[self.journal_name]))
        self.assertEqual(row['nonce'], self.nonce)
        self.assertEqual([item['path'] for item in row['events']],
                         ['/synthetic/STATE/' + name for name in self.event_names])
        self.assertEqual(before, (self.files, self.storage, self.native_row, self.source_rows))
        self.assertEqual(len(self.reads), len(p.DIAGNOSTIC_SOURCES) + 1)
        with self.assertRaises(TypeError):
            row['disposition'] = 'closed'
        with self.assertRaises(TypeError):
            row['claim']['sha256'] = '0' * 64
        self.assertEqual(json.loads(self.files[self.journal_name])['stage'], 'UNKNOWN')

    def test_original_unknown_without_diagnostics_remains_unclassified(self):
        for index in (2, 3):
            self.change_event(index, lambda row: row.pop('failure_diagnostics'))
        self.assertEqual(self.classify(verified=mock.Mock(side_effect=AssertionError('no sources needed'))), ())

    def test_unsupported_ambiguous_reasons_remain_unclassified(self):
        for reason in ('supervisor_supervision_failed', 'supervisor_worker_lease_failed',
                       'supervisor_config_bootstrap_failed', 'supervisor_error', 'unavailable', 'unrecognized'):
            with self.subTest(reason=reason):
                self.diagnostics['supervisor_reason'] = reason
                self.build()
                self.assertEqual(self.classify(), ())

    def test_additional_unknown_is_not_hidden(self):
        other = 'native-bridge-' + 'a' * 64
        self.files[other + '.claim.json'] = canonical({'nonce': 'a' * 64})
        self.files[other + '-journal.json'] = canonical({'stage': 'UNKNOWN', 'nonce': 'a' * 64})
        result = self.classify()
        excluded = set(result[0]['excluded_root_names'])
        self.assertNotIn(other + '.claim.json', excluded)
        self.assertNotIn(other + '-journal.json', excluded)

    def test_source_manifest_cannot_be_replaced_even_self_consistently(self):
        manifest = json.loads(self.manifest_raw)
        manifest['sources']['bridge_client.py']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(p.DispositionError, 'source_manifest_changed'):
            self.classify(source_manifest=canonical(manifest))

    def test_each_required_source_is_the_original_f5_bytes(self):
        for name in sorted(p.DIAGNOSTIC_SOURCES):
            with self.subTest(name=name):
                rows = copy.deepcopy(self.source_rows)
                rows[name] = self.store('/synthetic/modified/' + name, self.sources[name] + b'\n')
                with self.assertRaisesRegex(p.DispositionError, 'source_not_pinned_f5'):
                    self.classify(diagnostic_sources=rows)

    def test_changed_source_bytes_cannot_use_the_old_descriptor(self):
        self.storage[self.source_rows['bridge_client.py']['path']] += b'\n'
        with self.assertRaisesRegex(p.DispositionError, 'descriptor_changed'):
            self.classify()

    def test_missing_source_or_malformed_descriptor_rejected(self):
        rows = copy.deepcopy(self.source_rows)
        rows.pop('protocol.py')
        with self.assertRaisesRegex(p.DispositionError, 'diagnostic_source_closure'):
            self.classify(diagnostic_sources=rows)
        for change in ({'bytes': True}, {'sha256': 'wrong'}, {'path': '../relative'}, {'extra': 1}):
            with self.subTest(change=change):
                rows = copy.deepcopy(self.source_rows)
                rows['protocol.py'].update(change)
                with self.assertRaises(p.DispositionError):
                    self.classify(diagnostic_sources=rows)

    def test_native_configuration_hash_is_bound_to_claim(self):
        self.claim['bridge_configuration_sha256'] = 'f' * 64
        self.build()
        with self.assertRaisesRegex(p.DispositionError, 'claim_binding'):
            self.classify()

    def test_each_native_source_pin_mismatch_is_rejected(self):
        for name in p.NATIVE_SOURCES:
            with self.subTest(name=name):
                native = copy.deepcopy(self.native)
                native['sources'][name]['sha256'] = 'f' * 64
                descriptor = self.store('/synthetic/altered-native.json', canonical(native))
                with self.assertRaisesRegex(p.DispositionError, 'native_source_not_pinned_f5'):
                    self.classify(native_configuration=descriptor)

    def test_native_recovery_or_extra_fields_are_not_normal_configuration(self):
        for change in ({'format': 'irisx/run008-windows-sdk-recovery-runtime-v1'}, {'recovery': {}},
                       {'runtime': {}}, {'sources': {}}, {'versions': {**versions(), 'code': True}}):
            with self.subTest(change=change):
                native = {**self.native, **change}
                descriptor = self.store('/synthetic/altered-native.json', canonical(native))
                with self.assertRaises(p.DispositionError):
                    self.classify(native_configuration=descriptor)

    def test_claim_schema_binding_synthetic_and_number_guards(self):
        original = copy.deepcopy(self.claim)
        for change in ({'extra': None}, {'nonce': 'a' * 64}, {'synthetic_test_only': True},
                       {'max_seconds': 43200}, {'max_seconds': True}, {'deadline_epoch': False},
                       {'account': 'someone-else'}, {'configuration_sha256': 'invalid'},
                       {'publication_manifest_sha256': None}, {'versions': {**versions(), 'active': 42}}):
            with self.subTest(change=change):
                self.claim = {**original, **change}
                self.build()
                with self.assertRaises(p.DispositionError):
                    self.classify()

    def test_final_diagnostic_contradictions_block(self):
        original = copy.deepcopy(self.diagnostics)
        for change in ({'ready_observed': True}, {'authenticated_observed': True},
                       {'rpc_phase_observed': 'active'}, {'rpc_phase_observed': 'completed'},
                       {'cleanup': 'incomplete'}, {'writer_close': 'failed'}, {'finish': 'timeout'},
                       {'release': 'failed'}, {'proxy_exit_status': 0}, {'proxy_exit_status': True},
                       {'receipt_validation': 'valid_job_zero'}, {'receipt_validation': 'unavailable'},
                       {'receipt_bytes_capped': 0}, {'receipt_bytes_capped': 4097},
                       {'receipt_bytes_capped': True}, {'receipt_sha256': None}, {'extra': None}):
            with self.subTest(change=change):
                self.diagnostics = {**original, **change}
                self.build()
                with self.assertRaises(p.DispositionError):
                    self.classify()

    def test_any_event_ready_auth_mutation_or_closure_contradiction_blocks(self):
        original_files = copy.deepcopy(self.files)
        for index in range(4):
            for key, value in (('stage', 'authenticated'), ('mutation_attempted', True),
                               ('native_process_closure_verified', True), ('ready', True),
                               ('nonce', 'a' * 64), ('claim_sha256', 'f' * 64)):
                with self.subTest(index=index, key=key):
                    self.files = copy.deepcopy(original_files)
                    self.change_event(index, lambda row: row.update({key: value}))
                    with self.assertRaises(p.DispositionError):
                        self.classify()

    def test_initial_diagnostic_must_prove_no_activity(self):
        self.change_event(2, lambda row: row['failure_diagnostics'].update(rpc_phase_observed='completed'))
        with self.assertRaisesRegex(p.DispositionError, 'diagnostic_preworker_state'):
            self.classify()

    def test_exact_unknown_code_and_open_request_are_required(self):
        original_files = copy.deepcopy(self.files)
        for change in ({'unknown_reason': 'BRIDGE_OPEN_UNKNOWN'}, {'operation': 'save'},
                       {'sequence': 2}, {'sequence': True}, {'request_sha256': '0' * 64},
                       {'deadline_epoch': 1801000000.0}):
            with self.subTest(change=change):
                self.files = copy.deepcopy(original_files)
                self.change_event(3, lambda row: row.update(change))
                with self.assertRaises(p.DispositionError):
                    self.classify()
        self.files = copy.deepcopy(original_files)
        for index in (1, 2, 3):
            self.change_event(index, lambda row: row.update(request_sha256='0' * 64))
        with self.assertRaisesRegex(p.DispositionError, 'open_request_hash'):
            self.classify()

    def test_operation_number_type_drift_is_not_equivalent_evidence(self):
        self.change_event(3, lambda row: row.update(deadline_epoch=int(row['deadline_epoch'])))
        with self.assertRaisesRegex(p.DispositionError, 'operation_changed'):
            self.classify()

    def test_helper_supports_other_nonces_and_timestamps(self):
        for seed, epoch in ((b'first alternate synthetic nonce', 1792074033.0),
                            (b'second alternate synthetic nonce', 1700000000.25)):
            with self.subTest(seed=seed):
                nonce = sha(seed)
                self.files = synthetic_lease_files(self.native_row['sha256'], versions(),
                                                   nonce=nonce, epoch=epoch)
                result = self.classify()
                self.assertEqual(result[0]['nonce'], nonce)
                self.assertEqual(len(result[0]['events']), 4)

    def test_two_independent_preworker_failures_have_disjoint_pairs(self):
        second = synthetic_lease_files(self.native_row['sha256'], versions(),
                                       nonce=sha(b'another synthetic lease failure'))
        self.files.update(second)
        result = self.classify()
        self.assertEqual(len(result), 2)
        self.assertEqual(len({name for row in result for name in row['excluded_root_names']}), 4)

    def test_unrelated_events_and_refresh_do_not_change_classification(self):
        self.files['events/1800000000000000004-status-00000000.json'] = canonical(
            {'stage': 'closed', 'nonce': 'a' * 64, 'native_process_closure_verified': True})
        self.files['native-auth-refresh-' + 'b' * 24 + '.claim.json'] = canonical(
            {'bridge_nonce': 'b' * 64, 'existing_grant_only': True})
        self.assertEqual(len(self.classify()), 1)

    def test_missing_duplicate_out_of_order_and_extra_events_block(self):
        original_files = copy.deepcopy(self.files)
        for index in range(4):
            with self.subTest(missing=index):
                self.files = copy.deepcopy(original_files)
                self.files.pop(self.event_names[index])
                with self.assertRaisesRegex(p.DispositionError, 'session_event_sequence'):
                    self.classify()
        self.files = copy.deepcopy(original_files)
        extra = 'events/1800000000000000004-' + self.session + '-ffffffff.json'
        self.files[extra] = self.files[self.event_names[-1]]
        with self.assertRaisesRegex(p.DispositionError, 'session_event_sequence'):
            self.classify()
        self.files = copy.deepcopy(original_files)
        self.files[self.event_names[0]], self.files[self.event_names[1]] = (
            self.files[self.event_names[1]], self.files[self.event_names[0]])
        with self.assertRaises(p.DispositionError):
            self.classify()
        self.files = copy.deepcopy(original_files)
        name = self.event_names[1].replace('1800000000000000001', '1800000000000000000')
        self.files[name] = self.files.pop(self.event_names[1])
        with self.assertRaisesRegex(p.DispositionError, 'session_event_sequence'):
            self.classify()

    def test_final_event_bytes_must_equal_root_journal(self):
        self.files[self.journal_name] += b' '
        with self.assertRaisesRegex(p.DispositionError, 'journal_event_frontier'):
            self.classify()

    def test_refresh_and_other_nonce_mentions_anywhere_block(self):
        for name, value in (
            ('native-auth-refresh-' + 'a' * 24 + '.claim.json', {'bridge_nonce': self.nonce}),
            ('native-auth-refresh-' + 'a' * 24 + '-journal.json', {'stage': 'refresh_accepted', 'bridge_nonce': self.nonce}),
            ('events/1800000000000000004-other-00000000.json', {'nonce': self.nonce, 'ready': True}),
            ('other.json', {'nested': [{'owner': self.session}]})):
            with self.subTest(name=name):
                self.files[name] = canonical(value)
                with self.assertRaisesRegex(p.DispositionError, 'contradictory_nonce_evidence'):
                    self.classify()
                self.files.pop(name)

    def test_duplicate_json_nonfinite_and_invalid_snapshot_paths_block(self):
        for raw in (b'{"stage":1,"stage":2}', b'{"value":NaN}', b'{"value":Infinity}',
                    b'{"value":1e999}', b'[]', b'{"value":' + b'1' * 25 + b'}', b'\xff'):
            with self.subTest(raw=raw):
                self.files['bad.json'] = raw
                with self.assertRaises(p.DispositionError):
                    self.classify()
        self.files.pop('bad.json')
        for name in ('../escape.json', 'nested/other.json', 'events/bad.json'):
            with self.subTest(name=name):
                self.files[name] = b'{}'
                with self.assertRaises(p.DispositionError):
                    self.classify()
                self.files.pop(name)

    def test_orphan_purported_lease_failure_blocks(self):
        self.files.pop(self.claim_name)
        with self.assertRaisesRegex(p.DispositionError, 'session_missing_record'):
            self.classify()

    def test_source_semantics_are_historical_not_candidate_imports(self):
        # Source assertions document the actual reviewed interpretation rather
        # than introduce runtime caller-controlled stage/reason capabilities.
        supervisor = self.sources['win_supervisor.py'].decode()
        self.assertLess(supervisor.index("receipt['reason'] = 'supervisor_lease_failed'"),
                        supervisor.index("config = _pinned_module('native_config'"))
        self.assertLess(supervisor.index("config = _pinned_module('native_config'"),
                        supervisor.index('result = supervise(command'))
        self.assertIn('job = JobProcess(argv, env=env, job_nonce=', supervisor)
        bridge = self.sources['bridge_client.py'].decode()
        self.assertIn("result['nonce'] == self.nonce", bridge)
        self.assertIn('result = self.protocol.strict_json(raw)', bridge)
        self.assertIn("diagnostics['supervisor_reason'] = result['reason']", bridge)
        self.assertIn("PROTOCOL_SOURCE_SHA256 = '" + self.pins['protocol.py']['sha256'] + "'", bridge)
        self.assertEqual(sha(self.manifest_raw), p.SOURCE_PINS_SHA256)


def synthetic_lease_files(native_sha256, configured_versions, *, configuration_sha256='4' * 64,
                          publication_manifest_sha256='5' * 64, nonce=None, epoch=1800000000.0):
    """Produce synthetic root/event bytes; these never constitute native evidence.

    The caller supplies its complete authenticated normal f5 native template's
    hash and writes these ONLY into an isolated synthetic test STATE.
    """
    fixture = PreworkerTests(methodName='runTest')
    fixture.nonce = nonce or sha(b'OFFLINE synthetic integration pre-worker failure')
    fixture.session = 'native-bridge-' + fixture.nonce
    fixture.claim_name = fixture.session + '.claim.json'
    fixture.journal_name = fixture.session + '-journal.json'
    fixture.claim = {'format': 'irisx/windows-bridge-session-claim-v1', 'nonce': fixture.nonce,
        'account': 'danielwuu', 'versions': dict(configured_versions),
        'configuration_sha256': configuration_sha256,
        'bridge_configuration_sha256': native_sha256,
        'publication_manifest_sha256': publication_manifest_sha256,
        'deadline_epoch': float(epoch) + 43200.0, 'max_seconds': 43200.0,
        'synthetic_test_only': False}
    fixture.initial_diagnostics = {'format': 'irisx/windows-bridge-failure-diagnostics-v1',
        'ready_observed': False, 'authenticated_observed': False, 'rpc_phase_observed': 'not_started',
        'cleanup': 'not_started', 'writer_close': 'not_attempted', 'finish': 'not_attempted',
        'release': 'not_attempted', 'proxy_exit_status': None, 'receipt_validation': 'not_attempted',
        'receipt_bytes_capped': None, 'receipt_sha256': None, 'supervisor_reason': 'unavailable'}
    fixture.diagnostics = {**fixture.initial_diagnostics, 'cleanup': 'complete', 'writer_close': 'closed',
        'finish': 'complete', 'release': 'complete', 'proxy_exit_status': 125,
        'receipt_validation': 'rejected', 'receipt_bytes_capped': 184,
        'receipt_sha256': sha(b'synthetic retained diagnostic digest'),
        'supervisor_reason': 'supervisor_lease_failed'}
    fixture.files = {}
    fixture.build()
    if epoch != 1800000000.0:
        # Rebind the ordinary open preimage and preserve exact event ordering.
        arguments = {key: fixture.claim[key] for key in p.OPEN_KEYS}
        request = {'operation': 'open', 'arguments': arguments,
                   'deadline_epoch': float(epoch) + 120.0, 'max_seconds': 120}
        for index in (1, 2, 3):
            fixture.change_event(index, lambda row: row.update(
                deadline_epoch=request['deadline_epoch'], request_sha256=sha(canonical(request)[:-1])))
        for index, name in enumerate(fixture.event_names):
            replacement = 'events/' + str(int(float(epoch) * 1e9) + index) + '-' + fixture.session + '-' + format(index, '08x') + '.json'
            fixture.files[replacement] = fixture.files.pop(name)
    return fixture.files


if __name__ == '__main__':
    unittest.main()

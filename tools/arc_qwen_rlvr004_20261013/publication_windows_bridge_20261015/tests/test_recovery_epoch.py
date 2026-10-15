"""CPU-only fixtures: never native restart/auth/provider/capability evidence."""
import contextlib
import copy
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
SPEC = importlib.util.spec_from_file_location('test_recovery_epoch_module', ROOT / 'recovery_epoch.py')
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def write(path, value):
    raw = value if type(value) is bytes else r.canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return r.descriptor(path)


def request_hash(operation, arguments, deadline, seconds=120):
    return r.sha(json.dumps({'operation': operation, 'arguments': arguments,
        'deadline_epoch': deadline, 'max_seconds': seconds}, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode())


class Common:
    def __init__(self, root):
        self.root = root
        self.writes = []
        self.count = 1000
        self.fail = None
        self.config = types.SimpleNamespace(state_root=root, document_sha256='a' * 64)
        self.mapping = {'STATE': root, 'lock': self.lock, 'claim': self.claim,
                        'journal': self.journal, 'configured': lambda: self.config}

    @contextlib.contextmanager
    def lock(self, name):
        with (self.root.parent / 'publisher.lock').open('a+b') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _write(self, path, value):
        raw = r.canonical(value)
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.writes.append(path.name)
        return r.descriptor(path)

    def claim(self, name, value):
        result = self._write(self.root / (name + '.claim.json'), value)
        if self.fail == 'after_claim':
            raise OSError('synthetic crash after durable claim')
        return result

    def journal(self, name, value):
        self.count += 1
        self._write(self.root / 'events' / f'{self.count}-{name}-1234abcd.json', value)
        if self.fail == 'after_event':
            raise OSError('synthetic crash after durable event')
        temporary = self.root / (name + '-journal.json.fixture.tmp')
        self._write(temporary, value)
        if self.fail == 'after_temp':
            raise OSError('synthetic crash after durable temporary')
        destination = self.root / (name + '-journal.json')
        os.replace(temporary, destination)
        fd = os.open(self.root, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return destination


class EpochTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_sources = {}
        prefix = 'tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/'
        for name in r.ORIGINAL_SOURCES:
            cls.original_sources[name] = subprocess.check_output(
                ['git', 'show', r.ORIGINAL_COMMIT + ':' + prefix + name], cwd=REPO)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='offline-recovery-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        (self.state / 'events').mkdir(parents=True)
        self.c = Common(self.state)
        self.now = 1792050000.0
        self.challenge = 'e' * 64
        self.failed_nonce = '1' * 64
        self.closed_nonce = '2' * 64
        self.new_nonce = '3' * 64
        self.inject_refresh = False
        self.versions = {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39,
                         'inactive': 40, 'active': 41}
        self.source = '# synthetic notebook source; no evaluator data\n'
        self.dataset = {'id': 12504696, 'ref': 'danielwuu/iris-x-learning-agent-code-20261011',
            'isPrivate': True, 'currentVersionNumber': 20, 'title': 'Synthetic dataset',
            'licenseName': 'Other', 'ownerRef': 'danielwuu', 'versions': [{'versionNumber': 20}]}
        self.metadata = {'id': 138123872, 'ref': 'danielwuu/iris-x-learning-agent-20261011',
            'isPrivate': True, 'currentVersionNumber': 39, 'title': 'Synthetic kernel', 'language': 'python',
            'kernelType': 'notebook', 'kernelDataSources': [], 'enableGpu': True, 'enableTpu': False,
            'enableInternet': False, 'modelDataSources': [], 'datasetDataSources': [],
            'competitionDataSources': [], 'dockerImage': 'synthetic/image', 'machineShape': 'Synthetic'}
        self.native = {'format': 'irisx/run008-windows-sdk-runtime-v1', 'account': 'danielwuu',
            'versions': self.versions, 'sources': {name: {'bytes': r.ORIGINAL_SOURCES[name][0],
                'sha256': r.ORIGINAL_SOURCES[name][1]} for name in r.NATIVE_SOURCES}}
        native = write(self.root / 'original-native.json', self.native)
        self.local = {'format': 'irisx/run008-windows-bridge-operator-config-v1',
            'state_root': str(self.state), 'username': 'danielwuu', 'versions': self.versions,
            'publication_manifest_sha256': 'f' * 64,
            'windows_bridge': {'configuration': {'wsl_path': native['path'],
                'native_path': r'C:\Synthetic\original-native.json', 'sha256': native['sha256']}},
            'remote_predecessor': {'code_version': 20, 'notebook_version': 39,
                'notebook_source_sha256': r.sha(self.source.encode()), 'provider_status': 'ERROR',
                'snapshot_sha256': 'a' * 64}}
        local = write(self.root / 'original-local.json', self.local)
        self.preimages = []
        # Exact observed original structure: 17 closed-session events, 4 failed
        # open events, and four ancillary events without a session binding.
        # These are synthetic values, never reconstructed authentic bytes.
        self._session(self.closed_nonce, ['open', 'dataset', 'dataset', 'kernel', 'status', 'kernel', 'close'], local, native)
        self._session(self.failed_nonce, ['open'], local, native, unknown=True)
        auxiliary = []
        for label, value in [('bracket-v39-before', self.metadata), ('bracket-v39-after', self.metadata),
                             ('bracket-v39-status', {'status': 'ERROR', 'failure_message': ''}),
                             ('failure', {'action': 'synthetic failed open', 'classification': 'TRANSIENT',
                               'http_status': None, 'message': 'synthetic', 'retry_after_seconds': None,
                               'sprint_stop': False, 'time_epoch': self.now})]:
            self.c.count += 1
            name = f'events/{self.c.count}-{label}-1234abcd.json'
            write(self.state / name, value)
            auxiliary.append(name)
        self.original_bytes = r._scan(self.state)
        inventory = r.inventory_state(self.state)
        self.inventory = write(self.root / 'inventory.json', inventory)
        original_sources = {name: write(self.root / 'original-source' / name, raw)
                            for name, raw in self.original_sources.items()}
        recovery_sources = {}
        for name in r.RECOVERY_SOURCES:
            path = ROOT / name
            raw = path.read_bytes() if path.exists() else b'# synthetic source-only fixture\n'
            recovery_sources[name] = write(self.root / 'recovery-source' / name, raw)
        closed = 'native-bridge-' + self.closed_nonce
        self.review_value = {'format': 'irisx/recovery-source-review-v1', 'original_commit': r.ORIGINAL_COMMIT,
            'state_root': str(self.state), 'inventory_sha256': self.inventory['sha256'],
            'unknown_session': 'native-bridge-' + self.failed_nonce,
            'original_configuration': local, 'original_native_configuration': native,
            'original_sources': original_sources, 'recovery_sources': recovery_sources,
            'request_preimages': self.preimages, 'auxiliary_records': auxiliary,
            'closed_sessions': [{'session': closed, 'claim_sha256': r.sha(self.original_bytes[closed + '.claim.json']),
                'journal_sha256': r.sha(self.original_bytes[closed + '-journal.json'])}],
            'boot_source_sha256': {name: recovery_sources[name]['sha256'] for name in ('recovery_boot_probe.py', 'win_runtime.py')},
            'boot_runtime_sha256': {'python': 'a' * 64, 'base_python': 'b' * 64},
            'restart_authority': {'kind': 'reviewed-manual-start-menu-restart',
                'authorization_sha256': 'c' * 64, 'witness_review_sha256': 'd' * 64}}
        self.review = write(self.root / 'review.json', self.review_value)
        self.before_value = self.boot(self.now - 2, self.now - 10000)
        self.before = write(self.root / 'before.json', self.before_value)
        self.calls = [{'operation': operation, 'arguments': {}} for operation in
                      ['dataset', 'kernel', 'status', 'kernel', 'dataset']]

    def boot(self, observed, boot):
        return {'format': 'irisx/windows-recovery-boot-observation-v1', 'ok': True,
            'challenge': self.challenge, 'host_install_sha256': '9' * 64,
            'observed_utc': utc(observed), 'last_boot_utc': utc(boot),
            'tick_count64_ms': round((observed - boot) * 1000), 'windows_version': '10.0.26100',
            'windows_build': '26100', 'source_sha256': self.review_value['boot_source_sha256'],
            'runtime_sha256': self.review_value['boot_runtime_sha256'],
            'native_process_closure_verified': True, 'closure': self.closure(),
            'auth_started': False, 'credential_contents_accessed': False, 'provider_calls': 0, 'network_used': False}

    def closure(self):
        return {'format': 'irisx/windows-job-closure-v1', 'active_processes': 0, 'kill_on_close': True,
                'breakaway_permitted': False, 'atomic_job_assignment': True}

    def _session(self, nonce, operations, local, native, unknown=False, recovery=None):
        name = 'native-bridge-' + nonce
        claim = {'format': 'irisx/windows-bridge-session-claim-v1', 'nonce': nonce,
            'account': 'danielwuu', 'versions': self.versions, 'configuration_sha256': local['sha256'],
            'bridge_configuration_sha256': native['sha256'], 'publication_manifest_sha256': 'f' * 64,
            'deadline_epoch': self.now + (1000 if recovery else 43200), 'max_seconds': 43200.0,
            'synthetic_test_only': False}
        if recovery:
            claim['recovery'] = recovery
        claim_descriptor = self.c.claim(name, claim)
        proof = {'format': 'irisx/windows-bridge-session-journal-v1', 'nonce': nonce,
            'claim_sha256': claim_descriptor['sha256'], 'stage': 'launch_intent',
            'synthetic_test_only': False, 'native_process_closure_verified': False, 'mutation_attempted': False}
        self.c.journal(name, proof)
        for sequence, operation in enumerate(operations, 1):
            arguments = {key: value for key, value in claim.items() if key not in ('format', 'nonce', 'synthetic_test_only')} if operation == 'open' else {}
            self.preimages.append({'session': name, 'sequence': sequence, 'arguments': arguments, 'max_seconds': 120})
            deadline = self.now + 120
            proof.update(stage='operation_intent', operation=operation, sequence=sequence,
                deadline_epoch=deadline, request_sha256=request_hash(operation, arguments, deadline))
            self.c.journal(name, proof)
            if unknown:
                proof.update(stage='UNKNOWN', unknown_reason='BRIDGE_OPERATION_UNKNOWN')
                self.c.journal(name, proof)
                self.c.journal(name, proof)
                return
            if recovery and self.inject_refresh and sequence == 1:
                self._refresh(nonce, sequence, proof['request_sha256'])
            proof['stage'] = 'operation_accepted'
            self.c.journal(name, proof)
            if operation == 'open':
                proof['stage'] = 'authenticated'
                self.c.journal(name, proof)
        proof.update(stage='closed', native_process_closure_verified=True)
        self.c.journal(name, proof)

    def _refresh(self, nonce, sequence, request_sha256):
        metadata = {'account': 'danielwuu', 'old_expiration_epoch': self.now - 1}
        refresh_id = r.sha(r.canonical(metadata))
        name = 'native-auth-refresh-' + refresh_id[:24]
        claim = self.c.claim(name, {**metadata, 'existing_grant_only': True, 'time_epoch': self.now + 100,
            'bridge_nonce': nonce, 'refresh_id': refresh_id, 'synthetic_test_only': False})
        intent = {'stage': 'refresh_intent', 'claim_sha256': claim['sha256'],
            'old_expiration_epoch': metadata['old_expiration_epoch'], 'attempts': 1, 'refresh_id': refresh_id,
            'bridge_nonce': nonce, 'sequence': sequence, 'request_sha256': request_sha256}
        self.c.journal(name, intent)
        self.c.journal(name, {**intent, 'stage': 'refresh_accepted', 'new_expiration_epoch': self.now + 10000,
            'official_save_completed': True, 'credential_acl_verified': True, 'new_grant_created': False,
            'time_epoch': self.now + 101})

    def prepare(self, owner):
        return owner.prepare(self.inventory, self.review, self.before, challenge=self.challenge,
                             now_epoch=self.now, expires_epoch=self.now + 1000)

    def reseal_fixture_inventory(self):
        """Adversarial synthetic review; never relabel original production bytes."""
        self.inventory = write(self.root / 'inventory.json', r.inventory_state(self.state))
        self.review_value['inventory_sha256'] = self.inventory['sha256']
        self.review = write(self.root / 'review.json', self.review_value)

    def after(self, preparation):
        after = write(self.root / 'after.json', self.boot(self.now + 100, self.now + 50))
        restart = write(self.root / 'restart.json', {'format': 'irisx/trusted-host-controlled-restart-v1',
            'preparation_sha256': preparation['sha256'], 'challenge': self.challenge,
            'host_install_sha256': '9' * 64, 'before_observation_sha256': self.before['sha256'],
            'action': 'Restart', 'requested_utc': utc(self.now + 20),
            'authority_sha256': r.sha(r.canonical(self.review_value['restart_authority']))})
        expected_remote = write(self.root / 'expected-remote.json', {'format': 'irisx/recovery-expected-remote-v1',
            'dataset': self.dataset, 'kernel_metadata': self.metadata,
            'notebook_source_sha256': r.sha(self.source.encode()), 'provider_status': 'ERROR'})
        binding = write(self.root / 'binding-review.json', {'format': 'irisx/recovery-binding-review-v1',
            'state_root': str(self.state), 'preparation_sha256': preparation['sha256'],
            'local_configuration_template': self.review_value['original_configuration'],
            'native_configuration_template': self.review_value['original_native_configuration'],
            'output_local_configuration_path': str(self.root / 'recovery-local.json'),
            'output_native_configuration_path': str(self.root / 'recovery-native.json'),
            'expected_remote_metadata': expected_remote})
        return after, restart, binding

    def reserve(self, owner):
        preparation = self.prepare(owner)
        after, restart, binding = self.after(preparation)
        capability = owner.capability(preparation, after, restart, binding_review_descriptor=binding,
                                      calls=self.calls, now_epoch=self.now + 100)
        reservation = owner.reserve(capability, session_nonce=self.new_nonce,
                                    current_boot_descriptor=after, now_epoch=self.now + 100)
        return preparation, after, restart, binding, capability, reservation

    def finish(self, owner):
        preparation, after, restart, binding, capability, reservation = self.reserve(owner)
        context = owner.admit_session(reservation, current_boot_descriptor=after, now_epoch=self.now + 100)
        native = copy.deepcopy(self.native)
        native['format'] = 'irisx/run008-windows-sdk-recovery-runtime-v1'
        native['recovery'] = context['native_recovery']
        source = self.review_value['recovery_sources']['recovery_boot_probe.py']
        native['sources']['recovery_boot_probe.py'] = {key: source[key] for key in ('bytes', 'sha256')}
        native_descriptor = write(self.root / 'recovery-native.json', native)
        local = copy.deepcopy(self.local)
        local['windows_bridge']['configuration'] = {'wsl_path': native_descriptor['path'],
            'native_path': r'C:\Synthetic\recovery-native.json', 'sha256': native_descriptor['sha256']}
        local_descriptor = write(self.root / 'recovery-local.json', local)
        r.verify_generated_binding(reservation, native, local)
        self.c.config.document_sha256 = local_descriptor['sha256']
        self._session(self.new_nonce, ['open', *context['calls'], 'close'], local_descriptor, native_descriptor,
                      recovery={key: context['native_recovery'][key] for key in ('capability_sha256', 'reservation_sha256')})
        receipt = r.canonical({'format': 'irisx/windows-supervisor-result-v1', 'nonce': self.new_nonce,
            'ok': True, 'reason': 'worker_exit', 'closure': self.closure()})
        observations = {'dataset_before': self.dataset, 'kernel_before': {'metadata': self.metadata, 'blob': {'source': self.source}},
            'status': {'status': 'ERROR', 'failureMessage': ''},
            'kernel_after': {'metadata': self.metadata, 'blob': {'source': self.source}}, 'dataset_after': self.dataset}
        eligibility = owner.finalize(reservation, session_name='native-bridge-' + self.new_nonce,
            receipt_bytes=receipt, proxy_exit_status=0, observations=observations, now_epoch=self.now + 110)
        return preparation, after, reservation, context, eligibility

    def test_complete_restart_reserve_reconcile_preserves_original_bytes(self):
        self.assertEqual(len(self.original_bytes), 29)
        with r.RecoveryOwner(self.c.mapping) as owner:
            _, after, _, context, eligibility = self.finish(owner)
        self.c.config.document_sha256 = self.review_value['original_configuration']['sha256']
        allowed = r.validate_eligibility(self.c.mapping, self.c.config, context['covered_pending_claims'],
                                        current_boot_descriptor=after, now_epoch=self.now + 110)
        self.assertEqual(set(allowed), {'native-bridge-' + self.failed_nonce})
        for name, raw in self.original_bytes.items():
            self.assertEqual((self.state / name).read_bytes(), raw)
        self.assertEqual(r._document(eligibility)['original_authentication_outcome'], 'UNKNOWN')

    def test_successful_same_session_existing_grant_refresh_is_bound_and_preserved(self):
        self.inject_refresh = True
        with r.RecoveryOwner(self.c.mapping) as owner:
            _, after, _, context, _ = self.finish(owner)
        self.c.config.document_sha256 = self.review_value['original_configuration']['sha256']
        r.validate_eligibility(self.c.mapping, self.c.config, context['covered_pending_claims'],
                               current_boot_descriptor=after, now_epoch=self.now + 110)
        refresh = next(self.state.glob('native-auth-refresh-*-journal.json'))
        original = refresh.read_bytes()
        changed = r.strict_json(original)
        changed['stage'] = 'refresh_unknown'
        refresh.write_bytes(r.canonical(changed))
        with self.assertRaises(r.RecoveryError):
            r.validate_eligibility(self.c.mapping, self.c.config, context['covered_pending_claims'],
                                   current_boot_descriptor=after, now_epoch=self.now + 110)

    def test_future_event_growth_does_not_reopen_or_reblock_completed_disposition(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            _, after, _, context, _ = self.finish(owner)
        for i in range(600):
            write(self.state / 'events' / f'{20000+i}-ordinary-watch-1234abcd.json', {'observation': i})
        self.c.config.document_sha256 = self.review_value['original_configuration']['sha256']
        with mock.patch.object(r, '_scan', side_effect=AssertionError('must not scan later event history')):
            r.validate_eligibility(self.c.mapping, self.c.config, context['covered_pending_claims'],
                                   current_boot_descriptor=after, now_epoch=self.now + 110)

    def test_uncertain_completion_without_final_seal_does_not_admit(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            _, after, _, context, _ = self.finish(owner)
        next(self.state.glob('recovery-epoch-*-sealed.claim.json')).unlink()
        self.c.config.document_sha256 = self.review_value['original_configuration']['sha256']
        with self.assertRaisesRegex(r.RecoveryError, 'seal_required'):
            r.validate_eligibility(self.c.mapping, self.c.config, context['covered_pending_claims'],
                                   current_boot_descriptor=after, now_epoch=self.now + 110)

    def test_no_mutating_method_without_owned_external_lock(self):
        with self.assertRaisesRegex(r.RecoveryError, 'lock_required'):
            self.prepare(r.RecoveryOwner(self.c.mapping))

    def test_second_owner_cannot_acquire_publisher_lock(self):
        with r.RecoveryOwner(self.c.mapping):
            with self.assertRaises(BlockingIOError):
                with r.RecoveryOwner(self.c.mapping):
                    self.fail('second owner acquired lock')

    def test_closed_original_session_no_raw_receipt_required(self):
        frontier = r.validate_frontier(self.state, self.inventory, self.review)
        self.assertEqual([row['stage'] for row in frontier['sessions']], ['UNKNOWN', 'closed'])

    def test_missing_mandatory_authenticated_event_is_not_a_complete_source_trace(self):
        name = 'native-bridge-' + self.closed_nonce
        for _, path, raw in r._event_rows(r._scan(self.state), name):
            if r.strict_json(raw)['stage'] == 'authenticated':
                (self.state / path).unlink()
        self.reseal_fixture_inventory()
        with self.assertRaises(r.RecoveryError):
            r.validate_frontier(self.state, self.inventory, self.review)

    def test_repeated_unknown_cannot_change_reason_after_failure_latch(self):
        name = 'native-bridge-' + self.failed_nonce
        rows = r._event_rows(r._scan(self.state), name)
        altered = r.strict_json(rows[-1][2])
        altered['unknown_reason'] = 'BRIDGE_OPEN_UNKNOWN'
        write(self.state / rows[-1][1], altered)
        write(self.state / (name + '-journal.json'), altered)
        self.reseal_fixture_inventory()
        with self.assertRaises(r.RecoveryError):
            r.validate_frontier(self.state, self.inventory, self.review)

    def test_refresh_presence_rejected_even_after_fixture_inventory_reseal(self):
        write(self.state / ('native-auth-refresh-' + 'a' * 24 + '.claim.json'), {'stage': 'refresh_intent'})
        self.reseal_fixture_inventory()
        with self.assertRaisesRegex(r.RecoveryError, 'refresh_record'):
            r.validate_frontier(self.state, self.inventory, self.review)

    def test_nonmonotone_sequence_and_changed_request_hash_rejected_after_reseal(self):
        name = 'native-bridge-' + self.failed_nonce
        rows = r._event_rows(r._scan(self.state), name)
        for _, path, raw in rows:
            value = r.strict_json(raw)
            if 'sequence' in value:
                value['sequence'] = 2
                write(self.state / path, value)
        write(self.state / (name + '-journal.json'), r.strict_json((self.state / rows[-1][1]).read_bytes()))
        self.reseal_fixture_inventory()
        with self.assertRaisesRegex(r.RecoveryError, 'monotone_sequence'):
            r.validate_frontier(self.state, self.inventory, self.review)

    def test_uncovered_original_unknown_is_rejected_after_reseal(self):
        name = 'native-bridge-' + self.closed_nonce
        journal = r.strict_json((self.state / (name + '-journal.json')).read_bytes())
        journal['stage'] = 'UNKNOWN'
        journal['native_process_closure_verified'] = False
        journal['unknown_reason'] = 'BRIDGE_OPERATION_UNKNOWN'
        self.c.journal(name, journal)
        self.review_value['closed_sessions'][0]['journal_sha256'] = r.sha(r.canonical(journal))
        self.reseal_fixture_inventory()
        with self.assertRaises(r.RecoveryError):
            r.validate_frontier(self.state, self.inventory, self.review)

    def test_callback_cannot_rewrite_original_files(self):
        original_claim = self.c.claim
        name, raw = next(iter(self.original_bytes.items()))
        def corrupting_claim(label, value):
            result = original_claim(label, value)
            (self.state / name).write_bytes(raw + b' ')
            return result
        self.c.mapping['claim'] = corrupting_claim
        with r.RecoveryOwner(self.c.mapping) as owner:
            with self.assertRaisesRegex(r.RecoveryError, 'append_only'):
                self.prepare(owner)
            with self.assertRaisesRegex(r.RecoveryError, 'lock_required'):
                self.prepare(owner)

    def test_wrong_original_source_pin_rejected(self):
        changed = copy.deepcopy(self.review_value)
        changed['original_sources']['native_auth.py']['sha256'] = '0' * 64
        review = write(self.root / 'changed-review.json', changed)
        with self.assertRaisesRegex(r.RecoveryError, 'not_known01ca'):
            r.validate_frontier(self.state, self.inventory, review)

    def test_self_consistent_substituted_recovery_source_is_not_executing_source(self):
        changed = copy.deepcopy(self.review_value)
        path = Path(changed['recovery_sources']['protocol.py']['path'])
        changed['recovery_sources']['protocol.py'] = write(path, path.read_bytes() + b'\n# synthetic substitution\n')
        review = write(self.root / 'substituted-review.json', changed)
        with self.assertRaisesRegex(r.RecoveryError, 'executing_source_closure_changed'):
            r.validate_frontier(self.state, self.inventory, review)

    def test_pure_module_cannot_compile_caller_selected_substitute(self):
        source = self.root / 'substituted-protocol.py'
        row = write(source, b'raise AssertionError("synthetic code must not execute")\n')
        with self.assertRaisesRegex(r.RecoveryError, 'pure_module_executing_source_changed'):
            r._reviewed_module(row, 'protocol')

    def test_missing_extra_mutated_and_temporary_frontiers_rejected(self):
        with self.subTest('extra'):
            extra = self.state / 'extra.json'
            write(extra, {'stage': 'refresh_intent'})
            with self.assertRaises(r.RecoveryError):
                r.validate_frontier(self.state, self.inventory, self.review)
            extra.unlink()
        name, raw = next(iter(self.original_bytes.items()))
        target = self.state / name
        target.unlink()
        with self.assertRaises(r.RecoveryError):
            r.validate_frontier(self.state, self.inventory, self.review)
        target.write_bytes(raw + b' ')
        with self.assertRaises(r.RecoveryError):
            r.validate_frontier(self.state, self.inventory, self.review)
        target.write_bytes(raw)
        (self.state / 'torn.json.tmp').write_bytes(b'{}')
        with self.assertRaises(r.RecoveryError):
            r.inventory_state(self.state)

    def test_special_files_symlink_hardlink_fifo_rejected(self):
        path = self.state / 'special.json'
        other = write(self.root / 'other.json', {})
        for kind in ('symlink', 'hardlink', 'fifo'):
            with self.subTest(kind=kind):
                if kind == 'symlink':
                    path.symlink_to(other['path'])
                elif kind == 'hardlink':
                    os.link(other['path'], path)
                else:
                    os.mkfifo(path)
                try:
                    with self.assertRaises(r.RecoveryError):
                        r.inventory_state(self.state)
                finally:
                    path.unlink()

    def test_duplicate_nonfinite_complex_json_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}',
                    b'{"x":' + b'[' * 40 + b'0' + b']' * 40 + b'}'):
            with self.subTest(raw=raw[:30]), self.assertRaises(r.RecoveryError):
                r.strict_json(raw)

    def test_directory_symlink_rejected(self):
        (self.root / 'alias').symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(r.RecoveryError):
            r.inventory_state(self.root / 'alias')

    def test_ancestor_sibling_churn_between_stat_and_open_is_allowed(self):
        ancestor = self.root / 'traversed'
        path = ancestor / 'nested' / 'record.json'
        expected = write(path, {'x': 1})
        original_open = os.open
        changed = False

        def churn(name, *args, **kwargs):
            nonlocal changed
            if name == ancestor.name and not changed:
                changed = True
                # Deterministically changes ancestor link count and metadata.
                (ancestor / 'unrelated-sibling').mkdir()
            return original_open(name, *args, **kwargs)

        with mock.patch.object(r.os, 'open', churn):
            self.assertEqual(r.descriptor(path), expected)
        self.assertTrue(changed)

    def test_directory_replacement_before_open_and_after_read_is_rejected(self):
        for phase in ('before_open', 'after_read'):
            with self.subTest(phase=phase):
                ancestor = self.root / phase
                path = ancestor / 'record.json'
                write(path, {'x': 1})
                original_open = os.open
                changed = False
                opened = []

                def replace():
                    nonlocal changed
                    changed = True
                    ancestor.rename(self.root / (phase + '-displaced'))
                    ancestor.mkdir()
                    path.write_bytes(b'{"x":1}\n')

                def replaced(name, *args, **kwargs):
                    if name == ancestor.name and not changed:
                        replace()
                    fd = original_open(name, *args, **kwargs)
                    if name == ancestor.name:
                        opened.append(fd)
                    return fd

                if phase == 'before_open':
                    with mock.patch.object(r.os, 'open', replaced):
                        with self.assertRaisesRegex(r.RecoveryError, 'recovery_directory_race'):
                            r.bounded_read(path)
                    self.assertEqual(len(opened), 1)
                    with self.assertRaises(OSError):
                        os.fstat(opened[0])
                else:
                    with self.assertRaisesRegex(r.RecoveryError, 'recovery_directory_replaced'):
                        with r._directory(ancestor) as fd:
                            self.assertEqual(r._read_at(fd, path.name, r.FILE_CAP), r.canonical({'x': 1}))
                            replace()
                    with self.assertRaises(OSError):
                        os.fstat(fd)
                self.assertTrue(changed)

    def test_file_replaced_during_read_rejected(self):
        path = self.root / 'race.json'
        write(path, {'x': 1})
        original = os.stat
        count = 0
        def raced(name, *args, **kwargs):
            nonlocal count
            if name == path.name:
                count += 1
                if count == 2:
                    write(self.root / 'replacement.json', {'x': 2})
                    os.replace(self.root / 'replacement.json', path)
            return original(name, *args, **kwargs)
        with mock.patch.object(r.os, 'stat', raced), self.assertRaises(r.RecoveryError):
            r.bounded_read(path)

    def test_wrong_host_same_boot_clock_snapshot_and_replayed_boot_rejected(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            preparation = self.prepare(owner)
            after, restart, _ = self.after(preparation)
            original = r._document(after)
            for field, value in [('host_install_sha256', '8' * 64), ('last_boot_utc', self.before_value['last_boot_utc']),
                                  ('observed_utc', utc(self.now - 10)), ('tick_count64_ms', 999999999),
                                  ('challenge', '7' * 64)]:
                changed = copy.deepcopy(original)
                changed[field] = value
                row = write(self.root / 'bad-boot.json', changed)
                with self.subTest(field=field), self.assertRaises(r.RecoveryError):
                    r.validate_restart(preparation, row, restart, now_epoch=self.now + 100)
            with self.assertRaises(r.RecoveryError):
                r.validate_restart(preparation, self.before, restart, now_epoch=self.now + 100)

    def test_missing_windows_events_does_not_invalidate_restart(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            preparation = self.prepare(owner)
            after, restart, _ = self.after(preparation)
            result = r.validate_restart(preparation, after, restart, now_epoch=self.now + 100)
            self.assertEqual(result['last_boot_utc'], utc(self.now + 50))

    def test_declaration_without_controlled_restart_provenance_rejected(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            preparation = self.prepare(owner)
            after, restart, _ = self.after(preparation)
            value = r._document(restart)
            value['action'] = 'sleep'
            bad = write(self.root / 'manual-declaration.json', value)
            with self.assertRaises(r.RecoveryError):
                r.validate_restart(preparation, after, bad, now_epoch=self.now + 100)

    def test_one_capability_one_launch_and_no_reissue_from_new_owner(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            _, after, _, _, capability, reservation = self.reserve(owner)
            owner.admit_session(reservation, current_boot_descriptor=after, now_epoch=self.now + 100)
            with self.assertRaisesRegex(r.RecoveryError, 'reused'):
                owner.admit_session(reservation, current_boot_descriptor=after, now_epoch=self.now + 100)
            with self.assertRaises(r.RecoveryError):
                owner.reserve(capability, session_nonce='4' * 64, current_boot_descriptor=after, now_epoch=self.now + 100)
        with r.RecoveryOwner(self.c.mapping) as other:
            with self.assertRaisesRegex(r.RecoveryError, 'not_live'):
                other.admit_session(reservation, current_boot_descriptor=after, now_epoch=self.now + 100)

    def test_crash_consumes_claim_before_journal_or_launch(self):
        for fault in ('after_claim', 'after_event', 'after_temp'):
            with self.subTest(fault=fault):
                # Independent fixtures keep each simulated crash permanently.
                self.setUp()
                with r.RecoveryOwner(self.c.mapping) as owner:
                    preparation = self.prepare(owner)
                    after, restart, binding = self.after(preparation)
                    capability = owner.capability(preparation, after, restart, binding_review_descriptor=binding,
                        calls=self.calls, now_epoch=self.now + 100)
                    self.c.fail = fault
                    with self.assertRaises(OSError):
                        owner.reserve(capability, session_nonce=self.new_nonce,
                                      current_boot_descriptor=after, now_epoch=self.now + 100)
                    self.assertTrue((self.state / (r._prefix(r._document(preparation)) + '-capability.claim.json')).is_file())
                    self.assertFalse(any('-launch.claim.json' in name for name in self.c.writes))
                    with self.assertRaises(r.RecoveryError):
                        owner.reserve(capability, session_nonce=self.new_nonce,
                                      current_boot_descriptor=after, now_epoch=self.now + 100)
                self.c.fail = None
                with r.RecoveryOwner(self.c.mapping) as other, self.assertRaises(r.RecoveryError):
                    other.reserve(capability, session_nonce=self.new_nonce,
                                  current_boot_descriptor=after, now_epoch=self.now + 100)

    def test_capability_mutation_expiry_and_source_change_rejected(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            preparation = self.prepare(owner)
            after, restart, binding = self.after(preparation)
            with self.assertRaises(r.RecoveryError):
                owner.capability(preparation, after, restart, binding_review_descriptor=binding,
                    calls=[{'operation': 'save', 'arguments': {}}], now_epoch=self.now + 100)
            capability = owner.capability(preparation, after, restart, binding_review_descriptor=binding,
                                         calls=self.calls, now_epoch=self.now + 100)
            with self.assertRaises(r.RecoveryError):
                owner.reserve(capability, session_nonce=self.new_nonce, current_boot_descriptor=after,
                              now_epoch=self.now + 1001)
            source = Path(self.review_value['recovery_sources']['native_auth.py']['path'])
            source.write_bytes(source.read_bytes() + b'\n')
            with self.assertRaises(r.RecoveryError):
                owner.reserve(capability, session_nonce=self.new_nonce, current_boot_descriptor=after,
                              now_epoch=self.now + 100)

    def test_final_disposition_survives_closed_ordinary_session_and_capability_expiry(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            _, _, _, context, _ = self.finish(owner)
        self._session('4' * 64, ['open', 'dataset', 'close'], self.review_value['original_configuration'],
                      self.review_value['original_native_configuration'])
        self.c.config.document_sha256 = self.review_value['original_configuration']['sha256']
        fresh = write(self.root / 'later.json', self.boot(self.now + 2000, self.now + 50))
        r.validate_eligibility(self.c.mapping, self.c.config, context['covered_pending_claims'],
                               current_boot_descriptor=fresh, now_epoch=self.now + 2000)

    def test_final_disposition_rejects_uncovered_unknown_and_pending_epoch(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            _, after, _, context, _ = self.finish(owner)
        self.c.config.document_sha256 = self.review_value['original_configuration']['sha256']
        write(self.state / ('recovery-epoch-' + '7' * 64 + '.claim.json'), {'stage': 'prepared'})
        with self.assertRaisesRegex(r.RecoveryError, 'outstanding_token'):
            r.validate_eligibility(self.c.mapping, self.c.config, context['covered_pending_claims'],
                                   current_boot_descriptor=after, now_epoch=self.now + 110)

    def test_remote_hashes_are_recomputed_from_actual_bracket_dtos(self):
        with r.RecoveryOwner(self.c.mapping) as owner:
            preparation = self.prepare(owner)
            _, _, binding = self.after(preparation)
            observations = {'dataset_before': self.dataset, 'dataset_after': self.dataset,
                'kernel_before': {'metadata': self.metadata, 'blob': {'source': self.source}},
                'kernel_after': {'metadata': self.metadata, 'blob': {'source': self.source}},
                'status': {'status': 'ERROR', 'failureMessage': ''}}
            value = r.validate_reconciliation(observations, r._document(binding), r._document(preparation))
            self.assertEqual(value['notebook_source_sha256'], r.sha(self.source.encode()))
            observations['kernel_after'] = copy.deepcopy(observations['kernel_after'])
            observations['kernel_after']['blob']['source'] += '# changed'
            with self.assertRaises(r.RecoveryError):
                r.validate_reconciliation(observations, r._document(binding), r._document(preparation))

    def test_closure_wrong_nonce_and_boolean_job_count_rejected(self):
        receipt = {'format': 'irisx/windows-supervisor-result-v1', 'nonce': self.new_nonce,
                   'ok': True, 'reason': 'worker_exit', 'closure': self.closure()}
        with self.assertRaises(r.RecoveryError):
            r.validate_closure(r.canonical(receipt), nonce='4' * 64, exit_status=0)
        receipt['closure']['active_processes'] = False
        with self.assertRaises(r.RecoveryError):
            r.validate_closure(r.canonical(receipt), nonce=self.new_nonce, exit_status=0)


if __name__ == '__main__':
    unittest.main()

"""Offline exact-frontier and real Linux flock tests; no native/provider calls."""
import fcntl
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

from test_owner_integration import load_source

ROOT = Path(__file__).resolve().parents[1]


class PublisherOwnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='offline-readonly-owner-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.common = load_source('test_readonly_frontier_common', ROOT / 'operator_common.py')
        self.common.CONFIG = types.SimpleNamespace(scratch_root=self.root,
            document_sha256='1' * 64, publication_manifest_sha256='2' * 64)

    def test_real_exclusive_owner_is_required_and_expires_with_scope(self):
        with self.assertRaisesRegex(ValueError, 'publisher_lock_not_held'):
            self.common.publisher_lock_owner()
        with self.common.lock():
            owner = self.common.publisher_lock_owner()
            info = os.stat(self.root / 'publisher.lock')
            self.assertEqual(owner['pid'], os.getpid())
            self.assertEqual((owner['device'], owner['inode']), (info.st_dev, info.st_ino))
        self.assertIsNone(self.common._PUBLISHER_OWNER)
        with self.assertRaisesRegex(ValueError, 'publisher_lock_not_held'):
            self.common.publisher_lock_owner()

    def test_unlock_or_shared_lock_cannot_be_advertised_as_owner(self):
        for mode in (fcntl.LOCK_UN, fcntl.LOCK_SH):
            with self.subTest(mode=mode), self.common.lock():
                fcntl.flock(self.common._PUBLISHER_OWNER[0], mode)
                with self.assertRaisesRegex(ValueError, 'publisher_kernel_flock_required'):
                    self.common.publisher_lock_owner()

    def test_path_replacement_cannot_borrow_old_inode_lock(self):
        with self.common.lock():
            path = self.root / 'publisher.lock'
            path.unlink()
            path.touch()
            with self.assertRaisesRegex(ValueError, 'publisher_lock_file_changed'):
                self.common.publisher_lock_owner()

    def test_pid_or_thread_change_rejects_inherited_capability(self):
        for attribute in ('getpid',):
            with self.common.lock(), mock.patch.object(os, attribute, return_value=os.getpid() + 1):
                with self.assertRaisesRegex(ValueError, 'publisher_lock_owner_changed'):
                    self.common.publisher_lock_owner()
        with self.common.lock(), mock.patch.object(self.common.threading, 'get_ident', return_value=-1):
            with self.assertRaisesRegex(ValueError, 'publisher_lock_owner_changed'):
                self.common.publisher_lock_owner()

    def test_closed_file_and_unavailable_kernel_metadata_fail_closed(self):
        with self.common.lock():
            original = self.common._PUBLISHER_OWNER
            with tempfile.TemporaryFile() as other:
                replacement = (other, *original[1:])
            self.common._PUBLISHER_OWNER = replacement
            try:
                with self.assertRaisesRegex(ValueError, 'publisher_lock_owner_changed'):
                    self.common.publisher_lock_owner()
            finally:
                self.common._PUBLISHER_OWNER = original
            with mock.patch.object(self.common, 'open', side_effect=OSError, create=True):
                with self.assertRaisesRegex(ValueError, 'publisher_lock_metadata_unavailable'):
                    self.common.publisher_lock_owner()

    def test_context_exception_releases_actual_lock(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            with self.common.lock():
                raise RuntimeError('synthetic')
        with self.common.lock():
            self.common.publisher_lock_owner()

    def test_frontier_descriptor_requires_admitted_unchanged_review(self):
        with self.assertRaisesRegex(ValueError, 'admitted_action_review_required'):
            self.common.readonly_frontier_descriptor()
        evidence = self.root / 'historical-cut.json'
        evidence.write_bytes(b'{"synthetic":true}')
        frontier = self.common.descriptor(evidence)
        review = {'status': 'PASS', 'local_config_sha256': '1' * 64,
            'publication_manifest_sha256': '2' * 64, 'readonly_frontier': frontier}
        path = self.root / 'review.json'
        path.write_bytes(self.common.canonical(review))
        self.common.ACTION_REVIEW = self.common.descriptor(path)
        self.assertEqual(self.common.readonly_frontier_descriptor(), frontier)
        path.write_bytes(self.common.canonical({**review, 'readonly_frontier': None}))
        with self.assertRaisesRegex(ValueError, 'artifact_hash_or_size'):
            self.common.readonly_frontier_descriptor()



class FrontierTests(unittest.TestCase):
    def setUp(self):
        existing = getattr(self, '_cut_existing_root', None)
        if existing is None:
            temp = tempfile.TemporaryDirectory(prefix='offline-frontier-')
            self.addCleanup(temp.cleanup)
            existing = Path(temp.name)
        self.root = existing
        (self.root / 'events').mkdir(exist_ok=True)
        self.a = getattr(self, '_cut_existing_adapter', None) or load_source(
            'test_exact_readonly_context', ROOT / 'context_continuation.py')
        if getattr(self, '_cut_existing_adapter', None) is not None:
            import copy
            for key in ('READONLY_CLAIM', 'READONLY_JOURNAL', 'READONLY_STATE_SHA256',
                        'READONLY_SID_SHA256', 'READONLY_CALLER', 'READONLY_ARTIFACTS', 'READONLY_RESULT'):
                original = copy.deepcopy(getattr(self.a, key))
                self.addCleanup(setattr, self.a, key, original)
        self.common = load_source('test_frontier_owner', ROOT / 'operator_common.py')
        lock_temp = tempfile.TemporaryDirectory(prefix='offline-frontier-lock-')
        self.addCleanup(lock_temp.cleanup)
        self.common.CONFIG = types.SimpleNamespace(scratch_root=Path(lock_temp.name))
        self.c = {'publisher_lock_owner': self.common.publisher_lock_owner}
        self.prefix = 'native-bridge-' + self.a.READONLY_NONCE
        claim = {'nonce': self.a.READONLY_NONCE, 'synthetic_test_only': False, 'deadline_epoch': 500.0}
        self.claim = self.a._canonical(claim)
        base = {'format': 'irisx/windows-bridge-session-journal-v1', 'nonce': self.a.READONLY_NONCE,
            'claim_sha256': self.a._digest(self.claim), 'synthetic_test_only': False,
            'native_process_closure_verified': False, 'mutation_attempted': False}
        rows = [{**base, 'stage': 'launch_intent'}]
        for sequence in range(1, 98):
            intent = {**base, 'stage': 'operation_intent', 'sequence': sequence,
                'operation': 'open' if sequence == 1 else 'kernel',
                'request_sha256': f'{sequence:064x}', 'deadline_epoch': 100.0 + sequence}
            accepted = {**intent, 'stage': 'operation_accepted'}
            rows += [intent, accepted]
            if sequence == 1:
                rows += [{**accepted, 'stage': 'authenticated'}]
        self.events = {}
        for index, value in enumerate(rows):
            name = f'events/{1000 + index}-{self.prefix}-00000000.json'
            raw = self.a._canonical(value)
            (self.root / name).write_bytes(raw)
            self.events[name] = raw
        self.journal = self.a._canonical(rows[-1])
        self.a.READONLY_CLAIM = (len(self.claim), self.a._digest(self.claim))
        self.a.READONLY_JOURNAL = (len(self.journal), self.a._digest(self.journal))
        self.baseline = {self.prefix + '.claim.json': self.claim,
            self.prefix + '-journal.json': self.journal}
        for name, raw in self.baseline.items():
            (self.root / name).write_bytes(raw)
        self.guard = self.a._readonly_guard(self.c, self.root, self.baseline, self.events, {}, [])

    def write(self, name, value):
        raw = self.a._canonical(value)
        (self.root / name).write_bytes(raw)
        return raw

    def own_pair(self, nonce='a' * 64, stage='operation_intent'):
        prefix = 'native-bridge-' + nonce
        raw = self.write(prefix + '.claim.json', {'nonce': nonce, 'synthetic_test_only': False})
        self.write(prefix + '-journal.json', {'nonce': nonce, 'stage': stage,
            'claim_sha256': self.a._digest(raw), 'synthetic_test_only': False,
            'native_process_closure_verified': False})
        return nonce

    def test_full_196_history_and_final_pair_are_required_without_duration_preimage(self):
        self.a._readonly_history(self.claim, self.journal, self.events)
        for stage in ('UNKNOWN', 'operation_accepted', 'closed'):
            changed = dict(self.events)
            key = sorted(changed)[90]
            row = self.a._json(changed[key]); row['stage'] = stage
            changed[key] = self.a._canonical(row)
            with self.assertRaises(ValueError):
                self.a._readonly_history(self.claim, self.journal, changed)

    def test_mutation_or_unpaired_request_hash_rejects(self):
        for key, value in (('operation', 'version'), ('mutation_attempted', True),
                           ('request_sha256', 'f' * 64)):
            changed = dict(self.events)
            name = sorted(changed)[90]
            row = self.a._json(changed[name]); row[key] = value
            changed[name] = self.a._canonical(row)
            with self.assertRaises(ValueError):
                self.a._readonly_history(self.claim, self.journal, changed)

    def test_real_owner_and_unchanged_frontier_required(self):
        with self.assertRaisesRegex(ValueError, 'publisher_lock_not_held'):
            self.guard()
        with self.common.lock():
            self.guard()
            path = self.root / sorted(self.events)[20]
            before = path.stat()
            data = path.read_bytes().replace(b'kernel', b'status')
            path.write_bytes(data)
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, 'context_readonly_event_changed'):
                self.guard()

    def test_new_old_event_and_late_close_reject(self):
        with self.common.lock():
            self.write(f'events/9999-{self.prefix}-11111111.json', {'stage': 'UNKNOWN'})
            with self.assertRaisesRegex(ValueError, 'context_readonly_event_frontier'):
                self.guard()
        (self.root / f'events/9999-{self.prefix}-11111111.json').unlink()
        with self.common.lock():
            self.write(self.prefix + '-journal.json', {'stage': 'closed'})
            with self.assertRaisesRegex(ValueError, 'context_readonly_old_root_changed'):
                self.guard()

    def test_only_own_live_pair_can_evolve_and_other_unknown_rejects(self):
        with self.common.lock():
            nonce = self.own_pair()
            self.guard(nonce)
            self.own_pair(nonce, stage='operation_accepted')
            self.guard(nonce)
            self.own_pair(nonce, stage='UNKNOWN')
            with self.assertRaisesRegex(ValueError, 'context_readonly_successor_binding'):
                self.guard(nonce)
            self.own_pair(nonce, stage='operation_accepted')
            self.own_pair('b' * 64, stage='UNKNOWN')
            with self.assertRaisesRegex(ValueError, 'context_readonly_new_root'):
                self.guard(nonce)

    def test_only_own_acknowledged_refresh_may_be_added(self):
        nonce = self.own_pair()
        name = 'native-auth-refresh-' + 'c' * 24
        raw = self.write(name + '.claim.json', {'bridge_nonce': nonce, 'synthetic_test_only': False, 'existing_grant_only': True})
        accepted = {'bridge_nonce': nonce, 'claim_sha256': self.a._digest(raw),
                    'stage': 'refresh_accepted', 'new_grant_created': False}
        with self.common.lock():
            for stage in ('refresh_intent', 'UNKNOWN'):
                self.write(name + '-journal.json', {**accepted, 'stage': stage})
                with self.assertRaisesRegex(ValueError, 'context_readonly_new_refresh_unknown'):
                    self.guard(nonce)
            self.write(name + '-journal.json', accepted)
            self.guard(nonce)
            self.write(name + '-journal.json', {**accepted, 'bridge_nonce': 'd' * 64})
            with self.assertRaisesRegex(ValueError, 'context_readonly_new_refresh_unknown'):
                self.guard(nonce)

    def test_added_closed_sessions_are_permitted_by_next_admission_baseline(self):
        nonce = self.own_pair(stage='closed')
        # A new validate_context separately runs the unchanged frozen closed
        # predicate before delivering this new baseline's runtime guard.
        baseline = self.a._native_roots(self.root)
        guard = self.a._readonly_guard(self.c, self.root, baseline, self.events, {}, [])
        with self.common.lock():
            guard()
            self.own_pair('b' * 64)
            guard('b' * 64)
            self.write('native-bridge-' + nonce + '-journal.json', {'stage': 'UNKNOWN'})
            with self.assertRaisesRegex(ValueError, 'context_readonly_old_root_changed'):
                guard('b' * 64)

    def test_empty_stderr_is_rechecked_and_general_empty_descriptor_stays_forbidden(self):
        path = self.root / 'stderr.raw'; path.touch()
        row = {'path': str(path), 'bytes': 0, 'sha256': self.a._digest(b'')}
        self.assertEqual(self.a._readonly_verified(row), b'')
        with self.assertRaisesRegex(ValueError, 'context_descriptor_bounds'):
            self.a._verified(row)
        guard = self.a._readonly_guard(self.c, self.root, self.baseline, self.events, {}, [(row, b'')])
        with self.common.lock():
            guard()
            path.write_bytes(b'error')
            with self.assertRaisesRegex(ValueError, 'context_presence_stderr_not_empty'):
                guard()


class BridgeGuardTests(unittest.TestCase):
    def setUp(self):
        import test_bridge_client as b
        self.b = b
        temp = tempfile.TemporaryDirectory(prefix='offline-frontier-bridge-')
        self.addCleanup(temp.cleanup)
        self.common = b.Common(Path(temp.name))
        self.servers = []

    def create(self, guard, **options):
        b = self.b
        def factory(*args):
            server = b.SyntheticServer(self.common, *args, **options)
            self.servers.append(server)
            return server
        def install(client):
            client._receive_readonly_guard(guard)
        with mock.patch.object(b.client_module.BridgeClient, '_pending_sessions', install):
            return b.client_module.BridgeClient.for_testing(self.common.mapping, b.binding(), factory)

    def test_before_claim_open_ready_and_refresh_intent(self):
        states = []
        def guard(nonce, refresh=None):
            states.append([value['stage'] for _, value in self.common.writes if 'stage' in value])
        client = self.create(guard, refresh=True)
        self.assertEqual(len(states), 7)
        self.assertEqual(states[0], [])
        self.assertNotIn('refresh_intent', states[4])
        self.assertIn('refresh_intent', states[5])
        self.assertIn('refresh_accepted', states[6])
        self.assertEqual(len(self.servers[0].acks), 2)
        client.close()

    def test_blocked_ready_or_refresh_cannot_send_auth_ack_or_claim(self):
        for failure_at in (4, 5, 6, 7):
            with self.subTest(failure_at=failure_at):
                # Use a fresh namespace for each synthetic constructor.
                self.setUp()
                count = 0
                def guard(nonce, refresh=None):
                    nonlocal count
                    count += 1
                    if count == failure_at:
                        raise ValueError('synthetic_frontier_changed')
                with self.assertRaisesRegex(ValueError, 'synthetic_frontier_changed'):
                    self.create(guard, refresh=True)
                if failure_at <= 5:
                    self.assertFalse(list(self.common.root.glob('native-auth-refresh-*')))
                self.assertEqual(len(self.servers[0].acks), 1 if failure_at == 7 else 0)

    def test_all_business_operations_are_guarded_but_cleanup_close_is_not(self):
        client = self.create(lambda nonce: None)
        client.readonly_frontier_guard = mock.Mock(side_effect=ValueError('synthetic_owner_released'))
        with mock.patch.object(client.protocol, 'validate_request'), mock.patch.object(client, '_check_versions'):
            for operation in client.protocol.OPERATION_TIMEOUTS:
                if operation == 'close':
                    continue
                with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'synthetic_owner_released'):
                    client._command(operation, {})
        self.assertEqual(len(self.servers[0].requests), 1)
        client.close()
        self.assertTrue(client.closed)
        self.assertTrue(client.closure_verified)
        self.assertEqual(len(self.servers[0].requests), 2)


class CompleteCutTests(unittest.TestCase):
    """Synthetic hash pins are replaced only in this offline module instance."""
    write = FrontierTests.write
    own_pair = FrontierTests.own_pair

    def setUp(self):
        FrontierTests.setUp(self)
        a = self.a
        self.a.READONLY_STATE_SHA256 = a._digest(str(self.root).encode())
        self.a.READONLY_SID_SHA256 = a._digest(b'synthetic-sid')
        evidence_temp = tempfile.TemporaryDirectory(prefix='offline-cut-evidence-')
        self.addCleanup(evidence_temp.cleanup)
        out = Path(evidence_temp.name) / 'private-cut'; out.mkdir()
        self.out = out
        self.caller = {}
        work = out / 'owner-0001'; work.mkdir()
        for key, path in {'jit': out / 'jit_original_sequence.py', 'owner': out / 'owner.py',
                          'seq14': work / '0014.json', 'owner_start': work / 'OWNER-START.json'}.items():
            raw = a._canonical({'offline_synthetic': key})
            path.write_bytes(raw)
            self.caller[key] = {'path': str(path), **a._metadata(raw)}
            a.READONLY_CALLER[key] = (len(raw), a._digest(raw))
        self.c['readonly_caller_descriptors'] = lambda: self.caller
        self.c['readonly_frontier_descriptor'] = lambda: self.result_row
        self.pending = [{'claim': {'path': str(self.root / (self.prefix + '.claim.json')), **a._metadata(self.claim)},
                         'journal': {'path': str(self.root / (self.prefix + '-journal.json')), **a._metadata(self.journal)}}]
        native_raw = a._canonical({'identity': {'sid': 'synthetic-sid'}})
        native = out / 'native-config.json'; native.write_bytes(native_raw)
        self.actual = {'windows_bridge': {'configuration': {'wsl_path': str(native), 'sha256': a._digest(native_raw)}}}
        files = {name: a._metadata(raw) for name, raw in {**self.baseline, **self.events}.items()}
        refresh = {}
        for index in range(4):
            name = f'events/{2000 + index}-native-auth-refresh-' + 'a' * 24 + '-00000000.json'
            raw = self.write(name, {'synthetic_refresh_evidence': index})
            refresh[name] = a._metadata(raw)
        files.update(refresh)
        for index in range(3511 - len(files)):
            files[f'publication-synthetic-{index}.json'] = {'bytes': 20 * 1024**2, 'sha256': '0' * 64}
        self.before = {'format': 'irisx/readonly-presence-state-snapshot-v1', 'observed_epoch': 2.0,
            'files': files, 'file_count': 3511, 'edd_event_count': 196,
            'edd_event_inventory': {name: a._metadata(raw) for name, raw in self.events.items()},
            'refresh_inventory': refresh, 'original_accepted97_frontier_unchanged': True,
            'snapshot_scope': 'synthetic offline full inventory'}
        self.after = {**self.before, 'observed_epoch': 3.0}
        self.stdout = {'format': 'irisx/readonly-cim-native-process-presence-v1',
            'classification': 'ABSENT', 'executor_sid': 'synthetic-sid',
            'candidates': [], 'issues': [], 'queried_basenames': ['python.exe'],
            'original_job_zero_proven': False, 'historical_closure_changed': False,
            'enumeration_query_count': 1,
            'role_counts': {'other_edd_nonce_python': 0, 'sdk_worker': 0, 'win_supervisor': 0}}
        self.stdout.update({key: True for key in ('enumeration_complete', 'executor_sid_equal_config',
            'configuration_sha256_equal', 'query_source_sha256_equal', 'native_sources_equal_config',
            'native_executables_equal_config')})
        self.stdout.update({key: 0 for key in ('candidate_count', 'enumerated_candidate_count',
            'same_sid_count', 'other_sid_count', 'unknown_sid_count',
            'same_or_unknown_sid_incomplete_count', 'missing_field_count')})
        self.result = {'format': 'irisx/readonly-native-process-presence-summary-v1',
            'status': 'QUERY_COMPLETED', 'query_exit_code': 0, 'query_parse_error': None,
            'started_epoch': 1.0, 'finished_epoch': 4.0,
            'original_WSL_config_sha256': '0801edb1af103298efac50380c84ab2e248def1bf5bcf6c6769263f5a6aa97ed',
            'original_native_config_sha256': 'ec32867044bd6de4f8cead0cc6d9f73a45419c1a091dbe3cdbdfadaf669fe0f9',
            'observation': {key: value for key, value in self.stdout.items() if key not in
                ('format', 'executor_sid', 'candidates', 'issues', 'queried_basenames',
                 'original_job_zero_proven', 'historical_closure_changed')}}
        self.result.update({key: True for key in ('STATE_bytes_unchanged', 'lock_held_through_both_snapshots',
            'original_accepted97_frontier_unchanged', 'refresh_metadata_unchanged',
            'publisher_lock_bytes_unchanged', 'source_and_config_bytes_unchanged',
            'native_source_7_after_equal_config', 'no_new_STATE_intent_UNKNOWN_or_refresh')})
        self.result.update({key: 0 for key in ('Job', 'STATE_writes', 'auth', 'old_pipe', 'process_control', 'provider')})
        self.result.update({key: False for key in ('admission_created', 'historical_Job_zero_proven', 'old_closure_modified')})
        for key, (relative, _, _) in dict(a.READONLY_ARTIFACTS).items():
            raw = {'raw_stdout': a._canonical(self.stdout), 'before_snapshot': a._canonical(self.before),
                   'after_snapshot': a._canonical(self.after), 'raw_stderr': b''}.get(key, b'offline-source-only')
            path = out.parent / relative[3:] if relative.startswith('../') else out / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
            a.READONLY_ARTIFACTS[key] = (relative, len(raw), a._digest(raw))
            self.result[key] = a._metadata(raw)
        self.bind_result()

    def bind_result(self):
        raw = self.a._canonical(self.result)
        path = self.out / 'RESULT.json'; path.write_bytes(raw)
        self.result_row = {'path': str(path), **self.a._metadata(raw)}
        self.a.READONLY_RESULT = (len(raw), self.a._digest(raw))

    def classify(self):
        return self.a._classify_readonly(self.c, self.root, self.a._native_roots(self.root), self.pending, self.actual)

    def test_complete_cut_excludes_only_exact_pair_and_is_not_historical_coverage(self):
        with self.common.lock():
            pair, names, guard = self.classify()
            self.assertEqual(pair, self.pending[0])
            self.assertEqual(names, set(self.baseline))
            guard()
            # A completed independently bounded successor does not invalidate M.
            self.own_pair(stage='closed')
            _, _, second = self.classify()
            second()
            self.own_pair('b' * 64)
            second('b' * 64)

    def test_query_completed_does_not_override_parse_error_or_inconclusive(self):
        for key, value in (('query_parse_error', 'synthetic'), ('query_exit_code', 1)):
            with self.subTest(key=key), self.common.lock():
                original = self.result[key]; self.result[key] = value; self.bind_result()
                with self.assertRaisesRegex(ValueError, 'context_presence_query_failed'):
                    self.classify()
                self.result[key] = original; self.bind_result()
        for key, value in (('classification', 'INCONCLUSIVE'), ('enumeration_complete', False),
                           ('missing_field_count', 1), ('candidates', [{}]), ('issues', ['missing'])):
            stdout = {**self.stdout, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.a._presence_documents(self.result, stdout, self.before, self.after)

    def test_mismatched_maps_or_count_duplicate_keys_and_changed_original_fail(self):
        import copy
        for field in ('files', 'edd_event_inventory', 'refresh_inventory'):
            changed = copy.deepcopy(self.after)
            changed[field].pop(next(iter(changed[field])))
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.a._presence_documents(self.result, self.stdout, self.before, changed)
        with self.assertRaisesRegex(ValueError, 'context_duplicate_json_key'):
            self.a._json(b'{"status":1,"status":2}')
        with self.common.lock():
            (self.out / 'QUERY-STDOUT.raw').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, 'context_descriptor_changed'):
                self.classify()

    def test_caller_and_current_sid_are_bound_to_real_cut(self):
        with self.common.lock():
            original = self.caller['seq14']['sha256']; self.caller['seq14']['sha256'] = 'f' * 64
            with self.assertRaisesRegex(ValueError, 'context_readonly_caller_pin'):
                self.classify()
            self.caller['seq14']['sha256'] = original
            path = Path(self.actual['windows_bridge']['configuration']['wsl_path'])
            raw = self.a._canonical({'identity': {'sid': 'different-sid'}}); path.write_bytes(raw)
            self.actual['windows_bridge']['configuration']['sha256'] = self.a._digest(raw)
            with self.assertRaisesRegex(ValueError, 'context_readonly_current_native_sid'):
                self.classify()

    def test_inflight_refresh_allows_only_the_exact_bridge_proof(self):
        nonce = self.own_pair()
        name = 'native-auth-refresh-' + 'c' * 24
        raw = self.write(name + '.claim.json', {'bridge_nonce': nonce, 'synthetic_test_only': False,
                                               'existing_grant_only': True})
        proof = {'bridge_nonce': nonce, 'claim_sha256': self.a._digest(raw), 'stage': 'refresh_intent'}
        self.write(name + '-journal.json', proof)
        guard = self.a._readonly_guard(self.c, self.root, self.baseline, self.events, {}, [])
        with self.common.lock():
            guard(nonce, {'name': name, 'proof': proof})
            with self.assertRaisesRegex(ValueError, 'context_readonly_new_refresh_unknown'):
                guard(nonce, {'name': name, 'proof': {**proof, 'sequence': 7}})


class ContextCutIntegrationTests(unittest.TestCase):
    write = FrontierTests.write
    own_pair = FrontierTests.own_pair
    bind_result = CompleteCutTests.bind_result

    @classmethod
    def setUpClass(cls):
        import test_context_continuation as fixture
        fixture.ContextTests.setUpClass()

    def setUp(self):
        import test_context_continuation as fixture
        self.fixture_module = fixture
        self.context = fixture.ContextTests(methodName='runTest')
        self.context.setUp()
        self.addCleanup(self.context.doCleanups)
        self._cut_existing_root = self.context.state
        self._cut_existing_adapter = fixture.a
        CompleteCutTests.setUp(self)
        self.context.current['windows_bridge'] = self.actual['windows_bridge']
        self.context.bind_current()
        self.original_pending = list(self.context.pending)
        self.context.pending += self.pending
        self.received = []
        self.context.callbacks.update(self.c)
        self.context.callbacks['receive_readonly_frontier_guard'] = self.received.append

    def test_real_adapter_keeps_historical_coverage_and_handles_later_closed_successor(self):
        with self.common.lock():
            result = self.context.validate()
            self.assertEqual(result, {self.context.fixture.review_value['unknown_session']:
                self.original_pending[0]['claim']['sha256']})
            self.assertEqual(len(self.received), 1)
            self.received[-1]()
            self.context.fixture._session('a' * 64, ['open'], self.context.current_descriptor,
                self.context.fixture.review_value['original_native_configuration'])
            self.context.current['versions'] = {key: value + 2
                for key, value in self.context.current['versions'].items()}
            self.context.bind_current()
            result2 = self.context.validate()
            self.assertEqual(result, result2)
            self.assertEqual(len(self.received), 2)
            self.received[-1]()

    def test_real_adapter_does_not_filter_new_unknown(self):
        with self.common.lock():
            self.context.fixture._session('a' * 64, ['open'], self.context.current_descriptor,
                self.context.fixture.review_value['original_native_configuration'], unknown=True)
            with self.assertRaisesRegex(ValueError, 'later_session_unknown'):
                self.context.validate()
            self.assertEqual(self.received, [])

    def test_real_adapter_rejects_new_unknown_refresh(self):
        name = 'native-auth-refresh-' + 'e' * 24
        raw = self.write(name + '.claim.json', {'stage': 'intent'})
        self.write(name + '-journal.json', {'stage': 'refresh_intent', 'claim_sha256': self.a._digest(raw)})
        with self.common.lock(), self.assertRaisesRegex(ValueError, 'later_refresh_unknown'):
            self.context.validate()
        self.assertEqual(self.received, [])

    def test_real_adapter_rejects_preexisting_orphan_or_unknown_suffix(self):
        for name in ('native-bridge-' + 'a' * 64 + '-journal.json',
                     'native-auth-refresh-' + 'b' * 24 + '-journal.json',
                     'native-bridge-' + 'c' * 64 + '-unexpected.json'):
            with self.subTest(name=name), self.common.lock():
                self.write(name, {'stage': 'UNKNOWN'})
                with self.assertRaisesRegex(ValueError, 'context_readonly_new_root_pair'):
                    self.context.validate()
                (self.root / name).unlink()
        self.assertEqual(self.received, [])


if __name__ == '__main__':
    unittest.main()

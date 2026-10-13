"""Local reconstruction regressions. Synthetic rows are UNIT-ONLY, never provider proof."""
from __future__ import annotations
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.arc_qwen_rlvr004_20261013.preparation_successor import local_assemble_run006 as a
from tools.arc_qwen_rlvr004_20261013.preparation_successor import local_accept_numeric_mount as mount


class AllocationTests(unittest.TestCase):
    def identity(self, code=18, notebook=35):
        return {'format': 'irisx/preparation-successor-proposed-identity-v1',
            'status': 'PROPOSED_NOT_PROVIDER_RESERVED', 'run_id': 'irisx-qwen14b-rlvr-20261013-run006',
            'versions': {'code_predecessor': code, 'code': code + 1, 'notebook_predecessor': notebook,
                         'inactive': notebook + 1, 'active': notebook + 2}}

    def test_real_observed_and_future_consecutive_allocations_are_inert(self):
        for code, notebook in ((18, 35), (20, 44)):
            document = self.identity(code, notebook)
            self.assertEqual(a.p.identity(a.encoded(document)), document)
            self.assertEqual(a.p.namespaces(document)['run'], a.RUN)

    def test_unknown_nonconsecutive_or_boolean_versions_fail(self):
        for key, value in (('code', 21), ('code_predecessor', 17), ('notebook_predecessor', 34),
                           ('inactive', 38), ('active', 38), ('code', True)):
            document = self.identity()
            document['versions'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                a.p.identity(a.encoded(document))

    def test_namespace_never_reuses_consumed_run005(self):
        document = self.identity()
        document['run_id'] = 'irisx-qwen14b-rlvr-20261012-run005'
        with self.assertRaises(ValueError):
            a.p.identity(a.encoded(document))


class CurrentScopeTests(unittest.TestCase):
    def scope(self):
        return {'format': 'irisx/run006-local-owner-direction-v1', 'owner_id': 'danielwuu',
            'instruction': 'UNIT-ONLY test message for checking semantic rejection; never owner evidence.',
            'one_accepted_run_authorized': True, 'post_run_readback_once': True,
            'continuous_monitoring_authorized': False, 'watcher_authorized': False,
            'automatic_resubmission_after_delivery_authorized': False,
            'runtime_or_scientific_success_claim': False, 'session_limit_seconds': 43200,
            'public_task_count': 120, 'public_query_denominator': 167}

    def validate(self, document):
        raw = a.encoded(document)
        with patch.object(a, 'pinned', return_value=raw):
            return a.stop_attestation(Path('UNIT-ONLY'), a.sha(raw))

    def test_current_scope_is_single_run_then_one_readback(self):
        document = self.scope()
        self.assertEqual(self.validate(document), a.encoded(document))

    def test_monitor_watcher_resubmit_and_scientific_claim_fail(self):
        for key in ('continuous_monitoring_authorized', 'watcher_authorized',
                    'automatic_resubmission_after_delivery_authorized', 'runtime_or_scientific_success_claim'):
            document = self.scope()
            document[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(document)

    def test_changed_deadline_denominator_or_owner_fails(self):
        for key, value in (('session_limit_seconds', 86400), ('public_task_count', 119),
                           ('public_query_denominator', 166), ('owner_id', 'different-owner')):
            document = self.scope()
            document[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(document)


class GenuineInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local = Path(__file__).absolute().parents[3] / '.irisx/run006-local'

    def test_current_authentic_closed_packet_is_observation_only(self):
        root = self.local / 'sealed-inputs/observation'
        if not root.exists():
            self.skipTest('retained authentic operator inputs are intentionally outside Git')
        raw = a.read(root / 'OBSERVATION.json')
        files = a.observation_inputs(root, a.sha(raw))
        doc = a.obj(files['current-predecessor-v35/OBSERVATION.json'])
        self.assertFalse(doc['runtime_closure_verified'])
        self.assertFalse(doc['scientific_result_verified'])
        self.assertEqual(doc['original_deadline'] - doc['original_epoch'], 43200)

    def test_recovered_assembler_provenance_is_actual_unchanged_bytes(self):
        self.assertEqual(a.sha(a.read(a.HERE / 'assemble_run006.py')), a.RECOVERED_ASSEMBLER_SHA)

    def test_actual_final_candidate_has_minimal_current_owner_identity(self):
        candidate = self.local / 'candidate-run006'
        if not candidate.exists():
            self.skipTest('retained authentic final candidate is intentionally outside Git')
        release = a.obj(a.read(candidate / 'notebook-release.json'))
        owner_raw = a.read(self.local / 'OWNER-REQUEST.json')
        direction = a.obj(owner_raw)
        self.assertEqual(release['original_owner_request'], {
            'owner_id': direction['owner_id'], 'instruction': direction['instruction'],
            'request_id': 'local-run006-owner-direction-sha256-' + a.sha(owner_raw)})
        self.assertEqual(set(release['original_owner_request']), {'owner_id', 'request_id', 'instruction'})

    def test_actual_final_candidate_pure_jit_and_wire_preserve_contract(self):
        candidate = self.local / 'candidate-run006'
        if not candidate.exists():
            self.skipTest('retained authentic final candidate is intentionally outside Git')
        # Deliberate CPU review epoch only. Never write these generated active
        # documents into publication state, reserve a clock or call a provider.
        review_epoch = 1
        manifest_path = candidate / 'publication-manifest.json'
        manifest = a.obj(a.read(manifest_path))
        transport_path = a.HERE.parent / 'publication_run006/rl_transport.py'
        transport = a.p.load_module(a.pinned(transport_path,
            'b746f84bd6e0f4cf971c77650f6bdc1873ef5c3c9efb0f5d07dece15f461ef63'),
            'local_recovery_pure_transport_test', transport_path)
        documents = transport.finalized_documents(manifest, manifest_path, review_epoch)
        self.assertEqual(documents, transport.finalized_documents(manifest, manifest_path, review_epoch))
        self.assertEqual(set(documents), {'active-finalized.ipynb', 'original-request.json',
                                         'operator.json', 'parent-private-scorer.json'})
        owner = a.obj(documents['original-request.json'])
        self.assertEqual(owner['original_epoch'], review_epoch)
        self.assertEqual(owner['request_id'], a.obj(a.read(candidate / 'notebook-release.json'))['original_owner_request']['request_id'])
        cfg = transport.config(documents['active-finalized.ipynb'])
        self.assertEqual((cfg['PREDISPATCH_EPOCH'], cfg['SESSION_SECONDS'], cfg['EXECUTION_CUTOFF_SECONDS'],
                          cfg['OUTER_CUTOFF_SECONDS'], cfg['PROVIDER_RUNTIME_SECONDS']),
                         (review_epoch, 43200, 42000, 42180, 42300))
        self.assertEqual((cfg['OUTPUT_ROOT'], cfg['SOURCE_PARENT']), (a.RUN, a.SOURCE))
        self.assertIs(cfg['MANUAL_START'], True)
        self.assertIs(cfg['ENABLE_MODEL'], True)
        active = transport.row(manifest, 'rlvr004')
        with patch.object(transport, 'PINS', active['dataset_sources']):
            wire = transport.kernel_wire(active, documents['active-finalized.ipynb'])
        self.assertEqual(wire['dataset_data_sources'], active['dataset_sources'])
        self.assertEqual(wire['competition_data_sources'], ['arc-prize-2026-arc-agi-3'])
        self.assertEqual(wire['machine_shape'], 'NvidiaRtxPro6000')
        self.assertEqual(wire['session_timeout_seconds'], 42300)
        self.assertIs(wire['is_private'], True)
        self.assertIs(wire['enable_gpu'], True)
        self.assertIs(wire['enable_tpu'], False)
        self.assertIs(wire['enable_internet'], False)
        self.assertEqual(transport.clock(review_epoch)['global_deadline_epoch'], review_epoch + 43200)
        parent = a.obj(documents['parent-private-scorer.json'])
        self.assertEqual(parent['scorer_pins_sha256'], a.obj(a.read(candidate / 'notebook-release.json'))['scorer_pins_sha256'])

    def test_same_packet_cannot_use_an_unpinned_digest(self):
        root = self.local / 'sealed-inputs/observation'
        if not root.exists():
            self.skipTest('retained authentic operator inputs are intentionally outside Git')
        with self.assertRaisesRegex(ValueError, 'pinned input differs'):
            a.observation_inputs(root, '0' * 64)

    def test_numeric_acceptance_requires_reviewed_manifest_and_inventory_digests(self):
        with self.assertRaisesRegex(ValueError, 'independently pinned'):
            mount.accept(candidate_root='UNIT-ONLY', code_root='UNIT-ONLY', code_receipt_path='UNIT-ONLY',
                         code_receipt_sha='0' * 64, output_root='UNIT-ONLY', manifest_sha=None, inventory_sha=None)


if __name__ == '__main__':
    unittest.main()

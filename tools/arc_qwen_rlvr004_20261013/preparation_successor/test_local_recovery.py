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

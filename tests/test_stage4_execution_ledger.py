from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.stage4_execution_ledger import Ledger, canonical, sha, validate_plan, PLAN, RESOURCE_PLAN


NOW = '2026-10-06T08:00:00+00:00'


def plan(package=b'closed truth-free synthetic package', quota=b'synthetic quota receipt'):
    return {'format': PLAN, 'run_id': 'stage4-synthetic-ledger-001', 'purpose': 'development',
        'created_at': NOW, 'source_commit': 'a' * 40, 'package_sha256': sha(package),
        'provider': 'kaggle', 'private': True, 'internet': False, 'maximum_paid_usd': 0,
        'bounds': {'session_wall_seconds': 600, 'quota_multiplier': 2,
            'reserved_quota_seconds': 1200, 'gpu_count': 4, 'task_runs': 2,
            'training_steps': 256, 'generation_forwards': 8192,
            'verification_forwards': 256, 'input_tokens': 1024 * 1024,
            'maximum_output_bytes': 16 * 1024 * 1024, 'maximum_retrieval_attempts': 2},
        'quota': {'snapshot_sha256': sha(quota), 'observed_at': NOW,
            'remaining_free_seconds': 3600, 'pay_to_scale_enabled': False},
        'materials': {'model_ref': 'synthetic-only', 'model_material_digest': 'sha256:'+'1'*64,
            'source_inventory_digest': 'sha256:'+'2'*64, 'challenge_digest': 'sha256:'+'3'*64,
            'partition_manifest_sha256': '4'*64}}


class PlanTests(unittest.TestCase):
    def resource_plan(self):
        value = plan()
        value['format'] = RESOURCE_PLAN
        value['purpose'] = 'resource-check'
        value['bounds'].update(task_runs=0, training_steps=0, generation_forwards=0,
            verification_forwards=0, synthetic_worker_runs=4, control_forwards=28,
            input_tokens=672)
        return value

    def test_resource_controls_are_explicit_and_not_scientific_or_verification(self):
        value = self.resource_plan()
        self.assertEqual(validate_plan(value), value)
        for key in ('task_runs', 'training_steps', 'generation_forwards', 'verification_forwards'):
            bad = copy.deepcopy(value); bad['bounds'][key] = 1
            with self.subTest(key=key), self.assertRaises(ValueError): validate_plan(bad)
        for key, replacement in (('synthetic_worker_runs', 3), ('control_forwards', 0),
                                 ('control_forwards', True), ('input_tokens', 0)):
            bad = copy.deepcopy(value); bad['bounds'][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError): validate_plan(bad)
        bad = copy.deepcopy(value); bad['purpose'] = 'development'
        with self.assertRaises(ValueError): validate_plan(bad)

    def test_resource_and_historical_plan_schemas_do_not_alias(self):
        value = self.resource_plan()
        bad = copy.deepcopy(value); bad['format'] = PLAN
        with self.assertRaises(ValueError): validate_plan(bad)
        for key in ('control_forwards', 'synthetic_worker_runs'):
            bad = copy.deepcopy(value); del bad['bounds'][key]
            with self.subTest(key=key), self.assertRaises(ValueError): validate_plan(bad)
        bad = plan(); bad['bounds']['task_runs'] = 0
        with self.assertRaises(ValueError): validate_plan(bad)

    def test_resource_plan_uses_same_crash_conservative_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); package = root/'package'; quota = root/'quota'
            package.write_bytes(b'closed truth-free synthetic package')
            quota.write_bytes(b'synthetic quota receipt')
            ledger = Ledger(root/'fixture-only-ledger')
            ledger.initialize(self.resource_plan(), package=package, quota_snapshot=quota, now=NOW)
            request = ledger.reserve('push', now=NOW)
            self.assertEqual(ledger.read()['pending'], {request: 'push'})
            with self.assertRaises(ValueError): ledger.reserve('push', now=NOW)

    def test_closed_private_free_bound(self):
        self.assertEqual(validate_plan(plan()), plan())
        for field, value in [('purpose', 'official-submission'), ('private', False),
                             ('internet', True), ('maximum_paid_usd', 1),
                             ('maximum_paid_usd', False), ('source_commit', 'main')]:
            candidate = plan(); candidate[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_plan(candidate)

    def test_nonfinite_bool_negative_and_oversubscribed_rejected(self):
        for key, value in [('session_wall_seconds', float('nan')), ('task_runs', True),
                           ('input_tokens', -1), ('quota_multiplier', float('inf')),
                           ('reserved_quota_seconds', 1199), ('gpu_count', 5)]:
            candidate = plan(); candidate['bounds'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_plan(candidate)
        candidate = plan(); candidate['quota']['remaining_free_seconds'] = 1199
        with self.assertRaises(ValueError): validate_plan(candidate)
        candidate = plan(); candidate['quota']['pay_to_scale_enabled'] = True
        with self.assertRaises(ValueError): validate_plan(candidate)

    def test_truth_and_extra_keys_rejected(self):
        for container in ('root', 'materials', 'quota', 'bounds'):
            candidate = plan()
            (candidate if container == 'root' else candidate[container])['test_outputs'] = [[[0]]]
            with self.subTest(container=container), self.assertRaises(ValueError):
                validate_plan(candidate)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.package, self.quota = self.base/'package.bin', self.base/'quota.json'
        self.package.write_bytes(b'closed truth-free synthetic package')
        self.quota.write_bytes(b'synthetic quota receipt')
        self.ledger = Ledger(self.base/'ledger')
        self.ledger.initialize(plan(), package=self.package, quota_snapshot=self.quota, now=NOW)

    def reserve(self, action): return self.ledger.reserve(action, now=NOW)

    def receipt(self, request_id, result, **kwargs):
        if (self.ledger.read()['pending'].get(request_id) in {'status', 'retrieve'}
                and 'provider_identity' not in kwargs):
            kwargs['provider_identity'] = self.ledger.read()['accepted']
        return self.ledger.receipt(request_id, result, receipt_sha256='e'*64, now=NOW, **kwargs)

    def accepted(self):
        identity = {'kernel_id': 'owner/stage4-synthetic-ledger-001', 'version': 1}
        self.receipt(self.reserve('push'), 'accepted', provider_identity=identity)
        return identity

    def terminal(self):
        self.accepted()
        self.receipt(self.reserve('status'), 'complete')

    def test_complete_local_state_machine_and_immutable_identity(self):
        identity = self.accepted()
        self.assertEqual(self.ledger.read()['accepted'], identity)
        self.receipt(self.reserve('status'), 'queued')
        self.receipt(self.reserve('status'), 'running')
        self.receipt(self.reserve('status'), 'complete')
        self.receipt(self.reserve('retrieve'), 'verified')
        state = self.ledger.read()
        self.assertTrue(state['retrieved'])
        self.assertEqual(state['counts'], {'push': 1, 'status': 3, 'retrieve': 1})
        for action in ('push', 'status', 'retrieve', 'competition-submit'):
            with self.subTest(action=action), self.assertRaises(ValueError): self.reserve(action)

    def test_uncertain_push_cannot_duplicate(self):
        pending = self.reserve('push')
        self.assertEqual(self.ledger.read()['pending'], {pending: 'push'})
        for action in ('push', 'status', 'retrieve'):
            with self.subTest(action=action), self.assertRaises(ValueError): self.reserve(action)
        with self.assertRaises(ValueError): self.receipt(pending, 'unknown')
        self.assertEqual(self.ledger.read()['pending'], {pending: 'push'})

    def test_rejection_consumes_identity_and_no_unaccepted_status(self):
        self.receipt(self.reserve('push'), 'rejected-without-version')
        for action in ('push', 'status', 'retrieve'):
            with self.assertRaises(ValueError): self.reserve(action)

    def test_receipt_cannot_bind_fake_version_or_return_token_fields(self):
        request_id = self.reserve('push')
        for identity in ({'kernel_id': 'owner/kernel', 'version': True},
                         {'kernel_id': 'owner/kernel', 'version': 1, 'token': 'not-a-secret'},
                         {'kernel_id': 'https://example.org/private', 'version': 1}):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                self.receipt(request_id, 'accepted', provider_identity=identity)
        self.assertIn(request_id, self.ledger.read()['pending'])

    def test_preterminal_retrieval_and_overlimit_retrieval_rejected(self):
        self.accepted()
        with self.assertRaises(ValueError): self.reserve('retrieve')
        self.receipt(self.reserve('status'), 'error')
        for _ in range(2): self.receipt(self.reserve('retrieve'), 'failed')
        with self.assertRaises(ValueError): self.reserve('retrieve')

    def test_stale_or_future_quota_never_launches(self):
        for now in ('2026-10-06T08:15:01+00:00', '2026-10-06T07:59:59+00:00'):
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.ledger.reserve('push', now=now)
        self.assertEqual(self.ledger.read()['counts']['push'], 0)

    def test_altered_package_or_quota_rejected_before_initialization(self):
        for key in ('package', 'quota'):
            target = self.package if key == 'package' else self.quota
            previous = target.read_bytes(); target.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                Ledger(self.base/key).initialize(plan(), package=self.package, quota_snapshot=self.quota, now=NOW)
            target.write_bytes(previous)

    def test_duplicate_initialization_preserves_current_bytes(self):
        before = (self.ledger.root/'state.json').read_bytes()
        with self.assertRaises(FileExistsError):
            self.ledger.initialize(plan(), package=self.package, quota_snapshot=self.quota, now=NOW)
        self.assertEqual((self.ledger.root/'state.json').read_bytes(), before)

    def test_marker_or_plan_tamper_rejected(self):
        self.reserve('push')
        path = self.ledger.root/'plan.json'; original = path.read_bytes()
        candidate = json.loads(original); candidate['bounds']['task_runs'] = 99
        path.write_bytes(canonical(candidate))
        with self.assertRaises(ValueError): self.ledger.read()
        path.write_bytes(original)
        event = self.ledger.root/'events/000001.json'
        value = json.loads(event.read_bytes()); value['event']['action'] = 'competition-submit'
        event.write_bytes(canonical(value))
        with self.assertRaises(ValueError): self.ledger.read()

    def test_rehashed_invalid_transition_still_rejected(self):
        self.reserve('push')
        event = self.ledger.root/'events/000001.json'
        value = json.loads(event.read_bytes()); value['event']['action'] = 'retrieve'
        value['event'].pop('campaign_sha256')
        body = canonical(value); event.write_bytes(body)
        (self.ledger.root/'state.json').write_bytes(canonical({'sequence': 1, 'sha256': sha(body)}))
        with self.assertRaisesRegex(ValueError, 'accepted exact'): self.ledger.read()

    def test_interrupted_marker_keeps_prior_complete_state_and_blocks_orphan_reuse(self):
        before = self.ledger.read()['marker']
        with patch('tools.stage4_execution_ledger.os.replace', side_effect=OSError('disk-like failure')):
            with self.assertRaises(OSError): self.reserve('push')
        self.assertEqual(self.ledger.read()['marker'], before)
        self.assertEqual(self.ledger.read()['counts']['push'], 0)
        with self.assertRaises(FileExistsError): self.reserve('push')

    def test_lock_contention_never_overwrites_owner(self):
        lock = self.ledger.root/'.owner.lock'; lock.write_bytes(b'existing owner')
        with self.assertRaises(FileExistsError): self.reserve('push')
        self.assertEqual(lock.read_bytes(), b'existing owner')

    def test_symlink_event_rejected(self):
        path = self.ledger.root/'events/000000.json'
        body = path.read_bytes(); path.unlink()
        other = self.base/'elsewhere'; other.write_bytes(body); path.symlink_to(other)
        with self.assertRaises(ValueError): self.ledger.read()

    def test_shared_campaign_rejects_duplicate_identity_and_quota(self):
        second = Ledger(self.base/'second')
        second.initialize(plan(), package=self.package, quota_snapshot=self.quota, now=NOW)
        self.reserve('push')
        with self.assertRaisesRegex(ValueError, 'identity already consumed'):
            second.reserve('push', now=NOW)
        third = Ledger(self.base/'third'); third_plan = plan()
        third_plan['run_id'] = 'stage4-synthetic-quota-002'
        third_plan['quota']['remaining_free_seconds'] = 1200
        third.initialize(third_plan, package=self.package, quota_snapshot=self.quota, now=NOW)
        with self.assertRaisesRegex(ValueError, 'shared campaign'):
            third.reserve('push', now=NOW)

    def test_exact_immutable_payload_closes_original_path_race(self):
        request = self.reserve('push')
        original = self.ledger.payload_for_push(request)
        self.package.write_bytes(b'changed after reservation')
        self.assertEqual(self.ledger.payload_for_push(request), original)
        (self.ledger.root/'outbound.bin').write_bytes(b'tampered snapshot')
        with self.assertRaises(ValueError): self.ledger.payload_for_push(request)

    def test_original_changed_before_push_is_rejected(self):
        self.package.write_bytes(b'changed before reservation')
        with self.assertRaisesRegex(ValueError, 'package source changed'):
            self.reserve('push')

    def test_observations_require_exact_accepted_version(self):
        self.accepted(); request = self.reserve('status')
        for identity in (None, {'kernel_id': 'owner/stage4-synthetic-ledger-001', 'version': 2},
                         {'kernel_id': 'owner/stage4-synthetic-ledger-001', 'version': True},
                         {'kernel_id': 'owner/stage4-synthetic-ledger-001', 'version': 1.0}):
            with self.assertRaisesRegex(ValueError, 'kernel/version'):
                self.ledger.receipt(request, 'complete', receipt_sha256='e'*64,
                                    provider_identity=identity, now=NOW)
        self.receipt(request, 'complete')

    def test_invalid_timestamp_does_not_touch_journal(self):
        self.accepted()
        before = {str(p): p.read_bytes() for p in self.ledger.root.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError): self.ledger.reserve('status', now='invalid')
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.ledger.root.rglob('*') if p.is_file()})
        request = self.reserve('status'); before = (self.ledger.root/'state.json').read_bytes()
        with self.assertRaises(ValueError):
            self.ledger.receipt(request, 'complete', receipt_sha256='e'*64,
                                provider_identity=self.ledger.read()['accepted'], now='invalid')
        self.assertEqual((self.ledger.root/'state.json').read_bytes(), before)

    def test_single_clock_capture_on_freshness_boundary(self):
        with patch('tools.stage4_execution_ledger.utc', side_effect=[
                '2026-10-06T08:15:00+00:00', '2026-10-06T08:15:01+00:00']) as clock:
            self.ledger.reserve('push')
        self.assertEqual(clock.call_count, 1)
        self.assertEqual(self.ledger.read()['counts']['push'], 1)

    def test_termination_does_not_resurrect_consumed_old_quota(self):
        self.terminal()
        candidate = plan(); candidate['run_id'] = 'stage4-stale-quota-002'
        candidate['quota']['remaining_free_seconds'] = 1200
        second = Ledger(self.base/'second')
        second.initialize(candidate, package=self.package, quota_snapshot=self.quota, now=NOW)
        with self.assertRaisesRegex(ValueError, 'shared campaign'):
            second.reserve('push', now=NOW)

    def test_campaign_record_is_bound_to_exact_journal_event(self):
        self.reserve('push')
        path = self.ledger.campaign_root/(plan()['run_id']+'.json')
        value = json.loads(path.read_bytes()); value['at'] = '2020-01-01T00:00:00+00:00'
        path.write_bytes(canonical(value))
        with self.assertRaisesRegex(ValueError, 'campaign reservation differs'):
            self.ledger.read()


if __name__ == '__main__': unittest.main()

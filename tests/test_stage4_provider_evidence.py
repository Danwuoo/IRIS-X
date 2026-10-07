from __future__ import annotations
import copy
import unittest

from tools.stage4_execution_ledger import canonical
from tools.stage4_provider_evidence import (quota_cost, normalize_quota, ledger_quota,
    execution_source_digest, validate_current_kernel, normalize_status)

NOW = '2026-10-06T08:00:00+00:00'


def raw():
    return {'gpuQuota': {'timeUsed': '90000s', 'timeReserved': '1200s',
                        'totalTimeAllowed': '108000s', 'isPayToScaleEnabled': False},
            'tpuQuota': {}, 'quotaRefreshTime': '2026-10-12T00:00:00Z'}


def typed():
    return {'gpu_used_seconds': 90000, 'gpu_reserved_seconds': 1200,
            'gpu_total_seconds': 108000, 'gpu_pay_to_scale_enabled': False}


class QuotaEvidenceTests(unittest.TestCase):
    def test_official_sdk_optional_minimum_and_history_fields(self):
        value = raw()
        value['gpuQuota'].update(minimumTimeAllowed='108000s', hasEverRun=True)
        value['tpuQuota'] = {'minimumTimeAllowed': '72000s', 'totalTimeAllowed': '72000s',
                             'timeUsed': '0s', 'timeReserved': '0s', 'hasEverRun': False}
        self.assertEqual(normalize_quota(canonical(value), typed(), account='offline-owner',
            observed_at=NOW)['remaining_free_seconds'], 16800)
        for key, replacement in [('hasEverRun', 1), ('minimumTimeAllowed', 'broken'),
                                  ('minimumTimeAllowed', '108001s'), ('unrecognizedQuota', '0s')]:
            broken = copy.deepcopy(value); broken['gpuQuota'][key] = replacement
            with self.subTest(key=key, value=replacement), self.assertRaises(ValueError):
                normalize_quota(canonical(broken), typed(), account='offline-owner', observed_at=NOW)

    def test_minimum_quota_wire_comparison_does_not_round_away_a_nanosecond(self):
        value = raw(); values = typed()
        value['gpuQuota'].update(totalTimeAllowed='100000000s', minimumTimeAllowed='100000000.000000001s')
        values['gpu_total_seconds'] = 100000000
        with self.assertRaisesRegex(ValueError, 'minimum guaranteed quota exceeds'):
            normalize_quota(canonical(value), values, account='offline-owner', observed_at=NOW)

    def test_primary_typed_days_and_account_binding(self):
        value = normalize_quota(canonical(raw()), typed(), account='offline-owner', observed_at=NOW)
        self.assertEqual(value['remaining_free_seconds'], 16800)
        self.assertFalse(value['permission_granted'])
        projected = ledger_quota(canonical(value), expected_account='offline-owner', now=NOW)
        self.assertEqual(projected['remaining_free_seconds'], 16800)
        with self.assertRaises(ValueError):
            ledger_quota(canonical(value), expected_account='other-owner', now=NOW)

    def test_sdk_day_truncation_rejected(self):
        broken = typed(); broken['gpu_used_seconds'] = 3600
        with self.assertRaises(Exception):
            normalize_quota(canonical(raw()), broken, account='offline-owner', observed_at=NOW)

    def test_paid_bool_numeric_and_nonfinite_fail_closed(self):
        for key, value in [('gpu_used_seconds', True), ('gpu_reserved_seconds', float('nan')),
                           ('gpu_pay_to_scale_enabled', True)]:
            changed = typed(); changed[key] = value
            with self.subTest(key=key), self.assertRaises(Exception):
                normalize_quota(canonical(raw()), changed, account='offline-owner', observed_at=NOW)
        changed = raw(); changed['gpuQuota']['isPayToScaleEnabled'] = True
        with self.assertRaises(Exception):
            normalize_quota(canonical(changed), typed(), account='offline-owner', observed_at=NOW)

    def test_duplicate_keys_and_unknown_fields_rejected(self):
        body = b'{"gpuQuota":{},"gpuQuota":{},"tpuQuota":{},"quotaRefreshTime":"2026-10-12T00:00:00Z"}'
        with self.assertRaises(Exception): normalize_quota(body, typed(), account='offline-owner', observed_at=NOW)
        changed = raw(); changed['accessToken'] = 'synthetic-placeholder'
        with self.assertRaises(Exception):
            normalize_quota(canonical(changed), typed(), account='offline-owner', observed_at=NOW)

    def test_quota_units_do_not_multiply_allocation_ratio(self):
        cost = quota_cost(wall_seconds=5*3600, gpu_count=4, allocated_gpu_hours_per_quota_hour=2)
        self.assertEqual(cost['allocated_gpu_seconds'], 20*3600)
        self.assertEqual(cost['charged_quota_seconds'], 10*3600)
        self.assertEqual(cost['charged_quota_seconds_per_wall_second'], 2)
        for count in (True, 0, 5):
            with self.assertRaises(ValueError):
                quota_cost(wall_seconds=100, gpu_count=count, allocated_gpu_hours_per_quota_hour=2)

    def test_no_unverified_discount_or_zero_bounds(self):
        for wall, ratio in ((0, 2), (100, 0), (100, 8), (float('inf'), 2)):
            with self.assertRaises(ValueError):
                quota_cost(wall_seconds=wall, gpu_count=4, allocated_gpu_hours_per_quota_hour=ratio)

    def test_current_window_freshness_and_arithmetic(self):
        value = normalize_quota(canonical(raw()), typed(), account='offline-owner', observed_at=NOW)
        for now in ('2026-10-06T07:59:59Z', '2026-10-06T08:15:01Z'):
            with self.assertRaises(ValueError): ledger_quota(canonical(value), expected_account='offline-owner', now=now)
        value['remaining_free_seconds'] += 1
        with self.assertRaises(ValueError): ledger_quota(canonical(value), expected_account='offline-owner', now=NOW)

    def test_raw_expired_window_and_unexpected_quota_keys(self):
        for key, value in [('quotaRefreshTime', '2026-10-05T00:00:00Z'), ('extra', 'not retained')]:
            changed = raw(); changed[key] = value
            with self.assertRaises(ValueError):
                normalize_quota(canonical(changed), typed(), account='offline-owner', observed_at=NOW)

    def test_finite_inputs_cannot_overflow_resource_outputs(self):
        for wall, ratio in ((1e308, 2), (1, 1e-308)):
            with self.assertRaises(ValueError):
                quota_cost(wall_seconds=wall, gpu_count=4, allocated_gpu_hours_per_quota_hour=ratio)

    def test_rounding_tolerance_produces_coherent_conservative_snapshot(self):
        changed = raw(); changed['gpuQuota'].update(timeUsed='1s', timeReserved='2s', totalTimeAllowed='10s')
        values = {'gpu_used_seconds': .9999994, 'gpu_reserved_seconds': 1.9999994,
                  'gpu_total_seconds': 10.0000006, 'gpu_pay_to_scale_enabled': False}
        snapshot = normalize_quota(canonical(changed), values, account='offline-owner', observed_at=NOW)
        self.assertEqual(snapshot['remaining_free_seconds'], 7)
        self.assertEqual(ledger_quota(canonical(snapshot), expected_account='offline-owner', now=NOW)
                         ['remaining_free_seconds'], 7)

    def test_malformed_primary_duration_is_not_sdk_text_repaired(self):
        changed = raw(); changed['gpuQuota']['timeUsed'] = '90061.125.0s'
        values = typed(); values['gpu_used_seconds'] = 90061.125
        with self.assertRaises(ValueError):
            normalize_quota(canonical(changed), values, account='offline-owner', observed_at=NOW)

    def test_unused_tpu_quota_still_has_closed_typed_schema(self):
        for value in (None, [], 0, True, 'text', {'solutions': [[[0]]]},
                      {'timeUsed': 'bad'}, {'isPayToScaleEnabled': 0}):
            changed = raw(); changed['tpuQuota'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_quota(canonical(changed), typed(), account='offline-owner', observed_at=NOW)


class KernelObservationTests(unittest.TestCase):
    def setUp(self):
        self.identity = {'kernel_id': 'offline-owner/stage4-independent-001', 'version': 1}
        self.notebook = {'nbformat': 4, 'nbformat_minor': 5,
            'cells': [{'cell_type': 'code', 'source': ['print("synthetic")\n'], 'outputs': []}]}
        self.metadata = {**self.identity, 'private': True, 'internet': False, 'gpu': True,
                         'tpu': False, 'machine_shape': 'NvidiaL4'}
        self.digest = execution_source_digest(self.notebook)

    def observation(self, metadata=None, notebook=None):
        return validate_current_kernel(self.metadata if metadata is None else metadata,
            self.notebook if notebook is None else notebook, expected_identity=self.identity,
            expected_source_digest=self.digest)

    def test_source_semantics_explicitly_distinct_from_notebook_byte_hash(self):
        second = copy.deepcopy(self.notebook); second['cells'][0]['source'] = 'print("synthetic")\n'
        self.assertEqual(execution_source_digest(second), self.digest)
        self.assertEqual(self.observation(notebook=second), self.observation())
        second['cells'][0]['source'] += 'print("changed")\n'
        with self.assertRaises(ValueError): self.observation(notebook=second)

    def test_version_and_settings_exact_types(self):
        for key, value in [('version', True), ('version', 1.0), ('version', 2),
                           ('private', 1), ('private', False), ('internet', True),
                           ('kernel_id', 'other-owner/same'), ('machine_shape', 'unknown')]:
            changed = copy.deepcopy(self.metadata); changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.observation(metadata=changed)

    def test_extra_cell_and_source_order_cannot_hide(self):
        changed = copy.deepcopy(self.notebook)
        changed['cells'].append({'cell_type': 'code', 'source': 'print("extra")'})
        with self.assertRaises(ValueError): self.observation(notebook=changed)
        changed['cells'][-1]['cell_type'] = 'markdown'
        # Documentation is not executable source. Reclassifying an ORIGINAL
        # executable cell still changes the ordered-code digest below.
        self.assertEqual(self.observation(notebook=changed), self.observation())
        changed['cells'][0]['cell_type'] = 'markdown'
        with self.assertRaises(ValueError): self.observation(notebook=changed)

    def test_actual_stage4_renderer_documentation_and_code_digest(self):
        from tools.stage_nvarc_e10_screen import render
        notebook = render({'screen_id': 'stage4-e10-screen-digest-fixture',
            'maximum_archive_uncompressed_bytes': 1024}, {})
        self.assertEqual([cell['cell_type'] for cell in notebook['cells']], ['markdown', 'code', 'markdown', 'code'])
        expected = execution_source_digest(notebook)
        changed = copy.deepcopy(notebook)
        changed['cells'][0]['source'] = 'Changed non-executable documentation only'
        self.assertEqual(execution_source_digest(changed), expected)
        changed['cells'][2]['source'] = 'Changed download documentation only'
        self.assertEqual(execution_source_digest(changed), expected)
        for index in (1, 3):
            modified = copy.deepcopy(changed)
            modified['cells'][index]['source'].append('print("extra executable work")\n')
            self.assertNotEqual(execution_source_digest(modified), expected)
        for kind in ('raw', '', True, None):
            bad = copy.deepcopy(notebook); bad['cells'][0]['cell_type'] = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError): execution_source_digest(bad)

    def test_status_requires_stable_bracketing_and_does_not_claim_exit_or_score(self):
        before = self.observation(); after = copy.deepcopy(before)
        value = normalize_status('COMPLETE', before=before, after=after)
        self.assertEqual(value['identity'], self.identity)
        self.assertEqual(value['status'], 'complete')
        self.assertFalse(value['notebook_exit_inferred'])
        self.assertIsNone(value['official_score'])
        after['identity']['version'] = 2
        with self.assertRaises(ValueError): normalize_status('COMPLETE', before=before, after=after)

    def test_unknown_or_missing_typed_status_not_default_success(self):
        observation = self.observation()
        for status in ('', None, 'new-provider-state', 0, 'CANCEL_REQUESTED'):
            with self.assertRaises(ValueError): normalize_status(status, before=observation, after=observation)

    def test_foreign_or_extra_observation_fields_rejected(self):
        observation = self.observation(); observation['solutions'] = [[[0]]]
        with self.assertRaises(ValueError): normalize_status('COMPLETE', before=observation, after=observation)

    def test_after_observation_cannot_use_python_numeric_type_equivalence(self):
        before = self.observation()
        for version in (True, 1.0):
            after = copy.deepcopy(before); after['identity']['version'] = version
            with self.assertRaises(ValueError): normalize_status('COMPLETE', before=before, after=after)


if __name__ == '__main__': unittest.main()

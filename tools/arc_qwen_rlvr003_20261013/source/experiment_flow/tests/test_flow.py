"""Controlled adapters: no torch, model, provider, labels or network access."""
from copy import deepcopy
from pathlib import Path
import json, tempfile, unittest
from experiment_flow import ExperimentPlan, FixtureShape, Forecast, SourceFreeze, run_local_experiment, production_admission
from experiment_flow.contracts import canonical, digest, write_json, RecoverableWorkError, FatalStateError
from experiment_flow.audit import summarize
from experiment_flow.evaluation import read_predictions, select_dev

ROOT = Path(__file__).resolve().parents[2]
GATE = canonical({'maximum_absolute_gap': .20, 'minimum_unclipped_fraction': 1.,
                  'maximum_replay_seconds': 30., 'maximum_peak_bytes': 2**30,
                  'fixture_only': True, 'maximum_p95_gap': .05})


class Clock:
    def __init__(self): self.now = 50000.
    def __call__(self): return self.now
    def advance(self, value): self.now += value


class Dataset:
    scope = 'controlled-adapter-fixture'
    plan_sha256 = 'd' * 64
    def __init__(self, shape):
        self.shape = shape
        self.opened = []
    def cases(self, scope):
        n = self.shape.dev_cases if scope == 'dev' else self.shape.holdout_cases
        return [{'case_id': scope + ':' + str(i), 'parent_id': scope + str(i), 'scope': scope,
                 'demos': [{'input': [[0]], 'output': [[1]]}], 'query_input': [[i]],
                 'source': {'synthetic': True}} for i in range(n)]
    def bind_evaluator(self, authority):
        assert not hasattr(self, '_authority')
        self._authority = authority
    def open_targets(self, scope, seal, *, selection, authority=None):
        assert authority is self._authority
        authority.verify_escrow(scope, seal, selection)
        if scope == 'holdout':
            assert selection and 'dev' in self.opened
        assert scope not in self.opened
        self.opened.append(scope)
        return {c['case_id']: [[c['query_input'][0][0] + 1]] for c in self.cases(scope)}


class Panel:
    scope = 'controlled-adapter-fixture'
    def __init__(self, shape):
        self.parent_ids = tuple('train' + str(i) for i in range(shape.parents))
        self.group_size = shape.group_size
    def receipt(self, exposure):
        return {'parent_ids': list(self.parent_ids), 'committed_exposure': list(exposure), 'seeds_independent_of_exposure': True}


class FakeAdapter:
    scope = 'controlled-adapter-fixture'
    def __init__(self, clock, branch='mixed', *, sweep_cost=10., step_cost=2., save_cost=1.):
        self.clock, self.branch = clock, branch
        self.sweep_cost, self.step_cost, self.save_cost = sweep_cost, step_cost, save_cost
        self.state = {'weight': 0, 'stage': 'anchor', 'anchor_updates': 0, 'rl_updates': 0, 'control_updates': 0, 'cursor': 0}
        self.events, self.exposed = [], []
        self.fatal = False
        self.predictions = 0
        self.update_calls = 0
        self.batches = []
    def _op(self, name, seconds=1., failed=False):
        start = self.clock()
        self.clock.advance(seconds)
        self.events.append({'event_id': len(self.events), 'phase': name, 'started': start, 'ended': self.clock(), 'seconds': seconds,
                            'dispatched': True, 'status': 'failed' if failed else 'complete'})
    def sync(self):
        if self.fatal: raise FatalStateError('unknown device state')
    def assert_safe(self): self.sync()
    def assert_settled(self): self.sync()
    def identity(self):
        if getattr(self, 'identity_lost', False): raise RuntimeError('identity unavailable after failed close')
        return {'adapter_sha256': digest(self.state['weight']), 'policy_version': str(self.state['weight']), 'source_sha256': 'a' * 64}
    def counts(self): return {k: self.state[k] for k in ('anchor_updates', 'rl_updates', 'control_updates')}
    def successful_exposure(self): return tuple(self.exposed)
    def physical_events(self): return self.events
    def bind_training(self, dataset, panel): pass
    def sft_step(self, *, deadline):
        kind = 'anchor' if self.state['stage'] == 'anchor' else 'control'
        if self.branch == 'control-failure' and kind == 'control':
            self._op('control-failed-rolled-back', self.step_cost, True)
            raise RecoverableWorkError('controlled safe SFT rollback')
        self._op(kind + '-sft', self.step_cost)
        self.state[kind + '_updates'] += 1
        self.state['weight'] += 1 if kind == 'anchor' else 10
        self.state['cursor'] += 1
        self.exposed.append('row' + str(self.state['cursor']))
        return {'optimizer_committed': True}
    def begin(self, kind, *, deadline):
        assert self.state['stage'] == 'anchor'
        self._op('setup-' + kind)
        self.state['stage'] = kind
    def snapshot(self, label):
        return deepcopy(self.state)
    def restore(self, handle, *, deadline):
        self._op('restore')
        self.state = deepcopy(handle)
    def release_snapshot(self, handle): pass
    def close(self):
        if self.branch == 'close-failure':
            self.identity_lost = True
            raise RuntimeError('cleanup failed')
        if self.branch == 'bad-close':
            return {'closed': True, 'future_operations_blocked': True, 'model_references_released': True,
                    'device_synchronized': False, 'model_stopped': False, 'ledger_settled': False,
                    'fatal_native_state': 'cleanup-sync-failure'}
        self.assert_safe()
        self.closed = True
        return {'closed': True, 'future_operations_blocked': True, 'model_references_released': True,
                'device_synchronized': True, 'model_stopped': True, 'ledger_settled': True,
                'fatal_native_state': None, 'controlled_fake': True}
    def collect(self, panel, *, sweep, max_new_tokens, deadline):
        self._op('sample', self.sweep_cost)
        rows = []
        for parent in panel.parent_ids:
            for slot in range(panel.group_size):
                row = {'parent_id': parent, 'slot': slot, 'eligible': True, 'reward': slot % 2,
                       'status': 'eligible', 'trajectory': {'steps': [{'token': slot}], 'dispatched': True}}
                if self.branch in ('zero', 'no-update-drift'): row['reward'] = 0
                if self.branch in ('incomplete', 'sample-failure') and len(rows) > 0 or self.branch == 'later-incomplete' and sweep > 0 and len(rows) > 0:
                    row.update(eligible=False, reward=None, trajectory=None, status='not-reached')
                if self.branch == 'infrastructure':
                    row.update(eligible=False, reward=None, status='infrastructure-excluded')
                if self.branch == 'one-infrastructure' and slot == 0:
                    row.update(eligible=False, reward=None, status='infrastructure-excluded')
                if self.branch == 'context':
                    row.update(eligible=False, reward=None, trajectory=None, status='context-excluded')
                rows.append(row)
        batch = {'rows': rows, 'sweep': sweep, 'planned_attempts': len(rows), 'closed': True,
                 'all_slots_reached': all(r['status'] != 'not-reached' for r in rows),
                 'fatal_native_state': False, 'policy_version': self.state['weight']}
        self.batches.append(batch)
        if self.branch == 'fatal':
            self.fatal = True
            raise FatalStateError('controlled fatal native state')
        if self.branch == 'sample-failure':
            raise RecoverableWorkError('controlled partial audit', batch=batch)
        return batch
    def update(self, batch, *, gate_json, deadline):
        self.update_calls += 1
        self._op('RL-update', 2.)
        if self.branch == 'numeric': return {'optimizer_committed': False, 'status': 'numeric-nonadmission-no-update'}
        if self.branch == 'update-failure': raise RecoverableWorkError('controlled update rollback', batch=batch)
        self.state['weight'] += 1
        self.state['rl_updates'] += 1
        return {'optimizer_committed': True, 'status': 'committed'}
    def save(self, path, *, deadline):
        self._op('save', self.save_cost)
        manifest = {'state_sha256': digest(self.state), 'counts': self.counts(), 'files': {}, 'controlled_fake': True}
        write_json(Path(path) / 'state.json', self.state)
        write_json(Path(path) / 'manifest.json', manifest)
        return manifest
    def reload(self, path, *, deadline):
        self._op('reload', self.save_cost)
        self.state = json.loads((Path(path) / 'state.json').read_text())
        return {'reload_verified': True, 'same_source': True, 'state_sha256': digest(self.state)}
    def predict(self, case, *, transform, seed, max_new_tokens, deadline):
        self._op('predict', .1)
        self.predictions += 1
        index = case['query_input'][0][0]
        matches = 1 if self.state['weight'] == 1 else 2 if self.state['weight'] == 2 else 0
        answer = [[index + 1]] if index < matches else [[0]]
        if self.branch == 'dev-incomplete' and case['scope'] == 'dev':
            return {'case_id': case['case_id'], 'prediction': None, 'dispatched': True, 'transform': transform,
                    'status': 'infrastructure-excluded', 'adapter_sha256': self.identity()['adapter_sha256'], 'query_targets_used': False}
        if self.branch == 'invalid-grid':
            return {'case_id': case['case_id'], 'prediction': answer, 'dispatched': True, 'transform': transform,
                    'status': 'invalid', 'adapter_sha256': self.identity()['adapter_sha256'], 'query_targets_used': False}
        if self.branch == 'wrong-identity':
            return {'case_id': 'wrong', 'prediction': answer, 'dispatched': True, 'transform': transform,
                    'status': 'complete', 'adapter_sha256': self.identity()['adapter_sha256'], 'query_targets_used': True}
        if self.branch == 'no-update-drift' and self.state['stage'] == 'rl': answer = [[9]]
        return {'case_id': case['case_id'], 'prediction': answer, 'dispatched': True, 'transform': transform,
                'status': 'complete', 'adapter_sha256': self.identity()['adapter_sha256'], 'query_targets_used': False}


class FlowTests(unittest.TestCase):
    def run_case(self, branch='mixed', *, shape=None, remaining=41000., forecast=None, adapter_kwargs=None):
        shape = shape or FixtureShape(dev_cases=2, holdout_cases=2, max_control_updates=50)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        clock = Clock()
        plan = ExperimentPlan(SourceFreeze.capture(ROOT), forecast or Forecast('f'*64, 'controlled-fixture', 1., 12., 2., 2., 10., 10., 2., 2.),
                              clock() - (42000. - remaining), GATE, shape=shape, output_cap=1)
        # Valid global origin is nonnegative, use a sufficiently advanced clock.
        adapter = FakeAdapter(clock, branch, **(adapter_kwargs or {}))
        dataset, panel = Dataset(shape), Panel(shape)
        result = run_local_experiment(adapter, dataset, panel, plan, Path(self.tmp.name) / 'run', clock=clock)
        result=deepcopy(result)
        if result.get('physical_events_ref'):result['physical_events']=json.loads(Path(result['physical_events_ref']['path']).read_text())
        result['audit_sweeps']=[json.loads(Path(row['path']).read_text()) for row in result['audit_sweeps']]
        return result, adapter, dataset, plan

    def test_success_sealed_selection_and_real_distinct_arms(self):
        r, backend, data, plan = self.run_case()
        self.assertEqual(r['status'], 'local-comparison-complete-PUBLIC-integration-pending', r.get('error'))
        self.assertEqual(r['dev_selection']['selected_arm'], 'B')
        self.assertEqual(data.opened, ['dev', 'holdout'])
        self.assertEqual(backend.predictions, 3*4*2)
        self.assertEqual(r['public']['score'], None)
        self.assertFalse(r['public']['production_admitted'])
        self.assertTrue(r['time_matching']['matched'])
        self.assertEqual(len({r['arms'][a]['adapter_sha256'] for a in ('A','B','C')}), 3)
        self.assertTrue(all(r['arms'][a]['reload']['reload_verified'] for a in ('A','B','C')))
        self.assertFalse(production_admission(plan)['production_admitted'])

    def test_zero_signal_preserves_A_B_predictions_and_cost(self):
        r, backend, data, _ = self.run_case('zero')
        self.assertTrue(r['arms']['B']['no_update'])
        self.assertEqual(r['arms']['B']['audit_status'], 'zero-signal')
        self.assertEqual(r['dev_selection']['selected_arm'], 'A')
        self.assertEqual(backend.update_calls, 0)
        self.assertGreater(r['time_matching']['B_seconds'], 10.)
        self.assertEqual(r['arms']['A']['adapter_sha256'], r['arms']['B']['adapter_sha256'])

    def test_incomplete_is_not_zero_and_not_reached_stays_null(self):
        r, b, _, _ = self.run_case('incomplete')
        self.assertEqual(r['arms']['B']['audit_status'], 'incomplete-audit')
        row = r['audit_sweeps'][0]['batch']['rows'][1]
        self.assertIsNone(row['trajectory']); self.assertIsNone(row['reward'])
        self.assertEqual(r['audit_sweeps'][0]['summary']['not_reached'], 1)
        self.assertIsNotNone(r['dev_selection'])
        self.assertEqual(b.update_calls, 0)

    def test_infrastructure_and_context_have_null_rewards(self):
        for branch in ('infrastructure', 'context'):
            with self.subTest(branch=branch):
                r, _, _, _ = self.run_case(branch)
                summary = r['audit_sweeps'][0]['summary']
                self.assertIsNone(summary['eligible_mean_reward'])
                self.assertEqual(summary['eligible_mean_denominator'], 0)
                self.assertEqual(summary['pass_at_8_coverage'], 0)
                self.assertEqual(r['arms']['B']['audit_status'], 'incomplete-audit')
                self.assertIsNotNone(r['holdout'])

    def test_partial_eligible_mixed_sweep_cannot_update(self):
        shape = FixtureShape(group_size=8, dev_cases=2, holdout_cases=2)
        r, backend, _, _ = self.run_case('one-infrastructure', shape=shape)
        self.assertEqual(r['audit_sweeps'][0]['summary']['mixed_groups'], 1)
        self.assertEqual(r['arms']['B']['audit_status'], 'incomplete-audit')
        self.assertEqual(backend.update_calls, 0)
        self.assertTrue(r['arms']['B']['no_update'])

    def test_numeric_nonadmission_still_evaluates(self):
        r, _, _, _ = self.run_case('numeric')
        self.assertTrue(r['arms']['B']['no_update'])
        self.assertEqual(r['arms']['B']['audit_status'], 'numeric-nonadmission-no-update')
        self.assertIsNotNone(r['holdout'])

    def test_recoverable_sampling_and_update_failures_cost_survives(self):
        for branch in ('sample-failure', 'update-failure'):
            with self.subTest(branch=branch):
                r, _, _, _ = self.run_case(branch)
                self.assertTrue(r['audit_sweeps'][0]['rollback_verified'])
                self.assertTrue(r['arms']['B']['no_update'])
                self.assertIn('restore', [e['phase'] for e in r['physical_events']])
                self.assertIsNotNone(r['holdout'])

    def test_later_incomplete_retains_first_committed_B(self):
        shape = FixtureShape(dev_cases=2, holdout_cases=2, max_sweeps=4, max_control_updates=50)
        r, backend, _, _ = self.run_case('later-incomplete', shape=shape)
        self.assertFalse(r['arms']['B']['no_update'])
        self.assertEqual(r['arms']['B']['updates']['rl_updates'], 1)
        self.assertEqual(len(r['audit_sweeps']), 4)
        self.assertEqual([e['status'] for e in r['audit_sweeps'][2:]], ['not-reached','not-reached'])
        self.assertIsNotNone(r['holdout'])

    def test_full_production_shaped_four_sweeps(self):
        shape = FixtureShape(anchor_updates=64, parents=32, group_size=8, dev_cases=16, holdout_cases=32, max_sweeps=4, max_control_updates=100)
        r, backend, _, _ = self.run_case(shape=shape)
        self.assertEqual(len(r['audit_sweeps']), 4)
        self.assertEqual(r['arms']['B']['updates']['rl_updates'], 4)
        self.assertEqual(backend.predictions, 288)
        self.assertTrue(all(a['summary']['planned_attempts'] == 256 for a in r['audit_sweeps']))
        self.assertTrue(all(a['summary']['pass_at_8_coverage'] == 32 for a in r['audit_sweeps']))

    def test_fatal_state_stops_without_control_or_eval(self):
        r, backend, data, _ = self.run_case('fatal')
        self.assertEqual(r['status'], 'stopped-incomplete')
        self.assertEqual(r['device_state'], 'fatal-or-unknown')
        self.assertEqual(backend.predictions, 0)
        self.assertEqual(data.opened, [])
        self.assertNotIn('C', r['arms'])

    def test_control_failure_is_unmatched_honestly_and_evaluates(self):
        r, _, _, _ = self.run_case('control-failure')
        self.assertFalse(r['time_matching']['matched'])
        self.assertEqual(r['arms']['C']['control_status'], 'recoverable-control-failure')
        self.assertIsNotNone(r['holdout'])

    def test_control_step_cap_does_not_idle_pad(self):
        r, _, _, _ = self.run_case(shape=FixtureShape(dev_cases=2, holdout_cases=2, max_control_updates=1))
        self.assertFalse(r['time_matching']['matched'])
        self.assertEqual(r['arms']['C']['control_status'], 'control-step-cap')
        self.assertFalse(r['time_matching']['idle_padding'])

    def test_incomplete_dev_never_opens_holdout(self):
        r, _, data, _ = self.run_case('dev-incomplete')
        self.assertEqual(r['status'], 'stopped-incomplete')
        self.assertEqual(data.opened, [])
        self.assertIsNone(r['dev_selection'])
        self.assertIsNone(r['holdout'])

    def test_hash_tampering_rejected_before_label_access(self):
        r, _, data, _ = self.run_case()
        payload = read_predictions(r['dev_seal'])
        path = Path(payload['methods']['A'][0]['generations'][0]['path'])
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'generation receipt changed'):
            read_predictions(r['dev_seal'])

    def test_explicit_source_inventory_ignores_unexecuted_new_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'scope').mkdir(); (root/'scope/a.py').write_text('x=1')
            freeze = SourceFreeze.capture(root, ('scope',))
            (root/'scope/unrelated.py').write_text('x=2')
            freeze.verify()
            (root/'scope/a.py').write_text('x=3')
            with self.assertRaisesRegex(ValueError, 'source drift'): freeze.verify()

    def test_source_closure_rejects_new_executed_import(self):
        import sys, types
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'scope').mkdir(); (root/'scope/a.py').write_text('x=1')
            freeze = SourceFreeze.capture(root, ('scope',))
            extra = root/'scope/b.py'; extra.write_text('x=2')
            module = types.ModuleType('controlled_new_import'); module.__file__ = str(extra)
            sys.modules[module.__name__] = module
            try:
                with self.assertRaisesRegex(ValueError, 'unlisted source'): freeze.close_imports()
            finally: del sys.modules[module.__name__]

    def test_reserve_nonadmission_preserves_empty_audit_and_evaluates(self):
        r, backend, data, _ = self.run_case(remaining=45.)
        self.assertTrue(r['arms']['B']['no_update'])
        self.assertEqual(r['arms']['B']['audit_status'], 'not-admitted')
        self.assertEqual(r['audit_sweeps'][0]['summary']['not_reached'], 2)
        self.assertEqual(len(backend.batches), 0)
        self.assertIsNotNone(r['holdout'])

    def test_no_update_prediction_drift_fails_before_holdout_labels(self):
        r, _, data, _ = self.run_case('no-update-drift')
        self.assertEqual(r['status'], 'stopped-incomplete')
        self.assertEqual(data.opened, ['dev'])
        self.assertIsNone(r['holdout'])

    def test_actual_phase_cap_overrun_stops(self):
        r, backend, data, _ = self.run_case(adapter_kwargs={'sweep_cost': 7201.})
        self.assertEqual(r['status'], 'stopped-incomplete')
        self.assertEqual(backend.predictions, 0)
        self.assertEqual(data.opened, [])

    def test_failed_device_closure_cannot_open_holdout(self):
        r, _, dataset, _ = self.run_case('bad-close')
        self.assertEqual(r['status'], 'stopped-incomplete')
        self.assertEqual(dataset.opened, ['dev'])
        self.assertIsNone(r['holdout'])

    def test_failed_cleanup_and_identity_still_persist_result(self):
        r, _, dataset, _ = self.run_case('close-failure')
        self.assertEqual(r['status'], 'stopped-incomplete')
        self.assertTrue(Path(r['result_artifact']).is_file())
        self.assertIn('identity_error', r)
        self.assertEqual(dataset.opened, ['dev'])

    def test_invalid_nonnull_prediction_and_wrong_identity_stop(self):
        for branch in ('invalid-grid','wrong-identity'):
            with self.subTest(branch=branch):
                r, _, dataset, _ = self.run_case(branch)
                self.assertEqual(r['status'], 'stopped-incomplete')
                self.assertEqual(dataset.opened, [])

    def test_owned_seal_cannot_be_rehashed_to_empty_generations(self):
        r, _, dataset, _ = self.run_case()
        seal = deepcopy(r['dev_seal'])
        payload = json.loads(Path(seal['path']).read_text())
        payload['methods']['A'][0]['generations'] = []
        Path(seal['path']).write_bytes(canonical(payload))
        import hashlib
        seal['file_sha256'] = hashlib.sha256(Path(seal['path']).read_bytes()).hexdigest()
        seal['payload_sha256'] = digest(payload)
        with self.assertRaisesRegex(ValueError, 'owned prediction seal'):
            dataset._authority.admit('dev', seal)

    def test_source_audit_blocks_transient_runpy_execution(self):
        from experiment_flow.contracts import SourceExecutionGuard
        import runpy
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'scope').mkdir(); (root/'scope/a.py').write_text('x=1')
            freeze = SourceFreeze.capture(root, ('scope',))
            guard = SourceExecutionGuard(freeze)
            try:
                runpy.run_path(str(root/'scope/a.py'))
                self.assertTrue(freeze.close_imports(guard)['execution_history_closure_verified'])
                (root/'scope/b.py').write_text('x=2')
                with self.assertRaisesRegex(ValueError, 'unlisted or changed local source'):
                    runpy.run_path(str(root/'scope/b.py'))
            finally: guard.stop()

    def test_metering_rejects_reversed_and_unsettled_intervals(self):
        from experiment_flow.metering import close_metering
        for entry in ({'started': 2.,'ended': 1.,'seconds': 1.,'status': 'complete'},
                      {'started': 1.,'ended': 2.,'seconds': 1.,'status': 'unclosed-device-error'}):
            with self.assertRaises(ValueError):
                close_metering([{'event_id': 0,'phase': 'test','dispatched': True,**entry}], [])

    def test_nan_forecast_rejected(self):
        with self.assertRaisesRegex(ValueError, 'finite'):
            Forecast('f'*64, 'controlled-fixture', 1., float('nan'), 2., 2., 10., 10., 2., 2.)

    def test_fabricated_reward_for_unattempted_slot_rejected(self):
        batch = {'planned_attempts': 1, 'rows': [{'parent_id': 'p', 'slot': 0, 'eligible': False,
                 'reward': 0, 'trajectory': None, 'status': 'not-reached'}]}
        with self.assertRaises(ValueError): summarize(batch, ('p',), 1)

if __name__ == '__main__': unittest.main(verbosity=2)

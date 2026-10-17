"""E13 shared-training closure and publication boundaries; no native/provider work."""
from tests.platform_requirements import requires_linux
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import nvarc_e13_admission as owner
from tools import nvarc_e13_delivery_envelope as delivery
from tools import nvarc_e13_output_lifecycle as lifecycle


def _load_linux_runtime():
    global cleanup
    from tools import nvarc_e13_cleanup as cleanup

def inert_plan():
    raw = (Path(__file__).parent / 'fixtures/e12/frozen-inert-001-plan.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'f8000ab7db2a40795e93ff7482ad17ffa7fc817057207da7a9aadd6266739349'
    plan = delivery.parse(raw)
    plan.update(run_id=owner.RUN_ID, screen_id=owner.RUN_ID, source_commit='a' * 40,
        format='irisx/stage4-e13-search-budget-v1', generation_budget_profile='native-paired-search-budget-v12',
        expected_notebook_version=12, expected_previous_version=11,
        optimizer_steps=512, maximum_training_forwards=512, maximum_training_backwards=512,
        per_worker_training_steps=128, kernel_execution_type='INERT', owner_editor_only=True,
        resource_budget_profile=owner.BUDGET_PROFILE, resource_admission=None,
        **{key: False for key in owner.FALSE_FIELDS})
    plan['e13_process_policy'] = plan.pop('e12_process_policy')
    plan['arm_contracts'] = {arm: dict(arm_id=arm, training_updates=0, shared_training_updates=128,
        generation_seconds=seconds, schedule='interleaved', dfs_probability_floor=.2)
        for arm, seconds in (('search120', 120), ('search240', 240))}
    plan['arm_order'] = {key: list(delivery.ARMS) if index % 2 == 0 else list(reversed(delivery.ARMS))
        for index, key in enumerate(delivery.TASKS)}
    plan['owner_editor_admission'] = owner.admission(plan)
    return plan


class SharedTrainingClosureTests(unittest.TestCase):
    def setUp(self):
        self.plan = inert_plan()
        self.prefix = 'workers/0/'
        bound = dict(probe_id=delivery.RUN_ID, rank=0)
        self.proof = dict(terminal=dict(outcome='failed'), launches={'0': {'binding': bound}})
        result = dict(binding=bound, outcome='complete', completed_training_updates=128,
            shared_training_verified=True, paired_rng_restored=True,
            training={'training_updates': 128}, post_training_rng={'rng': 'observation'},
            arms={arm: {'arm_id': arm} for arm in delivery.ARMS})
        self.files = {self.prefix + 'result.json': result}
        self.files.update({self.prefix + 'training/' + name: {} for name in delivery.TRAINING_FILES})
        self.files.update({self.prefix + 'arms/' + arm + '/' + name: {}
            for arm in delivery.ARMS for name in delivery.ARM_FILES})
        self.files[self.prefix + 'training/training-receipt.json'] = copy.deepcopy(result['training'])
        self.files[self.prefix + 'training/post-training-rng.json'] = copy.deepcopy(result['post_training_rng'])
        for arm in delivery.ARMS:
            self.files[self.prefix + 'arms/' + arm + '/arm-receipt.json'] = copy.deepcopy(result['arms'][arm])

    def verify(self):
        delivery.validate_completed_workers(self.files, self.files.__getitem__, self.proof)

    def test_single_training_inventory_and_matching_receipts_close_without_native_import(self):
        self.verify()
        for name in self.files:
            self.assertEqual(delivery.member_kind(name, self.plan), 'runtime')
        self.assertFalse(delivery.TRAINING_FILES & delivery.ARM_FILES)

    def test_training_artifacts_and_old_arms_are_rejected_from_search_directories(self):
        for name in delivery.TRAINING_FILES:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unrecognized'):
                delivery.member_kind(self.prefix + 'arms/search120/' + name, self.plan)
        for name in ('arms/ttt128/arm-receipt.json', 'arms/ttt64/prefix-trace.json',
                     'training/answer-checkpoint.json', 'training/nested/prefix-trace.json'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unrecognized'):
                delivery.member_kind(self.prefix + name, self.plan)

    def test_every_training_and_inference_member_is_required_for_complete_claim(self):
        for name in sorted(set(self.files) - {self.prefix + 'result.json'}):
            value = self.files.pop(name)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'evidence inventories'):
                self.verify()
            self.files[name] = value

    def test_failed_worker_does_not_fabricate_complete_training(self):
        self.files = {self.prefix + 'result.json': dict(outcome='failed')}
        self.verify()

    def test_shared_training_flags_and_count_are_literal_not_truthy(self):
        result = self.files[self.prefix + 'result.json']
        for key, wrong in (('completed_training_updates', 256), ('completed_training_updates', 128.),
                ('shared_training_verified', 1), ('paired_rng_restored', 1), ('training', []),
                ('post_training_rng', None), ('arms', {'search120': {}})):
            old = result[key]; result[key] = wrong
            with self.subTest(key=key, value=wrong), self.assertRaisesRegex(ValueError, 'single128'):
                self.verify()
            result[key] = old

    def test_claimed_shared_state_and_arm_receipts_must_equal_retained_projections(self):
        for leaf in ('training/training-receipt.json', 'training/post-training-rng.json',
                     'arms/search120/arm-receipt.json', 'arms/search240/arm-receipt.json'):
            name = self.prefix + leaf; old = self.files[name]; self.files[name] = {'foreign': True}
            with self.subTest(name=leaf), self.assertRaisesRegex(ValueError, 'projections differ'):
                self.verify()
            self.files[name] = old

    def test_admission_projection_matches_trusted_admission_without_importing_it(self):
        for key in ('RUN_ID', 'BUDGET_PROFILE', 'RUN_BUDGET_PROFILE', 'RUN_START_FILE',
                'AUTHORIZATION_REF', 'CONSERVATIVE_POLICY', 'WAIVER_POLICY', 'CONFIG_NAME',
                'CONFIRMATION_FILE', 'FALSE_FIELDS', 'SCOPE_FIELDS', 'RUN_TRUE_FIELDS'):
            self.assertEqual(getattr(owner, key), getattr(delivery, key), key)
        self.assertEqual(delivery.scope(self.plan), owner.scope(self.plan))
        self.assertEqual(delivery.admission(self.plan), owner.admission(self.plan))
        delivery.validate_plan(self.plan, owner.RUN_ID)
        for module in (delivery, owner):
            tree = ast.parse(Path(module.__file__).read_text())
            if module is owner: owner_tree = tree
            else: delivery_tree = tree
        for name in ('scope', 'admission', 'run_admission', 'run_start_fields', 'verify_start_value',
                     'validate_resource_snapshot', 'is_run', '_timestamp'):
            expected = next(n for n in owner_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            observed = next(n for n in delivery_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            if name == 'run_start_fields':
                for node in ast.walk(expected):
                    if isinstance(node, ast.Name) and node.id == 'validate_plan':
                        node.id = 'validate_execution_admission'
            self.assertEqual(ast.dump(expected), ast.dump(observed), name)


@requires_linux('Shared GenerationStore fixture requires mandatory O_NOFOLLOW/O_NONBLOCK plan reads')
class E13OutputGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.plan = inert_plan()
        raw = owner.canonical(self.plan)
        (self.root / 'screen.json').write_bytes(raw); (self.root / 'plan.json').write_bytes(raw)
        owner.write_confirmation(self.root, self.plan, True, time.monotonic())
        self.bindings = dict(run_id=owner.RUN_ID, plan_digest=owner.digest(self.plan),
            challenges_digest=self.plan['challenges_digest'])
        self.store = lifecycle.GenerationStore(self.root, 'e13-search-budget-pilot', self.bindings)
        self.values = {name: {'synthetic': name} for name in lifecycle.SETS[self.store.kind]}

    def test_exact_eight_search_outputs_preserve_unknown_exit_and_no_promotion(self):
        manifest = self.store.publish(self.values, evidence_qualified=True)
        self.assertEqual(len(manifest['members']), 8)
        self.assertEqual(self.store.verify_projection(), manifest)
        self.assertEqual(manifest['outcomes'], dict(output_valid=True, notebook_exit='unknown',
            evidence_qualified=True, promotion=False))
        self.assertFalse((self.root / 'submission.json').exists())
        self.assertFalse(any(p.name.startswith('ttt') for p in self.root.iterdir()))

    def test_historical_output_kind_and_cross_run_bindings_cannot_be_admitted(self):
        for kind, bindings in [('e12-prefix-pilot', self.bindings),
                ('e13-search-budget-pilot', dict(self.bindings, run_id='stage4-e12-probe-prefix-20261008-003')),
                ('e13-search-budget-pilot', dict(self.bindings, plan_digest='sha256:' + '0' * 64))]:
            with self.subTest(kind=kind, bindings=bindings), self.assertRaises(RuntimeError):
                lifecycle.GenerationStore(self.root, kind, bindings)

    def test_wrong_file_set_never_creates_output_commit(self):
        for extra in ('ttt128-answers.json', 'submission.json', 'search120-training.json'):
            with self.subTest(extra=extra), self.assertRaisesRegex(RuntimeError, 'closed output'):
                self.store.publish(dict(self.values, **{extra: {}}))
        self.assertFalse((self.root / 'output-commit.json').exists())

    def test_precommit_failure_preserves_old_generation(self):
        original = self.store.publish(self.values)
        def fail(stage, path):
            if stage == 'before-commit': raise InterruptedError('synthetic precommit')
        self.store.observe = fail
        with self.assertRaises(InterruptedError): self.store.publish(self.values)
        self.assertEqual(self.store.read()[0], original)
        self.assertEqual(self.store.verify_projection(), original)
        self.assertFalse((self.root / '.output-writer.lock').exists())

    def test_committed_partial_projection_recovers_only_after_semantic_validation(self):
        self.store.publish(self.values)
        def fail(stage, path):
            if stage == 'before-projection': raise InterruptedError('synthetic projection')
        self.store.observe = fail
        changed = {name: {'new': True} for name in self.values}
        with self.assertRaises(InterruptedError): self.store.publish(changed)
        current = self.store.read()[0]
        with self.assertRaisesRegex(RuntimeError, 'marker differs'): self.store.verify_projection()
        self.store.observe = lambda *_: None
        with self.assertRaisesRegex(ValueError, 'semantic rejection'):
            self.store.recover(lambda *_: (_ for _ in ()).throw(ValueError('semantic rejection')))
        with self.assertRaisesRegex(RuntimeError, 'marker differs'): self.store.verify_projection()
        seen = []
        self.store.recover(lambda manifest, values: seen.append((manifest, values)))
        self.assertEqual(seen, [(current, changed)])
        self.assertEqual(self.store.verify_projection(), current)

    def test_corrupt_generation_cannot_fall_back_to_old_or_republish(self):
        first = self.store.publish(self.values); second = self.store.publish(self.values)
        self.assertNotEqual(first['generation'], second['generation'])
        (self.root / '.output-generations' / second['generation'] / 'search240-audit.json').write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError, 'hash differs'): self.store.read()
        with self.assertRaisesRegex(RuntimeError, 'hash differs'): self.store.publish(self.values)


@requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
class E13CleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_linux_runtime()

    def test_shutdown_cutoffs_are_unchanged_and_e13_receipts_distinct(self):
        self.assertEqual((cleanup.TERM_SECONDS, cleanup.KILL_SECONDS, cleanup.STOP_SECONDS,
                          cleanup.FINAL_SECONDS), (3290, 3299.8, 3300, 3600))
        with tempfile.TemporaryDirectory() as tmp:
            result = cleanup.prelaunch_failure(Path(tmp) / 'capture.log', started=100.,
                error=RuntimeError('synthetic startup failure'), now=lambda: 200.)
        self.assertIn('e13_supervision', result); self.assertNotIn('e12_supervision', result)
        self.assertEqual(result['e13_supervision']['format'], 'irisx/e13-supervision-v1')
        self.assertFalse(result['launch_attempted']); self.assertFalse(result['reserve_preserved'])

    def test_all_workers_receive_collective_kill_before_any_poll(self):
        events = []; resources = []; streams = []
        for rank in range(4):
            pid = 80000 + rank
            def poll(pid=pid):
                self.assertEqual(sum(kind == 'signal' for kind, _ in events), 4)
                events.append(('poll', pid)); return -9
            stream = io.StringIO(); streams.append(stream)
            resources.append(dict(identity=rank, process=SimpleNamespace(pid=pid, poll=poll),
                streams={'stdout': stream}))
        result = cleanup.cleanup_workers(resources, deadline_monotonic=10., now=lambda: 1.,
            signal_group=lambda pid, sig: events.append(('signal', pid)), group_exists=lambda _: False)
        self.assertEqual(result['format'], 'irisx/e13-collective-cleanup-v1')
        self.assertTrue(result['complete_before_deadline']); self.assertTrue(all(s.closed for s in streams))
        self.assertEqual([r['identity'] for r in result['workers']], ['0', '1', '2', '3'])

    def test_exited_leader_with_live_group_is_unconfirmed_and_no_drain_runs(self):
        drained = []; primary = RuntimeError('original failure')
        result = cleanup.cleanup_workers([dict(identity=0, process=SimpleNamespace(pid=80000, poll=lambda: -9))],
            primary=primary, drains=[('tail', lambda: drained.append(True))], deadline_monotonic=1.,
            now=lambda: 1., signal_group=lambda *_: None, group_exists=lambda _: True)
        self.assertFalse(result['all_producers_stopped']); self.assertTrue(result['timed_out'])
        self.assertEqual(drained, []); self.assertIs(primary.cleanup_report, result)

    def test_unsafe_process_ids_fail_before_signal(self):
        for pid in (1, os.getpid(), os.getpgrp(), True):
            with self.subTest(pid=pid), self.assertRaisesRegex(ValueError, 'unique positive'):
                cleanup.cleanup_workers([dict(identity=0, process=SimpleNamespace(pid=pid))],
                    deadline_monotonic=1., signal_group=lambda *_: self.fail('no signal before validation'))


if __name__ == '__main__': unittest.main()

"""Bounded tiny-random CPU neural evidence; no production/GPU efficacy claim."""
import copy
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.arc_learning_agent_20261011.stability import canary_decision
from tools.arc_learning_agent_20261011.tests import test_training_neural as _fixture_module


class CanaryDecisionTests(unittest.TestCase):
    def rows(self, a=2.0, b=20.0):
        return [{'sample_id': 'a', 'nll_sum': a, 'token_count': 1, 'valid': True},
                {'sample_id': 'b', 'nll_sum': b, 'token_count': 10, 'valid': True}]

    def decide(self, candidate, complete=True):
        return canary_decision(self.rows(), candidate, expected_ids=['a', 'b'], comparison_complete=complete)

    def test_loss_sum_weighting_and_deterministic_order(self):
        accepted = self.decide(self.rows(3, 17))
        self.assertTrue(accepted['accepted'])
        self.assertEqual(accepted['baseline_mean_nll'], 2.0)
        self.assertEqual(accepted, self.decide(list(reversed(self.rows(3, 17)))))
        self.assertFalse(self.decide(self.rows())['accepted'])
        self.assertFalse(self.decide(self.rows(10, 80))['stable'])

    def test_missing_invalid_duplicate_mismatched_tokens_never_select(self):
        candidates = [self.rows()[:1], [self.rows()[0]] * 2, self.rows(float('nan')), self.rows(float('inf'))]
        changed = self.rows(); changed[1]['token_count'] += 1; candidates.append(changed)
        for rows in candidates:
            result = self.decide(rows)
            self.assertFalse(result['comparison_complete'])
            self.assertFalse(result['accepted'])
        self.assertFalse(self.decide(self.rows(1, 10), False)['comparison_complete'])


@unittest.skipUnless(os.environ.get('ARC_LEARNING_NEURAL_TESTS') == '1', 'explicit tiny CPU neural tests only')
class StableTrainingNeuralTests(unittest.TestCase):
    setUpClass = classmethod(_fixture_module.TrainingNeuralTests.setUpClass.__func__)

    def make(self, **overrides):
        return _fixture_module.TrainingNeuralTests.make_trainer(self, **{
            'stability_mode': True, 'schedule_steps': 12, 'warmup_steps': 2,
            'accumulation_target_tokens': 1000, 'accumulation_max_microbatches': 2, **overrides})

    def run_microbatches(self, trainer, count, **kwargs):
        return trainer.train(self.records, max_steps=count, deadline=time.monotonic() + 90, **kwargs)

    def state_hash(self, trainer, value):
        from tools.arc_learning_agent_20261011.training import _fingerprint_tree
        return _fingerprint_tree(value, trainer.torch)

    def test_weighted_accumulation_equals_actual_token_sum_gradient(self):
        train, reference = self.make(), self.make()
        for trainer in (train, reference):
            for layer in trainer.model.modules():
                if hasattr(layer, 'attention_dropout'):
                    layer.attention_dropout = 0.0
        rows = [train._prepared(record) for record in self.records]
        first = rows[0]
        second = next(row for row in rows if row['supervised_tokens'] != first['supervised_tokens'])
        rows = [first, second]
        sums = [train._accumulate(row)['loss_sum'] for row in rows]
        reference.model.train()
        total = sum(row['supervised_tokens'] for row in rows)
        losses = []
        for row in rows:
            ids = self.torch.tensor([row['input_ids']])
            labels = self.torch.tensor([row['labels']])
            output = reference.model(input_ids=ids, attention_mask=self.torch.ones_like(ids), use_cache=False)
            losses.append(self.torch.nn.functional.cross_entropy(output.logits[:, :-1, :].float().reshape(-1, 130),
                          labels[:, 1:].reshape(-1), ignore_index=-100, reduction='sum'))
        (sum(losses) / total).backward()
        for name, parameter in train.parameters.items():
            self.assertTrue(self.torch.allclose(parameter.grad / total, reference.parameters[name].grad, atol=2e-7, rtol=2e-5), name)
        self.assertAlmostEqual(sum(sums) / total, float(sum(losses).detach()) / total, places=6)
        self.assertNotAlmostEqual(sum(sums) / total, sum(s / r['supervised_tokens'] for s, r in zip(sums, rows)) / 2, places=6)

    def test_physical_ceiling_counts_and_warmup_decay(self):
        trainer = self.make()
        result = self.run_microbatches(trainer, 5)
        self.assertEqual(result['status'], 'complete', result)
        self.assertEqual(result['attempted_microbatches'], 5)
        self.assertEqual(result['completed_microbatches'], 5)
        self.assertEqual(result['optimizer_steps'], 3)
        self.assertEqual([r['microbatches'] for r in result['updates']], [2, 2, 1])
        self.assertEqual(result['optimizer_diagnostics']['moments']['exp_avg']['dtypes'], ['torch.float32'])
        self.assertTrue(result['optimizer_diagnostics']['moments']['exp_avg_sq']['finite'])
        self.assertEqual(result['updates'][0]['learning_rate'], trainer.config['learning_rate'] / 2)
        self.assertEqual(result['updates'][1]['learning_rate'], trainer.config['learning_rate'])
        second = self.run_microbatches(trainer, 4)
        self.assertLess(second['updates'][-1]['learning_rate'], second['updates'][0]['learning_rate'])
        self.assertTrue(all(p.grad is None for p in trainer.parameters.values()))

    def test_short_stable_task_uses_independent_schedule_and_physical_ceiling(self):
        trainer = self.make(warmup_steps=32, schedule_steps=128, accumulation_max_microbatches=8)
        self.assertEqual(trainer.config['task_warmup_steps'], 1)
        self.assertEqual(trainer.config['task_schedule_steps'], 16)
        global_result = self.run_microbatches(trainer, 8)
        self.assertEqual(global_result['updates'][0]['learning_rate'], trainer.config['learning_rate'] / 32)
        trainer.freeze_global()
        for task, microbatches in (('A', 8), ('B', 16)):
            result = trainer.adapt_task(task, self.tasks['a']['train'], max_steps=microbatches,
                                        deadline=time.monotonic() + 90)
            self.assertEqual(result['status'], 'complete', result)
            self.assertEqual(result['attempted_microbatches'], microbatches)
            self.assertEqual(result['optimizer_steps'], microbatches // 8)
            self.assertEqual(result['updates'][0]['learning_rate'], trainer.config['task_learning_rate'])
            self.assertEqual(result['updates'][0]['adam_step'], 1)
            self.assertEqual(result['accumulation']['scheduler_unit'], 'optimizer_updates')
            trainer.end_task()

    def test_stable_task_reset_matches_fresh_task_optimizer_scheduler_rng(self):
        config = {'warmup_steps': 32, 'schedule_steps': 128,
                  'task_warmup_steps': 2, 'task_schedule_steps': 6}
        sequential, fresh = self.make(**config), self.make(**config)
        for trainer in (sequential, fresh):
            self.run_microbatches(trainer, 2)
            trainer.freeze_global()
        sequential.adapt_task('A', self.tasks['a']['train'], max_steps=6, deadline=time.monotonic() + 90)
        sequential.end_task()
        actual = sequential.adapt_task('B', self.tasks['b']['train'], max_steps=6, deadline=time.monotonic() + 90)
        expected = fresh.adapt_task('B', self.tasks['b']['train'], max_steps=6, deadline=time.monotonic() + 90)
        self.assertEqual(actual['attempted_microbatches'], 6)
        self.assertEqual(actual['optimizer_steps'], 3)
        self.assertEqual(actual['updates'][0]['learning_rate'], sequential.config['task_learning_rate'] / 2)
        for key in ('adapter_after_sha256', 'optimizer_state_sha256', 'scheduler_state_sha256', 'rng_sha256', 'cursor', 'losses'):
            self.assertEqual(actual[key], expected[key], key)
        sequential.end_task(); fresh.end_task()

    def test_task_schedule_configuration_validates_and_legacy_ignores_it(self):
        for changes in ({'task_warmup_steps': 0}, {'task_warmup_steps': True},
                        {'task_schedule_steps': 1}, {'task_schedule_steps': 1.5},
                        {'task_warmup_steps': 17}):
            with self.assertRaises(ValueError): self.make(**changes)
        legacy = _fixture_module.TrainingNeuralTests.make_trainer(self, warmup_steps=32, schedule_steps=128,
                                                                task_warmup_steps=8, task_schedule_steps=16)
        legacy.freeze_global()
        legacy.adapt_task('legacy', self.tasks['a']['train'], max_steps=0, deadline=time.monotonic() + 90)
        rates = []
        original = legacy.optimizer.step
        def observed_step(*args, **kwargs):
            rates.append(legacy.optimizer.param_groups[0]['lr'])
            return original(*args, **kwargs)
        legacy.optimizer.step = observed_step
        result = legacy.adapt_task('legacy', self.tasks['a']['train'], max_steps=3, deadline=time.monotonic() + 90)
        self.assertEqual(result['optimizer_steps'], 3)
        self.assertEqual(rates, [legacy.config['task_learning_rate']] * 3)
        legacy.end_task()

    def test_token_threshold_not_only_microbatch_count(self):
        trainer = _fixture_module.TrainingNeuralTests.make_trainer(self, stability_mode=True, schedule_steps=12, warmup_steps=2,
                                       accumulation_target_tokens=1, accumulation_max_microbatches=8)
        result = self.run_microbatches(trainer, 3)
        self.assertEqual(result['optimizer_steps'], 3)
        self.assertEqual([r['microbatches'] for r in result['updates']], [1, 1, 1])

    def test_complete_rollback_matches_uninterrupted_optimizer_rng_cursor(self):
        uninterrupted = self.make()
        full = self.run_microbatches(uninterrupted, 6)
        resumed = self.make()
        base = resumed.snapshot_training_state('base')
        self.run_microbatches(resumed, 2)
        best = resumed.snapshot_training_state('best')
        best_payload = copy.deepcopy(resumed._training_snapshots[best['snapshot_id']]['payload'])
        self.run_microbatches(resumed, 2)
        final = resumed.snapshot_training_state('final')
        self.assertNotEqual(best['state_sha256'], final['state_sha256'])
        self.assertEqual(best_payload['run_state'], resumed._training_snapshots[best['snapshot_id']]['payload']['run_state'])
        restored = resumed.restore_training_state(best)
        self.assertTrue(restored['physical_ledger_untouched'])
        result = self.run_microbatches(resumed, 4)
        for key in ('adapter_after_sha256', 'optimizer_state_sha256', 'scheduler_state_sha256', 'rng_sha256', 'cursor'):
            self.assertEqual(full[key], result[key], key)
        self.assertEqual(uninterrupted._run_state, resumed._run_state)
        self.assertEqual(uninterrupted._optimizer_serial, resumed._optimizer_serial)
        resumed.restore_training_state(base)
        self.assertIsNone(resumed.optimizer)
        self.assertIsNone(resumed._run_state)
        self.assertEqual(resumed.fingerprint(), base['fingerprint'])

    def test_rollback_never_refunds_metered_physical_work(self):
        from tools.arc_learning_agent_20261011.budget import WorkLedger, DEFAULT_CAPS
        from tools.arc_learning_agent_20261011.metering import MeteredTrainer
        with tempfile.TemporaryDirectory() as tmp:
            raw = self.make()
            ledger = WorkLedger(Path(tmp) / 'ledger', caps={**DEFAULT_CAPS, 'training_steps': 5})
            trainer = MeteredTrainer(raw, ledger, max_sequence_tokens=1024)
            base = trainer.snapshot_training_state('base')
            result = trainer.train(self.records, max_steps=4, deadline=time.monotonic() + 90)
            self.assertEqual(result['optimizer_steps'], 2)
            before = copy.deepcopy(ledger.used)
            trainer.restore_training_state(base)
            self.assertEqual(ledger.used, before)
            result = trainer.train(self.records, max_steps=4, deadline=time.monotonic() + 90)
            self.assertEqual(result['attempted_microbatches'], 1)
            self.assertEqual(result['admitted_steps'], 1)
            self.assertEqual(ledger.used['training_steps'], 5)
            self.assertEqual(trainer.completed_optimizer_steps, 3)

    def test_nonfinite_partial_accumulation_is_charged_cleaned_and_blocked(self):
        trainer = self.make()
        base = trainer.snapshot_training_state('base')
        original = trainer._accumulate
        calls = []
        def inject(row):
            calls.append(1)
            if len(calls) == 2:
                raise ValueError('nonfinite training loss injected after one real backward')
            return original(row)
        trainer._accumulate = inject
        result = self.run_microbatches(trainer, 5)
        self.assertEqual(result['status'], 'failed_update')
        self.assertEqual(result['attempted_microbatches'], 2)
        self.assertEqual(result['optimizer_steps'], 0)
        self.assertTrue(all(p.grad is None for p in trainer.parameters.values()))
        with self.assertRaises(ValueError): trainer.snapshot_training_state('invalid')
        with self.assertRaises(ValueError): self.run_microbatches(trainer, 1)
        trainer.restore_training_state(base)
        self.assertEqual(trainer.fingerprint(), base['fingerprint'])

    def test_expired_deadline_does_no_forward_or_late_partial_update(self):
        trainer = self.make()
        first = trainer.train(self.records, max_steps=3, deadline=time.monotonic() - 1)
        self.assertEqual(first['attempted_microbatches'], 0)
        self.assertEqual(first['status'], 'deadline')
        now = [100.0]
        original = trainer._accumulate
        def expire(row):
            result = original(row)
            now[0] = 102.0
            return result
        trainer._accumulate = expire
        with patch('tools.arc_learning_agent_20261011.training.time.monotonic', side_effect=lambda: now[0]):
            result = trainer.train(self.records, max_steps=3, deadline=101.0)
        self.assertEqual(result['status'], 'failed_update', result)
        self.assertEqual(result['attempted_microbatches'], 1)
        self.assertEqual(result['optimizer_steps'], 0)
        self.assertTrue(all(p.grad is None for p in trainer.parameters.values()))

    def test_real_finite_loss_regression_canary_rejects_and_restores(self):
        trainer = self.make()
        self.run_microbatches(trainer, 2)
        best = trainer.snapshot_training_state('best')
        record = next(row for row in self.records if row['split'] == 'train')
        def score():
            result = trainer.native.score_completion(record['messages'], record['completion'], deadline=time.monotonic() + 30)
            self.assertTrue(result['valid'], result)
            return [{**result, 'sample_id': 'fixed-train-canary'}]
        baseline = score()
        self.run_microbatches(trainer, 2)
        def corrupt(_module, _inputs, output):
            output = output.clone()
            output[..., 129] += 30.0
            return output
        hook = trainer.model.get_output_embeddings().register_forward_hook(corrupt)
        try:
            candidate = score()
        finally:
            hook.remove()
        decision = canary_decision(baseline, candidate, expected_ids=['fixed-train-canary'], comparison_complete=True)
        self.assertTrue(decision['comparison_complete'])
        self.assertFalse(decision['stable'])
        self.assertFalse(decision['accepted'])
        trainer.restore_training_state(best)
        self.assertEqual(trainer.fingerprint(), best['fingerprint'])

    def test_stable_disk_restart_captures_microbatch_counters(self):
        full = self.make(); expected = self.run_microbatches(full, 6)
        with tempfile.TemporaryDirectory() as tmp:
            first = self.make(); partial = self.run_microbatches(first, 2, checkpoint_dir=tmp)
            resumed = self.make(); actual = self.run_microbatches(resumed, 4, resume=partial['checkpoints'][-1]['path'])
            for key in ('adapter_after_sha256', 'optimizer_state_sha256', 'scheduler_state_sha256', 'rng_sha256', 'cursor'):
                self.assertEqual(expected[key], actual[key], key)
            self.assertEqual(resumed._run_state, full._run_state)

    def test_scaler_capture_gradient_boundary_and_explicit_release(self):
        trainer = self.make()
        trainer.scaler = self.torch.amp.GradScaler('cpu')
        trainer.scaler.scale(self.torch.tensor(1.0, requires_grad=True))
        saved = trainer.snapshot_training_state('with-scaler')
        original_scale = trainer.scaler.get_scale()
        trainer.scaler.update(new_scale=128.0)
        trainer.restore_training_state(saved)
        self.assertEqual(trainer.scaler.get_scale(), original_scale)
        parameter = next(iter(trainer.parameters.values()))
        parameter.grad = self.torch.ones_like(parameter)
        with self.assertRaises(ValueError): trainer.snapshot_training_state('partial')
        trainer.model.zero_grad(set_to_none=True)
        trainer.release_training_state(saved)
        self.assertTrue(trainer.release_training_state(copy.deepcopy(saved))['already_released'])
        with self.assertRaises(ValueError): trainer.restore_training_state(saved)
        bad = {**saved, 'label': 'forged'}
        with self.assertRaises(ValueError): trainer.release_training_state(bad)
        adapter = trainer.snapshot('adapter')
        self.assertFalse(trainer.release_snapshot(adapter)['already_released'])
        self.assertTrue(trainer.release_snapshot(copy.deepcopy(adapter))['already_released'])
        with self.assertRaises(ValueError): trainer.release_snapshot({**adapter, 'label': 'forged'})
        with self.assertRaises(ValueError): trainer.restore(adapter)

    def test_clipping_is_applied_before_real_adam_update(self):
        trainer = self.make(max_grad_norm=0.00001)
        self.run_microbatches(trainer, 0)
        original = trainer.optimizer.step
        norms = []
        def inspect(*args, **kwargs):
            norms.append(float(self.torch.linalg.vector_norm(self.torch.cat([p.grad.flatten() for p in trainer.parameters.values()]))))
            return original(*args, **kwargs)
        trainer.optimizer.step = inspect
        result = self.run_microbatches(trainer, 2)
        self.assertEqual(result['optimizer_steps'], 1)
        self.assertEqual(len(norms), 1)
        self.assertLessEqual(norms[0], 0.000010001)
        self.assertGreater(result['updates'][0]['gradient_norm'], norms[0])

    def test_bad_preparation_mid_accumulation_cleans_without_checkpoint(self):
        trainer = self.make()
        original = trainer._prepared
        calls = []
        def fail_second(record):
            calls.append(1)
            if len(calls) == 2:
                raise ValueError('mask validation deliberately failed')
            return original(record)
        trainer._prepared = fail_second
        result = self.run_microbatches(trainer, 3)
        self.assertEqual(result['status'], 'failed_update')
        self.assertEqual(result['attempted_microbatches'], 1)
        self.assertTrue(all(p.grad is None for p in trainer.parameters.values()))
        with self.assertRaises(ValueError): trainer.snapshot_training_state('invalid')

    def test_partial_optimizer_failure_requires_complete_restore(self):
        trainer = self.make()
        self.run_microbatches(trainer, 2)
        best = trainer.snapshot_training_state('best')
        original = trainer.optimizer.step
        def mutate_then_fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('injected failure after Adam mutation')
        trainer.optimizer.step = mutate_then_fail
        result = self.run_microbatches(trainer, 2)
        self.assertEqual(result['status'], 'failed_update')
        self.assertEqual(result['attempted_microbatches'], 2)
        self.assertEqual(result['optimizer_steps'], 1)
        self.assertTrue(all(p.grad is None for p in trainer.parameters.values()))
        trainer.restore_training_state(best)
        self.assertEqual(trainer.fingerprint(), best['fingerprint'])
        self.assertEqual(self.state_hash(trainer, trainer.optimizer.state_dict()),
                         self.state_hash(trainer, trainer._training_snapshots[best['snapshot_id']]['payload']['optimizer']))


if __name__ == '__main__':
    unittest.main()

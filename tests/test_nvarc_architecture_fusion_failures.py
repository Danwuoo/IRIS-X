"""Real CPU fusion state isolation and failure regression tests.

Scripted token selections exercise the existing reward routes, never replace
behavior probabilities. Models, AF3 graphs, gradients and AdamW steps are real.
Injected replay/optimizer faults must fail closed. These tiny synthetic checks
do not establish official-weight feasibility or held-out training gains.
"""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.test_nvarc_architecture_fusion import MISSING, config, engine

if not MISSING:
    import torch
    from tests.test_nvarc_matched_controls import scripted_groups
    from tests.test_nvarc_matched_workflow import corpus
    from tools.arc2_goal_sprint_20261017.model import adapter_state, make_optimizer
    from tools.nvarc_efficient_fusion_20261018 import contracts, panels, training
    from tools.nvarc_posttrain_20261017 import matched_controls as mc
    from tools.nvarc_posttrain_20261017.engine import FatalUpdateError


EXPANDED = ('depth32', 'moe4_top2', 'width8192')


@unittest.skipIf(bool(MISSING), 'Optional actual-ML dependencies absent: ' + ','.join(MISSING))
class ArchitectureFusionFailuresCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.temp = tempfile.TemporaryDirectory()
        args = corpus(Path(cls.temp.name))
        cls.prepared = panels.prepare_panels(*args[:4], **args[4], train_count=3, dev_count=2)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def assert_nested_exact(self, actual, expected):
        """Compare every tensor, including AdamW moments and step counters."""
        if isinstance(expected, torch.Tensor):
            self.assertEqual(actual.dtype, expected.dtype)
            self.assertEqual(actual.shape, expected.shape)
            self.assertTrue(torch.equal(actual, expected))
        elif isinstance(expected, dict):
            self.assertEqual(set(actual), set(expected))
            for key in expected:
                self.assert_nested_exact(actual[key], expected[key])
        elif isinstance(expected, (list, tuple)):
            self.assertEqual(len(actual), len(expected))
            for value, wanted in zip(actual, expected):
                self.assert_nested_exact(value, wanted)
        else:
            self.assertEqual(actual, expected)

    def test_interleaved_arms_match_uninterrupted_parameters_and_adamw_states(self):
        for kind in EXPANDED:
            with self.subTest(architecture=kind):
                current = engine(kind)
                optimizers, groups = [], {}

                def capture_optimizer(*args, **kwargs):
                    optimizer = make_optimizer(*args, **kwargs)
                    optimizers.append(optimizer)
                    return optimizer

                def capture_group(record):
                    if record['status'] == 'complete':
                        groups[record['slot']] = copy.deepcopy(record['group'])

                with patch.object(training, 'make_optimizer', side_effect=capture_optimizer), \
                        patch('torch.multinomial', side_effect=scripted_groups(
                            [[1] * 8, [0] * 8, [1, 0] * 4, [1] * 8])):
                    report = training.run_training(current, self.prepared,
                        deadline=time.time() + 120, config=config(), persist_group=capture_group)
                self.assertEqual(report['status'], 'complete')
                self.assertEqual(len(optimizers), 2)
                self.assertIsNot(optimizers[0], optimizers[1])
                self.assertEqual(set(groups), {0, 1, 2})

                # Same groups, but each arm now trains on its own fresh model
                # without any parameter-state switching or optimizer swapping.
                for arm, interleaved in zip(contracts.ARMS[1:], optimizers):
                    standalone = engine(kind)
                    uninterrupted = make_optimizer(standalone.model, config()['learning_rate'])
                    for slot in range(3):
                        group = groups[slot]
                        objective = (contracts.ROUTES[group['category']]
                                     if arm == 'routed_fusion' else 'known_target_ce')
                        if objective == 'exact_centered_ddis':
                            training.guarded_af3_update(standalone, group, uninterrupted,
                                deadline=time.time() + 60, slot=slot, persist=lambda _: None)
                        else:
                            mc._ce_update(standalone, [(group, 1.0)], uninterrupted,
                                time.time() + 60, positive=objective == 'exact_positive_ce')
                    self.assertEqual(standalone.optimizer_steps, 3)
                    self.assert_nested_exact(report['states'][arm], adapter_state(standalone.model))
                    self.assert_nested_exact(interleaved.state_dict(), uninterrupted.state_dict())

                shared_parameters = set(optimizers[0].state) & set(optimizers[1].state)
                self.assertTrue(shared_parameters)
                for parameter in shared_parameters:
                    for key in ('exp_avg', 'exp_avg_sq'):
                        self.assertNotEqual(optimizers[0].state[parameter][key].data_ptr(),
                                            optimizers[1].state[parameter][key].data_ptr())

    def check_failure(self, kind, failure):
        current = engine(kind)
        initial = adapter_state(current.model)
        policy = mc.full_policy_sha256(current)
        receipts, optimizers, active = [], [], [False]
        real_probe = training.cv._preflight
        real_logps = current.completion_logps

        def after_probe(*args, **kwargs):
            result = real_probe(*args, **kwargs)
            active[0] = True
            return result

        def changed_replay(ids, prompt_length):
            values = real_logps(ids, prompt_length)
            if active[0] and torch.is_grad_enabled() and failure in ('gap', 'nan'):
                values = values.clone()
                values[prompt_length] = (values[prompt_length] + .25
                                         if failure == 'gap' else float('nan'))
            return values

        def capture_optimizer(*args, **kwargs):
            optimizer = make_optimizer(*args, **kwargs)
            optimizers.append(optimizer)
            if failure in ('post_step_nan', 'post_step_exception'):
                real_step = optimizer.step

                def failed_step(*args, **kwargs):
                    result = real_step(*args, **kwargs)
                    if failure == 'post_step_exception':
                        raise RuntimeError('injected exception after actual AdamW mutation')
                    with torch.no_grad():
                        current.parameters[0].view(-1)[0] = float('nan')
                    return result

                optimizer.step = failed_step
            return optimizer

        fatal = failure in ('post_step_nan', 'post_step_exception')
        error_type = FatalUpdateError if fatal else ValueError
        error_text = 'update failed' if fatal else 'train-gradient replay'
        with patch.object(training.cv, '_preflight', side_effect=after_probe), \
                patch.object(current, 'completion_logps', side_effect=changed_replay), \
                patch.object(training, 'make_optimizer', side_effect=capture_optimizer), \
                patch('torch.multinomial', side_effect=scripted_groups([[1] * 8, [1, 0] * 4])):
            with self.assertRaisesRegex(error_type, error_text) as caught:
                training.run_training(current, self.prepared,
                    deadline=time.time() + 90, config=config(),
                    persist_gradient=lambda value: receipts.append(copy.deepcopy(value)))
        result = caught.exception.fusion_training_result
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['anchor_restored'])
        self.assert_nested_exact(adapter_state(current.model), initial)
        self.assertEqual(mc.full_policy_sha256(current), policy)
        self.assertTrue(all(parameter.grad is None for parameter in current.parameters))
        self.assertNotIn('completion_logps', current.__dict__)
        self.assertNotIn('commit', current.__dict__)
        self.assertEqual(current.optimizer_steps, 0)
        self.assertEqual(current._fatal_update, fatal)
        self.assertEqual(result['engine_poisoned'], fatal)
        self.assertEqual(receipts[-1]['status'], 'failed')
        if fatal:
            self.assertEqual(current.optimizer_attempts, 1)
            self.assertTrue(receipts[-1]['commit_admitted'])
            self.assertEqual(receipts[-1]['verified_rows'], 8)
            self.assertTrue(any(optimizer.state for optimizer in optimizers))
            # Rollback is parameters-only. It must never clear the poison or
            # label potentially advanced optimizer state as safely resumable.
            with self.assertRaises(FatalUpdateError):
                current._checkpoint_admission()
        else:
            self.assertEqual(current.optimizer_attempts, 0)
            self.assertTrue(all(not optimizer.state for optimizer in optimizers))
            self.assertFalse(receipts[-1]['commit_admitted'])
            self.assertEqual(receipts[-1]['observed_rows'], 1)
            self.assertEqual(receipts[-1]['verified_rows'], 0)
            self.assertIsNotNone(receipts[-1]['failed_row'])
            self.assertEqual(receipts[-1]['nonfinite_replay_observed'], failure == 'nan')
            if failure == 'gap':
                self.assertGreater(receipts[-1]['max_logp_gap'], .2)
            else:
                self.assertIsNone(receipts[-1]['max_logp_gap'])
                self.assertTrue(receipts[-1]['failed_row']['nonfinite_values'])

    def test_expanded_gradient_mismatch_blocks_commit_without_poison(self):
        for kind in EXPANDED:
            with self.subTest(architecture=kind):
                self.check_failure(kind, 'gap')

    def test_expanded_nonfinite_gradient_replay_blocks_commit_without_poison(self):
        for kind in EXPANDED:
            with self.subTest(architecture=kind):
                self.check_failure(kind, 'nan')

    def test_expanded_post_step_failures_restore_and_permanently_poison(self):
        for kind in EXPANDED:
            for failure in ('post_step_nan', 'post_step_exception'):
                with self.subTest(architecture=kind, failure=failure):
                    self.check_failure(kind, failure)

    def test_actual_mixed_af3_changes_router_and_expert_adapters(self):
        current = engine('moe4_top2')
        captured = []
        real_update = training.guarded_af3_update

        def observe_af3(engine, *args, **kwargs):
            before = adapter_state(engine.model)
            result = real_update(engine, *args, **kwargs)
            after = adapter_state(engine.model)
            captured.append({
                'router_gradients': engine.last_router_gradient_norms.copy(),
                'routers_changed': [name for name in after if '.router.weight' in name
                                    and not torch.equal(before[name], after[name])],
                'expert_adapters_changed': [name for name in after
                    if '.experts.' in name and '.lora_B.' in name
                    and not torch.equal(before[name], after[name])],
            })
            return result

        with patch.object(training, 'guarded_af3_update', side_effect=observe_af3), \
                patch('torch.multinomial', side_effect=scripted_groups(
                    [[1] * 8, [0] * 8, [1, 0] * 4, [1] * 8])):
            report = training.run_training(current, self.prepared,
                deadline=time.time() + 90, config=config())
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(len(captured), 1)
        observed = captured[0]
        self.assertTrue(observed['routers_changed'])
        self.assertTrue(observed['expert_adapters_changed'])
        self.assertTrue(any(value is not None and value > 0
                            for value in observed['router_gradients'].values()))


if __name__ == '__main__':
    unittest.main()

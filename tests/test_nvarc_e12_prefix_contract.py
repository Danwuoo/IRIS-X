"""E12 causal prefix counterexamples; deterministic CPU fakes, no ML imports."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from tools import nvarc_e12_prefix_contract as e12
from tools.nvarc_e12_prefix_fixture import FakeTrainer, fixture_inputs, paired_fixture, rng_observation
from tools.nvarc_native_ttt_schedule import ulp_distance
from tools.nvarc_e10_ttt_probe import training_accounting


class PrefixContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pair = paired_fixture()

    def setUp(self):
        self.contract, self.tokens = fixture_inputs()

    def fake(self, profile='E12-TTT64-PREFIX'):
        return FakeTrainer(self.contract, self.tokens, profile)

    def started(self):
        trainer = self.fake()
        c = trainer.controller
        c.start(trainer.args, trainer.state, self.contract['reset'])
        c.begin_step(0, **self.tokens[self.contract['sampler_order'][0]], rng_before=rng_observation(trainer.rng))
        return trainer, c

    def test_independent_resets_prove_first_64_actual_rows_lr_and_rng(self):
        result = e12.validate_pair(self.pair['contract'], self.pair['short'], self.pair['control'])
        self.assertTrue(result['prefix_verified'])
        self.assertFalse(result['native_runtime_verified'])
        self.assertIsNone(result['total_cost_reduction'])
        self.assertEqual(self.pair['short']['trainer_end']['epoch'], .5)
        self.assertEqual(self.pair['control']['trainer_end']['epoch'], 1.)
        self.assertEqual(self.pair['short']['steps'][-1]['learning_rates'], [e12.scalar_reference()[63]])
        self.assertEqual(self.pair['short']['steps'][-1]['scheduler_rates_after'], [e12.scalar_reference()[64]])
        self.assertGreater(e12.scalar_reference()[64], 0)

    def test_scalar_fixture_matches_pinned_reference_within_original_four_ulp(self):
        plan = json.loads(Path('research/stage4-e11/inert-dfs-floor-plan.json').read_text())
        # Historical reference is checked without modifying or executing its profile.
        def find(value):
            if isinstance(value, dict):
                if 'native_source_learning_rates' in value:
                    return value['native_source_learning_rates']
                for child in value.values():
                    result = find(child)
                    if result is not None:
                        return result
            return None
        reference = find(plan)
        self.assertEqual(len(reference), 129)
        self.assertLessEqual(max(ulp_distance(a, b) for a, b in zip(reference, e12.scalar_reference())), 4)

    def native_fixture(self):
        reference = e12.scalar_reference()
        rates = reference[:]
        rates[49] = math.nextafter(rates[49], math.inf)
        distances = [ulp_distance(a, b) for a, b in zip(rates, reference)]
        receipt = dict(source_sha256=e12.SOURCES, function_sha256=e12.FUNCTIONS,
                       warmup_steps=13, epoch_steps=128, rates=rates,
                       reference_rates_sha256=hashlib.sha256(json.dumps(reference, separators=(',', ':')).encode()).hexdigest(),
                       reference_ulp_distances=distances, maximum_reference_ulp_distance=1,
                       platform='synthetic receipt fixture only', python='synthetic receipt fixture only',
                       model_calls=0, optimizer_steps=0,
                       policy='optimizer rate must exactly equal same-platform pinned scalar replay; reference differs by at most four ULPs')
        return e12.build_native_contract(rows=self.contract['prepared_rows'], sampler_order=self.contract['sampler_order'],
                                          reset=self.contract['reset'], sources=self.contract['sources'],
                                          rates=rates, reference_rates=reference, schedule_receipt=receipt)

    def test_native_receipt_path_keeps_actual_rates_and_separate_inert_label(self):
        contract = self.native_fixture()
        self.assertEqual(contract['evidence_kind'], 'native-observed')
        self.assertFalse(contract['agent_execution'])
        self.assertFalse(contract['publication'])
        self.assertNotEqual(contract['learning_rates'][49], contract['schedule_reference_rates'][49])
        short = FakeTrainer(contract, self.tokens, 'E12-TTT64-PREFIX').run()
        control = FakeTrainer(contract, self.tokens, 'E12-TTT128-CONTROL').run()
        self.assertTrue(e12.validate_pair(contract, short, control)['prefix_verified'])
        self.assertEqual(short['evidence_kind'], 'native-observed')
        self.assertFalse(short['native_runtime_verified'])
        # This is still a fake receipt test, not native model proof.
        trainer = FakeTrainer(contract, self.tokens, 'E12-TTT64-PREFIX')
        with self.assertRaisesRegex(RuntimeError, 'original LR prefix'):
            trainer.run(rates=contract['schedule_reference_rates'])

    def test_native_receipt_missing_forged_source_or_over_tolerance_fails(self):
        for mutate in (lambda c: c.update(schedule_receipt=None),
                       lambda c: c['schedule_receipt'].update(source_sha256={}),
                       lambda c: c['schedule_receipt'].update(epoch_steps=64),
                       lambda c: c['schedule_receipt'].update(reference_rates_sha256='0' * 64),
                       lambda c: c['schedule_receipt'].update(maximum_reference_ulp_distance=True),
                       lambda c: c['schedule_receipt']['rates'].__setitem__(0, False),
                       lambda c: c['learning_rates'].__setitem__(49, .01),
                       lambda c: c.update(evidence_kind='cpu-synthetic-only')):
            contract = self.native_fixture()
            mutate(contract)
            with self.subTest(mutate=mutate), self.assertRaises(RuntimeError):
                e12.validate_contract(contract)

    def test_native_finite_loss_variation_is_diagnostic_without_relaxing_structure(self):
        contract = self.native_fixture()
        short = FakeTrainer(contract, self.tokens, 'E12-TTT64-PREFIX').run()
        control = FakeTrainer(contract, self.tokens, 'E12-TTT128-CONTROL').run()
        short['steps'][7]['loss'] += .25
        result = e12.validate_pair(contract, short, control)
        self.assertTrue(result['prefix_verified'])
        self.assertFalse(result['numerical_losses_equal'])
        self.assertEqual(result['max_absolute_loss_difference'], .25)
        self.assertFalse(result['numerical_loss_difference_overflow'])
        self.assertFalse(result['native_runtime_verified'])
        self.assertFalse(result['promotion'])
        for mutate in (lambda t: t['steps'][7].update(loss=float('nan')),
                       lambda t: t['steps'][7].update(loss=float('inf')),
                       lambda t: t['steps'][7]['rng_before'].update(torch_cpu=e12.digest('different RNG')),
                       lambda t: t['steps'][7].update(learning_rates=[.01]),
                       lambda t: t['steps'][7].update(parameter_steps_after=[9] * 506)):
            bad = deepcopy(short)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(RuntimeError):
                e12.validate_pair(contract, bad, control)
        # Finite operands can overflow a float difference; never serialize Infinity.
        short['steps'][7]['loss'], control['steps'][7]['loss'] = 1e308, -1e308
        result = e12.validate_pair(contract, short, control)
        self.assertIsNone(result['max_absolute_loss_difference'])
        self.assertTrue(result['numerical_loss_difference_overflow'])
        json.dumps(result, allow_nan=False)

    def test_synthetic_loss_variation_still_fails_strict_pair(self):
        short = deepcopy(self.pair['short'])
        short['steps'][7]['loss'] += .25
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            e12.validate_pair(self.pair['contract'], short, self.pair['control'])
        self.assertTrue(self.pair['validation']['numerical_losses_equal'])
        self.assertEqual(self.pair['validation']['max_absolute_loss_difference'], 0.)

    def test_zero_lr_first_update_counts_actual_adam_step_without_weight_change(self):
        trainer = self.fake()
        trace = trainer.run()
        self.assertEqual(trainer.weight_after_zero_lr, 1.)
        self.assertEqual(trace['steps'][0]['learning_rates'], [0.])
        self.assertEqual(trace['steps'][0]['parameter_steps_before'], [0] * 506)
        self.assertEqual(trace['steps'][0]['parameter_steps_after'], [1] * 506)
        self.assertEqual(trainer.actual_forward_calls, 64)
        self.assertEqual(trainer.actual_optimizer_calls, 64)

    def test_callback_ignored_blocks_65_before_model_entry_and_invalidates_run(self):
        trainer = self.fake()
        with self.assertRaisesRegex(RuntimeError, 'no entry beyond'):
            trainer.run(skip_callback_stop=True)
        self.assertEqual(trainer.actual_forward_calls, 64)
        self.assertEqual(trainer.actual_optimizer_calls, 64)
        self.assertEqual(len(trainer.controller.steps), 64)
        with self.assertRaises(RuntimeError):
            e12.validate_trace(self.contract, trainer.controller.snapshot())

    def test_native_128_control_remains_complete_and_rejects_truncated_return(self):
        trainer = self.fake('E12-TTT128-CONTROL')
        with self.assertRaisesRegex(RuntimeError, 'exact completed prefix'):
            trainer.run(rows=self.contract['sampler_order'][:64])
        self.assertEqual(trainer.actual_optimizer_calls, 64)
        good = self.fake('E12-TTT128-CONTROL')
        good.run()
        self.assertEqual(good.actual_optimizer_calls, 128)

    def test_frozen_e10_complete_epoch_verifier_still_rejects_64(self):
        ledger = dict(forwards=[dict(completed=True, input_tokens=3, supervised_tokens=2)] * 64,
                      training_steps=[dict(completed=True)] * 64, optimizer_steps=[dict(completed=True)] * 64,
                      optimizer_constructions=[dict(completed=True)], generation_calls=0, teacher_calls=0)
        with self.assertRaisesRegex(RuntimeError, 'complete single native epoch'):
            training_accounting(ledger, dict(training_input_tokens=384, training_supervised_tokens=256), complete=True)

    def test_shortened_trainer_horizon_rejected_before_forward(self):
        for field, value in (('max_steps', 64), ('num_train_epochs', .5), ('gradient_accumulation_steps', 2),
                             ('per_device_train_batch_size', 2), ('warmup_steps', 7), ('num_train_epochs', True)):
            trainer = self.fake()
            setattr(trainer.args, field, value)
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                trainer.run()
            self.assertEqual(trainer.actual_forward_calls, 0)
        trainer = self.fake()
        trainer.state.max_steps = 64
        with self.assertRaises(RuntimeError):
            trainer.run()

    def test_recomputed_64_lr_fails_before_second_optimizer_call(self):
        rates = [5e-5 * (i / 7 if i < 7 else max(0., .5 * (1. + math.cos(math.pi * (i - 7) / 57))))
                 for i in range(129)]
        trainer = self.fake()
        with self.assertRaisesRegex(RuntimeError, 'original LR prefix'):
            trainer.run(rates=rates)
        self.assertEqual(trainer.actual_optimizer_calls, 1)
        self.assertFalse(trainer.controller.steps[0]['callback_complete'])

    def test_shuffling_a_short_dataset_is_not_full_sampler_prefix(self):
        short_order = list(range(64))
        random.Random(818).shuffle(short_order)
        trainer = self.fake()
        with self.assertRaisesRegex(RuntimeError, 'actual row differs'):
            trainer.run(rows=short_order)
        self.assertEqual(trainer.actual_forward_calls, 0)

    def test_swapped_actual_rows_fail_even_with_same_row_multiset(self):
        order = self.contract['sampler_order'][:]
        order[9], order[10] = order[10], order[9]
        trainer = self.fake()
        with self.assertRaisesRegex(RuntimeError, 'actual row differs'):
            trainer.run(rows=order)
        self.assertEqual(trainer.actual_forward_calls, 9)

    def test_deterministic_fixture_and_input_contract_are_copied(self):
        trainer = self.fake()
        self.contract['sampler_order'].reverse()
        trace = trainer.run()
        self.assertEqual(trace, self.pair['short'])
        self.assertEqual(paired_fixture(), self.pair)

    def test_backward_failure_never_advances_optimizer_or_requests_stop(self):
        trainer = self.fake()
        with self.assertRaisesRegex(RuntimeError, 'backward failed'):
            trainer.run(fail_backward_at=63)
        self.assertEqual(trainer.actual_forward_calls, 64)
        self.assertEqual(trainer.actual_optimizer_calls, 63)
        self.assertFalse(trainer.control.should_training_stop)
        self.assertFalse(trainer.controller.steps[-1]['backward_complete'])

    def test_unknown_or_skipped_optimizer_steps_rejected(self):
        for counters in (None, [], [None] * 506, [True] * 506, [0] * 505, [1] * 506):
            trainer, c = self.started()
            c.forward_return(1.)
            c.backward_return(rng_observation(trainer.rng))
            with self.subTest(counters=str(counters)[:20]), self.assertRaises(RuntimeError):
                c.optimizer_enter([0.], counters)

    def test_optimizer_return_cannot_skip_zero_lr_counter_increment(self):
        trainer, c = self.started()
        c.forward_return(1.)
        c.backward_return(rng_observation(trainer.rng))
        c.optimizer_enter([0.], [0] * 506)
        with self.assertRaisesRegex(RuntimeError, 'moment step counters'):
            c.optimizer_return([0] * 506)
        self.assertFalse(c.steps[-1]['optimizer_complete'])

    def test_optimizer_exception_and_callback_before_update_are_unqualified(self):
        trainer, c = self.started()
        c.forward_return(1.)
        c.backward_return(rng_observation(trainer.rng))
        c.optimizer_enter([0.], [0] * 506)
        c.fail('AdamW.step', 'synthetic optimizer exception')
        with self.assertRaises(RuntimeError):
            c.optimizer_return([1] * 506)
        self.assertFalse(c.snapshot()['complete'])
        trainer, c = self.started()
        trainer.state.global_step = 1
        with self.assertRaisesRegex(RuntimeError, 'post-optimizer'):
            c.on_step_end(trainer.args, trainer.state, trainer.control)

    def test_early_stop_and_unknown_global_step_are_fail_closed(self):
        for global_step, stopping in ((None, False), (True, False), (2, False), (1, True)):
            trainer, c = self.started()
            c.forward_return(1.)
            c.backward_return(rng_observation(trainer.rng))
            c.optimizer_enter([0.], [0] * 506)
            c.optimizer_return([1] * 506)
            c.scheduler_return([self.contract['learning_rates'][1]])
            trainer.state.global_step = global_step
            trainer.control.should_training_stop = stopping
            with self.subTest(global_step=global_step, stopping=stopping), self.assertRaises(RuntimeError):
                c.on_step_end(trainer.args, trainer.state, trainer.control)

    def test_loss_nan_and_duplicate_forward_fail(self):
        for value in (None, True, float('nan'), float('inf')):
            trainer, c = self.started()
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                c.forward_return(value)
        trainer, c = self.started()
        c.forward_return(1.)
        with self.assertRaises(RuntimeError):
            c.forward_return(1.)

    def test_trace_tampering_and_truth_fields_fail_independent_validator(self):
        mutations = [lambda t: t['steps'].pop(), lambda t: t['steps'].append(deepcopy(t['steps'][-1])),
                     lambda t: t['steps'][0].update(global_step_after=None),
                     lambda t: t['steps'][0].update(backward_complete=1),
                     lambda t: t['steps'][0].update(learning_rates=[True]),
                     lambda t: t['steps'][0].update(parameter_steps_after=[None] * 506),
                     lambda t: t['steps'][0].update(test_output=[[1]]),
                     lambda t: t['trainer_end'].update(max_steps=64),
                     lambda t: t.update(native_runtime_verified=True),
                     lambda t: t['reset'].update(gradient_tensor_count=False),
                     lambda t: t['final_reset'].update(optimizer_state_entries=1)]
        for mutate in mutations:
            trace = deepcopy(self.pair['short'])
            mutate(trace)
            with self.subTest(mutate=mutate), self.assertRaises(RuntimeError):
                e12.validate_trace(self.pair['contract'], trace)

    def test_missing_rng_and_changed_dropout_trajectory_rejected(self):
        short = deepcopy(self.pair['short'])
        short['steps'][3]['rng_before'].pop('numpy')
        with self.assertRaises(RuntimeError):
            e12.validate_trace(self.contract, short)
        short = deepcopy(self.pair['short'])
        short['steps'][3]['rng_before']['torch_cuda'][0] = e12.digest('changed dropout stream')
        self.assertTrue(e12.validate_trace(self.contract, short))
        with self.assertRaisesRegex(RuntimeError, 'dropout RNG'):
            e12.validate_pair(self.contract, short, self.pair['control'])

    def test_reset_source_or_config_mismatch_cannot_pair(self):
        for field in ('model_inventory_digest', 'rng', 'optimizer_state_entries'):
            trainer = self.fake()
            bad = deepcopy(self.contract['reset'])
            bad[field] = {'python': e12.digest('bad')} if field == 'rng' else 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                trainer.controller.start(trainer.args, trainer.state, bad)
        changed = deepcopy(self.contract)
        changed['sources']['configuration_digest'] = e12.digest('another config')
        with self.assertRaises(RuntimeError):
            e12.validate_pair(changed, self.pair['short'], self.pair['control'])

    def test_contract_forbids_short_rows_schedule_sampler_and_truth(self):
        for mutate in (lambda c: c.update(horizon=64), lambda c: c.update(warmup_steps=7),
                       lambda c: c.update(agent_execution=True), lambda c: c.update(publication=True),
                       lambda c: c.update(saved_training_time_reallocation=True),
                       lambda c: c.update(design='shared-64-snapshot-continuation'),
                       lambda c: c['prepared_rows'].pop(), lambda c: c['learning_rates'].pop(),
                       lambda c: c['sampler_order'].__setitem__(0, True),
                       lambda c: c['prepared_rows'][0].update(test_output=[[1]])):
            contract = deepcopy(self.contract)
            mutate(contract)
            with self.subTest(mutate=mutate), self.assertRaises(RuntimeError):
                e12.validate_contract(contract)

    def test_cost_25_percent_gate_counts_fixed_overhead_and_is_not_quality(self):
        control = dict(meter_definition='allocated GPUs times complete observed session wall',
                       allocation_gpu_count=4, session_seconds=1000,
                       complete_session_observed=True, includes_startup_reset_inference_finalization=True,
                       includes_instrumentation_checkpoint=True, separate_reset_run=True)
        short = dict(control, session_seconds=750)
        result = e12.compare_costs(short, control)
        self.assertTrue(result['cost_gate_passed'])
        self.assertFalse(result['quality_gate_evaluated'])
        self.assertFalse(result['promotion'])
        self.assertFalse(e12.compare_costs(dict(short, session_seconds=751), control)['cost_gate_passed'])
        for updates in ({'session_seconds': None}, {'session_seconds': float('nan')},
                        {'separate_reset_run': False}, {'includes_instrumentation_checkpoint': False},
                        {'complete_session_observed': False}, {'allocation_gpu_count': 2}):
            with self.subTest(updates=updates), self.assertRaises(RuntimeError):
                e12.compare_costs(dict(short, **updates), control)

    def test_inert_plan_preserves_full_screen_thresholds_and_pilot_separation(self):
        plan = json.loads(Path('research/stage4-e12/inert-prefix-plan.json').read_text())
        screen, pilot = plan['screen'], plan['engineering_pilot_proposal']
        self.assertEqual([screen[k] for k in ('development_tasks', 'test_outputs', 'arms', 'technical_repeats')],
                         [24, 35, 2, 2])
        self.assertEqual(screen['task_runs'], 24 * 2 * 2)
        self.assertEqual(screen['optimizer_updates'], 24 * (64 + 128) * 2)
        self.assertEqual(screen['arm_test_evaluations'], 35 * 2 * 2)
        self.assertEqual(screen['acceptance']['minimum_total_allocated_gpu_cost_reduction_fraction'], .25)
        self.assertEqual(screen['acceptance']['maximum_pass_at_2_correct_test_loss'], 1)
        self.assertEqual(screen['acceptance']['maximum_oracle_correct_test_loss'], 1)
        self.assertFalse(plan['confirmation']['opened'])
        self.assertEqual(pilot['optimizer_updates'], 4 * (64 + 128))
        self.assertEqual(pilot['arm_test_evaluations'], sum(pilot['task_test_counts'].values()) * 2)
        self.assertEqual(sum(pilot['phase_caps_seconds'].values()), pilot['maximum_notebook_wall_seconds'])
        self.assertEqual(pilot['maximum_allocated_gpu_hours'], 4)
        self.assertFalse(plan['agent_execution'])
        self.assertFalse(plan['publication'])
        self.assertIsNone(screen['cost_reduction_observed'])
        self.assertIsNone(pilot['total_cost_reduction_observed'])

    def test_fixture_export_runs_with_no_native_dependencies_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'fixture.json'
            command = [sys.executable, '-S', 'tools/nvarc_e12_prefix_fixture.py', '--output', str(output)]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            fixture = json.loads(output.read_text())
            self.assertEqual(fixture, self.pair)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(json.loads(output.read_text()), fixture)


if __name__ == '__main__':
    unittest.main()

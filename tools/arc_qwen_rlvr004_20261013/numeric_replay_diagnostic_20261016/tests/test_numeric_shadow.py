"""CPU tensor/owned-ledger tests, explicitly not native Qwen or GPU evidence."""
from contextlib import contextmanager
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PACKAGE.parent / 'source'))
from rl_session.common import canonical, digest, need, tensor_signature, tree_sha
from owned_runtime.ledger import DurablePhysicalLedger

SPEC = importlib.util.spec_from_file_location('rl_session.numeric_shadow_tested',
    PACKAGE / 'runtime/rl_session/numeric_shadow.py')
shadow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow)


class FakeModel(torch.nn.Module):
    """Small deterministic M-sensitive head, not a simulated Qwen equivalence."""
    def __init__(self):
        super().__init__()
        self.base = torch.nn.Parameter(torch.arange(8, dtype=torch.float32), requires_grad=False)
        self.lora = torch.nn.Parameter(torch.tensor(0.25))
        self.register_buffer('buffer', torch.tensor(2.))
        self.child = torch.nn.Identity()
        self.child.train(False)
        self.config = SimpleNamespace(output_hidden_states=False, output_attentions=False)
        self.calls = []
        self.fail_at = None
        self.nonfinite_at = None
        self.effect = None
        self.perturbations = {}
        self.returned_logits = []
        self.teacher_batch_size = 1

    def get_base_model(self):
        return self

    def get_output_embeddings(self):
        return SimpleNamespace(weight=self.base.view(8, 1))

    def forward(self, **kwargs):
        need(not self.training and not torch.is_grad_enabled() and torch.is_inference_mode_enabled(),
             'fixture needs genuine eval/inference')
        need('output_hidden_states' not in kwargs and 'output_attentions' not in kwargs,
             'diagnostic must not request capture')
        need(kwargs['past_key_values'] is None and kwargs['use_cache'] is False,
             'diagnostic must be cache-free')
        self.calls.append({k: v.clone() if torch.is_tensor(v) else v for k, v in kwargs.items()})
        if self.effect is not None:
            effect, self.effect = self.effect, None
            effect(self)
        if len(self.calls) == self.fail_at:
            raise ValueError('fixture forward failed')
        tokens = kwargs['input_ids']
        selected = kwargs['logits_to_keep']
        length = tokens.shape[1]
        indices = torch.arange(length)[-selected:] if type(selected) is int else selected
        # Depend on context length and M to guarantee nonzero combined contrasts.
        hidden = indices.float()[None, :, None] * 0.03 + self.lora + length * 0.01
        logits = hidden * self.base[None, None, :] + len(indices) * self.base.square()[None, None, :] * .003
        if len(self.calls) == self.nonfinite_at:
            logits[0, 0, 0] = float('nan')
        if len(self.calls) in self.perturbations:
            logits[0, 0, 1] += self.perturbations[len(self.calls)]
        if len(indices) > 1 and self.teacher_batch_size != 1:
            logits = logits.repeat(self.teacher_batch_size, 1, 1)
        self.returned_logits.append(logits.clone())
        return SimpleNamespace(logits=logits, past_key_values=None)


class FakeTrainer:
    def __init__(self, model):
        self.model = model
        self.parameters = {'lora': model.lora}

    def _get_rng(self):
        return {'python': random.getstate(), 'torch': torch.get_rng_state().clone()}

    def _set_rng(self, state):
        random.setstate(state['python'])
        torch.set_rng_state(state['torch'])

    def fingerprint(self):
        return {'sha256': tree_sha(self.parameters)}


class FakeActor:
    def __init__(self, directory, *, length=80, forced=()):
        self.model = FakeModel()
        self.model.lora.grad = torch.tensor(.125)
        self.trainer = FakeTrainer(self.model)
        self.device = torch.device('cpu')
        self.native = SimpleNamespace(vocab_size=8, identity={'cpu_fake': True})
        self.cache_mode = 'cached'
        self._sources = {'fixture': 'source'}
        self.global_deadline = time.monotonic() + 600
        self._phase_deadline = self.global_deadline - 10
        self._lock = threading.RLock()
        self.ledger = DurablePhysicalLedger(self.device, self.global_deadline, lambda _: None,
            Path(directory) / 'journal.jsonl', auth_key=b'fake-key-only-for-unit-tests-123456', fixture=True)
        self.policy_version = 'fixture-policy'
        self._generation_epoch = 1
        self.counters = {'rl_updates': 0, 'backward_calls': 8}
        self._owned = {}
        self._batch_registry = {}
        self.batch = {'id': 'batch-fixture', 'batch_index': 0,
                      'parent_ids': ['parent-' + str(i) for i in range(8)], 'rows': []}
        self.replays = []
        for ordinal, parent in enumerate(self.batch['parent_ids']):
            for slot in range(8):
                identifier = parent + '-slot-' + str(slot)
                generated = [1] * length
                steps = [{'position': 1 + i, 'token': 1, 'support': [1] if i in forced else [1, 2, 3],
                          'log_mu': 0. if i in forced else float(torch.tensor(-.8))}
                         for i in range(length)]
                trajectory = {'trajectory_id': identifier, 'parent_id': parent, 'prompt_ids': [4, 5],
                              'original_ids': [4, 5] + generated, 'generated_ids': generated, 'steps': steps}
                self._owned[identifier] = canonical(trajectory)
                self.batch['rows'].append({'parent_id': parent, 'slot': slot, 'trajectory': trajectory,
                                          'eligible': True, 'status': 'eligible'})
                if (ordinal, slot) in ((6, 2), (0, 7)):
                    with self.ledger.work('causal-replay', self._phase_deadline) as event:
                        event.update(trajectory_id=identifier, update_batch_id=self.batch['id'], dispatched=True)
                    self.replays.append({'trajectory_id': identifier, 'parent_id': parent,
                                         'original_token_replay': True, 'training_mode': True,
                                         'update_batch_id': self.batch['id'], 'replay_event_id': event['event_id'],
                                         'log_pi': [-.7] * length, 'log_mu': [s['log_mu'] for s in steps]})
        self.rebind_batch()

    def rebind_batch(self):
        self._batch_registry[self.batch['id']] = canonical(self.batch)

    def _check_live(self):
        pass

    def _check_optimizer(self):
        pass

    def _optimizer_signature(self):
        return {'optimizer': 'unchanged-fixture'}

    def _check_batch(self, batch):
        need(self._batch_registry.get(batch.get('id')) == canonical(batch), 'unknown or changed batch')

    def _admit(self, row):
        need(self._owned.get(row['trajectory_id']) == canonical(row), 'unknown or changed trajectory')

    def _hooks(self):
        return tuple((n, k, tuple((i, id(h)) for i, h in getattr(m, k).items()))
                     for n, m in self.model.named_modules()
                     for k in ('_forward_hooks', '_forward_pre_hooks', '_backward_hooks'))

    def _functions(self):
        return tuple(id(m.forward.__func__) for m in self.model.modules())

    def _structure(self):
        return vars(self.model.config).copy()

    def _deadline(self, deadline):
        if time.monotonic() >= deadline:
            raise TimeoutError('fixture original deadline')

    @contextmanager
    def _mode(self, training):
        modes = {n: m.training for n, m in self.model.named_modules()}
        self.model.train(training)
        try:
            yield
        finally:
            for n, m in self.model.named_modules():
                m.training = modes[n]

    def run(self, **kwargs):
        return shadow.run_numeric_shadow(self, self.batch, self.replays,
                                         deadline=kwargs.get('deadline', self._phase_deadline))


class NumericShadowTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.temporary = tempfile.TemporaryDirectory(prefix='irisx-numeric-shadow-')
        self.actor = None

    def tearDown(self):
        if self.actor is not None:
            self.actor.ledger.release()
        self.temporary.cleanup()

    def actor_with(self, **kwargs):
        self.actor = FakeActor(self.temporary.name, **kwargs)
        return self.actor

    def test_complete_two_fixed_targets_eight_original_forwards(self):
        a = self.actor_with()
        before, rng = shadow._state(a), tree_sha(a.trainer._get_rng())
        old = deepcopy(a.replays)
        result = a.run()
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['schema'], 'numeric-shadow-training-tail-v2')
        self.assertTrue(result['state_preserved'])
        self.assertEqual(shadow._state(a), before)
        self.assertEqual(tree_sha(a.trainer._get_rng()), rng)
        self.assertEqual(a.replays, old)
        self.assertEqual(result['model_forward_calls'], 8)
        self.assertEqual(result['head_projection_calls'], 0)
        self.assertEqual([(r['parent_ordinal'], r['slot'], r['points'][0]['offset'])
                          for r in result['rows']], [(6, 2, 66), (0, 7, 77)])
        self.assertFalse(result['interpretation']['head_shape_causality_isolated'])
        self.assertFalse(result['source_binding']['observed_hidden_identity'])
        self.assertTrue(result['selection']['outcome_selected_from_prior_training_diagnostic'])
        self.assertFalse(result['selection']['independent_qualification'])
        self.assertEqual(result['selection']['prior_training_diagnostic']['source_audit_sha256'],
                         '12280cab41ec53be1b735bffd94ebc45e5f1ed427c5d15486b42b746b5b0f9ce')
        self.assertEqual([c['input_ids'].shape[1] for c in a.model.calls], [81, 81, 81, 68, 81, 81, 81, 79])
        for offset, position in ((0, 67), (4, 78)):
            calls = a.model.calls[offset:offset+4]
            self.assertTrue(torch.equal(calls[0]['logits_to_keep'], torch.arange(1, 81)))
            self.assertTrue(torch.equal(calls[1]['logits_to_keep'], torch.tensor([position])))
            self.assertTrue(torch.equal(calls[2]['logits_to_keep'], torch.tensor([position])))
            self.assertEqual(calls[3]['logits_to_keep'], 1)
            for key in calls[1]:
                if torch.is_tensor(calls[1][key]):
                    self.assertTrue(torch.equal(calls[1][key], calls[2][key]), key)
                else:
                    self.assertEqual(calls[1][key], calls[2][key], key)
            self.assertTrue(torch.equal(calls[0]['input_ids'], calls[1]['input_ids']))
            self.assertTrue(torch.equal(calls[0]['input_ids'][:, :position+1], calls[3]['input_ids']))
        for row in result['rows']:
            point = row['points'][0]
            self.assertEqual(row['original_prompt_length'], 2)
            self.assertEqual(row['original_generated_length'], 80)
            self.assertEqual(row['teacher_position_range'], {'start': 1, 'stop_exclusive': 81, 'count': 80})
            chain = ('train_vs_eval_gap', 'softmax_row_shape_gap',
                     'same_reduction_teacher_vs_fullinput_m1_gap', 'fullinput_m1_vs_prefix_m1_gap',
                     'prefix_2d_vs_1d_gap', 'prefix_vector_vs_actor_gap')
            self.assertAlmostEqual(sum(point[k] for k in chain), point['train_vs_actor_gap'], places=12)
            self.assertNotEqual(point['same_reduction_teacher_vs_fullinput_m1_gap'], 0.)
            self.assertNotEqual(point['fullinput_m1_vs_prefix_m1_gap'], 0.)
            self.assertEqual(point['fullinput_m1_logits_shape'], [1, 1, 8])
            self.assertEqual(point['fullinput_m1_repeat_logits_shape'], [1, 1, 8])
            self.assertEqual(point['fullinput_m1_input_shape'], [1, 81])
            self.assertEqual(point['fullinput_m1_repeat_input_shape'], [1, 81])
        payload = json.dumps(result)
        self.assertNotIn('generated_ids', payload)
        self.assertNotIn('support":', payload)
        self.assertLess(len(payload), shadow.MAX_REPORT_BYTES)
        recorded = [e for e in a.ledger.events if e['phase'] == 'numeric-shadow-forward']
        self.assertEqual(len(recorded), 8)
        self.assertTrue(all(e['status'] == 'complete' and e['dispatched'] for e in recorded))
        self.assertTrue(all(e['actual_cost']['forward_calls'] == 1 for e in recorded))
        self.assertEqual(sum(e['input_tokens'] for e in recorded), 633)
        self.assertTrue(all(e['input_tokens'] == e['actual_cost']['input_tokens'] ==
                            e['reserved_cost']['input_tokens'] for e in recorded))
        self.assertEqual(result['rows'][0]['inferred_teacher_head_input_shape'], [1, 80, 1])
        self.assertEqual(result['rows'][0]['points'][0]['inferred_prefix_head_input_shape'], [1, 1, 1])
        self.assertEqual(set(result['physical_event_ids']), {e['event_id'] for e in a.ledger.events[2:]})
        self.assertTrue(a.ledger.summary()['integrity_ok'])

    def test_vector_reductions_really_use_1d_actor_math(self):
        a = self.actor_with()
        original = shadow.rl_math.masked_log_probs
        seen = []
        def observed(logits, allowed, **kwargs):
            seen.append((logits.ndim, tuple(logits.shape), tuple(allowed.shape)))
            return original(logits, allowed, **kwargs)
        with patch.object(shadow.rl_math, 'masked_log_probs', side_effect=observed):
            result = a.run()
        self.assertTrue(result['complete'], result)
        self.assertEqual([shape for ndim, shape, _ in seen if ndim == 1], [(8,)] * 4)
        self.assertEqual(len([1 for ndim, _, _ in seen if ndim == 2]), 10)
        self.assertTrue(all(shape == allowed for _, shape, allowed in seen))
        mask = torch.zeros(8, dtype=torch.bool)
        mask[[1, 2, 3]] = True
        for index, row in enumerate(result['rows']):
            point = row['points'][0]
            logits = a.model.returned_logits[4*index][0, point['offset']]
            prefix = a.model.returned_logits[4*index+3][0, 0]
            self.assertEqual(point['same_logits_vector_log_pi'], float(original(logits, mask)[1]))
            self.assertEqual(point['prefix_vector_log_pi'], float(original(prefix, mask)[1]))
            self.assertEqual(point['same_logits_vector_shape'], [8])
            self.assertEqual(point['same_logits_single_row_shape'], [1, 8])
            self.assertEqual(point['prefix_vector_shape'], [8])
            self.assertEqual(point['prefix_single_row_shape'], [1, 8])

    def test_rank_sensitive_reducer_results_are_not_conflated(self):
        a = self.actor_with()
        original = shadow.rl_math.masked_log_probs
        def instrumented(logits, allowed, **kwargs):
            output = original(logits, allowed, **kwargs)
            return output + .125 if logits.ndim == 1 else output
        with patch.object(shadow.rl_math, 'masked_log_probs', side_effect=instrumented):
            result = a.run()
        self.assertTrue(result['complete'], result)
        for row in result['rows']:
            point = row['points'][0]
            self.assertEqual(point['same_logits_2d_vs_1d_gap'], -.125)
            self.assertEqual(point['prefix_2d_vs_1d_gap'], -.125)

    def test_nonzero_repeat_difference_is_retained_without_gate_claim(self):
        a = self.actor_with()
        a.model.perturbations = {3: .5, 7: -.25}
        result = a.run()
        self.assertTrue(result['complete'], result)
        self.assertFalse(result['interpretation']['repeat_is_gate_input'])
        self.assertFalse(result['gate_inputs_replaced'])
        self.assertFalse(result['optimizer_commit_allowed'])
        for row in result['rows']:
            point = row['points'][0]
            self.assertNotEqual(point['fullinput_m1_repeat_gap'], 0.)
            self.assertEqual(point['fullinput_m1_repeat_gap'],
                             point['fullinput_m1_repeat_log_pi'] - point['fullinput_m1_log_pi'])

    def test_ninth_forward_is_rejected_before_reservation(self):
        a = self.actor_with()
        result = a.run()
        self.assertTrue(result['complete'], result)
        events = len(a.ledger.events)
        with self.assertRaisesRegex(ValueError, 'forward ceiling'):
            shadow._forward(a, result, {}, [1], 1, a._phase_deadline, lambda: None)
        self.assertEqual(len(a.model.calls), 8)
        self.assertEqual(len(a.ledger.events), events)

    def test_teacher_extra_batch_dimension_is_rejected_before_row_indexing(self):
        a = self.actor_with()
        a.model.teacher_batch_size = 2
        before, rng = shadow._state(a), tree_sha(a.trainer._get_rng())
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertIn('exact original generated causal head row layout', result['reason'])
        self.assertEqual(result['model_forward_calls'], 1)
        self.assertEqual(tuple(a.model.returned_logits[0].shape), (2, 80, 8))
        self.assertNotIn('eval_multirow_log_pi', result['rows'][0]['points'][0])
        self.assertTrue(result['state_preserved'])
        self.assertEqual(shadow._state(a), before)
        self.assertEqual(tree_sha(a.trainer._get_rng()), rng)

    def test_dynamic_worst_gap_does_not_change_fixed_targets(self):
        a = self.actor_with()
        for old in a.replays:
            old['log_pi'][0] = -999.
        result = a.run()
        self.assertTrue(result['complete'], result)
        self.assertEqual([r['points'][0]['offset'] for r in result['rows']], [66, 77])
        self.assertFalse(result['selection']['dynamic_worst_selection'])

    def test_malformed_target_position_is_rejected_before_forward(self):
        a = self.actor_with()
        row = next(r['trajectory'] for r in a.batch['rows']
                   if r['parent_id'] == 'parent-6' and r['slot'] == 2)
        row['steps'][66]['position'] += 1
        a._owned[row['trajectory_id']] = canonical(row)
        a.rebind_batch()
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertIn('causal position', result['reason'])
        self.assertEqual(result['model_forward_calls'], 0)

    def test_forced_target_is_incomplete_without_substitution(self):
        a = self.actor_with(forced=(66,))
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertTrue(result['state_preserved'])
        self.assertEqual(result['model_forward_calls'], 4)
        self.assertEqual(result['rows'][0]['points'][0]['status'], 'forced-no-substitution')
        self.assertEqual(result['rows'][1]['points'][0]['offset'], 77)
        self.assertEqual(result['rows'][1]['points'][0]['status'], 'complete')

    def test_both_forced_targets_are_incomplete_without_forward(self):
        a = self.actor_with(forced=(66, 77))
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual([r['status'] for r in result['rows']], ['forced-no-substitution'] * 2)

    def test_missing_offset_preserves_other_target_without_replacement(self):
        a = self.actor_with(length=70)
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 4)
        self.assertEqual(result['rows'][0]['points'][0]['status'], 'complete')
        self.assertEqual(result['rows'][1]['points'][0]['status'], 'missing-offset')
        self.assertEqual(result['rows'][1]['points'][0]['offset'], 77)

    def test_both_missing_offsets_need_no_forward(self):
        a = self.actor_with(length=4)
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual([r['status'] for r in result['rows']], ['missing-offset'] * 2)

    def test_missing_parent_is_incomplete_without_other_parent(self):
        a = self.actor_with()
        a.batch['parent_ids'] = a.batch['parent_ids'][:6]
        a.rebind_batch()
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 4)
        self.assertEqual(result['rows'][0]['status'], 'missing')
        self.assertEqual(result['rows'][1]['status'], 'complete')

    def test_missing_slot_never_uses_another_slot(self):
        a = self.actor_with()
        a.batch['rows'] = [r for r in a.batch['rows'] if not (r['parent_id'] == 'parent-6' and r['slot'] == 2)]
        a.rebind_batch()
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 4)
        self.assertEqual(result['rows'][0]['status'], 'missing')

    def test_missing_replay_is_incomplete_without_replacement(self):
        a = self.actor_with()
        a.replays.pop()
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 4)
        self.assertEqual(result['rows'][0]['status'], 'missing-original-replay')

    def test_malformed_original_replay_event_is_rejected(self):
        a = self.actor_with()
        a.replays[0]['replay_event_id'] = 999
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)

    def test_mutated_original_trajectory_is_rejected(self):
        a = self.actor_with()
        a.batch['rows'][7]['trajectory']['generated_ids'][0] = 7
        a.rebind_batch()
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)

    def test_nonfirst_batch_is_rejected(self):
        a = self.actor_with()
        a.batch['batch_index'] = 1
        a.rebind_batch()
        self.assertFalse(a.run()['complete'])
        self.assertEqual(len(a.model.calls), 0)

    def test_successful_or_failed_diagnostic_cannot_be_retried(self):
        a = self.actor_with()
        a.model.fail_at = 2
        first = a.run()
        self.assertFalse(first['complete'])
        a.model.fail_at = None
        second = a.run()
        self.assertFalse(second['complete'])
        self.assertIn('no diagnostic retry', second['reason'])
        self.assertEqual(second['model_forward_calls'], 0)
        self.assertEqual(len(a.model.calls), 2)

    def test_unavailable_forward_source_is_incomplete_before_dispatch(self):
        a = self.actor_with()
        with patch.object(shadow.inspect, 'getsourcefile', return_value=None):
            result = a.run()
        self.assertFalse(result['complete'])
        self.assertTrue(result['state_preserved'])
        self.assertEqual(result['model_forward_calls'], 0)

    def test_nonfinite_old_pi_fails_before_extra_forward(self):
        a = self.actor_with()
        a.replays[0]['log_pi'][0] = float('nan')
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)

    def test_forward_failure_retains_charge_and_completed_partials(self):
        a = self.actor_with()
        a.model.fail_at = 3
        before = shadow._state(a)
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertTrue(result['state_preserved'])
        self.assertEqual(result['model_forward_calls'], 3)
        self.assertEqual(result['rows'][0]['points'][0]['status'], 'fullinput-reduced')
        self.assertIn('fullinput_m1_log_pi', result['rows'][0]['points'][0])
        self.assertNotIn('fullinput_m1_repeat_log_pi', result['rows'][0]['points'][0])
        self.assertEqual(shadow._state(a), before)
        failed = [e for e in a.ledger.events if e['phase'] == 'numeric-shadow-forward' and e['status'] == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertTrue(failed[0]['dispatched'])
        self.assertEqual(failed[0]['reserved_cost']['forward_calls'], 1)
        self.assertEqual(failed[0]['input_tokens'], 81)

    def test_second_target_failure_retains_first_complete_point(self):
        a = self.actor_with()
        a.model.fail_at = 7
        before = shadow._state(a)
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertTrue(result['state_preserved'])
        self.assertEqual(result['model_forward_calls'], 7)
        self.assertEqual(result['rows'][0]['status'], 'complete')
        self.assertEqual(result['rows'][1]['points'][0]['status'], 'fullinput-reduced')
        self.assertEqual(shadow._state(a), before)

    def test_dispatched_forward_deadline_restores_state_and_retains_partials(self):
        a = self.actor_with()
        before, rng = shadow._state(a), tree_sha(a.trainer._get_rng())
        original = a._deadline
        def deadline_after_second_call(deadline):
            original(deadline)
            if len(a.model.calls) >= 2:
                raise TimeoutError('fixture dispatched forward deadline')
        with patch.object(a, '_deadline', side_effect=deadline_after_second_call):
            result = a.run()
        self.assertFalse(result['complete'])
        self.assertTrue(result['state_preserved'])
        self.assertEqual(result['error_type'], 'TimeoutError')
        self.assertEqual(result['model_forward_calls'], 2)
        self.assertEqual(result['rows'][0]['points'][0]['status'], 'teacher-reduced')
        self.assertEqual(shadow._state(a), before)
        self.assertEqual(tree_sha(a.trainer._get_rng()), rng)
        failed = [e for e in a.ledger.events if e['phase'] == 'numeric-shadow-forward' and e['status'] == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertTrue(failed[0]['dispatched'])

    def test_nonfinite_new_logits_end_incomplete_without_retry(self):
        a = self.actor_with()
        a.model.nonfinite_at = 2
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 2)

    def test_rng_consumption_is_detected_and_restored(self):
        a = self.actor_with()
        before = tree_sha(a.trainer._get_rng())
        a.model.effect = lambda _: torch.rand(1)
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertIn('RNG', result['reason'])
        self.assertEqual(tree_sha(a.trainer._get_rng()), before)
        self.assertEqual(result['model_forward_calls'], 1)

    def test_adapter_gradient_and_hook_changes_detected(self):
        for kind in ('adapter', 'gradient', 'hook'):
            with self.subTest(kind=kind):
                if self.actor is not None:
                    self.actor.ledger.release()
                subdir = Path(self.temporary.name) / kind
                subdir.mkdir()
                a = self.actor = FakeActor(subdir)
                effects = {'adapter': lambda m: m.lora.add_(1),
                           'gradient': lambda m: m.lora.grad.add_(1),
                           'hook': lambda m: m.register_forward_hook(lambda *_: None)}
                a.model.effect = effects[kind]
                result = a.run()
                self.assertFalse(result['complete'])
                self.assertFalse(result['state_preserved'])
                self.assertEqual(result['model_forward_calls'], 1)

    def test_native_capture_flag_is_rejected_before_forward(self):
        a = self.actor_with()
        a.model.config.output_hidden_states = True
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertIn('capture', result['reason'])

    def test_expired_deadline_preserves_real_excluded_event_id(self):
        a = self.actor_with()
        result = a.run(deadline=time.monotonic() - 1)
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual(result['physical_event_ids'], [2])
        self.assertEqual(a.ledger.events[2]['status'], 'excluded')

    def test_original_phase_deadline_and_shadow_window_not_extended(self):
        a = self.actor_with()
        a._phase_deadline = time.monotonic() + 20
        result = a.run(deadline=a.global_deadline)
        self.assertTrue(result['complete'], result)
        self.assertTrue(all(e['deadline'] <= a._phase_deadline for e in a.ledger.events[2:]))
        outer = a.ledger.events[2]
        self.assertLessEqual(outer['deadline'] - outer['started'], 120)
        for event in a.ledger.events:
            if event['phase'] == 'numeric-shadow-forward':
                self.assertLessEqual(event['deadline'] - event['started'], 30)

    def test_memory_limit_checked_without_reset(self):
        a = self.actor_with()
        a.device = torch.device('cuda')
        with patch.object(torch.cuda, 'memory_allocated', return_value=shadow.MAX_ALLOCATED + 1), \
             patch.object(torch.cuda, 'memory_reserved', return_value=0), \
             patch.object(torch.cuda, 'max_memory_allocated', return_value=0), \
             patch.object(torch.cuda, 'max_memory_reserved', return_value=0), \
             patch.object(torch.cuda, 'reset_peak_memory_stats') as reset:
            result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)
        reset.assert_not_called()


if __name__ == '__main__':
    unittest.main()

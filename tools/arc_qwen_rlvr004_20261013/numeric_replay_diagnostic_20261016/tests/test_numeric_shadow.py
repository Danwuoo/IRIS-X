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
    def __init__(self, directory, *, length=4, forced=()):
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
                if ordinal in (0, 7) and slot == 0:
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

    def test_complete_two_fixed_trajectories_eight_original_forwards(self):
        a = self.actor_with()
        before, rng = shadow._state(a), tree_sha(a.trainer._get_rng())
        old = deepcopy(a.replays)
        result = a.run()
        self.assertTrue(result['complete'], result)
        self.assertTrue(result['state_preserved'])
        self.assertEqual(shadow._state(a), before)
        self.assertEqual(tree_sha(a.trainer._get_rng()), rng)
        self.assertEqual(a.replays, old)
        self.assertEqual(result['model_forward_calls'], 8)
        self.assertEqual(result['head_projection_calls'], 0)
        self.assertEqual([r['parent_ordinal'] for r in result['rows']], [0, 7])
        self.assertEqual([[p['offset'] for p in r['points']] for r in result['rows']], [[0, 1, 3]] * 2)
        self.assertFalse(result['interpretation']['head_shape_causality_isolated'])
        self.assertEqual([c['input_ids'].shape[1] for c in a.model.calls], [5, 2, 3, 5] * 2)
        for index in (0, 4):
            self.assertTrue(torch.equal(a.model.calls[index]['logits_to_keep'], torch.tensor([1, 2, 3, 4])))
        for row in result['rows']:
            for point in row['points']:
                gap_sum = point['train_vs_eval_gap'] + point['teacher_vs_prefix_gap'] + point['prefix_vs_actor_gap']
                self.assertAlmostEqual(gap_sum, point['train_log_pi'] - point['actor_log_mu'], places=12)
        payload = json.dumps(result)
        self.assertNotIn('generated_ids', payload)
        self.assertNotIn('support":', payload)
        self.assertLess(len(payload), shadow.MAX_REPORT_BYTES)
        recorded = [e for e in a.ledger.events if e['phase'] == 'numeric-shadow-forward']
        self.assertEqual(len(recorded), 8)
        self.assertTrue(all(e['status'] == 'complete' and e['dispatched'] for e in recorded))
        self.assertTrue(all(e['actual_cost']['forward_calls'] == 1 for e in recorded))
        self.assertEqual(sum(e['input_tokens'] for e in recorded), 30)
        self.assertTrue(all(e['input_tokens'] == e['actual_cost']['input_tokens'] ==
                            e['reserved_cost']['input_tokens'] for e in recorded))
        self.assertEqual(result['rows'][0]['inferred_teacher_head_input_shape'], [1, 4, 1])
        self.assertEqual(result['rows'][0]['points'][0]['inferred_prefix_head_input_shape'], [1, 1, 1])
        self.assertEqual(set(result['physical_event_ids']), {e['event_id'] for e in a.ledger.events[2:]})
        self.assertTrue(a.ledger.summary()['integrity_ok'])

    def test_offsets_are_deduplicated(self):
        a = self.actor_with(length=2)
        result = a.run()
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['model_forward_calls'], 6)
        self.assertEqual([p['offset'] for p in result['rows'][0]['points']], [0, 1])

    def test_forced_selected_point_has_no_substitution(self):
        a = self.actor_with(forced=(1,))
        result = a.run()
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['model_forward_calls'], 6)
        self.assertEqual(result['rows'][0]['points'][1]['status'], 'forced-no-substitution')
        self.assertEqual([p['offset'] for p in result['rows'][0]['points']], [0, 1, 3])

    def test_all_forced_points_need_no_extra_forward(self):
        a = self.actor_with(forced=(0, 1, 3))
        result = a.run()
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual(result['rows'][0]['status'], 'all-selected-points-forced')

    def test_missing_offset_is_incomplete_without_replacement(self):
        a = self.actor_with(length=1)
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual(result['rows'][0]['points'][1]['status'], 'missing-offset')

    def test_missing_parent_is_incomplete_without_other_parent(self):
        a = self.actor_with()
        a.batch['parent_ids'] = a.batch['parent_ids'][:7]
        a.rebind_batch()
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual(result['rows'][1]['status'], 'missing')

    def test_missing_replay_is_incomplete_before_dispatch(self):
        a = self.actor_with()
        a.replays.pop()
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual(result['rows'][1]['status'], 'missing-original-replay')

    def test_malformed_original_replay_event_is_rejected(self):
        a = self.actor_with()
        a.replays[0]['replay_event_id'] = 999
        result = a.run()
        self.assertFalse(result['complete'])
        self.assertEqual(result['model_forward_calls'], 0)

    def test_mutated_original_trajectory_is_rejected(self):
        a = self.actor_with()
        a.batch['rows'][0]['trajectory']['generated_ids'][0] = 7
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
        self.assertEqual(result['rows'][0]['points'][0]['status'], 'complete')
        self.assertEqual(shadow._state(a), before)
        failed = [e for e in a.ledger.events if e['phase'] == 'numeric-shadow-forward' and e['status'] == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertTrue(failed[0]['dispatched'])
        self.assertEqual(failed[0]['reserved_cost']['forward_calls'], 1)
        self.assertEqual(failed[0]['input_tokens'], 3)

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

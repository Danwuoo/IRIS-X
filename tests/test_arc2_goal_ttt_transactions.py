"""Synthetic CPU transaction regressions, not model capability evidence."""
from __future__ import annotations

import gc
import importlib.util
import json
import math
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

_MISSING = [n for n in ('torch', 'transformers', 'peft', 'pydantic') if importlib.util.find_spec(n) is None]
if not _MISSING:
    import torch
    from tests.test_arc2_goal_model import tiny_engine
    from tools.arc2_goal_sprint_20261017 import model, run, launch


@unittest.skipIf(bool(_MISSING), 'Optional ML dependencies missing: ' + ', '.join(_MISSING))
class TTTTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        self.engine = tiny_engine()
        self.selected = model.adapter_state(self.engine.model)
        self.task = {'train': [{'input': [[1]], 'output': [[2]]},
                               {'input': [[3]], 'output': [[4]]}], 'test': [{'input': [[5]]}]}
        self.cfg = {'run_id': 'synthetic-ttt-transaction', 'seed': 3, 'ttt_steps': 3,
                    'context_tokens': 128, 'generation_tokens': 3}
        self.events = []

    def audit(self, event, **fields):
        self.events.append((event, fields))

    def adapt(self, deadline=math.inf):
        return run.adapt_public_task(self.engine, self.task, self.cfg, self.audit,
            task_id='synthetic-task', rng=random.Random(2), deadline=deadline, loss_mode='final')

    def fingerprint(self):
        return model.state_digest(model.adapter_state(self.engine.model))

    def test_partial_optimizer_failures_restore_only_failed_step(self):
        for failure in ('oom', 'nonfinite', 'value'):
            with self.subTest(failure=failure):
                self.setUp()
                original = torch.optim.AdamW.step
                accepted, calls = [], []
                def step(optimizer, *args, **kwargs):
                    calls.append(1)
                    result = original(optimizer, *args, **kwargs)
                    if len(calls) == 1:
                        accepted.append(self.fingerprint())
                    else:
                        if failure == 'nonfinite':
                            with torch.no_grad(): self.engine.parameters[0].fill_(float('nan'))
                        elif failure == 'oom':
                            raise torch.cuda.OutOfMemoryError('synthetic partial optimizer allocation')
                        else:
                            raise ValueError('synthetic partial optimizer failure')
                    return result
                with patch('torch.optim.AdamW.step', new=step):
                    result = self.adapt()
                self.assertEqual(self.fingerprint(), accepted[0])
                self.assertNotEqual(accepted[0], model.state_digest(self.selected))
                self.assertEqual(result['steps'], 1)
                self.assertEqual(result['attempts'], 2)
                self.assertEqual(result['physical_optimizer_steps'], 1)
                self.assertEqual(result['physical_optimizer_attempts'], 2)
                self.assertTrue(all(p.grad is None for p in self.engine.parameters))
                rollback = next(r for e, r in self.events if e == 'ttt_rollback')
                self.assertTrue(rollback['snapshot_restored'])
                self.assertTrue(rollback['earlier_committed_steps_preserved'])
                self.assertEqual(rollback['rollback_scope'], 'failed_step_only')
                self.assertFalse(rollback['retried'])

    def test_precommit_deadline_preserves_earlier_finite_update(self):
        original = self.engine.sft_step
        calls, accepted = [], []
        def step(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                with patch.object(model, 'check_deadline', side_effect=[None, model.PhaseDeadline('synthetic backward crossed deadline')]):
                    return original(*args, **kwargs)
            result = original(*args, **kwargs)
            accepted.append(self.fingerprint())
            return result
        with patch.object(self.engine, 'sft_step', side_effect=step):
            result = self.adapt()
        self.assertEqual(self.fingerprint(), accepted[0])
        self.assertEqual(result['steps'], 1)
        self.assertEqual(result['physical_optimizer_steps'], 1)
        self.assertEqual(result['physical_optimizer_attempts'], 1)
        self.assertEqual(result['stop_reason'], 'PhaseDeadline')

    def test_late_successful_commit_is_charged_but_not_retained(self):
        original = self.engine.sft_step
        now, calls, accepted = [100.0], [], []
        clock = SimpleNamespace(time=lambda: now[0])
        def step(*args, **kwargs):
            calls.append(1)
            result = original(*args, **kwargs)
            if len(calls) == 1:
                accepted.append(self.fingerprint())
            else:
                now[0] = 200.0  # exact deadline is rejected, not merely overruns
            return result
        with patch.object(run, 'time', clock), patch.object(model, 'time', clock), \
             patch.object(self.engine, 'sft_step', side_effect=step):
            result = self.adapt(deadline=200.0)
        self.assertEqual(self.fingerprint(), accepted[0])
        self.assertEqual(result['steps'], 1)
        self.assertEqual(result['physical_optimizer_steps'], 2)
        self.assertEqual(result['physical_optimizer_attempts'], 2)
        self.assertEqual(result['stop_reason'], 'PhaseDeadline')
        self.assertEqual(result['wall_seconds'], 100.0)

    def test_encoding_failure_before_snapshot_keeps_current_adapter(self):
        original_encode, original_step = run.encoded_loo, self.engine.sft_step
        encodes, accepted = [], []
        def encode(*args, **kwargs):
            encodes.append(1)
            if len(encodes) == 2:
                raise ValueError('synthetic query exceeds context')
            return original_encode(*args, **kwargs)
        def step(*args, **kwargs):
            result = original_step(*args, **kwargs)
            accepted.append(self.fingerprint())
            return result
        with patch.object(run, 'encoded_loo', side_effect=encode), \
             patch.object(self.engine, 'sft_step', side_effect=step):
            result = self.adapt()
        self.assertEqual(self.fingerprint(), accepted[0])
        self.assertEqual(result['steps'], 1)
        self.assertEqual(result['physical_optimizer_steps'], 1)
        rollback = next(r for e, r in self.events if e == 'ttt_rollback')
        self.assertFalse(rollback['snapshot_restored'])

    def test_failed_traceback_tensor_is_released_before_restore(self):
        original_step, original_restore = self.engine.sft_step, run.restore_state
        calls, refs = [], []
        def step(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                tensor_owned_by_failed_frame = torch.ones(32)
                refs.append(weakref.ref(tensor_owned_by_failed_frame))
                raise torch.cuda.OutOfMemoryError('synthetic forward failure')
            return original_step(*args, **kwargs)
        def restore(*args, **kwargs):
            gc.collect()
            self.assertEqual(len(refs), 1)
            self.assertIsNone(refs[0]())
            return original_restore(*args, **kwargs)
        with patch.object(self.engine, 'sft_step', side_effect=step), \
             patch.object(run, 'restore_state', side_effect=restore):
            result = self.adapt()
        self.assertEqual(result['steps'], 1)

    def test_restore_exception_and_wrong_restoration_are_fatal(self):
        for mode in ('exception', 'wrong_state'):
            with self.subTest(mode=mode):
                self.setUp()
                original = torch.optim.AdamW.step
                calls = []
                def poison(optimizer, *args, **kwargs):
                    calls.append(1)
                    result = original(optimizer, *args, **kwargs)
                    if len(calls) == 2:
                        raise torch.cuda.OutOfMemoryError('synthetic mutation before failure')
                    return result
                def restore(*args, **kwargs):
                    if mode == 'exception': raise RuntimeError('synthetic restore failure')
                with patch('torch.optim.AdamW.step', new=poison), patch.object(run, 'restore_state', side_effect=restore):
                    with self.assertRaises(RuntimeError): self.adapt()
                self.assertFalse(any(e == 'ttt_phase_complete' for e, _ in self.events))
                self.assertTrue(all(p.grad is None for p in self.engine.parameters))

    def test_unknown_error_is_fatal_and_never_infers(self):
        original = self.engine.sft_step
        calls = []
        def step(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2: raise RuntimeError('synthetic unknown failure')
            return original(*args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(self.engine, 'sft_step', side_effect=step), \
             patch.object(self.engine, 'generate') as generate:
            with self.assertRaisesRegex(RuntimeError, 'unknown failure'):
                run.solve_public(self.engine, {'a': self.task, 'b': self.task}, self.selected,
                                 self.cfg, self.audit, Path(directory), deadline=math.inf)
            generate.assert_not_called()
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(p.grad is None for p in self.engine.parameters))

    def test_expired_and_zero_step_tasks_do_not_attempt_training(self):
        for steps, deadline, reason in ((3, 0.0, 'deadline_before_step'), (0, math.inf, 'step_limit')):
            with self.subTest(steps=steps), patch.object(run, 'encoded_loo') as encode:
                self.cfg['ttt_steps'] = steps
                result = self.adapt(deadline)
                encode.assert_not_called()
                self.assertEqual(result['stop_reason'], reason)
                self.assertEqual(result['steps'], 0)
                self.assertEqual(result['attempts'], 0)
                self.assertEqual(result['physical_optimizer_attempts'], 0)
                self.assertEqual(result['state_sha256'], model.state_digest(self.selected))

    def test_zero_signal_has_no_retained_or_physical_update(self):
        with patch('torch.nn.utils.clip_grad_norm_', return_value=torch.tensor(0.0)):
            result = self.adapt()
        self.assertEqual(result['steps'], 0)
        self.assertEqual(result['attempts'], 3)
        self.assertEqual(result['physical_optimizer_steps'], 0)
        self.assertEqual(result['physical_optimizer_attempts'], 0)
        self.assertEqual(self.fingerprint(), model.state_digest(self.selected))

    def test_next_task_resets_selected_and_batched_queries_use_retained_state(self):
        original_step, original_generate = self.engine.sft_step, self.engine.generate_prompts
        calls, starts, accepted, generation_states = [], [], [], []
        def step(*args, **kwargs):
            calls.append(1)
            if len(calls) % 2 == 0:
                raise model.PhaseDeadline('synthetic second-step deadline')
            starts.append(self.fingerprint())
            result = original_step(*args, **kwargs)
            accepted.append(self.fingerprint())
            return result
        def generate(*args, **kwargs):
            generation_states.append(self.fingerprint())
            return original_generate(*args, **kwargs)
        cfg = {**self.cfg, 'candidate_views': 8, 'candidate_batch_size': 4, 'candidate_ranker': 'vote'}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(self.engine, 'sft_step', side_effect=step), \
             patch.object(self.engine, 'generate_prompts', side_effect=generate):
            out = Path(directory)
            pools = run.solve_public(self.engine, {'a': self.task, 'b': self.task}, self.selected,
                                     cfg, self.audit, out, deadline=math.inf)
            receipt = launch.candidate_audit(out/'full-candidate-pools.json', pools)
        self.assertEqual(starts, [model.state_digest(self.selected)] * 2)
        self.assertEqual(generation_states, [accepted[0]] * 2 + [accepted[1]] * 2)
        self.assertTrue(receipt['complete_coverage'])
        self.assertEqual(receipt['queries'], 2)
        complete = [r for e, r in self.events if e == 'public_task_complete']
        self.assertEqual([r['ttt_steps'] for r in complete], [1, 1])
        self.assertEqual([r['physical_ttt_optimizer_steps'] for r in complete], [1, 1])
        self.assertEqual([r['ttt_retained_state_sha256'] for r in complete], accepted)
        self.assertEqual(model.state_digest(self.selected), starts[0])


if __name__ == '__main__':
    unittest.main()

import time
import json
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path
from tools.arc_learning_agent_20261011.budget import WorkLedger
from tools.arc_learning_agent_20261011.metering import MeteredModel, MeteredTrainer, TrainingStageFailed


class MeteringTests(unittest.TestCase):
    def test_adapter_assignment_reaches_actual_native(self):
        class Native:
            model = object()
            tokenizer = object()
            adapter_state_sha256 = None
        with tempfile.TemporaryDirectory() as d:
            native = Native(); model = MeteredModel(native, WorkLedger(Path(d) / 'ledger'))
            model.adapter_state_sha256 = 'a' * 64
            self.assertEqual(native.adapter_state_sha256, 'a' * 64)
            new = object(); model.model = new
            self.assertIs(native.model, new)

    def test_failed_second_update_charged_and_blocks_inference(self):
        class Trainer:
            def train(self, *args, **kwargs):
                return {'status': 'failed_update', 'steps': 1, 'optimizer_steps': 1,
                        'attempted_microbatches': 2, 'input_tokens': 100, 'usage_known': True}
        with tempfile.TemporaryDirectory() as d:
            ledger = WorkLedger(Path(d) / 'ledger')
            trainer = MeteredTrainer(Trainer(), ledger)
            with self.assertRaises(TrainingStageFailed): trainer.train([], max_steps=2, deadline=100)
            self.assertEqual(ledger.used['training_steps'], 2)
            self.assertEqual(trainer.completed_optimizer_steps, 1)
            self.assertEqual(ledger.pending, {})
            self.assertEqual(ledger.events[-1]['event'], 'failed')

    def test_normal_deadline_receipt_has_internal_watchdog_grace(self):
        now = [100.0]
        class Native:
            def generate(self, *args, **kwargs):
                soft = kwargs['deadline']
                marker = json.loads((ledger.path.parent / 'active-call.json').read_bytes())
                self_hard = marker['deadline_monotonic']
                if not soft < self_hard <= 120.0:
                    raise AssertionError('work cutoff must be inside hard cap')
                now[0] = soft + 0.01
                return {'valid': False, 'dispatched': True, 'input_tokens': 10,
                        'output_tokens': 2, 'finish_reason': 'deadline'}
        with tempfile.TemporaryDirectory() as d, patch('time.monotonic', side_effect=lambda: now[0]):
            ledger = WorkLedger(Path(d) / 'ledger')
            result = MeteredModel(Native(), ledger).generate([], kind='grid', seed=0,
                                                           max_new_tokens=10, deadline=120.0)
            self.assertEqual(result['finish_reason'], 'deadline')
            self.assertEqual(ledger.pending, {})
            self.assertEqual(ledger.used['generation_calls'], 1)
            marker = json.loads((ledger.path.parent / 'active-call.json').read_bytes())
            self.assertEqual(marker['status'], 'closed')
            self.assertLess(now[0], marker['deadline_monotonic'])

    def test_no_forward_exclusion_zero_physical_usage(self):
        class Native:
            def generate(self, *args, **kwargs):
                return {'valid': False, 'dispatched': False, 'input_tokens': 8000, 'output_tokens': 0}
        with tempfile.TemporaryDirectory() as d:
            ledger = WorkLedger(Path(d) / 'ledger')
            result = MeteredModel(Native(), ledger).generate([], kind='grid', seed=0,
                                                           max_new_tokens=10, deadline=time.monotonic()+30)
            self.assertFalse(result['dispatched'])
            self.assertEqual(ledger.used['generation_calls'], 0)
            self.assertEqual(ledger.used['input_tokens'], 0)


if __name__ == '__main__': unittest.main()

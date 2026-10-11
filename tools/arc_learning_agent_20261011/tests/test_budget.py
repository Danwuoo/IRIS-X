import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.arc_learning_agent_20261011.budget import (
    SessionClock, WorkLedger, BudgetExceeded, STAGE_SECONDS, DEFAULT_CAPS, calibrated_steps)


class ClockTests(unittest.TestCase):
    def test_exact_total(self): self.assertEqual(sum(STAGE_SECONDS.values()), 43200)

    def test_restart_does_not_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'clock.json'
            c = SessionClock.create(path, 's', maximum_seconds=100, wall=lambda: 1000, monotonic=lambda: 10)
            self.assertEqual(c.remaining(), 100)
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            d = SessionClock.resume(path, expected_sha256=sha, wall=lambda: 1040, monotonic=lambda: 3)
            self.assertEqual(d.remaining(), 60)
            e = SessionClock.resume(path, expected_sha256=sha, wall=lambda: 1110, monotonic=lambda: 0)
            self.assertEqual(e.remaining(), 0)
            with self.assertRaises(ValueError):
                SessionClock.create(path, 's', wall=lambda: 1000)

    def test_wall_backwards_does_not_extend_live_clock(self):
        wall, mono = [1000], [0]
        record = {'format': 'irisx/learning-clock-v1', 'started_epoch': 1000,
                  'deadline_epoch': 1100, 'maximum_seconds': 100, 'origin': 'first-active-cell', 'session_id': 's'}
        c = SessionClock(record, wall=lambda: wall[0], monotonic=lambda: mono[0])
        wall[0] = 900; mono[0] = 80
        self.assertEqual(c.remaining(), 20)

    def test_soft_cutoff_closes_cleanly_before_hard_stage_cap(self):
        now = [100.0]
        record = {'format': 'irisx/learning-clock-v1', 'started_epoch': 1000,
                  'deadline_epoch': 44200, 'maximum_seconds': 43200,
                  'origin': 'first-active-cell', 'session_id': 's'}
        c = SessionClock(record, wall=lambda: 1000 + now[0] - 100, monotonic=lambda: now[0])
        preserved = {'previous_prediction': [[1]]}
        with c.stage('global_sft') as soft:
            hard = c.events[-1]['hard_deadline_monotonic']
            self.assertGreater(hard, soft)
            now[0] = soft + 1  # ordinary completed update/receipt after work cutoff
        self.assertEqual(c.events[-1]['status'], 'complete')
        with c.stage('public_solve') as next_soft:
            self.assertGreater(next_soft, now[0])
        self.assertEqual(preserved['previous_prediction'], [[1]])
        with self.assertRaises(BudgetExceeded):
            with c.stage('calibrate'):
                now[0] = c.events[-1]['hard_deadline_monotonic'] + 0.01
        self.assertEqual(c.events[-1]['status'], 'overrun')

    def test_calibration_uses_slowest_observed_update(self):
        self.assertEqual(calibrated_steps(100, [1, 4, 2], maximum_steps=100), 20)
        self.assertEqual(calibrated_steps(100, [], maximum_steps=100), 0)

    def test_ledger_reservation_and_unknown_charge(self):
        with tempfile.TemporaryDirectory() as tmp:
            caps = dict(DEFAULT_CAPS); caps['generation_calls'] = 2
            ledger = WorkLedger(Path(tmp) / 'work.jsonl', caps=caps)
            ledger.reserve('one', {'generation_calls': 1, 'output_tokens': 2048})
            ledger.complete('one', {'generation_calls': 1, 'output_tokens': 10})
            ledger.reserve('two', {'generation_calls': 1, 'output_tokens': 2048})
            ledger.unknown('two', 'child stopped')
            with self.assertRaises(BudgetExceeded): ledger.reserve('three', {'generation_calls': 1})
            self.assertEqual(ledger.summary()['charged']['output_tokens'], 2058)
            self.assertIn('two', ledger.summary()['pending'])
            with self.assertRaises(ValueError): ledger.reserve('one', {'generation_calls': 0})

    def test_over_reservation_not_forgiven(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = WorkLedger(Path(tmp) / 'work.jsonl')
            ledger.reserve('one', {'input_tokens': 2})
            with self.assertRaises(ValueError): ledger.complete('one', {'input_tokens': 3})
            self.assertIn('one', ledger.pending)


if __name__ == '__main__': unittest.main()

"""Finite protocol faults plus two bounded real CPU cleanup observations."""
import json
import errno
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from tests import nvarc_output_fault_harness as harness
from tests.test_nvarc_mailbox_io import Clock, Child
from tests.test_nvarc_public_eval import fixture, record
from tools import nvarc_public_eval as public
from tools.nvarc_native_multitask import canonical


class FaultProtocolTests(unittest.TestCase):
    def test_control_denial_probation_is_bounded_and_phase_deadline_still_applies(self):
        value = {'nonce': 'n', 'phase': 'startup', 'writer_pid': 7, 'parent_pid': 6}
        for mode in ('recover', 'persistent', 'deadline'):
            with self.subTest(mode=mode):
                clock = Clock(); reads = []; events = []
                def read(path):
                    reads.append(1)
                    if mode == 'recover' and len(reads) == 2: return canonical(value)
                    raise PermissionError(errno.EACCES, 'injected control denial')
                reader = public.MailboxReader(read_bytes=read, windows=True,
                    observe=lambda kind, **kw: events.append(kind))
                def wait():
                    return harness.wait_control(Path('synthetic-control.json'), nonce='n', phase='startup', process=Child(0),
                        timeout=.01 if mode == 'deadline' else 1, overall_end=2, now=clock, pause=clock.advance, reader=reader)
                if mode == 'recover': self.assertEqual(wait(), value); self.assertEqual(len(reads), 2)
                elif mode == 'persistent':
                    with self.assertRaises(PermissionError): wait()
                    self.assertEqual(len(reads), 5)
                else:
                    with self.assertRaises(TimeoutError): wait()
                    self.assertEqual(len(reads), 1)

    def test_phase_timeout_is_finite_and_identifies_missing_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = Clock(); child = Child(0); pauses = []
            def pause(seconds): pauses.append(seconds); clock.advance(seconds)
            with self.assertRaisesRegex(TimeoutError, 'store-ready'):
                harness.wait_control(Path(tmp)/'absent.json', nonce='n', phase='store-ready', process=child,
                    timeout=.1, overall_end=1, now=clock, pause=pause)
            self.assertAlmostEqual(clock(), .1); self.assertLessEqual(len(pauses), 6)
            clock = Clock()
            with self.assertRaisesRegex(TimeoutError, 'barrier'):
                harness.wait_control(Path(tmp)/'absent.json', nonce='n', phase='barrier', process=child,
                    timeout=10, overall_end=.05, now=clock, pause=clock.advance)
            self.assertAlmostEqual(clock(), .05)

    def test_delayed_control_and_launcher_exit_have_distinct_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'control.json'; clock = Clock(); child = Child(0)
            value = {'nonce': 'n', 'phase': 'startup', 'writer_pid': 7, 'parent_pid': 6}
            def pause(seconds):
                clock.advance(seconds)
                if clock() >= .04: harness.atomic_bytes(path, canonical(value))
            self.assertEqual(harness.wait_control(path, nonce='n', phase='startup', process=child,
                timeout=.1, overall_end=1, now=clock, pause=pause), value)
            path.unlink(); child.code = 17
            with self.assertRaisesRegex(RuntimeError, 'launcher exited before startup'):
                harness.wait_control(path, nonce='n', phase='startup', process=child,
                    timeout=.1, overall_end=1, now=clock, pause=pause)

    def test_invalid_duplicate_or_foreign_control_fails_without_retry(self):
        bodies = [b'{', b'{"nonce":"n","nonce":"n"}',
                  canonical({'nonce': 'foreign', 'phase': 'startup', 'writer_pid': 7, 'parent_pid': 6}),
                  canonical({'nonce': 'n', 'phase': 'barrier', 'writer_pid': 7, 'parent_pid': 6}),
                  canonical({'nonce': 'n', 'phase': 'startup', 'writer_pid': True, 'parent_pid': 6})]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'control.json'
            for body in bodies:
                with self.subTest(body=body):
                    path.write_bytes(body)
                    with self.assertRaises((ValueError, RuntimeError)), patch.object(harness.time, 'sleep', side_effect=AssertionError('no retry')):
                        harness.wait_control(path, nonce='n', phase='startup', process=Child(0), timeout=1,
                                             overall_end=time.monotonic()+1)

    def test_atomic_control_preserves_old_complete_json_until_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'control.json'; path.write_bytes(b'{"version":1}')
            actual = harness.os.replace; observations = []
            def replace(source, target):
                observations.append(json.loads(path.read_bytes())); return actual(source, target)
            with patch.object(harness.os, 'replace', replace): harness.atomic_bytes(path, b'{"version":2}')
            self.assertEqual(observations, [{'version': 1}]); self.assertEqual(json.loads(path.read_bytes()), {'version': 2})

    def test_real_missing_startup_or_barrier_cleanup_has_honest_writer_receipt(self):
        evidence = Path(os.environ.get('IRIS_E01_EVIDENCE_DIR', str(harness.ROOT/'.irisx/e01-local-fault-cases')))
        for mode in ('no-startup', 'missing-barrier'):
            with self.subTest(mode=mode):
                root = evidence/'protocol-cases'/(mode+'-'+uuid.uuid4().hex)
                plan, data = fixture(); store = public.ResultStore(root, plan, data, allow_fixture=True)
                store.commit(record(plan, data, 'a', [[2]]))
                for name, value in [('fixture-plan.json', plan), ('fixture-input.json', data),
                                    ('update-record.json', record(plan, data, 'b', [[3]]))]:
                    (root/name).write_bytes(canonical(value))
                receipt = harness.run_case(root, mode, phase_seconds=.1 if mode == 'no-startup' else 10)
                self.assertFalse(receipt['barrier_reached']); self.assertTrue(receipt['launcher_stop_confirmed'])
                self.assertEqual(receipt['errors'][0]['phase'], 'protocol')
                self.assertLess(receipt['elapsed_seconds'], 40+15+15+5+1)
                if mode == 'no-startup':
                    self.assertIsNone(receipt['writer_pid']); self.assertIsNone(receipt['worker_exit_code'])
                    self.assertIsNone(receipt['worker_stopped_handle_verified']); self.assertIsNone(receipt['writer_stop_confirmed'])
                else:
                    self.assertIsNotNone(receipt['writer_pid']); self.assertTrue(receipt['writer_stop_confirmed'])
                with (evidence/'protocol-receipts.jsonl').open('ab') as stream: stream.write(canonical(receipt)+b'\n')

    def test_independent_handle_acquisition_failure_keeps_writer_exit_unknown(self):
        evidence = Path(os.environ.get('IRIS_E01_EVIDENCE_DIR', str(harness.ROOT/'.irisx/e01-local-fault-cases')))
        root = evidence/'protocol-cases'/('handle-failure-'+uuid.uuid4().hex)
        root.mkdir(parents=True)
        # The initial handshake precedes imports/recovery; no model or output
        # fixture is necessary. Only our known launcher tree is stopped.
        with patch.object(harness, 'WriterHandle', side_effect=OSError('injected OpenProcess failure')) as opening:
            receipt = harness.run_case(root, 'before-commit')
        self.assertTrue(receipt['launcher_stop_confirmed']); self.assertFalse(receipt['barrier_reached'])
        self.assertIsNotNone(receipt['writer_pid'])
        if os.name == 'nt':
            opening.assert_called_once_with(receipt['writer_pid'])
            self.assertIsNone(receipt['worker_exit_code']); self.assertIsNone(receipt['writer_stop_confirmed'])
            self.assertIsNone(receipt['worker_stopped_handle_verified'])
            self.assertIn('OpenProcess failure', receipt['errors'][0]['message'])
        else:
            opening.assert_not_called()  # POSIX uses the exact Popen writer, no Windows handle claim
            self.assertIsNone(receipt['worker_stopped_handle_verified'])
        with (evidence/'protocol-receipts.jsonl').open('ab') as stream: stream.write(canonical(receipt)+b'\n')


if __name__ == '__main__': unittest.main()

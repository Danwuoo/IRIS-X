"""Synthetic cleanup fault matrix. No real process or model launch here."""
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import nvarc_output_lifecycle as life
from tools import nvarc_public_eval_parent as parent
from tools import nvarc_official_parent as official
from tests.test_nvarc_mailbox_io import ParentFixture, Child


def retain(value):
    destination = os.environ.get('IRIS_E01_EVIDENCE_DIR')
    if destination:
        path = Path(destination); path.mkdir(parents=True, exist_ok=True)
        with (path/'cleanup-receipts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value, sort_keys=True)+'\n')


class ClosingStream:
    def __init__(self, stream, error): self.stream, self.error = stream, error
    @property
    def closed(self): return self.stream.closed
    def close(self):
        self.stream.close()
        if self.error:
            error, self.error = self.error, None
            raise error


class CleanupTests(unittest.TestCase):
    def capture(self, streams, *, close_error=None, open_error=None):
        original = Path.open
        def opening(path, *args, **kwargs):
            if path.name == 'stderr.log' and open_error is not None: raise open_error
            stream = original(path, *args, **kwargs)
            if path.name in ('stdout.log', 'stderr.log'):
                if not streams and close_error: stream = ClosingStream(stream, close_error)
                streams.append(stream)
            return stream
        return patch.object(Path, 'open', opening)

    def test_primary_stop_failure_attempts_every_worker_and_closes_eight_logs_without_drain(self):
        primary = RuntimeError('primary parent loop failure'); secondary = TimeoutError('first stop timed out')
        with tempfile.TemporaryDirectory() as tmp:
            f = ParentFixture(Path(tmp)); streams = []; drains = []
            def pause(_): raise primary
            def stop(child):
                f.stops.append(child.pid)
                if child.pid == 90000: raise secondary
                child.code = -9
            f.pause, f.stop = pause, stop
            with self.capture(streams), patch.object(parent.MailboxReader, 'final_read', side_effect=lambda *a, **k: drains.append(a)):
                with self.assertRaises(RuntimeError) as raised: f.run()
            self.assertIs(raised.exception, primary)
            self.assertEqual(f.stops, [90000, 90001, 90002, 90003])
            self.assertEqual(len(streams), 8); self.assertTrue(all(s.closed for s in streams))
            self.assertEqual(drains, [])
            report = primary.cleanup_report
            self.assertFalse(report['all_producers_stopped'])
            self.assertEqual(report['drain_status'], 'skipped-unconfirmed-producers')
            self.assertEqual(report['secondary_errors'][0]['type'], 'TimeoutError')
            self.assertEqual(life.diagnostic(primary, 'loop')['cleanup'], report)
            retain({'case': 'controller-first-stop-reproduction', 'primary_identity_preserved': raised.exception is primary,
                    'stops': f.stops, 'logs_closed': 8, 'cleanup': report, 'real_processes': 0})

    def test_primary_keeps_stop_close_and_both_final_drain_errors_after_confirmed_exit(self):
        primary = KeyboardInterrupt('primary interrupt'); streams = []; drained = []
        with tempfile.TemporaryDirectory() as tmp:
            f = ParentFixture(Path(tmp))
            def pause(_): raise primary
            def stop(child):
                f.stops.append(child.pid); child.code = -9
                if child.pid == 90000: raise TimeoutError('stop errored after exit')
            def drain(reader, path, **kwargs):
                self.assertTrue(all(c.code is not None for c in f.children))
                drained.append(path.parent.name); raise OSError('final drain '+path.parent.name)
            f.pause, f.stop = pause, stop
            with self.capture(streams, close_error=OSError('close failed after closing')), \
                 patch.object(parent.MailboxReader, 'final_read', drain):
                with self.assertRaises(KeyboardInterrupt) as raised: f.run()
            self.assertIs(raised.exception, primary); self.assertEqual(drained, ['a', 'b'])
            self.assertTrue(all(s.closed for s in streams))
            report = primary.cleanup_report
            self.assertTrue(report['all_producers_stopped']); self.assertEqual(report['drain_status'], 'attempted')
            self.assertEqual([e['phase'] for e in report['secondary_errors']], ['stop:0', 'close:0:stdout', 'drain:a', 'drain:b'])
            retain({'case': 'primary-stop-close-drain', 'primary_identity_preserved': True, 'cleanup': report, 'real_processes': 0})

    def test_without_primary_stop_or_drain_error_reports_failure_after_all_attempts(self):
        for mode in ('stop', 'drain'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                f = ParentFixture(Path(tmp)); streams = []; drained = []
                error = TimeoutError('cleanup failure '+mode)
                original_stop = f.stop
                def stop(child):
                    if child.pid == 90000:
                        f.stops.append((child.pid, f.clock())); raise error
                    original_stop(child)
                def drain(reader, path, **kwargs):
                    drained.append(path.parent.name); raise error
                if mode == 'stop': f.stop = stop
                with self.capture(streams), patch.object(parent.MailboxReader, 'final_read', drain):
                    with self.assertRaises(TimeoutError) as raised: f.run()
                self.assertIs(raised.exception, error); self.assertEqual(len(f.stops), 4)
                self.assertTrue(all(s.closed for s in streams)); self.assertEqual(len(streams), 8)
                self.assertEqual(drained, [] if mode == 'stop' else ['a', 'b'])
                retain({'case': 'no-primary-'+mode, 'cleanup': error.cleanup_report, 'raised_failure': True, 'real_processes': 0})

    def test_partial_log_open_and_launch_failure_close_already_acquired_resources(self):
        for mode in ('open', 'launch'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                f = ParentFixture(Path(tmp)); streams = []; error = OSError('partial '+mode)
                launch = f.launch
                def fail_launch(command, **kwargs):
                    if int(command[command.index('--rank')+1]) == 1: raise error
                    return launch(command, **kwargs)
                if mode == 'launch': f.launch = fail_launch
                with self.capture(streams, open_error=error if mode == 'open' else None):
                    with self.assertRaises(OSError) as raised: f.run()
                self.assertIs(raised.exception, error); self.assertTrue(all(s.closed for s in streams))
                self.assertEqual(len(streams), 1 if mode == 'open' else 4)
                self.assertEqual(len(f.stops), 0 if mode == 'open' else 1)
                retain({'case': 'partial-'+mode, 'cleanup': error.cleanup_report, 'real_processes': 0})

    def test_official_finally_uses_independent_cleanup_and_retains_primary_terminal(self):
        primary = RuntimeError('official primary source failure'); attempted = []
        streams = [io.StringIO() for _ in range(8)]; children = [Child(i) for i in range(4)]
        resources = [{'identity': i, 'process': c, 'streams': dict(zip(('stdout', 'stderr'), streams[2*i:2*i+2]))}
                     for i, c in enumerate(children)]
        def stop(child):
            attempted.append(child.pid)
            if child.pid == 90000: raise TimeoutError('official cleanup timeout')
            child.code = -9
        def inject(resources_from_execute, stop_from_execute, **kwargs):
            self.assertEqual(resources_from_execute, [])  # bounded fake injection, no real launch
            return life.cleanup_workers(resources, stop, **kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'root'; root.mkdir()
            with patch.object(official, 'require', side_effect=primary), patch.object(official, 'cleanup_workers', inject):
                with self.assertRaises(RuntimeError) as raised:
                    official.execute(root, {'run_id': 'synthetic-cleanup'}, {}, time.monotonic())
            self.assertIs(raised.exception, primary); self.assertEqual(attempted, [90000, 90001, 90002, 90003])
            self.assertTrue(all(s.closed for s in streams))
            terminal = json.loads((root/'terminal.json').read_bytes())
            self.assertEqual(terminal['primary_error']['message'], str(primary))
            self.assertEqual(terminal['cleanup'], primary.cleanup_report); self.assertEqual(terminal['notebook_exit'], 'failure')
            retain({'case': 'official-finally-fake-resources', 'terminal': terminal, 'real_processes': 0})

    def test_public_unconfirmed_cleanup_skips_archive_and_returns_failure(self):
        error = RuntimeError('parent failed'); error.cleanup_report = {'all_producers_stopped': False}
        with tempfile.TemporaryDirectory() as tmp:
            f = ParentFixture(Path(tmp)); plan = f.plan
            from tools.nvarc_native_multitask import write
            write(f.root/'challenges.json', f.data)
            with patch.object(parent, 'validate_plan'), patch.object(parent, 'ResultStore', return_value=f.store), \
                 patch.object(parent, 'sha', return_value=plan['challenges_sha256']), \
                 patch.object(parent, 'prepare', return_value=(f.root, [])), \
                 patch.object(parent, 'run_workers', side_effect=error), patch.object(parent, 'write_archive') as archive, \
                 patch.object(parent, 'print', create=True):
                code = parent.execute(f.root, plan, f.root, time.monotonic())
            self.assertEqual(code, 1); archive.assert_not_called()
            terminal = json.loads((f.root/'terminal.json').read_bytes())
            self.assertEqual(terminal['errors'][0]['message'], 'parent failed')
            self.assertIn('confirmed producer stop', terminal['errors'][-1]['message'])


if __name__ == '__main__': unittest.main()

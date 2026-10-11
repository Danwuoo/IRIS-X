import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tools.arc_learning_agent_20261011 import process_guard as pg


@unittest.skipUnless(sys.platform == 'linux', 'Linux lifecycle tests')
class ProcessGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.guards = []
        self.children = []

    def tearDown(self):
        for guard in self.guards:
            if guard.poll() is None or guard._remaining():
                guard.stop(timeout=5)
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
        self.temp.cleanup()

    def spawn(self, code, name='guard'):
        guard = pg.OwnedProcessGuard.spawn(
            [sys.executable, '-I', '-B', '-c', code], evidence_dir=self.root / name,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.guards.append(guard)
        return guard

    def wait_for(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.01)
        self.fail('synthetic child condition timed out')

    def wait_guard(self, guard):
        self.wait_for(lambda: guard.poll() is not None)
        return guard.closed_proof()

    def test_graceful_exit_durable_proof_and_reaped_child(self):
        guard = self.spawn('pass')
        proof = self.wait_guard(guard)
        self.assertTrue(pg.verify_closed_proof(proof))
        self.assertFalse(proof['forced'])
        self.assertEqual(proof['worker_returncode'], 0)
        self.assertEqual(proof['returncode'], 0)
        self.assertEqual(guard.identity['pid'], guard.identity['session'])
        self.assertGreaterEqual(len(proof['owned_identities']), 2)
        for name in ('launch.json', 'worker-launch.json', 'supervisor-result.json', 'closure.json'):
            self.assertTrue((self.root / 'guard' / name).is_file())
        with self.assertRaises(ChildProcessError):
            os.waitpid(guard.child.pid, os.WNOHANG)
        # Repeated proof does not overwrite exclusive evidence or lose closure.
        self.assertEqual(proof, guard.closed_proof())

    def test_worker_failure_is_not_hidden_by_supervisor(self):
        guard = self.spawn('raise SystemExit(37)')
        proof = self.wait_guard(guard)
        self.assertTrue(proof['closed'])
        self.assertEqual(proof['worker_returncode'], 37)
        self.assertEqual(guard.child.returncode, 37)
        self.assertFalse(proof['forced'])

    def test_stop_tracks_separate_sessions_and_does_not_touch_unrelated_child(self):
        unrelated = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(30)'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(unrelated)
        leaf_path = self.root / 'leaf.json'
        leaf = ('import os,signal,time,json; from pathlib import Path; '
                'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                f'Path({str(leaf_path)!r}).write_text(json.dumps({{"pid":os.getpid(),"sid":os.getsid(0)}})); '
                'time.sleep(30)')
        middle = ('import subprocess,sys,time,signal; '
                  'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                  f'subprocess.Popen([sys.executable,"-I","-c",{leaf!r}],start_new_session=True); '
                  'time.sleep(30)')
        worker = ('import subprocess,sys,time; '
                  f'subprocess.Popen([sys.executable,"-I","-c",{middle!r}],start_new_session=True); '
                  'time.sleep(30)')
        guard = self.spawn(worker)
        self.wait_for(leaf_path.exists)
        leaf_row = json.loads(leaf_path.read_text())
        self.assertEqual(leaf_row['pid'], leaf_row['sid'])
        self.assertNotEqual(leaf_row['sid'], guard.identity['session'])
        proof = guard.stop(timeout=8)
        self.assertTrue(proof['closed'], proof)
        self.assertTrue(proof['forced'])
        self.assertTrue(pg.verify_closed_proof(proof))
        self.assertGreaterEqual(len(proof['owned_identities']), 4)
        self.assertTrue(any(row['pid'] == leaf_row['pid'] for row in proof['owned_identities']))
        self.assertIsNone(unrelated.poll())
        for identity in proof['owned_identities']:
            self.assertFalse(pg._same(pg._read_process(identity['pid']), identity))
        self.assertNotIn(unrelated.pid, [row['pid'] for row in proof['owned_identities']])

    def test_orphan_between_parent_polls_is_reaped_and_not_graceful(self):
        marker = self.root / 'orphan.json'
        leaf = ('import os,time,json,signal; from pathlib import Path; '
                'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                f'Path({str(marker)!r}).write_text(json.dumps({{"pid":os.getpid(),"sid":os.getsid(0)}})); '
                'time.sleep(30)')
        worker = ('import subprocess,sys,time; from pathlib import Path; '
                  f'subprocess.Popen([sys.executable,"-I","-c",{leaf!r}],start_new_session=True); '
                  f'path=Path({str(marker)!r}); '\
                  '\nwhile not path.exists(): time.sleep(0.001)')
        guard = self.spawn(worker)
        # Intentionally do not poll while the worker forks/setsid/exits.
        time.sleep(0.25)
        proof = self.wait_guard(guard)
        orphan = json.loads(marker.read_text())
        self.assertTrue(proof['closed'], proof)
        self.assertTrue(proof['forced'])
        self.assertEqual(proof['worker_returncode'], 0)
        self.assertNotEqual(proof['returncode'], 0)
        self.assertTrue(any(row['pid'] == orphan['pid'] for row in proof['owned_identities']))
        self.assertTrue(pg.verify_closed_proof(proof))

    def test_pid_reuse_is_never_signalled_or_reaped(self):
        guard = self.spawn('import time; time.sleep(30)')
        guard.poll()
        original_read = pg._read_process
        identity = guard.identity
        def replaced(pid):
            row = original_read(pid)
            if row and pid == identity['pid']:
                return {**row, 'birth': row['birth'] + 1}
            return row
        with mock.patch.object(pg, '_read_process', side_effect=replaced), \
                mock.patch.object(signal, 'pidfd_send_signal') as send, \
                mock.patch.object(os, 'waitid') as wait:
            self.assertFalse(guard._signal(identity, signal.SIGKILL))
            guard._reap()
            send.assert_not_called()
            wait.assert_not_called()
        # Restore the pinned root handle closed after the synthetic reuse view.
        key = pg._key(identity)
        guard._pidfds[key] = os.pidfd_open(identity['pid'])
        self.assertTrue(guard.stop(timeout=8)['closed'])

    def test_direct_child_without_prelaunch_ownership_fails_complete_proof(self):
        child = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(30)'])
        guard = pg.OwnedProcessGuard(child)
        self.guards.append(guard)
        proof = guard.stop(timeout=5)
        self.assertFalse(proof['ownership_complete'])
        self.assertFalse(proof['closed'])
        self.assertEqual(proof['remaining'], [])
        with self.assertRaises(ValueError):
            pg.verify_closed_proof(proof)

    def test_parent_death_stops_worker_and_detached_descendant(self):
        # A synthetic coordinator is the only process killed here. Its supervised
        # tree is adopted by this test subreaper, so all identified zombies reap.
        pg.enable_subreaper()
        evidence = self.root / 'parent-death'
        marker = self.root / 'death-leaf.json'
        leaf = ('import os,time,json; from pathlib import Path; '
                f'Path({str(marker)!r}).write_text(json.dumps({{"pid":os.getpid()}})); '
                'time.sleep(30)')
        worker = ('import subprocess,sys,time; '
                  f'subprocess.Popen([sys.executable,"-I","-c",{leaf!r}],start_new_session=True); '
                  'time.sleep(30)')
        coordinator_code = ('import sys,time; '
            f'sys.path.insert(0,{str(Path(pg.__file__).resolve().parents[2])!r}); '
            'from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard; '
            f'guard=OwnedProcessGuard.spawn([sys.executable,"-I","-c",{worker!r}],evidence_dir={str(evidence)!r}); '
            'time.sleep(30)')
        coordinator = subprocess.Popen([sys.executable, '-I', '-B', '-c', coordinator_code],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(coordinator)
        coordinator_guard = pg.OwnedProcessGuard(coordinator)
        self.guards.append(coordinator_guard)
        self.wait_for(marker.exists)
        coordinator_guard.poll()
        tracked = list(coordinator_guard._known.values())
        self.assertGreaterEqual(len(tracked), 4)
        coordinator.kill(); coordinator.wait(timeout=5)
        self.wait_for(lambda: (evidence / 'supervisor-result.json').exists())
        self.wait_for(lambda: (coordinator_guard.poll() is not None and not coordinator_guard._remaining()))
        result = json.loads((evidence / 'supervisor-result.json').read_text())
        self.assertTrue(result['closed'], result)
        self.assertTrue(result['forced'])
        self.assertNotEqual(result['worker_returncode'], 0)
        self.assertFalse(any(pg._same(pg._read_process(row['pid']), row) for row in tracked))

    def test_kernel_child_presence_blocks_empty_snapshot_closure(self):
        guard = self.spawn('pass')
        self.wait_guard(guard)
        # Emulate a process-table scan missing an already adopted child. A
        # non-reaping kernel presence check must still block complete closure.
        guard._scope = pg._identity(pg._read_process(os.getpid()))
        with mock.patch.object(guard, '_discover'), mock.patch.object(os, 'waitid', return_value=None):
            self.assertFalse(guard.closed_proof()['closed'])
        guard._scope = None

    def test_missing_supervisor_receipt_fails_closed(self):
        guard = self.spawn('pass')
        self.wait_guard(guard)
        (self.root / 'guard' / 'supervisor-result.json').unlink()
        proof = guard.closed_proof()
        self.assertFalse(proof['closed'])
        self.assertFalse(proof['ownership_complete'])
        self.assertTrue(proof['errors'])

    def test_fresh_verifier_rejects_any_live_incarnation(self):
        guard = self.spawn('pass')
        proof = self.wait_guard(guard)
        identity = proof['owned_identities'][-1]
        with mock.patch.object(pg, '_read_process', return_value={**identity, 'parent': os.getpid()}):
            with self.assertRaisesRegex(ValueError, 'still present'):
                pg.verify_closed_proof(proof)


if __name__ == '__main__':
    unittest.main()

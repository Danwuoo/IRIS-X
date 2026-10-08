"""CPU-only streaming, immutable publication, and real owned-process tests."""
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from tools import nvarc_uncapped_artifacts as artifacts


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir()

    def test_event_larger_than_old_single_and_whole_ledger_caps_is_complete(self):
        path = self.runtime / 'inference-events.jsonl'
        content = 'large untruncated observation\n' * 350000
        self.assertGreater(len(content), 8 * 1024**2)
        with artifacts.stream_events(path, {'run_id': 'uncapped', 'rank': 0}) as events:
            large = events.emit('observed', content=content)
            tail = events.emit('terminal', done=True)
            self.assertEqual(events.sequence, 2)
            self.assertEqual(events.head, tail['digest'])
        rows = artifacts.iter_events(path, {'run_id': 'uncapped', 'rank': 0})
        self.assertEqual(next(rows), large)
        self.assertEqual(next(rows), tail)
        with self.assertRaises(StopIteration):
            next(rows)
        self.assertGreater(path.stat().st_size, 8 * 1024**2)

    def test_events_reject_overrides_corruption_and_partial_tail_without_repair(self):
        path = self.runtime / 'events.jsonl'
        with artifacts.StreamEvents(path, {'run_id': 'one'}) as events:
            with self.assertRaisesRegex(ValueError, 'override'):
                events.emit('bad', sequence=0)
            events.emit('good')
        original = path.read_bytes()
        path.write_bytes(original + b'{"partial":')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            list(artifacts.iter_events(path, {'run_id': 'one'}))
        self.assertEqual(path.read_bytes(), original + b'{"partial":')
        path.write_bytes(original.replace(b'good', b'evil'))
        with self.assertRaisesRegex(ValueError, 'digest'):
            list(artifacts.iter_events(path, {'run_id': 'one'}))
        path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'binding'):
            list(artifacts.iter_events(path, {'run_id': 'other'}))
        with self.assertRaises(FileExistsError):
            artifacts.StreamEvents(path, {})

    def test_event_disk_failure_poisoned_writer_retains_tail(self):
        path = self.runtime / 'events.jsonl'
        events = artifacts.StreamEvents(path, {})
        self.addCleanup(events.close)
        with patch.object(artifacts.os, 'fsync', side_effect=OSError(errno.ENOSPC, 'disk full')):
            with self.assertRaises(OSError):
                events.emit('partially-durable', payload='all bytes retained')
        self.assertEqual(events.sequence, 0)
        self.assertTrue(events.failed)
        self.assertIn(b'all bytes retained', path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'failed'):
            events.emit('cannot-pretend-committed')

    def test_atomic_json_strict_parsing_and_full_diagnostic(self):
        path = self.runtime / 'result.json'
        artifacts.atomic_json(path, {'complete': True})
        self.assertEqual(artifacts.read_json(path), {'complete': True})
        self.assertEqual(artifacts.sha_file(path), hashlib.sha256(path.read_bytes()).hexdigest())
        path.write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            artifacts.read_json(path)
        message = 'evidence' * 200000
        try:
            raise RuntimeError(message)
        except RuntimeError as error:
            error.add_note('full trailing note')
            value = artifacts.full_diagnostic(error, 'finalize')
        self.assertEqual(value['message'], message)
        self.assertIn(message, value['traceback'])
        self.assertTrue(value['traceback'].endswith('full trailing note\n'))

    def test_atomic_json_disk_failure_preserves_existing_and_partial_temp(self):
        path = self.runtime / 'result.json'
        artifacts.atomic_json(path, {'old': True})
        before = path.read_bytes()
        with patch.object(artifacts.os, 'fsync', side_effect=OSError(errno.ENOSPC, 'disk full')):
            with self.assertRaises(OSError) as caught:
                artifacts.atomic_json(path, {'new': True})
        self.assertEqual(path.read_bytes(), before)
        partial = list(self.runtime.glob('result.json.*.tmp'))
        self.assertEqual(len(partial), 1)
        self.assertEqual(json.loads(partial[0].read_bytes()), {'new': True})
        self.assertIn('retained', '\n'.join(caught.exception.__notes__))

    def test_archive_streams_large_log_and_full_partial_evidence_with_zip64(self):
        path = self.runtime / 'coordinator-output.log'
        block = b'complete log\n' * 10000
        with path.open('wb') as output:
            for _ in range(70):
                output.write(block)
        self.assertGreater(path.stat().st_size, 8 * 1024**2)
        worker = self.runtime / 'workers/0/inference'
        worker.mkdir(parents=True)
        (worker / 'inference-events.jsonl').write_bytes(b'{"started":true}\n{"partial":')
        (worker / 'answer-checkpoint.json.0123456789abcdef0123456789abcdef.tmp').write_bytes(b'{"unfinished":')
        (self.runtime / 'result.json').write_text('{"correctness_scored":false,"contains_evaluator_truth":false}')
        destination = self.root / 'result.zip'
        # Force actual ZIP64 structures with a small *format threshold*, not a
        # production capacity. No multi-GiB allocation is needed to prove it.
        with patch.object(zipfile, 'ZIP64_LIMIT', 1024):
            receipt = artifacts.stream_archive(self.runtime, destination)
            verified = artifacts.verify_archive(destination, receipt['manifest'])
        self.assertTrue(receipt['stream_verified'])
        self.assertTrue(verified['verified'])
        self.assertEqual(receipt['archive_sha256'], artifacts.sha_file(destination))
        self.assertEqual(receipt['manifest_sha256'], artifacts.sha_file(receipt['manifest']))
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o400)
        with zipfile.ZipFile(destination) as archive:
            info = archive.getinfo('coordinator-output.log')
            self.assertEqual(info.extract_version, 45)
            self.assertEqual(archive.read(info), path.read_bytes())
            self.assertEqual(archive.read('workers/0/inference/inference-events.jsonl'),
                             b'{"started":true}\n{"partial":')
            self.assertEqual(archive.read(artifacts._MANIFEST), Path(receipt['manifest']).read_bytes())
        before = destination.read_bytes()
        with self.assertRaises(FileExistsError):
            artifacts.stream_archive(self.runtime, destination)
        self.assertEqual(destination.read_bytes(), before)

    def test_sparse_file_larger_than_old_tree_and_file_caps_is_streamed(self):
        # >512 MiB logical input, only a small compressed ZIP on disk. It also
        # exceeds historical 8/64 MiB per-file limits without a RAM fixture.
        large = self.runtime / 'training-trace.log'
        with large.open('wb') as output:
            output.seek(512 * 1024**2 + 123)
            output.write(b'FINAL-UNCROPPED-TAIL')
        receipt = artifacts.stream_archive(self.runtime, self.root / 'large.zip')
        self.assertEqual(receipt['bytes'], large.stat().st_size)
        self.assertLess(receipt['archive_bytes'], 1024**2)
        with zipfile.ZipFile(receipt['archive']) as archive:
            with archive.open('training-trace.log') as output:
                output.seek(large.stat().st_size - len(b'FINAL-UNCROPPED-TAIL'))
                self.assertEqual(output.read(), b'FINAL-UNCROPPED-TAIL')

    def test_member_count_and_tree_depth_exceed_historical_ceilings(self):
        directory = self.runtime
        for _ in range(40):
            directory = directory / 'level'
            directory.mkdir()
        (directory / 'deep.log').write_text('entire deep evidence')
        for index in range(4100):
            (self.runtime / f'evidence-{index}.log').touch()
        # Real ZIP64 count records with a patched ZIP format threshold.
        with patch.object(zipfile, 'ZIP_FILECOUNT_LIMIT', 32), \
             patch.object(Path, 'read_bytes', side_effect=AssertionError('no whole-body archive reads')):
            receipt = artifacts.stream_archive(self.runtime, self.root / 'many.zip')
        self.assertEqual(receipt['members'], 4101)
        self.assertTrue(receipt['stream_verified'])

    def test_archive_excludes_weights_dependencies_caches_and_credentials(self):
        for directory in ('models', 'wheels', 'workers/0/triton-cache', 'workers/0/unsloth_compiled_cache'):
            folder = self.runtime / directory
            folder.mkdir(parents=True)
            (folder / 'do-not-copy.txt').write_text('excluded')
        for name in ('model.safetensors', 'adapter.pt', 'kaggle.json', '.env'):
            (self.runtime / name).write_text('excluded')
        (self.runtime / 'terminal.json').write_text('{"status":"failed"}')
        receipt = artifacts.stream_archive(self.runtime, self.root / 'result.zip')
        self.assertEqual(receipt['members'], 1)
        self.assertEqual(receipt['excluded'], 8)
        with zipfile.ZipFile(receipt['archive']) as archive:
            self.assertEqual(set(archive.namelist()), {'terminal.json', artifacts._MANIFEST})

    def test_archive_rejects_symlinks_and_case_duplicate_and_unknown(self):
        (self.runtime / 'real.log').write_text('okay')
        bad = self.runtime / 'link.log'
        bad.symlink_to(self.runtime / 'real.log')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            artifacts.stream_archive(self.runtime, self.root / 'symlink.zip')
        bad.unlink()
        (self.runtime / 'REAL.log').write_text('case collision')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            artifacts.stream_archive(self.runtime, self.root / 'duplicate.zip')
        (self.runtime / 'REAL.log').unlink()
        (self.runtime / 'unknown.data').write_text('unapproved file')
        with self.assertRaisesRegex(ValueError, 'unrecognized'):
            artifacts.stream_archive(self.runtime, self.root / 'unknown.zip')

    def test_archive_denies_unsafe_names_and_truth_even_across_small_buffers(self):
        for name in ('/absolute', '../escape', 'a//b', 'a\\b', 'C:drive', 'a/./b', 'a\x00b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                artifacts.safe_name(name)
        path = self.runtime / 'terminal.json'
        for body in (b'{"expected_output":[[1]]}', b'{"expected_\\u006futput":1}',
                     b'{"contains_evaluator_truth":true}', b'{"correctness_scored":null}',
                     b'{"password":"do not archive"}'):
            path.write_bytes(body)
            with patch.object(artifacts, 'BLOCK', 1):
                with self.assertRaisesRegex(ValueError, 'forbidden'):
                    artifacts.stream_archive(self.runtime, self.root / ('bad-' + hashlib.sha256(body).hexdigest() + '.zip'))

    def test_symlink_ancestors_refused_before_read_write_or_archive(self):
        link = self.root / 'alias'
        link.symlink_to(self.runtime, target_is_directory=True)
        (self.runtime / 'x.json').write_text('{}')
        for action in (lambda: artifacts.read_json(link / 'x.json'),
                       lambda: artifacts.sha_file(link / 'x.json'),
                       lambda: artifacts.atomic_json(link / 'x.json', {}),
                       lambda: artifacts.stream_archive(link, self.root / 'a.zip')):
            with self.assertRaises(OSError):
                action()

    def test_archive_disk_failure_has_no_commit_and_retains_source_and_temps(self):
        path = self.runtime / 'coordinator-output.log'
        path.write_bytes(b'complete source never deleted')
        with patch.object(artifacts.os, 'fsync', side_effect=OSError(errno.ENOSPC, 'disk exhausted')):
            with self.assertRaises(OSError):
                artifacts.stream_archive(self.runtime, self.root / 'result.zip')
        self.assertEqual(path.read_bytes(), b'complete source never deleted')
        self.assertFalse((self.root / 'result.zip.receipt.json').exists())
        self.assertTrue(list(self.root.glob('*.tmp')))

    def test_forged_zip_traversal_and_duplicate_rejected(self):
        manifest = self.root / 'm.jsonl'
        manifest.write_text('{"format":"irisx/uncapped-manifest-v1"}\n')
        path = self.root / 'unsafe.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('../escape.log', b'bad')
        with self.assertRaisesRegex(ValueError, 'safe relative'):
            artifacts.verify_archive(path, manifest)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux owned /proc process tests')
class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, PYTHONHASHSEED='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        self.env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])

    def test_direct_complete_capture_exceeds_old_byte_ceilings(self):
        path = self.root / 'coordinator-output.log'
        size = 9 * 1024**2 + 137
        command = [sys.executable, '-c',
            f'import os; os.write(1,b"A"*{size}); os.write(2,b"STDERR-FULL-TAIL\\n")']
        result = artifacts.supervise(command, cwd=self.root, env=self.env, capture_path=path)
        self.assertTrue(result['success'], result)
        self.assertTrue(result['confirmed_stopped'])
        self.assertFalse(result['output_capture']['truncated'])
        self.assertEqual(path.stat().st_size, size + len(b'STDERR-FULL-TAIL\n'))
        with path.open('rb') as source:
            source.seek(size)
            self.assertEqual(source.read(), b'STDERR-FULL-TAIL\n')
        self.assertEqual(result['output_capture']['sha256'], artifacts.sha_file(path))

    def test_no_clock_or_wait_timeout_is_consulted(self):
        with patch.object(artifacts.time, 'time', side_effect=AssertionError('no clock deadlines')), \
             patch.object(artifacts.time, 'monotonic', side_effect=AssertionError('no clock deadlines')):
            result = artifacts.supervise([sys.executable, '-c', 'print("done")'],
                cwd=self.root, env=self.env, capture_path=self.root / 'output.log')
        self.assertTrue(result['success'], result)

    def test_cleanup_kills_owned_ignoring_term_group_and_reports_stop(self):
        process = subprocess.Popen([sys.executable, '-c',
            'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(9999)'],
            start_new_session=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        state = artifacts.owned_process_state(process, 'owned')
        report = artifacts.cleanup_workers([state])
        self.assertTrue(report['all_producers_stopped'])
        self.assertTrue(report['all_process_groups_absent'])
        self.assertIsNotNone(process.returncode)

    def test_cleanup_refuses_self_and_reused_pid_without_signalling(self):
        invalid = {'identity': 'bad', 'pid': os.getpid(), 'pgid': os.getpid(), 'session': os.getpid(),
            'start_new_session': True, 'start_ticks': 1, 'uid': os.getuid()}
        with patch.object(artifacts.os, 'killpg') as kill:
            with self.assertRaises(artifacts.CleanupError) as caught:
                artifacts.cleanup_workers([invalid])
        kill.assert_not_called()
        self.assertFalse(caught.exception.cleanup_report['all_producers_stopped'])
        process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(9999)'], start_new_session=True)
        state = artifacts.owned_process_state(process, 'owned')
        try:
            invalid = dict(state, start_ticks=state['start_ticks'] + 1)
            with patch.object(artifacts.os, 'killpg') as kill:
                with self.assertRaises(artifacts.CleanupError):
                    artifacts.cleanup_workers([invalid])
                kill.assert_not_called()
        finally:
            artifacts.cleanup_workers([state])

    def test_nonzero_exit_and_capture_disk_failure_never_succeed(self):
        result = artifacts.supervise([sys.executable, '-c', 'raise RuntimeError("complete error")'],
            cwd=self.root, env=self.env, capture_path=self.root / 'failure.log')
        self.assertFalse(result['success'])
        self.assertEqual(result['returncode'], 1)
        self.assertIn(b'RuntimeError: complete error', (self.root / 'failure.log').read_bytes())
        original = artifacts.os.fsync
        calls = []
        def fail_capture(fd):
            calls.append(fd)
            if len(calls) >= 4:
                raise OSError(errno.ENOSPC, 'capture disk exhausted')
            return original(fd)
        with patch.object(artifacts.os, 'fsync', side_effect=fail_capture):
            result = artifacts.supervise([sys.executable, '-c', 'print("retained")'],
                cwd=self.root, env=self.env, capture_path=self.root / 'disk.log')
        self.assertFalse(result['success'])
        self.assertTrue(result['supervision_failed'])
        self.assertFalse(result['output_capture']['written'])
        self.assertIn(b'retained', (self.root / 'disk.log').read_bytes())

    def test_bad_registry_never_claims_stop_even_after_zero_exit(self):
        for index, tail in enumerate((b'{"unfinished":', b'not-json\n',
                                      b'{"ownership_nonce":"foreign"}\n')):
            command = [sys.executable, '-c',
                'import os; '                'p=os.environ["IRISX_UNCAPPED_WORKER_REGISTRY"]; '                f'open(p,"ab").write({tail!r})']
            result = artifacts.supervise(command, cwd=self.root, env=self.env,
                capture_path=self.root / f'bad-registry-{index}.log')
            self.assertEqual(result['returncode'], 0)
            self.assertFalse(result['confirmed_stopped'], result)
            self.assertFalse(result['success'])
            self.assertTrue(any(error['phase'] == 'worker-registry' for error in result['errors']))
            self.assertTrue(Path(result['worker_registry']).read_bytes().endswith(tail))

    def test_bad_registry_tail_still_cleans_valid_registered_prefix(self):
        code = """import os,subprocess,sys
from tools.nvarc_uncapped_artifacts import owned_process_state,register_worker
worker='from tools.nvarc_uncapped_artifacts import await_worker_registration; await_worker_registration(); import time; time.sleep(9999)'
p=subprocess.Popen([sys.executable,'-c',worker],start_new_session=True)
register_worker(owned_process_state(p,'registered-before-bad-tail'))
with open(os.environ['IRISX_UNCAPPED_WORKER_REGISTRY'],'ab') as out:
    out.write(b'{"partial":')
"""
        result = artifacts.supervise([sys.executable, '-c', code], cwd=self.root,
            env=self.env, capture_path=self.root / 'bad-tail.log')
        self.assertEqual(result['returncode'], 0)
        self.assertFalse(result['confirmed_stopped'], result)
        self.assertFalse(result['success'])
        cleanup = result['worker_cleanup']
        self.assertEqual(len(cleanup['workers']), 1)
        self.assertTrue(cleanup['all_producers_stopped'])
        row = cleanup['workers'][0]
        observed = artifacts._process_identity(row['pid'])
        self.assertTrue(observed is None or observed['state'] in {'Z', 'X'})

    def test_owner_cancellation_cleans_registered_worker_and_descendant(self):
        # Separate supervisor process permits a real SIGTERM without signalling
        # the test runner. The worker creates a same-group grandchild only after
        # durable registry admission; coordinator and worker ignore TERM.
        worker = self.root / 'worker.py'
        worker.write_text('''import os,signal,subprocess,sys,time
from pathlib import Path
from tools.nvarc_uncapped_artifacts import await_worker_registration
await_worker_registration()
signal.signal(signal.SIGTERM,signal.SIG_IGN)
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(9999)'])
Path('worker-pids.json').write_text(__import__('json').dumps([os.getpid(),p.pid]))
while True: time.sleep(1)
''')
        coordinator = self.root / 'coordinator.py'
        coordinator.write_text('''import signal,subprocess,sys,time
from tools.nvarc_uncapped_artifacts import owned_process_state,register_worker
signal.signal(signal.SIGTERM,signal.SIG_IGN)
p=subprocess.Popen([sys.executable,'worker.py'],start_new_session=True)
state=owned_process_state(p,'worker-0')
register_worker(state)
while True: time.sleep(1)
''')
        supervisor = self.root / 'supervisor.py'
        supervisor.write_text('''import os,sys
from tools.nvarc_uncapped_artifacts import supervise,atomic_json
result=supervise([sys.executable,'coordinator.py'],cwd='.',env=os.environ,capture_path='output.log')
atomic_json('receipt.json',result)
''')
        process = subprocess.Popen([sys.executable, str(supervisor)], cwd=self.root,
            env=self.env, start_new_session=True)
        pids = []
        try:
            # This is a test-harness hang guard, not a runtime program cap.
            deadline = time.monotonic() + 15
            while not (self.root / 'worker-pids.json').exists():
                self.assertIsNone(process.poll())
                self.assertLess(time.monotonic(), deadline, 'CPU fixture did not become ready')
                time.sleep(.02)
            pids = json.loads((self.root / 'worker-pids.json').read_text())
            os.kill(process.pid, signal.SIGTERM)
            self.assertEqual(process.wait(timeout=15), 0)
            result = artifacts.read_json(self.root / 'receipt.json')
            self.assertTrue(result['cancelled'], result)
            self.assertTrue(result['confirmed_stopped'], result)
            self.assertFalse(result['success'])
            for pid in pids:
                observed = artifacts._process_identity(pid)
                self.assertTrue(observed is None or observed['state'] in {'Z', 'X'})
            self.assertTrue(result['worker_cleanup']['all_producers_stopped'])
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            for pid in pids:
                observed = artifacts._process_identity(pid)
                if observed and observed['state'] not in {'Z', 'X'}:
                    os.kill(pid, signal.SIGKILL)


if __name__ == '__main__':
    unittest.main()

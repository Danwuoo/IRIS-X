"""Offline stdlib fixtures only; real child processes, never a real installer."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import tracemalloc
import types
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FROZEN = REPO / 'tools/arc_qwen_transfer_deployment_20261012/bootstrap.py'
ORIGINAL_SHA256 = '4ddac4166b154e1506fb029373b14297f7b0bfc7c87f37d9e83bcb9f554909f8'
GUARD = REPO / 'tools/arc_learning_agent_20261011/process_guard.py'


def load(name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                 optimize=sys.flags.optimize), vars(module))
    return module


def python():
    return [sys.executable, '-I', '-B', *(['-O'] if sys.flags.optimize else [])]


def identity():
    return {'pid': os.getpid(), 'parent': os.getppid(), 'session': os.getsid(0)}


def synthetic_installer(kind, root):
    """Fixed local bytes/controlled waits; no package, network or model imports."""
    root = Path(root)
    (root / 'installer-identity.json').write_text(json.dumps(identity()))
    if kind.startswith('descendant-'):
        # Double fork plus setsid exercises the existing owner's subreaper,
        # rather than depending on a process group or the immediate Popen PID.
        child = os.fork()
        if child == 0:
            os.setsid()
            grandchild = os.fork()
            if grandchild:
                os._exit(0)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            (root / 'descendant-identity.json').write_text(json.dumps(identity()))
            if kind == 'descendant-closed-pipe':
                os.close(1); os.close(2)
            time.sleep(30)
            os._exit(0)
        os.waitpid(child, 0)
        deadline = time.monotonic() + 3
        while not (root / 'descendant-identity.json').exists():
            if time.monotonic() >= deadline:
                raise RuntimeError('synthetic descendant handshake failed')
            time.sleep(0.005)
    if kind == 'environment':
        raw = json.dumps({'flags': {k: os.environ.get(k) for k in
                          ('HF_HUB_OFFLINE', 'HF_DATASETS_OFFLINE', 'TRANSFORMERS_OFFLINE',
                           'PYTHONDONTWRITEBYTECODE')},
                          'isolated': sys.flags.isolated, 'optimize': sys.flags.optimize}).encode()
        os.write(1, raw)
    elif kind in ('success', 'short-write'):
        for _ in range(64):
            os.write(1, b'OUT\x00\xff\n'); os.write(2, b'ERR\x80\n')
    elif kind == 'nonzero':
        os.write(1, b'before failure\n'); os.write(2, b'synthetic failure\n')
        raise SystemExit(37)
    elif kind in ('exact-cap', 'overflow', 'overflow-exit-zero', 'descendant-overflow'):
        for _ in range(128):
            os.write(1, b'X' * 32768); os.write(2, b'X' * 32768)
        if kind != 'exact-cap':
            os.write(2, b'!')
            if kind != 'overflow-exit-zero':
                time.sleep(30)
    elif kind in ('timeout', 'descendant-timeout'):
        os.write(2, b'before timeout\n')
        time.sleep(30)
    elif kind == 'closed-pipe-timeout':
        os.close(1); os.close(2); time.sleep(30)
    elif kind in ('descendant-held-pipe', 'descendant-closed-pipe'):
        os.write(1, b'parent exits\n')
    elif kind in ('write-error', 'zero-write', 'flush-error'):
        os.write(1, b'synthetic I/O bytes\n')
        if kind != 'flush-error':
            time.sleep(30)
    elif kind != 'empty':
        raise ValueError('unknown synthetic case')


class RecordingWriter:
    """A test sink boundary, never installed into any production module."""
    def __init__(self, stream, kind):
        self.stream = stream
        self.kind = kind
        self.maximum_write = 0

    def write(self, block):
        self.maximum_write = max(self.maximum_write, len(block))
        if self.kind == 'zero-write':
            return 0
        if self.kind == 'short-write':
            return self.stream.write(block[:7])
        return self.stream.write(block)

    def flush(self):
        if self.kind == 'flush-error':
            raise OSError('synthetic flush failure')
        return self.stream.flush()


def fixture_driver(kind, root):
    root = Path(root)
    overlay = load('installer_overlay_fixture', HERE / 'bootstrap.py')
    duration = 0.4 if 'timeout' in kind or kind == 'descendant-held-pipe' else 5
    request = {'started_epoch': time.time() - 43000,
               'execution_deadline_epoch': time.time() + overlay.OUTER_RESERVE_SECONDS + duration,
               'hard_deadline_epoch': time.time() + overlay.OUTER_RESERVE_SECONDS + duration + 60}
    if kind == 'expired':
        request['execution_deadline_epoch'] = time.time() + overlay.OUTER_RESERVE_SECONDS - 1
    if kind == 'hard-deadline':
        request['hard_deadline_epoch'] = time.time() + overlay.OUTER_RESERVE_SECONDS + 0.4
    before = copy.deepcopy(request)
    argv = python() + [str(Path(__file__).resolve()), '--synthetic-installer',
                      'timeout' if kind == 'hard-deadline' else kind, str(root)]
    if kind == 'spawn-error':
        argv = [str(root / 'deliberately-missing-interpreter')]
    path = root / 'installation.log'
    if kind == 'write-error':
        path.write_bytes(b'original-read-only-log')
    started = time.monotonic()
    outcome = {'request_before': before, 'driver_identity': identity()}
    tracemalloc.start()
    writer = None
    try:
        with path.open('rb' if kind == 'write-error' else 'xb') as stream:
            writer = RecordingWriter(stream, kind)
            completed = overlay.run_installer_bounded(argv, log=writer, request=request, env={
                **os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'HF_HUB_OFFLINE': '1',
                'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1'})
        outcome['returncode'] = completed.returncode
        overlay.require(completed.returncode == 0, 'offline installation child failed; inspect installation.log')
        outcome['status'] = 'success'
    except BaseException as error:
        outcome.update(status='failed', exception_type=type(error).__name__, message=str(error))
        raise
    finally:
        outcome.update(elapsed_seconds=time.monotonic() - started,
                       peak_traced_bytes=tracemalloc.get_traced_memory()[1],
                       maximum_write_bytes=None if writer is None else writer.maximum_write,
                       request_after=request)
        tracemalloc.stop()
        (root / 'fixture-result.json').write_text(json.dumps(outcome, sort_keys=True))


class SourceParityTests(unittest.TestCase):
    def test_frozen_bootstrap_has_not_changed(self):
        self.assertEqual(hashlib.sha256(FROZEN.read_bytes()).hexdigest(), ORIGINAL_SHA256)

    def test_entire_original_ast_except_bounded_child_call_is_unchanged(self):
        original = ast.parse(FROZEN.read_bytes())
        overlay = ast.parse((HERE / 'bootstrap.py').read_bytes())
        new_functions = {'_installer_time_left', '_installer_cleanup', 'run_installer_bounded'}
        new_constants = {'INSTALL_LOG_BYTES', 'INSTALL_READ_BYTES', 'INSTALL_POLL_SECONDS'}
        retained = []
        removed = []
        for node in overlay.body:
            if (isinstance(node, ast.FunctionDef) and node.name in new_functions or
                isinstance(node, ast.Import) and [a.name for a in node.names] in (['math'], ['selectors']) or
                isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in new_constants for t in node.targets)):
                removed.append(node)
            else:
                retained.append(node)
        self.assertEqual(len(removed), 8)
        overlay.body = retained
        old_function = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare_environment')
        new_function = next(n for n in overlay.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare_environment')
        old_call = next(n for n in ast.walk(old_function) if isinstance(n, ast.Call) and ast.unparse(n.func) == 'subprocess.run')
        new_call = next(n for n in ast.walk(new_function) if isinstance(n, ast.Call) and ast.unparse(n.func) == 'run_installer_bounded')
        self.assertEqual(ast.dump(ast.List(elts=old_call.args)), ast.dump(ast.List(elts=new_call.args)))
        old_keywords = {k.arg: k.value for k in old_call.keywords}
        new_keywords = {k.arg: k.value for k in new_call.keywords}
        self.assertEqual(set(old_keywords), {'stdout', 'stderr', 'timeout', 'check', 'env'})
        self.assertEqual(set(new_keywords), {'log', 'request', 'env'})
        self.assertEqual(ast.dump(new_keywords['env']), ast.dump(old_keywords['env']))
        self.assertEqual(ast.unparse(new_keywords['log']), 'log')
        self.assertEqual(ast.unparse(new_keywords['request']), 'request')
        new_call.func = old_call.func
        new_call.keywords = old_call.keywords
        self.assertEqual(ast.dump(overlay), ast.dump(original))

    def test_runner_keeps_the_enclosing_tree_and_has_no_unbounded_capture(self):
        tree = ast.parse((HERE / 'bootstrap.py').read_bytes())
        helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_installer_bounded')
        calls = [n for n in ast.walk(helper) if isinstance(n, ast.Call)]
        popen = [n for n in calls if ast.unparse(n.func) == 'subprocess.Popen']
        self.assertEqual(len(popen), 1)
        options = {k.arg: ast.literal_eval(k.value) for k in popen[0].keywords
                   if k.arg in ('close_fds', 'start_new_session', 'bufsize')}
        self.assertEqual(options, {'close_fds': True, 'start_new_session': False, 'bufsize': 0})
        forbidden = {'subprocess.run', 'os.setsid', 'os.setpgid', 'os.killpg', 'time.sleep'}
        self.assertTrue(forbidden.isdisjoint({ast.unparse(n.func) for n in calls}))
        self.assertFalse(any(isinstance(n.func, ast.Attribute) and n.func.attr in ('communicate', 'read', 'readlines')
                             and ast.unparse(n.func) != 'os.read' for n in calls))


class DeadlineTests(unittest.TestCase):
    def setUp(self):
        self.module = load('installer_clock_tests', HERE / 'bootstrap.py')

    def test_wall_forward_and_monotonic_limit_both_fail_closed(self):
        for wall, mono in ((100, 49), (99, 50), (1000, 40), (-1000, 50)):
            with self.subTest(wall=wall, mono=mono), self.assertRaises(TimeoutError):
                self.module._installer_time_left(100, 50, wall, mono)

    def test_wall_rollback_never_extends_original_mapped_budget(self):
        self.assertEqual(self.module._installer_time_left(100, 50, 90, 45), 5)
        self.assertEqual(self.module._installer_time_left(100, 50, -1000, 45), 5)
        self.assertEqual(self.module._installer_time_left(100, 50, 99, 45), 1)

    def test_nonfinite_clocks_rejected(self):
        for index in range(4):
            for bad in (float('inf'), float('-inf'), float('nan')):
                row = [100, 50, 90, 45]; row[index] = bad
                with self.subTest(index=index, bad=bad), self.assertRaises(ValueError):
                    self.module._installer_time_left(*row)


class CleanupBoundaryTests(unittest.TestCase):
    """Fault objects call the cleanup seam directly; no production patching."""
    def setUp(self):
        self.module = load('installer_cleanup_tests', HERE / 'bootstrap.py')

    def child(self, *, kill_error=None, wait_error=None, close_error=None):
        calls = []
        class Pipe:
            def close(self):
                calls.append('close')
                if close_error is not None:
                    raise close_error
        class Child:
            stdout = Pipe()
            def poll(self):
                calls.append('poll'); return None
            def kill(self):
                calls.append('kill')
                if kill_error is not None:
                    raise kill_error
            def wait(self, timeout):
                calls.append(('wait', timeout))
                if wait_error is not None:
                    raise wait_error
                return -9
        return Child(), calls

    def test_pipe_close_preserves_original_error(self):
        original = ValueError('original overflow')
        child, calls = self.child(close_error=OSError('close failed'))
        self.assertIs(self.module._installer_cleanup(child, original), original)
        self.assertEqual(calls, ['poll', 'kill', ('wait', 1), 'close'])
        self.assertIn('pipe close also failed', original.__notes__[0])

    def test_pipe_close_fault_after_success_is_returned_as_failure(self):
        original = OSError('close failed')
        child, calls = self.child(close_error=original)
        self.assertIs(self.module._installer_cleanup(child, None), original)
        self.assertEqual(calls, ['close'])

    def test_kill_or_wait_fault_preserves_original_and_still_closes_pipe(self):
        for kind in ('kill_error', 'wait_error'):
            original = TimeoutError('original timeout')
            child, calls = self.child(**{kind: OSError('cleanup failed')})
            self.assertIs(self.module._installer_cleanup(child, original), original)
            self.assertEqual(calls[-1], 'close')
            self.assertIn('direct-child cleanup failed', original.__notes__[0])

    def test_add_note_fault_cannot_hide_original_or_prevent_pipe_close(self):
        class ImmutableError(ValueError):
            def add_note(self, text):
                raise RuntimeError('cannot annotate')
        original = ImmutableError('original failure')
        child, calls = self.child(kill_error=OSError('kill failed'), close_error=OSError('close failed'))
        self.assertIs(self.module._installer_cleanup(child, original), original)
        self.assertEqual(calls, ['poll', 'kill', 'close'])
        self.assertEqual(str(original), 'original failure')

    def test_success_cleanup_has_no_failure(self):
        child, calls = self.child()
        self.assertIsNone(self.module._installer_cleanup(child, None))
        self.assertEqual(calls, ['close'])
        self.assertIsNone(self.module._installer_cleanup(None, None))


@unittest.skipUnless(sys.platform == 'linux', 'actual Linux owned-process guard required')
class RealOwnedInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.pg = load('actual_installer_test_process_guard', GUARD)
        self.guards = []

    def tearDown(self):
        for guard in self.guards:
            if guard.poll() is None or guard._remaining():
                guard.stop(timeout=5)
        self.temporary.cleanup()

    def run_case(self, kind):
        root = self.root / kind; root.mkdir()
        with (root / 'fixture-driver.log').open('xb') as log:
            guard = self.pg.OwnedProcessGuard.spawn(
                python() + [str(Path(__file__).resolve()), '--fixture-driver', kind, str(root)],
                evidence_dir=root / 'owned-tree', stdout=log, stderr=log, env=dict(os.environ))
            self.guards.append(guard)
            deadline = time.monotonic() + 12
            while guard.poll() is None:
                if time.monotonic() >= deadline:
                    guard.stop(timeout=5)
                    self.fail('synthetic owned fixture exceeded its test deadline')
                time.sleep(0.01)
            proof = guard.closed_proof()
        self.assertTrue(self.pg.verify_closed_proof(proof))
        self.assertEqual(proof['remaining'], [])
        self.assertEqual(proof['errors'], [])
        self.assertTrue(proof['ownership_complete'])
        result = json.loads((root / 'fixture-result.json').read_bytes())
        self.assertEqual(result['request_before'], result['request_after'])
        marker = root / 'installer-identity.json'
        if marker.exists():
            installer = json.loads(marker.read_bytes())
            self.assertEqual(installer['session'], result['driver_identity']['session'])
            self.assertEqual(installer['parent'], result['driver_identity']['pid'])
            self.assertFalse(Path('/proc', str(installer['pid'])).exists())
        return root, result, proof

    def assert_failed(self, result, proof, exception_type, phrase):
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['exception_type'], exception_type)
        self.assertIn(phrase, result['message'])
        self.assertNotEqual(proof['worker_returncode'], 0)
        self.assertNotEqual(proof['returncode'], 0)

    def test_success_preserves_complete_combined_binary_log(self):
        root, result, proof = self.run_case('success')
        self.assertEqual(result['status'], 'success')
        self.assertEqual((root / 'installation.log').read_bytes(), (b'OUT\x00\xff\nERR\x80\n') * 64)
        self.assertEqual(proof['returncode'], 0)
        self.assertFalse(proof['forced'])

    def test_empty_log_success(self):
        root, result, proof = self.run_case('empty')
        self.assertEqual(result['status'], 'success')
        self.assertEqual((root / 'installation.log').stat().st_size, 0)
        self.assertEqual(proof['returncode'], 0)

    def test_nonzero_is_failure_with_complete_log(self):
        root, result, proof = self.run_case('nonzero')
        self.assert_failed(result, proof, 'ValueError', 'child failed')
        self.assertEqual(result['returncode'], 37)
        self.assertEqual((root / 'installation.log').read_bytes(), b'before failure\nsynthetic failure\n')

    def test_exact_cap_succeeds_with_bounded_memory(self):
        root, result, proof = self.run_case('exact-cap')
        self.assertEqual(result['status'], 'success')
        self.assertEqual((root / 'installation.log').stat().st_size, 8 * 1024**2)
        self.assertEqual(hashlib.sha256((root / 'installation.log').read_bytes()).hexdigest(),
                         hashlib.sha256(b'X' * (8 * 1024**2)).hexdigest())
        self.assertLess(result['peak_traced_bytes'], 1024**2)
        self.assertLessEqual(result['maximum_write_bytes'], 64 * 1024)
        self.assertEqual(proof['returncode'], 0)

    def test_overflow_fails_without_writing_byte_beyond_cap(self):
        root, result, proof = self.run_case('overflow')
        self.assert_failed(result, proof, 'ValueError', 'byte ceiling exceeded')
        self.assertEqual((root / 'installation.log').stat().st_size, 8 * 1024**2)
        self.assertEqual((root / 'installation.log').read_bytes(), b'X' * (8 * 1024**2))
        self.assertLess(result['peak_traced_bytes'], 1024**2)

    def test_overflow_cannot_be_success_even_if_producer_exits_zero(self):
        root, result, proof = self.run_case('overflow-exit-zero')
        self.assert_failed(result, proof, 'ValueError', 'byte ceiling exceeded')
        self.assertEqual((root / 'installation.log').read_bytes(), b'X' * (8 * 1024**2))

    def test_timeouts_with_open_and_closed_pipes(self):
        for kind in ('timeout', 'closed-pipe-timeout', 'hard-deadline'):
            with self.subTest(kind=kind):
                root, result, proof = self.run_case(kind)
                self.assert_failed(result, proof, 'TimeoutError', 'original deadline reserve reached')
                self.assertLess(result['elapsed_seconds'], 2)
                if kind != 'closed-pipe-timeout':
                    self.assertEqual((root / 'installation.log').read_bytes(), b'before timeout\n')

    def test_expired_original_deadline_never_starts_installer(self):
        root, result, proof = self.run_case('expired')
        self.assert_failed(result, proof, 'ValueError', 'absolute probe deadline reserve reached')
        self.assertFalse((root / 'installer-identity.json').exists())

    def test_spawn_failure_propagates(self):
        root, result, proof = self.run_case('spawn-error')
        self.assert_failed(result, proof, 'FileNotFoundError', 'deliberately-missing-interpreter')
        self.assertFalse((root / 'installer-identity.json').exists())

    def test_real_read_only_file_write_failure_cleans_child(self):
        root, result, proof = self.run_case('write-error')
        self.assert_failed(result, proof, 'UnsupportedOperation', 'write')
        self.assertEqual((root / 'installation.log').read_bytes(), b'original-read-only-log')

    def test_short_writes_preserve_all_bytes(self):
        root, result, proof = self.run_case('short-write')
        self.assertEqual(result['status'], 'success')
        self.assertEqual((root / 'installation.log').read_bytes(), (b'OUT\x00\xff\nERR\x80\n') * 64)
        self.assertEqual(proof['returncode'], 0)

    def test_zero_progress_and_flush_io_failure_are_not_success(self):
        for kind, phrase in (('zero-write', 'valid progress'), ('flush-error', 'synthetic flush failure')):
            with self.subTest(kind=kind):
                root, result, proof = self.run_case(kind)
                self.assert_failed(result, proof, 'OSError', phrase)
                self.assertLessEqual((root / 'installation.log').stat().st_size, 8 * 1024**2)

    def test_double_fork_setsid_descendants_are_closed_on_failures(self):
        for kind in ('descendant-overflow', 'descendant-timeout', 'descendant-held-pipe'):
            with self.subTest(kind=kind):
                root, result, proof = self.run_case(kind)
                self.assertEqual(result['status'], 'failed')
                leaf = json.loads((root / 'descendant-identity.json').read_bytes())
                self.assertNotEqual(leaf['session'], result['driver_identity']['session'])
                self.assertFalse(Path('/proc', str(leaf['pid'])).exists())
                self.assertTrue(any(row['pid'] == leaf['pid'] for row in proof['owned_identities']))
                self.assertTrue(proof['forced'])

    def test_surviving_closed_pipe_descendant_cannot_create_outer_success(self):
        root, result, proof = self.run_case('descendant-closed-pipe')
        self.assertEqual(result['status'], 'success')
        self.assertEqual(proof['worker_returncode'], 0)
        self.assertTrue(proof['forced'])
        self.assertNotEqual(proof['returncode'], 0)
        leaf = json.loads((root / 'descendant-identity.json').read_bytes())
        self.assertFalse(Path('/proc', str(leaf['pid'])).exists())
        self.assertTrue(any(row['pid'] == leaf['pid'] for row in proof['owned_identities']))

    def test_offline_environment_and_isolated_python_are_preserved(self):
        root, result, proof = self.run_case('environment')
        self.assertEqual(result['status'], 'success')
        record = json.loads((root / 'installation.log').read_bytes())
        self.assertEqual(set(record['flags'].values()), {'1'})
        self.assertEqual(record['isolated'], 1)
        self.assertEqual(record['optimize'], sys.flags.optimize)
        self.assertEqual(proof['returncode'], 0)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--synthetic-installer':
        synthetic_installer(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == '--fixture-driver':
        fixture_driver(sys.argv[2], sys.argv[3])
    else:
        unittest.main()

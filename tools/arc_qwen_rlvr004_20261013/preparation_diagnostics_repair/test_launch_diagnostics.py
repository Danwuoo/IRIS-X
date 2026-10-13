"""LOCAL RECONSTRUCTION: bounded projections and real owned-child CPU tests.

The original final launcher test bytes were not recovered. This file uses the
recovered earlier test suite and the independently marked final-lines123-148
fragment, then adds focused deadline/log regressions for the recovered launcher.
Synthetic source/request markers below are unit fixtures, never release evidence.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRATCH = REPO / '.irisx/run006-local/diagnostics-tests'
SCRATCH.mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True


def load(name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ''
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


launch = load('diagnostic_overlay_launch_tests', HERE / 'launch_notebook.py')
guard = load('diagnostic_overlay_guard_tests', REPO / 'tools/arc_learning_agent_20261011/process_guard.py')
CONTEXT = {'source_sha256': 'a' * 64, 'request_sha256': 'b' * 64, 'original_epoch': 1234567890}


def report():
    return {'format': 'irisx/rlvr-preparation-failure-v1', 'status': 'FAILED',
            'stage': 'offline-installation', 'exception_type': 'ValueError',
            'source_sha256': CONTEXT['source_sha256'], 'request_sha256': CONTEXT['request_sha256'],
            'source_authenticated': True, 'installer_log': None, 'diagnostic_only': True,
            'closure_authority': False, 'model_or_GPU_execution_claim': False,
            'scoring_authority': False, 'operational_success': False}


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'preparation-failure.json'

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, document=None):
        raw = (json.dumps(report() if document is None else document, sort_keys=True) + '\n').encode()
        self.path.write_bytes(raw)
        return raw

    def read(self, context=None):
        return launch.read_preparation_failure(self.root, CONTEXT if context is None else context)

    def test_context_bound_safe_projection(self):
        raw = self.write()
        result = self.read()
        self.assertEqual(result['stage'], 'offline-installation')
        self.assertEqual(result['report_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertFalse(result['closure_authority'])
        self.assertFalse(result['model_or_GPU_execution_claim'])
        self.assertNotIn('installer_log', result)

    def test_absent_is_unknown(self):
        self.assertIsNone(self.read())

    def test_mismatched_context_or_unverified_hash_is_unknown(self):
        self.write()
        for key, value in (('source_sha256', 'c' * 64), ('request_sha256', 'c' * 64),
                           ('source_sha256', None), ('request_sha256', 'BAD')):
            with self.subTest(key=key, value=value):
                self.assertIsNone(self.read({**CONTEXT, key: value}))

    def test_enum_and_authority_claims_rejected(self):
        for key, value in [('stage', 'SYNTHETIC_SECRET'), ('exception_type', 'CustomSecretException'),
                           ('status', 'PASS'), ('format', 'other'), ('source_authenticated', 1),
                           ('diagnostic_only', False), ('closure_authority', True),
                           ('model_or_GPU_execution_claim', True), ('scoring_authority', True),
                           ('operational_success', True)]:
            with self.subTest(key=key):
                document = report(); document[key] = value
                self.write(document)
                self.assertIsNone(self.read())

    def test_trailing_payload_and_duplicate_keys_rejected(self):
        raw = self.write()
        for bad in (raw + b'{}', b'{"status":"FAILED","status":"FAILED"}', b'{"unused":NaN}', b'null', b'[]'):
            with self.subTest(raw=bad[:30]):
                self.path.write_bytes(bad)
                self.assertIsNone(self.read())

    def test_extra_untrusted_fields_never_projected_or_displayed(self):
        document = report()
        document['private_exception_text'] = 'SYNTHETIC_SECRET_EVALUATOR_PATH'
        document['installer_log'] = {'path': '/synthetic/private'}
        self.write(document)
        error = RuntimeError('outer')
        result = launch.annotate_preparation_failure(error, self.root, CONTEXT)
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(result))
        self.assertNotIn('/synthetic/private', '\n'.join(error.__notes__))
        self.assertEqual(str(error), 'outer')

    def test_symlink_and_hardlink_rejected(self):
        target = self.root / 'target'
        target.write_text(json.dumps(report()))
        self.path.symlink_to(target)
        self.assertIsNone(self.read())
        self.path.unlink(); os.link(target, self.path)
        self.assertIsNone(self.read())

    def test_linked_parent_rejected(self):
        directory = self.root / 'real'; directory.mkdir()
        (directory / self.path.name).write_text(json.dumps(report()))
        link = self.root / 'link'; link.symlink_to(directory, target_is_directory=True)
        self.assertIsNone(launch.read_preparation_failure(link, CONTEXT))

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX FIFO required')
    def test_fifo_rejected_without_open_or_blocking(self):
        os.mkfifo(self.path)
        original = os.open
        leaf_opens = []
        def opening(path, flags, *args, **kwargs):
            if path == self.path.name:
                leaf_opens.append(path)
                raise AssertionError('must not open FIFO leaf')
            return original(path, flags, *args, **kwargs)
        with patch.object(launch.os, 'open', opening):
            self.assertIsNone(self.read())
        self.assertEqual(leaf_opens, [])

    def test_directory_and_oversize_rejected(self):
        self.path.mkdir(); self.assertIsNone(self.read()); self.path.rmdir()
        self.path.write_bytes(b'x' * (launch.FAILURE_BYTES + 1))
        original = os.open
        leaf_opens = []
        def opening(path, flags, *args, **kwargs):
            if path == self.path.name:
                leaf_opens.append(path)
                raise AssertionError('oversize leaf must not open')
            return original(path, flags, *args, **kwargs)
        with patch.object(launch.os, 'open', opening):
            self.assertIsNone(self.read())
        self.assertEqual(leaf_opens, [])

    def test_mutation_during_read_rejected(self):
        self.write()
        original = os.read
        changed = False
        def reading(fd, count):
            nonlocal changed
            raw = original(fd, count)
            if not changed:
                changed = True
                self.path.write_bytes(self.path.read_bytes() + b' ')
            return raw
        with patch.object(launch.os, 'read', reading):
            self.assertIsNone(self.read())

    def test_replacement_during_read_rejected(self):
        raw = self.write()
        replacement = self.root / 'replacement'; replacement.write_bytes(raw)
        original = os.read
        changed = False
        def reading(fd, count):
            nonlocal changed
            result = original(fd, count)
            if not changed:
                changed = True; os.replace(replacement, self.path)
            return result
        with patch.object(launch.os, 'read', reading):
            self.assertIsNone(self.read())

    def test_rejected_report_note_stays_generic(self):
        self.path.write_bytes(b'SYNTHETIC_SECRET')
        error = ValueError('original')
        self.assertIsNone(launch.annotate_preparation_failure(error, self.root, CONTEXT))
        self.assertEqual(str(error), 'original')
        self.assertIn('unavailable or unverified', error.__notes__[0])
        self.assertNotIn('SYNTHETIC_SECRET', error.__notes__[0])

    def test_error_without_add_note_is_preserved(self):
        self.write()
        class ImmutableError(RuntimeError):
            def add_note(self, value):
                raise OSError('synthetic note failure')
        error = ImmutableError('original')
        self.assertEqual(launch.annotate_preparation_failure(error, self.root, CONTEXT)['stage'], 'offline-installation')
        self.assertEqual(str(error), 'original')


@unittest.skipUnless(sys.platform == 'linux', 'actual Linux pidfd/subreaper guard required')
class RealOwnedChildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.tmp.name)
        self.stage = self.root / 'preparation'

    def tearDown(self):
        self.tmp.cleanup()

    def run_child(self, code, **changes):
        args = {'guard_module': guard, 'directory': self.stage, 'deadline_epoch': time.time() + 45,
                'env': {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'},
                'scope': 'entire-owned-preparation-and-runtime', 'failure_context': CONTEXT}
        args.update(changes)
        return launch.run_bounded([sys.executable, '-I', '-B',
                                   *(['-O'] if sys.flags.optimize else []), '-c', code], **args)

    def assert_closed(self):
        proof = json.loads((self.stage / 'owned-tree/closure.json').read_bytes())
        guard.verify_closed_proof(proof)
        self.assertTrue(proof['closed'])
        self.assertFalse(proof['remaining'])
        return proof

    def test_success_unchanged_no_failure_artifact(self):
        receipt = self.run_child('print("synthetic CPU child")')
        self.assertEqual(receipt['proof']['worker_returncode'], 0)
        self.assertEqual(receipt['proof'], self.assert_closed())
        self.assertFalse((self.stage / 'startup-failure.json').exists())

    def test_binary_stdout_and_stderr_preserved_on_nonzero(self):
        with self.assertRaises(RuntimeError):
            self.run_child('import os; os.write(1,b"stdout\\x00\\xff\\n"); '
                           'os.write(2,b"inner failure\\x80\\n"); raise SystemExit(11)')
        self.assertEqual((self.stage / 'stdout.txt').read_bytes(), b'stdout\x00\xff\n')
        self.assertEqual((self.stage / 'stderr.txt').read_bytes(), b'inner failure\x80\n')
        self.assertEqual(self.assert_closed()['worker_returncode'], 11)

    def test_optimized_mode_reaches_owned_child(self):
        self.run_child('import sys; print(sys.flags.optimize)')
        self.assertEqual((self.stage / 'stdout.txt').read_text().strip(), str(sys.flags.optimize))
        self.assert_closed()

    def test_real_nonzero_surfaces_only_matching_child_stage(self):
        code = 'from pathlib import Path; import json; Path("preparation-failure.json").write_text(' + repr(json.dumps(report())) + '); raise SystemExit(7)'
        with self.assertRaises(RuntimeError) as caught:
            self.run_child(code)
        self.assertEqual(str(caught.exception), 'owned parent preparation/runtime failed; preserve closure and logs')
        self.assertIn('offline-installation', caught.exception.__notes__[0])
        self.assertEqual(self.assert_closed()['worker_returncode'], 7)
        failure = json.loads((self.stage / 'startup-failure.json').read_bytes())
        self.assertEqual(failure['preparation_failure']['stage'], 'offline-installation')
        self.assertFalse(failure['operational_success'])

    def test_real_nonzero_without_report_remains_unknown(self):
        with self.assertRaises(RuntimeError) as caught:
            self.run_child('raise SystemExit(3)')
        self.assertEqual(self.assert_closed()['worker_returncode'], 3)
        self.assertIn('unavailable or unverified', caught.exception.__notes__[0])
        self.assertIsNone(json.loads((self.stage / 'startup-failure.json').read_bytes())['preparation_failure'])

    def test_expired_clock_does_not_dispatch_or_reset(self):
        with self.assertRaisesRegex(ValueError, 'original outer reserve exhausted'):
            self.run_child('raise AssertionError("must not launch")', deadline_epoch=time.time() - 1)
        self.assertFalse((self.stage / 'owned-tree').exists())
        failure = json.loads((self.stage / 'startup-failure.json').read_bytes())
        self.assertEqual(failure['dispatch_state'], 'not-dispatched')
        self.assertEqual(failure['original_epoch'], CONTEXT['original_epoch'])

    def test_original_deadline_timeout_closes_owned_child(self):
        deadline = time.time() + 16
        started = time.monotonic()
        with self.assertRaises(RuntimeError):
            self.run_child('import os, time; os.write(2,b"inner marker\\n"); time.sleep(30)',
                           deadline_epoch=deadline)
        self.assertLess(time.monotonic() - started, 12)
        self.assertEqual((self.stage / 'stderr.txt').read_bytes(), b'inner marker\n')
        proof = self.assert_closed()
        self.assertTrue(proof['forced'])
        closure = json.loads((self.stage / 'closure.json').read_bytes())
        self.assertEqual(closure['deadline_epoch'], deadline)
        self.assertEqual(closure['reason'], 'original-outer-deadline')
        failure = json.loads((self.stage / 'startup-failure.json').read_bytes())
        self.assertEqual(failure['original_epoch'], CONTEXT['original_epoch'])
        self.assertFalse(failure['operational_success'])

    def test_selector_failure_still_closes_real_child(self):
        with patch.object(launch.selectors, 'DefaultSelector', side_effect=OSError('synthetic original fault')):
            with self.assertRaisesRegex(OSError, 'synthetic original fault'):
                self.run_child('import time; time.sleep(30)')
        self.assert_closed()
        self.assertEqual(json.loads((self.stage / 'startup-failure.json').read_bytes())['stage'], 'selector-setup')

    def test_oversize_pipe_still_forces_owned_closure(self):
        with self.assertRaises(RuntimeError):
            self.run_child('import os; data=b"x"*65536\nfor i in range(160): os.write(1,data)')
        self.assert_closed()
        closure = json.loads((self.stage / 'closure.json').read_bytes())
        self.assertTrue(closure['forced'])
        self.assertEqual(closure['reason'], 'bounded-launcher-log-cap')
        self.assertLessEqual((self.stage / 'stdout.txt').stat().st_size, 8 * 1024**2)

    def test_preexisting_stage_rejected_without_overwrite(self):
        self.stage.mkdir(); sentinel = self.stage / 'stdout.txt'; sentinel.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            self.run_child('print("must not launch")')
        self.assertEqual(sentinel.read_bytes(), b'preserve')


if __name__ == '__main__':
    unittest.main()

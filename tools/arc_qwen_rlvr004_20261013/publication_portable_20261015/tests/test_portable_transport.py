"""Run the frozen transport regressions against the portable successor.

Only fixture paths/configuration and the two obsolete wrapper assertions change.
The source-bound suite remains the same; every provider/credential is synthetic.
"""
import hashlib
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
FROZEN = HERE.with_name('publication_run008')


def frozen_suite(filename, digest, replacements):
    path = FROZEN / 'tests' / filename
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('frozen regression suite bytes changed')
    source = raw.decode()
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError('frozen regression fixture splice differs')
        source = source.replace(old, new)
    module = types.ModuleType('portable_' + filename[:-3])
    module.__file__ = str(path)
    exec(compile(source, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


_frozen = frozen_suite('test_native_transport.py', '60f5b74c56e2cbd08bc819c1dc5f8e0e5edba036bfe92fe93d1b72ba9c853fc5', [
    ('HERE=Path(__file__).resolve().parents[1]', 'HERE=Path(' + repr(str(HERE)) + ')'),
    ("        wrapper=self.root/'kaggle_setup/kaggle.sh';wrapper.parent.mkdir();wrapper.write_bytes((HERE.parents[3]/'kaggle_setup/kaggle.sh').read_bytes())", '        # Historical wrapper is deliberately not fabricated by successor tests.'),
])
load, sha, encoded = _frozen.load, _frozen.sha, _frozen.encoded


class PortableTransportTests(_frozen.NativeTransportTests):
    def setUp(self):
        from test_portable_binding import runtime_fixture
        _frozen.NativeTransportTests.setUp(self)
        self.config.pop('native_wrapper')
        self.config['format'] = 'irisx/run008-portable-posix-operator-config-v1'
        self.config['runtime'] = runtime_fixture(self.root)
        self.home = Path(self.config['runtime']['home'])
        account = types.SimpleNamespace(pw_dir=str(self.home))
        environment = {key: value for key, value in os.environ.items() if key != 'REQUESTS_CA_BUNDLE'}
        environment['HOME'] = str(self.home)
        for patch in (mock.patch.object(pwd, 'getpwuid', return_value=account),
                      mock.patch.dict(os.environ, environment, clear=True)):
            patch.start()
            self.addCleanup(patch.stop)
        self.rewrite_config(self.config)
        self.review['local_config_sha256'] = self.args.local_config_sha
        self.review_path.write_bytes(encoded(self.review))
        self.args.review_sha = sha(self.review_path)

    def test_native_boundary_rejects_arbitrary_wrapper(self):
        changed = dict(self.config)
        changed['native_wrapper'] = {'path': '/synthetic/obsolete/kaggle.sh', 'sha256': '0' * 64}
        self.rewrite_config(changed)
        with self.assertRaisesRegex(ValueError, 'schema'):
            self.bind()

    def test_launcher_plan_is_fixed_and_isolated(self):
        launcher = load('portable_launcher_test', HERE / 'launch.py')
        args = ['publish', 'validate', '--local-config', str(self.config_path), '--local-config-sha', sha(self.config_path)]
        executable, argv, environment = launcher.plan(args)
        self.assertEqual(executable, self.config['runtime']['executable']['path'])
        self.assertEqual(argv[1:3], ['-I', '-B'])
        self.assertEqual(environment['HOME'], str(self.home))
        self.assertNotIn('KAGGLE_CONFIG_DIR', environment)
        self.assertFalse(any(key.startswith('KAGGLE_') for key in environment))
        self.assertNotIn('PYTHONPATH', environment)
        with self.assertRaises(ValueError):
            launcher.plan(['arbitrary', 'file.py'])

    def test_claim_fsync_failure_preserves_uncertain_intent(self):
        self.bind()
        common = self.t._common
        with mock.patch.object(common.os, 'fsync', side_effect=OSError('synthetic fsync failure')):
            with self.assertRaises(OSError):
                common.claim('synthetic-send', {'synthetic_test_only': True})
        self.assertTrue((common.STATE / 'synthetic-send.claim.json').is_file())
        with self.assertRaises(FileExistsError):
            common.claim('synthetic-send', {'synthetic_test_only': True})

    def test_os_releases_lock_when_owner_is_terminated(self):
        self.bind()
        common = self.t._common
        marker = self.root / 'child-lock-acquired'
        program = '''import importlib.util,sys,time,types
from pathlib import Path
spec=importlib.util.spec_from_file_location('portable_lock_process',sys.argv[1])
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
c.CONFIG=types.SimpleNamespace(scratch_root=Path(sys.argv[2]))
with c.lock('publisher'):
 Path(sys.argv[3]).write_text('synthetic lock only')
 time.sleep(60)
'''
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', program, str(HERE / 'operator_common.py'),
                                  str(self.scratch), str(marker)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(marker.exists(), 'synthetic child failed to acquire lock')
            with self.assertRaisesRegex(ValueError, 'operator_already_running'):
                with common.lock('collector'):
                    pass
        finally:
            if child.poll() is None:
                child.terminate()
            try:
                child.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate(timeout=5)
        self.assertIsNotNone(child.returncode)
        with common.lock('collector'):
            pass


_auth = frozen_suite('test_native_auth.py', 'cfba5d7a95d5695efcfa965023e8294168dd99e0408a876c11c06bbb8bfb58b1', [
    ('import test_native_transport as fixtures', 'import test_portable_transport as fixtures'),
    ('from test_native_transport import load,HERE,sha', 'from test_portable_transport import load,HERE,sha'),
    ('setUp=fixtures.NativeTransportTests.setUp', 'setUp=fixtures.PortableTransportTests.setUp'),
    ('bind=fixtures.NativeTransportTests.bind', 'bind=fixtures.PortableTransportTests.bind'),
])


class PortableAuthLifecycleTests(unittest.TestCase):
    setUp = PortableTransportTests.setUp
    bind = PortableTransportTests.bind
    rewrite_config = PortableTransportTests.rewrite_config
    opened = _auth.NativeAuthTests.opened
    test_preexpiry_renewal_journal_and_resource_counters_preserved = _auth.NativeAuthTests.test_preexpiry_renewal_journal_and_resource_counters_preserved
    test_unknown_refresh_is_durable_and_never_retried = _auth.NativeAuthTests.test_unknown_refresh_is_durable_and_never_retried
    test_unclaimed_refresh_and_delete_blocked = _auth.NativeAuthTests.test_unclaimed_refresh_and_delete_blocked


if __name__ == '__main__':
    unittest.main(verbosity=2)

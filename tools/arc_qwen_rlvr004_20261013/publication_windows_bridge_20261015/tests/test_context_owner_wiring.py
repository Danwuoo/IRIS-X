"""Synthetic owner wiring only; no native process, auth, or provider calls."""
from pathlib import Path
import tempfile
import types
import unittest

from test_bridge_client import Common, binding, canonical, client_module, digest
from test_owner_integration import load_source

ROOT = Path(__file__).resolve().parents[1]


class ContextOwnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.c = Common(self.root)
        self.c.mapping['descriptor'] = lambda p: {'path': str(p),
            'bytes': Path(p).stat().st_size, 'sha256': digest(Path(p).read_bytes())}
        self.claim = self.c.claim('native-bridge-' + 'a' * 64, {'nonce': 'a' * 64})
        self.c.journal('native-bridge-' + 'a' * 64,
            {'stage': 'UNKNOWN', 'native_process_closure_verified': False,
             'claim_sha256': self.claim['sha256']})
        self.c.writes.clear()
        self.before = {p.name: p.read_bytes() for p in self.root.iterdir()}

    def eligible(self):
        (self.root / ('recovery-epoch-' + 'b' * 64 + '-eligibility.claim.json')).write_bytes(b'{}')
        self.before = {p.name: p.read_bytes() for p in self.root.iterdir()}

    def assert_unchanged(self):
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertEqual(self.c.writes, [])

    def test_missing_disposition_rejects_before_adapter_or_new_claim(self):
        instance = client_module.BridgeClient.__new__(client_module.BridgeClient)
        instance.c = self.c.mapping
        self.c.mapping['load_source_module'] = lambda *a: self.fail('adapter unexpectedly loaded')
        with self.assertRaisesRegex(ValueError, 'previous_session_unknown'):
            instance._pending_sessions()
        self.assert_unchanged()

    def test_pending_routes_actual_config_and_source_pin_to_adapter(self):
        self.eligible()
        calls = []
        def validate(callbacks, configured, pending):
            self.assertIs(configured, self.c.config)
            self.assertIs(callbacks['STATE'], self.root)
            self.assertTrue(callable(callbacks['recovery_boot_observation']))
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]['claim'], self.claim)
            calls.append('validate')
        def loader(name, path, expected):
            self.assertEqual(Path(path), ROOT / 'context_continuation.py')
            self.assertEqual(expected, digest(Path(path).read_bytes()))
            return types.SimpleNamespace(validate_context=validate)
        self.c.mapping['load_source_module'] = loader
        instance = client_module.BridgeClient.__new__(client_module.BridgeClient)
        instance.c = self.c.mapping
        instance._pending_sessions()
        self.assertEqual(calls, ['validate'])
        self.assert_unchanged()

    def test_adapter_denial_precedes_new_claim_or_transport(self):
        self.eligible()
        original = self.c.mapping['load_source_module']
        def deny(*args):
            raise ValueError('synthetic_context_denied')
        def loader(name, path, expected):
            if Path(path).name == 'context_continuation.py':
                return types.SimpleNamespace(validate_context=deny)
            return original(name, path, expected)
        self.c.mapping['load_source_module'] = loader
        with self.assertRaisesRegex(ValueError, 'synthetic_context_denied'):
            client_module.BridgeClient.for_testing(self.c.mapping, binding(),
                lambda *a: self.fail('transport unexpectedly launched'))
        self.assert_unchanged()

    def test_configuration_descriptor_is_current_bound_bytes_and_rejects_drift(self):
        common = load_source('context_owner_current_common', ROOT / 'operator_common.py')
        path = self.root / 'current-config.json'
        raw = canonical({'synthetic': True})
        path.write_bytes(raw)
        common.CONFIG = types.SimpleNamespace(document_sha256=digest(raw))
        common.CONFIG_PATH = path
        self.assertEqual(common.configuration_descriptor(),
            {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)})
        path.write_bytes(canonical({'synthetic': False}))
        with self.assertRaises(common.GuardError):
            common.configuration_descriptor()

    def test_configuration_descriptor_requires_actual_path(self):
        common = load_source('context_owner_missing_path_common', ROOT / 'operator_common.py')
        common.CONFIG = types.SimpleNamespace(document_sha256='c' * 64)
        with self.assertRaisesRegex(common.GuardError, 'current_configuration_path_required'):
            common.configuration_descriptor()


if __name__ == '__main__':
    unittest.main()

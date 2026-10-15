"""Synthetic CPU entry-to-core integration, never Windows/auth/provider evidence."""
import copy
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

import test_recovery_epoch as fixture
r, write = fixture.r, fixture.write

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('offline_recovery_entry_test', ROOT / 'recovery_entry.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class EntryCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.EpochTests.setUpClass()

    def setUp(self):
        self.f = fixture.EpochTests('test_complete_restart_reserve_reconcile_preserves_original_bytes')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.c = self.f.c.mapping
        self.c['verified'] = lambda path, digest, cap: r.verified(r.descriptor(path)) if r.descriptor(path)['sha256'] == digest else self.fail('input hash')
        self.c['write_new'] = lambda path, raw: self.f.c._write(Path(path), r.strict_json(raw))
        self.transport = types.SimpleNamespace(_common=types.SimpleNamespace(**self.c),
            load_contract=lambda args: None,
            execution_gate=lambda args: self.fail('provider gate not expected'),
            git_publication_gate=lambda args: self.fail('Git gate not expected'))

    def args(self, action, value):
        desc = write(self.f.root / 'entry-input.json', value)
        return types.SimpleNamespace(action=action, input=desc['path'], input_sha=desc['sha256'])

    def assert_original(self):
        for name, raw in self.f.original_bytes.items():
            self.assertEqual((self.f.state / name).read_bytes(), raw)

    def test_validate_actual_core_has_no_observer_or_new_state(self):
        before = r.inventory_state(self.f.state)
        args = self.args('validate', {'inventory': self.f.inventory, 'review': self.f.review})
        result = entry.execute(args, self.transport, r, types.SimpleNamespace())
        self.assertEqual(result['status'], 'RECOVERY_FRONTIER_VALIDATED')
        self.assertEqual(result['provider_calls'], 0)
        self.assertEqual(before, r.inventory_state(self.f.state))

    def test_prepare_binds_fresh_observer_and_exact_original_inventory(self):
        calls = []
        def observe(common, review, challenge):
            calls.append((review, challenge))
            return self.f.before
        args = self.args('prepare', {'inventory': self.f.inventory, 'review': self.f.review,
            'challenge': self.f.challenge, 'expires_epoch': self.f.now + 1000})
        with patch.object(entry.time, 'time', return_value=self.f.now):
            result = entry.execute(args, self.transport, r, types.SimpleNamespace(observe_recovery_boot=observe))
        self.assertEqual(result['status'], 'RECOVERY_PREPARATION_SAVED')
        self.assertEqual(len(calls), 1)
        self.assertEqual(r._document(result['preparation'])['before_boot'], self.f.before)
        self.assertFalse(result['manual_restart_executed'])
        self.assert_original()

    def test_reconcile_action_review_runs_before_boot_reservation_or_network(self):
        args = self.args('reconcile-read-only', {'preparation': {}, 'restart': {}, 'binding_review': {}, 'session_nonce': 'a'*64})
        def deny(args):
            raise ValueError('synthetic missing execution admission')
        self.transport.execution_gate = deny
        before = r.inventory_state(self.f.state)
        with self.assertRaisesRegex(ValueError, 'missing execution admission'):
            entry.execute(args, self.transport, r, types.SimpleNamespace())
        self.assertEqual(before, r.inventory_state(self.f.state))

    def test_exact_materialization_matches_real_core_and_cannot_overwrite(self):
        with r.RecoveryOwner(self.c) as owner:
            _, after, _, binding, _, reservation = self.f.reserve(owner)
            native, local, desc = entry.materialize_binding(r, owner, reservation, binding, self.c)
            r.verify_generated_binding(reservation, native, local)
            self.assertEqual(local['windows_bridge']['configuration']['native_path'], r'C:\Synthetic\recovery-native.json')
            self.assertEqual(r._document(desc), local)
            with self.assertRaises(FileExistsError):
                entry.materialize_binding(r, owner, reservation, binding, self.c)
        self.assert_original()

    def test_materialization_failure_leaves_consumed_reservation_and_no_second_use(self):
        with r.RecoveryOwner(self.c) as owner:
            _, after, _, binding, _, reservation = self.f.reserve(owner)
            def fail(path, raw):
                raise OSError('synthetic write failure')
            with self.assertRaises(OSError):
                entry.materialize_binding(r, owner, reservation, binding, dict(self.c, write_new=fail))
            capability = r._document(reservation)['capability']
            with self.assertRaises(r.RecoveryError):
                owner.reserve(capability, session_nonce=self.f.new_nonce,
                              current_boot_descriptor=after, now_epoch=self.f.now + 100)
        self.assert_original()

    def test_overlay_cannot_change_namespace_budget_or_account(self):
        with r.RecoveryOwner(self.c) as owner:
            _, _, _, binding, _, reservation = self.f.reserve(owner)
            native, local, _ = entry.materialize_binding(r, owner, reservation, binding, self.c)
            for key, value in [('state_root', '/different'), ('username', 'other'), ('versions', {})]:
                changed = copy.deepcopy(local)
                changed[key] = value
                with self.subTest(key=key), self.assertRaises(r.RecoveryError):
                    r.verify_generated_binding(reservation, native, changed)
        self.assert_original()


if __name__ == '__main__':
    unittest.main()

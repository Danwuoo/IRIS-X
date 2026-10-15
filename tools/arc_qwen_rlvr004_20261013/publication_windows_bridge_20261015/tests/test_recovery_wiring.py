"""Offline explicit recovery-mode binding; no native/auth/provider execution."""
import copy
import tempfile
import time
import types
from pathlib import Path
import unittest
from unittest.mock import patch

from test_preauth_probe import probe as PREAUTH, prepared, FakeTransport
from test_bridge_client import client_module as CLIENT, Common, SyntheticServer, binding

from test_config_admission import CONFIG, SyntheticFixture, VERSIONS, sha

ROOT = Path(__file__).resolve().parents[1]


def recovery_fields():
    return {'capability_sha256': '1' * 64, 'reservation_sha256': '2' * 64,
            'challenge': '3' * 64, 'host_install_sha256': '4' * 64,
            'last_boot_utc': '2026-10-15T12:00:00Z', 'expires_epoch': 2000000000.0,
            'allowed_operations': ['open', 'dataset', 'kernel', 'status', 'close']}


class RecoveryConfigTests(unittest.TestCase):
    def setUp(self):
        self.f = SyntheticFixture(self)

    def recovery_native(self):
        raw = (ROOT / 'recovery_boot_probe.py').read_bytes()
        self.f.allowed_local_reads.add(ROOT / 'recovery_boot_probe.py')
        self.f.native['format'] = 'irisx/run008-windows-sdk-recovery-runtime-v1'
        self.f.native['recovery'] = recovery_fields()
        self.f.native['sources']['recovery_boot_probe.py'] = {'bytes': len(raw), 'sha256': sha(raw)}
        self.f.sync_native()

    def test_normal_entry_rejects_recovery_mode_and_explicit_mode_accepts_structure(self):
        self.recovery_native()
        with self.assertRaisesRegex(ValueError, 'windows_bridge_native_configuration'):
            self.f.bridge_load()
        self.assertEqual(CONFIG.load_windows_bridge(self.f.bridge, VERSIONS, recovery=True), self.f.bridge)

    def test_recovery_requires_distinct_format_and_exact_eighth_source(self):
        with self.assertRaisesRegex(ValueError, 'windows_bridge_native_configuration'):
            CONFIG.load_windows_bridge(self.f.bridge, VERSIONS, recovery=True)
        self.recovery_native()
        del self.f.native['sources']['recovery_boot_probe.py']
        self.f.sync_native()
        with self.assertRaisesRegex(ValueError, 'windows_native_source_closure'):
            CONFIG.load_windows_bridge(self.f.bridge, VERSIONS, recovery=True)

    def test_recovery_fields_reject_mutation_extra_keys_bad_hash_bool_expiry(self):
        baseline = recovery_fields()
        variants = [dict(baseline, extra=True), dict(baseline, expires_epoch=True),
                    dict(baseline, expires_epoch=float('inf')),
                    dict(baseline, capability_sha256='unbound'),
                    dict(baseline, allowed_operations=['open', 'dataset', 'kernel', 'status', 'close', 'save'])]
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                CONFIG.recovery_stanza(value)

    def test_legacy_format_cannot_smuggle_recovery_stanza(self):
        self.f.native['recovery'] = recovery_fields()
        self.f.sync_native()
        with self.assertRaisesRegex(ValueError, 'windows_recovery_mode_required'):
            self.f.bridge_load()


class RecoveryPreauthTests(unittest.TestCase):
    def test_recovery_probe_sends_only_open_and_never_ready_ack(self):
        value = prepared()
        value['document']['recovery'] = recovery_fields()
        created = []
        def factory(*args):
            transport = FakeTransport(*args)
            created.append(transport)
            return transport
        result = PREAUTH.exercise(value, timeout_seconds=30, transport_factory=factory)
        self.assertTrue(result['ok'])
        self.assertTrue(result['recovery_boot_mode'])
        self.assertFalse(result['ready_ack_sent'])
        self.assertFalse(result['auth_started'])
        self.assertEqual(created[0].request['payload']['arguments']['recovery'],
                         {key: recovery_fields()[key] for key in ('capability_sha256', 'reservation_sha256')})
        self.assertLessEqual(created[0].request['payload']['arguments']['deadline_epoch'], 2000000000.0)

    def test_expired_recovery_probe_does_not_create_transport(self):
        value = prepared()
        value['document']['recovery'] = dict(recovery_fields(), expires_epoch=1.0)
        with self.assertRaisesRegex(PREAUTH.ProbeError, 'preauth_recovery_expired'):
            PREAUTH.exercise(value, transport_factory=lambda *args: self.fail('launch'))


class SyntheticRecoveryOwner:
    def __init__(self):
        self.used = False
        self.checks = 0

    def admit_session(self, reservation, *, current_boot_descriptor, now_epoch):
        if self.used:
            raise ValueError('recovery_launch_ticket_reused')
        self.used = True
        return {'session_nonce': 'f' * 64,
                'native_recovery': dict(recovery_fields(), expires_epoch=now_epoch + 600),
                'calls': ['dataset', 'kernel', 'status', 'kernel', 'dataset']}

    def validate_frontier_reserved(self, reservation):
        self.checks += 1
        return {}


class ReadServer(SyntheticServer):
    def control(self, envelope):
        if envelope['kind'] == 'request' and envelope['payload']['operation'] in ('dataset', 'kernel'):
            self.protocol.validate_envelope(envelope)
            self.current = envelope
            self.requests.append(envelope)
            if envelope['payload']['operation'] == 'dataset':
                result = {'id': 12504696, 'ref': 'danielwuu/iris-x-learning-agent-code-20261011',
                    'isPrivate': True, 'currentVersionNumber': 20, 'title': 'Synthetic code',
                    'licenseName': 'Other', 'ownerRef': 'danielwuu', 'versions': [{'versionNumber': 20}]}
            else:
                result = {'metadata': {'id': 138123872, 'ref': 'danielwuu/iris-x-learning-agent-20261011',
                    'isPrivate': True, 'currentVersionNumber': 39, 'title': 'Synthetic kernel',
                    'language': 'python', 'kernelType': 'notebook', 'kernelDataSources': [],
                    'enableGpu': False, 'enableTpu': False, 'enableInternet': False,
                    'modelDataSources': [], 'datasetDataSources': [], 'competitionDataSources': [],
                    'dockerImage': '', 'machineShape': ''}, 'blob': {'source': 'synthetic notebook'}}
            self.respond(result)
        else:
            super().control(envelope)


class RecoveryClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.common = Common(Path(self.temp.name))
        self.owner = SyntheticRecoveryOwner()
        self.created = []

    def make(self, fault=None):
        def factory(*args):
            server = ReadServer(self.common, *args, fault=fault)
            self.created.append(server)
            return server
        return CLIENT.RecoveryBridgeClient.for_recovery_testing(self.common.mapping, binding(),
            self.owner, {'sha256': 'a' * 64}, {}, factory)

    def test_actual_framing_exact_read_bracket_closes_and_retains_receipt(self):
        connection = self.make()
        for operation in ['dataset', 'kernel', 'status', 'kernel', 'dataset']:
            connection.call(operation, {})
        connection.close()
        self.assertTrue(connection.closed and connection.closure_verified)
        self.assertTrue(connection.native_receipt_bytes.endswith(b'\n'))
        self.assertEqual(connection.native_exit_status, 0)
        self.assertFalse(connection.can_rotate_read_only())
        self.assertEqual([r['payload']['operation'] for r in self.created[0].requests],
                         ['open', 'dataset', 'kernel', 'status', 'kernel', 'dataset', 'close'])
        self.assertEqual(self.created[0].requests[0]['payload']['arguments']['recovery'],
                         {'capability_sha256': '1' * 64, 'reservation_sha256': '2' * 64})
        self.assertGreaterEqual(self.owner.checks, 2)

    def test_mutation_download_upload_rotation_and_reordering_fail_before_dispatch(self):
        connection = self.make()
        count = len(self.created[0].requests)
        for operation in ('save', 'version', 'start_upload', 'list_files', 'status'):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                connection.call(operation, {})
        with self.assertRaisesRegex(ValueError, 'upload_forbidden'):
            connection.upload_once('unused', '/must/not/read')
        with self.assertRaisesRegex(ValueError, 'download_forbidden'):
            connection.download('unused', {}, None)
        with self.assertRaises(CLIENT.BridgeUnknown):
            connection.rotate_read_only()
        self.assertEqual(len(self.created[0].requests), count)
        for operation in ['dataset', 'kernel', 'status', 'kernel', 'dataset']:
            connection.call(operation, {})
        connection.close()

    def test_consumed_owner_cannot_relaunch_and_failed_open_stays_unknown(self):
        with self.assertRaises(Exception):
            self.make(fault='open_eof')
        self.assertTrue(self.owner.used)
        self.assertEqual(len(self.created), 1)
        with self.assertRaisesRegex(ValueError, 'ticket_reused'):
            self.make()
        self.assertEqual(len(self.created), 1)
        journals = list(Path(self.temp.name).glob('*-journal.json'))
        import json
        self.assertEqual(json.loads(journals[0].read_bytes())['stage'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()

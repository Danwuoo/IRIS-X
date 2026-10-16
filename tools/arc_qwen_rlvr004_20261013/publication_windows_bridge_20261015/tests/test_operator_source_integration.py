"""Narrow offline source integration; temporary reviews grant no real authority."""
import ast
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NUMERIC = ROOT.parent / 'numeric_replay_diagnostic_20261016'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def literal(path, name):
    tree = ast.parse(path.read_bytes())
    matches = [node for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    stores = [node for node in ast.walk(tree) if isinstance(node, ast.Name)
              and isinstance(node.ctx, ast.Store) and node.id == name]
    if len(matches) != 1 or len(stores) != 1:
        raise AssertionError('exactly one source pin required: ' + name)
    return ast.literal_eval(matches[0].value)


def load(path):
    module = types.ModuleType('offline_operator_source_' + path.stem)
    module.__file__, module.__package__ = str(path), ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                 optimize=sys.flags.optimize), vars(module))
    return module


class OperatorSourceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target, name in ((socket, 'socket'), (socket, 'create_connection'),
                             (subprocess, 'Popen')):
            self.stack.enter_context(patch.object(target, name,
                side_effect=AssertionError('offline source tests forbid external execution')))

    def test_bottom_up_source_pins(self):
        names = literal(ROOT / 'rl_transport.py', 'OPERATOR_SOURCE_NAMES')
        self.assertEqual(len(names), 22)
        self.assertEqual(len(set(names)), 22)
        for owner, constant, target in (
            ('context_continuation.py', 'SOURCE_PINS_SHA256', 'context-source-pins.json'),
            ('context_continuation.py', 'PUBLICATION_STATE_SHA256', 'publication_state.py'),
            ('context_continuation.py', 'PREWORKER_SOURCE_SHA256', 'preworker_disposition.py'),
            ('bridge_client.py', 'SDK_LOCK_SHA256', 'sdk-lock.json'),
            ('bridge_client.py', 'CONTEXT_SOURCE_SHA256', 'context_continuation.py'),
            ('bridge_client.py', 'PROTOCOL_SOURCE_SHA256', 'protocol.py'),
            ('operator_common.py', 'BRIDGE_CLIENT_SHA256', 'bridge_client.py'),
            ('operator_common.py', 'CONFIG_SOURCE_SHA256', 'config.py'),
            ('operator_common.py', 'PUBLICATION_STATE_SHA256', 'publication_state.py'),
            ('rl_transport.py', 'COMMON_SOURCE_SHA256', 'operator_common.py'),
            ('native_auth.py', 'LOCK_SHA256', 'sdk-lock.json'),
            ('sdk_worker.py', 'WIN_RUNTIME_SHA256', 'win_runtime.py'),
            ('sdk_worker.py', 'NATIVE_CONFIG_SHA256', 'native_config.py'),
            ('win_supervisor.py', 'WIN_RUNTIME_SHA256', 'win_runtime.py'),
            ('win_supervisor.py', 'NATIVE_CONFIG_SHA256', 'native_config.py'),
            ('preworker_disposition.py', 'SOURCE_PINS_SHA256', 'context-source-pins.json'),
            ('recovery_entry.py', 'TRANSPORT_SHA256', 'rl_transport.py'),
            ('recovery_entry.py', 'CLIENT_SHA256', 'bridge_client.py'),
            ('recovery_entry.py', 'CORE_SHA256', 'recovery_epoch.py'),
            ('launch.py', 'CONFIG_SOURCE_SHA256', 'config.py'),
        ):
            with self.subTest(owner=owner, target=target):
                self.assertEqual(literal(ROOT / owner, constant), sha((ROOT / target).read_bytes()))
        entries = literal(ROOT / 'launch.py', 'ENTRY_SHA256')
        self.assertEqual(set(entries), {'rl_transport.py', 'rl_collect.py', 'recovery_entry.py'})
        for name, digest in entries.items():
            self.assertEqual(digest, sha((ROOT / name).read_bytes()))

    def test_operator_uses_exact_numeric_overlays_and_original_path(self):
        for name in ('rl_transport.py', 'rl_collect.py', 'verify_active_wire.py'):
            self.assertEqual((ROOT / name).read_bytes(), (NUMERIC / 'publication' / name).read_bytes())
        suffix = literal(ROOT / 'context_continuation.py', 'PACKAGE_SUFFIX')
        self.assertEqual((ROOT / 'context_continuation.py').parts[-len(suffix):], suffix)

    def test_launcher_plans_all_three_exact_sources_without_execution(self):
        launch = load(ROOT / 'launch.py')
        config = types.SimpleNamespace(
            read_runtime=lambda path, digest: types.SimpleNamespace(executable=Path('/synthetic-only/python')),
            child_environment=lambda runtime, environment: {'SYNTHETIC_ONLY': '1'})
        with patch.object(launch, 'config_module', return_value=config):
            for mode, entry in (('publish', 'rl_transport.py'), ('collect', 'rl_collect.py'),
                                ('recover', 'recovery_entry.py')):
                args = [mode, 'validate', '--local-config', '/synthetic-only/config.json',
                        '--local-config-sha', '1' * 64]
                executable, argv, environment = launch.plan(args)
                self.assertEqual(executable, '/synthetic-only/python')
                self.assertEqual(argv, [executable, '-I', '-B', str(ROOT / entry), *args[1:]])
                self.assertEqual(environment, {'SYNTHETIC_ONLY': '1'})

    def test_launcher_rejects_stale_entry_pins(self):
        launch = load(ROOT / 'launch.py')
        config = types.SimpleNamespace(
            read_runtime=lambda path, digest: types.SimpleNamespace(executable=Path('/synthetic-only/python')),
            child_environment=lambda *args: self.fail('stale entry reached environment construction'))
        with patch.object(launch, 'config_module', return_value=config):
            for mode, entry in (('publish', 'rl_transport.py'), ('collect', 'rl_collect.py'),
                                ('recover', 'recovery_entry.py')):
                with patch.dict(launch.ENTRY_SHA256, {entry: '0' * 64}):
                    with self.assertRaisesRegex(ValueError, 'operator_source_bytes'):
                        launch.plan([mode, 'validate', '--local-config', '/synthetic-only/config.json',
                                     '--local-config-sha', '1' * 64])

    def review_fixture(self, root):
        transport = load(ROOT / 'rl_transport.py')
        transport.CONFIG = types.SimpleNamespace(document_sha256='1' * 64)
        review = {'status': 'PASS', 'synthetic_test_only': True,
                  'provider_execution_admitted': False, 'local_config_sha256': '1' * 64,
                  'publication_manifest_sha256': '2' * 64, 'material_approval_sha256': '3' * 64,
                  'operator_files': {name: sha((ROOT / name).read_bytes())
                                     for name in transport.OPERATOR_SOURCE_NAMES}}
        path = root / 'synthetic-review.json'
        return transport, review, path

    def review_gate(self, transport, review, path):
        path.write_bytes(encoded(review))
        return transport.review_gate(path, sha(path.read_bytes()), '2' * 64, '3' * 64, [])

    def test_action_review_binds_every_current_source_and_rejects_stale_or_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            transport, review, path = self.review_fixture(Path(directory))
            self.assertEqual(self.review_gate(transport, review, path), review)
            for name in transport.OPERATOR_SOURCE_NAMES:
                original = review['operator_files'][name]
                with self.subTest(name=name, mutation='stale'):
                    review['operator_files'][name] = '0' * 64
                    with self.assertRaisesRegex(ValueError, 'operator_bytes_not_reviewed'):
                        self.review_gate(transport, review, path)
                with self.subTest(name=name, mutation='missing'):
                    del review['operator_files'][name]
                    with self.assertRaisesRegex(ValueError, 'complete_bridge_operator_review_required'):
                        self.review_gate(transport, review, path)
                review['operator_files'][name] = original

    def test_monitor_review_requires_actual_collector_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport, review, path = self.review_fixture(root)
            consumer = root / 'synthetic-consumer'
            consumer.mkdir()
            (consumer / 'reviewed_entry.py').write_bytes(b'# Inert CPU fixture; no consumer execution.\n')
            (consumer / 'CONSUMER-INVENTORY.json').write_bytes(encoded({'synthetic_test_only': True}))
            pins = {'collector_entry_sha256': sha((ROOT / 'rl_collect.py').read_bytes()),
                    'helper_inventory_sha256': sha((consumer / 'CONSUMER-INVENTORY.json').read_bytes())}
            args = types.SimpleNamespace(monitor_review=str(path), monitor_sha='',
                consumer_root=str(consumer), manifest_sha='2' * 64, material_sha='3' * 64)
            def write_review():
                (consumer / 'CONSUMER-OPERATOR.json').write_bytes(encoded(pins))
                review['consumer_files'] = {p.name: sha(p.read_bytes()) for p in consumer.iterdir()}
                path.write_bytes(encoded(review))
                args.monitor_sha = sha(path.read_bytes())
            write_review()
            self.assertEqual(transport.monitor_gate(args), review)
            pins['collector_entry_sha256'] = '0' * 64
            write_review()
            with self.assertRaisesRegex(ValueError, 'consumer_collector_closure_link'):
                transport.monitor_gate(args)


if __name__ == '__main__':
    unittest.main()

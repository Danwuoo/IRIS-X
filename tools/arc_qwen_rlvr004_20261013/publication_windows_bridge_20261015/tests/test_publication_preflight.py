"""Synthetic static closure tests; never native/provider/dispatch evidence."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_owner_integration import load_source, sha

ROOT = Path(__file__).resolve().parents[1]


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


class ActionBindingTests(unittest.TestCase):
    def setUp(self):
        self.common = load_source('preflight_test_common', ROOT / 'operator_common.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_bytes(b'{}\n')
        self.common.CONFIG = SimpleNamespace(document_sha256='a' * 64,
            publication_manifest_sha256=sha(self.manifest.read_bytes()), candidate_root=self.root)
        self.common.MANIFEST_PATH = self.manifest

    def review(self, lineage=None):
        value = {'status': 'PASS', 'local_config_sha256': 'a' * 64,
            'publication_manifest_sha256': self.common.CONFIG.publication_manifest_sha256}
        if lineage is not None:
            value['candidate_lineage'] = lineage
        path = self.root / 'review.json'
        path.write_bytes(encoded(value))
        self.common.bind_action_review(path, sha(path.read_bytes()))
        return path

    def test_actual_manifest_descriptor_and_drift(self):
        row = self.common.publication_manifest_descriptor()
        self.assertEqual(row['path'], str(self.manifest))
        self.assertEqual(row['sha256'], self.common.CONFIG.publication_manifest_sha256)
        self.manifest.write_bytes(b'{"changed":true}\n')
        with self.assertRaises(ValueError):
            self.common.publication_manifest_descriptor()

    def test_no_lineage_remains_none_only_after_admitted_review(self):
        with self.assertRaisesRegex(ValueError, 'admitted_action_review_required'):
            self.common.material_lineage_descriptor()
        self.review()
        self.assertIsNone(self.common.material_lineage_descriptor())

    def test_exact_reviewed_lineage_and_replacement(self):
        path = self.root / 'lineage.json'
        path.write_bytes(b'{"synthetic":true}\n')
        row = self.common.descriptor(path)
        self.review(row)
        self.assertEqual(self.common.material_lineage_descriptor(), row)
        path.write_bytes(b'{"synthetic":false}\n')
        with self.assertRaises(ValueError):
            self.common.material_lineage_descriptor()

    def test_review_replacement_and_second_binding_rejected(self):
        path = self.review()
        with self.assertRaisesRegex(ValueError, 'action_review_already_bound'):
            self.common.bind_action_review(path, sha(path.read_bytes()))
        path.write_bytes(b'{}\n')
        with self.assertRaises(ValueError):
            self.common.material_lineage_descriptor()


class PublicationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.transport = load_source('preflight_test_transport', ROOT / 'rl_transport.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pins = {'source_sha256': 'a' * 64, 'source_archive_sha256': 'b' * 64,
            'release_sha256': 'c' * 64, 'policy_sha256': 'd' * 64,
            'collector_entry_sha256': sha((ROOT / 'rl_collect.py').read_bytes())}
        (self.root / 'CONSUMER-OPERATOR.json').write_bytes(encoded(self.pins))
        pin = sha((self.root / 'CONSUMER-OPERATOR.json').read_bytes())
        self.entry = self.root / 'reviewed_entry.py'
        self.entry.write_text('REVIEWED_OPERATOR_PINS_SHA256 = ' + repr(pin) + '\n')
        self.review = {'consumer_files': {'reviewed_entry.py': sha(self.entry.read_bytes())},
                       'operator_files': {'protocol.py': sha((ROOT / 'protocol.py').read_bytes())}}
        self.manifest = {'datasets': [{'transport_archive': {'path': 'code-upload.zip',
            'bytes': 100, 'sha256': 'b' * 64}}], 'consumer_contract': {'source_sha256': 'a' * 64,
            'source_archive': {'sha256': 'b' * 64}, 'release': {'sha256': 'c' * 64},
            'phase_policy': {'sha256': 'd' * 64}}}
        self.args = SimpleNamespace(consumer_root=str(self.root), manifest='synthetic-manifest',
                                    manifest_sha='e' * 64)
        self.monitor = self.enterContext(patch.object(self.transport, 'monitor_gate', return_value=self.review))
        self.finalizer = self.enterContext(patch.object(self.transport, 'finalized_documents', return_value={
            name: b'{"synthetic":true}\n' for name in ('active-finalized.ipynb', 'operator.json',
                                                     'original-request.json', 'parent-private-scorer.json')}))
        self.protocol = SimpleNamespace(validate_request=lambda operation, arguments: arguments,
                                        canonical=encoded)
        self.enterContext(patch.object(self.transport, 'load_source_module', return_value=self.protocol))
        self.enterContext(patch.object(self.transport, 'row', side_effect=lambda manifest, role: {'role': role}))
        self.enterContext(patch.object(self.transport, 'descriptor_at', return_value=b'{"synthetic":true}\n'))
        self.enterContext(patch.object(self.transport, 'kernel_wire', side_effect=lambda row, raw: {'role': row['role']}))

    def test_all_static_checks_without_writes_or_provider(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with patch.object(self.transport, 'Provider', side_effect=AssertionError('provider forbidden')):
            result = self.transport.publication_preflight(self.manifest, self.args)
        self.assertEqual(result['status'], 'OFFLINE_PUBLICATION_CLOSURE_PASS')
        self.assertFalse(result['production_dispatch_admitted'])
        self.assertFalse(result['actual_epoch_reserved'])
        self.assertEqual(result['state_writes'], 0)
        self.finalizer.assert_called_once_with(self.manifest, self.args.manifest, 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_changed_release_fails_before_finalizer(self):
        self.manifest['consumer_contract']['release']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'preflight_consumer_release_chain'):
            self.transport.publication_preflight(self.manifest, self.args)
        self.finalizer.assert_not_called()

    def test_wrong_entry_pin_fails_before_finalizer(self):
        self.entry.write_text('REVIEWED_OPERATOR_PINS_SHA256 = ' + repr('f' * 64) + '\n')
        self.review['consumer_files']['reviewed_entry.py'] = sha(self.entry.read_bytes())
        with self.assertRaisesRegex(ValueError, 'preflight_reviewed_entry_operator_pin'):
            self.transport.publication_preflight(self.manifest, self.args)
        self.finalizer.assert_not_called()

    def test_monitor_rejection_is_not_bypassed(self):
        self.monitor.side_effect = ValueError('synthetic_monitor_rejected')
        with self.assertRaisesRegex(ValueError, 'synthetic_monitor_rejected'):
            self.transport.publication_preflight(self.manifest, self.args)
        self.finalizer.assert_not_called()

    def test_cli_static_preflight_never_constructs_provider(self):
        with patch.object(self.transport, 'parser') as parser, \
             patch.object(self.transport, 'load_contract', return_value=self.manifest), \
             patch.object(self.transport, 'publication_preflight', return_value={'synthetic': True}), \
             patch.object(self.transport, 'Provider', side_effect=AssertionError('provider forbidden')), \
             patch('builtins.print'):
            parser.return_value.parse_args.return_value = SimpleNamespace(action='validate-publication')
            self.assertEqual(self.transport.main(), 0)

    def test_mutation_static_rejection_precedes_lock_and_provider(self):
        with patch.object(self.transport, 'parser') as parser, \
             patch.object(self.transport, 'load_contract', return_value=self.manifest), \
             patch.object(self.transport, 'execution_gate'), \
             patch.object(self.transport, 'publication_preflight', side_effect=ValueError('synthetic_static_rejected')), \
             patch.object(self.transport, 'lock', side_effect=AssertionError('lock forbidden')), \
             patch.object(self.transport, 'Provider', side_effect=AssertionError('provider forbidden')), \
             patch.object(self.transport, 'failure', return_value={'synthetic': True}), \
             patch('builtins.print'):
            parser.return_value.parse_args.return_value = SimpleNamespace(action='update-code')
            self.assertEqual(self.transport.main(), 2)


if __name__ == '__main__':
    unittest.main()

"""Affected exact final consumer tests; synthetic envelopes never admit science."""
import hashlib
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
NEW = ROOT / 'consumer-pinned-001'
OLD = BASE / 'portfolio63-rl-release-20261012/release-candidate-001/terminal-consumer'
RELEASE = ROOT / 'consumer-binding-final-001'
COLLECTOR = ROOT / 'publication/rl_collect.py'
OPERATOR = NEW / 'CONSUMER-OPERATOR.json'
ENTRY_SHA = 'cde1d7e79cadf144e353607f8de99e27930754b9687f715f28558e046ed2744d'
OPERATOR_SHA = 'c9b5c454ec31cb78ff41abf7ef39d79868fc8c5e338f1dc6a3faaecf153eda34'
COLLECTOR_SHA = '051e86df5e45712040dfe0127c095141259953090e75fd964a4ef0c2e2385dec'
RELEASE_SHA = 'cbd2fd5dee0a328da2a43212273fe6432779ee25cefdc06043638ac72039429d'
HELPERS = 'd88b66c3b45435c2b328c2cc36c9c605c889ba76e48a36c22729db0ec2fda710'
TINY = BASE / 'portfolio63-rl-batched-20261012'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def load(name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), module.__dict__)
    return module


class FinalBindingTests(unittest.TestCase):
    def entry(self):
        return load('final_bootstrap_entry_' + self._testMethodName, NEW / 'reviewed_entry.py')

    def test_exact_acyclic_graph(self):
        self.assertEqual(sha(COLLECTOR), COLLECTOR_SHA)
        self.assertEqual(sha(OPERATOR), OPERATOR_SHA)
        self.assertEqual(sha(NEW / 'reviewed_entry.py'), ENTRY_SHA)
        self.assertEqual(sha(RELEASE / 'release.json'), RELEASE_SHA)
        pins = read(OPERATOR)
        self.assertEqual(pins['collector_entry_sha256'], COLLECTOR_SHA)
        self.assertEqual(pins['release_sha256'], RELEASE_SHA)
        release = read(RELEASE / 'release.json')
        for name in ('environment', 'material_review', 'phase_policy', 'owner_protocol'):
            self.assertEqual(sha(RELEASE / (name + '.json')), release[name + '_sha256'])
        self.assertEqual(pins['source_sha256'], release['source_sha256'])
        self.assertEqual(pins['policy_sha256'], release['phase_policy_sha256'])

    def test_all_helpers_unchanged_and_closed(self):
        self.assertEqual(sha(NEW / 'CONSUMER-INVENTORY.json'), HELPERS)
        files = read(NEW / 'CONSUMER-INVENTORY.json')['files']
        self.assertEqual(len(files), 21)
        expected = set(files) | {'CONSUMER-INVENTORY.json', 'CONSUMER-OPERATOR.json', 'reviewed_entry.py'}
        self.assertEqual({p.relative_to(NEW).as_posix() for p in NEW.rglob('*') if p.is_file() and '__pycache__' not in p.parts}, expected)
        for name, value in files.items():
            self.assertEqual(sha(NEW / name), value)
            self.assertEqual((OLD / name).read_bytes(), (NEW / name).read_bytes())

    def test_entry_only_one_literal_changes(self):
        pattern = rb"(?m)^REVIEWED_OPERATOR_PINS_SHA256 = '[0-9a-f]{64}'$"
        before, n1 = re.subn(pattern, b'REVIEWED_OPERATOR_PINS_SHA256 = None', (OLD / 'reviewed_entry.py').read_bytes())
        after, n2 = re.subn(pattern, b'REVIEWED_OPERATOR_PINS_SHA256 = None', (NEW / 'reviewed_entry.py').read_bytes())
        self.assertEqual((n1, n2), (1, 1))
        self.assertEqual(before, after)

    def test_arbitrary_caller_denied(self):
        with self.assertRaisesRegex(ValueError, 'reviewed collector callsite'):
            self.entry().receive_authenticated_collection('not-read', '0' * 64, operator_pins_path=OPERATOR)

    def test_changed_operator_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pins.json'
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'operator pin bytes differ'):
                self.entry().receive_authenticated_collection('not-read', '0' * 64, operator_pins_path=path)

    def test_changed_helper_inventory_pin_denied(self):
        with self.assertRaisesRegex(ValueError, 'helper inventory bytes differ'):
            self.entry()._load_helpers('0' * 64)

    def actual_collector(self, body, archive, terminal, expected):
        collector = load('final_bootstrap_collector_' + self._testMethodName, COLLECTOR)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            envelope = root / 'synthetic-test-collection.json'
            envelope.write_text(json.dumps(body) + '\n')
            args = types.SimpleNamespace(consumer_root=str(NEW), manifest=str(root / 'absent-manifest.json'))
            manifest = {'consumer_contract': {'source_root': str(BASE / 'portfolio63-rl-environment-repair-20261013')}}
            # Only the monitor response is fabricated here. Actual final collector
            # callsite, entry, operator and helpers are executed unchanged.
            with mock.patch.object(collector.transport, 'monitor_gate', return_value={'consumer_files': {'reviewed_entry.py': ENTRY_SHA}}), mock.patch.object(collector, 'OUT', root):
                with self.assertRaisesRegex(ValueError, expected):
                    collector.validate_received(manifest, args, envelope, RELEASE, archive, terminal)

    def genuine(self, report_name):
        report = read(TINY / 'terminal_validation/tests' / report_name)
        body = report['collection']
        pins = read(OPERATOR)
        body.update(policy_sha256=pins['policy_sha256'], release_sha256=pins['release_sha256'], launch_sha256='0' * 64)
        archive = Path(report.get('archive', TINY / 'proof-output.evidence.zip'))
        terminal = Path(report.get('terminal', str(archive) + '.terminal.json'))
        return body, archive, terminal

    def test_actual_collector_rejects_tiny_complete_source(self):
        self.actual_collector(*self.genuine('GENUINE-REPLAY-RESULT.json'), 'collection differs from independently reviewed source_sha256')

    def test_actual_collector_rejects_tiny_failed_source(self):
        self.actual_collector(*self.genuine('SYNTHETIC-FAILED-ENVELOPE-RESULT.json'), 'collection differs from independently reviewed source_sha256')

    def test_actual_collector_rejects_relabelled_tiny(self):
        body, archive, terminal = self.genuine('GENUINE-REPLAY-RESULT.json')
        pins = read(OPERATOR)
        for name in ('source_sha256', 'source_archive_sha256', 'policy_sha256', 'release_sha256'):
            body[name] = pins[name]
        self.actual_collector(body, archive, terminal, 'terminal external source/request/outer lineage differs')


if __name__ == '__main__':
    unittest.main(verbosity=2)

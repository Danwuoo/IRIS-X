"""Split publication history composed with the exact frozen f5 context validator.

These are synthetic offline fixtures, never native/provider admission evidence.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

import test_context_continuation as context
import test_multiround_state as rounds
import test_publication_state as state


class MultiroundContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        context.ContextTests.setUpClass()

    def setUp(self):
        self.base = context.ContextTests(methodName='runTest')
        self.addCleanup(self.base.doCleanups)
        self.base.setUp()
        self.state = self.base.state
        self.original = self.snapshot()
        self.writes = list(self.base.fixture.c.writes)
        temp = tempfile.TemporaryDirectory(prefix='synthetic-multiround-context-')
        self.addCleanup(temp.cleanup)
        writer = types.SimpleNamespace(base=Path(temp.name))
        for name in ('make_manifest', 'make_round'):
            setattr(writer, name, types.MethodType(getattr(rounds.MultiroundStateTests, name), writer))
        self.old = writer.make_round(self.state, 21)
        self.current_manifest = writer.make_manifest(22, self.old['source'])
        self.selected = self.state / 'publications/code-v22'
        self.base.current.update(candidate_root=str(Path(self.current_manifest['path']).parent),
            publication_manifest_sha256=self.current_manifest['sha256'], versions=rounds.versions(22),
            publication={'history': [{'root': str(self.state), 'manifest': self.old['manifest']}]})
        self.base.config.publication_state_root = self.selected
        self.base.bind_current()
        self.base.callbacks['publication_manifest_descriptor'] = lambda: self.current_manifest
        (self.base.deployment / 'publication_state.py').write_bytes((context.ROOT / 'publication_state.py').read_bytes())
        # A new round's own partial reservation is legitimate read-only state.
        state.write(self.selected / 'dataset-code-v22.claim.json', {
            'manifest_sha256': self.current_manifest['sha256'],
            'expected_version': 22, 'expected_predecessor_version': 21})

    def snapshot(self):
        return {path.relative_to(self.state).as_posix(): path.read_bytes()
                for path in self.state.rglob('*') if path.is_file()}

    def assert_original_unchanged(self):
        for name, raw in self.original.items():
            self.assertEqual((self.state / name).read_bytes(), raw)
        journal = json.loads(Path(self.base.pending[0]['journal']['path']).read_bytes())
        self.assertEqual(journal['stage'], 'UNKNOWN')
        self.assertFalse(journal['native_process_closure_verified'])
        self.assertEqual(self.writes, self.base.fixture.c.writes)

    def test_old21_and_current22_compose_with_frozen_unknown_eligibility(self):
        before = self.snapshot()
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('no native/provider process')):
            result = self.base.validate()
        self.assertEqual(result, {self.base.fixture.review_value['unknown_session']:
                                  self.base.pending[0]['claim']['sha256']})
        self.assertEqual(before, self.snapshot())
        self.assert_original_unchanged()
        self.assertNotEqual(self.old['manifest']['sha256'], self.current_manifest['sha256'])
        self.assertFalse((self.selected / 'dataset-code-v22-receipt.json').exists())

    def test_split_history_does_not_hide_new_native_or_refresh_unknown(self):
        for prefix, stage, error in (
            ('native-bridge-' + 'f' * 64, 'UNKNOWN', 'later_session_unknown'),
            ('native-auth-refresh-' + 'f' * 24, 'refresh_intent', 'later_refresh_unknown')):
            with self.subTest(prefix=prefix):
                claim = state.write(self.state / (prefix + '.claim.json'), {'nonce': 'f' * 64})
                state.write(self.state / (prefix + '-journal.json'), {
                    'stage': stage, 'native_process_closure_verified': False, 'claim_sha256': claim['sha256']})
                before = self.snapshot()
                with patch.object(subprocess, 'Popen', side_effect=AssertionError('no native/provider process')):
                    with self.assertRaisesRegex(ValueError, error):
                        self.base.validate()
                self.assertEqual(before, self.snapshot())
                self.assert_original_unchanged()
                (self.state / (prefix + '.claim.json')).unlink()
                (self.state / (prefix + '-journal.json')).unlink()


if __name__ == '__main__':
    unittest.main()

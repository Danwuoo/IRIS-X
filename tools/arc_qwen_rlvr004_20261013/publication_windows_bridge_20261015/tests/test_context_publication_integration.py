"""Synthetic publication stages through the exact historical f5 validator.

No candidate/runtime/auth/provider acceptance: this tests read-only history
interpretation alongside real-shaped, explicitly synthetic publication files.
"""
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import test_context_continuation as context
import test_publication_state as state


class ContextPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        context.ContextTests.setUpClass()

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='synthetic-context-publication-')
        self.addCleanup(temp.cleanup)
        self.candidate = Path(temp.name)
        self.descriptor = state.write(self.candidate / 'publication-manifest.json', state.manifest())
        original_write = context.f.write
        def write(path, value):
            if path.name == 'original-local.json':
                value['publication_manifest_sha256'] = self.descriptor['sha256']
            return original_write(path, value)
        self.base = context.ContextTests(methodName='runTest')
        self.addCleanup(self.base.doCleanups)
        with patch.object(context.f, 'write', side_effect=write):
            self.base.setUp()
        for name in ('material_lineage.py', 'publication_state.py'):
            (self.base.deployment / name).write_bytes((context.ROOT / name).read_bytes())
        self.base.callbacks['publication_manifest_descriptor'] = lambda: self.descriptor
        self.state = self.base.state
        self.original = {p.relative_to(self.state).as_posix(): p.read_bytes()
                         for p in self.state.rglob('*') if p.is_file()}
        self.writer = types.SimpleNamespace(state=self.state, descriptor=self.descriptor,
            versions=state.versions(), payload=state.payload())
        for name in ('code_claim', 'notebook_claim', 'readback'):
            setattr(self.writer, name, types.MethodType(getattr(state.PublicationStateTests, name), self.writer))

    def admitted_history(self):
        result = self.base.validate()
        for name, raw in self.original.items():
            self.assertEqual((self.state / name).read_bytes(), raw)
        journal = json.loads((self.state / ('native-bridge-' + self.base.fixture.failed_nonce + '-journal.json')).read_bytes())
        self.assertEqual(journal['stage'], 'UNKNOWN')
        self.assertFalse(journal['native_process_closure_verified'])
        return result

    def test_every_publication_stage_preserves_original_history(self):
        self.admitted_history()
        self.writer.code_claim('version_accepted')
        self.admitted_history()
        readback = self.writer.readback([])
        self.admitted_history()
        for name, raw in self.writer.payload.items():
            state.write(readback / 'payload' / name, raw)
            self.admitted_history()
        code = 'dataset-code-v21'
        state.write(self.state / (code + '-receipt.json'), {
            'manifest_sha256': self.descriptor['sha256'], 'publication_manifest_sha256': self.descriptor['sha256'],
            'version': 21, 'dataset_id': 12504696,
            'claim_sha256': state.digest((self.state / (code + '.claim.json')).read_bytes()),
            'journal_sha256': state.digest((self.state / (code + '-journal.json')).read_bytes())})
        self.admitted_history()
        notebook = {'cells': [{'source': 'x' * 70000}], 'metadata': {}, 'nbformat': 4}
        for role, version in (('inactive', 40), ('rlvr004', 41)):
            stem, _, _ = self.writer.notebook_claim(role, 'save_accepted')
            state.write(self.state / (stem + '-wire.json'), {'id': 138123872, 'slug': state.p.REF,
                'text': state.encoded(notebook).decode(), 'dataset_data_sources': [state.p.DREF + '/21']})
            self.admitted_history()
            state.write(self.state / (stem + '-saved.ipynb'), notebook)
            self.admitted_history()
            state.write(self.state / (stem + '-receipt.json'), {
                'manifest_sha256': self.descriptor['sha256'], 'role': role, 'reference': state.p.REF,
                'kernel_id': 138123872, 'version': version,
                'launch_journal_sha256': state.digest((self.state / (stem + '-journal.json')).read_bytes())})
            self.admitted_history()
        documents = {'active-finalized.ipynb': notebook, 'original-request.json': {'synthetic': True},
            'operator.json': {'synthetic': True}, 'parent-private-scorer.json': {
                'format': 'owned-rl-parent-scorer-material-v1', 'scope': 'production-rl-abc', 'role': 'rl-abc',
                'owner_id': 'synthetic', 'original_request_id': 'synthetic', 'original_request_sha256': 'a' * 64,
                'raw_source_sha256': 'b' * 64, 'evaluator_root': '/synthetic/never-read',
                'evaluator_manifest_sha256': 'c' * 64, 'scorer_pins_sha256': 'd' * 64}}
        rows = {}
        for name, value in documents.items():
            rows[name] = state.write(self.state / name, value)
            self.admitted_history()
        state.write(self.state / 'finalization.json', {'format': 'irisx/rlvr-finalization-v1',
            'manifest_sha256': self.descriptor['sha256'], 'documents': rows})
        self.admitted_history()

    def test_new_unknown_is_not_hidden_behind_readback_directory(self):
        self.writer.readback()
        stem = 'native-bridge-' + 'f' * 64
        claim = state.write(self.state / (stem + '.claim.json'), {'nonce': 'f' * 64})
        state.write(self.state / (stem + '-journal.json'), {'stage': 'UNKNOWN',
            'native_process_closure_verified': False, 'claim_sha256': claim['sha256']})
        with self.assertRaisesRegex(ValueError, 'later_session_unknown'):
            self.base.validate()

    def test_new_pending_refresh_is_not_hidden_behind_readback_directory(self):
        self.writer.readback()
        stem = 'native-auth-refresh-' + 'f' * 24
        claim = state.write(self.state / (stem + '.claim.json'), {'synthetic': True})
        state.write(self.state / (stem + '-journal.json'), {'stage': 'refresh_intent',
            'claim_sha256': claim['sha256']})
        with self.assertRaisesRegex(ValueError, 'later_refresh_unknown'):
            self.base.validate()

    def test_original_history_change_still_rejected_after_publication(self):
        self.writer.readback()
        path = next(self.state / name for name in self.original if name.startswith('events/'))
        path.write_bytes(b'{"changed":true}\n')
        with self.assertRaisesRegex(ValueError, 'sealed_bytes_changed'):
            self.base.validate()

    def test_observer_time_publication_replacement_is_rejected(self):
        self.writer.code_claim()
        def observer(review, challenge):
            path = self.state / 'dataset-code-v21-journal.json'
            value = json.loads(path.read_bytes())
            value['stage'] = 'version_accepted'
            state.write(path, value)
            return self.base.boot
        self.base.callbacks['recovery_boot_observation'] = observer
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'):
            self.base.validate()


if __name__ == '__main__':
    unittest.main()

"""Offline round-selection fixtures; no provider, credential or native execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import test_publication_state as f

p, h = f.p, f.h
ROOT = f.ROOT
spec = importlib.util.spec_from_file_location('multiround_config_fixture', ROOT / 'config.py')
config = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = config
spec.loader.exec_module(config)


def versions(code):
    return {'code_predecessor': code - 1, 'code': code,
            'inactive_predecessor': 2 * code - 3, 'inactive': 2 * code - 2, 'active': 2 * code - 1}


class MultiroundStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='offline-multiround-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / 'state'
        self.state.mkdir()
        (self.state / 'events').mkdir()
        self.native = 'native-bridge-' + 'a' * 64
        self.original_native = f.encoded({'stage': 'UNKNOWN', 'synthetic_fixture': True})
        f.write(self.state / (self.native + '-journal.json'), self.original_native)
        self.old = self.make_round(self.state, 21)
        self.selected = self.state / 'publications' / 'code-v22'
        self.current = self.make_manifest(22, self.old['source'])
        self.history = [{'root': str(self.state), 'manifest': self.old['manifest']}]

    def make_manifest(self, code, predecessor='f' * 64):
        value = f.manifest(configured_versions=versions(code))
        value['notebooks'][0]['predecessor_source_sha256'] = predecessor
        value['notebooks'][0]['sha256'] = f.digest(f.encoded({'cells': [], 'nbformat': 4}))
        return f.write(self.base / ('candidate-' + str(code)) / 'publication-manifest.json', value)

    def make_round(self, root, code, predecessor='f' * 64):
        root.mkdir(parents=True, exist_ok=True)
        allocated = versions(code)
        manifest = self.make_manifest(code, predecessor)
        digest = manifest['sha256']
        stem = 'dataset-code-v' + str(code)
        claim = f.write(root / (stem + '.claim.json'), {'manifest_sha256': digest,
            'expected_version': code, 'expected_predecessor_version': code - 1})
        journal = f.write(root / (stem + '-journal.json'), {'manifest_sha256': digest,
            'expected_version': code, 'expected_predecessor_version': code - 1,
            'claim_sha256': claim['sha256'], 'version_calls': 1})
        f.write(root / (stem + '-receipt.json'), {'manifest_sha256': digest,
            'publication_manifest_sha256': digest, 'version': code, 'dataset_id': 12504696,
            'claim_sha256': claim['sha256'], 'journal_sha256': journal['sha256'], 'exact_byte_roundtrip': True})
        for name, raw in f.payload().items():
            f.write(root / ('code-v' + str(code) + '-readback') / 'payload' / name, raw)
        active = f.encoded({'cells': [{'source': 'inert round ' + str(code)}], 'nbformat': 4})
        docs = {'active-finalized.ipynb': active, 'original-request.json': {}, 'operator.json': {},
                'parent-private-scorer.json': {'format': 'owned-rl-parent-scorer-material-v1',
                    'scope': 'production-rl-abc', 'role': 'rl-abc', 'owner_id': 'synthetic-owner',
                    'original_request_id': 'synthetic-request', 'original_request_sha256': 'a' * 64,
                    'raw_source_sha256': 'b' * 64, 'evaluator_root': '/synthetic/evaluator',
                    'evaluator_manifest_sha256': 'c' * 64, 'scorer_pins_sha256': 'd' * 64}}
        descriptors = {name: f.write(root / name, raw) for name, raw in docs.items()}
        final = f.write(root / 'finalization.json', {'format': 'irisx/rlvr-finalization-v1',
            'manifest_sha256': digest, 'documents': descriptors, 'finalized_sha256': f.digest(active)})
        for role in ('inactive', 'rlvr004'):
            name = 'notebook-' + role
            number = allocated['inactive' if role == 'inactive' else 'active']
            metadata = {'manifest_sha256': digest, 'reference': p.REF, 'kernel_id': 138123872, 'role': role}
            claim = f.write(root / (name + '.claim.json'), dict(metadata, expected_version=number))
            raw = active if role == 'rlvr004' else f.encoded({'cells': [], 'nbformat': 4})
            saved = f.write(root / (name + '-saved.ipynb'), raw)
            wire = f.write(root / (name + '-wire.json'), {'id': 138123872, 'slug': p.REF,
                'text': raw.decode(), 'dataset_data_sources': [p.DREF + '/' + str(code)]})
            journal = f.write(root / (name + '-journal.json'), dict(metadata, expected_version=number,
                claim_sha256=claim['sha256'], save_calls=1, wire_sha256=wire['sha256'], source_sha256=f.digest(raw),
                finalization_sha256=final['sha256'] if role == 'rlvr004' else None))
            f.write(root / (name + '-receipt.json'), dict(metadata, version=number,
                launch_journal_sha256=journal['sha256'], status='COMPLETE' if role == 'inactive' else 'RUNNING',
                normalized_source_exact=True, saved_source=saved, submitted_source_sha256=f.digest(raw),
                finalization_sha256=final['sha256'] if role == 'rlvr004' else None))
        f.write(root / 'active-readback.claim.json', {'manifest_sha256': digest,
            'numeric_notebook_version': allocated['active'], 'launch_claim_sha256': claim['sha256'],
            'action': 'initial_post_submit_readback'})
        inventory = {'old-source.zip': 123}
        for number in range(8, max(7, code - 10) + 1):
            f.write(root / ('historical-code-v' + str(number) + '-inventory.json'),
                {'dataset_id': 12504696, 'numeric_version': number,
                 'captured_while_current_version': code - 1, 'inventory_sha256': f.digest(f.encoded(inventory)),
                 'files_inventory': inventory, 'payload_bytes_rehashed': False})
        return {'manifest': manifest, 'source': f.digest(active)}

    def capture(self):
        return p.capture(self.state, self.current, versions(22), h,
                         publication_root=self.selected, publication_history=self.history)

    def snapshot(self):
        return {str(path.relative_to(self.state)): path.read_bytes()
                for path in self.state.rglob('*') if path.is_file()}

    def test_flat_v41_uses_own_manifest_and_preserves_native_unknown_bytes(self):
        before = self.snapshot()
        view = self.capture()
        self.assertEqual(view.root_records(self.state), {self.native + '-journal.json': self.original_native})
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.selected.parent.exists())
        self.assertNotEqual(self.old['manifest']['sha256'], self.current['sha256'])

    def test_partial_current_round_allows_readonly_reconciliation(self):
        f.write(self.selected / 'dataset-code-v22.claim.json', {'manifest_sha256': self.current['sha256'],
            'expected_version': 22, 'expected_predecessor_version': 21})
        self.capture().verify_unchanged()
        self.assertFalse((self.selected / 'dataset-code-v22-receipt.json').exists())

    def test_prior_unknown_mutation_blocks_new_round_without_closure_invention(self):
        (self.state / 'notebook-rlvr004-receipt.json').unlink()
        with self.assertRaisesRegex(ValueError, 'previous_mutation_unresolved'):
            self.capture()

    def test_prior_readback_must_be_complete(self):
        (self.state / 'code-v21-readback/payload/NOTICE.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'historical_readback_incomplete'):
            self.capture()

    def test_prior_source_must_match_new_manifest_predecessor(self):
        self.current = self.make_manifest(22, '0' * 64)
        with self.assertRaisesRegex(ValueError, 'predecessor_source'):
            self.capture()

    def test_old_manifest_cannot_be_replaced_by_current_manifest(self):
        self.history[0]['manifest'] = self.current
        with self.assertRaisesRegex(ValueError, 'duplicate_allocation'):
            self.capture()

    def test_historical_manifest_file_change_is_rejected(self):
        path = Path(self.old['manifest']['path'])
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'descriptor_changed'):
            self.capture()

    def test_unregistered_round_and_old_flat_publication_names_are_rejected(self):
        extra = self.selected.parent / 'code-v23'
        extra.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'unregistered_round'):
            self.capture()
        extra.rmdir()
        f.write(self.state / 'dataset-code-v22.claim.json', {})
        with self.assertRaisesRegex(ValueError, 'unexpected_root'):
            self.capture()

    def test_round_directory_cannot_hide_native_or_events(self):
        f.write(self.selected / 'native-bridge-hidden.claim.json', {})
        with self.assertRaisesRegex(ValueError, 'unexpected_round_file'):
            self.capture()
        (self.selected / 'native-bridge-hidden.claim.json').unlink()
        (self.selected / 'events').mkdir()
        with self.assertRaisesRegex(ValueError, 'round_events_forbidden'):
            self.capture()

    def test_current_namespace_is_numeric_not_manifest_selected(self):
        self.selected = self.selected.with_name('code-v22-other-manifest')
        with self.assertRaisesRegex(ValueError, 'selected_round_root'):
            self.capture()

    def test_prior_active_readback_claim_cannot_disappear(self):
        (self.state / 'active-readback.claim.json').unlink()
        with self.assertRaisesRegex(ValueError, 'previous_readback_claim_missing'):
            self.capture()

    def test_historical_retention_cannot_disappear_between_rounds(self):
        (self.state / 'historical-code-v8-inventory.json').unlink()
        with self.assertRaisesRegex(ValueError, 'previous_retention_missing'):
            self.capture()

    def test_prior_retention_capture_remains_20(self):
        self.capture()
        value = json.loads((self.state / 'historical-code-v8-inventory.json').read_bytes())
        self.assertEqual(value['captured_while_current_version'], 20)

    def test_history_and_selected_tree_rechecked_after_capture(self):
        self.selected.mkdir(parents=True)
        view = self.capture()
        f.write(self.selected / 'notebook-inactive.claim.json', {'manifest_sha256': self.current['sha256'],
            'expected_version': 42, 'kernel_id': 138123872, 'reference': p.REF, 'role': 'inactive'})
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'):
            view.verify_unchanged()

    def test_third_round_projects_all_prior_directories(self):
        second = self.make_round(self.selected, 22, self.old['source'])
        third = self.make_manifest(23, second['source'])
        history = self.history + [{'root': str(self.selected), 'manifest': second['manifest']}]
        view = p.capture(self.state, third, versions(23), h,
                         publication_root=self.selected.with_name('code-v23'), publication_history=history)
        self.assertEqual(view.root_records(self.state)[self.native + '-journal.json'], self.original_native)
        with self.assertRaisesRegex(ValueError, 'predecessor_allocation|unregistered_round'):
            p.capture(self.state, third, versions(23), h,
                      publication_root=self.selected.with_name('code-v23'), publication_history=self.history)

    def test_duplicate_history_allocation_rejected(self):
        self.history.append(copy.deepcopy(self.history[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate_allocation'):
            self.capture()

    def test_history_extra_key_and_linked_round_rejected(self):
        self.history[0]['ignore'] = True
        with self.assertRaisesRegex(ValueError, 'history_row'):
            self.capture()
        del self.history[0]['ignore']
        self.selected.parent.mkdir()
        self.selected.symlink_to(self.state, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'round_directory_type'):
            self.capture()


    def test_unconditional_selection_checks_even_with_no_native_pending_claim(self):
        (self.state / (self.native + '-journal.json')).unlink()
        view = p.validate_selection(self.state, self.current, versions(22),
            publication_root=self.selected, publication_history=self.history)
        self.assertEqual(view.root_records(self.state), {})
        (self.state / 'dataset-code-v21-receipt.json').unlink()
        with self.assertRaisesRegex(ValueError, 'previous_mutation_unresolved'):
            p.validate_selection(self.state, self.current, versions(22),
                publication_root=self.selected, publication_history=self.history)

    def test_historical_wire_and_saved_bytes_are_linked(self):
        path = self.state / 'notebook-rlvr004-wire.json'
        wire = json.loads(path.read_bytes())
        wire['text'] = f.encoded({'cells': [], 'nbformat': 4}).decode()
        f.write(path, wire)
        with self.assertRaisesRegex(ValueError, 'previous_wire_source_binding'):
            self.capture()

    def test_configuration_derives_paths_and_authenticates_history(self):
        paths = {'state_root': self.state, 'evidence_root': self.base / 'evidence'}
        self.assertEqual(config.publication_selection({}, paths, versions(22)),
                         (self.state, self.base / 'evidence', ()))
        selected, evidence, history = config.publication_selection({'publication': {'history': self.history}},
                                                                  paths, versions(22))
        self.assertEqual(selected, self.selected)
        self.assertEqual(evidence, self.base / 'evidence/code-v22')
        self.assertEqual(history[0]['manifest']['sha256'], self.old['manifest']['sha256'])
        with self.assertRaises(TypeError):
            history[0]['root'] = '/changed'
        p.capture(self.state, self.current, versions(22), h, publication_root=selected, publication_history=history)
        self.history[0]['manifest']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'manifest_bytes'):
            config.publication_selection({'publication': {'history': self.history}}, paths, versions(22))


if __name__ == '__main__':
    unittest.main()

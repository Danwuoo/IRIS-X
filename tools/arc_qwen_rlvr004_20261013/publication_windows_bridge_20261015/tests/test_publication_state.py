"""Offline namespace/integrity fixtures; no provider, auth, recovery, or training."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


p = load('test_publication_state_module', ROOT / 'publication_state.py')
h = load('test_publication_frozen_f5', ROOT / 'recovery_epoch.py')


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    raw = value if type(value) is bytes else encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)}


def versions():
    """Fresh genuine numeric version shape for offline context integrations."""
    return {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39,
            'inactive': 40, 'active': 41}


def payload():
    return {'NOTICE.txt': b'synthetic fixture only\n', 'deployment/helper.py': b'# inert\n',
            'deployment/__init__.py': b'', 'source.zip': b'synthetic opaque source member\n'}


def manifest(files=None, configured_versions=None):
    """Reusable manifest namespace fixture; no runtime/provider admission claim."""
    files = payload() if files is None else files
    v = versions() if configured_versions is None else configured_versions
    inventory = [{'path': name, 'bytes': len(raw), 'sha256': digest(raw)}
                 for name, raw in files.items()]
    return {'format': 'irisx/qwen14b-rlvr-run008-publication-contract-v1',
        'datasets': [{'id': 12504696, 'reference': p.DREF,
                      'expected_predecessor_version': v['code_predecessor'],
                      'expected_version': v['code'],
                      'expected_readback_layouts': {'extracted-root': inventory}}],
        'notebooks': [{'role': role, 'existing_notebook_id': 138123872,
                       'existing_notebook_reference': p.REF, 'expected_predecessor_version': before,
                       'expected_version': after, 'dataset_sources': [p.DREF + '/' + str(v['code'])]}
                      for role, before, after in (('inactive', v['inactive_predecessor'], v['inactive']),
                                                 ('rlvr004', v['inactive'], v['active']))],
        'jit': {'output_documents': sorted(p.JIT_NAMES)}}


class PublicationStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='offline-publication-state-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / 'state'
        (self.state / 'events').mkdir(parents=True)
        self.versions = versions()
        self.native = 'native-bridge-' + 'a' * 64
        self.history = {
            self.native + '.claim.json': encoded({'format': 'synthetic-preserved-claim', 'nonce': 'a' * 64}),
            self.native + '-journal.json': encoded({'stage': 'UNKNOWN', 'synthetic_fixture': True}),
            'events/1-original-01234567.json': encoded({'synthetic_immutable_event': True})}
        for name, raw in self.history.items():
            write(self.state / name, raw)
        self.frontier = {'root': str(self.state), 'files': {
            name: {'bytes': len(raw), 'sha256': digest(raw)} for name, raw in self.history.items()}}
        self.payload = payload()
        self.manifest = manifest(self.payload, self.versions)
        self.manifest_path = self.base / 'candidate' / 'manifest.json'
        self.bind_manifest()

    def bind_manifest(self):
        self.descriptor = write(self.manifest_path, self.manifest)

    def capture(self, **kwargs):
        options = {'frontier': self.frontier}
        options.update(kwargs)
        return p.capture(self.state, self.descriptor, self.versions, h, **options)

    def code_claim(self, stage='version_intent'):
        self.code = 'dataset-code-v21'
        claim = {'manifest_sha256': self.descriptor['sha256'], 'stage': 'claimed', 'init_calls': 0,
                 'put_calls': 0, 'version_calls': 0, 'payload_sha256': 'b' * 64,
                 'expected_version': 21, 'expected_predecessor_version': 20}
        desc = write(self.state / (self.code + '.claim.json'), claim)
        journal = dict(claim, claim_sha256=desc['sha256'], stage=stage,
                       init_calls=1, put_calls=1, version_calls=1)
        write(self.state / (self.code + '-journal.json'), journal)
        return claim, journal

    def notebook_claim(self, role='inactive', stage='save_intent'):
        name = 'notebook-' + role
        claim = {'role': role, 'reference': p.REF, 'kernel_id': 138123872,
                 'expected_version': 40 if role == 'inactive' else 41,
                 'manifest_sha256': self.descriptor['sha256'], 'stage': 'claimed', 'save_calls': 0}
        desc = write(self.state / (name + '.claim.json'), claim)
        journal = dict(claim, claim_sha256=desc['sha256'], stage=stage, save_calls=1)
        write(self.state / (name + '-journal.json'), journal)
        return name, claim, journal

    def readback(self, names=None):
        self.code_claim()
        root = self.state / 'code-v21-readback'
        (root / 'payload').mkdir(parents=True, exist_ok=True)
        for name in self.payload if names is None else names:
            write(root / 'payload' / name, self.payload[name])
        return root

    def test_no_publication_preserves_every_historical_root_byte(self):
        before = {path.relative_to(self.state).as_posix(): path.read_bytes()
                  for path in self.state.rglob('*') if path.is_file()}
        view = self.capture()
        expected = {name: raw for name, raw in self.history.items() if not name.startswith('events/')}
        self.assertEqual(view.root_records(self.state), expected)
        result = view.root_records(self.state)
        result.clear()
        self.assertEqual(view.root_records(self.state), expected)
        self.assertEqual(before, {path.relative_to(self.state).as_posix(): path.read_bytes()
                                for path in self.state.rglob('*') if path.is_file()})

    def test_old_parser_rejects_directory_but_readonly_view_preserves_history(self):
        self.readback()
        with self.assertRaises(ValueError):
            h._root_records(self.state)
        view = self.capture()
        self.assertEqual(set(view.root_records(self.state)), {name for name in self.history if '/' not in name})

    def test_empty_and_partial_exact_payload_are_not_success_receipts(self):
        root = self.readback([])
        view = self.capture()
        self.assertFalse((self.state / 'dataset-code-v21-receipt.json').exists())
        self.assertNotIn('code-v21-readback', view.root_records(self.state))
        write(root / 'payload' / 'NOTICE.txt', self.payload['NOTICE.txt'])
        self.capture().verify_unchanged()

    def test_different_layout_subsets_cannot_be_mixed(self):
        self.manifest['datasets'][0]['expected_readback_layouts']['wrapped'] = [
            {'path': 'wrapper.zip', 'bytes': 3, 'sha256': digest(b'zip')}]
        self.bind_manifest()
        root = self.readback(['NOTICE.txt'])
        write(root / 'payload' / 'wrapper.zip', b'zip')
        with self.assertRaisesRegex(ValueError, 'mixed_payload_layout'):
            self.capture()

    def test_whole_archive_matches_manifest_and_metadata(self):
        root = self.readback(['NOTICE.txt'])
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, raw in self.payload.items():
                archive.writestr(name, raw)
        desc = write(root / 'provider.zip', stream.getvalue())
        write(root / 'archive-download.json', desc)
        self.capture().verify_unchanged()

    def test_archive_extra_empty_directory_and_orphan_readback_are_rejected(self):
        root = self.readback([])
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, raw in self.payload.items():
                archive.writestr(name, raw)
            archive.writestr('unrelated/', b'')
        write(root / 'provider.zip', stream.getvalue())
        with self.assertRaisesRegex(ValueError, 'archive_extra_directory'):
            self.capture()
        (root / 'provider.zip').unlink()
        (self.state / 'dataset-code-v21.claim.json').unlink()
        (self.state / 'dataset-code-v21-journal.json').unlink()
        with self.assertRaisesRegex(ValueError, 'readback_claim_required'):
            self.capture()

    def test_committed_real_inventory_paths_and_sizes_are_supported(self):
        release = json.loads((ROOT.parent / 'release/publication-manifest.json').read_bytes())
        self.manifest['datasets'][0]['expected_readback_layouts'] = release['datasets'][0]['expected_readback_layouts']
        self.bind_manifest()
        self.capture().verify_unchanged()

    def test_wrong_whole_archive_inventory_is_rejected(self):
        root = self.readback([])
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('evil.txt', b'not the candidate')
        write(root / 'provider.zip', stream.getvalue())
        with self.assertRaisesRegex(ValueError, 'archive_layout'):
            self.capture()

    def test_archive_metadata_cannot_reference_other_path(self):
        root = self.readback([])
        write(root / 'archive-download.json', {'path': '/foreign/archive.zip', 'bytes': 1, 'sha256': 'a' * 64})
        with self.assertRaisesRegex(ValueError, 'archive_descriptor'):
            self.capture()

    def test_temp_partial_and_unexpected_payload_entries_fail_closed(self):
        root = self.readback([])
        for name in ('provider.zip.partial', 'provider.zip.tmp', 'quarantined-partials', 'foreign.json'):
            with self.subTest(name=name):
                path = root / name
                write(path, b'x')
                with self.assertRaisesRegex(ValueError, 'unexpected_readback_entry'):
                    self.capture()
                path.unlink()
        write(root / 'payload' / 'unexpected.txt', b'x')
        with self.assertRaisesRegex(ValueError, 'extra_payload_file'):
            self.capture()

    def test_extra_empty_payload_directory_fails(self):
        root = self.readback([])
        (root / 'payload' / 'unexpected').mkdir()
        with self.assertRaisesRegex(ValueError, 'extra_payload_directory'):
            self.capture()

    def test_payload_bytes_must_already_match_current_manifest(self):
        root = self.readback(['NOTICE.txt'])
        write(root / 'payload' / 'NOTICE.txt', b'corrupt payload bytes\n')
        with self.assertRaises(ValueError):
            self.capture()

    def test_publication_claim_with_foreign_manifest_is_not_hidden(self):
        claim, _ = self.code_claim()
        claim['manifest_sha256'] = '0' * 64
        write(self.state / (self.code + '.claim.json'), claim)
        with self.assertRaisesRegex(ValueError, 'foreign_manifest'):
            self.capture()

    def test_publication_journal_with_foreign_manifest_is_not_hidden(self):
        _, journal = self.code_claim()
        journal['manifest_sha256'] = '0' * 64
        write(self.state / (self.code + '-journal.json'), journal)
        with self.assertRaisesRegex(ValueError, 'foreign_manifest'):
            self.capture()

    def test_versions_reject_bool_string_wrong_numbers_and_old_names(self):
        for value in (True, '21', 22):
            with self.subTest(value=value):
                claim, _ = self.code_claim()
                claim['expected_version'] = value
                write(self.state / (self.code + '.claim.json'), claim)
                with self.assertRaisesRegex(ValueError, 'record_version'):
                    self.capture()
        for name in ('dataset-code-v20.claim.json', 'notebook-other.claim.json', 'historical-code-v12-inventory.json'):
            with self.subTest(name=name):
                for path in self.state.glob('dataset-code-v21*'):
                    path.unlink()
                write(self.state / name, {})
                with self.assertRaisesRegex(ValueError, 'unexpected_root'):
                    self.capture()
                (self.state / name).unlink()

    def test_historical_numeric_inventory_is_bounded_and_exact(self):
        inventory = {'source.zip': 1234, 'NOTICE.txt': 12}
        value = {'dataset_id': 12504696, 'numeric_version': 11, 'captured_while_current_version': 20,
                 'inventory_sha256': digest(encoded(inventory)), 'files_inventory': inventory,
                 'payload_bytes_rehashed': False}
        write(self.state / 'historical-code-v11-inventory.json', value)
        self.capture()
        value['numeric_version'] = True
        write(self.state / 'historical-code-v11-inventory.json', value)
        with self.assertRaisesRegex(ValueError, 'record_version'):
            self.capture()

    def test_large_notebook_sources_and_wire_stay_out_of_f5_tiny_strings(self):
        name, _, _ = self.notebook_claim()
        notebook = {'cells': [{'source': 'x' * 70000}], 'metadata': {}, 'nbformat': 4}
        raw = encoded(notebook)
        write(self.state / (name + '-saved.ipynb'), raw)
        wire = {'id': 138123872, 'slug': p.REF, 'text': raw.decode(), 'dataset_data_sources': [p.DREF + '/21']}
        write(self.state / (name + '-wire.json'), wire)
        with self.assertRaisesRegex(ValueError, 'string_bound'):
            h.strict_json(encoded(wire))
        self.capture().verify_unchanged()

    def test_foreign_wire_code_pin_is_not_hidden(self):
        name, _, _ = self.notebook_claim()
        write(self.state / (name + '-wire.json'), {'id': 138123872, 'slug': p.REF, 'text': '{}',
                                                'dataset_data_sources': [p.DREF + '/20']})
        with self.assertRaisesRegex(ValueError, 'wire_code_pin'):
            self.capture()

    def test_exact_jit_metadata_documents_and_finalization_allowed(self):
        self.notebook_claim('rlvr004', 'wire_prepared')
        values = {'active-finalized.ipynb': {'cells': [{'source': 'x' * 70000}], 'nbformat': 4},
                  'original-request.json': {'format': 'synthetic-owner'},
                  'operator.json': {'format': 'synthetic-operator'},
                  'parent-private-scorer.json': {'format': 'owned-rl-parent-scorer-material-v1',
                      'scope': 'production-rl-abc', 'role': 'rl-abc', 'owner_id': 'synthetic-owner',
                      'original_request_id': 'synthetic-request', 'original_request_sha256': 'a' * 64,
                      'raw_source_sha256': 'b' * 64, 'evaluator_root': '/synthetic/evaluator',
                      'evaluator_manifest_sha256': 'c' * 64, 'scorer_pins_sha256': 'd' * 64}}
        documents = {name: write(self.state / name, value) for name, value in values.items()}
        write(self.state / 'finalization.json', {'format': 'irisx/rlvr-finalization-v1',
              'manifest_sha256': self.descriptor['sha256'], 'documents': documents})
        self.capture().verify_unchanged()
        values['parent-private-scorer.json']['evaluator_body'] = {'must_never_be_admitted': True}
        write(self.state / 'parent-private-scorer.json', values['parent-private-scorer.json'])
        (self.state / 'finalization.json').unlink()
        with self.assertRaisesRegex(ValueError, 'parent_metadata_only'):
            self.capture()

    def test_additional_unknown_native_refresh_and_recovery_roots_all_reach_f5(self):
        extras = {'native-bridge-' + 'b' * 64 + '.claim.json': {'unknown': True},
                  'native-auth-refresh-' + 'c' * 24 + '.claim.json': {'stage': 'refresh_intent'},
                  'recovery-epoch-' + 'd' * 64 + '.claim.json': {'stage': 'prepared'}}
        for name, value in extras.items():
            write(self.state / name, value)
        original = h.strict_json
        with mock.patch.object(h, 'strict_json', wraps=original) as parser:
            result = self.capture().root_records(self.state)
        for name, value in extras.items():
            self.assertEqual(result[name], encoded(value))
            self.assertTrue(any(call.args == (encoded(value),) for call in parser.call_args_list))
        self.assertEqual(result[self.native + '-journal.json'], self.history[self.native + '-journal.json'])

    def test_native_malformed_json_and_path_receive_original_f5_rejection(self):
        for name, raw, error in (('native-bridge-malformed.claim.json', b'{"same":1,"same":2}', 'recovery_duplicate'),
                                 ('native-auth-refresh-unexpected.ipynb', b'{}', 'recovery_state_path'),
                                 ('recovery-epoch-unbounded.json', encoded({'data': 'x' * 65537}), 'recovery_string_bound')):
            with self.subTest(name=name):
                write(self.state / name, raw)
                with self.assertRaisesRegex(h.RecoveryError, error):
                    self.capture()
                (self.state / name).unlink()

    def test_unrecognized_roots_and_case_aliases_fail_closed(self):
        write(self.state / 'unknown.json', {})
        with self.assertRaisesRegex(ValueError, 'unexpected_root'):
            self.capture()
        (self.state / 'unknown.json').unlink()
        write(self.state / self.native.upper().replace('.CLAIM.JSON', '.claim.json'), {})
        with self.assertRaises(ValueError):
            self.capture()

    def test_historical_claim_and_baseline_event_mutations_rejected(self):
        for name in self.history:
            with self.subTest(name=name):
                write(self.state / name, {'changed': True})
                with self.assertRaisesRegex(ValueError, 'frontier_changed'):
                    self.capture()
                write(self.state / name, self.history[name])

    def test_same_bytes_atomic_replacement_after_capture_is_rejected(self):
        self.code_claim()
        view = self.capture()
        target = self.state / (self.code + '-journal.json')
        temporary = self.base / 'replacement.json'
        temporary.write_bytes(target.read_bytes())
        os.replace(temporary, target)
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'):
            view.root_records(self.state)

    def test_publication_content_change_after_capture_is_rejected(self):
        self.code_claim()
        view = self.capture()
        target = self.state / (self.code + '-journal.json')
        value = json.loads(target.read_bytes())
        value['stage'] = 'version_accepted'
        write(target, value)
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'):
            view.verify_unchanged()

    def test_empty_readback_directory_replacement_and_new_root_are_rejected(self):
        root = self.readback([])
        view = self.capture()
        root.rename(self.base / 'old-readback')
        (root / 'payload').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'):
            view.root_records(self.state)
        view = self.capture()
        write(self.state / ('native-bridge-' + 'e' * 64 + '.claim.json'), {})
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'):
            view.verify_unchanged()

    def test_manifest_same_bytes_replacement_is_rejected(self):
        view = self.capture()
        replacement = self.base / 'replaced-manifest.json'
        replacement.write_bytes(self.manifest_path.read_bytes())
        os.replace(replacement, self.manifest_path)
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'):
            view.verify_unchanged()

    def test_file_hardlinks_and_directory_symlinks_fail_closed(self):
        root = self.readback([])
        outside = self.base / 'outside'
        outside.mkdir()
        (root / 'payload').rmdir()
        (root / 'payload').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'directory_type'):
            self.capture()
        (root / 'payload').unlink()
        (root / 'payload').mkdir()
        path = root / 'payload' / 'NOTICE.txt'
        write(path, self.payload['NOTICE.txt'])
        os.link(path, outside / 'hardlink')
        with self.assertRaisesRegex(ValueError, 'single_link_file'):
            self.capture()

    def test_fifo_and_symlink_root_record_fail_without_opening(self):
        path = self.state / 'notebook-inactive.claim.json'
        os.mkfifo(path)
        with self.assertRaisesRegex(ValueError, 'single_link_file'):
            self.capture()
        path.unlink()
        path.symlink_to(self.manifest_path)
        with self.assertRaisesRegex(ValueError, 'single_link_file'):
            self.capture()

    def test_file_identity_race_during_read_is_rejected(self):
        target = self.state / (self.native + '.claim.json')
        real_stat = p.os.stat
        calls = []
        def racing_stat(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            if path == target.name and kwargs.get('dir_fd') is not None:
                calls.append(path)
                if len(calls) == 3:
                    values = {key: getattr(result, key) for key in
                              ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')}
                    values['st_ino'] += 1
                    return types.SimpleNamespace(**values)
            return result
        with mock.patch.object(p.os, 'stat', side_effect=racing_stat):
            with self.assertRaisesRegex(ValueError, 'file_read_race'):
                self.capture()

    def test_caps_no_auth_execution_no_frozen_source_mutation(self):
        frozen_path = ROOT / 'recovery_epoch.py'
        before = frozen_path.read_bytes()
        with mock.patch.object(os, 'system', side_effect=AssertionError('no process execution')):
            self.capture().verify_unchanged()
        self.assertEqual(frozen_path.read_bytes(), before)
        with mock.patch.object(p, 'ROOT_CAP', 1):
            with self.assertRaisesRegex(ValueError, 'root_count'):
                self.capture()
        with mock.patch.object(p, 'TREE_CAP', 1):
            with self.assertRaisesRegex(ValueError, 'tree_bound'):
                self.capture()

    def test_duplicate_nonfinite_json_and_manifest_integer_types_fail_under_optimization(self):
        self.code_claim()
        target = self.state / (self.code + '.claim.json')
        for raw, message in ((b'{"x":1,"x":2}', 'duplicate_json_key'),
                             (b'{"x":NaN}', 'nonfinite_json')):
            with self.subTest(message=message):
                write(target, raw)
                with self.assertRaisesRegex(ValueError, message):
                    self.capture()
        self.manifest['datasets'][0]['expected_version'] = True
        self.bind_manifest()
        with self.assertRaisesRegex(ValueError, 'manifest_versions'):
            self.capture()


if __name__ == '__main__':
    unittest.main()

"""Synthetic CPU-only fixed-boundary tests; never actual Save or provider evidence."""
import ast
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_multiround_state as rounds
import test_publication_state as f

p, h = f.p, f.h


class ObservedTerminalBoundaryTests(unittest.TestCase):
    make_manifest = rounds.MultiroundStateTests.make_manifest
    make_round = rounds.MultiroundStateTests.make_round

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-observed-boundary-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / 'state'
        self.state.mkdir()
        (self.state / 'events').mkdir()
        self.native = 'native-bridge-' + 'a' * 64 + '-journal.json'
        f.write(self.state / self.native, {'stage': 'UNKNOWN', 'synthetic_fixture': True})
        self.history = []
        previous = 'f' * 64
        for code in range(21, 25):
            root = self.state if code == 21 else self.state / 'publications' / ('code-v' + str(code))
            completed = self.make_round(root, code, previous)
            previous = completed['source']
            self.history.append({'root': str(root), 'manifest': completed['manifest']})
        self.old_root = Path(self.history[-1]['root'])
        self.original = {'cells': [{'source': ['inert ', str(i)]} for i in range(4)],
                         'metadata': {}, 'nbformat': 4, 'nbformat_minor': 5}
        self.saved = copy.deepcopy(self.original)
        for i, cell in enumerate(self.saved['cells']):
            cell.update(id='synthetic-cell-' + str(i), source=''.join(cell['source']))
        self.saved['nbformat_minor'] = 4
        self.install_original()
        self.selected = self.state / 'publications/code-v25'
        self.current = self.make_manifest(25, f.digest(f.encoded(self.saved)))
        self.observation_root = Path(self.current['path']).parent / 'current-predecessor'
        wire = self.read_old('notebook-rlvr004-wire.json')
        metadata = {'id': 138123872, 'ref': p.REF, 'currentVersionNumber': 47,
            'isPrivate': True, 'enableGpu': True, 'enableTpu': False, 'enableInternet': False,
            'kernelType': 'notebook', 'language': 'python', 'machineShape': 'NvidiaRtxPro6000',
            'title': wire['new_title'], 'dockerImage': wire['docker_image'],
            'competitionDataSources': wire['competition_data_sources'], 'kernelDataSources': [],
            'datasetDataSources': [p.DREF], 'modelDataSources': wire['model_data_sources'],
            'synthetic_fixture_only': True}
        dataset = {'id': 12504696, 'ref': p.DREF, 'ownerRef': 'danielwuu',
                   'isPrivate': True, 'currentVersionNumber': 24, 'synthetic_fixture_only': True}
        self.raw_values = {'metadata-before.json': metadata, 'metadata-after.json': copy.deepcopy(metadata),
            'dataset.json': dataset, 'dataset-after.json': copy.deepcopy(dataset),
            'status.json': {'status': 'ERROR', 'failureMessage': ''}, 'saved_source.ipynb': self.saved}
        self.observed = {'format': 'irisx/run008-live-predecessor-observation-v1',
            'code_version': 24, 'notebook_version': 47, 'provider_status': 'ERROR',
            'observed_epoch': 102, 'gpu_unavailable_stop': False, 'native_process_closure_verified': True,
            'runtime_closure_verified': False, 'manual_editor_session_mapping_verified': False,
            'manual_failure_root_cause_verified': False, 'physical_costs_known': False,
            'scientific_result_verified': False,
            'scope': 'Synthetic fixture only; not actual provider evidence.'}
        self.seal()
        # Fixtures replace every fixed evidence hash with its actual bounded bytes.
        # They do not counterfeit real evidence descriptors or alter production pins.
        self.contract = self.fixture_contract()
        patcher = mock.patch.object(p, 'OBSERVED_TERMINAL_V47', self.contract)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read_old(self, name):
        return json.loads((self.old_root / name).read_bytes())

    def install_original(self):
        raw = f.encoded(self.original)
        source = f.write(self.old_root / 'active-finalized.ipynb', raw)
        final = self.read_old('finalization.json')
        final['documents']['active-finalized.ipynb'] = source
        final['finalized_sha256'] = source['sha256']
        final['predispatch_epoch'] = final['dispatch_epoch'] = 100
        finalized = f.write(self.old_root / 'finalization.json', final)
        wire = self.read_old('notebook-rlvr004-wire.json')
        wire.update(text=raw.decode(), new_title='Synthetic inert v47', language='python', kernel_type='notebook',
            model_data_sources=['qwen-lm/qwen-3/transformers/14b/1'],
            competition_data_sources=['arc-prize-2026-arc-agi-3'], kernel_data_sources=[],
            is_private=True, enable_gpu=True, enable_tpu=False, enable_internet=False,
            docker_image='synthetic-pinned-image', machine_shape='NvidiaRtxPro6000')
        wire_desc = f.write(self.old_root / 'notebook-rlvr004-wire.json', wire)
        journal = self.read_old('notebook-rlvr004-journal.json')
        journal.update(stage='save_intent', save_calls=1, source_sha256=source['sha256'],
            wire_sha256=wire_desc['sha256'], finalization_sha256=finalized['sha256'],
            dispatch_epoch=101, predispatch_epoch=100)
        f.write(self.old_root / 'notebook-rlvr004-journal.json', journal)
        (self.old_root / 'notebook-rlvr004-receipt.json').unlink()
        (self.old_root / 'notebook-rlvr004-saved.ipynb').unlink()

    def seal(self):
        roles = {'saved_source': ('saved_source.ipynb', 'saved_source_sha256'),
            'notebook_before': ('metadata-before.json', 'metadata_before_sha256'),
            'notebook_after': ('metadata-after.json', 'metadata_after_sha256'),
            'notebook_status': ('status.json', 'status_sha256'),
            'dataset_before': ('dataset.json', 'dataset_metadata_sha256'),
            'dataset_after': ('dataset-after.json', 'dataset_after_sha256')}
        descriptors = {name: f.write(self.observation_root / name, value) for name, value in self.raw_values.items()}
        for name, key in roles.values():
            self.observed[key] = descriptors[name]['sha256']
        descriptors['publisher-observation.json'] = f.write(self.observation_root / 'publisher-observation.json', self.observed)
        self.sealed = {**self.observed, 'format': 'irisx/run008-native-current-predecessor-observation-v1',
            'closed_files': {name: {key: desc[key] for key in ('bytes', 'sha256')} for name, desc in descriptors.items()},
            'evidence': {role: {**descriptors[name], 'path': name} for role, (name, _) in roles.items()},
            'original_observation_sha256': descriptors['publisher-observation.json']['sha256'],
            'provider_calls_by_sealer': 0,
            'scope': 'Exact existing official bracket; local sealing is not a new provider observation or runtime/scientific evidence.'}
        self.sealed['evidence']['original_observation'] = {
            **descriptors['publisher-observation.json'], 'path': 'publisher-observation.json'}
        self.bind_sealed()

    def bind_sealed(self):
        desc = f.write(self.observation_root / 'OBSERVATION.json', self.sealed)
        value = json.loads(Path(self.current['path']).read_bytes())
        value['current_predecessor_observation'] = {**desc, 'path': 'current-predecessor/OBSERVATION.json'}
        self.current = f.write(Path(self.current['path']), value)

    def fixture_contract(self):
        def desc(path):
            raw = path.read_bytes()
            return (len(raw), f.digest(raw))
        return {'manifest': (self.history[-1]['manifest']['bytes'], self.history[-1]['manifest']['sha256']),
            'admitting_manifest_sha256': self.current['sha256'],
            'sealed_sha256': desc(self.observation_root / 'OBSERVATION.json')[1],
            'original_files': {name: desc(self.old_root / name) for name in
                ('notebook-rlvr004.claim.json', 'notebook-rlvr004-journal.json', 'notebook-rlvr004-wire.json',
                 'finalization.json', 'active-finalized.ipynb')},
            'raw_files': {name: desc(self.observation_root / name) for name in
                ('publisher-observation.json', *self.raw_values)}}

    def reseal_fixture(self):
        self.seal()
        self.contract.update(self.fixture_contract())

    def capture(self, code=25, descriptor=None, history=None):
        return p.capture(self.state, self.current if descriptor is None else descriptor, rounds.versions(code), h,
            publication_root=self.selected.with_name('code-v' + str(code)),
            publication_history=self.history if history is None else history)

    def state_bytes(self):
        return {str(path.relative_to(self.state)): path.read_bytes() for path in self.state.rglob('*') if path.is_file()}

    def test_exact_bounded_fixture_preserves_unknown_save_and_all_old_state(self):
        before = self.state_bytes()
        with mock.patch.object(os, 'system', side_effect=AssertionError('no process execution')):
            view = self.capture()
            view.verify_unchanged()
            self.assertEqual(set(view.root_records(self.state)), {self.native})
        self.assertEqual(before, self.state_bytes())
        self.assertFalse((self.old_root / 'notebook-rlvr004-receipt.json').exists())
        self.assertFalse((self.old_root / 'notebook-rlvr004-saved.ipynb').exists())
        journal = self.read_old('notebook-rlvr004-journal.json')
        self.assertEqual(journal['stage'], 'save_intent')
        self.assertNotIn('save_accepted', journal)
        self.assertNotEqual(p._normalized_notebook(f.encoded(self.original)), p._normalized_notebook(f.encoded(self.saved)))
        self.assertTrue(any('publisher-observation.json' in name for name in view._fingerprint))
        source = ast.parse((f.ROOT / 'operator_common.py').read_text())
        normalizer = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'source_normalize')
        namespace = {'json': json}
        exec(compile(ast.Module(body=[normalizer], type_ignores=[]), '<unchanged-pure-normalizer>', 'exec'), namespace)
        self.assertNotEqual(namespace['source_normalize'](f.encoded(self.original)),
                            namespace['source_normalize'](f.encoded(self.saved)))
        result = self.resolve_boundary()
        self.assertEqual(result['source_sha256'], f.digest(f.encoded(self.saved)))
        self.assertNotEqual(result['source_sha256'], f.digest(f.encoded(self.original)))
        self.assertEqual(result['provenance'], 'fixed-v47-observed-terminal-save-unknown')

    def resolve_boundary(self, adjacent=None):
        files = {path.name: path.read_bytes() for path in self.old_root.iterdir() if path.is_file()}
        descriptor = self.history[-1]['manifest']
        manifest = json.loads(Path(descriptor['path']).read_bytes())
        parsed = p._publication_records(files, self.old_root, descriptor, rounds.versions(24), manifest)
        result = p._resolved_publication(files, parsed, self.old_root, rounds.versions(24), manifest,
                                        descriptor, self.current if adjacent is None else adjacent)
        self.assertNotIn('notebook-rlvr004-receipt.json', parsed)
        return result

    def test_valid_receipt_without_saved_bytes_still_uses_strict_receipt_path(self):
        journal = self.read_old('notebook-rlvr004-journal.json')
        receipt = {'role': 'rlvr004', 'reference': p.REF, 'kernel_id': 138123872, 'version': 47,
            'manifest_sha256': self.history[-1]['manifest']['sha256'],
            'launch_journal_sha256': self.contract['original_files']['notebook-rlvr004-journal.json'][1],
            'normalized_source_exact': True, 'submitted_source_sha256': journal['source_sha256'],
            'finalization_sha256': journal['finalization_sha256'],
            'saved_source': {'path': str(self.old_root / 'notebook-rlvr004-saved.ipynb'),
                            'bytes': len(f.encoded(self.saved)), 'sha256': f.digest(f.encoded(self.saved))}}
        f.write(self.old_root / 'notebook-rlvr004-receipt.json', receipt)
        with self.assertRaisesRegex(ValueError, 'previous_notebook_unresolved'): self.capture()
        f.write(self.old_root / 'notebook-rlvr004-saved.ipynb', self.saved)
        with self.assertRaisesRegex(ValueError, 'previous_wire_source_binding'): self.capture()

    def test_journal_unknown_disposition_and_wire_finalization_bindings_remain_strict(self):
        path = self.old_root / 'notebook-rlvr004-journal.json'
        original = self.read_old(path.name)
        cases = [('stage', 'save_accepted'), ('save_calls', 0), ('save_calls', True),
            ('save_accepted', True), ('response_version', 47), ('source_sha256', '0' * 64),
            ('wire_sha256', '0' * 64), ('finalization_sha256', '0' * 64),
            ('dispatch_epoch', 0), ('dispatch_epoch', True), ('dispatch_epoch', '101'), ('dispatch_epoch', 103)]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                desc = f.write(path, {**original, key: value})
                self.contract['original_files'][path.name] = (desc['bytes'], desc['sha256'])
                with self.assertRaises(ValueError): self.capture()

    def test_wrong_adjacent_allocation_rejected_even_with_synthetic_hash_rebinding(self):
        wrong = self.make_manifest(26, f.digest(f.encoded(self.saved)))
        self.contract['admitting_manifest_sha256'] = wrong['sha256']
        with self.assertRaisesRegex(ValueError, 'observed_admitting_versions'):
            self.resolve_boundary(wrong)

    def test_historical_manifest_byte_and_same_byte_identity_changes_are_detected(self):
        path = Path(self.history[-1]['manifest']['path'])
        view = self.capture()
        replacement = self.base / 'historical-replacement'
        replacement.write_bytes(path.read_bytes())
        os.replace(replacement, path)
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'): view.verify_unchanged()
        view = self.capture()
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'descriptor_changed'): view.verify_unchanged()

    def test_real_disposition_never_admits_synthetic_evidence(self):
        original = f.load('real_fixed_boundary_contract', f.ROOT / 'publication_state.py')
        with mock.patch.object(p, 'OBSERVED_TERMINAL_V47', original.OBSERVED_TERMINAL_V47):
            with self.assertRaisesRegex(ValueError, 'observed_boundary_disposition'):
                self.capture()

    def test_two_successor_rounds_reuse_same_adjacent_admitting_manifest(self):
        self.capture().verify_unchanged()
        admitting = self.current
        # Complete code25 under that exact existing admitting manifest. The reusable
        # fixture's generator first emits its own manifest, then we rebind the
        # routine records to the preserved admitting bytes.
        admitted_raw = Path(admitting['path']).read_bytes()
        second = self.make_round(self.selected, 25, f.digest(f.encoded(self.saved)))
        generated_digest = second['manifest']['sha256']
        f.write(Path(admitting['path']), admitted_raw)
        for path in self.selected.glob('*.json'):
            value = json.loads(path.read_bytes())
            changed = False
            for key in ('manifest_sha256', 'publication_manifest_sha256'):
                if value.get(key) == generated_digest:
                    value[key] = admitting['sha256']; changed = True
            if changed: f.write(path, value)
        # Recompute graph links after rebinding routine synthetic receipts.
        for stem in ('dataset-code-v25', 'notebook-inactive', 'notebook-rlvr004'):
            journal = json.loads((self.selected / (stem + '-journal.json')).read_bytes())
            journal['claim_sha256'] = f.digest((self.selected / (stem + '.claim.json')).read_bytes())
            if stem == 'notebook-rlvr004':
                journal['finalization_sha256'] = f.digest((self.selected / 'finalization.json').read_bytes())
            jd = f.write(self.selected / (stem + '-journal.json'), journal)
            receipt = json.loads((self.selected / (stem + '-receipt.json')).read_bytes())
            receipt['journal_sha256' if stem.startswith('dataset') else 'launch_journal_sha256'] = jd['sha256']
            if stem.startswith('dataset'): receipt['claim_sha256'] = journal['claim_sha256']
            if stem == 'notebook-rlvr004': receipt['finalization_sha256'] = journal['finalization_sha256']
            f.write(self.selected / (stem + '-receipt.json'), receipt)
        active = json.loads((self.selected / 'active-readback.claim.json').read_bytes())
        active['launch_claim_sha256'] = f.digest((self.selected / 'notebook-rlvr004.claim.json').read_bytes())
        f.write(self.selected / 'active-readback.claim.json', active)
        third = self.make_manifest(26, second['source'])
        history = self.history + [{'root': str(self.selected), 'manifest': admitting}]
        before = self.state_bytes()
        self.capture(26, third, history).verify_unchanged()
        self.assertEqual(before, self.state_bytes())
        self.assertEqual(Path(admitting['path']).read_bytes(), admitted_raw)
        wrong = json.loads(admitted_raw)
        wrong['synthetic_wrong_adjacent'] = True
        history[-1]['manifest'] = f.write(self.base / 'wrong-adjacent.json', wrong)
        with self.assertRaisesRegex(ValueError, 'observed_boundary_disposition'):
            self.capture(26, third, history)

    def test_missing_or_existing_conflicting_receipt_and_saved_never_fall_back(self):
        for name, value in (('notebook-rlvr004-receipt.json', {}),
                            ('notebook-rlvr004-receipt.json', b'{malformed'),
                            ('notebook-rlvr004-saved.ipynb', self.saved)):
            with self.subTest(name=name, value=value):
                path = self.old_root / name
                f.write(path, value)
                with self.assertRaises(ValueError): self.capture()
                path.unlink()
        (self.old_root / 'notebook-rlvr004-journal.json').unlink()
        with self.assertRaises(ValueError): self.capture()

    def test_original_journal_finalization_wire_and_claim_tampering_fail(self):
        for name in self.contract['original_files']:
            with self.subTest(name=name):
                path = self.old_root / name
                before = path.read_bytes()
                path.write_bytes(before + b' ')
                with self.assertRaises(ValueError): self.capture()
                path.write_bytes(before)

    def test_all_raw_proofs_and_sealed_observation_are_rehashed(self):
        for path in self.observation_root.iterdir():
            with self.subTest(name=path.name):
                before = path.read_bytes()
                path.write_bytes(before + b' ')
                with self.assertRaises(ValueError): self.capture()
                path.write_bytes(before)

    def test_hash_bound_source_cannot_be_replaced_even_if_new_manifest_matches(self):
        self.raw_values['saved_source.ipynb'] = {'cells': [], 'nbformat': 4}
        self.seal()
        with self.assertRaises(ValueError): self.capture()

    def test_wrong_observed_identity_native_closure_or_claims_rejected_semantically(self):
        cases = [('code_version', 23), ('code_version', True), ('notebook_version', 48),
            ('provider_status', 'RUNNING'), ('provider_status', 'COMPLETE'),
            ('native_process_closure_verified', False), ('gpu_unavailable_stop', True),
            ('scientific_result_verified', True), ('runtime_closure_verified', True)]
        original = copy.deepcopy(self.observed)
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.observed = {**original, key: value}
                self.reseal_fixture()
                with self.assertRaisesRegex(ValueError, 'observed_terminal_identity'): self.capture()

    def test_wrong_raw_status_rejected_even_when_resealed(self):
        self.raw_values['status.json']['status'] = 'COMPLETE'
        self.reseal_fixture()
        with self.assertRaisesRegex(ValueError, 'observed_raw_status'): self.capture()

    def test_all_observed_settings_and_mounts_must_match_original_wire(self):
        original = copy.deepcopy(self.raw_values['metadata-before.json'])
        cases = [('isPrivate', False), ('enableGpu', False), ('enableTpu', True), ('enableInternet', True),
            ('kernelType', 'script'), ('language', 'r'), ('machineShape', 'None'),
            ('dockerImage', 'different'), ('title', 'different'), ('datasetDataSources', []),
            ('modelDataSources', []), ('competitionDataSources', []), ('kernelDataSources', ['other']),
            ('id', 138123873), ('currentVersionNumber', 46), ('ref', 'other/notebook')]
        for key, value in cases:
            with self.subTest(key=key):
                self.raw_values['metadata-before.json'] = {**original, key: value}
                self.raw_values['metadata-after.json'] = {**original, key: value}
                self.reseal_fixture()
                with self.assertRaises(ValueError): self.capture()

    def test_full_metadata_and_dataset_brackets_not_only_selected_fields(self):
        for name in ('metadata-after.json', 'dataset-after.json'):
            with self.subTest(name=name):
                self.raw_values[name]['unselected_field'] = 'changed'
                self.reseal_fixture()
                with self.assertRaisesRegex(ValueError, 'observed_bracket_changed'): self.capture()
                del self.raw_values[name]['unselected_field']

    def test_dataset_identity_private_owner_and_numeric_version_are_required(self):
        original = copy.deepcopy(self.raw_values['dataset.json'])
        for key, value in [('id', 1), ('ref', 'other/dataset'), ('ownerRef', 'other'),
                           ('isPrivate', False), ('currentVersionNumber', 25), ('id', True)]:
            with self.subTest(key=key):
                self.raw_values['dataset.json'] = {**original, key: value}
                self.raw_values['dataset-after.json'] = {**original, key: value}
                self.reseal_fixture()
                with self.assertRaisesRegex(ValueError, 'observed_dataset_identity'): self.capture()

    def test_observation_must_be_finite_and_strictly_after_original_dispatch(self):
        for value in (0, 100, 101, True, '102'):
            with self.subTest(value=value):
                self.observed['observed_epoch'] = value
                self.reseal_fixture()
                with self.assertRaisesRegex(ValueError, 'observed_chronology'): self.capture()
        for value in (float('nan'), float('inf')):
            with self.subTest(value=value):
                self.observed['observed_epoch'] = value
                self.reseal_fixture()
                with self.assertRaisesRegex(ValueError, 'nonfinite_json'): self.capture()

    def test_new_manifest_predecessor_source_cannot_be_old_submitted_hash(self):
        value = json.loads(Path(self.current['path']).read_bytes())
        value['notebooks'][0]['predecessor_source_sha256'] = f.digest(f.encoded(self.original))
        self.current = f.write(Path(self.current['path']), value)
        self.contract['admitting_manifest_sha256'] = self.current['sha256']
        with self.assertRaisesRegex(ValueError, 'predecessor_source'): self.capture()

    def test_wrong_disposition_manifest_and_sealed_hashes_rejected(self):
        for key in ('manifest', 'admitting_manifest_sha256', 'sealed_sha256'):
            with self.subTest(key=key):
                old = self.contract[key]
                self.contract[key] = (old[0], '0' * 64) if key == 'manifest' else '0' * 64
                with self.assertRaises(ValueError): self.capture()
                self.contract[key] = old

    def test_seal_must_preserve_exact_raw_observation_inventory_and_role_links(self):
        original = copy.deepcopy(self.sealed)
        for part in ('closed_files', 'evidence'):
            with self.subTest(part=part):
                self.sealed = copy.deepcopy(original)
                self.sealed[part].pop(next(iter(self.sealed[part])))
                self.bind_sealed()
                self.contract.update(self.fixture_contract())
                with self.assertRaisesRegex(ValueError, 'observed_seal_binding'): self.capture()
        self.sealed = copy.deepcopy(original)
        self.sealed['native_process_closure_verified'] = False
        self.bind_sealed()
        self.contract.update(self.fixture_contract())
        with self.assertRaisesRegex(ValueError, 'observed_seal_binding'): self.capture()

    def test_extra_missing_symlink_and_hardlink_proof_files_fail_closed(self):
        extra = self.observation_root / 'extra.json'
        f.write(extra, {})
        with self.assertRaisesRegex(ValueError, 'observed_closed_directory'): self.capture()
        extra.unlink()
        path = self.observation_root / 'status.json'
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'observed_closed_directory'): self.capture()
        outside = self.base / 'outside.json'
        f.write(outside, raw)
        path.symlink_to(outside)
        with self.assertRaises(ValueError): self.capture()
        path.unlink()
        os.link(outside, path)
        with self.assertRaisesRegex(ValueError, 'single_link_file'): self.capture()

    def test_external_same_bytes_replacement_is_detected_on_every_callback(self):
        for path in (Path(self.current['path']), *self.observation_root.iterdir()):
            with self.subTest(name=path.name):
                view = self.capture()
                replacement = self.base / 'replacement'
                replacement.write_bytes(path.read_bytes())
                os.replace(replacement, path)
                with self.assertRaisesRegex(ValueError, 'changed_during_observation'): view.verify_unchanged()

    def test_external_directory_identity_and_later_proof_changes_are_detected(self):
        view = self.capture()
        old = self.base / 'old-observation'
        self.observation_root.rename(old)
        self.observation_root.mkdir()
        for path in old.iterdir():
            os.rename(path, self.observation_root / path.name)
        with self.assertRaisesRegex(ValueError, 'changed_during_observation'): view.root_records(self.state)
        view = self.capture()
        path = self.observation_root / 'status.json'
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(ValueError): view.verify_unchanged()

    def test_code_inactive_retention_readback_and_native_gates_remain(self):
        for name in ('dataset-code-v24-receipt.json', 'notebook-inactive-receipt.json',
                     'active-readback.claim.json', 'historical-code-v8-inventory.json',
                     'code-v24-readback/payload/NOTICE.txt'):
            with self.subTest(name=name):
                path = self.old_root / name
                before = path.read_bytes()
                path.unlink()
                with self.assertRaises(ValueError): self.capture()
                f.write(path, before)
        # Native records still reach the untouched original parser; this boundary
        # is not authority to close the original UNKNOWN native process.
        f.write(self.state / self.native, b'{"same":1,"same":2}')
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.capture()


if __name__ == '__main__':
    unittest.main()

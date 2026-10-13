"""CPU-only negative/helper tests for exact numeric19 mount acceptance.

All synthetic receipts/layouts/results are labelled UNIT-ONLY and exercise pure
helper gates or failing control flow. No test creates a production mount receipt.
Actual candidate tests authenticate whole files only and never open gold ZIP
members. No provider, credentials, model, GPU, or scorer is invoked. Test writes
stay under .irisx and do not modify the candidate or frozen helper/guard.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import zipfile

from tools.arc_qwen_rlvr004_20261013.preparation_successor import accept_numeric_mount as mount

REPOSITORY = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SYNTHETIC = b'SYNTHETIC UNIT-ONLY; NOT A PROVIDER OR PRODUCTION RECEIPT\n'
OFFLINE = {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0', 'HF_HUB_OFFLINE': '1',
           'HF_DATASETS_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'WANDB_MODE': 'offline'}
SCRATCH = None
PATCHES = []
OLD_BYTECODE = None


def setUpModule():
    global SCRATCH, OLD_BYTECODE
    OLD_BYTECODE = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    parent = mount.ordinary(REPOSITORY / '.irisx')
    parent.mkdir(exist_ok=True)
    SCRATCH = tempfile.TemporaryDirectory(dir=parent, prefix='numeric-mount-unit-tests-')
    PATCHES.extend((patch.dict(os.environ, {**OFFLINE, 'TMPDIR': SCRATCH.name}),
                   patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden'))))
    for item in PATCHES:
        item.start()


def tearDownModule():
    for item in reversed(PATCHES):
        item.stop()
    PATCHES.clear()
    if SCRATCH is not None:
        SCRATCH.cleanup()
    if OLD_BYTECODE is not None:
        sys.dont_write_bytecode = OLD_BYTECODE


class ScratchCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=SCRATCH.name, prefix='unit-only-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def put(self, name, raw=SYNTHETIC):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def synthetic_receipt(self):
        """Pure helper input only; never passed through successful accept()."""
        code = self.root / 'UNIT-ONLY-code'
        self.put('UNIT-ONLY-code/nested/UNIT-ONLY.txt')
        rows = {'nested/UNIT-ONLY.txt': mount.v.desc(SYNTHETIC)}
        listed = [{'path': name, **row} for name, row in rows.items()]
        manifest = {'synthetic_unit_fixture_only': True,
                    'datasets': [{'expected_readback_layouts': {'UNIT-ONLY-layout': listed}}]}
        metadata = {'id': 12504696, 'version': 19, 'private': True,
                    'owner_ref': 'danielwuu', 'ref': mount.REFERENCE,
                    'synthetic_unit_fixture_only': True}
        receipt = {'status': 'VERIFIED_CODE_V19', 'dataset_id': 12504696, 'version': 19,
                   'is_private': True, 'exact_byte_roundtrip': True,
                   'manifest_sha256': mount.MANIFEST_SHA, 'publication_manifest_sha256': mount.MANIFEST_SHA,
                   'payload_root': str(code), 'before': metadata, 'after': copy.deepcopy(metadata),
                   'layout': 'UNIT-ONLY-layout', 'files': 1, 'bytes': len(SYNTHETIC),
                   'inventory_sha256': mount.sha(mount.v.canonical(rows)),
                   'readback_method': 'numeric_per_file', 'provider_archive_verified': False, 'archive_sha256': None,
                   'synthetic_unit_fixture_only': True}
        return manifest, receipt, code, rows

    def helper_fixture(self):
        return {'format': 'irisx/rlvr-actual-local-code-mount-acceptance-v1',
                'status': 'PASS', 'synthetic_unit_fixture_only': True,
                'model_or_GPU_calls': 0, 'public_evaluator_body_reads': 0, 'provider_calls': 0,
                'production_execution_claim': False, 'provider_provenance_verified_by_this_helper': False,
                'external_numeric_download_receipt_required': True,
                'source_acceptance': {'format': 'irisx/rlvr-no-model-source-acceptance-v1', 'source_sha256': mount.SOURCE_SHA, 'source_archive_sha256': mount.ARCHIVE_SHA,
                    'manifest_sha256': mount.CODE_MANIFEST_SHA, 'source_members': 259,
                    'exact_archive_bytes_available': True, 'model_imported': False, 'weights_read': False,
                    'evaluator_body_read': False, 'provider_mount_verified': False},
                'isolated_import': {'source_sha256': mount.SOURCE_SHA, 'source_only': True,
                                    'model_libraries_imported': False}}

    def accept_arguments(self):
        return {'candidate_root': self.root / 'missing-candidate', 'code_root': self.root / 'missing-code',
                'code_receipt_path': self.root / 'missing-receipt.json', 'code_receipt_sha': '0' * 64,
                'output_root': self.root / 'uncreated-acceptance'}


class ClosedByteTests(ScratchCase):
    def test_exact_unit_tree_roundtrip_and_explicit_sidecar(self):
        self.put('nested/UNIT-ONLY.txt')
        self.put('inventory.json', b'{}\n')
        self.assertEqual(mount.closed(self.root, {'nested/UNIT-ONLY.txt': mount.v.desc(SYNTHETIC)},
                                     extra=('inventory.json',)), {'nested/UNIT-ONLY.txt': SYNTHETIC})

    def test_unknown_missing_changed_and_wrong_size_members_reject(self):
        path = self.put('UNIT-ONLY.txt')
        rows = {path.name: mount.v.desc(SYNTHETIC)}
        extra = self.put('extra.txt')
        with self.assertRaisesRegex(ValueError, 'closed member set differs'):
            mount.closed(self.root, rows)
        extra.unlink()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'closed member set differs'):
            mount.closed(self.root, rows)
        path.write_bytes(SYNTHETIC + b'changed')
        with self.assertRaisesRegex(ValueError, 'exact input digest'):
            mount.closed(self.root, rows)
        path.write_bytes(SYNTHETIC)
        rows[path.name]['bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'closed member byte count'):
            mount.closed(self.root, rows)

    def test_non_directory_and_invalid_descriptor_reject(self):
        path = self.put('UNIT-ONLY.txt')
        with self.assertRaisesRegex(ValueError, 'closed root required'):
            mount.closed(path, {path.name: mount.v.desc(SYNTHETIC)})
        good = mount.v.desc(SYNTHETIC)
        for row in ({**good, 'bytes': True}, {**good, 'bytes': -1}, {**good, 'bytes': mount.v.CAP + 1},
                    {**good, 'sha256': 'A' * 64}, {**good, 'extra': 1}):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, 'descriptor'):
                mount.closed(self.root, {path.name: row})
        for name in ('../escape', '/absolute', 'a//b', 'a\\b', 'a:b', 'a\nb'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'relative path'):
                mount.closed(self.root, {name: good})

    def test_total_size_rejects_before_any_body_read(self):
        rows = {f'UNIT-ONLY-{i}': {'bytes': mount.v.CAP, 'sha256': '0' * 64} for i in range(5)}
        with patch.object(mount, 'pinned', side_effect=AssertionError('oversized tree body read')):
            with self.assertRaisesRegex(ValueError, 'closed total bound'):
                mount.closed(self.root, rows)

    def test_symlink_hardlink_fifo_and_linked_ancestor_reject(self):
        target = self.put('UNIT-ONLY.txt')
        rows = {target.name: mount.v.desc(SYNTHETIC)}
        bad = self.root / 'bad'
        for kind in ('symlink', 'hardlink', 'fifo'):
            if kind == 'symlink':
                bad.symlink_to(target)
            elif kind == 'hardlink':
                os.link(target, bad)
            else:
                os.mkfifo(bad)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                mount.closed(self.root, rows)
            bad.unlink()
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ordinary path'):
            mount.closed(alias, rows)

    def test_digest_schema_rejects_before_input_read(self):
        with patch.object(mount, 'read', side_effect=AssertionError('read before SHA schema')):
            for digest in (None, b'0' * 64, '', '0' * 63, '0' * 65, 'A' * 64, 'g' * 64):
                with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, 'SHA256 required'):
                    mount.pinned(self.root / 'absent', digest)

    def test_put_is_exclusive_private_roundtripped_and_not_a_proof(self):
        path = self.root / 'UNIT-ONLY-output.json'
        value = {'synthetic_unit_fixture_only': True, 'purpose': 'exclusive writer test'}
        result = mount.put(path, value)
        self.assertEqual(result, {'path': str(path), **mount.v.desc(mount.encoded(value))})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            mount.put(path, b'overwrite')
        self.assertEqual(path.read_bytes(), mount.encoded(value))
        self.assertFalse((self.root / 'MOUNT-RECEIPT.json').exists())


class ReceiptGateTests(ScratchCase):
    def test_unit_only_receipt_helper_checks_local_exact_tree(self):
        manifest, receipt, code, _ = self.synthetic_receipt()
        with patch.object(zipfile.ZipFile, 'read', side_effect=AssertionError('ZIP member read')):
            self.assertEqual(mount.receipt_inputs(manifest, mount.encoded(receipt), code), receipt)
        self.assertFalse((self.root / 'MOUNT-RECEIPT.json').exists())

    def test_wrong_status_dataset_version_privacy_and_roundtrip_reject(self):
        manifest, original, code, _ = self.synthetic_receipt()
        changes = (('status', 'VERSION_ACCEPTED_READBACK_REQUIRED'), ('status', 'VERIFIED_CODE_V18'),
                   ('dataset_id', 1), ('version', 18), ('version', 20), ('version', '19'),
                   ('version', 19.0), ('is_private', False), ('is_private', 1),
                   ('exact_byte_roundtrip', False), ('exact_byte_roundtrip', 1))
        for key, value in changes:
            receipt = copy.deepcopy(original)
            receipt[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'authentic numeric19'):
                mount.receipt_inputs(manifest, mount.encoded(receipt), code)

    def test_both_publication_hashes_are_required(self):
        manifest, original, code, _ = self.synthetic_receipt()
        for key in ('manifest_sha256', 'publication_manifest_sha256'):
            for value in ('0' * 64, None):
                receipt = copy.deepcopy(original)
                receipt[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'publication binding'):
                    mount.receipt_inputs(manifest, mount.encoded(receipt), code)

    def test_official_transport_method_and_archive_fields_must_agree(self):
        manifest, original, code, _ = self.synthetic_receipt()
        for method in (None, '', 'cached', 'numeric18', 19):
            receipt = copy.deepcopy(original)
            receipt['readback_method'] = method
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, 'official numeric readback method'):
                mount.receipt_inputs(manifest, mount.encoded(receipt), code)
        for verified, digest in ((True, None), (0, None), (False, '0' * 64), (None, None)):
            receipt = copy.deepcopy(original)
            receipt.update(provider_archive_verified=verified, archive_sha256=digest)
            with self.subTest(verified=verified, digest=digest), self.assertRaisesRegex(ValueError, 'per-file transport provenance'):
                mount.receipt_inputs(manifest, mount.encoded(receipt), code)
        for verified, digest in ((False, '0' * 64), (1, '0' * 64), (True, None),
                                 (True, 'A' * 64), (True, '0' * 63), (True, 1)):
            receipt = copy.deepcopy(original)
            receipt.update(readback_method='numeric_whole_archive', provider_archive_verified=verified, archive_sha256=digest)
            with self.subTest(verified=verified, digest=digest), self.assertRaisesRegex(ValueError, 'whole archive transport provenance'):
                mount.receipt_inputs(manifest, mount.encoded(receipt), code)
        # Unit-only schema control; no archive or production output is created.
        receipt = copy.deepcopy(original)
        receipt.update(readback_method='numeric_whole_archive', provider_archive_verified=True, archive_sha256='a' * 64)
        self.assertEqual(mount.receipt_inputs(manifest, mount.encoded(receipt), code), receipt)
        self.assertFalse((self.root / 'MOUNT-RECEIPT.json').exists())

    def test_actual_absolute_root_is_bound_before_tree_access(self):
        manifest, original, code, _ = self.synthetic_receipt()
        for value in ('UNIT-ONLY-code', str(code) + '/', str(self.root / 'other')):
            receipt = copy.deepcopy(original)
            receipt['payload_root'] = value
            with self.subTest(value=value), patch.object(mount, 'closed', side_effect=AssertionError('wrong root read')):
                with self.assertRaisesRegex(ValueError, 'actual downloaded root binding'):
                    mount.receipt_inputs(manifest, mount.encoded(receipt), code)

    def test_metadata_bracket_and_owner_version_identity_reject_mutations(self):
        manifest, original, code, _ = self.synthetic_receipt()
        for key, value in (('id', 1), ('version', 18), ('private', False), ('private', 1),
                           ('owner_ref', 'other'), ('ref', 'other/reference')):
            receipt = copy.deepcopy(original)
            receipt['before'][key] = value
            receipt['after'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'metadata bracket'):
                mount.receipt_inputs(manifest, mount.encoded(receipt), code)
        receipt = copy.deepcopy(original)
        receipt['after']['version'] = 20
        with self.assertRaisesRegex(ValueError, 'metadata bracket'):
            mount.receipt_inputs(manifest, mount.encoded(receipt), code)
        for value in (None, [], 'metadata unavailable'):
            receipt = copy.deepcopy(original)
            receipt['before'] = receipt['after'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'metadata bracket'):
                mount.receipt_inputs(manifest, mount.encoded(receipt), code)

    def test_unknown_or_duplicate_layout_rejects(self):
        manifest, receipt, code, _ = self.synthetic_receipt()
        changed = copy.deepcopy(receipt)
        changed['layout'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'reviewed readback layout'):
            mount.receipt_inputs(manifest, mount.encoded(changed), code)
        listed = manifest['datasets'][0]['expected_readback_layouts']['UNIT-ONLY-layout']
        listed.append(copy.deepcopy(listed[0]))
        with self.assertRaisesRegex(ValueError, 'no duplicate layout paths'):
            mount.receipt_inputs(manifest, mount.encoded(receipt), code)

    def test_inventory_file_count_byte_count_hash_are_exact(self):
        manifest, original, code, _ = self.synthetic_receipt()
        for key, value in (('files', 0), ('files', True), ('files', 1.0), ('bytes', 0),
                           ('bytes', float(len(SYNTHETIC))), ('inventory_sha256', '0' * 64)):
            receipt = copy.deepcopy(original)
            receipt[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'numeric inventory binding'):
                mount.receipt_inputs(manifest, mount.encoded(receipt), code)

    def test_receipt_cannot_stand_in_for_missing_changed_or_extra_content(self):
        manifest, receipt, code, _ = self.synthetic_receipt()
        path = code / 'nested/UNIT-ONLY.txt'
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'closed member set differs'):
            mount.receipt_inputs(manifest, mount.encoded(receipt), code)
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'exact input digest'):
            mount.receipt_inputs(manifest, mount.encoded(receipt), code)
        path.write_bytes(SYNTHETIC)
        (code / 'extra').write_bytes(SYNTHETIC)
        with self.assertRaisesRegex(ValueError, 'closed member set differs'):
            mount.receipt_inputs(manifest, mount.encoded(receipt), code)

    def test_receipt_rejects_duplicate_keys_and_nonfinite_before_tree(self):
        manifest, _, code, _ = self.synthetic_receipt()
        for raw in (b'{"status":"x","status":"y"}', b'{"x":NaN}', b'{"x":1e9999}'):
            with self.subTest(raw=raw), patch.object(mount, 'closed', side_effect=AssertionError('invalid JSON read tree')):
                with self.assertRaises(ValueError):
                    mount.receipt_inputs(manifest, raw, code)


class HelperAndClosureTests(ScratchCase):
    def test_unit_helper_schema_emits_no_proof(self):
        mount.check_helper(self.helper_fixture())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_helper_top_level_success_and_nonexecution_flags_required(self):
        original = self.helper_fixture()
        for key, value in (('format', 'UNIT-ONLY-wrong'), ('status', 'FAIL'), ('model_or_GPU_calls', 1),
                           ('model_or_GPU_calls', False), ('public_evaluator_body_reads', 0.0),
                           ('external_numeric_download_receipt_required', False), ('public_evaluator_body_reads', 1),
                           ('provider_calls', 1), ('production_execution_claim', True),
                           ('production_execution_claim', 0), ('provider_provenance_verified_by_this_helper', True)):
            result = copy.deepcopy(original)
            result[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'frozen no-model helper result'):
                mount.check_helper(result)

    def test_all_source_identity_fields_and_complete259_are_required(self):
        original = self.helper_fixture()
        for key, value in (('format', 'UNIT-ONLY-wrong'), ('source_sha256', '0' * 64), ('source_archive_sha256', '0' * 64),
                           ('manifest_sha256', '0' * 64), ('source_members', 258), ('source_members', 259.0),
                           ('exact_archive_bytes_available', False), ('exact_archive_bytes_available', 1)):
            result = copy.deepcopy(original)
            result['source_acceptance'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'complete source259'):
                mount.check_helper(result)

    def test_model_weight_evaluator_and_provider_claims_reject(self):
        original = self.helper_fixture()
        for key in ('model_imported', 'weights_read', 'evaluator_body_read', 'provider_mount_verified'):
            for value in (True, 0, None):
                result = copy.deepcopy(original)
                result['source_acceptance'][key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'no model or evaluator'):
                    mount.check_helper(result)

    def test_isolated_import_scope_identity_and_model_flags_reject(self):
        original = self.helper_fixture()
        for key, value in (('source_sha256', '0' * 64), ('source_only', False), ('source_only', 1),
                           ('model_libraries_imported', True), ('model_libraries_imported', 0)):
            result = copy.deepcopy(original)
            result['isolated_import'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'no model or evaluator'):
                mount.check_helper(result)

    def test_check_closure_delegates_fresh_validation_before_returncode(self):
        guard = types.SimpleNamespace(verify_closed_proof=Mock(side_effect=ValueError('UNIT-ONLY no fresh ownership')))
        with self.assertRaisesRegex(ValueError, 'no fresh ownership'):
            mount.check_closure(guard, {'returncode': 0, 'worker_returncode': 0, 'forced': False})
        guard.verify_closed_proof.assert_called_once()

    def test_nonzero_bool_float_missing_or_forced_closure_rejects(self):
        guard = types.SimpleNamespace(verify_closed_proof=Mock(return_value=True))
        # Synthetic schema only, never a passed lifecycle proof or output file.
        original = {'synthetic_unit_fixture_only': True, 'returncode': 0, 'worker_returncode': 0, 'forced': False}
        for key, value in (('returncode', 1), ('returncode', False), ('returncode', 0.0),
                           ('worker_returncode', 1), ('worker_returncode', False), ('worker_returncode', None),
                           ('forced', True), ('forced', 0), ('forced', None)):
            proof = {**original, key: value}
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'successful unforced complete'):
                mount.check_closure(guard, proof)

    def test_exact_frozen_guard_rejects_incomplete_proof(self):
        path = REPOSITORY / 'tools/arc_learning_agent_20261011/process_guard.py'
        raw = mount.pinned(path, mount.GUARD_SHA)
        guard = mount.load_module(raw, path, 'unit_only_actual_frozen_guard')
        with self.assertRaisesRegex(ValueError, 'complete owned-process closure proof'):
            mount.check_closure(guard, {'synthetic_unit_fixture_only': True, 'returncode': 0})


class FailBeforeExecutionTests(ScratchCase):
    def test_missing_or_forged_candidate_cannot_import_guard_or_create_output(self):
        args = self.accept_arguments()
        with patch.object(mount, 'load_module', side_effect=AssertionError('unverified code import')):
            with self.assertRaises(FileNotFoundError):
                mount.accept(**args)
        self.assertFalse(args['output_root'].exists())
        args['candidate_root'].mkdir()
        (args['candidate_root'] / 'ASSEMBLY-INVENTORY.json').write_bytes(mount.encoded({'UNIT-ONLY': mount.v.desc(SYNTHETIC)}))
        with patch.object(mount, 'obj', side_effect=AssertionError('unverified inventory parsed')):
            with self.assertRaisesRegex(ValueError, 'exact input digest'):
                mount.accept(**args)
        self.assertFalse(args['output_root'].exists())

    def test_bad_receipt_digest_precedes_receipt_parse_or_guard_import(self):
        args = self.accept_arguments()
        args['code_receipt_path'] = self.put('UNIT-ONLY-invalid-receipt.json', b'not JSON')
        with patch.object(mount, 'candidate_inputs', return_value=({}, {})), \
                patch.object(mount, 'receipt_inputs', side_effect=AssertionError('receipt parsed before pin')), \
                patch.object(mount, 'load_module', side_effect=AssertionError('guard imported before receipt pin')):
            with self.assertRaisesRegex(ValueError, 'exact input digest'):
                mount.accept(**args)
        self.assertFalse(args['output_root'].exists())

    def test_wrong_numeric_receipt_precedes_guard_import_and_output(self):
        manifest, receipt, code, _ = self.synthetic_receipt()
        receipt['version'] = 18
        raw = mount.encoded(receipt)
        args = self.accept_arguments()
        args.update(code_root=code, code_receipt_path=self.put('UNIT-ONLY-invalid-receipt.json', raw),
                    code_receipt_sha=mount.sha(raw))
        with patch.object(mount, 'candidate_inputs', return_value=(manifest, {})), \
                patch.object(mount, 'load_module', side_effect=AssertionError('guard imported before numeric gate')):
            with self.assertRaisesRegex(ValueError, 'authentic numeric19'):
                mount.accept(**args)
        self.assertFalse(args['output_root'].exists())

    def test_changed_download_tree_precedes_guard_import_and_output(self):
        manifest, receipt, code, _ = self.synthetic_receipt()
        (code / 'nested/UNIT-ONLY.txt').write_bytes(b'changed')
        raw = mount.encoded(receipt)
        args = self.accept_arguments()
        args.update(code_root=code, code_receipt_path=self.put('UNIT-ONLY-receipt.json', raw), code_receipt_sha=mount.sha(raw))
        with patch.object(mount, 'candidate_inputs', return_value=(manifest, {})), \
                patch.object(mount, 'load_module', side_effect=AssertionError('guard imported before byte gate')):
            with self.assertRaisesRegex(ValueError, 'exact input digest'):
                mount.accept(**args)
        self.assertFalse(args['output_root'].exists())

    def test_invalid_output_and_overlap_reject_before_candidate_read(self):
        args = self.accept_arguments()
        args['output_root'] = REPOSITORY / 'UNIT-ONLY-NEVER-CREATED'
        with self.assertRaisesRegex(ValueError, 'fresh ignored owned output'):
            mount.accept(**args)
        self.assertFalse(args['output_root'].exists())
        for key in ('candidate_root', 'code_root', 'code_receipt_path'):
            args = self.accept_arguments()
            args['output_root'] = args[key] / 'output'
            with self.subTest(key=key), patch.object(mount, 'candidate_inputs', side_effect=AssertionError('overlap read')):
                with self.assertRaisesRegex(ValueError, 'input/output overlap'):
                    mount.accept(**args)
            self.assertFalse(args['output_root'].exists())

    def test_failed_owned_tree_is_stopped_without_final_receipt(self):
        # Deliberate failing lifecycle simulation. It launches no real process,
        # cannot generate closure proof, and never reaches helper acceptance.
        args = self.accept_arguments()
        raw = mount.encoded({'synthetic_unit_fixture_only': True})
        args.update(code_receipt_path=self.put('UNIT-ONLY-receipt.json', raw), code_receipt_sha=mount.sha(raw))
        owned = types.SimpleNamespace(poll=Mock(return_value=0),
            closed_proof=Mock(return_value={'returncode': 1, 'worker_returncode': 1, 'forced': False,
                                           'synthetic_unit_fixture_only': True}), stop=Mock())
        guard = types.SimpleNamespace(OwnedProcessGuard=types.SimpleNamespace(spawn=Mock(return_value=owned)),
                                      verify_closed_proof=Mock(return_value=True))
        with patch.object(mount, 'candidate_inputs', return_value=({}, {mount.GUARD: SYNTHETIC})), \
                patch.object(mount, 'receipt_inputs', return_value={'synthetic_unit_fixture_only': True}), \
                patch.object(mount, 'load_module', return_value=guard):
            with self.assertRaisesRegex(ValueError, 'successful unforced complete'):
                mount.accept(**args)
        owned.stop.assert_called_once_with(timeout=5)
        self.assertFalse((args['output_root'] / 'MOUNT-RECEIPT.json').exists())
        self.assertFalse((args['output_root'] / 'OWNED-CLOSURE.json').exists())
        argv = guard.OwnedProcessGuard.spawn.call_args.args[0]
        self.assertEqual(argv[1:4], ['-I', '-B', '-S'])
        self.assertEqual(argv[4], str(args['candidate_root'] / mount.HELPER))


class PinnedImportTests(ScratchCase):
    def copied_runner(self, helper_raw):
        runner = self.put('accept_numeric_mount.py', mount.read(HERE / 'accept_numeric_mount.py'))
        self.put('v35_lineage.py', helper_raw)
        return runner

    def run_copied(self, runner, *, optimized=False, prefix=''):
        code = prefix + '\nimport runpy\nrunpy.run_path(' + repr(str(runner)) + ', run_name="unit_only_no_main")\n'
        return subprocess.run([sys.executable, *(['-O'] if optimized else []), '-B', '-c', code], cwd=REPOSITORY,
                              env={**os.environ, **OFFLINE}, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)

    def test_tampered_verifier_rejected_before_sentinel_exec_normal_and_optimized(self):
        marker = self.root / 'MUST-NOT-BE-CREATED'
        sentinel = ('from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("executed")\n').encode()
        runner = self.copied_runner(sentinel)
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                result = self.run_copied(runner, optimized=optimized)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'unreviewed verifier source', result.stderr)
                self.assertFalse(marker.exists())

    def test_sys_modules_cannot_replace_exact_source_check(self):
        runner = self.copied_runner(SYNTHETIC)
        prefix = ('import sys, types\n'
                  'sys.modules["v35_lineage"] = types.ModuleType("v35_lineage")\n'
                  'sys.modules["numeric_mount_pinned_stdlib_verifier"] = types.ModuleType("numeric_mount_pinned_stdlib_verifier")\n')
        result = self.run_copied(runner, prefix=prefix)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'unreviewed verifier source', result.stderr)

    def test_authentic_import_makes_no_network_subprocess_or_bytecode(self):
        runner = self.copied_runner(mount.read(HERE / 'v35_lineage.py'))
        prefix = ('import socket, subprocess\n'
                  'def forbidden(*args, **kwargs):\n    raise RuntimeError("external execution forbidden")\n'
                  'socket.create_connection = forbidden\nsubprocess.run = forbidden\n')
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                result = self.run_copied(runner, optimized=optimized, prefix=prefix)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(result.stdout, b'')
        self.assertFalse((self.root / '__pycache__').exists())

    def test_symlink_hardlink_and_fifo_verifier_reject_before_body(self):
        runner = self.copied_runner(mount.read(HERE / 'v35_lineage.py'))
        verifier = self.root / 'v35_lineage.py'
        target = self.put('actual-verifier.py', verifier.read_bytes())
        verifier.unlink()
        for kind in ('symlink', 'hardlink', 'fifo'):
            if kind == 'symlink':
                verifier.symlink_to(target)
            elif kind == 'hardlink':
                os.link(target, verifier)
            else:
                os.mkfifo(verifier)
            with self.subTest(kind=kind):
                result = self.run_copied(runner)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(b'unsafe pinned verifier source' in result.stderr or b'bounded ordinary verifier source' in result.stderr)
            verifier.unlink()


class AvailableActualCandidateTests(unittest.TestCase):
    def test_exact_actual_final_candidate_authenticates_without_import_or_zip_members(self):
        root = REPOSITORY / '.irisx/preparation-successor/actual-final-candidate-001'
        if not root.is_dir():
            self.skipTest('Actual final candidate is absent; no substitute fixture is generated')
        with patch.object(mount, 'load_module', side_effect=AssertionError('candidate check imported code')), \
                patch.object(zipfile.ZipFile, 'open', side_effect=AssertionError('ZIP member read forbidden')), \
                patch.object(zipfile.ZipFile, 'read', side_effect=AssertionError('ZIP member read forbidden')):
            manifest, files = mount.candidate_inputs(root)
        self.assertEqual(mount.sha(files['publication-manifest.json']), mount.MANIFEST_SHA)
        self.assertEqual(mount.sha(files[mount.HELPER]), mount.HELPER_SHA)
        self.assertEqual(mount.sha(files[mount.GUARD]), mount.GUARD_SHA)
        self.assertEqual(manifest['runtime_source_sha256'], mount.SOURCE_SHA)
        self.assertIs(manifest['run_authorized'], True)


if __name__ == '__main__':
    unittest.main()

"""Offline unit-only checks for the pinned diagnostic mount successor.

All invented candidate, provider and closure documents are synthetic fixtures.
No provider, model, native helper or production mount acceptance is executed.
Mocked accept() control flow captures final writes in memory, never producing a
MOUNT-RECEIPT.json. Test files stay in ignored repository .irisx scratch.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from tools.arc_qwen_rlvr004_20261013.numeric_replay_diagnostic_20261016.assembly import accept_numeric_mount as mount

REPO = Path(__file__).absolute().parents[4]
SYNTHETIC = b'SYNTHETIC UNIT-ONLY; NOT PROVIDER OR PRODUCTION EVIDENCE\n'
SCRATCH = None


def setUpModule():
    global SCRATCH
    parent = REPO / '.irisx'
    parent.mkdir(exist_ok=True)
    SCRATCH = tempfile.TemporaryDirectory(dir=parent, prefix='numeric260-mount-tests-')


def tearDownModule():
    if SCRATCH is not None:
        SCRATCH.cleanup()


def load(path):
    module = types.ModuleType('synthetic_mount_test_module')
    module.__file__, module.__package__ = str(path), ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                 optimize=sys.flags.optimize), vars(module))
    return module


class FixtureCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=SCRATCH.name, prefix='UNIT-ONLY-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, value in (('MANIFEST_SHA', 'a' * 64), ('INVENTORY_SHA', 'b' * 64),
                            ('SOURCE_SHA', mount.SOURCE_SHA), ('ARCHIVE_SHA', mount.ARCHIVE_SHA),
                            ('CODE_MANIFEST_SHA', 'c' * 64)):
            item = patch.object(mount.base, name, value)
            item.start(); self.addCleanup(item.stop)
        for item in (patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')),
                     patch.object(subprocess, 'Popen', side_effect=AssertionError('native process forbidden'))):
            item.start(); self.addCleanup(item.stop)

    def put(self, name, raw=SYNTHETIC):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def helper(self):
        return {'synthetic_unit_fixture_only': True,
            'format': 'irisx/rlvr-actual-local-code-mount-acceptance-v1', 'status': 'PASS',
            'model_or_GPU_calls': 0, 'public_evaluator_body_reads': 0, 'provider_calls': 0,
            'production_execution_claim': False, 'provider_provenance_verified_by_this_helper': False,
            'external_numeric_download_receipt_required': True,
            'source_acceptance': {'format': 'irisx/rlvr-no-model-source-acceptance-v1',
                'source_sha256': mount.SOURCE_SHA, 'source_archive_sha256': mount.ARCHIVE_SHA,
                'manifest_sha256': mount.base.CODE_MANIFEST_SHA, 'source_members': 260,
                'exact_archive_bytes_available': True, 'model_imported': False, 'weights_read': False,
                'evaluator_body_read': False, 'provider_mount_verified': False},
            'isolated_import': {'source_sha256': mount.SOURCE_SHA, 'source_only': True,
                'model_libraries_imported': False}}

    def candidate(self, change=None):
        manifest = {'synthetic_unit_fixture_only': True,
            'format': 'irisx/qwen14b-rlvr-run008-publication-contract-v1', 'run_authorized': True,
            'run_purpose': mount.RUN_PURPOSE, 'runtime_source_sha256': mount.SOURCE_SHA,
            'consumer_contract': {'source_archive': {'sha256': mount.ARCHIVE_SHA}},
            'datasets': [{'expected_version': 23, 'root_manifest': {'sha256': 'c' * 64},
                'expected_readback_layouts': {'UNIT-ONLY': [{'path': 'UNIT-ONLY.txt', **mount.base.v.desc(SYNTHETIC)}]}}]}
        if change is not None:
            change(manifest)
        raw = mount.base.encoded(manifest)
        files = {'publication-manifest.json': raw,
            mount.base.HELPER: (REPO / 'tools/arc_qwen_rlvr004_20261013/support/assembly/accept_downloaded_mount.py').read_bytes(),
            mount.base.GUARD: (REPO / 'tools/arc_learning_agent_20261011/process_guard.py').read_bytes()}
        rows = {name: mount.base.v.desc(raw) for name, raw in files.items()}
        inventory = mount.base.encoded(rows)
        for name, raw in files.items():
            self.put('candidate/' + name, raw)
        self.put('candidate/ASSEMBLY-INVENTORY.json', inventory)
        mount.base.MANIFEST_SHA = mount.base.sha(files['publication-manifest.json'])
        mount.base.INVENTORY_SHA = mount.base.sha(inventory)
        return manifest, files

    def receipt(self, manifest):
        code = self.root / 'UNIT-ONLY-code'
        self.put('UNIT-ONLY-code/UNIT-ONLY.txt')
        rows = {'UNIT-ONLY.txt': mount.base.v.desc(SYNTHETIC)}
        metadata = {'synthetic_unit_fixture_only': True, 'id': 12504696,
            'version': 23, 'private': True, 'owner_ref': 'danielwuu', 'ref': mount.base.REFERENCE}
        return {'synthetic_unit_fixture_only': True, 'status': 'VERIFIED_CODE_V23',
            'dataset_id': 12504696, 'version': 23, 'is_private': True, 'exact_byte_roundtrip': True,
            'manifest_sha256': mount.base.MANIFEST_SHA, 'publication_manifest_sha256': mount.base.MANIFEST_SHA,
            'payload_root': str(code), 'before': metadata, 'after': copy.deepcopy(metadata),
            'layout': 'UNIT-ONLY', 'files': 1, 'bytes': len(SYNTHETIC),
            'inventory_sha256': mount.base.sha(mount.base.v.canonical(rows)),
            'readback_method': 'numeric_per_file', 'provider_archive_verified': False, 'archive_sha256': None}

    def arguments(self):
        manifest, _ = self.candidate()
        raw = mount.base.encoded(self.receipt(manifest))
        receipt = self.put('UNIT-ONLY-receipt.json', raw)
        return {'candidate_root': self.root / 'candidate', 'code_root': self.root / 'UNIT-ONLY-code',
            'code_receipt_path': receipt, 'code_receipt_sha': mount.base.sha(raw),
            'output_root': self.root / 'UNIT-ONLY-output', 'manifest_sha': mount.base.MANIFEST_SHA,
            'inventory_sha': mount.base.INVENTORY_SHA}

    def mocked_accept(self, args, *, proof_change=None, guard_error=None, helper_change=None,
                      before_second_candidate=None, source_swap=False):
        """Exercise inherited orchestration with no process and no final writes."""
        proof = {'synthetic_unit_fixture_only': True, 'returncode': 0, 'worker_returncode': 0, 'forced': False}
        if proof_change is not None:
            proof.update(proof_change)
        helper = self.helper()
        helper.update(actual_code_root=str(args['code_root']),
                      expected_code_reference=mount.base.REFERENCE + '/23')
        if helper_change is not None:
            helper_change(helper)
        owned = Mock()
        owned.poll.return_value = 0
        owned.closed_proof.return_value = proof
        guard = Mock()
        guard.verify_closed_proof.side_effect = guard_error
        def spawn(*_args, **kwargs):
            raw = mount.base.encoded(helper)
            kwargs['stdout'].write(raw)
            self.put('UNIT-ONLY-output/acceptance/receipt.json', raw)
            return owned
        guard.OwnedProcessGuard.spawn.side_effect = spawn
        written = {}
        def put(path, value):
            # Final production-shaped outputs are inspected only in memory.
            written[Path(path).name] = copy.deepcopy(value)
            return {'path': str(path), **mount.base.v.desc(mount.base.encoded(value))}
        calls = []
        def candidate(root):
            calls.append(root)
            if len(calls) == 2 and before_second_candidate is not None:
                before_second_candidate()
            return mount.candidate_inputs(root)
        original_read = mount._read
        def read(path, cap=mount.base.v.CAP):
            raw = original_read(path, cap)
            return raw + b'\n# substituted\n' if source_swap and Path(path) == mount.ENTRY else raw
        with (patch.object(mount.base, 'load_module', return_value=guard),
              patch.object(mount.base, 'put', side_effect=put),
              patch.object(mount.base, 'candidate_inputs', side_effect=candidate),
              patch.object(mount, '_read', side_effect=read)):
            result = mount.accept(**args)
        self.assertFalse((args['output_root'] / 'MOUNT-RECEIPT.json').exists())
        return result, written, calls, guard


class SourceAndParityTests(FixtureCase):
    def test_exact_source_archive_match_active_wire_and_consumed_pins_reject(self):
        wire = load(mount.ENTRY.parents[1] / 'publication/verify_active_wire.py')
        self.assertEqual((mount.SOURCE_SHA, mount.ARCHIVE_SHA), (wire.SOURCE, wire.ARCHIVE))
        self.assertEqual(mount.RUN_PURPOSE, wire.RUN_PURPOSE)
        consumed = ('69bf39ddee56278197eb4f1a46119d569dba45f51621a92588a56dd7d6f1e292',
                    '085a64b4dbe9c35db40d81ef0ae28dcce445eaa78f5da0e85518900bab035061')
        self.assertNotEqual(mount.SOURCE_SHA, consumed[0])
        self.assertNotEqual(mount.ARCHIVE_SHA, consumed[1])
        for index in (0, 1):
            def change(manifest):
                if index == 0: manifest['runtime_source_sha256'] = consumed[0]
                else: manifest['consumer_contract']['source_archive']['sha256'] = consumed[1]
            self.candidate(change)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'exact training-only numeric diagnostic'):
                mount.candidate_inputs(self.root / 'candidate')

    def test_base_source_pin_dependency_context_and_original_functions(self):
        self.assertEqual(mount.base.sha(mount.BASE.read_bytes()), mount.BASE_SHA)
        self.assertEqual(mount.base.HERE, mount.BASE.parent)
        self.assertEqual(mount.base.__file__, str(mount.ENTRY))
        self.assertEqual(mount.base.HERE.parents[2], REPO)
        self.assertIs(mount.accept, mount.base.accept)
        self.assertIs(mount.main, mount.base.main)
        self.assertIs(mount.base.candidate_inputs, mount.candidate_inputs)
        self.assertIs(mount.base.check_helper, mount.check_helper)
        self.assertEqual(mount.BASE_SHA, 'd84e2aa27edc5cef4fe557a9c327a5b4bffebbadf638d80948927677f1bd70b9')

    def test_check_helper_ast_only_count_label_and_live_base_namespace_differ(self):
        def node(path):
            return next(n for n in ast.parse(path.read_bytes()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'check_helper')
        class Normalize(ast.NodeTransformer):
            def visit_Attribute(self, item):
                if isinstance(item.value, ast.Name) and item.value.id == 'base':
                    if item.attr not in ('need', 'SOURCE_SHA', 'ARCHIVE_SHA', 'CODE_MANIFEST_SHA'):
                        raise ValueError('unexpected changed base qualification')
                    return ast.copy_location(ast.Name(id=item.attr, ctx=item.ctx), item)
                return self.generic_visit(item)
            def visit_Constant(self, item):
                if type(item.value) is int and item.value == 260:
                    return ast.copy_location(ast.Constant(value=259), item)
                if item.value == 'exact complete diagnostic source260 acceptance':
                    return ast.copy_location(ast.Constant(value='exact complete source259 acceptance'), item)
                return item
        self.assertEqual(ast.dump(node(mount.BASE)), ast.dump(Normalize().visit(node(mount.ENTRY))))

    def test_unchanged_base_still_accepts_only_259(self):
        base = load(mount.BASE)
        base.SOURCE_SHA, base.ARCHIVE_SHA, base.CODE_MANIFEST_SHA = mount.SOURCE_SHA, mount.ARCHIVE_SHA, 'c' * 64
        helper = self.helper()
        with self.assertRaisesRegex(ValueError, 'complete source259'):
            base.check_helper(helper)
        helper['source_acceptance']['source_members'] = 259
        base.check_helper(helper)
        with self.assertRaisesRegex(ValueError, 'diagnostic source260'):
            mount.check_helper(helper)
        self.assertEqual(mount.base.sha(mount.BASE.read_bytes()), mount.BASE_SHA)

    def test_substituted_base_rejected_before_execution(self):
        entry = self.put('isolated/numeric_replay_diagnostic_20261016/assembly/accept_numeric_mount.py', mount.ENTRY.read_bytes())
        marker = self.root / 'EXECUTED'
        self.put('isolated/admission_run008/accept_numeric_mount.py',
                 ('from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("unsafe")\n').encode())
        with self.assertRaisesRegex(ValueError, 'unreviewed frozen'):
            load(entry)
        self.assertFalse(marker.exists())

    def test_source_reader_rejects_links_fifo_directory_and_bound(self):
        source = self.put('ordinary.py', b'x = 1\n')
        self.assertEqual(mount.source_bytes(source), source.read_bytes())
        for kind in ('symlink', 'hardlink', 'fifo', 'directory', 'oversize'):
            path = self.root / ('bad-' + kind)
            if kind == 'symlink': path.symlink_to(source)
            elif kind == 'hardlink': os.link(source, path)
            elif kind == 'fifo': os.mkfifo(path)
            elif kind == 'directory': path.mkdir()
            else: path.write_bytes(b'x' * (1024**2 + 1))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                mount.source_bytes(path)
            if kind != 'directory': path.unlink()
        alias = self.root / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ordinary mount runner'):
            mount.source_bytes(alias / source.name)

    def test_source_replacement_between_stat_and_open_rejects(self):
        source = self.put('ordinary.py', b'first\n')
        replacement = self.put('replacement.py', b'other\n')
        original = os.open
        def opening(path, flags, *args, **kwargs):
            if Path(path) == source:
                os.replace(replacement, source)
            return original(path, flags, *args, **kwargs)
        with patch.object(os, 'open', side_effect=opening), self.assertRaisesRegex(ValueError, 'source replaced'):
            mount.source_bytes(source)

    def test_source_mutation_during_read_rejects(self):
        source = self.put('ordinary.py', b'first\n')
        original = os.fstat
        calls = []
        def fstat(fd):
            calls.append(fd)
            if len(calls) == 2:
                source.write_bytes(b'other\n')
            return original(fd)
        with patch.object(os, 'fstat', side_effect=fstat), self.assertRaisesRegex(ValueError, 'source changed'):
            mount.source_bytes(source)

    def test_same_length_mutation_with_identical_stat_keys_rejects(self):
        source = self.put('ordinary.py', b'first\n')
        before = source.lstat()
        original_lstat, original_pread = Path.lstat, os.pread
        calls, samples = [], []
        def fstat(fd):
            calls.append(fd)
            if len(calls) == 2:
                source.write_bytes(b'other\n')
            return before
        def lstat(path, *args, **kwargs):
            return before if path == source else original_lstat(path, *args, **kwargs)
        def pread(fd, size, offset):
            raw = original_pread(fd, size, offset)
            samples.append((size, offset, raw))
            return raw
        with patch.object(os, 'fstat', side_effect=fstat), patch.object(Path, 'lstat', new=lstat), \
                patch.object(os, 'pread', side_effect=pread), \
                self.assertRaisesRegex(ValueError, 'source changed'):
            mount.source_bytes(source)
        self.assertEqual(samples, [(1024**2 + 1, 0, b'other\n')])
        self.assertEqual(source.read_bytes(), b'other\n')

    def test_entry_or_base_change_after_import_rejects(self):
        original = mount.source_bytes
        for target in (mount.ENTRY, mount.BASE):
            def read(path):
                raw = original(path)
                return raw + b'\n' if path == target else raw
            with self.subTest(target=target), patch.object(mount, 'source_bytes', side_effect=read):
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    mount.check_sources()

    def test_cli_keeps_exact_seven_required_arguments(self):
        names = ('candidate-root', 'code-root', 'code-receipt-path', 'code-receipt-sha',
                 'output-root', 'manifest-sha', 'inventory-sha')
        argv = [str(mount.ENTRY)] + [item for name in names for item in ('--' + name, 'UNIT-ONLY-' + name)]
        with patch.object(sys, 'argv', argv), patch.object(mount.base, 'accept', return_value={}) as accept, patch('sys.stdout', new=io.StringIO()):
            mount.main()
        self.assertEqual(accept.call_args.kwargs, {name.replace('-', '_'): 'UNIT-ONLY-' + name for name in names})
        with patch.object(sys, 'argv', argv + ['--source-members', '259']), patch('sys.stderr', new=io.StringIO()):
            with self.assertRaises(SystemExit): mount.main()


class CandidateTests(FixtureCase):
    def test_original_tuple_and_closed_bytes_are_preserved(self):
        manifest, files = self.candidate()
        actual = mount.candidate_inputs(self.root / 'candidate')
        self.assertEqual(actual, (manifest, files))
        with patch.object(mount, '_candidate_inputs', return_value=actual):
            self.assertIs(mount.candidate_inputs(self.root / 'candidate'), actual)
        self.assertEqual(mount.base.SOURCE_SHA, mount.SOURCE_SHA)
        self.assertEqual(mount.base.ARCHIVE_SHA, mount.ARCHIVE_SHA)

    def test_exact_purpose_source_archive_reject_wrong_missing_null_and_bool(self):
        for field in ('run_purpose', 'runtime_source_sha256', 'archive'):
            for value in ('wrong', '0' * 64, None, True, False, 260, 260.0, ['wrong']):
                def change(manifest):
                    if field == 'archive': manifest['consumer_contract']['source_archive']['sha256'] = value
                    else: manifest[field] = value
                self.candidate(change)
                with self.subTest(field=field, value=value), self.assertRaises((ValueError, TypeError)):
                    mount.candidate_inputs(self.root / 'candidate')
            def remove(manifest):
                if field == 'archive': del manifest['consumer_contract']['source_archive']['sha256']
                else: del manifest[field]
            self.candidate(remove)
            with self.subTest(field=field, missing=True), self.assertRaises((ValueError, KeyError)):
                mount.candidate_inputs(self.root / 'candidate')

    def test_inherited_manifest_inventory_helper_guard_and_closed_tree_checks(self):
        for target in ('ASSEMBLY-INVENTORY.json', 'publication-manifest.json', mount.base.HELPER, mount.base.GUARD):
            self.candidate()
            path = self.root / 'candidate' / target
            path.write_bytes(path.read_bytes() + b'\n')
            with self.subTest(target=target), self.assertRaises(ValueError):
                mount.candidate_inputs(self.root / 'candidate')
        self.candidate()
        extra = self.put('candidate/UNIT-ONLY-extra')
        with self.assertRaisesRegex(ValueError, 'closed member set'):
            mount.candidate_inputs(self.root / 'candidate')
        extra.unlink()
        for key, value in (('format', 'other'), ('run_authorized', False), ('run_authorized', 1)):
            self.candidate(lambda manifest: manifest.update({key: value}))
            with self.subTest(key=key), self.assertRaises(ValueError):
                mount.candidate_inputs(self.root / 'candidate')


class HelperTests(FixtureCase):
    def test_exact_260_is_accepted_without_mutation(self):
        helper = self.helper(); original = copy.deepcopy(helper)
        mount.check_helper(helper)
        self.assertEqual(helper, original)

    def test_top_level_flags_and_counter_types_are_unchanged(self):
        for key in ('format', 'status', 'model_or_GPU_calls', 'public_evaluator_body_reads', 'provider_calls',
                    'production_execution_claim', 'provider_provenance_verified_by_this_helper',
                    'external_numeric_download_receipt_required'):
            original = self.helper()
            for value in (None, True, False, 0, 0.0, 1, '0', 'wrong'):
                if type(value) is type(original[key]) and value == original[key]: continue
                helper = copy.deepcopy(original); helper[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    mount.check_helper(helper)

    def test_all_source_and_isolated_fields_reject_changes(self):
        original = self.helper()
        for section in ('source_acceptance', 'isolated_import'):
            for key in original[section]:
                values = (None, True, False, 0, 1, 'wrong')
                if key == 'source_members': values += (258, 259, 261, 260.0, '260')
                if key.endswith('sha256'): values += ('0' * 64,)
                for value in values:
                    if type(value) is type(original[section][key]) and value == original[section][key]: continue
                    helper = copy.deepcopy(original); helper[section][key] = value
                    with self.subTest(section=section, key=key, value=value), self.assertRaises(ValueError):
                        mount.check_helper(helper)
                helper = copy.deepcopy(original); del helper[section][key]
                with self.subTest(section=section, missing=key), self.assertRaises((ValueError, KeyError)):
                    mount.check_helper(helper)

    def test_root_manifest_digest_is_live_from_original_accept(self):
        helper = self.helper()
        mount.base.CODE_MANIFEST_SHA = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'diagnostic source260'):
            mount.check_helper(helper)
        helper['source_acceptance']['manifest_sha256'] = mount.base.CODE_MANIFEST_SHA
        mount.check_helper(helper)


class InheritedReceiptAndClosureTests(FixtureCase):
    def test_original_receipt_errors_propagate(self):
        manifest, _ = self.candidate()
        receipt = self.receipt(manifest); code = self.root / 'UNIT-ONLY-code'
        self.assertEqual(mount.base.receipt_inputs(manifest, mount.base.encoded(receipt), code), receipt)
        changes = {'status': 'unverified', 'dataset_id': 1, 'version': True, 'is_private': 1,
            'exact_byte_roundtrip': False, 'manifest_sha256': '0' * 64, 'publication_manifest_sha256': None,
            'payload_root': str(self.root), 'before': None, 'after': {}, 'layout': 'unknown',
            'files': True, 'bytes': float(len(SYNTHETIC)), 'inventory_sha256': '0' * 64,
            'readback_method': 'fixture', 'provider_archive_verified': True, 'archive_sha256': '0' * 64}
        for key, value in changes.items():
            changed = copy.deepcopy(receipt); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                mount.base.receipt_inputs(manifest, mount.base.encoded(changed), code)
        self.put('UNIT-ONLY-code/extra')
        with self.assertRaisesRegex(ValueError, 'closed member set'):
            mount.base.receipt_inputs(manifest, mount.base.encoded(receipt), code)

    def test_original_closure_errors_propagate_and_types_stay_strict(self):
        good = {'returncode': 0, 'worker_returncode': 0, 'forced': False}
        for key, values in (('returncode', (1, False, 0.0)), ('worker_returncode', (1, False, 0.0)),
                            ('forced', (True, 0, None))):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'unforced complete'):
                    mount.base.check_closure(Mock(), dict(good, **{key: value}))
        guard = Mock(); guard.verify_closed_proof.side_effect = ValueError('UNIT-ONLY original guard failure')
        with self.assertRaisesRegex(ValueError, 'original guard failure'):
            mount.base.check_closure(guard, good)

    def test_original_frozen_guard_rejects_incomplete_proof(self):
        path = REPO / 'tools/arc_learning_agent_20261011/process_guard.py'
        raw = mount.base.pinned(path, mount.base.GUARD_SHA)
        guard = mount.base.load_module(raw, path, 'UNIT_ONLY_frozen_guard')
        with self.assertRaisesRegex(ValueError, 'complete owned-process closure proof'):
            mount.base.check_closure(guard, {'synthetic_unit_fixture_only': True, 'returncode': 0})

    def test_inherited_accept_checks_candidate_twice_and_reports_real_entry_hash(self):
        args = self.arguments()
        result, written, calls, guard = self.mocked_accept(args)
        self.assertEqual(calls, [args['candidate_root'], args['candidate_root']])
        self.assertEqual(result['runner_source_sha256'], hashlib.sha256(mount.ENTRY.read_bytes()).hexdigest())
        self.assertNotEqual(result['runner_source_sha256'], mount.BASE_SHA)
        self.assertEqual(result['source_sha256'], mount.SOURCE_SHA)
        self.assertEqual(guard.verify_closed_proof.call_count, 2)
        self.assertEqual(written['MOUNT-RECEIPT.json'], result)
        self.assertEqual(result['helper_source_sha256'], mount.base.HELPER_SHA)
        self.assertFalse(result['production_execution_claim'])

    def test_second_candidate_recheck_rejects_purpose_change(self):
        args = self.arguments()
        def changed():
            self.candidate(lambda manifest: manifest.update(run_purpose='wrong'))
        with self.assertRaisesRegex(ValueError, 'exact training-only numeric diagnostic'):
            self.mocked_accept(args, before_second_candidate=changed)
        self.assertFalse((args['output_root'] / 'MOUNT-RECEIPT.json').exists())

    def test_inherited_accept_does_not_upgrade_bad_helper_count(self):
        args = self.arguments()
        with self.assertRaisesRegex(ValueError, 'diagnostic source260'):
            self.mocked_accept(args, helper_change=lambda helper: helper['source_acceptance'].update(source_members=259))
        self.assertFalse((args['output_root'] / 'MOUNT-RECEIPT.json').exists())

    def test_inherited_accept_rejects_source_substitution_at_receipt_hash(self):
        args = self.arguments()
        with self.assertRaisesRegex(ValueError, 'receipt source changed'):
            self.mocked_accept(args, source_swap=True)
        self.assertFalse((args['output_root'] / 'MOUNT-RECEIPT.json').exists())

    def test_original_accept_propagates_guard_failure_without_receipt(self):
        args = self.arguments()
        with self.assertRaisesRegex(ValueError, 'UNIT-ONLY closure rejected'):
            self.mocked_accept(args, guard_error=ValueError('UNIT-ONLY closure rejected'))
        self.assertFalse((args['output_root'] / 'MOUNT-RECEIPT.json').exists())

    def test_original_accept_rejects_receipt_before_process_or_output(self):
        args = self.arguments()
        receipt = mount.base.obj(args['code_receipt_path'].read_bytes()); receipt['is_private'] = False
        raw = mount.base.encoded(receipt); args['code_receipt_path'].write_bytes(raw)
        args['code_receipt_sha'] = mount.base.sha(raw)
        with patch.object(mount.base, 'load_module', side_effect=AssertionError('process code loaded')):
            with self.assertRaisesRegex(ValueError, 'authentic numeric-successor'):
                mount.accept(**args)
        self.assertFalse(args['output_root'].exists())


if __name__ == '__main__':
    unittest.main()

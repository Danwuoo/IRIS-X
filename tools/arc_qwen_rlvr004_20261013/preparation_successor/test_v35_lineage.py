"""Offline negative/helper coverage for the original-v35 provenance gate.

Synthetic fixtures are explicitly UNIT-ONLY, fail the immutable original-code18
hash, and cannot become a verified lineage supplement. No authentic historical
state is manufactured, no embedded absolute path is opened, and no ZIP member,
provider, credential, model, GPU, or scorer is used. Writes stay below .irisx.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from tools.arc_qwen_rlvr004_20261013.preparation_successor import v35_lineage as lineage

REPOSITORY = Path(__file__).resolve().parents[3]
SYNTHETIC = b'SYNTHETIC UNIT-ONLY; NEVER AUTHENTIC HISTORICAL EVIDENCE\n'
OFFLINE = {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0',
           'HF_HUB_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1',
           'TRANSFORMERS_OFFLINE': '1', 'WANDB_MODE': 'offline'}
SCRATCH = None
PATCHES = []
OLD_BYTECODE = None


def setUpModule():
    global SCRATCH, OLD_BYTECODE
    OLD_BYTECODE = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    parent = REPOSITORY / '.irisx'
    parent.mkdir(exist_ok=True)
    SCRATCH = tempfile.TemporaryDirectory(dir=parent, prefix='v35-lineage-tests-')
    PATCHES.extend((patch.dict(os.environ, {**OFFLINE, 'TMPDIR': SCRATCH.name}),
                   patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden'))))
    for p in PATCHES:
        p.start()


def tearDownModule():
    for p in reversed(PATCHES):
        p.stop()
    PATCHES.clear()
    if SCRATCH is not None:
        SCRATCH.cleanup()
    if OLD_BYTECODE is not None:
        sys.dont_write_bytecode = OLD_BYTECODE


class ScratchCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=SCRATCH.name, prefix='synthetic-negative-only-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def put(self, name, raw=SYNTHETIC):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def negative_original_inputs(self):
        """Locally sealed fake roles; immutable old inventory MUST reject them."""
        marker = self.root / 'MUST-NOT-BE-READ-OR-CREATED'
        base, state = self.root / 'UNIT-ONLY-base', self.root / 'UNIT-ONLY-state'
        raw = {'frozen-code18/ASSEMBLY-INVENTORY.json': SYNTHETIC}
        for name in lineage.BASE_NAMES:
            raw['frozen-code18/' + name] = (b'from pathlib import Path\nPath(' +
                repr(str(marker)).encode() + b').write_text("BAD EXECUTION")\n') if name.endswith('.py') else SYNTHETIC
        state_rows = {}
        for name in lineage.STATE_NAMES:
            body = lineage.encoded({'synthetic_unit_fixture_only': True, 'role': name,
                                    'path': str(marker), 'evaluator_root': str(marker),
                                    'original_epoch': lineage.EPOCH, 'original_deadline': lineage.DEADLINE})
            raw['state/' + name] = body
            state_rows[name] = lineage.desc(body)
        inventory_raw = lineage.encoded(state_rows)
        raw['ORIGINAL-STATE-INVENTORY.json'] = inventory_raw
        for name, body in raw.items():
            if name.startswith('frozen-code18/'):
                self.put('UNIT-ONLY-base/' + name.removeprefix('frozen-code18/'), body)
            elif name.startswith('state/'):
                self.put('UNIT-ONLY-state/' + name.removeprefix('state/'), body)
        inventory = self.put('UNIT-ONLY-state-inventory.json', inventory_raw)
        return base, state, inventory, lineage.sha(inventory_raw), raw, marker

    def negative_supplement(self):
        _, _, _, inventory_sha, raw, marker = self.negative_original_inputs()
        bundle = self.root / 'UNIT-ONLY-invalid-supplement'
        proof = {'format': lineage.FORMAT, 'status': 'ORIGINAL_DISPATCH_LINEAGE_VERIFIED_NO_RUNTIME_CLOSURE',
                 'synthetic_unit_fixture_only': True,
                 'notebook_version': 35, 'code_version': 18,
                 'code18_assembly_inventory_sha256': lineage.ASSEMBLY_SHA,
                 'code18_publication_manifest_sha256': lineage.MANIFEST_SHA,
                 'state_inventory_sha256': inventory_sha,
                 'closed_files': {n: lineage.desc(b) for n, b in raw.items()}}
        # This envelope has the schema required to reach negative integrity
        # checks. Its original code18 inventory is deliberately unauthentic.
        for name, body in raw.items():
            self.put('UNIT-ONLY-invalid-supplement/' + name, body)
        manifest = bundle / 'LAUNCH-LINEAGE.json'
        manifest.write_bytes(lineage.encoded(proof))
        return bundle, proof, raw, marker

    def write_proof(self, bundle, proof):
        raw = lineage.encoded(proof)
        (bundle / 'LAUNCH-LINEAGE.json').write_bytes(raw)
        return lineage.sha(raw)


class JsonPathAndClockTests(ScratchCase):
    def test_strict_json_duplicate_keys_at_any_depth(self):
        for raw in (b'{"a":1,"a":2}', b'{"outer":{"x":1,"x":2}}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                lineage.obj(raw)

    def test_json_rejects_nonfinite_and_nonobject_values(self):
        for raw in (b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}',
                    b'{"a":1e9999}', b'{"a":-1e9999}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'finite JSON'):
                lineage.obj(raw)
        for raw in (b'[]', b'null', b'true', b'1', b'"text"'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'JSON object'):
                lineage.obj(raw)

    def test_json_encoding_is_deterministic_and_preserves_finite_values(self):
        value = {'z': 'UNIT-ONLY 測試', 'a': [False, None, 0, 1.5]}
        raw = lineage.encoded(value)
        self.assertEqual(lineage.obj(raw), value)
        self.assertEqual(raw, lineage.encoded(dict(reversed(list(value.items())))))
        self.assertTrue(raw.endswith(b'\n'))
        self.assertEqual(lineage.canonical(value), b'{"a":[false,null,0,1.5],"z":"UNIT-ONLY \xe6\xb8\xac\xe8\xa9\xa6"}\n')
        with self.assertRaises(ValueError):
            lineage.encoded({'invalid': float('nan')})

    def test_only_canonical_safe_relative_paths(self):
        self.assertEqual(lineage.relative('directory/UNIT-ONLY.json'), 'directory/UNIT-ONLY.json')
        for name in (None, 7, '', '.', '..', '../x', '/x', 'a//b', 'a/./b', 'a/../b',
                     'a/', 'a\\b', 'C:x', 'x\ny', 'x\x00y', 'x\x7fy'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'relative path'):
                lineage.relative(name)

    def test_inventory_descriptor_schema_and_types(self):
        good = lineage.desc(SYNTHETIC)
        lineage.check_rows({'UNIT-ONLY.json': good})
        variants = (None, [], {}, {'bytes': True, 'sha256': good['sha256']},
                    {**good, 'bytes': -1}, {**good, 'bytes': lineage.CAP + 1},
                    {**good, 'bytes': 1.0}, {**good, 'path': 'UNIT-ONLY.json'},
                    {**good, 'sha256': 'A' * 64}, {**good, 'sha256': 'g' * 64},
                    {**good, 'sha256': '0' * 63}, {**good, 'sha256': b'0' * 64})
        for row in variants:
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, 'descriptor'):
                lineage.check_rows({'UNIT-ONLY.json': row})
        for rows in (None, [], {}):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, 'closed inventory'):
                lineage.check_rows(rows)
        with self.assertRaisesRegex(ValueError, 'closed inventory'):
            lineage.check_rows({str(i): good for i in range(12001)})

    def test_original_clock_never_samples_or_renews_time(self):
        with patch.object(time, 'time', side_effect=AssertionError('clock sampling forbidden')), \
                patch.object(time, 'monotonic', side_effect=AssertionError('clock sampling forbidden')):
            expected = {'dispatch_epoch': 1791871874, 'predispatch_epoch': 1791871874,
                        'deadline_epoch': 1791915074, 'global_deadline_epoch': 1791915074,
                        'execution_deadline_epoch': 1791913874,
                        'outer_deadline_epoch': 1791914054, 'provider_timeout_seconds': 42300}
            self.assertEqual(lineage.clock(), expected)
            self.assertEqual(lineage.DEADLINE - lineage.EPOCH, 43200)
            self.assertTrue(all(type(x) is int for x in lineage.clock().values()))

    def test_notebook_normalization_changes_only_source_list_representation(self):
        left = {'cells': [{'cell_type': 'code', 'source': ['a\n', 'b\n'],
                           'outputs': [], 'metadata': {'UNIT-ONLY': True}}], 'metadata': {'same': 3}}
        right = copy.deepcopy(left)
        right['cells'][0]['source'] = 'a\nb\n'
        self.assertEqual(lineage.normalized(lineage.encoded(left)), right)
        self.assertEqual(lineage.normalized(lineage.encoded(right)), right)
        changed = copy.deepcopy(right)
        changed['cells'][0]['metadata']['UNIT-ONLY'] = False
        self.assertNotEqual(lineage.normalized(lineage.encoded(left)), changed)

    def test_target_free_fixed_role_and_nonclosure_flag_sets(self):
        self.assertEqual(len(lineage.STATE_NAMES), 13)
        self.assertEqual(len(set(lineage.STATE_NAMES)), 13)
        self.assertEqual(len(lineage.BASE_NAMES), 5)
        self.assertEqual(set(lineage.FALSE_FLAGS), {'runtime_or_model_closure_verified',
                         'physical_costs_known', 'manual_failure_root_cause_verified', 'scientific_result_verified'})
        for name in (*lineage.STATE_NAMES, *lineage.BASE_NAMES):
            self.assertFalse(name.endswith('.zip'))


class SafeBodyReadTests(ScratchCase):
    def test_regular_input_and_bound(self):
        path = self.put('UNIT-ONLY.txt')
        self.assertEqual(lineage.read(path), SYNTHETIC)
        with self.assertRaisesRegex(ValueError, 'bounded ordinary input'):
            lineage.read(path, cap=len(SYNTHETIC) - 1)

    def test_symlink_ancestor_hardlink_fifo_and_directory_fail_without_open(self):
        path = self.put('UNIT-ONLY.txt')
        link = self.root / 'symlink'
        link.symlink_to(path)
        ancestor = self.root / 'linked-parent'
        ancestor.symlink_to(self.root, target_is_directory=True)
        for target in (link, ancestor / path.name):
            with self.subTest(target=target), patch.object(lineage.os, 'open', side_effect=AssertionError('unsafe open')):
                with self.assertRaisesRegex(ValueError, 'no linked input'):
                    lineage.read(target)
        hard = self.root / 'hardlink'
        os.link(path, hard)
        fifo = self.root / 'fifo'
        os.mkfifo(fifo)
        for target in (path, hard, fifo, self.root):
            with self.subTest(target=target), patch.object(lineage.os, 'open', side_effect=AssertionError('unsafe open')):
                with self.assertRaisesRegex(ValueError, 'bounded ordinary input'):
                    lineage.read(target)

    def test_replace_after_lstat_is_rejected(self):
        path = self.put('UNIT-ONLY.txt')
        replacement = self.put('UNIT-ONLY-replacement.txt', b'different content')
        original_open = lineage.os.open
        def replace_then_open(target, *args, **kwargs):
            replacement.replace(path)
            return original_open(target, *args, **kwargs)
        with patch.object(lineage.os, 'open', side_effect=replace_then_open):
            with self.assertRaisesRegex(ValueError, 'replaced input'):
                lineage.read(path)


class OriginalStateNegativeTests(ScratchCase):
    def test_missing_state_inventory_fails_before_base_read_or_parse(self):
        with patch.object(lineage, 'obj', side_effect=AssertionError('parse before inventory')):
            with self.assertRaises(FileNotFoundError):
                lineage.build(self.root / 'base-absent', self.root / 'state-absent', self.root / 'inventory-absent', '0' * 64)

    def test_changed_state_inventory_fails_before_json_parse(self):
        inventory = self.put('UNIT-ONLY-inventory.json', b'not even JSON')
        with patch.object(lineage, 'obj', side_effect=AssertionError('parse before original inventory hash')):
            with self.assertRaisesRegex(ValueError, 'state inventory hash before parsing'):
                lineage.build(self.root / 'missing-base', self.root / 'missing-state', inventory, '0' * 64)

    def test_duplicate_state_inventory_fails_before_other_body_read(self):
        raw = b'{"UNIT-ONLY":1,"UNIT-ONLY":2}'
        inventory = self.put('UNIT-ONLY-inventory.json', raw)
        original_read = lineage.read
        seen = []
        def read_only_inventory(path, *args):
            seen.append(Path(path))
            self.assertEqual(Path(path), inventory)
            return original_read(path, *args)
        with patch.object(lineage, 'read', side_effect=read_only_inventory):
            with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                lineage.build(self.root / 'missing-base', self.root / 'missing-state', inventory, lineage.sha(raw))
        self.assertEqual(seen, [inventory])

    def test_missing_selected_roles_fail_before_base_or_state_read(self):
        raw = lineage.encoded({'UNIT-ONLY.txt': lineage.desc(SYNTHETIC)})
        inventory = self.put('UNIT-ONLY-inventory.json', raw)
        with self.assertRaisesRegex(ValueError, 'all13 original selected state'):
            lineage.build(self.root / 'missing-base', self.root / 'missing-state', inventory, lineage.sha(raw))

    def test_changed_selected_body_fails_before_parsing_or_finalizer_execution(self):
        base, state, inventory, digest, _, marker = self.negative_original_inputs()
        (state / lineage.STATE_NAMES[0]).write_bytes(b'changed and not JSON')
        with patch.object(lineage, '_check', side_effect=AssertionError('body parsed before hash')):
            with self.assertRaisesRegex(ValueError, 'authentic state body before parsing'):
                lineage.build(base, state, inventory, digest)
        self.assertFalse(marker.exists())

    def test_missing_selected_body_fails_without_lineage_or_output(self):
        base, state, inventory, digest, _, marker = self.negative_original_inputs()
        (state / lineage.STATE_NAMES[-1]).unlink()
        with patch.object(lineage, '_check', side_effect=AssertionError('incomplete original state admitted')):
            with self.assertRaises(FileNotFoundError):
                lineage.build(base, state, inventory, digest)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / 'LAUNCH-LINEAGE.json').exists())

    def test_self_consistent_synthetic_state_cannot_bypass_original_code18_pin(self):
        base, state, inventory, digest, _, marker = self.negative_original_inputs()
        with patch.object(lineage, 'obj', wraps=lineage.obj) as parse:
            with self.assertRaisesRegex(ValueError, 'original code18 inventory'):
                lineage.build(base, state, inventory, digest)
        # Only the synthetic state inventory was parsed; no receipt, manifest,
        # embedded path, or malicious finalizer body was executed or interpreted.
        self.assertEqual(parse.call_count, 2)
        self.assertTrue(all(call.args[0] == inventory.read_bytes() for call in parse.call_args_list))
        self.assertFalse(marker.exists())

    def test_negative_replay_never_opens_embedded_paths_or_zip_members(self):
        base, state, inventory, digest, _, marker = self.negative_original_inputs()
        allowed = {inventory, base / 'ASSEMBLY-INVENTORY.json',
                   *(base / n for n in lineage.BASE_NAMES), *(state / n for n in lineage.STATE_NAMES)}
        original_read = lineage.read
        observed = []
        def bounded_selected_read(path, *args, **kwargs):
            path = Path(path)
            self.assertIn(path, allowed)
            self.assertNotEqual(path, marker)
            observed.append(path)
            return original_read(path, *args, **kwargs)
        with patch.object(lineage, 'read', side_effect=bounded_selected_read), \
                patch.object(zipfile.ZipFile, 'open', side_effect=AssertionError('ZIP member read forbidden')), \
                patch.object(zipfile.ZipFile, 'read', side_effect=AssertionError('ZIP member read forbidden')), \
                patch.object(subprocess, 'run', side_effect=AssertionError('subprocess forbidden')):
            with self.assertRaisesRegex(ValueError, 'original code18 inventory'):
                lineage.build(base, state, inventory, digest)
        self.assertEqual(set(observed), allowed)
        self.assertFalse(marker.exists())

    def test_internal_replay_rejects_changed_inventory_before_parse(self):
        raw = {'ORIGINAL-STATE-INVENTORY.json': b'not JSON'}
        with patch.object(lineage, 'obj', side_effect=AssertionError('parse before original pin')):
            with self.assertRaisesRegex(ValueError, 'independently pinned original owner state inventory'):
                lineage._check(raw, self.root / 'missing', '0' * 64)


class SupplementNegativeTests(ScratchCase):
    def test_manifest_pin_precedes_parsing(self):
        self.put('LAUNCH-LINEAGE.json', b'not JSON')
        with patch.object(lineage, 'obj', side_effect=AssertionError('parse before supplement pin')):
            with self.assertRaisesRegex(ValueError, 'independently pinned launch supplement'):
                lineage.verify(self.root, '0' * 64)

    def test_supplement_identity_mutations_rejected_before_replay(self):
        bundle, original, _, _ = self.negative_supplement()
        for key, value in (('format', 'UNIT-ONLY-wrong'), ('status', 'REVIEW_REQUIRED'),
                           ('notebook_version', 36), ('code_version', 19),
                           ('code18_assembly_inventory_sha256', '0' * 64),
                           ('code18_publication_manifest_sha256', '0' * 64)):
            proof = copy.deepcopy(original)
            proof[key] = value
            digest = self.write_proof(bundle, proof)
            with self.subTest(key=key), patch.object(lineage, '_check', side_effect=AssertionError('bad identity replayed')):
                with self.assertRaisesRegex(ValueError, 'supplement exact identity'):
                    lineage.verify(bundle, digest)

    def test_extra_or_missing_declared_role_is_rejected(self):
        bundle, original, _, _ = self.negative_supplement()
        for change in ('extra', 'missing'):
            proof = copy.deepcopy(original)
            if change == 'extra':
                proof['closed_files']['UNIT-ONLY-extra.txt'] = lineage.desc(SYNTHETIC)
            else:
                proof['closed_files'].pop('state/' + lineage.STATE_NAMES[0])
            digest = self.write_proof(bundle, proof)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'closed original supplement roles'):
                lineage.verify(bundle, digest)

    def test_missing_or_unknown_physical_file_is_rejected(self):
        bundle, proof, _, _ = self.negative_supplement()
        digest = self.write_proof(bundle, proof)
        path = bundle / 'state' / lineage.STATE_NAMES[0]
        body = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'unknown or missing supplement body'):
            lineage.verify(bundle, digest)
        path.write_bytes(body)
        (bundle / 'UNIT-ONLY-extra.txt').write_bytes(SYNTHETIC)
        with self.assertRaisesRegex(ValueError, 'unknown or missing supplement body'):
            lineage.verify(bundle, digest)

    def test_corrupted_body_is_rejected_before_original_replay(self):
        bundle, proof, _, _ = self.negative_supplement()
        digest = self.write_proof(bundle, proof)
        (bundle / 'state' / lineage.STATE_NAMES[0]).write_bytes(b'changed')
        with patch.object(lineage, '_check', side_effect=AssertionError('body changed before replay')):
            with self.assertRaisesRegex(ValueError, 'supplement body integrity'):
                lineage.verify(bundle, digest)

    def test_symlink_hardlink_and_fifo_supplement_entries_rejected(self):
        bundle, proof, _, _ = self.negative_supplement()
        digest = self.write_proof(bundle, proof)
        bad = bundle / 'UNIT-ONLY-special'
        target = bundle / 'state' / lineage.STATE_NAMES[0]
        for kind in ('symlink', 'hardlink', 'fifo'):
            if kind == 'symlink':
                bad.symlink_to(target)
            elif kind == 'hardlink':
                os.link(target, bad)
            else:
                os.mkfifo(bad)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'supplement (symlink|special entry)'):
                lineage.verify(bundle, digest)
            bad.unlink()

    def test_unit_only_envelope_cannot_turn_fake_original_inputs_into_success(self):
        bundle, proof, _, marker = self.negative_supplement()
        digest = self.write_proof(bundle, proof)
        with patch.object(zipfile.ZipFile, 'open', side_effect=AssertionError('ZIP member forbidden')), \
                patch.object(zipfile.ZipFile, 'read', side_effect=AssertionError('ZIP member forbidden')):
            with self.assertRaisesRegex(ValueError, 'original code18 inventory'):
                lineage.verify(bundle, digest)
        self.assertFalse(marker.exists())

    def test_supplement_parent_symlink_rejected_before_body(self):
        bundle, proof, _, _ = self.negative_supplement()
        digest = self.write_proof(bundle, proof)
        alias = self.root / 'linked-supplement'
        alias.symlink_to(bundle, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'no linked input'):
            lineage.verify(alias, digest)


if __name__ == '__main__':
    unittest.main()

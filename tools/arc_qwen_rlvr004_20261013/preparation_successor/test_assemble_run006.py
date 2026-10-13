"""Offline run006 assembler tests; no provider, credentials, GPU or scoring.

Synthetic helper fixtures are explicitly UNIT-ONLY and are never submitted to
assembly as historical evidence. No successful full assembly is fabricated.
Real historical admission remains gated on the original complete code18 input.
All test writes, including isolated subprocess fixtures, stay below .irisx.
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
import unittest
from unittest.mock import patch

from tools.arc_qwen_rlvr004_20261013.preparation_successor import assemble_run006 as build

REPOSITORY = Path(__file__).resolve().parents[3]
PACKAGE = REPOSITORY / build.p.TOOL_REL
HERE = Path(__file__).resolve().parent
OFFLINE = {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0',
           'HF_HUB_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1',
           'TRANSFORMERS_OFFLINE': '1', 'WANDB_MODE': 'offline'}
SYNTHETIC = b'SYNTHETIC UNIT-ONLY BYTES; NOT HISTORICAL EVIDENCE\n'
SCRATCH = None
ENVIRONMENT_PATCH = None
NETWORK_PATCH = None
OLD_BYTECODE = None


def setUpModule():
    global SCRATCH, ENVIRONMENT_PATCH, NETWORK_PATCH, OLD_BYTECODE
    OLD_BYTECODE = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    parent = build.p.ordinary(REPOSITORY / '.irisx')
    parent.mkdir(exist_ok=True)
    SCRATCH = tempfile.TemporaryDirectory(dir=parent, prefix='run006-assembler-tests-')
    ENVIRONMENT_PATCH = patch.dict(os.environ, {**OFFLINE, 'TMPDIR': SCRATCH.name})
    ENVIRONMENT_PATCH.start()
    NETWORK_PATCH = patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden'))
    NETWORK_PATCH.start()


def tearDownModule():
    if NETWORK_PATCH is not None:
        NETWORK_PATCH.stop()
    if ENVIRONMENT_PATCH is not None:
        ENVIRONMENT_PATCH.stop()
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
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return target


class BoundedHelperTests(ScratchCase):
    def test_pinned_roundtrip_and_hash_rejection(self):
        path = self.put('UNIT-ONLY.txt')
        self.assertEqual(build.pinned(path, build.sha(SYNTHETIC)), SYNTHETIC)
        with self.assertRaisesRegex(ValueError, 'pinned input differs'):
            build.pinned(path, '0' * 64)

    def test_digest_schema_rejected_before_read(self):
        with patch.object(build, 'read', side_effect=AssertionError('read before digest check')):
            for digest in (None, 123, b'0' * 64, '', '0' * 63, '0' * 65, 'A' * 64, 'g' * 64):
                with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, 'exact SHA256'):
                    build.pinned(self.root / 'absent', digest)

    def test_pinned_cap_symlink_hardlink_and_fifo_rejected(self):
        path = self.put('UNIT-ONLY.txt')
        with self.assertRaisesRegex(ValueError, 'bounded regular input'):
            build.pinned(path, build.sha(SYNTHETIC), cap=1)
        link = self.root / 'symlink'
        link.symlink_to(path)
        with self.assertRaisesRegex(ValueError, 'linked or reparse'):
            build.pinned(link, build.sha(SYNTHETIC))
        hard = self.root / 'hardlink'
        os.link(path, hard)
        with self.assertRaisesRegex(ValueError, 'bounded regular input'):
            build.pinned(hard, build.sha(SYNTHETIC))
        fifo = self.root / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'bounded regular input'):
            build.pinned(fifo, build.sha(SYNTHETIC))

    def test_descriptor_strict_relative_names(self):
        self.assertEqual(build.descriptor(SYNTHETIC, 'unit/member.txt'),
                         {'path': 'unit/member.txt', **build.p.desc(SYNTHETIC)})
        for name in ('../escape', '/absolute', 'a//b', 'a/./b', 'a/../b', 'a\\b', 'a:b', 'a\nb', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                build.descriptor(SYNTHETIC, name)

    def test_closed_tree_roundtrip_and_explicit_inventory_sidecar(self):
        self.put('nested/UNIT-ONLY.txt')
        self.put('inventory.json', b'{}\n')
        inventory = {'nested/UNIT-ONLY.txt': build.p.desc(SYNTHETIC)}
        self.assertEqual(build.closed_files(self.root, inventory, extra=('inventory.json',)),
                         {'nested/UNIT-ONLY.txt': SYNTHETIC})

    def test_closed_tree_unknown_or_missing_member_rejected(self):
        path = self.put('UNIT-ONLY.txt')
        inventory = {path.name: build.p.desc(SYNTHETIC)}
        extra = self.put('unexpected.txt')
        with self.assertRaisesRegex(ValueError, 'path set differs'):
            build.closed_files(self.root, inventory)
        extra.unlink()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'path set differs'):
            build.closed_files(self.root, inventory)

    def test_closed_tree_descriptor_schema(self):
        self.put('UNIT-ONLY.txt')
        good = build.p.desc(SYNTHETIC)
        rows = ({}, [], {'bytes': True, 'sha256': good['sha256']},
                {**good, 'path': 'UNIT-ONLY.txt'}, {**good, 'bytes': -1},
                {**good, 'bytes': build.p.CAP + 1}, {**good, 'bytes': 1.0})
        for row in rows:
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, 'inventory descriptor schema'):
                build.closed_files(self.root, {'UNIT-ONLY.txt': row})
        for inventory in ({}, [], None):
            with self.subTest(inventory=inventory), self.assertRaisesRegex(ValueError, 'closed nonempty inventory'):
                build.closed_files(self.root, inventory)

    def test_closed_tree_unsafe_name_rejected_before_body_read(self):
        with patch.object(build, 'pinned', side_effect=AssertionError('body read too early')):
            for name in ('../escape', '/absolute', 'a//b', 'a:b', 'a\nb'):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unsafe relative name'):
                    build.closed_files(self.root, {name: build.p.desc(SYNTHETIC)})

    def test_closed_tree_digest_and_size_are_both_checked(self):
        self.put('UNIT-ONLY.txt')
        for row, message in (({'bytes': len(SYNTHETIC), 'sha256': '0' * 64}, 'pinned input differs'),
                             ({'bytes': len(SYNTHETIC) + 1, 'sha256': build.sha(SYNTHETIC)}, 'byte size differs')):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, message):
                build.closed_files(self.root, {'UNIT-ONLY.txt': row})

    def test_closed_tree_total_size_cap_precedes_body_reads(self):
        inventory = {}
        for i in range(5):
            name = f'UNIT-ONLY-{i}.txt'
            self.put(name, b'')
            inventory[name] = {'bytes': build.p.CAP, 'sha256': build.sha(b'')}
        with patch.object(build, 'pinned', side_effect=AssertionError('large inventory body read')):
            with self.assertRaisesRegex(ValueError, 'total cap'):
                build.closed_files(self.root, inventory)

    def test_closed_tree_rejects_special_objects_and_linked_directories(self):
        target = self.put('UNIT-ONLY.txt')
        inventory = {target.name: build.p.desc(SYNTHETIC)}
        bad = self.root / 'bad'
        for kind in ('symlink', 'hardlink', 'fifo', 'directory-symlink'):
            with self.subTest(kind=kind):
                if kind == 'symlink':
                    bad.symlink_to(target)
                elif kind == 'hardlink':
                    os.link(target, bad)
                elif kind == 'fifo':
                    os.mkfifo(bad)
                else:
                    bad.symlink_to(self.root, target_is_directory=True)
                with self.assertRaises(ValueError):
                    build.closed_files(self.root, inventory)
                bad.unlink()

    def test_output_is_exclusive_private_and_roundtrips(self):
        output = self.root / 'output'
        files = {'nested/UNIT-ONLY.txt': SYNTHETIC, 'empty.txt': b''}
        build.write_output(output, files)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((output / 'nested').stat().st_mode), 0o700)
        for name, raw in files.items():
            self.assertEqual((output / name).read_bytes(), raw)
            self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o600)
        with self.assertRaisesRegex(ValueError, 'fresh assembly output'):
            build.write_output(output, {'nested/UNIT-ONLY.txt': b'overwrite'})
        self.assertEqual((output / 'nested/UNIT-ONLY.txt').read_bytes(), SYNTHETIC)

    def test_output_rejects_traversal_and_linked_ancestor(self):
        output = self.root / 'output'
        with self.assertRaisesRegex(ValueError, 'unsafe relative name'):
            build.write_output(output, {'../escape.txt': SYNTHETIC})
        self.assertFalse((self.root / 'escape.txt').exists())
        link = self.root / 'linked'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked or reparse'):
            build.write_output(link / 'uncreated', {'UNIT-ONLY.txt': SYNTHETIC})
        self.assertFalse((self.root / 'uncreated').exists())


class ExactSourceProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Actual frozen source bytes only. This object is deliberately NOT a
        # complete historical candidate and never enters authenticated_base.
        cls.root = Path(SCRATCH.name) / 'actual-source-only'
        cls.snapshot = build.p.Snapshot(REPOSITORY)
        cls.assembler = build.p.load_module(cls.snapshot.tool('prepare_successor_release.py'),
            'run006_unit_exact_source_primitives', PACKAGE / 'prepare_successor_release.py')
        cls.old = build.p.frozen_runtime(cls.snapshot, cls.assembler)
        cls.source_only_base = {'producer-source/' + n: b for n, b in cls.old.items()}
        installer = PACKAGE / 'installer_logging_repair'
        review = installer / 'REVIEW.json'
        cls.result = build.p.prepare(repository_root=REPOSITORY,
            identity_path=HERE / 'proposed-identity.json', output_root=cls.root,
            installer_overlay_path=installer / 'bootstrap.py',
            installer_overlay_sha='20aca4d463da2cec7dd0128dab1582cc009931666139f75f87fbbec9d1ba35b4',
            installer_review_path=review, installer_review_sha=build.sha(build.read(review)))

    def test_exact_reviewed_installer_proposal_and_source_only_delta(self):
        self.assertEqual(self.result['proposal_inventory_sha256'], build.SOURCE_PROPOSAL_INVENTORY)
        files, source, deployment, proposal = build.source_inputs(self.root, self.source_only_base, self.assembler)
        self.assertEqual(len(source), 259)
        self.assertEqual({n for n in source if source[n] != self.old[n]},
                         {build.p.INSTALLER_TARGET, 'owned_runtime/release.py'})
        self.assertEqual(sum(source[n] == self.old[n] for n in source), 257)
        self.assertEqual(sum(source[n] == self.old[n] for n in source if n.startswith('baseline/')), 199)
        self.assertFalse(proposal['production_admitted'])
        self.assertFalse(proposal['original_baseline200_exact'])
        self.assertIsNone(proposal['successor_epoch'])
        self.assertEqual(build.sha(files['source.zip']), build.ARCHIVE_SHA)
        self.assertEqual({n: build.p.desc(b) for n, b in deployment.items()}, proposal['deployment'])

    def test_source_projection_rejects_changed_missing_or_additional_original_runtime(self):
        variants = []
        changed = dict(self.source_only_base)
        changed['producer-source/design/MEASURED-POLICY.json'] += b'\n'
        variants.append(changed)
        missing = dict(self.source_only_base)
        missing.pop('producer-source/design/MEASURED-POLICY.json')
        variants.append(missing)
        extra = dict(self.source_only_base)
        extra['producer-source/UNIT-ONLY-extra.txt'] = SYNTHETIC
        variants.append(extra)
        for base in variants:
            with self.subTest(count=len(base)), self.assertRaises(ValueError):
                build.source_inputs(self.root, base, self.assembler)

    def test_source_only_reconstruction_cannot_pass_original_candidate_gate(self):
        with self.assertRaises(FileNotFoundError):
            build.authenticated_base(self.snapshot, self.root)

    def test_diagnostics_only_proposal_is_not_accepted_as_installer_variant(self):
        root = Path(SCRATCH.name) / 'actual-diagnostics-only'
        build.p.prepare(repository_root=REPOSITORY, identity_path=HERE / 'proposed-identity.json', output_root=root)
        with self.assertRaisesRegex(ValueError, 'pinned input differs'):
            build.source_inputs(root, self.source_only_base, self.assembler)


class FinalReviewBindingTests(ScratchCase):
    """SYNTHETIC UNIT-ONLY schema tests; never historical or assembly inputs."""
    def setUp(self):
        super().setUp()
        self.proposal = {'format': build.PROPOSAL_FORMAT, 'synthetic_unit_fixture_only': True,
                         **{key: 'UNIT-ONLY-' + key for key in build.BINDING_KEYS}}
        self.proposal['deployment_inventory'] = {'UNIT-ONLY.py': build.p.desc(SYNTHETIC)}
        self.old_material = {'dataset_content_sha256': {'UNIT-ONLY': 'a' * 64},
                             'dataset_escrow_sha256': {'UNIT-ONLY': 'b' * 64}}
        self.runtime = {'format': 'irisx/run006-runtime-review-v1', 'status': 'PASS',
                        'synthetic_unit_fixture_only': True, 'baseline_unchanged_members': 199,
                        'production_GPU_validation_passed': False,
                        **{key: self.proposal[key] for key in build.BINDING_KEYS}}
        self.material = {'format': 'owned-rl-reviewed-material-v1', 'status': 'APPROVED',
                         'synthetic_unit_fixture_only': True, 'baseline_unchanged_members': 199,
                         'production_GPU_validation_passed': False, **copy.deepcopy(self.old_material),
                         **{key: self.proposal[key] for key in build.BINDING_KEYS}}

    def arguments(self):
        proposal_raw = build.encoded(self.proposal)
        proposal_sha = build.sha(proposal_raw)
        self.runtime['proposal_sha256'] = proposal_sha
        runtime_raw = build.encoded(self.runtime)
        runtime_sha = build.sha(runtime_raw)
        self.material['proposal_sha256'] = proposal_sha
        self.material['runtime_review_sha256'] = runtime_sha
        material_raw = build.encoded(self.material)
        return {'proposal_path': self.put('UNIT-ONLY-proposal.json', proposal_raw), 'proposal_sha': proposal_sha,
                'runtime_review_path': self.put('UNIT-ONLY-runtime-review.json', runtime_raw), 'runtime_review_sha': runtime_sha,
                'material_review_path': self.put('UNIT-ONLY-material-review.json', material_raw), 'material_review_sha': build.sha(material_raw),
                'old_material': self.old_material}

    def test_unit_only_exact_review_roundtrip_emits_no_candidate(self):
        args = self.arguments()
        actual = build.final_reviews(self.proposal, **args)
        self.assertEqual(actual, (args['runtime_review_path'].read_bytes(), args['material_review_path'].read_bytes()))
        self.assertFalse((self.root / 'publication-manifest.json').exists())
        self.assertFalse((self.root / 'ASSEMBLY-INVENTORY.json').exists())

    def test_every_runtime_and_material_binding_is_mandatory(self):
        for name in ('runtime', 'material'):
            for key in build.BINDING_KEYS:
                with self.subTest(review=name, key=key):
                    original = copy.deepcopy(getattr(self, name))
                    getattr(self, name)[key] = 'UNIT-ONLY-WRONG'
                    args = self.arguments()
                    with self.assertRaisesRegex(ValueError, 'reviewed input binding differs: ' + key):
                        build.final_reviews(self.proposal, **args)
                    setattr(self, name, original)

    def test_bound_proposal_is_compared_byte_for_byte(self):
        args = self.arguments()
        changed = args['proposal_path'].read_bytes() + b'\n'
        args['proposal_path'].write_bytes(changed)
        args['proposal_sha'] = build.sha(changed)
        with self.assertRaisesRegex(ValueError, 'exact independently reviewed proposal'):
            build.final_reviews(self.proposal, **args)

    def test_changing_collector_after_proposal_requires_new_exact_review(self):
        args = self.arguments()
        changed = copy.deepcopy(self.proposal)
        changed['collector_sha256'] = 'UNIT-ONLY-CHANGED-COLLECTOR'
        with self.assertRaisesRegex(ValueError, 'exact independently reviewed proposal'):
            build.final_reviews(changed, **args)
        # Merely resealing the changed proposal cannot make the old review bind.
        raw = build.encoded(changed)
        args['proposal_path'].write_bytes(raw)
        args['proposal_sha'] = build.sha(raw)
        with self.assertRaisesRegex(ValueError, 'independent runtime review'):
            build.final_reviews(changed, **args)

    def test_exact_runtime_and_material_file_hashes_required(self):
        for key in ('runtime_review_sha', 'material_review_sha', 'proposal_sha'):
            with self.subTest(key=key):
                args = self.arguments()
                args[key] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'pinned input differs'):
                    build.final_reviews(self.proposal, **args)

    def test_runtime_status_and_format_must_be_independent_review(self):
        for key, value in (('status', 'REVIEW_REQUIRED'), ('format', 'other')):
            old = self.runtime[key]
            self.runtime[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'independent runtime review'):
                build.final_reviews(self.proposal, **self.arguments())
            self.runtime[key] = old

    def test_material_status_and_format_must_be_approved(self):
        for key, value in (('status', 'REVIEW_REQUIRED'), ('format', 'other')):
            old = self.material[key]
            self.material[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'independent material review'):
                build.final_reviews(self.proposal, **self.arguments())
            self.material[key] = old

    def test_original_semantic_and_escrow_commitments_cannot_change(self):
        for key in ('dataset_content_sha256', 'dataset_escrow_sha256'):
            original = copy.deepcopy(self.material[key])
            self.material[key] = {'UNIT-ONLY': '0' * 64}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'original dataset semantic/escrow'):
                build.final_reviews(self.proposal, **self.arguments())
            self.material[key] = original

    def test_baseline200_and_gpu_success_claims_are_rejected(self):
        for name in ('runtime', 'material'):
            for key, value in (('baseline_unchanged_members', 200), ('production_GPU_validation_passed', True),
                               ('production_GPU_validation_passed', 0), ('production_GPU_validation_passed', None)):
                original = copy.deepcopy(getattr(self, name))
                getattr(self, name)[key] = value
                with self.subTest(review=name, key=key, value=value), self.assertRaisesRegex(ValueError, 'honest baseline199'):
                    build.final_reviews(self.proposal, **self.arguments())
                setattr(self, name, original)


class AuthenticInputNegativeTests(ScratchCase):
    def assembly_arguments(self):
        return {'repository_root': REPOSITORY, 'base_root': self.root / 'missing-authentic-code18',
                'source_proposal_root': self.root / 'source-proposal', 'observation_root': self.root / 'observation',
                'observation_sha': build.OBSERVATION_SHA, 'stop_attestation_path': self.root / 'stop.json',
                'stop_attestation_sha': build.STOP_ATTESTATION_SHA, 'solver_path': self.root / 'solver.json',
                'new_solver_path': self.root / 'new-solver.json', 'solver_review_path': self.root / 'solver-review.json',
                'solver_review_sha': '0' * 64, 'collector_path': self.root / 'collector.py', 'collector_sha': '0' * 64,
                'output_root': self.root / 'uncreated-output', 'mode': 'proposal'}

    def test_missing_real_predecessor_fails_before_source_or_output(self):
        args = self.assembly_arguments()
        with patch.object(build, 'source_inputs', side_effect=AssertionError('historical gate bypassed')):
            with self.assertRaises(FileNotFoundError):
                build.assemble(**args)
        self.assertFalse(args['output_root'].exists())

    def test_caller_pass_documents_do_not_bypass_missing_authentic_predecessor(self):
        args = self.assembly_arguments()
        args['mode'] = 'final'
        args.update(v35_state_root=self.root / 'missing-original-v35',
                    v35_state_inventory_path=self.root / 'missing-original-v35-inventory.json',
                    v35_state_inventory_sha='0' * 64)
        for role, status in (('proposal', 'INDEPENDENT_REVIEW_REQUIRED'),
                             ('runtime_review', 'PASS'), ('material_review', 'APPROVED')):
            raw = build.encoded({'synthetic_unit_fixture_only': True, 'status': status})
            args[role + '_path'] = self.put('UNIT-ONLY-' + role + '.json', raw)
            args[role + '_sha'] = build.sha(raw)
        with patch.object(build, 'final_reviews', side_effect=AssertionError('base gate bypassed')), \
                patch.object(build, 'source_inputs', side_effect=AssertionError('base gate bypassed')), \
                patch.object(build, 'write_output', side_effect=AssertionError('output before original evidence')):
            with self.assertRaises(FileNotFoundError):
                build.assemble(**args)
        self.assertFalse(args['output_root'].exists())

    def test_synthetic_inventory_never_satisfies_original_code18(self):
        root = self.root / 'UNIT-ONLY-not-a-predecessor'
        root.mkdir()
        (root / 'ASSEMBLY-INVENTORY.json').write_bytes(build.encoded({'UNIT-ONLY.txt': build.p.desc(SYNTHETIC)}))
        (root / 'UNIT-ONLY.txt').write_bytes(SYNTHETIC)
        with patch.object(build, 'closed_files', side_effect=AssertionError('original checksum bypassed')):
            with self.assertRaisesRegex(ValueError, 'exact code18 assembly inventory'):
                build.authenticated_base(build.p.Snapshot(REPOSITORY), root)

    def test_final_mode_requires_reviews_before_any_repository_access(self):
        args = self.assembly_arguments()
        args['mode'] = 'final'
        with patch.object(build.p, 'Snapshot', side_effect=AssertionError('read before review gate')):
            with self.assertRaisesRegex(ValueError, 'independent exact proposal/runtime/material'):
                build.assemble(**args)
        self.assertFalse(args['output_root'].exists())

    def test_final_original_v35_state_is_mandatory_before_repository_access(self):
        for omitted in ('all', 'v35_state_root', 'v35_state_inventory_path', 'v35_state_inventory_sha'):
            args = self.assembly_arguments()
            args['mode'] = 'final'
            for role in ('proposal', 'runtime_review', 'material_review'):
                args[role + '_path'] = self.root / ('UNIT-ONLY-absent-' + role)
                args[role + '_sha'] = '0' * 64
            if omitted != 'all':
                args.update(v35_state_root=self.root / 'missing-original-v35',
                            v35_state_inventory_path=self.root / 'missing-original-v35-inventory.json',
                            v35_state_inventory_sha='0' * 64)
                args.pop(omitted)
            with self.subTest(omitted=omitted), \
                    patch.object(build.p, 'Snapshot', side_effect=AssertionError('read before original-state gate')):
                with self.assertRaisesRegex(ValueError, 'original v35 state and independently pinned inventory'):
                    build.assemble(**args)
            self.assertFalse(args['output_root'].exists())

    def test_proposal_v35_state_arguments_are_all_or_none(self):
        names = ('v35_state_root', 'v35_state_inventory_path', 'v35_state_inventory_sha')
        values = (self.root / 'missing-original-v35', self.root / 'missing-original-inventory.json', '0' * 64)
        for mask in range(1, 7):
            args = self.assembly_arguments()
            args.update({name: value for bit, (name, value) in enumerate(zip(names, values)) if mask & (1 << bit)})
            with self.subTest(mask=mask), patch.object(build.p, 'Snapshot', side_effect=AssertionError('partial-state read')):
                with self.assertRaisesRegex(ValueError, 'all original-v35 state inputs required together'):
                    build.assemble(**args)
            self.assertFalse(args['output_root'].exists())

    def test_v35_state_root_cannot_overlap_output(self):
        for direction in ('output-inside-state', 'state-inside-output'):
            args = self.assembly_arguments()
            args.update(v35_state_root=self.root / 'missing-original-v35',
                        v35_state_inventory_path=self.root / 'missing-original-inventory.json',
                        v35_state_inventory_sha='0' * 64)
            if direction == 'output-inside-state':
                args['output_root'] = args['v35_state_root'] / 'output'
            else:
                args['v35_state_root'] = args['output_root'] / 'state'
            with self.subTest(direction=direction), patch.object(build.p, 'Snapshot', side_effect=AssertionError('overlap read')):
                with self.assertRaisesRegex(ValueError, 'input/output overlap'):
                    build.assemble(**args)
            self.assertFalse(args['output_root'].exists())

    def test_lineage_source_and_both_final_reviews_bind_original_state(self):
        self.assertEqual(build.sha(build.read(HERE / 'v35_lineage.py')), build.LINEAGE_HELPER_SHA)
        self.assertTrue({'v35_original_dispatch_chain_sha256', 'v35_state_inventory_sha256',
                         'v35_launch_lineage_verifier_sha256'} <= set(build.BINDING_KEYS))

    def test_unknown_mode_and_output_outside_scratch_rejected(self):
        args = self.assembly_arguments()
        args['mode'] = 'preview'
        with self.assertRaisesRegex(ValueError, 'proposal or final mode'):
            build.assemble(**args)
        args['mode'] = 'proposal'
        args['output_root'] = REPOSITORY / 'NEVER-CREATE-UNIT-ONLY'
        with self.assertRaisesRegex(ValueError, 'fresh ignored assembly output'):
            build.assemble(**args)
        self.assertFalse(args['output_root'].exists())

    def test_input_output_overlap_is_rejected_before_snapshot(self):
        for field in ('base_root', 'source_proposal_root', 'observation_root'):
            for direction in ('output-inside-input', 'input-inside-output'):
                args = self.assembly_arguments()
                if direction == 'output-inside-input':
                    args['output_root'] = args[field] / 'output'
                else:
                    args[field] = args['output_root'] / 'input'
                with self.subTest(field=field, direction=direction), \
                        patch.object(build.p, 'Snapshot', side_effect=AssertionError('overlap read')), \
                        self.assertRaisesRegex(ValueError, 'input/output overlap'):
                    build.assemble(**args)
                self.assertFalse(args['output_root'].exists())

    def test_synthetic_solver_cannot_reach_projection_or_review(self):
        old = self.put('UNIT-ONLY-solver.json', build.encoded({'synthetic_unit_fixture_only': True}))
        with patch.object(build.p, 'project_solver', side_effect=AssertionError('unauthenticated solver projected')):
            with self.assertRaisesRegex(ValueError, 'pinned input differs'):
                build.solver_inputs({}, old, self.root / 'new-missing', self.root / 'review-missing', '0' * 64)

    def test_observation_and_owner_attestation_use_distinct_exact_pins(self):
        with patch.object(build, 'pinned', side_effect=AssertionError('nonreviewed packet read')):
            for digest in ('0' * 64, build.STOP_ATTESTATION_SHA):
                with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, 'exact independently observed'):
                    build.observation_inputs(self.root, digest)
            for digest in ('0' * 64, build.OBSERVATION_SHA):
                with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, 'exact owner attestation'):
                    build.stop_attestation(self.root / 'absent', digest)


class StandaloneDependencyTests(ScratchCase):
    def copied_module(self):
        self.put('assemble_run006.py', build.read(HERE / 'assemble_run006.py'))
        return self.root / 'assemble_run006.py'

    def launch(self, module, *, optimized=False, prefix=''):
        code = prefix + '\nimport runpy\nrunpy.run_path(' + repr(str(module)) + ', run_name="unit_only_no_main")\n'
        return subprocess.run([sys.executable, *(['-O'] if optimized else []), '-B', '-c', code],
                              cwd=REPOSITORY, env={**os.environ, **OFFLINE},
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=30, check=False)

    def test_corrupt_dependency_fails_before_sentinel_exec_normal_and_optimized(self):
        module = self.copied_module()
        marker = self.root / 'MUST-NOT-EXIST'
        self.put('prepare.py', ('from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("executed")\n').encode())
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                proc = self.launch(module, optimized=optimized)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(b'reviewed preparation dependency hash differs', proc.stderr)
                self.assertFalse(marker.exists())

    def test_dependency_cannot_be_bypassed_by_existing_module_cache(self):
        module = self.copied_module()
        self.put('prepare.py', SYNTHETIC)
        prefix = ('import sys, types\n'
                  'sys.modules["prepare"] = types.ModuleType("prepare")\n'
                  'sys.modules["run006_pinned_source_preparation"] = types.ModuleType("run006_pinned_source_preparation")\n')
        proc = self.launch(module, prefix=prefix)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b'reviewed preparation dependency hash differs', proc.stderr)

    def test_authentic_dependency_import_has_no_external_execution(self):
        module = self.copied_module()
        self.put('prepare.py', build.read(HERE / 'prepare.py'))
        prefix = ('import socket, subprocess\n'
                  'def forbidden(*args, **kwargs):\n    raise RuntimeError("external execution forbidden")\n'
                  'socket.create_connection = forbidden\nsubprocess.run = forbidden\n')
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                proc = self.launch(module, optimized=optimized, prefix=prefix)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode())
                self.assertEqual(proc.stdout, b'')
        self.assertFalse((self.root / '__pycache__').exists())

    def test_linked_or_hardlinked_dependency_rejected(self):
        module = self.copied_module()
        good = self.put('actual-prepare.py', build.read(HERE / 'prepare.py'))
        dependency = self.root / 'prepare.py'
        dependency.symlink_to(good)
        proc = self.launch(module)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b'unsafe reviewed preparation dependency', proc.stderr)
        dependency.unlink()
        os.link(good, dependency)
        proc = self.launch(module)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b'bounded reviewed preparation dependency', proc.stderr)


class AvailableRealObservationTests(ScratchCase):
    """Optional genuine local transfer checks, never synthesized when absent."""
    def setUp(self):
        super().setUp()
        self.original = REPOSITORY.parent / 'provider-session/current-predecessor-v35'
        self.attestation = REPOSITORY.parent / 'provider-session/OWNER-SESSION-STOP-ATTESTATION.json'
        if not self.original.is_dir() or not self.attestation.is_file():
            self.skipTest('Original read-only v35 observation/owner packets are not transferred here; no fixture substituted')

    def test_real_observation_and_owner_attestation_remain_separate_qualified_evidence(self):
        files = build.observation_inputs(self.original, build.OBSERVATION_SHA)
        raw = build.stop_attestation(self.attestation, build.STOP_ATTESTATION_SHA)
        self.assertEqual(len(files), 31)
        doc = build.obj(files['current-predecessor-v35/OBSERVATION.json'])
        self.assertEqual(doc['status'], 'CANCEL_ACKNOWLEDGED_DIAGNOSTICS_UNAVAILABLE')
        self.assertEqual(doc['original_epoch'], build.p.OLD_EPOCH)
        self.assertEqual(doc['original_deadline'], build.p.OLD_DEADLINE)
        for key in ('runtime_closure_verified', 'manual_editor_session_mapping_verified',
                    'manual_failure_root_cause_verified', 'physical_costs_known', 'scientific_result_verified'):
            self.assertIs(doc[key], False)
        owner = build.obj(raw)
        self.assertIs(owner['owner_attested_manual_editor_stopped'], True)
        self.assertIs(owner['runtime_or_model_closure_verified'], False)
        self.assertIs(owner['provider_session_mapping_verified'], False)
        self.assertIs(owner['costs_or_billing_verified'], False)
        self.assertNotEqual(build.sha(raw), build.OBSERVATION_SHA)

    def test_actual_observation_missing_body_or_unknown_member_rejected(self):
        files = build.observation_inputs(self.original, build.OBSERVATION_SHA)
        local = self.root / 'observation-copy'
        local.mkdir()
        for name, raw in files.items():
            path = local / name.removeprefix('current-predecessor-v35/')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        member = local / 'saved_source.ipynb'
        saved = member.read_bytes()
        member.unlink()
        with self.assertRaisesRegex(ValueError, 'closed inventory path set differs'):
            build.observation_inputs(local, build.OBSERVATION_SHA)
        member.write_bytes(saved)
        (local / 'UNIT-ONLY-extra.txt').write_bytes(SYNTHETIC)
        with self.assertRaisesRegex(ValueError, 'closed inventory path set differs'):
            build.observation_inputs(local, build.OBSERVATION_SHA)

    def test_current_observation_or_owner_claim_cannot_be_promoted_by_rehash(self):
        observed = build.obj(build.read(self.original / 'OBSERVATION.json'))
        observed['runtime_closure_verified'] = True
        changed = self.put('OBSERVATION.json', build.encoded(observed))
        with self.assertRaisesRegex(ValueError, 'pinned input differs'):
            build.observation_inputs(self.root, build.OBSERVATION_SHA)
        with self.assertRaisesRegex(ValueError, 'exact independently observed'):
            build.observation_inputs(self.root, build.sha(changed.read_bytes()))
        owner = build.obj(build.read(self.attestation))
        owner['runtime_or_model_closure_verified'] = True
        changed = self.put('UNIT-ONLY-changed-owner.json', build.encoded(owner))
        with self.assertRaisesRegex(ValueError, 'pinned input differs'):
            build.stop_attestation(changed, build.STOP_ATTESTATION_SHA)
        with self.assertRaisesRegex(ValueError, 'exact owner attestation'):
            build.stop_attestation(changed, build.sha(changed.read_bytes()))


if __name__ == '__main__':
    unittest.main()

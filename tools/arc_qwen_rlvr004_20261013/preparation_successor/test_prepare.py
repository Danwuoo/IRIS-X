"""Offline source-proposal regressions; no provider, model or scoring execution.

Real frozen repository inputs are authenticated. All generated files and hostile
path fixtures stay below .irisx. Missing historical evidence is never invented;
negative predecessor tests establish rejection, not production admission.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
import copy
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.arc_qwen_rlvr004_20261013.preparation_successor import prepare as build


REPOSITORY = Path(__file__).resolve().parents[3]
PACKAGE = REPOSITORY / build.TOOL_REL
IDENTITY = PACKAGE / 'preparation_successor/proposed-identity.json'
DIAGNOSTICS = PACKAGE / 'preparation_diagnostics_repair'
OFFLINE = {
    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0',
    'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
    'HF_DATASETS_OFFLINE': '1', 'WANDB_MODE': 'offline',
}
SCRATCH = None
ENVIRONMENT_PATCH = None
OLD_BYTECODE = None


def setUpModule():
    global SCRATCH, ENVIRONMENT_PATCH, OLD_BYTECODE
    OLD_BYTECODE = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    parent = build.ordinary(REPOSITORY / '.irisx')
    parent.mkdir(exist_ok=True)
    SCRATCH = tempfile.TemporaryDirectory(dir=parent, prefix='source-preparation-tests-')
    ENVIRONMENT_PATCH = patch.dict(os.environ, {**OFFLINE, 'TMPDIR': SCRATCH.name})
    ENVIRONMENT_PATCH.start()


def tearDownModule():
    if ENVIRONMENT_PATCH is not None:
        ENVIRONMENT_PATCH.stop()
    if SCRATCH is not None:
        SCRATCH.cleanup()
    if OLD_BYTECODE is not None:
        sys.dont_write_bytecode = OLD_BYTECODE


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


class SourceProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(SCRATCH.name)
        cls.outputs = [cls.root / 'first', cls.root / 'different-parent/second']
        cls.git_calls = []
        original_run = subprocess.run

        def read_only_git(args, **kwargs):
            # Fail if source preparation adds a provider command or Git write.
            if (args[:3] != ['git', '-C', str(REPOSITORY)]
                    or args[3:] not in ([ 'cat-file', '-p', build.SNAPSHOT ],
                                       [ 'ls-tree', '-rz', '--full-tree', build.SNAPSHOT ])):
                raise AssertionError('unexpected subprocess: ' + repr(args))
            cls.git_calls.append(args)
            return original_run(args, **kwargs)

        with patch.object(build.subprocess, 'run', side_effect=read_only_git), \
                patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')):
            cls.results = [build.prepare(repository_root=REPOSITORY, identity_path=IDENTITY,
                                         output_root=output) for output in cls.outputs]
        cls.artifacts = tree_bytes(cls.outputs[0])
        cls.proposal = build.obj(cls.artifacts['SOURCE-PROPOSAL.json'])
        cls.release = build.obj(cls.artifacts['review-only-release.json'])
        cls.snapshot = build.Snapshot(REPOSITORY)
        cls.assembler = build.load_module(cls.snapshot.tool('prepare_successor_release.py'),
            'successor_preparation_test_frozen_assembler', PACKAGE / 'prepare_successor_release.py')
        cls.old = build.frozen_runtime(cls.snapshot, cls.assembler)
        cls.source = {name.removeprefix('producer-source/'): raw
                      for name, raw in cls.artifacts.items() if name.startswith('producer-source/')}
        cls.space = cls.proposal['namespaces']

    def scratch(self, prefix):
        value = tempfile.TemporaryDirectory(dir=self.root, prefix=prefix)
        self.addCleanup(value.cleanup)
        return Path(value.name)

    def test_two_different_output_directories_have_identical_bytes(self):
        self.assertEqual(self.artifacts, tree_bytes(self.outputs[1]))
        left, right = (dict(result) for result in self.results)
        self.assertNotEqual(left.pop('output_root'), right.pop('output_root'))
        self.assertEqual(left, right)
        self.assertEqual(len(self.git_calls), 4)

    def test_complete_inventory_hashes_every_output_and_no_extra_files(self):
        raw = self.artifacts['PROPOSAL-INVENTORY.json']
        inventory = build.obj(raw)
        self.assertEqual(set(inventory), set(self.artifacts) - {'PROPOSAL-INVENTORY.json'})
        self.assertEqual(build.sha(raw), self.results[0]['proposal_inventory_sha256'])
        for name, descriptor in inventory.items():
            with self.subTest(name=name):
                self.assertEqual(descriptor, build.desc(self.artifacts[name]))
        for output in self.outputs:
            for path in output.rglob('*'):
                self.assertFalse(path.is_symlink())
                if path.is_file():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_exact_original259_new259_baseline200_and_258_unchanged(self):
        self.assertEqual(len(self.old), 259)
        self.assertEqual(set(self.old), set(self.source))
        changed = {name for name in self.old if self.old[name] != self.source[name]}
        self.assertEqual(changed, {'owned_runtime/release.py'})
        self.assertEqual(sum(self.old[n] == self.source[n] for n in self.old), 258)
        baseline = [name for name in self.old if name.startswith('baseline/')]
        self.assertEqual(len(baseline), 200)
        self.assertTrue(all(self.old[n] == self.source[n] for n in baseline))
        self.assertEqual(build.sha(build.canonical(sorted((n, build.sha(b))
                         for n, b in self.old.items()))), build.SOURCE_SHA)
        self.assertEqual(build.sha(self.assembler.zip_blobs(self.old, stored=True)), build.ARCHIVE_SHA)

    def test_only_two_release_hash_assignments_change(self):
        def without_pins(raw):
            return re.sub(rb"(?m)^(REVIEWED_ENVIRONMENT_SHA256|NORMALIZED_SOURCE_CONTRACT_SHA256) = '[0-9a-f]{64}'$",
                          rb'\1 = None', raw)
        self.assertEqual(without_pins(self.old['owned_runtime/release.py']),
                         without_pins(self.source['owned_runtime/release.py']))
        normalized = dict(self.source)
        normalized['owned_runtime/release.py'] = re.sub(
            rb"(?m)^NORMALIZED_SOURCE_CONTRACT_SHA256 = '[0-9a-f]{64}'$",
            b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None', normalized['owned_runtime/release.py'])
        logical = build.sha(build.canonical(sorted((n, build.sha(b)) for n, b in normalized.items())))
        self.assertEqual(logical, self.proposal['normalized_source_contract_sha256'])
        self.assertIn(self.proposal['environment_sha256'].encode(), self.source['owned_runtime/release.py'])

    def test_deterministic_zip_matches_every_materialized_source_member(self):
        archive = self.artifacts['source.zip']
        self.assertEqual(build.sha(archive), self.proposal['source_archive_sha256'])
        self.assertEqual(archive, self.assembler.zip_blobs(self.source, stored=True))
        with zipfile.ZipFile(io.BytesIO(archive)) as stream:
            self.assertEqual(stream.namelist(), sorted(self.source))
            self.assertEqual(len(set(stream.namelist())), 259)
            for item in stream.infolist():
                self.assertEqual(item.date_time, (2026, 10, 12, 0, 0, 0))
                self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(stream.read(item), self.source[item.filename])
        freeze = build.obj(self.artifacts['SOURCE-FREEZE.json'])
        self.assertEqual(freeze['files'], {n: build.desc(b) for n, b in self.source.items()})
        self.assertFalse(freeze['production_admitted'])

    def test_environment_namespace_projection_reverses_to_exact_original_bytes(self):
        original_raw = self.snapshot.tool('driver_path_repair/environment-run005.json')
        original = build.obj(original_raw)
        updated = build.obj(self.artifacts['release/REVIEWED-ENVIRONMENT.json'])
        changed = {k for k in original['model_config']
                   if original['model_config'][k] != updated['model_config'][k]}
        self.assertEqual(changed, {'contract_path', 'environment_lock_path', 'tokenizer_path'})
        for key in changed:
            self.assertTrue(updated['model_config'][key].startswith(self.space['source'] + '/runtime/'))
            updated['model_config'][key] = updated['model_config'][key].replace(self.space['source'], build.OLD_SOURCE)
        self.assertEqual(build.encoded(updated), original_raw)
        self.assertEqual(build.sha(original_raw), build.ENVIRONMENT_SHA)

    def test_deployment_namespace_reversal_and_independent_overlay_pins(self):
        base = {'code-payload/deployment/' + name: self.snapshot.tool('support/deployment/' + name)
                for name in self.assembler.DEPLOYMENT_NAMES}
        base['assembly/verify_parent_wrappers.py'] = self.snapshot.tool('support/assembly/verify_parent_wrappers.py')
        predecessor, wrappers = self.assembler.derive_deployment(base)
        self.assertEqual(self.proposal['predecessor_deployment'],
                         {name: build.desc(raw) for name, raw in predecessor.items()})
        for name in self.assembler.DEPLOYMENT_NAMES:
            raw = self.artifacts['deployment/' + name]
            for new, old in ((self.space['run'], build.OLD_RUN),
                             (self.space['source'], build.OLD_SOURCE),
                             (self.space['environment'], build.OLD_ENVIRONMENT)):
                self.assertNotIn(old.encode(), raw)
                raw = raw.replace(new.encode(), old.encode())
            if name == 'source_loader.py':
                raw = raw.replace((self.assembler.DREF + '/19').encode(),
                                  (self.assembler.DREF + '/18').encode())
            if name == 'launch_notebook.py':
                raw = raw.replace(b'exact fresh successor run/source paths required',
                                  b'exact run005/source005 paths required')
            expected = (DIAGNOSTICS / name).read_bytes() if name in ('launch_notebook.py', 'prepare_entry.py') else predecessor[name]
            self.assertEqual(raw, expected, name)
            if name in build.OVERLAYS:
                self.assertEqual(build.sha(raw), build.OVERLAYS[name])
        projected = self.artifacts['review-only/verify_parent_wrappers.py']
        for new, old in ((self.space['run'], build.OLD_RUN),
                         (self.space['source'], build.OLD_SOURCE),
                         (self.space['environment'], build.OLD_ENVIRONMENT)):
            projected = projected.replace(new.encode(), old.encode())
        self.assertEqual(projected, wrappers)

    def test_collector_is_unmodified_consumed_reference_not_successor_operator(self):
        name = 'review-only/consumed-run005-collector-reference.py'
        expected = (DIAGNOSTICS / 'rl_collect.py').read_bytes()
        self.assertEqual(self.artifacts[name], expected)
        self.assertEqual(build.sha(expected), build.OVERLAYS['rl_collect.py'])
        self.assertNotIn('deployment/rl_collect.py', self.artifacts)
        self.assertNotIn(self.space['run'].encode(), expected)
        self.assertTrue(self.proposal['retained_collector_is_unmodified_run005_reference_not_successor_operator'])

    def test_all_noncode_release_pins_and_policy_remain_equal(self):
        old_release = build.obj(self.snapshot.tool('release/notebook-release.json'))
        self.assertEqual(self.release['dataset_references'][1:], old_release['dataset_references'][1:])
        self.assertEqual(len(self.release['dataset_references'][1:]), 7)
        self.assertEqual(self.release['material_pins'], old_release['material_pins'])
        self.assertEqual(self.release['phase_policy_sha256'], old_release['phase_policy_sha256'])
        self.assertEqual(self.release['scorer_pins_sha256'], old_release['scorer_pins_sha256'])
        allowed = {'production_admitted', 'code_reference', 'code_manifest_sha256', 'source_sha256',
                   'source_archive_sha256', 'environment_sha256', 'material_review_sha256',
                   'deployment', 'dataset_references', 'storage'}
        self.assertEqual(set(self.release), set(old_release))
        for key in set(old_release) - allowed:
            self.assertEqual(self.release[key], old_release[key], key)
        for key in set(old_release['storage']) - {'environment_root', 'observed_assembled_source_copy_bytes'}:
            self.assertEqual(self.release['storage'][key], old_release['storage'][key], key)
        policy_raw = self.snapshot.tool('release/consumer-release/phase_policy.json')
        policy = build.obj(policy_raw)
        self.assertEqual(build.sha(policy_raw), self.release['phase_policy_sha256'])
        self.assertEqual(policy['evaluation']['selected_PUBLIC_queries'], 167)
        self.assertEqual(policy['evaluation']['selected_PUBLIC_views'], 334)
        self.assertIn('151/167', policy['evaluation']['primary_scoring'])
        self.assertIn('missing/invalid answers wrong', policy['evaluation']['primary_scoring'])
        self.assertEqual(policy['clock_seconds'], {'absolute': 43200, 'inner': 42000, 'outer': 42180, 'provider': 42300})
        self.assertEqual(self.source['owned_runtime/parent_scoring.py'], self.old['owned_runtime/parent_scoring.py'])
        self.assertEqual(self.source['owned_runtime/policy.py'], self.old['owned_runtime/policy.py'])

    def test_preview_is_inert_and_executes_without_filesystem_or_network(self):
        notebook = build.obj(self.artifacts['inactive-review-preview.ipynb'])
        self.assertEqual(notebook['metadata']['rlvr_template_kind'], 'inactive')
        namespace = {'__name__': 'inert_preview_cpu_test'}
        with patch('builtins.open', side_effect=AssertionError('filesystem forbidden')), \
                patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')), \
                redirect_stdout(io.StringIO()):
            for cell in notebook['cells']:
                if cell['cell_type'] == 'code':
                    self.assertIsNone(cell['execution_count'])
                    self.assertEqual(cell['outputs'], [])
                    exec(compile(''.join(cell['source']), '<inert-preview-test>', 'exec'), namespace)
        self.assertIs(namespace['MANUAL_START'], False)
        self.assertIs(namespace['ENABLE_MODEL'], False)
        self.assertIsNone(namespace['PREDISPATCH_EPOCH'])
        self.assertIsNone(namespace['FINALIZED'])
        self.assertEqual(namespace['RESULT'], {'status': 'INACTIVE_NO_EXECUTION',
                                             'model_loaded': False, 'filesystem_accessed': False})
        self.assertEqual(namespace['OUTPUT_ROOT'], self.space['run'])
        self.assertEqual(namespace['SOURCE_PARENT'], self.space['source'])

    def test_no_active_manifest_finalizer_operator_clock_or_authority(self):
        artifacts = set(self.artifacts)
        for name in ('publication-manifest.json', 'manifest.json', 'finalization.json',
                     'active-finalized.ipynb', 'active-template.ipynb', 'operator.json',
                     'original-request.json', 'owner-clock.json', 'finalizer.py', 'rl_transport.py'):
            self.assertNotIn(name, artifacts)
            self.assertNotIn('deployment/' + name, artifacts)
        self.assertEqual([n for n in artifacts if n.endswith('.ipynb') and not n.startswith('producer-source/')],
                         ['inactive-review-preview.ipynb'])
        for key in ('production_admitted', 'run_authorized', 'provider_versions_reserved',
                    'publication_manifest_included', 'active_notebook_included'):
            self.assertIs(self.proposal[key], False, key)
        self.assertIsNone(self.proposal['successor_epoch'])
        self.assertIsNone(self.proposal['public_score'])
        self.assertEqual(self.proposal['provider_calls'], 0)
        self.assertEqual(self.proposal['model_or_GPU_calls'], 0)
        self.assertEqual(self.proposal['consumed_session'],
                         {'epoch': 1791871874, 'deadline': 1791915074, 'preserved_never_reused': True})
        self.assertEqual(self.proposal['manual_failure_root_cause'], 'UNVERIFIED')
        self.assertTrue(self.proposal['original_installer_log_writer_is_still_unbounded'])
        self.assertIsNone(self.release['material_review_sha256'])
        self.assertIsNone(self.release['code_manifest_sha256'])
        self.assertIsNone(self.proposal['target_free_solver'])
        self.assertNotIn('review-only/solver-descriptor.json', artifacts)

    def test_missing_input_ledger_retains_exact_historical_requirements(self):
        raw = self.artifacts['REQUIRED-INPUTS.json']
        required = build.obj(raw)
        self.assertEqual(build.sha(raw), self.proposal['required_inputs_sha256'])
        self.assertIs(required['production_admitted'], False)
        self.assertIs(required['source_only_can_satisfy_production_admission'], False)
        self.assertTrue(all(r['required'] is True for r in required['inputs']))
        historical = build.obj(self.snapshot.tool('release/PREDECESSOR-EVIDENCE.json'))
        actual = {r['role']: {k: v for k, v in r.items() if k not in {'group', 'role', 'required'}}
                  for r in required['inputs'] if r['group'] == 'historical_v31'}
        self.assertEqual(actual, historical['evidence'])
        self.assertEqual({r['group'] for r in required['inputs']},
                         {'historical_v31', 'code17_assembly', 'code18_assembly',
                          'v33_evidence', 'target_free_solver', 'v33_state', 'v35_state'})
        self.assertTrue(any(r.get('sha256') == build.CODE18_ASSEMBLY_SHA for r in required['inputs']))
        self.assertTrue(any(r.get('sha256') == build.CODE18_MANIFEST_SHA for r in required['inputs']))
        self.assertTrue(any(r.get('sha256') == build.SOLVER_SHA for r in required['inputs']))

    def test_default_availability_reports_unsupplied_roots_without_admission(self):
        report = build.obj(self.artifacts['LOCAL-INPUT-AVAILABILITY.json'])
        self.assertEqual(report['status'], 'NON_ADMITTING_AVAILABILITY_ONLY')
        self.assertTrue(report['inputs'])
        self.assertTrue(all(row['local_status'] == 'ROOT_NOT_SUPPLIED' and row['observed'] is None
                            for row in report['inputs']))
        for key in ('production_admitted', 'predecessor_chain_verified', 'all_assembly_members_checked'):
            self.assertIs(report[key], False)
        self.assertEqual(report['provider_calls'], 0)
        self.assertIsNone(self.proposal['installer_overlay'])
        self.assertIs(self.proposal['original_baseline200_exact'], True)
        self.assertIs(self.proposal['installer_runtime_validation_passed'], False)

    def test_optional_installer_requires_all_four_inputs_and_valid_digests(self):
        self.assertIsNone(build.installer_overlay(self.old))
        complete = {'overlay_path': self.root / 'never-read-overlay.py', 'overlay_sha': 'a' * 64,
                    'review_path': self.root / 'never-read-review.json', 'review_sha': 'b' * 64}
        for missing in complete:
            supplied = dict(complete)
            supplied.pop(missing)
            with self.subTest(missing=missing), patch.object(build, 'read', side_effect=AssertionError('read before full arguments')):
                with self.assertRaisesRegex(ValueError, 'installer overlay and independently hash-bound review required'):
                    build.installer_overlay(self.old, **supplied)
        for key in ('overlay_sha', 'review_sha'):
            for invalid in ('A' * 64, 'abc', True, 123):
                supplied = {**complete, key: invalid}
                with self.subTest(key=key, invalid=invalid), self.assertRaisesRegex(ValueError, 'installer overlay review digests'):
                    build.installer_overlay(self.old, **supplied)

    def installer_unit_fixture(self):
        """Synthetic function-level fixture, never evidence or a built proposal."""
        root = self.scratch('synthetic-installer-unit-only-')
        original = self.old[build.INSTALLER_TARGET]
        raw = original + b'\n# SYNTHETIC UNIT TEST ONLY: not an independently reviewed repair.\n'
        overlay = root / 'SYNTHETIC-overlay.py'
        review_path = root / 'SYNTHETIC-review.json'
        review = {'format': 'irisx/bounded-installer-log-review-v1', 'status': 'PASS',
                  'scope': 'LOCAL_SOURCE_REVIEW_ONLY', 'target': build.INSTALLER_TARGET,
                  'original_bootstrap_sha256': build.INSTALLER_ORIGINAL_SHA,
                  'overlay_sha256': build.sha(raw), 'synthetic_unit_fixture_not_real_evidence': True}
        overlay.write_bytes(raw)
        review_path.write_bytes(build.encoded(review))
        return overlay, review_path, raw, review

    def test_optional_installer_hash_schema_target_and_original_binding_rejections(self):
        overlay, review_path, raw, review = self.installer_unit_fixture()
        complete = {'overlay_path': overlay, 'overlay_sha': build.sha(raw),
                    'review_path': review_path, 'review_sha': build.sha(build.encoded(review))}
        for key in ('overlay_sha', 'review_sha'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'installer overlay or review hash mismatch'):
                build.installer_overlay(self.old, **{**complete, key: '0' * 64})
        for key, value, error in (
                ('format', 'other', 'independent local installer review required'),
                ('status', 'PENDING', 'independent local installer review required'),
                ('scope', 'PRODUCTION', 'independent local installer review required'),
                ('target', 'owned_runtime/policy.py', 'installer exact target/review binding'),
                ('original_bootstrap_sha256', '0' * 64, 'installer exact target/review binding'),
                ('overlay_sha256', '0' * 64, 'installer exact target/review binding')):
            changed = build.encoded({**review, key: value})
            review_path.write_bytes(changed)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, error):
                build.installer_overlay(self.old, **{**complete, 'review_sha': build.sha(changed)})
        review_path.write_bytes(build.encoded(review))
        wrong_old = dict(self.old)
        wrong_old[build.INSTALLER_TARGET] += b'\n'
        with self.assertRaisesRegex(ValueError, 'installer original or nonempty delta'):
            build.installer_overlay(wrong_old, **complete)

    def test_optional_installer_function_level_projection_is_exactly_two_file_delta(self):
        # Exercises mechanics only. This synthetic review is never passed to
        # prepare(), predecessor validation, a real approval record or provider.
        overlay, review_path, raw, review = self.installer_unit_fixture()
        installer = build.installer_overlay(self.old, overlay_path=overlay, overlay_sha=build.sha(raw),
            review_path=review_path, review_sha=build.sha(build.encoded(review)))
        files, archive, environment, normalized = build.project_runtime(self.old,
            self.snapshot.tool('driver_path_repair/environment-run005.json'), self.space, self.assembler, installer)
        self.assertEqual({n for n in files if files[n] != self.old[n]},
                         {'owned_runtime/release.py', build.INSTALLER_TARGET})
        self.assertEqual(sum(files[n] == self.old[n] for n in files), 257)
        self.assertEqual(sum(files[n] == self.old[n] for n in files if n.startswith('baseline/')), 199)
        self.assertEqual(files[build.INSTALLER_TARGET], raw)
        self.assertEqual(environment, self.artifacts['release/REVIEWED-ENVIRONMENT.json'])
        self.assertNotEqual(archive, self.artifacts['source.zip'])
        self.assertNotEqual(normalized, self.proposal['normalized_source_contract_sha256'])
        self.assertEqual(files['owned_runtime/policy.py'], self.old['owned_runtime/policy.py'])

    def test_frozen_input_manifest_records_actual_authenticated_bodies(self):
        inputs = build.obj(self.artifacts['FROZEN-INPUTS.json'])
        snapshot = build.Snapshot(REPOSITORY)
        for name, descriptor in inputs.items():
            self.assertEqual(descriptor, build.desc(snapshot.read(name)), name)
        self.assertEqual(self.proposal['snapshot_commit'], build.SNAPSHOT)
        self.assertEqual(self.proposal['snapshot_tree'], build.TREE)
        self.assertEqual(self.proposal['runtime_parent_commit'], build.RUNTIME_COMMIT)

    def test_frozen_input_mutation_fails_before_output_without_editing_source(self):
        target = PACKAGE / 'driver_path_repair/environment-run005.json'
        read = build.read
        output = self.scratch('frozen-mutation-') / 'proposal'
        def tampered(path, cap=build.CAP):
            raw = read(path, cap)
            return raw + b'\n' if Path(path) == target else raw
        with patch.object(build, 'read', side_effect=tampered):
            with self.assertRaisesRegex(ValueError, 'frozen input changed'):
                build.prepare(repository_root=REPOSITORY, identity_path=IDENTITY, output_root=output)
        self.assertFalse(output.exists())

    def test_each_independently_pinned_overlay_tamper_is_rejected(self):
        read = build.read
        for name in build.OVERLAYS:
            with self.subTest(name=name):
                output = self.scratch('overlay-tamper-') / 'proposal'
                target = DIAGNOSTICS / name
                def tampered(path, cap=build.CAP):
                    raw = read(path, cap)
                    return raw + b'\n' if Path(path) == target else raw
                with patch.object(build, 'read', side_effect=tampered):
                    with self.assertRaisesRegex(ValueError, 'independently reviewed diagnostic overlay changed'):
                        build.prepare(repository_root=REPOSITORY, identity_path=IDENTITY, output_root=output)
                self.assertFalse(output.exists())

    def test_inauthentic_solver_descriptor_cannot_create_output(self):
        root = self.scratch('solver-rejection-')
        descriptor = root / 'clearly-not-authentic-solver.json'
        descriptor.write_bytes(b'{}\n')
        output = root / 'proposal'
        with self.assertRaisesRegex(ValueError, 'authentic code18 target-free solver descriptor required'):
            build.prepare(repository_root=REPOSITORY, identity_path=IDENTITY,
                          output_root=output, solver_path=descriptor)
        self.assertFalse(output.exists())

    def test_consumed_or_existing_output_and_nonignored_output_rejected_before_inputs(self):
        for output in (self.outputs[0], REPOSITORY / '.irisx', REPOSITORY / 'not-an-output-directory'):
            with self.subTest(output=output), patch.object(build, 'read', side_effect=AssertionError('inputs must not be read')):
                with self.assertRaisesRegex(ValueError, 'fresh output directory|ignored local output'):
                    build.prepare(repository_root=REPOSITORY, identity_path=IDENTITY, output_root=output)

    def test_source_only_output_cannot_pass_authentic_predecessor_gate(self):
        with self.assertRaises(FileNotFoundError):
            build.verify_code18_candidate(build.Snapshot(REPOSITORY), self.outputs[0])
        self.assertNotIn('ASSEMBLY-INVENTORY.json', self.artifacts)
        self.assertNotIn('publication-manifest.json', self.artifacts)

    def test_altered_inventory_rejected_without_mocking_old_admission_gate(self):
        root = self.scratch('not-a-predecessor-')
        # A deliberately invalid input is a rejection fixture, not fabricated
        # historical evidence and never used to force the old contract through.
        (root / 'ASSEMBLY-INVENTORY.json').write_bytes(b'{}\n')
        with self.assertRaisesRegex(ValueError, 'exact code18 assembly inventory required'):
            build.verify_code18_candidate(build.Snapshot(REPOSITORY), root)

    def test_closed_inventory_rejects_fifo_and_hardlink_before_old_gate(self):
        # Isolate the directory-shape guard with a visibly synthetic empty
        # inventory. No historical archive is manufactured and the real frozen
        # contract must not load, let alone pass, in this negative unit test.
        for kind in ('fifo', 'hardlink'):
            root = self.scratch('synthetic-closed-set-' + kind + '-')
            inventory = b'{}\n'
            (root / 'ASSEMBLY-INVENTORY.json').write_bytes(inventory)
            if kind == 'fifo':
                os.mkfifo(root / 'SYNTHETIC-fifo')
            else:
                target = root / 'SYNTHETIC-target'
                target.write_bytes(b'SYNTHETIC UNIT TEST ONLY')
                os.link(target, root / 'SYNTHETIC-hardlink')
            with self.subTest(kind=kind), patch.object(build, 'CODE18_ASSEMBLY_SHA', build.sha(inventory)), \
                    patch.object(build, 'load_module', side_effect=AssertionError('old contract must not load')):
                with self.assertRaises(ValueError):
                    build.verify_code18_candidate(build.Snapshot(REPOSITORY), root)

    def test_predecessor_verifier_authenticates_frozen_validator_and_calls_strict_contract(self):
        source = ast.parse(Path(build.__file__).read_bytes())
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'verify_code18_candidate')
        calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]
        contracts = [n for n in calls if isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name)
                     and n.func.value.id == 'transport' and n.func.attr == 'contract']
        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0].keywords, [])
        self.assertEqual(len(contracts[0].args), 1)
        self.assertIn('publication-manifest.json', ast.unparse(contracts[0].args[0]))
        literals = {n.value for n in ast.walk(function) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        self.assertIn('publication_run005/rl_transport.py', literals)
        for name in ('config.py', 'operator_common.py', 'rl_transport.py'):
            self.assertIn(name, literals)
            self.snapshot.tool('publication_run005/' + name)
        # These immutable validators retain the real predecessor admission calls.
        old_transport = self.snapshot.tool('publication_run005/rl_transport.py')
        self.assertIn(b'predecessor_proof(m,root)', old_transport)
        self.assertIn(b"historical_v31", old_transport)
        self.assertIn(b"HISTORICAL_V31_SHA256=", old_transport)


class IdentityAndInputGuardTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(IDENTITY.read_bytes())
        self.temporary = tempfile.TemporaryDirectory(dir=SCRATCH.name, prefix='input-guards-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_expected_proposal_identity_and_all_fresh_namespaces(self):
        self.assertEqual(build.identity(build.encoded(self.document)), self.document)
        for suffix in range(6, 10):
            document = copy.deepcopy(self.document)
            document['run_id'] = 'irisx-qwen14b-rlvr-20261013-run00' + str(suffix)
            self.assertEqual(build.identity(build.encoded(document)), document)
            space = build.namespaces(document)
            self.assertEqual(space['source'], '/kaggle/working/' + document['run_id'].replace('-run', '-source'))
            self.assertEqual(space['environment'], '/tmp/' + document['run_id'].replace('-run', '-environment'))

    def test_old_or_unbounded_run_identity_rejected(self):
        for run_id in ('irisx-qwen14b-rlvr-20261012-run005', 'irisx-qwen14b-rlvr-20261013-run005',
                       'irisx-qwen14b-rlvr-20261013-run010', '../run006', 'irisx-qwen14b-rlvr-20261013-run006/child',
                       'irisx-qwen14b-rlvr-20261013-run006\n', None, False):
            with self.subTest(run_id=run_id):
                document = copy.deepcopy(self.document)
                document['run_id'] = run_id
                with self.assertRaisesRegex(ValueError, 'fresh successor namespace'):
                    build.identity(build.encoded(document))

    def test_false_proposed_status_and_extra_authority_fields_rejected(self):
        for status in (False, True, 'RESERVED', 'APPROVED', 'ACTIVE', None):
            with self.subTest(status=status):
                document = copy.deepcopy(self.document)
                document['status'] = status
                with self.assertRaisesRegex(ValueError, 'proposal identity only'):
                    build.identity(build.encoded(document))
        for field in ('proposed', 'run_authorized', 'production_admitted', 'predispatch_epoch'):
            document = copy.deepcopy(self.document)
            document[field] = False
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'identity schema'):
                build.identity(build.encoded(document))

    def test_invalid_version_types_and_changed_version_numbers_rejected(self):
        for key in self.document['versions']:
            for value in (False, True, 19.0, '19', None, -1, 0, self.document['versions'][key] + 1):
                document = copy.deepcopy(self.document)
                document['versions'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    build.identity(build.encoded(document))
        for versions in ([], None, {}, {**self.document['versions'], 'extra': 20}):
            document = copy.deepcopy(self.document)
            document['versions'] = versions
            with self.subTest(versions=versions), self.assertRaisesRegex(ValueError, 'version schema'):
                build.identity(build.encoded(document))

    def test_duplicate_json_keys_and_nonobject_json_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                build.obj(raw)
        for raw in (b'[]', b'null', b'true', b'1', b'"text"'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'JSON object required'):
                build.obj(raw)

    def test_nonfinite_json_literals_and_exponent_overflow_rejected(self):
        for raw in (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}',
                    b'{"x":1e400}', b'{"nested":[-1e400]}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'nonfinite JSON'):
                build.obj(raw)
        self.assertTrue(math.isfinite(build.obj(b'{"x":1e300}')['x']))

    def test_json_encoders_refuse_nonfinite_values(self):
        for encode in (build.encoded, build.canonical):
            for value in (math.inf, -math.inf, math.nan):
                with self.subTest(encoder=encode.__name__, value=value), self.assertRaises(ValueError):
                    encode({'nested': [value]})

    def test_unsafe_relative_names_and_controls_rejected(self):
        for name in ('', '.', '..', '../bad', '/absolute', 'C:/bad', 'a\\b', 'a//b',
                     'a/./b', 'a/../b', 'a/', '\x00', 'a\nb', 'a\rb', 'a\tb', 'a\x7fb', None, 2):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unsafe relative name'):
                build.relative(name)
        self.assertEqual(build.relative('safe/subdir/source.py'), 'safe/subdir/source.py')

    def test_input_size_and_regular_file_requirement(self):
        path = self.root / 'regular'
        path.write_bytes(b'four')
        self.assertEqual(build.read(path, 4), b'four')
        with self.assertRaisesRegex(ValueError, 'bounded regular input'):
            build.read(path, 3)
        with self.assertRaisesRegex(ValueError, 'bounded regular input'):
            build.read(self.root)
        fifo = self.root / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'bounded regular input'):
            build.read(fifo)

    def test_symlink_ancestor_link_and_hardlink_rejected(self):
        target = self.root / 'target'
        target.write_bytes(b'{}')
        link = self.root / 'link'
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'linked or reparse'):
            build.read(link)
        directory = self.root / 'linked-directory'
        directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked or reparse'):
            build.read(directory / 'target')
        hardlink = self.root / 'hardlink'
        os.link(target, hardlink)
        for path in (target, hardlink):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'bounded regular input'):
                build.read(path)

    def test_linked_output_parent_rejected_before_any_input_read(self):
        actual = self.root / 'actual'
        actual.mkdir()
        link = self.root / 'linked-output'
        link.symlink_to(actual, target_is_directory=True)
        with patch.object(build, 'read', side_effect=AssertionError('input read before output guard')):
            with self.assertRaisesRegex(ValueError, 'linked or reparse'):
                build.prepare(repository_root=REPOSITORY, identity_path=IDENTITY, output_root=link / 'proposal')
        self.assertFalse((actual / 'proposal').exists())

    def test_exact_replacement_rejects_missing_duplicate_and_nonreversible_input(self):
        for raw, before, after in ((b'a', 'x', 'y'), (b'x x', 'x', 'y'),
                                   (b'x y', 'x', 'y'), (b'x', 'x', 'x')):
            with self.subTest(raw=raw, before=before, after=after), self.assertRaises(ValueError):
                build.exact_replace(raw, before, after)
        self.assertEqual(build.exact_replace(b'one old path', 'old', 'new'), b'one new path')

    def test_audit_real_unsupplied_and_empty_roots_remain_missing_nonadmission(self):
        report = build.audit_inputs(build.Snapshot(REPOSITORY), {'v35_state': str(self.root)})
        for row in report['inputs']:
            self.assertEqual(row['local_status'], 'MISSING' if row['group'] == 'v35_state' else 'ROOT_NOT_SUPPLIED')
            self.assertIsNone(row['observed'])
        self.assertFalse(report['production_admitted'])
        self.assertFalse(report['predecessor_chain_verified'])

    def test_audit_synthetic_status_matrix_never_becomes_chain_verification(self):
        # Synthetic names and synthetic requirements exercise this reporting
        # function only; no original receipts or archives are manufactured.
        raw = b'SYNTHETIC UNIT TEST ONLY, NOT HISTORICAL EVIDENCE'
        requirements = {'inputs': [
            {'group': 'synthetic', 'path': 'SYNTHETIC-exact', 'required': True, **build.desc(raw)},
            {'group': 'synthetic', 'path': 'SYNTHETIC-mismatch', 'required': True, **build.desc(raw)},
            {'group': 'synthetic', 'path': 'SYNTHETIC-unpinned', 'required': True},
            {'group': 'synthetic', 'path': 'SYNTHETIC-missing', 'required': True},
            {'group': 'synthetic', 'path': 'SYNTHETIC-symlink', 'required': True},
        ]}
        (self.root / 'SYNTHETIC-exact').write_bytes(raw)
        (self.root / 'SYNTHETIC-mismatch').write_bytes(b'wrong bytes')
        (self.root / 'SYNTHETIC-unpinned').write_bytes(raw)
        (self.root / 'SYNTHETIC-symlink').symlink_to(self.root / 'SYNTHETIC-exact')
        with patch.object(build, 'requirements', return_value=requirements):
            report = build.audit_inputs(None, {'synthetic': str(self.root)})
        statuses = {row['path']: row['local_status'] for row in report['inputs']}
        self.assertEqual(statuses, {
            'SYNTHETIC-exact': 'EXACT_BYTES_PRESENT',
            'SYNTHETIC-mismatch': 'PIN_MISMATCH',
            'SYNTHETIC-unpinned': 'PRESENT_CHAIN_VERIFICATION_REQUIRED',
            'SYNTHETIC-missing': 'MISSING',
            'SYNTHETIC-symlink': 'UNSAFE_OR_UNREADABLE',
        })
        self.assertFalse(report['production_admitted'])
        self.assertFalse(report['predecessor_chain_verified'])
        self.assertFalse(report['all_assembly_members_checked'])
        self.assertEqual(report['provider_calls'], 0)

    def test_audit_unknown_groups_relative_roots_and_linked_roots_rejected(self):
        snapshot = build.Snapshot(REPOSITORY)
        for roots in ([], {'unknown': str(self.root)}, {'v35_state': '.'}, {'v35_state': 1}):
            with self.subTest(roots=roots), self.assertRaises(ValueError):
                build.audit_inputs(snapshot, roots)
        linked = self.root / 'linked-root'
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked or reparse'):
            build.audit_inputs(snapshot, {'v35_state': str(linked)})


if __name__ == '__main__':
    unittest.main()

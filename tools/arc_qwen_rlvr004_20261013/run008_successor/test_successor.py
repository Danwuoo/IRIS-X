"""Fresh CPU tests. Synthetic markers are fixtures, never publication approvals."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
REPO = HERE.parents[2]
REBUILD = REPO / '.irisx/transfer-verification-20261013/rebuild-offline-2'
SCRATCH = REPO / '.irisx/run008-packaging'
SCRATCH.mkdir(parents=True, exist_ok=True)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s = load('run008_test_prepare', HERE / 'prepare.py')
auth = load('run008_test_auth', HERE / 'native_auth.py')


class AssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='cpu-tests-', dir=SCRATCH)
        cls.root = Path(cls.tmp.name)
        cls.args = dict(repository_root=REPO, candidate_root=REBUILD / 'candidate-rebuild',
            source_proposal_root=REBUILD / 'source-rebuild', rebuild_report=REBUILD / 'REBUILD-REPORT.json')
        manifest = HERE.parent / 'loader_repair_run008/OVERLAY-MANIFEST.json'
        if manifest.exists():
            cls.args.update(overlay_manifest=manifest, overlay_manifest_sha=s.sha(manifest.read_bytes()))
        cls.candidate = cls.root / 'proposal'
        cls.result = s.prepare(**cls.args, output_root=cls.candidate)
        cls.loader = load('run008_test_mount', cls.candidate / 'code-payload/deployment/source_loader.py')
        cls.release = json.loads((cls.candidate / 'notebook-release.json').read_bytes())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_deterministic_complete_assembly(self):
        other = self.root / 'repeat'
        s.prepare(**self.args, output_root=other)
        self.assertEqual((self.candidate / 'ASSEMBLY-INVENTORY.json').read_bytes(), (other / 'ASSEMBLY-INVENTORY.json').read_bytes())
        self.assertEqual(self.result['unchanged_run007_baseline_members'], 200)
        self.assertEqual(self.result['unchanged_frozen_code18_baseline_members'], 199)
        self.assertEqual(self.result['unchanged_consumer_helper_members'], 21)
        self.assertEqual(set(self.result['runtime_delta']) - {'owned_runtime/release.py'},
                         set(json.loads(Path(self.args['overlay_manifest']).read_bytes())['files']) if 'overlay_manifest' in self.args else set())

    def test_no_replayed_approval_or_clock(self):
        self.assertEqual(self.result['status'], 'OFFLINE_PROPOSAL_NOT_PUBLISHABLE')
        self.assertIsNone(self.result['successor_epoch'])
        self.assertFalse(self.release['production_admitted'])
        self.assertIsNone(self.release['original_owner_request'])
        self.assertEqual(self.release['code_reference'], s.UNBOUND_REFERENCE)
        finalizer = load('run008_test_finalizer', self.candidate / 'assembly/finalize.py')
        with self.assertRaisesRegex(ValueError, 'independently admitted'):
            finalizer.finalize(self.candidate, 1792000000)
        entry = (self.candidate / 'terminal-consumer/reviewed_entry.py').read_bytes()
        self.assertIn(b'REVIEWED_OPERATOR_PINS_SHA256 = None', entry)

    def test_both_notebooks_execute_inert_without_filesystem_or_model(self):
        for kind in ('inactive', 'active-template'):
            notebook = json.loads((self.candidate / ('run008-' + kind + '.ipynb')).read_bytes())
            code = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
            with patch('sys.stdout', new=io.StringIO()):
                ns = {}; exec(compile(code, '<inert-template>', 'exec'), ns)
            self.assertEqual(ns['RESULT'], {'status': 'INACTIVE_NO_EXECUTION', 'model_loaded': False, 'filesystem_accessed': False})
            self.assertIsNone(ns['PREDISPATCH_EPOCH'])
            self.assertEqual(ns['SESSION_SECONDS'], 43200)
            self.assertEqual(ns['OUTPUT_ROOT'], s.RUN)

    def test_only_source_payload_archive_no_evaluator_or_historical_chain(self):
        with zipfile.ZipFile(self.candidate / 'code-upload-PROPOSAL.zip') as archive:
            names = set(archive.namelist())
            expected = {str(p.relative_to(self.candidate / 'code-payload')) for p in (self.candidate / 'code-payload').rglob('*') if p.is_file()}
            self.assertEqual(names, expected)
            self.assertFalse(any(n.startswith(('historical', 'predecessor', 'consumer', 'review/', 'evaluator', 'authentic-inputs')) for n in names))
        self.assertFalse((self.candidate / 'publication-manifest.json').exists())

    def test_fresh_process_no_model_mount_acceptance(self):
        output = self.root / 'mount-acceptance'
        command = [sys.executable, '-I', '-B', *(['-O'] if sys.flags.optimize else []),
            str(self.candidate / 'assembly/accept_downloaded_mount.py'), '--candidate-root', str(self.candidate),
            '--code-root', str(self.candidate / 'code-payload'), '--output-root', str(output)]
        proc = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=60, check=False, env={'PATH': os.defpath, 'LANG': 'C.UTF-8'})
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt['status'], 'PASS')
        self.assertFalse(receipt['isolated_import']['model_libraries_imported'])
        self.assertFalse(receipt['provider_provenance_verified_by_this_helper'])
        # The preserved helper's inner interpreter defaults to normal mode;
        # explicitly verify this suite's optimization level in a fresh child too.
        child = subprocess.run([sys.executable, '-I', '-B', *(['-O'] if sys.flags.optimize else []),
            str(output / 'source-check.py'), str(output / 'source/runtime')],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45,
            env={'PATH': os.defpath, 'LANG': 'C.UTF-8'}, check=False)
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        self.assertFalse(json.loads(child.stdout)['model_libraries_imported'])

    def test_archive_and_both_extracted_mount_layouts(self):
        manifest = json.loads((self.candidate / 'code-payload/manifest.json').read_bytes())
        for prefix in ('', 'source/'):
            root = self.root / ('mount-extracted-root' if not prefix else 'mount-source')
            shutil.copytree(self.candidate / 'code-payload', root)
            (root / 'source.zip').unlink()
            for name in manifest['source']['files']:
                target = root / (prefix + name); target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.candidate / 'producer-source' / name, target)
            result = self.loader.inspect_release(str(root), manifest_sha256=self.release['code_manifest_sha256'], archive_sha256=self.release['source_archive_sha256'])
            self.assertIn('verified-extracted', result[-1])

    def test_corrupt_mount_fails_before_output_creation(self):
        root = self.root / 'corrupt-mount'; shutil.copytree(self.candidate / 'code-payload', root)
        with (root / 'source.zip').open('ab') as stream: stream.write(b'corruption')
        output = self.root / 'never-created'
        with self.assertRaisesRegex(ValueError, 'source archive bytes differ'):
            self.loader.load_release(str(root), str(output), manifest_sha256=self.release['code_manifest_sha256'], archive_sha256=self.release['source_archive_sha256'])
        self.assertFalse(output.exists())

    def test_source_pins_policy_and_scoring_are_unchanged(self):
        original = json.loads((REBUILD / 'candidate-rebuild/notebook-release.json').read_bytes())
        for key in ('material_pins', 'phase_policy_sha256', 'scorer_pins_sha256'):
            self.assertEqual(self.release[key], original[key])
        self.assertEqual(self.release['dataset_references'][1:], original['dataset_references'][1:])
        for name in ('design/MEASURED-POLICY.json', 'owned_runtime/planning.py'):
            self.assertEqual((self.candidate / 'producer-source' / name).read_bytes(), (REBUILD / 'candidate-rebuild/producer-source' / name).read_bytes())

    def test_target_free_solver_only_two_paths_no_escrow_read(self):
        old = (REBUILD / 'source-rebuild/review-only/solver-descriptor.json').read_bytes()
        new = (self.candidate / 'review-only/solver-descriptor.json').read_bytes()
        self.assertEqual(new.replace(s.RUN.encode(), s.OLD_RUN.encode()), old)
        proof = json.loads((self.candidate / 'review-only/SOLVER-PROJECTION.json').read_bytes())
        self.assertEqual(proof['path_substitutions'], 2)
        self.assertFalse(proof['escrow_bodies_read'])
        self.assertEqual(proof['status'], 'INDEPENDENT_REVIEW_REQUIRED')

    def test_overwrite_and_outside_output_rejected(self):
        with self.assertRaises(ValueError): s.prepare(**self.args, output_root=self.candidate)
        with self.assertRaises(ValueError): s.prepare(**self.args, output_root=REPO / 'run008-must-not-exist')

    def test_new_output_cleanup_preserves_original_failure(self):
        output = self.root / 'failed-output'
        with patch.object(s, 'read', side_effect=OSError('synthetic write-readback failure')):
            with self.assertRaisesRegex(OSError, 'synthetic write-readback failure'):
                s.write_output(output, {'file.txt': b'fixture'})
        self.assertFalse(output.exists())

    def test_link_and_closed_extra_fail(self):
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            root = Path(temp); (root / 'data').write_bytes(b'fixture')
            inventory = s.encoded({'data': s.desc(b'fixture')}); (root / 'inventory.json').write_bytes(inventory)
            (root / 'extra').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError, 'path set'):
                s.closed(root, 'inventory.json', s.sha(inventory))
            (root / 'extra').unlink(); (root / 'data').unlink(); (root / 'data').symlink_to(root / 'inventory.json')
            with self.assertRaisesRegex(ValueError, 'linked'):
                s.closed(root, 'inventory.json', s.sha(inventory))

    def test_unreviewed_overlay_bound_but_unadmitted_and_outside_target_rejected(self):
        original = (self.candidate / 'producer-source/owned_runtime/worker.py').read_bytes()
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            root = Path(temp); overlay = original + b'\n# Synthetic CPU test marker, not a real loader repair.\n'
            (root / 'worker.py').write_bytes(overlay)
            document = {'format': 'irisx/run008-loader-overlay-set-v1', 'base_source_sha256': s.BASE_SOURCE,
                'files': {'owned_runtime/worker.py': {'path': 'worker.py', 'original_sha256': s.sha(original), **s.desc(overlay)}}}
            raw = s.encoded(document); (root / 'overlay.json').write_bytes(raw)
            sources, _, review = s.overlay_inputs({'owned_runtime/worker.py': original}, root / 'overlay.json', s.sha(raw))
            self.assertEqual(sources['owned_runtime/worker.py'], overlay); self.assertIsNone(review)
            document['files']['baseline/worker.py'] = document['files'].pop('owned_runtime/worker.py')
            raw = s.encoded(document); (root / 'overlay.json').write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'target set'):
                s.overlay_inputs({}, root / 'overlay.json', s.sha(raw))

    def test_historical_review_cannot_authorize_new_overlay(self):
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            root = Path(temp); source = b'original'; overlay = b'# synthetic fixture\n'
            (root / 'worker.py').write_bytes(overlay)
            raw = s.encoded({'format': 'irisx/run008-loader-overlay-set-v1', 'base_source_sha256': s.BASE_SOURCE,
                'files': {'owned_runtime/worker.py': {'path': 'worker.py', 'original_sha256': s.sha(source), **s.desc(overlay)}}})
            (root / 'overlay.json').write_bytes(raw)
            review = REBUILD / 'candidate-rebuild/code-payload/release/RUNTIME-REVIEW.json'
            with self.assertRaisesRegex(ValueError, 'fresh independent'):
                s.overlay_inputs({'owned_runtime/worker.py': source}, root / 'overlay.json', s.sha(raw), review, s.sha(review.read_bytes()))


@unittest.skipUnless(sys.platform == 'linux', 'real Linux owned-process guard')
class OwnedProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assembly_tmp = tempfile.TemporaryDirectory(prefix='owned-source-', dir=SCRATCH)
        root = Path(cls.assembly_tmp.name) / 'proposal'
        args = dict(repository_root=REPO, candidate_root=REBUILD / 'candidate-rebuild',
            source_proposal_root=REBUILD / 'source-rebuild', rebuild_report=REBUILD / 'REBUILD-REPORT.json')
        manifest = HERE.parent / 'loader_repair_run008/OVERLAY-MANIFEST.json'
        if manifest.exists(): args.update(overlay_manifest=manifest, overlay_manifest_sha=s.sha(manifest.read_bytes()))
        s.prepare(**args, output_root=root)
        cls.launch = load('run008_cpu_launch', root / 'code-payload/deployment/launch_notebook.py')
        cls.guard = load('run008_cpu_guard', root / 'producer-source/baseline/tools/arc_learning_agent_20261011/process_guard.py')

    @classmethod
    def tearDownClass(cls): cls.assembly_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='owned-cpu-', dir=SCRATCH)
        self.root = Path(self.tmp.name); self.stage = self.root / 'stage'

    def tearDown(self): self.tmp.cleanup()

    def child(self, code, deadline=None):
        return self.launch.run_bounded([sys.executable, '-I', '-B', *(['-O'] if sys.flags.optimize else []), '-c', code],
            guard_module=self.guard, directory=self.stage, deadline_epoch=time.time() + 45 if deadline is None else deadline,
            env={'PATH': os.defpath, 'LANG': 'C.UTF-8'}, scope='entire-owned-preparation-and-runtime',
            failure_context={'source_sha256': s.BASE_SOURCE, 'request_sha256': 'a' * 64, 'original_epoch': 1234567890})

    def proof(self):
        value = json.loads((self.stage / 'owned-tree/closure.json').read_bytes())
        self.guard.verify_closed_proof(value); self.assertTrue(value['closed']); self.assertFalse(value['remaining'])
        return value

    def test_actual_child_failure_cleanup(self):
        with self.assertRaises(RuntimeError): self.child('raise SystemExit(7)')
        self.assertEqual(self.proof()['worker_returncode'], 7)

    def test_expired_original_deadline_never_dispatches(self):
        with self.assertRaisesRegex(ValueError, 'reserve exhausted'): self.child('raise AssertionError()', time.time() - 1)
        self.assertFalse((self.stage / 'owned-tree').exists())

    def test_actual_child_timeout_closes_tree(self):
        deadline = time.time() + 16
        with self.assertRaises(RuntimeError): self.child('import time; time.sleep(30)', deadline)
        self.assertTrue(self.proof()['forced'])
        receipt = json.loads((self.stage / 'closure.json').read_bytes())
        self.assertEqual(receipt['deadline_epoch'], deadline)
        self.assertEqual(receipt['reason'], 'original-outer-deadline')

    def test_postspawn_parent_failure_cleanup(self):
        with patch.object(self.launch.selectors, 'DefaultSelector', side_effect=OSError('synthetic selector failure')):
            with self.assertRaisesRegex(OSError, 'synthetic selector failure'): self.child('import time; time.sleep(30)')
        self.proof()


class NativeAuthPlanTests(unittest.TestCase):
    def test_existing_wrapper_only_and_no_execution(self):
        with patch.object(subprocess, 'run', side_effect=AssertionError('provider must not execute')):
            proof = auth.status_read_plan(REPO.parent / 'kaggle_setup/kaggle.sh')
        self.assertTrue(proof['currently_blocked'])
        self.assertEqual(proof['boundary']['credential_body_reads'], 0)
        self.assertEqual(proof['argv'][-1], auth.REFERENCE)
        self.assertNotIn('HOME', proof['environment'])
        self.assertFalse(proof['boundary']['authentication_or_exact_resource_access_verified'])

    def test_other_wrapper_and_publication_rejected(self):
        with self.assertRaises(ValueError): auth.inspect_wrapper('/tmp/unreviewed-kaggle.sh')
        with self.assertRaisesRegex(ValueError, 'no executable adapter'): auth.publication_command()


if __name__ == '__main__': unittest.main()

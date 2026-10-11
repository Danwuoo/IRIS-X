"""Export boundary regressions, including a real offline tiny-wheel CPU fixture.

Synthetic wheels/owner results are never claimed as the production CUDA closure,
model inference, neural training, or an actual 52-wheel environment reinstall.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock
import zipfile

from tools.arc_learning_agent_20261011 import evaluation, export
from tools.arc_learning_agent_20261011.budget import SessionClock, atomic_json, canonical, digest
from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof
from tools.arc_learning_agent_20261011.tests.test_result_projection import _SYNTHETIC_OWNER
from tools.arc_public_research_20261010 import offline_bootstrap
from tools.arc_public_research_20261010.tests.test_public_data import make_assets
from tools import arc_next_offline_environment as offline
from tests.test_arc_next_offline_environment import Wheelhouse


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_bootstrap(root, lock):
    value = {'status': 'prepared', 'installed_offline': True,
             'environment_lock_path': str(root / export.ENVIRONMENT_LOCK),
             'actual_environment_lock_sha256': sha(root / export.ENVIRONMENT_LOCK),
             'python_command': lock['python_command'], 'synthetic_fixture': True}
    atomic_json(root / 'bootstrap-receipt.json', value, exclusive=True)
    return value


def environment_fixture(root, outside):
    environment = root / 'environment/environment-cp312-cu128'
    evidence = environment / 'evidence'; evidence.mkdir(parents=True)
    command = [str(environment / 'bin/python'), '-I', '-B', '-S', str(environment / 'offline-run.py')]
    lock = {'format': 'irisx/arc-next-environment-lock-v1', 'status': 'installed-offline',
            'environment_lock': str(root / export.ENVIRONMENT_LOCK), 'python_command': command,
            'python_executable': command[0], 'python_launcher_path': command[-1],
            'synthetic_fixture': True}
    atomic_json(root / export.ENVIRONMENT_LOCK, lock, exclusive=True)
    atomic_json(root / export.INSTALLATION_RECEIPT, lock, exclusive=True)
    write_bootstrap(root, lock)
    (evidence / 'wheels').symlink_to(outside, target_is_directory=True)
    interpreter = root / 'environment/cpython312/python/bin'; interpreter.mkdir(parents=True)
    (interpreter / 'python3.12').write_bytes(b'explicit synthetic interpreter')
    (interpreter / 'python3').symlink_to('python3.12')
    (root / 'environment/cycle').symlink_to(root, target_is_directory=True)
    return environment


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='export-boundary-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'output'; self.root.mkdir()
        self.outside = self.base / 'immutable-wheelhouse'; self.outside.mkdir()
        (self.outside / 'never-open').write_bytes(b'outside sentinel')
        (self.root / 'summary.json').write_bytes(b'{"status":"synthetic"}\n')

    def run_export(self, root=None, **kwargs):
        return export.export_evidence(root or self.root, run_id=kwargs.get('run_id', 'synthetic-export'),
                                      deadline=kwargs.get('deadline', time.monotonic() + 30))

    def assert_no_closure(self):
        self.assertFalse((self.root / 'post-seal-closure.json').exists())

    def test_no_environment_preserves_archive_and_separate_artifact_contract(self):
        for name in ('worker/checkpoints/step/state.pt', 'worker/trained-global-adapter/adapter.bin'):
            path = self.root / name; path.parent.mkdir(parents=True); path.write_bytes(b'weight-fixture')
        receipt = self.run_export()
        self.assertFalse(receipt['generation_may_resume'])
        self.assertEqual(sha(Path(receipt['archive']['path'])), receipt['archive']['sha256'])
        with zipfile.ZipFile(receipt['archive']['path']) as archive:
            self.assertEqual(set(archive.namelist()), {'summary.json', 'evidence-inventory.json'})
            inventory = json.loads(archive.read('evidence-inventory.json'))
        self.assertEqual(inventory['separate_artifacts'], receipt['separate_artifacts'])
        self.assertNotIn('environment_proof_files', inventory)
        self.assertEqual(digest(inventory), receipt['inventory_sha256'])
        with self.assertRaisesRegex(ValueError, 'identity consumed'): self.run_export()

    def test_environment_payload_and_links_are_not_scanned_or_archived(self):
        environment = environment_fixture(self.root, self.outside)
        with (environment / 'huge-installed-payload').open('wb') as stream: stream.truncate(600 * 1024**2)
        os.mkfifo(environment / 'never-open-fifo')
        scanned = []; original = os.scandir
        def guarded_scan(descriptor):
            path = Path(os.readlink('/proc/self/fd/' + str(descriptor)))
            self.assertFalse(path.is_relative_to(self.root / 'environment'), 'excluded payload was scanned')
            scanned.append(path)
            return original(descriptor)
        with mock.patch.object(export.os, 'scandir', side_effect=guarded_scan):
            receipt = self.run_export()
        with zipfile.ZipFile(receipt['archive']['path']) as archive:
            names = set(archive.namelist())
            self.assertEqual(names, {'summary.json', 'bootstrap-receipt.json', 'evidence-inventory.json',
                                     export.ENVIRONMENT_LOCK, export.INSTALLATION_RECEIPT})
            inventory = json.loads(archive.read('evidence-inventory.json'))
            self.assertFalse(inventory['installed_environment_included'])
            self.assertEqual(set(inventory['environment_proof_files']),
                             {export.ENVIRONMENT_LOCK, export.INSTALLATION_RECEIPT})
            for name, row in inventory['files'].items():
                raw = archive.read(name)
                self.assertEqual(row, {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
                self.assertEqual(raw, (self.root / name).read_bytes())
            bootstrap = json.loads(archive.read('bootstrap-receipt.json'))
            self.assertEqual(bootstrap['actual_environment_lock_sha256'], inventory['files'][export.ENVIRONMENT_LOCK]['sha256'])
        self.assertTrue(scanned)
        self.assertEqual((self.outside / 'never-open').read_bytes(), b'outside sentinel')

    def test_symlink_root_and_ancestor_are_rejected(self):
        link = self.base / 'link'; link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.run_export(link)
        parent_link = self.base / 'ancestor'; parent_link.symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.run_export(parent_link / 'output')
        self.assert_no_closure()

    def test_environment_root_link_is_rejected_without_opening_target(self):
        (self.root / 'environment').symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.run_export()
        self.assert_no_closure()

    def test_environment_root_must_be_directory(self):
        (self.root / 'environment').write_bytes(b'not a directory')
        with self.assertRaises(ValueError): self.run_export()
        self.assert_no_closure()

    def test_included_links_cannot_alias_excluded_environment(self):
        environment_fixture(self.root, self.outside)
        link = self.root / 'included'
        for target in (self.outside, self.root / export.ENVIRONMENT_LOCK, self.root / 'environment', self.base / 'missing'):
            with self.subTest(target=target):
                link.symlink_to(target)
                with self.assertRaisesRegex(ValueError, 'symlink'): self.run_export()
                link.unlink()
        self.assert_no_closure()

    def test_only_top_level_environment_is_excluded(self):
        nested = self.root / 'worker/environment'; nested.mkdir(parents=True)
        (nested / 'forbidden').symlink_to(self.outside)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.run_export()
        self.assert_no_closure()

    def test_included_fifo_is_rejected_without_opening(self):
        os.mkfifo(self.root / 'fifo')
        with self.assertRaisesRegex(ValueError, 'nonregular'): self.run_export()
        self.assert_no_closure()

    def test_missing_proof_files_fail_closed(self):
        environment_fixture(self.root, self.outside)
        for name in ('bootstrap-receipt.json', export.ENVIRONMENT_LOCK, export.INSTALLATION_RECEIPT):
            with self.subTest(name=name):
                path = self.root / name; raw = path.read_bytes(); path.unlink()
                with self.assertRaises(ValueError): self.run_export()
                path.write_bytes(raw)
                self.assert_no_closure()

    def test_bootstrap_cannot_outlive_missing_environment_root(self):
        environment_fixture(self.root, self.outside)
        (self.root / 'environment').rename(self.base / 'removed-environment')
        with self.assertRaisesRegex(ValueError, 'requires its environment directory'): self.run_export()
        self.assert_no_closure()

    def test_changed_lock_or_installation_proof_fails(self):
        environment_fixture(self.root, self.outside)
        for name in (export.ENVIRONMENT_LOCK, export.INSTALLATION_RECEIPT):
            with self.subTest(name=name):
                path = self.root / name; raw = path.read_bytes(); path.write_bytes(raw + b' ')
                with self.assertRaisesRegex(ValueError, 'binding differs'): self.run_export()
                path.write_bytes(raw)
        self.assert_no_closure()

    def test_bootstrap_path_hash_status_and_command_are_exact(self):
        environment_fixture(self.root, self.outside)
        path = self.root / 'bootstrap-receipt.json'; raw = path.read_bytes(); baseline = json.loads(raw)
        for key, value in (('environment_lock_path', str(self.outside / 'environment-lock.json')),
                           ('environment_lock_path', str(self.root / 'environment/../' / export.ENVIRONMENT_LOCK)),
                           ('actual_environment_lock_sha256', '0' * 64), ('status', 'unverified'),
                           ('installed_offline', 1), ('python_command', [])):
            with self.subTest(key=key, value=value):
                path.write_bytes(canonical({**baseline, key: value}))
                with self.assertRaises(ValueError): self.run_export()
                path.write_bytes(raw)
        self.assert_no_closure()

    def test_proof_symlink_or_ancestor_symlink_is_not_allowed(self):
        environment_fixture(self.root, self.outside)
        path = self.root / export.INSTALLATION_RECEIPT; raw = path.read_bytes(); path.unlink()
        path.symlink_to(self.root / export.ENVIRONMENT_LOCK)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.run_export()
        path.unlink(); path.write_bytes(raw)
        evidence = (self.root / export.ENVIRONMENT_LOCK).parent
        moved = evidence.with_name('moved-evidence'); evidence.rename(moved)
        evidence.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.run_export()
        self.assert_no_closure()

    def test_oversized_proof_is_rejected_before_archive_creation(self):
        environment_fixture(self.root, self.outside)
        (self.root / 'bootstrap-receipt.json').write_bytes(b' ' * (export.PROOF_LIMIT + 1))
        with self.assertRaisesRegex(ValueError, 'proof byte bound'): self.run_export()
        self.assertFalse((self.root / 'archives').exists())

    def test_deadline_and_path_escape_are_rejected(self):
        with self.assertRaises(TimeoutError): self.run_export(deadline=time.monotonic() - 1)
        with self.assertRaisesRegex(ValueError, 'traversal'): self.run_export(self.root / '..' / 'output')
        for run_id in ('../escape', '/absolute', 'a/b', 'x\\y'):
            with self.assertRaisesRegex(ValueError, 'safe export'): self.run_export(run_id=run_id)
        self.assert_no_closure()

    def test_existing_dangling_archive_identity_is_consumed(self):
        (self.root / 'archives').symlink_to(self.base / 'missing')
        with self.assertRaisesRegex(ValueError, 'identity consumed'): self.run_export()
        self.assert_no_closure()

    def test_replacement_link_after_inventory_is_rejected(self):
        original = shutil.disk_usage
        def swap(path):
            item = self.root / 'summary.json'; item.unlink(); item.symlink_to(self.outside / 'never-open')
            return original(path)
        with mock.patch.object(export.shutil, 'disk_usage', side_effect=swap):
            with self.assertRaisesRegex(ValueError, 'symlink'): self.run_export()
        self.assert_no_closure()

    def test_changed_file_during_zip_copy_cannot_publish_closure(self):
        original = export._read_file
        def change(path, deadline, **kwargs):
            if kwargs.get('destination') is not None and Path(path).name == 'summary.json':
                Path(path).write_bytes(b'changed after pre-copy hash')
            return original(path, deadline, **kwargs)
        with mock.patch.object(export, '_read_file', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'changed during archive'): self.run_export()
        self.assert_no_closure()

    def test_proof_changed_during_archive_cannot_publish_closure(self):
        environment_fixture(self.root, self.outside)
        original = export._read_file
        def change(path, deadline, **kwargs):
            if kwargs.get('destination') is not None and Path(path).name == 'summary.json':
                with (self.root / export.ENVIRONMENT_LOCK).open('ab') as stream: stream.write(b' ')
            return original(path, deadline, **kwargs)
        with mock.patch.object(export, '_read_file', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'binding differs'): self.run_export()
        self.assert_no_closure()

    def test_separate_artifact_changed_after_inventory_cannot_publish_closure(self):
        path = self.root / 'worker/checkpoints/state.pt'; path.parent.mkdir(parents=True); path.write_bytes(b'original')
        original = export._read_file
        def change(item, deadline, **kwargs):
            if kwargs.get('destination') is not None: path.write_bytes(b'changed')
            return original(item, deadline, **kwargs)
        with mock.patch.object(export, '_read_file', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'separate artifact changed'): self.run_export()
        self.assert_no_closure()


@unittest.skipUnless(platform.system() == 'Linux' and platform.machine() == 'x86_64' and
                     __import__('sys').version_info[:2] == (3, 12), 'CPU CPython 3.12 fixture required')
class OfflineLauncherExportTests(unittest.TestCase):
    def test_real_pinned_installer_and_launcher_owner_seal_evaluator_export(self):
        with tempfile.TemporaryDirectory(prefix='offline-export-') as tmp:
            base = Path(tmp); output = base / 'output'; output.mkdir()
            # The frozen helper is exact. Only the package material is synthetic.
            self.assertEqual(sha(Path(offline.__file__)), offline_bootstrap.HELPER_PINS['arc_next_offline_environment.py'])
            wheels = Wheelhouse(base)
            environment = output / 'environment/environment-cp312-cu128'; environment.parent.mkdir()
            lock = offline.install_offline(wheels.source, wheels.root, environment, enabled=True)
            self.assertTrue((environment / 'evidence/wheels').is_symlink())
            self.assertEqual((environment / 'evidence/wheels').resolve(), wheels.wheels)
            write_bootstrap(output, lock)
            cpython = output / 'environment/cpython312/python/bin'; cpython.mkdir(parents=True)
            (cpython / 'python3.12').write_bytes(b'explicit synthetic CPython payload')
            (cpython / 'python3').symlink_to('python3.12')
            assets = make_assets(base); worker = output / 'worker'; worker.mkdir()
            run_id = 'synthetic-offline-export'
            source = evaluation.source_identity()
            clock = SessionClock.create(output / 'session-clock.json', run_id, started_epoch=time.time() - 2400,
                                        origin='pre-dispatch')
            clock_raw = (output / 'session-clock.json').read_bytes()
            request = {'format': 'irisx/learning-owner-request-v1', 'run_id': run_id,
                'source_identity': source, 'solver_root': assets['solver_root'],
                'solver_manifest_sha256': assets['solver_manifest_sha256'], 'output_root': str(worker),
                'config': {'tiny_cpu': True, 'fixture_tasks': 120}, 'clock': clock.record}
            atomic_json(worker / 'request.json', request, exclusive=True)
            script = base / 'synthetic-owner.py'
            script.write_text(_SYNTHETIC_OWNER.replace('REPOSITORY', repr(str(evaluation.ROOT))))
            with (worker / 'stderr.txt').open('wb') as error:
                guard = OwnedProcessGuard.spawn([*lock['python_command'], str(script), str(worker / 'request.json'), digest(request)],
                    evidence_dir=worker / 'process-guard', cwd=worker, stdout=subprocess.DEVNULL, stderr=error,
                    env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                         'PYTHONDONTWRITEBYTECODE': '1'})
                self.addCleanup(lambda: guard.stop(timeout=5) if guard.poll() is None else None)
                until = time.monotonic() + 90
                while guard.poll() is None and time.monotonic() < until: time.sleep(0.05)
                if guard.poll() is None: guard.stop(timeout=5)
            self.assertEqual(guard.child.returncode, 0, (worker / 'stderr.txt').read_text())
            proof = guard.closed_proof(); self.assertTrue(verify_closed_proof(proof))
            self.assertFalse(proof['forced']); self.assertEqual(proof['worker_returncode'], 0)
            result = worker / 'result.json'
            closure = {'format': 'irisx/learning-owner-closure-v1', 'worker_identity': guard.identity,
                'returncode': guard.child.returncode, 'graceful': True, 'source_identity_sha256': digest(source),
                'request_sha256': digest(request), 'result_sha256': sha(result), 'session_members': [],
                'parent_identity': evaluation.process_identity(os.getpid()), 'process_tree_proof': proof}
            atomic_json(output / 'owner-closure.json', closure, exclusive=True)
            seal = evaluation.seal_predictions(output / 'predictions', solver_root=assets['solver_root'],
                solver_manifest_sha256=assets['solver_manifest_sha256'], evaluator_manifest_sha256=assets['evaluator_manifest_sha256'],
                result_path=result, closure=closure, bindings={'run_id': run_id, 'prediction_origin': 'synthetic_cpu'})
            scored = evaluation.evaluate_sealed(output / 'predictions', seal['sha256'], solver_root=assets['solver_root'],
                evaluator_root=assets['evaluator_root'], output_root=output / 'evaluation', deadline=time.monotonic() + 60)
            self.assertEqual(scored['status'], 'SCORED')
            self.assertEqual((scored['tasks'], scored['tests']), (120, 167))
            self.assertEqual(scored['prediction_origin'], 'synthetic_cpu'); self.assertFalse(scored['training_used'])
            receipt = export.export_evidence(output, run_id=run_id, deadline=time.monotonic() + 60)
            self.assertEqual(sha(Path(receipt['archive']['path'])), receipt['archive']['sha256'])
            self.assertEqual(json.loads((output / 'post-seal-closure.json').read_bytes()), receipt)
            with zipfile.ZipFile(receipt['archive']['path']) as archive:
                inventory = json.loads(archive.read('evidence-inventory.json'))
                self.assertEqual(digest(inventory), receipt['inventory_sha256'])
                self.assertEqual({name for name in archive.namelist() if name.startswith('environment/')},
                                 {export.ENVIRONMENT_LOCK, export.INSTALLATION_RECEIPT})
                for name, row in inventory['files'].items():
                    raw = archive.read(name)
                    self.assertEqual(raw, (output / name).read_bytes())
                    self.assertEqual(row, {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
                self.assertEqual(inventory['files'][export.ENVIRONMENT_LOCK]['sha256'],
                                 json.loads(archive.read('bootstrap-receipt.json'))['actual_environment_lock_sha256'])
            self.assertEqual((output / 'session-clock.json').read_bytes(), clock_raw)
            self.assertEqual(clock.record['deadline_epoch'], clock.record['started_epoch'] + 43200)


if __name__ == '__main__': unittest.main()

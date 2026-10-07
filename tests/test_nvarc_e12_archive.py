"""CPU-only E12 archive finalization; synthetic files, no native/provider work."""
import copy
import hashlib
import os
from pathlib import Path
import stat
import unittest
from unittest.mock import patch
import zipfile

from tools import nvarc_e12_archive as archive
from tools import nvarc_e12_delivery_envelope as delivery
from tests import test_nvarc_e12_delivery_envelope as delivery_tests


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.fixture = delivery_tests.DeliveryEnvelopeTests('test_missing_evidence_remains_unknown')
        self.fixture.setUp(); f = self.fixture
        f.archive_path.unlink()
        self.parent = f.root; self.root = f.root/f.run; self.root.mkdir()
        self.plan = f.plan; self.sha = f.sha; self.observation = copy.deepcopy(f.observation)
        self.observation['output_capture']['bytes_retained'] = 4
        self.files = dict(f.files); self.files.pop('outer-supervision.json')
        self.files['coordinator-output.log'] = b'mock'
        self.flush()

    def tearDown(self): self.fixture.tearDown()

    def flush(self):
        for name, body in self.files.items():
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)

    def finalize(self, **changes):
        return archive.finalize(self.root, changes.get('observation', self.observation), changes.get('sha', self.sha))

    def verify(self):
        return delivery.verify_envelope(self.parent, run_id=self.root.name, plan_sha256=self.sha)

    def full_complete(self):
        terminal = copy.deepcopy(self.fixture.terminal); terminal['outcome'] = 'complete'; terminal['cleanup']['workers'] = []
        for rank in range(4):
            launch = copy.deepcopy(self.fixture.launch)
            launch.update(pid=234+rank, process_group_id=234+rank)
            launch['binding'].update(rank=rank, task_id=list(delivery.TASKS)[rank])
            row = copy.deepcopy(self.fixture.terminal['cleanup']['workers'][0]); row.update(identity=str(rank), pid=234+rank)
            terminal['cleanup']['workers'].append(row)
            self.files[f'workers/{rank}/process-launch.json'] = delivery.canonical(launch)
            self.files[f'workers/{rank}/result.json'] = delivery.canonical(dict(outcome='complete', binding=launch['binding']))
            for arm in delivery.ARMS:
                for name in delivery.ARM_FILES:
                    self.files[f'workers/{rank}/arms/{arm}/{name}'] = b'{}\n'
        self.files['terminal.json'] = delivery.canonical(terminal); self.flush()

    def test_full_fake_completion_delivers_exact_post_write_result(self):
        self.full_complete(); result = self.finalize()
        self.assertTrue(result['final_archive_created'], result)
        self.assertTrue(result['finalization_qualified'], result)
        self.assertTrue(result['delivery_bundle_created'], result)
        self.assertEqual(self.verify()['completion']['runtime_outcome'], 'complete')
        raw = self.parent/(self.root.name+'.zip')
        with zipfile.ZipFile(result['delivery_bundle_path']) as bundle:
            self.assertEqual(bundle.read('runtime.zip'), raw.read_bytes())
            sidecar = delivery.parse(bundle.read('sidecar.json'))
            evidence = delivery.parse(bundle.read('finalizer-result.json'))
            self.assertFalse(sidecar['receipt_written']); self.assertFalse(sidecar['finalization_qualified'])
            self.assertTrue(evidence['finalization_timing']['receipt_written'])
            self.assertNotIn('delivery_bundle_sha256', evidence)
        self.assertEqual(stat.S_IMODE(raw.stat().st_mode), 0o400)

    def test_native_failed_result_keeps_full_evidence_without_native_success(self):
        result = self.finalize()
        self.assertTrue(result['final_archive_created'], result)
        self.assertTrue(result['delivery_bundle_created'], result)
        self.assertEqual(self.verify()['completion']['runtime_outcome'], 'failed')
        self.assertEqual(self.verify()['completion']['runtime_qualification'], 'not_assessed')

    def test_unknown_python_or_json_is_diagnostic_only(self):
        (self.root/'unknown.py').write_text('no execution')
        result = self.finalize()
        self.assertFalse(result['final_archive_created']); self.assertTrue(result['diagnostic_only_archive_created'], result)
        self.assertFalse(result['finalization_qualified']); self.assertTrue(result['delivery_bundle_created'], result)
        self.assertEqual(self.verify()['completion']['runtime_qualification'], 'diagnostic_only')
        with zipfile.ZipFile(self.parent/(self.root.name+'.zip')) as value:
            self.assertNotIn('unknown.py', value.namelist())

    def test_hash_mutation_is_diagnostic_and_cannot_be_full(self):
        (self.root/'tools/returned-code.py').write_bytes(b'mutated')
        result = self.finalize()
        self.assertFalse(result['final_archive_created']); self.assertTrue(result['diagnostic_only_archive_created'], result)
        self.assertTrue(result['delivery_bundle_created'], result)

    def test_unconfirmed_producer_rejected_before_reading_root(self):
        observation = copy.deepcopy(self.observation); observation['confirmed_stopped'] = False
        with patch.object(archive.delivery.os, 'open', side_effect=AssertionError('no I/O')):
            result = self.finalize(observation=observation)
        self.assertFalse(result['final_archive_created']); self.assertFalse(result['delivery_bundle_created'])
        self.assertIn('outer stop', result['diagnostic_errors'][0])

    def test_worker_cleanup_failure_does_not_archive_any_source(self):
        terminal = copy.deepcopy(self.fixture.terminal); terminal['cleanup']['workers'][0]['group_absent'] = False
        (self.root/'terminal.json').write_bytes(delivery.canonical(terminal))
        with patch.object(archive, '_inventory', side_effect=AssertionError('must not scan')):
            result = self.finalize()
        self.assertFalse(result['final_archive_created']); self.assertFalse(result['diagnostic_only_archive_created'])
        self.assertFalse((self.parent/(self.root.name+'.zip')).exists())

    def test_proven_early_launch_failure_emits_bounded_diagnostic(self):
        import shutil
        shutil.rmtree(self.root/'workers'); (self.root/'terminal.json').unlink()
        self.observation.update(launched=False, launch_failed=True, returncode=None,
            coordinator_pid=None, coordinator_process_group_id=None, coordinator_start_new_session=None)
        self.observation['reserve_preserved'] = False
        self.observation['e12_supervision'].update(coordinator_stopped_monotonic=None, reserve_preserved=False, errors=[{'phase':'launch'}])
        result = self.finalize()
        self.assertTrue(result['diagnostic_only_archive_created'], result)
        self.assertTrue(result['delivery_bundle_created'], result)
        self.assertEqual(self.verify()['completion']['runtime_outcome'], 'prelaunch_failure')

    def test_late_finalizer_retains_failure_and_creates_nothing(self):
        with patch.object(delivery.time, 'monotonic', return_value=3700.): result = self.finalize()
        self.assertFalse(result['finalization_qualified']); self.assertFalse(result['delivery_bundle_created'])
        self.assertFalse((self.parent/(self.root.name+'.zip')).exists())

    def test_runtime_destination_race_preserves_foreign_inode(self):
        original = os.link; target = self.parent/(self.root.name+'.zip')
        def race(source, destination, **kw):
            if destination == self.root.name+'.zip': target.write_bytes(b'competitor')
            return original(source, destination, **kw)
        with patch.object(archive.os, 'link', side_effect=race): result = self.finalize()
        self.assertEqual(target.read_bytes(), b'competitor'); self.assertFalse(result['finalization_qualified'])

    def test_source_symlink_downgrades_to_safe_diagnostic(self):
        target = self.root/'tools/returned-code.py'; target.unlink(); target.symlink_to('/etc/hostname')
        result = self.finalize()
        self.assertTrue(result['diagnostic_only_archive_created'], result)
        self.assertFalse(result['finalization_qualified'])

    def test_exact_cache_excluded_but_nested_symlink_rejected(self):
        cache = self.root/'workers/0/unsloth_compiled_cache'; cache.mkdir()
        (cache/'generated.py').write_text('not archive code')
        paths = archive.validate_members(self.root)
        self.assertNotIn(cache/'generated.py', paths)
        (cache/'bad').symlink_to('/tmp')
        with self.assertRaisesRegex(ValueError, 'symlink'): archive.validate_members(self.root)

    def test_cache_size_and_traversal_caps_are_enforced(self):
        cache = self.root/'workers/0/triton-cache'; cache.mkdir()
        (cache/'large').write_bytes(b'123456')
        with patch.object(archive, 'MAX_TREE_BYTES', 1), self.assertRaisesRegex(ValueError, 'byte cap'):
            archive.validate_members(self.root)
        with patch.object(archive, 'MAX_TREE_ENTRIES', 1), self.assertRaisesRegex(ValueError, 'entry cap'):
            archive.validate_members(self.root)

    def test_misplaced_compiler_cache_and_unknown_arm_rejected(self):
        for name in ('unsloth_compiled_cache/generated.py', 'workers/4/unsloth_compiled_cache/a.py',
                     'workers/0/arms/s64/result.json', 'workers/0/arms/ttt64/unknown.json'):
            with self.subTest(name=name), self.assertRaises(ValueError): delivery.member_kind(name, self.plan)

    def test_partial_json_and_ledger_tail_retained_but_truth_rejected(self):
        path = self.root/'workers/0/result.json.tmp'; path.write_bytes(b'{"outcome":')
        self.assertIn(path, archive.validate_members(self.root))
        path.write_bytes(b'{"official_score":')
        with self.assertRaisesRegex(ValueError, 'evaluator'): archive.validate_members(self.root)

    def test_cross_run_plan_hash_rejected(self):
        result = self.finalize(sha='0'*64)
        self.assertFalse(result['final_archive_created']); self.assertFalse(result['delivery_bundle_created'])
        self.assertIn('exact canonical', result['diagnostic_errors'][0])

    def test_cannot_replace_anonymous_temporary_inode(self):
        original = os.link
        def check(source, destination, **kw):
            self.assertTrue(source.startswith('/proc/self/fd/'))
            self.assertEqual(os.stat(source).st_nlink, 0)
            return original(source, destination, **kw)
        with patch.object(archive.os, 'link', side_effect=check): result = self.finalize()
        self.assertTrue(result['delivery_bundle_created'], result)

    def test_original_archive_is_never_rewritten(self):
        path = self.parent/(self.root.name+'.zip'); path.write_bytes(b'old evidence')
        result = self.finalize()
        self.assertTrue(result['existing_archive_preserved']); self.assertEqual(path.read_bytes(), b'old evidence')
        self.assertFalse(result['delivery_bundle_created'])

    def test_late_publication_preserves_bytes_but_cannot_claim_completion(self):
        original_link = os.link; original_sync = os.fsync; published = []
        def link(source, destination, **kw):
            original_link(source, destination, **kw); published.append(destination)
        def sync(fd):
            original_sync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode) and published[-1:] == [self.root.name+'.zip']:
                delivery.time.monotonic.return_value = 3701.
        with patch.object(archive.os, 'link', side_effect=link), patch.object(archive.os, 'fsync', side_effect=sync):
            result = self.finalize()
        self.assertTrue(result['final_archive_created'], result)
        self.assertTrue(result['finalization_timing']['archive_exists'])
        self.assertFalse(result['finalization_qualified']); self.assertFalse(result['delivery_bundle_created'])
        self.assertTrue((self.parent/(self.root.name+'.zip')).is_file())

    def test_empty_unregistered_worker_directory_blocks_all_archives(self):
        (self.root/'workers/1').mkdir()
        result = self.finalize()
        self.assertFalse(result['final_archive_created']); self.assertFalse(result['diagnostic_only_archive_created'])
        self.assertIn('registered worker', result['diagnostic_errors'][0])

    def test_missing_complete_arm_evidence_is_diagnostic(self):
        self.full_complete(); (self.root/'workers/0/arms/ttt64/prefix-trace.json').unlink()
        result = self.finalize()
        self.assertFalse(result['final_archive_created']); self.assertTrue(result['diagnostic_only_archive_created'], result)
        self.assertTrue(result['delivery_bundle_created'], result)

    def test_inventory_inode_replacement_is_rejected(self):
        actual = archive._read; target = self.root/'coordinator-output.log'; raced = []
        def read(fd, name, limit, deadline, **kw):
            if name == 'coordinator-output.log' and kw.get('expected') is not None and not raced:
                target.unlink(); target.write_bytes(b'fake'); raced.append(True)
            return actual(fd, name, limit, deadline, **kw)
        with patch.object(archive, '_read', side_effect=read), self.assertRaisesRegex(ValueError, 'inode changed'):
            archive.validate_members(self.root)

    def test_launched_pre_admission_failure_preserves_capture_and_original_bootstrap(self):
        import shutil
        shutil.rmtree(self.root/'workers'); (self.root/'terminal.json').unlink()
        original = b'{"message":"actual entry rejection"}'
        (self.root/'bootstrap-failure.json').write_bytes(original)
        self.observation['returncode'] = 1
        result = self.finalize()
        self.assertTrue(result['diagnostic_only_archive_created'], result)
        self.assertTrue(result['delivery_bundle_created'], result)
        self.assertEqual(self.verify()['completion']['runtime_outcome'], 'pre_admission_failure')
        with zipfile.ZipFile(self.parent/(self.root.name+'.zip')) as value:
            self.assertEqual(value.read('bootstrap-failure.json'), original)
            self.assertEqual(value.read('coordinator-output.log'), b'mock')

    def test_missing_terminal_after_admission_never_fabricates_worker_cleanup(self):
        import shutil
        shutil.rmtree(self.root/'workers'); (self.root/'terminal.json').unlink()
        (self.root/'coordinator-admitted.json').write_bytes(b'{}')
        self.observation['returncode'] = 1
        result = self.finalize()
        self.assertFalse(result['diagnostic_only_archive_created']); self.assertFalse(result['final_archive_created'])

    def test_uncommitted_generation_tail_is_indexed_but_selected_corruption_rejected(self):
        directory = self.root/'.output-generations'/('a'*32); directory.mkdir(parents=True)
        (directory/'ttt64-answers.json').write_bytes(b'{"answer":')
        result = self.finalize()
        self.assertTrue(result['delivery_bundle_created'], result)
        with zipfile.ZipFile(self.parent/(self.root.name+'.zip')) as value:
            index = delivery.parse(value.read('interrupted-retention.json'))
            self.assertEqual(index['artifacts'][0]['kind'], 'uncommitted generation member')
            self.assertFalse(index['candidate_qualification'])
        (self.root/'output-commit.json').write_bytes(delivery.canonical(dict(generation='a'*32)))
        with self.assertRaisesRegex(ValueError, 'committed JSON'): archive.validate_members(self.root)

    def test_anonymous_temporary_support_absence_fails_closed(self):
        actual = archive.os.open
        def unsupported(path, flags, *args, **kwargs):
            if flags & os.O_TMPFILE == os.O_TMPFILE: raise OSError('synthetic unsupported anonymous inode')
            return actual(path, flags, *args, **kwargs)
        with patch.object(archive.os, 'open', side_effect=unsupported): result = self.finalize()
        self.assertFalse(result['final_archive_created']); self.assertFalse(result['delivery_bundle_created'])
        self.assertFalse((self.parent/(self.root.name+'.zip')).exists())

    def test_late_receipt_write_cannot_be_upgraded_by_immutable_sidecar(self):
        original_link = os.link; original_sync = os.fsync; published = []
        def link(source, destination, **kw):
            original_link(source, destination, **kw); published.append(destination)
        def sync(fd):
            original_sync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode) and published[-1:] == [self.root.name+'-finalization-receipt.json']:
                delivery.time.monotonic.return_value = 3701.
        with patch.object(archive.os, 'link', side_effect=link), patch.object(archive.os, 'fsync', side_effect=sync):
            result = self.finalize()
        sidecar = delivery.parse((self.parent/(self.root.name+'-finalization-receipt.json')).read_bytes())
        self.assertFalse(sidecar['receipt_written']); self.assertFalse(sidecar['finalization_qualified'])
        self.assertFalse(result['finalization_qualified']); self.assertFalse(result['delivery_bundle_created'])

    def test_unattempted_preflight_failure_never_fabricates_a_launch(self):
        import shutil
        shutil.rmtree(self.root/'workers'); (self.root/'terminal.json').unlink()
        self.observation.update(launched=False, launch_failed=False, prelaunch_failed=True,
            launch_attempted=False, launch_uncertain=False, returncode=None, reserve_preserved=False,
            coordinator_pid=None, coordinator_process_group_id=None, coordinator_start_new_session=None)
        self.observation['e12_supervision'].update(coordinator_stopped_monotonic=None,
            reserve_preserved=False, errors=[{'phase':'preflight', 'message':'exact dependency mount missing'}])
        result = self.finalize()
        self.assertTrue(result['diagnostic_only_archive_created'], result)
        self.assertTrue(result['delivery_bundle_created'], result)
        with zipfile.ZipFile(result['delivery_bundle_path']) as bundle:
            observation = delivery.parse(bundle.read('stop-evidence.json'))['observation']
            self.assertFalse(observation['launch_attempted']); self.assertFalse(observation['launch_failed'])

    def test_actual_cleanup_prelaunch_helper_interoperates_with_finalizer(self):
        import shutil
        from tools.nvarc_e12_cleanup import prelaunch_failure
        shutil.rmtree(self.root/'workers'); (self.root/'terminal.json').unlink()
        capture = self.root/'coordinator-output.log'; capture.unlink()
        try: raise RuntimeError('synthetic dependency discovery failure')
        except RuntimeError as error:
            self.observation = prelaunch_failure(capture, started=100., error=error, now=lambda: 1600.)
        result = self.finalize()
        self.assertTrue(result['diagnostic_only_archive_created'], result)
        self.assertTrue(result['delivery_bundle_created'], result)
        self.assertIn('synthetic dependency discovery failure', result['coordinator_diagnostic_excerpt'])
        self.assertEqual(self.verify()['completion']['runtime_outcome'], 'prelaunch_failure')


if __name__ == '__main__': unittest.main()

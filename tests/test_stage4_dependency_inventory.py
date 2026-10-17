"""Only synthetic opaque bytes and our own stdlib inventory code execute here."""
from tests.platform_requirements import requires_linux
import ast
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('our_dependency_inventory', ROOT/'tools/stage4_dependency_inventory.py')
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inventory-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.target = self.folder/'output-bytes'
        self.target.mkdir()
        self.evidence = self.folder/'synthetic-provider-evidence'
        self.evidence.mkdir()
        self.receipt = self.folder/'synthetic-only-receipt.json'
        self.fixtures = {'native/flash_attn_fake.so': b'\x7fELF\x00SYNTHETIC-NOT-A-NATIVE-LIBRARY',
                         'qwen3.patch': b'SYNTHETIC inert patch\n',
                         'sitecustomize.py': b'raise RuntimeError("NEVER EXECUTE THIS FIXTURE")\n',
                         'start.pth': b'import NEVER_EXECUTE_DISCOVERED_FILES\n',
                         'pkg/module.py': b'raise RuntimeError("opaque only")\n',
                         'wheel.whl': b'SYNTHETIC opaque archive, not an installed wheel\n'}
        self.make_fixture(self.fixtures)

    def make_fixture(self, fixtures):
        for name, body in fixtures.items():
            path = self.target/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        identity = inventory.canonical({'synthetic': True, 'ref': inventory.REF,
            'version_number': 2, 'script_version_id': 272622465})
        listing = inventory.canonical({'synthetic': True, 'complete': True,
                                      'files': sorted(fixtures)})
        (self.evidence/'identity-response.json').write_bytes(identity)
        (self.evidence/'listing-response.json').write_bytes(listing)
        receipt = {'format': inventory.RECEIPT_FORMAT, 'run_id': inventory.RUN_ID,
            'provider': 'kaggle', 'ref': inventory.REF, 'version_number': 2,
            'script_version_id': 272622465, 'observed_utc': '2026-10-06T10:00:00Z',
            'listing_complete': True, 'listing_pages': 1,
            'scope': 'complete-provider-output-files', 'provider_file_count': len(fixtures),
            'identity_response_sha256': inventory.sha(identity),
            'listing_response_sha256': inventory.sha(listing), 'files': []}
        for name, body in sorted(fixtures.items()):
            receipt['files'].append({'path': name, 'bytes': len(body), 'sha256': inventory.sha(body),
                'download_host': 'www.kaggleusercontent.com', 'download_status': 200,
                'download_path_script_version_id': 272622465})
        self.receipt.write_bytes(inventory.canonical(receipt))
        return receipt

    def observe(self, limits=inventory.MAXIMUM):
        return inventory.inventory(self.target, self.receipt, self.evidence, limits)

    def amend(self, action):
        receipt = json.loads(self.receipt.read_bytes())
        action(receipt)
        self.receipt.write_bytes(inventory.canonical(receipt))

    def assertBlocked(self, code, limits=inventory.MAXIMUM):
        with self.assertRaisesRegex(inventory.InventoryError, code):
            self.observe(limits)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_exact_synthetic_hashes_no_execution_or_mount_claim(self):
        first = self.observe()
        self.assertEqual(inventory.canonical(first), inventory.canonical(self.observe()))
        self.assertEqual(first['file_count'], len(self.fixtures))
        self.assertEqual(first['total_file_bytes'], sum(map(len, self.fixtures.values())))
        for name, body in self.fixtures.items():
            self.assertEqual(first['files'][name]['bytes'], len(body))
            self.assertEqual(first['files'][name]['sha256'], hashlib.sha256(body).hexdigest())
        self.assertEqual(first['files']['sitecustomize.py']['kind'], 'startup-candidate-opaque')
        self.assertEqual(first['files']['native/flash_attn_fake.so']['kind'], 'native-binary-opaque')
        self.assertEqual(first['files']['wheel.whl']['kind'], 'archive-opaque-members-not-inventoried')
        self.assertEqual(first['directories'], ['native', 'pkg'])
        for field in ('actual_current_mount_inventoried', 'api_output_to_mount_equivalence_verified',
                      'archive_members_inventoried', 'safe_to_import_or_execute', 'source_license_verified'):
            self.assertIs(first[field], False)
        self.assertEqual(first['discovered_files_imported_or_executed'], 0)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_current_identity_keeps_historical_reference_separate(self):
        def amend(receipt):
            receipt['version_number'] = 3
            receipt['script_version_id'] = 999
            for row in receipt['files']:
                row['download_path_script_version_id'] = 999
        self.amend(amend)
        self.assertFalse(self.observe()['historical_reference']['matches_observed_identity'])

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_identity_schema_listing_and_download_bindings_fail_closed(self):
        checks = [('receipt-identity', lambda r: r.update(ref='someone/other')),
                  ('receipt-schema', lambda r: r.update(credentials='not allowed')),
                  ('incomplete-provider-listing', lambda r: r.update(listing_complete=False)),
                  ('incomplete-provider-listing', lambda r: r.update(listing_pages=129)),
                  ('receipt-timestamp', lambda r: r.update(observed_utc='2026-10-06T10:00:00')),
                  ('download-version-binding', lambda r: r['files'][0].update(download_path_script_version_id=1)),
                  ('download-version-binding', lambda r: r['files'][0].update(download_host='untrusted.example')),
                  ('download-version-binding', lambda r: r['files'][0].update(download_status=True))]
        original = self.receipt.read_bytes()
        for code, amend in checks:
            with self.subTest(code=code):
                self.receipt.write_bytes(original)
                self.amend(amend)
                self.assertBlocked(code)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_duplicate_paths_and_json_keys(self):
        def amend(receipt):
            receipt['files'].append(receipt['files'][0])
            receipt['provider_file_count'] += 1
        self.amend(amend)
        self.assertBlocked('duplicate-provider-path')
        with self.assertRaisesRegex(inventory.InventoryError, 'duplicate-json-key'):
            inventory.parse(b'{"a":1,"a":2}')
        with self.assertRaises(inventory.InventoryError):
            inventory.parse(b'{"a":NaN}')

    def test_path_semantics_and_sensitive_roots(self):
        for name in ('../escape', '/absolute', 'a//b', 'a/./b', 'a\\b', 'C:drive', 'a\x00b',
                     '.kaggle/kaggle.json', 'arc-agi_training_solutions.json', 'e\u0301.py'):
            with self.subTest(name=name), self.assertRaises(inventory.InventoryError):
                inventory.path_parts(name, inventory.MAXIMUM)
        self.assertEqual(inventory.path_parts('normal/é.py', inventory.MAXIMUM), ['normal', 'é.py'])
        with self.assertRaisesRegex(inventory.InventoryError, 'unsafe-path'):
            inventory.path_parts('x'*1025, inventory.MAXIMUM)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_file_count_single_total_metadata_and_directory_caps(self):
        self.assertBlocked('file-count-cap', replace(inventory.MAXIMUM, file_count=1))
        self.assertBlocked('single-file-byte-cap', replace(inventory.MAXIMUM, single_file_bytes=1))
        self.assertBlocked('total-file-byte-cap', replace(inventory.MAXIMUM, total_file_bytes=1))
        self.assertBlocked('metadata-byte-cap', replace(inventory.MAXIMUM, receipt_bytes=1))
        self.assertBlocked('metadata-byte-cap', replace(inventory.MAXIMUM, evidence_file_bytes=1))
        self.assertBlocked('directory-count-cap', replace(inventory.MAXIMUM, directory_count=1))
        with self.assertRaisesRegex(inventory.InventoryError, 'limits-range'):
            self.observe(replace(inventory.MAXIMUM, file_count=inventory.MAXIMUM.file_count+1))

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_digest_size_evidence_and_listing_order_tamper(self):
        original = self.receipt.read_bytes()
        self.amend(lambda r: r['files'][0].update(sha256='0'*64))
        self.assertBlocked('file-digest-binding')
        self.receipt.write_bytes(original)
        self.amend(lambda r: r['files'][0].update(bytes=0))
        self.assertBlocked('file-count-or-size-binding')
        self.receipt.write_bytes(original)
        self.amend(lambda r: r['files'].reverse())
        self.assertBlocked('ordered-provider-listing')
        self.receipt.write_bytes(original)
        (self.evidence/'identity-response.json').write_bytes(b'{}')
        self.assertBlocked('provider-evidence-digest')

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_unlisted_file_and_empty_directory_are_rejected(self):
        extra = self.target/'unlisted.py'
        extra.write_bytes(b'not executed')
        self.assertBlocked('unlisted-file')
        extra.unlink()
        (self.target/'unlisted-empty-directory').mkdir()
        self.assertBlocked('unlisted-directory')

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_symlink_hardlink_fifo_and_symlink_root_are_rejected(self):
        path = self.target/'qwen3.patch'
        path.unlink()
        os.symlink(self.receipt, path)
        self.assertBlocked('nonregular-or-hardlinked-file')
        path.unlink()
        os.link(self.target/'sitecustomize.py', path)
        self.assertBlocked('nonregular-or-hardlinked-file')
        path.unlink()
        os.mkfifo(path)
        self.assertBlocked('nonregular-or-hardlinked-file')
        linked_root = self.folder/'root-alias'
        linked_root.symlink_to(self.target, target_is_directory=True)
        with self.assertRaises(OSError):
            inventory.inventory(linked_root, self.receipt, self.evidence)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_file_mutation_during_read_is_rejected(self):
        original = inventory.os.read
        changed = False
        def read(fd, size):
            nonlocal changed
            result = original(fd, size)
            if not changed and result == self.fixtures['native/flash_attn_fake.so']:
                changed = True
                (self.target/'native/flash_attn_fake.so').write_bytes(b'changed')
            return result
        with patch.object(inventory.os, 'read', read):
            self.assertBlocked('file-changed')
        self.assertTrue(changed)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_new_output_and_output_cap_are_enforced(self):
        output = self.folder/'report.json'
        with self.assertRaisesRegex(inventory.InventoryError, 'output-byte-cap'):
            inventory.write_new(output, b'12345', 4)
        self.assertFalse(output.exists())
        inventory.write_new(output, b'1234', 4)
        self.assertEqual(output.read_bytes(), b'1234')
        with self.assertRaisesRegex(inventory.InventoryError, 'new-output-identity-required'):
            inventory.write_new(output, b'new', 4)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_wall_alarm_interrupts_pending_work(self):
        old = inventory.arm_wall(0.03)
        try:
            with self.assertRaisesRegex(inventory.InventoryError, 'wall-time-cap'):
                time.sleep(1)
        finally:
            inventory.disarm_wall(old)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_cli_isolated_startup_ignores_synthetic_dependency_path(self):
        marker = self.folder/'forbidden-startup-marker'
        body = ('from pathlib import Path\nPath('+repr(str(marker))+').write_text("executed")\n').encode()
        (self.target/'sitecustomize.py').write_bytes(body)
        self.fixtures['sitecustomize.py'] = body
        self.make_fixture(self.fixtures)
        output = self.folder/'cli-report.json'
        env = dict(os.environ, PYTHONPATH=str(self.target))
        result = subprocess.run([sys.executable, '-I', '-S', str(ROOT/'tools/stage4_dependency_inventory.py'),
            '--root', str(self.target), '--receipt', str(self.receipt), '--evidence', str(self.evidence),
            '--output', str(output)], cwd=self.target, env=env, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertFalse(marker.exists())
        self.assertFalse(list(self.target.rglob('__pycache__')))
        self.assertEqual(json.loads(output.read_bytes())['discovered_files_imported_or_executed'], 0)

    def test_nonisolated_cli_is_rejected_and_never_writes_output(self):
        # Plain interpreter is started from our trusted controller, not the input tree.
        result = subprocess.run([sys.executable, '-S', str(ROOT/'tools/stage4_dependency_inventory.py')],
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'python-I-S-required', result.stderr)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_cli_bad_digest_leaves_no_report(self):
        self.amend(lambda r: r['files'][0].update(sha256='0'*64))
        output = self.folder/'no-report.json'
        result = subprocess.run([sys.executable, '-I', '-S', str(ROOT/'tools/stage4_dependency_inventory.py'),
            '--root', str(self.target), '--receipt', str(self.receipt), '--evidence', str(self.evidence),
            '--output', str(output)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name+'.pending').exists())

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_inert_package_closed_deterministic_exact_member_pins(self):
        one = self.folder/'package-one.zip'
        two = self.folder/'package-two.zip'
        report = inventory.build_package(one)
        self.assertEqual(report['sha256'], inventory.build_package(two)['sha256'])
        self.assertEqual(one.read_bytes(), two.read_bytes())
        with zipfile.ZipFile(one) as archive:
            self.assertEqual(archive.namelist(), ['README.txt', 'inventory-plan.json',
                                                 'inventory.py', 'package-bindings.json'])
            plan = json.loads(archive.read('inventory-plan.json'))
            self.assertFalse(plan['approved'])
            self.assertEqual(plan['kernel_sources'], [])
            self.assertEqual(plan['minimum_remote_disclosure']['code_files'], [])
            self.assertEqual(plan['metadata_stage_limits']['maximum_output_file_byte_download_requests'], 0)
            self.assertEqual(plan['byte_stage_admission']['maximum_file_requests'], 0)
            self.assertEqual(plan['byte_stage_admission']['minimum_disk_reserve_bytes'], 5*1024**3)
            bindings = json.loads(archive.read('package-bindings.json'))
            for name, pin in bindings['files'].items():
                body = archive.read(name)
                self.assertEqual(pin, {'bytes': len(body), 'sha256': inventory.sha(body)})
            source = ast.parse(archive.read('inventory.py'))
            imports = set()
            for node in ast.walk(source):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module.split('.')[0])
            self.assertLessEqual(imports, sys.stdlib_module_names | {'__future__'})
            self.assertNotIn('subprocess', imports)
            self.assertNotIn('socket', imports)

    def listing(self):
        receipt = json.loads(self.receipt.read_bytes())
        listing = {key: value for key, value in receipt.items()
                   if key not in ('run_id', 'provider', 'scope', 'provider_file_count')}
        listing['format'] = 'irisx/stage4-dependency-output-listing-v1'
        listing['files'] = [{'path': row['path'], 'bytes': row['bytes']} for row in receipt['files']]
        path = self.folder/'synthetic-normalized-listing.json'
        path.write_bytes(inventory.canonical(listing))
        return path

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_exact_byte_proposal_requires_disk_reserve_without_authorizing_fetch(self):
        space = type('Space', (), {'f_bavail': 24*1024**3, 'f_frsize': 1})()
        with patch.object(inventory.os, 'fstatvfs', return_value=space):
            proposal = inventory.prepare_acquisition_proposal(self.listing(), self.evidence,
                                                              self.target, list(self.fixtures))
        self.assertFalse(proposal['approved'])
        self.assertTrue(proposal['no_download_authority'])
        self.assertEqual(proposal['maximum_byte_download_requests_until_approval'], 0)
        self.assertEqual(proposal['proposed_exact_file_requests'], len(self.fixtures))
        self.assertEqual(proposal['proposed_total_file_bytes'], sum(map(len, self.fixtures.values())))
        required = proposal['disk_check']['required_available_bytes']
        fake = type('Space', (), {'f_bavail': required-1, 'f_frsize': 1})()
        with patch.object(inventory.os, 'fstatvfs', return_value=fake):
            with self.assertRaisesRegex(inventory.InventoryError, 'destination-free-disk-reserve'):
                inventory.prepare_acquisition_proposal(self.listing(), self.evidence, self.target, list(self.fixtures))
        fake.f_bavail = required
        with patch.object(inventory.os, 'fstatvfs', return_value=fake):
            self.assertEqual(inventory.prepare_acquisition_proposal(self.listing(), self.evidence,
                             self.target, list(self.fixtures))['disk_check']['available_bytes'], required)

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_proposal_missing_current_script_identity_is_blocked(self):
        listing_path = self.listing()
        listing = json.loads(listing_path.read_bytes())
        listing['script_version_id'] = None
        listing_path.write_bytes(inventory.canonical(listing))
        with self.assertRaisesRegex(inventory.InventoryError, 'incomplete-provider-listing'):
            inventory.prepare_acquisition_proposal(listing_path, self.evidence, self.target, list(self.fixtures))

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_proposal_requires_explicit_selection_and_preserves_partial_scope(self):
        listing = self.listing()
        for selection in (None, [], ['missing'], ['qwen3.patch', 'qwen3.patch']):
            with self.subTest(selection=selection), self.assertRaisesRegex(inventory.InventoryError,
                                                                        'explicit-selected-paths'):
                inventory.prepare_acquisition_proposal(listing, self.evidence, self.target, selection)
        space = type('Space', (), {'f_bavail': 24*1024**3, 'f_frsize': 1})()
        with patch.object(inventory.os, 'fstatvfs', return_value=space):
            proposal = inventory.prepare_acquisition_proposal(listing, self.evidence, self.target, ['qwen3.patch'])
        self.assertEqual(proposal['scope'], 'selected-provider-output-files')
        self.assertEqual(proposal['provider_file_count'], len(self.fixtures))
        self.assertEqual(proposal['proposed_exact_file_requests'], 1)
        self.assertEqual(proposal['proposed_files'], [{'path': 'qwen3.patch',
                                                    'bytes': len(self.fixtures['qwen3.patch'])}])

    @requires_linux('Inventory platform_valid requires POSIX descriptor APIs, setitimer and filesystem reserve observations')
    def test_selected_local_copy_does_not_claim_complete_provider_inventory(self):
        for name in self.fixtures:
            if name != 'qwen3.patch':
                (self.target/name).unlink()
        (self.target/'native').rmdir()
        (self.target/'pkg').rmdir()
        self.amend(lambda r: r.update(scope='selected-provider-output-files',
                                      files=[row for row in r['files'] if row['path'] == 'qwen3.patch']))
        result = self.observe()
        self.assertFalse(result['all_provider_output_files_inventoried'])
        self.assertEqual(result['file_count'], 1)
        self.assertEqual(result['provider_file_count'], len(self.fixtures))


if __name__ == '__main__':
    unittest.main(verbosity=2)

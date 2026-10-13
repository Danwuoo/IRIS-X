"""Meaningful restore rejection fixtures; nested archives remain opaque."""
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

from . import verify_transfer as v


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).absolute()

    def archive(self, name, entries, *, manifest=None, mode=stat.S_IFREG | 0o600):
        path = self.root / name
        expected = {key: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                    for key, raw in entries}
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
                for key, raw in [*entries, (v.INVENTORY_NAME, v.canonical(expected if manifest is None else manifest))]:
                    info = zipfile.ZipInfo(key, (2026, 10, 14, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = mode << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, raw)
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_roundtrip_and_verify_only_leave_nested_archive_opaque(self):
        nested = b'opaque bytes; intentionally not even a valid nested zip'
        archive, sha = self.archive('good.zip', [('source/file.txt', b'code'), ('evaluator/evidence.zip', nested)])
        report = v.process(archive_path=archive, expected_sha256=sha)
        self.assertFalse(report['extracted'])
        output = self.root / 'restored'
        report = v.process(archive_path=archive, expected_sha256=sha, output_root=output)
        self.assertTrue(report['all_member_hashes_and_CRC_verified'])
        self.assertEqual((output / 'evaluator/evidence.zip').read_bytes(), nested)

    def test_traversal_and_nonportable_names_rejected_before_output(self):
        for index, name in enumerate(('../escape', '/absolute', 'C:/drive', 'dir\\file', 'CON.txt',
                                      '.', 'dir?file', 'dir<file', 'dir"file', 'dir|file', 'dir*file')):
            with self.subTest(name=name):
                archive, sha = self.archive(f'unsafe{index}.zip', [(name, b'data')])
                output = self.root / f'output{index}'
                with self.assertRaises(v.TransferError):
                    v.process(archive_path=archive, expected_sha256=sha, output_root=output)
                self.assertFalse(output.exists())

    def test_embedded_nul_central_name_rejected(self):
        archive, unused_sha = self.archive('nul.zip', [('file!evil', b'data')])
        raw = archive.read_bytes().replace(b'file!evil', b'file\x00evil')
        archive.write_bytes(raw)
        with self.assertRaisesRegex(v.TransferError, 'truncated member'):
            v.process(archive_path=archive, expected_sha256=hashlib.sha256(raw).hexdigest())

    def test_link_and_special_payload_rejected(self):
        for index, mode in enumerate((stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFDIR | 0o700)):
            with self.subTest(mode=mode):
                archive, sha = self.archive(f'kind{index}.zip', [('member', b'target')], mode=mode)
                with self.assertRaisesRegex(v.TransferError, 'regular payload'):
                    v.process(archive_path=archive, expected_sha256=sha)

    def test_duplicate_casefold_and_parent_collisions_rejected(self):
        fixtures = [[('same', b'a'), ('same', b'b')], [('Case', b'a'), ('case', b'b')],
                    [('parent', b'a'), ('parent/child', b'b')]]
        for index, entries in enumerate(fixtures):
            with self.subTest(entries=entries):
                archive, sha = self.archive(f'collision{index}.zip', entries)
                with self.assertRaisesRegex(v.TransferError, 'collision'):
                    v.process(archive_path=archive, expected_sha256=sha)

    def test_member_tamper_detected_before_destination_exists(self):
        bad = {'file': {'bytes': 4, 'sha256': hashlib.sha256(b'good').hexdigest()}}
        archive, sha = self.archive('tamper.zip', [('file', b'evil')], manifest=bad)
        output = self.root / 'tampered-output'
        with self.assertRaisesRegex(v.TransferError, 'bytes/hash'):
            v.process(archive_path=archive, expected_sha256=sha, output_root=output)
        self.assertFalse(output.exists())

    def test_outer_hash_and_existing_destination_rejected(self):
        archive, sha = self.archive('input.zip', [('file', b'good')])
        with self.assertRaisesRegex(v.TransferError, 'outer archive SHA'):
            v.process(archive_path=archive, expected_sha256='0' * 64)
        output = self.root / 'existing'
        output.mkdir()
        (output / 'keep').write_bytes(b'preserve')
        with self.assertRaisesRegex(v.TransferError, 'existing output'):
            v.process(archive_path=archive, expected_sha256=sha, output_root=output)
        self.assertEqual((output / 'keep').read_bytes(), b'preserve')

    @unittest.skipUnless(os.name == 'posix', 'POSIX ancestor link fixture')
    def test_symlink_ancestor_rejected(self):
        archive, sha = self.archive('real.zip', [('file', b'good')])
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(v.TransferError, 'link/reparse'):
            v.process(archive_path=alias / archive.name, expected_sha256=sha)


if __name__ == '__main__':
    unittest.main()

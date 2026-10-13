"""Path/integrity tests for the CPU-only transfer wrapper; no original proof fabrication."""
import ast
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from . import rebuild_portable as r


class PortableBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).absolute()
        self.repo = self.root / 'repo'
        self.inputs = self.root / 'inputs'
        self.repo.mkdir()
        self.inputs.mkdir()

    @unittest.skipUnless(os.name == 'posix', 'actual builder requires POSIX')
    def test_explicit_relocated_roots_admitted(self):
        output = self.repo / '.irisx/relocated-rebuild'
        self.assertEqual(r.validate_paths(self.repo, self.inputs, output),
                         (self.repo, self.inputs, output))

    def test_relative_path_rejected(self):
        with self.assertRaisesRegex(r.RebuildError, 'absolute'):
            r.validate_paths(self.repo, self.inputs, Path('relative-output'))

    def test_outside_repository_rejected(self):
        with self.assertRaisesRegex(r.RebuildError, 'below repository'):
            r.validate_paths(self.repo, self.inputs, self.root / 'external-output')

    def test_existing_output_preserved(self):
        output = self.repo / '.irisx/previous'
        output.mkdir(parents=True)
        marker = output / 'keep'
        marker.write_bytes(b'previous attempt')
        with self.assertRaisesRegex(r.RebuildError, 'existing output'):
            r.validate_paths(self.repo, self.inputs, output)
        self.assertEqual(marker.read_bytes(), b'previous attempt')

    def test_input_output_overlap_rejected(self):
        inputs = self.repo / '.irisx/inputs'
        inputs.mkdir(parents=True)
        with self.assertRaisesRegex(r.RebuildError, 'overlap'):
            r.validate_paths(self.repo, inputs, inputs / 'rebuild')

    @unittest.skipUnless(os.name == 'posix', 'POSIX link fixture')
    def test_symlink_ancestor_rejected(self):
        alias = self.root / 'repo-alias'
        alias.symlink_to(self.repo, target_is_directory=True)
        with self.assertRaisesRegex(r.RebuildError, 'link/reparse'):
            r.validate_paths(alias, self.inputs, alias / '.irisx/rebuild')

    def test_tampered_input_and_extra_member_rejected(self):
        member = self.inputs / 'fixture.txt'
        member.write_bytes(b'original')
        inventory = {'fixture.txt': {'bytes': 8, 'sha256': hashlib.sha256(b'original').hexdigest()}}
        r.closed_tree(self.inputs, inventory)
        member.write_bytes(b'tampered')
        with self.assertRaisesRegex(r.RebuildError, 'inventory bytes differ'):
            r.closed_tree(self.inputs, inventory)
        member.write_bytes(b'original')
        (self.inputs / 'extra.txt').write_bytes(b'extra')
        with self.assertRaisesRegex(r.RebuildError, 'closed file set'):
            r.closed_tree(self.inputs, inventory)

    def test_inventory_traversal_rejected(self):
        for name in ('../outside', '/absolute', 'drive:stream', 'dir\\file'):
            with self.subTest(name=name), self.assertRaises(r.RebuildError):
                r.relative(name)

    def test_help_needs_no_auth_or_runtime_import(self):
        proc = subprocess.run([sys.executable, '-B', str(Path(r.__file__)), '--help'],
                              capture_output=True, text=True, check=True)
        self.assertIn('--inputs-root', proc.stdout)
        tree = ast.parse(Path(r.__file__).read_text(encoding='utf-8'))
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertNotIn('kaggle', imports)
        self.assertFalse(any(value and ('publication_run007' in value or 'owned_runtime' in value)
                             for value in imports))


if __name__ == '__main__':
    unittest.main()
